"""PostgreSQLIsolationSwitchLogRepository 薄单测（Story 5.6 — Task 2 TDD 循环 B）

mock session 逻辑面（真实 PG 断言归集成测试）:
- IsolationSwitchLogModel __table_args__: 列集九（八字段实体 + created_at 行创建
  审计列）/ 索引五（agent_id / switch_timestamp / previous_level / target_level /
  组合——level 双向命中 or_ 两臂皆索引化）/ CheckConstraint（previous != target）
- save/search 双模式分派: ContextVar 命中 → add+flush/execute（请求路径）；
  未命中（RuntimeError）→ session_factory fallback 独立会话（CLI 检索可达性前提
  ——search 漏 fallback 则 CLI 场景必炸 RuntimeError）
- SQLAlchemyError → StorageError(cause=exc) 包装链（save/search 两方法——
  redis_isolation_repository L94 先例的 PG 版；outbox/audit 模板均不包装，
  本仓储相对模板的必做增量）
- search 条件构建: level 双向 or_（previous_level OR target_level）+ AND 组合
- ORM→实体映射: 丢弃 created_at 列（实体八字段无 created_at——检索投影不传）

Run with:
    poetry run pytest tests/unit/infrastructure/storage/postgresql/\\
        test_isolation_switch_log_repository.py -v
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.domain.entities.isolation_switch_log import IsolationSwitchLog
from src.domain.events.enums import IsolationLevel
from src.domain.events.isolation_events import IsolationLevelSwitched
from src.domain.exceptions import StorageError
from src.infrastructure.storage.postgresql.models.isolation_switch_log import (
    IsolationSwitchLogModel,
)
from src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository import (
    PostgreSQLIsolationSwitchLogRepository,
)
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


def run_async(coro: Any) -> Any:
    """同步 runner（薄单测同步形态——对齐 document_version 先例）。"""
    return asyncio.run(coro)


def _make_log(chain: tuple[str, ...] = ("审批人",)) -> IsolationSwitchLog:
    """合法日志实体构造辅助."""
    event = IsolationLevelSwitched(
        agent_id=uuid.uuid4(),
        previous_level=IsolationLevel.L4_HARD,
        target_level=IsolationLevel.L3_SOFT,
        trigger_reason="仓储薄单测",
        approval_chain=list(chain),
        switch_timestamp=datetime(2026, 10, 25, 10, 0, 0, tzinfo=UTC),
    )
    return IsolationSwitchLog.from_event(event)


def _make_model() -> IsolationSwitchLogModel:
    """合法 ORM 模型行构造辅助（检索投影面）."""
    return IsolationSwitchLogModel(
        log_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        previous_level="L4",
        target_level="L3",
        trigger_reason="仓储薄单测",
        approval_chain=["审批人"],
        switch_timestamp=datetime(2026, 10, 25, 10, 0, 0, tzinfo=UTC),
    )


class TestModelTableArgs:
    """IsolationSwitchLogModel 表结构断言（ORM ↔ migration 015 一致性）。"""

    def test_columns_nine(self) -> None:
        """列集九列: 八字段实体 + created_at（行创建审计列——server_default NOW()）."""
        columns = {c.name for c in IsolationSwitchLogModel.__table__.columns}
        assert columns == {
            "log_id",
            "agent_id",
            "previous_level",
            "target_level",
            "trigger_reason",
            "approval_chain",
            "switch_timestamp",
            "worm_ref",
            "created_at",
        }

    def test_five_indexes(self) -> None:
        """索引五: agent_id / switch_timestamp / previous_level / target_level /
        (agent_id, switch_timestamp) 组合——level 双向命中 or_ 两臂皆索引化
        （PG BitmapOr 可达，单维 level 检索 P95<500ms 结构性前提）。"""
        from sqlalchemy import Table

        table = IsolationSwitchLogModel.__table__
        assert isinstance(table, Table)  # declarative __table__ 运行时窄化（FromClause → Table）
        index_cols = {tuple(c.name for c in idx.columns) for idx in table.indexes}
        assert ("agent_id",) in index_cols
        assert ("switch_timestamp",) in index_cols
        assert ("previous_level",) in index_cols
        assert ("target_level",) in index_cols
        assert ("agent_id", "switch_timestamp") in index_cols

    def test_check_constraint_noop_rejected(self) -> None:
        """CheckConstraint: previous_level != target_level（DB 层拒绝 no-op 日志——
        实体不变量的 DB 投影，双层防线）。"""
        from sqlalchemy import CheckConstraint as SACheckConstraint
        from sqlalchemy import Table

        table = IsolationSwitchLogModel.__table__
        assert isinstance(table, Table)  # declarative __table__ 运行时窄化（FromClause → Table）
        constraint: SACheckConstraint | None = None
        for candidate in table.constraints:
            if isinstance(candidate, SACheckConstraint):
                constraint = candidate
                break
        assert constraint is not None
        assert "previous_level" in str(constraint.sqltext)
        assert "target_level" in str(constraint.sqltext)

    def test_worm_ref_nullable(self) -> None:
        """worm_ref nullable（OD-1 预留）."""
        assert IsolationSwitchLogModel.__table__.columns["worm_ref"].nullable is True

    def test_created_at_server_default(self) -> None:
        """created_at server_default NOW()（行创建审计列——DB 侧独立于实体投影）。"""
        assert IsolationSwitchLogModel.__table__.columns["created_at"].server_default is not None


class TestSaveRequestPath:
    """save 双模式分派——请求路径（ContextVar 命中 → add + flush）。"""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """mock AsyncSession（add 同步 / flush async）。"""
        mock = AsyncMock()
        mock.add = MagicMock()
        mock.flush = AsyncMock()
        return mock

    def test_save_adds_and_flushes_via_context_session(self, mock_session: AsyncMock) -> None:
        """ContextVar 命中: add + flush（不 commit——请求事务由外层负责）。"""
        token = set_session(mock_session)
        try:
            repo = PostgreSQLIsolationSwitchLogRepository()
            run_async(repo.save(_make_log()))
        finally:
            reset_session(token)
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        mock_session.commit.assert_not_awaited()  # 请求路径零 commit

    def test_save_wraps_sqlalchemy_error_request_path(self, mock_session: AsyncMock) -> None:
        """包装链（请求路径）: flush SQLAlchemyError → StorageError + __cause__ 链接。"""
        mock_session.flush = AsyncMock(side_effect=SQLAlchemyError("connection reset"))
        token = set_session(mock_session)
        try:
            repo = PostgreSQLIsolationSwitchLogRepository()
            with pytest.raises(StorageError) as exc_info:
                run_async(repo.save(_make_log()))
        finally:
            reset_session(token)
        assert exc_info.value.code == "EXCEPTION_103"
        assert isinstance(exc_info.value.__cause__, SQLAlchemyError)
        assert exc_info.value.cause is not None  # cause=exc 构造参数（5-1 Task 3 纪律）

    def test_save_wraps_os_error_fallback_path(self) -> None:
        """包装链（OSError 面）: asyncpg connect 阶段网络故障（ConnectionRefused
        等）穿透 SQLAlchemy 包装层——实测抛原生 OSError 家族，包装链必须覆盖
        （否则 AC-2.3 坏仓储场景 ConnectionRefusedError 裸抛）。"""
        factory_session = AsyncMock()
        factory_session.add = MagicMock()
        factory_session.flush = AsyncMock(side_effect=ConnectionRefusedError(111, "refused"))
        factory = MagicMock(return_value=factory_session)
        repo = PostgreSQLIsolationSwitchLogRepository(session_factory=factory)
        with pytest.raises(StorageError) as exc_info:
            run_async(repo.save(_make_log()))
        assert exc_info.value.code == "EXCEPTION_103"
        assert isinstance(exc_info.value.__cause__, OSError)


class TestSaveFallbackPath:
    """save 双模式分派——fallback 路径（RuntimeError → session_factory 独立会话 commit）。"""

    def test_save_via_factory_session_commits(self) -> None:
        """无 ContextVar session: factory 独立会话 add+flush（CLI/后台路径——
        session_context 编排 commit/close，Story 4-7 outbox 先例）。"""
        factory_session = AsyncMock()
        factory_session.add = MagicMock()
        factory_session.flush = AsyncMock()
        factory = MagicMock(return_value=factory_session)
        repo = PostgreSQLIsolationSwitchLogRepository(session_factory=factory)
        run_async(repo.save(_make_log()))
        factory.assert_called_once()
        factory_session.add.assert_called_once()
        factory_session.flush.assert_awaited_once()
        factory_session.commit.assert_awaited_once()  # session_context 独立会话 commit

    def test_save_wraps_sqlalchemy_error_fallback_path(self) -> None:
        """包装链（fallback 路径）: flush SQLAlchemyError → StorageError（经
        session_context rollback 后上抛的 SQLAlchemyError 同样被外层包装）。"""
        factory_session = AsyncMock()
        factory_session.add = MagicMock()
        factory_session.flush = AsyncMock(side_effect=SQLAlchemyError("server closed"))
        factory = MagicMock(return_value=factory_session)
        repo = PostgreSQLIsolationSwitchLogRepository(session_factory=factory)
        with pytest.raises(StorageError) as exc_info:
            run_async(repo.save(_make_log()))
        assert exc_info.value.code == "EXCEPTION_103"
        assert isinstance(exc_info.value.__cause__, SQLAlchemyError)
        factory_session.rollback.assert_awaited_once()  # session_context 失败回滚

    def test_save_without_factory_reraises_runtime_error(self) -> None:
        """无 ContextVar 且无 factory: RuntimeError 原样上抛（配置缺失显式失败）。"""
        repo = PostgreSQLIsolationSwitchLogRepository()
        with pytest.raises(RuntimeError):
            run_async(repo.save(_make_log()))


class TestSearchRequestPath:
    """search 双模式分派——请求路径 + 条件构建。"""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """mock AsyncSession（execute 返回 count + items 双形态 result）。"""
        mock = AsyncMock()
        result = MagicMock()
        result.scalar_one.return_value = 1  # count 分支
        scalars = MagicMock()
        scalars.all.return_value = [_make_model()]  # items 分支
        result.scalars.return_value = scalars
        mock.execute = AsyncMock(return_value=result)
        return mock

    def test_search_executes_via_context_session(self, mock_session: AsyncMock) -> None:
        """ContextVar 命中: execute 检索（count + items 双查询）。"""
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

        token = set_session(mock_session)
        try:
            repo = PostgreSQLIsolationSwitchLogRepository()
            result = run_async(repo.search(IsolationSwitchLogQuery(agent_id=uuid.uuid4())))
        finally:
            reset_session(token)
        assert mock_session.execute.await_count == 2  # count + items
        assert result.total == 1
        assert len(result.items) == 1

    def test_search_level_condition_is_bidirectional_or(self, mock_session: AsyncMock) -> None:
        """level 条件构建: or_（previous_level OR target_level）——双向命中语义
        （DC-3；单侧 eq 会使集成双向断言红）。"""
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

        captured: list[Any] = []
        original_execute = mock_session.execute

        async def _capture(stmt: Any, *args: Any, **kwargs: Any) -> Any:
            captured.append(stmt)
            return await original_execute(stmt, *args, **kwargs)

        mock_session.execute = AsyncMock(side_effect=_capture)
        token = set_session(mock_session)
        try:
            repo = PostgreSQLIsolationSwitchLogRepository()
            run_async(repo.search(IsolationSwitchLogQuery(level=IsolationLevel.L3_SOFT)))
        finally:
            reset_session(token)
        # whereclause 精确断言（禁全语句匹配——ORDER BY 的 "OR" 子串会假阳性）
        where_texts = [str(stmt.whereclause) for stmt in captured if stmt.whereclause is not None]
        joined = " ".join(where_texts)
        assert "previous_level" in joined, "level 条件缺 previous_level 臂（or_ 双向命中退化）"
        assert "target_level" in joined, "level 条件缺 target_level 臂"
        assert " OR " in joined, "level 条件应为 or_ 双向命中（单侧 eq 语义错误）"

    def test_search_combined_conditions_and(self, mock_session: AsyncMock) -> None:
        """组合条件: agent_id + 时间范围 + level 三条件 AND（audit match_any
        缺陷防呆——本端口纯 AND，无 match_any 字段）。"""
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

        token = set_session(mock_session)
        try:
            repo = PostgreSQLIsolationSwitchLogRepository()
            run_async(
                repo.search(
                    IsolationSwitchLogQuery(
                        agent_id=uuid.uuid4(),
                        start_time=datetime(2026, 10, 25, tzinfo=UTC),
                        end_time=datetime(2026, 10, 26, tzinfo=UTC),
                        level=IsolationLevel.L3_SOFT,
                    )
                )
            )
        finally:
            reset_session(token)
        assert mock_session.execute.await_count == 2

    def test_search_wraps_sqlalchemy_error(self) -> None:
        """包装链（search）: execute SQLAlchemyError → StorageError。"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("timeout"))
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

        token = set_session(mock_session)
        try:
            repo = PostgreSQLIsolationSwitchLogRepository()
            with pytest.raises(StorageError) as exc_info:
                run_async(repo.search(IsolationSwitchLogQuery()))
        finally:
            reset_session(token)
        assert exc_info.value.code == "EXCEPTION_103"
        assert isinstance(exc_info.value.__cause__, SQLAlchemyError)


class TestSearchFallbackPath:
    """search 双模式分派——fallback 路径（CLI isolation-logs 检索可达性前提）。"""

    def test_search_via_factory_session(self) -> None:
        """无 ContextVar session: factory 独立会话检索（只读 commit 是无害空 commit）。"""
        factory_session = AsyncMock()
        result = MagicMock()
        result.scalar_one.return_value = 0
        scalars = MagicMock()
        scalars.all.return_value = []
        result.scalars.return_value = scalars
        factory_session.execute = AsyncMock(return_value=result)
        factory = MagicMock(return_value=factory_session)
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

        repo = PostgreSQLIsolationSwitchLogRepository(session_factory=factory)
        search_result = run_async(repo.search(IsolationSwitchLogQuery()))
        assert search_result.total == 0
        assert search_result.items == ()
        factory_session.execute.assert_awaited()

    def test_search_wraps_sqlalchemy_error_fallback(self) -> None:
        """包装链（search fallback）: SQLAlchemyError → StorageError。"""
        factory_session = AsyncMock()
        factory_session.execute = AsyncMock(side_effect=SQLAlchemyError("refused"))
        factory = MagicMock(return_value=factory_session)
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogQuery

        repo = PostgreSQLIsolationSwitchLogRepository(session_factory=factory)
        with pytest.raises(StorageError) as exc_info:
            run_async(repo.search(IsolationSwitchLogQuery()))
        assert exc_info.value.code == "EXCEPTION_103"


class TestOrmToEntityMapping:
    """ORM→实体映射（检索投影——丢弃 created_at 列）。"""

    def test_to_entity_drops_created_at(self) -> None:
        """映射丢弃 created_at（实体八字段无 created_at——行创建审计列仅 DB 侧；
        AuditLog 实体含 created_at 是 1.10 形态，本实体单钟以 switch_timestamp
        为时间真源）。"""
        model = _make_model()
        entity = PostgreSQLIsolationSwitchLogRepository._to_entity(model)
        assert entity.log_id == model.log_id
        assert entity.agent_id == model.agent_id
        assert entity.previous_level is IsolationLevel.L4_HARD
        assert entity.target_level is IsolationLevel.L3_SOFT
        assert entity.trigger_reason == model.trigger_reason
        assert entity.approval_chain == ("审批人",)  # list → tuple
        assert entity.switch_timestamp == model.switch_timestamp
        assert entity.worm_ref is None
        assert not hasattr(entity, "created_at")

    def test_to_model_roundtrip_fields(self) -> None:
        """实体→ORM 模型字段完整（save 写入面——log_id/agent_id/枚举 .value/chain list）。"""
        log = _make_log(chain=("审批人", "安全官"))
        model = PostgreSQLIsolationSwitchLogRepository._to_model(log)
        assert model.log_id == log.log_id
        assert model.agent_id == log.agent_id
        assert model.previous_level == "L4"
        assert model.target_level == "L3"
        assert model.approval_chain == ["审批人", "安全官"]  # tuple → list（JSONB）
        assert model.switch_timestamp == log.switch_timestamp
        assert model.worm_ref is None
