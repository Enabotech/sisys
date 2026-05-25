"""Unit tests for UDMRService.

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.entities.routing_decision_log import RoutingDecisionLog
from src.domain.events.routing_events import RoutingDecided
from src.domain.services.udmr_service import UDMRService
from src.domain.value_objects.compliance_result import ComplianceResult
from src.domain.value_objects.udmr_task import UDMRTask


def _make_task(**kwargs: Any) -> UDMRTask:
    """辅助构造 UDMRTask."""
    defaults: dict[str, Any] = {
        "task_id": uuid.uuid4(),
        "input": "test input",
        "data_residency": "CHINA_DOMESTIC",
    }
    defaults.update(kwargs)
    return UDMRTask(**defaults)


def _make_compliance(
    allowed: bool = True,
    forced_local: bool = False,
) -> ComplianceResult:
    """辅助构造 ComplianceResult."""
    return ComplianceResult(allowed=allowed, forced_local=forced_local)


@pytest.fixture
def mock_compliance_gateway() -> AsyncMock:
    """Mock ComplianceGatewayPort."""
    gw = AsyncMock()
    gw.check.return_value = _make_compliance()
    return gw


@pytest.fixture
def mock_policy() -> AsyncMock:
    """Mock UdmrPolicyPort."""
    policy = AsyncMock()
    policy.route.return_value = ("cloud", "MiniMax-M2.7", None)
    return policy


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
    pub = AsyncMock()
    pub.publish.return_value = MagicMock()  # PublishResult
    return pub


@pytest.fixture
def service(
    mock_compliance_gateway: AsyncMock,
    mock_policy: AsyncMock,
    mock_health_checker: AsyncMock,
    mock_log_repo: AsyncMock,
    mock_publisher: AsyncMock,
) -> UDMRService:
    """构造 UDMRService 实例."""
    return UDMRService(
        compliance_gateway=mock_compliance_gateway,
        policy=mock_policy,
        health_checker=mock_health_checker,
        log_repo=mock_log_repo,
        publisher=mock_publisher,
        local_first=False,
        local_model="qwen2.5:7b",
        llm_timeout=600,
    )


# ===================================================================
# 决策流程测试
# ===================================================================


class TestUDMRServiceDecide:
    """UDMRService.decide() 测试."""

    async def test_decide_returns_routing_decided(
        self,
        service: UDMRService,
        mock_compliance_gateway: AsyncMock,
        mock_policy: AsyncMock,
    ) -> None:
        """decide() 应返回 RoutingDecided 事件."""
        task = _make_task()
        mock_compliance_gateway.check.return_value = _make_compliance()
        mock_policy.route.return_value = ("cloud", "MiniMax-M2.7", None)

        result = await service.decide(task)

        assert isinstance(result, RoutingDecided)
        assert result.route_type == "cloud"
        assert result.selected_model == "MiniMax-M2.7"

    async def test_decide_calls_compliance_check(
        self,
        service: UDMRService,
        mock_compliance_gateway: AsyncMock,
    ) -> None:
        """decide() 应调用合规检查."""
        task = _make_task()
        await service.decide(task)
        mock_compliance_gateway.check.assert_called_once_with(task)

    async def test_decide_calls_policy_route(
        self,
        service: UDMRService,
        mock_compliance_gateway: AsyncMock,
        mock_policy: AsyncMock,
    ) -> None:
        """decide() 应调用策略路由."""
        task = _make_task()
        compliance = _make_compliance()
        mock_compliance_gateway.check.return_value = compliance

        await service.decide(task)

        mock_policy.route.assert_called_once_with(task, compliance)

    async def test_decide_publishes_event(
        self,
        service: UDMRService,
        mock_publisher: AsyncMock,
    ) -> None:
        """decide() 应发布 RoutingDecided 事件."""
        task = _make_task()
        await service.decide(task)
        mock_publisher.publish.assert_called_once()
        event = mock_publisher.publish.call_args[0][0]
        assert isinstance(event, RoutingDecided)

    async def test_decide_cloud_with_fallback_reason(
        self,
        service: UDMRService,
        mock_compliance_gateway: AsyncMock,
        mock_policy: AsyncMock,
    ) -> None:
        """云端不可用时 fallback_reason 应正确传递."""
        task = _make_task()
        mock_policy.route.return_value = ("local", "qwen2.5:7b", "unavailable")

        result = await service.decide(task)

        assert result.route_type == "local"
        assert result.selected_model == "qwen2.5:7b"
        assert result.fallback_reason == "unavailable"

    async def test_decide_health_check_result_in_event(
        self,
        service: UDMRService,
        mock_health_checker: AsyncMock,
    ) -> None:
        """健康检查结果应写入 RoutingDecided 事件."""
        mock_health_checker.check.return_value = False
        task = _make_task()

        result = await service.decide(task)

        assert result.health_check_passed is False

    async def test_decide_health_check_passed(
        self,
        service: UDMRService,
        mock_health_checker: AsyncMock,
    ) -> None:
        """健康检查通过时 health_check_passed=True."""
        mock_health_checker.check.return_value = True
        task = _make_task()

        result = await service.decide(task)

        assert result.health_check_passed is True

    async def test_decide_persist_log(
        self,
        service: UDMRService,
        mock_log_repo: AsyncMock,
    ) -> None:
        """decide() 应持久化路由决策日志."""
        task = _make_task()

        await service.decide(task)

        # _persist_decision_log 使用 asyncio.create_task（fire-and-forget）
        # 验证 save 被调用（给后台任务执行时间）
        import asyncio

        await asyncio.sleep(0.05)
        mock_log_repo.save.assert_called_once()
        log: RoutingDecisionLog = mock_log_repo.save.call_args[0][0]
        assert log.selected_model == "MiniMax-M2.7"
        assert log.route_type == "cloud"
        assert log.fallback_reason is None

    async def test_decide_persist_log_with_fallback(
        self,
        service: UDMRService,
        mock_log_repo: AsyncMock,
        mock_policy: AsyncMock,
    ) -> None:
        """日志应包含 fallback_reason."""
        task = _make_task()
        mock_policy.route.return_value = ("local", "qwen2.5:7b", "unavailable")

        await service.decide(task)

        import asyncio

        await asyncio.sleep(0.05)
        log: RoutingDecisionLog = mock_log_repo.save.call_args[0][0]
        assert log.fallback_reason == "unavailable"
        assert log.selected_model == "qwen2.5:7b"

    async def test_decide_task_id_in_event(
        self,
        service: UDMRService,
    ) -> None:
        """RoutingDecided 事件应包含 task_id."""
        task_id = uuid.uuid4()
        task = _make_task(task_id=task_id)

        result = await service.decide(task)

        assert result.task_id == task_id


# ===================================================================
# 无 publisher/repo 场景
# ===================================================================


class TestUDMRServiceOptionalDeps:
    """可选依赖为 None 时的行为."""

    async def test_decide_without_publisher(
        self,
        mock_compliance_gateway: AsyncMock,
        mock_policy: AsyncMock,
        mock_health_checker: AsyncMock,
    ) -> None:
        """无 publisher 时不发布事件但正常返回."""
        svc = UDMRService(
            compliance_gateway=mock_compliance_gateway,
            policy=mock_policy,
            health_checker=mock_health_checker,
            log_repo=None,
            publisher=None,
        )
        task = _make_task()
        result = await svc.decide(task)
        assert isinstance(result, RoutingDecided)

    async def test_decide_without_log_repo(
        self,
        mock_compliance_gateway: AsyncMock,
        mock_policy: AsyncMock,
        mock_health_checker: AsyncMock,
        mock_publisher: AsyncMock,
    ) -> None:
        """无 log_repo 时不持久化日志但正常返回."""
        svc = UDMRService(
            compliance_gateway=mock_compliance_gateway,
            policy=mock_policy,
            health_checker=mock_health_checker,
            log_repo=None,
            publisher=mock_publisher,
        )
        task = _make_task()
        result = await svc.decide(task)
        assert isinstance(result, RoutingDecided)
