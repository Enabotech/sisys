"""Story 6-4 — GetBlmChainTraceUseCase 单元测试（追溯用例薄透传 + 242 守卫）。

覆盖面（Task 3 循环 A 红→绿钦定）：
- 透传（plan_id/include_blob 双参直达服务——薄用例零编排逻辑）
- 空清单（服务空视图透传——查询面幂等读语义）
- 242 守卫（plan_id 非 UUID 构造真实 EntityValidationError——6-3 R1-F18
  统一形态先例：context 三键 use_case/field/plan_id）

Mock 形态（AsyncMock(spec=端口协议)——单元测试 Mock 红线合规）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit/application/use_cases/test_blm_chain_trace_use_case.py -v
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.ports.chain_of_thought_archive import (
    ChainOfThoughtArchiveServicePort,
    ChainOfThoughtTraceView,
)
from src.application.use_cases.get_blm_chain_trace import GetBlmChainTraceUseCase
from src.domain.exceptions import EntityValidationError


def _make_service_mock(*, view: ChainOfThoughtTraceView | None = None) -> Any:
    """思维链归档服务替身工厂（query_chain_trace 返回面注入）。"""
    mock = AsyncMock(spec=ChainOfThoughtArchiveServicePort)
    mock.query_chain_trace = AsyncMock(return_value=view or ChainOfThoughtTraceView(plan_id=""))
    return mock


def _make_use_case(service_mock: Any) -> GetBlmChainTraceUseCase:
    """用例工厂（keyword-only 注入——6-3 用例先例形态）。"""
    return GetBlmChainTraceUseCase(chain_archive_service=service_mock)


class TestGetBlmChainTraceUseCase:
    """追溯用例（透传/空清单/242 守卫）。"""

    async def test_execute_passes_through_plan_id_and_include_blob(self) -> None:
        """透传（UUID 解析后直达服务 query_chain_trace——双参原样）。"""
        plan_id = str(uuid.uuid4())
        service_mock = _make_service_mock()
        use_case = _make_use_case(service_mock)
        await use_case.execute(plan_id=plan_id, include_blob=True)
        service_mock.query_chain_trace.assert_awaited_once_with(uuid.UUID(plan_id), include_blob=True)

    async def test_execute_default_include_blob_false(self) -> None:
        """include_blob 默认 False（读 L2 决策依据足够——深度审计显式开启）。"""
        plan_id = str(uuid.uuid4())
        service_mock = _make_service_mock()
        use_case = _make_use_case(service_mock)
        await use_case.execute(plan_id=plan_id)
        service_mock.query_chain_trace.assert_awaited_once_with(uuid.UUID(plan_id), include_blob=False)

    async def test_execute_returns_view_verbatim(self) -> None:
        """视图原样返回（薄透传零加工）。"""
        plan_id = str(uuid.uuid4())
        view = ChainOfThoughtTraceView(plan_id=plan_id, records=[], total=0, archived_count=0)
        service_mock = _make_service_mock(view=view)
        result = await _make_use_case(service_mock).execute(plan_id=plan_id)
        assert result is view

    async def test_empty_trace_passes_through(self) -> None:
        """空清单透传（无档案合法 plan_id——用例层不抛不加工）。"""
        plan_id = str(uuid.uuid4())
        service_mock = _make_service_mock(view=ChainOfThoughtTraceView(plan_id=plan_id))
        result = await _make_use_case(service_mock).execute(plan_id=plan_id)
        assert result.total == 0
        assert result.records == []

    async def test_invalid_plan_id_raises_242_with_context(self) -> None:
        """非 UUID 242 守卫（R1-F18 统一形态——context 三键）。"""
        service_mock = _make_service_mock()
        use_case = _make_use_case(service_mock)
        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id="not-a-uuid")
        error = exc_info.value
        assert error.code == "EXCEPTION_242"
        assert error.context.get("use_case") == "GetBlmChainTraceUseCase"
        assert error.context.get("field") == "plan_id"
        assert error.context.get("plan_id") == "not-a-uuid"
        service_mock.query_chain_trace.assert_not_awaited()  # 守卫先于服务调用

    async def test_empty_string_plan_id_raises_242(self) -> None:
        """空串同走 242（与「空清单」语义分立——R1-F14）。"""
        service_mock = _make_service_mock()
        use_case = _make_use_case(service_mock)
        with pytest.raises(EntityValidationError):
            await use_case.execute(plan_id="")
