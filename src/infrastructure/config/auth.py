"""AuthConfig — Authentication and authorization configuration.

Reference: Story 1.4-1.8 Config pattern (XxxConfig + from_env()).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class AuthConfig:
    """Authentication and authorization configuration.

    Attributes:
        jwt_secret_key: Secret key for JWT signing (HS256).
        jwt_algorithm: Algorithm for JWT signing (HS256 MVP, RS256 V1+).
        jwt_expiration_hours: JWT token expiration time in hours.
        jwt_refresh_expiration_days: Refresh token expiration time in days.
        password_min_length: Minimum password length (Deng Bao 2.0 requires 8+).
        password_require_uppercase: Require uppercase letters in password.
        password_require_lowercase: Require lowercase letters in password.
        password_require_digit: Require digits in password.
        password_require_special: Require special characters in password.
        max_login_attempts: Maximum failed login attempts before lockout.
        lockout_duration_minutes: Account lockout duration in minutes.
        session_timeout_minutes: Session timeout after inactivity (30 min for Deng Bao 2.0).
        refresh_token_enabled: Enable refresh token functionality.
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
    refresh_token_enabled: bool = True

    # Predefined role permissions (MVP)
    predefined_roles: dict[str, list[str]] = field(
        default_factory=lambda: {
            "admin": ["*:*"],
            "analyst": [
                "document:read",
                "document:write",
                "tool:execute",
                "agent:execute",
            ],
            "viewer": ["document:read"],
        }
    )

    @classmethod
    def from_env(cls) -> AuthConfig:
        """Load configuration from environment variables.

        Environment variables:
            AUTH_JWT_SECRET_KEY: Secret key for JWT signing.
            AUTH_JWT_ALGORITHM: Algorithm for JWT signing (default: HS256).
            AUTH_JWT_EXPIRATION_HOURS: JWT expiration in hours (default: 24).
            AUTH_JWT_REFRESH_EXPIRATION_DAYS: Refresh token expiration in days (default: 7).
            AUTH_PASSWORD_MIN_LENGTH: Minimum password length (default: 8).
            AUTH_PASSWORD_REQUIRE_UPPERCASE: Require uppercase (default: true).
            AUTH_PASSWORD_REQUIRE_LOWERCASE: Require lowercase (default: true).
            AUTH_PASSWORD_REQUIRE_DIGIT: Require digit (default: true).
            AUTH_PASSWORD_REQUIRE_SPECIAL: Require special char (default: true).
            AUTH_MAX_LOGIN_ATTEMPTS: Max login attempts before lockout (default: 5).
            AUTH_LOCKOUT_DURATION_MINUTES: Lockout duration minutes (default: 30).
            AUTH_SESSION_TIMEOUT_MINUTES: Session timeout minutes (default: 30).
            AUTH_REFRESH_TOKEN_ENABLED: Enable refresh token (default: true).
        """
        return cls(
            jwt_secret_key=os.getenv("AUTH_JWT_SECRET_KEY", "dev-secret-key-change-in-production"),
            jwt_algorithm=os.getenv("AUTH_JWT_ALGORITHM", "HS256"),
            jwt_expiration_hours=int(os.getenv("AUTH_JWT_EXPIRATION_HOURS", "24")),
            jwt_refresh_expiration_days=int(os.getenv("AUTH_JWT_REFRESH_EXPIRATION_DAYS", "7")),
            password_min_length=int(os.getenv("AUTH_PASSWORD_MIN_LENGTH", "8")),
            password_require_uppercase=os.getenv("AUTH_PASSWORD_REQUIRE_UPPERCASE", "true").lower() in ("true", "1", "yes"),
            password_require_lowercase=os.getenv("AUTH_PASSWORD_REQUIRE_LOWERCASE", "true").lower() in ("true", "1", "yes"),
            password_require_digit=os.getenv("AUTH_PASSWORD_REQUIRE_DIGIT", "true").lower() in ("true", "1", "yes"),
            password_require_special=os.getenv("AUTH_PASSWORD_REQUIRE_SPECIAL", "true").lower() in ("true", "1", "yes"),
            max_login_attempts=int(os.getenv("AUTH_MAX_LOGIN_ATTEMPTS", "5")),
            lockout_duration_minutes=int(os.getenv("AUTH_LOCKOUT_DURATION_MINUTES", "30")),
            session_timeout_minutes=int(os.getenv("AUTH_SESSION_TIMEOUT_MINUTES", "30")),
            refresh_token_enabled=os.getenv("AUTH_REFRESH_TOKEN_ENABLED", "true").lower() in ("true", "1", "yes"),
        )


# Global config instance (lazy loading)
_auth_config: AuthConfig | None = None


def get_auth_config() -> AuthConfig:
    """Get the global AuthConfig instance (lazy loading).

    Returns:
        AuthConfig: The global authentication configuration.
    """
    global _auth_config
    if _auth_config is None:
        _auth_config = AuthConfig.from_env()
    return _auth_config
