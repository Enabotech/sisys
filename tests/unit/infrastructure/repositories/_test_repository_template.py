"""
仓储测试模板 - 测试仓储实现。

基础设施层测试特点：
- 测试仓储 CRUD 操作
- 测试事务一致性
- 测试外部服务集成

使用示例：
    复制本文件为 test_<entity>_repository.py，然后根据具体仓储修改
"""

from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from src.domain.entities.base import AggregateRoot
from src.domain.repositories.base import BaseRepository

# ========== 单元测试模板 ==========


class TestEntityRepositoryUnit:
    """实体仓储单元测试模板"""

    @pytest.mark.asyncio
    async def test_repository_add_entity(self, mock_repository):
        """Given 新实体，When 添加，Then 成功添加"""
        # Arrange
        entity = Entity()

        # Act
        result = await mock_repository.add(entity)

        # Assert
        assert result == entity

    @pytest.mark.asyncio
    async def test_repository_get_by_id(self, mock_repository):
        """Given 存在的 ID，When 获取，Then 返回实体"""
        # Arrange
        entity = Entity()
        await mock_repository.add(entity)

        # Act
        result = await mock_repository.get_by_id(entity.id)

        # Assert
        assert result == entity

    @pytest.mark.asyncio
    async def test_repository_get_by_id_not_found(self, mock_repository):
        """Given 不存在的 ID，When 获取，Then 返回 None"""
        # Arrange
        non_existent_id = uuid4()

        # Act
        result = await mock_repository.get_by_id(non_existent_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_repository_update_entity(self, mock_repository):
        """Given 现有实体，When 更新，Then 成功更新"""
        # Arrange
        entity = Entity()
        await mock_repository.add(entity)

        # Act
        result = await mock_repository.update(entity)

        # Assert
        assert result == entity

    @pytest.mark.asyncio
    async def test_repository_delete_existing_entity(self, mock_repository):
        """Given 现有实体，When 删除，Then 成功删除"""
        # Arrange
        entity = Entity()
        await mock_repository.add(entity)

        # Act
        result = await mock_repository.delete(entity.id)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_repository_delete_non_existing_entity(self, mock_repository):
        """Given 不存在的实体，When 删除，Then 返回 False"""
        # Arrange
        non_existent_id = uuid4()

        # Act
        result = await mock_repository.delete(non_existent_id)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_repository_find_all_empty(self, mock_repository):
        """Given 空仓库，When 查询所有，Then 返回空列表"""
        # Act
        result = await mock_repository.find_all()

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_repository_find_all_with_entities(self, mock_repository):
        """Given 有多个实体，When 查询所有，Then 返回所有实体"""
        # Arrange
        entity1 = Entity()
        entity2 = Entity()
        entity3 = Entity()
        await mock_repository.add(entity1)
        await mock_repository.add(entity2)
        await mock_repository.add(entity3)

        # Act
        result = await mock_repository.find_all()

        # Assert
        assert len(result) == 3
        assert entity1 in result
        assert entity2 in result
        assert entity3 in result


# ========== 集成测试模板 ==========


class TestEntityRepositoryIntegration:
    """实体仓储集成测试模板"""

    @pytest.mark.asyncio
    async def test_repository_add_and_get(self, db_session):
        """Given 新实体，When 添加并获取，Then 成功返回"""
        # Arrange
        repository = EntityRepositoryImpl(session=db_session)
        entity = Entity()

        # Act
        saved = await repository.add(entity)
        retrieved = await repository.get_by_id(saved.id)

        # Assert
        assert retrieved is not None
        assert retrieved.id == saved.id

    @pytest.mark.asyncio
    async def test_repository_update(self, db_session):
        """Given 现有实体，When 更新，Then 成功更新"""
        # Arrange
        repository = EntityRepositoryImpl(session=db_session)
        entity = Entity()
        saved = await repository.add(entity)

        # Act
        saved.some_field = "updated_value"
        updated = await repository.update(saved)

        # Assert
        assert updated.some_field == "updated_value"

    @pytest.mark.asyncio
    async def test_repository_delete(self, db_session):
        """Given 现有实体，When 删除，Then 成功删除"""
        # Arrange
        repository = EntityRepositoryImpl(session=db_session)
        entity = Entity()
        saved = await repository.add(entity)

        # Act
        deleted = await repository.delete(saved.id)
        retrieved = await repository.get_by_id(saved.id)

        # Assert
        assert deleted is True
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_repository_transaction_commit(self, db_session):
        """Given 事务操作，When 提交，Then 所有操作持久化"""
        # Arrange
        repository = EntityRepositoryImpl(session=db_session)

        # Act
        entity1 = Entity()
        entity2 = Entity()
        await repository.add(entity1)
        await repository.add(entity2)
        await db_session.commit()

        # Assert
        all_entities = await repository.find_all()
        assert len(all_entities) >= 2

    @pytest.mark.asyncio
    async def test_repository_transaction_rollback(self, db_session):
        """Given 事务操作，When 回滚，Then 所有操作撤销"""
        # Arrange
        repository = EntityRepositoryImpl(session=db_session)
        initial_count = len(await repository.find_all())

        # Act
        entity = Entity()
        await repository.add(entity)
        await db_session.rollback()

        # Assert
        final_count = len(await repository.find_all())
        assert final_count == initial_count


# ========== 测试辅助类模板 ==========


class Entity(AggregateRoot):
    """实体模板"""

    def __init__(self, id=None):
        super().__init__(id)
        self.some_field = "default_value"


class EntityRepositoryImpl(BaseRepository):
    """仓储实现模板"""

    def __init__(self, session):
        self.session = session
        self._storage = {}

    async def get_by_id(self, id):
        """根据 ID 获取实体"""
        return self._storage.get(str(id))

    async def add(self, entity):
        """添加实体"""
        self._storage[str(entity.id)] = entity
        return entity

    async def update(self, entity):
        """更新实体"""
        self._storage[str(entity.id)] = entity
        return entity

    async def delete(self, id):
        """删除实体"""
        id_str = str(id)
        if id_str in self._storage:
            del self._storage[id_str]
            return True
        return False

    async def find_all(self):
        """查询所有实体"""
        return list(self._storage.values())


@pytest.fixture
def mock_repository(mocker: MockerFixture):
    """Mock 仓储 fixture"""
    mock = mocker.AsyncMock(spec=BaseRepository)
    mock.get_by_id = mocker.AsyncMock()
    mock.find_all = mocker.AsyncMock()
    mock.add = mocker.AsyncMock()
    mock.update = mocker.AsyncMock()
    mock.delete = mocker.AsyncMock()
    yield mock


@pytest.fixture
async def db_session():
    """数据库会话 fixture"""
    # 这里应该使用实际的数据库会话
    # 示例中使用内存存储
    yield InMemorySession()


class InMemorySession:
    """内存会话模板"""

    async def commit(self):
        pass

    async def rollback(self):
        pass
