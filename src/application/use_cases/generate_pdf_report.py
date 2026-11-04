"""PDF 报告生成用例（Story 6-5b——plan_id 守卫 + 服务透传）。

与 6-5a ``GenerateMarkdownReportUseCase`` 同构：CLI 入口的安全边界
（plan_id 字符串→UUID 守卫 242）+ 编排服务透传。
"""

import uuid

from src.application.ports.pdf_report import PdfReportGenerationServicePort
from src.domain.entities.strategic_report import StrategicReport
from src.domain.exceptions import EntityValidationError

__all__ = ["GeneratePdfReportUseCase"]


class GeneratePdfReportUseCase:
    """PDF 报告生成用例（CLI 入口安全边界——`report-generate --format pdf`）。"""

    def __init__(self, *, report_service: PdfReportGenerationServicePort) -> None:
        """初始化用例。

        Args:
            report_service: PDF 报告生成服务（端口注入）。
        """
        self._report_service = report_service

    async def execute(self, *, plan_id: str) -> StrategicReport:
        """执行 PDF 报告生成。

        Args:
            plan_id: 规划任务标识（UUID 字符串——CLI 参数原样传入）。

        Returns:
            StrategicReport 实体（report_type=PDF）。

        Raises:
            EntityValidationError: plan_id 非 UUID 字符串（242——先于服务调用）。
        """
        try:
            plan_uuid = uuid.UUID(plan_id)
        except ValueError as error:
            raise EntityValidationError(
                message="plan_id 必须为 UUID 字符串",
                context={"use_case": "GeneratePdfReportUseCase", "field": "plan_id", "plan_id": plan_id},
            ) from error
        return await self._report_service.generate_pdf_report(plan_uuid)
