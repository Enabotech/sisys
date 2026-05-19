"""Saga 上下文 Protocol - 领域层接口定义

定义 SagaContext 的接口契约，供 SagaStep 和 SagaRepositoryProtocol 引用。
具体实现位于 infrastructure/saga/saga_context.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from src.domain.ports.saga_status import SagaStatus


@runtime_checkable
class SagaContext(Protocol):
    """Saga 执行上下文 Protocol。

    定义 Saga 执行过程中的状态管理接口：
    - 记录当前执行状态
    - 存储每个步骤的输入/输出数据
    - 支持序列化和反序列化（用于持久化）
    - 记录执行错误用于调试和补偿
    """

    @property
    def saga_id(self) -> uuid.UUID:
        """Saga 实例唯一标识。"""
        ...

    @property
    def saga_type(self) -> str:
        """Saga 类型标识符。"""
        ...

    @property
    def status(self) -> SagaStatus:
        """当前 Saga 状态。"""
        ...

    @property
    def steps_data(self) -> dict[str, dict[str, Any]]:
        """各步骤的输入/输出数据。"""
        ...

    @property
    def current_step_index(self) -> int:
        """当前步骤索引。"""
        ...

    @property
    def errors(self) -> list[dict[str, Any]]:
        """错误记录列表。"""
        ...

    @property
    def created_at(self) -> datetime:
        """创建时间。"""
        ...

    @property
    def updated_at(self) -> datetime:
        """更新时间。"""
        ...

    @property
    def metadata(self) -> dict[str, Any]:
        """元数据。"""
        ...

    def update_status(self, new_status: SagaStatus) -> SagaContext:
        """更新状态，返回新的 SagaContext 实例。"""
        ...

    def set_step_data(self, step_name: str, input_data: Any | None, output_data: Any | None) -> SagaContext:
        """设置步骤执行数据，返回新的 SagaContext 实例。"""
        ...

    def get_step_output(self, step_name: str) -> Any | None:
        """获取步骤的输出数据。"""
        ...

    def advance_step(self, total_steps: int) -> SagaContext:
        """前进到下一个步骤，返回新的 SagaContext 实例。"""
        ...

    def add_error(self, step_name: str, error_message: str) -> SagaContext:
        """添加错误记录，返回新的 SagaContext 实例。"""
        ...

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于持久化）。"""
        ...


__all__ = ["SagaContext"]
