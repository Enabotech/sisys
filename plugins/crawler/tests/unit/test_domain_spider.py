"""Domain Spider 单元测试

验证 DomainSpider 的链接判断、深度控制、浏览器模式和认证 cookies 注入
"""

from __future__ import annotations

import asyncio
import json
import tempfile

import scrapy

from plugins.crawler.scrapy_engine.spiders.domain_spider import DomainSpider


class TestDomainSpider:
    """DomainSpider 测试"""

    def test_init_default_values(self) -> None:
        """初始化应使用默认值"""
        spider = DomainSpider(task_id="test-1", domains=("example.com",))

        assert spider.task_id == "test-1"
        assert spider.domains == ("example.com",)
        assert spider.max_depth == 3
        assert spider.follow_subdomains is True
        assert spider.allowed_extensions == set()
        assert spider.use_browser is False

    def test_init_custom_values(self) -> None:
        """初始化应接受自定义值"""
        spider = DomainSpider(
            task_id="test-2",
            domains=("test.com",),
            max_depth=5,
            follow_subdomains=False,
            allowed_extensions=("pdf", "docx"),
            use_browser=True,
        )

        assert spider.max_depth == 5
        assert spider.follow_subdomains is False
        assert spider.allowed_extensions == {"pdf", "docx"}
        assert spider.use_browser is True

    def test_is_target_file_with_allowed_extension(self) -> None:
        """允许的扩展名应返回 True"""
        spider = DomainSpider(
            task_id="test",
            domains=("example.com",),
            allowed_extensions=("pdf", "docx"),
        )

        assert spider._is_target_file("https://example.com/docs/report.pdf") is True
        assert spider._is_target_file("https://example.com/docs/report.DOCX") is True

    def test_is_target_file_with_disallowed_extension(self) -> None:
        """不允许的扩展名应返回 False"""
        spider = DomainSpider(
            task_id="test",
            domains=("example.com",),
            allowed_extensions=("pdf",),
        )

        assert spider._is_target_file("https://example.com/docs/report.docx") is False
        assert spider._is_target_file("https://example.com/page.html") is False

    def test_is_target_file_without_extension(self) -> None:
        """无扩展名的 URL 应返回 False"""
        spider = DomainSpider(
            task_id="test",
            domains=("example.com",),
            allowed_extensions=("pdf",),
        )

        assert spider._is_target_file("https://example.com/docs/") is False

    def test_is_target_file_without_allowed_extensions(self) -> None:
        """未配置允许扩展名时应返回 False"""
        spider = DomainSpider(task_id="test", domains=("example.com",))

        assert spider._is_target_file("https://example.com/docs/report.pdf") is False

    def test_should_follow_within_max_depth(self) -> None:
        """深度小于最大值时应返回 True"""
        spider = DomainSpider(task_id="test", domains=("example.com",), max_depth=3)

        assert spider._should_follow("https://example.com/page2", 0) is True
        assert spider._should_follow("https://example.com/page2", 2) is True

    def test_should_follow_at_max_depth(self) -> None:
        """达到最大深度时应返回 False"""
        spider = DomainSpider(task_id="test", domains=("example.com",), max_depth=3)

        assert spider._should_follow("https://example.com/page2", 3) is False

    def test_should_follow_same_domain(self) -> None:
        """同一域名应返回 True"""
        spider = DomainSpider(task_id="test", domains=("example.com",), follow_subdomains=False)

        assert spider._should_follow("https://example.com/page", 0) is True

    def test_should_follow_different_domain(self) -> None:
        """不同域名应返回 False"""
        spider = DomainSpider(task_id="test", domains=("example.com",), follow_subdomains=False)

        assert spider._should_follow("https://other.com/page", 0) is False

    def test_should_follow_subdomain_enabled(self) -> None:
        """启用子域名跟踪时子域名应返回 True"""
        spider = DomainSpider(task_id="test", domains=("example.com",), follow_subdomains=True)

        assert spider._should_follow("https://docs.example.com/page", 0) is True
        assert spider._should_follow("https://blog.example.com/page", 0) is True

    def test_should_follow_subdomain_disabled(self) -> None:
        """禁用子域名跟踪时子域名应返回 False"""
        spider = DomainSpider(task_id="test", domains=("example.com",), follow_subdomains=False)

        assert spider._should_follow("https://docs.example.com/page", 0) is False

    def test_extract_filename_from_url(self) -> None:
        """应正确提取文件名"""
        assert DomainSpider._extract_filename_from_url("https://example.com/docs/report.pdf") == "report.pdf"
        assert DomainSpider._extract_filename_from_url("https://example.com/file.tar.gz") == "file.tar.gz"
        assert DomainSpider._extract_filename_from_url("https://example.com/") == ""

    def test_parse_skips_non_http_schemes(self) -> None:
        """应跳过 mailto:、tel:、javascript: 等非 HTTP(S) 协议链接"""
        spider = DomainSpider(
            task_id="test",
            domains=("example.com",),
            allowed_extensions=("pdf",),
            max_depth=2,
        )
        html = (
            "<html><body>"
            '<a href="mailto:test@example.com">email</a>'
            '<a href="tel:+123456">phone</a>'
            '<a href="/doc.pdf">file</a>'
            "</body></html>"
        )
        response = _make_text_response("https://example.com/", html, meta={"depth": 0})
        requests = list(spider.parse(response))
        urls = [r.url for r in requests]
        assert "mailto:test@example.com" not in urls
        assert "tel:+123456" not in urls
        assert "https://example.com/doc.pdf" in urls

    def test_parse_file_has_download_timeout(self) -> None:
        """文件下载请求应使用独立的下载超时"""
        spider = DomainSpider(
            task_id="test",
            domains=("example.com",),
            allowed_extensions=("pdf",),
        )
        html = '<html><body><a href="/doc.pdf">PDF</a></body></html>'
        response = _make_text_response("https://example.com/", html, meta={"depth": 0})
        requests = list(spider.parse(response))
        file_requests = [r for r in requests if r.callback.__name__ == "parse_file"]
        assert len(file_requests) == 1
        assert file_requests[0].meta.get("download_timeout") == 300


def _collect_start_requests(spider: DomainSpider) -> list:
    """收集 async start() 方法的全部请求"""
    return asyncio.get_event_loop().run_until_complete(_alist(spider.start()))


async def _alist(async_gen):
    """将 async generator 转为 list"""
    result = []
    async for item in async_gen:
        result.append(item)
    return result


def _make_text_response(
    url: str,
    body: str = "<html><body></body></html>",
    meta: dict | None = None,
) -> scrapy.http.TextResponse:
    """构造 TextResponse 测试对象"""
    request = scrapy.Request(url=url, meta=meta or {})
    return scrapy.http.TextResponse(url=url, body=body.encode(), request=request)


class TestDomainSpiderBrowserMode:
    """DomainSpider 浏览器模式测试"""

    def test_use_browser_false_no_playwright_meta(self) -> None:
        """use_browser=False 时初始请求不应包含 playwright meta"""
        spider = DomainSpider(domains=("example.com",), use_browser=False)
        requests = _collect_start_requests(spider)
        assert len(requests) == 1
        assert "playwright" not in requests[0].meta

    def test_use_browser_true_has_playwright_meta(self) -> None:
        """use_browser=True 时初始请求应包含 playwright meta 和 domcontentloaded"""
        spider = DomainSpider(domains=("example.com",), use_browser=True)
        requests = _collect_start_requests(spider)
        assert len(requests) == 1
        assert requests[0].meta.get("playwright") is True
        assert requests[0].meta.get("playwright_page_goto_kwargs") == {"wait_until": "domcontentloaded"}

    def test_parse_page_link_browser_mode(self) -> None:
        """浏览器模式下页面链接应包含 playwright meta 和 domcontentloaded"""
        spider = DomainSpider(domains=("example.com",), use_browser=True, max_depth=2)
        html = '<html><head><title>Test</title></head><body><a href="/page">link</a></body></html>'
        response = _make_text_response("https://example.com/", html, meta={"depth": 0})
        requests = list(spider.parse(response))
        page_requests = [r for r in requests if r.callback.__name__ == "parse"]
        assert len(page_requests) == 1
        assert page_requests[0].meta.get("playwright") is True
        assert page_requests[0].meta.get("playwright_page_goto_kwargs") == {"wait_until": "domcontentloaded"}

    def test_parse_file_link_browser_mode(self) -> None:
        """浏览器模式下文件链接应走标准 HTTP（无 playwright meta），携带认证 cookies"""
        import os

        # 创建临时 storageState 文件
        storage_state = {
            "cookies": [
                {"name": "session", "value": "abc123", "domain": ".example.com"},
            ]
        }
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(storage_state, f)

            spider = DomainSpider(
                domains=("example.com",),
                use_browser=True,
                allowed_extensions=("pdf",),
                storage_state_path=path,
            )
            html = '<html><head><title>Test</title></head><body><a href="/doc.pdf">PDF</a></body></html>'
            response = _make_text_response("https://example.com/", html, meta={"depth": 0})
            requests = list(spider.parse(response))
            file_requests = [r for r in requests if r.callback.__name__ == "parse_file"]
            assert len(file_requests) == 1
            # 文件下载不使用 Playwright（避免二进制文件 page.goto 问题）
            assert "playwright" not in file_requests[0].meta
            # 应携带认证 cookies
            assert file_requests[0].cookies.get("session") == "abc123"
        finally:
            os.unlink(path)

    def test_parse_file_link_no_browser(self) -> None:
        """非浏览器模式下文件链接不应包含 playwright meta，无 cookies"""
        spider = DomainSpider(
            domains=("example.com",),
            use_browser=False,
            allowed_extensions=("pdf",),
        )
        html = '<html><head><title>Test</title></head><body><a href="/doc.pdf">PDF</a></body></html>'
        response = _make_text_response("https://example.com/", html, meta={"depth": 0})
        requests = list(spider.parse(response))
        file_requests = [r for r in requests if r.callback.__name__ == "parse_file"]
        assert len(file_requests) == 1
        assert "playwright" not in file_requests[0].meta
        assert len(file_requests[0].cookies) == 0

    def test_parse_page_link_no_browser(self) -> None:
        """非浏览器模式下页面链接不应包含 playwright meta"""
        spider = DomainSpider(domains=("example.com",), use_browser=False, max_depth=2)
        html = '<html><head><title>Test</title></head><body><a href="/page">link</a></body></html>'
        response = _make_text_response("https://example.com/", html, meta={"depth": 0})
        requests = list(spider.parse(response))
        page_requests = [r for r in requests if r.callback.__name__ == "parse"]
        assert len(page_requests) == 1
        assert "playwright" not in page_requests[0].meta


class TestDomainSpiderCookies:
    """DomainSpider 认证 cookies 测试"""

    def test_load_cookies_from_storage_state(self) -> None:
        """应正确从 storageState 文件加载 cookies"""
        import os

        storage_state = {
            "cookies": [
                {"name": "sessionid", "value": "abc123", "domain": ".example.com"},
                {"name": "token", "value": "xyz789", "domain": "api.example.com"},
            ]
        }
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(storage_state, f)

            cookies_by_domain = DomainSpider._load_cookies(path)
            assert "example.com" in cookies_by_domain
            assert cookies_by_domain["example.com"]["sessionid"] == "abc123"
            assert "api.example.com" in cookies_by_domain
            assert cookies_by_domain["api.example.com"]["token"] == "xyz789"
        finally:
            os.unlink(path)

    def test_get_cookies_for_url_exact_domain(self) -> None:
        """精确域名匹配应返回对应 cookies"""
        spider = DomainSpider(domains=("example.com",))
        spider._cookies_by_domain = {"example.com": {"session": "test123"}}

        cookies = spider._get_cookies_for_url("https://example.com/doc.pdf")
        assert cookies.get("session") == "test123"

    def test_get_cookies_for_url_subdomain(self) -> None:
        """子域名应匹配父域名的 cookies"""
        spider = DomainSpider(domains=("example.com",))
        spider._cookies_by_domain = {"example.com": {"session": "test123"}}

        cookies = spider._get_cookies_for_url("https://api.example.com/doc.pdf")
        assert cookies.get("session") == "test123"

    def test_get_cookies_for_url_no_match(self) -> None:
        """不匹配域名应返回空 cookies"""
        spider = DomainSpider(domains=("example.com",))
        spider._cookies_by_domain = {"other.com": {"session": "test123"}}

        cookies = spider._get_cookies_for_url("https://example.com/doc.pdf")
        assert len(cookies) == 0

    def test_init_without_storage_state_path(self) -> None:
        """无 storageState 路径时 cookies 应为空"""
        spider = DomainSpider(domains=("example.com",), use_browser=True)
        assert spider._cookies_by_domain == {}
