"""SISYS 领域层 纠正事件模块

定义纠正审批相关的领域事件

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class CorrectionApproved(DomainEvent):
    """纠正被审批通过时触发的事件

    Attributes:
        correction_id: 纠正唯一标识符
        event_type: 事件类型，固定为"CorrectionApproved"
        correction_type: 纠正类型
        previous_value: 纠正前的值
        new_value: 纠正后的值
        approval_chain: 审批链列表
    """

    correction_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="CorrectionApproved", init=False)
    correction_type: str = ""
    previous_value: Any = None
    new_value: Any = None
    approval_chain: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.correction_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Correction")
