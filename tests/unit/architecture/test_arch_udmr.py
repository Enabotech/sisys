"""Architecture constraint tests for UDMR.

验证六边形架构约束：领域层零外部依赖、依赖方向正确
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ===================================================================
# 领域层零外部依赖验证
# ===================================================================


class TestUDMRDomainZeroDependency:
    """验证 UDMRService 仅依赖领域层端口和 Python 标准库."""

    def test_udmr_service_no_infrastructure_imports(self) -> None:
        """UDMRService 不应导入基础设施层模块."""
        # 解析 udmr_service.py AST
        service_path = Path("src/domain/services/udmr_service.py")
        if not service_path.exists():
            pytest.skip("UDMRService not yet implemented")

        source = service_path.read_text()
        tree = ast.parse(source)

        forbidden_prefixes = (
            "src.infrastructure",
            "src.interfaces",
            "redis",
            "httpx",
            "aioredis",
            "neo4j",
            "qdrant",
            "minio",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    assert not name.startswith(forbidden_prefixes), f"Forbidden import: {name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(forbidden_prefixes), f"Forbidden import from: {module}"

    def test_udmr_service_imports_domain_only(self) -> None:
        """UDMRService 应仅导入领域层模块."""
        service_path = Path("src/domain/services/udmr_service.py")
        if not service_path.exists():
            pytest.skip("UDMRService not yet implemented")

        source = service_path.read_text()
        tree = ast.parse(source)

        allowed_prefixes = (
            "__future__",
            "dataclasses",
            "typing",
            "logging",
            "asyncio",
            "uuid",
            "datetime",
            "time",
            "src.domain",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    is_allowed = any(name.startswith(p) or name == p.split(".")[-1] for p in allowed_prefixes)
                    assert is_allowed, f"Unexpected import: {name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                is_allowed = any(module.startswith(p) for p in allowed_prefixes)
                assert is_allowed, f"Unexpected import from: {module}"


# ===================================================================
# 依赖方向矩阵验证
# ===================================================================


class TestUDMRDependencyDirection:
    """验证依赖方向符合六边形架构."""

    def test_udmr_handler_imports_domain(self) -> None:
        """UDMRHandler（application层）应导入 domain 层."""
        handler_path = Path("src/application/event_handlers/udmr_handler.py")
        if not handler_path.exists():
            pytest.skip("UDMRHandler not yet implemented")

        source = handler_path.read_text()
        # 应包含 domain 导入
        assert "src.domain" in source, "UDMRHandler should import from domain"

    def test_udmr_handler_no_infrastructure_imports(self) -> None:
        """UDMRHandler 不应直接导入基础设施层."""
        handler_path = Path("src/application/event_handlers/udmr_handler.py")
        if not handler_path.exists():
            pytest.skip("UDMRHandler not yet implemented")

        source = handler_path.read_text()
        forbidden = ("src.infrastructure.config", "src.infrastructure.routing")
        for f in forbidden:
            assert f not in source, f"UDMRHandler should not import {f}"

    def test_static_udmr_policy_infrastructure_layer(self) -> None:
        """StaticUdmrPolicy 应位于 infrastructure 层."""
        policy_path = Path("src/infrastructure/routing/udmr_policy.py")
        assert policy_path.exists(), "StaticUdmrPolicy should exist"

    def test_cloud_health_checker_infrastructure_layer(self) -> None:
        """CloudHealthChecker 应位于 infrastructure 层."""
        checker_path = Path("src/infrastructure/external_services/llm/cloud_health_checker.py")
        assert checker_path.exists(), "CloudHealthChecker should exist"


# ===================================================================
# 端口实现协议验证
# ===================================================================


class TestUDMRPortImplementation:
    """验证端口实现满足 Protocol."""

    def test_static_udmr_policy_implements_route(self) -> None:
        """StaticUdmrPolicy 应实现 route() 方法."""
        from src.infrastructure.routing.udmr_policy import StaticUdmrPolicy

        policy = StaticUdmrPolicy(cloud_configs=[], local_model="test")
        assert hasattr(policy, "route")
        assert callable(policy.route)

    def test_cloud_health_checker_implements_check_and_close(self) -> None:
        """CloudHealthChecker 应实现 check() 和 close() 方法."""
        from src.infrastructure.external_services.llm.cloud_health_checker import (
            CloudHealthChecker,
        )

        checker = CloudHealthChecker(cloud_configs=[])
        assert hasattr(checker, "check")
        assert callable(checker.check)
        assert hasattr(checker, "close")
        assert callable(checker.close)
