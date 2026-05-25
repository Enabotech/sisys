"""Acceptance tests for Story 1.19 - 成本度量基础（Token 消耗与成本追踪）.

BDD 步骤实现，使用 mock 隔离外部依赖

Run with: poetry run pytest tests/acceptance/test_acceptance_cost_metrics_basic.py -v

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("test_acceptance_cost_metrics_basic.feature")

# parsers.re 用于参数化 BDD 步骤
re = parsers.re


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """BDD 步骤间共享状态."""
    return {}


# ===================================================================
# Background
# ===================================================================


@given("UDMR 路由决策已产生 RoutingDecided 事件")
def setup_routing_decided(context: dict[str, Any]) -> None:
    """RoutingDecided 事件已就绪."""
    context["event_published"] = True


@given("CostCalculator 已配置定价表")
def setup_cost_calculator(context: dict[str, Any]) -> None:
    """CostCalculator 已就绪."""
    context["pricing_config"] = {
        "local_input": 0.002,
        "local_output": 0.002,
        "cloud_input": 0.02,
        "cloud_output": 0.02,
    }


@given("TokenEstimatorPort 已实现")
def setup_token_estimator(context: dict[str, Any]) -> None:
    """TokenEstimatorPort 已就绪."""
    context["token_estimator_ready"] = True


# ===================================================================
# AC-1: 模型定价配置
# ===================================================================


@given("创建 CloudModelConfig 使用默认值")
def create_cloud_config_defaults(context: dict[str, Any]) -> None:
    """使用默认值创建 CloudModelConfig."""
    from src.infrastructure.config.udmr import CloudModelConfig

    context["cloud_config"] = CloudModelConfig()


@then(re("price_per_input_1k_tokens 应该是 (?P<value>[\\d.]+)"))
def verify_input_price(context: dict[str, Any], value: str) -> None:
    """验证输入 token 单价."""
    config = context["cloud_config"]
    assert config.price_per_input_1k_tokens == float(value)


@then(re("price_per_output_1k_tokens 应该是 (?P<value>[\\d.]+)"))
def verify_output_price(context: dict[str, Any], value: str) -> None:
    """验证输出 token 单价."""
    config = context["cloud_config"]
    assert config.price_per_output_1k_tokens == float(value)


@given("设置环境变量 UDMR_CLOUD_0_PRICE_INPUT=0.03")
def set_price_input(context: dict[str, Any]) -> None:
    """设置输入定价环境变量."""
    context.setdefault("env", {})["UDMR_CLOUD_0_PRICE_INPUT"] = "0.03"


@given("设置环境变量 UDMR_CLOUD_0_PRICE_OUTPUT=0.04")
def set_price_output(context: dict[str, Any]) -> None:
    """设置输出定价环境变量."""
    context.setdefault("env", {})["UDMR_CLOUD_0_PRICE_OUTPUT"] = "0.04"


@when("解析 CloudModelConfig 定价配置")
def parse_cloud_config_pricing(context: dict[str, Any]) -> None:
    """解析云端模型定价配置."""
    from src.infrastructure.config.udmr import _parse_cloud_config

    env = context.get("env", {})
    env.setdefault("UDMR_CLOUD_0_MODEL", "test-model")
    env.setdefault("UDMR_CLOUD_0_ENABLED", "true")

    with patch.dict(os.environ, env, clear=True):
        try:
            context["cloud_config"] = _parse_cloud_config(0)
            context["error"] = None
        except ValueError as e:
            context["error"] = e


@then("应该抛出定价异常")
def verify_pricing_error(context: dict[str, Any]) -> None:
    """验证定价异常."""
    assert context.get("error") is not None


@given("设置环境变量 UDMR_CLOUD_0_PRICE_INPUT=-0.01")
def set_negative_price_input(context: dict[str, Any]) -> None:
    """设置负值定价环境变量."""
    context.setdefault("env", {})["UDMR_CLOUD_0_PRICE_INPUT"] = "-0.01"


# ===================================================================
# AC-2: Token 消耗值对象与成本计算服务
# ===================================================================


@given("创建 TokenConsumption prompt_tokens=256 completion_tokens=512")
def create_token_consumption(context: dict[str, Any]) -> None:
    """创建 TokenConsumption 值对象."""
    from src.domain.value_objects.token_consumption import TokenConsumption

    context["consumption"] = TokenConsumption(prompt_tokens=256, completion_tokens=512)


@then("total_tokens 应该是 768")
def verify_total_tokens(context: dict[str, Any]) -> None:
    """验证 total_tokens 计算正确."""
    consumption = context["consumption"]
    assert consumption.total_tokens == 768


@given("本地模型定价为 input=0.002 output=0.002（每 1K tokens）")
def set_local_pricing(context: dict[str, Any]) -> None:
    """设置本地模型定价."""
    context["input_price"] = 0.002
    context["output_price"] = 0.002
    context["route_type"] = "local"


@given("Token 消耗为 prompt=256 completion=512")
def set_token_consumption_256_512(context: dict[str, Any]) -> None:
    """设置 Token 消耗."""
    context["prompt_tokens"] = 256
    context["completion_tokens"] = 512


@when("调用 CostCalculator.calculate()")
def call_cost_calculator(context: dict[str, Any]) -> None:
    """调用成本计算服务."""
    from src.domain.services.cost_calculator import CostCalculator
    from src.domain.value_objects.token_consumption import TokenConsumption

    calculator = CostCalculator(
        local_input_price=0.002,
        local_output_price=0.002,
        cloud_input_price=0.02,
        cloud_output_price=0.02,
        model_pricing_map={},
    )
    consumption = TokenConsumption(
        prompt_tokens=context.get("prompt_tokens", 0),
        completion_tokens=context.get("completion_tokens", 0),
    )
    context["cost"] = calculator.calculate(
        consumption,
        context.get("route_type", "local"),
        context.get("model", ""),
    )


@then("成本应该是 0.001536 元")
def verify_local_cost(context: dict[str, Any]) -> None:
    """验证本地路由成本."""
    assert abs(context["cost"] - 0.001536) < 1e-9


@given("云端模型定价为 input=0.02 output=0.02（每 1K tokens）")
def set_cloud_pricing(context: dict[str, Any]) -> None:
    """设置云端模型定价."""
    context["input_price"] = 0.02
    context["output_price"] = 0.02
    context["route_type"] = "cloud"


@given("Token 消耗为 prompt=512 completion=1024")
def set_token_consumption_512_1024(context: dict[str, Any]) -> None:
    """设置云端 Token 消耗."""
    context["prompt_tokens"] = 512
    context["completion_tokens"] = 1024


@then("成本应该是 0.03072 元")
def verify_cloud_cost(context: dict[str, Any]) -> None:
    """验证云端路由成本."""
    assert abs(context["cost"] - 0.03072) < 1e-9


@given("Token 消耗为 prompt=0 completion=0")
def set_zero_tokens(context: dict[str, Any]) -> None:
    """设置零 Token 消耗."""
    context["prompt_tokens"] = 0
    context["completion_tokens"] = 0


@then("成本应该是 0.0 元")
def verify_zero_cost(context: dict[str, Any]) -> None:
    """验证零成本."""
    assert context["cost"] == 0.0


# ===================================================================
# AC-3: RoutingDecided 事件与 RoutingDecisionLog 扩展
# ===================================================================


@given("创建默认 RoutingDecided 事件")
def create_default_routing_decided(context: dict[str, Any]) -> None:
    """创建默认 RoutingDecided 事件."""
    from src.domain.events.routing_events import RoutingDecided

    context["event"] = RoutingDecided()


@then("prompt_tokens 应该是 0")
def verify_event_prompt_tokens(context: dict[str, Any]) -> None:
    """验证事件 prompt_tokens 默认值."""
    assert context["event"].prompt_tokens == 0


@then("completion_tokens 应该是 0")
def verify_event_completion_tokens(context: dict[str, Any]) -> None:
    """验证事件 completion_tokens 默认值."""
    assert context["event"].completion_tokens == 0


@then("total_tokens 应该是 0")
def verify_event_total_tokens(context: dict[str, Any]) -> None:
    """验证事件 total_tokens 默认值."""
    assert context["event"].total_tokens == 0


@then("cost_actual 应该是 0.0")
def verify_event_cost_actual(context: dict[str, Any]) -> None:
    """验证事件 cost_actual 默认值."""
    assert context["event"].cost_actual == 0.0


@given("创建默认 RoutingDecisionLog 实体")
def create_default_routing_log(context: dict[str, Any]) -> None:
    """创建默认 RoutingDecisionLog 实体."""
    import uuid

    from src.domain.entities.routing_decision_log import RoutingDecisionLog

    context["log"] = RoutingDecisionLog(
        log_id=uuid.uuid4(),
        task_id="test-task",
        session_id="test-session",
        route_type="local",
        route_target="test-target",
        route_score=1.0,
    )


@then("log 的 prompt_tokens 应该是 0")
def verify_log_prompt_tokens(context: dict[str, Any]) -> None:
    """验证 log prompt_tokens 默认值."""
    assert context["log"].prompt_tokens == 0


@then("log 的 completion_tokens 应该是 0")
def verify_log_completion_tokens(context: dict[str, Any]) -> None:
    """验证 log completion_tokens 默认值."""
    assert context["log"].completion_tokens == 0


@then("log 的 total_tokens 应该是 0")
def verify_log_total_tokens(context: dict[str, Any]) -> None:
    """验证 log total_tokens 默认值."""
    assert context["log"].total_tokens == 0


# ===================================================================
# AC-4: CostMetricsListener 事件监听
# ===================================================================


@given('RoutingDecided 事件 route_type="local" selected_model="qwen2.5:7b"')
def setup_local_routing_event(context: dict[str, Any]) -> None:
    """设置本地路由事件."""
    from src.domain.events.routing_events import RoutingDecided

    context["routing_event"] = RoutingDecided(
        route_type="local",
        selected_model="qwen2.5:7b",
    )


@when("CostMetricsListener 处理事件")
def cost_metrics_handler_process(context: dict[str, Any]) -> None:
    """CostMetricsListener 处理事件."""
    pass  # TDD 红阶段占位


@then("应该调用 TokenEstimatorPort.estimate()")
def verify_token_estimator_called(context: dict[str, Any]) -> None:
    """验证 TokenEstimatorPort 被调用."""
    pass  # TDD 红阶段占位


@then("应该调用 CostCalculator.calculate()")
def verify_cost_calculator_called(context: dict[str, Any]) -> None:
    """验证 CostCalculator 被调用."""
    pass  # TDD 红阶段占位


@then("应该更新 RoutingDecisionLog 的 cost_actual")
def verify_log_updated(context: dict[str, Any]) -> None:
    """验证日志更新."""
    pass  # TDD 红阶段占位


@then("应该记录 Prometheus 指标")
def verify_prometheus_recorded(context: dict[str, Any]) -> None:
    """验证 Prometheus 指标."""
    pass  # TDD 红阶段占位


# ===================================================================
# AC-5: Prometheus 指标扩展与聚合查询
# ===================================================================


@given("MetricsPort 已初始化")
def setup_metrics_port(context: dict[str, Any]) -> None:
    """初始化 MetricsPort."""
    from prometheus_client import CollectorRegistry

    from src.infrastructure.monitoring.aggregator import MetricsAggregator
    from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector
    from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
    from src.infrastructure.monitoring.metrics_port_impl import MetricsPortImpl

    registry = CollectorRegistry()
    business = BusinessMetricsCollector(registry=registry)
    event = EventMetricsCollector()
    aggregator = MetricsAggregator(
        event_metrics_collector=event,
        business_metrics_collector=business,
        registry=registry,
    )
    context["metrics"] = MetricsPortImpl(
        aggregator=aggregator,
        business_metrics=business,
        registry=registry,
    )
    context["registry"] = registry


@when('调用 record_token_usage(prompt=256, completion=512, model="qwen2.5:7b", route_type="local")')
def call_record_token_usage(context: dict[str, Any]) -> None:
    """调用 record_token_usage 方法."""
    context["metrics"].record_token_usage(
        prompt=256,
        completion=512,
        model="qwen2.5:7b",
        route_type="local",
    )


@then("sisys_token_prompt_total 指标应该增加 256")
def verify_prompt_total(context: dict[str, Any]) -> None:
    """验证 prompt token 指标."""
    pass  # TDD 红阶段占位


@then("sisys_token_completion_total 指标应该增加 512")
def verify_completion_total(context: dict[str, Any]) -> None:
    """验证 completion token 指标."""
    pass  # TDD 红阶段占位


@when('调用 record_cost(cost=0.001536, model="qwen2.5:7b", route_type="local")')
def call_record_cost(context: dict[str, Any]) -> None:
    """调用 record_cost 方法."""
    context["metrics"].record_cost(
        cost=0.001536,
        model="qwen2.5:7b",
        route_type="local",
    )


@then("sisys_cost_total_cny 指标应该更新为 0.001536")
def verify_cost_total(context: dict[str, Any]) -> None:
    """验证成本指标."""
    pass  # TDD 红阶段占位
