"""GenerateMarkdownReportUseCase 单元测试（Story 6-5a Task 3 循环 B）。

覆盖面（get_blm_chain_trace 用例同族形态）：
- plan_id UUID 守卫（非法 → EntityValidationError 242——context use_case 三键）
- 守卫先于服务调用（非法形态零服务调用）
- 透传（plan_id UUID 转发服务）与返回实体

Run with:
    poetry run pytest tests/unit/application/use_cases/test_generate_markdown_report_use_case.py -v
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from src.application.ports.report_generation import ReportGenerationServicePort
from src.application.use_cases.generate_markdown_report import GenerateMarkdownReportUseCase
from src.domain.entities.strategic_report import ReportType, StrategicReport
from src.domain.exceptions import EntityValidationError


def _make_report() -> StrategicReport:
    """构造报告实体（返回值透传断言锚）。"""
    return StrategicReport(
        plan_id=str(uuid.uuid4()),
        report_type=ReportType.MARKDOWN,
        file_path="reports/plan_20261103120000.md",
        section_count=11,
        degraded_section_count=0,
        generation_ms=100,
    )


def _make_use_case(service: AsyncMock) -> GenerateMarkdownReportUseCase:
    """构造被测用例（服务 AsyncMock 注入）。"""
    return GenerateMarkdownReportUseCase(report_service=service)


class TestPlanIdGuard:
    """plan_id UUID 守卫（get_blm_chain_trace 先例同族形态）。"""

    @pytest.mark.asyncio
    async def test_invalid_plan_id_raises_242(self) -> None:
        """非法 plan_id → EntityValidationError 242（context 三键）。"""
        service = AsyncMock(spec=ReportGenerationServicePort)
        use_case = _make_use_case(service)
        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id="not-a-uuid")
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["use_case"] == "GenerateMarkdownReportUseCase"
        assert exc_info.value.context["field"] == "plan_id"

    @pytest.mark.asyncio
    async def test_invalid_plan_id_no_service_call(self) -> None:
        """守卫先于服务调用（非法形态零服务调用）。"""
        service = AsyncMock(spec=ReportGenerationServicePort)
        use_case = _make_use_case(service)
        with pytest.raises(EntityValidationError):
            await use_case.execute(plan_id="")
        service.generate_markdown_report.assert_not_awaited()


class TestPassthroughAndReturn:
    """透传与返回。"""

    @pytest.mark.asyncio
    async def test_passthrough_plan_id_and_returns_entity(self) -> None:
        """plan_id 转 UUID 透传服务 + 返回实体原样。"""
        plan_uuid = uuid.uuid4()
        report = _make_report()
        service = AsyncMock(spec=ReportGenerationServicePort)
        service.generate_markdown_report.return_value = report
        use_case = _make_use_case(service)
        result = await use_case.execute(plan_id=str(plan_uuid))
        service.generate_markdown_report.assert_awaited_once_with(plan_uuid)
        assert result is report
