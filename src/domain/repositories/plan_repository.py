"""
sisys - Plan Repository Protocol.

战略规划仓储接口定义（使用 Protocol 进行结构化子类型）。
"""
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.entities.strategic_plan import StrategicPlan


@runtime_checkable
class PlanRepository(Protocol):
    """战略规划仓储接口。"""

    async def get_by_id(self, id: UUID) -> StrategicPlan | None:
        """根据 ID 获取规划。"""
        ...

    async def find_all(self) -> list[StrategicPlan]:
        """获取所有规划。"""
        ...

    async def add(self, plan: StrategicPlan) -> StrategicPlan:
        """添加新规划。"""
        ...

    async def update(self, plan: StrategicPlan) -> StrategicPlan:
        """更新规划。"""
        ...

    async def delete(self, plan: StrategicPlan) -> None:
        """删除规划。"""
        ...
