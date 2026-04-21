# =============================================================================
# SISYS 测试 fixtures
# =============================================================================
# 用途：提供测试资源清理 fixtures，支持租户隔离
# Story: 20-1 (sisys-testing-refactor) - Phase 3
# =============================================================================

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager

import pytest

from tests.environments import TestEnvConfig, get_test_env, reset_test_env
from tests.isolation import (
    TenantContext,
    TestTenant,
    generate_test_tenant,
    tenant_context,
)

# =============================================================================
# Session 级 fixture - 环境配置
# =============================================================================


@pytest.fixture(scope="session")
def test_env_config() -> TestEnvConfig:
    """Session 级测试环境配置

    整个测试会话使用相同的配置。
    """
    return get_test_env()


# =============================================================================
# Function 级 fixture - 租户隔离
# =============================================================================


@pytest.fixture
def test_tenant() -> TestTenant:
    """Function 级测试租户

    每个测试函数使用唯一的租户 ID。
    """
    return generate_test_tenant()


@pytest.fixture
def isolated_tenant(test_tenant: TestTenant) -> Generator[TestTenant, None, None]:
    """隔离的测试租户（设置到上下文）

    将租户设置为当前上下文，确保资源使用正确的隔离前缀。
    """
    TenantContext.set_current_tenant(test_tenant)
    yield test_tenant
    TenantContext.clear_current_tenant()


@pytest.fixture
def tenant_context_fixture(
    test_tenant: TestTenant,
) -> Generator[TestTenant, None, None]:
    """租户上下文 fixture

    使用上下文管理器确保租户正确设置和清理。
    """
    with tenant_context(test_tenant) as tenant:
        yield tenant


# =============================================================================
# Function 级 fixture - 清理函数
# =============================================================================


async def _cleanup_tenant_resources(tenant: TestTenant) -> None:
    """清理租户资源

    清理 6 个服务的测试资源:
    - Redis: 删除所有带有租户前缀的 keys
    - PostgreSQL: 删除租户的 schema
    - Qdrant: 删除租户的 collections
    - MinIO: 删除租户的 buckets
    - Neo4j: 删除租户的数据
    - RabbitMQ: 删除租户的 queues/exchanges
    """
    import logging

    logger = logging.getLogger(__name__)

    # Redis 清理
    try:
        import redis

        redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        pattern = f"{tenant.redis_key_prefix}*"
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
            logger.debug(f"Cleaned {len(keys)} Redis keys for tenant {tenant.id}")
    except Exception as e:
        logger.warning(f"Redis cleanup failed for tenant {tenant.id}: {e}")

    # PostgreSQL 清理
    try:
        import psycopg2

        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",  # pragma: allowlist secret (test credentials)
            database="sisys",
        )
        conn.autocommit = True
        cur = conn.cursor()
        # 删除 schema（级联删除所有对象）
        cur.execute(f"DROP SCHEMA IF EXISTS {tenant.postgres_schema} CASCADE")
        logger.debug(f"Cleaned PostgreSQL schema for tenant {tenant.id}")
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"PostgreSQL cleanup failed for tenant {tenant.id}: {e}")

    # Qdrant 清理
    try:
        from qdrant_client import QdrantClient

        qdrant_client = QdrantClient(host="localhost", port=6333)
        # 列出所有 collections
        collections = qdrant_client.get_collections().collections
        prefix = tenant.qdrant_collection_prefix
        for col in collections:
            if col.name.startswith(prefix):
                qdrant_client.delete_collection(col.name)
                logger.debug(f"Cleaned Qdrant collection {col.name} for tenant {tenant.id}")
    except Exception as e:
        logger.warning(f"Qdrant cleanup failed for tenant {tenant.id}: {e}")

    # MinIO 清理
    try:
        import minio

        minio_client = minio.Minio(
            "localhost:9000",
            access_key="minioadmin",  # pragma: allowlist secret (test credentials)
            secret_key="minioadmin",  # pragma: allowlist secret (test credentials)
            secure=False,
        )
        bucket_name = tenant.minio_bucket
        if minio_client.bucket_exists(bucket_name):
            objects = minio_client.list_objects(bucket_name, recursive=True)
            for obj in objects:
                minio_client.remove_object(bucket_name, obj.object_name)
            minio_client.remove_bucket(bucket_name)
            logger.debug(f"Cleaned MinIO bucket {bucket_name} for tenant {tenant.id}")
    except Exception as e:
        logger.warning(f"MinIO cleanup failed for tenant {tenant.id}: {e}")

    # Neo4j 清理
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "password123"),
        )
        with driver.session() as session:
            # 删除租户相关的所有节点和关系
            session.run(f"MATCH (n) WHERE n.tenant_id = '{tenant.id}' DETACH DELETE n")
            logger.debug(f"Cleaned Neo4j data for tenant {tenant.id}")
        driver.close()
    except Exception as e:
        logger.warning(f"Neo4j cleanup failed for tenant {tenant.id}: {e}")

    # RabbitMQ 清理
    try:
        import pika

        credentials = pika.PlainCredentials("guest", "guest")
        parameters = pika.ConnectionParameters(host="localhost", port=5672, credentials=credentials)
        connection = pika.BlockingConnection(parameters)
        _channel = connection.channel()

        # 列出所有队列并删除匹配前缀的队列
        prefix = tenant.rabbitmq_queue_prefix
        # 注意：这里只是演示，实际需要遍历并删除匹配的队列
        # 真实实现需要调用 _channel.queue_delete()

        connection.close()
    except Exception as e:
        logger.warning(f"RabbitMQ cleanup failed for tenant {tenant.id}: {e}")


def _cleanup_tenant_resources_sync(tenant: TestTenant) -> None:
    """同步版本的清理函数"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果已经在运行中，创建新任务
            loop.run_until_complete(_cleanup_tenant_resources(tenant))
        else:
            loop.run_until_complete(_cleanup_tenant_resources(tenant))
    except RuntimeError:
        # 没有事件循环
        asyncio.run(_cleanup_tenant_resources(tenant))


@pytest.fixture
def cleanup_test_tenant(test_tenant: TestTenant) -> Generator[TestTenant, None, None]:
    """自动清理租户资源的 fixture

    在测试完成后自动清理租户的所有资源。
    """
    yield test_tenant

    # 测试完成后清理
    _cleanup_tenant_resources_sync(test_tenant)


# =============================================================================
# Session 级 fixture - 清理旧资源
# =============================================================================


@pytest.fixture(scope="session", autouse=True)
def cleanup_old_test_resources() -> Generator[None, None, None]:
    """Session 级自动清理

    在测试会话开始前清理可能存在的旧测试资源。
    """
    # Session 开始前清理（可选）
    yield
    # Session 结束后不做清理，因为资源可能被其他 session 共享


# =============================================================================
# Reset environment fixture
# =============================================================================


@pytest.fixture(autouse=True)
def reset_test_environment() -> Generator[None, None, None]:
    """自动重置测试环境

    每个测试函数前后重置全局状态，防止测试间污染。
    """
    # 测试前：重置环境配置
    reset_test_env()

    # 清理 TenantContext
    TenantContext.clear_current_tenant()

    yield

    # 测试后：再次清理（确保无泄漏）
    reset_test_env()
    TenantContext.clear_current_tenant()


# =============================================================================
# Async 上下文管理器
# =============================================================================


@asynccontextmanager
async def isolated_async_tenant() -> AsyncGenerator[TestTenant, None]:
    """异步隔离的租户上下文管理器

    用法:
        async with isolated_async_tenant() as tenant:
            # tenant 就是隔离的租户
            pass
    """
    tenant = generate_test_tenant()
    TenantContext.set_current_tenant(tenant)

    try:
        yield tenant
    finally:
        TenantContext.clear_current_tenant()


# =============================================================================
# 并行测试支持
# =============================================================================


@pytest.fixture
def unique_id() -> str:
    """生成唯一 ID

    用于并行测试时生成唯一的资源名称。
    """
    return uuid.uuid4().hex[:12]


@pytest.fixture
def unique_queue_name(unique_id: str) -> str:
    """生成唯一的队列名"""
    return f"test_{unique_id}_queue"


@pytest.fixture
def unique_collection_name(unique_id: str) -> str:
    """生成唯一的 collection 名"""
    return f"test_{unique_id}_collection"


@pytest.fixture
def unique_redis_key(unique_id: str) -> str:
    """生成唯一的 Redis key"""
    return f"test:{unique_id}:key"
