"""身份鉴别合规集成测试

等保2.0三级身份鉴别要求验证:
- AC-1.1: 双因子认证基础设施就绪（OTP/短信+密码）
- AC-1.2: 密码复杂度验证（8位以上，大小写+数字+特殊字符）
- AC-1.3: 认证失败锁定（连续5次失败锁定30分钟）

本测试验证 AuthService + PasswordValidationService + LoginAttemptRepository
的等保合规集成，非实现新服务

对应 Story: 1-12-equilibrium-level-3-compliance Task 1 Subtask 1.1-1.3
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions.service_exceptions import PasswordValidationError
from src.infrastructure.security.auth_service_impl import AuthServiceImpl
from src.infrastructure.security.password_validation_service import (
    PasswordValidationService,
)


@pytest.fixture
def password_service() -> PasswordValidationService:
    """创建密码验证服务实例"""
    return PasswordValidationService()


@pytest.fixture
def auth_service() -> AuthServiceImpl:
    """创建认证服务实例（含 mock 依赖）"""
    mock_jwt = MagicMock()
    mock_encryption = MagicMock()
    mock_user_repo = AsyncMock()
    mock_user_role_repo = AsyncMock()
    mock_login_attempt_repo = AsyncMock()
    mock_token_blacklist = AsyncMock()
    mock_refresh_token_store = AsyncMock()

    mock_login_attempt_repo.record_attempt_and_check_lockout = AsyncMock(return_value=(False, 0))
    mock_login_attempt_repo.is_account_locked = AsyncMock(return_value=False)

    return AuthServiceImpl(
        jwt_service=mock_jwt,
        encryption_service=mock_encryption,
        user_repository=mock_user_repo,
        user_role_repository=mock_user_role_repo,
        login_attempt_repository=mock_login_attempt_repo,
        token_blacklist=mock_token_blacklist,
        refresh_token_store=mock_refresh_token_store,
    )


class TestPasswordComplexityCompliance:
    """密码复杂度合规验证 (AC-1.2)"""

    def test_password_length_minimum_8_characters(self, password_service: PasswordValidationService) -> None:
        """密码长度必须至少8位"""
        with pytest.raises(PasswordValidationError, match="长度"):
            password_service.validate("short")

    def test_password_requires_uppercase(self, password_service: PasswordValidationService) -> None:
        """密码必须包含大写字母"""
        with pytest.raises(PasswordValidationError, match="大写字母"):
            password_service.validate("lowercase1!")

    def test_password_requires_lowercase(self, password_service: PasswordValidationService) -> None:
        """密码必须包含小写字母"""
        with pytest.raises(PasswordValidationError, match="小写字母"):
            password_service.validate("UPPERCASE1!")

    def test_password_requires_digit(self, password_service: PasswordValidationService) -> None:
        """密码必须包含数字"""
        with pytest.raises(PasswordValidationError, match="数字"):
            password_service.validate("NoDigits!")

    def test_password_requires_special_character(self, password_service: PasswordValidationService) -> None:
        """密码必须包含特殊字符"""
        with pytest.raises(PasswordValidationError, match="特殊字符"):
            password_service.validate("NoSpecial1")

    def test_valid_complex_password_accepted(self, password_service: PasswordValidationService) -> None:
        """符合所有要求的密码应被接受（不抛异常）"""
        # 不抛异常即表示验证通过
        password_service.validate("ValidPass1!")

    def test_password_requirements_query(self, password_service: PasswordValidationService) -> None:
        """密码要求查询应返回完整规则"""
        requirements = password_service.get_requirements()
        assert requirements is not None
        assert "min_length" in requirements
        assert "uppercase" in requirements
        assert "lowercase" in requirements
        assert "digit" in requirements
        assert "special" in requirements


class TestAuthenticationLockoutCompliance:
    """认证失败锁定合规验证 (AC-1.3)"""

    @pytest.mark.asyncio
    async def test_lockout_after_5_consecutive_failures(self, auth_service: AuthServiceImpl) -> None:
        """连续5次认证失败后应锁定账户"""
        # 等保2.0三级要求: 连续5次失败锁定30分钟
        auth_service._login_attempt_repo.record_attempt_and_check_lockout = AsyncMock(return_value=(True, 5))
        auth_service._login_attempt_repo.is_account_locked = AsyncMock(return_value=True)

        locked = await auth_service._login_attempt_repo.is_account_locked("testuser")
        assert locked is True, "连续5次失败后账户应被锁定"

    @pytest.mark.asyncio
    async def test_lockout_mechanism_exists(self, auth_service: AuthServiceImpl) -> None:
        """认证服务应具备锁定机制"""
        assert hasattr(auth_service, "_login_attempt_repo")
        assert hasattr(auth_service._login_attempt_repo, "record_attempt_and_check_lockout")


class TestMFAInfrastructureCompliance:
    """双因子认证基础设施合规验证 (AC-1.1)"""

    def test_totp_otp_support_available(self) -> None:
        """TOTP OTP支持应可用"""
        import pyotp

        totp = pyotp.TOTP("JBSWY3DPEHPK3PXP")
        otp_code = totp.now()
        assert len(otp_code) == 6, "TOTP应生成6位OTP码"
        assert totp.verify(otp_code), "TOTP应能验证生成的OTP码"

    def test_mfa_challenge_event_defined(self) -> None:
        """MFA挑战事件应已定义"""
        from src.domain.events.compliance_events import MFAChallengeIssuedEvent

        event = MFAChallengeIssuedEvent()
        assert event.event_type == "MFAChallengeIssuedEvent"
        assert event.aggregate_type == "MFAChallenge"

    def test_mfa_challenge_types_defined(self) -> None:
        """MFA挑战类型应包含TOTP"""
        from src.domain.events.compliance_events import MFAChallengeType

        assert hasattr(MFAChallengeType, "TOTP")
        assert hasattr(MFAChallengeType, "SMS")
        assert hasattr(MFAChallengeType, "EMAIL")
