"""报告仓储端口（Story 6-5a——R1 基础端口）。

L2 strategic_reports 表仓储契约：save 落元数据行（report_id 主键 + metadata
JSONB 扩展位——timeline_available/缺失步清单等可观测面）；get_latest_by_plan
按 created_at 取最新行（幂等锚=report_id——同 plan_id 重复生成产生新行，
OD-10）。

查询参数决策规则：单字段标识查找 → 直接参数（get_latest_by_plan(plan_id)）。
"""

import uuid
from typing import Any, Protocol, runtime_checkable

from src.domain.entities.strategic_report import StrategicReport

__all__ = ["ReportRepositoryProtocol"]


@runtime_checkable
class ReportRepositoryProtocol(Protocol):
    """报告仓储端口（R1 基础端口——infrastructure 层实现）。"""

    async def save(self, report: StrategicReport, metadata: dict[str, Any] | None = None) -> StrategicReport:
        """保存报告元数据行。

        Args:
            report: 报告实体（八字段——report_id 主键）。
            metadata: 扩展元数据（JSONB——timeline_available/缺失步清单等）。

        Returns:
            保存后的报告实体。

        Raises:
            ReportStorageError: L2 落库失败（layer="l2"——服务层包装）。
        """
        ...

    async def get_latest_by_plan(self, plan_id: uuid.UUID) -> StrategicReport | None:
        """按 plan_id 取最新报告（created_at 降序首行）。

        Args:
            plan_id: 规划任务标识。

        Returns:
            最新报告实体；无记录返回 None。
        """
        ...
