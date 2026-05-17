"""Tests for Neo4jMemoryGraphStorage — MemoryGraphPort implementation.

验证存储包装器正确委托 Neo4jAdapter，并实现记忆关系特有语义
架构意义：组合注入适配器，添加记忆实体和知识图谱语义
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.neo4j.neo4j_memory_graph_storage import (
    Neo4jMemoryGraphStorage,
    _content_hash,
)


class TestNeo4jMemoryGraphStorageInterface:
    """验证存储包装器正确初始化"""

    def test_delegates_to_internal_adapter(self):
        """验证适配器通过构造函数注入"""
        mock_adapter = MagicMock()
        storage = Neo4jMemoryGraphStorage(mock_adapter)
        assert storage._adapter is mock_adapter


class TestContentHash:
    """_content_hash 辅助函数验证"""

    def test_returns_16_char_hex_string(self):
        """验证返回 16 字符十六进制字符串"""
        result = _content_hash("test content")
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic_for_same_input(self):
        """验证相同输入产生相同 hash"""
        hash1 = _content_hash("same content")
        hash2 = _content_hash("same content")
        assert hash1 == hash2

    def test_different_for_different_input(self):
        """验证不同输入产生不同 hash"""
        hash1 = _content_hash("content one")
        hash2 = _content_hash("content two")
        assert hash1 != hash2

    def test_handles_empty_string(self):
        """验证空字符串返回有效 hash"""
        result = _content_hash("")
        assert len(result) == 16


class TestNeo4jMemoryGraphStorageDelegation:
    """验证 L5GraphPort 方法正确委托给适配器"""

    @pytest.mark.asyncio
    async def test_create_entity_delegates_to_adapter(self):
        """验证 create_entity 正确委托"""
        mock_adapter = AsyncMock()
        mock_adapter.create_entity = AsyncMock(return_value=True)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.create_entity(
            memory_id="mem-123",
            entity_type="project",
            properties={"name": "Test"},
        )

        assert result is True
        mock_adapter.create_entity.assert_called_once_with("mem-123", "project", {"name": "Test"})

    @pytest.mark.asyncio
    async def test_get_entity_delegates_to_adapter(self):
        """验证 get_entity 正确委托"""
        mock_adapter = AsyncMock()
        expected = {"id": "mem-123", "type": "project", "properties": {}}
        mock_adapter.get_entity = AsyncMock(return_value=expected)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.get_entity("mem-123")

        assert result == expected
        mock_adapter.get_entity.assert_called_once_with("mem-123")

    @pytest.mark.asyncio
    async def test_delete_entity_delegates_to_adapter(self):
        """验证 delete_entity 正确委托"""
        mock_adapter = AsyncMock()
        mock_adapter.delete_entity = AsyncMock(return_value=True)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.delete_entity("mem-123")

        assert result is True
        mock_adapter.delete_entity.assert_called_once_with("mem-123")

    @pytest.mark.asyncio
    async def test_create_relationship_delegates_to_adapter(self):
        """验证 create_relationship 正确委托"""
        mock_adapter = AsyncMock()
        mock_adapter.create_relationship = AsyncMock(return_value=True)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.create_relationship(
            source_memory_id="mem-1",
            target_memory_id="mem-2",
            relationship_type="DEPENDS_ON",
            properties={"weight": 1},
        )

        assert result is True
        mock_adapter.create_relationship.assert_called_once_with("mem-1", "mem-2", "DEPENDS_ON", {"weight": 1})

    @pytest.mark.asyncio
    async def test_create_relationship_without_properties(self):
        """验证 create_relationship 无属性时传递 None"""
        mock_adapter = AsyncMock()
        mock_adapter.create_relationship = AsyncMock(return_value=True)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.create_relationship(
            source_memory_id="mem-1",
            target_memory_id="mem-2",
            relationship_type="RELATED_TO",
        )

        assert result is True
        mock_adapter.create_relationship.assert_called_once_with("mem-1", "mem-2", "RELATED_TO", None)

    @pytest.mark.asyncio
    async def test_delete_relationship_delegates_to_adapter(self):
        """验证 delete_relationship 正确委托"""
        mock_adapter = AsyncMock()
        mock_adapter.delete_relationship = AsyncMock(return_value=True)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.delete_relationship("mem-1", "mem-2", "DEPENDS_ON")

        assert result is True
        mock_adapter.delete_relationship.assert_called_once_with("mem-1", "mem-2", "DEPENDS_ON")

    @pytest.mark.asyncio
    async def test_find_related_delegates_to_adapter(self):
        """验证 find_related 正确委托"""
        mock_adapter = AsyncMock()
        expected = [{"memory_id": "mem-2", "type": "ref", "properties": {}}]
        mock_adapter.find_related = AsyncMock(return_value=expected)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.find_related("mem-1", max_depth=3, relationship_type="DEPENDS_ON")

        assert result == expected
        mock_adapter.find_related.assert_called_once_with("mem-1", 3, "DEPENDS_ON")

    @pytest.mark.asyncio
    async def test_execute_query_delegates_to_adapter(self):
        """验证 execute_query 正确委托"""
        mock_adapter = AsyncMock()
        expected = [{"n": {"id": "mem-1"}}]
        mock_adapter.execute_query = AsyncMock(return_value=expected)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.execute_query("MATCH (n) RETURN n", {"limit": 10})

        assert result == expected
        mock_adapter.execute_query.assert_called_once_with("MATCH (n) RETURN n", {"limit": 10})

    @pytest.mark.asyncio
    async def test_execute_write_query_delegates_to_adapter(self):
        """验证 execute_write_query 正确委托"""
        mock_adapter = AsyncMock()
        expected = []
        mock_adapter.execute_write_query = AsyncMock(return_value=expected)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.execute_write_query("CREATE (n:Memory {id: $id})", {"id": "mem-123"})

        assert result == expected
        mock_adapter.execute_write_query.assert_called_once_with("CREATE (n:Memory {id: $id})", {"id": "mem-123"})

    @pytest.mark.asyncio
    async def test_get_neighbors_delegates_to_adapter(self):
        """验证 get_neighbors 正确委托"""
        mock_adapter = AsyncMock()
        expected = [{"memory_id": "mem-2", "type": "ref", "properties": {}}]
        mock_adapter.get_neighbors = AsyncMock(return_value=expected)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.get_neighbors("mem-1", max_depth=1, edge_type="DEPENDS_ON")

        assert result == expected
        mock_adapter.get_neighbors.assert_called_once_with("mem-1", 1, "DEPENDS_ON")


class TestIndexMemoryRelations:
    """index_memory_relations 方法验证（特有行为）"""

    @pytest.mark.asyncio
    async def test_creates_memory_entity_with_content_hash(self):
        """验证创建 Memory 实体并包含 content_hash"""
        mock_adapter = AsyncMock()
        mock_adapter.create_entity = AsyncMock(return_value=True)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.index_memory_relations(
            memory_id="mem-123",
            content="This is some memory content",
        )

        assert result == 1
        mock_adapter.create_entity.assert_called_once()
        call_kwargs = mock_adapter.create_entity.call_args[1]
        assert call_kwargs["memory_id"] == "mem-123"
        assert call_kwargs["entity_type"] == "Memory"
        properties = call_kwargs["properties"]
        assert "content_hash" in properties
        assert len(properties["content_hash"]) == 16

    @pytest.mark.asyncio
    async def test_returns_1_as_relation_count(self):
        """验证固定返回 1（简单实现）"""
        mock_adapter = AsyncMock()
        mock_adapter.create_entity = AsyncMock(return_value=True)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.index_memory_relations(
            memory_id="mem-456",
            content="Another memory",
        )

        assert result == 1


class TestGetKnowledgeGraph:
    """get_knowledge_graph 方法验证（特有行为）"""

    @pytest.mark.asyncio
    async def test_returns_empty_when_entity_is_none(self):
        """验证实体不存在时返回空图谱"""
        mock_adapter = AsyncMock()
        mock_adapter.get_entity = AsyncMock(return_value=None)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.get_knowledge_graph("nonexistent-id")

        assert result == {"entities": [], "connections": []}
        mock_adapter.get_entity.assert_called_once_with("nonexistent-id")

    @pytest.mark.asyncio
    async def test_returns_entity_and_related(self):
        """验证返回实体和关联实体"""
        mock_adapter = AsyncMock()
        entity = {"id": "mem-1", "type": "Memory", "properties": {"content_hash": "abc123"}}
        related = [
            {"memory_id": "mem-2", "type": "Memory", "properties": {"key": "val"}, "path": []},
            {"memory_id": "mem-3", "type": "Concept", "properties": {}, "path": []},
        ]
        mock_adapter.get_entity = AsyncMock(return_value=entity)
        mock_adapter.find_related = AsyncMock(return_value=related)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.get_knowledge_graph("mem-1", depth=2)

        assert len(result["entities"]) == 3
        assert result["entities"][0] == entity
        assert result["entities"][1]["id"] == "mem-2"
        assert result["entities"][2]["id"] == "mem-3"
        assert result["connections"] == related

    @pytest.mark.asyncio
    async def test_calls_find_related_with_correct_depth(self):
        """验证使用正确深度调用 find_related"""
        mock_adapter = AsyncMock()
        entity = {"id": "mem-1", "type": "Memory", "properties": {}}
        mock_adapter.get_entity = AsyncMock(return_value=entity)
        mock_adapter.find_related = AsyncMock(return_value=[])

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        await storage.get_knowledge_graph("mem-1", depth=3)

        mock_adapter.find_related.assert_called_once_with("mem-1", max_depth=3)

    @pytest.mark.asyncio
    async def test_handles_related_with_missing_fields(self):
        """验证关联实体缺少字段时使用默认值"""
        mock_adapter = AsyncMock()
        entity = {"id": "mem-1", "type": "Memory", "properties": {}}
        related = [
            {"memory_id": "mem-2"},
        ]
        mock_adapter.get_entity = AsyncMock(return_value=entity)
        mock_adapter.find_related = AsyncMock(return_value=related)

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        result = await storage.get_knowledge_graph("mem-1")

        assert result["entities"][1]["id"] == "mem-2"
        assert result["entities"][1]["type"] is None
        assert result["entities"][1]["properties"] == {}

    @pytest.mark.asyncio
    async def test_uses_default_depth_of_2(self):
        """验证默认深度为 2"""
        mock_adapter = AsyncMock()
        entity = {"id": "mem-1", "type": "Memory", "properties": {}}
        mock_adapter.get_entity = AsyncMock(return_value=entity)
        mock_adapter.find_related = AsyncMock(return_value=[])

        storage = Neo4jMemoryGraphStorage(mock_adapter)
        await storage.get_knowledge_graph("mem-1")

        mock_adapter.find_related.assert_called_once_with("mem-1", max_depth=2)
