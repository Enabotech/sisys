"""文档版本快照领域事件单元测试

测试 DocumentVersionSnapshotCreated 事件：
- 构造与默认字段
- event_type 自动注册
- 序列化/反序列化
- __post_init__ 设置 aggregate_id
"""

from __future__ import annotations

from uuid import UUID, uuid4

from src.domain.events.base import DomainEvent
from src.domain.events.document_events import DocumentVersionSnapshotCreated


class TestDocumentVersionSnapshotCreatedCreation:
    """测试事件构造"""

    def test_create_with_defaults(self) -> None:
        """使用默认字段创建事件"""
        event = DocumentVersionSnapshotCreated()

        assert event.event_type == "DocumentVersionSnapshotCreated"
        assert isinstance(event.event_id, UUID)
        assert isinstance(event.document_id, UUID)
        assert isinstance(event.snapshot_id, UUID)
        assert event.new_version == 0
        assert event.created_by == ""
        assert event.diff_summary == ""
        assert event.tenant_id == ""

    def test_create_with_all_fields(self) -> None:
        """使用所有字段创建事件"""
        document_id = uuid4()
        snapshot_id = uuid4()

        event = DocumentVersionSnapshotCreated(
            document_id=document_id,
            new_version=2,
            snapshot_id=snapshot_id,
            created_by="user-1",
            diff_summary="metadata changed",
            tenant_id="tenant-1",
        )

        assert event.document_id == document_id
        assert event.new_version == 2
        assert event.snapshot_id == snapshot_id
        assert event.created_by == "user-1"
        assert event.diff_summary == "metadata changed"
        assert event.tenant_id == "tenant-1"


class TestDocumentVersionSnapshotCreatedRegistration:
    """测试事件自动注册"""

    def test_registered_in_domain_event_registry(self) -> None:
        """事件应自动注册到 DomainEvent._registry"""
        assert "DocumentVersionSnapshotCreated" in DomainEvent._registry
        assert DomainEvent._registry["DocumentVersionSnapshotCreated"] is DocumentVersionSnapshotCreated


class TestDocumentVersionSnapshotCreatedPostInit:
    """测试 __post_init__ 逻辑"""

    def test_aggregate_id_set_to_document_id(self) -> None:
        """aggregate_id 应设置为 document_id"""
        document_id = uuid4()
        event = DocumentVersionSnapshotCreated(document_id=document_id)

        assert event.aggregate_id == document_id

    def test_aggregate_type_set_to_document(self) -> None:
        """aggregate_type 应设置为 'Document'"""
        event = DocumentVersionSnapshotCreated()

        assert event.aggregate_type == "Document"


class TestDocumentVersionSnapshotCreatedSerialization:
    """测试序列化/反序列化"""

    def test_to_dict_contains_all_fields(self) -> None:
        """to_dict() 应包含所有事件字段"""
        document_id = uuid4()
        snapshot_id = uuid4()

        event = DocumentVersionSnapshotCreated(
            document_id=document_id,
            new_version=2,
            snapshot_id=snapshot_id,
            created_by="user-1",
            diff_summary="metadata changed",
            tenant_id="tenant-1",
        )

        result = event.to_dict()

        assert result["event_type"] == "DocumentVersionSnapshotCreated"
        assert result["payload"]["document_id"] == str(document_id)
        assert result["payload"]["new_version"] == 2
        assert result["payload"]["snapshot_id"] == str(snapshot_id)
        assert result["payload"]["created_by"] == "user-1"
        assert result["payload"]["diff_summary"] == "metadata changed"
        assert result["payload"]["tenant_id"] == "tenant-1"

    def test_round_trip_serialization(self) -> None:
        """序列化再反序列化后应恢复原始事件"""
        document_id = uuid4()
        snapshot_id = uuid4()

        original = DocumentVersionSnapshotCreated(
            document_id=document_id,
            new_version=3,
            snapshot_id=snapshot_id,
            created_by="user-2",
            diff_summary="file content changed",
            tenant_id="tenant-2",
        )

        data = original.to_dict()
        restored = DomainEvent.from_dict(data)

        assert isinstance(restored, DocumentVersionSnapshotCreated)
        assert restored.event_type == "DocumentVersionSnapshotCreated"
        # from_dict 从 payload 反序列化 document_id 为 UUID
        assert str(restored.document_id) == str(document_id)
        assert restored.new_version == original.new_version
        assert str(restored.snapshot_id) == str(snapshot_id)
        assert restored.created_by == original.created_by
        assert restored.diff_summary == original.diff_summary
        assert restored.tenant_id == original.tenant_id
