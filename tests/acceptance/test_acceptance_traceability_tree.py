"""Acceptance tests for Story 6-7 - 溯源树展示（四层追溯聚合查询）.

真实服务验收（零 mock——归档行直交 + Qdrant 点预置 + PG documents 行预置三通道装配；
本 Story 验收装配面零 LLM 零 Embedding——纯读侧聚合，与 6-3~6-6 创建链前置的根本差异）。

场景三属性分档表（12 场景全绑定——S 编号为 6-7 自有编号）：
    | 场景 | AC | 调用面 | 红阶段形态 |
    |------|----|--------|-----------|
    | S1 全树四层落位 | AC-1 | 编程面（服务直调） | 运行期 ImportError（traceability_tree 模块缺失） |
    | S2 结论层双形态 | AC-1 | 编程面 | 同上 |
    | S3 depth 懒加载三档 | AC-2 | 编程面 | 同上 |
    | S4 跳转载荷与脏形态 | AC-3 | 编程面 | 同上 |
    | S5 多 run 叠加判别 | AC-4 | 编程面 | 同上 |
    | S6 kind 过滤 | AC-4 | 编程面 | 同上 |
    | S7 降级链路三态两层 | AC-5 | 编程面 | 同上 |
    | S8 空计划+畸形 242 | AC-5 | 编程面（用例守卫） | 同上 |
    | S9 CLI 树形输出 | AC-6 | CLI in-process 直调 | argparse invalid choice exit 2 → 断言步红 |
    | S10 CLI 过滤+242 stderr | AC-6 | CLI in-process 直调 | 同上 |
    | S11 性能采样 | AC-7 | 编程面（20 轮计时） | 运行期 ImportError |
    | S12 完成清单存在性 | 收尾 | 文件系统断言 | Then 文件不存在 AssertionError |

epics 架构测试三项落位对账（epics L2366-2368）：
    - 溯源树结构测试 → S1/S2；交互式展开测试 → S3；Bounding Box 跳转测试 → S4
    （跳转载荷组装口径——OD-7 口径差声明：CLI 无跳转运行时，Web 点击跳转归 6-8）

性能三段口径（OD-7——验收 docstring 落档）：
    ① 加载 P95<300ms = build_trace_tree 服务面窗口（query_archive + get_point×N + find×M 去重后串行）；
    ② 「Bounding Box 跳转响应<300ms」以跳转载荷组装口径承载（depth=4 全树窗口含载荷组装即覆盖）；
    ③ 「溯源定位准确率≥95%」以解析成功率口径承载（resolved/(resolved+missing) 节点统计——
       真值口径（人工抽检坐标正确性）归部署验证，Fake/预置数据无真值面）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_traceability_tree.py -v
"""

from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenario, then, when

pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.database,
    pytest.mark.redis,
    pytest.mark.qdrant,
    pytest.mark.xdist_group("blm-planning-perf"),
]

# ===================================================================
# Paths & Constants（模块级期望常量独立构造——性能采样纪律）
# ===================================================================

ROOT = Path(__file__).resolve().parents[2]

_P95_LIMIT_MS: float = 300.0
_P95_PERCENTILE: float = 0.95
_SAMPLE_ROUNDS: int = 20
_WARMUP_ROUNDS: int = 2

_GAP_STAGE: str = "performance_gap"
_TREND_STAGE: str = "market_insight_trend"
_COMPETITION_STAGE: str = "market_insight_competition"
_SYNTHESIS_STAGE: str = "market_insight_synthesis"

# 独立测试 collection（TestTenant/uuid 前缀——预置与读回同 collection 单源；
# CLI 面 monkeypatch BLM_SEARCH_COLLECTION 桥接同值）
_COLLECTION: str = f"trace-tree-acceptance-{uuid.uuid4().hex[:8]}"

_VECTOR_DIM: int = 1024  # 与生产 embedding 及适配器维度校验对齐（6-5b 同款字面量向量）

# 完成清单（S12 断言对象 = File List 的 src/测试 15 项存在性；
# 两 md 台账（deferred-work/sprint-status）与故事文件不入断言面——修改性断言物理不可写，DR3-10）
_COMPLETION_SRC_FILES: dict[str, str] = {
    "端口契约（五 VO + TraceabilityTreePort）": "src/application/ports/traceability_tree.py",
    "树服务（四段编排）": "src/application/services/traceability_tree_service.py",
    "查询用例（双守卫+透传）": "src/application/use_cases/get_traceability_tree.py",
    "payload 扩键（chunk_indexing_handler 6→8 键）": "src/application/event_handlers/chunk_indexing_handler.py",
    "CLI trace-tree 子命令": "src/entrypoints/agent_cli.py",
    "组合根两注册块": "src/composition_root.py",
}
_COMPLETION_TEST_FILES: dict[str, str] = {
    "服务单测": "tests/unit/application/test_traceability_tree_service.py",
    "用例单测": "tests/unit/application/use_cases/test_traceability_tree_use_case.py",
    "架构四验证器": "tests/unit/architecture/test_traceability_tree.py",
    "CLI 单测扩展": "tests/unit/interfaces/cli/test_agent_cli.py",
    "payload 单测扩展（8 键断言）": "tests/unit/infrastructure/workflow/test_document_tasks_index_payload.py",
    "集成四场景": "tests/integration/test_integration_traceability_tree.py",
    "端口契约测试（五断言族）": "tests/contracts/test_port_contract_traceability_tree.py",
    "验收 feature": "tests/acceptance/test_acceptance_traceability_tree.feature",
    "验收 BDD 步骤实现": "tests/acceptance/test_acceptance_traceability_tree.py",
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
    """驱逐 resolver SINGLETON/SCOPED 缓存（CLI 直调双清钦定——R3-1 证伪单清形态防线）。"""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()


@pytest.fixture
def context(event_loop: Any, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> Any:
    """场景级 context dict（数据面预置登记 + CLI 直调产物位 + teardown 清单）。"""
    ctx: dict[str, Any] = {
        "_loop": event_loop,
        "_capsys_ref": capsys,
        "_monkeypatch_ref": monkeypatch,
        "_collection": _COLLECTION,
        "_active_plan": "",
        "_empty_plan": "",
        "_plan_ids": [],
        "_chunk_specs": [],
        "_document_ids": [],
        "tree": None,
        "durations": [],
    }
    yield ctx
    _run_async(_teardown_tree_assets(ctx), event_loop)
    _clear_resolver_caches()


# ===================================================================
# 服务探测与 collection 准备（Background——不可达环境 pytest.skip 动态跳过）
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


def _probe_qdrant_available() -> None:
    """Qdrant 可达性探测（轻量 HTTP /collections——失败 skip）。"""
    from qdrant_client import AsyncQdrantClient

    from tests.environments import get_test_env

    env = get_test_env()
    probe_loop = asyncio.new_event_loop()
    try:

        async def _check() -> bool:
            client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
            try:
                await client.get_collections()
                return True
            except Exception:
                return False
            finally:
                await client.close()

        if not probe_loop.run_until_complete(_check()):
            pytest.skip(f"Qdrant not available at {env.qdrant.host}:{env.qdrant.port}")
    finally:
        probe_loop.close()


def _probe_redis_available() -> None:
    """Redis 可达性探测（bootstrap/组合根 resolve 连接池依赖——失败 skip）。"""
    from redis import asyncio as aioredis

    from tests.environments import get_test_env

    env = get_test_env()
    probe_loop = asyncio.new_event_loop()
    try:

        async def _check() -> bool:
            client = aioredis.Redis(host=env.redis.host, port=env.redis.port)
            try:
                return bool(await client.ping())
            except Exception:
                return False
            finally:
                await client.close()

        if not probe_loop.run_until_complete(_check()):
            pytest.skip(f"Redis not available at {env.redis.host}:{env.redis.port}")
    finally:
        probe_loop.close()


async def _ensure_collection() -> None:
    """独立测试 collection 幂等创建（1024 维——生产 embedding 维度对齐）。"""
    from qdrant_client import AsyncQdrantClient, models

    from tests.environments import get_test_env

    env = get_test_env()
    client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
    try:
        existing = {item.name for item in (await client.get_collections()).collections}
        if _COLLECTION not in existing:
            await client.create_collection(
                collection_name=_COLLECTION,
                vectors_config=models.VectorParams(size=_VECTOR_DIM, distance=models.Distance.COSINE),
            )
    finally:
        await client.close()


# ===================================================================
# 数据面三预置通道（归档行直交 + Qdrant 点预置 + PG documents 行原生 SQL）
# ===================================================================


def _make_tree_archive_service() -> Any:
    """归档预置服务（StrategicArchiveService 全 None 依赖构造——纯 L2 预置）.

    勿照抄 6-4 轻装配的 Fake embedding + 真实 MinIO 形态（会引入 L4 依赖与 minio
    marker 面——DR1-7）；archive_plan 对 None 依赖各步优雅跳过（L3/L4/L5/发布全跳过）。
    """
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


def _make_chain_payload(stage: str, *, index: int = 0, plan_tag: str = "s") -> dict[str, Any]:
    """构造 chain.final_answer 的 payload（三型分派——synthesis/gap/六子）."""
    if stage == _SYNTHESIS_STAGE:
        return {
            "conclusions": [f"综合结论一（{plan_tag}）", f"综合结论二（{plan_tag}）"],
            "degraded_inputs": [],
        }
    if stage == _GAP_STAGE:
        return {
            "financial_gap": "财务差距量化：营收达成率 85%",
            "operational_gap": "运营差距分析：交付周期延长",
            "root_causes": ["根因一：组织能力缺口"],
            "portfolio_health": "业务组合健康度：核心稳健",
            "degraded": False,
            "degrade_reason": "",
        }
    step_key = stage.removeprefix("market_insight_")
    return {"summary": f"步骤摘要（{step_key}#{index}）", "findings": ["发现一", "发现二"]}


async def _archive_row(
    ctx: dict[str, Any],
    plan_id: str,
    *,
    stage: str,
    evidence_refs: tuple[str, ...],
    index: int = 0,
    kind: str | None = None,
    plan_tag: str = "s",
) -> None:
    """归档行直交（无 LLM——assumptions/decision_basis 按 6-4 写入侧形态构造）."""
    import uuid as uuid_module

    from src.application.ports.chain_of_thought_archive import CHAIN_ARCHIVE_KIND
    from src.domain.entities.strategic_archive import ArchiveType

    payload = _make_chain_payload(stage, index=index, plan_tag=plan_tag)
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
        "kind": kind if kind is not None else CHAIN_ARCHIVE_KIND,
        "stage": stage,
        "chain": chain_dict,
        "degraded": False,
    }
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
    """chunk 预置规格（Qdrant 点 / PG 行 / metadata.chunks 收录三开关——降级形态构造）."""
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "page_start": page_start,
        "page_end": page_end,
        "upsert_qdrant": upsert_qdrant,
        "insert_pg": insert_pg,
        "pg_chunks_include": pg_chunks_include,
    }


async def _preset_qdrant_points_and_pg_rows(ctx: dict[str, Any]) -> None:
    """按 chunk 规格预置 Qdrant 点（8 业务键——扩键后形态）与 PG documents 行（原生 SQL）.

    Qdrant 点经 L3VectorPort.upsert_points 生产通道（MD5 归一读写对称闭环——禁裸
    client 直写）；PG 行原生 SQL INSERT（metadata 含 chunks+storage_object_key 两键
    ——jump_ready 依赖后者，DR1-16）。
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
                "content": f"切片内容（{spec['chunk_id']}）——用于溯源树预置的语义切片文本",
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
        await l3.upsert_points(_COLLECTION, points)

    # PG 行按 document_id 去重；metadata.chunks 仅收录 pg_chunks_include 的 chunk
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
                            "filename": f"溯源树预置文档-{document_id[:8]}.pdf",
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


async def _teardown_tree_assets(ctx: dict[str, Any]) -> None:
    """teardown 三步链（归档行定向 DELETE / PG 行定向 DELETE / Qdrant collection 整删——执行序，R2-F2 对齐）.

    各步独立 try/except——单步失败不阻断后续清理；归档行清理走原生 SQL 定向 DELETE
    （仓储与服务均无删除方法面——DR2-8）。
    """
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from tests.environments import get_test_env

    env = get_test_env()
    try:
        engine = create_async_engine(
            f"postgresql+asyncpg://{env.postgres.username}:{env.postgres.password}"
            f"@{env.postgres.host}:{env.postgres.port}/{env.postgres.database}"
        )
        try:
            async with engine.begin() as conn:
                if ctx["_plan_ids"]:
                    await conn.execute(
                        sa.text("DELETE FROM strategic_archives WHERE plan_id = ANY(:ids)"),
                        {"ids": list(ctx["_plan_ids"])},
                    )
        finally:
            await engine.dispose()
    except Exception as error:  # teardown 容错（清理失败不阻断测试结果上报——6-5b 静默包裹同款）
        print(f"[teardown:archives] 清理异常（容错）: {error}")
    try:
        engine = create_async_engine(
            f"postgresql+asyncpg://{env.postgres.username}:{env.postgres.password}"
            f"@{env.postgres.host}:{env.postgres.port}/{env.postgres.database}"
        )
        try:
            async with engine.begin() as conn:
                if ctx["_document_ids"]:
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

        client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
        try:
            await client.delete_collection(collection_name=_COLLECTION)
        finally:
            await client.close()
    except Exception as error:  # teardown 容错
        print(f"[teardown:qdrant] 清理异常（容错）: {error}")


def _build_tree_service(ctx: dict[str, Any]) -> Any:
    """构建树服务（延迟 import——红锚：traceability_tree_service 模块缺失即 ImportError）.

    document_repository 严格 ContextVar 会话——_SessionScopedFind 镜像包装
    （组合根 _SessionScopedDocumentRepository 同款，6-5b 集成先例）。
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.application.services.agent_workflow_context import MVP_TENANT_ID
    from src.application.services.traceability_tree_service import TraceabilityTreeService
    from src.domain.ports.resolver import resolve
    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
    from src.infrastructure.storage.postgresql.session_context import session_context
    from tests.environments import get_test_env

    class _SessionScopedFind:
        """find 会话包装（组合根 _SessionScopedDocumentRepository 同款镜像）."""

        def __init__(self, inner: Any, factory: Any) -> None:
            self._inner = inner
            self._factory = factory

        async def find(self, query: Any) -> Any:
            async with session_context(self._factory):
                return await self._inner.find(query)

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
    factory = async_sessionmaker(manager.get_async_engine())
    # cast 契约面收窄（组合根 _SessionScopedDocumentRepository 同款注记——包装仅承载 find 会话语境）
    from typing import cast

    from src.domain.ports.document_repository import DocumentRepositoryPort

    return TraceabilityTreeService(
        strategic_archive_service=_make_tree_archive_service(),
        l3_vector=resolve("l3_vector"),
        document_repository=cast(
            "DocumentRepositoryPort",
            _SessionScopedFind(resolve("document_repository"), factory),
        ),
        search_collection=ctx["_collection"],
        tenant_id=str(MVP_TENANT_ID),
    )


def _preset_common_stages(ctx: dict[str, Any], plan_id: str, stages: list[str], chunk_ids: dict[str, str]) -> None:
    """通用归档预置（每 stage 一行一 chunk）+ 规格登记."""
    for stage in stages:
        _run_async(
            _archive_row(
                ctx,
                plan_id,
                stage=stage,
                evidence_refs=(chunk_ids[stage],),
                plan_tag=plan_id[:8],
            ),
            ctx["_loop"],
        )
        ctx["_chunk_specs"].append(
            _spec_chunk(
                chunk_ids[stage], document_id=ctx.get("_shared_document_id", str(uuid.uuid4())), page_start=3, page_end=3
            )
        )
    ctx["_active_plan"] = plan_id


# ===================================================================
# 场景绑定（12 场景全绑定——R6 模板 @scenario 多行字面量形态）
# ===================================================================


@scenario("test_acceptance_traceability_tree.feature", "S1 全树四层落位与键集值级断言")
def test_s1_full_tree_four_layers() -> None:
    """S1: AC-1 全树四层落位（epics 溯源树结构测试落位——L2366）."""


@scenario("test_acceptance_traceability_tree.feature", "S2 结论层双形态")
def test_s2_conclusion_dual_forms() -> None:
    """S2: AC-1 结论层双形态（epics 溯源树结构测试落位——L2366）."""


@scenario("test_acceptance_traceability_tree.feature", "S3 depth 懒加载三档树形断言")
def test_s3_depth_lazy_loading() -> None:
    """S3: AC-2 depth 懒加载（epics 交互式展开测试落位——L2367）."""


@scenario("test_acceptance_traceability_tree.feature", "S4 页码级跳转载荷与脏形态降级")
def test_s4_jump_payload_and_dirty_chunk() -> None:
    """S4: AC-3 跳转载荷（epics Bounding Box 跳转测试落位——L2368，跳转载荷组装口径）."""


@scenario("test_acceptance_traceability_tree.feature", "S5 多 run 叠加 last-write-wins 判别")
def test_s5_multi_run_last_write_wins() -> None:
    """S5: AC-4 多 run 叠加判别（6.4-DF3 清偿）."""


@scenario("test_acceptance_traceability_tree.feature", "S6 非思维链行 kind 过滤")
def test_s6_kind_filter() -> None:
    """S6: AC-4 kind 过滤."""


@scenario("test_acceptance_traceability_tree.feature", "S7 降级链路三态两层承载")
def test_s7_degraded_chain_two_layers() -> None:
    """S7: AC-5 降级链路三态两层承载."""


@scenario("test_acceptance_traceability_tree.feature", "S8 空计划幂等读与畸形 plan_id 242")
def test_s8_empty_plan_and_malformed_242() -> None:
    """S8: AC-5 空计划幂等读 + 畸形 plan_id 242."""


@scenario("test_acceptance_traceability_tree.feature", "S9 CLI 树形输出")
def test_s9_cli_tree_output() -> None:
    """S9: AC-6 CLI 树形输出."""


@scenario("test_acceptance_traceability_tree.feature", "S10 CLI stage 过滤与畸形 plan_id stderr")
def test_s10_cli_stage_filter_and_stderr() -> None:
    """S10: AC-6 CLI --stage 过滤 + 242 stderr 形态."""


@scenario("test_acceptance_traceability_tree.feature", "S11 性能采样与解析成功率")
def test_s11_performance_sampling() -> None:
    """S11: AC-7 性能采样（P95<300ms）+ 解析成功率 100%."""


@scenario("test_acceptance_traceability_tree.feature", "S12 src 与四测试目录完成清单")
def test_s12_completion_checklist() -> None:
    """S12: 收尾完成清单存在性断言（6-6 S14 形态先例）."""


# ===================================================================
# Background Steps
# ===================================================================


@given("溯源树依赖服务可用")
def traceability_services_available(context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """Background：PG/Qdrant/Redis 三服务探测（不可达 pytest.skip 动态跳过）."""
    context["_capsys_ref"] = capsys
    _probe_pg_available()
    _probe_qdrant_available()
    _probe_redis_available()


@given("溯源树测试租户与隔离 collection 已准备")
def tenant_and_collection_ready(context: dict[str, Any]) -> None:
    """Background：独立测试 collection 幂等创建."""
    _run_async(_ensure_collection(), context["_loop"])


# ===================================================================
# Given Steps（数据面预置——真实服务三通道）
# ===================================================================


@given("预置 2 个 stage 各 1 个 chunk 且同一 document_id 的归档链")
def preset_two_stage_same_document(context: dict[str, Any]) -> None:
    """S1/S3/S9/S10 预置：performance_gap + market_insight_trend 各 1 chunk 同一 document_id（DR3-6）."""
    plan_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    context["_shared_document_id"] = document_id
    _preset_common_stages(
        context,
        plan_id,
        [_GAP_STAGE, _TREND_STAGE],
        {_GAP_STAGE: "chunk-s1-gap", _TREND_STAGE: "chunk-s1-trend"},
    )


@given("evidence chunk 已预置 Qdrant 点与 PG 文档行")
def preset_qdrant_and_pg(context: dict[str, Any]) -> None:
    """按 chunk 规格预置存储面（Qdrant 8 业务键点 + PG documents 行）."""
    _run_async(_preset_qdrant_points_and_pg_rows(context), context["_loop"])


@given("预置 synthesis 与 performance_gap 双行归档链")
def preset_synthesis_and_gap(context: dict[str, Any]) -> None:
    """S2 腿1：synthesis 行 + gap 行（conclusions 联展取自 synthesis；stage_count==1）."""
    plan_id = str(uuid.uuid4())
    _run_async(
        _archive_row(
            context,
            plan_id,
            stage=_SYNTHESIS_STAGE,
            evidence_refs=(),
            plan_tag=plan_id[:8],
        ),
        context["_loop"],
    )
    _run_async(
        _archive_row(
            context,
            plan_id,
            stage=_GAP_STAGE,
            evidence_refs=("chunk-s2-gap",),
            plan_tag=plan_id[:8],
        ),
        context["_loop"],
    )
    context["_active_plan"] = plan_id


@given("预置仅 performance_gap 单行归档链")
def preset_gap_only(context: dict[str, Any]) -> None:
    """S2 腿2：gap-only（无 synthesis 行——结论层 summary 降级空串）."""
    plan_id = str(uuid.uuid4())
    _run_async(
        _archive_row(
            context,
            plan_id,
            stage=_GAP_STAGE,
            evidence_refs=("chunk-s2b-gap",),
            plan_tag=plan_id[:8],
        ),
        context["_loop"],
    )
    context["_active_plan"] = plan_id


@given("预置 1 个 stage 2 个 chunk 一干净一脏的归档链")
def preset_one_stage_two_chunks(context: dict[str, Any]) -> None:
    """S4 预置：market_insight_trend 2 chunk（1 干净+1 脏——脏 chunk 不在 PG metadata.chunks）."""
    plan_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    _run_async(
        _archive_row(
            context,
            plan_id,
            stage=_TREND_STAGE,
            evidence_refs=("chunk-s4-clean", "chunk-s4-dirty"),
            plan_tag=plan_id[:8],
        ),
        context["_loop"],
    )
    context["_chunk_specs"].append(_spec_chunk("chunk-s4-clean", document_id=document_id, page_start=3, page_end=4))
    context["_chunk_specs"].append(
        _spec_chunk("chunk-s4-dirty", document_id=document_id, page_start=7, page_end=8, pg_chunks_include=False)
    )
    context["_active_plan"] = plan_id


@given("预置同 stage 连续两次直交的叠加归档链")
def preset_multi_run_overlay(context: dict[str, Any]) -> None:
    """S5 预置：3 stage 各一行 + 第 4 行为 performance_gap 旧行（连续两次直交）.

    行型钦定 gap 型（input_summary 判别链最短——DR3-11）；新旧行以 index 区分
    chunk_id 判别锚（DR1-4——archived_at 服务自动生成不可外传）。
    """
    plan_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    for stage, index in ((_GAP_STAGE, 0), (_TREND_STAGE, 0), (_COMPETITION_STAGE, 0), (_GAP_STAGE, 1)):
        _run_async(
            _archive_row(
                context,
                plan_id,
                stage=stage,
                evidence_refs=(f"chunk-s5-{stage}-{index}",),
                index=index,
                plan_tag=plan_id[:8],
            ),
            context["_loop"],
        )
        context["_chunk_specs"].append(
            _spec_chunk(f"chunk-s5-{stage}-{index}", document_id=document_id, page_start=2, page_end=2)
        )
    context["_active_plan"] = plan_id


@given("预置混入非思维链归档行的三 stage 归档链")
def preset_kind_filter_chain(context: dict[str, Any]) -> None:
    """S6 预置：3 思维链行 + 1 非思维链行（EVIDENCE_PACKAGE 且 kind≠CHAIN_ARCHIVE_KIND）."""
    plan_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    for stage in (_GAP_STAGE, _TREND_STAGE, _COMPETITION_STAGE):
        _run_async(
            _archive_row(
                context,
                plan_id,
                stage=stage,
                evidence_refs=(f"chunk-s6-{stage}",),
                plan_tag=plan_id[:8],
            ),
            context["_loop"],
        )
        context["_chunk_specs"].append(_spec_chunk(f"chunk-s6-{stage}", document_id=document_id, page_start=4, page_end=4))
    _run_async(
        _archive_row(
            context,
            plan_id,
            stage=_TREND_STAGE,
            evidence_refs=("chunk-s6-nonchain",),
            index=9,
            kind="manual_annotation",
            plan_tag=plan_id[:8],
        ),
        context["_loop"],
    )
    context["_active_plan"] = plan_id


@given("预置两 stage 各带一失效引用的归档链")
def preset_degraded_chain(context: dict[str, Any]) -> None:
    """S7 预置：单 plan 两 stage——competition 点删（point_missing）+ trend 文档删（document_missing）."""
    plan_id = str(uuid.uuid4())
    trend_document_id = str(uuid.uuid4())
    _run_async(
        _archive_row(
            context,
            plan_id,
            stage=_COMPETITION_STAGE,
            evidence_refs=("chunk-s7-comp",),
            plan_tag=plan_id[:8],
        ),
        context["_loop"],
    )
    _run_async(
        _archive_row(
            context,
            plan_id,
            stage=_TREND_STAGE,
            evidence_refs=("chunk-s7-trend",),
            plan_tag=plan_id[:8],
        ),
        context["_loop"],
    )
    # competition chunk：不预置 Qdrant 点（点已删——真实删除形态非 mock）
    context["_chunk_specs"].append(
        _spec_chunk("chunk-s7-comp", document_id=str(uuid.uuid4()), page_start=2, page_end=2, upsert_qdrant=False)
    )
    # trend chunk：Qdrant 点在而 PG 文档行不预置（文档已删——真实删除形态非 mock）
    context["_chunk_specs"].append(
        _spec_chunk("chunk-s7-trend", document_id=trend_document_id, page_start=5, page_end=5, insert_pg=False)
    )
    context["_active_plan"] = plan_id


@given("预置零归档行的空 plan")
def preset_empty_plan(context: dict[str, Any]) -> None:
    """S8 腿1：空 plan（零归档行——幂等读语义）."""
    context["_empty_plan"] = str(uuid.uuid4())
    context["_active_plan"] = context["_empty_plan"]


@given("预置多 stage 多 chunk 归档链且服务已预热")
def preset_performance_fixture(context: dict[str, Any]) -> None:
    """S11 预置：3 stage 各 2 chunk（同一 document_id——find 去重后 1 次）+ 首次构建预热."""
    plan_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    refs: tuple[str, ...] = ()
    for stage in (_GAP_STAGE, _TREND_STAGE, _COMPETITION_STAGE):
        for i in (1, 2):
            refs += (f"chunk-s11-{stage}-{i}",)
            context["_chunk_specs"].append(
                _spec_chunk(f"chunk-s11-{stage}-{i}", document_id=document_id, page_start=1 + i, page_end=1 + i)
            )
    for stage in (_GAP_STAGE, _TREND_STAGE, _COMPETITION_STAGE):
        _run_async(
            _archive_row(
                context,
                plan_id,
                stage=stage,
                evidence_refs=tuple(ref for ref in refs if ref.startswith(f"chunk-s11-{stage}-")),
                plan_tag=plan_id[:8],
            ),
            context["_loop"],
        )
    context["_active_plan"] = plan_id
    _run_async(_preset_qdrant_points_and_pg_rows(context), context["_loop"])
    # 预热含首次真实 load（连接池建立——R8-F5 注记继承）
    for _ in range(_WARMUP_ROUNDS):
        _run_async(_build_tree_service(context).build_trace_tree(plan_id=plan_id, depth=4), context["_loop"])


# ===================================================================
# When Steps（构建/CLI/采样——编程面与 CLI 面调用面矩阵）
# ===================================================================


def _build_tree_at_depth(context: dict[str, Any], depth: int) -> None:
    """编程面构建（服务直调——红锚：TraceabilityTreeService 缺失即 ImportError）."""
    service = _build_tree_service(context)
    context["tree"] = _run_async(
        service.build_trace_tree(plan_id=context["_active_plan"], depth=depth),
        context["_loop"],
    )


@when("以 depth=4 构建溯源树")
def build_tree_depth_4(context: dict[str, Any]) -> None:
    """depth=4 全树构建（S1/S4/S5/S6/S7）."""
    _build_tree_at_depth(context, 4)


@when("以 depth=2 构建溯源树")
def build_tree_depth_2(context: dict[str, Any]) -> None:
    """depth=2 构建（S2 双腿/S3 第一档）."""
    _build_tree_at_depth(context, 2)


@when("以 depth=3 构建溯源树")
def build_tree_depth_3(context: dict[str, Any]) -> None:
    """depth=3 构建（S3 第二档）."""
    _build_tree_at_depth(context, 3)


@when("构建空 plan 的溯源树")
def build_empty_plan_tree(context: dict[str, Any]) -> None:
    """空 plan 构建（S8 腿1——幂等读）."""
    _build_tree_at_depth(context, 4)


@when("以畸形 plan_id 请求溯源树")
def request_with_malformed_plan_id(context: dict[str, Any]) -> None:
    """S8 腿2：畸形 plan_id（编程面用例守卫——242 单源；import 在 try 外保证红阶段可达）."""
    from src.application.use_cases.get_traceability_tree import GetTraceabilityTreeUseCase

    use_case = GetTraceabilityTreeUseCase(tree_service=_build_tree_service(context))
    try:
        _run_async(use_case.execute(plan_id="not-a-uuid"), context["_loop"])
        context["malformed_error"] = None
    except Exception as error:  # 异常记录供断言步（242 守卫形态验证——绿阶段为 EntityValidationError）
        context["malformed_error"] = error


def _run_cli_trace_tree(context: dict[str, Any], *, depth: str, stage: str | None = None) -> None:
    """CLI in-process 直调（双清钦定 + monkeypatch BLM_SEARCH_COLLECTION 桥接——DR1-6）."""
    from src.entrypoints import agent_cli

    monkeypatch: pytest.MonkeyPatch = context["_monkeypatch_ref"]
    monkeypatch.setenv("BLM_SEARCH_COLLECTION", context["_collection"])
    _clear_resolver_caches()
    argv = ["trace-tree", "--plan-id", context["_active_plan"], "--depth", depth]
    if stage is not None:
        argv += ["--stage", stage]
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


@when("CLI 直调 trace-tree 全树输出")
def cli_trace_tree_full(context: dict[str, Any]) -> None:
    """S9：CLI 全树输出（--depth 4）."""
    _run_cli_trace_tree(context, depth="4")


@when("CLI 直调 trace-tree 指定 stage 过滤")
def cli_trace_tree_stage_filter(context: dict[str, Any]) -> None:
    """S10 腿1：--stage 过滤（保留结论层行——DR3-7）."""
    _run_cli_trace_tree(context, depth="4", stage=_TREND_STAGE)


@when("CLI 直调 trace-tree 传入畸形 plan_id")
def cli_trace_tree_malformed(context: dict[str, Any]) -> None:
    """S10 腿2：畸形 plan_id → [EXCEPTION_242] stderr + exit 1."""
    context["_active_plan"] = "not-a-uuid"
    _run_cli_trace_tree(context, depth="4")


@when("采样 20 轮树构建计时")
def sample_tree_build_timing(context: dict[str, Any]) -> None:
    """S11：20 轮采样（perf_counter 毫秒窗口——预热已在预置步完成）."""
    service = _build_tree_service(context)
    durations: list[float] = []
    for _ in range(_SAMPLE_ROUNDS):
        start = time.perf_counter()
        context["tree"] = _run_async(
            service.build_trace_tree(plan_id=context["_active_plan"], depth=4),
            context["_loop"],
        )
        durations.append((time.perf_counter() - start) * 1000.0)
    context["durations"] = durations


# ===================================================================
# Then Steps（断言——值级/键集/序三类形态）
# ===================================================================


def _collect_nodes(tree: Any) -> dict[str, list[Any]]:
    """遍历树收集各层节点（断言辅助）."""
    stages = list(tree.root.children)
    chunks: list[Any] = []
    documents: list[Any] = []
    for stage_node in stages:
        chunks.extend(stage_node.children)
        for chunk_node in stage_node.children:
            documents.extend(chunk_node.children)
    return {"stages": stages, "chunks": chunks, "documents": documents}


def _iter_status_nodes(tree: Any) -> list[Any]:
    """收集带 status 键的节点（ChunkNode+DocumentNode——解析成功率统计口径）."""
    nodes: list[Any] = []
    for stage_node in tree.root.children:
        for chunk_node in stage_node.children:
            nodes.append(chunk_node)
            nodes.extend(chunk_node.children)
    return nodes


@then("树节点四层落位且键集完整")
def verify_four_layers_and_keys(context: dict[str, Any]) -> None:
    """S1：四层落位 + 五 VO 键集 exact set 断言 + 值级断言."""
    from dataclasses import fields

    tree = context["tree"]
    assert tree is not None, "树构建失败（context 缺 tree）"
    assert {f.name for f in fields(tree.root)} == {"plan_id", "title", "summary", "stage_count", "children"}
    nodes = _collect_nodes(tree)
    assert len(nodes["stages"]) == 2, f"分析层应 2 节点，实际 {len(nodes['stages'])}"
    assert tree.root.stage_count == 2
    for stage_node in nodes["stages"]:
        assert {f.name for f in fields(stage_node)} == {
            "stage",
            "display_name",
            "summary",
            "degraded",
            "degrade_reason",
            "tools_used",
            "reflection_excerpt",
            "evidence_count",
            "children",
        }
    assert {f.name for f in fields(nodes["chunks"][0])} == {
        "chunk_id",
        "content_excerpt",
        "page_start",
        "page_end",
        "status",
        "children",
    }
    assert {f.name for f in fields(nodes["documents"][0])} == {
        "document_id",
        "filename",
        "version",
        "page",
        "object_key",
        "bucket",
        "bbox",
        "status",
        "jump_ready",
    }
    # 值级断言：chunk_id 与预置一致、document_id 经 get_point payload 解析、filename/page 值级
    chunk_ids = {chunk.chunk_id for chunk in nodes["chunks"]}
    assert chunk_ids == {"chunk-s1-gap", "chunk-s1-trend"}, f"chunk_id 值级断言失败: {chunk_ids}"
    assert all(doc.filename.startswith("溯源树预置文档-") for doc in nodes["documents"])
    page_values = {doc.page for doc in nodes["documents"]}
    assert page_values == {3}, f"page 应取预置 page_start=3，实际 {page_values}"


@then("root.children 序为 BLM 流程规范序")
def verify_children_canonical_order(context: dict[str, Any]) -> None:
    """S1：root.children 序 = performance_gap 在前 + 六子按 MARKET_INSIGHT_STEP_CONFIG 枚举序（DR3-1）."""
    tree = context["tree"]
    actual = [stage_node.stage for stage_node in tree.root.children]
    assert actual == [_GAP_STAGE, _TREND_STAGE], f"流程规范序断言失败: {actual}"


@then("同一 document_id 的两个 DocumentNode 值等且各自在位")
def verify_same_document_duplicate_nodes(context: dict[str, Any]) -> None:
    """S1：嵌套重复非共享（每条 stage→chunk 路径独立——DR3-6 验收级断言锚）."""
    nodes = _collect_nodes(context["tree"])
    documents = nodes["documents"]
    assert len(documents) == 2, f"应 2 个 DocumentNode，实际 {len(documents)}"
    assert documents[0].document_id == documents[1].document_id
    assert documents[0].filename == documents[1].filename
    assert documents[0] is not documents[1], "嵌套重复非共享——两 DocumentNode 应各自在位（同一 dataclass 实例不可共享）"


@then("StageNode 三元组承载完整")
def verify_stage_triple(context: dict[str, Any]) -> None:
    """S1：数据来源（evidence_count）/ 计算逻辑（tools_used+reflection_excerpt）/ 中间结论（summary）."""
    nodes = _collect_nodes(context["tree"])
    gap_node = next(n for n in nodes["stages"] if n.stage == _GAP_STAGE)
    assert gap_node.tools_used == ("tool-performance_gap-0",), f"tools_used 值级断言失败: {gap_node.tools_used}"
    assert gap_node.summary, "summary（中间结论）非空"
    assert gap_node.evidence_count == 1
    assert gap_node.reflection_excerpt.startswith("反思内容（performance_gap#0）")


@then("结论层 summary 为 conclusions 联展非空")
def verify_summary_concat(context: dict[str, Any]) -> None:
    """S2 腿1：conclusions 联展（"\n".join 保序——DR3-8）."""
    tree = context["tree"]
    plan_tag = context["_active_plan"][:8]
    assert tree.root.summary == f"综合结论一（{plan_tag}）\n综合结论二（{plan_tag}）", (
        f"conclusions 联展断言失败: {tree.root.summary!r}"
    )


@then("stage_count 等于 1")
def verify_stage_count_one(context: dict[str, Any]) -> None:
    """S2 双腿：synthesis 不入分析层（DR1-13——错实现给 2 必红）."""
    tree = context["tree"]
    assert tree.root.stage_count == 1, f"stage_count 应 1（synthesis 不产生 StageNode），实际 {tree.root.stage_count}"


@then("结论层 summary 降级为空串")
def verify_summary_downgrade(context: dict[str, Any]) -> None:
    """S2 腿2：无 synthesis 行 → 空串降级."""
    tree = context["tree"]
    assert tree.root.summary == "", f"gap-only 应降级空串，实际 {tree.root.summary!r}"


@then("stage_count 等于 1 且树正常返回")
def verify_stage_count_one_tree_ok(context: dict[str, Any]) -> None:
    """S2 腿2：树正常返回（gap StageNode 在位）."""
    tree = context["tree"]
    assert tree.root.stage_count == 1
    assert [n.stage for n in tree.root.children] == [_GAP_STAGE]


@then("depth=2 时树仅含结论层与分析层")
def verify_depth2_no_chunks(context: dict[str, Any]) -> None:
    """S3 第一档：StageNode.children 恒空元组（切片层零解析）."""
    tree = context["tree"]
    for stage_node in tree.root.children:
        assert stage_node.children == (), f"depth=2 时 StageNode.children 应恒空，实际 {stage_node.children}"


@then("depth=3 时切片层在位且树内零文档层")
def verify_depth3_chunks_only(context: dict[str, Any]) -> None:
    """S3 第二档：ChunkNode 在位 + 全树零 DocumentNode（文档层零解析）."""
    tree = context["tree"]
    nodes = _collect_nodes(tree)
    assert len(nodes["chunks"]) == 2, f"depth=3 切片层应 2 节点，实际 {len(nodes['chunks'])}"
    assert nodes["documents"] == [], f"depth=3 应零 DocumentNode，实际 {len(nodes['documents'])}"


@then("depth=4 时四层全树在位")
def verify_depth4_full_tree(context: dict[str, Any]) -> None:
    """S3 第三档：四层全在位."""
    tree = context["tree"]
    nodes = _collect_nodes(tree)
    assert len(nodes["stages"]) == 2
    assert len(nodes["chunks"]) == 2
    assert len(nodes["documents"]) == 2


@then("DocumentNode 跳转载荷六键值级正确")
def verify_jump_payload_six_keys(context: dict[str, Any]) -> None:
    """S4：document_id/filename/version/page/object_key/bucket 六键值级."""
    nodes = _collect_nodes(context["tree"])
    documents = {doc.page: doc for doc in nodes["documents"]}
    clean_doc = documents[3]
    assert clean_doc.version == 1
    assert clean_doc.object_key == f"raw-documents/acceptance/{clean_doc.document_id}.pdf"
    assert clean_doc.bucket == "raw-documents"
    assert clean_doc.jump_ready is True, "跳转载荷齐备应 jump_ready=True"


@then("bbox 键存在且透传不合成")
def verify_bbox_passthrough(context: dict[str, Any]) -> None:
    """S4：bbox 透传语义（预置 8 业务键无 bbox → 恒 None——不合成坐标，OD-8；R1-F2 收口 is None）."""
    nodes = _collect_nodes(context["tree"])
    for doc in nodes["documents"]:
        assert hasattr(doc, "bbox")
        assert doc.bbox is None, f"预置无 bbox 时不得合成坐标（透传语义），实际 {doc.bbox!r}"


@then("干净 chunk 的 page 取预置页码值")
def verify_clean_chunk_page(context: dict[str, Any]) -> None:
    """S4：page 取 PG metadata.chunks 匹配 page_start."""
    nodes = _collect_nodes(context["tree"])
    documents = {doc.page: doc for doc in nodes["documents"]}
    assert 3 in documents, f"干净 chunk 的 page 应为预置 page_start=3，实际 pages={list(documents)}"


@then("脏 chunk 的 page 降级为 None 且树不抛异常")
def verify_dirty_chunk_page_none(context: dict[str, Any]) -> None:
    """S4：chunk 不在 chunks 列表 → page=None（本 Story VO 契约——非 6-5b 的 0 值语义，DR3-7 防漂移）."""
    nodes = _collect_nodes(context["tree"])
    dirty_docs = [doc for doc in nodes["documents"] if doc.page is None]
    assert len(dirty_docs) == 1, f"脏 chunk 的 DocumentNode.page 应降 None，实际 pages={[d.page for d in nodes['documents']]}"
    assert dirty_docs[0].jump_ready is False, "page=None 时 jump_ready 应 False"


@then("叠加 stage 恰一节点且取最新行值")
def verify_overlay_last_write_wins(context: dict[str, Any]) -> None:
    """S5：stage 分组 last-write-wins（summary/tools_used 取 index=1 新行——判别锚）."""
    tree = context["tree"]
    gap_nodes = [n for n in tree.root.children if n.stage == _GAP_STAGE]
    assert len(gap_nodes) == 1, f"叠加 stage 应恰一节点，实际 {len(gap_nodes)}"
    gap_node = gap_nodes[0]
    assert gap_node.summary == "输入摘要（performance_gap#1）", (
        f"gap 型 summary 应取新行 chain.input_summary，实际 {gap_node.summary!r}"
    )
    assert gap_node.tools_used == ("tool-performance_gap-1",), f"tools_used 应取新行值: {gap_node.tools_used}"


@then("adopted 等于 3 且 total 等于 4")
def verify_adopted_total(context: dict[str, Any]) -> None:
    """S5：adopted/total 对照（run 压制丢弃面可见）."""
    tree = context["tree"]
    assert tree.adopted_archives == 3, f"adopted 应 3（3 stage 各一行采纳），实际 {tree.adopted_archives}"
    assert tree.total_archives == 4, f"total 应 4（kind 过滤后 4 行全思维链），实际 {tree.total_archives}"


@then("非思维链行不进树且不计 total")
def verify_kind_filter_excluded(context: dict[str, Any]) -> None:
    """S6：kind≠CHAIN_ARCHIVE_KIND 的 EVIDENCE_PACKAGE 行不进树（kind 过滤）."""
    tree = context["tree"]
    assert [n.stage for n in tree.root.children] == [_GAP_STAGE, _TREND_STAGE, _COMPETITION_STAGE]
    summaries = [n.summary for n in tree.root.children if n.stage == _TREND_STAGE]
    assert len(summaries) == 1
    assert "#9" not in summaries[0], f"非思维链行（index=9）不应进树: {summaries[0]!r}"


@then("total 等于 3")
def verify_total_three(context: dict[str, Any]) -> None:
    """S6：total==3（kind 口径值级断言——DR1-12）."""
    tree = context["tree"]
    assert tree.total_archives == 3, f"kind 过滤后 total 应 3，实际 {tree.total_archives}"


@then("point_missing 与 document_missing 两态各一专属断言段")
def verify_degraded_two_statuses(context: dict[str, Any]) -> None:
    """S7：chunk 层 point_missing / 文档层 document_missing 两态两层承载."""
    tree = context["tree"]
    nodes = _collect_nodes(tree)
    by_chunk = {chunk.chunk_id: chunk for chunk in nodes["chunks"]}
    comp_chunk = by_chunk["chunk-s7-comp"]
    assert comp_chunk.status == "point_missing", f"competition chunk 应 point_missing，实际 {comp_chunk.status}"
    assert comp_chunk.children == (), "point_missing 的 ChunkNode 应无子节点"
    trend_chunk = by_chunk["chunk-s7-trend"]
    assert trend_chunk.status == "resolved", f"trend chunk 点在应 resolved，实际 {trend_chunk.status}"
    assert trend_chunk.children[0].status == "document_missing", (
        f"trend 文档行已删应 document_missing，实际 {trend_chunk.children[0].status}"
    )


@then("degraded_stages 为升序元组")
def verify_degraded_stages_ascending(context: dict[str, Any]) -> None:
    """S7：stage 级降级上卷（升序去重——DR1-9）."""
    tree = context["tree"]
    assert tree.degraded_stages == (_COMPETITION_STAGE, _TREND_STAGE), (
        f"degraded_stages 应升序 ({_COMPETITION_STAGE}, {_TREND_STAGE})，实际 {tree.degraded_stages}"
    )


@then("resolved 与 missing 节点计数值级正确")
def verify_resolved_missing_counts(context: dict[str, Any]) -> None:
    """S7：resolved/(resolved+missing) 节点统计值级（AC-7 解析成功率落位锚——DR3-3/DR3-5）."""
    tree = context["tree"]
    status_nodes = _iter_status_nodes(tree)
    resolved = [n for n in status_nodes if n.status == "resolved"]
    missing = [n for n in status_nodes if n.status != "resolved"]
    assert len(resolved) == 1, f"resolved 节点应 1（trend chunk），实际 {len(resolved)}"
    assert len(missing) == 2, f"missing 节点应 2（comp chunk + trend doc），实际 {len(missing)}"


@then("仅根节点空树且零异常")
def verify_empty_tree(context: dict[str, Any]) -> None:
    """S8 腿1：空计划幂等读（键恒在——6-2 R1-6 七键契约同族）."""
    tree = context["tree"]
    assert tree.root.children == ()
    assert tree.root.stage_count == 0
    assert tree.adopted_archives == 0
    assert tree.total_archives == 0


@then("build_degraded 为 False")
def verify_build_not_degraded(context: dict[str, Any]) -> None:
    """S8 腿1：空树与真空树分立（build_degraded=False——无数据非拿不到数据）."""
    assert context["tree"].build_degraded is False


@then("抛出 EntityValidationError 且 code 为 242")
def verify_malformed_242(context: dict[str, Any]) -> None:
    """S8 腿2：用例层 UUID 守卫（GetBlmChainTraceUseCase 直系先例）."""
    from src.domain.exceptions import EntityValidationError

    error = context.get("malformed_error")
    assert isinstance(error, EntityValidationError), f"应抛 EntityValidationError，实际 {error!r}"
    assert error.code == "EXCEPTION_242", f"code 应 EXCEPTION_242，实际 {error.code}"


@then("输出含四层层级标签")
def verify_cli_four_layer_labels(context: dict[str, Any]) -> None:
    """S9：层级标签前缀（结论/分析/切片/文档——输出即契约）."""
    stdout = context["cli_stdout"]
    assert context["cli_exit_code"] == 0, f"CLI 应 exit 0，实际 {context['cli_exit_code']}（stderr={context['cli_stderr']!r}）"
    for label in ("结论:", "分析:", "切片:", "文档:"):
        assert label in stdout, f"输出缺层级标签 {label!r}（stdout={stdout!r}）"


@then("分析层行序为流程规范序")
def verify_cli_stage_order(context: dict[str, Any]) -> None:
    """S9：CLI 行序=root.children 流程规范序（DR3-1）."""
    stdout = context["cli_stdout"]
    gap_pos = stdout.find("业绩差距分析")
    trend_pos = stdout.find("看趋势")
    assert gap_pos >= 0 and trend_pos >= 0, "输出应含两 stage display_name"
    assert gap_pos < trend_pos, f"流程规范序断言失败：gap({gap_pos}) 应在 trend({trend_pos}) 前"


@then("chunk 行前 8 位与文档行 filename 值级正确")
def verify_cli_value_level_lines(context: dict[str, Any]) -> None:
    """S9：chunk_id 前 8 位 + filename 值级."""
    stdout = context["cli_stdout"]
    assert "chunk-s1" in stdout, "输出应含 chunk_id 前 8 位（chunk-s1）"
    assert "溯源树预置文档-" in stdout, "输出应含预置 filename"


@then("仅展示指定 stage 层且保留结论层行")
def verify_cli_stage_filter(context: dict[str, Any]) -> None:
    """S10 腿1：--stage 过滤（其余 stage 零输出——仅指分析层以下；结论层行保留，DR3-7）."""
    stdout = context["cli_stdout"]
    assert context["cli_exit_code"] == 0
    assert "结论:" in stdout, "--stage 过滤应保留结论层行"
    assert "看趋势" in stdout, "指定 stage（trend）应展示"
    assert "业绩差距分析" not in stdout, "未指定 stage（gap）分析层应零输出"
    assert "chunk-s1-gap" not in stdout, "未指定 stage 的切片行应零输出"


@then("stderr 含 EXCEPTION_242 且 exit code 为 1")
def verify_cli_stderr_242(context: dict[str, Any]) -> None:
    """S10 腿2：畸形 plan_id CLI 形态（[EXCEPTION_242] stderr + exit 1）."""
    assert context["cli_exit_code"] == 1, f"畸形 plan_id 应 exit 1，实际 {context['cli_exit_code']}"
    assert "[EXCEPTION_242]" in context["cli_stderr"], f"stderr 应含 [EXCEPTION_242]，实际 {context['cli_stderr']!r}"


@then("P95 小于 300ms")
def verify_p95(context: dict[str, Any]) -> None:
    """S11：P95 = sorted(durations)[ceil(0.95*n)-1] < 300ms（数学口径——6-3/6-6 同款公式）."""
    durations = context["durations"]
    assert len(durations) == _SAMPLE_ROUNDS
    p95 = sorted(durations)[math.ceil(_P95_PERCENTILE * len(durations)) - 1]
    assert p95 < _P95_LIMIT_MS, f"P95 {p95:.1f}ms 超门禁 {_P95_LIMIT_MS}ms（全量: {sorted(durations)}）"


@then("resolved 节点占比为 100%")
def verify_resolved_ratio_100(context: dict[str, Any]) -> None:
    """S11：解析成功率口径（预置全可解析数据 resolved 占比==100%≥95%）."""
    status_nodes = _iter_status_nodes(context["tree"])
    assert status_nodes, "树应含带 status 节点"
    resolved = [n for n in status_nodes if n.status == "resolved"]
    assert len(resolved) == len(status_nodes), f"全可解析场景 resolved 占比应 100%，实际 {len(resolved)}/{len(status_nodes)}"


@then("src 新增与修改文件存在")
def verify_completion_src_files() -> None:
    """S12：src 六项存在性（File List 为准——DR3-10）."""
    for label, relative in _COMPLETION_SRC_FILES.items():
        path = ROOT / relative
        assert path.is_file(), f"完成清单缺 {label}: {relative}"


@then("四测试目录新增与修改文件存在")
def verify_completion_test_files() -> None:
    """S12：四测试目录九项存在性."""
    for label, relative in _COMPLETION_TEST_FILES.items():
        path = ROOT / relative
        assert path.is_file(), f"完成清单缺 {label}: {relative}"
