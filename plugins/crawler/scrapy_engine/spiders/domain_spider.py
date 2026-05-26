"""域名爬虫模块

基于域名列表爬取目标网站，提取文件链接和页面链接

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import scrapy

from plugins.crawler.scrapy_engine.items import CrawledFileItem

logger = logging.getLogger(__name__)


class DomainSpider(scrapy.Spider):
    """域名爬虫

    根据配置的域名列表和种子 URL 爬取目标站点，
    提取文件链接下载，跟踪页面链接继续爬取

    Attributes:
        task_id: 任务 ID
        domains: 目标域名元组
        allowed_extensions: 允许的文件扩展名集合
        max_depth: 最大递归深度
        follow_subdomains: 是否跟踪子域名
    """

    name = "domain"

    def __init__(
        self,
        task_id: str = "",
        domains: tuple[str, ...] = (),
        seed_urls: tuple[str, ...] = (),
        allowed_extensions: tuple[str, ...] = (),
        max_depth: int = 3,
        follow_subdomains: bool = True,
    ):
        """初始化域名爬虫

        Args:
            task_id: 任务 ID
            domains: 目标域名元组
            seed_urls: 种子 URL 元组
            allowed_extensions: 允许的文件扩展名
            max_depth: 最大爬取深度
            follow_subdomains: 是否跟踪子域名
        """
        super().__init__()
        self.task_id = task_id
        self.domains = domains
        self.seed_urls = seed_urls
        self.allowed_extensions = set(ext.lower().lstrip(".") for ext in allowed_extensions)
        self.max_depth = max_depth
        self.follow_subdomains = follow_subdomains

    def start_requests(self):
        """生成初始请求"""
        urls = self.seed_urls if self.seed_urls else tuple(f"https://{d}" for d in self.domains)
        for url in urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={"depth": 0, "page_title": "", "parent_url": ""},
            )

    def parse(self, response):
        """解析页面，提取文件链接和页面链接

        Args:
            response: Scrapy 响应对象
        """
        page_title = response.css("title::text").get("").strip()
        current_depth = response.meta.get("depth", 0)

        for link in response.css("a[href]"):
            href = link.attrib.get("href", "")
            link_text = link.css("::text").get("").strip()

            if not href:
                continue

            url = response.urljoin(href)

            if self._is_target_file(url):
                yield scrapy.Request(
                    url=url,
                    callback=self.parse_file,
                    meta={
                        "parent_url": response.url,
                        "page_title": page_title,
                        "link_text": link_text,
                        "depth": current_depth,
                    },
                )
            elif self._should_follow(url, current_depth):
                yield scrapy.Request(
                    url=url,
                    callback=self.parse,
                    meta={
                        "depth": current_depth + 1,
                        "page_title": "",
                        "parent_url": response.url,
                    },
                )

    def parse_file(self, response):
        """处理文件下载响应

        Args:
            response: Scrapy 响应对象
        """
        import os
        import tempfile

        content_type = response.headers.get("Content-Type", b"").decode("utf-8", errors="replace").split(";")[0].strip()

        url_filename = self._extract_filename_from_url(response.url)
        extension = os.path.splitext(url_filename)[1].lower().lstrip(".")

        fd, temp_path = tempfile.mkstemp(suffix=f".{extension}" if extension else "")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(response.body)
        except Exception:
            os.close(fd)
            raise

        item = CrawledFileItem()
        item["url"] = response.url
        item["file_path"] = temp_path
        item["file_name"] = url_filename
        item["file_size"] = len(response.body)
        item["content_type"] = content_type
        item["file_extension"] = extension
        item["parent_url"] = response.meta.get("parent_url", "")
        item["page_title"] = response.meta.get("page_title", "")
        item["link_text"] = response.meta.get("link_text", "")
        item["depth"] = response.meta.get("depth", 0)
        item["task_id"] = self.task_id
        yield item

    def _is_target_file(self, url: str) -> bool:
        """判断 URL 是否为目标文件

        Args:
            url: 待判断的 URL

        Returns:
            是否为目标文件
        """
        if not self.allowed_extensions:
            return False

        path = urlparse(url).path.lower()
        ext = path.rsplit(".", 1)[-1] if "." in path else ""
        return ext in self.allowed_extensions

    def _should_follow(self, url: str, current_depth: int) -> bool:
        """判断是否应该跟踪该 URL

        Args:
            url: 待判断的 URL
            current_depth: 当前爬取深度

        Returns:
            是否应该跟踪
        """
        if current_depth >= self.max_depth:
            return False

        parsed = urlparse(url)
        host = parsed.hostname or ""

        if not self.follow_subdomains:
            return host in self.domains

        domain_set = set(self.domains)
        return host in domain_set or any(host.endswith(f".{d}") for d in domain_set)

    @staticmethod
    def _extract_filename_from_url(url: str) -> str:
        """从 URL 提取文件名

        Args:
            url: 文件 URL

        Returns:
            提取的文件名
        """
        path = urlparse(url).path
        return path.rsplit("/", 1)[-1] if "/" in path else path
