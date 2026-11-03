"""Markdown 报告生成用例（Story 6-5a——CLI report-generate 入口的用例层）。

get_blm_chain_trace 用例同族形态：plan_id UUID 守卫（242）→ 服务透传 →
实体返回。
"""

import uuid

from src.application.ports.report_generation import ReportGenerationServicePort
from src.domain.entities.strategic_report import StrategicReport
from src.domain.exceptions import EntityValidationError

__all__ = ["GenerateMarkdownReportUseCase"]


class GenerateMarkdownReportUseCase:
    """Markdown 报告生成用例（plan_id 守卫 + 服务透传）。"""

    def __init__(self, *, report_service: ReportGenerationServicePort) -> None:
        """初始化用例。

        Args:
            report_service: 报告生成服务（R2 应用端口）。
        """
        self._report_service = report_service

    async def execute(self, *, plan_id: str) -> StrategicReport:
        """执行报告生成（plan_id 守卫 + 透传）。

        Args:
            plan_id: 规划任务标识（UUID 字符串——与 chain 归档 plan_id 同源）。

        Returns:
            StrategicReport 实体。

        Raises:
            EntityValidationError: plan_id 非 UUID 字符串（242——守卫先于服务调用）。
            ReportGenerationError: 数据源全缺（490——服务层透传）。
            ReportStorageError: 持久化失败（491——服务层透传）。
        """
        try:
            plan_uuid = uuid.UUID(plan_id)
        except ValueError as error:
            raise EntityValidationError(
                message="plan_id 必须为 UUID 字符串",
                context={
                    "use_case": "GenerateMarkdownReportUseCase",
                    "field": "plan_id",
                    "plan_id": plan_id,
                },
            ) from error
        return await self._report_service.generate_markdown_report(plan_uuid)
