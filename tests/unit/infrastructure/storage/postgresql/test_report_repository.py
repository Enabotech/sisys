"""PostgreSQLReportRepository 单元测试（Story 6-5a Task 3 循环 A）。

Mock-session 单测模式（test_isolation_switch_log_repository.py 形态模板）：
- ORM 表结构断言（ReportModel 列集/索引——migration 017 镜像）
- save 双模式 fallback（请求 session 路径 + session_factory 独立会话路径
  ——6-4 CR1-F1 修复后形态；report_repository 从第一天带 factory）
- get_latest_by_plan 双模式 fallback + created_at 最新序
- ORM ↔ 实体映射（report_type enum ↔ str）

Run with:
    poetry run pytest tests/unit/infrastructure/storage/postgresql/test_report_repository.py -v
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.entities.strategic_report import ReportType, StrategicReport
from src.domain.ports.report_repository import ReportRepositoryProtocol
from src.infrastructure.storage.postgresql.models.report import ReportModel
from src.infrastructure.storage.postgresql.repository.report_repository import (
    PostgreSQLReportRepository,
)

#: ORM 列集冻结基线（migration 017 镜像——增减列即契约变更）
_EXPECTED_COLUMNS: frozenset[str] = frozenset(
    {
        "report_id",
        "plan_id",
        "report_type",
        "file_path",
        "section_count",
        "degraded_section_count",
        "generation_ms",
        "metadata",
        "created_at",
    }
)


def run_async(coro):
    """同步驱动协程（无 xdist 单进程形态）。"""
    return asyncio.run(coro)


def _make_report(**overrides: object) -> StrategicReport:
    """构造报告实体（缺省合法形态——覆盖参数注入）。

    Args:
        overrides: 字段覆盖。

    Returns:
        StrategicReport 实例。
    """
    defaults: dict = {
        "plan_id": str(uuid.uuid4()),
        "report_type": ReportType.MARKDOWN,
        "file_path": "reports/plan_20261103120000.md",
        "section_count": 11,
        "degraded_section_count": 0,
        "generation_ms": 120,
    }
    defaults.update(overrides)
    return StrategicReport(**defaults)


def _make_mock_session() -> AsyncMock:
    """构造 mock AsyncSession（add 同步 / flush async——isolation 模板形态）。"""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


class TestModelTableArgs:
    """ReportModel 表结构断言（migration 017 镜像）。"""

    def test_tablename(self) -> None:
        """表名 strategic_reports（L2 元数据表钦定名）。"""
        assert ReportModel.__tablename__ == "strategic_reports"

    def test_columns_match_baseline(self) -> None:
        """列集与冻结基线全等（增减列即契约变更——防漂移即守护）。"""
        columns = set(ReportModel.__table__.columns.keys())
        assert columns == _EXPECTED_COLUMNS

    def test_report_id_primary_key(self) -> None:
        """report_id 主键（幂等锚）。"""
        assert ReportModel.__table__.columns["report_id"].primary_key

    def test_plan_id_indexed(self) -> None:
        """plan_id 带索引（get_latest_by_plan 查询面——__table__ 运行时为 Table，静态 FromClause 需 cast）。"""
        from typing import cast

        from sqlalchemy import Table

        table = cast("Table", ReportModel.__table__)
        indexed_columns = {column.name for index in table.indexes for column in index.columns}
        assert "plan_id" in indexed_columns


class TestSaveRequestPath:
    """save 请求 session 路径（set_session 注入——HTTP 请求形态）。"""

    def test_save_uses_request_session(self) -> None:
        """请求 session 在位 → 直用请求会话 add+flush（零 commit——请求事务外层负责）。"""
        from src.infrastructure.storage.postgresql.session_context import reset_session, set_session

        repo = PostgreSQLReportRepository()
        mock_session = _make_mock_session()
        token = set_session(mock_session)
        try:
            report = _make_report()
            result = run_async(repo.save(report, metadata={"timeline_available": True}))
            assert isinstance(result, StrategicReport)
            mock_session.add.assert_called_once()
            mock_session.flush.assert_awaited_once()
            mock_session.commit.assert_not_awaited()  # 请求路径零 commit
        finally:
            reset_session(token)


class TestSaveFallbackPath:
    """save fallback 路径（CLI/后台无请求 session——session_factory 独立会话）。"""

    def test_save_via_factory_session_commits(self) -> None:
        """无请求 session → 经注入 factory 独立会话（add+flush+commit——CLI 可达性）。"""
        factory_session = _make_mock_session()
        factory = MagicMock(return_value=factory_session)
        repo = PostgreSQLReportRepository(session_factory=factory)
        result = run_async(repo.save(_make_report()))
        assert isinstance(result, StrategicReport)
        factory.assert_called_once()
        factory_session.add.assert_called_once()
        factory_session.flush.assert_awaited_once()
        factory_session.commit.assert_awaited_once()  # session_context 独立会话 commit

    def test_save_without_factory_raises_runtime_error(self) -> None:
        """无请求 session 且无 factory → RuntimeError 显式失败（配置缺失 fail-loud）。"""
        repo = PostgreSQLReportRepository()
        report = _make_report()
        with pytest.raises(RuntimeError):
            run_async(repo.save(report))


class TestGetLatestByPlan:
    """get_latest_by_plan 查询面。"""

    def test_implements_protocol(self) -> None:
        """仓储实现 R1 端口（runtime_checkable isinstance）。"""
        repo = PostgreSQLReportRepository()
        assert isinstance(repo, ReportRepositoryProtocol)

    def test_latest_ordering_by_created_at_desc(self) -> None:
        """查询编译产物含 created_at 降序 + LIMIT（CR1-F2 重写——原 getsource 断言被 docstring 命中恒真）。"""
        from src.infrastructure.storage.postgresql.session_context import reset_session, set_session

        repo = PostgreSQLReportRepository()
        mock_session = _make_mock_session()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        token = set_session(mock_session)
        try:
            run_async(repo.get_latest_by_plan(uuid.uuid4()))
            statement = mock_session.execute.call_args.args[0]
            compiled = str(statement.compile()).lower()
            # 行为面断言：突变 .asc()/删 order_by 即红（docstring 命中不再可能）
            assert "order by strategic_reports.created_at desc" in compiled
            assert "limit" in compiled
        finally:
            reset_session(token)

    def test_none_when_no_rows(self) -> None:
        """无记录返回 None（协议契约——factory 独立会话查询路径）。"""
        factory_session = _make_mock_session()
        factory_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        factory = MagicMock(return_value=factory_session)
        repo = PostgreSQLReportRepository(session_factory=factory)
        result = run_async(repo.get_latest_by_plan(uuid.uuid4()))
        assert result is None


class TestOrmEntityMapping:
    """ORM ↔ 实体映射（enum ↔ str 双向）。"""

    def test_entity_to_model_fields(self) -> None:
        """实体 → ORM 字段映射值级（CR1-F11 重写——mock 捕获 add 的模型实例逐字段断言）。"""
        from src.infrastructure.storage.postgresql.session_context import reset_session, set_session

        repo = PostgreSQLReportRepository()
        mock_session = _make_mock_session()
        token = set_session(mock_session)
        try:
            report = _make_report(
                section_count=11,
                degraded_section_count=2,
                generation_ms=345,
            )
            run_async(repo.save(report, metadata={"timeline_available": False, "missing_stages": ["market_insight_trend"]}))
            added = mock_session.add.call_args.args[0]
            assert isinstance(added, ReportModel)
            assert added.report_id == report.report_id
            assert added.plan_id == uuid.UUID(report.plan_id)  # str → UUID 转换
            assert added.report_type == "markdown"  # enum → str
            assert added.file_path == report.file_path
            assert added.section_count == 11
            assert added.degraded_section_count == 2
            assert added.generation_ms == 345
            assert added.metadata_ == {"timeline_available": False, "missing_stages": ["market_insight_trend"]}
            assert added.created_at == report.created_at
        finally:
            reset_session(token)

    def test_model_metadata_jsonb_roundtrip_ready(self) -> None:
        """metadata JSONB 列在位（timeline_available 可观测面载体）。"""
        assert "metadata" in ReportModel.__table__.columns.keys()
