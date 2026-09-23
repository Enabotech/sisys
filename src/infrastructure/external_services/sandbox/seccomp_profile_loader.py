"""基础设施层 seccomp profile 加载器

Story 4.4 — Docker 沙箱执行(Round 3 审查修订: 兑现 AC-5 强化 seccomp 承诺)。

加载仓库内置 hardened profile 并转换为 Docker Engine API 的 SecurityOpt 内联格式
(`seccomp=<紧凑JSON>`,daemon 侧无需文件路径,已由 Engine API create 201/start 204 实证)。

路径假设: src-layout 源码运行(部署形态为仓库 checkout),
以 `Path(__file__)` 锚定仓库根目录,不依赖进程 cwd。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from src.domain.exceptions import SandboxConfigurationError

# src/infrastructure/external_services/sandbox/seccomp_profile_loader.py → 上溯 4 级 = 仓库根
_REPO_ROOT = Path(__file__).resolve().parents[4]


@lru_cache(maxsize=8)
def load_seccomp_profile(profile_path: str) -> str:
    """加载 seccomp profile 并返回 SecurityOpt 内联字符串

    Args:
        profile_path: profile 文件路径(相对路径基于仓库根目录解析)

    Returns:
        "seccomp=<紧凑JSON>" 格式的 SecurityOpt 条目

    Raises:
        SandboxConfigurationError: EXCEPTION_319 — 文件不存在/JSON 非法/缺必需键
    """
    path = Path(profile_path)
    if not path.is_absolute():
        path = _REPO_ROOT / profile_path
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SandboxConfigurationError(
            f"seccomp profile 加载失败: {profile_path}",
            field_name="seccomp_profile",
            field_value=profile_path,
            reason_detail=f"file read error: {type(exc).__name__}",
        ) from exc
    except json.JSONDecodeError as exc:
        raise SandboxConfigurationError(
            f"seccomp profile 加载失败: {profile_path}",
            field_name="seccomp_profile",
            field_value=profile_path,
            reason_detail=f"invalid JSON: {exc.msg}",
        ) from exc
    if not isinstance(profile, dict) or "defaultAction" not in profile or "syscalls" not in profile:
        raise SandboxConfigurationError(
            f"seccomp profile 加载失败: {profile_path}",
            field_name="seccomp_profile",
            field_value=profile_path,
            reason_detail="missing required keys: defaultAction/syscalls",
        )
    return "seccomp=" + json.dumps(profile, separators=(",", ":"))


__all__ = ["load_seccomp_profile"]
