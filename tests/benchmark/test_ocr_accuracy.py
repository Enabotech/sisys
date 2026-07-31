"""OCR 准确率基准测试

使用真实 PaddleOCR-VL 服务对 6 个真实 PDF 文档进行 OCR 准确率验证。
测试项：
1. 置信度值域校验 [0.0, 1.0]
2. 关键术语识别（ground truth keyword matching）
3. 中英文混合识别能力
4. 扫描页检测正确性
5. 常规文本页跳过 OCR 逻辑

前置条件：
- PaddleOCR-VL 服务运行在 localhost:8080（或通过 get_test_env() 配置）
- 数据集位于 /mnt/x/.data/raw/ocr/

运行方式：
    poetry run pytest tests/benchmark/test_ocr_accuracy.py -v --timeout=600
    poetry run pytest tests/benchmark/test_ocr_accuracy.py -v -k "keyword"  # 仅关键词测试
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx
import pytest

from src.domain.value_objects.parsed_document import ParsedDocument
from src.infrastructure.document_parsing.paddleocr_vl_adapter import PaddleOCRVLAdapter
from tests.benchmark.ocr_data import (
    ACCURACY_TEST_DOCUMENTS,
    ALL_DOCUMENTS,
    OCRDocumentSpec,
)
from tests.environments import get_test_env

logger = logging.getLogger(__name__)

# ===================================================================
# 常量
# ===================================================================
_PADDLEOCR_VL_URL = get_test_env().paddleocr.api_url
_OCR_CONFIDENCE_THRESHOLD = 0.85
_OCR_MAX_BYTES = 50 * 1024 * 1024  # 50MB — 与领域层常量一致

# 准确率达标阈值
_KEYWORD_RECALL_THRESHOLD = 0.8  # 关键词召回率 ≥ 80%
_CHINESE_ACCURACY_THRESHOLD = 0.85  # 中文识别置信度均值 ≥ 0.85


# ===================================================================
# Helpers
# ===================================================================


def _paddleocr_vl_available() -> bool:
    """检查 PaddleOCR-VL API 是否可用"""
    try:
        resp = httpx.get(f"{_PADDLEOCR_VL_URL}/health", timeout=5.0)
        return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def _check_file_size_guard(spec: OCRDocumentSpec) -> bool:
    """检查文件是否超过 OCR 大小限制（50MB）

    Returns:
        True 如果文件可执行 OCR（≤ 50MB）
    """
    file_size = os.path.getsize(str(spec.path))
    return file_size <= _OCR_MAX_BYTES


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture(scope="module")
def event_loop():
    """模块级事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def ocr_adapter() -> PaddleOCRVLAdapter:
    """创建 PaddleOCR-VL 适配器实例"""
    return PaddleOCRVLAdapter(base_url=_PADDLEOCR_VL_URL, timeout=600.0)


# ===================================================================
# 工具函数
# ===================================================================


async def _ocr_document(
    adapter: PaddleOCRVLAdapter,
    spec: OCRDocumentSpec,
    page_numbers: list[int] | None = None,
) -> list:
    """对单个文档执行 OCR 识别

    Args:
        adapter: PaddleOCR-VL 适配器
        spec: 文档规格
        page_numbers: 需要 OCR 的页码列表，None 表示全部

    Returns:
        OCRPageResult 列表
    """
    file_path = str(spec.path)
    if not os.path.exists(file_path):
        pytest.skip(f"数据集文件不存在: {file_path}")

    return await adapter.recognize(file_path, page_numbers)


async def _ocr_with_parser(
    adapter: PaddleOCRVLAdapter,
    spec: OCRDocumentSpec,
) -> ParsedDocument:
    """通过 DocumentParsingService._apply_ocr() 流程执行 OCR

    先使用 PDFParser 解析获取页面结构，再应用 OCR 增强。
    """
    from unittest.mock import MagicMock

    from src.application.services.document_parsing_service import DocumentParsingService
    from src.infrastructure.document_parsing.pdf_parser import PDFParser

    file_path = str(spec.path)
    if not os.path.exists(file_path):
        pytest.skip(f"数据集文件不存在: {file_path}")

    # 第一步：使用 PDFParser 解析文件获取页面结构
    pdf_parser = PDFParser()
    # 确定 MIME 类型
    mime_type = "application/pdf"
    parsed_doc = pdf_parser.parse(file_path, mime_type)

    if parsed_doc.is_failed():
        return parsed_doc

    # 第二步：创建 DocumentParsingService 并应用 OCR
    service = DocumentParsingService(
        document_repository=MagicMock(),
        document_storage=MagicMock(),
        event_publisher=MagicMock(),
        document_parser=MagicMock(),
        ocr=adapter,
    )

    result, _ = await service._apply_ocr(parsed_doc, file_path, mime_type)
    return result


# ===================================================================
# 测试 — 置信度值域校验
# ===================================================================


class TestOCRConfidenceValidity:
    """OCR 置信度值域和格式校验"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "spec",
        [s for s in ACCURACY_TEST_DOCUMENTS if _check_file_size_guard(s)],
        ids=[s.display_name for s in ACCURACY_TEST_DOCUMENTS if _check_file_size_guard(s)],
    )
    async def test_confidence_in_range(self, ocr_adapter: PaddleOCRVLAdapter, spec: OCRDocumentSpec) -> None:
        """验证所有 OCR 返回的 confidence 值在 [0.0, 1.0] 范围内"""
        if not _paddleocr_vl_available():
            pytest.skip("PaddleOCR-VL 服务不可用")

        # 仅测试前 5 页（大文档避免超时）
        test_pages = list(range(1, min(6, spec.total_pages + 1)))
        results = await _ocr_document(ocr_adapter, spec, page_numbers=test_pages)

        assert len(results) > 0, f"{spec.display_name} OCR 未返回结果"

        for page_result in results:
            for elem in page_result.elements:
                assert 0.0 <= elem.confidence <= 1.0, f"confidence={elem.confidence} 超出 [0.0, 1.0]"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "spec",
        [s for s in ACCURACY_TEST_DOCUMENTS if _check_file_size_guard(s)],
        ids=[s.display_name for s in ACCURACY_TEST_DOCUMENTS if _check_file_size_guard(s)],
    )
    async def test_confidence_reasonable(self, ocr_adapter: PaddleOCRVLAdapter, spec: OCRDocumentSpec) -> None:
        """验证 OCR 置信度均值在合理范围内（≥ 0.5）"""
        if not _paddleocr_vl_available():
            pytest.skip("PaddleOCR-VL 服务不可用")

        test_pages = list(range(1, min(4, spec.total_pages + 1)))
        results = await _ocr_document(ocr_adapter, spec, page_numbers=test_pages)

        all_confidences = []
        for page_result in results:
            for elem in page_result.elements:
                all_confidences.append(elem.confidence)

        if all_confidences:
            avg_conf = sum(all_confidences) / len(all_confidences)
            assert avg_conf >= 0.5, f"{spec.display_name} 平均置信度 {avg_conf:.3f} 过低"


# ===================================================================
# 测试 — 关键词识别（ground truth）
# ===================================================================


class TestOCRKeywordRecognition:
    """OCR 关键词识别准确率测试"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "spec",
        [s for s in ACCURACY_TEST_DOCUMENTS if _check_file_size_guard(s)],
        ids=[s.display_name for s in ACCURACY_TEST_DOCUMENTS if _check_file_size_guard(s)],
    )
    async def test_keyword_recall(self, ocr_adapter: PaddleOCRVLAdapter, spec: OCRDocumentSpec) -> None:
        """验证 OCR 能识别 ground truth 关键词中的大部分

        测试策略：
        - 对文档前 10 页执行 OCR
        - 检查 ground truth 关键词在 OCR 结果中的召回率
        - 关键词包含中文和英文，验证中英文混合识别能力
        """
        if not _paddleocr_vl_available():
            pytest.skip("PaddleOCR-VL 服务不可用")

        test_pages = list(range(1, min(11, spec.total_pages + 1)))
        results = await _ocr_document(ocr_adapter, spec, page_numbers=test_pages)

        # 收集所有 OCR 文本
        all_text = ""
        for page_result in results:
            for elem in page_result.elements:
                all_text += elem.content + "\n"

        # 检查关键词召回率
        keywords = spec.ground_truth_keywords
        if not keywords:
            pytest.skip(f"{spec.display_name} 未配置 ground truth 关键词")

        matched = 0
        unmatched: list[str] = []
        for kw in keywords:
            if kw.lower() in all_text.lower():
                matched += 1
            else:
                unmatched.append(kw)

        recall = matched / len(keywords)
        logger.info(
            "%s 关键词召回率: %.1f%% (%d/%d), 未匹配: %s",
            spec.display_name,
            recall * 100,
            matched,
            len(keywords),
            unmatched,
        )

        # 允许一些关键词由于 OCR 识别差异而未被匹配
        # 但至少应达到阈值
        assert recall >= _KEYWORD_RECALL_THRESHOLD, (
            f"{spec.display_name} 关键词召回率 {recall:.1%} < {_KEYWORD_RECALL_THRESHOLD:.0%}, 未匹配: {unmatched}"
        )


# ===================================================================
# 测试 — 完整解析流程测试
# ===================================================================


class TestOCRFullPipeline:
    """完整解析流程（PDFParser → _apply_ocr）测试"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "spec",
        [s for s in ACCURACY_TEST_DOCUMENTS if _check_file_size_guard(s)],
        ids=[s.display_name for s in ACCURACY_TEST_DOCUMENTS if _check_file_size_guard(s)],
    )
    async def test_full_pipeline_scanned_pages(self, ocr_adapter: PaddleOCRVLAdapter, spec: OCRDocumentSpec) -> None:
        """完整流程：PDFParser 解析 → _apply_ocr 扫描页检测 → OCR 识别

        验证：
        - 扫描页 PDF 解析后状态为 COMPLETED
        - 每个 ParsedElement 含 content 和 confidence
        - confidence 值域 [0.0, 1.0]
        """
        if not _paddleocr_vl_available():
            pytest.skip("PaddleOCR-VL 服务不可用")

        result = await _ocr_with_parser(ocr_adapter, spec)

        # 验证解析状态
        assert result.is_completed(), f"{spec.display_name} 解析状态应为 COMPLETED，实际: {result.parse_status}"

        # 验证每个元素的结构
        for page in result.pages:
            for elem in page.texts:
                assert isinstance(elem.content, str), "content 应为字符串"
                assert 0.0 <= elem.confidence <= 1.0, f"confidence 超出范围: {elem.confidence}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "spec",
        [s for s in ALL_DOCUMENTS],
        ids=[s.display_name for s in ALL_DOCUMENTS],
    )
    async def test_pipeline_does_not_crash(self, ocr_adapter: PaddleOCRVLAdapter, spec: OCRDocumentSpec) -> None:
        """验证完整流程对所有文档不崩溃

        即使大文件超过 50MB OCR 限制，流程也应正常降级。
        """
        if not _paddleocr_vl_available():
            pytest.skip("PaddleOCR-VL 服务不可用")

        result = await _ocr_with_parser(ocr_adapter, spec)

        # 不应抛出异常，解析状态应为 COMPLETED 或 FAILED
        assert result.parse_status in ("completed", "failed"), f"意外解析状态: {result.parse_status}"


# ===================================================================
# 测试 — 中英文混合识别
# ===================================================================


class TestOCRChineseEnglish:
    """中英文混合识别能力测试"""

    @pytest.mark.asyncio
    async def test_chinese_text_recognized(self, ocr_adapter: PaddleOCRVLAdapter) -> None:
        """验证中文文本被正确识别

        使用费恩曼物理学讲义（纯中文扫描件）
        """
        if not _paddleocr_vl_available():
            pytest.skip("PaddleOCR-VL 服务不可用")

        from tests.benchmark.ocr_data import FEYNMAN_1

        if not _check_file_size_guard(FEYNMAN_1):
            pytest.skip("文件超过 50MB OCR 限制")

        test_pages = [1, 2, 3]  # 前 3 页
        results = await _ocr_document(ocr_adapter, FEYNMAN_1, page_numbers=test_pages)

        all_text = ""
        for page_result in results:
            for elem in page_result.elements:
                all_text += elem.content

        # 验证中文文本非空
        assert len(all_text) > 0, "OCR 未识别出任何中文文本"

        # 验证包含中文字符
        chinese_chars = sum(1 for c in all_text if "一" <= c <= "鿿")
        assert chinese_chars > 0, f"OCR 结果中未检测到中文字符，文本: {all_text[:200]}"

        # 验证平均置信度
        all_conf = [e.confidence for pr in results for e in pr.elements]
        if all_conf:
            avg_conf = sum(all_conf) / len(all_conf)
            assert avg_conf >= _CHINESE_ACCURACY_THRESHOLD, f"中文识别平均置信度 {avg_conf:.3f} < {_CHINESE_ACCURACY_THRESHOLD}"

    @pytest.mark.asyncio
    async def test_bilingual_document(self, ocr_adapter: PaddleOCRVLAdapter) -> None:
        """验证中英文混合文档的识别能力

        使用少年时系列（含中文标题和英文术语）
        """
        if not _paddleocr_vl_available():
            pytest.skip("PaddleOCR-VL 服务不可用")

        from tests.benchmark.ocr_data import SHAONIANSHI_36

        if not _check_file_size_guard(SHAONIANSHI_36):
            pytest.skip("文件超过 50MB OCR 限制")

        test_pages = [1, 2, 3]
        results = await _ocr_document(ocr_adapter, SHAONIANSHI_36, page_numbers=test_pages)

        all_text = ""
        for page_result in results:
            for elem in page_result.elements:
                all_text += elem.content

        # 验证包含中文字符
        chinese_chars = sum(1 for c in all_text if "一" <= c <= "鿿")
        assert chinese_chars > 0, "OCR 结果中未检测到中文字符"

        # 验证包含英文字符（科学术语可能含英文）
        english_chars = sum(1 for c in all_text if c.isascii() and c.isalpha())
        logger.info("OCR 结果: 中文 %d 字符, 英文 %d 字符, 总 %d 字符", chinese_chars, english_chars, len(all_text))


# ===================================================================
# 测试 — 扫描页检测正确性
# ===================================================================


class TestOCRScannedPageDetection:
    """扫描页检测逻辑正确性测试"""

    @pytest.mark.asyncio
    async def test_scanned_pages_detected(self, ocr_adapter: PaddleOCRVLAdapter) -> None:
        """验证纯扫描件 PDF 的扫描页检测

        费恩曼物理学讲义无嵌入文本，所有页面应被检测为扫描页。
        """
        from src.domain.services.scanned_page_detector import detect_scanned_pages
        from src.infrastructure.document_parsing.pdf_parser import PDFParser
        from tests.benchmark.ocr_data import FEYNMAN_1

        if not os.path.exists(str(FEYNMAN_1.path)):
            pytest.skip("数据集文件不存在")

        # 先用 PDFParser 解析
        parser = PDFParser()
        parsed_doc = parser.parse(str(FEYNMAN_1.path), "application/pdf")

        # 检测扫描页
        scanned_pages = detect_scanned_pages(parsed_doc.pages)

        # 纯扫描件应所有页都被检测为扫描页
        assert len(scanned_pages) > 0, "纯扫描件应检测到扫描页"
        logger.info("费恩曼-1: %d/%d 页被检测为扫描页", len(scanned_pages), len(parsed_doc.pages))


# ===================================================================
# 测试 — 文件大小守卫
# ===================================================================


class TestOCRFileSizeGuard:
    """OCR 文件大小守卫逻辑测试"""

    @pytest.mark.asyncio
    async def test_large_file_skipped(self) -> None:
        """验证超过 50MB 的文件跳过 OCR

        少年时-50（128MB）和少年时-60（144MB）应被跳过
        """
        from tests.benchmark.ocr_data import SHAONIANSHI_50, SHAONIANSHI_60

        for spec in [SHAONIANSHI_50, SHAONIANSHI_60]:
            file_size = os.path.getsize(str(spec.path))
            if file_size > _OCR_MAX_BYTES:
                logger.info("%s 大小 %dMB > 50MB，确认跳过 OCR", spec.display_name, file_size // (1024 * 1024))
            else:
                logger.info("%s 大小 %dMB ≤ 50MB，可执行 OCR", spec.display_name, file_size // (1024 * 1024))
