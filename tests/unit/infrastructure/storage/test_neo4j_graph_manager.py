"""Neo4jGraphManager 单元测试"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.neo4j.graph_manager import Neo4jGraphManager


class _AsyncCM:
    """辅助类：模拟异步上下文管理器"""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


def _mock_session(driver, session, single_result):
    """设置会话模拟

    Args:
        driver: MagicMock driver (NOT AsyncMock)
        session: MagicMock session
        single_result: session.run().single() 应返回的值
    """

    async def mock_run(*args, **kwargs):
        result_mock = MagicMock()
        result_mock.single = AsyncMock(return_value=single_result)
        return result_mock

    session.run = mock_run
    driver.session.return_value = _AsyncCM(session)


@pytest.fixture
def mock_driver():
    """模拟 Neo4j 异步驱动（必须用 MagicMock，不能用 AsyncMock）"""
    return MagicMock()


@pytest.fixture
def mock_session():
    """模拟 Neo4j 会话"""
    return MagicMock()


@pytest.fixture
def manager(mock_driver):
    """创建 Neo4jGraphManager 实例"""
    return Neo4jGraphManager(driver=mock_driver, database="neo4j")


class TestNeo4jGraphManager:
    """Neo4jGraphManager 测试类"""

    async def test_create_node_success(self, manager, mock_driver, mock_session):
        """测试创建节点成功"""
        from src.infrastructure.storage.neo4j.models import GraphNode

        node = GraphNode(
            id="entity-001",
            labels=["sisys:Entity"],
            properties={"business_domain": "strategy", "entity_type": "Entity", "content_hash": "abc123"},
        )

        _mock_session(mock_driver, mock_session, MagicMock())
        result = await manager.create_node(node)
        assert result is True

    async def test_create_node_merge_existing(self, manager, mock_driver, mock_session):
        """测试 MERGE 语义：节点已存在时返回 False"""
        from src.infrastructure.storage.neo4j.models import GraphNode

        node = GraphNode(
            id="entity-001",
            labels=["sisys:Entity"],
            properties={"business_domain": "strategy", "entity_type": "Entity", "content_hash": "abc123"},
        )

        _mock_session(mock_driver, mock_session, None)
        result = await manager.create_node(node)
        assert result is False

    async def test_delete_node_success(self, manager, mock_driver, mock_session):
        """测试删除节点成功"""
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: 1
        _mock_session(mock_driver, mock_session, mock_record)

        result = await manager.delete_node("entity-001")
        assert result is True

    async def test_delete_node_not_found(self, manager, mock_driver, mock_session):
        """测试删除不存在的节点"""
        _mock_session(mock_driver, mock_session, None)

        result = await manager.delete_node("nonexistent")
        assert result is False

    async def test_get_node_success(self, manager, mock_driver, mock_session):
        """测试获取节点成功"""
        mock_node_data = {"id": "entity-001", "name": "Test Entity"}
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: mock_node_data
        _mock_session(mock_driver, mock_session, mock_record)

        result = await manager.get_node("entity-001")
        assert result is not None
        assert result["id"] == "entity-001"

    async def test_get_node_not_found(self, manager, mock_driver, mock_session):
        """测试获取不存在的节点"""
        _mock_session(mock_driver, mock_session, None)

        result = await manager.get_node("nonexistent")
        assert result is None

    async def test_create_relationship_success(self, manager, mock_driver, mock_session):
        """测试创建关系成功"""
        from src.infrastructure.storage.neo4j.models import GraphRelationship, RelationshipType

        rel = GraphRelationship(
            start_node_id="entity-001",
            end_node_id="entity-002",
            relationship_type=RelationshipType.MENTIONS,
            properties={"confidence": 0.95},
        )

        _mock_session(mock_driver, mock_session, MagicMock())
        result = await manager.create_relationship(rel)
        assert result is True

    async def test_delete_relationship_success(self, manager, mock_driver, mock_session):
        """测试删除关系成功"""
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: 1
        _mock_session(mock_driver, mock_session, mock_record)

        result = await manager.delete_relationship("entity-001", "entity-002", "MENTIONS")
        assert result is True

    async def test_delete_relationship_not_found(self, manager, mock_driver, mock_session):
        """测试删除不存在的关系"""
        _mock_session(mock_driver, mock_session, None)

        result = await manager.delete_relationship("entity-001", "entity-002", "MENTIONS")
        assert result is False
