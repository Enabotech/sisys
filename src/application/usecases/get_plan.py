"""
sisys - Get Plan Use Case.

获取战略规划用例。
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from src.domain.entities.strategic_plan import StrategicPlan
    from src.domain.repositories import PlanRepository


@dataclass(frozen=True)
class GetPlanQuery:
    """获取战略规划查询。"""

    plan_id: "UUID"


class GetPlanHandler:
    """获取战略规划用例处理器。"""

    def __init__(self, plan_repository: "PlanRepository"):
        """
        初始化处理器。

        Args:
            plan_repository: 规划仓储
        """
        self._plan_repository = plan_repository

    async def handle(self, query: GetPlanQuery) -> "StrategicPlan":
        """
        处理获取规划查询。

        Args:
            query: 查询

        Returns:
            规划数据

        Raises:
            NotFoundError: 当规划不存在时
        """
        from src.domain.exceptions.not_found_error import NotFoundError

        result = await self._plan_repository.get_by_id(query.plan_id)
        if result is None:
            raise NotFoundError("StrategicPlan", str(query.plan_id))
        return result
