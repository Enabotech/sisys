"""Story 6-8 - 高管简化视图集成测试（真实四源链聚合）.

真实服务 Schema 隔离子模式（6-x 集成双子模式选型：真实服务面——四源全真实零 mock）：
Redis 快照三键族（latest/CP 族/恢复记录）+ PG 报告/审计行（A 面 set_session 回滚式 /
C 面 commit+定向 DELETE 三分面——R2-F3）。含 get_latest_by_plan 首消费激活验证
（报告段 report_id str 化与预置一致——Story 6-8 终结其零消费方状态）。

性能三段口径差声明（OD-7——集成 docstring 落档）：
    ① 视图加载 P95<500ms = build_executive_view 服务面窗口（五读串行：Redis 点查×11
       [latest 1 + list_checkpoints 内部 9 + 审批段恢复记录直读 1——R1-F10 口径] +
       PG 单行查 + audit 窗口查）；audit search 的 total 全行取回实现形态在 MVP 数据量级
       （时间窗内百行级）远小于门禁——审计量增长至万行级时 total 全行取回成为热点，
       分组计数端口立项锚 Epic 7/21；
    ② 并发 20 = 单一数据源 plan_id×20 路并发读（gather+服务无状态+两两相等断言；
       对照排除集六键 {generated_at, window_start, window_end, total_events,
       recent_events, last_event_at} 不入对照——R1-F5/R2-F4；「20 个独立 plan」写面
       变体不采——构造成本与读面并发安全证明目标不成比例，6-5a OD-8 同构）；
    ③ 「信息密度达标（Lighthouse 评分≥90）」与「状态指示器实时更新」为前端指标后端
       不定义（epics L2415 自注原文——Web 面指标归 Epic 21 Story 21.1 届时验收）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_executive_view.py -v
"""

from __future__ import annotations

import asyncio
import dataclasses
import math
import time
import uuid as uuid_module
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.database,
    pytest.mark.redis,
    pytest.mark.qdrant,  # 装配链依赖（checkpoint_service→strategic_archive_service→l3）
    pytest.mark.xdist_group("blm-planning-perf"),
]

# ===================================================================
# 期望常量（模块级独立构造——性能采样纪律）
# ===================================================================

_P95_LIMIT_MS: float = 500.0
_P95_PERCENTILE: float = 0.95
_SAMPLE_ROUNDS: int = 20
_WARMUP_ROUNDS: int = 2
_CONCURRENCY: int = 20
_WINDOW_DAYS: int = 7

_STEP_SEQUENCE: tuple[str, ...] = (
    "performance_gap",
    "market_insight_trend",
    "market_insight_competition",
    "market_insight_strategy",
    "market_insight_org",
    "market_insight_risk",
    "market_insight_execution",
    "market_insight_synthesis",
)

_EXCLUDED_TOP_KEYS: tuple[str, ...] = ("generated_at",)
_EXCLUDED_AUDIT_KEYS: tuple[str, ...] = (
    "window_start",
    "window_end",
    "total_events",
    "recent_events",
    "last_event_at",
)


# ===================================================================
# 基建 fixture（module event_loop + autouse 双清 + 服务探测）
# ===================================================================


@pytest.fixture(scope="module")
def event_loop() -> Any:
    """模块级事件循环（6-x 集成惯例——场景间共享 loop，资源 per-test 隔离）."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _fresh_resolver_per_test() -> Any:
    """每测试驱逐 resolver 缓存（SINGLETON/SCOPED——跨 loop 防线，6-5b/6-7 同款）."""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()
    yield resolver
    resolver.clear_singleton()
    resolver.clear_scoped()


@pytest.fixture(scope="module", autouse=True)
def _require_services(event_loop: Any) -> None:
    """三服务可达探测（不可达 pytest.skip 动态跳过——禁 @pytest.mark.skip 写死）."""
    from tests.acceptance.test_acceptance_executive_view import (
        _probe_pg_available,
        _probe_qdrant_available,
        _probe_redis_available,
    )

    _probe_pg_available()
    _probe_redis_available()
    _probe_qdrant_available()


# ===================================================================
# 服务构建与预置工厂
# ===================================================================


def _build_service() -> Any:
    """构建视图服务（四依赖 resolve 既有注册名——OD-11）."""
    from src.application.services.executive_view_service import ExecutiveViewService
    from src.domain.ports.resolver import resolve

    return ExecutiveViewService(
        snapshot_repository=resolve("snapshot_repository"),
        checkpoint_service=resolve("checkpoint_service"),
        report_repository=resolve("report_repository"),
        audit_repository=resolve("audit_repo"),
    )


def _make_latest_state(plan_id: str, *, completed: int, degraded_steps: list[str]) -> dict[str, Any]:
    """latest 快照 state_data 七键（与验收预置工厂同构）."""
    now = datetime.now(UTC)
    done = list(_STEP_SEQUENCE[:completed])
    timeline = [
        {
            "step": step,
            "started_at": (now - timedelta(minutes=10)).isoformat(),
            "completed_at": (now - timedelta(minutes=9)).isoformat(),
            "status": "completed",
            "summary_excerpt": f"{step} 摘要（集成预置）",
            "degraded": step in degraded_steps,
        }
        for step in done
    ]
    return {
        "plan_id": plan_id,
        "phase": "market_insight",
        "current_step": done[-1] if done else "performance_gap",
        "completed_steps": completed,
        "total_steps": 8,
        "degraded_steps": list(degraded_steps),
        "timeline": timeline,
    }


def _make_cp_snapshot(plan_id: str, cp_no: str, *, completed: bool) -> Any:
    """Checkpoint 快照直写（十键 state_data——R1-F11 直写通道裁定）."""
    from src.application.ports.checkpoint import CHECKPOINT_SESSION_PREFIX
    from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

    step = _STEP_SEQUENCE[0]
    return CheckpointSnapshot(
        session_id=f"{CHECKPOINT_SESSION_PREFIX}{plan_id}:{cp_no}",
        stage_id=step,
        state_data={
            "plan_id": plan_id,
            "step": step,
            "summary": f"{cp_no} 摘要（集成预置）",
            "structured_output": {"preset": True},
            "degraded": False,
            "degrade_reason": "",
            "completed_steps": [],
            "stage_id": step,
            "completed": completed,
            "created_via": "use_case",
        },
    )


def _make_recovery_snapshot(plan_id: str, *, mode: str = "replay", confirmed_by: str = "cfo-integration") -> Any:
    """恢复记录 12 键直写（与 checkpoint_service.py:693-714 构造键面同源）."""
    from src.application.ports.checkpoint import CHECKPOINT_RECOVERY_SESSION_PREFIX
    from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

    now = datetime.now(UTC)
    return CheckpointSnapshot(
        session_id=f"{CHECKPOINT_RECOVERY_SESSION_PREFIX}{plan_id}",
        stage_id="recovery_record",
        state_data={
            "plan_id": plan_id,
            "checkpoint_no": "CP-1",
            "recovery_mode": mode,
            "corrected": False,
            "correction": {},
            "affected_checkpoints": [],
            "pending_sync_checkpoints": [],
            "invalidated_checkpoints": [],
            "confirmed_by": confirmed_by,
            "recovered_at": now.isoformat(),
            "execution_ms": 12.5,
            "created_via": "cli",
        },
        timestamp=now,
    )


def _make_report(plan_id: str, *, degraded_sections: int = 0) -> Any:
    """报告实体（真实构造守卫通道）."""
    from src.domain.entities.strategic_report import ReportType, StrategicReport

    return StrategicReport(
        report_id=uuid_module.uuid4(),
        plan_id=plan_id,
        report_type=ReportType.MARKDOWN,
        file_path=f"/tmp/sisys-reports/{plan_id}.md",
        section_count=11,
        degraded_section_count=degraded_sections,
        generation_ms=1234,
        created_at=datetime.now(UTC),
    )


def _make_audit_rows(n_window: int) -> list[dict[str, Any]]:
    """审计行（必填双键+递减微秒偏移去并列——R1-F1/R2-F1）."""
    now = datetime.now(UTC)
    return [
        {
            "log_id": str(uuid_module.uuid4()),
            "timestamp": (now - timedelta(microseconds=100 * i)).isoformat(),
            "actor": f"integration-actor-{i}",
            "action_type": f"exec-view:integration-{i % 3}",
            "target_resource": f"integration-target-{i}",
        }
        for i in range(1, n_window + 1)
    ]


async def _preset_redis(ctx: dict[str, Any], plan_id: str, *, completed: int, degraded_steps: list[str]) -> None:
    """Redis 三键族预置（latest+CP-1/CP-2+恢复记录）."""
    from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX
    from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
    from src.domain.ports.resolver import resolve

    repo = resolve("snapshot_repository")
    snapshots = [
        CheckpointSnapshot(
            session_id=f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}",
            state_data=_make_latest_state(plan_id, completed=completed, degraded_steps=degraded_steps),
        ),
        _make_cp_snapshot(plan_id, "CP-1", completed=True),
        _make_cp_snapshot(plan_id, "CP-2", completed=True),
        _make_recovery_snapshot(plan_id),
    ]
    for snapshot in snapshots:
        await repo.save(snapshot)
    ctx["_snapshot_keys"].extend(s.session_id for s in snapshots)


async def _teardown_redis(ctx: dict[str, Any]) -> None:
    """Redis 三键族定向 DEL（delete 不存在键 no-op——uuid plan_id 天然隔离）."""
    from src.domain.ports.resolver import resolve

    repo = resolve("snapshot_repository")
    for session_id in ctx["_snapshot_keys"]:
        try:
            await repo.delete(session_id)
        except Exception as error:  # teardown 容错
            print(f"[teardown:redis] 删除异常（容错）: {session_id}: {error}")


async def _teardown_bc_rows(ctx: dict[str, Any]) -> None:
    """C 面 PG 定向 DELETE（行数断言防静默 0 行假绿——R2-F3）."""
    if not (ctx["_audit_log_ids"] or ctx["_report_ids"]):
        return
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from tests.environments import get_test_env

    env = get_test_env()
    engine = create_async_engine(
        f"postgresql+asyncpg://{env.postgres.username}:{env.postgres.password}"
        f"@{env.postgres.host}:{env.postgres.port}/{env.postgres.database}"
    )
    try:
        async with engine.begin() as conn:
            if ctx["_audit_log_ids"]:
                result = await conn.execute(
                    sa.text("DELETE FROM audit_log WHERE log_id = ANY(:ids)"),
                    {"ids": list(ctx["_audit_log_ids"])},
                )
                assert result.rowcount == len(ctx["_audit_log_ids"]), (
                    f"audit_log DELETE 行数 {result.rowcount} != 预置 {len(ctx['_audit_log_ids'])}"
                )
            if ctx["_report_ids"]:
                result = await conn.execute(
                    sa.text("DELETE FROM strategic_reports WHERE report_id = ANY(:ids)"),
                    {"ids": list(ctx["_report_ids"])},
                )
                assert result.rowcount == len(ctx["_report_ids"]), (
                    f"strategic_reports DELETE 行数 {result.rowcount} != 预置 {len(ctx['_report_ids'])}"
                )
    finally:
        await engine.dispose()


# ===================================================================
# 场景①②：A 面全数据 round-trip 与空 plan 幂等读（set_session 回滚式）
# ===================================================================


@pytest.fixture
def repo_session(event_loop: Any) -> Any:
    """A 面真实 PG 会话（savepoint 事务回滚隔离——strategic_archive repo_session 样板）."""
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
    from src.infrastructure.storage.postgresql.session_context import reset_session, set_session
    from tests.environments import get_test_env

    env = get_test_env()
    manager = PostgreSQLManager(
        PostgreSQLConfig(
            host=env.postgres.host,
            port=env.postgres.port,
            database=env.postgres.database,
            username=env.postgres.username,
            password=env.postgres.password,
        )
    )
    session = AsyncSession(manager.get_async_engine(), expire_on_commit=False)

    async def _begin() -> None:
        await session.begin()

    event_loop.run_until_complete(_begin())
    token = set_session(session)
    yield session
    reset_session(token)

    async def _finalize() -> None:
        await session.rollback()
        await session.close()
        await manager.get_async_engine().dispose()

    event_loop.run_until_complete(_finalize())


async def _query_window_total() -> int:
    """全局窗 total 基线查询（差值断言锚——R1-F6）."""
    from src.domain.ports.audit_repository import AuditSearchCriteria
    from src.domain.ports.resolver import resolve

    now = datetime.now(UTC)
    result = await resolve("audit_repo").search(
        AuditSearchCriteria(start_time=now - timedelta(days=_WINDOW_DAYS), end_time=now, limit=1)
    )
    return int(result.total)


async def test_scenario_1_full_data_round_trip(repo_session: Any) -> None:
    """场景①：全数据四段 round-trip（A 面——真实链值级+get_latest_by_plan 首消费激活+差值）."""
    from src.domain.ports.resolver import resolve

    plan_id = str(uuid_module.uuid4())
    report = _make_report(plan_id, degraded_sections=2)
    audit_rows = _make_audit_rows(6)
    ctx: dict[str, Any] = {"_snapshot_keys": [], "_audit_log_ids": [], "_report_ids": []}
    try:
        await _preset_redis(ctx, plan_id, completed=3, degraded_steps=[_STEP_SEQUENCE[0]])
        baseline = await _query_window_total()
        for row in audit_rows:
            await resolve("audit_repo").save(row)
            ctx["_audit_log_ids"].append(row["log_id"])
        saved_report = await resolve("report_repository").save(report)
        ctx["_report_ids"].append(str(saved_report.report_id))

        view = await _build_service().build_executive_view(plan_id=plan_id)

        # 四段值级断言（真实链 round-trip）
        assert view.plan_id == plan_id
        assert view.build_degraded is False
        planning = view.planning
        assert planning.available is True
        assert planning.completed_steps == 3
        assert planning.total_steps == 8
        assert planning.progress_percent == 37
        assert planning.degraded_step_count == 1
        approval = view.approval
        assert approval.available is True
        assert approval.total_checkpoints == 2
        assert approval.completed_count == 2
        assert approval.in_sync_count == 2
        assert approval.last_recovery_mode == "replay"
        assert approval.last_recovery_confirmed_by == "cfo-integration"
        report_section = view.report
        assert report_section.available is True
        # get_latest_by_plan 首消费激活断言（report_id str 化与预置一致——本 Story 终结零消费方状态）
        assert report_section.report_id == str(saved_report.report_id)
        assert report_section.generated_at == saved_report.created_at.isoformat()
        assert report_section.section_count == 11
        assert report_section.degraded_section_count == 2
        audit_section = view.audit
        assert audit_section.degraded is False
        assert audit_section.total_events - baseline == 6, "预置 6 窗内行差值（全局窗背景行不进断言）"
        assert audit_section.window_days == _WINDOW_DAYS
        assert audit_section.recent_events[0].actor == "integration-actor-1", "递减微秒占头（同组串行前提）"
    finally:
        await _teardown_redis(ctx)


async def test_scenario_2_empty_plan_idempotent(repo_session: Any) -> None:
    """场景②：空数据 plan 幂等读（A 面——8 键+build_degraded False+health AMBER+审计差值==0）."""
    ctx: dict[str, Any] = {"_snapshot_keys": [], "_audit_log_ids": [], "_report_ids": []}
    try:
        baseline = await _query_window_total()
        empty_plan = str(uuid_module.uuid4())

        view = await _build_service().build_executive_view(plan_id=empty_plan)

        assert view.plan_id == empty_plan
        assert view.build_degraded is False, "「没有数据」非「拿不到数据」"
        assert view.health.value == "amber"
        assert view.planning.available is False
        assert view.approval.available is False
        assert view.report.available is False
        assert view.audit.degraded is False
        assert view.audit.total_events - baseline == 0, "零新增差值（绝对空断言不可写——R1-F6）"
    finally:
        await _teardown_redis(ctx)


# ===================================================================
# 场景③④：C 面性能采样与并发（禁 set_session——每路 fallback 独立会话）
# ===================================================================


async def _preset_commit_mode(ctx: dict[str, Any], plan_id: str) -> None:
    """C 面预置（clear_session → impl fallback 独立会话 commit 式——R2-F3）."""
    from src.domain.ports.resolver import resolve
    from src.infrastructure.storage.postgresql.session_context import clear_session

    clear_session()
    await _preset_redis(ctx, plan_id, completed=3, degraded_steps=[_STEP_SEQUENCE[0]])
    report = _make_report(plan_id, degraded_sections=2)
    saved = await resolve("report_repository").save(report)
    ctx["_report_ids"].append(str(saved.report_id))
    for row in _make_audit_rows(6):
        await resolve("audit_repo").save(row)
        ctx["_audit_log_ids"].append(row["log_id"])


async def test_scenario_3_performance_p95() -> None:
    """场景③：20 轮采样 P95<500ms（C 面——性能口径含 fallback 连接开销更保守真实）."""
    plan_id = str(uuid_module.uuid4())
    ctx: dict[str, Any] = {"_snapshot_keys": [], "_audit_log_ids": [], "_report_ids": []}
    try:
        await _preset_commit_mode(ctx, plan_id)
        service = _build_service()
        for _ in range(_WARMUP_ROUNDS):  # 预热含首次真实 load（连接池建立——R8-F5 注记继承）
            await service.build_executive_view(plan_id=plan_id)
        durations: list[float] = []
        for _ in range(_SAMPLE_ROUNDS):
            start = time.perf_counter()
            await service.build_executive_view(plan_id=plan_id)
            durations.append((time.perf_counter() - start) * 1000.0)

        p95 = sorted(durations)[math.ceil(_P95_PERCENTILE * len(durations)) - 1]
        assert p95 < _P95_LIMIT_MS, f"P95 {p95:.1f}ms 超门禁 {_P95_LIMIT_MS}ms（全量: {sorted(durations)}）"
    finally:
        await _teardown_redis(ctx)
        await _teardown_bc_rows(ctx)


async def test_scenario_4_concurrent_20_reads() -> None:
    """场景④：20 路并发读全成功+排除集六键剔除后两两相等（C 面——服务无状态证明）."""
    plan_id = str(uuid_module.uuid4())
    ctx: dict[str, Any] = {"_snapshot_keys": [], "_audit_log_ids": [], "_report_ids": []}
    try:
        await _preset_commit_mode(ctx, plan_id)
        service = _build_service()

        views = list(await asyncio.gather(*[service.build_executive_view(plan_id=plan_id) for _ in range(_CONCURRENCY)]))

        assert len(views) == _CONCURRENCY
        assert all(view is not None for view in views), "20 路应全部成功不抛（pool 15<20 等待制——R3 推演）"

        def _freeze(value: Any) -> Any:
            if isinstance(value, dict):
                return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
            if isinstance(value, (list, tuple)):
                return tuple(_freeze(item) for item in value)
            return value

        def _serialize(view: Any) -> Any:
            data = dataclasses.asdict(view)
            for key in _EXCLUDED_TOP_KEYS:
                data.pop(key, None)
            for key in _EXCLUDED_AUDIT_KEYS:
                data["audit"].pop(key, None)
            return _freeze(data)

        serialized = {_serialize(view) for view in views}
        assert len(serialized) == 1, f"剔除六键后应两两相等，实际 {len(serialized)} 种形态"
    finally:
        await _teardown_redis(ctx)
        await _teardown_bc_rows(ctx)
