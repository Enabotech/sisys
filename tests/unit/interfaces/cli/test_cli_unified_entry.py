"""统一 CLI 入口骨架单测（Task 1 循环 A——AC-1 装配面）。

断言对象钦定=cli_main 组装后的完整 app（OD-16：interfaces 裸 app 仅三模块，
六模块断言必须锚组装后 app——cli_main.get_app() 暴露模块级 importable 装配函数）。

覆盖面：
    - get_app 存在性与 Typer 类型
    - 六模块挂载（document/tool/agent/plan/checkpoint/archive）
    - --help 帮助文本六模块可见（Typer CliRunner）
    - main(argv) 返回 int 契约（0=成功/2=用法错误——argparse 前端同契约）
    - console_script 双段注册（pyproject [project.scripts]+[tool.poetry.scripts]
      sisys 条目一致——断言收窄为 sisys 条目，现状两段不对称 crawler 仅前者）
    - python -m 形态守卫（if __name__ == "__main__"）
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from src.entrypoints import cli_main

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

runner = CliRunner()

_SIX_MODULES: tuple[str, ...] = ("document", "tool", "agent", "plan", "checkpoint", "archive")


class TestGetApp:
    """组装函数契约。"""

    def test_get_app_exists_and_returns_typer(self) -> None:
        """get_app 装配函数存在且返回 Typer 实例（模块级 importable——断言对象钦定）。"""
        app = cli_main.get_app()
        assert isinstance(app, typer.Typer), f"get_app 应返回 Typer 实例: {type(app)}"

    def test_six_modules_mounted_on_assembled_app(self) -> None:
        """六模块全部挂载在组装后 app（OD-16——裸 app 仅三模块，组装后六模块）。"""
        app = cli_main.get_app()
        mounted = {group.name for group in app.registered_groups}
        for module in _SIX_MODULES:
            assert module in mounted, f"模块 {module} 未挂载（实际: {sorted(str(name) for name in mounted)}）"


class TestHelpText:
    """帮助文本骨架。"""

    def test_cli_help_lists_six_modules(self) -> None:
        """sisys --help 六模块全部可见。"""
        result = runner.invoke(cli_main.get_app(), ["--help"])
        assert result.exit_code == 0, f"help 退出码 {result.exit_code}: {result.output}"
        for module in _SIX_MODULES:
            assert module in result.output, f"帮助文本缺模块 {module}: {result.output}"

    def test_document_module_help_reachable(self) -> None:
        """document 模块帮助可达（三级结构第一跳）。"""
        result = runner.invoke(cli_main.get_app(), ["document", "--help"])
        assert result.exit_code == 0, f"document --help 退出码 {result.exit_code}"


class TestMainContract:
    """main(argv) 返回 int 契约（与 agent_cli.main 同契约——测试直调面）。"""

    def test_main_returns_int_for_help(self) -> None:
        """--help 返回 0。"""
        assert cli_main.main(["--help"]) == 0

    def test_main_returns_two_for_unknown_command(self) -> None:
        """未知命令返回 2（用法错误——argparse 同契约）。"""
        assert cli_main.main(["no-such-command"]) == 2

    def test_main_returns_two_for_empty_argv(self) -> None:
        """空 argv 返回 2（缺子命令——required True 形态）。"""
        assert cli_main.main([]) == 2


class TestConsoleScript:
    """console_script 双段注册（AC-1 验证标准①——sisys 条目双段一致）。"""

    def test_sisys_entry_in_both_script_sections(self) -> None:
        """pyproject 两段 scripts 均含 sisys 条目且值一致。"""
        import tomllib

        data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
        project_scripts = data.get("project", {}).get("scripts", {})
        poetry_scripts = data.get("tool", {}).get("poetry", {}).get("scripts", {})
        assert "sisys" in project_scripts, f"[project.scripts] 缺 sisys: {project_scripts}"
        assert "sisys" in poetry_scripts, f"[tool.poetry.scripts] 缺 sisys: {poetry_scripts}"
        assert project_scripts["sisys"] == poetry_scripts["sisys"], "两段 sisys 条目值不一致"
        assert project_scripts["sisys"] == "src.entrypoints.cli_main:main"

    def test_cli_main_has_dunder_main_guard(self) -> None:
        """cli_main.py 含 if __name__ == \"__main__\" 守卫（python -m 形态支持——AC-6①）。"""
        source = Path(cli_main.__file__).read_text(encoding="utf-8")
        assert "__main__" in source, "cli_main.py 缺 __main__ 守卫（python -m 形态不可用）"


class TestLayering:
    """分层落位（OD-16——interfaces 侧三模块/entrypoints 侧三组）。"""

    def test_interfaces_main_app_mounts_three_modules(self) -> None:
        """interfaces/cli/main.py 裸 app 仅三模块（document/tool/archive）。"""
        from src.interfaces.cli.main import app as interfaces_app

        mounted = {group.name for group in interfaces_app.registered_groups}
        assert {"document", "tool", "archive"} <= mounted, f"interfaces app 缺三模块: {sorted(str(name) for name in mounted)}"

    def test_cli_commands_module_has_three_groups(self) -> None:
        """cli_commands.py 三组子 app（agent/plan/checkpoint——Task 2 填命令）。"""
        from src.entrypoints import cli_commands

        for group_name in ("agent_app", "plan_app", "checkpoint_app"):
            group = getattr(cli_commands, group_name, None)
            assert isinstance(group, typer.Typer), f"cli_commands.{group_name} 缺失或非 Typer"

    def test_interfaces_app_no_entrypoints_import(self) -> None:
        """interfaces/cli 包禁 import entrypoints（OD-16 传导链守卫——单测轻量版）。"""
        import ast

        for py_file in (Path(__file__).resolve().parents[3] / "src" / "interfaces" / "cli").rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                targets: list[str] = []
                if isinstance(node, ast.Import):
                    targets.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    targets.append(node.module)
                for target in targets:
                    assert not target.startswith("src.entrypoints"), f"{py_file.name} 违规 import {target}"
                    assert not target.startswith("src.composition_root"), f"{py_file.name} 违规 import {target}"


@pytest.mark.parametrize("module", _SIX_MODULES)
def test_each_module_group_has_sub_app(module: str) -> None:
    """六模块各组子 app 实例在位（骨架时点可空组——命令挂载断言归 Task 2 循环 C/Task 3）。"""
    app = cli_main.get_app()
    groups = {group.name: group for group in app.registered_groups}
    assert module in groups, f"模块 {module} 未挂载"
    assert groups[module].typer_instance is not None, f"{module} 组缺 Typer 实例"


# ===================================================================
# Task 3 DoD：三参数无豁免矩阵复验（13+1 命令 × 三参数全可解析——R2-03 承接位）
# ===================================================================

_FULL_COMMAND_ARGS: dict[tuple[str, ...], list[str]] = {
    ("document", "upload"): [
        "--file",
        "/dev/null",
        "--business-domain",
        "t",
        "--source",
        "s",
        "--license",
        "l",
        "--uploaded-by",
        "u",
    ],
    ("document", "search"): ["--query", "q"],
    ("document", "version", "list"): ["--id", "11111111-1111-1111-1111-111111111111"],
    ("document", "version", "snapshot"): [
        "--id",
        "11111111-1111-1111-1111-111111111111",
        "--description",
        "矩阵",
    ],
    ("tool", "list"): [],
    ("tool", "run"): [
        "--tool-id",
        "11111111-1111-1111-1111-111111111111",
        "--input",
        "{}",
        "--tenant-id",
        "11111111-1111-1111-1111-111111111111",
    ],
    ("agent", "instantiate"): ["--role", "ceo"],
    ("agent", "run-task"): ["--agent-id", "11111111-1111-1111-1111-111111111111", "--task", "t"],
    ("plan", "generate"): ["--agent-id", "11111111-1111-1111-1111-111111111111", "--task", "t"],
    ("plan", "report"): ["--plan-id", "11111111-1111-1111-1111-111111111111"],
    ("plan", "trace-tree"): ["--plan-id", "11111111-1111-1111-1111-111111111111"],
    ("checkpoint", "list"): ["--plan-id", "11111111-1111-1111-1111-111111111111"],
    ("checkpoint", "recover"): ["--plan-id", "11111111-1111-1111-1111-111111111111", "--checkpoint-no", "1"],
    ("archive", "query"): [],
}


@pytest.mark.parametrize(("command_path", "base_args"), sorted(_FULL_COMMAND_ARGS.items()))
@pytest.mark.parametrize("agent_flag", ["--yes", "--dry-run", "--mock"])
def test_agent_params_parseable_on_all_commands(
    command_path: tuple[str, ...],
    base_args: list[str],
    agent_flag: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """三参数无豁免矩阵：13+1 命令 × --yes/--dry-run/--mock 全可解析（非 exit 2）。

    dry-run/mock 零 resolve（守卫通过即 exit 0）；--yes 幂等接受（命令真实
    执行形态因参数合法性而异——本断言只锁「参数面可解析」无 exit 2）。
    R1-T6：显式 delenv SISYS_TENANT_ID——shell export 该键时 document upload
    --yes 腿会真实写入 PG/MinIO（非确定性副作用——环境偶然前提加固）。
    """
    monkeypatch.delenv("SISYS_TENANT_ID", raising=False)
    exit_code = cli_main.main([*command_path, *base_args, agent_flag])
    captured = capsys.readouterr()
    assert exit_code != 2, f"{command_path} × {agent_flag} 参数不可解析（exit 2）: {captured.err!r}"


# ===================================================================
# Task 2 循环 C：7 整合命令挂载与三格式（agent/plan/checkpoint——OD-16 层位）
# ===================================================================

_SEVEN_INTEGRATED: tuple[tuple[str, list[str]], ...] = (
    ("agent", ["instantiate", "run-task"]),
    ("plan", ["generate", "report", "trace-tree"]),
    ("checkpoint", ["list", "recover"]),
)


class TestIntegratedCommandMounting:
    """7 整合命令挂载（controller 抽取后 Typer 面可达）。"""

    @pytest.mark.parametrize(("module", "commands"), _SEVEN_INTEGRATED)
    def test_integrated_commands_mounted(self, module: str, commands: list[str]) -> None:
        """整合命令按 Task 0.1 冻结表挂载。"""
        app = cli_main.get_app()
        groups = {group.name: group for group in app.registered_groups}
        sub_app = groups[module].typer_instance
        assert sub_app is not None, f"{module} 子 app 未实例化"
        registered = {cmd.name for cmd in sub_app.registered_commands}
        for command in commands:
            assert command in registered, f"{module} 缺命令 {command}（实际: {sorted(str(name) for name in registered)}）"


class TestIntegratedCommandFormats:
    """整合命令三格式输出（json/table 消费 controller result——OD-14）。"""

    def test_checkpoint_list_json_envelope(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """checkpoint list --format json：信封 data 含清单视图（渲染源=controller result）。"""

        class _StubSummary:
            checkpoint_no = "CP-1"
            stage_id = "market_insight"
            completed = True
            state_version = 1
            sync_status = "in_sync"

        from src.entrypoints import agent_cli

        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)

        # execute 是 async——异步 stub（R1-T4：首个同步 resolve patch 系被
        # 覆盖的死代码，已删）
        class _AsyncUseCase:
            async def execute(self, **kwargs: object) -> list:
                return [_StubSummary()]

        monkeypatch.setattr(agent_cli, "resolve", lambda name: _AsyncUseCase())
        import uuid as uuid_module

        exit_code = cli_main.main(["checkpoint", "list", "--plan-id", str(uuid_module.uuid4()), "--format", "json"])
        captured = capsys.readouterr()
        assert exit_code == 0, f"json 态 exit={exit_code} stderr={captured.err!r}"
        envelope = json.loads(captured.out)
        assert envelope["command"] == "sisys checkpoint list"
        assert envelope["data"]["checkpoints"][0]["checkpoint_no"] == "CP-1"

    def test_checkpoint_list_dry_run_action_list(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """checkpoint list --dry-run：动作清单+零 bootstrap（守卫段直落短路）。"""
        from src.entrypoints import agent_cli

        bootstrap_calls: list[int] = []
        monkeypatch.setattr(agent_cli, "bootstrap", lambda: bootstrap_calls.append(1))
        import uuid as uuid_module

        exit_code = cli_main.main(["checkpoint", "list", "--plan-id", str(uuid_module.uuid4()), "--dry-run"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "将查询" in captured.out or "将执行" in captured.out
        assert not bootstrap_calls, "dry-run 零 bootstrap 实证失败"

    def test_instantiate_mock_envelope(self, capsys: pytest.CaptureFixture[str]) -> None:
        """agent instantiate --mock：mock 信封+echo 回显。"""
        exit_code = cli_main.main(["agent", "instantiate", "--role", "ceo", "--mock"])
        captured = capsys.readouterr()
        assert exit_code == 0
        envelope = json.loads(captured.out)
        assert envelope["mock"] is True
        assert envelope["echo"]["role"] == "ceo"

    def test_report_dual_format_params(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """plan report：--format json × --report-format markdown 双参数并存可解析（OD-13）。"""
        from src.entrypoints import agent_cli

        class _StubReport:
            memory_id = "mem-1"
            content_markdown = "# 报告"

        class _AsyncReportUseCase:
            async def execute(self, **kwargs: object) -> object:
                return _StubReport()

        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", lambda name: _AsyncReportUseCase())
        import uuid as uuid_module

        exit_code = cli_main.main(
            ["plan", "report", "--plan-id", str(uuid_module.uuid4()), "--format", "json", "--report-format", "markdown"]
        )
        captured = capsys.readouterr()
        assert exit_code == 0, f"双参数并存 exit={exit_code} stderr={captured.err!r}"
        envelope = json.loads(captured.out)
        assert envelope["data"]["report_format"] == "markdown"


class TestRecoverIntegratedSemantics:
    """recover 整合语义（裸跑评估保留/--dry-run 短路/--mode 校验前移——OD-12）。"""

    def _patch_recovery(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
        """patch 评估/执行两用例并返回调用记录。"""
        from src.entrypoints import agent_cli

        calls: dict[str, list[str]] = {"view": [], "execute": []}

        class _ViewUseCase:
            async def execute(self, **kwargs: object) -> object:
                calls["view"].append("called")
                return type("V", (), {"plan_id": "p", "checkpoint_no": 1})()

        class _ExecUseCase:
            async def execute(self, **kwargs: object) -> object:
                calls["execute"].append("called")
                return type("O", (), {"recovery_id": "r-1"})()

        def _resolve(name: str) -> object:
            return {"checkpoint_recovery_use_case": _ViewUseCase(), "checkpoint_recovery_execute_use_case": _ExecUseCase()}[
                name
            ]

        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", _resolve)
        return calls

    def test_bare_run_resolves_view_use_case(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """裸跑：评估模式保留（resolve 视图用例被调）。"""
        calls = self._patch_recovery(monkeypatch)
        import uuid as uuid_module

        exit_code = cli_main.main(["checkpoint", "recover", "--plan-id", str(uuid_module.uuid4()), "--checkpoint-no", "1"])
        captured = capsys.readouterr()
        assert exit_code == 0, f"裸跑评估 exit={exit_code} stderr={captured.err!r}"
        assert calls["view"], "裸跑应 resolve 评估视图用例"
        assert not calls["execute"]

    def test_dry_run_shortcircuits_all_use_cases(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--dry-run：全局短路（评估用例也不触达）+ 清单随 --yes 切换。"""
        calls = self._patch_recovery(monkeypatch)
        import uuid as uuid_module

        exit_code = cli_main.main(
            ["checkpoint", "recover", "--plan-id", str(uuid_module.uuid4()), "--checkpoint-no", "1", "--dry-run"]
        )
        captured = capsys.readouterr()
        assert exit_code == 0
        assert not calls["view"] and not calls["execute"], "dry-run 短路失败（用例被触达）"
        assert "评估" in captured.out

        exit_yes = cli_main.main(
            [
                "checkpoint",
                "recover",
                "--plan-id",
                str(uuid_module.uuid4()),
                "--checkpoint-no",
                "1",
                "--dry-run",
                "--yes",
                "--confirmed-by",
                "cli7",
            ]
        )
        out_yes = capsys.readouterr().out
        assert exit_yes == 0
        assert "执行" in out_yes or "应用" in out_yes, "带 --yes 清单应为执行态措辞"

    def test_mode_validation_before_dryrun(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """--mode 非法值 + --dry-run：值域校验前移守卫段（exit 1 非 0）。"""
        self._patch_recovery(monkeypatch)
        import uuid as uuid_module

        exit_code = cli_main.main(
            [
                "checkpoint",
                "recover",
                "--plan-id",
                str(uuid_module.uuid4()),
                "--checkpoint-no",
                "1",
                "--mode",
                "not-a-mode",
                "--dry-run",
            ]
        )
        captured = capsys.readouterr()
        assert exit_code == 1, f"非法 mode 应 exit 1（dry-run 不豁免）: {exit_code}"
        assert "[EXCEPTION_" in captured.err

    def test_yes_equivalent_confirm_semantics(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--yes（Typer 面）等价 --confirm（兼容入口）：执行用例被调。"""
        calls = self._patch_recovery(monkeypatch)
        import uuid as uuid_module

        from src.entrypoints import agent_cli

        plan_id = str(uuid_module.uuid4())
        exit_code = cli_main.main(
            ["checkpoint", "recover", "--plan-id", plan_id, "--checkpoint-no", "1", "--yes", "--confirmed-by", "cli7"]
        )
        captured = capsys.readouterr()
        assert exit_code == 0, f"--yes 执行 exit={exit_code} stderr={captured.err!r}"
        assert calls["execute"], "Typer 面 --yes 应触达执行用例"

        # 兼容入口 --confirm 同语义（跨入口等价）
        calls["execute"].clear()
        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        exit_compat = agent_cli.main(
            ["checkpoint-recover", "--plan-id", plan_id, "--checkpoint-no", "1", "--confirm", "--confirmed-by", "cli7"]
        )
        assert exit_compat == 0
        assert calls["execute"], "兼容入口 --confirm 应触达执行用例"


class TestR1ContractAssertions:
    """R1 代码审查修复的契约断言族（零锁定项——修完无红=没修的六项之四）。

    覆盖：F2（--format 值域解析层 exit 2）/F7（recover json 双态白名单）/
    F10（--depth 值域解析层 exit 2）/D2（plan generate/trace-tree json 白名单）。
    替身以真实属性形态（枚举/嵌套）构造——防纯 str 替身掩蔽渲染层缺陷。
    """

    def test_f2_invalid_format_rejected_exit_2(self) -> None:
        """--format 非法值解析层拒绝 exit 2（R1-F2——原静默 pretty 真实执行 exit 0）。"""
        import uuid as uuid_module

        exit_code = cli_main.main(
            ["checkpoint", "list", "--plan-id", str(uuid_module.uuid4()), "--format", "yaml", "--dry-run"]
        )
        assert exit_code == 2, f"非法 format 应解析层 exit 2（非静默 pretty）: exit={exit_code}"

    def test_f10_invalid_depth_rejected_exit_2(self) -> None:
        """--depth 非数字与越域值解析层拒绝 exit 2（R1-F10——原 ValueError 兜底 exit 1）。"""
        import uuid as uuid_module

        plan_id = str(uuid_module.uuid4())
        for bad_depth in ("abc", "9"):
            exit_code = cli_main.main(["plan", "trace-tree", "--plan-id", plan_id, "--depth", bad_depth, "--dry-run"])
            assert exit_code == 2, f"--depth {bad_depth} 应解析层 exit 2: exit={exit_code}"

    def test_f5_depth_default_full_tree(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--depth 缺省 4（全深度——与兼容入口一致，R1-F5；R3 强锁升级）。"""
        import uuid as uuid_module

        exit_code = cli_main.main(
            ["plan", "trace-tree", "--plan-id", str(uuid_module.uuid4()), "--dry-run", "--format", "json"]
        )
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        envelope = json.loads(captured.out)
        action = envelope["data"]["actions"][0]
        # R3 补锁：值断言（缺省改坏即红）+ 类名禁令（R2-P1 枚举泄漏复发防线）
        assert "depth=4" in action, f"缺省深度应为 4（全深度）: {action!r}"
        assert "TraceDepth" not in action, f"动作文本枚举类名泄漏（R2-P1 复发）: {action!r}"

    def test_f10_explicit_depth_rendered(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--depth 显式 2 动作文本回显（R3 补锁——合法值面）。"""
        import uuid as uuid_module

        exit_code = cli_main.main(
            ["plan", "trace-tree", "--plan-id", str(uuid_module.uuid4()), "--depth", "2", "--dry-run", "--format", "json"]
        )
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        action = json.loads(captured.out)["data"]["actions"][0]
        assert "depth=2" in action and "TraceDepth" not in action, f"显式深度回显漂移: {action!r}"

    def test_f3_invalid_report_format_242(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--report-format 非法值 242（R3 补锁——原 F3 修复全仓零锁，docx 静默落 markdown 带副作用）。"""
        import uuid as uuid_module

        for bad_format in ("docx", "PDF"):
            exit_code = cli_main.main(
                ["plan", "report", "--plan-id", str(uuid_module.uuid4()), "--report-format", bad_format, "--dry-run"]
            )
            captured = capsys.readouterr()
            assert exit_code == 1, f"--report-format {bad_format} 应 242 拒绝（大小写敏感）: exit={exit_code}"
            assert "EXCEPTION_242" in captured.err, f"守卫定式缺失: {captured.err!r}"

    def test_f14_494_message_neutral_param_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        """494 组合守卫文案含统一面参数名 --report-format（R3 补锁——F14 中性措辞锚）。"""
        import uuid as uuid_module

        exit_code = cli_main.main(
            [
                "plan",
                "report",
                "--plan-id",
                str(uuid_module.uuid4()),
                "--report-format",
                "markdown",
                "--brand-template",
                "tpl",
                "--dry-run",
            ]
        )
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "EXCEPTION_494" in captured.err
        assert "--report-format" in captured.err, f"494 文案应引用统一面参数名（R1-F14）: {captured.err!r}"

    def test_f7_recover_json_assessment_view(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """recover 评估态 json data 白名单（R1-F7——assessment 摘要真值非类名占位）。"""
        import uuid as uuid_module

        from src.domain.entities.checkpoint import RecoveryMode
        from src.entrypoints import agent_cli

        class _StubView:
            checkpoint_no = "1"
            recommended_mode = RecoveryMode.REPLAY
            subsequent_checkpoints = ["CP-2", "CP-3"]

        monkeypatch.setattr(agent_cli, "_checkpoint_recover_controller", lambda *args, **kwargs: _StubView())
        exit_code = cli_main.main(
            ["checkpoint", "recover", "--plan-id", str(uuid_module.uuid4()), "--checkpoint-no", "1", "--format", "json"]
        )
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        data = json.loads(captured.out)["data"]
        assert set(data) == {"plan_id", "checkpoint_no", "assessment"}, f"评估态白名单漂移: {sorted(data)}"
        assert data["assessment"]["recommended_mode"] == "replay", f"RecoveryMode 枚举值泄漏: {data['assessment']!r}"
        assert data["assessment"]["subsequent_count"] == 2

    def test_f7_recover_json_outcome_view(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """recover 执行态 json data 白名单（R1-F7——recovery 摘要真值）。"""
        import uuid as uuid_module

        from src.domain.entities.checkpoint import RecoveryMode
        from src.entrypoints import agent_cli

        class _StubOutcome:
            checkpoint_no = "1"
            recovery_mode = RecoveryMode.OVERRIDE
            corrected = True
            new_state_version = 3
            affected_checkpoints = ["CP-2"]

        monkeypatch.setattr(agent_cli, "_checkpoint_recover_controller", lambda *args, **kwargs: _StubOutcome())
        exit_code = cli_main.main(
            [
                "checkpoint",
                "recover",
                "--plan-id",
                str(uuid_module.uuid4()),
                "--checkpoint-no",
                "1",
                "--yes",
                "--confirmed-by",
                "cli7",
                "--format",
                "json",
            ]
        )
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        data = json.loads(captured.out)["data"]
        assert set(data) == {"plan_id", "checkpoint_no", "recovery"}, f"执行态白名单漂移: {sorted(data)}"
        assert data["recovery"]["mode"] == "override", f"RecoveryMode 枚举值泄漏: {data['recovery']!r}"
        assert data["recovery"]["corrected"] is True
        assert data["recovery"]["new_state_version"] == 3
        assert data["recovery"]["affected_count"] == 1

    def test_d2_plan_generate_json_whitelist(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """plan generate json data 白名单（R1-D2——plan_id/degraded_steps 实现形态锁）。"""
        import uuid as uuid_module

        from src.entrypoints import agent_cli

        class _StubPlanResult:
            plan_id = "22222222-2222-2222-2222-222222222222"
            degraded_steps = ("trend", "gap")

        monkeypatch.setattr(agent_cli, "_blm_plan_controller", lambda *args, **kwargs: _StubPlanResult())
        exit_code = cli_main.main(
            ["plan", "generate", "--agent-id", str(uuid_module.uuid4()), "--task", "t", "--format", "json"]
        )
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        data = json.loads(captured.out)["data"]
        assert set(data) == {"plan_id", "degraded_steps"}, f"generate 白名单漂移: {sorted(data)}"
        assert data["degraded_steps"] == 2

    def test_d2_trace_tree_json_whitelist(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """plan trace-tree json data 白名单（R1-D2——total/build_degraded 实现形态锁）。"""
        import uuid as uuid_module

        from src.entrypoints import agent_cli

        class _StubTree:
            total = 7
            build_degraded = False

        monkeypatch.setattr(agent_cli, "_trace_tree_controller", lambda *args, **kwargs: _StubTree())
        exit_code = cli_main.main(["plan", "trace-tree", "--plan-id", str(uuid_module.uuid4()), "--format", "json"])
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        data = json.loads(captured.out)["data"]
        assert set(data) == {"plan_id", "total", "build_degraded"}, f"trace-tree 白名单漂移: {sorted(data)}"
        assert data["total"] == 7 and data["build_degraded"] is False
