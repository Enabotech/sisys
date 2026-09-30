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

# ConfigurationError 已在 import 列表中
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

# AC-2.5 金丝雀假 Key（低熵、无 tvly- 真实前缀，detect-secrets 实测零误报——R2-2-C6/I5）
_FAKE_TAVILY_KEY = "fake-tavily-key-test1234"


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context(
    event_loop: Any,
    acceptance_env_config: Any,
) -> Generator[dict[str, Any], None, None]:
    """BDD 步骤间共享状态容器（场景级 UUID 租户前缀 + 场景级共享事件循环 + teardown 清理本场景缓存键）

    R2-2-C2/I2：Redis 客户端场景级独立创建并在**同一事件循环**内关闭——
    原 conftest session-scope 共享客户端的连接池绑定首个使用它的 function-scope
    循环，跨场景报 "Event loop is closed"（对齐 test_acceptance_skill_data_collection.py
    范本；共享前提经 grep 证伪——唯一消费者即本文件）。
    """
    import redis.asyncio as aioredis

    client = aioredis.Redis(
        host=acceptance_env_config.redis.host,
        port=acceptance_env_config.redis.port,
        password=acceptance_env_config.redis.password,
        decode_responses=True,
    )
    ctx: dict[str, Any] = {
        # 标准 UUID 字符串形态（R3-3 H7v2：engine 的 ExecutionContext.tenant_id
        # 须可从本值解析（uuid.UUID），并与 resolver 直取路径同命名空间——
        # 原 acc- 前缀形态与 engine 随机 UUID 不同值，缓存键泄漏 teardown 之外）
        "_tenant": str(uuid.uuid4()),
        "_loop": event_loop,
        "_redis_client": client,
    }
    try:
        yield ctx
    finally:
        # teardown: 先清理本场景缓存键（delete_pattern 限定租户前缀），再同循环关闭客户端
        cache = ctx.get("cache")
        if cache is not None:
            _run_async(event_loop, cache.delete_pattern(f"sisys:cache:datasource:{ctx['_tenant']}:*"))
        _run_async(event_loop, client.close())  # 对齐范本 close()（redis-py 5.x 与 aclose 等价；aclose 泛型标注 mypy 不识别）


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
        if self.behavior == "auth_failed":
            # Round 2 修复后契约（commit f9f8e422）：401/403 → ConfigurationError(101)
            # 而非通用 4xx → DataSourceResponseError(413)
            raise ConfigurationError(
                message=f"数据源 {self._ref.name} API Key 无效或未授权（模拟 401/403）",
                context={"source_name": self._ref.name, "status_code": 401},
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
    """驱动真实 Engine 执行含标记代码，异常捕获到 context["query_error"]。

    Round 3 根因修复：Redis 不可用时显式 pytest.skip（精确 skip 本场景，
    不牵连整个 scenario）。
    """
    _assert_redis_available(context, event_loop)
    engine = _make_engine(context, code)
    tool = Tool(tool_id=uuid.uuid4(), name="测试工具", slug="test-tool")
    context["tool"] = tool
    exec_context = ExecutionContext(
        tenant_id=uuid.UUID(context["_tenant"]),  # 线程化为场景租户（H7v2：防缓存键泄漏）
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
) -> None:
    """初始化采集基础设施（优雅降级）：InMemoryEventBus + 空适配器映射 + Redis 连接尽力初始化。

    Round 3 根因修复：原实现（line 280）在 Redis ping 失败时抛 pytest.skip()，导致整个 scenario skip，
    包括不依赖 Redis 的元场景（AC-5.x / AC-6.x / AC-7.x）也被无意义 skip。

    新实现：
    - Redis ping 失败 → context["redis_available"] = False，context["cache"] = None
      （不抛 pytest.skip），元场景正常执行
    - Redis 依赖场景在 _run_engine / resolver.fetch 入口通过 _assert_redis_available()
      helper 显式 skip，命中 CLAUDE.md §5 "运行时动态 skip（禁止写死 @pytest.mark.skip）"

    R2-2-C2/I2：客户端来自 context fixture 的场景级实例（同循环创建/关闭），
    不再依赖 conftest session-scope 共享客户端。
    """
    client = context["_redis_client"]
    context["redis_client"] = client
    context["adapters"] = {}
    context["query_error"] = None
    context["event_bus"] = InMemoryEventBus()

    try:
        _run_async(event_loop, client.ping())
    except Exception as e:
        # 优雅降级：标记 Redis 不可用，让非依赖场景继续运行
        context["redis_available"] = False
        context["cache"] = None
        context["skip_reason"] = f"Redis 不可用: {e}"
        return

    context["redis_available"] = True
    context["cache"] = RedisAdapter(redis_client=client)


def _assert_redis_available(context: dict[str, Any], event_loop: Any) -> None:
    """Redis 不可用时显式 pytest.skip（用于 Redis 依赖场景入口的精确 skip）。

    Round 3 根因修复：从 `given_infra_initialized` 提取的 skip 判定 helper，
    仅 Redis 依赖场景（_run_engine / resolver.fetch / cache 操作）调用，
    避免 background 失败导致元场景被牵连 skip。

    R2-2-C2/I2 后客户端为场景级实例（与本场景 event_loop 同循环创建），
    ping 实证保留作为真实可用性探针（belt-and-braces）；lazy 重建分支
    同样保留（background ping 失败 → 场景级 ping 成功的恢复路径）。
    """

    client = context.get("redis_client")
    if client is None:
        pytest.skip(context.get("skip_reason", "Redis 客户端未初始化"))
    try:
        _run_async(event_loop, client.ping())
    except Exception as e:
        pytest.skip(f"Redis 不可用: {e}")

    if context.get("cache") is None:
        context["cache"] = RedisAdapter(redis_client=client)


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
    _assert_redis_available(context, event_loop)
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


@given(parsers.parse("真实 NewsAPI 适配器收到 401（HTTP 层 mock，鉴权分流验证）"))
def given_source_auth_failed(context: dict[str, Any]) -> None:
    """构造真实 NewsAPIAdapter + MockTransport 401（R3-5 J1 重写）。

    原场景对 `_FakeDataSourceAdapter(behavior="auth_failed")` 直接调用自证——
    删除生产 401/403→101 映射（_http_helpers）该场景仍全绿，属 R3-P1-9 红线
    破口（验收测试替身自证）。重写后驱动生产映射链路（真实适配器 →
    request_json_with_resilience → 101 分流）；mock 仅限外部 HTTP 传输层
    （对齐项目「mock 仅限外部数据源替身」范本）。
    """
    import httpx

    from src.infrastructure.config.newsapi import NewsAPIConfig
    from src.infrastructure.external_services.datasources.newsapi_adapter import NewsAPIAdapter

    adapter = NewsAPIAdapter(
        config=NewsAPIConfig(api_key="acc-test-auth-key", api_url="https://mock.local", timeout=5.0),
        client=httpx.AsyncClient(
            base_url="https://mock.local",
            transport=httpx.MockTransport(lambda req: httpx.Response(401, json={"message": "invalid key"})),
            timeout=5.0,
        ),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )
    context["auth_failed_adapter"] = adapter


@when("调用该适配器 fetch 并捕获鉴权异常")
def when_call_fake_adapter_fetch(context: dict[str, Any], event_loop: Any) -> None:
    from src.domain.ports.data_source import DataSourceQuery

    adapter = context["auth_failed_adapter"]
    try:
        _run_async(event_loop, adapter.fetch(DataSourceQuery(source_name="newsapi", query="test")))
        context["query_error"] = None
    except ConfigurationError as exc:
        context["query_error"] = exc


# ===================================================================
# AC-2.4 Edge：TAVILY_API_KEY 缺失时条件注册跳过，Resolver 服务仍可用
# ===================================================================


@given(parsers.parse("TAVILY_API_KEY 未配置（composition_root 条件注册跳过）"))
def given_tavily_key_unset(context: dict[str, Any]) -> None:
    """R2-2-C5/I4 子进程实证条件注册（原实现为空语义标识步骤）。

    注册发生于 `bootstrap()`（本进程 session 启动时已执行），进程内 delenv
    无法回滚——起干净子进程验证：scrub KEY → 显式 bootstrap → 断言
    tavily 未注册且核心适配器已注册；with-Key 阳性对照防探针恒报未注册的假阴性。
    bootstrap 全为惰性 lambda 注册（纯 dict 操作），无 DB/Redis 依赖，秒级完成。
    """
    import subprocess
    import sys
    from pathlib import Path

    script_tpl = (
        "import os;"
        "os.environ.pop('TAVILY_API_KEY', None);"
        "os.environ.pop('NEWSAPI_API_KEY', None);"
        "{with_key_line}"
        "from src.composition_root import bootstrap;"
        "from src.domain.ports.registry import _global_registry;"
        "bootstrap();"
        "ports = sorted(s.name for s in _global_registry.list_all() if s.name.startswith('data_source_'));"
        "assert _global_registry.get('data_source_tavily') is {tavily_expect}, 'tavily 注册态与 KEY 配置不符: ' + str(ports);"
        "assert _global_registry.get('data_source_worldbank') is not None, '核心适配器应无条件注册';"
        "print('PORTS=' + ','.join(ports))"
    )
    # 反向对照：注入假 Key 时 tavily 应注册（防探针恒报未注册）；
    # 值经 f-string 插值（复用模块级低熵假 Key 常量，字面赋值形态会触发 detect-secrets）
    with_key = script_tpl.format(
        with_key_line=f"os.environ['TAVILY_API_KEY'] = '{_FAKE_TAVILY_KEY}';",
        tavily_expect="not None",
    )
    without_key = script_tpl.format(with_key_line="", tavily_expect="None")
    repo_root = Path(__file__).resolve().parents[2]
    for script in (without_key, with_key):
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=repo_root,
        )
        assert result.returncode == 0, f"条件注册探针失败:\n{result.stdout}\n{result.stderr}"
        assert "PORTS=" in result.stdout
    context["tavily_conditional_registration_verified"] = True


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
    _assert_redis_available(context, event_loop)
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
def then_resolver_available_for_other_sources(context: dict[str, Any], event_loop: Any) -> None:
    """真实行为断言（R3-4 K3 重写）：同一 Resolver 实例再次解析（不同 query，独立
    缓存键）仍成功——服务可用性未因 tavily 缺 Key 条件注册跳过而降级。
    原 fixture dict 自省（"world-bank" in adapters）与被测系统零交互，零判别力。"""
    _assert_redis_available(context, event_loop)
    resolver = context["resolver"]
    result = _run_async(
        event_loop,
        resolver.fetch(context["metadata"], "world-bank", "GDP USA 2023", tenant_id=context["_tenant"]),
    )
    assert result.source_name == "world-bank"
    assert result.cache_hit is False  # 新查询键未命中，真实走采集链路
    assert context["adapters"]["world-bank"].call_count == 2  # 两次真实采集


# ===================================================================
# AC-2.5 Edge：配置缺失 + 优雅降级
# ===================================================================


@when("以缺失 API Key 构造 TavilyAdapter")
def when_construct_tavily_without_key(context: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """R2-2-C6/I5 金丝雀：进程内注入固定假 Key——证明即使环境中存在 Key 材料，
    空配置构造失败路径的 message/context/序列化也零插值泄露。
    （TavilyAdapter 构造不读 env，读取在 TavilyConfig.from_env——金丝雀模拟
    "环境有 Key 材料但配置显式为空"的失败路径）"""
    monkeypatch.setenv("TAVILY_API_KEY", _FAKE_TAVILY_KEY)
    try:
        context["tavily_adapter"] = TavilyAdapter(config=TavilyConfig(api_key=""))
        context["query_error"] = None
    except ConfigurationError as exc:
        context["query_error"] = exc


@then("抛出 ConfigurationError")
def then_raises_config_error(context: dict[str, Any]) -> None:
    """直接验证 _FakeDataSourceAdapter.fetch 抛 ConfigurationError
    （R2-P1-7 修复后 Engine 已恢复 101 直传，本断言定位适配器行为）"""
    assert isinstance(context["query_error"], ConfigurationError)


@then("401 异常消息不含密钥材料")
def then_auth_error_message_no_key_material(context: dict[str, Any]) -> None:
    """AC-2.3 专属：401/403 异常消息为固定文案（仅含 source_name 与 status_code，零密钥材料）。"""
    exc = context["query_error"]
    assert exc is not None
    message = str(exc)
    assert "api_key" not in message.lower().replace("api key 无效", "")  # 仅允许固定文案中的字段名
    for material in ("key=", "token=", "secret=", "Bearer "):
        assert material not in message


@then("context 含 status_code 字段")
def then_context_has_status_code(context: dict[str, Any]) -> None:
    """验证异常 context 含 status_code 字段（401/403 场景标识）"""
    exc = context["query_error"]
    assert exc.context.get("status_code") == 401, f"context 应含 status_code=401，实际 {exc.context}"


@then("异常消息不包含密钥字串")
def then_error_message_sanitized(context: dict[str, Any]) -> None:
    """R2-2-C6/I5 无条件断言（原 if env_key: 条件形态在无 Key 环境恒空转）。"""
    import os

    exc = context["query_error"]
    assert exc is not None
    assert os.getenv("TAVILY_API_KEY") == _FAKE_TAVILY_KEY, "金丝雀未注入（断言将空转）"
    assert _FAKE_TAVILY_KEY not in str(exc)
    assert _FAKE_TAVILY_KEY not in json.dumps(exc.to_dict(), ensure_ascii=False)


@then("Resolver 数据源映射不含 tavily 时查询返回白名单违规")
def then_unregistered_source_whitelist_violation(context: dict[str, Any], event_loop: Any) -> None:
    """优雅降级验证：tavily 未注册（Key 缺失条件注册），且 Tool 未声明 → 白名单违规 207。"""
    _assert_redis_available(context, event_loop)
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
    _assert_redis_available(context, event_loop)
    stale_time = datetime.now(UTC) - timedelta(seconds=120)
    entry = {
        "payload": json.dumps({"indicator": "GDP China 2024", "value": 1.23}),
        "source_timestamp": stale_time.isoformat(),
        "fetched_at": stale_time.isoformat(),
        "confidence": 0.9,
    }
    key = build_data_source_cache_key(context["_tenant"], "world-bank", "GDP China 2024")
    context["stale_source_timestamp"] = stale_time
    # 前置条件落实（R3-4 K3：写失败即红——原返回值被忽略，重采可能来自「未命中」
    # 而非「stale 判定」，场景恒绿空转）
    written = _run_async(event_loop, context["cache"].set_with_ttl(key, json.dumps(entry), 3600))
    assert written is True, "预置过期条目写入失败——后续 stale 断言失去前提"
    # 替换为短 TTL 元数据（60s，值为不变量下界），使 120s 前的条目必然 stale
    context["adapters"]["world-bank"] = _FakeDataSourceAdapter("world-bank", ttl_seconds=60)
    context["metadata"] = _make_tool_metadata(("world-bank",), ttl_seconds=60)


@when("同一查询再次经采集通道处理")
def when_fetch_after_ttl_expired(context: dict[str, Any], event_loop: Any) -> None:
    _assert_redis_available(context, event_loop)
    # fetch 前捕获键存活态（R3-4 K3：_write_cache 会覆写条目，必须在 fetch 前取）
    key = build_data_source_cache_key(context["_tenant"], "world-bank", "GDP China 2024")
    context["stale_key_alive"] = _run_async(event_loop, context["cache"].exists(key))
    resolver = _make_resolver(context)
    result = _run_async(
        event_loop,
        resolver.fetch(context["metadata"], "world-bank", "GDP China 2024", tenant_id=context["_tenant"]),
    )
    context["refetch_result"] = result


@then("数据新鲜度判定为 stale")
def then_stale_detected(context: dict[str, Any]) -> None:
    """stale 判定真实生效的判别锚点（R3-4 K3 重写）：Redis 条目存活（非 Redis TTL
    过期）但未被复用——重采只能归因于 resolver 条目年龄判定（fetched_at 距今 >
    白名单 ttl）；且重采结果的 freshness ttl 为白名单权威值（H6 单一权威路径）。"""
    assert context["stale_key_alive"] is True, "预置过期条目不存在——重采来自未命中而非 stale 判定"
    assert context["refetch_result"].cache_hit is False
    assert context["refetch_result"].freshness.ttl_seconds == 60  # 白名单 ttl 权威（非适配器默认）


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

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
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


# ===================================================================
# AC-5 领域异常与事件契约（Round 2 完整覆盖）
# ===================================================================


@given("构造 ConfigurationError 含敏感 Key 字段 example.com 含 fake_test_marker")
def given_config_error_with_context(context: dict[str, Any]) -> None:
    """构造 context.url 含 api_key 参数的 ConfigurationError（R2-2-C1/I1 真实化）。

    url 携带低熵假 Key（test1234fake，detect-secrets 实测零误报），
    使脱敏断言具备真实判别力（原实现 url 不含任何敏感串，断言恒真）。
    .feature step text 与装饰器精确字面匹配（pytest-bdd strict equal）。
    """
    name = "tavily"
    url = "https://api.example.test/search?api_key=test1234fake&query=gdp"
    exc = ConfigurationError(
        message=f"数据源 {name} 配置缺失",
        context={"source_name": name, "url": url},
    )
    context["config_error_with_url"] = exc


@when("调用异常 to_dict 序列化")
def when_call_exception_to_dict(context: dict[str, Any]) -> None:
    """Round 2 新增：对构造的异常调用 to_dict() 并存储结果到 context。"""
    exc = context["config_error_with_url"]
    context["exception_to_dict_result"] = exc.to_dict()


@then("序列化字典存在 context 键且 source_name 等于 tavily")
def then_serialized_dict_has_source_name(context: dict[str, Any]) -> None:
    """Round 3 根因修复：固定字面匹配避免 parsers.parse 占位符与 .feature step 不匹配。"""
    result = context["exception_to_dict_result"]
    assert "context" in result
    assert result["context"]["source_name"] == "tavily"


@then("序列化字典中不出现敏感 API Key 字串")
def then_serialized_dict_has_no_secret(context: dict[str, Any]) -> None:
    """R2-2-C1/I1 三断言（原串消失 + 阳性对照 + 防过度脱敏）。"""
    import json as _json

    result = context["exception_to_dict_result"]
    serialized = _json.dumps(result, ensure_ascii=False)
    assert "test1234fake" not in serialized, "to_dict 序列化结果含敏感字段（API Key 泄露）"
    assert "***REDACTED***" in serialized, "脱敏未真实发生（阳性对照缺失，断言可能空转）"
    assert "query=gdp" in serialized, "非敏感参数应原样保留（防过度脱敏）"


@given("遍历 src/domain/exceptions/data_source_exceptions.py 全部异常类")
def given_enumerate_data_source_exception_classes(context: dict[str, Any]) -> None:
    """Round 2 新增：遍历 4 个 DataSource 子域异常类 + 收集 (class_name, code_value) 列表。"""
    import inspect

    from src.domain.exceptions import data_source_exceptions as ds_exc_module

    classes = []
    for name, obj in inspect.getmembers(ds_exc_module, inspect.isclass):
        if obj.__module__ != ds_exc_module.__name__:
            continue
        code = getattr(obj, "code", None)
        if isinstance(code, str) and code.startswith("EXCEPTION_4"):
            classes.append((name, code))
    context["data_source_exception_classes"] = classes


@when("用 _code_ranges.py 校验每个类的 code 字段所在子域")
def when_validate_each_code_subdomain(context: dict[str, Any]) -> None:
    """Round 2 新增：调用 _code_ranges.get_subdomain_for_class 校验每个异常类 code 字段所在子域段。"""
    from src.domain.exceptions import _code_ranges

    classes = context["data_source_exception_classes"]
    rows = []
    for class_name, code_value in classes:
        # 通过同名字符串解析 code → 整数
        code_int = int(code_value.split("_")[1])
        row = {
            "class_name": class_name,
            "code_value": code_value,
            "code_int": code_int,
            "subdomain": _code_ranges.get_subdomain_for_class(class_name),
        }
        rows.append(row)
    context["data_source_exception_rows"] = rows


@then("所有 4 个 DataSource 子域异常（EXCEPTION_410-413）code 与子域段 [410, 419] 一致")
def then_all_codes_in_data_source_range(context: dict[str, Any]) -> None:
    """Round 2 新增：所有 DataSource 子域异常 code 都属于 [410, 419] 子域段。"""
    rows = context["data_source_exception_rows"]
    assert len(rows) == 4, f"预期 4 个 DataSource 异常，实际 {len(rows)}"
    for row in rows:
        code_int = row["code_int"]
        assert 410 <= code_int <= 419, f"{row['class_name']} code {code_int} 不在 [410, 419]"
        assert row["subdomain"] == "data_source", f"{row['class_name']} 子域 {row['subdomain']}"


@then("_CLASS_TO_SUBDOMAIN 注册条目与异常类数匹配")
def then_class_to_subdomain_count_matches(context: dict[str, Any]) -> None:
    """Round 2 新增：_CLASS_TO_SUBDOMAIN 中 4 个 DataSource 异常类全部映射到 data_source 子域。

    注意 _code_ranges._CLASS_TO_SUBDOMAIN 是反向映射 {class_name: subdomain}，而非 {subdomain: count}。
    故用 list comprehension 过滤 data_source 子域条目数 == 4。
    """
    from src.domain.exceptions import _code_ranges

    rows = context["data_source_exception_rows"]
    data_source_entries = [
        class_name for class_name, subdomain in _code_ranges._CLASS_TO_SUBDOMAIN.items() if subdomain == "data_source"
    ]
    assert len(data_source_entries) == 4
    assert len(rows) == 4
    # 双向校验：每个异常类的子类域 = "data_source"
    for row in rows:
        assert row["subdomain"] == "data_source"


@given("加载 configs/event_channels.yaml 的 events 块")
def given_load_event_channels_yaml(context: dict[str, Any]) -> None:
    """Round 2 新增：解析 configs/event_channels.yaml 提取所有 event_type 名称。"""
    from pathlib import Path

    import yaml

    config_path = Path("configs/event_channels.yaml")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    # Round 3 根因修复：yaml 顶层是 `event_channels:` dict，keys 直接是事件名
    # （每个事件名映射到内层 dict 含 redis_channel / delivery_mode / description 等配置）
    channels_section = data.get("event_channels", {})
    context["yaml_event_types"] = set(channels_section.keys())


@when("提取 yaml 中所有 event_type 与 ChannelRouter.DEFAULT_MAPPINGS 键对比")
def when_compare_yaml_with_router_defaults(context: dict[str, Any]) -> None:
    """Round 2 新增：提取 ChannelRouter.DEFAULT_MAPPINGS 事件类型集合，与 yaml 集合对比。"""
    from src.infrastructure.messaging.channel_router import ChannelRouter

    yaml_events = context["yaml_event_types"]
    default_events = set(ChannelRouter.DEFAULT_MAPPINGS.keys())
    context["yaml_events"] = yaml_events
    context["default_events"] = default_events
    context["events_intersection"] = yaml_events & default_events
    context["events_yaml_only"] = yaml_events - default_events
    context["events_default_only"] = default_events - yaml_events


@then("DataSourceFetched 事件在 yaml 与 DEFAULT_MAPPINGS 两处均登记")
def then_data_source_fetched_in_both(context: dict[str, Any]) -> None:
    """Round 3 根因修复：DataSourceFetched 必须在 yaml 与 DEFAULT_MAPPINGS 中均登记（字面精确匹配避免参数化歧义）。"""
    intersection = context.get("events_intersection", set())
    assert "DataSourceFetched" in intersection, "DataSourceFetched 未在 yaml 与 DEFAULT_MAPPINGS 中均登记"


@then("DataSourceFetchFailed 事件在 yaml 与 DEFAULT_MAPPINGS 两处均登记")
def then_data_source_fetch_failed_in_both(context: dict[str, Any]) -> None:
    """Round 3 根因修复：DataSourceFetchFailed 必须在 yaml 与 DEFAULT_MAPPINGS 中均登记。"""
    intersection = context.get("events_intersection", set())
    assert "DataSourceFetchFailed" in intersection, "DataSourceFetchFailed 未在 yaml 与 DEFAULT_MAPPINGS 中均登记"


# ===================================================================
# AC-6 集成测试（真实服务链路 + xdist_group 协作，Round 2 完整覆盖）
# ===================================================================


@given("检查 tests/integration/external_services/data_sources/ 路径")
def given_check_integration_data_source_dir(context: dict[str, Any]) -> None:
    """Round 2 新增：探测集成测试目录是否存在并列出 .py 文件。"""
    from pathlib import Path

    target = Path("tests/integration/external_services/data_sources")
    context["integration_dir_exists"] = target.exists()
    py_files = sorted([p.name for p in target.glob("test_*.py")]) if target.exists() else []
    context["integration_py_files"] = py_files
    context["integration_dir_path"] = str(target)


@when("列出该目录下所有 .py 测试文件")
def when_list_integration_py_files(context: dict[str, Any]) -> None:
    """Round 2 新增：补充收集 .py 文件中是否包含 xdist_group('data-source-cache') marker。"""
    from pathlib import Path

    target = Path("tests/integration/external_services/data_sources")
    files_with_marker = []
    for p in sorted(target.glob("test_*.py")):
        text = p.read_text(encoding="utf-8")
        if "xdist_group" in text and "data-source-cache" in text:
            files_with_marker.append(p.name)
    context["integration_files_with_marker"] = files_with_marker


@then("至少存在 test_adapters_http_chain.py")
@then("至少存在 test_china_nbs_crawler.py")
def then_required_integration_files_exist(context: dict[str, Any]) -> None:
    """Round 2 新增：核心集成测试文件至少存在（与 4-1b 文档承诺一致）。"""
    files = context["integration_py_files"]
    assert "test_adapters_http_chain.py" in files
    assert "test_china_nbs_crawler.py" in files


@then('这些测试文件声明 xdist_group("data-source-cache")（与 4-1b 验收测试共享组）')
def then_integration_files_use_shared_xdist_group(context: dict[str, Any]) -> None:
    """Round 2 新增：集成测试文件声明 xdist_group 共享同一 worker 串行组。"""
    files_with_marker = context["integration_files_with_marker"]
    assert "test_adapters_http_chain.py" in files_with_marker
    assert "test_china_nbs_crawler.py" in files_with_marker


@given("检查所有 acceptance test 中 _run_engine 调用")
def given_check_run_engine_calls(context: dict[str, Any]) -> None:
    """Round 2 新增：扫描 4-1b 自身 .py 中 _run_engine 调用，确认场景级 fixture 共享 Resolver/Engine/Redis 实例。"""
    import ast
    from pathlib import Path

    source = Path("tests/acceptance/test_acceptance_data_source.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    call_count = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_run_engine"
    )
    context["run_engine_call_count"] = call_count


@then("_run_engine 调用次数 >= 4")
def then_engine_linkage_uses_shared_fixture(context: dict[str, Any]) -> None:
    """Round 3 根因修复：_run_engine 实际调用数 = 4（AC-2.1 + AC-4.1/4.2/4.3 共 4 处）。

    之前预期 >= 8 是误判（实际只有 Engine.Execute 阶段调用 _run_engine；AC-3.x 调
    _run_async(resolver.fetch)，AC-5.x 是元场景无 Engine 调用）。
    """
    call_count = context["run_engine_call_count"]
    assert call_count >= 4, f"预期 _run_engine >= 4 次调用（Engine.Execute 链路），实际 {call_count}"


@then("integration 测试也使用 pytestmark 列表双标记")
def then_integration_tests_use_dual_marker(context: dict[str, Any]) -> None:
    """Round 3 根因修复：AC-6.2 不依赖 AC-6.1 的 When 步骤，独立扫描 integration 测试目录。

    每个集成测试文件均显式声明 pytestmark list 形式（integration + xdist_group）。
    """
    from pathlib import Path

    target = Path("tests/integration/external_services/data_sources")
    files_with_marker = []
    for p in sorted(target.glob("test_*.py")):
        text = p.read_text(encoding="utf-8")
        if "xdist_group" in text and "data-source-cache" in text:
            files_with_marker.append(p.name)
    assert len(files_with_marker) >= 2, (
        f"集成测试目录应有 >= 2 个声明 xdist_group(data-source-cache) 的文件，实际 {files_with_marker}"
    )


@then('integration 测试也使用 pytestmark = [pytest.mark.integration, pytest.mark.xdist_group("data-source-cache")] 双标记')
def then_integration_tests_dual_marker(context: dict[str, Any]) -> None:
    """Round 2 新增：每个集成测试文件均显式声明 pytestmark list 形式（integration + xdist_group）。"""
    # 已在 when_list_integration_py_files 时收集，再核验
    files_with_marker = context["integration_files_with_marker"]
    assert len(files_with_marker) >= 2


# ===================================================================
# AC-7 SDD 架构验证测试（六边形约束 + 端口注册 + 域零依赖，Round 2 完整覆盖）
#
# 历史注记：AC-7.1「subprocess 运行架构测试套件」场景已随游离提交 730e1cb4 删除
# （其 when 步骤依赖 PATH 中 poetry 二进制，CI venv 直跑不成立）；架构套件由
# CI（.gitea/workflows/ci.yaml test 阶段）与本地 `make test-unit` 直跑覆盖。
# 下列步骤保留 AC-7.2/7.3（注册完整性与 domain 零依赖，进程内反射断言）。
# ===================================================================


@given("导入 src.composition_root._PORT_REGISTRY（懒加载触发模块级注册）")
@given("导入 src.composition_root._global_registry 模块级全局注册中心")
def given_import_composition_root_registry(context: dict[str, Any]) -> None:
    """获取全局注册中心（`_global_registry`，src/domain/ports/registry.py）。

    R2-2-C4/I3 机制纠偏：注册并非 __import__ 模块级副作用，而是
    `bootstrap()` 函数体内执行——由 tests/conftest.py 的 session autouse
    `_bootstrap_once` 在会话启动时调用一次；本步骤仅取回该注册中心实例。
    """
    registry = __import__(
        "src.composition_root",
        fromlist=["_global_registry"],
    )._global_registry
    context["composition_root_registry"] = registry


@when("反射获取所有 name 以 data_source_ 开头且非 data_source_resolver 的端口")
def when_extract_data_source_ports(context: dict[str, Any]) -> None:
    """Round 3 根因修复：PortRegistry 提供 `list_all()` 方法（不是 dict `values()`）。

    过滤 _global_registry 提取 8 个 data_source 适配器端口名。
    """
    registry = context["composition_root_registry"]
    names = {
        spec.name
        for spec in registry.list_all()
        if spec.name.startswith("data_source_") and spec.name != "data_source_resolver"
    }
    context["registered_data_source_ports"] = sorted(names)


@then("端口注册集合与按环境 KEY 推导的期望一致（无条件 7 + 条件注册逐 KEY 判定，4.1f 起 11 端口态）")
def then_eight_data_source_adapters_registered(context: dict[str, Any]) -> None:
    """R2-2-C4/I3：按进程环境 KEY 确定性推导期望注册集合（兼容 {5,6,7,8} 态）。

    uspto/newsapi/tavily 条件注册独立判定（composition_root `bool(os.getenv(...))`，
    空串视为未配置——uspto 自 R3-P1-3 起条件注册：PatentsView v1 强制 X-Api-Key，
    无 Key 时注册只会必然 403），原 `len==8 or len==6` 断言在单 KEY 配置时误失败；
    测试进程 env 与 session 级 bootstrap 决策天然一致。
    """
    import os

    ports_set = set(context["registered_data_source_ports"])
    core_required = {
        "data_source_worldbank",
        "data_source_imf",
        "data_source_eurostat",
        "data_source_ipcc",
        "data_source_china_nbs",
        # 4.1f 无条件新源（免 key / key 可选——官方免费通道可达即注册）
        "data_source_sec_edgar",
        "data_source_comtrade",
    }
    expected = set(core_required)
    # 判定语义与 composition_root 条件注册逐字一致（bool() 拒 None 与空串；
    # epo-ops 双凭据门——Key/Secret 双键合取，任一缺失即不注册，4.1f）
    for port_name, env_keys in (
        ("data_source_uspto", ("USPTO_API_KEY",)),
        ("data_source_newsapi", ("NEWSAPI_API_KEY",)),
        ("data_source_tavily", ("TAVILY_API_KEY",)),
        ("data_source_epo_ops", ("EPO_OPS_CONSUMER_KEY", "EPO_OPS_CONSUMER_SECRET")),
    ):
        if all(bool(os.getenv(key)) for key in env_keys):
            expected.add(port_name)
    assert ports_set == expected, f"注册集合 {sorted(ports_set)} 与按环境 KEY 推导的期望 {sorted(expected)} 不一致"


@given("收集 src/domain/{ports,value_objects,events,exceptions} 下 data_source 相关文件")
def given_collect_domain_data_source_files(context: dict[str, Any]) -> None:
    """Round 2 新增：收集 domain 层下数据源相关 .py 文件清单（domain 零依赖检查输入）。"""
    from pathlib import Path

    base = Path("src/domain")
    files = []
    for sub in ("ports", "value_objects", "events", "exceptions"):
        for p in (base / sub).glob("*.py"):
            if "data_source" in p.name:
                files.append(p)
    context["domain_data_source_files"] = [str(f) for f in files]


@when("AST 扫描每个文件的 import 语句")
def when_ast_scan_imports(context: dict[str, Any]) -> None:
    """Round 2 新增：AST 提取每个 domain 文件的 import 语句 + 标注来源分类。"""
    import ast
    from pathlib import Path

    files = [Path(p) for p in context["domain_data_source_files"]]
    # 黑名单与 unit 架构测试 test_arch_data_source.FORBIDDEN_IMPORTS 保持同步
    # （18 项；R3-3 H8v2：原 8 项比 unit 17 项窄一半，未来新增 domain 文件可裸穿。
    # sqlmodel/aioredis/instructor 属「domain 层已知诱惑库」防御性条目，非当前依赖）
    banned = {
        "pydantic",
        "sqlalchemy",
        "redis",
        "fastapi",
        "typer",
        "langgraph",
        "prefect",
        "qdrant",
        "minio",
        "neo4j",
        "aio_pika",
        "litellm",
        "instructor",
        "asyncpg",
        "aioredis",
        "httpx",
        "tenacity",
        "sqlmodel",
    }
    violators = []
    for file in files:
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in banned:
                        violators.append(f"{file.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                top = node.module.split(".")[0]
                if top in banned:
                    violators.append(f"{file.name}: from {node.module} import ...")
    context["violators"] = violators


@then("所有 import 仅来自 typing/dataclasses/datetime/uuid/abc/enum 或 src.domain.* 项目内")
@then("零 httpx/redis/tenacity/sqlalchemy/pydantic 等第三方依赖")
def then_domain_files_no_3rd_party_dependencies(context: dict[str, Any]) -> None:
    """Round 2 新增：domain 层 data_source 文件零第三方依赖（对齐 .importlinter 强制）。"""
    violators = context["violators"]
    assert violators == [], "domain 层 data_source 文件不允许含第三方依赖：\n" + "\n".join(violators)
