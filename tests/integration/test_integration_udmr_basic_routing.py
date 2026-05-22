"""Integration tests for UDMR basic routing.

端到端验证 UDMR 管线：AutoRouted → UDMRHandler → UDMRService → RoutingDecided

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from src.application.event_handlers.udmr_handler import UDMRHandler
from src.domain.events.auto_route_events import AutoRouted
from src.domain.events.routing_events import RoutingDecided
from src.domain.services.udmr_service import UDMRService
from src.infrastructure.config.udmr import CloudModelConfig
from src.infrastructure.routing.udmr_policy import StaticUdmrPolicy


def _make_cloud(model: str = "MiniMax-M2.7") -> CloudModelConfig:
    """辅助构造 CloudModelConfig."""
    return CloudModelConfig(
        api_type="anthropic",
        endpoint="https://api.example.com",
        api_key="TESTING_DUMMY_KEY",
        model=model,
        enabled=True,
        max_tokens=4096,
    )


@pytest.fixture
def mock_compliance_gateway() -> AsyncMock:
    """Mock ComplianceGatewayPort."""
    from src.domain.value_objects.compliance_result import ComplianceResult

    gw = AsyncMock()
    gw.check.return_value = ComplianceResult(allowed=True, forced_local=False)
    return gw


@pytest.fixture
def mock_health_checker() -> AsyncMock:
    """Mock HealthCheckPort."""
    checker = AsyncMock()
    checker.check.return_value = True
    return checker


@pytest.fixture
def mock_log_repo() -> AsyncMock:
    """Mock RoutingDecisionLogRepository."""
    return AsyncMock()


@pytest.fixture
def mock_publisher() -> AsyncMock:
    """Mock EventPublisher."""
    return AsyncMock()


@pytest.fixture
def mock_event_bus() -> AsyncMock:
    """Mock DualChannelEventBus."""
    bus = AsyncMock()
    bus.subscribe_async.return_value = None
    return bus


@pytest.fixture
def policy() -> StaticUdmrPolicy:
    """真实 StaticUdmrPolicy 实例."""
    return StaticUdmrPolicy(
        cloud_configs=[_make_cloud("MiniMax-M2.7")],
        local_model="qwen2.5:7b",
        local_first=False,
    )


@pytest.fixture
def udmr_service(
    mock_compliance_gateway: AsyncMock,
    policy: StaticUdmrPolicy,
    mock_health_checker: AsyncMock,
    mock_log_repo: AsyncMock,
    mock_publisher: AsyncMock,
) -> UDMRService:
    """真实 UDMRService 实例."""
    return UDMRService(
        compliance_gateway=mock_compliance_gateway,  # type: ignore[arg-type]
        policy=policy,
        health_checker=mock_health_checker,
        log_repo=mock_log_repo,
        publisher=mock_publisher,
        local_first=False,
        local_model="qwen2.5:7b",
    )


@pytest.fixture
def handler(
    udmr_service: UDMRService,
    mock_event_bus: AsyncMock,
) -> UDMRHandler:
    """真实 UDMRHandler 实例."""
    return UDMRHandler(
        udmr_service=udmr_service,
        event_bus=mock_event_bus,
        enabled=True,
    )


# ===================================================================
# 端到端集成测试
# ===================================================================


class TestUDMREndToEnd:
    """UDMR 管线端到端测试."""

    @pytest.mark.asyncio
    async def test_auto_routed_to_routing_decided(
        self,
        handler: UDMRHandler,
        mock_publisher: AsyncMock,
    ) -> None:
        """AutoRouted → UDMRHandler → RoutingDecided."""
        event = AutoRouted(
            session_id="session-e2e",
            task_context={"input": "test integration"},
            route_type="hash",
            route_target="agent-1",
        )

        result = await handler.on_routed(event)

        assert result is not None
        assert isinstance(result, RoutingDecided)
        assert result.route_type == "cloud"
        assert result.selected_model == "MiniMax-M2.7"

    @pytest.mark.asyncio
    async def test_forced_local_routing(
        self,
        mock_compliance_gateway: AsyncMock,
        policy: StaticUdmrPolicy,
        mock_health_checker: AsyncMock,
        mock_log_repo: AsyncMock,
        mock_publisher: AsyncMock,
    ) -> None:
        """L1 合规强制本地路由."""
        from src.domain.value_objects.compliance_result import ComplianceResult
        from src.domain.value_objects.udmr_task import UDMRTask

        mock_compliance_gateway.check.return_value = ComplianceResult(allowed=True, forced_local=True, reason="PII detected")

        service = UDMRService(
            compliance_gateway=mock_compliance_gateway,  # type: ignore[arg-type]
            policy=policy,
            health_checker=mock_health_checker,
            log_repo=mock_log_repo,
            publisher=mock_publisher,
        )

        task = UDMRTask(task_id=uuid.uuid4(), input="sensitive data")
        result = await service.decide(task)

        assert result.route_type == "local"
        assert result.selected_model == "qwen2.5:7b"

    @pytest.mark.asyncio
    async def test_cloud_unavailable_fallback(
        self,
        mock_compliance_gateway: AsyncMock,
        mock_health_checker: AsyncMock,
        mock_log_repo: AsyncMock,
        mock_publisher: AsyncMock,
    ) -> None:
        """云端不可用回退本地."""
        from src.domain.value_objects.udmr_task import UDMRTask

        # 所有云端 disabled
        policy = StaticUdmrPolicy(
            cloud_configs=[],
            local_model="qwen2.5:7b",
        )

        service = UDMRService(
            compliance_gateway=mock_compliance_gateway,  # type: ignore[arg-type]
            policy=policy,
            health_checker=mock_health_checker,
            log_repo=mock_log_repo,
            publisher=mock_publisher,
        )

        task = UDMRTask(task_id=uuid.uuid4())
        result = await service.decide(task)

        assert result.route_type == "local"
        assert result.fallback_reason == "unavailable"

    @pytest.mark.asyncio
    async def test_handler_register_subscribes(
        self,
        handler: UDMRHandler,
        mock_event_bus: AsyncMock,
    ) -> None:
        """handler.register() 应订阅 AutoRouted."""
        await handler.register()
        mock_event_bus.subscribe_async.assert_called_once_with("AutoRouted", handler.on_routed)
