"""PasswordValidationService 单元测试."""

from __future__ import annotations

import pytest

from src.domain.ports.password_validation_service import PasswordValidationError
from src.infrastructure.security.password_validation_service import (
    PasswordValidationService,
)


@pytest.fixture
def service():
    return PasswordValidationService()


class TestPasswordValidationService:
    """PasswordValidationService 测试."""

    def test_validate_valid_password(self, service):
        """测试有效密码通过验证."""
        password = "Test@1234"  # pragma: allowlist secret
        # Should not raise
        service.validate(password)

    def test_validate_password_too_short(self, service):
        """测试密码太短被拒绝."""
        password = "short"  # pragma: allowlist secret
        with pytest.raises(PasswordValidationError) as exc_info:
            service.validate(password)
        assert "PASSWORD_WEAK" in exc_info.value.code

    def test_validate_password_no_uppercase(self, service):
        """测试密码缺少大写字母被拒绝."""
        password = "test@1234"  # pragma: allowlist secret
        with pytest.raises(PasswordValidationError) as exc_info:
            service.validate(password)
        assert "PASSWORD_WEAK" in exc_info.value.code

    def test_validate_password_no_lowercase(self, service):
        """测试密码缺少小写字母被拒绝."""
        password = "TEST@1234"  # pragma: allowlist secret
        with pytest.raises(PasswordValidationError) as exc_info:
            service.validate(password)
        assert "PASSWORD_WEAK" in exc_info.value.code

    def test_validate_password_no_digit(self, service):
        """测试密码缺少数字被拒绝."""
        password = "Test@abcd"  # pragma: allowlist secret
        with pytest.raises(PasswordValidationError) as exc_info:
            service.validate(password)
        assert "PASSWORD_WEAK" in exc_info.value.code

    def test_validate_password_no_special_char(self, service):
        """测试密码缺少特殊字符被拒绝."""
        password = "Test1234"  # pragma: allowlist secret
        with pytest.raises(PasswordValidationError) as exc_info:
            service.validate(password)
        assert "PASSWORD_WEAK" in exc_info.value.code

    def test_get_requirements(self, service):
        """测试获取密码复杂度要求."""
        requirements = service.get_requirements()
        assert "min_length" in requirements
        assert "uppercase" in requirements
        assert "lowercase" in requirements
        assert "digit" in requirements
        assert "special" in requirements
        assert requirements["min_length"] == "至少 8 个字符"
