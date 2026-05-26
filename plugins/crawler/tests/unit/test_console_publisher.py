"""控制台发布器单元测试

验证 ConsolePublisher 的日志输出

"""

from __future__ import annotations

import logging

import pytest

from plugins.crawler.core.entities import CrawledFile, CrawlResult
from plugins.crawler.messaging.console_publisher import ConsolePublisher


class TestConsolePublisher:
    """ConsolePublisher 测试"""

    @pytest.mark.asyncio
    async def test_publish_crawl_completed_logs_info(self, caplog: pytest.LogCaptureFixture) -> None:
        """publish_crawl_completed 应记录 INFO 级别日志"""
        caplog.set_level(logging.INFO)
        publisher = ConsolePublisher()
        result = CrawlResult(task_id="task-1")
        result.mark_completed()

        await publisher.publish_crawl_completed(result)

        assert any("Crawl completed" in r.message for r in caplog.records)
        assert any(r.levelno == logging.INFO for r in caplog.records)

    @pytest.mark.asyncio
    async def test_publish_crawl_failed_logs_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """publish_crawl_failed 应记录 ERROR 级别日志"""
        caplog.set_level(logging.ERROR)
        publisher = ConsolePublisher()

        await publisher.publish_crawl_failed("task-1", "network error")

        assert any("Crawl failed" in r.message for r in caplog.records)
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    @pytest.mark.asyncio
    async def test_publish_file_crawled_logs_info(self, caplog: pytest.LogCaptureFixture) -> None:
        """publish_file_crawled 应记录 INFO 级别日志"""
        caplog.set_level(logging.INFO)
        publisher = ConsolePublisher()
        file_info = CrawledFile(
            url="https://example.com/test.pdf",
            file_path="./test.pdf",
            file_name="test.pdf",
            file_size=1024,
            content_type="application/pdf",
            file_extension="pdf",
            smart_name="Test Document.pdf",
            naming_strategy="metadata_title",
            task_id="task-1",
        )

        await publisher.publish_file_crawled(file_info)

        assert any("File crawled" in r.message for r in caplog.records)
