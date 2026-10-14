import os
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app import __version__ as APP_VERSION
from app.services.coaching_helper_service import stop_helper_process
from app.ui.theme import (
    CREAM,
    DARK_NAVY,
    GLOBAL_FONT_FAMILY,
    GOLD,
    MUTED,
    NAVY,
    SUCCESS_GREEN,
    TEXT,
    WHITE,
)


class UpdateDownloadWorker(QThread):
    progress = pyqtSignal(int, int)  # (downloaded_bytes, total_bytes)
    finished = pyqtSignal(str)       # (downloaded_file_path)
    error = pyqtSignal(str)          # (error_message)

    def __init__(self, download_url: str, filename: str):
        super().__init__()
        self.download_url = download_url
        self.filename = filename
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            dest_dir = Path(tempfile.gettempdir()) / "TAMS_Updates"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / self.filename

            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": f"TAMS-Desktop-App/{APP_VERSION}"},
            )

            with urllib.request.urlopen(req, timeout=20.0) as resp:
                total_size = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 64 * 1024  # 64 KB

                with open(dest_path, "wb") as f:
                    while True:
                        if self._is_cancelled:
                            return
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total_size)

            if not self._is_cancelled:
                self.finished.emit(str(dest_path))
        except Exception as e:
            if not self._is_cancelled:
                self.error.emit(str(e))


class AppUpdateDialog(QDialog):
    """
    Dialog displaying the available update details and allowing 1-click
    automatic download and in-place upgrade.
    """

    def __init__(self, update_info: dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.update_info = update_info
        self.download_worker: Optional[UpdateDownloadWorker] = None
        self._is_downloading = False

        latest_version = update_info.get("latest_version", "New")
        self.setWindowTitle(f"Update Available - TAMS v{latest_version}")
        self.setMinimumWidth(560)
        self.setMinimumHeight(440)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {CREAM};
                font-family: {GLOBAL_FONT_FAMILY};
            }}
        """)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header Card
        header_card = QFrame()
        header_card.setStyleSheet(f"""
            QFrame {{
                background-color: {WHITE};
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(14, 12, 14, 12)
        h_layout.setSpacing(14)

        icon_lbl = QLabel("🚀")
        icon_lbl.setStyleSheet("font-size: 32px;")
        h_layout.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(4)

        title_lbl = QLabel("A new version of TAMS is available!")
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {NAVY};")
        title_box.addWidget(title_lbl)

        current_ver = self.update_info.get("current_version", APP_VERSION)
        latest_ver = self.update_info.get("latest_version", "Unknown")
        asset_name = self.update_info.get("asset_name") or f"TAMS_Setup_v{latest_ver}.exe"
        size_bytes = self.update_info.get("asset_size", 0)
        size_str = f"({size_bytes / (1024 * 1024):.1f} MB)" if size_bytes > 0 else ""

        subtitle_lbl = QLabel(
            f"Installed: <b>v{current_ver}</b> &nbsp;➔&nbsp; Latest: <span style='color: {SUCCESS_GREEN}; font-weight: bold;'>v{latest_ver}</span> &nbsp; {size_str}"
        )
        subtitle_lbl.setStyleSheet(f"font-size: 13px; color: {MUTED};")
        title_box.addWidget(subtitle_lbl)

        h_layout.addLayout(title_box)
        h_layout.addStretch()
        layout.addWidget(header_card)

        # Release Notes Section
        notes_label = QLabel("What's New in this Release:")
        notes_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {TEXT};")
        layout.addWidget(notes_label)

        self.notes_edit = QTextEdit()
        self.notes_edit.setReadOnly(True)
        raw_notes = self.update_info.get("release_notes", "").strip() or "General improvements and bug fixes."
        self.notes_edit.setPlainText(raw_notes)
        self.notes_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {WHITE};
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 10px;
                color: {TEXT};
                font-size: 12px;
                line-height: 1.4;
            }}
        """)
        layout.addWidget(self.notes_edit, 1)

        # Download Progress Area (Hidden by default)
        self.progress_container = QWidget()
        prog_layout = QVBoxLayout(self.progress_container)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.setSpacing(6)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #E2E8F0;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                height: 20px;
                text-align: center;
                font-weight: 600;
                color: #0F172A;
            }}
            QProgressBar::chunk {{
                background-color: {NAVY};
                border-radius: 5px;
            }}
        """)
        prog_layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("Ready to download update...")
        self.status_lbl.setStyleSheet(f"font-size: 12px; color: {MUTED};")
        prog_layout.addWidget(self.status_lbl)

        self.progress_container.setVisible(False)
        layout.addWidget(self.progress_container)

        # Button Bar
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        self.view_web_btn = QPushButton("🌐 View on GitHub")
        self.view_web_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid #CBD5E1;
                color: {TEXT};
                padding: 8px 14px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #E2E8F0;
            }}
        """)
        self.view_web_btn.clicked.connect(self._on_view_web_clicked)
        btn_bar.addWidget(self.view_web_btn)

        btn_bar.addStretch()

        self.cancel_btn = QPushButton("Remind Me Later")
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid #CBD5E1;
                color: {MUTED};
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #E2E8F0;
                color: {TEXT};
            }}
        """)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_bar.addWidget(self.cancel_btn)

        self.update_btn = QPushButton("⚡ Download & Update Now")
        self.update_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY};
                color: #FFFFFF;
                border: none;
                padding: 8px 18px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {DARK_NAVY};
            }}
            QPushButton:disabled {{
                background-color: #94A3B8;
            }}
        """)
        self.update_btn.clicked.connect(self._on_update_clicked)
        btn_bar.addWidget(self.update_btn)

        layout.addLayout(btn_bar)

    def _on_view_web_clicked(self):
        url = self.update_info.get("release_url", "https://github.com/ChitranshSingh-ind/TAMS/releases/latest")
        QDesktopServices.openUrl(QUrl(url))

    def _on_cancel_clicked(self):
        if self._is_downloading and self.download_worker:
            self.download_worker.cancel()
        self.reject()

    def _on_update_clicked(self):
        download_url = self.update_info.get("download_url")
        if not download_url:
            QMessageBox.information(
                self,
                "Web Download",
                "No direct installer binary was attached to the GitHub release. Opening release page in browser.",
            )
            self._on_view_web_clicked()
            self.accept()
            return

        latest_ver = self.update_info.get("latest_version", "latest")
        asset_name = self.update_info.get("asset_name") or f"TAMS_Setup_v{latest_ver}.exe"

        self._is_downloading = True
        self.update_btn.setEnabled(False)
        self.update_btn.setText("Downloading...")
        self.cancel_btn.setText("Cancel Download")
        self.progress_container.setVisible(True)
        self.status_lbl.setText("Connecting to server...")

        self.download_worker = UpdateDownloadWorker(download_url, asset_name)
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.error.connect(self._on_download_error)
        self.download_worker.start()

    def _on_download_progress(self, downloaded: int, total: int):
        if total > 0:
            percent = int((downloaded / total) * 100)
            self.progress_bar.setValue(percent)
            mb_down = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self.status_lbl.setText(f"Downloading update: {mb_down:.1f} MB / {mb_total:.1f} MB ({percent}%)")
        else:
            self.progress_bar.setRange(0, 0)  # Indeterminate
            mb_down = downloaded / (1024 * 1024)
            self.status_lbl.setText(f"Downloading update: {mb_down:.1f} MB downloaded...")

    def _on_download_error(self, err_msg: str):
        self._is_downloading = False
        self.update_btn.setEnabled(True)
        self.update_btn.setText("⚡ Retry Download")
        self.cancel_btn.setText("Close")
        self.status_lbl.setText(f"❌ Download failed: {err_msg}")
        QMessageBox.warning(
            self,
            "Download Error",
            f"Failed to download the update package:\n{err_msg}\n\nYou can manually download it from GitHub.",
        )

    def _on_download_finished(self, file_path: str):
        self._is_downloading = False
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.status_lbl.setText("✅ Download complete! Preparing to install...")

        if sys.platform == "win32":
            # Gracefully terminate background companion helper before installer overwrites files
            try:
                stop_helper_process(timeout_seconds=2.0)
            except Exception:
                pass

            import subprocess

            try:
                # Launch Inno Setup in silent mode with automatic close and restart
                subprocess.Popen([file_path, "/SILENT", "/SP-", "/CLOSEAPPLICATIONS"])
                QApplication.instance().quit()
                sys.exit(0)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Installation Failed",
                    f"Could not launch the installer automatically:\n{e}\n\nPlease run the installer manually from:\n{file_path}",
                )
        else:
            QMessageBox.information(
                self,
                "Update Downloaded",
                f"Update successfully downloaded to:\n{file_path}\n\n(On Windows, this automatically installs and restarts TAMS).",
            )
            self.accept()
