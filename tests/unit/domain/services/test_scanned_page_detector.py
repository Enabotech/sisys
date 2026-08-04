"""扫描页检测领域服务测试

测试 detect_scanned_pages() 纯函数的文本密度计算、阈值判断和边界场景。
"""

from __future__ import annotations

from src.domain.services.scanned_page_detector import (
    SCANNED_PAGE_TEXT_DENSITY_THRESHOLD,
    detect_scanned_pages,
)
from src.domain.value_objects.parsed_document import ParsedElement, ParsedPage


class TestDetectScannedPages:
    """detect_scanned_pages 测试"""

    def test_empty_page_returns_scanned(self) -> None:
        """空页面（0 字符）→ 判定为扫描页"""
        pages = [
            ParsedPage(page_number=1, texts=[]),
        ]
        result = detect_scanned_pages(pages)
        assert result == [1]

    def test_empty_page_list(self) -> None:
        """空页面列表 → 返回空列表"""
        result = detect_scanned_pages([])
        assert result == []

    def test_high_density_text_page(self) -> None:
        """高密度文本页 → 判定为文本页（不触发 OCR）"""
        pages = [
            ParsedPage(
                page_number=1,
                texts=[
                    ParsedElement(content="A" * 100),
                    ParsedElement(content="B" * 100),
                ],
            ),
        ]
        result = detect_scanned_pages(pages)
        assert result == []

    def test_low_density_text_page(self) -> None:
        """低密度文本页（< 阈值）→ 判定为扫描页"""
        pages = [
            ParsedPage(
                page_number=1,
                texts=[
                    ParsedElement(content="A" * 10),
                ],
            ),
        ]
        result = detect_scanned_pages(pages)
        assert result == [1]

    def test_mixed_pages(self) -> None:
        """混合页面列表 → 正确分类每个页面"""
        pages = [
            ParsedPage(
                page_number=1,
                texts=[ParsedElement(content="A" * 100)],  # 文本页
            ),
            ParsedPage(
                page_number=2,
                texts=[ParsedElement(content="B" * 5)],  # 扫描页
            ),
            ParsedPage(
                page_number=3,
                texts=[ParsedElement(content="C" * 200)],  # 文本页
            ),
            ParsedPage(
                page_number=4,
                texts=[ParsedElement(content="D" * 3)],  # 扫描页
            ),
        ]
        result = detect_scanned_pages(pages)
        assert result == [2, 4]

    def test_boundary_exact_threshold(self) -> None:
        """恰好等于阈值 → 不触发 OCR（非扫描页）"""
        content = "A" * SCANNED_PAGE_TEXT_DENSITY_THRESHOLD  # 恰好 50 字符
        pages = [
            ParsedPage(
                page_number=1,
                texts=[ParsedElement(content=content)],
            ),
        ]
        result = detect_scanned_pages(pages)
        assert result == []

    def test_boundary_just_below_threshold(self) -> None:
        """略低于阈值 → 触发 OCR"""
        content = "A" * (SCANNED_PAGE_TEXT_DENSITY_THRESHOLD - 1)  # 49 字符
        pages = [
            ParsedPage(
                page_number=1,
                texts=[ParsedElement(content=content)],
            ),
        ]
        result = detect_scanned_pages(pages)
        assert result == [1]

    def test_multiple_elements_summed(self) -> None:
        """多个元素字符数累加"""
        pages = [
            ParsedPage(
                page_number=1,
                texts=[
                    ParsedElement(content="A" * 20),
                    ParsedElement(content="B" * 20),
                    ParsedElement(content="C" * 15),
                ],  # 总共 55 字符 > 50，文本页
            ),
        ]
        result = detect_scanned_pages(pages)
        assert result == []

    def test_only_noise_text(self) -> None:
        """仅含页码/页眉等少量噪声文本（< 50 字符）→ 仍判定为扫描页"""
        pages = [
            ParsedPage(
                page_number=1,
                texts=[
                    ParsedElement(content="Page 1 of 10"),  # 12 字符
                ],
            ),
        ]
        result = detect_scanned_pages(pages)
        assert result == [1]

    def test_custom_threshold_parameter(self) -> None:
        """通过参数传入自定义阈值"""
        pages = [
            ParsedPage(
                page_number=1,
                texts=[ParsedElement(content="A" * 30)],
            ),
        ]
        # 自定义阈值为 20 → 30 >= 20 不触发
        result = detect_scanned_pages(pages, threshold=20)
        assert result == []

    def test_env_var_threshold_override(self, monkeypatch) -> None:
        """环境变量 SISYS_SCANNED_PAGE_THRESHOLD 覆盖默认阈值"""
        pages = [
            ParsedPage(
                page_number=1,
                texts=[ParsedElement(content="A" * 30)],
            ),
        ]
        monkeypatch.setenv("SISYS_SCANNED_PAGE_THRESHOLD", "20")
        # 30 >= 20 → 不触发 OCR
        result = detect_scanned_pages(pages)
        assert result == []

    def test_env_var_threshold_invalid_type_raises(self, monkeypatch) -> None:
        """环境变量值非整数时抛出 OCRProcessingError"""
        from src.domain.exceptions.ocr_exceptions import OCRProcessingError

        pages = [
            ParsedPage(page_number=1, texts=[ParsedElement(content="test")]),
        ]
        monkeypatch.setenv("SISYS_SCANNED_PAGE_THRESHOLD", "not_a_number")
        try:
            detect_scanned_pages(pages)
            assert False, "应该抛出 OCRProcessingError"
        except OCRProcessingError as e:
            assert "SISYS_SCANNED_PAGE_THRESHOLD" in str(e)
