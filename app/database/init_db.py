"""
Database Initialization and Migration Runner for TAMS.
Ensures that all tables, columns, indexes, and initial seed configurations
exist whenever TAMS or CoachingHelper starts up on any machine.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger("TAMS.DatabaseInit")


def init_database() -> None:
    """
    Ensures all database tables and initial seeds exist.
    Completely idempotent: safe to call on every application startup.
    """
    from app.database.connection import engine, SessionLocal
    from app.database.base import Base

    # Import all SQLAlchemy models so Base.metadata is fully populated
    import app.database.models.batch
    import app.database.models.parent
    import app.database.models.student
    import app.database.models.fee
    import app.database.models.test
    import app.database.models.lesson
    import app.database.models.expense
    import app.database.models.attendance
    import app.database.models.message

    logger.info("Initializing database tables and schema...")
    Base.metadata.create_all(bind=engine)

    # Run Alembic migrations if alembic is present to bring schema to head
    try:
        from alembic.config import Config
        from alembic import command

        base = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parent.parent.parent
        ini_path = base / "alembic.ini"
        if ini_path.exists():
            cfg = Config(str(ini_path))
            cfg.set_main_option("script_location", str(base / "migrations"))
            command.upgrade(cfg, "head")
    except Exception as e:
        logger.debug("Alembic upgrade note: %s", e)

    # Seed essential configuration and default templates if needed
    try:
        from app.services.messaging_service import ensure_messaging_seed_data
        with SessionLocal() as session:
            ensure_messaging_seed_data(session)
    except Exception as e:
        logger.warning("Could not seed messaging data: %s", e)
