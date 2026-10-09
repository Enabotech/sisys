"""Story 4.7: EXCEPTION_399 ValidationFeedbackRetryExhaustedError 单元测试.

覆盖构造/context 四字段/继承链（BusinessException——断言继承关系非父类码号，
R1-14 教训：103 是 StorageError 勿混标）/子域映射 toolchain/编码唯一性。

TDD 红→绿：本文件先于 src/domain/exceptions/validation_feedback_exceptions.py
与五处登记实现（Subtask 2.4）。
"""

from __future__ import annotations

from src.domain.exceptions import (
    BusinessException,
    ValidationFeedbackRetryExhaustedError,
)
from src.domain.exceptions._code_ranges import get_subdomain_for_class


class TestValidationFeedbackRetryExhaustedError:
    """399 异常契约（4.1b/4.3 两度预留编码的兑现）."""

    def test_code_is_399(self) -> None:
        """编码占用既定预留码位 EXCEPTION_399（toolchain 子域最后一个码位）."""
        assert ValidationFeedbackRetryExhaustedError.code == "EXCEPTION_399"

    def test_inherits_business_exception(self) -> None:
        """继承 BusinessException（EXCEPTION_2XX 业务规则基类——非 103 StorageError）."""
        assert issubclass(ValidationFeedbackRetryExhaustedError, BusinessException)

    def test_constructor_context_fields(self) -> None:
        """构造器经 context 暴露四字段：execution_id/tool_id/enhanced_retry_count/error_signature."""
        exc = ValidationFeedbackRetryExhaustedError(
            execution_id="exec-1",
            tool_id="tool-1",
            enhanced_retry_count=3,
            error_signature="d" * 64,
        )
        assert exc.context["execution_id"] == "exec-1"
        assert exc.context["tool_id"] == "tool-1"
        assert exc.context["enhanced_retry_count"] == 3
        assert exc.context["error_signature"] == "d" * 64

    def test_subdomain_is_toolchain(self) -> None:
        """子域映射注册为 toolchain（399 物理归属，语义为反馈闭环——4.2/4.3 惯例）."""
        assert get_subdomain_for_class("ValidationFeedbackRetryExhaustedError") == "toolchain"

    def test_message_readable(self) -> None:
        """默认消息面向调用方可理解（不泄露内部实现细节）."""
        exc = ValidationFeedbackRetryExhaustedError(
            execution_id="e", tool_id="t", enhanced_retry_count=3, error_signature="s" * 64
        )
        assert "不可行" in exc.message or "exhausted" in exc.message.lower()

    def test_cause_transparent(self) -> None:
        """cause 透传（内部耗尽信号链路保留）。"""
        trigger = RuntimeError("last failure")
        exc = ValidationFeedbackRetryExhaustedError(
            execution_id="e", tool_id="t", enhanced_retry_count=3, error_signature="s" * 64, cause=trigger
        )
        assert exc.cause is trigger

    def test_semantic_distinction_from_383(self) -> None:
        """383/399 语义区分：383=基础重试（stage 级 RetryPolicy）耗尽仍可入增强闭环；
        399=增强重试（反馈闭环级）耗尽的终态不可行信号——docstring 必须显式写明（防同义混淆）."""
        from src.domain.exceptions import ToolExecutionRetryExhaustedError

        doc = ValidationFeedbackRetryExhaustedError.__doc__ or ""
        assert "增强" in doc
        assert ToolExecutionRetryExhaustedError.code == "EXCEPTION_383"
        assert ValidationFeedbackRetryExhaustedError.code == "EXCEPTION_399"
        assert ToolExecutionRetryExhaustedError is not ValidationFeedbackRetryExhaustedError


class TestExceptionRegistration:
    """五处登记完整性."""

    def test_exported_from_package(self) -> None:
        """exceptions/__init__.py 导出 + __all__ 登记."""
        from src.domain.exceptions import __all__ as exceptions_all

        assert "ValidationFeedbackRetryExhaustedError" in exceptions_all

    def test_http_map_registered_422(self) -> None:
        """EXCEPTION_HTTP_MAP 精确注册 399→422（与 396 出参校验失败语义对齐——
        「语义上不可处理」而非 502「可重试下游故障」）."""
        from fastapi import status

        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP.get(ValidationFeedbackRetryExhaustedError) == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_code_uniqueness_no_collision(self) -> None:
        """编码唯一（399 仅本类占用）."""

        # 遍历全部注册异常类，确认 399 仅 ValidationFeedbackRetryExhaustedError 使用
        import inspect

        from src.domain import exceptions as exc_pkg

        same_code = [
            name for name, obj in inspect.getmembers(exc_pkg, inspect.isclass) if getattr(obj, "code", None) == "EXCEPTION_399"
        ]
        assert same_code == ["ValidationFeedbackRetryExhaustedError"]
