"""Architecture constraint tests for event system (Story 1.2).

Verifies:
1. Domain events use only Python standard library (no Pydantic)
2. Event serialization logic layer separation (TypeAdapter only in application layer)
3. Dependency direction is correct
"""

import ast
from pathlib import Path


class TestDomainEventsNoPydantic:
    """Verify domain events have zero Pydantic dependencies."""

    def test_no_pydantic_imports_in_domain_events(self):
        """Domain events directory has no pydantic imports."""
        events_dir = Path("src/domain/events")
        pydantic_files = []

        for py_file in events_dir.rglob("*.py"):
            source = py_file.read_text()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "pydantic" in alias.name:
                            pydantic_files.append(f"{py_file}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and "pydantic" in node.module:
                        pydantic_files.append(f"{py_file}: from {node.module} import ...")

        assert len(pydantic_files) == 0, f"Pydantic imports found in domain/events: {pydantic_files}"

    def test_domain_event_files_exist(self):
        """Domain event files exist in the expected locations."""
        event_files = [
            "src/domain/events/base.py",
            "src/domain/events/enums.py",
            "src/domain/events/document_events.py",
            "src/domain/events/tool_events.py",
            "src/domain/events/agent_events.py",
            "src/domain/events/checkpoint_events.py",
            "src/domain/events/correction_events.py",
            "src/domain/events/planning_events.py",
            "src/domain/events/heartbeat_events.py",
            "src/domain/events/isolation_events.py",
            "src/domain/events/routing_events.py",
        ]

        for file_path in event_files:
            path = Path(file_path)
            assert path.exists(), f"Event file missing: {file_path}"


class TestApplicationLayerTypeAdapter:
    """Verify TypeAdapter is only used in application/infrastructure layer."""

    def test_type_adapter_in_application_layer(self):
        """TypeAdapter is used in src/application/event_handlers/event_dict_to_json.py."""
        adapters_file = Path("src/application/event_handlers/event_dict_to_json.py")
        assert adapters_file.exists(), "Application adapters file missing"

        source = adapters_file.read_text()
        assert "TypeAdapter" in source, "TypeAdapter should be in application layer"

    def test_no_type_adapter_in_domain_layer(self):
        """TypeAdapter is not used in domain layer."""
        domain_dir = Path("src/domain")

        for py_file in domain_dir.rglob("*.py"):
            source = py_file.read_text()
            assert "TypeAdapter" not in source, f"TypeAdapter should not be in domain layer: {py_file}"


class TestEventDependencyDirection:
    """Verify event-related dependency direction is correct."""

    def test_domain_does_not_import_infrastructure(self):
        """Domain layer does not import infrastructure."""
        domain_dir = Path("src/domain")

        for py_file in domain_dir.rglob("*.py"):
            source = py_file.read_text()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert "infrastructure" not in alias.name, f"Domain imports infrastructure in {py_file}: {alias.name}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        assert "infrastructure" not in node.module, f"Domain imports infrastructure in {py_file}: {node.module}"

    def test_domain_does_not_import_application(self):
        """Domain layer does not import application."""
        domain_dir = Path("src/domain")

        for py_file in domain_dir.rglob("*.py"):
            source = py_file.read_text()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert "application" not in alias.name, f"Domain imports application in {py_file}: {alias.name}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        assert "application" not in node.module, f"Domain imports application in {py_file}: {node.module}"


class TestEventModuleStructure:
    """Verify event module structure is correct."""

    def test_all_10_events_exported(self):
        """All 10 events are exported from __init__.py."""
        init_file = Path("src/domain/events/__init__.py")
        source = init_file.read_text()

        expected_events = [
            "DocumentProcessed",
            "ToolExecuted",
            "AgentDecided",
            "CheckpointReached",
            "CorrectionApproved",
            "StrategicDeviationWarning",
            "HeartbeatTriggered",
            "IsolationLevelSwitched",
            "CheckpointRecovered",
            "RoutingDecided",
        ]

        for event_name in expected_events:
            assert event_name in source, f"Event {event_name} not exported from __init__.py"

    def test_enums_exported(self):
        """Event enums are exported."""
        init_file = Path("src/domain/events/__init__.py")
        source = init_file.read_text()

        expected_enums = [
            "DeviationLevel",
            "CorrectionType",
            "IsolationLevel",
            "RecoveryMode",
        ]

        for enum_name in expected_enums:
            assert enum_name in source, f"Enum {enum_name} not exported from __init__.py"

    def test_event_interfaces_exist(self):
        """Event interfaces (publisher, listener, store) are defined."""
        expected_files = [
            "src/domain/ports/event_publisher.py",
            "src/domain/events/listener.py",
            "src/domain/events/event_store.py",
        ]

        for file_path in expected_files:
            assert Path(file_path).exists(), f"Interface file missing: {file_path}"
