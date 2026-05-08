"""Neo4jAdapter 实现测试。

验证 Neo4jAdapter 实现了 L5GraphPort 接口。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestNeo4jAdapterL5GraphPortCompliance:
    """验证 Neo4jAdapter 实现了 L5GraphPort 接口。"""

    def test_adapter_implements_l5_graph_port(self) -> None:
        """Neo4jAdapter 应实现 L5GraphPort。"""
        from src.domain.ports.l5_graph import L5GraphPort
        from src.infrastructure.storage.neo4j.neo4j_adapter import Neo4jAdapter

        mock_storage = MagicMock()
        adapter = Neo4jAdapter(mock_storage)

        assert isinstance(adapter, L5GraphPort)

    def test_adapter_has_all_required_methods(self) -> None:
        """Neo4jAdapter 应有 L5GraphPort 的所有方法。"""
        from src.domain.ports.l5_graph import L5GraphPort
        from src.infrastructure.storage.neo4j.neo4j_adapter import Neo4jAdapter

        mock_storage = MagicMock()
        adapter = Neo4jAdapter(mock_storage)

        for method_name in [
            "create_entity",
            "get_entity",
            "delete_entity",
            "create_relationship",
            "delete_relationship",
            "find_related",
            "execute_query",
            "execute_write_query",
        ]:
            assert hasattr(adapter, method_name)
            assert hasattr(L5GraphPort, method_name)

    def test_all_methods_are_async(self) -> None:
        """所有方法应为 async def。"""
        from src.infrastructure.storage.neo4j.neo4j_adapter import Neo4jAdapter

        mock_storage = MagicMock()
        adapter = Neo4jAdapter(mock_storage)

        for method_name in [
            "create_entity",
            "get_entity",
            "delete_entity",
            "create_relationship",
            "delete_relationship",
            "find_related",
            "execute_query",
            "execute_write_query",
        ]:
            method = getattr(adapter, method_name)
            assert asyncio.iscoroutinefunction(method), f"{method_name} should be async"


class TestNeo4jAdapterBehavior:
    """Neo4jAdapter 行为测试。"""

    @pytest.fixture
    def mock_neo4j_storage(self):
        """创建模拟的 Neo4jGraphStorage。"""
        mock = MagicMock()
        mock.execute_write_query = AsyncMock(return_value=[{"n": {"id": "mem-123"}}])
        mock.execute_query = AsyncMock(return_value=[{"id": "mem-123", "type": "project", "properties": {}}])
        return mock

    @pytest.fixture
    def adapter(self, mock_neo4j_storage):
        """创建 Neo4jAdapter 实例。"""
        from src.infrastructure.storage.neo4j.neo4j_adapter import Neo4jAdapter

        return Neo4jAdapter(mock_neo4j_storage)

    @pytest.mark.asyncio
    async def test_create_entity_uses_cypher_merge(self, adapter, mock_neo4j_storage) -> None:
        """create_entity 应使用 MERGE Cypher 语句。"""
        result = await adapter.create_entity(
            memory_id="mem-123",
            entity_type="project",
            properties={"name": "Test Project"},
        )

        assert result is True
        mock_neo4j_storage.execute_write_query.assert_called_once()
        call_args = mock_neo4j_storage.execute_write_query.call_args
        cypher = call_args[0][0]
        assert "MERGE" in cypher

    @pytest.mark.asyncio
    async def test_get_entity_uses_match_query(self, adapter, mock_neo4j_storage) -> None:
        """get_entity 应使用 MATCH 查询。"""
        result = await adapter.get_entity(memory_id="mem-123")

        assert result is not None
        mock_neo4j_storage.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_entity_uses_detach_delete(self, adapter, mock_neo4j_storage) -> None:
        """delete_entity 应使用 DETACH DELETE。"""
        result = await adapter.delete_entity(memory_id="mem-123")

        assert result is True
        call_args = mock_neo4j_storage.execute_write_query.call_args
        cypher = call_args[0][0]
        assert "DETACH DELETE" in cypher

    @pytest.mark.asyncio
    async def test_create_relationship_uses_cypher_merge(self, adapter, mock_neo4j_storage) -> None:
        """create_relationship 应使用 MERGE。"""
        result = await adapter.create_relationship(
            source_memory_id="mem-1",
            target_memory_id="mem-2",
            relationship_type="DEPENDS_ON",
        )

        assert result is True
        call_args = mock_neo4j_storage.execute_write_query.call_args
        cypher = call_args[0][0]
        assert "MERGE" in cypher
        assert "DEPENDS_ON" in cypher

    @pytest.mark.asyncio
    async def test_delete_relationship_uses_delete(self, adapter, mock_neo4j_storage) -> None:
        """delete_relationship 应删除关系。"""
        result = await adapter.delete_relationship(
            source_memory_id="mem-1",
            target_memory_id="mem-2",
            relationship_type="DEPENDS_ON",
        )

        assert result is True
        call_args = mock_neo4j_storage.execute_write_query.call_args
        cypher = call_args[0][0]
        assert "DELETE" in cypher

    @pytest.mark.asyncio
    async def test_find_related_uses_path_traversal(self, adapter, mock_neo4j_storage) -> None:
        """find_related 应使用路径遍历。"""
        result = await adapter.find_related(memory_id="mem-1", max_depth=2)

        assert result is not None
        mock_neo4j_storage.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_delegates_to_storage(self, adapter, mock_neo4j_storage) -> None:
        """execute_query 应委托给内部存储。"""
        result = await adapter.execute_query("MATCH (n) RETURN n", {})

        assert result is not None
        mock_neo4j_storage.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_write_query_delegates_to_storage(self, adapter, mock_neo4j_storage) -> None:
        """execute_write_query 应委托给内部存储。"""
        result = await adapter.execute_write_query("CREATE (n) RETURN n", {})

        assert result is not None
        mock_neo4j_storage.execute_write_query.assert_called_once()
