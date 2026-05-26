"""Domain Spider 单元测试

验证 DomainSpider 的链接判断和深度控制

"""

from __future__ import annotations

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

    def test_init_custom_values(self) -> None:
        """初始化应接受自定义值"""
        spider = DomainSpider(
            task_id="test-2",
            domains=("test.com",),
            max_depth=5,
            follow_subdomains=False,
            allowed_extensions=("pdf", "docx"),
        )

        assert spider.max_depth == 5
        assert spider.follow_subdomains is False
        assert spider.allowed_extensions == {"pdf", "docx"}

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
