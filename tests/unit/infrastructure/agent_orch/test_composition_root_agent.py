"""Composition Root Agent 引擎注册验证测试

验证 agent_engine 端口注册链路、OrchestrationService 双引擎注入

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from src.domain.ports.agent_engine import AgentEnginePort
from src.domain.ports.registry import _global_registry
from src.domain.ports.resolver import Resolver


class TestAgentEngineRegistration:
    """agent_engine 端口注册验证"""

    def test_agent_engine_registered_in_registry(self) -> None:
        """agent_engine 应在全局注册中心中"""
        spec = _global_registry.get("agent_engine")
        assert spec is not None, "agent_engine 端口未注册"

    def test_agent_engine_interface_is_correct(self) -> None:
        """agent_engine 接口应为 AgentEnginePort"""
        spec = _global_registry.get("agent_engine")
        assert spec is not None
        assert spec.interface is AgentEnginePort

    def test_agent_engine_module_path(self) -> None:
        """agent_engine 模块路径应指向 langgraph_engine"""
        spec = _global_registry.get("agent_engine")
        assert spec is not None
        assert "langgraph_engine" in spec.module

    def test_agent_engine_lifetime_is_singleton(self) -> None:
        """agent_engine 生命周期应为 SINGLETON"""
        from src.domain.ports.registry import Lifetime

        spec = _global_registry.get("agent_engine")
        assert spec is not None
        assert spec.lifetime == Lifetime.SINGLETON

    def test_agent_engine_resolves_to_langgraph_engine(self) -> None:
        """解析 agent_engine 应返回 LangGraphEngine 实例"""
        from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine

        resolver = Resolver()
        impl = resolver.resolve("agent_engine")
        assert isinstance(impl, LangGraphEngine)
        assert isinstance(impl, AgentEnginePort)


class TestOrchestrationServiceDualEngine:
    """OrchestrationService 双引擎注入验证"""

    def test_orchestration_service_resolves_with_both_engines(self) -> None:
        """orchestration_service 解析后应包含双引擎"""
        from src.application.services.orchestration_service import OrchestrationService

        resolver = Resolver()
        impl = resolver.resolve("orchestration_service")
        assert isinstance(impl, OrchestrationService)
        assert hasattr(impl, "_workflow_engine")
        assert hasattr(impl, "_agent_engine")
