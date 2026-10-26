"""Story 5-1 — CEO Agent 实例化 MVP 验收测试（BDD 场景步骤实现）。

结构范本：test_acceptance_skill_data_collection.py（FEATURE 常量 + @scenario 显式绑定 +
context dict + 场景级独立 Redis 客户端 + _run_async 同循环调度 + Background 动态 skip）；
场景命名与断言风格：test_acceptance_data_source.py（AC 编号场景名 + error.code 断言）。

新模块延迟 import 纪律：本 Story 交付的模块（agent_exceptions / agent_config /
agent_config_loader / redis_agent_repository / agent_instantiation）一律在步骤函数体内
延迟 import——模块顶部 import 会使 pytest 收集期整文件 collection error，已实现/未实现
场景一起炸，无法逐 Task 转绿（先例 test_acceptance_strategic_archive.py L107-108）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_agent_instantiation.py -v

测试隔离:
    - Redis 键 build_key("agent", str(agent_id)) 无租户维度——agent_id uuid4 天然唯一即隔离
    - teardown 仅精确删除本场景记录的 agent_id 键（禁 delete_pattern/flush——多 worker
      共享 6380 实例会误删并行场景正使用的键）
    - 场景级独立 Redis 客户端 + 同循环关闭（跨循环 "Event loop is closed" 存档教训）
    - BDD 步骤禁 @pytest.mark.asyncio（context 数据丢失），统一 _run_async 调度
    - 验收禁调用 bootstrap()（session 级 _bootstrap_once 已引导，同进程二次调用因
      lambda 工厂 spec 不幂等必抛 ConflictError）
    - 功能场景禁 resolve("agent_repository") / resolve("agent_instantiation_use_case")
      发命令（SCOPED/SINGLETON 实例钉住全局 Resolver，其 SINGLETON redis_client 跨
      function-scope 循环复用必抛 "Event loop is closed"）——仓储一律场景级手动组装；
      resolve 仅做 AC-6.1 接线断言且禁对产物发命令
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
from pytest_bdd import given, parsers, scenario, then, when

from src.domain.entities.agent import AgentRole, AgentStatus
from src.infrastructure.storage.redis.key_builder import build_key

FEATURE = "test_acceptance_agent_instantiation.feature"

# 仓库根锚定（AC-6.2 完成清单断言用，不依赖 cwd）
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# 文件名不含服务关键词，acceptance conftest 不会自动添加 marker——显式声明；
# xdist_group 使本文件全部场景（含 AC-5.1 计时）在同一 worker 串行执行
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.redis,
    pytest.mark.xdist_group("agent-instantiation"),
]


# ===================================================================
# 场景绑定（13 个，场景名从 .feature 复制粘贴——ASCII 连字符 + 两侧空格）
# ===================================================================


@scenario(FEATURE, "AC-1.1 - 实例化 CEO Agent 成功")
def test_ac_1_1_instantiate_ceo_success(context: dict[str, Any]) -> None:
    """AC-1.1: 实例化返回 agent_id 且实体为 CEO/IDLE。"""


@scenario(FEATURE, "AC-1.2 - 实例化未开放角色抛异常")
def test_ac_1_2_unsupported_role_rejected(context: dict[str, Any]) -> None:
    """AC-1.2: 非 CEO 角色 → AgentRoleNotSupportedError(441)。"""


@scenario(FEATURE, "AC-1.3 - 两次实例化相互独立")
def test_ac_1_3_two_instantiations_independent(context: dict[str, Any]) -> None:
    """AC-1.3: 两次实例化 agent_id 不同、键不互相覆盖。"""


@scenario(FEATURE, "AC-2.1 - 加载 CEO 基础配置成功")
def test_ac_2_1_load_ceo_config_success(context: dict[str, Any]) -> None:
    """AC-2.1: 内置 ceo_agent.yaml 经端口加载字段映射完整。"""


@scenario(FEATURE, "AC-2.2 - 配置文件缺失抛异常")
def test_ac_2_2_config_file_missing(context: dict[str, Any]) -> None:
    """AC-2.2: 配置文件缺失 → AgentConfigError(440)。"""


@scenario(FEATURE, "AC-2.3 - 配置字段无效抛异常")
def test_ac_2_3_config_role_mismatch(context: dict[str, Any]) -> None:
    """AC-2.3: role 与配置不匹配 → AgentConfigError(440)。"""


@scenario(FEATURE, "AC-3.1 - Agent 状态持久化并可读回")
def test_ac_3_1_state_persisted_and_restorable(context: dict[str, Any]) -> None:
    """AC-3.1: 键存在 + TTL>0 + 实体全字段读回一致。"""


@scenario(FEATURE, "AC-4.1 - 实例化发布 AgentInstantiated 事件")
def test_ac_4_1_agent_instantiated_event_published(context: dict[str, Any]) -> None:
    """AC-4.1: 真实 InMemoryEventBus 捕获 AgentInstantiated 且字段正确。"""


@scenario(FEATURE, "AC-4.2 - 事件通道双登记")
def test_ac_4_2_event_channel_dual_registration(context: dict[str, Any]) -> None:
    """AC-4.2: event_channels.yaml 与 DEFAULT_MAPPINGS 双登记可达。"""


@scenario(FEATURE, "AC-5.1 - 实例化延迟 P95 小于 200 毫秒")
def test_ac_5_1_p95_under_200ms(context: dict[str, Any]) -> None:
    """AC-5.1: 真实 Redis ≥20 采样 P95<200ms（warmup 剔除 1 次）。"""


@scenario(FEATURE, "AC-5.2 - 十个并发实例化全部成功")
def test_ac_5_2_ten_concurrent_instantiations(context: dict[str, Any]) -> None:
    """AC-5.2: asyncio.gather 10 并发全成功 + agent_id 互异（禁 scan 计数）。"""


@scenario(FEATURE, "AC-6.1 - 三端口接线可达")
def test_ac_6_1_three_ports_resolvable(context: dict[str, Any]) -> None:
    """AC-6.1: 三端口 resolve 可达 + isinstance 合规（禁对产物发命令）。"""


@scenario(FEATURE, "AC-6.2 - 完成清单逐项确认")
def test_ac_6_2_completion_checklist(context: dict[str, Any]) -> None:
    """AC-6.2: src/tests 完成清单 + L1-L8 接线终态（Task 8 收尾转绿）。"""


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
    agent_id 对应键——build_key 产出 sisys:agent:{uuid} 无租户维度，TestTenant
    前缀无存储层叠加机制，通配删除会误删并行 worker 正使用的键。
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
        for namespace in ("agent", "isolation"):
            _run_async(event_loop, redis_client.delete(build_key(namespace, str(agent_id))))
    _run_async(event_loop, redis_client.close())


def _run_async(event_loop: asyncio.AbstractEventLoop, coro: Coroutine[Any, Any, Any]) -> Any:
    """在场景级共享事件循环上同步调度协程。

    BDD 步骤函数禁止 @pytest.mark.asyncio（context 数据丢失）；
    aioredis/asyncio.Lock 等对象在首次使用时绑定事件循环，
    必须复用同一循环，否则抛 "Event loop is closed" 跨循环错误。
    """
    return event_loop.run_until_complete(coro)


class _StubIsolationSwitchLogRepository:
    """手写 duck-typing 日志仓储替身（直接实现 IsolationSwitchLogRepository 端口
    契约——Story 5.6 回归面：5-1 验收断言锚是实例化链路，日志仓储以零 IO
    替身注入保持原断言语义；真实 PG 日志链归 5.6 验收文件）。"""

    def __init__(self) -> None:
        self.saved_logs: list[Any] = []

    async def save(self, log: Any) -> None:
        self.saved_logs.append(log)

    async def search(self, query: Any) -> Any:
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogSearchResult

        return IsolationSwitchLogSearchResult(items=(), total=0, offset=query.offset, limit=query.limit)


# ===================================================================
# Background 与服务组装
# ===================================================================


@given("Redis 缓存服务可用")
def given_redis_service_available(context: dict[str, Any]) -> None:
    """验证 Redis 服务可用（不可用时场景整体动态跳过，禁止写死 skip）。"""
    try:
        _run_async(context["_loop"], context["_redis_client"].ping())
    except Exception as exc:
        pytest.skip(f"Redis not available: {exc}")


@given("Agent 协作服务已启动")
def given_agent_service_started(context: dict[str, Any]) -> None:
    """手动组装实例化链路（bootstrap 禁令下不经组合根获取有状态端口）。

    - config_loader 经组合根 resolve（SINGLETON、构造零 IO、无连接安全）
    - 仓储用场景级 Redis 客户端手动组装（RedisAdapter 组合注入——
      skill_data_collection L318 先例；禁 resolve("agent_repository")）
    - 事件总线用真实 InMemoryEventBus 直接构造（验收环境无 RabbitMQ，
      组合根默认 event_publisher 是 DualChannelEventBus 不适用）
    - 用例手动实例化（禁 resolve("agent_instantiation_use_case")——
      其 resolve 产物钉住全局 Resolver，跨场景循环复用必炸）
    """
    # Story 5-4 第四依赖: 真实 IsolationManagementService 手动组装（验收禁 mock
    # ——R3-F04 分派；实例化即 L4 隔离键真实写入，teardown 已双键化清理）
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

    context["event_bus"] = InMemoryEventBus()
    context["repository"] = RedisAgentRepository(adapter=RedisAdapter(redis_client=context["_redis_client"]))
    context["loader"] = resolve("agent_config_loader")
    context["isolation_service"] = IsolationManagementService(
        isolation_repository=RedisIsolationRepository(adapter=RedisAdapter(redis_client=context["_redis_client"])),
        agent_repository=context["repository"],
        event_publisher=InMemoryEventBus(),
        agent_config_loader=context["loader"],
        isolation_switch_log_repository=_StubIsolationSwitchLogRepository(),
        audit_service=None,
    )
    context["use_case"] = InstantiateAgentUseCase(
        config_loader=context["loader"],
        repository=context["repository"],
        event_publisher=context["event_bus"],
        isolation_service=context["isolation_service"],
    )


# ===================================================================
# AC-1: 实例化命令与实体构造
# ===================================================================


@when(parsers.parse("接收 Agent 实例化命令（指定角色 {role}）"))
def when_instantiate_agent(context: dict[str, Any], role: str) -> None:
    """执行实例化用例（合法枚举字符串经 AgentRole 转换），结果/异常分别记录。"""
    context["result"] = None
    context["error"] = None
    try:
        result = _run_async(context["_loop"], context["use_case"].execute(role=AgentRole(role)))
        context["result"] = result
        context["_agent_ids"].append(result.agent_id)
    except Exception as exc:  # BDD 异常断言统一入口（isinstance + code 在 Then 步骤校验）
        context["error"] = exc


@then("实例化返回 agent_id 且实体为 CEO 角色与 IDLE 状态")
def then_instantiation_result(context: dict[str, Any]) -> None:
    """断言结果对象含 UUID agent_id，实体 role=CEO、status=IDLE、name 非空。"""
    result = context["result"]
    assert result is not None, f"实例化失败: {context['error']!r}"
    assert isinstance(result.agent_id, uuid.UUID)
    agent = result.agent
    assert agent.role == AgentRole.CEO
    assert agent.status == AgentStatus.IDLE
    assert agent.name, "name 应来自基础配置注入，非空"


@then("抛出 AgentRoleNotSupportedError")
def then_raise_role_not_supported(context: dict[str, Any]) -> None:
    """断言异常类型且 context 携带 role。"""
    from src.domain.exceptions import AgentRoleNotSupportedError

    error = context["error"]
    assert isinstance(error, AgentRoleNotSupportedError), f"期望 AgentRoleNotSupportedError，实际: {error!r}"
    assert error.context.get("role") is not None, "异常 context 应携带 role"


@then("错误码为 EXCEPTION_441")
def then_error_code_441(context: dict[str, Any]) -> None:
    """断言错误码与消息非空。"""
    error = context["error"]
    assert error is not None, "未捕获到异常"
    assert error.code == "EXCEPTION_441", f"期望 EXCEPTION_441，实际 {error.code}"
    assert error.message, "异常消息不能为空"


@when("连续两次接收 Agent 实例化命令（指定角色 ceo）")
def when_instantiate_twice(context: dict[str, Any]) -> None:
    """两次实例化，结果列表记入 context["results"]。"""
    results = []
    for _ in range(2):
        result = _run_async(context["_loop"], context["use_case"].execute(role=AgentRole.CEO))
        results.append(result)
        context["_agent_ids"].append(result.agent_id)
    context["results"] = results


@then("两次实例化生成两个不同的 agent_id")
def then_two_agent_ids_differ(context: dict[str, Any]) -> None:
    """断言两次实例化的 agent_id 互异。"""
    first, second = context["results"]
    assert first.agent_id != second.agent_id, "两次实例化 agent_id 必须不同"


@then("两个 Agent 状态键各自存在且可读回各自实体")
def then_two_keys_exist_independently(context: dict[str, Any]) -> None:
    """断言两键各自存在（禁 scan 计数）且 get_by_id 各读回自己的实体。"""
    client = context["_redis_client"]
    for result in context["results"]:
        key = build_key("agent", str(result.agent_id))
        assert _run_async(context["_loop"], client.exists(key)) == 1, f"键不存在: {key}"
        agent = _run_async(context["_loop"], context["repository"].get_by_id(result.agent_id))
        assert agent is not None, f"读回失败: {result.agent_id}"
        assert agent.agent_id == result.agent_id


# ===================================================================
# AC-2: 基础配置加载
# ===================================================================


@given("配置目录中不存在请求角色的配置文件")
def given_config_file_missing(context: dict[str, Any], tmp_path: Path) -> None:
    """构造指向空目录的加载器（文件缺失路径，tmp_path 真实目录零 mock）。"""
    from src.infrastructure.agent_orch.yaml_agent_config_loader import YamlAgentConfigLoader

    context["loader"] = YamlAgentConfigLoader(config_dir=tmp_path)


@given("配置文件 identity.role 与请求角色不匹配")
def given_config_role_mismatch(context: dict[str, Any], tmp_path: Path) -> None:
    """写入 role 与请求角色不匹配的真实 YAML 文件（字段无效路径）。"""
    (tmp_path / "ceo_agent.yaml").write_text(
        "agent:\n"
        '  name: "CEO Agent"\n'
        '  version: "1.0.0"\n'
        '  description: "角色不匹配的测试配置"\n'
        "identity:\n"
        '  role: "sys"\n'
        "capabilities:\n"
        '  responsibilities: ["最终决策"]\n'
        '  domain_knowledge: ["战略"]\n'
        "llm_config:\n"
        "  preferred_model: null\n"
        "eip_config:\n"
        '  default_isolation_level: "L4"\n'
        "memory_config:\n"
        "  state_ttl: 86400\n",
        encoding="utf-8",
    )
    from src.infrastructure.agent_orch.yaml_agent_config_loader import YamlAgentConfigLoader

    context["loader"] = YamlAgentConfigLoader(config_dir=tmp_path)


@when("通过配置加载端口加载 CEO Agent 基础配置")
def when_load_ceo_config(context: dict[str, Any]) -> None:
    """经配置加载端口加载（优先用场景注入加载器，否则组合根 resolve），结果/异常分别记录。"""
    from src.domain.ports.resolver import resolve

    loader = context.get("loader") or resolve("agent_config_loader")
    context["config"] = None
    context["error"] = None
    try:
        context["config"] = _run_async(context["_loop"], loader.load(AgentRole.CEO))
    except Exception as exc:
        context["error"] = exc


@then("AgentConfig 字段映射完整")
def then_config_fields(context: dict[str, Any]) -> None:
    """断言 YAML 字段到值对象的完整映射（内置 configs/agents/ceo_agent.yaml）。"""
    config = context["config"]
    assert config is not None, f"配置加载失败: {context['error']!r}"
    assert config.role == AgentRole.CEO
    assert config.name == "CEO Agent"
    assert config.version == "1.0.0"
    assert config.description, "description 非空"
    assert "战略方向" in config.responsibilities
    assert "宏观趋势" in config.domain_knowledge
    assert config.state_ttl == 86400
    assert config.default_isolation_level == "L4"


@then("抛出 AgentConfigError")
def then_raise_agent_config_error(context: dict[str, Any]) -> None:
    """断言异常类型。"""
    from src.domain.exceptions import AgentConfigError

    error = context["error"]
    assert isinstance(error, AgentConfigError), f"期望 AgentConfigError，实际: {error!r}"


@then("错误码为 EXCEPTION_440")
def then_error_code_440(context: dict[str, Any]) -> None:
    """断言错误码与消息非空（消息面向调用方可理解，不泄露内部细节）。"""
    error = context["error"]
    assert error is not None, "未捕获到异常"
    assert error.code == "EXCEPTION_440", f"期望 EXCEPTION_440，实际 {error.code}"
    assert error.message, "异常消息不能为空"


# ===================================================================
# AC-3: Redis 持久化与读回
# ===================================================================


@then("Redis 中 Agent 状态键存在且 TTL 大于 0")
def then_key_exists_ttl_positive(context: dict[str, Any]) -> None:
    """断言键 sisys:agent:{agent_id} 存在且 TTL>0（经场景级同循环客户端）。"""
    result = context["result"]
    key = build_key("agent", str(result.agent_id))
    client = context["_redis_client"]
    assert _run_async(context["_loop"], client.exists(key)) == 1, f"键不存在: {key}"
    assert _run_async(context["_loop"], client.ttl(key)) > 0, "TTL 应大于 0"


@then("读回实体与写入实体字段完全一致")
def then_roundtrip_fields(context: dict[str, Any]) -> None:
    """断言全字段读回一致（UUID/Enum/datetime 显式重建正确，非恒真断言）。"""
    from datetime import datetime

    original = context["result"].agent
    restored = _run_async(context["_loop"], context["repository"].get_by_id(original.agent_id))
    assert restored is not None, "读回结果为 None"
    assert restored.agent_id == original.agent_id
    assert restored.role == original.role
    assert restored.name == original.name
    assert restored.description == original.description
    assert restored.status == original.status
    assert restored.failure_reason == original.failure_reason
    assert restored.domain_knowledge == original.domain_knowledge
    assert restored.responsibilities == original.responsibilities
    assert restored.created_at == original.created_at
    assert restored.updated_at == original.updated_at
    # 类型重建断言（json_loads 不还原类型，仓储必须显式重建）
    assert isinstance(restored.role, AgentRole)
    assert isinstance(restored.status, AgentStatus)
    assert isinstance(restored.created_at, datetime)


# ===================================================================
# AC-4: 领域事件发布与双登记
# ===================================================================


@then("已发布 AgentInstantiated 事件且字段正确")
def then_agent_instantiated_event(context: dict[str, Any]) -> None:
    """断言真实 InMemoryEventBus 捕获事件且 agent_id/role/name/config_version 正确。"""
    from src.domain.events.agent_events import AgentInstantiated

    events = [e for e in context["event_bus"].published_events if isinstance(e, AgentInstantiated)]
    assert events, "未发布 AgentInstantiated 事件（发布点断线——Epic 4 零发布教训防线）"
    event = events[-1]
    result = context["result"]
    assert event.agent_id == result.agent_id
    assert event.role == AgentRole.CEO.value
    assert event.name == result.agent.name
    assert event.config_version == "1.0.0"
    assert event.aggregate_type == "Agent"
    assert event.aggregate_id == result.agent_id


@then("AgentInstantiated 事件通道双登记可达")
def then_event_dual_registration(context: dict[str, Any]) -> None:
    """断言 event_channels.yaml 与 ChannelRouter.DEFAULT_MAPPINGS 两处登记（两处 grep 可达）。"""
    yaml_text = (REPO_ROOT / "configs" / "event_channels.yaml").read_text(encoding="utf-8")
    assert "AgentInstantiated:" in yaml_text, "event_channels.yaml 未登记 AgentInstantiated"
    assert "sisys.events.reliable.agent_instantiated" in yaml_text, "routing key 未登记"

    from src.infrastructure.messaging.channel_router import ChannelRouter

    mapping = ChannelRouter.DEFAULT_MAPPINGS.get("AgentInstantiated")
    assert mapping is not None, "DEFAULT_MAPPINGS 未登记 AgentInstantiated"
    assert mapping.rabbitmq_routing_key == "sisys.events.reliable.agent_instantiated"


# ===================================================================
# AC-5: 性能指标
# ===================================================================


@when("执行实例化全链路采样（1 次 warmup 与 20 次计时）")
def when_measure_latency(context: dict[str, Any]) -> None:
    """warmup 剔除 1 次后 20 次计时采样，P95 经 statistics.quantiles(n=20)[18] 计算。"""
    use_case = context["use_case"]
    warmup = _run_async(context["_loop"], use_case.execute(role=AgentRole.CEO))
    context["_agent_ids"].append(warmup.agent_id)
    latencies = []
    for _ in range(20):
        started = time.perf_counter()
        result = _run_async(context["_loop"], use_case.execute(role=AgentRole.CEO))
        latencies.append((time.perf_counter() - started) * 1000)  # ms
        context["_agent_ids"].append(result.agent_id)
    context["latencies_ms"] = latencies
    context["p95_ms"] = statistics.quantiles(latencies, n=20)[18]


@then("实例化延迟 P95 小于 200 毫秒")
def then_p95_under_200ms(context: dict[str, Any]) -> None:
    """断言 P95 < 200ms（200ms 对典型 <20ms 链路约 10 倍余量）。"""
    assert context["p95_ms"] < 200, f"P95 {context['p95_ms']:.1f}ms 应小于 200ms"


@when("10 个 Agent 并发实例化")
def when_10_concurrent(context: dict[str, Any]) -> None:
    """asyncio.gather 10 并发实例化（NFR-PERF-04 MVP 档）。"""

    async def _instantiate_all() -> list[Any]:
        # 协程内即时登记 agent_id：gather 部分失败时已落库键仍可被 teardown 精确清理
        async def _instantiate_one() -> Any:
            result = await context["use_case"].execute(role=AgentRole.CEO)
            context["_agent_ids"].append(result.agent_id)
            return result

        return await asyncio.gather(*(_instantiate_one() for _ in range(10)))

    results = _run_async(context["_loop"], _instantiate_all())
    context["results"] = results


@then("全部实例化成功且 agent_id 互异")
def then_all_success_distinct(context: dict[str, Any]) -> None:
    """断言 10 个结果全部成功且 agent_id 全互异。"""
    results = context["results"]
    assert len(results) == 10
    ids = [result.agent_id for result in results]
    assert len(set(ids)) == 10, "10 个 agent_id 必须全部互异"


@then("10 个 Agent 状态键逐一存在")
def then_10_keys_exist(context: dict[str, Any]) -> None:
    """对记录的 10 个 agent_id 逐一 exists() 断言（禁 scan 模式计数——多 worker 误计）。"""
    client = context["_redis_client"]
    for agent_id in (result.agent_id for result in context["results"]):
        key = build_key("agent", str(agent_id))
        assert _run_async(context["_loop"], client.exists(key)) == 1, f"键不存在: {key}"


# ===================================================================
# AC-6: 端口接线与完成清单
# ===================================================================


@then("三个新端口 resolve 可达且实例类型合规")
def then_three_ports_resolvable(context: dict[str, Any]) -> None:
    """AC-6.1 接线断言：三端口 resolve 可达 + isinstance 合规（禁对产物发命令）。"""
    from src.application.ports.agent_config_loader import AgentConfigLoader
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.ports.agent_repository import AgentRepository
    from src.domain.ports.resolver import resolve

    assert isinstance(resolve("agent_repository"), AgentRepository), "agent_repository 接线失败"
    assert isinstance(resolve("agent_config_loader"), AgentConfigLoader), "agent_config_loader 接线失败"
    assert isinstance(resolve("agent_instantiation_use_case"), InstantiateAgentUseCase), "agent_instantiation_use_case 接线失败"


@then("src 与 tests 完成清单逐项存在")
def then_completion_checklist(context: dict[str, Any]) -> None:
    """AC-6.2 收尾：src 十处产出 + tests 十二处测试文件逐项存在性断言。"""
    checklist = [
        # src 产出（九处 + 配置资产）
        "src/domain/value_objects/agent_config.py",
        "src/domain/ports/agent_repository.py",
        "src/domain/events/agent_events.py",
        "src/domain/exceptions/agent_exceptions.py",
        "src/application/ports/agent_config_loader.py",
        "src/application/use_cases/agent_instantiation.py",
        "src/infrastructure/agent_orch/yaml_agent_config_loader.py",
        "src/infrastructure/storage/redis/redis_agent_repository.py",
        "src/entrypoints/agent_cli.py",
        "configs/agents/ceo_agent.yaml",
        # tests 产出（unit 8 + contracts 3 + integration 1 + acceptance 2）
        "tests/unit/domain/events/test_agent_events.py",
        "tests/unit/domain/exceptions/test_agent_exceptions.py",
        "tests/unit/domain/value_objects/test_agent_config.py",
        "tests/unit/infrastructure/agent_orch/test_yaml_agent_config_loader.py",
        "tests/unit/infrastructure/storage/redis/test_redis_agent_repository.py",
        "tests/unit/application/use_cases/test_agent_instantiation.py",
        "tests/unit/interfaces/cli/test_agent_cli.py",
        "tests/unit/architecture/test_arch_agent_instantiation.py",
        "tests/contracts/test_port_contract_agent_repository.py",
        "tests/contracts/test_port_contract_agent_config_loader.py",
        "tests/contracts/test_port_contract_agent_instantiation_use_case.py",
        "tests/integration/test_integration_agent_instantiation.py",
    ]
    for rel in checklist:
        assert (REPO_ROOT / rel).exists(), f"完成清单缺失: {rel}"

    # 组合根三端口注册 + CLI script 双注册（接线 grep 断言）
    composition = (REPO_ROOT / "src" / "composition_root.py").read_text(encoding="utf-8")
    for port_name in ('"agent_repository"', '"agent_config_loader"', '"agent_instantiation_use_case"'):
        assert port_name in composition, f"组合根未注册 {port_name}"
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'sisys-agent = "src.entrypoints.agent_cli:main"' in pyproject, "pyproject 未注册 sisys-agent"


@then("链路接线断言清单 L1-L8 终态符合预期")
def then_wiring_checklist_final(context: dict[str, Any]) -> None:
    """AC-6.2 收尾：L1-L5 接线绿灯实证 + L6-L8 deferred-work.md 登记仍在且未误删。"""
    # L1-L3: 三端口注册可达
    from src.domain.ports.registry import _global_registry

    for port_name in ("agent_repository", "agent_config_loader", "agent_instantiation_use_case"):
        assert _global_registry.get(port_name) is not None, f"L1-L3 接线失败: {port_name}"

    # L4: 事件双登记
    yaml_text = (REPO_ROOT / "configs" / "event_channels.yaml").read_text(encoding="utf-8")
    assert "AgentInstantiated:" in yaml_text, "L4 事件 yaml 登记缺失"
    from src.infrastructure.messaging.channel_router import ChannelRouter

    assert "AgentInstantiated" in ChannelRouter.DEFAULT_MAPPINGS, "L4 事件 DEFAULT_MAPPINGS 登记缺失"

    # L5: CLI 入口注册
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "sisys-agent" in pyproject, "L5 CLI script 注册缺失"

    # L6-L8: deferred 登记仍在（session_storage 补登记 + L7/L8 既有）
    deferred = (REPO_ROOT / "_bmad-output" / "implementation-artifacts" / "deferred-work.md").read_text(encoding="utf-8")
    assert "session_storage" in deferred, "L6 session_storage deferred 登记缺失"
    assert "agent_engine" in deferred, "L7 agent_engine deferred 登记缺失"
    assert "AutoTriggerHandler" in deferred, "L8 AutoTriggerHandler deferred 登记缺失"
