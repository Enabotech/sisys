"""JWT Service — JWT token generation and validation.

Reference: architecture.md - ADR-010 JWT local auth decision.
Uses python-jose for JWT operations.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from jose import ExpiredSignatureError, JWTError, jwt

from src.infrastructure.config.auth import AuthConfig, get_auth_config


class JWTServiceError(Exception):
    """Base exception for JWT operations."""

    pass


class TokenExpiredError(JWTServiceError):
    """Token has expired."""

    pass


class InvalidTokenError(JWTServiceError):
    """Token is invalid."""

    pass


class JWTService:
    """JWT token service for generating and validating tokens.

    Attributes:
        secret_key: Secret key for signing tokens.
        algorithm: Algorithm for signing (HS256 MVP, RS256 V1+).
        access_token_expire_hours: Access token expiration in hours.
        refresh_token_expire_days: Refresh token expiration in days.
    """

    def __init__(self, config: AuthConfig | None = None) -> None:
        """Initialize JWT service.

        Args:
            config: AuthConfig instance. If None, loads from environment.
        """
        self._config = config or get_auth_config()
        self._secret_key = self._config.jwt_secret_key
        self._algorithm = self._config.jwt_algorithm
        self._access_token_expire_hours = self._config.jwt_expiration_hours
        self._refresh_token_expire_days = self._config.jwt_refresh_expiration_days

    def create_access_token(
        self,
        user_id: UUID,
        username: str,
        roles: list[str],
        additional_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create a new JWT access token.

        Args:
            user_id: User's unique identifier.
            username: User's username.
            roles: List of role names.
            additional_claims: Optional additional claims to include.

        Returns:
            str: Encoded JWT token.
        """
        now = datetime.now(UTC)
        expire = now + timedelta(hours=self._access_token_expire_hours)

        payload = {
            "sub": str(user_id),
            "username": username,
            "roles": roles,
            "iat": now,
            "exp": expire,
            "type": "access",
        }

        if additional_claims:
            payload.update(additional_claims)

        return cast(str, jwt.encode(payload, self._secret_key, algorithm=self._algorithm))

    def create_refresh_token(self, user_id: UUID) -> str:
        """Create a new JWT refresh token.

        Args:
            user_id: User's unique identifier.

        Returns:
            str: Encoded JWT refresh token.
        """
        now = datetime.now(UTC)
        expire = now + timedelta(days=self._refresh_token_expire_days)

        payload = {
            "sub": str(user_id),
            "iat": now,
            "exp": expire,
            "type": "refresh",
        }

        return cast(str, jwt.encode(payload, self._secret_key, algorithm=self._algorithm))

    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify and decode a JWT token.

        Args:
            token: JWT token string.

        Returns:
            dict: Decoded token payload.

        Raises:
            TokenExpiredError: If token has expired.
            InvalidTokenError: If token is invalid.
        """
        try:
            payload = cast(
                dict[str, Any],
                jwt.decode(
                    token,
                    self._secret_key,
                    algorithms=[self._algorithm],
                ),
            )
            return dict(payload)
        except ExpiredSignatureError as e:
            raise TokenExpiredError("Token has expired") from e
        except JWTError as e:
            raise InvalidTokenError(f"Invalid token: {e}") from e

    def decode_token(self, token: str) -> dict[str, Any]:
        """Decode a JWT token without verification (for debugging).

        Args:
            token: JWT token string.

        Returns:
            dict: Decoded token payload (unverified).
        """
        return cast(
            dict[str, Any],
            jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={"verify_signature": False},
            ),
        )

    def get_user_id_from_token(self, token: str) -> UUID:
        """Extract user ID from a token.

        Args:
            token: JWT token string.

        Returns:
            UUID: User's unique identifier.

        Raises:
            InvalidTokenError: If token is invalid or missing sub claim.
        """
        payload = self.verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise InvalidTokenError("Token missing 'sub' claim")
        return UUID(user_id)

    def get_token_type(self, token: str) -> str:
        """Get the type of token.

        Args:
            token: JWT token string.

        Returns:
            str: Token type ("access" or "refresh").
        """
        payload = self.verify_token(token)
        return cast(str, payload.get("type", "access"))

    def is_access_token(self, token: str) -> bool:
        """Check if token is an access token.

        Args:
            token: JWT token string.

        Returns:
            bool: True if token is an access token.
        """
        return self.get_token_type(token) == "access"

    def is_refresh_token(self, token: str) -> bool:
        """Check if token is a refresh token.

        Args:
            token: JWT token string.

        Returns:
            bool: True if token is a refresh token.
        """
        return self.get_token_type(token) == "refresh"

    def get_expires_in(self) -> int:
        """Get access token expiration time in seconds.

        Returns:
            int: Expiration time in seconds.
        """
        return self._access_token_expire_hours * 3600


# Global JWT service instance
_jwt_service: JWTService | None = None


def get_jwt_service() -> JWTService:
    """Get the global JWTService instance.

    Returns:
        JWTService: The global JWT service instance.
    """
    global _jwt_service
    if _jwt_service is None:
        _jwt_service = JWTService()
    return _jwt_service
