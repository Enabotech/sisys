"""基础设施层死信队列模块（re-export）

DeadLetterQueue Protocol 和 InMemoryDeadLetterQueue 已统一到 Domain 层，
本文件仅提供 re-export 以保持向后兼容
"""

from src.domain.ports.dead_letter_queue import DeadLetterQueue
from src.infrastructure.messaging.inmemory_dead_letter_queue import InMemoryDeadLetterQueue

__all__ = ["DeadLetterQueue", "InMemoryDeadLetterQueue"]
