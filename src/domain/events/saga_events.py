"""Saga 状态变更领域事件

Saga 是分布式事务编排模式，用于协调跨多个服务/存储的操作
SagaStatusChanged 事件记录 Saga 执行过程中的状态转换，
用于审计追踪、补偿触发和监控告警

事件流程：
- Saga 启动 → PENDING
- 步骤执行中 → RUNNING
- 全部成功 → COMPLETED
- 部分失败触发补偿 → COMPENSATING
- 补偿完成 → COMPENSATED
- 异常终止 → FAILED
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from src.domain.events.base import DomainEvent


@dataclass(frozen=True)
class SagaStatusChanged(DomainEvent):
    """Saga 状态变更事件

    记录 Saga 从一个状态转换到另一个状态的时刻
    状态转换包括：启动、执行、完成、补偿、终止

    属性：
        saga_id: Saga 实例唯一标识符
        saga_type: Saga 类型标识（如 "DocumentProcessing"、"StrategicPlanning"）
        old_status: 变更前的状态（首次启动时为 None）
        new_status: 变换后的状态
        step_index: 当前执行到的步骤索引（可选）
        error_message: 错误信息（仅 FAILED 状态时有效）
    """

    saga_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="SagaStatusChanged", init=False)
    source: str = field(default="saga", init=False)
    saga_type: str = ""
    aggregate_type: str = field(default="Saga", init=False)
    old_status: str | None = None
    new_status: str = ""
    step_index: int | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        """验证事件数据完整性，设置派生字段"""
        # 设置 aggregate_id = saga_id（frozen dataclass 需用 object.__setattr__）
        object.__setattr__(self, "aggregate_id", self.saga_id)

        # 验证
        if not self.saga_type:
            raise ValueError("saga_type 不能为空")
        if not self.new_status:
            raise ValueError("new_status 不能为空")
        valid_statuses = ("PENDING", "RUNNING", "COMPLETED", "COMPENSATING", "COMPENSATED", "FAILED")
        if self.new_status not in valid_statuses:
            raise ValueError(f"new_status 必须是有效状态: {valid_statuses}")
        if self.old_status is not None and self.old_status not in valid_statuses:
            raise ValueError(f"old_status 必须是有效状态: {valid_statuses}")


__all__ = ["SagaStatusChanged"]
