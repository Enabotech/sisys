"""Acceptance tests for Story 6-10 - 顾问视图（三段聚合查询——多项目概况/品牌配置状态/白标导出概况 + CLI consultant-view）.

真实服务验收（零 mock——PG 归档行+PG 报告行双通道直写装配；验收装配面零 LLM
零 Embedding——纯读侧聚合，与 6-6/6-7/6-8/6-9 查询面先例同族；段级容错归单测
——验收面无故障注入通道，6-8/6-9 分立裁定第三连）。

场景三属性分档表（12 场景全绑定——S 编号为本 Story 自有 docstring 编号，不入 Gherkin）：
    | 场景 | AC | 调用面 | 红阶段形态 |
    |------|----|--------|-----------|
    | S1 三段全落位 | AC-1 | 编程面（服务直调） | 运行期 ImportError（consultant_view 模块缺失） |
    | S2 三 plan 交付形态 | AC-2 | 编程面 | 同上 |
    | S3 品牌段恒默认态 | AC-3 | 编程面 | 同上 |
    | S4 导出段派生 | AC-4 | 编程面 | 同上 |
    | S5 空态幂等读 | AC-5 | 编程面 | 同上 |
    | S6 单源契约绊线 | AC-5 | 编程面 | 同上 |
    | S7 CLI 全数据输出 | AC-6 | CLI in-process 直调 | argparse invalid choice exit 2 → 断言步红 |
    | S8 CLI 输出格式 | AC-6 | CLI in-process 直调 | 同上 |
    | S9 性能采样 | AC-7 | 编程面（C 面通道） | 运行期 ImportError |
    | S10 并发 20 路 | AC-7 | 编程面（C 面通道） | 同上 |
    | S11 租户隔离正向可见性 | AC-7 | 编程面（A 面通道） | 运行期 ImportError |
    | S12 完成清单存在性 | 收尾 | 文件系统断言 | Then 文件不存在 AssertionError |

性能三段口径差声明（OD-8——验收 docstring 落档）：
    ① 视图加载 P95<800ms = build_consultant_view 服务面窗口（两读源：archive find
       1 次 PG 查询[1000 行内聚合在应用层]+plan_count 次 get_latest_by_plan 点查
       [plan_id 索引命中——017 migration ix_strategic_reports_plan_id]）；
       N+1 风险注记：plan 数百级时点查链成热点，「DISTINCT+JOIN LATERAL 单查询化」
       立项锚 Epic 7/21；find 截断风险注记：归档行超 1000 截断——SQL 化清单端口同锚；
    ② 并发 20 = 零输入全局读 20 路并发（gather+服务无状态+预置子集过滤后逐路相等
       ——全集相等禁用：全局无窗查询并发窗内受其他 worker 写入抖动[6-8 R2-F2
       「排除集不可收缩」教训同源]；membership 过滤 projects+brand 段恒稳对照；
       禁 set_session——每路独立会话天然 per-task 隔离，6-8 R2-F3 C 面纪律直系）；
    ③ 「白标报告导出时间<1 分钟」=report-generate 既有入口的生成性能面（6-5b 性能
       验收已承载——本 Story 导出段是导出状态展示面非导出执行面，同 6-9「溯源
       跳转<300ms 归 6-7 既有面」裁定形态第三连）；「多租户隔离测试 100% 通过」=
       继承口径（1-11 合规面测试承载——S11 正向可见性口径：共享测试库单 schema 下
       「零跨漏」排他断言不可判别，隔离语义本体归 1-11；「Schema per Tenant 完整
       实现」归租户管理后续 Story——OD-1 注记）。

共享库全局面断言体系（OD-13——本 Story 特有结构性纪律）：
    验收 PG 是共享库共享 schema——find(plan_id=None) 全局无窗查询见全库背景行
    （Epic 6 视图族首个跨 plan 全局查询——6-8/6-9 单 plan 锚定先例结构性失效）。
    断言体系四件套：① 预置时间戳未来偏移（基准 now 起微秒级递减——预置行恒新于
    背景行→行序「占首三」/latest_pdf 三键绝对可判别；无时间窗过滤无 6-8 审计窗
    「未来偏移出窗」风险——场景分立注记）；② membership 全含断言（预置 plan 集
    ⊆ 清单+各恰一行+行级值直推——外来 plan 免疫+判别更强，差值法废止[R2-F1 窗口
    竞态]；窗口稳定结构前提：全仓提交型归档写入方全挂 blm-planning-perf 组同
    worker 串行——本模块同组惯例延续）；③ CLI 包含断言+格式断言（不断言完整
    输出集/总行数——背景行计入输出）；④ 绝对空态断言归单测（共享库背景行在，
    「零行全库」物理不可构造——验收承载核心四断言[5 键+brand 完整+build_degraded
    False+不抛]）。

归档行预置通道（R5 改钦——repo.save 直写）：StrategicArchive 实体直构造
（archived_at 未来偏移可编程）+ archive_repository.save(entity)——经 L2RdbPort
基类继承方法（save :36+PG :191 UPSERT+_to_model :108-127 archived_at 直传）；
与报告行 report_repository.save 通道完全对称（同 Story 两资产通道对称）；禁复刻
6-7 _archive_row 编排通道（archived_at 服务内部生成不可控——R3-F1 结构性冲突）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_consultant_view.py -v
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
    pytest.mark.xdist_group("blm-planning-perf"),  # 全仓提交型归档写入方同组串行——OD-13② 窗口稳定结构前提
]

# ===================================================================
# Paths & Constants（模块级期望常量独立构造——性能采样纪律）
# ===================================================================

ROOT = Path(__file__).resolve().parents[2]

_P95_LIMIT_MS: float = 800.0
_P95_PERCENTILE: float = 0.95
_SAMPLE_ROUNDS: int = 20
_WARMUP_ROUNDS: int = 2
_CONCURRENCY: int = 20

# 性能场景背景量级 skip 门（OD-13：全库 distinct plan 数 N 含背景 plan——
# N 次点查链成本随 N 增长，>50 视为环境量级超敏，pytest.skip 动态跳过）
_BACKGROUND_PLAN_LIMIT: int = 50

# 并发对照排除单键（generated_at 每路互异——服务入口单时间锚；projects 段按预置
# 子集 membership 过滤后对照；export 段全库派生窗内可变不入对照——OD-8②）
_EXCLUDED_TOP_KEYS: tuple[str, ...] = ("generated_at", "export")

# S12 完成清单（收尾场景存在性断言——src 面 3 新建+2 扩展）
_COMPLETION_SRC_FILES: dict[str, str] = {
    "端口契约（五 VO+三常量+Port）": "src/application/ports/consultant_view.py",
    "三段编排服务": "src/application/services/consultant_view_service.py",
    "用例（零参透传）": "src/application/use_cases/get_consultant_view.py",
    "CLI 子命令（扩展）": "src/entrypoints/agent_cli.py",
    "组合根双注册（扩展）": "src/composition_root.py",
}

# S12 完成清单（收尾场景存在性断言——四测试目录 8 新建+1 扩展）
_COMPLETION_TEST_FILES: dict[str, str] = {
    "VO 单测": "tests/unit/application/test_consultant_view_vos.py",
    "服务单测（排序派生+容错矩阵）": "tests/unit/application/test_consultant_view_service.py",
    "用例单测": "tests/unit/application/use_cases/test_consultant_view_use_case.py",
    "CLI 单测扩展": "tests/unit/interfaces/cli/test_agent_cli.py",
    "架构四验证器": "tests/unit/architecture/test_consultant_view.py",
    "集成四场景": "tests/integration/test_integration_consultant_view.py",
    "端口契约测试（五断言族）": "tests/contracts/test_port_contract_consultant_view.py",
    "验收 feature": "tests/acceptance/test_acceptance_consultant_view.feature",
    "验收 BDD 步骤实现": "tests/acceptance/test_acceptance_consultant_view.py",
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
    """清 ContextVar 会话（无参防御复位 API——B/C 面预置与 CLI 直调前钦定）。"""
    from src.infrastructure.storage.postgresql.session_context import clear_session

    clear_session()


@pytest.fixture
def context(event_loop: Any, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> Any:
    """场景级 context dict（数据面预置登记 + CLI 直调产物位 + teardown 清单）."""
    ctx: dict[str, Any] = {
        "_loop": event_loop,
        "_capsys_ref": capsys,
        "_a_mode": False,
        "_session_token": None,
        # 预置资产登记（teardown 定向 DELETE 面——B/C 面；A 面经 pg_session rollback 回收）
        "_plan_ids": [],
        "_archive_ids": [],
        "_report_ids": [],
        # 预置形态登记（断言直推数据——OD-13② 行级值直推）
        "preset": {},
        # 产物位
        "view": None,
        "concurrent_views": [],
        "durations": [],
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
    """A 面进入（set_session 注入 fixture session——6-8 R2-F5 直系）.

    幂等：同场景多步骤重复进入只 set 一次（token 记入 context 供 teardown reset）。
    """
    from src.infrastructure.storage.postgresql.session_context import set_session

    if ctx["_session_token"] is None:
        ctx["_session_token"] = set_session(pg_session)
    ctx["_a_mode"] = True


# ===================================================================
# 预检跳过（pytest.skip 动态跳过——禁 @pytest.mark.skip 写死）
# ===================================================================


def _probe_pg_available() -> None:
    """PostgreSQL 可达性探测（strategic_archives/strategic_reports 表预检——失败 skip）。"""
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
                    await conn.execute("SELECT 1 FROM strategic_archives LIMIT 1")
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


# ===================================================================
# 预置时间戳未来偏移构造（OD-13①——单一基准锚+微秒级偏移判别）
# ===================================================================


def _preset_anchor() -> tuple[datetime, Any]:
    """预置时间基准锚（单一 now——禁逐行取 now 双调：微秒级偏移会被调用间漂移淹没）.

    返回 (base, _at 偏移函数)——base+微秒偏移构造未来时间戳：预置行恒新于共享库
    背景行→行序「占首三」/latest_pdf 三键绝对判别；微秒量级（非 ≥1s）：三 plan
    相互判别+背景行免疫双目标（无时间窗过滤无 6-8 审计窗出窗风险——场景分立注记）。
    """
    base = datetime.now(UTC)

    def _at(microseconds: int) -> datetime:
        return base + timedelta(microseconds=microseconds)

    return base, _at


# ===================================================================
# 归档行预置（repo.save 直写通道——R5 改钦，与报告行通道对称）
# ===================================================================


async def _save_archive_row(
    ctx: dict[str, Any],
    plan_id: str | None,
    *,
    archived_at: datetime,
) -> str:
    """归档行直写（StrategicArchive 实体直构造+archive_repository.save——R5 改钦）.

    archived_at 实体构造参数化（未来偏移可编程——OD-13①）；EVIDENCE_PACKAGE 类型
    plan_id 可空（实体不变量 :48-53 仅三类型强制非空——None 行防御形态可达）；
    A 面走 fixture session flush 不 commit（teardown rollback 回收），B/C 面
    clear_session 后 fallback 独立会话 commit。
    """
    from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
    from src.domain.ports.resolver import resolve

    if not ctx["_a_mode"]:
        _clear_session_ctx()
    archive_id = uuid_module.uuid4()
    entity = StrategicArchive(
        archive_id=archive_id,
        plan_id=uuid_module.UUID(plan_id) if plan_id is not None else None,
        plan_type="SP",
        archive_type=ArchiveType.EVIDENCE_PACKAGE,
        assumptions={"tools_used": [], "evidence_refs": []},
        decision_basis={"kind": "evidence_package", "degraded": False},
        execution_deviation={},
        created_at=archived_at - timedelta(microseconds=1),
        archived_at=archived_at,
    )
    await resolve("archive_repository").save(entity)
    ctx["_archive_ids"].append(str(archive_id))
    if plan_id is not None and plan_id not in ctx["_plan_ids"]:
        ctx["_plan_ids"].append(plan_id)
    return str(archive_id)


# ===================================================================
# 报告行预置（report_repository.save 直写——6-8 _save_report 先例形态）
# ===================================================================


async def _save_report_row(
    ctx: dict[str, Any],
    plan_id: str,
    *,
    report_type: str,
    created_at: datetime,
    degraded_sections: int = 2,
) -> dict[str, str]:
    """报告行直写（StrategicReport 实体构造+report_repository.save 单参——6-8 先例）.

    file_path 按生产单源格式构造（markdown L0 逻辑路径/pdf L4 对象键——
    PDF_OBJECT_KEY_TEMPLATE :79 单源）；created_at 未来偏移可编程（OD-13①）。
    返回精确定位三元组（report_id/file_path/created_at ISO）——断言直推单源
    （A 面未提交行对独立连接回查不可见——预置侧登记替代回查）。
    """
    from src.domain.entities.strategic_report import ReportType, StrategicReport
    from src.domain.ports.resolver import resolve

    if not ctx["_a_mode"]:
        _clear_session_ctx()
    report_id = uuid_module.uuid4()
    file_path = (
        f"reports/{plan_id}/{report_id}.pdf"
        if report_type == "pdf"
        else f"reports/{plan_id}_{created_at.strftime('%Y%m%d%H%M%S')}.md"
    )
    report = StrategicReport(
        report_id=report_id,
        plan_id=plan_id,
        report_type=ReportType(report_type),
        file_path=file_path,
        section_count=11,
        degraded_section_count=degraded_sections,
        generation_ms=1234,
        created_at=created_at,
    )
    await resolve("report_repository").save(report)
    ctx["_report_ids"].append(str(report_id))
    if plan_id not in ctx["_plan_ids"]:
        ctx["_plan_ids"].append(plan_id)
    return {"report_id": str(report_id), "file_path": file_path, "created_at_iso": created_at.isoformat()}


# ===================================================================
# teardown（B/C 面定向 DELETE 行数断言——A 面经 pg_session rollback 回收）
# ===================================================================


async def _teardown_assets(ctx: dict[str, Any]) -> None:
    """teardown 归档行+报告行定向 DELETE（行数断言防静默 0 行假绿——6-8 R2-F3 纪律直系）.

    各步独立 try/except——单步失败不阻断后续清理；A 面归档行/报告行经 pg_session
    fixture rollback 整体回收（跳过 DELETE——零 DELETE 通道）。
    """
    if ctx["_a_mode"] or not (ctx["_archive_ids"] or ctx["_report_ids"]):
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
                if ctx["_archive_ids"]:
                    result = await conn.execute(
                        sa.text("DELETE FROM strategic_archives WHERE archive_id = ANY(:ids)"),
                        {"ids": list(ctx["_archive_ids"])},
                    )
                    expected_archives = len(ctx["_archive_ids"])
                    assert result.rowcount == expected_archives, (
                        f"strategic_archives DELETE 行数 {result.rowcount} != 预置 {expected_archives}（静默 0 行假绿防线）"
                    )
                if ctx["_report_ids"]:
                    result = await conn.execute(
                        sa.text("DELETE FROM strategic_reports WHERE report_id = ANY(:ids)"),
                        {"ids": list(ctx["_report_ids"])},
                    )
                    expected_reports = len(ctx["_report_ids"])
                    assert result.rowcount == expected_reports, (
                        f"strategic_reports DELETE 行数 {result.rowcount} != 预置 {expected_reports}（静默 0 行假绿防线）"
                    )
        finally:
            await engine.dispose()
    except AssertionError:
        raise
    except Exception as error:  # teardown 容错
        print(f"[teardown:consultant-view] 清理异常（容错）: {error}")


# ===================================================================
# 服务构建 + CLI 直调 helper（src 符号全部延迟 import——红锚形态前提）
# ===================================================================


def _build_view_service() -> Any:
    """构建顾问视图服务（两依赖 resolve 既有注册名——OD-10）.

    红锚：consultant_view_service 模块缺失 → 运行期 ImportError（Task 0 红阶段形态）。
    """
    from src.application.services.consultant_view_service import ConsultantViewService
    from src.domain.ports.resolver import resolve

    return ConsultantViewService(
        archive_repository=resolve("archive_repository"),
        report_repository=resolve("report_repository"),
    )


def _run_cli_consultant_view(context: dict[str, Any]) -> None:
    """CLI in-process 直调（双清钦定 + clear_session 清 ContextVar）.

    clear_session 是 CLI 面硬前置：asyncio.run 新循环继承当前上下文的 fixture session 会
    触发「Future attached to a different loop」——必清使服务各仓储走 fallback 独立会话。
    """
    from src.entrypoints import agent_cli

    _clear_session_ctx()
    _clear_resolver_caches()
    exit_code = 0
    try:
        exit_code = agent_cli.main(["consultant-view"])
    except SystemExit as error:  # 红阶段命令未注册 → argparse invalid choice exit 2
        exit_code = int(error.code or 0)
    captured = context["_capsys_ref"].readouterr()
    _clear_resolver_caches()
    context["cli_exit_code"] = exit_code
    context["cli_stdout"] = captured.out
    context["cli_stderr"] = captured.err


def _field_names(obj: Any) -> set[str]:
    """dataclass 字段名集合（键集 exact set 断言——6-8 R1-F10 激活先例形态）."""
    from dataclasses import fields

    return {f.name for f in fields(obj)}


# ===================================================================
# 预置形态（三 plan 交付形态——S2/S4/S7/S10 共用；双 plan——S1；报告行单置——S6；单 plan——S11）
# ===================================================================


def _preset_three_plan_delivery(ctx: dict[str, Any], pg_session: Any) -> dict[str, Any]:
    """预置三 plan 交付形态+None 行（A 面）——AC-2/AC-4 权威预置.

    形态：plan-A 3 归档（+300/+200/+100 µs）+md（+50µs）+pdf（+60µs——最新）；
    plan-B 2 归档（+90/+80 µs）+md（+40µs）；plan-C 1 归档（+70µs）零报告；
    另 1 条 plan_id=None 归档行（+400µs——时间戳最大但剔除判别）。
    行序期望：首三 A→B→C（latest_activity 降序）；latest_pdf 三键==A 的 pdf 行。
    """
    _a_mode_enter(ctx, pg_session)
    _base, _at = _preset_anchor()
    plan_a, plan_b, plan_c = str(uuid_module.uuid4()), str(uuid_module.uuid4()), str(uuid_module.uuid4())

    def _preset() -> None:
        # plan-A：3 条归档行（单基准未来偏移递减——A 组内判别）
        for offset in (300, 200, 100):
            _run_async(_save_archive_row(ctx, plan_a, archived_at=_at(offset)), ctx["_loop"])
        # plan-B：2 条归档行
        for offset in (90, 80):
            _run_async(_save_archive_row(ctx, plan_b, archived_at=_at(offset)), ctx["_loop"])
        # plan-C：1 条归档行（零报告——「有活动无交付物」形态）
        _run_async(_save_archive_row(ctx, plan_c, archived_at=_at(70)), ctx["_loop"])
        # None 行（时间戳全库最大但剔除——防御形态判别）
        _run_async(_save_archive_row(ctx, None, archived_at=_at(400)), ctx["_loop"])
        # 报告行：A md（+50）→A pdf（+60——A 内最新）；B md（+40）
        _run_async(_save_report_row(ctx, plan_a, report_type="markdown", created_at=_at(50)), ctx["_loop"])
        pdf_a = _run_async(_save_report_row(ctx, plan_a, report_type="pdf", created_at=_at(60)), ctx["_loop"])
        _run_async(_save_report_row(ctx, plan_b, report_type="markdown", created_at=_at(40)), ctx["_loop"])
        ctx["preset"]["pdf_a_report_id"] = pdf_a["report_id"]
        ctx["preset"]["pdf_info"] = pdf_a

    _preset()
    preset = {
        "plan_a": plan_a,
        "plan_b": plan_b,
        "plan_c": plan_c,
        "plan_ids": (plan_a, plan_b, plan_c),
        "archive_counts": {plan_a: 3, plan_b: 2, plan_c: 1},
        "latest_activity_offsets": {plan_a: 300, plan_b: 90, plan_c: 70},
        "expected_order": (plan_a, plan_b, plan_c),
        # pdf 行精确定位三元组（预置侧登记单源——A 面未提交行回查不可见，直推替代）
        "pdf_report_id": ctx["preset"].get("pdf_a_report_id", ""),
        "pdf_info": ctx["preset"].get("pdf_info"),
    }
    ctx["preset"].update(preset)
    return preset


def _preset_dual_plan_full(ctx: dict[str, Any], pg_session: Any) -> dict[str, Any]:
    """预置双 plan 全数据形态（A 面）——AC-1 权威预置.

    形态：plan-A 2 归档（+300/+200 µs）+md（+50µs）+pdf（+60µs）；plan-B 1 归档
    （+90µs）+md（+40µs）。latest_pdf 三键==A 的 pdf 行（未来偏移恒为全库最新）。
    """
    _a_mode_enter(ctx, pg_session)
    _base, _at = _preset_anchor()
    plan_a, plan_b = str(uuid_module.uuid4()), str(uuid_module.uuid4())

    def _preset() -> None:
        for offset in (300, 200):
            _run_async(_save_archive_row(ctx, plan_a, archived_at=_at(offset)), ctx["_loop"])
        _run_async(_save_archive_row(ctx, plan_b, archived_at=_at(90)), ctx["_loop"])
        pdf_a = _run_async(_save_report_row(ctx, plan_a, report_type="pdf", created_at=_at(60)), ctx["_loop"])
        _run_async(_save_report_row(ctx, plan_a, report_type="markdown", created_at=_at(50)), ctx["_loop"])
        _run_async(_save_report_row(ctx, plan_b, report_type="markdown", created_at=_at(40)), ctx["_loop"])
        ctx["preset"]["pdf_a_report_id"] = pdf_a["report_id"]
        ctx["preset"]["pdf_info"] = pdf_a

    _preset()
    preset = {
        "plan_a": plan_a,
        "plan_b": plan_b,
        "plan_ids": (plan_a, plan_b),
        "archive_counts": {plan_a: 2, plan_b: 1},
        "expected_pdf_plan": plan_a,
        "pdf_report_id": ctx["preset"].get("pdf_a_report_id", ""),
        "pdf_info": ctx["preset"].get("pdf_info"),
    }
    ctx["preset"].update(preset)
    return preset


def _row_by_plan(view: Any, plan_id: str) -> Any:
    """按 plan_id 定位项目行（预置行级断言——背景行免疫 OD-13）."""
    for row in view.projects.projects:
        if row.plan_id == plan_id:
            return row
    raise AssertionError(f"预置 plan {plan_id} 行不在清单（membership 断言前置失败）")


# ===================================================================
# Background
# ===================================================================


@given("顾问视图依赖服务可用")
def consultant_view_services_available(context: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """Background：PG 服务探测（不可达 pytest.skip 动态跳过）——双表预检."""
    context["_capsys_ref"] = capsys
    _probe_pg_available()


# ===================================================================
# AC-1 三段全落位与键集值级断言
# ===================================================================


@scenario(
    "test_acceptance_consultant_view.feature",
    "三段全落位与键集值级断言",
)
def test_full_view_three_sections() -> None:
    """S1/AC-1 三段全落位（双 plan 全数据——5 键+嵌套键集+值级+恒等式三联）."""
    pass


@given("预置跨 plan 双 plan 全数据形态")
def preset_dual_plan_full(context: dict[str, Any], pg_session: Any) -> None:
    """S1 预置（A 面回滚式通道）：plan-A 2 归档+md+pdf（最新）/plan-B 1 归档+md."""
    _preset_dual_plan_full(context, pg_session)


@when("构建顾问视图")
def build_consultant_view_step(context: dict[str, Any]) -> None:
    """S1~S6/S11：服务直调构建视图（红锚=consultant_view_service ImportError；零参数——全局视图）."""
    service = _build_view_service()
    context["view"] = _run_async(service.build_consultant_view(), context["_loop"])


@then("视图 5 键与三段嵌套键集完整")
def verify_view_and_section_keys(context: dict[str, Any]) -> None:
    """S1：ConsultantView 5 键 + 三段嵌套键集（4/5/7）+ ProjectSummary 6 键 exact set（Task 0.1 冻结表）."""
    view = context["view"]
    assert view is not None, "视图构建失败（context 缺 view）"
    assert _field_names(view) == {"generated_at", "build_degraded", "projects", "brand", "export"}, (
        "顶层 5 键 exact set（顶层无 plan_id 键——全局视图零输入 OD-1）"
    )
    assert _field_names(view.projects) == {"available", "degraded", "plan_count", "projects"}
    assert _field_names(view.brand) == {"degraded", "configured", "logo_status", "color_scheme_status", "font_status"}
    assert _field_names(view.export) == {
        "available",
        "degraded",
        "plans_with_reports",
        "plans_with_latest_pdf",
        "latest_pdf_plan_id",
        "latest_pdf_object_key",
        "latest_pdf_generated_at",
    }
    projects = view.projects.projects
    summary_keys = {
        "plan_id",
        "archive_count",
        "latest_activity_at",
        "latest_report_type",
        "latest_report_at",
        "latest_degraded_section_count",
    }
    assert all(_field_names(row) == summary_keys for row in projects), "ProjectSummary 6 键 exact set（投影白名单防扩散）"
    assert isinstance(view.generated_at, str) and view.generated_at, "generated_at ISO 字符串（单时间锚）"


@then("双 plan 各恰一行且 archive_count 与预置一致")
def verify_dual_plan_membership(context: dict[str, Any]) -> None:
    """S1：membership 全含（双 plan ∈ 清单+各恰一行）+行级 archive_count 直推（背景行免疫 OD-13②）."""
    view = context["view"]
    preset = context["preset"]
    rows = [row for row in view.projects.projects if row.plan_id in preset["plan_ids"]]
    assert len(rows) == 2, f"预置双 plan 应各恰一行（实测 {len(rows)} 行）"
    for plan_id, expected_count in preset["archive_counts"].items():
        row = _row_by_plan(view, plan_id)
        assert row.archive_count == expected_count, (
            f"plan {plan_id[:8]} archive_count 应=={expected_count}（实测 {row.archive_count}）"
        )
        assert isinstance(row.plan_id, str), "plan_id str 化钦定（实体 UUID→str——6-8 report_id 同款）"


@then("latest_pdf 定位三键与预置 pdf 行一致")
def verify_latest_pdf_keys(context: dict[str, Any]) -> None:
    """S1：latest_pdf 三键值级与预置 pdf 行直推（未来偏移保全库最新——OD-13①）."""
    view = context["view"]
    preset = context["preset"]
    pdf_info = preset["pdf_info"]
    assert pdf_info is not None, "预置 pdf 行定位三元组缺失"
    assert view.export.latest_pdf_plan_id == preset["expected_pdf_plan"]
    assert view.export.latest_pdf_object_key == pdf_info["file_path"], "latest_pdf_object_key==file_path 直传（L4 对象键单源）"
    assert view.export.latest_pdf_generated_at == pdf_info["created_at_iso"]


@then("计数恒等式三联成立")
def verify_count_invariants(context: dict[str, Any]) -> None:
    """S1：VO 内部不变量三联（对任意行集成立——背景行免疫，验收面直接断言）."""
    view = context["view"]
    projects = view.projects.projects
    assert view.projects.plan_count == len(projects), "plan_count == len(projects)"
    assert view.export.plans_with_reports == sum(1 for row in projects if row.latest_report_type is not None)
    assert view.export.plans_with_latest_pdf == sum(1 for row in projects if row.latest_report_type == "pdf")


# ===================================================================
# AC-2 三 plan 交付形态与排序判别
# ===================================================================


@scenario(
    "test_acceptance_consultant_view.feature",
    "三 plan 交付形态与排序判别",
)
def test_three_plan_delivery_forms() -> None:
    """S2/AC-2 三 plan 形态（排序+None 行剔除+零报告形态）."""
    pass


@given("预置三 plan 交付形态与无 plan 归档行")
def preset_three_plan_delivery_step(context: dict[str, Any], pg_session: Any) -> None:
    """S2/S4 预置（A 面回滚式通道）：三 plan 交付形态+None 行（时间戳未来偏移判别）."""
    _preset_three_plan_delivery(context, pg_session)


@then("预置三 plan 占清单首三且内部按最新活动降序")
def verify_preset_order_head(context: dict[str, Any]) -> None:
    """S2：预置行占首三（未来偏移恒新于背景行）+内部降序 A→B→C（OD-13①）."""
    view = context["view"]
    preset = context["preset"]
    head_three = tuple(row.plan_id for row in view.projects.projects[:3])
    assert head_three == preset["expected_order"], (
        f"首三应=={tuple(p[:8] for p in preset['expected_order'])}（实测 {tuple(p[:8] for p in head_three)}）"
    )


@then("逐行 archive_count 精确为 3 与 2 与 1")
def verify_archive_counts(context: dict[str, Any]) -> None:
    """S2：三行 archive_count 直推 3/2/1（None 行不计入即判别——错计入则红）."""
    view = context["view"]
    preset = context["preset"]
    for plan_id, expected in preset["archive_counts"].items():
        row = _row_by_plan(view, plan_id)
        assert row.archive_count == expected, (
            f"plan {plan_id[:8]} archive_count 应=={expected}（实测 {row.archive_count}——None 行计入即红）"
        )


@then("零报告 plan 的报告三键全为 None")
def verify_zero_report_plan(context: dict[str, Any]) -> None:
    """S2：plan-C 报告三键 None（「有活动无交付物」诚实态——无报告非降级）."""
    view = context["view"]
    row = _row_by_plan(view, context["preset"]["plan_c"])
    assert row.latest_report_type is None
    assert row.latest_report_at is None
    assert row.latest_degraded_section_count is None


@then("无 plan 归档行不计入任何项目计数")
def verify_none_row_excluded(context: dict[str, Any]) -> None:
    """S2：None 行剔除判别（三行 archive_count 精确值即判别——防御格验收承载）.

    None 行时间戳全库最大（+400µs）——若误入清单将占首行且 plan_count 多计；
    三行计数精确+首三占位断言共同构成剔除判别（口径四冻结）。
    """
    view = context["view"]
    preset = context["preset"]
    # 预置三 plan 之外若还有行必为背景行（非 None——None 行 plan_id 非法字符串不可达）；
    # 本断言核心是三 plan 计数精确（上一步承载）+首三占位——此处防御 None 形态泄漏
    for row in view.projects.projects[:3]:
        assert row.plan_id in preset["plan_ids"], "首三必为预置 plan（None 行/背景行不入首三）"


# ===================================================================
# AC-3 品牌段恒系统默认态
# ===================================================================


@scenario(
    "test_acceptance_consultant_view.feature",
    "品牌段恒系统默认态",
)
def test_brand_section_defaults() -> None:
    """S3/AC-3 品牌段（V1 恒系统默认态——6-11 对接锚）."""
    pass


@then("品牌段 5 键五值级恒默认态")
def verify_brand_defaults(context: dict[str, Any]) -> None:
    """S3：品牌段零 IO 静态恒在——五值级恒等（V1 时点事实断言——6-11 演进信号语义）."""
    from src.application.ports.consultant_view import BRAND_FONT_STATUS, BRAND_STATUS_UNCONFIGURED

    view = context["view"]
    brand = view.brand
    assert brand.degraded is False, "品牌段无降级面（零 IO 恒稳——结构性承诺）"
    assert brand.configured is False, "configured 恒 False（V1——6-11 实施后红是预期演进信号非 flake）"
    assert brand.logo_status == BRAND_STATUS_UNCONFIGURED == "未配置（系统默认）"
    assert brand.color_scheme_status == BRAND_STATUS_UNCONFIGURED == "未配置（系统默认）"
    assert brand.font_status == BRAND_FONT_STATUS == "STSong-Light（内置）", (
        "font_status 与渲染器 _FONT_NAME :60 冻结字体事实单源对齐（字面量承载禁 import infra）"
    )


# ===================================================================
# AC-4 导出段派生与最新 PDF 定位
# ===================================================================


@scenario(
    "test_acceptance_consultant_view.feature",
    "导出段派生与最新 PDF 定位",
)
def test_export_section_derivation() -> None:
    """S4/AC-4 导出段（跨 plan 报告派生+最新 PDF 定位+遮蔽口径）."""
    pass


@then("双报告 plan 行最新报告类型为 pdf 且单报告 plan 行为 markdown")
def verify_latest_report_types(context: dict[str, Any]) -> None:
    """S4：预置行级断言（A 行 latest==pdf——md 被 pdf 遮蔽；B 行 latest==markdown）."""
    view = context["view"]
    preset = context["preset"]
    row_a = _row_by_plan(view, preset["plan_a"])
    row_b = _row_by_plan(view, preset["plan_b"])
    assert row_a.latest_report_type == "pdf", (
        f"plan-A 行 latest 应==pdf（先生成 md 后生成 pdf——最新遮蔽口径 OD-7；实测 {row_a.latest_report_type}）"
    )
    assert row_b.latest_report_type == "markdown"
    assert row_a.latest_report_at is not None and row_b.latest_report_at is not None


@then("latest_pdf 三键与预置 pdf 行直推一致")
def verify_latest_pdf_derivation(context: dict[str, Any]) -> None:
    """S4：latest_pdf 三键值级（预置 pdf 行未来偏移恒为全库最新——绝对断言成立）."""
    view = context["view"]
    preset = context["preset"]
    pdf_info = preset["pdf_info"]
    assert pdf_info is not None, "预置 pdf 行定位三元组缺失"
    assert view.export.latest_pdf_plan_id == preset["plan_a"]
    assert view.export.latest_pdf_object_key == pdf_info["file_path"]
    assert view.export.latest_pdf_generated_at == pdf_info["created_at_iso"]
    assert view.export.available is True, "available==plans_with_reports>0（有报告可导出——markdown 亦是可交付物）"


@then("导出段计数与项目段循环结果恒等")
def verify_export_projection(context: dict[str, Any]) -> None:
    """S4：导出段纯投影派生（两计数恒等式——VO 内部不变量背景行免疫）."""
    view = context["view"]
    projects = view.projects.projects
    assert view.export.plans_with_reports == sum(1 for row in projects if row.latest_report_type is not None)
    assert view.export.plans_with_latest_pdf == sum(1 for row in projects if row.latest_report_type == "pdf")
    assert view.export.degraded == view.projects.degraded, "导出段与项目段同源联动（OD-12）"


# ===================================================================
# AC-5 空态幂等读 + 单源契约绊线
# ===================================================================


@scenario(
    "test_acceptance_consultant_view.feature",
    "空态幂等读核心四断言",
)
def test_empty_state_idempotent_read() -> None:
    """S5/AC-5 空态幂等读（共享库核心四断言——绝对空态断言归单测 OD-13④）."""
    pass


@given("零预置的空租户形态")
def preset_nothing(context: dict[str, Any]) -> None:
    """S5 预置：零预置（本场景不写入——共享库背景行不在断言面，核心四断言承载）."""
    # 零预置（零 IO 面）——断言口径 OD-13④：5 键恒在+brand 完整+build_degraded False+不抛
    # 「零行全库」物理不可构造（共享库背景行在），绝对空态值断言归单测（Task 2 空态格）
    assert context["view"] is None


@then("视图 5 键恒在且 build_degraded 为 False")
def verify_empty_state_five_keys(context: dict[str, Any]) -> None:
    """S5：5 键恒在+build_degraded False（「没有数据」非「拿不到数据」——五先例族第六连）."""
    view = context["view"]
    assert view is not None, "空态幂等读应正常返回视图（不抛）"
    assert _field_names(view) == {"generated_at", "build_degraded", "projects", "brand", "export"}
    assert view.build_degraded is False


@then("品牌段完整默认态五键恒在")
def verify_empty_state_brand(context: dict[str, Any]) -> None:
    """S5：品牌段完整默认态（三段中唯一恒数据段——零 IO 恒在，与数据面正交）."""
    view = context["view"]
    assert _field_names(view.brand) == {"degraded", "configured", "logo_status", "color_scheme_status", "font_status"}
    assert view.brand.degraded is False
    assert view.brand.configured is False
    assert view.brand.logo_status == "未配置（系统默认）"
    assert view.brand.color_scheme_status == "未配置（系统默认）"
    assert view.brand.font_status == "STSong-Light（内置）"


@then("构建不抛异常")
def verify_build_no_raise(context: dict[str, Any]) -> None:
    """S5：构建不抛（When 步骤成功返回即承载——五先例族；空态是正常态非错误）."""
    assert context["view"] is not None, "构建步骤应成功返回（异常则 When 步已红）"


@scenario(
    "test_acceptance_consultant_view.feature",
    "单源契约绊线",
)
def test_single_source_tripwire() -> None:
    """S6/AC-5 单源契约绊线（零归档+报告行在场→报告行 plan 不入清单——R4-F3 诚实重标）."""
    pass


@given("预置零归档行仅有报告行的形态")
def preset_report_only(context: dict[str, Any], pg_session: Any) -> None:
    """S6 预置（A 面）：仅 1 报告行零归档行（plan 清单单源=archives 反推判别）.

    绊线语义（R4-F3）：ReportRepositoryProtocol 无 plan 枚举 API（get_latest_by_plan
    是 plan_id 入参点查）——「从报告行聚合 plan」变异在两端口注入面内无实现通道，
    本场景当前端口面下恒绿——判别力面向未来端口扩展（6-11/7-x 加 list/distinct
    方法后 union 清单立即红）；段级容错归单测的注记随本 docstring 承载。
    """
    _a_mode_enter(context, pg_session)
    _base, _at = _preset_anchor()
    plan_d = str(uuid_module.uuid4())

    def _preset() -> None:
        _run_async(
            _save_report_row(context, plan_d, report_type="markdown", created_at=_at(50)),
            context["_loop"],
        )

    _preset()
    context["preset"]["report_only_plan"] = plan_d


@then("报告行所属 plan 不入项目清单")
def verify_report_only_plan_excluded(context: dict[str, Any]) -> None:
    """S6：报告行 plan_id ∉ 清单 plan 集（membership 措辞——OD-13② 升格联动）."""
    view = context["view"]
    plan_d = context["preset"]["report_only_plan"]
    listed = {row.plan_id for row in view.projects.projects}
    assert plan_d not in listed, "清单单源=archives 反推（报告行 plan 不入清单——单源契约绊线）"


# ===================================================================
# AC-6 CLI consultant-view（零参数全局视图）
# ===================================================================


@scenario(
    "test_acceptance_consultant_view.feature",
    "CLI 全数据输出",
)
def test_cli_full_data_output() -> None:
    """S7/AC-6 CLI 全数据输出（包含断言——预置行输出 in stdout，背景行免疫 OD-13③）."""
    pass


@given("CLI 面已预置三 plan 全数据形态")
def preset_cli_three_plan(context: dict[str, Any]) -> None:
    """S7 预置（B 面 commit 式——CLI 直调须 clear_session，预置走 fallback 独立会话 commit）."""
    context["_a_mode"] = False  # B 面：禁 set_session（CLI asyncio.run 新循环防线）
    _clear_session_ctx()
    _base, _at = _preset_anchor()
    plan_a, plan_b, plan_c = str(uuid_module.uuid4()), str(uuid_module.uuid4()), str(uuid_module.uuid4())

    def _preset() -> None:
        for offset in (300, 200, 100):
            _run_async(_save_archive_row(context, plan_a, archived_at=_at(offset)), context["_loop"])
        for offset in (90, 80):
            _run_async(_save_archive_row(context, plan_b, archived_at=_at(offset)), context["_loop"])
        _run_async(_save_archive_row(context, plan_c, archived_at=_at(70)), context["_loop"])
        _run_async(_save_archive_row(context, None, archived_at=_at(400)), context["_loop"])
        pdf_a = _run_async(
            _save_report_row(context, plan_a, report_type="pdf", created_at=_at(60)),
            context["_loop"],
        )
        _run_async(
            _save_report_row(context, plan_a, report_type="markdown", created_at=_at(50)),
            context["_loop"],
        )
        _run_async(
            _save_report_row(context, plan_b, report_type="markdown", created_at=_at(40)),
            context["_loop"],
        )
        context["preset"]["pdf_report_id"] = pdf_a["report_id"]

    _preset()
    context["preset"].update(
        {
            "plan_a": plan_a,
            "plan_b": plan_b,
            "plan_c": plan_c,
            "plan_ids": (plan_a, plan_b, plan_c),
            "archive_counts": {plan_a: 3, plan_b: 2, plan_c: 1},
            "latest_activity_offsets": {plan_a: 300, plan_b: 90, plan_c: 70},
        }
    )


@when("CLI 直调 consultant-view")
def run_cli_consultant_view_step(context: dict[str, Any]) -> None:
    """S7/S8：CLI in-process 直调（双清+clear_session——红锚=argparse invalid choice exit 2）."""
    _run_cli_consultant_view(context)


@then("预置三 plan 逐行输出与品牌两行与导出段行均在 stdout")
def verify_cli_full_output(context: dict[str, Any]) -> None:
    """S7：包含断言（预置行逐行 in stdout——不断言完整输出集，背景行计入输出 OD-13③）."""
    stdout = context["cli_stdout"]
    preset = context["preset"]
    assert context["cli_exit_code"] == 0, f"exit code 应 0（实测 {context['cli_exit_code']}）"
    assert "顾问视图（全局多项目面板）" in stdout, "首行恒在"
    for separator in ("── 多项目概况 ──", "── 品牌配置 ──", "── 白标导出 ──"):
        assert separator in stdout, f"三段分隔行缺失 {separator}"
    for plan_id, count in preset["archive_counts"].items():
        assert f"{plan_id} | 归档: {count} |" in stdout, (
            f"预置 plan {plan_id[:8]} 项目行（归档 {count}）应在 stdout（包含断言——背景行免疫）"
        )
    assert "品牌模板: 未配置（系统默认） | Logo: 默认 | 配色: 默认 | 字体: STSong-Light（内置）" in stdout
    assert "提示: 品牌模板配置归 Story 6-11（白标报告基础）" in stdout, "品牌段注记行恒在（6-11 对接锚呈现面）"
    assert "最新 PDF:" in stdout, "导出段最新 PDF 定位行在位"


@then("提示行在位且 exit code 为 0")
def verify_cli_hint_lines(context: dict[str, Any]) -> None:
    """S7：导出提示行（指向既有命令——6-8 :1579「可先执行 report-generate」同款形态第三连）+exit 0."""
    stdout = context["cli_stdout"]
    assert context["cli_exit_code"] == 0
    assert "提示: 执行 report-generate --plan-id <uuid> --format pdf 生成白标 PDF" in stdout
    assert f"最新 PDF: {context['preset']['plan_a']}" in stdout, "最新 PDF 定位行指向预置 plan-A"


@scenario(
    "test_acceptance_consultant_view.feature",
    "CLI 输出格式与恒在行断言",
)
def test_cli_format_and_permanent_lines() -> None:
    """S8/AC-6 CLI 输出格式与恒在行（真库任意行数冒烟——空态精确语义归 CLI 单测 stub 格）."""
    pass


@then("项目计数行格式与品牌两行与提示行恒在")
def verify_cli_format_lines(context: dict[str, Any]) -> None:
    """S8：格式断言（`项目: 共 ` 前缀+` 个` 后缀模式+品牌两行+提示行恒在——不断言总行数）."""
    stdout = context["cli_stdout"]
    assert "项目: 共 " in stdout and " 个" in stdout, "项目计数行格式模式（真库任意行数）"
    assert "品牌模板: 未配置（系统默认） | Logo: 默认 | 配色: 默认 | 字体: STSong-Light（内置）" in stdout
    assert "提示: 品牌模板配置归 Story 6-11（白标报告基础）" in stdout
    assert "提示: 执行 report-generate --plan-id <uuid> --format pdf 生成白标 PDF" in stdout


@then("exit code 为 0")
def verify_cli_exit_zero(context: dict[str, Any]) -> None:
    """S8：正常退出（含空态——空态是正常态非错误）."""
    assert context["cli_exit_code"] == 0


# ===================================================================
# AC-7 性能与并发
# ===================================================================


@scenario(
    "test_acceptance_consultant_view.feature",
    "性能采样 20 轮 P95",
)
def test_performance_p95() -> None:
    """S9/AC-7 性能 20 轮 P95<800ms（服务面两读窗口——背景量级敏感 skip 门）."""
    pass


@given("性能面服务已预热且背景量级在阈值内")
def preset_performance_warmup(context: dict[str, Any]) -> None:
    """S9 预置（C 面）：背景 distinct plan 清点（>50 skip——环境量级敏感 OD-13）+预热.

    C 面纪律：禁 set_session——每路 fallback 独立会话天然 per-task 隔离（6-8 R2-F3 直系）。
    """
    context["_a_mode"] = False
    _clear_session_ctx()
    service = _build_view_service()

    async def _count_background_plans() -> int:
        from src.domain.ports.archive_repository import ArchiveQuery
        from src.domain.ports.resolver import resolve

        rows = await resolve("archive_repository").find(ArchiveQuery(plan_id=None, limit=1000))
        return len({row.plan_id for row in rows if row.plan_id is not None})

    background_plans = _run_async(_count_background_plans(), context["_loop"])
    if background_plans > _BACKGROUND_PLAN_LIMIT:
        pytest.skip(
            f"背景 distinct plan 数 {background_plans} 超阈值 {_BACKGROUND_PLAN_LIMIT}（环境量级敏感——N+1 点查链成本随 N 增长）"
        )
    for _ in range(_WARMUP_ROUNDS):  # 预热含首轮连接池建立
        _run_async(service.build_consultant_view(), context["_loop"])


@when("采样 20 轮视图构建计时")
def sample_20_rounds(context: dict[str, Any]) -> None:
    """S9：20 轮采样（sorted[ceil(0.95*n)-1] 数学口径——6-3/6-6/6-7/6-8/6-9 六连同款公式）."""
    service = _build_view_service()
    durations: list[float] = []
    for _ in range(_SAMPLE_ROUNDS):
        start = time.perf_counter()
        _run_async(service.build_consultant_view(), context["_loop"])
        durations.append((time.perf_counter() - start) * 1000.0)
    context["durations"] = durations


@then("P95 小于 800ms")
def verify_p95(context: dict[str, Any]) -> None:
    """S9：P95<800ms（epics L2498 视图加载延迟的聚合服务面等价口径）."""
    durations = context["durations"]
    assert len(durations) == _SAMPLE_ROUNDS
    p95 = sorted(durations)[math.ceil(_P95_PERCENTILE * len(durations)) - 1]
    assert p95 < _P95_LIMIT_MS, f"P95 {p95:.1f}ms 超门禁 {_P95_LIMIT_MS}ms（全量: {sorted(durations)}）"


@scenario(
    "test_acceptance_consultant_view.feature",
    "并发 20 路子集过滤对照",
)
def test_concurrent_20_reads() -> None:
    """S10/AC-7 并发 20 路（预置子集过滤后逐路相等——全集相等禁用 OD-13）."""
    pass


@given("并发面已预置三 plan 全数据形态")
def preset_concurrent_three_plan(context: dict[str, Any]) -> None:
    """S10 预置（C 面 commit 式）：三 plan 全数据（与 S2 形态同构——membership 过滤对照面）."""
    context["_a_mode"] = False
    _clear_session_ctx()
    _base, _at = _preset_anchor()
    plan_a, plan_b, plan_c = str(uuid_module.uuid4()), str(uuid_module.uuid4()), str(uuid_module.uuid4())

    def _preset() -> None:
        for offset in (300, 200, 100):
            _run_async(_save_archive_row(context, plan_a, archived_at=_at(offset)), context["_loop"])
        for offset in (90, 80):
            _run_async(_save_archive_row(context, plan_b, archived_at=_at(offset)), context["_loop"])
        _run_async(_save_archive_row(context, plan_c, archived_at=_at(70)), context["_loop"])
        _run_async(
            _save_report_row(context, plan_a, report_type="pdf", created_at=_at(60)),
            context["_loop"],
        )
        _run_async(
            _save_report_row(context, plan_b, report_type="markdown", created_at=_at(40)),
            context["_loop"],
        )

    _preset()
    context["preset"]["plan_ids"] = (plan_a, plan_b, plan_c)


@when("20 路并发构建顾问视图")
def concurrent_20_builds(context: dict[str, Any]) -> None:
    """S10：gather 20 路（读面幂等无副作用；服务无状态——SINGLETON 并发共享禁持可变实例态）."""

    async def _gather() -> list[Any]:
        service = _build_view_service()
        return list(await asyncio.gather(*[service.build_consultant_view() for _ in range(_CONCURRENCY)]))

    context["concurrent_views"] = _run_async(_gather(), context["_loop"])


@then("全部成功且预置子集过滤后逐路相等")
def verify_concurrent_subset_equality(context: dict[str, Any]) -> None:
    """S10：20 路全成功+membership 过滤 projects 后逐路相等（排除 generated_at+export 段）.

    全集相等禁用（OD-13）：全局无窗查询并发窗内受其他 worker 写入抖动——projects
    全排除则判别力归零，故按预置 plan 子集过滤后对照；export 段是全库派生投影
    （窗内可变）不入对照；brand 段零 IO 恒稳入对照；generated_at 每路互异排除。
    """

    def _freeze(value: Any) -> Any:
        if isinstance(value, dict):
            return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
        if isinstance(value, (list, tuple)):
            return tuple(_freeze(item) for item in value)
        return value

    preset_ids = set(context["preset"]["plan_ids"])
    serialized: set[Any] = set()
    for view in context["concurrent_views"]:
        assert view is not None, "20 路应全部成功不抛"
        data = dataclasses.asdict(view)
        for key in _EXCLUDED_TOP_KEYS:
            data.pop(key, None)
        data["projects"]["projects"] = [row for row in data["projects"]["projects"] if row["plan_id"] in preset_ids]
        serialized.add(_freeze(data))
    assert len(context["concurrent_views"]) == _CONCURRENCY
    assert len(serialized) == 1, f"预置子集过滤后应逐路相等（实测 {len(serialized)} 种形态——含 build_degraded/brand 段对照）"


# ===================================================================
# AC-7 租户隔离正向可见性
# ===================================================================


@scenario(
    "test_acceptance_consultant_view.feature",
    "租户隔离正向可见性",
)
def test_tenant_isolation_visibility() -> None:
    """S11/AC-7 租户隔离正向可见性（隔离继承口径——1-11 合规面承载语义本体）."""
    pass


@given("预置租户可见性判别 plan")
def preset_isolation_plan(context: dict[str, Any], pg_session: Any) -> None:
    """S11 预置（A 面）：单 plan 1 归档行（正向可见性断言数据面）.

    口径声明（OD-13）：共享测试库单 schema 下「零跨漏」排他断言不可判别——本场景
    承载正向可见性（预置 plan 在面板可见+值级直推）；隔离语义本体归 1-11 合规面
    测试承载；「Schema per Tenant 完整实现」归租户管理后续 Story（OD-1 注记）。
    """
    _a_mode_enter(context, pg_session)
    _base, _at = _preset_anchor()
    plan_id = str(uuid_module.uuid4())
    _run_async(_save_archive_row(context, plan_id, archived_at=_at(100)), context["_loop"])
    context["preset"]["isolation_plan"] = plan_id


@then("预置 plan 在面板可见且值级直推一致")
def verify_isolation_visibility(context: dict[str, Any]) -> None:
    """S11：预置 plan ∈ 清单+各恰一行+行级值直推（membership 全含——正向可见性）."""
    view = context["view"]
    plan_id = context["preset"]["isolation_plan"]
    rows = [row for row in view.projects.projects if row.plan_id == plan_id]
    assert len(rows) == 1, f"预置 plan 应恰一行（实测 {len(rows)}）"
    row = rows[0]
    assert row.archive_count == 1
    assert row.latest_activity_at is not None, "预置行未来偏移时间戳→latest_activity_at 非 None"


# ===================================================================
# 收尾：完成清单存在性断言
# ===================================================================


@scenario(
    "test_acceptance_consultant_view.feature",
    "src 与四测试目录完成清单",
)
def test_completion_checklist() -> None:
    """S12/收尾：src 与四测试目录完成清单存在性断言（6-7/6-8/6-9 S12 形态第四连）."""
    pass


@then("src 新增与扩展文件存在")
def verify_completion_src_files() -> None:
    """S12①：src 面 3 新建+2 扩展完成清单（path.is_file 断言）."""
    for label, relative in _COMPLETION_SRC_FILES.items():
        path = ROOT / relative
        assert path.is_file(), f"src 完成清单缺失: {label} ({relative})"


@then("四测试目录新增与扩展文件存在")
def verify_completion_test_files() -> None:
    """S12②：四测试目录 8 新建+1 扩展完成清单（path.is_file 断言）."""
    for label, relative in _COMPLETION_TEST_FILES.items():
        path = ROOT / relative
        assert path.is_file(), f"测试完成清单缺失: {label} ({relative})"
