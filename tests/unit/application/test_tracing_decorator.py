"""@trace 装饰器单元测试（Story 5.7 — Task 2 TDD 循环 A）

覆盖装饰器五面：正常（span 自动创建 + 名正确）/ attributes 参数化写入 / 异常
（record_exception + status ERROR + re-raise 原异常——零吞异常）/ NoOp 降级
（全局未 set 零 span 主链等价——注入通道观察哨）/ functools.wraps 签名保真；
另锁定 SpanAttributeKeys/SpanNames 常量（键字符串单一真源——5.8/5.9 防拼写漂移）。

测试通道（SSOT）：装饰器走 OTel 全局 API——文件级 function-scope autouse
fixture 每用例「双复位 → 注入 provider 经 initialize 全局 set → teardown 双复位」
（R3-6：每用例自足对抗 xdist 分发不确定性，NoOp 用例无需尾序约束；全局未 set
前提用例[NoOp]同样前置双复位——前提测试条款 R3-2）。

Run with:
    poetry run pytest tests/unit/application/test_tracing_decorator.py -v
"""

from __future__ import annotations

from typing import Any, Generator

import pytest

from src.application.tracing import trace

_INSTRUMENTING_NAME = "sisys.agent"


@pytest.fixture(autouse=True)
def _tracing_global_channel() -> Generator[dict[str, Any], None, None]:
    """装饰器测试统一通道：注入 provider 经 initialize 全局 set（唯一通道）。

    每用例独立 provider/exporter（function-scope——NoOp 用例 reset 后不影响
    同 worker 后续用例）；teardown 双复位（复位义务正交条款）。
    """
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from src.infrastructure.config.phoenix import PhoenixConfig
    from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

    PhoenixTracer.reset_for_testing()
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = PhoenixTracer(
        config=PhoenixConfig(enabled=True, endpoint="http://localhost:4317", project_name="sisys-agent", sampling_ratio=1.0),
        tracer_provider=provider,
    )
    assert tracer.initialize() is True
    channel = {"exporter": exporter, "provider": provider}
    yield channel
    PhoenixTracer.reset_for_testing()


class TestTraceDecorator:
    """@trace 装饰器五面（正常/属性/异常/NoOp/签名）。"""

    def test_decorated_async_span_created_with_name(self, _tracing_global_channel: dict[str, Any]) -> None:
        """正常面：被装饰 async 函数执行 → span 自动创建且名正确（epics 钦定名）。"""

        @trace("agent_execution")
        async def _sample(value: int) -> int:
            return value * 2

        import asyncio

        assert asyncio.new_event_loop().run_until_complete(_sample(21)) == 42
        spans = _tracing_global_channel["exporter"].get_finished_spans()
        assert [s.name for s in spans] == ["agent_execution"]

    def test_decorator_attributes_written(self, _tracing_global_channel: dict[str, Any]) -> None:
        """属性面：attributes 参数进入时批量写入。"""

        @trace("agent.plan", attributes={"phase.depth": 1, "phase.reentry": True})
        async def _sample() -> str:
            return "ok"

        import asyncio

        asyncio.new_event_loop().run_until_complete(_sample())
        span = _tracing_global_channel["exporter"].get_finished_spans()[0]
        assert span.attributes["phase.depth"] == 1
        assert span.attributes["phase.reentry"] is True

    def test_exception_recorded_status_error_and_reraise(self, _tracing_global_channel: dict[str, Any]) -> None:
        """异常面：record_exception + status ERROR + 原异常对象透传（零吞异常——装饰器不改异常语义）。"""
        from opentelemetry.trace import StatusCode

        from src.domain.exceptions.agent_exceptions import AgentWorkflowError

        boom = AgentWorkflowError(agent_id="a1", phase="verify", reason="注入异常")

        @trace("agent.verify")
        async def _sample() -> None:
            raise boom

        import asyncio

        loop = asyncio.new_event_loop()
        with pytest.raises(AgentWorkflowError) as excinfo:
            loop.run_until_complete(_sample())
        loop.close()

        assert excinfo.value is boom, "应透传同一异常对象（零吞异常）"
        span = _tracing_global_channel["exporter"].get_finished_spans()[0]
        assert span.status.status_code == StatusCode.ERROR
        assert any(event.name == "exception" for event in span.events)

    def test_noop_zero_span_when_global_unset(self) -> None:
        """NoOp 面：全局未 set（proxy 态前提）零 span 且主链行为等价（观察哨恒零——无旁路泄漏）。"""
        import asyncio

        import opentelemetry.trace as otel_trace
        from opentelemetry.trace import ProxyTracerProvider

        from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer

        PhoenixTracer.reset_for_testing()  # 前提测试条款：NoOp 断言「未 set」前置双复位
        assert isinstance(otel_trace.get_tracer_provider(), ProxyTracerProvider), "NoOp 前提：全局应 proxy 态"

        sentinel_provider, sentinel_exporter = _make_sentinel()  # 注入通道待命不 initialize（读法丙）

        @trace("agent_execution")
        async def _sample(value: int) -> int:
            return value + 1

        loop = asyncio.new_event_loop()
        assert loop.run_until_complete(_sample(41)) == 42  # NoOp 下主链行为等价
        loop.close()

        assert len(sentinel_exporter.get_finished_spans()) == 0, "观察哨应零 span（无旁路泄漏）"

    def test_wraps_signature_preserved(self) -> None:
        """签名面：functools.wraps 保 __name__/__doc__/__wrapped__（mypy 泛型签名不窄化前提）。"""

        @trace("agent.reflect")
        async def _documented_method(arg_a: str, arg_b: int = 3) -> str:
            """docstring 锚."""
            return arg_a * arg_b

        assert _documented_method.__name__ == "_documented_method"
        assert _documented_method.__doc__ == "docstring 锚."
        assert hasattr(_documented_method, "__wrapped__")


class TestSpanConstants:
    """SpanAttributeKeys/SpanNames 常量锁定（键字符串单一真源——AC-3.2 元断言）。"""

    def test_eval_drift_four_keys_literal(self) -> None:
        """四键逐字断言（epics 三键 + confidence_accuracy 键形增设）。"""
        from src.application.ports.agent_tracing import SpanAttributeKeys

        assert SpanAttributeKeys.EVAL_HALLUCINATION_SCORE == "eval.hallucination_score"
        assert SpanAttributeKeys.EVAL_CONTEXT_RELEVANCE == "eval.context_relevance"
        assert SpanAttributeKeys.EVAL_CONFIDENCE_ACCURACY == "eval.confidence_accuracy"
        assert SpanAttributeKeys.DRIFT_DETECTED == "drift.detected"

    def test_mvp_ten_keys_literal(self) -> None:
        """MVP 十项键常量逐字（数据源钉死见 AC-3）。"""
        from src.application.ports.agent_tracing import SpanAttributeKeys

        expected = {
            "AGENT_ID": "agent.id",
            "AGENT_NAME": "agent.name",
            "AGENT_ROLE": "agent.role",
            "AGENT_STARTUP_CONTEXT_TOKENS": "agent.startup_context_tokens",
            "AGENT_ACTIVE_SKILL_COUNT": "agent.active_skill_count",
            "WORKFLOW_STATUS": "workflow.status",
            "WORKFLOW_RETRY_COUNT": "workflow.retry_count",
            "WORKFLOW_EXECUTED_PHASES": "workflow.executed_phases",
            "EVAL_CONFIDENCE": "eval.confidence",
            "EVIDENCE_INPUT_HASH": "evidence.input_hash",
        }
        for attr, literal in expected.items():
            assert getattr(SpanAttributeKeys, attr) == literal

    def test_epics_three_keys_subset_meta(self) -> None:
        """子集式元断言（R1-4）：epics L1726-1728 三键 ⊆ 注册表且逐字相等。"""
        from src.application.ports.agent_tracing import SpanAttributeKeys

        epics_keys = {"eval.hallucination_score", "eval.context_relevance", "drift.detected"}
        registered = {
            value for name, value in vars(SpanAttributeKeys).items() if not name.startswith("_") and isinstance(value, str)
        }
        assert epics_keys <= registered

    def test_span_names_constants(self) -> None:
        """SpanNames 常量：agent_execution 根（epics 钦定）+ agent. 前缀（对齐 executed_phases 枚举）。"""
        from src.application.ports.agent_tracing import SpanNames

        assert SpanNames.AGENT_EXECUTION == "agent_execution"
        assert SpanNames.PHASE_PREFIX == "agent."


def _make_sentinel() -> tuple[Any, Any]:
    """注入通道观察哨材料（不 set 全局——守护「不经全局的旁路泄漏」）。"""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
