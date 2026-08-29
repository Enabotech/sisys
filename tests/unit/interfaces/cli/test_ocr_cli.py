"""OCR CLI 命令单元测试

测试 parse_page_spec 页码范围解析、_format_as_markdown、build_parser 等纯函数。
无需 OCR 服务连接。
"""

from __future__ import annotations

import pytest

from src.interfaces.cli.ocr_cli import _format_as_markdown, build_parser, parse_page_spec


class TestParsePageSpec:
    """测试 parse_page_spec 页码范围解析"""

    def test_single_page(self) -> None:
        assert parse_page_spec("3") == [3]

    def test_range_format(self) -> None:
        assert parse_page_spec("1-5") == [1, 2, 3, 4, 5]

    def test_comma_separated_combination(self) -> None:
        result = parse_page_spec("1-5,10,20-22")
        assert result == [1, 2, 3, 4, 5, 10, 20, 21, 22]

    def test_mixed_single_and_ranges(self) -> None:
        result = parse_page_spec("1,3,5-7")
        assert result == [1, 3, 5, 6, 7]

    def test_whitespace_insensitive(self) -> None:
        result = parse_page_spec(" 1 , 3 - 5 , 10 ")
        assert result == [1, 3, 4, 5, 10]

    def test_empty_parts_skipped(self) -> None:
        result = parse_page_spec("1, , 3")
        assert result == [1, 3]

    def test_sorted_output(self) -> None:
        result = parse_page_spec("5,1,3")
        assert result == [1, 3, 5]

    def test_page_0_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="页码必须为正整数"):
            parse_page_spec("0")

    def test_negative_page_raises_value_error(self) -> None:
        # "-1" 被解析为范围格式（- 作为分隔符），抛出范围格式错误
        with pytest.raises(ValueError, match="页码范围格式无效|页码必须为正整数"):
            parse_page_spec("-1")

    def test_range_start_lt_1_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="页码必须为正整数"):
            parse_page_spec("0-5")

    def test_range_end_lt_start_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="必须大于等于"):
            parse_page_spec("5-3")

    def test_invalid_range_format_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="页码范围格式无效"):
            parse_page_spec("a-b")

    def test_invalid_single_page_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="页码格式无效"):
            parse_page_spec("abc")

    def test_empty_spec_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="页码范围为空"):
            parse_page_spec("")

    def test_only_commas_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="页码范围为空"):
            parse_page_spec(", ,")


class TestBuildParser:
    """测试 build_parser 命令行参数解析器"""

    def test_creates_parser_with_required_file_arg(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["test.pdf"])
        assert args.file == "test.pdf"

    def test_default_pages_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["test.pdf"])
        assert args.pages is None

    def test_pages_short_option(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["test.pdf", "-p", "1-5"])
        assert args.pages == "1-5"

    def test_pages_long_option(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["test.pdf", "--pages", "1-5,10"])
        assert args.pages == "1-5,10"

    def test_output_option(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["test.pdf", "-o", "result.json"])
        assert args.output == "result.json"

    def test_model_dir_option(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["test.pdf", "--model-dir", "/models/rapidocr"])
        assert args.model_dir == "/models/rapidocr"

    def test_max_concurrency_option(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["test.pdf", "--max-concurrency", "2"])
        assert args.max_concurrency == 2


class TestFormatAsMarkdown:
    """测试 _format_as_markdown 函数"""

    def test_empty_results_returns_header_only(self) -> None:
        result = _format_as_markdown([], "/path/to/doc.pdf")
        assert "# OCR 结果: doc.pdf" in result

    def test_single_page_with_elements(self) -> None:
        from src.domain.value_objects.ocr_result import OCRPageResult
        from src.domain.value_objects.parsed_document import ParsedElement

        elem = ParsedElement(content="测试文本")
        page = OCRPageResult(page_number=1, elements=[elem])
        result = _format_as_markdown([page], "/path/doc.pdf")
        assert "## 第 1 页" in result
        assert "测试文本" in result


__all__ = [
    "TestParsePageSpec",
    "TestBuildParser",
    "TestFormatAsMarkdown",
]
