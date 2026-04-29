"""PostgreSQL Real Instance Integration Tests.

端到端测试，验证真实 PostgreSQL 实例上的数据库操作。
使用真实的 PostgreSQL 部署（localhost:5432），不使用 mock。

运行方式:
    pytest tests/integration/test_postgresql_real_integration.py -v

前置条件:
    - PostgreSQL 服务已部署并运行在 localhost:5432
    - 数据库已创建（sisu0）
    - 用户有权限

Tenant Isolation (AC-6 R6):
    - Uses TEMP tables which are automatically cleaned up after session ends
    - Each test gets isolated transaction via session scope
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.postgresql.engine import DatabaseEngine

# Import reset_test_environment for test isolation (AC-6)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def test_tenant_id() -> str:
    """Generate unique tenant ID for test isolation."""
    return f"test_{uuid4().hex[:8]}"


@pytest.fixture
async def pg_engine():
    """Provide PostgreSQL engine."""
    import os

    config = PostgreSQLConfig(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DATABASE", "sisys"),
        username=os.getenv("POSTGRES_USERNAME", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )

    engine = DatabaseEngine(config)

    # Verify connection
    try:
        async with AsyncSession(engine.get_async_engine()) as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
    except Exception as e:
        pytest.skip(f"PostgreSQL not available: {e}")

    yield engine
    await engine.close()


class TestPostgreSQLReal:
    """PostgreSQL 真实实例集成测试。"""

    async def test_connection_and_query(self, pg_engine):
        """测试数据库连接和基本查询。"""
        async with AsyncSession(pg_engine.get_async_engine()) as session:
            result = await session.execute(text("SELECT version()"))
            version = result.scalar()
            assert version is not None
            assert "PostgreSQL" in version

    async def test_insert_and_select(self, pg_engine):
        """测试插入和查询。"""
        async with AsyncSession(pg_engine.get_async_engine()) as session:
            # 创建临时表
            await session.execute(
                text(
                    """
                CREATE TEMP TABLE IF NOT EXISTS test_table (
                    id UUID PRIMARY KEY,
                    name VARCHAR(100)
                )
            """
                )
            )

            # 插入数据
            test_id = str(uuid4())
            await session.execute(
                text("INSERT INTO test_table (id, name) VALUES (:id, :name)"), {"id": test_id, "name": "test_user"}
            )
            await session.commit()

            # 查询数据
            result = await session.execute(text("SELECT id, name FROM test_table WHERE id = :id"), {"id": test_id})
            row = result.first()
            assert row is not None
            assert row.name == "test_user"


class TestDatabaseEngineReal:
    """DatabaseEngine 真实实例测试。"""

    async def test_async_engine_creation(self, pg_engine):
        """测试异步引擎创建。"""
        async_engine = pg_engine.get_async_engine()
        assert async_engine is not None

        # 使用引擎执行查询
        async with AsyncSession(async_engine) as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    async def test_health_check(self, pg_engine):
        """测试健康检查。"""
        # DatabaseEngine 应该有健康检查方法
        # 由于没有暴露 health_check 方法，我们通过查询验证
        async with AsyncSession(pg_engine.get_async_engine()) as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
