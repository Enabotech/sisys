"""AuthService — Authentication service implementation.

Implements the AuthService protocol defined in domain layer.
Uses bcrypt for password hashing and JWT for token generation.

Reference: architecture.md - ADR-010 JWT local auth decision.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from passlib.context import CryptContext

from src.infrastructure.config.auth import AuthConfig, get_auth_config
from src.infrastructure.security.jwt_service import (
    InvalidTokenError,
    JWTService,
    TokenExpiredError,
    get_jwt_service,
)

if TYPE_CHECKING:
    from src.infrastructure.storage.postgresql.role_repository import RoleRepository
    from src.infrastructure.storage.postgresql.user_repository import UserRepository

# Password hashing context using bcrypt
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthenticationError(Exception):
    """Base exception for authentication errors."""

    pass


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password."""

    pass


class AccountLockedError(AuthenticationError):
    """Account is locked due to failed login attempts."""

    pass


class UserInactiveError(AuthenticationError):
    """User account is inactive."""

    pass


class AuthServiceImpl:
    """Authentication service implementation.

    Implements the AuthService protocol for user authentication
    using username/password and JWT tokens.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        role_repository: RoleRepository,
        jwt_service: JWTService | None = None,
        config: AuthConfig | None = None,
    ) -> None:
        """Initialize AuthService.

        Args:
            user_repository: User repository for database operations.
            role_repository: Role repository for role queries.
            jwt_service: JWT service instance. If None, uses global instance.
            config: Auth configuration. If None, loads from environment.
        """
        self._user_repo = user_repository
        self._role_repo = role_repository
        self._jwt_service = jwt_service or get_jwt_service()
        self._config = config or get_auth_config()

    async def authenticate(self, username: str, password: str) -> dict[str, Any]:
        """Authenticate user with username and password.

        Args:
            username: User's username.
            password: User's plain text password.

        Returns:
            dict: Authentication result containing:
                - access_token: JWT access token
                - refresh_token: JWT refresh token
                - token_type: Token type (always "bearer")
                - expires_in: Token expiration time in seconds
                - user: User information dict

        Raises:
            InvalidCredentialsError: If username/password is invalid.
            AccountLockedError: If account is locked due to failed attempts.
            UserInactiveError: If user account is deactivated.
        """
        from src.infrastructure.storage.postgresql.models.user import UserModel

        # Get user by username
        user: UserModel | None = await self._user_repo.get_by_username(username)

        if user is None:
            raise InvalidCredentialsError("Invalid credentials")

        # Check if user is active
        if not user.is_active:
            raise UserInactiveError("User account is inactive")

        # Check if account is locked (using the user's failed_login_attempts and locked_until)
        # For now, we use simple logic; can be enhanced with Redis for distributed locking
        # Note: UserModel would need these fields - if not present, we skip this check
        if hasattr(user, "locked_until") and user.locked_until:
            if user.locked_until > datetime.now(UTC).replace(tzinfo=None):
                raise AccountLockedError(
                    f"Account locked due to multiple failed attempts. " f"Try again after {user.locked_until.isoformat()}"
                )

        # Verify password
        if not user.hashed_password:
            raise InvalidCredentialsError("Invalid credentials")

        if not self.verify_password(password, user.hashed_password):
            # Increment failed login attempts
            if hasattr(user, "failed_login_attempts"):
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

                # Check if should lock account
                if user.failed_login_attempts >= self._config.max_login_attempts:
                    if hasattr(user, "lock_account"):
                        user.lock_account(self._config.lockout_duration_minutes)
                    elif hasattr(user, "locked_until"):
                        user.locked_until = datetime.now(UTC).replace(tzinfo=None) + timedelta(
                            minutes=self._config.lockout_duration_minutes
                        )

                await self._user_repo.save(user)

            raise InvalidCredentialsError("Invalid credentials")

        # Reset failed login attempts on successful login
        if hasattr(user, "failed_login_attempts") and user.failed_login_attempts > 0:
            user.failed_login_attempts = 0
            if hasattr(user, "locked_until"):
                user.locked_until = None
            await self._user_repo.save(user)

        # Get user roles
        roles = await self.get_user_roles(user.id)

        # Generate tokens
        access_token = self._jwt_service.create_access_token(
            user_id=user.id,
            username=user.username,
            roles=roles,
        )

        refresh_token = None
        if self._config.refresh_token_enabled:
            refresh_token = self._jwt_service.create_refresh_token(user.id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self._jwt_service.get_expires_in(),
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "roles": roles,
                "is_active": user.is_active,
            },
        }

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify and decode a JWT token.

        Args:
            token: JWT token string.

        Returns:
            dict: Decoded token payload.

        Raises:
            InvalidTokenError: If token is invalid or expired.
        """
        try:
            payload = self._jwt_service.verify_token(token)
            return dict(payload)
        except TokenExpiredError as e:
            raise InvalidTokenError(f"Token expired: {e}") from e
        except Exception as e:
            raise InvalidTokenError(f"Invalid token: {e}") from e

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh an expired or expiring access token.

        Args:
            refresh_token: Valid refresh token string.

        Returns:
            dict: New token pair containing:
                - access_token: New JWT access token
                - refresh_token: New refresh token
                - expires_in: Token expiration time in seconds

        Raises:
            InvalidTokenError: If refresh token is invalid or expired.
        """
        if not self._jwt_service.is_refresh_token(refresh_token):
            raise InvalidTokenError("Not a valid refresh token")

        try:
            payload = self._jwt_service.verify_token(refresh_token)
        except TokenExpiredError as e:
            raise InvalidTokenError(f"Refresh token expired: {e}") from e
        except Exception as e:
            raise InvalidTokenError(f"Invalid refresh token: {e}") from e

        user_id = UUID(payload["sub"])

        # Get user to verify still active
        user = await self._user_repo.get_by_id(str(user_id))
        if user is None:
            raise InvalidTokenError("User not found")
        if not user.is_active:
            raise UserInactiveError("User account is inactive")

        # Get user roles
        roles = await self.get_user_roles(user_id)

        # Generate new tokens
        access_token = self._jwt_service.create_access_token(
            user_id=user_id,
            username=user.username,
            roles=roles,
        )

        new_refresh_token = None
        if self._config.refresh_token_enabled:
            new_refresh_token = self._jwt_service.create_refresh_token(user_id)

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": self._jwt_service.get_expires_in(),
        }

    def hash_password(self, password: str) -> str:
        """Hash a plain text password.

        Args:
            password: Plain text password.

        Returns:
            str: Bcrypt hashed password.
        """
        return cast(str, _pwd_context.hash(password))

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain text password against a hash.

        Args:
            plain_password: Plain text password to verify.
            hashed_password: Bcrypt hashed password to check against.

        Returns:
            bool: True if password matches, False otherwise.
        """
        return cast(bool, _pwd_context.verify(plain_password, hashed_password))

    async def get_user_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        """Get user information by user ID.

        Args:
            user_id: User's UUID.

        Returns:
            dict | None: User information dict or None if not found.
        """
        user = await self._user_repo.get_by_id(str(user_id))
        if user is None:
            return None

        roles = await self.get_user_roles(user_id)

        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "roles": roles,
            "is_active": user.is_active,
        }

    async def get_user_roles(self, user_id: UUID) -> list[str]:
        """Get all role names for a user.

        Args:
            user_id: User's UUID.

        Returns:
            list[str]: List of role names.
        """
        # Get all roles for user from user_roles association
        from sqlalchemy import select

        from src.infrastructure.storage.postgresql.models.association import user_roles_table
        from src.infrastructure.storage.postgresql.models.role import RoleModel

        result = await self._user_repo._session.execute(
            select(RoleModel.name)
            .join(user_roles_table, RoleModel.id == user_roles_table.c.role_id)
            .where(user_roles_table.c.user_id == user_id)
        )
        return list(result.scalars().all())
