"""Story 6-6 Checkpoint 摘要查看与恢复——BDD 验收步骤实现。

模板基准: tests/acceptance/test_acceptance_postgresql_relational_layer.feature/.py
（R6——# language: zh-CN 中文 Gherkin + AC 横幅注释分组（# === 分隔）+
@scenario 多行字面量路径绑定 + 14 场景全绑定；R6 自身 py 仅绑定部分场景且缺
pytestmark/context dict/_run_async 属旧模板欠账——本文件 14 场景全绑定，三件套
由 6-1/6-2/6-3 基建承载）。装配形态对齐 6-3（真实服务链 + Fake LLM/Fake
Embedding 双豁免（外部 SaaS）+ 延迟 import 纪律 + 场景三属性分档表 docstring +
teardown 链「断言失败也执行」）。

14 场景三属性分档表（Task 0.4 钉死——层级/LLM 依赖/服务门控）：

| #  | 场景                                    | 层级     | LLM    | 服务门控                    | 调用面          |
|----|-----------------------------------------|----------|--------|-----------------------------|-----------------|
| 1  | AC-1.1 清单全量+sync 推导               | 用例级   | Fake   | Redis+PG+Qdrant+MinIO       | 编程面          |
| 2  | AC-1.2 详情九键（CLI show 入口）        | CLI 级   | Fake   | 同上                        | CLI in-process  |
| 3  | AC-2.1 修正往返与连续累积               | 用例级   | Fake   | 同上                        | 编程面          |
| 4  | AC-2.2 482/242 修正与编号异常           | 服务级   | Fake   | 同上                        | 编程面+CLI 局部 |
| 5  | AC-3.1 Override 执行+尾点边界           | 用例级   | Fake   | 同上                        | 编程面          |
| 6  | AC-3.2 Replay 执行三态                  | 用例级   | Fake   | 同上                        | 编程面          |
| 7  | AC-3.3 模式冲突 487 零副作用            | 用例级   | Fake   | 同上                        | 编程面          |
| 8  | AC-4.1 dry-run 三零                     | CLI 级   | Fake   | 同上                        | CLI in-process  |
| 9  | AC-4.2 confirm+修正恢复一体+outbox      | 用例级   | Fake   | 同上+真实 publisher         | 编程面          |
| 10 | AC-5.1 五路并发互不干扰                 | 用例级   | Fake   | 同上                        | 编程面（gather）|
| 11 | AC-6.1 摘要双窗口 P95                   | 服务级   | Fake   | 同上                        | 编程面采样      |
| 12 | AC-6.2 恢复窗口+成功率                  | 用例级   | Fake   | 同上                        | 编程面采样      |
| 13 | AC-7.1 480/484 恢复入口异常             | 服务级   | Fake   | 同上                        | 编程面          |
| 14 | 收尾完成清单                            | 静态清单 | 无     | 无                          | 无服务调用      |

逐场景调用面矩阵（Task 0.5 钦定——验收步骤的驱动面）：S1/S3/S4(242 腿)/S5/S6/
S7/S9/S10/S12/S13 = 编程面（用例/服务直调——断言锚 Outcome/恢复记录/事件在编程面
单源可达）；S2/S8 = CLI 面 in-process 直调 agent_cli.main（dry-run 是 CLI-only
状态；**每次 CLI 直调前 clear_singleton()+clear_scoped() 双清钦定**——CLI 函数体内
asyncio.run 新建 event loop+resolve，全局 resolver 单例绑旧 loop 时「Event loop is
closed」+ SCOPED snapshot_repository 残留死 loop 客户端使 load 吞错静默假 480/假
in_sync（R3 实跑证伪单清形态；markdown_report.py 双清先例）；禁重新 bootstrap——
registry spec 持久+_ensure_bootstrapped 自动短路，双清实例即可）；S4(482 腿)/S11
采样 = 编程面（S11 采样窗口钉死=recover_checkpoint 数据面窗口+list_checkpoints
窗口——经 CLI 进程面采样会把 ensure_bootstrapped+asyncio.run 建连开销计入窗口
冲破 200ms 口径）；CLI 交互面的完整参数/输出覆盖由 tests/unit/interfaces/cli/
test_agent_cli.py 承载（验收只覆盖 S2/S8 两态关键路径 CLI 形态）；S14 收尾=src
与四测试目录存在性断言，无服务调用面。

门控档位（服务不可达环境 pytest.skip() 动态跳过——禁 @pytest.mark.skip 写死）：
Redis = ping 探测；PG = 连接 + event_outbox/strategic_archives 表存在双预检；
Qdrant = get_collections 探测；MinIO = 桶健康探测。strategic_archive_service 组合根
lambda 强制依赖 embedding_service（外部 SaaS）——Fake Embedding（固定维度向量
AsyncMock 注入，L3 写入链可构造）与 Fake LLM（压缩摘要 generate 消费点）同为外部
SaaS 豁免；entity_extractor 用真实规则基 RuleBasedExtractor（纯规则无 LLM）。

创建侧值域纪律（6.3-R1-DF1 互锁解除继承）：本 Story 验收的 checkpoint 创建侧
stage_id 一律取 performance_gap（CP-1 对应值——与 checkpoint_no 编号无关，
CP-3/CP-5/CP-8 创建同用此值；禁用 market_insight 值域——6-2 侧 LIKE 无 plan_id
过滤通道会捕获假红）；创建侧 CheckpointReached 行照常产生（teardown 定向 DELETE
覆盖创建侧行——键计数净增 0 纪律）；恢复链新增发布 CheckpointRecovered（不同
event_type 通道，与 6-2 LIKE 断言面正交）。

延迟 import 纪律：本 Story 新交付模块（application/use_cases/checkpoint_approval、
CheckpointServicePort 新方法 list_checkpoints/execute_recovery、domain 异常 486/487、
CLI 三命令）一律步骤函数/装配函数体内延迟 import——模块顶部 import 会使 pytest
收集期整文件 collection error，Task 0 预期红因 = 运行期 ImportError（缺失类名；
6-2/6-3 先例——收集期零错误本身即延迟 import 纪律的自证）。

gather 并发会话契约（AC-5/OD-10）：S10 五路并发的创建与恢复均入 gather——
per-plan 协程体内自建 AsyncSession 并 set_session()（PEP 567 task 级 context 拷贝
使 set 不外泄，深层 get_session() 调用期解析自动命中本任务会话——outbox_repository
.save 优先 get_session() 实证；共享装配链单 AsyncSession 形态下并发写必触发
SQLAlchemy 并发会话防呆）；每任务会话生命周期 try/finally 收口（begin→执行→
commit（异常 rollback）→close）。

性能口径（OD-8 三段声明）：①摘要显示 P95<200ms = show 单点窗口（recover_
checkpoint 数据面 load+verify+视图组装）与 list 清单窗口（≤8 点 probe+恢复记录
join）双覆盖，20 轮采样 sorted(durations)[ceil(0.95*n)-1]（n=20 升序取次大值）、
预热含首次 load（连接池建立——R8-F5 注记继承）；②恢复执行成功率 100% = N 次
恢复 N 次恢复记录可读回（强制环节零吞错）；③Replay P95<60s/Override P95<15s
（epics 6.3 L2164 完整执行口径归 6-6 的兑现）= 引擎编排窗口口径（②~⑤步纯数据面
毫秒量级）——**口径差声明**：引擎窗口不含 LLM 重跑（OD-1 defer 归 Epic 10），
断言载体=Outcome.execution_ms（①~⑤组装点窗口 ⊇ ②~⑤引擎声明窗口，含①守卫解析
差为保守方向）；逐次 <15s 断言严格蕴含 P95<15s≤P95<60s 双门禁。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_checkpoint_recovery.py -v
"""

from __future__ import annotations

import asyncio
import math
import time
import uuid
from collections.abc import Awaitable, Generator
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pytest_bdd import given, scenario, then, when

from src.infrastructure.storage.redis.key_builder import build_key

# marker 名以 pyproject 注册为准（database 非 postgresql——6-3 R2-F23 钦定）；
# xdist_group 整模块 pytestmark 级——与 6-3 验收+集成同 worker 串行（互锁结构
# 前提 R8-F2 注记继承）
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.database,
    pytest.mark.redis,
    pytest.mark.qdrant,
    pytest.mark.minio,
    pytest.mark.xdist_group("blm-planning-perf"),
]

#: _run_async 泛型参数（协程返回类型透传）
_T = TypeVar("_T")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: 摘要视图 8 键契约（Task 0.1 冻结唯一版本——期望值独立构造，禁经被测服务生成）
EXPECTED_SUMMARY_VIEW_KEYS: tuple[str, ...] = (
    "checkpoint_no",
    "stage_id",
    "completed",
    "summary",
    "state_version",
    "created_via",
    "timestamp",
    "sync_status",
)

#: 恢复视图 9 键契约（6-3 既有——零改动复用；checkpoint-show 直出面）
EXPECTED_RECOVERY_VIEW_KEYS: tuple[str, ...] = (
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

#: 恢复执行结果 10 键契约（Task 0.1 冻结唯一版本）
EXPECTED_OUTCOME_KEYS: tuple[str, ...] = (
    "checkpoint_no",
    "recovery_mode",
    "corrected",
    "new_state_version",
    "affected_checkpoints",
    "marked_checkpoints",
    "execution_ms",
    "next_action_hint",
    "recovery_record_session_id",
    "recovered_snapshot_id",
)

#: 恢复记录 state_data 12 键契约（第三键族载荷——Task 0.1 冻结唯一版本）
EXPECTED_RECOVERY_RECORD_KEYS: tuple[str, ...] = (
    "plan_id",
    "checkpoint_no",
    "recovery_mode",
    "corrected",
    "correction",
    "affected_checkpoints",
    "pending_sync_checkpoints",
    "invalidated_checkpoints",
    "confirmed_by",
    "recovered_at",
    "execution_ms",
    "created_via",
)

#: 恢复记录会话前缀字面量（OD-3 第三键族——断言侧字面量防 import 自证，
#: 单源常量在 application/ports/checkpoint.py）
CHECKPOINT_RECOVERY_SESSION_PREFIX_LITERAL = "blm-checkpoint-recovery-"

#: 完整形态快照会话前缀字面量（6-3 既有——与恢复记录前缀互异判别）
CHECKPOINT_SESSION_PREFIX_LITERAL = "blm-checkpoint-"

#: 恢复记录 TTL（30 天——对齐 checkpoint 键族合规窗）
RECOVERY_RECORD_TTL_SECONDS: int = 2_592_000

#: sync_status 三值域（AC-1 钦定）
SYNC_STATUS_IN_SYNC = "in_sync"
SYNC_STATUS_PENDING = "pending_sync"
SYNC_STATUS_INVALIDATED = "invalidated"

#: 摘要显示窗口 P95 门禁（毫秒——AC-6/epics L2330）
SUMMARY_P95_LIMIT_MS: float = 200.0

#: 恢复执行窗口门禁（秒——逐次断言严格蕴含 P95<15s≤P95<60s 双门禁）
RECOVERY_WINDOW_LIMIT_SECONDS: float = 15.0

#: P95 采样轮数（AC-6——6-3 AC-8 数学口径同款）
PERF_SAMPLE_ROUNDS: int = 20

#: 并发审批路数（AC-5/epics L2332——5 独立 plan）
CONCURRENT_PLAN_COUNT: int = 5

#: 恢复成功率采样每模式次数（AC-6——Override×5+Replay×5）
RECOVERY_SAMPLES_PER_MODE: int = 5

#: 创建侧 stage_id 值域纪律（6.3-R1-DF1 互锁解除继承——一律 performance_gap）
CREATION_STAGE_ID = "performance_gap"

#: 检索语料（背景建制——长度充分使压缩比 ≥0.70 可构造；6-3 同款）
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

#: Fake LLM 达标压缩产物（6-3 同款——压缩比 ≥0.70 且质量分达标形态）
_FAKE_COMPRESSED_TEXT = (
    "战略语境压缩摘要：市场渗透率提升与技术演进加速并存；财务达成率 87% 与毛利率下滑"
    "需修正；海外市场渗透差距 23 点，三阶段弥合策略以东南亚/中东/拉美为先。"
)


def _run_async(event_loop: asyncio.AbstractEventLoop, awaitable: Awaitable[_T]) -> _T:
    """在模块级事件循环上运行可等待对象（BDD 步骤禁 @pytest.mark.asyncio；
    Awaitable 口径兼容 Coroutine 与 AsyncSessionTransaction 等非协程 awaitable）。"""
    return event_loop.run_until_complete(awaitable)


def _make_search_results() -> list[dict[str, Any]]:
    """构造最小检索证据族（{"id":…, "payload": {"content": …}} 形态——6-3 同款）。"""
    return [
        {"id": f"rec-corpuse-{index}", "score": 0.9, "payload": {"content": text}} for index, text in enumerate(_CORPUS_TEXTS)
    ]


def _new_plan_id() -> str:
    """生成独立 plan_id（UUID 字符串——恢复记录/事件/归档按 plan 天然隔离）。"""
    return str(uuid.uuid4())


def _snapshot_session_id(plan_id: str, checkpoint_no: str) -> str:
    """完整形态快照会话键（期望形态独立构造——blm-checkpoint-{plan}:{cp}）。"""
    return f"{CHECKPOINT_SESSION_PREFIX_LITERAL}{plan_id}:{checkpoint_no}"


def _recovery_session_id(plan_id: str) -> str:
    """恢复记录会话键（期望形态独立构造——blm-checkpoint-recovery-{plan}）。"""
    return f"{CHECKPOINT_RECOVERY_SESSION_PREFIX_LITERAL}{plan_id}"


def _p95(durations: list[float]) -> float:
    """P95 数学口径（sorted 升序取 ceil(0.95*n)-1 位——6-3 AC-8 同款）。"""
    ordered = sorted(durations)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


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
    """BDD 步骤间共享状态容器（场景级独立客户端 + 同循环 teardown 链）。

    teardown 顺序（断言失败也执行）：① 端口覆写还原 + PG 会话收尾；② outbox
    事件行按 event_id/plan_id 精确 DELETE（创建侧 CheckpointReached + 恢复侧
    CheckpointRecovered 两类）；③ Redis 四键族逐键精确删除（快照/恢复记录/
    note/compressed——恢复记录键族调用前预登记，delete 不存在键 no-op）；
    ④⑤ Qdrant 点 / MinIO 对象 / PG 归档行精确清理；⑥ 同循环关闭全部客户端。
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
    """teardown 链（context fixture yield 后执行——断言失败也运行）。

    各步独立 try/except（前步失败不阻断后步——残局防线）；全部 _run_async
    同循环（跨循环 "Event loop is closed" 存档教训）。
    """
    # ① 端口覆写还原（CLI 场景的 resolver 双清还原）+ PG 会话收尾
    #    （①③④ 链级 try/except 包裹——代码审查 R1-F5：对齐 docstring「各步独立
    #    try/except」宣称，前步异常不再阻断后步残局清理）
    for restore in ctx["_restorers"]:
        try:
            restore()
        except Exception:
            pass
    try:
        _run_async(ctx["_loop"], _finalize_pg_session(ctx))
    except Exception:
        pass
    # ② outbox 事件行精确 DELETE（event_id 面 + plan_id 兜底双通道）
    try:
        _cleanup_outbox_rows(ctx)
    except Exception:
        pass
    # ③ Redis 键族逐键精确删除（快照+恢复记录第三键族+note+compressed）
    try:
        _run_async(ctx["_loop"], _cleanup_redis_keys(ctx))
    except Exception:
        pass
    # ④⑤ Qdrant 点 / MinIO 对象 / PG 归档行精确清理
    try:
        _run_async(ctx["_loop"], _cleanup_archive_residues(ctx))
    except Exception:
        pass
    # ⑥ 共享 PG manager 无条件收口（代码审查 R1-F18：close=dispose+置空防复活——
    #    此前仅归档分支 dispose，无归档场景每次泄漏一个连接池；None 守卫防 CLI-only 场景误建）
    if ctx["_pg_manager"] is not None:
        try:
            _run_async(ctx["_loop"], ctx["_pg_manager"].close())
        except Exception:
            pass
    # ⑦ 同循环关闭 Redis 客户端
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
    """Redis 键族精确删除（快照会话键+恢复记录键+note 缓存键+compressed 缓存键）。"""
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
    # ④ Qdrant 点按 payload.archive_id filter 精确删除
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
    """outbox 事件行精确 DELETE（event_id 面 + plan_id 兜底双通道——收集面
    覆盖创建侧 CheckpointReached、恢复侧 CheckpointRecovered 与 ArchiveCreated）。"""
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
# Fake 工厂（外部 SaaS 豁免——Fake LLM / Fake Embedding 双豁免，6-3 同款）
# ===================================================================


def _make_fake_llm() -> Any:
    """Fake LLM 工厂（AsyncMock(spec=LLMClientPort)——外部 SaaS 豁免面）。

    generate 恒返回固定达标压缩产物（压缩比 ≥0.70、质量评估达标——五步链
    一次通过形态；恢复链零 LLM，仅创建前置链消费）。
    """
    from unittest.mock import AsyncMock

    from src.domain.ports.llm_client import LLMClientPort, LLMResponse

    fake = AsyncMock(spec=LLMClientPort)
    fake.generate = AsyncMock(
        return_value=LLMResponse(content=_FAKE_COMPRESSED_TEXT, finish_reason="stop", usage={}, model="fake-llm")
    )
    fake.close = AsyncMock()
    return fake


def _make_fake_embedding() -> Any:
    """Fake Embedding 工厂（AsyncMock(spec=EmbeddingServicePort)——外部 SaaS 豁免）。"""
    from unittest.mock import AsyncMock

    from src.domain.ports.embedding_service import EmbeddingServicePort

    fake = AsyncMock(spec=EmbeddingServicePort)
    fake.embed_query = AsyncMock(return_value=[0.1] * 1024)
    fake.embed_documents = AsyncMock(return_value=[[0.1] * 1024])
    fake.close = AsyncMock()
    return fake


# ===================================================================
# 装配链（四真实服务 + Fake LLM/Fake Embedding 双豁免——6-3 基座扩展恢复链）
# ===================================================================


def _resolve_archive_bucket_name(ctx: dict[str, Any]) -> str:
    """解析 archive-evidence 物理 bucket 名（经组合根 l4_object 实例内部锚解析）。"""
    from src.domain.ports.resolver import resolve

    l4 = resolve("l4_object")
    return str(l4._repository._resolve_bucket_name("archive-evidence"))


def _assemble_recovery_chain(context: dict[str, Any]) -> None:
    """装配 Checkpoint 摘要与恢复链（用例级——Task 7 全场景转绿形态）。

    真实面：Redis（快照+恢复记录存储 + L1 缓存）+ PG（archive L2 + outbox
    落行，AsyncSession/SessionContext 激活）+ Qdrant（L3 向量）+ MinIO（L4
    WORM 对象）；Fake 面：LLMClientPort + EmbeddingServicePort（外部 SaaS
    双豁免）。与 6-3 装配的差异面：event_publisher 用真实 publisher
    （resolve("event_publisher")——CheckpointRecovered 发布是本 Story 验收
    断言面；创建侧行经 teardown 定向 DELETE 覆盖）+ 恢复链两用例（延迟
    import——Task 0 红因承载）。
    """
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.application.services.checkpoint_service import CheckpointService
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.application.use_cases.create_checkpoint import CreateCheckpointUseCase, RecoverCheckpointUseCase
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
    #    套记录壳——note:/compressed: 键随 take_notes 全路径登记进清理面）
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
            context["_note_cache_keys"].append(f"note:{note.note_id}")
            context["_compressed_cache_keys"].append(f"compressed:{note.note_id}")
            return note

    note_taker = _RecordingNoteTaker(
        entity_extractor=RuleBasedExtractor(),
        audit_service=None,
        l1_cache=redis_adapter,
    )
    compressor = ContextCompressor(
        llm_client=_make_fake_llm(),
        note_taker=note_taker,
        quality_evaluator=CompressionQualityEvaluator(),
        l1_cache=redis_adapter,
    )

    # 3) PG 会话激活（SessionContext——归档 L2 仓储 + outbox 落行前置）+ 归档服务
    from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore

    context["_snapshot_repository_local"] = RedisSnapshotStore(adapter=redis_adapter)
    session = AsyncSession(context["_pg_manager"].get_async_engine())
    _run_async(context["_loop"], session.begin())
    context["_pg_session"] = session
    context["_pg_session_token"] = set_session(session)
    archive_service = StrategicArchiveService(
        archive_repo=resolve("archive_repository"),
        embedding_service=_make_fake_embedding(),  # 外部 SaaS 豁免
        vector_storage=resolve("l3_vector"),
        object_storage=resolve("l4_object"),
        graph_storage=None,  # L5 可选降级
        event_publisher=None,
        staleness_service=None,
    )

    # 4) Checkpoint 编排服务（五依赖组合注入——event_publisher 用真实 publisher：
    #    CheckpointRecovered 落行是 S5/S6/S9/S10 的 outbox 断言面）+ 三用例
    snapshot_repository = context["_snapshot_repository_local"]
    get_resolver().clear_singleton()
    real_publisher = resolve("event_publisher")
    checkpoint_service = CheckpointService(
        note_taker=note_taker,
        compressor=compressor,
        archive_service=archive_service,
        snapshot_repository=snapshot_repository,
        event_publisher=real_publisher,
    )
    context["_checkpoint_service"] = checkpoint_service
    context["_snapshot_repository"] = snapshot_repository
    context["_use_case"] = CreateCheckpointUseCase(checkpoint_service=checkpoint_service)
    context["_recovery_view_use_case"] = RecoverCheckpointUseCase(checkpoint_service=checkpoint_service)
    # 恢复链两新用例（延迟 import——Task 0 红因承载：模块缺失即 ImportError）
    from src.application.use_cases.checkpoint_approval import (
        ExecuteCheckpointRecoveryUseCase,
        ListCheckpointsUseCase,
    )

    context["_list_use_case"] = ListCheckpointsUseCase(checkpoint_service=checkpoint_service)
    context["_recovery_execute_use_case"] = ExecuteCheckpointRecoveryUseCase(checkpoint_service=checkpoint_service)
    context["_resolver"] = get_resolver()


def _create_checkpoint(context: dict[str, Any], *, plan_id: str, checkpoint_no: str, query: str = "五年战略规划") -> Any:
    """经用例层直调创建 Checkpoint（默认参 created_via='use_case'——登记键进清理面）。"""
    session_id = _snapshot_session_id(plan_id, checkpoint_no)
    context["_snapshot_session_ids"].append(session_id)
    context["_archive_plan_ids"].append(plan_id)
    context["_outbox_plan_ids"].append(plan_id)
    return _run_async(
        context["_loop"],
        context["_use_case"].execute(
            plan_id=plan_id,
            checkpoint_no=checkpoint_no,
            stage_id=CREATION_STAGE_ID,
            query=query,
            retrieved_docs=_make_search_results(),
            user_id="acceptance-executor",
            summary=f"{checkpoint_no} 阶段摘要（验收直供）",
        ),
    )


def _register_recovery_record(context: dict[str, Any], plan_id: str) -> None:
    """恢复记录键预登记（R1-F1 键清理面纪律——恢复执行前登记，delete 不存在键 no-op）。"""
    context["_snapshot_session_ids"].append(_recovery_session_id(plan_id))


def _commit_pg_session(context: dict[str, Any]) -> None:
    """共享 PG 会话提交（outbox 行/归档行同事务——提交后独立连接可见）。"""

    async def _commit() -> None:
        session = context.get("_pg_session")
        if session is None:
            return
        await session.commit()

    _run_async(context["_loop"], _commit())


def _clear_resolver_caches() -> None:
    """resolver SINGLETON/SCOPED 双清（CLI 直调跨 loop 防线——markdown_report 先例）。"""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()


def _load_recovery_record(context: dict[str, Any], plan_id: str) -> Any:
    """恢复记录读回（经装配链 snapshot_repository.load——第三键族同形态承载）。"""
    return _run_async(context["_loop"], context["_snapshot_repository"].load(_recovery_session_id(plan_id)))


def _query_outbox_recovered(context: dict[str, Any], plan_id: str) -> list[dict[str, Any]]:
    """查询 CheckpointRecovered 落行（checkpoint_id 新键路径+metadata.plan_id 先例通道——5 分钟窗）。

    断言键通道钦定（AC-4 VC）：payload->'payload'->>'checkpoint_id'（子类字段经
    base.py to_dict 并入 payload 子字典——新键路径，6-3 先例通道是
    phase_identifier/user_feedback_request）+ payload->'metadata'->>'plan_id'
    （R3-3 双关联键——6-3 直系先例通道）。
    """
    import sqlalchemy as sa

    async def _query() -> list[dict[str, Any]]:
        engine = context["_pg_manager"].get_async_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT event_id, event_type, "
                        "payload->'payload'->>'checkpoint_id' AS checkpoint_id, "
                        "payload->'payload'->>'recovery_mode' AS recovery_mode, "
                        "payload->'payload'->>'consistency_risk_level' AS consistency_risk_level, "
                        "payload->'metadata'->>'plan_id' AS metadata_plan_id "
                        "FROM event_outbox "
                        "WHERE event_type = 'CheckpointRecovered' "
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
                "checkpoint_id": row[2],
                "recovery_mode": row[3],
                "consistency_risk_level": row[4],
                "metadata_plan_id": row[5],
            }
            for row in rows
        ]

    return _run_async(context["_loop"], _query())


# ===================================================================
# 场景绑定（14 场景全绑定——R6 欠账禁沿用）
# ===================================================================


@scenario(
    "test_acceptance_checkpoint_recovery.feature",
    "清单全量列出与 sync 状态推导（plan 级摘要查看）",
)
def test_list_checkpoints_with_sync_status() -> None:
    """S1/AC-1.1 清单全量 probe+sync join+空 plan 边界（8 键 VO）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_recovery.feature",
    "单点详情九键视图输出（CLI checkpoint-show 入口）",
)
def test_show_checkpoint_via_cli() -> None:
    """S2/AC-1.2 详情九键+四要素显示（CLI checkpoint-show in-process 直调保红）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_recovery.feature",
    "修正往返与连续修正累积（版本递增与 checksum 完整性闭环）",
)
def test_correction_roundtrip_and_accumulation() -> None:
    """S3/AC-2.1 修正往返+连续修正两条累积+版本递增+checksum 绿（经 Execute 用例保红）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_recovery.feature",
    "修正与编号异常分立（482 旧基线与 242 畸形与部分参数）",
)
def test_correction_and_number_validation_errors() -> None:
    """S4/AC-2.2+AC-7 242/482 分立（畸形 242 面在此承载——AC-7 钦定）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_recovery.feature",
    "Override 恢复执行（pending_sync 标记与恢复后再查清单）",
)
def test_override_recovery_pending_sync() -> None:
    """S5/AC-3.1 Override 全链+pending_sync 一点+再查清单两态+尾点边界（独立 plan）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_recovery.feature",
    "Replay 恢复执行（invalidated 全标与重跑指引）",
)
def test_replay_recovery_invalidated() -> None:
    """S6/AC-3.2 Replay 全标 invalidated+三态清单+重跑指引非空。"""
    pass


@scenario(
    "test_acceptance_checkpoint_recovery.feature",
    "模式强制执法拒绝（487 零副作用）",
)
def test_mode_conflict_rejected_zero_side_effect() -> None:
    """S7/AC-3.3 强制 Replay 违反→487（记录未写/事件未发/版本不变——零副作用）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_recovery.feature",
    "无确认恢复调用输出影响评估（dry-run 三零）",
)
def test_dry_run_assessment_three_zeros() -> None:
    """S8/AC-4.1 dry-run 两态（评估输出含修正展示+exit 0+三零断言）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_recovery.feature",
    "确认恢复执行与修正恢复一体（CheckpointRecovered 恰一行）",
)
def test_confirm_recovery_with_correction_one_row() -> None:
    """S9/AC-4.2 confirm+修正一体+outbox 恰一行（checkpoint_id 新键路径值级单源）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_recovery.feature",
    "五路并发恢复互不干扰（独立 plan 各自成功）",
)
def test_five_way_concurrent_recovery() -> None:
    """S10/AC-5 gather 5 路（每任务会话隔离——互不干扰+分组恰一行）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_recovery.feature",
    "摘要显示窗口 P95 小于 200ms（show 与 list 双窗口 20 轮）",
)
def test_summary_display_p95_under_200ms() -> None:
    """S11/AC-6.1 show+list 双窗口 20 轮采样 P95（编程面数据面窗口口径）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_recovery.feature",
    "恢复执行窗口与成功率（双模式采样逐次小于 15s）",
)
def test_recovery_window_and_success_rate() -> None:
    """S12/AC-6.2 Override×5+Replay×5 逐次窗口+10 次全读回（成功率 100%）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_recovery.feature",
    "恢复执行入口异常分立（480 不存在与 484 校验失败）",
)
def test_recovery_entry_errors_480_484() -> None:
    """S13/AC-7 五码验收面残两条（480/484——242/482 在 S4、487 在 S7 承载）。"""
    pass


@scenario(
    "test_acceptance_checkpoint_recovery.feature",
    "开发完成清单收尾（src 与四测试目录交付件存在性）",
)
def test_development_completion_checklist() -> None:
    """S14/收尾——src 与四测试目录完成清单逐项存在性断言（Task 7.3 承载）。"""
    pass


# ===================================================================
# Background 门控 + 装配
# ===================================================================


@given("Redis 服务可用")
def redis_service_available(context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """Redis 连通性门控（Background——不可达环境动态 skip）+ CLI 输出捕获装配。"""
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
    # CLI 直调输出捕获（capsys fixture 引用存入 context——S2/S8 步骤消费；非 CLI 场景不消费）
    context["_capsys_ref"] = capsys


@given("Checkpoint 创建链服务可用")
def checkpoint_chain_available(context: dict[str, Any]) -> None:
    """四真实服务双探测门控 + 摘要恢复链装配（PG/Qdrant/MinIO 逐档 skip）。"""
    _probe_postgres(context)
    _probe_qdrant(context)
    _probe_minio(context)
    _assemble_recovery_chain(context)
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
    """Qdrant 连通性门控 + strategic_archive collection 确保（向量维度 1024）。"""
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
    """MinIO 连通性门控 + archive-evidence 物理 bucket 确保（object-lock 形态）。"""
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

    try:
        _run_async(context["_loop"], asyncio.to_thread(_probe))
    except Exception as exc:
        pytest.skip(f"MinIO 不可用: {exc}")


# ===================================================================
# AC-1: 清单与摘要查看
# ===================================================================


@given("某 plan 下已创建 CP-1 与 CP-3 与 CP-5 三个 Checkpoint")
def three_checkpoints_created(context: dict[str, Any]) -> None:
    """三 Checkpoint 前置（分 Given 步逐个创建——6-3 R2-F6 先例；stage 值域纪律）。"""
    context["_plan_id"] = _new_plan_id()
    for checkpoint_no in ("CP-1", "CP-3", "CP-5"):
        _create_checkpoint(context, plan_id=context["_plan_id"], checkpoint_no=checkpoint_no)
    _commit_pg_session(context)
    context["_outbox_plan_ids"].append(context["_plan_id"])


@given("某 plan 下已创建 CP-1 Checkpoint")
def single_checkpoint_created(context: dict[str, Any]) -> None:
    """单 Checkpoint 前置（S2/S3/S4/S13 共用文本）。"""
    context["_plan_id"] = _new_plan_id()
    _create_checkpoint(context, plan_id=context["_plan_id"], checkpoint_no="CP-1")
    _commit_pg_session(context)


@when("高管请求查看该 plan 的 Checkpoint 清单")
def request_checkpoint_list(context: dict[str, Any]) -> None:
    """清单请求（编程面——ListCheckpointsUseCase 直调；延迟 import 红锚）。"""
    context["_summary_list"] = _run_async(
        context["_loop"],
        context["_list_use_case"].execute(plan_id=context["_plan_id"]),
    )
    # 空 plan 边界（AC-1 VC：零 checkpoint 返回空清单不抛 480）
    context["_empty_plan_id"] = _new_plan_id()
    context["_empty_summary_list"] = _run_async(
        context["_loop"],
        context["_list_use_case"].execute(plan_id=context["_empty_plan_id"]),
    )


@then("清单按编号升序返回三个条目且各携带 8 键摘要")
def list_three_entries_eight_keys(context: dict[str, Any]) -> None:
    """清单场景断言（升序+8 键 exact set——多键/缺键均违规）。"""
    summaries = context["_summary_list"]
    assert isinstance(summaries, list), f"清单实测类型={type(summaries)} 期望 list"
    assert len(summaries) == 3, f"清单条目实测={len(summaries)} 期望=3（probe 全量从 CP-1 起）"
    assert [s.checkpoint_no for s in summaries] == ["CP-1", "CP-3", "CP-5"], (
        f"清单编号序实测={[s.checkpoint_no for s in summaries]} 期望升序 ['CP-1', 'CP-3', 'CP-5']"
    )
    for summary in summaries:
        if hasattr(summary, "__dataclass_fields__"):
            actual_keys = set(summary.__dataclass_fields__.keys())
        else:
            actual_keys = set(vars(summary).keys())
        assert actual_keys == set(EXPECTED_SUMMARY_VIEW_KEYS), (
            f"摘要 8 键契约实测={sorted(actual_keys)} 期望={sorted(EXPECTED_SUMMARY_VIEW_KEYS)}"
        )


@then("无恢复记录时全部条目 sync 状态为 in_sync")
def all_entries_in_sync_without_record(context: dict[str, Any]) -> None:
    """sync 推导边界（无恢复记录→全量 in_sync——键恒在纪律的读侧镜像）。"""
    for summary in context["_summary_list"]:
        assert summary.sync_status == SYNC_STATUS_IN_SYNC, (
            f"{summary.checkpoint_no} sync_status 实测={summary.sync_status!r} 期望={SYNC_STATUS_IN_SYNC!r}"
            "（无恢复记录全量 in_sync）"
        )


@then("空规划的清单请求返回空清单不抛 480")
def empty_plan_returns_empty_list(context: dict[str, Any]) -> None:
    """空 plan 边界（清单是枚举面非单点面——与 recover_checkpoint 单点 480 语义分立）。"""
    assert context["_empty_summary_list"] == [], f"空 plan 清单实测={context['_empty_summary_list']} 期望=[]（枚举面不抛 480）"


@when("高管经 CLI 查看 CP-1 摘要详情")
def show_checkpoint_via_cli(context: dict[str, Any]) -> None:
    """CLI checkpoint-show in-process 直调（双清钦定——R3-1 证伪单清形态防线）。"""
    capsys = context.get("_capsys_ref")
    exit_code, stdout, stderr = 0, "", ""
    from src.entrypoints import agent_cli

    _clear_resolver_caches()
    try:
        exit_code = agent_cli.main(["checkpoint-show", "--plan-id", context["_plan_id"], "--checkpoint-no", "CP-1"])
    except SystemExit as error:  # 红阶段命令未注册 → argparse invalid choice exit 2
        exit_code = int(error.code or 0)
    if capsys is not None:
        captured = capsys.readouterr()
        stdout, stderr = captured.out, captured.err
    _clear_resolver_caches()
    context["_cli_exit_code"] = exit_code
    context["_cli_stdout"] = stdout
    context["_cli_stderr"] = stderr


@then("详情输出 9 键恢复视图且四要素齐备")
def cli_show_nine_keys_four_elements(context: dict[str, Any]) -> None:
    """详情场景断言（exit 0+9 键视图+四要素：阶段标识/完成状态/关键参数/修正响应）。"""
    assert context["_cli_exit_code"] == 0, (
        f"checkpoint-show 退出码实测={context['_cli_exit_code']} 期望=0（stderr={context['_cli_stderr']!r}）"
    )
    stdout = context["_cli_stdout"]
    # 9 键视图逐键输出断言（checkpoint-show 直出 CheckpointRecoveryView 9 键——零适配复用）
    for key in EXPECTED_RECOVERY_VIEW_KEYS:
        assert key in stdout, f"stdout 缺 9 键视图键 {key}（实测输出={stdout!r}）"
    # 四要素显示（epics L2319 钦定）：阶段标识（checkpoint_no+stage 值）/完成状态
    # （completed）/关键参数（summary+correction_history 修正历史）/用户反馈
    # （correction_history 修正响应历史承载）
    assert "CP-1" in stdout, "stdout 缺阶段标识 checkpoint_no=CP-1"
    assert CREATION_STAGE_ID in stdout, "stdout 缺阶段标识 stage 值"
    assert "completed" in stdout, "stdout 缺完成状态 completed 键（state_data keys 列表承载）"
    assert "summary" in stdout, "stdout 缺关键参数 summary 键"
    assert "correction_history" in stdout, "stdout 缺修正历史键（用户反馈要素承载）"
    # 值级断言（AC-1 VC 钦定——6-3 S10 :1719-1725 先例形态继承，代码审查 R1-F2：
    # 键名存在性对「忘填用默认值」零检出，load 快照后值级比对封堵）
    loaded = _run_async(
        context["_loop"],
        context["_snapshot_repository"].load(_snapshot_session_id(context["_plan_id"], "CP-1")),
    )
    assert loaded is not None, "S2 前置快照读回 None（值级断言前提）"
    assert f"state_version: {loaded.state_version}" in stdout, (
        f"stdout state_version 值级失配（实测 stdout 无 'state_version: {loaded.state_version}'）"
    )
    assert f"snapshot_id: {loaded.snapshot_id}" in stdout, (
        "stdout snapshot_id 值级失配（防忘填默认值零检出——R3-2 断言形态兑现）"
    )


# ===================================================================
# AC-2: 关键参数修正（乐观锁闭环）
# ===================================================================


@when("高管经恢复执行用例连续提交两次关键参数修正")
def two_consecutive_corrections_via_use_case(context: dict[str, Any]) -> None:
    """连续修正（编程面 ExecuteCheckpointRecoveryUseCase——延迟 import 红锚）。"""
    from src.domain.entities.checkpoint import CorrectionRecord

    context["_correction_outcomes"] = []
    for index in range(2):
        outcome = _run_async(
            context["_loop"],
            context["_recovery_execute_use_case"].execute(
                plan_id=context["_plan_id"],
                checkpoint_no="CP-1",
                correction=CorrectionRecord(
                    correction_type="L2",
                    previous_value=f"旧值-{index}",
                    new_value=f"新值-{index}",
                    applied_by="高管-审批人",
                ),
                confirmed_by="高管-审批人",
            ),
        )
        context["_correction_outcomes"].append(outcome)
    _commit_pg_session(context)


@then("修正历史累积两条五字段投影且版本递增至 v2")
def correction_history_two_entries_version_v2(context: dict[str, Any]) -> None:
    """连续修正断言（历史累积两条+版本 v0→v1→v2——修正链历史累积语义）。"""
    snapshot = _run_async(
        context["_loop"],
        context["_snapshot_repository"].load(_snapshot_session_id(context["_plan_id"], "CP-1")),
    )
    assert snapshot is not None, "修正后快照读回 None"
    history = snapshot.state_data["correction_history"]
    assert len(history) == 2, f"修正历史实测={len(history)} 条 期望=2（累积——单键单版本语义）"
    entry = history[-1]
    assert set(entry.keys()) == {"correction_type", "previous_value", "new_value", "applied_by", "applied_at"}, (
        f"五字段投影实测键={sorted(entry.keys())}"
    )
    assert entry["correction_type"] == "L2"
    assert entry["new_value"] == "新值-1"
    assert isinstance(entry["applied_at"], str) and entry["applied_at"], "applied_at 须为 isoformat 字符串（五字段投影）"
    assert snapshot.state_version == 2, f"版本实测={snapshot.state_version} 期望=2（v0→v1→v2）"
    outcomes = context["_correction_outcomes"]
    assert [o.corrected for o in outcomes] == [True, True], "两次修正 corrected 均应为 True"
    assert [o.new_state_version for o in outcomes] == [1, 2], "Outcome 版本链 1→2"


@then("修正后快照读回校验绿（checksum 完整性闭环）")
def corrected_snapshot_verify_green(context: dict[str, Any]) -> None:
    """修正链完整性闭环（6-3 AC-3 语义在入口面复证）。"""
    snapshot = _run_async(
        context["_loop"],
        context["_snapshot_repository"].load(_snapshot_session_id(context["_plan_id"], "CP-1")),
    )
    assert snapshot is not None and snapshot.verify_integrity(), "修正后快照 verify 红（checksum 重算封印断裂）"


@given("某 plan 下已创建 CP-1 Checkpoint 并已完成一次修正")
def checkpoint_with_one_correction(context: dict[str, Any]) -> None:
    """482 场景前置（v1 存活——经编程面 apply_correction 构造基线漂移）。"""
    from src.domain.entities.checkpoint import CorrectionRecord

    context["_plan_id"] = _new_plan_id()
    _create_checkpoint(context, plan_id=context["_plan_id"], checkpoint_no="CP-1")
    _run_async(
        context["_loop"],
        context["_checkpoint_service"].apply_correction(
            session_id=_snapshot_session_id(context["_plan_id"], "CP-1"),
            correction=CorrectionRecord(correction_type="L1", previous_value="旧", new_value="新", applied_by="前置修正人"),
            expected_state_version=0,
        ),
    )
    _commit_pg_session(context)


@when("以旧基线版本提交修正或提交畸形编号或仅提交部分修正参数")
def stale_baseline_or_malformed_or_partial(context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """三腿异常构造（482 编程面 / 242 畸形编程面 / 242 部分参数 CLI 面）。"""
    from src.domain.entities.checkpoint import CorrectionRecord
    from src.domain.exceptions import EntityValidationError, PlanningStateError
    from src.entrypoints import agent_cli

    # 腿一：旧基线修正（expected=0 对存活 v1）→ 482 透传（6-3 R6-2 两步构造法）
    context["_stale_error"] = None
    try:
        _run_async(
            context["_loop"],
            context["_checkpoint_service"].apply_correction(
                session_id=_snapshot_session_id(context["_plan_id"], "CP-1"),
                correction=CorrectionRecord(correction_type="L1", previous_value="a", new_value="b", applied_by="x"),
                expected_state_version=0,
            ),
        )
    except PlanningStateError as error:
        context["_stale_error"] = error

    # 腿二：畸形 checkpoint_no 恢复执行 → 242（_parse_checkpoint_number 三重守卫复用）
    context["_malformed_error"] = None
    try:
        _run_async(
            context["_loop"],
            context["_recovery_execute_use_case"].execute(
                plan_id=context["_plan_id"],
                checkpoint_no="cp3",
                confirmed_by="高管",
            ),
        )
    except EntityValidationError as error:
        context["_malformed_error"] = error

    # 腿三：CLI 四参数部分出现（仅 --correction-type）→ 242（CLI 层唯一落位）
    _clear_resolver_caches()
    context["_partial_exit_code"] = -1
    context["_partial_stderr"] = ""
    try:
        context["_partial_exit_code"] = agent_cli.main(
            [
                "checkpoint-recover",
                "--plan-id",
                context["_plan_id"],
                "--checkpoint-no",
                "CP-1",
                "--correction-type",
                "L2",
            ]
        )
    except SystemExit as error:
        context["_partial_exit_code"] = int(error.code or 0)
    context["_partial_stderr"] = capsys.readouterr().err
    _clear_resolver_caches()


@then("旧基线修正抛 482 透传")
def stale_baseline_raises_482(context: dict[str, Any]) -> None:
    """482 断言（apply_correction 乐观锁既有触发点透传）。"""
    error = context["_stale_error"]
    assert error is not None, "旧基线修正未抛 PlanningStateError（482 透传断裂）"
    assert error.code == "EXCEPTION_482", f"实测 code={error.code}"


@then("畸形编号与部分修正参数分别抛 242")
def malformed_and_partial_raise_242(context: dict[str, Any]) -> None:
    """242 双腿断言（畸形编号守卫+CLI 层四参数成组检测）。"""
    malformed = context["_malformed_error"]
    assert malformed is not None, "畸形 checkpoint_no 未抛 EntityValidationError（242 守卫断裂）"
    assert malformed.code == "EXCEPTION_242", f"畸形腿实测 code={malformed.code}"
    assert context["_partial_exit_code"] == 1, f"CLI 部分参数退出码实测={context['_partial_exit_code']} 期望=1（242 业务异常）"
    assert "[EXCEPTION_242]" in context["_partial_stderr"], (
        f"CLI stderr 实测={context['_partial_stderr']!r} 期望含 [EXCEPTION_242]（成组约束 CLI 层唯一落位）"
    )


# ===================================================================
# AC-3: 双模式恢复执行
# ===================================================================


@when("高管确认恢复 CP-3（Override 模式）")
def confirm_recovery_cp3_override(context: dict[str, Any]) -> None:
    """Override 恢复执行（后续仅 CP-5 → 建议 Override；编程面默认建议模式）。"""
    _register_recovery_record(context, context["_plan_id"])
    context["_recovery_outcome"] = _run_async(
        context["_loop"],
        context["_recovery_execute_use_case"].execute(
            plan_id=context["_plan_id"],
            checkpoint_no="CP-3",
            confirmed_by="高管-审批人",
        ),
    )
    _commit_pg_session(context)


@then("恢复记录 12 键落库且后续 CP-5 标记 pending_sync")
def override_record_twelve_keys_pending_sync(context: dict[str, Any]) -> None:
    """恢复记录断言（12 键 exact set+Override 分支 pending_sync 一点）。"""
    outcome = context["_recovery_outcome"]
    record = _load_recovery_record(context, context["_plan_id"])
    assert record is not None, "恢复记录读回 None（第三键族落库断裂）"
    actual_keys = set(record.state_data.keys())
    assert actual_keys == set(EXPECTED_RECOVERY_RECORD_KEYS), (
        f"恢复记录 12 键契约实测={sorted(actual_keys)} 期望={sorted(EXPECTED_RECOVERY_RECORD_KEYS)}"
    )
    state = record.state_data
    assert state["checkpoint_no"] == "CP-3", f"恢复起点实测={state['checkpoint_no']}"
    assert state["recovery_mode"] == "override", f"recovery_mode 实测={state['recovery_mode']!r}（entities 小写形态）"
    assert state["pending_sync_checkpoints"] == ["CP-5"], (
        f"pending_sync 清单实测={state['pending_sync_checkpoints']} 期望=['CP-5']（Override 后续 ≤1）"
    )
    assert state["invalidated_checkpoints"] == [], "Override 分支 invalidated 恒空清单（键恒在纪律）"
    assert state["confirmed_by"] == "高管-审批人", "审批留痕 confirmed_by 值级断言"
    assert outcome.recovery_record_session_id == _recovery_session_id(context["_plan_id"]), (
        "Outcome 审计回溯锚与恢复记录键不一致"
    )


@then("事件 recovery_mode 为 Override 且一致性风险为 medium")
def override_event_mode_and_risk(context: dict[str, Any]) -> None:
    """Override 事件断言（outbox recovery_mode 大写+medium 风险——同源消费判别腿）。"""
    rows = _query_outbox_recovered(context, context["_plan_id"])
    context["_outbox_event_ids"].extend(row["event_id"] for row in rows)
    assert len(rows) == 1, f"CheckpointRecovered 落行实测={len(rows)} 期望=1"
    row = rows[0]
    assert row["recovery_mode"] == "Override", (
        f"事件 recovery_mode 实测={row['recovery_mode']!r} 期望='Override'（events 枚举大写形态——转换函数消费面）"
    )
    assert row["consistency_risk_level"] == "medium", (
        f"一致性风险实测={row['consistency_risk_level']!r} 期望='medium'（Override+有后续——同源计算唯一可判别腿）"
    )
    assert row["metadata_plan_id"] == context["_plan_id"]


@then("恢复后再查清单呈现 in_sync 与 pending_sync 两态")
def list_after_override_two_statuses(context: dict[str, Any]) -> None:
    """sync join 断言（起点恒 in_sync+后续 pending_sync+前序 in_sync）。"""
    summaries = _run_async(
        context["_loop"],
        context["_list_use_case"].execute(plan_id=context["_plan_id"]),
    )
    by_no = {s.checkpoint_no: s.sync_status for s in summaries}
    assert by_no == {"CP-1": SYNC_STATUS_IN_SYNC, "CP-3": SYNC_STATUS_IN_SYNC, "CP-5": SYNC_STATUS_PENDING}, (
        f"恢复后清单 sync 态实测={by_no} 期望 CP-1/CP-3 in_sync + CP-5 pending_sync（恢复起点恒 in_sync 新基线）"
    )


@then("独立规划尾点 CP-8 恢复影响清单为空且风险为 low")
def tail_cp8_empty_affected_low_risk(context: dict[str, Any]) -> None:
    """CP-8 尾点边界（独立第二 plan——同 plan 二次恢复会单键覆盖洗掉三态标记）。"""
    tail_plan_id = _new_plan_id()
    _create_checkpoint(context, plan_id=tail_plan_id, checkpoint_no="CP-8")
    _commit_pg_session(context)
    _register_recovery_record(context, tail_plan_id)
    outcome = _run_async(
        context["_loop"],
        context["_recovery_execute_use_case"].execute(
            plan_id=tail_plan_id,
            checkpoint_no="CP-8",
            confirmed_by="高管-尾点审批人",
        ),
    )
    _commit_pg_session(context)
    assert outcome.affected_checkpoints == [], f"尾点影响清单实测={outcome.affected_checkpoints} 期望=[]（无后续边界）"
    rows = _query_outbox_recovered(context, tail_plan_id)
    context["_outbox_event_ids"].extend(row["event_id"] for row in rows)
    assert len(rows) == 1, f"尾点事件行实测={len(rows)} 期望=1"
    assert rows[0]["consistency_risk_level"] == "low", (
        f"尾点风险实测={rows[0]['consistency_risk_level']!r} 期望='low'（Override 无后续）"
    )


@when("高管确认恢复 CP-1（Replay 模式）")
def confirm_recovery_cp1_replay(context: dict[str, Any]) -> None:
    """Replay 恢复执行（后续 CP-3/CP-5 ≥2 → 建议 REPLAY）。"""
    _register_recovery_record(context, context["_plan_id"])
    context["_recovery_outcome"] = _run_async(
        context["_loop"],
        context["_recovery_execute_use_case"].execute(
            plan_id=context["_plan_id"],
            checkpoint_no="CP-1",
            confirmed_by="高管-审批人",
        ),
    )
    _commit_pg_session(context)


@then("后续清单全部标记 invalidated 且恢复后再查清单呈现三态")
def replay_invalidated_and_three_statuses(context: dict[str, Any]) -> None:
    """Replay 分支断言（invalidated 全标+三态清单全谱——与 S5 合并覆盖 sync 三态）。"""
    outcome = context["_recovery_outcome"]
    record = _load_recovery_record(context, context["_plan_id"])
    assert record is not None, "恢复记录读回 None"
    state = record.state_data
    assert state["recovery_mode"] == "replay", f"recovery_mode 实测={state['recovery_mode']!r}"
    assert state["invalidated_checkpoints"] == ["CP-3", "CP-5"], (
        f"invalidated 清单实测={state['invalidated_checkpoints']} 期望=['CP-3', 'CP-5']（全标）"
    )
    assert state["pending_sync_checkpoints"] == [], "Replay 分支 pending_sync 恒空清单（键恒在纪律）"
    summaries = _run_async(
        context["_loop"],
        context["_list_use_case"].execute(plan_id=context["_plan_id"]),
    )
    by_no = {s.checkpoint_no: s.sync_status for s in summaries}
    assert by_no == {"CP-1": SYNC_STATUS_IN_SYNC, "CP-3": SYNC_STATUS_INVALIDATED, "CP-5": SYNC_STATUS_INVALIDATED}, (
        f"Replay 后清单 sync 态实测={by_no} 期望起点 in_sync+后续全 invalidated（三态全谱）"
    )
    assert outcome.affected_checkpoints == ["CP-3", "CP-5"], "Outcome.affected 与 invalidated 清单恒等（MVP）"


@then("事件 recovery_mode 为 Replay 且重跑指引非空")
def replay_event_mode_and_hint(context: dict[str, Any]) -> None:
    """Replay 事件断言（大写+指引非空——MVP 标记+指引形态）。"""
    outcome = context["_recovery_outcome"]
    rows = _query_outbox_recovered(context, context["_plan_id"])
    context["_outbox_event_ids"].extend(row["event_id"] for row in rows)
    assert len(rows) == 1, f"CheckpointRecovered 落行实测={len(rows)} 期望=1"
    assert rows[0]["recovery_mode"] == "Replay", f"事件 recovery_mode 实测={rows[0]['recovery_mode']!r} 期望='Replay'"
    assert outcome.next_action_hint, "重跑指引 next_action_hint 为空（建议新 plan_id 经 blm-plan 重跑）"


@when("高管显式请求 Override 模式恢复 CP-1 而建议为 Replay")
def explicit_override_against_replay_recommendation(context: dict[str, Any]) -> None:
    """模式冲突构造（≥2 后续+显式 OVERRIDE——执法点②.5 前置于修正应用）。"""
    from src.domain.entities.checkpoint import RecoveryMode
    from src.domain.exceptions import RecoveryModeConflictError

    _register_recovery_record(context, context["_plan_id"])
    context["_mode_conflict_error"] = None
    try:
        _run_async(
            context["_loop"],
            context["_recovery_execute_use_case"].execute(
                plan_id=context["_plan_id"],
                checkpoint_no="CP-1",
                mode=RecoveryMode.OVERRIDE,
                confirmed_by="高管-冲突请求人",
            ),
        )
    except RecoveryModeConflictError as error:
        context["_mode_conflict_error"] = error


@then("恢复拒绝抛 487 且零副作用（记录未写事件未发修正未应用）")
def mode_conflict_487_zero_side_effect(context: dict[str, Any]) -> None:
    """487 零副作用断言（验收层等价形态=记录键不存在+outbox 零行+版本不变）。"""
    error = context["_mode_conflict_error"]
    assert error is not None, "模式冲突未抛 RecoveryModeConflictError（487 执法断裂）"
    assert error.code == "EXCEPTION_487", f"实测 code={error.code}"
    assert "Replay" in error.message and "Override" in error.message, (
        f"487 message 须携建议/请求双模式（可理解性裁决面）——实测={error.message!r}"
    )
    record = _load_recovery_record(context, context["_plan_id"])
    assert record is None, "恢复记录已写入（零副作用破坏——执法点须前置于④）"
    rows = _query_outbox_recovered(context, context["_plan_id"])
    assert rows == [], f"outbox CheckpointRecovered 实测={len(rows)} 行 期望=0（零副作用）"
    snapshot = _run_async(
        context["_loop"],
        context["_snapshot_repository"].load(_snapshot_session_id(context["_plan_id"], "CP-1")),
    )
    assert snapshot is not None and snapshot.state_version == 0, (
        f"state_version 实测={snapshot.state_version if snapshot else None} 期望=0（修正零应用）"
    )


# ===================================================================
# AC-4: 审批确认流程（两态确认+事件落行）
# ===================================================================


@when("高管无确认调用恢复且携带修正参数")
def dry_run_call_with_correction(context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """dry-run 两态（CLI-only 状态——无 --confirm 输出影响评估不执行恢复）。"""
    from src.entrypoints import agent_cli

    _register_recovery_record(context, context["_plan_id"])
    _clear_resolver_caches()
    exit_code: int = -1
    try:
        exit_code = agent_cli.main(
            [
                "checkpoint-recover",
                "--plan-id",
                context["_plan_id"],
                "--checkpoint-no",
                "CP-3",
                "--correction-type",
                "L2",
                "--previous-value",
                "旧战略参数",
                "--new-value",
                "新战略参数",
                "--applied-by",
                "高管-dryrun",
            ]
        )
    except SystemExit as error:
        exit_code = int(error.code or 0)
    captured = capsys.readouterr()
    context["_dryrun_exit_code"] = exit_code
    context["_dryrun_stdout"] = captured.out
    _clear_resolver_caches()


@then("输出影响评估含修正展示且退出码为零")
def dry_run_assessment_output_exit_zero(context: dict[str, Any]) -> None:
    """dry-run 评估断言（exit 0+修正四参数展示+建议模式+风险提示+待确认提示）。"""
    assert context["_dryrun_exit_code"] == 0, f"dry-run 退出码实测={context['_dryrun_exit_code']} 期望=0（评估态非错误）"
    stdout = context["_dryrun_stdout"]
    assert "新战略参数" in stdout, "评估输出缺将应用的修正展示（new_value——仅展示零应用）"
    assert "L2" in stdout, "评估输出缺 correction_type 展示"
    assert "override" in stdout.lower() or "Override" in stdout, "评估输出缺建议模式（后续 CP-5 一点→override）"
    assert "确认" in stdout, "评估输出缺待确认提示"


@then("恢复记录零写入事件零发布修正零应用（三零）")
def dry_run_three_zeros(context: dict[str, Any]) -> None:
    """dry-run 三零断言（记录键不存在+outbox 零行+state_version 不变）。"""
    record = _load_recovery_record(context, context["_plan_id"])
    assert record is None, "dry-run 后恢复记录已写入（三零破坏——评估态禁调引擎）"
    rows = _query_outbox_recovered(context, context["_plan_id"])
    assert rows == [], f"dry-run 后 outbox CheckpointRecovered 实测={len(rows)} 行 期望=0"
    snapshot = _run_async(
        context["_loop"],
        context["_snapshot_repository"].load(_snapshot_session_id(context["_plan_id"], "CP-3")),
    )
    assert snapshot is not None, "CP-3 快照读回 None"
    assert snapshot.state_data["correction_history"] == [], "dry-run 后修正已应用（三零破坏）"
    assert snapshot.state_version == 0, f"dry-run 后 state_version 实测={snapshot.state_version} 期望=0"


@when("高管确认恢复 CP-3 并同时携带关键参数修正")
def confirm_recovery_with_correction(context: dict[str, Any]) -> None:
    """修正+恢复一体（③④⑤链式——correction 与 confirm 同给）。"""
    from src.domain.entities.checkpoint import CorrectionRecord

    _register_recovery_record(context, context["_plan_id"])
    context["_recovery_outcome"] = _run_async(
        context["_loop"],
        context["_recovery_execute_use_case"].execute(
            plan_id=context["_plan_id"],
            checkpoint_no="CP-3",
            correction=CorrectionRecord(
                correction_type="L2",
                previous_value="旧战略参数",
                new_value="新战略参数",
                applied_by="高管-修正人",
            ),
            confirmed_by="高管-确认人",
        ),
    )
    _commit_pg_session(context)


@then("恢复链式成功且事件 modification_content 携五字段投影")
def recovery_with_correction_event_payload(context: dict[str, Any]) -> None:
    """修正一体断言（Outcome.corrected+new_state_version+10 键 exact-set+事件投影五键）。"""
    import json
    from dataclasses import fields

    import sqlalchemy as sa

    outcome = context["_recovery_outcome"]
    assert outcome.corrected is True, "修正一体 corrected 须为 True"
    assert outcome.new_state_version == 1, f"修正后版本实测={outcome.new_state_version} 期望=1（v0→v1）"
    # 10 键 Outcome 契约 exact-set 守护（代码审查 R1-F10：激活既有死常量——
    # 三契约 8/12/10 键中唯一缺 exact-set 断言的一环，增删键不再零检出）
    assert {field.name for field in fields(outcome)} == set(EXPECTED_OUTCOME_KEYS), (
        f"Outcome 键集实测={sorted(field.name for field in fields(outcome))}"
        f" 期望={sorted(EXPECTED_OUTCOME_KEYS)}（Task 0 冻结 10 键契约）"
    )

    async def _query_modification() -> Any:
        engine = context["_pg_manager"].get_async_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT payload->'payload'->'modification_content' AS modification "
                        "FROM event_outbox "
                        "WHERE event_type = 'CheckpointRecovered' "
                        "AND created_at >= NOW() - INTERVAL '5 minutes' "
                        "AND payload->'metadata'->>'plan_id' = :plan_id"
                    ),
                    {"plan_id": context["_plan_id"]},
                )
            ).fetchall()
        await engine.dispose()
        return rows[0][0] if rows else None

    modification = _run_async(context["_loop"], _query_modification())
    assert modification is not None, "事件行缺失（modification_content 通道）"
    content = modification if isinstance(modification, dict) else json.loads(modification)
    assert set(content.keys()) == {"correction_type", "previous_value", "new_value", "applied_by", "applied_at"}, (
        f"modification_content 实测键={sorted(content.keys())} 期望五字段投影"
    )
    assert content["new_value"] == "新战略参数"


@then("outbox 恰一行 CheckpointRecovered（checkpoint_id 与 plan_id 双通道值级）")
def outbox_exactly_one_row_dual_channel(context: dict[str, Any]) -> None:
    """outbox 恰一行（双通道值级——预期值单源 Outcome.recovered_snapshot_id）。"""
    rows = _query_outbox_recovered(context, context["_plan_id"])
    context["_outbox_event_ids"].extend(row["event_id"] for row in rows)
    assert len(rows) == 1, f"CheckpointRecovered 落行实测={len(rows)} 期望=1（恰一行）"
    row = rows[0]
    outcome = context["_recovery_outcome"]
    assert row["checkpoint_id"] == outcome.recovered_snapshot_id, (
        f"checkpoint_id 通道实测={row['checkpoint_id']!r} 期望={outcome.recovered_snapshot_id!r}"
        "（⑤步显式传值——修正一体=③步 sealed.snapshot_id；断言预期值单源=Outcome.recovered_snapshot_id）"
    )
    assert row["metadata_plan_id"] == context["_plan_id"], "metadata.plan_id 双关联键值级断言"


# ===================================================================
# AC-5: 并发审批（5 路互不干扰）
# ===================================================================


@given("五个独立规划各持一个已创建 Checkpoint")
def five_independent_plans_with_checkpoint(context: dict[str, Any]) -> None:
    """5 独立 plan 前置（仅预生成 plan_id——创建入 gather 每任务会话隔离）。"""
    context["_concurrent_plan_ids"] = [_new_plan_id() for _ in range(CONCURRENT_PLAN_COUNT)]


@when("五位高管并发触发恢复执行")
def five_way_concurrent_recovery(context: dict[str, Any]) -> None:
    """gather 5 路（创建+恢复均入 gather——每任务自建 AsyncSession+set_session，
    PEP 567 task 级 context 拷贝不外泄；try/finally 会话生命周期收口）。"""

    async def _one_plan(plan_id: str) -> Any:
        from sqlalchemy.ext.asyncio import AsyncSession

        from src.infrastructure.storage.postgresql.session_context import reset_session, set_session

        engine = context["_pg_manager"].get_async_engine()
        session = AsyncSession(engine)
        try:
            await session.begin()
            token = set_session(session)
            try:
                use_case = context["_use_case"]
                snapshot = await use_case.execute(
                    plan_id=plan_id,
                    checkpoint_no="CP-1",
                    stage_id=CREATION_STAGE_ID,
                    query="五年战略规划（并发审批）",
                    retrieved_docs=_make_search_results(),
                    user_id="acceptance-executor",
                    summary="CP-1 阶段摘要（并发验收直供）",
                )
                recovery_use_case = context["_recovery_execute_use_case"]
                outcome = await recovery_use_case.execute(
                    plan_id=plan_id,
                    checkpoint_no="CP-1",
                    confirmed_by=f"高管-{plan_id[:8]}",
                )
                return snapshot, outcome
            finally:
                reset_session(token)
            # （try 内 return 已含 commit 前状态——会话提交收口见下）
        except Exception:
            await session.rollback()
            raise
        finally:
            try:
                await session.commit()
            except Exception:
                pass
            await session.close()

    async def _gather_all() -> list[Any]:
        return await asyncio.gather(*[_one_plan(plan_id) for plan_id in context["_concurrent_plan_ids"]])

    for plan_id in context["_concurrent_plan_ids"]:
        context["_snapshot_session_ids"].append(_snapshot_session_id(plan_id, "CP-1"))
        context["_snapshot_session_ids"].append(_recovery_session_id(plan_id))
        context["_archive_plan_ids"].append(plan_id)
        context["_outbox_plan_ids"].append(plan_id)
    context["_concurrent_results"] = _run_async(context["_loop"], _gather_all())


@then("五路全部成功且恢复记录互不干扰")
def five_way_success_no_cross_talk(context: dict[str, Any]) -> None:
    """gather 全成功+5 恢复记录独立读回+plan_id 键值与发起方一致（值级）。"""
    results = context["_concurrent_results"]
    assert len(results) == CONCURRENT_PLAN_COUNT, f"gather 结果数实测={len(results)}"
    for plan_id, (snapshot, outcome) in zip(context["_concurrent_plan_ids"], results, strict=True):
        assert snapshot is not None and outcome is not None
        record = _load_recovery_record(context, plan_id)
        assert record is not None, f"plan={plan_id} 恢复记录读回 None"
        assert record.state_data["plan_id"] == plan_id, (
            f"恢复记录 plan_id 实测={record.state_data['plan_id']} 期望={plan_id}（无交叉污染值级断言）"
        )
        assert record.state_data["confirmed_by"] == f"高管-{plan_id[:8]}", "并发路审批留痕与发起方一致"


@then("outbox 按规划分组各恰一行")
def outbox_grouped_one_row_per_plan(context: dict[str, Any]) -> None:
    """outbox 分组计数断言（非空锚防过滤键空真——6-2 R1-F2 教训继承）。"""
    import sqlalchemy as sa

    async def _group_count() -> list[tuple[str, int]]:
        engine = context["_pg_manager"].get_async_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT payload->'metadata'->>'plan_id' AS plan_id, COUNT(*) "
                        "FROM event_outbox "
                        "WHERE event_type = 'CheckpointRecovered' "
                        "AND created_at >= NOW() - INTERVAL '5 minutes' "
                        "AND payload->'metadata'->>'plan_id' = ANY(:ids) "
                        "GROUP BY payload->'metadata'->>'plan_id'"
                    ),
                    {"ids": list(context["_concurrent_plan_ids"])},
                )
            ).fetchall()
        await engine.dispose()
        return [(str(row[0]), int(row[1])) for row in rows]

    groups = _run_async(context["_loop"], _group_count())
    expected = {plan_id: 1 for plan_id in context["_concurrent_plan_ids"]}
    assert dict(groups) == expected, f"outbox 分组实测={dict(groups)} 期望 5 plan 各恰一行（按 metadata.plan_id 分组）"


# ===================================================================
# AC-6: 性能与成功率
# ===================================================================


@when("采样摘要显示窗口二十轮（show 与 list 双窗口）")
def sample_summary_windows(context: dict[str, Any]) -> None:
    """双窗口采样（show=recover_checkpoint 数据面窗口/list=清单窗口；编程面口径
    ——经 CLI 进程面采样会把建连开销计入窗口冲破 200ms；预热含首次 load）。"""
    service = context["_checkpoint_service"]
    loop = context["_loop"]

    async def _sample() -> tuple[list[float], list[float]]:
        show_durations: list[float] = []
        list_durations: list[float] = []
        # 预热轮（连接池建立——R8-F5 注记继承；不计入采样）
        await service.recover_checkpoint(plan_id=context["_plan_id"], checkpoint_no="CP-1")
        await context["_list_use_case"].execute(plan_id=context["_plan_id"])
        for _ in range(PERF_SAMPLE_ROUNDS):
            start = time.perf_counter()
            await service.recover_checkpoint(plan_id=context["_plan_id"], checkpoint_no="CP-1")
            show_durations.append((time.perf_counter() - start) * 1000.0)
            start = time.perf_counter()
            await context["_list_use_case"].execute(plan_id=context["_plan_id"])
            list_durations.append((time.perf_counter() - start) * 1000.0)
        return show_durations, list_durations

    context["_show_durations"], context["_list_durations"] = _run_async(loop, _sample())


@then("双窗口 P95 均小于 200ms")
def dual_window_p95_under_200ms(context: dict[str, Any]) -> None:
    """P95 双门禁断言（sorted 升序 ceil(0.95*n)-1 位——n=20 取次大值）。"""
    show_p95 = _p95(context["_show_durations"])
    list_p95 = _p95(context["_list_durations"])
    assert show_p95 < SUMMARY_P95_LIMIT_MS, (
        f"show 窗口 P95 实测={show_p95:.2f}ms 期望<{SUMMARY_P95_LIMIT_MS}ms（epics L2330 摘要显示门禁）"
    )
    assert list_p95 < SUMMARY_P95_LIMIT_MS, (
        f"list 窗口 P95 实测={list_p95:.2f}ms 期望<{SUMMARY_P95_LIMIT_MS}ms（多 checkpoint 前置场景同门禁）"
    )


@given("十个独立规划各持一个已创建 Checkpoint")
def ten_independent_plans_with_checkpoint(context: dict[str, Any]) -> None:
    """10 plan 前置（采样矩阵：Override×5 建议模式+Replay×5 显式弱替强允——
    每样本单点 plan 省 2 次创建链）。"""
    context["_sample_plan_ids"] = [_new_plan_id() for _ in range(RECOVERY_SAMPLES_PER_MODE * 2)]
    for plan_id in context["_sample_plan_ids"]:
        _create_checkpoint(context, plan_id=plan_id, checkpoint_no="CP-1")
        _register_recovery_record(context, plan_id)
    _commit_pg_session(context)


@when("双模式各五次恢复执行并逐次采样窗口")
def dual_mode_recovery_sampling(context: dict[str, Any]) -> None:
    """双模式采样（断言载体=Outcome.execution_ms——①~⑤组装点窗口 ⊇ ②~⑤引擎
    声明窗口，含①守卫解析差为保守方向）。"""
    from src.domain.entities.checkpoint import RecoveryMode

    half = RECOVERY_SAMPLES_PER_MODE
    context["_sample_outcomes"] = []
    for index, plan_id in enumerate(context["_sample_plan_ids"]):
        explicit_mode = RecoveryMode.REPLAY if index >= half else None  # 前 5 建议（Override）/后 5 显式 Replay
        outcome = _run_async(
            context["_loop"],
            context["_recovery_execute_use_case"].execute(
                plan_id=plan_id,
                checkpoint_no="CP-1",
                mode=explicit_mode,
                confirmed_by=f"高管-采样-{index}",
            ),
        )
        context["_sample_outcomes"].append((plan_id, outcome))
    _commit_pg_session(context)


@then("逐次执行窗口小于 15s 且十次恢复记录全部读回")
def per_sample_window_and_success_rate(context: dict[str, Any]) -> None:
    """窗口+成功率断言（逐次 <15s 严格蕴含 P95<15s≤P95<60s 双门禁——工程冗余
    断言口径成文；N=10 次恢复记录全读回=成功率 100% 口径）。"""
    modes: list[str] = []
    for plan_id, outcome in context["_sample_outcomes"]:
        assert outcome.execution_ms < RECOVERY_WINDOW_LIMIT_SECONDS * 1000.0, (
            f"plan={plan_id} 执行窗口实测={outcome.execution_ms}ms 期望<{RECOVERY_WINDOW_LIMIT_SECONDS}s"
            "（纯数据面毫秒量级——漂移即红）"
        )
        assert outcome.execution_ms > 0.0, "execution_ms 须为实测正值（perf_counter 窗口）"
        record = _load_recovery_record(context, plan_id)
        assert record is not None, f"plan={plan_id} 恢复记录读回 None（成功率 100% 口径断裂）"
        modes.append(record.state_data["recovery_mode"])
    override_count = modes.count("override")
    replay_count = modes.count("replay")
    assert override_count == RECOVERY_SAMPLES_PER_MODE and replay_count == RECOVERY_SAMPLES_PER_MODE, (
        f"双模式采样实测 override={override_count}/replay={replay_count} 期望各 {RECOVERY_SAMPLES_PER_MODE}"
    )


# ===================================================================
# AC-7: 异常路径全链（六码分立——验收面 480/484）
# ===================================================================


@when("以不存在编号恢复或以损坏校验和快照恢复")
def recover_missing_or_tampered(context: dict[str, Any]) -> None:
    """480/484 双腿构造（不存在键经 probe 落空→_load_or_480；损坏=hset 坏 checksum）。"""
    from src.domain.exceptions import CheckpointIntegrityError, PlanningNotFoundError

    # 腿一：不存在编号（CP-2 未创建）→ 480
    context["_missing_error"] = None
    try:
        _run_async(
            context["_loop"],
            context["_recovery_execute_use_case"].execute(
                plan_id=context["_plan_id"],
                checkpoint_no="CP-2",
                confirmed_by="高管",
            ),
        )
    except PlanningNotFoundError as error:
        context["_missing_error"] = error

    # 腿二：损坏 checksum（篡改 Redis latest JSON 字段内的 checksum 值）→ 484
    import json

    tamper_key = build_key("snapshot", _snapshot_session_id(context["_plan_id"], "CP-1"))

    async def _tamper_checksum() -> None:
        raw = await context["_redis_client"].hget(tamper_key, "latest")
        assert raw is not None, "篡改前提：CP-1 快照 latest 字段在位"
        hash_data = json.loads(raw)
        hash_data["checksum"] = "deadbeef"
        await context["_redis_client"].hset(tamper_key, "latest", json.dumps(hash_data, ensure_ascii=False))

    _run_async(context["_loop"], _tamper_checksum())
    context["_tampered_error"] = None
    try:
        _run_async(
            context["_loop"],
            context["_recovery_execute_use_case"].execute(
                plan_id=context["_plan_id"],
                checkpoint_no="CP-1",
                confirmed_by="高管",
            ),
        )
    except CheckpointIntegrityError as error:
        context["_tampered_error"] = error


@then("不存在编号抛 480 与校验失败抛 484")
def missing_480_and_tampered_484(context: dict[str, Any]) -> None:
    """480/484 断言（六码全景验收面残两条——486 归单测层 AsyncMock 承载）。"""
    missing = context["_missing_error"]
    assert missing is not None, "不存在编号未抛 PlanningNotFoundError（480 恢复入口复用断裂）"
    assert missing.code == "EXCEPTION_480", f"480 腿实测 code={missing.code}"
    tampered = context["_tampered_error"]
    assert tampered is not None, "损坏校验和未抛 CheckpointIntegrityError（484 恢复入口 verify 断裂）"
    assert tampered.code == "EXCEPTION_484", f"484 腿实测 code={tampered.code}"


# ===================================================================
# 收尾: 完成清单存在性断言（Task 7.3 承载）
# ===================================================================


@when("检查 src 与四测试目录交付件")
def check_src_and_test_artifacts() -> None:
    """完成清单检查（src 新增/修改文件+四测试目录文件——Task 7.3 最终确认）。"""
    pass


@then("完成清单逐项存在")
def completion_checklist_all_present() -> None:
    """完成清单断言（S14——6-3 S13 形态先例；Task 7.3 实现收尾断言）。"""
    completion_files = {
        "src 领域纯函数扩展": "src/domain/services/recovery_mode.py",
        "src planning 异常扩展": "src/domain/exceptions/planning_exceptions.py",
        "src 应用端口扩展": "src/application/ports/checkpoint.py",
        "src 编排服务扩展": "src/application/services/checkpoint_service.py",
        "src 恢复审批用例（新建）": "src/application/use_cases/checkpoint_approval.py",
        "src 异常处理器扩展": "src/interfaces/api/exception_handlers.py",
        "src CLI 三子命令扩展": "src/entrypoints/agent_cli.py",
        "src 组合根扩展": "src/composition_root.py",
        "unit 领域服务测试扩展": "tests/unit/domain/services/test_recovery_mode.py",
        "unit planning 异常测试扩展": "tests/unit/domain/exceptions/test_planning_exceptions.py",
        "unit 异常处理器测试扩展": "tests/unit/interfaces/api/test_exception_handlers.py",
        "unit 服务单测扩展": "tests/unit/application/test_checkpoint_service.py",
        "unit 用例单测扩展": "tests/unit/application/use_cases/test_checkpoint_use_case.py",
        "unit CLI 单测扩展": "tests/unit/interfaces/cli/test_agent_cli.py",
        "unit 架构验证（新建）": "tests/unit/architecture/test_checkpoint_recovery.py",
        "integration 恢复链（新建）": "tests/integration/test_integration_checkpoint_recovery.py",
        "contracts 端口契约扩展": "tests/contracts/test_port_contract_checkpoint.py",
        "contracts 事件通道守护（新建）": "tests/contracts/test_event_channel_mapping_checkpoint_recovery.py",
        "acceptance feature（本文件对）": "tests/acceptance/test_acceptance_checkpoint_recovery.feature",
        "acceptance 步骤实现（本文件）": "tests/acceptance/test_acceptance_checkpoint_recovery.py",
        "6-4 让位 architecture 侧": "tests/unit/architecture/test_json_chain_of_thought.py",
        "6-4 让位 acceptance 侧": "tests/acceptance/test_acceptance_json_chain_of_thought.py",
    }
    for label, relative in completion_files.items():
        path = REPO_ROOT / relative
        assert path.is_file(), f"完成清单缺 {label}: {relative}"
