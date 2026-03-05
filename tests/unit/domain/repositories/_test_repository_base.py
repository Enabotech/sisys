"""
仓储基类测试 - 测试 BaseRepository、UnitOfWork。

领域层测试特点：
- 快速执行（无外部依赖）
- 100% 内存执行
- 验证业务规则
- 验证领域不变量
"""

from uuid import uuid4

import pytest

from src.domain.entities.base import AggregateRoot
from src.domain.exceptions import NotFoundError
from src.domain.repositories.base import BaseRepository, UnitOfWork


class TestBaseRepository:
    """BaseRepository 基类测试"""

    @pytest.mark.asyncio
    async def test_repository_get_by_id_not_found(self):
        """Given 不存在的 ID，When 获取实体，Then 返回 None"""
        # Arrange
        repository = InMemoryTestRepository()
        non_existent_id = uuid4()

        # Act
        result = await repository.get_by_id(non_existent_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_repository_get_by_id_or_raise_not_found(self):
        """Given 不存在的 ID，When 获取实体或抛异常，Then 抛出 NotFoundError"""
        # Arrange
        repository = InMemoryTestRepository()
        non_existent_id = uuid4()

        # Act & Assert
        with pytest.raises(NotFoundError):
            await repository.get_by_id_or_raise(non_existent_id)

    @pytest.mark.asyncio
    async def test_repository_get_by_id_or_raise_found(self):
        """Given 存在的 ID，When 获取实体或抛异常，Then 返回实体"""
        # Arrange
        repository = InMemoryTestRepository()
        entity = TestAggregateRoot()
        await repository.add(entity)

        # Act
        result = await repository.get_by_id_or_raise(entity.id)

        # Assert
        assert result == entity

    @pytest.mark.asyncio
    async def test_repository_add(self):
        """Given 新实体，When 添加，Then 成功添加"""
        # Arrange
        repository = InMemoryTestRepository()
        entity = TestAggregateRoot()

        # Act
        result = await repository.add(entity)

        # Assert
        assert result == entity
        assert await repository.get_by_id(entity.id) == entity

    @pytest.mark.asyncio
    async def test_repository_update(self):
        """Given 现有实体，When 更新，Then 成功更新"""
        # Arrange
        repository = InMemoryTestRepository()
        entity = TestAggregateRoot()
        await repository.add(entity)

        # Act
        result = await repository.update(entity)

        # Assert
        assert result == entity

    @pytest.mark.asyncio
    async def test_repository_delete_existing(self):
        """Given 现有实体，When 删除，Then 成功删除"""
        # Arrange
        repository = InMemoryTestRepository()
        entity = TestAggregateRoot()
        await repository.add(entity)

        # Act
        result = await repository.delete(entity.id)

        # Assert
        assert result is True
        assert await repository.get_by_id(entity.id) is None

    @pytest.mark.asyncio
    async def test_repository_delete_non_existing(self):
        """Given 不存在的实体，When 删除，Then 返回 False"""
        # Arrange
        repository = InMemoryTestRepository()
        non_existent_id = uuid4()

        # Act
        result = await repository.delete(non_existent_id)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_repository_find_all_empty(self):
        """Given 空仓库，When 查询所有，Then 返回空列表"""
        # Arrange
        repository = InMemoryTestRepository()

        # Act
        result = await repository.find_all()

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_repository_find_all_with_entities(self):
        """Given 有多个实体，When 查询所有，Then 返回所有实体"""
        # Arrange
        repository = InMemoryTestRepository()
        entity1 = TestAggregateRoot()
        entity2 = TestAggregateRoot()
        entity3 = TestAggregateRoot()
        await repository.add(entity1)
        await repository.add(entity2)
        await repository.add(entity3)

        # Act
        result = await repository.find_all()

        # Assert
        assert len(result) == 3
        assert entity1 in result
        assert entity2 in result
        assert entity3 in result

    def test_repository_entity_name(self):
        """Given 仓储实例，When 获取实体名称，Then 返回正确的名称"""
        # Arrange
        repository = InMemoryTestRepository()

        # Act
        result = repository._entity_name()

        # Assert
        assert result == "Test"


class TestUnitOfWork:
    """UnitOfWork 工作单元测试"""

    @pytest.mark.asyncio
    async def test_unit_of_work_commit(self):
        """Given 工作单元，When 提交，Then 成功提交"""
        # Arrange
        uow = InMemoryUnitOfWork()

        # Act
        await uow.commit()

        # Assert
        assert uow.committed is True

    @pytest.mark.asyncio
    async def test_unit_of_work_rollback(self):
        """Given 工作单元，When 回滚，Then 成功回滚"""
        # Arrange
        uow = InMemoryUnitOfWork()

        # Act
        await uow.rollback()

        # Assert
        assert uow.rolled_back is True

    @pytest.mark.asyncio
    async def test_unit_of_work_close(self):
        """Given 工作单元，When 关闭，Then 成功关闭"""
        # Arrange
        uow = InMemoryUnitOfWork()

        # Act
        await uow.close()

        # Assert
        assert uow.closed is True


# ========== 测试辅助类 ==========


class TestAggregateRoot(AggregateRoot):
    """测试用聚合根"""

    def __init__(self, id=None):
        super().__init__(id)


class InMemoryTestRepository(BaseRepository):
    """内存测试仓储实现"""

    def __init__(self):
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


class InMemoryUnitOfWork(UnitOfWork):
    """内存工作单元实现"""

    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False

    async def commit(self):
        """提交"""
        self.committed = True

    async def rollback(self):
        """回滚"""
        self.rolled_back = True

    async def close(self):
        """关闭"""
        self.closed = True
