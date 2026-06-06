"""AuthConfig 配置模型单元测试

验证 JWT 认证配置的初始化、环境变量加载和完整性校验。
"""

from __future__ import annotations

import os
from unittest.mock import patch

from src.infrastructure.config.auth import AuthConfig


class TestAuthConfigInit:
    """AuthConfig 初始化测试"""

    def test_default_values(self) -> None:
        """默认值验证"""
        config = AuthConfig()
        assert config.jwt_secret_key == ""
        assert config.jwt_algorithm == "HS256"
        assert config.jwt_expiration_hours == 24
        assert config.jwt_refresh_expiration_days == 7
        assert config.password_min_length == 8
        assert config.password_require_uppercase is True
        assert config.password_require_lowercase is True
        assert config.password_require_digit is True
        assert config.password_require_special is True
        assert config.max_login_attempts == 5
        assert config.lockout_duration_minutes == 30
        assert config.session_timeout_minutes == 30

    def test_custom_values(self) -> None:
        """自定义值验证"""
        config = AuthConfig(
            jwt_secret_key="a" * 32,
            jwt_algorithm="RS256",
            jwt_expiration_hours=1,
            jwt_refresh_expiration_days=30,
            password_min_length=12,
            password_require_uppercase=False,
            password_require_lowercase=False,
            password_require_digit=False,
            password_require_special=False,
            max_login_attempts=3,
            lockout_duration_minutes=15,
            session_timeout_minutes=60,
        )
        assert config.jwt_algorithm == "RS256"
        assert config.jwt_expiration_hours == 1
        assert config.password_min_length == 12
        assert config.password_require_uppercase is False
        assert config.max_login_attempts == 3
        assert config.session_timeout_minutes == 60


class TestAuthConfigFromEnv:
    """from_env 类方法测试"""

    def test_from_env_defaults(self) -> None:
        """无环境变量时使用默认值"""
        with patch.dict(os.environ, {}, clear=True):
            config = AuthConfig.from_env()
            assert config.jwt_secret_key == ""
            assert config.jwt_algorithm == "HS256"
            assert config.jwt_expiration_hours == 24

    def test_from_env_custom_values(self) -> None:
        """完整自定义环境变量"""
        with patch.dict(
            os.environ,
            {
                "JWT_SECRET_KEY": "my-secret-key-at-least-32-chars!!",  # pragma: allowlist secret
                "JWT_ALGORITHM": "RS256",
                "JWT_EXPIRATION_HOURS": "12",
                "JWT_REFRESH_EXPIRATION_DAYS": "14",
                "PASSWORD_MIN_LENGTH": "10",
                "PASSWORD_REQUIRE_UPPERCASE": "false",  # pragma: allowlist secret
                "PASSWORD_REQUIRE_LOWERCASE": "false",  # pragma: allowlist secret
                "PASSWORD_REQUIRE_DIGIT": "false",  # pragma: allowlist secret
                "PASSWORD_REQUIRE_SPECIAL": "false",  # pragma: allowlist secret
                "MAX_LOGIN_ATTEMPTS": "3",
                "LOCKOUT_DURATION_MINUTES": "15",
                "SESSION_TIMEOUT_MINUTES": "60",
            },
            clear=True,
        ):
            config = AuthConfig.from_env()
            assert config.jwt_secret_key == "my-secret-key-at-least-32-chars!!"  # pragma: allowlist secret
            assert config.jwt_algorithm == "RS256"
            assert config.jwt_expiration_hours == 12
            assert config.jwt_refresh_expiration_days == 14
            assert config.password_min_length == 10
            assert config.password_require_uppercase is False
            assert config.password_require_lowercase is False
            assert config.password_require_digit is False
            assert config.password_require_special is False
            assert config.max_login_attempts == 3
            assert config.lockout_duration_minutes == 15
            assert config.session_timeout_minutes == 60

    def test_from_env_boolean_variants(self) -> None:
        """布尔环境变量支持 true/1/yes 变体"""
        for true_val in ("true", "1", "yes"):
            with patch.dict(os.environ, {"PASSWORD_REQUIRE_UPPERCASE": true_val}, clear=True):
                config = AuthConfig.from_env()
                assert config.password_require_uppercase is True, f"值 '{true_val}' 应解析为 True"

        for false_val in ("false", "0", "no", "no"):
            with patch.dict(os.environ, {"PASSWORD_REQUIRE_UPPERCASE": false_val}, clear=True):
                config = AuthConfig.from_env()
                assert config.password_require_uppercase is False, f"值 '{false_val}' 应解析为 False"


class TestAuthConfigValidate:
    """validate 完整性校验测试"""

    def test_validate_empty_secret_key(self) -> None:
        """空密钥应报告错误"""
        config = AuthConfig(jwt_secret_key="")
        errors = config.validate()
        assert "JWT_SECRET_KEY is required" in errors

    def test_validate_short_secret_key_for_hs256(self) -> None:
        """HS256 算法下密钥长度不足 32 应报告错误"""
        config = AuthConfig(jwt_secret_key="short", jwt_algorithm="HS256")
        errors = config.validate()
        assert any("JWT_SECRET_KEY must be at least 32 characters" in e for e in errors)

    def test_validate_short_secret_key_for_hs512(self) -> None:
        """HS512 算法下密钥长度不足 32 也应报告错误"""
        config = AuthConfig(jwt_secret_key="short", jwt_algorithm="HS512")
        errors = config.validate()
        assert any("JWT_SECRET_KEY must be at least 32 characters" in e for e in errors)

    def test_validate_short_key_ok_for_rs256(self) -> None:
        """RS256 算法不检查密钥长度（非 HS 前缀）"""
        config = AuthConfig(jwt_secret_key="short", jwt_algorithm="RS256")
        errors = config.validate()
        # RS256 使用非对称密钥，不需要长度检查
        assert not any("JWT_SECRET_KEY must be at least 32 characters" in e for e in errors)

    def test_validate_negative_expiration(self) -> None:
        """过期时间 ≤0 应报告错误"""
        config = AuthConfig(jwt_expiration_hours=0)
        errors = config.validate()
        assert "JWT_EXPIRATION_HOURS must be positive" in errors

        config2 = AuthConfig(jwt_expiration_hours=-1)
        errors2 = config2.validate()
        assert "JWT_EXPIRATION_HOURS must be positive" in errors2

    def test_validate_password_min_length_too_short(self) -> None:
        """密码最小长度 <8 应报告错误"""
        config = AuthConfig(password_min_length=6)
        errors = config.validate()
        assert "PASSWORD_MIN_LENGTH must be at least 8" in errors

    def test_validate_max_login_attempts_zero(self) -> None:
        """max_login_attempts <1 应报告错误"""
        config = AuthConfig(max_login_attempts=0)
        errors = config.validate()
        assert "MAX_LOGIN_ATTEMPTS must be at least 1" in errors

        config2 = AuthConfig(max_login_attempts=-1)
        errors2 = config2.validate()
        assert "MAX_LOGIN_ATTEMPTS must be at least 1" in errors2

    def test_validate_lockout_duration_zero(self) -> None:
        """lockout_duration_minutes <1 应报告错误"""
        config = AuthConfig(lockout_duration_minutes=0)
        errors = config.validate()
        assert "LOCKOUT_DURATION_MINUTES must be at least 1" in errors

    def test_validate_all_valid(self) -> None:
        """有效配置返回空错误列表"""
        config = AuthConfig(
            jwt_secret_key="a" * 32,
            jwt_expiration_hours=24,
            password_min_length=8,
            max_login_attempts=5,
            lockout_duration_minutes=30,
        )
        errors = config.validate()
        assert errors == []

    def test_validate_multiple_errors(self) -> None:
        """多个验证错误应同时返回"""
        config = AuthConfig(
            jwt_secret_key="",
            jwt_expiration_hours=0,
            password_min_length=4,
            max_login_attempts=0,
            lockout_duration_minutes=0,
        )
        errors = config.validate()
        assert len(errors) >= 4
        assert "JWT_SECRET_KEY is required" in errors
        assert "JWT_EXPIRATION_HOURS must be positive" in errors
        assert "MAX_LOGIN_ATTEMPTS must be at least 1" in errors
        assert "LOCKOUT_DURATION_MINUTES must be at least 1" in errors
