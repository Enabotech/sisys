"""Tests for JWT Service.

TDD Red phase - tests should fail before implementation.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.infrastructure.security.jwt_service import (
    InvalidTokenError,
    JWTService,
    TokenExpiredError,
)


class TestJWTService:
    """JWT Service tests."""

    @pytest.fixture
    def jwt_service(self) -> JWTService:
        """Create JWT service instance for testing."""
        from src.infrastructure.config.auth import AuthConfig

        config = AuthConfig(
            jwt_secret_key="test-secret-key-for-testing-only",  # pragma: allowlist secret
            jwt_algorithm="HS256",
            jwt_expiration_hours=24,
            jwt_refresh_expiration_days=7,
        )
        return JWTService(config)

    def test_create_access_token(self, jwt_service: JWTService):
        """Should create a valid JWT access token."""
        user_id = uuid4()
        username = "testuser"
        roles = ["admin", "viewer"]

        token = jwt_service.create_access_token(
            user_id=user_id,
            username=username,
            roles=roles,
        )

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_contains_claims(self, jwt_service: JWTService):
        """Should create token with correct claims."""
        user_id = uuid4()
        username = "testuser"
        roles = ["admin"]

        token = jwt_service.create_access_token(
            user_id=user_id,
            username=username,
            roles=roles,
        )

        payload = jwt_service.verify_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["username"] == username
        assert payload["roles"] == roles
        assert payload["type"] == "access"
        assert "iat" in payload
        assert "exp" in payload

    def test_create_refresh_token(self, jwt_service: JWTService):
        """Should create a valid JWT refresh token."""
        user_id = uuid4()

        token = jwt_service.create_refresh_token(user_id)

        assert token is not None
        assert isinstance(token, str)

    def test_create_refresh_token_contains_claims(self, jwt_service: JWTService):
        """Should create refresh token with correct claims."""
        user_id = uuid4()

        token = jwt_service.create_refresh_token(user_id)
        payload = jwt_service.verify_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
        assert "iat" in payload
        assert "exp" in payload

    def test_verify_valid_token(self, jwt_service: JWTService):
        """Should verify a valid token."""
        user_id = uuid4()

        token = jwt_service.create_access_token(
            user_id=user_id,
            username="testuser",
            roles=["admin"],
        )

        payload = jwt_service.verify_token(token)

        assert payload["sub"] == str(user_id)

    def test_verify_expired_token(self, jwt_service: JWTService):
        """Should raise TokenExpiredError for expired token."""
        import time

        from src.infrastructure.config.auth import AuthConfig

        # Create service with very short expiration
        config = AuthConfig(
            jwt_secret_key="test-secret-key",  # pragma: allowlist secret
            jwt_algorithm="HS256",
            jwt_expiration_hours=0,  # 0 hours - will be expired immediately
            jwt_refresh_expiration_days=0,
        )
        service = JWTService(config)

        user_id = uuid4()
        token = service.create_access_token(
            user_id=user_id,
            username="testuser",
            roles=[],
        )

        # Token should be expired after a short delay
        time.sleep(1)
        with pytest.raises(TokenExpiredError):
            service.verify_token(token)

    def test_verify_invalid_token(self, jwt_service: JWTService):
        """Should raise InvalidTokenError for invalid token."""
        with pytest.raises(InvalidTokenError):
            jwt_service.verify_token("invalid.token.string")

    def test_verify_token_wrong_secret(self):
        """Should raise InvalidTokenError when secret key doesn't match."""
        from src.infrastructure.config.auth import AuthConfig

        config1 = AuthConfig(
            jwt_secret_key="secret-key-one",  # pragma: allowlist secret
            jwt_algorithm="HS256",
        )
        config2 = AuthConfig(
            jwt_secret_key="secret-key-two",  # pragma: allowlist secret
            jwt_algorithm="HS256",
        )

        service1 = JWTService(config1)
        service2 = JWTService(config2)

        token = service1.create_access_token(
            user_id=uuid4(),
            username="testuser",
            roles=[],
        )

        with pytest.raises(InvalidTokenError):
            service2.verify_token(token)

    def test_get_user_id_from_token(self, jwt_service: JWTService):
        """Should extract user ID from token."""
        user_id = uuid4()

        token = jwt_service.create_access_token(
            user_id=user_id,
            username="testuser",
            roles=[],
        )

        extracted_id = jwt_service.get_user_id_from_token(token)

        assert extracted_id == user_id

    def test_get_token_type_access(self, jwt_service: JWTService):
        """Should return 'access' for access token."""
        token = jwt_service.create_access_token(
            user_id=uuid4(),
            username="testuser",
            roles=[],
        )

        assert jwt_service.get_token_type(token) == "access"
        assert jwt_service.is_access_token(token)
        assert not jwt_service.is_refresh_token(token)

    def test_get_token_type_refresh(self, jwt_service: JWTService):
        """Should return 'refresh' for refresh token."""
        token = jwt_service.create_refresh_token(uuid4())

        assert jwt_service.get_token_type(token) == "refresh"
        assert jwt_service.is_refresh_token(token)
        assert not jwt_service.is_access_token(token)

    def test_get_expires_in(self, jwt_service: JWTService):
        """Should return expiration time in seconds."""
        expires_in = jwt_service.get_expires_in()

        # 24 hours * 3600 seconds = 86400
        assert expires_in == 24 * 3600

    def test_decode_token_without_verification(self, jwt_service: JWTService):
        """Should decode token without verification (for debugging)."""
        token = jwt_service.create_access_token(
            user_id=uuid4(),
            username="testuser",
            roles=["admin"],
        )

        payload = jwt_service.decode_token(token)

        assert payload["username"] == "testuser"
        assert payload["roles"] == ["admin"]
