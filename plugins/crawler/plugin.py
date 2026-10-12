"""Crawler 插件主类模块

管理爬虫生命周期：安装、激活、启动、查询、取消

爬取任务以独立子进程执行（task_runner）：CrawlerProcess 必须运行在
进程主线程（signal handler 安装 + Twisted reactor 进程级单例的契约），
在服务进程的后台线程内运行会导致事件循环冲突与 signal 安装失败。
"""

from __future__ import annotations

import dataclasses
import json
import logging
import subprocess
import sys
from pathlib import Path

from plugins.crawler.config.settings import CrawlerSettings
from plugins.crawler.core.entities import CrawledFile, CrawlResult, CrawlTask
from plugins.crawler.core.format.registry import FileFormatHandlerRegistry
from plugins.crawler.core.naming.engine import SmartNamingEngine
from plugins.crawler.core.naming.metadata_extractor import MetadataExtractor
from plugins.crawler.core.value_objects import CrawlStatus
from plugins.crawler.messaging.base import EventPublisher
from plugins.crawler.storage.base import StoragePort

logger = logging.getLogger(__name__)

# 仓库根目录（plugins/ 的父目录）——子进程 cwd，保证 plugins 包可导入
_REPO_ROOT = Path(__file__).resolve().parents[2]


class CrawlerPlugin:
    """Crawler 插件主类 — 管理爬虫生命周期

    Attributes:
        _settings: 全局配置
        _format_registry: 文件格式注册表
        _naming_engine: 智能命名引擎
        _metadata_extractor: 元数据提取器
        _storage: 存储端口
        _publisher: 事件发布端口
        _tasks: 任务状态字典
        _task_processes: 任务子进程句柄字典
    """

    def __init__(self, settings: CrawlerSettings | None = None):
        """初始化 Crawler 插件

        Args:
            settings: 爬虫配置，为 None 时使用默认值
        """
        self._settings = settings or CrawlerSettings()
        self._format_registry = FileFormatHandlerRegistry()
        self._naming_engine = SmartNamingEngine(
            max_length=self._settings.max_filename_length,
            conflict_strategy=self._settings.filename_conflict_strategy,
        )
        self._metadata_extractor = MetadataExtractor(self._format_registry)
        self._storage: StoragePort | None = None
        self._publisher: EventPublisher | None = None
        self._tasks: dict[str, CrawlResult] = {}
        self._task_processes: dict[str, subprocess.Popen] = {}

    def install(self) -> None:
        """安装插件 — 注册默认格式处理器"""
        self._format_registry.register_default_handlers()
        logger.info("Crawler 插件已安装")

    def activate(self, storage: StoragePort, publisher: EventPublisher) -> None:
        """激活插件 — 注入存储和事件发布端口

        Args:
            storage: 存储端口实现
            publisher: 事件发布端口实现
        """
        self._storage = storage
        self._publisher = publisher
        logger.info("Crawler 插件已激活")

    def _task_dir(self) -> Path:
        """任务工作目录（输出目录的绝对路径，兼作任务/结果 JSON 落盘位置）

        Returns:
            输出目录 Path（不存在时自动创建）
        """
        output_dir = Path(self._settings.local_output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def start_crawl(self, task: CrawlTask) -> str:
        """启动爬取任务 — 派发子进程执行

        Args:
            task: 爬取任务实体

        Returns:
            任务 ID
        """
        result = CrawlResult(task_id=task.task_id)
        result.mark_running()
        self._tasks[task.task_id] = result

        # 任务级配置覆盖（全局默认 + 任务参数合并），与子进程共享同一份 JSON
        settings = CrawlerSettings(
            respect_robots_txt=self._settings.respect_robots_txt,
            max_concurrent_requests=self._settings.max_concurrent_requests,
            download_delay=task.download_delay,
            download_timeout=self._settings.download_timeout,
            use_browser=task.use_browser,
            browser_timeout=self._settings.browser_timeout,
            browser_headless=self._settings.browser_headless,
            browser_proxy=self._settings.browser_proxy,
            auth_storage_state_path=task.auth_storage_state_path,
            auth_headers=task.auth_headers,
            local_output_dir=str(self._task_dir()),
        )

        task_dir = self._task_dir()
        task_file = task_dir / f"{task.task_id}.task.json"
        result_file = task_dir / f"{task.task_id}.result.json"
        task_file.write_text(
            json.dumps(
                {"task": task.to_request_dict(), "settings": dataclasses.asdict(settings)},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        cmd = [sys.executable, "-m", "plugins.crawler.task_runner", str(task_file), str(result_file)]
        self._task_processes[task.task_id] = subprocess.Popen(cmd, cwd=str(_REPO_ROOT), start_new_session=True)

        logger.info("爬取任务子进程已启动: %s", task.task_id)
        return task.task_id

    def get_task_status(self, task_id: str) -> CrawlResult | None:
        """查询任务状态（先同步子进程退出状态与结果文件）

        Args:
            task_id: 任务 ID

        Returns:
            爬取结果，不存在时返回 None
        """
        self._refresh_status(task_id)
        return self._tasks.get(task_id)

    def _refresh_status(self, task_id: str) -> None:
        """轮询子进程退出状态，读取结果 JSON 回填统计

        RUNNING 状态的任务在子进程退出后转入终态：
        - 退出码 0 且结果 JSON 存在 → COMPLETED（回填文件明细/失败 URL）
        - 其余情形 → FAILED（若结果 JSON 存在仍回填已爬取部分）

        Args:
            task_id: 任务 ID
        """
        result = self._tasks.get(task_id)
        process = self._task_processes.get(task_id)
        if result is None or process is None:
            return
        if result.status != CrawlStatus.RUNNING:
            self._task_processes.pop(task_id, None)
            return

        returncode = process.poll()
        if returncode is None:
            return

        result_file = self._task_dir() / f"{task_id}.result.json"
        if result_file.exists():
            payload = json.loads(result_file.read_text(encoding="utf-8"))
            for file_fields in payload.get("files", []):
                result.add_file(CrawledFile(**file_fields))
            for url in payload.get("failed_urls", []):
                result.add_failed_url(url)

        if returncode == 0 and result_file.exists():
            result.mark_completed()
        else:
            result.mark_failed()

        self._cleanup_task_files(task_id)
        self._task_processes.pop(task_id, None)

    def _cleanup_task_files(self, task_id: str) -> None:
        """删除任务/结果临时 JSON（爬取的文件本体保留在输出目录）

        Args:
            task_id: 任务 ID
        """
        task_dir = Path(self._settings.local_output_dir).resolve()
        for name in (f"{task_id}.task.json", f"{task_id}.result.json"):
            (task_dir / name).unlink(missing_ok=True)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务 — 终止子进程并标记取消

        Args:
            task_id: 任务 ID

        Returns:
            是否成功取消
        """
        result = self._tasks.get(task_id)
        if result is None:
            return False

        if result.status in (CrawlStatus.COMPLETED, CrawlStatus.FAILED, CrawlStatus.CANCELLED):
            return False

        process = self._task_processes.pop(task_id, None)
        if process is not None and process.poll() is None:
            process.terminate()

        result.mark_cancelled()
        self._cleanup_task_files(task_id)
        logger.info("任务已取消: %s", task_id)
        return True

    def list_tasks(self) -> list[CrawlResult]:
        """列出所有任务

        Returns:
            所有爬取结果列表
        """
        return list(self._tasks.values())

    def list_supported_formats(self) -> list[str]:
        """列出支持的文件格式

        Returns:
            排序后的扩展名列表
        """
        return self._format_registry.supported_extensions_list()
