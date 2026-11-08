"""Story 6-10 - 顾问视图用例单元测试（零参透传 + 无守卫面架构注记）.

零输入零守卫面（OD-3）：本 Story 无 plan_id 输入——build_consultant_view 无参
（畸形 plan_id 守卫面语义自然缺席：零输入即零畸形面，非缺失；6-8/6-9 连续两
Story 242 UUID 守卫后的设计结果）——「无守卫面注记测试」用 inspect.getsource
断言用例源码零 EntityValidationError token（架构注记落测试面）。

Run with:
    poetry run pytest tests/unit/application/use_cases/test_consultant_view_use_case.py -v
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest import mock

import pytest


def _make_view() -> Any:
    """合法 ConsultantView 替身（空态默认构造——用例透传面零字段消费）."""
    from src.application.ports.consultant_view import ConsultantView

    return ConsultantView(generated_at="2026-11-08T10:00:00+00:00")


def _make_use_case(
    *,
    view: Any | None = None,
    service_error: Exception | None = None,
) -> tuple[Any, mock.AsyncMock]:
    """用例+服务替身构造（AsyncMock spec=ConsultantViewPort——6-8/6-9 用例单测同款形态）."""
    from src.application.ports.consultant_view import ConsultantViewPort
    from src.application.use_cases.get_consultant_view import GetConsultantViewUseCase

    service = mock.AsyncMock(spec=ConsultantViewPort)
    if service_error is not None:
        service.build_consultant_view.side_effect = service_error
    else:
        service.build_consultant_view.return_value = view if view is not None else _make_view()
    return GetConsultantViewUseCase(view_service=service), service


class TestZeroParamPassthrough:
    """零参透传（execute() 无参调用服务一次+返回直传——去守卫形态）."""

    async def test_execute_calls_service_once_and_returns_view(self) -> None:
        """execute() 无参调用服务恰一次+视图直传（零参数签名——全局视图 OD-1）."""
        view = _make_view()
        use_case, service = _make_use_case(view=view)
        result = await use_case.execute()
        service.build_consultant_view.assert_awaited_once_with()
        assert result is view

    async def test_service_error_propagates(self) -> None:
        """服务异常原样传播（透传无吞——用例不设容错面）."""
        use_case, _service = _make_use_case(service_error=RuntimeError("service down"))
        with pytest.raises(RuntimeError, match="service down"):
            await use_case.execute()

    async def test_no_guard_face_architecture_note(self) -> None:
        """无守卫面注记测试：用例源码零 EntityValidationError token（「242 语义自然缺席」架构注记落测试——OD-3）."""
        from src.application.use_cases.get_consultant_view import GetConsultantViewUseCase

        source = inspect.getsource(GetConsultantViewUseCase)
        assert "EntityValidationError" not in source, (
            "零输入零畸形面——用例不得含 242 守卫（6-8/6-9 连续两 Story 守卫后的语义自然缺席，非缺失）"
        )

    async def test_execute_signature_zero_param(self) -> None:
        """execute 签名零参（{self}——与 6-8/6-9 {self, plan_id} 分立注记）."""
        from src.application.use_cases.get_consultant_view import GetConsultantViewUseCase

        signature = inspect.signature(GetConsultantViewUseCase.execute)
        assert set(signature.parameters.keys()) == {"self"}
