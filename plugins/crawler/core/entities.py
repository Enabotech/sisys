"""Crawler 插件实体模块

定义爬虫核心实体：CrawlTask（任务）、CrawledFile（爬取文件）、CrawlResult（结果）
零外部依赖，仅使用标准库

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from plugins.crawler.core.value_objects import CrawlStatus


@dataclass(frozen=True)
class CrawlTask:
    """爬取任务实体（不可变）

    Attributes:
        task_id: 任务唯一标识
        domains: 目标域名元组
        seed_urls: 种子 URL 元组
        max_depth: 最大递归深度
        allowed_extensions: 允许的文件扩展名元组
        follow_subdomains: 是否跟踪子域名
        max_files: 单任务最大文件数
        max_file_size_mb: 单文件大小上限（MB）
        download_delay: 请求间隔（秒）
        url_include: URL 包含模式元组
        url_exclude: URL 排除模式元组
    """

    task_id: str = field(default_factory=lambda: str(uuid4()))
    domains: tuple[str, ...] = ()
    seed_urls: tuple[str, ...] = ()
    max_depth: int = 3
    allowed_extensions: tuple[str, ...] = ()
    follow_subdomains: bool = True
    max_files: int = 1000
    max_file_size_mb: int = 2048
    download_delay: float = 1.0
    url_include: tuple[str, ...] = ()
    url_exclude: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict) -> CrawlTask:
        """从字典创建 CrawlTask

        Args:
            data: 包含任务参数的字典

        Returns:
            CrawlTask 实例
        """
        domains = tuple(data.get("domains", []))
        seed_urls = tuple(data.get("seed_urls", []))
        allowed_extensions = tuple(data.get("allowed_extensions", []))
        url_include = tuple(data.get("url_patterns", {}).get("include", []))
        url_exclude = tuple(data.get("url_patterns", {}).get("exclude", []))
        return cls(
            domains=domains,
            seed_urls=seed_urls,
            max_depth=data.get("max_depth", 3),
            allowed_extensions=allowed_extensions,
            follow_subdomains=data.get("follow_subdomains", True),
            max_files=data.get("max_files", 1000),
            max_file_size_mb=data.get("max_file_size_mb", 2048),
            download_delay=data.get("download_delay", 1.0),
            url_include=url_include,
            url_exclude=url_exclude,
        )


@dataclass(frozen=True)
class CrawledFile:
    """爬取到的文件实体（不可变）

    Attributes:
        url: 原始下载 URL
        file_path: 本地临时路径
        file_name: 原始文件名
        file_size: 文件大小（字节）
        content_type: MIME 类型
        file_extension: 文件扩展名
        smart_name: 智能命名结果
        naming_strategy: 使用的命名策略名
        task_id: 所属任务 ID
        parent_url: 来源页面 URL
        page_title: 来源页面标题
        link_text: 链接锚文本
        depth: 爬取深度
        metadata_title: 文件元数据中的标题
        metadata_author: 文件元数据中的作者
    """

    url: str
    file_path: str
    file_name: str
    file_size: int
    content_type: str
    file_extension: str
    smart_name: str
    naming_strategy: str
    task_id: str
    parent_url: str = ""
    page_title: str = ""
    link_text: str = ""
    depth: int = 0
    metadata_title: str = ""
    metadata_author: str = ""


@dataclass
class CrawlResult:
    """爬取结果（可变，用于汇总统计）

    Attributes:
        task_id: 任务 ID
        status: 任务状态
        files: 已爬取文件列表
        failed_urls: 失败 URL 列表
        started_at: 开始时间
        completed_at: 完成时间
        total_size_bytes: 总文件大小（字节）
    """

    task_id: str
    status: CrawlStatus = CrawlStatus.PENDING
    files: list[CrawledFile] = field(default_factory=list)
    failed_urls: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_size_bytes: int = 0

    def add_file(self, file: CrawledFile) -> None:
        """添加已爬取文件

        Args:
            file: 爬取到的文件实体
        """
        self.files.append(file)
        self.total_size_bytes += file.file_size

    def add_failed_url(self, url: str) -> None:
        """添加失败 URL

        Args:
            url: 失败的 URL
        """
        self.failed_urls.append(url)

    def mark_running(self) -> None:
        """标记任务开始运行"""
        self.status = CrawlStatus.RUNNING
        self.started_at = datetime.now()

    def mark_completed(self) -> None:
        """标记任务完成"""
        self.status = CrawlStatus.COMPLETED
        self.completed_at = datetime.now()

    def mark_failed(self) -> None:
        """标记任务失败"""
        self.status = CrawlStatus.FAILED
        self.completed_at = datetime.now()

    def mark_cancelled(self) -> None:
        """标记任务取消"""
        self.status = CrawlStatus.CANCELLED
        self.completed_at = datetime.now()

    def to_dict(self) -> dict:
        """转换为字典（用于 API 响应）"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "files_crawled": len(self.files),
            "files_failed": len(self.failed_urls),
            "total_size_bytes": self.total_size_bytes,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
