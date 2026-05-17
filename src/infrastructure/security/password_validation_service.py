"""基础设施层密码验证服务模块

基于等保 2.0 三级要求实现密码复杂度验证功能

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from src.domain.ports.password_validation_service import (
    PasswordValidationError,
    PasswordValidationServicePort,
)


class PasswordValidationService(PasswordValidationServicePort):
    """密码验证服务实现，满足等保 2.0 三级密码复杂度要求

    要求至少 8 字符、包含大小写字母、数字和特殊字符

    Attributes:
        MIN_LENGTH: 密码最小长度常量
        REQUIREMENTS: 密码复杂度要求描述字典
    """

    MIN_LENGTH = 8
    REQUIREMENTS = {
        "min_length": f"至少 {MIN_LENGTH} 个字符",
        "uppercase": "包含大写字母 (A-Z)",
        "lowercase": "包含小写字母 (a-z)",
        "digit": "包含数字 (0-9)",
        "special": "包含特殊字符 (!@#$%^&*()_+-=[]{}|;:',.<>?/)",
    }

    def validate(self, password: str) -> None:
        """验证密码复杂度

        Args:
            password: 明文密码

        Raises:
            PasswordValidationError: 密码不符合复杂度要求
        """
        errors = []

        if len(password) < self.MIN_LENGTH:
            errors.append(f"密码长度至少 {self.MIN_LENGTH} 个字符")

        if not any(c.isupper() for c in password):
            errors.append("密码必须包含至少一个大写字母")

        if not any(c.islower() for c in password):
            errors.append("密码必须包含至少一个小写字母")

        if not any(c.isdigit() for c in password):
            errors.append("密码必须包含至少一个数字")

        if not any(c in "!@#$%^&*()_+-=[]{}|;:',.<>?/" for c in password):
            errors.append("密码必须包含至少一个特殊字符")

        if errors:
            raise PasswordValidationError(
                message=f"密码不符合复杂度要求: {'; '.join(errors)}",
                code="PASSWORD_WEAK",
            )

    def get_requirements(self) -> dict[str, str]:
        """获取密码复杂度要求描述

        Returns:
            密码要求字典
        """
        return self.REQUIREMENTS.copy()
