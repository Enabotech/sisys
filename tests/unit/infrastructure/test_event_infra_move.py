"""Test event infrastructure move from domain/events to infrastructure/messaging.

AC-2: 4 files (publisher.py, listener.py, store.py, publish_result.py)
should move from domain/events/ to infrastructure/messaging/.
"""

from __future__ import annotations

from pathlib import Path

# Root of the source tree
SRC_ROOT = Path(__file__).resolve().parents[5] / "src"


class TestEventInfrastructureMove:
    """Verify event infrastructure files have been moved to infrastructure/messaging/."""

    def test_event_publisher_moved_to_infrastructure(self):
        """publisher.py should exist in infrastructure/messaging/."""
        infra_path = SRC_ROOT / "infrastructure" / "messaging" / "event_publisher.py"
        assert infra_path.exists(), f"event_publisher.py should exist at {infra_path}"

    def test_event_listener_moved_to_infrastructure(self):
        """listener.py should exist in infrastructure/messaging/."""
        infra_path = SRC_ROOT / "infrastructure" / "messaging" / "event_listener.py"
        assert infra_path.exists(), f"event_listener.py should exist at {infra_path}"

    def test_event_store_moved_to_infrastructure(self):
        """store.py should exist in infrastructure/messaging/ as event_store_domain.py."""
        infra_path = SRC_ROOT / "infrastructure" / "messaging" / "event_store_domain.py"
        assert infra_path.exists(), f"event_store_domain.py should exist at {infra_path}"

    def test_publish_result_moved_to_infrastructure(self):
        """publish_result.py should exist in infrastructure/messaging/."""
        infra_path = SRC_ROOT / "infrastructure" / "messaging" / "publish_result.py"
        assert infra_path.exists(), f"publish_result.py should exist at {infra_path}"

    def test_old_publisher_removed_from_domain(self):
        """publisher.py should NOT exist in domain/events/."""
        domain_path = SRC_ROOT / "domain" / "events" / "publisher.py"
        assert not domain_path.exists(), f"publisher.py should be removed from {domain_path}"

    def test_old_listener_removed_from_domain(self):
        """listener.py should NOT exist in domain/events/."""
        domain_path = SRC_ROOT / "domain" / "events" / "listener.py"
        assert not domain_path.exists(), f"listener.py should be removed from {domain_path}"

    def test_old_store_removed_from_domain(self):
        """store.py should NOT exist in domain/events/."""
        domain_path = SRC_ROOT / "domain" / "events" / "store.py"
        assert not domain_path.exists(), f"store.py should be removed from {domain_path}"

    def test_old_publish_result_removed_from_domain(self):
        """publish_result.py should NOT exist in domain/events/."""
        domain_path = SRC_ROOT / "domain" / "events" / "publish_result.py"
        assert not domain_path.exists(), f"publish_result.py should be removed from {domain_path}"

    def test_domain_events_contains_only_17_domain_events(self):
        """domain/events/ should contain only domain event files (17 files)."""
        domain_events_dir = SRC_ROOT / "domain" / "events"
        py_files = [f for f in domain_events_dir.glob("*.py") if f.name != "__init__.py"]

        # Expected domain event files (excluding infrastructure files)
        expected_events = {
            "agent_events.py",
            "audit_events.py",
            "auto_execute_events.py",
            "auto_route_events.py",
            "auto_trigger_events.py",
            "base.py",
            "checkpoint_events.py",
            "compliance_events.py",
            "correction_events.py",
            "document_events.py",
            "enums.py",
            "heartbeat_events.py",
            "isolation_events.py",
            "memory_events.py",
            "planning_events.py",
            "routing_events.py",
            "tool_events.py",
        }

        actual_files = {f.name for f in py_files}
        extra_files = actual_files - expected_events
        missing_files = expected_events - actual_files

        assert not extra_files, f"Unexpected files in domain/events/: {extra_files}"
        assert not missing_files, f"Missing expected domain events: {missing_files}"
        assert len(py_files) == 17, f"Expected 17 domain event files, got {len(py_files)}"

    def test_infrastructure_messaging_directory_exists(self):
        """infrastructure/messaging/ directory should exist."""
        infra_dir = SRC_ROOT / "infrastructure" / "messaging"
        assert infra_dir.exists(), f"infrastructure/messaging/ directory should exist at {infra_dir}"
        assert infra_dir.is_dir(), f"{infra_dir} should be a directory"

    def test_infrastructure_messaging_contains_event_files(self):
        """infrastructure/messaging/ should contain the 4 moved event infrastructure files."""
        infra_dir = SRC_ROOT / "infrastructure" / "messaging"
        expected_files = {
            "event_publisher.py",
            "event_listener.py",
            "event_store_domain.py",
            "publish_result.py",
        }
        actual_files = {f.name for f in infra_dir.glob("*.py")}

        missing = expected_files - actual_files
        assert not missing, f"Missing expected files in infrastructure/messaging/: {missing}"
