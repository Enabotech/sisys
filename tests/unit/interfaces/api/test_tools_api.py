"""工具版本管理 REST API 单元测试（Story 4-6 Task 6 TDD 红→绿）

TestClient + AsyncMock(spec=ToolVersionServicePort) + get_current_user_override
（document_upload _make_client 先例）：6 端点正常路径 + 错误映射（380/430/
431/397/433/432/243/242）+ 401 无认证 + 响应模型字段。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.application.ports.tool_version_service import ToolVersionServicePort
from src.domain.entities.tool_version import ToolVersion, ToolVersionStatus
from src.domain.exceptions import EntityValidationError
from src.domain.exceptions.tool_exceptions import ToolNotFoundError
from src.domain.exceptions.tool_schema_exceptions import ToolSchemaCompatibilityError
from src.domain.exceptions.tool_version_exceptions import (
    ToolVersionAlreadyExistsError,
    ToolVersionNotFoundError,
    ToolVersionRollbackError,
    ToolVersionTrafficWeightError,
)
from src.domain.value_objects.token_payload import TokenPayload
from src.interfaces.api.exception_handlers import register_exception_handlers
from src.interfaces.api.middleware.exception_context import ExceptionContextMiddleware
from src.interfaces.api.tools import create_tools_router


def _make_token() -> TokenPayload:
    """构造认证 Payload。"""
    return TokenPayload(
        user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        username="testuser",
        roles=("admin",),
        exp=datetime(2099, 1, 1, tzinfo=UTC),
    )


def _make_tv(
    tool_id: uuid.UUID | None = None,
    version: str = "1.1.0",
    status: ToolVersionStatus = ToolVersionStatus.CANARY,
    weight: int = 30,
) -> ToolVersion:
    """构造版本实体。"""
    return ToolVersion(
        tool_id=tool_id or uuid.uuid4(),
        version=version,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        status=status,
        traffic_weight=weight,
    )


def _make_client(service: AsyncMock | None = None, auth: bool = True) -> TestClient:
    """构建 tools 路由 TestClient（auth=False 构造未认证客户端）。"""
    app = FastAPI()
    app.add_middleware(ExceptionContextMiddleware)
    register_exception_handlers(app)
    kwargs: dict[str, Any] = {"tool_version_service": service or AsyncMock(spec=ToolVersionServicePort)}
    if auth:

        def _override() -> TokenPayload:
            return _make_token()

        kwargs["get_current_user_override"] = _override
    app.include_router(create_tools_router(**kwargs))
    return TestClient(app)


TID = str(uuid.uuid4())


class TestRegisterEndpoint:
    """POST /versions（201 / 400(242) / 404(380) / 409(431/397)）。"""

    def test_register_201(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.register_version = AsyncMock(return_value=_make_tv(status=ToolVersionStatus.PENDING, weight=0))
        resp = _make_client(svc).post(
            f"/api/v1/tools/{TID}/versions",
            json={"version": "1.1.0", "input_schema": {}, "output_schema": {}},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        for field in ("version_id", "tool_id", "version", "status", "created_at"):
            assert field in data

    def test_register_409_431(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.register_version = AsyncMock(side_effect=ToolVersionAlreadyExistsError(tool_id=TID, version="1.1.0"))
        resp = _make_client(svc).post(
            f"/api/v1/tools/{TID}/versions",
            json={"version": "1.1.0", "input_schema": {}, "output_schema": {}},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "EXCEPTION_431"

    def test_register_409_397(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.register_version = AsyncMock(
            side_effect=ToolSchemaCompatibilityError(
                tool_id=TID, old_version="1.0.0", new_version="2.0.0", breaking_changes=[{"s": "critical"}]
            )
        )
        resp = _make_client(svc).post(
            f"/api/v1/tools/{TID}/versions",
            json={"version": "2.0.0", "input_schema": {}, "output_schema": {}},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "EXCEPTION_397"

    def test_register_400_242_semver(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.register_version = AsyncMock(side_effect=EntityValidationError(message="version must match SemVer"))
        resp = _make_client(svc).post(
            f"/api/v1/tools/{TID}/versions",
            json={"version": "bad", "input_schema": {}, "output_schema": {}},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "EXCEPTION_242"

    def test_register_404_380(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.register_version = AsyncMock(side_effect=ToolNotFoundError(tool_id=TID))
        resp = _make_client(svc).post(
            f"/api/v1/tools/{TID}/versions",
            json={"version": "1.0.0", "input_schema": {}, "output_schema": {}},
        )
        assert resp.status_code == 404


class TestListEndpoint:
    """GET /versions（200 / 401 / 404）。"""

    def test_list_200(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.list_versions = AsyncMock(return_value=[_make_tv(version=v) for v in ("1.0.0", "1.1.0")])
        resp = _make_client(svc).get(f"/api/v1/tools/{TID}/versions")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2
        assert resp.json()["total"] == 2

    def test_list_401_no_auth(self) -> None:
        resp = _make_client(auth=False).get(f"/api/v1/tools/{TID}/versions")
        assert resp.status_code == 401


class TestBearerTokenPositivePath:
    """真实 Authorization 头解析路径（不经 override——锁 Depends(oauth2_scheme) 接线）。

    Round 1 审查 P0 回归防线：修复前 get_current_user 未挂 oauth2_scheme，
    Bearer 头永不解析，正路径任何 token 均 401。
    """

    VALID = "valid-bearer-token"

    def _make_auth_client(self) -> TestClient:
        """构建经 auth_service 二级路径（真实依赖工厂）的客户端。"""

        class _StubAuthService:
            """认证服务桩（固定 token 通过，其余抛领域认证异常）。"""

            async def verify_token(self, token: str) -> TokenPayload:
                if token != TestBearerTokenPositivePath.VALID:
                    from src.domain.ports.auth_service import AuthenticationError

                    raise AuthenticationError(f"无效 token: {token[:8]}")
                return _make_token()

        app = FastAPI()
        app.add_middleware(ExceptionContextMiddleware)
        register_exception_handlers(app)
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.list_versions = AsyncMock(return_value=[_make_tv(version="1.0.0")])
        app.include_router(
            create_tools_router(
                tool_version_service=svc,
                auth_service=_StubAuthService(),
            )
        )
        return TestClient(app)

    def test_bearer_header_positive_path_200(self) -> None:
        """合法 Bearer 头 → 认证通过（200/2xx 非 401）。"""
        client = self._make_auth_client()
        resp = client.get(f"/api/v1/tools/{TID}/versions", headers={"Authorization": f"Bearer {self.VALID}"})
        assert resp.status_code != 401, "合法 Bearer 头必须可达认证后端点"
        assert resp.status_code == 200

    def test_bearer_header_invalid_token_401(self) -> None:
        """非法 token → 401（Invalid token）。"""
        client = self._make_auth_client()
        resp = client.get(f"/api/v1/tools/{TID}/versions", headers={"Authorization": "Bearer wrong-token"})
        assert resp.status_code == 401

    def test_no_header_401_on_real_dependency(self) -> None:
        """无 Authorization 头 → 401（真实依赖路径）。"""
        client = self._make_auth_client()
        resp = client.get(f"/api/v1/tools/{TID}/versions")
        assert resp.status_code == 401

    def test_list_404_380(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.list_versions = AsyncMock(side_effect=ToolNotFoundError(tool_id=TID))
        resp = _make_client(svc).get(f"/api/v1/tools/{TID}/versions")
        assert resp.status_code == 404


class TestPublishEndpoint:
    """POST /versions/{version}/publish（200 / 400(432) / 404(430) / 409(243)）。"""

    def test_publish_200_canary(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.publish_version = AsyncMock(return_value=_make_tv(status=ToolVersionStatus.CANARY, weight=30))
        resp = _make_client(svc).post(f"/api/v1/tools/{TID}/versions/1.1.0/publish", json={"traffic_weight": 30})
        assert resp.status_code == 200
        assert resp.json()["status"] == "canary"

    def test_publish_400_432_constraint(self) -> None:
        """服务层发布约束冲突 → 400/432（如 canary_only 直接全量）。"""
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.publish_version = AsyncMock(
            side_effect=ToolVersionTrafficWeightError(tool_id=TID, version="2.0.0", conflict_reason="canary_only 直接全量")
        )
        resp = _make_client(svc).post(f"/api/v1/tools/{TID}/versions/2.0.0/publish", json={"traffic_weight": 100})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "EXCEPTION_432"

    def test_publish_400_weight_zero_rejected_by_contract(self) -> None:
        """权重域 (0,100] 契约：weight=0 在 Pydantic 层被拒（映射 400）。"""
        svc = AsyncMock(spec=ToolVersionServicePort)
        resp = _make_client(svc).post(f"/api/v1/tools/{TID}/versions/1.1.0/publish", json={"traffic_weight": 0})
        assert resp.status_code == 400  # 契约层校验（ge=1）先于服务层（统一 400）

    def test_publish_404_430(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.publish_version = AsyncMock(side_effect=ToolVersionNotFoundError(tool_id=TID, version="9.9.9"))
        resp = _make_client(svc).post(f"/api/v1/tools/{TID}/versions/9.9.9/publish", json={})
        assert resp.status_code == 404


class TestRollbackEndpoint:
    """POST /rollback（200 / 404(380/430) / 409(433)）。"""

    def test_rollback_200(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.rollback = AsyncMock(return_value=_make_tv(version="1.9.0", status=ToolVersionStatus.STABLE, weight=100))
        resp = _make_client(svc).post(f"/api/v1/tools/{TID}/rollback", json={})
        assert resp.status_code == 200

    def test_rollback_409_433(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.rollback = AsyncMock(side_effect=ToolVersionRollbackError(tool_id=TID, reason="no_stable_history"))
        resp = _make_client(svc).post(f"/api/v1/tools/{TID}/rollback")
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "EXCEPTION_433"
        assert body["error"]["message"]
        assert "request_id" in body

    def test_rollback_404_430_explicit_target(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.rollback = AsyncMock(side_effect=ToolVersionNotFoundError(tool_id=TID, version="9.9.9"))
        resp = _make_client(svc).post(f"/api/v1/tools/{TID}/rollback", json={"target_version": "9.9.9"})
        assert resp.status_code == 404


class TestAbortEndpoint:
    """POST /abort-canary（200 / 409(243)）。"""

    def test_abort_200(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.abort_canary = AsyncMock(return_value=_make_tv(status=ToolVersionStatus.DEPRECATED, weight=0))
        resp = _make_client(svc).post(f"/api/v1/tools/{TID}/abort-canary")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deprecated"

    def test_abort_404_380(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.abort_canary = AsyncMock(side_effect=ToolNotFoundError(tool_id=TID))
        resp = _make_client(svc).post(f"/api/v1/tools/{TID}/abort-canary")
        assert resp.status_code == 404


class TestTrafficEndpoint:
    """GET /versions/traffic（200 / 404）。"""

    def test_traffic_200(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.get_version_traffic = AsyncMock(
            return_value={"stable_version": "1.0.0", "canary_version": "1.1.0", "canary_weight": 30}
        )
        resp = _make_client(svc).get(f"/api/v1/tools/{TID}/versions/traffic")
        assert resp.status_code == 200
        data = resp.json()
        for field in ("stable_version", "canary_version", "canary_weight"):
            assert field in data

    def test_traffic_200_null_when_no_active(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.get_version_traffic = AsyncMock(
            return_value={"stable_version": None, "canary_version": None, "canary_weight": None}
        )
        resp = _make_client(svc).get(f"/api/v1/tools/{TID}/versions/traffic")
        assert resp.status_code == 200
        assert resp.json()["stable_version"] is None


class TestErrorBodyContract:
    """统一错误响应契约（error.code + error.message + request_id）。"""

    def test_error_body_structure(self) -> None:
        svc = AsyncMock(spec=ToolVersionServicePort)
        svc.rollback = AsyncMock(side_effect=ToolVersionRollbackError(tool_id=TID, reason="no_stable_history"))
        body = _make_client(svc).post(f"/api/v1/tools/{TID}/rollback").json()
        assert set(body.keys()) >= {"error", "request_id"}
        assert set(body["error"].keys()) >= {"code", "message"}
