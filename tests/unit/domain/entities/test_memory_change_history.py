"""Tests for MemoryChangeHistory entity.

RED PHASE: 验证 MemoryChangeHistory 实体定义正确性。
"""

from __future__ import annotations

import uuid

import pytest

from src.domain.entities.memory_change_history import MemoryChangeHistory


class TestMemoryChangeHistorySchema:
    """MemoryChangeHistory 实体 Schema 验证"""

    def test_create_history_entry(self):
        """验证创建 MemoryChangeHistory 条目"""
        memory_id = uuid.uuid4()
        history = MemoryChangeHistory.create(
            memory_id=memory_id,
            version=1,
            change_type="create",
            changed_by="user123",
            changed_fields={"name": ["old", "new"]},
            diff_summary="name: old -> new",
        )
        assert history.memory_id == memory_id
        assert history.version == 1
        assert history.change_type == "create"
        assert history.changed_by == "user123"

    def test_id_is_uuid(self):
        """验证 id 是 UUID 格式"""
        history = MemoryChangeHistory.create(
            memory_id=uuid.uuid4(),
            version=1,
            change_type="create",
        )
        assert isinstance(history.id, uuid.UUID)

    def test_invalid_change_type_raises(self):
        """验证无效 change_type 抛出异常"""
        with pytest.raises(ValueError, match="change_type must be one of"):
            MemoryChangeHistory.create(
                memory_id=uuid.uuid4(),
                version=1,
                change_type="invalid",
            )

    @pytest.mark.parametrize("change_type", ["create", "update", "delete"])
    def test_valid_change_types(self, change_type):
        """验证所有有效 change_type"""
        history = MemoryChangeHistory.create(
            memory_id=uuid.uuid4(),
            version=1,
            change_type=change_type,
        )
        assert history.change_type == change_type

    def test_delete_change_type_for_deletion(self):
        """验证 delete 操作创建历史记录"""
        history = MemoryChangeHistory.create(
            memory_id=uuid.uuid4(),
            version=1,
            change_type="delete",
            changed_by="user123",
            diff_summary="memory deleted",
        )
        assert history.change_type == "delete"


class TestMemoryChangeHistoryAppendOnly:
    """MemoryChangeHistory append-only 特性验证"""

    def test_archived_ref_optional(self):
        """验证 archived_ref 可选"""
        history = MemoryChangeHistory.create(
            memory_id=uuid.uuid4(),
            version=1,
            change_type="create",
            archived_ref="",  # 空字符串
        )
        assert history.archived_ref == ""

    def test_changed_fields_default_empty_dict(self):
        """验证 changed_fields 默认空字典"""
        history = MemoryChangeHistory.create(
            memory_id=uuid.uuid4(),
            version=1,
            change_type="create",
        )
        assert history.changed_fields == {}

    def test_changed_fields_jsonb_format(self):
        """验证 changed_fields JSONB 格式"""
        fields = {"name": ["old-name", "new-name"], "type": [None, "feedback"]}
        history = MemoryChangeHistory.create(
            memory_id=uuid.uuid4(),
            version=1,
            change_type="update",
            changed_fields=fields,
        )
        assert history.changed_fields == fields
