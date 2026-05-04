"""Architecture constraint tests for event bus components.

Validates AC-11: Hexagonal architecture constraints satisfaction.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


class TestDomainLayerZeroExternalDependencies:
    """AC-11.1: Domain layer must have zero external dependencies."""

    def test_publish_result_has_no_external_imports(self) -> None:
        """PublishResult should only use dataclass and typing from stdlib."""
        module_path = Path(__file__).parents[3] / "src" / "domain" / "events" / "publish_result.py"
        assert module_path.exists(), f"Module not found: {module_path}"

        source = module_path.read_text()
        tree = ast.parse(source)

        allowed_modules = {"dataclasses", "typing", "__future__"}
        external_imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                module = node.module if isinstance(node, ast.ImportFrom) else None
                if module and not any(module.startswith(allowed) for allowed in allowed_modules):
                    external_imports.append(module)

        assert not external_imports, f"PublishResult has external imports: {external_imports}"


class TestDeliveryModeInInfrastructureLayer:
    """AC-11.2: DeliveryMode enum must be in infrastructure layer."""

    def test_delivery_mode_not_in_domain_layer(self) -> None:
        """DeliveryMode should NOT be defined in domain layer."""
        domain_events_path = Path(__file__).parents[3] / "src" / "domain" / "events"
        if not domain_events_path.exists():
            pytest.skip("Domain events path does not exist")

        for py_file in domain_events_path.rglob("*.py"):
            content = py_file.read_text()
            assert "class DeliveryMode" not in content, f"DeliveryMode found in {py_file}"
            assert "DeliveryMode.REALTIME" not in content, f"DeliveryMode.REALTIME found in {py_file}"
            assert "DeliveryMode.RELIABLE" not in content, f"DeliveryMode.RELIABLE found in {py_file}"

    def test_delivery_mode_in_infrastructure_layer(self) -> None:
        """DeliveryMode should be defined in infrastructure layer."""
        infra_path = Path(__file__).parents[3] / "src" / "infrastructure" / "messaging" / "channel_router.py"
        assert infra_path.exists(), f"ChannelRouter not found: {infra_path}"

        content = infra_path.read_text()
        assert "class DeliveryMode" in content, "DeliveryMode class not found in channel_router.py"


class TestInterfacesDoNotDependOnDomain:
    """AC-11.3: Interface layer should not depend on domain layer implementations."""

    def test_event_publisher_interface_exists(self) -> None:
        """EventPublisher interface should exist."""
        interface_path = Path(__file__).parents[3] / "src" / "domain" / "ports" / "event_publisher.py"
        assert interface_path.exists(), f"EventPublisher interface not found: {interface_path}"

    def test_event_subscriber_interface_exists(self) -> None:
        """EventSubscriber interface should exist."""
        interface_path = Path(__file__).parents[3] / "src" / "interfaces" / "event_subscriber.py"
        assert interface_path.exists(), f"EventSubscriber interface not found: {interface_path}"


class TestInfrastructureComponentsImplementInterfaces:
    """Verify infrastructure components implement correct interfaces."""

    def test_redis_event_bus_implements_publisher_and_subscriber(self) -> None:
        """RedisEventBus should implement EventPublisher and EventSubscriber."""
        from src.domain.ports.event_publisher import EventPublisher
        from src.infrastructure.messaging.redis_event_bus import RedisEventBus
        from src.interfaces.event_subscriber import EventSubscriber

        assert issubclass(RedisEventBus, EventPublisher), "RedisEventBus should implement EventPublisher"
        assert issubclass(RedisEventBus, EventSubscriber), "RedisEventBus should implement EventSubscriber"

    def test_rabbitmq_event_bus_implements_publisher(self) -> None:
        """RabbitMQEventBus should implement EventPublisher."""
        from src.domain.ports.event_publisher import EventPublisher
        from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus

        assert issubclass(RabbitMQEventBus, EventPublisher), "RabbitMQEventBus should implement EventPublisher"

    def test_dual_channel_event_bus_implements_publisher(self) -> None:
        """DualChannelEventBus should implement EventPublisher."""
        from src.domain.ports.event_publisher import EventPublisher
        from src.infrastructure.messaging.dual_channel_event_bus import DualChannelEventBus

        assert issubclass(DualChannelEventBus, EventPublisher), "DualChannelEventBus should implement EventPublisher"


class TestRuffAndMypyCompliance:
    """AC-11.4: Code should pass Ruff and MyPy checks."""

    def test_ruff_check_passes_for_new_files(self) -> None:
        """New messaging files should pass Ruff checks."""
        import subprocess

        new_files = [
            "src/infrastructure/messaging/redis_event_bus.py",
            "src/infrastructure/messaging/rabbitmq_event_bus.py",
            "src/infrastructure/messaging/dual_channel_event_bus.py",
            "src/infrastructure/messaging/channel_router.py",
            "src/infrastructure/messaging/event_bus_factory.py",
            "src/infrastructure/messaging/event_bus_config_loader.py",
        ]

        root = Path(__file__).parents[3]
        failures = []

        for rel_path in new_files:
            file_path = root / rel_path
            if not file_path.exists():
                continue
            result = subprocess.run(
                ["poetry", "run", "ruff", "check", str(file_path)],
                capture_output=True,
                text=True,
                cwd=root,
            )
            if result.returncode != 0:
                failures.append(f"{rel_path}: {result.stdout}")

        assert not failures, f"Ruff check failures:\n{chr(10).join(failures)}"

    def test_mypy_check_passes_for_new_files(self) -> None:
        """New messaging files should pass MyPy checks."""
        import subprocess

        new_files = [
            "src/infrastructure/messaging/redis_event_bus.py",
            "src/infrastructure/messaging/rabbitmq_event_bus.py",
            "src/infrastructure/messaging/dual_channel_event_bus.py",
            "src/infrastructure/messaging/channel_router.py",
            "src/infrastructure/messaging/event_bus_factory.py",
            "src/infrastructure/messaging/event_bus_config_loader.py",
        ]

        root = Path(__file__).parents[3]
        failures = []

        for rel_path in new_files:
            file_path = root / rel_path
            if not file_path.exists():
                continue
            result = subprocess.run(
                ["poetry", "run", "mypy", str(file_path)],
                capture_output=True,
                text=True,
                cwd=root,
            )
            if result.returncode != 0:
                failures.append(f"{rel_path}: {result.stdout}")

        assert not failures, f"MyPy check failures:\n{chr(10).join(failures)}"
