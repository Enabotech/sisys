"""插件生命周期单元测试

验证 CrawlerPlugin 的安装、激活、子进程任务派发、状态同步、取消

子进程派发（start_crawl → task_runner）通过 mock Popen 验证：
CrawlerProcess 在服务进程内运行会与 uvicorn 事件循环/signal 安装冲突，
子进程隔离是爬取任务的唯一合法执行形态。
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from plugins.crawler.config.settings import CrawlerSettings
from plugins.crawler.core.entities import CrawlTask
from plugins.crawler.core.value_objects import CrawlStatus
from plugins.crawler.plugin import CrawlerPlugin


def _make_plugin(tmp_path: Path) -> CrawlerPlugin:
    """构造输出目录指向 tmp_path 的插件实例

    Args:
        tmp_path: pytest 临时目录

    Returns:
        已安装的 CrawlerPlugin
    """
    settings = CrawlerSettings(local_output_dir=str(tmp_path))
    plugin = CrawlerPlugin(settings=settings)
    plugin.install()
    return plugin


def _write_result_json(tmp_path: Path, task_id: str, files: list[dict], failed_urls: list[str]) -> Path:
    """模拟子进程写出的结果 JSON

    Args:
        tmp_path: 输出目录
        task_id: 任务 ID
        files: 文件明细列表
        failed_urls: 失败 URL 列表

    Returns:
        结果 JSON 路径
    """
    result_file = tmp_path / f"{task_id}.result.json"
    result_file.write_text(
        json.dumps({"status": "completed", "files": files, "failed_urls": failed_urls}, ensure_ascii=False),
        encoding="utf-8",
    )
    return result_file


_FILE_A = {
    "url": "https://example.com/a.pdf",
    "file_path": "downloads/a.pdf",
    "file_name": "a.pdf",
    "file_size": 100,
    "content_type": "application/pdf",
    "file_extension": "pdf",
    "smart_name": "A Report.pdf",
    "naming_strategy": "url_derived",
    "task_id": "",
}


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


class TestStartCrawlSubprocess:
    """start_crawl 子进程派发测试"""

    @patch("plugins.crawler.plugin.subprocess.Popen")
    def test_start_crawl_spawns_task_runner(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """start_crawl 应以子进程运行 task_runner 并落盘任务 JSON"""
        mock_popen.return_value.poll.return_value = None
        plugin = _make_plugin(tmp_path)
        task = CrawlTask(domains=("example.com",), allowed_extensions=("pdf",))

        task_id = plugin.start_crawl(task)

        assert task_id == task.task_id
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert cmd[1:3] == ["-m", "plugins.crawler.task_runner"]
        # 任务 JSON 含 task_id 与绝对化输出目录
        task_file = tmp_path / f"{task.task_id}.task.json"
        payload = json.loads(task_file.read_text(encoding="utf-8"))
        assert payload["task"]["task_id"] == task.task_id
        assert payload["task"]["domains"] == ["example.com"]
        assert payload["settings"]["local_output_dir"] == str(tmp_path.resolve())
        # 状态为 RUNNING
        result = plugin.get_task_status(task.task_id)
        assert result is not None
        assert result.status == CrawlStatus.RUNNING

    @patch("plugins.crawler.plugin.subprocess.Popen")
    def test_refresh_completed_backfills_files_and_cleans_up(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """子进程退出码 0 + 结果 JSON → COMPLETED 且文件明细/失败 URL 回填，临时 JSON 清理"""
        mock_popen.return_value.poll.return_value = None
        plugin = _make_plugin(tmp_path)
        task = CrawlTask(domains=("example.com",))
        plugin.start_crawl(task)
        result_file = _write_result_json(
            tmp_path, task.task_id, [dict(_FILE_A, task_id=task.task_id)], ["https://example.com/b.pdf"]
        )

        # 模拟子进程成功退出
        mock_popen.return_value.poll.return_value = 0
        result = plugin.get_task_status(task.task_id)

        assert result is not None
        assert result.status == CrawlStatus.COMPLETED
        assert len(result.files) == 1
        assert result.files[0].smart_name == "A Report.pdf"
        assert result.total_size_bytes == 100
        assert result.failed_urls == ["https://example.com/b.pdf"]
        assert result.completed_at is not None
        # 临时 JSON 已清理（爬取文件本体不受影响）
        assert not (tmp_path / f"{task.task_id}.task.json").exists()
        assert not result_file.exists()

    @patch("plugins.crawler.plugin.subprocess.Popen")
    def test_refresh_failed_on_nonzero_exit(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """子进程非 0 退出 → FAILED（无结果 JSON 时不回填）"""
        mock_popen.return_value.poll.return_value = None
        plugin = _make_plugin(tmp_path)
        task = CrawlTask(domains=("example.com",))
        plugin.start_crawl(task)

        mock_popen.return_value.poll.return_value = 1
        result = plugin.get_task_status(task.task_id)

        assert result is not None
        assert result.status == CrawlStatus.FAILED
        assert result.files == []
        assert result.completed_at is not None

    @patch("plugins.crawler.plugin.subprocess.Popen")
    def test_refresh_failed_zero_exit_without_result_json(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """退出码 0 但结果 JSON 缺失 → FAILED（结果文件是完成判据的必要条件）"""
        mock_popen.return_value.poll.return_value = None
        plugin = _make_plugin(tmp_path)
        task = CrawlTask(domains=("example.com",))
        plugin.start_crawl(task)

        mock_popen.return_value.poll.return_value = 0
        result = plugin.get_task_status(task.task_id)

        assert result is not None
        assert result.status == CrawlStatus.FAILED

    @patch("plugins.crawler.plugin.subprocess.Popen")
    def test_refresh_failed_nonzero_exit_with_result_json(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """非 0 退出 + 结果 JSON 存在 → FAILED（退出码优先于结果文件，已爬文件仍回填）"""
        mock_popen.return_value.poll.return_value = None
        plugin = _make_plugin(tmp_path)
        task = CrawlTask(domains=("example.com",))
        plugin.start_crawl(task)
        _write_result_json(tmp_path, task.task_id, [dict(_FILE_A, task_id=task.task_id)], [])

        mock_popen.return_value.poll.return_value = 1
        result = plugin.get_task_status(task.task_id)

        assert result is not None
        assert result.status == CrawlStatus.FAILED
        assert len(result.files) == 1

    @patch("plugins.crawler.plugin.subprocess.Popen")
    def test_cancel_terminates_running_process(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """取消 RUNNING 任务应 terminate 子进程"""
        mock_popen.return_value.poll.return_value = None
        plugin = _make_plugin(tmp_path)
        task = CrawlTask(domains=("example.com",))
        plugin.start_crawl(task)

        assert plugin.cancel_task(task.task_id) is True
        mock_popen.return_value.terminate.assert_called_once()
        result = plugin.get_task_status(task.task_id)
        assert result is not None
        assert result.status == CrawlStatus.CANCELLED
        # 任务 JSON 已清理
        assert not (tmp_path / f"{task.task_id}.task.json").exists()

    @patch("plugins.crawler.plugin.subprocess.Popen")
    def test_cancel_completed_task(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """取消已完成的任务应返回 False"""
        mock_popen.return_value.poll.return_value = None
        plugin = _make_plugin(tmp_path)
        plugin.activate(storage=MagicMock(), publisher=MagicMock())
        task = CrawlTask(domains=("example.com",), allowed_extensions=("pdf",))
        plugin.start_crawl(task)

        mock_popen.return_value.poll.return_value = 0
        _write_result_json(tmp_path, task.task_id, [], [])
        plugin.get_task_status(task.task_id)

        assert plugin.cancel_task(task.task_id) is False
