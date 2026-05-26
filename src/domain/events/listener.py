"""领域层事件监听器接口模块（向后兼容 re-export）

协议定义已迁移至 src.domain.ports.event_listener 和 src.domain.ports.dead_letter_queue
具体实现已迁移至 src.infrastructure.messaging.inmemory_event_listener 和 inmemory_dead_letter_queue
"""

from __future__ import annotations

# Re-export Protocol definitions from new location
from src.domain.ports.dead_letter_queue import DeadLetterQueue
from src.domain.ports.event_listener import EventListener, EventListenerAsync

__all__ = [
    "DeadLetterQueue",
    "EventListener",
    "EventListenerAsync",
]
