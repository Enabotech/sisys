"""PostgreSQLAdapter 单元测试（原 BaseRepository 测试适配）

测试 CRUD 操作和事务回滚
"""

from __future__ import annotations

from unittest import mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.models import UserModel
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import PostgreSQLAdapter
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


class _TestUserAdapter(PostgreSQLAdapter[UserModel, UserModel]):
    """测试用恒等转换适配器"""

    def _to_entity(self, model: UserModel) -> UserModel:
        return model

    def _to_model(self, entity: UserModel) -> UserModel:
        return entity


@pytest.fixture
def mock_session():
    """创建模拟数据库会话"""
    session = mock.AsyncMock(spec=AsyncSession)
    session.add = mock.Mock()
    session.delete = mock.Mock()
    session.flush = mock.AsyncMock()
    session.refresh = mock.AsyncMock()
    return session


@pytest.fixture
def repository(mock_session):
    """创建 PostgreSQLAdapter 测试实例"""
    token = set_session(mock_session)
    repo = _TestUserAdapter(UserModel)
    yield repo
    reset_session(token)


class TestPostgreSQLAdapter:
    """PostgreSQLAdapter 测试"""

    @pytest.mark.asyncio
    async def test_get_by_id_exists(self, repository, mock_session):
        """测试获取存在的实体"""
        user = mock.Mock()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id("test-id")

        assert result == user
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repository, mock_session):
        """测试获取不存在的实体"""
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_save_insert(self, repository, mock_session):
        """测试保存实体（_do_save 默认插入）"""
        user = mock.Mock()
        mock_session.flush = mock.AsyncMock()
        mock_session.refresh = mock.AsyncMock()

        await repository.save(user)

        mock_session.add.assert_called_once_with(user)
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_hard(self, repository, mock_session):
        """测试硬删除存在的实体"""
        user = mock.Mock()
        mock_session.execute = mock.AsyncMock()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = mock_result
        mock_session.delete = mock.AsyncMock()
        mock_session.flush = mock.AsyncMock()

        await repository.delete("test-id")

        mock_session.delete.assert_called_once_with(user)
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, repository, mock_session):
        """测试删除不存在的实体（无操作）"""
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.delete("nonexistent")

        mock_session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_all(self, repository, mock_session):
        """测试获取实体列表"""
        users = [mock.Mock(), mock.Mock()]
        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = users
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.list_all(skip=0, limit=10)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_count(self, repository, mock_session):
        """测试获取实体总数"""
        mock_result = mock.Mock()
        mock_result.scalar.return_value = 5
        mock_session.execute.return_value = mock_result

        result = await repository.count()

        assert result == 5


class TestSessionContextFriendlyError:
    """验证 ContextVar 未设置时的友好错误信息"""

    def test_session_not_set_contains_repository_name(self):
        """验证错误信息包含具体仓库名"""
        repo = _TestUserAdapter(UserModel)
        with pytest.raises(RuntimeError, match="_TestUserAdapter requires an active AsyncSession"):
            _ = repo._session

    def test_session_not_set_contains_fix_suggestion(self):
        """验证错误信息包含修复建议"""
        repo = _TestUserAdapter(UserModel)
        with pytest.raises(RuntimeError, match="SessionMiddleware or session_context"):
            _ = repo._session

    @pytest.mark.asyncio
    async def test_session_set_works_normally(self, mock_session):
        """验证 ContextVar 已设置时正常工作"""
        token = set_session(mock_session)
        try:
            repo = _TestUserAdapter(UserModel)
            assert repo._session is mock_session
        finally:
            reset_session(token)
