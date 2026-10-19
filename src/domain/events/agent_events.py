"""领域层 Agent事件模块

定义 Agent 决策与生命周期相关的领域事件
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class AgentDecided(DomainEvent):
    """Agent做出决策时触发的事件

    Attributes:
        agent_id: Agent唯一标识符
        event_type: 事件类型，固定为"AgentDecided"
        decision_result: 决策结果字典
        confidence: 决策置信度，范围0.0-1.0
    """

    agent_id: uuid.UUID = field(kw_only=True)  # kw_only 必填（2-6 系技术债清偿 A2）
    event_type: str = field(default="AgentDecided", init=False)
    decision_result: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    def __post_init__(self) -> None:
        """初始化后设置aggregate_id和aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.agent_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Agent")


@dataclass(frozen=True)
class AgentInstantiated(DomainEvent):
    """Agent实例化完成时触发的事件（Story 5-1 — CEO Agent 实例化 MVP）

    审计合规型事件（reliable 单通道），携带配置资产版本供 5.6 隔离日志/5.7
    Phoenix 追溯「哪个配置版本产出该 Agent」。

    Attributes:
        agent_id: Agent唯一标识符（UUID 对象）
        role: Agent角色（AgentRole.value 字符串，如 "ceo"）
        name: Agent显示名称（如 "CEO Agent"）
        config_version: 配置资产版本（AgentConfig.version，如 "1.0.0"）
        event_type: 事件类型，固定为"AgentInstantiated"
    """

    # 必填字段必须 kw_only——DomainEvent 基类字段全带默认值，子类无默认值的
    # 非 kw_only 字段跟在其后时类定义即抛 TypeError（对齐 AgentDecided 先例）
    agent_id: uuid.UUID = field(kw_only=True)
    role: str = field(kw_only=True)
    name: str = field(kw_only=True)
    config_version: str = field(kw_only=True)
    event_type: str = field(default="AgentInstantiated", init=False)

    def __post_init__(self) -> None:
        """初始化后设置aggregate_id和aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.agent_id)  # UUID 对象非 str（基类契约 uuid.UUID | None）
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Agent")


@dataclass(frozen=True)
class AgentProfileLoaded(DomainEvent):
    """Agent身份档案加载完成时触发的事件（Story 5-2 — Agent 身份档案加载）

    审计合规型事件（reliable 单通道，同 AgentInstantiated 语义），携带启动上下文
    计量与活跃技能数——5.7 Phoenix 追踪（token 预算可观测）与 5.9 漂移检测
    （ACTIVE 工具数基线）的消费锚点。

    Attributes:
        agent_id: Agent唯一标识符（UUID 对象——档案归属锚点）
        role: Agent角色（AgentRole.value 字符串，如 "ceo"）
        startup_context_tokens: 启动上下文 token 计量（IDENTITY+SOUL+TOOLS_L1
            拼接后一次 //4 计量，AC-4 预算可观测）
        active_skill_count: ACTIVE 工具数（== len(result.tools_l1) 同源派生）
        event_type: 事件类型，固定为"AgentProfileLoaded"
    """

    # 必填字段必须 kw_only——DomainEvent 基类字段全带默认值，子类无默认值的
    # 非 kw_only 字段跟在其后时类定义即抛 TypeError（对齐 AgentInstantiated 先例）
    agent_id: uuid.UUID = field(kw_only=True)
    role: str = field(kw_only=True)
    startup_context_tokens: int = field(kw_only=True)
    active_skill_count: int = field(kw_only=True)
    event_type: str = field(default="AgentProfileLoaded", init=False)

    def __post_init__(self) -> None:
        """初始化后设置aggregate_id和aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.agent_id)  # UUID 对象非 str（基类契约 uuid.UUID | None）
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Agent")
