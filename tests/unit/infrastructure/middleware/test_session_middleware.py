"""Unit tests for SessionMiddleware."""

from __future__ import annotations

from unittest import mock

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from src.infrastructure.middleware.session_middleware import SessionMiddleware
from src.infrastructure.storage.postgresql.session_context import get_session_optional


@pytest.fixture
def mock_session():
    """Mock AsyncSession."""
    session = mock.AsyncMock()
    session.commit = mock.AsyncMock()
    session.rollback = mock.AsyncMock()
    session.close = mock.AsyncMock()
    session.in_transaction = mock.MagicMock(return_value=True)
    return session


@pytest.fixture
def mock_factory(mock_session):
    """Mock session factory that returns mock_session."""
    factory = mock.MagicMock(return_value=mock_session)
    return factory


def _create_app(factory) -> Starlette:
    """Create Starlette app with SessionMiddleware."""
    app = Starlette()
    app.add_middleware(SessionMiddleware, session_factory=factory)
    return app


class TestSessionMiddleware:
    """SessionMiddleware unit tests."""

    def test_session_created_per_request(self, mock_factory, mock_session):
        """Each request should create a new session."""
        app = _create_app(mock_factory)

        @app.route("/test")
        async def handler(request):
            return PlainTextResponse("ok")

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        mock_factory.assert_called_once()
        mock_session.commit.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    def test_session_committed_on_success(self, mock_factory, mock_session):
        """Session should be committed on successful request."""
        app = _create_app(mock_factory)

        @app.route("/test")
        async def handler(request):
            return PlainTextResponse("ok")

        client = TestClient(app)
        client.get("/test")

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()

    def test_session_rolled_back_on_exception(self, mock_factory, mock_session):
        """Session should be rolled back on handler exception."""
        app = _create_app(mock_factory)

        @app.route("/test")
        async def handler(request):
            raise RuntimeError("boom")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test")

        assert response.status_code == 500
        mock_session.rollback.assert_awaited_once()
        mock_session.commit.assert_not_awaited()
        mock_session.close.assert_awaited_once()

    def test_session_closed_on_success(self, mock_factory, mock_session):
        """Session should always be closed."""
        app = _create_app(mock_factory)

        @app.route("/test")
        async def handler(request):
            return PlainTextResponse("ok")

        client = TestClient(app)
        client.get("/test")

        mock_session.close.assert_awaited_once()

    def test_session_closed_on_error(self, mock_factory, mock_session):
        """Session should be closed even when handler raises."""
        app = _create_app(mock_factory)

        @app.route("/test")
        async def handler(request):
            raise RuntimeError("boom")

        client = TestClient(app, raise_server_exceptions=False)
        client.get("/test")

        mock_session.close.assert_awaited_once()

    def test_contextvar_cleared_after_request(self, mock_factory, mock_session):
        """ContextVar should be reset after request completes."""
        app = _create_app(mock_factory)

        @app.route("/test")
        async def handler(request):
            return PlainTextResponse("ok")

        client = TestClient(app)
        client.get("/test")

        assert get_session_optional() is None

    def test_uow_managed_skips_commit(self, mock_factory, mock_session):
        """当 UoW 已管理事务（in_transaction=False）时，Middleware 不应 commit"""
        mock_session.in_transaction.return_value = False

        app = _create_app(mock_factory)

        @app.route("/test")
        async def handler(request):
            return PlainTextResponse("ok")

        client = TestClient(app)
        client.get("/test")

        mock_session.commit.assert_not_awaited()
        mock_session.rollback.assert_not_awaited()
        mock_session.close.assert_awaited_once()

    def test_uow_managed_skips_rollback_on_exception(self, mock_factory, mock_session):
        """当 UoW 已管理事务（in_transaction=False）且有异常时，Middleware 不应 rollback"""
        mock_session.in_transaction.return_value = False

        app = _create_app(mock_factory)

        @app.route("/test")
        async def handler(request):
            raise RuntimeError("boom")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test")

        assert response.status_code == 500
        mock_session.rollback.assert_not_awaited()
        mock_session.commit.assert_not_awaited()
        mock_session.close.assert_awaited_once()

    def test_uow_not_used_commits_normally(self, mock_factory, mock_session):
        """当 UoW 未使用时（in_transaction=True），Middleware 正常 commit"""
        mock_session.in_transaction.return_value = True

        app = _create_app(mock_factory)

        @app.route("/test")
        async def handler(request):
            return PlainTextResponse("ok")

        client = TestClient(app)
        client.get("/test")

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()
        mock_session.close.assert_awaited_once()
