"""Architecture tests for execute mechanism - verifying hexagonal architecture constraints."""

from pathlib import Path


class TestExecuteArchitecture:
    """SDD architecture validation tests for execute mechanism.

    Validates hexagonal architecture constraints:
    - ExecuteService is in domain layer (no external framework dependencies)
    - SandboxExecutor port is in interfaces layer
    - Infrastructure implementations are in infrastructure layer
    - No circular dependencies between layers
    """

    def test_execute_service_in_domain_layer(self) -> None:
        """AutoExecuteService must be in domain layer."""
        execute_service_path = Path("src/domain/services/auto_execute_service.py")

        assert execute_service_path.exists(), "AutoExecuteService must exist in domain/services/"

        content = execute_service_path.read_text()

        # Should not import from infrastructure directly
        msg = "AutoExecuteService must not import infrastructure directly - use ports"
        assert "from src.infrastructure" not in content, msg
        assert (
            "from src.interfaces" not in content or "Protocol" in content
        ), "AutoExecuteService must only import interfaces.Protocol for ports"

    def test_sandbox_executor_port_in_interfaces_layer(self) -> None:
        """SandboxExecutor port must be in interfaces layer."""
        port_path = Path("src/interfaces/sandbox/sandbox_port.py")

        assert port_path.exists(), "SandboxExecutor port must exist in interfaces/sandbox/"

    def test_docker_sandbox_adapter_in_infrastructure_layer(self) -> None:
        """DockerSandboxAdapter must be in infrastructure layer."""
        adapter_path = Path("src/infrastructure/external_services/sandbox/docker_sandbox_adapter.py")

        assert adapter_path.exists(), "DockerSandboxAdapter must exist in infrastructure/sandbox/"

    def test_executed_event_in_domain_events(self) -> None:
        """AutoExecuted event must be in domain/events layer."""
        event_path = Path("src/domain/events/auto_execute_events.py")

        assert event_path.exists(), "AutoExecuted event must exist in domain/events/"

    def test_checkpoint_snapshot_in_domain_entities(self) -> None:
        """CheckpointSnapshot must be in domain/entities layer."""
        entity_path = Path("src/domain/entities/checkpoint_snapshot.py")

        assert entity_path.exists(), "CheckpointSnapshot must exist in domain/entities/"

    def test_no_circular_dependencies(self) -> None:
        """Verify no circular dependencies between execute mechanism files."""
        # Check that domain layer files don't import from infrastructure
        domain_files = [
            "src/domain/services/auto_execute_service.py",
            "src/domain/events/auto_execute_events.py",
            "src/domain/entities/checkpoint_snapshot.py",
        ]

        for file_path in domain_files:
            if not Path(file_path).exists():
                continue

            content = Path(file_path).read_text()

            # Extract imports
            import_lines = [line for line in content.split("\n") if line.startswith("from src.")]

            for line in import_lines:
                # Domain should not import from infrastructure
                assert (
                    "src/infrastructure" not in line or "Protocol" in line
                ), f"{file_path} must not import from infrastructure directly"

    def test_interfaces_layer_defines_ports(self) -> None:
        """Interfaces layer must define ports (abstract interfaces)."""
        port_file = Path("src/interfaces/sandbox/sandbox_port.py")

        content = port_file.read_text()

        # Port should define abstract methods
        assert "ABC" in content or "abstractmethod" in content, "Port must define abstract methods"
        assert "async def start_container" in content, "Port must define start_container method"
        assert "async def execute_code" in content, "Port must define execute_code method"
        assert "async def stop_container" in content, "Port must define stop_container method"

    def test_infrastructure_implements_ports(self) -> None:
        """Infrastructure layer must implement interfaces layer ports."""
        adapter_file = Path("src/infrastructure/external_services/sandbox/docker_sandbox_adapter.py")

        content = adapter_file.read_text()

        # Adapter should import from interfaces
        assert (
            "from src.interfaces.sandbox.sandbox_port import" in content
        ), "DockerSandboxAdapter must import from interfaces.sandbox.sandbox_port"
