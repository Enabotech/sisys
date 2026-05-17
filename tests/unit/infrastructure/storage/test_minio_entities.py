"""MinIO 实体测试 — ObjectMetadata / LifecycleRule

TDD 红→绿→重构循环 B
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.infrastructure.storage.minio.entities import LifecycleRule, ObjectMetadata


class TestObjectMetadata:
    """ObjectMetadata 实体测试"""

    def test_create_minimal(self):
        """最小创建"""
        obj_id = uuid4()
        meta = ObjectMetadata(
            object_id=obj_id,
            bucket_name="raw-documents-test",
            object_key="test-file.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            etag="abc123",
        )
        assert meta.object_id == obj_id
        assert meta.bucket_name == "raw-documents-test"
        assert meta.object_key == "test-file.pdf"
        assert meta.content_type == "application/pdf"
        assert meta.size_bytes == 1024
        assert meta.etag == "abc123"
        assert meta.version_id is None
        assert meta.upload_id is None
        assert meta.uploaded_parts == []
        assert meta.worm_locked is False
        assert meta.retention_until is None
        assert meta.tags == {}

    def test_with_version_id(self):
        """带版本 ID 创建"""
        obj_id = uuid4()
        meta = ObjectMetadata(
            object_id=obj_id,
            bucket_name="raw-documents-test",
            object_key="test-file.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            etag="abc123",
            version_id="v1-abc",
        )
        assert meta.version_id == "v1-abc"

    def test_with_worm_lock(self):
        """带 WORM 锁定"""
        obj_id = uuid4()
        retention = datetime.now(UTC) + timedelta(days=2555)
        meta = ObjectMetadata(
            object_id=obj_id,
            bucket_name="audit-archives-test",
            object_key="audit-log.json",
            content_type="application/json",
            size_bytes=512,
            etag="def456",
            worm_locked=True,
            retention_until=retention,
        )
        assert meta.worm_locked is True
        assert meta.retention_until == retention

    def test_with_tags(self):
        """带标签"""
        obj_id = uuid4()
        meta = ObjectMetadata(
            object_id=obj_id,
            bucket_name="raw-documents-test",
            object_key="test-file.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            etag="abc123",
            tags={"env": "test", "team": "engineering"},
        )
        assert meta.tags["env"] == "test"
        assert meta.tags["team"] == "engineering"

    def test_multipart_state(self):
        """分片上传状态"""
        obj_id = uuid4()
        meta = ObjectMetadata(
            object_id=obj_id,
            bucket_name="raw-documents-test",
            object_key="large-file.zip",
            content_type="application/zip",
            size_bytes=1_000_000_000,
            etag="",
            upload_id="upload-123",
            uploaded_parts=[
                {"PartNumber": 1, "ETag": "etag-1"},
                {"PartNumber": 2, "ETag": "etag-2"},
            ],
        )
        assert meta.upload_id == "upload-123"
        assert len(meta.uploaded_parts) == 2

    def test_to_dict(self):
        """序列化为字典"""
        obj_id = uuid4()
        meta = ObjectMetadata(
            object_id=obj_id,
            bucket_name="raw-documents-test",
            object_key="test-file.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            etag="abc123",
            tags={"env": "test"},
        )
        d = meta.to_dict()
        assert d["object_id"] == str(obj_id)
        assert d["bucket_name"] == "raw-documents-test"
        assert d["tags"]["env"] == "test"

    def test_from_dict(self):
        """从字典反序列化"""
        obj_id = uuid4()
        data = {
            "object_id": str(obj_id),
            "bucket_name": "raw-documents-test",
            "object_key": "test-file.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
            "etag": "abc123",
            "tags": {"env": "test"},
        }
        meta = ObjectMetadata.from_dict(data)
        assert meta.object_id == obj_id
        assert meta.tags["env"] == "test"


class TestLifecycleRule:
    """LifecycleRule 实体测试"""

    def test_create_expiration_rule(self):
        """创建过期规则"""
        rule = LifecycleRule(
            rule_id="expire-temp",
            status="Enabled",
            prefix="temp/",
            expiration_days=30,
        )
        assert rule.rule_id == "expire-temp"
        assert rule.status == "Enabled"
        assert rule.prefix == "temp/"
        assert rule.expiration_days == 30
        assert rule.transition_days is None
        assert rule.transition_storage_class is None

    def test_create_transition_rule(self):
        """创建转换规则"""
        rule = LifecycleRule(
            rule_id="transition-to-cold",
            status="Enabled",
            prefix="",
            expiration_days=None,
            transition_days=90,
            transition_storage_class="GLACIER",
        )
        assert rule.transition_days == 90
        assert rule.transition_storage_class == "GLACIER"

    def test_to_minio_dict(self):
        """转换为 MinIO 生命周期字典"""
        rule = LifecycleRule(
            rule_id="expire-temp",
            status="Enabled",
            prefix="temp/",
            expiration_days=30,
        )
        d = rule.to_minio_dict()
        assert d["ID"] == "expire-temp"
        assert d["Status"] == "Enabled"
        assert d["Expiration"]["Days"] == 30
