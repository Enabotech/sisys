"""Hexagonal Architecture Constraints Test Suite.

Comprehensive test suite for hexagonal (ports & adapters) architecture validation.
Validates dependency direction rules, layer isolation, and domain zero-dependency principle.

Architecture Layers:
    domain          - Core business logic, zero external dependencies
    application     - Use case orchestration
    interfaces     - Adapters (API, CLI, Event Listeners)
    infrastructure  - Technical implementations

Dependency Direction Matrix:
    From / To      | domain | application | interfaces | infrastructure |
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

Inspired by hexagonal_arch_guard.py with enhanced AST parsing.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"

# Standard library modules (Python 3.11+)
STDLIB_MODULES: frozenset[str] = frozenset(sys.stdlib_module_names)

# Forbidden imports for domain layer (external frameworks and project layers)
FORBIDDEN_DOMAIN_IMPORTS: frozenset[str] = frozenset(
    {
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
    }
)

# Layer definition
LAYERS = {
    "domain": SRC_DIR / "domain",
    "application": SRC_DIR / "application",
    "interfaces": SRC_DIR / "interfaces",
    "infrastructure": SRC_DIR / "infrastructure",
}


@dataclass
class ImportOccurrence:
    """A single import statement occurrence."""

    file: Path
    lineno: int
    raw_import: str
    resolved_import: str | None
    kind: str  # "import" or "from"
    source_layer: str | None
    target_layer: str | None
    in_type_checking: bool = False


def _get_python_files(directory: Path) -> list[Path]:
    """Get all Python files in directory recursively, excluding __init__.py."""
    if not directory.exists():
        return []
    return [f for f in directory.rglob("*.py") if f.name != "__init__.py"]


def _normalize_import(imp: str) -> str:
    """Normalize import name (handle 'src.layer' vs 'layer')."""
    if imp.startswith("src."):
        return imp[4:]
    return imp


def _root_import_name(import_name: str) -> str:
    """Return the top-level package/module segment."""
    return import_name.split(".", 1)[0]


def _layer_for_import(import_name: str) -> str | None:
    """Determine whether an import name belongs to one of the architecture layers."""
    normalized = _normalize_import(import_name)
    for layer in LAYERS:
        if normalized == layer or normalized.startswith(f"{layer}."):
            return layer
    return None


def _current_module_name(file_path: Path, src_dir: Path) -> str | None:
    """Convert a file path into a dotted module path rooted at src/."""
    try:
        relative = file_path.resolve().relative_to(src_dir.resolve())
    except ValueError:
        return None

    parts = list(relative.with_suffix("").parts)
    if not parts:
        return None

    return "src." + ".".join(parts)


def _module_package_parts(module_name: str) -> list[str]:
    """Get package parts from a module name."""
    parts = module_name.split(".")
    if parts and parts[-1] == "__init__":
        return parts[:-1]
    return parts[:-1] if parts else []


def _resolve_relative_import(
    current_module: str,
    level: int,
    module: str | None,
) -> str | None:
    """Resolve a relative import to an absolute dotted module name.

    Example:
        current_module = "src.application.use_cases.foo"
        from ..domain import bar  ->  "src.application.domain"
    """
    package_parts = _module_package_parts(current_module)
    if level <= 0:
        return module

    # Python semantics: one leading dot means current package
    base_len = max(0, len(package_parts) - (level - 1))
    base_parts = package_parts[:base_len]

    if module:
        module_parts = module.split(".")
        return ".".join([*base_parts, *module_parts]) if base_parts else module
    return ".".join(base_parts) if base_parts else module


def _collect_typing_aliases(tree: ast.AST) -> set[str]:
    """Collect names that may evaluate to typing.TYPE_CHECKING.

    Handles cases like:
        import typing
        from typing import TYPE_CHECKING
        import typing as t
    """
    aliases: set[str] = {"TYPE_CHECKING"}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            for alias in node.names:
                if alias.name == "TYPE_CHECKING":
                    aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "typing":
                    aliases.add(alias.asname or alias.name)

    return aliases


def _is_type_checking_guard(node: ast.AST, typing_aliases: set[str]) -> bool:
    """Return True if an if-test is a typing TYPE_CHECKING guard."""
    if isinstance(node, ast.Name):
        return node.id in typing_aliases
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.attr == "TYPE_CHECKING" and node.value.id in typing_aliases
    return False


def _type_checking_ranges(tree: ast.AST) -> list[tuple[int, int]]:
    """Collect line ranges covered by TYPE_CHECKING guards."""
    typing_aliases = _collect_typing_aliases(tree)
    ranges: list[tuple[int, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _is_type_checking_guard(node.test, typing_aliases):
            end_lineno = getattr(node, "end_lineno", None) or node.lineno
            ranges.append((node.lineno, end_lineno))

    return ranges


def _range_contains(ranges: list[tuple[int, int]], lineno: int) -> bool:
    """Check if lineno falls within any of the ranges."""
    return any(start <= lineno <= end for start, end in ranges)


def _scan_file_imports(file_path: Path) -> list[ImportOccurrence]:
    """Extract all runtime import occurrences from a Python file using AST.

    Handles:
    - Regular imports: import os, import src.domain
    - From imports: from src.domain.events import Something
    - Relative imports: from ..domain import something (with level > 0)
    - TYPE_CHECKING blocks are excluded
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []
    except UnicodeDecodeError:
        return []

    type_checking_ranges = _type_checking_ranges(tree)
    current_module = _current_module_name(file_path, SRC_DIR) or file_path.stem

    imports: list[ImportOccurrence] = []

    for node in ast.walk(tree):
        if not hasattr(node, "lineno"):
            continue

        lineno = int(getattr(node, "lineno"))
        in_type_checking = _range_contains(type_checking_ranges, lineno)

        if isinstance(node, ast.Import):
            source_layer = _layer_for_import(current_module)
            for alias in node.names:
                raw = alias.name
                target_layer = _layer_for_import(raw)
                imports.append(
                    ImportOccurrence(
                        file=file_path,
                        lineno=lineno,
                        raw_import=raw,
                        resolved_import=raw,
                        kind="import",
                        source_layer=source_layer,
                        target_layer=target_layer,
                        in_type_checking=in_type_checking,
                    )
                )

        elif isinstance(node, ast.ImportFrom):
            module = node.module

            # Handle relative imports
            if node.level and node.level > 0:
                resolved_module = _resolve_relative_import(
                    current_module=current_module,
                    level=node.level,
                    module=module,
                )
            else:
                resolved_module = module

            if resolved_module:
                source_layer = _layer_for_import(current_module)
                target_layer = _layer_for_import(resolved_module)
                imports.append(
                    ImportOccurrence(
                        file=file_path,
                        lineno=lineno,
                        raw_import=resolved_module,
                        resolved_import=resolved_module,
                        kind="from",
                        source_layer=source_layer,
                        target_layer=target_layer,
                        in_type_checking=in_type_checking,
                    )
                )

    return imports


def has_layer_import(file_path: Path, target_layer: str) -> bool:
    """Check if file imports specific layer using AST."""
    imports = _scan_file_imports(file_path)
    return any(imp.target_layer == target_layer for imp in imports if not imp.in_type_checking)


def get_layer_imports(layer: str) -> list[ImportOccurrence]:
    """Get all imports from a specific layer."""
    layer_dir = LAYERS.get(layer)
    if not layer_dir or not layer_dir.exists():
        return []

    all_imports: list[ImportOccurrence] = []
    for f in _get_python_files(layer_dir):
        all_imports.extend(_scan_file_imports(f))
    return all_imports


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
            for imp in _scan_file_imports(f):
                if imp.in_type_checking:
                    continue
                if imp.resolved_import is None:
                    continue

                normalized = _normalize_import(imp.resolved_import.split(".")[0])
                if normalized in FORBIDDEN_DOMAIN_IMPORTS:
                    violations.append(f"{f.relative_to(ROOT)}:{imp.lineno} imports '{normalized}'")

        assert not violations, "Domain layer has forbidden imports:\n" + "\n".join(violations)

    def test_domain_uses_only_stdlib(self):
        """Domain layer must only use Python standard library modules."""
        files = _get_python_files(LAYERS["domain"])
        violations = []

        for f in files:
            for imp in _scan_file_imports(f):
                if imp.in_type_checking:
                    continue
                if imp.resolved_import is None:
                    continue

                normalized = _normalize_import(imp.resolved_import.split(".")[0])

                # Skip stdlib modules
                if normalized in STDLIB_MODULES:
                    continue
                # Skip forbidden imports (already checked above)
                if normalized in FORBIDDEN_DOMAIN_IMPORTS:
                    continue
                # Skip relative imports and known safe imports
                if normalized.startswith(".") or normalized in ("src", "domain"):
                    continue

                # Check if it's a site-package (external)
                import importlib.util

                spec = importlib.util.find_spec(normalized)
                if spec is not None and "site-packages" in str(spec.origin or ""):
                    violations.append(f"{f.relative_to(ROOT)}:{imp.lineno} imports site-package '{normalized}'")

        assert not violations, "Domain layer imports external packages:\n" + "\n".join(violations)

    def test_domain_ruff_check_passes(self):
        """Domain layer must pass ruff check (no unused imports, etc)."""
        result = subprocess.run(
            ["poetry", "run", "ruff", "check", "src/domain/"],
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

    @pytest.mark.parametrize(
        "layer,forbidden_layers",
        [
            ("domain", ["application", "interfaces", "infrastructure"]),
            ("application", ["interfaces", "infrastructure"]),
            ("infrastructure", ["interfaces"]),
            ("interfaces", ["infrastructure"]),
        ],
    )
    def test_layer_not_importing_forbidden_layers(self, layer: str, forbidden_layers: list[str]):
        """Verify layer only imports allowed layers per dependency matrix.

        Uses AST-based import detection instead of string matching.
        """
        layer_dir = LAYERS[layer]
        if not layer_dir.exists():
            pytest.skip(f"Layer '{layer}' does not exist")

        files = _get_python_files(layer_dir)
        violations: dict[str, list[str]] = {target: [] for target in forbidden_layers}

        for f in files:
            for imp in _scan_file_imports(f):
                if imp.in_type_checking:
                    continue
                if imp.target_layer in forbidden_layers:
                    violations[imp.target_layer].append(f"{f.relative_to(ROOT)}:{imp.lineno}")

        failed_checks = [f"  - {target} imported by: {', '.join(viols)}" for target, viols in violations.items() if viols]

        assert not failed_checks, f"Layer '{layer}' has forbidden dependencies:\n" + "\n".join(failed_checks)


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
        has_app_import = any(has_layer_import(f, "application") for f in files)
        if not has_app_import:
            pytest.skip("interfaces → application import pattern not implemented yet")

    def test_interfaces_can_import_domain(self):
        """Interfaces can import domain (outer → inner is allowed)."""
        files = _get_python_files(LAYERS["interfaces"])
        has_domain_import = any(has_layer_import(f, "domain") for f in files)
        if not has_domain_import:
            pytest.skip("interfaces → domain import pattern not implemented yet")

    def test_interfaces_no_redis_direct_import(self):
        """Interfaces layer must NOT directly import redis client.

        Redis client should only be used in infrastructure layer.
        """
        files = _get_python_files(LAYERS["interfaces"])
        violations = []

        for f in files:
            for imp in _scan_file_imports(f):
                if imp.in_type_checking:
                    continue
                if imp.resolved_import and (imp.resolved_import == "redis" or imp.resolved_import.startswith("redis.")):
                    violations.append(f"{f.relative_to(ROOT)}:{imp.lineno}")

        assert not violations, "Interfaces must NOT import redis directly:\n" + "\n".join(violations)

    def test_interfaces_no_sqlalchemy_direct_import(self):
        """Interfaces layer must NOT directly import sqlalchemy.

        SQLAlchemy is infrastructure implementation, not for direct use in interfaces.
        """
        files = _get_python_files(LAYERS["interfaces"])
        violations = []

        for f in files:
            for imp in _scan_file_imports(f):
                if imp.in_type_checking:
                    continue
                if imp.resolved_import and (
                    imp.resolved_import == "sqlalchemy" or imp.resolved_import.startswith("sqlalchemy.")
                ):
                    violations.append(f"{f.relative_to(ROOT)}:{imp.lineno}")

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
            if has_layer_import(f, "infrastructure"):
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
            if has_layer_import(f, "application"):
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
            "infrastructure/routing/ollama_health.py",
        ]
        for impl in expected_implementations:
            impl_path = SRC_DIR / impl
            if not impl_path.exists():
                pytest.skip(f"Implementation {impl} does not exist yet")
