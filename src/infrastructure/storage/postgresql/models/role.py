"""RoleModel — SQLAlchemy model for roles table."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class RoleModel(Base):
    """SQLAlchemy model for the roles table."""

    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
