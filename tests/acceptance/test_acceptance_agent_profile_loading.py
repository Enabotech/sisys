"""Story 5-2 — Agent 身份档案加载验收测试（BDD 场景步骤实现）。

结构范本：test_acceptance_agent_instantiation.py（5-1 最新形态——FEATURE 常量 +
@scenario 显式绑定 + context dict + 场景级独立 Redis 客户端 + _run_async 同循环调度）；
AST 静态扫描写法参照 test_acceptance_postgresql_relational_layer.py（用户指定模板的
继承先例——本 Story 未含独立 AST 场景，架构约束归 tests/unit/architecture/）。

新模块延迟 import 纪律：本 Story 交付的模块（agent_profile / agent_profile_loader /
markdown_agent_profile_loader / skill_selector / registry.selector /
agent_profile_loading / 442-443 异常）一律在步骤函数体内延迟 import——模块顶部
import 会使 pytest 收集期整文件 collection error，已实现/未实现场景一起炸，
无法逐 Task 转绿（先例 test_acceptance_strategic_archive.py L107-108）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_agent_profile_loading.py -v

测试隔离:
    - Redis 键 build_key("agent", str(agent_id)) 无租户维度——agent_id uuid4 天然唯一即隔离
    - teardown 仅精确删除本场景记录的 agent_id 键（禁 delete_pattern/flush——多 worker
      共享 6380 实例会误删并行场景正使用的键）
    - 场景级独立 Redis 客户端 + 同循环关闭（跨循环 "Event loop is closed" 存档教训）
    - BDD 步骤禁 @pytest.mark.asyncio（context 数据丢失），统一 _run_async 调度
    - 验收禁调用 bootstrap()（session 级 _bootstrap_once 已引导，同进程二次调用因
      lambda 工厂 spec 不幂等必抛 ConflictError）
    - resolve 纪律分档：仅无连接构造端口（agent_profile_loader / skill_loader /
      skill_selector——本地静态文件只读）可 resolve；仓储一律场景级客户端手动组装；
      禁 resolve("agent_repository") / resolve("agent_profile_use_case") 发命令
      （SCOPED/SINGLETON 实例钉住全局 Resolver，跨循环死连接）
    - 档案破坏场景（AC-1.2/1.3/2.3）一律 tmp_path 构造 + 构造注入 profile_root，
      禁止修改内置 configs/agents/profiles/ceo/ 生产资产
"""

from __future__ import annotations

import asyncio
import statistics
import time
import uuid
from collections.abc import Coroutine, Generator
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenario, then, when

from src.domain.entities.agent import AgentRole, AgentStatus
from src.infrastructure.storage.redis.key_builder import build_key

FEATURE = "test_acceptance_agent_profile_loading.feature"

# 仓库根锚定（AC-2.1 内置资产 / AC-6.2/6.3 完成清单断言用，不依赖 cwd）
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# 六档案固定名（加载顺序即 or.md 四.1.[1] 枚举序）
PROFILE_FILE_NAMES = ("IDENTITY.md", "CODE.md", "SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md")

# 文件名不含服务关键词，acceptance conftest 不会自动添加 marker——显式声明；
# xdist_group 使本文件全部场景（含 AC-5.1 计时）在同一 worker 串行执行
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.redis,
    pytest.mark.xdist_group("agent-profile-loading"),
]


# ===================================================================
# 场景绑定（14 个，场景名从 .feature 复制粘贴——ASCII 连字符 + 两侧空格）
# ===================================================================


@scenario(FEATURE, "AC-1.1 - 加载 CEO Agent 七档案成功")
def test_ac_1_1_load_ceo_seven_profiles_success(context: dict[str, Any]) -> None:
    """AC-1.1: 六档案 + TOOLS L1 视图（23 ACTIVE）+ 三段结果。"""


@scenario(FEATURE, "AC-1.2 - 档案文件缺失抛异常")
def test_ac_1_2_profile_file_missing(context: dict[str, Any]) -> None:
    """AC-1.2: 缺 IDENTITY.md → AgentProfileError(442) 携带文件名。"""


@scenario(FEATURE, "AC-1.3 - 档案内容空白抛异常")
def test_ac_1_3_profile_content_blank(context: dict[str, Any]) -> None:
    """AC-1.3: 六档案全空白 → 442 携带空白文件名与原因。"""


@scenario(FEATURE, "AC-2.1 - 档案内容验证通过")
def test_ac_2_1_profile_content_valid(context: dict[str, Any]) -> None:
    """AC-2.1: 内置 CEO 档案验证全过 + IDENTITY 含 CEO + ≤64KB。"""


@scenario(FEATURE, "AC-2.2 - agent_id 不存在抛异常")
def test_ac_2_2_agent_not_found(context: dict[str, Any]) -> None:
    """AC-2.2: 随机 agent_id → AgentNotFoundError(443) 携带 agent_id。"""


@scenario(FEATURE, "AC-2.3 - 档案大小超限抛异常")
def test_ac_2_3_profile_size_exceeded(context: dict[str, Any]) -> None:
    """AC-2.3: 单档案 >65536 字节 → 442 携带超限文件名。"""


@scenario(FEATURE, "AC-3.1 - Skills L1 元数据与 token 预算")
def test_ac_3_1_skills_l1_metadata_and_budget(context: dict[str, Any]) -> None:
    """AC-3.1: 23 条 ACTIVE + L1 拼接视图计量 ≤1200 tokens。"""


@scenario(FEATURE, "AC-3.2 - SkillSelector 返回 ACTIVE 列表")
def test_ac_3_2_skill_selector_active_list(context: dict[str, Any]) -> None:
    """AC-3.2: list_active_skills 返回 23 条 ACTIVE 且零排序副作用。"""


@scenario(FEATURE, "AC-4.1 - 启动上下文 token 预算与事件发布")
def test_ac_4_1_startup_budget_and_event(context: dict[str, Any]) -> None:
    """AC-4.1: 分项/总量预算 + InMemoryEventBus 捕获 AgentProfileLoaded 四字段。"""


@pytest.mark.benchmark  # 性能场景级标记（AC-5 checklist L138/L460——R1-F8 场景级形态，不打文件级以防 12 个非计时场景误挂语义）
@scenario(FEATURE, "AC-5.1 - 档案加载延迟 P95 小于 500 毫秒")
def test_ac_5_1_p95_under_500ms(context: dict[str, Any]) -> None:
    """AC-5.1: 真实 Redis ≥20 采样 P95<500ms（warmup 剔除 1 次）。"""


@pytest.mark.benchmark  # 性能场景级标记（同上——R1-F8）
@scenario(FEATURE, "AC-5.2 - 二十次重复档案加载全部成功")
def test_ac_5_2_twenty_repeated_loads(context: dict[str, Any]) -> None:
    """AC-5.2: 同一 agent_id 20 次重复加载全部成功（幂等只读）。"""


@scenario(FEATURE, "AC-6.1 - 三端口接线可达")
def test_ac_6_1_three_ports_resolvable(context: dict[str, Any]) -> None:
    """AC-6.1: 三端口 resolve 可达 + isinstance 合规（禁对产物发命令）。"""


@scenario(FEATURE, "AC-6.2 - 事件双登记与 CLI 注册")
def test_ac_6_2_event_dual_registration_and_cli(context: dict[str, Any]) -> None:
    """AC-6.2: yaml + DEFAULT_MAPPINGS 双登记 + CLI load-profile 注册（静态 tripwire）。"""


@scenario(FEATURE, "AC-6.3 - 完成清单逐项确认")
def test_ac_6_3_completion_checklist(context: dict[str, Any]) -> None:
    """AC-6.3: src/tests 完成清单 + L1-L8 接线终态（Task 0 落盘，Task 8 转绿核对）。"""


# ===================================================================
# 共享基建：context fixture + _run_async
# ===================================================================


@pytest.fixture
def context(
    event_loop: asyncio.AbstractEventLoop,
    acceptance_env_config: Any,
) -> Generator[dict[str, Any], None, None]:
    """BDD 步骤间共享状态容器（场景级独立 Redis 客户端 + 同循环 teardown 关闭）。

    Redis 客户端必须场景级独立创建（不用 session 级共享 fixture）：session 客户端的
    连接池持有前一场景已关闭事件循环的连接，跨场景复用会抛 RuntimeError
    "Event loop is closed"（仓库存档教训）。teardown 仅精确删除本场景记录的
    agent_id 对应键——通配删除会误删并行 worker 正使用的键；无需 Redis 的
    端口直连/静态场景不触发任何 Redis 命令（客户端仅在 teardown 关闭，空连零副作用）。
    """
    import redis.asyncio as aioredis

    redis_client = aioredis.Redis(
        host=acceptance_env_config.redis.host,
        port=acceptance_env_config.redis.port,
        password=acceptance_env_config.redis.password,
        decode_responses=True,
    )
    ctx: dict[str, Any] = {
        "_tenant": uuid.uuid4(),
        "_loop": event_loop,
        "_redis_client": redis_client,
        "_agent_ids": [],
    }
    yield ctx

    # teardown: 逐键精确删除本场景创建的 Agent 状态键 + 同循环关闭客户端
    for agent_id in ctx["_agent_ids"]:
        _run_async(event_loop, redis_client.delete(build_key("agent", str(agent_id))))
    _run_async(event_loop, redis_client.close())


def _run_async(event_loop: asyncio.AbstractEventLoop, coro: Coroutine[Any, Any, Any]) -> Any:
    """在场景级共享事件循环上同步调度协程。

    BDD 步骤函数禁止 @pytest.mark.asyncio（context 数据丢失）；
    aioredis/asyncio.Lock 等对象在首次使用时绑定事件循环，
    必须复用同一循环，否则抛 "Event loop is closed" 跨循环错误。
    """
    return event_loop.run_until_complete(coro)


# ===================================================================
# 门控与用例级服务组装（分档：需 instantiate 四场景 / 仅仓储 / 端口直连）
# ===================================================================


@given("Redis 缓存服务可用")
def given_redis_service_available(context: dict[str, Any]) -> None:
    """验证 Redis 服务可用（不可用时场景整体动态跳过，禁止写死 skip）。"""
    try:
        _run_async(context["_loop"], context["_redis_client"].ping())
    except Exception as exc:
        pytest.skip(f"Redis not available: {exc}")


@given("CEO Agent 已实例化且状态为 IDLE")
def given_ceo_agent_instantiated(context: dict[str, Any]) -> None:
    """先 5-1 用例真实 instantiate 产出 agent，再手动组装本 Story 档案加载用例。

    - 5-1 实例化：resolve("agent_config_loader")（SINGLETON、构造零连接安全）+
      手动仓储（场景级客户端 RedisAdapter 组合注入）+ InMemoryEventBus——
      禁 resolve("agent_repository") / 用例端口（SCOPED 钉住全局 Resolver 跨循环死连接）
    - 5-2 加载用例：resolve("agent_profile_loader") + resolve("skill_selector")
      （均本地静态文件只读、无连接构造，跨循环安全）+ 同一手动仓储 + 新 InMemoryEventBus
      （事件捕获锚点）+ LoadAgentProfileUseCase 手动实例化
    """
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository

    repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=context["_redis_client"]))
    context["repository"] = repository

    instantiate_use_case = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=repository,
        event_publisher=InMemoryEventBus(),
    )
    instantiation = _run_async(context["_loop"], instantiate_use_case.execute(role=AgentRole.CEO))
    context["_agent_ids"].append(instantiation.agent_id)
    context["agent_id"] = instantiation.agent_id
    assert instantiation.agent.status == AgentStatus.IDLE, "前置 Agent 应为 IDLE 状态"

    from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase

    context["event_bus"] = InMemoryEventBus()
    context["use_case"] = LoadAgentProfileUseCase(
        profile_loader=resolve("agent_profile_loader"),
        repository=repository,
        skill_selector=resolve("skill_selector"),
        event_publisher=context["event_bus"],
    )


@given("随机 agent_id 在仓储中不存在")
def given_random_agent_id_absent(context: dict[str, Any]) -> None:
    """组装用例（真实仓储 + 无连接端口）并生成随机 uuid（键本应查无——验证 443 守卫）。

    无需 instantiate：随机 agent_id 在仓储中必然不存在（uuid4 碰撞概率可忽略）。
    """
    from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository

    context["repository"] = RedisAgentRepository(adapter=RedisAdapter(redis_client=context["_redis_client"]))
    context["use_case"] = LoadAgentProfileUseCase(
        profile_loader=resolve("agent_profile_loader"),
        repository=context["repository"],
        skill_selector=resolve("skill_selector"),
        event_publisher=InMemoryEventBus(),
    )
    context["random_agent_id"] = uuid.uuid4()


# ===================================================================
# AC-1: 加载 CEO Agent 七档案
# ===================================================================


@when("执行 Agent 档案加载用例")
def when_execute_load_profile(context: dict[str, Any]) -> None:
    """执行档案加载用例（agent_id 取实例化产出或随机 uuid），结果/异常分别记录。"""
    agent_id = context.get("agent_id") or context.get("random_agent_id")
    context["result"] = None
    context["error"] = None
    try:
        context["result"] = _run_async(context["_loop"], context["use_case"].execute(agent_id=agent_id))
    except Exception as exc:  # BDD 异常断言统一入口（isinstance + code 在 Then 步骤校验）
        context["error"] = exc


@then("六档案内容加载完整且含 CEO 语义锚点")
def then_six_profiles_loaded_with_ceo_anchor(context: dict[str, Any]) -> None:
    """断言 AgentProfile 六档案字段全非空且 IDENTITY 含「CEO」语义锚点。"""
    result = context["result"]
    assert result is not None, f"档案加载失败: {context['error']!r}"
    profile = result.profile
    for field_name in ("identity", "code_of_conduct", "soul", "user_preferences", "memory", "heartbeat"):
        content = getattr(profile, field_name)
        assert isinstance(content, str) and content.strip(), f"档案字段 {field_name} 应为非空字符串"
    assert "CEO" in profile.identity, "IDENTITY 档案应含 CEO 角色语义锚点"


@then("L1 工具元数据清单包含 23 个 ACTIVE 工具")
def then_tools_l1_contains_23_active(context: dict[str, Any]) -> None:
    """断言 tools_l1 条目数 23 且全部 status=="active"（Skills 资产 tripwire）。"""
    result = context["result"]
    tools = result.tools_l1
    assert len(tools) == 23, f"期望 23 个 L1 工具，实际 {len(tools)}（Skills 资产演进需同步更新断言）"
    assert all(meta.status == "active" for meta in tools), "L1 清单应仅含 active 条目"


@then("返回结果包含档案、工具清单与 token 计量")
def then_result_contains_profile_tools_tokens(context: dict[str, Any]) -> None:
    """断言结果 DTO 三段：profile / tools_l1（tuple）/ startup_context_tokens（int>0）。"""
    from src.domain.value_objects.agent_profile import AgentProfile

    result = context["result"]
    assert isinstance(result.profile, AgentProfile), "profile 应为 AgentProfile 领域值对象"
    assert isinstance(result.tools_l1, tuple), "tools_l1 应为 tuple"
    assert isinstance(result.startup_context_tokens, int) and result.startup_context_tokens > 0
    assert result.agent_id == context["agent_id"]
    assert result.role == AgentRole.CEO


@given("临时档案目录缺失 IDENTITY.md 文件")
def given_profile_dir_missing_identity(context: dict[str, Any], tmp_path: Path) -> None:
    """tmp_path 构造完整六档案后删除 IDENTITY.md（文件缺失路径，真实文件 IO 零 mock）。"""
    profile_dir = tmp_path / "ceo"
    profile_dir.mkdir()
    for file_name in PROFILE_FILE_NAMES:
        (profile_dir / file_name).write_text(f"# {file_name} 测试档案内容\n", encoding="utf-8")
    (profile_dir / "IDENTITY.md").unlink()

    from src.infrastructure.agent_orch.markdown_agent_profile_loader import MarkdownAgentProfileLoader

    context["loader"] = MarkdownAgentProfileLoader(profile_root=tmp_path)


@when("通过档案加载端口加载 CEO 档案")
def when_load_via_profile_port(context: dict[str, Any]) -> None:
    """经档案加载端口直连加载（场景注入的 tmp_path 加载器），结果/异常分别记录。"""
    context["profile"] = None
    context["error"] = None
    try:
        context["profile"] = _run_async(context["_loop"], context["loader"].load(role=AgentRole.CEO, agent_id=uuid.uuid4()))
    except Exception as exc:
        context["error"] = exc


@then("抛出 AgentProfileError")
def then_raise_agent_profile_error(context: dict[str, Any]) -> None:
    """断言异常类型（442 覆盖七类成因——同码多因靠 context 区分断言）。"""
    from src.domain.exceptions import AgentProfileError

    error = context["error"]
    assert isinstance(error, AgentProfileError), f"期望 AgentProfileError，实际: {error!r}"


@then("错误码为 EXCEPTION_442")
def then_error_code_442(context: dict[str, Any]) -> None:
    """断言错误码与消息非空。"""
    error = context["error"]
    assert error is not None, "未捕获到异常"
    assert error.code == "EXCEPTION_442", f"期望 EXCEPTION_442，实际 {error.code}"
    assert error.message, "异常消息不能为空"


@then("错误上下文携带缺失文件名")
def then_context_contains_missing_file(context: dict[str, Any]) -> None:
    """断言 context.profile_path 含缺失文件名（判空/缺文件主检在加载器的观测锚点）。"""
    error = context["error"]
    profile_path = error.context.get("profile_path", "")
    assert "IDENTITY.md" in profile_path, f"context.profile_path 应含缺失文件名，实际: {profile_path!r}"


@given("临时档案目录六档案内容全部空白")
def given_profile_dir_all_blank(context: dict[str, Any], tmp_path: Path) -> None:
    """tmp_path/ceo/ 角色子目录构造六份空白档案（空串/纯空白/纯换行三形态轮转）。

    子目录层级对齐寻址契约 profile_root / role.value / 固定名——写 tmp_path 根级
    会报「目录缺失」442 假绿（Round 3 审查 #21）。
    """
    profile_dir = tmp_path / "ceo"
    profile_dir.mkdir()
    blank_forms = ("", "   \t  ", "\n\n\n")
    for index, file_name in enumerate(PROFILE_FILE_NAMES):
        (profile_dir / file_name).write_text(blank_forms[index % len(blank_forms)], encoding="utf-8")

    from src.infrastructure.agent_orch.markdown_agent_profile_loader import MarkdownAgentProfileLoader

    context["loader"] = MarkdownAgentProfileLoader(profile_root=tmp_path)


@then("错误上下文携带空白文件名与原因")
def then_context_contains_blank_file_and_reason(context: dict[str, Any]) -> None:
    """断言 442 的 context 区分力：profile_path 含首个空白文件名 + reason 含空白语义。"""
    error = context["error"]
    profile_path = error.context.get("profile_path", "")
    reason = error.context.get("reason", "")
    assert "IDENTITY.md" in profile_path, f"profile_path 应含空白文件名（固定加载序首个），实际: {profile_path!r}"
    assert "空白" in reason, f"reason 应含空白语义（同码多因区分），实际: {reason!r}"


# ===================================================================
# AC-2: 档案验证与存在性守卫
# ===================================================================


@when("通过档案加载端口加载内置 CEO 档案")
def when_load_builtin_ceo_profiles(context: dict[str, Any]) -> None:
    """经组合根 resolve 加载内置 configs/agents/profiles/ceo/ 档案（默认 profile_root）。"""
    from src.domain.ports.resolver import resolve

    loader = resolve("agent_profile_loader")
    context["profile"] = None
    context["error"] = None
    try:
        context["profile"] = _run_async(context["_loop"], loader.load(role=AgentRole.CEO, agent_id=uuid.uuid4()))
    except Exception as exc:
        context["error"] = exc


@then("六档案内容验证全部通过")
def then_six_profiles_validation_passed(context: dict[str, Any]) -> None:
    """断言内置六档案加载成功且 VO 自校验通过（strip 非空全字段）。"""
    profile = context["profile"]
    assert profile is not None, f"内置档案加载失败: {context['error']!r}"
    for field_name in ("identity", "code_of_conduct", "soul", "user_preferences", "memory", "heartbeat"):
        content = getattr(profile, field_name)
        assert isinstance(content, str) and content.strip(), f"{field_name} 验证未通过"


@then("IDENTITY 档案含 CEO 语义锚点")
def then_identity_contains_ceo_anchor(context: dict[str, Any]) -> None:
    """断言 IDENTITY 档案含角色名 CEO（资产语义红线）。"""
    assert "CEO" in context["profile"].identity, "IDENTITY 应含角色名 CEO"


@then("单档案大小不超过 64KB 上限")
def then_each_profile_file_under_64kb(context: dict[str, Any]) -> None:
    """断言内置六物理文件字节大小均 ≤65536（PROFILE_FILE_MAX_BYTES 字节口径）。"""
    profile_dir = REPO_ROOT / "configs" / "agents" / "profiles" / "ceo"
    for file_name in PROFILE_FILE_NAMES:
        size = (profile_dir / file_name).stat().st_size
        assert size <= 65536, f"{file_name} 超限: {size} 字节 > 65536"


@then("抛出 AgentNotFoundError")
def then_raise_agent_not_found(context: dict[str, Any]) -> None:
    """断言异常类型（443 存在性守卫）。"""
    from src.domain.exceptions import AgentNotFoundError

    error = context["error"]
    assert isinstance(error, AgentNotFoundError), f"期望 AgentNotFoundError，实际: {error!r}"


@then("错误码为 EXCEPTION_443")
def then_error_code_443(context: dict[str, Any]) -> None:
    """断言错误码与消息非空。"""
    error = context["error"]
    assert error is not None, "未捕获到异常"
    assert error.code == "EXCEPTION_443", f"期望 EXCEPTION_443，实际 {error.code}"
    assert error.message, "异常消息不能为空"


@then("错误上下文携带 agent_id")
def then_context_contains_agent_id(context: dict[str, Any]) -> None:
    """断言 context.agent_id == str(随机 id)（raise 侧 str 形态，对齐 5-1 role=role.value 先例）。"""
    error = context["error"]
    assert error.context.get("agent_id") == str(context["random_agent_id"]), (
        f"context.agent_id 应为 {str(context['random_agent_id'])}，实际: {error.context.get('agent_id')!r}"
    )


@given("临时档案目录单档案超过 64KB 上限")
def given_profile_dir_oversized_file(context: dict[str, Any], tmp_path: Path) -> None:
    """tmp_path/ceo/ 子目录构造 >65536 字节档案（ASCII 65537 字节即稳，字节口径）。"""
    profile_dir = tmp_path / "ceo"
    profile_dir.mkdir()
    for file_name in PROFILE_FILE_NAMES:
        if file_name == "CODE.md":
            (profile_dir / file_name).write_bytes(b"x" * 65537)
        else:
            (profile_dir / file_name).write_text(f"# {file_name} 测试档案内容\n", encoding="utf-8")

    from src.infrastructure.agent_orch.markdown_agent_profile_loader import MarkdownAgentProfileLoader

    context["loader"] = MarkdownAgentProfileLoader(profile_root=tmp_path)


@then("错误上下文携带超限文件名")
def then_context_contains_oversized_file(context: dict[str, Any]) -> None:
    """断言 context.profile_path 含超限文件名（CODE.md）。"""
    error = context["error"]
    profile_path = error.context.get("profile_path", "")
    assert "CODE.md" in profile_path, f"profile_path 应含超限文件名，实际: {profile_path!r}"


# ===================================================================
# AC-3: Skills L1 元数据与 SkillSelector
# ===================================================================


@when("通过技能加载端口查询 L1 元数据")
def when_query_l1_metadata(context: dict[str, Any]) -> None:
    """经组合根 resolve("skill_loader") 逐 slug 查询 L1 元数据（本地文件只读无连接）。

    步骤内联现算拼接视图——tripwire 性质（保护既有 Skills 资产，23 条/~218 tokens
    恒满足），Task 0 即绿属预期（故事文件 AC-3.1 红绿形态注记）。
    """
    from src.application.skills.skill_manifest import get_all_slugs
    from src.domain.ports.resolver import resolve

    skill_loader = resolve("skill_loader")
    context["error"] = None
    try:
        tools = []
        for slug in get_all_slugs():
            tools.append(_run_async(context["_loop"], skill_loader.load_metadata(slug)))
        context["l1_tools"] = tools
    except Exception as exc:
        context["error"] = exc


@then("L1 元数据清单包含 23 个 ACTIVE 工具")
def then_l1_metadata_23_active(context: dict[str, Any]) -> None:
    """断言直查 L1 元数据 23 条且全部 active（Skills 资产 tripwire——与 AC-1.1 用例口径互补）。"""
    assert context["error"] is None, f"L1 元数据查询失败: {context['error']!r}"
    tools = context["l1_tools"]
    assert len(tools) == 23, f"期望 23 条 L1 元数据，实际 {len(tools)}（Skills 资产演进需同步更新断言）"
    assert all(meta.status == "active" for meta in tools)


@then("L1 拼接视图 token 计量不超过 1200")
def then_l1_view_tokens_within_budget(context: dict[str, Any]) -> None:
    """断言用例拼接视图（tool_name: description 换行拼接，chars//4 口径）≤1200 tokens。

    断言对象 = 用例计量口径（AC-3 口径②，TOOLS.md 内容子集实测 ~218）；
    1104 为 TOOLS.md 文件全文口径参照值，非本断言对象（DC-3 两口径分述）。
    """
    tools = context["l1_tools"]
    view_text = "\n".join(f"{meta.tool_name}: {meta.description}" for meta in tools)
    tokens = len(view_text) // 4
    assert tokens <= 1200, f"L1 拼接视图计量 {tokens} tokens 超出 1200 预算"


@when("调用 SkillSelector 查询活跃技能")
def when_call_skill_selector(context: dict[str, Any]) -> None:
    """resolve("skill_selector")（无连接构造）调用 list_active_skills()。"""
    from src.domain.ports.resolver import resolve

    selector = resolve("skill_selector")
    context["error"] = None
    try:
        context["active_skills"] = _run_async(context["_loop"], selector.list_active_skills())
    except Exception as exc:
        context["error"] = exc


@then("活跃技能清单包含 23 个条目且全部为 active")
def then_active_skills_23_all_active(context: dict[str, Any]) -> None:
    """断言条目数 23 + 全部 status=="active"（GAP-CRITICAL-08b 纯过滤交付形态）。"""
    skills = context["active_skills"]
    assert len(skills) == 23, f"期望 23 个活跃技能，实际 {len(skills)}（Skills 资产演进需同步更新断言）"
    assert all(meta.status == "active" for meta in skills)


@then("返回顺序与 slug 清单一致")
def then_order_matches_slug_manifest(context: dict[str, Any]) -> None:
    """断言零排序副作用：返回顺序与 get_all_slugs() 清单一致（稳定序）。"""
    from src.application.skills.skill_manifest import get_all_slugs

    returned_slugs = [meta.slug for meta in context["active_skills"]]
    assert returned_slugs == get_all_slugs(), "SkillSelector 返回顺序应与 slug 清单一致（零排序副作用）"


# ===================================================================
# AC-4: 启动上下文 token 预算与 AgentProfileLoaded 事件
# ===================================================================


@then("启动上下文 token 预算符合约束")
def then_startup_context_budget(context: dict[str, Any]) -> None:
    """断言分项与总量预算（分项由测试从 result 按 chars//4 同款口径现算——DTO 无分项字段）。

    - IDENTITY+SOUL ≤500 tokens（资产编写红线，Task 2 落实）
    - 总量 result.startup_context_tokens ≤1700（IDENTITY+SOUL+L1 拼接后一次 //4 计量）
    - 取整差注记：总量为拼接后一次计量，与分项之和存在 ≤1 取整差
    """
    result = context["result"]
    profile = result.profile
    identity_soul_tokens = (len(profile.identity) + len(profile.soul)) // 4
    assert identity_soul_tokens <= 500, f"IDENTITY+SOUL 分项 {identity_soul_tokens} tokens 超出 500 预算"
    assert result.startup_context_tokens <= 1700, f"启动上下文总量 {result.startup_context_tokens} tokens 超出 1700 预算"
    # 总量与分项同源口径一致性（拼接后一次计量 ≥ 分项之和 - 1 取整差）
    l1_view = "\n".join(f"{meta.tool_name}: {meta.description}" for meta in result.tools_l1)
    expected_total = (len(profile.identity) + len(profile.soul) + len(l1_view)) // 4
    assert result.startup_context_tokens == expected_total, (
        f"总量计量应等于拼接后一次 //4 计量 {expected_total}，实际 {result.startup_context_tokens}"
    )


@then("已发布 AgentProfileLoaded 事件且字段正确")
def then_agent_profile_loaded_event(context: dict[str, Any]) -> None:
    """断言真实 InMemoryEventBus 捕获事件且四字段正确（active_skill_count 同源派生）。"""
    from src.domain.events.agent_events import AgentProfileLoaded

    events = [e for e in context["event_bus"].published_events if isinstance(e, AgentProfileLoaded)]
    assert events, "未发布 AgentProfileLoaded 事件（发布点断线——Epic 4 零发布教训防线）"
    event = events[-1]
    result = context["result"]
    assert event.agent_id == result.agent_id
    assert event.role == AgentRole.CEO.value
    assert event.startup_context_tokens == result.startup_context_tokens
    assert event.active_skill_count == len(result.tools_l1), "active_skill_count 应与 DTO 同源派生"
    assert event.aggregate_type == "Agent"
    assert event.aggregate_id == result.agent_id


# ===================================================================
# AC-5: 性能指标
# ===================================================================


@when("执行档案加载全链路采样（1 次 warmup 与 20 次计时）")
def when_measure_load_latency(context: dict[str, Any]) -> None:
    """warmup 剔除 1 次后 20 次计时采样，P95 经 statistics.quantiles(n=20)[18] 计算。

    同一 agent_id 复用（load-profile 幂等只读，无新键产生——teardown 零增量）。
    """
    use_case = context["use_case"]
    agent_id = context["agent_id"]
    _run_async(context["_loop"], use_case.execute(agent_id=agent_id))  # warmup
    latencies = []
    for _ in range(20):
        started = time.perf_counter()
        _run_async(context["_loop"], use_case.execute(agent_id=agent_id))
        latencies.append((time.perf_counter() - started) * 1000)  # ms
    context["latencies_ms"] = latencies
    context["p95_ms"] = statistics.quantiles(latencies, n=20)[18]


@then("档案加载延迟 P95 小于 500 毫秒")
def then_p95_under_500ms(context: dict[str, Any]) -> None:
    """断言 P95 < 500ms（对典型 <20ms 链路约 25 倍余量）。"""
    assert context["p95_ms"] < 500, f"P95 {context['p95_ms']:.1f}ms 应小于 500ms"


@when("同一 agent_id 连续执行 20 次档案加载")
def when_load_20_times_same_agent(context: dict[str, Any]) -> None:
    """同一 agent_id 20 次重复加载（幂等只读设计行为——确定性文件 IO + L1 内存缓存命中）。"""
    results = []
    for _ in range(20):
        results.append(_run_async(context["_loop"], context["use_case"].execute(agent_id=context["agent_id"])))
    context["results"] = results


@then("20 次加载全部成功")
def then_20_loads_all_succeed(context: dict[str, Any]) -> None:
    """断言计数 == 20 全成功且 agent_id 一致（幂等只读）。"""
    results = context["results"]
    assert len(results) == 20
    assert all(result is not None for result in results), "20 次重复加载应全部成功（无随机失败面）"
    assert all(result.agent_id == context["agent_id"] for result in results)


# ===================================================================
# AC-6: 端口接线、事件双登记与 CLI 注册
# ===================================================================


@then("三个新端口 resolve 可达且实例类型合规")
def then_three_ports_resolvable(context: dict[str, Any]) -> None:
    """AC-6.1 接线断言：三端口 resolve 可达 + isinstance 合规（禁对产物发命令）。"""
    from src.application.ports.agent_profile_loader import AgentProfileLoader
    from src.application.ports.skill_selector import SkillSelectorPort
    from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase
    from src.domain.ports.resolver import resolve

    assert isinstance(resolve("agent_profile_loader"), AgentProfileLoader), "agent_profile_loader 接线失败"
    assert isinstance(resolve("skill_selector"), SkillSelectorPort), "skill_selector 接线失败"
    assert isinstance(resolve("agent_profile_use_case"), LoadAgentProfileUseCase), "agent_profile_use_case 接线失败"


@then("AgentProfileLoaded 事件通道双登记可达")
def then_event_dual_registration(context: dict[str, Any]) -> None:
    """断言 event_channels.yaml 与 ChannelRouter.DEFAULT_MAPPINGS 两处登记（两处 grep 可达）。"""
    yaml_text = (REPO_ROOT / "configs" / "event_channels.yaml").read_text(encoding="utf-8")
    assert "AgentProfileLoaded:" in yaml_text, "event_channels.yaml 未登记 AgentProfileLoaded"
    assert "sisys.events.reliable.agent_profile_loaded" in yaml_text, "routing key 未登记"

    from src.infrastructure.messaging.channel_router import ChannelRouter

    mapping = ChannelRouter.DEFAULT_MAPPINGS.get("AgentProfileLoaded")
    assert mapping is not None, "DEFAULT_MAPPINGS 未登记 AgentProfileLoaded"
    assert mapping.rabbitmq_routing_key == "sisys.events.reliable.agent_profile_loaded"


@then("CLI load-profile 子命令注册可达")
def then_cli_load_profile_registered(context: dict[str, Any]) -> None:
    """断言 pyproject sisys-agent script 注册 + agent_cli 源码含 load-profile 子命令。

    script 已注册（5-1 交付）——断言为防误删 tripwire，当前恒真属预期；
    load-profile 子命令为 Story 5-2 新增接线（Task 5 转绿）。
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'sisys-agent = "src.entrypoints.agent_cli:main"' in pyproject, "pyproject 未注册 sisys-agent"
    cli_source = (REPO_ROOT / "src" / "entrypoints" / "agent_cli.py").read_text(encoding="utf-8")
    assert "load-profile" in cli_source, "agent_cli 未注册 load-profile 子命令"
    assert "--agent-id" in cli_source, "load-profile 应声明 --agent-id 必填参数"


@then("src 与 tests 完成清单逐项存在")
def then_completion_checklist(context: dict[str, Any]) -> None:
    """AC-6.3 收尾：src 产出 + tests 测试文件 + 六档案资产逐项存在性断言（Task 0 落盘，Task 8 转绿核对）。"""
    checklist = [
        # src 产出（领域层 3 + 应用层 5 + 基础设施 1 + 入口 1）
        "src/domain/value_objects/agent_profile.py",
        "src/domain/events/agent_events.py",
        "src/domain/exceptions/agent_exceptions.py",
        "src/application/ports/agent_profile_loader.py",
        "src/application/ports/skill_selector.py",
        "src/application/skills/registry/__init__.py",
        "src/application/skills/registry/selector.py",
        "src/application/use_cases/agent_profile_loading.py",
        "src/infrastructure/agent_orch/markdown_agent_profile_loader.py",
        "src/entrypoints/agent_cli.py",
        # 六档案资产（IDENTITY+SOUL 合计 ≤500 tokens 红线在 AC-4.1 分项断言）
        "configs/agents/profiles/ceo/IDENTITY.md",
        "configs/agents/profiles/ceo/CODE.md",
        "configs/agents/profiles/ceo/SOUL.md",
        "configs/agents/profiles/ceo/USER.md",
        "configs/agents/profiles/ceo/MEMORY.md",
        "configs/agents/profiles/ceo/HEARTBEAT.md",
        # tests 产出（unit 8 + contracts 3 + integration 1 + acceptance 2）
        "tests/unit/domain/events/test_agent_events.py",
        "tests/unit/domain/exceptions/test_agent_exceptions.py",
        "tests/unit/domain/value_objects/test_agent_profile.py",
        "tests/unit/application/skills/test_skill_selector.py",
        "tests/unit/application/use_cases/test_agent_profile_loading.py",
        "tests/unit/infrastructure/agent_orch/test_markdown_agent_profile_loader.py",
        "tests/unit/interfaces/cli/test_agent_cli.py",
        "tests/unit/architecture/test_arch_agent_profile_loading.py",
        "tests/contracts/test_port_contract_agent_profile_loader.py",
        "tests/contracts/test_port_contract_skill_selector.py",
        "tests/contracts/test_port_contract_agent_profile_use_case.py",
        "tests/integration/test_integration_agent_profile_loading.py",
    ]
    for rel in checklist:
        assert (REPO_ROOT / rel).exists(), f"完成清单缺失: {rel}"

    # 组合根三端口注册 grep 断言
    composition = (REPO_ROOT / "src" / "composition_root.py").read_text(encoding="utf-8")
    for port_name in ('"agent_profile_loader"', '"skill_selector"', '"agent_profile_use_case"'):
        assert port_name in composition, f"组合根未注册 {port_name}"


@then("链路接线断言清单 L1-L8 终态符合预期")
def then_wiring_checklist_final(context: dict[str, Any]) -> None:
    """AC-6.3 收尾：L1-L6 接线绿灯实证 + L7/L8 deferred-work.md 登记仍在且未误删。"""
    # L1-L3: 三端口注册可达
    from src.domain.ports.registry import _global_registry

    for port_name in ("agent_profile_loader", "skill_selector", "agent_profile_use_case"):
        assert _global_registry.get(port_name) is not None, f"L1-L3 接线失败: {port_name}"

    # L4: 事件双登记
    yaml_text = (REPO_ROOT / "configs" / "event_channels.yaml").read_text(encoding="utf-8")
    assert "AgentProfileLoaded:" in yaml_text, "L4 事件 yaml 登记缺失"
    from src.infrastructure.messaging.channel_router import ChannelRouter

    assert "AgentProfileLoaded" in ChannelRouter.DEFAULT_MAPPINGS, "L4 事件 DEFAULT_MAPPINGS 登记缺失"

    # L5: CLI 入口注册 + load-profile 子命令
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "sisys-agent" in pyproject, "L5 CLI script 注册缺失"
    cli_source = (REPO_ROOT / "src" / "entrypoints" / "agent_cli.py").read_text(encoding="utf-8")
    assert "load-profile" in cli_source, "L5 load-profile 子命令缺失"

    # L6: skill_loader 新消费方接线（SkillSelector 组合注入）
    selector_source = (REPO_ROOT / "src" / "application" / "skills" / "registry" / "selector.py").read_text(encoding="utf-8")
    assert "SkillLoaderPort" in selector_source, "L6 SkillSelector 应组合注入 skill_loader 端口"

    # L7/L8: deferred 登记仍在（心跳链路 + 记忆链路 + 本 Story 补登记的 impl 路径失效观察项）
    deferred = (REPO_ROOT / "_bmad-output" / "implementation-artifacts" / "deferred-work.md").read_text(encoding="utf-8")
    assert "heartbeat_scheduler" in deferred, "L7 心跳链路 deferred 登记缺失"
    assert "L0/memory" in deferred, "L8 记忆链路 deferred 登记缺失"
    assert "l0_storage" in deferred and "fs/file_memory_adapter" in deferred, "L8 组合根 impl 路径失效观察项登记缺失"
