"""接口层 SAP 消息类型枚举（Story 5-3 — FR-IF-03 SAP 消息契约定义）

SAP（Structured Agent Protocol）消息类型与优先级枚举——Agent 间结构化通信
协议的基础类型定义。属接口层横向协议（非领域事件——职责矩阵 interface-design
§2.2），5.11 实现 bus/传输/黑板交互时消费本契约。

设计源：interface-design.md §7.4 L1302-1335 + sisys-core-domain-design.md
§17.3.7 L1558-1585（两份一致）。
"""

from __future__ import annotations

from enum import Enum


class MessageType(str, Enum):
    """SAP 消息类型（五值）

    语义：
    - request: 请求（期待接收方响应）
    - response: 响应（对 request 的回复——correlation_id 关联原请求）
    - notification: 通知（单播告知，不期待响应）
    - broadcast: 广播（receiver_id 约定值 "broadcast"）
    - debate: 辩论（多 Agent 对抗性论证消息）
    """

    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    BROADCAST = "broadcast"
    DEBATE = "debate"


class MessagePriority(str, Enum):
    """SAP 消息优先级（四值）

    语义：low（低）/ normal（普通——默认）/ high（高）/ urgent（紧急）。
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


__all__ = ["MessagePriority", "MessageType"]
