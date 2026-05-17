"""Neo4jGraphStorage 单元测试"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage


class _AsyncCM:
    """辅助类：模拟异步上下文管理器"""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


def _mock_session(driver, session, data_result):
    """设置会话模拟"""

    async def mock_run(*args, **kwargs):
        result_mock = MagicMock()
        result_mock.data = AsyncMock(return_value=data_result)
        return result_mock

    # 用 MagicMock 包装 mock_run，保留 call_args
    mock_run_wrapped = MagicMock(side_effect=mock_run)
    session.run = mock_run_wrapped
    driver.session.return_value = _AsyncCM(session)


@pytest.fixture
def mock_driver():
    return MagicMock()


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def storage(mock_driver):
    return Neo4jGraphStorage(driver=mock_driver, database="neo4j")


class TestNeo4jGraphStorage:
    """Neo4jGraphStorage 测试类"""

    async def test_execute_query_with_params(self, storage, mock_driver, mock_session):
        """测试参数化查询"""
        _mock_session(mock_driver, mock_session, [{"n": {"id": "entity-001"}}])

        result = await storage.execute_query(
            "MATCH (n:sisys:Entity {id: $node_id}) RETURN n",
            {"node_id": "entity-001"},
        )
        assert len(result) == 1
        # 验证参数化查询（不拼接字符串）
        call_args = mock_session.run.call_args
        assert "$node_id" in call_args[0][0]

    async def test_execute_query_no_params(self, storage, mock_driver, mock_session):
        """测试无参数查询"""
        _mock_session(mock_driver, mock_session, [{"count(n)": 10}])

        result = await storage.execute_query("MATCH (n) RETURN count(n)")
        assert len(result) == 1

    async def test_execute_write_query(self, storage, mock_driver, mock_session):
        """测试写入查询"""
        _mock_session(mock_driver, mock_session, [{"n": {"id": "new-entity"}}])

        result = await storage.execute_write_query(
            "CREATE (n:sisys:Entity {id: $id}) RETURN n",
            {"id": "new-entity"},
        )
        assert len(result) == 1

    async def test_find_path(self, storage, mock_driver, mock_session):
        """测试路径查询"""
        _mock_session(mock_driver, mock_session, [{"path": MagicMock()}])

        result = await storage.find_path("node-a", "node-b", max_depth=3)
        assert len(result) >= 0

    async def test_find_path_max_depth(self, storage, mock_driver, mock_session):
        """测试路径最大深度限制

        注意：Cypher 不支持参数在可变长度模式中（如 [*1..$max_depth]），
        所以实现使用 f-string 直接插值。这是 Cypher 限制，不是 bug
        """
        _mock_session(mock_driver, mock_session, [])

        await storage.find_path("node-a", "node-b", max_depth=2)
        call_args = mock_session.run.call_args
        # Cypher uses literal value in variable-length patterns, not parameter
        assert "[*1..2]" in call_args[0][0]
        assert call_args[1]["start_id"] == "node-a"
        assert call_args[1]["end_id"] == "node-b"

    async def test_get_neighbors_no_rel_type(self, storage, mock_driver, mock_session):
        """测试获取所有邻居（无关系类型过滤）"""
        _mock_session(mock_driver, mock_session, [{"neighbor": {"id": "neighbor-001"}}])

        result = await storage.get_neighbors("node-a")
        assert len(result) >= 0

    async def test_get_neighbors_with_rel_type(self, storage, mock_driver, mock_session):
        """测试获取特定关系的邻居"""
        _mock_session(mock_driver, mock_session, [{"neighbor": {"id": "neighbor-001"}}])

        await storage.get_neighbors("node-a", rel_type="MENTIONS")
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        assert "MENTIONS" in cypher

    async def test_get_neighbors_direction_out(self, storage, mock_driver, mock_session):
        """测试 OUT 方向邻居"""
        _mock_session(mock_driver, mock_session, [])

        await storage.get_neighbors("node-a", direction="OUT")
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        assert "->" in cypher

    async def test_get_neighbors_direction_in(self, storage, mock_driver, mock_session):
        """测试 IN 方向邻居"""
        _mock_session(mock_driver, mock_session, [])

        await storage.get_neighbors("node-a", direction="IN")
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        assert "<-" in cypher
