"""领域层 隔离级别事件模块

定义Agent隔离级别切换相关的领域事件
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .base import DomainEvent
from .enums import IsolationLevel


@dataclass(frozen=True)
class IsolationLevelSwitched(DomainEvent):
    """Agent隔离级别切换时触发的事件

    Story 5-4 纪律收紧（DC-6）: 切换事件核心字段必填——agent_id 随机自铸
    会断链 aggregate 关联、previous/target 无默认防「L4→L4 无意义切换」、
    trigger_reason 必填（空串是无意义的切换事件）；approval_chain 与
    switch_timestamp 保留默认（MVP 用户请求无审批链——SYS 命令通道归 V1）。

    Attributes:
        agent_id: Agent唯一标识符
        event_type: 事件类型，固定为"IsolationLevelSwitched"
        previous_level: 切换前的隔离级别
        target_level: 目标隔离级别
        trigger_reason: 触发原因
        approval_chain: 审批链列表
        switch_timestamp: 切换时间戳
    """

    # 必填字段必须 kw_only——DomainEvent 基类字段全带默认值，子类无默认值的
    # 非 kw_only 字段跟在其后时类定义即抛 TypeError（对齐 AgentProfileLoaded 先例）
    agent_id: uuid.UUID = field(kw_only=True)
    previous_level: IsolationLevel = field(kw_only=True)
    target_level: IsolationLevel = field(kw_only=True)
    trigger_reason: str = field(kw_only=True)
    event_type: str = field(default="IsolationLevelSwitched", init=False)
    approval_chain: list[str] = field(default_factory=list)
    switch_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.agent_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Agent")
