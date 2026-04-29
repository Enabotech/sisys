"""MinIO Real Instance Integration Tests.

端到端测试，验证真实 MinIO 实例上的对象存储和 Bucket 管理。
使用真实的 MinIO 部署（localhost:9000），不使用 mock。

运行方式:
    pytest tests/integration/test_minio_real_integration.py -v

前置条件:
    - MinIO 服务已部署并运行在 localhost:9000
    - 使用 deploy/app/docker-compose.yml 部署
"""

from __future__ import annotations

import io
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from src.infrastructure.config.minio import MinIOConfig
from src.infrastructure.storage.minio.bucket_manager import BucketManager
from src.infrastructure.storage.minio.client_adapter import MinioClientAdapter

# Load environment variables from .env file
load_dotenv(Path(__file__).parents[2] / ".env")

# Import reset_test_environment for test isolation (AC-6)

pytestmark = pytest.mark.asyncio


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def test_tenant_id() -> str:
    """Generate unique tenant ID for test isolation (uses hyphen for MinIO compatibility)."""
    return f"test-{uuid4().hex[:8]}"


@pytest.fixture
async def minio_config():
    """Provide MinIO configuration."""
    return MinIOConfig.from_env()


@pytest.fixture
async def minio_client(minio_config: MinIOConfig):
    """Provide MinIO client adapter."""
    client = MinioClientAdapter(minio_config)

    # Verify connection
    if not client.health_check():
        pytest.skip("MinIO not available")

    yield client


@pytest.fixture
async def bucket_manager(minio_config: MinIOConfig):
    """Provide BucketManager with real MinIO client."""
    return BucketManager(minio_config)


# ===================================================================
# Test MinIO Client Health Check
# ===================================================================


class TestMinioClientAdapter:
    """MinIO 客户端适配器真实实例测试。"""

    async def test_health_check(self, minio_client: MinioClientAdapter):
        """测试健康检查。"""
        result = minio_client.health_check()
        assert result is True

    async def test_client_connection(self, minio_client: MinioClientAdapter):
        """测试客户端连接。"""
        # Should be able to list buckets without error
        buckets = minio_client.client.list_buckets()
        assert isinstance(buckets, list)


# ===================================================================
# Test Bucket Management
# ===================================================================


class TestBucketManager:
    """Bucket 管理器真实实例测试。"""

    async def test_create_and_delete_bucket(self, bucket_manager: BucketManager, test_tenant_id: str):
        """测试 Bucket 创建和删除。"""
        bucket_name = f"sisys-documents-{test_tenant_id}"

        # Cleanup first
        bucket_manager.delete_bucket(bucket_name, force=True)

        # Create
        result = bucket_manager.create_bucket(bucket_name)
        assert result is True

        # Verify exists
        exists = bucket_manager.bucket_exists(bucket_name)
        assert exists is True

        # Delete
        deleted = bucket_manager.delete_bucket(bucket_name)
        assert deleted is True

        # Verify deleted
        exists = bucket_manager.bucket_exists(bucket_name)
        assert exists is False

    async def test_create_existing_bucket_returns_false(self, bucket_manager: BucketManager, test_tenant_id: str):
        """测试创建已存在的 Bucket 返回 False。"""
        bucket_name = f"sisys-exists-{test_tenant_id}"

        # Cleanup first
        bucket_manager.delete_bucket(bucket_name, force=True)

        # Create first time
        result1 = bucket_manager.create_bucket(bucket_name)
        assert result1 is True

        # Create second time - should return False
        result2 = bucket_manager.create_bucket(bucket_name)
        assert result2 is False

        # Cleanup
        bucket_manager.delete_bucket(bucket_name, force=True)

    async def test_delete_nonexistent_bucket_returns_false(self, bucket_manager: BucketManager, test_tenant_id: str):
        """测试删除不存在的 Bucket 返回 False。"""
        result = bucket_manager.delete_bucket(f"sisys-nonexistent-{test_tenant_id}")
        assert result is False

    async def test_list_buckets(self, bucket_manager: BucketManager, test_tenant_id: str):
        """测试列出所有 Bucket。"""
        bucket_name = f"sisys-list-{test_tenant_id}"

        # Cleanup first
        bucket_manager.delete_bucket(bucket_name, force=True)

        # Create a bucket
        bucket_manager.create_bucket(bucket_name)

        # List
        buckets = bucket_manager.list_buckets()
        assert isinstance(buckets, list)

        # Verify our bucket is in the list
        bucket_names = [b["name"] for b in buckets]
        assert bucket_name in bucket_names

        # Cleanup
        bucket_manager.delete_bucket(bucket_name, force=True)


# ===================================================================
# Test Object Operations (Basic)
# ===================================================================


class TestMinioObjectOperations:
    """MinIO 对象操作真实实例测试。"""

    async def test_bucket_creation_for_objects(self, minio_client: MinioClientAdapter, test_tenant_id: str):
        """测试对象操作前的 Bucket 创建。"""
        bucket_name = f"sisys-objects-{test_tenant_id}"

        # Cleanup
        try:
            minio_client.client.remove_bucket(bucket_name)
        except Exception:
            pass

        # Create bucket
        minio_client.client.make_bucket(bucket_name)

        # Verify exists
        buckets = minio_client.client.list_buckets()
        assert any(b.name == bucket_name for b in buckets)

        # Cleanup
        minio_client.client.remove_bucket(bucket_name)

    async def test_put_and_get_object(self, minio_client: MinioClientAdapter, test_tenant_id: str):
        """测试对象上传和下载。"""
        bucket_name = f"sisys-ops-{test_tenant_id}"
        object_name = "test-document.txt"
        content = b"Hello, MinIO!"

        # Cleanup bucket
        try:
            minio_client.client.remove_bucket(bucket_name)
        except Exception:
            pass

        # Create bucket
        minio_client.client.make_bucket(bucket_name)

        try:
            # Put object
            data = io.BytesIO(content)
            minio_client.client.put_object(
                bucket_name,
                object_name,
                data,
                length=len(content),
            )

            # Get object
            response = minio_client.client.get_object(bucket_name, object_name)
            loaded_content = response.read()
            assert loaded_content == content
            response.close()
            response.release_conn()

        finally:
            # Cleanup bucket
            try:
                minio_client.client.remove_object(bucket_name, object_name)
            except Exception:
                pass
            try:
                minio_client.client.remove_bucket(bucket_name)
            except Exception:
                pass
