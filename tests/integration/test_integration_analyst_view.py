"""Story 6-9 - 分析师视图集成测试（真实三源链聚合）.

真实服务 Schema 隔离子模式（6-x 集成双子模式选型：真实服务面——三源全真实零 mock）：
工具箱静态真源（TOOLS.md 打包内存读）+ Redis latest 快照直写 + PG 归档行/documents
行直写 + Qdrant 点直写（归档族预置复用验收 helper 形态——collection 参数注入独立
集成 collection）。

性能三段口径差声明（OD-7——集成 docstring 落档）：
    ① 视图加载 P95<800ms = build_analyst_view 服务面窗口（三读串行：
       list_active_skills 内存遍历微秒级 + snapshot load Redis 单键点查 +
       build_trace_tree 全树[query_archive PG 归档查+get_point/find Qdrant 点查——
       三读最重]）；trace_tree 全树成本随归档量增长——万行级归档时该段成为热点，
       分组统计端口立项锚 Epic 7/21；
    ② 并发 20 = 单一数据源 plan_id×20 路并发读（asyncio.gather+服务无状态+两两
       相等断言；对照排除集单键 {generated_at}——toolbox 静态真源恒稳/progress
       单键快照读恒稳/traceability 段不透传树 generated_at[OD-6 联动]，排除集
       最小化是本 Story VO 设计的直接收益；asdict 序列化剔除对照；禁 set_session
       ——每路独立会话天然 per-task 隔离，6-8 R2-F3 C 面纪律直系）；
    ③ 「快捷键响应<100ms」为前端指标后端不定义（epics L2457 原文——键盘事件响应
       归 Epic 21 Story 21.9 届时验收）；「溯源跳转<300ms」已由 6-7 跳转载荷组装
       承载——本 Story 溯源段是统计摘要面非跳转执行面，跳转执行归 trace-tree
       既有命令。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_analyst_view.py -v
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
    pytest.mark.qdrant,  # 装配链依赖（traceability_tree_service→l3_vector→qdrant）
    pytest.mark.xdist_group("blm-planning-perf"),
]

# ===================================================================
# 期望常量（模块级独立构造——性能采样纪律）
# ===================================================================

_P95_LIMIT_MS: float = 800.0
_P95_PERCENTILE: float = 0.95
_SAMPLE_ROUNDS: int = 20
_WARMUP_ROUNDS: int = 2
_CONCURRENCY: int = 20

# 并发对照排除集单键（OD-7 ②/OD-6 联动——段不透传树 generated_at 故排除集最小化）
_EXCLUDED_TOP_KEYS: tuple[str, ...] = ("generated_at",)

# 8 步全序列（写侧实值三形态——R1-F4；与 BLM_TOTAL_STEPS=8 单源对齐）
_STEP_SEQUENCE: tuple[str, ...] = (
    "performance_gap",
    "trend",
    "market_customer",
    "competition",
    "self",
    "opportunity",
    "opportunity_gap",
    "market_insight_synthesis",
)

# 五战略分类期望配比（Story 4.1 AC-2 钦定）
_EXPECTED_CATEGORY_COUNTS: dict[str, int] = {
    "environment_analysis": 3,
    "competitive_analysis": 3,
    "strategic_selection": 6,
    "business_model": 3,
    "execution_management": 8,
}

# 独立集成 collection（uuid 前缀——与验收 collection 互不污染）
_COLLECTION: str = f"analyst-view-integration-{uuid_module.uuid4().hex[:8]}"

_VECTOR_DIM: int = 1024

# ===================================================================
# 夹具（module event_loop + 每测试清 resolver + 服务探测）
# ===================================================================


@pytest.fixture(scope="module")
def event_loop() -> Any:
    """模块级事件循环（6-x 集成惯例——场景间共享 loop，资源 per-test 隔离）."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _fresh_resolver_per_test(monkeypatch: pytest.MonkeyPatch) -> Any:
    """每测试驱逐 resolver 缓存（SINGLETON/SCOPED——跨 loop 防线，6-5b/6-7/6-8 同款）.

    collection 桥接 setenv 同点承载（R1-F6）：monkeypatch.setenv 在 fixture setup
    注入+测试退出自动恢复 env——与后置双清同点原子收尾（模块结束后同 worker 后续
    模块既无残留 env 也无持旧 collection 的缓存实例——组合根 lambda 在 resolve 时刻
    读 env，故 env 只需在 _build_service 前就位，per-test 生命周期覆盖全程）.
    """
    from src.domain.ports.resolver import get_resolver

    monkeypatch.setenv("BLM_SEARCH_COLLECTION", _COLLECTION)
    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()
    yield resolver
    resolver.clear_singleton()
    resolver.clear_scoped()


@pytest.fixture(scope="module", autouse=True)
def _require_services(event_loop: Any) -> None:
    """三服务可达探测（不可达 pytest.skip 动态跳过——禁 @pytest.mark.skip 写死）."""
    from tests.acceptance.test_acceptance_analyst_view import (
        _ensure_collection,
        _probe_pg_available,
        _probe_qdrant_available,
        _probe_redis_available,
    )

    _probe_pg_available()
    _probe_redis_available()
    _probe_qdrant_available()
    event_loop.run_until_complete(_ensure_collection(_COLLECTION))


# ===================================================================
# 预置/清理通道（归档族 helper 复用验收形态+独立 collection；快照直写+定向 DEL）
# ===================================================================


def _build_service() -> Any:
    """构建分析师视图服务（三依赖 resolve 既有注册名——OD-11）.

    collection 桥接 setenv 已上移 `_fresh_resolver_per_test` fixture（R1-F6：
    per-test 注入+自动恢复——禁 os.environ 直写残留毒化同 worker 后续模块）.
    """
    from src.application.services.analyst_view_service import AnalystViewService
    from src.domain.ports.resolver import resolve

    return AnalystViewService(
        skill_selector=resolve("skill_selector"),
        snapshot_repository=resolve("snapshot_repository"),
        traceability_tree_service=resolve("traceability_tree_service"),
    )


async def _preset_full_archive_family(ctx: dict[str, Any], plan_id: str) -> None:
    """归档族预置（钦定 2 stage×3 chunk 实例判别计数面错接——R3-F4+jump_ready 混合）.

    复用验收 _archive_row/_spec_chunk helper（归档行纯 PG 无 collection 依赖）；
    Qdrant/documents 预置经 collection 参数注入独立集成 collection。
    """
    from tests.acceptance.test_acceptance_analyst_view import (
        _archive_row,
        _preset_qdrant_points_and_pg_rows,
        _spec_chunk,
    )

    document_ids = {
        "chunk-it-a": str(uuid_module.uuid4()),
        "chunk-it-b": str(uuid_module.uuid4()),
        "chunk-it-c": str(uuid_module.uuid4()),
    }
    await _archive_row(ctx, plan_id, stage="performance_gap", evidence_refs=("chunk-it-a",))
    await _archive_row(ctx, plan_id, stage="market_insight_trend", evidence_refs=("chunk-it-b", "chunk-it-c"))
    await _archive_row(ctx, plan_id, stage="market_insight_synthesis", evidence_refs=())
    ctx["_chunk_specs"].append(_spec_chunk("chunk-it-a", document_id=document_ids["chunk-it-a"], page_start=3, page_end=4))
    ctx["_chunk_specs"].append(_spec_chunk("chunk-it-b", document_id=document_ids["chunk-it-b"], page_start=5, page_end=6))
    ctx["_chunk_specs"].append(
        _spec_chunk("chunk-it-c", document_id=document_ids["chunk-it-c"], page_start=7, page_end=8, pg_chunks_include=False)
    )
    await _preset_qdrant_points_and_pg_rows(ctx, collection=_COLLECTION)


async def _preset_snapshot(plan_id: str) -> None:
    """Redis latest 快照直写（3/8 完成+1 降级——progress_percent=37 整数口径锚）."""
    from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX
    from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
    from src.domain.ports.resolver import resolve

    base = datetime.now(UTC)
    timeline = [
        {
            "step": step,
            "started_at": (base - timedelta(seconds=8 - index)).isoformat(),
            "completed_at": (base - timedelta(seconds=8 - index - 1)).isoformat(),
            "status": "completed",
            "summary_excerpt": f"步骤摘要（{step}）",
            "degraded": step == "performance_gap",
        }
        for index, step in enumerate(_STEP_SEQUENCE[:3])
    ]
    snapshot = CheckpointSnapshot(
        session_id=f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}",
        state_data={
            "plan_id": plan_id,
            "phase": "market_insight",
            "current_step": _STEP_SEQUENCE[2],
            "completed_steps": 3,
            "total_steps": 8,
            "degraded_steps": [_STEP_SEQUENCE[0]],
            "timeline": timeline,
        },
    )
    await resolve("snapshot_repository").save(snapshot)


def _make_ctx() -> dict[str, Any]:
    """场景级 context dict（teardown 清单登记——集成面无 A 面恒 commit 式）."""
    return {"_a_mode": False, "_plan_ids": [], "_chunk_specs": [], "_document_ids": [], "_snapshot_keys": []}


async def _teardown_assets(ctx: dict[str, Any]) -> None:
    """teardown：Redis 快照 DEL+归档行/documents 定向 DELETE（行数断言）+collection 整删."""
    from src.domain.ports.resolver import resolve

    try:
        repo = resolve("snapshot_repository")
        for session_id in ctx["_snapshot_keys"]:
            try:
                await repo.delete(session_id)
            except Exception as error:
                print(f"[teardown:redis] 删除异常（容错）: {session_id}: {error}")
    except Exception as error:
        print(f"[teardown:redis] 仓储不可达（容错）: {error}")
    try:
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
                if ctx["_plan_ids"]:
                    result = await conn.execute(
                        sa.text("DELETE FROM strategic_archives WHERE plan_id = ANY(:ids)"),
                        {"ids": list(ctx["_plan_ids"])},
                    )
                    assert result.rowcount == len(ctx["_plan_ids"]), (
                        f"strategic_archives DELETE 行数 {result.rowcount} != 预置 {len(ctx['_plan_ids'])}"
                    )
                if ctx["_document_ids"]:
                    result = await conn.execute(
                        sa.text("DELETE FROM documents WHERE id = ANY(:ids)"),
                        {"ids": list(ctx["_document_ids"])},
                    )
                    assert result.rowcount == len(ctx["_document_ids"]), (
                        f"documents DELETE 行数 {result.rowcount} != 预置 {len(ctx['_document_ids'])}"
                    )
        finally:
            await engine.dispose()
    except AssertionError:
        raise
    except Exception as error:
        print(f"[teardown:pg] 定向 DELETE 异常（容错）: {error}")
    try:
        from qdrant_client import AsyncQdrantClient

        from tests.environments import get_test_env

        env = get_test_env()
        client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
        try:
            await client.delete_collection(collection_name=_COLLECTION)
        finally:
            await client.close()
    except Exception as error:
        print(f"[teardown:qdrant] 清理异常（容错）: {error}")


async def _preset_full_plan(ctx: dict[str, Any], plan_id: str) -> None:
    """全数据预置（归档族+快照——commit 式通道：clear_session 后 fallback 独立会话）.

    每场景幂等 ensure collection（前一场景 teardown 整删后重建——collection 是
    场景级生命周期非模块级）。
    """
    from src.infrastructure.storage.postgresql.session_context import clear_session
    from tests.acceptance.test_acceptance_analyst_view import _ensure_collection

    await _ensure_collection(_COLLECTION)
    clear_session()
    await _preset_full_archive_family(ctx, plan_id)
    await _preset_snapshot(plan_id)
    ctx["_snapshot_keys"].append(f"blm-planning-{plan_id}")


# ===================================================================
# 场景①②：真实链三段聚合 round-trip + 空 plan 幂等读
# ===================================================================


async def test_scenario_1_full_data_round_trip() -> None:
    """场景①：全数据三段 round-trip（真实三源——23 工具+配比 3/3/6/3/8+阶段派生+树统计）."""
    from src.application.ports.analyst_view import PhaseStatus
    from src.application.skills.skill_manifest import get_all_slugs

    plan_id = str(uuid_module.uuid4())
    ctx = _make_ctx()
    try:
        await _preset_full_plan(ctx, plan_id)
        service = _build_service()
        view = await service.build_analyst_view(plan_id=plan_id)

        # 工具箱段：真实静态真源（23 工具+全 slug 序+五分类配比+和恒等式）
        assert view.toolbox.total_tools == 23
        assert tuple(tool.slug for tool in view.toolbox.tools) == tuple(get_all_slugs())
        actual_counts = {category.category: category.tool_count for category in view.toolbox.categories}
        assert actual_counts == _EXPECTED_CATEGORY_COUNTS
        assert sum(category.tool_count for category in view.toolbox.categories) == 23

        # 进度段：真实快照（3/8 直读+37% 整数+阶段派生 completed/in_progress 2/7+后四 not_started）
        assert view.progress.completed_steps == 3
        assert view.progress.total_steps == 8
        assert view.progress.progress_percent == 37
        assert view.progress.degraded_step_count == 1
        statuses = [stage.status for stage in view.progress.stages]
        assert statuses == [
            PhaseStatus.COMPLETED,
            PhaseStatus.IN_PROGRESS,
            PhaseStatus.NOT_STARTED,
            PhaseStatus.NOT_STARTED,
            PhaseStatus.NOT_STARTED,
            PhaseStatus.NOT_STARTED,
        ]
        assert view.progress.stages[1].step_completed == 2

        # 溯源段：真实归档族（2 stage×3 chunk 实例判别+jump_ready 混合 2+树顶层键透传）
        assert view.traceability.stage_count == 2
        assert view.traceability.chunk_count == 3
        assert view.traceability.document_count == 3
        assert view.traceability.jump_ready_count == 2
        assert view.traceability.degraded_stage_count == 0
        assert view.traceability.tree_build_degraded is False
        assert view.build_degraded is False
        assert view.plan_id == plan_id
    finally:
        await _teardown_assets(ctx)


async def test_scenario_2_empty_plan_toolbox_integrity() -> None:
    """场景②：空 plan 幂等读（工具箱段完整 23——静态真源正交性断言）."""
    from src.application.ports.analyst_view import PhaseStatus

    plan_id = str(uuid_module.uuid4())
    ctx = _make_ctx()
    try:
        service = _build_service()
        view = await service.build_analyst_view(plan_id=plan_id)

        assert view.build_degraded is False
        assert view.toolbox.total_tools == 23  # 三段中唯一恒数据段（与 plan 正交）
        assert len(view.toolbox.tools) == 23
        assert len(view.toolbox.categories) == 5
        assert view.progress.available is False
        assert all(stage.status is PhaseStatus.NOT_STARTED for stage in view.progress.stages)
        assert view.progress.total_steps == 0
        assert view.traceability.available is False
        assert view.traceability.stage_count == 0
    finally:
        await _teardown_assets(ctx)


# ===================================================================
# 场景③④：性能 20 轮 P95 + 并发 20 路两两相等
# ===================================================================


async def test_scenario_3_performance_p95() -> None:
    """场景③：20 轮采样 P95<800ms（C 面——三读串行服务面窗口，预热含首次 load）."""
    plan_id = str(uuid_module.uuid4())
    ctx = _make_ctx()
    try:
        await _preset_full_plan(ctx, plan_id)
        service = _build_service()
        for _ in range(_WARMUP_ROUNDS):  # 预热含首次真实 load（连接池建立）
            await service.build_analyst_view(plan_id=plan_id)
        durations: list[float] = []
        for _ in range(_SAMPLE_ROUNDS):
            start = time.perf_counter()
            await service.build_analyst_view(plan_id=plan_id)
            durations.append((time.perf_counter() - start) * 1000.0)

        p95 = sorted(durations)[math.ceil(_P95_PERCENTILE * len(durations)) - 1]
        assert p95 < _P95_LIMIT_MS, f"P95 {p95:.1f}ms 超门禁 {_P95_LIMIT_MS}ms（全量: {sorted(durations)}）"
    finally:
        await _teardown_assets(ctx)


async def test_scenario_4_concurrent_20_reads() -> None:
    """场景④：20 路并发读全成功+排除集单键剔除后两两相等（C 面——服务无状态证明）."""
    plan_id = str(uuid_module.uuid4())
    ctx = _make_ctx()
    try:
        await _preset_full_plan(ctx, plan_id)
        service = _build_service()

        views = list(await asyncio.gather(*[service.build_analyst_view(plan_id=plan_id) for _ in range(_CONCURRENCY)]))

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
            return _freeze(data)

        serialized = {_serialize(view) for view in views}
        assert len(serialized) == 1, f"剔除生成时间单键后应两两相等，实际 {len(serialized)} 种形态"
    finally:
        await _teardown_assets(ctx)
