"""分析师视图查询用例（Story 6-9）——UUID 守卫 242 + 透传.

守卫分工钦定（GetExecutiveViewUseCase 直系先例）：用例层 UUID 守卫 242 单源
（畸形 plan_id 在此拦截——服务层不守卫，AC-5/OD-3）；空串与非 UUID 走同一
ValueError 分支（uuid.UUID("") 亦抛 ValueError——两输入形态单分支）。

端口版本：(v1.0.0)
"""

from __future__ import annotations

import uuid

from src.application.ports.analyst_view import AnalystView, AnalystViewPort
from src.domain.exceptions import EntityValidationError

__all__ = ["GetAnalystViewUseCase"]


class GetAnalystViewUseCase:
    """分析师视图查询用例（守卫+透传——SINGLETON 无状态）."""

    def __init__(self, *, view_service: AnalystViewPort) -> None:
        """视图服务 keyword-only 注入（组合根 analyst_view_service 注册名 resolve）."""
        self._view_service = view_service

    async def execute(self, *, plan_id: str) -> AnalystView:
        """执行分析师视图查询（守卫后透传服务——空 plan 幂等读语义归服务承载）.

        Args:
            plan_id: 规划任务标识（UUID 字符串）.

        Returns:
            AnalystView 六键冻结视图.

        Raises:
            EntityValidationError: plan_id 非 UUID 字符串（code=EXCEPTION_242）.
        """
        try:
            uuid.UUID(plan_id)
        except ValueError as error:
            raise EntityValidationError(
                message="plan_id 必须为 UUID 字符串",
                context={
                    "use_case": "GetAnalystViewUseCase",
                    "field": "plan_id",
                    "plan_id": plan_id,
                },
            ) from error
        return await self._view_service.build_analyst_view(plan_id=plan_id)
