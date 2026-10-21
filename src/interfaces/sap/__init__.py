"""接口层 SAP 协议包（Story 5-3 — FR-IF-03 SAP 消息契约定义）

SAP（Structured Agent Protocol）——Agent 间结构化通信协议的接口层落位
（architecture.md §13.5 钦定位）。本 Story 交付消息契约（types.py 枚举 +
message.py 模型）；bus.py（消息总线实现）归 Story 5.11、middleware.py
（协议中间件）归 V2。

职责边界（职责矩阵 interface-design §2.2）：接口层横向协议（外部通信
适配），非领域事件——SAPMessage 不进 event_channels.yaml/ChannelRouter。
"""

from src.interfaces.sap.message import SAPMessage
from src.interfaces.sap.types import MessagePriority, MessageType

__all__ = [
    "MessagePriority",
    "MessageType",
    "SAPMessage",
]
