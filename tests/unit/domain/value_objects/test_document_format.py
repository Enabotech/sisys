"""Tests for DocumentFormat value object — 17 种格式校验与 MIME 映射"""

from src.domain.value_objects.document_format import (
    ARCHIVE_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    SUPPORTED_FORMATS,
    _extract_extension,
    get_extension,
    get_mime_type,
    is_supported,
)


class TestSupportedFormats:
    """验证 17 种格式定义（15 种文档 + 2 种压缩）"""

    def test_seventeen_unique_mime_types(self) -> None:
        """17 种格式对应 17 个唯一 MIME 类型"""
        unique_mimes = set(SUPPORTED_FORMATS.values())
        assert len(unique_mimes) == 17

    def test_pdf_supported(self) -> None:
        assert "pdf" in SUPPORTED_FORMATS
        assert SUPPORTED_FORMATS["pdf"] == "application/pdf"

    def test_txt_supported(self) -> None:
        assert "txt" in SUPPORTED_FORMATS
        assert SUPPORTED_FORMATS["txt"] == "text/plain"

    def test_doc_docx_supported(self) -> None:
        assert SUPPORTED_FORMATS["doc"] == "application/msword"
        assert "docx" in SUPPORTED_FORMATS

    def test_ppt_pptx_supported(self) -> None:
        assert "ppt" in SUPPORTED_FORMATS
        assert "pptx" in SUPPORTED_FORMATS

    def test_xls_xlsx_supported(self) -> None:
        assert "xls" in SUPPORTED_FORMATS
        assert "xlsx" in SUPPORTED_FORMATS

    def test_csv_supported(self) -> None:
        assert SUPPORTED_FORMATS["csv"] == "text/csv"

    def test_jpeg_jpg_both_map_to_image_jpeg(self) -> None:
        assert SUPPORTED_FORMATS["jpeg"] == "image/jpeg"
        assert SUPPORTED_FORMATS["jpg"] == "image/jpeg"

    def test_png_gif_supported(self) -> None:
        assert SUPPORTED_FORMATS["png"] == "image/png"
        assert SUPPORTED_FORMATS["gif"] == "image/gif"

    def test_markdown_and_md_both_supported(self) -> None:
        assert SUPPORTED_FORMATS["markdown"] == "text/markdown"
        assert SUPPORTED_FORMATS["md"] == "text/markdown"

    def test_html_supported(self) -> None:
        assert SUPPORTED_FORMATS["html"] == "text/html"

    def test_rtf_supported(self) -> None:
        assert SUPPORTED_FORMATS["rtf"] == "application/rtf"

    def test_zip_tar_supported(self) -> None:
        assert SUPPORTED_FORMATS["zip"] == "application/zip"
        assert SUPPORTED_FORMATS["tar"] == "application/x-tar"


class TestExtensionSets:
    """验证文档/压缩扩展名集合"""

    def test_archive_extensions_has_zip_and_tar(self) -> None:
        assert "zip" in ARCHIVE_EXTENSIONS
        assert "tar" in ARCHIVE_EXTENSIONS
        assert len(ARCHIVE_EXTENSIONS) == 2

    def test_document_extensions_count(self) -> None:
        assert len(DOCUMENT_EXTENSIONS) == 15


class TestGetMimeType:
    """验证根据文件名获取 MIME 类型"""

    def test_pdf(self) -> None:
        assert get_mime_type("report.pdf") == "application/pdf"

    def test_case_insensitive(self) -> None:
        assert get_mime_type("REPORT.PDF") == "application/pdf"
        assert get_mime_type("Report.Pdf") == "application/pdf"

    def test_jpg_extension(self) -> None:
        assert get_mime_type("photo.jpg") == "image/jpeg"

    def test_jpeg_extension(self) -> None:
        assert get_mime_type("photo.jpeg") == "image/jpeg"

    def test_md_extension(self) -> None:
        assert get_mime_type("readme.md") == "text/markdown"

    def test_markdown_extension(self) -> None:
        assert get_mime_type("doc.markdown") == "text/markdown"

    def test_unsupported_returns_none(self) -> None:
        assert get_mime_type("malware.exe") is None

    def test_no_extension_returns_none(self) -> None:
        assert get_mime_type("noext") is None

    def test_empty_string_returns_none(self) -> None:
        assert get_mime_type("") is None

    def test_dot_only_returns_none(self) -> None:
        assert get_mime_type(".") is None

    def test_trailing_dot_returns_none(self) -> None:
        assert get_mime_type("file.") is None

    def test_path_with_dots(self) -> None:
        assert get_mime_type("my.document.pdf") == "application/pdf"


class TestGetExtension:
    """验证根据 MIME 类型获取扩展名"""

    def test_pdf(self) -> None:
        assert get_extension("application/pdf") == "pdf"

    def test_image_jpeg(self) -> None:
        assert get_extension("image/jpeg") == "jpeg"

    def test_unknown_returns_none(self) -> None:
        assert get_extension("application/unknown") is None


class TestIsSupported:
    """验证格式校验"""

    def test_supported_format(self) -> None:
        assert is_supported("test.pdf") is True

    def test_unsupported_format(self) -> None:
        assert is_supported("test.exe") is False

    def test_case_insensitive(self) -> None:
        assert is_supported("TEST.PDF") is True

    def test_no_extension(self) -> None:
        assert is_supported("noext") is False

    def test_mime_matches(self) -> None:
        assert is_supported("test.pdf", "application/pdf") is True

    def test_mime_mismatch(self) -> None:
        assert is_supported("test.pdf", "text/plain") is False

    def test_jpg_mime_matches(self) -> None:
        assert is_supported("photo.jpg", "image/jpeg") is True

    def test_supported_format_none_mime(self) -> None:
        assert is_supported("test.pdf", None) is True


class TestExtractExtension:
    """验证扩展名提取"""

    def test_simple_filename(self) -> None:
        assert _extract_extension("file.pdf") == "pdf"

    def test_multiple_dots(self) -> None:
        assert _extract_extension("my.file.pdf") == "pdf"

    def test_uppercase(self) -> None:
        assert _extract_extension("file.PDF") == "pdf"

    def test_no_extension(self) -> None:
        assert _extract_extension("noext") is None

    def test_empty(self) -> None:
        assert _extract_extension("") is None

    def test_dot_only(self) -> None:
        assert _extract_extension(".") is None

    def test_trailing_dot(self) -> None:
        assert _extract_extension("file.") is None
