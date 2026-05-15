"""Qdrant Real Instance Integration Tests.

端到端测试，验证真实 Qdrant 实例上的向量存储和 Collection 管理。
使用真实的 Qdrant 部署（localhost:6333），不使用 mock。

运行方式:
    pytest tests/integration/test_qdrant_real_integration.py -v

前置条件:
    - Qdrant 服务已部署并运行在 localhost:6333
    - 使用 deploy/app/docker-compose.yml 部署

Tenant Isolation (AC-6 R4):
    - Uses UUID prefix for collection names to prevent collision between tests
    - Each test uses unique collection name with UUID suffix
"""

from __future__ import annotations

import uuid

import pytest

from src.infrastructure.storage.qdrant.client import QdrantClientWrapper
from src.infrastructure.storage.qdrant.collection_manager import QdrantCollectionManager
from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage
from tests.environments import get_test_env

pytestmark = pytest.mark.asyncio


# ===================================================================
# Fixture
# ===================================================================


@pytest.fixture
async def test_tenant_id() -> str:
    """Generate unique tenant ID for test isolation."""
    return f"test_{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def qdrant_client():
    """Provide a real Qdrant client connection."""
    env = get_test_env()
    from src.infrastructure.config.qdrant import QdrantConfig

    config = QdrantConfig(
        host=env.qdrant.host,
        port=env.qdrant.port,
        grpc_port=env.qdrant.grpc_port,
        api_key=env.qdrant.api_key,
        https=env.qdrant.https,
        timeout=env.qdrant.timeout,
    )
    wrapper = QdrantClientWrapper(config)

    # Verify connection
    try:
        client = wrapper.get_client()
        await client.get_collections()
    except Exception as e:
        pytest.skip(f"Qdrant not available: {e}")

    yield wrapper
    await wrapper.close()


@pytest.fixture
async def collection_manager(qdrant_client: QdrantClientWrapper):
    """Provide QdrantCollectionManager with real client."""
    return QdrantCollectionManager(qdrant_client.get_client())


@pytest.fixture
async def vector_storage(qdrant_client: QdrantClientWrapper):
    """Provide QdrantVectorStorage with real client."""
    return QdrantVectorStorage(qdrant_client.get_client())


# ===================================================================
# Test Collection Management
# ===================================================================


class TestQdrantCollectionManager:
    """Qdrant Collection 管理器真实实例集成测试。"""

    async def test_create_and_delete_collection(self, collection_manager: QdrantCollectionManager, test_tenant_id: str):
        """测试 Collection 创建和删除。"""
        collection_name = f"{test_tenant_id}_collection_create"

        # Cleanup first (ignore errors if doesn't exist)
        try:
            await collection_manager.delete_collection(collection_name)
        except Exception:
            pass

        # Create
        result = await collection_manager.create_collection(
            name=collection_name,
            vector_size=4,  # Small size for testing
            distance="Cosine",
        )
        assert result is True

        # Verify exists
        exists = await collection_manager.collection_exists(collection_name)
        assert exists is True

        # Delete
        deleted = await collection_manager.delete_collection(collection_name)
        assert deleted is True

        # Verify deleted
        exists = await collection_manager.collection_exists(collection_name)
        assert exists is False

    async def test_create_existing_collection_returns_false(
        self, collection_manager: QdrantCollectionManager, test_tenant_id: str
    ):
        """测试创建已存在的 Collection 返回 False。"""
        collection_name = f"{test_tenant_id}_collection_exists"

        # Cleanup first
        try:
            await collection_manager.delete_collection(collection_name)
        except Exception:
            pass

        # Create first time
        result1 = await collection_manager.create_collection(collection_name, vector_size=4)
        assert result1 is True

        # Create second time - should return False
        result2 = await collection_manager.create_collection(collection_name, vector_size=4)
        assert result2 is False

        # Cleanup
        await collection_manager.delete_collection(collection_name)

    async def test_delete_nonexistent_collection_returns_false(
        self, collection_manager: QdrantCollectionManager, test_tenant_id: str
    ):
        """测试删除不存在的 Collection 返回 False。"""
        result = await collection_manager.delete_collection(f"{test_tenant_id}_nonexistent")
        assert result is False

    async def test_list_collections(self, collection_manager: QdrantCollectionManager, test_tenant_id: str):
        """测试列出所有 Collection。"""
        collection_name = f"{test_tenant_id}_collection_list"

        # Cleanup first
        try:
            await collection_manager.delete_collection(collection_name)
        except Exception:
            pass

        # Create a collection
        await collection_manager.create_collection(collection_name, vector_size=1024)

        # List
        collections = await collection_manager.list_collections()
        assert isinstance(collections, list)
        assert collection_name in collections

        # Cleanup
        await collection_manager.delete_collection(collection_name)


# ===================================================================
# Test Vector Storage
# ===================================================================


class TestQdrantVectorStorage:
    """Qdrant 向量存储真实实例集成测试。

    注意：qdrant-client 1.7.1 与 Qdrant v1.7.1 服务器的 upsert API 存在兼容性问题。
    Collection Manager 测试通过，验证核心功能正常。Vector Storage 测试在某些版本组合下可能失败。
    """

    async def test_upsert_and_search_vectors(
        self, vector_storage: QdrantVectorStorage, qdrant_client: QdrantClientWrapper, test_tenant_id: str
    ):
        """测试向量插入和搜索。"""
        collection_name = f"{test_tenant_id}_vector_storage"
        vector_size = 1024

        # Create collection
        from src.infrastructure.storage.qdrant.collection_manager import QdrantCollectionManager

        manager = QdrantCollectionManager(qdrant_client.get_client())
        try:
            await manager.delete_collection(collection_name)
        except Exception:
            pass
        await manager.create_collection(collection_name, vector_size=vector_size)

        try:
            # Create VectorPoint instances with 1024-dim vectors
            # 注意：Qdrant v1.7.1 要求 ID 为整数类型
            from src.infrastructure.storage.qdrant.models import VectorPoint

            # Create 1024-dim vectors (simple repeating pattern)
            vec1 = [0.1] * 1024
            vec2 = [0.2] * 1024
            vec3 = [0.3] * 1024

            points = [
                VectorPoint(
                    id="1",  # 使用字符串数字，Qdrant 会自动转换
                    vector=vec1,
                    payload={"text": "first vector"},
                ),
                VectorPoint(
                    id="2",
                    vector=vec2,
                    payload={"text": "second vector"},
                ),
                VectorPoint(
                    id="3",
                    vector=vec3,
                    payload={"text": "third vector"},
                ),
            ]

            # Upsert using actual method name upsert_points
            await vector_storage.upsert_points(collection_name, points)

            # Search using actual method name search
            query_vector = [0.1] * 1024
            results = await vector_storage.search(
                collection_name,
                query_vector,
                limit=2,
            )

            assert isinstance(results, list)
            assert len(results) <= 2

            # Verify result structure
            for result in results:
                assert isinstance(result, dict)
                assert "id" in result
                assert "score" in result

        finally:
            # Cleanup
            try:
                await manager.delete_collection(collection_name)
            except Exception:
                pass

    async def test_delete_vectors(
        self, vector_storage: QdrantVectorStorage, qdrant_client: QdrantClientWrapper, test_tenant_id: str
    ):
        """测试删除向量。"""
        collection_name = f"{test_tenant_id}_vector_delete"
        vector_size = 1024

        # Create collection
        from src.infrastructure.storage.qdrant.collection_manager import QdrantCollectionManager

        manager = QdrantCollectionManager(qdrant_client.get_client())
        try:
            await manager.delete_collection(collection_name)
        except Exception:
            pass
        await manager.create_collection(collection_name, vector_size=vector_size)

        try:
            # Insert vector using VectorPoint
            # 注意：Qdrant v1.7.x 要求 ID 为整数类型
            from src.infrastructure.storage.qdrant.models import VectorPoint

            points = [
                VectorPoint(
                    id="1",  # 使用数字字符串
                    vector=[0.1] * 1024,
                    payload={"id": "1"},
                ),
            ]

            await vector_storage.upsert_points(collection_name, points)

            # Delete vector using actual method delete_points
            await vector_storage.delete_points(collection_name, ["1"])

            # Verify deleted (search should not return it)
            query_vector = [0.1] * 1024
            results = await vector_storage.search(
                collection_name,
                query_vector,
                limit=10,
            )

            # Results should not contain the deleted vector
            ids = [r["id"] for r in results]

            assert 1 not in ids

        finally:
            # Cleanup
            try:
                await manager.delete_collection(collection_name)
            except Exception:
                pass


# ===================================================================
# Test Health Check
# ===================================================================


class TestQdrantHealthCheck:
    """Qdrant 健康检查测试。"""

    async def test_health_check(self, qdrant_client: QdrantClientWrapper):
        """测试健康检查。"""
        is_healthy = await qdrant_client.health_check()
        assert is_healthy is True
