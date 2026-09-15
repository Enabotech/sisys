"""基础设施层 seccomp profile 加载器模块（Story 4.4 Task 5)

加载仓库内置的强化 seccomp profile JSON 文件。

设计依据:
- 单一职责:从文件系统加载 seccomp profile JSON
- 失败时抛 SandboxConfigurationError(EXCEPTION_319)
- 路径:deploy/docker/seccomp/sisys-hardened.json(ContainerSpec.seccomp_profile 默认值)

注意:本模块仅定义加载器,**真实 seccomp profile JSON 文件**
需在 deploy/docker/seccomp/sisys-hardened.json 单独创建(部署资源)。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.domain.exceptions.sandbox_exceptions import SandboxConfigurationError

logger = logging.getLogger(__name__)

__all__ = ["SeccompProfileLoader"]


class SeccompProfileLoader:
    """seccomp profile JSON 加载器（Story 4.4 Task 5)

    Attributes:
        _project_root: 项目根目录(从模块路径推断)
        _default_profile_path: 默认 profile 路径(相对项目根)
    """

    def __init__(self, project_root: Path | None = None) -> None:
        """初始化加载器。

        Args:
            project_root: 项目根目录(默认 None → 自动推断)
        """
        self._project_root = project_root or Path(__file__).resolve().parents[3]
        self._default_profile_path = "deploy/docker/seccomp/sisys-hardened.json"

    def load_profile(self, profile_path: str | None = None) -> dict[str, Any]:
        """加载 seccomp profile JSON 文件。

        Args:
            profile_path: profile 路径(默认 None → 使用默认路径)

        Returns:
            seccomp profile 字典(包含 defaultAction / architectures / syscalls 等字段)

        Raises:
            SandboxConfigurationError: 文件不存在 / JSON 解析失败 / 格式错误
        """
        rel_path = profile_path or self._default_profile_path
        abs_path = self._project_root / rel_path

        if not abs_path.exists():
            raise SandboxConfigurationError(
                message=f"seccomp profile not found: {abs_path}",
                field_name="seccomp_profile",
                field_value=str(abs_path),
                reason="file not found",
            )

        try:
            with abs_path.open("r", encoding="utf-8") as f:
                profile = json.load(f)
        except json.JSONDecodeError as exc:
            raise SandboxConfigurationError(
                message=f"Invalid seccomp profile JSON: {exc}",
                field_name="seccomp_profile",
                field_value=str(abs_path),
                reason=f"JSONDecodeError: {exc}",
            ) from exc
        except OSError as exc:
            raise SandboxConfigurationError(
                message=f"Failed to read seccomp profile: {exc}",
                field_name="seccomp_profile",
                field_value=str(abs_path),
                reason=f"OSError: {exc}",
            ) from exc

        # 校验 profile 必需字段
        if not isinstance(profile, dict):
            raise SandboxConfigurationError(
                message=f"seccomp profile must be a JSON object, got {type(profile).__name__}",
                field_name="seccomp_profile",
                field_value=str(abs_path),
                reason="invalid root type",
            )

        if "syscalls" not in profile:
            raise SandboxConfigurationError(
                message="seccomp profile missing required field: 'syscalls'",
                field_name="seccomp_profile",
                field_value=str(abs_path),
                reason="missing syscalls field",
            )

        logger.info("Loaded seccomp profile: %s", abs_path)
        return profile

    def resolve_profile_path(self, profile_path: str | None = None) -> str:
        """解析 profile 路径为绝对路径(用于 aiodocker security_opt)。

        Args:
            profile_path: profile 路径(默认 None → 使用默认路径)

        Returns:
            绝对路径字符串

        Raises:
            SandboxConfigurationError: 文件不存在
        """
        rel_path = profile_path or self._default_profile_path
        abs_path = self._project_root / rel_path
        if not abs_path.exists():
            raise SandboxConfigurationError(
                message=f"seccomp profile not found: {abs_path}",
                field_name="seccomp_profile",
                field_value=str(abs_path),
                reason="file not found",
            )
        return str(abs_path)


__all__ = ["SeccompProfileLoader"]
