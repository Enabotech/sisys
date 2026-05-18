"""基础设施层死信队列模块（re-export）

DeadLetterQueue Protocol 和 InMemoryDeadLetterQueue 已统一到 Domain 层，
本文件仅提供 re-export 以保持向后兼容

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from src.domain.events.listener import DeadLetterQueue, InMemoryDeadLetterQueue

__all__ = ["DeadLetterQueue", "InMemoryDeadLetterQueue"]
