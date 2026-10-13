"""
CoachingHelper Qt Controller and Process Supervisor for TAMS.
Monitors the companion background service, synchronizes status with the TAMS UI,
handles process startup/shutdown, and dispatches IPC commands.
Prevents duplicate competing queue workers while keeping UI fully responsive.
"""

from __future__ import annotations

import logging
import os
import socket
import time
import uuid
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.database.connection import SessionLocal
from app.services.coaching_helper_service import (
    get_helper_process_info,
    is_helper_process_running,
    read_helper_status,
    restart_helper_process,
    start_helper_process,
    stop_helper_process,
    trigger_helper_queue_cycle,
)
from app.services.messaging_service import (
    get_messaging_config,
    process_message_queue,
)

logger = logging.getLogger("TAMS.CoachingHelper")


class CoachingHelper(QThread):
    """
    Qt Controller and Supervisor thread for CoachingHelper.
    Supervises the companion process, monitors health status,
    and provides fallback/on-demand queue execution when standalone process is offline.
    """
    queue_processed = pyqtSignal(dict)  # Emits processing summary dict
    status_changed = pyqtSignal(str)     # Emits status message

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._running = False
        self._check_interval_seconds = 5
        self._last_heartbeat: str | None = None
        self._last_processed_count: int = 0
        self.worker_id = f"TAMSController_{socket.gethostname()}_{uuid.uuid4().hex[:6]}"

    def run(self):
        """
        Background monitoring loop.
        Checks companion process health. If companion is not running and autostart
        is enabled, attempts to spawn it.
        """
        self._running = True
        logger.info("CoachingHelper supervisor started.")
        self.status_changed.emit("Supervisor Active")

        # Initial launch check: if configured, ensure companion process is running
        try:
            with SessionLocal() as session:
                cfg = get_messaging_config(session)
                autostart = cfg.get("helper_autostart_with_tams", "true").lower() == "true"
                if autostart and not is_helper_process_running() and not os.environ.get("PYTEST_CURRENT_TEST"):
                    start_helper_process(headless=False)
        except Exception as e:
            logger.debug("Initial helper autostart check skipped: %s", e)

        while self._running:
            try:
                info = get_helper_process_info()
                is_running = info.get("running", False)

                if is_running:
                    state = info.get("state", "RUNNING")
                    self.status_changed.emit(f"Companion Active ({state})")
                    summary = info.get("last_cycle_summary", {})
                    if summary and summary.get("processed", 0) > self._last_processed_count:
                        self._last_processed_count = summary.get("processed", 0)
                        self.queue_processed.emit(summary)
                else:
                    self.status_changed.emit("Companion Inactive (On-Demand Mode)")

            except Exception as e:
                logger.debug("CoachingHelper monitor cycle error: %s", e)

            # Sleep in small increments for responsive stop()
            for _ in range(int(self._check_interval_seconds * 2)):
                if not self._running:
                    break
                self.msleep(500)

        logger.info("CoachingHelper supervisor stopped.")
        self.status_changed.emit("Supervisor Stopped")

    def stop(self):
        """Signals supervisor thread to stop gracefully."""
        self._running = False
        self.wait(3000)

    def is_running(self) -> bool:
        """Returns True if the supervisor thread or companion process is active."""
        return self._running or is_helper_process_running()

    def trigger_immediate_run(self) -> dict[str, Any]:
        """
        Forces an immediate queue cycle.
        If companion process is active, signals it via IPC.
        If companion process is inactive, runs one cycle directly in fallback mode.
        """
        if is_helper_process_running():
            trigger_helper_queue_cycle()
            return {"status": "TRIGGERED_VIA_IPC"}

        # Fallback direct execution when companion is offline
        try:
            with SessionLocal() as session:
                summary = process_message_queue(
                    session,
                    worker_id=self.worker_id,
                    batch_limit=10,
                )
                if summary.get("processed", 0) > 0:
                    self.queue_processed.emit(summary)
                return summary
        except Exception as e:
            logger.error("Direct queue execution error: %s", e)
            return {"error": str(e)}

    def restart_companion(self) -> bool:
        """Restarts the standalone companion process."""
        return restart_helper_process()
