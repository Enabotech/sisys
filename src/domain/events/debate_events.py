"""领域层红蓝辩论事件模块

Story 4.5 — 红蓝辩论机制基础（单 Agent 多视角 MVP）。

事件清单：
- DebateCompleted: 红蓝辩论完成事件（双通道 reliable：realtime Redis pub/sub +
  reliable RabbitMQ，对齐 ToolExecuted 模式），下游消费方：审计/工作流/
  后续 Agent 协作（Epic 5/10）。

事件聚合根设计（对齐 sandbox_events.py 惯例）：
- aggregate_type = "DebateSession"
- aggregate_id = debate_id（UUID）
- metadata 透传 tenant_id（多租户归属）
- topic_title 超 100 字符经 object.__setattr__ 截断（frozen dataclass 惯例）

双通道登记（两处同步，本文件 > DEFAULT_MAPPINGS 优先级声明见 yaml 文件头）：
- configs/event_channels.yaml: redis_channel="sisys:rt:debate_completed"
  + rabbitmq_routing_key="sisys.events.reliable.debate_completed"
  + delivery_mode="reliable"
- src/infrastructure/messaging/channel_router.py DEFAULT_MAPPINGS 同参数条目
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent

# 议题标题截断上限（异常 context 同款惯例）
_TOPIC_TITLE_MAX_LENGTH = 100


@dataclass(frozen=True)
class DebateCompleted(DomainEvent):
    """红蓝辩论完成事件

    Attributes:
        debate_id: 辩论会话 ID（aggregate_id 同源）
        tenant_id: 租户 ID（metadata 透传）
        topic_title: 议题标题（超 100 字符截断）
        red_stance: 红方（激进派）立场摘要
        blue_stance: 蓝方（保守派）立场摘要
        consensus_count: 共识区域数量
        disagreement_count: 分歧区域数量
        overlap_rate: 红蓝重叠率
        overall_risk_level: 整体风险等级（LOW/MEDIUM/HIGH）
        duration_ms: 辩论耗时（毫秒）
        temperature_profile: 温度阶梯 {"red": 0.8, "blue": 0.5, "synthesis": 0.2}
        event_type: 事件类型，固定为 "DebateCompleted"（init=False 自动注册）
    """

    debate_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID = field(default_factory=uuid.uuid4)
    topic_title: str = ""
    red_stance: str = ""
    blue_stance: str = ""
    consensus_count: int = 0
    disagreement_count: int = 0
    overlap_rate: float = 0.0
    overall_risk_level: str = "MEDIUM"
    duration_ms: int = 0
    temperature_profile: dict[str, Any] = field(default_factory=lambda: {"red": 0.8, "blue": 0.5, "synthesis": 0.2})
    event_type: str = field(default="DebateCompleted", init=False)

    def __post_init__(self) -> None:
        """填 aggregate 归属 + metadata 透传 tenant_id + 超长标题截断"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.debate_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "DebateSession")
        if "tenant_id" not in self.metadata:
            object.__setattr__(
                self,
                "metadata",
                {**self.metadata, "tenant_id": self.tenant_id},
            )
        if len(self.topic_title) > _TOPIC_TITLE_MAX_LENGTH:
            object.__setattr__(
                self,
                "topic_title",
                self.topic_title[:_TOPIC_TITLE_MAX_LENGTH],
            )


__all__ = ["DebateCompleted"]
