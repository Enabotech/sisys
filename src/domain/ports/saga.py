"""Saga 领域端口定义

包含 SagaStep（Saga 步骤抽象）和 SagaRepositoryProtocol（Saga 持久化端口）

领域层定义接口，基础设施层提供具体实现：
- SagaStep Protocol → infrastructure/saga/ 具体步骤
- SagaRepositoryProtocol → infrastructure/saga/saga_repository.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from src.domain.ports.saga_status import SagaStatus

if TYPE_CHECKING:
    from src.domain.ports.saga_context import SagaContext


@runtime_checkable
class SagaStep(Protocol):
    """Saga 步骤 Protocol

    每个 SagaStep 表示 Saga 流程中的一个原子操作
    当步骤失败时，compensate() 方法用于执行补偿操作
    """

    @property
    def name(self) -> str:
        """步骤唯一名称"""
        ...

    async def execute(self, context: SagaContext) -> SagaContext:
        """执行正向操作"""
        ...

    async def compensate(self, context: SagaContext) -> SagaContext:
        """执行补偿操作"""
        ...


@runtime_checkable
class SagaRepositoryProtocol(Protocol):
    """Saga 实例持久化端口"""

    async def save(self, context: SagaContext) -> None:
        """保存 Saga 上下文"""
        ...

    async def load(self, saga_id: str) -> SagaContext | None:
        """加载 Saga 上下文"""
        ...

    async def update_status(self, saga_id: str, status: SagaStatus) -> None:
        """更新 Saga 状态"""
        ...


__all__ = ["SagaStep", "SagaRepositoryProtocol"]
