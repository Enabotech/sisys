"""CrawlerSettings 配置单元测试

TDD 阶段：绿
验证默认值和环境变量覆盖

"""

from __future__ import annotations

import os

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
        }
        assert set(settings.allowed_extensions) == expected
