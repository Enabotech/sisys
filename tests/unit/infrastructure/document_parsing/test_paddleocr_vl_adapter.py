"""PaddleOCR-VL 适配器单元测试

测试 PaddleOCRVLAdapter 的 HTTP 通信、响应解析、异常处理和降级逻辑。
使用 httpx.MockTransport 模拟 HTTP 请求。
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from typing import Any

import httpx
import pytest

from src.domain.exceptions.ocr_exceptions import OCRConnectionError, OCRProcessingError
from src.infrastructure.document_parsing.paddleocr_vl_adapter import PaddleOCRVLAdapter

# 测试数据
_SAMPLE_RESPONSE = {
    "result": {
        "layoutParsingResults": [
            {
                "pageIndex": 0,
                "prunedResult": {
                    "parsing_res_list": [
                        {
                            "block_bbox": [0.05, 0.05, 0.9, 0.1],
                            "block_label": "title",
                            "block_content": "## 测试报告",
                            "block_id": 0,
                            "confidence": 0.98,
                        },
                        {
                            "block_bbox": [0.05, 0.15, 0.9, 0.5],
                            "block_label": "text",
                            "block_content": "本报告分析了当前市场环境。",
                            "block_id": 1,
                            "confidence": 0.95,
                        },
                    ]
                },
            }
        ]
    }
}

_EMPTY_RESPONSE: dict[str, Any] = {
    "result": {
        "layoutParsingResults": [],
    }
}

_ENGLISH_RESPONSE = {
    "result": {
        "layoutParsingResults": [
            {
                "pageIndex": 0,
                "prunedResult": {
                    "parsing_res_list": [
                        {
                            "block_bbox": [0.05, 0.05, 0.9, 0.1],
                            "block_label": "title",
                            "block_content": "## Annual Report 2026",
                            "block_id": 0,
                            "confidence": 0.97,
                        },
                        {
                            "block_bbox": [0.05, 0.15, 0.9, 0.5],
                            "block_label": "text",
                            "block_content": "This report analyzes the market environment.",
                            "block_id": 1,
                            "confidence": 0.94,
                        },
                    ]
                },
            }
        ]
    }
}


def _create_temp_file(content: str = "test content", suffix: str = ".pdf") -> str:
    """创建临时测试文件"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(content.encode())
    tmp.close()
    return tmp.name


@pytest.fixture
def temp_pdf() -> Generator[str, None, None]:
    """创建临时 PDF 测试文件"""
    path = _create_temp_file(content="fake pdf content", suffix=".pdf")
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def temp_image() -> Generator[str, None, None]:
    """创建临时图像测试文件"""
    path = _create_temp_file(content="fake image content", suffix=".png")
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestPaddleOCRVLAdapter:
    """PaddleOCRVLAdapter 核心功能测试"""

    @pytest.mark.asyncio
    async def test_successful_ocr(self, temp_pdf: str) -> None:
        """测试成功场景：Mock 返回标准响应 → 验证 OCRPageResult 输出"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_SAMPLE_RESPONSE)

        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        try:
            results = await adapter.recognize(temp_pdf)
            assert len(results) == 1
            result = results[0]
            assert result.page_number == 1
            assert len(result.elements) == 2
            assert result.elements[0].content == "测试报告"
            assert result.elements[0].confidence == 0.98
            assert result.elements[0].metadata["ocr_block_label"] == "title"
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_chinese_recognition(self, temp_pdf: str) -> None:
        """测试中文识别结果正确映射"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_SAMPLE_RESPONSE)

        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        try:
            results = await adapter.recognize(temp_pdf)
            assert "测试报告" in results[0].elements[0].content
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_english_recognition(self, temp_pdf: str) -> None:
        """测试英文识别结果正确映射"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_ENGLISH_RESPONSE)

        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        try:
            results = await adapter.recognize(temp_pdf)
            assert "Annual Report 2026" in results[0].elements[0].content
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_empty_page(self, temp_pdf: str) -> None:
        """测试空页面（无文字块）→ 返回空 elements 列表"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_EMPTY_RESPONSE)

        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        try:
            results = await adapter.recognize(temp_pdf)
            assert len(results) == 1
            assert results[0].elements == []
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_connect_timeout(self, temp_pdf: str) -> None:
        """测试连接超时 → 抛出 OCRConnectionError"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        try:
            # Mock _wait_retry 避免真实指数退避睡眠（~3.5s）
            from unittest.mock import AsyncMock, patch

            with patch.object(adapter, "_wait_retry", AsyncMock()):
                with pytest.raises(OCRConnectionError) as exc_info:
                    await adapter.recognize(temp_pdf)
                assert "EXCEPTION_320" in str(exc_info.value.code)
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_http_500(self, temp_pdf: str) -> None:
        """测试 HTTP 5xx → 抛出 OCRProcessingError"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        try:
            with pytest.raises(OCRProcessingError) as exc_info:
                await adapter.recognize(temp_pdf)
            assert exc_info.value.context.get("status_code") == 500
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_http_400(self, temp_pdf: str) -> None:
        """测试 HTTP 4xx → 抛出 OCRProcessingError"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, text="Bad Request")

        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        try:
            with pytest.raises(OCRProcessingError) as exc_info:
                await adapter.recognize(temp_pdf)
            assert exc_info.value.context.get("status_code") == 400
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_json_parse_error(self, temp_pdf: str) -> None:
        """测试响应 JSON 解析失败 → 抛出 OCRProcessingError"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not-json")

        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        try:
            with pytest.raises(OCRProcessingError):
                await adapter.recognize(temp_pdf)
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_image_file_recognition(self, temp_image: str) -> None:
        """测试图像文件识别"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_SAMPLE_RESPONSE)

        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        try:
            results = await adapter.recognize(temp_image)
            assert len(results) == 1
            assert len(results[0].elements) == 2
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_confidence_default_when_missing(self, temp_pdf: str) -> None:
        """测试置信度缺失时默认使用 0.5"""
        response_no_conf = {
            "result": {
                "layoutParsingResults": [
                    {
                        "pageIndex": 0,
                        "prunedResult": {
                            "parsing_res_list": [
                                {
                                    "block_bbox": [0.05, 0.05, 0.9, 0.1],
                                    "block_label": "text",
                                    "block_content": "test",
                                    "block_id": 0,
                                },
                            ]
                        },
                    }
                ]
            }
        }

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=response_no_conf)

        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        try:
            results = await adapter.recognize(temp_pdf)
            assert results[0].elements[0].confidence == 0.5
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_confidence_clamped(self, temp_pdf: str) -> None:
        """测试置信度值域范围 [0.0, 1.0]"""
        response_clamped = {
            "result": {
                "layoutParsingResults": [
                    {
                        "pageIndex": 0,
                        "prunedResult": {
                            "parsing_res_list": [
                                {
                                    "block_bbox": [0.05, 0.05, 0.9, 0.1],
                                    "block_label": "text",
                                    "block_content": "test",
                                    "block_id": 0,
                                    "confidence": 1.5,  # 超出范围
                                },
                            ]
                        },
                    }
                ]
            }
        }

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=response_clamped)

        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        try:
            results = await adapter.recognize(temp_pdf)
            assert results[0].elements[0].confidence == 1.0
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_strip_markdown(self) -> None:
        """测试 Markdown 转纯文本"""
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        try:
            result = adapter._strip_markdown("## 标题\n\n**粗体**文本\n\n- 列表项")
            assert "标题" in result
            assert "粗体" in result
            assert "列表项" in result
            assert "##" not in result
            assert "**" not in result
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_retry_on_connect_error(self, temp_pdf: str) -> None:
        """测试连接错误重试（指数退避）"""
        call_count = 0

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection refused")
            return httpx.Response(200, json=_SAMPLE_RESPONSE)

        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        try:
            # Mock _wait_retry 避免真实指数退避睡眠（~4s）
            from unittest.mock import AsyncMock, patch

            with patch.object(adapter, "_wait_retry", AsyncMock()) as mock_wait:
                results = await adapter.recognize(temp_pdf)
                assert len(results) == 1
                assert call_count == 3  # 初始 + 2 次重试
                # 验证 _wait_retry 被调用了 2 次（attempt 0 和 attempt 1）
                assert mock_wait.call_count == 2
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_retry_eventually_fails(self, temp_pdf: str) -> None:
        """测试重试耗尽后仍失败"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        try:
            # Mock _wait_retry 避免真实指数退避睡眠（~3.5s）
            from unittest.mock import AsyncMock, patch

            with patch.object(adapter, "_wait_retry", AsyncMock()) as mock_wait:
                with pytest.raises(OCRConnectionError):
                    await adapter.recognize(temp_pdf)
                # 验证重试耗尽：初始 + MAX_RETRIES(2) 次重试后仍失败
                # _wait_retry 被调用了 MAX_RETRIES 次
                assert mock_wait.call_count == 2
        finally:
            await adapter.close()
