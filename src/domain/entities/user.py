"""领域层用户实体模块

定义用户领域实体，遵循六边形架构：领域层零依赖，仅使用标准库
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID


@dataclass(frozen=True)
class User:
    """用户领域实体（不可变）.

    Attributes:
        id: 用户 UUID
        username: 用户名（唯一）
        password_hash: 密码哈希（bcrypt）
        is_active: 账户是否激活
        is_locked: 账户是否锁定
        failed_login_attempts: 连续登录失败次数
        locked_until: 账户锁定截止时间（UTC）
        created_at: 账户创建时间
        updated_at: 账户最后更新时间
    """

    id: UUID
    username: str
    email: str
    password_hash: str
    is_active: bool = True
    is_locked: bool = False
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def is_account_locked(self, now: datetime | None = None) -> bool:
        """检查账户是否被锁定."""
        if not self.is_locked:
            return False
        if self.locked_until is None:
            return True
        if now is None:
            from datetime import datetime

            now = datetime.now(UTC)
        return now < self.locked_until
