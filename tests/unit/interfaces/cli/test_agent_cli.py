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

    def test_resolve_failure_still_closes_pools(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """resolve 抛出时 finally 关池仍执行（代码审查 R1-F17/G8——连接池不泄漏绑死 loop）。

        修复前异步壳的 resolve 在 try 之外——注册名漂移等 resolve 失败会跳过
        finally 的 _close_connection_pools；修复后 resolve 入 try，同 loop 收口。
        """

        def _boom_resolve(name: str) -> Any:
            raise RuntimeError("registry drift")

        close_calls: list[int] = []

        async def _spy_close() -> None:
            close_calls.append(1)

        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", _boom_resolve)
        monkeypatch.setattr(agent_cli, "_close_connection_pools", _spy_close)
        with caplog.at_level(logging.ERROR, logger="src.entrypoints.agent_cli"):
            exit_code = agent_cli.main(["checkpoint-list", "--plan-id", str(uuid.uuid4())])
        assert exit_code == 1
        assert close_calls, "resolve 抛出后 finally 关池仍须执行（R1-F17 修复锚）"
        assert "registry drift" in caplog.text


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
        """反转时间窗（start > end）→ Query 242 拒绝（R1-F20 传导链——
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


# ===================================================================
# Story 6-1: blm-plan 子命令（BLM 前两阶段规划——argparse 进程内直调先例）
# ===================================================================


class _StubGapArtifacts:
    """阶段 1 产物替身（四字段——getattr 摘要输出面）。"""

    financial_gap = "财务差距量化：达成率 82%"
    operational_gap = "运营差距：交付周期延长"
    root_causes = ("价格竞争侵蚀毛利", "供应链成本上升")
    portfolio_health = "核心业务稳健，新兴业务双低"
    degraded = False
    degrade_reason = ""


class _StubSynthesis:
    """综合洞察替身。"""

    conclusions = ("优先补强内部能力", "把握海外机会窗口")
    degraded_inputs = ()


class _StubBlmPlanningResult:
    """BLM 规划结果 DTO 替身（_print_blm_progress getattr 消费面）。"""

    def __init__(self, *, plan_id: str, degraded_steps: tuple[str, ...] = ()) -> None:
        self.plan_id = plan_id
        self.agent_id = uuid.uuid4()
        self.gap_artifacts = _StubGapArtifacts()
        self.insight_steps = ()
        self.synthesis = _StubSynthesis()
        self.degraded_steps = degraded_steps
        self.execution_ms = 1234


class _StubBlmPlanningUseCase:
    """BLM 规划用例替身（calls 记录 + 可编程异常）。"""

    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, str, str | None]] = []
        self.error: Exception | None = None
        self.result_override: _StubBlmPlanningResult | None = None
        self.last_result: _StubBlmPlanningResult | None = None

    async def execute(self, agent_id: uuid.UUID, task: str, plan_id: str | None = None) -> _StubBlmPlanningResult:
        self.calls.append((agent_id, task, plan_id))
        if self.error is not None:
            raise self.error
        if self.result_override is not None:
            self.last_result = self.result_override
            return self.last_result
        self.last_result = _StubBlmPlanningResult(plan_id=plan_id or str(uuid.uuid4()))
        return self.last_result


def _patch_blm_plan_entry(monkeypatch: pytest.MonkeyPatch, use_case: _StubBlmPlanningUseCase) -> None:
    """blm-plan 入口注入（bootstrap/resolve/get_resolver 三件套替身）。"""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
    monkeypatch.setattr(agent_cli, "resolve", lambda name: use_case)
    monkeypatch.setattr(agent_cli, "get_resolver", lambda: _StubResolver())


class TestBlmPlanParser:
    """blm-plan 子命令解析（参数面——type=str 纪律）。"""

    def test_blm_plan_requires_agent_and_task(self) -> None:
        """-a/-t 双必填（缺一 usage error exit 2）。"""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["blm-plan"])
        assert exc_info.value.code == 2

    def test_blm_plan_short_options(self) -> None:
        """短选项形态（-a/-t——run-task 先例）。"""
        args = agent_cli.build_parser().parse_args(["blm-plan", "-a", str(uuid.uuid4()), "-t", "五年战略规划"])
        assert args.command == "blm-plan"
        assert args.agent_id and args.task == "五年战略规划"
        assert args.plan_id is None

    def test_blm_plan_optional_plan_id(self) -> None:
        """--plan-id 可选透传（恢复/幂等锚）。"""
        args = agent_cli.build_parser().parse_args(["blm-plan", "-a", str(uuid.uuid4()), "-t", "任务", "--plan-id", "plan-42"])
        assert args.plan_id == "plan-42"


class TestBlmPlanExecution:
    """blm-plan 执行链（守卫/摘要输出/退出语义）。"""

    def test_success_outputs_progress_and_plan_id(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """成功：exit 0 + 进度摘要输出（_print_blm_progress——进度/降级/耗时）。"""
        stub = _StubBlmPlanningUseCase()
        _patch_blm_plan_entry(monkeypatch, stub)
        agent_id = uuid.uuid4()
        exit_code = agent_cli.main(["blm-plan", "-a", str(agent_id), "-t", "五年战略规划"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "规划" in out
        assert "子步骤完成" in out, "进度行缺失（进度摘要输出断言——R1-9①）"
        assert stub.last_result is not None and stub.last_result.plan_id in out
        assert stub.calls == [(agent_id, "五年战略规划", None)]

    def test_invalid_agent_uuid_guards_before_bootstrap(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """非法 UUID → 201 先于 bootstrap（use_case 零调用——argparse type= 纪律）。"""
        stub = _StubBlmPlanningUseCase()
        _patch_blm_plan_entry(monkeypatch, stub)
        exit_code = agent_cli.main(["blm-plan", "-a", "not-a-uuid", "-t", "任务"])
        assert exit_code == 1
        assert "EXCEPTION_201" in capsys.readouterr().err
        assert stub.calls == []

    def test_domain_error_exits_one(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """业务异常（481 全降级）→ exit 1 + stderr 编码。"""
        from src.domain.exceptions.planning_exceptions import PlanningExecutionError

        stub = _StubBlmPlanningUseCase()
        stub.error = PlanningExecutionError(agent_id="a", plan_id="p", reason="全部 8 步降级")
        _patch_blm_plan_entry(monkeypatch, stub)
        exit_code = agent_cli.main(["blm-plan", "-a", str(uuid.uuid4()), "-t", "任务"])
        assert exit_code == 1
        assert "EXCEPTION_481" in capsys.readouterr().err

    def test_degraded_flow_marks_output(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """部分降级成功 → 摘要含降级标记（降级可见性——AC-6③）。"""
        stub = _StubBlmPlanningUseCase()
        _patch_blm_plan_entry(monkeypatch, stub)
        stub.result_override = _StubBlmPlanningResult(plan_id="plan-d", degraded_steps=("trend",))
        exit_code = agent_cli.main(["blm-plan", "-a", str(uuid.uuid4()), "-t", "任务"])
        assert exit_code == 0
        assert "降级" in capsys.readouterr().out

    def test_plan_id_passthrough(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """--plan-id 透传到用例（execute 第三参数）。"""
        stub = _StubBlmPlanningUseCase()
        _patch_blm_plan_entry(monkeypatch, stub)
        agent_id = uuid.uuid4()
        agent_cli.main(["blm-plan", "-a", str(agent_id), "-t", "任务", "--plan-id", "plan-77"])
        assert stub.calls[0][2] == "plan-77"


# ===================================================================
# Story 6-3: checkpoint-create 子命令（扁平子命令——R2-F18 钦定 argparse 形态）
# ===================================================================


class _StubCheckpointSnapshot:
    """Checkpoint 快照替身（_print_checkpoint_result getattr 消费面）。"""

    def __init__(self, *, plan_id: str, checkpoint_no: str = "CP-1") -> None:
        self.snapshot_id = uuid.uuid4()
        self.session_id = f"blm-checkpoint-{plan_id}:{checkpoint_no}"
        self.checkpoint_no = checkpoint_no
        self.stage_id = "performance_gap"
        self.state_version = 0
        self.state_data = {"created_via": "cli"}


class _StubCheckpointUseCase:
    """Checkpoint 创建用例替身（calls 记录 + 可编程异常）。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None

    async def execute(self, **kwargs) -> _StubCheckpointSnapshot:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return _StubCheckpointSnapshot(plan_id=kwargs["plan_id"], checkpoint_no=kwargs["checkpoint_no"])


def _patch_checkpoint_create_entry(monkeypatch: pytest.MonkeyPatch, use_case: _StubCheckpointUseCase) -> None:
    """checkpoint-create 入口注入（bootstrap/resolve 三件套替身——blm-plan 先例）。"""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
    monkeypatch.setattr(agent_cli, "resolve", lambda name: use_case)


class TestCheckpointCreateParser:
    """checkpoint-create 子命令解析（六参数面 + BooleanOptionalAction）。"""

    def test_checkpoint_create_requires_core_params(self) -> None:
        """必填参数缺失 usage error exit 2（--plan-id/--checkpoint-no/--stage-id/--query/--user-id/--summary）。"""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["checkpoint-create"])
        assert exc_info.value.code == 2

    def test_checkpoint_create_full_arguments(self) -> None:
        """全参数解析（含 --completed/--no-completed 双旗标——R6-21 BooleanOptionalAction）。"""
        args = agent_cli.build_parser().parse_args(
            [
                "checkpoint-create",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-1",
                "--stage-id",
                "performance_gap",
                "--query",
                "五年战略规划",
                "--user-id",
                "exec-001",
                "--summary",
                "阶段摘要",
            ]
        )
        assert args.command == "checkpoint-create"
        assert args.completed is True  # 默认 True（R6-21——裸 store_true 默认 False 不符钦定）

        args_no = agent_cli.build_parser().parse_args(
            [
                "checkpoint-create",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-1",
                "--stage-id",
                "performance_gap",
                "--query",
                "q",
                "--user-id",
                "u",
                "--summary",
                "s",
                "--no-completed",
            ]
        )
        assert args_no.completed is False

    def test_checkpoint_create_no_created_via_flag(self) -> None:
        """CLI 入口不暴露 created_via 参数（硬编码传 "cli"——R6-4）。"""
        with pytest.raises(SystemExit):
            agent_cli.build_parser().parse_args(["checkpoint-create", "--plan-id", str(uuid.uuid4()), "--created-via", "cli"])


class TestCheckpointCreateExecution:
    """checkpoint-create 执行（五步定式——_run_blm_plan_cli 先例）。"""

    def test_success_exit_0_with_checkpoint_no_output(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """成功路径：exit 0 + 输出含 checkpoint_no + created_via 硬编码 "cli"。"""
        stub = _StubCheckpointUseCase()
        _patch_checkpoint_create_entry(monkeypatch, stub)
        plan_id = str(uuid.uuid4())

        exit_code = agent_cli.main(
            [
                "checkpoint-create",
                "--plan-id",
                plan_id,
                "--checkpoint-no",
                "CP-1",
                "--stage-id",
                "performance_gap",
                "--query",
                "五年战略规划",
                "--user-id",
                "exec-001",
                "--summary",
                "阶段摘要",
            ]
        )

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "checkpoint_no" in out, "输出缺 checkpoint_no 标签（进度摘要断言——标签锚防漂移）"
        assert "CP-1" in out, "输出缺 checkpoint 编号值"
        assert stub.calls, "用例未被调用"
        assert stub.calls[0]["created_via"] == "cli"  # 硬编码传值（R6-4）
        assert stub.calls[0]["retrieved_docs"] == []  # argparse 不接收检索证据（空列表构造）

    def test_business_exception_exit_1(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """业务异常路径：DomainError → exit 1 + stderr 含 code（五步定式）。"""
        from src.domain.exceptions import CheckpointCreationError

        stub = _StubCheckpointUseCase()
        stub.error = CheckpointCreationError(plan_id="p", checkpoint_no="CP-1", reason="归档失败")
        _patch_checkpoint_create_entry(monkeypatch, stub)

        exit_code = agent_cli.main(
            [
                "checkpoint-create",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-1",
                "--stage-id",
                "performance_gap",
                "--query",
                "q",
                "--user-id",
                "u",
                "--summary",
                "s",
            ]
        )

        assert exit_code == 1
        stderr = capsys.readouterr().err
        assert "EXCEPTION_483" in stderr
        # R1 审查 FR-3：message 组合 reason 后 CLI 人机面可见根因（原静态文案掩蔽）
        assert "归档失败" in stderr, f"stderr 缺 reason 根因（实测={stderr!r}）"

    def test_invalid_plan_id_exit_1_before_bootstrap(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """plan_id 非 UUID：守卫先于 bootstrap（UUID 解析失败 exit 1）。"""
        stub = _StubCheckpointUseCase()
        _patch_checkpoint_create_entry(monkeypatch, stub)

        exit_code = agent_cli.main(
            [
                "checkpoint-create",
                "--plan-id",
                "not-a-uuid",
                "--checkpoint-no",
                "CP-1",
                "--stage-id",
                "performance_gap",
                "--query",
                "q",
                "--user-id",
                "u",
                "--summary",
                "s",
            ]
        )

        assert exit_code == 1
        assert not stub.calls, "守卫失败后不得触达用例"
        # R1 审查 FR-18：守卫错误走真实 EntityValidationError 的 [code] 统一形态
        assert "[EXCEPTION_242]" in capsys.readouterr().err

    def test_success_exit_0(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """成功路径 exit 0（R3-D：exit 0 判据=快照落库成功）。

        R1 审查 FR-12 改名注记：本用例未构造发布降态（CLI 层物理不可观测——
        发布降级在服务层吸收）；降级语义的真测在服务单测
        test_publish_failure_does_not_rollback_snapshot（R6-25 原登记维持）。
        """
        stub = _StubCheckpointUseCase()
        _patch_checkpoint_create_entry(monkeypatch, stub)

        exit_code = agent_cli.main(
            [
                "checkpoint-create",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-1",
                "--stage-id",
                "performance_gap",
                "--query",
                "q",
                "--user-id",
                "u",
                "--summary",
                "s",
            ]
        )

        assert exit_code == 0  # 用例成功即 exit 0（服务层发布降级已被吸收）


# ===================================================================
# Story 6-4：chain-query 子命令（决策追溯查询 CLI 入口）
# ===================================================================


class _StubChainTraceView:
    """追溯视图替身（total/records 属性访问面——_StubResult 先例形态）。"""

    def __init__(self, *, records: list | None = None, total: int = 0) -> None:
        self.records = records or []
        self.total = total


class _StubChainTraceUseCase:
    """追溯查询用例替身（calls 记录 + 可编程异常）。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.view = _StubChainTraceView()

    async def execute(self, **kwargs) -> _StubChainTraceView:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.view


def _patch_chain_query_entry(monkeypatch: pytest.MonkeyPatch, use_case: _StubChainTraceUseCase) -> None:
    """chain-query 入口注入（bootstrap/resolve 三件套替身——checkpoint-create 先例）。"""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
    monkeypatch.setattr(agent_cli, "resolve", lambda name: use_case)


class TestChainQueryParser:
    """chain-query 子命令解析（--plan-id 必填 + --include-blob 旗标）。"""

    def test_chain_query_requires_plan_id(self) -> None:
        """必填参数缺失 usage error exit 2。"""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["chain-query"])
        assert exc_info.value.code == 2

    def test_chain_query_full_arguments(self) -> None:
        """全参数解析（--include-blob 默认 False 开启 True）。"""
        args = agent_cli.build_parser().parse_args(["chain-query", "--plan-id", str(uuid.uuid4()), "--include-blob"])
        assert args.command == "chain-query"
        assert args.include_blob is True

    def test_chain_query_include_blob_defaults_false(self) -> None:
        """--include-blob 缺省 False（默认读 L2 决策依据足够）。"""
        args = agent_cli.build_parser().parse_args(["chain-query", "--plan-id", str(uuid.uuid4())])
        assert args.include_blob is False


class TestChainQueryExecution:
    """chain-query 执行（正常输出/空清单/非法 plan_id 242/意外异常兜底）。"""

    def test_success_output_contains_display_and_archive_count(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """成功路径：exit 0 + 每条 to_display 五段形态 + 归档计数行。"""
        from src.application.ports.chain_of_thought_archive import StepChainMaterial
        from src.application.services.chain_of_thought_archive_service import compose_step_chain

        material = StepChainMaterial(
            stage="market_insight_trend",
            display_name="看趋势",
            role_prefix="以 CEO 宏观趋势判断与 CTO 技术趋势分析的双重视角",
            task="制定新能源汽车行业五年战略规划",
            evidence_count=5,
            tool_slug="PESTEL 分析",
            summary="市场洞察产物",
            findings_count=2,
            payload={"summary": "市场洞察产物"},
        )
        record = {
            "stage": "market_insight_trend",
            "chain": compose_step_chain(material),
            "archive_id": "arch-1",
            "degraded": False,
            "blob_content": None,
        }
        stub = _StubChainTraceUseCase()
        stub.view = _StubChainTraceView(records=[record], total=1)
        _patch_chain_query_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["chain-query", "--plan-id", str(uuid.uuid4())])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "<Reflection>" in out and "</Reflection>" in out, "输出缺五段展示形态（DC-2 展示用标签）"
        assert "<Tools_Used>" in out and "<Constraints_Check>" in out
        assert "market_insight_trend" in out
        assert stub.calls, "用例未被调用"
        assert stub.calls[0]["include_blob"] is False  # 默认 False 透传

    def test_empty_trace_exit_0_with_empty_marker(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """空清单：exit 0 + total=0（查询面幂等读——非异常路径）。"""
        stub = _StubChainTraceUseCase()
        stub.view = _StubChainTraceView(records=[], total=0)
        _patch_chain_query_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["chain-query", "--plan-id", str(uuid.uuid4())])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "共 0 条思维链档案" in out  # total=0 精确可见（CR1-F9——裸 "0" 子串判别力弱）

    def test_unexpected_exception_exit_1_logged(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """意外异常兜底（CR2-F1）：RuntimeError 透传 → exit 1 + logger.error 带
        堆栈（对齐 blm-plan/checkpoint-create 双层五步定式——异常逃逸则 main
        直接 raise 本测试以 error 失败，exit 1 即「非 traceback 逃逸」证明）。"""
        stub = _StubChainTraceUseCase()
        stub.error = RuntimeError("检索链路意外故障（注入）")
        _patch_chain_query_entry(monkeypatch, stub)

        with caplog.at_level(logging.ERROR, logger="src.entrypoints.agent_cli"):
            exit_code = agent_cli.main(["chain-query", "--plan-id", str(uuid.uuid4())])

        assert exit_code == 1
        assert "决策追溯查询异常" in caplog.text
        assert caplog.records[-1].exc_info is not None  # exc_info 带堆栈形态钉死

    def test_invalid_plan_id_exit_1_stderr_242(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """非法 plan_id：exit 1 + stderr [EXCEPTION_242]（守卫构造真实异常）。"""
        stub = _StubChainTraceUseCase()
        from src.domain.exceptions import EntityValidationError

        stub.error = EntityValidationError(
            message="plan_id 必须为 UUID 字符串",
            context={"use_case": "GetBlmChainTraceUseCase", "field": "plan_id"},
        )
        _patch_chain_query_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["chain-query", "--plan-id", "not-a-uuid"])

        assert exit_code == 1
        stderr = capsys.readouterr().err
        assert "[EXCEPTION_242]" in stderr


class TestBlmPlanChainSummaryLine:
    """blm-plan 汇总行三段式（R2-F8——成功 N/失败 M/预期 8）。"""

    def test_progress_prints_three_segment_chain_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        """_print_blm_progress 尾部思维链计数行（三段式口径）。"""
        from src.application.ports.blm_planning import BlmPlanningResult
        from src.application.ports.chain_of_thought_archive import ChainRecord
        from src.domain.value_objects.blm_phases import InsightSynthesis, PerformanceGapArtifacts

        def _record(stage: str, archived: bool) -> ChainRecord:
            from src.domain.value_objects.chain_of_thought import ChainOfThought

            return ChainRecord(
                stage=stage,
                chain=ChainOfThought(
                    input_summary=f"input-{stage}",
                    reflection="reflection",
                    tools_used=(),
                    constraints_check="constraints",
                    final_answer='{"stage": "x"}',
                ),
                archived=archived,
                archive_id="a" if archived else "",
            )

        result = BlmPlanningResult(
            plan_id="plan-1",
            agent_id=uuid.uuid4(),
            gap_artifacts=PerformanceGapArtifacts(financial_gap="f", operational_gap="o", root_causes=(), portfolio_health="p"),
            insight_steps=(),
            synthesis=InsightSynthesis(conclusions=("c1",)),
            degraded_steps=(),
            execution_ms=10,
            chain_records=(
                _record("performance_gap", True),
                _record("market_insight_trend", False),
            ),
        )
        agent_cli._print_blm_progress(result)
        out = capsys.readouterr().out
        assert "思维链归档" in out, "缺思维链归档汇总行（零静默吞错——AC-4 可见性）"
        assert "成功 1/失败 1/预期 8" in out, f"三段式口径漂移（实测输出={out!r}）"

    def test_progress_without_chain_records_omits_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        """chain_records 空（尾参未注入）不打印汇总行（旧形态零破坏）。"""
        from src.application.ports.blm_planning import BlmPlanningResult
        from src.domain.value_objects.blm_phases import PerformanceGapArtifacts

        result = BlmPlanningResult(
            plan_id="plan-1",
            agent_id=uuid.uuid4(),
            gap_artifacts=PerformanceGapArtifacts(financial_gap="f", operational_gap="o", root_causes=(), portfolio_health="p"),
        )
        agent_cli._print_blm_progress(result)
        out = capsys.readouterr().out
        assert "思维链归档" not in out, "chain_records 空时不应打印汇总行"


# ======================================================================
# Story 6-5a: report-generate 子命令（Markdown 报告生成 CLI 入口）
# ======================================================================


class _StubStrategicReport:
    """StrategicReport 属性面替身（report_id/file_path/section_count 等）。"""

    def __init__(self) -> None:
        """初始化替身（getattr 打印面消费字段——CR1-F9：report_type 用真实枚举防形态掩蔽）。"""
        import uuid as _uuid

        from src.domain.entities.strategic_report import ReportType

        self.report_id = _uuid.uuid4()
        self.plan_id = "plan-1"
        self.report_type = ReportType.MARKDOWN  # 真实枚举成员（CLI 打印取 .value——裸 str 替身会掩蔽 repr 形态缺陷）
        self.file_path = "reports/plan-1_20261103120000.md"
        self.section_count = 11
        self.degraded_section_count = 0
        self.generation_ms = 120


class _StubReportGenerateUseCase:
    """report_generation_use_case 替身（calls 记录 + 可注入 error）。"""

    def __init__(self) -> None:
        """初始化替身。"""
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.result = _StubStrategicReport()

    async def execute(self, *, plan_id: str) -> object:
        """替身 execute（记录调用）。"""
        self.calls.append({"plan_id": plan_id})
        if self.error is not None:
            raise self.error
        return self.result


def _patch_report_generate_entry(monkeypatch: pytest.MonkeyPatch, use_case: _StubReportGenerateUseCase) -> None:
    """CLI 入口替身注入（bootstrap/resolve 拦截——chain-query 精简版同款）。"""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
    monkeypatch.setattr(agent_cli, "resolve", lambda name: use_case)


class TestReportGenerateParser:
    """report-generate 参数解析。"""

    def test_missing_plan_id_exits_two(self) -> None:
        """缺 --plan-id → argparse usage error exit 2。"""
        parser = agent_cli.build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["report-generate"])
        assert exc_info.value.code == 2

    def test_full_args_parsed(self) -> None:
        """全参解析（--plan-id 必填）。"""
        parser = agent_cli.build_parser()
        args = parser.parse_args(["report-generate", "--plan-id", "plan-1"])
        assert args.command == "report-generate"
        assert args.plan_id == "plan-1"


class TestReportGenerateExecution:
    """report-generate 执行入口（五步定式——checkpoint-create 模板）。"""

    def test_success_prints_summary_and_returns_zero(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """成功：打印 report_id/file_path（逻辑路径）/memory_id/章节计数汇总 + exit 0。"""
        stub = _StubReportGenerateUseCase()
        _patch_report_generate_entry(monkeypatch, stub)
        passed_plan_id = str(uuid.uuid4())
        exit_code = agent_cli.main(["report-generate", "--plan-id", passed_plan_id])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "报告生成完成" in out
        assert str(stub.result.report_id) in out
        assert stub.result.file_path in out  # 逻辑路径打印
        # CR1-F10：按行精确断言（file_path 行自含 memory_id 子串——裸 in 断言被子串遮蔽恒绿）
        assert "  memory_id: plan-1_20261103120000" in out.splitlines()
        # CR1-F9：枚举成员经 .value 打印为 "markdown"（打印 "ReportType.MARKDOWN" repr 即红）
        assert "  报告类型: markdown" in out.splitlines()
        assert "ReportType.MARKDOWN" not in out  # 枚举 repr 不得外泄
        assert "正文章节数: 11（降级 0）" in out  # 章节计数汇总行（值级）
        # CR1-F21（部分）：plan_id 向用例透传值级断言（独立构造期望——执行器传错/硬编码即红）
        assert stub.calls == [{"plan_id": passed_plan_id}]

    def test_domain_error_prints_code_and_returns_one(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """DomainError：[EXCEPTION_490] message stderr + exit 1（双层异常定式首层）。"""
        from src.domain.exceptions import ReportGenerationError

        stub = _StubReportGenerateUseCase()
        stub.error = ReportGenerationError(plan_id="plan-x")
        _patch_report_generate_entry(monkeypatch, stub)
        exit_code = agent_cli.main(["report-generate", "--plan-id", str(uuid.uuid4())])
        assert exit_code == 1
        err = capsys.readouterr().err
        assert "[EXCEPTION_490]" in err
        assert "该 plan_id 无思维链归档记录" in err

    def test_invalid_plan_id_guarded_before_use_case(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """非法 plan_id：[EXCEPTION_242] stderr + exit 1 + 守卫先于用例（零调用）。"""
        stub = _StubReportGenerateUseCase()
        _patch_report_generate_entry(monkeypatch, stub)
        exit_code = agent_cli.main(["report-generate", "--plan-id", "not-a-uuid"])
        assert exit_code == 1
        assert "[EXCEPTION_242]" in capsys.readouterr().err
        assert not stub.calls

    def test_unexpected_error_logged_and_returns_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """意外异常：仅 logger.error（exc_info）+ exit 1（双层定式第二层——无 stderr print）。"""
        stub = _StubReportGenerateUseCase()
        stub.error = RuntimeError("意外故障")
        _patch_report_generate_entry(monkeypatch, stub)
        import logging

        with caplog.at_level(logging.ERROR, logger="src.entrypoints.agent_cli"):
            exit_code = agent_cli.main(["report-generate", "--plan-id", str(uuid.uuid4())])
        assert exit_code == 1
        assert caplog.records[-1].exc_info is not None
        assert "[EXCEPTION" not in capsys.readouterr().err


# ======================================================================
# Story 6-5b: report-generate --format pdf（PDF 报告 CLI 入口）
# ======================================================================


class _StubPdfReport:
    """PDF 形态报告替身（file_path=L4 对象键 + citation_count 汇总面）。"""

    def __init__(self) -> None:
        """初始化替身（真实枚举成员——CR1-F9 纪律延续）。"""
        import uuid as _uuid

        from src.domain.entities.strategic_report import ReportType

        self.report_id = _uuid.uuid4()
        self.plan_id = "plan-pdf-1"
        self.report_type = ReportType.PDF  # 真实枚举成员（.value 打印为 "pdf"）
        self.file_path = f"reports/plan-pdf-1/{_uuid.uuid4()}.pdf"  # L4 对象键逻辑路径
        self.section_count = 11
        self.degraded_section_count = 0
        self.generation_ms = 240


class _StubPdfReportUseCase:
    """pdf_report_generation_use_case 替身（calls 记录 + 可注入 error）。"""

    def __init__(self) -> None:
        """初始化替身。"""
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.result = _StubPdfReport()

    async def execute(self, *, plan_id: str) -> object:
        """替身 execute（记录调用）。"""
        self.calls.append({"plan_id": plan_id})
        if self.error is not None:
            raise self.error
        return self.result


def _patch_format_entry(
    monkeypatch: pytest.MonkeyPatch,
    markdown_use_case: _StubReportGenerateUseCase,
    pdf_use_case: _StubPdfReportUseCase,
) -> None:
    """CLI 入口替身注入（resolve 按 name 分发两用例——format 分发通道锚）。"""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)

    def _fake_resolve(name: str) -> object:
        if name == "pdf_report_generation_use_case":
            return pdf_use_case
        return markdown_use_case

    monkeypatch.setattr(agent_cli, "resolve", _fake_resolve)


class TestReportGenerateFormatParser:
    """--format 参数解析（默认 markdown 向后兼容 + choices 校验）。"""

    def test_format_defaults_markdown(self) -> None:
        """缺省 --format == "markdown"（既有用户脚本零破坏——OD-11）。"""
        parser = agent_cli.build_parser()
        args = parser.parse_args(["report-generate", "--plan-id", "plan-1"])
        assert args.format == "markdown"

    def test_format_pdf_parsed(self) -> None:
        """--format pdf 解析。"""
        parser = agent_cli.build_parser()
        args = parser.parse_args(["report-generate", "--plan-id", "plan-1", "--format", "pdf"])
        assert args.format == "pdf"

    def test_format_invalid_exits_two(self) -> None:
        """非法 format 值 → argparse choices 校验 exit 2。"""
        parser = agent_cli.build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["report-generate", "--plan-id", "plan-1", "--format", "docx"])
        assert exc_info.value.code == 2


class TestReportGenerateFormatExecution:
    """--format 分发执行（PDF 分支打印/异常定式/默认通道零变化）。"""

    def test_pdf_dispatch_and_prints_summary(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """--format pdf：分发 pdf 用例 + 打印对象键/bucket/报告类型 pdf。"""
        from src.application.ports.pdf_report import EVIDENCE_BUCKET_TYPE

        markdown_stub = _StubReportGenerateUseCase()
        pdf_stub = _StubPdfReportUseCase()
        _patch_format_entry(monkeypatch, markdown_stub, pdf_stub)
        passed_plan_id = str(uuid.uuid4())
        exit_code = agent_cli.main(["report-generate", "--plan-id", passed_plan_id, "--format", "pdf"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "报告生成完成" in out
        assert str(pdf_stub.result.report_id) in out
        assert pdf_stub.result.file_path in out  # L4 对象键逻辑路径打印
        assert "  报告类型: pdf" in out.splitlines()
        assert EVIDENCE_BUCKET_TYPE in out  # bucket 打印（常量 import——实体不携 bucket）
        assert (
            "引文计数" not in out
        )  # R3-1：实体不携 citation_count（6-5a 冻结八字段）——打印面不呈现恒 0 死指标（L2 metadata 可查）
        assert "memory_id" not in out  # memory_id 反解仅 markdown 分支（.md 钉死不适用 PDF）
        assert pdf_stub.calls == [{"plan_id": passed_plan_id}]
        assert not markdown_stub.calls  # 不误分发 markdown 用例

    def test_default_format_dispatches_markdown(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """缺省 format：markdown 用例分发（既有行为零变化——AC-6 向后兼容）。"""
        markdown_stub = _StubReportGenerateUseCase()
        pdf_stub = _StubPdfReportUseCase()
        _patch_format_entry(monkeypatch, markdown_stub, pdf_stub)
        exit_code = agent_cli.main(["report-generate", "--plan-id", str(uuid.uuid4())])
        assert exit_code == 0
        assert len(markdown_stub.calls) == 1
        assert not pdf_stub.calls

    def test_pdf_492_domain_error_prints_code(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """PDF 渲染失败 492：[EXCEPTION_492] stderr + exit 1（双层定式首层）。"""
        from src.domain.exceptions import PdfRenderingError

        pdf_stub = _StubPdfReportUseCase()
        pdf_stub.error = PdfRenderingError(plan_id="plan-x")
        _patch_format_entry(monkeypatch, _StubReportGenerateUseCase(), pdf_stub)
        exit_code = agent_cli.main(["report-generate", "--plan-id", str(uuid.uuid4()), "--format", "pdf"])
        assert exit_code == 1
        err = capsys.readouterr().err
        assert "[EXCEPTION_492]" in err
        assert "PDF 报告渲染失败" in err

    def test_pdf_493_domain_error_prints_code(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """L4 证据归档失败 493：[EXCEPTION_493] stderr + exit 1。"""
        from src.domain.exceptions import ReportEvidenceStorageError

        pdf_stub = _StubPdfReportUseCase()
        pdf_stub.error = ReportEvidenceStorageError(plan_id="plan-x")
        _patch_format_entry(monkeypatch, _StubReportGenerateUseCase(), pdf_stub)
        exit_code = agent_cli.main(["report-generate", "--plan-id", str(uuid.uuid4()), "--format", "pdf"])
        assert exit_code == 1
        assert "[EXCEPTION_493]" in capsys.readouterr().err

    def test_pdf_cli_production_channel_l4_resolvable(self) -> None:
        """CLI 生产通道 L4 resolve 可达（三步排查法自动化——组合根注册链实证）。"""
        from src.domain.ports.l4_object import L4ObjectPort
        from src.domain.ports.resolver import get_resolver

        if not _global_registry_has("pdf_report_generation_use_case"):
            from src.composition_root import bootstrap

            bootstrap()
        instance = get_resolver().resolve("l4_object")
        assert isinstance(instance, L4ObjectPort)


def _global_registry_has(name: str) -> bool:
    """组合根注册探测（bootstrap 幂等守卫——conftest 已装配则零重复）。"""
    from src.domain.ports.registry import _global_registry

    return _global_registry.get(name) is not None


class _StubSummaryView:
    """摘要视图替身（checkpoint-list 表格输出 getattr 消费面）。"""

    def __init__(self, *, checkpoint_no: str, sync_status: str = "in_sync") -> None:
        self.checkpoint_no = checkpoint_no
        self.stage_id = "performance_gap"
        self.completed = True
        self.summary = f"{checkpoint_no} 阶段摘要"
        self.state_version = 0
        self.created_via = "use_case"
        self.timestamp = "2026-11-05T10:00:00+00:00"
        self.sync_status = sync_status


class _StubListUseCase:
    """清单用例替身（calls 记录 + 可编程异常）。"""

    def __init__(self, summaries: list[_StubSummaryView] | None = None) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.summaries = summaries if summaries is not None else []

    async def execute(self, **kwargs) -> list[_StubSummaryView]:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.summaries


class _StubRecoveryView:
    """恢复视图替身（checkpoint-show 九键输出 getattr 消费面）。"""

    def __init__(self, *, plan_id: str, checkpoint_no: str = "CP-1") -> None:
        self.checkpoint_no = checkpoint_no
        self.stage = "performance_gap"
        self.compressed_context = "压缩语境摘要"
        self.state_data = {"checkpoint_no": checkpoint_no, "plan_id": plan_id}
        self.correction_history: list[dict[str, Any]] = []
        self.subsequent_checkpoints = ["CP-3"]
        self.recommended_mode = "override"
        self.state_version = 0
        self.snapshot_id = str(uuid.uuid4())


class _StubRecoveryViewUseCase:
    """恢复视图用例替身（checkpoint-show 消费面——既有 checkpoint_recovery_use_case 首消费方）。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None

    async def execute(self, **kwargs) -> _StubRecoveryView:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return _StubRecoveryView(plan_id=kwargs["plan_id"], checkpoint_no=kwargs["checkpoint_no"])


class TestCheckpointListParser:
    """checkpoint-list 子命令解析（单必填参数面）。"""

    def test_checkpoint_list_requires_plan_id(self) -> None:
        """必填参数缺失 usage error exit 2（--plan-id）。"""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["checkpoint-list"])
        assert exc_info.value.code == 2

    def test_checkpoint_list_full_arguments(self) -> None:
        """全参数解析（单 --plan-id 必填）。"""
        args = agent_cli.build_parser().parse_args(["checkpoint-list", "--plan-id", str(uuid.uuid4())])
        assert args.command == "checkpoint-list"


class TestCheckpointListExecution:
    """checkpoint-list 执行（五步定式+纯标准库动态列宽表格——钦定新形态）。"""

    def test_success_table_header_and_rows(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """成功路径：表头行精确串（五列头 + ` | ` 分隔符）+ 行值级断言（sync 三态/true）。"""
        stub = _StubListUseCase(
            [
                _StubSummaryView(checkpoint_no="CP-1"),
                _StubSummaryView(checkpoint_no="CP-3", sync_status="pending_sync"),
            ]
        )
        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)
        plan_id = str(uuid.uuid4())

        exit_code = agent_cli.main(["checkpoint-list", "--plan-id", plan_id])

        assert exit_code == 0
        out = capsys.readouterr().out
        # 表头行精确断言（五列钦定：checkpoint_no/stage/completed/version/sync_status；
        # ljust 动态列宽填充——按 ` | ` 分割后逐列 strip 值级比较）
        first_line = out.splitlines()[0] if out else ""
        columns = [cell.strip() for cell in first_line.split(" | ")]
        assert columns == ["checkpoint_no", "stage", "completed", "version", "sync_status"], (
            f"表头五列钦定形态缺（实测首行={first_line!r}）"
        )
        # 行值级断言（含 sync 三态值与 true——禁子串存在性弱断言之外的形态漂移）
        assert "CP-1" in out and "CP-3" in out
        assert "performance_gap" in out
        assert "true" in out
        assert "in_sync" in out and "pending_sync" in out
        assert stub.calls and stub.calls[0]["plan_id"] == plan_id

    def test_empty_list_outputs_empty_note(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """空清单路径：exit 0 + 空态提示（枚举面非错误）。"""
        stub = _StubListUseCase([])
        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)

        exit_code = agent_cli.main(["checkpoint-list", "--plan-id", str(uuid.uuid4())])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "无 Checkpoint" in out, f"空态提示缺（实测={out!r}）"

    def test_invalid_plan_id_exit_1_before_bootstrap(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """plan_id 非 UUID：守卫先于 bootstrap（[EXCEPTION_242] stderr 形态）。"""
        stub = _StubListUseCase()
        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)

        exit_code = agent_cli.main(["checkpoint-list", "--plan-id", "not-a-uuid"])

        assert exit_code == 1
        assert not stub.calls, "守卫失败后不得触达用例"
        assert "[EXCEPTION_242]" in capsys.readouterr().err


class TestCheckpointShowParser:
    """checkpoint-show 子命令解析（双必填参数面）。"""

    def test_checkpoint_show_requires_core_params(self) -> None:
        """必填参数缺失 usage error exit 2（--plan-id/--checkpoint-no）。"""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["checkpoint-show", "--plan-id", str(uuid.uuid4())])
        assert exc_info.value.code == 2

    def test_checkpoint_show_full_arguments(self) -> None:
        """全参数解析（双必填）。"""
        args = agent_cli.build_parser().parse_args(
            ["checkpoint-show", "--plan-id", str(uuid.uuid4()), "--checkpoint-no", "CP-1"]
        )
        assert args.command == "checkpoint-show"
        assert args.checkpoint_no == "CP-1"


class TestCheckpointShowExecution:
    """checkpoint-show 执行（resolve 既有 checkpoint_recovery_use_case——首消费方）。"""

    def test_success_nine_keys_output(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """成功路径：exit 0 + 9 键视图逐键输出（零适配复用 CheckpointRecoveryView）。"""
        stub = _StubRecoveryViewUseCase()
        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)
        plan_id = str(uuid.uuid4())

        exit_code = agent_cli.main(["checkpoint-show", "--plan-id", plan_id, "--checkpoint-no", "CP-1"])

        assert exit_code == 0
        out = capsys.readouterr().out
        for key in (
            "checkpoint_no",
            "stage",
            "compressed_context",
            "state_data",
            "correction_history",
            "subsequent_checkpoints",
            "recommended_mode",
            "state_version",
            "snapshot_id",
        ):
            assert key in out, f"输出缺 9 键视图键 {key}（实测={out!r}）"
        assert "override" in out
        assert stub.calls and stub.calls[0]["plan_id"] == plan_id
        assert stub.calls[0]["checkpoint_no"] == "CP-1"

    def test_resolves_recovery_view_use_case(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """resolve 目标 = checkpoint_recovery_use_case（既有注册首消费方——接线断言③）。"""
        stub = _StubRecoveryViewUseCase()
        resolved_names: list[str] = []

        def _record_resolve(name: str) -> Any:
            resolved_names.append(name)
            return stub

        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", _record_resolve)

        exit_code = agent_cli.main(["checkpoint-show", "--plan-id", str(uuid.uuid4()), "--checkpoint-no", "CP-1"])

        assert exit_code == 0
        assert "checkpoint_recovery_use_case" in resolved_names, (
            f"checkpoint-show 须 resolve 既有 checkpoint_recovery_use_case（实测={resolved_names}）"
        )

    def test_business_exception_exit_1(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """业务异常路径：480 → exit 1 + stderr 含 code。"""
        from src.domain.exceptions import PlanningNotFoundError

        stub = _StubRecoveryViewUseCase()
        stub.error = PlanningNotFoundError(plan_id="p")
        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)

        exit_code = agent_cli.main(["checkpoint-show", "--plan-id", str(uuid.uuid4()), "--checkpoint-no", "CP-2"])

        assert exit_code == 1
        assert "EXCEPTION_480" in capsys.readouterr().err


class _StubRecoveryOutcome:
    """恢复结果替身（checkpoint-recover 输出 getattr 消费面）。"""

    def __init__(self) -> None:
        self.checkpoint_no = "CP-3"
        self.recovery_mode = "override"
        self.corrected = True
        self.new_state_version = 1
        self.affected_checkpoints = ["CP-5"]
        self.marked_checkpoints = ["CP-5"]
        self.execution_ms = 3.2
        self.next_action_hint = "一致性风险提示：后续 Checkpoint 基于旧版本"
        self.recovery_record_session_id = "blm-checkpoint-recovery-plan"
        self.recovered_snapshot_id = str(uuid.uuid4())


class _StubRecoveryViewOutcome:
    """恢复视图替身（dry-run 评估输出消费面——recover_checkpoint ②步视图）。"""

    def __init__(self) -> None:
        self.checkpoint_no = "CP-3"
        self.stage = "performance_gap"
        self.subsequent_checkpoints = ["CP-5"]
        self.recommended_mode = "override"
        self.state_version = 0
        self.snapshot_id = str(uuid.uuid4())


class _StubRecoveryExecuteUseCase:
    """恢复执行用例替身（calls 记录 + 可编程异常）。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None

    async def execute(self, **kwargs) -> _StubRecoveryOutcome:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return _StubRecoveryOutcome()


class TestCheckpointRecoverParser:
    """checkpoint-recover 子命令解析（双必填+修正四参数+mode+confirm）。"""

    def test_checkpoint_recover_requires_core_params(self) -> None:
        """必填参数缺失 usage error exit 2（--plan-id/--checkpoint-no）。"""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["checkpoint-recover", "--plan-id", str(uuid.uuid4())])
        assert exc_info.value.code == 2

    def test_checkpoint_recover_mode_choices(self) -> None:
        """--mode 值域 choices 拦截（replay/override 小写——非法值 exit 2）。"""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(
                ["checkpoint-recover", "--plan-id", str(uuid.uuid4()), "--checkpoint-no", "CP-1", "--mode", "REPLAY"]
            )
        assert exc_info.value.code == 2

    def test_checkpoint_recover_full_arguments(self) -> None:
        """全参数解析（修正四参数成组+--mode+--confirm+--confirmed-by）。"""
        args = agent_cli.build_parser().parse_args(
            [
                "checkpoint-recover",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-3",
                "--correction-type",
                "L2",
                "--previous-value",
                "旧",
                "--new-value",
                "新",
                "--applied-by",
                "高管",
                "--mode",
                "override",
                "--confirm",
                "--confirmed-by",
                "审批人",
            ]
        )
        assert args.command == "checkpoint-recover"
        assert args.correction_type == "L2"
        assert args.confirm is True
        assert args.mode == "override"


class _StubRecoveryViewUseCaseForDryRun:
    """dry-run 评估视图用例替身（execute 返回可定制视图——按名分派消费面）。"""

    def __init__(self, view: Any = None) -> None:
        self._view = view if view is not None else _StubRecoveryViewOutcome()

    async def execute(self, **kwargs: Any) -> Any:
        return self._view


class TestCheckpointRecoverDryRun:
    """checkpoint-recover dry-run 两态（无 --confirm——评估输出不调引擎）。"""

    def _patch_dual(self, monkeypatch: pytest.MonkeyPatch, exec_stub: Any, view_use_case: Any) -> list[str]:
        """双 resolve 目标注入（执行用例+恢复视图用例——按名分派）。"""
        resolved: list[str] = []

        def _resolve(name: str) -> Any:
            resolved.append(name)
            if name == "checkpoint_recovery_use_case":
                return view_use_case
            return exec_stub

        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", _resolve)
        return resolved

    def test_dry_run_exit_0_with_assessment_no_engine_call(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """dry-run：exit 0 + 影响评估输出 + 执行用例零调用（三零之一）。"""
        exec_stub = _StubRecoveryExecuteUseCase()
        self._patch_dual(monkeypatch, exec_stub, _StubRecoveryViewUseCaseForDryRun())

        exit_code = agent_cli.main(
            [
                "checkpoint-recover",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-3",
            ]
        )

        assert exit_code == 0
        assert not exec_stub.calls, "dry-run 不得调用恢复执行引擎（三零——记录未写事件未发修正未应用）"
        out = capsys.readouterr().out
        assert "CP-5" in out, "评估输出缺后续清单"
        assert "override" in out, "评估输出缺建议模式"
        assert "确认" in out, "评估输出缺待确认提示"

    def test_dry_run_with_correction_shows_parameters(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """dry-run 带修正参数：四参数展示（仅展示零应用——applied_at 构造时生成）。"""
        exec_stub = _StubRecoveryExecuteUseCase()
        self._patch_dual(monkeypatch, exec_stub, _StubRecoveryViewUseCaseForDryRun())

        exit_code = agent_cli.main(
            [
                "checkpoint-recover",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-3",
                "--correction-type",
                "L2",
                "--previous-value",
                "旧战略参数",
                "--new-value",
                "新战略参数",
                "--applied-by",
                "高管-dryrun",
            ]
        )

        assert exit_code == 0
        assert not exec_stub.calls
        out = capsys.readouterr().out
        assert "新战略参数" in out, "评估输出缺修正展示（new_value）"
        assert "L2" in out, "评估输出缺 correction_type 展示"

    def test_dry_run_empty_correction_type_exit_1(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """dry-run 态 --correction-type 空串 → 242（代码审查 R2-F3/N6）。

        成组守卫（含空串校验）先于两态分支——评估/执行参数校验面一致的
        评估态红锚（此前仅 confirm 态有锚，结构保证成立但缺测试钉）。
        """
        exec_stub = _StubRecoveryExecuteUseCase()
        self._patch_dual(monkeypatch, exec_stub, _StubRecoveryViewUseCaseForDryRun())

        exit_code = agent_cli.main(
            [
                "checkpoint-recover",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-3",
                "--correction-type",
                "",
                "--previous-value",
                "旧战略参数",
                "--new-value",
                "新战略参数",
                "--applied-by",
                "高管-dryrun",
            ]
        )

        assert exit_code == 1
        assert not exec_stub.calls, "空串守卫失败后不得触达任何用例"
        stderr = capsys.readouterr().err
        assert "[EXCEPTION_242]" in stderr
        assert "correction-type 不可为空" in stderr, f"stderr 缺空串守卫语义（实测={stderr!r}）"

    def test_dry_run_explicit_empty_confirmed_by_shows_not_provided(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """dry-run 显式空串审批人显示「（未提供）」不滑入 applied_by（代码审查 R3-F1）。

        R2-F1 显示链对齐 is None 语义的展示面红锚：`--confirmed-by ""` 在
        dry-run 显示兜底提示（与 confirm 态 242 拒绝的预期一致）——突变
        回退 or 链则显示 applied_by 兜底值，本断言红。
        """
        exec_stub = _StubRecoveryExecuteUseCase()
        self._patch_dual(monkeypatch, exec_stub, _StubRecoveryViewUseCaseForDryRun())

        exit_code = agent_cli.main(
            [
                "checkpoint-recover",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-3",
                "--correction-type",
                "L2",
                "--previous-value",
                "旧战略参数",
                "--new-value",
                "新战略参数",
                "--applied-by",
                "修正人A",
                "--confirmed-by",
                "",
            ]
        )

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "（未提供——confirm 时必填）" in out, f"显式空串审批人须显示兜底提示而非滑入 applied_by（实测={out!r}）"
        assert "审批人: 修正人A" not in out, "显式空串不得静默滑入 applied_by 兜底（R2-F1 展示锚）"

    def test_dry_run_conflict_mode_pre_warning(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """dry-run 冲突组合评估预警（建议 replay+请求 override → 预检提示）。"""

        class _ReplayView(_StubRecoveryViewOutcome):
            def __init__(self) -> None:
                super().__init__()
                self.recommended_mode = "replay"
                self.subsequent_checkpoints = ["CP-3", "CP-5"]

        exec_stub = _StubRecoveryExecuteUseCase()
        self._patch_dual(monkeypatch, exec_stub, _StubRecoveryViewUseCaseForDryRun(_ReplayView()))

        exit_code = agent_cli.main(
            [
                "checkpoint-recover",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-1",
                "--mode",
                "override",
            ]
        )

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "487" in out, "冲突组合评估输出缺「confirm 必拒 487」预检提示"


class TestCheckpointRecoverExecution:
    """checkpoint-recover confirm 执行（五步定式+成组守卫+两态守卫分工）。"""

    def _patch_exec(self, monkeypatch: pytest.MonkeyPatch, exec_stub: Any) -> None:
        monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
        monkeypatch.setattr(agent_cli, "resolve", lambda name: exec_stub)

    def test_confirm_calls_engine_with_full_params(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """confirm 执行：全参调用引擎+created_via="cli"+confirmed_by 链。"""
        exec_stub = _StubRecoveryExecuteUseCase()
        self._patch_exec(monkeypatch, exec_stub)
        plan_id = str(uuid.uuid4())

        exit_code = agent_cli.main(
            [
                "checkpoint-recover",
                "--plan-id",
                plan_id,
                "--checkpoint-no",
                "CP-3",
                "--confirm",
                "--confirmed-by",
                "审批人",
            ]
        )

        assert exit_code == 0
        assert exec_stub.calls, "confirm 未调用引擎"
        kwargs = exec_stub.calls[0]
        assert kwargs["plan_id"] == plan_id
        assert kwargs["confirmed_by"] == "审批人"
        assert kwargs["created_via"] == "cli"
        assert kwargs["correction"] is None
        out = capsys.readouterr().out
        assert "CP-3" in out

    def test_confirm_with_correction_constructs_record(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """confirm+修正：CorrectionRecord 构造传抵（四参数成组完整形态）。"""
        exec_stub = _StubRecoveryExecuteUseCase()
        self._patch_exec(monkeypatch, exec_stub)

        exit_code = agent_cli.main(
            [
                "checkpoint-recover",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-3",
                "--correction-type",
                "L2",
                "--previous-value",
                "旧",
                "--new-value",
                "新",
                "--applied-by",
                "修正人",
                "--confirm",
            ]
        )

        assert exit_code == 0
        correction = exec_stub.calls[0]["correction"]
        assert correction is not None
        assert correction.correction_type == "L2"
        assert correction.previous_value == "旧"
        assert correction.new_value == "新"
        assert correction.applied_by == "修正人"
        # --confirmed-by 缺省链：修正场景缺省取 --applied-by
        assert exec_stub.calls[0]["confirmed_by"] == "修正人"

    def test_confirm_without_confirmed_by_and_correction_exit_1(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """纯恢复 confirm 无 --confirmed-by/--applied-by → 242（CLI 层+用例层双落位）。"""
        exec_stub = _StubRecoveryExecuteUseCase()
        self._patch_exec(monkeypatch, exec_stub)

        exit_code = agent_cli.main(
            [
                "checkpoint-recover",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-3",
                "--confirm",
            ]
        )

        assert exit_code == 1
        assert not exec_stub.calls, "守卫失败后不得触达引擎"
        assert "[EXCEPTION_242]" in capsys.readouterr().err

    def test_partial_correction_params_exit_1(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """四参数部分出现 → 242（CLI 层 post-parse 成组检测——唯一落位）。"""
        exec_stub = _StubRecoveryExecuteUseCase()
        self._patch_exec(monkeypatch, exec_stub)

        exit_code = agent_cli.main(
            [
                "checkpoint-recover",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-3",
                "--correction-type",
                "L2",
                "--confirm",
            ]
        )

        assert exit_code == 1
        assert not exec_stub.calls
        stderr = capsys.readouterr().err
        assert "[EXCEPTION_242]" in stderr
        assert "成组" in stderr or "correction" in stderr.lower(), f"stderr 缺成组约束语义（实测={stderr!r}）"

    def test_empty_correction_type_full_group_exit_1(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """四参全供但 --correction-type 空串 → 242（代码审查 R1-F9/G2——空修正无审计语义）。"""
        exec_stub = _StubRecoveryExecuteUseCase()
        self._patch_exec(monkeypatch, exec_stub)

        exit_code = agent_cli.main(
            [
                "checkpoint-recover",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-3",
                "--correction-type",
                "",
                "--previous-value",
                "旧值",
                "--new-value",
                "新值",
                "--applied-by",
                "修正人",
                "--confirm",
                "--confirmed-by",
                "高管",
            ]
        )

        assert exit_code == 1
        assert not exec_stub.calls, "correction_type 空串守卫失败后不得触达引擎"
        stderr = capsys.readouterr().err
        assert "[EXCEPTION_242]" in stderr
        assert "correction-type 不可为空" in stderr, f"stderr 缺空串守卫语义（实测={stderr!r}）"

    def test_explicit_empty_confirmed_by_exit_1_not_silent_fallback(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--confirmed-by 显式空串 → 242 不静默滑入 --applied-by（代码审查 R1-F9/G2）。

        修复前 `confirmed_by or (applied_by or "")` 使显式空串与缺省不可区分——
        审批人身份被静默替换为修正人；修复后 is None 判缺省，显式空串 fail-loud。
        """
        exec_stub = _StubRecoveryExecuteUseCase()
        self._patch_exec(monkeypatch, exec_stub)

        exit_code = agent_cli.main(
            [
                "checkpoint-recover",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-3",
                "--correction-type",
                "L2",
                "--previous-value",
                "旧值",
                "--new-value",
                "新值",
                "--applied-by",
                "修正人A",
                "--confirm",
                "--confirmed-by",
                "",
            ]
        )

        assert exit_code == 1
        assert not exec_stub.calls, "显式空串审批人守卫失败后不得触达引擎"
        stderr = capsys.readouterr().err
        assert "[EXCEPTION_242]" in stderr
        assert "confirmed-by" in stderr, f"stderr 缺审批人守卫语义（实测={stderr!r}）"

    def test_mode_conflict_487_stderr(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """--mode override 冲突 → 487 stderr [EXCEPTION_487] exit 1。"""
        from src.domain.exceptions import RecoveryModeConflictError

        exec_stub = _StubRecoveryExecuteUseCase()
        exec_stub.error = RecoveryModeConflictError(recommended_mode="Replay", requested_mode="Override")
        self._patch_exec(monkeypatch, exec_stub)

        exit_code = agent_cli.main(
            [
                "checkpoint-recover",
                "--plan-id",
                str(uuid.uuid4()),
                "--checkpoint-no",
                "CP-1",
                "--mode",
                "override",
                "--confirm",
                "--confirmed-by",
                "高管",
            ]
        )

        assert exit_code == 1
        stderr = capsys.readouterr().err
        assert "[EXCEPTION_487]" in stderr
        assert "Replay" in stderr and "Override" in stderr, "487 message 双模式可见"

    def test_invalid_plan_id_exit_1(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """plan_id 非 UUID → exit 1 [EXCEPTION_242]（守卫先于 bootstrap）。"""
        exec_stub = _StubRecoveryExecuteUseCase()
        self._patch_exec(monkeypatch, exec_stub)

        exit_code = agent_cli.main(
            ["checkpoint-recover", "--plan-id", "not-a-uuid", "--checkpoint-no", "CP-1", "--confirm", "--confirmed-by", "x"]
        )

        assert exit_code == 1
        assert not exec_stub.calls
        assert "[EXCEPTION_242]" in capsys.readouterr().err


# ===================================================================
# Story 6-7: trace-tree 子命令（溯源树四层展示——CLI 分析视入口）
# ===================================================================


def _make_stub_tree(*, build_degraded: bool = False, stages: tuple[str, ...] | None = None) -> Any:
    """构造树 VO 替身（SimpleNamespace——打印函数 getattr 形态零强耦合）."""
    from types import SimpleNamespace

    display_map = {"performance_gap": "业绩差距分析", "market_insight_trend": "看趋势"}
    chunk_id_map = {"performance_gap": "chunkgap01abcdef", "market_insight_trend": "chunktrend01abc"}
    stage_nodes = []
    for stage, display in display_map.items():
        if stages is not None and stage not in stages:
            continue
        chunk = SimpleNamespace(
            chunk_id=chunk_id_map[stage],
            content_excerpt="切片内容" * 5,
            page_start=3,
            page_end=3,
            status="resolved",
            children=[
                SimpleNamespace(
                    document_id="d-1",
                    filename="年报.pdf",
                    version=1,
                    page=3,
                    object_key="raw-documents/test/d-1.pdf",
                    bucket="raw-documents",
                    bbox=None,
                    status="resolved",
                    jump_ready=True,
                )
            ],
        )
        stage_nodes.append(
            SimpleNamespace(
                stage=stage,
                display_name=display,
                summary=f"{display}摘要",
                degraded=False,
                degrade_reason="",
                tools_used=("t1",),
                reflection_excerpt="反思",
                evidence_count=1,
                children=[chunk],
            )
        )
    root = SimpleNamespace(
        plan_id=str(uuid.uuid4()),
        title="BLM 战略规划溯源",
        summary="综合结论",
        stage_count=len(stage_nodes),
        children=tuple(stage_nodes),
    )
    return SimpleNamespace(
        plan_id=root.plan_id,
        root=root,
        adopted_archives=len(stage_nodes),
        total_archives=len(stage_nodes),
        degraded_stages=(),
        build_degraded=build_degraded,
        generated_at="2026-11-05T00:00:00+00:00",
    )


class _StubTreeUseCase:
    """trace-tree 用例替身（记录调用参数/可编程树或异常）."""

    def __init__(self, tree: Any = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._tree = tree
        self._error = error

    async def execute(self, *, plan_id: str, depth: int = 4) -> Any:
        self.calls.append({"plan_id": plan_id, "depth": depth})
        if self._error is not None:
            raise self._error
        return self._tree


def _patch_trace_tree_entry(monkeypatch: pytest.MonkeyPatch, stub: _StubTreeUseCase) -> None:
    """monkeypatch agent_cli 模块级 bootstrap/resolve（checkpoint 族注入器同款）."""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
    monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)


class TestTraceTreeParser:
    """trace-tree 子命令解析（--plan-id 必填 + --depth choices str 元组 + --stage）."""

    def test_trace_tree_requires_plan_id(self) -> None:
        """必填参数缺失 usage error exit 2（--plan-id）."""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["trace-tree"])
        assert exc_info.value.code == 2

    def test_trace_tree_full_arguments(self) -> None:
        """全参数解析（--plan-id/--depth/--stage）."""
        args = agent_cli.build_parser().parse_args(
            ["trace-tree", "--plan-id", str(uuid.uuid4()), "--depth", "2", "--stage", "performance_gap"]
        )
        assert args.command == "trace-tree"
        assert args.depth == "2", "--depth 应为字符串入参（DR3-7——runner 内 int 转换）"
        assert args.stage == "performance_gap"

    def test_trace_tree_depth_default_4(self) -> None:
        """--depth 默认 "4"（全树）."""
        args = agent_cli.build_parser().parse_args(["trace-tree", "--plan-id", str(uuid.uuid4())])
        assert args.depth == "4"
        assert args.stage is None

    def test_trace_tree_depth_zero_rejected_by_choices_exit_2(self) -> None:
        """--depth 0 由 argparse choices 拦截 exit 2（CLI 面不走 242——分工钦定）."""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["trace-tree", "--plan-id", str(uuid.uuid4()), "--depth", "0"])
        assert exc_info.value.code == 2

    def test_trace_tree_depth_five_rejected_by_choices_exit_2(self) -> None:
        """--depth 5 由 argparse choices 拦截 exit 2."""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["trace-tree", "--plan-id", str(uuid.uuid4()), "--depth", "5"])
        assert exc_info.value.code == 2


class TestTraceTreeExecution:
    """trace-tree 执行（五步定式 + 树形缩进打印 + --stage 客户端过滤）."""

    def test_success_four_layer_labels_and_values(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """成功路径：exit 0 + 四层层级标签 + chunk 前 8 位 + filename 值级."""
        stub = _StubTreeUseCase(_make_stub_tree())
        _patch_trace_tree_entry(monkeypatch, stub)
        plan_id = str(uuid.uuid4())

        exit_code = agent_cli.main(["trace-tree", "--plan-id", plan_id])

        assert exit_code == 0
        out = capsys.readouterr().out
        for label in ("结论:", "分析:", "切片:", "文档:"):
            assert label in out, f"输出缺层级标签 {label!r}"
        assert "chunkgap" in out, "输出应含 chunk_id 前 8 位"
        assert "年报.pdf" in out, "输出应含文档 filename 值级"
        assert stub.calls and stub.calls[0]["depth"] == 4

    def test_stage_order_canonical(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """分析层行序=流程规范序（gap 在 trend 前——DR3-1）."""
        stub = _StubTreeUseCase(_make_stub_tree())
        _patch_trace_tree_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["trace-tree", "--plan-id", str(uuid.uuid4())])

        assert exit_code == 0
        out = capsys.readouterr().out
        gap_pos, trend_pos = out.find("业绩差距分析"), out.find("看趋势")
        assert gap_pos >= 0 and trend_pos >= 0
        assert gap_pos < trend_pos

    def test_stage_filter_keeps_conclusion_line(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--stage 过滤：指定 stage 展示、其余分析层零输出、结论层行保留（DR3-7）."""
        stub = _StubTreeUseCase(_make_stub_tree())
        _patch_trace_tree_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["trace-tree", "--plan-id", str(uuid.uuid4()), "--stage", "market_insight_trend"])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "结论:" in out, "过滤应保留结论层行"
        assert "看趋势" in out
        assert "业绩差距分析" not in out, "未指定 stage 分析层应零输出"
        assert "chunkgap" not in out, "未指定 stage 的切片行应零输出（gap chunk 前 8 位锚）"

    def test_depth_string_converted_to_int(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """--depth 字符串入参在 runner 内 int 转换（DR3-7 签名钦定）."""
        stub = _StubTreeUseCase(_make_stub_tree(stages=("market_insight_trend",)))
        _patch_trace_tree_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["trace-tree", "--plan-id", str(uuid.uuid4()), "--depth", "2"])

        assert exit_code == 0
        assert stub.calls and stub.calls[0]["depth"] == 2, "runner 应 int(depth) 转换后传端口"

    def test_invalid_plan_id_stderr_242_exit_1(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """畸形 plan_id：CLI 层 UUID 守卫 → [EXCEPTION_242] stderr + exit 1（守卫先于 bootstrap）."""
        stub = _StubTreeUseCase()
        _patch_trace_tree_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["trace-tree", "--plan-id", "not-a-uuid"])

        assert exit_code == 1
        assert not stub.calls, "守卫失败后不得触达用例"
        assert "[EXCEPTION_242]" in capsys.readouterr().err

    def test_empty_tree_outputs_no_archive_note(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """空树（无归档）：exit 0 + 「该 plan 无思维链归档行」提示（空树是正常态——AC-5；R3-F3 精确化）."""
        stub = _StubTreeUseCase(_make_stub_tree(build_degraded=False, stages=()))
        _patch_trace_tree_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["trace-tree", "--plan-id", str(uuid.uuid4())])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "该 plan 无思维链归档行" in out, f"空树应打无归档提示（实测={out!r}）"
        assert "归档查询失败" not in out, "真空树不得打降级提示（与顶层失败分立——DR1-9）"

    def test_degraded_tree_outputs_query_failed_note(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """空树（顶层降级）：exit 0 + 「⚠ 归档查询失败（已降级）」提示（顶层容错 CLI 面可测位——DR2-7）."""
        stub = _StubTreeUseCase(_make_stub_tree(build_degraded=True, stages=()))
        _patch_trace_tree_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["trace-tree", "--plan-id", str(uuid.uuid4())])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "归档查询失败（已降级）" in out, f"顶层降级应打失败提示（实测={out!r}）"
        assert "该 plan 无思维链归档行" not in out, "降级空树不得打无归档提示（分立哨兵——R3-F3 同步新文案防永真）"

    def test_collapsed_tree_outputs_archive_stats_not_empty_note(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """折叠空 children（depth=1 有归档/全脏 stage 形态）：打归档对照行而非「无归档行」假话（R1-F3 三分化第三腿）."""
        stub_tree = _make_stub_tree(build_degraded=False, stages=("performance_gap",))
        stub_tree.root.children = ()  # 模拟服务 depth=1 折叠/全脏 stage 形态（total>0 而 children 空）
        stub = _StubTreeUseCase(stub_tree)
        _patch_trace_tree_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["trace-tree", "--plan-id", str(uuid.uuid4()), "--depth", "1"])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "归档对照" in out, f"折叠形态应打对照行（实测={out!r}）"
        assert "该 plan 无思维链归档行" not in out, "total>0 时不得打无归档假话（读模型诚实性——DR1-9/R3-F3 同步）"
        assert "归档查询失败" not in out, "非降级形态不得打降级提示"

    def test_degradation_markers_visible_in_output(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """降级状态呈现（R3-F1）：切片/文档行携带 status 标记 + 顶层降级 stage 行——解析降级对分析视用户可见."""
        from types import SimpleNamespace

        degraded_doc = SimpleNamespace(
            document_id="d-9",
            filename="年报.pdf",
            version=1,
            page=3,
            object_key="raw-documents/test/d-9.pdf",
            bucket="raw-documents",
            bbox=None,
            status="document_missing",
            jump_ready=False,
        )
        missing_chunk = SimpleNamespace(
            chunk_id="chunkmissing01",
            content_excerpt="",
            page_start=None,
            page_end=None,
            status="point_missing",
            children=(),
        )
        ok_doc = SimpleNamespace(
            document_id="d-1",
            filename="月报.pdf",
            version=1,
            page=2,
            object_key="raw-documents/test/d-1.pdf",
            bucket="raw-documents",
            bbox=None,
            status="resolved",
            jump_ready=True,
        )
        ok_chunk = SimpleNamespace(
            chunk_id="chunkok01abcdef",
            content_excerpt="正常切片",
            page_start=2,
            page_end=2,
            status="resolved",
            children=[ok_doc, degraded_doc],
        )
        stage_node = SimpleNamespace(
            stage="market_insight_trend",
            display_name="看趋势",
            summary="摘要",
            degraded=False,
            degrade_reason="",
            tools_used=("t1",),
            reflection_excerpt="反思",
            evidence_count=2,
            children=[missing_chunk, ok_chunk],
        )
        root = SimpleNamespace(
            plan_id=str(uuid.uuid4()),
            title="BLM 战略规划溯源",
            summary="综合结论",
            stage_count=1,
            children=(stage_node,),
        )
        tree = SimpleNamespace(
            plan_id=root.plan_id,
            root=root,
            adopted_archives=1,
            total_archives=1,
            degraded_stages=("market_insight_trend",),
            build_degraded=False,
            generated_at="2026-11-06T00:00:00+00:00",
        )
        stub = _StubTreeUseCase(tree)
        _patch_trace_tree_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["trace-tree", "--plan-id", root.plan_id])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "[point_missing]" in out, f"点失效切片行应携带状态标记（实测={out!r}）"
        assert "[document_missing]" in out, f"文档缺失行应携带状态标记（实测={out!r}）"
        assert "降级 stage: market_insight_trend" in out, f"degraded_stages 非空应打顶层降级行（实测={out!r}）"
        assert "[resolved]" not in out, "resolved 正常态不打标记（标记仅降级态）"


# ===================================================================
# === Story 6-8: executive-view 子命令（高管速览入口——四段聚合+RAG 三色）===
# ===================================================================


def _make_stub_view_sections(
    *,
    planning_available: bool = True,
    completed: int = 8,
    total: int = 8,
    percent: int = 100,
    degraded_steps: int = 0,
    current_step: str | None = "market_insight_synthesis",
    last_activity: str | None = "2026-11-06T10:00:00+00:00",
    cp_total: int = 2,
    cp_completed: int = 2,
    in_sync: int = 2,
    pending_sync: int = 0,
    invalidated: int = 0,
    recovery_mode: str | None = "replay",
    recovery_by: str | None = "ceo-cli-s8",
    recovered_at: str | None = "2026-11-06T10:00:00+00:00",
    window_days: int = 7,
    audit_total: int = 42,
    recent_events: tuple = (),
    last_event: str | None = None,
    report_available: bool = True,
    report_type: str | None = "markdown",
    file_path: str | None = "/tmp/sisys-reports/plan.md",
    section_count: int = 11,
    degraded_sections: int = 0,
    report_generated_at: str | None = "2026-11-06T10:00:00+00:00",
) -> Any:
    """executive-view 视图替身工厂（getattr 零 VO import——6-3 先例形态）."""
    from types import SimpleNamespace

    planning = SimpleNamespace(
        available=planning_available,
        degraded=False,
        completed_steps=completed,
        total_steps=total,
        progress_percent=percent,
        current_step=current_step,
        degraded_step_count=degraded_steps,
        last_activity_at=last_activity,
    )
    approval = SimpleNamespace(
        available=cp_total > 0,
        degraded=False,
        total_checkpoints=cp_total,
        completed_count=cp_completed,
        in_sync_count=in_sync,
        pending_sync_count=pending_sync,
        invalidated_count=invalidated,
        last_recovery_mode=recovery_mode,
        last_recovery_confirmed_by=recovery_by,
        last_recovered_at=recovered_at,
    )
    audit = SimpleNamespace(
        degraded=False,
        window_days=window_days,
        window_start="2026-10-30T10:00:01+00:00",
        window_end="2026-11-06T10:00:01+00:00",
        total_events=audit_total,
        recent_events=recent_events,
        last_event_at=last_event,
    )
    report = SimpleNamespace(
        available=report_available,
        degraded=False,
        report_id="0f0e0d0c-0b0a-0908-0706-050403020100" if report_available else None,
        report_type=report_type,
        file_path=file_path,
        section_count=section_count,
        degraded_section_count=degraded_sections,
        generated_at=report_generated_at,
    )
    return SimpleNamespace(
        plan_id=str(uuid.uuid4()),
        generated_at="2026-11-06T10:00:01+00:00",
        health=SimpleNamespace(value="green"),
        build_degraded=False,
        planning=planning,
        approval=approval,
        audit=audit,
        report=report,
    )


class _StubExecutiveViewUseCase:
    """executive-view 用例替身（记录调用参数/可编程视图或异常——_StubTreeUseCase 同款形态）."""

    def __init__(self, view: Any = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._view = view
        self._error = error

    async def execute(self, *, plan_id: str) -> Any:
        self.calls.append({"plan_id": plan_id})
        if self._error is not None:
            raise self._error
        return self._view


def _patch_executive_view_entry(monkeypatch: pytest.MonkeyPatch, stub: _StubExecutiveViewUseCase) -> None:
    """monkeypatch agent_cli 模块级 bootstrap/resolve（trace-tree 族注入器同款——每命令族专用 patcher纪律）."""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
    monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)


class TestExecutiveViewParser:
    """executive-view 参数解析（--plan-id 必填单参数——零可选参数 YAGNI）."""

    def test_parses_command_and_plan_id(self) -> None:
        """注册锚：build_parser 识别 executive-view 子命令与 --plan-id."""
        args = agent_cli.build_parser().parse_args(["executive-view", "--plan-id", "123e4567-e89b-12d3-a456-426614174000"])
        assert args.command == "executive-view"
        assert args.plan_id == "123e4567-e89b-12d3-a456-426614174000"

    def test_missing_plan_id_exits_2(self) -> None:
        """缺 --plan-id → argparse SystemExit 2（argparse 原生用法错误承载）."""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["executive-view"])
        assert exc_info.value.code == 2

    def test_no_optional_arguments(self) -> None:
        """零可选参数（无 --window-days/--format——YAGNI 钦定）."""
        import inspect

        source = inspect.getsource(agent_cli.build_parser)
        executive_block = source.split('add_parser(\n        "executive-view"')[1].split("add_parser(")[0]
        assert "--window-days" not in executive_block
        assert "--format" not in executive_block


class TestExecutiveViewExecution:
    """executive-view 执行（五步定式：守卫→bootstrap→resolve→打印→异常退码）."""

    def test_full_data_green_output(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """全数据 GREEN：健康行精确+四段分隔行+值级行+exit 0."""
        from types import SimpleNamespace

        view = _make_stub_view_sections(
            recent_events=(
                SimpleNamespace(
                    action_type="exec-view:probe",
                    actor="ceo",
                    target_resource="plan",
                    timestamp="2026-11-06T09:59:59+00:00",
                ),
            ),
            last_event="2026-11-06T09:59:59+00:00",
        )
        stub = _StubExecutiveViewUseCase(view)
        _patch_executive_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["executive-view", "--plan-id", view.plan_id])

        assert exit_code == 0
        assert stub.calls and stub.calls[0]["plan_id"] == view.plan_id
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert f"高管简化视图（plan: {view.plan_id}）" in lines, f"首行应精确匹配（实测={out!r}）"
        assert "健康状态: green（健康）" in lines, f"健康行精确匹配（实测={out!r}）"
        for separator in ("── 规划态势 ──", "── 审批中心 ──", "── 审计摘要 ──", "── 报告 ──"):
            assert separator in lines, f"四段分隔行缺失 {separator}（实测={out!r}）"
        assert "进度: 8/8（100%）" in out
        assert "降级: 0 步" in out
        assert "Checkpoint: 共 2 | 已完成 2 | in_sync 2 | pending_sync 0 | invalidated 0" in out
        assert "最近恢复: replay by ceo-cli-s8 at 2026-11-06T10:00:00+00:00" in out
        assert "近 7 天事件: 42 | 最近: exec-view:probe by ceo at 2026-11-06T09:59:59+00:00" in out
        assert "最新报告: markdown /tmp/sisys-reports/plan.md | 章节 11（降级 0）" in out

    def test_red_health_label_output(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """RED 标签分支：red →「健康状态: red（危险）」精确匹配（R1-P3⑩ 补测——三色标签全覆盖）."""
        from types import SimpleNamespace

        view = _make_stub_view_sections(
            completed=3,
            percent=37,
            degraded_steps=3,
        )
        view.health = SimpleNamespace(value="red")
        stub = _StubExecutiveViewUseCase(view)
        _patch_executive_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["executive-view", "--plan-id", view.plan_id])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "健康状态: red（危险）" in out.splitlines(), f"red 标签行精确匹配（实测={out!r}）"

    def test_empty_plan_output(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """空 plan 空态：四段空态行齐备+exit 0（空态是正常态——AC-5/AC-6）."""
        view = _make_stub_view_sections(
            planning_available=False,
            completed=0,
            percent=0,
            current_step=None,
            last_activity=None,
            cp_total=0,
            cp_completed=0,
            in_sync=0,
            recovery_mode=None,
            recovery_by=None,
            recovered_at=None,
            window_days=7,
            audit_total=5,
            recent_events=(),
            last_event=None,
            report_available=False,
            report_type=None,
            file_path=None,
            section_count=0,
            degraded_sections=0,
            report_generated_at=None,
        )
        from types import SimpleNamespace

        view.health = SimpleNamespace(value="amber")
        stub = _StubExecutiveViewUseCase(view)
        _patch_executive_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["executive-view", "--plan-id", view.plan_id])

        assert exit_code == 0
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert "健康状态: amber（关注）" in lines
        assert "进度: 0/8（0%） | 当前: 无 | 降级: 0 步 | 最近活动: 无" in lines, f"规划空态行（实测={out!r}）"
        assert "Checkpoint: 共 0 | 已完成 0 | in_sync 0 | pending_sync 0 | invalidated 0" in lines
        assert "最近恢复: 无" in lines
        assert "近 7 天事件: 5 | 最近: 无" in lines, "审计空态半行（最近: 无——仅 stub 面可达形态）"
        assert "最新报告: 无（可先执行 report-generate）" in lines

    def test_malformed_plan_id_stderr_242(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """畸形 plan_id：CLI 守卫 242 → stderr [EXCEPTION_242] + exit 1 + 不触达用例."""
        stub = _StubExecutiveViewUseCase(_make_stub_view_sections())
        _patch_executive_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["executive-view", "--plan-id", "not-a-uuid"])

        assert exit_code == 1
        assert not stub.calls, "守卫失败后不得触达用例"
        assert "[EXCEPTION_242]" in capsys.readouterr().err

    def test_domain_error_stderr_exit_1(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """用例抛 DomainError → stderr [code] message + exit 1."""
        from src.domain.exceptions import PlanningNotFoundError

        stub = _StubExecutiveViewUseCase(error=PlanningNotFoundError(plan_id="123e4567-e89b-12d3-a456-426614174000"))
        _patch_executive_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["executive-view", "--plan-id", "123e4567-e89b-12d3-a456-426614174000"])

        assert exit_code == 1
        assert "[EXCEPTION_480]" in capsys.readouterr().err

    def test_build_degraded_mark_on_health_line(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """build_degraded=True → 健康行追加「（部分数据降级）」标记（AC-6）."""
        from types import SimpleNamespace

        view = _make_stub_view_sections()
        view.build_degraded = True
        view.health = SimpleNamespace(value="amber")
        stub = _StubExecutiveViewUseCase(view)
        _patch_executive_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["executive-view", "--plan-id", view.plan_id])

        assert exit_code == 0
        assert "健康状态: amber（关注）（部分数据降级）" in capsys.readouterr().out.splitlines()


# ===================================================================
# === Story 6-9: analyst-view 子命令（分析师作业入口——三段聚合视图）===
# ===================================================================


def _make_stub_analyst_view(
    *,
    plan_id: str | None = None,
    toolbox_degraded: bool = False,
    tools: tuple = (
        ("pestel-analysis", "PESTEL 分析", "environment_analysis"),
        ("competitor-analysis", "竞争对手分析", "competitive_analysis"),
    ),
    categories: tuple = (("environment_analysis", 1), ("competitive_analysis", 1)),
    progress_available: bool = True,
    completed: int = 3,
    total: int = 8,
    percent: int = 37,
    current_step: str | None = "market_customer",
    degraded_steps: int = 1,
    stages: tuple = (),
    stage_count: int = 2,
    chunk_count: int = 3,
    document_count: int = 3,
    jump_ready: int = 2,
    degraded_stage_count: int = 0,
    tree_build_degraded: bool = False,
    build_degraded: bool = False,
) -> Any:
    """analyst-view 视图替身工厂（getattr 零 VO import——6-3/6-8 先例形态）.

    stages 缺省时构造六阶段全景（1/7/0/0/0/0——k 表断言与验收形态对齐）。
    """
    from types import SimpleNamespace

    from src.application.ports.analyst_view import BLM_SIX_PHASES, PhaseStatus

    if not stages:
        stage_specs = (
            ("业绩差距分析", PhaseStatus.COMPLETED, 1, 1),
            ("市场洞察", PhaseStatus.IN_PROGRESS, 2, 7),
            ("战略意图与目标", PhaseStatus.NOT_STARTED, 0, 0),
            ("创新焦点", PhaseStatus.NOT_STARTED, 0, 0),
            ("业务设计", PhaseStatus.NOT_STARTED, 0, 0),
            ("执行设计", PhaseStatus.NOT_STARTED, 0, 0),
        )
        stages = tuple(
            SimpleNamespace(phase_key=key, phase_name=name, status=status, step_completed=done, step_total=total_)
            for (key, name), (_, status, done, total_) in zip(BLM_SIX_PHASES, stage_specs)
        )
    toolbox = SimpleNamespace(
        degraded=toolbox_degraded,
        total_tools=len(tools),
        tools=tuple(
            SimpleNamespace(slug=slug, tool_name=name, category=category, description=f"{slug} 描述", status="active")
            for slug, name, category in tools
        ),
        categories=tuple(SimpleNamespace(category=category, tool_count=count) for category, count in categories),
    )
    progress = SimpleNamespace(
        available=progress_available,
        degraded=False,
        phase="market_insight",
        current_step=current_step,
        completed_steps=completed,
        total_steps=total,
        progress_percent=percent,
        degraded_step_count=degraded_steps,
        stages=stages,
    )
    traceability = SimpleNamespace(
        available=stage_count > 0,
        degraded=False,
        stage_count=stage_count,
        chunk_count=chunk_count,
        document_count=document_count,
        jump_ready_count=jump_ready,
        degraded_stage_count=degraded_stage_count,
        tree_build_degraded=tree_build_degraded,
    )
    return SimpleNamespace(
        plan_id=plan_id or str(uuid.uuid4()),
        generated_at="2026-11-07T10:00:01+00:00",
        build_degraded=build_degraded,
        toolbox=toolbox,
        progress=progress,
        traceability=traceability,
    )


class _StubAnalystViewUseCase:
    """analyst-view 用例替身（记录调用参数/可编程视图或异常——_StubExecutiveViewUseCase 同款形态）."""

    def __init__(self, view: Any = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._view = view
        self._error = error

    async def execute(self, *, plan_id: str) -> Any:
        self.calls.append({"plan_id": plan_id})
        if self._error is not None:
            raise self._error
        return self._view


def _patch_analyst_view_entry(monkeypatch: pytest.MonkeyPatch, stub: _StubAnalystViewUseCase) -> None:
    """monkeypatch agent_cli 模块级 bootstrap/resolve（每命令族专用 patcher 纪律——6-8 R1-F11）."""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
    monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)


class TestAnalystViewParser:
    """analyst-view 参数解析（--plan-id 必填单参数——零可选参数 YAGNI）."""

    def test_parses_command_and_plan_id(self) -> None:
        """注册锚：build_parser 识别 analyst-view 子命令与 --plan-id."""
        args = agent_cli.build_parser().parse_args(["analyst-view", "--plan-id", "123e4567-e89b-12d3-a456-426614174000"])
        assert args.command == "analyst-view"
        assert args.plan_id == "123e4567-e89b-12d3-a456-426614174000"

    def test_missing_plan_id_exits_2(self) -> None:
        """缺 --plan-id → argparse SystemExit 2（argparse 原生用法错误承载）."""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["analyst-view"])
        assert exc_info.value.code == 2

    def test_no_optional_arguments(self) -> None:
        """零可选参数（无 --format/--category 过滤——YAGNI 钦定）."""
        import inspect

        source = inspect.getsource(agent_cli.build_parser)
        analyst_block = source.split('add_parser(\n        "analyst-view"')[1].split("add_parser(")[0]
        assert "--format" not in analyst_block
        assert "--category" not in analyst_block


class TestAnalystViewExecution:
    """analyst-view 执行（五步定式：守卫→bootstrap→resolve→打印→异常退码）."""

    def test_full_data_output(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """全数据：首行精确+三段分隔行+工具行+六阶段 6 行（status 中文+V1 注记后四）+溯源统计+提示行+exit 0."""
        view = _make_stub_analyst_view()
        stub = _StubAnalystViewUseCase(view)
        _patch_analyst_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["analyst-view", "--plan-id", view.plan_id])

        assert exit_code == 0
        assert stub.calls and stub.calls[0]["plan_id"] == view.plan_id
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert f"分析师视图（plan: {view.plan_id}）" in lines, f"首行应精确匹配（实测={out!r}）"
        for separator in ("── 专业工具箱 ──", "── BLM 进度 ──", "── 溯源摘要 ──"):
            assert separator in lines, f"三段分隔行缺失 {separator}（实测={out!r}）"
        assert "工具: 共 2 种（ACTIVE） | 分类: environment_analysis×1 competitive_analysis×1" in lines
        assert "  pestel-analysis — PESTEL 分析（environment_analysis）" in lines
        assert "进度: 3/8（37%） | 当前: market_customer | 降级: 1 步" in lines
        assert "  1. 业绩差距分析: [██████████] 已完成（1/1）" in lines
        assert "  2. 市场洞察: [███░░░░░░░] 进行中（2/7）" in lines
        v1_lines = [line for line in lines if "（V1 交付）" in line]
        assert len(v1_lines) == 4, f"后四阶段 V1 注记应恰 4 行（实测 {len(v1_lines)}）"
        assert "分析: 2 | 切片: 3 | 文档: 3 | 可跳转: 2" in lines
        assert f"提示: 执行 trace-tree --plan-id {view.plan_id} 查看完整溯源树" in lines

    def test_progress_bar_k_table_enumeration(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """进度条 k 表枚举：c=0..7 → [0,1,3,4,6,7,9,10] 逐格断言（±1 即红——R1-F11）."""
        from types import SimpleNamespace

        stages = tuple(
            SimpleNamespace(
                phase_key=f"p{index}",
                phase_name=f"阶段{index}",
                status=None,
                step_completed=completed,
                step_total=7,
            )
            for index, completed in enumerate(range(8))
        )
        view = _make_stub_analyst_view(stages=stages, progress_available=False)
        stub = _StubAnalystViewUseCase(view)
        _patch_analyst_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["analyst-view", "--plan-id", view.plan_id])

        assert exit_code == 0
        lines = capsys.readouterr().out.splitlines()
        expected_filled = [0, 1, 3, 4, 6, 7, 9, 10]
        bar_lines = [line for line in lines if ("[" in line and "█" in line) or ("[" in line and "░" in line)]
        filled_actual = [line.split("[")[1].split("]")[0].count("█") for line in bar_lines]
        assert filled_actual == expected_filled, f"k 表应 [0,1,3,4,6,7,9,10]（实测 {filled_actual}——round 公式 ±1 即红）"

    def test_empty_plan_output(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """空 plan：进度无快照行+六阶段框架行恒在+工具箱照常+溯源统计行全 0+exit 0."""
        from types import SimpleNamespace

        from src.application.ports.analyst_view import BLM_SIX_PHASES, PhaseStatus

        empty_stages = tuple(
            SimpleNamespace(phase_key=key, phase_name=name, status=PhaseStatus.NOT_STARTED, step_completed=0, step_total=total_)
            for (key, name), total_ in zip(BLM_SIX_PHASES, (1, 7, 0, 0, 0, 0))
        )
        view = _make_stub_analyst_view(
            progress_available=False,
            stages=empty_stages,  # 空 plan 六阶段全 not_started 框架（AC-3 P-empty 语义）
            stage_count=0,
            chunk_count=0,
            document_count=0,
            jump_ready=0,
        )
        stub = _StubAnalystViewUseCase(view)
        _patch_analyst_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["analyst-view", "--plan-id", view.plan_id])

        assert exit_code == 0
        lines = capsys.readouterr().out.splitlines()
        assert "进度: 无快照" in lines
        framework_lines = [line for line in lines if "未启动" in line]
        assert len(framework_lines) == 6, f"六阶段框架行恒在（实测 {len(framework_lines)}）"
        assert "  pestel-analysis — PESTEL 分析（environment_analysis）" in lines, "空 plan 工具箱照常"
        assert "分析: 0 | 切片: 0 | 文档: 0 | 可跳转: 0" in lines
        assert f"提示: 执行 trace-tree --plan-id {view.plan_id} 查看完整溯源树" in lines
        assert not any("降级 stage:" in line for line in lines), (
            "空 plan 降级 stage 行应缺席（子串扫描——list 全等负断言恒真，R1-F5）"
        )

    def test_current_step_none_fallback(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """current_step=None → 「当前: 无」fallback（6-8 :1519 直系——R3-F5）."""
        view = _make_stub_analyst_view(current_step=None)
        stub = _StubAnalystViewUseCase(view)
        _patch_analyst_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["analyst-view", "--plan-id", view.plan_id])

        assert exit_code == 0
        assert "进度: 3/8（37%） | 当前: 无 | 降级: 1 步" in capsys.readouterr().out.splitlines()

    def test_malformed_plan_id_stderr_242(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """畸形 plan_id：CLI 守卫 242 → stderr [EXCEPTION_242] + exit 1 + 不触达用例."""
        stub = _StubAnalystViewUseCase(_make_stub_analyst_view())
        _patch_analyst_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["analyst-view", "--plan-id", "not-a-uuid"])

        assert exit_code == 1
        assert not stub.calls, "守卫失败后不得触达用例"
        assert "[EXCEPTION_242]" in capsys.readouterr().err

    def test_domain_error_stderr_exit_1(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """用例抛 DomainError → stderr [EXCEPTION_480] + exit 1（五步定式第四步）."""
        from src.domain.exceptions import PlanningNotFoundError

        stub = _StubAnalystViewUseCase(error=PlanningNotFoundError(plan_id="123e4567-e89b-12d3-a456-426614174000"))
        _patch_analyst_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["analyst-view", "--plan-id", "123e4567-e89b-12d3-a456-426614174000"])

        assert exit_code == 1
        assert "[EXCEPTION_480]" in capsys.readouterr().err

    def test_degraded_marks_double_form(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """降级标记双形态并存（R3-F1）：build_degraded+tree_build_degraded 双 True →
        首行含「（部分数据降级）」+溯源统计行含「（部分树数据降级）」."""
        view = _make_stub_analyst_view(build_degraded=True, tree_build_degraded=True)
        stub = _StubAnalystViewUseCase(view)
        _patch_analyst_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["analyst-view", "--plan-id", view.plan_id])

        assert exit_code == 0
        lines = capsys.readouterr().out.splitlines()
        assert f"分析师视图（plan: {view.plan_id}）（部分数据降级）" in lines, "首行应含顶层降级标记"
        assert "分析: 2 | 切片: 3 | 文档: 3 | 可跳转: 2（部分树数据降级）" in lines, "溯源统计行应含树降级标记"

    def test_toolbox_degraded_single_line(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """工具箱段降级 → 「工具清单获取失败」单行（段降级形态——AC-6）."""
        view = _make_stub_analyst_view(toolbox_degraded=True)
        stub = _StubAnalystViewUseCase(view)
        _patch_analyst_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["analyst-view", "--plan-id", view.plan_id])

        assert exit_code == 0
        lines = capsys.readouterr().out.splitlines()
        assert "工具清单获取失败" in lines
        assert "  pestel-analysis — PESTEL 分析（environment_analysis）" not in lines

    def test_degraded_stage_count_line(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """degraded_stage_count>0 → 「降级 stage: n」行在位（仅非零时呈现）."""
        view = _make_stub_analyst_view(degraded_stage_count=2)
        stub = _StubAnalystViewUseCase(view)
        _patch_analyst_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["analyst-view", "--plan-id", view.plan_id])

        assert exit_code == 0
        assert "降级 stage: 2" in capsys.readouterr().out.splitlines()


# ===================================================================
# === Story 6-10: consultant-view 子命令（顾问交付入口——零参数全局视图）===
# ===================================================================


def _make_stub_consultant_view(
    *,
    plans: tuple = (
        (
            "11111111-1111-4111-8111-111111111111",
            3,
            "2026-11-08T10:00:00.000300+00:00",
            "pdf",
            "2026-11-08T10:00:00.000060+00:00",
            2,
        ),
        (
            "22222222-2222-4222-8222-222222222222",
            2,
            "2026-11-08T09:00:00.000090+00:00",
            "markdown",
            "2026-11-08T09:00:00.000040+00:00",
            1,
        ),
    ),
    plan_count: int | None = None,
    projects_degraded: bool = False,
    build_degraded: bool = False,
    plans_with_reports: int | None = None,
    plans_with_latest_pdf: int | None = None,
    latest_pdf_plan_id: str | None = "11111111-1111-4111-8111-111111111111",
    latest_pdf_object_key: str | None = "reports/plan/rid.pdf",
) -> Any:
    """consultant-view 视图替身工厂（getattr 零 VO import——SimpleNamespace 造 VO 树）.

    plans 六元组：(plan_id, archive_count, latest_activity_at, latest_report_type,
    latest_report_at, latest_degraded_section_count)。
    """
    from types import SimpleNamespace

    rows = tuple(
        SimpleNamespace(
            plan_id=plan_id,
            archive_count=count,
            latest_activity_at=activity,
            latest_report_type=report_type,
            latest_report_at=report_at,
            latest_degraded_section_count=degraded_sections,
        )
        for plan_id, count, activity, report_type, report_at, degraded_sections in plans
    )
    projects = SimpleNamespace(
        available=len(rows) > 0,
        degraded=projects_degraded,
        plan_count=plan_count if plan_count is not None else len(rows),
        projects=rows,
    )
    brand = SimpleNamespace(
        degraded=False,
        configured=False,
        logo_status="未配置（系统默认）",
        color_scheme_status="未配置（系统默认）",
        font_status="STSong-Light（内置）",
    )
    export = SimpleNamespace(
        available=(plans_with_reports if plans_with_reports is not None else 2) > 0,
        degraded=projects_degraded,
        plans_with_reports=plans_with_reports if plans_with_reports is not None else 2,
        plans_with_latest_pdf=plans_with_latest_pdf if plans_with_latest_pdf is not None else 1,
        latest_pdf_plan_id=latest_pdf_plan_id,
        latest_pdf_object_key=latest_pdf_object_key,
        latest_pdf_generated_at="2026-11-08T10:00:00.000060+00:00" if latest_pdf_plan_id else None,
    )
    return SimpleNamespace(
        generated_at="2026-11-08T10:00:01+00:00",
        build_degraded=build_degraded,
        projects=projects,
        brand=brand,
        export=export,
    )


class _StubConsultantViewUseCase:
    """consultant-view 用例替身（记录调用/可编程视图或异常——_StubAnalystViewUseCase 同款形态）."""

    def __init__(self, view: Any = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._view = view
        self._error = error

    async def execute(self) -> Any:
        self.calls.append({})
        if self._error is not None:
            raise self._error
        return self._view


def _patch_consultant_view_entry(monkeypatch: pytest.MonkeyPatch, stub: _StubConsultantViewUseCase) -> None:
    """monkeypatch agent_cli 模块级 bootstrap/resolve（每命令族专用 patcher 纪律——6-8 R1-F11/6-9 第三连）."""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
    monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)


class TestConsultantViewParser:
    """consultant-view 参数解析（零参数面真空——CLI 族首个零 add_argument 命令）."""

    def test_parses_command(self) -> None:
        """注册锚：build_parser 识别 consultant-view 子命令（零参数可裸调）."""
        args = agent_cli.build_parser().parse_args(["consultant-view"])
        assert args.command == "consultant-view"

    def test_any_argument_exits_2(self) -> None:
        """任意参数 → argparse unrecognized exit 2（参数面真空——多项目面板无过滤/分页需求 YAGNI）."""
        with pytest.raises(SystemExit) as exc_info:
            agent_cli.build_parser().parse_args(["consultant-view", "--plan-id", "x"])
        assert exc_info.value.code == 2

    def test_zero_add_argument_calls(self) -> None:
        """零参数面 getsource 断言：注册块内零 add_argument 调用（与 isolation-logs 可选参数面分立）."""
        import inspect

        source = inspect.getsource(agent_cli.build_parser)
        block = source.split('add_parser(\n        "consultant-view"')[1].split("add_parser(")[0]
        assert "add_argument" not in block, "参数面真空（首个零 add_argument 命令——AC-6 钦定）"


class TestConsultantViewExecution:
    """consultant-view 执行（三段打印+退出语义——输出即契约纯标准库 print）."""

    def test_full_data_output(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """全数据：首行+三段分隔行+项目行两行形态+品牌两行+导出三行+提示行+exit 0."""
        view = _make_stub_consultant_view()
        stub = _StubConsultantViewUseCase(view)
        _patch_consultant_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["consultant-view"])

        assert exit_code == 0
        assert stub.calls, "用例应被调用（零参 execute）"
        lines = capsys.readouterr().out.splitlines()
        assert "顾问视图（全局多项目面板）" in lines, f"首行应精确（实测={lines!r}）"
        for separator in ("── 多项目概况 ──", "── 品牌配置 ──", "── 白标导出 ──"):
            assert separator in lines, f"三段分隔行缺失 {separator}"
        assert "项目: 共 2 个" in lines
        assert "  11111111-1111-4111-8111-111111111111 | 归档: 3 | 最新活动: 2026-11-08 10:00" in lines
        assert "    最新报告: pdf（2026-11-08 10:00，降级小节 2）" in lines, "两行形态（信息密度呈现拆两行）"
        assert "    最新报告: 无" not in lines, "有报告行不降无报告行"
        assert "品牌模板: 未配置 | Logo: 未配置（系统默认） | 配色: 未配置（系统默认） | 字体: STSong-Light（内置）" in lines
        assert "提示: 执行 brand-template-save 配置品牌模板" in lines, "品牌提示行恒在（6-11 v1.1.0 新文案）"
        assert "可交付: 2 项目有报告 | 最新 PDF: 1 项目" in lines
        assert "  最新 PDF: 11111111-1111-4111-8111-111111111111" in lines
        assert "  对象键: reports/plan/rid.pdf" in lines
        assert "提示: 执行 report-generate --plan-id <uuid> --format pdf 生成白标 PDF" in lines

    def test_empty_state_output(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """空态：项目共 0 后无行+品牌两行恒在+导出空态行+exit 0（空态是正常态）."""
        view = _make_stub_consultant_view(
            plans=(),
            plan_count=0,
            plans_with_reports=0,
            plans_with_latest_pdf=0,
            latest_pdf_plan_id=None,
            latest_pdf_object_key=None,
        )
        stub = _StubConsultantViewUseCase(view)
        _patch_consultant_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["consultant-view"])

        assert exit_code == 0
        lines = capsys.readouterr().out.splitlines()
        head = lines.index("项目: 共 0 个")
        brand_separator = lines.index("── 品牌配置 ──")
        project_body = lines[head + 1 : brand_separator]
        assert project_body == [], f"空态项目计数行与品牌段之间应无任何行（实测 {project_body!r}）"
        assert "品牌模板: 未配置 | Logo: 未配置（系统默认） | 配色: 未配置（系统默认） | 字体: STSong-Light（内置）" in lines
        assert "可交付: 0 项目有报告 | 最新 PDF: 0 项目" in lines
        assert "  最新 PDF: 无" in lines, "零 PDF 定位行降无"

    def test_zero_report_plan_row(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """零报告 plan 行：最新报告行降「无」（有活动无交付物形态）."""
        view = _make_stub_consultant_view(
            plans=(("33333333-3333-4333-8333-333333333333", 1, "2026-11-08T08:00:00.000070+00:00", None, None, None),),
            plan_count=1,
            plans_with_reports=0,
            plans_with_latest_pdf=0,
            latest_pdf_plan_id=None,
            latest_pdf_object_key=None,
        )
        stub = _StubConsultantViewUseCase(view)
        _patch_consultant_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["consultant-view"])

        assert exit_code == 0
        lines = capsys.readouterr().out.splitlines()
        assert "  33333333-3333-4333-8333-333333333333 | 归档: 1 | 最新活动: 2026-11-08 08:00" in lines
        assert "    最新报告: 无" in lines, "零报告行降无报告行"

    def test_degraded_mark_and_single_line(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """find 级降级格：build_degraded 首行追加标记；projects 段降级（degraded+空清单）降「项目清单获取失败」单行.

        段降级两形态分立（OD-12 呈现面）：find 级=段值降默认（空清单）——本格；
        循环级=清单保留——test_partial_degraded_keeps_listing 承载。导出七键随形态
        置零（矛盾 VO 纪律——清单获取失败与「2 报告」并存属 stub 自身缺陷）。
        """
        view = _make_stub_consultant_view(
            plans=(),
            plan_count=0,
            projects_degraded=True,
            build_degraded=True,
            plans_with_reports=0,
            plans_with_latest_pdf=0,
            latest_pdf_plan_id=None,
            latest_pdf_object_key=None,
        )
        stub = _StubConsultantViewUseCase(view)
        _patch_consultant_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["consultant-view"])

        assert exit_code == 0
        lines = capsys.readouterr().out.splitlines()
        assert "顾问视图（全局多项目面板）（部分数据降级）" in lines, "首行含顶层降级标记（6-8/6-9 直系）"
        assert "项目清单获取失败" in lines, "find 级项目段降级行"
        assert "可交付: 0 项目有报告 | 最新 PDF: 0 项目" in lines, "导出段降级值级（段值降默认）"

    def test_partial_degraded_keeps_listing(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """循环级降级格：degraded+清单保留 → 照常呈现清单（行报告列 None 呈「最新报告: 无」）+不降「获取失败」单行.

        OD-12 循环级=清单保留+行报告列 None（「部分降级」语义的呈现面）——清单
        已取到的行不得因单 plan 点查失败被丢弃；降级信号由首行标记承载。
        """
        view = _make_stub_consultant_view(
            plans=(("44444444-4444-4444-8444-444444444444", 2, "2026-11-08T07:30:00.000080+00:00", None, None, None),),
            plan_count=1,
            projects_degraded=True,
            build_degraded=True,
            plans_with_reports=0,
            plans_with_latest_pdf=0,
            latest_pdf_plan_id=None,
            latest_pdf_object_key=None,
        )
        stub = _StubConsultantViewUseCase(view)
        _patch_consultant_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["consultant-view"])

        assert exit_code == 0
        lines = capsys.readouterr().out.splitlines()
        assert "顾问视图（全局多项目面板）（部分数据降级）" in lines, "首行含顶层降级标记"
        assert "项目清单获取失败" not in lines, "循环级降级清单保留——不得降获取失败单行"
        assert "项目: 共 1 个" in lines, "清单照常呈现"
        assert "  44444444-4444-4444-8444-444444444444 | 归档: 2 | 最新活动: 2026-11-08 07:30" in lines, "清单行在场"
        assert "    最新报告: 无" in lines, "循环级行报告列 None 呈现「无」"

    def test_domain_error_stderr_exit_1(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """用例抛 DomainError → stderr [EXCEPTION_ 前缀+exit 1（防御性兜底——段级容错下不可达，兜底结构照设）."""
        from src.domain.exceptions import PlanningNotFoundError

        stub = _StubConsultantViewUseCase(error=PlanningNotFoundError(plan_id="11111111-1111-4111-8111-111111111111"))
        _patch_consultant_view_entry(monkeypatch, stub)

        exit_code = agent_cli.main(["consultant-view"])

        assert exit_code == 1
        assert "[EXCEPTION_" in capsys.readouterr().err


# ===================================================================
# Story 6-11: brand-template-save / brand-template-list 两新命令 +
# report-generate --brand-template 同入口扩展（17→19 命令族）
# ===================================================================


class _StubBrandTemplate:
    """品牌模板实体替身（getattr 属性面消费——零实体 import 依赖）。"""

    def __init__(self, *, name: str = "商务蓝模板", template_id=None, logo_object_key=None) -> None:
        import uuid as uuid_mod

        self.name = name
        self.template_id = template_id or uuid_mod.uuid4()
        self.color_scheme = "corporate-blue"
        self.font_preset = "noto-sans-sc"
        self.logo_object_key = logo_object_key
        self.updated_at = None


class _StubSaveBrandTemplateUseCase:
    """SaveBrandTemplateUseCase 替身（记录调用+可注入异常）。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.result = _StubBrandTemplate()

    async def execute(self, *, name: str, color_scheme: str, font_preset: str, logo_path=None) -> object:
        """替身 execute（记录调用）。"""
        self.calls.append({"name": name, "color_scheme": color_scheme, "font_preset": font_preset, "logo_path": logo_path})
        if self.error is not None:
            raise self.error
        return self.result


class _StubListBrandTemplatesUseCase:
    """ListBrandTemplatesUseCase 替身（零参 execute）。"""

    def __init__(self, rows=None) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.rows = rows if rows is not None else []

    async def execute(self) -> object:
        """替身 execute（记录调用）。"""
        self.calls.append({})
        if self.error is not None:
            raise self.error
        return tuple(self.rows)


class _StubReportGenerateBrandUseCase(_StubReportGenerateUseCase):
    """report-generate 品牌态替身（plan_id+brand_template_name 双参记录）。

    继承基桩（is-a 关系——v1.1.0 增参形态的 LSP 兼容覆写：增带默认值的
    keyword-only 参数；兼容 _patch_report_generate_entry 单一签名注入）。
    """

    def __init__(self) -> None:
        super().__init__()
        self.calls = []

    async def execute(self, *, plan_id: str, brand_template_name: str | None = None) -> object:
        """替身 execute（记录双参——透传断言锚）。"""
        self.calls.append({"plan_id": plan_id, "brand_template_name": brand_template_name})
        return self.result


def _patch_brand_save_entry(monkeypatch: pytest.MonkeyPatch, stub: _StubSaveBrandTemplateUseCase) -> None:
    """brand-template-save 入口替身注入（每命令族专用 patcher 纪律）。"""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
    monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)


def _patch_brand_list_entry(monkeypatch: pytest.MonkeyPatch, stub: _StubListBrandTemplatesUseCase) -> None:
    """brand-template-list 入口替身注入。"""
    monkeypatch.setattr(agent_cli, "bootstrap", lambda: None)
    monkeypatch.setattr(agent_cli, "resolve", lambda name: stub)


class TestBrandTemplateSaveParser:
    """brand-template-save 参数解析（--name/--color-scheme/--font-preset/--logo-path）。"""

    def test_full_args_parsed(self) -> None:
        """全参解析（四参数键+choices 值域面）。"""
        parser = agent_cli.build_parser()
        args = parser.parse_args(
            [
                "brand-template-save",
                "--name",
                "商务蓝模板",
                "--color-scheme",
                "corporate-blue",
                "--font-preset",
                "noto-sans-sc",
                "--logo-path",
                "/tmp/logo.png",
            ]
        )
        assert args.command == "brand-template-save"
        assert args.name == "商务蓝模板"
        assert args.color_scheme == "corporate-blue"
        assert args.font_preset == "noto-sans-sc"
        assert args.logo_path == "/tmp/logo.png"

    def test_logo_path_optional_default_none(self) -> None:
        """--logo-path 可选（缺省 None——logo 缺席=保留语义）。"""
        parser = agent_cli.build_parser()
        args = parser.parse_args(
            ["brand-template-save", "--name", "x", "--color-scheme", "graphite", "--font-preset", "stsong"]
        )
        assert args.logo_path is None

    def test_missing_name_exits_two(self) -> None:
        """缺 --name → exit 2（必填）。"""
        parser = agent_cli.build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["brand-template-save", "--color-scheme", "graphite", "--font-preset", "stsong"])
        assert exc_info.value.code == 2

    def test_invalid_color_scheme_exits_two(self) -> None:
        """非法 --color-scheme → argparse choices 硬拦截 exit 2（第一道 UX 面
        ——深层 494 值域校验经编程面 use case 直调触达）。"""
        parser = agent_cli.build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["brand-template-save", "--name", "x", "--color-scheme", "neon-pink", "--font-preset", "stsong"])
        assert exc_info.value.code == 2

    def test_invalid_font_preset_exits_two(self) -> None:
        """非法 --font-preset → exit 2。"""
        parser = agent_cli.build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(
                ["brand-template-save", "--name", "x", "--color-scheme", "graphite", "--font-preset", "comic-sans"]
            )
        assert exc_info.value.code == 2

    def test_block_boundary_getsource_no_format_words(self) -> None:
        """切块边界断言（getsource 块内禁 --format/--plan-id 字样——6-9 教训
        第四连：措辞纪律防切块断言边界污染）。"""
        import inspect

        source = inspect.getsource(agent_cli.build_parser)
        block = source.split('add_parser(\n        "brand-template-save"')[1].split("add_parser(")[0]
        assert "--format" not in block and "--plan-id" not in block


class TestBrandTemplateListParser:
    """brand-template-list 参数解析（零参数全局清单）。"""

    def test_zero_args_parsed(self) -> None:
        """零参解析（全局模板清单——CLI 族第二个零参数命令）。"""
        parser = agent_cli.build_parser()
        args = parser.parse_args(["brand-template-list"])
        assert args.command == "brand-template-list"

    def test_any_argument_exits_two(self) -> None:
        """任意参数 → exit 2（零参数面）。"""
        parser = agent_cli.build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["brand-template-list", "--anything"])
        assert exc_info.value.code == 2


class TestBrandTemplateSaveExecution:
    """brand-template-save 执行入口（五步定式——写命令模板）。"""

    def test_success_output_contract(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """成功输出契约（保存行+配置行+模板标识行）。"""
        stub = _StubSaveBrandTemplateUseCase()
        _patch_brand_save_entry(monkeypatch, stub)
        exit_code = agent_cli.main(
            [
                "brand-template-save",
                "--name",
                "商务蓝模板",
                "--color-scheme",
                "corporate-blue",
                "--font-preset",
                "noto-sans-sc",
            ]
        )
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "品牌模板已保存: 商务蓝模板" in out.splitlines()
        assert "配色: 商务蓝 | 字体: Noto Sans SC（黑体） | Logo: 未设置" in out
        assert f"模板标识: {stub.result.template_id}" in out
        # 透传值级断言
        assert stub.calls == [
            {"name": "商务蓝模板", "color_scheme": "corporate-blue", "font_preset": "noto-sans-sc", "logo_path": None}
        ]

    def test_empty_name_exit_1_stderr_242(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """空名：exit 1 + stderr [EXCEPTION_242]（R3-F2——本命令 242 专属锚补格：
        argparse required 只管旗标在场，空串必达 use case；杀「CLI 层加空名
        守卫提前拦截」与「except 域收窄排除校验子类」两突变体）。"""
        stub = _StubSaveBrandTemplateUseCase()
        from src.domain.exceptions import EntityValidationError

        stub.error = EntityValidationError(
            message="品牌模板名不可为空",
            context={"use_case": "SaveBrandTemplateUseCase", "field": "name"},
        )
        _patch_brand_save_entry(monkeypatch, stub)

        exit_code = agent_cli.main(
            ["brand-template-save", "--name", "", "--color-scheme", "corporate-blue", "--font-preset", "stsong"]
        )

        assert exit_code == 1
        stderr = capsys.readouterr().err
        assert "[EXCEPTION_242]" in stderr

    def test_success_with_logo_uploaded_wording(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path
    ) -> None:
        """带 logo 成功（Logo: 已上传 形态——服务返回体携带 logo_object_key）。"""
        logo = tmp_path / "logo.png"
        logo.write_bytes(b"\x89PNG\r\n\x1a\nstub")
        stub = _StubSaveBrandTemplateUseCase()
        stub.result = _StubBrandTemplate(name="x", logo_object_key="logos/uploaded")
        _patch_brand_save_entry(monkeypatch, stub)
        exit_code = agent_cli.main(
            [
                "brand-template-save",
                "--name",
                "x",
                "--color-scheme",
                "graphite",
                "--font-preset",
                "stsong",
                "--logo-path",
                str(logo),
            ]
        )
        assert exit_code == 0
        assert "Logo: 已上传" in capsys.readouterr().out

    def test_domain_error_494_stderr_exit_one(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """DomainError：[EXCEPTION_494] stderr + exit 1（双层异常定式）。"""
        from src.domain.exceptions import BrandTemplateValidationError

        stub = _StubSaveBrandTemplateUseCase()
        stub.error = BrandTemplateValidationError(field="logo_path", message="Logo 文件非法")
        _patch_brand_save_entry(monkeypatch, stub)
        exit_code = agent_cli.main(
            ["brand-template-save", "--name", "x", "--color-scheme", "graphite", "--font-preset", "stsong"]
        )
        assert exit_code == 1
        assert "[EXCEPTION_494]" in capsys.readouterr().err

    def test_unexpected_error_exit_one(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """意外异常：exit 1（双层定式第二层）。"""
        stub = _StubSaveBrandTemplateUseCase()
        stub.error = RuntimeError("意外故障")
        _patch_brand_save_entry(monkeypatch, stub)
        exit_code = agent_cli.main(
            ["brand-template-save", "--name", "x", "--color-scheme", "graphite", "--font-preset", "stsong"]
        )
        assert exit_code == 1


class TestBrandTemplateListExecution:
    """brand-template-list 执行入口。"""

    def test_rows_output_contract(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """多行输出契约（首行计数+逐模板行呈现名+行序 updated_at 降序由服务
        返回序承载——CLI 只呈现）。"""
        rows = [
            _StubBrandTemplate(name="模板甲"),
            _StubBrandTemplate(name="模板乙"),
        ]
        stub = _StubListBrandTemplatesUseCase(rows=rows)
        _patch_brand_list_entry(monkeypatch, stub)
        exit_code = agent_cli.main(["brand-template-list"])
        assert exit_code == 0
        out_lines = capsys.readouterr().out.splitlines()
        assert "品牌模板: 共 2 个" in out_lines
        row_lines = [line for line in out_lines if line.startswith("  ")]
        assert len(row_lines) == 2
        assert any("模板甲" in line and "配色: 商务蓝" in line for line in row_lines)

    def test_empty_state_output(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """空态输出（共 0 个+恒在提示行——指向 brand-template-save）。"""
        stub = _StubListBrandTemplatesUseCase(rows=[])
        _patch_brand_list_entry(monkeypatch, stub)
        exit_code = agent_cli.main(["brand-template-list"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "品牌模板: 共 0 个" in out
        assert "提示: 执行 brand-template-save 配置品牌模板" in out

    def test_domain_error_stderr_exit_one(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """DomainError 495：stderr + exit 1。"""
        from src.domain.exceptions import BrandTemplateStorageError

        stub = _StubListBrandTemplatesUseCase()
        stub.error = BrandTemplateStorageError(layer="l2")
        _patch_brand_list_entry(monkeypatch, stub)
        exit_code = agent_cli.main(["brand-template-list"])
        assert exit_code == 1
        assert "[EXCEPTION_495]" in capsys.readouterr().err


class TestReportGenerateBrandTemplate:
    """report-generate --brand-template 同入口扩展（6-5b OD-11 兑现）。"""

    def test_brand_template_param_optional_default_none(self) -> None:
        """--brand-template 可选默认 None（自由名非枚举——模板名非 choices）。"""
        parser = agent_cli.build_parser()
        args = parser.parse_args(["report-generate", "--plan-id", "p1"])
        assert getattr(args, "brand_template", None) is None

    def test_brand_template_free_name_parsed(self) -> None:
        """--brand-template 自由名解析（choices 不限——模板名非枚举值）。"""
        parser = agent_cli.build_parser()
        args = parser.parse_args(["report-generate", "--plan-id", "p1", "--format", "pdf", "--brand-template", "任意自定义名"])
        assert args.brand_template == "任意自定义名"

    def test_combination_guard_markdown_brand_494(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """组合守卫：--brand-template+--format markdown → [EXCEPTION_494]
        stderr exit 1（post-parse 检测归 CLI 层唯一落位——bootstrap 前，
        守卫先于用例零调用）。"""
        stub = _StubReportGenerateBrandUseCase()
        _patch_report_generate_entry(monkeypatch, stub)
        exit_code = agent_cli.main(
            ["report-generate", "--plan-id", str(uuid.uuid4()), "--format", "markdown", "--brand-template", "any"]
        )
        assert exit_code == 1
        assert "[EXCEPTION_494]" in capsys.readouterr().err
        assert not stub.calls

    def test_brand_template_passthrough(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """透传格：--brand-template X → use case 调用参数锚（X 入参+品牌增量行）。"""
        stub = _StubReportGenerateBrandUseCase()
        _patch_report_generate_entry(monkeypatch, stub)
        plan_id = str(uuid.uuid4())
        exit_code = agent_cli.main(
            ["report-generate", "--plan-id", plan_id, "--format", "pdf", "--brand-template", "商务蓝模板"]
        )
        assert exit_code == 0
        assert stub.calls == [{"plan_id": plan_id, "brand_template_name": "商务蓝模板"}]
        out = capsys.readouterr().out
        assert "品牌模板: 商务蓝模板（已应用）" in out

    def test_default_format_zero_change(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """默认格：无 --brand-template → 既有调用形态零变化（None 透传）。"""
        stub = _StubReportGenerateBrandUseCase()
        _patch_report_generate_entry(monkeypatch, stub)
        plan_id = str(uuid.uuid4())
        exit_code = agent_cli.main(["report-generate", "--plan-id", plan_id, "--format", "pdf"])
        assert exit_code == 0
        assert stub.calls == [{"plan_id": plan_id, "brand_template_name": None}]
        assert "品牌模板:" not in capsys.readouterr().out.split("报告生成完成")[0]
