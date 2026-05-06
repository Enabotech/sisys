"""LoginAttemptRepository 单元测试."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.login_attempt_repository import (
    LoginAttemptRepository,
)


@pytest.fixture
def mock_session():
    return mock.AsyncMock(spec=AsyncSession)


@pytest.fixture
def repository(mock_session):
    return LoginAttemptRepository(mock_session)


class TestLoginAttemptRepository:
    """LoginAttemptRepository 测试."""

    @pytest.mark.asyncio
    async def test_record_attempt_success(self, repository, mock_session):
        """测试记录成功登录尝试."""
        username = "testuser"
        user_id = uuid4()

        await repository.record_attempt(
            username=username,
            success=True,
            failure_reason=None,
            user_id=user_id,
            ip_address="127.0.0.1",
            user_agent="TestAgent",
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_attempt_failure(self, repository, mock_session):
        """测试记录失败登录尝试."""
        username = "testuser"
        user_id = uuid4()

        await repository.record_attempt(
            username=username,
            success=False,
            failure_reason="invalid_password",
            user_id=user_id,
            ip_address="127.0.0.1",
            user_agent="TestAgent",
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_is_account_locked_when_not_locked(self, repository, mock_session):
        """测试账户未锁定时返回 False."""
        username = "testuser"
        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = []
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.is_account_locked(username)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_account_locked_when_locked(self, repository, mock_session):
        """测试账户被锁定时返回 True (5次失败)."""
        username = "testuser"
        now = datetime.now(UTC)
        # Simulate 5 failed attempts within lockout period
        attempts = [mock.Mock(attempted_at=now - timedelta(minutes=i * 5)) for i in range(5)]
        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = attempts
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.is_account_locked(username)

        assert result is True

    @pytest.mark.asyncio
    async def test_get_lockout_remaining_minutes(self, repository, mock_session):
        """测试获取锁定剩余分钟数."""
        username = "testuser"
        # Use offset-naive datetime to match what the code expects
        now = datetime.now(UTC).replace(tzinfo=None)
        # 5 failed attempts at 5-minute intervals starting 25 min ago
        # This triggers lockout since MAX_LOGIN_ATTEMPTS = 5
        attempts = [mock.Mock(attempted_at=now - timedelta(minutes=i * 5)) for i in range(25, 0, -5)]
        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = attempts
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        remaining = await repository.get_lockout_remaining_minutes(username)

        assert remaining is not None
        assert remaining > 0

    @pytest.mark.asyncio
    async def test_clear_attempts(self, repository, mock_session):
        """测试清除登录尝试记录."""
        username = "testuser"

        await repository.clear_attempts(username)

        mock_session.execute.assert_called_once()
