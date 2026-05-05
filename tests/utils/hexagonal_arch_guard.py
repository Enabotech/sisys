"""Hexagonal architecture constraint engine.

This module provides a production-oriented scanner for validating hexagonal
(ports & adapters) architecture rules in Python projects.

Features:
- AST-based import extraction
- TYPE_CHECKING-aware dependency checks
- Layer-to-layer dependency matrix validation
- Forbidden import root checks per layer
- Domain zero-external-dependency validation
- Required directory / file structure checks
- Optional port interface contract checks
- Human-readable report and JSON output
- CLI entry point for CI usage

The engine is intentionally framework-light: it depends only on the Python
standard library and can be embedded in pytest, pre-commit, or a custom CI job.

Typical usage:
    from hexagonal_arch_guard import assert_hexagonal_architecture
    assert_hexagonal_architecture()

Or from the CLI:
    python hexagonal_arch_guard.py --root /path/to/repo
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import importlib
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

STD_LIB_MODULES: frozenset[str] = frozenset(sys.stdlib_module_names)

DEFAULT_EXTERNAL_FORBIDDEN: frozenset[str] = frozenset(
    {
        # common framework / infra packages that should not leak into domain
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
    }
)

DEFAULT_LAYERS: tuple[str, ...] = ("domain", "application", "interfaces", "infrastructure")

DEFAULT_ALLOWED_DEPENDENCIES: dict[str, frozenset[str]] = {
    "domain": frozenset(),
    "application": frozenset({"domain"}),
    "interfaces": frozenset({"domain", "application"}),
    "infrastructure": frozenset({"domain", "application"}),
}

DEFAULT_FORBIDDEN_IMPORTS: dict[str, frozenset[str]] = {
    "domain": frozenset(
        set(DEFAULT_EXTERNAL_FORBIDDEN)
        | {"src.application", "src.interfaces", "src.infrastructure"}
        | {"application", "interfaces", "infrastructure"}
    ),
    # adapter rule examples from the supplied test suite
    "interfaces": frozenset({"redis", "sqlalchemy"}),
}

DEFAULT_REQUIRED_DIRECTORIES: tuple[str, ...] = (
    "src/domain",
    "src/application",
    "src/interfaces",
    "src/infrastructure",
    "src/interfaces/api",
    "src/domain/ports",
    "src/application/ports",
)

DEFAULT_REQUIRED_NONEMPTY_DIRECTORIES: tuple[str, ...] = (
    "src/domain",
    "src/application",
    "src/interfaces",
    "src/infrastructure",
)


@dataclass(frozen=True, slots=True)
class PortContract:
    """Interface contract used to validate that a port exposes required methods."""

    module: str
    symbol: str
    required_methods: tuple[str, ...]


DEFAULT_PORT_CONTRACTS: tuple["PortContract", ...] = (
    # The module paths below match the supplied suite conventions.
    # Missing modules are reported as skipped rather than hard failures.
    PortContract(
        module="src.domain.ports.l0_storage",
        symbol="L0StoragePort",
        required_methods=("write", "read", "delete", "exists", "list_memories"),
    ),
    PortContract(
        module="src.domain.ports.index_manager",
        symbol="IndexManagerPort",
        required_methods=("update_entry", "remove_entry", "read_entries", "search", "truncate"),
    ),
    PortContract(
        module="src.domain.ports.health_check",
        symbol="HealthCheckPort",
        required_methods=("check", "close"),
    ),
    PortContract(
        module="src.domain.ports.integrity",
        symbol="IntegrityPort",
        required_methods=("verify_file", "compute_hash", "verify_hash"),
    ),
)


@dataclass(frozen=True, slots=True)
class ImportOccurrence:
    """A single import statement occurrence."""

    file: Path
    lineno: int
    raw_import: str
    resolved_import: str | None
    kind: str  # "import" or "from"
    source_layer: str | None
    target_layer: str | None
    in_type_checking: bool


@dataclass(frozen=True, slots=True)
class Violation:
    """A concrete architecture rule violation."""

    code: str
    message: str
    file: Path | None = None
    lineno: int | None = None
    source_layer: str | None = None
    target_layer: str | None = None
    import_name: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True, slots=True)
class CheckNote:
    """Non-fatal note emitted during scanning (e.g. skipped optional contract)."""

    code: str
    message: str


@dataclass(slots=True)
class ArchitectureReport:
    """Aggregated output of a scan."""

    root: Path
    src_dir: Path
    scanned_files: int = 0
    violations: list[Violation] = field(default_factory=list)
    warnings: list[CheckNote] = field(default_factory=list)
    skipped: list[CheckNote] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def add_violation(
        self,
        code: str,
        message: str,
        *,
        file: Path | None = None,
        lineno: int | None = None,
        source_layer: str | None = None,
        target_layer: str | None = None,
        import_name: str | None = None,
    ) -> None:
        self.violations.append(
            Violation(
                code=code,
                message=message,
                file=file,
                lineno=lineno,
                source_layer=source_layer,
                target_layer=target_layer,
                import_name=import_name,
            )
        )

    def add_warning(self, code: str, message: str) -> None:
        self.warnings.append(CheckNote(code=code, message=message))

    def add_skipped(self, code: str, message: str) -> None:
        self.skipped.append(CheckNote(code=code, message=message))

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "src_dir": str(self.src_dir),
            "scanned_files": self.scanned_files,
            "ok": self.ok,
            "violations": [v.as_dict() for v in self.violations],
            "warnings": [dataclasses.asdict(w) for w in self.warnings],
            "skipped": [dataclasses.asdict(s) for s in self.skipped],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def format_text(self) -> str:
        lines: list[str] = []
        lines.append(f"Root: {self.root}")
        lines.append(f"Src:  {self.src_dir}")
        lines.append(f"Scanned files: {self.scanned_files}")
        lines.append(f"Status: {'PASS' if self.ok else 'FAIL'}")

        if self.violations:
            lines.append("")
            lines.append("Violations:")
            for v in self.violations:
                location = []
                if v.file is not None:
                    location.append(str(v.file))
                if v.lineno is not None:
                    location.append(f"line {v.lineno}")
                loc = f" ({', '.join(location)})" if location else ""
                layer_info = ""
                if v.source_layer or v.target_layer:
                    layer_info = f" [from={v.source_layer!s}, to={v.target_layer!s}]"
                imp = f" import={v.import_name!r}" if v.import_name else ""
                lines.append(f"- [{v.code}]{layer_info}{loc}{imp}: {v.message}")

        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"- [{w.code}] {w.message}")

        if self.skipped:
            lines.append("")
            lines.append("Skipped:")
            for s in self.skipped:
                lines.append(f"- [{s.code}] {s.message}")

        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class ArchitectureConfig:
    """Configuration object controlling the engine rules."""

    root: Path
    src_dir: Path
    layers: dict[str, Path]
    allowed_dependencies: dict[str, frozenset[str]]
    forbidden_import_roots: dict[str, frozenset[str]]
    required_directories: tuple[Path, ...] = ()
    required_nonempty_directories: tuple[Path, ...] = ()
    port_contracts: tuple[PortContract, ...] = ()
    stdlib_only_layers: frozenset[str] = frozenset({"domain"})
    enforce_type_checking_skip: bool = True
    include_hidden_files: bool = False
    fail_on_missing_src_dir: bool = True

    def layer_for_path(self, file_path: Path) -> str | None:
        try:
            relative = file_path.resolve().relative_to(self.src_dir.resolve())
        except ValueError:
            return None
        if not relative.parts:
            return None
        head = relative.parts[0]
        return head if head in self.layers else None


def discover_repo_root(start: Path | None = None) -> Path:
    """Discover a repository root by walking up until pyproject.toml or .git is found."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            return candidate
    return current


def build_default_config(root: Path | None = None) -> ArchitectureConfig:
    """Create a ready-to-use configuration matching the supplied test suite conventions."""
    root_path = discover_repo_root(root)
    src_dir = root_path / "src"
    layers = {layer: src_dir / layer for layer in DEFAULT_LAYERS}

    return ArchitectureConfig(
        root=root_path,
        src_dir=src_dir,
        layers=layers,
        allowed_dependencies=DEFAULT_ALLOWED_DEPENDENCIES,
        forbidden_import_roots=DEFAULT_FORBIDDEN_IMPORTS,
        required_directories=tuple(root_path / p for p in DEFAULT_REQUIRED_DIRECTORIES),
        required_nonempty_directories=tuple(root_path / p for p in DEFAULT_REQUIRED_NONEMPTY_DIRECTORIES),
        port_contracts=DEFAULT_PORT_CONTRACTS,
    )


def _iter_python_files(directory: Path, *, include_hidden_files: bool = False) -> list[Path]:
    if not directory.exists():
        return []
    files = [p for p in directory.rglob("*.py") if p.name != "__init__.py"]
    if include_hidden_files:
        return sorted(files)
    return sorted(p for p in files if not any(part.startswith(".") for part in p.parts))


def _read_python_tree(file_path: Path) -> ast.AST:
    try:
        source = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Cannot decode {file_path} as UTF-8") from exc

    try:
        return ast.parse(source, filename=str(file_path))
    except SyntaxError as exc:
        raise SyntaxError(f"Syntax error in {file_path}: {exc}") from exc


def _collect_typing_aliases(tree: ast.AST) -> set[str]:
    """Collect names that may evaluate to typing.TYPE_CHECKING."""
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


def _is_type_checking_test(test: ast.AST, typing_aliases: set[str]) -> bool:
    """Return True if an if-test is a typing TYPE_CHECKING guard."""
    if isinstance(test, ast.Name):
        return test.id in typing_aliases

    if isinstance(test, ast.Attribute) and isinstance(test.value, ast.Name):
        return test.attr == "TYPE_CHECKING" and test.value.id in typing_aliases

    return False


def _range_contains(ranges: Sequence[tuple[int, int]], lineno: int) -> bool:
    return any(start <= lineno <= end for start, end in ranges)


def _type_checking_ranges(tree: ast.AST) -> list[tuple[int, int]]:
    """Collect line ranges covered by TYPE_CHECKING guards."""
    typing_aliases = _collect_typing_aliases(tree)
    ranges: list[tuple[int, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _is_type_checking_test(node.test, typing_aliases):
            end_lineno = getattr(node, "end_lineno", None) or node.lineno
            ranges.append((node.lineno, end_lineno))

    return ranges


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
    parts = module_name.split(".")
    if parts and parts[-1] == "__init__":
        return parts[:-1]
    return parts[:-1] if parts else []


def _resolve_relative_import(
    *,
    current_module: str,
    level: int,
    module: str | None,
) -> str | None:
    """
    Resolve a relative import to an absolute dotted module name.

    Example:
        current_module = "src.application.use_cases.foo"
        from ..domain import bar  -> "src.application.domain" is not valid semantically,
                                    but the resolver returns the syntactic target based on package scope.
    """
    package_parts = _module_package_parts(current_module)
    if level <= 0:
        return module

    # Python semantics: one leading dot means current package.
    base_len = max(0, len(package_parts) - (level - 1))
    base_parts = package_parts[:base_len]

    if module:
        module_parts = module.split(".")
        return ".".join([*base_parts, *module_parts]) if base_parts else module
    return ".".join(base_parts) if base_parts else module


def _root_import_name(import_name: str) -> str:
    """Return the top-level package / module segment."""
    return import_name.split(".", 1)[0]


def _normalized_project_import(import_name: str) -> str:
    """Normalize `src.foo.bar` to `foo.bar` for layer matching."""
    return import_name[4:] if import_name.startswith("src.") else import_name


def _layer_for_import(import_name: str, layers: Iterable[str]) -> str | None:
    """Determine whether an import name belongs to one of the architecture layers."""
    normalized = _normalized_project_import(import_name)
    for layer in layers:
        if normalized == layer or normalized.startswith(f"{layer}."):
            return layer
    return None


def _is_stdlib_import(import_name: str) -> bool:
    root = _root_import_name(_normalized_project_import(import_name))
    return root in STD_LIB_MODULES


def _is_forbidden_root(import_name: str, forbidden_roots: frozenset[str]) -> bool:
    normalized = _normalized_project_import(import_name)
    root = _root_import_name(normalized)
    return normalized in forbidden_roots or root in forbidden_roots


def _scan_file_imports(file_path: Path, config: ArchitectureConfig) -> list[ImportOccurrence]:
    """Extract all runtime import occurrences from a Python file."""
    tree = _read_python_tree(file_path)
    type_checking_ranges = _type_checking_ranges(tree)
    current_module = _current_module_name(file_path, config.src_dir) or file_path.stem

    imports: list[ImportOccurrence] = []

    for node in ast.walk(tree):
        if not hasattr(node, "lineno"):
            continue
        lineno = int(getattr(node, "lineno"))
        in_type_checking = _range_contains(type_checking_ranges, lineno) if config.enforce_type_checking_skip else False
        if in_type_checking:
            continue

        if isinstance(node, ast.Import):
            for alias in node.names:
                raw = alias.name
                resolved = raw
                source_layer = config.layer_for_path(file_path)
                target_layer = _layer_for_import(resolved, config.layers.keys())
                imports.append(
                    ImportOccurrence(
                        file=file_path,
                        lineno=lineno,
                        raw_import=raw,
                        resolved_import=resolved,
                        kind="import",
                        source_layer=source_layer,
                        target_layer=target_layer,
                        in_type_checking=False,
                    )
                )

        elif isinstance(node, ast.ImportFrom):
            module = node.module
            resolved_module: str | None
            if node.level and node.level > 0:
                resolved_module = _resolve_relative_import(
                    current_module=current_module,
                    level=node.level,
                    module=module,
                )
            else:
                resolved_module = module

            # One ImportFrom can bring multiple names from the same module.
            for alias in node.names:
                if resolved_module:
                    if alias.name == "*":
                        resolved = resolved_module
                    else:
                        resolved = f"{resolved_module}.{alias.name}"
                else:
                    resolved = alias.name

                source_layer = config.layer_for_path(file_path)
                target_layer = _layer_for_import(resolved_module or resolved, config.layers.keys())
                imports.append(
                    ImportOccurrence(
                        file=file_path,
                        lineno=lineno,
                        raw_import=resolved_module or alias.name,
                        resolved_import=resolved_module or alias.name,
                        kind="from",
                        source_layer=source_layer,
                        target_layer=target_layer,
                        in_type_checking=False,
                    )
                )

    return imports


def _gather_layer_files(config: ArchitectureConfig) -> dict[str, list[Path]]:
    return {
        layer: _iter_python_files(path, include_hidden_files=config.include_hidden_files)
        for layer, path in config.layers.items()
    }


def _check_required_paths(config: ArchitectureConfig, report: ArchitectureReport) -> None:
    for directory in config.required_directories:
        if not directory.exists():
            report.add_violation(
                "LAYOUT_MISSING_DIR",
                f"Required directory is missing: {directory}",
                file=directory,
            )

    for directory in config.required_nonempty_directories:
        if not directory.exists():
            report.add_violation(
                "LAYOUT_MISSING_NONEMPTY_DIR",
                f"Required non-empty directory is missing: {directory}",
                file=directory,
            )
            continue

        has_python = any(p.suffix == ".py" for p in directory.rglob("*.py"))
        if not has_python:
            report.add_violation(
                "LAYOUT_EMPTY_DIR",
                f"Required directory contains no Python files: {directory}",
                file=directory,
            )

    if config.fail_on_missing_src_dir and not config.src_dir.exists():
        report.add_violation(
            "LAYOUT_MISSING_SRC",
            f"Source directory is missing: {config.src_dir}",
            file=config.src_dir,
        )


def _check_layer_existence(config: ArchitectureConfig, report: ArchitectureReport) -> None:
    for layer, path in config.layers.items():
        if not path.exists():
            report.add_violation(
                "LAYER_MISSING",
                f"Layer '{layer}' directory must exist at {path}",
                file=path,
                source_layer=layer,
            )


def _check_dependency_direction(config: ArchitectureConfig, report: ArchitectureReport) -> None:
    for source_layer, source_path in config.layers.items():
        files = _iter_python_files(source_path, include_hidden_files=config.include_hidden_files)
        for file_path in files:
            try:
                imports = _scan_file_imports(file_path, config)
            except SyntaxError as exc:
                report.add_violation(
                    "SYNTAX_ERROR",
                    str(exc),
                    file=file_path,
                    source_layer=source_layer,
                )
                continue
            except ValueError as exc:
                report.add_violation(
                    "DECODE_ERROR",
                    str(exc),
                    file=file_path,
                    source_layer=source_layer,
                )
                continue

            for occurrence in imports:
                target_layer = occurrence.target_layer
                if target_layer is None:
                    continue

                allowed_targets = config.allowed_dependencies.get(source_layer, frozenset())
                if target_layer not in allowed_targets and target_layer != source_layer:
                    # same-layer imports are always allowed
                    report.add_violation(
                        "DEPENDENCY_DIRECTION",
                        f"Layer '{source_layer}' must not depend on outer layer '{target_layer}'.",
                        file=occurrence.file,
                        lineno=occurrence.lineno,
                        source_layer=source_layer,
                        target_layer=target_layer,
                        import_name=occurrence.resolved_import,
                    )


def _check_forbidden_import_roots(config: ArchitectureConfig, report: ArchitectureReport) -> None:
    for layer, forbidden_roots in config.forbidden_import_roots.items():
        source_path = config.layers.get(layer)
        if source_path is None or not source_path.exists():
            continue

        for file_path in _iter_python_files(source_path, include_hidden_files=config.include_hidden_files):
            try:
                imports = _scan_file_imports(file_path, config)
            except (SyntaxError, ValueError):
                continue

            for occurrence in imports:
                if occurrence.resolved_import is None:
                    continue

                if _is_forbidden_root(occurrence.resolved_import, forbidden_roots):
                    report.add_violation(
                        "FORBIDDEN_IMPORT",
                        f"Layer '{layer}' imports forbidden module '{occurrence.resolved_import}'.",
                        file=file_path,
                        lineno=occurrence.lineno,
                        source_layer=layer,
                        target_layer=occurrence.target_layer,
                        import_name=occurrence.resolved_import,
                    )


def _check_domain_zero_dependency(config: ArchitectureConfig, report: ArchitectureReport) -> None:
    domain_path = config.layers.get("domain")
    if domain_path is None or not domain_path.exists():
        return

    files = _iter_python_files(domain_path, include_hidden_files=config.include_hidden_files)
    for file_path in files:
        try:
            imports = _scan_file_imports(file_path, config)
        except (SyntaxError, ValueError) as exc:
            report.add_violation(
                "DOMAIN_SCAN_ERROR",
                str(exc),
                file=file_path,
                source_layer="domain",
            )
            continue

        for occurrence in imports:
            if occurrence.resolved_import is None:
                continue

            # Allow intra-domain imports and stdlib imports.
            if _layer_for_import(occurrence.resolved_import, ("domain",)) == "domain":
                continue
            if _is_stdlib_import(occurrence.resolved_import):
                continue

            report.add_violation(
                "DOMAIN_EXTERNAL_DEPENDENCY",
                f"Domain layer must depend only on stdlib and interal modules, but imports '{occurrence.resolved_import}'.",
                file=file_path,
                lineno=occurrence.lineno,
                source_layer="domain",
                target_layer=occurrence.target_layer,
                import_name=occurrence.resolved_import,
            )


def _import_object(module_name: str, symbol: str) -> Any:
    module = importlib.import_module(module_name)
    return getattr(module, symbol)


def _check_port_contracts(config: ArchitectureConfig, report: ArchitectureReport) -> None:
    for contract in config.port_contracts:
        try:
            obj = _import_object(contract.module, contract.symbol)
        except ModuleNotFoundError:
            report.add_skipped(
                "PORT_CONTRACT_SKIPPED",
                f"Optional port contract skipped because module is missing: {contract.module}.{contract.symbol}",
            )
            continue
        except AttributeError:
            report.add_violation(
                "PORT_CONTRACT_MISSING_SYMBOL",
                f"Port symbol not found: {contract.module}.{contract.symbol}",
            )
            continue
        except Exception as exc:  # pragma: no cover - defensive, but kept for production robustness
            report.add_violation(
                "PORT_CONTRACT_IMPORT_ERROR",
                f"Failed to import port contract {contract.module}.{contract.symbol}: {exc}",
            )
            continue

        missing = [method for method in contract.required_methods if not hasattr(obj, method)]
        if missing:
            report.add_violation(
                "PORT_CONTRACT_METHODS",
                f"{contract.symbol} is missing required methods: {', '.join(missing)}",
            )


class HexagonalArchitectureEngine:
    """Complete constraint engine for hexagonal architecture validation."""

    def __init__(self, config: ArchitectureConfig) -> None:
        self.config = config

    def scan(self) -> ArchitectureReport:
        report = ArchitectureReport(root=self.config.root, src_dir=self.config.src_dir)

        _check_required_paths(self.config, report)
        _check_layer_existence(self.config, report)
        _check_domain_zero_dependency(self.config, report)
        _check_dependency_direction(self.config, report)
        _check_forbidden_import_roots(self.config, report)
        _check_port_contracts(self.config, report)

        report.scanned_files = sum(len(files) for files in _gather_layer_files(self.config).values())
        return report

    def assert_clean(self) -> ArchitectureReport:
        report = self.scan()
        if not report.ok:
            raise AssertionError(report.format_text())
        return report


def assert_hexagonal_architecture(root: Path | str | None = None, *, strict: bool = True) -> ArchitectureReport:
    """Convenience helper for pytest / scripts.

    Args:
        root: repository root, or None to auto-discover.
        strict: when True, raises AssertionError on any violation.

    Returns:
        ArchitectureReport
    """
    root_path = Path(root).resolve() if root is not None else discover_repo_root()
    config = build_default_config(root_path)
    engine = HexagonalArchitectureEngine(config)
    report = engine.scan()
    if strict and not report.ok:
        raise AssertionError(report.format_text())
    return report


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate hexagonal architecture constraints in a Python codebase.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root. Defaults to auto-discovery.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Return exit code 0 even when violations are found.",
    )
    parser.add_argument(
        "--no-default-contracts",
        action="store_true",
        help="Disable built-in port interface contract checks.",
    )
    return parser


def _main(argv: Sequence[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    root = args.root or discover_repo_root()
    config = build_default_config(root)
    if args.no_default_contracts:
        config = dataclasses.replace(config, port_contracts=())

    report = HexagonalArchitectureEngine(config).scan()

    if args.json:
        print(report.to_json())
    else:
        print(report.format_text())

    if args.no_strict:
        return 0
    return 0 if report.ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
