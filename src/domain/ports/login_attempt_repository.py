"""LoginAttemptRepository Port - 登录尝试仓储端口.

领域层接口，定义登录尝试跟踪的契约。
遵循六边形架构：领域层零依赖，仅使用 ABC + 标准库。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID


class LoginAttemptRepositoryPort(ABC):
    """登录尝试仓储端口（领域层定义，仅使用 ABC + 标准库）

    负责跟踪用户登录失败尝试，用于实现账户锁定功能。
    """

    @abstractmethod
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
        ...

    @abstractmethod
    async def get_recent_failed_attempts(self, username: str) -> int:
        """获取最近的失败尝试次数。

        Args:
            username: 用户名

        Returns:
            最近失败次数
        """
        ...

    @abstractmethod
    async def is_account_locked(self, username: str) -> bool:
        """检查账户是否被锁定。

        Args:
            username: 用户名

        Returns:
            True 如果账户被锁定
        """
        ...

    @abstractmethod
    async def get_lockout_remaining_minutes(self, username: str) -> int:
        """获取账户剩余锁定时间。

        Args:
            username: 用户名

        Returns:
            剩余锁定分钟数
        """
        ...

    @abstractmethod
    async def clear_attempts(self, username: str) -> None:
        """清除用户的登录尝试记录。

        Args:
            username: 用户名
        """
        ...

    @abstractmethod
    async def check_and_record_lockout(
        self,
        username: str,
        success: bool,
        failure_reason: str | None = None,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[bool, int]:
        """原子操作：检查账户是否锁定并记录尝试。

        解决登录锁定竞态条件问题 - 在同一事务中完成检查和记录。

        Args:
            username: 用户名
            success: 是否成功
            failure_reason: 失败原因
            user_id: 用户 UUID（如果存在）
            ip_address: IP 地址
            user_agent: 用户代理字符串

        Returns:
            tuple[bool, int]: (是否被锁定, 剩余锁定分钟数)
        """
        ...
