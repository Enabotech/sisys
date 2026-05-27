"""CrawlerSettings 配置单元测试

TDD 阶段：绿
验证默认值和环境变量覆盖

"""

from __future__ import annotations

import os
import tempfile

from plugins.crawler.config.settings import CrawlerSettings


class TestCrawlerSettings:
    """CrawlerSettings 配置测试"""

    def test_default_values(self) -> None:
        """默认配置值应正确"""
        settings = CrawlerSettings()
        assert settings.host == ""
        assert settings.port == 8900
        assert settings.max_depth == 3
        assert settings.max_concurrent_requests == 8
        assert settings.download_delay == 1.0
        assert settings.respect_robots_txt is True
        assert settings.max_filename_length == 200
        assert settings.filename_conflict_strategy == "append_hash"
        assert settings.storage_backend == "minio"
        assert "pdf" in settings.allowed_extensions
        assert "docx" in settings.allowed_extensions

    def test_from_env_defaults(self) -> None:
        """from_env 无环境变量时应返回默认值"""
        settings = CrawlerSettings.from_env()
        assert settings.port == 8900
        assert settings.max_depth == 3

    def test_from_env_override(self) -> None:
        """from_env 应读取 CRAWLER_ 前缀的环境变量"""
        os.environ["CRAWLER_PORT"] = "9999"
        os.environ["CRAWLER_MAX_DEPTH"] = "5"
        os.environ["CRAWLER_RESPECT_ROBOTS_TXT"] = "false"
        try:
            settings = CrawlerSettings.from_env()
            assert settings.port == 9999
            assert settings.max_depth == 5
            assert settings.respect_robots_txt is False
        finally:
            del os.environ["CRAWLER_PORT"]
            del os.environ["CRAWLER_MAX_DEPTH"]
            del os.environ["CRAWLER_RESPECT_ROBOTS_TXT"]

    def test_allowed_extensions_contains_all_formats(self) -> None:
        """默认扩展名应包含所有支持的格式"""
        settings = CrawlerSettings()
        expected = {
            "pdf",
            "txt",
            "doc",
            "docx",
            "ppt",
            "pptx",
            "xls",
            "xlsx",
            "csv",
            "jpeg",
            "jpg",
            "png",
            "gif",
            "md",
            "markdown",
            "zip",
            "tar",
            "gz",
            "bz2",
            # 视频
            "mp4",
            "avi",
            "mov",
            "mkv",
            "webm",
            "wmv",
            "flv",
            "m4v",
            "3gp",
            # 音频
            "mp3",
            "wav",
            "ogg",
            "flac",
            "aac",
            "wma",
            "m4a",
        }
        assert set(settings.allowed_extensions) == expected

    def test_to_scrapy_settings_basic(self) -> None:
        """to_scrapy_settings 应包含基础配置"""
        settings = CrawlerSettings()
        result = settings.to_scrapy_settings()
        assert result["BOT_NAME"] == "sisys_crawler"
        assert result["ROBOTSTXT_OBEY"] is True
        assert result["CONCURRENT_REQUESTS"] == 8
        assert result["DOWNLOAD_DELAY"] == 1.0
        assert "ITEM_PIPELINES" in result
        assert len(result["ITEM_PIPELINES"]) == 6

    def test_to_scrapy_settings_middlewares_activated(self) -> None:
        """默认应激活三个中间件"""
        settings = CrawlerSettings()
        result = settings.to_scrapy_settings()
        assert "DOWNLOADER_MIDDLEWARES" in result
        middlewares = result["DOWNLOADER_MIDDLEWARES"]
        assert len(middlewares) == 3
        assert "RateLimitMiddleware" in str(middlewares)
        assert "UserAgentRotationMiddleware" in str(middlewares)
        assert "RetryMiddleware" in str(middlewares)

    def test_to_scrapy_settings_middlewares_disabled(self) -> None:
        """中间件开关关闭时不应出现在配置中"""
        settings = CrawlerSettings(enable_rate_limit=False, enable_ua_rotation=False, enable_retry=False)
        result = settings.to_scrapy_settings()
        assert "DOWNLOADER_MIDDLEWARES" not in result

    def test_to_scrapy_settings_browser_disabled_by_default(self) -> None:
        """默认不应包含 Playwright 配置"""
        settings = CrawlerSettings()
        result = settings.to_scrapy_settings()
        assert "TWISTED_REACTOR" not in result
        assert "DOWNLOAD_HANDLERS" not in result

    def test_to_scrapy_settings_browser_enabled(self) -> None:
        """启用浏览器时应包含 Playwright 配置"""
        settings = CrawlerSettings(enable_browser=True)
        result = settings.to_scrapy_settings()
        assert result["TWISTED_REACTOR"] == "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
        assert "ScrapyPlaywrightDownloadHandler" in str(result["DOWNLOAD_HANDLERS"])
        assert "playwright_abort" in result["PLAYWRIGHT_ABORT_REQUEST"]
        assert result["PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT"] == 30000

    def test_to_scrapy_settings_browser_proxy(self) -> None:
        """配置代理时应传入 PLAYWRIGHT_LAUNCH_OPTIONS"""
        settings = CrawlerSettings(enable_browser=True, browser_proxy="http://proxy:8080")
        result = settings.to_scrapy_settings()
        assert result["PLAYWRIGHT_LAUNCH_OPTIONS"]["proxy"]["server"] == "http://proxy:8080"

    def test_to_scrapy_settings_user_agent(self) -> None:
        """传入 user_agent 时应设置 USER_AGENT"""
        settings = CrawlerSettings()
        result = settings.to_scrapy_settings(user_agent="CustomBot/1.0")
        assert result["USER_AGENT"] == "CustomBot/1.0"

    def test_to_scrapy_settings_no_user_agent(self) -> None:
        """不传 user_agent 时不应设置 USER_AGENT（交给 UA 轮换中间件）"""
        settings = CrawlerSettings()
        result = settings.to_scrapy_settings()
        assert "USER_AGENT" not in result

    # ── 认证配置测试 ──

    def test_default_auth_fields_empty(self) -> None:
        """默认认证字段应为空"""
        settings = CrawlerSettings()
        assert settings.auth_storage_state_path == ""
        assert settings.auth_headers == {}

    def test_from_env_auth_storage_state_path(self) -> None:
        """环境变量 CRAWLER_AUTH_STORAGE_STATE_PATH 应正确加载"""
        auth_path = os.path.join(tempfile.gettempdir(), "auth.json")
        os.environ["CRAWLER_AUTH_STORAGE_STATE_PATH"] = auth_path
        try:
            settings = CrawlerSettings.from_env()
            assert settings.auth_storage_state_path == auth_path
        finally:
            del os.environ["CRAWLER_AUTH_STORAGE_STATE_PATH"]

    def test_to_scrapy_settings_no_auth_by_default(self) -> None:
        """默认不应包含认证相关配置"""
        settings = CrawlerSettings()
        result = settings.to_scrapy_settings()
        assert "PLAYWRIGHT_CONTEXT_ARGS" not in result
        assert "DEFAULT_REQUEST_HEADERS" not in result

    def test_to_scrapy_settings_storage_state_with_browser(self) -> None:
        """enable_browser=True + auth_storage_state_path 应注入 PLAYWRIGHT_CONTEXT_ARGS"""
        auth_path = os.path.join(tempfile.gettempdir(), "auth.json")
        settings = CrawlerSettings(enable_browser=True, auth_storage_state_path=auth_path)
        result = settings.to_scrapy_settings()
        assert result["PLAYWRIGHT_CONTEXT_ARGS"] == {"storage_state": auth_path}

    def test_to_scrapy_settings_storage_state_without_browser(self) -> None:
        """enable_browser=False 时 auth_storage_state_path 不应注入 PLAYWRIGHT_CONTEXT_ARGS"""
        auth_path = os.path.join(tempfile.gettempdir(), "auth.json")
        settings = CrawlerSettings(enable_browser=False, auth_storage_state_path=auth_path)
        result = settings.to_scrapy_settings()
        assert "PLAYWRIGHT_CONTEXT_ARGS" not in result

    def test_to_scrapy_settings_auth_headers(self) -> None:
        """auth_headers 应注入为 DEFAULT_REQUEST_HEADERS"""
        settings = CrawlerSettings(auth_headers={"Authorization": "Bearer token"})
        result = settings.to_scrapy_settings()
        assert result["DEFAULT_REQUEST_HEADERS"] == {"Authorization": "Bearer token"}

    def test_to_scrapy_settings_auth_headers_with_browser_and_storage(self) -> None:
        """browser + storageState + headers 应全部注入"""
        auth_path = os.path.join(tempfile.gettempdir(), "auth.json")
        settings = CrawlerSettings(
            enable_browser=True,
            auth_storage_state_path=auth_path,
            auth_headers={"X-Custom": "value"},
        )
        result = settings.to_scrapy_settings()
        assert result["PLAYWRIGHT_CONTEXT_ARGS"] == {"storage_state": auth_path}
        assert result["DEFAULT_REQUEST_HEADERS"] == {"X-Custom": "value"}

    def test_to_scrapy_settings_auth_headers_empty(self) -> None:
        """空 auth_headers 不应产生 DEFAULT_REQUEST_HEADERS"""
        settings = CrawlerSettings(auth_headers={})
        result = settings.to_scrapy_settings()
        assert "DEFAULT_REQUEST_HEADERS" not in result
