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
from src.domain.exceptions import (
    BusinessRuleViolationError,
    DataSourceRateLimitError,
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
) -> ToolExecutionEngine:
    """构建真实 Engine（Mock LLM/Sandbox 端口适配器）。"""

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

    return ToolExecutionEngine(llm_client=llm, sandbox=sandbox)


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
    """resolver=None 零行为变化（Story 4.4 回归保护）。"""

    @pytest.mark.asyncio
    async def test_no_resolver_marker_code_passes_through(self) -> None:
        code = '$DATA_SOURCE("world-bank", "GDP")\nprint(1)'
        sandbox_codes: list[str] = []
        engine = _make_engine(code, sandbox_codes)
        result = await _run_engine(engine, _make_metadata("world-bank"))
        assert result.status == ToolResultStatus.SUCCESS
        # 代码原样送沙箱（无 preamble 注入）
        assert sandbox_codes[0] == code
        # 证据包无数据源元数据
        assert result.evidence_package is not None
        assert result.evidence_package.data_sources == ()

    @pytest.mark.asyncio
    async def test_set_resolver_none_revokes_injection(self) -> None:
        code = '$DATA_SOURCE("world-bank", "GDP")\nprint(1)'
        sandbox_codes: list[str] = []
        engine = _make_engine(code, sandbox_codes)
        resolver = DataSourceResolverService(
            adapters={"world-bank": _StubAdapter("world-bank")}, cache=_NullCache(), event_publisher=InMemoryEventBus()
        )
        engine.set_data_source_resolver(resolver)
        engine.set_data_source_resolver(None)  # 撤销注入
        await _run_engine(engine, _make_metadata("world-bank"))
        assert sandbox_codes[0] == code


class TestEngineWithResolver:
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
    async def test_all_failed_raises_first_error_unwrapped(self) -> None:
        code = '$DATA_SOURCE("newsapi", "tech")\nprint(1)'
        sandbox_codes: list[str] = []
        engine = _make_engine(code, sandbox_codes)
        resolver = DataSourceResolverService(
            adapters={
                "newsapi": _StubAdapter(
                    "newsapi", error=DataSourceRateLimitError(message="429", context={"source_name": "newsapi"})
                )
            },
            cache=_NullCache(),
            event_publisher=InMemoryEventBus(),
        )
        engine.set_data_source_resolver(resolver)
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            await _run_engine(engine, _make_metadata("newsapi"))
        assert exc_info.value.code == "EXCEPTION_412"

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
