"""GeneratePdfReportUseCase 单元测试（Story 6-5b Task 4——三用例同构 6-5a）。

覆盖面：plan_id UUID 守卫（242）/透传（plan_uuid 值级）/返回实体。

Run with:
    poetry run pytest tests/unit/application/use_cases/test_generate_pdf_report_use_case.py -v
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.ports.pdf_report import PdfReportGenerationServicePort
from src.application.use_cases.generate_pdf_report import GeneratePdfReportUseCase
from src.domain.exceptions import EntityValidationError


def _make_use_case(**overrides: Any) -> tuple[GeneratePdfReportUseCase, AsyncMock]:
    """构造被测用例（服务端口 AsyncMock——mock 仅限单测层纪律）。"""
    service = AsyncMock(spec=PdfReportGenerationServicePort)
    for key, value in overrides.items():
        setattr(service, key, value)
    return GeneratePdfReportUseCase(report_service=service), service


class TestGeneratePdfReportUseCase:
    """用例三面（守卫/透传/返回）。"""

    async def test_invalid_plan_id_raises_242(self) -> None:
        """非法 plan_id（非 UUID）抛 EntityValidationError 242（先于服务调用）。"""
        use_case, service = _make_use_case()
        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id="not-a-uuid")
        assert exc_info.value.code == "EXCEPTION_242"
        service.generate_pdf_report.assert_not_called()

    async def test_plan_id_uuid_passthrough(self) -> None:
        """合法 plan_id 透传为 UUID 值（str→uuid 转换链值级断言）。"""
        plan_uuid = uuid.uuid4()
        use_case, service = _make_use_case()
        service.generate_pdf_report.return_value = object()
        await use_case.execute(plan_id=str(plan_uuid))
        service.generate_pdf_report.assert_called_once_with(plan_uuid)

    async def test_returns_entity(self) -> None:
        """返回服务产物（透传实体）。"""
        sentinel = object()
        use_case, service = _make_use_case()
        service.generate_pdf_report.return_value = sentinel
        result = await use_case.execute(plan_id=str(uuid.uuid4()))
        assert result is sentinel


class TestBrandTemplatePassthrough:
    """Story 6-11：brand_template_name 可选参透传（CLI→use case→服务的必需中间件）。"""

    async def test_brand_none_single_call_unchanged(self) -> None:
        """brand_template_name=None 走单参调用（既有调用形态零变化——可选参
        向后兼容；注册零改动维持 v1.0.0 的运行面证据）。"""
        plan_uuid = uuid.uuid4()
        use_case, service = _make_use_case()
        service.generate_pdf_report.return_value = object()
        await use_case.execute(plan_id=str(plan_uuid))
        service.generate_pdf_report.assert_called_once_with(plan_uuid)

    async def test_brand_template_name_passthrough(self) -> None:
        """品牌参透传（execute 的 brand_template_name → 服务同名 keyword 参
        值级断言——传递链锚）。"""
        plan_uuid = uuid.uuid4()
        use_case, service = _make_use_case()
        service.generate_pdf_report.return_value = object()
        await use_case.execute(plan_id=str(plan_uuid), brand_template_name="商务蓝模板")
        service.generate_pdf_report.assert_called_once_with(plan_uuid, brand_template_name="商务蓝模板")

    async def test_brand_error_propagates(self) -> None:
        """服务异常透传（494 模板不存在等——不吞不包装）。"""
        from src.domain.exceptions import BrandTemplateValidationError

        plan_uuid = uuid.uuid4()
        use_case, service = _make_use_case()
        service.generate_pdf_report.side_effect = BrandTemplateValidationError(
            field="template_name", message="品牌模板不存在: ghost"
        )
        with pytest.raises(BrandTemplateValidationError):
            await use_case.execute(plan_id=str(plan_uuid), brand_template_name="ghost")

    async def test_architecture_note_no_entity_validation_in_source(self) -> None:
        """架构注记测试（getsource 零 EntityValidationError 字样——6-10 :62-69
        直系：用例层架构注记是防回归锚）。"""
        import inspect

        source = inspect.getsource(GeneratePdfReportUseCase)
        assert "EntityValidationError" in source, "守卫注记应在场（架构注记防回归锚）"
