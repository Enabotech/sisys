"""工具 CLI 命令单元测试（Task 3 循环 B——tool list / tool run）。

端口契约（Task 0.1 冻结表 + 能力级对账）：
    - list → ``tool_execution_service.list_tools_metadata(ToolListQuery)``
      （**同步方法**——Query Object：tenant_id 可选 UUID/category/status/offset/limit）
    - run → ``tool_execution_service.execute(tool_id, ToolCall, ExecutionContext)``
      （ExecutionContext.tenant_id 为 UUID 类型——CLI 面字符串转换守卫）
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.entrypoints import cli_main
from src.interfaces.cli.commands import tool_commands


class _StubTool:
    """Tool 实体替身（R1-F4 后 category/status 用真实枚举——纯 str 替身掩蔽 str() 泄漏形态）。"""

    def __init__(self, tool_id: str = "99999999-9999-9999-9999-999999999999") -> None:
        from src.domain.entities.tool import ToolCategory, ToolStatus

        self.tool_id = tool_id
        self.name = "swot-tows"
        self.category = ToolCategory.ANALYSIS
        self.status = ToolStatus.ACTIVE


class _StubToolService:
    """工具执行服务替身（list 同步 + execute 异步双形态）。"""

    def __init__(self) -> None:
        self.list_queries: list[Any] = []
        self.execute_calls: list[dict[str, Any]] = []

    def list_tools_metadata(self, query: Any) -> list[_StubTool]:
        self.list_queries.append(query)
        return [_StubTool(), _StubTool("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")]

    async def execute(self, tool_id: Any, tool_call: Any, context: Any) -> object:
        from src.domain.value_objects.tool_execution import ToolResultStatus

        self.execute_calls.append({"tool_id": tool_id, "tool_call": tool_call, "context": context})
        return type("TR", (), {"status": ToolResultStatus.SUCCESS, "output": {"result": "ok"}, "error": None})()


def _patch_service(monkeypatch: pytest.MonkeyPatch) -> _StubToolService:
    """注入工具服务替身（tool_commands 模块级 get_resolver patch 点）。"""
    stub = _StubToolService()

    class _FakeResolver:
        def resolve(self, name: str) -> object:
            assert name == "tool_execution_service", f"端口名漂移: {name}"
            return stub

    monkeypatch.setattr(tool_commands, "get_resolver", lambda: _FakeResolver())
    return stub


class TestToolListCommand:
    """tool list 命令（Query Object 调用形态）。"""

    def test_list_calls_with_query_object(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """list 经 ToolListQuery 调用（缺省全租户视图——tenant_id None）。"""
        stub = _patch_service(monkeypatch)
        exit_code = cli_main.main(["tool", "list"])
        assert exit_code == 0, capsys.readouterr()
        assert len(stub.list_queries) == 1, "list_tools_metadata 应恰一次调用"
        query = stub.list_queries[0]
        assert query.tenant_id is None, "缺省全租户视图（ToolListQuery.tenant_id Optional）"
        assert query.limit == 100

    def test_list_tenant_optional_filter(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """--tenant-id 可选过滤（UUID 转换——ToolListQuery 契约）。"""
        import uuid as uuid_module

        stub = _patch_service(monkeypatch)
        tenant = str(uuid_module.uuid4())
        exit_code = cli_main.main(["tool", "list", "--tenant-id", tenant])
        assert exit_code == 0, capsys.readouterr()
        assert str(stub.list_queries[0].tenant_id) == tenant

    def test_list_tenant_invalid_uuid_242(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """非法租户 UUID → 242 stderr（ToolListQuery 契约前置守卫）。"""
        _patch_service(monkeypatch)
        exit_code = cli_main.main(["tool", "list", "--tenant-id", "not-a-uuid"])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "[EXCEPTION_" in captured.err

    def test_list_json_envelope(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """--format json：tools 白名单（tool_id/name/category/status）。"""
        _patch_service(monkeypatch)
        exit_code = cli_main.main(["tool", "list", "--format", "json"])
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        envelope = json.loads(captured.out)
        assert envelope["data"]["total"] == 2
        first = envelope["data"]["tools"][0]
        assert {"tool_id", "name", "category", "status"} <= set(first)

    def test_list_json_enum_values_no_class_prefix(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """枚举字段以 .value 形态进信封（R1-F4 零锁定断言——替身真实枚举）。

        Py3.11 下 (str,Enum) 的 str() 输出 "ToolStatus.ACTIVE" 类名形态——
        json 信封机器可消费契约（P1）禁止该泄漏；本断言删 enum_value 包装即红。
        """
        _patch_service(monkeypatch)
        exit_code = cli_main.main(["tool", "list", "--format", "json"])
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        envelope = json.loads(captured.out)
        first = envelope["data"]["tools"][0]
        assert first["status"] == "active", f"status 枚举值泄漏类名前缀: {first['status']!r}"
        assert first["category"] == "analysis", f"category 枚举值泄漏类名前缀: {first['category']!r}"
        assert "." not in first["status"] and "." not in first["category"]

    def test_list_dry_run_zero_service(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """--dry-run：读命令退化态（守卫+动作回显零 service）。"""
        stub = _patch_service(monkeypatch)
        exit_code = cli_main.main(["tool", "list", "--dry-run"])
        assert exit_code == 0, capsys.readouterr()
        assert not stub.list_queries, "dry-run 零 service 调用失败"


class TestToolRunCommand:
    """tool run 命令（execute 调用形态+dry-run 门+mock 信封）。"""

    def test_run_calls_execute_full_contract(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """run 全参（tool_id/ToolCall.arguments/ExecutionContext.tenant_id UUID）。"""
        import uuid as uuid_module

        stub = _patch_service(monkeypatch)
        tool_id = str(uuid_module.uuid4())
        tenant = str(uuid_module.uuid4())
        exit_code = cli_main.main(["tool", "run", "--tool-id", tool_id, "--input", '{"domain": "tech"}', "--tenant-id", tenant])
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        assert len(stub.execute_calls) == 1
        call = stub.execute_calls[0]
        assert str(call["tool_id"]) == tool_id
        assert call["tool_call"].arguments == {"domain": "tech"}

    def test_run_input_json_guard(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """--input 非 JSON → 242 stderr（守卫先于 service）。"""
        import uuid as uuid_module

        _patch_service(monkeypatch)
        exit_code = cli_main.main(
            [
                "tool",
                "run",
                "--tool-id",
                str(uuid_module.uuid4()),
                "--input",
                "not-json",
                "--tenant-id",
                str(uuid_module.uuid4()),
            ]
        )
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "[EXCEPTION_" in captured.err

    def test_run_tool_id_uuid_guard(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """非法 tool-id → 242 stderr。"""
        _patch_service(monkeypatch)
        exit_code = cli_main.main(["tool", "run", "--tool-id", "bad", "--input", "{}", "--tenant-id", "t"])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "[EXCEPTION_" in captured.err

    def test_run_tenant_dual_channel_env_fallback(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--tenant-id 缺省经 SISYS_TENANT_ID env 回退（R1-F12 双通道——零锁定断言）。"""
        import uuid as uuid_module

        stub = _patch_service(monkeypatch)
        tenant = str(uuid_module.uuid4())
        monkeypatch.setenv("SISYS_TENANT_ID", tenant)
        exit_code = cli_main.main(["tool", "run", "--tool-id", str(uuid_module.uuid4()), "--input", "{}"])
        captured = capsys.readouterr()
        assert exit_code == 0, captured.err
        assert len(stub.execute_calls) == 1
        assert str(stub.execute_calls[0]["context"].tenant_id) == tenant, "env 通道租户未生效"

    def test_run_tenant_dual_channel_both_missing_242(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--tenant-id 与 SISYS_TENANT_ID 双缺 → 242 fail-loud（R1-F12——零锁定断言）。"""
        import uuid as uuid_module

        stub = _patch_service(monkeypatch)
        monkeypatch.delenv("SISYS_TENANT_ID", raising=False)
        exit_code = cli_main.main(["tool", "run", "--tool-id", str(uuid_module.uuid4()), "--input", "{}"])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "EXCEPTION_242" in captured.err, f"双缺应 242 fail-loud: {captured.err!r}"
        assert not stub.execute_calls

    def test_run_dry_run_action_semantics(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """--dry-run：工具名+入参回显+Schema 摘要+「将执行」语义（Task 3.7 钦定）。"""
        import uuid as uuid_module

        stub = _patch_service(monkeypatch)
        exit_code = cli_main.main(
            [
                "tool",
                "run",
                "--tool-id",
                str(uuid_module.uuid4()),
                "--input",
                '{"domain": "tech"}',
                "--tenant-id",
                str(uuid_module.uuid4()),
                "--dry-run",
            ]
        )
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "将执行" in captured.out, "dry-run 缺「将执行」动作语义"
        assert "domain" in captured.out, "dry-run 缺入参回显"
        assert not stub.execute_calls, "dry-run 零 service 调用失败"

    def test_run_mock_envelope(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """--mock：信封标记+参数回显。"""
        import uuid as uuid_module

        stub = _patch_service(monkeypatch)
        tool_id = str(uuid_module.uuid4())
        exit_code = cli_main.main(
            ["tool", "run", "--tool-id", tool_id, "--input", "{}", "--tenant-id", str(uuid_module.uuid4()), "--mock"]
        )
        captured = capsys.readouterr()
        assert exit_code == 0
        envelope = json.loads(captured.out)
        assert envelope["mock"] is True
        assert envelope["echo"]["tool_id"] == tool_id
        assert not stub.execute_calls
