"""白标报告基础集成测试（Story 6-11 Task 8——真实链端到端五场景）.

真实服务模式：独立 PG 连接 commit 式 + 定向 DELETE 行数断言回收 + MinIO
共享 default 桶（resolve 通道组合根未传 tenant_id 恒 ``{prefix}-brand-assets-default``
——对象键锚 template_id 定位+定向清理；6-5b 集成共享桶先例直系）+ 自愈建桶
前置（bucket_exists 探测→make_bucket 勿带 object_lock——WORM 锁破坏 logo
覆盖与清理）+ 真实渲染端到端。

五场景：
- 场景①保存主链（真实 PG 行+真实 MinIO logo 对象+读回逐字节）
- 场景②UPSERT 修订（同名二存 template_id 稳定+updated_at 前进点名断言
  [AC-1 语义的端到端单点承载]+L4 同键覆盖）
- 场景③白标导出端到端（真实 BLM 产物预置→generate_pdf_report(brand)→
  L2 行品牌两键+L4 WORM PDF 对象）
- 场景④品牌应用 100% 准确端到端（pypdf 解析：品牌字体资源名[noto 形态]+
  首页 Image XObject+品牌色 fp_str——对照腿零图像）
- 场景⑤性能双段（保存 20 轮 P95<200ms+导出 20 轮 P95<60s）

性能三段口径差声明（AC-8——六连纪律第七连）：保存 P95<200ms=服务面窗口
（20 轮 sorted[ceil(0.95n)-1]）；导出<1 分钟=6-5b 60s P95 口径继承（编程面
use case 直调免 bootstrap 开销混入）；准确率 100%=场景④结构化四件套（非计时）。

隔离：pytestmark 挂 xdist_group("blm-planning-perf")（与 6-7~6-10 全部
strategic_* 提交型写入方同 worker 串行）；TestTenant 前缀模板名；多模板行
预置显式 updated_at 构造（单 now 基准+微秒偏移——R2-B-2）；teardown 顺序
钦定 L4 对象先行 PG 行后行。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_white_label_report.py -v
"""

import asyncio
import math
import uuid as uuid_module
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.database,
    pytest.mark.redis,
    pytest.mark.qdrant,
    pytest.mark.minio,
    pytest.mark.xdist_group("blm-planning-perf"),
]

#: 性能口径常量（AC-8）
_SAMPLE_ROUNDS: int = 20
_WARMUP_ROUNDS: int = 2
_P95_PERCENTILE: float = 0.95
_SAVE_P95_LIMIT_MS: float = 200.0
_EXPORT_P95_LIMIT_SECONDS: float = 60.0

#: 品牌/归档桶类型（清理通道）
_BRAND_BUCKET_TYPE: str = "brand-assets"
_EVIDENCE_BUCKET_TYPE: str = "archive-evidence"

#: 八 stage 期望序（BLM 预置——与 6-5a/6-5b 同源）
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

_BLM_TASK = "制定新能源汽车行业五年战略规划（白标集成真实链）"


def _env() -> Any:
    """测试环境配置单源."""
    from tests.environments import get_test_env

    return get_test_env()


def _clear_resolver_caches() -> None:
    """驱逐 resolver 双缓存（每测试装配前置——6-10 直系）。"""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()


def _clear_session_ctx() -> None:
    """清 ContextVar 会话（预置直写前置）。"""
    from src.infrastructure.storage.postgresql.session_context import clear_session

    clear_session()


async def _make_engine() -> Any:
    """独立异步引擎（teardown/直查专用）."""
    from sqlalchemy.ext.asyncio import create_async_engine

    env = _env()
    return create_async_engine(
        f"postgresql+asyncpg://{env.postgres.username}:{env.postgres.password}"
        f"@{env.postgres.host}:{env.postgres.port}/{env.postgres.database}"
    )


async def _require_services() -> None:
    """服务可达探测（PG 四表+Redis+Qdrant+MinIO 双桶自愈——失败动态 skip；
    pytest-asyncio auto 模式下测试已在事件循环内——本协程直接 await 不自建
    loop。开头三清：pytest-asyncio 每测试新事件循环，SINGLETON 缓存实例可能
    绑定前一测试 loop（InterfaceError/旧 session——驱逐后 resolve 惰性重建）。"""
    _clear_resolver_caches()
    import pytest as _pytest
    from sqlalchemy import text

    from src.domain.ports.registry import _global_registry

    if _global_registry.get("agent_workflow_use_case") is None:
        from src.composition_root import bootstrap

        bootstrap()
    env = _env()
    engine = await _make_engine()
    try:
        async with engine.connect() as conn:
            for table in ("event_outbox", "strategic_archives", "strategic_reports", "documents", "brand_templates"):
                await conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
    except Exception as exc:
        await engine.dispose()
        _pytest.skip(f"PostgreSQL/表不可用: {exc}")
    finally:
        await engine.dispose()
    import redis.asyncio as aioredis

    redis_client = aioredis.Redis(host=env.redis.host, port=env.redis.port, decode_responses=False)
    try:
        await redis_client.ping()
    except Exception as exc:
        await redis_client.close()
        _pytest.skip(f"Redis 不可用: {exc}")
    await redis_client.close()
    import urllib.request

    def _probe_qdrant() -> None:
        url = f"http://{env.qdrant.host}:{env.qdrant.port}/collections"
        with urllib.request.urlopen(url, timeout=10) as response:
            assert response.status == 200

    try:
        await asyncio.to_thread(_probe_qdrant)
    except Exception as exc:
        _pytest.skip(f"Qdrant 不可用: {exc}")
    try:
        await asyncio.to_thread(_ensure_brand_bucket)
    except Exception as exc:
        _pytest.skip(f"MinIO 不可用: {exc}")


def _minio_client() -> Any:
    """裸 MinIO client（清理/建桶专用）."""
    from minio import Minio

    env = _env()
    return Minio(
        endpoint=env.minio.endpoint,
        access_key=env.minio.access_key,
        secret_key=env.minio.secret_key,
        secure=env.minio.secure,
    )


def _resolve_bucket_name(bucket_type: str) -> str:
    """经组合根 l4_object 解析物理桶名（零硬编码）."""
    from src.domain.ports.resolver import get_resolver

    l4 = get_resolver().resolve("l4_object")
    return str(l4._repository._resolve_bucket_name(bucket_type))


def _ensure_brand_bucket() -> None:
    """brand-assets 桶自愈（探测→make_bucket 勿带 object_lock——OD-3⑦ 钦定）."""
    client = _minio_client()
    bucket_name = _resolve_bucket_name(_BRAND_BUCKET_TYPE)
    if not client.bucket_exists(bucket_name):
        try:
            client.make_bucket(bucket_name)
        except Exception:
            if not client.bucket_exists(bucket_name):
                raise


def _make_logo_png(path: Path) -> None:
    """Pillow 生成最小合法 PNG（可解码性前提）."""
    from PIL import Image

    Image.new("RGB", (64, 64), color=(31, 78, 121)).save(path, format="PNG")


def _unique_template_name() -> str:
    """TestTenant 前缀模板名（name UNIQUE 防撞+teardown 定位）."""
    return f"itest-{uuid_module.uuid4().hex[:8]}-品牌模板"


async def _save_template_row(
    *,
    name: str,
    color_scheme: str,
    font_preset: str,
    logo_object_key: str | None,
    updated_at: datetime,
    created_at: datetime | None = None,
) -> str:
    """模板行直写（repo.save 直写通道——updated_at 显式构造[单 now 基准+偏移]）."""
    from src.domain.entities.brand_template import BrandTemplate
    from src.domain.ports.resolver import resolve

    _clear_session_ctx()
    template_id = uuid_module.uuid4()
    entity = BrandTemplate(
        template_id=template_id,
        name=name,
        color_scheme=color_scheme,
        font_preset=font_preset,
        logo_object_key=logo_object_key,
        created_at=created_at or (updated_at - timedelta(microseconds=1)),
        updated_at=updated_at,
    )
    await resolve("brand_template_repository").save(entity)
    return str(template_id)


def _make_fake_embedding() -> Any:
    """Fake Embedding 工厂（外部 SaaS 豁免——固定 1024 维）."""
    from unittest.mock import AsyncMock

    from src.domain.ports.embedding_service import EmbeddingServicePort

    fake = AsyncMock(spec=EmbeddingServicePort)
    fake.embed_query = AsyncMock(return_value=[0.1] * 1024)
    fake.embed_documents = AsyncMock(return_value=[[0.1] * 1024])
    fake.close = AsyncMock()
    return fake


def _assemble_services(engine: Any) -> dict[str, Any]:
    """轻装配（归档通道+PDF 主链十依赖——6-5b :600-679 直系+v1.1.0 品牌依赖）."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.application.services.chain_of_thought_archive_service import ChainOfThoughtArchiveService
    from src.application.services.pdf_report_generation_service import PdfReportGenerationService
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.application.use_cases.generate_pdf_report import GeneratePdfReportUseCase
    from src.domain.ports.resolver import resolve
    from src.infrastructure.storage.postgresql.session_context import session_context

    class _SessionScopedFind:
        """find 会话包装（组合根 wrapper 同款——测试装配镜像生产通道形态）。"""

        def __init__(self, inner: Any, factory: Any) -> None:
            self._inner = inner
            self._factory = factory

        async def find(self, query: Any) -> Any:
            async with session_context(self._factory):
                return await self._inner.find(query)

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
    from typing import cast

    from src.domain.ports.document_repository import DocumentRepositoryPort

    pdf_report_service = PdfReportGenerationService(
        chain_archive_service=chain_archive_service,
        snapshot_repository=resolve("snapshot_repository"),
        report_repository=resolve("report_repository"),
        event_publisher=resolve("event_publisher"),
        pdf_renderer=resolve("pdf_renderer"),
        l4_object=resolve("l4_object"),
        l3_vector=resolve("l3_vector"),
        document_repository=cast(
            DocumentRepositoryPort,
            _SessionScopedFind(resolve("document_repository"), async_sessionmaker(engine)),
        ),
        archive_service=resolve("strategic_archive_service"),
        brand_template_service=resolve("brand_template_service"),
    )
    return {
        "chain_archive_service": chain_archive_service,
        "pdf_report_service": pdf_report_service,
        "pdf_use_case": GeneratePdfReportUseCase(report_service=pdf_report_service),
    }


def _make_material(stage: str, *, index: int = 0) -> Any:
    """归档素材构造（stage 判型三态——6-5b 同款）."""
    from src.application.ports.chain_of_thought_archive import StepChainMaterial

    is_synthesis = stage == "market_insight_synthesis"
    is_gap = stage == "performance_gap"
    payload: dict[str, Any]
    if is_synthesis:
        payload = {"conclusions": ["综合结论（白标集成）"], "degraded_inputs": ["market_insight_trend"]}
    elif is_gap:
        payload = {
            "financial_gap": "财务差距量化：营收达成率 85%",
            "operational_gap": "运营差距分析：交付周期延长",
            "root_causes": ["根因一", "根因二"],
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


async def _archive_steps(services: dict[str, Any], engine: Any, plan_id: str) -> None:
    """八阶段归档预置（session_context 独立会话承载）。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.infrastructure.storage.postgresql.session_context import session_context

    factory = async_sessionmaker(engine)
    async with session_context(factory):
        for index, stage in enumerate(_EXPECTED_STAGE_ORDER):
            await services["chain_archive_service"].compose_and_archive_step_chain(
                uuid_module.UUID(plan_id), stage, _make_material(stage, index=index)
            )


async def _teardown_assets(
    engine: Any,
    *,
    plan_ids: list[str],
    report_ids: list[str],
    template_ids: list[str],
    logo_object_keys: list[str],
    pdf_object_keys: list[str],
) -> None:
    """teardown 六步链（L4 对象先行 PG 行后行钦定；rowcount 断言殿后防孤儿）."""
    from minio.deleteobjects import DeleteObject
    from sqlalchemy import text

    # ①② L4 对象（logo 非 WORM 直删+WORM PDF bypass）
    def _remove_objects(bucket_type: str, keys: list[str], bypass: bool) -> None:
        if not keys:
            return
        client = _minio_client()
        errors = client.remove_objects(
            _resolve_bucket_name(bucket_type),
            [DeleteObject(key) for key in keys],
            bypass_governance_mode=bypass,
        )
        for _ in errors:
            pass

    for bucket_type, keys, bypass in (
        (_BRAND_BUCKET_TYPE, logo_object_keys, False),
        (_EVIDENCE_BUCKET_TYPE, pdf_object_keys, True),
    ):
        try:
            await asyncio.to_thread(_remove_objects, bucket_type, keys, bypass)
        except Exception as error:
            print(f"[teardown:white-label] {bucket_type} 对象清理异常（容错）: {error}")
    # ③④⑤ PG 行（报告行+outbox 行+归档三面行）
    from sqlalchemy.ext.asyncio import AsyncSession

    archive_ids: list[str] = []
    try:
        async with AsyncSession(engine) as session:
            if plan_ids:
                rows = await session.execute(
                    text("SELECT archive_id FROM strategic_archives WHERE plan_id = ANY(:ids)"),
                    {"ids": plan_ids},
                )
                archive_ids = [str(row[0]) for row in rows]
            if report_ids:
                await session.execute(
                    text("DELETE FROM strategic_reports WHERE report_id = ANY(:ids)"),
                    {"ids": report_ids},
                )
            if plan_ids:
                await session.execute(
                    text(
                        "DELETE FROM event_outbox WHERE payload->'metadata'->>'plan_id' = ANY(:ids) "
                        "OR payload->'payload'->>'plan_id' = ANY(:ids)"
                    ),
                    {"ids": plan_ids},
                )
                await session.execute(text("DELETE FROM strategic_reports WHERE plan_id = ANY(:ids)"), {"ids": plan_ids})
            if archive_ids:
                await session.execute(
                    text("DELETE FROM strategic_archives WHERE archive_id = ANY(:ids)"),
                    {"ids": archive_ids},
                )
            await session.commit()
    except Exception as error:
        print(f"[teardown:white-label] PG 行清理异常（容错）: {error}")
    # ⑥ 品牌模板行（rowcount 断言殿后）
    try:
        async with AsyncSession(engine) as session:
            if template_ids:
                from sqlalchemy import CursorResult

                result = await session.execute(
                    text("DELETE FROM brand_templates WHERE template_id = ANY(:ids)"),
                    {"ids": template_ids},
                )
                assert isinstance(result, CursorResult), "DML 语句返回 CursorResult（rowcount 类型收窄）"
                assert result.rowcount == len(template_ids), (
                    f"brand_templates DELETE 行数 {result.rowcount} != 预期 {len(template_ids)}（静默 0 行假绿防线）"
                )
            await session.commit()
    except AssertionError:
        raise
    except Exception as error:
        print(f"[teardown:white-label] 品牌行清理异常（容错）: {error}")


async def _run_scenario(
    tmp_path: Path,
    *,
    plan_count: int = 1,
    with_brand_template: bool = True,
) -> dict[str, Any]:
    """场景执行骨架（探测→预置→组装→返回登记面——供四场景复用）."""
    _clear_resolver_caches()
    engine = await _make_engine()
    ctx: dict[str, Any] = {
        "engine": engine,
        "plan_ids": [],
        "report_ids": [],
        "template_ids": [],
        "logo_object_keys": [],
        "pdf_object_keys": [],
    }
    try:
        if with_brand_template:
            name = _unique_template_name()
            logo_path = tmp_path / f"logo-{uuid_module.uuid4().hex[:8]}.png"
            _make_logo_png(logo_path)
            base = datetime.now(UTC)
            template_id = await _save_template_row(
                name=name,
                color_scheme="corporate-blue",
                font_preset="noto-sans-sc",
                logo_object_key=None,
                updated_at=base + timedelta(microseconds=1000),
            )
            from src.domain.ports.resolver import resolve

            object_key = f"logos/{template_id}"
            await resolve("l4_object").store(
                bucket_type=_BRAND_BUCKET_TYPE,
                object_key=object_key,
                file_path=str(logo_path),
                content_type="image/png",
            )
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import AsyncSession

            async with AsyncSession(engine) as session:
                await session.execute(
                    text("UPDATE brand_templates SET logo_object_key = :k WHERE template_id = :tid"),
                    {"k": object_key, "tid": template_id},
                )
                await session.commit()
            ctx["template_ids"].append(template_id)
            ctx["logo_object_keys"].append(object_key)
            ctx["template_name"] = name
            ctx["template_id"] = template_id
            ctx["logo_path"] = str(logo_path)
        services = _assemble_services(engine)
        ctx["services"] = services
        for _ in range(plan_count):
            plan_id = str(uuid_module.uuid4())
            await _archive_steps(services, engine, plan_id)
            ctx["plan_ids"].append(plan_id)
        ctx["cleanup"] = lambda: _teardown_assets(
            engine,
            plan_ids=ctx["plan_ids"],
            report_ids=ctx["report_ids"],
            template_ids=ctx["template_ids"],
            logo_object_keys=ctx["logo_object_keys"],
            pdf_object_keys=ctx["pdf_object_keys"],
        )
        return ctx
    except BaseException:
        await _teardown_assets(
            engine,
            plan_ids=ctx["plan_ids"],
            report_ids=ctx["report_ids"],
            template_ids=ctx["template_ids"],
            logo_object_keys=ctx["logo_object_keys"],
            pdf_object_keys=ctx["pdf_object_keys"],
        )
        await engine.dispose()
        raise


async def _fetch_latest_report_metadata(engine: Any, plan_id: str) -> dict[str, Any]:
    """按 plan 读回最新报告行（metadata/file_path——S3 断言源）."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(engine) as session:
        rows = await session.execute(
            text(
                "SELECT report_id, file_path, metadata FROM strategic_reports "
                "WHERE plan_id = CAST(:p AS uuid) ORDER BY created_at DESC LIMIT 1"
            ),
            {"p": plan_id},
        )
        row = rows.one()
        return {"report_id": str(row[0]), "file_path": str(row[1]), "metadata": row[2] or {}}


async def _read_pdf_bytes(file_path: str) -> bytes:
    """L4 读回 PDF bytes（WORM 读允许）。"""
    from src.domain.ports.resolver import resolve

    chunks: list[bytes] = []
    async for chunk in resolve("l4_object").retrieve(bucket_type=_EVIDENCE_BUCKET_TYPE, object_key=file_path):
        chunks.append(chunk)
    return b"".join(chunks)


async def _read_logo_bytes(object_key: str) -> bytes:
    """L4 读回 logo bytes。"""
    from src.domain.ports.resolver import resolve

    chunks: list[bytes] = []
    async for chunk in resolve("l4_object").retrieve(bucket_type=_BRAND_BUCKET_TYPE, object_key=object_key):
        chunks.append(chunk)
    return b"".join(chunks)


class TestSaveMasterChain:
    """场景①：保存主链（真实 PG 行+真实 MinIO logo 对象+读回逐字节）。"""

    async def test_save_full_chain_roundtrip(self, tmp_path: Path) -> None:
        """保存主链端到端（服务→PG 行七字段+L4 对象逐字节）。"""
        import pytest as _pytest

        try:
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import AsyncSession

            from src.domain.ports.resolver import resolve

            await _require_services()
            _clear_resolver_caches()

            engine = await _make_engine()
            try:
                logo_path = tmp_path / "save-logo.png"
                _make_logo_png(logo_path)
                name = _unique_template_name()
                service = resolve("brand_template_service")
                saved = await service.save_brand_template(
                    name=name, color_scheme="corporate-blue", font_preset="noto-sans-sc", logo_path=str(logo_path)
                )
                async with AsyncSession(engine) as session:
                    rows = await session.execute(
                        text(
                            "SELECT name, color_scheme, font_preset, logo_object_key FROM "
                            "brand_templates WHERE template_id = CAST(:t AS uuid)"
                        ),
                        {"t": str(saved.template_id)},
                    )
                    row = rows.one()
                    assert row[0] == name and row[1] == "corporate-blue" and row[2] == "noto-sans-sc"
                    assert row[3] == f"logos/{saved.template_id}"
                fetched = await _read_logo_bytes(f"logos/{saved.template_id}")
                assert fetched == Path(logo_path).read_bytes(), "L4 读回逐字节对照失败"
                await _teardown_assets(
                    engine,
                    plan_ids=[],
                    report_ids=[],
                    template_ids=[str(saved.template_id)],
                    logo_object_keys=[f"logos/{saved.template_id}"],
                    pdf_object_keys=[],
                )
            finally:
                await engine.dispose()
        except Exception as error:
            if "不可用" in str(error):
                _pytest.skip(str(error))
            raise


class TestUpsertRevision:
    """场景②：UPSERT 修订（updated_at 前进端到端单点承载）。"""

    async def test_same_name_revision_template_id_stable(self) -> None:
        """同名二存：template_id 稳定+updated_at 前进点名断言+三配置字段更新。"""
        import pytest as _pytest

        try:
            from src.domain.ports.resolver import resolve

            await _require_services()
            _clear_resolver_caches()
            engine = await _make_engine()
            try:
                name = _unique_template_name()
                service = resolve("brand_template_service")
                first = await service.save_brand_template(name=name, color_scheme="graphite", font_preset="stsong")
                await asyncio.sleep(0.01)  # updated_at 前进可判别（服务定时戳 ms 粒度）
                second = await service.save_brand_template(name=name, color_scheme="burgundy", font_preset="noto-sans-sc")
                assert str(second.template_id) == str(first.template_id), "同名修订 template_id 漂移"
                assert second.updated_at is not None and first.updated_at is not None
                assert second.updated_at > first.updated_at, "updated_at 前进点名断言（AC-1 端到端单点承载）"
                assert second.color_scheme == "burgundy"
                await _teardown_assets(
                    engine,
                    plan_ids=[],
                    report_ids=[],
                    template_ids=[str(first.template_id)],
                    logo_object_keys=[],
                    pdf_object_keys=[],
                )
            finally:
                await engine.dispose()
        except Exception as error:
            if "不可用" in str(error):
                _pytest.skip(str(error))
            raise


class TestWhiteLabelExportEndToEnd:
    """场景③：白标导出端到端（真实 BLM 预置→品牌导出→L2/L4 双资产）。"""

    async def test_branded_export_master_chain(self, tmp_path: Path) -> None:
        """白标导出主链（use case 直调→metadata 品牌两键+WORM 对象键通道）。"""
        import pytest as _pytest

        try:
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import AsyncSession

            await _require_services()
            ctx = await _run_scenario(tmp_path)
            try:
                plan_id = ctx["plan_ids"][0]
                report = await ctx["services"]["pdf_use_case"].execute(
                    plan_id=plan_id, brand_template_name=ctx["template_name"]
                )
                ctx["report_ids"].append(str(report.report_id))
                ctx["pdf_object_keys"].append(str(report.file_path))
                assert str(report.file_path) == f"reports/{plan_id}/{report.report_id}.pdf"
                async with AsyncSession(ctx["engine"]) as session:
                    rows = await session.execute(
                        text(
                            "SELECT metadata->>'brand_template_id', metadata->>'brand_applied' "
                            "FROM strategic_reports WHERE report_id = CAST(:r AS uuid)"
                        ),
                        {"r": str(report.report_id)},
                    )
                    row = rows.one()
                    assert row[0] == ctx["template_id"], f"brand_template_id 漂移: {row[0]}"
                    assert row[1] == "true" or row[1] == "True", f"brand_applied 漂移: {row[1]}"
                pdf_bytes = await _read_pdf_bytes(str(report.file_path))
                assert pdf_bytes.startswith(b"%PDF")
            finally:
                await ctx["cleanup"]()
                await ctx["engine"].dispose()
        except Exception as error:
            if "不可用" in str(error):
                _pytest.skip(str(error))
            raise


class TestBrandAccuracyEndToEnd:
    """场景④：品牌应用 100% 准确端到端（pypdf 结构化四件套+对照腿）。"""

    async def test_brand_accuracy_four_pieces(self, tmp_path: Path) -> None:
        """四件套端到端（字体资源名+首页 XObject+品牌色 fp_str——对照腿零图像）。"""
        import io

        import pytest as _pytest

        try:
            from pypdf import PdfReader
            from reportlab.lib.rl_accel import fp_str

            await _require_services()
            ctx = await _run_scenario(tmp_path, plan_count=1)
            try:
                plan_id = ctx["plan_ids"][0]
                branded = await ctx["services"]["pdf_use_case"].execute(
                    plan_id=plan_id, brand_template_name=ctx["template_name"]
                )
                ctx["report_ids"].append(str(branded.report_id))
                ctx["pdf_object_keys"].append(str(branded.file_path))
                control = await ctx["services"]["pdf_use_case"].execute(plan_id=plan_id)
                ctx["report_ids"].append(str(control.report_id))
                ctx["pdf_object_keys"].append(str(control.file_path))
                branded_bytes = await _read_pdf_bytes(str(branded.file_path))
                control_bytes = await _read_pdf_bytes(str(control.file_path))
                branded_reader = PdfReader(io.BytesIO(branded_bytes))
                base_fonts = [
                    str(font.get_object().get("/BaseFont", ""))
                    for page in branded_reader.pages
                    for font in page.get("/Resources", {}).get("/Font", {}).values()
                ]
                assert any("NotoSansSC" in name for name in base_fonts), f"品牌字体缺席: {base_fonts}"
                first = branded_reader.pages[0].get("/Resources", {})
                xobjects = first.get("/XObject", {})
                images = [obj for obj in xobjects.values() if obj.get_object().get("/Subtype") == "/Image"]
                assert images, "首页 Image XObject 缺席（logo）"

                def _page_bytes(page_reader: Any) -> bytes:
                    contents = page_reader.get_contents()
                    assert contents is not None, "页面内容流在位（渲染产物非空页）"
                    return bytes(contents.get_data())  # bytes() 收窄 pypdf Any 返回

                content = b"".join(_page_bytes(page) for page in branded_reader.pages)
                title_rgb = fp_str(0x1F / 255, 0x4E / 255, 0x79 / 255)  # corporate-blue #1F4E79
                header_rgb = fp_str(0xDC / 255, 0xE6 / 255, 0xF1 / 255)  # #DCE6F1
                assert title_rgb.encode("latin-1") in content and header_rgb.encode("latin-1") in content
                control_reader = PdfReader(io.BytesIO(control_bytes))
                for page in control_reader.pages:
                    control_xobjects = page.get("/Resources", {}).get("/XObject", {})
                    control_images = [obj for obj in control_xobjects.values() if obj.get_object().get("/Subtype") == "/Image"]
                    assert not control_images, "对照腿不应含图像"
                control_content = b"".join(_page_bytes(page) for page in control_reader.pages)
                assert title_rgb.encode("latin-1") not in control_content, "对照腿不应含品牌色"
            finally:
                await ctx["cleanup"]()
                await ctx["engine"].dispose()
        except Exception as error:
            if "不可用" in str(error):
                _pytest.skip(str(error))
            raise


class TestPerformanceDualSegment:
    """场景⑤：性能双段（保存 P95<200ms+导出 P95<60s——20 轮口径）。"""

    async def test_save_p95_under_200ms(self, tmp_path: Path) -> None:
        """保存 20 轮 P95（最重路径：全参含 logo 同名 UPSERT+L4 store 每轮）。"""
        import pytest as _pytest

        try:
            from src.domain.ports.resolver import resolve

            await _require_services()
            _clear_resolver_caches()
            engine = await _make_engine()
            try:
                logo_path = tmp_path / "perf-logo.png"
                _make_logo_png(logo_path)
                name = _unique_template_name()
                service = resolve("brand_template_service")
                durations: list[float] = []
                for _ in range(_WARMUP_ROUNDS + _SAMPLE_ROUNDS):
                    start = datetime.now(UTC)
                    saved = await service.save_brand_template(
                        name=name, color_scheme="corporate-blue", font_preset="stsong", logo_path=str(logo_path)
                    )
                    elapsed = (datetime.now(UTC) - start).total_seconds() * 1000
                    durations.append(elapsed)
                samples = sorted(durations[_WARMUP_ROUNDS:])
                p95 = samples[math.ceil(_P95_PERCENTILE * len(samples)) - 1]
                assert p95 < _SAVE_P95_LIMIT_MS, f"保存 P95 {p95:.1f}ms 超门禁 {_SAVE_P95_LIMIT_MS}ms（全量: {samples}）"
                await _teardown_assets(
                    engine,
                    plan_ids=[],
                    report_ids=[],
                    template_ids=[str(saved.template_id)],
                    logo_object_keys=[f"logos/{saved.template_id}"],
                    pdf_object_keys=[],
                )
            finally:
                await engine.dispose()
        except Exception as error:
            if "不可用" in str(error):
                _pytest.skip(str(error))
            raise

    async def test_export_p95_under_60s(self, tmp_path: Path) -> None:
        """导出 20 轮 P95（单一数据源品牌导出——6-5b 口径继承）。"""
        import pytest as _pytest

        try:
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import AsyncSession

            await _require_services()
            ctx = await _run_scenario(tmp_path)
            try:
                plan_id = ctx["plan_ids"][0]
                durations: list[float] = []
                for _ in range(_SAMPLE_ROUNDS):
                    start = datetime.now(UTC)
                    report = await ctx["services"]["pdf_use_case"].execute(
                        plan_id=plan_id, brand_template_name=ctx["template_name"]
                    )
                    durations.append((datetime.now(UTC) - start).total_seconds())
                    ctx["report_ids"].append(str(report.report_id))
                    ctx["pdf_object_keys"].append(str(report.file_path))
                samples = sorted(durations)
                p95 = samples[math.ceil(_P95_PERCENTILE * len(samples)) - 1]
                assert p95 < _EXPORT_P95_LIMIT_SECONDS, (
                    f"导出 P95 {p95:.1f}s 超门禁 {_EXPORT_P95_LIMIT_SECONDS}s（全量: {samples}）"
                )
                async with AsyncSession(ctx["engine"]) as session:
                    rows = await session.execute(
                        text("SELECT COUNT(*) FROM strategic_reports WHERE plan_id = CAST(:p AS uuid)"),
                        {"p": plan_id},
                    )
                    count = int(rows.scalar() or 0)
                    assert count == _SAMPLE_ROUNDS, f"L2 行数 {count} != {_SAMPLE_ROUNDS}"
            finally:
                await ctx["cleanup"]()
                await ctx["engine"].dispose()
        except Exception as error:
            if "不可用" in str(error):
                _pytest.skip(str(error))
            raise
