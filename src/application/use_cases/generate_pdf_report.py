"""PDF 报告生成用例（Story 6-5b——plan_id 守卫 + 服务透传；6-11 品牌参透传）。

与 6-5a ``GenerateMarkdownReportUseCase`` 同构：CLI 入口的安全边界
（plan_id 字符串→UUID 守卫 242）+ 编排服务透传。Story 6-11（R3-1 补位）：
``--brand-template`` 传递链 CLI→use case→服务的必需中间件——execute 增
keyword-only ``brand_template_name`` 可选参透传（None 走单参调用——既有
调用形态零变化；注册零改动维持 v1.0.0[可选参默认 None 向后兼容]）。
"""

import uuid

from src.application.ports.pdf_report import PdfReportGenerationServicePort
from src.domain.entities.strategic_report import StrategicReport
from src.domain.exceptions import EntityValidationError

__all__ = ["GeneratePdfReportUseCase"]


class GeneratePdfReportUseCase:
    """PDF 报告生成用例（CLI 入口安全边界——`report-generate --format pdf [--brand-template]`）。"""

    def __init__(self, *, report_service: PdfReportGenerationServicePort) -> None:
        """初始化用例。

        Args:
            report_service: PDF 报告生成服务（端口注入）。
        """
        self._report_service = report_service

    async def execute(
        self,
        *,
        plan_id: str,
        brand_template_name: str | None = None,
    ) -> StrategicReport:
        """执行 PDF 报告生成（品牌模板可选应用）。

        Args:
            plan_id: 规划任务标识（UUID 字符串——CLI 参数原样传入）。
            brand_template_name: 品牌模板名（None=默认态——单参调用形态零变化；
                非 None 透传服务 v1.1.0 品牌编排）。

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
        if brand_template_name is None:
            return await self._report_service.generate_pdf_report(plan_uuid)
        return await self._report_service.generate_pdf_report(plan_uuid, brand_template_name=brand_template_name)
