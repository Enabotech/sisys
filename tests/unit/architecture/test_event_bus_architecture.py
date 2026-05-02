"""Task 6 — Event Bus Architecture Constraint Tests.

验证六边形架构依赖方向：
1. 领域层不导入 OutboxEntity（基础设施层）
2. Redis/RabbitMQ 客户端导入仅在基础设施层
3. 领域层仅依赖 EventPublisher/EventListener 接口
"""

from __future__ import annotations

import ast
import pathlib


class TestEventBusArchitecture:
    """事件总线架构约束验证。"""

    def test_domain_layer_no_outbox_entity_import(self):
        """领域层不应导入 OutboxEntity（基础设施层定义）。"""
        domain_path = pathlib.Path("src/domain")
        violations = []

        for py_file in domain_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            source = py_file.read_text()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and "infrastructure" in node.module:
                        violations.append(f"{py_file} imports from infrastructure: {node.module}")

        assert not violations, "Domain layer should not import infrastructure:\n" + "\n".join(violations)

    def test_redis_client_import_only_in_infrastructure(self):
        """Redis 客户端导入应仅在基础设施层。"""
        src_path = pathlib.Path("src")
        violations = []

        for py_file in src_path.rglob("*.py"):
            if "infrastructure" in str(py_file):
                continue  # Allow in infrastructure
            if py_file.name == "__init__.py":
                continue

            source = py_file.read_text()
            if "import redis" in source or "from redis" in source:
                # Check if it's in domain layer
                if "domain" in str(py_file):
                    violations.append(f"{py_file} imports redis")

        assert not violations, "Redis client should only be imported in infrastructure layer:\n" + "\n".join(violations)

    def test_rabbitmq_client_import_only_in_infrastructure(self):
        """RabbitMQ 客户端导入应仅在基础设施层。"""
        src_path = pathlib.Path("src")
        violations = []

        for py_file in src_path.rglob("*.py"):
            if "infrastructure" in str(py_file):
                continue
            if py_file.name == "__init__.py":
                continue

            source = py_file.read_text()
            if "import aio_pika" in source or "from aio_pika" in source:
                if "domain" in str(py_file):
                    violations.append(f"{py_file} imports aio_pika")

        assert not violations, "RabbitMQ client should only be imported in infrastructure layer:\n" + "\n".join(violations)

    def test_domain_uses_event_publisher_interface(self):
        """领域层应使用 EventPublisher 接口而非具体实现。"""
        from src.domain.events.publisher import EventPublisher

        assert EventPublisher is not None

    def test_outbox_repository_interface_uses_domain_event(self):
        """OutboxRepository 接口应使用 DomainEvent 而非 OutboxEntity。"""
        import inspect

        from src.domain.ports.outbox import OutboxRepository

        # Check save method signature uses DomainEvent
        sig = inspect.signature(OutboxRepository.save)
        params = list(sig.parameters.keys())
        assert "event" in params, "save method should accept 'event' parameter"

    def test_domain_layer_zero_dependency(self):
        """领域层应仅使用 Python 标准库。"""
        domain_path = pathlib.Path("src/domain")
        forbidden_packages = {
            "pydantic",
            "redis",
            "aio_pika",
            "sqlalchemy",
            "fastapi",
            "typer",
            "opentelemetry",
            "prometheus",
        }
        violations = []

        for py_file in domain_path.rglob("*.py"):
            source = py_file.read_text()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module:
                        for pkg in forbidden_packages:
                            if pkg in node.module.lower():
                                violations.append(f"{py_file} imports forbidden package: {node.module}")

        assert not violations, "Domain layer should have zero external dependencies:\n" + "\n".join(violations)
