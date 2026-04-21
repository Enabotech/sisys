"""Tests for Encryption Service.

TDD Red phase - tests should fail before implementation.
"""

from __future__ import annotations

import pytest

from src.infrastructure.security.encryption_service import (
    AES256EncryptionService,
    EncryptionService,
    get_aes256_service,
    get_encryption_service,
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


# =============================================================================
# AES256EncryptionService Tests
# =============================================================================


class TestAES256EncryptionService:
    """Tests for AES-256-GCM encryption service."""

    def test_init_with_master_key(self):
        """Should initialize with provided master key."""
        master_key = b"0" * 32  # 256-bit key
        service = AES256EncryptionService(master_key=master_key)
        assert service._master_key == master_key

    def test_init_without_master_key_generates_one(self):
        """Should generate random master key when none provided."""
        service = AES256EncryptionService()
        assert service._master_key is not None
        assert len(service._master_key) == 32  # 256 bits

    def test_generate_data_key(self):
        """Should generate derived data key."""
        service = AES256EncryptionService()
        data_key = service.generate_data_key("test-purpose")
        assert isinstance(data_key, bytes)
        assert len(data_key) == 32  # 256 bits

    def test_generate_data_key_different_purposes(self):
        """Should generate different keys for different purposes."""
        service = AES256EncryptionService()
        key1 = service.generate_data_key("purpose-1")
        key2 = service.generate_data_key("purpose-2")
        assert key1 != key2

    def test_encrypt_decrypt_roundtrip(self):
        """Should encrypt and decrypt data successfully."""
        service = AES256EncryptionService()
        plaintext = b"Hello, World!"

        ciphertext, nonce = service.encrypt(plaintext)
        decrypted = service.decrypt(ciphertext, nonce)

        assert decrypted == plaintext

    def test_encrypt_with_aad(self):
        """Should encrypt with additional authenticated data."""
        service = AES256EncryptionService()
        plaintext = b"Secret message"
        aad = b"associated data"

        ciphertext, nonce = service.encrypt(plaintext, aad)
        decrypted = service.decrypt(ciphertext, nonce, aad)

        assert decrypted == plaintext

    def test_decrypt_with_wrong_aad_fails(self):
        """Should fail decryption when AAD is wrong."""
        service = AES256EncryptionService()
        plaintext = b"Secret message"
        aad = b"original aad"
        wrong_aad = b"wrong aad"

        ciphertext, nonce = service.encrypt(plaintext, aad)

        with pytest.raises(ValueError):
            service.decrypt(ciphertext, nonce, wrong_aad)

    def test_decrypt_with_wrong_nonce_fails(self):
        """Should fail decryption when nonce is wrong."""
        service = AES256EncryptionService()
        plaintext = b"Secret message"

        ciphertext, nonce = service.encrypt(plaintext)
        wrong_nonce = b"0" * 12  # 96-bit nonce

        with pytest.raises(ValueError):
            service.decrypt(ciphertext, wrong_nonce)

    def test_encrypt_to_base64(self):
        """Should encrypt and return base64 encoded string."""
        service = AES256EncryptionService()
        plaintext = b"Hello, World!"

        encoded = service.encrypt_to_base64(plaintext)

        assert isinstance(encoded, str)
        # Base64 output should be decodable
        import base64

        decoded = base64.b64decode(encoded)
        assert len(decoded) > 16  # nonce (12) + some ciphertext

    def test_decrypt_from_base64(self):
        """Should decrypt base64 encoded data."""
        service = AES256EncryptionService()
        plaintext = b"Hello, World!"

        encoded = service.encrypt_to_base64(plaintext)
        decrypted = service.decrypt_from_base64(encoded)

        assert decrypted == plaintext

    def test_decrypt_from_base64_with_aad(self):
        """Should decrypt base64 encoded data with AAD."""
        service = AES256EncryptionService()
        plaintext = b"Secret message"
        aad = b"associated data"

        encoded = service.encrypt_to_base64(plaintext, aad)
        decrypted = service.decrypt_from_base64(encoded, aad)

        assert decrypted == plaintext

    def test_decrypt_invalid_data_fails(self):
        """Should raise ValueError for invalid ciphertext."""
        service = AES256EncryptionService()

        with pytest.raises(ValueError, match="Decryption failed"):
            service.decrypt(b"invalid", b"0" * 12)


class TestGlobalServiceInstances:
    """Tests for global service singleton functions."""

    def test_get_aes256_service_returns_singleton(self):
        """Should return same instance on multiple calls."""
        service1 = get_aes256_service()
        service2 = get_aes256_service()
        assert service1 is service2

    def test_get_encryption_service_returns_singleton(self):
        """Should return same instance on multiple calls."""
        service1 = get_encryption_service()
        service2 = get_encryption_service()
        assert service1 is service2
