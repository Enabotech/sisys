"""Tests for PasswordValidationServicePort interface."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.domain.ports.password_validation_service import (
    PasswordValidationError,
    PasswordValidationServicePort,
)


class TestPasswordValidationServiceSignature:
    """Structural signature tests — verify sync contract."""

    def test_validate_exists(self) -> None:
        """validate method must exist."""
        assert hasattr(PasswordValidationServicePort, "validate")

    def test_get_requirements_exists(self) -> None:
        """get_requirements method must exist."""
        assert hasattr(PasswordValidationServicePort, "get_requirements")


class TestPasswordValidationServiceMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec constraint."""

    def test_mock_validate_verified(self) -> None:
        """Mock validate should be verifiable."""
        mock = MagicMock(spec=PasswordValidationServicePort)
        mock.validate.return_value = None

        mock.validate("ValidPass123!")
        mock.validate.assert_called_once_with("ValidPass123!")

    def test_mock_validate_raises_on_invalid(self) -> None:
        """Mock validate should raise PasswordValidationError on invalid password."""
        mock = MagicMock(spec=PasswordValidationServicePort)
        mock.validate.side_effect = PasswordValidationError(message="Password too short", code="PASSWORD_TOO_SHORT")

        with pytest.raises(PasswordValidationError) as exc_info:
            mock.validate("weak")
        assert exc_info.value.code == "PASSWORD_TOO_SHORT"

    def test_mock_get_requirements_verified(self) -> None:
        """Mock get_requirements should be verifiable."""
        mock = MagicMock(spec=PasswordValidationServicePort)
        mock.get_requirements.return_value = {
            "min_length": "8",
            "require_uppercase": "true",
            "require_lowercase": "true",
            "require_digit": "true",
            "require_special": "true",
        }

        result = mock.get_requirements()
        assert result["min_length"] == "8"
        mock.get_requirements.assert_called_once()
