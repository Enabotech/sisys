"""领域层 Schema 验证事件模块

定义 ToolSchemaValidationFailed 领域事件(Story 4.3 AC-6):
- 13 字段(含 tenant_id baseline + schema_version + is_final)
- INPUT 阶段 is_final=True(不重试)
- OUTPUT 阶段每次重试失败都发布,仅最后一次 is_final=True
- 简化 4.7 订阅者去重逻辑

设计依据：
- 沿用 4.2 ToolChainExecuted DomainEvent 子类模式(frozen dataclass + event_type init=False)
- payload 字段含 violations 列表(JSON Pointer 路径 + 期望类型 + 实际值)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.domain.events.base import DomainEvent


@dataclass(frozen=True)
class ToolSchemaValidationFailed(DomainEvent):
    """工具 Schema 验证失败领域事件(Story 4.3 AC-6,13 字段)

    Attributes:
        execution_id: 关联 ToolExecution 聚合根 ID
        tool_id: 工具 ID
        tenant_id: 多租户隔离(4.2 起 toolchain 事件 baseline 必填)
        event_type: 事件类型,固定为 "ToolSchemaValidationFailed"
        validation_phase: 校验阶段(INPUT / OUTPUT / COMPATIBILITY)
        schema_violations: 违规列表(每项含 path/expected/actual/message)
        retry_attempt: 当前重试次数(1-based)
        failed_at: 失败时间戳(ISO 8601)
        schema_version: Tool.version 快照(4.6 兼容性追踪用)
        is_final: 是否终止事件(INPUT 失败=True;OUTPUT 仅最后一次=True)
    """

    execution_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tool_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="ToolSchemaValidationFailed", init=False)
    validation_phase: str = "INPUT"
    schema_violations: list[dict[str, Any]] = field(default_factory=list)
    retry_attempt: int = 1
    failed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    schema_version: str = "1.0.0"
    is_final: bool = True

    def __post_init__(self) -> None:
        """设置 aggregate_id / aggregate_type / payload"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.execution_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "ToolExecution")
        # payload 含事件载荷(供下游订阅者统一访问)
        object.__setattr__(
            self,
            "payload",
            {
                "execution_id": str(self.execution_id),
                "tool_id": str(self.tool_id),
                "tenant_id": str(self.tenant_id),
                "validation_phase": self.validation_phase,
                "schema_violations": self.schema_violations,
                "retry_attempt": self.retry_attempt,
                "failed_at": self.failed_at.isoformat(),
                "schema_version": self.schema_version,
                "is_final": self.is_final,
            },
        )


__all__ = ["ToolSchemaValidationFailed"]
