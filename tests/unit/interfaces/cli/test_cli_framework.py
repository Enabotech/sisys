"""Story 7-1 — CLI 基础框架单元测试（Task 2 TDD 循环 A：工厂与全局参数）。

覆盖 AC-1/AC-3 契约：create_cli_app 工厂（stub resolve 直注——DC-2 DI 红利）、
六模块子 app 挂载、--version 顶层选项（R3-6 callback 豁免边界）、--format
Enum choice 值域 exit 2、全局参数尾置形态解析（R1-F1 P0 回归锚——测试内
动态挂载消费 _params 注解的桩命令验证机制，各命令组尾置断言随 Task 3-6
落地——R2-A1 时序注）、短路执行基建（--dry-run 静态端口名+resolve 零调用
/--mock DTO/--yes 缺 budget→201）。

Run with:
    poetry run pytest tests/unit/interfaces/cli/test_cli_framework.py -v
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from src.interfaces.cli import _params

runner = CliRunner()

_SIX_MODULES = ("document", "tool", "agent", "plan", "checkpoint", "archive")


def _stub_resolve_factory() -> tuple[dict[str, Any], Any]:
    """构造计数型 stub resolve（DC-2 工厂注入——断言零调用/调用契约）。"""

    calls: dict[str, int] = {}

    def _resolve(name: str) -> Any:
        calls[name] = calls.get(name, 0) + 1
        return object()

    return calls, _resolve


# ===================================================================
# 工厂与模块挂载
# ===================================================================


class TestCreateCliAppFactory:
    """create_cli_app 工厂契约（AC-1：三级结构自描述+六模块挂载）。"""

    def test_factory_returns_typer_app_with_six_modules(self) -> None:
        """工厂返回 Typer 实例且六模块子 app 全部挂载（--help 可见）。"""
        from src.interfaces.cli.main import create_cli_app

        _, stub = _stub_resolve_factory()
        result = runner.invoke(create_cli_app(stub), ["--help"])
        assert result.exit_code == 0, result.output
        for module_name in _SIX_MODULES:
            assert module_name in result.output, f"--help 缺模块 {module_name}: {result.output}"

    @pytest.mark.parametrize("module_name", list(_SIX_MODULES))
    def test_each_module_help_reachable(self, module_name: str) -> None:
        """各模块 --help 自描述可达（骨架组挂载断言两时点之一——R3-4）。"""
        from src.interfaces.cli.main import create_cli_app

        _, stub = _stub_resolve_factory()
        result = runner.invoke(create_cli_app(stub), [module_name, "--help"])
        assert result.exit_code == 0, result.output

    def test_version_flag_top_level_exit_zero(self) -> None:
        """--version 顶层选项 exit 0（R3-6 豁免边界：顶层前置形态无尾置可达性问题）。"""
        from src.interfaces.cli.main import create_cli_app

        _, stub = _stub_resolve_factory()
        result = runner.invoke(create_cli_app(stub), ["--version"])
        assert result.exit_code == 0, result.output
        assert result.output.strip()


# ===================================================================
# 全局参数共享注解（_params.py）与尾置机制
# ===================================================================


class TestSharedParamsTailForm:
    """共享 Annotated 参数注解（_params.py 单一来源）+ 尾置形态解析（R1-F1）。"""

    def _build_stub_app(self) -> Any:
        """工厂+动态挂载消费 _params 注解的桩命令（机制验证载体——R2-A1）。"""
        from src.interfaces.cli.main import create_cli_app

        _, stub = _stub_resolve_factory()
        app = create_cli_app(stub)
        captured: dict[str, Any] = {}

        @app.command(name="stub-probe")
        def stub_probe(
            yes: _params.YesOption = False,
            dry_run: _params.DryRunOption = False,
            mock: _params.MockOption = False,
            fmt: _params.FormatOption = _params.OutputFormat.TABLE,
            session: _params.SessionOption = "",
            timeout: _params.TimeoutOption = 300,
            cost_budget: _params.CostBudgetOption = None,
            task: str = typer.Option("默认任务", "--task"),
        ) -> None:
            captured.update(
                task=task,
                yes=yes,
                dry_run=dry_run,
                mock=mock,
                fmt=str(fmt.value) if hasattr(fmt, "value") else fmt,
                session=session,
                timeout=timeout,
                cost_budget=cost_budget,
            )

        return app, captured

    def test_tail_form_global_params_parsed(self) -> None:
        """全局参数尾置形态解析（sisys cmd --task x --yes --cost-budget 1.5 后置可达——P0 回归锚）。"""
        app, captured = self._build_stub_app()
        result = runner.invoke(
            app,
            ["stub-probe", "--task", "分析", "--yes", "--cost-budget", "1.5", "--dry-run", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        assert captured["task"] == "分析"
        assert captured["yes"] is True
        assert captured["dry_run"] is True
        assert captured["fmt"] == "json"
        assert captured["cost_budget"] == "1.5"

    def test_format_enum_invalid_value_exit_two(self) -> None:
        """非法 --format 值 → exit 2（typer Enum choice 守卫——AC-4）。"""
        app, _ = self._build_stub_app()
        result = runner.invoke(app, ["stub-probe", "--format", "yaml"])
        assert result.exit_code == 2

    def test_format_default_is_table(self) -> None:
        """缺省 --format=table（AC-3 钦定默认值）。"""
        app, captured = self._build_stub_app()
        result = runner.invoke(app, ["stub-probe"])
        assert result.exit_code == 0, result.output
        assert captured["fmt"] == "table"

    def test_agent_params_defaults(self) -> None:
        """Agent 专用参数缺省值（--session 缺省自动生成占位/--timeout 缺省 300）。"""
        app, captured = self._build_stub_app()
        result = runner.invoke(app, ["stub-probe"])
        assert result.exit_code == 0, result.output
        assert captured["timeout"] == 300


# ===================================================================
# 短路执行基建（controllers/base.execute_command）
# ===================================================================


def _make_command_context(**overrides: Any) -> Any:
    """构造短路执行器入参（CommandContext 值对象）。"""
    from src.interfaces.cli.controllers.base import CommandContext

    defaults: dict[str, Any] = {
        "command": "stub-probe",
        "port_name": "stub_service",
        "parameters": {"task": "分析", "plan_id": "12345678-1234-5678-1234-567812345678"},
        "fmt": "table",
        "dry_run": False,
        "mock": False,
        "yes": False,
        "cost_budget": None,
        "session": "session-abc",
    }
    defaults.update(overrides)
    return CommandContext(**defaults)


class TestExecuteCommandShortCircuits:
    """短路执行基建（--dry-run 最外层/--mock 次层/守卫前置——DC-5 优先级契约）。"""

    def test_dry_run_renders_port_name_and_params_zero_resolve(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--dry-run 输出静态端口名与归一后参数，resolve 零调用（不 bootstrap 自洽——R1-F5）。"""
        from src.interfaces.cli.controllers.base import execute_command

        calls, stub = _stub_resolve_factory()

        def _real_runner(resolve: Any) -> int:
            return resolve("stub_service") and 0 or 0

        exit_code = execute_command(_make_command_context(dry_run=True), stub, _real_runner)
        assert exit_code == 0
        assert calls == {}, "--dry-run 面 resolve 应零调用（不 bootstrap 契约）"
        output = capsys.readouterr().out
        assert "stub_service" in output, f"--dry-run 输出缺端口名: {output!r}"
        assert "stub-probe" in output

    def test_mock_returns_dto_without_resolve(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--mock 短路返回冻结 DTO（mock/command/parameters/session 四键），resolve 零调用。"""
        from src.interfaces.cli.controllers.base import execute_command

        calls, stub = _stub_resolve_factory()

        def _real_runner(resolve: Any) -> int:
            raise AssertionError("mock 面不得进入真实执行")

        exit_code = execute_command(_make_command_context(mock=True, fmt="json"), stub, _real_runner)
        assert exit_code == 0
        assert calls == {}
        output = capsys.readouterr().out
        assert '"mock": true' in output or '"mock":true' in output
        assert "stub-probe" in output and "session-abc" in output

    def test_dry_run_takes_precedence_over_mock(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--dry-run×--mock 同给 → --dry-run 优先（输出端口名预览非 mock DTO——R1-21/R2-8）。"""
        from src.interfaces.cli.controllers.base import execute_command

        calls, stub = _stub_resolve_factory()
        exit_code = execute_command(_make_command_context(dry_run=True, mock=True, fmt="json"), stub, lambda resolve: 0)
        assert exit_code == 0
        output = capsys.readouterr().out
        assert "stub_service" in output, "dry-run 优先应输出端口名预览"
        assert '"mock": true' not in output and '"mock":true' not in output, "不应输出 mock DTO"

    def test_yes_without_budget_raises_validation_error_201(self) -> None:
        """--yes 缺 --cost-budget → ValidationError EXCEPTION_201（守卫先于短路——AC-3）。"""
        from src.domain.exceptions import ValidationError
        from src.interfaces.cli.controllers.base import execute_command

        calls, stub = _stub_resolve_factory()
        with pytest.raises(ValidationError) as exc_info:
            execute_command(_make_command_context(yes=True, cost_budget=None, mock=True), stub, lambda resolve: 0)
        assert exc_info.value.code == "EXCEPTION_201"
        assert calls == {}, "守卫拒绝面 resolve 应零调用"

    def test_yes_with_budget_passes_guard(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--yes + --cost-budget 齐备 → 守卫通过（mock 短路正常返回）。"""
        from src.interfaces.cli.controllers.base import execute_command

        calls, stub = _stub_resolve_factory()
        exit_code = execute_command(
            _make_command_context(yes=True, cost_budget=Decimal("1.5"), mock=True), stub, lambda resolve: 0
        )
        assert exit_code == 0

    def test_default_format_renders_table(self, capsys: pytest.CaptureFixture[str]) -> None:
        """缺省 fmt=table 渲染（R1-F30 断言锚：默认 table 非 JSON）。"""
        from src.interfaces.cli.controllers.base import execute_command

        _, stub = _stub_resolve_factory()
        execute_command(_make_command_context(mock=True), stub, lambda resolve: 0)
        output = capsys.readouterr().out
        assert output.strip() and not output.strip().startswith("{")


# ===================================================================
# 共享参数注解单一来源
# ===================================================================


class TestParamsModuleContract:
    """_params.py 共享注解契约（Annotated 类型单一来源——R1-F1 机制载体）。"""

    def test_params_module_exports_all_shared_options(self) -> None:
        """七项共享注解齐备（四全局+三 Agent 专用）。"""
        from src.interfaces.cli import _params

        for name in (
            "YesOption",
            "DryRunOption",
            "MockOption",
            "FormatOption",
            "SessionOption",
            "TimeoutOption",
            "CostBudgetOption",
        ):
            assert hasattr(_params, name), f"_params 缺共享注解 {name}"

    def test_format_option_is_enum_choice(self) -> None:
        """FormatOption 注解为 Enum 值域（json|table|pretty——choice 守卫载体）。"""
        import enum
        import typing

        from src.interfaces.cli import _params

        annotation = _params.FormatOption
        actual = typing.get_args(annotation)[0] if hasattr(annotation, "__metadata__") else annotation
        assert isinstance(actual, type) and issubclass(actual, enum.Enum), f"FormatOption 应为 Enum 值域: {actual}"
        assert {member.value for member in actual} == {"json", "table", "pretty"}


# ===================================================================
# TDD 循环 B：共享守卫（canonical_uuid / agent UUID）
# ===================================================================


class TestCanonicalUuidGuard:
    """canonical_uuid 守卫（plan-id 实体族——EntityValidationError 242 契约）。"""

    def test_lowercase_canonical_passthrough(self) -> None:
        """canonical 小写形态原样返回。"""
        from src.interfaces.cli._guards import canonical_uuid

        value = "12345678-1234-5678-1234-567812345678"
        assert canonical_uuid(value, field="plan_id") == value

    def test_uppercase_normalized(self) -> None:
        """大写形态归一为 canonical 小写（6.9-R1-DF1 新面清偿——非静默空态）。"""
        from src.interfaces.cli._guards import canonical_uuid

        assert canonical_uuid("12345678-1234-5678-1234-567812345678".upper(), field="plan_id") == (
            "12345678-1234-5678-1234-567812345678"
        )

    def test_urn_form_normalized(self) -> None:
        """URN 形态归一命中。"""
        from src.interfaces.cli._guards import canonical_uuid

        assert canonical_uuid("urn:uuid:12345678-1234-5678-1234-567812345678", field="plan_id") == (
            "12345678-1234-5678-1234-567812345678"
        )

    def test_no_hyphen_form_normalized(self) -> None:
        """无连字符形态归一命中。"""
        from src.interfaces.cli._guards import canonical_uuid

        assert canonical_uuid("12345678123456781234567812345678", field="plan_id") == ("12345678-1234-5678-1234-567812345678")

    def test_non_uuid_raises_entity_validation_242(self) -> None:
        """非 UUID → EntityValidationError EXCEPTION_242（实体 ID 族契约）。"""
        from src.domain.exceptions import EntityValidationError
        from src.interfaces.cli._guards import canonical_uuid

        with pytest.raises(EntityValidationError) as exc_info:
            canonical_uuid("not-a-uuid", field="plan_id")
        assert exc_info.value.code == "EXCEPTION_242"
        assert "plan_id" in str(exc_info.value.context)


class TestAgentUuidGuard:
    """agent UUID 守卫（agent-id 族——ValidationError 201，_parse_agent_uuid 先例）。"""

    def test_valid_agent_uuid_returns_uuid_instance(self) -> None:
        """合法 UUID 返回 uuid.UUID 实例。"""
        from src.interfaces.cli._guards import parse_agent_uuid

        parsed = parse_agent_uuid("12345678-1234-5678-1234-567812345678")
        assert str(parsed) == "12345678-1234-5678-1234-567812345678"

    def test_invalid_agent_uuid_raises_validation_201(self) -> None:
        """非 UUID → ValidationError EXCEPTION_201（agent-id 族契约）。"""
        from src.domain.exceptions import ValidationError
        from src.interfaces.cli._guards import parse_agent_uuid

        with pytest.raises(ValidationError) as exc_info:
            parse_agent_uuid("not-a-uuid")
        assert exc_info.value.code == "EXCEPTION_201"

    def test_whitespace_stripped_before_parse(self) -> None:
        """首尾空白剥离后解析（agent_cli :156-173 先例形态）。"""
        from src.interfaces.cli._guards import parse_agent_uuid

        assert str(parse_agent_uuid("  12345678-1234-5678-1234-567812345678  ")) == ("12345678-1234-5678-1234-567812345678")


# ===================================================================
# TDD 循环 B：进程入口（main_cli.main）
# ===================================================================


class TestMainCliEntrypoint:
    """main_cli 进程入口契约（load_dotenv→懒 bootstrap→create_cli_app→派发）。"""

    def test_main_signature_returns_int(self) -> None:
        """模块级 main(argv: list[str] | None = None) -> int 签名契约（agent_cli:2623 同签名先例）。"""
        import inspect

        from src.entrypoints import main_cli

        signature = inspect.signature(main_cli.main)
        params = list(signature.parameters)
        assert params == ["argv"]
        assert signature.return_annotation in ("int", int)

    def test_load_dotenv_called_before_bootstrap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_dotenv(ENV_FILE) 在 main() 函数体内先于 bootstrap（R3-5 钉死——顺序守卫）。

        --version 零 resolve 路径：load_dotenv 已调用、bootstrap 零调用；
        随后手动触发懒 bootstrap（_resolve_port 包装）断言顺序（注册表探测
        monkeypatch 强制走 bootstrap 分支——conftest session bootstrap 隔离）。
        """
        from src.entrypoints import main_cli

        calls: list[str] = []
        monkeypatch.setattr(
            main_cli,
            "load_dotenv",
            lambda *_args, **_kwargs: calls.append("load_dotenv"),
            raising=False,
        )
        monkeypatch.setattr(main_cli, "bootstrap", lambda: calls.append("bootstrap"), raising=False)
        monkeypatch.setattr(main_cli, "_BOOTSTRAPPED", False)
        monkeypatch.setattr(main_cli, "_registry_bootstrapped", lambda: False)

        exit_code = main_cli.main(["--version"])
        assert exit_code == 0
        assert "load_dotenv" in calls, "main() 应在函数体内调用 load_dotenv"
        assert "bootstrap" not in calls, "--version 零 resolve 路径不应 bootstrap"

        main_cli._resolve_port("tool_registry_service")
        assert "bootstrap" in calls, "懒 bootstrap 应在首次 resolve 时触发"
        assert calls.index("load_dotenv") < calls.index("bootstrap"), "load_dotenv 必须先于 bootstrap"

    def test_domain_error_maps_to_stderr_and_exit_one(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """DomainError → stderr [EXCEPTION_NNN] message + exit 1（AC-1 逐字契约）。"""
        from src.domain.exceptions import ValidationError
        from src.entrypoints import main_cli

        class _BoomApp:
            def __call__(self, argv: list[str], *, standalone_mode: bool = False) -> int:
                raise ValidationError(message="领域校验失败", context={})

        monkeypatch.setattr(main_cli, "load_dotenv", lambda *_a, **_k: None, raising=False)
        monkeypatch.setattr(main_cli, "create_cli_app", lambda _resolve: _BoomApp())
        exit_code = main_cli.main(["document", "upload"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "[EXCEPTION_201] 领域校验失败" in captured.err

    def test_usage_error_maps_to_exit_two(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """click UsageError → exit 2（用法错误契约）。"""
        import click

        from src.entrypoints import main_cli

        class _UsageBoomApp:
            def __call__(self, argv: list[str], *, standalone_mode: bool = False) -> int:
                raise click.exceptions.UsageError("No such option")

        monkeypatch.setattr(main_cli, "load_dotenv", lambda *_a, **_k: None, raising=False)
        monkeypatch.setattr(main_cli, "create_cli_app", lambda _resolve: _UsageBoomApp())
        assert main_cli.main(["--unknown-option"]) == 2

    def test_typer_exit_maps_to_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """typer.Exit(exit_code=N) → N（--help/--version 等内置出口映射）。"""
        import typer

        from src.entrypoints import main_cli

        class _ExitApp:
            def __call__(self, argv: list[str], *, standalone_mode: bool = False) -> int:
                raise typer.Exit(2)

        monkeypatch.setattr(main_cli, "load_dotenv", lambda *_a, **_k: None, raising=False)
        monkeypatch.setattr(main_cli, "create_cli_app", lambda _resolve: _ExitApp())
        assert main_cli.main(["whatever"]) == 2

    def test_int_return_passthrough(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """命令函数返回 int 退出码直传（standalone_mode=False 返回值语义）。"""
        from src.entrypoints import main_cli

        class _IntApp:
            def __call__(self, argv: list[str], *, standalone_mode: bool = False) -> int:
                return 5

        monkeypatch.setattr(main_cli, "load_dotenv", lambda *_a, **_k: None, raising=False)
        monkeypatch.setattr(main_cli, "create_cli_app", lambda _resolve: _IntApp())
        assert main_cli.main(["whatever"]) == 5

    def test_none_return_maps_to_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """命令函数返回 None → 0（无显式退出码默认成功）。"""
        from src.entrypoints import main_cli

        class _NoneApp:
            def __call__(self, argv: list[str], *, standalone_mode: bool = False) -> None:
                return None

        monkeypatch.setattr(main_cli, "load_dotenv", lambda *_a, **_k: None, raising=False)
        monkeypatch.setattr(main_cli, "create_cli_app", lambda _resolve: _NoneApp())
        assert main_cli.main(["whatever"]) == 0

    def test_env_file_constant_is_repo_root(self) -> None:
        """ENV_FILE 模块常量 = 仓库根 .env（parents[2] 推导——R2-11 钉死）。"""
        from pathlib import Path

        from src.entrypoints import main_cli

        expected = Path(main_cli.__file__).resolve().parents[2] / ".env"
        assert main_cli.ENV_FILE == expected
