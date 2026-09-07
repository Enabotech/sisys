"""领域层工具执行异常单元测试（Story 4.1a）

测试 7 个新异常的 11 维度：
- 构造参数 / to_dict / HTTP 映射 / 继承链 / cause 链 / 子域归属 / 编码唯一性
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import (
    DomainError,
    EvidenceValidationFailedError,
    NotFoundError,
    SkillLoadError,
    SkillNotFoundError,
    ToolExecutionFailedError,
    ToolExecutionRetryExhaustedError,
    ToolExecutionTimeoutError,
    ToolResultValidationError,
    ValidationError,
)
from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP


class TestToolExecutionFailedError:
    """ToolExecutionFailedError (EXCEPTION_382) 测试"""

    def test_inherits_business_exception(self) -> None:
        """继承 BusinessException"""
        exc = ToolExecutionFailedError()
        assert isinstance(exc, DomainError)

    def test_code_is_382(self) -> None:
        exc = ToolExecutionFailedError()
        assert exc.code == "EXCEPTION_382"

    def test_constructor_with_context(self) -> None:
        exc = ToolExecutionFailedError(
            execution_id="e-123",
            tool_id="t-1",
            stage="PLANNING",
        )
        assert exc.context["execution_id"] == "e-123"
        assert exc.context["tool_id"] == "t-1"
        assert exc.context["stage"] == "PLANNING"

    def test_constructor_with_cause(self) -> None:
        cause = ValueError("test")
        exc = ToolExecutionFailedError(cause=cause)
        assert exc.cause is cause

    def test_to_dict(self) -> None:
        exc = ToolExecutionFailedError(stage="EXECUTING")
        d = exc.to_dict()
        assert d["code"] == "EXCEPTION_382"
        assert "stage" in d["context"]

    def test_http_map_500(self) -> None:
        exc = ToolExecutionFailedError()
        assert EXCEPTION_HTTP_MAP.get(type(exc)) == 500


class TestToolExecutionRetryExhaustedError:
    """ToolExecutionRetryExhaustedError (EXCEPTION_383) 测试"""

    def test_inherits_business_exception(self) -> None:
        exc = ToolExecutionRetryExhaustedError()
        assert isinstance(exc, DomainError)

    def test_code_is_383(self) -> None:
        exc = ToolExecutionRetryExhaustedError()
        assert exc.code == "EXCEPTION_383"

    def test_constructor_with_retry_count(self) -> None:
        exc = ToolExecutionRetryExhaustedError(retry_count=3)
        assert exc.context["retry_count"] == 3

    def test_to_dict_contains_retry_count(self) -> None:
        exc = ToolExecutionRetryExhaustedError(retry_count=3)
        d = exc.to_dict()
        assert d["context"]["retry_count"] == 3

    def test_http_map_502(self) -> None:
        exc = ToolExecutionRetryExhaustedError()
        assert EXCEPTION_HTTP_MAP.get(type(exc)) == 502


class TestToolExecutionTimeoutError:
    """ToolExecutionTimeoutError (EXCEPTION_385) 测试"""

    def test_inherits_business_exception(self) -> None:
        exc = ToolExecutionTimeoutError()
        assert isinstance(exc, DomainError)

    def test_code_is_385(self) -> None:
        exc = ToolExecutionTimeoutError()
        assert exc.code == "EXCEPTION_385"

    def test_constructor_with_elapsed_sec(self) -> None:
        exc = ToolExecutionTimeoutError(elapsed_sec=125.5)
        assert exc.context["elapsed_sec"] == 125.5

    def test_http_map_504(self) -> None:
        exc = ToolExecutionTimeoutError()
        assert EXCEPTION_HTTP_MAP.get(type(exc)) == 504


class TestEvidenceValidationFailedError:
    """EvidenceValidationFailedError (EXCEPTION_386) 测试"""

    def test_inherits_validation_error(self) -> None:
        exc = EvidenceValidationFailedError()
        assert isinstance(exc, ValidationError)

    def test_code_is_386(self) -> None:
        exc = EvidenceValidationFailedError()
        assert exc.code == "EXCEPTION_386"

    def test_constructor_with_missing_fields(self) -> None:
        exc = EvidenceValidationFailedError(missing_fields=["plan", "code"])
        assert exc.context["missing_fields"] == ["plan", "code"]

    def test_to_dict(self) -> None:
        exc = EvidenceValidationFailedError(missing_fields=["plan"])
        d = exc.to_dict()
        assert d["context"]["missing_fields"] == ["plan"]

    def test_http_map_400(self) -> None:
        exc = EvidenceValidationFailedError()
        assert EXCEPTION_HTTP_MAP.get(type(exc)) == 400


class TestSkillNotFoundError:
    """SkillNotFoundError (EXCEPTION_387) 测试"""

    def test_inherits_not_found_error(self) -> None:
        exc = SkillNotFoundError()
        assert isinstance(exc, NotFoundError)

    def test_code_is_387(self) -> None:
        exc = SkillNotFoundError()
        assert exc.code == "EXCEPTION_387"

    def test_constructor_with_tool_name(self) -> None:
        exc = SkillNotFoundError(tool_name="pestel-analysis")
        assert exc.context["tool_name"] == "pestel-analysis"

    def test_constructor_with_slug(self) -> None:
        exc = SkillNotFoundError(slug="pestel-analysis")
        assert exc.context["slug"] == "pestel-analysis"

    def test_http_map_404(self) -> None:
        exc = SkillNotFoundError()
        assert EXCEPTION_HTTP_MAP.get(type(exc)) == 404


class TestSkillLoadError:
    """SkillLoadError (EXCEPTION_388) 测试"""

    def test_inherits_business_exception(self) -> None:
        exc = SkillLoadError()
        assert isinstance(exc, DomainError)

    def test_code_is_388(self) -> None:
        exc = SkillLoadError()
        assert exc.code == "EXCEPTION_388"

    def test_constructor_with_file_path(self) -> None:
        exc = SkillLoadError(file_path="/skills/foo/SKILL.md")
        assert exc.context["file_path"] == "/skills/foo/SKILL.md"

    def test_constructor_with_cause(self) -> None:
        cause = FileNotFoundError("not found")
        exc = SkillLoadError(cause=cause)
        assert exc.cause is cause

    def test_http_map_500(self) -> None:
        exc = SkillLoadError()
        assert EXCEPTION_HTTP_MAP.get(type(exc)) == 500


class TestToolResultValidationError:
    """ToolResultValidationError (EXCEPTION_389) 测试"""

    def test_inherits_validation_error(self) -> None:
        exc = ToolResultValidationError()
        assert isinstance(exc, ValidationError)

    def test_code_is_389(self) -> None:
        exc = ToolResultValidationError()
        assert exc.code == "EXCEPTION_389"

    def test_constructor_with_reason(self) -> None:
        exc = ToolResultValidationError(reason="output_schema_mismatch")
        assert exc.context["reason"] == "output_schema_mismatch"

    def test_http_map_400(self) -> None:
        exc = ToolResultValidationError()
        assert EXCEPTION_HTTP_MAP.get(type(exc)) == 400


class TestToolExceptionSubdomainRegistration:
    """所有 7 个新异常必须注册到 tool 子域"""

    @pytest.mark.parametrize(
        "exc_cls,expected_code",
        [
            (ToolExecutionFailedError, "EXCEPTION_382"),
            (ToolExecutionRetryExhaustedError, "EXCEPTION_383"),
            (ToolExecutionTimeoutError, "EXCEPTION_385"),
            (EvidenceValidationFailedError, "EXCEPTION_386"),
            (SkillNotFoundError, "EXCEPTION_387"),
            (SkillLoadError, "EXCEPTION_388"),
            (ToolResultValidationError, "EXCEPTION_389"),
        ],
    )
    def test_exception_in_tool_subdomain(
        self,
        exc_cls: type[DomainError],
        expected_code: str,
    ) -> None:
        from src.domain.exceptions._code_ranges import get_subdomain_for_class

        subdomain = get_subdomain_for_class(exc_cls.__name__)
        assert subdomain == "tool"
        assert exc_cls().code == expected_code
