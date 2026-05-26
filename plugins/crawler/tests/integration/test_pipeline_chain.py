"""Pipeline 全链路集成测试

使用 fake_server 提供文件链接，验证 Pipeline 完整流程

"""

from __future__ import annotations

import os
import tempfile

import pytest

from plugins.crawler.scrapy_engine.items import CrawledFileItem
from plugins.crawler.scrapy_engine.pipelines.file_download_pipeline import FileDownloadPipeline
from plugins.crawler.scrapy_engine.pipelines.format_detection_pipeline import FormatDetectionPipeline
from plugins.crawler.scrapy_engine.pipelines.metadata_pipeline import MetadataPipeline
from plugins.crawler.scrapy_engine.pipelines.smart_naming_pipeline import SmartNamingPipeline


class TestPipelineChain:
    """Pipeline 全链路集成测试"""

    def setup_method(self) -> None:
        self.temp_dir = tempfile.mkdtemp()

    def _create_test_file(self, content: bytes, extension: str) -> str:
        """创建测试文件

        Args:
            content: 文件内容
            extension: 文件扩展名

        Returns:
            文件路径
        """
        fd, path = tempfile.mkstemp(suffix=f".{extension}", dir=self.temp_dir)
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        return path

    def _make_item(self, file_path: str, extension: str, content_type: str = "") -> CrawledFileItem:
        """创建测试 Item

        Args:
            file_path: 文件路径
            extension: 扩展名
            content_type: MIME 类型

        Returns:
            CrawledFileItem
        """
        item = CrawledFileItem()
        item["url"] = f"https://example.com/docs/test.{extension}"
        item["file_path"] = file_path
        item["file_name"] = f"test.{extension}"
        item["file_size"] = os.path.getsize(file_path)
        item["content_type"] = content_type
        item["file_extension"] = extension
        item["parent_url"] = "https://example.com/docs/"
        item["page_title"] = "文档中心"
        item["link_text"] = "年度报告"
        item["depth"] = 1
        item["task_id"] = "test-integration"
        return item

    def test_pdf_pipeline_chain(self) -> None:
        """PDF 文件全链路 Pipeline"""
        pdf_path = self._create_test_file(b"%PDF-1.4 test content", "pdf")
        item = self._make_item(pdf_path, "pdf", "application/pdf")

        # Pipeline 1: 文件下载验证
        download_pipeline = FileDownloadPipeline()
        item = download_pipeline.process_item(item)
        assert item["file_size"] > 0

        # Pipeline 2: 格式检测
        format_pipeline = FormatDetectionPipeline()
        format_pipeline.open_spider()
        item = format_pipeline.process_item(item)
        assert item["detected_format"] == "pdf"

        # Pipeline 3: 元数据提取
        metadata_pipeline = MetadataPipeline()
        metadata_pipeline.open_spider()
        item = metadata_pipeline.process_item(item)
        assert "metadata_title" in item
        assert "metadata_author" in item

        # Pipeline 4: 智能命名
        naming_pipeline = SmartNamingPipeline()
        naming_pipeline.open_spider()
        item = naming_pipeline.process_item(item)
        assert item["smart_name"]
        assert item["naming_strategy_used"]
        assert item["smart_name"].endswith(".pdf")

    def test_txt_pipeline_chain(self) -> None:
        """TXT 文件全链路 Pipeline"""
        txt_path = self._create_test_file("年度战略规划报告\n2024年Q4总结".encode("utf-8"), "txt")
        item = self._make_item(txt_path, "txt", "text/plain")

        download_pipeline = FileDownloadPipeline()
        format_pipeline = FormatDetectionPipeline()
        format_pipeline.open_spider()
        metadata_pipeline = MetadataPipeline()
        metadata_pipeline.open_spider()
        naming_pipeline = SmartNamingPipeline()
        naming_pipeline.open_spider()

        item = download_pipeline.process_item(item)
        item = format_pipeline.process_item(item)
        assert item["detected_format"] == "txt"

        item = metadata_pipeline.process_item(item)
        assert "metadata_title" in item

        item = naming_pipeline.process_item(item)
        assert item["smart_name"]
        assert item["smart_name"].endswith(".txt")

    def test_empty_file_dropped(self) -> None:
        """空文件应在下载 Pipeline 被丢弃"""
        from scrapy.exceptions import DropItem

        empty_path = self._create_test_file(b"", "pdf")
        item = self._make_item(empty_path, "pdf", "application/pdf")

        download_pipeline = FileDownloadPipeline()
        with pytest.raises(DropItem):
            download_pipeline.process_item(item)

    def test_naming_with_link_text(self) -> None:
        """有链接文本时应优先使用链接文本命名"""
        txt_path = self._create_test_file("内容".encode("utf-8"), "txt")
        item = self._make_item(txt_path, "txt", "text/plain")
        item["link_text"] = "战略规划报告"

        download_pipeline = FileDownloadPipeline()
        metadata_pipeline = MetadataPipeline()
        metadata_pipeline.open_spider()
        naming_pipeline = SmartNamingPipeline()
        naming_pipeline.open_spider()

        item = download_pipeline.process_item(item)
        item = metadata_pipeline.process_item(item)
        item = naming_pipeline.process_item(item)

        assert "战略规划报告" in item["smart_name"] or item["naming_strategy_used"] in (
            "link_text",
            "metadata_title",
            "page_title",
        )
