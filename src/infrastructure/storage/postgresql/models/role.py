"""RoleModel — SQLAlchemy model for roles table."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


def _utc_now() -> datetime:
    """Return current UTC datetime (naive, for database compatibility)."""
    return datetime.now(UTC).replace(tzinfo=None)


class RoleModel(Base):
    """SQLAlchemy model for the roles table."""

    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
