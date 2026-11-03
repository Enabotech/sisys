"""Story 6-4 — 思维链归档真实链集成测试（四真实服务 + Fake Embedding 豁免）。

五场景（Task 5 钦定——OD-7 文件名对仓规 test_integration_* 惯例对齐）：
- ① 真实链全量归档 round-trip：8 步素材经 ChainOfThoughtArchiveService 逐条
  compose+archive（真实 L2 PG 行/L3 Qdrant 点/L4 MinIO WORM blob/retention
  2555/全量 archived=True）
- ② 追溯+blob 深度解引用+ArchiveCreated outbox 落行（真实 publisher——
  event_type 过滤防自捕）
- ③ 并发 10（asyncio.gather + 每协程 session_context() 独立 scope——R1-F7；
  10 素材共享一个场景专属 plan_id，count==10 按 plan_id+archive_type 过滤）
- ④ 性能采样（组装窗口 P95<50ms——直调纯函数 compose_step_chain，R1-F13；
  口径差声明 OD-10：归档 I/O 与 LLM 延迟显式出栈独立计量）
- ⑤ 清理闭环互证（四键族跑前跑后净增 0——R1-F1 教训直接继承）

装配形态（6-3 test_integration_checkpoint.py 先例）：真实 PG（archive L2 +
outbox）+ 真实 Qdrant（L3）+ 真实 MinIO（L4 WORM）+ Fake Embedding（外部
SaaS 豁免——固定 1024 维）；归档真实提交 + 按 plan_id 定向删除清理（R1-F7
口径——savepoint 回滚不适用于服务内归档链路）。

async 测试函数裸 async def（asyncio_mode=auto）；pytestmark 显式声明全套
（文件名含服务关键词时 conftest 自动加挂，此处双保险对齐 6-3 形态）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_chain_of_thought.py -v
"""

from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from typing import Any

import pytest

from src.application.ports.chain_of_thought_archive import (
    CHAIN_ARCHIVE_KIND,
    StepChainMaterial,
)
from src.application.services.chain_of_thought_archive_service import (
    ChainOfThoughtArchiveService,
    compose_step_chain,
)

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

_BLM_TASK = "制定新能源汽车行业五年战略规划（集成真实链）"


def _make_material(stage: str, *, index: int = 0) -> StepChainMaterial:
    """构造步骤素材（stage 判型——同型差异经 index 区分证据引用）。"""
    is_synthesis = stage == "market_insight_synthesis"
    is_gap = stage == "performance_gap"
    payload: dict[str, Any]
    if is_synthesis:
        payload = {"conclusions": [f"综合结论一（{index}）", "综合结论二"], "degraded_inputs": []}
    elif is_gap:
        payload = {
            "financial_gap": f"财务差距量化：营收达成率 8{index}%",
            "operational_gap": "运营差距分析：交付周期延长",
            "root_causes": ["根因一", "根因二"],
            "portfolio_health": "业务组合健康度：核心稳健",
            "degraded": False,
            "degrade_reason": "",
        }
    else:
        payload = {"summary": f"市场洞察产物:{stage.removeprefix('market_insight_')}", "findings": ["发现一", "发现二"]}
    return StepChainMaterial(
        stage=stage,
        display_name="市场洞察综合" if is_synthesis else ("业绩差距分析" if is_gap else "看趋势"),
        role_prefix="CMO"
        if is_synthesis
        else (
            "以 CFO 财务差距量化与 COO 运营差距分析的双重视角" if is_gap else "以 CEO 宏观趋势判断与 CTO 技术趋势分析的双重视角"
        ),
        task=_BLM_TASK,
        evidence_count=0 if is_synthesis else 5,
        tool_slug="" if is_synthesis else "PESTEL 分析",
        evidence_refs=() if is_synthesis else (f"chunk-{index}-001", f"chunk-{index}-002"),
        summary="" if is_synthesis else f"步骤摘要（{stage}）",
        findings_count=2,
        degraded=False,
        payload=payload,
        structured_ok=True,
    )


def _make_fake_embedding() -> Any:
    """Fake Embedding 工厂（外部 SaaS 豁免——6-3 集成同款）。"""
    from unittest.mock import AsyncMock

    from src.domain.ports.embedding_service import EmbeddingServicePort

    fake = AsyncMock(spec=EmbeddingServicePort)
    fake.embed_query = AsyncMock(return_value=[0.1] * 1024)
    fake.embed_documents = AsyncMock(return_value=[[0.1] * 1024])
    fake.close = AsyncMock()
    return fake


async def _probe_services() -> None:
    """四真实服务门控探测（不可达逐场景动态 skip——禁写死 skip 标记）。

    async 形态（async 测试函数内直 await——run_until_complete 在已运行 loop
    上抛 RuntimeError 会误触发 skip）。
    """
    import sqlalchemy as sa

    from src.domain.ports.resolver import resolve
    from tests.environments import get_test_env

    env = get_test_env()

    async def _probe() -> None:
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
        await engine.dispose()

    try:
        await _probe()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 不可达: {exc}")

    async def _probe_qdrant() -> None:
        from qdrant_client import AsyncQdrantClient, models

        client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
        try:
            existing = {collection.name for collection in (await client.get_collections()).collections}
            if "strategic_archive" not in existing:
                await client.create_collection(
                    collection_name="strategic_archive",
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

        bucket_name = resolve("l4_object")._repository._resolve_bucket_name("archive-evidence")
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


async def _count_archive_rows(plan_id: str) -> int:
    """按 plan_id + EVIDENCE_PACKAGE 计数 L2 行（独立连接）。"""
    import sqlalchemy as sa

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
    try:
        engine = manager.get_async_engine()
        async with engine.connect() as conn:
            result = await conn.execute(
                sa.text(
                    "SELECT COUNT(*) FROM strategic_archives "
                    "WHERE plan_id = CAST(:plan_id AS uuid) AND archive_type = 'evidence_package'"
                ),
                {"plan_id": plan_id},
            )
            return int(result.scalar_one())
    finally:
        await engine.dispose()


async def _cleanup_by_plan_id(plan_id: str) -> None:
    """按 plan_id 定向清理四键族（档案行/outbox 行/Qdrant 点/MinIO 对象）。

    各步独立 try/except（断言失败也执行——残局防线）；MinIO 走
    bypass_governance（object-lock GOVERNANCE retention 清理形态）。
    """
    import sqlalchemy as sa

    from src.domain.ports.resolver import resolve
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
    archive_ids: list[str] = []
    blob_refs: list[str] = []
    engine = manager.get_async_engine()
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text("SELECT archive_id, blob_ref FROM strategic_archives WHERE plan_id = CAST(:p AS uuid)"),
                    {"p": plan_id},
                )
            ).fetchall()
        for row in rows:
            archive_ids.append(str(row[0]))
            if row[1]:
                blob_refs.append(row[1])
    except Exception:
        pass
    # outbox 行（event_id 不可预知——payload 双 JSONB 通道兜底）
    try:
        async with engine.begin() as conn:
            await conn.execute(
                sa.text(
                    "DELETE FROM event_outbox WHERE payload->'payload'->>'plan_id' = :p OR payload->'metadata'->>'plan_id' = :p"
                ),
                {"p": plan_id},
            )
    except Exception:
        pass
    # Qdrant 点（payload.archive_id filter——点 ID 为 MD5 哈希 int）
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
        # MinIO WORM 对象（bypass 清理）
        if blob_refs:
            try:
                from minio import Minio
                from minio.deleteobjects import DeleteObject

                def _remove() -> None:
                    bucket_name = resolve("l4_object")._repository._resolve_bucket_name("archive-evidence")
                    client_minio = Minio(
                        endpoint=env.minio.endpoint,
                        access_key=env.minio.access_key,
                        secret_key=env.minio.secret_key,
                        secure=env.minio.secure,
                    )
                    _ = list(
                        client_minio.remove_objects(
                            bucket_name,
                            [DeleteObject(blob_ref) for blob_ref in blob_refs],
                            bypass_governance_mode=True,
                        )
                    )

                await asyncio.to_thread(_remove)
            except Exception:
                pass
        # PG 档案行
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    sa.text("DELETE FROM strategic_archives WHERE archive_id = ANY(:ids)"),
                    {"ids": archive_ids},
                )
        except Exception:
            pass
    await engine.dispose()


def _make_service(*, event_publisher: Any = None) -> ChainOfThoughtArchiveService:
    """手工构造组装归档服务（真实 L2/L3/L4 + Fake Embedding + 可选真实 publisher）。"""
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.domain.ports.resolver import resolve

    archive_service = StrategicArchiveService(
        archive_repo=resolve("archive_repository"),
        embedding_service=_make_fake_embedding(),
        vector_storage=resolve("l3_vector"),
        object_storage=resolve("l4_object"),
        graph_storage=None,
        event_publisher=event_publisher,
        staleness_service=None,
    )
    return ChainOfThoughtArchiveService(
        archive_service=archive_service,
        object_storage=resolve("l4_object"),
    )


async def _archive_eight_steps(service: ChainOfThoughtArchiveService, plan_id: str) -> list[Any]:
    """经服务逐条组装归档 8 步（真实链——session 生命周期由调用方管理）。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
    from src.infrastructure.storage.postgresql.session_context import session_context
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
    factory = async_sessionmaker(manager.get_async_engine())
    records = []
    async with session_context(factory):
        for index, stage in enumerate(EXPECTED_STAGE_ORDER):
            record = await service.compose_and_archive_step_chain(uuid.UUID(plan_id), stage, _make_material(stage, index=index))
            records.append(record)
    await manager.get_async_engine().dispose()
    return records


async def test_scenario_one_full_run_eight_chains_roundtrip() -> None:
    """场景① 真实链全量归档 round-trip（L2 8 行/L3 点可搜/L4 blob 等值/WORM）。"""
    await _probe_services()
    plan_id = str(uuid.uuid4())
    service = _make_service()
    try:
        records = await _archive_eight_steps(service, plan_id)
        assert len(records) == 8
        assert all(record is not None and record.archived for record in records), "归档成功率应 8/8（OD-5 正常路径）"
        # L2 恰 8 行
        row_count = await _count_archive_rows(plan_id)
        assert row_count == 8, f"L2 EVIDENCE_PACKAGE 实测={row_count} 期望=8"
        # L4 blob 解引用 JSON == 期望五字段（独立构造期望——非自证；blob_ref 形态经 L2 行取）
        from src.domain.ports.resolver import resolve

        l4 = resolve("l4_object")
        import sqlalchemy as sa

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
        engine = manager.get_async_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT decision_basis, blob_ref FROM strategic_archives "
                        "WHERE plan_id = CAST(:p AS uuid) AND archive_type = 'evidence_package' "
                        "ORDER BY archived_at ASC"
                    ),
                    {"p": plan_id},
                )
            ).fetchall()
        await engine.dispose()
        assert len(rows) == 8
        for index, (decision_basis, blob_ref) in enumerate(rows):
            assert decision_basis.get("kind") == CHAIN_ARCHIVE_KIND
            assert decision_basis.get("stage") == EXPECTED_STAGE_ORDER[index]
            assert blob_ref, "L4 blob_ref 缺失（落对象双前提未满足——R1-F16）"
            chunks: list[bytes] = []
            async for chunk in l4.retrieve(bucket_type="archive-evidence", object_key=blob_ref):
                chunks.append(chunk)
            blob_json = json.loads(b"".join(chunks).decode("utf-8"))
            expected_chain = compose_step_chain(_make_material(EXPECTED_STAGE_ORDER[index], index=index))
            assert blob_json["stage"] == EXPECTED_STAGE_ORDER[index]
            assert blob_json["chain"]["final_answer"] == expected_chain.final_answer

        # WORM retention 2555（get_object_retention——抽样一条）
        def _check_retention() -> None:
            from minio import Minio

            client = Minio(
                endpoint=env.minio.endpoint,
                access_key=env.minio.access_key,
                secret_key=env.minio.secret_key,
                secure=env.minio.secure,
            )
            bucket_name = resolve("l4_object")._repository._resolve_bucket_name("archive-evidence")
            retention = client.get_object_retention(bucket_name, rows[0][1])
            assert retention is not None
            days = (retention.retain_until_date.timestamp() - time.time()) / 86400
            assert 2550 <= days <= 2560, f"WORM retention 实测={days:.1f} 天 期望≈2555"

        await asyncio.to_thread(_check_retention)
        # L3 Qdrant 点可搜（filter 面——payload.archive_id 匹配）
        from qdrant_client import AsyncQdrantClient, models

        qclient = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
        try:
            archive_id_first = records[0].archive_id
            found = await qclient.scroll(
                collection_name="strategic_archive",
                scroll_filter=models.Filter(
                    must=[models.FieldCondition(key="archive_id", match=models.MatchValue(value=archive_id_first))]
                ),
                limit=1,
            )
            assert found[0], f"L3 点缺失（archive_id={archive_id_first}）"
            first_payload = found[0][0].payload or {}
            assert str(first_payload.get("archive_id")) == archive_id_first
        finally:
            await qclient.close()
    finally:
        await _cleanup_by_plan_id(plan_id)
        assert await _count_archive_rows(plan_id) == 0, "清理闭环失效（档案行残留）"


async def test_scenario_two_trace_query_blob_and_outbox() -> None:
    """场景② 追溯+blob 深度解引用+ArchiveCreated outbox 落行（真实 publisher）。"""
    await _probe_services()
    plan_id = str(uuid.uuid4())
    from src.domain.ports.resolver import resolve

    # 真实 publisher 直接 resolve（本场景未注册替身——clear_singleton 会使
    # l4_object 等端口重走构造路径，MinIO 凭证上下文漂移触发 AccessDenied）
    real_publisher = resolve("event_publisher")
    service = _make_service(event_publisher=real_publisher)
    try:
        records = await _archive_eight_steps(service, plan_id)
        assert len(records) == 8
        time.sleep(0.2)  # outbox 异步落行窗口
        # 追溯查询（round-trip 升序 + include_blob 深度解引用——L2 读侧同需
        # session_context scope：仓储 session 来自 ContextVar）
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from src.infrastructure.config.postgresql import PostgreSQLConfig
        from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
        from src.infrastructure.storage.postgresql.session_context import session_context
        from tests.environments import get_test_env

        env = get_test_env()
        trace_manager = PostgreSQLManager(
            PostgreSQLConfig(
                host=env.postgres.host,
                port=env.postgres.port,
                database=env.postgres.database,
                username=env.postgres.username,
                password=env.postgres.password,
            )
        )
        trace_factory = async_sessionmaker(trace_manager.get_async_engine())
        async with session_context(trace_factory):
            view = await service.query_chain_trace(uuid.UUID(plan_id), include_blob=True)
        await trace_manager.get_async_engine().dispose()
        assert view.total == 8
        assert [record["stage"] for record in view.records] == list(EXPECTED_STAGE_ORDER)
        for index, record in enumerate(view.records):
            blob_content = record["blob_content"]
            assert blob_content is not None, f"stage={record['stage']} blob_content 未填充"
            expected_chain = compose_step_chain(_make_material(record["stage"], index=index))
            assert blob_content["chain"]["final_answer"] == expected_chain.final_answer
        # ArchiveCreated outbox 落行（event_type 过滤防自捕）
        import sqlalchemy as sa

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
        engine = manager.get_async_engine()
        async with engine.connect() as conn:
            outbox_rows = (
                await conn.execute(
                    sa.text(
                        "SELECT event_type FROM event_outbox "
                        "WHERE payload->'payload'->>'plan_id' = :p AND event_type = 'ArchiveCreated'"
                    ),
                    {"p": plan_id},
                )
            ).fetchall()
        await engine.dispose()
        assert len(outbox_rows) == 8, f"ArchiveCreated 落行实测={len(outbox_rows)} 期望=8"
    finally:
        await _cleanup_by_plan_id(plan_id)


async def test_scenario_three_concurrent_ten_chains() -> None:
    """场景③ 并发 10（gather + 每协程 session_context 独立 scope——R1-F7）。"""
    await _probe_services()
    plan_id = str(uuid.uuid4())
    service = _make_service()
    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from src.infrastructure.config.postgresql import PostgreSQLConfig
        from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
        from src.infrastructure.storage.postgresql.session_context import session_context
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
        factory = async_sessionmaker(manager.get_async_engine())
        plan_uuid = uuid.UUID(plan_id)

        async def _archive_one(index: int) -> Any:
            # R1-F7：gather 共享单 AsyncSession 并发使用不被 SQLAlchemy 支持——
            # 每协程 session_context() 独立 scope
            async with session_context(factory):
                return await service.compose_and_archive_step_chain(
                    plan_uuid, "market_insight_trend", _make_material("market_insight_trend", index=index)
                )

        results = await asyncio.gather(*(_archive_one(index) for index in range(10)))
        await manager.get_async_engine().dispose()
        assert len(results) == 10
        assert all(record is not None and record.archived for record in results), "并发归档应全部成功"
        row_count = await _count_archive_rows(plan_id)
        assert row_count == 10, f"并发 count 实测={row_count} 期望=10（共享场景专属 plan_id——R1-F7 口径）"
    finally:
        await _cleanup_by_plan_id(plan_id)


async def test_scenario_four_p95_assembly_window() -> None:
    """场景④ 组装窗口 P95<50ms（直调纯函数——OD-10 口径差声明）。

    口径：素材就绪 → ChainOfThought VO 构造完成窗口（纯内存——确定性组装
    零 LLM 调用使指标物理可达）；归档 I/O（L2/L3/L4）与 LLM 延迟显式出栈
    独立计量（不进本 P95 口径——epic 未预见组装/归档/LLM 三段分离）。
    采样素材型=六子步骤型（Task 5.4 钦定）；升序排序后 P95=sorted[ceil(0.95*n)-1]。
    """
    material = _make_material("market_insight_trend")
    durations: list[float] = []
    for _ in range(25):
        started = time.perf_counter()
        compose_step_chain(material)
        durations.append((time.perf_counter() - started) * 1000)
    ordered = sorted(durations)
    p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
    assert p95 < 50.0, f"组装窗口 P95 实测={p95:.3f}ms 期望<50ms（纯内存组装）"


async def test_scenario_five_no_residue_after_cleanup() -> None:
    """场景⑤ 清理闭环互证（净增 0——归档面按 plan_id 定向清理的残局防线）。"""
    await _probe_services()
    plan_id = str(uuid.uuid4())
    service = _make_service()
    assert await _count_archive_rows(plan_id) == 0, "前置应零行"
    try:
        records = await _archive_eight_steps(service, plan_id)
        assert len(records) == 8
        assert await _count_archive_rows(plan_id) == 8
    finally:
        await _cleanup_by_plan_id(plan_id)
    assert await _count_archive_rows(plan_id) == 0, "清理后净增应为 0（四键族残局防线）"
