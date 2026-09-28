"""Story 4.1b — ToolExecutionEngine $DATA_SOURCE 集成单元测试

验证 Engine Execute 阶段增强（宿主机侧采集 + preamble 注入）：
- resolver=None 时零行为变化（回归保护，Story 4.4 兼容：__init__ 签名不变，set 后注入）
- 注入 resolver 后：标记 → 白名单校验 → 并发采集 → DATA_SOURCES preamble 内联注入
- 白名单违规 → BusinessRuleViolationError(207) 不包装直传
- 全部失败 → 首个数据源异常不包装直传（412/413）
- 部分失败 → 成功源注入 + 执行继续
- EvidencePackage.data_sources 溯源元数据（source/freshness/confidence）
- context.extensions 缺 tool_metadata → 207（无白名单依据）

Mock 仅限端口适配器（LLM/Sandbox），Resolver 使用真实服务 + 测试替身适配器。
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.ports.skill_loader import ToolMetadata
from src.application.services.data_source_resolver import DataSourceResolverService
from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.domain.entities.tool import Tool
from src.domain.events.data_source_events import DataSourceFetchFailed
from src.domain.exceptions import (
    BusinessRuleViolationError,
    ConfigurationError,
    DataSourceRateLimitError,
    DataSourceUnavailableError,
    TimeoutError,
)
from src.domain.ports.data_source import DataSourceQuery
from src.domain.ports.tool_execution_repository import ToolExecutionRepositoryPort
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)
from src.domain.value_objects.tool_execution import ExecutionContext, ToolCall, ToolResultStatus
from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

# ===================================================================
# 测试替身与工厂
# ===================================================================


class _StubAdapter:
    """可编程数据源适配器桩。"""

    def __init__(self, name: str, error: Exception | None = None) -> None:
        self._ref = DataSourceRef(
            name=name, url=f"https://fake.local/{name}", ttl_seconds=3600, api_type=DataSourceApiType.REST_JSON
        )
        self.call_count = 0
        self._error = error

    def get_metadata(self) -> DataSourceRef:
        return self._ref

    async def health_check(self) -> bool:
        return self._error is None

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        self.call_count += 1
        if self._error is not None:
            raise self._error
        now = datetime.now(UTC)
        return DataSourceResult(
            source_name=self._ref.name,
            payload=json.dumps({"q": query.query, "v": 1.0}),
            source_timestamp=now,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=now, ttl_seconds=3600),
            confidence=0.9,
        )


class _NullCache:
    """L1CachePort 空实现（Engine 集成测试不验证缓存语义，避免状态干扰）。"""

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        return True

    async def set_with_ttl(self, key: str, value: str, ttl: int) -> bool:
        return True

    async def delete(self, key: str) -> bool:
        return True

    async def delete_pattern(self, pattern: str) -> int:
        return 0

    async def exists(self, key: str) -> bool:
        return False

    async def set_nx(self, key: str, value: str, ttl: int) -> bool:
        return True

    async def eval(self, script: str, keys: list[str], args: list[str]) -> Any:
        return None


def _make_metadata(*names: str) -> ToolMetadata:
    return ToolMetadata(
        tool_name="测试工具",
        slug="test-tool",
        category="environment_analysis",
        input_schema={},
        output_schema={},
        data_sources=tuple(
            DataSourceRef(name=n, url=f"https://fake.local/{n}", api_type=DataSourceApiType.REST_JSON) for n in names
        ),
    )


def _make_engine(
    code: str,
    sandbox_codes: list[str],
    tool_execution_repository: Any = None,
) -> ToolExecutionEngine:
    """构建真实 Engine（Mock LLM/Sandbox 端口适配器；仓储可选注入——R3-4 K2）。"""

    async def _llm_dispatch(prompt: str, response_schema: Any) -> str:
        if "生成代码" in prompt:
            return code
        return "ok"

    llm = AsyncMock()
    llm.structured_generate = AsyncMock(side_effect=_llm_dispatch)

    async def _sandbox_execute(session_id: str, code_arg: str, **_kwargs: Any) -> dict[str, Any]:
        sandbox_codes.append(code_arg)
        return {"status": "ok", "output": "done"}

    sandbox = AsyncMock()
    sandbox.start_container = AsyncMock()
    sandbox.execute_code = AsyncMock(side_effect=_sandbox_execute)
    sandbox.stop_container = AsyncMock()

    return ToolExecutionEngine(llm_client=llm, sandbox=sandbox, tool_execution_repository=tool_execution_repository)


async def _run_engine(
    engine: ToolExecutionEngine,
    metadata: ToolMetadata | None,
) -> Any:
    tool = Tool(tool_id=uuid.uuid4(), name="测试工具", slug="test-tool")
    extensions: dict[str, Any] = {}
    if metadata is not None:
        extensions["tool_metadata"] = metadata
    return await engine.execute(
        tool_id=tool.tool_id,
        tool=tool,
        tool_call=ToolCall(tool_id=tool.tool_id, arguments={}),
        context=ExecutionContext(tenant_id=uuid.uuid4(), session_id=f"sess-{uuid.uuid4().hex[:8]}", extensions=extensions),
    )


# ===================================================================
# 测试
# ===================================================================


class TestEngineWithoutResolver:
    """resolver=None 语义（R3-2 G6 重写：含标记代码 fail-fast 101，干净代码零行为变化）。

    原「标记代码直通沙箱」语义已废弃——resolver 缺失 + 含标记 = 组合根装配漂移，
    fail-fast ConfigurationError(101) 远优于沙箱 SyntaxError 被误包装为
    ToolExecutionFailedError（排障方向误导）。
    """

    @pytest.mark.asyncio
    async def test_no_resolver_marker_code_fails_fast(self) -> None:
        """含未掩码标记 + resolver 未注入 → 101 fail-fast，代码永不达沙箱"""
        from src.domain.exceptions import ConfigurationError

        code = '$DATA_SOURCE("world-bank", "GDP")\nprint(1)'
        sandbox_codes: list[str] = []
        engine = _make_engine(code, sandbox_codes)
        with pytest.raises(ConfigurationError) as exc_info:
            await _run_engine(engine, _make_metadata("world-bank"))
        assert exc_info.value.code == "EXCEPTION_101"
        assert exc_info.value.context.get("marker_count") == 1
        assert sandbox_codes == []  # 快速失败：含标记代码不进沙箱（原语义会 SyntaxError 白烧沙箱）

    @pytest.mark.asyncio
    async def test_clean_code_without_resolver_passes_through(self) -> None:
        """干净代码（无标记）+ resolver 未注入 → 4.4 零行为变化（直通成功）"""
        code = "print(1)"
        sandbox_codes: list[str] = []
        engine = _make_engine(code, sandbox_codes)
        result = await _run_engine(engine, _make_metadata("world-bank"))
        assert result.status == ToolResultStatus.SUCCESS
        assert sandbox_codes[0] == code
        assert result.evidence_package is not None
        assert result.evidence_package.data_sources == ()

    @pytest.mark.asyncio
    async def test_dollar_inside_string_without_resolver_passes_through(self) -> None:
        """字符串字面量内的 $DATA_SOURCE 文本（掩码后 markers=()）+ resolver 未注入 →
        直通成功（锁死「干净代码与 resolver 注入正交」边界，防 fail-fast 误伤）"""
        code = 'print("$DATA_SOURCE(x)")\nprint(1)'
        sandbox_codes: list[str] = []
        engine = _make_engine(code, sandbox_codes)
        result = await _run_engine(engine, _make_metadata("world-bank"))
        assert result.status == ToolResultStatus.SUCCESS
        assert sandbox_codes[0] == code

    @pytest.mark.asyncio
    async def test_malformed_marker_without_resolver_raises_201_before_101(self) -> None:
        """畸形标记 + resolver 未注入 → 标记解析在前，201 先于 101（语法错误是根因）"""
        from src.domain.exceptions import ValidationError

        code = '$DATA_SOURCE("world-bank")\nprint(1)'  # 缺第二参数
        engine = _make_engine(code, [])
        with pytest.raises(ValidationError):
            await _run_engine(engine, _make_metadata("world-bank"))

    @pytest.mark.asyncio
    async def test_set_resolver_none_revokes_injection(self) -> None:
        """setter 撤销注入生效：撤销后干净代码成功且无注入（4.4 setter 契约保护）"""
        clean_code = "print(1)"
        sandbox_codes: list[str] = []
        engine = _make_engine(clean_code, sandbox_codes)
        resolver = DataSourceResolverService(
            adapters={"world-bank": _StubAdapter("world-bank")}, cache=_NullCache(), event_publisher=InMemoryEventBus()
        )
        engine.set_data_source_resolver(resolver)
        engine.set_data_source_resolver(None)  # 撤销注入
        result = await _run_engine(engine, _make_metadata("world-bank"))
        assert result.status == ToolResultStatus.SUCCESS
        assert sandbox_codes[0] == clean_code  # 撤销后干净代码直通、无 preamble 注入


class TestEngineWithResolver:
    @pytest.mark.asyncio
    async def test_fetched_event_bound_to_execution_aggregate(self) -> None:
        """事件 aggregate_id == engine 内部 ToolExecution.execution_id（R3-4 K2 端到端绑定）

        execution_id 由 engine 内部生成不外露——经仓储端口 Mock 捕获 save(execution)
        取证。断言锚点：事件字段与捕获的聚合根比较（execution_id/aggregate_id 的
        自反式断言恒真——`__post_init__` 无条件设 aggregate_id=execution_id）。
        删除 resolver 发布路径的 with_execution_id 调用（事件回落自生成 uuid4）
        本用例必红——原全仓零覆盖。
        """
        from src.domain.events.data_source_events import DataSourceFetched
        from src.domain.ports.tool_execution_repository import ToolExecutionRepositoryPort

        code = '$DATA_SOURCE("world-bank", "GDP")\nprint(DATA_SOURCES)'
        sandbox_codes: list[str] = []
        repo = AsyncMock(spec=ToolExecutionRepositoryPort)
        engine = _make_engine(code, sandbox_codes, tool_execution_repository=repo)
        bus = InMemoryEventBus()
        resolver = DataSourceResolverService(
            adapters={"world-bank": _StubAdapter("world-bank")}, cache=_NullCache(), event_publisher=bus
        )
        engine.set_data_source_resolver(resolver)
        result = await _run_engine(engine, _make_metadata("world-bank"))
        assert result.status == ToolResultStatus.SUCCESS
        saved = repo.save.call_args.args[0]  # 成功路径持久化的聚合根（save 恰 1 次）
        fetched = [e for e in bus.published_events if isinstance(e, DataSourceFetched)]
        assert len(fetched) == 1
        assert fetched[0].execution_id == saved.execution_id  # 与聚合根比较（非自反）
        assert fetched[0].aggregate_id == saved.execution_id
        assert fetched[0].aggregate_type == "ToolExecution"

    @pytest.mark.asyncio
    async def test_preamble_injected_and_metadata_attached(self) -> None:
        code = '$DATA_SOURCE("world-bank", "GDP")\nprint(DATA_SOURCES)'
        sandbox_codes: list[str] = []
        engine = _make_engine(code, sandbox_codes)
        bus = InMemoryEventBus()
        resolver = DataSourceResolverService(
            adapters={"world-bank": _StubAdapter("world-bank")}, cache=_NullCache(), event_publisher=bus
        )
        engine.set_data_source_resolver(resolver)

        result = await _run_engine(engine, _make_metadata("world-bank"))

        assert result.status == ToolResultStatus.SUCCESS
        # preamble 注入（单行 JSON 字面量）
        preamble = sandbox_codes[0].split("\n", 1)[0]
        assert preamble.startswith("DATA_SOURCES = ")
        assert "world-bank" in preamble
        # 证据包溯源元数据
        assert result.evidence_package is not None
        metas = result.evidence_package.data_sources
        assert len(metas) == 1
        assert metas[0].source_name == "world-bank"
        assert 0.0 < metas[0].freshness_score <= 1.0
        assert metas[0].confidence == 0.9

    @pytest.mark.asyncio
    async def test_whitelist_violation_propagates_unwrapped(self) -> None:
        code = '$DATA_SOURCE("newsapi", "tech")\nprint(1)'
        sandbox_codes: list[str] = []
        engine = _make_engine(code, sandbox_codes)
        resolver = DataSourceResolverService(
            adapters={"world-bank": _StubAdapter("world-bank")}, cache=_NullCache(), event_publisher=InMemoryEventBus()
        )
        engine.set_data_source_resolver(resolver)
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await _run_engine(engine, _make_metadata("world-bank"))
        assert exc_info.value.code == "EXCEPTION_207"
        assert not sandbox_codes  # 未进入沙箱执行

    @pytest.mark.asyncio
    async def test_missing_tool_metadata_raises_207(self) -> None:
        code = '$DATA_SOURCE("world-bank", "GDP")\nprint(1)'
        sandbox_codes: list[str] = []
        engine = _make_engine(code, sandbox_codes)
        resolver = DataSourceResolverService(
            adapters={"world-bank": _StubAdapter("world-bank")}, cache=_NullCache(), event_publisher=InMemoryEventBus()
        )
        engine.set_data_source_resolver(resolver)
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await _run_engine(engine, None)  # 无 tool_metadata → 无白名单依据
        assert exc_info.value.code == "EXCEPTION_207"

    @pytest.mark.asyncio
    async def test_configuration_error_propagates_unwrapped(self) -> None:
        """R2-2-P1-3：适配器抛 ConfigurationError(101)（如 401/403 鉴权失败）经 Engine 不包装直传。

        回归锁：except 直传元组若回退掉 ConfigurationError，本用例必须变红。
        """
        code = '$DATA_SOURCE("newsapi", "tech")\nprint(1)'
        sandbox_codes: list[str] = []
        engine = _make_engine(code, sandbox_codes)
        resolver = DataSourceResolverService(
            adapters={
                "newsapi": _StubAdapter(
                    "newsapi",
                    error=ConfigurationError(
                        message="数据源 newsapi 鉴权失败（HTTP 401）",
                        context={"source_name": "newsapi", "status_code": 401},
                    ),
                )
            },
            cache=_NullCache(),
            event_publisher=InMemoryEventBus(),
        )
        engine.set_data_source_resolver(resolver)
        with pytest.raises(ConfigurationError) as exc_info:
            await _run_engine(engine, _make_metadata("newsapi"))
        assert exc_info.value.code == "EXCEPTION_101"
        assert not sandbox_codes  # 未进入沙箱执行

    @pytest.mark.asyncio
    async def test_domain_timeout_error_propagates_unwrapped(self) -> None:
        """R2-2-P1-3：适配器抛领域 TimeoutError(302)（采集超时）经 Engine 不包装直传。"""
        code = '$DATA_SOURCE("world-bank", "GDP")\nprint(1)'
        sandbox_codes: list[str] = []
        engine = _make_engine(code, sandbox_codes)
        resolver = DataSourceResolverService(
            adapters={
                "world-bank": _StubAdapter(
                    "world-bank",
                    error=TimeoutError(message="数据源 world-bank 请求超时", context={"source_name": "world-bank"}),
                )
            },
            cache=_NullCache(),
            event_publisher=InMemoryEventBus(),
        )
        engine.set_data_source_resolver(resolver)
        with pytest.raises(TimeoutError) as exc_info:
            await _run_engine(engine, _make_metadata("world-bank"))
        assert exc_info.value.code == "EXCEPTION_302"

    @pytest.mark.asyncio
    async def test_all_failed_raises_first_error_unwrapped(self) -> None:
        code = '$DATA_SOURCE("newsapi", "tech")\nprint(1)'
        sandbox_codes: list[str] = []
        bus = InMemoryEventBus()
        repo = AsyncMock(spec=ToolExecutionRepositoryPort)
        engine = _make_engine(code, sandbox_codes, tool_execution_repository=repo)
        resolver = DataSourceResolverService(
            adapters={
                "newsapi": _StubAdapter(
                    "newsapi", error=DataSourceRateLimitError(message="429", context={"source_name": "newsapi"})
                )
            },
            cache=_NullCache(),
            event_publisher=bus,
        )
        engine.set_data_source_resolver(resolver)
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            await _run_engine(engine, _make_metadata("newsapi"))
        assert exc_info.value.code == "EXCEPTION_412"
        # R3-4 K2：失败事件与 FAILED 聚合根绑定（resolver 发布在先、engine except
        # 分支 save 在后——与捕获的 execution.execution_id 比较方有判别力）
        failed = [e for e in bus.published_events if isinstance(e, DataSourceFetchFailed)]
        assert len(failed) == 1
        saved = repo.save.call_args.args[0]
        assert failed[0].execution_id == saved.execution_id
        assert failed[0].aggregate_id == saved.execution_id

    @pytest.mark.asyncio
    async def test_partial_failure_injects_success_only(self) -> None:
        code = '$DATA_SOURCE("world-bank", "GDP")\n$DATA_SOURCE("eurostat", "EU")\nprint(DATA_SOURCES)'
        sandbox_codes: list[str] = []
        engine = _make_engine(code, sandbox_codes)
        resolver = DataSourceResolverService(
            adapters={
                "world-bank": _StubAdapter("world-bank"),
                "eurostat": _StubAdapter(
                    "eurostat",
                    error=DataSourceUnavailableError(message="down", context={"source_name": "eurostat"}),
                ),
            },
            cache=_NullCache(),
            event_publisher=InMemoryEventBus(),
        )
        engine.set_data_source_resolver(resolver)
        result = await _run_engine(engine, _make_metadata("world-bank", "eurostat"))
        assert result.status == ToolResultStatus.SUCCESS
        preamble = sandbox_codes[0].split("\n", 1)[0]
        assert "world-bank" in preamble
        assert "eurostat" not in preamble

    @pytest.mark.asyncio
    async def test_no_marker_no_resolver_calls(self) -> None:
        """代码无标记时：resolver 已注入但零采集调用（直通）。"""
        code = "print('plain code')"
        sandbox_codes: list[str] = []
        engine = _make_engine(code, sandbox_codes)
        stub = _StubAdapter("world-bank")
        resolver = DataSourceResolverService(
            adapters={"world-bank": stub}, cache=_NullCache(), event_publisher=InMemoryEventBus()
        )
        engine.set_data_source_resolver(resolver)
        result = await _run_engine(engine, _make_metadata("world-bank"))
        assert result.status == ToolResultStatus.SUCCESS
        assert stub.call_count == 0
        assert sandbox_codes[0] == code
