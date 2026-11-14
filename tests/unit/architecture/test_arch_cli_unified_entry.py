"""SDD 架构约束验证测试（Story 7-1 Task 6——AC-4 七原则 + AC-5 架构面）。

验证器族：
    - 六模块挂载完整性（13+1 命令注册断言——帮助文本漂移锁 agent_cli 同款先例）
    - 七原则断言族：P1 挂载/P4 MCP=0/P5 SkillSelector 形态不变/P7 input_examples 23/23
    - import 方向（interfaces/cli AST 断言禁 import infrastructure/entrypoints/
      composition_root——OD-16 传导链守卫；dispatch 层 json/table 态零
      ``_print_*`` 调用 AST 断言——OD-14 机制升架构位）
    - console_script 双段一致（sisys 条目收窄断言）+ 消费端口对账表 grep 断言
    - 12 个既有 agent_cli 架构测试锚点零漂移（Subtask 6.6——全量回归承载）
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

from src.entrypoints import cli_main

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"
CLI_DIR = SRC_DIR / "interfaces" / "cli"

_SIX_MODULES: tuple[str, ...] = ("document", "tool", "agent", "plan", "checkpoint", "archive")

_THIRTEEN_PLUS_ONE: dict[str, list[str]] = {
    "document": ["upload", "search"],
    "tool": ["list", "run"],
    "agent": ["instantiate", "run-task"],
    "plan": ["generate", "report", "trace-tree"],
    "checkpoint": ["list", "recover"],
    "archive": ["query"],
}

# 消费端口对账表（Task 0.1 冻结表同源——组合根注册名在册断言）
_CONSUMED_PORTS: tuple[str, ...] = (
    "document_upload_service",
    "hybrid_search_service",
    "document_version_service",
    "tool_execution_service",
    "agent_instantiation_use_case",
    "agent_workflow_use_case",
    "blm_planning_use_case",
    "report_generation_use_case",
    "pdf_report_generation_use_case",
    "traceability_tree_use_case",
    "checkpoint_list_use_case",
    "checkpoint_recovery_use_case",
    "checkpoint_recovery_execute_use_case",
    "strategic_archive_service",
    "session_factory",
)


class TestSixModuleMounting:
    """验证器 1：六模块挂载完整性（P1——帮助文本漂移锁）。"""

    def test_six_modules_mounted_on_assembled_app(self) -> None:
        """六模块全部挂载（组装后 app——OD-16 断言对象钦定）。"""
        app = cli_main.get_app()
        mounted = {group.name for group in app.registered_groups}
        for module in _SIX_MODULES:
            assert module in mounted, f"模块 {module} 未挂载: {sorted(str(name) for name in mounted)}"

    @pytest.mark.parametrize(("module", "commands"), sorted(_THIRTEEN_PLUS_ONE.items()))
    def test_thirteen_commands_registered(self, module: str, commands: list[str]) -> None:
        """13 命令注册完整性（Task 0.1 冻结表——漂移即红）。"""
        app = cli_main.get_app()
        groups = {group.name: group for group in app.registered_groups}
        sub_app = groups[module].typer_instance
        assert sub_app is not None, f"{module} 子 app 未实例化"
        registered = {cmd.name for cmd in sub_app.registered_commands}
        for command in commands:
            assert command in registered, f"{module} 缺命令 {command}（实际: {sorted(str(name) for name in registered)}）"

    def test_help_text_drift_lock(self) -> None:
        """帮助文本漂移锁（agent_cli test_help_text 同款——装配面两文件齐现）。"""
        cli_main_source = (SRC_DIR / "entrypoints" / "cli_main.py").read_text(encoding="utf-8")
        interfaces_main_source = (CLI_DIR / "main.py").read_text(encoding="utf-8")
        # entrypoints 侧三组（cli_main 程序化注册）
        for module in ("agent", "plan", "checkpoint"):
            assert f'name="{module}"' in cli_main_source, f"cli_main 装配面漂移（{module} 注册缺失）"
        # interfaces 侧三模块（main.py add_typer）
        for module in ("document", "tool", "archive"):
            assert f'name="{module}"' in interfaces_main_source, f"interfaces main 装配面漂移（{module} 挂载缺失）"


class TestSevenPrinciples:
    """验证器 2：七原则断言族（AC-4——P4/P5/P7 源码级，P1 归验证器 1）。"""

    def test_p4_no_mcp_directory_or_dependency(self) -> None:
        """P4：MCP 代码量为零（无 src/**/mcp 目录+无 mcp 依赖）。"""
        mcp_dirs = [p for p in SRC_DIR.rglob("*") if p.is_dir() and p.name == "mcp"]
        assert not mcp_dirs, f"MCP 目录存在: {mcp_dirs}"
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        dep_lines = [line for line in pyproject.splitlines() if "mcp" in line.lower() and "=" in line]
        assert not dep_lines, f"MCP 依赖声明存在: {dep_lines}"

    def test_p5_skill_selector_form_unchanged(self) -> None:
        """P5：SkillSelector 形态不变（ACTIVE 过滤+description 触发——零排序零打分零 Top-K）。"""
        selector = SRC_DIR / "application" / "skills" / "registry" / "selector.py"
        source = selector.read_text(encoding="utf-8")
        for banned in ("sorted(", ".sort(", "top_k", "topk", "TopK", "score(", "rank("):
            assert banned not in source, f"SkillSelector 出现禁用形态 {banned!r}（P5 违规）"
        assert "active" in source.lower(), "ACTIVE 过滤形态缺失"

    def test_p7_input_examples_full_coverage(self) -> None:
        """P7：input_examples 存在性清单断言（23/23 SKILL.md `## 8.` 章节各 ≥1）。"""
        skills_dir = SRC_DIR / "application" / "skills"
        skill_docs = sorted(skills_dir.glob("*/SKILL.md"))
        assert len(skill_docs) == 23, f"SKILL.md 数量漂移: {len(skill_docs)}（预期 23）"
        missing = [
            str(p.relative_to(REPO_ROOT)) for p in skill_docs if "## 8. input_examples" not in p.read_text(encoding="utf-8")
        ]
        assert not missing, f"缺 input_examples 章节: {missing}"


class TestImportDirection:
    """验证器 3：import 方向（OD-16 传导链守卫 + OD-14 dispatch 机制位）。"""

    @pytest.mark.parametrize("py_file", sorted(CLI_DIR.rglob("*.py")), ids=lambda p: p.name)
    def test_interfaces_cli_forbidden_imports(self, py_file: Path) -> None:
        """interfaces/cli 文件禁 import infrastructure/entrypoints/composition_root（OD-16）。"""
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                targets.append(node.module)
            for target in targets:
                assert not target.startswith("src.infrastructure"), f"{py_file.name} 违规 import {target}"
                assert not target.startswith("src.entrypoints"), f"{py_file.name} 违规 import {target}"
                assert not target.startswith("src.composition_root"), f"{py_file.name} 违规 import {target}"

    def test_dispatch_json_table_no_print_calls(self) -> None:
        """OD-14 机制升架构位：dispatch 层 json/table 渲染路径零 ``_print_*`` 调用。

        stdout 纯净机制（json/table 渲染源=controller result——AST 断言禁
        ``_print_`` 前缀函数调用，cli_commands.py 整合命令面同守）。
        """
        for source_path in (
            CLI_DIR / "dispatch.py",
            SRC_DIR / "entrypoints" / "cli_commands.py",
        ):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    assert not node.func.id.startswith("_print_"), (
                        f"{source_path.name} 调用 _print_* 系（OD-14 违规——json/table 禁经人类可读渲染）"
                    )

    def test_typer_form_in_entrypoints(self) -> None:
        """Typer 形态断言（cli_main/cli_commands app 构造+Option 使用在位）。"""
        cli_main_source = (SRC_DIR / "entrypoints" / "cli_main.py").read_text(encoding="utf-8")
        assert "typer.Typer" in cli_main_source or "add_typer" in cli_main_source, "cli_main 缺 Typer 装配形态"
        commands_source = (SRC_DIR / "entrypoints" / "cli_commands.py").read_text(encoding="utf-8")
        assert commands_source.count("@") >= 7, "cli_commands 缺命令装饰器形态（7 命令）"

    def test_agent_cli_controller_resident(self) -> None:
        """controller 留驻 agent_cli（202 单测 patch 面前提——源码锚）。"""
        agent_cli_source = (SRC_DIR / "entrypoints" / "agent_cli.py").read_text(encoding="utf-8")
        for controller_name in (
            "_task_controller",
            "_blm_plan_controller",
            "_report_generate_controller",
            "_trace_tree_controller",
            "_checkpoint_list_controller",
            "_checkpoint_recover_controller",
            "_instantiate_controller",
        ):
            assert f"def {controller_name}" in agent_cli_source, (
                f"controller {controller_name} 未留驻 agent_cli（patch 面破坏）"
            )


class TestConsoleScriptAndPorts:
    """验证器 4：console_script 双段一致 + 消费端口对账（链路接线断言清单②）。"""

    def test_console_script_sisys_both_sections(self) -> None:
        """sisys 条目双段一致（断言收窄——现状两段不对称 crawler 仅 [project.scripts]）。"""
        data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project_scripts = data.get("project", {}).get("scripts", {})
        poetry_scripts = data.get("tool", {}).get("poetry", {}).get("scripts", {})
        assert "sisys" in project_scripts, "[project.scripts] 缺 sisys"
        assert "sisys" in poetry_scripts, "[tool.poetry.scripts] 缺 sisys"
        assert project_scripts["sisys"] == poetry_scripts["sisys"] == "src.entrypoints.cli_main:main"

    def test_consumed_ports_registered_in_composition_root(self) -> None:
        """13 命令消费端口全部组合根在册（对账表逐条——注册名漂移即红）。"""
        composition = (SRC_DIR / "composition_root.py").read_text(encoding="utf-8")
        for port_name in _CONSUMED_PORTS:
            assert f'name="{port_name}"' in composition, f"消费端口 {port_name} 未在组合根注册（对账失败）"

    def test_session_factory_wiring_guard(self) -> None:
        """6.4-DF2 接线守卫：archive_repository 注册 lambda 注入 session_factory。"""
        composition = (SRC_DIR / "composition_root.py").read_text(encoding="utf-8")
        assert 'name="archive_repository"' in composition
        archive_block_start = composition.index('name="archive_repository"')
        block = composition[archive_block_start : archive_block_start + 400]
        assert "session_factory" in block, "archive_repository 注册缺 session_factory 注入（6.4-DF2 守卫）"
