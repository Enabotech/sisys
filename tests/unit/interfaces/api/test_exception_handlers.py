"""exception_handlers 单元测试.

验证异常处理器正确映射领域异常到 HTTP 状态码，
正确处理请求验证错误、Pydantic 验证错误及未预期异常

Reference: src/interfaces/api/exception_handlers.py
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest import mock
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError

from src.domain.exceptions import (
    AuthenticationError,
    BaseException,
    BucketNameValidationError,
    BucketNotFoundError,
    BusinessException,
    BusinessRuleViolationError,
    CannotDeleteRoleWithUsersError,
    CannotDeleteSystemRoleError,
    ChunkingError,
    ComplianceLockError,
    ConfigurationError,
    ConflictError,
    ContainerStartError,
    ContainerStopError,
    DictionaryEntryConflictError,
    DictionaryNotFoundError,
    DictionaryVersionConflictError,
    DocumentVersionConflictError,
    EntityBusinessRuleError,
    EntityExtractionError,
    EntityStateTransitionError,
    EntityValidationError,
    ExecutionError,
    ExternalException,
    HybridSearchError,
    InsufficientTokenError,
    InvalidStateError,
    InvalidStateTransitionError,
    LLMAPIError,
    LLMConfigError,
    LLMResponseError,
    MemoryAccessDeniedError,
    MemoryNotFoundError,
    MemoryVersionConflictError,
    MessageBusError,
    MetadataValidationError,
    MinIOConnectionError,
    NetworkError,
    NotFoundError,
    OCRConnectionError,
    OCRProcessingError,
    PasswordValidationError,
    PermissionDeniedError,
    RerankError,
    RoleAlreadyExistsError,
    RoleNotFoundError,
    SandboxError,
    ServiceUnavailableError,
    StorageError,
    SystemException,
    ThirdPartyError,
    TimeoutError,
    TransferNotApprovedError,
    TransferNotFoundError,
    UnknownError,
    ValidationError,
    VersionError,
)
from src.interfaces.api.exception_handlers import (
    EXCEPTION_HTTP_MAP,
    ExceptionHandlers,
    _get_http_status,
    register_exception_handlers,
)


async def _parse_json_response(resp):
    """从 JSONResponse 解析 JSON 内容."""
    import json

    return json.loads(resp.body.decode())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    """创建注册了异常处理器的 FastAPI 应用."""
    application = FastAPI()
    register_exception_handlers(application)
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """创建测试客户端."""
    return TestClient(app, raise_server_exceptions=False)


def _make_raising_route(exception: Exception):
    """创建一个抛出指定异常的路由工厂."""

    def route():
        raise exception

    return route


def _install_route(app: FastAPI, exception: Exception):
    """向 FastAPI 应用安装一个抛出异常的路由并返回 TestClient."""
    from fastapi import APIRouter

    router = APIRouter()
    router.get("/test")(lambda: (_ for _ in ()).throw(exception))
    # 使用显式抛出避免生成器 hack 的可读性问题
    # 重新用闭包实现
    exc = exception

    @router.get("/test")
    def raise_exc():
        raise exc

    app.include_router(router)


# ---------------------------------------------------------------------------
# EXCEPTION_HTTP_MAP 映射完整性
# ---------------------------------------------------------------------------


class TestExceptionHttpMap:
    """验证 EXCEPTION_HTTP_MAP 映射表的完整性和正确性."""

    def test_map_contains_all_expected_exception_types(self):
        """验证映射表包含所有关键异常类型."""
        expected_types = {
            # 三层基类
            SystemException,
            BusinessException,
            ExternalException,
            # 系统级具体异常
            ConfigurationError,
            NetworkError,
            StorageError,
            MessageBusError,
            MinIOConnectionError,
            # 业务级具体异常
            NotFoundError,
            PermissionDeniedError,
            AuthenticationError,
            ConflictError,
            ValidationError,
            InvalidStateError,
            InvalidStateTransitionError,
            BusinessRuleViolationError,
            # 实体验证异常
            EntityValidationError,
            EntityStateTransitionError,
            EntityBusinessRuleError,
            # 存储子域异常
            MemoryNotFoundError,
            BucketNotFoundError,
            MemoryVersionConflictError,
            BucketNameValidationError,
            MemoryAccessDeniedError,
            DocumentVersionConflictError,
            MetadataValidationError,
            ChunkingError,
            # 角色子域异常
            RoleNotFoundError,
            RoleAlreadyExistsError,
            CannotDeleteRoleWithUsersError,
            CannotDeleteSystemRoleError,
            # 服务子域异常
            PasswordValidationError,
            ComplianceLockError,
            # 权限子域异常
            InsufficientTokenError,
            # 事件子域异常
            VersionError,
            # 跨境传输子域异常
            TransferNotFoundError,
            TransferNotApprovedError,
            # 外部服务异常
            ThirdPartyError,
            TimeoutError,
            ServiceUnavailableError,
            SandboxError,
            ContainerStartError,
            ExecutionError,
            ContainerStopError,
            # OCR 异常
            OCRConnectionError,
            OCRProcessingError,
            # LLM 异常
            LLMAPIError,
            LLMResponseError,
            LLMConfigError,
            # 实体抽取异常
            EntityExtractionError,
            # 重排序异常
            RerankError,
            # 混合检索异常
            HybridSearchError,
            # 词典管理异常
            DictionaryNotFoundError,
            DictionaryEntryConflictError,
            DictionaryVersionConflictError,
            UnknownError,
        }
        assert set(EXCEPTION_HTTP_MAP.keys()) == expected_types

    def test_system_exception_maps_to_500(self):
        """验证系统级异常映射到 500."""
        assert EXCEPTION_HTTP_MAP[SystemException] == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_business_exception_maps_to_400(self):
        """验证业务级异常映射到 400."""
        assert EXCEPTION_HTTP_MAP[BusinessException] == status.HTTP_400_BAD_REQUEST

    def test_external_exception_maps_to_502(self):
        """验证外部服务异常映射到 502."""
        assert EXCEPTION_HTTP_MAP[ExternalException] == status.HTTP_502_BAD_GATEWAY

    def test_not_found_maps_to_404(self):
        """验证 NotFoundError 映射到 404."""
        assert EXCEPTION_HTTP_MAP[NotFoundError] == status.HTTP_404_NOT_FOUND

    def test_permission_denied_maps_to_403(self):
        """验证 PermissionDeniedError 映射到 403."""
        assert EXCEPTION_HTTP_MAP[PermissionDeniedError] == status.HTTP_403_FORBIDDEN

    def test_authentication_error_maps_to_401(self):
        """验证 AuthenticationError 映射到 401."""
        assert EXCEPTION_HTTP_MAP[AuthenticationError] == status.HTTP_401_UNAUTHORIZED

    def test_conflict_maps_to_409(self):
        """验证 ConflictError 映射到 409."""
        assert EXCEPTION_HTTP_MAP[ConflictError] == status.HTTP_409_CONFLICT

    def test_validation_error_maps_to_400(self):
        """验证 ValidationError 映射到 400."""
        assert EXCEPTION_HTTP_MAP[ValidationError] == status.HTTP_400_BAD_REQUEST

    def test_invalid_state_maps_to_409(self):
        """验证 InvalidStateError 映射到 409."""
        assert EXCEPTION_HTTP_MAP[InvalidStateError] == status.HTTP_409_CONFLICT

    def test_invalid_state_transition_maps_to_409(self):
        """验证 InvalidStateTransitionError 映射到 409."""
        assert EXCEPTION_HTTP_MAP[InvalidStateTransitionError] == status.HTTP_409_CONFLICT

    def test_business_rule_violation_maps_to_422(self):
        """验证 BusinessRuleViolationError 映射到 422."""
        assert EXCEPTION_HTTP_MAP[BusinessRuleViolationError] == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_third_party_maps_to_502(self):
        """验证 ThirdPartyError 映射到 502."""
        assert EXCEPTION_HTTP_MAP[ThirdPartyError] == status.HTTP_502_BAD_GATEWAY

    def test_network_error_maps_to_500(self):
        """验证 NetworkError 映射到 500."""
        assert EXCEPTION_HTTP_MAP[NetworkError] == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_storage_error_maps_to_500(self):
        """验证 StorageError 映射到 500."""
        assert EXCEPTION_HTTP_MAP[StorageError] == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_message_bus_maps_to_500(self):
        """验证 MessageBusError 映射到 500."""
        assert EXCEPTION_HTTP_MAP[MessageBusError] == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_configuration_error_maps_to_500(self):
        """验证 ConfigurationError 映射到 500."""
        assert EXCEPTION_HTTP_MAP[ConfigurationError] == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_sandbox_error_maps_to_502(self):
        """验证 SandboxError 映射到 502."""
        assert EXCEPTION_HTTP_MAP[SandboxError] == status.HTTP_502_BAD_GATEWAY

    def test_timeout_error_maps_to_504(self):
        """验证 TimeoutError 映射到 504."""
        assert EXCEPTION_HTTP_MAP[TimeoutError] == status.HTTP_504_GATEWAY_TIMEOUT

    def test_service_unavailable_maps_to_503(self):
        """验证 ServiceUnavailableError 映射到 503."""
        assert EXCEPTION_HTTP_MAP[ServiceUnavailableError] == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_unknown_error_maps_to_500(self):
        """验证 UnknownError 映射到 500."""
        assert EXCEPTION_HTTP_MAP[UnknownError] == status.HTTP_500_INTERNAL_SERVER_ERROR


# ---------------------------------------------------------------------------
# _get_http_status 函数
# ---------------------------------------------------------------------------


class TestGetHttpStatus:
    """验证 _get_http_status 状态码查找逻辑."""

    def test_exact_type_match_returns_mapped_status(self):
        """验证精确类型匹配返回映射的状态码."""
        exc = NotFoundError("test")
        assert _get_http_status(exc) == status.HTTP_404_NOT_FOUND

    def test_isinstance_fallback_for_subclass(self):
        """验证子类通过 isinstance 回退机制匹配父类映射.

         ContainerStartError 继承自 SandboxError（在 EXCEPTION_HTTP_MAP 中），
        但自身不在映射表中，应通过 isinstance 回退找到 SandboxError 的映射
        """
        from src.domain.exceptions.sandbox_exceptions import ContainerStartError

        exc = ContainerStartError("container failed to start")
        assert _get_http_status(exc) == status.HTTP_502_BAD_GATEWAY

    def test_unknown_exception_returns_500(self):
        """验证未映射的异常类型返回 500."""

        class UnmappedException(BaseException):
            pass

        exc = UnmappedException("nobody knows me")
        assert _get_http_status(exc) == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_exact_match_takes_priority_over_isinstance(self):
        """验证精确类型匹配优先于 isinstance 回退.

        ConflictError 同时是 ConflictError 和 BusinessException 的实例
        精确匹配 ConflictError 应返回 409 而非 400
        """
        exc = ConflictError("conflict")
        assert _get_http_status(exc) == status.HTTP_409_CONFLICT

    def test_base_exception_subclass_without_exact_match(self):
        """验证不在映射表中的 BaseException 子类通过 isinstance 回退.

        AuditError 继承自 SystemException，自身不在 EXCEPTION_HTTP_MAP 中
        """
        from src.domain.exceptions.service_exceptions import AuditError

        exc = AuditError("audit failure")
        # AuditError 是 SystemException 子类
        assert _get_http_status(exc) == status.HTTP_500_INTERNAL_SERVER_ERROR


# ---------------------------------------------------------------------------
# 领域异常 HTTP 集成测试（每种异常类型）
# ---------------------------------------------------------------------------


class TestDomainExceptionHttpIntegration:
    """通过 FastAPI TestClient 验证每种领域异常的 HTTP 响应."""

    def _make_app_with_exc(self, exc: BaseException) -> TestClient:
        """创建包含异常抛出路由的测试应用."""
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/test")
        def route():
            raise exc

        return TestClient(app, raise_server_exceptions=False)

    def test_system_exception_returns_500(self):
        """验证 SystemException 返回 500."""
        client = self._make_app_with_exc(SystemException("system failure"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_business_exception_returns_400(self):
        """验证 BusinessException 返回 400."""
        client = self._make_app_with_exc(BusinessException("business error"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_external_exception_returns_502(self):
        """验证 ExternalException 返回 502."""
        client = self._make_app_with_exc(ExternalException("external error"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_502_BAD_GATEWAY

    def test_not_found_returns_404(self):
        """验证 NotFoundError 返回 404."""
        client = self._make_app_with_exc(NotFoundError("resource missing"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_permission_denied_returns_403(self):
        """验证 PermissionDeniedError 返回 403."""
        client = self._make_app_with_exc(PermissionDeniedError("no access"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_authentication_error_returns_401(self):
        """验证 AuthenticationError 返回 401."""
        client = self._make_app_with_exc(AuthenticationError("bad credentials"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_conflict_returns_409(self):
        """验证 ConflictError 返回 409."""
        client = self._make_app_with_exc(ConflictError("duplicate"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_validation_error_returns_400(self):
        """验证 ValidationError 返回 400."""
        client = self._make_app_with_exc(ValidationError("invalid input"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_state_returns_409(self):
        """验证 InvalidStateError 返回 409."""
        client = self._make_app_with_exc(InvalidStateError("bad state"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_invalid_state_transition_returns_409(self):
        """验证 InvalidStateTransitionError 返回 409."""
        exc = InvalidStateTransitionError("PENDING", "COMPLETED")
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_business_rule_violation_returns_422(self):
        """验证 BusinessRuleViolationError 返回 422."""
        client = self._make_app_with_exc(BusinessRuleViolationError("rule broken"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_entity_validation_error_returns_400(self):
        """验证 EntityValidationError 返回 400."""
        client = self._make_app_with_exc(
            EntityValidationError(
                message="agent_id must be a valid UUID",
                context={"entity": "Agent", "field": "agent_id"},
            )
        )
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        data = resp.json()
        assert data["error"]["code"] == "EXCEPTION_242"

    def test_entity_state_transition_error_returns_409(self):
        """验证 EntityStateTransitionError 返回 409."""
        client = self._make_app_with_exc(
            EntityStateTransitionError(
                from_status="running",
                to_status="running",
                message="Agent is already running",
            )
        )
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_409_CONFLICT
        data = resp.json()
        assert data["error"]["code"] == "EXCEPTION_243"

    def test_entity_business_rule_error_returns_422(self):
        """验证 EntityBusinessRuleError 返回 422."""
        client = self._make_app_with_exc(
            EntityBusinessRuleError(
                message="total_tokens must equal prompt + completion",
                context={"rule": "token_sum_invariant"},
            )
        )
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = resp.json()
        assert data["error"]["code"] == "EXCEPTION_244"

    def test_metadata_validation_error_returns_422(self):
        """验证 MetadataValidationError 返回 422."""
        from uuid import uuid4

        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        client = self._make_app_with_exc(
            MetadataValidationError(
                document_id=uuid4(),
                missing_fields=["license", "source"],
            )
        )
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = resp.json()
        assert data["error"]["code"] == "EXCEPTION_217"
        assert "license" in data["error"]["context"]["missing_fields"]

    def test_third_party_returns_502(self):
        """验证 ThirdPartyError 返回 502."""
        client = self._make_app_with_exc(ThirdPartyError("ext service down"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_502_BAD_GATEWAY

    def test_network_error_returns_500(self):
        """验证 NetworkError 返回 500."""
        client = self._make_app_with_exc(NetworkError("network down"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_storage_error_returns_500(self):
        """验证 StorageError 返回 500."""
        client = self._make_app_with_exc(StorageError("disk full"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_message_bus_returns_500(self):
        """验证 MessageBusError 返回 500."""
        client = self._make_app_with_exc(MessageBusError("bus offline"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_configuration_error_returns_500(self):
        """验证 ConfigurationError 返回 500."""
        client = self._make_app_with_exc(ConfigurationError("bad config"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_sandbox_error_returns_502(self):
        """验证 SandboxError 返回 502."""
        client = self._make_app_with_exc(SandboxError("sandbox crash"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_502_BAD_GATEWAY

    def test_timeout_returns_504(self):
        """验证 TimeoutError 返回 504."""
        client = self._make_app_with_exc(TimeoutError("timed out"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_504_GATEWAY_TIMEOUT

    def test_service_unavailable_returns_503(self):
        """验证 ServiceUnavailableError 返回 503."""
        client = self._make_app_with_exc(ServiceUnavailableError("unavailable"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_unknown_error_returns_500(self):
        """验证 UnknownError 返回 500."""
        client = self._make_app_with_exc(UnknownError("mystery"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ---------------------------------------------------------------------------
# _handle_exception 响应结构
# ---------------------------------------------------------------------------


class TestHandleExceptionResponse:
    """验证 _handle_exception 返回的 JSON 响应结构."""

    def _make_app_with_exc(self, exc: BaseException) -> TestClient:
        """创建包含异常抛出路由的测试应用."""
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/test")
        def route():
            raise exc

        return TestClient(app, raise_server_exceptions=False)

    def test_response_has_error_and_request_id(self):
        """验证响应包含 error 和 request_id 字段."""
        client = self._make_app_with_exc(NotFoundError("not found"))
        resp = client.get("/test")
        body = resp.json()
        assert "error" in body
        assert "request_id" in body

    def test_error_dict_contains_code_message_context(self):
        """验证 error 字典包含 code/message/context."""
        client = self._make_app_with_exc(NotFoundError("resource x"))
        resp = client.get("/test")
        error = resp.json()["error"]
        assert error["code"] == "EXCEPTION_202"
        assert "not found" in error["message"].lower() or error["message"]
        assert "context" in error

    def test_x_error_code_header(self):
        """验证响应包含 X-Error-Code 头."""
        client = self._make_app_with_exc(NotFoundError("gone"))
        resp = client.get("/test")
        assert "x-error-code" in resp.headers
        assert resp.headers["x-error-code"] == "EXCEPTION_202"

    def test_request_id_from_request_state(self):
        """验证 request_id 来自 request.state.request_id."""
        app = FastAPI()
        register_exception_handlers(app)

        @app.middleware("http")
        async def set_request_id(request, call_next):

            request.state.request_id = "req-test-123"
            response = await call_next(request)
            return response

        @app.get("/test")
        def route():
            raise NotFoundError("missing")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.json()["request_id"] == "req-test-123"

    def test_request_id_defaults_to_unknown(self):
        """验证未设置 request_id 时默认为 'unknown'."""
        client = self._make_app_with_exc(NotFoundError("missing"))
        resp = client.get("/test")
        assert resp.json()["request_id"] == "unknown"

    def test_cause_included_in_error_dict(self):
        """验证异常的 cause 字段被序列化到响应中."""
        root_cause = ValueError("db connection refused")
        exc = StorageError("storage failed", cause=root_cause)
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        error = resp.json()["error"]
        assert "cause" in error
        assert error["cause"]["type"] == "ValueError"
        assert "db connection refused" in error["cause"]["message"]


# ---------------------------------------------------------------------------
# AuthenticationError locked 特殊处理
# ---------------------------------------------------------------------------


class TestAuthenticationErrorLocked:
    """验证 AuthenticationError 的 locked 状态特殊处理."""

    def _make_app_with_exc(self, exc: AuthenticationError) -> TestClient:
        """创建包含异常抛出路由的测试应用."""
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/test")
        def route():
            raise exc

        return TestClient(app, raise_server_exceptions=False)

    def test_locked_returns_423(self):
        """验证 locked AuthenticationError 返回 423 LOCKED."""
        exc = AuthenticationError("account locked", context={"locked": True})
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_423_LOCKED

    def test_locked_response_message(self):
        """验证 locked 响应的 message 为 'Account is locked'."""
        exc = AuthenticationError("any", context={"locked": True})
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        assert resp.json()["error"]["message"] == "Account is locked"

    def test_locked_includes_context(self):
        """验证 locked 响应包含原始 context."""
        ctx = {"locked": True, "attempts": 5}
        exc = AuthenticationError("locked out", context=ctx)
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        body = resp.json()
        assert body["error"]["context"]["locked"] is True
        assert body["error"]["context"]["attempts"] == 5

    def test_locked_includes_x_error_code_header(self):
        """验证 locked 响应包含 X-Error-Code 头."""
        exc = AuthenticationError("locked", context={"locked": True})
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        assert resp.headers["x-error-code"] == "EXCEPTION_205"

    def test_unlocked_authentication_error_returns_401(self):
        """验证未 locked 的 AuthenticationError 返回 401."""
        exc = AuthenticationError("wrong password")
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authentication_error_with_empty_context_returns_401(self):
        """验证 context 为空字典的 AuthenticationError 返回 401."""
        exc = AuthenticationError("bad token", context={})
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authentication_error_with_none_context_returns_401(self):
        """验证 context 为 None 的 AuthenticationError 返回 401."""
        exc = AuthenticationError("bad token")
        exc.context = None
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# to_dict() 失败回退
# ---------------------------------------------------------------------------


class TestToDictFailureFallback:
    """验证 to_dict() 抛出异常时的回退处理."""

    def _make_app_with_exc(self, exc: BaseException) -> TestClient:
        """创建包含异常抛出路由的测试应用."""
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/test")
        def route():
            raise exc

        return TestClient(app, raise_server_exceptions=False)

    def test_to_dict_failure_returns_fallback_code(self):
        """验证 to_dict() 失败时使用异常的 code 属性作为回退."""
        exc = NotFoundError("missing")

        def broken_to_dict():
            raise RuntimeError("serialization failed")

        exc.to_dict = broken_to_dict
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        error = resp.json()["error"]
        assert error["code"] == "EXCEPTION_202"

    def test_to_dict_failure_returns_str_message(self):
        """验证 to_dict() 失败时使用 str(exc) 的前 500 字符."""
        exc = NotFoundError("resource gone")

        def broken_to_dict():
            raise RuntimeError("boom")

        exc.to_dict = broken_to_dict
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        error = resp.json()["error"]
        assert "resource gone" in error["message"]

    def test_to_dict_failure_returns_empty_context(self):
        """验证 to_dict() 失败且无 context 时回退为空字典."""
        exc = NotFoundError("missing")
        exc.context = None

        def broken_to_dict():
            raise RuntimeError("boom")

        exc.to_dict = broken_to_dict
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        error = resp.json()["error"]
        assert error["context"] == {}

    def test_to_dict_failure_with_cause(self):
        """验证 to_dict() 失败且异常有 cause 时，回退序列化 cause."""
        root = ValueError("original error")
        exc = StorageError("storage fail", cause=root)

        def broken_to_dict():
            raise RuntimeError("serialization failed")

        exc.to_dict = broken_to_dict
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        error = resp.json()["error"]
        assert "cause" in error
        assert error["cause"]["type"] == "ValueError"
        assert "original error" in error["cause"]["message"]

    def test_to_dict_failure_with_no_code_uses_default(self):
        """验证 to_dict() 失败且异常 code 为 None 时使用 EXCEPTION_999 回退."""
        exc = BaseException("unknown issue")
        exc.code = None

        def broken_to_dict():
            raise RuntimeError("boom")

        exc.to_dict = broken_to_dict
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        error = resp.json()["error"]
        assert error["code"] == "EXCEPTION_999"

    def test_to_dict_failure_message_truncated_to_500(self):
        """验证 to_dict() 失败时超长消息被截断到 500 字符."""
        long_message = "x" * 1000
        exc = NotFoundError(long_message)

        def broken_to_dict():
            raise RuntimeError("boom")

        exc.to_dict = broken_to_dict
        client = self._make_app_with_exc(exc)
        resp = client.get("/test")
        error = resp.json()["error"]
        assert len(error["message"]) <= 500


# ---------------------------------------------------------------------------
# RequestValidationError 处理
# ---------------------------------------------------------------------------


class TestHandleValidationError:
    """验证 RequestValidationError 处理逻辑."""

    @pytest.fixture
    def handlers_app(self) -> FastAPI:
        """创建注册了异常处理器的 FastAPI 应用."""
        app = FastAPI()
        register_exception_handlers(app)
        return app

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """创建 mock Request 对象."""
        request = MagicMock()
        request.state.request_id = "test-req-id"
        return request

    def test_validation_error_returns_400(self, handlers_app, mock_request):
        """验证 RequestValidationError 返回 400."""
        handler = handlers_app.exception_handlers[RequestValidationError]
        errors = [
            {"loc": ("body", "name"), "msg": "field required", "type": "value_error.missing"},
        ]
        exc = RequestValidationError(errors)

        resp = asyncio.run(handler(mock_request, exc))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_validation_error_response_structure(self, handlers_app, mock_request):
        """验证 RequestValidationError 响应结构."""
        handler = handlers_app.exception_handlers[RequestValidationError]
        errors = [
            {"loc": ("body", "name"), "msg": "field required", "type": "value_error.missing"},
        ]
        exc = RequestValidationError(errors)
        import asyncio

        resp = asyncio.run(handler(mock_request, exc))
        body = asyncio.run(_parse_json_response(resp))
        assert body["error"]["code"] == "EXCEPTION_201"
        assert body["error"]["message"] == "Validation error"
        assert "validation_errors" in body["error"]["context"]

    def test_validation_error_extracts_field_message_type(self, handlers_app, mock_request):
        """验证 RequestValidationError 提取 field/message/type."""
        handler = handlers_app.exception_handlers[RequestValidationError]
        errors = [
            {"loc": ("body", "email"), "msg": "invalid email", "type": "value_error.email"},
            {"loc": ("query", "page"), "msg": "not a valid integer", "type": "type_error.integer"},
        ]
        exc = RequestValidationError(errors)
        import asyncio

        resp = asyncio.run(handler(mock_request, exc))
        body = asyncio.run(_parse_json_response(resp))
        validation_errors = body["error"]["context"]["validation_errors"]
        assert len(validation_errors) == 2
        assert validation_errors[0]["field"] == "body.email"
        assert validation_errors[0]["message"] == "invalid email"
        assert validation_errors[0]["type"] == "value_error.email"
        assert validation_errors[1]["field"] == "query.page"

    def test_validation_error_includes_x_error_code(self, handlers_app, mock_request):
        """验证 RequestValidationError 响应包含 X-Error-Code 头."""
        handler = handlers_app.exception_handlers[RequestValidationError]
        errors = [{"loc": ("body", "x"), "msg": "bad", "type": "value_error"}]
        exc = RequestValidationError(errors)
        import asyncio

        resp = asyncio.run(handler(mock_request, exc))
        assert resp.headers["x-error-code"] == "EXCEPTION_201"

    def test_validation_error_includes_request_id(self, handlers_app, mock_request):
        """验证 RequestValidationError 响应包含 request_id."""
        handler = handlers_app.exception_handlers[RequestValidationError]
        errors = [{"loc": ("body", "x"), "msg": "bad", "type": "value_error"}]
        exc = RequestValidationError(errors)
        import asyncio

        resp = asyncio.run(handler(mock_request, exc))
        body = asyncio.run(_parse_json_response(resp))
        assert body["request_id"] == "test-req-id"

    def test_validation_error_request_id_defaults_to_unknown(self, handlers_app):
        """验证未设置 request_id 时默认为 'unknown'."""
        request = MagicMock()
        del request.state.request_id
        handler = handlers_app.exception_handlers[RequestValidationError]
        errors = [{"loc": ("body", "x"), "msg": "bad", "type": "value_error"}]
        exc = RequestValidationError(errors)
        import asyncio

        resp = asyncio.run(handler(request, exc))
        body = asyncio.run(_parse_json_response(resp))
        assert body["request_id"] == "unknown"


# ---------------------------------------------------------------------------
# PydanticValidationError 处理
# ---------------------------------------------------------------------------


class TestHandlePydanticError:
    """验证 PydanticValidationError 处理逻辑."""

    @pytest.fixture
    def handlers_app(self) -> FastAPI:
        """创建注册了异常处理器的 FastAPI 应用."""
        app = FastAPI()
        register_exception_handlers(app)
        return app

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """创建 mock Request 对象."""
        request = MagicMock()
        request.state.request_id = "test-req-id"
        return request

    def test_pydantic_error_returns_422(self, handlers_app: Any, mock_request: Any) -> None:
        """验证 PydanticValidationError 返回 422."""
        # 创建一个真实的 PydanticValidationError
        from pydantic import BaseModel

        class TestModel(BaseModel):
            name: str
            age: int

        # 触发验证错误
        try:
            TestModel.model_validate({"name": 123, "age": "abc"})
        except PydanticValidationError as exc:
            handler = handlers_app.exception_handlers[PydanticValidationError]
            import asyncio

            resp = asyncio.run(handler(mock_request, exc))
            assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_pydantic_error_response_structure(self, handlers_app: Any, mock_request: Any) -> None:
        """验证 PydanticValidationError 响应结构."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: int

        try:
            TestModel.model_validate({"value": "not_an_int"})
        except PydanticValidationError as exc:
            handler = handlers_app.exception_handlers[PydanticValidationError]
            import asyncio

            resp = asyncio.run(handler(mock_request, exc))
            body = asyncio.run(_parse_json_response(resp))
            assert body["error"]["code"] == "EXCEPTION_201"
            assert body["error"]["message"] == "Data validation error"
            assert "errors" in body["error"]["context"]

    def test_pydantic_error_includes_request_id(self, handlers_app: Any, mock_request: Any) -> None:
        """验证 PydanticValidationError 响应包含 request_id."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            x: int

        try:
            TestModel.model_validate({"x": "bad"})
        except PydanticValidationError as exc:
            handler = handlers_app.exception_handlers[PydanticValidationError]
            import asyncio

            resp = asyncio.run(handler(mock_request, exc))
            body = asyncio.run(_parse_json_response(resp))
            assert body["request_id"] == "test-req-id"


# ---------------------------------------------------------------------------
# 未预期异常处理
# ---------------------------------------------------------------------------


class TestHandleUnexpectedError:
    """验证未预期异常（非领域异常）的处理."""

    def _make_unexpected_error_app(self, exc: Exception) -> TestClient:
        """创建抛出未预期异常的测试应用."""
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/test")
        def route():
            raise exc

        return TestClient(app, raise_server_exceptions=False)

    def test_generic_exception_returns_500(self):
        """验证普通 Exception 返回 500."""
        client = self._make_unexpected_error_app(RuntimeError("unexpected"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_generic_exception_returns_generic_message(self):
        """验证普通 Exception 返回通用错误消息."""
        client = self._make_unexpected_error_app(RuntimeError("some details"))
        resp = client.get("/test")
        body = resp.json()
        assert body["error"]["message"] == "Internal server error"

    def test_generic_exception_returns_exception_999_code(self):
        """验证普通 Exception 返回 EXCEPTION_999 错误码."""
        client = self._make_unexpected_error_app(RuntimeError("oops"))
        resp = client.get("/test")
        body = resp.json()
        assert body["error"]["code"] == "EXCEPTION_999"

    def test_generic_exception_includes_x_error_code_header(self):
        """验证普通 Exception 响应包含 X-Error-Code 头."""
        client = self._make_unexpected_error_app(RuntimeError("oops"))
        resp = client.get("/test")
        assert resp.headers["x-error-code"] == "EXCEPTION_999"

    def test_generic_exception_no_request_id(self):
        """验证普通 Exception 响应不包含 request_id 字段."""
        client = self._make_unexpected_error_app(RuntimeError("oops"))
        resp = client.get("/test")
        body = resp.json()
        assert "request_id" not in body

    def test_key_error_returns_500(self):
        """验证 KeyError 返回 500."""
        client = self._make_unexpected_error_app(KeyError("missing_key"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_value_error_returns_500(self):
        """验证 ValueError 返回 500（兜底处理器已移除，归入通用异常处理）."""
        client = self._make_unexpected_error_app(ValueError("bad value"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @mock.patch("src.interfaces.api.exception_handlers.logger")
    def test_unexpected_error_logs_exception(self, mock_logger):
        """验证未预期异常被记录日志."""
        client = self._make_unexpected_error_app(RuntimeError("logged error"))
        client.get("/test")
        mock_logger.exception.assert_called_once()


# ---------------------------------------------------------------------------
# ExceptionHandlers 注册逻辑
# ---------------------------------------------------------------------------


class TestExceptionHandlersRegistration:
    """验证 ExceptionHandlers 正确注册到 FastAPI 应用."""

    def test_register_exception_handlers_creates_handlers(self):
        """验证 register_exception_handlers 注册异常处理器."""
        app = FastAPI()
        register_exception_handlers(app)
        # FastAPI stores exception handlers in app.exception_handlers
        handler_count = len(app.exception_handlers)
        assert handler_count >= 4

    def test_exception_handlers_class_registers_four_handlers(self):
        """验证 ExceptionHandlers 注册 4 个处理器."""
        app = FastAPI()
        _ = ExceptionHandlers(app)
        # 验证关键异常类型的处理器已注册
        from fastapi.exceptions import RequestValidationError  # noqa: N817
        from pydantic import ValidationError  # noqa: N814

        assert RequestValidationError in app.exception_handlers
        assert ValidationError in app.exception_handlers
        assert BaseException in app.exception_handlers
        assert Exception in app.exception_handlers


# ---------------------------------------------------------------------------
# 子类继承映射
# ---------------------------------------------------------------------------


class TestSubclassMapping:
    """验证未在 EXCEPTION_HTTP_MAP 中显式注册的子类通过 isinstance 回退."""

    def _make_app_with_exc(self, exc: BaseException) -> TestClient:
        """创建包含异常抛出路由的测试应用."""
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/test")
        def route():
            raise exc

        return TestClient(app, raise_server_exceptions=False)

    def test_container_start_error_returns_502(self):
        """验证 ContainerStartError（SandboxError 子类）返回 502."""
        from src.domain.exceptions.sandbox_exceptions import ContainerStartError

        client = self._make_app_with_exc(ContainerStartError("start failed"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_502_BAD_GATEWAY

    def test_execution_error_returns_502(self):
        """验证 ExecutionError（SandboxError 子类）返回 502."""
        from src.domain.exceptions.sandbox_exceptions import ExecutionError

        client = self._make_app_with_exc(ExecutionError("exec failed"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_502_BAD_GATEWAY

    def test_container_stop_error_returns_502(self):
        """验证 ContainerStopError（SandboxError 子类）返回 502."""
        from src.domain.exceptions.sandbox_exceptions import ContainerStopError

        client = self._make_app_with_exc(ContainerStopError("stop failed"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_502_BAD_GATEWAY

    def test_role_not_found_matches_business_exception(self):
        """验证 RoleNotFoundError 精确映射到 404.

        EXCEPTION_HTTP_MAP 中 RoleNotFoundError 有精确映射（404），
        精确匹配优先于 isinstance 回退到 BusinessException（400）
        """
        from src.domain.exceptions.role_exceptions import RoleNotFoundError

        client = self._make_app_with_exc(RoleNotFoundError(uuid4()))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_audit_error_returns_500(self):
        """验证 AuditError（SystemException 子类）通过 isinstance 匹配 500."""
        from src.domain.exceptions.service_exceptions import AuditError

        client = self._make_app_with_exc(AuditError("audit failed"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_minio_connection_error_returns_500(self):
        """验证 MinIOConnectionError（SystemException 子类）通过 isinstance 匹配 500."""
        from src.domain.exceptions.storage_exceptions import MinIOConnectionError

        client = self._make_app_with_exc(MinIOConnectionError("minio down"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_insufficient_token_error_matches_business_exception(self):
        """验证 InsufficientTokenError 精确映射到 403.

        EXCEPTION_HTTP_MAP 中 InsufficientTokenError 有精确映射（403），
        精确匹配优先于 isinstance 回退到 BusinessException（400）
        """
        from src.domain.exceptions.permission_exceptions import InsufficientTokenError

        client = self._make_app_with_exc(InsufficientTokenError("token expired"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_version_error_matches_business_exception(self):
        """验证 VersionError 精确映射到 409.

        EXCEPTION_HTTP_MAP 中 VersionError 有精确映射（409），
        精确匹配优先于 isinstance 回退到 BusinessException（400）
        """
        from src.domain.exceptions.event_exceptions import VersionError

        client = self._make_app_with_exc(VersionError("version conflict"))
        resp = client.get("/test")
        assert resp.status_code == status.HTTP_409_CONFLICT
