"""LoginAttemptRepository — 登录尝试仓储实现。

用于跟踪用户登录失败尝试，实现账户锁定功能。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ports.login_attempt_repository import LoginAttemptRepositoryPort


class LoginAttemptRepository(LoginAttemptRepositoryPort):
    """登录尝试仓储实现。

    跟踪登录失败尝试，用于实现账户锁定（等保 2.0 合规）。
    """

    # 等保 2.0 配置
    MAX_LOGIN_ATTEMPTS = 5  # 最大失败次数
    LOCKOUT_DURATION_MINUTES = 30  # 锁定时长（分钟）

    def __init__(self, session: AsyncSession):
        """初始化 LoginAttemptRepository。

        Args:
            session: 异步数据库会话
        """
        self._session = session

    async def record_attempt(
        self,
        username: str,
        success: bool,
        failure_reason: str | None = None,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """记录登录尝试。

        Args:
            username: 用户名
            success: 是否成功
            failure_reason: 失败原因
            user_id: 用户 UUID（如果存在）
            ip_address: IP 地址
            user_agent: 用户代理字符串
        """
        from src.infrastructure.storage.postgresql.models import LoginAttemptModel

        attempt = LoginAttemptModel(
            username=username,
            success=success,
            failure_reason=failure_reason,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._session.add(attempt)
        await self._session.flush()

    async def get_recent_failed_attempts(self, username: str) -> int:
        """获取最近的失败尝试次数。

        Args:
            username: 用户名

        Returns:
            最近失败次数（包含成功之后重新计数的逻辑）
        """
        from src.infrastructure.storage.postgresql.models import LoginAttemptModel

        # 获取最近的锁定时间窗口
        cutoff_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)

        # 查找该用户在锁定时间窗口内的失败尝试
        # 包括最后的成功尝试之后的所有失败
        result = await self._session.execute(
            select(LoginAttemptModel)
            .where(
                and_(
                    LoginAttemptModel.username == username,
                    LoginAttemptModel.attempted_at >= cutoff_time,
                    ~LoginAttemptModel.success,
                )
            )
            .order_by(LoginAttemptModel.attempted_at.desc())
        )
        attempts = list(result.scalars().all())
        return len(attempts)

    async def is_account_locked(self, username: str) -> bool:
        """检查账户是否被锁定。

        Args:
            username: 用户名

        Returns:
            True 如果账户被锁定
        """

        recent_failures = await self.get_recent_failed_attempts(username)
        return recent_failures >= self.MAX_LOGIN_ATTEMPTS

    async def get_lockout_remaining_minutes(self, username: str) -> int:
        """获取账户剩余锁定时间。

        Args:
            username: 用户名

        Returns:
            剩余锁定分钟数，如果未锁定返回 0
        """
        from src.infrastructure.storage.postgresql.models import LoginAttemptModel

        cutoff_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)

        # 找到最早的失败尝试
        result = await self._session.execute(
            select(LoginAttemptModel)
            .where(
                and_(
                    LoginAttemptModel.username == username,
                    LoginAttemptModel.attempted_at >= cutoff_time,
                    ~LoginAttemptModel.success,
                )
            )
            .order_by(LoginAttemptModel.attempted_at.asc())
        )
        attempts = list(result.scalars().all())

        if len(attempts) < self.MAX_LOGIN_ATTEMPTS:
            return 0

        # 找到第 MAX_LOGIN_ATTEMPTS 次失败的时间
        lockout_start = attempts[self.MAX_LOGIN_ATTEMPTS - 1].attempted_at
        lockout_end = lockout_start + timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)
        now = datetime.now(UTC).replace(tzinfo=None)

        if now >= lockout_end:
            return 0

        remaining = (lockout_end - now).total_seconds() / 60
        return int(remaining)

    async def clear_attempts(self, username: str) -> None:
        """清除用户的登录尝试记录（在成功登录后调用）。

        Args:
            username: 用户名
        """
        from src.infrastructure.storage.postgresql.models import LoginAttemptModel

        await self._session.execute(delete(LoginAttemptModel).where(LoginAttemptModel.username == username))
        await self._session.flush()
