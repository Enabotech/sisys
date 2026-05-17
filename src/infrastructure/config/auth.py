"""基础设施层认证配置模块

提供 JWT 认证和授权配置，用于 RBAC 权限管理系统

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AuthConfig:
    """JWT 认证和授权配置

    用于 RBAC 权限管理系统，支持 JWT 令牌生成和验证

    Attributes:
        jwt_secret_key: JWT 签名密钥（生产环境必须使用强随机密钥）
        jwt_algorithm: JWT 签名算法（HS256 用于 MVP，RS256 用于 V1+）
        jwt_expiration_hours: JWT 访问令牌过期时间（小时）
        jwt_refresh_expiration_days: JWT 刷新令牌过期时间（天）
        password_min_length: 密码最小长度
        password_require_uppercase: 是否要求大写字母
        password_require_lowercase: 是否要求小写字母
        password_require_digit: 是否要求数字
        password_require_special: 是否要求特殊字符
        max_login_attempts: 最大登录失败次数
        lockout_duration_minutes: 账户锁定时长（分钟）
        session_timeout_minutes: 会话超时时间（分钟，无操作）
    """

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    jwt_refresh_expiration_days: int = 7
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_digit: bool = True
    password_require_special: bool = True
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 30
    session_timeout_minutes: int = 30

    @classmethod
    def from_env(cls) -> AuthConfig:
        """从环境变量加载配置

        Args:
            无（从 os.environ 读取）

        Returns:
            AuthConfig 实例
        """
        return cls(
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", ""),
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            jwt_expiration_hours=int(os.getenv("JWT_EXPIRATION_HOURS", "24")),
            jwt_refresh_expiration_days=int(os.getenv("JWT_REFRESH_EXPIRATION_DAYS", "7")),
            password_min_length=int(os.getenv("PASSWORD_MIN_LENGTH", "8")),
            password_require_uppercase=os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() in ("true", "1", "yes"),
            password_require_lowercase=os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() in ("true", "1", "yes"),
            password_require_digit=os.getenv("PASSWORD_REQUIRE_DIGIT", "true").lower() in ("true", "1", "yes"),
            password_require_special=os.getenv("PASSWORD_REQUIRE_SPECIAL", "true").lower() in ("true", "1", "yes"),
            max_login_attempts=int(os.getenv("MAX_LOGIN_ATTEMPTS", "5")),
            lockout_duration_minutes=int(os.getenv("LOCKOUT_DURATION_MINUTES", "30")),
            session_timeout_minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "30")),
        )

    def validate(self) -> list[str]:
        """验证配置完整性.

        Returns:
            验证错误列表，空列表表示验证通过
        """
        errors = []
        if not self.jwt_secret_key:
            errors.append("JWT_SECRET_KEY is required")
        if len(self.jwt_secret_key) < 32 and self.jwt_algorithm.startswith("HS"):
            errors.append("JWT_SECRET_KEY must be at least 32 characters for HS256")
        if self.jwt_expiration_hours <= 0:
            errors.append("JWT_EXPIRATION_HOURS must be positive")
        if self.password_min_length < 8:
            errors.append("PASSWORD_MIN_LENGTH must be at least 8")
        if self.max_login_attempts < 1:
            errors.append("MAX_LOGIN_ATTEMPTS must be at least 1")
        if self.lockout_duration_minutes < 1:
            errors.append("LOCKOUT_DURATION_MINUTES must be at least 1")
        return errors
