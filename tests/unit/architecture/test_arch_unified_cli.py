"""Story 7-1 — 统一 CLI 架构约束验证测试（Task 8 SDD 验证面）。

非 TDD 单元测试——验证架构/约束是否被遵守（AC-1/AC-6）：
- P4 MCP=0 断言（无 src/infrastructure/mcp/ 目录、pyproject 无 mcp 依赖、
  src 全仓无 mcp import）
- 分层断言（src/interfaces/cli 零 composition_root/infrastructure import；
  typer 零入 src/domain/src/application——domain 零依赖全仓断言既有测试
  自然覆盖，此处加 CLI 面专项）
- 退出码契约矩阵与存量入口零回归（sisys-agent/sisys-ocr script 仍在+
  main_cli.main 契约）

断言形态：AST 解析（ast.walk 收集 ImportFrom/Import——test_analyst_view
先例形态）。

Run with:
    poetry run pytest tests/unit/architecture/test_arch_unified_cli.py -v
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
CLI_DIR = SRC_DIR / "interfaces" / "cli"


def _imports_of(path: Path) -> set[str]:
    """收集文件全部 import 目标（AST 解析——test_analyst_view.py:50-59 先例形态）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                targets.add(f"{module}.{alias.name}" if module != "" else alias.name)
            targets.add(module)
    return targets


# ===================================================================
# Subtask 8.2: P4 MCP=0 架构断言
# ===================================================================


class TestP4McpZero:
    """P4：MCP 退居生态层——MVP 阶段 MCP 相关代码量 = 0。"""

    def test_no_mcp_directory_in_infrastructure(self) -> None:
        """无 src/infrastructure/mcp/ 目录。"""
        assert not (SRC_DIR / "infrastructure" / "mcp").exists(), "MCP 目录不应存在（MVP P4）"

    def test_no_mcp_dependency_in_pyproject(self) -> None:
        """pyproject 无 mcp 依赖。"""
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        for line in pyproject.splitlines():
            normalized = line.strip().lower()
            if normalized.startswith(("mcp", '"mcp', "'mcp", "modelcontextprotocol")):
                pytest.fail(f"pyproject 含 MCP 依赖: {line.strip()}")

    def test_no_mcp_import_in_src(self) -> None:
        """src 全仓无 mcp import。"""
        for py_file in SRC_DIR.rglob("*.py"):
            for target in _imports_of(py_file):
                if "mcp" in target.lower().split("."):
                    pytest.fail(f"{py_file} 含 mcp import: {target}")


# ===================================================================
# Subtask 8.3: 分层断言
# ===================================================================


class TestLayeringConstraints:
    """六边形分层（interfaces 禁 composition_root/infrastructure；typer 不入 domain/application）。"""

    @pytest.mark.parametrize("py_file", sorted(CLI_DIR.rglob("*.py")))
    def test_cli_layer_no_composition_root_or_infrastructure(self, py_file: Path) -> None:
        """src/interfaces/cli 零 composition_root/infrastructure import（importlinter 传导禁令——.importlinter:72-78）。"""
        targets = _imports_of(py_file)
        for target in targets:
            assert not target.startswith("src.composition_root"), f"{py_file} 违约 import {target}"
            assert not target.startswith("src.infrastructure"), f"{py_file} 违约 import {target}"

    def test_cli_layer_no_entrypoints_import(self) -> None:
        """interfaces/cli 零 entrypoints import（组装层单向——入口装配 CLI 非反向）。"""
        for py_file in CLI_DIR.rglob("*.py"):
            for target in _imports_of(py_file):
                assert not target.startswith("src.entrypoints"), f"{py_file} 反向 import {target}"

    def test_typer_not_in_domain_or_application(self) -> None:
        """typer 依赖仅入 interfaces/entrypoints 层（architecture.md 钦定）。"""
        for layer in ("domain", "application"):
            for py_file in (SRC_DIR / layer).rglob("*.py"):
                targets = _imports_of(py_file)
                assert "typer" not in targets, f"{py_file}（{layer} 层）违规 import typer"

    def test_domain_cli_face_zero_external_dependency(self) -> None:
        """domain 零外部依赖 CLI 面专项（typer/dotenv/click 三件不入 domain——全仓断言的 CLI 增补面）。"""
        for py_file in (SRC_DIR / "domain").rglob("*.py"):
            targets = _imports_of(py_file)
            for forbidden in ("typer", "click", "dotenv"):
                assert forbidden not in targets, f"{py_file}（domain 层）违规 import {forbidden}"


# ===================================================================
# Subtask 8.4: 退出码契约矩阵与存量入口零回归
# ===================================================================


class TestExitCodeContractMatrix:
    """退出码契约（0/1/2）+ DomainError stderr 呈现 + 存量入口零回归。"""

    def test_main_cli_exit_code_mapping_exists(self) -> None:
        """main_cli 统一出口三映射（DomainError→stderr [code] message+1 / UsageError→2 / 成功→0）。"""
        import inspect

        from src.entrypoints import main_cli

        source = inspect.getsource(main_cli._map_exception_to_exit_code)
        assert "DomainError" in source
        assert "UsageError" in source
        assert "[{" in source, "DomainError stderr 呈现应为 [EXCEPTION_NNN] message 格式"

    def test_legacy_entry_scripts_preserved(self) -> None:
        """存量入口 script 仍在（sisys-agent/sisys-ocr——DC-3 冻结零回归）。"""
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert 'sisys-agent = "src.entrypoints.agent_cli:main"' in pyproject
        assert 'sisys-ocr = "src.entrypoints.ocr_cli:main"' in pyproject

    def test_unified_entry_script_registered(self) -> None:
        """统一入口 sisys script 注册于 [project.scripts]（AC-1）。"""
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert 'sisys = "src.entrypoints.main_cli:main"' in pyproject

    def test_legacy_cli_source_untouched(self) -> None:
        """存量 agent_cli/ocr_cli 源文件在位（冻结面——命令族迁移归 7-1-DF1）。"""
        assert (SRC_DIR / "entrypoints" / "agent_cli.py").is_file()
        assert (SRC_DIR / "entrypoints" / "ocr_cli.py").is_file()

    def test_legacy_cli_tests_exist(self) -> None:
        """存量 CLI 测试在位（4294 行基线——AC-1 零回归面）。"""
        tests_dir = ROOT / "tests" / "unit" / "interfaces" / "cli"
        assert (tests_dir / "test_agent_cli.py").is_file()
        assert (tests_dir / "test_ocr_cli.py").is_file()


# ===================================================================
# Subtask 8.5: 变异自证（对被测生产面突变注入验证测试红——R3-10 纯测试 Task 判别力）
# ===================================================================


class TestArchitectureAssertionDiscrimination:
    """架构断言判别力自证（对临时注入的违规 import 验证测试红）。"""

    def test_layering_assertion_catches_violation(self, tmp_path: Path) -> None:
        """分层断言对违规 import 文件红（AST 断言判别力——非恒真）。"""
        violating = tmp_path / "violating_module.py"
        violating.write_text("from src.composition_root import bootstrap\n", encoding="utf-8")
        targets = _imports_of(violating)
        assert any(target.startswith("src.composition_root") for target in targets), "AST 断言应捕获违规 import"
