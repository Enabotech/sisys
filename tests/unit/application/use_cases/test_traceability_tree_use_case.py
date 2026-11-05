"""Story 6-7 GetTraceabilityTreeUseCase 单元测试（TDD 循环 A——用例层）

双守卫（UUID 242 / depth 值域 242——GetBlmChainTraceUseCase 直系先例）+ 薄透传。
CLI 面越域 depth 由 argparse choices 拦截 exit 2 不走 242——用例守卫仅达编程面
直接调用（AC-6/API 契约节分工钦定）。
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

_VALID_PLAN_ID = str(uuid.uuid4())


def _make_use_case() -> tuple[Any, AsyncMock]:
    """构造用例与端口替身（AsyncMock spec=TraceabilityTreePort）."""
    from src.application.ports.traceability_tree import TraceabilityTreePort
    from src.application.use_cases.get_traceability_tree import GetTraceabilityTreeUseCase

    tree_service = AsyncMock(spec=TraceabilityTreePort)
    return GetTraceabilityTreeUseCase(tree_service=tree_service), tree_service


class TestGetTraceabilityTreeUseCase:
    """用例层双守卫 + 透传."""

    @pytest.mark.asyncio
    async def test_guard_malformed_plan_id_242(self) -> None:
        """畸形 plan_id（非 UUID）→ EntityValidationError 242（用例层守卫）."""
        from src.domain.exceptions import EntityValidationError

        use_case, _ = _make_use_case()
        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id="not-a-uuid")
        assert exc_info.value.code == "EXCEPTION_242"
        assert "plan_id" in str(exc_info.value.context.get("field", ""))

    @pytest.mark.asyncio
    async def test_guard_depth_zero_242(self) -> None:
        """depth=0（越域下边界）→ 242."""
        from src.domain.exceptions import EntityValidationError

        use_case, _ = _make_use_case()
        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id=_VALID_PLAN_ID, depth=0)
        assert exc_info.value.code == "EXCEPTION_242"

    @pytest.mark.asyncio
    async def test_guard_depth_five_242(self) -> None:
        """depth=5（越域上边界）→ 242."""
        from src.domain.exceptions import EntityValidationError

        use_case, _ = _make_use_case()
        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id=_VALID_PLAN_ID, depth=5)
        assert exc_info.value.code == "EXCEPTION_242"

    @pytest.mark.asyncio
    async def test_pass_through_with_default_depth(self) -> None:
        """透传：默认 depth=4 传端口（单测 Mock 红线——AsyncMock spec 端口）."""
        use_case, tree_service = _make_use_case()
        await use_case.execute(plan_id=_VALID_PLAN_ID)
        tree_service.build_trace_tree.assert_awaited_once_with(plan_id=_VALID_PLAN_ID, depth=4)

    @pytest.mark.asyncio
    async def test_pass_through_custom_depth(self) -> None:
        """透传：自定义 depth=2 原样传端口."""
        use_case, tree_service = _make_use_case()
        await use_case.execute(plan_id=_VALID_PLAN_ID, depth=2)
        tree_service.build_trace_tree.assert_awaited_once_with(plan_id=_VALID_PLAN_ID, depth=2)

    @pytest.mark.asyncio
    async def test_combined_invalid_uuid_and_depth_raises_242(self) -> None:
        """组合畸形输入：畸形 UUID + 越域 depth 同时出现时 242 仍抛（守卫面完整——顺序不可观测，仅验证双守卫合取不漏）."""
        from src.domain.exceptions import EntityValidationError

        use_case, _ = _make_use_case()
        with pytest.raises(EntityValidationError):
            await use_case.execute(plan_id="bad", depth=99)
