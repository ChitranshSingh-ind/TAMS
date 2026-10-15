"""
TAMS Bulk Student Management & Promotion Dialog.

Provides an administrative modal interface to transfer cohorts of students
between academic batches (batch promotion/reassignment) and update enrollment
lifecycle statuses (ACTIVE, INACTIVE, ALUMNI) in bulk.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import SessionLocal
from app.services.student_service import (
    bulk_update_student_batch,
    bulk_update_student_status,
    get_students_by_batch,
)
from app.ui.theme import (
    CREAM,
    DARK_NAVY,
    GOLD,
    LIGHT_GOLD,
    MUTED,
    NAVY,
    SUCCESS_GREEN,
    TEXT,
    WHITE,
)


class BulkStudentDialog(QDialog):
    """
    Modal dialog allowing teachers to select multiple students and apply
    bulk operations such as batch transfers/promotions or status updates.
    """

    def __init__(self, batches, initial_batch_id: int | None = None, parent=None):
        """
        Initialize the BulkStudentDialog.

        Args:
            batches: Iterable of active Batch model instances.
            initial_batch_id: Optional initial batch ID to pre-filter the source list.
            parent: Parent QWidget.
        """
        super().__init__(parent)
        self.batches = list(batches)
        self.initial_batch_id = initial_batch_id
        self._updating_checks = False

        self.setWindowTitle("Bulk Student Operations & Batch Promotion")
        self.setMinimumSize(780, 640)
        self.resize(840, 700)

        self._setup_ui()
        self._load_students_data()

    def _setup_ui(self):
        """Build and style dialog layout and widgets."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 22)
        main_layout.setSpacing(14)

        # ── Header Section ───────────────────────────────────
        header_box = QVBoxLayout()
        header_box.setSpacing(4)

        title = QLabel("👥 Bulk Student Operations & Promotion")
        title.setStyleSheet(f"""
            QLabel {{
                color: {NAVY};
                font-size: 19px;
                font-weight: 700;
            }}
        """)

        subtitle = QLabel(
            "Transfer student cohorts to new batches or update enrollment lifecycle statuses in a single action."
        )
        subtitle.setStyleSheet(f"""
            QLabel {{
                color: {MUTED};
                font-size: 13px;
            }}
        """)

        header_box.addWidget(title)
        header_box.addWidget(subtitle)
        main_layout.addLayout(header_box)

        # ── Source Filters Bar ───────────────────────────────
        filter_frame = QFrame()
        filter_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CREAM};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 8px;
                padding: 4px;
            }}
        """)
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(12, 10, 12, 10)
        filter_layout.setSpacing(12)

        # Batch filter dropdown
        batch_lbl = QLabel("Source Batch:")
        batch_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 12px;")
        self.source_batch_combo = QComboBox()
        self.source_batch_combo.addItem("All Batches", None)
        for b in self.batches:
            self.source_batch_combo.addItem(b.name, b.id)

        if self.initial_batch_id is not None:
            idx = self.source_batch_combo.findData(self.initial_batch_id)
            if idx >= 0:
                self.source_batch_combo.setCurrentIndex(idx)

        self.source_batch_combo.currentIndexChanged.connect(self._load_students_data)
        filter_layout.addWidget(batch_lbl)
        filter_layout.addWidget(self.source_batch_combo)

        # Status filter dropdown
        status_lbl = QLabel("Status:")
        status_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 12px;")
        self.source_status_combo = QComboBox()
        self.source_status_combo.addItem("All Statuses", "ALL")
        self.source_status_combo.addItem("ACTIVE", "ACTIVE")
        self.source_status_combo.addItem("INACTIVE", "INACTIVE")
        self.source_status_combo.addItem("ALUMNI", "ALUMNI")
        self.source_status_combo.addItem("LEFT", "LEFT")
        self.source_status_combo.currentIndexChanged.connect(self._apply_table_filters)
        filter_layout.addWidget(status_lbl)
        filter_layout.addWidget(self.source_status_combo)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search student by name or admission no...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(34)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {WHITE};
                color: {TEXT};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {NAVY};
            }}
        """)
        self.search_input.textChanged.connect(self._apply_table_filters)
        filter_layout.addWidget(self.search_input, 1)

        main_layout.addWidget(filter_frame)

        # ── Selection Controls Bar ───────────────────────────
        sel_bar = QHBoxLayout()
        sel_bar.setSpacing(10)

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setFixedHeight(30)
        self.select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WHITE};
                color: {NAVY};
                border: 1px solid {GOLD};
                border-radius: 5px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {LIGHT_GOLD};
            }}
        """)
        self.select_all_btn.clicked.connect(self._select_all_visible)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.setFixedHeight(30)
        self.deselect_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.deselect_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WHITE};
                color: {MUTED};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 5px;
                padding: 4px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {CREAM};
            }}
        """)
        self.deselect_all_btn.clicked.connect(self._deselect_all)

        self.selection_label = QLabel("0 students selected")
        self.selection_label.setStyleSheet(f"""
            QLabel {{
                color: {NAVY};
                font-weight: 700;
                font-size: 12px;
                padding: 4px 10px;
                background-color: {LIGHT_GOLD};
                border-radius: 5px;
            }}
        """)

        sel_bar.addWidget(self.select_all_btn)
        sel_bar.addWidget(self.deselect_all_btn)
        sel_bar.addStretch()
        sel_bar.addWidget(self.selection_label)
        main_layout.addLayout(sel_bar)

        # ── Students Selection Table ─────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Admission No.",
            "Student Name",
            "Current Batch",
            "Current Status",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.itemChanged.connect(self._on_table_item_changed)
        self.table.itemClicked.connect(self._on_table_item_clicked)
        main_layout.addWidget(self.table, 1)

        # ── Action Tabs Card ─────────────────────────────────
        action_card = QFrame()
        action_card.setStyleSheet(f"""
            QFrame#actionCard {{
                background-color: {WHITE};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 8px;
            }}
        """)
        action_card.setObjectName("actionCard")
        action_card_layout = QVBoxLayout(action_card)
        action_card_layout.setContentsMargins(14, 12, 14, 12)
        action_card_layout.setSpacing(10)

        card_title = QLabel("Choose Bulk Operation to Apply:")
        card_title.setStyleSheet(f"color: {NAVY}; font-weight: 700; font-size: 13px;")
        action_card_layout.addWidget(card_title)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {LIGHT_GOLD};
                background: {WHITE};
                border-radius: 6px;
                padding: 10px;
            }}
            QTabBar::tab {{
                background: {CREAM};
                color: {TEXT};
                font-weight: 600;
                font-size: 12px;
                padding: 8px 16px;
                border: 1px solid {LIGHT_GOLD};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {NAVY};
                color: {WHITE};
                border-color: {NAVY};
            }}
        """)

        # Tab 1: Batch Promotion / Transfer
        tab_batch = QWidget()
        t_batch_layout = QVBoxLayout(tab_batch)
        t_batch_layout.setSpacing(10)
        t_batch_layout.setContentsMargins(8, 8, 8, 8)

        dest_row = QHBoxLayout()
        dest_lbl = QLabel("Target Destination Batch <span style='color: #DC2626; font-weight: bold;'>*</span>:")
        dest_lbl.setTextFormat(Qt.TextFormat.RichText)
        dest_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        self.target_batch_combo = QComboBox()
        self.target_batch_combo.setFixedHeight(34)
        for b in self.batches:
            self.target_batch_combo.addItem(b.name, b.id)

        dest_row.addWidget(dest_lbl)
        dest_row.addWidget(self.target_batch_combo, 1)
        t_batch_layout.addLayout(dest_row)

        batch_info = QLabel(
            "ℹ️ Selected students will be transferred into the target batch. "
            "Their historical attendance entries, test marks, and fee payment ledgers remain completely safe and intact."
        )
        batch_info.setWordWrap(True)
        batch_info.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        t_batch_layout.addWidget(batch_info)

        self.tab_widget.addTab(tab_batch, "🚀 Promote / Transfer to Batch")

        # Tab 2: Status Lifecycle Update
        tab_status = QWidget()
        t_status_layout = QVBoxLayout(tab_status)
        t_status_layout.setSpacing(10)
        t_status_layout.setContentsMargins(8, 8, 8, 8)

        stat_row = QHBoxLayout()
        stat_lbl = QLabel("New Lifecycle Status <span style='color: #DC2626; font-weight: bold;'>*</span>:")
        stat_lbl.setTextFormat(Qt.TextFormat.RichText)
        stat_lbl.setStyleSheet(f"color: {NAVY}; font-weight: 600; font-size: 13px;")
        self.target_status_combo = QComboBox()
        self.target_status_combo.setFixedHeight(34)
        self.target_status_combo.addItem("ACTIVE — Currently attending classes", "ACTIVE")
        self.target_status_combo.addItem("INACTIVE — Temporarily paused / suspended", "INACTIVE")
        self.target_status_combo.addItem("ALUMNI — Completed course / graduated", "ALUMNI")
        self.target_status_combo.addItem("LEFT — Left institute / withdrawn", "LEFT")

        stat_row.addWidget(stat_lbl)
        stat_row.addWidget(self.target_status_combo, 1)
        t_status_layout.addLayout(stat_row)

        status_info = QLabel(
            "ℹ️ Active students are included in daily attendance and tests. "
            "Inactive students are hidden from active registers. Alumni students represent completed academic cohorts."
        )
        status_info.setWordWrap(True)
        status_info.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        t_status_layout.addWidget(status_info)

        self.tab_widget.addTab(tab_status, "🏷️ Update Enrollment Status")

        action_card_layout.addWidget(self.tab_widget)
        main_layout.addWidget(action_card)

        # ── Dialog Action Buttons ────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WHITE};
                color: {TEXT};
                border: 1px solid {LIGHT_GOLD};
                border-radius: 6px;
                padding: 6px 18px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {CREAM};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)

        self.apply_btn = QPushButton("⚡ Apply Changes")
        self.apply_btn.setFixedHeight(38)
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY};
                color: {WHITE};
                border: 1px solid {GOLD};
                border-radius: 6px;
                padding: 6px 22px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {DARK_NAVY};
            }}
            QPushButton:pressed {{
                background-color: #001F3A;
            }}
        """)
        self.apply_btn.clicked.connect(self._on_apply_clicked)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.apply_btn)
        main_layout.addLayout(btn_layout)

    def _load_students_data(self):
        """Query students based on the selected source batch and populate the table."""
        source_batch_id = self.source_batch_combo.currentData()

        with SessionLocal() as session:
            students = get_students_by_batch(
                session,
                batch_id=source_batch_id,
                include_inactive=True,
            )

        self._updating_checks = True
        self.table.setRowCount(len(students))

        for row, s in enumerate(students):
            # Column 0: Checkable Admission Number
            adm_text = s.admission_number or "—"
            adm_item = QTableWidgetItem(f" {adm_text}")
            adm_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            adm_item.setCheckState(Qt.CheckState.Unchecked)
            # Store student ID in item user role
            adm_item.setData(Qt.ItemDataRole.UserRole, s.id)
            self.table.setItem(row, 0, adm_item)

            # Column 1: Full Name
            full_name = f"{s.first_name} {s.last_name or ''}".strip()
            name_item = QTableWidgetItem(full_name)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 1, name_item)

            # Column 2: Current Batch Name
            batch_name = s.batch.name if s.batch else "—"
            batch_item = QTableWidgetItem(batch_name)
            batch_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            batch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, batch_item)

            # Column 3: Current Status
            status_item = QTableWidgetItem(s.status or "ACTIVE")
            status_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, status_item)

        self._updating_checks = False
        self._apply_table_filters()

    def _apply_table_filters(self):
        """Filter table rows based on status dropdown and search text."""
        status_filter = self.source_status_combo.currentData()
        search_query = self.search_input.text().strip().lower()

        visible_count = 0
        for row in range(self.table.rowCount()):
            adm_item = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            status_item = self.table.item(row, 3)

            adm = adm_item.text().lower() if adm_item else ""
            name = name_item.text().lower() if name_item else ""
            status = status_item.text().strip().upper() if status_item else ""

            status_matches = (status_filter == "ALL") or (status == status_filter)
            text_matches = (not search_query) or (search_query in adm) or (search_query in name)

            visible = status_matches and text_matches
            self.table.setRowHidden(row, not visible)
            if visible:
                visible_count += 1

        self._update_selection_counter()

    def _on_table_item_clicked(self, item: QTableWidgetItem):
        """Toggle check state when clicking on row items for convenience."""
        row = item.row()
        adm_item = self.table.item(row, 0)
        if adm_item and item.column() != 0:
            current_state = adm_item.checkState()
            new_state = (
                Qt.CheckState.Unchecked
                if current_state == Qt.CheckState.Checked
                else Qt.CheckState.Checked
            )
            adm_item.setCheckState(new_state)

    def _on_table_item_changed(self, item: QTableWidgetItem):
        """Update selected count when checkboxes are toggled."""
        if not self._updating_checks and item.column() == 0:
            self._update_selection_counter()

    def _select_all_visible(self):
        """Check all visible rows in the table."""
        self._updating_checks = True
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                item = self.table.item(row, 0)
                if item:
                    item.setCheckState(Qt.CheckState.Checked)
        self._updating_checks = False
        self._update_selection_counter()

    def _deselect_all(self):
        """Uncheck all rows in the table."""
        self._updating_checks = True
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        self._updating_checks = False
        self._update_selection_counter()

    def _get_selected_student_ids(self) -> list[int]:
        """Collect IDs of all checked students."""
        selected_ids = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                student_id = item.data(Qt.ItemDataRole.UserRole)
                if student_id:
                    selected_ids.append(student_id)
        return selected_ids

    def _update_selection_counter(self):
        """Refresh badge showing how many students are currently selected."""
        count = len(self._get_selected_student_ids())
        self.selection_label.setText(f"{count} student{'s' if count != 1 else ''} selected")

    def _on_apply_clicked(self):
        """Validate input, ask user confirmation, and execute bulk changes."""
        selected_ids = self._get_selected_student_ids()
        if not selected_ids:
            QMessageBox.warning(
                self,
                "No Students Selected",
                "Please select at least one student from the table before applying bulk changes.",
            )
            return

        active_tab_index = self.tab_widget.currentIndex()

        if active_tab_index == 0:
            # Batch transfer / promotion
            target_batch_id = self.target_batch_combo.currentData()
            target_batch_name = self.target_batch_combo.currentText()
            if target_batch_id is None:
                QMessageBox.warning(self, "No Batch Selected", "Please select a valid destination batch.")
                return

            reply = QMessageBox.question(
                self,
                "Confirm Batch Transfer / Promotion",
                f"Are you sure you want to transfer {len(selected_ids)} student(s) to '{target_batch_name}'?\n\n"
                "Their historical attendance and test records will be preserved.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            try:
                with SessionLocal() as session:
                    count = bulk_update_student_batch(
                        session=session,
                        student_ids=selected_ids,
                        new_batch_id=target_batch_id,
                    )

                QMessageBox.information(
                    self,
                    "Batch Transfer Complete",
                    f"Successfully transferred {count} student(s) to '{target_batch_name}'.",
                )
                self.accept()

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Transfer Failed",
                    f"Failed to transfer students: {e}",
                )

        else:
            # Status update
            target_status = self.target_status_combo.currentData()
            status_display = self.target_status_combo.currentText()

            reply = QMessageBox.question(
                self,
                "Confirm Bulk Status Update",
                f"Are you sure you want to update the status of {len(selected_ids)} student(s) to '{status_display}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            try:
                with SessionLocal() as session:
                    count = bulk_update_student_status(
                        session=session,
                        student_ids=selected_ids,
                        new_status=target_status,
                    )

                QMessageBox.information(
                    self,
                    "Status Update Complete",
                    f"Successfully updated status for {count} student(s) to '{target_status}'.",
                )
                self.accept()

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Update Failed",
                    f"Failed to update student status: {e}",
                )
