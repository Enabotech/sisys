"""Story 7-1 — tool 命令组单元测试（Task 4 TDD 循环 B）。

覆盖 AC-5/AC-6 契约：tool list 域过滤 / tool schema 输出含 input_examples
（经 ``skill_loader.load_sop`` → ``SkillDocument.frontmatter.input_examples``
——R1-F3 通路锚）/ tool run 的 slug→``get_tool(tool_name=)``→``Tool.tool_id``
UUID→ToolCall 解析链（R1-F4——slug 非 UUID 禁套 canonical 守卫）/ --input
JSON 装载 / chain run --config 装载 / Agent 专用参数透传 context
（--session/--timeout）。

Run with:
    poetry run pytest tests/unit/interfaces/cli/test_tool_commands.py -v
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from src.application.skills.skill_manifest import SLUG_TO_TOOL_ID
from src.interfaces.cli.main import create_cli_app

runner = CliRunner()

_SLUG = "pestel-analysis"
_TOOL_UUID = SLUG_TO_TOOL_ID[_SLUG]
_INPUT_JSON = '{"query": "市场分析", "time_horizon": "3年"}'


def _make_tool(slug: str = _SLUG) -> Any:
    """构造 Tool 实体 stub（tool_id=skill_manifest 静态映射值——slug→UUID 解析链锚点）。"""
    return SimpleNamespace(
        tool_id=SLUG_TO_TOOL_ID[slug],
        name="PESTEL 分析" if slug == _SLUG else "SWOT 分析",
        slug=slug,
        description="宏观环境分析工具",
        category="analysis",
        input_schema={"query": "string"},
        output_schema={"result": "string"},
        version="1.0.0",
        status="active",
    )


class _StubRegistry:
    """tool_registry_service stub（同步端口——get_tool/register_all/list_all_tools）。"""

    def __init__(self) -> None:
        self.tools: list[Any] = [_make_tool(), _make_tool("swot-tows")]
        self.get_calls: list[dict[str, Any]] = []
        self.register_calls = 0

    def get_tool(self, tool_id: Any = None, tool_name: str | None = None) -> Any:
        self.get_calls.append({"tool_id": tool_id, "tool_name": tool_name})
        for tool in self.tools:
            if tool.tool_id == tool_id or tool.slug == tool_name:
                return tool
        from src.domain.exceptions import ToolNotFoundError

        raise ToolNotFoundError(tool_name=str(tool_name))

    def register_all(self) -> None:
        self.register_calls += 1

    def list_all_tools(self) -> list[Any]:
        return list(self.tools)


class _StubSkillLoader:
    """skill_loader stub（load_sop async → SkillDocument 携 input_examples）。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def load_sop(self, tool_name: str) -> Any:
        self.calls.append(tool_name)
        return SimpleNamespace(
            tool_name="PESTEL 分析",
            slug=tool_name,
            frontmatter=SimpleNamespace(input_examples=('{"query": "示例查询"}',)),
        )


class _StubExecutionService:
    """tool_execution_service stub（execute async——记录解析链产物）。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, tool_id: Any, tool_call: Any, context: Any) -> Any:
        self.calls.append({"tool_id": tool_id, "tool_call": tool_call, "context": context})
        return SimpleNamespace(status="completed", output={"summary": "分析完成"}, execution_ms=120)


class _StubChainUseCase:
    """run_tool_chain_use_case stub。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, chain_name: str, parameters: dict, context: Any) -> Any:
        self.calls.append({"chain_name": chain_name, "parameters": parameters, "context": context})
        return SimpleNamespace(chain_name=chain_name, status="completed", steps_completed=3)


def _build_app(**services: Any) -> typer.Typer:
    """经 create_cli_app 构造含 tool 命令组的测试 app（stub resolve 直注）。"""

    def _resolve(name: str) -> Any:
        if name in services:
            return services[name]
        raise KeyError(f"测试未注册端口: {name}")

    return create_cli_app(_resolve)


def _tool_services(**overrides: Any) -> dict[str, Any]:
    services: dict[str, Any] = {
        "tool_registry_service": _StubRegistry(),
        "skill_loader": _StubSkillLoader(),
        "tool_execution_service": _StubExecutionService(),
        "run_tool_chain_use_case": _StubChainUseCase(),
    }
    services.update(overrides)
    return services


# ===================================================================
# tool list
# ===================================================================


class TestToolListCommand:
    """sisys tool list 契约。"""

    def test_list_all_tools_json(self) -> None:
        """list 输出全部工具（幂等装载 register_all + json 渲染 slug 可见）。"""
        services = _tool_services()
        app = _build_app(**services)
        result = runner.invoke(app, ["tool", "list", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert len(payload) == 2
        assert payload[0]["slug"] == _SLUG
        assert services["tool_registry_service"].register_calls == 1

    def test_list_category_filter(self) -> None:
        """--category 域过滤（get_tools_by_category 消费）。"""
        services = _tool_services()
        services["tool_registry_service"] = _StubRegistry()
        app = _build_app(**services)
        result = runner.invoke(app, ["tool", "list", "--category", "analysis", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert all(row["category"] == "analysis" for row in payload)

    def test_list_mock_short_circuit(self) -> None:
        """--mock：零 resolve 调用（DTO 冻结形态）。"""
        registry = _StubRegistry()
        app = _build_app(tool_registry_service=registry)
        result = runner.invoke(app, ["tool", "list", "--mock", "--format", "json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["mock"] is True
        assert registry.get_calls == []

    def test_dry_run_port_name(self) -> None:
        """--dry-run：静态端口名 tool_registry_service（composition_root.py:2598）。"""
        app = _build_app(**_tool_services())
        result = runner.invoke(app, ["tool", "list", "--dry-run", "--format", "json"])
        assert result.exit_code == 0, result.output
        assert "tool_registry_service" in result.stdout


# ===================================================================
# tool schema
# ===================================================================


class TestToolSchemaCommand:
    """sisys tool schema 契约（input_examples 运行时通路——R1-F3）。"""

    def test_schema_output_contains_input_examples(self) -> None:
        """schema JSON 输出含非空 input_examples（skill_loader.load_sop 通路锚）。"""
        services = _tool_services()
        app = _build_app(**services)
        result = runner.invoke(app, ["tool", "schema", _SLUG, "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["input_examples"] == ['{"query": "示例查询"}']
        assert services["skill_loader"].calls == [_SLUG], "load_sop 应以 slug 调用"

    def test_schema_uses_get_tool_by_slug(self) -> None:
        """schema 经 skill_manifest slug→tool_id 映射后 get_tool(tool_id=) 解析（R1-F4 链）。"""
        services = _tool_services()
        app = _build_app(**services)
        result = runner.invoke(app, ["tool", "schema", _SLUG])
        assert result.exit_code == 0, result.output
        assert services["tool_registry_service"].get_calls == [{"tool_id": _TOOL_UUID, "tool_name": None}]

    def test_schema_unknown_slug_domain_error_exit_one(self) -> None:
        """未知 slug → ToolNotFoundError 透传 exit 1（DomainError 统一出口）。"""
        from src.entrypoints import main_cli

        exit_code = main_cli.main(["tool", "schema", "no-such-tool"])
        assert exit_code == 1

    def test_schema_mock_short_circuit(self) -> None:
        """--mock：parameters 含 slug（DTO 冻结形态，零 resolve）。"""
        services = _tool_services()
        app = _build_app(**services)
        result = runner.invoke(app, ["tool", "schema", _SLUG, "--mock", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["parameters"]["slug"] == _SLUG
        assert services["skill_loader"].calls == []


# ===================================================================
# tool run（slug→UUID 解析链——R1-F4）
# ===================================================================


class TestToolRunCommand:
    """sisys tool run 契约（Agent 专用参数命令）。"""

    def test_run_slug_to_tool_id_resolution_chain(self) -> None:
        """slug→get_tool(tool_name=)→Tool.tool_id UUID→ToolCall 解析链（R1-F4）。"""
        from src.domain.value_objects.tool_execution import ToolCall

        services = _tool_services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            ["tool", "run", _SLUG, "--input", _INPUT_JSON, "--session", "sess-1", "--timeout", "60"],
        )
        assert result.exit_code == 0, result.output
        registry = services["tool_registry_service"]
        execution = services["tool_execution_service"]
        assert registry.get_calls == [{"tool_id": _TOOL_UUID, "tool_name": None}]
        assert len(execution.calls) == 1
        call = execution.calls[0]
        assert call["tool_id"] == _TOOL_UUID, "execute 应收 Tool.tool_id（UUID 非 slug）"
        assert isinstance(call["tool_call"], ToolCall)
        assert call["tool_call"].tool_id == _TOOL_UUID
        assert call["tool_call"].arguments == {"query": "市场分析", "time_horizon": "3年"}

    def test_run_context_carries_session_and_timeout(self) -> None:
        """ExecutionContext 透传 --session/--timeout（Agent 专用参数——AC-3）。"""
        services = _tool_services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            ["tool", "run", _SLUG, "--input", _INPUT_JSON, "--session", "sess-42", "--timeout", "77"],
        )
        assert result.exit_code == 0, result.output
        context = services["tool_execution_service"].calls[0]["context"]
        assert context.session_id == "sess-42"
        assert context.timeout_sec == 77.0

    def test_run_invalid_input_json_raises_201(self) -> None:
        """非法 --input JSON → ValidationError EXCEPTION_201（参数装载守卫）。"""
        from src.domain.exceptions import ValidationError
        from src.interfaces.cli.controllers.tool_controller import load_input_json

        with pytest.raises(ValidationError) as exc_info:
            load_input_json("{not-json")
        assert exc_info.value.code == "EXCEPTION_201"

    def test_run_cli_invalid_input_exit_one(self) -> None:
        """CLI 面：非法 --input → exit 1（守卫先于 bootstrap）。"""
        from src.entrypoints import main_cli

        assert main_cli.main(["tool", "run", _SLUG, "--input", "{not-json", "--dry-run"]) == 1

    def test_run_dry_run_port_name_and_normalized_args(self) -> None:
        """--dry-run：端口名 tool_execution_service（:2741）+ 归一后参数（input 已装载）。"""
        services = _tool_services()
        app = _build_app(**services)
        result = runner.invoke(app, ["tool", "run", _SLUG, "--input", _INPUT_JSON, "--dry-run", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["port"] == "tool_execution_service"
        assert payload["parameters"]["arguments"] == {"query": "市场分析", "time_horizon": "3年"}
        assert services["tool_execution_service"].calls == []

    def test_run_missing_budget_rejected(self) -> None:
        """--yes 缺 --cost-budget → exit 1（Agent 模式守卫在 tool run 生效）。"""
        from src.entrypoints import main_cli

        assert main_cli.main(["tool", "run", _SLUG, "--input", _INPUT_JSON, "--yes"]) == 1

    def test_run_tail_form_agent_params(self) -> None:
        """Agent 专用参数尾置形态（sisys tool run slug --input x --session y 后置可达）。"""
        services = _tool_services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            ["tool", "run", _SLUG, "--input", _INPUT_JSON, "--session", "sess-tail", "--timeout", "90", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        context = services["tool_execution_service"].calls[0]["context"]
        assert context.session_id == "sess-tail"
        assert context.timeout_sec == 90.0


# ===================================================================
# tool chain run
# ===================================================================


class TestToolChainRunCommand:
    """sisys tool chain run 契约。"""

    def test_chain_run_config_inline_json(self) -> None:
        """chain run --config 内联 JSON 装载（parameters dict 透传）。"""
        services = _tool_services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            ["tool", "chain", "run", "pestel-swot-chain", "--config", '{"domain": "新能源"}', "--session", "s1"],
        )
        assert result.exit_code == 0, result.output
        call = services["run_tool_chain_use_case"].calls[0]
        assert call["chain_name"] == "pestel-swot-chain"
        assert call["parameters"] == {"domain": "新能源"}

    def test_chain_run_config_from_file(self, tmp_path: Any) -> None:
        """chain run --config 文件路径装载（读文件 JSON）。"""
        config_file = tmp_path / "chain-config.json"
        config_file.write_text('{"domain": "半导体"}', encoding="utf-8")
        services = _tool_services()
        app = _build_app(**services)
        result = runner.invoke(app, ["tool", "chain", "run", "chain-x", "--config", str(config_file)])
        assert result.exit_code == 0, result.output
        assert services["run_tool_chain_use_case"].calls[0]["parameters"] == {"domain": "半导体"}

    def test_chain_run_dry_run_port_name(self) -> None:
        """--dry-run：端口名 run_tool_chain_use_case（:2945）。"""
        services = _tool_services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            ["tool", "chain", "run", "chain-x", "--config", "{}", "--dry-run", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        assert "run_tool_chain_use_case" in result.stdout


# ===================================================================
# help 可达
# ===================================================================


class TestToolCommandGroupMount:
    """tool 命令组挂载与 help 可达（AC-5）。"""

    @pytest.mark.parametrize(
        ("args", "anchor"),
        [
            (["tool", "list", "--help"], "--category"),
            (["tool", "schema", "--help"], "SLUG"),
            (["tool", "run", "--help"], "--input"),
            (["tool", "chain", "--help"], "run"),
        ],
    )
    def test_four_commands_help_reachable(self, args: list[str], anchor: str) -> None:
        """四命令 --help 自描述可达（12 命令矩阵 tool 族）。"""
        app = _build_app(**_tool_services())
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        assert anchor in result.output
