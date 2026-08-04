"""PasswordValidationServicePort 端口契约测试

验证 PasswordValidationServicePort 的结构化子类型合规性。
"""

from __future__ import annotations

import inspect

from src.domain.ports.password_validation_service import PasswordValidationServicePort


class TestPasswordValidationServicePortContract:
    """测试 PasswordValidationServicePort 端口契约"""

    def test_protocol_is_runtime_checkable(self) -> None:
        """验证 Protocol 使用 @runtime_checkable 装饰器"""
        assert hasattr(PasswordValidationServicePort, "_is_runtime_protocol")
        assert PasswordValidationServicePort._is_runtime_protocol is True  # type: ignore[attr-defined]

    def test_validate_method_exists(self) -> None:
        """验证 validate 方法存在"""
        assert hasattr(PasswordValidationServicePort, "validate")
        method = getattr(PasswordValidationServicePort, "validate")
        assert callable(method)

    def test_validate_method_signature(self) -> None:
        """验证 validate(password) -> None"""
        method = getattr(PasswordValidationServicePort, "validate")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert params == ["self", "password"]
        assert sig.return_annotation == "None"

    def test_get_requirements_method_exists(self) -> None:
        """验证 get_requirements 方法存在"""
        assert hasattr(PasswordValidationServicePort, "get_requirements")
        method = getattr(PasswordValidationServicePort, "get_requirements")
        assert callable(method)

    def test_get_requirements_return_type(self) -> None:
        """验证 get_requirements 返回 dict[str, str]"""
        method = getattr(PasswordValidationServicePort, "get_requirements")
        sig = inspect.signature(method)
        assert sig.return_annotation == "dict[str, str]"

    def test_compliant_implementation(self) -> None:
        """验证合规实现可通过 isinstance 检查"""

        class MockValidator:
            def validate(self, password: str) -> None:
                pass

            def get_requirements(self) -> dict[str, str]:
                return {"min_length": "8"}

        validator = MockValidator()
        assert isinstance(validator, PasswordValidationServicePort)

    def test_noncompliant_implementation_fails(self) -> None:
        """验证不合规实现无法通过 isinstance 检查"""

        class BadValidator:
            pass

        assert not isinstance(BadValidator(), PasswordValidationServicePort)


__all__ = ["TestPasswordValidationServicePortContract"]
