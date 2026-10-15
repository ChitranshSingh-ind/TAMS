import os
import sys
import tempfile
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication

# Setup temporary test isolation directory before any module imports app.database.connection
_TEST_TEMP_DIR = tempfile.TemporaryDirectory()
_TEMP_DATA_DIR = Path(_TEST_TEMP_DIR.name)
_TEMP_DB_PATH = _TEMP_DATA_DIR / "test_tams.db"
_TEMP_DB_URL = f"sqlite:///{_TEMP_DB_PATH}"

os.environ["TAMS_DATA_DIR"] = str(_TEMP_DATA_DIR)
os.environ["TAMS_DATABASE_PATH"] = str(_TEMP_DB_PATH)
os.environ["TAMS_DATABASE_URL"] = _TEMP_DB_URL
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTEST_CURRENT_TEST"] = "1"


@pytest.fixture(scope="session", autouse=True)
def isolate_test_database():
    """
    Session-wide fixture that builds the schema on the isolated test SQLite database
    and seeds essential initial data.
    """
    import app.database.connection as conn
    conn.DATA_DIR = _TEMP_DATA_DIR
    conn.DATABASE_PATH = _TEMP_DB_PATH
    conn.DATABASE_URL = _TEMP_DB_URL

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    new_engine = create_engine(
        _TEMP_DB_URL,
        echo=False,
        connect_args={"timeout": 30.0},
    )
    conn.engine = new_engine
    conn._session_factory = sessionmaker(bind=new_engine, autoflush=False, autocommit=False)

    # Create all tables on the isolated database
    from app.database.base import Base
    import app.database.models.batch
    import app.database.models.parent
    import app.database.models.student
    import app.database.models.fee
    import app.database.models.test
    import app.database.models.lesson
    import app.database.models.expense
    import app.database.models.attendance
    import app.database.models.message

    Base.metadata.create_all(bind=new_engine)

    # Seed essential config data
    from app.services.messaging_service import ensure_messaging_seed_data
    with conn.SessionLocal() as session:
        ensure_messaging_seed_data(session)

    yield

    new_engine.dispose()
    try:
        _TEST_TEMP_DIR.cleanup()
    except Exception:
        pass


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app
