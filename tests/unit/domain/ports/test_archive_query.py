"""ArchiveQuery 值对象 + ValidityStatus 枚举单元测试

纯领域层值对象验证，与端口契约测试分离。
验证 ArchiveQuery 新字段（valid_from/valid_until/validity_status）和 ValidityStatus 枚举。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.domain.entities.strategic_archive import ArchiveType
from src.domain.ports.archive_repository import ArchiveQuery, ValidityStatus


class TestValidityStatus:
    """ValidityStatus 枚举测试"""

    def test_enum_values(self) -> None:
        """枚举值必须符合规范"""
        assert ValidityStatus.VALID.value == "valid"
        assert ValidityStatus.EXPIRED.value == "expired"

    def test_enum_membership(self) -> None:
        """枚举成员完整性"""
        members = {v.value for v in ValidityStatus}
        assert members == {"valid", "expired"}

    def test_no_all_member(self) -> None:
        """不包含 ALL 枚举值，None 表达"不过滤"语义"""
        assert not hasattr(ValidityStatus, "ALL")


class TestArchiveQueryValidityFields:
    """ArchiveQuery 有效期字段测试"""

    def test_valid_from_default(self) -> None:
        """valid_from 默认值为 None"""
        query = ArchiveQuery()
        assert query.valid_from is None

    def test_valid_until_default(self) -> None:
        """valid_until 默认值为 None"""
        query = ArchiveQuery()
        assert query.valid_until is None

    def test_validity_status_default(self) -> None:
        """validity_status 默认值为 None"""
        query = ArchiveQuery()
        assert query.validity_status is None

    def test_all_validity_fields_assigned(self) -> None:
        """所有有效期字段赋值"""
        now = datetime.now(UTC)
        valid_from = now
        valid_until = datetime(2027, 12, 31, tzinfo=UTC)
        query = ArchiveQuery(
            valid_from=valid_from,
            valid_until=valid_until,
            validity_status=ValidityStatus.VALID,
        )
        assert query.valid_from == valid_from
        assert query.valid_until == valid_until
        assert query.validity_status == ValidityStatus.VALID

    def test_validity_status_expired(self) -> None:
        """validity_status 设置为 EXPIRED"""
        query = ArchiveQuery(validity_status=ValidityStatus.EXPIRED)
        assert query.validity_status == ValidityStatus.EXPIRED

    def test_validity_status_none_is_no_filter(self) -> None:
        """validity_status=None 表示不按有效期过滤，不影响现有查询"""
        query = ArchiveQuery(archive_type=ArchiveType.ASSUMPTION)
        assert query.validity_status is None
        assert query.archive_type == ArchiveType.ASSUMPTION

    def test_backward_compatible(self) -> None:
        """新增字段均为可选，默认 None，不影响现有 ArchiveQuery 构造"""
        query = ArchiveQuery()
        assert query.valid_from is None
        assert query.valid_until is None
        assert query.validity_status is None
        # 原有字段仍可正常使用
        plan_id = uuid4()
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 12, 31, tzinfo=UTC)
        query2 = ArchiveQuery(
            plan_id=plan_id,
            archive_type=ArchiveType.DECISION,
            plan_type="SP",
            start_date=start,
            end_date=end,
            offset=5,
            limit=30,
        )
        assert query2.plan_id == plan_id
        assert query2.archive_type == ArchiveType.DECISION
        assert query2.plan_type == "SP"
        assert query2.start_date == start
        assert query2.end_date == end
        assert query2.offset == 5
        assert query2.limit == 30
        assert query2.valid_from is None
        assert query2.valid_until is None
        assert query2.validity_status is None

    def test_frozen_preserved(self) -> None:
        """frozen dataclass 不可变属性仍然保持"""
        query = ArchiveQuery()
        with pytest.raises(AttributeError):
            setattr(query, "valid_from", datetime.now(UTC))
