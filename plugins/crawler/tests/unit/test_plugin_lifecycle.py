"""插件生命周期单元测试

验证 CrawlerPlugin 的安装、激活、任务管理

"""

from __future__ import annotations

from unittest.mock import MagicMock

from plugins.crawler.core.value_objects import CrawlStatus
from plugins.crawler.plugin import CrawlerPlugin


class TestCrawlerPlugin:
    """CrawlerPlugin 生命周期测试"""

    def test_install_registers_handlers(self) -> None:
        """install 应注册默认格式处理器"""
        plugin = CrawlerPlugin()
        plugin.install()
        formats = plugin.list_supported_formats()
        assert "pdf" in formats
        assert "docx" in formats
        assert "xlsx" in formats

    def test_list_supported_formats_sorted(self) -> None:
        """list_supported_formats 应返回排序列表"""
        plugin = CrawlerPlugin()
        plugin.install()
        formats = plugin.list_supported_formats()
        assert formats == sorted(formats)

    def test_get_task_status_not_found(self) -> None:
        """查询不存在的任务应返回 None"""
        plugin = CrawlerPlugin()
        assert plugin.get_task_status("nonexistent") is None

    def test_cancel_nonexistent_task(self) -> None:
        """取消不存在的任务应返回 False"""
        plugin = CrawlerPlugin()
        assert plugin.cancel_task("nonexistent") is False

    def test_list_tasks_empty(self) -> None:
        """初始时任务列表应为空"""
        plugin = CrawlerPlugin()
        assert plugin.list_tasks() == []

    def test_cancel_completed_task(self) -> None:
        """取消已完成的任务应返回 False"""
        plugin = CrawlerPlugin()
        plugin.install()
        plugin.activate(
            storage=MagicMock(),
            publisher=MagicMock(),
        )
        from plugins.crawler.core.entities import CrawlTask

        task = CrawlTask(domains=("example.com",), allowed_extensions=("pdf",))
        plugin.start_crawl(task)
        result = plugin.get_task_status(task.task_id)
        assert result is not None
        result.status = CrawlStatus.COMPLETED
        assert plugin.cancel_task(task.task_id) is False
