"""agent_cli 命令行单元测试（Story 5-1）

覆盖 sisys-agent CLI 入口：
- build_parser 参数契约：instantiate 子命令 + --role 必填 + add_subparsers
  required=True（裸调用退出码 2 且 stderr 含 usage——argparse 用法错，
  防漏 required 时取 args.role 抛 AttributeError 裸崩）
- 角色字符串守卫（红线）："ceo" 合法、"CEO" 大写归一化成功、
  "cfo"/"xyz" → AgentRoleNotSupportedError(441) 且 context 携带原始输入
  （禁止裸 AgentRole(value) 导致 ValueError 逃逸统一异常体系）
- main 成功路径：输出纯 UUID 单行 stdout、退出码 0（monkeypatch 模块级
  bootstrap/resolve 属性——项目无 Resolver override 公开 API，双 bootstrap
  抛 ConflictError，monkeypatch 是唯一可行注入）
- 业务异常路径：退出码 1 且 stderr 含 EXCEPTION_441（对齐 ocr_cli 0/1 先例）

Run with:
    poetry run pytest tests/unit/interfaces/cli/test_agent_cli.py -v
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import pytest

from src.domain.entities.agent import Agent, AgentRole
from src.domain.exceptions import AgentRoleNotSupportedError
from src.interfaces.cli import agent_cli


class _StubResult:
    """用例结果替身（结构对齐 AgentInstantiationResult）。"""

    def __init__(self) -> None:
        self.agent_id = uuid.uuid4()
        self.agent = Agent(agent_id=self.agent_id, role=AgentRole.CEO, name="CEO Agent")


class _StubUseCase:
    """用例替身：记录调用并可编程抛异常。"""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[AgentRole] = []
        self.last_result: _StubResult | None = None
        self._error = error

    async def execute(self, role: AgentRole) -> _StubResult:
        self.calls.append(role)
        if self._error is not None:
            raise self._error
        self.last_result = _StubResult()
        return self.last_result


class _StubResolver:
    """get_resolver 替身：peek_singleton 恒 None（Redis 池清理空转）。"""

    def peek_singleton(self, name: str) -> Any:
        return None


def _patch_entry(monkeypatch: pytest.MonkeyPatch, use_case: _StubUseCase) -> None:
    """monkeypatch agent_cli 模块级 bootstrap/resolve/get_resolver 属性。"""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
    monkeypatch.setattr(agent_cli, "resolve", lambda name: use_case)
    monkeypatch.setattr(agent_cli, "get_resolver", lambda: _StubResolver())


# ===================================================================
# build_parser 参数契约
# ===================================================================


class TestBuildParser:
    """parser 结构契约。"""

    def test_instantiate_with_role_ceo(self) -> None:
        args = agent_cli.build_parser().parse_args(["instantiate", "--role", "ceo"])
        assert args.command == "instantiate"
        assert args.role == "ceo"

    def test_role_short_option(self) -> None:
        args = agent_cli.build_parser().parse_args(["instantiate", "-r", "ceo"])
        assert args.role == "ceo"

    def test_role_required(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["instantiate"])
        assert exc_info.value.code == 2

    def test_bare_invocation_usage_error_exit_2(self, capsys: pytest.CaptureFixture[str]) -> None:
        """裸调用（无子命令）→ SystemExit 2 且 stderr 含 usage。

        add_subparsers 必设 required=True：默认可选时裸调用会走到取
        args.role 抛 AttributeError 裸崩（逃逸统一异常体系）。
        """
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.main([])
        assert exc_info.value.code == 2
        assert "usage" in capsys.readouterr().err.lower()

    def test_unknown_subcommand_exit_2(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["destroy", "--role", "ceo"])
        assert exc_info.value.code == 2


# ===================================================================
# 角色字符串守卫（红线：禁止 ValueError 逃逸）
# ===================================================================


class TestRoleStringGuard:
    """_parse_role 守卫契约。"""

    def test_lowercase_ceo_valid(self) -> None:
        assert agent_cli._parse_role("ceo") is AgentRole.CEO

    def test_uppercase_ceo_normalized(self) -> None:
        """大写归一化（.lower() 防漏——漏写时合法输入误报 441）。"""
        assert agent_cli._parse_role("CEO") is AgentRole.CEO

    def test_whitespace_stripped(self) -> None:
        assert agent_cli._parse_role("  ceo ") is AgentRole.CEO

    def test_cfo_is_valid_enum_but_unsupported(self) -> None:
        """cfo 是合法枚举值——字符串层拦不住，必须映射 441（用例层守卫的 CLI 预检）。"""
        with pytest.raises(AgentRoleNotSupportedError) as exc_info:
            agent_cli._parse_role("cfo")
        assert exc_info.value.code == "EXCEPTION_441"

    def test_invalid_string_maps_441_not_valueerror(self) -> None:
        """非法字符串 → 441（禁止裸 AgentRole(value) 的 ValueError 逃逸）。"""
        with pytest.raises(AgentRoleNotSupportedError) as exc_info:
            agent_cli._parse_role("xyz")
        assert exc_info.value.code == "EXCEPTION_441"
        assert exc_info.value.context["role"] == "xyz", "context 必须携带原始输入字符串"
        assert exc_info.value.context["supported_roles"] == ["ceo"]

    def test_no_valueerror_leaks_from_parse_role(self) -> None:
        """穷举常见非法输入形态，ValueError 必须全部被映射。"""
        for raw in ("", "  ", "战略决策者", "agent", "441", "-r"):
            with pytest.raises(AgentRoleNotSupportedError):
                agent_cli._parse_role(raw)

    def test_padded_uppercase_normalizes(self) -> None:
        """带空白的大写形态归一化为合法角色。"""
        assert agent_cli._parse_role("CEO ") is AgentRole.CEO


# ===================================================================
# main 成功路径（monkeypatch 注入）
# ===================================================================


class TestMainSuccess:
    """main(argv) 成功路径：UUID 单行 stdout + 退出码 0。"""

    def test_outputs_pure_uuid_single_line(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        stub = _StubUseCase()
        _patch_entry(monkeypatch, stub)
        exit_code = agent_cli.main(["instantiate", "--role", "ceo"])
        assert exit_code == 0
        out = capsys.readouterr().out
        lines = [line for line in out.splitlines() if line.strip()]
        assert len(lines) == 1, f"stdout 应为纯 UUID 单行: {out!r}"
        assert stub.last_result is not None
        assert uuid.UUID(lines[0]) == stub.last_result.agent_id
        assert stub.calls == [AgentRole.CEO]

    def test_uppercase_role_argument_accepted(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--role CEO（大写）经归一化成功实例化。"""
        stub = _StubUseCase()
        _patch_entry(monkeypatch, stub)
        assert agent_cli.main(["instantiate", "--role", "CEO"]) == 0
        assert stub.calls == [AgentRole.CEO]


# ===================================================================
# main 业务异常路径（退出码 1 + 统一异常体系输出）
# ===================================================================


class TestMainErrorPaths:
    """业务异常 → 退出码 1 且 stderr 含错误码。"""

    def test_unsupported_role_exit_1_with_code(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stub = _StubUseCase()
        _patch_entry(monkeypatch, stub)
        exit_code = agent_cli.main(["instantiate", "--role", "cfo"])
        assert exit_code == 1
        assert "EXCEPTION_441" in capsys.readouterr().err

    def test_invalid_string_exit_1_with_code(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        stub = _StubUseCase()
        _patch_entry(monkeypatch, stub)
        assert agent_cli.main(["instantiate", "--role", "xyz"]) == 1
        assert "EXCEPTION_441" in capsys.readouterr().err

    def test_use_case_domain_error_exit_1(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """用例抛领域异常（如配置缺失 440）→ 退出码 1 且 stderr 含编码。"""
        from src.domain.exceptions import AgentConfigError

        stub = _StubUseCase(error=AgentConfigError(role="ceo", reason="配置文件不存在"))
        _patch_entry(monkeypatch, stub)
        assert agent_cli.main(["instantiate", "--role", "ceo"]) == 1
        assert "EXCEPTION_440" in capsys.readouterr().err

    def test_use_case_calls_only_after_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """441 路径用例未被调用（守卫先于 resolve/execute）。"""
        stub = _StubUseCase()
        _patch_entry(monkeypatch, stub)
        agent_cli.main(["instantiate", "--role", "cfo"])
        assert stub.calls == []


# ===================================================================
# bootstrap/清理路径健壮性（统一退出码契约 + finally 防御）
# ===================================================================


class TestBootstrapAndCleanupRobustness:
    """bootstrap 失败统一退出码 + 关池失败不反噬主结果。"""

    def test_bootstrap_failure_exit_1(self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        """bootstrap 抛异常 → 退出码 1 + 错误日志记录（禁裸 traceback 逃逸统一退出码契约）。

        该路径经 logger.error 输出（生产环境 stderr；pytest 下经 caplog 断言——
        捕获插件接管 root logger 后 capsys 不可见）。
        """

        def _boom() -> None:
            raise RuntimeError("composition root broken")

        monkeypatch.setattr(agent_cli, "bootstrap", _boom)
        monkeypatch.setattr(agent_cli, "resolve", lambda name: _StubUseCase())
        monkeypatch.setattr(agent_cli, "get_resolver", lambda: _StubResolver())
        with caplog.at_level(logging.ERROR, logger="src.interfaces.cli.agent_cli"):
            exit_code = agent_cli.main(["instantiate", "--role", "ceo"])
        assert exit_code == 1
        assert "composition root broken" in caplog.text

    def test_close_pool_failure_does_not_mask_success(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Redis 池关闭失败不得反噬实例化成功结果（finally 防御——记 warning 返回 0）。"""
        stub = _StubUseCase()

        class _FailingManager:
            async def close(self) -> None:
                raise TimeoutError("close timeout")

        class _StubResolverWithManager:
            def peek_singleton(self, name: str) -> Any:
                return _FailingManager()

        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)
        monkeypatch.setattr(agent_cli, "get_resolver", lambda: _StubResolverWithManager())
        exit_code = agent_cli.main(["instantiate", "--role", "ceo"])
        assert exit_code == 0, "关池失败不得反噬成功结果"
        assert stub.last_result is not None
        assert uuid.UUID(capsys.readouterr().out.strip()) == stub.last_result.agent_id
