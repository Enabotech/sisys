"""Agent 模式参数面单测（Task 2 循环 B——AC-3：--yes/--dry-run/--mock）。

测试对=本地脚手架命令（Task 2 时点全局 13 命令未挂载——循环 B 验证注入层
与短路层；Task 3 DoD 三参数无豁免矩阵复验收口）。

语义矩阵（Task 0.2 冻结表 + AC-3 验证标准钦定）：
    - --dry-run：client 语义——守卫全执行（失败 242 exit 1）+ 动作清单 +
      零 resolve 零副作用 + exit 0（短路层=controller 内 dry_run 分叉）
    - --mock：零副作用 + "mock": true 信封 + echo 回显 + exit 0（先过守卫）
    - --yes：等价兼容入口 --confirm（Typer 面仅暴露 --yes）
    - 优先级：--dry-run > --mock > --yes
    - recover 双态：裸跑=评估模式保留（resolve 视图用例被调）；
      --dry-run=全局短路零 resolve（OD-12 归宿落位）
"""

from __future__ import annotations

import json
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from src.entrypoints import agent_cli
from src.interfaces.cli.dispatch import CommandSpec, invoke_command
from src.interfaces.cli.formatters import DryRunOption, FormatOption, MockOption, OutputFormat, YesOption

runner = CliRunner()


class _ResolveRecorder:
    """resolve 计数替身（单测 mock 合法——计数断言锚）。"""

    def __init__(self, payload: Any = None) -> None:
        self.calls: list[str] = []
        self.payload = payload

    def __call__(self, name: str) -> Any:
        self.calls.append(name)
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class _StubView:
    """脚手架视图对象（属性访问形态）。"""

    plan_id = "p-1"
    items: list[str] = []


def _make_scaffold_app() -> tuple[typer.Typer, dict[str, Any]]:
    """构造脚手架 app（单命令——消费 dispatch 注入层；返回 app+捕获面）。"""

    state: dict[str, Any] = {"recorder": _ResolveRecorder(_StubView()), "pretty_shell_called": False}

    def _guard(plan_id: str) -> str:
        return agent_cli._validate_plan_uuid(plan_id, "scaffold-query")

    def controller(dry_run: bool = False) -> Any:
        canonical = _guard(state["input_plan_id"])
        if dry_run:
            return [f"将查询脚手架数据（plan_id={canonical}）"]
        state["recorder"]("scaffold_use_case")
        return {"plan_id": canonical, "total": 0}

    def pretty_shell() -> int:
        state["pretty_shell_called"] = True
        result = controller(dry_run=False)
        print(f"脚手架查询完成: plan_id={result['plan_id']}")
        return 0

    app = typer.Typer()

    @app.command("query")
    def query(
        plan_id: str = typer.Option(..., "--plan-id"),
        dry_run: DryRunOption = False,
        mock: MockOption = False,
        yes: YesOption = False,
        fmt: FormatOption = OutputFormat.PRETTY,
    ) -> None:
        state["input_plan_id"] = plan_id
        invoke_command(
            CommandSpec(
                command="scaffold query",
                controller=controller,
                pretty_shell=pretty_shell,
                mock_echo=lambda: {"plan_id": plan_id},
                fmt=fmt,
            ),
            dry_run=dry_run,
            mock=mock,
            yes=yes,
        )

    root = typer.Typer()
    root.add_typer(app, name="scaffold")
    return root, state


def _make_recover_scaffold_app() -> tuple[typer.Typer, dict[str, Any]]:
    """构造 recover 双态脚手架（confirm 分叉——评估/执行两内核形态）。"""

    state: dict[str, Any] = {"recorder": _ResolveRecorder(_StubView())}

    def _guard(plan_id: str) -> str:
        return agent_cli._validate_plan_uuid(plan_id, "scaffold-recover")

    def _guard_mode(mode: str | None) -> None:
        if mode is not None and mode not in ("replay", "override"):
            from src.domain.exceptions import EntityValidationError

            raise EntityValidationError(
                message="--mode 值域非法（replay|override）",
                context={"command": "scaffold-recover", "field": "mode", "mode": mode},
            )

    def controller(dry_run: bool = False) -> Any:
        _guard(state["input_plan_id"])
        _guard_mode(state["input_mode"])
        if dry_run:
            if state["input_yes"]:
                return ["应用修正", "落恢复记录", "发布事件"]
            return ["输出影响评估"]
        if not state["input_yes"]:
            state["recorder"]("checkpoint_recovery_use_case")
            return {"assessment": "评估视图"}
        state["recorder"]("checkpoint_recovery_execute_use_case")
        return {"recovery_id": "r-1"}

    def pretty_shell() -> int:
        controller(dry_run=False)
        print("脚手架恢复完成")
        return 0

    app = typer.Typer()

    @app.command("recover")
    def recover(
        plan_id: str = typer.Option(..., "--plan-id"),
        mode: str | None = typer.Option(None, "--mode"),
        yes: YesOption = False,
        dry_run: DryRunOption = False,
        mock: MockOption = False,
        fmt: FormatOption = OutputFormat.PRETTY,
    ) -> None:
        state["input_plan_id"] = plan_id
        state["input_mode"] = mode
        state["input_yes"] = yes
        invoke_command(
            CommandSpec(
                command="scaffold recover",
                controller=controller,
                pretty_shell=pretty_shell,
                mock_echo=lambda: {"plan_id": plan_id, "mode": mode},
                fmt=fmt,
            ),
            dry_run=dry_run,
            mock=mock,
            yes=yes,
        )

    root = typer.Typer()
    root.add_typer(app, name="scaffold-recover")
    return root, state


class TestDryRunSemantics:
    """--dry-run client 语义（守卫全执行+动作清单+零 resolve+exit 0）。"""

    def test_dry_run_zero_resolve_and_action_list(self) -> None:
        """dry-run：resolve 计数零 + 动作清单输出 + exit 0（短路实证）。"""
        app, state = _make_scaffold_app()
        import uuid as uuid_module

        result = runner.invoke(app, ["scaffold", "query", "--plan-id", str(uuid_module.uuid4()), "--dry-run"])
        assert result.exit_code == 0, f"dry-run 应 exit 0: {result.output}"
        assert not state["recorder"].calls, f"dry-run 零 resolve 实证失败: {state['recorder'].calls}"
        assert "将查询" in result.output, f"动作清单缺失: {result.output!r}"

    def test_dry_run_guard_not_exempted(self, capsys: pytest.CaptureFixture[str]) -> None:
        """dry-run + 非法 plan-id：守卫不豁免（242 stderr + exit 1）。"""
        app, _ = _make_scaffold_app()
        result = runner.invoke(app, ["scaffold", "query", "--plan-id", "not-a-uuid", "--dry-run"])
        assert result.exit_code == 1, f"守卫失败应 exit 1 非 0: {result.exit_code}"
        # R1-T3：exit 1 单独断言无法区分「242 守卫拒绝」与「意外崩溃」——补定式锚
        assert "EXCEPTION_242" in result.output, f"守卫定式 [EXCEPTION_242] stderr 缺失: {result.output!r}"

    def test_dry_run_follows_format_json(self) -> None:
        """dry-run 遵循 --format（json=data.actions 数组）。"""
        app, _ = _make_scaffold_app()
        import uuid as uuid_module

        result = runner.invoke(
            app, ["scaffold", "query", "--plan-id", str(uuid_module.uuid4()), "--dry-run", "--format", "json"]
        )
        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["mock"] is False
        assert isinstance(envelope["data"]["actions"], list), f"data.actions 数组缺失: {envelope}"


class TestMockSemantics:
    """--mock 信封语义（零副作用+mock=true+echo+exit 0；先过守卫）。"""

    def test_mock_envelope_marker_and_echo(self) -> None:
        """mock：json 信封 mock=true + echo 回显 + resolve 零调用。"""
        app, state = _make_scaffold_app()
        import uuid as uuid_module

        plan_id = str(uuid_module.uuid4())
        result = runner.invoke(app, ["scaffold", "query", "--plan-id", plan_id, "--mock"])
        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["mock"] is True, f"mock 标记缺失: {envelope}"
        assert envelope["echo"]["plan_id"] == plan_id
        assert not state["recorder"].calls, "mock 零 resolve 实证失败"

    def test_mock_guard_not_exempted(self) -> None:
        """mock + 非法参数：先过守卫（242 exit 1 非 exit 0）。"""
        app, _ = _make_scaffold_app()
        result = runner.invoke(app, ["scaffold", "query", "--plan-id", "not-a-uuid", "--mock"])
        assert result.exit_code == 1, f"mock 守卫失败应 exit 1: {result.exit_code}"
        # R1-T3：同上——守卫定式锚（防意外崩溃冒充守卫拒绝）
        assert "EXCEPTION_242" in result.output, f"守卫定式 [EXCEPTION_242] stderr 缺失: {result.output!r}"


class TestPriorityMatrix:
    """三参数并存优先级（--dry-run > --mock > --yes）。"""

    def test_dry_run_takes_priority_over_mock(self) -> None:
        """--dry-run --mock 并存：dry-run 语义生效（动作清单非 mock 信封）。"""
        app, _ = _make_scaffold_app()
        import uuid as uuid_module

        result = runner.invoke(app, ["scaffold", "query", "--plan-id", str(uuid_module.uuid4()), "--dry-run", "--mock"])
        assert result.exit_code == 0
        assert "将查询" in result.output, "dry-run 优先级未生效"
        assert '"mock": true' not in result.output, "dry-run 优先时不应输出 mock 信封"


class TestDefaultAndFormatPaths:
    """缺省 pretty 薄壳与 json/table controller 路径。"""

    def test_default_pretty_shell_called(self) -> None:
        """缺省（无参数）：pretty 薄壳直调（_run_*_cli 同构）。"""
        app, state = _make_scaffold_app()
        import uuid as uuid_module

        result = runner.invoke(app, ["scaffold", "query", "--plan-id", str(uuid_module.uuid4())])
        assert result.exit_code == 0
        assert state["pretty_shell_called"], "缺省态应直调 pretty 薄壳"
        assert "脚手架查询完成" in result.output

    def test_format_json_consumes_controller_result(self) -> None:
        """--format json：渲染源=controller result（resolve 正常调用+信封 data）。"""
        app, state = _make_scaffold_app()
        import uuid as uuid_module

        result = runner.invoke(app, ["scaffold", "query", "--plan-id", str(uuid_module.uuid4()), "--format", "json"])
        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["data"]["total"] == 0, f"信封 data 应为 controller result 视图: {envelope}"
        assert state["recorder"].calls, "json 态应真实调用 resolve"


class TestYesSemantics:
    """--yes 确认门语义（Typer 面仅暴露 --yes）。"""

    def test_yes_flag_accepted_without_gate(self) -> None:
        """无门命令幂等接受 --yes（行为不变——resolve 正常+exit 0）。"""
        app, state = _make_scaffold_app()
        import uuid as uuid_module

        result = runner.invoke(app, ["scaffold", "query", "--plan-id", str(uuid_module.uuid4()), "--yes"])
        assert result.exit_code == 0
        assert state["recorder"].calls, "--yes 幂等接受不改变执行语义"


class TestRecoverDualMode:
    """recover 双态两用例（OD-12 归宿落位——Subtask 2.5 钦定）。"""

    def test_bare_run_preserves_assessment_mode(self) -> None:
        """裸跑（无 flag）：评估模式保留——resolve 视图用例被调。"""
        app, state = _make_recover_scaffold_app()
        import uuid as uuid_module

        result = runner.invoke(app, ["scaffold-recover", "recover", "--plan-id", str(uuid_module.uuid4())])
        assert result.exit_code == 0
        assert "checkpoint_recovery_use_case" in state["recorder"].calls, "裸跑应 resolve 评估视图用例"
        assert "checkpoint_recovery_execute_use_case" not in state["recorder"].calls

    def test_dry_run_shortcircuits_before_use_case(self) -> None:
        """--dry-run：全局短路——零 resolve（评估用例也不触达）。"""
        app, state = _make_recover_scaffold_app()
        import uuid as uuid_module

        result = runner.invoke(app, ["scaffold-recover", "recover", "--plan-id", str(uuid_module.uuid4()), "--dry-run"])
        assert result.exit_code == 0
        assert not state["recorder"].calls, "dry-run 短路零 resolve 失败（评估用例被触达）"
        assert "影响评估" in result.output, "无 --yes 动作清单应为评估态措辞"

    def test_dry_run_action_list_switches_by_yes(self) -> None:
        """dry-run 动作清单随 --yes 切换（评估态/执行态措辞分叉）。"""
        app, _ = _make_recover_scaffold_app()
        import uuid as uuid_module

        bare = runner.invoke(app, ["scaffold-recover", "recover", "--plan-id", str(uuid_module.uuid4()), "--dry-run"])
        with_yes = runner.invoke(
            app, ["scaffold-recover", "recover", "--plan-id", str(uuid_module.uuid4()), "--dry-run", "--yes"]
        )
        assert "影响评估" in bare.output
        assert "应用修正" in with_yes.output, "带 --yes 清单应为执行态措辞"
        assert bare.output != with_yes.output

    def test_mode_validation_before_dryrun_shortcircuit(self) -> None:
        """--mode 值域校验前移守卫段（dry-run 短路不跳过校验——非法值 exit 1）。"""
        app, state = _make_recover_scaffold_app()
        import uuid as uuid_module

        result = runner.invoke(
            app, ["scaffold-recover", "recover", "--plan-id", str(uuid_module.uuid4()), "--mode", "not-a-mode", "--dry-run"]
        )
        assert result.exit_code == 1, f"非法 mode 应守卫失败 exit 1（dry-run 不豁免）: {result.exit_code}"
        assert not state["recorder"].calls
