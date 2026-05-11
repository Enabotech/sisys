"""Tests for JWTService - RED PHASE (failing tests).

TDD Phase 🔴: Tests must fail before implementation.
"""

# pragma: allowlist secret  # Test fixtures - not real secrets
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.domain.ports.auth_service import AuthenticationError
from src.infrastructure.config.auth import AuthConfig
from src.infrastructure.security.jwt_service import JWTService


class TestJWTServiceCreation:
    """Tests for JWT token creation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = AuthConfig(
            jwt_secret_key="test-secret-key-at-least-32-characters-long!",  # pragma: allowlist secret
            jwt_algorithm="HS256",
            jwt_expiration_hours=24,
            jwt_refresh_expiration_days=7,
        )
        self.jwt_service = JWTService(self.config)

    def test_create_access_token_returns_string(self):
        """🔴 RED: Access token should be a non-empty string."""
        user_id = uuid4()
        token = self.jwt_service.create_access_token(
            user_id=user_id,
            username="testuser",
            roles=["admin", "viewer"],
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_access_token_contains_three_parts(self):
        """🔴 RED: JWT should be JWT format (header.payload.signature)."""
        user_id = uuid4()
        token = self.jwt_service.create_access_token(
            user_id=user_id,
            username="testuser",
            roles=["admin"],
        )
        parts = token.split(".")
        assert len(parts) == 3, "JWT must have 3 parts"

    def test_create_access_token_with_custom_expiration(self):
        """🔴 RED: Custom expiration should be respected."""
        user_id = uuid4()
        custom_delta = timedelta(hours=1)
        token = self.jwt_service.create_access_token(
            user_id=user_id,
            username="testuser",
            roles=["admin"],
            expires_delta=custom_delta,
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token_returns_string(self):
        """🔴 RED: Refresh token should be a non-empty string."""
        user_id = uuid4()
        token = self.jwt_service.create_refresh_token(user_id=user_id)
        assert isinstance(token, str)
        assert len(token) > 0


class TestJWTServiceVerification:
    """Tests for JWT token verification."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = AuthConfig(
            jwt_secret_key="test-secret-key-at-least-32-characters-long!",  # pragma: allowlist secret
            jwt_algorithm="HS256",
            jwt_expiration_hours=24,
        )
        self.jwt_service = JWTService(self.config)

    def test_verify_valid_access_token_returns_token_payload(self):
        """🔴 RED: Valid access token should return TokenPayload."""
        user_id = uuid4()
        token = self.jwt_service.create_access_token(
            user_id=user_id,
            username="testuser",
            roles=["admin"],
        )
        payload = self.jwt_service.verify_token(token)
        assert payload is not None
        assert str(payload.user_id) == str(user_id)
        assert payload.username == "testuser"
        assert "admin" in payload.roles

    def test_verify_token_with_expired_token_raises_error(self):
        """🔴 RED: Expired token should raise AuthenticationError."""
        user_id = uuid4()
        # Create token that expires immediately
        token = self.jwt_service.create_access_token(
            user_id=user_id,
            username="testuser",
            roles=["admin"],
            expires_delta=timedelta(seconds=-1),  # Already expired
        )
        with pytest.raises(AuthenticationError):
            self.jwt_service.verify_token(token)

    def test_verify_token_with_invalid_signature_raises_error(self):
        """🔴 RED: Token with wrong signature should raise AuthenticationError."""
        user_id = uuid4()
        token = self.jwt_service.create_access_token(
            user_id=user_id,
            username="testuser",
            roles=["admin"],
        )
        # Try to verify with different secret
        other_config = AuthConfig(
            jwt_secret_key="different-secret-key-at-least-32-chars!",  # pragma: allowlist secret
            jwt_algorithm="HS256",
        )
        other_jwt_service = JWTService(other_config)
        with pytest.raises(AuthenticationError):
            other_jwt_service.verify_token(token)

    def test_verify_refresh_token_returns_user_id(self):
        """🔴 RED: Valid refresh token should return user UUID."""
        user_id = uuid4()
        token = self.jwt_service.create_refresh_token(user_id=user_id)
        result = self.jwt_service.verify_refresh_token(token)
        assert result == user_id

    def test_verify_access_token_as_refresh_raises_error(self):
        """🔴 RED: Access token cannot be used as refresh token."""
        user_id = uuid4()
        token = self.jwt_service.create_access_token(
            user_id=user_id,
            username="testuser",
            roles=["admin"],
        )
        with pytest.raises(AuthenticationError):
            self.jwt_service.verify_refresh_token(token)


class TestTokenPayloadMethods:
    """Tests for TokenPayload value object methods."""

    def test_is_expired_returns_false_for_valid_token(self):
        """🔴 RED: TokenPayload.is_expired() returns False for valid token."""
        from src.domain.value_objects.token_payload import TokenPayload

        future_exp = datetime.now(UTC) + timedelta(hours=1)
        payload = TokenPayload(
            user_id=uuid4(),
            username="testuser",
            roles=("admin",),
            exp=future_exp,
        )
        assert payload.is_expired() is False

    def test_is_expired_returns_true_for_expired_token(self):
        """🔴 RED: TokenPayload.is_expired() returns True for expired token."""
        from src.domain.value_objects.token_payload import TokenPayload

        past_exp = datetime.now(UTC) - timedelta(hours=1)
        payload = TokenPayload(
            user_id=uuid4(),
            username="testuser",
            roles=("admin",),
            exp=past_exp,
        )
        assert payload.is_expired() is True

    def test_has_role_returns_true_for_existing_role(self):
        """🔴 RED: TokenPayload.has_role() returns True for existing role."""
        from src.domain.value_objects.token_payload import TokenPayload

        payload = TokenPayload(
            user_id=uuid4(),
            username="testuser",
            roles=("admin", "viewer"),
            exp=datetime.now(UTC) + timedelta(hours=1),
        )
        assert payload.has_role("admin") is True

    def test_has_role_returns_false_for_missing_role(self):
        """🔴 RED: TokenPayload.has_role() returns False for missing role."""
        from src.domain.value_objects.token_payload import TokenPayload

        payload = TokenPayload(
            user_id=uuid4(),
            username="testuser",
            roles=("viewer",),
            exp=datetime.now(UTC) + timedelta(hours=1),
        )
        assert payload.has_role("admin") is False

    def test_has_any_role_returns_true_when_one_matches(self):
        """🔴 RED: TokenPayload.has_any_role() returns True when one role matches."""
        from src.domain.value_objects.token_payload import TokenPayload

        payload = TokenPayload(
            user_id=uuid4(),
            username="testuser",
            roles=("viewer",),
            exp=datetime.now(UTC) + timedelta(hours=1),
        )
        assert payload.has_any_role("admin", "viewer") is True

    def test_has_any_role_returns_false_when_none_match(self):
        """🔴 RED: TokenPayload.has_any_role() returns False when no roles match."""
        from src.domain.value_objects.token_payload import TokenPayload

        payload = TokenPayload(
            user_id=uuid4(),
            username="testuser",
            roles=("guest",),
            exp=datetime.now(UTC) + timedelta(hours=1),
        )
        assert payload.has_any_role("admin", "viewer") is False
