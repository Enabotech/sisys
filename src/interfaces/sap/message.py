"""接口层 SAP 消息模型（Story 5-3 — FR-IF-03 SAP 消息契约定义）

SAPMessage——Agent 间结构化通信协议的消息载体（Pydantic v2 模型，接口层
合规——domain 零依赖红线不污染）。本 Story 仅交付 Schema 契约；bus/传输/
序列化性能/黑板交互全部归 Story 5.11（SAP 协议支持）实现。

设计源：interface-design.md §7.4 L1302-1335 + sisys-core-domain-design.md
§17.3.7 L1558-1585（两份一致）。

设计缺陷修正（D-7）：sisys-core-domain-design §17.3.7 原文
``correlation_id: UUID = None`` 在 pydantic v2 非法（不可空类型配 None
默认）——修正为 ``UUID | None = None``。

依赖方向：interfaces → domain 枚举（IsolationLevel 复用——SSOT，与
IsolationLevelSwitched 事件同源，str,Enum 与 pydantic v2 原生兼容）。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from src.domain.events.enums import IsolationLevel
from src.interfaces.sap.types import MessagePriority, MessageType


def _utc_now() -> datetime:
    """构造 UTC 感知时间戳（禁裸 utcnow——architecture v8.4.0 红线）。"""
    return datetime.now(UTC)


class SAPMessage(BaseModel):
    """SAP 结构化消息（15 字段）

    必需字段 10（epics 验收点名）：message_id / conversation_id / sender_id /
    receiver_id / message_type / priority / content / correlation_id /
    isolation_level / blackboard_visible。
    补充字段 5（设计文档）：timestamp / subject / context /
    requires_response / timeout_seconds。

    约定：
    - receiver_id 广播时约定值 "broadcast"（message_type=broadcast 组合）
    - correlation_id 关联原请求（response 消息指向 request 的 message_id；
      MVP 阶段可空默认 None）
    - conversation_id 与 PublicBlackboard 端口 str 键的换算（str(conv_id)）
      归 5.11 处理

    Attributes:
        message_id: 消息唯一标识（UUID）
        conversation_id: 会话标识（UUID——必填，无默认）
        sender_id: 发送方 Agent 标识
        receiver_id: 接收方 Agent 标识（广播约定值 "broadcast"）
        message_type: 消息类型（五值枚举）
        priority: 优先级（四值枚举，默认 NORMAL）
        content: 消息内容
        correlation_id: 关联消息标识（可选——D-7 修正联合类型）
        isolation_level: 隔离级别（复用 domain 枚举，默认 L4_HARD）
        blackboard_visible: 黑板可见性（默认 False——5.11 黑板交互消费）
        timestamp: 消息时间戳（UTC 感知）
        subject: 消息主题（默认空串）
        context: 结构化上下文（默认空 dict）
        requires_response: 是否期待响应（默认 False）
        timeout_seconds: 响应超时秒数（默认 300）
    """

    message_id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: str = Field(min_length=1)
    receiver_id: str = Field(min_length=1)
    message_type: MessageType
    priority: MessagePriority = MessagePriority.NORMAL
    content: str
    correlation_id: uuid.UUID | None = None
    isolation_level: IsolationLevel = IsolationLevel.L4_HARD
    blackboard_visible: bool = False
    timestamp: datetime = Field(default_factory=_utc_now)
    subject: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    requires_response: bool = False
    timeout_seconds: int = 300


__all__ = ["SAPMessage"]
