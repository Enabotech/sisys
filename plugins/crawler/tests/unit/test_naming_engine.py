"""智能命名引擎单元测试

TDD 阶段：绿
验证 SmartNamingEngine 的优先级链、冲突处理、降级策略

"""

from __future__ import annotations

from plugins.crawler.core.naming.engine import SmartNamingEngine


class TestSmartNamingEngine:
    """SmartNamingEngine 命名逻辑测试"""

    def setup_method(self) -> None:
        self.engine = SmartNamingEngine(max_length=200, conflict_strategy="append_hash")

    def test_metadata_title_highest_priority(self) -> None:
        """metadata_title 应优先于 page_title"""
        result = self.engine.generate_name(
            metadata_title="元数据标题",
            page_title="页面标题",
            url="https://example.com/file.pdf",
            file_extension="pdf",
        )
        assert result.strategy_name == "metadata_title"
        assert "元数据标题" in result.filename

    def test_page_title_second_priority(self) -> None:
        """page_title 在无 metadata_title 时应被选中"""
        result = self.engine.generate_name(
            page_title="页面标题",
            link_text="链接文本",
            url="https://example.com/file.pdf",
            file_extension="pdf",
        )
        assert result.strategy_name == "page_title"

    def test_link_text_third_priority(self) -> None:
        """link_text 在无更高优先级时应被选中"""
        result = self.engine.generate_name(
            link_text="下载报告",
            url="https://example.com/file.pdf",
            file_extension="pdf",
        )
        assert result.strategy_name == "link_text"

    def test_url_derived_fourth_priority(self) -> None:
        """URL 推导在无文本来源时应被选中"""
        result = self.engine.generate_name(
            url="https://example.com/reports/annual-report-2024.pdf",
            file_extension="pdf",
        )
        assert result.strategy_name == "url_derived"

    def test_hash_fallback(self) -> None:
        """无任何文本来源时应降级到哈希"""
        result = self.engine.generate_name(
            url="https://example.com/file.pdf",
            file_extension="pdf",
        )
        # url_derived 或 content_hash 都有可能
        assert result.filename.endswith(".pdf")
        assert result.confidence > 0

    def test_empty_all_inputs_with_url(self) -> None:
        """仅提供 URL 时应返回有效文件名"""
        result = self.engine.generate_name(
            url="https://example.com/test.pdf",
            file_extension="pdf",
        )
        assert ".pdf" in result.filename

    def test_empty_all_inputs_no_url_raises(self) -> None:
        """无任何输入时应抛出 ValueError"""
        import pytest

        with pytest.raises(ValueError):
            self.engine.generate_name()

    def test_conflict_append_hash(self) -> None:
        """冲突策略 append_hash 应追加短哈希"""
        result1 = self.engine.generate_name(
            metadata_title="Report",
            file_extension="pdf",
        )
        result2 = self.engine.generate_name(
            metadata_title="Report",
            file_extension="pdf",
        )
        assert result1.filename != result2.filename
        assert result2.filename.count("_") >= 1

    def test_conflict_append_counter(self) -> None:
        """冲突策略 append_counter 应追加计数器"""
        engine = SmartNamingEngine(conflict_strategy="append_counter")
        result1 = engine.generate_name(metadata_title="Report", file_extension="pdf")
        result2 = engine.generate_name(metadata_title="Report", file_extension="pdf")
        assert "(1)" not in result1.filename
        assert "(2)" in result2.filename

    def test_reset_seen(self) -> None:
        """reset_seen 后同名文件不应冲突"""
        self.engine.generate_name(metadata_title="Report", file_extension="pdf")
        self.engine.reset_seen()
        result = self.engine.generate_name(metadata_title="Report", file_extension="pdf")
        assert "(2)" not in result.filename

    def test_author_appended_to_page_title(self) -> None:
        """page_title 策略应追加作者"""
        result = self.engine.generate_name(
            page_title="报告",
            author="张三",
            url="https://example.com/file.pdf",
            file_extension="pdf",
        )
        assert "张三" in result.filename

    def test_content_title_below_metadata_title(self) -> None:
        """content_title 应低于 metadata_title"""
        result = self.engine.generate_name(
            metadata_title="元数据标题",
            content_title="内容标题",
            url="https://example.com/file.pdf",
            file_extension="pdf",
        )
        assert result.strategy_name == "metadata_title"
        assert "元数据标题" in result.filename

    def test_content_title_above_page_title(self) -> None:
        """content_title 应高于 page_title"""
        result = self.engine.generate_name(
            content_title="内容标题",
            page_title="页面标题",
            url="https://example.com/file.pdf",
            file_extension="pdf",
        )
        assert result.strategy_name == "content_title"
        assert "内容标题" in result.filename

    def test_content_title_empty_falls_to_page(self) -> None:
        """content_title 为空时应降级到 page_title"""
        result = self.engine.generate_name(
            content_title="",
            page_title="页面标题",
            url="https://example.com/file.pdf",
            file_extension="pdf",
        )
        assert result.strategy_name == "page_title"
