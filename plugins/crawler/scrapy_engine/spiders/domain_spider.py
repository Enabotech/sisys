"""域名爬虫模块

基于域名列表爬取目标网站，提取文件链接和页面链接
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
        use_browser: bool = False,
        auth_storage_state_path: str = "",
    ):
        """初始化域名爬虫

        Args:
            task_id: 任务 ID
            domains: 目标域名元组
            seed_urls: 种子 URL 元组
            allowed_extensions: 允许的文件扩展名
            max_depth: 最大爬取深度
            follow_subdomains: 是否跟踪子域名
            use_browser: 是否启用 Playwright 浏览器模式
            auth_storage_state_path: Playwright storageState JSON 文件路径
        """
        super().__init__()
        self.task_id = task_id
        self.domains = domains
        self.seed_urls = seed_urls
        self.allowed_extensions = set(ext.lower().lstrip(".") for ext in allowed_extensions)
        self.max_depth = max_depth
        self.follow_subdomains = follow_subdomains
        self.use_browser = use_browser
        self._cookies_by_domain = self._load_cookies(auth_storage_state_path) if auth_storage_state_path else {}

    _FILE_DOWNLOAD_TIMEOUT = 300  # 文件下载超时（秒），大文件需更长时间

    async def start(self):
        """生成初始请求（Scrapy 2.16+ async start API）"""
        urls = self.seed_urls if self.seed_urls else tuple(f"https://{d}" for d in self.domains)
        for url in urls:
            meta = {"depth": 0, "page_title": "", "parent_url": ""}
            if self.use_browser:
                meta["playwright"] = True
                meta["playwright_page_goto_kwargs"] = {"wait_until": "domcontentloaded"}
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta=meta,
            )

    def parse(self, response):
        """解析页面，提取文件链接和页面链接

        Args:
            response: Scrapy 响应对象
        """
        if not isinstance(response, scrapy.http.TextResponse):
            return

        page_title = response.css("title::text").get("").strip()
        current_depth = response.meta.get("depth", 0)

        for link in response.css("a[href]"):
            href = link.attrib.get("href", "")
            link_text = link.css("::text").get("").strip()

            if not href:
                continue

            url = response.urljoin(href)

            # 跳过非 HTTP(S) 协议（mailto:、tel:、javascript: 等）
            parsed_href = urlparse(url)
            if parsed_href.scheme and parsed_href.scheme not in ("http", "https"):
                continue

            if self._is_target_file(url):
                file_meta = {
                    "parent_url": response.url,
                    "page_title": page_title,
                    "link_text": link_text,
                    "depth": current_depth,
                    "download_timeout": self._FILE_DOWNLOAD_TIMEOUT,
                }
                if self.use_browser:
                    file_meta["playwright"] = True
                    file_meta["playwright_include_page"] = True
                    file_meta["playwright_page_goto_kwargs"] = {
                        "referer": response.url,
                        "timeout": self._FILE_DOWNLOAD_TIMEOUT * 1000,
                    }
                yield scrapy.Request(
                    url=url,
                    callback=self.parse_file,
                    meta=file_meta,
                    cookies=self._get_cookies_for_url(url),
                    headers={"Referer": response.url},
                )
            elif self._should_follow(url, current_depth):
                meta = {
                    "depth": current_depth + 1,
                    "page_title": "",
                    "parent_url": response.url,
                }
                if self.use_browser:
                    meta["playwright"] = True
                    meta["playwright_page_goto_kwargs"] = {"wait_until": "domcontentloaded"}
                yield scrapy.Request(
                    url=url,
                    callback=self.parse,
                    meta=meta,
                )

    async def parse_file(self, response):
        """处理文件下载响应

        浏览器模式下，scrapy-playwright 对非 Content-Disposition 响应使用
        page.content() 返回 DOM HTML（非原始二进制），需通过 APIRequestContext
        重下载获取完整文件内容。

        Args:
            response: Scrapy 响应对象
        """
        import os
        import tempfile

        body = response.body
        content_type = response.headers.get("Content-Type", b"").decode("utf-8", errors="replace").split(";")[0].strip()
        page = response.meta.get("playwright_page")

        if page and body[:1] == b"<":
            # scrapy-playwright 返回了 DOM HTML（page.content()），非二进制数据
            # 通过 APIRequestContext 重下载：同 TLS 指纹 + 同 cookies，返回原始二进制
            api_response = await page.context.request.get(
                response.url,
                headers={"Referer": response.meta.get("parent_url", "")},
            )
            body = await api_response.body()
            content_type = api_response.headers.get("content-type", content_type).split(";")[0].strip()

        if page:
            await page.close()

        url_filename = self._extract_filename_from_url(response.url)
        extension = os.path.splitext(url_filename)[1].lower().lstrip(".")

        tmp_dir = os.path.join(tempfile.gettempdir(), "crawler")
        os.makedirs(tmp_dir, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(suffix=f".{extension}" if extension else "", dir=tmp_dir)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(body)
        except Exception:
            os.close(fd)
            raise

        item = CrawledFileItem()
        item["url"] = response.url
        item["file_path"] = temp_path
        item["file_name"] = url_filename
        item["file_size"] = len(body)
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

    _NON_PAGE_EXTENSIONS = frozenset(
        {
            "mp4",
            "mp3",
            "avi",
            "mov",
            "wmv",
            "flv",
            "mkv",
            "webm",
            "m4v",
            "3gp",
            "wav",
            "ogg",
            "flac",
            "aac",
            "wma",
            "m4a",
            "pdf",
            "doc",
            "docx",
            "xls",
            "xlsx",
            "ppt",
            "pptx",
            "zip",
            "rar",
            "7z",
            "tar",
            "gz",
            "bz2",
            "exe",
            "dmg",
            "iso",
            "png",
            "jpg",
            "jpeg",
            "gif",
            "svg",
            "webp",
            "ico",
            "bmp",
            "css",
            "js",
            "woff",
            "woff2",
            "ttf",
            "eot",
            "json",
            "ipynb",
        }
    )

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
        path = parsed.path.lower()
        ext = path.rsplit(".", 1)[-1] if "." in path else ""
        if ext in self._NON_PAGE_EXTENSIONS:
            return False

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

    @staticmethod
    def _load_cookies(auth_storage_state_path: str) -> dict[str, dict[str, str]]:
        """从 Playwright storageState 文件加载 cookies

        Args:
            auth_storage_state_path: storageState JSON 文件路径

        Returns:
            域名到 cookie 键值对的映射
        """
        import json

        with open(auth_storage_state_path) as f:
            state = json.load(f)

        cookies_by_domain: dict[str, dict[str, str]] = {}
        for cookie in state.get("cookies", []):
            domain = cookie.get("domain", "").lstrip(".")
            if domain not in cookies_by_domain:
                cookies_by_domain[domain] = {}
            cookies_by_domain[domain][cookie["name"]] = cookie["value"]
        return cookies_by_domain

    def _get_cookies_for_url(self, url: str) -> dict[str, str]:
        """获取 URL 匹配域名的认证 cookies

        Args:
            url: 目标 URL

        Returns:
            cookie 键值对
        """
        host = urlparse(url).hostname or ""
        cookies: dict[str, str] = {}
        for domain, domain_cookies in self._cookies_by_domain.items():
            if host == domain or host.endswith(f".{domain}"):
                cookies.update(domain_cookies)
        return cookies
