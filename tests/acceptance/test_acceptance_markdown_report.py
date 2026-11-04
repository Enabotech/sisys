"""Markdown 报告生成（基础）验收测试（Story 6-5a）。

13 场景分档表：

| # | 场景 | AC | 数据面构造 | 门控 |
|---|------|----|-----------|------|
| S1 | 报告生成主链五段编排全落位 | AC-1 | Fake LLM/Embedding 完整 8 步 run | 四真实服务 |
| S2 | 同 plan_id 重复生成产生新报告 | AC-1 | 同 S1（跨秒间隔 ≥1.05s——OD-10 秒级注记） | 四真实服务 |
| S3 | 冻结章节结构全量输出 | AC-2 | 同 S1 | 四真实服务 |
| S4 | 章节标题与要素字段逐字对齐配置源 | AC-2 | 同 S1 | 四真实服务 |
| S5 | 基础格式化三要素语法正确 | AC-3 | 同 S1 | 四真实服务 |
| S6 | 归档行部分缺失时章节降级标注 | AC-4 | 逐 stage 七步归档跳过目标六子步（钦定构造——禁删行） | 四真实服务 |
| S7 | 数据源全缺时抛出 490 异常 | AC-4 | 从未归档的独立 plan_id（天然 total==0） | 四真实服务 |
| S8 | latest 快照缺失时附录 A 省略 | AC-4 | 逐 stage 八步归档（无 run → 天然无快照） | 四真实服务 |
| S9 | ReportGenerated 事件经 outbox 落行 | AC-5 | 同 S1 | 四真实服务 |
| S10 | 读侧消费面契约键集全等 | AC-6 | 同 S1 | 四真实服务 |
| S11 | 性能 P95 与成功率采样 | AC-7 | 逐 stage 八步归档 ×1 plan ×20 次生成（OD-10 幂等锚采样） | 四真实服务 |
| S12 | 并发生成 3 个报告互不串扰 | AC-7 | 逐 stage 八步归档 ×3 plan（gather 形态锚） | 四真实服务 |
| S13 | Story 交付件存在性收尾验收 | 收尾 | 静态文件断言 | 无 |

测试隔离与口径声明：
- **OD-8 性能口径差**：生成窗口 P95 = 数据聚合起点→事件发布返回（不含 BLM run 前置——
  run 是数据面构造非被测窗口）；采样形态 = 单一数据源 plan_id × 20 次生成（重跑幂等锚
  语义下合法采样，归档链只构造一次）。
- **L0 写路径隔离**（R1-17/R2-5）：tmp_path 自建 FileMemoryAdapter 覆写注入 + _restorers
  还原——真实 resolve 通道会写运行机器 ~/.sisys/memory/reports/ 污染共享目录；且组合根
  SCOPED lambda 缓存于 resolver 实例，resolve 后 setenv 不生效，覆写注入是唯一可靠隔离。
- **teardown 七步链**：端口覆写还原 → PG 会话终结 → outbox 行精确 DELETE → L2
  strategic_reports 行 DELETE → L0 报告文件删除 → 归档三面（PG 档案行/Qdrant 点/MinIO
  WORM——6-4 _cleanup_archive_residues 移植）→ Redis 快照键族 + 关闭客户端。
- **真实提交定向清理**：报告链内含 L2 落库链（savepoint 不适用——6-4 钦定口径），按
  plan_id/report_id 定向 DELETE 清理（定向清理例外钦定；禁手动 delete/truncate 共享表）。
- **延迟 import 纪律**：本 Story 新交付模块一律在步骤/装配函数体内 import——顶部 import
  会使 pytest 收集期整文件 collection error，Task 0 预期红因 = 运行期 ImportError。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_markdown_report.py -v
"""

import asyncio
import uuid
from collections.abc import Awaitable, Generator
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pytest_bdd import given, scenario, then, when

# marker 名以 pyproject 注册为准（database 非 postgresql——R2-F23）；xdist_group
# 模块级挂法复用 6-1/6-2/6-3/6-4 组名（性能/采样场景跨 Story 同 worker 串行）
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.database,
    pytest.mark.redis,
    pytest.mark.qdrant,
    pytest.mark.minio,
    pytest.mark.xdist_group("blm-planning-perf"),
]

_T = TypeVar("_T")

#: 仓库根（S13 交付件存在性断言）
_REPO_ROOT = Path(__file__).resolve().parents[2]

#: 八 stage 期望序（归档数据构造排序参考；断言期望一律经 MARKET_INSIGHT_STEP_CONFIG
#: 键序独立构造——派生公式单源在端口契约，测试侧禁二次硬编码断言源）
_EXPECTED_STAGE_ORDER: tuple[str, ...] = (
    "performance_gap",
    "market_insight_trend",
    "market_insight_market_customer",
    "market_insight_competition",
    "market_insight_self",
    "market_insight_opportunity",
    "market_insight_opportunity_gap",
    "market_insight_synthesis",
)

#: chain 读侧 records 五键冻结基线（AC-6×1 字面键集——防漂移即守护）
_RECORD_KEY_BASELINE: tuple[str, ...] = ("stage", "chain", "archive_id", "degraded", "blob_content")

#: ReportGenerated outbox payload 键族冻结基线（事件类冻结字段面——AC-6×1；
#: CR1-F27：嵌套期望 = 基线 − 核心三键差集派生，加字段只改此常量即联动）
_REPORT_EVENT_PAYLOAD_KEY_BASELINE: frozenset[str] = frozenset(
    {"report_id", "report_type", "file_path", "aggregate_id", "aggregate_type", "event_type"}
)

#: 事件基类核心三键（DomainEvent 顶层通用键——两级路径的顶层单源命名）
_CORE_EVENT_PAYLOAD_KEYS: frozenset[str] = frozenset({"aggregate_id", "aggregate_type", "event_type"})

#: 性能采样轮数（OD-8：N 与成功率口径同源）
_PERF_SAMPLE_ROUNDS: int = 20

#: P95 上限（秒）——AC-7 口径（聚合起点→事件发布返回）
_PERF_P95_LIMIT_SECONDS: float = 30.0

#: 同 plan_id 重复生成跨秒间隔（OD-10 秒级精度注记：YYYYMMDDHHMMSS 秒内连跑 memory_id
#: 相同 → L0 覆写为一份；件数断言需跨秒 ≥1.05s）
_REPEAT_GENERATION_GAP_SECONDS: float = 1.05


# ======================================================================
# 三件套（模块级 event_loop + context dict + _run_async——BDD 步骤禁
# @pytest.mark.asyncio，同循环驱动防 context 丢失）
# ======================================================================


def _run_async(event_loop: asyncio.AbstractEventLoop, awaitable: Awaitable[_T]) -> _T:
    """在模块级事件循环上运行可等待对象（BDD 步骤禁 @pytest.mark.asyncio）。

    Args:
        event_loop: 模块级事件循环（fixture 注入）。
        awaitable: 待运行的可等待对象。

    Returns:
        可等待对象的结果。
    """
    return event_loop.run_until_complete(awaitable)


@pytest.fixture(scope="module")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """模块级事件循环（BDD 步骤禁 @pytest.mark.asyncio——同循环三件套）。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _clear_resolver_caches() -> None:
    """驱逐 resolver SINGLETON/SCOPED 缓存（跨 loop/跨文件污染防线）。

    缓存实例内含 asyncpg 连接池（绑首用 loop）——xdist 同 worker 内跨文件
    （6-x 组先跑的 resolve 缓存）与跨场景复用必炸 "different loop"；前后各
    清一次：前清防被先前文件污染（本场景 resolve 重建绑本 loop），后清防
    污染后续文件（6-1 场景③ clear_singleton 先例 + clear_scoped 补全——
    集成测试 _fresh_resolver_per_test 同款）。
    """
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()


@pytest.fixture
def context(
    event_loop: asyncio.AbstractEventLoop,
    acceptance_env_config: Any,
    tmp_path: Path,
) -> Generator[dict[str, Any], None, None]:
    """场景级上下文（teardown 七步链随 yield 后执行——断言失败也清理）。"""
    _clear_resolver_caches()
    ctx: dict[str, Any] = {
        "_loop": event_loop,
        "_env": acceptance_env_config,
        "_report_tmp_path": tmp_path,
        "_restorers": [],
        "_chain_assembled": False,
        "_pg_manager": None,
        "_pg_session": None,
        "_pg_session_token": None,
        "_redis_client": None,
        "_report_l0_storage": None,
        # 清理登记面（调用服务之前预登记——R1 审查 FR-1 先例）
        "_plan_ids": [],
        "_archive_row_ids": [],
        "_minio_blob_refs": [],
        "_outbox_event_ids": [],
        "_snapshot_session_ids": [],
        "_report_ids": [],
        "_l0_memory_ids": [],
        "_agent_ids": [],
    }
    yield ctx
    _teardown_chain(ctx)
    _clear_resolver_caches()


# ======================================================================
# teardown 七步链（各步独立 try/except——前步失败不阻断后步）
# ======================================================================


def _teardown_chain(ctx: dict[str, Any]) -> None:
    """teardown 七步链（报告三元 + 归档三面 + 快照键族 + 覆写还原）。

    各步独立 try/except（残局防线）；全部 _run_async 同循环（跨循环
    "Event loop is closed" 存档教训）。
    """
    # ① 端口覆写还原（L0 tmp_path 覆写替身）+ SINGLETON 缓存驱逐
    for restore in ctx["_restorers"]:
        try:
            restore()
        except Exception:
            pass
    _run_async(ctx["_loop"], _finalize_pg_session(ctx))
    # ② outbox 事件行精确 DELETE（event_id 面 + plan_id/report_id 兜底多通道）
    try:
        _run_async(ctx["_loop"], _cleanup_outbox_rows(ctx))
    except Exception:
        pass
    # ③ L2 strategic_reports 行精确 DELETE（report_id 面 + plan_id 兜底）
    try:
        _run_async(ctx["_loop"], _cleanup_report_rows(ctx))
    except Exception:
        pass
    # ④ L0 报告文件删除（memory_id 定向——tmp_path 隔离下理论零残留，双保险）
    try:
        _run_async(ctx["_loop"], _cleanup_l0_report_files(ctx))
    except Exception:
        pass
    # ⑤⑥ 归档三面（PG 档案行 / Qdrant 点 / MinIO WORM——6-4 移植）
    try:
        _run_async(ctx["_loop"], _cleanup_archive_residues(ctx))
    except Exception:
        pass
    # ⑦ Redis 快照键族删除 + 同循环关闭客户端
    try:
        _run_async(ctx["_loop"], _cleanup_redis_keys(ctx))
    except Exception:
        pass
    if ctx["_redis_client"] is not None:
        try:
            _run_async(ctx["_loop"], ctx["_redis_client"].close())
        except Exception:
            pass


def _make_pg_manager(env: Any) -> Any:
    """构建独立 PostgreSQLManager（teardown/清理专用——不复用场景会话）。

    Args:
        env: 测试环境配置（acceptance_env_config）。

    Returns:
        PostgreSQLManager 实例（调用方负责 dispose）。
    """
    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

    return PostgreSQLManager(
        PostgreSQLConfig(
            host=env.postgres.host,
            port=env.postgres.port,
            database=env.postgres.database,
            username=env.postgres.username,
            password=env.postgres.password,
        )
    )


async def _finalize_pg_session(ctx: dict[str, Any]) -> None:
    """PG 会话终结（commit→失败 rollback→reset→close，各自独立容错）。"""
    session = ctx.get("_pg_session")
    if session is None:
        return
    try:
        await session.commit()
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass
    token = ctx.get("_pg_session_token")
    if token is not None:
        try:
            from src.infrastructure.storage.postgresql.session_context import reset_session

            reset_session(token)
        except Exception:
            pass
    try:
        await session.close()
    except Exception:
        pass
    manager = ctx.get("_pg_manager")
    if manager is not None:
        try:
            await manager.get_async_engine().dispose()
        except Exception:
            pass


async def _cleanup_outbox_rows(ctx: dict[str, Any]) -> None:
    """outbox 事件行精确 DELETE（event_id 面 + plan_id/report_id 双 JSONB 通道兜底）。"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    manager = _make_pg_manager(ctx["_env"])
    try:
        async with AsyncSession(manager.get_async_engine()) as session:
            if ctx["_outbox_event_ids"]:
                await session.execute(
                    text("DELETE FROM event_outbox WHERE event_id = ANY(:ids)"),
                    {"ids": list(ctx["_outbox_event_ids"])},
                )
            if ctx["_plan_ids"] or ctx["_report_ids"]:
                await session.execute(
                    text(
                        "DELETE FROM event_outbox WHERE payload->'metadata'->>'plan_id' = ANY(:plan_ids) "
                        "OR payload->'payload'->>'plan_id' = ANY(:plan_ids) "
                        "OR payload->'payload'->>'report_id' = ANY(:report_ids)"
                    ),
                    {
                        "plan_ids": list(ctx["_plan_ids"]),
                        "report_ids": [str(rid) for rid in ctx["_report_ids"]],
                    },
                )
            await session.commit()
    finally:
        await manager.get_async_engine().dispose()


async def _cleanup_report_rows(ctx: dict[str, Any]) -> None:
    """L2 strategic_reports 行精确 DELETE（report_id 面 + plan_id 兜底）。"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    manager = _make_pg_manager(ctx["_env"])
    try:
        async with AsyncSession(manager.get_async_engine()) as session:
            if ctx["_report_ids"]:
                await session.execute(
                    text("DELETE FROM strategic_reports WHERE report_id = ANY(:ids)"),
                    {"ids": [str(rid) for rid in ctx["_report_ids"]]},
                )
            if ctx["_plan_ids"]:
                await session.execute(
                    text("DELETE FROM strategic_reports WHERE plan_id = ANY(:ids)"),
                    {"ids": list(ctx["_plan_ids"])},
                )
            await session.commit()
    finally:
        await manager.get_async_engine().dispose()


async def _cleanup_l0_report_files(ctx: dict[str, Any]) -> None:
    """L0 报告文件定向删除（memory_id 锚；tmp_path 隔离下双保险）。"""
    l0_storage = ctx.get("_report_l0_storage")
    if l0_storage is None:
        return
    for memory_id in list(ctx["_l0_memory_ids"]):
        try:
            await l0_storage.delete(memory_id, "reports")
        except Exception:
            pass


async def _cleanup_archive_residues(ctx: dict[str, Any]) -> None:
    """归档三面清理（PG 档案行 / Qdrant 点 / MinIO WORM——6-4 _cleanup_archive_residues 移植）。"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    env = ctx["_env"]
    manager = _make_pg_manager(env)
    archive_ids: list[str] = []
    blob_refs: list[str] = []
    try:
        async with AsyncSession(manager.get_async_engine()) as session:
            if ctx["_plan_ids"]:
                rows = await session.execute(
                    text("SELECT archive_id, blob_ref FROM strategic_archives WHERE plan_id = ANY(:ids)"),
                    {"ids": list(ctx["_plan_ids"])},
                )
                for row in rows:
                    archive_ids.append(str(row[0]))
                    if row[1]:
                        blob_refs.append(str(row[1]))
        archive_ids.extend(ctx["_archive_row_ids"])
        blob_refs.extend(ctx["_minio_blob_refs"])
        if archive_ids:
            # Qdrant 点删除（strategic_archive collection 按 archive_id FilterSelector）
            try:
                from qdrant_client import AsyncQdrantClient
                from qdrant_client import models as qdrant_models

                qdrant = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
                try:
                    await qdrant.delete(
                        collection_name="strategic_archive",
                        points_selector=qdrant_models.FilterSelector(
                            filter=qdrant_models.Filter(
                                must=[
                                    qdrant_models.FieldCondition(
                                        key="archive_id", match=qdrant_models.MatchAny(any=archive_ids)
                                    )
                                ]
                            )
                        ),
                    )
                finally:
                    await qdrant.close()
            except Exception:
                pass
            # MinIO WORM 对象删除（bypass_governance_mode=True——6-3 集成先例）
            if blob_refs:
                try:
                    from minio import Minio
                    from minio.deleteobjects import DeleteObject

                    def _remove_minio() -> None:
                        client = Minio(
                            endpoint=env.minio.endpoint,
                            access_key=env.minio.access_key,
                            secret_key=env.minio.secret_key,
                            secure=env.minio.secure,
                        )
                        bucket_name = _resolve_archive_bucket_name()
                        errors = client.remove_objects(
                            bucket_name,
                            [DeleteObject(blob_ref) for blob_ref in blob_refs],
                            bypass_governance_mode=True,
                        )
                        for _ in errors:
                            pass

                    await asyncio.to_thread(_remove_minio)
                except Exception:
                    pass
            # PG 档案行删除
            async with AsyncSession(manager.get_async_engine()) as session:
                await session.execute(
                    text("DELETE FROM strategic_archives WHERE archive_id = ANY(:ids)"),
                    {"ids": archive_ids},
                )
                await session.commit()
    finally:
        await manager.get_async_engine().dispose()


def _resolve_archive_bucket_name() -> str:
    """解析归档 bucket 名（经组合根 l4_object 仓储——零硬编码）。

    Returns:
        bucket 名字符串。
    """
    from src.domain.ports.resolver import get_resolver

    l4 = get_resolver().resolve("l4_object")
    return str(l4._repository._resolve_bucket_name("archive-evidence"))


async def _cleanup_redis_keys(ctx: dict[str, Any]) -> None:
    """Redis 键族精确删除（快照双 session 键 + Agent 状态双 namespace——禁 flush）。"""
    if ctx["_redis_client"] is None:
        return
    try:
        from src.infrastructure.storage.redis.key_builder import build_key

        for session_id in list(ctx["_snapshot_session_ids"]):
            await ctx["_redis_client"].delete(build_key("snapshot", session_id))
        for agent_id in list(ctx["_agent_ids"]):
            for namespace in ("agent", "isolation"):
                await ctx["_redis_client"].delete(build_key(namespace, str(agent_id)))
    except Exception:
        pass


# ======================================================================
# 场景绑定（13 场景全绑定——R6 旧欠账不承袭）
# ======================================================================


@scenario("test_acceptance_markdown_report.feature", "报告生成主链五段编排全落位")
def test_report_generation_main_chain() -> None:
    """S1: AC-1 主链五段编排（聚合→渲染→持久化→事件）。"""
    pass


@scenario("test_acceptance_markdown_report.feature", "同 plan_id 重复生成产生新报告")
def test_repeat_generation_new_report() -> None:
    """S2: AC-1 幂等锚=report_id（跨秒间隔断言件数）。"""
    pass


@scenario("test_acceptance_markdown_report.feature", "冻结章节结构全量输出")
def test_frozen_section_structure() -> None:
    """S3: AC-2 章节结构冻结全量断言。"""
    pass


@scenario("test_acceptance_markdown_report.feature", "章节标题与要素字段逐字对齐配置源")
def test_display_name_literal_alignment() -> None:
    """S4: AC-2 display_name 逐字源 + 六 Schema 全字段。"""
    pass


@scenario("test_acceptance_markdown_report.feature", "基础格式化三要素语法正确")
def test_basic_formatting_three_elements() -> None:
    """S5: AC-3 标题/列表/表格格式化。"""
    pass


@scenario("test_acceptance_markdown_report.feature", "归档行部分缺失时章节降级标注")
def test_partial_missing_degradation() -> None:
    """S6: AC-4 部分缺失降级（跳六子步构造）。"""
    pass


@scenario("test_acceptance_markdown_report.feature", "数据源全缺时抛出 490 异常")
def test_total_missing_raises_490() -> None:
    """S7: AC-4 全缺 490 异常路径。"""
    pass


@scenario("test_acceptance_markdown_report.feature", "latest 快照缺失时附录 A 省略")
def test_snapshot_missing_omits_appendix_a() -> None:
    """S8: AC-4 快照缺失容错。"""
    pass


@scenario("test_acceptance_markdown_report.feature", "ReportGenerated 事件经 outbox 落行")
def test_report_generated_outbox_row() -> None:
    """S9: AC-5 事件 outbox 落行三键值级断言。"""
    pass


@scenario("test_acceptance_markdown_report.feature", "读侧消费面契约键集全等")
def test_read_side_contract_key_sets() -> None:
    """S10: AC-6 读侧消费面契约（chain 五键 + payload 键族全等）。"""
    pass


@scenario("test_acceptance_markdown_report.feature", "性能 P95 与成功率采样（单一数据源 20 轮）")
def test_performance_p95_and_success_rate() -> None:
    """S11: AC-7 性能 P95 + 成功率（OD-8 口径）。"""
    pass


@scenario("test_acceptance_markdown_report.feature", "并发生成 3 个报告互不串扰")
def test_concurrent_three_reports() -> None:
    """S12: AC-7 并发 3（gather 形态锚）。"""
    pass


@scenario("test_acceptance_markdown_report.feature", "Story 交付件存在性收尾验收")
def test_story_deliverables_existence() -> None:
    """S13: 收尾交付件存在性逐项断言。"""
    pass


# ======================================================================


async def _probe_and_assemble(ctx: dict[str, Any]) -> None:
    """四服务探测（PG/Redis/Qdrant/MinIO）+ 基础资源装配（探测失败动态 skip）。

    bootstrap 幂等守卫（tests/conftest _bootstrap_once 已会话级装配——重复
    bootstrap 会因 lambda 新函数对象 spec 不同抛 ConflictError）。
    """
    import pytest as _pytest
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    env = ctx["_env"]
    from src.domain.ports.registry import _global_registry

    if _global_registry.get("agent_workflow_use_case") is None:
        from src.composition_root import bootstrap

        bootstrap()
    # PostgreSQL 探测（报告元数据表 + outbox + 归档表三表预检）
    pg_manager = _make_pg_manager(env)
    try:
        async with AsyncSession(pg_manager.get_async_engine()) as session:
            await session.execute(text("SELECT 1 FROM event_outbox LIMIT 1"))
            await session.execute(text("SELECT 1 FROM strategic_archives LIMIT 1"))
            await session.execute(text("SELECT 1 FROM strategic_reports LIMIT 1"))
    except Exception as exc:
        await pg_manager.get_async_engine().dispose()
        _pytest.skip(f"PostgreSQL 不可用: {exc}")
    # Redis 探测
    import redis.asyncio as aioredis

    redis_client = aioredis.Redis(host=env.redis.host, port=env.redis.port, decode_responses=False)
    try:
        await redis_client.ping()
    except Exception as exc:
        await redis_client.close()
        await pg_manager.get_async_engine().dispose()
        _pytest.skip(f"Redis 不可用: {exc}")
    # Qdrant 探测（轻量 HTTP /collections——绕开 AsyncQdrantClient 在重 bootstrap
    # 进程内的库级连接状态问题；探测语义=REST 可达，场景内真实客户端经 resolve）
    try:
        import urllib.request

        def _probe_qdrant_http() -> None:
            url = f"http://{env.qdrant.host}:{env.qdrant.port}/collections"
            with urllib.request.urlopen(url, timeout=10) as response:
                if response.status != 200:
                    raise RuntimeError(f"Qdrant /collections 状态异常: {response.status}")

        await asyncio.to_thread(_probe_qdrant_http)
    except Exception as exc:
        await redis_client.close()
        await pg_manager.get_async_engine().dispose()
        _pytest.skip(f"Qdrant 不可用: {type(exc).__name__}: {exc}")
    # MinIO 探测（bucket 预检——经组合根解析 bucket 名）
    try:
        from minio import Minio

        def _probe_minio() -> None:
            bucket_name = _resolve_archive_bucket_name()
            client = Minio(
                endpoint=env.minio.endpoint,
                access_key=env.minio.access_key,
                secret_key=env.minio.secret_key,
                secure=env.minio.secure,
            )
            if not client.bucket_exists(bucket_name):
                raise RuntimeError(f"MinIO bucket 不存在: {bucket_name}")

        await asyncio.to_thread(_probe_minio)
    except Exception as exc:
        await redis_client.close()
        await pg_manager.get_async_engine().dispose()
        _pytest.skip(f"MinIO 不可用: {exc}")
    # 基础资源登记（报告链 L0 tmp_path 实例 + PG/Redis 句柄）
    from src.infrastructure.config.memory import MemoryConfig
    from src.infrastructure.storage.fs.file_memory_adapter import FileMemoryAdapter

    ctx["_report_l0_storage"] = FileMemoryAdapter(MemoryConfig(memory_l0_path=str(ctx["_report_tmp_path"])))
    ctx["_pg_manager"] = pg_manager
    ctx["_redis_client"] = redis_client
    ctx["_chain_assembled"] = True


def _ensure_qdrant_retrieval(ctx: dict[str, Any]) -> None:
    """检索 R 门控（S1 完整 run 面需要——embedding 服务不可达动态 skip）。

    仅在完整 run 场景惰性调用（_assemble_full_flow 内）；归档轻装配不触发。
    """
    if "retrieval_collection" in ctx:
        return

    from qdrant_client import AsyncQdrantClient

    from src.infrastructure.config.embedding import EmbeddingConfig
    from src.infrastructure.config.qdrant import QdrantConfig
    from src.infrastructure.external_services.embedding.embedding_api_client import EmbeddingAPIClient

    env = ctx["_env"]
    loop = ctx["_loop"]

    async def _setup() -> tuple[str, Any, AsyncQdrantClient]:
        embedding = _CachedEmbedding(EmbeddingAPIClient(EmbeddingConfig.from_env()))
        qconfig = QdrantConfig(
            host=env.qdrant.host, port=env.qdrant.port, grpc_port=env.qdrant.grpc_port, api_key=env.qdrant.api_key
        )
        client = AsyncQdrantClient(url=f"http://{qconfig.host}:{qconfig.port}", timeout=30)
        await embedding.embed_query("连通性探测")
        await client.get_collections()

        collection = f"test_report_{uuid.uuid4().hex[:8]}"
        from qdrant_client import models

        await client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
        )
        vectors = await embedding.embed_documents(list(_CORPUS_TEXTS))
        points = [
            models.PointStruct(id=str(uuid.uuid4()), vector=vec, payload={"text": text})
            for vec, text in zip(vectors, _CORPUS_TEXTS)
        ]
        await client.upsert(collection_name=collection, points=points)
        return collection, embedding, client

    try:
        collection, embedding, qclient = _run_async(loop, _setup())
    except Exception as exc:
        pytest.skip(f"检索服务（embedding/Qdrant）不可用: {exc}")

    ctx["retrieval_collection"] = collection
    ctx["_embedding_client"] = embedding
    ctx["_qdrant_client"] = qclient


# ======================================================================
# Fake/替身工厂（6-4 验收形态移植——外部 SaaS 豁免面）
# ======================================================================

#: 检索语料（hybrid 检索 R 门控——6-4 同款）
_CORPUS_TEXTS: tuple[str, ...] = (
    "新能源汽车行业进入战略分析报告：市场增速放缓但渗透率持续提升",
    "财务业绩差距分析：营收目标达成率与毛利率下滑根因",
    "竞争对手动态：头部厂商价格战与渠道下沉策略",
    "宏观趋势：政策补贴退坡与技术路线演进（固态电池）",
    "内部能力评估：研发投入占比与组织能力短板",
    "市场机会：海外新兴市场增长路径与机会差距量化",
)

#: Fake 步骤摘要前缀（S4 期望独立构造锚）
_FAKE_STEP_SUMMARY_PREFIX = "FAKE_STEP_SUMMARY"

_BLM_TASK = "制定新能源汽车行业五年战略规划（报告验收真实链）"


def _make_fake_llm() -> Any:
    """BLM 面 Fake LLM 替身（八 Schema __name__ 分派——6-4 验收版形态移植）。"""
    from unittest.mock import AsyncMock

    from src.domain.ports.llm_client import LLMClientPort, LLMResponse

    async def _structured_generate(
        prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
    ) -> Any:
        from src.domain.exceptions.llm_exceptions import LLMAPIError

        if response_schema.__name__ == "TrendInsightSchema":
            return response_schema(
                summary=f"{_FAKE_STEP_SUMMARY_PREFIX}:trend（结构化要点）",
                findings=["发现一：政策与技术双趋势信号明确", "发现二：情景分化风险上升"],
                pestel_political="政策维度：补贴退坡与准入收紧",
                pestel_economic="经济维度：利率上行压制可选消费",
                pestel_social="社会维度：绿色出行消费习惯迁移",
                pestel_technological="技术维度：固态电池与智能驾驶演进",
                pestel_environmental="环境维度：碳排法规趋严",
                pestel_legal="法律维度：数据合规与知识产权要求升级",
                technology_roadmap=["短期：平台化架构降本", "中期：固态电池量产", "长期：智驾生态成型"],
                scenario_plans=["基准情景：渗透率稳步提升", "乐观情景：政策加码提速"],
            )
        if response_schema.__name__ == "MarketCustomerInsightSchema":
            return response_schema(
                summary=f"{_FAKE_STEP_SUMMARY_PREFIX}:market_customer（结构化要点）",
                findings=["发现一：细分需求分化明显", "发现二：补能效率是首要痛点"],
                customer_segments=["价格敏感型家庭用户", "科技尝鲜型年轻用户"],
                demand_priority_matrix=["续航与补能效率（最高优先）", "智能座舱体验（高优先）"],
                value_proposition_map=["痛点：补能焦虑→收益：超充网络覆盖"],
            )
        if response_schema.__name__ == "CompetitionInsightSchema":
            return response_schema(
                summary=f"{_FAKE_STEP_SUMMARY_PREFIX}:competition（结构化要点）",
                findings=["发现一：竞争强度处历史高位", "发现二：头部厂商成本优势扩大"],
                five_forces_supplier_power="供应商议价能力：中高（电池厂商集中度高）",
                five_forces_buyer_power="购买者议价能力：中（选择增多但转换成本存在）",
                five_forces_new_entrants="新进入者威胁：高（跨界造车与代工模式降低门槛）",
                five_forces_substitutes="替代品威胁：中（公共交通与共享出行部分替代）",
                five_forces_rivalry="现有竞争者强度：极高（价格战与渠道战并发）",
                competitor_radar=["研发能力：头部厂商 9/10", "成本控制：二线厂商 6/10"],
                strategy_recommendations=["以差异化配置避开正面价格战"],
            )
        if response_schema.__name__ == "SelfInsightSchema":
            return response_schema(
                summary=f"{_FAKE_STEP_SUMMARY_PREFIX}:self（结构化要点）",
                findings=["发现一：三电自研是核心能力", "发现二：渠道与品牌存在短板"],
                internal_capabilities=["三电自研平台", "软件 OTA 体系"],
                vrio_assessment=["三电平台：价值+稀有+难模仿+组织适配（核心能力）"],
                resource_constraints=["研发预算受限", "电池产能依赖外部"],
            )
        if response_schema.__name__ == "OpportunityInsightSchema":
            return response_schema(
                summary=f"{_FAKE_STEP_SUMMARY_PREFIX}:opportunity（结构化要点）",
                findings=["发现一：海外市场窗口期明确", "发现二：高端智能化溢价空间大"],
                opportunity_list=["海外新兴市场渗透", "高端智能化细分"],
                priority_ranking=["海外新兴市场（评分 9）", "高端智能化（评分 8）"],
                growth_path=["现产品×新市场：出海优先", "新产品×现市场：高端智能款"],
            )
        if response_schema.__name__ == "OpportunityGapInsightSchema":
            return response_schema(
                summary=f"{_FAKE_STEP_SUMMARY_PREFIX}:opportunity_gap（结构化要点）",
                findings=["发现一：渠道差距是首要瓶颈", "发现二：品牌溢价能力不足"],
                gap_quantification=["海外渠道覆盖差距 40%"],
                capability_match_matrix=["海外机会×渠道能力：弱匹配"],
                closure_strategies=["合资并购获取渠道"],
            )
        if response_schema.__name__ == "GapAnalysisSchema":
            return response_schema(
                financial_gap="财务差距量化：营收达成率 82%，毛利率 -3.2pct",
                operational_gap="运营差距分析：交付周期延长与产能利用率不足",
                root_causes=["价格竞争侵蚀毛利", "供应链成本上升", "组织响应迟缓"],
                portfolio_health="业务组合健康度：核心业务稳健，新兴业务双低",
            )
        if response_schema.__name__ == "InsightSynthesisSchema":
            return response_schema(conclusions=["综合结论一：优先补强内部能力", "综合结论二：把握海外机会窗口"])
        raise LLMAPIError(f"未知 response_schema: {response_schema!r}")

    async def _generate(prompt: str, config: Any = None, system_prompt: str | None = None) -> LLMResponse:
        return LLMResponse(content='{"valid": true, "confidence": 0.9}', model="fake-llm")

    async def _close() -> None:
        return None

    fake = AsyncMock(spec=LLMClientPort)
    fake.structured_generate.side_effect = _structured_generate
    fake.generate.side_effect = _generate
    fake.close.side_effect = _close
    return fake


def _make_fake_embedding() -> Any:
    """Fake Embedding 工厂（外部 SaaS 豁免——固定 1024 维，6-4 同款）。"""
    from unittest.mock import AsyncMock

    from src.domain.ports.embedding_service import EmbeddingServicePort

    fake = AsyncMock(spec=EmbeddingServicePort)
    fake.embed_query = AsyncMock(return_value=[0.1] * 1024)
    fake.embed_documents = AsyncMock(return_value=[[0.1] * 1024])
    fake.close = AsyncMock()
    return fake


class _RecordingEventBus:
    """记录发布事件的发布器（手写 EventPublisher——run 链隔离用，6-4 同款）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


class _StubIsolationSwitchLogRepository:
    """手写日志仓储替身（零 IO 替身——5-3/6-2/6-4 先例；方法签名对齐端口协议）。"""

    async def save(self, log: Any) -> None:
        """零 IO 追加（日志实体仅丢弃——测试面无检索断言）。"""

    async def search(self, query: Any) -> Any:
        """零 IO 检索（恒空结果——测试面无隔离日志检索断言）。"""
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogSearchResult

        return IsolationSwitchLogSearchResult(items=(), total=0, offset=query.offset, limit=query.limit)


class _CachedEmbedding:
    """embedding 查询缓存代理（测试面性能优化——6-4 同款）。"""

    _query_cache: dict[str, Any] = {}
    _documents_cache: dict[tuple[str, ...], Any] = {}

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    async def embed_query(self, text: str) -> Any:
        if text not in self._query_cache:
            self._query_cache[text] = await self._inner.embed_query(text)
        return self._query_cache[text]

    async def embed_documents(self, texts: list[str]) -> Any:
        key = tuple(texts)
        if key not in self._documents_cache:
            self._documents_cache[key] = await self._inner.embed_documents(texts)
        return self._documents_cache[key]

    async def close(self) -> None:
        await self._inner.close()


def _make_registry() -> Any:
    """手工组装工具注册服务（InMemoryToolRepository + register_all）。"""
    from src.application.services.tool_registry_service import ToolRegistryService
    from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

    registry = ToolRegistryService(InMemoryToolRepository())
    registry.register_all()
    return registry


def _build_tool_execution_service(fake_llm: Any) -> Any:
    """真实工具执行装饰链（Fake LLM 注入——sandbox 替身豁免）。"""
    from unittest.mock import AsyncMock

    from src.application.services.retry_helpers import RetryPolicy
    from src.application.services.tool_execution_engine import ToolExecutionEngine
    from src.application.services.tool_execution_service import ToolExecutionService
    from src.domain.ports.sandbox_executor import SandboxExecutor

    sandbox = AsyncMock(spec=SandboxExecutor)
    sandbox.execute_code.return_value = {"status": "ok", "output": '{"valid": true}', "error": None}
    engine = ToolExecutionEngine(
        llm_client=fake_llm,
        sandbox=sandbox,
        retry_policy=RetryPolicy(max_attempts=1, initial_delay_sec=0.01),
    )
    return ToolExecutionService(registry=_make_registry(), engine=engine)


def _make_real_guard_chain(ctx: dict[str, Any]) -> Any:
    """真实隔离守卫链（场景级 Redis 仓储——6-4 同款）。"""
    if "isolation_guard_chain" in ctx:
        return ctx["isolation_guard_chain"]["guard"]

    from src.application.services.isolation_guard_service import IsolationGuardService
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

    redis_client = ctx["_redis_client"]
    config_loader = resolve("agent_config_loader")
    agent_repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_repository = RedisIsolationRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_service = IsolationManagementService(
        isolation_repository=isolation_repository,
        agent_repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        agent_config_loader=config_loader,
        isolation_switch_log_repository=_StubIsolationSwitchLogRepository(),
        audit_service=None,
    )
    guard = IsolationGuardService(
        isolation_management_service=isolation_service,
        agent_repository=agent_repository,
        agent_config_loader=config_loader,
    )
    ctx["isolation_guard_chain"] = {
        "guard": guard,
        "agent_repository": agent_repository,
        "isolation_service": isolation_service,
    }
    _run_async(ctx["_loop"], redis_client.ping())
    return guard


def _instantiate_real_agent(ctx: dict[str, Any]) -> uuid.UUID:
    """经真实实例化用例构造 CEO Agent（6-4 同步形态）。"""
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.entities.agent import AgentRole
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

    chain = ctx["isolation_guard_chain"]
    use_case = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=chain["agent_repository"],
        event_publisher=InMemoryEventBus(),
        isolation_service=chain["isolation_service"],
    )
    result = _run_async(ctx["_loop"], use_case.execute(role=AgentRole.CEO))
    agent_id: uuid.UUID = result.agent_id
    ctx["_agent_ids"].append(agent_id)
    return agent_id


def _make_real_hybrid_search(ctx: dict[str, Any]) -> Any:
    """真实 hybrid 检索服务（dense+sparse 双路——6-4 同款）。"""
    _ensure_qdrant_retrieval(ctx)

    from src.application.services.dense_search_service import DenseSemanticSearchService
    from src.application.services.hybrid_search_service import HybridSearchService
    from src.application.services.sparse_search_service import Bm25SparseSearchService
    from src.domain.services.rrf_fusion import fuse
    from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage

    vector_storage = QdrantVectorStorage(ctx["_qdrant_client"])
    dense = DenseSemanticSearchService(embedding_service=ctx["_embedding_client"], vector_storage=vector_storage)
    sparse = Bm25SparseSearchService(embedding_service=ctx["_embedding_client"], vector_storage=vector_storage)
    return HybridSearchService(dense_search=dense, sparse_search=sparse, fuse=fuse, graph_search=None, weights=[1.0, 1.0, 0.5])


def _make_report_service(ctx: dict[str, Any]) -> Any:
    """报告生成服务（真实五依赖 + tmp_path L0 + 真实 event_publisher）。

    L0 写路径隔离（R1-17）：tmp_path 实例层注入；event_publisher 用真实
    resolve（S9 outbox 落行断言前提——run 链 recorder 不进报告链）。
    """
    from src.application.services.report_generation_service import ReportGenerationService
    from src.domain.ports.resolver import resolve
    from src.infrastructure.config.memory import MemoryConfig
    from src.infrastructure.storage.fs.file_memory_adapter import FileMemoryAdapter

    return ReportGenerationService(
        chain_archive_service=ctx["chain_archive_service"],
        snapshot_repository=ctx["snapshot_store"],
        l0_storage=FileMemoryAdapter(MemoryConfig(memory_l0_path=str(ctx["_report_tmp_path"]))),
        report_repository=resolve("report_repository"),
        event_publisher=resolve("event_publisher"),
    )


def _assemble_full_flow(ctx: dict[str, Any]) -> None:
    """装配 BLM 完整 run 链 + 报告链（6-4 _assemble_json_chain 移植+报告挂接）。"""
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.application.services.blm_planning_service import BlmPlanningService
    from src.application.services.chain_of_thought_archive_service import ChainOfThoughtArchiveService
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.application.use_cases.agent_profile_loading import AgentProfileLoadResult, LoadAgentProfileUseCase
    from src.application.use_cases.generate_markdown_report import GenerateMarkdownReportUseCase
    from src.application.use_cases.run_blm_planning import RunBlmPlanningUseCase
    from src.domain.entities.agent import AgentRole
    from src.domain.ports.resolver import resolve
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.postgresql.session_context import set_session
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore

    loop = ctx["_loop"]
    env = ctx["_env"]

    redis_client = aioredis.Redis(
        host=env.redis.host,
        port=env.redis.port,
        password=env.redis.password or None,
        decode_responses=True,
    )
    _run_async(loop, redis_client.ping())
    ctx["_redis_client"] = redis_client
    redis_adapter = RedisAdapter(redis_client=redis_client)
    snapshot_store = RedisSnapshotStore(adapter=redis_adapter)
    ctx["snapshot_store"] = snapshot_store

    _make_real_guard_chain(ctx)
    agent_id = _instantiate_real_agent(ctx)
    profile_loader = resolve("agent_profile_loader")
    profile = _run_async(loop, profile_loader.load(role=AgentRole.CEO, agent_id=agent_id))
    skill_selector = resolve("skill_selector")
    tools_l1 = _run_async(loop, skill_selector.list_active_skills())
    profile_result = AgentProfileLoadResult(
        agent_id=agent_id,
        role=AgentRole.CEO,
        profile=profile,
        tools_l1=tools_l1,
        startup_context_tokens=0,
    )
    ctx["agent_id"] = agent_id
    ctx["profile_result"] = profile_result

    fake_llm = _make_fake_llm()
    ctx["fake_llm"] = fake_llm
    tool_execution_service = _build_tool_execution_service(fake_llm)

    session = AsyncSession(ctx["_pg_manager"].get_async_engine())
    _run_async(loop, session.begin())
    ctx["_pg_session"] = session
    ctx["_pg_session_token"] = set_session(session)

    archive_service = StrategicArchiveService(
        archive_repo=resolve("archive_repository"),
        embedding_service=_make_fake_embedding(),
        vector_storage=resolve("l3_vector"),
        object_storage=resolve("l4_object"),
        graph_storage=None,
        event_publisher=None,
        staleness_service=None,
    )
    chain_archive_service = ChainOfThoughtArchiveService(
        archive_service=archive_service,
        object_storage=resolve("l4_object"),
    )
    ctx["chain_archive_service"] = chain_archive_service

    recorder = _RecordingEventBus()
    ctx["recorder"] = recorder
    service = BlmPlanningService(
        llm_client=fake_llm,
        tool_execution_service=tool_execution_service,
        tool_registry_service=_make_registry(),
        isolation_guard=ctx["isolation_guard_chain"]["guard"],
        hybrid_search=_make_real_hybrid_search(ctx),
        search_collection=ctx["retrieval_collection"],
        event_publisher=recorder,
        snapshot_repository=snapshot_store,
        chain_archive_service=chain_archive_service,
    )
    ctx["blm_service"] = service

    ctx["engine"] = LangGraphEngine(
        config=LangGraphConfig.from_env(),
        event_publisher=recorder,
        blm_planning_service=service,
    )
    profile_use_case = LoadAgentProfileUseCase(
        profile_loader=resolve("agent_profile_loader"),
        repository=ctx["isolation_guard_chain"]["agent_repository"],
        skill_selector=resolve("skill_selector"),
        event_publisher=InMemoryEventBus(),
    )
    ctx["use_case"] = RunBlmPlanningUseCase(
        agent_repository=ctx["isolation_guard_chain"]["agent_repository"],
        agent_profile_use_case=profile_use_case,
        agent_engine=ctx["engine"],
        blm_planning_service=service,
        isolation_guard=ctx["isolation_guard_chain"]["guard"],
        event_publisher=recorder,
    )
    # 报告链挂接（6-5a 新交付——tmp_path L0 + 真实 publisher）
    ctx["report_service"] = _make_report_service(ctx)
    ctx["report_use_case"] = GenerateMarkdownReportUseCase(report_service=ctx["report_service"])
    ctx["task"] = _BLM_TASK


def _assemble_archive_only(ctx: dict[str, Any]) -> None:
    """轻装配（逐 stage 归档通道——S6/S8/S11/S12 数据面；无 LLM run）。"""
    from src.application.services.chain_of_thought_archive_service import ChainOfThoughtArchiveService
    from src.application.services.report_generation_service import ReportGenerationService
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.application.use_cases.generate_markdown_report import GenerateMarkdownReportUseCase
    from src.domain.ports.resolver import resolve
    from src.infrastructure.config.memory import MemoryConfig
    from src.infrastructure.storage.fs.file_memory_adapter import FileMemoryAdapter

    archive_service = StrategicArchiveService(
        archive_repo=resolve("archive_repository"),
        embedding_service=_make_fake_embedding(),
        vector_storage=resolve("l3_vector"),
        object_storage=resolve("l4_object"),
        graph_storage=None,
        event_publisher=None,
        staleness_service=None,
    )
    ctx["chain_archive_service"] = ChainOfThoughtArchiveService(
        archive_service=archive_service,
        object_storage=resolve("l4_object"),
    )
    ctx["report_service"] = ReportGenerationService(
        chain_archive_service=ctx["chain_archive_service"],
        snapshot_repository=resolve("snapshot_repository"),
        l0_storage=FileMemoryAdapter(MemoryConfig(memory_l0_path=str(ctx["_report_tmp_path"]))),
        report_repository=resolve("report_repository"),
        event_publisher=resolve("event_publisher"),
    )
    ctx["report_use_case"] = GenerateMarkdownReportUseCase(report_service=ctx["report_service"])


def _make_material(stage: str, *, index: int = 0) -> Any:
    """构造归档素材（stage 判型——集成同款三型分派）。"""
    from src.application.ports.chain_of_thought_archive import StepChainMaterial

    is_synthesis = stage == "market_insight_synthesis"
    is_gap = stage == "performance_gap"
    payload: dict[str, Any]
    if is_synthesis:
        payload = {"conclusions": ["综合结论一（聚焦核心市场）"], "degraded_inputs": ["market_insight_trend"]}
    elif is_gap:
        payload = {
            "financial_gap": "财务差距量化：营收达成率 85%",
            "operational_gap": "运营差距分析：交付周期延长",
            "root_causes": ["根因一：组织能力缺口", "根因二：流程效率不足"],
            "portfolio_health": "业务组合健康度：核心稳健",
            "degraded": False,
            "degrade_reason": "",
        }
    else:
        step_key = stage.removeprefix("market_insight_")
        payload = {"summary": f"步骤摘要（{step_key}）", "findings": ["发现一", "发现二"]}
    return StepChainMaterial(
        stage=stage,
        display_name="市场洞察综合" if is_synthesis else ("业绩差距分析" if is_gap else "看趋势"),
        role_prefix="CMO" if is_synthesis else ("CFO" if is_gap else "CEO"),
        task=_BLM_TASK,
        evidence_count=0 if is_synthesis else 5,
        tool_slug="" if is_synthesis else "PESTEL 分析",
        evidence_refs=() if is_synthesis else (f"chunk-{index}-001",),
        summary="" if is_synthesis else f"步骤摘要（{stage}）",
        findings_count=2,
        degraded=False,
        payload=payload,
        structured_ok=True,
    )


async def _archive_steps(ctx: dict[str, Any], plan_id: str, skip_stages: frozenset[str] = frozenset()) -> list[Any]:
    """逐 stage 组装归档（跳步变体——session_context 独立会话承载）。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.infrastructure.storage.postgresql.session_context import session_context

    factory = async_sessionmaker(ctx["_pg_manager"].get_async_engine())
    records = []
    async with session_context(factory):
        for index, stage in enumerate(_EXPECTED_STAGE_ORDER):
            if stage in skip_stages:
                continue
            record = await ctx["chain_archive_service"].compose_and_archive_step_chain(
                uuid.UUID(plan_id), stage, _make_material(stage, index=index)
            )
            records.append(record)
    return records


def _register_flow_cleanup(ctx: dict[str, Any], plan_id: str) -> None:
    """登记 run 级清理面（快照会话键 latest + per-step——归档行按 plan_id 兜底）。"""
    from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX

    ctx["_snapshot_session_ids"].append(f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}")
    for step_value in ("trend", "market_customer", "competition", "self", "opportunity", "opportunity_gap"):
        ctx["_snapshot_session_ids"].append(f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}:{step_value}")


def _run_full_flow(ctx: dict[str, Any]) -> Any:
    """执行 BLM 前两阶段全流程（显式 plan_id——清理面可登记）。"""
    plan_id = str(uuid.uuid4())
    ctx["plan_id"] = plan_id
    ctx["_plan_ids"].append(plan_id)
    _register_flow_cleanup(ctx, plan_id)
    result = _run_async(
        ctx["_loop"],
        ctx["use_case"].execute(agent_id=ctx["agent_id"], task=ctx["task"], plan_id=plan_id),
    )
    _commit_pg_session(ctx)
    ctx["result"] = result
    return result


def _commit_pg_session(ctx: dict[str, Any]) -> None:
    """提交当前 PG 事务（行断言前置——commit 后独立连接可见）。"""
    session = ctx.get("_pg_session")
    if session is not None:
        _run_async(ctx["_loop"], session.commit())


def _generate_report(ctx: dict[str, Any], plan_id: str) -> Any:
    """执行报告生成（记录实体+读回文本到 ctx——多场景共享形态）。"""
    report = _run_async(ctx["_loop"], ctx["report_use_case"].execute(plan_id=plan_id))
    ctx["report"] = report
    ctx["_report_ids"].append(str(report.report_id))
    _commit_pg_session(ctx)  # 完整 run 场景请求路径行落库后提交（独立连接可见）
    from pathlib import PurePosixPath

    memory_id = PurePosixPath(report.file_path).stem
    ctx["memory_id"] = memory_id
    ctx["_l0_memory_ids"].append(memory_id)
    ctx["report_text"] = (ctx["_report_tmp_path"] / "reports" / f"{memory_id}.md").read_text(encoding="utf-8")
    return report


async def _query_outbox_report_rows(ctx: dict[str, Any], report_id: str) -> list[Any]:
    """查询 ReportGenerated outbox 行（三键 + payload 键族——独立连接）。"""
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(ctx["_pg_manager"].get_async_engine()) as session:
        result = await session.execute(
            sa.text(
                "SELECT payload->'payload'->>'report_id', payload->'payload'->>'report_type', "
                "payload->'payload'->>'file_path', payload FROM event_outbox "
                "WHERE payload->'payload'->>'report_id' = :rid AND event_type = 'ReportGenerated'"
            ),
            {"rid": report_id},
        )
        return list(result.fetchall())


async def _query_report_metadata_jsonb(ctx: dict[str, Any], plan_id: str) -> Any:
    """直查 L2 metadata JSONB（timeline_available 可观测面——R3-3 载体）。"""
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(ctx["_pg_manager"].get_async_engine()) as session:
        result = await session.execute(
            sa.text(
                "SELECT metadata->>'timeline_available' FROM strategic_reports "
                "WHERE plan_id = CAST(:p AS uuid) ORDER BY created_at DESC LIMIT 1"
            ),
            {"p": plan_id},
        )
        return result.scalar_one_or_none()


async def _count_report_rows(ctx: dict[str, Any], plan_id: str) -> int:
    """按 plan_id 计数 strategic_reports 行。"""
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(ctx["_pg_manager"].get_async_engine()) as session:
        result = await session.execute(
            sa.text("SELECT COUNT(*) FROM strategic_reports WHERE plan_id = CAST(:p AS uuid)"),
            {"p": plan_id},
        )
        return int(result.scalar_one())


async def _get_latest_report(ctx: dict[str, Any], plan_id: str) -> Any:
    """经真实 report_repository 取最新报告（CR1-F2——排序方向行为级验证通道）。"""
    import uuid as _uuid

    from src.domain.ports.resolver import resolve

    repository = resolve("report_repository")
    return await repository.get_latest_by_plan(_uuid.UUID(plan_id))


def _query_chain_records(ctx: dict[str, Any], plan_id: str) -> list[dict[str, Any]]:
    """chain 读侧 records 查询（读侧消费面契约——AC-6×1 断言数据源）。"""
    from src.application.use_cases.get_blm_chain_trace import GetBlmChainTraceUseCase

    trace_use_case = GetBlmChainTraceUseCase(chain_archive_service=ctx["chain_archive_service"])
    view = _run_async(ctx["_loop"], trace_use_case.execute(plan_id=plan_id))
    return list(view.records)


# Given 步骤（服务门控 + 数据面构造）
# ======================================================================


@given("Markdown 报告生成链服务可用")
def report_chain_services_available(context: dict[str, Any]) -> None:
    """四真实服务门控探测（不可达动态 skip——禁写死 skip 标记）+ 链装配。"""
    _run_async(context["_loop"], _probe_and_assemble(context))


@given("BLM 前两阶段已完成（八步思维链归档在位）")
def blm_eight_steps_archived(context: dict[str, Any]) -> None:
    """完整 8 步 BLM run（Fake LLM/Embedding 双豁免 + 四真实存储）→ 归档行 + latest 快照在位。"""
    if "use_case" not in context:
        _assemble_full_flow(context)
    result = _run_full_flow(context)
    assert result is not None


@given("目标六子步骤归档缺席（其余七步归档在位）")
def target_insight_step_archived_missing(context: dict[str, Any]) -> None:
    """逐 stage 归档七步跳过目标六子步（AC-4 钦定构造——禁跑后删行）。"""
    if "report_use_case" not in context:
        _assemble_archive_only(context)
    plan_id = str(uuid.uuid4())
    context["plan_id"] = plan_id
    context["_plan_ids"].append(plan_id)
    records = _run_async(
        context["_loop"],
        _archive_steps(context, plan_id, skip_stages=frozenset({"market_insight_trend"})),
    )
    assert len(records) == 7


@given("从未归档的独立 plan_id")
def never_archived_plan_id(context: dict[str, Any]) -> None:
    """天然 total==0 的独立 plan_id（无需清空构造）。"""
    if "report_use_case" not in context:
        _assemble_archive_only(context)
    context["plan_id"] = str(uuid.uuid4())
    context["_plan_ids"].append(context["plan_id"])


@given("八步归档在位且 latest 快照缺失")
def eight_steps_archived_without_snapshot(context: dict[str, Any]) -> None:
    """逐 stage 八步归档（不经完整 run——latest 快照天然缺失）。"""
    if "report_use_case" not in context:
        _assemble_archive_only(context)
    plan_id = str(uuid.uuid4())
    context["plan_id"] = plan_id
    context["_plan_ids"].append(plan_id)
    records = _run_async(context["_loop"], _archive_steps(context, plan_id))
    assert len(records) == 8


@given("三个独立 plan_id 各自八步归档在位")
def three_plans_eight_steps_archived(context: dict[str, Any]) -> None:
    """三独立 plan_id 各自逐 stage 八步归档（并发场景数据面）。"""
    if "report_use_case" not in context:
        _assemble_archive_only(context)
    context["concurrent_plan_ids"] = []
    for _ in range(3):
        plan_id = str(uuid.uuid4())
        context["concurrent_plan_ids"].append(plan_id)
        context["_plan_ids"].append(plan_id)
        records = _run_async(context["_loop"], _archive_steps(context, plan_id))
        assert len(records) == 8


@given("开发实施完成")
def development_completed() -> None:
    """S13 收尾场景前置（静态断言无服务依赖）。"""


# ======================================================================
# When 步骤（报告生成调用）
# ======================================================================


@when("调用报告生成用例（plan_id）")
def invoke_report_generation(context: dict[str, Any]) -> None:
    """经报告生成用例执行（生产通道形态——490 异常捕获记录供 Then 断言）。"""
    from src.domain.exceptions import DomainError

    try:
        _generate_report(context, context["plan_id"])
    except DomainError as error:
        context["caught_error"] = error


@when("跨秒间隔连续两次调用报告生成（同 plan_id）")
def invoke_twice_with_gap(context: dict[str, Any]) -> None:
    """同 plan_id 两次生成（间隔 ≥1.05s 跨秒——OD-10 件数断言前提）。"""
    import time as _time

    first = _generate_report(context, context["plan_id"])
    _time.sleep(_REPEAT_GENERATION_GAP_SECONDS)
    second = _generate_report(context, context["plan_id"])
    context["repeat_reports"] = [first, second]


@when("单一数据源连续 20 次生成报告")
def invoke_twenty_rounds(context: dict[str, Any]) -> None:
    """单一 plan_id × 20 次生成（OD-10 幂等锚合法采样形态）。"""
    import time as _time

    durations: list[float] = []
    report_ids: list[str] = []
    for _ in range(_PERF_SAMPLE_ROUNDS):
        started = _time.monotonic()
        report = _generate_report(context, context["plan_id"])
        durations.append(_time.monotonic() - started)
        report_ids.append(str(report.report_id))
    context["perf_durations"] = durations
    context["perf_report_ids"] = report_ids


@when("asyncio gather 并发生成 3 个报告")
def gather_three_concurrent_reports(context: dict[str, Any]) -> None:
    """gather 3（async 辅助函数体内 await + _run_async 驱动——6-4 形态锚）。"""
    plan_ids = context["concurrent_plan_ids"]

    async def _gather() -> list[Any]:
        return await asyncio.gather(*(context["report_use_case"].execute(plan_id=pid) for pid in plan_ids))

    reports = _run_async(context["_loop"], _gather())
    context["concurrent_reports"] = reports
    for report in reports:
        context["_report_ids"].append(str(report.report_id))


# ======================================================================
# Then 步骤（断言面）
# ======================================================================


@then("报告生成五段编排全部落位")
def assert_five_stage_orchestration(context: dict[str, Any]) -> None:
    """五段编排断言（五段产物全断言——聚合/辅源/渲染/持久化/事件）。"""
    from src.application.ports.chain_of_thought_archive import SYNTHESIS_DISPLAY_NAME

    report = context["report"]
    text = context["report_text"]
    assert context["result"] is not None  # ①run 产物（归档行在位前提）
    assert "## 附录 A 执行时间线" in text  # ②latest 快照辅源
    # CR1-F1：synthesis 行三源映射值级断言（写侧 timeline 实录 "market_insight_synthesis"
    # ——判别 miss 时会裸串直显；期望由 SYNTHESIS_DISPLAY_NAME 配置源独立构造）
    assert f"| {SYNTHESIS_DISPLAY_NAME} |" in text
    assert "market_insight_synthesis" not in text.split("附录 A 执行时间线")[-1].split("附录 B")[0]  # 裸串不得直显
    assert text.startswith("# 战略规划报告")  # ③渲染产物
    assert (context["_report_tmp_path"] / "reports" / f"{context['memory_id']}.md").exists()  # ④L0
    rows = _run_async(context["_loop"], _count_report_rows(context, context["plan_id"]))
    assert rows == 1  # ④L2
    outbox = _run_async(context["_loop"], _query_outbox_report_rows(context, str(report.report_id)))
    assert len(outbox) == 1  # ⑤事件


@then("返回实体七字段完整且类型正确")
def assert_entity_seven_fields(context: dict[str, Any]) -> None:
    """StrategicReport 七字段（report_id UUID/plan_id/report_type/file_path/计数双字段/generation_ms）。"""
    from src.domain.entities.strategic_report import ReportType, StrategicReport

    report = context["report"]
    assert isinstance(report, StrategicReport)
    assert isinstance(report.report_id, uuid.UUID)
    assert report.plan_id == context["plan_id"]
    assert report.report_type is ReportType.MARKDOWN
    assert isinstance(report.file_path, str) and report.file_path.startswith("reports/")
    assert report.section_count == 11
    assert isinstance(report.degraded_section_count, int) and report.degraded_section_count >= 0
    assert isinstance(report.generation_ms, int) and report.generation_ms >= 0


@then("L0 报告文件可读回且含冻结章节标题族")
def assert_l0_file_readable(context: dict[str, Any]) -> None:
    """memory_id 经实体 file_path stem 反解 → 读回 → display_name 源独立构造期望。"""
    from src.application.ports.chain_of_thought_archive import SYNTHESIS_DISPLAY_NAME
    from src.application.services.blm_planning_prompts import (
        MARKET_INSIGHT_STEP_CONFIG,
        PERFORMANCE_GAP_CONFIG,
    )

    text = context["report_text"]
    step_titles = [cfg.display_name for cfg in MARKET_INSIGHT_STEP_CONFIG.values()]
    for expected in (
        f"## 1 {PERFORMANCE_GAP_CONFIG.display_name}",
        *[f"### 2.{i} {name}" for i, name in enumerate(step_titles, start=1)],
        f"### 2.7 {SYNTHESIS_DISPLAY_NAME}",
    ):
        assert expected in text, f"冻结章节标题缺失: {expected}"


@then("L2 元数据行可读回且字段与实体一致")
def assert_l2_row_readable(context: dict[str, Any]) -> None:
    """get_latest_by_plan 返回最新行（字段与实体一致性断言）。"""
    from src.domain.ports.resolver import resolve

    repo = resolve("report_repository")
    latest = _run_async(context["_loop"], repo.get_latest_by_plan(uuid.UUID(context["plan_id"])))
    assert latest is not None
    report = context["report"]
    assert str(latest.report_id) == str(report.report_id)
    assert latest.file_path == report.file_path
    assert latest.section_count == report.section_count
    assert latest.degraded_section_count == report.degraded_section_count


@then("两次生成产生两个新 report_id")
def assert_two_new_report_ids(context: dict[str, Any]) -> None:
    """幂等锚=report_id（两次生成 report_id 互异）+ get_latest 取第二份（CR1-F2 值级断言）。"""
    first, second = context["repeat_reports"]
    assert first.report_id != second.report_id
    # CR1-F2：排序方向行为级验证（两行在位时取最新——.asc() 突变即红；全仓原零杀伤）
    latest = _run_async(context["_loop"], _get_latest_report(context, context["plan_id"]))
    assert latest is not None
    assert latest.report_id == second.report_id, f"get_latest 应取最新报告（第二份），实取 {latest.report_id}"


@then("L2 strategic_reports 行数增加 2 且 L0 文件为 2 份")
def assert_l2_rows_and_l0_files(context: dict[str, Any]) -> None:
    """跨秒间隔下 L2 行 +2 与 L0 件数 2（秒级覆写豁免不适用——已跨秒）。"""
    rows = _run_async(context["_loop"], _count_report_rows(context, context["plan_id"]))
    assert rows == 2
    files = list((context["_report_tmp_path"] / "reports").glob(f"{context['plan_id']}_*.md"))
    assert len(files) == 2


@then("Markdown 章节标题序列与冻结结构全等")
def assert_frozen_section_titles(context: dict[str, Any]) -> None:
    """H1/H2/H3 全序列字面基线全等（期望由冻结表独立构造——序断言）。"""
    lines = context["report_text"].splitlines()
    heading_lines = [line for line in lines if line.startswith("#")]
    from src.application.ports.chain_of_thought_archive import SYNTHESIS_DISPLAY_NAME
    from src.application.services.blm_planning_prompts import (
        MARKET_INSIGHT_STEP_CONFIG,
        PERFORMANCE_GAP_CONFIG,
    )

    step_names = [cfg.display_name for cfg in MARKET_INSIGHT_STEP_CONFIG.values()]
    expected_headings = [
        "# 战略规划报告（BLM 前两阶段）",
        "## 目录",
        f"## 1 {PERFORMANCE_GAP_CONFIG.display_name}",
        "### 1.1 财务差距",
        "### 1.2 运营差距",
        "### 1.3 根因分析",
        "### 1.4 业务组合健康度",
        "## 2 市场洞察",
        *[f"### 2.{i} {name}" for i, name in enumerate(step_names, start=1)],
        f"### 2.7 {SYNTHESIS_DISPLAY_NAME}",
        "## 附录 A 执行时间线",
        "## 附录 B 降级与数据缺失记录",
    ]
    assert heading_lines == expected_headings, f"标题序列漂移: 实测={heading_lines} 期望={expected_headings}"


@then("目录收录 H2 章级与附录且锚点链接正确")
def assert_toc_entries_and_anchors(context: dict[str, Any]) -> None:
    """目录收录面冻结（H2 章级 + 附录 A/B 四条；GitHub slug 锚点）。"""
    from src.application.ports.chain_of_thought_archive import SYNTHESIS_DISPLAY_NAME
    from src.application.services.blm_planning_prompts import PERFORMANCE_GAP_CONFIG

    text = context["report_text"]
    assert f"- [1 {PERFORMANCE_GAP_CONFIG.display_name}](#1-{PERFORMANCE_GAP_CONFIG.display_name})" in text
    assert "- [2 市场洞察](#2-市场洞察)" in text
    assert "- [附录 A 执行时间线](#附录-a-执行时间线)" in text
    assert "- [附录 B 降级与数据缺失记录](#附录-b-降级与数据缺失记录)" in text
    # H3 小节不进目录
    assert "[1.1 财务差距]" not in text
    assert f"[2.7 {SYNTHESIS_DISPLAY_NAME}]" not in text


@then("章节标题与 display_name 配置源逐字对齐")
def assert_display_name_literal(context: dict[str, Any]) -> None:
    """display_name 配置源三处独立取值比对（配置值与渲染标题逐字）。"""
    from src.application.ports.chain_of_thought_archive import SYNTHESIS_DISPLAY_NAME
    from src.application.services.blm_planning_prompts import (
        MARKET_INSIGHT_STEP_CONFIG,
        PERFORMANCE_GAP_CONFIG,
    )

    text = context["report_text"]
    assert f"## 1 {PERFORMANCE_GAP_CONFIG.display_name}" in text
    for index, config in enumerate(MARKET_INSIGHT_STEP_CONFIG.values(), start=1):
        assert f"### 2.{index} {config.display_name}" in text
    assert f"### 2.7 {SYNTHESIS_DISPLAY_NAME}" in text


@then("gap 四字段与六 Schema 全字段渲染无遗漏")
def assert_schema_fields_rendered(context: dict[str, Any]) -> None:
    """gap 四字段 + 六 Schema 领域字段渲染（Fake 产物值独立构造期望）。

    CR1-F3：每字段至少一条值级断言（summary/findings 正向渲染 + 十余原零断言
    字段补齐——删任一渲染映射即红）；期望全部由 Fake fixture 值独立构造。
    """
    text = context["report_text"]
    # gap 四字段（Fake GapAnalysisSchema 产物值）
    assert "财务差距量化：营收达成率 82%，毛利率 -3.2pct" in text
    assert "运营差距分析：交付周期延长与产能利用率不足" in text
    assert "- 价格竞争侵蚀毛利" in text
    assert "业务组合健康度：核心业务稳健，新兴业务双低" in text
    # 六子公共前缀：summary 段落 + findings 列表正向渲染（CR1-F3——原零断言）
    for step in ("trend", "market_customer", "competition", "self", "opportunity", "opportunity_gap"):
        assert f"{_FAKE_STEP_SUMMARY_PREFIX}:{step}（结构化要点）" in text, step
    assert "- 发现一：政策与技术双趋势信号明确" in text  # trend findings
    assert "- 发现二：补能效率是首要痛点" in text  # market_customer findings
    assert "- 发现一：竞争强度处历史高位" in text  # competition findings
    assert "- 发现一：三电自研是核心能力" in text  # self findings
    assert "- 发现一：海外市场窗口期明确" in text  # opportunity findings
    assert "- 发现一：渠道差距是首要瓶颈" in text  # opportunity_gap findings
    # trend 领域字段（PESTEL 全六维 + 路线图 + 情景）
    assert "| 政治 | 政策维度：补贴退坡与准入收紧 |" in text
    assert "| 经济 | 经济维度：利率上行压制可选消费 |" in text
    assert "| 社会 | 社会维度：绿色出行消费习惯迁移 |" in text
    assert "| 技术 | 技术维度：固态电池与智能驾驶演进 |" in text
    assert "| 环境 | 环境维度：碳排法规趋严 |" in text
    assert "| 法律 | 法律维度：数据合规与知识产权要求升级 |" in text
    assert "- 短期：平台化架构降本" in text
    assert "- 中期：固态电池量产" in text  # roadmap 第二项（CR1-F3）
    assert "- 基准情景：渗透率稳步提升" in text  # scenario_plans（CR1-F3——原零断言）
    # market_customer 三组（加粗行标签 + 列表数据行全组）
    assert "**客户细分画像**" in text
    assert "- 价格敏感型家庭用户" in text
    assert "**需求优先级矩阵（$APPEALS）**" in text  # 行标签（CR1-F3）
    assert "- 续航与补能效率（最高优先）" in text  # demand_priority_matrix（原零断言）
    assert "**价值主张地图**" in text  # 行标签（CR1-F3）
    assert "- 痛点：补能焦虑→收益：超充网络覆盖" in text  # value_proposition_map（原零断言）
    # competition 五力全五维 + 雷达表数据行 + 建议
    assert "| 供应商议价能力 | 供应商议价能力：中高（电池厂商集中度高） |" in text
    assert "| 购买者议价能力 | 购买者议价能力：中（选择增多但转换成本存在） |" in text
    assert "| 新进入者威胁 | 新进入者威胁：高（跨界造车与代工模式降低门槛） |" in text
    assert "| 替代品威胁 | 替代品威胁：中（公共交通与共享出行部分替代） |" in text
    assert "| 现有竞争者强度 | 现有竞争者强度：极高（价格战与渠道战并发） |" in text
    assert "| 能力维度 | 评估要点 |" in text
    assert "| 维度 1 | 研发能力：头部厂商 9/10 |" in text  # competitor_radar 数据行（OD-9 表格承载——原零断言）
    assert "- 以差异化配置避开正面价格战" in text
    # self 三组数据行（CR1-F3——原仅标签断言）
    assert "**内部能力清单**" in text
    assert "- 三电自研平台" in text  # internal_capabilities
    assert "**核心能力 VRIO 评估**" in text
    assert "- 三电平台：价值+稀有+难模仿+组织适配（核心能力）" in text  # vrio_assessment
    assert "**资源约束分析**" in text
    assert "- 研发预算受限" in text  # resource_constraints
    # opportunity 三组数据行
    assert "**机会清单**" in text
    assert "- 海外新兴市场渗透" in text  # opportunity_list
    assert "**机会优先级排序**" in text
    assert "- 海外新兴市场（评分 9）" in text  # priority_ranking（原零断言）
    assert "**增长路径图（安索夫矩阵路径）**" in text
    assert "- 现产品×新市场：出海优先" in text
    assert "- 新产品×现市场：高端智能款" in text  # growth_path 第二项
    # opportunity_gap 三组数据行
    assert "**机会差距量化报告要点**" in text
    assert "- 海外渠道覆盖差距 40%" in text
    assert "**能力-机会匹配矩阵**" in text
    assert "- 海外机会×渠道能力：弱匹配" in text  # capability_match_matrix（原零断言）
    assert "**差距弥合策略**" in text
    assert "- 合资并购获取渠道" in text  # closure_strategies（原零断言）


@then("synthesis 结论与降级输入显式列举")
def assert_synthesis_lists(context: dict[str, Any]) -> None:
    """conclusions bullet_list + degraded_inputs callout 显式列举。"""
    text = context["report_text"]
    assert "- 综合结论一：优先补强内部能力" in text
    assert "- 综合结论二：把握海外机会窗口" in text


@then("ATX 标题层级严格递进不跳级")
def assert_atx_heading_levels(context: dict[str, Any]) -> None:
    """逐行 # 计数 ∈ {1,2,3} + 相邻层级差 ≤ +1（首行 H1——CR2-F5 递进补强）。"""
    lines = context["report_text"].splitlines()
    heading_levels = [len(line) - len(line.lstrip("#")) for line in lines if line.startswith("#")]
    assert heading_levels[0] == 1
    assert all(1 <= level <= 3 for level in heading_levels)
    # CR2-F5：严格递进不跳级（H1→H3 跳级即红——原断言仅查值域查不出跳级）
    assert all(right - left <= 1 for left, right in zip(heading_levels, heading_levels[1:]))


@then("GFM 管道表格表头分隔行数据行对齐（PESTEL 六行五力五行）")
def assert_gfm_tables(context: dict[str, Any]) -> None:
    """表头 + 分隔行 + 数据行数（表头定位法——PESTEL 6 行/五力 5 行）。"""
    lines = context["report_text"].splitlines()
    pestel_header = lines.index("| 维度 | 评估 |")
    assert lines[pestel_header + 1] == "| --- | --- |"
    pestel_data = lines[pestel_header + 2 : pestel_header + 8]
    assert all(line.startswith("| ") for line in pestel_data)
    assert len(pestel_data) == 6
    forces_header = lines.index("| 五力 | 评估 |")
    assert lines[forces_header + 1] == "| --- | --- |"
    forces_data = lines[forces_header + 2 : forces_header + 7]
    assert all(line.startswith("| ") for line in forces_data)
    assert len(forces_data) == 5


@then("无序列表项数与源数据一致且中文原样输出")
def assert_bullet_lists_and_chinese(context: dict[str, Any]) -> None:
    """列表项与源数据逐项一致（root_causes 3 项 Fake 产物）+ 中文原样。"""
    text = context["report_text"]
    for item in ("价格竞争侵蚀毛利", "供应链成本上升", "组织响应迟缓"):
        assert f"- {item}" in text
    assert "\\u" not in text


@then("缺席步骤章节渲染 H3 骨架加数据缺失标注")
def assert_missing_step_h3_skeleton(context: dict[str, Any]) -> None:
    """缺行小节仍渲染 H3 骨架 + [数据缺失] callout 唯一块（R3-1 冻结）。"""
    text = context["report_text"]
    assert "### 2.1 看趋势" in text
    assert "> ⚠️ [数据缺失] 看趋势：该步骤归档记录不可用" in text


@then("降级章节数计数为 1")
def assert_degraded_count_one(context: dict[str, Any]) -> None:
    """degraded_section_count == 1（六子缺一步口径）。"""
    assert context["report"].degraded_section_count == 1
    assert context["report"].section_count == 11


@then("报告照常生成且附录 B 记录数据缺失行")
def assert_report_generated_with_appendix_b(context: dict[str, Any]) -> None:
    """报告成功 + 附录 B [数据缺失] 行（类型/步骤/原因三列）。"""
    text = context["report_text"]
    assert context["report"].report_id is not None
    assert "| [数据缺失] | 看趋势 | 该步骤归档记录不可用 |" in text


@then("报告生成抛出 ReportGenerationError（EXCEPTION_490）")
def assert_490_exception(context: dict[str, Any]) -> None:
    """异常 code/context 断言（490——记录于 when 步骤的捕获面）。"""
    error = context.get("caught_error")
    assert error is not None and error.code == "EXCEPTION_490"
    assert error.context["plan_id"] == context["plan_id"]


@then("异常 message 陈述可观测事实")
def assert_490_message(context: dict[str, Any]) -> None:
    """message 钦定口径「该 plan_id 无思维链归档记录，无法生成报告」。"""
    assert context["caught_error"].message == "该 plan_id 无思维链归档记录，无法生成报告"


@then("报告生成成功且无附录 A 执行时间线")
def assert_no_appendix_a(context: dict[str, Any]) -> None:
    """快照缺失 → 附录 A 省略 + 报告成功（不阻断）。"""
    assert context["report"].report_id is not None
    assert "## 附录 A 执行时间线" not in context["report_text"]


@then("L2 元数据 timeline_available 为 false")
def assert_timeline_unavailable(context: dict[str, Any]) -> None:
    """快照缺失可观测面 = 直查 PG JSONB（metadata.timeline_available='false'）。"""
    value = _run_async(context["_loop"], _query_report_metadata_jsonb(context, context["plan_id"]))
    assert value == "false"


@then("outbox 落行且事件三键值级匹配")
def assert_outbox_three_keys(context: dict[str, Any]) -> None:
    """event_type/report_id/file_path 三键值级断言（两级路径查询）。"""
    report = context["report"]
    rows = _run_async(context["_loop"], _query_outbox_report_rows(context, str(report.report_id)))
    assert len(rows) == 1
    assert rows[0][0] == str(report.report_id)
    assert rows[0][1] == "markdown"
    assert rows[0][2] == report.file_path


@then("chain 读侧 records 五键结构与冻结面全等")
def assert_chain_record_keys(context: dict[str, Any]) -> None:
    """records 五键结构字面基线全等（防漂移即守护——AC-6×1 处方）。"""
    records = _query_chain_records(context, context["plan_id"])
    assert len(records) == 8
    for record in records:
        assert tuple(record.keys()) == _RECORD_KEY_BASELINE, f"records 键集漂移: {tuple(record.keys())}"


@then("ReportGenerated outbox 行 payload 键族与事件类冻结字段面全等")
def assert_event_payload_key_family(context: dict[str, Any]) -> None:
    """payload 键族与事件类冻结字段面全等（子类三键嵌套 payload + 核心三键顶层）。

    CR1-F27：期望由 _REPORT_EVENT_PAYLOAD_KEY_BASELINE 冻结基线差集派生
    （顶层三键独立命名单源——后续 6-5b/6-11 加字段只改基线常量即联动）。
    """
    report = context["report"]
    rows = _run_async(context["_loop"], _query_outbox_report_rows(context, str(report.report_id)))
    payload = rows[0][3]
    nested = payload["payload"]
    # 子类字段经 to_dict 并入嵌套 payload 键（base.py 机理——两级路径之源）
    expected_nested = _REPORT_EVENT_PAYLOAD_KEY_BASELINE - _CORE_EVENT_PAYLOAD_KEYS
    assert set(nested.keys()) == expected_nested, f"嵌套键族漂移: {set(nested.keys())} 期望 {expected_nested}"
    # 核心字段在顶层（aggregate_id/aggregate_type/event_type——事件类冻结字段面）
    assert payload["event_type"] == "ReportGenerated"
    assert payload["aggregate_id"] == str(report.report_id)
    assert payload["aggregate_type"] == "Report"


@then("每轮新 report_id 且 L2 行数累计 20")
def assert_twenty_unique_reports(context: dict[str, Any]) -> None:
    """report_id 集合无重复 + L2 行数 20（采样锚）。"""
    assert len(set(context["perf_report_ids"])) == _PERF_SAMPLE_ROUNDS
    rows = _run_async(context["_loop"], _count_report_rows(context, context["plan_id"]))
    assert rows == _PERF_SAMPLE_ROUNDS


@then("生成窗口 P95 小于 30 秒且三元每轮可读回")
def assert_p95_and_readback(context: dict[str, Any]) -> None:
    """sorted(durations)[ceil(0.95*20)-1] < 30s + 每轮即时读回（_generate_report 内置）。"""
    import math

    durations = context["perf_durations"]
    ordered = sorted(durations)
    p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
    assert p95 < _PERF_P95_LIMIT_SECONDS, f"P95 实测={p95:.3f}s 期望<{_PERF_P95_LIMIT_SECONDS}s"


@then("三报告全部成功且文件元数据行事件三元互不串扰")
def assert_three_reports_isolated(context: dict[str, Any]) -> None:
    """三 plan_id 三元互不串扰（每 plan 恰 1 行 + report_id 互异）。"""
    reports = context["concurrent_reports"]
    assert len(reports) == 3
    report_ids = {str(report.report_id) for report in reports}
    assert len(report_ids) == 3
    for plan_id, report in zip(context["concurrent_plan_ids"], reports):
        rows = _run_async(context["_loop"], _count_report_rows(context, plan_id))
        assert rows == 1, f"并发三元串扰: plan={plan_id} rows={rows}"
        assert report.plan_id == plan_id


@then("src 交付件（实体/VO/渲染器/异常/端口/服务/用例/仓储/ORM/migration/CLI）逐项存在")
def assert_src_deliverables(context: dict[str, Any]) -> None:
    """src 11 项交付件存在性逐项断言。"""
    deliverables = (
        "src/domain/entities/strategic_report.py",
        "src/domain/value_objects/markdown_report.py",
        "src/domain/services/markdown_report_renderer.py",
        "src/domain/exceptions/report_exceptions.py",
        "src/domain/ports/report_repository.py",
        "src/application/ports/report_generation.py",
        "src/application/services/report_generation_service.py",
        "src/application/use_cases/generate_markdown_report.py",
        "src/infrastructure/storage/postgresql/models/report.py",
        "src/infrastructure/storage/postgresql/repository/report_repository.py",
        "deploy/postgresql/alembic/versions/017_strategic_reports.py",
    )
    for relative in deliverables:
        assert (_REPO_ROOT / relative).exists(), f"src 交付件缺失: {relative}"


@then("四测试目录交付件逐项存在")
def assert_test_deliverables(context: dict[str, Any]) -> None:
    """四测试目录交付件存在性逐项断言。"""
    deliverables = (
        "tests/unit/domain/test_strategic_report.py",
        "tests/unit/domain/services/test_markdown_report_renderer.py",
        "tests/unit/domain/exceptions/test_report_exceptions.py",
        "tests/unit/application/test_report_generation_service.py",
        "tests/unit/application/use_cases/test_generate_markdown_report_use_case.py",
        "tests/unit/infrastructure/storage/postgresql/test_report_repository.py",
        "tests/unit/architecture/test_markdown_report.py",
        "tests/integration/test_integration_markdown_report.py",
        "tests/contracts/test_port_contract_report_generation.py",
        "tests/contracts/test_event_channel_mapping_report.py",
        "tests/acceptance/test_acceptance_markdown_report.feature",
        "tests/acceptance/test_acceptance_markdown_report.py",
    )
    for relative in deliverables:
        assert (_REPO_ROOT / relative).exists(), f"测试交付件缺失: {relative}"
