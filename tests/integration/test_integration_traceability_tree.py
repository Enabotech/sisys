"""Story 6-7 集成测试——真实链树构建（四场景）

自包含装配类模式（真实 PG/Qdrant/Redis + 组合根 resolve；零 LLM/零 MinIO；
embedding 仅场景④ Fake 豁免——AsyncMock spec EmbeddingServicePort 外部 SaaS
豁免先例 DR1-7；fake.embed_documents 按批次长度等长返回——DR2-6）。

场景清单：
    ① 全链 round-trip（归档两 stage 直交→Qdrant 点 8 业务键预置（扩键后形态——
      实存第 9 键 created_at 存在不计数 DR1-3）→PG 行原生 SQL→树四层值级+jump_ready）
    ② 多 run 判别 + 真实降级（同 stage 连续两次直交→新行采纳+adopted/total 对照；
      Qdrant 点真实删除→point_missing；PG 行真实删除→document_missing）
    ③ 性能采样（20 轮 P95<300ms+预热含首次 load；resolved 占比 100%——OD-7 三段口径）
    ④ ingestion 扩键 round-trip（ChunkIndexingHandler 直调生产通道→共享 "documents"
      collection 落点→get_point 读回 8 业务键+created_at→delete_points 定向点删 DR2-3）

teardown：归档行按 plan_id 定向 DELETE（原生 SQL）+ PG 行定向 DELETE + Qdrant collection
整删（场景④例外：共享 collection 定向点删禁整删）——执行序，R2-F2 对齐；键计数净增 0 纪律。
"""

from __future__ import annotations

import json
import math
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.database,
    pytest.mark.redis,
    pytest.mark.qdrant,
    pytest.mark.xdist_group("blm-planning-perf"),
]

REPO_ROOT = Path(__file__).resolve().parents[2]

_P95_LIMIT_MS: float = 300.0
_P95_PERCENTILE: float = 0.95
_SAMPLE_ROUNDS: int = 20
_WARMUP_ROUNDS: int = 2
_VECTOR_DIM: int = 1024

_GAP_STAGE = "performance_gap"
_TREND_STAGE = "market_insight_trend"
_COMPETITION_STAGE = "market_insight_competition"
_SYNTHESIS_STAGE = "market_insight_synthesis"


@pytest.fixture(autouse=True)
def _fresh_resolver_per_test() -> Any:
    """每测试驱逐 resolver 缓存（SINGLETON/SCOPED——跨 loop 防线，6-5b 同款）."""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()
    yield resolver
    resolver.clear_singleton()
    resolver.clear_scoped()


# ===================================================================
# 装配 helpers（真实服务三通道）
# ===================================================================


def _collection_name() -> str:
    """独立测试 collection（uuid 前缀——预置与读回同 collection 单源）."""
    return f"trace-tree-integration-{uuid.uuid4().hex[:8]}"


def _make_archive_service() -> Any:
    """归档预置服务（StrategicArchiveService 全 None 依赖构造——纯 L2，DR1-7）."""
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


def _make_session_scoped_find(inner: Any) -> Any:
    """find 会话包装（组合根 _SessionScopedDocumentRepository 同款镜像——树服务/handler 共用）."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
    from src.infrastructure.storage.postgresql.session_context import session_context
    from tests.environments import get_test_env

    class _SessionScopedFind:
        """find 会话包装（组合根 _SessionScopedDocumentRepository 同款镜像）."""

        def __init__(self, repo: Any, factory: Any) -> None:
            self._inner = repo
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
    return _SessionScopedFind(inner, factory)


def _make_tree_service(collection: str) -> Any:
    """被测树服务（组合根三依赖 resolve + 独立 collection 注入）.

    document_repository 严格 ContextVar 会话（无 factory fallback——组合根
    _SessionScopedDocumentRepository 同款镜像包装，6-5b 集成先例；服务层保持
    纯 application——session_context 是 infrastructure 模块，测试装配是合法宿主）。
    """
    from src.application.services.agent_workflow_context import MVP_TENANT_ID
    from src.application.services.traceability_tree_service import TraceabilityTreeService
    from src.domain.ports.resolver import resolve

    return TraceabilityTreeService(
        strategic_archive_service=_make_archive_service(),
        l3_vector=resolve("l3_vector"),
        document_repository=_make_session_scoped_find(resolve("document_repository")),
        search_collection=collection,
        tenant_id=str(MVP_TENANT_ID),
    )


def _make_chain_payload(stage: str, *, index: int = 0) -> dict[str, Any]:
    """chain.final_answer payload（三型分派——验收同款）."""
    if stage == _SYNTHESIS_STAGE:
        return {"conclusions": [f"综合结论一（{index}）"], "degraded_inputs": []}
    if stage == _GAP_STAGE:
        return {
            "financial_gap": "财务差距",
            "operational_gap": "运营差距",
            "root_causes": ["根因一"],
            "portfolio_health": "核心稳健",
            "degraded": False,
            "degrade_reason": "",
        }
    return {"summary": f"步骤摘要（{stage}#{index}）", "findings": ["发现一"]}


async def _archive_row(
    plan_id: str,
    *,
    stage: str,
    evidence_refs: tuple[str, ...],
    index: int = 0,
    kind: str | None = None,
) -> None:
    """归档行直交（无 LLM——assumptions/decision_basis 按 6-4 写入侧形态）."""
    import uuid as uuid_module

    from src.application.ports.chain_of_thought_archive import CHAIN_ARCHIVE_KIND
    from src.domain.entities.strategic_archive import ArchiveType

    chain_dict: dict[str, Any] = {
        "input_summary": f"输入摘要（{stage}#{index}）",
        "reflection": f"反思内容（{stage}#{index}）——完整论据链复核",
        "tools_used": [f"tool-{stage}-{index}"],
        "constraints_check": {},
        "final_answer": json.dumps(_make_chain_payload(stage, index=index), ensure_ascii=False),
    }
    service = _make_archive_service()
    await service.archive_plan(
        plan_id=uuid_module.UUID(plan_id),
        plan_type="SP",
        archive_type=ArchiveType.EVIDENCE_PACKAGE,
        assumptions={
            "tools_used": list(chain_dict["tools_used"]),
            "evidence_refs": list(evidence_refs),
        },
        decision_basis={
            "kind": kind if kind is not None else CHAIN_ARCHIVE_KIND,
            "stage": stage,
            "chain": chain_dict,
            "degraded": False,
        },
        execution_deviation={},
        evidence_blob=None,
    )


async def _upsert_points(collection: str, specs: list[dict[str, Any]]) -> None:
    """Qdrant 点预置（L3VectorPort 生产通道——MD5 归一读写对称闭环 DR1-3）."""
    from src.domain.ports.resolver import resolve

    points = [
        {
            "id": spec["chunk_id"],
            "vector": [0.1] * _VECTOR_DIM,
            "payload": {
                "chunk_id": spec["chunk_id"],
                "document_id": spec["document_id"],
                "parent_chunk_id": None,
                "index_level": "child",
                "content": f"切片内容（{spec['chunk_id']}）",
                "chunk_header": f"标题（{spec['chunk_id']}）",
                "page_start": spec["page_start"],
                "page_end": spec["page_end"],
            },
        }
        for spec in specs
    ]
    if points:
        l3 = resolve("l3_vector")
        await l3.upsert_points(collection, points)


async def _insert_pg_document(document_id: str, chunks_meta: list[dict[str, Any]]) -> None:
    """PG documents 行原生 SQL INSERT（metadata 含 chunks+storage_object_key 两键——DR1-16）."""
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.application.services.agent_workflow_context import MVP_TENANT_ID
    from tests.environments import get_test_env

    env = get_test_env()
    engine = create_async_engine(
        f"postgresql+asyncpg://{env.postgres.username}:{env.postgres.password}"
        f"@{env.postgres.host}:{env.postgres.port}/{env.postgres.database}"
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(
                sa.text(
                    "INSERT INTO documents (id, tenant_id, filename, mime_type, file_size_bytes, "
                    "document_type, parse_status, uploaded_by, version, metadata, created_at, updated_at) "
                    "VALUES (CAST(:id AS uuid), :tenant, :filename, 'application/pdf', 1024, "
                    "'other', 'completed', 'integration', 1, CAST(:meta AS jsonb), now(), now())"
                ),
                {
                    "id": document_id,
                    "tenant": str(MVP_TENANT_ID),
                    "filename": f"集成预置文档-{document_id[:8]}.pdf",
                    "meta": json.dumps(
                        {
                            "chunks": chunks_meta,
                            "storage_object_key": f"raw-documents/integration/{document_id}.pdf",
                        },
                        ensure_ascii=False,
                    ),
                },
            )
    finally:
        await engine.dispose()


async def _ensure_collection(collection: str) -> None:
    """独立 collection 幂等创建（vector_size=1024——适配器维度校验对齐）."""
    from qdrant_client import AsyncQdrantClient, models

    from tests.environments import get_test_env

    env = get_test_env()
    client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
    try:
        existing = {item.name for item in (await client.get_collections()).collections}
        if collection not in existing:
            await client.create_collection(
                collection_name=collection,
                vectors_config=models.VectorParams(size=_VECTOR_DIM, distance=models.Distance.COSINE),
            )
    finally:
        await client.close()


async def _drop_collection(collection: str) -> None:
    """collection 整删（teardown——独立测试 collection 专属）."""
    from qdrant_client import AsyncQdrantClient

    from tests.environments import get_test_env

    env = get_test_env()
    client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
    try:
        await client.delete_collection(collection_name=collection)
    finally:
        await client.close()


async def _cleanup_plan_and_documents(plan_ids: list[str], document_ids: list[str]) -> None:
    """归档行与 PG 行定向 DELETE（键计数净增 0 纪律——原生 SQL 唯一通道 DR2-8）.

    两 DELETE 各自独立 try/except（teardown 三步各步独立钦定——单步失败不阻断后续清理）。
    """
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from tests.environments import get_test_env

    env = get_test_env()
    engine = create_async_engine(
        f"postgresql+asyncpg://{env.postgres.username}:{env.postgres.password}"
        f"@{env.postgres.host}:{env.postgres.port}/{env.postgres.database}"
    )
    try:
        try:
            async with engine.begin() as conn:
                if plan_ids:
                    await conn.execute(
                        sa.text("DELETE FROM strategic_archives WHERE plan_id = ANY(:ids)"),
                        {"ids": plan_ids},
                    )
        except Exception as error:  # teardown 容错（清理失败不阻断后续清理）
            print(f"[teardown:archives] 清理异常（容错）: {error}")
        try:
            async with engine.begin() as conn:
                if document_ids:
                    await conn.execute(
                        sa.text("DELETE FROM documents WHERE id = ANY(:ids)"),
                        {"ids": document_ids},
                    )
        except Exception as error:  # teardown 容错
            print(f"[teardown:documents] 清理异常（容错）: {error}")
    finally:
        await engine.dispose()


async def _probe_services() -> None:
    """三真实服务门控探测（PG/Qdrant/Redis——不可达动态 skip；无 MinIO 面）."""
    import sqlalchemy as sa

    from tests.environments import get_test_env

    env = get_test_env()

    async def _probe_pg() -> None:
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(
            f"postgresql+asyncpg://{env.postgres.username}:{env.postgres.password}"
            f"@{env.postgres.host}:{env.postgres.port}/{env.postgres.database}"
        )
        try:
            async with engine.connect() as conn:
                await conn.execute(sa.text("SELECT archive_id FROM strategic_archives LIMIT 1"))
                await conn.execute(sa.text("SELECT id FROM documents LIMIT 1"))
        finally:
            await engine.dispose()

    async def _probe_qdrant() -> None:
        from qdrant_client import AsyncQdrantClient

        client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
        try:
            await client.get_collections()
        finally:
            await client.close()

    async def _probe_redis() -> None:
        from redis import asyncio as aioredis

        client = aioredis.Redis(host=env.redis.host, port=env.redis.port)
        try:
            assert await client.ping()
        finally:
            await client.close()

    for probe, label in ((_probe_pg, "PostgreSQL"), (_probe_qdrant, "Qdrant"), (_probe_redis, "Redis")):
        try:
            await probe()
        except Exception as error:
            pytest.skip(f"{label} not available: {error}")


# ===================================================================
# 场景①：全链 round-trip
# ===================================================================


async def test_scenario_one_full_roundtrip() -> None:
    """场景①：归档直交→Qdrant 8 业务键点→PG 行→树四层值级+jump_ready（AC-1/AC-3）."""
    await _probe_services()
    collection = _collection_name()
    plan_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    specs = [
        {"chunk_id": "int-gap-1", "document_id": document_id, "page_start": 2, "page_end": 2},
        {"chunk_id": "int-trend-1", "document_id": document_id, "page_start": 5, "page_end": 6},
    ]
    await _ensure_collection(collection)
    try:
        await _archive_row(plan_id, stage=_GAP_STAGE, evidence_refs=("int-gap-1",))
        await _archive_row(plan_id, stage=_TREND_STAGE, evidence_refs=("int-trend-1",))
        await _upsert_points(collection, specs)
        await _insert_pg_document(
            document_id,
            [
                {"chunk_id": "int-gap-1", "page_start": 2, "page_end": 2},
                {"chunk_id": "int-trend-1", "page_start": 5, "page_end": 6},
            ],
        )

        service = _make_tree_service(collection)
        tree = await service.build_trace_tree(plan_id=plan_id, depth=4)

        assert tree.build_degraded is False
        assert tree.total_archives == 2
        assert tree.adopted_archives == 2
        assert [s.stage for s in tree.root.children] == [_GAP_STAGE, _TREND_STAGE], "流程规范序"
        gap_chunk = tree.root.children[0].children[0]
        trend_chunk = tree.root.children[1].children[0]
        assert gap_chunk.status == "resolved" and trend_chunk.status == "resolved"
        assert gap_chunk.page_start == 2 and gap_chunk.page_end == 2, "页码经 payload 扩键通道读回"
        assert trend_chunk.page_start == 5 and trend_chunk.page_end == 6
        trend_doc = trend_chunk.children[0]
        assert trend_doc.status == "resolved"
        assert trend_doc.document_id == document_id, "document_id 经 get_point payload 解析"
        assert trend_doc.filename == f"集成预置文档-{document_id[:8]}.pdf"
        assert trend_doc.page == 5, "page 取 PG metadata.chunks 匹配 page_start"
        assert trend_doc.object_key == f"raw-documents/integration/{document_id}.pdf"
        assert trend_doc.bucket == "raw-documents"
        assert trend_doc.jump_ready is True
        assert tree.degraded_stages == ()
    finally:
        await _cleanup_plan_and_documents([plan_id], [document_id])
        await _drop_collection(collection)


# ===================================================================
# 场景②：多 run 判别 + 真实降级
# ===================================================================


async def test_scenario_two_multi_run_and_real_degradation() -> None:
    """场景②：同 stage 连续两次直交→新行采纳；点/文档行真实删除→两态降级（AC-4/AC-5）."""
    await _probe_services()
    collection = _collection_name()
    plan_id = str(uuid.uuid4())
    gap_document_id = str(uuid.uuid4())  # gap 独立文档行（保留——降级段不触达）
    shared_document_id = str(uuid.uuid4())  # trend/comp 共用（降级段真实删除）
    specs = [
        {"chunk_id": "ov-gap-0", "document_id": gap_document_id, "page_start": 1, "page_end": 1},
        {"chunk_id": "ov-gap-1", "document_id": gap_document_id, "page_start": 2, "page_end": 2},
        {"chunk_id": "ov-trend-1", "document_id": shared_document_id, "page_start": 3, "page_end": 3},
        {"chunk_id": "ov-comp-1", "document_id": shared_document_id, "page_start": 4, "page_end": 4},
    ]
    await _ensure_collection(collection)
    try:
        # 3 stage 各一行 + gap 旧行（连续两次直交——archived_at 服务自动 now 微秒差）
        await _archive_row(plan_id, stage=_GAP_STAGE, evidence_refs=("ov-gap-0",), index=0)
        await _archive_row(plan_id, stage=_GAP_STAGE, evidence_refs=("ov-gap-1",), index=1)
        await _archive_row(plan_id, stage=_TREND_STAGE, evidence_refs=("ov-trend-1",))
        await _archive_row(plan_id, stage=_COMPETITION_STAGE, evidence_refs=("ov-comp-1",))
        await _upsert_points(collection, specs)
        await _insert_pg_document(
            gap_document_id,
            [
                {"chunk_id": "ov-gap-1", "page_start": 2, "page_end": 2},
            ],
        )
        await _insert_pg_document(
            shared_document_id,
            [
                {"chunk_id": "ov-trend-1", "page_start": 3, "page_end": 3},
                {"chunk_id": "ov-comp-1", "page_start": 4, "page_end": 4},
            ],
        )

        service = _make_tree_service(collection)
        tree = await service.build_trace_tree(plan_id=plan_id, depth=4)
        # 判别段：gap 新行采纳（index=1）+ adopted/total 对照
        assert tree.total_archives == 4
        assert tree.adopted_archives == 3
        gap_stage = next(s for s in tree.root.children if s.stage == _GAP_STAGE)
        assert gap_stage.summary == "输入摘要（performance_gap#1）", "gap 型取新行 input_summary"
        assert gap_stage.tools_used == ("tool-performance_gap-1",)
        chunk_ids = {c.chunk_id for c in gap_stage.children}
        assert chunk_ids == {"ov-gap-1"}, "采纳行 evidence_refs 取新行"
        assert gap_stage.children[0].children[0].status == "resolved", "gap 独立文档行不受降级段影响"

        # 降级段：真实删除构造（点删+文档行删）
        from src.domain.ports.resolver import resolve

        l3 = resolve("l3_vector")
        await l3.delete_points(collection, ["ov-comp-1"])
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
                await conn.execute(sa.text("DELETE FROM documents WHERE id = CAST(:id AS uuid)"), {"id": shared_document_id})
        finally:
            await engine.dispose()

        rebuilt = await service.build_trace_tree(plan_id=plan_id, depth=4)
        by_chunk: dict[str, Any] = {}
        for stage_node in rebuilt.root.children:
            for chunk_node in stage_node.children:
                by_chunk[chunk_node.chunk_id] = chunk_node
        assert by_chunk["ov-comp-1"].status == "point_missing", "点已真实删除→point_missing"
        assert by_chunk["ov-comp-1"].children == ()
        assert by_chunk["ov-trend-1"].status == "resolved"
        assert by_chunk["ov-trend-1"].children[0].status == "document_missing", "文档行已真实删除→document_missing"
        assert rebuilt.degraded_stages == (_COMPETITION_STAGE, _TREND_STAGE), "升序上卷"
    finally:
        await _cleanup_plan_and_documents([plan_id], [gap_document_id])  # shared 行已在场景内删除
        await _drop_collection(collection)


# ===================================================================
# 场景③：性能采样（OD-7 三段口径——服务面窗口）
# ===================================================================


async def test_scenario_three_performance_sampling() -> None:
    """场景③：20 轮 P95<300ms + resolved 占比 100%（AC-7——真值口径归部署验证注记）."""
    await _probe_services()
    collection = _collection_name()
    plan_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    specs = [
        {"chunk_id": f"perf-{stage}-{i}", "document_id": document_id, "page_start": i, "page_end": i}
        for stage in (_GAP_STAGE, _TREND_STAGE, _COMPETITION_STAGE)
        for i in (1, 2)
    ]
    await _ensure_collection(collection)
    try:
        for stage in (_GAP_STAGE, _TREND_STAGE, _COMPETITION_STAGE):
            await _archive_row(
                plan_id,
                stage=stage,
                evidence_refs=tuple(f"perf-{stage}-{i}" for i in (1, 2)),
            )
        await _upsert_points(collection, specs)
        await _insert_pg_document(
            document_id,
            [{"chunk_id": spec["chunk_id"], "page_start": spec["page_start"], "page_end": spec["page_end"]} for spec in specs],
        )

        service = _make_tree_service(collection)
        for _ in range(_WARMUP_ROUNDS):  # 预热含首次真实 load（连接池建立——R8-F5）
            await service.build_trace_tree(plan_id=plan_id, depth=4)
        durations: list[float] = []
        tree = None
        for _ in range(_SAMPLE_ROUNDS):
            start = time.perf_counter()
            tree = await service.build_trace_tree(plan_id=plan_id, depth=4)
            durations.append((time.perf_counter() - start) * 1000.0)

        p95 = sorted(durations)[math.ceil(_P95_PERCENTILE * len(durations)) - 1]
        assert p95 < _P95_LIMIT_MS, f"P95 {p95:.1f}ms 超门禁 {_P95_LIMIT_MS}ms（全量: {sorted(durations)}）"
        assert tree is not None
        status_nodes = [
            *(c for s in tree.root.children for c in s.children),
            *(d for s in tree.root.children for c in s.children for d in c.children),
        ]
        assert status_nodes and all(n.status == "resolved" for n in status_nodes), "全可解析场景 resolved 占比 100%"
    finally:
        await _cleanup_plan_and_documents([plan_id], [document_id])
        await _drop_collection(collection)


# ===================================================================
# 场景④：ingestion 扩键 round-trip（生产通道级验证）
# ===================================================================


async def test_scenario_four_handler_payload_roundtrip() -> None:
    """场景④：ChunkIndexingHandler 直调→共享 documents 落点→8 业务键读回（DR2-3 collection 偏离）.

    handler 写目标硬编码 "documents"（chunk_indexing_handler.py:215）不受
    BLM_SEARCH_COLLECTION 影响——读回经 get_point("documents", chunk_id)、清理经
    delete_points 定向点删，禁对共享 collection 整删（DR2-3）。
    """
    from unittest.mock import AsyncMock

    from src.application.event_handlers.chunk_indexing_handler import ChunkIndexingHandler
    from src.application.services.agent_workflow_context import MVP_TENANT_ID
    from src.domain.events.workflow_events import RAGIndexed
    from src.domain.ports.resolver import resolve

    await _probe_services()
    plan_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    chunk_ids = [f"ing-doc-{document_id[:8]}-{i}" for i in (1, 2)]
    await _archive_row(plan_id, stage=_GAP_STAGE, evidence_refs=(chunk_ids[0],))  # 归档行仅为 plan 清理登记
    try:
        # PG 行（handler 经 document_repository.find 读 metadata.chunks——生产通道）
        await _insert_pg_document(
            document_id,
            [
                {"chunk_id": chunk_ids[0], "page_start": 7, "page_end": 8, "content": "扩键块一", "index_level": "child"},
                {"chunk_id": chunk_ids[1], "page_start": 9, "page_end": 9, "content": "扩键块二", "index_level": "child"},
            ],
        )

        # Fake-embedding 豁免（DR1-7——外部 SaaS；按批次长度等长返回 DR2-6）
        from src.domain.ports.embedding_service import EmbeddingServicePort

        fake_embedding = AsyncMock(spec=EmbeddingServicePort)
        fake_embedding.embed_query = AsyncMock(return_value=[0.1] * _VECTOR_DIM)
        fake_embedding.embed_documents = AsyncMock(side_effect=lambda batch: [[0.1] * _VECTOR_DIM for _ in batch])
        # sparse 不可用形态：抛异常走 handler 真实降级分支（Sparse 失败不阻断 Dense 索引）
        fake_embedding.embed_sparse = AsyncMock(side_effect=RuntimeError("sparse not configured"))
        fake_embedding.close = AsyncMock()

        handler = ChunkIndexingHandler(
            embedding_service=fake_embedding,
            l3_vector=resolve("l3_vector"),
            # find 会话语境（handler 直调无事件消费中间件会话——_SessionScopedFind
            # 镜像包装同款；生产链路 handler 在消费上下文内活动会话运行）
            document_repository=_make_session_scoped_find(resolve("document_repository")),
        )
        event = RAGIndexed(document_id=uuid.UUID(document_id), chunk_count=2, tenant_id=str(MVP_TENANT_ID))
        await handler.handle_chunk_indexed(event)

        l3 = resolve("l3_vector")
        for chunk_id, expected_start, expected_end in zip(chunk_ids, (7, 9), (8, 9), strict=True):
            point = await l3.get_point("documents", chunk_id)
            assert point is not None, f"handler 通道点缺失: {chunk_id}"
            payload = point["payload"]
            business_keys = {
                "chunk_id",
                "document_id",
                "parent_chunk_id",
                "index_level",
                "content",
                "chunk_header",
                "page_start",
                "page_end",
            }
            assert business_keys <= set(payload.keys()), f"扩键后 payload 应含 8 业务键: {sorted(payload.keys())}"
            assert payload["page_start"] == expected_start, f"page_start 读回值级: {payload['page_start']}"
            assert payload["page_end"] == expected_end, f"page_end 读回值级: {payload['page_end']}"
            assert payload["chunk_id"] == chunk_id
            assert "created_at" in payload, "infra upsert 追加 created_at（实存第 9 键——存在性断言不计数 DR1-3）"
        # 清理：共享 collection 定向点删（禁整删——DR2-3）+ PG 行定向 DELETE
        await l3.delete_points("documents", chunk_ids)
        assert await l3.get_point("documents", chunk_ids[0]) is None, "定向点删后 get_point 返 None（清理闭环）"
    finally:
        await _cleanup_plan_and_documents([plan_id], [document_id])
