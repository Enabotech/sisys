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
