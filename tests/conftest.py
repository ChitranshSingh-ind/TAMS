import os
import tempfile
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication
import sys

# Ensure Qt offscreen platform is set before any GUI imports
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTEST_CURRENT_TEST"] = "1"

@pytest.fixture(scope="session", autouse=True)
def isolate_test_database():
    """
    Session-wide fixture that creates a temporary isolated SQLite database
    and configures TAMS to use it, preventing any modification or pollution
    of the user's authentic database file (~/.local/share/TAMS/tams.db).
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_data_dir = Path(temp_dir)
        temp_db_path = temp_data_dir / "test_tams.db"
        temp_db_url = f"sqlite:///{temp_db_path}"

        os.environ["TAMS_DATA_DIR"] = str(temp_data_dir)
        os.environ["TAMS_DATABASE_PATH"] = str(temp_db_path)
        os.environ["TAMS_DATABASE_URL"] = temp_db_url

        # Now import connection and models to build schema on the isolated DB
        import app.database.connection as conn
        conn.DATA_DIR = temp_data_dir
        conn.DATABASE_PATH = temp_db_path
        conn.DATABASE_URL = temp_db_url

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        new_engine = create_engine(
            temp_db_url,
            echo=False,
            connect_args={"timeout": 30.0},
        )
        conn.engine = new_engine
        conn._session_factory = sessionmaker(bind=new_engine, autoflush=False, autocommit=False)

        # Create all tables on the isolated database
        from app.database.base import Base
        # Ensure all models are registered
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


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app
