"""Tests for Deng Bao 2.0 Compliance - Identity & Access Control.

TDD Phase 🔴: Tests for compliance validation.
Tests for password complexity, account lockout, session timeout.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class PasswordComplexityValidator:
    """Validates password meets complexity requirements.

    Minimal implementation for GREEN phase.
    """

    def __init__(
        self,
        min_length: int = 8,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digit: bool = True,
        require_special: bool = True,
    ):
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digit = require_digit
        self.require_special = require_special

    def validate(self, password: str) -> tuple[bool, list[str]]:
        """Validate password complexity.

        Returns:
            (is_valid, list of error messages)
        """
        errors = []

        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters")

        if self.require_uppercase and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")

        if self.require_lowercase and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")

        if self.require_digit and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")

        if self.require_special and not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?`~" for c in password):
            errors.append("Password must contain at least one special character")

        return (len(errors) == 0, errors)


class AccountLockoutValidator:
    """Validates account lockout policy compliance."""

    def __init__(
        self,
        max_login_attempts: int = 5,
        lockout_duration_minutes: int = 30,
    ):
        self.max_login_attempts = max_login_attempts
        self.lockout_duration = timedelta(minutes=lockout_duration_minutes)

    def is_locked(self, failed_attempts: int, locked_until: datetime | None) -> bool:
        """Check if account is locked."""
        if failed_attempts < self.max_login_attempts:
            return False
        if locked_until is None:
            return True
        return datetime.now(UTC) < locked_until

    def calculate_lockout_end(self, failed_attempts: int) -> datetime | None:
        """Calculate when lockout ends."""
        if failed_attempts < self.max_login_attempts:
            return None
        return datetime.now(UTC) + self.lockout_duration


class TestPasswordComplexity:
    """Tests for password complexity validation (Deng Bao 2.0)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = PasswordComplexityValidator()

    def test_password_validates_successfully(self):
        """🔴 RED: Valid password should pass all checks."""
        password = "Password123!"  # pragma: allowlist secret

        is_valid, errors = self.validator.validate(password)

        assert is_valid is True
        assert len(errors) == 0

    def test_password_too_short(self):
        """🔴 RED: Password shorter than min length should fail."""
        password = "Pass1!"  # pragma: allowlist secret

        is_valid, errors = self.validator.validate(password)

        assert is_valid is False
        assert any("at least 8 characters" in e for e in errors)

    def test_password_missing_uppercase(self):
        """🔴 RED: Password without uppercase should fail."""
        password = "password123!"  # pragma: allowlist secret

        is_valid, errors = self.validator.validate(password)

        assert is_valid is False
        assert any("uppercase" in e.lower() for e in errors)

    def test_password_missing_lowercase(self):
        """🔴 RED: Password without lowercase should fail."""
        password = "PASSWORD123!"  # pragma: allowlist secret

        is_valid, errors = self.validator.validate(password)

        assert is_valid is False
        assert any("lowercase" in e.lower() for e in errors)

    def test_password_missing_digit(self):
        """🔴 RED: Password without digit should fail."""
        password = "Password!"  # pragma: allowlist secret

        is_valid, errors = self.validator.validate(password)

        assert is_valid is False
        assert any("digit" in e.lower() for e in errors)

    def test_password_missing_special(self):
        """🔴 RED: Password without special character should fail."""
        password = "Password123"  # pragma: allowlist secret

        is_valid, errors = self.validator.validate(password)

        assert is_valid is False
        assert any("special" in e.lower() for e in errors)


class TestAccountLockout:
    """Tests for account lockout (Deng Bao 2.0)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = AccountLockoutValidator()

    def test_account_not_locked_under_threshold(self):
        """🔴 RED: Account with failed attempts under threshold should not be locked."""
        is_locked = self.validator.is_locked(failed_attempts=3, locked_until=None)

        assert is_locked is False

    def test_account_locked_at_threshold(self):
        """🔴 RED: Account with failed attempts at threshold should be locked."""
        is_locked = self.validator.is_locked(failed_attempts=5, locked_until=None)

        assert is_locked is True

    def test_account_locked_with_future_unlock_time(self):
        """🔴 RED: Account with future unlock time should be locked."""
        future_time = datetime.now(UTC) + timedelta(minutes=30)
        is_locked = self.validator.is_locked(failed_attempts=5, locked_until=future_time)

        assert is_locked is True

    def test_account_unlock_after_duration(self):
        """🔴 RED: Account should unlock after lockout duration."""
        past_time = datetime.now(UTC) - timedelta(minutes=1)
        is_locked = self.validator.is_locked(failed_attempts=5, locked_until=past_time)

        assert is_locked is False

    def test_calculate_lockout_end_returns_future_time(self):
        """🔴 RED: Lockout end time should be in the future."""
        lockout_end = self.validator.calculate_lockout_end(failed_attempts=5)

        assert lockout_end is not None
        assert lockout_end > datetime.now(UTC)

    def test_calculate_lockout_end_returns_none_under_threshold(self):
        """🔴 RED: Lockout end time should be None when under threshold."""
        lockout_end = self.validator.calculate_lockout_end(failed_attempts=3)

        assert lockout_end is None


class TestSessionTimeout:
    """Tests for session timeout (Deng Bao 2.0)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.session_timeout_minutes = 30

    def test_session_valid_before_timeout(self):
        """🔴 RED: Session should be valid if last activity is recent."""
        last_activity = datetime.now(UTC) - timedelta(minutes=10)
        is_expired = self._is_session_expired(last_activity, self.session_timeout_minutes)

        assert is_expired is False

    def test_session_expired_after_timeout(self):
        """🔴 RED: Session should be expired if last activity is too long ago."""
        last_activity = datetime.now(UTC) - timedelta(minutes=31)
        is_expired = self._is_session_expired(last_activity, self.session_timeout_minutes)

        assert is_expired is True

    def test_session_expired_at_exact_timeout(self):
        """🔴 RED: Session should be expired at exact timeout boundary."""
        last_activity = datetime.now(UTC) - timedelta(minutes=30)
        is_expired = self._is_session_expired(last_activity, self.session_timeout_minutes)

        assert is_expired is True

    def _is_session_expired(self, last_activity: datetime, timeout_minutes: int) -> bool:
        """Check if session is expired based on last activity."""
        elapsed = datetime.now(UTC) - last_activity
        return elapsed > timedelta(minutes=timeout_minutes)
