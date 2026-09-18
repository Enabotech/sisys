"""领域层沙箱会话聚合根模块

Story 4.4 — Docker 沙箱执行。
SandboxSession 聚合根（10 字段）支撑:
- 配额统计
- 30 分钟空闲 TTL 清理
- 乐观锁并发安全（state_version）

主键为字符串 session_id（与 L2RdbPort[UUID] 冲突）,
因此 SandboxSessionRepositoryPort 独立 Protocol, 不继承 L2RdbPort。
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from src.domain.exceptions import (
    EntityBusinessRuleError,
    EntityValidationError,
)

# session_id 格式正则（防注入）
SESSION_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

SandboxSessionState = Literal["RUNNING", "TERMINATED", "FAILED"]


@dataclass(frozen=True)
class SandboxSession:
    """沙箱会话聚合根（10 字段,不可变）

    Attributes:
        session_id: 业务会话标识符（字符串,匹配 ^[A-Za-z0-9_-]{1,64}$）
        tenant_id: 多租户隔离 UUID
        container_id: Docker container ID（启动后填充,终止前可空）
        image_digest: 实际启动的镜像 digest
        started_at: 启动时间(UTC)
        last_activity_at: 最后活动时间(UTC),用于 30 分钟 TTL 计算
        terminated_at: 终止时间(UTC),终态时填充
        resource_limits: 容器资源限制字典（来自 ContainerSpec.to_dict()）
        state: 状态字面量（"RUNNING" / "TERMINATED" / "FAILED"）
        state_version: 乐观锁版本号,初始为 0
    """

    session_id: str
    tenant_id: uuid.UUID
    container_id: str | None = None
    image_digest: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    terminated_at: datetime | None = None
    resource_limits: dict[str, Any] = field(default_factory=dict)
    state: SandboxSessionState = "RUNNING"
    state_version: int = 0

    def __post_init__(self) -> None:
        """字段不变量校验"""
        # session_id 正则校验（防注入）
        if not SESSION_ID_REGEX.match(self.session_id):
            raise EntityValidationError(
                f"session_id must match {SESSION_ID_REGEX.pattern}, got '{self.session_id}'",
                context={
                    "entity": "SandboxSession",
                    "field": "session_id",
                    "value": self.session_id,
                    "constraint": SESSION_ID_REGEX.pattern,
                },
            )
        # tenant_id 必须非空 UUID
        if self.tenant_id is None:
            raise EntityValidationError(
                "tenant_id must not be None",
                context={"entity": "SandboxSession", "field": "tenant_id"},
            )
        # 终态时 terminated_at 必填
        if self.state in ("TERMINATED", "FAILED") and self.terminated_at is None:
            raise EntityBusinessRuleError(
                f"state '{self.state}' requires terminated_at to be set",
                context={
                    "entity": "SandboxSession",
                    "field": "terminated_at",
                    "state": self.state,
                },
            )

    def is_idle(self, threshold: datetime) -> bool:
        """判断会话是否空闲（last_activity_at < threshold）

        Args:
            threshold: 空闲判定阈值时间点

        Returns:
            若会话处于 RUNNING 且 last_activity_at 早于阈值,返回 True
        """
        if self.state != "RUNNING":
            return False
        return self.last_activity_at < threshold

    def with_activity_updated(self, at: datetime | None = None) -> "SandboxSession":
        """返回新的 SandboxSession 实例,更新 last_activity_at 和 state_version

        用于记录活动事件（执行代码、停止容器等）。

        Args:
            at: 活动时间(UTC),None 表示当前时间

        Returns:
            新的 SandboxSession 实例（不可变,frozen 模式）
        """
        new_at = at or datetime.now(UTC)
        return SandboxSession(
            session_id=self.session_id,
            tenant_id=self.tenant_id,
            container_id=self.container_id,
            image_digest=self.image_digest,
            started_at=self.started_at,
            last_activity_at=new_at,
            terminated_at=self.terminated_at,
            resource_limits=self.resource_limits,
            state=self.state,
            state_version=self.state_version + 1,
        )

    def with_terminated(self, at: datetime | None = None) -> "SandboxSession":
        """返回新的 SandboxSession 实例,标记为已终止

        Args:
            at: 终止时间(UTC),None 表示当前时间

        Returns:
            新的 SandboxSession 实例,state="TERMINATED",terminated_at 已设置
        """
        new_at = at or datetime.now(UTC)
        return SandboxSession(
            session_id=self.session_id,
            tenant_id=self.tenant_id,
            container_id=self.container_id,
            image_digest=self.image_digest,
            started_at=self.started_at,
            last_activity_at=new_at,
            terminated_at=new_at,
            resource_limits=self.resource_limits,
            state="TERMINATED",
            state_version=self.state_version + 1,
        )


__all__ = ["SandboxSession", "SESSION_ID_REGEX", "SandboxSessionState"]
