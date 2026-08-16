"""Story 3.6 摘要生成异常单元测试

验证 SummaryGenerationError 和 SummaryPerspectiveNotSupportedError 的构造、序列化、HTTP 映射。
"""

from __future__ import annotations

from src.domain.exceptions import (
    BusinessException,
    SummaryGenerationError,
    SummaryPerspectiveNotSupportedError,
    ValidationError,
)


class TestSummaryGenerationError:
    """SummaryGenerationError 异常验证"""

    def test_exception_code(self) -> None:
        """异常编码为 EXCEPTION_290"""
        exc = SummaryGenerationError(perspective="financial", query_text="测试查询")
        assert exc.code == "EXCEPTION_290"

    def test_exception_message(self) -> None:
        """异常默认消息"""
        exc = SummaryGenerationError(perspective="financial", query_text="测试查询")
        assert exc.message == "摘要生成失败"

    def test_custom_message(self) -> None:
        """自定义消息覆盖默认"""
        exc = SummaryGenerationError(
            perspective="financial",
            query_text="测试查询",
            message="LLM API 调用失败",
        )
        assert exc.message == "LLM API 调用失败"

    def test_perspective_in_context(self) -> None:
        """视角类型在 context 中"""
        exc = SummaryGenerationError(perspective="financial", query_text="测试查询")
        assert exc.context["perspective"] == "financial"

    def test_query_text_in_context(self) -> None:
        """查询文本在 context 中"""
        exc = SummaryGenerationError(perspective="financial", query_text="这是一个很长的查询文本，用于测试截断逻辑" * 10)
        # 截断至 100 字符
        assert len(exc.context["query_text"]) <= 100

    def test_inherits_business_exception(self) -> None:
        """继承 BusinessException"""
        exc = SummaryGenerationError(perspective="financial", query_text="测试查询")
        assert isinstance(exc, BusinessException)

    def test_to_dict(self) -> None:
        """to_dict() 序列化正确"""
        exc = SummaryGenerationError(
            perspective="financial",
            query_text="测试查询",
            message="摘要生成失败",
        )
        data = exc.to_dict()
        assert data["code"] == "EXCEPTION_290"
        assert data["message"] == "摘要生成失败"
        assert data["context"]["perspective"] == "financial"
        assert data["context"]["query_text"] == "测试查询"

    def test_to_dict_with_cause(self) -> None:
        """to_dict() 包含 cause 链"""
        cause = ValueError("原始错误")
        exc = SummaryGenerationError(
            perspective="financial",
            query_text="测试查询",
            cause=cause,
        )
        data = exc.to_dict()
        assert "cause" in data
        assert data["cause"]["type"] == "ValueError"

    def test_cause_chain(self) -> None:
        """cause 链正确传递"""
        cause = ValueError("原始错误")
        exc = SummaryGenerationError(
            perspective="financial",
            query_text="测试查询",
            cause=cause,
        )
        assert exc.cause is cause

    def test_str_representation(self) -> None:
        """字符串表示包含消息"""
        exc = SummaryGenerationError(
            perspective="financial",
            query_text="测试查询",
            message="LLM 调用失败",
        )
        assert "LLM 调用失败" in str(exc)


class TestSummaryPerspectiveNotSupportedError:
    """SummaryPerspectiveNotSupportedError 异常验证"""

    def test_exception_code(self) -> None:
        """异常编码为 EXCEPTION_291"""
        exc = SummaryPerspectiveNotSupportedError(perspective="unsupported")
        assert exc.code == "EXCEPTION_291"

    def test_exception_message(self) -> None:
        """异常默认消息"""
        exc = SummaryPerspectiveNotSupportedError(perspective="unsupported")
        assert exc.message == "不支持的摘要视角"

    def test_perspective_in_context(self) -> None:
        """视角类型在 context 中"""
        exc = SummaryPerspectiveNotSupportedError(perspective="unsupported_视角")
        assert exc.context["perspective"] == "unsupported_视角"

    def test_inherits_validation_error(self) -> None:
        """继承 ValidationError"""
        exc = SummaryPerspectiveNotSupportedError(perspective="unsupported")
        assert isinstance(exc, ValidationError)
        assert isinstance(exc, BusinessException)

    def test_to_dict(self) -> None:
        """to_dict() 序列化正确"""
        exc = SummaryPerspectiveNotSupportedError(
            perspective="invalid_perspective",
            message="不支持的视角类型",
        )
        data = exc.to_dict()
        assert data["code"] == "EXCEPTION_291"
        assert data["message"] == "不支持的视角类型"
        assert data["context"]["perspective"] == "invalid_perspective"


class TestExceptionHTTPMapping:
    """异常 HTTP 状态码映射验证"""

    def test_summary_generation_error_http_500(self) -> None:
        """SummaryGenerationError 映射到 HTTP 500"""
        from fastapi import status

        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        exc = SummaryGenerationError(perspective="financial", query_text="测试")
        mapped_status = None
        for exc_type, http_status in EXCEPTION_HTTP_MAP.items():
            if type(exc) is exc_type:
                mapped_status = http_status
                break
        if mapped_status is None:
            # 回退到 isinstance 匹配
            for exc_type, http_status in EXCEPTION_HTTP_MAP.items():
                if isinstance(exc, exc_type):
                    mapped_status = http_status
                    break
        assert mapped_status == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_perspective_not_supported_http_400(self) -> None:
        """SummaryPerspectiveNotSupportedError 映射到 HTTP 400"""
        from fastapi import status

        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        exc = SummaryPerspectiveNotSupportedError(perspective="invalid")
        mapped_status = None
        for exc_type, http_status in EXCEPTION_HTTP_MAP.items():
            if type(exc) is exc_type:
                mapped_status = http_status
                break
        if mapped_status is None:
            for exc_type, http_status in EXCEPTION_HTTP_MAP.items():
                if isinstance(exc, exc_type):
                    mapped_status = http_status
                    break
        assert mapped_status == status.HTTP_400_BAD_REQUEST


class TestExceptionCodeUniqueness:
    """异常编码唯一性验证"""

    def test_no_code_collision_290(self) -> None:
        """EXCEPTION_290 无碰撞"""

        import src.domain.exceptions as exc_module

        count = 0
        for name in exc_module.__all__:
            cls = getattr(exc_module, name)
            if isinstance(cls, type) and issubclass(cls, Exception):
                code = getattr(cls, "code", None)
                if code == "EXCEPTION_290":
                    count += 1
        assert count == 1, f"EXCEPTION_290 出现 {count} 次，预期 1 次"

    def test_no_code_collision_291(self) -> None:
        """EXCEPTION_291 无碰撞"""

        import src.domain.exceptions as exc_module

        count = 0
        for name in exc_module.__all__:
            cls = getattr(exc_module, name)
            if isinstance(cls, type) and issubclass(cls, Exception):
                code = getattr(cls, "code", None)
                if code == "EXCEPTION_291":
                    count += 1
        assert count == 1, f"EXCEPTION_291 出现 {count} 次，预期 1 次"
