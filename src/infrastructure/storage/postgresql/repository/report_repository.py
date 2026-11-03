"""PostgreSQL 报告仓储（Story 6-5a——L2 strategic_reports 表）。

session_factory 可选尾参 + save/get 双模式 fallback（6-4 CR1-F1 修复后
形态——report_repository 从第一天带 factory，不走裸构造后补）。

fallback 防呆（archive_repository 模块 docstring 同款纪律）：fallback 分派
必须直调 ``session_context.get_session()`` 并 catch ``RuntimeError``——经
``PostgreSQLAdapter._session`` property 则 RuntimeError 被包成
InvalidStateError（``from None``），except 永不命中。
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.strategic_report import ReportType, StrategicReport
from src.infrastructure.storage.postgresql.models.report import ReportModel
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import PostgreSQLAdapter
from src.infrastructure.storage.postgresql.session_context import get_session, session_context


class PostgreSQLReportRepository(PostgreSQLAdapter[StrategicReport, ReportModel]):
    """报告仓储实现（ReportRepositoryProtocol——L2 元数据行）。

    通过 ``_to_entity``/``_to_model`` 隔离领域层与 ORM 层（report_type
    enum ↔ str 双向映射）。
    """

    pk_column: str = "report_id"

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        """初始化报告仓储.

        Args:
            session_factory: fallback 独立会话工厂（CLI/后台路径——None 时无
                ContextVar session 则 RuntimeError 上抛，配置缺失显式失败；
                组合根恒注入使生产 CLI 不落此形态）。
        """
        super().__init__(ReportModel)
        self._session_factory = session_factory

    def _to_entity(self, model: ReportModel) -> StrategicReport:
        """ORM 模型 → 领域实体（report_type str → enum）。

        Args:
            model: ORM 行。

        Returns:
            StrategicReport 实体。
        """
        return StrategicReport(
            report_id=model.report_id,
            plan_id=str(model.plan_id),
            report_type=ReportType(model.report_type),
            file_path=model.file_path,
            section_count=model.section_count,
            degraded_section_count=model.degraded_section_count,
            generation_ms=model.generation_ms,
            created_at=model.created_at or datetime.now(timezone.utc),
        )

    def _to_model(self, report: StrategicReport, metadata: dict[str, Any] | None = None) -> ReportModel:
        """领域实体 → ORM 模型（report_type enum → str + metadata JSONB）。

        Args:
            report: 报告实体。
            metadata: 扩展元数据（JSONB——timeline_available/缺失步清单）。

        Returns:
            ReportModel ORM 实例。
        """
        return ReportModel(
            report_id=report.report_id,
            plan_id=uuid.UUID(report.plan_id),
            report_type=report.report_type.value,
            file_path=report.file_path,
            section_count=report.section_count,
            degraded_section_count=report.degraded_section_count,
            generation_ms=report.generation_ms,
            metadata_=metadata or {},
            created_at=report.created_at,
        )

    async def save(self, report: StrategicReport, metadata: dict[str, Any] | None = None) -> StrategicReport:
        """保存报告元数据行（双模式 fallback——6-4 CR1-F1 形态）。

        Args:
            report: 报告实体。
            metadata: 扩展元数据（JSONB）。

        Returns:
            保存后的报告实体。

        Raises:
            RuntimeError: 无请求 session 且无 factory（配置缺失显式失败）。
        """
        try:
            get_session()
        except RuntimeError:
            # CLI/后台路径（无请求 session）——经注入工厂走独立会话 commit
            if self._session_factory is None:
                raise
            async with session_context(self._session_factory):
                return await self._persist(report, metadata)
        return await self._persist(report, metadata)

    async def _persist(self, report: StrategicReport, metadata: dict[str, Any] | None) -> StrategicReport:
        """实际保存（add + flush——report_id 恒新生成 uuid4，纯 INSERT 语义）。

        Args:
            report: 报告实体。
            metadata: 扩展元数据。

        Returns:
            原报告实体（id/时间戳应用侧已定——零 DB 回读依赖）。
        """
        model = self._to_model(report, metadata)
        self._session.add(model)
        await self._session.flush()
        return report

    async def get_latest_by_plan(self, plan_id: uuid.UUID) -> StrategicReport | None:
        """按 plan_id 取最新报告（created_at 降序首行——双模式 fallback）。

        Args:
            plan_id: 规划任务标识。

        Returns:
            最新报告实体；无记录返回 None。

        Raises:
            RuntimeError: 无请求 session 且无 factory（配置缺失显式失败）。
        """
        try:
            get_session()
        except RuntimeError:
            # CLI 检索路径——get 也必须走 fallback 才可达（6-4 chain-query 同款）
            if self._session_factory is None:
                raise
            async with session_context(self._session_factory):
                return await self._do_get_latest(plan_id)
        return await self._do_get_latest(plan_id)

    async def _do_get_latest(self, plan_id: uuid.UUID) -> StrategicReport | None:
        """实际查询（created_at 降序首行）。

        Args:
            plan_id: 规划任务标识。

        Returns:
            最新报告实体或 None。
        """
        statement = select(ReportModel).where(ReportModel.plan_id == plan_id).order_by(ReportModel.created_at.desc()).limit(1)
        result = await self._session.execute(statement)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model is not None else None
