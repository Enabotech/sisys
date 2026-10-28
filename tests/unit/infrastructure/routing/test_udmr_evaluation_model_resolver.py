"""UdmrEvaluationModelResolver 单元测试（Story 5.8——AC-2 UDMR in-band 消费链）。

真实 UDMR 决策链手工装配（DC-7 豁免面）：真实 UDMRService（十参数）+ 真实
StaticUdmrPolicy（测试 cloud_configs 注入）+ 真实 ComplianceGatewayImpl（**pipl_service
显式注入**——零参装配下 PIPL 正则分支被 `if self._pipl_service:` 门死不可达）+
真实 StaticTokenEstimator + 真实 build_cost_calculator（纯计算零 IO）+ 手写零 IO
publisher/决策日志替身 + 手写健康检查替身（True/False 可控路由方向）。

覆盖用例：cloud 路由逐字段匹配 / local 回退 / from_env 101 防御性包装 / 非硬编码
双配置矩阵 / 匹配失败 450（monkeypatch 变体——单测面）/ RoutingDecided 事件发布 /
UDMRTask 构造（wrapper 子类）。

Run with:
    poetry run pytest tests/unit/infrastructure/routing/test_udmr_evaluation_model_resolver.py -v
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.exceptions import AgentEvaluationError, ConfigurationError

_TEST_LOCAL_MODEL = "qwen2.5-eval-local"
_TEST_LLM_TIMEOUT = 30
_EVAL_TEXT = "最终回答：三层次进入策略（评估路由输入文本）"


def _make_cloud_config(model: str) -> Any:
    """测试云端模型配置（连接字段全非默认值——逐字段断言有判别力）。"""
    from src.infrastructure.config.udmr import CloudModelConfig

    return CloudModelConfig(
        api_type="openai",
        endpoint=f"https://{model}.example/v1",
        api_key=f"key-{model}",
        model=model,
        enabled=True,
        max_tokens=1024,
        temperature=0.5,
    )


class _RecordingEventPublisher:
    """零 IO 事件发布替身（duck-typing——5-7 先例同款形态）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(event.event_id) if hasattr(event, "event_id") else "",
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


class _RecordingDecisionLogRepository:
    """零 IO 路由决策日志仓储替身（save 调用记录——决策日志断言锚）。"""

    def __init__(self) -> None:
        self.saved_logs: list[Any] = []

    async def save(self, log_entry: Any) -> None:
        self.saved_logs.append(log_entry)


class _StubHealthChecker:
    """健康检查替身（外部探测面豁免——True/False 可控路由方向；双方法防 isinstance）。"""

    def __init__(self, healthy: bool) -> None:
        self._healthy = healthy
        self.check_calls = 0

    async def check(self) -> bool:
        self.check_calls += 1
        return self._healthy

    async def close(self) -> None:
        return None


class _RecordingUdmrService:
    """UDMRService 子类 wrapper（覆写 decide 记录 task 后 super() 委托真实链——
    R1-F7：决策日志与 RoutingDecided 均不含 task.input，不可作 input 断言锚）。"""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.captured_tasks: list[Any] = []

    async def decide(self, task: Any, causation_id: Any = None) -> Any:
        self.captured_tasks.append(task)
        return await self._inner.decide(task, causation_id)


def _build_udmr_service(
    policy_models: tuple[str, ...],
    *,
    health_healthy: bool = True,
    publisher: Any = None,
    log_repo: Any = None,
) -> Any:
    """真实 UDMR 决策链装配（pipl_service 显式注入——PIPL 分支可达前提）。

    零 IO 替身经 Any 中转注入（duck-typing 结构满足端口契约——mypy 具体类型
    参数不接受替身类，Any 是测试替身注入的惯用通道）。
    """
    from src.domain.services.udmr_service import UDMRService
    from src.infrastructure.config.udmr import build_cost_calculator
    from src.infrastructure.monitoring.static_token_estimator import StaticTokenEstimator
    from src.infrastructure.routing.udmr_policy import StaticUdmrPolicy
    from src.infrastructure.security.compliance_gateway_impl import ComplianceGatewayImpl
    from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

    resolved_log_repo: Any = log_repo if log_repo is not None else _RecordingDecisionLogRepository()
    resolved_publisher: Any = publisher if publisher is not None else _RecordingEventPublisher()

    return UDMRService(
        compliance_gateway=ComplianceGatewayImpl(pipl_service=PIPLComplianceServiceImpl()),
        policy=StaticUdmrPolicy(
            cloud_configs=[_make_cloud_config(m) for m in policy_models],
            local_model=_TEST_LOCAL_MODEL,
        ),
        health_checker=_StubHealthChecker(health_healthy),
        log_repo=resolved_log_repo,
        publisher=resolved_publisher,
        local_first=False,
        local_model=_TEST_LOCAL_MODEL,
        llm_timeout=_TEST_LLM_TIMEOUT,
        token_estimator=StaticTokenEstimator(),
        cost_calculator=build_cost_calculator(),
    )


def _build_resolver(
    policy_models: tuple[str, ...],
    resolver_models: tuple[str, ...],
    *,
    health_healthy: bool = True,
    publisher: Any = None,
    log_repo: Any = None,
    wrap_recorder: bool = False,
) -> tuple[Any, Any]:
    """构造 resolver（+可选 wrapper 服务——返回 (resolver, recorder)）。"""
    from src.infrastructure.routing.udmr_evaluation_model_resolver import UdmrEvaluationModelResolver

    service = _build_udmr_service(policy_models, health_healthy=health_healthy, publisher=publisher, log_repo=log_repo)
    recorder = None
    if wrap_recorder:
        recorder = _RecordingUdmrService(service)
        service = recorder
    resolver = UdmrEvaluationModelResolver(
        udmr_service=service,
        cloud_configs=[_make_cloud_config(m) for m in resolver_models],
        local_model=_TEST_LOCAL_MODEL,
        llm_timeout=_TEST_LLM_TIMEOUT,
    )
    return resolver, recorder


class TestCloudRouting:
    """cloud 路由（健康 True → decide 产出 cloud → 六连接字段 + timeout 匹配）。"""

    async def test_cloud_route_config_matches(self) -> None:
        """config.model == cloud.model + endpoint/api_key/timeout 逐字段相等。"""
        resolver, _ = _build_resolver(("test-model-a",), ("test-model-a",), health_healthy=True)
        expected_cloud = _make_cloud_config("test-model-a")
        config = await resolver.resolve_config(_EVAL_TEXT)
        assert config.model == expected_cloud.model
        assert config.endpoint == expected_cloud.endpoint
        assert config.api_key == expected_cloud.api_key
        assert config.api_type == expected_cloud.api_type
        assert config.max_tokens == expected_cloud.max_tokens
        assert config.timeout == _TEST_LLM_TIMEOUT, "timeout ← llm_timeout（build_default_llm_config 先例）"

    async def test_routing_decided_event_published(self) -> None:
        """RoutingDecided 事件经替身捕获（route_type/selected_model 与 config 对应）。"""
        from src.domain.events.routing_events import RoutingDecided

        publisher = _RecordingEventPublisher()
        resolver, _ = _build_resolver(("test-model-a",), ("test-model-a",), publisher=publisher)
        config = await resolver.resolve_config(_EVAL_TEXT)
        events = [e for e in publisher.published_events if isinstance(e, RoutingDecided)]
        assert len(events) == 1
        assert events[0].route_type == "cloud"
        assert events[0].selected_model == config.model

    async def test_decision_log_persisted(self) -> None:
        """决策日志持久化调用发生（零 IO 替身捕获）。"""
        log_repo = _RecordingDecisionLogRepository()
        resolver, _ = _build_resolver(("test-model-a",), ("test-model-a",), log_repo=log_repo)
        config = await resolver.resolve_config(_EVAL_TEXT)
        assert len(log_repo.saved_logs) == 1
        assert log_repo.saved_logs[0].route_type == "cloud"
        assert log_repo.saved_logs[0].selected_model == config.model

    async def test_udmr_task_construction_via_wrapper(self) -> None:
        """UDMRTask 构造断言（wrapper 记录 task——input/data_residency/allowed_models）。"""
        from src.domain.value_objects.udmr_task import UDMRTask

        resolver, recorder = _build_resolver(("test-model-a",), ("test-model-a",), wrap_recorder=True)
        await resolver.resolve_config(_EVAL_TEXT)
        assert recorder is not None and len(recorder.captured_tasks) == 1
        task = recorder.captured_tasks[0]
        assert isinstance(task, UDMRTask)
        assert task.input == _EVAL_TEXT
        assert task.data_residency == "CHINA_DOMESTIC"


class TestLocalFallback:
    """local 回退（健康 False → decide 内部回退 → local 分支）。"""

    async def test_local_fallback_config(self) -> None:
        """config.model == selected_model == local_model + 连接字段来自 from_env 形态。"""
        from src.domain.ports.llm_client import LLMConfig

        resolver, _ = _build_resolver(("test-model-a",), ("test-model-a",), health_healthy=False)
        config = await resolver.resolve_config(_EVAL_TEXT)
        assert config.model == _TEST_LOCAL_MODEL, "local 分支 model 应对齐路由产物"
        # 判别力前提：local_model ≠ from_env 默认 qwen2.5:7b（replace 恒等变异锚失效防线）
        from_env_defaults = LLMConfig.from_env()
        assert _TEST_LOCAL_MODEL != from_env_defaults.model
        # 连接字段随 from_env（LLMConfig 无 route 字段——只断可观察面）
        assert config.endpoint == from_env_defaults.endpoint
        assert config.api_key == from_env_defaults.api_key
        assert config.api_type == from_env_defaults.api_type

    async def test_local_fallback_event_route_type(self) -> None:
        """回退后 RoutingDecided.route_type == local（fallback_reason=health_check_failed）。"""
        from src.domain.events.routing_events import RoutingDecided

        publisher = _RecordingEventPublisher()
        resolver, _ = _build_resolver(("test-model-a",), ("test-model-a",), health_healthy=False, publisher=publisher)
        await resolver.resolve_config(_EVAL_TEXT)
        events = [e for e in publisher.published_events if isinstance(e, RoutingDecided)]
        assert len(events) == 1
        assert events[0].route_type == "local"
        assert events[0].selected_model == _TEST_LOCAL_MODEL
        assert events[0].fallback_reason == "health_check_failed"

    async def test_from_env_configuration_error_wrapped_450(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """from_env 抛 101 注入 → 450 包装（防御性契约——R1-F10 降级网完整性）。"""
        from src.domain.ports.llm_client import LLMConfig

        def _broken_from_env() -> Any:
            raise ConfigurationError(message="模拟 LLM_* 环境损坏（101 注入）")

        monkeypatch.setattr(LLMConfig, "from_env", _broken_from_env)
        resolver, _ = _build_resolver(("test-model-a",), ("test-model-a",), health_healthy=False)
        with pytest.raises(AgentEvaluationError) as exc_info:
            await resolver.resolve_config(_EVAL_TEXT)
        caught = exc_info.value
        assert caught.code == "EXCEPTION_450"
        assert caught.context["reason"] == "model_resolution"
        assert isinstance(caught.__cause__, ConfigurationError)


class TestNonHardcodedMatrix:
    """非硬编码判别（双配置矩阵——同一 resolver 代码不同注入 → 不同模型）。"""

    async def test_dual_config_matrix(self) -> None:
        """cloud_configs=[A] → config.model==A；[B] → ==B（硬编码实现必红）。"""
        resolver_a, _ = _build_resolver(("test-model-a",), ("test-model-a",))
        config_a = await resolver_a.resolve_config(_EVAL_TEXT)
        assert config_a.model == "test-model-a"

        resolver_b, _ = _build_resolver(("test-model-b",), ("test-model-b",))
        config_b = await resolver_b.resolve_config(_EVAL_TEXT)
        assert config_b.model == "test-model-b"
        assert config_a.model != config_b.model, "config.model 应随注入变化（非硬编码锚）"


class TestMatchFailure:
    """匹配失败 450（selected_model 不在 resolver cloud_configs——配置漂移）。"""

    async def test_drift_config_dual_injection(self) -> None:
        """漂移双注入（policy=B × resolver=A）——零 monkeypatch 全真实链。"""
        resolver, _ = _build_resolver(("test-model-b",), ("test-model-a",))
        with pytest.raises(AgentEvaluationError) as exc_info:
            await resolver.resolve_config(_EVAL_TEXT)
        caught = exc_info.value
        assert caught.code == "EXCEPTION_450"
        assert caught.context["reason"] == "model_resolution"
        assert caught.context.get("selected_model") == "test-model-b"
        available = caught.context.get("available_models")
        assert available is not None and "test-model-a" in available

    async def test_monkeypatched_decide_unknown_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """monkeypatch decide 返回不存在模型（单测变体——验收禁 mock 红线外）。"""
        from src.domain.events.routing_events import RoutingDecided

        resolver, _ = _build_resolver(("test-model-a",), ("test-model-a",))

        async def _fake_decide(task: Any, causation_id: Any = None) -> RoutingDecided:
            return RoutingDecided(route_type="cloud", selected_model="ghost-model-x")

        monkeypatch.setattr(resolver._udmr_service, "decide", _fake_decide)
        with pytest.raises(AgentEvaluationError) as exc_info:
            await resolver.resolve_config(_EVAL_TEXT)
        caught = exc_info.value
        assert caught.context.get("selected_model") == "ghost-model-x"
        assert "test-model-a" in caught.context.get("available_models", "")

    async def test_match_failure_after_event_published(self) -> None:
        """漂移场景事件先于 450 发布（decide 真实链完成副作用）。"""
        from src.domain.events.routing_events import RoutingDecided

        publisher = _RecordingEventPublisher()
        resolver, _ = _build_resolver(("test-model-b",), ("test-model-a",), publisher=publisher)
        with pytest.raises(AgentEvaluationError):
            await resolver.resolve_config(_EVAL_TEXT)
        events = [e for e in publisher.published_events if isinstance(e, RoutingDecided)]
        assert len(events) == 1, "匹配失败前 decide() 应已完成事件发布"
        assert events[0].selected_model == "test-model-b"
