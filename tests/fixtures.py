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
from typing import TypeVar

import pytest

from src.domain.ports.resolver import Resolver
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

    整个测试会话使用相同的配置
    """
    return get_test_env()


# =============================================================================
# Function 级 fixture - 租户隔离
# =============================================================================


@pytest.fixture
def test_tenant() -> TestTenant:
    """Function 级测试租户

    每个测试函数使用唯一的租户 ID
    """
    return generate_test_tenant()


@pytest.fixture
def isolated_tenant(test_tenant: TestTenant) -> Generator[TestTenant, None, None]:
    """隔离的测试租户（设置到上下文）

    将租户设置为当前上下文，确保资源使用正确的隔离前缀
    """
    TenantContext.set_current_tenant(test_tenant)
    yield test_tenant
    TenantContext.clear_current_tenant()


@pytest.fixture
def tenant_context_fixture(
    test_tenant: TestTenant,
) -> Generator[TestTenant, None, None]:
    """租户上下文 fixture

    使用上下文管理器确保租户正确设置和清理
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

    env_config = get_test_env()

    # Redis 清理
    try:
        import redis

        redis_client = redis.Redis(
            host=env_config.redis.host,
            port=env_config.redis.port,
            decode_responses=True,
        )
        pattern = f"{tenant.redis_key_prefix}*"
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
            logger.debug(f"Cleaned {len(keys)} Redis keys for tenant {tenant.id}")
    except Exception as e:
        logger.error(f"Redis cleanup failed for tenant {tenant.id}: {e}")

    # PostgreSQL 清理
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=env_config.postgres.host,
            port=env_config.postgres.port,
            user=env_config.postgres.username,
            password=env_config.postgres.password,
            database=env_config.postgres.database,
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

        qdrant_client = QdrantClient(host=env_config.qdrant.host, port=env_config.qdrant.port)
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
            env_config.minio.endpoint,
            access_key=env_config.minio.access_key,
            secret_key=env_config.minio.secret_key,
            secure=env_config.minio.secure,
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
            env_config.neo4j.bolt_url,
            auth=(env_config.neo4j.username, env_config.neo4j.password),
        )
        with driver.session() as session:
            # 使用参数化查询避免注入
            session.run("MATCH (n) WHERE n.tenant_id = $tenant_id DETACH DELETE n", tenant_id=tenant.id)
            logger.debug(f"Cleaned Neo4j data for tenant {tenant.id}")
        driver.close()
    except Exception as e:
        logger.error(f"Neo4j cleanup failed for tenant {tenant.id}: {e}")

    # RabbitMQ 清理
    try:
        import importlib

        pika = importlib.import_module("pika")

        credentials = pika.PlainCredentials(env_config.rabbitmq.username, env_config.rabbitmq.password)
        parameters = pika.ConnectionParameters(
            host=env_config.rabbitmq.host, port=env_config.rabbitmq.port, credentials=credentials
        )
        connection = pika.BlockingConnection(parameters)
        _channel = connection.channel()

        # 列出所有队列并删除匹配前缀的队列
        prefix = tenant.rabbitmq_queue_prefix
        result = _channel.queue_declare("", passive=True)
        for q in result:
            if q.name.startswith(prefix):
                _channel.queue_delete(q.name)
                logger.debug(f"Cleaned RabbitMQ queue {q.name} for tenant {tenant.id}")

        connection.close()
    except Exception as e:
        logger.error(f"RabbitMQ cleanup failed for tenant {tenant.id}: {e}")


def _cleanup_tenant_resources_sync(tenant: TestTenant) -> None:
    """同步版本的清理函数"""
    try:
        # 获取当前运行中的循环
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 没有运行中的循环，创建新的
        asyncio.run(_cleanup_tenant_resources(tenant))
        return

    # 有运行中的循环，使用 create_task 方式
    async def _run_cleanup():
        await _cleanup_tenant_resources(tenant)

    try:
        # 创建一个 future 并在当前循环中运行
        task = loop.create_task(_run_cleanup())
        # 等待任务完成（阻塞）
        loop.run_until_complete(task)
    except RuntimeError:
        # 作为最后的手段，使用线程池
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _cleanup_tenant_resources(tenant))
            future.result()


@pytest.fixture
def cleanup_test_tenant(test_tenant: TestTenant) -> Generator[TestTenant, None, None]:
    """自动清理租户资源的 fixture

    在测试完成后自动清理租户的所有资源
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

    在测试会话开始前清理可能存在的旧测试资源
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

    每个测试函数前后重置全局状态，防止测试间污染
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

    用于并行测试时生成唯一的资源名称
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


# =============================================================================
# Resolver Fixture - 统一端口管理
# =============================================================================
T = TypeVar("T")


@pytest.fixture
def resolver() -> Resolver:
    """通过 Resolver 获取端口实例（统一端口管理）

    所有验收测试应通过此 fixture 访问接口，保证测试与生产环境一致的接口管理

    用法::

        def test_something(resolver):
            service = resolver.resolve("my_service")
            result = await service.do_something()
            assert result is not None

    注意:
        - 此 fixture 依赖 session 级 bootstrap() fixture（conftest.py）
        - 获取的是全局单例实例
        - 如需覆盖默认实现，传入 overrides 参数
    """
    from src.domain.ports.resolver import Resolver

    return Resolver()


def resolve_port(resolver: Resolver, port_name: str, interface: type[T]) -> T:
    """解析端口并返回正确类型（用于 fixture 返回类型推导）"""
    return resolver.resolve(port_name, interface)
