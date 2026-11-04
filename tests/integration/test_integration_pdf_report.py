"""Story 6-5b — PDF 报告生成真实链集成测试（四真实服务 + Fake Embedding 豁免）。

五场景（Task 6 钦定）：
- ① 全链生成：八步归档（含 evidence_refs 预置 chunk）→ PDF 生成 → 六段产物
  断言（实体/L4 读回 pypdf 页数/L2 行 report_type=pdf + metadata citations
  七键/outbox 四键/附录 C 值级 cell 序列——display_name 源独立构造期望）
- ② 双格式对照：同 plan_id 先 Markdown 后 PDF——section_count 恒等 + 章节
  标题族 PDF 文本层可寻 + 附录 B 降级行数 == degraded_section_count 联动
  （聚合复用双格式同值——AC-2 第三条承载）
- ③ 引文降级：evidence_refs 喂不存在 chunk_id（真实缺失构造）→
  [溯源不可用：检索点缺失] 条目 + unresolvable_citation_count==M + 报告
  成功 + section_count 恒 11
- ④ 490 全缺：从未归档的独立 plan_id → code/message/context + 零 L2 行零
  L4 对象零事件
- ⑤ 导航结构与渲染质量：outline 层级（display_name 源期望）/目录 link 注释
  （/Annots /Link /Dest 数组）/引文锚点附录 C 页独占/pypdfium2 每页非空白/
  metadata Title

性能采样（Task 6.4）：单一数据源 plan × 20 次（每轮新 report_id + L2 行
累计 20 + **L4 对象数 20**——键锚 report_id 天然互异）+ P95<60s（epics
L2289 钦定上限——**勿照抄 6-5a 源码 30.0**，那是 6-5a epics 口径）+
asyncio.gather 三 plan 并发（对象键互异集合 + plan↔report 一一对应值级）。
OD-8 口径差声明：生成窗口 P95 = 聚合起点→事件发布返回，不含归档构造前置。

净增 0（Task 6.5）：报告行/outbox 行/L4 对象/引文预置四面跑前跑后对照全零
（归档三面属测试自构造预置——归并引文预置面口径；Redis 快照键族归 6-5a
链对照面——本 Story PDF 链不写 Redis）。

装配（6-5a 集成先例 + 引文预置扩展）：真实 PG/Qdrant/MinIO/Redis + Fake
Embedding（1024 维）；PDF 服务手动构造（document_repository 会话包装注入
——组合根 _SessionScopedDocumentRepository 同款，document_repository 严格
ContextVar 会话）；引文预置走生产通道 upsert（点 id MD5 归一一致——验收
实施攻坚实证）；真实提交 + 定向 DELETE/bypass 清理。

async 测试函数裸 async def（asyncio_mode=auto——探测直 await 禁
run_until_complete——6-4 教训）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_pdf_report.py -v
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

from src.application.ports.chain_of_thought_archive import StepChainMaterial
from src.application.services.chain_of_thought_archive_service import ChainOfThoughtArchiveService

pytestmark = [
    pytest.mark.integration,
    pytest.mark.database,
    pytest.mark.redis,
    pytest.mark.qdrant,
    pytest.mark.minio,
    pytest.mark.xdist_group("blm-planning-perf"),
]

#: 8 步 stage 执行序（独立构造——期望常量禁经被测服务生成）
EXPECTED_STAGE_ORDER: tuple[str, ...] = (
    "performance_gap",
    "market_insight_trend",
    "market_insight_market_customer",
    "market_insight_competition",
    "market_insight_self",
    "market_insight_opportunity",
    "market_insight_opportunity_gap",
    "market_insight_synthesis",
)

_BLM_TASK = "制定新能源汽车行业战略规划（PDF 报告集成真实链）"

#: 性能采样轮数（OD-8：N 与成功率口径同源）
_PERF_ROUNDS = 20

#: P95 上限秒（AC-7 口径 = epics L2289 钦定 60s——6-5b 专属，勿照抄 6-5a 的 30.0）
_P95_LIMIT_SECONDS = 60.0

#: 引文链测试租户（服务构造注入 + 预置 PG 行同值闭环——OD-6）
_CITATION_TENANT_ID = "integration-pdf-citation-tenant"

#: 引文预置 collection（生产默认名——R4T-2 复用既有测试 collection 裁定）
_CITATION_COLLECTION = "documents"

#: 附录 C 冻结标题
_APPENDIX_C_TITLE = "附录 C 引文索引"

#: L4 桶类型常量镜像（断言期望独立字面——双源漂移即红）
_EVIDENCE_BUCKET_TYPE = "archive-evidence"


@pytest.fixture(autouse=True)
def _fresh_resolver_per_test() -> Any:
    """每测试驱逐 resolver 缓存（SINGLETON/SCOPED——跨 loop 防线，6-5a 同款）。"""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()
    yield resolver
    resolver.clear_singleton()
    resolver.clear_scoped()


def _make_material(stage: str, *, index: int = 0, evidence_refs: tuple[str, ...] | None = None) -> StepChainMaterial:
    """构造步骤素材（stage 判型——6-5a 集成版 + evidence_refs 显式覆写位）。"""
    is_synthesis = stage == "market_insight_synthesis"
    is_gap = stage == "performance_gap"
    payload: dict[str, Any]
    if is_synthesis:
        payload = {"conclusions": ["综合结论一（聚焦核心市场）"], "degraded_inputs": []}
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
    if evidence_refs is None:
        evidence_refs = () if is_synthesis else (f"chunk-{index}-001", f"chunk-{index}-002")
    return StepChainMaterial(
        stage=stage,
        display_name="市场洞察综合" if is_synthesis else ("业绩差距分析" if is_gap else "看趋势"),
        role_prefix="CMO" if is_synthesis else ("CFO" if is_gap else "CEO"),
        task=_BLM_TASK,
        evidence_count=0 if is_synthesis else 5,
        tool_slug="" if is_synthesis else "PESTEL 分析",
        evidence_refs=evidence_refs,
        summary="" if is_synthesis else f"步骤摘要（{stage}）",
        findings_count=2,
        degraded=False,
        payload=payload,
        structured_ok=True,
    )


def _make_fake_embedding() -> Any:
    """Fake Embedding 工厂（外部 SaaS 豁免——6-4/6-5a 集成同款）。"""
    from unittest.mock import AsyncMock

    from src.domain.ports.embedding_service import EmbeddingServicePort

    fake = AsyncMock(spec=EmbeddingServicePort)
    fake.embed_query = AsyncMock(return_value=[0.1] * 1024)
    fake.embed_documents = AsyncMock(return_value=[[0.1] * 1024])
    fake.close = AsyncMock()
    return fake


def _make_archive_service() -> ChainOfThoughtArchiveService:
    """手工构造组装归档服务（真实 L2/L3/L4 + Fake Embedding——数据面构造通道）。"""
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.domain.ports.resolver import resolve

    archive_service = StrategicArchiveService(
        archive_repo=resolve("archive_repository"),
        embedding_service=_make_fake_embedding(),
        vector_storage=resolve("l3_vector"),
        object_storage=resolve("l4_object"),
        graph_storage=None,
        event_publisher=None,
        staleness_service=None,
    )
    return ChainOfThoughtArchiveService(
        archive_service=archive_service,
        object_storage=resolve("l4_object"),
    )


def _make_pdf_report_service(chain_service: ChainOfThoughtArchiveService) -> Any:
    """手工构造 PDF 报告服务（真实九依赖 + document_repository 会话包装——组合根同款）。"""
    from typing import cast

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.application.services.pdf_report_generation_service import PdfReportGenerationService
    from src.domain.ports.document_repository import DocumentRepositoryPort
    from src.domain.ports.resolver import resolve
    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
    from src.infrastructure.storage.postgresql.session_context import session_context
    from tests.environments import get_test_env

    class _SessionScopedFind:
        """find 会话包装（组合根 _SessionScopedDocumentRepository 同款镜像）。"""

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
    return PdfReportGenerationService(
        chain_archive_service=chain_service,
        snapshot_repository=resolve("snapshot_repository"),
        report_repository=resolve("report_repository"),
        event_publisher=resolve("event_publisher"),
        pdf_renderer=resolve("pdf_renderer"),
        l4_object=resolve("l4_object"),
        l3_vector=resolve("l3_vector"),
        # cast 契约面收窄（组合根同款注记——包装仅承载 find 会话语境）
        document_repository=cast(
            DocumentRepositoryPort,
            _SessionScopedFind(resolve("document_repository"), async_sessionmaker(manager.get_async_engine())),
        ),
        archive_service=resolve("strategic_archive_service"),
        collection=_CITATION_COLLECTION,
        tenant_id=_CITATION_TENANT_ID,
    )


def _make_markdown_report_service(tmp_path: Path) -> Any:
    """Markdown 对照服务（6-5a 五依赖 + tmp_path L0——场景②双格式对照用）。"""
    from src.application.services.report_generation_service import ReportGenerationService
    from src.domain.ports.resolver import resolve
    from src.infrastructure.config.memory import MemoryConfig
    from src.infrastructure.storage.fs.file_memory_adapter import FileMemoryAdapter

    return ReportGenerationService(
        chain_archive_service=resolve("chain_of_thought_archive_service"),
        snapshot_repository=resolve("snapshot_repository"),
        l0_storage=FileMemoryAdapter(MemoryConfig(memory_l0_path=str(tmp_path))),
        report_repository=resolve("report_repository"),
        event_publisher=resolve("event_publisher"),
    )


async def _probe_services() -> None:
    """四真实服务门控探测（不可达动态 skip——直 await 禁 run_until_complete）。"""
    import sqlalchemy as sa

    from src.domain.ports.resolver import resolve
    from tests.environments import get_test_env

    env = get_test_env()

    async def _probe_pg() -> None:
        from src.infrastructure.config.postgresql import PostgreSQLConfig
        from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

        manager = PostgreSQLManager(
            PostgreSQLConfig(
                host=env.postgres.host,
                port=env.postgres.port,
                database=env.postgres.database,
                username=env.postgres.username,
                password=env.postgres.password,
            )
        )
        engine = manager.get_async_engine()
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT archive_id FROM strategic_archives LIMIT 1"))
            await conn.execute(sa.text("SELECT event_id FROM event_outbox LIMIT 1"))
            await conn.execute(sa.text("SELECT report_id FROM strategic_reports LIMIT 1"))
            await conn.execute(sa.text("SELECT id FROM documents LIMIT 1"))
        await engine.dispose()

    try:
        await _probe_pg()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 不可达: {exc}")

    async def _probe_qdrant() -> None:
        from qdrant_client import AsyncQdrantClient, models

        client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
        try:
            existing = {collection.name for collection in (await client.get_collections()).collections}
            for name in ("strategic_archive", _CITATION_COLLECTION):
                if name not in existing:
                    await client.create_collection(
                        collection_name=name,
                        vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
                    )
        finally:
            await client.close()

    try:
        await _probe_qdrant()
    except Exception as exc:
        pytest.skip(f"Qdrant 不可用: {exc}")

    def _probe_minio() -> None:
        from minio import Minio

        bucket_name = resolve("l4_object")._repository._resolve_bucket_name(_EVIDENCE_BUCKET_TYPE)
        client = Minio(
            endpoint=env.minio.endpoint,
            access_key=env.minio.access_key,
            secret_key=env.minio.secret_key,
            secure=env.minio.secure,
        )
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name, object_lock=True)

    try:
        await asyncio.to_thread(_probe_minio)
    except Exception as exc:
        pytest.skip(f"MinIO 不可用: {exc}")

    async def _probe_redis() -> None:
        import redis.asyncio as aioredis

        client = aioredis.Redis(host=env.redis.host, port=env.redis.port, decode_responses=False)
        try:
            await client.ping()
        finally:
            await client.close()

    try:
        await _probe_redis()
    except Exception as exc:
        pytest.skip(f"Redis 不可用: {exc}")


def _make_session_factory() -> Any:
    """构造独立会话工厂（归档构造/清理共用）。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

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
    return async_sessionmaker(manager.get_async_engine())


async def _archive_steps(
    service: ChainOfThoughtArchiveService,
    plan_id: str,
    refs_factory: Any = None,
) -> list[Any]:
    """逐 stage 组装归档（refs_factory 覆写 evidence_refs——session_context 独立会话承载）。"""
    from src.infrastructure.storage.postgresql.session_context import session_context

    factory = _make_session_factory()
    records = []
    async with session_context(factory):
        for index, stage in enumerate(EXPECTED_STAGE_ORDER):
            refs = refs_factory(stage, index) if refs_factory is not None else None
            record = await service.compose_and_archive_step_chain(
                uuid.UUID(plan_id), stage, _make_material(stage, index=index, evidence_refs=refs)
            )
            records.append(record)
    return records


async def _preset_citation_fixture(count: int) -> list[dict[str, Any]]:
    """引文预置（Qdrant 点生产通道 upsert + PG documents 行——同租户闭环）。"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.domain.ports.resolver import resolve

    presets: list[dict[str, Any]] = []
    for i in range(count):
        presets.append(
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": uuid.uuid4(),
                "filename": f"战略研判参考报告-集成-{i + 1:02d}.pdf",
                "page": 12 + i,
            }
        )
    l3 = resolve("l3_vector")
    await l3.upsert_points(
        _CITATION_COLLECTION,
        [
            {
                "id": preset["chunk_id"],
                "vector": [0.1] * 1024,
                "payload": {
                    "chunk_id": preset["chunk_id"],
                    "document_id": str(preset["document_id"]),
                    "chunk_header": f"参考报告章节标题-{preset['filename']}",
                    "content": "行业趋势与竞争格局研判要点",
                    "index_level": "child",
                    "parent_chunk_id": None,
                },
            }
            for preset in presets
        ],
    )
    manager_factory = _make_session_factory()
    async with AsyncSession(manager_factory.kw["bind"]) as session:
        for preset in presets:
            chunks_meta = [
                {
                    "chunk_id": preset["chunk_id"],
                    "page_start": preset["page"],
                    "page_end": preset["page"],
                    "chunk_header": f"参考报告章节标题-{preset['filename']}",
                }
            ]
            await session.execute(
                text(
                    "INSERT INTO documents (id, tenant_id, filename, mime_type, file_size_bytes, "
                    "document_type, parse_status, uploaded_by, version, metadata, created_at, updated_at) "
                    "VALUES (CAST(:id AS uuid), :tenant, :filename, 'application/pdf', 1024, "
                    "'other', 'completed', 'integration', 1, CAST(:meta AS jsonb), now(), now())"
                ),
                {
                    "id": str(preset["document_id"]),
                    "tenant": _CITATION_TENANT_ID,
                    "filename": preset["filename"],
                    "meta": json.dumps({"chunks": chunks_meta}, ensure_ascii=False),
                },
            )
        await session.commit()
    return presets


# ======================================================================
# PDF 读回与结构断言辅助（pypdf——R3 实证口径；与验收文件同源形态）
# ======================================================================


async def _retrieve_pdf_bytes(object_key: str) -> bytes:
    """L4 对象流式读回收 bytes（AC-1 读回口径——OD-8）。"""
    from src.domain.ports.resolver import resolve

    l4 = resolve("l4_object")
    chunks: list[bytes] = []
    async for chunk in l4.retrieve(_EVIDENCE_BUCKET_TYPE, object_key):
        chunks.append(chunk)
    return b"".join(chunks)


def _pdf_reader(pdf_bytes: bytes) -> Any:
    """pypdf PdfReader 构造。"""
    import io

    from pypdf import PdfReader

    return PdfReader(io.BytesIO(pdf_bytes))


def _pdf_full_text(reader: Any) -> str:
    """全页 extract_text 拼接（STSong-Light 中文完美工作——R3 实证）。"""
    return "\n".join(page.extract_text() for page in reader.pages)


def _flatten_outline(reader: Any) -> list[tuple[int, str]]:
    """outline 展平为 (层级, 标题) 序列。"""

    def walk(items: list[Any], depth: int) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        for item in items:
            if isinstance(item, list):
                out.extend(walk(item, depth + 1))
            else:
                out.append((depth, str(item.title)))
        return out

    return walk(list(reader.outline), 0)


def _pdf_link_targets(reader: Any) -> list[tuple[int, int]]:
    """全文档 link 注释收集为 (注释页, 目标页) 序列（/Dest 数组首元素 idnum 对比）。"""
    from pypdf.generic import IndirectObject

    links: list[tuple[int, int]] = []
    for page_index, page in enumerate(reader.pages):
        annots = page.get("/Annots")
        if not annots:
            continue
        for annot_ref in annots.get_object():
            annot = annot_ref.get_object()
            if annot.get("/Subtype") != "/Link":
                continue
            dest = annot.get("/Dest")
            if dest is None:
                continue
            target = dest.get_object() if hasattr(dest, "get_object") else dest
            first = target[0]
            if not isinstance(first, IndirectObject):
                continue
            for target_index, candidate in enumerate(reader.pages):
                cand_ref = candidate.indirect_reference
                if cand_ref is not None and cand_ref.idnum == first.idnum:
                    links.append((page_index, target_index))
                    break
    return links


# ======================================================================
# 计数/查询/清理辅助（6-5a 形态移植 + L4 对象/引文预置扩展）
# ======================================================================


async def _count_report_rows(plan_id: str) -> int:
    """按 plan_id 计数 strategic_reports 行。"""
    import sqlalchemy as sa

    factory = _make_session_factory()
    async with factory() as session:
        result = await session.execute(
            sa.text("SELECT COUNT(*) FROM strategic_reports WHERE plan_id = CAST(:p AS uuid)"), {"p": plan_id}
        )
        return int(result.scalar_one())


async def _count_outbox_report_rows(plan_id: str) -> int:
    """按 plan_id 计数 outbox ReportGenerated 行。"""
    import sqlalchemy as sa

    factory = _make_session_factory()
    async with factory() as session:
        result = await session.execute(
            sa.text(
                "SELECT COUNT(*) FROM event_outbox WHERE event_type = 'ReportGenerated' "
                "AND (payload->'metadata'->>'plan_id' = :p OR payload->'payload'->>'report_id' IN "
                "(SELECT report_id::text FROM strategic_reports WHERE plan_id = CAST(:p AS uuid)))"
            ),
            {"p": plan_id},
        )
        return int(result.scalar_one())


async def _query_report_metadata(report_id: str) -> dict[str, Any]:
    """直查 L2 metadata JSONB。"""
    import sqlalchemy as sa

    factory = _make_session_factory()
    async with factory() as session:
        result = await session.execute(
            sa.text("SELECT metadata FROM strategic_reports WHERE report_id = CAST(:r AS uuid)"),
            {"r": report_id},
        )
        row = result.scalar_one_or_none()
        return dict(row) if row else {}


async def _query_outbox_four_keys(report_id: str) -> list[Any]:
    """查询 ReportGenerated outbox 行四键。"""
    import sqlalchemy as sa

    factory = _make_session_factory()
    async with factory() as session:
        result = await session.execute(
            sa.text(
                "SELECT payload->'payload'->>'report_id', payload->'payload'->>'report_type', "
                "payload->'payload'->>'file_path' FROM event_outbox "
                "WHERE payload->'payload'->>'report_id' = :rid AND event_type = 'ReportGenerated'"
            ),
            {"rid": report_id},
        )
        return list(result.fetchall())


def _count_pdf_objects_sync(plan_id: str) -> int:
    """按 plan_id 前缀计数 L4 PDF 对象（MinIO list——同步经 to_thread 调用）。"""
    from minio import Minio

    from src.domain.ports.resolver import resolve
    from tests.environments import get_test_env

    env = get_test_env()
    client = Minio(
        endpoint=env.minio.endpoint,
        access_key=env.minio.access_key,
        secret_key=env.minio.secret_key,
        secure=env.minio.secure,
    )
    return sum(
        1
        for _ in client.list_objects(
            resolve("l4_object")._repository._resolve_bucket_name(_EVIDENCE_BUCKET_TYPE),
            prefix=f"reports/{plan_id}/",
            recursive=True,
        )
    )


async def _count_pdf_objects(plan_id: str) -> int:
    """L4 对象计数（to_thread 包装）。"""
    return await asyncio.to_thread(_count_pdf_objects_sync, plan_id)


async def _cleanup_pdf_objects(plan_id: str) -> None:
    """L4 PDF 对象 bypass 定向删（reports/{plan_id}/ 前缀——对象键锚 report_id）。"""
    from minio import Minio
    from minio.deleteobjects import DeleteObject

    from src.domain.ports.resolver import resolve
    from tests.environments import get_test_env

    env = get_test_env()

    def _remove() -> None:
        client = Minio(
            endpoint=env.minio.endpoint,
            access_key=env.minio.access_key,
            secret_key=env.minio.secret_key,
            secure=env.minio.secure,
        )
        bucket = resolve("l4_object")._repository._resolve_bucket_name(_EVIDENCE_BUCKET_TYPE)
        keys = [obj.object_name for obj in client.list_objects(bucket, prefix=f"reports/{plan_id}/", recursive=True)]
        if keys:
            _ = list(client.remove_objects(bucket, [DeleteObject(k) for k in keys], bypass_governance_mode=True))

    await asyncio.to_thread(_remove)


async def _count_citation_documents(presets: list[dict[str, Any]]) -> int:
    """引文预置 documents 行残留计数（CR1-F12——净增 0 对照第四面）。"""
    from sqlalchemy import text

    factory = _make_session_factory()
    async with factory() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM documents WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": [str(preset["document_id"]) for preset in presets]},
        )
        return int(result.scalar_one())


async def _count_citation_points(presets: list[dict[str, Any]]) -> int:
    """引文预置 Qdrant 点残留计数（payload chunk_id 面——与清理面同过滤形态）。"""
    from qdrant_client import AsyncQdrantClient, models

    from tests.environments import get_test_env

    env = get_test_env()
    chunk_ids = [preset["chunk_id"] for preset in presets]
    client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
    try:
        response = await client.count(
            collection_name=_CITATION_COLLECTION,
            count_filter=models.Filter(must=[models.FieldCondition(key="chunk_id", match=models.MatchAny(any=chunk_ids))]),
            exact=True,
        )
        return int(response.count)
    finally:
        await client.close()


async def _cleanup_citation_presets(presets: list[dict[str, Any]]) -> None:
    """引文预置两面清理（Qdrant payload 面 + PG documents 行）。"""
    from qdrant_client import AsyncQdrantClient, models
    from sqlalchemy import text

    from tests.environments import get_test_env

    env = get_test_env()
    chunk_ids = [preset["chunk_id"] for preset in presets]
    client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
    try:
        await client.delete(
            collection_name=_CITATION_COLLECTION,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=[models.FieldCondition(key="chunk_id", match=models.MatchAny(any=chunk_ids))])
            ),
        )
    finally:
        await client.close()
    factory = _make_session_factory()
    async with factory() as session:
        await session.execute(
            text("DELETE FROM documents WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": [str(preset["document_id"]) for preset in presets]},
        )
        await session.commit()


async def _cleanup_report_residues(plan_id: str) -> None:
    """报告侧定向清理（outbox report 行 + strategic_reports 行——6-5a 同款）。"""
    import sqlalchemy as sa

    factory = _make_session_factory()
    async with factory() as session:
        for statement in (
            "DELETE FROM event_outbox WHERE payload->'payload'->>'report_id' IN "
            "(SELECT report_id::text FROM strategic_reports WHERE plan_id = CAST(:p AS uuid))",
            "DELETE FROM strategic_reports WHERE plan_id = CAST(:p AS uuid)",
        ):
            try:
                await session.execute(sa.text(statement), {"p": plan_id})
            except Exception:
                pass
        await session.commit()


async def _cleanup_archive_residues_by_plan(plan_id: str) -> None:
    """归档三面定向清理（6-5a _cleanup_archive_residues_by_plan 移植）。"""
    import sqlalchemy as sa

    from src.domain.ports.resolver import resolve
    from tests.environments import get_test_env

    env = get_test_env()
    factory = _make_session_factory()
    archive_ids: list[str] = []
    blob_refs: list[str] = []
    async with factory() as session:
        rows = (
            await session.execute(
                sa.text("SELECT archive_id, blob_ref FROM strategic_archives WHERE plan_id = CAST(:p AS uuid)"),
                {"p": plan_id},
            )
        ).fetchall()
    for row in rows:
        archive_ids.append(str(row[0]))
        if row[1]:
            blob_refs.append(str(row[1]))
    try:
        async with factory() as session:
            await session.execute(
                sa.text(
                    "DELETE FROM event_outbox WHERE payload->'payload'->>'plan_id' = :p OR payload->'metadata'->>'plan_id' = :p"
                ),
                {"p": plan_id},
            )
            await session.commit()
    except Exception:
        pass
    if archive_ids:
        try:
            from qdrant_client import AsyncQdrantClient, models

            client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
            try:
                await client.delete(
                    collection_name="strategic_archive",
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[models.FieldCondition(key="archive_id", match=models.MatchAny(any=archive_ids))]
                        )
                    ),
                )
            finally:
                await client.close()
        except Exception:
            pass
        if blob_refs:
            try:
                from minio import Minio
                from minio.deleteobjects import DeleteObject

                def _remove() -> None:
                    bucket_name = resolve("l4_object")._repository._resolve_bucket_name(_EVIDENCE_BUCKET_TYPE)
                    client_minio = Minio(
                        endpoint=env.minio.endpoint,
                        access_key=env.minio.access_key,
                        secret_key=env.minio.secret_key,
                        secure=env.minio.secure,
                    )
                    _ = list(
                        client_minio.remove_objects(
                            bucket_name,
                            [DeleteObject(ref) for ref in blob_refs],
                            bypass_governance_mode=True,
                        )
                    )

                await asyncio.to_thread(_remove)
            except Exception:
                pass
        try:
            async with factory() as session:
                await session.execute(
                    sa.text("DELETE FROM strategic_archives WHERE archive_id = ANY(:ids)"), {"ids": archive_ids}
                )
                await session.commit()
        except Exception:
            pass


async def _cleanup_all(plan_id: str, presets: list[dict[str, Any]] | None = None) -> None:
    """全量清理链（报告侧 + L4 对象 + 归档三面 + 引文预置）。"""
    await _cleanup_report_residues(plan_id)
    await _cleanup_pdf_objects(plan_id)
    await _cleanup_archive_residues_by_plan(plan_id)
    if presets:
        await _cleanup_citation_presets(presets)


# ======================================================================
# 五场景
# ======================================================================


async def test_scenario_one_full_generation_roundtrip() -> None:
    """场景① 全链生成（八步归档含预置引文 → 六段产物断言）。"""
    await _probe_services()
    plan_id = str(uuid.uuid4())
    presets = await _preset_citation_fixture(count=1)
    archive_service = _make_archive_service()
    pdf_service = _make_pdf_report_service(archive_service)
    try:
        chunk_id = presets[0]["chunk_id"]
        records = await _archive_steps(
            archive_service,
            plan_id,
            refs_factory=lambda stage, index: () if stage == "market_insight_synthesis" else (chunk_id,),
        )
        assert len(records) == 8
        report = await pdf_service.generate_pdf_report(uuid.UUID(plan_id))
        # 实体八字段
        from src.domain.entities.strategic_report import ReportType

        assert report.report_type is ReportType.PDF
        assert report.section_count == 11
        assert report.file_path == f"reports/{plan_id}/{report.report_id}.pdf"
        # L4 读回（流式收 bytes + pypdf 页数）
        pdf_bytes = await _retrieve_pdf_bytes(report.file_path)
        assert pdf_bytes.startswith(b"%PDF")
        reader = _pdf_reader(pdf_bytes)
        assert len(reader.pages) >= 1
        # L2 行（report_type=pdf + metadata citations 七键值级）
        metadata = await _query_report_metadata(str(report.report_id))
        assert metadata["citation_count"] == 1
        entry = metadata["citations"][0]
        assert set(entry.keys()) == {"index", "document_id", "chunk_id", "filename", "page", "status", "stage"}
        assert entry["document_id"] == str(presets[0]["document_id"])
        assert entry["filename"] == presets[0]["filename"]
        assert entry["page"] == presets[0]["page"]
        assert entry["status"] == "resolved"
        assert entry["stage"] == "performance_gap"  # 首现步骤（八步全喂同一 chunk）
        # outbox 四键值级
        rows = await _query_outbox_four_keys(str(report.report_id))
        assert len(rows) == 1
        assert rows[0][0] == str(report.report_id)
        assert rows[0][1] == "pdf"
        assert rows[0][2] == report.file_path
        # 附录 C 值级（cell 连续序列——display_name 源独立构造期望）
        full_text = _pdf_full_text(reader)
        citation_block = full_text.rsplit("切片标识", 1)[-1]
        expected_cells = f"1\n{presets[0]['filename']}\np.{presets[0]['page']}\n{presets[0]['chunk_id'][:8]}"
        assert expected_cells in citation_block
    finally:
        await _cleanup_all(plan_id, presets)


async def test_scenario_two_dual_format_consistency(tmp_path: Path) -> None:
    """场景② 双格式对照（同 plan_id 双渲染——section_count 恒等 + 标题族 + 附录 B 联动）。"""
    await _probe_services()
    plan_id = str(uuid.uuid4())
    archive_service = _make_archive_service()
    markdown_service = _make_markdown_report_service(tmp_path)
    pdf_service = _make_pdf_report_service(archive_service)
    try:
        await _archive_steps(archive_service, plan_id)
        markdown_report = await markdown_service.generate_markdown_report(uuid.UUID(plan_id))
        pdf_report = await pdf_service.generate_pdf_report(uuid.UUID(plan_id))
        # section_count 恒等（同聚合同 H3 计数单位——附录 C 两侧均不计入）
        assert pdf_report.section_count == markdown_report.section_count == 11
        # 章节标题族 PDF 文本层可寻（display_name 配置源独立构造期望）
        from src.application.ports.chain_of_thought_archive import SYNTHESIS_DISPLAY_NAME
        from src.application.ports.report_generation import REPORT_TITLE_TEMPLATE
        from src.application.services.blm_planning_prompts import (
            MARKET_INSIGHT_STEP_CONFIG,
            PERFORMANCE_GAP_CONFIG,
        )

        full_text = _pdf_full_text(_pdf_reader(await _retrieve_pdf_bytes(pdf_report.file_path)))
        assert REPORT_TITLE_TEMPLATE in full_text
        step_titles = [cfg.display_name for cfg in MARKET_INSIGHT_STEP_CONFIG.values()]
        for expected in (
            f"1 {PERFORMANCE_GAP_CONFIG.display_name}",
            *[f"2.{i} {name}" for i, name in enumerate(step_titles, start=1)],
            f"2.7 {SYNTHESIS_DISPLAY_NAME}",
            "附录 B 降级与数据缺失记录",
            _APPENDIX_C_TITLE,
        ):
            assert expected in full_text, f"PDF 文本层章节标题缺失: {expected}"
        # 附录 B 降级行数与实体计数联动（聚合复用双格式同值——AC-2 第三条）
        assert pdf_report.degraded_section_count == markdown_report.degraded_section_count == 0
        pdf_metadata = await _query_report_metadata(str(pdf_report.report_id))
        assert pdf_metadata.get("degraded_stages") == []
    finally:
        await _cleanup_all(plan_id)


async def test_scenario_three_citation_degradation() -> None:
    """场景③ 引文降级（真实缺失构造：evidence_refs 喂不存在 chunk_id）。"""
    await _probe_services()
    plan_id = str(uuid.uuid4())
    missing_chunk = str(uuid.uuid4())
    archive_service = _make_archive_service()
    pdf_service = _make_pdf_report_service(archive_service)
    try:
        await _archive_steps(
            archive_service,
            plan_id,
            refs_factory=lambda stage, index: () if stage == "market_insight_synthesis" else (missing_chunk,),
        )
        report = await pdf_service.generate_pdf_report(uuid.UUID(plan_id))
        assert report.report_id is not None  # 降级不阻断（增强面哲学）
        assert report.section_count == 11  # 引文降级不计入 degraded 口径（H3 冻结）
        metadata = await _query_report_metadata(str(report.report_id))
        assert metadata["citation_count"] == 1
        assert metadata["unresolvable_citation_count"] == 1
        assert metadata["citations"][0]["status"] == "point_missing"
        assert metadata["citations"][0]["chunk_id"] == missing_chunk
        full_text = _pdf_full_text(_pdf_reader(await _retrieve_pdf_bytes(report.file_path)))
        citation_block = full_text.rsplit("切片标识", 1)[-1]
        assert f"1\n[溯源不可用：检索点缺失]\n-\n{missing_chunk[:8]}" in citation_block
    finally:
        await _cleanup_all(plan_id)


async def test_scenario_four_total_missing_490() -> None:
    """场景④ 数据源全缺（独立 plan → 490 code/message/context + 零落库零对象零事件）。"""
    await _probe_services()
    plan_id = str(uuid.uuid4())
    archive_service = _make_archive_service()
    pdf_service = _make_pdf_report_service(archive_service)
    from src.domain.exceptions import ReportGenerationError

    try:
        with pytest.raises(ReportGenerationError) as exc_info:
            await pdf_service.generate_pdf_report(uuid.UUID(plan_id))
        assert exc_info.value.code == "EXCEPTION_490"
        assert exc_info.value.message == "该 plan_id 无思维链归档记录，无法生成报告"
        assert exc_info.value.context["plan_id"] == plan_id
        assert await _count_report_rows(plan_id) == 0
        assert await _count_pdf_objects(plan_id) == 0
        assert await _count_outbox_report_rows(plan_id) == 0
    finally:
        await _cleanup_all(plan_id)


async def test_scenario_five_navigation_and_render_quality() -> None:
    """场景⑤ 导航结构与渲染质量（outline/link/引文锚点/pypdfium2 冒烟/metadata）。"""
    await _probe_services()
    plan_id = str(uuid.uuid4())
    presets = await _preset_citation_fixture(count=1)
    archive_service = _make_archive_service()
    pdf_service = _make_pdf_report_service(archive_service)
    try:
        chunk_id = presets[0]["chunk_id"]
        await _archive_steps(
            archive_service,
            plan_id,
            refs_factory=lambda stage, index: () if stage == "market_insight_synthesis" else (chunk_id,),
        )
        report = await pdf_service.generate_pdf_report(uuid.UUID(plan_id))
        reader = _pdf_reader(await _retrieve_pdf_bytes(report.file_path))
        # outline 层级（display_name 配置源独立构造期望）
        from src.application.ports.chain_of_thought_archive import SYNTHESIS_DISPLAY_NAME
        from src.application.ports.report_generation import REPORT_TITLE_TEMPLATE
        from src.application.services.blm_planning_prompts import (
            MARKET_INSIGHT_STEP_CONFIG,
            PERFORMANCE_GAP_CONFIG,
        )

        flat = _flatten_outline(reader)
        step_titles = [cfg.display_name for cfg in MARKET_INSIGHT_STEP_CONFIG.values()]
        expected = [
            (0, REPORT_TITLE_TEMPLATE),
            (1, f"1 {PERFORMANCE_GAP_CONFIG.display_name}"),
            (2, "1.1 财务差距"),
            (2, "1.2 运营差距"),
            (2, "1.3 根因分析"),
            (2, "1.4 业务组合健康度"),
            (1, "2 市场洞察"),
            *[(2, f"2.{i} {name}") for i, name in enumerate(step_titles, start=1)],
            (2, f"2.7 {SYNTHESIS_DISPLAY_NAME}"),
            (1, "附录 B 降级与数据缺失记录"),
            (1, _APPENDIX_C_TITLE),
        ]
        assert flat == expected, f"outline 层级漂移: {flat}"
        # 目录 link 注释（/Annots /Link + /Dest 数组目标页有效——条目数==收录面 4）
        links = _pdf_link_targets(reader)
        page_texts = [page.extract_text() for page in reader.pages]
        toc_pages = {page for page, _ in links if "目录" in page_texts[page]}
        assert toc_pages
        toc_links = [(page, target) for page, target in links if page in toc_pages]
        assert len(toc_links) == 4  # 两章 + 附录 B + 附录 C（无快照无附录 A）
        for _, target in links:
            assert 0 <= target < len(reader.pages)
        # 引文锚点附录 C 页独占（非目录页 link 全部自指附录 C——1 条引文）
        non_toc_links = [(page, target) for page, target in links if page not in toc_pages]
        assert len(non_toc_links) == 1
        for page, target in non_toc_links:
            assert target == page
            assert _APPENDIX_C_TITLE in page_texts[page]
        # pypdfium2 渲染冒烟（每页非空白——AC-8 视觉面；变量名 pdf_page 与上文
        # 页索引 page 分立；getdata 全量灰度——6-5a 验收先例形态）
        import pypdfium2 as pdfium

        pdf_doc = pdfium.PdfDocument(await _retrieve_pdf_bytes(report.file_path))
        for pdf_page in pdf_doc:
            grayscale_values = list(pdf_page.render().to_pil().convert("L").getdata())
            non_white = sum(1 for value in grayscale_values if value < 250)
            assert non_white > 0, "页面光栅化后纯白"
        # metadata（Title 中文值 + Producer 非空）
        assert reader.metadata is not None
        assert reader.metadata.title == REPORT_TITLE_TEMPLATE
        assert reader.metadata.producer
    finally:
        await _cleanup_all(plan_id, presets)


# ======================================================================
# 性能采样 + 并发 + 净增 0（Task 6.4/6.5）
# ======================================================================


async def test_performance_sampling_and_concurrency() -> None:
    """性能采样（20 轮 P95<60s + L4 对象 20）+ 并发 3 互不串扰 + 净增 0。

    OD-8 口径声明：P95 窗口 = 聚合起点→事件发布返回（计时包 generate_pdf_
    report 全程），不含归档构造前置；引文解析批量性能注记（AC-7 第三条）：
    本场景引文量级 1 条（×2 查询）——实测落本 docstring（M>50 超窗口形态归
    deferred-work 6.5b-DF2 条件性登记裁定）。
    """
    await _probe_services()
    plan_id = str(uuid.uuid4())
    presets = await _preset_citation_fixture(count=1)
    archive_service = _make_archive_service()
    pdf_service = _make_pdf_report_service(archive_service)
    concurrent_plans = [str(uuid.uuid4()) for _ in range(3)]
    concurrent_presets = await _preset_citation_fixture(count=1)
    try:
        chunk_id = presets[0]["chunk_id"]
        await _archive_steps(
            archive_service,
            plan_id,
            refs_factory=lambda stage, index: () if stage == "market_insight_synthesis" else (chunk_id,),
        )
        # 净增 0 基线
        baseline_reports = await _count_report_rows(plan_id)
        baseline_objects = await _count_pdf_objects(plan_id)
        baseline_outbox = await _count_outbox_report_rows(plan_id)
        # 20 轮采样
        durations: list[float] = []
        report_ids: list[str] = []
        for _ in range(_PERF_ROUNDS):
            started = time.monotonic()
            report = await pdf_service.generate_pdf_report(uuid.UUID(plan_id))
            durations.append(time.monotonic() - started)
            report_ids.append(str(report.report_id))
        assert len(set(report_ids)) == _PERF_ROUNDS  # 每轮新 report_id（幂等锚）
        assert await _count_report_rows(plan_id) - baseline_reports == _PERF_ROUNDS
        assert await _count_pdf_objects(plan_id) - baseline_objects == _PERF_ROUNDS  # L4 对象 20
        assert await _count_outbox_report_rows(plan_id) - baseline_outbox == _PERF_ROUNDS  # 事件 20（CR1-F12）
        ordered = sorted(durations)
        p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
        assert p95 < _P95_LIMIT_SECONDS, f"P95 实测={p95:.3f}s 期望<{_P95_LIMIT_SECONDS}s"
        # 并发 3（独立 plan 八步归档 + gather 互不串扰值级断言）
        concurrent_chunk = concurrent_presets[0]["chunk_id"]
        for concurrent_plan in concurrent_plans:
            await _archive_steps(
                archive_service,
                concurrent_plan,
                refs_factory=lambda stage, index: () if stage == "market_insight_synthesis" else (concurrent_chunk,),
            )
        concurrent_reports = await asyncio.gather(
            *(pdf_service.generate_pdf_report(uuid.UUID(pid)) for pid in concurrent_plans)
        )
        assert len({str(r.report_id) for r in concurrent_reports}) == 3
        assert len({r.file_path for r in concurrent_reports}) == 3  # 对象键互异集合
        for pid, report in zip(concurrent_plans, concurrent_reports):
            assert report.plan_id == pid  # plan↔report 一一对应
            assert await _count_report_rows(pid) == 1
            assert await _count_outbox_report_rows(pid) == 1  # 每 plan 恰一事件（CR1-F12）
        # 净增 0 对照（清理后全零——报告三元 + 引文预置两面）
        await _cleanup_all(plan_id, presets)
        for concurrent_plan in concurrent_plans:
            await _cleanup_all(concurrent_plan)
        await _cleanup_citation_presets(concurrent_presets)
        assert await _count_report_rows(plan_id) == 0
        assert await _count_outbox_report_rows(plan_id) == 0
        assert await _count_pdf_objects(plan_id) == 0
        for concurrent_plan in concurrent_plans:
            assert await _count_report_rows(concurrent_plan) == 0
            assert await _count_pdf_objects(concurrent_plan) == 0
        # 引文预置两面净增 0（documents 行 + Qdrant 点——CR1-F12 第四面对照）
        for cleaned_presets in (presets, concurrent_presets):
            assert await _count_citation_documents(cleaned_presets) == 0
            assert await _count_citation_points(cleaned_presets) == 0
    finally:
        await _cleanup_all(plan_id, presets)
        for concurrent_plan in concurrent_plans:
            await _cleanup_all(concurrent_plan)
        await _cleanup_citation_presets(concurrent_presets)
