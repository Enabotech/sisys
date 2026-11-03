"""应用层决策追溯查询用例（Story 6-4 — JSON 思维链输出）

GetBlmChainTraceUseCase——按 plan_id 读回 EVIDENCE_PACKAGE 思维链档案清单
组装追溯视图（薄透传 + UUID 守卫——6-3 RecoverCheckpointUseCase R1-F18 统一
形态先例）。读侧零编排逻辑：过滤/排序/round-trip 重构/blob 解引用全部下沉
ChainOfThoughtArchiveService.query_chain_trace（AC-5 唯一数据面）。

出处：AC-5 决策追溯查询面（CLI chain-query --plan-id 消费入口）。
"""

from __future__ import annotations

import logging
import uuid

from src.application.ports.chain_of_thought_archive import (
    ChainOfThoughtArchiveServicePort,
    ChainOfThoughtTraceView,
)
from src.domain.exceptions import EntityValidationError

logger = logging.getLogger(__name__)


class GetBlmChainTraceUseCase:
    """决策追溯查询用例（薄透传——查询面幂等读语义）。"""

    def __init__(self, *, chain_archive_service: ChainOfThoughtArchiveServicePort) -> None:
        """初始化追溯查询用例。

        Args:
            chain_archive_service: 思维链归档服务（query_chain_trace 数据面）。
        """
        self._chain_archive_service = chain_archive_service

    async def execute(self, *, plan_id: str, include_blob: bool = False) -> ChainOfThoughtTraceView:
        """执行决策追溯查询（UUID 守卫 → 服务透传）。

        Args:
            plan_id: 规划任务标识（必须 UUID 字符串——CLI --plan-id 透传面守卫）。
            include_blob: 是否深度解引用 L4 WORM blob（默认 False）。

        Returns:
            追溯视图（无档案合法 plan_id 返回空清单 total=0——幂等读）。

        Raises:
            EntityValidationError: EXCEPTION_242——plan_id 非 UUID 形态（空串/
                畸形与「空清单」语义分立——R1-F14）。
        """
        # 参数守卫：plan_id 必须 UUID 字符串（6-3 R1-F18 统一形态——context 三键）
        try:
            plan_uuid = uuid.UUID(plan_id)
        except ValueError as error:
            raise EntityValidationError(
                message="plan_id 必须为 UUID 字符串",
                context={"use_case": "GetBlmChainTraceUseCase", "field": "plan_id", "plan_id": plan_id},
            ) from error
        return await self._chain_archive_service.query_chain_trace(plan_uuid, include_blob=include_blob)


__all__ = ["GetBlmChainTraceUseCase"]
