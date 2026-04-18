"""Encryption Service — Password hashing and verification utilities.

Provides password hashing using bcrypt via passlib.
Reference: 等保 2.0 password complexity requirements.
"""

from __future__ import annotations

import re
from typing import cast

from passlib.context import CryptContext

# Password hashing context using bcrypt
# bcrypt automatically handles salt generation
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_PASSWORD_MIN_LENGTH = 8
_PASSWORD_PATTERN_UPPERCASE = re.compile(r"[A-Z]")
_PASSWORD_PATTERN_LOWERCASE = re.compile(r"[a-z]")
_PASSWORD_PATTERN_DIGIT = re.compile(r"\d")
_PASSWORD_PATTERN_SPECIAL = re.compile(r"[!@#$%^&*(),.?\":{}|<>]")


class PasswordComplexityError(Exception):
    """Password does not meet complexity requirements."""

    pass


class EncryptionService:
    """Encryption service for password hashing and verification.

    Implements 等保 2.0 password complexity requirements:
    - Minimum 8 characters
    - Uppercase and lowercase letters
    - Numbers
    - Special characters
    """

    def __init__(
        self,
        min_length: int = _PASSWORD_MIN_LENGTH,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digit: bool = True,
        require_special: bool = True,
    ) -> None:
        """Initialize encryption service.

        Args:
            min_length: Minimum password length.
            require_uppercase: Require at least one uppercase letter.
            require_lowercase: Require at least one lowercase letter.
            require_digit: Require at least one digit.
            require_special: Require at least one special character.
        """
        self._min_length = min_length
        self._require_uppercase = require_uppercase
        self._require_lowercase = require_lowercase
        self._require_digit = require_digit
        self._require_special = require_special

    def hash_password(self, password: str) -> str:
        """Hash a plain text password using bcrypt.

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

    def validate_password_strength(self, password: str) -> list[str]:
        """Validate password meets complexity requirements.

        Args:
            password: Password to validate.

        Returns:
            list[str]: List of validation errors (empty if valid).
        """
        errors = []

        if len(password) < self._min_length:
            errors.append(f"Password must be at least {self._min_length} characters long")

        if self._require_uppercase and not _PASSWORD_PATTERN_UPPERCASE.search(password):
            errors.append("Password must contain at least one uppercase letter")

        if self._require_lowercase and not _PASSWORD_PATTERN_LOWERCASE.search(password):
            errors.append("Password must contain at least one lowercase letter")

        if self._require_digit and not _PASSWORD_PATTERN_DIGIT.search(password):
            errors.append("Password must contain at least one digit")

        if self._require_special and not _PASSWORD_PATTERN_SPECIAL.search(password):
            errors.append("Password must contain at least one special character")

        return errors

    def is_password_strong(self, password: str) -> bool:
        """Check if password meets all complexity requirements.

        Args:
            password: Password to check.

        Returns:
            bool: True if password is strong enough, False otherwise.
        """
        return len(self.validate_password_strength(password)) == 0


# Global encryption service instance
_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """Get the global EncryptionService instance.

    Returns:
        EncryptionService: The global encryption service instance.
    """
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
