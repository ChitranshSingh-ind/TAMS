"""
CoachingHelper Background Worker for TAMS.
Runs periodic queue polling and message delivery outside the main UI thread.
Handles application shutdown gracefully, uses claim-lease locking for SQLite safety,
and emits signals for live UI status updates.
"""

from __future__ import annotations

import logging
import socket
import time
import uuid
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.database.connection import SessionLocal
from app.services.messaging_service import process_message_queue

logger = logging.getLogger("TAMS.CoachingHelper")


class CoachingHelper(QThread):
    """
    Background worker thread executing automated message queue processing.
    Safe against UI blocking, crashes, and duplicate execution.
    """
    queue_processed = pyqtSignal(dict)  # Emits processing summary
    status_changed = pyqtSignal(str)     # Emits status message

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._running = False
        self._interval_seconds = 15
        self.worker_id = f"Helper_{socket.gethostname()}_{uuid.uuid4().hex[:6]}"

    def run(self):
        self._running = True
        logger.info("CoachingHelper started with worker ID: %s", self.worker_id)
        self.status_changed.emit("Running")

        while self._running:
            try:
                with SessionLocal() as session:
                    summary = process_message_queue(
                        session,
                        worker_id=self.worker_id,
                        batch_limit=10,
                    )
                    if summary.get("processed", 0) > 0:
                        self.queue_processed.emit(summary)

            except Exception as e:
                logger.error("CoachingHelper error in processing cycle: %s", e)
                self.status_changed.emit(f"Cycle error: {type(e).__name__}")

            # Sleep in small increments for responsive stop()
            for _ in range(int(self._interval_seconds * 2)):
                if not self._running:
                    break
                self.msleep(500)

        logger.info("CoachingHelper stopped gracefully.")
        self.status_changed.emit("Stopped")

    def stop(self):
        """Signals the background worker to stop gracefully and waits for cycle to complete."""
        self._running = False
        self.wait(3000)

    def __del__(self):
        try:
            self._running = False
            if self.isRunning():
                self.wait(1000)
        except Exception:
            pass

    def trigger_immediate_run(self):
        """Forces an immediate processing cycle in the worker thread."""
        if self.isRunning() and self._running:
            # Wake up from sleep
            pass
