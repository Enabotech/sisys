"""CLI 入口标准化单测（Task 4——AC-6：6.8-R1-DF1 + 5-7 R1-DF6 核销）。

循环 A：显式 load_dotenv（OD-7 三选一定谳——入口显式加载）：
    - tmp_path 写 .env + 指定路径 → 目标键注入 os.environ（纯语义红锚——
      删 load_dotenv 调用即红；in-process「.env 失效复现」结构性不可达
      [conftest _bootstrap_once 已填充 registry]——裸跑复现归 subprocess/e2e 面）
    - override=False：已设键不被覆盖
    - SISYS_USE_TEST_PORTS=1 测试形态守卫跳过（.env 被 git 追踪——进程内
      注入泄漏非端口键污染同 worker 后续场景，R1-19）

循环 B：SIGTERM 优雅退出（OD-9 最小处置——信号 handler 精确刷盘）：
    - handler 函数存在性与注册（main() 调用后 getsignal 非 default）
    - handler 直调安全（未激活 tracer 零动作——弱化断言已注明；span 刷盘
      强计数断言归本文件 mock 面[单测 mock 合法]）
"""

from __future__ import annotations

import signal
from pathlib import Path
from typing import Any

import pytest


class TestLoadEnvSemantics:
    """load_env 纯语义（双入口复用单函数——Task 4.4 收敛位）。"""

    def test_dotenv_injects_custom_keys(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """指定路径 .env 的自定义键注入 os.environ（删 load_dotenv 即红锚①）。"""
        from src.entrypoints import cli_main

        monkeypatch.delenv("SISYS_USE_TEST_PORTS", raising=False)
        dotenv_path = tmp_path / ".env"
        # 测试探针键值（detect-secrets 高熵误报——pragma 标注）
        dotenv_path.write_text("CLI7_UNIT_PROBE_KEY=from_env_file\n", encoding="utf-8")  # pragma: allowlist secret
        monkeypatch.delenv("CLI7_UNIT_PROBE_KEY", raising=False)

        cli_main.load_env(dotenv_path=str(dotenv_path))

        import os

        assert os.environ.get("CLI7_UNIT_PROBE_KEY") == "from_env_file", ".env 键未注入（load_dotenv 缺失或未生效）"

    def test_override_false_keeps_existing_keys(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """override=False：已存在键不被覆盖（锚②）。"""
        from src.entrypoints import cli_main

        monkeypatch.delenv("SISYS_USE_TEST_PORTS", raising=False)
        dotenv_path = tmp_path / ".env"
        dotenv_path.write_text("CLI7_UNIT_EXISTING_KEY=from_env_file\n", encoding="utf-8")
        monkeypatch.setenv("CLI7_UNIT_EXISTING_KEY", "preset_in_environ")

        cli_main.load_env(dotenv_path=str(dotenv_path))

        import os

        assert os.environ.get("CLI7_UNIT_EXISTING_KEY") == "preset_in_environ", "override=False 失效（已设键被覆盖）"

    def test_test_ports_guard_skips_loading(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """SISYS_USE_TEST_PORTS=1 跳过 .env 加载（测试形态守卫——R1-19）。"""
        from src.entrypoints import cli_main

        monkeypatch.setenv("SISYS_USE_TEST_PORTS", "1")
        dotenv_path = tmp_path / ".env_guard"
        # 测试探针键值（detect-secrets 高熵误报——pragma 标注）
        dotenv_path.write_text("CLI7_UNIT_GUARD_KEY=should_not_inject\n", encoding="utf-8")  # pragma: allowlist secret
        monkeypatch.delenv("CLI7_UNIT_GUARD_KEY", raising=False)

        cli_main.load_env(dotenv_path=str(dotenv_path))

        import os

        assert os.environ.get("CLI7_UNIT_GUARD_KEY") is None, "测试形态守卫失效（TEST_PORTS=1 应跳过加载）"

    def test_missing_dotenv_file_no_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """无 .env 文件零报错（缺省仓库根探测——不存在即直通）。"""
        from src.entrypoints import cli_main

        monkeypatch.delenv("SISYS_USE_TEST_PORTS", raising=False)
        cli_main.load_env(dotenv_path=str(tmp_path / "nonexistent.env"))  # 不抛即通过

    def test_agent_cli_compatible_entry_mounts_load_env(self) -> None:
        """兼容入口同链复用（agent_cli 源码含 load_dotenv 显式挂载——AC-6④）。"""
        agent_cli_path = Path(__file__).resolve().parents[3] / "src" / "entrypoints" / "agent_cli.py"
        source = agent_cli_path.read_text(encoding="utf-8")
        assert "load_env" in source, "兼容入口未挂载 load_env（双入口复用缺失）"

    def test_main_entry_invokes_load_env_behaviorally(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() 调用点行为级红锚（R1-T2——CI 无 e2e 执行位的盲区补齐）。

        既有「源码含 load_env 字样」文本断言对调用点删除不红（函数定义即绿）；
        本用例 monkeypatch 计数包装 cli_main.load_env，断言 main() 真实触达
        ——删 cli_main.main 内 load_env() 调用行即红（6.8-R1-DF1 核销本体）。
        """
        from src.entrypoints import cli_main

        calls: list[str] = []
        original = cli_main.load_env

        def _counting_load_env(*args: Any, **kwargs: Any) -> None:
            calls.append("load_env")
            original(*args, **kwargs)

        monkeypatch.setattr(cli_main, "load_env", _counting_load_env)
        exit_code = cli_main.main(["--help"])
        assert exit_code == 0
        assert calls == ["load_env"], "main() 未触达 load_env 调用点（6.8-R1-DF1 核销链断裂）"


class TestSignalHandler:
    """SIGTERM/SIGINT 优雅退出 handler（OD-9——handler 直调单测形态）。"""

    def test_handle_termination_signal_exists(self) -> None:
        """handler 函数在 cli_main 定义（组装层——entrypoints 设计使然）。"""
        from src.entrypoints import cli_main

        assert callable(getattr(cli_main, "handle_termination_signal", None)), "缺信号处理函数 handle_termination_signal"

    def test_handler_direct_call_safe_without_tracer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """handler 直调安全（未激活 tracer 零动作——peek 受控隔离真实 tracer）。"""
        from src.entrypoints import cli_main

        class _ResolverStub:
            def peek_singleton(self, name: str) -> Any:
                return None  # 未激活 tracer 形态（隔离真实 tracer 的 flush 黑洞）

        monkeypatch.setattr(cli_main, "get_resolver", lambda: _ResolverStub())
        monkeypatch.setattr(cli_main.os, "_exit", lambda code: None)  # 无 loop 分支直退拦截
        cli_main.handle_termination_signal(signal.SIGTERM, None)  # 不抛即通过（同步面降级）

    def test_handler_flushes_tracer_when_activated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """激活 tracer 时 shutdown 被调（mock peek_singleton——单测合法）。"""
        from src.entrypoints import cli_main

        calls: list[str] = []

        class _TracerStub:
            def shutdown(self, timeout_sec: int = 5) -> None:
                calls.append("shutdown")

        class _ResolverStub:
            def peek_singleton(self, name: str) -> Any:
                calls.append(f"peek:{name}")
                return _TracerStub() if name == "agent_tracing" else None

        monkeypatch.setattr(cli_main, "get_resolver", lambda: _ResolverStub())
        monkeypatch.setattr(cli_main.os, "_exit", lambda code: calls.append(f"exit:{code}"))
        cli_main.handle_termination_signal(signal.SIGTERM, None)
        assert "shutdown" in calls, "激活 tracer 未刷盘（shutdown 未调用）"
        # R1-F9：退出码 128+signum（POSIX 惯例——中断不再上报 exit 0 成功态；
        # 无运行 loop 分支直退路径）
        assert f"exit:{128 + signal.SIGTERM}" in calls, "信号退出码非 128+signum（中断被上报为成功态）"

    def test_register_signal_handlers_in_main_thread(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """register_signal_handlers 注册后 getsignal 非 default（守卫解除+测试后恢复）。"""
        import os

        from src.entrypoints import cli_main

        monkeypatch.delenv("SISYS_USE_TEST_PORTS", raising=False)  # 解除测试形态守卫
        original_term = signal.getsignal(signal.SIGTERM)
        original_int = signal.getsignal(signal.SIGINT)
        monkeypatch.setattr(os, "_exit", lambda code: None)  # 直退拦截（monkeypatch 自动恢复）
        try:
            cli_main.register_signal_handlers()
            assert signal.getsignal(signal.SIGTERM) is not signal.SIG_DFL, "SIGTERM 未注册 handler"
            assert signal.getsignal(signal.SIGINT) is not signal.SIG_DFL, "SIGINT 未注册 handler"
        finally:
            signal.signal(signal.SIGTERM, original_term)
            signal.signal(signal.SIGINT, original_int)

    def test_register_guarded_under_test_ports(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试形态守卫：TEST_PORTS=1 下注册跳过（pytest/xdist 信号机制保护）。"""
        from src.entrypoints import cli_main

        monkeypatch.setenv("SISYS_USE_TEST_PORTS", "1")
        original_term = signal.getsignal(signal.SIGTERM)
        cli_main.register_signal_handlers()
        assert signal.getsignal(signal.SIGTERM) is original_term, "测试形态下不应注册（信号劫持）"

    def test_flush_and_exit_survives_broken_pipe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """stdout flush 抛 BrokenPipeError 时退出码契约保真（R3 补锁——R2 flush 防护）。"""
        import io

        from src.entrypoints import cli_main

        exits: list[int] = []

        def _broken_flush() -> None:
            raise BrokenPipeError("pipe closed")

        monkeypatch.setattr(cli_main.sys, "stdout", type("BrokenOut", (), {"flush": _broken_flush})())
        monkeypatch.setattr(cli_main.sys, "stderr", io.StringIO())
        monkeypatch.setattr(cli_main.os, "_exit", lambda code: exits.append(code))
        cli_main._flush_and_exit(signal.SIGTERM)
        assert exits == [128 + signal.SIGTERM], f"flush 失败应不阻断按码退出: {exits}"
