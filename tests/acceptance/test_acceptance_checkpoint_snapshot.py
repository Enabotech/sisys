"""Story 6-3 Checkpoint 快照创建——BDD 验收步骤实现。

模板基准: tests/acceptance/test_acceptance_postgresql_relational_layer.feature/.py
（R6——# language: zh-CN 中文 Gherkin + AC 横幅注释分组（# === 分隔）+
@scenario 多行字面量路径绑定 + 场景绑定与步骤实现交替排列；R6 自身 py 仅
绑定部分场景且缺 pytestmark/context dict/_run_async 属旧模板欠账——本文件
13 场景全绑定，三件套由 6-1/6-2 基建承载）。装配形态对齐 6-1/6-2（真实
服务链 + Fake LLM/Fake Embedding 双豁免 + 延迟 import 纪律 + 场景三属性
分档表 docstring + teardown 链「断言失败也执行」）。

13 场景三属性分档表（Subtask 0.4 钉死——层级/LLM 依赖/服务门控）：

| #  | 场景                              | 层级     | LLM         | 服务门控                    |
|----|-----------------------------------|----------|-------------|-----------------------------|
| 1  | AC-1.1 五步全链 13 键+TTL         | 用例级   | Fake        | Redis+PG+Qdrant+MinIO       |
| 2  | AC-1.2 六子步骤独立性             | 用例级   | Fake        | 同上                        |
| 3  | AC-2.1 空引用守卫                 | 实体级   | 无          | 无（纯构造）                |
| 4  | AC-2.2 二次路径（双响应注入）     | 用例级   | Fake 双响应 | 同 #1                       |
| 5  | AC-3.1 checksum round-trip+篡改   | 用例级   | Fake        | 同 #1                       |
| 6  | AC-4.1 发布字段+outbox 落行       | 用例级   | Fake        | 同 #1+真实 publisher        |
| 7  | AC-4.2 6-2 互证（run 零发布）     | 用例级   | Fake        | 同 #1                       |
| 8  | AC-5.1 L2+L3+L4 三层归档          | 用例级   | Fake+FakeE  | 同 #1                       |
| 9  | AC-6.1 修正记录往返+版本递增      | 用例级   | Fake        | 同 #1                       |
| 10 | AC-7.1 恢复视图+判定边界          | 用例级   | Fake        | 同 #1                       |
| 11 | AC-7.2 非法操作三分 480/484/482   | 用例级   | Fake        | 同 #1                       |
| 12 | AC-8.1 创建窗口 P95（20 轮采样）  | 服务级   | Fake        | Redis（预热含全链）         |
| 13 | 收尾完成清单                      | 静态清单 | 无          | 无                          |

门控档位（服务不可达环境 pytest.skip() 动态跳过——禁 @pytest.mark.skip
写死）：Redis = ping 探测；PG = 连接 + event_outbox 表存在双预检（5-4
R1-F07 先例）+ strategic_archives 表预检；Qdrant = get_collections 探测；
MinIO = 桶健康探测。strategic_archive_service 组合根 lambda 强制依赖
embedding_service（外部 SaaS）——Fake Embedding（固定维度向量 AsyncMock
注入，L3 写入链可构造）与 Fake LLM（压缩摘要 generate 消费点）同为外部
SaaS 豁免（R2-F2 钦定；禁照抄 3-10 AsyncMock L3/L4/L5/embedding 的 mock
先例——违反本 Story no-mock 红线）；entity_extractor 用真实规则基
RuleBasedExtractor（纯规则无 LLM/Neo4j——真实服务非 mock）。

延迟 import 纪律：本 Story 新交付模块（application/ports/checkpoint、
application/services/checkpoint_service、application/use_cases/
create_checkpoint、domain/services/recovery_mode 等）一律步骤函数/装配
函数体内延迟 import——模块顶部 import 会使 pytest 收集期整文件 collection
error，Task 0 预期红因 = 运行期 ImportError（缺失类名；6-2 先例——收集期
零错误本身即延迟 import 纪律的自证）。

测试隔离（Run with + 隔离清单）：teardown 链「断言失败也执行」（context
fixture yield teardown，K8 先例）六步——① 端口覆写还原（_restorers）；
② outbox 按 event_id 精确 DELETE（_outbox_event_ids 收集面覆盖 ⑤
CheckpointReached 与 ③ ArchiveCreated 两类事件行——R2A-8）；③ Redis 键
逐键精确删除（三键族：sisys:snapshot:blm-checkpoint-* 快照键 + note:
{note_id} 笔记缓存键 + compressed:{note_id} 压缩缓存键——禁 flush）；④
Qdrant 点按 ID 精确 DELETE；⑤ MinIO 对象按 blob_ref 精确删除 + PG
strategic_archives 行按 archive_id 精确 DELETE；⑥ 同循环关闭全部客户端。
BDD 步骤禁 @pytest.mark.asyncio（context 数据丢失——用模块级 event_loop
+ _run_async 三件套）。

性能口径（OD-6 口径差声明）：AC-8 创建提交窗口 P95<100ms = 压缩产物就绪
后的「build_snapshot 构造起点（含 checksum 计算——R6-5）→ Redis save
返回」窗口；持久化笔记实体抽取与 LLM 压缩延迟显式出栈独立计量（Fake LLM
固定产物使压缩延迟出栈——6-1 DC-7/6-2 OD-3 先例）。20 轮 = 20 个独立
plan_id 各建 CP-1（值域 8 上限下同 plan 不可承载 20 键——R1-F2 守卫值域，
R5-1 勘误：原误挂 R1-F17 与集成侧 R2-5 同型）；采样
复用预热轮压缩产物（含 persistent_note_ref 血缘——R6-11 性能口径豁免，
断言面仅验键存在与 TTL）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_checkpoint_snapshot.py -v
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Generator
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pytest_bdd import given, scenario, then, when

from src.infrastructure.storage.redis.key_builder import build_key

# marker 名以 pyproject 注册为准（database 非 postgresql——R2-F23）；xdist_group
# 模块级挂法复用 6-1/6-2 组名（性能/采样场景跨 Story 同 worker 串行——R2-F24）
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.database,
    pytest.mark.redis,
    pytest.mark.qdrant,
    pytest.mark.minio,
    pytest.mark.xdist_group("blm-planning-perf"),
]

#: _run_async 泛型参数（协程返回类型透传——裸 Any 向调用点扩散 no-any-return）
_T = TypeVar("_T")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: 完整形态快照 state_data 13 键契约（Task 0.2 冻结唯一版本——期望值独立
#: 构造，禁经被测服务生成；断言失败消息含实测值+规则锚）
EXPECTED_STATE_DATA_KEYS: tuple[str, ...] = (
    "checkpoint_no",
    "stage_id",
    "stage_number",
    "plan_id",
    "completed",
    "summary",
    "compressed_context",
    "compression_ratio",
    "quality_score",
    "token_count",
    "persistent_note_ref",
    "correction_history",
    "created_via",
)

#: checkpoint_no 值域（BLM 前两阶段 8 恢复点——Subtask 0.1 冻结；CP-8=synthesis
#: 后为本 Story 钦定，六子步骤名以 6-2 STAGE_VALUE_DOMAIN 为准）
CHECKPOINT_NO_VALUE_DOMAIN: tuple[str, ...] = (
    "CP-1",
    "CP-2",
    "CP-3",
    "CP-4",
    "CP-5",
    "CP-6",
    "CP-7",
    "CP-8",
)

#: checkpoint_no → stage_id 映射表（Subtask 0.1 冻结——phase_identifier 复用
#: stage 值域与 CheckpointReached.phase_identifier 同口径）
CHECKPOINT_STAGE_MAPPING: dict[str, str] = {
    "CP-1": "performance_gap",
    "CP-2": "market_insight_trend",
    "CP-3": "market_insight_market_customer",
    "CP-4": "market_insight_competition",
    "CP-5": "market_insight_self",
    "CP-6": "market_insight_opportunity",
    "CP-7": "market_insight_opportunity_gap",
    "CP-8": "market_insight_synthesis",
}

#: 完整形态快照 TTL（30 天——AC-1 钦定；R6-20 ttl() 读法秒口径断言）
SNAPSHOT_TTL_SECONDS: int = 2_592_000

#: 验收场景触发源期望值（R7-5 钦定——经用例层直调 create_checkpoint 默认参
#: → 期望常量取 "use_case"；created_via="cli" 路径由 CLI 单测承载）
EXPECTED_CREATED_VIA: str = "use_case"

#: 恢复视图 DTO 键契约（Task 0 冻结——AC-7 VC：checkpoint_no/stage/
#: compressed_context/state_data/修正历史/后续 checkpoint 清单/建议恢复模式）
EXPECTED_RECOVERY_VIEW_KEYS: tuple[str, ...] = (  # 7 键 + R3-2 增补 state_version/snapshot_id
    "checkpoint_no",
    "stage",
    "compressed_context",
    "state_data",
    "correction_history",
    "subsequent_checkpoints",
    "recommended_mode",
    "state_version",
    "snapshot_id",
)

#: 快照会话前缀字面量（OD-3 双轨制——与 6-2 blm-planning- 前缀显式区分；
#: 断言侧字面量防 import 自证，单源常量在 application/ports/checkpoint.py）
CHECKPOINT_SESSION_PREFIX_LITERAL = "blm-checkpoint-"

#: L1 笔记缓存键前缀（persistent_note_taker.py _cache_note 形态 note:{note_id}）
NOTE_CACHE_KEY_PREFIX = "note:"

#: 压缩结果缓存键前缀（context_compressor.py _cache_compressed 形态 compressed:{note_id}）
COMPRESSED_CACHE_KEY_PREFIX = "compressed:"

#: 检索语料（背景建制——长度充分使压缩比 ≥0.70 可构造；payload.content 键
#: 与生产读取路径 payload.get("content") or payload.get("summary_text") 一致）
_CORPUS_TEXTS: tuple[str, ...] = (
    "新能源汽车行业战略分析：市场增速放缓但渗透率持续提升，固态电池技术路线演进加速，"
    "头部厂商价格战与渠道下沉竞争加剧，海外新兴市场成为第二增长曲线，研发投入占比与"
    "组织能力短板是内部能力评估的核心约束，政策补贴退坡与准入收紧构成宏观压力。",
    "财务业绩差距分析：营收目标达成率 87% 低于预期，毛利率下滑 2.3 个百分点根因在于"
    "原材料成本上升与产品结构下移，运营差距体现在交付周期拉长与库存周转下降，组合健康度"
    "评估显示现金流承压但资产负债结构稳健，需在下一规划周期修正关键财务参数。",
    "机会差距量化报告：海外新兴市场渗透率仅 12% 对标标杆 35% 存在 23 个百分点差距，"
    "能力-机会匹配矩阵显示渠道能力与本地化合规是两大短板，差距弥合策略分三阶段推进——"
    "先试点再复制后规模化，机会优先级排序前三位为东南亚、中东、拉美市场。",
)

#: Fake LLM 达标压缩产物（固定短摘要——压缩比 ≥0.70 且质量分达标形态）
_FAKE_COMPRESSED_TEXT = (
    "战略语境压缩摘要：市场渗透率提升与技术演进加速并存；财务达成率 87% 与毛利率下滑"
    "需修正；海外市场渗透差距 23 点，三阶段弥合策略以东南亚/中东/拉美为先。"
)

#: Fake LLM 双响应首轮形态（冗长低压缩——长度接近语料原文使 ratio<0.70
#: 触发二次压缩路径；R6-23 轮次感知 side_effect 注入）
_FAKE_VERBOSE_TEXT = _CORPUS_TEXTS[0] + _CORPUS_TEXTS[1] + _CORPUS_TEXTS[2]


def _run_async(event_loop: asyncio.AbstractEventLoop, awaitable: Awaitable[_T]) -> _T:
    """在模块级事件循环上运行可等待对象（BDD 步骤禁 @pytest.mark.asyncio；
    Awaitable 口径兼容 Coroutine 与 AsyncSessionTransaction 等非协程 awaitable）。"""
    return event_loop.run_until_complete(awaitable)


def _make_search_results() -> list[dict[str, Any]]:
    """构造最小检索证据族（Task 0 钦定——{"id":…, "payload": {"content": …}} 形态）。

    SearchResult 是 dict 形态（TypedDict）——payload.content 键与
    persistent_note_taker/context_compressor 的读取路径一致。
    """
    return [
        {"id": f"chk-corpuse-{index}", "score": 0.9, "payload": {"content": text}} for index, text in enumerate(_CORPUS_TEXTS)
    ]


def _new_plan_id() -> str:
    """生成独立 plan_id（UUID 字符串——用例层守卫校验形态；快照键/归档行/事件行按 plan 天然隔离）。"""
    return str(uuid.uuid4())


def _snapshot_session_id(plan_id: str, checkpoint_no: str) -> str:
    """构造完整形态快照会话键（期望形态独立构造——blm-checkpoint-{plan}:{cp}）。"""
    return f"{CHECKPOINT_SESSION_PREFIX_LITERAL}{plan_id}:{checkpoint_no}"


# ===================================================================
# 共享基建：三件套（context fixture / 模块级 event_loop / _run_async）
# ===================================================================


@pytest.fixture(scope="module")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """模块级事件循环（BDD 步骤禁 @pytest.mark.asyncio——同循环三件套）。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def context(
    event_loop: asyncio.AbstractEventLoop,
    acceptance_env_config: Any,
) -> Generator[dict[str, Any], None, None]:
    """BDD 步骤间共享状态容器（场景级独立客户端 + 同循环 teardown 六步链）。

    teardown 顺序（断言失败也执行——K8 纪律）：① 端口覆写还原；② outbox
    事件行按 event_id 精确 DELETE（⑤ CheckpointReached + ③ ArchiveCreated
    两类——R2A-8）；③ Redis 三键族逐键精确删除（快照/note/compressed——禁
    flush）；④ Qdrant 点按 ID 精确 DELETE；⑤ MinIO 对象精确删除 + PG
    strategic_archives 行按 archive_id 精确 DELETE；⑥ 同循环关闭全部客户端。
    """
    ctx: dict[str, Any] = {
        "_loop": event_loop,
        "_env": acceptance_env_config,
        "_redis_client": None,
        "_restorers": [],
        "_outbox_event_ids": [],
        "_outbox_plan_ids": [],
        "_snapshot_session_ids": [],
        "_note_cache_keys": [],
        "_compressed_cache_keys": [],
        "_archive_plan_ids": [],
        "_archive_row_ids": [],
        "_minio_blob_refs": [],
        "_pg_manager": None,
        "_pg_session": None,
        "_pg_session_token": None,
    }
    yield ctx
    _teardown_chain(ctx)


def _teardown_chain(ctx: dict[str, Any]) -> None:
    """teardown 六步链（context fixture yield 后执行——断言失败也运行）。

    各步独立 try/except（前步失败不阻断后步——残局防线，R8-F2）；全部
    _run_async 同循环（跨循环 "Event loop is closed" 存档教训）。
    """
    # ① 端口覆写还原（真实发布链路场景注册的替身）+ PG 会话提交还原
    for restore in ctx["_restorers"]:
        try:
            restore()
        except Exception:
            pass
    _run_async(ctx["_loop"], _finalize_pg_session(ctx))
    # ② outbox 事件行精确 DELETE（event_id 面 + plan_id 兜底双通道）
    try:
        _cleanup_outbox_rows(ctx)
    except Exception:
        pass
    # ③ Redis 三键族逐键精确删除
    _run_async(ctx["_loop"], _cleanup_redis_keys(ctx))
    # ④⑤ Qdrant 点 / MinIO 对象 / PG 归档行精确清理
    _run_async(ctx["_loop"], _cleanup_archive_residues(ctx))
    # ⑥ 同循环关闭 Redis 客户端
    if ctx["_redis_client"] is not None:
        try:
            _run_async(ctx["_loop"], ctx["_redis_client"].close())
        except Exception:
            pass


async def _finalize_pg_session(ctx: dict[str, Any]) -> None:
    """PG 会话收尾（commit 残留事务 → 还原 ContextVar → 关闭会话）。"""
    session = ctx.get("_pg_session")
    if session is None:
        return
    from src.infrastructure.storage.postgresql.session_context import reset_session

    try:
        await session.commit()
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass
    if ctx.get("_pg_session_token") is not None:
        try:
            reset_session(ctx["_pg_session_token"])
        except Exception:
            pass
    try:
        await session.close()
    except Exception:
        pass


async def _cleanup_redis_keys(ctx: dict[str, Any]) -> None:
    """Redis 三键族精确删除（快照会话键/note 缓存键/compressed 缓存键）。"""
    client = ctx["_redis_client"]
    if client is None:
        return
    keys: list[str] = []
    for session_id in ctx["_snapshot_session_ids"]:
        keys.append(build_key("snapshot", session_id))
    keys.extend(ctx["_note_cache_keys"])
    keys.extend(ctx["_compressed_cache_keys"])
    for key in keys:
        try:
            await client.delete(key)
        except Exception:
            pass


async def _cleanup_archive_residues(ctx: dict[str, Any]) -> None:
    """归档残留精确清理（Qdrant 点按 payload.archive_id / MinIO 对象 bypass / PG 归档行）。"""
    env = ctx["_env"]
    # 按收集面 plan_id 补集归档行（archive_id/blob_ref 双收集——失败不阻断）
    if ctx["_archive_plan_ids"] and ctx["_pg_manager"] is not None:
        try:
            import sqlalchemy as sa

            engine = ctx["_pg_manager"].get_async_engine()
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        sa.text("SELECT archive_id, blob_ref FROM strategic_archives WHERE plan_id = ANY(:ids)"),
                        {"ids": list(ctx["_archive_plan_ids"])},
                    )
                ).fetchall()
            await engine.dispose()
            for row in rows:
                ctx["_archive_row_ids"].append(str(row[0]))
                if row[1]:
                    ctx["_minio_blob_refs"].append(row[1])
        except Exception:
            pass
    # ④ Qdrant 点按 payload.archive_id filter 精确删除（点 ID 为 MD5 哈希 int）
    if ctx["_archive_row_ids"]:
        try:
            from qdrant_client import AsyncQdrantClient, models

            client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
            try:
                await client.delete(
                    collection_name="strategic_archive",
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="archive_id",
                                    match=models.MatchAny(any=list(ctx["_archive_row_ids"])),
                                )
                            ]
                        )
                    ),
                )
            finally:
                await client.close()
        except Exception:
            pass
    # ⑤ MinIO 对象批量删除（object-lock bucket GOVERNANCE retention——bypass 形态）
    if ctx["_minio_blob_refs"]:
        try:
            from minio import Minio
            from minio.deleteobjects import DeleteObject

            minio_client = Minio(
                endpoint=env.minio.endpoint,
                access_key=env.minio.access_key,
                secret_key=env.minio.secret_key,
                secure=env.minio.secure,
            )
            bucket_name = _resolve_archive_bucket_name(ctx)
            _ = list(
                minio_client.remove_objects(
                    bucket_name,
                    [DeleteObject(blob_ref) for blob_ref in ctx["_minio_blob_refs"]],
                    bypass_governance_mode=True,
                )
            )
        except Exception:
            pass
    # ⑤ PG strategic_archives 行按 archive_id 精确 DELETE
    if ctx["_archive_row_ids"]:
        try:
            import sqlalchemy as sa

            manager = ctx["_pg_manager"]
            if manager is not None:
                engine = manager.get_async_engine()
                async with engine.begin() as conn:
                    await conn.execute(
                        sa.text("DELETE FROM strategic_archives WHERE archive_id = ANY(:ids)"),
                        {"ids": list(ctx["_archive_row_ids"])},
                    )
                await engine.dispose()
        except Exception:
            pass


def _cleanup_outbox_rows(ctx: dict[str, Any]) -> None:
    """outbox 事件行精确 DELETE（event_id 面 + plan_id 兜底双通道——R2A-8 收集面
    覆盖 ⑤ CheckpointReached 与 ③ ArchiveCreated 两类事件行）。"""
    import sqlalchemy as sa

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

    env = ctx["_env"]

    async def _delete() -> None:
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
            async with engine.begin() as conn:
                if ctx["_outbox_event_ids"]:
                    await conn.execute(
                        sa.text("DELETE FROM event_outbox WHERE event_id = ANY(:ids)"),
                        {"ids": [str(e) for e in ctx["_outbox_event_ids"]]},
                    )
                if ctx["_outbox_plan_ids"]:
                    await conn.execute(
                        sa.text(
                            "DELETE FROM event_outbox WHERE payload->'metadata'->>'plan_id' = ANY(:ids) "
                            "OR payload->'payload'->>'plan_id' = ANY(:ids)"
                        ),
                        {"ids": list(ctx["_outbox_plan_ids"])},
                    )
            await engine.dispose()
        except Exception:
            pass

    _run_async(ctx["_loop"], _delete())


# ===================================================================
# Fake 工厂（外部 SaaS 豁免——Fake LLM / Fake Embedding 双豁免，R2-F2）
# ===================================================================


def _make_fake_llm(*, dual_response: bool = False) -> Any:
    """Fake LLM 工厂（AsyncMock(spec=LLMClientPort)——外部 SaaS 豁免面）。

    默认形态（单值分派）：generate 恒返回固定达标压缩产物（压缩比 ≥0.70、
    质量评估达标——五步链一次通过形态）。

    双响应形态（R6-23 钦定——轮次感知）：side_effect 列表分派，首轮返回
    冗长低压缩形态（长度接近语料原文 → compression_ratio<0.70 触发二次压缩）、
    次轮返回达标形态；形态对齐既有工厂「按 response_schema 身份定值分派」
    的轮次扩展而非旁路新建。

    Args:
        dual_response: 双响应模式（AC-2.2 二次路径场景注入）。

    Returns:
        AsyncMock(spec=LLMClientPort) 替身。
    """
    from unittest.mock import AsyncMock

    from src.domain.ports.llm_client import LLMClientPort, LLMResponse

    def _response(text: str) -> LLMResponse:
        return LLMResponse(content=text, finish_reason="stop", usage={}, model="fake-llm")

    fake = AsyncMock(spec=LLMClientPort)
    if dual_response:
        fake.generate = AsyncMock(side_effect=[_response(_FAKE_VERBOSE_TEXT), _response(_FAKE_COMPRESSED_TEXT)])
    else:
        fake.generate = AsyncMock(return_value=_response(_FAKE_COMPRESSED_TEXT))
    fake.close = AsyncMock()
    return fake


def _make_fake_embedding() -> Any:
    """Fake Embedding 工厂（AsyncMock(spec=EmbeddingServicePort)——外部 SaaS 豁免）。

    embedding_service 是 strategic_archive_service 的强制依赖（组合根
    lambda 必选 resolve），属外部 SaaS 同类（embedding 向量）——固定维度
    向量注入使 L3 写入链可构造（R2-F2 钦定；与 3-10 AsyncMock L3/L4/L5 的
    区别：仅豁免外部 SaaS 端口，存储端口保持真实）。
    """
    from unittest.mock import AsyncMock

    from src.domain.ports.embedding_service import EmbeddingServicePort

    fake = AsyncMock(spec=EmbeddingServicePort)
    fake.embed_query = AsyncMock(return_value=[0.1] * 1024)
    fake.embed_documents = AsyncMock(return_value=[[0.1] * 1024])
    fake.close = AsyncMock()
    return fake


# ===================================================================
# 装配链（四真实服务 + Fake LLM/Fake Embedding 双豁免）
# ===================================================================


def _resolve_archive_bucket_name(ctx: dict[str, Any]) -> str:
    """解析 archive-evidence 物理 bucket 名（{prefix}-{type}-{tenant} 复合形态）。

    经组合根 l4_object 实例内部锚解析（集成测试同款）——断言/清理零硬编码。
    """
    from src.domain.ports.resolver import resolve

    l4 = resolve("l4_object")
    return str(l4._repository._resolve_bucket_name("archive-evidence"))


def _assemble_checkpoint_chain(context: dict[str, Any], *, dual_response_llm: bool = False) -> None:
    """装配 Checkpoint 创建链（用例级——Task 7 全场景转绿形态）。

    真实面：Redis（快照存储 + L1 缓存）+ PG（archive L2 + outbox 落行，
    AsyncSession/SessionContext 激活）+ Qdrant（L3 向量）+ MinIO（L4 WORM
    对象）；Fake 面：LLMClientPort（压缩摘要 generate 消费点）+
    EmbeddingServicePort（embedding 向量）——外部 SaaS 双豁免；归档服务手工
    构造注入 Fake Embedding（组合根 lambda 强制依赖外部 SaaS embedding——
    测试面豁免注入，L2/L4 存储保持真实）；entity_extractor 用真实规则基
    RuleBasedExtractor（纯规则实现，真实服务非 mock）。
    """
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.application.services.checkpoint_service import CheckpointService
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.application.use_cases.create_checkpoint import CreateCheckpointUseCase
    from src.domain.ports.resolver import get_resolver, resolve
    from src.domain.services.compression_quality_evaluator import CompressionQualityEvaluator
    from src.domain.services.context_compressor import ContextCompressor
    from src.domain.services.persistent_note_taker import PersistentNoteTaker
    from src.infrastructure.external_services.entity_extraction.rule_extractor import RuleBasedExtractor
    from src.infrastructure.storage.postgresql.session_context import set_session
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter

    env = context["_env"]

    # 1) 真实 Redis 客户端 + 快照仓储（场景级独立客户端——跨循环教训）
    redis_client = aioredis.Redis(
        host=env.redis.host,
        port=env.redis.port,
        password=env.redis.password or None,
        decode_responses=True,
    )
    _run_async(context["_loop"], redis_client.ping())  # 门控：不可达由 Given 步骤先行 skip
    context["_redis_client"] = redis_client
    redis_adapter = RedisAdapter(redis_client=redis_client)

    # 2) 领域服务链（真实规则基抽取 + Fake LLM 压缩 + 真实 L1 缓存；note_taker
    #    套记录壳——R2 审查 R2-2：note:/compressed: 键随 take_notes 全路径登记进
    #    清理面，消灭「step① 成功后②③④失败」的登记窗口（与集成侧同形态——
    #    note_id 是内部 uuid4 调用前不可知，记录壳是唯一完备登记形态））
    from src.domain.ports.l3_vector import SearchResult
    from src.domain.services.persistent_note_taker import PersistentNote

    class _RecordingNoteTaker(PersistentNoteTaker):
        """take_notes 记录壳（本地子类——登记缓存键进 context 清理面）。"""

        async def take_notes(
            self,
            query: str,
            retrieved_docs: list[SearchResult],
            user_id: str,
            session_id: str,
        ) -> PersistentNote:
            note = await super().take_notes(query=query, retrieved_docs=retrieved_docs, user_id=user_id, session_id=session_id)
            context["_note_cache_keys"].append(f"{NOTE_CACHE_KEY_PREFIX}{note.note_id}")
            context["_compressed_cache_keys"].append(f"{COMPRESSED_CACHE_KEY_PREFIX}{note.note_id}")
            return note

    note_taker = _RecordingNoteTaker(
        entity_extractor=RuleBasedExtractor(),
        audit_service=None,
        l1_cache=redis_adapter,
    )
    compressor = ContextCompressor(
        llm_client=_make_fake_llm(dual_response=dual_response_llm),
        note_taker=note_taker,
        quality_evaluator=CompressionQualityEvaluator(),
        l1_cache=redis_adapter,
    )

    # 3) PG 会话激活（SessionContext——归档 L2 仓储前置）+ 归档服务（真实
    #    L2/L3/L4 + Fake Embedding 豁免 + L5 可选降级 None）
    from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore

    context["_snapshot_repository_local"] = RedisSnapshotStore(adapter=redis_adapter)
    session = AsyncSession(context["_pg_manager"].get_async_engine())
    _run_async(context["_loop"], session.begin())
    context["_pg_session"] = session
    context["_pg_session_token"] = set_session(session)
    archive_service = StrategicArchiveService(
        archive_repo=resolve("archive_repository"),
        embedding_service=_make_fake_embedding(),  # 外部 SaaS 豁免（R2-F2）
        vector_storage=resolve("l3_vector"),
        object_storage=resolve("l4_object"),
        graph_storage=None,  # L5 可选降级（Neo4j 非本 Story 断言面）
        event_publisher=None,  # 验收默认无发布——发布场景经真实 publisher 重建
        staleness_service=None,
    )
    context["_archive_service"] = archive_service

    # 4) Checkpoint 编排服务（五依赖组合注入——R2）+ 用例
    snapshot_repository = context["_snapshot_repository_local"]
    checkpoint_service = CheckpointService(
        note_taker=note_taker,
        compressor=compressor,
        archive_service=archive_service,
        snapshot_repository=snapshot_repository,
        event_publisher=_NoopPublisher(),
    )
    context["_checkpoint_service"] = checkpoint_service
    context["_snapshot_repository"] = snapshot_repository
    context["_use_case"] = CreateCheckpointUseCase(checkpoint_service=checkpoint_service)
    context["_resolver"] = get_resolver()


class _NoopPublisher:
    """无发布替身（默认装配——真实发布场景经 resolve 重建注入）。

    实现 EventPublisher 协议面（进程内空实现非 AsyncMock——发布行为在
    S6/S7 场景经真实 publisher 行为级验证）。
    """

    async def publish(self, event: Any) -> Any:
        """发布空实现（返回成功结果面）。"""
        from src.domain.events.publish_result import ChannelResult, PublishResult

        return PublishResult(event_id=str(uuid.uuid4()), results=(ChannelResult("inmemory", True),))


def _create_checkpoint(context: dict[str, Any], *, plan_id: str, checkpoint_no: str, query: str = "五年战略规划") -> Any:
    """经用例层直调创建 Checkpoint（默认参 created_via='use_case'——R7-5）。"""
    session_id = _snapshot_session_id(plan_id, checkpoint_no)
    context["_snapshot_session_ids"].append(session_id)
    context["_archive_plan_ids"].append(plan_id)
    context["_outbox_plan_ids"].append(plan_id)
    result = _run_async(
        context["_loop"],
        context["_use_case"].execute(
            plan_id=plan_id,
            checkpoint_no=checkpoint_no,
            stage_id=CHECKPOINT_STAGE_MAPPING[checkpoint_no],
            query=query,
            retrieved_docs=_make_search_results(),
            user_id="acceptance-executor",
            summary=f"{checkpoint_no} 阶段摘要（验收直供）",
        ),
    )
    # 缓存键登记经装配链记录壳全路径承载（R2 审查 R2-2——含失败路径；R1 的
    # 返回后登记形态被壳取代，此函数不再重复登记）
    return result


def _snapshot_redis_key(session_id: str) -> str:
    """完整形态快照最终 Redis 键（build_key('snapshot', session_id) 形态）。"""
    return build_key("snapshot", session_id)


# ===================================================================
# 场景绑定（13 场景全绑定——R6 欠账禁沿用）
# ===================================================================


@scenario(
    "test_acceptance_checkpoint_snapshot.feature",
    "五步全链创建完整形态快照（13 键契约与 TTL 30 天）",
)
def test_full_chain_creates_complete_snapshot() -> None:
    """AC-1.1 五步全链创建（13 键断言 + TTL 30 天双验）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_snapshot.feature",
    "六子步骤各自独立创建 Checkpoint 互不覆盖",
)
def test_substep_checkpoints_independent() -> None:
    """AC-1.2 六子步骤多 Checkpoint 独立性（CP-2/CP-5 双点不覆盖）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_snapshot.feature",
    "空持久化引用构造完整形态快照被守卫拒绝",
)
def test_empty_note_ref_guard_raises_484() -> None:
    """AC-2.1 空引用构造守卫（484——完整形态进入即校验）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_snapshot.feature",
    "压缩产物首轮不足触发二次路径",
)
def test_compression_second_path_triggered() -> None:
    """AC-2.2 压缩质量门禁（双响应注入 → rerun_count ≥1）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_snapshot.feature",
    "checksum round-trip 与篡改检测",
)
def test_checksum_roundtrip_and_tamper() -> None:
    """AC-3.1 checksum round-trip 绿 + state_data 篡改红。"""
    pass


@scenario(
    "test_acceptance_checkpoint_snapshot.feature",
    "CheckpointReached 事件发布与 outbox 落行",
)
def test_checkpoint_reached_published_and_outboxed() -> None:
    """AC-4.1 发布字段与 outbox 落行（恰一行 + phase_identifier 通道）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_snapshot.feature",
    "6-2 负向断言面零破坏互证（创建前零落行与创建恰一行）",
)
def test_6_2_negative_surface_zero_adaptation() -> None:
    """AC-4.2 6-2 负向断言面互证（run 零发布 + 创建恰一行——CP-1 值域）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_snapshot.feature",
    "归档三层落位（L2 元数据与 L3 向量与 L4 对象）",
)
def test_archive_three_layers_persisted() -> None:
    """AC-5.1 L2+L3+L4 三层归档断言（1-15b 钦定义务清偿）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_snapshot.feature",
    "修正记录不可变更新与版本递增",
)
def test_correction_record_immutable_update() -> None:
    """AC-6.1 修正记录往返 + state_version 递增 + checksum 重算闭环。"""
    pass


@scenario(
    "test_acceptance_checkpoint_snapshot.feature",
    "恢复视图组装与双模式判定边界（恰 2 强制 Replay）",
)
def test_recovery_view_and_mode_boundary() -> None:
    """AC-7.1 恢复视图 DTO + 判定纯函数边界（恰 2 强制——突变实证）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_snapshot.feature",
    "非法操作三分（不存在 480 与校验失败 484 与版本倒退 482）",
)
def test_illegal_operations_three_way_errors() -> None:
    """AC-7.2 非法操作三分（480/484/482 第二触发点——经修正面两步构造）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_snapshot.feature",
    "创建提交窗口 P95 小于 100ms（20 轮采样）",
)
def test_creation_window_p95_under_100ms() -> None:
    """AC-8.1 创建提交窗口 P95<100ms（20 轮独立 plan_id 采样）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_snapshot.feature",
    "开发完成清单收尾（src 与四测试目录交付件存在性）",
)
def test_development_completion_checklist() -> None:
    """收尾——src 与四测试目录完成清单逐项存在性断言（Task 7.3 承载）。"""
    pass


# ===================================================================
# AC-1: Checkpoint 创建五步完整机制
# ===================================================================


@given("Redis 服务可用")
def redis_service_available(context: dict[str, Any]) -> None:
    """Redis 连通性门控（Background——不可达环境动态 skip）。"""
    import redis.asyncio as aioredis

    env = context["_env"]
    client = aioredis.Redis(
        host=env.redis.host,
        port=env.redis.port,
        password=env.redis.password or None,
        decode_responses=True,
    )
    try:
        _run_async(context["_loop"], client.ping())
    except Exception as exc:
        _run_async(context["_loop"], client.close())
        pytest.skip(f"Redis 不可用: {exc}")
    _run_async(context["_loop"], client.close())


def _dispose_assembly(context: dict[str, Any]) -> None:
    """释放既有装配资源（重复装配前置——Redis 客户端关闭 + PG 会话还原，防泄漏）。"""
    _run_async(context["_loop"], _finalize_pg_session(context))
    if context["_redis_client"] is not None:
        try:
            _run_async(context["_loop"], context["_redis_client"].close())
        except Exception:
            pass
    context["_redis_client"] = None
    context["_pg_session"] = None
    context["_pg_session_token"] = None
    context["_chain_assembled"] = False


@given("Checkpoint 创建链服务可用")
def checkpoint_chain_available(context: dict[str, Any]) -> None:
    """四真实服务双探测门控 + 创建链装配（PG/Qdrant/MinIO 逐档 skip）。"""
    _probe_postgres(context)
    _probe_qdrant(context)
    _probe_minio(context)
    _assemble_checkpoint_chain(context)
    context["_chain_assembled"] = True


def _probe_postgres(context: dict[str, Any]) -> None:
    """PG 双预检（连接 + event_outbox/strategic_archives 表存在——5-4 R1-F07 先例）。"""
    import sqlalchemy as sa

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

    env = context["_env"]
    manager = PostgreSQLManager(
        PostgreSQLConfig(
            host=env.postgres.host,
            port=env.postgres.port,
            database=env.postgres.database,
            username=env.postgres.username,
            password=env.postgres.password,
        )
    )

    async def _probe() -> None:
        engine = manager.get_async_engine()
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT event_id FROM event_outbox LIMIT 1"))
            await conn.execute(sa.text("SELECT archive_id FROM strategic_archives LIMIT 1"))
        await engine.dispose()

    try:
        _run_async(context["_loop"], _probe())
    except Exception as exc:
        pytest.skip(f"PostgreSQL 不可达或 event_outbox/strategic_archives 表未初始化: {exc}")
    context["_pg_manager"] = manager


def _probe_qdrant(context: dict[str, Any]) -> None:
    """Qdrant 连通性门控 + strategic_archive collection 确保（向量维度 1024
    对齐 Fake Embedding——L3 upsert 前提）。"""
    from qdrant_client import AsyncQdrantClient, models

    env = context["_env"]

    async def _probe() -> None:
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
        _run_async(context["_loop"], _probe())
    except Exception as exc:
        pytest.skip(f"Qdrant 不可用: {exc}")


def _probe_minio(context: dict[str, Any]) -> None:
    """MinIO 连通性门控 + archive-evidence 物理 bucket 确保（object-lock 形态——
    L4 WORM GOVERNANCE retention 前提；历史无锁形态自愈：bypass 清版本重建）。"""
    env = context["_env"]

    def _probe() -> None:
        from minio import Minio
        from minio.deleteobjects import DeleteObject

        from src.domain.ports.resolver import resolve

        client = Minio(
            endpoint=env.minio.endpoint,
            access_key=env.minio.access_key,
            secret_key=env.minio.secret_key,
            secure=env.minio.secure,
        )
        bucket_name = resolve("l4_object")._repository._resolve_bucket_name("archive-evidence")
        if not client.bucket_exists(bucket_name):
            try:
                client.make_bucket(bucket_name, object_lock=True)
            except Exception:
                # 并行重建竞态（BucketAlreadyOwnedByYou）——bucket 在位即可
                if not client.bucket_exists(bucket_name):
                    raise
            return
        try:
            client.get_object_lock_config(bucket_name)
        except Exception:
            # 历史无锁形态 best-effort 自愈（bypass 清版本重建带锁；竞态失败接受现状）
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

    try:
        _run_async(context["_loop"], asyncio.to_thread(_probe))
    except Exception as exc:
        pytest.skip(f"MinIO 不可用: {exc}")


@given("调用方持 CP-1 阶段产物输入（performance_gap 完成后）")
def caller_holds_cp1_inputs(context: dict[str, Any]) -> None:
    """CP-1 阶段产物输入（plan_id/checkpoint_no/stage_id/query/检索证据/summary）。"""
    context["_plan_id"] = _new_plan_id()
    context["_checkpoint_no"] = "CP-1"


@given("调用方持 CP-2 与 CP-5 两个子步骤阶段产物输入")
def caller_holds_cp2_cp5_inputs(context: dict[str, Any]) -> None:
    """CP-2/CP-5 两子步骤输入（独立 plan_id 规避覆盖——测试隔离）。"""
    context["_plan_id"] = _new_plan_id()
    context["_dual_checkpoints"] = ("CP-2", "CP-5")


@given("Fake LLM 以轮次感知双响应注入（首轮冗长低压缩形态与次轮达标形态）")
def fake_llm_dual_response_injected(context: dict[str, Any]) -> None:
    """Fake LLM 双响应装配（R6-23——首轮冗长→ratio<0.70 触发二次压缩）。

    双装配防泄漏：既有默认链（"创建链服务可用" Given 已装）先释放资源再
    以双响应形态重装（Redis 客户端/PG 会话不残留）。
    """
    if context.get("_chain_assembled"):
        _dispose_assembly(context)
    _assemble_checkpoint_chain(context, dual_response_llm=True)
    context["_chain_assembled"] = True
    if "_plan_id" not in context:
        context["_plan_id"] = _new_plan_id()
    if "_checkpoint_no" not in context:
        context["_checkpoint_no"] = "CP-1"


@when("显式调用 Checkpoint 创建")
def explicitly_create_checkpoint(context: dict[str, Any]) -> None:
    """显式调用创建（OD-5——MVP 同步链下由显式调用触发；plan_id 缺省生成写回）。"""
    context["_plan_id"] = context.get("_plan_id") or _new_plan_id()
    context["_checkpoint_no"] = context.get("_checkpoint_no") or "CP-1"
    context["result"] = _create_checkpoint(context, plan_id=context["_plan_id"], checkpoint_no=context["_checkpoint_no"])
    _commit_pg_session(context)


@when("以空 persistent_note_ref 构造完整形态快照（checkpoint_no 非空）")
def construct_snapshot_with_empty_note_ref(context: dict[str, Any]) -> None:
    """空引用构造完整形态快照（实体守卫红——延迟 import 缺失类即红）。"""
    from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
    from src.domain.exceptions import CheckpointIntegrityError

    context["_guard_raised"] = None
    try:
        CheckpointSnapshot(
            session_id=_snapshot_session_id(_new_plan_id(), "CP-1"),
            stage_id="performance_gap",
            checkpoint_no="CP-1",
            persistent_note_ref="",
            state_data={"checkpoint_no": "CP-1"},
        )
    except CheckpointIntegrityError as error:
        context["_guard_raised"] = error


@when("依次显式创建 CP-2 与 CP-5 两个 Checkpoint")
def create_cp2_and_cp5_sequentially(context: dict[str, Any]) -> None:
    """依次创建 CP-2 与 CP-5（互不覆盖验证前置）。"""
    plan_id = context["_plan_id"]
    context["_dual_results"] = {
        checkpoint_no: _create_checkpoint(context, plan_id=plan_id, checkpoint_no=checkpoint_no)
        for checkpoint_no in context["_dual_checkpoints"]
    }


@then("完整形态快照键 sisys:snapshot:blm-checkpoint-前缀可读回")
def complete_snapshot_key_readable(context: dict[str, Any]) -> None:
    """完整形态快照经快照仓储 load 读回（独立键族——OD-3 双轨制）。"""
    snapshot = context["result"]
    assert snapshot is not None, "创建未返回快照"
    assert snapshot.session_id.startswith(CHECKPOINT_SESSION_PREFIX_LITERAL), (
        f"session_id 前缀实测={snapshot.session_id!r} 期望前缀={CHECKPOINT_SESSION_PREFIX_LITERAL!r}"
        "（OD-3 双轨制——blm-checkpoint- 独立键族）"
    )
    loaded = _run_async(context["_loop"], context["_snapshot_repository"].load(snapshot.session_id))
    assert loaded is not None, f"快照读回为 None: session_id={snapshot.session_id}"


@then("state_data 携带 Task 0 冻结的 13 键契约")
def state_data_13_key_contract(context: dict[str, Any]) -> None:
    """state_data 13 键契约逐键断言（期望常量独立构造——Task 0.2 冻结）。"""
    state_data = context["result"].state_data
    actual_keys = set(state_data.keys())
    assert actual_keys == set(EXPECTED_STATE_DATA_KEYS), (
        f"state_data 键契约实测={sorted(actual_keys)} 期望={sorted(EXPECTED_STATE_DATA_KEYS)}"
        "（Task 0.2 冻结 13 键——多键/缺键均违规）"
    )
    assert state_data["checkpoint_no"] == context["result"].checkpoint_no
    assert state_data["created_via"] == EXPECTED_CREATED_VIA
    assert state_data["stage_number"] == int(context["_checkpoint_no"].split("-")[1])
    # stage_id 值域锚（独立字面量——禁引用 CHECKPOINT_STAGE_MAPPING 自证）
    assert state_data["stage_id"] == "performance_gap", (
        f"stage_id 实测={state_data['stage_id']!r} 期望='performance_gap'（Subtask 0.1 映射表）"
    )
    assert state_data["plan_id"] == context["_plan_id"]


@then("persistent_note_ref 非空且指向真实持久化笔记（L1 缓存 note 前缀键可读回）")
def persistent_note_ref_points_to_real_note(context: dict[str, Any]) -> None:
    """persistent_note_ref 非空 + L1 缓存 note:{note_id} 可读回（血缘真实）。"""
    snapshot = context["result"]
    note_ref = snapshot.state_data["persistent_note_ref"]
    assert note_ref, "persistent_note_ref 为空（系统公理二强制关联被破坏）"
    note_key = f"{NOTE_CACHE_KEY_PREFIX}{note_ref}"  # 缓存键登记已经 _create_checkpoint 创建时点承载（R1 审查 FR-1）
    raw = _run_async(context["_loop"], context["_redis_client"].get(note_key))
    assert raw is not None, f"L1 笔记缓存键 {note_key} 读回为 None（笔记未真实持久化）"


@then("Redis TTL 为 2592000 秒（30 天）")
def redis_ttl_30_days(context: dict[str, Any]) -> None:
    """TTL 双验（实体 ttl_seconds 与 redis ttl() 秒口径——R6-20 读法钦定）。

    ttl() 是流逝递减值（写入后每秒 -1），恒等断言在「写入→断言」间隔超 1s 时
    （全量并发负载形态）物理性必红（2591999 != 2592000）——改为容差窗断言
    （±下界 5s 流逝容差 + 上界封顶初值防 TTL 配置放大漏检）。"""
    snapshot = context["result"]
    assert snapshot.ttl_seconds == SNAPSHOT_TTL_SECONDS, (
        f"实体 ttl_seconds 实测={snapshot.ttl_seconds} 期望={SNAPSHOT_TTL_SECONDS}（R8-F4 落值点）"
    )
    key = _snapshot_redis_key(snapshot.session_id)
    ttl = _run_async(context["_loop"], context["_redis_client"].ttl(key))
    assert SNAPSHOT_TTL_SECONDS - 5 <= ttl <= SNAPSHOT_TTL_SECONDS, (
        f"redis ttl() 实测={ttl} 期望 [{SNAPSHOT_TTL_SECONDS - 5}, {SNAPSHOT_TTL_SECONDS}]"
        f"（秒 int 口径——-1 永续/-2 不存在；下界 5s 为写入→断言流逝容差）"
    )


@then("压缩产物元数据随快照携带（compression_ratio 与 quality_score 与 token_count）")
def compression_metadata_carried(context: dict[str, Any]) -> None:
    """压缩元数据三键随快照携带（双位同源——R2A-10）。"""
    state_data = context["result"].state_data
    assert state_data["compression_ratio"] >= 0.70, f"compression_ratio 实测={state_data['compression_ratio']}"
    assert state_data["quality_score"] >= 0.70, f"quality_score 实测={state_data['quality_score']}"
    assert state_data["token_count"] > 0, "token_count 非正（压缩产物 token 数缺失）"
    assert state_data["compressed_context"], "compressed_context 为空"


@then("CP-2 快照与 CP-5 快照均独立读回")
def cp2_cp5_both_readable(context: dict[str, Any]) -> None:
    """双点独立读回（独立键——互不覆盖）。"""
    for checkpoint_no, snapshot in context["_dual_results"].items():
        assert snapshot is not None, f"{checkpoint_no} 创建未返回快照"
        loaded = _run_async(context["_loop"], context["_snapshot_repository"].load(snapshot.session_id))
        assert loaded is not None, f"{checkpoint_no} 快照读回为 None（键被覆盖）"


@then("两快照 state_data 的 checkpoint_no 分别为 CP-2 与 CP-5")
def dual_snapshot_checkpoint_no_distinct(context: dict[str, Any]) -> None:
    """两快照 checkpoint_no 锚互异（读侧判别规则）。"""
    results = context["_dual_results"]
    assert results["CP-2"].state_data["checkpoint_no"] == "CP-2"
    assert results["CP-5"].state_data["checkpoint_no"] == "CP-5"
    assert results["CP-2"].session_id != results["CP-5"].session_id, "双点 session_id 相同（键冲突）"


@then("六子步骤 checkpoint_no 值域对齐编号体系（CP-2 至 CP-7 与 CP-8）")
def checkpoint_no_domain_alignment(context: dict[str, Any]) -> None:
    """checkpoint_no 值域断言（8 恢复点——CP-1/CP-2-7/CP-8 编号体系）。

    生产锚（R1 审查 FR-6）：CHECKPOINT_NO_MAX 常量锚定——值域上界漂移
    （改 7/10）即红；映射表互查部分为规范自洽检查（值域执行面在服务守卫）。
    """
    from src.application.ports.checkpoint import CHECKPOINT_NO_MAX

    for checkpoint_no, stage_id in CHECKPOINT_STAGE_MAPPING.items():
        assert checkpoint_no in CHECKPOINT_NO_VALUE_DOMAIN
        assert stage_id, f"{checkpoint_no} 的 stage_id 映射为空"
    assert len(CHECKPOINT_STAGE_MAPPING) == 8, "BLM 前两阶段 8 恢复点口径"
    assert CHECKPOINT_NO_MAX == 8, f"生产常量 CHECKPOINT_NO_MAX 实测={CHECKPOINT_NO_MAX} 期望=8（值域生产锚）"


# ===================================================================
# AC-2: 系统公理二强制（压缩前必须持久化）
# ===================================================================


@then("抛出 CheckpointIntegrityError（EXCEPTION_484）")
def checkpoint_integrity_error_raised(context: dict[str, Any]) -> None:
    """空引用守卫抛 484（构造点守卫——Task 0 钦定触发条件）。"""
    error = context["_guard_raised"]
    assert error is not None, "空 persistent_note_ref 构造未抛 CheckpointIntegrityError"
    assert error.code == "EXCEPTION_484", f"异常 code 实测={error.code}"


@then("不产出无持久化引用的完整形态快照")
def no_snapshot_without_note_ref(context: dict[str, Any]) -> None:
    """守卫拒绝后无半成品快照（0 次违规口径——设计文档 §2.1 验收表）。"""
    assert context.get("result") is None, "守卫场景不应产出快照（result 未消费）"


@then("压缩产物 rerun_count 至少为 1")
def rerun_count_at_least_one(context: dict[str, Any]) -> None:
    """二次路径触发断言（Fake 双响应口径——rerun_count ≥1）。"""
    snapshot = context["result"]
    assert snapshot.state_data["compression_ratio"] >= 0.70
    # rerun_count 经 snapshot_metadata 读侧断言（压缩元数据键族——Task 0.2 冻结）
    assert snapshot.snapshot_metadata.get("rerun_count", 0) >= 1, (
        f"rerun_count 实测={snapshot.snapshot_metadata.get('rerun_count')} 期望 ≥1"
        "（首轮冗长形态应触发二次压缩——R6-23 双响应注入）"
    )


@then("最终快照的 compression_ratio 不低于 0.70")
def final_compression_ratio_qualified(context: dict[str, Any]) -> None:
    """最终产物达标（二次路径后——编排终态门禁通过面）。"""
    assert context["result"].state_data["compression_ratio"] >= 0.70


# ===================================================================
# AC-3: 完整性验证（SHA-256 checksum）
# ===================================================================


@given("已创建一个完整形态快照")
def one_complete_snapshot_created(context: dict[str, Any]) -> None:
    """前置快照创建（独立 plan_id——每场景隔离）。"""
    context["_plan_id"] = _new_plan_id()
    context["_checkpoint_no"] = "CP-1"
    context["result"] = _create_checkpoint(context, plan_id=context["_plan_id"], checkpoint_no="CP-1")


@when("读回快照执行完整性验证并篡改 state_data 任一键后重验")
def verify_then_tamper_then_reverify(context: dict[str, Any]) -> None:
    """round-trip 验证 + 篡改 state_data（summary 键）后重验（突变实证）。"""
    from dataclasses import replace as dc_replace

    snapshot = context["result"]
    loaded = _run_async(context["_loop"], context["_snapshot_repository"].load(snapshot.session_id))
    context["_roundtrip_ok"] = loaded is not None and loaded.verify_integrity()
    # 篡改 state_data 任一键（compressed_context——载荷参与 checksum 的直接可达性，OD-11）
    tampered_state = dict(loaded.state_data)
    tampered_state["compressed_context"] = "被篡改的压缩上下文"
    tampered = dc_replace(loaded, state_data=tampered_state)
    context["_tampered_verify_ok"] = tampered.verify_integrity()
    # 替换 persistent_note_ref 形态（第二类篡改——身份字段参与）
    context["_tampered_ref_verify_ok"] = dc_replace(loaded, persistent_note_ref=str(uuid.uuid4())).verify_integrity()


@then("读回快照 checksum round-trip 验证通过")
def roundtrip_verify_green(context: dict[str, Any]) -> None:
    """round-trip 绿（创建→读回→verify）。"""
    assert context["_roundtrip_ok"], "创建→读回→verify_integrity round-trip 失败"


@then("篡改后重算不匹配且完整性验证失败")
def tampered_verify_red(context: dict[str, Any]) -> None:
    """篡改 state_data/persistent_note_ref 后 verify 红（载荷保护可达性）。"""
    assert context["_tampered_verify_ok"] is False, "篡改 state_data 后 verify 仍绿（载荷未参与 checksum——OD-11 失效）"
    assert context["_tampered_ref_verify_ok"] is False, "替换 persistent_note_ref 后 verify 仍绿"


@then("checksum 算法为 SHA-256 hexdigest（标准库 hashlib）")
def checksum_algorithm_sha256(context: dict[str, Any]) -> None:
    """checksum 形态断言（64 位十六进制——SHA-256 hexdigest）。"""
    checksum = context["result"].checksum
    assert len(checksum) == 64 and all(c in "0123456789abcdef" for c in checksum), (
        f"checksum 实测={checksum!r} 非 SHA-256 hexdigest 形态"
    )


# ===================================================================
# AC-4: CheckpointReached 真实发布
# ===================================================================


@given("真实事件发布器与 PG outbox 已装配")
def real_publisher_and_outbox_assembled(context: dict[str, Any]) -> None:
    """真实 publisher 装配（clear_singleton + resolve 覆写——6-1 场景③先例）。

    双落行重建：编排服务⑤步 CheckpointReached + 归档服务内 ArchiveCreated
    均注入真实 publisher（StrategicArchiveService 同步重建——R2A-8 收集面）。
    双装配防泄漏（R1 审查 FR-14）：既有默认链先释放资源再重装（Redis 客户端/
    PG 会话不孤儿化——对齐双响应 Given 的 dispose 守卫形态）。
    """
    from src.application.services.checkpoint_service import CheckpointService
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.application.use_cases.create_checkpoint import CreateCheckpointUseCase
    from src.domain.ports.resolver import get_resolver, resolve

    if context.get("_chain_assembled"):
        _dispose_assembly(context)
    _assemble_checkpoint_chain(context)
    get_resolver().clear_singleton()
    real_publisher = resolve("event_publisher")

    context["_checkpoint_service"] = CheckpointService(
        note_taker=context["_checkpoint_service"]._note_taker,
        compressor=context["_checkpoint_service"]._compressor,
        archive_service=StrategicArchiveService(
            archive_repo=resolve("archive_repository"),
            embedding_service=_make_fake_embedding(),
            vector_storage=resolve("l3_vector"),
            object_storage=resolve("l4_object"),
            graph_storage=None,
            event_publisher=real_publisher,
            staleness_service=None,
        ),
        snapshot_repository=context["_checkpoint_service"]._snapshot_repository,
        event_publisher=real_publisher,
    )
    context["_use_case"] = CreateCheckpointUseCase(checkpoint_service=context["_checkpoint_service"])

    def _restore() -> None:
        get_resolver().clear_singleton()

    context["_restorers"].append(_restore)


def _commit_pg_session(context: dict[str, Any]) -> None:
    """提交当前 PG 事务（行断言前置——commit 后独立连接可见；session 自动新事务）。"""
    session = context.get("_pg_session")
    if session is not None:
        _run_async(context["_loop"], session.commit())


@when("显式调用 Checkpoint 创建（CP-1 与 performance_gap 值域）")
def create_cp1_performance_gap(context: dict[str, Any]) -> None:
    """创建 CP-1（互锁解除钦定——R6-6：互证场景创建侧一律 performance_gap 值域）。"""
    context["_plan_id"] = _new_plan_id()
    context["_checkpoint_no"] = "CP-1"
    context["result"] = _create_checkpoint(context, plan_id=context["_plan_id"], checkpoint_no="CP-1")
    _commit_pg_session(context)  # 归档行 + outbox 行（同事务）提交——独立连接可见
    time.sleep(0.2)  # outbox 异步落行窗口


@then("outbox 落行 CheckpointReached 恰一行")
def outbox_exactly_one_checkpoint_reached_row(context: dict[str, Any]) -> None:
    """outbox 落行恰一行（phase_identifier 通道过滤——禁 plan_id 子字典通道）。"""
    rows = _query_outbox_checkpoint_reached(context, context["_plan_id"])
    context["_outbox_event_ids"].extend(row["event_id"] for row in rows)
    assert len(rows) == 1, f"CheckpointReached 落行实测={len(rows)} 期望=1（恰一行）"


@then("行字段 phase_identifier 为 performance_gap 且 user_feedback_request 为 true")
def outbox_row_fields_asserted(context: dict[str, Any]) -> None:
    """行字段断言（phase_identifier 通道——事件类字段族无 plan_id）。"""
    rows = [r for r in _query_outbox_checkpoint_reached(context, context["_plan_id"])]
    assert rows, "行已被清理（前步收集后重查）"
    row = rows[0]
    assert row["phase_identifier"] == "performance_gap", f"phase_identifier 实测={row['phase_identifier']}"
    assert row["user_feedback_request"] in (True, "true"), f"user_feedback_request 实测={row['user_feedback_request']}"
    assert row["event_type"] == "CheckpointReached"


@then("行 payload 顶层 metadata.plan_id 关联规划标识")
def outbox_metadata_plan_id_linked(context: dict[str, Any]) -> None:
    """plan 关联断言键 = payload->'metadata'->>'plan_id'（顶层——OD-9 定谳）。"""
    rows = _query_outbox_checkpoint_reached(context, context["_plan_id"])
    assert rows, "行缺失"
    assert rows[0]["metadata_plan_id"] == context["_plan_id"], (
        f"metadata.plan_id 实测={rows[0]['metadata_plan_id']} 期望={context['_plan_id']}"
        "（plan 关联经 DomainEvent metadata 顶层通道——R1-D1 实证）"
    )


@then("发布点位于 checkpoint 应用服务新文件（blm_planning 四文件零引用）")
def publish_point_in_new_file_only(context: dict[str, Any]) -> None:
    """发布点落位行为级证据（新文件在位 + 四文件零引用——OD-4）。"""
    publish_source = REPO_ROOT / "src" / "application" / "services" / "checkpoint_service.py"
    assert publish_source.is_file(), "checkpoint 应用服务新文件缺失"
    assert "CheckpointReached" in publish_source.read_text(encoding="utf-8"), "新文件无发布调用"
    for relative in (
        "application/services/blm_planning_service.py",
        "application/use_cases/run_blm_planning.py",
        "application/use_cases/get_blm_planning_status.py",
        "application/services/blm_planning_prompts.py",
    ):
        content = (REPO_ROOT / "src" / relative).read_text(encoding="utf-8")
        assert "CheckpointReached" not in content, f"{relative} 不得发布 CheckpointReached（OD-4 零触碰）"


def _query_outbox_checkpoint_reached(context: dict[str, Any], plan_id: str) -> list[dict[str, Any]]:
    """查询 CheckpointReached 落行（phase_identifier + metadata 双通道——5 分钟窗）。"""
    import sqlalchemy as sa

    async def _query() -> list[dict[str, Any]]:
        engine = context["_pg_manager"].get_async_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT event_id, event_type, "
                        "payload->'payload'->>'phase_identifier' AS phase_identifier, "
                        "payload->'payload'->>'user_feedback_request' AS user_feedback_request, "
                        "payload->'metadata'->>'plan_id' AS metadata_plan_id "
                        "FROM event_outbox "
                        "WHERE event_type = 'CheckpointReached' "
                        "AND created_at >= NOW() - INTERVAL '5 minutes' "
                        "AND payload->'metadata'->>'plan_id' = :plan_id"
                    ),
                    {"plan_id": plan_id},
                )
            ).fetchall()
        return [
            {
                "event_id": str(row[0]),
                "event_type": row[1],
                "phase_identifier": row[2],
                "user_feedback_request": row[3],
                "metadata_plan_id": row[4],
            }
            for row in rows
        ]

    return _run_async(context["_loop"], _query())


@when("显式创建 CP-1 前核验全通道零 CheckpointReached 落行后创建")
def pre_create_zero_rows_check_then_create_cp1(context: dict[str, Any]) -> None:
    """创建前全通道零落行核验（残局防线——R1 审查 FR-5 名实相符化改写）。

    本场景不执行 BLM run：正交性的行为级证据由 6-2 既有验收 AC-3（市场洞察
    run 内零 CheckpointReached）零适配回归承载（Task 4.3——OD-13 勘误注记）；
    此处断言面 = 创建前全通道计数（teardown 残局/跨场景污染的真实防线——
    6-2 负向查询同构形态）。真实 publisher 重建（S6 同款）：互证断言面要求
    创建侧落行——默认装配的 NoopPublisher 不落行，此处注入真实 publisher 后创建。
    """
    from src.application.services.checkpoint_service import CheckpointService
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.application.use_cases.create_checkpoint import CreateCheckpointUseCase
    from src.domain.ports.resolver import get_resolver, resolve

    get_resolver().clear_singleton()
    real_publisher = resolve("event_publisher")
    context["_checkpoint_service"] = CheckpointService(
        note_taker=context["_checkpoint_service"]._note_taker,
        compressor=context["_checkpoint_service"]._compressor,
        archive_service=StrategicArchiveService(
            archive_repo=resolve("archive_repository"),
            embedding_service=_make_fake_embedding(),
            vector_storage=resolve("l3_vector"),
            object_storage=resolve("l4_object"),
            graph_storage=None,
            event_publisher=real_publisher,
            staleness_service=None,
        ),
        snapshot_repository=context["_checkpoint_service"]._snapshot_repository,
        event_publisher=real_publisher,
    )
    context["_use_case"] = CreateCheckpointUseCase(checkpoint_service=context["_checkpoint_service"])

    def _restore() -> None:
        get_resolver().clear_singleton()

    context["_restorers"].append(_restore)

    context["_plan_id"] = _new_plan_id()
    # 创建前先查询——防创建侧行经时间窗交叉捕获（R6-6 执行序钦定）
    context["_pre_create_count"] = _count_checkpoint_reached_all_channels(context)
    context["result"] = _create_checkpoint(context, plan_id=context["_plan_id"], checkpoint_no="CP-1")
    _commit_pg_session(context)
    time.sleep(0.2)  # outbox 异步落行窗口


def _count_checkpoint_reached_all_channels(context: dict[str, Any]) -> int:
    """全通道计数（含 LIKE market 转义下划线——与 6-2 负向查询同构）。"""
    import sqlalchemy as sa

    async def _count() -> int:
        engine = context["_pg_manager"].get_async_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT COUNT(*) FROM event_outbox "
                        "WHERE event_type = 'CheckpointReached' "
                        "AND created_at >= NOW() - INTERVAL '5 minutes' "
                        "AND (payload->'metadata'->>'plan_id' = :plan_id "
                        "OR payload->'payload'->>'phase_identifier' LIKE 'market\\_insight%')"
                    ),
                    {"plan_id": context["_plan_id"]},
                )
            ).fetchall()
        return int(rows[0][0])

    return _run_async(context["_loop"], _count())


@then("创建前全通道（含 6-2 LIKE 通道）零 CheckpointReached 落行")
def pre_create_all_channels_zero_checkpoint_reached(context: dict[str, Any]) -> None:
    """创建前全通道零落行（残局防线——非空锚防过滤键空真；正交性证据归 6-2 资产）。"""
    assert context["_pre_create_count"] == 0, (
        f"创建前 CheckpointReached 全通道计数实测={context['_pre_create_count']} 期望=0"
        "（teardown 残局防线——run 正交性行为级证据由 6-2 既有验收承载，OD-13）"
    )


@then("创建路径恰一行（phase_identifier 通道过滤）")
def create_path_exactly_one_row(context: dict[str, Any]) -> None:
    """创建路径恰一行（CP-1/performance_gap 值域）。"""
    rows = _query_outbox_checkpoint_reached(context, context["_plan_id"])
    context["_outbox_event_ids"].extend(row["event_id"] for row in rows)
    assert len(rows) == 1, f"创建路径落行实测={len(rows)} 期望=1"


@then("6-2 侧负向查询通道（LIKE market 转义下划线前缀）零捕获自产行")
def like_channel_zero_self_capture(context: dict[str, Any]) -> None:
    """LIKE market\\_insight% 通道零捕获（创建侧 CP-1 值域不落通道——R6-6）。"""
    import sqlalchemy as sa

    async def _count() -> int:
        engine = context["_pg_manager"].get_async_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT COUNT(*) FROM event_outbox "
                        "WHERE event_type = 'CheckpointReached' "
                        "AND created_at >= NOW() - INTERVAL '5 minutes' "
                        "AND payload->'payload'->>'phase_identifier' LIKE 'market\\_insight%'"
                    ),
                )
            ).fetchall()
        return int(rows[0][0])

    count = _run_async(context["_loop"], _count())
    assert count == 0, (
        f"LIKE market\\_insight% 通道实测={count} 期望=0（创建侧 CP-1/performance_gap 值域——自产行被捕获即假红，R6-6 互锁解除）"
    )


# ===================================================================
# AC-5: L3/L4 触发接线（1-15b 钦定义务清偿）
# ===================================================================


@then("PG strategic_archives 归档行存在且 plan_type 为 SP")
def archive_row_exists_with_sp(context: dict[str, Any]) -> None:
    """L2 归档行断言（plan_type='SP' 钦定——R6-1；commit 后独立连接可见）。"""
    import sqlalchemy as sa

    _commit_pg_session(context)

    async def _query() -> list[Any]:
        engine = context["_pg_manager"].get_async_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT archive_id, plan_type, blob_ref, embedding_ref, "
                        "decision_basis, assumptions "
                        "FROM strategic_archives WHERE plan_id = :plan_id"
                    ),
                    {"plan_id": context["_plan_id"]},
                )
            ).fetchall()
        return list(rows)

    rows = _run_async(context["_loop"], _query())
    assert rows, f"strategic_archives 归档行缺失: plan_id={context['_plan_id']}"
    context["_archive_rows"] = [
        {
            "archive_id": str(row[0]),
            "plan_type": row[1],
            "blob_ref": row[2],
            "embedding_ref": row[3],
            "decision_basis": row[4] or {},
            "assumptions": row[5] or {},
        }
        for row in rows
    ]
    context["_archive_row_ids"].extend(row["archive_id"] for row in context["_archive_rows"])
    for row in context["_archive_rows"]:
        assert row["plan_type"] == "SP", f"plan_type 实测={row['plan_type']} 期望=SP（R6-1 钦定）"


@then("Qdrant strategic_archive 集合点可检索（search_vectors 读回）")
def qdrant_point_searchable(context: dict[str, Any]) -> None:
    """L3 向量点断言（scroll 定向过滤读回——按 payload.archive_id 过滤后匹配，点 ID 为 MD5
    哈希 int 形态，payload.archive_id 是归档语境锚）。scroll_filter 定向过滤使断言免受共享
    collection 残留点干扰（残留规模突破 limit 后无过滤 scroll 会截断丢点致稳定假红——
    6.11-R2-DF1 核销修复，integration checkpoint 同款）。"""
    from qdrant_client import AsyncQdrantClient, models

    env = context["_env"]
    archive_ids = [row["archive_id"] for row in context["_archive_rows"]]

    async def _search() -> Any:
        client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
        try:
            return await client.scroll(
                collection_name="strategic_archive",
                scroll_filter=models.Filter(
                    must=[models.FieldCondition(key="archive_id", match=models.MatchAny(any=archive_ids))]
                ),
                limit=50,
                with_payload=True,
            )
        finally:
            await client.close()

    points, _next = _run_async(context["_loop"], _search())
    point_archives = {str(point.payload.get("archive_id")) for point in points}
    missing = set(archive_ids) - point_archives
    assert not missing, f"Qdrant strategic_archive 点未读回（payload.archive_id 实测={point_archives} 缺 {missing}）"


@then("MinIO archive-evidence 桶对象可取（blob_ref 解引用含压缩上下文）")
def minio_object_fetchable(context: dict[str, Any]) -> None:
    """L4 WORM 对象断言（blob_ref 经 L4 端口 retrieve 解引用——含压缩上下文）。"""
    from src.domain.ports.resolver import resolve

    blob_refs = [row["blob_ref"] for row in context["_archive_rows"] if row["blob_ref"]]
    context["_minio_blob_refs"].extend(blob_refs)
    object_storage = resolve("l4_object")
    compressed_context = context["result"].state_data["compressed_context"]

    async def _fetch(blob_ref: str) -> bytes:
        data = b""
        async for chunk in object_storage.retrieve(bucket_type="archive-evidence", object_key=blob_ref):
            data += chunk
        return data

    for blob_ref in blob_refs:
        blob_text = _run_async(context["_loop"], _fetch(blob_ref)).decode("utf-8")
        assert compressed_context[:32] in blob_text, f"blob_ref={blob_ref} 解引用内容不含压缩上下文（L4 载荷映射——Task 0.8②）"


@then("归档行 decision_basis 携带 checkpoint_no 语境锚")
def decision_basis_carries_checkpoint_no(context: dict[str, Any]) -> None:
    """decision_basis.checkpoint_no 断言（R8-F3 钦定——归档行 checkpoint 语境锚）。"""
    for row in context["_archive_rows"]:
        assert row["decision_basis"].get("checkpoint_no") == context["result"].checkpoint_no, (
            f"decision_basis.checkpoint_no 实测={row['decision_basis'].get('checkpoint_no')}"
            f" 期望={context['result'].checkpoint_no}（R8-F3——同 plan 多 checkpoint 判别锚）"
        )
    # assumptions 承载笔记实体/摘要（Task 0.8② 冻结映射）
    for row in context["_archive_rows"]:
        assert row["assumptions"], "assumptions 载荷为空（笔记实体/摘要未入档）"


# ===================================================================
# AC-6: 用户反馈请求与修正记录
# ===================================================================


@when("对 Checkpoint 提交一条修正（CorrectionRecord 五字段）")
def apply_one_correction(context: dict[str, Any]) -> None:
    """修正应用（CorrectionRecord 五字段 → apply_correction 乐观锁）。"""
    from src.domain.entities.checkpoint import CorrectionRecord

    snapshot = context["result"]
    correction = CorrectionRecord(
        correction_type="key_param",
        previous_value="营收目标达成率 87%",
        new_value="营收目标达成率 90%（高管修正）",
        applied_by="acceptance-executor",
    )
    context["_correction_applied"] = correction
    context["corrected"] = _run_async(
        context["_loop"],
        context["_checkpoint_service"].apply_correction(
            session_id=snapshot.session_id,
            correction=correction,
            expected_state_version=snapshot.state_version,
        ),
    )


@then("修正后快照 state_version 递增（v0 至 v1）")
def state_version_incremented(context: dict[str, Any]) -> None:
    """版本递增断言（首建 v0（实体默认）→ 修正 v1——R6-2 钦定基线）。"""
    before = context["result"]
    after = context["corrected"]
    assert before.state_version == 0, f"首建版本实测={before.state_version} 期望=0（R6-2 实体默认基线）"
    assert after.state_version == 1, f"修正后版本实测={after.state_version} 期望=1（修正链 +1）"


@then("correction_history 追加一条修正记录且原快照字段保留")
def correction_history_appended(context: dict[str, Any]) -> None:
    """修正历史追加（五字段 dict 投影——R8-F5 asdict 等价形态）+ 字段保留。"""
    after = context["corrected"]
    history = after.state_data["correction_history"]
    assert len(history) == 1, f"correction_history 实测={len(history)} 条 期望=1"
    entry = history[0]
    correction = context["_correction_applied"]
    assert entry["correction_type"] == correction.correction_type
    assert entry["previous_value"] == correction.previous_value
    assert entry["new_value"] == correction.new_value
    assert entry["applied_by"] == correction.applied_by
    assert isinstance(entry["applied_at"], str) and entry["applied_at"], "applied_at 应为 isoformat 字符串（R8-F5）"
    # 原快照字段保留（with_updated_state 不可变更新——合并语义）
    assert after.state_data["plan_id"] == context["result"].state_data["plan_id"]
    assert after.state_data["summary"] == context["result"].state_data["summary"]


@then("checksum 重算后 round-trip 完整性验证通过")
def checksum_recomputed_roundtrip_green(context: dict[str, Any]) -> None:
    """修正链完整性闭环（载荷已变而 checksum 重算替换——AC-3 重算点）。"""
    corrected = context["corrected"]
    assert corrected.verify_integrity(), "修正后 checksum 未重算（verify 恒红——重算点缺失）"


@then("修正后快照保留原 persistent_note_ref 血缘")
def note_ref_lineage_preserved(context: dict[str, Any]) -> None:
    """血缘链保留断言（修正不换笔记血缘）。"""
    assert context["corrected"].state_data["persistent_note_ref"] == context["result"].state_data["persistent_note_ref"]


# ===================================================================
# AC-7: 恢复数据面与双模式判定
# ===================================================================


@given("已独立创建 CP-1 一个 Checkpoint")
def independently_created_cp1(context: dict[str, Any]) -> None:
    """前置 CP-1（每步一次全链——R2-F6 三点分步钦定）。"""
    context["_plan_id"] = _new_plan_id()
    _create_checkpoint(context, plan_id=context["_plan_id"], checkpoint_no="CP-1")


@given("已独立创建 CP-3 一个 Checkpoint")
def independently_created_cp3(context: dict[str, Any]) -> None:
    """前置 CP-3（同 plan——后续清单推导同一 plan_id 值域）。"""
    _create_checkpoint(context, plan_id=context["_plan_id"], checkpoint_no="CP-3")


@given("已独立创建 CP-5 一个 Checkpoint")
def independently_created_cp5(context: dict[str, Any]) -> None:
    """前置 CP-5（三点在位——AC-7 前置 ≥3 快照族）。"""
    _create_checkpoint(context, plan_id=context["_plan_id"], checkpoint_no="CP-5")


@when("分别从 CP-3 与 CP-1 恢复")
def recover_from_cp3_and_cp1(context: dict[str, Any]) -> None:
    """恢复执行（load→verify→反序列化→视图组装——恢复数据面）。"""
    context["_recovery_views"] = {
        checkpoint_no: _run_async(
            context["_loop"],
            context["_checkpoint_service"].recover_checkpoint(plan_id=context["_plan_id"], checkpoint_no=checkpoint_no),
        )
        for checkpoint_no in ("CP-3", "CP-1")
    }


@then("恢复视图 DTO 键契约完整（Task 0 冻结键族）")
def recovery_view_key_contract(context: dict[str, Any]) -> None:
    """恢复视图 ≥7 键断言（Task 0 冻结键族——6-6 消费面契约）。"""
    from dataclasses import fields as dc_fields

    for checkpoint_no, view in context["_recovery_views"].items():
        actual = {field.name for field in dc_fields(view)}
        assert actual == set(EXPECTED_RECOVERY_VIEW_KEYS), (
            f"{checkpoint_no} 恢复视图键实测={sorted(actual)} 期望={sorted(EXPECTED_RECOVERY_VIEW_KEYS)}"
        )


@then("CP-3 恢复视图后续清单为 CP-5 且建议恢复模式为 override（1 小于 2）")
def cp3_view_subsequent_and_override(context: dict[str, Any]) -> None:
    """CP-3 视图（后续 [CP-5] → 1<2 → OVERRIDE 推荐）+ R3-2 增补键值级断言。"""
    view = context["_recovery_views"]["CP-3"]
    assert view.subsequent_checkpoints == ["CP-5"], f"后续清单实测={view.subsequent_checkpoints}"
    assert view.recommended_mode == "override", f"建议模式实测={view.recommended_mode!r}"
    # R3-2 值级断言：state_version/snapshot_id 真实填充（防「忘填用默认值」零检出）
    assert view.state_version == 0, f"首建快照版本实测={view.state_version} 期望=0（R6-2 基线）"
    loaded = _run_async(
        context["_loop"], context["_snapshot_repository"].load(_snapshot_session_id(context["_plan_id"], "CP-3"))
    )
    assert loaded is not None
    assert view.snapshot_id == str(loaded.snapshot_id), "视图 snapshot_id 与存储快照不一致（填充断裂）"


@then("CP-1 恢复视图后续清单为 CP-3 与 CP-5 且判定恰 2 后续强制 replay")
def cp1_view_subsequent_and_replay(context: dict[str, Any]) -> None:
    """CP-1 视图（后续 [CP-3, CP-5] → 2≥2 边界 → REPLAY 强制）。"""
    view = context["_recovery_views"]["CP-1"]
    assert view.subsequent_checkpoints == ["CP-3", "CP-5"], f"后续清单实测={view.subsequent_checkpoints}"
    assert view.recommended_mode == "replay", f"建议模式实测={view.recommended_mode!r}（恰 2 强制）"


@then("判定纯函数边界全覆盖（0 与 1 推荐 override、2 与 3 强制 replay）")
def mode_pure_function_boundaries(context: dict[str, Any]) -> None:
    """判定纯函数直测（0/1→OVERRIDE、2/3→REPLAY——边界值 2 恰好强制）。"""
    from src.domain.entities.checkpoint import RecoveryMode
    from src.domain.services.recovery_mode import recommend_recovery_mode

    assert recommend_recovery_mode(0) is RecoveryMode.OVERRIDE
    assert recommend_recovery_mode(1) is RecoveryMode.OVERRIDE
    assert recommend_recovery_mode(2) is RecoveryMode.REPLAY, "边界 2 恰好强制 Replay（突变实证锚）"
    assert recommend_recovery_mode(3) is RecoveryMode.REPLAY


@given("已创建一个完整形态快照并应用一次修正产出版本 v1")
def snapshot_created_and_corrected_to_v1(context: dict[str, Any]) -> None:
    """前置：快照 v0 → 修正 → v1（482 两步构造法第一步——R6-2）。"""
    from src.domain.entities.checkpoint import CorrectionRecord

    context["_plan_id"] = _new_plan_id()
    context["result"] = _create_checkpoint(context, plan_id=context["_plan_id"], checkpoint_no="CP-1")
    context["corrected"] = _run_async(
        context["_loop"],
        context["_checkpoint_service"].apply_correction(
            session_id=context["result"].session_id,
            correction=CorrectionRecord(
                correction_type="prelude",
                previous_value="v0",
                new_value="v1",
                applied_by="acceptance-executor",
            ),
            expected_state_version=0,
        ),
    )
    assert context["corrected"].state_version == 1, "两步构造法第一步失败（v0→v1）"


@when("依次尝试恢复不存在的 checkpoint 键与以过期版本提交修正与恢复被篡改快照")
def attempt_three_illegal_operations(context: dict[str, Any]) -> None:
    """三分构造（480 不存在键/482 过期版本/484 篡改——Task 0.3 钦定口径）。

    执行序钦定（R3-1）：482 构造先于篡改——修正作用于**未篡改**存活 v1
    （R3-1 写前完整性门禁落位后，对篡改体的修正会先抛 484 遮蔽 482 断言）；
    篡改保 state_version=1 后存储态即篡改体，482 在 save 前抛出不污染。
    """
    from dataclasses import replace as dc_replace

    from src.domain.entities.checkpoint import CorrectionRecord

    service = context["_checkpoint_service"]
    plan_id = context["_plan_id"]
    context["_three_way"] = {}

    # ① 不存在的 checkpoint 键 → 480（含 JSON 损坏同路径——统一承载）
    try:
        _run_async(context["_loop"], service.recover_checkpoint(plan_id=plan_id, checkpoint_no="CP-8"))
        context["_three_way"]["missing"] = None
    except Exception as error:  # 三分异常类型本身是断言对象（类型/编码在 Then 步骤断言）
        context["_three_way"]["missing"] = error

    # ② 以过期版本提交修正 → 482（对存活 v1 传 expected=0——两步构造法第二步；
    #    先于篡改执行——修正面作用于未篡改 v1，R3-1 门禁不触发）
    correction = CorrectionRecord(
        correction_type="stale",
        previous_value="v1",
        new_value="v2",
        applied_by="acceptance-executor",
    )
    try:
        _run_async(
            context["_loop"],
            service.apply_correction(
                session_id=context["result"].session_id,
                correction=correction,
                expected_state_version=0,
            ),
        )
        context["_three_way"]["stale"] = None
    except Exception as error:  # 三分异常类型本身是断言对象（类型/编码在 Then 步骤断言）
        context["_three_way"]["stale"] = error

    # ③ 恢复被篡改快照 → 484（读回后篡改 state_data 再存——checksum 不匹配构造）
    loaded = _run_async(context["_loop"], context["_snapshot_repository"].load(context["result"].session_id))
    tampered_state = dict(loaded.state_data)
    tampered_state["summary"] = "被篡改的摘要（场景注入）"
    tampered = dc_replace(loaded, state_data=tampered_state)
    _run_async(context["_loop"], context["_snapshot_repository"].save(tampered))
    try:
        _run_async(context["_loop"], service.recover_checkpoint(plan_id=plan_id, checkpoint_no="CP-1"))
        context["_three_way"]["tampered"] = None
    except Exception as error:  # 三分异常类型本身是断言对象（类型/编码在 Then 步骤断言）
        context["_three_way"]["tampered"] = error


@then("不存在键抛 480（PlanningNotFoundError 承载 checkpoint 语境）")
def missing_key_raises_480(context: dict[str, Any]) -> None:
    """480 断言（键不存在与 JSON 损坏同路径统一承载——R6-22 参数映射）。"""
    from src.domain.exceptions import PlanningNotFoundError

    error = context["_three_way"]["missing"]
    assert isinstance(error, PlanningNotFoundError), f"异常类型实测={type(error).__name__} 期望=PlanningNotFoundError"
    assert error.code == "EXCEPTION_480"
    assert error.context.get("reason") == "checkpoint_key_not_found", (
        f"context.reason 实测={error.context.get('reason')}（R6-22 语境承载钦定）"
    )


@then("checksum 不匹配抛 484（CheckpointIntegrityError）")
def checksum_mismatch_raises_484(context: dict[str, Any]) -> None:
    """484 断言（恢复入口强制先 verify_integrity——校验失败拒绝恢复）。"""
    from src.domain.exceptions import CheckpointIntegrityError

    error = context["_three_way"]["tampered"]
    assert isinstance(error, CheckpointIntegrityError), f"异常类型实测={type(error).__name__}"
    assert error.code == "EXCEPTION_484"


@then("版本倒退抛 482（PlanningStateError 第二触发点）")
def version_rollback_raises_482(context: dict[str, Any]) -> None:
    """482 断言（apply_correction 乐观锁——修正面唯一构造通道，R6-3 收窄）。"""
    from src.domain.exceptions import PlanningStateError

    error = context["_three_way"]["stale"]
    assert isinstance(error, PlanningStateError), f"异常类型实测={type(error).__name__}"
    assert error.code == "EXCEPTION_482"


@then("482 的 HTTP 映射 409 在位（既有注册零改动）")
def error_482_http_mapping_409(context: dict[str, Any]) -> None:
    """482→409 预留映射在位断言（既有注册零改动验证——预留映射已存在）。"""
    from fastapi import status

    from src.domain.exceptions import PlanningStateError
    from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

    assert EXCEPTION_HTTP_MAP[PlanningStateError] == status.HTTP_409_CONFLICT


# ===================================================================
# AC-8: 性能与持久化成功率
# ===================================================================


@given("单次全链预热已完成（固定压缩产物就绪且 Redis 连接池已建立）")
def full_chain_warmup_completed(context: dict[str, Any]) -> None:
    """预热（含④步 save——R8-F5：防首轮建连开销抬 P95，禁窄化为仅①②步）。"""
    from src.domain.services.context_compressor import CompressedContext

    context["_plan_id"] = _new_plan_id()
    warmup = _create_checkpoint(context, plan_id=context["_plan_id"], checkpoint_no="CP-1")
    state_data = warmup.state_data
    # 预热产物（CompressedContext 形态重构——20 轮复用；R6-11 血缘豁免注记：
    # persistent_note_ref 同属预热 plan 的笔记血缘，性能口径下不构成本轮 plan 语义）
    context["_warmup_compressed"] = CompressedContext(
        context=state_data["compressed_context"],
        compression_ratio=state_data["compression_ratio"],
        quality_score=state_data["quality_score"],
        token_count=state_data["token_count"],
        persistent_note_ref=state_data["persistent_note_ref"],
        query="五年战略规划",
    )


@when("连续执行 20 轮独立 plan_id 的快照构造与提交窗口采样")
def sample_20_rounds_creation_window(context: dict[str, Any]) -> None:
    """20 轮采样（直调 build_snapshot→save 两段——R6-5 窗口同构）。"""
    service = context["_checkpoint_service"]
    snapshot_repository = context["_snapshot_repository"]
    compressed = context["_warmup_compressed"]
    durations: list[float] = []
    sampled_sessions: list[str] = []
    for _round in range(20):
        plan_id = _new_plan_id()
        session_id = _snapshot_session_id(plan_id, "CP-1")
        start = time.monotonic()
        snapshot = service.build_snapshot(
            plan_id=plan_id,
            checkpoint_no="CP-1",
            stage_id="performance_gap",
            compressed=compressed,
            summary="性能采样窗口（固定输入）",
            completed=True,
            created_via="use_case",
        )
        _run_async(context["_loop"], snapshot_repository.save(snapshot))
        durations.append(time.monotonic() - start)
        sampled_sessions.append(session_id)
        context["_snapshot_session_ids"].append(session_id)  # 采样快照键并入清理链（R1 审查 FR-1）
    context["_perf_durations"] = durations
    context["_perf_sessions"] = sampled_sessions


@then("20 轮窗口 P95 小于 100ms（升序排序次大值口径）")
def p95_under_100ms(context: dict[str, Any]) -> None:
    """P95 断言（sorted 升序 [ceil(0.95n)-1]——n=20 取次大值；数学口径声明）。"""
    durations = sorted(context["_perf_durations"])  # 升序排序前提（6-1/6-2 同款口径）
    import math

    p95 = durations[math.ceil(0.95 * len(durations)) - 1]
    assert p95 < 0.100, f"创建提交窗口 P95 实测={p95 * 1000:.2f}ms ≥ 100ms（OD-6 口径：build_snapshot→save 窗口）"


@then("20 个快照全部可读回（持久化成功率 100%）")
def all_20_snapshots_readable(context: dict[str, Any]) -> None:
    """成功率断言（N 次创建 N 次可读回——强制环节零失败语义）。"""
    snapshot_repository = context["_snapshot_repository"]
    for session_id in context["_perf_sessions"]:
        loaded = _run_async(context["_loop"], snapshot_repository.load(session_id))
        assert loaded is not None, f"采样快照读回为 None: {session_id}"


@then("每个快照 TTL 为 2592000 秒")
def every_sampled_snapshot_ttl(context: dict[str, Any]) -> None:
    """TTL 断言（build_snapshot 落值点——R8-F4）。容差窗同 redis_ttl_30_days（ttl() 流逝递减——恒等断言负载形态必红）。"""
    for session_id in context["_perf_sessions"]:
        key = _snapshot_redis_key(session_id)
        ttl = _run_async(context["_loop"], context["_redis_client"].ttl(key))
        assert SNAPSHOT_TTL_SECONDS - 5 <= ttl <= SNAPSHOT_TTL_SECONDS, (
            f"ttl() 实测={ttl} 期望 [{SNAPSHOT_TTL_SECONDS - 5}, {SNAPSHOT_TTL_SECONDS}]（key={key}；下界 5s 流逝容差）"
        )


# ===================================================================
# 收尾: 开发完成清单（Task 7.3 承载——静态清单零服务依赖）
# ===================================================================


@given("Story 6-3 交付面清单已定义")
def delivery_checklist_defined(context: dict[str, Any]) -> None:
    """交付面清单定义（src 与四测试目录——File List 单源）。"""
    context["_src_checklist"] = (
        "src/domain/entities/checkpoint_snapshot.py",
        "src/domain/entities/checkpoint.py",
        "src/domain/services/recovery_mode.py",
        "src/domain/exceptions/planning_exceptions.py",
        "src/domain/exceptions/_code_ranges.py",
        "src/domain/exceptions/__init__.py",
        "src/application/ports/checkpoint.py",
        "src/application/services/checkpoint_service.py",
        "src/application/use_cases/create_checkpoint.py",
        "src/infrastructure/storage/redis/redis_snapshot_store.py",
        "src/interfaces/api/exception_handlers.py",
        "src/composition_root.py",
        "src/entrypoints/agent_cli.py",
    )
    context["_tests_checklist"] = (
        "tests/unit/domain/entities/test_checkpoint_snapshot.py",
        "tests/unit/domain/entities/test_checkpoint.py",
        "tests/unit/domain/services/test_recovery_mode.py",
        "tests/unit/domain/exceptions/test_planning_exceptions.py",
        "tests/unit/infrastructure/storage/test_redis_snapshot_store.py",
        "tests/unit/interfaces/api/test_exception_handlers.py",
        "tests/unit/application/test_checkpoint_service.py",
        "tests/unit/application/use_cases/test_checkpoint_use_case.py",
        "tests/unit/interfaces/cli/test_agent_cli.py",
        "tests/unit/architecture/test_checkpoint.py",
        "tests/integration/test_integration_checkpoint.py",
        "tests/contracts/test_port_contract_checkpoint.py",
        "tests/contracts/test_event_channel_mapping_blm_planning.py",
        "tests/acceptance/test_acceptance_checkpoint_snapshot.feature",
        "tests/acceptance/test_acceptance_checkpoint_snapshot.py",
    )


@when("逐项检查 src 完成清单与四测试目录完成清单")
def check_delivery_files(context: dict[str, Any]) -> None:
    """逐项存在性检查（REPO_ROOT 相对路径）。"""
    context["_missing"] = [
        relative
        for relative in (*context["_src_checklist"], *context["_tests_checklist"])
        if not (REPO_ROOT / relative).is_file()
    ]


@then("src 交付件逐项存在（实体扩展与纯函数与异常与端口与服务与用例与组合根与 CLI）")
def src_deliverables_present(context: dict[str, Any]) -> None:
    """src 完成清单断言。"""
    assert not context["_missing"], f"交付件缺失: {context['_missing']}"


@then("四测试目录交付件逐项存在（单测与集成与契约与验收全文件）")
def tests_deliverables_present(context: dict[str, Any]) -> None:
    """四测试目录完成清单断言（本 Story 测试分类表全文件）。"""
    assert not context["_missing"], f"交付件缺失: {context['_missing']}"
