"""Story 4.4: SandboxSessionQuery 查询值对象单元测试

验证 Query Object(CLAUDE.md §4 决策规则: 多字段组合+分页 → frozen dataclass):
- 默认值(offset=0, limit=100)
- frozen 不可变
- 组合字段构造
"""

from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from src.domain.ports.sandbox_session_repository import SandboxSessionQuery


class TestSandboxSessionQuery:
    """SandboxSessionQuery 值对象测试"""

    def test_default_values(self) -> None:
        """默认值: 全部过滤字段 None + offset=0 + limit=100"""
        query = SandboxSessionQuery()

        assert query.tenant_id is None
        assert query.state is None
        assert query.idle_threshold is None
        assert query.offset == 0
        assert query.limit == 100

    def test_frozen_immutable(self) -> None:
        """frozen dataclass: 字段赋值抛 FrozenInstanceError"""
        query = SandboxSessionQuery()

        with pytest.raises(FrozenInstanceError):
            query.offset = 5  # type: ignore[misc]

    def test_combined_fields(self) -> None:
        """多字段组合构造"""
        tenant = uuid.uuid4()
        threshold = datetime.now(UTC)
        query = SandboxSessionQuery(
            tenant_id=tenant,
            state="RUNNING",
            idle_threshold=threshold,
            offset=10,
            limit=50,
        )

        assert query.tenant_id == tenant
        assert query.state == "RUNNING"
        assert query.idle_threshold == threshold
        assert query.offset == 10
        assert query.limit == 50

    def test_state_literal_values(self) -> None:
        """state 字段接受三值字面量"""
        for state in ("RUNNING", "TERMINATED", "FAILED"):
            query = SandboxSessionQuery(state=state)
            assert query.state == state
