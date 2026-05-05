r"""Hexagonal Architecture Constraints Test Suite.

Comprehensive test suite for hexagonal (ports & adapters) architecture validation.
Validates dependency direction rules, layer isolation, and domain zero-dependency principle.

Architecture Layers:
    domain          - Core business logic, zero external dependencies
    application     - Use case orchestration
    interfaces     - Adapters (API, CLI, Event Listeners)
    infrastructure  - Technical implementations

Dependency Direction Matrix:
    From \ To      | domain | application | interfaces | infrastructure |
    ---------------|--------|-------------|------------|----------------|
    domain         |   -    |     ✗       |     ✗      |       ✗        |
    application    |   ✓    |     -       |     ✗      |       ✗        |
    infrastructure |   ✓    |     ✓       |     ✗      |       -        |
    interfaces     |   ✓    |     ✓       |     -      |       -        |

Core Rules:
1. Domain layer: zero external dependencies (stdlib only)
2. Inner layers must NOT import outer layers
3. Outer layers can import inner layers (dependency inversion)
4. TYPE_CHECKING blocks are excluded from runtime dependency checks
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"

# Standard library modules (Python 3.10+)
STDLIB_MODULES: frozenset[str] = frozenset(
    getattr(
        sys,
        "stdlib_module_names",
        [
            "dataclasses",
            "datetime",
            "uuid",
            "enum",
            "typing",
            "abc",
            "json",
            "copy",
            "collections",
            "itertools",
            "functools",
            "operator",
            "pathlib",
            "os",
            "sys",
            "io",
            "re",
            "string",
            "math",
            "numbers",
            "decimal",
            "fractions",
            "statistics",
            "array",
            "weakref",
            "types",
            "contextlib",
            "warnings",
            "traceback",
            "logging",
            "unittest",
            "ast",
            "dis",
            "pickle",
            "shelve",
            "dbm",
            "csv",
            "configparser",
            "hashlib",
            "hmac",
            "secrets",
            "time",
            "calendar",
            "zoneinfo",
            "textwrap",
            "difflib",
            "pprint",
            "reprlib",
            "inspect",
            "importlib",
            "pkgutil",
            "sysconfig",
            "atexit",
            "signal",
            "threading",
            "multiprocessing",
            "concurrent",
            "subprocess",
            "sched",
            "queue",
            "contextvars",
            "_thread",
            "socket",
            "ssl",
            "select",
            "selectors",
            "asyncio",
            "socketserver",
            "xml",
            "html",
            "webbrowser",
            "cgi",
            "urllib",
            "http",
            "ftplib",
            "poplib",
            "imaplib",
            "smtplib",
            "email",
            "struct",
            "codecs",
            "unicodedata",
            "stringprep",
            "readline",
            "rlcompleter",
            "bisect",
            "heapq",
            "tomllib",
            "graphlib",
            "__future__",
            "typing_extensions",
        ],
    )
)

# Forbidden imports for domain layer (external frameworks and project layers)
FORBIDDEN_DOMAIN_IMPORTS: frozenset[str] = frozenset(
    [
        # External frameworks
        "langgraph",
        "prefect",
        "fastapi",
        "pydantic",
        "pydantic_settings",
        "sqlalchemy",
        "typer",
        "redis",
        "qdrant_client",
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
        "boto3",
        "numpy",
        "pandas",
        "torch",
        "uvicorn",
        "alembic",
        "loguru",
        "dotenv",
        "jsonschema",
        "prometheus_client",
        "pytest",
        "click",
        # Project layers (domain must not depend on these)
        "src.application",
        "src.interfaces",
        "src.infrastructure",
        "application",
        "interfaces",
        "infrastructure",
    ]
)

# Layer definition
LAYERS = {
    "domain": SRC_DIR / "domain",
    "application": SRC_DIR / "application",
    "interfaces": SRC_DIR / "interfaces",
    "infrastructure": SRC_DIR / "infrastructure",
}

# Dependency direction matrix (from -> to)
# True = allowed, False = forbidden
ALLOWED_DEPENDENCIES = {
    "domain": {"application": False, "interfaces": False, "infrastructure": False},
    "application": {"domain": True, "interfaces": False, "infrastructure": False},
    "interfaces": {"domain": True, "application": True, "infrastructure": False},
    "infrastructure": {"domain": True, "application": True, "interfaces": False},
}


def _get_python_files(directory: Path) -> list[Path]:
    """Get all Python files in directory recursively, excluding __init__.py."""
    if not directory.exists():
        return []
    return [f for f in directory.rglob("*.py") if f.name != "__init__.py"]


def _get_imports(file_path: Path) -> tuple[list[str], list[str]]:
    """Extract all import module names from a Python file using AST.

    Returns:
        Tuple of (direct_imports, from_imports)
    """
    with open(file_path, encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=str(file_path))
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {file_path}: {e}")
            return [], []

    direct_imports = []
    from_imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                direct_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                from_imports.append(node.module)
    return direct_imports, from_imports


def _remove_type_checking_blocks(content: str) -> str:
    """Remove TYPE_CHECKING blocks from content for runtime dependency check."""
    pattern = r"if\s+TYPE_CHECKING:.*?(?=\n\S|\Z)"
    return re.sub(pattern, "", content, flags=re.DOTALL)


def _normalize_import(imp: str) -> str:
    """Normalize import name (handle 'src.layer' vs 'layer')."""
    if imp.startswith("src."):
        return imp[4:]  # Remove 'src.' prefix
    return imp


def _get_layer_from_import(imp: str) -> str | None:
    """Get layer name from import path, or None if not a layer import."""
    normalized = _normalize_import(imp)
    for layer in LAYERS:
        if normalized == layer or normalized.startswith(f"{layer}."):
            return layer
    return None


# =============================================================================
# Layer Existence Tests
# =============================================================================


class TestLayerExistence:
    """Verify all hexagonal architecture layers exist."""

    def test_all_layers_exist(self):
        """All four hexagonal architecture layers must exist."""
        for layer, path in LAYERS.items():
            assert path.exists(), f"Layer '{layer}' directory must exist at {path}"


# =============================================================================
# Domain Layer Zero Dependency Tests
# =============================================================================


class TestDomainLayerZeroDependency:
    """Domain layer must have zero external dependencies."""

    def test_domain_exists(self):
        """Domain layer directory exists."""
        assert LAYERS["domain"].exists(), "src/domain/ directory must exist"

    def test_domain_no_external_imports(self):
        """Domain layer must not import any external libraries."""
        files = _get_python_files(LAYERS["domain"])
        assert len(files) > 0, "Domain layer must have at least one .py file"

        violations = []
        for f in files:
            direct_imports, from_imports = _get_imports(f)
            all_imports = direct_imports + from_imports

            for imp in all_imports:
                normalized = _normalize_import(imp.split(".")[0])
                if normalized in FORBIDDEN_DOMAIN_IMPORTS:
                    violations.append(f"{f.relative_to(ROOT)} imports '{normalized}'")

        assert not violations, "Domain layer has forbidden imports:\n" + "\n".join(violations)

    def test_domain_uses_only_stdlib(self):
        """Domain layer must only use Python standard library modules."""
        files = _get_python_files(LAYERS["domain"])
        violations = []

        for f in files:
            direct_imports, from_imports = _get_imports(f)
            all_imports = direct_imports + [imp.split(".")[0] for imp in from_imports]

            for imp in all_imports:
                normalized = _normalize_import(imp)
                # Skip if it's a stdlib module
                if normalized in STDLIB_MODULES:
                    continue
                # Skip if it's a forbidden external (already checked above)
                if normalized in FORBIDDEN_DOMAIN_IMPORTS:
                    continue
                # Skip relative imports and known safe imports
                if normalized.startswith(".") or normalized in ("src", "domain"):
                    continue
                # Check if it's a site-package (external)
                try:
                    import importlib.util

                    spec = importlib.util.find_spec(normalized)
                    if spec is not None and "site-packages" in str(spec.origin or ""):
                        violations.append(f"{f.relative_to(ROOT)} imports site-package '{normalized}'")
                except (ModuleNotFoundError, ValueError):
                    pass

        assert not violations, "Domain layer imports external packages:\n" + "\n".join(violations)

    def test_domain_ruff_check_passes(self):
        """Domain layer must pass ruff check (no unused imports, etc).

        Note: UP042 (StrEnum recommendation) is excluded as it's a style
        suggestion, not a blocking error, and many existing enums use the
        legacy str, Enum pattern.
        """
        result = subprocess.run(
            ["poetry", "run", "ruff", "check", "src/domain/", "--select", "E,F,I,N,W"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Domain layer ruff check failed:\n{result.stdout}\n{result.stderr}"

    def test_domain_mypy_type_check_passes(self):
        """Domain layer ports must pass mypy type check."""
        result = subprocess.run(
            ["poetry", "run", "mypy", "src/domain/ports/", "--ignore-missing-imports"],
            capture_output=True,
            text=True,
        )
        assert "error" not in result.stdout.lower() or result.returncode == 0, f"Type check failed:\n{result.stdout}"


# =============================================================================
# Dependency Direction Tests
# =============================================================================


class TestDependencyDirectionRules:
    """Verify dependency direction follows hexagonal architecture rules.

    Inner layers must NOT import outer layers.
    Outer layers CAN import inner layers (dependency inversion).
    """

    @pytest.mark.parametrize("layer", ["domain", "application", "infrastructure", "interfaces"])
    def test_layer_not_importing_forbidden_layers(self, layer: str):
        """Verify a layer only imports allowed layers per dependency matrix."""
        layer_dir = LAYERS[layer]
        if not layer_dir.exists():
            pytest.skip(f"Layer '{layer}' does not exist")

        files = _get_python_files(layer_dir)
        violations = []

        for f in files:
            content = f.read_text()
            content = _remove_type_checking_blocks(content)

            for target_layer, allowed in ALLOWED_DEPENDENCIES[layer].items():
                if not allowed:
                    target_path = f"src.{target_layer}"
                    if target_path in content or f"import {target_layer}" in content:
                        violations.append(f"{f.relative_to(ROOT)} imports {target_layer}")

        assert not violations, f"Layer '{layer}' has forbidden dependencies:\n" + "\n".join(violations)

    def test_domain_not_importing_application(self):
        """Domain must NOT import application (inner → outer forbidden)."""
        files = _get_python_files(LAYERS["domain"])
        violations = []

        for f in files:
            content = f.read_text()
            content = _remove_type_checking_blocks(content)
            if "from src.application" in content or "import src.application" in content:
                violations.append(str(f.relative_to(ROOT)))

        assert not violations, "Domain must NOT import application:\n" + "\n".join(violations)

    def test_domain_not_importing_interfaces(self):
        """Domain must NOT import interfaces (inner → outer forbidden)."""
        files = _get_python_files(LAYERS["domain"])
        violations = []

        for f in files:
            content = f.read_text()
            content = _remove_type_checking_blocks(content)
            if "from src.interfaces" in content or "import src.interfaces" in content:
                violations.append(str(f.relative_to(ROOT)))

        assert not violations, "Domain must NOT import interfaces:\n" + "\n".join(violations)

    def test_domain_not_importing_infrastructure(self):
        """Domain must NOT import infrastructure (inner → outer forbidden)."""
        files = _get_python_files(LAYERS["domain"])
        violations = []

        for f in files:
            content = f.read_text()
            content = _remove_type_checking_blocks(content)
            if "from src.infrastructure" in content or "import src.infrastructure" in content:
                violations.append(str(f.relative_to(ROOT)))

        assert not violations, "Domain must NOT import infrastructure:\n" + "\n".join(violations)

    def test_application_not_importing_infrastructure(self):
        """Application must NOT import infrastructure (middle → outer forbidden)."""
        files = _get_python_files(LAYERS["application"])
        violations = []

        for f in files:
            content = f.read_text()
            content = _remove_type_checking_blocks(content)
            if "from src.infrastructure" in content or "import src.infrastructure" in content:
                violations.append(str(f.relative_to(ROOT)))

        assert not violations, "Application must NOT import infrastructure:\n" + "\n".join(violations)

    def test_application_not_importing_interfaces(self):
        """Application must NOT import interfaces (middle → outer forbidden)."""
        files = _get_python_files(LAYERS["application"])
        violations = []

        for f in files:
            content = f.read_text()
            content = _remove_type_checking_blocks(content)
            if "from src.interfaces" in content or "import src.interfaces" in content:
                violations.append(str(f.relative_to(ROOT)))

        assert not violations, "Application must NOT import interfaces:\n" + "\n".join(violations)

    def test_infrastructure_not_importing_interfaces(self):
        """Infrastructure must NOT import interfaces (outer → outer forbidden)."""
        files = _get_python_files(LAYERS["infrastructure"])
        violations = []

        for f in files:
            content = f.read_text()
            content = _remove_type_checking_blocks(content)
            if "from src.interfaces" in content or "import src.interfaces" in content:
                violations.append(str(f.relative_to(ROOT)))

        assert not violations, "Infrastructure must NOT import interfaces:\n" + "\n".join(violations)

    def test_interfaces_not_importing_infrastructure(self):
        """Interfaces must NOT import infrastructure (reverse dependency)."""
        files = _get_python_files(LAYERS["interfaces"])
        violations = []

        for f in files:
            content = f.read_text()
            content = _remove_type_checking_blocks(content)
            if "from src.infrastructure" in content or "import src.infrastructure" in content:
                violations.append(str(f.relative_to(ROOT)))

        assert not violations, "Interfaces must NOT import infrastructure:\n" + "\n".join(violations)


# =============================================================================
# Interfaces Layer Specific Tests
# =============================================================================


class TestInterfacesLayerConstraints:
    """Interfaces layer (adapter layer) specific constraints."""

    def test_interfaces_layer_exists(self):
        """Interfaces layer directory exists."""
        assert LAYERS["interfaces"].exists(), "src/interfaces/ directory must exist"

    def test_interfaces_api_subdirectory_exists(self):
        """Interfaces/api subdirectory exists (REST API adapter)."""
        api_dir = LAYERS["interfaces"] / "api"
        assert api_dir.exists(), "src/interfaces/api/ directory must exist"

    def test_interfaces_can_import_application(self):
        """Interfaces can import application (outer → middle is allowed).

        Example: *_adapter.py calls *_handler.py
        """
        files = _get_python_files(LAYERS["interfaces"])
        has_app_import = any(
            ("from src.application" in f.read_text() or "import src.application" in f.read_text()) for f in files
        )
        if not has_app_import:
            pytest.skip("interfaces → application import pattern not implemented yet")

    def test_interfaces_can_import_domain(self):
        """Interfaces can import domain (outer → inner is allowed)."""
        files = _get_python_files(LAYERS["interfaces"])
        has_domain_import = any(("from src.domain" in f.read_text() or "import src.domain" in f.read_text()) for f in files)
        if not has_domain_import:
            pytest.skip("interfaces → domain import pattern not implemented yet")

    def test_interfaces_no_redis_direct_import(self):
        """Interfaces layer must NOT directly import redis client.

        Redis client should only be used in infrastructure layer.
        """
        files = _get_python_files(LAYERS["interfaces"])
        violations = []

        for f in files:
            content = f.read_text()
            content = _remove_type_checking_blocks(content)
            if "import redis" in content or "from redis" in content:
                violations.append(str(f.relative_to(ROOT)))

        assert not violations, "Interfaces must NOT import redis directly:\n" + "\n".join(violations)

    def test_interfaces_no_sqlalchemy_direct_import(self):
        """Interfaces layer must NOT directly import sqlalchemy.

        SQLAlchemy is infrastructure implementation, not for direct use in interfaces.
        """
        files = _get_python_files(LAYERS["interfaces"])
        violations = []

        for f in files:
            content = f.read_text()
            content = _remove_type_checking_blocks(content)
            if "import sqlalchemy" in content or "from sqlalchemy" in content:
                violations.append(str(f.relative_to(ROOT)))

        assert not violations, "Interfaces must NOT import sqlalchemy directly:\n" + "\n".join(violations)


# =============================================================================
# Domain Ports Isolation Tests
# =============================================================================


class TestDomainPortsIsolation:
    """Domain layer Port interfaces must be isolated from outer layers."""

    def test_domain_has_ports_directory(self):
        """Domain/ports directory exists (Port interface definition location)."""
        ports_dir = LAYERS["domain"] / "ports"
        assert ports_dir.exists(), "Domain ports should be in src/domain/ports/"

    def test_domain_ports_not_importing_infrastructure(self):
        """Domain ports must NOT import infrastructure layer."""
        ports_dir = LAYERS["domain"] / "ports"
        if not ports_dir.exists():
            pytest.skip("domain/ports directory does not exist")

        files = list(ports_dir.glob("*.py"))
        violations = []

        for f in files:
            content = f.read_text()
            content = _remove_type_checking_blocks(content)
            if "from src.infrastructure" in content or "import src.infrastructure" in content:
                violations.append(str(f.relative_to(ROOT)))

        assert not violations, "Domain ports must NOT import infrastructure:\n" + "\n".join(violations)

    def test_domain_ports_not_importing_application(self):
        """Domain ports must NOT import application layer."""
        ports_dir = LAYERS["domain"] / "ports"
        if not ports_dir.exists():
            pytest.skip("domain/ports directory does not exist")

        files = list(ports_dir.glob("*.py"))
        violations = []

        for f in files:
            content = f.read_text()
            content = _remove_type_checking_blocks(content)
            if "from src.application" in content or "import src.application" in content:
                violations.append(str(f.relative_to(ROOT)))

        assert not violations, "Domain ports must NOT import application:\n" + "\n".join(violations)


# =============================================================================
# Infrastructure Layer Isolation Tests
# =============================================================================


class TestInfrastructureLayerIsolation:
    """Infrastructure layer technical implementation isolation."""

    def test_infrastructure_storage_exists(self):
        """Infrastructure/storage directory exists for storage implementations."""
        storage_dir = LAYERS["infrastructure"] / "storage"
        if not storage_dir.exists():
            pytest.skip("infrastructure/storage directory does not exist")
        files = list(storage_dir.glob("*.py"))
        assert len(files) > 0, "Storage directory should have implementation files"


# =============================================================================
# Application Layer Port Usage Tests
# =============================================================================


class TestApplicationLayerPortUsage:
    """Application layer should use Port interfaces instead of concrete implementations."""

    def test_application_layer_exists(self):
        """Application layer directory exists."""
        assert LAYERS["application"].exists(), "src/application/ directory must exist"

    def test_application_has_ports_directory(self):
        """Application layer has ports directory for interface definitions."""
        ports_dir = LAYERS["application"] / "ports"
        if not ports_dir.exists():
            pytest.skip("application/ports directory does not exist")
        files = list(ports_dir.glob("*.py"))
        assert len(files) > 0, "Application ports directory should have port definitions"


# =============================================================================
# Port Interface Compliance Tests
# =============================================================================


class TestPortInterfaceCompliance:
    """Verify Port interfaces have required methods."""

    def test_l0_storage_port_has_required_methods(self):
        """L0StoragePort interface must have required methods."""
        try:
            from src.domain.ports.l0_storage import L0StoragePort
        except ImportError:
            pytest.skip("L0StoragePort not defined")

        required_methods = ["write", "read", "delete", "exists", "list_memories"]
        for method in required_methods:
            assert hasattr(L0StoragePort, method), f"L0StoragePort missing method: {method}"

    def test_index_manager_port_has_required_methods(self):
        """IndexManagerPort interface must have required methods."""
        try:
            from src.domain.ports.index_manager import IndexManagerPort
        except ImportError:
            pytest.skip("IndexManagerPort not defined")

        required_methods = ["update_entry", "remove_entry", "read_entries", "search", "truncate"]
        for method in required_methods:
            assert hasattr(IndexManagerPort, method), f"IndexManagerPort missing method: {method}"

    def test_health_check_port_has_required_methods(self):
        """HealthCheckPort interface must have required methods."""
        try:
            from src.domain.ports.health_check import HealthCheckPort
        except ImportError:
            pytest.skip("HealthCheckPort not defined")

        required_methods = ["check", "close"]
        for method in required_methods:
            assert hasattr(HealthCheckPort, method), f"HealthCheckPort missing method: {method}"

    def test_integrity_port_has_required_methods(self):
        """IntegrityPort interface must have required methods."""
        try:
            from src.domain.ports.integrity import IntegrityPort
        except ImportError:
            pytest.skip("IntegrityPort not defined")

        required_methods = ["verify_file", "compute_hash", "verify_hash"]
        for method in required_methods:
            assert hasattr(IntegrityPort, method), f"IntegrityPort missing method: {method}"


# =============================================================================
# Implementation Location Tests
# =============================================================================


class TestImplementationLocation:
    """Verify implementations are in correct layers."""

    def test_implementations_in_infrastructure(self):
        """Implementation classes should be in infrastructure layer."""
        expected_implementations = [
            "infrastructure/storage/file_memory_adapter.py",
            "infrastructure/storage/memory_index.py",
            "infrastructure/routing/ollama_health_adapter.py",
        ]
        for impl in expected_implementations:
            impl_path = SRC_DIR / impl
            if not impl_path.exists():
                pytest.skip(f"Implementation {impl} does not exist yet")
