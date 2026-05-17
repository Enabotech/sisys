"""Unit tests for User domain entity."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from src.domain.entities.user import User


class TestUserIsAccountLocked:
    """Test User.is_account_locked method."""

    def test_not_locked_returns_false(self) -> None:
        """Should return False when is_locked is False."""
        user = User(
            id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            password_hash="abc",
            is_locked=False,
        )
        assert user.is_account_locked() is False

    def test_locked_with_no_expiry_returns_true(self) -> None:
        """Should return True when locked_until is None."""
        user = User(
            id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            password_hash="abc",
            is_locked=True,
            locked_until=None,
        )
        assert user.is_account_locked() is True

    def test_locked_with_future_expiry_returns_true(self) -> None:
        """Should return True when current time is before locked_until."""
        user = User(
            id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            password_hash="abc",
            is_locked=True,
            locked_until=datetime.now(UTC) + timedelta(hours=1),
        )
        now = datetime.now(UTC)
        assert user.is_account_locked(now) is True

    def test_locked_with_past_expiry_returns_false(self) -> None:
        """Should return False when current time is after locked_until."""
        user = User(
            id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            password_hash="abc",
            is_locked=True,
            locked_until=datetime.now(UTC) - timedelta(hours=1),
        )
        now = datetime.now(UTC)
        assert user.is_account_locked(now) is False

    def test_uses_current_time_when_now_not_provided(self) -> None:
        """Should use datetime.now(UTC) when now parameter not provided."""
        user = User(
            id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            password_hash="abc",
            is_locked=True,
            locked_until=datetime.now(UTC) + timedelta(hours=1),
        )
        # Should not raise, uses datetime.now(UTC) internally
        result = user.is_account_locked()
        assert result is True
