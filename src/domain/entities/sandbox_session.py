"""领域层沙箱会话聚合根模块

定义沙箱会话聚合根（Story 4.4 R3）,记录会话生命周期信息
（启动时间、资源限制、容器 ID、空闲 TTL、终态时间）。

设计依据:
- 业务主键 session_id:str(匹配 ^[A-Za-z0-9_-]{1,64}$,防注入)
- tenant_id:UUID 多租户隔离
- 不可变设计:@dataclass(frozen=True);状态变更通过 replace() 返回新实例
- 状态字段简化为 3 值(RUNNING/TERMINATED/FAILED),不引入状态机,避免过度设计
- 乐观锁 state_version:int 防止并发更新冲突
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from src.domain.exceptions import EntityValidationError

__all__ = ["SandboxSession", "SandboxSessionState", "SESSION_ID_REGEX"]

SandboxSessionState = Literal["RUNNING", "TERMINATED", "FAILED"]
SESSION_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class SandboxSession:
    """沙箱会话聚合根（Story 4.4 R3 新建)

    Attributes:
        session_id: 业务标识符(字符串,匹配 ^[A-Za-z0-9_-]{1,64}$,非 UUID 主键)
        tenant_id: 多租户隔离 UUID
        container_id: Docker container ID(启动后填充)
        image_digest: 实际启动的镜像 digest
        started_at: 会话启动时间
        last_activity_at: 最近活动时间(用于 30 分钟 TTL 计算)
        terminated_at: 终态时间(TERMINATED/FAILED 时填充)
        resource_limits: 来自 ContainerSpec.to_dict() 的资源限制字典
        state: 状态字面量("RUNNING"/"TERMINATED"/"FAILED")
        state_version: 乐观锁版本号(每次状态变更递增)
    """

    session_id: str
    tenant_id: UUID
    image_digest: str
    started_at: datetime
    last_activity_at: datetime
    resource_limits: dict[str, Any] = field(default_factory=dict)
    container_id: str | None = None
    terminated_at: datetime | None = None
    state: SandboxSessionState = "RUNNING"
    state_version: int = 1

    def __post_init__(self) -> None:
        """字段不变量校验（违反抛 EntityValidationError EXCEPTION_242)。

        校验项:
        1. session_id 格式正则 ^[A-Za-z0-9_-]{1,64}$
        2. tenant_id 非空 UUID
        3. 终态时 terminated_at 必填
        4. started_at / last_activity_at 必须有时区
        """
        if not SESSION_ID_REGEX.match(self.session_id):
            raise EntityValidationError(
                message=(f"session_id must match ^[A-Za-z0-9_-]{{1,64}}$, got '{self.session_id}'"),
                context={
                    "entity": "SandboxSession",
                    "field": "session_id",
                    "value": self.session_id,
                    "pattern": "^[A-Za-z0-9_-]{1,64}$",
                },
            )
        if self.tenant_id is None:
            raise EntityValidationError(
                message="tenant_id must not be None",
                context={"entity": "SandboxSession", "field": "tenant_id"},
            )
        if self.state in ("TERMINATED", "FAILED") and self.terminated_at is None:
            raise EntityValidationError(
                message=f"terminated_at must be set when state is '{self.state}'",
                context={
                    "entity": "SandboxSession",
                    "field": "terminated_at",
                    "state": self.state,
                },
            )

    def with_container_id(self, container_id: str) -> SandboxSession:
        """返回填充 container_id 的新实例（不可变设计）。"""
        return replace(self, container_id=container_id)

    def with_activity(self, activity_time: datetime | None = None) -> SandboxSession:
        """更新 last_activity_at,返回新实例（用于空闲 TTL 计算）。"""
        ts = activity_time or datetime.now(UTC)
        return replace(
            self,
            last_activity_at=ts,
            state_version=self.state_version + 1,
        )

    def with_terminated(self, terminated_at: datetime | None = None) -> SandboxSession:
        """标记为 TERMINATED,返回新实例（终态时 state_version 递增）。"""
        ts = terminated_at or datetime.now(UTC)
        return replace(
            self,
            state="TERMINATED",
            terminated_at=ts,
            last_activity_at=ts,
            state_version=self.state_version + 1,
        )

    def with_failed(self, failed_at: datetime | None = None) -> SandboxSession:
        """标记为 FAILED,返回新实例。"""
        ts = failed_at or datetime.now(UTC)
        return replace(
            self,
            state="FAILED",
            terminated_at=ts,
            last_activity_at=ts,
            state_version=self.state_version + 1,
        )

    def is_idle(self, threshold: datetime) -> bool:
        """判断会话是否空闲（last_activity_at < threshold 且 state=RUNNING）。"""
        return self.state == "RUNNING" and self.last_activity_at < threshold


__all__ = ["SandboxSession", "SandboxSessionState", "SESSION_ID_REGEX"]
