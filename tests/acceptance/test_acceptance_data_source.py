"""Story 4.1b — Skills 数据采集基础设施验收测试（BDD 步骤实现）

本文件遵循项目验收测试规范（参考 tests/acceptance/test_acceptance_strategic_tool_impl.py
与 test_acceptance_semantic_cache.py）：

- 步骤函数使用 @given / @when / @then 装饰器 + context: dict[str, Any] fixture
- 真实服务优先：真实 DataSourceResolverService + 真实 Redis（RedisAdapter）+ InMemoryEventBus
- Mock 仅限端口适配器：外部数据源（_FakeDataSourceAdapter 测试替身）、LLM 客户端、沙箱
  （对齐 4-1a 先例：禁止 mock 核心域服务，仅允许 Mock 端口适配器）
- 步骤**严格按 AC 顺序**，`# ====` 分隔
- 异常处理：try/except 捕获到 context["query_error"]，Then 步骤断言 isinstance + error.code
- Redis 不可用时通过 pytest.skip() 动态跳过（禁止写死 @pytest.mark.skip）
- BDD 步骤函数**禁止** @pytest.mark.asyncio，使用 _run helper（场景级共享 event_loop，避免跨循环绑定错误）
- 测试隔离：缓存键含场景级 UUID 前缀（context["_tenant"]），teardown 仅清理本场景键
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
from src.domain.ports.data_source import DataSourceQuery
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


def _run(context: dict[str, Any], coro: Any) -> Any:
    """同步调度异步协程（BDD 步骤函数禁止 @pytest.mark.asyncio）。

    使用场景级共享事件循环（context["_loop"]，由 event_loop fixture 提供）：
    aioredis/asyncio.Lock 等对象在首次使用时绑定事件循环，
    每次新建循环会导致 "Event loop is closed" 跨循环错误。
    """
    return context["_loop"].run_until_complete(coro)


# 全部场景归入 data-source-cache 组: 与共享缓存键的测试在同一 worker 串行执行
pytestmark = pytest.mark.xdist_group("data-source-cache")


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context(event_loop: Any) -> Generator[dict[str, Any], None, None]:
    """BDD 步骤间共享状态容器（场景级 UUID 租户前缀 + 场景级共享事件循环 + teardown 清理本场景缓存键）"""
    ctx: dict[str, Any] = {"_tenant": f"acc-{uuid.uuid4().hex[:8]}", "_loop": event_loop}
    yield ctx

    # teardown: 仅清理本场景创建的缓存键（delete_pattern 限定租户前缀）
    cache = ctx.get("cache")
    if cache is not None:
        _run(ctx, cache.delete_pattern(f"sisys:cache:datasource:{ctx['_tenant']}:*"))
    redis_client = ctx.get("redis_client")
    if redis_client is not None:
        _run(ctx, redis_client.close())


@pytest.fixture
def _redis_client() -> Any:
    """真实 Redis 客户端（连接失败时动态 skip，禁止写死 @pytest.mark.skip）"""
    import redis.asyncio as aioredis

    from tests.environments import get_test_env

    try:
        env = get_test_env()
    except Exception as e:
        pytest.skip(f"测试环境不可用: {e}")

    return aioredis.Redis(
        host=env.redis.host,
        port=env.redis.port,
        password=env.redis.password,
        decode_responses=True,
    )


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
    """构建真实 ToolExecutionEngine（Mock LLM/Sandbox 端口适配器）+ 后注入 Resolver。"""

    async def _llm_dispatch(prompt: str, response_schema: Any) -> str:
        # Code 阶段 prompt 以"基于以下计划生成代码"开头（engine._build_code_prompt）
        if "生成代码" in prompt:
            return code
        return "ok"

    llm = AsyncMock()
    llm.structured_generate = AsyncMock(side_effect=_llm_dispatch)

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


def _run_engine(context: dict[str, Any], code: str) -> None:
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
        result = _run(
            context,
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
def given_infra_initialized(context: dict[str, Any], _redis_client: Any) -> None:
    """初始化采集基础设施：真实 Redis 缓存（动态 skip）+ InMemoryEventBus + 空适配器映射。"""
    try:
        _run(context, _redis_client.ping())
    except Exception as e:
        pytest.skip(f"Redis 不可用: {e}")

    context["redis_client"] = _redis_client
    context["cache"] = RedisAdapter(redis_client=_redis_client)
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
def when_engine_execute_with_marker(context: dict[str, Any]) -> None:
    code = '$DATA_SOURCE("world-bank", "GDP China 2024")\nprint(DATA_SOURCES)'
    _run_engine(context, code)


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
def when_engine_execute_whitelist_violation(context: dict[str, Any]) -> None:
    code = '$DATA_SOURCE("newsapi", "tech news")\nprint(DATA_SOURCES)'
    _run_engine(context, code)


@then("抛出 BusinessRuleViolationError")
def then_raises_whitelist_error(context: dict[str, Any]) -> None:
    assert isinstance(context["query_error"], BusinessRuleViolationError)


# ===================================================================
# AC-4.3 Edge：单源不可用部分失败收敛
# ===================================================================


@when("含双源标记的沙箱代码经 Engine Execute 阶段处理")
def when_engine_execute_two_sources(context: dict[str, Any]) -> None:
    code = '$DATA_SOURCE("world-bank", "GDP")\n$DATA_SOURCE("eurostat", "EU GDP")\nprint(DATA_SOURCES)'
    _run_engine(context, code)


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
def when_fetch_twice_same_query(context: dict[str, Any]) -> None:
    resolver = _make_resolver(context)
    metadata = context["metadata"]
    first = _run(context, resolver.fetch(metadata, "world-bank", "GDP China 2024", tenant_id=context["_tenant"]))
    second = _run(context, resolver.fetch(metadata, "world-bank", "GDP China 2024", tenant_id=context["_tenant"]))
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
def when_engine_execute_single_marker(context: dict[str, Any]) -> None:
    code = '$DATA_SOURCE("newsapi", "tech news")\nprint(DATA_SOURCES)'
    _run_engine(context, code)


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
# AC-2.3 Edge：配置缺失 + 优雅降级
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
def then_unregistered_source_whitelist_violation(context: dict[str, Any]) -> None:
    """优雅降级验证：tavily 未注册（Key 缺失条件注册），且 Tool 未声明 → 白名单违规 207。"""
    context["adapters"].pop("tavily", None)
    resolver = _make_resolver(context)
    metadata = _make_tool_metadata(("world-bank",))
    context["adapters"]["world-bank"] = _FakeDataSourceAdapter("world-bank")
    with pytest.raises(BusinessRuleViolationError) as exc_info:
        _run(context, resolver.fetch(metadata, "tavily", "tech news", tenant_id=context["_tenant"]))
    assert exc_info.value.code == "EXCEPTION_207"


# ===================================================================
# AC-3.2 Edge：缓存 TTL 过期触发重新采集
# ===================================================================


@given("查询结果已缓存且已超过 TTL")
def given_stale_cache_entry(context: dict[str, Any]) -> None:
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
    _run(context, context["cache"].set_with_ttl(key, json.dumps(entry), 3600))
    # 替换为短 TTL 元数据（60s，值为不变量下界），使 120s 前的条目必然 stale
    context["adapters"]["world-bank"] = _FakeDataSourceAdapter("world-bank", ttl_seconds=60)
    context["metadata"] = _make_tool_metadata(("world-bank",), ttl_seconds=60)


@when("同一查询再次经采集通道处理")
def when_fetch_after_ttl_expired(context: dict[str, Any]) -> None:
    resolver = _make_resolver(context)
    result = _run(
        context,
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
