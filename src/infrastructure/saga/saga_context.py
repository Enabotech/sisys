"""Saga 上下文 - Saga 执行状态和步骤数据的容器

SagaContext 是 Saga 执行过程中的状态管理核心：
- 记录当前执行状态
- 存储每个步骤的输入/输出数据
- 支持序列化和反序列化（用于持久化）
- 记录执行错误用于调试和补偿
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.domain.ports.saga_status import SagaStatus


@dataclass
class SagaContext:
    """Saga 执行上下文"""

    saga_id: uuid.UUID = field(default_factory=uuid.uuid4)
    saga_type: str = ""
    status: SagaStatus = SagaStatus.PENDING
    steps_data: dict[str, dict[str, Any]] = field(default_factory=dict)
    current_step_index: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """验证初始数据"""
        if not self.saga_type:
            raise ValueError("saga_type 不能为空")

    def update_status(self, new_status: SagaStatus) -> SagaContext:
        """更新状态，返回新的 SagaContext 实例"""
        if not self.status.can_transition_to(new_status):
            raise ValueError(f"非法状态转换: {self.status} → {new_status}")
        return SagaContext(
            saga_id=self.saga_id,
            saga_type=self.saga_type,
            status=new_status,
            steps_data=self.steps_data,
            current_step_index=self.current_step_index,
            errors=self.errors,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            metadata=self.metadata,
        )

    def set_step_data(self, step_name: str, input_data: Any | None, output_data: Any | None) -> SagaContext:
        """设置步骤执行数据，返回新的 SagaContext 实例"""
        new_steps_data = copy.deepcopy(self.steps_data)
        new_steps_data[step_name] = {"input": input_data, "output": output_data}
        return SagaContext(
            saga_id=self.saga_id,
            saga_type=self.saga_type,
            status=self.status,
            steps_data=new_steps_data,
            current_step_index=self.current_step_index,
            errors=self.errors,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            metadata=self.metadata,
        )

    def get_step_output(self, step_name: str) -> Any | None:
        """获取步骤的输出数据"""
        step_data = self.steps_data.get(step_name, {})
        return step_data.get("output")

    def advance_step(self, total_steps: int) -> SagaContext:
        """前进到下一个步骤，返回新的 SagaContext 实例"""
        new_index = min(self.current_step_index + 1, total_steps)
        return SagaContext(
            saga_id=self.saga_id,
            saga_type=self.saga_type,
            status=self.status,
            steps_data=self.steps_data,
            current_step_index=new_index,
            errors=self.errors,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            metadata=self.metadata,
        )

    def add_error(self, step_name: str, error_message: str) -> SagaContext:
        """添加错误记录，返回新的 SagaContext 实例"""
        new_errors = list(self.errors)
        new_errors.append(
            {
                "step": step_name,
                "error": error_message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return SagaContext(
            saga_id=self.saga_id,
            saga_type=self.saga_type,
            status=self.status,
            steps_data=self.steps_data,
            current_step_index=self.current_step_index,
            errors=new_errors,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            metadata=self.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于持久化）"""
        return {
            "saga_id": str(self.saga_id),
            "saga_type": self.saga_type,
            "status": self.status.value,
            "steps_data": self.steps_data,
            "current_step_index": self.current_step_index,
            "errors": self.errors,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SagaContext:
        """从字典反序列化

        Args:
            data: 序列化数据

        Returns:
            反序列化后的 SagaContext 实例

        Raises:
            ValueError: 缺少必要字段时抛出
        """
        required_fields = ["saga_id", "saga_type", "status", "created_at", "updated_at"]
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"from_dict 缺少必要字段: {field_name}")

        return cls(
            saga_id=uuid.UUID(data["saga_id"]),
            saga_type=data["saga_type"],
            status=SagaStatus(data["status"]),
            steps_data=data.get("steps_data", {}),
            current_step_index=data.get("current_step_index", 0),
            errors=data.get("errors", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
        )


__all__ = ["SagaContext"]
