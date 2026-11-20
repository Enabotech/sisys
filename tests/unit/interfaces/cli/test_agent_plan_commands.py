"""Story 7-1 — agent 与 plan 命令组单元测试（Task 5 TDD）。

覆盖 AC-2/AC-5 契约：agent run（OD-9：位置参数为 agent-id UUID——
RunAgentWorkflowUseCase.execute(agent_id: UUID, task) 签名现实层优先）
/ plan generate --agent-id --task [--plan-id] 双守卫（agent-id 族 201 /
plan-id 实体族 242）/ Mock 短路形态冻结 / Agent 专用参数透传 /
真实面 stub resolve 调用形态。

Run with:
    poetry run pytest tests/unit/interfaces/cli/test_agent_plan_commands.py -v
"""

from __future__ import annotations

import json
import uuid as uuid_module
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from src.interfaces.cli.main import create_cli_app

runner = CliRunner()

_AGENT_ID = "b1c2d3e4-f5a6-4b7c-8d9e-0f1a2b3c4d5e"
_PLAN_ID = "c2d3e4f5-a6b7-4c8d-9e0f-1a2b3c4d5e6f"


class _StubAgentWorkflowUseCase:
    """agent_workflow_use_case stub（execute async——调用契约记录）。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, agent_id: Any, task: str) -> Any:
        self.calls.append({"agent_id": agent_id, "task": task})
        return SimpleNamespace(
            agent_id=str(agent_id),
            workflow_status="completed",
            retry_count=0,
            executed_phases=["市场洞察", "战略选择"],
            evidence=SimpleNamespace(input_hash="h", confidence=0.9, failure_reason=None),
            chain=SimpleNamespace(to_display=lambda: "思维链摘要"),
        )


class _StubBlmPlanningUseCase:
    """blm_planning_use_case stub（execute(agent_id, task, plan_id)——位置参数签名）。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, agent_id: Any, task: str, plan_id: str | None = None) -> Any:
        self.calls.append({"agent_id": agent_id, "task": task, "plan_id": plan_id})
        return SimpleNamespace(
            plan_id=plan_id or str(uuid_module.uuid4()),
            status="completed",
            stages_completed=8,
        )


def _build_app(**services: Any) -> typer.Typer:
    def _resolve(name: str) -> Any:
        if name in services:
            return services[name]
        raise KeyError(f"测试未注册端口: {name}")

    return create_cli_app(_resolve)


def _agent_plan_services() -> dict[str, Any]:
    return {
        "agent_workflow_use_case": _StubAgentWorkflowUseCase(),
        "blm_planning_use_case": _StubBlmPlanningUseCase(),
    }


# ===================================================================
# agent run
# ===================================================================


class TestAgentRunCommand:
    """sisys agent run 契约（OD-9：<agent-id> 位置参数 UUID）。"""

    def test_real_call_contract_via_stub(self) -> None:
        """真实面调用契约：execute(UUID 实例, task)。"""
        services = _agent_plan_services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            ["agent", "run", _AGENT_ID, "--task", "分析市场趋势", "--session", "s-1", "--timeout", "120"],
        )
        assert result.exit_code == 0, result.output
        call = services["agent_workflow_use_case"].calls[0]
        assert call["agent_id"] == uuid_module.UUID(_AGENT_ID)
        assert call["task"] == "分析市场趋势"

    def test_non_uuid_agent_id_raises_201(self) -> None:
        """非 UUID agent-id → ValidationError 201（agent-id 族守卫——_parse_agent_uuid 先例）。"""
        from src.domain.exceptions import ValidationError
        from src.interfaces.cli.controllers.agent_controller import run_agent_workflow

        with pytest.raises(ValidationError) as exc_info:
            run_agent_workflow("not-a-uuid", task="分析", fmt="table", resolve=lambda name: None)
        assert exc_info.value.code == "EXCEPTION_201"

    def test_cli_non_uuid_exit_one(self) -> None:
        """CLI 面：非 UUID → exit 1（守卫先于 bootstrap）。"""
        from src.entrypoints import main_cli

        assert main_cli.main(["agent", "run", "not-a-uuid", "--task", "x", "--mock"]) == 1

    def test_mock_short_circuit_payload_frozen(self) -> None:
        """--mock：DTO 冻结形态（mock/command/parameters/session 四键）。"""
        services = _agent_plan_services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            ["agent", "run", _AGENT_ID, "--task", "分析", "--mock", "--yes", "--cost-budget", "1.5", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["mock"] is True
        assert payload["command"] == "agent run"
        assert payload["parameters"]["agent_id"] == _AGENT_ID
        assert payload["parameters"]["task"] == "分析"
        assert payload["session"]
        assert services["agent_workflow_use_case"].calls == []

    def test_dry_run_port_name(self) -> None:
        """--dry-run：端口名 agent_workflow_use_case（:3178）。"""
        services = _agent_plan_services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            ["agent", "run", _AGENT_ID, "--task", "分析", "--dry-run", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        assert "agent_workflow_use_case" in result.stdout

    def test_missing_budget_rejected(self) -> None:
        """--yes 缺 --cost-budget → exit 1（AC-3 全 Agent 专用命令一致）。"""
        from src.entrypoints import main_cli

        assert main_cli.main(["agent", "run", _AGENT_ID, "--task", "x", "--yes"]) == 1

    def test_uppercase_agent_id_normalized(self) -> None:
        """大写 agent-id 归一后入调用（parse_agent_uuid 返回 UUID 实例归一语义）。"""
        services = _agent_plan_services()
        app = _build_app(**services)
        result = runner.invoke(app, ["agent", "run", _AGENT_ID.upper(), "--task", "分析"])
        assert result.exit_code == 0, result.output
        call = services["agent_workflow_use_case"].calls[0]
        assert str(call["agent_id"]) == _AGENT_ID


# ===================================================================
# plan generate
# ===================================================================


class TestPlanGenerateCommand:
    """sisys plan generate 契约（--agent-id 201 / --plan-id 242 双守卫族）。"""

    def test_real_call_contract_via_stub(self) -> None:
        """真实面调用契约：execute(UUID, task, plan_id)。"""
        services = _agent_plan_services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            ["plan", "generate", "--agent-id", _AGENT_ID, "--task", "生成战略规划", "--plan-id", _PLAN_ID],
        )
        assert result.exit_code == 0, result.output
        call = services["blm_planning_use_case"].calls[0]
        assert call["agent_id"] == uuid_module.UUID(_AGENT_ID)
        assert call["task"] == "生成战略规划"
        assert call["plan_id"] == _PLAN_ID

    def test_non_uuid_plan_id_raises_242(self) -> None:
        """非 UUID --plan-id → EntityValidationError 242（实体 ID 族）。"""
        from src.entrypoints import main_cli

        assert (
            main_cli.main(["plan", "generate", "--agent-id", _AGENT_ID, "--task", "x", "--plan-id", "not-a-uuid", "--mock"])
            == 1
        )

    def test_non_uuid_agent_id_raises_201_cli(self) -> None:
        """CLI 面：非 UUID --agent-id → exit 1（201 族）。"""
        from src.entrypoints import main_cli

        assert main_cli.main(["plan", "generate", "--agent-id", "not-a-uuid", "--task", "x", "--mock"]) == 1

    def test_mock_short_circuit(self) -> None:
        """--mock：plan generate DTO 冻结形态（归一后 agent_id/plan_id 入 parameters）。"""
        services = _agent_plan_services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            [
                "plan",
                "generate",
                "--agent-id",
                _AGENT_ID.upper(),
                "--task",
                "规划",
                "--mock",
                "--yes",
                "--cost-budget",
                "2.0",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["mock"] is True
        assert payload["command"] == "plan generate"
        assert payload["parameters"]["agent_id"] == _AGENT_ID, "大写输入应归一入 parameters"

    def test_dry_run_port_name(self) -> None:
        """--dry-run：端口名 blm_planning_use_case（:3518）。"""
        services = _agent_plan_services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            ["plan", "generate", "--agent-id", _AGENT_ID, "--task", "x", "--dry-run", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        assert "blm_planning_use_case" in result.stdout

    def test_plan_id_optional(self) -> None:
        """--plan-id 可选（缺省 None 透传——BLM 自生成 plan_id）。"""
        services = _agent_plan_services()
        app = _build_app(**services)
        result = runner.invoke(app, ["plan", "generate", "--agent-id", _AGENT_ID, "--task", "x"])
        assert result.exit_code == 0, result.output
        assert services["blm_planning_use_case"].calls[0]["plan_id"] is None


# ===================================================================
# help 可达
# ===================================================================


class TestAgentPlanCommandMount:
    """agent/plan 命令组挂载与 help 可达（AC-5）。"""

    def test_agent_run_help(self) -> None:
        app = _build_app(**_agent_plan_services())
        result = runner.invoke(app, ["agent", "run", "--help"])
        assert result.exit_code == 0
        assert "--task" in result.output

    def test_plan_generate_help(self) -> None:
        app = _build_app(**_agent_plan_services())
        result = runner.invoke(app, ["plan", "generate", "--help"])
        assert result.exit_code == 0
        assert "--agent-id" in result.output
