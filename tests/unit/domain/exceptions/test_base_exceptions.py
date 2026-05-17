"""BaseException 领域异常根类单元测试

验证异常初始化、序列化、cause 处理和默认值行为
"""

from __future__ import annotations

from src.domain.exceptions.base_exceptions import BaseException


class TestBaseExceptionInit:
    """BaseException 初始化测试"""

    def test_default_message(self) -> None:
        """默认消息应为类级别 message"""
        ex = BaseException()
        assert ex.message == "Unknown error"

    def test_custom_message(self) -> None:
        """自定义消息应覆盖默认值"""
        ex = BaseException(message="custom error")
        assert ex.message == "custom error"

    def test_default_code(self) -> None:
        """默认 code 应为 EXCEPTION_000"""
        ex = BaseException()
        assert ex.code == "EXCEPTION_000"

    def test_cause_stored(self) -> None:
        """cause 应被正确存储"""
        original = ValueError("original")
        ex = BaseException(message="wrapped", cause=original)
        assert ex.cause is original

    def test_context_default_empty_dict(self) -> None:
        """context 默认应为空字典"""
        ex = BaseException()
        assert ex.context == {}

    def test_context_custom(self) -> None:
        """自定义 context 应被正确存储"""
        ctx = {"field": "value", "count": 42}
        ex = BaseException(context=ctx)
        assert ex.context == ctx

    def test_inherits_from_python_exception(self) -> None:
        """应继承自 Python 内置 Exception"""
        assert issubclass(BaseException, Exception)

    def test_str_representation(self) -> None:
        """str() 应返回 message"""
        ex = BaseException(message="test message")
        assert str(ex) == "test message"


class TestBaseExceptionToDict:
    """BaseException.to_dict() 序列化测试"""

    def test_basic_dict(self) -> None:
        """无 cause 时应返回 code/message/context"""
        ex = BaseException(message="test", context={"k": "v"})
        d = ex.to_dict()
        assert d["code"] == "EXCEPTION_000"
        assert d["message"] == "test"
        assert d["context"] == {"k": "v"}
        assert "cause" not in d

    def test_cause_domain_exception(self) -> None:
        """cause 为领域异常时应递归序列化"""
        inner = BaseException(message="inner error", context={"layer": "repo"})
        outer = BaseException(message="outer error", cause=inner)
        d = outer.to_dict()

        assert isinstance(d["cause"], dict)
        assert d["cause"]["message"] == "inner error"
        assert d["cause"]["code"] == "EXCEPTION_000"
        assert d["cause"]["context"] == {"layer": "repo"}

    def test_cause_plain_exception(self) -> None:
        """cause 为普通异常时应序列化为 type/message 字典"""
        inner = ValueError("plain error")
        outer = BaseException(message="wrapped", cause=inner)
        d = outer.to_dict()

        assert isinstance(d["cause"], dict)
        assert d["cause"]["type"] == "ValueError"
        assert d["cause"]["message"] == "plain error"

    def test_cause_runtime_error(self) -> None:
        """cause 为 RuntimeError 时应正确序列化"""
        inner = RuntimeError("timeout")
        outer = BaseException(message="operation failed", cause=inner)
        d = outer.to_dict()

        assert d["cause"]["type"] == "RuntimeError"
        assert d["cause"]["message"] == "timeout"

    def test_nested_domain_exceptions(self) -> None:
        """嵌套领域异常应完整递归序列化"""
        inner = BaseException(message="db error", context={"table": "users"})
        middle = BaseException(message="service error", cause=inner)
        outer = BaseException(message="api error", cause=middle)
        d = outer.to_dict()

        assert d["cause"]["message"] == "service error"
        assert d["cause"]["cause"]["message"] == "db error"
        assert d["cause"]["cause"]["context"]["table"] == "users"


class TestBaseExceptionSubclass:
    """子类化 BaseException 的行为测试"""

    def test_subclass_default_message(self) -> None:
        """子类可以定义自己的默认 message"""

        class NotFoundError(BaseException):
            code = "ERR_404"
            message = "Resource not found"

        ex = NotFoundError()
        assert ex.message == "Resource not found"
        assert ex.code == "ERR_404"

    def test_subclass_override_message(self) -> None:
        """子类实例可以覆盖默认 message"""

        class AuthError(BaseException):
            code = "ERR_AUTH"
            message = "Authentication failed"

        ex = AuthError(message="Token expired")
        assert ex.message == "Token expired"
        assert ex.code == "ERR_AUTH"

    def test_subclass_to_dict_preserves_code(self) -> None:
        """子类 to_dict 应使用子类的 code"""

        class ValidationError(BaseException):
            code = "ERR_VALIDATION"
            message = "Validation failed"

        ex = ValidationError(context={"field": "email"})
        d = ex.to_dict()
        assert d["code"] == "ERR_VALIDATION"
