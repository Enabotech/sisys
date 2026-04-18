"""AuthService — Domain service interface for authentication.

This module defines the authentication service interface (Protocol)
following hexagonal architecture: domain layer defines interface,
infrastructure layer implements it.

Reference: architecture.md - ADR-010 API Gateway decision for JWT auth.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    pass


class AuthService(Protocol):
    """Protocol defining authentication service interface.

    The authentication service is responsible for:
    - User credential validation
    - JWT token generation and validation
    - Session management

    This is a domain layer interface (Protocol) that must be implemented
    by the infrastructure layer (src/infrastructure/security/auth_service.py).
    """

    def authenticate(self, username: str, password: str) -> dict:
        """Authenticate user with username and password.

        Args:
            username: User's username.
            password: User's plain text password.

        Returns:
            dict: Authentication result containing:
                - access_token: JWT access token
                - token_type: Token type (always "bearer")
                - expires_in: Token expiration time in seconds
                - user: User information dict

        Raises:
            InvalidCredentialsError: If username/password is invalid.
            AccountLockedError: If account is locked due to failed attempts.
            UserInactiveError: If user account is deactivated.
        """
        ...

    def verify_token(self, token: str) -> dict:
        """Verify and decode a JWT token.

        Args:
            token: JWT token string.

        Returns:
            dict: Decoded token payload containing:
                - sub: User ID
                - username: User's username
                - roles: List of role names
                - iat: Issued at timestamp
                - exp: Expiration timestamp

        Raises:
            InvalidTokenError: If token is invalid or expired.
        """
        ...

    def refresh_token(self, refresh_token: str) -> dict:
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
        ...

    def hash_password(self, password: str) -> str:
        """Hash a plain text password.

        Args:
            password: Plain text password.

        Returns:
            str: Bcrypt hashed password.
        """
        ...

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain text password against a hash.

        Args:
            plain_password: Plain text password to verify.
            hashed_password: Bcrypt hashed password to check against.

        Returns:
            bool: True if password matches, False otherwise.
        """
        ...

    def get_user_by_id(self, user_id: UUID) -> dict | None:
        """Get user information by user ID.

        Args:
            user_id: User's UUID.

        Returns:
            dict | None: User information dict or None if not found.
        """
        ...

    def get_user_roles(self, user_id: UUID) -> list[str]:
        """Get all role names for a user.

        Args:
            user_id: User's UUID.

        Returns:
            list[str]: List of role names.
        """
        ...
