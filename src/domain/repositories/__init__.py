"""Repository interfaces."""

from .base import BaseRepository
from .outbox import OutboxRepository

__all__ = ["BaseRepository", "OutboxRepository"]
