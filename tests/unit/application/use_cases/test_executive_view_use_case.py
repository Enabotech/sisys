"""Story 6-8 - GetExecutiveViewUseCase 单元测试（UUID 守卫 242 + 透传）.

守卫分工钦定（6-7 直系先例）：用例层 UUID 守卫 242 单源（服务层不守卫——
AC-5/OD-3）；空串与非 UUID 走同一 ValueError 分支（uuid.UUID("") 亦抛
ValueError——两输入形态单分支）。

Run with:
    poetry run pytest tests/unit/application/use_cases/test_executive_view_use_case.py -v
"""

from __future__ import annotations

import uuid as uuid_module
from unittest import mock

import pytest

from src.application.ports.executive_view import ExecutiveViewPort
from src.application.use_cases.get_executive_view import GetExecutiveViewUseCase
from src.domain.exceptions import EntityValidationError


def _make_service_stub() -> mock.AsyncMock:
    """视图服务替身（AsyncMock spec=ExecutiveViewPort——Protocol 契约约束）."""
    return mock.AsyncMock(spec=ExecutiveViewPort)


class TestGetExecutiveViewUseCaseGuards:
    """UUID 守卫 242 两边界+透传（AC-5 畸形腿的用例层单测面）."""

    async def test_malformed_uuid_rejected_242(self) -> None:
        """非 UUID 字符串 → EntityValidationError(242)（code 值级断言）."""
        use_case = GetExecutiveViewUseCase(view_service=_make_service_stub())
        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id="not-a-uuid")
        assert exc_info.value.code == "EXCEPTION_242"
        assert "plan_id" in str(exc_info.value.context)

    async def test_empty_plan_id_rejected_242(self) -> None:
        """空串 plan_id → 242（uuid.UUID("") 同抛 ValueError——同分支两输入形态）."""
        use_case = GetExecutiveViewUseCase(view_service=_make_service_stub())
        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id="")
        assert exc_info.value.code == "EXCEPTION_242"

    async def test_guard_fires_before_service(self) -> None:
        """守卫失败后不得触达服务（守卫先于透传——CLI 五步定式同序）."""
        service = _make_service_stub()
        use_case = GetExecutiveViewUseCase(view_service=service)
        with pytest.raises(EntityValidationError):
            await use_case.execute(plan_id="malformed")
        service.build_executive_view.assert_not_awaited()

    async def test_execute_passes_through_to_service(self) -> None:
        """合法 plan_id → keyword-only 透传服务并返回其视图."""
        service = _make_service_stub()
        sentinel = mock.Mock()
        service.build_executive_view.return_value = sentinel
        use_case = GetExecutiveViewUseCase(view_service=service)
        plan_id = str(uuid_module.uuid4())
        result = await use_case.execute(plan_id=plan_id)
        service.build_executive_view.assert_awaited_once_with(plan_id=plan_id)
        assert result is sentinel
