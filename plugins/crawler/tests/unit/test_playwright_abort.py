"""Playwright 资源过滤谓词单元测试

验证 should_abort_request 对不同资源类型的过滤行为
"""

from __future__ import annotations

from unittest.mock import MagicMock

from plugins.crawler.scrapy_engine.middlewares.playwright_abort import should_abort_request


def _mock_request(resource_type: str) -> MagicMock:
    """构造模拟 Playwright Request"""
    request = MagicMock()
    request.resource_type = resource_type
    return request


class TestPlaywrightAbort:
    """Playwright 资源过滤测试"""

    def test_abort_image(self) -> None:
        """图片资源应被中止"""
        assert should_abort_request(_mock_request("image")) is True

    def test_abort_font(self) -> None:
        """字体资源应被中止"""
        assert should_abort_request(_mock_request("font")) is True

    def test_abort_stylesheet(self) -> None:
        """CSS 样式表应被中止"""
        assert should_abort_request(_mock_request("stylesheet")) is True

    def test_abort_media(self) -> None:
        """媒体资源应被中止"""
        assert should_abort_request(_mock_request("media")) is True

    def test_keep_document(self) -> None:
        """HTML 文档不应被中止"""
        assert should_abort_request(_mock_request("document")) is False

    def test_keep_script(self) -> None:
        """JavaScript 脚本不应被中止"""
        assert should_abort_request(_mock_request("script")) is False

    def test_keep_xhr(self) -> None:
        """XHR/Fetch 请求不应被中止"""
        assert should_abort_request(_mock_request("xhr")) is False

    def test_keep_other(self) -> None:
        """其他未知类型不应被中止"""
        assert should_abort_request(_mock_request("websocket")) is False
