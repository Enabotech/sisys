"""GraphRetriever 单元测试"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.storage.neo4j.graph_retriever import GraphRetriever


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
def retriever(mock_driver):
    return GraphRetriever(driver=mock_driver, database="neo4j")


class TestGraphRetriever:
    """GraphRetriever 测试类"""

    async def test_find_related_entities(self, retriever, mock_driver, mock_session):
        """测试实体关联检索"""
        _mock_session(
            mock_driver,
            mock_session,
            [
                {"related": {"id": "entity-002"}, "hops": 1, "connection_count": 3},
                {"related": {"id": "entity-003"}, "hops": 2, "connection_count": 1},
            ],
        )

        result = await retriever.find_related_entities("entity-001", max_depth=2, limit=20)
        assert len(result) == 2
        assert result[0]["entity"]["id"] == "entity-002"
        assert result[0]["hops"] == 1
        assert result[0]["connection_count"] == 3

    async def test_find_related_entities_limit(self, retriever, mock_driver, mock_session):
        """测试结果数量限制"""
        _mock_session(
            mock_driver, mock_session, [{"related": {"id": f"entity-{i}"}, "hops": 1, "connection_count": 1} for i in range(5)]
        )

        result = await retriever.find_related_entities("entity-001", max_depth=2, limit=5)
        assert len(result) == 5

    async def test_find_related_entities_empty(self, retriever, mock_driver, mock_session):
        """测试无关联实体"""
        _mock_session(mock_driver, mock_session, [])

        result = await retriever.find_related_entities("entity-001")
        assert result == []

    async def test_find_related_documents(self, retriever, mock_driver, mock_session):
        """测试文档关联检索"""
        _mock_session(
            mock_driver,
            mock_session,
            [
                {"doc": {"id": "doc-001"}, "mention_count": 5},
                {"doc": {"id": "doc-002"}, "mention_count": 2},
            ],
        )

        result = await retriever.find_related_documents("entity-001", limit=10)
        assert len(result) == 2
        assert result[0]["document"]["id"] == "doc-001"
        assert result[0]["mention_count"] == 5

    async def test_find_related_documents_limit(self, retriever, mock_driver, mock_session):
        """测试文档数量限制"""
        _mock_session(mock_driver, mock_session, [{"doc": {"id": f"doc-{i}"}, "mention_count": 1} for i in range(3)])

        result = await retriever.find_related_documents("entity-001", limit=3)
        assert len(result) == 3

    async def test_find_community(self, retriever, mock_driver, mock_session):
        """测试社区发现"""
        _mock_session(
            mock_driver,
            mock_session,
            [
                {"community_member": {"id": "node-001"}},
                {"community_member": {"id": "node-002"}},
            ],
        )

        result = await retriever.find_community(["node-001", "node-002"])
        assert len(result) == 2

    async def test_find_community_empty_input(self, retriever, mock_driver, mock_session):
        """测试空输入社区发现"""
        result = await retriever.find_community([])
        assert result == []
        mock_driver.session.assert_not_called()
