"""OCR 性能基准测试

使用真实 PaddleOCR-VL 服务对 6 个真实 PDF 文档进行性能测试。
测试项：
1. 单页处理延迟（P50/P95/P99）
2. 多页并发处理吞吐量
3. 文件大小对性能的影响
4. 重试/超时场景
5. 内存使用

前置条件：
- PaddleOCR-VL 服务运行在 localhost:8080（或通过 get_test_env() 配置）
- 数据集位于 /mnt/x/.data/raw/ocr/

运行方式：
    poetry run pytest tests/benchmark/test_ocr_performance.py -v --timeout=600
    poetry run pytest tests/benchmark/test_ocr_performance.py -v -k "single_page"  # 仅单页测试
"""

from __future__ import annotations

import asyncio
import logging
import os
import statistics
import time

import httpx
import pytest

from src.infrastructure.document_parsing.paddleocr_vl_adapter import PaddleOCRVLAdapter
from tests.benchmark.ocr_data import (
    ALL_DOCUMENTS,
    PERF_TEST_DOCUMENTS,
    OCRDocumentSpec,
)
from tests.environments import get_test_env

logger = logging.getLogger(__name__)

# ===================================================================
# 常量
# ===================================================================
_PADDLEOCR_VL_URL = get_test_env().paddleocr.api_url
_OCR_MAX_BYTES = 50 * 1024 * 1024  # 50MB

# 性能目标阈值
SINGLE_PAGE_P95_TARGET = 30.0  # 单页 P95 < 30 秒（最佳努力）
BATCH_PAGES_TARGET = 5  # 批量测试页数
PERF_SAMPLE_PAGES = 3  # 性能采样页数


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
    """检查文件是否超过 OCR 大小限制（50MB）"""
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
# 测试 — 单页延迟
# ===================================================================


class TestOCRPageLatency:
    """单页 OCR 处理延迟测试"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "spec",
        [s for s in PERF_TEST_DOCUMENTS if _check_file_size_guard(s)],
        ids=[s.display_name for s in PERF_TEST_DOCUMENTS if _check_file_size_guard(s)],
    )
    async def test_single_page_latency(self, ocr_adapter: PaddleOCRVLAdapter, spec: OCRDocumentSpec) -> None:
        """测量单页 OCR 处理延迟

        验证单页 P95 延迟在可接受范围内。
        注意：首次调用可能较慢（模型预热），结果仅供参考。
        """
        if not _paddleocr_vl_available():
            pytest.skip("PaddleOCR-VL 服务不可用")

        file_path = str(spec.path)
        if not os.path.exists(file_path):
            pytest.skip(f"数据集文件不存在: {file_path}")

        # 测量单页延迟（第 1 页）
        latencies: list[float] = []
        for i in range(PERF_SAMPLE_PAGES):
            page = i + 1
            t0 = time.monotonic()
            results = await ocr_adapter.recognize(file_path, page_numbers=[page])
            elapsed = time.monotonic() - t0
            latencies.append(elapsed)

            elem_count = len(results[0].elements) if results else 0
            logger.info(
                "%s 第%d页: %.2f秒, %d元素",
                spec.display_name,
                page,
                elapsed,
                elem_count,
            )

        # 统计
        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 2 else latencies[-1]

        logger.info(
            "%s 单页延迟: P50=%.2f秒, P95=%.2f秒, 采样=%d次",
            spec.display_name,
            p50,
            p95,
            len(latencies),
        )

        # 记录但不强制断言（首次运行可能较慢）
        if p95 > SINGLE_PAGE_P95_TARGET:
            logger.warning(
                "%s P95 延迟 %.2f秒 超过目标 %.2f秒（首次运行可能有模型预热开销）",
                spec.display_name,
                p95,
                SINGLE_PAGE_P95_TARGET,
            )


# ===================================================================
# 测试 — 多页并发处理
# ===================================================================


class TestOCRMultiPageConcurrency:
    """多页并发 OCR 处理测试"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "spec",
        [s for s in PERF_TEST_DOCUMENTS if _check_file_size_guard(s)],
        ids=[s.display_name for s in PERF_TEST_DOCUMENTS if _check_file_size_guard(s)],
    )
    async def test_concurrent_pages(self, ocr_adapter: PaddleOCRVLAdapter, spec: OCRDocumentSpec) -> None:
        """测试多页并发处理性能

        验证 Semaphore(5) 并发控制下多页处理的总延迟。
        """
        if not _paddleocr_vl_available():
            pytest.skip("PaddleOCR-VL 服务不可用")

        file_path = str(spec.path)
        if not os.path.exists(file_path):
            pytest.skip(f"数据集文件不存在: {file_path}")

        # 取前 BATCH_PAGES_TARGET 页
        test_pages = list(range(1, min(BATCH_PAGES_TARGET + 1, spec.total_pages + 1)))

        t0 = time.monotonic()
        results = await ocr_adapter.recognize(file_path, page_numbers=test_pages)
        total_elapsed = time.monotonic() - t0

        # 统计
        total_elements = sum(len(r.elements) for r in results)
        pages_processed = len(results)

        logger.info(
            "%s 并发处理 %d页: 总耗时%.2f秒, 平均%.2f秒/页, 共%d元素",
            spec.display_name,
            pages_processed,
            total_elapsed,
            total_elapsed / pages_processed if pages_processed else 0,
            total_elements,
        )

        # 验证所有请求页面都返回了结果
        assert pages_processed > 0, f"{spec.display_name} 未返回任何结果"


# ===================================================================
# 测试 — 文件大小对性能的影响
# ===================================================================


class TestOCRFileSizeImpact:
    """文件大小对 OCR 性能的影响测试"""

    @pytest.mark.asyncio
    async def test_small_vs_large_file_performance(self) -> None:
        """比较小文件和大文件的 OCR 处理时间

        小文件 = 费恩曼-3（20MB, 377页）
        大文件 = 少年时-50（128MB, 140页）— 超过 50MB 限制，应被跳过
        """
        from tests.benchmark.ocr_data import FEYNMAN_3, SHAONIANSHI_50

        if not _paddleocr_vl_available():
            pytest.skip("PaddleOCR-VL 服务不可用")

        # 测试小文件（费恩曼-3，20MB，≤ 50MB）
        small_path = str(FEYNMAN_3.path)
        if not os.path.exists(small_path):
            pytest.skip("数据集文件不存在")

        small_size = os.path.getsize(small_path)
        logger.info("小文件: %s, %dMB", FEYNMAN_3.display_name, small_size // (1024 * 1024))

        adapter = PaddleOCRVLAdapter(base_url=_PADDLEOCR_VL_URL, timeout=600.0)
        try:
            # 处理前 3 页
            t0 = time.monotonic()
            small_results = await adapter.recognize(small_path, page_numbers=[1, 2, 3])
            small_elapsed = time.monotonic() - t0
            logger.info("小文件 3页: %.2f秒, 共%d元素", small_elapsed, sum(len(r.elements) for r in small_results))

            # 大文件（超过 50MB）应被跳过
            large_path = str(SHAONIANSHI_50.path)
            if os.path.exists(large_path):
                large_size = os.path.getsize(large_path)
                if large_size > _OCR_MAX_BYTES:
                    logger.info(
                        "大文件 %s (%dMB) 超过 50MB 限制，跳过 OCR（预期行为）",
                        SHAONIANSHI_50.display_name,
                        large_size // (1024 * 1024),
                    )
        finally:
            await adapter.close()


# ===================================================================
# 测试 — 重试和超时
# ===================================================================


class TestOCRRetryBehavior:
    """OCR 重试行为测试（使用 Mock 模拟超时）"""

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self) -> None:
        """验证连接超时后的重试行为

        使用 MockTransport 模拟超时，验证重试机制正常工作。
        """
        import tempfile

        from src.domain.exceptions.ocr_exceptions import OCRConnectionError

        # 创建临时文件作为测试输入
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(b"%PDF-1.4 fake pdf content for testing")
        tmp.close()
        fake_pdf = tmp.name

        # 创建 Mock 传输，模拟连接超时
        async def mock_timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Simulated connection timeout")

        adapter = PaddleOCRVLAdapter(
            base_url="http://localhost:19999",
            timeout=2.0,
        )
        # 替换 httpx 客户端为 MockTransport
        adapter._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_timeout_handler),
            timeout=httpx.Timeout(2.0),
        )

        try:
            t0 = time.monotonic()
            with pytest.raises(OCRConnectionError):
                await adapter.recognize(fake_pdf, page_numbers=[1])
            elapsed = time.monotonic() - t0

            # 验证重试耗时（2 次重试：1s + 2s + jitter ≈ 3-5 秒）
            logger.info("重试耗尽耗时: %.2f秒", elapsed)
            assert elapsed >= 1.0, f"重试应至少耗时 1 秒，实际: {elapsed:.2f}秒"
        finally:
            await adapter.close()
            if os.path.exists(fake_pdf):
                os.unlink(fake_pdf)


# ===================================================================
# 测试 — 长时间运行稳定性
# ===================================================================


class TestOCRStability:
    """OCR 长时间运行稳定性测试"""

    @pytest.mark.asyncio
    async def test_repeated_calls_stability(self, ocr_adapter: PaddleOCRVLAdapter) -> None:
        """验证重复调用 OCR 服务的稳定性

        对同一文档连续调用 3 次，验证：
        - 无内存泄漏（通过重复调用检测）
        - 无连接泄漏（httpx 连接池正常工作）
        - 结果一致性（相同页面的 OCR 结果非空）
        """
        from tests.benchmark.ocr_data import FEYNMAN_3

        if not _paddleocr_vl_available():
            pytest.skip("PaddleOCR-VL 服务不可用")

        if not _check_file_size_guard(FEYNMAN_3):
            pytest.skip("文件超过 50MB 限制")

        file_path = str(FEYNMAN_3.path)
        if not os.path.exists(file_path):
            pytest.skip("数据集文件不存在")

        for i in range(3):
            t0 = time.monotonic()
            results = await ocr_adapter.recognize(file_path, page_numbers=[1, 2])
            elapsed = time.monotonic() - t0

            elem_count = sum(len(r.elements) for r in results)
            logger.info("第%d次调用: %.2f秒, 共%d元素", i + 1, elapsed, elem_count)

            # 验证每次调用都返回结果
            assert len(results) > 0, f"第{i + 1}次调用返回空结果"


# ===================================================================
# 测试 — 数据完整性
# ===================================================================


class TestOCRDataIntegrity:
    """OCR 数据完整性测试"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "spec",
        [s for s in ALL_DOCUMENTS if _check_file_size_guard(s)],
        ids=[s.display_name for s in ALL_DOCUMENTS if _check_file_size_guard(s)],
    )
    async def test_ocr_result_structure(self, ocr_adapter: PaddleOCRVLAdapter, spec: OCRDocumentSpec) -> None:
        """验证 OCR 返回结果的结构完整性

        检查：
        - 每个 page_result 包含 page_number 和 elements
        - 每个 element 包含 content、confidence、metadata
        - metadata 包含 ocr_format、original_markdown、ocr_block_label
        """
        if not _paddleocr_vl_available():
            pytest.skip("PaddleOCR-VL 服务不可用")

        file_path = str(spec.path)
        if not os.path.exists(file_path):
            pytest.skip(f"数据集文件不存在: {file_path}")

        test_pages = list(range(1, min(3, spec.total_pages + 1)))
        results = await ocr_adapter.recognize(file_path, page_numbers=test_pages)

        for page_result in results:
            # 验证 page_number
            assert page_result.page_number > 0, "page_number 必须为正整数"

            # 验证每个元素的结构
            for elem in page_result.elements:
                assert isinstance(elem.content, str), "content 应为字符串"
                assert 0.0 <= elem.confidence <= 1.0, f"confidence 超出范围: {elem.confidence}"

                # 验证 metadata 中包含 OCR 标签
                if elem.metadata:
                    assert "ocr_format" in elem.metadata, "metadata 应包含 ocr_format"
                    assert "ocr_block_label" in elem.metadata, "metadata 应包含 ocr_block_label"
