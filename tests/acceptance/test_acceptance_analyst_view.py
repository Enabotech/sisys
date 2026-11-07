"""Acceptance tests for Story 6-9 - 分析师视图（三段聚合查询——专业工具箱/BLM 六阶段进度/溯源摘要 + CLI analyst-view）.

真实服务验收（零 mock——工具箱静态真源（TOOLS.md 打包内存读）+ Redis latest 快照直写 +
PG 归档行/documents 行直写 + Qdrant 点直写四通道装配；验收装配面零 LLM 零 Embedding——
纯读侧聚合，与 6-6/6-7/6-8 查询面先例同族；段级容错归单测——验收面无故障注入通道）。

场景三属性分档表（12 场景全绑定——S 编号为本 Story 自有 docstring 编号，不入 Gherkin）：
    | 场景 | AC | 调用面 | 红阶段形态 |
    |------|----|--------|-----------|
    | S1 三段全落位 | AC-1 | 编程面（服务直调） | 运行期 ImportError（analyst_view 模块缺失） |
    | S2 三 plan 六阶段派生 | AC-3 | 编程面 | 同上 |
    | S3 工具箱清单+配比 | AC-2 | 编程面 | 同上 |
    | S4 溯源统计+跳转混合 | AC-4 | 编程面 | 同上 |
    | S5 空 plan 幂等读 | AC-5 | 编程面 | 同上 |
    | S6 投影白名单 | AC-1 | 编程面 | 同上 |
    | S7 畸形 plan_id 242 | AC-5 | 编程面（用例守卫） | 同上 |
    | S8 CLI 全数据输出 | AC-6 | CLI in-process 直调 | argparse invalid choice exit 2 → 断言步红 |
    | S9 CLI 空态+242 stderr | AC-6 | CLI in-process 直调 | 同上 |
    | S10 性能采样 | AC-7 | 编程面（C 面通道） | 运行期 ImportError |
    | S11 并发 20 路 | AC-7 | 编程面（C 面通道） | 同上 |
    | S12 完成清单存在性 | 收尾 | 文件系统断言 | Then 文件不存在 AssertionError |

性能三段口径差声明（OD-7——验收 docstring 落档）：
    ① 视图加载 P95<800ms = build_analyst_view 服务面窗口（三读串行：list_active_skills
       内存遍历微秒级 + snapshot load Redis 单键点查 + build_trace_tree 全树[query_archive
       PG 归档查 + get_point/find Qdrant 点查——三读最重]）；trace_tree 全树成本随归档量
       增长——万行级归档时该段成为热点，分组统计端口立项锚 Epic 7/21；
    ② 并发 20 = 单一数据源 plan_id×20 路并发读（asyncio.gather+服务无状态+两两相等；
       对照排除集单键 {generated_at}——toolbox 静态真源恒稳/progress 单键快照读恒稳/
       traceability 段不透传树 generated_at[OD-6 联动设计收益]，排除集最小化；
       「批量操作」epics L2446 本义是工作台证据勾选 Web 交互归 Epic 22.1——本 Story
       以并发批量读作读面等价锚）；
    ③ 「快捷键响应<100ms」为前端指标后端不定义（epics L2457 原文——键盘事件响应归
       Epic 21 Story 21.9 届时验收）；「溯源跳转<300ms」已由 6-7 跳转载荷组装承载——
       本 Story 溯源段是统计摘要面非跳转执行面，跳转执行归 trace-tree 既有命令。

PG 面三分面通道（R2-F3——预置纪律钦定，6-8 直系）：
    - A 编程面（S1~S7）：归档行写入经 set_session 注入 fixture session → flush 不
      commit → 服务读同 session 同事务可见 → teardown rollback 整体回收（归档行零
      DELETE 通道）；documents 行原生 SQL INSERT + Qdrant 点为 commit 式 → 定向
      DELETE/collection 整删（两通道不经 session_context——A 面仅覆盖归档行）；
    - B CLI 面（S8/S9）：clear_session() 清 ContextVar → 归档行经 fallback 独立会话
      commit 式 → teardown 定向 DELETE + 行数断言防静默 0 行假绿；
    - C 并发/性能面（S10/S11）：场景内禁 set_session → 每路各自走 fallback 独立会话
      （天然 per-task 隔离）→ 预置 commit 式 + teardown 定向 DELETE 行数断言。

快照 timeline 预置纪律（R1-F4）：本 Story 是首个 timeline step 值消费者——预置值按
写侧实值三形态构造（"performance_gap"/六子裸值 trend 等/"market_insight_synthesis"），
禁复刻 6-8 _STEP_SEQUENCE 的 market_insight_trend 前缀形态（计数面专用非 canonical）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_analyst_view.py -v
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import math
import time
import uuid as uuid_module
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenario, then, when

pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.database,
    pytest.mark.redis,
    pytest.mark.qdrant,  # 装配链依赖（bootstrap/组合根 resolve 链含 Qdrant 适配器——6-7/6-8 同款注记）
    pytest.mark.xdist_group("blm-planning-perf"),
]

# ===================================================================
# Paths & Constants（模块级期望常量独立构造——性能采样纪律）
# ===================================================================

ROOT = Path(__file__).resolve().parents[2]

_P95_LIMIT_MS: float = 800.0
_P95_PERCENTILE: float = 0.95
_SAMPLE_ROUNDS: int = 20
_WARMUP_ROUNDS: int = 2
_CONCURRENCY: int = 20

# 并发对照排除集单键（OD-7 ②口径/OD-6 联动——段不透传树 generated_at 故排除集最小化：
# toolbox 静态真源恒稳/progress 单键快照读恒稳/traceability 五计数+哨兵恒稳）
_EXCLUDED_TOP_KEYS: tuple[str, ...] = ("generated_at",)

# 8 步全序列（写侧实值三形态——R1-F4：performance_gap 前缀形态 + 六子裸值 + synthesis；
# 与 BLM_TOTAL_STEPS=8 单源对齐——预置工厂与断言共用）
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

# 五战略分类期望配比（Story 4.1 AC-2 钦定——slug 清单稳定序去重序）
_EXPECTED_CATEGORY_COUNTS: dict[str, int] = {
    "environment_analysis": 3,
    "competitive_analysis": 3,
    "strategic_selection": 6,
    "business_model": 3,
    "execution_management": 8,
}

# 独立测试 collection（TestTenant/uuid 前缀——预置与读回同 collection 单源；
# CLI 面 monkeypatch BLM_SEARCH_COLLECTION 桥接同值——6-7 同款）
_COLLECTION: str = f"analyst-view-acceptance-{uuid_module.uuid4().hex[:8]}"

_VECTOR_DIM: int = 1024  # 与生产 embedding 及适配器维度校验对齐（6-5b/6-7 同款字面量向量）

# 完成清单（S12 断言对象 = File List 的 src/测试项存在性；
# 两 md 台账（deferred-work/sprint-status）与故事文件不入断言面——修改性断言物理不可写，6-8 S12 同款）
_COMPLETION_SRC_FILES: dict[str, str] = {
    "端口契约（七 VO + PhaseStatus + BLM_SIX_PHASES + AnalystViewPort）": "src/application/ports/analyst_view.py",
    "视图服务（三段编排+derive_stage_status）": "src/application/services/analyst_view_service.py",
    "查询用例（UUID 守卫+透传）": "src/application/use_cases/get_analyst_view.py",
    "CLI analyst-view 子命令": "src/entrypoints/agent_cli.py",
    "组合根双注册块": "src/composition_root.py",
}
_COMPLETION_TEST_FILES: dict[str, str] = {
    "VO 单测": "tests/unit/application/test_analyst_view_vos.py",
    "服务单测（派生矩阵+容错矩阵）": "tests/unit/application/test_analyst_view_service.py",
    "用例单测": "tests/unit/application/use_cases/test_analyst_view_use_case.py",
    "CLI 单测扩展": "tests/unit/interfaces/cli/test_agent_cli.py",
    "架构四验证器": "tests/unit/architecture/test_analyst_view.py",
    "集成四场景": "tests/integration/test_integration_analyst_view.py",
    "端口契约测试（五断言族）": "tests/contracts/test_port_contract_analyst_view.py",
    "验收 feature": "tests/acceptance/test_acceptance_analyst_view.feature",
    "验收 BDD 步骤实现": "tests/acceptance/test_acceptance_analyst_view.py",
}

# ===================================================================
# 三件套（event_loop fixture + _run_async + context dict——6-x 样板）
# ===================================================================


@pytest.fixture
def event_loop() -> Any:
    """模块级事件循环（BDD 步骤禁 @pytest.mark.asyncio——context 数据丢失防线）。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _run_async(coro: Any, loop: Any) -> Any:
    """在模块级 event_loop 上运行协程（三件套之一）。"""
    return loop.run_until_complete(coro)


def _clear_resolver_caches() -> None:
    """驱逐 resolver SINGLETON/SCOPED 缓存（CLI 直调双清钦定——6-6 R3-1 证伪单清形态防线）。"""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()


def _clear_session_ctx() -> None:
    """清 ContextVar 会话（无参防御复位 API——B/C 面预置与 CLI 直调前钦定）。"""
    from src.infrastructure.storage.postgresql.session_context import clear_session

    clear_session()


@pytest.fixture
def context(event_loop: Any, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> Any:
    """场景级 context dict（数据面预置登记 + CLI 直调产物位 + teardown 清单）。"""
    ctx: dict[str, Any] = {
        "_loop": event_loop,
        "_capsys_ref": capsys,
        "_monkeypatch_ref": monkeypatch,
        "_collection": _COLLECTION,
        "_a_mode": False,
        "_session_token": None,
        "_active_plan": "",
        "_empty_plan": "",
        "_snapshot_keys": [],
        "_plan_ids": [],
        "_chunk_specs": [],
        "_document_ids": [],
        "view": None,
        "views": {},
        "malformed_error": None,
        "durations": [],
        "concurrent_views": [],
        "cli_exit_code": None,
        "cli_stdout": "",
        "cli_stderr": "",
    }
    yield ctx
    _run_async(_teardown_assets(ctx), event_loop)
    if ctx["_session_token"] is not None:
        from src.infrastructure.storage.postgresql.session_context import reset_session

        reset_session(ctx.pop("_session_token"))
    _clear_resolver_caches()


@pytest.fixture
def pg_session(event_loop: Any) -> Any:
    """A 面真实 PG 会话（事务回滚式——R6 outbox_repo 原型形态：begin→yield→rollback）。"""
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
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
    yield session

    async def _finalize() -> None:
        await session.rollback()
        await session.close()
        await manager.get_async_engine().dispose()

    event_loop.run_until_complete(_finalize())


def _a_mode_enter(ctx: dict[str, Any], pg_session: Any) -> None:
    """A 面进入（set_session 注入 fixture session——6-8 R2-F5 直系）.

    幂等：同场景多步骤重复进入只 set 一次（token 记入 context 供 teardown reset）。
    """
    from src.infrastructure.storage.postgresql.session_context import set_session

    if ctx["_session_token"] is None:
        ctx["_session_token"] = set_session(pg_session)
    ctx["_a_mode"] = True


# ===================================================================
# 预检跳过（pytest.skip 动态跳过——禁 @pytest.mark.skip 写死）
# ===================================================================


def _probe_pg_available() -> None:
    """PostgreSQL 可达性探测（strategic_archives/documents 表预检——失败 skip）。"""
    import asyncpg

    from tests.environments import get_test_env

    env = get_test_env()
    probe_loop = asyncio.new_event_loop()
    try:

        async def _check() -> bool:
            try:
                conn = await asyncpg.connect(
                    host=env.postgres.host,
                    port=env.postgres.port,
                    user=env.postgres.username,
                    password=env.postgres.password,
                    database=env.postgres.database,
                )
                try:
                    await conn.execute("SELECT 1 FROM strategic_archives LIMIT 1")
                    await conn.execute("SELECT 1 FROM documents LIMIT 1")
                finally:
                    await conn.close()
                return True
            except Exception:
                return False

        if not probe_loop.run_until_complete(_check()):
            pytest.skip(f"PostgreSQL not available at {env.postgres.host}:{env.postgres.port}")
    finally:
        probe_loop.close()


def _probe_redis_available() -> None:
    """Redis 可达性探测（ping——失败 skip）。"""
    import redis.asyncio as aioredis

    from tests.environments import get_test_env

    env = get_test_env()
    probe_loop = asyncio.new_event_loop()
    try:

        async def _check() -> bool:
            client = aioredis.Redis(
                host=env.redis.host,
                port=env.redis.port,
                password=env.redis.password or None,
                decode_responses=True,
            )
            try:
                return bool(await client.ping())
            except Exception:
                return False
            finally:
                await client.close()  # close 形态对齐仓内验收先例（traceability_tree :207 等——类型存根无 aclose）

        if not probe_loop.run_until_complete(_check()):
            pytest.skip(f"Redis not available at {env.redis.host}:{env.redis.port}")
    finally:
        probe_loop.close()


def _probe_qdrant_available() -> None:
    """Qdrant 可达性探测（get_collections——失败 skip）。"""
    from qdrant_client import AsyncQdrantClient

    from tests.environments import get_test_env

    env = get_test_env()
    probe_loop = asyncio.new_event_loop()
    try:

        async def _check() -> bool:
            try:
                client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=5)
                try:
                    await client.get_collections()
                finally:
                    await client.close()
                return True
            except Exception:
                return False

        if not probe_loop.run_until_complete(_check()):
            pytest.skip(f"Qdrant not available at {env.qdrant.host}:{env.qdrant.port}")
    finally:
        probe_loop.close()


async def _ensure_collection(collection: str | None = None) -> None:
    """幂等建独立测试 collection（1024 维 COSINE——6-7 形态直系；可注入集成 collection）。"""
    from qdrant_client import AsyncQdrantClient

    from tests.environments import get_test_env

    target = collection if collection is not None else _COLLECTION
    env = get_test_env()
    client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
    try:
        existing = {item.name for item in (await client.get_collections()).collections}
        if target not in existing:
            from qdrant_client.models import Distance, VectorParams

            await client.create_collection(
                collection_name=target,
                vectors_config=VectorParams(size=_VECTOR_DIM, distance=Distance.COSINE),
            )
    finally:
        await client.close()


# ===================================================================
# 归档族预置 helper（6-7 test_acceptance_traceability_tree.py 直系复刻）
# ===================================================================

_GAP_STAGE = "performance_gap"
_TREND_STAGE = "market_insight_trend"
_SYNTHESIS_STAGE = "market_insight_synthesis"


def _make_chain_payload(stage: str, *, index: int = 0, plan_tag: str = "s") -> dict[str, Any]:
    """按 stage 三型分派构造 chain.final_answer payload（gap 五键/synthesis 结论/子步双键）。"""
    if stage == _SYNTHESIS_STAGE:
        return {"conclusions": [f"综合结论一（{plan_tag}）", f"综合结论二（{plan_tag}）"], "degraded_inputs": []}
    if stage == _GAP_STAGE:
        return {
            "financial_gap": "财务差距样本",
            "operational_gap": "运营差距样本",
            "root_causes": ["根因一", "根因二"],
            "portfolio_health": "组合健康度样本",
            "degraded": False,
            "degrade_reason": "",
        }
    return {"summary": f"步骤摘要（{stage}#{index}）", "findings": ["发现一", "发现二"]}


def _make_tree_archive_service() -> Any:
    """归档服务构造（全 None 依赖纯 L2 预置——6-7 DR1-7 形态直系）."""
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.domain.ports.resolver import resolve

    return StrategicArchiveService(
        archive_repo=resolve("archive_repository"),
        embedding_service=None,
        vector_storage=None,
        object_storage=None,
        graph_storage=None,
        event_publisher=None,
        staleness_service=None,
    )


async def _archive_row(
    ctx: dict[str, Any],
    plan_id: str,
    *,
    stage: str,
    evidence_refs: tuple[str, ...],
    index: int = 0,
) -> None:
    """归档行直写（无 LLM——assumptions/decision_basis 按 6-4 写入侧形态构造）."""
    from src.application.ports.chain_of_thought_archive import CHAIN_ARCHIVE_KIND
    from src.domain.entities.strategic_archive import ArchiveType

    payload = _make_chain_payload(stage, index=index, plan_tag=plan_id[:8])
    chain_dict: dict[str, Any] = {
        "input_summary": f"输入摘要（{stage}#{index}）",
        "reflection": f"反思内容（{stage}#{index}）——论据链完整性与一致性复核通过，含改进建议若干",
        "tools_used": [f"tool-{stage}-{index}"],
        "constraints_check": {},
        "final_answer": json.dumps(payload, ensure_ascii=False),
    }
    assumptions: dict[str, Any] = {
        "tools_used": list(chain_dict["tools_used"]),
        "evidence_refs": list(evidence_refs),
    }
    decision_basis: dict[str, Any] = {
        "kind": CHAIN_ARCHIVE_KIND,
        "stage": stage,
        "chain": chain_dict,
        "degraded": False,
    }
    if not ctx["_a_mode"]:
        _clear_session_ctx()
    service = _make_tree_archive_service()
    await service.archive_plan(
        plan_id=uuid_module.UUID(plan_id),
        plan_type="SP",
        archive_type=ArchiveType.EVIDENCE_PACKAGE,
        assumptions=assumptions,
        decision_basis=decision_basis,
        execution_deviation={},
        evidence_blob=None,
    )
    ctx["_plan_ids"].append(plan_id)


def _spec_chunk(
    chunk_id: str,
    *,
    document_id: str,
    page_start: int,
    page_end: int,
    upsert_qdrant: bool = True,
    insert_pg: bool = True,
    pg_chunks_include: bool = True,
) -> dict[str, Any]:
    """chunk 预置规格（Qdrant 点 / PG 行 / metadata.chunks 收录三开关——降级形态构造）。"""
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "page_start": page_start,
        "page_end": page_end,
        "upsert_qdrant": upsert_qdrant,
        "insert_pg": insert_pg,
        "pg_chunks_include": pg_chunks_include,
    }


async def _preset_qdrant_points_and_pg_rows(ctx: dict[str, Any], collection: str | None = None) -> None:
    """按 chunk 规格预置 Qdrant 点（8 业务键）与 PG documents 行（原生 SQL）.

    Qdrant 点经 L3VectorPort.upsert_points 生产通道（MD5 归一读写对称闭环——禁裸
    client 直写）；PG 行原生 SQL INSERT（metadata 含 chunks+storage_object_key 两键
    ——jump_ready 依赖后者）。collection 可注入（集成测试复用本 helper 传独立
    collection——默认本验收模块 _COLLECTION）。
    """
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.application.services.agent_workflow_context import MVP_TENANT_ID
    from src.domain.ports.resolver import resolve
    from tests.environments import get_test_env

    env = get_test_env()
    points = [
        {
            "id": spec["chunk_id"],
            "vector": [0.1] * _VECTOR_DIM,
            "payload": {
                "chunk_id": spec["chunk_id"],
                "document_id": spec["document_id"],
                "parent_chunk_id": None,
                "index_level": "child",
                "content": f"切片内容（{spec['chunk_id']}）——用于分析师视图预置的语义切片文本",
                "chunk_header": f"标题（{spec['chunk_id']}）",
                "page_start": spec["page_start"],
                "page_end": spec["page_end"],
            },
        }
        for spec in ctx["_chunk_specs"]
        if spec["upsert_qdrant"]
    ]
    if points:
        l3 = resolve("l3_vector")
        await l3.upsert_points(collection if collection is not None else _COLLECTION, points)

    documents: dict[str, list[dict[str, Any]]] = {}
    for spec in ctx["_chunk_specs"]:
        if not spec["insert_pg"]:
            continue
        documents.setdefault(spec["document_id"], []).append(
            {
                "chunk_id": spec["chunk_id"],
                "page_start": spec["page_start"],
                "page_end": spec["page_end"],
                "chunk_header": f"标题（{spec['chunk_id']}）",
            }
            if spec["pg_chunks_include"]
            else {"chunk_id": f"other-{spec['chunk_id']}", "page_start": 1, "page_end": 1}
        )
    if documents:
        engine = create_async_engine(
            f"postgresql+asyncpg://{env.postgres.username}:{env.postgres.password}"
            f"@{env.postgres.host}:{env.postgres.port}/{env.postgres.database}"
        )
        try:
            async with engine.begin() as conn:
                for document_id, chunks_meta in documents.items():
                    ctx["_document_ids"].append(document_id)
                    await conn.execute(
                        sa.text(
                            "INSERT INTO documents (id, tenant_id, filename, mime_type, file_size_bytes, "
                            "document_type, parse_status, uploaded_by, version, metadata, created_at, updated_at) "
                            "VALUES (CAST(:id AS uuid), :tenant, :filename, 'application/pdf', 1024, "
                            "'other', 'completed', 'acceptance', 1, CAST(:meta AS jsonb), now(), now())"
                        ),
                        {
                            "id": document_id,
                            "tenant": str(MVP_TENANT_ID),
                            "filename": f"分析师视图预置文档-{document_id[:8]}.pdf",
                            "meta": json.dumps(
                                {
                                    "chunks": chunks_meta,
                                    "storage_object_key": f"raw-documents/acceptance/{document_id}.pdf",
                                },
                                ensure_ascii=False,
                            ),
                        },
                    )
        finally:
            await engine.dispose()


async def _teardown_assets(ctx: dict[str, Any]) -> None:
    """teardown 四步链（Redis 快照 DEL / 归档行定向 DELETE[A 面跳过] / documents 定向 DELETE / Qdrant 整删）.

    各步独立 try/except——单步失败不阻断后续清理；A 面归档行经 pg_session fixture
    rollback 整体回收（跳过 DELETE——零 DELETE 通道）；B/C 面 commit 式预置须定向
    DELETE；documents/Qdrant 全通道 commit 式恒清理（不经 session_context）。
    """
    try:
        from src.domain.ports.resolver import resolve

        repo = resolve("snapshot_repository")
        for session_id in ctx["_snapshot_keys"]:
            try:
                await repo.delete(session_id)
            except Exception as error:  # teardown 容错（单键失败不阻断后续清理）
                print(f"[teardown:redis] 删除异常（容错）: {session_id}: {error}")
    except Exception as error:  # teardown 容错
        print(f"[teardown:redis] 仓储不可达（容错）: {error}")
    if not ctx["_a_mode"] and ctx["_plan_ids"]:
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
                    result = await conn.execute(
                        sa.text("DELETE FROM strategic_archives WHERE plan_id = ANY(:ids)"),
                        {"ids": list(ctx["_plan_ids"])},
                    )
                    assert result.rowcount > 0 or not ctx["_plan_ids"], (
                        f"strategic_archives 定向 DELETE 行数 {result.rowcount}（静默 0 行假绿防线——R2-F3）"
                    )
            finally:
                await engine.dispose()
        except AssertionError:
            raise
        except Exception as error:  # teardown 容错
            print(f"[teardown:archives] 清理异常（容错）: {error}")
    if ctx["_document_ids"]:
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
                    await conn.execute(
                        sa.text("DELETE FROM documents WHERE id = ANY(:ids)"),
                        {"ids": list(ctx["_document_ids"])},
                    )
            finally:
                await engine.dispose()
        except Exception as error:  # teardown 容错
            print(f"[teardown:documents] 清理异常（容错）: {error}")
    try:
        from qdrant_client import AsyncQdrantClient

        from tests.environments import get_test_env

        env = get_test_env()
        client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
        try:
            await client.delete_collection(collection_name=_COLLECTION)
        finally:
            await client.close()
    except Exception as error:  # teardown 容错
        print(f"[teardown:qdrant] 清理异常（容错）: {error}")


# ===================================================================
# 快照预置 helper（latest 快照直写——progress 段数据源）
# ===================================================================


def _make_latest_state(
    plan_id: str,
    *,
    completed: int,
    degraded_steps: list[str],
    timeline_steps: tuple[str, ...],
) -> dict[str, Any]:
    """latest 快照 state_data 七键（timeline 按 timeline_steps 构造——R1-F4 写侧实值三形态）."""
    base = datetime.now(UTC)
    timeline = [
        {
            "step": step,
            "started_at": (base - timedelta(seconds=len(_STEP_SEQUENCE) - i)).isoformat(),
            "completed_at": (base - timedelta(seconds=len(_STEP_SEQUENCE) - i - 1)).isoformat(),
            "status": "completed",
            "summary_excerpt": f"步骤摘要（{step}）",
            "degraded": step in degraded_steps,
        }
        for i, step in enumerate(timeline_steps)
    ]
    return {
        "plan_id": plan_id,
        "phase": "market_insight",
        "current_step": timeline_steps[-1] if timeline_steps else None,
        "completed_steps": completed,
        "total_steps": len(_STEP_SEQUENCE),
        "degraded_steps": list(degraded_steps),
        "timeline": timeline,
    }


async def _save_snapshot(ctx: dict[str, Any], snapshot: Any) -> None:
    """Redis 快照直写（snapshot_repository.save 真实通道+键登记）."""
    from src.domain.ports.resolver import resolve

    await resolve("snapshot_repository").save(snapshot)
    ctx["_snapshot_keys"].append(snapshot.session_id)


# ===================================================================
# 服务构建 + CLI 直调 helper
# ===================================================================


def _build_view_service(context: dict[str, Any]) -> Any:
    """构建分析师视图服务（三依赖 resolve 既有注册名——OD-11；collection 桥接 setenv）.

    红锚：analyst_view_service 模块缺失 → 运行期 ImportError（Task 0 红阶段形态）。
    """
    from src.application.services.analyst_view_service import AnalystViewService
    from src.domain.ports.resolver import resolve

    context["_monkeypatch_ref"].setenv("BLM_SEARCH_COLLECTION", _COLLECTION)
    _clear_resolver_caches()  # SINGLETON 重建使 collection 环境变量生效——6-7 桥接直系
    return AnalystViewService(
        skill_selector=resolve("skill_selector"),
        snapshot_repository=resolve("snapshot_repository"),
        traceability_tree_service=resolve("traceability_tree_service"),
    )


def _run_cli_analyst_view(context: dict[str, Any], *, plan_id: str | None = None) -> None:
    """CLI in-process 直调（双清钦定 + clear_session 清 ContextVar）.

    clear_session 是 CLI 面硬前置：asyncio.run 新循环继承当前上下文的 fixture session 会
    触发「Future attached to a different loop」——必清使服务各仓储走 fallback 独立会话。
    """
    from src.entrypoints import agent_cli

    _clear_session_ctx()
    _clear_resolver_caches()
    context["_monkeypatch_ref"].setenv("BLM_SEARCH_COLLECTION", _COLLECTION)
    argv = ["analyst-view", "--plan-id", plan_id or context["_active_plan"]]
    exit_code = 0
    try:
        exit_code = agent_cli.main(argv)
    except SystemExit as error:  # 红阶段命令未注册 → argparse invalid choice exit 2
        exit_code = int(error.code or 0)
    captured = context["_capsys_ref"].readouterr()
    _clear_resolver_caches()
    context["cli_exit_code"] = exit_code
    context["cli_stdout"] = captured.out
    context["cli_stderr"] = captured.err


def _field_names(obj: Any) -> set[str]:
    """dataclass 字段名集合（键集 exact set 断言——6-8 R1-F10 激活先例形态）."""
    from dataclasses import fields

    return {f.name for f in fields(obj)}


# ===================================================================
# 全数据归档族预置（S1/S4/S8/S10/S11 共用——钦定 2 stage×3 chunk 判别计数面错接 R3-F4）
# ===================================================================


def _preset_full_archive_family(ctx: dict[str, Any], plan_id: str) -> None:
    """预置全数据归档族：2 分析 stage×3 chunk 实例+jump_ready 真假混合+1 synthesis 行.

    期望统计（段断言单源锚）：stage_count=2 / chunk_count=3（≠stage_count 判别计数面
    错接——R3-F4 钦定形态）/ document_count=3 / jump_ready_count=2（True 2+False 1
    混合判别——计数既非全 0 亦非全量）/ degraded_stage_count=0。
    """
    document_ids = {
        "chunk-av-a": str(uuid_module.uuid4()),
        "chunk-av-b": str(uuid_module.uuid4()),
        "chunk-av-c": str(uuid_module.uuid4()),
    }

    def _preset() -> None:
        _run_async(
            _archive_row(ctx, plan_id, stage=_GAP_STAGE, evidence_refs=("chunk-av-a",)),
            ctx["_loop"],
        )
        _run_async(
            _archive_row(ctx, plan_id, stage=_TREND_STAGE, evidence_refs=("chunk-av-b", "chunk-av-c")),
            ctx["_loop"],
        )
        _run_async(
            _archive_row(ctx, plan_id, stage=_SYNTHESIS_STAGE, evidence_refs=()),
            ctx["_loop"],
        )

    _preset()
    ctx["_chunk_specs"].append(_spec_chunk("chunk-av-a", document_id=document_ids["chunk-av-a"], page_start=3, page_end=4))
    ctx["_chunk_specs"].append(_spec_chunk("chunk-av-b", document_id=document_ids["chunk-av-b"], page_start=5, page_end=6))
    # jump_ready False 腿：pg_chunks_include=False → metadata.chunks 匹配不上 → page=None
    ctx["_chunk_specs"].append(
        _spec_chunk("chunk-av-c", document_id=document_ids["chunk-av-c"], page_start=7, page_end=8, pg_chunks_include=False)
    )
    _run_async(_preset_qdrant_points_and_pg_rows(ctx), ctx["_loop"])


def _preset_full_plan_snapshot(ctx: dict[str, Any], plan_id: str) -> None:
    """预置全数据 latest 快照（3/8 完成+1 降级——progress_percent=int(3/8*100)=37 整数口径锚）."""

    async def _preset() -> None:
        from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        await _save_snapshot(
            ctx,
            CheckpointSnapshot(
                session_id=f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}",
                state_data=_make_latest_state(
                    plan_id,
                    completed=3,
                    degraded_steps=[_STEP_SEQUENCE[0]],
                    timeline_steps=(_STEP_SEQUENCE[0], _STEP_SEQUENCE[1], _STEP_SEQUENCE[2]),
                ),
            ),
        )

    _run_async(_preset(), ctx["_loop"])


# ===================================================================
# Background
# ===================================================================


@given("分析师视图依赖服务可用")
def analyst_view_services_available(context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """Background：PG/Redis/Qdrant 三服务探测（不可达 pytest.skip 动态跳过）+ collection 准备."""
    context["_capsys_ref"] = capsys
    _probe_pg_available()
    _probe_redis_available()
    _probe_qdrant_available()
    _run_async(_ensure_collection(), context["_loop"])


# ===================================================================
# AC-1 三段全落位与键集值级断言
# ===================================================================


@scenario(
    "test_acceptance_analyst_view.feature",
    "三段全落位与键集值级断言",
)
def test_full_view_three_sections() -> None:
    """S1/AC-1 三段全落位（全数据形态三段聚合——6 键+嵌套键集+值级）."""
    pass


@given("预置全数据形态的 plan（快照 3/8 与溯源归档族含跳转混合）")
def preset_full_data_plan(context: dict[str, Any], pg_session: Any) -> None:
    """S1 预置（A 面回滚式通道）：latest 快照 3/8（1 降级）+ 归档族 2 stage×3 chunk 混合跳转."""
    _a_mode_enter(context, pg_session)
    plan_id = str(uuid_module.uuid4())
    _preset_full_archive_family(context, plan_id)
    _preset_full_plan_snapshot(context, plan_id)
    context["_active_plan"] = plan_id


@when("构建分析师视图")
def build_analyst_view_step(context: dict[str, Any]) -> None:
    """S1/S3/S4/S6：服务直调构建视图（红锚=analyst_view_service ImportError；未预设
    _active_plan 时现场生成空 plan——S3/S6 工具箱面自足腿，静态真源与 plan 正交）."""
    if not context["_active_plan"]:
        context["_active_plan"] = str(uuid_module.uuid4())
    service = _build_view_service(context)
    context["view"] = _run_async(service.build_analyst_view(plan_id=context["_active_plan"]), context["_loop"])


@then("视图 6 键与三段嵌套键集完整")
def verify_view_and_section_keys(context: dict[str, Any]) -> None:
    """S1：AnalystView 6 键 + 三段嵌套键集 exact set（Task 0.1 冻结表逐键对齐）."""
    view = context["view"]
    assert view is not None, "视图构建失败（context 缺 view）"
    assert _field_names(view) == {
        "plan_id",
        "generated_at",
        "build_degraded",
        "toolbox",
        "progress",
        "traceability",
    }
    assert _field_names(view.toolbox) == {"degraded", "total_tools", "tools", "categories"}
    assert _field_names(view.progress) == {
        "available",
        "degraded",
        "phase",
        "current_step",
        "completed_steps",
        "total_steps",
        "progress_percent",
        "degraded_step_count",
        "stages",
    }
    assert _field_names(view.traceability) == {
        "available",
        "degraded",
        "stage_count",
        "chunk_count",
        "document_count",
        "jump_ready_count",
        "degraded_stage_count",
        "tree_build_degraded",
    }
    for tool in view.toolbox.tools:
        assert _field_names(tool) == {"slug", "tool_name", "category", "description", "status"}
    for category in view.toolbox.categories:
        assert _field_names(category) == {"category", "tool_count"}
    for stage in view.progress.stages:
        assert _field_names(stage) == {"phase_key", "phase_name", "status", "step_completed", "step_total"}
    assert view.build_degraded is False, "全数据在位视图不应段降级"
    assert view.plan_id == context["_active_plan"]
    assert view.generated_at, "顶层 generated_at 应为非空 ISO 字符串（单时间锚）"


@then("三段计数与预置一致")
def verify_section_counts(context: dict[str, Any]) -> None:
    """S1：三段计数值级（工具 23/进度 3/8 直读/溯源五计数——五计数值级归本步与 S4 双承载）."""
    view = context["view"]
    assert view.toolbox.total_tools == 23
    assert view.progress.available is True
    assert view.progress.completed_steps == 3
    assert view.progress.total_steps == 8
    assert view.progress.degraded_step_count == 1
    assert view.progress.phase == "market_insight"
    assert view.progress.current_step == _STEP_SEQUENCE[2]
    assert view.traceability.available is True
    assert view.traceability.stage_count == 2
    assert view.traceability.chunk_count == 3
    assert view.traceability.document_count == 3
    assert view.traceability.jump_ready_count == 2
    assert view.traceability.degraded_stage_count == 0
    assert view.traceability.tree_build_degraded is False


@then("progress_percent 为整数口径 37")
def verify_progress_percent_integer(context: dict[str, Any]) -> None:
    """S1：progress_percent 整数口径（int(3/8*100) 向下取整=37——非 37.5）."""
    view = context["view"]
    assert isinstance(view.progress.progress_percent, int)
    assert view.progress.progress_percent == 37


# ===================================================================
# AC-1 工具摘要投影白名单五键
# ===================================================================


@scenario(
    "test_acceptance_analyst_view.feature",
    "工具摘要投影白名单五键",
)
def test_tool_summary_projection_whitelist() -> None:
    """S6/AC-1 ToolSummary 投影白名单（5 键 exact set+值非空+status active+抽样值级锚）."""
    pass


@given("工具箱静态真源在位")
def toolbox_static_source_ready(context: dict[str, Any]) -> None:
    """S3/S6 Given：静态真源零预置（TOOLS.md 打包文件只读——无资源生命周期，隔离表钦定）."""
    context["_toolbox_ready"] = True


@then("每条工具摘要恰 5 键且值非空且状态为 active")
def verify_tool_summary_values(context: dict[str, Any]) -> None:
    """S6：每条 ToolSummary 五键值级（slug/tool_name/category/description 非空+status=="active"）."""
    view = context["view"]
    for tool in view.toolbox.tools:
        assert tool.slug, "slug 应非空"
        assert tool.tool_name, "tool_name 应非空"
        assert tool.category, "category 应非空"
        assert tool.description, "description 应非空"
        assert tool.status == "active", f"status 应为 active（实测 {tool.status}）"


@then("抽样工具名称与描述与清单原文一致")
def verify_tool_summary_sampling(context: dict[str, Any]) -> None:
    """S6：抽样 ≥3 工具与 L1 元数据单源直比（投影源字段直传零变形——首/中/末三锚）."""
    from src.domain.ports.resolver import resolve

    view = context["view"]
    sample_indexes = (0, 11, 22)  # 首锚 pestel-analysis/中锚/末锚 change-management
    loader = resolve("skill_loader")
    for index in sample_indexes:
        tool = view.toolbox.tools[index]
        metadata = _run_async(loader.load_metadata(tool.slug), context["_loop"])
        assert tool.tool_name == metadata.tool_name
        assert tool.category == metadata.category
        assert tool.description == metadata.description
        assert tool.status == metadata.status


# ===================================================================
# AC-2 工具箱真实清单与分类配比
# ===================================================================


@scenario(
    "test_acceptance_analyst_view.feature",
    "工具箱真实清单与分类配比",
)
def test_toolbox_real_inventory() -> None:
    """S3/AC-2 工具箱真实清单（23 事实断言+全 slug 序直比+五分类配比+和恒等式）."""
    pass


@then("total_tools 等于 23 且全 slug 序与清单一致")
def verify_toolbox_total_and_order(context: dict[str, Any]) -> None:
    """S3：total_tools==23（MVP 交付时点全 ACTIVE 事实断言——预期退化信号非 flake）+
    全序列 slug 直比静态真源（get_all_slugs——R1-F11 主锚，中段乱序判别）+首末锚."""
    from src.application.skills.skill_manifest import get_all_slugs

    view = context["view"]
    assert view.toolbox.total_tools == 23, "total_tools 应为 23（MVP 交付时点全 ACTIVE 事实）"
    assert tuple(tool.slug for tool in view.toolbox.tools) == tuple(get_all_slugs()), (
        "全序列 slug 应与静态真源一致（selector 返回序契约——禁排序重排）"
    )
    assert view.toolbox.tools[0].slug == "pestel-analysis"  # 首锚（快速失败）
    assert view.toolbox.tools[-1].slug == "change-management"  # 末锚（快速失败）


@then("五分类配比为 3/3/6/3/8 且分组和恒等式成立")
def verify_category_counts(context: dict[str, Any]) -> None:
    """S3：五分类各 tool_count 值级（Story 4.1 AC-2 钦定配比）+和恒等式+len==5 防第六类静默出现."""
    view = context["view"]
    assert len(view.toolbox.categories) == 5, f"分类数应为 5（实测 {len(view.toolbox.categories)}）"
    actual_counts = {category.category: category.tool_count for category in view.toolbox.categories}
    assert actual_counts == _EXPECTED_CATEGORY_COUNTS, f"五分类配比不符（实测 {actual_counts}）"
    assert sum(category.tool_count for category in view.toolbox.categories) == view.toolbox.total_tools, (
        "分组和恒等式 sum(tool_count) == total_tools 应成立（分组计数完备性）"
    )


# ===================================================================
# AC-3 三 plan 形态六阶段派生
# ===================================================================


@scenario(
    "test_acceptance_analyst_view.feature",
    "三 plan 形态六阶段派生",
)
def test_three_plan_stage_derivation() -> None:
    """S2/AC-3 三 plan 形态（P-mid 进行中/P-full 全完成/P-empty 框架恒在）."""
    pass


@given("预置 P-mid 进行中与 P-full 全完成与 P-empty 空 plan 三形态")
def preset_three_plan_forms(context: dict[str, Any], pg_session: Any) -> None:
    """S2 预置（A 面通道）：P-mid（performance_gap+trend 2 步）+P-full（8 步全序列）+P-empty（零快照）."""
    _a_mode_enter(context, pg_session)
    context["p_mid_plan"] = str(uuid_module.uuid4())
    context["p_full_plan"] = str(uuid_module.uuid4())
    context["p_empty_plan"] = str(uuid_module.uuid4())

    async def _preset() -> None:
        from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        await _save_snapshot(
            context,
            CheckpointSnapshot(
                session_id=f"{BLM_PLANNING_SESSION_PREFIX}{context['p_mid_plan']}",
                state_data=_make_latest_state(
                    context["p_mid_plan"],
                    completed=2,
                    degraded_steps=[],
                    timeline_steps=(_STEP_SEQUENCE[0], _STEP_SEQUENCE[1]),
                ),
            ),
        )
        await _save_snapshot(
            context,
            CheckpointSnapshot(
                session_id=f"{BLM_PLANNING_SESSION_PREFIX}{context['p_full_plan']}",
                state_data=_make_latest_state(
                    context["p_full_plan"],
                    completed=8,
                    degraded_steps=[],
                    timeline_steps=_STEP_SEQUENCE,
                ),
            ),
        )

    _run_async(_preset(), context["_loop"])


@when("分别构建三 plan 分析师视图")
def build_three_plan_views(context: dict[str, Any]) -> None:
    """S2 When：三 plan 分别构建（服务直调——P-empty 零快照幂等读）."""
    service = _build_view_service(context)
    for key in ("p_mid_plan", "p_full_plan", "p_empty_plan"):
        context["views"][key] = _run_async(service.build_analyst_view(plan_id=context[key]), context["_loop"])


@then("P-mid 六阶段派生与预置一致")
def verify_p_mid_stages(context: dict[str, Any]) -> None:
    """S2：P-mid（阶段1 completed+阶段2 in_progress 1/7+后四 not_started）."""
    progress = context["views"]["p_mid_plan"].progress
    statuses = [stage.status.value for stage in progress.stages]
    assert statuses == ["completed", "in_progress", "not_started", "not_started", "not_started", "not_started"]
    assert progress.stages[0].step_completed == 1
    assert progress.stages[0].step_total == 1
    assert progress.stages[1].step_completed == 1  # 仅 trend 一步
    assert progress.stages[1].step_total == 7


@then("P-full 六阶段派生与预置一致")
def verify_p_full_stages(context: dict[str, Any]) -> None:
    """S2：P-full（阶段1/2 全 completed 且 step_completed==step_total+后四 not_started）."""
    progress = context["views"]["p_full_plan"].progress
    statuses = [stage.status.value for stage in progress.stages]
    assert statuses == ["completed", "completed", "not_started", "not_started", "not_started", "not_started"]
    assert progress.stages[0].step_completed == progress.stages[0].step_total == 1
    assert progress.stages[1].step_completed == progress.stages[1].step_total == 7


@then("P-empty 六阶段框架恒在全未启动")
def verify_p_empty_stages(context: dict[str, Any]) -> None:
    """S2：P-empty（available=False+六阶段框架恒在+全 not_started——静态清单不依赖快照）."""
    view = context["views"]["p_empty_plan"]
    assert view.progress.available is False
    statuses = [stage.status.value for stage in view.progress.stages]
    assert statuses == ["not_started"] * 6
    for stage in view.progress.stages:
        assert stage.step_completed == 0
    assert view.progress.total_steps == 0  # 空态默认值钦定（R3-F2——总数语义由 stages 框架承载）
    assert view.progress.progress_percent == 0


# ===================================================================
# AC-4 溯源段统计与跳转混合判别
# ===================================================================


@scenario(
    "test_acceptance_analyst_view.feature",
    "溯源段统计与跳转混合判别",
)
def test_traceability_statistics() -> None:
    """S4/AC-4 溯源段统计（五计数+跳转混合+树顶层键透传+空归档对照腿）."""
    pass


@given("预置溯源归档族（两分析阶段三切片实例与跳转真假混合文档节点）")
def preset_traceability_family(context: dict[str, Any], pg_session: Any) -> None:
    """S4 预置（A 面通道）：2 stage×3 chunk 实例+jump_ready 真假混合（_preset_full_archive_family 钦定形态）."""
    _a_mode_enter(context, pg_session)
    plan_id = str(uuid_module.uuid4())
    _preset_full_archive_family(context, plan_id)
    context["_active_plan"] = plan_id


@then("五计数与预置归档形态一致")
def verify_traceability_counts(context: dict[str, Any]) -> None:
    """S4：五计数+树顶层哨兵透传（chunk_count≠stage_count 判别+jump_ready 混合判别）."""
    traceability = context["view"].traceability
    assert traceability.available is True
    assert traceability.stage_count == 2, "分析层 StageNode 计数应为 2（synthesis 行不计入）"
    assert traceability.chunk_count == 3, "切片层 ChunkNode 实例计数应为 3（≠stage_count 判别计数面错接）"
    assert traceability.document_count == 3, "文档层 DocumentNode 实例计数应为 3"
    assert traceability.jump_ready_count == 2, "jump_ready 应为 2（True 2+False 1 混合判别——既非全 0 亦非全量）"
    assert traceability.degraded_stage_count == 0
    assert traceability.tree_build_degraded is False, "树顶层哨兵应透传 False（正常树形态）"


@then("无归档 plan 溯源段为空态不抛异常")
def verify_empty_archive_traceability(context: dict[str, Any]) -> None:
    """S4 对照腿：无归档 plan → 空树幂等 → 溯源段 available=False+五计数 0+不抛（「没有数据」非「拿不到数据」）."""
    empty_plan = str(uuid_module.uuid4())
    service = _build_view_service(context)
    view = _run_async(service.build_analyst_view(plan_id=empty_plan), context["_loop"])
    assert view.traceability.available is False
    assert view.traceability.stage_count == 0
    assert view.traceability.chunk_count == 0
    assert view.traceability.document_count == 0
    assert view.traceability.jump_ready_count == 0
    assert view.traceability.degraded_stage_count == 0
    assert view.traceability.tree_build_degraded is False
    assert view.build_degraded is False


# ===================================================================
# AC-5 空 plan 幂等读四断言
# ===================================================================


@scenario(
    "test_acceptance_analyst_view.feature",
    "空 plan 幂等读四断言",
)
def test_empty_plan_idempotent_read() -> None:
    """S5/AC-5 空 plan 幂等读（6 键恒在+build_degraded False+toolbox 完整+两段空态框架）."""
    pass


@given("预置零数据的空 plan")
def preset_empty_plan(context: dict[str, Any]) -> None:
    """S5 Given：空 plan 现场生成（零快照零归档——工具箱静态真源与 plan 正交）."""
    context["_empty_plan"] = str(uuid_module.uuid4())


@when("构建空 plan 分析师视图")
def build_empty_plan_view(context: dict[str, Any]) -> None:
    """S5 When：空 plan 服务直调（幂等读不抛——四先例族延续）."""
    service = _build_view_service(context)
    context["view"] = _run_async(service.build_analyst_view(plan_id=context["_empty_plan"]), context["_loop"])


@then("视图 6 键恒在且 build_degraded 为 False")
def verify_empty_view_keys(context: dict[str, Any]) -> None:
    """S5：空 plan 6 键恒在+build_degraded False（「没有数据」非「拿不到数据」——空态分立第三连）."""
    view = context["view"]
    assert _field_names(view) == {
        "plan_id",
        "generated_at",
        "build_degraded",
        "toolbox",
        "progress",
        "traceability",
    }
    assert view.build_degraded is False


@then("工具箱段完整 23 工具")
def verify_empty_plan_toolbox(context: dict[str, Any]) -> None:
    """S5：toolbox 段照常完整 23 工具（静态真源与 plan 正交——三段中唯一恒数据段）."""
    toolbox = context["view"].toolbox
    assert toolbox.degraded is False
    assert toolbox.total_tools == 23
    assert len(toolbox.tools) == 23
    assert len(toolbox.categories) == 5


@then("进度与溯源两段空态框架恒在")
def verify_empty_plan_two_sections(context: dict[str, Any]) -> None:
    """S5：progress available=False+六阶段框架 not_started 恒在+traceability available=False+五计数 0."""
    progress = context["view"].progress
    assert progress.available is False
    assert progress.degraded is False
    assert [stage.status.value for stage in progress.stages] == ["not_started"] * 6
    assert progress.phase is None
    assert progress.current_step is None
    traceability = context["view"].traceability
    assert traceability.available is False
    assert traceability.degraded is False
    assert traceability.stage_count == 0
    assert traceability.jump_ready_count == 0


# ===================================================================
# AC-5 畸形 plan_id 守卫 242
# ===================================================================


@scenario(
    "test_acceptance_analyst_view.feature",
    "畸形 plan_id 守卫 242",
)
def test_malformed_plan_id_242() -> None:
    """S7/AC-5 畸形 plan_id（编程面用例守卫——242 单源）."""
    pass


@given("空数据服务在位")
def empty_services_ready(context: dict[str, Any]) -> None:
    """S7 Given：Background 探测已承载（无预置——守卫测试不触达数据面）."""
    context["_guard_ready"] = True


@when("以畸形 plan_id 请求分析师视图")
def request_with_malformed_plan_id(context: dict[str, Any]) -> None:
    """S7 When：畸形 plan_id 经用例守卫（import 在 try 外保证红阶段可达——6-8 直系）."""
    from src.application.use_cases.get_analyst_view import GetAnalystViewUseCase

    use_case = GetAnalystViewUseCase(view_service=_build_view_service(context))
    try:
        _run_async(use_case.execute(plan_id="not-a-uuid"), context["_loop"])
        context["malformed_error"] = None
    except Exception as error:  # 异常记录供断言步（242 守卫形态验证——绿阶段为 EntityValidationError）
        context["malformed_error"] = error


@then("抛出 EntityValidationError 且 code 为 242")
def verify_malformed_242(context: dict[str, Any]) -> None:
    """S7：EntityValidationError+code 值级断言（EXCEPTION_242——编程面 pytest.raises 分立形态）."""
    from src.domain.exceptions import EntityValidationError

    error = context["malformed_error"]
    assert isinstance(error, EntityValidationError), f"应为 EntityValidationError（实测 {type(error).__name__}）"
    assert error.code == "EXCEPTION_242"


# ===================================================================
# AC-6 CLI 全数据输出
# ===================================================================


@scenario(
    "test_acceptance_analyst_view.feature",
    "CLI 全数据输出",
)
def test_cli_full_data_output() -> None:
    """S8/AC-6 CLI 全数据输出（三段分隔行+23 工具行+六阶段 6 行+溯源统计行+提示行）."""
    pass


@given("CLI 面已预置全数据形态的 plan")
def preset_cli_full_plan(context: dict[str, Any]) -> None:
    """S8 预置（B 面通道）：全数据形态（归档族+快照 3/8）——commit 式预置."""
    plan_id = str(uuid_module.uuid4())
    _preset_full_archive_family(context, plan_id)
    _preset_full_plan_snapshot(context, plan_id)
    context["_active_plan"] = plan_id


@when("CLI 直调 analyst-view 全数据")
def cli_invoke_full_data(context: dict[str, Any]) -> None:
    """S8 When：CLI in-process 直调（双清+clear_session——B 面硬前置）."""
    _run_cli_analyst_view(context)


@then("三段分隔行与 23 工具行与六阶段 6 行齐备")
def verify_cli_three_sections(context: dict[str, Any]) -> None:
    """S8：三段分隔行+工具箱 23 行计数+六阶段 6 行（status 中文+V1 注记后四）."""
    out = context["cli_stdout"]
    lines = out.splitlines()
    assert f"分析师视图（plan: {context['_active_plan']}）" in lines, f"首行应精确匹配（实测={out!r}）"
    for separator in ("── 专业工具箱 ──", "── BLM 进度 ──", "── 溯源摘要 ──"):
        assert separator in lines, f"三段分隔行缺失 {separator}（实测={out!r}）"
    tool_lines = [line for line in lines if line.startswith("  ") and " — " in line]
    assert len(tool_lines) == 23, f"工具行应恰 23 行（实测 {len(tool_lines)}）"
    expected_toolbox_header = (
        "工具: 共 23 种（ACTIVE） | 分类: environment_analysis×3 competitive_analysis×3 "
        "strategic_selection×6 business_model×3 execution_management×8"
    )
    assert expected_toolbox_header in lines, f"工具箱首行应精确匹配（实测={out!r}）"
    stage_names = ("业绩差距分析", "市场洞察", "战略意图与目标", "创新焦点", "业务设计", "执行设计")
    stage_lines = [line for line in lines if any(name in line for name in stage_names)]
    assert len(stage_lines) == 6, f"六阶段行应恰 6 行（实测 {len(stage_lines)}）"
    assert "  1. 业绩差距分析: [██████████] 已完成（1/1）" in lines, "阶段 1 行应精确匹配（10 格全 █）"
    assert "  2. 市场洞察: [███░░░░░░░] 进行中（2/7）" in lines, "阶段 2 行应精确匹配（k=round(2/7*10)=3）"
    v1_lines = [line for line in lines if "（V1 交付）" in line]
    assert len(v1_lines) == 4, f"后四阶段 V1 注记应恰 4 行（实测 {len(v1_lines)}）"
    assert "进度: 3/8（37%） | 当前: market_customer | 降级: 1 步" in lines, "进度行应精确匹配（快照直读口径）"


@then("溯源统计行与提示行在位")
def verify_cli_traceability_lines(context: dict[str, Any]) -> None:
    """S8：溯源统计行（三层计数+可跳转）+操作提示行（指向既有 trace-tree 命令）."""
    lines = context["cli_stdout"].splitlines()
    assert "分析: 2 | 切片: 3 | 文档: 3 | 可跳转: 2" in lines, "溯源统计行应精确匹配（三层有效计数+jump_ready）"
    assert f"提示: 执行 trace-tree --plan-id {context['_active_plan']} 查看完整溯源树" in lines, (
        "操作提示行应指向既有 trace-tree 命令"
    )


@then("exit code 为 0")
def verify_cli_exit_zero(context: dict[str, Any]) -> None:
    """S8/S9 腿1：正常退出 0（含空 plan 空态——空态是正常态非错误）."""
    assert context["cli_exit_code"] == 0, f"exit code 应为 0（实测 {context['cli_exit_code']}）"


# ===================================================================
# AC-6 CLI 空态与畸形 stderr
# ===================================================================


@scenario(
    "test_acceptance_analyst_view.feature",
    "CLI 空态与畸形 plan_id stderr",
)
def test_cli_empty_and_malformed() -> None:
    """S9/AC-6 CLI 空态输出（六阶段框架恒在+exit 0）+畸形 242 stderr（exit 1）."""
    pass


@given("CLI 面已预置空 plan")
def preset_cli_empty_plan(context: dict[str, Any]) -> None:
    """S9 Given：空 plan 现场生成（零快照零归档）."""
    context["_empty_plan"] = str(uuid_module.uuid4())
    context["_active_plan"] = context["_empty_plan"]


@when("CLI 直调 analyst-view 空态")
def cli_invoke_empty_plan(context: dict[str, Any]) -> None:
    """S9 腿1 When：空 plan CLI 直调（幂等读——空态是正常态）."""
    _run_cli_analyst_view(context, plan_id=context["_empty_plan"])


@then("六阶段框架行恒在且工具箱照常且溯源统计行全 0 且 exit code 为 0")
def verify_cli_empty_output(context: dict[str, Any]) -> None:
    """S9 腿1：空态输出=首行+三段空态行（工具箱照常 23 行+进度无快照+六阶段框架+溯源全 0+提示行）."""
    out = context["cli_stdout"]
    lines = out.splitlines()
    assert "进度: 无快照" in lines, "空态进度行应为「进度: 无快照」"
    stage_lines = [line for line in lines if "（V1 交付）" in line or "未启动" in line]
    assert len(stage_lines) >= 6, f"六阶段框架行恒在（实测 {len(stage_lines)} 行）"
    tool_lines = [line for line in lines if line.startswith("  ") and " — " in line]
    assert len(tool_lines) == 23, "空 plan 工具箱段照常 23 行（静态真源正交性）"
    assert "分析: 0 | 切片: 0 | 文档: 0 | 可跳转: 0" in lines, "溯源统计行恒在全 0 形态（R2 钉死）"
    assert f"提示: 执行 trace-tree --plan-id {context['_empty_plan']} 查看完整溯源树" in lines, "提示行恒在"
    assert "（部分数据降级）" not in lines[0], "空态首行不应带降级标记"
    assert "（部分树数据降级）" not in out, "空态不应带树降级标记"


@when("CLI 直调 analyst-view 传入畸形 plan_id")
def cli_invoke_malformed(context: dict[str, Any]) -> None:
    """S9 腿2 When：畸形 plan_id CLI 直调（CLI 层 UUID 守卫——[EXCEPTION_242] stderr）."""
    _run_cli_analyst_view(context, plan_id="not-a-uuid")


@then("stderr 含 EXCEPTION_242 且 exit code 为 1")
def verify_cli_malformed_stderr(context: dict[str, Any]) -> None:
    """S9 腿2：畸形 plan_id → exit 1 + stderr [EXCEPTION_242]（6-8 前缀统一先例）."""
    assert context["cli_exit_code"] == 1, f"exit code 应为 1（实测 {context['cli_exit_code']}）"
    assert "[EXCEPTION_242]" in context["cli_stderr"], f"stderr 应含 [EXCEPTION_242]（实测 {context['cli_stderr']!r}）"


# ===================================================================
# AC-7 性能采样 20 轮 P95
# ===================================================================


@scenario(
    "test_acceptance_analyst_view.feature",
    "性能采样 20 轮 P95",
)
def test_performance_p95() -> None:
    """S10/AC-7 性能 20 轮 P95<800ms（服务面三读窗口——OD-7 ①口径）."""
    pass


@given("性能面已预置全数据形态的 plan 且服务已预热")
def preset_performance_plan(context: dict[str, Any]) -> None:
    """S10 预置（C 面通道——禁 set_session）：全数据形态+预热 2 轮（含首次 load 连接池建立）."""
    plan_id = str(uuid_module.uuid4())
    _preset_full_archive_family(context, plan_id)
    _preset_full_plan_snapshot(context, plan_id)
    context["_active_plan"] = plan_id
    service = _build_view_service(context)
    for _ in range(_WARMUP_ROUNDS):
        _run_async(service.build_analyst_view(plan_id=plan_id), context["_loop"])


@when("采样 20 轮视图构建计时")
def sample_20_rounds(context: dict[str, Any]) -> None:
    """S10 When：20 轮采样计时（perf_counter 毫秒——模块级期望常量独立构造）."""
    service = _build_view_service(context)
    durations: list[float] = []
    for _ in range(_SAMPLE_ROUNDS):
        start = time.perf_counter()
        _run_async(service.build_analyst_view(plan_id=context["_active_plan"]), context["_loop"])
        durations.append((time.perf_counter() - start) * 1000.0)
    context["durations"] = durations


@then("P95 小于 800ms")
def verify_p95(context: dict[str, Any]) -> None:
    """S10：sorted[ceil(0.95*n)-1] 数学口径 P95<800ms（epics L2456 聚合服务面等价口径）."""
    durations = context["durations"]
    assert len(durations) == _SAMPLE_ROUNDS
    p95 = sorted(durations)[math.ceil(_P95_PERCENTILE * len(durations)) - 1]
    assert p95 < _P95_LIMIT_MS, f"P95 {p95:.1f}ms 超门禁 {_P95_LIMIT_MS}ms（全量: {sorted(durations)}）"


# ===================================================================
# AC-7 并发 20 路两两相等
# ===================================================================


@scenario(
    "test_acceptance_analyst_view.feature",
    "并发 20 路两两相等",
)
def test_concurrent_20_reads() -> None:
    """S11/AC-7 并发 20 路（gather 全成功+排除集单键剔除后两两相等——OD-7 ②口径）."""
    pass


@given("并发面已预置全数据形态的 plan")
def preset_concurrent_plan(context: dict[str, Any]) -> None:
    """S11 预置（C 面通道——禁 set_session，每路 fallback 独立会话）：全数据形态."""
    plan_id = str(uuid_module.uuid4())
    _preset_full_archive_family(context, plan_id)
    _preset_full_plan_snapshot(context, plan_id)
    context["_active_plan"] = plan_id


@when("20 路并发构建分析师视图")
def concurrent_20_builds(context: dict[str, Any]) -> None:
    """S11 When：asyncio.gather 20 路并发读（服务无状态约束——禁 set_session 每路独立会话）."""
    service = _build_view_service(context)
    plan_id = context["_active_plan"]

    async def _gather() -> Any:
        return await asyncio.gather(*[service.build_analyst_view(plan_id=plan_id) for _ in range(_CONCURRENCY)])

    context["concurrent_views"] = list(_run_async(_gather(), context["_loop"]))


@then("全部成功且剔除生成时间后两两相等")
def verify_concurrent_equality(context: dict[str, Any]) -> None:
    """S11：20 路全成功+asdict 剔除 {generated_at} 单键后两两相等（排除集最小化——OD-6 联动收益）."""

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

    views = context["concurrent_views"]
    assert len(views) == _CONCURRENCY
    assert all(view is not None for view in views), "20 路应全部成功不抛"
    serialized = {_serialize(view) for view in views}
    assert len(serialized) == 1, f"剔除生成时间后应两两相等，实际 {len(serialized)} 种形态"


# ===================================================================
# 收尾 src 与四测试目录完成清单——存在性断言
# ===================================================================


@scenario(
    "test_acceptance_analyst_view.feature",
    "src 与四测试目录完成清单",
)
def test_completion_checklist() -> None:
    """S12/收尾 src 与四测试目录完成清单存在性断言."""
    pass


@then("src 新增与修改文件存在")
def verify_completion_src_files() -> None:
    """S12：src 五项存在性（File List 为准——6-8 S12 形态）."""
    for label, relative in _COMPLETION_SRC_FILES.items():
        path = ROOT / relative
        assert path.is_file(), f"完成清单缺 {label}: {relative}"


@then("四测试目录新增与修改文件存在")
def verify_completion_test_files() -> None:
    """S12：四测试目录九项存在性."""
    for label, relative in _COMPLETION_TEST_FILES.items():
        path = ROOT / relative
        assert path.is_file(), f"完成清单缺 {label}: {relative}"
