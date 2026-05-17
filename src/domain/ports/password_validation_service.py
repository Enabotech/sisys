"""领域层密码验证服务端口模块

领域层接口，定义密码复杂度验证的契约
遵循六边形架构：领域层零依赖，仅使用标准库

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.exceptions.service_exceptions import PasswordValidationError

__all__ = ["PasswordValidationError"]


@runtime_checkable
class PasswordValidationServicePort(Protocol):
    """密码验证服务端口（领域层定义，仅使用标准库）

    负责密码复杂度验证，满足等保 2.0 三级要求：
    - 至少 8 字符
    - 包含大小写字母
    - 包含数字
    - 包含特殊字符
    """

    def validate(self, password: str) -> None:
        """验证密码复杂度

        Args:
            password: 明文密码

        Raises:
            PasswordValidationError: 密码不符合复杂度要求
        """
        ...

    def get_requirements(self) -> dict[str, str]:
        """获取密码复杂度要求描述

        Returns:
            密码要求字典
        """
        ...
