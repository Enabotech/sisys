"""WorkflowEnginePort 端口契约测试

验证端口注册、元数据完整性、Protocol 兼容性

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from src.domain.ports.workflow_engine import WorkflowEnginePort


class TestWorkflowEnginePortContract:
    """WorkflowEnginePort 端口契约测试"""

    PORT_NAME = "workflow_engine"
    INTERFACE = WorkflowEnginePort

    def test_port_is_registered(self, registry) -> None:
        """workflow_engine 端口应已注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 '{self.PORT_NAME}' 未注册"
        assert spec.interface is self.INTERFACE

    def test_metadata_complete(self, registry) -> None:
        """端口元数据应完整（version, owner, module, lifetime）"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version
        assert spec.owner
        assert spec.module
        assert spec.lifetime is not None

    def test_impl_satisfies_protocol(self, resolver) -> None:
        """实现类应满足 WorkflowEnginePort Protocol"""
        impl = resolver.resolve(self.PORT_NAME)
        assert isinstance(impl, self.INTERFACE)


class TestOrchestrationServiceContract:
    """OrchestrationService 端口契约测试"""

    PORT_NAME = "orchestration_service"

    def test_port_is_registered(self, registry) -> None:
        """orchestration_service 端口应已注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 '{self.PORT_NAME}' 未注册"

    def test_metadata_complete(self, registry) -> None:
        """端口元数据应完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version
        assert spec.module
