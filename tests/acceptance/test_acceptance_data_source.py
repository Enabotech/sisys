"""Story 4.1b — Skills 数据采集基础设施验收测试（BDD 步骤实现）

本文件遵循项目验收测试规范（参考 test_acceptance_docker_sandbox.py 与
test_acceptance_strategic_tool_impl.py）：
- 步骤函数使用 @given / @when / @then 装饰器 + context: dict[str, Any] fixture
- 真实服务优先：真实 DataSourceResolverService + 真实 Redis（RedisAdapter）+ InMemoryEventBus
- Mock 仅限端口适配器：外部数据源（_FakeDataSourceAdapter 测试替身）、LLM 客户端、沙箱
- 步骤**严格按 AC 编号顺序**排列（AC-1.x → AC-2.x → AC-3.x → AC-4.x）
- 异常处理：try/except 捕获到 context["query_error"]，Then 步骤断言 isinstance + error.code
- Redis 不可用时通过 pytest.skip() 动态跳过（禁止写死 @pytest.mark.skip）
- BDD 步骤函数**禁止** @pytest.mark.asyncio，使用 _run_async helper（场景级共享 event_loop）
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.ports.skill_loader import ToolMetadata
from src.application.services.data_source_resolver import (
    DataSourceResolverService,
    build_data_source_cache_key,
)
from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.domain.entities.tool import Tool
from src.domain.events.data_source_events import DataSourceFetched, DataSourceFetchFailed
from src.domain.exceptions import (
    BusinessRuleViolationError,
    ConfigurationError,
    DataSourceRateLimitError,
    DataSourceResponseError,
    DataSourceUnavailableError,
)
from src.domain.ports.data_source import DataSourcePort, DataSourceQuery
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)
from src.domain.value_objects.tool_execution import ExecutionContext, ToolCall, ToolResultStatus
from src.infrastructure.config.tavily import TavilyConfig
from src.infrastructure.external_services.datasources.tavily_adapter import TavilyAdapter
from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
from src.infrastructure.storage.redis.redis_adapter import RedisAdapter

scenarios("test_acceptance_data_source.feature")


def _run_async(event_loop: Any, coro: Any) -> Any:
    """同步调度异步协程（BDD 步骤函数禁止 @pytest.mark.asyncio）。

    使用场景级共享事件循环（pytest-asyncio function-scope fixture）：
    aioredis/asyncio.Lock 等对象在首次使用时绑定事件循环，
    每次新建循环会导致 "Event loop is closed" 跨循环错误。
    """
    return event_loop.run_until_complete(coro)


# 全部场景归入 data-source-cache 组: 与共享缓存键的测试在同一 worker 串行执行
pytestmark = pytest.mark.xdist_group("data-source-cache")


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context(
    event_loop: Any,
    acceptance_redis_client: Any,
) -> Generator[dict[str, Any], None, None]:
    """BDD 步骤间共享状态容器（场景级 UUID 租户前缀 + 场景级共享事件循环 + teardown 清理本场景缓存键）

    acceptance_redis_client 由 tests/acceptance/conftest.py session-scope 提供，
    避免每个测试文件重复建连（4-1b 与 semantic_cache 原各自内联同款 fixture，
    Round 1 重构提取为共享 fixture）。
    """
    ctx: dict[str, Any] = {
        "_tenant": f"acc-{uuid.uuid4().hex[:8]}",
        "_loop": event_loop,
        "_redis_client": acceptance_redis_client,
    }
    yield ctx

    # teardown: 仅清理本场景创建的缓存键（delete_pattern 限定租户前缀）
    cache = ctx.get("cache")
    if cache is not None:
        _run_async(event_loop, cache.delete_pattern(f"sisys:cache:datasource:{ctx['_tenant']}:*"))


# ===================================================================
# 测试替身（Mock 仅限外部数据源端口适配器）
# ===================================================================


class _FakeDataSourceAdapter:
    """外部数据源测试替身（替代真实外部 HTTP API，行为可编程）。

    实现 DataSourcePort 契约（fetch/get_metadata/health_check），
    call_count 记录真实采集次数，供"缓存命中不重复采集"等断言使用。
    """

    def __init__(self, name: str, behavior: str = "ok", ttl_seconds: int = 3600) -> None:
        self._ref = DataSourceRef(
            name=name,
            url=f"https://fake.local/{name}",
            ttl_seconds=ttl_seconds,
            api_type=DataSourceApiType.REST_JSON,
        )
        self.behavior = behavior
        self.call_count = 0

    def get_metadata(self) -> DataSourceRef:
        return self._ref

    async def health_check(self) -> bool:
        return self.behavior == "ok"

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        self.call_count += 1
        if self.behavior == "unavailable":
            raise DataSourceUnavailableError(
                message=f"数据源 {self._ref.name} 不可用（模拟 5xx）",
                context={"source_name": self._ref.name},
            )
        if self.behavior == "rate_limit":
            raise DataSourceRateLimitError(
                message=f"数据源 {self._ref.name} 触发限流（模拟 429）",
                context={"source_name": self._ref.name},
            )
        if self.behavior == "bad_response":
            raise DataSourceResponseError(
                message=f"数据源 {self._ref.name} 响应解析失败（模拟非法 JSON）",
                context={"source_name": self._ref.name},
            )
        now = datetime.now(UTC)
        return DataSourceResult(
            source_name=self._ref.name,
            payload=json.dumps({"indicator": query.query, "value": 1.23}),
            source_timestamp=now,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=now, ttl_seconds=self._ref.ttl_seconds),
            confidence=0.9,
        )


# ===================================================================
# 辅助函数
# ===================================================================


def _make_tool_metadata(source_names: tuple[str, ...], ttl_seconds: int = 3600) -> ToolMetadata:
    """构造声明指定数据源的 ToolMetadata（白名单依据）。"""
    return ToolMetadata(
        tool_name="测试工具",
        slug="test-tool",
        category="environment_analysis",
        input_schema={},
        output_schema={},
        data_sources=tuple(
            DataSourceRef(
                name=name,
                url=f"https://fake.local/{name}",
                ttl_seconds=ttl_seconds,
                api_type=DataSourceApiType.REST_JSON,
            )
            for name in source_names
        ),
    )


def _make_resolver(context: dict[str, Any]) -> DataSourceResolverService:
    """基于 context 中已配置的适配器构建真实 Resolver。"""
    resolver = DataSourceResolverService(
        adapters=context["adapters"],
        cache=context["cache"],
        event_publisher=context["event_bus"],
    )
    context["resolver"] = resolver
    return resolver


def _make_engine(context: dict[str, Any], code: str) -> ToolExecutionEngine:
    """构建真实 ToolExecutionEngine（Mock LLM/Sandbox 端口适配器）+ 后注入 Resolver。

    LLM mock 按调用顺序响应：
    1. Think 阶段（第 1 次调用）→ 返回 "ok" 模拟 plan 文本
    2. Code 阶段（第 2 次调用）→ 返回上下文注入的 code（含 DATA_SOURCE 标记）
    3. Validate 阶段（第 3 次调用）→ 返回 "ok" 模拟 validation 文本

    Round 1 重构：使用调用顺序（mock_calls 计数）而非 prompt 字符串前缀，
    避免强耦合 Engine 内部 prompt 模板（仅依赖 Engine 五阶段调用规律）。
    """
    llm_call_count = {"n": 0}

    async def _llm_dispatch(prompt: str, response_schema: Any) -> str:
        llm_call_count["n"] += 1
        # 第 2 次调用（Code 阶段）返回测试预设代码
        if llm_call_count["n"] == 2:
            return code
        return "ok"

    llm = AsyncMock()
    llm.structured_generate = AsyncMock(side_effect=_llm_dispatch)
    context["llm_mock"] = llm

    async def _sandbox_execute(session_id: str, code_arg: str, **_kwargs: Any) -> dict[str, Any]:
        context.setdefault("sandbox_codes", []).append(code_arg)
        return {"status": "ok", "output": "done"}

    sandbox = AsyncMock()
    sandbox.start_container = AsyncMock()
    sandbox.execute_code = AsyncMock(side_effect=_sandbox_execute)
    sandbox.stop_container = AsyncMock()
    context["sandbox_mock"] = sandbox

    engine = ToolExecutionEngine(llm_client=llm, sandbox=sandbox)
    engine.set_data_source_resolver(_make_resolver(context))
    return engine


def _run_engine(
    context: dict[str, Any],
    code: str,
    event_loop: Any,
) -> None:
    """驱动真实 Engine 执行含标记代码，异常捕获到 context["query_error"]。"""
    engine = _make_engine(context, code)
    tool = Tool(tool_id=uuid.uuid4(), name="测试工具", slug="test-tool")
    context["tool"] = tool
    exec_context = ExecutionContext(
        tenant_id=uuid.uuid4(),
        session_id=f"sess-{uuid.uuid4().hex[:8]}",
        extensions={"tool_metadata": context["metadata"]},
    )
    try:
        result = _run_async(
            event_loop,
            engine.execute(
                tool_id=tool.tool_id,
                tool=tool,
                tool_call=ToolCall(tool_id=tool.tool_id, arguments={}),
                context=exec_context,
            ),
        )
        context["tool_result"] = result
        context["query_error"] = None
    except Exception as exc:  # BDD 异常断言统一入口（isinstance + code 在 Then 步骤校验）
        context["tool_result"] = None
        context["query_error"] = exc


# ===================================================================
# 背景 Background Steps
# ===================================================================


@given("数据采集基础设施已初始化（真实 DataSourceResolverService + 模拟数据源适配器 + 真实缓存 + InMemoryEventBus）")
def given_infra_initialized(
    context: dict[str, Any],
    event_loop: Any,
    acceptance_redis_client: Any,
) -> None:
    """初始化采集基础设施：真实 Redis 缓存（动态 skip）+ InMemoryEventBus + 空适配器映射。

    Round 1 重构：acceptance_redis_client 由 conftest.py session-scope 提供（沿用 session 寿命的 Redis 连接池）。
    """
    try:
        _run_async(event_loop, acceptance_redis_client.ping())
    except Exception as e:
        pytest.skip(f"Redis 不可用: {e}")

    context["redis_client"] = acceptance_redis_client
    context["cache"] = RedisAdapter(redis_client=acceptance_redis_client)
    context["event_bus"] = InMemoryEventBus()
    context["adapters"] = {}
    context["query_error"] = None


# ===================================================================
# 共享 Given 步骤
# ===================================================================


@given('工具元数据声明数据源 "world-bank"')
def given_metadata_worldbank(context: dict[str, Any]) -> None:
    adapter = _FakeDataSourceAdapter("world-bank")
    context["adapters"]["world-bank"] = adapter
    context["metadata"] = _make_tool_metadata(("world-bank",))


@given('工具元数据声明数据源 "world-bank" 与 "eurostat"')
def given_metadata_worldbank_eurostat(context: dict[str, Any]) -> None:
    context["adapters"]["world-bank"] = _FakeDataSourceAdapter("world-bank")
    context["adapters"]["eurostat"] = _FakeDataSourceAdapter("eurostat")
    context["metadata"] = _make_tool_metadata(("world-bank", "eurostat"))


@given('工具元数据声明数据源 "newsapi"')
def given_metadata_newsapi(context: dict[str, Any]) -> None:
    context["adapters"]["newsapi"] = _FakeDataSourceAdapter("newsapi")
    context["metadata"] = _make_tool_metadata(("newsapi",))


@given(parsers.parse('数据源 "{name}" 配置为不可用'))
def given_source_unavailable(context: dict[str, Any], name: str) -> None:
    context["adapters"][name] = _FakeDataSourceAdapter(name, behavior="unavailable")


@given(parsers.parse('数据源 "{name}" 配置为限流'))
def given_source_rate_limited(context: dict[str, Any], name: str) -> None:
    context["adapters"][name] = _FakeDataSourceAdapter(name, behavior="rate_limit")


@given(parsers.parse('数据源 "{name}" 配置为返回非法响应'))
def given_source_bad_response(context: dict[str, Any], name: str) -> None:
    context["adapters"][name] = _FakeDataSourceAdapter(name, behavior="bad_response")


# ===================================================================
# AC-4.1 Happy Path：标记采集与注入
# ===================================================================


@when("含标记的沙箱代码经 Engine Execute 阶段处理")
def when_engine_execute_with_marker(context: dict[str, Any], event_loop: Any) -> None:
    code = '$DATA_SOURCE("world-bank", "GDP China 2024")\nprint(DATA_SOURCES)'
    _run_engine(context, code, event_loop)


@then("注入后代码包含 DATA_SOURCES 数据前言")
def then_code_contains_preamble(context: dict[str, Any]) -> None:
    assert context["query_error"] is None
    codes = context["sandbox_mock"].execute_code.call_args_list
    assert codes, "沙箱 execute_code 未被调用"
    executed_code = codes[0].args[1] if codes[0].args else codes[0].kwargs["code"]
    assert "DATA_SOURCES" in executed_code
    assert "world-bank" in executed_code


@then("输出元数据含 source 与 freshness 与 confidence")
def then_output_has_lineage_metadata(context: dict[str, Any]) -> None:
    result = context["tool_result"]
    assert result is not None
    assert result.status == ToolResultStatus.SUCCESS
    evidence = result.evidence_package
    assert evidence is not None
    assert len(evidence.data_sources) == 1
    meta = evidence.data_sources[0]
    assert meta.source_name == "world-bank"
    assert 0.0 <= meta.freshness_score <= 1.0
    assert 0.0 <= meta.confidence <= 1.0


@then("已发布 DataSourceFetched 事件")
def then_fetched_event_published(context: dict[str, Any]) -> None:
    events = context["event_bus"].published_events
    fetched = [e for e in events if isinstance(e, DataSourceFetched)]
    assert fetched, "未发布 DataSourceFetched 事件"
    assert fetched[0].source_name == "world-bank"


# ===================================================================
# AC-4.2 Edge：白名单外数据源
# ===================================================================


@when('沙箱代码引用白名单外数据源 "newsapi"')
def when_engine_execute_whitelist_violation(context: dict[str, Any], event_loop: Any) -> None:
    code = '$DATA_SOURCE("newsapi", "tech news")\nprint(DATA_SOURCES)'
    _run_engine(context, code, event_loop)


@then("抛出 BusinessRuleViolationError")
def then_raises_whitelist_error(context: dict[str, Any]) -> None:
    assert isinstance(context["query_error"], BusinessRuleViolationError)


# ===================================================================
# AC-4.3 Edge：单源不可用部分失败收敛
# ===================================================================


@when("含双源标记的沙箱代码经 Engine Execute 阶段处理")
def when_engine_execute_two_sources(context: dict[str, Any], event_loop: Any) -> None:
    code = '$DATA_SOURCE("world-bank", "GDP")\n$DATA_SOURCE("eurostat", "EU GDP")\nprint(DATA_SOURCES)'
    _run_engine(context, code, event_loop)


@then("可用数据源数据已注入")
def then_available_source_injected(context: dict[str, Any]) -> None:
    assert context["query_error"] is None
    codes = context["sandbox_mock"].execute_code.call_args_list
    executed_code = codes[0].args[1] if codes[0].args else codes[0].kwargs["code"]
    # 前言为单行 JSON 字面量（DATA_SOURCES = {...}），其后为原始标记代码
    preamble = executed_code.split("\n", 1)[0]
    assert preamble.startswith("DATA_SOURCES")
    assert "world-bank" in preamble
    assert "eurostat" not in preamble


@then("已发布 DataSourceFetchFailed 事件")
def then_fetch_failed_event_published(context: dict[str, Any]) -> None:
    events = context["event_bus"].published_events
    failed = [e for e in events if isinstance(e, DataSourceFetchFailed)]
    assert failed, "未发布 DataSourceFetchFailed 事件"
    assert failed[0].source_name == "eurostat"


# ===================================================================
# AC-3.1 Edge：缓存命中二次执行不重复采集
# ===================================================================


@when("同一查询连续两次经采集通道处理")
def when_fetch_twice_same_query(context: dict[str, Any], event_loop: Any) -> None:
    resolver = _make_resolver(context)
    metadata = context["metadata"]
    first = _run_async(event_loop, resolver.fetch(metadata, "world-bank", "GDP China 2024", tenant_id=context["_tenant"]))
    second = _run_async(event_loop, resolver.fetch(metadata, "world-bank", "GDP China 2024", tenant_id=context["_tenant"]))
    context["first_result"] = first
    context["second_result"] = second


@then("第二次结果 cache_hit 为真")
def then_second_cache_hit(context: dict[str, Any]) -> None:
    assert context["first_result"].cache_hit is False
    assert context["second_result"].cache_hit is True


@then("外部采集次数为 1")
def then_fetch_count_one(context: dict[str, Any]) -> None:
    assert context["adapters"]["world-bank"].call_count == 1


# ===================================================================
# AC-2.1 Edge：429 限流
# ===================================================================


@when("该数据源唯一标记经 Engine Execute 阶段处理")
def when_engine_execute_single_marker(context: dict[str, Any], event_loop: Any) -> None:
    code = '$DATA_SOURCE("newsapi", "tech news")\nprint(DATA_SOURCES)'
    _run_engine(context, code, event_loop)


@then("抛出 DataSourceRateLimitError")
def then_raises_rate_limit(context: dict[str, Any]) -> None:
    assert isinstance(context["query_error"], DataSourceRateLimitError)


# ===================================================================
# AC-2.2 Edge：响应解析失败（不重试）
# ===================================================================


@then("抛出 DataSourceResponseError")
def then_raises_response_error(context: dict[str, Any]) -> None:
    assert isinstance(context["query_error"], DataSourceResponseError)


# ===================================================================
# AC-2.3 Edge：401/403 鉴权失败归 ConfigurationError
# ===================================================================


@given(parsers.parse('数据源 "{name}" 配置为鉴权失败（401/403）'))
def given_source_auth_failed(context: dict[str, Any], name: str) -> None:
    """Round 1 新增：401/403 → ConfigurationError（不符合通用 4xx → DataSourceResponseError）"""
    context["adapters"][name] = _FakeDataSourceAdapter(name, behavior="auth_failed")


# ===================================================================
# AC-2.4 Edge：TAVILY_API_KEY 缺失时条件注册跳过，Resolver 服务仍可用
# ===================================================================


@given(parsers.parse("TAVILY_API_KEY 未配置（composition_root 条件注册跳过）"))
def given_tavily_key_unset() -> None:
    """Round 1 新增：模拟 TAVILY_API_KEY 环境变量缺失场景，
    composition_root 不会注册 data_source_tavily（条件注册跳过）。
    本步骤仅为语义标识，实际"未注册"由 context["adapters"] 显式控制。
    """


@given(parsers.parse('工具元数据仅声明 "{name}"'))
def given_metadata_only(context: dict[str, Any], name: str) -> None:
    """Round 1 新增：覆盖仅声明单一数据源的 helper（支持任意 source 名）。"""
    context["adapters"][name] = _FakeDataSourceAdapter(name)
    context["metadata"] = _make_tool_metadata((name,))


@given(parsers.parse('数据源 "{name}" 可用且 "{absent}" 未注册'))
def given_source_available_and_other_unregistered(
    context: dict[str, Any],
    name: str,
    absent: str,
) -> None:
    """Round 1 新增：声明的源可用 + 未声明的源在 adapters Mapping 不存在（冷启动 Key 缺失已注册的服务同样可达）。"""
    context["adapters"][name] = _FakeDataSourceAdapter(name)
    context["adapters"].pop(absent, None)


@when("经 Resolver 采集通道处理 world-bank 查询")
def when_resolver_fetch_worldbank(context: dict[str, Any], event_loop: Any) -> None:
    resolver = _make_resolver(context)
    metadata = context["metadata"]
    result = _run_async(
        event_loop,
        resolver.fetch(metadata, "world-bank", "GDP China 2024", tenant_id=context["_tenant"]),
    )
    context["resolver_result"] = result


@then("world-bank 正常采集成功（不抛 ConfigurationError）")
def then_worldbank_fetched_successfully(context: dict[str, Any]) -> None:
    assert context.get("query_error") is None
    result = context.get("resolver_result")
    assert result is not None
    assert result.source_name == "world-bank"
    assert result.cache_hit is False


@then("Resolver 仍可解析其他已注册数据源")
def then_resolver_available_for_other_sources(context: dict[str, Any]) -> None:
    """断言：成功采集后 adapters 仍保持单一 world-bank 注册，Resolver Mapping.get("tavily") = None 时调用应抛 207"""
    assert "world-bank" in context["adapters"]
    assert "tavily" not in context["adapters"]


# ===================================================================
# AC-2.5 Edge：配置缺失 + 优雅降级
# ===================================================================


@when("以缺失 API Key 构造 TavilyAdapter")
def when_construct_tavily_without_key(context: dict[str, Any]) -> None:
    try:
        context["tavily_adapter"] = TavilyAdapter(config=TavilyConfig(api_key=""))
        context["query_error"] = None
    except ConfigurationError as exc:
        context["query_error"] = exc


@then("抛出 ConfigurationError")
def then_raises_config_error(context: dict[str, Any]) -> None:
    assert isinstance(context["query_error"], ConfigurationError)


@then("异常消息不包含密钥字串")
def then_error_message_sanitized(context: dict[str, Any]) -> None:
    import os

    exc = context["query_error"]
    assert exc is not None
    env_key = os.getenv("TAVILY_API_KEY")
    if env_key:  # 环境存在真实 Key 时必须零泄露
        assert env_key not in str(exc)
        assert env_key not in json.dumps(exc.to_dict(), ensure_ascii=False)


@then("Resolver 数据源映射不含 tavily 时查询返回白名单违规")
def then_unregistered_source_whitelist_violation(context: dict[str, Any], event_loop: Any) -> None:
    """优雅降级验证：tavily 未注册（Key 缺失条件注册），且 Tool 未声明 → 白名单违规 207。"""
    context["adapters"].pop("tavily", None)
    resolver = _make_resolver(context)
    metadata = _make_tool_metadata(("world-bank",))
    context["adapters"]["world-bank"] = _FakeDataSourceAdapter("world-bank")
    with pytest.raises(BusinessRuleViolationError) as exc_info:
        _run_async(
            event_loop,
            resolver.fetch(metadata, "tavily", "tech news", tenant_id=context["_tenant"]),
        )
    assert exc_info.value.code == "EXCEPTION_207"


# ===================================================================
# AC-3.2 Edge：缓存 TTL 过期触发重新采集
# ===================================================================


@given("查询结果已缓存且已超过 TTL")
def given_stale_cache_entry(context: dict[str, Any], event_loop: Any) -> None:
    """直接向缓存写入过期条目（fetched_at 早于 ttl_seconds），模拟 TTL 过期场景。"""
    stale_time = datetime.now(UTC) - timedelta(seconds=120)
    entry = {
        "payload": json.dumps({"indicator": "GDP China 2024", "value": 1.23}),
        "source_timestamp": stale_time.isoformat(),
        "fetched_at": stale_time.isoformat(),
        "confidence": 0.9,
    }
    key = build_data_source_cache_key(context["_tenant"], "world-bank", "GDP China 2024")
    context["stale_source_timestamp"] = stale_time
    # 缓存条目本身写入成功（Redis TTL 是上限保鲜，stale 判定由 DataFreshness 负责）
    _run_async(event_loop, context["cache"].set_with_ttl(key, json.dumps(entry), 3600))
    # 替换为短 TTL 元数据（60s，值为不变量下界），使 120s 前的条目必然 stale
    context["adapters"]["world-bank"] = _FakeDataSourceAdapter("world-bank", ttl_seconds=60)
    context["metadata"] = _make_tool_metadata(("world-bank",), ttl_seconds=60)


@when("同一查询再次经采集通道处理")
def when_fetch_after_ttl_expired(context: dict[str, Any], event_loop: Any) -> None:
    resolver = _make_resolver(context)
    result = _run_async(
        event_loop,
        resolver.fetch(context["metadata"], "world-bank", "GDP China 2024", tenant_id=context["_tenant"]),
    )
    context["refetch_result"] = result


@then("数据新鲜度判定为 stale")
def then_stale_detected(context: dict[str, Any]) -> None:
    freshness = DataFreshness(source_timestamp=context["stale_source_timestamp"], ttl_seconds=60)
    assert freshness.is_stale(datetime.now(UTC)) is True


@then("外部采集次数增加 1")
def then_refetch_happened(context: dict[str, Any]) -> None:
    assert context["refetch_result"].cache_hit is False
    assert context["adapters"]["world-bank"].call_count == 1


# ===================================================================
# 共享 Then 步骤（错误码断言）
# ===================================================================


@then(parsers.parse("错误码为 {code}"))
def then_error_code(context: dict[str, Any], code: str) -> None:
    exc = context["query_error"]
    assert exc is not None, "预期抛出异常但未捕获"
    assert exc.code == code
    assert exc.message, "error.message 非空"


# ===================================================================
# AC-1.1 数据源端口契约（基础契约，Round 1 新增）
# ===================================================================


class _CompliantAdapter:
    """合规实现 DataSourcePort 三方法契约的最小可验证实现（BDD 测试专用）。"""

    def __init__(self) -> None:
        from src.domain.value_objects.data_source import DataSourceApiType, DataSourceRef

        self._ref = DataSourceRef(
            name="compliant",
            url="https://example.local/compliant",
            ttl_seconds=3600,
            api_type=DataSourceApiType.REST_JSON,
        )

    def get_metadata(self) -> DataSourceRef:
        return self._ref

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:  # noqa: D401
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        return DataSourceResult(
            source_name="compliant",
            payload="{}",
            source_timestamp=now,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=now, ttl_seconds=3600),
            confidence=0.5,
        )

    async def health_check(self) -> bool:
        return True


@given("定义合规实现 _CompliantAdapter（fetch/get_metadata/health_check 三方法签名齐全）")
def given_compliant_adapter(context: dict[str, Any]) -> None:
    """Round 1 新增：定义 _CompliantAdapter 实例并存入 context（AC-1.1 端口契约验证）。"""
    context["compliant_adapter"] = _CompliantAdapter()


@then("isinstance(_CompliantAdapter(), DataSourcePort) 为真")
def then_isinstance_datasource_port(context: dict[str, Any]) -> None:
    """Round 1 新增：验证 @runtime_checkable Protocol isinstance 断言成立。"""
    instance = context["compliant_adapter"]
    assert isinstance(instance, DataSourcePort)


@then("三方法签名与契约完全一致")
def then_three_method_signatures_match(context: dict[str, Any]) -> None:
    """Round 1 新增：验证 DataSourcePort 三方法在 _CompliantAdapter 中存在且签名一致。"""
    instance = context["compliant_adapter"]
    assert hasattr(instance, "fetch") and callable(instance.fetch)
    assert hasattr(instance, "get_metadata") and callable(instance.get_metadata)
    assert hasattr(instance, "health_check") and callable(instance.health_check)
