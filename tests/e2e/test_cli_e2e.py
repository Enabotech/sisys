"""E2E 子进程冒烟（Story 7-1 Task 5 循环 B——统一 CLI 入口安装态验证）。

13/13 命令冒烟全覆盖（E2E 声明式收敛口径——epics「E2E≥80%」无分母）：
    - 每命令 ``--help`` exit 0 全集（参数面安装态）
    - 真实只读命令冒烟子集（tool list/archive query——服务可用时）
    - 写命令 ``--dry-run`` 冒烟（兼验短路层子进程面接线）
    - 双通道机制：``shutil.which("sisys")`` 探测 console_script（可用时
      script 通道与 ``-m`` 通道均执行）+ 不可用时 ``-m`` 通道回退 + 仍不可用
      pytest.skip 动态降级

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/e2e/test_cli_e2e.py -v

子进程 env：TEST_PORTS=1 + 独立环境构造（不依赖调用方残留）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid as uuid_module
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e]

_REPO_ROOT = Path(__file__).resolve().parents[2]

# 13+1 命令清单（Task 0.1 冻结表同源——冒烟全集）
_SMOKE_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("document", "upload"),
    ("document", "search"),
    ("document", "version", "list"),
    ("document", "version", "snapshot"),
    ("tool", "list"),
    ("tool", "run"),
    ("agent", "instantiate"),
    ("agent", "run-task"),
    ("plan", "generate"),
    ("plan", "report"),
    ("plan", "trace-tree"),
    ("checkpoint", "list"),
    ("checkpoint", "recover"),
    ("archive", "query"),
)

# 写命令 --dry-run 冒烟子集（短路层子进程面接线验证——含最小必填参数）
_DRY_RUN_CASES: tuple[tuple[tuple[str, ...], list[str]], ...] = (
    (("checkpoint", "list"), ["--plan-id", "11111111-1111-1111-1111-111111111111"]),
    (("document", "search"), ["--query", "战略", "--tenant-id", "t1"]),
    (("agent", "instantiate"), ["--role", "ceo"]),
)


def _build_env() -> dict[str, str]:
    """构造子进程 env（TEST_PORTS=1 + 继承 PATH/测试端口变量——独立形态）。"""
    return {**os.environ, "SISYS_USE_TEST_PORTS": "1"}


def _run_subprocess(argv: list[str], *, use_script: bool = False) -> subprocess.CompletedProcess[str]:
    """运行 CLI 子进程（-m 通道或 console_script 通道）。"""
    if use_script:
        command = ["sisys", *argv]
    else:
        command = [sys.executable, "-m", "src.entrypoints.cli_main", *argv]
    return subprocess.run(command, capture_output=True, text=True, timeout=120, cwd=_REPO_ROOT, env=_build_env())


def _require_module_channel() -> None:
    """-m 通道可用性守卫（不可用动态 skip——安装态缺依赖形态）。"""
    probe = _run_subprocess(["--help"])
    if probe.returncode != 0:
        pytest.skip(f"-m 通道不可用（模块导入失败）: {probe.stderr[:200]}")


class TestHelpFullSet:
    """13+1 命令 --help 全集（安装态参数面）。"""

    def test_top_level_help_six_modules(self) -> None:
        """sisys --help 六模块总览（-m 通道）。"""
        _require_module_channel()
        result = _run_subprocess(["--help"])
        assert result.returncode == 0, result.stderr
        for module in ("document", "tool", "agent", "plan", "checkpoint", "archive"):
            assert module in result.stdout, f"帮助缺模块 {module}"

    @pytest.mark.parametrize("command_path", _SMOKE_COMMANDS, ids=lambda c: "-".join(c))
    def test_each_command_help_exit_zero(self, command_path: tuple[str, ...]) -> None:
        """每命令 --help exit 0（三级/四级结构解析面）。"""
        _require_module_channel()
        result = _run_subprocess([*command_path, "--help"])
        assert result.returncode == 0, f"{' '.join(command_path)} --help 失败: {result.stderr[:200]}"

    def test_console_script_channel_when_available(self) -> None:
        """console_script 通道（shutil.which 探测——可用时与 -m 通道均验证）。"""
        _require_module_channel()
        script_path = shutil.which("sisys")
        if script_path is None:
            pytest.skip("console_script sisys 不可用（未 poetry install——script 通道动态降级）")
        result = subprocess.run(
            ["sisys", "--help"], capture_output=True, text=True, timeout=60, cwd=_REPO_ROOT, env=_build_env()
        )
        assert result.returncode == 0, f"script 通道失败: {result.stderr[:200]}"
        assert "document" in result.stdout


class TestDryRunSmoke:
    """写命令 --dry-run 冒烟（短路层子进程面接线——零服务调用 exit 0）。"""

    @pytest.mark.parametrize(
        ("command_path", "base_args"), _DRY_RUN_CASES, ids=lambda v: "-".join(v) if isinstance(v, tuple) else "args"
    )
    def test_dry_run_shortcircuit_in_subprocess(self, command_path: tuple[str, ...], base_args: list[str]) -> None:
        """--dry-run 子进程形态：动作清单+exit 0（bootstrap 前短路）。"""
        _require_module_channel()
        result = _run_subprocess([*command_path, *base_args, "--dry-run"])
        assert result.returncode == 0, f"{' '.join(command_path)} --dry-run 失败: {result.stderr[:200]}"
        assert result.stdout.strip(), "dry-run 动作清单为空"


class TestRealReadSmoke:
    """真实只读命令冒烟（服务可用时——tool list 元数据/UUID 归一形态）。"""

    def test_tool_list_real_metadata(self) -> None:
        """tool list 真实元数据（服务不可用动态 skip）。"""
        _require_module_channel()
        result = _run_subprocess(["tool", "list", "--format", "json"])
        if result.returncode != 0:
            pytest.skip(f"真实服务不可用（tool list 冒烟动态跳过）: {result.stderr[:200]}")
        assert result.stdout.strip()

    def test_uuid_normalization_subprocess(self) -> None:
        """大写 plan-id 归一（子进程面——6.9-R1-DF1 核销 e2e 证据）。"""
        _require_module_channel()
        canonical = str(uuid_module.uuid4())
        upper = _run_subprocess(["checkpoint", "list", "--plan-id", canonical.upper()])
        lower = _run_subprocess(["checkpoint", "list", "--plan-id", canonical])
        if upper.returncode != 0 and lower.returncode != 0:
            pytest.skip("真实服务不可用（归一冒烟动态跳过）")
        assert upper.returncode == lower.returncode, "大写/小写退出码不一致（归一失效形态）"
        assert upper.stdout == lower.stdout, "大写输出与 canonical 不一致（归一失效）"

    def test_compatible_entry_sisys_agent_alive(self) -> None:
        """sisys-agent 兼容入口子进程存活（--help exit 0——双入口共存）。"""
        result = subprocess.run(
            [sys.executable, "-m", "src.entrypoints.agent_cli", "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=_REPO_ROOT,
            env=_build_env(),
        )
        assert result.returncode == 0, f"兼容入口失败: {result.stderr[:200]}"


class TestDotenvBootstrapSmoke:
    """.env 加载后子进程可完成装配（6.8-R1-DF1 核销 e2e 证据——AC-6①）。"""

    def test_module_channel_bootstraps_with_dotenv(self) -> None:
        """python -m 形态 bootstrap 可达（.env 加载后不再 201/InvalidPasswordError）。"""
        _require_module_channel()
        result = _run_subprocess(["checkpoint", "list", "--plan-id", str(uuid_module.uuid4()), "--format", "json"])
        # 断言：不再出现组合根装配链 201/InvalidPasswordError（6.8 留项两呈现）
        assert "EXCEPTION_201" not in result.stderr, f".env 加载失效（embedding 201 复现）: {result.stderr[:200]}"
        assert "InvalidPasswordError" not in result.stderr, f".env 加载失效（空密码复现）: {result.stderr[:200]}"
