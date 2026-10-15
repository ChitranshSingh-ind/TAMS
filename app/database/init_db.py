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

    # Run Alembic migrations or stamp head if fresh installation
    try:
        from alembic.config import Config
        from alembic import command
        from sqlalchemy import inspect, text

        base = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parent.parent.parent
        ini_path = base / "alembic.ini"
        if ini_path.exists():
            cfg = Config(str(ini_path))
            cfg.set_main_option("script_location", str(base / "migrations"))

            has_revision = False
            with engine.connect() as conn:
                inspector = inspect(conn)
                if "alembic_version" in inspector.get_table_names():
                    res = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
                    has_revision = bool(res)

            if not has_revision:
                logger.info("Database newly created; stamping alembic_version directly to head...")
                command.stamp(cfg, "head")
            else:
                logger.info("Upgrading database schema to head...")
                command.upgrade(cfg, "head")
    except Exception as e:
        logger.debug("Alembic initialization note: %s", e)

    # Seed essential configuration and default templates if needed
    try:
        from app.services.messaging_service import ensure_messaging_seed_data
        with SessionLocal() as session:
            ensure_messaging_seed_data(session)
    except Exception as e:
        logger.warning("Could not seed messaging data: %s", e)
