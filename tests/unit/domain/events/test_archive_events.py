"""ArchiveCreated / ValidityPeriodSet / FactBecameStale 领域事件单元测试

验证事件的构造、序列化与反序列化、字段完整性。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.entities.strategic_archive import ArchiveType
from src.domain.events import ArchiveCreated, FactBecameStale, ValidityPeriodSet
from src.domain.events.base import DEFAULT_SCHEMA_VERSION, DomainEvent


class TestArchiveCreated:
    """ArchiveCreated 事件测试"""

    def test_is_domain_event(self) -> None:
        """必须是 DomainEvent 子类"""
        event = ArchiveCreated(archive_id=uuid.uuid4())
        assert isinstance(event, DomainEvent)

    def test_event_type(self) -> None:
        """event_type 必须为 ArchiveCreated"""
        event = ArchiveCreated(archive_id=uuid.uuid4())
        assert event.event_type == "ArchiveCreated"

    def test_aggregate_type(self) -> None:
        """aggregate_type 必须为 StrategicArchive"""
        event = ArchiveCreated(archive_id=uuid.uuid4())
        assert event.aggregate_type == "StrategicArchive"

    def test_aggregate_id_set(self) -> None:
        """aggregate_id 必须与 archive_id 一致"""
        archive_id = uuid.uuid4()
        event = ArchiveCreated(archive_id=archive_id)
        assert event.aggregate_id == archive_id

    def test_fields(self) -> None:
        """字段完整赋值"""
        archive_id = uuid.uuid4()
        plan_id = uuid.uuid4()
        event = ArchiveCreated(
            archive_id=archive_id,
            plan_id=plan_id,
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            has_embedding=True,
            has_blob=True,
            has_graph=True,
        )
        assert event.archive_id == archive_id
        assert event.plan_id == plan_id
        assert event.plan_type == "SP"
        assert event.archive_type == ArchiveType.ASSUMPTION
        assert event.has_embedding is True
        assert event.has_blob is True
        assert event.has_graph is True

    def test_default_flags(self) -> None:
        """默认 flags 为 False"""
        event = ArchiveCreated(archive_id=uuid.uuid4())
        assert event.has_embedding is False
        assert event.has_blob is False
        assert event.has_graph is False

    def test_schema_version(self) -> None:
        """Schema 版本为默认 v1.0.0"""
        event = ArchiveCreated(archive_id=uuid.uuid4())
        assert event.schema_version == DEFAULT_SCHEMA_VERSION

    def test_to_dict_includes_archive_fields(self) -> None:
        """to_dict 包含 archive 专属字段"""
        archive_id = uuid.uuid4()
        plan_id = uuid.uuid4()
        event = ArchiveCreated(
            archive_id=archive_id,
            plan_id=plan_id,
            plan_type="SP",
            archive_type=ArchiveType.DECISION,
            has_blob=True,
        )
        data = event.to_dict()
        assert data["event_type"] == "ArchiveCreated"
        assert data["aggregate_type"] == "StrategicArchive"
        assert data["aggregate_id"] == str(archive_id)
        payload = data["payload"]
        assert payload["archive_id"] == str(archive_id)
        assert payload["plan_id"] == str(plan_id)
        assert payload["plan_type"] == "SP"
        assert payload["archive_type"] == "decision"
        assert payload["has_embedding"] is False
        assert payload["has_blob"] is True
        assert payload["has_graph"] is False

    def test_from_dict_roundtrip(self) -> None:
        """序列化后反序列化完整还原"""
        archive_id = uuid.uuid4()
        plan_id = uuid.uuid4()
        event = ArchiveCreated(
            archive_id=archive_id,
            plan_id=plan_id,
            plan_type="BP",
            archive_type=ArchiveType.DEVIATION,
            has_embedding=True,
            has_blob=True,
            has_graph=True,
            source="test",
        )
        data = event.to_dict()
        restored = DomainEvent.from_dict(data)
        assert isinstance(restored, ArchiveCreated)
        assert restored.archive_id == str(archive_id)
        assert str(restored.plan_id) == str(plan_id)
        assert restored.plan_type == "BP"
        assert restored.archive_type == ArchiveType.DEVIATION
        assert restored.has_embedding is True
        assert restored.has_blob is True
        assert restored.has_graph is True

    def test_frozen(self) -> None:
        """事件必须为不可变"""
        import pytest

        event = ArchiveCreated(archive_id=uuid.uuid4())
        with pytest.raises(AttributeError):
            setattr(event, "plan_type", "BP")

    def test_auto_registered(self) -> None:
        """事件必须自动注册到 DomainEvent._registry"""
        assert "ArchiveCreated" in DomainEvent._registry
        assert DomainEvent._registry["ArchiveCreated"] is ArchiveCreated


class TestValidityPeriodSet:
    """ValidityPeriodSet 事件测试"""

    def test_is_domain_event(self) -> None:
        """必须是 DomainEvent 子类"""
        event = ValidityPeriodSet(archive_id=uuid.uuid4())
        assert isinstance(event, DomainEvent)

    def test_event_type(self) -> None:
        """event_type 必须为 ValidityPeriodSet"""
        event = ValidityPeriodSet(archive_id=uuid.uuid4())
        assert event.event_type == "ValidityPeriodSet"

    def test_aggregate_type(self) -> None:
        """aggregate_type 必须为 StrategicArchive"""
        event = ValidityPeriodSet(archive_id=uuid.uuid4())
        assert event.aggregate_type == "StrategicArchive"

    def test_aggregate_id_set(self) -> None:
        """aggregate_id 必须与 archive_id 一致（无条件赋值）"""
        archive_id = uuid.uuid4()
        event = ValidityPeriodSet(archive_id=archive_id)
        assert event.aggregate_id == archive_id

    def test_fields(self) -> None:
        """字段完整赋值"""
        archive_id = uuid.uuid4()
        plan_id = uuid.uuid4()
        now = datetime.now(UTC)
        event = ValidityPeriodSet(
            archive_id=archive_id,
            plan_id=plan_id,
            archive_type=ArchiveType.DECISION,
            valid_from=now,
            valid_until=datetime(2027, 12, 31, tzinfo=UTC),
        )
        assert event.archive_id == archive_id
        assert event.plan_id == plan_id
        assert event.archive_type == ArchiveType.DECISION
        assert event.valid_from == now
        assert event.valid_until == datetime(2027, 12, 31, tzinfo=UTC)

    def test_default_fields(self) -> None:
        """默认字段值"""
        archive_id = uuid.uuid4()
        event = ValidityPeriodSet(archive_id=archive_id)
        assert event.plan_id is None
        assert event.archive_type == ArchiveType.ASSUMPTION
        assert event.valid_from is None
        assert event.valid_until is None

    def test_schema_version(self) -> None:
        """Schema 版本为默认 v1.0.0"""
        event = ValidityPeriodSet(archive_id=uuid.uuid4())
        assert event.schema_version == DEFAULT_SCHEMA_VERSION

    def test_to_dict_includes_fields(self) -> None:
        """to_dict 包含有效期专属字段"""
        archive_id = uuid.uuid4()
        event = ValidityPeriodSet(
            archive_id=archive_id,
            plan_id=uuid.uuid4(),
            archive_type=ArchiveType.ASSUMPTION,
            valid_from=datetime(2026, 1, 1, tzinfo=UTC),
            valid_until=datetime(2027, 12, 31, tzinfo=UTC),
        )
        data = event.to_dict()
        assert data["event_type"] == "ValidityPeriodSet"
        assert data["aggregate_type"] == "StrategicArchive"
        payload = data["payload"]
        assert payload["archive_id"] == str(archive_id)
        assert payload["valid_from"] == "2026-01-01T00:00:00+00:00"
        assert payload["valid_until"] == "2027-12-31T00:00:00+00:00"

    def test_from_dict_roundtrip(self) -> None:
        """序列化后反序列化完整还原"""
        archive_id = uuid.uuid4()
        event = ValidityPeriodSet(
            archive_id=archive_id,
            plan_id=uuid.uuid4(),
            archive_type=ArchiveType.DEVIATION,
            valid_from=datetime(2026, 6, 1, tzinfo=UTC),
            valid_until=None,
        )
        data = event.to_dict()
        restored = DomainEvent.from_dict(data)
        assert isinstance(restored, ValidityPeriodSet)
        assert restored.archive_id == str(archive_id)
        assert restored.archive_type == ArchiveType.DEVIATION
        assert restored.valid_from == "2026-06-01T00:00:00+00:00"
        assert restored.valid_until is None

    def test_frozen(self) -> None:
        """事件必须为不可变"""
        event = ValidityPeriodSet(archive_id=uuid.uuid4())
        with pytest.raises(AttributeError):
            setattr(event, "archive_type", "invalid")

    def test_auto_registered(self) -> None:
        """事件必须自动注册到 DomainEvent._registry"""
        assert "ValidityPeriodSet" in DomainEvent._registry
        assert DomainEvent._registry["ValidityPeriodSet"] is ValidityPeriodSet


class TestFactBecameStale:
    """FactBecameStale 事件测试"""

    def test_is_domain_event(self) -> None:
        """必须是 DomainEvent 子类"""
        event = FactBecameStale(archive_id=uuid.uuid4(), stale_reason="expired")
        assert isinstance(event, DomainEvent)

    def test_event_type(self) -> None:
        """event_type 必须为 FactBecameStale"""
        event = FactBecameStale(archive_id=uuid.uuid4(), stale_reason="expired")
        assert event.event_type == "FactBecameStale"

    def test_aggregate_type(self) -> None:
        """aggregate_type 必须为 StrategicArchive"""
        event = FactBecameStale(archive_id=uuid.uuid4(), stale_reason="expired")
        assert event.aggregate_type == "StrategicArchive"

    def test_aggregate_id_set(self) -> None:
        """aggregate_id 必须与 archive_id 一致"""
        archive_id = uuid.uuid4()
        event = FactBecameStale(archive_id=archive_id, stale_reason="expired")
        assert event.aggregate_id == archive_id

    def test_fields(self) -> None:
        """字段完整赋值"""
        archive_id = uuid.uuid4()
        plan_id = uuid.uuid4()
        now = datetime.now(UTC)
        event = FactBecameStale(
            archive_id=archive_id,
            plan_id=plan_id,
            archive_type=ArchiveType.ASSUMPTION,
            valid_until=datetime(2021, 1, 1, tzinfo=UTC),
            stale_since=now,
            stale_reason="expired",
        )
        assert event.archive_id == archive_id
        assert event.plan_id == plan_id
        assert event.archive_type == ArchiveType.ASSUMPTION
        assert event.valid_until == datetime(2021, 1, 1, tzinfo=UTC)
        assert event.stale_since == now
        assert event.stale_reason == "expired"

    def test_default_fields(self) -> None:
        """默认字段值"""
        event = FactBecameStale(archive_id=uuid.uuid4(), stale_reason="archived_too_long")
        assert event.plan_id is None
        assert event.archive_type == ArchiveType.ASSUMPTION
        assert event.valid_until is None
        assert event.stale_reason == "archived_too_long"

    def test_two_stale_reasons(self) -> None:
        """两种陈旧原因"""
        expired = FactBecameStale(archive_id=uuid.uuid4(), stale_reason="expired")
        assert expired.stale_reason == "expired"
        archived_long = FactBecameStale(archive_id=uuid.uuid4(), stale_reason="archived_too_long")
        assert archived_long.stale_reason == "archived_too_long"

    def test_to_dict_includes_fields(self) -> None:
        """to_dict 包含陈旧事件专属字段"""
        archive_id = uuid.uuid4()
        event = FactBecameStale(
            archive_id=archive_id,
            plan_id=uuid.uuid4(),
            archive_type=ArchiveType.ASSUMPTION,
            valid_until=datetime(2021, 1, 1, tzinfo=UTC),
            stale_reason="expired",
        )
        data = event.to_dict()
        assert data["event_type"] == "FactBecameStale"
        assert data["aggregate_type"] == "StrategicArchive"
        payload = data["payload"]
        assert payload["archive_id"] == str(archive_id)
        assert payload["stale_reason"] == "expired"

    def test_from_dict_roundtrip(self) -> None:
        """序列化后反序列化完整还原"""
        archive_id = uuid.uuid4()
        event = FactBecameStale(
            archive_id=archive_id,
            plan_id=uuid.uuid4(),
            archive_type=ArchiveType.DEVIATION,
            valid_until=None,
            stale_reason="archived_too_long",
        )
        data = event.to_dict()
        restored = DomainEvent.from_dict(data)
        assert isinstance(restored, FactBecameStale)
        assert restored.archive_id == str(archive_id)
        assert restored.archive_type == ArchiveType.DEVIATION
        assert restored.stale_reason == "archived_too_long"
        assert restored.valid_until is None

    def test_frozen(self) -> None:
        """事件必须为不可变"""
        event = FactBecameStale(archive_id=uuid.uuid4(), stale_reason="expired")
        with pytest.raises(AttributeError):
            setattr(event, "stale_reason", "invalid")

    def test_auto_registered(self) -> None:
        """事件必须自动注册到 DomainEvent._registry"""
        assert "FactBecameStale" in DomainEvent._registry
        assert DomainEvent._registry["FactBecameStale"] is FactBecameStale
