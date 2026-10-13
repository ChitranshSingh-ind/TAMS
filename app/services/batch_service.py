
"""
TAMS Batch Management Service.

This service encapsulates all business logic and database interactions for student
batches, including creating new batches, retrieving active batches for selectors,
modifying batch schedules/timings, and archiving (deactivating/reactivating) batches.
"""

from datetime import time
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.batch import Batch


def create_batch(
    session: Session,
    name: str,
    start_time: time | None = None,
    end_time: time | None = None,
    days: str | None = None,
) -> Batch:
    """
    Creates and persists a new coaching batch.

    Args:
        session: Active SQLAlchemy database session.
        name: Unique, human-readable name for the batch (e.g. 'Class 10 Science').
        start_time: Optional scheduled start time of classes.
        end_time: Optional scheduled end time of classes.
        days: Comma-separated scheduled days (e.g. 'Mon,Wed,Fri').

    Returns:
        The newly created, persisted Batch instance with its assigned primary key.
    """
    # Instantiate the Batch model entity with sanitized name
    batch = Batch(
        name=name.strip(),
        start_time=start_time,
        end_time=end_time,
        days=days,
    )

    # Persist the new batch to the database
    session.add(batch)
    session.commit()
    session.refresh(batch)

    return batch


def get_batch(session: Session, batch_id: int) -> Batch | None:
    """
    Retrieves a single batch by its primary key ID.

    Args:
        session: Active SQLAlchemy database session.
        batch_id: The primary key ID of the batch.

    Returns:
        The Batch object if found, otherwise None.
    """
    return session.get(Batch, batch_id)


def get_active_batches(session: Session) -> list[Batch]:
    """
    Queries all currently active batches, ordered alphabetically by name.
    Used across UI dropdown selectors (main toolbar, student dialog, fee filters).

    Args:
        session: Active SQLAlchemy database session.

    Returns:
        A list of active Batch instances.
    """
    statement = (
        select(Batch)
        .where(Batch.active.is_(True))
        .order_by(Batch.name)
    )

    return list(session.scalars(statement).all())


def update_batch(
    session: Session,
    batch_id: int,
    *,
    name: str | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    days: str | None = None,
    active: bool | None = None,
) -> Batch | None:
    """
    Updates configuration attributes of an existing batch.

    Args:
        session: Active SQLAlchemy database session.
        batch_id: ID of the batch to update.
        name: Optional updated batch name.
        start_time: Optional updated start time.
        end_time: Optional updated end time.
        days: Optional updated days string.
        active: Optional updated active status flag.

    Returns:
        The updated Batch object, or None if the batch doesn't exist.
    """
    batch = session.get(Batch, batch_id)

    if batch is None:
        return None

    # Apply provided non-None field updates
    if name is not None:
        batch.name = name.strip()

    if start_time is not None:
        batch.start_time = start_time

    if end_time is not None:
        batch.end_time = end_time

    if days is not None:
        batch.days = days

    if active is not None:
        batch.active = active

    # Save changes and refresh the entity state
    session.commit()
    session.refresh(batch)

    return batch


def deactivate_batch(session: Session, batch_id: int) -> Batch | None:
    """
    Soft-deactivates an active batch so it no longer appears in default active selectors,
    while preserving historical student enrollments, attendance, and fee ledgers.

    Args:
        session: Active SQLAlchemy database session.
        batch_id: Primary key of the batch to archive.

    Returns:
        The updated Batch object with active=False, or None if not found.
    """
    batch = get_batch(session, batch_id)

    if batch is None:
        return None

    # Mark batch inactive
    batch.active = False

    session.commit()
    session.refresh(batch)

    return batch


def reactivate_batch(session: Session, batch_id: int) -> Batch | None:
    """
    Restores a previously archived/deactivated batch back into active status.

    Args:
        session: Active SQLAlchemy database session.
        batch_id: Primary key of the batch to restore.

    Returns:
        The updated Batch object with active=True, or None if not found.
    """
    batch = get_batch(session, batch_id)

    if batch is None:
        return None

    # Restore batch active state
    batch.active = True

    session.commit()
    session.refresh(batch)

    return batch