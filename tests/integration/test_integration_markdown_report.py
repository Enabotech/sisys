"""Story 6-5a — Markdown 报告生成真实链集成测试（四真实服务 + Fake Embedding 豁免）。

五场景（Task 5 钦定；③b 为③的第二断言块非独立场景——R2 计数澄清）：
- ① 全链生成：八步归档 → 报告生成 → 报告三元断言（L0 读回/L2 行/outbox 行）
  + 章节结构断言（冻结标题族——display_name 源独立构造期望）
- ② 格式化三要素：ATX 标题层级/GFM 表格（PESTEL 六行/五力五行）/列表项数
- ③ 降级语义：逐 stage 七次归档跳过目标六子步（钦定构造——禁删行）→
  [数据缺失] callout + degraded==1；③b 六子缺三步 → degraded==3 ≤
  section_count==11 不变量成立报告成功
- ④ 490 全缺：从未归档的独立 plan_id（天然 total==0）→ 异常码/message
- ⑤ 性能采样 + 并发 + 净增 0：单一数据源 plan_id × 20 次生成（OD-10 幂等锚
  合法采样——**OD-8 口径差声明：生成窗口 P95 = 聚合起点→事件发布返回，
  不含 BLM 归档构造前置**；N=20 数学口径 sorted[ceil(0.95*20)-1]=次大值）+
  asyncio.gather 三 plan_id 并发互不串扰 + 跑前跑后净增 0

装配（6-4 集成先例）：真实 PG（strategic_archives/strategic_reports/event_outbox）
+ 真实 Qdrant + 真实 MinIO + Fake Embedding（外部 SaaS 豁免 1024 维）；报告
服务手动构造注入 tmp_path L0（写路径隔离——R1-17 三理由）；真实提交 + 按
plan_id/report_id 定向 DELETE 清理（savepoint 不适用——服务内含 L2 落库链）。

async 测试函数裸 async def（asyncio_mode=auto——探测直 await 禁 run_until_complete）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_markdown_report.py -v
"""

from __future__ import annotations

import asyncio
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

_BLM_TASK = "制定新能源汽车行业五年战略规划（报告集成真实链）"

#: 性能采样轮数（OD-8：N 与成功率口径同源）
_PERF_ROUNDS = 20

#: P95 上限秒（AC-7 口径——聚合起点→事件发布返回）
_P95_LIMIT_SECONDS = 30.0


@pytest.fixture(autouse=True)
def _fresh_resolver_per_test() -> Any:
    """每测试驱逐 resolver 缓存（SINGLETON/SCOPED——跨 loop 防线）。

    SCOPED/SINGLETON 实例内含 asyncpg 连接池（engine lazy 建池绑首用 loop）；
    pytest-asyncio 每测试函数新 loop——缓存实例跨测试复用必炸 "Future
    attached to a different loop"。每测试前后各清一次（6-1 场景③
    clear_singleton 先例 + clear_scoped 补全），强制本场景实例全新。
    """
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()
    yield resolver
    resolver.clear_singleton()
    resolver.clear_scoped()


def _make_material(stage: str, *, index: int = 0) -> StepChainMaterial:
    """构造步骤素材（stage 判型——6-4 _make_material 形态移植）。"""
    is_synthesis = stage == "market_insight_synthesis"
    is_gap = stage == "performance_gap"
    payload: dict[str, Any]
    if is_synthesis:
        payload = {"conclusions": ["综合结论一（聚焦核心市场）", "综合结论二（补强数据能力）"], "degraded_inputs": []}
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
        if step_key == "trend":
            payload = {
                "summary": "看趋势摘要：宏观政策与技术双轮驱动",
                "findings": ["发现一：政策转向确定性高", "发现二：技术成熟度爬升"],
                "pestel_political": "政策稳定",
                "pestel_economic": "温和增长",
                "pestel_social": "人口结构变化",
                "pestel_technological": "AI 成熟度爬升",
                "pestel_environmental": "双碳约束",
                "pestel_legal": "数据合规强化",
                "technology_roadmap": ["试点验证", "规模推广", "生态整合"],
                "scenario_plans": ["基准情景", "乐观情景"],
            }
        elif step_key == "competition":
            payload = {
                "summary": "看竞争摘要：头部集中度提升",
                "findings": ["发现一：价格战加剧", "发现二：技术壁垒抬高"],
                "five_forces_supplier_power": "中等",
                "five_forces_buyer_power": "较强",
                "five_forces_new_entrants": "中等",
                "five_forces_substitutes": "较低",
                "five_forces_rivalry": "高",
                "competitor_radar": ["研发能力强", "渠道覆盖广", "品牌力弱"],
                "strategy_recommendations": ["强化差异化", "锁定核心客户"],
            }
        else:
            payload = {"summary": f"步骤摘要（{step_key}）", "findings": ["发现一", "发现二"]}
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
    """Fake Embedding 工厂（外部 SaaS 豁免——6-4 集成同款）。"""
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


def _make_report_service(tmp_path: Path) -> Any:
    """手工构造报告生成服务（真实五依赖 + tmp_path L0 覆写——写路径隔离）。

    L0 覆写三理由（R1-17）：真实 resolve 通道写运行机器 ~/.sisys/memory/reports/
    污染共享目录；SCOPED lambda 缓存于 resolver 实例 setenv 不生效；并行计数
    互扰。服务实例层注入是唯一可靠隔离（6-3 先例）。
    """
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


async def _archive_steps(
    service: ChainOfThoughtArchiveService, plan_id: str, skip_stages: frozenset[str] = frozenset()
) -> list[Any]:
    """逐 stage 组装归档（跳步变体——AC-4 钦定构造手段；禁跑后删行）。"""
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
            if stage in skip_stages:
                continue
            record = await service.compose_and_archive_step_chain(uuid.UUID(plan_id), stage, _make_material(stage, index=index))
            records.append(record)
    await manager.get_async_engine().dispose()
    return records


async def _query_outbox_report_rows(report_id: str) -> list[Any]:
    """查询 ReportGenerated outbox 行（payload->'payload'->>'report_id' 两级路径）。"""
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
                    "SELECT payload->'payload'->>'report_id', payload->'payload'->>'report_type', "
                    "payload->'payload'->>'file_path' FROM event_outbox "
                    "WHERE payload->'payload'->>'report_id' = :rid AND event_type = 'ReportGenerated'"
                ),
                {"rid": report_id},
            )
            return list(result.fetchall())
    finally:
        await manager.get_async_engine().dispose()


async def _count_report_rows(plan_id: str) -> int:
    """按 plan_id 计数 strategic_reports 行（净增 0 断言面）。"""
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
                sa.text("SELECT COUNT(*) FROM strategic_reports WHERE plan_id = CAST(:p AS uuid)"),
                {"p": plan_id},
            )
            return int(result.scalar_one())
    finally:
        await manager.get_async_engine().dispose()


async def _count_outbox_report_rows(plan_id: str) -> int:
    """按 plan_id 双通道计数 outbox ReportGenerated 行（净增 0 断言面）。"""
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
                    "SELECT COUNT(*) FROM event_outbox WHERE event_type = 'ReportGenerated' "
                    "AND (payload->'metadata'->>'plan_id' = :p OR payload->'payload'->>'report_id' IN "
                    "(SELECT report_id::text FROM strategic_reports WHERE plan_id = CAST(:p AS uuid)))"
                ),
                {"p": plan_id},
            )
            return int(result.scalar_one())
    finally:
        await manager.get_async_engine().dispose()


async def _cleanup_report_residues(plan_id: str) -> None:
    """报告侧定向清理（outbox report 行 + strategic_reports 行——归档面另走 6-4 清理）。"""
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
    for statement in (
        "DELETE FROM event_outbox WHERE payload->'payload'->>'report_id' IN "
        "(SELECT report_id::text FROM strategic_reports WHERE plan_id = CAST(:p AS uuid))",
        "DELETE FROM strategic_reports WHERE plan_id = CAST(:p AS uuid)",
    ):
        try:
            async with engine.begin() as conn:
                await conn.execute(sa.text(statement), {"p": plan_id})
        except Exception:
            pass
    await engine.dispose()


async def _cleanup_archive_residues_by_plan(plan_id: str) -> None:
    """归档三面定向清理（6-4 _cleanup_by_plan_id 移植——档案行/Qdrant 点/MinIO WORM/outbox）。"""
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
                blob_refs.append(str(row[1]))
    except Exception:
        pass
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
                            [DeleteObject(ref) for ref in blob_refs],
                            bypass_governance_mode=True,
                        )
                    )

                await asyncio.to_thread(_remove)
            except Exception:
                pass
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    sa.text("DELETE FROM strategic_archives WHERE archive_id = ANY(:ids)"),
                    {"ids": archive_ids},
                )
        except Exception:
            pass
    await engine.dispose()


async def _cleanup_all(plan_id: str) -> None:
    """全量清理链（报告侧 + 归档三面）。"""
    await _cleanup_report_residues(plan_id)
    await _cleanup_archive_residues_by_plan(plan_id)


def _read_report_text(tmp_path: Path, memory_id: str) -> str:
    """直接读回 L0 报告文件（tmp_path 物理路径——与端口 read 等价双通道）。"""
    return (tmp_path / "reports" / f"{memory_id}.md").read_text(encoding="utf-8")


async def test_scenario_one_full_generation_roundtrip(tmp_path: Path) -> None:
    """场景① 全链生成（八步归档 → 报告三元 + 章节结构断言）。"""
    await _probe_services()
    plan_id = str(uuid.uuid4())
    archive_service = _make_archive_service()
    report_service = _make_report_service(tmp_path)
    from pathlib import PurePosixPath

    from src.application.ports.chain_of_thought_archive import SYNTHESIS_DISPLAY_NAME
    from src.application.services.blm_planning_prompts import (
        MARKET_INSIGHT_STEP_CONFIG,
        PERFORMANCE_GAP_CONFIG,
    )

    try:
        records = await _archive_steps(archive_service, plan_id)
        assert len(records) == 8
        report = await report_service.generate_markdown_report(uuid.UUID(plan_id))
        # 实体字段
        assert str(report.plan_id) == plan_id
        assert report.section_count == 11
        assert report.degraded_section_count == 0
        # L0 读回（memory_id 经实体 file_path stem 反解）
        memory_id = PurePosixPath(report.file_path).stem
        text = _read_report_text(tmp_path, memory_id)
        # 章节结构断言（display_name 源独立构造期望——非报告文本自证）
        step_titles = [f"2.{i} {cfg.display_name}" for i, cfg in enumerate(MARKET_INSIGHT_STEP_CONFIG.values(), start=1)]
        for title in (
            "# 战略规划报告（BLM 前两阶段）",
            f"## 1 {PERFORMANCE_GAP_CONFIG.display_name}",
            "### 1.1 财务差距",
            "### 1.2 运营差距",
            "### 1.3 根因分析",
            "### 1.4 业务组合健康度",
            "## 2 市场洞察",
            *step_titles,
            f"### 2.7 {SYNTHESIS_DISPLAY_NAME}",
        ):
            assert title in text, f"冻结章节标题缺失: {title}"
        # L2 行可读回
        row_count = await _count_report_rows(plan_id)
        assert row_count == 1
        # get_latest_by_plan 值级读回（CR1-F2——排序方向行为级验证：实体七字段全等比对）
        from src.domain.ports.resolver import resolve

        latest = await resolve("report_repository").get_latest_by_plan(uuid.UUID(plan_id))
        assert latest is not None
        assert latest.report_id == report.report_id
        assert latest.plan_id == plan_id
        assert latest.report_type == report.report_type
        assert latest.file_path == report.file_path
        assert latest.section_count == report.section_count
        assert latest.degraded_section_count == report.degraded_section_count
        # outbox 落行三键值级
        rows = await _query_outbox_report_rows(str(report.report_id))
        assert len(rows) == 1
        assert rows[0][0] == str(report.report_id)
        assert rows[0][1] == "markdown"
        assert rows[0][2] == report.file_path
    finally:
        await _cleanup_all(plan_id)
    assert await _count_report_rows(plan_id) == 0, "清理后报告行净增应为 0"


async def test_scenario_two_formatting_elements(tmp_path: Path) -> None:
    """场景② 格式化三要素（标题层级/GFM 表格行列/列表项数/中文原样）。"""
    await _probe_services()
    plan_id = str(uuid.uuid4())
    archive_service = _make_archive_service()
    report_service = _make_report_service(tmp_path)
    from pathlib import PurePosixPath

    try:
        await _archive_steps(archive_service, plan_id)
        report = await report_service.generate_markdown_report(uuid.UUID(plan_id))
        memory_id = PurePosixPath(report.file_path).stem
        text = _read_report_text(tmp_path, memory_id)
        lines = text.splitlines()
        # ATX 标题层级严格递进（逐行 # 计数 ∈ {1,2,3} 且首行 H1）
        heading_levels = [len(line) - len(line.lstrip("#")) for line in lines if line.startswith("#")]
        assert heading_levels[0] == 1
        assert all(1 <= level <= 3 for level in heading_levels)
        # PESTEL 表 6 行数据（表头定位法——防分隔行串扰）
        pestel_header = lines.index("| 维度 | 评估 |")
        assert lines[pestel_header + 1] == "| --- | --- |"
        pestel_data = [line for line in lines[pestel_header + 2 : pestel_header + 8]]
        assert all(line.startswith("| ") for line in pestel_data)
        assert len(pestel_data) == 6
        # 五力表 5 行
        forces_header = lines.index("| 五力 | 评估 |")
        forces_data = lines[forces_header + 2 : forces_header + 7]
        assert len(forces_data) == 5
        # 列表项数与源数据一致（root_causes 2 项/technology_roadmap 3 项——素材独立构造）
        assert "- 根因一：组织能力缺口" in text
        assert text.count("- 试点验证\n- 规模推广\n- 生态整合") == 1
        # 中文原样（无 \u 转义）
        assert "\\u" not in text
    finally:
        await _cleanup_all(plan_id)


async def test_scenario_three_partial_missing_and_three_missing(tmp_path: Path) -> None:
    """场景③ 部分缺失降级（跳一步六子步）+ ③b 缺三步不变量。"""
    await _probe_services()
    archive_service = _make_archive_service()
    report_service = _make_report_service(tmp_path)
    from pathlib import PurePosixPath

    # ③ 跳一步（六子步钦定——期望 degraded==1）
    plan_one = str(uuid.uuid4())
    try:
        records = await _archive_steps(archive_service, plan_one, skip_stages=frozenset({"market_insight_trend"}))
        assert len(records) == 7
        report = await report_service.generate_markdown_report(uuid.UUID(plan_one))
        assert report.degraded_section_count == 1
        assert report.section_count == 11  # 恒 11（R3-1 骨架渲染冻结）
        memory_id = PurePosixPath(report.file_path).stem
        text = _read_report_text(tmp_path, memory_id)
        assert "### 2.1 看趋势" in text
        assert "> ⚠️ [数据缺失] 看趋势：该步骤归档记录不可用" in text
        assert "| [数据缺失] | 看趋势 | 该步骤归档记录不可用 |" in text  # 附录 B 行
    finally:
        await _cleanup_all(plan_one)

    # ③b 六子缺三步（期望 degraded==3 ≤ 11 无 242——计数口径锁死）
    plan_three = str(uuid.uuid4())
    try:
        await _archive_steps(
            archive_service,
            plan_three,
            skip_stages=frozenset({"market_insight_trend", "market_insight_self", "market_insight_opportunity"}),
        )
        report = await report_service.generate_markdown_report(uuid.UUID(plan_three))
        assert report.degraded_section_count == 3
        assert report.section_count == 11
        assert report.degraded_section_count <= report.section_count  # 不变量（242 未触发）
    finally:
        await _cleanup_all(plan_three)


async def test_scenario_four_total_missing_raises_490(tmp_path: Path) -> None:
    """场景④ 490 全缺（从未归档的独立 plan_id——天然 total==0）。"""
    from src.domain.exceptions import ReportGenerationError

    await _probe_services()
    plan_id = str(uuid.uuid4())
    report_service = _make_report_service(tmp_path)
    try:
        with pytest.raises(ReportGenerationError) as exc_info:
            await report_service.generate_markdown_report(uuid.UUID(plan_id))
        assert exc_info.value.code == "EXCEPTION_490"
        assert exc_info.value.message == "该 plan_id 无思维链归档记录，无法生成报告"
        assert exc_info.value.context["plan_id"] == plan_id
        assert await _count_report_rows(plan_id) == 0  # 零落库
    finally:
        await _cleanup_all(plan_id)


async def test_scenario_five_performance_concurrent_and_zero_delta(tmp_path: Path) -> None:
    """场景⑤ 性能采样（单 plan_id×20）+ 并发 3 + 净增 0（OD-8 口径 docstring 见模块头）。

    生成窗口口径 = execute 调用包裹（聚合起点→事件发布返回——归档构造前置
    显式出栈）；n=20 P95 = sorted[ceil(0.95*20)-1] 即次大值（噪声敏感如实承受）。
    """
    await _probe_services()
    archive_service = _make_archive_service()
    report_service = _make_report_service(tmp_path)  # SINGLETON 语义共享实例（AC-7 无状态约束）
    from pathlib import PurePosixPath

    plan_perf = str(uuid.uuid4())
    plan_ids = [plan_perf] + [str(uuid.uuid4()) for _ in range(3)]
    try:
        # 跑前净增基线（五面——报告行/outbox 报告行/归档行）
        baseline_rows = {pid: await _count_report_rows(pid) for pid in plan_ids}
        # 数据源构造（性能 1 次 + 并发 3——OD-10 幂等锚：重复生成合法采样）
        await _archive_steps(archive_service, plan_perf)
        for pid in plan_ids[1:]:
            await _archive_steps(archive_service, pid)
        # 20 轮采样（单一 plan_id）
        durations: list[float] = []
        report_ids: set[str] = set()
        for _ in range(_PERF_ROUNDS):
            started = time.monotonic()
            report = await report_service.generate_markdown_report(uuid.UUID(plan_perf))
            durations.append(time.monotonic() - started)
            report_ids.add(str(report.report_id))
            # 每轮即时读回（秒级覆写形态下事后统一断言会假失败——AC-1 注记）
            memory_id = PurePosixPath(report.file_path).stem
            assert _read_report_text(tmp_path, memory_id)
        assert len(report_ids) == _PERF_ROUNDS  # report_id 集合无重复
        assert await _count_report_rows(plan_perf) == _PERF_ROUNDS
        ordered = sorted(durations)
        p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
        assert p95 < _P95_LIMIT_SECONDS, f"生成窗口 P95 实测={p95:.3f}s 期望<{_P95_LIMIT_SECONDS}s（OD-8 口径）"
        # 并发 3（gather 形态锚：async 函数内直 await——裸 async 测试函数无跨 loop 陷阱）
        concurrent_reports = await asyncio.gather(
            *(report_service.generate_markdown_report(uuid.UUID(pid)) for pid in plan_ids[1:])
        )
        assert len(concurrent_reports) == 3
        per_plan = {pid: await _count_report_rows(pid) for pid in plan_ids[1:]}
        assert all(count == 1 for count in per_plan.values()), f"并发三元串扰: {per_plan}"
        # 互不串扰（report_id 互异 + 文件互异）
        concurrent_ids = {str(r.report_id) for r in concurrent_reports}
        assert len(concurrent_ids) == 3
    finally:
        for pid in plan_ids:
            await _cleanup_all(pid)
    # 净增 0（跑后与基线对照——报告行净增 0；outbox/归档行随 _cleanup_all 清）
    for pid in plan_ids:
        assert await _count_report_rows(pid) == baseline_rows[pid], f"清理后净增非 0: {pid}"
        assert await _count_outbox_report_rows(pid) == 0, f"outbox 报告行残留: {pid}"
