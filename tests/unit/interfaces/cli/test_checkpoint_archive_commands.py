"""Story 7-1 — checkpoint 与 archive 命令组单元测试（Task 6 TDD）。

覆盖 AC-2/AC-5 契约（R3-3 参数形态）：checkpoint list --plan-id（:2524）/
checkpoint show --plan-id --checkpoint-no 复合定位（:2508 预览视图——两参
keyword-only 必填，R5 方案 a）/ checkpoint recover --plan-id --checkpoint-no
[--mode] [--confirmed-by]（:2536 执行面——created_via="cli" 固定传值
R4-2、--confirmed-by 缺省取 --session 且归一先于短路 R4-3）/ archive
query --plan-id（:2567）。--checkpoint-no 为 CP-N 编号非 UUID（格式校验
仅前缀锚定，不入 UUID 守卫族）。

Run with:
    poetry run pytest tests/unit/interfaces/cli/test_checkpoint_archive_commands.py -v
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

_PLAN_ID = "d3e4f5a6-b7c8-4d9e-0f1a-2b3c4d5e6f7a"


class _StubListUseCase:
    """checkpoint_list_use_case stub（execute(*, plan_id) → list[CheckpointSummaryView]）。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, *, plan_id: str) -> list[Any]:
        self.calls.append({"plan_id": plan_id})
        return [
            SimpleNamespace(
                checkpoint_no="CP-1",
                stage_id="market_insight",
                completed=True,
                summary="市场洞察完成",
                state_version="v3",
                created_via="cli",
                timestamp="2026-11-20T10:00:00",
                sync_status="synced",
            )
        ]


class _StubRecoveryUseCase:
    """checkpoint_recovery_use_case stub（:2508 预览面 execute(*, plan_id, checkpoint_no)）。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, *, plan_id: str, checkpoint_no: str) -> Any:
        self.calls.append({"plan_id": plan_id, "checkpoint_no": checkpoint_no})
        return SimpleNamespace(
            checkpoint_no=checkpoint_no,
            stage="market_insight",
            compressed_context="压缩上下文",
            state_data={},
            correction_history=[],
            subsequent_checkpoints=[],
            recommended_mode="replay",
            state_version="v3",
            snapshot_id=str(uuid_module.uuid4()),
        )


class _StubRecoveryExecuteUseCase:
    """checkpoint_recovery_execute_use_case stub（:2536 执行面全 keyword-only 签名）。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(
        self,
        *,
        plan_id: str,
        checkpoint_no: str,
        correction: Any = None,
        mode: Any = None,
        confirmed_by: str = "",
        created_via: str = "use_case",
    ) -> Any:
        self.calls.append(
            {
                "plan_id": plan_id,
                "checkpoint_no": checkpoint_no,
                "correction": correction,
                "mode": mode,
                "confirmed_by": confirmed_by,
                "created_via": created_via,
            }
        )
        return SimpleNamespace(
            checkpoint_no=checkpoint_no,
            recovery_mode=mode,
            corrected=False,
            new_state_version="v4",
            affected_checkpoints=1,
            execution_ms=88,
        )


class _StubChainTraceUseCase:
    """blm_chain_trace_use_case stub（execute(*, plan_id, include_blob=False)）。"""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, *, plan_id: str, include_blob: bool = False) -> Any:
        self.calls.append({"plan_id": plan_id, "include_blob": include_blob})
        return SimpleNamespace(plan_id=plan_id, records=[], total=0, archived_count=0)


def _build_app(**services: Any) -> typer.Typer:
    def _resolve(name: str) -> Any:
        if name in services:
            return services[name]
        raise KeyError(f"测试未注册端口: {name}")

    return create_cli_app(_resolve)


def _services() -> dict[str, Any]:
    return {
        "checkpoint_list_use_case": _StubListUseCase(),
        "checkpoint_recovery_use_case": _StubRecoveryUseCase(),
        "checkpoint_recovery_execute_use_case": _StubRecoveryExecuteUseCase(),
        "blm_chain_trace_use_case": _StubChainTraceUseCase(),
    }


# ===================================================================
# checkpoint list
# ===================================================================


class TestCheckpointListCommand:
    """sisys checkpoint list 契约。"""

    def test_call_contract_plan_id_normalized(self) -> None:
        """调用契约：execute(plan_id=归一后)（:2524 keyword-only 签名）。"""
        services = _services()
        app = _build_app(**services)
        result = runner.invoke(app, ["checkpoint", "list", "--plan-id", _PLAN_ID.upper(), "--format", "json"])
        assert result.exit_code == 0, result.output
        assert services["checkpoint_list_use_case"].calls == [{"plan_id": _PLAN_ID}]

    def test_non_uuid_plan_id_exit_one(self) -> None:
        """非 UUID --plan-id → 242 exit 1（实体族守卫）。"""
        from src.entrypoints import main_cli

        assert main_cli.main(["checkpoint", "list", "--plan-id", "not-a-uuid"]) == 1

    def test_yes_without_budget_guard_on_non_agent_command(self) -> None:
        """非 Agent 命令 --yes 无 budget → 201 exit 1（base 管线统一守卫的命令级锚——防未来守卫移位）。"""
        from src.entrypoints import main_cli

        assert main_cli.main(["checkpoint", "list", "--plan-id", _PLAN_ID, "--yes"]) == 1

    def test_empty_list_exit_zero(self) -> None:
        """空清单 exit 0 + 空态输出（json=[]——R2-6 冻结）。"""
        services = _services()
        services["checkpoint_list_use_case"] = _StubListUseCase()
        services["checkpoint_list_use_case"].calls = []

        async def _empty(*, plan_id: str) -> list[Any]:
            return []

        services["checkpoint_list_use_case"].execute = _empty  # type: ignore[method-assign]
        app = _build_app(**services)
        result = runner.invoke(app, ["checkpoint", "list", "--plan-id", _PLAN_ID, "--format", "json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == []

    def test_dry_run_port_name(self) -> None:
        """--dry-run：端口名 checkpoint_list_use_case（:2524）。"""
        app = _build_app(**_services())
        result = runner.invoke(app, ["checkpoint", "list", "--plan-id", _PLAN_ID, "--dry-run", "--format", "json"])
        assert result.exit_code == 0, result.output
        assert "checkpoint_list_use_case" in result.stdout


# ===================================================================
# checkpoint show（复合定位——:2508 预览视图）
# ===================================================================


class TestCheckpointShowCommand:
    """sisys checkpoint show 契约（R5 方案 a：两参必填复合定位）。"""

    def test_call_contract_preview_view(self) -> None:
        """调用契约：:2508 execute(*, plan_id, checkpoint_no) 预览视图。"""
        services = _services()
        app = _build_app(**services)
        result = runner.invoke(app, ["checkpoint", "show", "--plan-id", _PLAN_ID, "--checkpoint-no", "CP-1"])
        assert result.exit_code == 0, result.output
        assert services["checkpoint_recovery_use_case"].calls == [{"plan_id": _PLAN_ID, "checkpoint_no": "CP-1"}]

    def test_missing_checkpoint_no_usage_error_exit_two(self) -> None:
        """缺 --checkpoint-no → exit 2（两参必填——无「缺省取最新」合成层）。"""
        app = _build_app(**_services())
        result = runner.invoke(app, ["checkpoint", "show", "--plan-id", _PLAN_ID])
        assert result.exit_code == 2

    def test_checkpoint_no_prefix_anchored(self) -> None:
        """--checkpoint-no 非 CP-N 前缀 → 201（格式校验仅前缀锚定——AC-7）。"""
        from src.domain.exceptions import ValidationError
        from src.interfaces.cli.controllers.checkpoint_controller import validate_checkpoint_no

        with pytest.raises(ValidationError) as exc_info:
            validate_checkpoint_no("XX-1")
        assert exc_info.value.code == "EXCEPTION_201"
        assert validate_checkpoint_no("CP-1") == "CP-1"
        assert validate_checkpoint_no("CP-12") == "CP-12"


# ===================================================================
# checkpoint recover（:2536 执行面）
# ===================================================================


class TestCheckpointRecoverCommand:
    """sisys checkpoint recover 契约。"""

    def test_call_contract_execute_surface(self) -> None:
        """调用契约：:2536 execute(plan_id, checkpoint_no, mode, confirmed_by, created_via="cli")（R4-2）。"""
        services = _services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            [
                "checkpoint",
                "recover",
                "--plan-id",
                _PLAN_ID,
                "--checkpoint-no",
                "CP-1",
                "--mode",
                "replay",
                "--confirmed-by",
                "operator-1",
                "--yes",
                "--cost-budget",
                "1.0",
            ],
        )
        assert result.exit_code == 0, result.output
        call = services["checkpoint_recovery_execute_use_case"].calls[0]
        assert call["plan_id"] == _PLAN_ID
        assert call["checkpoint_no"] == "CP-1"
        assert call["mode"] == "replay"
        assert call["confirmed_by"] == "operator-1"
        assert call["created_via"] == "cli", "created_via 固定 cli（缺省会落错触发源审计标识——R4-2）"

    def test_confirmed_by_defaults_to_session(self) -> None:
        """--confirmed-by 缺省取 --session 标识（--session 缺省自动生成——非空串防 242）。"""
        services = _services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            [
                "checkpoint",
                "recover",
                "--plan-id",
                _PLAN_ID,
                "--checkpoint-no",
                "CP-1",
                "--yes",
                "--cost-budget",
                "1.0",
                "--session",
                "sess-cb",
            ],
        )
        assert result.exit_code == 0, result.output
        assert services["checkpoint_recovery_execute_use_case"].calls[0]["confirmed_by"] == "sess-cb"

    def test_invalid_mode_exit_two(self) -> None:
        """非法 --mode 值 → exit 2（typer choice 守卫 replay|override）。"""
        app = _build_app(**_services())
        result = runner.invoke(
            app,
            ["checkpoint", "recover", "--plan-id", _PLAN_ID, "--checkpoint-no", "CP-1", "--mode", "merge"],
        )
        assert result.exit_code == 2

    def test_mode_optional_override(self) -> None:
        """--mode 可选（缺省 None 透传——用例默认推荐模式）。"""
        services = _services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            ["checkpoint", "recover", "--plan-id", _PLAN_ID, "--checkpoint-no", "CP-1", "--mode", "override"],
        )
        assert result.exit_code == 0, result.output
        assert services["checkpoint_recovery_execute_use_case"].calls[0]["mode"] == "override"

    def test_mock_parameters_contain_resolved_confirmed_by(self) -> None:
        """--mock：parameters 含解析后 confirmed_by（守卫层随参数归一完成——R4-3）。"""
        services = _services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            [
                "checkpoint",
                "recover",
                "--plan-id",
                _PLAN_ID,
                "--checkpoint-no",
                "CP-1",
                "--mock",
                "--yes",
                "--cost-budget",
                "1.0",
                "--session",
                "sess-m",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["parameters"]["confirmed_by"] == "sess-m"
        assert services["checkpoint_recovery_execute_use_case"].calls == []

    def test_dry_run_consumes_preview_surface(self) -> None:
        """--dry-run 面消费 :2508 预览视图（天然对齐——AC-5 recover 行注记）。"""
        services = _services()
        app = _build_app(**services)
        result = runner.invoke(
            app,
            ["checkpoint", "recover", "--plan-id", _PLAN_ID, "--checkpoint-no", "CP-1", "--dry-run", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["port"] == "checkpoint_recovery_use_case"
        assert services["checkpoint_recovery_use_case"].calls == [{"plan_id": _PLAN_ID, "checkpoint_no": "CP-1"}], (
            "--dry-run 消费 :2508 预览面执行真实预览查询"
        )
        assert services["checkpoint_recovery_execute_use_case"].calls == []


# ===================================================================
# archive query
# ===================================================================


class TestArchiveQueryCommand:
    """sisys archive query 契约。"""

    def test_call_contract(self) -> None:
        """调用契约：execute(plan_id=归一后)（:2567——fallback find 读路径载体）。"""
        services = _services()
        app = _build_app(**services)
        result = runner.invoke(app, ["archive", "query", "--plan-id", _PLAN_ID.upper()])
        assert result.exit_code == 0, result.output
        assert services["blm_chain_trace_use_case"].calls == [{"plan_id": _PLAN_ID, "include_blob": False}]

    def test_non_uuid_exit_one(self) -> None:
        """非 UUID → 242 exit 1。"""
        from src.entrypoints import main_cli

        assert main_cli.main(["archive", "query", "--plan-id", "not-a-uuid"]) == 1

    def test_empty_records_exit_zero(self) -> None:
        """空归档 exit 0（空态输出——fallback 读路径往返成功语义）。"""
        services = _services()
        app = _build_app(**services)
        result = runner.invoke(app, ["archive", "query", "--plan-id", _PLAN_ID, "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["total"] == 0


# ===================================================================
# help 可达（12 命令矩阵收官）
# ===================================================================


class TestCheckpointArchiveMount:
    """checkpoint/archive 命令组挂载与 help 可达。"""

    @pytest.mark.parametrize(
        "args",
        [
            ["checkpoint", "list", "--help"],
            ["checkpoint", "show", "--help"],
            ["checkpoint", "recover", "--help"],
            ["archive", "query", "--help"],
        ],
    )
    def test_four_commands_help_reachable(self, args: list[str]) -> None:
        """四命令 --help 可达（12 命令矩阵全部就位——AC-5 审计断言）。"""
        app = _build_app(**_services())
        result = runner.invoke(app, args)
        assert result.exit_code == 0
