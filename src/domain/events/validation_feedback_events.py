"""领域层 Validation Feedback 事件模块

Story 4.7 — Validation Feedback 闭环（增强重试与不可行标记）。

事件清单（两事件自有字段：MarkedInfeasible 8 个 / Recovered 7 个）：
- ToolExecutionMarkedInfeasible: 3 次增强重试耗尽后的不可行标记事件
- ToolExecutionRecovered: 增强重试恢复成功事件

事件聚合根设计（对齐 debate_events.py / sandbox_events.py 惯例）：
- aggregate_type = "ToolExecution"
- aggregate_id = execution_id（主 id——与演进日志幂等键同源，R2-11 定稿；
  attempt 级引擎事件回链仅经 fix_attempts.attempt_execution_id）
- metadata 透传 tenant_id（**str 形态**——UUID 对象会击穿 outbox JSONB /
  redis / rabbitmq 三处 json.dumps，4-5 R1-F01 修复先例）
- failure_summary 超长截断（防 DoS）

双通道登记（两处同步，yaml > DEFAULT_MAPPINGS 优先级声明见 yaml 文件头）：
- configs/event_channels.yaml: redis_channel="sisys:rt:tool_execution_marked_infeasible"
  + rabbitmq_routing_key="sisys.events.reliable.tool_execution_marked_infeasible"
  + delivery_mode="reliable"（ToolExecutionRecovered 同款形态）
- src/infrastructure/messaging/channel_router.py DEFAULT_MAPPINGS 同参数条目
- 运行时语义：DualChannelEventBus 对 reliable 事件仅走 outbox/RabbitMQ 路径
  不发布 Redis（dual_channel_event_bus.py:58-65）——「双通道」指配置面双登记
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .base import DomainEvent

# 失败摘要截断上限（对齐摘录字段统一口径，防 DoS）
_FAILURE_SUMMARY_MAX_LENGTH = 2000


@dataclass(frozen=True)
class ToolExecutionMarkedInfeasible(DomainEvent):
    """工具执行不可行标记事件（3 次增强重试耗尽——AC-3）

    Attributes:
        execution_id: 触发执行的 execution id（主 id——与演进日志幂等键同源）
        tool_id: 工具 ID
        tenant_id: 租户 ID（metadata 透传 str 形态）
        tool_version: 工具版本快照
        error_signature: 归一化错误签名（64 hex）
        enhanced_retry_count: 增强尝试总数（1-3）
        failure_summary: 失败摘要（error_signature/最终 STDERR 摘要/尝试次数——超长截断）
        occurred_at: 发生时间
        event_type: 事件类型，固定为 "ToolExecutionMarkedInfeasible"（init=False 自动注册）
    """

    execution_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tool_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tool_version: str = ""
    error_signature: str = ""
    enhanced_retry_count: int = 3
    failure_summary: str = ""
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_type: str = field(default="ToolExecutionMarkedInfeasible", init=False)

    def __post_init__(self) -> None:
        """填 aggregate 归属 + metadata 透传 tenant_id + 超长摘要截断."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.execution_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "ToolExecution")
        if "tenant_id" not in self.metadata:
            object.__setattr__(
                self,
                "metadata",
                # metadata 以 str 形态透传（debate/tool_schema 事件先例——R1-F01）
                {**self.metadata, "tenant_id": str(self.tenant_id)},
            )
        if len(self.failure_summary) > _FAILURE_SUMMARY_MAX_LENGTH:
            object.__setattr__(self, "failure_summary", self.failure_summary[:_FAILURE_SUMMARY_MAX_LENGTH])


@dataclass(frozen=True)
class ToolExecutionRecovered(DomainEvent):
    """工具执行恢复成功事件（增强重试成功——AC-3）

    Attributes:
        execution_id: 触发执行的 execution id（主 id——与演进日志幂等键同源）
        tool_id: 工具 ID
        tenant_id: 租户 ID（metadata 透传 str 形态）
        tool_version: 工具版本快照
        error_signature: 归一化错误签名（64 hex）
        enhanced_retry_count: 增强尝试总数（1-3，恢复成功时的尝试次数）
        occurred_at: 发生时间
        event_type: 事件类型，固定为 "ToolExecutionRecovered"（init=False 自动注册）
    """

    execution_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tool_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tool_version: str = ""
    error_signature: str = ""
    enhanced_retry_count: int = 1
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_type: str = field(default="ToolExecutionRecovered", init=False)

    def __post_init__(self) -> None:
        """填 aggregate 归属 + metadata 透传 tenant_id."""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.execution_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "ToolExecution")
        if "tenant_id" not in self.metadata:
            object.__setattr__(
                self,
                "metadata",
                {**self.metadata, "tenant_id": str(self.tenant_id)},
            )


__all__ = ["ToolExecutionMarkedInfeasible", "ToolExecutionRecovered"]
