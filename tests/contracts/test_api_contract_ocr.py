"""PaddleOCR-VL API 契约测试

基于 mock HTTP 通信验证 OCR API 的请求/响应契约，无需 GPU / Docker 即可在 CI 中运行。
覆盖 PaddleOCRVLAdapter 与 PaddleOCR-VL 服务之间的 API 契约：

- POST /health 健康检查
- POST /layout-parsing 主 OCR 识别
- 请求 payload 结构（base64 file / fileType / formatBlockContent）
- 响应结构（layoutParsingResults / prunedResult / parsing_res_list）
- 异常响应格式（非 200 状态码 / 超时 / 连接错误）

运行: poetry run pytest tests/contracts/test_api_contract_ocr.py -v
"""

from __future__ import annotations

import os
import tempfile
from typing import Any

import httpx
import pytest

from src.domain.exceptions.ocr_exceptions import OCRConnectionError, OCRProcessingError
from src.infrastructure.document_parsing.paddleocr_vl_adapter import PaddleOCRVLAdapter

# ── 契约响应样本数据 ──────────────────────────────────────────────────

_HEALTH_OK_RESPONSE = {"errorCode": 0, "message": "ok"}

_OCR_SUCCESS_RESPONSE: dict[str, Any] = {
    "result": {
        "layoutParsingResults": [
            {
                "pageIndex": 0,
                "markdown": {
                    "text": "## 测试报告\n\n本报告分析了市场环境。\n\n| 指标 | 数值 |\n| --- | --- |\n| 营收 | 100 万 |\n",
                    "images": {},
                },
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

_OCR_EMPTY_RESPONSE: dict[str, Any] = {"result": {"layoutParsingResults": []}}

_OCR_ERROR_RESPONSE: dict[str, Any] = {"errorCode": 500, "message": "Internal server error"}


def _create_temp_file(content: str = "fake pdf content", suffix: str = ".pdf") -> str:
    """创建临时测试文件"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(content.encode())
    tmp.close()
    return tmp.name


def _cleanup(path: str) -> None:
    if path and os.path.exists(path):
        os.unlink(path)


# ── 契约测试 ──────────────────────────────────────────────────────────


class TestPaddleOCRVLAPIContract:
    """PaddleOCR-VL API 请求/响应契约测试"""

    # ── 请求 payload 契约 ──

    @pytest.mark.asyncio
    async def test_request_payload_contains_base64_file(self) -> None:
        """验证请求 payload 包含 base64 编码的文件内容"""
        captured: dict[str, Any] = {}

        async def capture_handler(request: httpx.Request) -> httpx.Response:
            import json

            body = json.loads(request.read())
            captured.update(body)
            return httpx.Response(200, json=_OCR_EMPTY_RESPONSE)

        pdf_path = _create_temp_file()
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(capture_handler))
        try:
            await adapter.recognize(pdf_path)
            # 验证请求 payload 包含必要字段
            assert "file" in captured, "请求 payload 必须包含 file（base64 编码）"
            assert isinstance(captured["file"], str), "file 必须是 base64 字符串"
            assert len(captured["file"]) > 0, "file 不能为空"
            assert "fileType" in captured, "请求 payload 必须包含 fileType"
            assert captured["fileType"] in (0, 1), "fileType 必须是 0（PDF）或 1（image）"
            assert captured.get("formatBlockContent") is True, "formatBlockContent 必须为 True"
        finally:
            await adapter.close()
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_request_payload_pdf_file_type_is_0(self) -> None:
        """验证 PDF 文件的 fileType 为 0"""
        captured: dict[str, Any] = {}

        async def capture_handler(request: httpx.Request) -> httpx.Response:
            import json

            body = json.loads(request.read())
            captured.update(body)
            return httpx.Response(200, json=_OCR_EMPTY_RESPONSE)

        pdf_path = _create_temp_file(suffix=".pdf")
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(capture_handler))
        try:
            await adapter.recognize(pdf_path)
            assert captured.get("fileType") == 0, "PDF 文件 fileType 应为 0"
        finally:
            await adapter.close()
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_request_payload_image_file_type_is_1(self) -> None:
        """验证图像文件的 fileType 为 1"""
        captured: dict[str, Any] = {}

        async def capture_handler(request: httpx.Request) -> httpx.Response:
            import json

            body = json.loads(request.read())
            captured.update(body)
            return httpx.Response(200, json=_OCR_EMPTY_RESPONSE)

        img_path = _create_temp_file(suffix=".png")
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(capture_handler))
        try:
            await adapter.recognize(img_path)
            assert captured.get("fileType") == 1, "图像文件 fileType 应为 1"
        finally:
            await adapter.close()
            _cleanup(img_path)

    @pytest.mark.asyncio
    async def test_request_url_is_layout_parsing(self) -> None:
        """验证请求 URL 为 /layout-parsing"""
        captured_url: str | None = None

        async def capture_handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_url
            captured_url = str(request.url)
            return httpx.Response(200, json=_OCR_EMPTY_RESPONSE)

        pdf_path = _create_temp_file()
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(capture_handler))
        try:
            await adapter.recognize(pdf_path)
            assert captured_url is not None
            assert captured_url.endswith("/layout-parsing"), f"请求 URL 应为 /layout-parsing，实际: {captured_url}"
        finally:
            await adapter.close()
            _cleanup(pdf_path)

    # ── 响应结构契约 ──

    @pytest.mark.asyncio
    async def test_response_contains_required_fields(self) -> None:
        """验证成功响应包含 result → layoutParsingResults → prunedResult → parsing_res_list"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_OCR_SUCCESS_RESPONSE)

        pdf_path = _create_temp_file()
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        try:
            results = await adapter.recognize(pdf_path)
            assert len(results) == 1, "应返回 1 页结果"
            result = results[0]
            assert result.page_number == 1, "页码应为 1 (1-indexed)"
            assert len(result.elements) == 2, "应解析 2 个元素"
            # 验证元素内容映射正确
            assert result.elements[0].content == "测试报告"
            assert result.elements[0].confidence == 0.98
            assert result.elements[1].content == "本报告分析了当前市场环境。"
            assert result.elements[1].confidence == 0.95
            # 验证 markdown 字段
            assert result.markdown_text is not None
            assert "测试报告" in result.markdown_text
            # 验证 raw_response 保留
            assert result.raw_response is not None
        finally:
            await adapter.close()
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_response_empty_layout_results(self) -> None:
        """验证空结果响应（layoutParsingResults=[]）返回空 elements"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_OCR_EMPTY_RESPONSE)

        pdf_path = _create_temp_file()
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        try:
            results = await adapter.recognize(pdf_path)
            assert len(results) == 1
            assert len(results[0].elements) == 0, "空结果应返回空 elements 列表"
        finally:
            await adapter.close()
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_response_page_index_1_indexed(self) -> None:
        """验证 pageIndex 0 → page_number 1（1-indexed 转换）"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_OCR_SUCCESS_RESPONSE)

        pdf_path = _create_temp_file()
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        try:
            results = await adapter.recognize(pdf_path)
            assert results[0].page_number == 1, "pageIndex 0 应映射为 page_number 1"
        finally:
            await adapter.close()
            _cleanup(pdf_path)

    # ── 异常响应契约 ──

    @pytest.mark.asyncio
    async def test_http_500_raises_processing_error(self) -> None:
        """验证 HTTP 500 抛出 OCRProcessingError"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json=_OCR_ERROR_RESPONSE)

        pdf_path = _create_temp_file()
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        try:
            with pytest.raises(OCRProcessingError) as exc_info:
                await adapter.recognize(pdf_path)
            assert "500" in str(exc_info.value), "错误信息应包含状态码"
        finally:
            await adapter.close()
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_connect_error_raises_connection_error(self) -> None:
        """验证连接错误抛出 OCRConnectionError"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        pdf_path = _create_temp_file()
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        try:
            with pytest.raises(OCRConnectionError) as exc_info:
                await adapter.recognize(pdf_path)
            assert "连接" in str(exc_info.value) or "不可达" in str(exc_info.value)
        finally:
            await adapter.close()
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_timeout_raises_connection_error(self) -> None:
        """验证超时抛出 OCRConnectionError"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("Request timed out")

        pdf_path = _create_temp_file()
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        try:
            with pytest.raises(OCRConnectionError) as exc_info:
                await adapter.recognize(pdf_path)
            assert "超时" in str(exc_info.value) or "timeout" in str(exc_info.value).lower()
        finally:
            await adapter.close()
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_http_400_not_retried(self) -> None:
        """验证 HTTP 400 不重试（客户端错误，非可恢复错误）"""
        call_count = 0

        async def fail_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(400, json={"error": "Bad request"})

        pdf_path = _create_temp_file()
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(fail_handler))
        try:
            with pytest.raises(OCRProcessingError):
                await adapter.recognize(pdf_path)
            assert call_count == 1, "400 不应重试"
        finally:
            await adapter.close()
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_http_500_not_retried(self) -> None:
        """验证 HTTP 500 不重试（响应级错误立即抛出，仅连接/超时错误重试）"""
        call_count = 0

        async def fail_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(500, json=_OCR_ERROR_RESPONSE)

        pdf_path = _create_temp_file()
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(fail_handler))
        try:
            with pytest.raises(OCRProcessingError):
                await adapter.recognize(pdf_path)
            assert call_count == 1, "500 不应重试（仅连接/超时错误重试）"
        finally:
            await adapter.close()
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_response_missing_layout_parsing_results(self) -> None:
        """验证缺失 layoutParsingResults 的响应不抛出异常"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"result": {}})

        pdf_path = _create_temp_file()
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        try:
            results = await adapter.recognize(pdf_path)
            assert len(results) == 1
            assert len(results[0].elements) == 0, "缺失 layoutParsingResults 应返回空 elements"
        finally:
            await adapter.close()
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_response_missing_pruned_result(self) -> None:
        """验证缺失 prunedResult 的响应不抛出异常"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"result": {"layoutParsingResults": [{"pageIndex": 0, "markdown": {"text": "", "images": {}}}]}}
            )

        pdf_path = _create_temp_file()
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        try:
            results = await adapter.recognize(pdf_path)
            assert len(results) == 1
            assert len(results[0].elements) == 0
        finally:
            await adapter.close()
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_confidence_sanitization(self) -> None:
        """验证置信度 sanitization（非数值/越界 → 回退 0.5）"""

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "result": {
                        "layoutParsingResults": [
                            {
                                "pageIndex": 0,
                                "prunedResult": {
                                    "parsing_res_list": [
                                        {"block_content": "text", "confidence": "invalid"},
                                        {"block_content": "text", "confidence": 1.5},
                                        {"block_content": "text", "confidence": -0.5},
                                        {"block_content": "text"},  # 无 confidence 字段
                                    ]
                                },
                            }
                        ]
                    }
                },
            )

        pdf_path = _create_temp_file()
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        try:
            results = await adapter.recognize(pdf_path)
            for elem in results[0].elements:
                assert 0.0 <= elem.confidence <= 1.0, f"confidence={elem.confidence} 超出 [0.0, 1.0]"
                # 非法值应回退到 0.5
                if elem.confidence == 0.5:
                    break
            else:
                pytest.fail("未找到回退到 0.5 的置信度")
        finally:
            await adapter.close()
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_retry_on_connect_error(self) -> None:
        """验证连接错误重试 (指数退避)"""
        call_count = 0

        async def fail_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection refused")
            return httpx.Response(200, json=_OCR_EMPTY_RESPONSE)

        pdf_path = _create_temp_file()
        adapter = PaddleOCRVLAdapter(base_url="http://test:8080", timeout=30.0)
        adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(fail_handler))
        try:
            # 第 3 次成功，不应抛出异常
            await adapter.recognize(pdf_path)
            assert call_count == 3, f"连接错误应重试 2 次后成功，实际调用 {call_count} 次"
        finally:
            await adapter.close()
            _cleanup(pdf_path)


__all__: list = []
