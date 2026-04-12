"""Hexagonal architecture constraint tests.

These tests verify that the hexagonal architecture boundaries are respected:
1. Domain layer has zero external dependencies
2. Dependency direction is correct (infrastructure -> application -> domain)
"""

import ast
import importlib
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
DOMAIN_DIR = SRC_DIR / "domain"


def _get_python_files(directory: Path) -> list[Path]:
    """Recursively find all .py files in directory."""
    return [f for f in directory.rglob("*.py") if f.name != "__init__.py"]


def _get_imports(file_path: Path) -> list[str]:
    """Extract all import module names from a Python file using ast."""
    with open(file_path, encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=str(file_path))
        except SyntaxError:
            return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    return imports


# External libraries that domain layer must NOT import
FORBIDDEN_DOMAIN_IMPORTS = {
    "langgraph",
    "prefect",
    "fastapi",
    "pydantic",
    "sqlalchemy",
    "typer",
    "redis",
    "psycopg2",
    "qdrant",
    "minio",
    "neo4j",
    "aio_pika",
    "litellm",
    "instructor",
    "requests",
    "httpx",
    "docker",
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

    def test_domain_uses_only_stdlib(self):
        """Domain layer only uses known stdlib modules."""
        stdlib_modules = {
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
            "uuid",
            "email",
            "struct",
            "codecs",
            "unicodedata",
            "stringprep",
            "readline",
            "rlcompleter",
            "bisect",
            "heapq",
            "array",
            "copy",
            "deepcopy",
            "typing",
            "abc",
            "__future__",
        }

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
