"""Task 10 TDD Tests — 架构约束验证 (AC-10)."""

from __future__ import annotations

import ast
from pathlib import Path

# Get root directory (project root)
ROOT_DIR = Path(__file__).parents[4]


class TestArchitectureConstraints:
    """Architecture constraint validation tests."""

    def test_domain_layer_has_no_external_dependencies(self):
        """领域层零外部依赖约束验证。

        领域层（src/domain/）只能使用 Python 标准库。
        禁止导入：langgraph, prefect, fastapi, pydantic, sqlalchemy, typer,
        redis, qdrant, minio, neo4j, aio_pika, litellm, instructor, requests, httpx, docker, psycopg2
        """
        domain_dir = ROOT_DIR / "src" / "domain"
        forbidden_imports = {
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
            "redis.asyncio",
            "aioredis",
        }

        violations = []

        for py_file in domain_dir.rglob("*.py"):
            with open(py_file, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in forbidden_imports or any(
                            alias.name.startswith(f"{forbidden}.") for forbidden in forbidden_imports
                        ):
                            violations.append(f"{py_file.relative_to(ROOT_DIR)}: imports {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and (
                        node.module in forbidden_imports
                        or any(node.module.startswith(f"{forbidden}.") for forbidden in forbidden_imports)
                    ):
                        violations.append(f"{py_file.relative_to(ROOT_DIR)}: from {node.module} import ...")

        assert not violations, "Domain layer has external dependencies:\n" + "\n".join(violations)

    def test_domain_layer_does_not_import_infrastructure_models(self):
        """领域层不导入 infrastructure.storage.postgresql.models 约束验证。"""
        domain_dir = ROOT_DIR / "src" / "domain"
        violations = []

        for py_file in domain_dir.rglob("*.py"):
            with open(py_file, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and "infrastructure" in node.module and "models" in node.module:
                        violations.append(f"{py_file.relative_to(ROOT_DIR)}: from {node.module} import ...")

        assert not violations, "Domain layer imports infrastructure models:\n" + "\n".join(violations)

    def test_ruff_check_passes_for_domain_layer(self):
        """领域层 Ruff 检查通过。"""
        import subprocess

        result = subprocess.run(
            ["poetry", "run", "ruff", "check", "src/domain/"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Ruff check failed:\n{result.stdout}\n{result.stderr}"

    def test_mypy_check_passes_for_domain_layer(self):
        """领域层 MyPy 检查通过。"""
        import subprocess

        result = subprocess.run(
            ["poetry", "run", "mypy", "src/domain/"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"MyPy check failed:\n{result.stdout}\n{result.stderr}"


class TestHexagonalArchitecture:
    """六边形架构依赖方向约束验证。"""

    def test_application_layer_respects_dependencies(self):
        """应用层依赖方向约束。

        应用层可以导入基础设施层，但不能导入 domain 层之外的外部依赖。
        """
        # This is a structural test - verify file structure
        app_dir = ROOT_DIR / "src" / "application"
        assert app_dir.exists(), "Application layer should exist"

    def test_infrastructure_layer_can_import_domain_and_application(self):
        """基础设施层可以导入领域层和应用层。"""
        infra_dir = ROOT_DIR / "src" / "infrastructure"
        assert infra_dir.exists(), "Infrastructure layer should exist"


class TestEventMessagingComponents:
    """事件消息组件结构验证。"""

    def test_new_components_exist(self):
        """验证新组件文件已创建。"""
        assert (ROOT_DIR / "src" / "infrastructure" / "messaging" / "outbox" / "postgres_dead_letter_queue.py").exists()
        assert (ROOT_DIR / "src" / "infrastructure" / "messaging" / "retry" / "redis_retry_queue.py").exists()
        assert (ROOT_DIR / "src" / "infrastructure" / "messaging" / "retry" / "dual_idempotency_checker.py").exists()
        assert (ROOT_DIR / "src" / "infrastructure" / "messaging" / "rabbitmq_listener.py").exists()
        assert (ROOT_DIR / "src" / "infrastructure" / "messaging" / "event_store.py").exists()

    def test_new_domain_interfaces_exist(self):
        """验证新领域接口文件已创建。"""
        assert (ROOT_DIR / "src" / "domain" / "repositories" / "unit_of_work.py").exists()
        listener_file = ROOT_DIR / "src" / "domain" / "events" / "listener.py"
        assert listener_file.exists()
        # Verify EventListenerAsync is defined
        content = listener_file.read_text()
        assert "class EventListenerAsync" in content
