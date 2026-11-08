"""顾问视图查询用例（Story 6-10）——零参透传（去守卫形态）.

零输入零守卫面（OD-3）：本 Story 无 plan_id 输入——build_consultant_view 无参
（畸形守卫面语义自然缺席：零输入即零畸形面，非缺失——6-8/6-9 连续两 Story
UUID 守卫后的设计结果）；空态幂等读不抛归服务承载（五先例族第六连）。

端口版本：(v1.0.0)
"""

from __future__ import annotations

from src.application.ports.consultant_view import ConsultantView, ConsultantViewPort

__all__ = ["GetConsultantViewUseCase"]


class GetConsultantViewUseCase:
    """顾问视图查询用例（零参透传——SINGLETON 无状态）."""

    def __init__(self, *, view_service: ConsultantViewPort) -> None:
        """视图服务 keyword-only 注入（组合根 consultant_view_service 注册名 resolve）."""
        self._view_service = view_service

    async def execute(self) -> ConsultantView:
        """执行顾问视图查询（零参透传——全局多项目面板）.

        Returns:
            ConsultantView 五键冻结视图（空态幂等读返回空态视图不抛——AC-5）.
        """
        return await self._view_service.build_consultant_view()
