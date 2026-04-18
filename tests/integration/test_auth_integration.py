"""Integration tests for Authentication and Authorization.

End-to-end tests for the complete auth flow.
Requires PostgreSQL running and accessible.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.config.auth import AuthConfig
from src.infrastructure.security.auth_service import (
    AuthServiceImpl,
    InvalidCredentialsError,
)
from src.infrastructure.security.encryption_service import EncryptionService
from src.infrastructure.security.jwt_service import JWTService
from src.infrastructure.security.role_service import RoleService
from src.infrastructure.storage.postgresql.engine import DatabaseEngine
from src.infrastructure.storage.postgresql.role_repository import RoleRepository
from src.infrastructure.storage.postgresql.user_repository import UserRepository

# Load .env file from project root
load_dotenv(Path(__file__).parent.parent.parent / ".env")


def is_postgres_available() -> bool:
    """Check if PostgreSQL is actually reachable."""
    try:
        from src.infrastructure.config.postgresql import PostgreSQLConfig

        config = PostgreSQLConfig.from_env()
        engine = DatabaseEngine(config)
        return asyncio.run(engine.health_check())
    except Exception:
        return False


def ensure_schema_created() -> None:
    """Create database schema if tables don't exist."""
    try:
        from src.infrastructure.config.postgresql import PostgreSQLConfig
        from src.infrastructure.storage.postgresql.models import Base

        config = PostgreSQLConfig.from_env()
        engine = DatabaseEngine(config)
        Base.metadata.create_all(engine.get_sync_engine())
    except Exception:
        # If schema creation fails, let tests fail naturally
        pass


# Skip if PostgreSQL is not actually available
pytestmark = pytest.mark.skipif(
    not is_postgres_available(),
    reason="PostgreSQL not available or not reachable",
)


class TestAuthIntegration:
    """Integration tests for authentication flow."""

    @pytest.fixture(scope="class")
    def event_loop(self):
        """Create event loop for async tests."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture(scope="class")
    def db_engine(self) -> DatabaseEngine:
        """Get database engine and ensure schema exists."""
        from src.infrastructure.config.postgresql import PostgreSQLConfig

        config = PostgreSQLConfig.from_env()
        engine = DatabaseEngine(config)
        ensure_schema_created()
        return engine

    @pytest.fixture
    async def session(self, db_engine: DatabaseEngine) -> AsyncGenerator[AsyncSession, None]:
        """Get database session."""
        async with db_engine.get_async_session() as sess:
            yield sess

    @pytest.fixture
    def auth_config(self) -> AuthConfig:
        """Get auth config."""
        return AuthConfig(
            jwt_secret_key="test-integration-secret-key",  # pragma: allowlist secret
            jwt_algorithm="HS256",
            jwt_expiration_hours=24,
            password_min_length=8,
            max_login_attempts=5,
            lockout_duration_minutes=30,
        )

    @pytest.fixture
    def encryption_service(self) -> EncryptionService:
        """Get encryption service."""
        return EncryptionService()

    @pytest.mark.asyncio
    async def test_user_registration_and_login(
        self,
        session: AsyncSession,
        auth_config: AuthConfig,
        encryption_service: EncryptionService,
    ):
        """Should register user and login successfully."""
        # Create repositories
        user_repo = UserRepository(session)
        role_repo = RoleRepository(session)

        # Create encryption service for password hashing
        password = "TestPass123!"  # pragma: allowlist secret
        hashed_password = encryption_service.hash_password(password)

        # Create test user
        from src.infrastructure.storage.postgresql.models.user import UserModel

        test_user = UserModel(
            id=uuid4(),
            username=f"testuser_{uuid4().hex[:8]}",
            email=f"test_{uuid4().hex[:8]}@example.com",
            hashed_password=hashed_password,
            is_active=True,
        )

        session.add(test_user)
        await session.flush()

        # Create auth service
        jwt_service = JWTService(auth_config)
        auth_service = AuthServiceImpl(
            user_repository=user_repo,
            role_repository=role_repo,
            jwt_service=jwt_service,
            config=auth_config,
        )

        # Login with correct password
        result = await auth_service.authenticate(test_user.username, password)

        assert "access_token" in result
        assert result["token_type"] == "bearer"
        assert result["user"]["username"] == test_user.username

        # Verify JWT token
        payload = await auth_service.verify_token(result["access_token"])
        assert payload["username"] == test_user.username

    @pytest.mark.asyncio
    async def test_login_wrong_password(
        self,
        session: AsyncSession,
        auth_config: AuthConfig,
    ):
        """Should fail login with wrong password."""
        user_repo = UserRepository(session)
        role_repo = RoleRepository(session)

        jwt_service = JWTService(auth_config)
        encryption_service = EncryptionService()

        password = "TestPass123!"  # pragma: allowlist secret
        hashed_password = encryption_service.hash_password(password)

        # Create test user
        from src.infrastructure.storage.postgresql.models.user import UserModel

        test_user = UserModel(
            id=uuid4(),
            username=f"testuser_{uuid4().hex[:8]}",
            email=f"test_{uuid4().hex[:8]}@example.com",
            hashed_password=hashed_password,
            is_active=True,
        )

        session.add(test_user)
        await session.flush()

        auth_service = AuthServiceImpl(
            user_repository=user_repo,
            role_repository=role_repo,
            jwt_service=jwt_service,
            config=auth_config,
        )

        # Try login with wrong password
        with pytest.raises(InvalidCredentialsError):
            await auth_service.authenticate(test_user.username, "WrongPassword!")


class TestRoleManagementIntegration:
    """Integration tests for role management."""

    @pytest.fixture(scope="class")
    def event_loop(self):
        """Create event loop for async tests."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture(scope="class")
    def db_engine(self) -> DatabaseEngine:
        """Get database engine and ensure schema exists."""
        from src.infrastructure.config.postgresql import PostgreSQLConfig

        config = PostgreSQLConfig.from_env()
        engine = DatabaseEngine(config)
        ensure_schema_created()
        return engine

    @pytest.fixture
    async def session(self, db_engine: DatabaseEngine) -> AsyncGenerator[AsyncSession, None]:
        """Get database session."""
        async with db_engine.get_async_session() as sess:
            yield sess

    @pytest.mark.asyncio
    async def test_create_and_query_role(self, session: AsyncSession):
        """Should create role and query it successfully."""
        role_service = RoleService(session)

        # Create role
        role = await role_service.create_role(
            name=f"test_role_{uuid4().hex[:8]}",
            description="Test role",
            permissions=["document:read", "document:write"],
        )

        assert role.name is not None
        assert "document:read" in role.permissions
        assert "document:write" in role.permissions

        # Query role
        fetched_role = await role_service.get_role_by_id(role.id)
        assert fetched_role is not None
        assert fetched_role.name == role.name

    @pytest.mark.asyncio
    async def test_update_role_permissions(self, session: AsyncSession):
        """Should update role permissions."""
        role_service = RoleService(session)

        # Create role
        role = await role_service.create_role(
            name=f"test_role_{uuid4().hex[:8]}",
            permissions=["document:read"],
        )

        # Add more permissions
        await role_service.assign_permission_to_role(role.id, "document:write")
        await role_service.assign_permission_to_role(role.id, "tool:execute")

        # Verify permissions
        permissions = await role_service.get_role_permissions(role.id)
        assert "document:read" in permissions
        assert "document:write" in permissions
        assert "tool:execute" in permissions

    @pytest.mark.asyncio
    async def test_delete_role_soft_delete(self, session: AsyncSession):
        """Should soft delete role (set is_active=False)."""
        role_service = RoleService(session)

        # Create role
        role = await role_service.create_role(
            name=f"test_role_{uuid4().hex[:8]}",
        )

        role_id = role.id

        # Delete role
        await role_service.delete_role(role_id)

        # Role should not be returned by get_all_roles
        all_roles = await role_service.get_all_roles()
        role_names = [r.name for r in all_roles]
        assert role.name not in role_names

        # But should still exist in database
        fetched_role = await role_service.get_role_by_id(role_id)
        assert fetched_role is not None
        assert fetched_role.is_active is False
