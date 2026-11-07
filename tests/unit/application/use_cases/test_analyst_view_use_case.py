"""Story 6-9 - 分析师视图查询用例单元测试（UUID 守卫 242 + 透传）.

守卫分工钦定（GetExecutiveViewUseCase 直系先例）：用例层 UUID 守卫 242 单源
（畸形 plan_id 在此拦截——服务层不守卫，AC-5/OD-3）；空串与非 UUID 走同一
ValueError 分支（uuid.UUID("") 亦抛 ValueError——两输入形态单分支，6-8 Task 0.8
复核结论延续）。

Run with:
    poetry run pytest tests/unit/application/use_cases/test_analyst_view_use_case.py -v
"""

from __future__ import annotations

import uuid as uuid_module
from typing import Any
from unittest import mock

import pytest

from src.application.ports.analyst_view import AnalystView
from src.application.use_cases.get_analyst_view import GetAnalystViewUseCase
from src.domain.exceptions import EntityValidationError

_VALID_PLAN_ID = "123e4567-e89b-12d3-a456-426614174000"


def _make_view(plan_id: str = _VALID_PLAN_ID) -> AnalystView:
    """合法 AnalystView fixture（全默认段——用例只守卫+透传零段语义）."""
    return AnalystView(plan_id=plan_id)


def _make_use_case(
    *,
    view: AnalystView | None = None,
    service_error: Exception | None = None,
) -> tuple[GetAnalystViewUseCase, mock.AsyncMock]:
    """用例+服务替身构造（AsyncMock spec=AnalystViewPort——6-8 用例单测同款形态）."""
    from src.application.ports.analyst_view import AnalystViewPort

    service = mock.AsyncMock(spec=AnalystViewPort)
    if service_error is not None:
        service.build_analyst_view.side_effect = service_error
    else:
        service.build_analyst_view.return_value = view if view is not None else _make_view()
    return GetAnalystViewUseCase(view_service=service), service


class TestUuidGuard:
    """UUID 守卫 242（畸形 plan_id 两形态——非 UUID/空串同分支）."""

    async def test_malformed_plan_id_raises_242(self) -> None:
        """非 UUID plan_id → EntityValidationError(code=EXCEPTION_242)不触达服务."""
        use_case, service = _make_use_case()
        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id="not-a-uuid")
        assert exc_info.value.code == "EXCEPTION_242"
        service.build_analyst_view.assert_not_awaited()

    async def test_empty_plan_id_raises_242(self) -> None:
        """空串 plan_id → 同分支 242（uuid.UUID("") 亦抛 ValueError）."""
        use_case, service = _make_use_case()
        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id="")
        assert exc_info.value.code == "EXCEPTION_242"
        service.build_analyst_view.assert_not_awaited()

    async def test_guard_context_carries_use_case_name(self) -> None:
        """242 context 携带用例名与字段（诊断面——GetExecutiveViewUseCase 同款形态）."""
        use_case, _ = _make_use_case()
        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id="malformed")
        context: dict[str, Any] = exc_info.value.context if isinstance(exc_info.value.context, dict) else {}
        assert context.get("use_case") == "GetAnalystViewUseCase"
        assert context.get("field") == "plan_id"


class TestPassthrough:
    """守卫后透传（合法 plan_id——空 plan 幂等读语义归服务承载）."""

    async def test_valid_plan_id_passes_through(self) -> None:
        """合法 UUID → keyword-only 透传服务+返回视图零变形."""
        view = _make_view()
        use_case, service = _make_use_case(view=view)
        result = await use_case.execute(plan_id=_VALID_PLAN_ID)
        assert result is view
        service.build_analyst_view.assert_awaited_once_with(plan_id=_VALID_PLAN_ID)

    async def test_random_valid_uuid_accepted(self) -> None:
        """任意合法 UUID 透传（uuid4 形态——不限定版本位）."""
        plan_id = str(uuid_module.uuid4())
        use_case, service = _make_use_case()
        await use_case.execute(plan_id=plan_id)
        service.build_analyst_view.assert_awaited_once_with(plan_id=plan_id)

    async def test_service_error_propagates(self) -> None:
        """服务异常原样传播（用例零捕获——段级容错归服务，用例不做第二层吞异常）."""
        use_case, _ = _make_use_case(service_error=RuntimeError("service down"))
        with pytest.raises(RuntimeError, match="service down"):
            await use_case.execute(plan_id=_VALID_PLAN_ID)
