"""领域层死信队列端口模块

定义死信队列 Protocol，由基础设施层实现
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.events.base import DomainEvent


@runtime_checkable
class DeadLetterQueue(Protocol):
    """死信队列抽象接口

    所有方法均为 async（设计规则3：async一致性），
    __len__ 不纳入 Protocol（Python dunder 方法不可 async）
    """

    async def enqueue(self, event: DomainEvent, error: str, retry_count: int = 0) -> None: ...

    async def dequeue(self) -> tuple[DomainEvent, str, int] | None: ...
