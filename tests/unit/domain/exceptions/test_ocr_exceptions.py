"""OCR 子域异常测试

测试 OCR 异常类的构造、属性、to_dict() 序列化、cause 链和 HTTP 映射。
"""

from __future__ import annotations

from src.domain.exceptions.ocr_exceptions import OCRConnectionError, OCRProcessingError


class TestOCRConnectionError:
    """OCRConnectionError 异常测试"""

    def test_constructor_default(self) -> None:
        """测试默认构造"""
        exc = OCRConnectionError()
        assert exc.code == "EXCEPTION_320"
        assert exc.message == "OCR 连接失败"
        assert exc.cause is None

    def test_constructor_with_message(self) -> None:
        """测试带消息构造"""
        exc = OCRConnectionError(message="PaddleOCR-VL 服务不可达")
        assert exc.message == "PaddleOCR-VL 服务不可达"

    def test_constructor_with_cause(self) -> None:
        """测试带 cause 构造"""
        cause = RuntimeError("connection refused")
        exc = OCRConnectionError(cause=cause)
        assert exc.cause is cause
        assert exc.message == "OCR 连接失败"

    def test_constructor_with_service_url(self) -> None:
        """测试带 service_url 构造（host 信息存入 context）"""
        exc = OCRConnectionError(service_url="http://paddleocr-vl-api:8080")
        assert exc.context.get("service_host") == "http://paddleocr-vl-api"

    def test_to_dict(self) -> None:
        """测试 to_dict() 序列化"""
        exc = OCRConnectionError(message="连接失败")
        result = exc.to_dict()
        assert result["code"] == "EXCEPTION_320"
        assert result["message"] == "连接失败"

    def test_to_dict_with_cause(self) -> None:
        """测试带 cause 的 to_dict() 序列化"""
        cause = RuntimeError("timeout")
        exc = OCRConnectionError(message="连接失败", cause=cause)
        result = exc.to_dict()
        assert result["cause"]["type"] == "RuntimeError"
        assert result["cause"]["message"] == "timeout"


class TestOCRProcessingError:
    """OCRProcessingError 异常测试"""

    def test_constructor_default(self) -> None:
        """测试默认构造"""
        exc = OCRProcessingError()
        assert exc.code == "EXCEPTION_321"
        assert exc.message == "OCR 处理失败"
        assert exc.cause is None

    def test_constructor_with_message(self) -> None:
        """测试带消息构造"""
        exc = OCRProcessingError(message="解析失败")
        assert exc.message == "解析失败"

    def test_constructor_with_status_code(self) -> None:
        """测试带 status_code 构造"""
        exc = OCRProcessingError(service_url="http://paddleocr-vl-api:8080", status_code=500)
        assert exc.context.get("status_code") == 500
        assert exc.context.get("service_host") == "http://paddleocr-vl-api"

    def test_constructor_with_response_body(self) -> None:
        """测试带 response_body 构造（截断至 200 字符）"""
        exc = OCRProcessingError(response_body="a" * 500)
        assert len(exc.context.get("response_summary", "")) == 200

    def test_to_dict(self) -> None:
        """测试 to_dict() 序列化"""
        exc = OCRProcessingError(message="处理失败")
        result = exc.to_dict()
        assert result["code"] == "EXCEPTION_321"
        assert result["message"] == "处理失败"

    def test_to_dict_with_cause(self) -> None:
        """测试带 cause 的 to_dict() 序列化"""
        cause = ValueError("bad response")
        exc = OCRProcessingError(message="处理失败", cause=cause)
        result = exc.to_dict()
        assert result["cause"]["type"] == "ValueError"
        assert result["cause"]["message"] == "bad response"


class TestOCRExceptionHTTPMapping:
    """OCR 异常 HTTP 映射测试"""

    def test_ocr_connection_error_http_status(self) -> None:
        """验证 OCRConnectionError 映射到 504"""
        from fastapi import status
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP.get(OCRConnectionError) == status.HTTP_504_GATEWAY_TIMEOUT

    def test_ocr_processing_error_http_status(self) -> None:
        """验证 OCRProcessingError 映射到 502"""
        from fastapi import status
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP.get(OCRProcessingError) == status.HTTP_502_BAD_GATEWAY