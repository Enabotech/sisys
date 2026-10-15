"""共享认证依赖单元测试（Story 91-1 — API 认证守卫统一化）

覆盖 src/interfaces/api/auth_dependency.py 的 get_current_user_dependency：
- 认证失败三分支统一 raise AuthenticationError（EXCEPTION_205，统一异常体系
  接线——由 ExceptionHandlers 映射 401 + WWW-Authenticate header）
- verify_token 真实契约（raise AuthenticationError）透传 + 替身契约
  （返回 None / 其他异常）兜底兼容
- 工厂形态与既有 9 路由文件的 get_current_user_dependency 签名兼容

Run with:
    poetry run pytest tests/unit/interfaces/api/test_auth_dependency.py -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.domain.exceptions import AuthenticationError
from src.domain.value_objects.token_payload import TokenPayload
from src.interfaces.api.auth import get_current_user_dependency


def _make_token_payload() -> TokenPayload:
    """构造合法 TokenPayload 替身（结构对齐领域值对象）。"""
    return TokenPayload(
        user_id=uuid.uuid4(),
        username="tester",
        roles=("admin",),
        exp=datetime.now(UTC) + timedelta(hours=1),
    )


class TestGetCurrentUserDependency:
    """共享认证依赖工厂行为契约。"""

    @pytest.fixture
    def auth_service(self) -> Any:
        """认证服务替身（AsyncMock，verify_token 可编程）。"""
        service = type("StubAuthService", (), {})()
        service.verify_token = AsyncMock(return_value=_make_token_payload())
        return service

    async def test_no_token_raises_authentication_error(self, auth_service: Any) -> None:
        """无 token → AuthenticationError（205，消息 Not authenticated）。"""
        dependency = get_current_user_dependency(auth_service)
        with pytest.raises(AuthenticationError) as exc_info:
            await dependency(token=None)
        assert exc_info.value.code == "EXCEPTION_205"
        assert "Not authenticated" in str(exc_info.value.message)

    async def test_verify_token_domain_error_passes_through(self, auth_service: Any) -> None:
        """verify_token 抛 AuthenticationError（真实契约）→ 异常对象原样透传（同一性）。"""
        root = AuthenticationError(message="token expired")
        auth_service.verify_token = AsyncMock(side_effect=root)
        dependency = get_current_user_dependency(auth_service)
        with pytest.raises(AuthenticationError) as exc_info:
            await dependency(token="expired-token")
        assert exc_info.value is root, "透传形态=异常对象同一（不重新包装丢上下文）"

    async def test_verify_token_unexpected_error_wrapped(self, auth_service: Any) -> None:
        """verify_token 抛非领域异常（测试替身/实现漂移形态）→ 包装为 AuthenticationError。"""
        auth_service.verify_token = AsyncMock(side_effect=RuntimeError("stub drift"))
        dependency = get_current_user_dependency(auth_service)
        with pytest.raises(AuthenticationError) as exc_info:
            await dependency(token="any")
        assert exc_info.value.code == "EXCEPTION_205"

    async def test_verify_token_none_wrapped(self, auth_service: Any) -> None:
        """verify_token 返回 None（替身宽松契约）→ AuthenticationError（不静默放行）。"""
        auth_service.verify_token = AsyncMock(return_value=None)
        dependency = get_current_user_dependency(auth_service)
        with pytest.raises(AuthenticationError) as exc_info:
            await dependency(token="any")
        assert exc_info.value.code == "EXCEPTION_205"

    async def test_valid_token_returns_payload(self, auth_service: Any) -> None:
        """合法 token → 返回 TokenPayload 原对象。"""
        expected = _make_token_payload()
        auth_service.verify_token = AsyncMock(return_value=expected)
        dependency = get_current_user_dependency(auth_service)
        payload = await dependency(token="valid")
        assert payload is expected

    def test_factory_returns_callable(self, auth_service: Any) -> None:
        """工厂签名与既有 9 路由文件本地工厂兼容（接收 auth_service 返回依赖）。"""
        dependency = get_current_user_dependency(auth_service)
        assert callable(dependency)
