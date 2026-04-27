"""Unit tests for UDMR architecture validation."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent.parent


class TestUDMRArchitecture:
    """Test suite for UDMR architecture validation (hexagonal constraints)."""

    def test_udmr_files_have_no_external_dependencies(self) -> None:
        """UDMR files in domain layer should not import external frameworks."""
        udmr_files = [
            ROOT_DIR / "src" / "domain" / "services" / "udmr_router.py",
            ROOT_DIR / "src" / "domain" / "value_objects" / "routing_decision.py",
            ROOT_DIR / "src" / "domain" / "entities" / "routing_decision_log.py",
        ]
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

        violations = []
        for py_file in udmr_files:
            if not py_file.exists():
                continue
            content = py_file.read_text()
            for forbidden in forbidden_imports:
                if forbidden in content:
                    violations.append(f"{py_file.name}: contains '{forbidden}'")

        assert len(violations) == 0, "UDMR files violations:\n" + "\n".join(violations)

    def test_udmr_router_in_domain_layer(self) -> None:
        """UDMRouter should be in domain layer."""
        udmr_path = ROOT_DIR / "src" / "domain" / "services" / "udmr_router.py"
        assert udmr_path.exists(), "UDMRouter should be in domain/services/"

    def test_no_circular_dependencies_in_udmr(self) -> None:
        """UDMR components should not have circular dependencies."""
        udmr_files = [
            "src/domain/services/udmr_router.py",
            "src/domain/value_objects/routing_decision.py",
        ]
        result = subprocess.run(
            ["poetry", "run", "ruff", "check"] + udmr_files,
            capture_output=True,
            text=True,
            cwd=str(ROOT_DIR),
        )
        assert result.returncode == 0, f"Ruff check failed:\n{result.stderr}"

    def test_infrastructure_routing_isolated(self) -> None:
        """Infrastructure routing should not import domain services."""
        routing_dir = ROOT_DIR / "src" / "infrastructure" / "routing"
        domain_imports = [
            "src.domain.services.udmr_router",
            "src.domain.services.route_service",
        ]

        violations = []
        for py_file in routing_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            for forbidden in domain_imports:
                if forbidden in content:
                    violations.append(f"{py_file.name}: imports '{forbidden}'")

        assert len(violations) == 0, "Infrastructure routing violations:\n" + "\n".join(violations)
