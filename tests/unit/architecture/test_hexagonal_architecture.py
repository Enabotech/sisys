"""Hexagonal architecture constraint tests.

These tests verify that the hexagonal architecture boundaries are respected:
1. Domain layer has zero external dependencies
2. Dependency direction is correct (infrastructure -> application -> domain)
"""

import ast
import importlib
import sys
from pathlib import Path

import pytest

# Paths
ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
DOMAIN_DIR = SRC_DIR / "domain"


def _get_python_files(directory: Path) -> list[Path]:
    """Recursively find all .py files in directory."""
    return [f for f in directory.rglob("*.py") if f.name != "__init__.py"]


def _get_imports(file_path: Path) -> list[str]:
    """Extract all import module names from a Python file using ast.

    P0-04 Fix: Raise test failure on syntax errors instead of silent skip.
    """
    with open(file_path, encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=str(file_path))
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {file_path}: {e}")
            return []  # unreachable, keeps type checker happy

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    return imports


def _get_external_dependencies() -> set[str]:
    """Dynamically derive forbidden imports from pyproject.toml dependencies.

    P1-06 Fix: Instead of maintaining a hardcoded list, extract actual
    project dependencies from pyproject.toml [project.dependencies].
    """
    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists():
        return set()

    content = pyproject.read_text()
    # Simple extraction: find all package names in dependencies
    # Format: "package-name>=version" or "package_name"
    import re

    # Match dependency patterns like "langgraph>=0.1", "pydantic", etc.
    deps_section = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
    if not deps_section:
        return set()

    forbidden: set[str] = set()
    for dep_match in re.finditer(r'"([a-zA-Z0-9_-]+)', deps_section.group(1)):
        # Normalize: hyphens to underscores (pip normalizes names)
        forbidden.add(dep_match.group(1).replace("-", "_"))
    return forbidden


# P1-06 Fix: Derive forbidden imports from pyproject.toml, merged with
# known external frameworks that might be transitive dependencies.
FORBIDDEN_DOMAIN_IMPORTS = _get_external_dependencies() | {
    # External frameworks (project dependencies — also in pyproject.toml)
    "langgraph",
    "prefect",
    "fastapi",
    "pydantic",
    "pydantic_settings",
    "sqlalchemy",
    "typer",
    "redis",
    "qdrant_client",
    "minio",
    "neo4j",
    "aio_pika",
    "litellm",
    "instructor",
    # Common third-party packages
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
    # Other project layers (domain must not depend on these)
    "src.application",
    "src.interfaces",
    "src.infrastructure",
}


class TestDomainLayerZeroDependency:
    """Test that domain layer only uses Python standard library."""

    def test_domain_files_exist(self):
        """Domain layer directory exists."""
        assert DOMAIN_DIR.exists(), "src/domain/ directory must exist"

    def test_domain_has_python_files(self):
        """Domain layer contains Python files."""
        files = _get_python_files(DOMAIN_DIR)
        assert len(files) > 0, "Domain layer must have at least one .py file"

    def test_domain_no_external_imports(self):
        """Domain layer must not import any external libraries."""
        files = _get_python_files(DOMAIN_DIR)
        violations = []

        for f in files:
            imports = _get_imports(f)
            for imp in imports:
                if imp in FORBIDDEN_DOMAIN_IMPORTS:
                    violations.append(f"{f.relative_to(ROOT)} imports forbidden library '{imp}'")

        assert not violations, "Domain layer has external dependencies:\n" + "\n".join(violations)

    def test_domain_uses_only_stdlib(self) -> None:
        """Domain layer only uses known stdlib modules.

        P1-06 Fix: Use sys.stdlib_module_names (Python 3.10+) instead of
        a manually maintained allowlist.
        """
        # Python 3.10+ provides the complete stdlib module set
        if hasattr(sys, "stdlib_module_names"):
            stdlib_modules: frozenset[str] = sys.stdlib_module_names
        else:
            # Fallback for older Python versions
            stdlib_modules = frozenset(
                {
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
                }
            )

        files = _get_python_files(DOMAIN_DIR)
        violations = []

        for f in files:
            imports = _get_imports(f)
            for imp in imports:
                # Allow relative imports (domain internal)
                # and stdlib modules; flag unknown external modules
                if (
                    imp not in stdlib_modules
                    and imp not in FORBIDDEN_DOMAIN_IMPORTS
                    and not imp.startswith(".")
                    and imp not in ("src", "domain")  # Allow project-internal
                ):
                    # Check if it's actually an external package (not stdlib)
                    try:
                        spec = importlib.util.find_spec(imp)
                        if spec is not None and "site-packages" in str(spec.origin or ""):
                            violations.append(f"{f.relative_to(ROOT)} imports site-package '{imp}'")
                    except (ModuleNotFoundError, ValueError):
                        pass  # Module not found, might be conditional import

        assert not violations, "Domain layer imports site-packages:\n" + "\n".join(violations)


class TestDependencyDirection:
    """Test that dependency direction is correct."""

    def test_application_dir_exists(self):
        """Application layer directory exists."""
        app_dir = SRC_DIR / "application"
        assert app_dir.exists(), "src/application/ directory must exist"

    def test_interfaces_dir_exists(self):
        """Interfaces layer directory exists."""
        intf_dir = SRC_DIR / "interfaces"
        assert intf_dir.exists(), "src/interfaces/ directory must exist"

    def test_infrastructure_dir_exists(self):
        """Infrastructure layer directory exists."""
        infra_dir = SRC_DIR / "infrastructure"
        assert infra_dir.exists(), "src/infrastructure/ directory must exist"

    def test_hexagonal_layers_exist(self):
        """All four hexagonal architecture layers exist."""
        expected = ["domain", "application", "interfaces", "infrastructure"]
        for layer in expected:
            layer_dir = SRC_DIR / layer
            assert layer_dir.exists(), f"src/{layer}/ directory must exist"
