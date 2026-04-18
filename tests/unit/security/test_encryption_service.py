"""Tests for Encryption Service.

TDD Red phase - tests should fail before implementation.
"""

from __future__ import annotations

import pytest

from src.infrastructure.security.encryption_service import (
    EncryptionService,
)


class TestEncryptionService:
    """Encryption Service tests."""

    @pytest.fixture
    def encryption_service(self) -> EncryptionService:
        """Create encryption service instance."""
        return EncryptionService()

    def test_hash_password(self, encryption_service: EncryptionService):
        """Should hash password using bcrypt."""
        password = "TestPassword123!"  # pragma: allowlist secret

        hashed = encryption_service.hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_verify_password_correct(self, encryption_service: EncryptionService):
        """Should verify correct password."""
        password = "TestPassword123!"  # pragma: allowlist secret
        hashed = encryption_service.hash_password(password)

        assert encryption_service.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self, encryption_service: EncryptionService):
        """Should return False for incorrect password."""
        password = "TestPassword123!"  # pragma: allowlist secret
        hashed = encryption_service.hash_password(password)

        assert encryption_service.verify_password("WrongPassword!", hashed) is False

    def test_validate_password_valid(self, encryption_service: EncryptionService):
        """Should return no errors for valid password."""
        password = "TestPassword123!"  # pragma: allowlist secret

        errors = encryption_service.validate_password_strength(password)

        assert len(errors) == 0

    def test_validate_password_too_short(self, encryption_service: EncryptionService):
        """Should report error for password that's too short."""
        password = "Abc1!"  # pragma: allowlist secret

        errors = encryption_service.validate_password_strength(password)

        assert len(errors) > 0
        assert any("at least 8 characters" in error for error in errors)

    def test_validate_password_no_uppercase(self, encryption_service: EncryptionService):
        """Should report error for password without uppercase."""
        password = "testpassword123!"  # pragma: allowlist secret

        errors = encryption_service.validate_password_strength(password)

        assert len(errors) > 0
        assert any("uppercase" in error.lower() for error in errors)

    def test_validate_password_no_lowercase(self, encryption_service: EncryptionService):
        """Should report error for password without lowercase."""
        password = "TESTPASSWORD123!"  # pragma: allowlist secret

        errors = encryption_service.validate_password_strength(password)

        assert len(errors) > 0
        assert any("lowercase" in error.lower() for error in errors)

    def test_validate_password_no_digit(self, encryption_service: EncryptionService):
        """Should report error for password without digit."""
        password = "TestPassword!"  # pragma: allowlist secret

        errors = encryption_service.validate_password_strength(password)

        assert len(errors) > 0
        assert any("digit" in error.lower() for error in errors)

    def test_validate_password_no_special(self, encryption_service: EncryptionService):
        """Should report error for password without special character."""
        password = "TestPassword123"  # pragma: allowlist secret

        errors = encryption_service.validate_password_strength(password)

        assert len(errors) > 0
        assert any("special" in error.lower() for error in errors)

    def test_is_password_strong_true(self, encryption_service: EncryptionService):
        """Should return True for strong password."""
        password = "TestPassword123!"  # pragma: allowlist secret

        assert encryption_service.is_password_strong(password) is True

    def test_is_password_strong_false(self, encryption_service: EncryptionService):
        """Should return False for weak password."""
        password = "weak"  # pragma: allowlist secret

        assert encryption_service.is_password_strong(password) is False

    def test_custom_requirements(self):
        """Should respect custom complexity requirements."""
        # Create service with only 6 char minimum, no special required
        service = EncryptionService(
            min_length=6,
            require_uppercase=False,
            require_lowercase=False,
            require_digit=False,
            require_special=False,
        )

        password = "test12"  # pragma: allowlist secret

        errors = service.validate_password_strength(password)

        assert len(errors) == 0
