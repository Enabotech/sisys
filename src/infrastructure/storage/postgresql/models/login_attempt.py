"""基础设施层登录尝试模型模块

定义登录尝试的 SQLAlchemy ORM 模型，对应 login_attempts 表
用于跟踪用户登录失败尝试，实现账户锁定功能（等保 2.0 合规）
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


def _utc_now() -> datetime:
    """返回当前 UTC 时间（无时区，用于数据库兼容）。"""
    return datetime.now(UTC).replace(tzinfo=None)


class LoginAttemptModel(Base):
    """登录尝试 SQLAlchemy 模型，对应 login_attempts 表

    跟踪登录失败尝试，实现账户锁定（连续失败 5 次后锁定 30 分钟）

    Attributes:
        id: 主键 UUID
        user_id: 关联用户 UUID（可为空）
        username: 用户名
        ip_address: IP 地址
        user_agent: 用户代理字符串
        success: 是否成功
        failure_reason: 失败原因
        attempted_at: 尝试时间
    """

    __tablename__ = "login_attempts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max length
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    success: Mapped[bool] = mapped_column(default=False)
    failure_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)

    __table_args__ = (
        Index("ix_login_attempts_username_attempted_at", "username", "attempted_at"),
        Index("ix_login_attempts_user_id_attempted_at", "user_id", "attempted_at"),
        UniqueConstraint("user_id", "attempted_at", name="uq_login_attempt_user_time"),
    )

    def __init__(
        self,
        username: str,
        success: bool = False,
        failure_reason: str | None = None,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        id: UUID | None = None,
        attempted_at: datetime | None = None,
    ) -> None:
        """初始化登录尝试记录

        Args:
            username: 用户名
            success: 是否成功，默认 False
            failure_reason: 失败原因，可选
            user_id: 关联用户 UUID，可选
            ip_address: IP 地址，可选
            user_agent: 用户代理字符串，可选
            id: 主键 UUID，为 None 时自动生成
            attempted_at: 尝试时间，为 None 时使用当前 UTC 时间
        """
        self.id = id or uuid4()
        self.user_id = user_id
        self.username = username
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.success = success
        self.failure_reason = failure_reason
        self.attempted_at = attempted_at or _utc_now()
