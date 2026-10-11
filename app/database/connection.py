from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


import os
import sys

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

DATA_DIR = _resolve_data_dir()

DATABASE_PATH = DATA_DIR / "tams.db"

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
)


# SQLite foreign keys are disabled by default.
# TAMS needs them enabled for data integrity.
@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)