"""PDF 报告生成 + 引文索引验收测试（Story 6-5b）。

13 场景分档表：

| # | 场景 | AC | 数据面构造 | 门控 |
|---|------|----|-----------|------|
| S1 | PDF 报告生成主链六段编排全落位 | AC-1 | 归档轻装配八步（OD-3 口径重读：归档数据面就绪即生成） | 四真实服务 |
| S2 | 数据源全缺时抛出 490 异常 | AC-1 | 从未归档的独立 plan_id（天然 total==0——PDF 链同判复用） | 四真实服务 |
| S3 | 双格式同源一致 | AC-2 | 同 plan_id 先 Markdown 后 PDF（同聚合同计数单位） | 四真实服务 |
| S4 | 引文索引正常解析 | AC-3 | 预置 Qdrant 点 + PG documents 行（同租户闭环）+ 归档喂真实 chunk_id | 四真实服务 |
| S5 | 引文去重保序 | AC-3 | 两步骤（trend/competition）共享同一预置 chunk_id | 四真实服务 |
| S6 | 引文解析降级与全空引文 | AC-3 | 降级 plan（喂不存在 chunk_id）+ 全空 plan（evidence_refs 全空）两态 | 四真实服务 |
| S7 | 书签 outline 层级结构 | AC-4 | 同 S1（display_name 源独立构造期望） | 四真实服务 |
| S8 | 目录内链与引文锚点 | AC-4 | 同 S4（真实引文锚点可寻址形态断言） | 四真实服务 |
| S9 | ReportGenerated 事件经 outbox 落行 | AC-5 | 同 S1（report_type=pdf 值级） | 四真实服务 |
| S10 | 读侧消费面契约键集全等 | AC-6 | 同 S1（chain 五键 + payload 键族——对齐 6-5a S10 形态） | 四真实服务 |
| S11 | 性能 P95 与成功率采样 | AC-7 | 单一数据源 plan × 20 次（L4 对象数 20——键锚 report_id 天然互异） | 四真实服务 |
| S12 | 并发生成 3 个 PDF 报告互不串扰 | AC-7 | 三 plan 八步归档（gather 形态锚） | 四真实服务 |
| S13 | Story 交付件存在性收尾验收 | 收尾 | 静态文件断言 | 无 |

测试隔离与口径声明：
- **OD-3 口径重读**：PDF 生成不要求 Markdown 报告行存在（归档数据面就绪即生成）——全部场景用
  归档轻装配（Fake LLM 不进链路——ComposeAndArchiveStepChain 直交归档，无 LLM 依赖）；
  Markdown 链仅在 S3 双格式对照场景同 plan_id 生成一次。
- **OD-4 L4 WORM**：对象键锚 report_id（reports/{plan_id}/{report_id}.pdf——每 report 恰一对象
  天然唯一，无同秒覆写形态）；测试桶 WORM 面探测自愈（无锁桶重建——6-4 先例）；清理
  bypass_governance_mode=True 绕过端口直用 minio client（L4ObjectPort 无 remove_objects）。
- **引文预置（AC-3）**：Qdrant 点 upsert 至生产默认 "documents" collection（复用既有测试
  collection 裁定——零生命周期管理，点级 chunk_id FilterSelector 定向清理即闭环）；PG
  documents 行 tenant_id=服务构造注入的测试租户同值闭环（find 硬过滤下租户不匹配必现
  document_missing 假降级——OD-6）。
- **AC-8 断言分层**：渲染质量归单测 Task 2 + 集成场景⑤ Task 6 承载、验收层不单列场景；验收
  文本层断言依赖 R3 实证（STSong-Light extract_text 中文完美工作——正确 setFont 前提）。
- **引文锚点断言形态（Task 0.2 复验钉死）**：孤立 bookmarkPage 在 PDF 中零留存
  （named_destinations 恒空）——锚点承载 = 附录 C 条目行 link 注释自指（PDF.js/6-8 可经
  /Annots 寻址）；负向断言 = 正文页 /Annots 零 Link。
- **teardown 九步链**（6-5a 七步 + L4/引文预置两步扩展）：端口覆写还原 → PG 会话终结 →
  outbox 行精确 DELETE → L2 行 DELETE → 归档三面（PG/Qdrant/MinIO WORM）→ L4 PDF 对象
  bypass 定向删 → 引文预置两面（Qdrant 点 + PG documents 行）→ Redis 键族 + 关闭客户端。
- **延迟 import 纪律**：本 Story 新交付模块一律在步骤/装配函数体内 import——顶部 import
  会使 pytest 收集期整文件 collection error，Task 0 预期红因 = 运行期 ImportError。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_pdf_report.py -v
"""

import asyncio
import logging
import math
import uuid
from collections.abc import Awaitable, Generator
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pytest_bdd import given, scenario, then, when

logger = logging.getLogger(__name__)

# marker 名以 pyproject 注册为准（database 非 postgresql）；xdist_group 模块级挂法
# 复用 6-1~6-5a 组名（性能/采样场景跨 Story 同 worker 串行）
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

#: 八 stage 期望序（归档数据构造排序参考——与 6-5a 同源）
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

#: chain 读侧 records 五键冻结基线（AC-6 字面键集——防漂移即守护，6-5a 同款）
_RECORD_KEY_BASELINE: tuple[str, ...] = ("stage", "chain", "archive_id", "degraded", "blob_content")

#: ReportGenerated outbox payload 键族冻结基线（事件类冻结字段面——零新增守护）
_REPORT_EVENT_PAYLOAD_KEY_BASELINE: frozenset[str] = frozenset(
    {"report_id", "report_type", "file_path", "aggregate_id", "aggregate_type", "event_type"}
)

#: 事件基类核心三键（DomainEvent 顶层通用键——两级路径的顶层单源命名）
_CORE_EVENT_PAYLOAD_KEYS: frozenset[str] = frozenset({"aggregate_id", "aggregate_type", "event_type"})

#: 性能采样轮数（OD-8：N 与成功率口径同源）
_PERF_SAMPLE_ROUNDS: int = 20

#: P95 上限（秒）——AC-7 口径 = epics 钦定 60s（OD-8；勿照抄 6-5a 源码的 30.0——那是 6-5a epics 口径）
_PERF_P95_LIMIT_SECONDS: float = 60.0

#: section_count 冻结口径（附录 C 是 H2 附录不计 H3 小节——与 6-5a 恒同）
_EXPECTED_SECTION_COUNT: int = 11

#: 引文链测试租户（服务构造注入 + 预置 PG documents 行同值闭环——OD-6；
#: 数据链无租户可用，注入是唯一来源，多租户扩展归后续 Story）
_CITATION_TENANT_ID: str = "acceptance-pdf-citation-tenant"

#: 引文预置 collection（生产默认名——R4T-2 裁定复用既有测试 collection 零生命周期管理）
_CITATION_COLLECTION: str = "documents"

#: 附录 C 冻结标题（增量冻结表——Task 0 权威输入）
_APPENDIX_C_TITLE: str = "附录 C 引文索引"

#: 全空引文单行说明（增量冻结表钦定文案）
_EMPTY_CITATION_NOTE: str = "本报告无检索证据引用"

#: L4 桶类型常量镜像（服务端口单源对齐——断言期望独立字面，双源漂移即红）
_EVIDENCE_BUCKET_TYPE: str = "archive-evidence"

_BLM_TASK = "制定新能源汽车行业五年战略规划（PDF 报告验收真实链）"


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
    """驱逐 resolver SINGLETON/SCOPED 缓存（跨 loop/跨文件污染防线——6-5a 实施攻坚沉淀）。"""
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
    """场景级上下文（teardown 九步链随 yield 后执行——断言失败也清理）。"""
    _clear_resolver_caches()
    ctx: dict[str, Any] = {
        "_loop": event_loop,
        "_env": acceptance_env_config,
        "_report_tmp_path": tmp_path,
        "_restorers": [],
        "_chain_assembled": False,
        "_pg_manager": None,
        "_redis_client": None,
        # 清理登记面（调用服务之前预登记）
        "_plan_ids": [],
        "_report_ids": [],
        "_pdf_object_keys": [],
        "_citation_point_ids": [],
        "_citation_document_ids": [],
    }
    yield ctx
    _teardown_chain(ctx)
    _clear_resolver_caches()


# ======================================================================
# teardown 九步链（各步独立 try/except——前步失败不阻断后步；6-5a 七步 +
# L4 PDF 对象/引文预置两面两步扩展）
# ======================================================================


def _teardown_chain(ctx: dict[str, Any]) -> None:
    """teardown 九步链（报告三元 + 归档三面 + L4 对象 + 引文预置 + 客户端关闭）。

    各步独立 try/except（残局防线）；清理失败 logger.error 可观测；
    全部 _run_async 同循环（跨循环 "Event loop is closed" 存档教训）。
    """
    # ① 端口覆写还原 + PG 会话终结
    for restore in ctx["_restorers"]:
        try:
            restore()
        except Exception as exc:
            logger.error("teardown 端口还原失败（残局防线不阻断）: %s", exc, exc_info=exc)
    # ② outbox 事件行精确 DELETE
    try:
        _run_async(ctx["_loop"], _cleanup_outbox_rows(ctx))
    except Exception as exc:
        logger.error("teardown outbox 行清理失败: %s", exc, exc_info=exc)
    # ③ L2 strategic_reports 行精确 DELETE
    try:
        _run_async(ctx["_loop"], _cleanup_report_rows(ctx))
    except Exception as exc:
        logger.error("teardown L2 报告行清理失败: %s", exc, exc_info=exc)
    # ④⑤ 归档三面（PG 档案行 / Qdrant 点 / MinIO WORM 归档 blob——6-5a 移植）
    try:
        _run_async(ctx["_loop"], _cleanup_archive_residues(ctx))
    except Exception as exc:
        logger.error("teardown 归档三面清理失败: %s", exc, exc_info=exc)
    # ⑥ L4 PDF 对象 bypass 定向删（对象键锚 report_id——reports/ 前缀与归档键天然隔离）
    try:
        _run_async(ctx["_loop"], _cleanup_pdf_objects(ctx))
    except Exception as exc:
        logger.error("teardown L4 PDF 对象清理失败: %s", exc, exc_info=exc)
    # ⑦ 引文预置两面（Qdrant documents 点 + PG documents 行）
    try:
        _run_async(ctx["_loop"], _cleanup_citation_presets(ctx))
    except Exception as exc:
        logger.error("teardown 引文预置清理失败: %s", exc, exc_info=exc)
    # ⑧⑨ Redis 客户端关闭（本 Story 无快照键族——轻装配不经 run 链；仅关句柄）
    if ctx["_redis_client"] is not None:
        try:
            _run_async(ctx["_loop"], ctx["_redis_client"].close())
        except Exception as exc:
            logger.error("teardown Redis 客户端关闭失败: %s", exc, exc_info=exc)


def _make_pg_manager(env: Any) -> Any:
    """构建独立 PostgreSQLManager（teardown/清理专用——不复用场景会话）。"""
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


async def _cleanup_outbox_rows(ctx: dict[str, Any]) -> None:
    """outbox 事件行精确 DELETE（event_id 面 + plan_id/report_id 双 JSONB 通道兜底）。"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    manager = _make_pg_manager(ctx["_env"])
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


async def _cleanup_archive_residues(ctx: dict[str, Any]) -> None:
    """归档三面清理（PG 档案行 / Qdrant 点 / MinIO WORM 归档 blob——6-5a 移植）。"""
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
            # MinIO WORM 归档 blob 删除（bypass——6-3 集成先例）
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
                        errors = client.remove_objects(
                            _resolve_archive_bucket_name(),
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


async def _cleanup_pdf_objects(ctx: dict[str, Any]) -> None:
    """L4 PDF 对象 bypass 定向删（对象键锚 report_id——WORM 治理绕过端口直用 minio client）。"""
    if not ctx["_pdf_object_keys"]:
        return
    from minio import Minio
    from minio.deleteobjects import DeleteObject

    env = ctx["_env"]

    def _remove() -> None:
        client = Minio(
            endpoint=env.minio.endpoint,
            access_key=env.minio.access_key,
            secret_key=env.minio.secret_key,
            secure=env.minio.secure,
        )
        errors = client.remove_objects(
            _resolve_archive_bucket_name(),
            [DeleteObject(key) for key in ctx["_pdf_object_keys"]],
            bypass_governance_mode=True,
        )
        for _ in errors:
            pass

    await asyncio.to_thread(_remove)


async def _cleanup_citation_presets(ctx: dict[str, Any]) -> None:
    """引文预置两面清理（Qdrant documents 点 chunk_id payload 面定向 + PG documents 行）。"""
    env = ctx["_env"]
    # Qdrant 点（payload.chunk_id FilterSelector 面——点 id 经 MD5 归一，payload 键是稳定清理锚）
    if ctx["_citation_point_ids"]:
        try:
            from qdrant_client import AsyncQdrantClient
            from qdrant_client import models as qdrant_models

            qdrant = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
            try:
                await qdrant.delete(
                    collection_name=_CITATION_COLLECTION,
                    points_selector=qdrant_models.FilterSelector(
                        filter=qdrant_models.Filter(
                            must=[
                                qdrant_models.FieldCondition(
                                    key="chunk_id",
                                    match=qdrant_models.MatchAny(any=list(ctx["_citation_point_ids"])),
                                )
                            ]
                        )
                    ),
                )
            finally:
                await qdrant.close()
        except Exception:
            pass
    # PG documents 行
    if ctx["_citation_document_ids"]:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession

        manager = _make_pg_manager(env)
        try:
            async with AsyncSession(manager.get_async_engine()) as session:
                await session.execute(
                    text("DELETE FROM documents WHERE id = ANY(:ids)"),
                    {"ids": [str(did) for did in ctx["_citation_document_ids"]]},
                )
                await session.commit()
        finally:
            await manager.get_async_engine().dispose()


def _resolve_archive_bucket_name() -> str:
    """解析归档 bucket 名（经组合根 l4_object 仓储——零硬编码，6-4 形态）。"""
    from src.domain.ports.resolver import get_resolver

    l4 = get_resolver().resolve("l4_object")
    return str(l4._repository._resolve_bucket_name(_EVIDENCE_BUCKET_TYPE))


async def _probe_and_assemble(ctx: dict[str, Any]) -> None:
    """四服务探测（PG/Redis/Qdrant/MinIO）+ WORM 桶自愈（探测失败动态 skip）。"""
    import pytest as _pytest
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    env = ctx["_env"]
    from src.domain.ports.registry import _global_registry

    if _global_registry.get("agent_workflow_use_case") is None:
        from src.composition_root import bootstrap

        bootstrap()
    # PostgreSQL 探测（报告元数据表 + outbox + 归档表 + documents 预检）
    pg_manager = _make_pg_manager(env)
    try:
        async with AsyncSession(pg_manager.get_async_engine()) as session:
            await session.execute(text("SELECT 1 FROM event_outbox LIMIT 1"))
            await session.execute(text("SELECT 1 FROM strategic_archives LIMIT 1"))
            await session.execute(text("SELECT 1 FROM strategic_reports LIMIT 1"))
            await session.execute(text("SELECT 1 FROM documents LIMIT 1"))
    except Exception as exc:
        await pg_manager.get_async_engine().dispose()
        _pytest.skip(f"PostgreSQL 不可用: {exc}")
    # Redis 探测（本 Story 报告链不写 Redis——探测维持四件门控口径与组串行一致性）
    import redis.asyncio as aioredis

    redis_client = aioredis.Redis(host=env.redis.host, port=env.redis.port, decode_responses=False)
    try:
        await redis_client.ping()
    except Exception as exc:
        await redis_client.close()
        await pg_manager.get_async_engine().dispose()
        _pytest.skip(f"Redis 不可用: {exc}")
    # Qdrant 探测（轻量 HTTP /collections）
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
    # MinIO 探测 + WORM 桶自愈（archive-evidence 无锁则重建带锁——6-4 先例）
    try:
        await asyncio.to_thread(_probe_minio_worm, env)
    except Exception as exc:
        await redis_client.close()
        await pg_manager.get_async_engine().dispose()
        _pytest.skip(f"MinIO 不可用: {exc}")
    # 引文 collection 确保（documents 不存在则幂等创建——向量占位 4 维，get_point 按 id 检索不涉维度）
    try:
        await _ensure_citation_collection(env)
    except Exception as exc:
        await redis_client.close()
        await pg_manager.get_async_engine().dispose()
        _pytest.skip(f"Qdrant 引文 collection 不可用: {exc}")
    ctx["_pg_manager"] = pg_manager
    ctx["_redis_client"] = redis_client
    ctx["_chain_assembled"] = True


def _probe_minio_worm(env: Any) -> None:
    """MinIO WORM 桶自愈探测（bucket 缺失建带锁桶；存在但无锁配置清版本重建——6-4 :995-1035 形态）。"""
    from minio import Minio
    from minio.deleteobjects import DeleteObject

    from src.domain.ports.resolver import get_resolver

    client = Minio(
        endpoint=env.minio.endpoint,
        access_key=env.minio.access_key,
        secret_key=env.minio.secret_key,
        secure=env.minio.secure,
    )
    bucket_name = str(get_resolver().resolve("l4_object")._repository._resolve_bucket_name(_EVIDENCE_BUCKET_TYPE))
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


async def _ensure_citation_collection(env: Any) -> None:
    """引文 collection 确保（documents 幂等创建——R4T-2 复用既有测试 collection 裁定）。"""
    from qdrant_client import AsyncQdrantClient, models

    qdrant = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
    try:
        existing = {item.name for item in (await qdrant.get_collections()).collections}
        if _CITATION_COLLECTION not in existing:
            await qdrant.create_collection(
                collection_name=_CITATION_COLLECTION,
                # 1024 维与生产 embedding 及适配器维度校验对齐（get_point 按 id
                # 检索不涉维度，但 upsert 走生产通道受适配器 1024 维校验约束）
                vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
            )
    finally:
        await qdrant.close()


def _make_fake_embedding() -> Any:
    """Fake Embedding 工厂（外部 SaaS 豁免——固定 1024 维，6-4/6-5a 同款）。"""
    from unittest.mock import AsyncMock

    from src.domain.ports.embedding_service import EmbeddingServicePort

    fake = AsyncMock(spec=EmbeddingServicePort)
    fake.embed_query = AsyncMock(return_value=[0.1] * 1024)
    fake.embed_documents = AsyncMock(return_value=[[0.1] * 1024])
    fake.close = AsyncMock()
    return fake


def _assemble_archive_only(ctx: dict[str, Any]) -> None:
    """轻装配（逐 stage 归档通道 + PDF/Markdown 双格式服务挂接——无 LLM run）。

    PDF 服务构造参数注入（collection/tenant_id）：测试租户与引文预置 PG 行同值
    闭环（find 硬过滤下租户不匹配必现 document_missing 假降级——OD-6）；
    document_repository 经会话包装注入（组合根 _SessionScopedDocumentRepository
    同款——document_repository 严格 ContextVar 会话，CLI/后台上下文对偶）。
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.application.services.chain_of_thought_archive_service import ChainOfThoughtArchiveService
    from src.application.services.pdf_report_generation_service import PdfReportGenerationService
    from src.application.services.report_generation_service import ReportGenerationService
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.application.use_cases.generate_markdown_report import GenerateMarkdownReportUseCase
    from src.application.use_cases.generate_pdf_report import GeneratePdfReportUseCase
    from src.domain.ports.resolver import resolve
    from src.infrastructure.config.memory import MemoryConfig
    from src.infrastructure.storage.fs.file_memory_adapter import FileMemoryAdapter
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
    # Markdown 对照链（S3 双格式——6-5a 轻装配形态，tmp_path L0 隔离）
    ctx["markdown_report_service"] = ReportGenerationService(
        chain_archive_service=ctx["chain_archive_service"],
        snapshot_repository=resolve("snapshot_repository"),
        l0_storage=FileMemoryAdapter(MemoryConfig(memory_l0_path=str(ctx["_report_tmp_path"]))),
        report_repository=resolve("report_repository"),
        event_publisher=resolve("event_publisher"),
    )
    ctx["markdown_use_case"] = GenerateMarkdownReportUseCase(report_service=ctx["markdown_report_service"])
    # PDF 主链（九依赖 + collection/tenant 构造参数注入——OD-6；document_repository
    # 经 cast 契约面收窄注入会话包装——组合根同款注记）
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
        collection=_CITATION_COLLECTION,
        tenant_id=_CITATION_TENANT_ID,
    )
    ctx["pdf_use_case"] = GeneratePdfReportUseCase(report_service=ctx["pdf_report_service"])


def _make_material(stage: str, *, index: int = 0, evidence_refs: tuple[str, ...] | None = None) -> Any:
    """构造归档素材（stage 判型三态分派——6-5a 同款 + evidence_refs 显式覆写位）。

    Args:
        stage: 归档步骤键。
        index: 步骤序（默认占位 chunk_id 变化位）。
        evidence_refs: 显式引文清单覆写（None=默认占位形态 ``chunk-{index}-001``；
            synthesis 步恒空——6-5a 语义）。

    Returns:
        StepChainMaterial 实例。
    """
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
    if evidence_refs is None:
        evidence_refs = () if is_synthesis else (f"chunk-{index}-001",)
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


async def _archive_steps(
    ctx: dict[str, Any],
    plan_id: str,
    refs_factory: Any = None,
) -> list[Any]:
    """逐 stage 组装归档（refs_factory 覆写 evidence_refs——session_context 独立会话承载）。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.infrastructure.storage.postgresql.session_context import session_context

    factory = async_sessionmaker(ctx["_pg_manager"].get_async_engine())
    records = []
    async with session_context(factory):
        for index, stage in enumerate(_EXPECTED_STAGE_ORDER):
            refs = refs_factory(stage, index) if refs_factory is not None else None
            record = await ctx["chain_archive_service"].compose_and_archive_step_chain(
                uuid.UUID(plan_id), stage, _make_material(stage, index=index, evidence_refs=refs)
            )
            records.append(record)
    return records


async def _preset_citation_fixture(ctx: dict[str, Any], count: int) -> list[dict[str, Any]]:
    """引文预置 fixture（Qdrant 点 + PG documents 行——同租户闭环）。

    Qdrant 点预置走生产通道 ``l3_vector.upsert_points``（与 chunk_indexing
    写侧同链——point id 经 ``_normalize_point_id`` MD5 整数归一，裸 client
    以原始 uuid 直写会被 get_point 归一查询漏查——实施攻坚实证）。

    Args:
        ctx: 场景上下文（登记清理面）。
        count: 预置引文数（每条 = 独立 Qdrant 点 + 独立 documents 行）。

    Returns:
        预置清单（每项含 chunk_id/document_id/filename/page——期望独立构造源）。
    """
    import json

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.domain.ports.resolver import resolve

    env = ctx["_env"]
    presets: list[dict[str, Any]] = []
    for i in range(count):
        chunk_id = str(uuid.uuid4())
        document_id = uuid.uuid4()
        filename = f"战略研判参考报告-{i + 1:02d}.pdf"
        page = 12 + i
        presets.append({"chunk_id": chunk_id, "document_id": document_id, "filename": filename, "page": page})
    # Qdrant 点（documents collection——经生产通道 upsert，payload 对齐生产 6 键子集）
    l3 = resolve("l3_vector")
    points = [
        {
            "id": preset["chunk_id"],
            "vector": [0.1] * 1024,  # 既有 documents collection 维度对齐（生产 embedding 1024 维）
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
    ]
    await l3.upsert_points(_CITATION_COLLECTION, points)
    # PG documents 行（tenant_id=服务注入租户同值闭环 + metadata.chunks 含 chunk_id/page_start）
    manager = _make_pg_manager(env)
    try:
        async with AsyncSession(manager.get_async_engine()) as session:
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
                        "'other', 'completed', 'acceptance', 1, CAST(:meta AS jsonb), now(), now())"
                    ),
                    {
                        "id": str(preset["document_id"]),
                        "tenant": _CITATION_TENANT_ID,
                        "filename": preset["filename"],
                        "meta": json.dumps({"chunks": chunks_meta}, ensure_ascii=False),
                    },
                )
            await session.commit()
    finally:
        await manager.get_async_engine().dispose()
    # 清理登记（点 + 行两面）
    for preset in presets:
        ctx["_citation_point_ids"].append(preset["chunk_id"])
        ctx["_citation_document_ids"].append(preset["document_id"])
    return presets


async def _retrieve_pdf_bytes(ctx: dict[str, Any], object_key: str) -> bytes:
    """L4 对象流式读回收 bytes（retrieve 同步返回 AsyncIterator——AC-1 读回口径）。"""
    from src.domain.ports.resolver import resolve

    l4 = resolve("l4_object")
    chunks: list[bytes] = []
    async for chunk in l4.retrieve(_EVIDENCE_BUCKET_TYPE, object_key):
        chunks.append(chunk)
    return b"".join(chunks)


def _pdf_reader(ctx: dict[str, Any], key: str = "pdf_bytes") -> Any:
    """pypdf PdfReader 构造（ctx 内缓存的 PDF bytes）。"""
    import io

    from pypdf import PdfReader

    return PdfReader(io.BytesIO(ctx[key]))


def _pdf_full_text(reader: Any) -> str:
    """全页 extract_text 拼接（STSong-Light 中文完美工作——R3 实证 + Task 0.2 复验）。"""
    return "\n".join(page.extract_text() for page in reader.pages)


def _flatten_outline(reader: Any) -> list[tuple[int, str, int]]:
    """outline 展平为 (层级, 标题, 目标页索引) 序列（嵌套 list 递归展开）。"""

    def walk(items: list[Any], depth: int) -> list[tuple[int, str, int]]:
        out: list[tuple[int, str, int]] = []
        for item in items:
            if isinstance(item, list):
                out.extend(walk(item, depth + 1))
            else:
                out.append((depth, str(item.title), reader.get_destination_page_number(item)))
        return out

    return walk(list(reader.outline), 0)


def _pdf_link_targets(reader: Any) -> list[tuple[int, int]]:
    """全文档 link 注释收集为 (注释所在页索引, 目标页索引) 序列。

    /Dest 数组首元素解析为有效页对象（R3 实证：reportlab save 期已将命名目标
    解析为直接数组——named_destinations 恒空，「命名目标可解析」不可实现，
    锚定 /Dest 数组即锚定目标页）。
    """
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


def _generate_pdf_report(ctx: dict[str, Any], plan_id: str) -> Any:
    """执行 PDF 生成（记录实体 + L4 读回 bytes——多场景共享形态）。

    会话由装配层注入的 find 包装承担（组合根 wrapper 同款）——生成调用
    无需外层 session_context；L2 落库走 report_repository 双模式 fallback。
    """
    report = _run_async(ctx["_loop"], ctx["pdf_use_case"].execute(plan_id=plan_id))
    ctx["report"] = report
    ctx["_report_ids"].append(str(report.report_id))
    ctx["_pdf_object_keys"].append(report.file_path)
    ctx["pdf_bytes"] = _run_async(ctx["_loop"], _retrieve_pdf_bytes(ctx, report.file_path))
    return report


def _register_plan(ctx: dict[str, Any]) -> str:
    """新 plan_id 登记（清理面）。"""
    plan_id = str(uuid.uuid4())
    ctx["plan_id"] = plan_id
    ctx["_plan_ids"].append(plan_id)
    return plan_id


async def _query_outbox_report_rows(ctx: dict[str, Any], report_id: str) -> list[Any]:
    """查询 ReportGenerated outbox 行（四键 + payload——独立连接）。"""
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


async def _count_pdf_objects(ctx: dict[str, Any], plan_id: str) -> int:
    """按 plan_id 前缀计数 L4 PDF 对象（reports/{plan_id}/ 前缀——MinIO list）。"""
    from minio import Minio

    env = ctx["_env"]

    def _count() -> int:
        client = Minio(
            endpoint=env.minio.endpoint,
            access_key=env.minio.access_key,
            secret_key=env.minio.secret_key,
            secure=env.minio.secure,
        )
        return sum(1 for _ in client.list_objects(_resolve_archive_bucket_name(), prefix=f"reports/{plan_id}/", recursive=True))

    return await asyncio.to_thread(_count)


async def _count_outbox_rows(ctx: dict[str, Any], plan_id: str) -> int:
    """按 plan_id 计数 outbox ReportGenerated 行（plan 维度——CR1-F11）。

    通道与清理面同源（metadata.plan_id 直连 + report_id 子查询兜底——
    集成 _count_outbox_report_rows 同款）。
    """
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(ctx["_pg_manager"].get_async_engine()) as session:
        result = await session.execute(
            sa.text(
                "SELECT COUNT(*) FROM event_outbox WHERE event_type = 'ReportGenerated' "
                "AND (payload->'metadata'->>'plan_id' = :p OR payload->'payload'->>'report_id' IN "
                "(SELECT report_id::text FROM strategic_reports WHERE plan_id = CAST(:p AS uuid)))"
            ),
            {"p": plan_id},
        )
        return int(result.scalar_one())


async def _query_report_metadata(ctx: dict[str, Any], report_id: str) -> dict[str, Any]:
    """直查 L2 metadata JSONB（citation 计数与 citations 键——独立连接）。"""
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(ctx["_pg_manager"].get_async_engine()) as session:
        result = await session.execute(
            sa.text("SELECT metadata FROM strategic_reports WHERE report_id = CAST(:r AS uuid)"),
            {"r": report_id},
        )
        row = result.scalar_one_or_none()
        return dict(row) if row else {}


def _query_chain_records(ctx: dict[str, Any], plan_id: str) -> list[dict[str, Any]]:
    """chain 读侧 records 查询（读侧消费面契约——AC-6 断言数据源）。"""
    from src.application.use_cases.get_blm_chain_trace import GetBlmChainTraceUseCase

    trace_use_case = GetBlmChainTraceUseCase(chain_archive_service=ctx["chain_archive_service"])
    view = _run_async(ctx["_loop"], trace_use_case.execute(plan_id=plan_id))
    return list(view.records)


# ======================================================================
# Background Steps
# ======================================================================


@given("PDF 报告生成链服务可用")
def pdf_report_chain_services_available(context: dict[str, Any]) -> None:
    """四真实服务门控探测（不可达动态 skip——禁写死 skip 标记）+ WORM 桶自愈。"""
    _run_async(context["_loop"], _probe_and_assemble(context))


# ======================================================================
# AC-1: PDF 生成主链（聚合复用 → 快照辅源 → 引文聚合 → 渲染 → L4 WORM + L2 → 事件）
# ======================================================================


@scenario(
    "test_acceptance_pdf_report.feature",
    "PDF 报告生成主链六段编排全落位",
)
def test_pdf_main_chain_six_stages() -> None:
    """S1: AC-1 主链六段编排（聚合→快照→引文→渲染→L4+L2→事件）。"""
    pass


@scenario(
    "test_acceptance_pdf_report.feature",
    "数据源全缺时抛出 490 异常",
)
def test_total_missing_raises_490() -> None:
    """S2: AC-1 全缺 490 异常路径（PDF 链同判复用）。"""
    pass


@given("BLM 前两阶段已完成（八步思维链归档在位）")
def blm_eight_steps_archived(context: dict[str, Any]) -> None:
    """归档轻装配 + 逐 stage 八步归档（默认占位 evidence_refs——OD-3 口径：归档面就绪即 PDF 可生成）。"""
    if "pdf_use_case" not in context:
        _assemble_archive_only(context)
    plan_id = _register_plan(context)
    records = _run_async(context["_loop"], _archive_steps(context, plan_id))
    assert len(records) == 8


@given("从未归档的独立 plan_id")
def never_archived_plan_id(context: dict[str, Any]) -> None:
    """天然 total==0 的独立 plan_id（无需清空构造）。"""
    if "pdf_use_case" not in context:
        _assemble_archive_only(context)
    _register_plan(context)


@when("调用 PDF 报告生成用例（plan_id）")
def invoke_pdf_report_generation(context: dict[str, Any]) -> None:
    """经 PDF 生成用例执行（生产通道形态——490 异常捕获记录供 Then 断言）。"""
    from src.domain.exceptions import DomainError

    try:
        _generate_pdf_report(context, context["plan_id"])
    except DomainError as error:
        context["caught_error"] = error


@then("PDF 生成六段编排全部落位")
def assert_six_stage_orchestration(context: dict[str, Any]) -> None:
    """六段编排断言（聚合/快照辅源/引文/渲染/L4+L2/事件各至少一断言）。"""
    from src.application.ports.report_generation import REPORT_TITLE_TEMPLATE

    report = context["report"]
    reader = _pdf_reader(context)
    full_text = _pdf_full_text(reader)
    assert report.section_count == _EXPECTED_SECTION_COUNT  # ①聚合复用（H3 计数恒 11）
    assert "附录 A 执行时间线" not in full_text  # ②latest 快照辅源（轻装配无快照→附录 A 省）
    metadata = _run_async(context["_loop"], _query_report_metadata(context, str(report.report_id)))
    assert metadata.get("timeline_available") is False  # ②辅源可观测面
    assert _APPENDIX_C_TITLE in full_text  # ③引文聚合（附录 C 恒存在）
    assert "citation_count" in metadata and "unresolvable_citation_count" in metadata  # ③计数键
    assert reader.metadata is not None and reader.metadata.title == REPORT_TITLE_TEMPLATE  # ④渲染
    assert len(context["pdf_bytes"]) > 0  # ④渲染产物（L4 读回非空）
    assert context["pdf_bytes"].startswith(b"%PDF")  # ④PDF 魔数
    rows = _run_async(context["_loop"], _count_report_rows(context, context["plan_id"]))
    assert rows >= 1  # ⑤L2 落位
    outbox = _run_async(context["_loop"], _query_outbox_report_rows(context, str(report.report_id)))
    assert len(outbox) == 1  # ⑥事件发布


@then("返回 PDF 实体八字段完整且类型正确")
def assert_entity_eight_fields(context: dict[str, Any]) -> None:
    """StrategicReport 八字段（report_id/plan_id/report_type=PDF/file_path=对象键/计数双字段/generation_ms/created_at）。"""
    from src.domain.entities.strategic_report import ReportType, StrategicReport

    report = context["report"]
    assert isinstance(report, StrategicReport)
    assert isinstance(report.report_id, uuid.UUID)
    assert report.plan_id == context["plan_id"]
    assert report.report_type is ReportType.PDF
    assert report.file_path == f"reports/{context['plan_id']}/{report.report_id}.pdf"  # 对象键模板派生（OD-4）
    assert report.section_count == _EXPECTED_SECTION_COUNT
    assert isinstance(report.degraded_section_count, int) and report.degraded_section_count >= 0
    assert isinstance(report.generation_ms, int) and report.generation_ms >= 0
    assert report.created_at is not None


@then("L4 对象可读回且为有效 PDF")
def assert_l4_object_readable(context: dict[str, Any]) -> None:
    """L4 对象读回（流式收 bytes + pypdf 页数≥1——AC-1 读回口径 OD-8）。"""
    reader = _pdf_reader(context)
    assert len(reader.pages) >= 1
    assert len(reader.pages) >= 3  # 页数下界：封面/目录/正文+附录的自然分布（轻装配实测 3 页）


@then("L2 元数据行可读回且字段与实体一致")
def assert_l2_row_readable(context: dict[str, Any]) -> None:
    """get_latest_by_plan 返回最新行（report_type=pdf 与实体一致 + metadata 扩展键在位）。"""
    from src.domain.entities.strategic_report import ReportType
    from src.domain.ports.resolver import resolve

    repo = resolve("report_repository")
    latest = _run_async(context["_loop"], repo.get_latest_by_plan(uuid.UUID(context["plan_id"])))
    assert latest is not None
    report = context["report"]
    assert str(latest.report_id) == str(report.report_id)
    assert latest.report_type is ReportType.PDF
    assert latest.file_path == report.file_path
    assert latest.section_count == report.section_count
    metadata = _run_async(context["_loop"], _query_report_metadata(context, str(report.report_id)))
    assert "citation_count" in metadata  # L2 metadata 扩展键（AC-3 可观测面）
    assert "citations" in metadata


@then("PDF 生成抛出 ReportGenerationError（EXCEPTION_490）")
def assert_490_exception(context: dict[str, Any]) -> None:
    """异常 code/context 断言（490——PDF 链同判复用）。"""
    error = context.get("caught_error")
    assert error is not None and error.code == "EXCEPTION_490"
    assert error.context["plan_id"] == context["plan_id"]


@then("零 L2 行零 L4 对象零事件落位")
def assert_zero_persistence(context: dict[str, Any]) -> None:
    """490 抛出后零残留（L2 行 0 + L4 对象 0 + outbox 0——编排前置守卫不落盘）。"""
    rows = _run_async(context["_loop"], _count_report_rows(context, context["plan_id"]))
    assert rows == 0
    objects = _run_async(context["_loop"], _count_pdf_objects(context, context["plan_id"]))
    assert objects == 0
    outbox = _run_async(context["_loop"], _count_outbox_rows(context, context["plan_id"]))
    assert outbox == 0, "490 前置守卫路径不应产生事件落行"


# ======================================================================
# AC-2: 格式一致性（同源文档模型——与 Markdown 报告结构同源）
# ======================================================================


@scenario(
    "test_acceptance_pdf_report.feature",
    "双格式同源一致",
)
def test_dual_format_same_source() -> None:
    """S3: AC-2 同源双渲染（section_count 恒等+标题族文本层可寻）。"""
    pass


@when("分别生成 Markdown 与 PDF 报告（同 plan_id）")
def invoke_dual_format_generation(context: dict[str, Any]) -> None:
    """同 plan_id 先 Markdown 后 PDF（同一聚合产物双渲染——OD-3 同源双渲染）。"""
    context["markdown_report"] = _run_async(context["_loop"], context["markdown_use_case"].execute(plan_id=context["plan_id"]))
    context["_report_ids"].append(str(context["markdown_report"].report_id))
    _generate_pdf_report(context, context["plan_id"])


@then("双格式 section_count 恒等且章节标题族 PDF 文本层可寻")
def assert_dual_format_consistency(context: dict[str, Any]) -> None:
    """同聚合同计数单位恒等 + Markdown 标题族在 PDF 文本层可寻（display_name 源独立构造）。"""
    from src.application.ports.chain_of_thought_archive import SYNTHESIS_DISPLAY_NAME
    from src.application.ports.report_generation import REPORT_TITLE_TEMPLATE
    from src.application.services.blm_planning_prompts import (
        MARKET_INSIGHT_STEP_CONFIG,
        PERFORMANCE_GAP_CONFIG,
    )

    markdown_report = context["markdown_report"]
    pdf_report = context["report"]
    assert pdf_report.section_count == markdown_report.section_count == _EXPECTED_SECTION_COUNT
    full_text = _pdf_full_text(_pdf_reader(context))
    assert REPORT_TITLE_TEMPLATE in full_text  # H1 封面题
    step_titles = [cfg.display_name for cfg in MARKET_INSIGHT_STEP_CONFIG.values()]
    for expected in (
        f"1 {PERFORMANCE_GAP_CONFIG.display_name}",
        *[f"2.{i} {name}" for i, name in enumerate(step_titles, start=1)],
        f"2.7 {SYNTHESIS_DISPLAY_NAME}",
        "附录 B 降级与数据缺失记录",
        _APPENDIX_C_TITLE,
    ):
        assert expected in full_text, f"PDF 文本层章节标题缺失: {expected}"


@then("附录 B 降级行数与实体计数联动一致")
def assert_appendix_b_count_linkage(context: dict[str, Any]) -> None:
    """附录 B 降级行数 == degraded_section_count（聚合复用双格式同值——AC-2 第三条承载）。"""
    markdown_report = context["markdown_report"]
    pdf_report = context["report"]
    assert pdf_report.degraded_section_count == markdown_report.degraded_section_count == 0  # 轻装配零降级
    metadata = _run_async(context["_loop"], _query_report_metadata(context, str(pdf_report.report_id)))
    assert metadata.get("degraded_stages") == []


# ======================================================================
# AC-3: 引文索引（evidence_refs 首消费 → 附录 C）
# ======================================================================


@scenario(
    "test_acceptance_pdf_report.feature",
    "引文索引正常解析",
)
def test_citation_index_resolved() -> None:
    """S4: AC-3 真实引文链（预置点+文档行→附录 C 值级）。"""
    pass


@scenario(
    "test_acceptance_pdf_report.feature",
    "引文去重保序",
)
def test_citation_dedup_order() -> None:
    """S5: AC-3 去重保序（两步骤共享 chunk_id→索引唯一+首现次序）。"""
    pass


@scenario(
    "test_acceptance_pdf_report.feature",
    "引文解析降级与全空引文",
)
def test_citation_degraded_and_empty() -> None:
    """S6: AC-3 降级三态真实缺失构造 + 全空单行说明。"""
    pass


@given("引文预置在位（Qdrant 点与文档行）且八步归档含该引文")
def citation_preset_and_archived(context: dict[str, Any]) -> None:
    """预置 1 条引文（Qdrant 点 + documents 行）+ 八步归档全部喂该 chunk_id（去重后 1 条 resolved）。"""
    if "pdf_use_case" not in context:
        _assemble_archive_only(context)
    presets = _run_async(context["_loop"], _preset_citation_fixture(context, count=1))
    context["citation_presets"] = presets
    plan_id = _register_plan(context)
    chunk_id = presets[0]["chunk_id"]

    def _refs(stage: str, index: int) -> tuple[str, ...]:
        return () if stage == "market_insight_synthesis" else (chunk_id,)

    records = _run_async(context["_loop"], _archive_steps(context, plan_id, refs_factory=_refs))
    assert len(records) == 8


@given("两步骤共享同一引文标识的八步归档在位")
def two_steps_share_citation(context: dict[str, Any]) -> None:
    """预置 2 条引文：trend 喂 A、competition 喂 (A, B)——A 跨步骤共享（首现 trend）。"""
    if "pdf_use_case" not in context:
        _assemble_archive_only(context)
    presets = _run_async(context["_loop"], _preset_citation_fixture(context, count=2))
    context["citation_presets"] = presets
    plan_id = _register_plan(context)
    first, second = presets[0]["chunk_id"], presets[1]["chunk_id"]

    def _refs(stage: str, index: int) -> tuple[str, ...]:
        if stage == "market_insight_trend":
            return (first,)
        if stage == "market_insight_competition":
            return (first, second)
        return () if stage == "market_insight_synthesis" else (f"chunk-{index}-001",)

    records = _run_async(context["_loop"], _archive_steps(context, plan_id, refs_factory=_refs))
    assert len(records) == 8


@given("降级与全空两个独立 plan 各自八步归档在位")
def degraded_and_empty_plans_archived(context: dict[str, Any]) -> None:
    """降级 plan（八步全喂同一不存在 chunk_id）+ 全空 plan（evidence_refs 全空）两态。"""
    if "pdf_use_case" not in context:
        _assemble_archive_only(context)
    missing_chunk = str(uuid.uuid4())
    context["missing_chunk_id"] = missing_chunk
    # 降级 plan
    degraded_plan = str(uuid.uuid4())
    context["degraded_plan_id"] = degraded_plan
    context["_plan_ids"].append(degraded_plan)

    def _refs_missing(stage: str, index: int) -> tuple[str, ...]:
        return () if stage == "market_insight_synthesis" else (missing_chunk,)

    records = _run_async(context["_loop"], _archive_steps(context, degraded_plan, refs_factory=_refs_missing))
    assert len(records) == 8
    # 全空 plan
    empty_plan = str(uuid.uuid4())
    context["empty_plan_id"] = empty_plan
    context["_plan_ids"].append(empty_plan)
    records = _run_async(context["_loop"], _archive_steps(context, empty_plan, refs_factory=lambda stage, index: ()))
    assert len(records) == 8


@when("分别生成降级与全空两份 PDF 报告")
def invoke_degraded_and_empty_generation(context: dict[str, Any]) -> None:
    """降级 plan 与全空 plan 各生成一份（两态断言数据面）。"""
    _generate_pdf_report(context, context["degraded_plan_id"])
    context["degraded_report"] = context["report"]
    context["degraded_pdf_bytes"] = context["pdf_bytes"]
    context["degraded_metadata"] = _run_async(
        context["_loop"], _query_report_metadata(context, str(context["degraded_report"].report_id))
    )
    _generate_pdf_report(context, context["empty_plan_id"])
    context["empty_report"] = context["report"]
    context["empty_pdf_bytes"] = context["pdf_bytes"]
    context["empty_metadata"] = _run_async(
        context["_loop"], _query_report_metadata(context, str(context["empty_report"].report_id))
    )


@then("附录 C 引文条目值级匹配（文档名页码切片标识）")
def assert_appendix_c_entry_values(context: dict[str, Any]) -> None:
    """附录 C 条目值级断言（cell 连续序列——extract_text 逐 cell 换行形态）。

    断言形态注记：表格四列是四个独立 Paragraph，extract_text 输出逐 cell
    换行——行级拼接断言不可实现；断言表头锚定后的数据 cell 连续序列
    （"1\\n{filename}\\np.{page}\\n{chunk_id_8}"——序列连续即四列值全对）。
    """
    preset = context["citation_presets"][0]
    full_text = _pdf_full_text(_pdf_reader(context))
    assert "附录 C 引文索引" in full_text
    citation_block = full_text.rsplit("切片标识", 1)[-1]  # 表头锚定后的数据区
    expected_cells = f"1\n{preset['filename']}\np.{preset['page']}\n{preset['chunk_id'][:8]}"
    assert expected_cells in citation_block, f"附录 C 引文条目 cell 序列缺失: {expected_cells!r}"


@then("L2 metadata 引文七键值级断言")
def assert_citations_seven_keys(context: dict[str, Any]) -> None:
    """citations 七键（index/document_id/chunk_id/filename/page/status/stage）值级断言。"""
    preset = context["citation_presets"][0]
    metadata = _run_async(context["_loop"], _query_report_metadata(context, str(context["report"].report_id)))
    citations = metadata["citations"]
    assert isinstance(citations, list) and len(citations) >= 1
    entry = citations[0]
    assert set(entry.keys()) == {"index", "document_id", "chunk_id", "filename", "page", "status", "stage"}
    assert entry["index"] == 1
    assert entry["document_id"] == str(preset["document_id"])
    assert entry["chunk_id"] == preset["chunk_id"]
    assert entry["filename"] == preset["filename"]
    assert entry["page"] == preset["page"]
    assert entry["status"] == "resolved"
    assert entry["stage"] == "performance_gap"  # 首现步骤（八步第一步喂该 chunk）
    assert metadata["citation_count"] == 1
    assert metadata["unresolvable_citation_count"] == 0


@then("引文索引唯一且首现次序正确")
def assert_citation_dedup_order(context: dict[str, Any]) -> None:
    """去重保序（A 共享两步只 1 条 + 首现次序 + stage=首现步骤名）。

    数据面口径：其余五步喂默认占位 chunk（降级条目）——citation_count=7
    （5 占位 + A + B 去重后唯一）；首现序 = 归档写入序（gap 占位[1]→A[2]
    →market_customer 占位[3]→B[4]→余占位）。
    """
    first_preset, second_preset = context["citation_presets"]
    metadata = _run_async(context["_loop"], _query_report_metadata(context, str(context["report"].report_id)))
    citations = metadata["citations"]
    assert metadata["citation_count"] == 7  # 5 占位降级 + A + B（A 跨步骤去重后唯一）
    resolved = [c for c in citations if c["status"] == "resolved"]
    assert len(resolved) == 2  # 仅 A/B 解析成功（占位 chunk 不存在）
    assert [c["chunk_id"] for c in citations].count(first_preset["chunk_id"]) == 1  # A 唯一（去重）
    first_entry = next(c for c in citations if c["chunk_id"] == first_preset["chunk_id"])
    second_entry = next(c for c in citations if c["chunk_id"] == second_preset["chunk_id"])
    assert first_entry["index"] == 2 and second_entry["index"] == 4  # 首现次序（占位交错下的真实序）
    assert first_entry["stage"] == "market_insight_trend"  # A 锚首现步骤
    assert second_entry["stage"] == "market_insight_competition"
    full_text = _pdf_full_text(_pdf_reader(context))
    citation_block = full_text.rsplit("切片标识", 1)[-1]
    first_cells = f"2\n{first_preset['filename']}\np.{first_preset['page']}\n{first_preset['chunk_id'][:8]}"
    second_cells = f"4\n{second_preset['filename']}\np.{second_preset['page']}\n{second_preset['chunk_id'][:8]}"
    assert first_cells in citation_block, f"首现条目 cell 序列缺失: {first_cells!r}"
    assert second_cells in citation_block, f"次现条目 cell 序列缺失: {second_cells!r}"


@then("降级条目显示溯源不可用且报告照常生成")
def assert_degraded_citation_entry(context: dict[str, Any]) -> None:
    """[溯源不可用：检索点缺失] 条目值级 + 报告成功（降级不阻断——增强面哲学）。"""
    reader = _pdf_reader(context, key="degraded_pdf_bytes")
    full_text = _pdf_full_text(reader)
    citation_block = full_text.rsplit("切片标识", 1)[-1]
    expected_cells = f"1\n[溯源不可用：检索点缺失]\n-\n{context['missing_chunk_id'][:8]}"
    assert expected_cells in citation_block, f"降级条目 cell 序列缺失: {expected_cells!r}"
    assert context["degraded_report"].report_id is not None
    metadata = context["degraded_metadata"]
    assert metadata["citation_count"] == 1
    assert metadata["unresolvable_citation_count"] == 1
    assert metadata["citations"][0]["status"] == "point_missing"
    assert metadata["citations"][0]["chunk_id"] == context["missing_chunk_id"]


@then("全空引文附录 C 单行说明且 section_count 恒 11")
def assert_empty_citation_note(context: dict[str, Any]) -> None:
    """全空引文 → 附录 C 单行说明（恒存在哲学）+ 计数口径不漂移。"""
    full_text = _pdf_full_text(_pdf_reader(context, key="empty_pdf_bytes"))
    assert _EMPTY_CITATION_NOTE in full_text
    assert _APPENDIX_C_TITLE in full_text  # 附录 C 恒存在（空态不省略）
    assert context["empty_report"].section_count == _EXPECTED_SECTION_COUNT  # 附录 C 不计入 H3 口径
    metadata = context["empty_metadata"]
    assert metadata["citation_count"] == 0
    assert metadata["unresolvable_citation_count"] == 0


# ======================================================================
# AC-4: PDF 内部可点击导航（目录/书签/引文锚点）
# ======================================================================


@scenario(
    "test_acceptance_pdf_report.feature",
    "书签 outline 层级结构",
)
def test_outline_hierarchy() -> None:
    """S7: AC-4 书签 outline 层级（display_name 源独立构造期望）。"""
    pass


@scenario(
    "test_acceptance_pdf_report.feature",
    "目录内链与引文锚点",
)
def test_toc_links_and_citation_anchors() -> None:
    """S8: AC-4 目录 link 注释 + 引文锚点附录 C 页独占。"""
    pass


@then("PDF 书签 outline 层级与冻结章节结构一致")
def assert_outline_hierarchy(context: dict[str, Any]) -> None:
    """outline 层级序列全等（display_name 配置源独立构造期望——含 H1 题级与附录 B/C）。"""
    from src.application.ports.chain_of_thought_archive import SYNTHESIS_DISPLAY_NAME
    from src.application.ports.report_generation import REPORT_TITLE_TEMPLATE
    from src.application.services.blm_planning_prompts import (
        MARKET_INSIGHT_STEP_CONFIG,
        PERFORMANCE_GAP_CONFIG,
    )

    flat = _flatten_outline(_pdf_reader(context))
    step_titles = [cfg.display_name for cfg in MARKET_INSIGHT_STEP_CONFIG.values()]
    expected: list[tuple[int, str]] = [
        (0, REPORT_TITLE_TEMPLATE),  # H1 文档题（outline 收录面含 H1——与目录自 H2 起差异注记）
        (1, f"1 {PERFORMANCE_GAP_CONFIG.display_name}"),
        (2, "1.1 财务差距"),
        (2, "1.2 运营差距"),
        (2, "1.3 根因分析"),
        (2, "1.4 业务组合健康度"),
        (1, "2 市场洞察"),
        *[(2, f"2.{i} {name}") for i, name in enumerate(step_titles, start=1)],
        (2, f"2.7 {SYNTHESIS_DISPLAY_NAME}"),
        (1, "附录 B 降级与数据缺失记录"),
        (1, _APPENDIX_C_TITLE),  # 无快照 → 无附录 A（轻装配口径）
    ]
    actual = [(depth, title) for depth, title, _page in flat]
    assert actual == expected, f"outline 层级漂移: 实测={actual} 期望={expected}"
    for depth, title, page in flat:
        assert 0 <= page < len(_pdf_reader(context).pages)  # 每条目标页有效（锚点可解析）


@then("目录 link 注释目标锚点全部有效")
def assert_toc_links_valid(context: dict[str, Any]) -> None:
    """目录页 link 注释数 == 目录收录面（H2 章级+附录 B/C=4）+ /Dest 数组目标页全有效。"""
    reader = _pdf_reader(context)
    links = _pdf_link_targets(reader)
    page_texts = [page.extract_text() for page in reader.pages]
    toc_pages = {page for page, _ in links if "目录" in page_texts[page]}
    assert toc_pages, "目录 link 未锚定目录页"
    toc_links = [(page, target) for page, target in links if page in toc_pages]
    assert len(toc_links) == 4  # 两章 + 附录 B + 附录 C（无快照无附录 A——收录面口径）
    for _, target in links:
        assert 0 <= target < len(reader.pages)  # /Dest 数组首元素解析为有效页（R3 实证形态）


@then("引文锚点仅注册于附录 C 页")
def assert_citation_anchors_appendix_only(context: dict[str, Any]) -> None:
    """附录 C 页 link 自指锚点数 == 引文条目数 + 正文页零 link。

    断言形态（Task 0.2 复验钉死）：孤立 bookmarkPage 在 PDF 零留存——锚点承载
    = 条目行 link 注释自指（6-8 Web 阅读器可经 /Annots 寻址）；目录页与附录 C
    页分离形态下，非目录页 link 全部是引文自指锚点。
    """
    reader = _pdf_reader(context)
    links = _pdf_link_targets(reader)
    page_texts = [page.extract_text() for page in reader.pages]
    toc_pages = {page for page, _ in links if "目录" in page_texts[page]}
    assert toc_pages, "目录 link 未锚定目录页"
    non_toc_links = [(page, target) for page, target in links if page not in toc_pages]
    assert len(non_toc_links) == 1  # S4 数据面：1 条引文 → 1 个自指锚点（正文页零 link 守护）
    for page, target in non_toc_links:
        assert target == page  # 自指（条目行锚点在本页）
        assert _APPENDIX_C_TITLE in page_texts[page]  # 锚定附录 C 页


# ======================================================================
# AC-5: ReportGenerated 事件零新增复用（report_type=pdf）
# ======================================================================


@scenario(
    "test_acceptance_pdf_report.feature",
    "ReportGenerated 事件经 outbox 落行",
)
def test_report_generated_outbox_row() -> None:
    """S9: AC-5 事件 outbox 落行四键值级（report_type=pdf）。"""
    pass


@then("outbox 落行且事件四键值级匹配（report_type 为 pdf）")
def assert_outbox_four_keys(context: dict[str, Any]) -> None:
    """event_type/report_id/report_type/file_path 四键值级断言（非仅存在性）。"""
    report = context["report"]
    rows = _run_async(context["_loop"], _query_outbox_report_rows(context, str(report.report_id)))
    assert len(rows) == 1
    assert rows[0][0] == str(report.report_id)
    assert rows[0][1] == "pdf"
    assert rows[0][2] == report.file_path


# ======================================================================
# AC-6: 契约零破坏（6-5a/6-x 冻结面零触碰）
# ======================================================================


@scenario(
    "test_acceptance_pdf_report.feature",
    "读侧消费面契约键集全等",
)
def test_read_side_contract_key_sets() -> None:
    """S10: AC-6 读侧消费面契约（chain 五键 + payload 键族全等）。"""
    pass


@then("chain 读侧 records 五键结构与冻结面全等")
def assert_chain_record_keys(context: dict[str, Any]) -> None:
    """records 五键结构字面基线全等（防漂移即守护——AC-6 处方，6-5a 同款）。"""
    records = _query_chain_records(context, context["plan_id"])
    assert len(records) == 8
    for record in records:
        assert tuple(record.keys()) == _RECORD_KEY_BASELINE, f"records 键集漂移: {tuple(record.keys())}"


@then("ReportGenerated payload 键族与事件类冻结字段面全等")
def assert_event_payload_key_family(context: dict[str, Any]) -> None:
    """payload 键族与事件类冻结字段面全等（零新增守护——含 report_type 键在嵌套面）。"""
    report = context["report"]
    rows = _run_async(context["_loop"], _query_outbox_report_rows(context, str(report.report_id)))
    payload = rows[0][3]
    nested = payload["payload"]
    expected_nested = _REPORT_EVENT_PAYLOAD_KEY_BASELINE - _CORE_EVENT_PAYLOAD_KEYS
    assert set(nested.keys()) == expected_nested, f"嵌套键族漂移: {set(nested.keys())} 期望 {expected_nested}"
    assert payload["event_type"] == "ReportGenerated"
    assert payload["aggregate_id"] == str(report.report_id)
    assert payload["aggregate_type"] == "Report"


# ======================================================================
# AC-7: 性能与持久化成功率
# ======================================================================


@scenario(
    "test_acceptance_pdf_report.feature",
    "性能 P95 与成功率采样（单一数据源 20 轮）",
)
def test_performance_p95_and_success_rate() -> None:
    """S11: AC-7 性能 P95<60s + L4 对象数 20（OD-8 口径）。"""
    pass


@scenario(
    "test_acceptance_pdf_report.feature",
    "并发生成 3 个 PDF 报告互不串扰",
)
def test_concurrent_three_pdf_reports() -> None:
    """S12: AC-7 并发 3（gather 形态锚）。"""
    pass


@given("三个独立 plan_id 各自八步归档在位")
def three_plans_eight_steps_archived(context: dict[str, Any]) -> None:
    """三独立 plan_id 各自逐 stage 八步归档（并发场景数据面）。"""
    if "pdf_use_case" not in context:
        _assemble_archive_only(context)
    context["concurrent_plan_ids"] = []
    for _ in range(3):
        plan_id = str(uuid.uuid4())
        context["concurrent_plan_ids"].append(plan_id)
        context["_plan_ids"].append(plan_id)
        records = _run_async(context["_loop"], _archive_steps(context, plan_id))
        assert len(records) == 8


@when("单一数据源连续 20 次生成 PDF 报告")
def invoke_twenty_rounds(context: dict[str, Any]) -> None:
    """单一 plan_id × 20 次生成（OD-8 采样形态——每轮 L4 对象键锚 report_id 天然互异）。"""
    import time as _time

    durations: list[float] = []
    report_ids: list[str] = []
    for _ in range(_PERF_SAMPLE_ROUNDS):
        started = _time.monotonic()
        report = _generate_pdf_report(context, context["plan_id"])
        durations.append(_time.monotonic() - started)
        report_ids.append(str(report.report_id))
    context["perf_durations"] = durations
    context["perf_report_ids"] = report_ids


@when("asyncio gather 并发生成 3 个 PDF 报告")
def gather_three_concurrent_reports(context: dict[str, Any]) -> None:
    """gather 3（async 辅助函数体内 await + _run_async 驱动——6-4 形态锚）。

    会话由装配层 find 包装承担（每 find 调用独立 session_context——并发
    任务各持独立会话，AsyncSession 非并发安全的分任务防线）。
    """
    plan_ids = context["concurrent_plan_ids"]

    async def _gather() -> list[Any]:
        return await asyncio.gather(*(context["pdf_use_case"].execute(plan_id=pid) for pid in plan_ids))

    reports = _run_async(context["_loop"], _gather())
    context["concurrent_reports"] = reports
    for report in reports:
        context["_report_ids"].append(str(report.report_id))
        context["_pdf_object_keys"].append(report.file_path)


@then("每轮新 report_id 且 L2 行数、L4 对象数与 outbox 行数累计 20")
def assert_twenty_unique_reports(context: dict[str, Any]) -> None:
    """report_id 集合无重复 + L2 行 20 + L4 对象 20 + outbox 行 20（三元落位——CR1-F12③ R2 补）。"""
    assert len(set(context["perf_report_ids"])) == _PERF_SAMPLE_ROUNDS
    rows = _run_async(context["_loop"], _count_report_rows(context, context["plan_id"]))
    assert rows == _PERF_SAMPLE_ROUNDS
    objects = _run_async(context["_loop"], _count_pdf_objects(context, context["plan_id"]))
    assert objects == _PERF_SAMPLE_ROUNDS
    outbox = _run_async(context["_loop"], _count_outbox_rows(context, context["plan_id"]))
    assert outbox == _PERF_SAMPLE_ROUNDS


@then("生成窗口 P95 小于 60 秒且三元每轮可读回")
def assert_p95_and_readback(context: dict[str, Any]) -> None:
    """sorted(durations)[ceil(0.95*20)-1] < 60s + 每轮 L4 读回（_generate_pdf_report 内置）。"""
    durations = context["perf_durations"]
    ordered = sorted(durations)
    p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
    assert p95 < _PERF_P95_LIMIT_SECONDS, f"P95 实测={p95:.3f}s 期望<{_PERF_P95_LIMIT_SECONDS}s"


@then("三报告全部成功且对象行事件三元互不串扰")
def assert_three_reports_isolated(context: dict[str, Any]) -> None:
    """三 plan_id 三元互不串扰（plan↔report 一一对应 + 对象键互异集合——值级形态）。"""
    reports = context["concurrent_reports"]
    assert len(reports) == 3
    report_ids = {str(report.report_id) for report in reports}
    assert len(report_ids) == 3
    object_keys = {report.file_path for report in reports}
    assert len(object_keys) == 3  # 对象键互异（键锚 report_id）
    for plan_id, report in zip(context["concurrent_plan_ids"], reports):
        assert report.plan_id == plan_id  # plan_id↔report_id 一一对应
        rows = _run_async(context["_loop"], _count_report_rows(context, plan_id))
        assert rows == 1, f"并发三元串扰: plan={plan_id} rows={rows}"
        outbox = _run_async(context["_loop"], _query_outbox_report_rows(context, str(report.report_id)))
        assert len(outbox) == 1  # 事件三元——每 report 恰一行


# ======================================================================
# 收尾: 交付件存在性验收
# ======================================================================


@scenario(
    "test_acceptance_pdf_report.feature",
    "Story 交付件存在性收尾验收",
)
def test_story_deliverables_existence() -> None:
    """S13: 收尾交付件存在性逐项断言。"""
    pass


@given("开发实施完成")
def development_completed() -> None:
    """S13 收尾场景前置（静态断言无服务依赖）。"""


@then("src 交付件（VO/异常/端口/服务/用例/渲染器/CLI/组合根）逐项存在")
def assert_src_deliverables(context: dict[str, Any]) -> None:
    """src 9 项交付件存在性逐项断言。"""
    deliverables = (
        "src/domain/value_objects/citation_entry.py",
        "src/domain/exceptions/report_exceptions.py",
        "src/application/ports/pdf_report.py",
        "src/application/services/pdf_report_generation_service.py",
        "src/application/use_cases/generate_pdf_report.py",
        "src/infrastructure/reporting/__init__.py",
        "src/infrastructure/reporting/reportlab_pdf_renderer.py",
        "src/entrypoints/agent_cli.py",
        "src/composition_root.py",
    )
    for relative in deliverables:
        assert (_REPO_ROOT / relative).exists(), f"src 交付件缺失: {relative}"


@then("四测试目录交付件逐项存在")
def assert_test_deliverables(context: dict[str, Any]) -> None:
    """四测试目录交付件存在性逐项断言。"""
    deliverables = (
        "tests/unit/domain/test_citation_entry.py",
        "tests/unit/domain/exceptions/test_report_exceptions.py",
        "tests/unit/infrastructure/reporting/test_reportlab_pdf_renderer.py",
        "tests/unit/application/test_pdf_report_generation_service.py",
        "tests/unit/application/use_cases/test_generate_pdf_report_use_case.py",
        "tests/unit/interfaces/cli/test_agent_cli.py",
        "tests/unit/architecture/test_pdf_report.py",
        "tests/integration/test_integration_pdf_report.py",
        "tests/contracts/test_port_contract_pdf_report.py",
        "tests/contracts/test_event_channel_mapping_pdf_report.py",
        "tests/acceptance/test_acceptance_pdf_report.feature",
        "tests/acceptance/test_acceptance_pdf_report.py",
    )
    for relative in deliverables:
        assert (_REPO_ROOT / relative).exists(), f"测试交付件缺失: {relative}"
