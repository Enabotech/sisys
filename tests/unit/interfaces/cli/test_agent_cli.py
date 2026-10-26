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
from src.entrypoints import agent_cli


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

    def test_help_text_lists_all_registered_subcommands(self) -> None:
        """帮助文本漂移锁：六子命令名均出现于帮助输出（R2-F03——两代子命令
        加入未更新 description/epilog 的缺陷形态防复发；Story 5.6 扩展
        isolation-logs 第六子命令）。"""
        help_text = agent_cli.build_parser().format_help()
        for subcommand in (
            "instantiate",
            "load-profile",
            "run-task",
            "isolation-status",
            "set-isolation",
            "isolation-logs",
        ):
            assert subcommand in help_text, f"帮助文本缺少子命令 {subcommand}（description/epilog 漂移）"

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
        with caplog.at_level(logging.ERROR, logger="src.entrypoints.agent_cli"):
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


# ===================================================================
# Story 5-2 — load-profile 子命令（档案加载）
# ===================================================================


class _StubProfile:
    """档案 VO 替身（六字段对齐 AgentProfile）。"""

    def __init__(self) -> None:
        self.identity = "# IDENTITY\nCEO 战略方向最终决策高管协调"
        self.code_of_conduct = "# CODE\n证据优先角色隔离"
        self.soul = "# SOUL\n高管决策视角"
        self.user_preferences = "# USER\n结论先行"
        self.memory = "# MEMORY\n静态种子占位"
        self.heartbeat = "# HEARTBEAT\n每日频率占位"


class _StubLoadResult:
    """load-profile 用例结果替身（结构对齐 AgentProfileLoadResult）。"""

    def __init__(self) -> None:
        self.agent_id = uuid.uuid4()
        self.role = AgentRole.CEO
        self.profile = _StubProfile()
        self.tools_l1 = tuple(f"meta-{i}" for i in range(23))
        self.startup_context_tokens = 342


class _StubLoadUseCase:
    """load-profile 用例替身：记录 agent_id 并可编程抛异常。"""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[uuid.UUID] = []
        self.last_result: _StubLoadResult | None = None
        self._error = error

    async def execute(self, agent_id: uuid.UUID) -> _StubLoadResult:
        self.calls.append(agent_id)
        if self._error is not None:
            raise self._error
        self.last_result = _StubLoadResult()
        return self.last_result


class TestLoadProfileBuildParser:
    """load-profile 子命令参数契约。"""

    def test_load_profile_with_agent_id(self) -> None:
        agent_id = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
        args = agent_cli.build_parser().parse_args(["load-profile", "--agent-id", agent_id])
        assert args.command == "load-profile"
        assert args.agent_id == agent_id

    def test_agent_id_short_option(self) -> None:
        agent_id = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
        args = agent_cli.build_parser().parse_args(["load-profile", "-a", agent_id])
        assert args.agent_id == agent_id

    def test_agent_id_required(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["load-profile"])
        assert exc_info.value.code == 2


class TestAgentIdUuidGuard:
    """_parse_agent_uuid 守卫契约（红线：禁止裸 uuid.UUID 的 ValueError 逃逸）。"""

    def test_valid_uuid_accepted(self) -> None:
        agent_id = uuid.uuid4()
        assert agent_cli._parse_agent_uuid(str(agent_id)) == agent_id

    def test_padded_uuid_normalized(self) -> None:
        """带空白的 UUID 字符串剥离后成功。"""
        agent_id = uuid.uuid4()
        assert agent_cli._parse_agent_uuid(f"  {agent_id} ") == agent_id

    def test_invalid_string_maps_201_not_valueerror(self) -> None:
        """非法字符串 → ValidationError(201) 且 context 携带原始输入。"""
        from src.domain.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            agent_cli._parse_agent_uuid("not-a-uuid")
        assert exc_info.value.code == "EXCEPTION_201"
        assert exc_info.value.context.get("agent_id") == "not-a-uuid", "context 必须携带原始输入"

    def test_empty_string_maps_201(self) -> None:
        from src.domain.exceptions import ValidationError

        with pytest.raises(ValidationError):
            agent_cli._parse_agent_uuid("")

    def test_malformed_uuid_variants_all_mapped(self) -> None:
        """穷举常见非法形态，ValueError 必须全部被映射为 201。"""
        from src.domain.exceptions import ValidationError

        for raw in ("0f1e2d3c", "uuid", "0f1e2d3c-4b5a-6978-8796", "{}", "00000000-0000-0000-0000-00000000000g"):
            with pytest.raises(ValidationError):
                agent_cli._parse_agent_uuid(raw)


class TestLoadProfileMain:
    """load-profile main 路径：成功摘要输出 + 退出码契约。"""

    def test_success_outputs_summary(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """成功路径输出六档案逐项 OK + 活跃技能 + 启动上下文（多行人类可读摘要）。"""
        stub = _StubLoadUseCase()
        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)
        monkeypatch.setattr(agent_cli, "get_resolver", lambda: _StubResolver())
        exit_code = agent_cli.main(["load-profile", "--agent-id", str(uuid.uuid4())])
        assert exit_code == 0
        out = capsys.readouterr().out
        for file_label in ("IDENTITY.md", "CODE.md", "SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"):
            assert f"{file_label}: OK" in out, f"摘要应含 {file_label}: OK 行"
        assert "活跃技能: 23" in out, "摘要应含活跃技能数整行（整行锚定防子串误配——R1-F6）"
        assert "启动上下文: 342 tokens" in out, "摘要应含 token 计量整行"
        assert stub.last_result is not None

    def test_agent_not_found_exit_1_with_code(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """用例抛 AgentNotFoundError(443) → 退出码 1 且 stderr 含编码。"""
        from src.domain.exceptions import AgentNotFoundError

        stub = _StubLoadUseCase(error=AgentNotFoundError(agent_id=str(uuid.uuid4())))
        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)
        monkeypatch.setattr(agent_cli, "get_resolver", lambda: _StubResolver())
        exit_code = agent_cli.main(["load-profile", "--agent-id", str(uuid.uuid4())])
        assert exit_code == 1
        assert "EXCEPTION_443" in capsys.readouterr().err

    def test_profile_error_exit_1_with_code(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """用例抛 AgentProfileError(442) → 退出码 1 且 stderr 含编码。"""
        from src.domain.exceptions import AgentProfileError

        stub = _StubLoadUseCase(error=AgentProfileError(reason="档案文件缺失"))
        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)
        monkeypatch.setattr(agent_cli, "get_resolver", lambda: _StubResolver())
        exit_code = agent_cli.main(["load-profile", "--agent-id", str(uuid.uuid4())])
        assert exit_code == 1
        assert "EXCEPTION_442" in capsys.readouterr().err

    def test_invalid_uuid_cli_path_exit_1_with_201(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """main 路径非法 UUID 字符串 → 退出码 1 且 stderr 含 EXCEPTION_201（ValueError 不逃逸）。"""
        stub = _StubLoadUseCase()
        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)
        monkeypatch.setattr(agent_cli, "get_resolver", lambda: _StubResolver())
        exit_code = agent_cli.main(["load-profile", "--agent-id", "not-a-uuid"])
        assert exit_code == 1
        assert "EXCEPTION_201" in capsys.readouterr().err
        assert stub.calls == [], "UUID 守卫先于用例调用"


# ===================================================================
# Story 5-3 — run-task 子命令（六阶段工作流 CLI 全链）
# ===================================================================


class _StubWorkflowResult:
    """工作流用例结果替身（结构对齐 AgentWorkflowResult 五字段）。"""

    def __init__(self, status: str = "completed") -> None:
        import hashlib

        from src.domain.value_objects.chain_of_thought import ChainOfThought
        from src.domain.value_objects.task_evidence import TaskEvidencePackage

        self.workflow_status = status
        self.retry_count = 0 if status == "completed" else 2
        self.executed_phases = ("perceive", "plan", "execute", "verify", "package")
        self.evidence = TaskEvidencePackage(
            input_hash=hashlib.sha256("任务".encode()).hexdigest(),
            task_breakdown=("执行分析",),
            tool_trace=(),
            artifacts_snapshot=(),
            confidence=0.85,
            confidence_rationale="结构化检查通过",
            citations=(),
            status=status,
            failure_reason="" if status == "completed" else "第 3 次验证未通过",
        )
        self.chain = ChainOfThought(
            input_summary="任务摘要：战略分析",
            reflection="一次通过" if status == "completed" else "历经修正",
            tools_used=(),
            constraints_check="约束符合",
            final_answer='{"answer": "三层次建议"}',
        )


class _StubWorkflowUseCase:
    """工作流用例替身：记录调用并可编程抛异常。"""

    def __init__(self, error: Exception | None = None, status: str = "completed") -> None:
        self.calls: list[tuple[uuid.UUID, str]] = []
        self._error = error
        self._status = status

    async def execute(self, agent_id: uuid.UUID, task: str) -> _StubWorkflowResult:
        self.calls.append((agent_id, task))
        if self._error is not None:
            raise self._error
        return _StubWorkflowResult(status=self._status)


def _patch_run_task_entry(monkeypatch: pytest.MonkeyPatch, use_case: _StubWorkflowUseCase) -> None:
    """monkeypatch agent_cli 模块级属性（run-task 链路注入——同 _patch_entry 形态）。"""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
    monkeypatch.setattr(agent_cli, "resolve", lambda name: use_case)
    monkeypatch.setattr(agent_cli, "get_resolver", lambda: _StubResolver())


class TestRunTaskParser:
    """run-task 参数契约。"""

    def test_run_task_requires_agent_id_and_task(self) -> None:
        """--agent-id/-a 与 --task/-t 双必填（缺任一退出码 2）。"""
        parser = agent_cli.build_parser()
        args = parser.parse_args(["run-task", "--agent-id", str(uuid.uuid4()), "--task", "任务"])
        assert args.command == "run-task"
        args_short = parser.parse_args(["run-task", "-a", str(uuid.uuid4()), "-t", "任务"])
        assert args_short.command == "run-task"

    def test_run_task_missing_args_exit_two(self, capsys: pytest.CaptureFixture[str]) -> None:
        """缺 --task 时 argparse 用法错误退出码 2。"""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["run-task", "--agent-id", str(uuid.uuid4())])
        assert exc_info.value.code == 2


class TestRunTaskExecution:
    """run-task 执行契约（成功/失败完成态/守卫路径）。"""

    def test_success_outputs_summary_exit_zero(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """成功路径：exit 0 + 六阶段状态行 + 思维链预览 + 置信度 + 证据引用。"""
        use_case = _StubWorkflowUseCase(status="completed")
        _patch_run_task_entry(monkeypatch, use_case)
        agent_id = uuid.uuid4()

        exit_code = agent_cli.main(["run-task", "--agent-id", str(agent_id), "--task", "分析任务"])

        assert exit_code == 0
        assert use_case.calls == [(agent_id, "分析任务")]
        output = capsys.readouterr().out
        assert "perceive" in output and "package" in output, "六阶段状态行缺失"
        assert "<Reflection>" in output, "思维链五段预览缺失"
        assert "0.85" in output, "置信度输出缺失"

    def test_failed_completion_exit_zero_with_summary(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """失败完成态：exit 0（工作流正常走完语义）+ status=failed 摘要。"""
        use_case = _StubWorkflowUseCase(status="failed")
        _patch_run_task_entry(monkeypatch, use_case)

        exit_code = agent_cli.main(["run-task", "--agent-id", str(uuid.uuid4()), "--task", "任务"])

        assert exit_code == 0, "失败完成态是正常走完——与系统错误 exit 1 区分"
        output = capsys.readouterr().out
        assert "failed" in output, "失败状态摘要缺失"

    def test_agent_not_found_exit_one_with_code(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """443 守卫路径：exit 1 + stderr [EXCEPTION_443]。"""
        from src.domain.exceptions import AgentNotFoundError

        use_case = _StubWorkflowUseCase(error=AgentNotFoundError(agent_id=str(uuid.uuid4())))
        _patch_run_task_entry(monkeypatch, use_case)

        exit_code = agent_cli.main(["run-task", "--agent-id", str(uuid.uuid4()), "--task", "任务"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "EXCEPTION_443" in captured.err

    def test_role_not_supported_exit_one_with_code(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """441 守卫路径（R1-F12 补位——Story Task 6 钦定 443/441/444 三守卫）：
        exit 1 + stderr [EXCEPTION_441]。"""
        from src.domain.exceptions import AgentRoleNotSupportedError

        use_case = _StubWorkflowUseCase(error=AgentRoleNotSupportedError(role="CFO"))
        _patch_run_task_entry(monkeypatch, use_case)

        exit_code = agent_cli.main(["run-task", "--agent-id", str(uuid.uuid4()), "--task", "任务"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "EXCEPTION_441" in captured.err

    def test_workflow_error_exit_one_with_code(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """444 路径：exit 1 + stderr [EXCEPTION_444]（引擎 DomainError 透传链路）。"""
        from src.domain.exceptions.agent_exceptions import AgentWorkflowError

        use_case = _StubWorkflowUseCase(error=AgentWorkflowError(agent_id="a", phase="verify", reason="LLM 失败"))
        _patch_run_task_entry(monkeypatch, use_case)

        exit_code = agent_cli.main(["run-task", "--agent-id", str(uuid.uuid4()), "--task", "任务"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "EXCEPTION_444" in captured.err

    def test_invalid_uuid_guard_exit_one(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """UUID 守卫：非法 agent-id → 201 退出码 1（先于 bootstrap）。"""
        use_case = _StubWorkflowUseCase()
        _patch_run_task_entry(monkeypatch, use_case)

        exit_code = agent_cli.main(["run-task", "--agent-id", "not-a-uuid", "--task", "任务"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "EXCEPTION_201" in captured.err
        assert use_case.calls == [], "守卫失败不得触达用例"

    def test_bootstrap_idempotent_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """bootstrap 幂等守卫：registry 关键端口已存在即跳过重放（DC-12 ③前提）。"""
        bootstrap_calls = {"count": 0}
        original_bootstrap = agent_cli.bootstrap

        def _counting_bootstrap() -> None:
            bootstrap_calls["count"] += 1
            original_bootstrap()

        monkeypatch.setattr(agent_cli, "bootstrap", _counting_bootstrap)
        # conftest 已 bootstrap——本调用应被幂等守卫短路（count 不增）
        agent_cli._ensure_bootstrapped()
        assert bootstrap_calls["count"] == 0, "幂等守卫未生效（二次 bootstrap 必抛 ConflictError）"


# ===================================================================
# Story 5-4: isolation-status / set-isolation 子命令
# ===================================================================


class _StubIsolationState:
    """isolation-status 摘要输出所需状态属性面。"""

    def __init__(self, level: str = "L4", reason: str = "initial_default") -> None:
        from datetime import UTC, datetime

        from src.domain.events.enums import IsolationLevel

        self.agent_id = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
        self.current_level = IsolationLevel(level)  # 真实链路形态（枚举实例）
        self.initialized_at = datetime(2026, 10, 22, 8, 0, 0, tzinfo=UTC)
        self.updated_at = self.initialized_at
        self.last_trigger_reason = reason


class _StubSwitchedEvent:
    """切换事件属性面（previous_level 枚举形态——对齐真实 IsolationLevelSwitched）。"""

    def __init__(self, previous: str) -> None:
        from src.domain.events.enums import IsolationLevel

        self.previous_level = IsolationLevel(previous)


class _StubSwitchResult:
    """set-isolation 摘要输出所需结果属性面。"""

    def __init__(self, switched: bool, previous: str, target: str, reason: str) -> None:
        self.switched = switched
        self.state = _StubIsolationState(level=target, reason=reason)
        self.event = _StubSwitchedEvent(previous) if switched else None  # 真实链路: no-op 时 None


class _StubIsolationService:
    """isolation 两子命令共享 stub（get/switch 可注入错误）。"""

    def __init__(
        self,
        state: object | None = None,
        switch_result: object | None = None,
        error: Exception | None = None,
    ) -> None:
        self.state = state if state is not None else _StubIsolationState()
        self.switch_result = switch_result or _StubSwitchResult(True, "L4", "L3", "CLI 链路验证")
        self.error = error
        self.get_calls: list[str] = []
        self.switch_calls: list[tuple[str, str, str]] = []

    async def get_isolation_state(self, agent_id: object) -> object:
        self.get_calls.append(str(agent_id))
        if self.error is not None:
            raise self.error
        return self.state

    async def switch_isolation_level(
        self, agent_id: object, target_level: object, trigger_reason: str, approval_chain: object = ()
    ) -> object:
        self.switch_calls.append((str(agent_id), str(target_level), trigger_reason))
        if self.error is not None:
            raise self.error
        return self.switch_result


def _patch_isolation_entry(monkeypatch: pytest.MonkeyPatch, service: _StubIsolationService) -> None:
    """isolation 子命令三件套注入（bootstrap/resolve/get_resolver）。"""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
    monkeypatch.setattr(agent_cli, "resolve", lambda name: service)
    monkeypatch.setattr(agent_cli, "get_resolver", lambda: _StubResolver())


class TestSupportedIsolationLevelsConstant:
    """SUPPORTED_ISOLATION_LEVELS 常量双锁（显式元组 × MVP_ALLOWED_LEVELS 集合）。"""

    def test_explicit_tuple_form(self) -> None:
        """显式元组字面量（禁 frozenset 迭代派生——迭代序不稳定致帮助文本漂移）。"""
        assert agent_cli.SUPPORTED_ISOLATION_LEVELS == ("L4", "L3", "L2")

    def test_set_equals_mvp_allowed_levels(self) -> None:
        """与 MVP_ALLOWED_LEVELS 集合相等（V2 开放 L1 时仅改常量——双锁防漏改）。"""
        from src.domain.events.enums import IsolationLevel
        from src.domain.value_objects.isolation_policy import MVP_ALLOWED_LEVELS

        assert set(agent_cli.SUPPORTED_ISOLATION_LEVELS) == {level.value for level in MVP_ALLOWED_LEVELS}
        assert IsolationLevel.L1_FUSED.value not in agent_cli.SUPPORTED_ISOLATION_LEVELS


class TestParseIsolationLevelGuard:
    """_parse_isolation_level 两道守卫（顺序对齐 _parse_role 先例——R1-F07）。"""

    def test_valid_levels_parsed(self) -> None:
        from src.domain.events.enums import IsolationLevel

        assert agent_cli._parse_isolation_level("L4") is IsolationLevel.L4_HARD
        assert agent_cli._parse_isolation_level("L3") is IsolationLevel.L3_SOFT
        assert agent_cli._parse_isolation_level("L2") is IsolationLevel.L2_COLLAB

    @pytest.mark.parametrize("raw", ["L9", "l4", "xyz", ""])
    def test_invalid_string_raises_446(self, raw: str) -> None:
        """第一道: 非法枚举字符串 → 446（禁裸 IsolationLevel(value) ValueError 逃逸；
        大小写敏感——IsolationLevel 枚举值全大写，"l4" 属非法输入）。"""
        from src.domain.exceptions import IsolationLevelNotSupportedError

        with pytest.raises(IsolationLevelNotSupportedError) as exc_info:
            agent_cli._parse_isolation_level(raw)
        assert exc_info.value.code == "EXCEPTION_446"
        assert exc_info.value.context["level"] == raw
        assert exc_info.value.context["supported_levels"] == ["L4", "L3", "L2"]

    def test_l1_valid_enum_but_mvp_disabled_raises_446(self) -> None:
        """第二道: 合法枚举但未开放（L1 融合态）→ 446（统一异常出口非 argparse 拒绝）。"""
        from src.domain.exceptions import IsolationLevelNotSupportedError

        with pytest.raises(IsolationLevelNotSupportedError) as exc_info:
            agent_cli._parse_isolation_level("L1")
        assert exc_info.value.code == "EXCEPTION_446"


class TestIsolationStatusCommand:
    """isolation-status 子命令（查询与退出码契约）。"""

    def test_success_outputs_level_and_policy_dimensions(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """成功: exit 0 + 等级/名称 + 三维度策略 + isoformat 时间 + 原因。"""
        import re

        service = _StubIsolationService(state=_StubIsolationState(level="L4"))
        _patch_isolation_entry(monkeypatch, service)

        exit_code = agent_cli.main(["isolation-status", "--agent-id", "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "当前隔离等级: L4" in captured.out
        assert "硬隔离" in captured.out
        assert "read_only" in captured.out, "三维度策略须随状态输出"
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", captured.out), "时间须 isoformat 全格式"
        assert "initial_default" in captured.out

    @pytest.mark.parametrize(
        ("error_code", "error_cls_name"),
        [
            ("EXCEPTION_443", "AgentNotFoundError"),
            ("EXCEPTION_447", "IsolationStateNotInitializedError"),
            ("EXCEPTION_201", "ValidationError"),
        ],
        ids=["443", "447", "201"],
    )
    def test_guard_paths_exit_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        error_code: str,
        error_cls_name: str,
    ) -> None:
        """守卫路径: 443/447/201 → exit 1 + stderr 统一异常编码。"""
        import src.domain.exceptions as exceptions_module

        error_cls = getattr(exceptions_module, error_cls_name)
        error = error_cls() if error_cls_name == "ValidationError" else error_cls(agent_id="x")
        service = _StubIsolationService(error=error)
        _patch_isolation_entry(monkeypatch, service)

        exit_code = agent_cli.main(["isolation-status", "--agent-id", "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"])

        assert exit_code == 1
        assert error_code in capsys.readouterr().err


class TestSetIsolationCommand:
    """set-isolation 子命令（切换/no-op/退出码契约）。"""

    def test_success_outputs_switch_summary(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """成功: exit 0 + 切换摘要 previous -> target。"""
        from src.domain.events.enums import IsolationLevel

        service = _StubIsolationService(switch_result=_StubSwitchResult(True, "L4", "L3", "CLI 链路验证"))
        _patch_isolation_entry(monkeypatch, service)

        exit_code = agent_cli.main(
            [
                "set-isolation",
                "--agent-id",
                "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
                "--level",
                "L3",
                "--reason",
                "CLI 链路验证",
            ]
        )

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "L4 -> L3" in captured.out
        assert service.switch_calls, "服务 switch 必须被调用"
        assert service.switch_calls[0][1] == str(IsolationLevel.L3_SOFT)  # 枚举 str 混入形态

    def test_noop_outputs_hint_exit_zero(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """no-op: exit 0 + 未变更提示（幂等是正常态非错误）。"""
        service = _StubIsolationService(switch_result=_StubSwitchResult(False, "L4", "L4", "同等级重试"))
        _patch_isolation_entry(monkeypatch, service)

        exit_code = agent_cli.main(
            [
                "set-isolation",
                "--agent-id",
                "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
                "--level",
                "L4",
                "--reason",
                "同等级重试",
            ]
        )

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "no-op" in captured.out

    def test_invalid_level_string_l9_exit_one_446(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI 层非法字符串（L9）→ 446（守卫先于 bootstrap——统一异常出口）。"""
        service = _StubIsolationService()
        _patch_isolation_entry(monkeypatch, service)

        exit_code = agent_cli.main(
            [
                "set-isolation",
                "--agent-id",
                "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
                "--level",
                "L9",
                "--reason",
                "非法等级探测",
            ]
        )

        assert exit_code == 1
        assert "EXCEPTION_446" in capsys.readouterr().err
        assert service.switch_calls == [], "446 守卫不得触达服务"

    def test_l1_string_exit_one_446(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """CLI 层 L1（合法枚举未开放）→ 446（第二道预检）。"""
        service = _StubIsolationService()
        _patch_isolation_entry(monkeypatch, service)

        exit_code = agent_cli.main(
            [
                "set-isolation",
                "--agent-id",
                "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
                "--level",
                "L1",
                "--reason",
                "融合态探测",
            ]
        )

        assert exit_code == 1
        assert "EXCEPTION_446" in capsys.readouterr().err

    @pytest.mark.parametrize(
        ("error_code", "error_cls_name"),
        [
            ("EXCEPTION_443", "AgentNotFoundError"),
            ("EXCEPTION_447", "IsolationStateNotInitializedError"),
            ("EXCEPTION_201", "ValidationError"),
        ],
        ids=["443", "447", "201"],
    )
    def test_service_error_paths_exit_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        error_code: str,
        error_cls_name: str,
    ) -> None:
        """服务异常路径: 443/447/201 → exit 1 + stderr 编码。"""
        import src.domain.exceptions as exceptions_module

        error_cls = getattr(exceptions_module, error_cls_name)
        error = error_cls() if error_cls_name == "ValidationError" else error_cls(agent_id="x")
        service = _StubIsolationService(error=error)
        _patch_isolation_entry(monkeypatch, service)

        exit_code = agent_cli.main(
            [
                "set-isolation",
                "--agent-id",
                "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
                "--level",
                "L3",
                "--reason",
                "异常路径",
            ]
        )

        assert exit_code == 1
        assert error_code in capsys.readouterr().err


class TestIsolationSubcommandArgs:
    """两子命令参数契约（argparse 层）。"""

    def test_isolation_status_requires_agent_id(self) -> None:
        """--agent-id 必填（缺失 → argparse 用法错 exit 2）。"""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["isolation-status"])
        assert exc_info.value.code == 2

    def test_set_isolation_requires_all_three_args(self) -> None:
        """--agent-id/--level/--reason 三参数必填。"""
        with pytest.raises(SystemExit):
            agent_cli.build_parser().parse_args(["set-isolation", "--agent-id", "x"])
        with pytest.raises(SystemExit):
            agent_cli.build_parser().parse_args(["set-isolation", "--agent-id", "x", "--level", "L3"])


class _StubSwitchLog:
    """isolation-logs 摘要输出所需日志属性面（对齐真实 IsolationSwitchLog）。"""

    def __init__(self, previous: str = "L4", target: str = "L3", reason: str = "CLI 检索验证原因") -> None:
        import uuid
        from datetime import UTC, datetime

        from src.domain.events.enums import IsolationLevel

        self.log_id = uuid.UUID("0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")
        self.agent_id = uuid.UUID("0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0")
        self.previous_level = IsolationLevel(previous)
        self.target_level = IsolationLevel(target)
        self.trigger_reason = reason
        self.approval_chain = ("合规负责人",)
        self.switch_timestamp = datetime(2026, 10, 25, 10, 0, 0, tzinfo=UTC)
        self.worm_ref = None


class _StubLogSearchResult:
    """isolation-logs 检索结果属性面（items/total/offset）。"""

    def __init__(self, items: tuple, total: int, offset: int = 0) -> None:
        self.items = items
        self.total = total
        self.offset = offset


class _StubIsolationSwitchLogRepository:
    """isolation-logs 子命令 stub（search 可注入结果/异常；query 记录）。"""

    def __init__(
        self,
        result: object | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result if result is not None else _StubLogSearchResult((), 0)
        self.error = error
        self.search_calls: list[Any] = []

    async def save(self, log: object) -> None:
        return None

    async def search(self, query: object) -> object:
        self.search_calls.append(query)
        if self.error is not None:
            raise self.error
        return self.result


def _patch_isolation_logs_entry(monkeypatch: pytest.MonkeyPatch, repo: _StubIsolationSwitchLogRepository) -> None:
    """isolation-logs 三件套注入（bootstrap/resolve/get_resolver——resolve 统一返回 stub）。"""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
    monkeypatch.setattr(agent_cli, "resolve", lambda name: repo)
    monkeypatch.setattr(agent_cli, "get_resolver", lambda: _StubResolver())


class TestIsolationLogsCommand:
    """isolation-logs 子命令（Story 5.6——参数契约/守卫/输出形态）。"""

    def test_all_filter_args_parsed(self) -> None:
        """六过滤参数全量解析（--agent-id/--level/--start/--end/--limit/--offset）。"""
        args = agent_cli.build_parser().parse_args(
            [
                "isolation-logs",
                "--agent-id",
                "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
                "--level",
                "L3",
                "--start",
                "2026-10-25T00:00:00+00:00",
                "--end",
                "2026-10-26T00:00:00+00:00",
                "--limit",
                "10",
                "--offset",
                "5",
            ]
        )
        assert args.command == "isolation-logs"
        assert args.agent_id == "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
        assert args.level == "L3"
        assert args.start == "2026-10-25T00:00:00+00:00"
        assert args.end == "2026-10-26T00:00:00+00:00"
        assert args.limit == 10
        assert args.offset == 5

    def test_all_filter_args_optional(self) -> None:
        """六参数全可选（缺省全量检索——默认 limit 50 / offset 0）。"""
        args = agent_cli.build_parser().parse_args(["isolation-logs"])
        assert args.agent_id is None
        assert args.level is None
        assert args.start is None
        assert args.end is None
        assert args.limit == 50
        assert args.offset == 0

    def test_invalid_level_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
        """level 校验: 非法等级 → 446 退出码非 0 + 错误提示（CLI 层枚举转换守卫）。"""
        repo = _StubIsolationSwitchLogRepository()
        _patch_isolation_logs_entry(monkeypatch, repo)
        exit_code = agent_cli.main(["isolation-logs", "--level", "L9"])
        assert exit_code == 1
        assert "EXCEPTION_446" in capsys.readouterr().err
        assert repo.search_calls == []  # 守卫先于检索

    def test_naive_datetime_rejected(self, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
        """时间校验: 裸时间（无时区）→ 201 退出码非 0。"""
        repo = _StubIsolationSwitchLogRepository()
        _patch_isolation_logs_entry(monkeypatch, repo)
        exit_code = agent_cli.main(["isolation-logs", "--start", "2026-10-25T00:00:00"])
        assert exit_code == 1
        assert "EXCEPTION_201" in capsys.readouterr().err

    def test_success_outputs_summary_lines(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """有结果: exit 0 + 多行摘要（等级行/原因/审批链）+ 尾行总数。"""
        from src.domain.events.enums import IsolationLevel

        log = _StubSwitchLog()
        repo = _StubIsolationSwitchLogRepository(result=_StubLogSearchResult((log,), 1))
        _patch_isolation_logs_entry(monkeypatch, repo)
        exit_code = agent_cli.main(
            [
                "isolation-logs",
                "--agent-id",
                "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0",
                "--level",
                "L3",
            ]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "L4 -> L3" in captured.out
        assert "CLI 检索验证原因" in captured.out
        assert "合规负责人" in captured.out
        assert "共 1 条" in captured.out
        # 查询参数正确组装（agent_id UUID 化 + level 枚举化）
        query = repo.search_calls[0]
        assert query.level is IsolationLevel.L3_SOFT

    def test_empty_result_outputs_single_line(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """空结果: 「无隔离切换日志记录」单行 + exit 0。"""
        repo = _StubIsolationSwitchLogRepository(result=_StubLogSearchResult((), 0))
        _patch_isolation_logs_entry(monkeypatch, repo)
        exit_code = agent_cli.main(["isolation-logs"])
        assert exit_code == 0
        assert "无隔离切换日志记录" in capsys.readouterr().out

    def test_search_error_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """检索异常: StorageError → 103 退出码非 0。"""
        from src.domain.exceptions import StorageError

        repo = _StubIsolationSwitchLogRepository(error=StorageError("PG 不可达"))
        _patch_isolation_logs_entry(monkeypatch, repo)
        exit_code = agent_cli.main(["isolation-logs"])
        assert exit_code == 1
        assert "EXCEPTION_103" in capsys.readouterr().err

    def test_inverted_time_window_exits_nonzero(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """反转时间窗（start > end）→ Query 242 拒绝（R1-F21 传导链——
        Query 构造已上移 bootstrap 前，输入错误不触发端口注册表初始化）。"""
        repo = _StubIsolationSwitchLogRepository()
        _patch_isolation_logs_entry(monkeypatch, repo)
        exit_code = agent_cli.main(
            [
                "isolation-logs",
                "--start",
                "2026-10-26T00:00:00+00:00",
                "--end",
                "2026-10-25T00:00:00+00:00",
            ]
        )
        assert exit_code == 1
        assert "EXCEPTION_242" in capsys.readouterr().err
        assert repo.search_calls == []  # Query 守卫先于检索

    def test_zero_limit_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """limit=0 越界 → Query 242 拒绝（分页下限——CLI 传参面传导，
        Query 层守卫单测之外的组装面验证）。"""
        repo = _StubIsolationSwitchLogRepository()
        _patch_isolation_logs_entry(monkeypatch, repo)
        exit_code = agent_cli.main(["isolation-logs", "--limit", "0"])
        assert exit_code == 1
        assert "EXCEPTION_242" in capsys.readouterr().err
        assert repo.search_calls == []
