"""
TAMS Database Engine & Connection Infrastructure.

Manages the SQLite database path across Windows, macOS, and Linux, ensuring data
is isolated in user-standard application directories. Configures SQLite for safe
multi-process concurrency (TAMS desktop app + CoachingHelper background companion)
using Write-Ahead Logging (WAL), foreign keys, and busy timeouts.
"""

from pathlib import Path
import os
import sys

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


# Keep application data separate from source code, cross-platform.
def _resolve_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        target = Path(base) / "TAMS" if base else Path.home() / "AppData" / "Roaming" / "TAMS"
    elif sys.platform == "darwin":
        target = Path.home() / "Library" / "Application Support" / "TAMS"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        target = Path(xdg) / "TAMS" if xdg else Path.home() / ".local" / "share" / "TAMS"
    target.mkdir(parents=True, exist_ok=True)
    return target

DATA_DIR = Path(os.environ["TAMS_DATA_DIR"]) if "TAMS_DATA_DIR" in os.environ else _resolve_data_dir()

DATABASE_PATH = Path(os.environ["TAMS_DATABASE_PATH"]) if "TAMS_DATABASE_PATH" in os.environ else (DATA_DIR / "tams.db")

DATABASE_URL = os.environ.get("TAMS_DATABASE_URL", f"sqlite:///{DATABASE_PATH}")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"timeout": 30.0},
)


# SQLite multi-process configuration for TAMS and CoachingHelper:
# 1. Foreign keys enabled for relational integrity.
# 2. Write-Ahead Logging (WAL) for concurrent read/write across processes.
# 3. Busy timeout (30 seconds) to prevent 'database is locked' errors.
@event.listens_for(engine, "connect")
def configure_sqlite_connection(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)