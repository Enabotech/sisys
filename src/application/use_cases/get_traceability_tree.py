"""溯源树查询用例（Story 6-7——薄透传 + 双守卫）

GetBlmChainTraceUseCase 直系粒度（UUID 守卫同层同码 242 + 透传）；depth 值域
守卫是本 Story 新增面（值域枚举形态——仓内新形态注记 DR1-21，先例=GetBlmChain
TraceUseCase 的 UUID 守卫用例层同层）。CLI 面越域 depth 由 argparse choices
拦截 exit 2 不走本守卫——分工钦定（API 契约节/AC-6）。
"""

from __future__ import annotations

import uuid

from src.application.ports.traceability_tree import TraceabilityTree, TraceabilityTreePort
from src.domain.exceptions import EntityValidationError

_VALID_DEPTHS: frozenset[int] = frozenset({1, 2, 3, 4})


class GetTraceabilityTreeUseCase:
    """溯源树查询用例（SINGLETON 无状态透传）.

    Raises:
        EntityValidationError (EXCEPTION_242): plan_id 非 UUID 或 depth 越域
            （{1,2,3,4} 之外）——用例层守卫（服务层不重复守卫）。
    """

    def __init__(self, *, tree_service: TraceabilityTreePort) -> None:
        """初始化用例依赖.

        Args:
            tree_service: 溯源树聚合端口（TraceabilityTreePort 实现）.
        """
        self._tree_service = tree_service

    async def execute(self, *, plan_id: str, depth: int = 4) -> TraceabilityTree:
        """执行溯源树查询（守卫 + 透传）.

        Args:
            plan_id: 战略规划 ID（UUID 字符串）。
            depth: 展开深度 {1,2,3,4}，默认 4。

        Returns:
            TraceabilityTree——空计划幂等读返回空树（不抛异常）。

        Raises:
            EntityValidationError: plan_id 非 UUID 或 depth 越域（EXCEPTION_242）。
        """
        try:
            uuid.UUID(plan_id)
        except ValueError as error:
            raise EntityValidationError(
                message="plan_id 必须为 UUID 字符串",
                context={
                    "use_case": "GetTraceabilityTreeUseCase",
                    "field": "plan_id",
                    "plan_id": plan_id,
                },
            ) from error
        if depth not in _VALID_DEPTHS:
            raise EntityValidationError(
                message="depth 必须为 1~4 之间的整数",
                context={
                    "use_case": "GetTraceabilityTreeUseCase",
                    "field": "depth",
                    "depth": depth,
                },
            )
        return await self._tree_service.build_trace_tree(plan_id=plan_id, depth=depth)


__all__ = ["GetTraceabilityTreeUseCase"]
