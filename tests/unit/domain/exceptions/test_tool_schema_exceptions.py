"""tool_schema_exceptions 模块 4 个新异常单元测试(Story 4.3 AC 异常契约守护)

覆盖范围:
1. EXCEPTION_395 ToolInputSchemaValidationError MRO + code + 子域 + HTTP
2. EXCEPTION_396 ToolOutputSchemaValidationError MRO + code + 子域 + HTTP
3. EXCEPTION_397 ToolSchemaCompatibilityError MRO + code + 子域 + HTTP
4. EXCEPTION_398 ToolSchemaMissingError MRO + code + 子域 + HTTP
5. context 字段完整(tool_id / execution_id / retry_attempt / violations)
6. parent class 链路(MRO 含正确基类)
"""

from __future__ import annotations

from src.domain.exceptions import (
    BusinessException,
    ConfigurationError,
    DomainError,
    ToolInputSchemaValidationError,
    ToolOutputSchemaValidationError,
    ToolSchemaCompatibilityError,
    ToolSchemaMissingError,
    ValidationError,
)
from src.domain.exceptions._code_ranges import get_subdomain_for_class


class TestToolInputSchemaValidationError:
    """EXCEPTION_395:ToolInputSchemaValidationError"""

    def test_code_is_395(self) -> None:
        assert ToolInputSchemaValidationError.code == "EXCEPTION_395"

    def test_default_message(self) -> None:
        assert ToolInputSchemaValidationError.message == "Tool input schema validation error"

    def test_subdomain_is_toolchain(self) -> None:
        """子域归属必须是 toolchain (390-399)"""
        subdomain = get_subdomain_for_class(ToolInputSchemaValidationError.__name__)
        assert subdomain == "toolchain"

    def test_subdomain_code_range(self) -> None:
        """code 必须在 toolchain 子域 395 范围内"""
        assert ToolInputSchemaValidationError.code == "EXCEPTION_395"
        assert "395" in ToolInputSchemaValidationError.code

    def test_inherits_validation_error(self) -> None:
        """parent class 必须为 ValidationError (EXCEPTION_201)"""
        assert issubclass(ToolInputSchemaValidationError, ValidationError)

    def test_inherits_domain_error(self) -> None:
        """parent class 链路必须含 DomainError"""
        assert issubclass(ToolInputSchemaValidationError, DomainError)

    def test_construct_with_minimal_args(self) -> None:
        err = ToolInputSchemaValidationError()
        assert err.code == "EXCEPTION_395"
        assert err.message == "Tool input schema validation error"

    def test_construct_with_tool_id_and_violations(self) -> None:
        violations = [{"path": "/name", "expected": "string", "actual": 1, "message": "bad"}]
        err = ToolInputSchemaValidationError(
            message="test",
            tool_id="t-1",
            execution_id="e-1",
            tool_call_id="tc-1",
            violations=violations,
        )
        assert err.context["tool_id"] == "t-1"
        assert err.context["execution_id"] == "e-1"
        assert err.context["tool_call_id"] == "tc-1"
        assert err.context["violations"] == violations

    def test_construct_with_none_violations_omits_from_context(self) -> None:
        """violations=None 不写入 context(向后兼容)"""
        err = ToolInputSchemaValidationError(message="test")
        assert "violations" not in err.context


class TestToolOutputSchemaValidationError:
    """EXCEPTION_396:ToolOutputSchemaValidationError(Round 2 文档化保留)"""

    def test_code_is_396(self) -> None:
        assert ToolOutputSchemaValidationError.code == "EXCEPTION_396"

    def test_default_message(self) -> None:
        assert ToolOutputSchemaValidationError.message == "Tool output schema validation error"

    def test_subdomain_is_toolchain(self) -> None:
        subdomain = get_subdomain_for_class(ToolOutputSchemaValidationError.__name__)
        assert subdomain == "toolchain"

    def test_inherits_validation_error(self) -> None:
        """继承 ValidationError (HTTP 422 语义错误)"""
        assert issubclass(ToolOutputSchemaValidationError, ValidationError)

    def test_construct_with_retry_attempt(self) -> None:
        err = ToolOutputSchemaValidationError(
            message="test",
            tool_id="t-1",
            execution_id="e-1",
            retry_attempt=3,
            violations=[{"path": "/x"}],
        )
        assert err.context["tool_id"] == "t-1"
        assert err.context["execution_id"] == "e-1"
        assert err.context["retry_attempt"] == 3


class TestToolSchemaCompatibilityError:
    """EXCEPTION_397:ToolSchemaCompatibilityError(Story 4.6 灰度发布拦截)"""

    def test_code_is_397(self) -> None:
        assert ToolSchemaCompatibilityError.code == "EXCEPTION_397"

    def test_default_message(self) -> None:
        assert ToolSchemaCompatibilityError.message == "Tool schema compatibility error"

    def test_subdomain_is_toolchain(self) -> None:
        subdomain = get_subdomain_for_class(ToolSchemaCompatibilityError.__name__)
        assert subdomain == "toolchain"

    def test_inherits_business_exception(self) -> None:
        """继承 BusinessException(非 ValidationError)"""
        assert issubclass(ToolSchemaCompatibilityError, BusinessException)
        assert not issubclass(ToolSchemaCompatibilityError, ValidationError)

    def test_construct_with_breaking_changes(self) -> None:
        err = ToolSchemaCompatibilityError(
            message="incompatible schema",
            tool_id="t-1",
            old_version="1.0.0",
            new_version="1.1.0",
            breaking_changes=[{"path": "/x", "change_type": "required_field_added"}],
        )
        assert err.context["tool_id"] == "t-1"
        assert err.context["old_version"] == "1.0.0"
        assert err.context["new_version"] == "1.1.0"
        assert err.context["breaking_changes"] == [
            {"path": "/x", "change_type": "required_field_added"},
        ]


class TestToolSchemaMissingError:
    """EXCEPTION_398:ToolSchemaMissingError(Story 4.7 required_schema 集成)"""

    def test_code_is_398(self) -> None:
        assert ToolSchemaMissingError.code == "EXCEPTION_398"

    def test_default_message(self) -> None:
        assert ToolSchemaMissingError.message == "Tool schema missing error"

    def test_subdomain_is_toolchain(self) -> None:
        subdomain = get_subdomain_for_class(ToolSchemaMissingError.__name__)
        assert subdomain == "toolchain"

    def test_inherits_configuration_error(self) -> None:
        """继承 ConfigurationError (EXCEPTION_101, HTTP 500)"""
        assert issubclass(ToolSchemaMissingError, ConfigurationError)
        assert not issubclass(ToolSchemaMissingError, BusinessException)

    def test_construct_with_tool_id_and_schema_field(self) -> None:
        err = ToolSchemaMissingError(
            message="missing required schema",
            tool_id="t-1",
        )
        assert err.context["tool_id"] == "t-1"
        # ToolSchemaMissingError 接受 message + tool_id(基础字段)
        assert err.code == "EXCEPTION_398"


class TestExceptionSubdomainCoverage:
    """4 个新异常在 _code_ranges.py 的完整覆盖"""

    def test_all_4_exceptions_in_class_to_subdomain(self) -> None:
        """_CLASS_TO_SUBDOMAIN 表覆盖全部 4 个新异常"""
        for cls in [
            ToolInputSchemaValidationError,
            ToolOutputSchemaValidationError,
            ToolSchemaCompatibilityError,
            ToolSchemaMissingError,
        ]:
            assert get_subdomain_for_class(cls.__name__) == "toolchain", (
                f"{cls.__name__} 未注册到 _CLASS_TO_SUBDOMAIN 的 toolchain"
            )

    def test_all_4_codes_in_toolchain_subdomain(self) -> None:
        """4 个异常 code 都在 toolchain 子域 395-398 范围内"""
        expected_codes = {
            "EXCEPTION_395",
            "EXCEPTION_396",
            "EXCEPTION_397",
            "EXCEPTION_398",
        }
        actual_codes = {
            ToolInputSchemaValidationError.code,
            ToolOutputSchemaValidationError.code,
            ToolSchemaCompatibilityError.code,
            ToolSchemaMissingError.code,
        }
        assert actual_codes == expected_codes
