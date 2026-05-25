"""Port contract tests for TokenEstimatorPort.

Tests that StaticTokenEstimator implementation satisfies the TokenEstimatorPort.

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from src.domain.ports.token_estimator import TokenEstimatorPort


class TestTokenEstimatorPortContract:
    """Contract tests for TokenEstimator port."""

    PORT_NAME = "token_estimator"
    INTERFACE = TokenEstimatorPort
    REQUIRED_METHODS = ["estimate"]

    def test_port_is_registered(self, registry) -> None:
        """端口必须在全局 registry 中注册."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """实现类必须包含协议定义的所有方法."""
        from src.infrastructure.monitoring.static_token_estimator import StaticTokenEstimator

        impl = StaticTokenEstimator()
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """端口元数据必须完整."""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.version, "Port version is empty"
        assert spec.owner, "Port owner is empty"
        assert spec.module, "Port module is empty"
