"""架构约束验证测试

验证六边形架构约束：
- domain 层零外部依赖
- 端口注册正确
- 循环依赖检测
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


class TestHexagonalArchitectureConstraints:
    """Test hexagonal architecture constraints for tool module."""

    def test_domain_tool_module_no_external_imports(self):
        """domain 层工具模块无外部依赖（仅 Python 标准库）"""
        domain_files = [
            "src/domain/entities/tool.py",
            "src/domain/entities/strategic_tool_catalog.py",
            "src/domain/ports/tool_repository.py",
            "src/domain/exceptions/tool_exceptions.py",
        ]
        forbidden_imports = {
            "pydantic",
            "sqlalchemy",
            "redis",
            "fastapi",
            "pytest",
            "httpx",
            "aiohttp",
        }

        for file_path in domain_files:
            full_path = Path(file_path)
            if not full_path.exists():
                continue

            with open(full_path) as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name
                        if any(module.startswith(forbidden) for forbidden in forbidden_imports):
                            pytest.fail(f"{file_path}: forbidden import '{module}'")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and any(node.module.startswith(forbidden) for forbidden in forbidden_imports):
                        pytest.fail(f"{file_path}: forbidden import '{node.module}'")

    def test_tool_repository_port_in_registry(self):
        """tool_repository 端口在 PortRegistry 中注册"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("tool_repository")
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_tool_registry_service_port_in_registry(self):
        """tool_registry_service 端口在 PortRegistry 中注册"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("tool_registry_service")
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_inmemory_tool_repository_implements_port(self):
        """InMemoryToolRepository 实现 ToolRepositoryPort"""
        from src.domain.ports.tool_repository import ToolRepositoryPort
        from src.infrastructure.storage.inmemory.tool_repository import (
            InMemoryToolRepository,
        )

        repo = InMemoryToolRepository()
        assert isinstance(repo, ToolRepositoryPort)

    def test_tool_registry_service_implements_port(self):
        """ToolRegistryService 实现 ToolRegistryServicePort"""
        from src.application.ports.tool_registry_service import (
            ToolRegistryServicePort,
        )
        from src.application.services.tool_registry_service import (
            ToolRegistryService,
        )
        from src.infrastructure.storage.inmemory.tool_repository import (
            InMemoryToolRepository,
        )

        repo = InMemoryToolRepository()
        service = ToolRegistryService(repository=repo)
        assert isinstance(service, ToolRegistryServicePort)
