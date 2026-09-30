
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.batch import Batch


def create_batch(
    session: Session,
    name: str,
    start_time=None,
    end_time=None,
    days: str | None = None,
) -> Batch:
    batch = Batch(
        name=name.strip(),
        start_time=start_time,
        end_time=end_time,
        days=days,
    )

    session.add(batch)
    session.commit()
    session.refresh(batch)

    return batch


def get_batch(session: Session, batch_id: int) -> Batch | None:
    return session.get(Batch, batch_id)


def get_active_batches(session: Session) -> list[Batch]:
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
    start_time=None,
    end_time=None,
    days: str | None = None,
    active: bool | None = None,
) -> Batch | None:
    batch = session.get(Batch, batch_id)

    if batch is None:
        return None

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

    session.commit()
    session.refresh(batch)

    return batch
def deactivate_batch(session, batch_id):
    batch = get_batch(session, batch_id)

    if batch is None:
        return None

    batch.active = False
    session.commit()
    session.refresh(batch)

    return batch