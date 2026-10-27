"""PhoenixTracer 单元测试（Story 5.7 — Task 1 TDD 循环 B）

覆盖：实例化双路径（注入通道可观测[R2-1 双源解析] / 自建路径 Resource+sampler）
+ initialize 状态机（幂等实例闩 / enabled=false 不装配 / 外来 set 检测 warning）
+ create_span 双源解析与降级（无 tracer 来源 yield None / OTel 异常降级零上抛）
+ reset_for_testing 双复位（Once 闩锁重建——单复位突变本用例红）+ SpanHandle
契约行为断言（set_attribute/record_exception 经 exporter 可观测——禁 isinstance
假绿，runtime_checkable 只查方法名存在）。

OTel 全局状态隔离：文件级 function-scope autouse 双复位兜底（R3-2——本文件
含 initialize 用例，复位义务正交条款；兼修同文件场景间泄漏）。

Run with:
    poetry run pytest tests/unit/infrastructure/monitoring/test_phoenix_tracer.py -v
"""

from __future__ import annotations

import logging
from typing import Any, Generator

import pytest

from src.infrastructure.config.phoenix import PhoenixConfig
from src.infrastructure.monitoring.phoenix_tracer import PhoenixTracer


@pytest.fixture(autouse=True)
def _otel_global_state_isolation() -> Generator[None, None, None]:
    """OTel 全局状态 function 级双复位（前置 + teardown——凡 initialize 用例一律复位义务）。"""
    PhoenixTracer.reset_for_testing()
    yield
    PhoenixTracer.reset_for_testing()


def _make_enabled_config(**overrides: Any) -> PhoenixConfig:
    """测试启用配置（endpoint 生产形态仅装配不外联——测试全用 InMemory 导出器注入）。"""
    base: dict[str, Any] = {
        "enabled": True,
        "endpoint": "http://localhost:4317",
        "project_name": "sisys-agent",
        "sampling_ratio": 1.0,
    }
    base.update(overrides)
    return PhoenixConfig(**base)


def _make_injectable() -> tuple[Any, Any]:
    """注入通道材料：新 TracerProvider + SimpleSpanProcessor + InMemorySpanExporter。"""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _assert_proxy_global() -> None:
    """全局 provider 未 set 判据（proxy 态——NoOp 前提钉死）。"""
    import opentelemetry.trace as otel_trace
    from opentelemetry.trace import ProxyTracerProvider

    assert isinstance(otel_trace.get_tracer_provider(), ProxyTracerProvider)


class TestPhoenixTracerInstantiation:
    """实例化与 create_span 双源解析（R2-1——注入 provider 优先，None 降级判据是「无 tracer 来源」）。"""

    def test_injected_provider_create_span_without_initialize(self) -> None:
        """注入通道可观测：未 initialize 亦产真 span（注入 provider 优先——照抄 initialize 状态守卫会死锁）。"""
        provider, exporter = _make_injectable()
        tracer = PhoenixTracer(config=_make_enabled_config(), tracer_provider=provider)

        with tracer.create_span("inject-channel-probe") as handle:
            assert handle is not None, "注入通道应产真 span（R2-1 双源解析）"
            handle.set_attribute("probe.key", "value")

        spans = exporter.get_finished_spans()
        assert [s.name for s in spans] == ["inject-channel-probe"]
        assert spans[0].attributes["probe.key"] == "value"

    def test_no_source_yield_none(self) -> None:
        """降级判据：无可用 tracer 来源（未注入且未 initialize）→ yield None（零开销降级）。"""
        _assert_proxy_global()
        tracer = PhoenixTracer(config=_make_enabled_config())

        with tracer.create_span("noop-probe") as handle:
            assert handle is None

    def test_constructor_no_global_side_effect(self) -> None:
        """构造器纯赋值（R3-13——event_metrics 模板构造器 enabled 时调 init() 是照抄陷阱）。"""
        PhoenixTracer(config=_make_enabled_config())

        _assert_proxy_global()


class TestInitializeStateMachine:
    """initialize 状态机（幂等实例闩 / enabled=false / 外来 set 检测 / 自建装配）。"""

    def test_initialize_injected_sets_global(self) -> None:
        """注入路径：initialize 履行全局 set 唯一职责（全局 == 注入实例）。"""
        import opentelemetry.trace as otel_trace

        provider, _ = _make_injectable()
        tracer = PhoenixTracer(config=_make_enabled_config(), tracer_provider=provider)

        assert tracer.initialize() is True
        assert otel_trace.get_tracer_provider() is provider

    def test_initialize_idempotent_same_instance(self, caplog: pytest.LogCaptureFixture) -> None:
        """幂等行为断言：同实例两次 initialize → 1 span → exporter 恰收 1（重复装配会收 2）。"""
        provider, exporter = _make_injectable()
        tracer = PhoenixTracer(config=_make_enabled_config(), tracer_provider=provider)
        assert tracer.initialize() is True

        with caplog.at_level(logging.WARNING):
            assert tracer.initialize() is True  # 实例闩：同实例再入静默 True

        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
        with tracer.create_span("idempotent-probe") as handle:
            assert handle is not None
        assert len(exporter.get_finished_spans()) == 1

    def test_initialize_disabled_returns_false_and_no_assembly(self) -> None:
        """enabled=false：返回 False + 不装配不设全局（NoOp 天然降级）。"""
        provider, _ = _make_injectable()
        tracer = PhoenixTracer(config=_make_enabled_config(enabled=False), tracer_provider=provider)

        assert tracer.initialize() is False
        _assert_proxy_global()

    def test_initialize_foreign_set_detected_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """外来 set 检测：全局已非 proxy 且非本实例所 set → logger.warning 显式提示（杜绝静默双 setter）。"""
        import opentelemetry.trace as otel_trace

        provider_first, _ = _make_injectable()
        first = PhoenixTracer(config=_make_enabled_config(), tracer_provider=provider_first)
        assert first.initialize() is True

        provider_second, _ = _make_injectable()
        second = PhoenixTracer(config=_make_enabled_config(), tracer_provider=provider_second)
        with caplog.at_level(logging.WARNING):
            result = second.initialize()

        assert result is True  # 返回既有状态（追踪可用——全局已有人设置）
        assert otel_trace.get_tracer_provider() is provider_first  # 全局保持既有
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert warnings, "外来 set 检测应 logger.warning（不静默）"

    def test_initialize_selfbuilt_resource_and_sampler(self) -> None:
        """自建路径：Resource service.name（OD-1 project_name 映射）+ TraceIdRatioBased 采样率。"""
        import opentelemetry.trace as otel_trace
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        tracer = PhoenixTracer(config=_make_enabled_config(sampling_ratio=0.5))

        assert tracer.initialize() is True
        provider: Any = otel_trace.get_tracer_provider()  # API 类型无 resource/sampler 属性声明（SDK 实现面——运行时在位）
        assert provider.resource.attributes["service.name"] == "sisys-agent"
        assert isinstance(provider.sampler, TraceIdRatioBased)
        assert provider.sampler.rate == 0.5

    def test_initialize_failure_degrades_and_latches(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """装配失败降级 + 失败闩锁（R1-F2 补测——DC-7 契约明文却曾零覆盖）：返回 False + 再入静默仍 False + 不 set 全局。"""

        def _boom() -> Any:
            raise RuntimeError("注入装配失败（R1-F2）")

        tracer = PhoenixTracer(config=_make_enabled_config())
        monkeypatch.setattr(tracer, "_build_production_provider", _boom)

        with caplog.at_level(logging.WARNING):
            assert tracer.initialize() is False

        assert tracer.initialize() is False, "失败态实例闩：再入静默返回既有 False（无重试通道）"
        _assert_proxy_global()
        assert [r for r in caplog.records if r.levelno >= logging.WARNING], "降级路径应 logger.warning（不静默）"


class TestCreateSpanDegradation:
    """create_span 降级路径（DC-7——追踪失败降级不上抛）。"""

    def test_otel_exception_degrades_to_none_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """OTel 异常注入（坏 provider 对象）→ logger.warning 降级 yield None（零上抛）。"""
        from typing import cast

        class _BrokenProvider:
            """坏 provider 替身（get_tracer 缺失——触发 OTel 解析异常）。"""

        tracer = PhoenixTracer(
            config=_make_enabled_config(),
            tracer_provider=cast(Any, _BrokenProvider()),
        )

        with caplog.at_level(logging.WARNING):
            with tracer.create_span("broken-probe") as handle:
                assert handle is None, "OTel 异常应降级 yield None"

        assert [r for r in caplog.records if r.levelno >= logging.WARNING], "降级路径应 logger.warning（不静默）"

    def test_attributes_batch_write(self) -> None:
        """attributes 参数批量写入（进入开 span 后逐键 set）。"""
        provider, exporter = _make_injectable()
        tracer = PhoenixTracer(config=_make_enabled_config(), tracer_provider=provider)
        payload = {"str.key": "值", "bool.key": True, "int.key": 7, "float.key": 0.5, "tuple.key": ("a", "b")}

        with tracer.create_span("attrs-probe", attributes=payload) as handle:
            assert handle is not None

        span = exporter.get_finished_spans()[0]
        for key, value in payload.items():
            assert span.attributes[key] == value


class TestConsumerExceptionPassthrough:
    """消费方段异常契约（R1-F1——with 体内业务异常原样穿透：不被吞、不被 RuntimeError 改写）。"""

    def test_consumer_exception_passes_through_unchanged(self) -> None:
        """真 span 路径：原异常对象原样上抛 + span ERROR + exception 事件恰 1（框架 __exit__ 兜底）。"""
        from opentelemetry.trace import StatusCode

        from src.domain.exceptions.agent_exceptions import AgentWorkflowError

        provider, exporter = _make_injectable()
        tracer = PhoenixTracer(config=_make_enabled_config(), tracer_provider=provider)
        boom = AgentWorkflowError(agent_id="a1", phase="verify", reason="消费方注入异常（R1-F1）")

        with pytest.raises(AgentWorkflowError) as excinfo:
            with tracer.create_span("consumer-boom") as handle:
                assert handle is not None
                raise boom

        assert excinfo.value is boom, "应透传同一异常对象（R1-F1——不被吞/不被 RuntimeError 替换）"
        span = exporter.get_finished_spans()[0]
        assert span.status.status_code == StatusCode.ERROR
        exception_events = [e for e in span.events if e.name == "exception"]
        assert len(exception_events) == 1, "exception 事件应恰 1（use_span __exit__ 兜底——无显式重复调用）"

    def test_consumer_exception_passes_through_on_degraded_none(self) -> None:
        """降级 None 路径：消费方异常同样原样穿透（降级出口在 try 外——R1-F1 四路径矩阵）。"""
        from src.domain.exceptions.agent_exceptions import AgentWorkflowError

        tracer = PhoenixTracer(config=_make_enabled_config(enabled=False))  # 无 tracer 来源（未注入未 initialize）
        boom = AgentWorkflowError(agent_id="a2", phase="plan", reason="降级路径注入异常（R1-F1）")

        with pytest.raises(AgentWorkflowError) as excinfo:
            with tracer.create_span("degraded-boom") as handle:
                assert handle is None
                raise boom

        assert excinfo.value is boom, "降级出口消费方异常同样原样穿透（不被吞）"


class TestResetForTestingDoubleRestore:
    """reset_for_testing 双复位（变量 + Once 闩锁重建——锁定的 OTel 1.44.0 单复位不恢复 re-set）。"""

    def test_reset_restores_reinit_capability(self) -> None:
        """initialize → 双复位 → 再 initialize → 新 provider 可收 span（单复位突变本用例红——变异锚）。"""
        import opentelemetry.trace as otel_trace

        provider_first, exporter_first = _make_injectable()
        first = PhoenixTracer(config=_make_enabled_config(), tracer_provider=provider_first)
        assert first.initialize() is True
        with first.create_span("before-reset") as handle:
            assert handle is not None
        assert len(exporter_first.get_finished_spans()) == 1

        PhoenixTracer.reset_for_testing()
        _assert_proxy_global()

        provider_second, exporter_second = _make_injectable()
        second = PhoenixTracer(config=_make_enabled_config(), tracer_provider=provider_second)
        assert second.initialize() is True, "双复位后 re-set 能力应恢复（Once 闩锁重建）"
        assert otel_trace.get_tracer_provider() is provider_second

        with second.create_span("after-reset") as handle:
            assert handle is not None
        assert len(exporter_second.get_finished_spans()) == 1


class TestSpanHandleBehaviorContract:
    """SpanHandle 协议契约行为断言（duck-type OTel Span——禁 isinstance 假绿）。"""

    def test_handle_set_attribute_observable_via_exporter(self) -> None:
        """行为断言：handle.set_attribute → exporter span.attributes 含键值（5.8 消费面）。"""
        from src.application.ports.agent_tracing import SpanAttributeKeys, SpanHandle

        provider, exporter = _make_injectable()
        tracer = PhoenixTracer(config=_make_enabled_config(), tracer_provider=provider)

        with tracer.create_span("handle-contract") as handle:
            assert handle is not None
            assert isinstance(handle, SpanHandle)  # duck-type 天然满足（结构性自证——判别力由下方行为断言承载）
            handle.set_attribute(SpanAttributeKeys.EVAL_HALLUCINATION_SCORE, 0.08)

        span = exporter.get_finished_spans()[0]
        assert span.attributes[SpanAttributeKeys.EVAL_HALLUCINATION_SCORE] == 0.08

    def test_handle_record_exception_observable_via_exporter(self) -> None:
        """行为断言：handle.record_exception → span events 含 exception 事件（5.9/异常路径消费面）。"""
        provider, exporter = _make_injectable()
        tracer = PhoenixTracer(config=_make_enabled_config(), tracer_provider=provider)

        with tracer.create_span("handle-exception") as handle:
            assert handle is not None
            handle.record_exception(ValueError("契约行为探针异常"))

        span = exporter.get_finished_spans()[0]
        assert any(event.name == "exception" for event in span.events)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
