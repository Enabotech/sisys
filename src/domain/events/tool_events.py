"""领域层 工具事件模块

定义工具执行相关的领域事件。
Story 4.1a AC-5 Round 2 修正：
- 事件归属：ToolExecution 才是执行聚合根
- aggregate_id = execution_id（不是 tool_id）
- aggregate_type = "ToolExecution"（不是 "Tool"）
- 新增 execution_id 字段（必填）
- tool_id 继续作为关联 ID
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class ToolExecuted(DomainEvent):
    """工具执行完成时触发的事件

    Attributes:
        execution_id: ToolExecution 聚合根主键（Story 4.1a 新增）
        tool_id: 工具唯一标识符（关联 ID）
        tool_version: 工具版本快照
        event_type: 事件类型，固定为"ToolExecuted"
        execution_result: 执行结果字典
        cost_audit: 成本审计字典（LLM token、sandbox 时长）
    """

    execution_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tool_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tool_version: str = ""
    event_type: str = field(default="ToolExecuted", init=False)
    execution_result: dict[str, Any] = field(default_factory=dict)
    cost_audit: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.execution_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "ToolExecution")
