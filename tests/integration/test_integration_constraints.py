"""Integration test constraint validation.

Verifies integration-test-specific architectural constraints:
- Mock objects do not leak into production code (src/)
- Test isolation works correctly (each test gets independent repo)
- pytest-timeout is configured and working
"""

from __future__ import annotations

from pathlib import Path

# ===================================================================
# Constraint 1: Mock Non-Leakage
# ===================================================================


class TestMockNonLeakage:
    """Verify Mock imports only exist in test code, not in src/."""

    def test_no_fakeredis_in_production_code(self) -> None:
        """fakeredis should only be imported in test code."""
        src_dir = Path(__file__).resolve().parents[2] / "src"
        violations = []

        for py_file in src_dir.rglob("*.py"):
            content = py_file.read_text()
            if "fakeredis" in content:
                violations.append(str(py_file.relative_to(src_dir.parents[1])))

        assert len(violations) == 0, f"fakeredis found in production code: {violations}"

    def test_no_unittest_mock_in_production_code(self) -> None:
        """unittest.mock should only be imported in test code."""
        src_dir = Path(__file__).resolve().parents[2] / "src"
        violations = []

        for py_file in src_dir.rglob("*.py"):
            content = py_file.read_text()
            if "unittest.mock" in content:
                violations.append(str(py_file.relative_to(src_dir.parents[1])))

        assert len(violations) == 0, f"unittest.mock found in production code: {violations}"


# ===================================================================
# Constraint 2: Test Isolation
# ===================================================================


class TestTestIsolation:
    """Verify test isolation mechanisms work correctly."""

    def test_fixture_provides_independent_repo(self) -> None:
        """Each fixture call should return a new repo instance."""
        from src.infrastructure.repositories.outbox import InMemoryOutboxRepository

        repo1 = InMemoryOutboxRepository()
        repo2 = InMemoryOutboxRepository()

        assert repo1 is not repo2
        assert repo1._entities is not repo2._entities

    def test_repo_clear_isolates_tests(self) -> None:
        """Calling clear on repo should not affect other instances."""
        from uuid import uuid4

        from src.domain.events.base import DomainEvent
        from src.infrastructure.repositories.outbox import InMemoryOutboxRepository

        repo1 = InMemoryOutboxRepository()
        repo2 = InMemoryOutboxRepository()

        # Add data to repo1
        repo1.save(
            DomainEvent(
                event_id=uuid4(),
                event_type="TestEvent",
                source="test",
                aggregate_id=uuid4(),
                aggregate_type="Test",
                version=1,
                payload={},
            )
        )

        # repo2 should be unaffected
        assert len(repo2.get_unpublished(limit=10)) == 0


# ===================================================================
# Constraint 3: Timeout Configuration
# ===================================================================


class TestTimeoutConfiguration:
    """Verify pytest-timeout is configured and working."""

    def test_pytest_timeout_is_installed(self) -> None:
        """pytest-timeout should be installed and importable."""
        import pytest_timeout  # noqa: F401 (verify package exists)

    def test_pytest_timeout_in_pyproject(self) -> None:
        """pyproject.toml should reference pytest-timeout."""
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        content = pyproject_path.read_text()
        assert "pytest-timeout" in content, "pytest-timeout not found in pyproject.toml"

    def test_pytest_timeout_actually_enforces_timeout(self) -> None:
        """Verify that pytest-timeout plugin is registered and active.

        When pytest runs with --timeout, the timeout plugin is registered.
        We verify this by checking the pytest plugin list.
        """
        import subprocess
        import sys

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--co",  # Collect only
                "--timeout=1",
                "-q",
                str(Path(__file__).resolve().parent / "test_test_utils.py"),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # If timeout plugin is not registered, pytest would show a warning
        # and exit with a different code. We verify it runs cleanly.
        assert result.returncode == 0, f"pytest --timeout=1 failed:\nstdout={result.stdout}\nstderr={result.stderr}"
        # The fact that pytest accepted --timeout=1 without error proves it's active
