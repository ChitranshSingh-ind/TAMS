"""
Database Backup & Maintenance Service for TAMS.
Provides safe, transaction-consistent SQLite online backups,
integrity validation, retention management, and recovery.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.database.connection import DATABASE_PATH, DATA_DIR

logger = logging.getLogger("TAMS.BackupService")


def get_database_path() -> Path:
    """Returns the path to the active database file, respecting environment overrides."""
    import os
    import app.database.connection as conn
    if "TAMS_DATABASE_PATH" in os.environ:
        return Path(os.environ["TAMS_DATABASE_PATH"])
    return Path(conn.DATABASE_PATH)


def get_backup_directory() -> Path:
    """Returns the directory where database backups are stored, ensuring it exists."""
    import os
    import app.database.connection as conn
    base_dir = Path(os.environ.get("TAMS_DATA_DIR", conn.DATA_DIR))
    backup_dir = base_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def create_database_backup(
    *,
    custom_label: str | None = None,
    max_retention: int | None = None,
) -> dict[str, Any]:
    """
    Creates a transaction-consistent SQLite online backup using SQLite's backup API.
    Safe to run while TAMS is actively running.
    Validates backup integrity with PRAGMA quick_check.
    Enforces backup retention policy (retains latest `max_retention` backups).
    """
    backup_dir = get_backup_directory()
    db_path = get_database_path()

    if max_retention is None:
        try:
            from app.database.connection import SessionLocal
            from app.services.messaging_service import get_messaging_config
            with SessionLocal() as session:
                cfg = get_messaging_config(session)
                max_retention = int(cfg.get("max_backup_retention", "10"))
        except Exception:
            max_retention = 10

    if not db_path.exists():
        return {
            "success": False,
            "error": f"Database file not found at {db_path}",
            "backup_path": None,
        }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label_suffix = f"_{custom_label.strip()}" if custom_label else ""
    backup_filename = f"tams_backup_{timestamp}{label_suffix}.db"
    backup_target = backup_dir / backup_filename

    source_conn = None
    backup_conn = None
    try:
        source_conn = sqlite3.connect(str(db_path), timeout=30.0)
        backup_conn = sqlite3.connect(str(backup_target), timeout=30.0)

        # Execute safe online backup using native SQLite backup API
        source_conn.backup(backup_conn, pages=100)
        backup_conn.commit()

        # Validate backup file integrity
        cursor = backup_conn.cursor()
        cursor.execute("PRAGMA quick_check")
        check_result = cursor.fetchone()
        if not check_result or check_result[0] != "ok":
            backup_conn.close()
            if backup_target.exists():
                backup_target.unlink()
            return {
                "success": False,
                "error": f"Integrity check failed: {check_result[0] if check_result else 'unknown error'}",
                "backup_path": None,
            }

        backup_conn.close()
        source_conn.close()

        file_size_bytes = backup_target.stat().st_size

        # Apply retention cleanup
        pruned_count = enforce_backup_retention(max_retention=max_retention)

        logger.info(
            "Created database backup: %s (%d bytes). Pruned %d older backups.",
            backup_target.name,
            file_size_bytes,
            pruned_count,
        )

        return {
            "success": True,
            "backup_filename": backup_filename,
            "backup_path": str(backup_target),
            "size_bytes": file_size_bytes,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "pruned_backups": pruned_count,
            "error": None,
        }

    except Exception as e:
        logger.error("Failed to create database backup: %s", e)
        if backup_conn:
            try:
                backup_conn.close()
            except Exception:
                pass
        if source_conn:
            try:
                source_conn.close()
            except Exception:
                pass
        if backup_target.exists():
            try:
                backup_target.unlink()
            except Exception:
                pass
        return {
            "success": False,
            "error": str(e),
            "backup_path": None,
        }


def list_backups() -> list[dict[str, Any]]:
    """Lists all available backup files sorted by creation date descending."""
    backup_dir = get_backup_directory()
    backups = []

    for file in backup_dir.glob("tams_backup_*.db"):
        if file.is_file():
            stat = file.stat()
            size_fmt = f"{stat.st_size / (1024 * 1024):.2f} MB" if stat.st_size >= 1024 * 1024 else f"{stat.st_size / 1024:.1f} KB"
            date_fmt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%d %b %Y %H:%M:%S UTC")
            backups.append({
                "filename": file.name,
                "path": str(file),
                "size_bytes": stat.st_size,
                "size_display": size_fmt,
                "size_formatted": size_fmt,
                "modified_at": date_fmt,
                "created_iso": date_fmt,
                "timestamp_epoch": stat.st_mtime,
            })


    # Sort descending by file modification timestamp
    backups.sort(key=lambda b: b["timestamp_epoch"], reverse=True)
    return backups


def enforce_backup_retention(max_retention: int = 10) -> int:
    """Removes older backups when total count exceeds `max_retention`. Returns count of pruned files."""
    if max_retention <= 0:
        return 0

    backups = list_backups()
    if len(backups) <= max_retention:
        return 0

    to_prune = backups[max_retention:]
    pruned = 0
    for b in to_prune:
        p = Path(b["path"])
        try:
            p.unlink()
            pruned += 1
        except Exception as e:
            logger.warning("Could not delete old backup %s: %s", p.name, e)

    return pruned


def restore_database_backup(backup_path: str | Path) -> dict[str, Any]:
    """
    Restores the database from a verified backup file.
    Always creates a pre-restore safety snapshot of the current database before replacing it.
    """
    backup_file = Path(backup_path)
    db_path = get_database_path()

    if not backup_file.exists():
        return {"success": False, "error": f"Backup file not found: {backup_file}"}

    # Verify backup integrity first
    try:
        test_conn = sqlite3.connect(str(backup_file))
        cursor = test_conn.cursor()
        cursor.execute("PRAGMA quick_check")
        res = cursor.fetchone()
        test_conn.close()
        if not res or res[0] != "ok":
            return {"success": False, "error": "Selected backup file failed integrity check"}
    except Exception as e:
        return {"success": False, "error": f"Could not verify backup file: {e}"}

    # Create safety snapshot of current database
    safety_res = create_database_backup(custom_label="pre_restore_safety")
    if not safety_res["success"] and db_path.exists():
        logger.warning("Pre-restore safety snapshot could not be created: %s", safety_res["error"])

    helper_was_running = False
    try:
        from app.services.coaching_helper_service import (
            is_helper_process_running,
            start_helper_process,
            stop_helper_process,
        )
        if is_helper_process_running():
            helper_was_running = True
            logger.info("CoachingHelper is active; stopping it before database restore...")
            stop_helper_process(timeout_seconds=3.0)
    except Exception as e:
        logger.debug("CoachingHelper pre-restore check note: %s", e)

    try:
        # Close any active pooled SQLAlchemy connections before file replacement
        try:
            from app.database.connection import engine
            engine.dispose()
        except Exception:
            pass

        # Atomic file copy
        temp_dest = db_path.with_suffix(".tmp_restore")
        shutil.copy2(backup_file, temp_dest)
        if db_path.exists():
            db_path.unlink()
        temp_dest.rename(db_path)

        # Remove stale WAL/SHM files if present
        for extra in [db_path.with_suffix(".db-wal"), db_path.with_suffix(".db-shm"), Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")]:
            if extra.exists():
                try:
                    extra.unlink()
                except Exception:
                    pass

        try:
            from app.database.connection import engine
            engine.dispose()
        except Exception:
            pass

        logger.info("Database successfully restored from backup: %s", backup_file.name)

        return {
            "success": True,
            "error": None,
            "safety_snapshot_path": safety_res.get("backup_path"),
        }
    except Exception as e:
        logger.error("Failed restoring database from backup: %s", e)
        return {"success": False, "error": str(e), "safety_snapshot_path": None}
    finally:
        if helper_was_running:
            try:
                from app.services.coaching_helper_service import start_helper_process
                logger.info("Restarting CoachingHelper companion after database restore...")
                start_helper_process(headless=True)
            except Exception as e:
                logger.warning("Could not restart CoachingHelper after restore: %s", e)

