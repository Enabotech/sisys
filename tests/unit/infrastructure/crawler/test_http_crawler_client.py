"""单元测试：HTTP Crawler 客户端适配器

测试 HttpCrawlerClient 的各方法，使用 httpx mock 进行 HTTP 请求模拟
"""

from __future__ import annotations

import json

import httpx
import pytest


class TestHttpCrawlerClient:
    """HttpCrawlerClient 单元测试"""

    def test_init(self) -> None:
        """测试初始化"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        client = HttpCrawlerClient(base_url="http://localhost:8900")
        assert client._base_url == "http://localhost:8900"
        assert client._timeout == 30.0
        assert client._client is None

    def test_init_with_trailing_slash(self) -> None:
        """测试初始化时去除尾部斜杠"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        client = HttpCrawlerClient(base_url="http://localhost:8900/")
        assert client._base_url == "http://localhost:8900"

    def test_init_with_custom_timeout(self) -> None:
        """测试初始化时设置自定义超时"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        client = HttpCrawlerClient(base_url="http://localhost:8900", timeout=60.0)
        assert client._timeout == 60.0

    @pytest.mark.asyncio
    async def test_submit_task_success(self) -> None:
        """测试提交任务成功"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        mock_response = httpx.Response(201, json={"task_id": "test-task-123"})

        async def mock_transport(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert str(request.url) == "http://localhost:8900/api/v1/tasks"
            assert json.loads(request.content)["domains"] == ["example.com"]
            return mock_response

        transport = httpx.MockTransport(mock_transport)
        client = HttpCrawlerClient(base_url="http://localhost:8900")
        client._client = httpx.AsyncClient(transport=transport)

        task_id = await client.submit_task(domains=["example.com"])
        assert task_id == "test-task-123"

        await client.close()

    @pytest.mark.asyncio
    async def test_submit_task_with_all_params(self) -> None:
        """测试提交任务带所有参数"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        mock_response = httpx.Response(201, json={"task_id": "test-task-456"})

        async def mock_transport(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            payload = json.loads(request.content)
            assert payload["domains"] == ["example.com", "test.com"]
            assert payload["seed_urls"] == ["http://example.com/page1"]
            assert payload["allowed_extensions"] == [".pdf", ".doc"]
            assert payload["max_depth"] == 5
            assert payload["follow_subdomains"] is False
            assert payload["max_files"] == 500
            assert payload["download_delay"] == 2.0
            return mock_response

        transport = httpx.MockTransport(mock_transport)
        client = HttpCrawlerClient(base_url="http://localhost:8900")
        client._client = httpx.AsyncClient(transport=transport)

        task_id = await client.submit_task(
            domains=["example.com", "test.com"],
            seed_urls=["http://example.com/page1"],
            allowed_extensions=[".pdf", ".doc"],
            max_depth=5,
            follow_subdomains=False,
            max_files=500,
            download_delay=2.0,
        )
        assert task_id == "test-task-456"

        await client.close()

    @pytest.mark.asyncio
    async def test_submit_task_failure(self) -> None:
        """测试提交任务失败"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        async def mock_transport(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "Internal server error"})

        transport = httpx.MockTransport(mock_transport)
        client = HttpCrawlerClient(base_url="http://localhost:8900")
        client._client = httpx.AsyncClient(transport=transport)

        with pytest.raises(httpx.HTTPStatusError):
            await client.submit_task(domains=["example.com"])

        await client.close()

    @pytest.mark.asyncio
    async def test_get_task_status_success(self) -> None:
        """测试查询任务状态成功"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        mock_response = httpx.Response(
            200,
            json={
                "task_id": "test-task-123",
                "status": "running",
                "progress": 0.5,
                "files_downloaded": 50,
                "errors": 2,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T01:00:00Z",
            },
        )

        async def mock_transport(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert str(request.url) == "http://localhost:8900/api/v1/tasks/test-task-123"
            return mock_response

        transport = httpx.MockTransport(mock_transport)
        client = HttpCrawlerClient(base_url="http://localhost:8900")
        client._client = httpx.AsyncClient(transport=transport)

        status_data = await client.get_task_status("test-task-123")
        assert status_data["task_id"] == "test-task-123"
        assert status_data["status"] == "running"
        assert status_data["progress"] == 0.5
        assert status_data["files_downloaded"] == 50

        await client.close()

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self) -> None:
        """测试查询任务状态不存在"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        async def mock_transport(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "Task not found"})

        transport = httpx.MockTransport(mock_transport)
        client = HttpCrawlerClient(base_url="http://localhost:8900")
        client._client = httpx.AsyncClient(transport=transport)

        with pytest.raises(httpx.HTTPStatusError):
            await client.get_task_status("non-existent-task")

        await client.close()

    @pytest.mark.asyncio
    async def test_cancel_task_success(self) -> None:
        """测试取消任务成功"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        async def mock_transport(request: httpx.Request) -> httpx.Response:
            assert request.method == "DELETE"
            assert str(request.url) == "http://localhost:8900/api/v1/tasks/test-task-123"
            return httpx.Response(200, json={"cancelled": True})

        transport = httpx.MockTransport(mock_transport)
        client = HttpCrawlerClient(base_url="http://localhost:8900")
        client._client = httpx.AsyncClient(transport=transport)

        result = await client.cancel_task("test-task-123")
        assert result is True

        await client.close()

    @pytest.mark.asyncio
    async def test_cancel_task_failure(self) -> None:
        """测试取消任务失败"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        async def mock_transport(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "Cannot cancel completed task"})

        transport = httpx.MockTransport(mock_transport)
        client = HttpCrawlerClient(base_url="http://localhost:8900")
        client._client = httpx.AsyncClient(transport=transport)

        result = await client.cancel_task("completed-task")
        assert result is False

        await client.close()

    @pytest.mark.asyncio
    async def test_list_supported_formats_success(self) -> None:
        """测试列出支持的文件格式成功"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        mock_response = httpx.Response(
            200,
            json={"formats": ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx"]},
        )

        async def mock_transport(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert str(request.url) == "http://localhost:8900/api/v1/formats"
            return mock_response

        transport = httpx.MockTransport(mock_transport)
        client = HttpCrawlerClient(base_url="http://localhost:8900")
        client._client = httpx.AsyncClient(transport=transport)

        formats = await client.list_supported_formats()
        assert formats == ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx"]

        await client.close()

    @pytest.mark.asyncio
    async def test_list_supported_formats_empty(self) -> None:
        """测试列出支持的文件格式为空"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        mock_response = httpx.Response(200, json={"formats": []})

        async def mock_transport(request: httpx.Request) -> httpx.Response:
            return mock_response

        transport = httpx.MockTransport(mock_transport)
        client = HttpCrawlerClient(base_url="http://localhost:8900")
        client._client = httpx.AsyncClient(transport=transport)

        formats = await client.list_supported_formats()
        assert formats == []

        await client.close()

    @pytest.mark.asyncio
    async def test_close_client(self) -> None:
        """测试关闭客户端"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        client = HttpCrawlerClient(base_url="http://localhost:8900")
        await client._get_client()
        assert client._client is not None

        await client.close()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_client_when_none(self) -> None:
        """测试关闭未初始化的客户端"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        client = HttpCrawlerClient(base_url="http://localhost:8900")
        assert client._client is None

        await client.close()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_lazy_client_creation(self) -> None:
        """测试延迟创建客户端"""
        from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

        client = HttpCrawlerClient(base_url="http://localhost:8900")
        assert client._client is None

        first_client = await client._get_client()
        assert client._client is not None
        assert first_client is client._client

        second_client = await client._get_client()
        assert second_client is first_client

        await client.close()
