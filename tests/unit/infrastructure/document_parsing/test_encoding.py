"""文档解析编码检测工具单元测试

验证 detect_and_decode 函数的编码自动检测行为：
UTF-8 → GBK → GB18030 逐级回退策略。
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import ValidationError
from src.infrastructure.document_parsing._encoding import detect_and_decode


class TestDetectAndDecode:
    """编码自动检测测试"""

    def test_utf8_content_detected(self) -> None:
        """UTF-8 编码内容应正确识别并解码"""
        text = "你好世界"
        raw = text.encode("utf-8")
        result_text, encoding = detect_and_decode(raw)
        assert result_text == text
        assert encoding == "utf-8"

    def test_gbk_content_detected(self) -> None:
        """GBK 编码内容应正确识别（UTF-8 失败后回退到 GBK）"""
        text = "中文测试内容"
        raw = text.encode("gbk")
        result_text, encoding = detect_and_decode(raw)
        assert result_text == text
        assert encoding == "gbk"

    def test_gb18030_fallback(self) -> None:
        """GB18030 兜底解码成功"""
        text = "测试"
        raw = text.encode("gb18030")
        result_text, encoding = detect_and_decode(raw)
        assert result_text == text
        assert encoding in ("gbk", "gb18030")

    def test_invalid_binary_raises_validation_error(self) -> None:
        """无法解码的二进制内容应抛出 ValidationError"""
        # b'\x80\x81\x82\x83\x84\x85' 在 UTF-8/GBK/GB18030 三种编码下均解码失败
        invalid_bytes = b"\x80\x81\x82\x83\x84\x85"
        with pytest.raises(ValidationError):
            detect_and_decode(invalid_bytes)

    def test_empty_bytes_returns_empty_string(self) -> None:
        """空字节应返回空字符串和 utf-8 编码名"""
        text, encoding = detect_and_decode(b"")
        assert text == ""
        assert encoding == "utf-8"

    def test_return_type_is_tuple_str_str(self) -> None:
        """返回值应为 (str, str) 元组"""
        result = detect_and_decode(b"hello")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)

    def test_ascii_content_detected_as_utf8(self) -> None:
        """纯 ASCII 内容应识别为 UTF-8"""
        text, encoding = detect_and_decode(b"Hello, World!")
        assert text == "Hello, World!"
        assert encoding == "utf-8"
