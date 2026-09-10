"""领域层工具链事件模块

定义工具链执行相关的领域事件（Story 4.2 AC-7）。
与 Story 4.1a 的 ToolExecuted 事件独立，是 ToolChainRun 聚合根完成时的事件。

事件载荷：
- event_type: 固定为 "ToolChainExecuted"
- chain_run_id: ToolChainRun 聚合根主键
- chain_id: 关联 ToolChainDag 聚合根 ID
- tenant_id: 多租户隔离
- aggregate_id: = chain_run_id
- aggregate_type: "ToolChainRun"
- execution_result: ToolChainRunResult 序列化
- cost_audit: 成本审计字典
- failure_strategy: FAIL_FAST / CONTINUE_ON_ERROR / SKIP_DOWNSTREAM
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class ToolChainExecuted(DomainEvent):
    """工具链执行完成时触发的事件

    Attributes:
        chain_run_id: ToolChainRun 聚合根主键
        chain_id: 关联 ToolChainDag 聚合根 ID
        tenant_id: 多租户隔离
        event_type: 事件类型，固定为 "ToolChainExecuted"
        execution_result: ToolChainRunResult 序列化（node_results + failed_nodes + total_duration_sec）
        cost_audit: 成本审计字典（LLM token / sandbox 时长 / 并行加速比）
        failure_strategy: FAIL_FAST / CONTINUE_ON_ERROR / SKIP_DOWNSTREAM
    """

    chain_run_id: uuid.UUID = field(default_factory=uuid.uuid4)
    chain_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="ToolChainExecuted", init=False)
    execution_result: dict[str, Any] = field(default_factory=dict)
    cost_audit: dict[str, Any] = field(default_factory=dict)
    failure_strategy: str = ""

    def __post_init__(self) -> None:
        """设置 aggregate_id 和 aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.chain_run_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "ToolChainRun")


__all__ = ["ToolChainExecuted"]
