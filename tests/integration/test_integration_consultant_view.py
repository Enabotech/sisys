"""Story 6-10 - 顾问视图集成测试（真实双源链聚合——PG 归档行+PG 报告行）.

真实服务面（6-x 集成双子模式选型：双源全真实零 mock）；集成面同为共享库
（事务回滚式非独立 schema——背景行同在，断言口径与验收面同 OD-13 membership
全含体系）。集成面恒 commit 式（6-9 直系——无 A 面：每测试独立 ctx+定向 DELETE
行数断言回收）。

性能三段口径差声明（OD-8——集成 docstring 落档）：
    ① 视图加载 P95<800ms = build_consultant_view 服务面窗口（两读源：archive
       find 1 次 PG 查询[1000 行内聚合在应用层]+plan_count 次 get_latest_by_plan
       点查[plan_id 索引命中]——20 轮 sorted[ceil(0.95*n)-1] 数学口径六连）；
       N+1 风险注记：plan 数百级时点查链成热点，「DISTINCT+JOIN LATERAL 单查询化」
       立项锚 Epic 7/21；find 截断风险注记：归档行超 1000 截断——SQL 化清单端口同锚；
    ② 并发 20 路零输入全局读（gather+服务无状态+预置子集过滤后逐路相等——全集
       相等禁用：全局无窗查询并发窗内受其他 worker 写入抖动[6-8 R2-F2 教训]；
       membership 过滤 projects+排除 generated_at/export 段；禁 set_session——
       每路独立会话天然 per-task 隔离，6-8 R2-F3 C 面纪律直系第三连）；
    ③ 「白标导出<1 分钟」=report-generate 既有入口性能面（6-5b 承载——本 Story
       导出段是状态展示面非执行面）；「多租户隔离 100%」=继承口径（1-11 合规面
       测试承载——共享单 schema 下排他断言不可判别，正向可见性承载）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_consultant_view.py -v
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

# 性能场景背景量级 skip 门（OD-13——全库 distinct plan 数 N 含背景 plan）
_BACKGROUND_PLAN_LIMIT: int = 50

# 并发对照排除（generated_at 每路互异+export 段全库派生窗内可变不入对照）
_EXCLUDED_TOP_KEYS: tuple[str, ...] = ("generated_at", "export")


# ===================================================================
# 基建 fixture（6-8/6-9 集成惯例）
# ===================================================================


@pytest.fixture(scope="module")
def event_loop() -> Any:
    """模块级事件循环（6-x 集成惯例——场景间共享 loop，资源 per-test 隔离）."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def _fresh_resolver_per_test() -> Any:
    """每测试驱逐 resolver 缓存（SINGLETON/SCOPED——跨 loop 防线，6-5b/6-7/6-9 同款）."""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()
    yield
    resolver.clear_singleton()
    resolver.clear_scoped()


@pytest.fixture(autouse=True, scope="module")
def _require_services(event_loop: Any) -> Any:
    """服务可达探测（不可达 pytest.skip 动态跳过——禁 @pytest.mark.skip 写死）."""
    from tests.acceptance.test_acceptance_consultant_view import _probe_pg_available

    _probe_pg_available()
    yield


# ===================================================================
# 服务构建 + 预置工厂 + teardown
# ===================================================================


def _build_service() -> Any:
    """构建视图服务（两依赖 resolve 既有注册名——OD-10）."""
    from src.application.services.consultant_view_service import ConsultantViewService
    from src.domain.ports.resolver import resolve

    return ConsultantViewService(
        archive_repository=resolve("archive_repository"),
        report_repository=resolve("report_repository"),
    )


def _preset_anchor() -> tuple[datetime, Any]:
    """预置时间基准锚（单一 now——禁逐行取 now 双调：微秒级偏移会被调用间漂移淹没）.

    返回 (base, _at 偏移函数)——base+微秒偏移构造未来时间戳（预置行恒新于共享库
    背景行，行序/latest_pdf 绝对判别——OD-13①）。
    """
    base = datetime.now(UTC)

    def _at(microseconds: int) -> datetime:
        return base + timedelta(microseconds=microseconds)

    return base, _at


def _make_ctx() -> dict[str, Any]:
    """场景级 ctx（预置资产登记——teardown 定向 DELETE 面）."""
    return {"_archive_ids": [], "_report_ids": [], "_plan_ids": []}


async def _save_archive_row(ctx: dict[str, Any], plan_id: str | None, *, archived_at: datetime) -> None:
    """归档行直写（repo.save 直写通道——R5 改钦，archived_at 实体构造参数化）."""
    from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
    from src.domain.ports.resolver import resolve

    archive_id = uuid_module.uuid4()
    await resolve("archive_repository").save(
        StrategicArchive(
            archive_id=archive_id,
            plan_id=uuid_module.UUID(plan_id) if plan_id is not None else None,
            plan_type="SP",
            archive_type=ArchiveType.EVIDENCE_PACKAGE,
            assumptions={"tools_used": [], "evidence_refs": []},
            decision_basis={"kind": "evidence_package", "degraded": False},
            execution_deviation={},
            created_at=archived_at - timedelta(microseconds=1),
            archived_at=archived_at,
        )
    )
    ctx["_archive_ids"].append(str(archive_id))
    if plan_id is not None:
        ctx["_plan_ids"].append(plan_id)


async def _save_report_row(
    ctx: dict[str, Any],
    plan_id: str,
    *,
    report_type: str,
    created_at: datetime,
) -> str:
    """报告行直写（report_repository.save 单参——6-8 _save_report 先例形态）."""
    from src.domain.entities.strategic_report import ReportType, StrategicReport
    from src.domain.ports.resolver import resolve

    report_id = uuid_module.uuid4()
    await resolve("report_repository").save(
        StrategicReport(
            report_id=report_id,
            plan_id=plan_id,
            report_type=ReportType(report_type),
            file_path=(
                f"reports/{plan_id}/{report_id}.pdf"
                if report_type == "pdf"
                else f"reports/{plan_id}_{created_at.strftime('%Y%m%d%H%M%S')}.md"
            ),
            section_count=11,
            degraded_section_count=2,
            generation_ms=1234,
            created_at=created_at,
        )
    )
    ctx["_report_ids"].append(str(report_id))
    return str(report_id)


async def _preset_three_plan(ctx: dict[str, Any]) -> dict[str, str]:
    """预置三 plan 交付形态+None 行+报告行（单基准未来偏移判别——AC-2 权威形态）."""
    _base, _at = _preset_anchor()
    plan_a, plan_b, plan_c = str(uuid_module.uuid4()), str(uuid_module.uuid4()), str(uuid_module.uuid4())
    for offset in (300, 200, 100):
        await _save_archive_row(ctx, plan_a, archived_at=_at(offset))
    for offset in (90, 80):
        await _save_archive_row(ctx, plan_b, archived_at=_at(offset))
    await _save_archive_row(ctx, plan_c, archived_at=_at(70))
    await _save_archive_row(ctx, None, archived_at=_at(400))
    await _save_report_row(ctx, plan_a, report_type="markdown", created_at=_at(50))
    pdf_id = await _save_report_row(ctx, plan_a, report_type="pdf", created_at=_at(60))
    await _save_report_row(ctx, plan_b, report_type="markdown", created_at=_at(40))
    return {"plan_a": plan_a, "plan_b": plan_b, "plan_c": plan_c, "pdf_id": pdf_id}


async def _teardown_rows(ctx: dict[str, Any]) -> None:
    """定向 DELETE 行数断言（防静默 0 行假绿——6-8 R2-F3 纪律直系）."""
    if not (ctx["_archive_ids"] or ctx["_report_ids"]):
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
            if ctx["_archive_ids"]:
                result = await conn.execute(
                    sa.text("DELETE FROM strategic_archives WHERE archive_id = ANY(:ids)"),
                    {"ids": list(ctx["_archive_ids"])},
                )
                assert result.rowcount == len(ctx["_archive_ids"]), (
                    f"strategic_archives DELETE 行数 {result.rowcount} != 预置 {len(ctx['_archive_ids'])}"
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


async def _query_pdf_row(report_id: str) -> tuple[str, str] | None:
    """回查预置 pdf 报告行（file_path/created_at 精确值单源）."""
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
            result = await conn.execute(
                sa.text("SELECT file_path, created_at FROM strategic_reports WHERE report_id = :rid"),
                {"rid": report_id},
            )
            row = result.first()
            return (row.file_path, row.created_at.isoformat()) if row else None
    finally:
        await engine.dispose()


# ===================================================================
# 场景① 全数据三段 round-trip
# ===================================================================


async def test_scenario_1_full_round_trip() -> None:
    """场景①：真实双源 round-trip（membership 全含口径 OD-13——三 plan 各恰一行+首三降序+值级直推）."""
    ctx = _make_ctx()
    try:
        preset = await _preset_three_plan(ctx)
        view = await _build_service().build_consultant_view()

        listed = tuple(row.plan_id for row in view.projects.projects)
        # membership 全含（预置三 plan ∈ 清单+各恰一行——背景行免疫 OD-13②）
        for plan_id in (preset["plan_a"], preset["plan_b"], preset["plan_c"]):
            assert listed.count(plan_id) == 1, f"预置 plan {plan_id[:8]} 应恰一行"
        # 首三占位+内部降序（未来偏移恒新于背景行——OD-13①）
        assert listed[:3] == (preset["plan_a"], preset["plan_b"], preset["plan_c"]), "首三 A→B→C 降序"
        # 行级值直推（None 行不计入即判别——3/2/1 精确）
        rows = {row.plan_id: row for row in view.projects.projects}
        assert rows[preset["plan_a"]].archive_count == 3
        assert rows[preset["plan_b"]].archive_count == 2
        assert rows[preset["plan_c"]].archive_count == 1
        # 零报告形态（有活动无交付物）
        assert rows[preset["plan_c"]].latest_report_type is None
        assert rows[preset["plan_c"]].latest_report_at is None
        # latest 遮蔽口径（plan-A 先 md 后 pdf → latest=pdf）
        assert rows[preset["plan_a"]].latest_report_type == "pdf"
        assert rows[preset["plan_b"]].latest_report_type == "markdown"
        # latest_pdf 三键与预置 pdf 行直推（未来偏移保全库最新）
        pdf_row = await _query_pdf_row(preset["pdf_id"])
        assert pdf_row is not None
        assert view.export.latest_pdf_plan_id == preset["plan_a"]
        assert view.export.latest_pdf_object_key == pdf_row[0]
        assert view.export.latest_pdf_generated_at == pdf_row[1]
        # 品牌恒默认态
        assert view.brand.configured is False
        assert view.brand.font_status == "STSong-Light（内置）"
        # 计数恒等式三联（VO 内部不变量——背景行免疫）
        assert view.projects.plan_count == len(view.projects.projects)
        assert view.export.plans_with_reports == sum(1 for row in view.projects.projects if row.latest_report_type is not None)
        assert view.export.plans_with_latest_pdf == sum(1 for row in view.projects.projects if row.latest_report_type == "pdf")
        assert view.build_degraded is False
    finally:
        await _teardown_rows(ctx)


# ===================================================================
# 场景② 空态幂等读（核心四断言——绝对空态断言归单测 OD-13④）
# ===================================================================


async def test_scenario_2_empty_state() -> None:
    """场景②：零预置 → 5 键恒在+brand 完整+build_degraded False+不抛（6-8 集成「绝对空断言不可写 R1-F6」直系）."""
    view = await _build_service().build_consultant_view()
    assert view is not None, "空态幂等读应正常返回（不抛）"
    assert {f.name for f in dataclasses.fields(view)} == {"generated_at", "build_degraded", "projects", "brand", "export"}
    assert view.build_degraded is False, "「没有数据」非「拿不到数据」"
    assert view.brand.configured is False
    assert view.brand.logo_status == "未配置（系统默认）"
    assert view.brand.color_scheme_status == "未配置（系统默认）"
    assert view.brand.font_status == "STSong-Light（内置）"


# ===================================================================
# 场景③ 性能 20 轮 P95<800ms（背景量级 skip 门）
# ===================================================================


async def test_scenario_3_performance_p95() -> None:
    """场景③：20 轮采样 P95<800ms（服务面两读窗口；背景 distinct plan>50 时 skip——环境量级敏感）."""
    from src.domain.ports.archive_repository import ArchiveQuery
    from src.domain.ports.resolver import resolve

    rows = await resolve("archive_repository").find(ArchiveQuery(plan_id=None, limit=1000))
    background_plans = len({row.plan_id for row in rows if row.plan_id is not None})
    if background_plans > _BACKGROUND_PLAN_LIMIT:
        pytest.skip(f"背景 distinct plan 数 {background_plans} 超阈值 {_BACKGROUND_PLAN_LIMIT}（环境量级敏感）")

    ctx = _make_ctx()
    try:
        await _preset_three_plan(ctx)
        service = _build_service()
        for _ in range(_WARMUP_ROUNDS):  # 预热含首轮连接池建立
            await service.build_consultant_view()
        durations: list[float] = []
        for _ in range(_SAMPLE_ROUNDS):
            start = time.perf_counter()
            await service.build_consultant_view()
            durations.append((time.perf_counter() - start) * 1000.0)
        p95 = sorted(durations)[math.ceil(_P95_PERCENTILE * len(durations)) - 1]
        assert p95 < _P95_LIMIT_MS, f"P95 {p95:.1f}ms 超门禁 {_P95_LIMIT_MS}ms（全量: {sorted(durations)}）"
    finally:
        await _teardown_rows(ctx)


# ===================================================================
# 场景④ 并发 20 路（预置子集过滤后逐路相等——全集相等禁用 OD-13）
# ===================================================================


async def test_scenario_4_concurrent_20_reads() -> None:
    """场景④：20 路并发读全成功+预置子集过滤后逐路相等（禁 set_session——每路独立会话）."""
    ctx = _make_ctx()
    try:
        preset = await _preset_three_plan(ctx)
        service = _build_service()
        views = list(await asyncio.gather(*[service.build_consultant_view() for _ in range(_CONCURRENCY)]))
        assert len(views) == _CONCURRENCY
        assert all(view is not None for view in views), "20 路应全部成功不抛（服务无状态 SINGLETON 共享）"

        def _freeze(value: Any) -> Any:
            if isinstance(value, dict):
                return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
            if isinstance(value, (list, tuple)):
                return tuple(_freeze(item) for item in value)
            return value

        preset_ids = {preset["plan_a"], preset["plan_b"], preset["plan_c"]}
        serialized: set[Any] = set()
        for view in views:
            data = dataclasses.asdict(view)
            for key in _EXCLUDED_TOP_KEYS:
                data.pop(key, None)
            data["projects"]["projects"] = [row for row in data["projects"]["projects"] if row["plan_id"] in preset_ids]
            serialized.add(_freeze(data))
        assert len(serialized) == 1, f"预置子集过滤后应逐路相等（实测 {len(serialized)} 种形态——含 build_degraded/brand 对照）"
    finally:
        await _teardown_rows(ctx)
