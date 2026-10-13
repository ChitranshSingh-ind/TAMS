"""
CoachingHelper Companion Service for TAMS.
Runs background queue processing, automated database backups,
connectivity-aware retry management, health reporting, single-instance locking,
and IPC process supervision. Works cross-platform (Windows & Linux).
"""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.database.connection import DATA_DIR, SessionLocal
from app.services.backup_service import create_database_backup, list_backups
from app.services.messaging_service import (
    get_messaging_overview_stats,
    process_message_queue,
)

logger = logging.getLogger("TAMS.CoachingHelperService")

APP_VERSION = "2.0.0"
HELPER_STATUS_FILE = DATA_DIR / "helper_status.json"
HELPER_LOCK_FILE = DATA_DIR / "coaching_helper.lock"
HELPER_CONTROL_FILE = DATA_DIR / "helper_control.json"
HELPER_LOG_DIR = DATA_DIR / "logs"
HELPER_LOG_FILE = HELPER_LOG_DIR / "coaching_helper.log"

WINDOWS_AUTOSTART_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WINDOWS_AUTOSTART_APP_NAME = "TAMS CoachingHelper"


def get_helper_status_file_path() -> Path:
    """Returns the path to helper_status.json."""
    return HELPER_STATUS_FILE


# ─────────────────────────────────────────────────────────────────────────────
# 1. LOGGING & SENSITIVE DATA MASKING
# ─────────────────────────────────────────────────────────────────────────────

class SensitiveDataLogFilter(logging.Filter):
    """
    Scrubs Meta Graph API access tokens, bearer tokens, and sensitive credentials
    from all log records before writing to disk.
    """
    _PATTERNS = [
        (re.compile(r"EAA[a-zA-Z0-9_\-]{20,}"), "EAA***[REDACTED]"),
        (re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{15,}", re.IGNORECASE), "Bearer [REDACTED]"),
        (re.compile(r'(access_token["\']?\s*[:=]\s*["\']?)([^"\'&\s]{10,})', re.IGNORECASE), r'\1[REDACTED]'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            for pattern, repl in self._PATTERNS:
                msg = pattern.sub(repl, msg)
            record.msg = msg
        return True


def setup_helper_logging(log_level: int = logging.INFO) -> None:
    """
    Configures a bounded 5MB rotating file logger with 3 backups for CoachingHelper.
    Ensures log directories exist and sensitive tokens are masked.
    """
    HELPER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    root_helper_logger = logging.getLogger("TAMS")
    
    # Check if rotating file handler already exists
    for h in root_helper_logger.handlers:
        if isinstance(h, RotatingFileHandler) and Path(h.baseFilename) == HELPER_LOG_FILE:
            return

    try:
        file_handler = RotatingFileHandler(
            HELPER_LOG_FILE,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.addFilter(SensitiveDataLogFilter())
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        root_helper_logger.addHandler(file_handler)
    except Exception as e:
        logger.warning("Could not setup rotating log handler: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# 2. PROCESS LIVENESS & SINGLE-INSTANCE LOCKING
# ─────────────────────────────────────────────────────────────────────────────

def is_pid_alive(pid: int) -> bool:
    """
    Verifies if a process with the given PID is actively executing.
    Works reliably on Windows (via Win32 API) and Unix (via signal 0).
    """
    if pid <= 0:
        return False

    if sys.platform == "win32":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid
            )
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(handle)
            STILL_ACTIVE = 259
            return exit_code.value == STILL_ACTIVE
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


class SingleInstanceLock:
    """
    Ensures only a single instance of CoachingHelper background process runs.
    Uses POSIX fcntl on Linux/macOS and msvcrt on Windows.
    Recovers cleanly from orphaned/stale lock files when previous processes crash.
    """

    def __init__(self, lock_path: Path = HELPER_LOCK_FILE):
        self.lock_path = lock_path
        self.lock_file_fd = None
        self._is_locked = False

    def acquire(self) -> bool:
        """
        Attempts to acquire exclusive lock.
        If a lock file exists, inspects the recorded PID. If the previous process
        has died (stale lock), automatically cleans it up and acquires the lock.
        """
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)

            # Check for stale lock file from a dead process
            if self.lock_path.exists() and not self._is_locked:
                existing_pid = self._read_locked_pid()
                if existing_pid and not is_pid_alive(existing_pid):
                    logger.info("Found stale lock file for inactive PID %d. Recovering lock.", existing_pid)
                    try:
                        self.lock_path.unlink(missing_ok=True)
                    except Exception:
                        pass

            self.lock_file_fd = open(self.lock_path, "a+")

            if sys.platform == "win32":
                import msvcrt
                try:
                    self.lock_file_fd.seek(0)
                    msvcrt.locking(self.lock_file_fd.fileno(), msvcrt.LK_NBLCK, 1)
                    self._is_locked = True
                except (IOError, OSError):
                    # Check if the process holding it is actually alive
                    existing_pid = self._read_locked_pid()
                    if existing_pid and not is_pid_alive(existing_pid):
                        self.lock_file_fd.close()
                        self.lock_file_fd = None
                        self.lock_path.unlink(missing_ok=True)
                        return self.acquire()
                    return False
            else:
                import fcntl
                try:
                    fcntl.flock(self.lock_file_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._is_locked = True
                except (IOError, OSError):
                    existing_pid = self._read_locked_pid()
                    if existing_pid and not is_pid_alive(existing_pid):
                        self.lock_file_fd.close()
                        self.lock_file_fd = None
                        self.lock_path.unlink(missing_ok=True)
                        return self.acquire()
                    return False

            # Record PID and timestamp into lock file
            self.lock_file_fd.seek(0)
            self.lock_file_fd.truncate()
            self.lock_file_fd.write(f"PID={os.getpid()}\nSTARTED={datetime.now(timezone.utc).isoformat()}\n")
            self.lock_file_fd.flush()
            return True

        except Exception as e:
            logger.error("Error acquiring single instance lock: %s", e)
            return False

    def _read_locked_pid(self) -> int | None:
        """Reads PID from current lock file content if possible."""
        try:
            if self.lock_path.exists():
                content = self.lock_path.read_text(encoding="utf-8")
                for line in content.splitlines():
                    if line.startswith("PID="):
                        return int(line.split("=")[1].strip())
        except Exception:
            pass
        return None

    def release(self):
        """Releases the lock and closes the file descriptor."""
        if not self._is_locked or not self.lock_file_fd:
            return
        try:
            if sys.platform == "win32":
                import msvcrt
                try:
                    self.lock_file_fd.seek(0)
                    msvcrt.locking(self.lock_file_fd.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            else:
                import fcntl
                try:
                    fcntl.flock(self.lock_file_fd.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
            self.lock_file_fd.close()
            self.lock_file_fd = None
            self._is_locked = False
            if self.lock_path.exists():
                try:
                    self.lock_path.unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception as e:
            logger.error("Error releasing lock: %s", e)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def is_helper_process_running() -> bool:
    """
    Checks whether another CoachingHelper process is currently active.
    Combines lock file existence, PID liveness verification, and heartbeat freshness.
    """
    # 1. Check lock file PID
    lock = SingleInstanceLock()
    locked_pid = lock._read_locked_pid()
    if locked_pid:
        if is_pid_alive(locked_pid):
            return True
        else:
            # Process died without removing lock file
            try:
                HELPER_LOCK_FILE.unlink(missing_ok=True)
            except Exception:
                pass

    # 2. Check status file heartbeat freshness (within 45 seconds) and PID
    status = read_helper_status()
    if not status:
        return False

    status_pid = status.get("pid")
    if status_pid and not is_pid_alive(status_pid):
        return False

    try:
        hb_str = status.get("heartbeat_at", "")
        if hb_str:
            hb = datetime.fromisoformat(hb_str)
            diff = (datetime.now(timezone.utc) - hb).total_seconds()
            return diff < 45.0
    except Exception:
        pass

    return False


# ─────────────────────────────────────────────────────────────────────────────
# 3. STATUS REPORTING & CONNECTIVITY CHECK
# ─────────────────────────────────────────────────────────────────────────────

def write_helper_status(status_data: dict[str, Any]) -> None:
    """Atomically writes status JSON for inspection by the main TAMS UI."""
    try:
        HELPER_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = HELPER_STATUS_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2)
        temp_file.replace(HELPER_STATUS_FILE)
    except Exception as e:
        logger.warning("Could not write helper status: %s", e)


def read_helper_status() -> dict[str, Any] | None:
    """Reads helper status JSON written by background process."""
    if not HELPER_STATUS_FILE.exists():
        return None
    try:
        with open(HELPER_STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def check_internet_connectivity(timeout: float = 3.0) -> bool:
    """
    Lightweight, bounded connectivity check to verify internet access.
    Checks TCP connection to Meta Graph API, Cloudflare, or Google DNS.
    """
    for target in ("graph.facebook.com", "1.1.1.1", "google.com"):
        try:
            socket.create_connection((target, 443), timeout=timeout).close()
            return True
        except (socket.timeout, OSError):
            continue
    return False


def check_for_updates() -> dict[str, Any]:
    """
    Checks GitHub Releases API for updates to TAMS.
    Gracefully handles network offline, rate limits, and parsing errors.
    """
    url = "https://api.github.com/repos/ChitranshSingh-ind/TAMS/releases/latest"
    headers = {"User-Agent": f"TAMS-Desktop-App/{APP_VERSION}", "Accept": "application/vnd.github.v3+json"}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                tag_name = data.get("tag_name", "").lstrip("v").strip()
                release_notes = data.get("body", "Bug fixes and performance improvements.")
                is_newer = tag_name > APP_VERSION if tag_name else False
                return {
                    "status": "update_available" if is_newer else "up_to_date",
                    "message": f"Update {tag_name} is available." if is_newer else "You are running the latest version of TAMS.",
                    "current_version": APP_VERSION,
                    "latest_version": tag_name or APP_VERSION,
                    "is_up_to_date": not is_newer,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "release_notes": release_notes,
                }
    except Exception as e:
        logger.debug("Update check returned offline/fallback: %s", e)

    # Return safe fallback status
    return {
        "status": "up_to_date",
        "message": "You are running the latest version of TAMS.",
        "current_version": APP_VERSION,
        "latest_version": APP_VERSION,
        "is_up_to_date": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "release_notes": "TAMS v2.0 - Coaching Intelligence, WhatsApp Integration & Analytics Suite.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. IPC (INTER-PROCESS COMMUNICATION) MECHANISM
# ─────────────────────────────────────────────────────────────────────────────

def send_helper_ipc_command(command: str) -> bool:
    """
    Sends an IPC command to the background CoachingHelper process.
    Commands supported: 'STOP', 'PAUSE', 'RESUME', 'RUN_CYCLE'.
    """
    valid_commands = {"STOP", "PAUSE", "RESUME", "RUN_CYCLE"}
    cmd_upper = command.strip().upper()
    if cmd_upper not in valid_commands:
        logger.error("Unknown helper IPC command: %s", command)
        return False

    try:
        HELPER_CONTROL_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = HELPER_CONTROL_FILE.with_suffix(".tmp")
        payload = {
            "command": cmd_upper,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "id": str(uuid.uuid4()),
        }
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        temp_file.replace(HELPER_CONTROL_FILE)
        logger.info("Sent IPC command '%s' to CoachingHelper", cmd_upper)
        return True
    except Exception as e:
        logger.error("Failed to write IPC command: %s", e)
        return False


def read_and_clear_helper_ipc_command() -> str | None:
    """
    Reads and consumes any pending IPC command file.
    Returns the command name or None if no command is waiting.
    """
    if not HELPER_CONTROL_FILE.exists():
        return None
    try:
        with open(HELPER_CONTROL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        HELPER_CONTROL_FILE.unlink(missing_ok=True)
        return data.get("command")
    except Exception as e:
        logger.debug("Error reading IPC command: %s", e)
        try:
            HELPER_CONTROL_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 5. WINDOWS AUTOSTART REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────

def is_windows_autostart_enabled() -> bool:
    """Checks whether CoachingHelper is set to run at Windows user login."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            WINDOWS_AUTOSTART_REG_KEY,
            0,
            winreg.KEY_READ,
        )
        val, _ = winreg.QueryValueEx(key, WINDOWS_AUTOSTART_APP_NAME)
        winreg.CloseKey(key)
        return bool(val)
    except Exception:
        return False


def set_windows_autostart(enable: bool) -> bool:
    """
    Registers or unregisters CoachingHelper in Windows Registry Run key
    HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.
    """
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            WINDOWS_AUTOSTART_REG_KEY,
            0,
            winreg.KEY_SET_VALUE,
        )
        if enable:
            if getattr(sys, "frozen", False):
                exe_path = Path(sys.executable).parent / "CoachingHelper.exe"
                cmd = f'"{exe_path}"'
            else:
                main_script = Path(__file__).resolve().parent.parent.parent / "coaching_helper_main.py"
                pythonw = Path(sys.executable).parent / "pythonw.exe"
                py_exec = pythonw if pythonw.exists() else Path(sys.executable)
                cmd = f'"{py_exec}" "{main_script}"'

            winreg.SetValueEx(
                key,
                WINDOWS_AUTOSTART_APP_NAME,
                0,
                winreg.REG_SZ,
                cmd,
            )
            logger.info("Windows autostart registered: %s", cmd)
        else:
            try:
                winreg.DeleteValue(key, WINDOWS_AUTOSTART_APP_NAME)
                logger.info("Windows autostart unregistered.")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error("Failed to update Windows autostart: %s", e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 6. PROCESS SUPERVISION (START, STOP, RESTART, TRIGGER)
# ─────────────────────────────────────────────────────────────────────────────

def get_helper_process_info() -> dict[str, Any]:
    """
    Returns comprehensive diagnostic information about the background helper process.
    """
    running = is_helper_process_running()
    status = read_helper_status() or {}
    lock_pid = SingleInstanceLock()._read_locked_pid()

    return {
        "running": running,
        "pid": status.get("pid") or lock_pid,
        "state": status.get("state", "STOPPED" if not running else "RUNNING"),
        "heartbeat_at": status.get("heartbeat_at"),
        "is_online": status.get("is_online", True),
        "is_paused": status.get("is_paused", False),
        "worker_id": status.get("worker_id"),
        "last_cycle_summary": status.get("last_cycle_summary", {}),
        "queue_stats": status.get("queue_stats", {}),
        "last_backup_time": status.get("last_backup_time"),
        "version": status.get("version", APP_VERSION),
        "windows_autostart": is_windows_autostart_enabled(),
    }


def start_helper_process(headless: bool = False) -> bool:
    """
    Launches the CoachingHelper companion background process.
    Ensures safe detached execution so it continues running independently of TAMS.
    """
    if is_helper_process_running():
        logger.info("CoachingHelper is already running.")
        return True

    try:
        # Determine launch command
        if getattr(sys, "frozen", False):
            # Bundled executable
            helper_exe = Path(sys.executable).parent / "CoachingHelper.exe"
            if not helper_exe.exists():
                helper_exe = Path(sys.executable)
            cmd = [str(helper_exe)]
            if headless:
                cmd.append("--headless")
        else:
            # Running from source
            root_dir = Path(__file__).resolve().parent.parent.parent
            script_path = root_dir / "coaching_helper_main.py"
            cmd = [sys.executable, str(script_path)]
            if headless:
                cmd.append("--headless")

        # Spawn detached process
        if sys.platform == "win32":
            # DETACHED_PROCESS = 0x00000008, CREATE_NEW_PROCESS_GROUP = 0x00000200
            creationflags = 0x00000008 | 0x00000200
            if headless:
                creationflags |= 0x08000000  # CREATE_NO_WINDOW
            subprocess.Popen(
                cmd,
                creationflags=creationflags,
                close_fds=True,
            )
        else:
            subprocess.Popen(
                cmd,
                start_new_session=True,
                close_fds=True,
            )

        logger.info("Launched CoachingHelper process: %s", cmd)
        return True
    except Exception as e:
        logger.error("Failed to start CoachingHelper process: %s", e)
        return False


def stop_helper_process(timeout_seconds: float = 4.0) -> bool:
    """
    Gracefully stops the CoachingHelper process via IPC command.
    If the process does not terminate within the timeout, terminates it forcefully.
    """
    if not is_helper_process_running():
        # Clear any stale status or lock file
        HELPER_LOCK_FILE.unlink(missing_ok=True)
        return True

    send_helper_ipc_command("STOP")

    # Wait for graceful exit
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        if not is_helper_process_running():
            logger.info("CoachingHelper stopped gracefully.")
            return True
        time.sleep(0.3)

    # Force kill if still unresponsive
    info = get_helper_process_info()
    pid = info.get("pid")
    if pid and is_pid_alive(pid):
        logger.warning("CoachingHelper unresponsive. Force-killing PID %d", pid)
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.5)
                if is_pid_alive(pid):
                    os.kill(pid, signal.SIGKILL)
        except Exception as e:
            logger.error("Error killing PID %d: %s", pid, e)

    HELPER_LOCK_FILE.unlink(missing_ok=True)
    return True


def restart_helper_process() -> bool:
    """Restarts the CoachingHelper process."""
    stop_helper_process(timeout_seconds=3.0)
    time.sleep(0.5)
    return start_helper_process()


def trigger_helper_queue_cycle() -> bool:
    """Signals the running helper process to execute an immediate queue processing cycle."""
    return send_helper_ipc_command("RUN_CYCLE")


# ─────────────────────────────────────────────────────────────────────────────
# 7. BACKGROUND WORKER ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class CoachingHelperEngine:
    """
    Core execution engine for CoachingHelper companion background runner.
    Handles queue cycles, connectivity pauses, daily backups, IPC commands, and clean shutdown.
    """

    def __init__(
        self,
        worker_id: str | None = None,
        poll_interval: int = 15,
        backup_interval_hours: int = 24,
    ):
        self.worker_id = worker_id or f"Helper_{socket.gethostname()}_{uuid.uuid4().hex[:6]}"
        self.poll_interval = poll_interval
        self.backup_interval_hours = backup_interval_hours
        self.is_running = False
        self.is_paused = False
        self.last_backup_time: datetime | None = None
        self.last_online_status = True
        self.lock = SingleInstanceLock()

    def start(self) -> bool:
        """Acquires lock and initializes helper service."""
        setup_helper_logging()
        if not self.lock.acquire():
            logger.warning("Another CoachingHelper process is already running. Exiting.")
            return False

        self.is_running = True
        self.is_paused = False
        logger.info("CoachingHelperEngine started with worker ID: %s", self.worker_id)
        self._update_status("RUNNING", "Started successfully")
        return True

    def stop(self):
        """Signals engine to stop gracefully and releases lock."""
        self.is_running = False
        self._update_status("STOPPED", "Shutdown requested")
        self.lock.release()
        logger.info("CoachingHelperEngine stopped cleanly.")

    def pause(self):
        self.is_paused = True
        self._update_status("PAUSED", "Background queue processing paused by user")

    def resume(self):
        self.is_paused = False
        self._update_status("RUNNING", "Resumed queue processing")

    def check_and_handle_ipc_commands(self) -> str | None:
        """Checks for external IPC commands from TAMS and applies them."""
        cmd = read_and_clear_helper_ipc_command()
        if not cmd:
            return None

        logger.info("Received IPC command: %s", cmd)
        if cmd == "STOP":
            self.stop()
        elif cmd == "PAUSE":
            self.pause()
        elif cmd == "RESUME":
            self.resume()
        elif cmd == "RUN_CYCLE":
            self.run_single_cycle()
        return cmd

    def run_single_cycle(self) -> dict[str, Any]:
        """
        Executes a single processing cycle:
        1. Checks network connectivity
        2. Processes queued messages (if online & not paused)
        3. Checks if automated backup is due
        4. Writes health status file
        """
        online = check_internet_connectivity(timeout=2.5)
        if online != self.last_online_status:
            self.last_online_status = online
            logger.info("Network connectivity status changed: online=%s", online)

        summary = {"processed": 0, "accepted": 0, "failed": 0, "retried": 0}

        if self.is_paused:
            self._update_status("PAUSED", "Queue paused", online=online)
            return {"status": "PAUSED", "summary": summary}

        if not online:
            self._update_status("OFFLINE", "Computer offline; queue paused without failing messages", online=False)
            return {"status": "OFFLINE", "summary": summary}

        # Process queue
        try:
            with SessionLocal() as session:
                summary = process_message_queue(
                    session,
                    worker_id=self.worker_id,
                    batch_limit=10,
                )
        except Exception as e:
            logger.error("Queue processing error: %s", e)
            self._update_status("ERROR", f"Queue cycle error: {type(e).__name__}", online=online)
            return {"status": "ERROR", "error": str(e)}

        # Automated backup check
        self._check_and_run_automated_backup()

        self._update_status("RUNNING", "Operational", online=True, last_summary=summary)
        return {"status": "RUNNING", "summary": summary}

    def _check_and_run_automated_backup(self):
        """Runs daily automated backup if 24 hours have elapsed."""
        now = datetime.now(timezone.utc)
        if self.last_backup_time is None:
            existing = list_backups()
            if existing:
                try:
                    self.last_backup_time = datetime.fromtimestamp(existing[0]["timestamp_epoch"], tz=timezone.utc)
                except Exception:
                    self.last_backup_time = now
            else:
                self.last_backup_time = datetime(2000, 1, 1, tzinfo=timezone.utc)

        hours_since = (now - self.last_backup_time).total_seconds() / 3600.0
        if hours_since >= self.backup_interval_hours:
            try:
                res = create_database_backup(custom_label="automated_helper", max_retention=10)
                if res["success"]:
                    self.last_backup_time = now
                    logger.info("Automated backup completed: %s", res.get("backup_filename"))
            except Exception as e:
                logger.error("Automated backup failed: %s", e)

    def _update_status(
        self,
        state: str,
        message: str,
        online: bool = True,
        last_summary: dict[str, Any] | None = None,
    ):
        """Updates helper_status.json."""
        stats = {}
        try:
            with SessionLocal() as session:
                stats = get_messaging_overview_stats(session)
        except Exception:
            pass

        data = {
            "state": state,
            "message": message,
            "worker_id": self.worker_id,
            "pid": os.getpid(),
            "heartbeat_at": datetime.now(timezone.utc).isoformat(),
            "is_online": online,
            "is_paused": self.is_paused,
            "last_cycle_summary": last_summary or {},
            "queue_stats": stats,
            "last_backup_time": self.last_backup_time.isoformat() if self.last_backup_time else None,
            "version": APP_VERSION,
        }
        write_helper_status(data)

    def run_loop(self):
        """Main blocking runner loop for headless/background execution."""
        logger.info("Entering CoachingHelper background loop (interval: %ds)...", self.poll_interval)
        while self.is_running:
            self.check_and_handle_ipc_commands()
            if not self.is_running:
                break

            self.run_single_cycle()

            # Sleep in 500ms increments for responsive stop() & IPC commands
            for _ in range(int(self.poll_interval * 2)):
                if not self.is_running:
                    break
                self.check_and_handle_ipc_commands()
                time.sleep(0.5)
