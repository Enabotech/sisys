"""接口层 Crawler API 路由单元测试

验证 Crawler 路由端点的请求处理、响应格式和异常转换行为，
包括 Pydantic 模型验证、成功路径响应、异常路径 ServiceUnavailableError 转换
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.interfaces.api.crawler import SubmitTaskRequest, create_crawler_router
from src.interfaces.api.exception_handlers import register_exception_handlers

# =============================================================================
# Pydantic 模型验证测试
# =============================================================================


class TestSubmitTaskRequest:
    """提交任务请求模型验证"""

    def test_default_values(self) -> None:
        """默认值验证：可选字段应有正确默认值"""
        req = SubmitTaskRequest(domains=["example.com"])

        assert req.domains == ["example.com"]
        assert req.seed_urls is None
        assert req.allowed_extensions is None
        assert req.max_depth == 3
        assert req.follow_subdomains is True
        assert req.max_files == 1000
        assert req.download_delay == 1.0

    def test_domains_required(self) -> None:
        """domains 为必填字段，缺失时应抛出验证错误"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SubmitTaskRequest()  # type: ignore[call-arg]

    def test_domains_must_not_be_empty(self) -> None:
        """domains 列表不能为空（min_length=1）"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SubmitTaskRequest(domains=[])

    def test_max_depth_boundary(self) -> None:
        """max_depth 边界值验证：ge=1, le=10"""
        from pydantic import ValidationError

        # 最小值边界
        req_min = SubmitTaskRequest(domains=["example.com"], max_depth=1)
        assert req_min.max_depth == 1

        # 最大值边界
        req_max = SubmitTaskRequest(domains=["example.com"], max_depth=10)
        assert req_max.max_depth == 10

        # 超出下界
        with pytest.raises(ValidationError):
            SubmitTaskRequest(domains=["example.com"], max_depth=0)

        # 超出上界
        with pytest.raises(ValidationError):
            SubmitTaskRequest(domains=["example.com"], max_depth=11)

    def test_max_files_boundary(self) -> None:
        """max_files 边界值验证：ge=1, le=10000"""
        from pydantic import ValidationError

        req_min = SubmitTaskRequest(domains=["example.com"], max_files=1)
        assert req_min.max_files == 1

        req_max = SubmitTaskRequest(domains=["example.com"], max_files=10000)
        assert req_max.max_files == 10000

        with pytest.raises(ValidationError):
            SubmitTaskRequest(domains=["example.com"], max_files=0)

        with pytest.raises(ValidationError):
            SubmitTaskRequest(domains=["example.com"], max_files=10001)

    def test_download_delay_boundary(self) -> None:
        """download_delay 边界值验证：ge=0.1, le=10.0"""
        from pydantic import ValidationError

        req_min = SubmitTaskRequest(domains=["example.com"], download_delay=0.1)
        assert req_min.download_delay == 0.1

        req_max = SubmitTaskRequest(domains=["example.com"], download_delay=10.0)
        assert req_max.download_delay == 10.0

        with pytest.raises(ValidationError):
            SubmitTaskRequest(domains=["example.com"], download_delay=0.05)

        with pytest.raises(ValidationError):
            SubmitTaskRequest(domains=["example.com"], download_delay=10.1)

    def test_custom_values(self) -> None:
        """自定义全部字段值"""
        req = SubmitTaskRequest(
            domains=["a.com", "b.com"],
            seed_urls=["https://a.com/page1"],
            allowed_extensions=[".pdf", ".docx"],
            max_depth=5,
            follow_subdomains=False,
            max_files=500,
            download_delay=2.0,
        )
        assert req.domains == ["a.com", "b.com"]
        assert req.seed_urls == ["https://a.com/page1"]
        assert req.allowed_extensions == [".pdf", ".docx"]
        assert req.max_depth == 5
        assert req.follow_subdomains is False
        assert req.max_files == 500
        assert req.download_delay == 2.0


# =============================================================================
# 端点测试 Fixture
# =============================================================================


class _MockCrawlerClient:
    """模拟 CrawlerClientPort 的测试替身

    通过 side_effect 属性支持异常注入
    """

    def __init__(
        self,
        submit_task_return: str = "task-abc-123",
        get_task_status_return: dict[str, Any] | None = None,
        cancel_task_return: bool = True,
        list_supported_formats_return: list[str] | None = None,
    ) -> None:
        """初始化模拟客户端

        Args:
            submit_task_return: submit_task 返回值
            get_task_status_return: get_task_status 返回值
            cancel_task_return: cancel_task 返回值
            list_supported_formats_return: list_supported_formats 返回值
        """
        self._submit_task_return = submit_task_return
        self._get_task_status_return = get_task_status_return or {
            "task_id": "task-abc-123",
            "status": "running",
            "progress": 0.5,
            "files_downloaded": 10,
            "errors": 0,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T01:00:00Z",
        }
        self._cancel_task_return = cancel_task_return
        self._list_supported_formats_return: list[str] = (
            list_supported_formats_return if list_supported_formats_return is not None else ["pdf", "docx", "xlsx"]
        )

        # 异常注入点：设置为异常实例则抛出
        self.submit_task_side_effect: Exception | None = None
        self.get_task_status_side_effect: Exception | None = None
        self.cancel_task_side_effect: Exception | None = None
        self.list_supported_formats_side_effect: Exception | None = None

        # 记录调用参数
        self.submit_task_call_args: dict[str, Any] | None = None
        self.get_task_status_call_args: str | None = None
        self.cancel_task_call_args: str | None = None

    async def submit_task(
        self,
        domains: list[str],
        seed_urls: list[str] | None = None,
        allowed_extensions: list[str] | None = None,
        max_depth: int = 3,
        follow_subdomains: bool = True,
        max_files: int = 1000,
        download_delay: float = 1.0,
    ) -> str:
        """模拟提交爬取任务"""
        self.submit_task_call_args = {
            "domains": domains,
            "seed_urls": seed_urls,
            "allowed_extensions": allowed_extensions,
            "max_depth": max_depth,
            "follow_subdomains": follow_subdomains,
            "max_files": max_files,
            "download_delay": download_delay,
        }
        if self.submit_task_side_effect:
            raise self.submit_task_side_effect
        return self._submit_task_return

    async def get_task_status(self, task_id: str) -> dict[str, Any]:
        """模拟查询任务状态"""
        self.get_task_status_call_args = task_id
        if self.get_task_status_side_effect:
            raise self.get_task_status_side_effect
        return self._get_task_status_return

    async def cancel_task(self, task_id: str) -> bool:
        """模拟取消任务"""
        self.cancel_task_call_args = task_id
        if self.cancel_task_side_effect:
            raise self.cancel_task_side_effect
        return self._cancel_task_return

    async def list_supported_formats(self) -> list[str]:
        """模拟列出支持格式"""
        if self.list_supported_formats_side_effect:
            raise self.list_supported_formats_side_effect
        return self._list_supported_formats_return


def _create_app(mock_client: _MockCrawlerClient) -> FastAPI:
    """创建包含 Crawler 路由和异常处理器的 FastAPI 测试应用

    Args:
        mock_client: 模拟的 CrawlerClientPort 实例

    Returns:
        配置好的 FastAPI 应用
    """
    app = FastAPI()
    register_exception_handlers(app)
    router = create_crawler_router(get_crawler_client=lambda: mock_client)
    app.include_router(router)
    return app


# =============================================================================
# 端点测试
# =============================================================================


class TestSubmitTask:
    """提交任务端点测试"""

    @pytest.mark.asyncio
    async def test_submit_task_success(self) -> None:
        """提交任务成功返回 201 + task_id"""
        mock_client = _MockCrawlerClient(submit_task_return="task-xyz-789")
        app = _create_app(mock_client)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/crawler/tasks",
                json={"domains": ["example.com"]},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["task_id"] == "task-xyz-789"

    @pytest.mark.asyncio
    async def test_submit_task_passes_all_params(self) -> None:
        """提交任务时传递所有参数到客户端"""
        mock_client = _MockCrawlerClient()
        app = _create_app(mock_client)

        payload = {
            "domains": ["a.com", "b.com"],
            "seed_urls": ["https://a.com/1"],
            "allowed_extensions": [".pdf"],
            "max_depth": 5,
            "follow_subdomains": False,
            "max_files": 200,
            "download_delay": 2.5,
        }

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/crawler/tasks",
                json=payload,
            )

        assert response.status_code == 201
        assert mock_client.submit_task_call_args == {
            "domains": ["a.com", "b.com"],
            "seed_urls": ["https://a.com/1"],
            "allowed_extensions": [".pdf"],
            "max_depth": 5,
            "follow_subdomains": False,
            "max_files": 200,
            "download_delay": 2.5,
        }

    @pytest.mark.asyncio
    async def test_submit_task_service_unavailable(self) -> None:
        """client 抛异常时转换为 ServiceUnavailableError 返回 503"""
        mock_client = _MockCrawlerClient()
        mock_client.submit_task_side_effect = ConnectionError("Crawler service down")
        app = _create_app(mock_client)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/crawler/tasks",
                json={"domains": ["example.com"]},
            )

        assert response.status_code == 503
        body = response.json()
        assert "Crawler service unavailable" in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_submit_task_invalid_request_body(self) -> None:
        """请求体缺少必填字段时返回 400"""
        mock_client = _MockCrawlerClient()
        app = _create_app(mock_client)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/crawler/tasks",
                json={},
            )

        assert response.status_code == 400


class TestGetTaskStatus:
    """查询任务状态端点测试"""

    @pytest.mark.asyncio
    async def test_get_task_status_success(self) -> None:
        """查询任务状态成功返回完整状态信息"""
        mock_client = _MockCrawlerClient(
            get_task_status_return={
                "task_id": "task-001",
                "status": "completed",
                "progress": 1.0,
                "files_downloaded": 42,
                "errors": 2,
                "created_at": "2025-06-01T10:00:00Z",
                "updated_at": "2025-06-01T11:00:00Z",
            }
        )
        app = _create_app(mock_client)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/crawler/tasks/task-001")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-001"
        assert data["status"] == "completed"
        assert data["progress"] == 1.0
        assert data["files_downloaded"] == 42
        assert data["errors"] == 2
        assert data["created_at"] == "2025-06-01T10:00:00Z"
        assert data["updated_at"] == "2025-06-01T11:00:00Z"

    @pytest.mark.asyncio
    async def test_get_task_status_with_defaults(self) -> None:
        """状态查询缺失字段使用 .get() 默认值"""
        mock_client = _MockCrawlerClient(
            get_task_status_return={
                "task_id": "task-002",
            }
        )
        app = _create_app(mock_client)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/crawler/tasks/task-002")

        assert response.status_code == 200
        data = response.json()
        # task_id 来自 dict
        assert data["task_id"] == "task-002"
        # status 默认值 "unknown"
        assert data["status"] == "unknown"
        # 可选字段均为 None
        assert data["progress"] is None
        assert data["files_downloaded"] is None
        assert data["errors"] is None
        assert data["created_at"] is None
        assert data["updated_at"] is None

    @pytest.mark.asyncio
    async def test_get_task_status_missing_task_id_uses_path_param(self) -> None:
        """状态字典中缺少 task_id 时使用路径参数 task_id"""
        mock_client = _MockCrawlerClient(
            get_task_status_return={
                "status": "running",
            }
        )
        app = _create_app(mock_client)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/crawler/tasks/path-task-id")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "path-task-id"

    @pytest.mark.asyncio
    async def test_get_task_status_service_unavailable(self) -> None:
        """状态查询服务不可用返回 503"""
        mock_client = _MockCrawlerClient()
        mock_client.get_task_status_side_effect = TimeoutError("Connection timed out")
        app = _create_app(mock_client)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/crawler/tasks/task-999")

        assert response.status_code == 503
        body = response.json()
        assert "Crawler service unavailable" in body["error"]["message"]


class TestCancelTask:
    """取消任务端点测试"""

    @pytest.mark.asyncio
    async def test_cancel_task_success(self) -> None:
        """取消任务成功返回 cancelled=true"""
        mock_client = _MockCrawlerClient(cancel_task_return=True)
        app = _create_app(mock_client)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete("/api/v1/crawler/tasks/task-001")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-001"
        assert data["cancelled"] is True

    @pytest.mark.asyncio
    async def test_cancel_task_returns_false(self) -> None:
        """取消任务返回 cancelled=false（如任务已完成无法取消）"""
        mock_client = _MockCrawlerClient(cancel_task_return=False)
        app = _create_app(mock_client)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete("/api/v1/crawler/tasks/task-done")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-done"
        assert data["cancelled"] is False

    @pytest.mark.asyncio
    async def test_cancel_task_service_unavailable(self) -> None:
        """取消任务服务不可用返回 503"""
        mock_client = _MockCrawlerClient()
        mock_client.cancel_task_side_effect = RuntimeError("Service crashed")
        app = _create_app(mock_client)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete("/api/v1/crawler/tasks/task-001")

        assert response.status_code == 503
        body = response.json()
        assert "Crawler service unavailable" in body["error"]["message"]


class TestListSupportedFormats:
    """列出支持格式端点测试"""

    @pytest.mark.asyncio
    async def test_list_formats_success(self) -> None:
        """列出支持格式成功返回格式列表"""
        mock_client = _MockCrawlerClient(list_supported_formats_return=["pdf", "docx", "xlsx", "pptx"])
        app = _create_app(mock_client)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/crawler/formats")

        assert response.status_code == 200
        data = response.json()
        assert data["formats"] == ["pdf", "docx", "xlsx", "pptx"]

    @pytest.mark.asyncio
    async def test_list_formats_empty(self) -> None:
        """格式列表为空时返回空数组"""
        mock_client = _MockCrawlerClient(list_supported_formats_return=[])
        app = _create_app(mock_client)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/crawler/formats")

        assert response.status_code == 200
        data = response.json()
        assert data["formats"] == []

    @pytest.mark.asyncio
    async def test_list_formats_service_unavailable(self) -> None:
        """列格式服务不可用返回 503"""
        mock_client = _MockCrawlerClient()
        mock_client.list_supported_formats_side_effect = OSError("Network unreachable")
        app = _create_app(mock_client)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/crawler/formats")

        assert response.status_code == 503
        body = response.json()
        assert "Crawler service unavailable" in body["error"]["message"]


class TestRouterConfiguration:
    """路由配置验证"""

    def test_router_has_correct_prefix(self) -> None:
        """路由包含 /api/v1/crawler 前缀"""
        mock_client = _MockCrawlerClient()
        app = _create_app(mock_client)
        crawler_paths = [r.path for r in app.routes if hasattr(r, "path") and r.path.startswith("/api/v1/crawler")]
        assert len(crawler_paths) == 4

    def test_router_has_all_endpoints(self) -> None:
        """路由包含 4 个端点：submit / status / cancel / formats"""
        mock_client = _MockCrawlerClient()
        app = _create_app(mock_client)
        crawler_paths = sorted(r.path for r in app.routes if hasattr(r, "path") and r.path.startswith("/api/v1/crawler"))
        expected = [
            "/api/v1/crawler/formats",
            "/api/v1/crawler/tasks",
            "/api/v1/crawler/tasks/{task_id}",
            "/api/v1/crawler/tasks/{task_id}",
        ]
        assert crawler_paths == expected
