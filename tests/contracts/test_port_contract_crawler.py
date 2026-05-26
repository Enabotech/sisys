"""SISYS 侧 Crawler 端口契约测试

验证 crawler_client 端口已注册且方法签名正确

"""

from __future__ import annotations


class TestCrawlerPortContract:
    """Crawler 端口契约测试"""

    def test_port_interface_exists(self) -> None:
        """CrawlerClientPort 应可导入"""
        from src.domain.ports.crawler_client import CrawlerClientPort

        assert CrawlerClientPort is not None

    def test_port_is_runtime_checkable(self) -> None:
        """CrawlerClientPort 应支持运行时检查"""
        from src.domain.ports.crawler_client import CrawlerClientPort

        assert hasattr(CrawlerClientPort, "__protocol_attrs__") or hasattr(
            CrawlerClientPort,
            "_is_protocol",
        )

    def test_port_has_required_methods(self) -> None:
        """CrawlerClientPort 应包含所有必要方法"""
        from src.domain.ports.crawler_client import CrawlerClientPort

        required_methods = [
            "submit_task",
            "get_task_status",
            "cancel_task",
            "list_supported_formats",
        ]
        for method_name in required_methods:
            assert hasattr(CrawlerClientPort, method_name), f"缺少方法: {method_name}"

    def test_http_client_implements_port(self) -> None:
        """HttpCrawlerClient 应实现 CrawlerClientPort"""
        from src.domain.ports.crawler_client import CrawlerClientPort
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        assert isinstance(HttpCrawlerClient(base_url="http://localhost:8900"), CrawlerClientPort)
