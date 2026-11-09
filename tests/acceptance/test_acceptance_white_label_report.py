"""白标报告基础验收 BDD 步骤实现（Story 6-11——14 场景 S1~S14）.

场景索引（docstring 斜杠形态——R6 纪律：S 编号禁泄入 Gherkin 场景名/绑定函数名）：
- S1 品牌模板保存主链 / S2 预设值域守卫（编程面直调） / S3 Logo 格式与路径守卫
- S4 列表空态与提示行 / S5 白标 PDF 导出主链 / S6 品牌元素结构化四件套
- S7 默认态回归 / S8 模板不存在守卫 / S9 参数组合守卫
- S10 顾问视图品牌段联动 / S11 保存性能采样 / S12 白标导出性能
- S13 同一模板跨 plan 复用 / S14 src 与四测试目录完成清单

性能三段口径差声明（AC-8——六连纪律第七连）：
- 保存 P95<200ms = save 服务面窗口（PG upsert+可选 L4 store；20 轮 sorted[ceil(0.95n)-1]
  数学口径——毫秒级上限参照 6-3/6-6 快照族而非 800ms 视图族）；
- 白标导出<1 分钟 = 6-5b 60s P95 既有口径承载（60s<1min 钦定关系——编程面 use case 直调
  采样，CLI bootstrap 秒级开销不混入计时窗口）；品牌渲染增量不构成风险面注记；
- 品牌应用准确率 100% = S6 结构化断言四件套承载（非计时口径——纯函数确定性）。

隔离策略（OD-13 四层防御）：
- pytestmark 挂 xdist_group("blm-planning-perf")——品牌模板写入方与 6-7~6-10 全部
  strategic_* 提交型写入方同 worker 串行（漏挂则与 6-10 S3 skip 门/6-7 归档面并行假红）；
- 模板名 TestTenant UUID 前缀（name UNIQUE 防撞+teardown 定位）；
- teardown 六步链顺序钦定：L4 对象（logo+WORM PDF）先行、PG 行后行（行清理 rowcount
  断言 assert-raise 中断不跳过对象清理——防孤儿泄漏）；brand_templates 行 rowcount 断言
  防静默 0 行假绿（6-10 :417-429 先例直系）；
- brand-assets 桶测试自愈建桶（bucket_exists 探测→make_bucket 勿带 object_lock——
  store 对缺桶抛 NoSuchBucket 且 src 零生产建桶；WORM 锁破坏 logo 覆盖与清理）；
- 模块级零本 Story 新词族 import（src 符号全部延迟到步骤函数内——模块级 import 收集期
  ImportError 全文件 ERROR 是 6-9 :55-68 教训第四连）；
- CLI 直调三清（clear_singleton+clear_scoped+clear_session）+禁二次 bootstrap；
- BLM 产物预置与导出副产物清理复刻 6-5b 验收（归档三面+report 行+outbox 行+WORM PDF
  bypass_governance 裸删）。
"""

import asyncio
import logging
import math
import uuid as uuid_module
from collections.abc import Awaitable, Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pytest_bdd import given, scenario, then, when

logger = logging.getLogger(__name__)

# marker 名以 pyproject 注册为准；xdist_group 与 6-7~6-10 blm-planning-perf 同组串行
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.database,
    pytest.mark.redis,
    pytest.mark.qdrant,
    pytest.mark.minio,
    pytest.mark.xdist_group("blm-planning-perf"),
]

_T = TypeVar("_T")

#: 仓库根（S14 交付件存在性断言）
_REPO_ROOT = Path(__file__).resolve().parents[2]

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

_BLM_TASK = "制定新能源汽车行业五年战略规划（白标报告验收真实链）"

#: 性能采样口径（20 轮 sorted[ceil(0.95n)-1] 数学口径——AC-8）
_SAMPLE_ROUNDS: int = 20
_WARMUP_ROUNDS: int = 2
_P95_PERCENTILE: float = 0.95
_SAVE_P95_LIMIT_MS: float = 200.0
_EXPORT_P95_LIMIT_SECONDS: float = 60.0

#: 品牌资产桶类型（L4 三段物理桶名第二段——组合根 resolve 通道 tenant 恒 default 共享桶）
_BRAND_BUCKET_TYPE: str = "brand-assets"

#: 归档桶类型镜像（WORM PDF 导出通道——6-5b 冻结常量对齐，断言期望独立字面双源漂移即红）
_EVIDENCE_BUCKET_TYPE: str = "archive-evidence"

#: S14 完成清单（src 新建 9 + 扩展 12 = 21 项 + migration 018 单独清单项
#: ——R5 勘误+R1 代码审查勘误补列 exception_handlers.py 口径）
_COMPLETION_SRC_FILES: dict[str, str] = {
    # 新建 9（domain 2 + application 4 + infrastructure 2 + 字体资产 1）
    "品牌模板实体": "src/domain/entities/brand_template.py",
    "品牌模板仓储端口": "src/domain/ports/brand_template_repository.py",
    "品牌模板应用端口与预设常量": "src/application/ports/brand_template.py",
    "品牌模板服务": "src/application/services/brand_template_service.py",
    "保存品牌模板用例": "src/application/use_cases/save_brand_template.py",
    "品牌模板清单用例": "src/application/use_cases/list_brand_templates.py",
    "品牌模板 ORM 模型": "src/infrastructure/storage/postgresql/models/brand_template.py",
    "品牌模板 PG 仓储": "src/infrastructure/storage/postgresql/repository/brand_template_repository.py",
    "Noto Sans SC 字体资产（OFL）": "src/infrastructure/reporting/fonts/NotoSansSC-VF.ttf",
    # 扩展 12（domain 异常 3 + application 5 + infrastructure 1 + interfaces 1 + entrypoints 1 + 组合根 1）
    # [R1 代码审查勘误：11→12——补列 exception_handlers.py（AC-7 HTTP_MAP 注册义务交付件）]
    "报告域异常扩展（494/495）": "src/domain/exceptions/report_exceptions.py",
    "异常码段注册扩展": "src/domain/exceptions/_code_ranges.py",
    "异常包导出扩展": "src/domain/exceptions/__init__.py",
    "PDF 渲染契约端口（BrandRenderSpec）": "src/application/ports/pdf_report.py",
    "PDF 报告生成服务 v1.1.0": "src/application/services/pdf_report_generation_service.py",
    "PDF 报告用例透传扩展": "src/application/use_cases/generate_pdf_report.py",
    "顾问视图端口 docstring 勘误": "src/application/ports/consultant_view.py",
    "顾问视图服务 v1.1.0": "src/application/services/consultant_view_service.py",
    "reportlab 渲染器品牌三件": "src/infrastructure/reporting/reportlab_pdf_renderer.py",
    "HTTP_MAP 494/495 注册": "src/interfaces/api/exception_handlers.py",
    "CLI 命令族扩展": "src/entrypoints/agent_cli.py",
    "组合根 4 新注册": "src/composition_root.py",
}

#: S14 migration 单独清单项（只增红线——已合入禁改）
_COMPLETION_MIGRATION_FILE: str = "deploy/postgresql/alembic/versions/018_brand_templates.py"

#: S14 完成清单（四测试目录：12 新建 + 9 扩展——含 6-10/6-5b 测试文件回归面
#: [R1 代码审查勘误：4→9——补列 5 个实交扩展文件]）
_COMPLETION_TEST_FILES: dict[str, str] = {
    "实体单测": "tests/unit/domain/entities/test_brand_template.py",
    "仓储单测（真实 PG）": "tests/unit/infrastructure/storage/test_brand_template_repository.py",
    "渲染器品牌单测": "tests/unit/infrastructure/reporting/test_reportlab_pdf_renderer_brand.py",
    "预设常量单测": "tests/unit/application/test_brand_template_presets.py",
    "品牌模板服务单测": "tests/unit/application/test_brand_template_service.py",
    "PDF 服务品牌段单测（扩展）": "tests/unit/application/test_pdf_report_generation_service.py",
    "保存用例单测": "tests/unit/application/use_cases/test_save_brand_template.py",
    "清单用例单测": "tests/unit/application/use_cases/test_list_brand_templates.py",
    "PDF 用例透传单测（6-5b 扩展）": "tests/unit/application/use_cases/test_generate_pdf_report_use_case.py",
    "CLI 单测（三命令段扩展）": "tests/unit/interfaces/cli/test_agent_cli.py",
    "顾问视图服务单测（6-10 回归）": "tests/unit/application/test_consultant_view_service.py",
    "渲染器默认态等价单测（6-5b carve out）": "tests/unit/infrastructure/reporting/test_reportlab_pdf_renderer.py",
    "异常八项族单测（扩展）": "tests/unit/domain/exceptions/test_report_exceptions.py",
    "HTTP_MAP expected 单测（扩展）": "tests/unit/interfaces/api/test_exception_handlers.py",
    "6-10 端口契约（版本拆分扩展）": "tests/contracts/test_port_contract_consultant_view.py",
    "架构四验证器": "tests/unit/architecture/test_white_label_report.py",
    "集成五场景": "tests/integration/test_integration_white_label_report.py",
    "端口契约测试": "tests/contracts/test_port_contract_white_label_report.py",
    "验收 feature": "tests/acceptance/test_acceptance_white_label_report.feature",
    "验收 BDD 步骤实现": "tests/acceptance/test_acceptance_white_label_report.py",
    "6-10 验收回归（skip 门）": "tests/acceptance/test_acceptance_consultant_view.py",
}


# ======================================================================
# 三件套（模块级 event_loop + _run_async + context dict——BDD 步骤禁
# @pytest.mark.asyncio，同循环驱动防 context 丢失）
# ======================================================================


def _run_async(event_loop: asyncio.AbstractEventLoop, awaitable: Awaitable[_T]) -> _T:
    """在模块级事件循环上运行可等待对象（BDD 步骤禁 @pytest.mark.asyncio）。

    Args:
        event_loop: 模块级事件循环。
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
    """驱逐 resolver SINGLETON/SCOPED 缓存（CLI 直调双清钦定——6-6 R3-1 证伪单清形态防线）。"""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()


def _clear_session_ctx() -> None:
    """清 ContextVar 会话（无参防御复位 API——预置与 CLI 直调前钦定）。"""
    from src.infrastructure.storage.postgresql.session_context import clear_session

    clear_session()


@pytest.fixture
def context(
    event_loop: asyncio.AbstractEventLoop,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> Generator[dict[str, Any], None, None]:
    """场景级上下文（预置登记 + CLI 直调产物位 + teardown 六步链——断言失败也清理）。"""
    _clear_resolver_caches()
    ctx: dict[str, Any] = {
        "_loop": event_loop,
        "_capsys_ref": capsys,
        "_tmp_path": tmp_path,
        "_pg_manager": None,
        "_assembled": False,
        # 清理登记面（调用服务之前预登记——teardown 定向清理锚）
        "_plan_ids": [],
        "_report_ids": [],
        "_pdf_object_keys": [],
        "_archive_cleanup_needed": False,
        "_brand_template_ids": [],
        "_logo_object_keys": [],
        # 产物位
        "logo_path": None,
        "preset": {},
        "views": [],
        "durations": [],
        "cli_exit_code": None,
        "cli_stdout": "",
        "cli_stderr": "",
    }
    yield ctx
    _teardown_chain(ctx)
    _clear_resolver_caches()


# ======================================================================
# teardown 六步链（L4 对象先行 PG 行后行钦定——rowcount 断言殿后防孤儿；
# 各步独立 try/except 残局防线，全部同循环执行）
# ======================================================================


def _teardown_chain(ctx: dict[str, Any]) -> None:
    """teardown 六步链（logo 对象→WORM PDF→归档三面→report 行→outbox 行→brand 行）。

    顺序钦定（R2-P3）：L4 对象清理先行、PG 行清理后行——brand 行 rowcount 断言
    assert-raise 中断时对象清理已完成（防孤儿泄漏）；各步独立 try/except 不阻断。
    """
    steps: list[tuple[str, Any]] = [
        ("logo 对象清理", _cleanup_logo_objects(ctx)),
        ("WORM PDF 对象清理", _cleanup_pdf_objects(ctx)),
        ("归档三面清理", _cleanup_archive_residues(ctx)),
        ("报告行清理", _cleanup_report_rows(ctx)),
        ("outbox 行清理", _cleanup_outbox_rows(ctx)),
        ("品牌模板行清理", _cleanup_brand_rows(ctx)),
    ]
    for name, coro in steps:
        try:
            _run_async(ctx["_loop"], coro)
        except Exception as exc:
            logger.error("teardown %s 失败（残局防线不阻断）: %s", name, exc, exc_info=exc)


def _make_pg_manager() -> Any:
    """构建独立 PostgreSQLManager（teardown/清理专用——不复用场景会话）。"""
    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
    from tests.environments import get_test_env

    env = get_test_env()
    return PostgreSQLManager(
        PostgreSQLConfig(
            host=env.postgres.host,
            port=env.postgres.port,
            database=env.postgres.database,
            username=env.postgres.username,
            password=env.postgres.password,
        )
    )


def _env() -> Any:
    """测试环境配置单源（模块内复用——tests.environments 直系）。"""
    from tests.environments import get_test_env

    return get_test_env()


def _minio_client() -> Any:
    """裸 MinIO client（teardown 清理专用——bypass_governance 通道前提）。"""
    from minio import Minio

    env = _env()
    return Minio(
        endpoint=env.minio.endpoint,
        access_key=env.minio.access_key,
        secret_key=env.minio.secret_key,
        secure=env.minio.secure,
    )


def _resolve_bucket_name(bucket_type: str) -> str:
    """经组合根 l4_object 仓储解析物理桶名（零硬编码——6-5b 形态直系）。"""
    from src.domain.ports.resolver import get_resolver

    l4 = get_resolver().resolve("l4_object")
    return str(l4._repository._resolve_bucket_name(bucket_type))


async def _cleanup_logo_objects(ctx: dict[str, Any]) -> None:
    """brand-assets 桶 logo 对象定向删（对象键锚 template_id——非 WORM 桶直接删）。"""
    if not ctx["_logo_object_keys"]:
        return
    from minio.deleteobjects import DeleteObject

    def _remove() -> None:
        client = _minio_client()
        errors = client.remove_objects(
            _resolve_bucket_name(_BRAND_BUCKET_TYPE),
            [DeleteObject(key) for key in ctx["_logo_object_keys"]],
        )
        for _ in errors:
            pass

    await asyncio.to_thread(_remove)


async def _cleanup_pdf_objects(ctx: dict[str, Any]) -> None:
    """archive-evidence 桶 WORM PDF 对象 bypass 定向删（端口 delete 对锁定对象抛
    ComplianceLockError——裸 client remove_objects(bypass_governance_mode=True)
    是 6-5b `_cleanup_pdf_objects` 直系）。"""
    if not ctx["_pdf_object_keys"]:
        return
    from minio.deleteobjects import DeleteObject

    def _remove() -> None:
        client = _minio_client()
        errors = client.remove_objects(
            _resolve_bucket_name(_EVIDENCE_BUCKET_TYPE),
            [DeleteObject(key) for key in ctx["_pdf_object_keys"]],
            bypass_governance_mode=True,
        )
        for _ in errors:
            pass

    await asyncio.to_thread(_remove)


async def _cleanup_archive_residues(ctx: dict[str, Any]) -> None:
    """BLM 预置归档三面清理（PG 档案行 / Qdrant 点 / MinIO WORM 归档 blob——6-5b 直系）。"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    env = _env()
    manager = _make_pg_manager()
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
        if archive_ids:
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
            if blob_refs:
                try:
                    from minio.deleteobjects import DeleteObject

                    def _remove_minio() -> None:
                        client = _minio_client()
                        errors = client.remove_objects(
                            _resolve_bucket_name(_EVIDENCE_BUCKET_TYPE),
                            [DeleteObject(blob_ref) for blob_ref in blob_refs],
                            bypass_governance_mode=True,
                        )
                        for _ in errors:
                            pass

                    await asyncio.to_thread(_remove_minio)
                except Exception:
                    pass
            async with AsyncSession(manager.get_async_engine()) as session:
                await session.execute(
                    text("DELETE FROM strategic_archives WHERE archive_id = ANY(:ids)"),
                    {"ids": archive_ids},
                )
                await session.commit()
    finally:
        await manager.get_async_engine().dispose()


async def _cleanup_report_rows(ctx: dict[str, Any]) -> None:
    """L2 strategic_reports 行精确 DELETE（report_id 面 + plan_id 兜底——6-5b 直系）。"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    manager = _make_pg_manager()
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


async def _cleanup_outbox_rows(ctx: dict[str, Any]) -> None:
    """outbox 事件行精确 DELETE（plan_id/report_id 双 JSONB 通道——6-5b 直系）。"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    manager = _make_pg_manager()
    try:
        async with AsyncSession(manager.get_async_engine()) as session:
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


async def _cleanup_brand_rows(ctx: dict[str, Any]) -> None:
    """brand_templates 行定向 DELETE + rowcount 断言（防静默 0 行假绿——6-10 :417-429 直系）。

    rowcount 断言殿后（六步链末位）：AssertionError 中断时全部对象清理已完成。
    红阶段（018 migration 未建）表不存在——teardown 容错跳过（异常交由链级 logger.error）。
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    if not ctx["_brand_template_ids"]:
        return
    manager = _make_pg_manager()
    try:
        async with AsyncSession(manager.get_async_engine()) as session:
            from sqlalchemy import CursorResult

            result = await session.execute(
                text("DELETE FROM brand_templates WHERE template_id = ANY(:ids)"),
                {"ids": [str(tid) for tid in ctx["_brand_template_ids"]]},
            )
            assert isinstance(result, CursorResult), "DML 语句返回 CursorResult（rowcount 类型收窄）"
            expected = len(ctx["_brand_template_ids"])
            assert result.rowcount == expected, (
                f"brand_templates DELETE 行数 {result.rowcount} != 预置 {expected}（静默 0 行假绿防线）"
            )
            await session.commit()
    finally:
        await manager.get_async_engine().dispose()


# ======================================================================
# 服务探测与桶自愈（背景 given——探测失败动态 skip）
# ======================================================================


async def _require_services_async(ctx: dict[str, Any]) -> None:
    """四服务探测（PG/Redis/Qdrant/MinIO）+ 双桶自愈（brand-assets 无锁+archive-evidence WORM）。

    brand-assets 桶自愈（make_bucket 勿带 object_lock）：store 对缺桶抛 NoSuchBucket
    且 src 零生产建桶——测试前置自愈是 6-5b 验收探测+自愈先例直系；WORM 锁破坏
    logo 覆盖与 teardown 清理（与 archive-evidence 的 object_lock=True 建桶分立）。
    """
    import pytest as _pytest
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.domain.ports.registry import _global_registry

    if _global_registry.get("agent_workflow_use_case") is None:
        from src.composition_root import bootstrap

        bootstrap()
    env = _env()
    # PostgreSQL 探测（四表预检——brand_templates 不入探测：018 migration 归 Task 2，
    # 红阶段表缺席是预期态而非服务不可用）
    pg_manager = _make_pg_manager()
    try:
        async with AsyncSession(pg_manager.get_async_engine()) as session:
            await session.execute(text("SELECT 1 FROM event_outbox LIMIT 1"))
            await session.execute(text("SELECT 1 FROM strategic_archives LIMIT 1"))
            await session.execute(text("SELECT 1 FROM strategic_reports LIMIT 1"))
            await session.execute(text("SELECT 1 FROM documents LIMIT 1"))
    except Exception as exc:
        await pg_manager.get_async_engine().dispose()
        _pytest.skip(f"PostgreSQL 不可用: {exc}")
    # Redis 探测（导出链 event_publisher realtime 通道——维持四件门控口径）
    import redis.asyncio as aioredis

    redis_client = aioredis.Redis(host=env.redis.host, port=env.redis.port, decode_responses=False)
    try:
        await redis_client.ping()
    except Exception as exc:
        await redis_client.close()
        await pg_manager.get_async_engine().dispose()
        _pytest.skip(f"Redis 不可用: {exc}")
    # Qdrant 探测（轻量 HTTP /collections——BLM 预置归档链真实点写入）
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
    # MinIO 探测 + 双桶自愈
    try:
        await asyncio.to_thread(_ensure_brand_bucket)
        await asyncio.to_thread(_ensure_worm_bucket)
    except Exception as exc:
        await redis_client.close()
        await pg_manager.get_async_engine().dispose()
        _pytest.skip(f"MinIO 不可用: {exc}")
    await redis_client.close()
    ctx["_pg_manager"] = pg_manager


def _ensure_brand_bucket() -> None:
    """brand-assets 桶自愈（探测→make_bucket 勿带 object_lock——OD-3⑦ 钦定）。"""
    client = _minio_client()
    bucket_name = _resolve_bucket_name(_BRAND_BUCKET_TYPE)
    if not client.bucket_exists(bucket_name):
        try:
            # 勿带 object_lock：logo 需可替换覆盖与 teardown 清理——WORM 反语义
            client.make_bucket(bucket_name)
        except Exception:
            if not client.bucket_exists(bucket_name):
                raise


def _ensure_worm_bucket() -> None:
    """archive-evidence WORM 桶自愈（缺桶建带锁桶——6-5b :533-566 形态，白标导出沿用）。"""
    from minio.deleteobjects import DeleteObject

    client = _minio_client()
    bucket_name = _resolve_bucket_name(_EVIDENCE_BUCKET_TYPE)
    if not client.bucket_exists(bucket_name):
        try:
            client.make_bucket(bucket_name, object_lock=True)
        except Exception:
            if not client.bucket_exists(bucket_name):
                raise
        return
    try:
        client.get_object_lock_config(bucket_name)
    except Exception:
        try:
            versions = [
                DeleteObject(obj.object_name, version_id=obj.version_id)
                for obj in client.list_objects(bucket_name, recursive=True, include_version=True)
            ]
            _ = list(client.remove_objects(bucket_name, versions, bypass_governance_mode=True))
            client.remove_bucket(bucket_name)
            client.make_bucket(bucket_name, object_lock=True)
        except Exception:
            pass


# ======================================================================
# 预置 helper（时间锚/Logo 资产/模板行直写/BLM 八阶段归档——R2-B-2 显式 updated_at 义务）
# ======================================================================


def _preset_anchor() -> tuple[datetime, Any]:
    """预置时间基准锚（单一 now+微秒偏移——6-10 :281-293 直系）.

    直写通道绕过服务定时戳而 PG now() 是事务开始时间（同事务恒值）——隐式构造
    致多行预置 updated_at 全同、列表排序退化 tie-break（R2-B-2 裁定）；单基准
    微秒偏移保证主排序键可区分。
    """
    base = datetime.now(UTC)

    def _at(microseconds: int) -> datetime:
        return base + timedelta(microseconds=microseconds)

    return base, _at


def _make_logo_png(path: Path) -> None:
    """Pillow 生成最小合法 PNG（渲染正例——仓内既有 PNG 测试字节是截断假体：magic
    8 字节可过守卫但 ImageReader 渲染 492；Pillow 已是项目依赖零新依赖）。"""
    from PIL import Image

    img = Image.new("RGB", (64, 64), color=(31, 78, 121))
    img.save(path, format="PNG")


def _unique_template_name() -> str:
    """TestTenant UUID 前缀模板名（name UNIQUE 防撞+teardown 定位——OD-13①）。"""
    return f"test-{uuid_module.uuid4().hex[:8]}-品牌模板"


async def _upload_logo(ctx: dict[str, Any], template_id: Any, logo_path: Path) -> str:
    """logo 对象上传（L4 store 通道——对象键锚 template_id 单键覆盖）。"""
    from src.domain.ports.resolver import resolve

    object_key = f"logos/{template_id}"
    await resolve("l4_object").store(
        bucket_type=_BRAND_BUCKET_TYPE,
        object_key=object_key,
        file_path=str(logo_path),
        content_type="image/png",
    )
    if object_key not in ctx["_logo_object_keys"]:
        ctx["_logo_object_keys"].append(object_key)
    return object_key


async def _save_brand_template_row(
    ctx: dict[str, Any],
    *,
    name: str,
    color_scheme: str,
    font_preset: str,
    logo_object_key: str | None,
    updated_at: datetime,
) -> str:
    """品牌模板行直写（BrandTemplate 实体直构造+brand_template_repository.save——
    6-10 `_save_archive_row` 直写通道直系）.

    红锚：src.domain.entities.brand_template 模块缺失 → ImportError（Task 0 红阶段
    钦定形态——含预置的场景统一由本 helper 首行延迟 import 触发）。
    """
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
        created_at=updated_at - timedelta(microseconds=1),
        updated_at=updated_at,
    )
    await resolve("brand_template_repository").save(entity)
    ctx["_brand_template_ids"].append(str(template_id))
    return str(template_id)


def _assemble_archive_only(ctx: dict[str, Any]) -> None:
    """轻装配（逐 stage 归档通道 + PDF 主链挂接——无 LLM run；6-5b :600-679 直系）.

    绿形态（v1.1.0）：PDF 主链十依赖（增 brand_template_service 第十依赖——
    R3 裁定 lambda 9 参→10 参）。红锚注记：含模板预置的场景由 `_save_brand_template_row`
    的 ImportError 先触发（Given 内先模板后装配钦定序）。
    """
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
    ctx["chain_archive_service"] = ChainOfThoughtArchiveService(
        archive_service=archive_service,
        object_storage=resolve("l4_object"),
    )
    from typing import cast

    from src.domain.ports.document_repository import DocumentRepositoryPort

    ctx["pdf_report_service"] = PdfReportGenerationService(
        chain_archive_service=ctx["chain_archive_service"],
        snapshot_repository=resolve("snapshot_repository"),
        report_repository=resolve("report_repository"),
        event_publisher=resolve("event_publisher"),
        pdf_renderer=resolve("pdf_renderer"),
        l4_object=resolve("l4_object"),
        l3_vector=resolve("l3_vector"),
        document_repository=cast(
            DocumentRepositoryPort,
            _SessionScopedFind(
                resolve("document_repository"),
                async_sessionmaker(ctx["_pg_manager"].get_async_engine()),
            ),
        ),
        archive_service=resolve("strategic_archive_service"),
        brand_template_service=resolve("brand_template_service"),
    )
    ctx["pdf_use_case"] = GeneratePdfReportUseCase(report_service=ctx["pdf_report_service"])
    ctx["_assembled"] = True


def _make_fake_embedding() -> Any:
    """Fake Embedding 工厂（外部 SaaS 豁免——固定 1024 维，6-4/6-5a/6-5b 同款）。"""
    from unittest.mock import AsyncMock

    from src.domain.ports.embedding_service import EmbeddingServicePort

    fake = AsyncMock(spec=EmbeddingServicePort)
    fake.embed_query = AsyncMock(return_value=[0.1] * 1024)
    fake.embed_documents = AsyncMock(return_value=[[0.1] * 1024])
    fake.close = AsyncMock()
    return fake


def _make_material(stage: str, *, index: int = 0) -> Any:
    """构造归档素材（stage 判型三态分派——6-5b 同款）。"""
    from src.application.ports.chain_of_thought_archive import StepChainMaterial

    is_synthesis = stage == "market_insight_synthesis"
    is_gap = stage == "performance_gap"
    payload: dict[str, Any]
    if is_synthesis:
        payload = {"conclusions": ["综合结论一（白标品牌聚焦核心市场）"], "degraded_inputs": ["market_insight_trend"]}
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


async def _archive_steps(ctx: dict[str, Any], plan_id: str) -> list[Any]:
    """逐 stage 组装归档（八阶段循环——session_context 独立会话承载；6-5b 直系）。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.infrastructure.storage.postgresql.session_context import session_context

    factory = async_sessionmaker(ctx["_pg_manager"].get_async_engine())
    records = []
    async with session_context(factory):
        for index, stage in enumerate(_EXPECTED_STAGE_ORDER):
            record = await ctx["chain_archive_service"].compose_and_archive_step_chain(
                uuid_module.UUID(plan_id), stage, _make_material(stage, index=index)
            )
            records.append(record)
    return records


async def _preset_blm_with_template(
    ctx: dict[str, Any],
    *,
    plan_count: int = 1,
    font_preset: str = "noto-sans-sc",
    with_logo: bool = True,
) -> dict[str, Any]:
    """组合预置（模板行先行[红锚 ImportError]→BLM 八阶段归档→轻装配）.

    返回预置形态登记（template_id/template_name/plan_ids/logo_object_key）。
    """
    template_name = _unique_template_name()
    _, _at = _preset_anchor()
    logo_object_key = None
    if with_logo:
        logo_path = ctx["_tmp_path"] / f"logo-{uuid_module.uuid4().hex[:8]}.png"
        _make_logo_png(logo_path)
        ctx["logo_path"] = logo_path
    template_id = await _save_brand_template_row(
        ctx,
        name=template_name,
        color_scheme="corporate-blue",
        font_preset=font_preset,
        logo_object_key=None,  # 占位——logo 对象上传后回填由服务链承载（预置直写形态：键直书）
        updated_at=_at(1000),
    )
    if with_logo:
        logo_object_key = await _upload_logo(ctx, template_id, ctx["logo_path"])
        # 预置行 logo_object_key 回填（直写通道二段：上传后 UPDATE 行——预置归服务外的测试装配面）
        from sqlalchemy import text as sa_text
        from sqlalchemy.ext.asyncio import AsyncSession

        manager = _make_pg_manager()
        try:
            async with AsyncSession(manager.get_async_engine()) as session:
                await session.execute(
                    sa_text("UPDATE brand_templates SET logo_object_key = :k WHERE template_id = :tid"),
                    {"k": logo_object_key, "tid": template_id},
                )
                await session.commit()
        finally:
            await manager.get_async_engine().dispose()
    plan_ids: list[str] = []
    _assemble_archive_only(ctx)
    for _ in range(plan_count):
        plan_id = str(uuid_module.uuid4())
        await _archive_steps(ctx, plan_id)
        ctx["_plan_ids"].append(plan_id)
        plan_ids.append(plan_id)
    preset = {
        "template_id": template_id,
        "template_name": template_name,
        "plan_ids": plan_ids,
        "logo_object_key": logo_object_key,
        "font_preset": font_preset,
    }
    ctx["preset"] = preset
    return preset


# ======================================================================
# CLI 直调 helper（三清+main(argv)+SystemExit 捕获——6-10 :457-476 直系；
# 红阶段命令未注册/参数未注册 → argparse exit 2 → SystemExit 捕获 →
# exit_code 断言 AssertionError 是 Task 0.6 符号表钦定红形态）
# ======================================================================


def _run_cli(context: dict[str, Any], argv: list[str]) -> None:
    """CLI in-process 直调（三清钦定——clear_session 是 asyncio.run 新循环硬前置：
    继承 fixture session 会触发 Future attached to a different loop）。"""
    from src.entrypoints import agent_cli

    _clear_session_ctx()
    _clear_resolver_caches()
    exit_code = 0
    try:
        exit_code = agent_cli.main(argv)
    except SystemExit as error:  # 红阶段命令/参数未注册 → argparse exit 2
        exit_code = int(error.code or 0)
    captured = context["_capsys_ref"].readouterr()
    _clear_resolver_caches()
    context["cli_exit_code"] = exit_code
    context["cli_stdout"] = captured.out
    context["cli_stderr"] = captured.err


# ======================================================================
# 场景绑定（@scenario——14 场景）
# ======================================================================


@scenario("test_acceptance_white_label_report.feature", "品牌模板保存主链（全参含 Logo）")
def test_save_master_chain() -> None:
    """S1：保存主链（CLI 全参含 logo → PG 行七字段+L4 对象逐字节）。"""


@scenario("test_acceptance_white_label_report.feature", "预设值域守卫（编程面直调）")
def test_preset_value_domain_guard() -> None:
    """S2：值域守卫（编程面 use case 直调——CLI choices 是 exit 2 硬拦截不可经 CLI 触达）。"""


@scenario("test_acceptance_white_label_report.feature", "Logo 格式与路径守卫")
def test_logo_format_guard() -> None:
    """S3：magic bytes/大小/路径三负例（494 stderr exit 1）。"""


@scenario("test_acceptance_white_label_report.feature", "列表空态与提示行")
def test_list_empty_state() -> None:
    """S4：空态输出（前置零行清点有行 skip——背景行防御）。"""


@scenario("test_acceptance_white_label_report.feature", "白标 PDF 导出主链")
def test_white_label_export_master_chain() -> None:
    """S5：白标导出主链（六段编排+品牌增量三段）。"""


@scenario("test_acceptance_white_label_report.feature", "品牌元素结构化四件套")
def test_brand_accuracy_four_pieces() -> None:
    """S6：100% 准确=结构化四件套（字体/XObject/色/传递链——非计时口径）。"""


@scenario("test_acceptance_white_label_report.feature", "默认态回归（无品牌导出零破坏）")
def test_default_state_regression() -> None:
    """S7：默认态回归（库有模板但未指定品牌导出=零品牌键+通道不变）。"""


@scenario("test_acceptance_white_label_report.feature", "模板不存在守卫")
def test_template_not_found_guard() -> None:
    """S8：ghost 模板名 → 494（get_render_spec 前置于聚合查询——免 BLM 预置直达）。"""


@scenario("test_acceptance_white_label_report.feature", "参数组合守卫（品牌仅支持 PDF 面）")
def test_combination_guard() -> None:
    """S9：--brand-template+--format markdown → 494（post-parse 守卫位 bootstrap 前）。"""


@scenario("test_acceptance_white_label_report.feature", "顾问视图品牌段联动")
def test_consultant_view_brand_linkage() -> None:
    """S10：consultant_view v1.1.0 读配置（configured True+呈现名直推）。"""


@scenario("test_acceptance_white_label_report.feature", "保存性能采样 20 轮 P95")
def test_save_performance() -> None:
    """S11：保存 P95<200ms（全参含 logo 最重路径——服务面窗口）。"""


@scenario("test_acceptance_white_label_report.feature", "白标导出性能 20 轮 P95")
def test_export_performance() -> None:
    """S12：导出 P95<60s（6-5b 口径继承——编程面直调免 bootstrap 开销混入）。"""


@scenario("test_acceptance_white_label_report.feature", "同一模板跨 plan 复用导出")
def test_cross_plan_reuse() -> None:
    """S13：模板不锚定 plan（同一模板两 plan 导出同 brand_template_id）。"""


@scenario("test_acceptance_white_label_report.feature", "src 与四测试目录完成清单")
def test_completion_checklist() -> None:
    """S14：交付件存在性收尾（20 src+migration+16 测试文件）。"""


# ======================================================================
# 背景
# ======================================================================


@given("白标报告基础依赖服务可用")
def require_services(context: dict[str, Any]) -> None:
    """四服务探测+双桶自愈（PG/Redis/Qdrant/MinIO——失败动态 skip）。"""
    _run_async(context["_loop"], _require_services_async(context))


# ======================================================================
# AC-1 + AC-2: 保存主链/值域守卫/Logo 格式守卫（S1/S2/S3）
# ======================================================================


@given("顾问持有合法 Logo 图片文件")
def given_valid_logo(context: dict[str, Any]) -> None:
    """合法 Logo 预置（Pillow 生成最小合法 PNG——可解码性是渲染正例前提）。"""
    logo_path = context["_tmp_path"] / f"logo-{uuid_module.uuid4().hex[:8]}.png"
    _make_logo_png(logo_path)
    context["logo_path"] = logo_path


@given("品牌模板服务可用")
def given_brand_service_available(context: dict[str, Any]) -> None:
    """品牌模板服务可用（编程面前置——延迟 import 预设常量触发红锚 ImportError）。"""
    from src.application.ports.brand_template import COLOR_SCHEME_PRESETS, FONT_PRESETS

    context["preset"]["color_keys"] = set(COLOR_SCHEME_PRESETS)
    context["preset"]["font_keys"] = set(FONT_PRESETS)


@given("顾问持有非法 Logo 文件（文本内容）")
def given_text_logo(context: dict[str, Any]) -> None:
    """magic 负例预置（文本内容——非 PNG/JPEG magic bytes）。"""
    logo_path = context["_tmp_path"] / f"fake-{uuid_module.uuid4().hex[:8]}.txt"
    logo_path.write_bytes("this is not an image, just plain text bytes".encode("utf-8"))
    context["logo_path"] = logo_path


@given("品牌模板表零行（有背景行则跳过）")
def given_empty_brand_table(context: dict[str, Any]) -> None:
    """空态前置（零行清点——有背景行 pytest.skip：共享库残留防御；表不存在容错跳过：
    红阶段 018 未建是预期态，红锚由 When 的 argparse exit 2 主导——Task 0.6 符号表）。"""
    from sqlalchemy import text as sa_text
    from sqlalchemy.ext.asyncio import AsyncSession

    manager = _make_pg_manager()

    async def _check() -> None:
        try:
            async with AsyncSession(manager.get_async_engine()) as session:
                exists = await session.execute(
                    sa_text("SELECT 1 FROM information_schema.tables WHERE table_name = 'brand_templates'")
                )
                if exists.scalar() is None:
                    return
                rows = await session.execute(sa_text("SELECT COUNT(*) FROM brand_templates"))
                count = int(rows.scalar() or 0)
                if count > 0:
                    pytest.skip(f"品牌模板表存在 {count} 行背景残留——空态断言免疫跳过")
        finally:
            await manager.get_async_engine().dispose()

    _run_async(context["_loop"], _check())


@when("CLI 直调 brand-template-save（全参含 logo）")
def when_cli_brand_save_full(context: dict[str, Any]) -> None:
    """CLI 保存全参（TestTenant 前缀名+三预设键+logo 路径）。"""
    name = _unique_template_name()
    context["preset"]["name"] = name
    _run_cli(
        context,
        [
            "brand-template-save",
            "--name",
            name,
            "--color-scheme",
            "corporate-blue",
            "--font-preset",
            "noto-sans-sc",
            "--logo-path",
            str(context["logo_path"]),
        ],
    )


@when("编程面直调保存用例（非法配色键与非法字体键两形态）")
def when_usecase_invalid_presets(context: dict[str, Any]) -> None:
    """编程面两形态直调（非法 color key/非法 font key → 494——argparse choices
    是 exit 2 硬拦截，值域 494 仅编程面可达——AC-7 口径）。"""
    from src.domain.ports.resolver import resolve

    use_case = resolve("save_brand_template_use_case")
    errors: list[Any] = []
    for kwargs in (
        {"color_scheme": "neon-pink-not-exist", "font_preset": "stsong"},
        {"color_scheme": "corporate-blue", "font_preset": "comic-sans-not-exist"},
    ):
        try:
            _run_async(
                context["_loop"],
                use_case.execute(
                    name=_unique_template_name(),
                    **kwargs,
                ),
            )
        except Exception as error:
            errors.append(error)
    context["preset"]["value_domain_errors"] = errors


@when("CLI 直调 brand-template-save（logo 为文本文件）")
def when_cli_brand_save_text_logo(context: dict[str, Any]) -> None:
    """magic 负例直调（文本文件 → 494；服务层校验先于 L4 调用）。"""
    name = _unique_template_name()
    context["preset"]["name"] = name
    _run_cli(
        context,
        [
            "brand-template-save",
            "--name",
            name,
            "--color-scheme",
            "corporate-blue",
            "--font-preset",
            "stsong",
            "--logo-path",
            str(context["logo_path"]),
        ],
    )


@then("保存成功输出与模板标识行在 stdout 且 exit code 为 0")
def then_save_success_output(context: dict[str, Any]) -> None:
    """保存成功呈现（输出契约：保存行+配置行+模板标识行）。"""
    assert context["cli_exit_code"] == 0, f"exit={context['cli_exit_code']} stderr={context['cli_stderr']}"
    assert f"品牌模板已保存: {context['preset']['name']}" in context["cli_stdout"]
    assert "模板标识: " in context["cli_stdout"]


@then("PG 行七字段值级读回一致且均非空")
def then_pg_row_seven_fields(context: dict[str, Any]) -> None:
    """PG 行直查七字段（template_id/name/color_scheme/font_preset/logo_object_key/
    created_at/updated_at——独立连接回查，双源漂移即红）。"""
    from sqlalchemy import text as sa_text
    from sqlalchemy.ext.asyncio import AsyncSession

    manager = _make_pg_manager()

    async def _fetch() -> dict[str, Any]:
        try:
            async with AsyncSession(manager.get_async_engine()) as session:
                rows = await session.execute(
                    sa_text(
                        "SELECT template_id, name, color_scheme, font_preset, logo_object_key, "
                        "created_at, updated_at FROM brand_templates WHERE name = :n"
                    ),
                    {"n": context["preset"]["name"]},
                )
                row = rows.one()
                return {
                    "template_id": row[0],
                    "name": row[1],
                    "color_scheme": row[2],
                    "font_preset": row[3],
                    "logo_object_key": row[4],
                    "created_at": row[5],
                    "updated_at": row[6],
                }
        finally:
            await manager.get_async_engine().dispose()

    record = _run_async(context["_loop"], _fetch())
    assert record["name"] == context["preset"]["name"]
    assert record["color_scheme"] == "corporate-blue"
    assert record["font_preset"] == "noto-sans-sc"
    assert record["logo_object_key"] == f"logos/{record['template_id']}"
    assert record["created_at"] is not None and record["updated_at"] is not None
    context["preset"]["template_id"] = str(record["template_id"])
    context["preset"]["logo_object_key"] = str(record["logo_object_key"])
    context["_brand_template_ids"].append(str(record["template_id"]))
    context["_logo_object_keys"].append(str(record["logo_object_key"]))


@then("L4 logo 对象读回与源文件逐字节相等")
def then_logo_roundtrip(context: dict[str, Any]) -> None:
    """L4 读回逐字节对照（retrieve 异步迭代聚合——生产通道单源）。"""
    from src.domain.ports.resolver import resolve

    async def _read() -> bytes:
        chunks: list[bytes] = []
        async for chunk in resolve("l4_object").retrieve(
            bucket_type=_BRAND_BUCKET_TYPE, object_key=context["preset"]["logo_object_key"]
        ):
            chunks.append(chunk)
        return b"".join(chunks)

    fetched = _run_async(context["_loop"], _read())
    source = Path(context["logo_path"]).read_bytes()
    assert fetched == source, f"L4 读回 {len(fetched)}B != 源 {len(source)}B（逐字节对照失败）"


@then("两形态均抛出 BrandTemplateValidationError（EXCEPTION_494）")
def then_value_domain_494(context: dict[str, Any]) -> None:
    """两形态 494 断言（code 值级——DomainError.code 字面）。"""
    errors = context["preset"]["value_domain_errors"]
    assert len(errors) == 2, f"应有 2 个异常，实得 {len(errors)}"
    for error in errors:
        assert type(error).__name__ == "BrandTemplateValidationError", f"异常类型漂移: {type(error).__name__}"
        assert getattr(error, "code", None) == "EXCEPTION_494", f"code 漂移: {getattr(error, 'code', None)}"


@then("stderr 呈现 EXCEPTION_494 且 exit code 为 1")
def then_stderr_494_exit_1(context: dict[str, Any]) -> None:
    """494 stderr 呈现（`[EXCEPTION_494]` 前缀格式+exit 1——CLI 异常呈现五步定式）。"""
    assert context["cli_exit_code"] == 1, f"exit={context['cli_exit_code']}"
    assert "[EXCEPTION_494]" in context["cli_stderr"], f"stderr={context['cli_stderr']!r}"


@then("超限与路径不存在负例同样呈现 494")
def then_oversize_and_missing_path_494(context: dict[str, Any]) -> None:
    """大小上限/路径不存在两负例（>2MB 带 PNG magic 头构造——magic 先过后撞上限；
    路径不存在是文件不可读伞形）。"""
    # 超限文件（PNG magic + 3MB 载荷——过 magic 检查后撞大小上限）
    oversize = context["_tmp_path"] / f"big-{uuid_module.uuid4().hex[:8]}.png"
    oversize.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * (3 * 1024 * 1024))
    _run_cli(
        context,
        [
            "brand-template-save",
            "--name",
            _unique_template_name(),
            "--color-scheme",
            "corporate-blue",
            "--font-preset",
            "stsong",
            "--logo-path",
            str(oversize),
        ],
    )
    assert context["cli_exit_code"] == 1 and "[EXCEPTION_494]" in context["cli_stderr"], (
        f"超限负例失败: exit={context['cli_exit_code']} stderr={context['cli_stderr']!r}"
    )
    # 路径不存在
    _run_cli(
        context,
        [
            "brand-template-save",
            "--name",
            _unique_template_name(),
            "--color-scheme",
            "corporate-blue",
            "--font-preset",
            "stsong",
            "--logo-path",
            f"/nonexistent-path-{uuid_module.uuid4().hex[:6]}/logo.png",
        ],
    )
    assert context["cli_exit_code"] == 1 and "[EXCEPTION_494]" in context["cli_stderr"], (
        f"路径不存在负例失败: exit={context['cli_exit_code']} stderr={context['cli_stderr']!r}"
    )


# ======================================================================
# AC-3: 列表空态/模板不存在/组合守卫/跨 plan 复用（S4/S8/S9/S13）
# ======================================================================


@when("CLI 直调 brand-template-list")
def when_cli_brand_list(context: dict[str, Any]) -> None:
    """零参数全局清单直调。"""
    _run_cli(context, ["brand-template-list"])


@then("空态计数行与保存提示行在位且 exit code 为 0")
def then_empty_list_output(context: dict[str, Any]) -> None:
    """空态输出（首行计数+零行+恒在提示行——指向 brand-template-save）。"""
    assert context["cli_exit_code"] == 0, f"exit={context['cli_exit_code']} stderr={context['cli_stderr']}"
    assert "品牌模板: 共 0 个" in context["cli_stdout"]
    assert "提示: 执行 brand-template-save 配置品牌模板" in context["cli_stdout"]
    # 计数行后无模板行（空态——逐行校验）
    lines = [line for line in context["cli_stdout"].splitlines() if line.strip()]
    after_count = lines[lines.index("品牌模板: 共 0 个") + 1 :]
    assert all(line.startswith("提示:") for line in after_count), f"空态后不应有模板行: {after_count}"


@when("CLI 直调 report-generate（--brand-template 不存在的模板名）")
def when_cli_generate_ghost_template(context: dict[str, Any]) -> None:
    """ghost 模板名直调（get_render_spec 前置于聚合查询——免 BLM 预置直达 494）。"""
    ghost = f"ghost-{uuid_module.uuid4().hex[:8]}"
    context["preset"]["ghost_name"] = ghost
    _run_cli(
        context,
        [
            "report-generate",
            "--plan-id",
            str(uuid_module.uuid4()),
            "--format",
            "pdf",
            "--brand-template",
            ghost,
        ],
    )


@when("CLI 直调 report-generate（--brand-template 且 --format markdown）")
def when_cli_generate_combination_guard(context: dict[str, Any]) -> None:
    """组合守卫直调（品牌仅 PDF 面支持——markdown 组合非法显式拒绝非静默忽略）。"""
    _run_cli(
        context,
        [
            "report-generate",
            "--plan-id",
            str(uuid_module.uuid4()),
            "--format",
            "markdown",
            "--brand-template",
            "any-template-name",
        ],
    )


@then("stderr 呈现 EXCEPTION_494 且 message 含模板名")
def then_494_with_template_name(context: dict[str, Any]) -> None:
    """494+模板名 message 断言（404 等价语义——CLI 面 exit 1）。"""
    assert context["cli_exit_code"] == 1, f"exit={context['cli_exit_code']}"
    assert "[EXCEPTION_494]" in context["cli_stderr"]
    assert context["preset"]["ghost_name"] in context["cli_stderr"], (
        f"message 应含模板名 {context['preset']['ghost_name']}: {context['cli_stderr']!r}"
    )


@then("exit code 为 1")
def then_exit_code_one(context: dict[str, Any]) -> None:
    """exit 1 独立断言（S8 尾步——与 S3 组合式断言分立的逐行步骤形态）。"""
    assert context["cli_exit_code"] == 1, f"exit={context['cli_exit_code']}"


# ======================================================================
# AC-4 + AC-5: 白标导出主链/默认态回归/品牌准确四件套（S5/S6/S7）
# ======================================================================


@given("BLM 前两阶段已完成（八步思维链归档在位）且品牌模板已保存")
def given_blm_and_brand_template(context: dict[str, Any]) -> None:
    """组合预置（模板行先行[红锚]→BLM 八阶段归档→轻装配——单 plan）。"""
    _run_async(context["_loop"], _preset_blm_with_template(context))


@given("BLM 前两阶段已完成（八步思维链归档在位）且含 Logo 品牌模板（黑体预设）已保存")
def given_blm_and_noto_brand_template(context: dict[str, Any]) -> None:
    """品牌准确场景预置（黑体预设钦定——stsong 与默认渲染器同字体恒真不可判别）。"""
    _run_async(context["_loop"], _preset_blm_with_template(context, font_preset="noto-sans-sc", with_logo=True))


@given("两独立 plan 各自 BLM 前两阶段已完成且品牌模板已保存")
def given_two_plans_and_brand_template(context: dict[str, Any]) -> None:
    """跨 plan 复用预置（一模板+两 plan 八阶段归档——模板不锚定 plan 语义载体）。"""
    _run_async(context["_loop"], _preset_blm_with_template(context, plan_count=2))


@when("CLI 直调 report-generate（--format pdf --brand-template）")
def when_cli_generate_branded(context: dict[str, Any]) -> None:
    """白标导出直调（同入口扩展参数——六段编排+品牌增量三段）。"""
    plan_id = context["preset"]["plan_ids"][0]
    _run_cli(
        context,
        [
            "report-generate",
            "--plan-id",
            plan_id,
            "--format",
            "pdf",
            "--brand-template",
            context["preset"]["template_name"],
        ],
    )


@when("CLI 直调 report-generate（--format pdf 无品牌参）")
def when_cli_generate_default(context: dict[str, Any]) -> None:
    """默认态导出直调（库有模板但未指定——默认路径 byte 等价前提）。"""
    plan_id = context["preset"]["plan_ids"][0]
    _run_cli(
        context,
        ["report-generate", "--plan-id", plan_id, "--format", "pdf"],
    )


@when("分别执行品牌导出与对照导出")
def when_branded_and_control_export(context: dict[str, Any]) -> None:
    """同 plan 双导出（品牌/对照——同数据源唯一变量是品牌，判别最严格）。"""
    plan_id = context["preset"]["plan_ids"][0]
    # 品牌导出
    _run_cli(
        context,
        [
            "report-generate",
            "--plan-id",
            plan_id,
            "--format",
            "pdf",
            "--brand-template",
            context["preset"]["template_name"],
        ],
    )
    assert context["cli_exit_code"] == 0, f"品牌导出失败: {context['cli_stderr']}"
    context["preset"]["branded_plan_id"] = plan_id
    # 对照导出（同 plan 无品牌参）
    _run_cli(
        context,
        ["report-generate", "--plan-id", plan_id, "--format", "pdf"],
    )
    assert context["cli_exit_code"] == 0, f"对照导出失败: {context['cli_stderr']}"


async def _fetch_latest_report(context: dict[str, Any], plan_id: str) -> dict[str, Any]:
    """按 plan 读回最新报告行（report_id/file_path/metadata——登记清理面）。"""
    from sqlalchemy import text as sa_text
    from sqlalchemy.ext.asyncio import AsyncSession

    manager = _make_pg_manager()
    try:
        async with AsyncSession(manager.get_async_engine()) as session:
            rows = await session.execute(
                sa_text(
                    "SELECT report_id, file_path, metadata FROM strategic_reports "
                    "WHERE plan_id = CAST(:p AS uuid) ORDER BY created_at DESC LIMIT 1"
                ),
                {"p": plan_id},
            )
            row = rows.one()
            report_id, file_path, metadata = row[0], row[1], (row[2] or {})
    finally:
        await manager.get_async_engine().dispose()
    context["_report_ids"].append(str(report_id))
    context["_pdf_object_keys"].append(str(file_path))
    return {"report_id": str(report_id), "file_path": str(file_path), "metadata": metadata}


@then("导出成功且品牌增量行在 stdout")
def then_branded_export_success(context: dict[str, Any]) -> None:
    """导出成功呈现（品牌增量行——brand 参在场时打印）。"""
    assert context["cli_exit_code"] == 0, f"exit={context['cli_exit_code']} stderr={context['cli_stderr']}"
    assert f"品牌模板: {context['preset']['template_name']}（已应用）" in context["cli_stdout"]


@then("L2 行 metadata 品牌两键值级断言")
def then_metadata_brand_keys(context: dict[str, Any]) -> None:
    """metadata 品牌两键（brand_template_id/brand_applied 直推预置 template_id）。"""
    report = _run_async(context["_loop"], _fetch_latest_report(context, context["preset"]["plan_ids"][0]))
    assert report["metadata"].get("brand_template_id") == context["preset"]["template_id"], (
        f"brand_template_id 漂移: {report['metadata'].get('brand_template_id')}"
    )
    assert report["metadata"].get("brand_applied") is True, f"brand_applied 漂移: {report['metadata'].get('brand_applied')}"


@then("L4 WORM PDF 对象键通道不变")
def then_pdf_object_key_channel(context: dict[str, Any]) -> None:
    """对象键通道（reports/{plan_id}/{report_id}.pdf——白标不改变归档通道）。"""
    report = _run_async(context["_loop"], _fetch_latest_report(context, context["preset"]["plan_ids"][0]))
    expected = f"reports/{context['preset']['plan_ids'][0]}/{report['report_id']}.pdf"
    assert report["file_path"] == expected, f"对象键漂移: {report['file_path']} != {expected}"


@then("L2 行 metadata 零品牌键")
def then_metadata_no_brand_keys(context: dict[str, Any]) -> None:
    """默认态零品牌键（无品牌导出不写品牌两键——JSONB 顶层自由扩展的方向性）。"""
    report = _run_async(context["_loop"], _fetch_latest_report(context, context["preset"]["plan_ids"][0]))
    assert "brand_template_id" not in report["metadata"], "默认态不应有 brand_template_id"
    assert "brand_applied" not in report["metadata"], "默认态不应有 brand_applied"


@then("L4 对象键通道与 6-5b 冻结形态一致")
def then_default_object_key_6b_shape(context: dict[str, Any]) -> None:
    """默认态对象键（PDF_OBJECT_KEY_TEMPLATE 单源格式——v1.1.0 演进零破坏运行面）。"""
    report = _run_async(context["_loop"], _fetch_latest_report(context, context["preset"]["plan_ids"][0]))
    expected = f"reports/{context['preset']['plan_ids'][0]}/{report['report_id']}.pdf"
    assert report["file_path"] == expected


async def _read_pdf_bytes(context: dict[str, Any], file_path: str) -> bytes:
    """L4 读回 PDF bytes（WORM 读允许——retrieve 聚合）。"""
    from src.domain.ports.resolver import resolve

    chunks: list[bytes] = []
    async for chunk in resolve("l4_object").retrieve(bucket_type=_EVIDENCE_BUCKET_TYPE, object_key=file_path):
        chunks.append(chunk)
    return b"".join(chunks)


@then("PDF 字体资源含品牌注册名且首页含 Image XObject")
def then_font_and_xobject(context: dict[str, Any]) -> None:
    """四件套前两件（字体名[TTF 形态可判别]+首页 Image XObject——pypdf 解析）。"""
    import io

    from pypdf import PdfReader

    # 双导出后最新行是对照导出（latest 被覆盖）——品牌 PDF 按 metadata 品牌键过滤回查
    branded = _run_async(context["_loop"], _fetch_brand_report(context, context["preset"]["branded_plan_id"]))
    pdf_bytes = _run_async(context["_loop"], _read_pdf_bytes(context, branded["file_path"]))
    reader = PdfReader(io.BytesIO(pdf_bytes))
    # 字体资源（任一页 /Resources/Font 的 BaseFont 含注册名 NotoSansSC——子集前缀容忍）
    base_fonts: list[str] = []
    for page in reader.pages:
        fonts = page.get("/Resources", {}).get("/Font", {})
        for font in fonts.values():
            base_font = font.get_object().get("/BaseFont", "")
            base_fonts.append(str(base_font))
    assert any("NotoSansSC" in name for name in base_fonts), f"字体资源不含 NotoSansSC: {base_fonts}"
    # 首页 Image XObject（logo 位图首启——platypus.Image）
    first = reader.pages[0].get("/Resources", {})
    xobjects = first.get("/XObject", {})
    images = [obj.get_object() for obj in xobjects.values() if obj.get_object().get("/Subtype") == "/Image"]
    assert images, f"首页零图像 XObject（logo 缺席）: {list(xobjects.keys())}"
    context["preset"]["pdf_bytes"] = pdf_bytes


@then("品牌色 RGB 序列在内容流（fp_str 格式）")
def then_brand_color_in_content_stream(context: dict[str, Any]) -> None:
    """四件套之三（内容流含品牌色——reportlab fp_str 格式期望串，直拼 f'{r/255:.6f}'
    恒不中——期望串须用 fp_str 生成）。"""
    import io

    from pypdf import PdfReader
    from reportlab.lib.rl_accel import fp_str

    reader = PdfReader(io.BytesIO(context["preset"]["pdf_bytes"]))

    def _page_bytes(page_reader: Any) -> bytes:
        contents = page_reader.get_contents()
        assert contents is not None, "页面内容流在位（渲染产物非空页）"
        return bytes(contents.get_data())  # bytes() 收窄 pypdf Any 返回

    content = b"".join(_page_bytes(page) for page in reader.pages)
    title_rgb = fp_str(0x1F / 255, 0x4E / 255, 0x79 / 255)  # corporate-blue title_color #1F4E79
    header_rgb = fp_str(0xDC / 255, 0xE6 / 255, 0xF1 / 255)  # corporate-blue header_bg #DCE6F1
    assert title_rgb.encode("latin-1") in content, f"品牌标题色 {title_rgb} 不在内容流"
    assert header_rgb.encode("latin-1") in content, f"品牌表头底色 {header_rgb} 不在内容流"


@then("对照腿零图像 XObject 且零品牌色")
def then_control_leg_discriminates(context: dict[str, Any]) -> None:
    """四件套之四（对照腿判别——零图像+零品牌色，判别非恒真）。"""
    import io

    from pypdf import PdfReader
    from reportlab.lib.rl_accel import fp_str

    control = _run_async(context["_loop"], _fetch_latest_report(context, context["preset"]["branded_plan_id"]))
    assert "brand_template_id" not in control["metadata"], "对照腿应是默认态导出"
    pdf_bytes = _run_async(context["_loop"], _read_pdf_bytes(context, control["file_path"]))
    reader = PdfReader(io.BytesIO(pdf_bytes))
    for page in reader.pages:
        xobjects = page.get("/Resources", {}).get("/XObject", {})
        images = [obj for obj in xobjects.values() if obj.get_object().get("/Subtype") == "/Image"]
        assert not images, "对照腿不应含图像 XObject"

    def _control_page_bytes(page_reader: Any) -> bytes:
        contents = page_reader.get_contents()
        assert contents is not None, "对照腿页面内容流在位"
        return bytes(contents.get_data())  # bytes() 收窄 pypdf Any 返回

    content = b"".join(_control_page_bytes(page) for page in reader.pages)
    title_rgb = fp_str(0x1F / 255, 0x4E / 255, 0x79 / 255)
    assert title_rgb.encode("latin-1") not in content, "对照腿不应含品牌标题色"


async def _fetch_brand_report(context: dict[str, Any], plan_id: str) -> dict[str, Any]:
    """按 plan 读回品牌报告行（metadata 含 brand_template_id 的最新行——双导出后
    对照行覆盖 latest，品牌行需按键过滤回查）。"""
    from sqlalchemy import text as sa_text
    from sqlalchemy.ext.asyncio import AsyncSession

    manager = _make_pg_manager()
    try:
        async with AsyncSession(manager.get_async_engine()) as session:
            rows = await session.execute(
                sa_text(
                    "SELECT report_id, file_path, metadata FROM strategic_reports "
                    "WHERE plan_id = CAST(:p AS uuid) "
                    "AND metadata ? 'brand_template_id' ORDER BY created_at DESC LIMIT 1"
                ),
                {"p": plan_id},
            )
            row = rows.one()
            report_id, file_path, metadata = row[0], row[1], (row[2] or {})
    finally:
        await manager.get_async_engine().dispose()
    context["_report_ids"].append(str(report_id))
    context["_pdf_object_keys"].append(str(file_path))
    return {"report_id": str(report_id), "file_path": str(file_path), "metadata": metadata}


# ======================================================================
# AC-6: 顾问视图品牌段联动（S10）
# ======================================================================


@given("品牌模板行已预置（含 Logo 的最新模板）")
def given_preset_brand_row_with_logo(context: dict[str, Any]) -> None:
    """品牌段联动预置（含 logo 行——logo_status 已配置派生载体）。"""
    logo_path = context["_tmp_path"] / f"logo-{uuid_module.uuid4().hex[:8]}.png"
    _make_logo_png(logo_path)
    context["logo_path"] = logo_path

    async def _preset() -> str:
        name = _unique_template_name()
        _, _at = _preset_anchor()
        template_id = await _save_brand_template_row(
            ctx=context,
            name=name,
            color_scheme="corporate-blue",
            font_preset="noto-sans-sc",
            logo_object_key=None,
            updated_at=_at(1000),
        )
        logo_object_key = await _upload_logo(context, template_id, logo_path)
        from sqlalchemy import text as sa_text
        from sqlalchemy.ext.asyncio import AsyncSession

        manager = _make_pg_manager()
        try:
            async with AsyncSession(manager.get_async_engine()) as session:
                await session.execute(
                    sa_text("UPDATE brand_templates SET logo_object_key = :k WHERE template_id = :tid"),
                    {"k": logo_object_key, "tid": template_id},
                )
                await session.commit()
        finally:
            await manager.get_async_engine().dispose()
        return name

    context["preset"]["template_name"] = _run_async(context["_loop"], _preset())


@when("构建顾问视图")
def when_build_consultant_view(context: dict[str, Any]) -> None:
    """顾问视图构建（组合根 resolve——v1.1.0 三依赖服务读配置面）。"""
    from src.domain.ports.resolver import resolve

    service = resolve("consultant_view_service")
    context["views"].append(_run_async(context["_loop"], service.build_consultant_view()))


@then("品牌段 configured 为 True 且三状态呈现名直推")
def then_brand_section_derived(context: dict[str, Any]) -> None:
    """品牌段三状态断言（呈现名字面期望——独立字面双源漂移即红）。"""
    brand = context["views"][-1].brand
    assert brand.configured is True, f"configured 漂移: {brand.configured}（应读配置派生 True）"
    assert brand.logo_status == "已配置", f"logo_status 漂移: {brand.logo_status}"
    assert brand.color_scheme_status == "商务蓝", f"color_scheme_status 漂移: {brand.color_scheme_status}"
    assert brand.font_status == "Noto Sans SC（黑体）", f"font_status 漂移: {brand.font_status}"
    assert brand.degraded is False


# ======================================================================
# AC-8: 性能双段（S11/S12——口径差声明见模块 docstring）
# ======================================================================


@given("品牌模板服务可用且 Logo 文件在位")
def given_brand_service_and_logo(context: dict[str, Any]) -> None:
    """性能面预置（服务可用+合法 logo——最重路径采样前提）。"""
    from src.application.ports.brand_template import COLOR_SCHEME_PRESETS, FONT_PRESETS

    assert COLOR_SCHEME_PRESETS and FONT_PRESETS
    logo_path = context["_tmp_path"] / f"logo-{uuid_module.uuid4().hex[:8]}.png"
    _make_logo_png(logo_path)
    context["logo_path"] = logo_path


@when("同名全参形态连续保存 20 轮计时")
def when_save_20_rounds(context: dict[str, Any]) -> None:
    """保存采样（同名 UPSERT 20 轮+2 预热——最重路径：PG upsert+L4 store 每轮；
    同名覆盖同键零垃圾对象、单行登记零行累积）。"""
    from src.domain.ports.resolver import resolve

    service = resolve("brand_template_service")
    name = _unique_template_name()
    context["preset"]["name"] = name

    async def _rounds() -> None:
        for _ in range(_WARMUP_ROUNDS):
            await service.save_brand_template(
                name=name,
                color_scheme="corporate-blue",
                font_preset="stsong",
                logo_path=str(context["logo_path"]),
            )
        for _ in range(_SAMPLE_ROUNDS):
            start = datetime.now(UTC)
            template = await service.save_brand_template(
                name=name,
                color_scheme="corporate-blue",
                font_preset="stsong",
                logo_path=str(context["logo_path"]),
            )
            context["durations"].append((datetime.now(UTC) - start).total_seconds() * 1000)
        context["_brand_template_ids"].append(str(template.template_id))
        context["_logo_object_keys"].append(f"logos/{template.template_id}")

    _run_async(context["_loop"], _rounds())


@then("P95 小于 200ms")
def then_save_p95(context: dict[str, Any]) -> None:
    """保存 P95 断言（sorted[ceil(0.95n)-1] 数学口径——20 轮服务面窗口）。"""
    durations = sorted(context["durations"])
    p95 = durations[math.ceil(_P95_PERCENTILE * len(durations)) - 1]
    assert p95 < _SAVE_P95_LIMIT_MS, f"P95 {p95:.1f}ms 超门禁 {_SAVE_P95_LIMIT_MS}ms（全量: {durations}）"


@when("单一数据源连续 20 次品牌导出计时")
def when_export_20_rounds(context: dict[str, Any]) -> None:
    """导出采样（编程面 use case 直调 20 轮——6-5b 口径继承；CLI bootstrap
    秒级开销不混入计时窗口）。"""
    plan_id = context["preset"]["plan_ids"][0]
    template_name = context["preset"]["template_name"]

    async def _rounds() -> None:
        for _ in range(_SAMPLE_ROUNDS):
            start = datetime.now(UTC)
            report = await ctx_use_case_execute(context, plan_id, template_name)
            elapsed = (datetime.now(UTC) - start).total_seconds()
            context["durations"].append(elapsed)
            context["_report_ids"].append(str(report.report_id))
            context["_pdf_object_keys"].append(str(report.file_path))

    _run_async(context["_loop"], _rounds())


def ctx_use_case_execute(context: dict[str, Any], plan_id: str, template_name: str) -> Any:
    """编程面品牌导出（ctx 装配 use case——v1.1.0 brand_template_name 透传）。"""
    return context["pdf_use_case"].execute(plan_id=plan_id, brand_template_name=template_name)


@then("P95 小于 60 秒且每轮三元可读回")
def then_export_p95(context: dict[str, Any]) -> None:
    """导出 P95+三元（L2 行数/L4 对象数累计 20——每轮新 report_id 单调）。"""
    from sqlalchemy import text as sa_text
    from sqlalchemy.ext.asyncio import AsyncSession

    durations = sorted(context["durations"])
    p95 = durations[math.ceil(_P95_PERCENTILE * len(durations)) - 1]
    assert p95 < _EXPORT_P95_LIMIT_SECONDS, f"P95 {p95:.1f}s 超门禁 {_EXPORT_P95_LIMIT_SECONDS}s（全量: {durations}）"
    plan_id = context["preset"]["plan_ids"][0]
    manager = _make_pg_manager()

    async def _verify() -> None:
        try:
            async with AsyncSession(manager.get_async_engine()) as session:
                rows = await session.execute(
                    sa_text("SELECT COUNT(*) FROM strategic_reports WHERE plan_id = CAST(:p AS uuid)"),
                    {"p": plan_id},
                )
                count = int(rows.scalar() or 0)
                assert count == _SAMPLE_ROUNDS, f"L2 行数 {count} != {_SAMPLE_ROUNDS}"
        finally:
            await manager.get_async_engine().dispose()

    _run_async(context["_loop"], _verify())

    # L4 对象数（WORM 桶前缀计数——reports/{plan_id}/ 恰 20 对象）
    def _count_objects() -> int:
        client = _minio_client()
        bucket = _resolve_bucket_name(_EVIDENCE_BUCKET_TYPE)
        return sum(1 for _ in client.list_objects(bucket, prefix=f"reports/{plan_id}/"))

    count = _run_async(context["_loop"], asyncio.to_thread(_count_objects))
    assert count == _SAMPLE_ROUNDS, f"L4 对象数 {count} != {_SAMPLE_ROUNDS}"
    # 每轮 report_id 唯一（单调新行）
    assert len(set(context["_report_ids"])) == _SAMPLE_ROUNDS


# ======================================================================
# AC-3: 跨 plan 复用（S13）
# ======================================================================


@when("两 plan 分别以同模板名品牌导出")
def when_export_two_plans(context: dict[str, Any]) -> None:
    """两 plan 编程面品牌导出（同模板名——复用入口语义：模板不锚定 plan）。"""
    template_name = context["preset"]["template_name"]

    async def _rounds() -> None:
        for plan_id in context["preset"]["plan_ids"]:
            report = await ctx_use_case_execute(context, plan_id, template_name)
            context["_report_ids"].append(str(report.report_id))
            context["_pdf_object_keys"].append(str(report.file_path))

    _run_async(context["_loop"], _rounds())


@then("两份 L2 行 brand_template_id 一致且各自对象键正确")
def then_two_plans_same_brand(context: dict[str, Any]) -> None:
    """跨 plan 复用断言（两行同 brand_template_id+各自 plan 锚定对象键）。"""
    from sqlalchemy import text as sa_text
    from sqlalchemy.ext.asyncio import AsyncSession

    manager = _make_pg_manager()

    async def _fetch() -> list[dict[str, Any]]:
        try:
            async with AsyncSession(manager.get_async_engine()) as session:
                rows = await session.execute(
                    sa_text(
                        "SELECT plan_id, report_id, file_path, metadata->>'brand_template_id' AS btid "
                        "FROM strategic_reports WHERE report_id = ANY(:ids)"
                    ),
                    {"ids": context["_report_ids"][-2:]},
                )
                return [
                    {
                        "plan_id": str(row[0]),
                        "report_id": str(row[1]),
                        "file_path": str(row[2]),
                        "brand_template_id": str(row[3]),
                    }
                    for row in rows
                ]
        finally:
            await manager.get_async_engine().dispose()

    records = _run_async(context["_loop"], _fetch())
    assert len(records) == 2, f"应有 2 行，实得 {len(records)}"
    expected_btid = context["preset"]["template_id"]
    for record in records:
        assert record["brand_template_id"] == expected_btid, (
            f"brand_template_id 漂移: {record['brand_template_id']} != {expected_btid}"
        )
        assert record["file_path"] == f"reports/{record['plan_id']}/{record['report_id']}.pdf"
    assert records[0]["plan_id"] != records[1]["plan_id"], "两行应分属两 plan"


# ======================================================================
# 收尾（S14——src 与四测试目录完成清单存在性）
# ======================================================================


@then("src 新建与扩展文件存在（含字体资产与 018 migration）")
def then_completion_src_files() -> None:
    """S14a：src 完成清单（新建 9+扩展 12=21 项+migration 018——逐项 is_file）。"""
    for label, relative in _COMPLETION_SRC_FILES.items():
        path = _REPO_ROOT / relative
        assert path.is_file(), f"src 交付件缺失[{label}]: {relative}"
    migration_path = _REPO_ROOT / _COMPLETION_MIGRATION_FILE
    assert migration_path.is_file(), f"migration 交付件缺失: {_COMPLETION_MIGRATION_FILE}"


@then("四测试目录新增与扩展文件存在")
def then_completion_test_files() -> None:
    """S14b：四测试目录完成清单（12 新建+9 扩展——逐项 is_file）。"""
    for label, relative in _COMPLETION_TEST_FILES.items():
        path = _REPO_ROOT / relative
        assert path.is_file(), f"测试交付件缺失[{label}]: {relative}"
