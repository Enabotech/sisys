"""Tests for Neo4jAdapter — L5GraphPort implementation.

验证适配器正确委托存储操作，实现 L5GraphPort 接口。
架构意义：薄适配器层，使用 memory_id 作为实体主键。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.neo4j.neo4j_adapter import Neo4jAdapter


class TestNeo4jAdapterInterface:
    """验证适配器实现 L5GraphPort 接口"""

    def test_delegates_to_internal_storage(self):
        """验证适配器委托操作给内部存储"""
        mock_storage = MagicMock()
        adapter = Neo4jAdapter(mock_storage)
        assert adapter._storage is mock_storage


class TestNeo4jAdapterCreateEntity:
    """create_entity 方法验证"""

    @pytest.mark.asyncio
    async def test_create_entity_uses_merge_semantics(self):
        """验证使用 MERGE 语义（已存在不报错）"""
        mock_storage = AsyncMock()
        mock_storage.execute_write_query = AsyncMock(return_value=[{"n": {}}])

        adapter = Neo4jAdapter(mock_storage)
        result = await adapter.create_entity(
            memory_id="mem-123",
            entity_type="project",
            properties={"name": "Test Project"},
        )

        assert result is True
        mock_storage.execute_write_query.assert_called_once()
        cypher = mock_storage.execute_write_query.call_args[0][0]
        assert "MERGE" in cypher
        assert "$memory_id" in cypher

    @pytest.mark.asyncio
    async def test_create_entity_returns_false_when_fail(self):
        """验证执行失败返回 False"""
        mock_storage = AsyncMock()
        mock_storage.execute_write_query = AsyncMock(return_value=[])

        adapter = Neo4jAdapter(mock_storage)
        result = await adapter.create_entity(
            memory_id="mem-123",
            entity_type="project",
            properties={},
        )

        assert result is False


class TestNeo4jAdapterGetEntity:
    """get_entity 方法验证"""

    @pytest.mark.asyncio
    async def test_get_entity_returns_none_when_not_found(self):
        """验证不存在时返回 None"""
        mock_storage = AsyncMock()
        mock_storage.execute_query = AsyncMock(return_value=[])

        adapter = Neo4jAdapter(mock_storage)
        result = await adapter.get_entity("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_entity_returns_dict_with_id_type_properties(self):
        """验证返回正确结构的 dict"""
        mock_storage = AsyncMock()
        mock_storage.execute_query = AsyncMock(
            return_value=[{"id": "mem-123", "type": "project", "properties": {"name": "Test"}}]
        )

        adapter = Neo4jAdapter(mock_storage)
        result = await adapter.get_entity("mem-123")

        assert result is not None
        assert result["id"] == "mem-123"
        assert result["type"] == "project"
        assert result["properties"] == {"name": "Test"}


class TestNeo4jAdapterDeleteEntity:
    """delete_entity 方法验证"""

    @pytest.mark.asyncio
    async def test_delete_entity_always_returns_true(self):
        """验证删除总是返回 True（即使不存在）"""
        mock_storage = AsyncMock()
        mock_storage.execute_write_query = AsyncMock(return_value=[])

        adapter = Neo4jAdapter(mock_storage)
        result = await adapter.delete_entity("mem-123")

        assert result is True
        cypher = mock_storage.execute_write_query.call_args[0][0]
        assert "DETACH DELETE" in cypher


class TestNeo4jAdapterRelationships:
    """关系操作方法验证"""

    @pytest.mark.asyncio
    async def test_create_relationship_uses_merge(self):
        """验证 create_relationship 使用 MERGE 语义"""
        mock_storage = AsyncMock()
        mock_storage.execute_write_query = AsyncMock(return_value=[{"r": {}}])

        adapter = Neo4jAdapter(mock_storage)
        result = await adapter.create_relationship(
            source_memory_id="mem-1",
            target_memory_id="mem-2",
            relationship_type="DEPENDS_ON",
            properties={"weight": 1},
        )

        assert result is True
        cypher = mock_storage.execute_write_query.call_args[0][0]
        assert "MERGE" in cypher
        assert "DEPENDS_ON" in cypher

    @pytest.mark.asyncio
    async def test_delete_relationship_returns_true(self):
        """验证删除关系返回 True"""
        mock_storage = AsyncMock()
        mock_storage.execute_write_query = AsyncMock(return_value=[])

        adapter = Neo4jAdapter(mock_storage)
        result = await adapter.delete_relationship("mem-1", "mem-2", "DEPENDS_ON")

        assert result is True


class TestNeo4jAdapterFindRelated:
    """find_related 方法验证"""

    @pytest.mark.asyncio
    async def test_find_related_with_specific_relationship_type(self):
        """验证带关系类型过滤的遍历"""
        mock_storage = AsyncMock()
        mock_storage.execute_query = AsyncMock(return_value=[])

        adapter = Neo4jAdapter(mock_storage)
        await adapter.find_related("mem-123", max_depth=2, relationship_type="DEPENDS_ON")

        cypher = mock_storage.execute_query.call_args[0][0]
        assert "DEPENDS_ON" in cypher

    @pytest.mark.asyncio
    async def test_find_related_without_relationship_type(self):
        """验证不带关系类型过滤的遍历"""
        mock_storage = AsyncMock()
        mock_storage.execute_query = AsyncMock(return_value=[])

        adapter = Neo4jAdapter(mock_storage)
        await adapter.find_related("mem-123", max_depth=3)

        cypher = mock_storage.execute_query.call_args[0][0]
        assert "DEPENDS_ON" not in cypher

    @pytest.mark.asyncio
    async def test_find_related_returns_list_of_dict(self):
        """验证返回正确结构的列表"""
        mock_storage = AsyncMock()
        mock_storage.execute_query = AsyncMock(
            return_value=[
                {"memory_id": "mem-1", "type": "project", "properties": {}, "path": []},
                {"memory_id": "mem-2", "type": "reference", "properties": {}, "path": []},
            ]
        )

        adapter = Neo4jAdapter(mock_storage)
        result = await adapter.find_related("mem-123")

        assert len(result) == 2
        assert result[0]["memory_id"] == "mem-1"


class TestNeo4jAdapterExecuteQuery:
    """execute_query 方法验证"""

    @pytest.mark.asyncio
    async def test_execute_query_delegates_to_storage(self):
        """验证只读查询委托"""
        mock_storage = AsyncMock()
        mock_storage.execute_query = AsyncMock(return_value=[{"n": {}}])

        adapter = Neo4jAdapter(mock_storage)
        result = await adapter.execute_query("MATCH (n) RETURN n", {"limit": 10})

        assert len(result) == 1
        mock_storage.execute_query.assert_called_once_with("MATCH (n) RETURN n", {"limit": 10})

    @pytest.mark.asyncio
    async def test_execute_write_query_delegates(self):
        """验证写入查询委托"""
        mock_storage = AsyncMock()
        mock_storage.execute_write_query = AsyncMock(return_value=[])

        adapter = Neo4jAdapter(mock_storage)
        result = await adapter.execute_write_query("CREATE (n:Memory {id: $id})", {"id": "mem-123"})

        assert result == []
        mock_storage.execute_write_query.assert_called_once_with("CREATE (n:Memory {id: $id})", {"id": "mem-123"})
