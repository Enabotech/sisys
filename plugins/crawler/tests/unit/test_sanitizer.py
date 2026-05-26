"""文件名清洗器单元测试

TDD 阶段：绿
验证 FilenameSanitizer 的非法字符替换、长度截断、保留名处理

"""

from __future__ import annotations

from plugins.crawler.core.naming.sanitizer import FilenameSanitizer


class TestFilenameSanitizer:
    """FilenameSanitizer 清洗逻辑测试"""

    def setup_method(self) -> None:
        self.sanitizer = FilenameSanitizer(max_length=200)

    def test_replace_illegal_chars(self) -> None:
        """非法字符应替换为下划线"""
        result = self.sanitizer.sanitize("Report: Q3/2024 <Draft>", "pdf")
        assert ":" not in result
        assert "/" not in result
        assert "<" not in result
        assert ">" not in result
        assert result.endswith(".pdf")

    def test_collapse_whitespace(self) -> None:
        """连续空格和下划线应合并为单空格"""
        result = self.sanitizer.sanitize("Annual   Report", "pdf")
        assert "  " not in result
        assert result == "Annual Report.pdf"

    def test_collapse_underscores(self) -> None:
        """连续下划线应合并为空格"""
        result = self.sanitizer.sanitize("Annual___Report", "pdf")
        assert "___" not in result

    def test_reserved_name_con(self) -> None:
        """Windows 保留名 CON 应加前缀下划线"""
        result = self.sanitizer.sanitize("CON", "txt")
        assert result.startswith("_")

    def test_reserved_name_prn(self) -> None:
        """Windows 保留名 PRN 应加前缀下划线"""
        result = self.sanitizer.sanitize("PRN", "txt")
        assert result.startswith("_")

    def test_normal_name_unchanged(self) -> None:
        """正常文件名应直接追加扩展名"""
        result = self.sanitizer.sanitize("Annual Report", "pdf")
        assert result == "Annual Report.pdf"

    def test_truncate_long_name(self) -> None:
        """超长文件名应截断"""
        sanitizer = FilenameSanitizer(max_length=20)
        long_name = "A" * 100
        result = sanitizer.sanitize(long_name, "pdf")
        assert len(result) <= 20

    def test_strip_leading_trailing_dots(self) -> None:
        """首尾点号应去除"""
        result = self.sanitizer.sanitize(" Report.pdf ", "pdf")
        assert not result.startswith(".")
        assert not result.startswith(" ")

    def test_empty_input(self) -> None:
        """空输入应返回仅扩展名"""
        result = self.sanitizer.sanitize("", "pdf")
        assert result == ".pdf"

    def test_no_extension(self) -> None:
        """无扩展名时应返回清洗后的名称"""
        result = self.sanitizer.sanitize("Test File", "")
        assert result == "Test File"

    def test_all_special_chars(self) -> None:
        """所有非法字符均应被替换"""
        result = self.sanitizer.sanitize('a<b>c:d"e/f\\g|h?i*j', "txt")
        for char in '<>:"/\\|?*':
            assert char not in result
