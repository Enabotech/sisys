"""Acceptance tests for Story 6-8 - 高管简化视图（四段聚合查询 + RAG 三色健康状态 + CLI executive-view）.

真实服务验收（零 mock——Redis 快照/CP/恢复记录直写 + PG 报告/审计行真实 save 四通道装配；
验收装配面零 LLM 零 Embedding——纯读侧聚合，与 6-6/6-7 查询面先例同族）。

场景三属性分档表（12 场景全绑定——S 编号为 6-8 自有编号，跨故事引用带故事号前缀）：
    | 场景 | AC | 调用面 | 红阶段形态 |
    |------|----|--------|-----------|
    | S1 四段全落位 | AC-1 | 编程面（服务直调） | 运行期 ImportError（executive_view 模块缺失） |
    | S2 三色规则表 | AC-2 | 编程面 | 同上 |
    | S3 审批分布+留痕 | AC-3 | 编程面 | 同上 |
    | S4 审计时间窗+样本 | AC-4 | 编程面 | 同上 |
    | S5 审计零新增空态 | AC-4 | 编程面 | 同上 |
    | S6 段缺席形态 | AC-1/AC-5 | 编程面 | 同上 |
    | S7 空 plan+畸形 242 | AC-5 | 编程面（用例守卫） | 同上 |
    | S8 CLI 全数据输出 | AC-6 | CLI in-process 直调 | argparse invalid choice exit 2 → 断言步红 |
    | S9 CLI 空态+242 stderr | AC-6 | CLI in-process 直调 | 同上 |
    | S10 性能采样 | AC-7 | 编程面（C 面 fallback） | 运行期 ImportError |
    | S11 并发 20 路 | AC-7 | 编程面（C 面 fallback） | 同上 |
    | S12 完成清单存在性 | 收尾 | 文件系统断言 | Then 文件不存在 AssertionError |

epics 架构测试三项落位对账（epics L2409-2411）：
    - 仪表盘显示测试 → S1/S2（四段聚合+三色即 KPI 面的 MVP 口径对账——10 项财务 KPI 归
      Epic 21 范围注记 OD-1；状态指示器=health 三色 S2 承载）
    - 信息密度测试 → AC-7 前端指标口径差声明（Lighthouse 后端不定义——epics L2415 自注原文）
    - 审批中心测试 → S3（功能等价重分布——6-6 OD-5/6-7 OD-6 先例）

性能三段口径（OD-7——验收 docstring 落档）：
    ① 视图加载 P95<500ms = build_executive_view 服务面窗口（五读串行：Redis 点查×11
       [latest 1 + list_checkpoints 内部 9 + 审批段恢复记录直读 1] + PG 单行查 + audit
       窗口查）；audit search 的 total 全行取回实现形态在 MVP 数据量级（百行级）远小于
       门禁——审计量万行级时触发分组计数端口立项锚 Epic 7/21；
    ② 并发 20 = 单一数据源 plan_id×20 路并发读（gather+服务无状态+两两相等断言；对照
       排除集六键 {generated_at, window_start, window_end, total_events, recent_events,
       last_event_at}——三时间键每次调用新生成 + audit 值级三键受全局窗并发写入抖动；
       「20 个独立 plan」写面变体不采——构造成本与读面并发安全证明目标不成比例）；
    ③ 「信息密度达标（Lighthouse 评分≥90）」与「状态指示器实时更新」为前端指标后端
       不定义（epics L2415 自注原文——Web 面指标归 Epic 21 Story 21.1 届时验收）。

PG 面三分面通道（R2-F3——预置纪律钦定）：
    - A 编程面（S1~S7）：sync 层 set_session 注入 fixture session → 预置 flush 不 commit
      → 服务读同 session 同事务可见 → teardown rollback 整体回收（零 DELETE 通道）；
    - B CLI 面（S8/S9）：clear_session() 清 ContextVar → 预置经 fallback 独立会话 commit 式
      → teardown 定向 DELETE（按 log_id/report_id）+ 行数断言防静默 0 行假绿；
    - C 并发/性能面（S10/S11）：场景内禁 set_session → 每路各自走 fallback 独立会话
      （天然 per-task 隔离）→ 预置 commit 式 + teardown 定向 DELETE 行数断言。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_executive_view.py -v
"""

from __future__ import annotations

import asyncio
import dataclasses
import math
import time
import uuid as uuid_module
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenario, then, when

pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.database,
    pytest.mark.redis,
    pytest.mark.qdrant,  # 装配链依赖（bootstrap/组合根 resolve 链含 Qdrant 适配器——6-7 同款注记）
    pytest.mark.xdist_group("blm-planning-perf"),
]

# ===================================================================
# Paths & Constants（模块级期望常量独立构造——性能采样纪律）
# ===================================================================

ROOT = Path(__file__).resolve().parents[2]

_P95_LIMIT_MS: float = 500.0
_P95_PERCENTILE: float = 0.95
_SAMPLE_ROUNDS: int = 20
_WARMUP_ROUNDS: int = 2
_CONCURRENCY: int = 20
_WINDOW_DAYS: int = 7

# 并发对照排除集六键（R1-F5/R2-F4——OD-7 ②口径；**不可收缩注记（代码审查 R2-F2）**：
# 单锚派生后 window 键与 generated_at 同路恒等（同一 now——service 单锚），但 20 路各路
# 入口 now 互异（µs 分辨率）——同路恒等≠跨路可比，收缩为只排 generated_at 会使两两相等假红）
_EXCLUDED_TOP_KEYS: tuple[str, ...] = ("generated_at",)
_EXCLUDED_AUDIT_KEYS: tuple[str, ...] = (
    "window_start",
    "window_end",
    "total_events",
    "recent_events",
    "last_event_at",
)

# 8 步流程规范序（BLM_TOTAL_STEPS=8 单源对齐——预置工厂与断言共用）
_STEP_SEQUENCE: tuple[str, ...] = (
    "performance_gap",
    "market_insight_trend",
    "market_insight_competition",
    "market_insight_strategy",
    "market_insight_org",
    "market_insight_risk",
    "market_insight_execution",
    "market_insight_synthesis",
)

# 完成清单（S12 断言对象 = File List 的 src/测试项存在性；
# 两 md 台账（deferred-work/sprint-status）与故事文件不入断言面——修改性断言物理不可写，6-7 S12 同款）
_COMPLETION_SRC_FILES: dict[str, str] = {
    "端口契约（六 VO + ExecutiveHealth + ExecutiveViewPort）": "src/application/ports/executive_view.py",
    "视图服务（四段编排+derive_health）": "src/application/services/executive_view_service.py",
    "查询用例（UUID 守卫+透传）": "src/application/use_cases/get_executive_view.py",
    "CLI executive-view 子命令": "src/entrypoints/agent_cli.py",
    "组合根两注册块": "src/composition_root.py",
    "audit search session_factory fallback": "src/infrastructure/security/audit_repository_impl.py",
}
_COMPLETION_TEST_FILES: dict[str, str] = {
    "VO 单测": "tests/unit/application/test_executive_view_vos.py",
    "服务单测（规则表矩阵+容错）": "tests/unit/application/test_executive_view_service.py",
    "用例单测": "tests/unit/application/use_cases/test_executive_view_use_case.py",
    "CLI 单测扩展": "tests/unit/interfaces/cli/test_agent_cli.py",
    "audit search fallback 单测扩展": "tests/unit/infrastructure/security/test_audit_repository.py",
    "架构四验证器": "tests/unit/architecture/test_executive_view.py",
    "集成四场景": "tests/integration/test_integration_executive_view.py",
    "端口契约测试（五断言族）": "tests/contracts/test_port_contract_executive_view.py",
    "验收 feature": "tests/acceptance/test_acceptance_executive_view.feature",
    "验收 BDD 步骤实现": "tests/acceptance/test_acceptance_executive_view.py",
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
    """驱逐 resolver SINGLETON/SCOPED 缓存（CLI 直调双清钦定——6-6 R3-1 证伪单清形态防线）。"""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    resolver.clear_singleton()
    resolver.clear_scoped()


def _clear_session_ctx() -> None:
    """清 ContextVar 会话（无参防御复位 API——R3-N12；B/C 面预置与 CLI 直调前钦定）."""
    from src.infrastructure.storage.postgresql.session_context import clear_session

    clear_session()


@pytest.fixture
def context(event_loop: Any, capsys: pytest.CaptureFixture[str]) -> Any:
    """场景级 context dict（数据面预置登记 + CLI 直调产物位 + teardown 清单）."""
    ctx: dict[str, Any] = {
        "_loop": event_loop,
        "_capsys_ref": capsys,
        "_a_mode": False,
        "_session_token": None,
        "_active_plan": "",
        "_empty_plan": "",
        "_snapshot_keys": [],
        "_audit_log_ids": [],
        "_report_ids": [],
        "audit_baseline_total": None,
        "view": None,
        "views": {},
        "malformed_error": None,
        "durations": [],
        "concurrent_views": [],
        "cli_exit_code": None,
        "cli_stdout": "",
        "cli_stderr": "",
    }
    yield ctx
    _run_async(_teardown_assets(ctx), event_loop)
    if ctx["_session_token"] is not None:
        from src.infrastructure.storage.postgresql.session_context import reset_session

        reset_session(ctx.pop("_session_token"))
    _clear_resolver_caches()


@pytest.fixture
def pg_session(event_loop: Any) -> Any:
    """A 面真实 PG 会话（事务回滚式——R6 outbox_repo 原型形态：begin→yield→rollback）."""
    from sqlalchemy.ext.asyncio import AsyncSession

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
    session = AsyncSession(manager.get_async_engine(), expire_on_commit=False)

    async def _begin() -> None:
        await session.begin()

    event_loop.run_until_complete(_begin())
    yield session

    async def _finalize() -> None:
        await session.rollback()
        await session.close()
        await manager.get_async_engine().dispose()

    event_loop.run_until_complete(_finalize())


def _a_mode_enter(ctx: dict[str, Any], pg_session: Any) -> None:
    """A 面进入（sync 层 set_session 钦定——R2-F5：async 上下文内 set 不外泄到步骤 task）.

    幂等：同场景多步骤重复进入只 set 一次（token 记入 context 供 teardown reset）。
    """
    from src.infrastructure.storage.postgresql.session_context import set_session

    if ctx["_session_token"] is None:
        ctx["_session_token"] = set_session(pg_session)
    ctx["_a_mode"] = True


# ===================================================================
# 服务探测（Background——不可达环境 pytest.skip 动态跳过）
# ===================================================================


def _probe_pg_available() -> None:
    """PostgreSQL 可达性探测（audit_log/strategic_reports 表预检——失败 skip）."""
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
                    await conn.execute("SELECT 1 FROM audit_log LIMIT 1")
                    await conn.execute("SELECT 1 FROM strategic_reports LIMIT 1")
                finally:
                    await conn.close()
                return True
            except Exception:
                return False

        if not probe_loop.run_until_complete(_check()):
            pytest.skip(f"PostgreSQL not available at {env.postgres.host}:{env.postgres.port}")
    finally:
        probe_loop.close()


def _probe_redis_available() -> None:
    """Redis 可达性探测（快照/CP/恢复记录三键族宿主——失败 skip）."""
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


def _probe_qdrant_available() -> None:
    """Qdrant 可达性探测（bootstrap/组合根 resolve 装配链依赖——失败 skip）."""
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


# ===================================================================
# 服务构建与预置工厂（四通道真实服务——零 mock 红线）
# ===================================================================


def _build_view_service() -> Any:
    """构建视图服务（延迟 import——红锚：executive_view_service 模块缺失即 ImportError）.

    四依赖全既有注册名 resolve（OD-11——snapshot_repository/checkpoint_service/
    report_repository/audit_repo；checkpoint_service 具体类注入——6-7 同款先例）。
    """
    from src.application.services.executive_view_service import ExecutiveViewService
    from src.domain.ports.resolver import resolve

    return ExecutiveViewService(
        snapshot_repository=resolve("snapshot_repository"),
        checkpoint_service=resolve("checkpoint_service"),
        report_repository=resolve("report_repository"),
        audit_repository=resolve("audit_repo"),
    )


def _make_latest_state(plan_id: str, *, completed: int, degraded_steps: list[str]) -> dict[str, Any]:
    """构造 latest 快照 state_data 七键（6-1 timeline 条目六键同源——预置工厂）."""
    now = datetime.now(UTC)
    done = list(_STEP_SEQUENCE[:completed])
    timeline: list[dict[str, Any]] = []
    for index, step in enumerate(done):
        started = now - timedelta(minutes=10 * (len(done) - index))
        finished = now - timedelta(minutes=10 * (len(done) - index) - 1)
        timeline.append(
            {
                "step": step,
                "started_at": started.isoformat(),
                "completed_at": finished.isoformat(),
                "status": "completed",
                "summary_excerpt": f"{step} 摘要（exec-view 预置）",
                "degraded": step in degraded_steps,
            }
        )
    return {
        "plan_id": plan_id,
        "phase": "market_insight",
        "current_step": done[-1] if done else "performance_gap",
        "completed_steps": completed,
        "total_steps": len(_STEP_SEQUENCE),
        "degraded_steps": list(degraded_steps),
        "timeline": timeline,
    }


def _make_cp_snapshot(plan_id: str, cp_no: str, *, completed: bool, step: str) -> Any:
    """构造 Checkpoint 快照（直写通道——state_data 十键=6-3 七键契约+list_checkpoints 读取面三键）.

    钦定空 checkpoint_no（实体构造参数默认 ""——484 守卫双条件不触发，R1-F11 通道裁定）。
    """
    from src.application.ports.checkpoint import CHECKPOINT_SESSION_PREFIX
    from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

    return CheckpointSnapshot(
        session_id=f"{CHECKPOINT_SESSION_PREFIX}{plan_id}:{cp_no}",
        stage_id=step,
        state_data={
            "plan_id": plan_id,
            "step": step,
            "summary": f"{cp_no} 摘要（exec-view 预置）",
            "structured_output": {"preset": True},
            "degraded": False,
            "degrade_reason": "",
            "completed_steps": [],
            "stage_id": step,
            "completed": completed,
            "created_via": "use_case",
        },
    )


def _make_recovery_snapshot(
    plan_id: str,
    *,
    mode: str,
    confirmed_by: str,
    pending: tuple[str, ...] = (),
    invalidated: tuple[str, ...] = (),
) -> Any:
    """构造恢复记录快照（12 键直写——与 checkpoint_service.py:693-714 构造键面同源）."""
    from src.application.ports.checkpoint import CHECKPOINT_RECOVERY_SESSION_PREFIX
    from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

    now = datetime.now(UTC)
    return CheckpointSnapshot(
        session_id=f"{CHECKPOINT_RECOVERY_SESSION_PREFIX}{plan_id}",
        stage_id="recovery_record",
        state_data={
            "plan_id": plan_id,
            "checkpoint_no": "CP-1",
            "recovery_mode": mode,
            "corrected": False,
            "correction": {},
            "affected_checkpoints": [],
            "pending_sync_checkpoints": list(pending),
            "invalidated_checkpoints": list(invalidated),
            "confirmed_by": confirmed_by,
            "recovered_at": now.isoformat(),
            "execution_ms": 12.5,
            "created_via": "cli",
        },
        timestamp=now,
    )


def _make_report_entity(plan_id: str, *, degraded_sections: int = 0) -> Any:
    """构造 StrategicReport 实体（八字段+构造守卫——6-5a 冻结面）."""
    from src.domain.entities.strategic_report import ReportType, StrategicReport

    return StrategicReport(
        report_id=uuid_module.uuid4(),
        plan_id=plan_id,
        report_type=ReportType.MARKDOWN,
        file_path=f"/tmp/sisys-reports/{plan_id}.md",
        section_count=11,
        degraded_section_count=degraded_sections,
        generation_ms=1234,
        created_at=datetime.now(UTC),
    )


def _make_audit_rows(*, n_window: int = 6, n_outside: int = 1) -> list[dict[str, Any]]:
    """构造审计行（必填双键 log_id+timestamp——R1-F1；窗内递减微秒偏移去并列——R2-F1）.

    窗内行 timestamp = now − i×100µs（i=1..n_window）：全部 ≤ end_time 在窗内（闭区间）
    + 严格互异 + 新于一切已存在背景行（同组串行 best-effort 占头）；窗外行 now−8 天。
    """
    now = datetime.now(UTC)
    actions = ("exec-view:probe-a", "exec-view:probe-b", "exec-view:probe-c")
    rows: list[dict[str, Any]] = []
    for i in range(1, n_window + 1):
        rows.append(
            {
                "log_id": str(uuid_module.uuid4()),
                "timestamp": (now - timedelta(microseconds=100 * i)).isoformat(),
                "actor": f"exec-view-actor-{i}",
                "action_type": actions[(i - 1) % 3],
                "target_resource": f"exec-view-target-{i}",
            }
        )
    for _ in range(n_outside):
        rows.append(
            {
                "log_id": str(uuid_module.uuid4()),
                "timestamp": (now - timedelta(days=8)).isoformat(),
                "actor": "exec-view-outside",
                "action_type": "exec-view:outside",
                "target_resource": "exec-view-outside-target",
            }
        )
    return rows


async def _save_snapshot(ctx: dict[str, Any], snapshot: Any) -> None:
    """Redis 快照直写（snapshot_repository.save 真实通道+键登记）."""
    from src.domain.ports.resolver import resolve

    await resolve("snapshot_repository").save(snapshot)
    ctx["_snapshot_keys"].append(snapshot.session_id)


async def _save_report(ctx: dict[str, Any], report: Any) -> Any:
    """PG 报告行真实写（A 面 ContextVar flush / B·C 面 fallback commit——三分面自动分派）."""
    from src.domain.ports.resolver import resolve

    if not ctx["_a_mode"]:
        _clear_session_ctx()
    saved = await resolve("report_repository").save(report)
    ctx["_report_ids"].append(str(saved.report_id))
    return saved


async def _save_audit_rows(ctx: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    """PG 审计行真实写（audit_repo.save——必填双键下标取值；通道同三分面分派）."""
    from src.domain.ports.resolver import resolve

    if not ctx["_a_mode"]:
        _clear_session_ctx()
    repo = resolve("audit_repo")
    for row in rows:
        await repo.save(row)
    ctx["_audit_log_ids"].extend(row["log_id"] for row in rows)


async def _teardown_assets(ctx: dict[str, Any]) -> None:
    """teardown 两步链：Redis 三键族定向 DEL → B/C 面 PG 定向 DELETE（行数断言）.

    A 面（_a_mode）PG 行经 pg_session fixture rollback 整体回收（零 DELETE 通道——
    R1-F9）；B/C 面 commit 式预置须定向 DELETE 且行数断言防静默 0 行假绿（R2-F3）。
    Redis 键族：uuid plan_id 天然隔离，delete 不存在键 no-op（6-6 R1-F1 键清理面纪律）。
    """
    try:
        from src.domain.ports.resolver import resolve

        repo = resolve("snapshot_repository")
        for session_id in ctx["_snapshot_keys"]:
            try:
                await repo.delete(session_id)
            except Exception as error:  # teardown 容错（单键失败不阻断后续清理）
                print(f"[teardown:redis] 删除异常（容错）: {session_id}: {error}")
    except Exception as error:  # teardown 容错
        print(f"[teardown:redis] 仓储不可达（容错）: {error}")
    if ctx["_a_mode"]:
        return
    if not (ctx["_audit_log_ids"] or ctx["_report_ids"]):
        return
    try:
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
                if ctx["_audit_log_ids"]:
                    result = await conn.execute(
                        sa.text("DELETE FROM audit_log WHERE log_id = ANY(:ids)"),
                        {"ids": list(ctx["_audit_log_ids"])},
                    )
                    assert result.rowcount == len(ctx["_audit_log_ids"]), (
                        f"audit_log 定向 DELETE 行数 {result.rowcount} != 预置 {len(ctx['_audit_log_ids'])}"
                        "（静默 0 行假绿防线——R2-F3）"
                    )
                if ctx["_report_ids"]:
                    result = await conn.execute(
                        sa.text("DELETE FROM strategic_reports WHERE report_id = ANY(:ids)"),
                        {"ids": list(ctx["_report_ids"])},
                    )
                    assert result.rowcount == len(ctx["_report_ids"]), (
                        f"strategic_reports 定向 DELETE 行数 {result.rowcount} != 预置 {len(ctx['_report_ids'])}"
                    )
        finally:
            await engine.dispose()
    except AssertionError:
        raise
    except Exception as error:  # teardown 容错
        print(f"[teardown:pg] B/C 面定向 DELETE 异常（容错）: {error}")


# ===================================================================
# Scenario 绑定（12 场景全绑定——R6 模板合规）
# ===================================================================


def _field_names(value: Any) -> set[str]:
    """dataclasses 字段名集合（键集 exact set 断言辅助——6-6 R1-F10 激活先例）."""
    from dataclasses import fields

    return {f.name for f in fields(value)}


# ===================================================================
# Background Steps
# ===================================================================


@given("高管视图依赖服务可用")
def executive_view_services_available(context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """Background：PG/Redis/Qdrant 三服务探测（不可达 pytest.skip 动态跳过）."""
    context["_capsys_ref"] = capsys
    _probe_pg_available()
    _probe_redis_available()
    _probe_qdrant_available()


# ===================================================================
# AC-1: 四段聚合数据结构（ExecutiveView 键契约）——S1
# ===================================================================


@scenario(
    "test_acceptance_executive_view.feature",
    "四段全落位与键集值级断言",
)
def test_full_view_four_sections() -> None:
    """S1/AC-1 四段全落位（全数据形态四段聚合——8 键+嵌套键集+值级）."""
    pass


@given("审计窗口基线已查询")
def audit_baseline_queried(context: dict[str, Any], pg_session: Any) -> None:
    """A 面进入 + 全局窗基线 total（差值断言锚——R1-F6：全局窗无 plan 维度）."""
    _a_mode_enter(context, pg_session)

    from src.domain.ports.audit_repository import AuditSearchCriteria
    from src.domain.ports.resolver import resolve

    async def _query() -> Any:
        now = datetime.now(UTC)
        return await resolve("audit_repo").search(
            AuditSearchCriteria(start_time=now - timedelta(days=_WINDOW_DAYS), end_time=now, limit=1)
        )

    context["audit_baseline_total"] = _run_async(_query(), context["_loop"]).total


@given("预置全数据形态的 plan（快照 3/8 与 checkpoint 混合与恢复记录与报告与审计窗内行）")
def preset_full_data_plan(context: dict[str, Any], pg_session: Any) -> None:
    """S1 预置：latest 快照 3/8（1 降级）+ CP-1/2/3 混合（2 completed）+ 恢复记录（空清单）
    + 报告（11 章节 2 降级）+ 审计 6 窗内 + 1 窗外（A 面回滚式通道）。"""
    _a_mode_enter(context, pg_session)
    plan_id = str(uuid_module.uuid4())
    latest = _make_latest_state(plan_id, completed=3, degraded_steps=[_STEP_SEQUENCE[0]])
    recovery = _make_recovery_snapshot(plan_id, mode="replay", confirmed_by="ceo-acceptance-s1")
    report = _make_report_entity(plan_id, degraded_sections=2)

    async def _preset() -> None:
        from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        await _save_snapshot(
            context,
            CheckpointSnapshot(session_id=f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}", state_data=latest),
        )
        await _save_snapshot(context, _make_cp_snapshot(plan_id, "CP-1", completed=True, step=_STEP_SEQUENCE[0]))
        await _save_snapshot(context, _make_cp_snapshot(plan_id, "CP-2", completed=True, step=_STEP_SEQUENCE[1]))
        await _save_snapshot(context, _make_cp_snapshot(plan_id, "CP-3", completed=False, step=_STEP_SEQUENCE[2]))
        await _save_snapshot(context, recovery)
        context["preset_report"] = await _save_report(context, report)
        await _save_audit_rows(context, _make_audit_rows())

    _run_async(_preset(), context["_loop"])
    context["_active_plan"] = plan_id


@when("构建高管简化视图")
def build_executive_view_step(context: dict[str, Any]) -> None:
    """S1/S3/S4/S6：服务直调构建视图（红锚=executive_view_service ImportError）."""
    service = _build_view_service()
    context["view"] = _run_async(service.build_executive_view(plan_id=context["_active_plan"]), context["_loop"])


@then("视图 8 键与四段嵌套键集完整")
def verify_view_and_section_keys(context: dict[str, Any]) -> None:
    """S1：ExecutiveView 8 键 + 四段嵌套键集 exact set（Task 0.1 冻结表逐键对齐）."""
    view = context["view"]
    assert view is not None, "视图构建失败（context 缺 view）"
    assert _field_names(view) == {
        "plan_id",
        "generated_at",
        "health",
        "build_degraded",
        "planning",
        "approval",
        "audit",
        "report",
    }
    assert _field_names(view.planning) == {
        "available",
        "degraded",
        "completed_steps",
        "total_steps",
        "progress_percent",
        "current_step",
        "degraded_step_count",
        "last_activity_at",
    }
    assert _field_names(view.approval) == {
        "available",
        "degraded",
        "total_checkpoints",
        "completed_count",
        "in_sync_count",
        "pending_sync_count",
        "invalidated_count",
        "last_recovery_mode",
        "last_recovery_confirmed_by",
        "last_recovered_at",
    }
    assert _field_names(view.audit) == {
        "degraded",
        "window_days",
        "window_start",
        "window_end",
        "total_events",
        "recent_events",
        "last_event_at",
    }, "审计段无 available 键（OD-4——窗口零事件是合法空态非不可得）"
    assert _field_names(view.report) == {
        "available",
        "degraded",
        "report_id",
        "report_type",
        "file_path",
        "section_count",
        "degraded_section_count",
        "generated_at",
    }
    assert view.build_degraded is False, "全数据在位视图不应段降级"
    assert view.plan_id == context["_active_plan"]


@then("四段计数与预置一致")
def verify_section_counts(context: dict[str, Any]) -> None:
    """S1：四段值级断言（计数/标识/派生键与预置锚一致——值级防默认值假绿）."""
    view = context["view"]
    planning = view.planning
    assert planning.available is True
    assert planning.degraded is False
    assert planning.completed_steps == 3
    assert planning.total_steps == 8
    assert planning.degraded_step_count == 1, "degraded_step_count 应派生自 degraded_steps 清单 len()"
    assert planning.current_step == _STEP_SEQUENCE[2]
    assert planning.last_activity_at is not None
    approval = view.approval
    assert approval.available is True
    assert approval.total_checkpoints == 3
    assert approval.completed_count == 2
    assert approval.in_sync_count == 3, "空清单恢复记录→全量 in_sync 退化语义（checkpoint_service :526/:535）"
    assert approval.pending_sync_count == 0
    assert approval.invalidated_count == 0
    assert approval.last_recovery_mode == "replay"
    assert approval.last_recovery_confirmed_by == "ceo-acceptance-s1", "审批留痕身份值级（可判别非默认空串）"
    assert approval.last_recovered_at is not None
    report = view.report
    assert report.available is True
    assert report.report_id == str(context["preset_report"].report_id), "report_id 应 str() 化（R1-F4）"
    assert report.report_type == "markdown"
    assert report.section_count == 11
    assert report.degraded_section_count == 2
    assert report.generated_at == context["preset_report"].created_at.isoformat(), (
        "generated_at 应派生映射 created_at.isoformat()（R1-F4）"
    )
    audit = view.audit
    assert audit.degraded is False
    assert audit.window_days == _WINDOW_DAYS
    datetime.fromisoformat(audit.window_start)
    datetime.fromisoformat(audit.window_end)
    # 单锚派生恒等式（R1-F2）：window 键与 generated_at 同锚可严格推导（AC-4 时间锚一致性）
    assert audit.window_end == view.generated_at
    generated_anchor = datetime.fromisoformat(view.generated_at)
    assert datetime.fromisoformat(audit.window_start) == generated_anchor - timedelta(days=_WINDOW_DAYS)
    assert audit.last_event_at is not None


@then("total_events 差值等于 6")
def verify_audit_delta_s1(context: dict[str, Any]) -> None:
    """S1：total_events 差值==6（预置 6 窗内行——全局窗背景行不进断言，R1-F6）."""
    delta = context["view"].audit.total_events - context["audit_baseline_total"]
    assert delta == 6, (
        f"预置 6 条窗内行差值应 ==6，实际 {delta}"
        f"（基线 {context['audit_baseline_total']} → {context['view'].audit.total_events}）"
    )


@then("progress_percent 为整数口径 37")
def verify_progress_percent_int(context: dict[str, Any]) -> None:
    """S1：progress_percent 整数口径（int(3/8*100)=37 向下取整——R1-F3 口径分立裁定）."""
    planning = context["view"].planning
    assert isinstance(planning.progress_percent, int)
    assert planning.progress_percent == 37, "int(3/8*100)=37 非 37.5（与实体 float round 口径有意分立）"


# ===================================================================
# AC-2: RAG 三色健康状态推导——S2
# ===================================================================


@scenario(
    "test_acceptance_executive_view.feature",
    "三色规则表三 plan 四断言段",
)
def test_three_color_rule_table() -> None:
    """S2/AC-2 三色规则表（三 plan 三色+空数据第四腿）."""
    pass


@given("预置 P-green 全健康与 P-amber 部分降级与 P-red 全降级三形态 plan")
def preset_three_color_plans(context: dict[str, Any], pg_session: Any) -> None:
    """S2 预置：P-green（8/8+零 checkpoint+报告零降级——R1-F15 钦定最简构造）/
    P-amber（3/8+1 降级）/P-red（3/3 已完成步全降级）三 plan（A 面通道）。"""
    _a_mode_enter(context, pg_session)
    p_green = str(uuid_module.uuid4())
    p_amber = str(uuid_module.uuid4())
    p_red = str(uuid_module.uuid4())

    async def _preset() -> None:
        from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        await _save_snapshot(
            context,
            CheckpointSnapshot(
                session_id=f"{BLM_PLANNING_SESSION_PREFIX}{p_green}",
                state_data=_make_latest_state(p_green, completed=8, degraded_steps=[]),
            ),
        )
        await _save_report(context, _make_report_entity(p_green, degraded_sections=0))
        await _save_snapshot(
            context,
            CheckpointSnapshot(
                session_id=f"{BLM_PLANNING_SESSION_PREFIX}{p_amber}",
                state_data=_make_latest_state(p_amber, completed=3, degraded_steps=[_STEP_SEQUENCE[0]]),
            ),
        )
        await _save_snapshot(
            context,
            CheckpointSnapshot(
                session_id=f"{BLM_PLANNING_SESSION_PREFIX}{p_red}",
                state_data=_make_latest_state(p_red, completed=3, degraded_steps=list(_STEP_SEQUENCE[:3])),
            ),
        )

    _run_async(_preset(), context["_loop"])
    context["_three_plans"] = {"green": p_green, "amber": p_amber, "red": p_red}


@when("分别构建三 plan 简化视图")
def build_three_plan_views(context: dict[str, Any]) -> None:
    """S2：三 plan 分别构建（P-green/P-amber/P-red）."""
    service = _build_view_service()
    for color, plan_id in context["_three_plans"].items():
        context["views"][color] = _run_async(service.build_executive_view(plan_id=plan_id), context["_loop"])


@then("P-green 视图 health 为 green")
def verify_p_green(context: dict[str, Any]) -> None:
    """S2 腿1：P-green→GREEN（8/8+零 checkpoint+报告零降级——green 规则全合取）."""
    assert context["views"]["green"].health.value == "green"


@then("P-amber 视图 health 为 amber")
def verify_p_amber(context: dict[str, Any]) -> None:
    """S2 腿2：P-amber→AMBER（3/8+1 降级——amber 兜底）."""
    assert context["views"]["amber"].health.value == "amber"


@then("P-red 视图 health 为 red")
def verify_p_red(context: dict[str, Any]) -> None:
    """S2 腿3：P-red→RED（degraded_step_count==completed_steps>0——可信度危险）."""
    assert context["views"]["red"].health.value == "red"


@when("构建空数据 plan 的简化视图")
def build_empty_plan_view(context: dict[str, Any]) -> None:
    """S2 第四腿/S7 腿1：空数据 plan 幂等读（_empty_plan 未预设时现场生成——S2 自足）."""
    if not context["_empty_plan"]:
        context["_empty_plan"] = str(uuid_module.uuid4())
    service = _build_view_service()
    context["view"] = _run_async(service.build_executive_view(plan_id=context["_empty_plan"]), context["_loop"])


@then("空数据视图 health 为 amber 且三段不可得")
def verify_empty_plan_amber(context: dict[str, Any]) -> None:
    """S2 第四腿/S7：空数据 plan→AMBER+三段 available False（审计段无 available 键——OD-4）."""
    view = context["view"]
    assert view.health.value == "amber", "空 plan 是「无可判绿红的中间态」非错误态"
    assert view.planning.available is False
    assert view.approval.available is False
    assert view.report.available is False


# ===================================================================
# AC-3: 审批中心段聚合——S3
# ===================================================================


@scenario(
    "test_acceptance_executive_view.feature",
    "审批中心分布与恢复留痕",
)
def test_approval_distribution_and_recovery() -> None:
    """S3/AC-3 审批分布计数+留痕三键."""
    pass


@given("预置 3 个 Checkpoint 混合分布与恢复记录的 plan")
def preset_approval_plan(context: dict[str, Any], pg_session: Any) -> None:
    """S3 预置：CP-1/CP-2 completed + CP-3 非 completed；恢复记录 override 模式
    invalidated=[CP-3]（三态分布 2+0+1——判别力锚）。"""
    _a_mode_enter(context, pg_session)
    plan_id = str(uuid_module.uuid4())
    recovery = _make_recovery_snapshot(
        plan_id,
        mode="override",
        confirmed_by="cfo-approval-s3",
        invalidated=("CP-3",),
    )

    async def _preset() -> None:
        await _save_snapshot(context, _make_cp_snapshot(plan_id, "CP-1", completed=True, step=_STEP_SEQUENCE[0]))
        await _save_snapshot(context, _make_cp_snapshot(plan_id, "CP-2", completed=True, step=_STEP_SEQUENCE[1]))
        await _save_snapshot(context, _make_cp_snapshot(plan_id, "CP-3", completed=False, step=_STEP_SEQUENCE[2]))
        await _save_snapshot(context, recovery)

    _run_async(_preset(), context["_loop"])
    context["_active_plan"] = plan_id
    context["preset_recovery"] = recovery


@then("审批段分布计数与预置一致")
def verify_approval_distribution(context: dict[str, Any]) -> None:
    """S3：混合分布计数（2 completed+1 非 completed；三态 2+0+1——invalidated 清单命中制）."""
    approval = context["view"].approval
    assert approval.total_checkpoints == 3
    assert approval.completed_count == 2
    assert approval.in_sync_count == 2
    assert approval.pending_sync_count == 0
    assert approval.invalidated_count == 1, "恢复记录 invalidated=[CP-3] 清单命中（R1-F2 真实仓储退化语义对照）"


@then("三态分布完备恒等式成立")
def verify_sync_invariant(context: dict[str, Any]) -> None:
    """S3：in_sync + pending_sync + invalidated == total（缺行/重复计数即红）."""
    approval = context["view"].approval
    total = approval.in_sync_count + approval.pending_sync_count + approval.invalidated_count
    assert total == approval.total_checkpoints, f"三态分布和 {total} != 总数 {approval.total_checkpoints}"


@then("恢复留痕三键值级正确")
def verify_recovery_trace(context: dict[str, Any]) -> None:
    """S3：留痕三键与预置恢复记录 12 键直读值级相等（小写 mode/审批身份/ISO 时间）."""
    approval = context["view"].approval
    recovery = context["preset_recovery"]
    assert approval.last_recovery_mode == recovery.state_data["recovery_mode"] == "override"
    assert approval.last_recovery_confirmed_by == recovery.state_data["confirmed_by"] == "cfo-approval-s3"
    assert approval.last_recovered_at == recovery.state_data["recovered_at"]


# ===================================================================
# AC-4: 审计摘要段聚合——S4/S5
# ===================================================================


@scenario(
    "test_acceptance_executive_view.feature",
    "审计时间窗与最近样本",
)
def test_audit_window_and_recent_samples() -> None:
    """S4/AC-4 审计时间窗差值+最近样本降序."""
    pass


@scenario(
    "test_acceptance_executive_view.feature",
    "审计零新增空态",
)
def test_audit_zero_delta() -> None:
    """S5/AC-4 审计零新增差值==0 空态."""
    pass


@given("预置 6 条窗内递减微秒审计行与 1 条窗外行")
def preset_audit_rows(context: dict[str, Any], pg_session: Any) -> None:
    """S4 预置：6 窗内（3 种 action_type 各 2 条，timestamp=now−i×100µs 递减去并列）
    + 1 窗外（now−8 天）——差值==6 与降序断言的数据锚。"""
    _a_mode_enter(context, pg_session)
    plan_id = str(uuid_module.uuid4())

    async def _preset() -> None:
        await _save_audit_rows(context, _make_audit_rows(n_window=6, n_outside=1))

    _run_async(_preset(), context["_loop"])
    context["_active_plan"] = plan_id


@given("预置零审计新增的独立 plan")
def preset_zero_audit_plan(context: dict[str, Any], pg_session: Any) -> None:
    """S5 预置：独立 plan_id 零审计预置（合法空态——差值==0 判别）。"""
    _a_mode_enter(context, pg_session)
    context["_active_plan"] = str(uuid_module.uuid4())


@when("构建该 plan 简化视图")
def build_zero_audit_plan_view(context: dict[str, Any]) -> None:
    """S5：独立 plan（零审计新增）视图构建."""
    service = _build_view_service()
    context["view"] = _run_async(service.build_executive_view(plan_id=context["_active_plan"]), context["_loop"])


@then("total_events 差值等于 6 且窗外行不进差值")
def verify_audit_delta_s4(context: dict[str, Any]) -> None:
    """S4：差值==6（窗外行 now−8d 不进差值——内外行数可判别）."""
    delta = context["view"].audit.total_events - context["audit_baseline_total"]
    assert delta == 6, f"预置 6 窗内行差值应 ==6（窗外 1 行不进），实际 {delta}"


@then("recent_events 恰 5 条 4 键且降序")
def verify_recent_events(context: dict[str, Any]) -> None:
    """S4：recent_events 5 条上限+4 键 exact set+降序+值级（断言序列=预置 i=1..5 行——R2-F7）."""
    audit = context["view"].audit
    events = audit.recent_events
    assert isinstance(events, tuple), "recent_events 恒元组（frozen 纪律）"
    assert len(events) == 5, "6 条预置取 5（丢弃最旧 i=6 行）"
    for event in events:
        assert _field_names(event) == {"action_type", "actor", "target_resource", "timestamp"}, (
            "投影白名单四键（审计行 15 键禁入高管视图——安全面）"
        )
    timestamps = [event.timestamp for event in events]
    assert timestamps == sorted(timestamps, reverse=True), "recent_events 按 timestamp 降序"
    assert events[0].actor == "exec-view-actor-1", "预置 i=1 行（最新微秒偏移）占降序头部"
    assert events[4].actor == "exec-view-actor-5", "断言序列为预置 i=1..5 行（i=6 被丢弃）"


@then("last_event_at 与最近事件一致")
def verify_last_event_at(context: dict[str, Any]) -> None:
    """S4：last_event_at == recent_events[0].timestamp（同源一致性——占头前提下恒可写）."""
    audit = context["view"].audit
    assert audit.last_event_at == audit.recent_events[0].timestamp


@then("审计段差值为 0 且不降级且键恒在")
def verify_zero_delta(context: dict[str, Any]) -> None:
    """S5：零新增空态（差值==0+不降级+7 键恒在——绝对空断言不可写改差值语义，R1-F6）."""
    view = context["view"]
    delta = view.audit.total_events - context["audit_baseline_total"]
    assert delta == 0, f"零新增 plan 差值应 ==0，实际 {delta}"
    assert view.audit.degraded is False
    assert _field_names(view.audit) == {
        "degraded",
        "window_days",
        "window_start",
        "window_end",
        "total_events",
        "recent_events",
        "last_event_at",
    }


# ===================================================================
# AC-5: 段级容错与空 plan 幂等读——S6/S7
# ===================================================================


@scenario(
    "test_acceptance_executive_view.feature",
    "段缺席形态部分可得",
)
def test_partial_availability() -> None:
    """S6/AC-1·AC-5 段缺席形态（部分数据与零数据分立锚）."""
    pass


@scenario(
    "test_acceptance_executive_view.feature",
    "空 plan 幂等读与畸形 plan_id 242",
)
def test_empty_plan_and_malformed_242() -> None:
    """S7/AC-5 空 plan 幂等读三断言+畸形 242."""
    pass


@given("预置仅有快照无报告无恢复记录的 plan")
def preset_snapshot_only_plan(context: dict[str, Any], pg_session: Any) -> None:
    """S6 预置：latest 快照 5/8 零降级 + CP-1 一个（无恢复记录——None→全量 in_sync 退化语义）
    无报告（部分可得形态）。"""
    _a_mode_enter(context, pg_session)
    plan_id = str(uuid_module.uuid4())

    async def _preset() -> None:
        from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        await _save_snapshot(
            context,
            CheckpointSnapshot(
                session_id=f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}",
                state_data=_make_latest_state(plan_id, completed=5, degraded_steps=[]),
            ),
        )
        await _save_snapshot(context, _make_cp_snapshot(plan_id, "CP-1", completed=True, step=_STEP_SEQUENCE[0]))

    _run_async(_preset(), context["_loop"])
    context["_active_plan"] = plan_id


@given("预置零数据的空 plan")
def preset_empty_plan(context: dict[str, Any], pg_session: Any) -> None:
    """S7 预置：空 plan_id（零快照/零 checkpoint/零报告/本场景零审计预置行）。"""
    _a_mode_enter(context, pg_session)
    context["_active_plan"] = str(uuid_module.uuid4())
    context["_empty_plan"] = context["_active_plan"]


@then("报告段不可得且计数降级")
def verify_report_absent(context: dict[str, Any]) -> None:
    """S6：report.available==False+标识降 None+计数降 0（键恒在纪律）."""
    report = context["view"].report
    assert report.available is False
    assert report.degraded is False, "无报告是合法空态非段降级"
    assert report.report_id is None
    assert report.file_path is None
    assert report.section_count == 0
    assert report.degraded_section_count == 0
    assert report.generated_at is None


@then("恢复留痕三键为 None")
def verify_no_recovery_trace(context: dict[str, Any]) -> None:
    """S6：无恢复记录→留痕三键恒在值 None（对照腿）."""
    approval = context["view"].approval
    assert approval.last_recovery_mode is None
    assert approval.last_recovery_confirmed_by is None
    assert approval.last_recovered_at is None


@then("规划态势段正常聚合")
def verify_planning_normal(context: dict[str, Any]) -> None:
    """S6：planning.available==True 正常聚合（部分可得与零数据分立锚）."""
    planning = context["view"].planning
    assert planning.available is True
    assert planning.completed_steps == 5
    assert planning.degraded_step_count == 0
    assert planning.progress_percent == 62, "int(5/8*100)=62"


@then("视图 8 键恒在且 build_degraded 为 False")
def verify_empty_plan_idempotent(context: dict[str, Any]) -> None:
    """S7 腿1：空 plan 幂等读三断言之首（8 键+build_degraded False+审计腿差值==0）."""
    view = context["view"]
    assert _field_names(view) == {
        "plan_id",
        "generated_at",
        "health",
        "build_degraded",
        "planning",
        "approval",
        "audit",
        "report",
    }
    assert view.build_degraded is False, "「没有数据」非「拿不到数据」（6-7 空树分立语义延续）"
    delta = view.audit.total_events - context["audit_baseline_total"]
    assert delta == 0, f"空 plan 零新增差值应 ==0，实际 {delta}"


@when("以畸形 plan_id 请求简化视图")
def request_with_malformed_plan_id(context: dict[str, Any]) -> None:
    """S7 腿2：畸形 plan_id（编程面用例守卫——242 单源；import 在 try 外保证红阶段可达）."""
    from src.application.use_cases.get_executive_view import GetExecutiveViewUseCase

    use_case = GetExecutiveViewUseCase(view_service=_build_view_service())
    try:
        _run_async(use_case.execute(plan_id="not-a-uuid"), context["_loop"])
        context["malformed_error"] = None
    except Exception as error:  # 异常记录供断言步（242 守卫形态验证——绿阶段为 EntityValidationError）
        context["malformed_error"] = error


@then("抛出 EntityValidationError 且 code 为 242")
def verify_malformed_242(context: dict[str, Any]) -> None:
    """S7 腿2：畸形 plan_id → EntityValidationError(242)（code 值级断言——编程面）."""
    from src.domain.exceptions import EntityValidationError

    error = context["malformed_error"]
    assert error is not None, "畸形 plan_id 应抛 EntityValidationError"
    assert isinstance(error, EntityValidationError)
    assert error.code == "EXCEPTION_242"


# ===================================================================
# AC-6: CLI executive-view 命令——S8/S9
# ===================================================================


@scenario(
    "test_acceptance_executive_view.feature",
    "CLI 全数据输出",
)
def test_cli_full_output() -> None:
    """S8/AC-6 CLI 全数据 GREEN 输出."""
    pass


@scenario(
    "test_acceptance_executive_view.feature",
    "CLI 空态与畸形 plan_id stderr",
)
def test_cli_empty_and_stderr() -> None:
    """S9/AC-6 CLI 空态 exit 0+畸形 exit 1 stderr."""
    pass


@given("CLI 面已预置全健康数据形态的 plan")
def preset_cli_full_plan(context: dict[str, Any]) -> None:
    """S8 预置（B 面通道）：8/8 快照+2 CP completed+恢复记录空清单（→全 in_sync）+
    报告零降级——期望 health==GREEN（R1-F15 钦定构造路径）."""
    plan_id = str(uuid_module.uuid4())
    latest = _make_latest_state(plan_id, completed=8, degraded_steps=[])
    recovery = _make_recovery_snapshot(plan_id, mode="replay", confirmed_by="ceo-cli-s8")

    async def _preset() -> None:
        from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        await _save_snapshot(
            context,
            CheckpointSnapshot(session_id=f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}", state_data=latest),
        )
        await _save_snapshot(context, _make_cp_snapshot(plan_id, "CP-1", completed=True, step=_STEP_SEQUENCE[0]))
        await _save_snapshot(context, _make_cp_snapshot(plan_id, "CP-2", completed=True, step=_STEP_SEQUENCE[1]))
        await _save_snapshot(context, recovery)
        context["preset_report"] = await _save_report(context, _make_report_entity(plan_id, degraded_sections=0))

    _run_async(_preset(), context["_loop"])
    context["_active_plan"] = plan_id


@given("CLI 面已预置空 plan")
def preset_cli_empty_plan(context: dict[str, Any]) -> None:
    """S9 预置（B 面通道）：空 plan_id（零数据空态）。"""
    context["_active_plan"] = str(uuid_module.uuid4())
    context["_empty_plan"] = context["_active_plan"]


def _run_cli_executive_view(context: dict[str, Any], *, plan_id: str | None = None) -> None:
    """CLI in-process 直调（双清钦定 + clear_session 清 ContextVar——R3-N12/R2-F3）.

    clear_session 是 CLI 面硬前置：asyncio.run 新循环继承当前上下文的 fixture session 会
    触发「Future attached to a different loop」——必清使服务各仓储走 fallback 独立会话。
    """
    from src.entrypoints import agent_cli

    _clear_session_ctx()
    _clear_resolver_caches()
    argv = ["executive-view", "--plan-id", plan_id or context["_active_plan"]]
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


@when("CLI 直调 executive-view 全数据")
def cli_executive_view_full(context: dict[str, Any]) -> None:
    """S8：CLI 全数据输出（期望 GREEN——R1-F15 钦定构造）."""
    _run_cli_executive_view(context)


@when("CLI 直调 executive-view 空态")
def cli_executive_view_empty(context: dict[str, Any]) -> None:
    """S9 腿1：CLI 空态输出（exit 0——空态是正常态非错误）."""
    _run_cli_executive_view(context, plan_id=context["_empty_plan"])


@when("CLI 直调 executive-view 传入畸形 plan_id")
def cli_executive_view_malformed(context: dict[str, Any]) -> None:
    """S9 腿2：畸形 plan_id → [EXCEPTION_242] stderr + exit 1."""
    _run_cli_executive_view(context, plan_id="not-a-uuid")


@then("健康行精确匹配 green 且四段分隔行齐备")
def verify_cli_health_line(context: dict[str, Any]) -> None:
    """S8：健康行精确匹配（GREEN——R1-F15 钦定构造）+ 四段分隔行."""
    lines = context["cli_stdout"].splitlines()
    assert "高管简化视图（plan: %s）" % context["_active_plan"] in lines, "首行应精确匹配"
    assert "健康状态: green（健康）" in lines, "健康行精确匹配（无降级标记——build_degraded False）"
    for separator in ("── 规划态势 ──", "── 审批中心 ──", "── 审计摘要 ──", "── 报告 ──"):
        assert separator in lines, f"四段分隔行缺失: {separator}"


@then("四段值级行输出正确")
def verify_cli_value_lines(context: dict[str, Any]) -> None:
    """S8：四段值级行（进度 100%/Checkpoint 分布/恢复行/报告行/审计行 in 判定）."""
    stdout = context["cli_stdout"]
    assert "进度: 8/8（100%）" in stdout
    assert "降级: 0 步" in stdout
    assert "Checkpoint: 共 2 | 已完成 2 | in_sync 2 | pending_sync 0 | invalidated 0" in stdout
    assert "最近恢复: replay by ceo-cli-s8 at " in stdout
    assert "章节 11（降级 0）" in stdout
    assert "近 7 天事件:" in stdout, "审计行 total 为全局窗动态值——in 判定（R1-F6）"


@then("exit code 为 0")
def verify_cli_exit_zero(context: dict[str, Any]) -> None:
    """S8：正常退出 0."""
    assert context["cli_exit_code"] == 0, f"exit code 应 0，实际 {context['cli_exit_code']}"


@then("四段空态行齐备且 exit code 为 0")
def verify_cli_empty_output(context: dict[str, Any]) -> None:
    """S9 腿1：空态输出（首行+amber 健康行+四段空态行）+ exit 0（空态是正常态）."""
    stdout = context["cli_stdout"]
    lines = stdout.splitlines()
    assert "健康状态: amber（关注）" in lines
    assert "进度: 0/8（0%）" in stdout
    assert "最近活动: 无" in stdout
    assert "Checkpoint: 共 0 | 已完成 0 | in_sync 0 | pending_sync 0 | invalidated 0" in stdout
    assert "最近恢复: 无" in stdout
    assert "近 7 天事件:" in stdout, "审计行动态值 in 判定（共享库背景行恒在——R1-F6/F16）"
    assert "最新报告: 无（可先执行 report-generate）" in stdout
    assert context["cli_exit_code"] == 0


@then("stderr 含 EXCEPTION_242 且 exit code 为 1")
def verify_cli_stderr_242(context: dict[str, Any]) -> None:
    """S9 腿2：畸形 plan_id → [EXCEPTION_242] stderr + exit 1（6-3 R1-F18 前缀统一先例）."""
    assert "[EXCEPTION_242]" in context["cli_stderr"]
    assert context["cli_exit_code"] == 1


# ===================================================================
# AC-7: 性能与并发——S10/S11
# ===================================================================


@scenario(
    "test_acceptance_executive_view.feature",
    "性能采样 20 轮 P95",
)
def test_performance_sampling() -> None:
    """S10/AC-7 性能采样 20 轮 P95<500ms."""
    pass


@scenario(
    "test_acceptance_executive_view.feature",
    "并发 20 路两两相等",
)
def test_concurrent_20_reads() -> None:
    """S11/AC-7 并发 20 路全成功+排除集对照两两相等."""
    pass


@given("并发面已预置全数据形态的 plan 且服务已预热")
def preset_perf_fixture(context: dict[str, Any]) -> None:
    """S10 预置（C 面通道——禁 set_session，每路 fallback 独立会话）：S1 同构全数据形态
    + 预热 _WARMUP_ROUNDS 轮（含首次 load 连接池建立——R8-F5 注记继承）。"""
    _preset_concurrent_full_plan(context)
    service = _build_view_service()
    for _ in range(_WARMUP_ROUNDS):
        _run_async(service.build_executive_view(plan_id=context["_active_plan"]), context["_loop"])


@given("并发面已预置全数据形态的 plan")
def preset_concurrent_plan(context: dict[str, Any]) -> None:
    """S11 预置（C 面通道）：S1 同构全数据形态（20 路共读单一数据源）。"""
    _preset_concurrent_full_plan(context)


def _preset_concurrent_full_plan(context: dict[str, Any]) -> None:
    """C 面全数据形态预置（clear_session → fallback commit 式——R2-F3）."""
    plan_id = str(uuid_module.uuid4())

    async def _preset() -> None:
        from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        _clear_session_ctx()
        await _save_snapshot(
            context,
            CheckpointSnapshot(
                session_id=f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}",
                state_data=_make_latest_state(plan_id, completed=3, degraded_steps=[_STEP_SEQUENCE[0]]),
            ),
        )
        await _save_snapshot(context, _make_cp_snapshot(plan_id, "CP-1", completed=True, step=_STEP_SEQUENCE[0]))
        await _save_snapshot(context, _make_cp_snapshot(plan_id, "CP-2", completed=True, step=_STEP_SEQUENCE[1]))
        await _save_snapshot(context, _make_recovery_snapshot(plan_id, mode="replay", confirmed_by="cfo-perf"))
        await _save_report(context, _make_report_entity(plan_id, degraded_sections=2))
        await _save_audit_rows(context, _make_audit_rows())

    _run_async(_preset(), context["_loop"])
    context["_active_plan"] = plan_id


@when("采样 20 轮视图构建计时")
def sample_view_build_timing(context: dict[str, Any]) -> None:
    """S10：20 轮采样（perf_counter 毫秒窗口；预热已在预置步完成）."""
    service = _build_view_service()
    durations: list[float] = []
    for _ in range(_SAMPLE_ROUNDS):
        start = time.perf_counter()
        context["view"] = _run_async(service.build_executive_view(plan_id=context["_active_plan"]), context["_loop"])
        durations.append((time.perf_counter() - start) * 1000.0)
    context["durations"] = durations


@when("20 路并发构建简化视图")
def concurrent_20_builds(context: dict[str, Any]) -> None:
    """S11：asyncio.gather 20 路（C 面禁 set_session——每路 fallback 独立会话天然隔离）."""
    service = _build_view_service()

    async def _gather() -> Any:
        return await asyncio.gather(
            *[service.build_executive_view(plan_id=context["_active_plan"]) for _ in range(_CONCURRENCY)]
        )

    context["concurrent_views"] = list(_run_async(_gather(), context["_loop"]))


@then("P95 小于 500ms")
def verify_p95(context: dict[str, Any]) -> None:
    """S10：P95 = sorted(durations)[ceil(0.95*n)-1] < 500ms（数学口径——6-3/6-6/6-7 同款公式）."""
    durations = context["durations"]
    assert len(durations) == _SAMPLE_ROUNDS
    p95 = sorted(durations)[math.ceil(_P95_PERCENTILE * len(durations)) - 1]
    assert p95 < _P95_LIMIT_MS, f"P95 {p95:.1f}ms 超门禁 {_P95_LIMIT_MS}ms（全量: {sorted(durations)}）"


@then("全部成功且剔除六键后两两相等")
def verify_concurrent_equivalence(context: dict[str, Any]) -> None:
    """S11：20 路全成功+排除集六键剔除后 tuple 序列化两两相等（服务无状态+读不互损）."""

    def _freeze(value: Any) -> Any:
        if isinstance(value, dict):
            return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
        if isinstance(value, (list, tuple)):
            return tuple(_freeze(item) for item in value)
        return value

    def _serialize(view: Any) -> Any:
        data = dataclasses.asdict(view)
        for key in _EXCLUDED_TOP_KEYS:
            data.pop(key, None)
        for key in _EXCLUDED_AUDIT_KEYS:
            data["audit"].pop(key, None)
        return _freeze(data)

    views = context["concurrent_views"]
    assert len(views) == _CONCURRENCY
    assert all(view is not None for view in views), "20 路应全部成功不抛"
    serialized = {_serialize(view) for view in views}
    assert len(serialized) == 1, f"剔除六键后应两两相等，实际 {len(serialized)} 种形态（服务无状态约束违反？）"


# ===================================================================
# 收尾: src 与四测试目录完成清单——S12
# ===================================================================


@scenario(
    "test_acceptance_executive_view.feature",
    "src 与四测试目录完成清单",
)
def test_completion_checklist() -> None:
    """S12/收尾 src 与四测试目录完成清单存在性断言."""
    pass


@then("src 新增与修改文件存在")
def verify_completion_src_files() -> None:
    """S12：src 六项存在性（File List 为准——6-7 S12 形态）."""
    for label, relative in _COMPLETION_SRC_FILES.items():
        path = ROOT / relative
        assert path.is_file(), f"完成清单缺 {label}: {relative}"


@then("四测试目录新增与修改文件存在")
def verify_completion_test_files() -> None:
    """S12：四测试目录十项存在性."""
    for label, relative in _COMPLETION_TEST_FILES.items():
        path = ROOT / relative
        assert path.is_file(), f"完成清单缺 {label}: {relative}"
