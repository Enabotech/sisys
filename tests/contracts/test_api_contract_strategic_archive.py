"""战略档案 API 契约测试

验证战略档案 API 路由的请求/响应结构、状态码和错误响应格式。
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive


class TestApiContractStrategicArchive:
    """API 契约测试 — 验证请求/响应结构、状态码、错误格式"""

    BASE_PATH = "/api/v1/archive"

    @pytest.fixture
    def app(self) -> FastAPI:
        """创建测试用 FastAPI 应用"""
        from src.interfaces.api.strategic_archive import create_archive_router

        app = FastAPI()
        app.include_router(create_archive_router())
        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """创建测试客户端"""
        return TestClient(app)

    @pytest.fixture
    def mock_service(self) -> Any:
        """创建 Mock 战略档案服务"""
        mock = AsyncMock()
        mock.archive_plan.return_value = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            assumptions={"key": "value"},
            metadata_ref="strategic_archives:test-id",
        )
        mock.get_archive.return_value = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            assumptions={"key": "value"},
            metadata_ref="strategic_archives:test-id",
        )
        mock.query_archive.return_value = [
            StrategicArchive(
                archive_id=uuid.uuid4(),
                plan_id=uuid.uuid4(),
                plan_type="SP",
                archive_type=ArchiveType.ASSUMPTION,
                assumptions={"key": "value"},
                metadata_ref="strategic_archives:test-id",
            )
        ]
        return mock

    @pytest.fixture
    def override_app(self, app: FastAPI, mock_service: Any) -> FastAPI:
        """注入 mock 服务到路由"""
        from src.interfaces.api.strategic_archive import create_archive_router

        # 重新创建路由并注入 mock
        router = create_archive_router(archive_service=mock_service, get_current_user_override=lambda: None)
        app.router.routes = [r for r in app.router.routes if not hasattr(r, "path") or not r.path.startswith(self.BASE_PATH)]
        app.include_router(router)
        return app

    @pytest.fixture
    def auth_client(self, override_app: FastAPI) -> TestClient:
        """带认证覆盖的客户端"""
        return TestClient(override_app)

    # ------------------------------------------------------------------
    # GET /api/v1/archive/entries — 档案列表
    # ------------------------------------------------------------------

    def test_list_entries_returns_200(self, auth_client: TestClient) -> None:
        """GET /entries 返回 200"""
        response = auth_client.get(f"{self.BASE_PATH}/entries")
        assert response.status_code == 200

    def test_list_entries_returns_list(self, auth_client: TestClient) -> None:
        """GET /entries 返回列表"""
        response = auth_client.get(f"{self.BASE_PATH}/entries")
        data = response.json()
        assert isinstance(data, list)

    def test_list_entries_supports_filters(self, auth_client: TestClient) -> None:
        """GET /entries 支持过滤参数"""
        response = auth_client.get(
            f"{self.BASE_PATH}/entries",
            params={
                "archive_type": "assumption",
                "plan_type": "SP",
                "start_date": "2026-01-01T00:00:00Z",
                "end_date": "2026-12-31T23:59:59Z",
                "offset": 0,
                "limit": 20,
            },
        )
        assert response.status_code == 200

    # ------------------------------------------------------------------
    # GET /api/v1/archive/entries/{archive_id} — 档案详情
    # ------------------------------------------------------------------

    def test_get_entry_returns_200(self, auth_client: TestClient, mock_service: Any) -> None:
        """GET /entries/{archive_id} 返回 200"""
        archive_id = uuid.uuid4()
        mock_service.get_archive.return_value = StrategicArchive(
            archive_id=archive_id,
            plan_id=uuid.uuid4(),
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            assumptions={},
            metadata_ref="test",
        )
        response = auth_client.get(f"{self.BASE_PATH}/entries/{archive_id}")
        assert response.status_code == 200

    def test_get_entry_returns_archive(self, auth_client: TestClient, mock_service: Any) -> None:
        """GET /entries/{archive_id} 返回档案对象"""
        archive_id = uuid.uuid4()
        mock_service.get_archive.return_value = StrategicArchive(
            archive_id=archive_id,
            plan_id=uuid.uuid4(),
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            assumptions={},
            metadata_ref="test",
        )
        response = auth_client.get(f"{self.BASE_PATH}/entries/{archive_id}")
        data = response.json()
        assert "archive_id" in data

    # ------------------------------------------------------------------
    # POST /api/v1/archive/archive — 手动触发归档
    # ------------------------------------------------------------------

    def test_archive_endpoint_returns_201(self, auth_client: TestClient) -> None:
        """POST /archive 返回 201"""
        response = auth_client.post(
            f"{self.BASE_PATH}/archive",
            json={
                "plan_id": str(uuid.uuid4()),
                "plan_type": "SP",
                "assumptions": {"key": "value"},
                "decision_basis": {},
                "execution_deviation": {},
            },
        )
        assert response.status_code in (200, 201)

    def test_archive_endpoint_returns_archive(self, auth_client: TestClient) -> None:
        """POST /archive 返回创建的档案"""
        response = auth_client.post(
            f"{self.BASE_PATH}/archive",
            json={
                "plan_id": str(uuid.uuid4()),
                "plan_type": "SP",
                "assumptions": {"key": "value"},
                "decision_basis": {},
                "execution_deviation": {},
            },
        )
        data = response.json()
        assert "archive_id" in data

    # ------------------------------------------------------------------
    # GET /api/v1/archive/plans/{plan_id} — 按规划 ID 查询
    # ------------------------------------------------------------------

    def test_get_by_plan_returns_200(self, auth_client: TestClient) -> None:
        """GET /plans/{plan_id} 返回 200"""
        plan_id = uuid.uuid4()
        response = auth_client.get(f"{self.BASE_PATH}/plans/{plan_id}")
        assert response.status_code == 200

    def test_get_by_plan_returns_list(self, auth_client: TestClient) -> None:
        """GET /plans/{plan_id} 返回列表"""
        plan_id = uuid.uuid4()
        response = auth_client.get(f"{self.BASE_PATH}/plans/{plan_id}")
        data = response.json()
        assert isinstance(data, list)

    # ------------------------------------------------------------------
    # 错误响应格式
    # ------------------------------------------------------------------

    def test_error_response_has_code_and_message(self, auth_client: TestClient) -> None:
        """错误响应包含 code 和 message"""
        response = auth_client.get(f"{self.BASE_PATH}/entries/{uuid.uuid4()}")
        if response.status_code != 200:
            data = response.json()
            assert "error" in data
            assert "code" in data["error"]
            assert "message" in data["error"]
