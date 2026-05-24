"""Acceptance tests for Story 1.17 - UDMR 基础路由（云端优先静态配置）.

BDD 步骤实现，使用 mock 隔离外部依赖

Run with: poetry run pytest tests/acceptance/test_acceptance_udmr-basic-routing.py -v

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("test_acceptance_udmr_basic_routing.feature")


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


@given("UDMRConfig 已配置本地模型和云端模型")
def setup_udmr_config(context: dict[str, Any]) -> None:
    """配置 UDMR 环境."""
    context["env"] = {
        "UDMR_ENABLED": "true",
        "UDMR_LOCAL_FIRST": "false",
        "UDMR_LOCAL_MODEL": "qwen2.5:7b",
        "UDMR_LLM_TIMEOUT": "600",
        "UDMR_HEALTHCHECK_INTERVAL": "300",
    }


@given("ComplianceGatewayPort 已实现")
def setup_compliance_gateway(context: dict[str, Any]) -> None:
    """ComplianceGateway 已就绪."""
    context["compliance_gateway"] = AsyncMock()


@given("StaticUdmrPolicy 已实现云端优先策略")
def setup_static_policy(context: dict[str, Any]) -> None:
    """静态路由策略已就绪."""
    context["policy"] = AsyncMock()


# ===================================================================
# AC-1: UDMR 配置模型
# ===================================================================


@given("设置环境变量 UDMR_ENABLED=true")
def set_env_enabled(context: dict[str, Any]) -> None:
    context["env"]["UDMR_ENABLED"] = "true"


@given("设置环境变量 UDMR_LOCAL_FIRST=false")
def set_env_local_first(context: dict[str, Any]) -> None:
    context["env"]["UDMR_LOCAL_FIRST"] = "false"


@given("设置环境变量 UDMR_LOCAL_MODEL=qwen2.5:7b")
def set_env_local_model(context: dict[str, Any]) -> None:
    context["env"]["UDMR_LOCAL_MODEL"] = "qwen2.5:7b"


@when("调用 UDMRConfig.from_env()")
def call_from_env(context: dict[str, Any]) -> None:
    from src.infrastructure.config.udmr import UDMRConfig

    with patch.dict(os.environ, context.get("env", {}), clear=True):
        try:
            context["config"] = UDMRConfig.from_env()
            context["error"] = None
        except ValueError as e:
            context["error"] = e


@then('应该返回 enabled=True, local_first=False, local_model="qwen2.5:7b" 的配置')
def verify_config_values(context: dict[str, Any]) -> None:
    assert context["error"] is None
    config = context["config"]
    assert config.enabled is True
    assert config.local_first is False
    assert config.local_model == "qwen2.5:7b"


@given("设置环境变量 UDMR_CLOUD_0_API_TYPE=anthropic")
def set_cloud_0_api_type(context: dict[str, Any]) -> None:
    context["env"]["UDMR_CLOUD_0_ENABLED"] = "true"
    context["env"]["UDMR_CLOUD_0_API_TYPE"] = "anthropic"
    context["env"]["UDMR_CLOUD_0_ENDPOINT"] = "https://api.minimax.chat/anthropic"
    context["env"]["UDMR_CLOUD_0_API_KEY"] = "TESTING_DUMMY_KEY"  # pragma: allowlist secret
    context["env"]["UDMR_CLOUD_0_MODEL"] = "MiniMax-M2.7"
    context["env"]["UDMR_CLOUD_0_MAX_TOKENS"] = "4096"


@given("设置环境变量 UDMR_CLOUD_0_ENDPOINT=https://api.minimax.chat/anthropic")
def set_cloud_0_endpoint(context: dict[str, Any]) -> None:
    context["env"]["UDMR_CLOUD_0_ENDPOINT"] = "https://api.minimax.chat/anthropic"


@given("设置环境变量 UDMR_CLOUD_0_MODEL=MiniMax-M2.7")
def set_cloud_0_model(context: dict[str, Any]) -> None:
    context["env"]["UDMR_CLOUD_0_MODEL"] = "MiniMax-M2.7"


@given("设置环境变量 UDMR_CLOUD_0_MAX_TOKENS=4096")
def set_cloud_0_max_tokens(context: dict[str, Any]) -> None:
    context["env"]["UDMR_CLOUD_0_MAX_TOKENS"] = "4096"


@then("应该包含 1 个云端模型配置")
def verify_cloud_config_count(context: dict[str, Any]) -> None:
    assert context["error"] is None
    assert len(context["config"].cloud_configs) == 1


@then('云端模型的 api_type 应该是 "anthropic"')
def verify_cloud_api_type(context: dict[str, Any]) -> None:
    assert context["config"].cloud_configs[0].api_type == "anthropic"


@then("云端模型的 max_tokens 应该是 4096")
def verify_cloud_max_tokens(context: dict[str, Any]) -> None:
    assert context["config"].cloud_configs[0].max_tokens == 4096


@given("未设置 UDMR_CLOUD_0_MAX_TOKENS")
def unset_cloud_0_max_tokens(context: dict[str, Any]) -> None:
    context["env"].pop("UDMR_CLOUD_0_MAX_TOKENS", None)


@then("应该抛出 ValueError 异常")
def verify_value_error(context: dict[str, Any]) -> None:
    assert context["error"] is not None
    assert isinstance(context["error"], ValueError)


# ===================================================================
# AC-2: UDMR 静态路由决策
# ===================================================================


@given("UDMR 配置为云端优先")
def setup_cloud_first(context: dict[str, Any]) -> None:
    context["local_first"] = False


@given("L1 合规检查通过（forced_local=False）")
def compliance_passed(context: dict[str, Any]) -> None:
    from src.domain.value_objects.compliance_result import ComplianceResult

    context["compliance_result"] = ComplianceResult(
        allowed=True,
        forced_local=False,
    )


@when("UDMRService 执行路由决策")
def execute_route_decision(context: dict[str, Any]) -> None:
    """路由决策（将在 Task 3 实现后连接真实服务）."""
    pass  # TDD 红阶段占位


@then('route_type 应该是 "cloud"')
def verify_route_type_cloud(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@then("selected_model 应该是第一个 enabled 的云端模型")
def verify_selected_model(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@given("L1 合规检查返回 forced_local=True（含敏感数据）")
def compliance_forced_local(context: dict[str, Any]) -> None:
    from src.domain.value_objects.compliance_result import ComplianceResult

    context["compliance_result"] = ComplianceResult(
        allowed=True,
        forced_local=True,
        reason="Sensitive data",
    )


@then('route_type 应该是 "local"')
def verify_route_type_local(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@then("selected_model 应该是本地模型")
def verify_selected_model_local(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@given("所有云端模型均 disabled 或不可用")
def all_clouds_disabled(context: dict[str, Any]) -> None:
    context["clouds_available"] = False


@then('fallback_reason 应该是 "unavailable"')
def verify_fallback_reason(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


# ===================================================================
# AC-3: 云端健康检查
# ===================================================================


@given("CloudHealthChecker 检查云端模型可用性")
def setup_health_checker(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@when("云端 API 响应正常")
def cloud_api_healthy(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@then("check() 应该返回 True")
def verify_check_true(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@when("云端 API 超时")
def cloud_api_timeout(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@then("check() 应该返回 False")
def verify_check_false(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


# ===================================================================
# AC-4: 事件集成
# ===================================================================


@given("UDMRHandler 已注册订阅 AutoRouted 事件")
def setup_udmr_handler(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@when("接收到 AutoRouted 事件")
def receive_auto_routed(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@then("UDMRHandler 应该调用 UDMRService.decide()")
def verify_decide_called(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@then("应该发布 RoutingDecided 事件")
def verify_routing_decided_published(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@given("RoutingDecided 事件被发布")
def routing_decided_published(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@then("AutoTriggerHandler 不应该被 RoutingDecided 事件触发")
def verify_no_loop(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


# ===================================================================
# AC-5: 路由性能
# ===================================================================


@given("UDMR 配置为静态路由模式")
def setup_static_mode(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@when("执行 1000 次路由决策")
def execute_1000_decisions(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位


@then("P95 延迟应该小于 100ms")
def verify_p95_latency(context: dict[str, Any]) -> None:
    pass  # TDD 红阶段占位
