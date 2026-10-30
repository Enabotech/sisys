"""接口层 SAP 协议包（Story 5-3 消息契约 + Story 5-11 协议运行时）

SAP（Structured Agent Protocol）——Agent 间结构化通信协议的接口层落位
（architecture.md §13.5 钦定位）。Story 5-3 交付消息契约（types.py 枚举 +
message.py 模型）；Story 5-11 交付协议运行时（bus.py——SAPBus 端口 +
InProcessSAPBus 进程内总线 + JSON wire format 序列化 + 公共黑板桥）；
middleware.py（协议中间件——消息签名/审计）归 V2。

职责边界（职责矩阵 interface-design §2.2）：接口层横向协议（外部通信
适配），非领域事件——SAPMessage 不进 event_channels.yaml/ChannelRouter。
"""

from src.interfaces.sap.bus import InProcessSAPBus, SAPBus, deserialize, serialize
from src.interfaces.sap.message import SAPMessage
from src.interfaces.sap.types import MessagePriority, MessageType

__all__ = [
    "InProcessSAPBus",
    "MessagePriority",
    "MessageType",
    "SAPBus",
    "SAPMessage",
    "deserialize",
    "serialize",
]
