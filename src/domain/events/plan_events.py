"""
sisys - Plan Events.

战略规划相关领域事件。
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.domain.events.base import DomainEvent

if TYPE_CHECKING:
    from src.domain.entities.strategic_plan import PlanStatus


class PlanCreated(DomainEvent):
    """
    规划创建事件。

    当新的战略规划创建时发布。
    """

    def __init__(
        self,
        plan_id: UUID,
        creator_id: str,
        event_id: UUID | None = None,
        occurred_on: datetime | None = None,
    ):
        """
        初始化规划创建事件。

        Args:
            plan_id: 规划 ID
            creator_id: 创建者 ID
        """
        super().__init__(event_id=event_id, occurred_on=occurred_on, aggregate_id=plan_id)
        self._plan_id = plan_id
        self._creator_id = creator_id

    @property
    def plan_id(self) -> UUID:
        """返回规划 ID。"""
        return self._plan_id

    @property
    def creator_id(self) -> str:
        """返回创建者 ID。"""
        return self._creator_id

    @property
    def event_type(self) -> str:
        """返回事件类型。"""
        return "plan.created"

    @property
    def payload(self) -> dict[str, Any]:
        """返回事件负载。"""
        return {
            "plan_id": str(self.plan_id),
            "creator_id": self.creator_id,
        }


class PlanStatusChanged(DomainEvent):
    """
    规划状态变更事件。

    当战略规划的状态发生变更时发布。
    """

    def __init__(
        self,
        plan_id: UUID,
        old_status: "PlanStatus",
        new_status: "PlanStatus",
        event_id: UUID | None = None,
        occurred_on: datetime | None = None,
    ):
        """
        初始化规划状态变更事件。

        Args:
            plan_id: 规划 ID
            old_status: 原状态
            new_status: 新状态
        """
        super().__init__(event_id=event_id, occurred_on=occurred_on, aggregate_id=plan_id)
        self._plan_id = plan_id
        self._old_status = old_status
        self._new_status = new_status

    @property
    def plan_id(self) -> UUID:
        """返回规划 ID。"""
        return self._plan_id

    @property
    def old_status(self) -> "PlanStatus":
        """返回原状态。"""
        return self._old_status

    @property
    def new_status(self) -> "PlanStatus":
        """返回新状态。"""
        return self._new_status

    @property
    def event_type(self) -> str:
        """返回事件类型。"""
        return "plan.status_changed"

    @property
    def payload(self) -> dict[str, Any]:
        """返回事件负载。"""
        return {
            "plan_id": str(self.plan_id),
            "old_status": self.old_status.value,
            "new_status": self.new_status.value,
        }
