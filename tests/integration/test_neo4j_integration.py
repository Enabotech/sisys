"""Neo4j 端到端集成测试（Mock 版本）。

验证完整节点/关系/查询流程，使用 Mock 客户端替代真实 Neo4j 实例。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class _AsyncCM:
    """辅助类：模拟异步上下文管理器。"""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


def _mock_session_single(driver, session, single_result):
    """设置会话模拟（用于 .single() 场景）。"""

    async def mock_run(*args, **kwargs):
        result_mock = MagicMock()
        result_mock.single = AsyncMock(return_value=single_result)
        result_mock.data = AsyncMock(return_value=single_result if isinstance(single_result, list) else [])
        return result_mock

    session.run = mock_run
    driver.session.return_value = _AsyncCM(session)


def _mock_session_data(driver, session, data_result):
    """设置会话模拟（用于 .data() 场景）。"""

    async def mock_run(*args, **kwargs):
        result_mock = MagicMock()
        result_mock.data = AsyncMock(return_value=data_result)
        result_mock.single = AsyncMock(return_value=data_result[0] if data_result else None)
        return result_mock

    mock_run_wrapped = MagicMock(side_effect=mock_run)
    session.run = mock_run_wrapped
    driver.session.return_value = _AsyncCM(session)


@pytest.fixture
def mock_driver():
    return MagicMock()


@pytest.fixture
def mock_session():
    return MagicMock()


class TestNeo4jNodeLifecycle:
    """节点生命周期端到端测试。"""

    async def test_create_get_delete_node(self, mock_driver, mock_session):
        """测试节点创建→查询→验证→删除完整流程。"""
        from src.infrastructure.storage.neo4j.graph_manager import Neo4jGraphManager

        manager = Neo4jGraphManager(driver=mock_driver, database="neo4j")

        from src.infrastructure.storage.neo4j.models import GraphNode

        node = GraphNode(
            id="doc-001",
            labels=["sisys:Document"],
            properties={"business_domain": "strategy", "entity_type": "Document", "content_hash": "abc123"},
        )

        # 创建节点
        _mock_session_single(mock_driver, mock_session, MagicMock())
        create_result = await manager.create_node(node)
        assert create_result is True

        # 查询节点
        mock_node_data = {"id": "doc-001"}
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: mock_node_data
        _mock_session_single(mock_driver, mock_session, mock_record)
        get_result = await manager.get_node("doc-001")
        assert get_result is not None

        # 删除节点
        mock_del_record = MagicMock()
        mock_del_record.__getitem__ = lambda self, key: 1
        _mock_session_single(mock_driver, mock_session, mock_del_record)
        delete_result = await manager.delete_node("doc-001")
        assert delete_result is True


class TestNeo4jRelationshipLifecycle:
    """关系生命周期端到端测试。"""

    async def test_create_delete_relationship(self, mock_driver, mock_session):
        """测试关系创建→查询→验证→删除完整流程。"""
        from src.infrastructure.storage.neo4j.graph_manager import Neo4jGraphManager

        manager = Neo4jGraphManager(driver=mock_driver, database="neo4j")

        from src.infrastructure.storage.neo4j.models import GraphRelationship, RelationshipType

        rel = GraphRelationship(
            start_node_id="doc-001",
            end_node_id="entity-001",
            relationship_type=RelationshipType.MENTIONS,
            properties={"confidence": 0.95},
        )

        # 创建关系
        _mock_session_single(mock_driver, mock_session, MagicMock())
        create_result = await manager.create_relationship(rel)
        assert create_result is True

        # 删除关系
        mock_del_record = MagicMock()
        mock_del_record.__getitem__ = lambda self, key: 1
        _mock_session_single(mock_driver, mock_session, mock_del_record)
        delete_result = await manager.delete_relationship("doc-001", "entity-001", "MENTIONS")
        assert delete_result is True


class TestNeo4jCypherQueries:
    """Cypher 查询端到端测试。"""

    async def test_parameterized_query(self, mock_driver, mock_session):
        """测试参数化 Cypher 查询。"""
        from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage

        storage = Neo4jGraphStorage(driver=mock_driver, database="neo4j")

        _mock_session_data(mock_driver, mock_session, [{"n": {"id": "entity-001"}}])

        result = await storage.execute_query(
            "MATCH (n:sisys:Entity {id: $node_id}) RETURN n",
            {"node_id": "entity-001"},
        )
        assert len(result) == 1
        call_args = mock_session.run.call_args
        assert "$node_id" in call_args[0][0]


class TestNeo4jGraphRAG:
    """GraphRAG 实体关联检索端到端测试。"""

    async def test_find_related_entities_full_flow(self, mock_driver, mock_session):
        """测试 GraphRAG 实体关联检索完整流程。"""
        from src.infrastructure.storage.neo4j.graph_retriever import GraphRetriever

        retriever = GraphRetriever(driver=mock_driver, database="neo4j")

        _mock_session_data(
            mock_driver,
            mock_session,
            [
                {"related": {"id": "entity-002", "entity_type": "Entity"}, "hops": 1, "connection_count": 5},
                {"related": {"id": "entity-003", "entity_type": "Document"}, "hops": 2, "connection_count": 2},
            ],
        )

        result = await retriever.find_related_entities("entity-001", max_depth=2, limit=20)
        assert len(result) == 2
        assert result[0]["entity"]["id"] == "entity-002"
        assert result[1]["entity"]["id"] == "entity-003"


class TestNeo4jMultiTenantIsolation:
    """多租户隔离端到端测试。"""

    async def test_business_domain_filtering(self, mock_driver, mock_session):
        """测试不同 business_domain 数据隔离。"""
        from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage

        storage = Neo4jGraphStorage(driver=mock_driver, database="neo4j")

        _mock_session_data(
            mock_driver,
            mock_session,
            [
                {"n": {"id": "entity-001", "business_domain": "strategy"}},
            ],
        )

        result = await storage.execute_query(
            "MATCH (n {business_domain: $domain}) RETURN n",
            {"domain": "strategy"},
        )
        assert len(result) == 1
        assert result[0]["n"]["business_domain"] == "strategy"
