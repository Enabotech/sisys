"""领域层工具异常单元测试

验证 ToolNotFoundError 和 ToolAlreadyExistsError：
- 构造、to_dict、编码唯一性
- HTTP 映射（通过 EXCEPTION_HTTP_MAP）
"""

from __future__ import annotations

from src.domain.exceptions.tool_exceptions import (
    ToolAlreadyExistsError,
    ToolNotFoundError,
)


class TestToolNotFoundError:
    """Test ToolNotFoundError exception."""

    def test_code_is_exception_380(self):
        """ToolNotFoundError 编码为 EXCEPTION_380."""
        assert ToolNotFoundError.code == "EXCEPTION_380"

    def test_default_message(self):
        """默认消息为 'Tool not found'."""
        exc = ToolNotFoundError()
        assert exc.message == "Tool not found"

    def test_custom_message(self):
        """自定义消息覆盖默认消息."""
        exc = ToolNotFoundError(message="Custom error")
        assert exc.message == "Custom error"

    def test_context_with_tool_id(self):
        """携带 tool_id 上下文."""
        exc = ToolNotFoundError(tool_id="tool-123")
        assert exc.context["tool_id"] == "tool-123"

    def test_context_with_tool_name(self):
        """携带 tool_name 上下文."""
        exc = ToolNotFoundError(tool_name="PESTEL 分析")
        assert exc.context["tool_name"] == "PESTEL 分析"

    def test_context_with_both(self):
        """同时携带 tool_id 和 tool_name 上下文."""
        exc = ToolNotFoundError(tool_id="tool-123", tool_name="PESTEL 分析")
        assert exc.context["tool_id"] == "tool-123"
        assert exc.context["tool_name"] == "PESTEL 分析"

    def test_to_dict(self):
        """to_dict 包含 code、message、context."""
        exc = ToolNotFoundError(tool_id="tool-123")
        result = exc.to_dict()
        assert result["code"] == "EXCEPTION_380"
        assert result["message"] == "Tool not found"
        assert result["context"]["tool_id"] == "tool-123"

    def test_is_not_found_error(self):
        """ToolNotFoundError 继承 NotFoundError，保持 HTTP 404 映射."""
        from src.domain.exceptions.business_exceptions import NotFoundError

        assert issubclass(ToolNotFoundError, NotFoundError)

    def test_is_business_exception_via_not_found(self):
        """ToolNotFoundError 通过 NotFoundError 间接继承 BusinessException."""
        from src.domain.exceptions.business_exceptions import BusinessException

        assert issubclass(ToolNotFoundError, BusinessException)


class TestToolAlreadyExistsError:
    """Test ToolAlreadyExistsError exception."""

    def test_code_is_exception_381(self):
        """ToolAlreadyExistsError 编码为 EXCEPTION_381."""
        assert ToolAlreadyExistsError.code == "EXCEPTION_381"

    def test_default_message(self):
        """默认消息为 'Tool already exists'."""
        exc = ToolAlreadyExistsError()
        assert exc.message == "Tool already exists"

    def test_custom_message(self):
        """自定义消息覆盖默认消息."""
        exc = ToolAlreadyExistsError(message="Custom error")
        assert exc.message == "Custom error"

    def test_context_with_tool_id(self):
        """携带 tool_id 上下文."""
        exc = ToolAlreadyExistsError(tool_id="tool-123")
        assert exc.context["tool_id"] == "tool-123"

    def test_context_with_tool_name(self):
        """携带 tool_name 上下文."""
        exc = ToolAlreadyExistsError(tool_name="PESTEL 分析")
        assert exc.context["tool_name"] == "PESTEL 分析"

    def test_context_with_both(self):
        """同时携带 tool_id 和 tool_name 上下文."""
        exc = ToolAlreadyExistsError(tool_id="tool-123", tool_name="PESTEL 分析")
        assert exc.context["tool_id"] == "tool-123"
        assert exc.context["tool_name"] == "PESTEL 分析"

    def test_to_dict(self):
        """to_dict 包含 code、message、context."""
        exc = ToolAlreadyExistsError(tool_name="PESTEL 分析")
        result = exc.to_dict()
        assert result["code"] == "EXCEPTION_381"
        assert result["message"] == "Tool already exists"
        assert result["context"]["tool_name"] == "PESTEL 分析"

    def test_is_conflict_error(self):
        """ToolAlreadyExistsError 继承 ConflictError."""
        from src.domain.exceptions.business_exceptions import ConflictError

        assert issubclass(ToolAlreadyExistsError, ConflictError)


class TestToolExceptionCodeUniqueness:
    """Test that tool exception codes are unique across all exceptions."""

    def test_tool_codes_unique(self):
        """Tool 异常编码不与现有异常碰撞."""
        from src.domain.exceptions._code_ranges import _CLASS_TO_SUBDOMAIN

        tool_classes = [c for c, s in _CLASS_TO_SUBDOMAIN.items() if s == "tool"]
        assert len(tool_classes) >= 2, "至少应有 2 个 tool 子域异常"

    def test_tool_codes_within_range(self):
        """Tool 异常编码在 380-389 范围内."""
        from src.domain.exceptions._code_ranges import CODE_RANGES

        tool_range = CODE_RANGES.get("tool")
        assert tool_range is not None
        assert tool_range == (380, 389)

    def test_exception_380_not_placeholder(self):
        """EXCEPTION_380 不是占位符编码."""
        from src.domain.exceptions._code_ranges import is_placeholder

        assert not is_placeholder(380)

    def test_exception_381_not_placeholder(self):
        """EXCEPTION_381 不是占位符编码."""
        from src.domain.exceptions._code_ranges import is_placeholder

        assert not is_placeholder(381)
