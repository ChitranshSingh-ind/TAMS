from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship as sa_relationship

from app.database.base import Base


class Parent(Base):
    __tablename__ = "parents"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(150), nullable=False)

    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    whatsapp_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    relationship: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    students = sa_relationship(
        "Student",
        back_populates="parent",
    )