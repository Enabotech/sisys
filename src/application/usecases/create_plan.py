"""
sisys - Create Plan Use Case.

创建战略规划用例。
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.domain.entities.strategic_plan import PlanType

if TYPE_CHECKING:
    from src.domain.entities.strategic_plan import StrategicPlan
    from src.domain.repositories import PlanRepository
    from src.infrastructure.event_bus import EventBus


@dataclass(frozen=True)
class CreatePlanCommand:
    """创建战略规划命令。"""

    plan_type: PlanType
    creator_id: str


class CreatePlanHandler:
    """创建战略规划用例处理器。"""

    def __init__(
        self,
        plan_repository: "PlanRepository",
        event_bus: "EventBus | None" = None,
    ):
        """
        初始化处理器。

        Args:
            plan_repository: 规划仓储
            event_bus: 事件总线（可选）
        """
        self._plan_repository = plan_repository
        self._event_bus = event_bus

    async def handle(self, command: CreatePlanCommand) -> "StrategicPlan":
        """
        处理创建规划命令。

        Args:
            command: 创建命令

        Returns:
            新创建的规划
        """
        from src.domain.entities.strategic_plan import StrategicPlan

        # 创建规划
        plan = StrategicPlan.create(
            plan_type=command.plan_type,
            creator_id=command.creator_id,
        )

        # 保存到仓储
        result = await self._plan_repository.add(plan)

        # 发布事件
        if self._event_bus:
            for event in plan.domain_events:
                await self._event_bus.publish(event.event_type, event.payload)
            plan.clear_events()

        return result
