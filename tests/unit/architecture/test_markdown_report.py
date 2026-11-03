"""Markdown 报告生成架构约束验证（Story 6-5a Task 6——SDD 规范验证测试）。

四验证器（test_checkpoint.py 形态模板——AST/import 扫描）：
A 领域层零第三方依赖（渲染器/VO/实体/异常四文件黑名单 + 白名单双向校验）
B 应用层零 infrastructure import（聚合服务/端口/用例——application-no-
  infrastructure importlinter 契约的文件级补充锚）
C 文件落位守护（本 Story 交付件在冻结路径清单内——防漂移落位）
D 端口经 resolver 解耦（CLI 不直依赖实现类——组装层仅 resolve 端口名）

Run with:
    poetry run pytest tests/unit/architecture/test_markdown_report.py -v
"""

import ast
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[3] / "src"

#: 领域层交付文件（渲染器/VO/实体/异常——零第三方依赖校验面）
REPORT_DOMAIN_FILES: tuple[Path, ...] = (
    SRC_ROOT / "domain" / "services" / "markdown_report_renderer.py",
    SRC_ROOT / "domain" / "value_objects" / "markdown_report.py",
    SRC_ROOT / "domain" / "entities" / "strategic_report.py",
    SRC_ROOT / "domain" / "exceptions" / "report_exceptions.py",
)

#: 应用层交付文件（零 infrastructure import 校验面）
REPORT_APPLICATION_FILES: tuple[Path, ...] = (
    SRC_ROOT / "application" / "services" / "report_generation_service.py",
    SRC_ROOT / "application" / "ports" / "report_generation.py",
    SRC_ROOT / "application" / "use_cases" / "generate_markdown_report.py",
)

#: 禁 import 黑名单（domain 零依赖——importlinter 同源清单）
FORBIDDEN_IMPORTS: frozenset[str] = frozenset(
    {
        "pydantic",
        "sqlalchemy",
        "redis",
        "fastapi",
        "typer",
        "langgraph",
        "prefect",
        "qdrant_client",
        "minio",
        "neo4j",
        "aio_pika",
        "litellm",
        "instructor",
        "asyncpg",
        "httpx",
        "yaml",
        "dotenv",
        "alembic",
    }
)

#: domain 允许顶层（标准库 + src.domain）
_DOMAIN_ALLOWED_TOP_LEVELS: frozenset[str] = frozenset({"src", "__future__"} | set(sys.stdlib_module_names))

#: 本 Story src 交付件冻结路径清单（落位守护——增文件须同步本清单）
REPORT_STORY_FILES: frozenset[str] = frozenset(
    {
        "src/domain/entities/strategic_report.py",
        "src/domain/value_objects/markdown_report.py",
        "src/domain/services/markdown_report_renderer.py",
        "src/domain/exceptions/report_exceptions.py",
        "src/domain/ports/report_repository.py",
        "src/application/ports/report_generation.py",
        "src/application/services/report_generation_service.py",
        "src/application/use_cases/generate_markdown_report.py",
        "src/infrastructure/storage/postgresql/models/report.py",
        "src/infrastructure/storage/postgresql/repository/report_repository.py",
        "deploy/postgresql/alembic/versions/017_strategic_reports.py",
    }
)


def _extract_imports(file_path: Path) -> list[str]:
    """AST 提取模块级与函数级 import 目标（test_checkpoint.py 同款形态）。

    Args:
        file_path: 源文件路径。

    Returns:
        import 目标模块名列表。
    """
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            targets.append(node.module)
    return targets


class TestDomainZeroDependencies:
    """A 领域层零第三方依赖（渲染器/VO/实体/异常四文件）。"""

    def test_report_domain_files_exist(self) -> None:
        """四领域交付文件存在（前置——缺文件即架构面失败）。"""
        for file_path in REPORT_DOMAIN_FILES:
            assert file_path.exists(), f"领域交付文件缺失: {file_path}"

    def test_report_domain_no_forbidden_imports(self) -> None:
        """四文件零第三方 import（黑名单命中即违规）。"""
        for file_path in REPORT_DOMAIN_FILES:
            imports = _extract_imports(file_path)
            violated = [
                target
                for target in imports
                for banned in FORBIDDEN_IMPORTS
                if target == banned or target.startswith(f"{banned}.")
            ]
            assert not violated, f"{file_path.name} 含禁 import: {violated}"

    def test_report_domain_imports_within_allowlist(self) -> None:
        """四文件 import 全在允许域（标准库 + src.domain——白名单双向校验）。"""
        for file_path in REPORT_DOMAIN_FILES:
            for target in _extract_imports(file_path):
                top = target.split(".")[0]
                assert top in _DOMAIN_ALLOWED_TOP_LEVELS, f"{file_path.name} 非白名单 import: {target}"
                if top == "src":
                    assert target.startswith("src.domain"), f"{file_path.name} domain 越层 import: {target}"


class TestApplicationLayerIsolation:
    """B 应用层零 infrastructure import（聚合服务/端口/用例）。"""

    def test_report_application_no_infrastructure_imports(self) -> None:
        """三应用层文件零 src.infrastructure import（importlinter 契约文件级锚）。"""
        for file_path in REPORT_APPLICATION_FILES:
            imports = _extract_imports(file_path)
            violated = [target for target in imports if target.startswith("src.infrastructure")]
            assert not violated, f"{file_path.name} 应用层直依赖 infrastructure: {violated}"

    def test_report_application_no_local_protocol_definitions(self) -> None:
        """服务文件禁本地 Protocol 定义（端口定义单源在 ports/——契约纪律）。"""
        service_file = SRC_ROOT / "application" / "services" / "report_generation_service.py"
        tree = ast.parse(service_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "Protocol":
                        raise AssertionError(f"服务文件本地 Protocol 定义违规: {node.name}")


class TestFilePlacement:
    """C 文件落位守护（交付件在冻结路径清单内）。"""

    def test_report_story_files_all_exist(self) -> None:
        """冻结清单 11 文件全部存在（落位+存在双守护）。"""
        for relative in REPORT_STORY_FILES:
            assert (SRC_ROOT.parent / relative).exists(), f"交付件缺失或落位漂移: {relative}"

    def test_no_stray_report_files_outside_frozen_paths(self) -> None:
        """仓内 report 主题文件不散落冻结清单外（防漂移新增——仅 .py 源文件）。"""
        known_report_paths: set[Path] = {SRC_ROOT.parent / relative for relative in REPORT_STORY_FILES}
        patterns = (
            "**/strategic_report*.py",
            "**/markdown_report*.py",
            "**/report_generation*.py",
            "**/*report_repository*.py",
        )
        for pattern in patterns:
            for found in SRC_ROOT.rglob(pattern):
                if found in known_report_paths or found.name == "__init__.py" or "__pycache__" in found.parts:
                    continue
                relative = found.relative_to(SRC_ROOT.parent)
                assert str(relative) in REPORT_STORY_FILES, f"冻结清单外 report 文件: {relative}"


class TestPortResolverDecoupling:
    """D 端口经 resolver 解耦（CLI 组装层不直依赖实现类）。"""

    def test_cli_resolves_port_not_implementation(self) -> None:
        """agent_cli report-generate 经 resolve("report_generation_use_case")——零实现类 import。"""
        cli_source = (SRC_ROOT / "entrypoints" / "agent_cli.py").read_text(encoding="utf-8")
        assert 'resolve("report_generation_use_case")' in cli_source
        for implementation in ("PostgreSQLReportRepository", "ReportGenerationService("):
            assert implementation not in cli_source, f"CLI 直依赖实现类: {implementation}"

    def test_service_consumes_ports_only(self) -> None:
        """聚合服务依赖面全端口（五依赖 Protocol/Port 类型——零实现类 import）。"""
        service_file = REPORT_APPLICATION_FILES[0]
        imports = _extract_imports(service_file)
        for target in imports:
            if target.startswith("src.infrastructure"):
                raise AssertionError(f"聚合服务依赖实现类: {target}")
