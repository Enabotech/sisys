"""领域层 工具事件模块

定义工具执行相关的领域事件
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
        tool_id: 工具唯一标识符
        event_type: 事件类型，固定为"ToolExecuted"
        execution_result: 执行结果字典
        cost_audit: 成本审计字典
    """

    tool_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="ToolExecuted", init=False)
    execution_result: dict[str, Any] = field(default_factory=dict)
    cost_audit: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.tool_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Tool")
