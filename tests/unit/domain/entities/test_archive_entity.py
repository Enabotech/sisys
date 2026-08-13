"""StrategicArchive 实体单元测试

验证战略档案实体的创建、validate() 校验和各字段赋值。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.exceptions import EntityBusinessRuleError, EntityValidationError


class TestArchiveType:
    """ArchiveType 枚举测试"""

    def test_enum_values(self) -> None:
        """枚举值必须符合规范"""
        assert ArchiveType.ASSUMPTION.value == "assumption"
        assert ArchiveType.DECISION.value == "decision"
        assert ArchiveType.DEVIATION.value == "deviation"
        assert ArchiveType.EVIDENCE_PACKAGE.value == "evidence_package"

    def test_enum_membership(self) -> None:
        """枚举成员完整性"""
        members = {t.value for t in ArchiveType}
        assert members == {"assumption", "decision", "deviation", "evidence_package"}


class TestStrategicArchive:
    """StrategicArchive 实体测试"""

    def test_creation_defaults(self) -> None:
        """默认字段赋值"""
        archive_id = uuid.uuid4()
        archive = StrategicArchive(
            archive_id=archive_id,
            plan_id=uuid.uuid4(),
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
        )
        assert archive.archive_id == archive_id
        assert archive.archive_type == ArchiveType.ASSUMPTION
        assert archive.version == 1
        assert archive.assumptions == {}
        assert archive.decision_basis == {}
        assert archive.execution_deviation == {}
        assert archive.metadata_ref == ""
        assert archive.embedding_ref is None
        assert archive.blob_ref is None
        assert archive.graph_ref is None
        assert archive.deleted_at is None
        assert archive.metadata == {}

    def test_full_field_assignment(self) -> None:
        """完整字段赋值"""
        archive_id = uuid.uuid4()
        now = datetime.now(UTC)
        archive = StrategicArchive(
            archive_id=archive_id,
            plan_id=uuid.uuid4(),
            plan_type="BP",
            archive_type=ArchiveType.DECISION,
            created_by=uuid.uuid4(),
            version=3,
            assumptions={"market": "grow"},
            decision_basis={"scenario": "A"},
            execution_deviation={"cost": 0.1},
            metadata_ref="strategic_archives:test",
            embedding_ref="strategic_archive:test-id",
            blob_ref="test-uuid/test-key.json",
            graph_ref="test-node-id",
            created_at=now,
            archived_at=now,
            metadata={"ext": "extra"},
        )
        assert archive.plan_type == "BP"
        assert archive.archive_type == ArchiveType.DECISION
        assert archive.version == 3
        assert archive.assumptions == {"market": "grow"}
        assert archive.decision_basis == {"scenario": "A"}
        assert archive.execution_deviation == {"cost": 0.1}
        assert archive.embedding_ref == "strategic_archive:test-id"
        assert archive.blob_ref == "test-uuid/test-key.json"
        assert archive.graph_ref == "test-node-id"
        assert archive.metadata == {"ext": "extra"}

    def test_valid_archive_passes_validate(self) -> None:
        """有效档案通过校验"""
        archive = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            created_at=datetime.now(UTC),
            archived_at=datetime.now(UTC),
        )
        assert archive.validate() is True

    def test_validate_rejects_invalid_archive_id(self) -> None:
        """无效 archive_id 抛出 EntityValidationError"""
        from typing import Any, cast

        archive = StrategicArchive(
            archive_id=cast(Any, "not-a-uuid"),
            plan_id=uuid.uuid4(),
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
        )
        with pytest.raises(EntityValidationError):
            archive.validate()

    def test_validate_rejects_invalid_archive_type(self) -> None:
        """无效 archive_type 抛出 EntityValidationError"""
        from typing import Any, cast

        archive = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            plan_type="SP",
            archive_type=cast(Any, "invalid_type"),
        )
        with pytest.raises(EntityValidationError):
            archive.validate()

    def test_validate_rejects_created_after_archived(self) -> None:
        """created_at 晚于 archived_at 抛出 EntityBusinessRuleError"""
        created = datetime(2026, 12, 1, tzinfo=UTC)
        archived = datetime(2026, 1, 1, tzinfo=UTC)
        archive = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            created_at=created,
            archived_at=archived,
        )
        with pytest.raises(EntityBusinessRuleError):
            archive.validate()

    def test_validate_accepts_created_equal_archived(self) -> None:
        """created_at 等于 archived_at 通过校验"""
        now = datetime.now(UTC)
        archive = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            created_at=now,
            archived_at=now,
        )
        assert archive.validate() is True

    def test_validate_rejects_missing_plan_id_for_assumption(self) -> None:
        """assumption 类型缺少 plan_id 抛出 EntityBusinessRuleError"""
        archive = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=None,
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
        )
        with pytest.raises(EntityBusinessRuleError):
            archive.validate()

    def test_validate_allows_missing_plan_id_for_evidence_package(self) -> None:
        """evidence_package 类型允许 plan_id 为空"""
        archive = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=None,
            plan_type="",
            archive_type=ArchiveType.EVIDENCE_PACKAGE,
        )
        assert archive.validate() is True

    def test_not_frozen_allows_mutation(self) -> None:
        """实体非 frozen，允许创建后状态变更"""
        archive = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
        )
        archive.embedding_ref = "strategic_archive:test"
        archive.graph_ref = "graph-test"
        assert archive.embedding_ref == "strategic_archive:test"
        assert archive.graph_ref == "graph-test"
