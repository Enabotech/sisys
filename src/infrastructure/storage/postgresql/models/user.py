"""UserModel — SQLAlchemy model for users table."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class UserModel(Base):
    """SQLAlchemy model for the users table."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __init__(
        self,
        username: str,
        email: str,
        id: UUID | None = None,
        hashed_password: str | None = None,
        is_active: bool = True,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.username = username
        self.email = email
        self.hashed_password = hashed_password
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at
