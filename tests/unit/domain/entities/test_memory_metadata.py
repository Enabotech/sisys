"""Tests for MemoryMetadata entity.

RED PHASE: 验证 MemoryMetadata 实体定义正确性。
"""

from __future__ import annotations

import uuid

import pytest

from src.domain.entities.memory_metadata import MemoryMetadata


class TestMemoryMetadataSchema:
    """MemoryMetadata 实体 Schema 验证"""

    def test_create_memory_metadata(self):
        """验证创建 MemoryMetadata"""
        memory = MemoryMetadata.create(
            name="test-memory",
            memory_type="user",
            user_id="user123",
            description="Test description",
        )
        assert memory.name == "test-memory"
        assert memory.type == "user"
        assert memory.user_id == "user123"
        assert memory.description == "Test description"
        assert memory.version == 1
        assert memory.path.startswith("user/")

    def test_memory_id_is_uuid(self):
        """验证 memory_id 是 UUID 格式"""
        memory = MemoryMetadata.create(
            name="test-memory",
            memory_type="feedback",
        )
        assert isinstance(memory.memory_id, uuid.UUID)

    def test_path_format(self):
        """验证 path 格式为 {type}/{memory_id}.md"""
        memory = MemoryMetadata.create(
            name="bun-npm",
            memory_type="feedback",
        )
        assert memory.path == f"feedback/{memory.memory_id}.md"

    def test_invalid_type_raises(self):
        """验证无效 type 抛出异常"""
        with pytest.raises(ValueError, match="type must be one of"):
            MemoryMetadata.create(
                name="test",
                memory_type="invalid",
            )

    def test_bump_version(self):
        """验证版本递增"""
        memory = MemoryMetadata.create(
            name="test-memory",
            memory_type="user",
        )
        original_version = memory.version
        memory.bump_version()
        assert memory.version == original_version + 1


class TestMemoryMetadataTypes:
    """MemoryMetadata 类型验证"""

    @pytest.mark.parametrize("memory_type", ["user", "feedback", "project", "reference"])
    def test_valid_types(self, memory_type):
        """验证所有有效类型"""
        memory = MemoryMetadata.create(
            name="test",
            memory_type=memory_type,
        )
        assert memory.type == memory_type
        assert memory.path.startswith(f"{memory_type}/")
