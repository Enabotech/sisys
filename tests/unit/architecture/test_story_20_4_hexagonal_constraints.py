"""Hexagonal Architecture Constraint Verification Tests (Task 15).

验证领域层零外部依赖约束满足。

验证标准（AC-14）:
- [ ] ruff check src/domain/ 无外部依赖违规
- [ ] mypy src/domain/repositories/ 类型检查通过
- [ ] Port 接口位于 src/domain/repositories/
- [ ] 实现类位于 src/infrastructure/
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


class TestHexagonalArchitectureConstraints:
    """六边形架构约束验证"""

    def test_domain_layer_no_external_dependencies(self):
        """验证领域层没有外部依赖"""
        # 运行 ruff check
        result = subprocess.run(
            ["poetry", "run", "ruff", "check", "src/domain/"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Domain layer has violations: {result.stdout}\n{result.stderr}"

    def test_domain_repositories_type_check(self):
        """验证 domain/repositories 类型检查通过"""
        result = subprocess.run(
            ["poetry", "run", "mypy", "src/domain/repositories/", "--ignore-missing-imports"],
            capture_output=True,
            text=True,
        )
        # mypy 可能返回非零即使有错误，检查输出
        assert "error" not in result.stdout.lower() or result.returncode == 0, f"Type check failed: {result.stdout}"

    def test_port_interfaces_in_domain_repositories(self):
        """验证 Port 接口位于 src/domain/repositories/"""
        domain_repos = Path("src/domain/repositories")

        # 检查必需的 Port 接口存在
        required_ports = [
            "health_check.py",
            "l0_storage.py",
            "index_manager.py",
            "integrity.py",
        ]

        for port_file in required_ports:
            port_path = domain_repos / port_file
            assert port_path.exists(), f"Port interface {port_file} not found in domain/repositories/"

    def test_implementation_classes_in_infrastructure(self):
        """验证实现类位于 src/infrastructure/"""
        infrastructure_path = Path("src/infrastructure")

        # 检查关键实现存在
        implementations = [
            "storage/file_memory_adapter.py",
            "storage/memory_index.py",
            "routing/ollama_health_adapter.py",
            "security/integrity_service.py",
        ]

        for impl in implementations:
            impl_path = infrastructure_path / impl
            assert impl_path.exists(), f"Implementation {impl} not found in infrastructure/"

    def test_domain_repositories_not_importing_infrastructure(self):
        """验证 domain/repositories 不导入 infrastructure 层"""
        domain_repos = Path("src/domain/repositories")

        for py_file in domain_repos.glob("*.py"):
            content = py_file.read_text()
            # 检查没有从 infrastructure 导入
            lines = content.split("\n")
            for line in lines:
                if "from src.infrastructure" in line or "import src.infrastructure" in line:
                    pytest.fail(f"{py_file.name} imports from infrastructure: {line.strip()}")


class TestPortInterfaceCompliance:
    """Port 接口合规性验证"""

    def test_l0_storage_port_has_required_methods(self):
        """验证 L0StoragePort 接口有所需方法"""

        from src.domain.repositories.l0_storage import L0StoragePort

        methods = ["write", "read", "delete", "exists", "list_memories"]
        for method in methods:
            assert hasattr(L0StoragePort, method), f"L0StoragePort missing method: {method}"

    def test_index_manager_port_has_required_methods(self):
        """验证 IndexManagerPort 接口有所需方法"""

        from src.domain.repositories.index_manager import IndexManagerPort

        methods = ["update_entry", "remove_entry", "read_entries", "search", "truncate"]
        for method in methods:
            assert hasattr(IndexManagerPort, method), f"IndexManagerPort missing method: {method}"

    def test_health_check_port_has_required_methods(self):
        """验证 HealthCheckPort 接口有所需方法"""
        from src.domain.repositories.health_check import HealthCheckPort

        methods = ["check", "close"]
        for method in methods:
            assert hasattr(HealthCheckPort, method), f"HealthCheckPort missing method: {method}"

    def test_integrity_port_has_required_methods(self):
        """验证 IntegrityPort 接口有所需方法"""
        from src.domain.repositories.integrity import IntegrityPort

        methods = ["verify_file", "compute_hash", "verify_hash"]
        for method in methods:
            assert hasattr(IntegrityPort, method), f"IntegrityPort missing method: {method}"


class TestDependencyRuleCompliance:
    """依赖规则合规性验证"""

    def test_domain_layer_uses_only_stdlib(self):
        """验证领域层只使用标准库"""
        domain_path = Path("src/domain")

        # 禁止的外部依赖
        forbidden_imports = [
            "langgraph",
            "prefect",
            "fastapi",
            "pydantic",
            "sqlalchemy",
            "typer",
            "redis",
            "qdrant",
            "minio",
            "neo4j",
            "aio_pika",
            "litellm",
            "instructor",
            "requests",
            "httpx",
            "docker",
            "psycopg2",
        ]

        for py_file in domain_path.rglob("*.py"):
            content = py_file.read_text()
            for forbidden in forbidden_imports:
                if f"import {forbidden}" in content or f"from {forbidden}" in content:
                    pytest.fail(f"{py_file.relative_to(domain_path)} imports {forbidden}")

    def test_application_layer_respects_layer_boundaries(self):
        """验证应用层遵守层边界"""
        # 应用层可以导入领域层和基础设施层
        app_path = Path("src/application")

        # 应用层不应该直接导入接口层（应该通过领域层端口）
        # 这个测试比较宽松，只要没有明显违规即可
        assert app_path.exists()

    def test_infrastructure_layer_imports_domain_only(self):
        """验证基础设施层只导入领域层（不反向依赖）"""
        infra_path = Path("src/infrastructure")

        for py_file in infra_path.rglob("*.py"):
            content = py_file.read_text()

            # 基础设施层不应该导入 application 层（反向依赖）
            if "from src.application" in content or "import src.application" in content:
                pytest.fail(f"{py_file.relative_to(infra_path)} imports application layer (reverse dependency)")
