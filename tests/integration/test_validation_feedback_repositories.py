"""Story 4.7: PG 双仓储集成测试（ErrorCase + EvolutionLogEntry）

真实 PostgreSQL（探活失败 pytest.skip 动态跳过）+ repo_session 事务 rollback 隔离 +
xdist_group 串行（4-6 test_tool_version_integration 样板）。

覆盖：upsert 幂等 / UNIQUE 冲突 begin_nested 容错（4-6 CR1-4）/ JSONB fix_attempts
读写 / list_by_query 分页过滤 / get_by_execution / record_case 幂等计数。

R3-1 注记：outbox fallback 用例不在本批——落 Task 6 循环 C 向本文件追加
（fallback 修复在 Task 6，本批入库时含该用例必红）。

TDD 红→绿：本文件先于 PG 双仓储 + migration 017 实现（Subtask 4.4）。
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.error_case import ErrorCase
from src.domain.entities.evolution_log_entry import EvolutionLogEntry
from src.domain.ports.evolution_log_repository import EvolutionLogQuery
from src.domain.value_objects.validation_feedback import (
    FeedbackOutcome,
    FixAttempt,
    FixStrategy,
    TriggerCode,
)
from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.postgresql.models import Base
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.repository.error_case_repository import (
    PostgreSQLErrorCaseRepository,
)
from src.infrastructure.storage.postgresql.repository.evolution_log_repository import (
    PostgreSQLEvolutionLogRepository,
)
from src.infrastructure.storage.postgresql.session_context import (
    reset_session,
    set_session,
)
from tests.environments import get_test_env

pytestmark = pytest.mark.xdist_group("validation-feedback-pg")

_SIG = "a" * 64


# ============================================================================
# Fixtures（4-6 样板）
# ============================================================================


@pytest.fixture
def pg_config() -> PostgreSQLConfig:
    """真实 PostgreSQL 配置."""
    env = get_test_env()
    return PostgreSQLConfig(
        host=env.postgres.host,
        port=env.postgres.port,
        database=env.postgres.database,
        username=env.postgres.username,
        password=env.postgres.password,
        pool_size=5,
        max_overflow=10,
    )


@pytest.fixture
def db_engine(pg_config: PostgreSQLConfig) -> PostgreSQLManager:
    """真实数据库引擎."""
    return PostgreSQLManager(pg_config)


@pytest.fixture
def pg_available(pg_config: PostgreSQLConfig, event_loop) -> bool:
    """PostgreSQL 探活（失败动态 skip）."""
    import asyncpg

    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(
                host=pg_config.host,
                port=pg_config.port,
                user=pg_config.username,
                password=pg_config.password,
                database=pg_config.database,
            )
            await conn.close()
            return True
        except Exception:
            return False

    return bool(event_loop.run_until_complete(_check()))


@pytest.fixture
def repo_session(
    db_engine: PostgreSQLManager,
    pg_available: bool,
    event_loop,
) -> Generator[AsyncSession, None, None]:
    """真实 PG 会话（begin + set_session + rollback 隔离）."""
    if not pg_available:
        pytest.skip("PostgreSQL not available")
        return

    try:
        Base.metadata.create_all(db_engine.get_sync_engine())
    except Exception:
        pass

    async_engine = db_engine.get_async_engine()
    session = AsyncSession(async_engine)
    event_loop.run_until_complete(session.begin())
    token = set_session(session)
    yield session
    reset_session(token)
    event_loop.run_until_complete(session.rollback())
    event_loop.run_until_complete(session.close())


# ============================================================================
# 构造工厂
# ============================================================================


def _make_attempt(no: int) -> FixAttempt:
    """构造 attempt 记录."""
    return FixAttempt(
        attempt_no=no,
        attempt_execution_id=str(uuid.uuid4()),
        error_signature=_SIG,
        fix_strategy=FixStrategy.PURE_LLM,
        stderr_excerpt="Traceback ... KeyError: 'x'",
        suggested_fix_excerpt="方案：改前缀",
        succeeded=False,
        detail="retry_failed",
    )


def _make_entry(
    tenant_id: uuid.UUID,
    tool_id: uuid.UUID,
    execution_id: uuid.UUID | None = None,
    *,
    attempts: int = 3,
    final: str = "MARKED_INFEASIBLE",
) -> EvolutionLogEntry:
    """构造演进日志条目."""
    return EvolutionLogEntry(
        tenant_id=tenant_id,
        tool_id=tool_id,
        execution_id=execution_id or uuid.uuid4(),
        trigger_code=TriggerCode.EXCEPTION_389,
        error_signature=_SIG,
        enhanced_retry_count=attempts,
        fix_attempts=tuple(_make_attempt(i) for i in range(1, attempts + 1)),
        duration_sec=2.5,
        final_status=FeedbackOutcome(final),
        tool_version="1.0.0",
    )


def _make_case(
    tenant_id: uuid.UUID,
    tool_id: uuid.UUID,
    signature: str = _SIG,
    *,
    outcome: str = "RECOVERED",
    fix_summary: str = "",
    recovered: int = 1,
    infeasible: int = 0,
) -> ErrorCase:
    """构造回填形态案例."""
    return ErrorCase(
        tenant_id=tenant_id,
        tool_id=tool_id,
        error_signature=signature,
        error_category="SCHEMA_VIOLATION",
        stderr_excerpt="err",
        fix_summary=fix_summary,
        outcome=FeedbackOutcome(outcome),
        recovered_count=recovered,
        infeasible_count=infeasible,
        occurrence_count=recovered + infeasible,
        last_seen_at=datetime.now(UTC),
    )


# ============================================================================
# EvolutionLog PG 仓储用例
# ============================================================================


class TestEvolutionLogPGRepository:
    """PostgreSQLEvolutionLogRepository 真实持久化."""

    @pytest.mark.asyncio
    async def test_save_and_get_by_execution_roundtrip(self, repo_session: AsyncSession) -> None:
        """保存后按 execution_id 精确读回（JSONB fix_attempts 读写）."""
        repo = PostgreSQLEvolutionLogRepository()
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        entry = _make_entry(tenant, tool)

        await repo.save(entry)
        found = await repo.get_by_execution(entry.execution_id, tenant)

        assert found is not None
        assert str(found.execution_id) == str(entry.execution_id)
        assert found.trigger_code == TriggerCode.EXCEPTION_389
        assert found.enhanced_retry_count == 3
        assert len(found.fix_attempts) == 3
        assert found.fix_attempts[0].fix_strategy == FixStrategy.PURE_LLM
        assert found.fix_attempts[0].suggested_fix_excerpt == "方案：改前缀"
        assert found.fix_attempts[1].attempt_execution_id  # 回链非空

    @pytest.mark.asyncio
    async def test_save_idempotent_upsert_single_row(self, repo_session: AsyncSession) -> None:
        """同 execution_id 重复写入不产生重复行（覆盖为最新次）."""
        repo = PostgreSQLEvolutionLogRepository()
        tenant, tool, exec_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

        await repo.save(_make_entry(tenant, tool, exec_id))
        await repo.save(_make_entry(tenant, tool, exec_id, final="RECOVERED", attempts=2))

        logs = await repo.list_by_query(EvolutionLogQuery(tool_id=tool, tenant_id=tenant))
        assert len(logs) == 1
        assert logs[0].final_status == FeedbackOutcome.RECOVERED
        assert logs[0].enhanced_retry_count == 2

    @pytest.mark.asyncio
    async def test_list_by_query_filter_and_pagination(self, repo_session: AsyncSession) -> None:
        """多字段过滤 + 分页 + created_at 降序."""
        repo = PostgreSQLEvolutionLogRepository()
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        for _ in range(5):
            await repo.save(_make_entry(tenant, tool))
        await repo.save(_make_entry(uuid.uuid4(), uuid.uuid4()))  # 异租户噪声

        page = await repo.list_by_query(EvolutionLogQuery(tenant_id=tenant, limit=3, offset=0))
        assert len(page) == 3
        rest = await repo.list_by_query(EvolutionLogQuery(tenant_id=tenant, limit=3, offset=3))
        assert len(rest) == 2
        # 降序：page 全部新于等于 rest 首条（构造后 created_at 必非 None）
        assert page[0].created_at is not None and rest[0].created_at is not None
        assert page[0].created_at >= rest[0].created_at

    @pytest.mark.asyncio
    async def test_get_by_execution_tenant_isolation(self, repo_session: AsyncSession) -> None:
        """跨租户不可见."""
        repo = PostgreSQLEvolutionLogRepository()
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        entry = _make_entry(tenant, tool)
        await repo.save(entry)
        assert await repo.get_by_execution(entry.execution_id, uuid.uuid4()) is None


# ============================================================================
# ErrorCase PG 仓储用例
# ============================================================================


class TestErrorCasePGRepository:
    """PostgreSQLErrorCaseRepository 真实持久化."""

    @pytest.mark.asyncio
    async def test_record_and_get_by_natural_key(self, repo_session: AsyncSession) -> None:
        """首记录建行 + 精确查询."""
        repo = PostgreSQLErrorCaseRepository()
        tenant, tool = uuid.uuid4(), uuid.uuid4()

        result = await repo.record_case(_make_case(tenant, tool, outcome="RECOVERED", fix_summary="配方A"))
        assert result.recovered_count == 1
        assert result.occurrence_count == 1

        found = await repo.get_by_natural_key(tenant, tool, _SIG)
        assert found is not None
        assert found.fix_summary == "配方A"

    @pytest.mark.asyncio
    async def test_record_case_idempotent_increment(self, repo_session: AsyncSession) -> None:
        """同自然键二次回填：单行 + 分类计数递增 + occurrence 守恒."""
        repo = PostgreSQLErrorCaseRepository()
        tenant, tool = uuid.uuid4(), uuid.uuid4()

        await repo.record_case(_make_case(tenant, tool, outcome="RECOVERED", fix_summary="旧"))
        await repo.record_case(_make_case(tenant, tool, outcome="MARKED_INFEASIBLE", recovered=0, infeasible=1))

        found = await repo.get_by_natural_key(tenant, tool, _SIG)
        assert found is not None
        assert found.recovered_count == 1
        assert found.infeasible_count == 1
        assert found.occurrence_count == 2
        assert found.fix_summary == "旧"  # 不可行回填不动配方

    @pytest.mark.asyncio
    async def test_record_case_category_first_write_freeze(self, repo_session: AsyncSession) -> None:
        """error_category 首写定格（R1-F10——与 InMemory 同款定向断言）：异 category
        二次回填后行上 category 保持首写值（重放占位 LLM_TRANSIENT 不翻转生产分类）."""
        repo = PostgreSQLErrorCaseRepository()
        tenant, tool = uuid.uuid4(), uuid.uuid4()

        await repo.record_case(_make_case(tenant, tool))  # 首写 SCHEMA_VIOLATION
        await repo.record_case(
            ErrorCase(
                tenant_id=tenant,
                tool_id=tool,
                error_signature=_SIG,
                error_category="LLM_TRANSIENT",
                stderr_excerpt="err",
                fix_summary="",
                outcome=FeedbackOutcome.RECOVERED,
                recovered_count=1,
                infeasible_count=0,
                occurrence_count=1,
                last_seen_at=datetime.now(UTC),
            )
        )

        found = await repo.get_by_natural_key(tenant, tool, _SIG)
        assert found is not None
        assert found.error_category == "SCHEMA_VIOLATION", "PG 侧 category 首写定格——后续回填不覆写"
        assert found.recovered_count == 2, "计数仍正常递增"

    @pytest.mark.asyncio
    async def test_record_case_after_unique_conflict_recovery(self, repo_session: AsyncSession) -> None:
        """UNIQUE 冲突后 record_case 容错（4-6 CR1-4：SAVEPOINT 保护 + 重读合并）.

        模拟并发对手路径：SAVEPOINT 内裸插同自然键触发 IntegrityError（对手已建行
        的等价形态）——SAVEPOINT 回滚后外层事务须保持健康，record_case 重读合并
        不崩溃且计数正确。AsyncSession 禁止同 session 协程并发（isce），故以
        冲突注入替代 gather 并发（等价验证容错路径）。
        """
        from sqlalchemy.exc import IntegrityError

        from src.infrastructure.storage.postgresql.models.error_case import ErrorCaseModel

        repo = PostgreSQLErrorCaseRepository()
        tenant, tool = uuid.uuid4(), uuid.uuid4()
        await repo.record_case(_make_case(tenant, tool, outcome="RECOVERED", fix_summary="配方"))

        # 冲突注入：SAVEPOINT 内裸插同自然键（绕过 record_case 的 select 前置）
        dup = ErrorCaseModel(
            case_id=uuid.uuid4(),
            tenant_id=tenant,
            tool_id=tool,
            error_signature=_SIG,
            error_category="SCHEMA_VIOLATION",
            outcome="RECOVERED",
            recovered_count=1,
            infeasible_count=0,
            occurrence_count=1,
            last_seen_at=datetime.now(UTC),
        )
        try:
            async with repo_session.begin_nested():
                repo_session.add(dup)
                await repo_session.flush()
            conflict_raised = False
        except IntegrityError:
            conflict_raised = True
        assert conflict_raised, "同自然键裸插应触发 UNIQUE 冲突"

        # 冲突后外层事务健康：record_case 正常增量合并
        merged = await repo.record_case(_make_case(tenant, tool, outcome="MARKED_INFEASIBLE", recovered=0, infeasible=1))
        assert merged.recovered_count == 1
        assert merged.infeasible_count == 1
        assert merged.occurrence_count == 2


# ============================================================================
# Task 6 循环 C：outbox 后台路径 fallback 独立 session 修复（R3-1 本批追加）
# ============================================================================


class TestOutboxFallbackIndependentSession:
    """后台/CLI 路径（无请求 session）reliable 事件经 fallback 独立 session 落库.

    隔离纪律（R2-6/陷阱 15）：fallback 走 session_context 独立写入即 commit——
    不挂 repo_session（否则 ContextVar 有值触发不了 RuntimeError 分支），并在
    try/finally 中按本测试自建 event_id 集合定向删除自建行（「只清理自己创建
    的资源」的合规例外——禁令针对 truncate 全表/误删他行）。
    """

    @pytest.mark.asyncio
    async def test_background_path_saves_via_fallback(
        self, db_engine: PostgreSQLManager, pg_available: bool, event_loop
    ) -> None:
        """无请求 session → RuntimeError 分支 → fallback 独立写入成功（现状静默丢失）."""
        import uuid as uuid_lib

        from src.domain.events.validation_feedback_events import ToolExecutionRecovered
        from src.infrastructure.messaging.outbox.outbox_repository import (
            PostgreSQLOutboxRepository,
        )
        from src.infrastructure.storage.postgresql.session_context import get_session

        if not pg_available:
            pytest.skip("PostgreSQL not available")
            return

        from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession

        def _factory() -> _AsyncSession:
            return _AsyncSession(db_engine.get_async_engine())

        event = ToolExecutionRecovered(
            execution_id=uuid_lib.uuid4(),
            tool_id=uuid_lib.uuid4(),
            tenant_id=uuid_lib.uuid4(),
            error_signature="a" * 64,
            enhanced_retry_count=1,
        )
        repo = PostgreSQLOutboxRepository(session_factory=_factory)
        try:
            # 未 set_session——get_session() 抛 RuntimeError → fallback 路径
            try:
                get_session()
                pytest.skip("ContextVar 意外有值（上层 fixture 泄漏）——无法验证 fallback 分支")
                return
            except RuntimeError:
                pass
            await repo.save(event)

            # 独立会话验证落库
            async def _verify() -> bool:
                from sqlalchemy import select

                from src.infrastructure.storage.postgresql.models import OutboxModel

                verify_session = _AsyncSession(db_engine.get_async_engine())
                try:
                    result = await verify_session.execute(select(OutboxModel).where(OutboxModel.event_id == event.event_id))
                    return result.scalar_one_or_none() is not None
                finally:
                    await verify_session.close()

            assert await _verify(), "fallback 独立写入应落库"
        finally:
            # 定向清理自建行（合规例外显式声明）
            async def _cleanup() -> None:
                from sqlalchemy import delete

                from src.infrastructure.storage.postgresql.models import OutboxModel

                cleanup_session = _AsyncSession(db_engine.get_async_engine())
                try:
                    await cleanup_session.execute(delete(OutboxModel).where(OutboxModel.event_id == event.event_id))
                    await cleanup_session.commit()
                finally:
                    await cleanup_session.close()

            await _cleanup()

    @pytest.mark.asyncio
    async def test_http_path_uses_request_session_unchanged(self, repo_session: AsyncSession) -> None:
        """HTTP 形态（有请求 session）：仍走请求 session 同事务——rollback 后无行
        （事务性原子性保持；「有请求 session」形态经 set_session fixture 模拟——
        SessionMiddleware 未接线前生产不可达，验证 fallback 分支语义）."""
        import uuid as uuid_lib

        from src.domain.events.validation_feedback_events import ToolExecutionRecovered
        from src.infrastructure.messaging.outbox.outbox_repository import (
            PostgreSQLOutboxRepository,
        )

        event = ToolExecutionRecovered(
            execution_id=uuid_lib.uuid4(),
            tool_id=uuid_lib.uuid4(),
            tenant_id=uuid_lib.uuid4(),
            error_signature="b" * 64,
            enhanced_retry_count=1,
        )
        repo = PostgreSQLOutboxRepository(session_factory=None)
        await repo.save(event)
        # 事务内 flush 可见（repo_session 隔离——rollback 由 fixture 收尾）
        from sqlalchemy import select

        from src.infrastructure.storage.postgresql.models import OutboxModel

        result = await repo_session.execute(select(OutboxModel).where(OutboxModel.event_id == event.event_id))
        assert result.scalar_one_or_none() is not None


class TestToolExecutionSaveFallbackIndependentSession:
    """ToolExecution save 后台路径 fallback（技术债清偿 A 类——outbox 同构）.

    _persist_execution 失败态持久化在无请求 session 的后台路径此前 RuntimeError
    被引擎 best-effort 吞掉（聚合行丢失）——经注入 session_factory 走独立会话
    写入后落库。隔离纪律同 outbox fallback 用例（R2-6/陷阱 15）。
    """

    @pytest.mark.asyncio
    async def test_background_path_save_via_fallback(
        self, db_engine: PostgreSQLManager, pg_available: bool, event_loop
    ) -> None:
        """无请求 session → RuntimeError 分支 → fallback 独立写入 FAILED 聚合行."""
        import uuid as uuid_lib
        from datetime import UTC, datetime

        from src.domain.entities.tool_execution import ToolExecution, ToolExecutionState
        from src.infrastructure.storage.postgresql.repository.tool_execution_repository import (
            PostgreSQLToolExecutionRepository,
        )
        from src.infrastructure.storage.postgresql.session_context import get_session

        if not pg_available:
            pytest.skip("PostgreSQL not available")
            return

        from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession

        def _factory() -> _AsyncSession:
            return _AsyncSession(db_engine.get_async_engine())

        execution = ToolExecution(
            execution_id=uuid_lib.uuid4(),
            tenant_id=uuid_lib.uuid4(),
            tool_id=uuid_lib.uuid4(),
            tool_version="1.0.0",
            state=ToolExecutionState.FAILED,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        repo = PostgreSQLToolExecutionRepository(session_factory=_factory)
        try:
            try:
                get_session()
                pytest.skip("ContextVar 意外有值（上层 fixture 泄漏）——无法验证 fallback 分支")
                return
            except RuntimeError:
                pass
            saved = await repo.save(execution)
            assert saved.execution_id == execution.execution_id, "fallback 写入应返回保存后实体"

            async def _verify() -> bool:
                from sqlalchemy import select

                from src.infrastructure.storage.postgresql.models.tool_execution import (
                    ToolExecutionModel,
                )

                verify_session = _AsyncSession(db_engine.get_async_engine())
                try:
                    result = await verify_session.execute(
                        select(ToolExecutionModel).where(ToolExecutionModel.execution_id == execution.execution_id)
                    )
                    return result.scalar_one_or_none() is not None
                finally:
                    await verify_session.close()

            assert await _verify(), "fallback 独立写入应落库"
        finally:

            async def _cleanup() -> None:
                from sqlalchemy import delete

                from src.infrastructure.storage.postgresql.models.tool_execution import (
                    ToolExecutionModel,
                )

                cleanup_session = _AsyncSession(db_engine.get_async_engine())
                try:
                    await cleanup_session.execute(
                        delete(ToolExecutionModel).where(ToolExecutionModel.execution_id == execution.execution_id)
                    )
                    await cleanup_session.commit()
                finally:
                    await cleanup_session.close()

            await _cleanup()

    @pytest.mark.asyncio
    async def test_no_factory_no_session_keeps_runtime_error(self, pg_available: bool, event_loop) -> None:
        """未注入 session_factory 且无请求 session → RuntimeError 显式失败
        （与 outbox 同款语义——不静默丢失）。"""
        from src.infrastructure.storage.postgresql.repository.tool_execution_repository import (
            PostgreSQLToolExecutionRepository,
        )
        from src.infrastructure.storage.postgresql.session_context import get_session

        if not pg_available:
            pytest.skip("PostgreSQL not available")
            return

        try:
            get_session()
            pytest.skip("ContextVar 意外有值——无法验证无 session 分支")
            return
        except RuntimeError:
            pass

        import uuid as uuid_lib
        from datetime import UTC, datetime

        from src.domain.entities.tool_execution import ToolExecution, ToolExecutionState

        repo = PostgreSQLToolExecutionRepository()  # 无 factory
        now = datetime.now(UTC)
        execution = ToolExecution(
            execution_id=uuid_lib.uuid4(),
            tenant_id=uuid_lib.uuid4(),
            tool_id=uuid_lib.uuid4(),
            tool_version="1.0.0",
            state=ToolExecutionState.FAILED,
            started_at=now,
            completed_at=now,
        )
        with pytest.raises(RuntimeError):
            await repo.save(execution)
