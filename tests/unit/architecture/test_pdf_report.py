"""PDF 报告生成架构约束验证（Story 6-5b Task 7——SDD 规范验证测试）。

四验证器（test_markdown_report.py 形态模板——AST/import 扫描）：
A 领域层零第三方依赖（引文 VO/异常扩展文件白名单双向校验）
B 应用层零 infrastructure import（PDF 服务/端口/用例 + 禁本地 Protocol）
C reportlab 唯一宿主（全 src/ AST 扫描 import reportlab 仅命中渲染器——
  本 Story 特有验证器，OD-5「渲染技术是基础设施」的守护面）
D 落位守护（本 Story 交付件冻结路径清单 + rglob 防散落 + CLI resolve 端口名）

Run with:
    poetry run pytest tests/unit/architecture/test_pdf_report.py -v
"""

import ast
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[3] / "src"

#: 领域层交付文件（引文 VO + 异常扩展——零第三方依赖校验面）
PDF_DOMAIN_FILES: tuple[Path, ...] = (
    SRC_ROOT / "domain" / "value_objects" / "citation_entry.py",
    SRC_ROOT / "domain" / "exceptions" / "report_exceptions.py",
)

#: 应用层交付文件（零 infrastructure import 校验面）
PDF_APPLICATION_FILES: tuple[Path, ...] = (
    SRC_ROOT / "application" / "services" / "pdf_report_generation_service.py",
    SRC_ROOT / "application" / "ports" / "pdf_report.py",
    SRC_ROOT / "application" / "use_cases" / "generate_pdf_report.py",
)

#: 禁 import 黑名单（domain 零依赖——importlinter 同源清单 + reportlab）
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
        "reportlab",  # 6-5b 新增面（OD-5：渲染技术禁入 domain）
        "pypdf",
        "pypdfium2",
    }
)

#: domain 允许顶层（标准库 + src.domain）
_DOMAIN_ALLOWED_TOP_LEVELS: frozenset[str] = frozenset({"src", "__future__"} | set(sys.stdlib_module_names))

#: 本 Story src 交付件冻结路径清单（落位守护——增文件须同步本清单）
PDF_STORY_FILES: frozenset[str] = frozenset(
    {
        "src/domain/value_objects/citation_entry.py",
        "src/domain/exceptions/report_exceptions.py",
        "src/application/ports/pdf_report.py",
        "src/application/services/pdf_report_generation_service.py",
        "src/application/use_cases/generate_pdf_report.py",
        "src/infrastructure/reporting/__init__.py",
        "src/infrastructure/reporting/reportlab_pdf_renderer.py",
    }
)

#: reportlab 唯一宿主文件（OD-5——架构测试 C 验证器锚）
_RENDERER_FILE = "src/infrastructure/reporting/reportlab_pdf_renderer.py"


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
    """A 领域层零第三方依赖（引文 VO/异常扩展）。"""

    def test_pdf_domain_files_exist(self) -> None:
        """领域交付文件存在（前置——缺文件即架构面失败）。"""
        for file_path in PDF_DOMAIN_FILES:
            assert file_path.exists(), f"领域交付文件缺失: {file_path}"

    def test_pdf_domain_no_forbidden_imports(self) -> None:
        """文件零第三方 import（黑名单命中即违规——reportlab/pypdf/pypdfium2 禁入 domain）。"""
        for file_path in PDF_DOMAIN_FILES:
            imports = _extract_imports(file_path)
            violated = [
                target
                for target in imports
                for banned in FORBIDDEN_IMPORTS
                if target == banned or target.startswith(f"{banned}.")
            ]
            assert not violated, f"{file_path.name} 含禁 import: {violated}"

    def test_pdf_domain_imports_within_allowlist(self) -> None:
        """import 全在允许域（标准库 + src.domain——白名单双向校验）。"""
        for file_path in PDF_DOMAIN_FILES:
            for target in _extract_imports(file_path):
                top = target.split(".")[0]
                assert top in _DOMAIN_ALLOWED_TOP_LEVELS, f"{file_path.name} 非白名单 import: {target}"
                if top == "src":
                    assert target.startswith("src.domain"), f"{file_path.name} domain 越层 import: {target}"


class TestApplicationLayerIsolation:
    """B 应用层零 infrastructure import（PDF 服务/端口/用例）。"""

    def test_pdf_application_no_infrastructure_imports(self) -> None:
        """三应用层文件零 src.infrastructure import（importlinter 契约文件级锚）。"""
        for file_path in PDF_APPLICATION_FILES:
            imports = _extract_imports(file_path)
            violated = [target for target in imports if target.startswith("src.infrastructure")]
            assert not violated, f"{file_path.name} 应用层直依赖 infrastructure: {violated}"

    def test_pdf_application_no_local_protocol_definitions(self) -> None:
        """服务文件禁本地 Protocol 定义（端口定义单源在 ports/——契约纪律）。"""
        service_file = SRC_ROOT / "application" / "services" / "pdf_report_generation_service.py"
        tree = ast.parse(service_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "Protocol":
                        raise AssertionError(f"服务文件本地 Protocol 定义违规: {node.name}")


class TestReportlabUniqueHost:
    """C reportlab 唯一宿主（全 src/ AST 扫描——OD-5 守护面）。"""

    def test_reportlab_imports_only_in_renderer(self) -> None:
        """全 src/ import reportlab 仅命中 reportlab_pdf_renderer.py（唯一宿主）。"""
        violators: list[str] = []
        for path in sorted(SRC_ROOT.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            relative = str(path.relative_to(SRC_ROOT.parent))
            if relative == _RENDERER_FILE:
                continue
            for target in _extract_imports(path):
                if target == "reportlab" or target.startswith("reportlab."):
                    violators.append(f"{relative}: {target}")
        assert not violators, f"reportlab 唯一宿主违例（{relative if violators else ''}）: {violators}"

    def test_renderer_file_exists_and_imports_reportlab(self) -> None:
        """渲染器文件存在且 import reportlab（正向存在性——宿主在位）。"""
        renderer = SRC_ROOT.parent / _RENDERER_FILE
        assert renderer.exists()
        imports = _extract_imports(renderer)
        assert any(target.startswith("reportlab") for target in imports), "渲染器未 import reportlab（宿主失位）"


class TestFilePlacement:
    """D 落位守护（交付件在冻结路径清单内）。"""

    def test_pdf_story_files_all_exist(self) -> None:
        """冻结清单文件全部存在（落位+存在双守护）。"""
        for relative in PDF_STORY_FILES:
            assert (SRC_ROOT.parent / relative).exists(), f"交付件缺失或落位漂移: {relative}"

    def test_no_stray_pdf_files_outside_frozen_paths(self) -> None:
        """仓内 PDF 报告主题文件不散落冻结清单外（防漂移新增——仅 .py 源文件）。"""
        known_paths: set[Path] = {SRC_ROOT.parent / relative for relative in PDF_STORY_FILES}
        patterns = (
            "**/citation_entry*.py",
            "**/pdf_report*.py",
            "**/reportlab_pdf_renderer*.py",
            "**/reporting/*.py",
        )
        for pattern in patterns:
            for found in SRC_ROOT.rglob(pattern):
                if found in known_paths or found.name == "__init__.py" or "__pycache__" in found.parts:
                    continue
                relative = found.relative_to(SRC_ROOT.parent)
                assert str(relative) in PDF_STORY_FILES, f"冻结清单外 PDF 报告文件: {relative}"

    def test_cli_resolves_pdf_port_not_implementation(self) -> None:
        """agent_cli 经 resolve("pdf_report_generation_use_case")——零实现类 import。"""
        cli_source = (SRC_ROOT / "entrypoints" / "agent_cli.py").read_text(encoding="utf-8")
        assert 'resolve("pdf_report_generation_use_case")' in cli_source
        for implementation in ("ReportLabPdfRenderer", "PdfReportGenerationService("):
            assert implementation not in cli_source, f"CLI 直依赖实现类: {implementation}"
