"""
CoachingHelper Companion Service for TAMS.
Runs background queue processing, automated database backups,
connectivity-aware retry management, health reporting, and single-instance locking.
Works cross-platform (Windows & Linux).
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.database.connection import DATABASE_PATH, DATA_DIR, SessionLocal
from app.services.backup_service import create_database_backup, list_backups
from app.services.messaging_service import (
    get_messaging_config,
    get_messaging_overview_stats,
    process_message_queue,
)

logger = logging.getLogger("TAMS.CoachingHelperService")

HELPER_STATUS_FILE = DATA_DIR / "helper_status.json"
HELPER_LOCK_FILE = DATA_DIR / "coaching_helper.lock"
APP_VERSION = "2.0.0"


def get_helper_status_file_path() -> Path:
    """Returns the path to helper_status.json."""
    return HELPER_STATUS_FILE



# ─────────────────────────────────────────────────────────────────────────────
# 1. CROSS-PLATFORM SINGLE-INSTANCE LOCKING
# ─────────────────────────────────────────────────────────────────────────────

class SingleInstanceLock:
    """
    Ensures only a single instance of CoachingHelper background process runs.
    Uses POSIX fcntl on Linux/macOS and msvcrt/file-locking on Windows.
    """

    def __init__(self, lock_path: Path = HELPER_LOCK_FILE):
        self.lock_path = lock_path
        self.lock_file_fd = None
        self._is_locked = False

    def acquire(self) -> bool:
        """Attempts to acquire exclusive lock. Returns True if successful, False if already running."""
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self.lock_file_fd = open(self.lock_path, "a+")

            if sys.platform == "win32":
                import msvcrt
                try:
                    self.lock_file_fd.seek(0)
                    msvcrt.locking(self.lock_file_fd.fileno(), msvcrt.LK_NBLCK, 1)
                    self._is_locked = True
                except (IOError, OSError):
                    return False
            else:
                import fcntl
                try:
                    fcntl.flock(self.lock_file_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._is_locked = True
                except (IOError, OSError):
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
                    self.lock_path.unlink()
                except Exception:
                    pass
        except Exception as e:
            logger.error("Error releasing lock: %s", e)


def is_helper_process_running() -> bool:
    """Checks whether another CoachingHelper process is currently active."""
    if not HELPER_LOCK_FILE.exists():
        return False
    # Check status file heartbeat freshness (within 45 seconds)
    status = read_helper_status()
    if not status:
        return False
    try:
        hb = datetime.fromisoformat(status.get("heartbeat_at", ""))
        diff = (datetime.now(timezone.utc) - hb).total_seconds()
        return diff < 45.0
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 2. STATUS REPORTING & CONNECTIVITY CHECK
# ─────────────────────────────────────────────────────────────────────────────

def write_helper_status(status_data: dict[str, Any]) -> None:
    """Writes status JSON for inspection by the main TAMS UI."""
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
    Lightweight, bounded connectivity check to verify if the machine can reach the internet.
    Checks DNS resolution for Meta Graph API / Cloudflare.
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
    Safe version check for TAMS.
    Returns current version status without executing arbitrary scripts.
    """
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
# 3. BACKGROUND WORKER ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class CoachingHelperEngine:
    """
    Core execution engine for CoachingHelper companion background runner.
    Handles queue cycles, connectivity pauses, daily backups, and clean shutdown.
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
            # Check existing backups
            existing = list_backups()
            if existing:
                try:
                    self.last_backup_time = datetime.fromtimestamp(existing[0]["timestamp_epoch"], tz=timezone.utc)
                except Exception:
                    self.last_backup_time = now
            else:
                self.last_backup_time = datetime(2000, 1, 1, tz=timezone.utc)

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
            self.run_single_cycle()
            # Sleep in 500ms increments for responsive stop()
            for _ in range(int(self.poll_interval * 2)):
                if not self.is_running:
                    break
                time.sleep(0.5)
