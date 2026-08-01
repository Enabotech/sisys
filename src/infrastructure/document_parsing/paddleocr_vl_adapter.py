"""PaddleOCR-VL 适配器

通过 HTTP 调用 PaddleOCR-VL 服务化 API 实现 OCRPort 协议。
使用 httpx.AsyncClient 进行异步 HTTP 通信，支持 PDF 按页拆分、并发控制和异常降级。

架构约束：
- 领域层零外部依赖，此处为基础设施层实现
- 通过 httpx.AsyncClient 实现 async def recognize()（项目 56 端口 213 async 方法惯例）
- 临时文件安全：tempfile.NamedTemporaryFile + os.fchmod(0o600) + try/finally os.unlink()
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import secrets
import tempfile
from typing import Any

import httpx

from src.domain.exceptions.ocr_exceptions import OCRConnectionError, OCRProcessingError
from src.domain.value_objects.ocr_result import OCRPageResult
from src.domain.value_objects.parsed_document import ParsedElement

logger = logging.getLogger(__name__)

# PaddleOCR-VL API 默认配置
DEFAULT_BASE_URL = "http://localhost:8080"
DEFAULT_TIMEOUT = 300.0
MAX_RETRIES = 2
MAX_CONCURRENCY = 5


class PaddleOCRVLAdapter:
    """PaddleOCR-VL 适配器

    通过 HTTP 调用 PaddleOCR-VL 服务化 API，实现 OCRPort 协议。
    支持 PDF 和图像格式，PDF 按页拆分并发请求。

    Attributes:
        base_url: PaddleOCR-VL API 基础 URL
        timeout: HTTP 请求超时时间（秒）
        _client: httpx.AsyncClient 实例
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """初始化 PaddleOCR-VL 适配器

        Args:
            base_url: PaddleOCR-VL API 基础 URL，默认从环境变量读取
            timeout: HTTP 请求超时时间（秒），默认从环境变量读取
        """
        # 优先级：参数 > 环境变量 > 默认值
        from src.infrastructure.config.paddleocr import PaddleOCRConfig

        config = PaddleOCRConfig.from_env()
        self.base_url = (base_url or config.api_url).rstrip("/")
        self.timeout = timeout or config.api_timeout
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))

    async def recognize(
        self,
        file_path: str,
        page_numbers: list[int] | None = None,
    ) -> list[OCRPageResult]:
        """对指定文件执行 OCR 识别

        Args:
            file_path: 待识别文件的本地路径
            page_numbers: 需要 OCR 的页码列表（1-indexed），None 表示全部页面

        Returns:
            OCR 识别结果列表

        Raises:
            OCRConnectionError: PaddleOCR-VL 服务不可达或连接超时
            OCRProcessingError: PaddleOCR-VL 返回错误或响应解析失败
        """
        # 判断文件类型
        ext = os.path.splitext(file_path)[1].lower()
        is_pdf = ext == ".pdf"

        if is_pdf:
            return await self._recognize_pdf(file_path, page_numbers)
        else:
            return await self._recognize_image(file_path)

    async def _recognize_pdf(
        self,
        file_path: str,
        page_numbers: list[int] | None = None,
    ) -> list[OCRPageResult]:
        """对 PDF 文件执行 OCR 识别

        若 page_numbers 指定了页码范围，调用 pypdf 拆分 PDF 为单页文件后分别请求。
        使用 asyncio.Semaphore(MAX_CONCURRENCY) 限制并发数。

        Args:
            file_path: PDF 文件路径
            page_numbers: 需要 OCR 的页码列表

        Returns:
            OCR 识别结果列表
        """
        if page_numbers is None:
            # 全量 OCR：直接发送完整 PDF
            result = await self._call_ocr_api(file_path, file_type=0)
            return [result]
        else:
            # 按页拆分后并发请求
            return await self._recognize_pdf_pages(file_path, page_numbers)

    async def _recognize_pdf_pages(
        self,
        file_path: str,
        page_numbers: list[int],
    ) -> list[OCRPageResult]:
        """拆分 PDF 为单页后并发 OCR 识别

        使用 asyncio.Semaphore(MAX_CONCURRENCY) 限制并发数，
        通过 asyncio.gather() 并发发送多页请求。

        Args:
            file_path: PDF 文件路径
            page_numbers: 需要 OCR 的页码列表

        Returns:
            OCR 识别结果列表
        """
        from pypdf import PdfReader, PdfWriter

        # 去重并校验页码
        page_numbers = sorted(set(page_numbers))
        if not page_numbers:
            return []
        if any(pn < 1 for pn in page_numbers):
            raise OCRProcessingError(
                message=f"页码必须为正整数: {page_numbers}",
                service_url=self.base_url,
            )

        results: list[OCRPageResult] = []
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        async def _process_page(page_number: int) -> OCRPageResult | None:
            """处理单页 OCR"""
            async with semaphore:
                tmp_path = ""
                try:
                    # 写入单页临时 PDF
                    try:
                        reader = PdfReader(file_path)
                    except Exception as e:
                        logger.warning("无法读取 PDF 文件: %s", os.path.basename(file_path), exc_info=True)
                        raise OCRProcessingError(
                            message=f"PDF 第 {page_number} 页读取失败",
                            cause=e,
                            service_url=self.base_url,
                        ) from e
                    if page_number - 1 < 0 or page_number - 1 >= len(reader.pages):
                        logger.warning("PDF 页码超出范围: page=%d, total=%d", page_number, len(reader.pages))
                        return None
                    writer = PdfWriter()
                    writer.add_page(reader.pages[page_number - 1])
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                    try:
                        os.fchmod(tmp.fileno(), 0o600)
                        writer.write(tmp)
                        tmp.close()
                        tmp_path = tmp.name
                    except Exception:
                        tmp.close()
                        if os.path.exists(tmp.name):
                            os.unlink(tmp.name)
                        raise

                    # 调用 OCR API
                    return await self._call_ocr_api(tmp_path, file_type=0, page_number=page_number)

                except Exception as e:
                    raise OCRProcessingError(
                        message=f"PDF 第 {page_number} 页 OCR 处理失败",
                        cause=e,
                        service_url=self.base_url,
                    ) from e
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            logger.warning("临时文件清理失败: %s", tmp_path)

        tasks = [_process_page(pn) for pn in page_numbers]
        page_results = await asyncio.gather(*tasks, return_exceptions=True)

        connection_failures = 0
        for pn, res in zip(page_numbers, page_results):
            if isinstance(res, OCRConnectionError):
                connection_failures += 1
                logger.warning("第 %d 页 OCR 连接失败: %s", pn, res)
                continue
            if isinstance(res, Exception):
                logger.warning("第 %d 页 OCR 失败: %s", pn, res)
                continue
            if res is not None:
                if not isinstance(res, OCRPageResult):
                    logger.warning("第 %d 页返回非 OCRPageResult 类型: %s", pn, type(res))
                    continue
                results.append(res)

        if not results:
            if connection_failures == len(page_numbers):
                raise OCRConnectionError(
                    message="OCR 服务不可达：所有页面连接失败",
                    service_url=self.base_url,
                )
            raise OCRProcessingError(
                message="OCR 处理失败：所有页面均未返回结果",
                service_url=self.base_url,
            )

        return results

    async def _recognize_image(self, file_path: str) -> list[OCRPageResult]:
        """对图像文件执行 OCR 识别

        Args:
            file_path: 图像文件路径

        Returns:
            OCR 识别结果列表
        """
        result = await self._call_ocr_api(file_path, file_type=1)
        return [result]

    async def _call_ocr_api(
        self,
        file_path: str,
        file_type: int,
        page_number: int | None = None,
    ) -> OCRPageResult:
        """调用 PaddleOCR-VL API 执行 OCR

        实现指数退避重试（含随机抖动 jitter），仅对 5xx/连接错误重试。

        Args:
            file_path: 文件路径
            file_type: 文件类型（0=PDF, 1=image）
            page_number: 页码（用于多页 PDF 拆分场景）

        Returns:
            单页 OCR 识别结果

        Raises:
            OCRConnectionError: 服务不可达或连接超时
            OCRProcessingError: 返回错误或响应解析失败
        """
        # 读取文件为 base64
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        except OSError as e:
            raise OCRProcessingError(
                message="无法读取文件",
                cause=e,
                service_url=self.base_url,
            ) from e

        b64_data = base64.b64encode(file_bytes).decode("ascii")

        payload = {
            "file": b64_data,
            "fileType": file_type,
        }

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.post(
                    f"{self.base_url}/layout-parsing",
                    json=payload,
                )

                if resp.status_code != 200:
                    raise OCRProcessingError(
                        message=f"PaddleOCR-VL 返回非 200 状态码: {resp.status_code}",
                        service_url=self.base_url,
                        status_code=resp.status_code,
                        response_body=resp.text[:200],
                    )

                return self._parse_response(resp.json(), page_number=page_number)

            except httpx.ConnectError as e:
                last_error = OCRConnectionError(
                    message=f"PaddleOCR-VL 服务不可达 (attempt {attempt + 1}/{MAX_RETRIES + 1})",
                    cause=e,
                    service_url=self.base_url,
                )
                if attempt < MAX_RETRIES:
                    await self._wait_retry(attempt)
                continue

            except httpx.TimeoutException as e:
                last_error = OCRConnectionError(
                    message=f"PaddleOCR-VL 请求超时 (attempt {attempt + 1}/{MAX_RETRIES + 1})",
                    cause=e,
                    service_url=self.base_url,
                )
                if attempt < MAX_RETRIES:
                    await self._wait_retry(attempt)
                continue

            except (OCRConnectionError, OCRProcessingError):
                raise

            except Exception as e:
                raise OCRProcessingError(
                    message="OCR API 调用异常",
                    cause=e,
                    service_url=self.base_url,
                ) from e

        if last_error is None:
            raise OCRProcessingError(
                message="OCR 重试耗尽但未记录错误",
                service_url=self.base_url,
            )
        raise last_error

    async def _wait_retry(self, attempt: int) -> None:
        """指数退避等待（含随机抖动 jitter）

        Args:
            attempt: 当前重试次数（0-indexed）
        """
        base = 1.0
        delay = base * (2**attempt) + secrets.randbelow(1000) / 1000.0
        logger.info("OCR 重试等待 %.2f 秒 (attempt %d)", delay, attempt + 1)
        await asyncio.sleep(delay)

    def _parse_response(
        self,
        response_data: dict[str, Any],
        page_number: int | None = None,
    ) -> OCRPageResult:
        """解析 PaddleOCR-VL API 响应

        Args:
            response_data: API 返回的 JSON 数据
            page_number: 页码（从 response 中提取或使用传入值）

        Returns:
            单页 OCR 识别结果

        Raises:
            OCRProcessingError: 响应格式不符合预期
        """
        try:
            result = response_data.get("result", {})
            layout_results = result.get("layoutParsingResults", [])
        except (AttributeError, TypeError) as e:
            raise OCRProcessingError(
                message="PaddleOCR-VL 响应结构不符合预期",
                cause=e,
                service_url=self.base_url,
            ) from e

        if not layout_results:
            # 空结果：返回空 elements 列表
            return OCRPageResult(
                page_number=page_number or 1,
                elements=[],
                raw_response=response_data,
            )

        page_result = layout_results[0]
        actual_page = page_number or (page_result.get("pageIndex", 0) + 1)

        pruned = page_result.get("prunedResult", {})
        parsing_res_list = pruned.get("parsing_res_list", [])

        elements: list[ParsedElement] = []
        for block in parsing_res_list:
            element = self._block_to_element(block)
            elements.append(element)

        return OCRPageResult(
            page_number=actual_page,
            elements=elements,
            raw_response=response_data,
        )

    def _block_to_element(self, block: dict[str, Any]) -> ParsedElement:
        """将 PaddleOCR-VL block 映射为 ParsedElement

        Args:
            block: PaddleOCR-VL 返回的单个 block 数据

        Returns:
            ParsedElement 实例
        """
        block_content = block.get("block_content", "")
        plain_text = self._strip_markdown(block_content)

        # 置信度提取：API per-block confidence → layout_det_res score → 默认 0.5
        confidence = block.get("confidence", None)
        if confidence is None:
            # 尝试从 layout_det_res 中提取 score
            layout_det_res = block.get("layout_det_res", {})
            confidence = layout_det_res.get("score", None)
        if confidence is None:
            confidence = 0.5

        # 确保 confidence 在 [0.0, 1.0] 范围内
        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            logger.warning("OCR 返回非数值置信度: %s，回退至 0.5", confidence)
            confidence = 0.5

        confidence = round(confidence, 4)

        metadata: dict[str, Any] = {
            "ocr_format": "markdown",
            "original_markdown": block_content,
            "ocr_block_label": block.get("block_label", ""),
        }

        # 可选：BoundingBox 信息
        block_bbox = block.get("block_bbox", None)
        if block_bbox and isinstance(block_bbox, list) and len(block_bbox) == 4:
            metadata["ocr_block_bbox"] = {
                "x": block_bbox[0],
                "y": block_bbox[1],
                "width": block_bbox[2],
                "height": block_bbox[3],
            }

        return ParsedElement(
            content=plain_text,
            confidence=confidence,
            metadata=metadata,
        )

    @staticmethod
    def _strip_markdown(markdown_text: str) -> str:
        """将 Markdown 格式文本转为纯文本

        移除 Markdown 标记（标题 #、粗体 **、列表 -、表格 | 等），
        保留换行作为段落分隔。

        Args:
            markdown_text: Markdown 格式文本

        Returns:
            纯文本
        """
        import re

        text = markdown_text

        # 移除图像标记 ![alt](url)
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
        # 移除链接标记 [text](url)
        text = re.sub(r"\[([^\]]*?)\]\(.*?\)", r"\1", text)
        # 移除 Markdown 标题标记
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        # 移除粗体/斜体
        text = re.sub(r"\*\*\*(.*?)\*\*\*", r"\1", text)
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"\*(.*?)\*", r"\1", text)
        # 移除行内代码
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # 移除表格分隔行
        text = re.sub(r"^\|[-| ]+\|$", "", text, flags=re.MULTILINE)
        # 移除表格行首/尾的 |
        text = re.sub(r"^\|", "", text, flags=re.MULTILINE)
        text = re.sub(r"\|$", "", text, flags=re.MULTILINE)
        # 移除列表标记
        text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[\s]*\d+\.\s+", "", text, flags=re.MULTILINE)
        # 移除引用标记
        text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
        # 移除水平线
        text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
        # 合并多个空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 合并多个空格
        text = re.sub(r" {2,}", " ", text)

        return text.strip()

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        await self._client.aclose()

    async def __aenter__(self) -> PaddleOCRVLAdapter:
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, *args) -> None:
        """异步上下文管理器退出"""
        await self.close()


__all__ = [
    "PaddleOCRVLAdapter",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "MAX_CONCURRENCY",
]
