"""PermissionRepository 单元测试

验证权限仓储的实体/模型转换、CRUD 操作和查询方法
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, cast
from unittest import mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.permission import Permission
from src.infrastructure.storage.postgresql.repository.permission_repository import PermissionRepository
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


def _make_permission_model(**overrides) -> SimpleNamespace:
    """构造模拟 PermissionModel 的 SimpleNamespace（属性返回真实值）"""
    defaults = {
        "id": uuid.uuid4(),
        "name": "read:document",
        "resource": "document",
        "action": "read",
        "created_at": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def mock_session():
    return mock.AsyncMock(spec=AsyncSession)


@pytest.fixture
def repository(mock_session):
    token = set_session(mock_session)
    repo = PermissionRepository()
    yield repo
    reset_session(token)


class TestPermissionRepository:
    """PermissionRepository 测试"""

    async def test_get_by_name(self, repository, mock_session):
        """测试根据名称获取权限"""
        model = _make_permission_model()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_name("read:document")

        assert isinstance(result, Permission)
        assert result.id == model.id
        assert result.name == model.name

    async def test_get_by_name_not_found(self, repository, mock_session):
        """测试根据名称获取不存在的权限"""
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_name("nonexistent")

        assert result is None


class TestPermissionRepositoryConversion:
    """PermissionRepository 实体/模型转换测试"""

    def test_to_entity_maps_all_fields(self) -> None:
        """_to_entity 应正确映射所有字段"""
        repo = PermissionRepository()
        model_id = uuid.uuid4()
        model = _make_permission_model(
            id=model_id,
            name="write:report",
            resource="report",
            action="write",
        )

        entity = repo._to_entity(cast("Any", model))

        assert isinstance(entity, Permission)
        assert entity.id == model_id
        assert entity.name == "write:report"
        assert entity.resource == "report"
        assert entity.action == "write"
        assert entity.created_at is None

    def test_to_model_maps_all_fields(self) -> None:
        """_to_model 应正确映射字段（不含 created_at）"""
        from src.infrastructure.storage.postgresql.models import PermissionModel

        repo = PermissionRepository()
        entity_id = uuid.uuid4()
        entity = Permission(
            id=entity_id,
            name="delete:user",
            resource="user",
            action="delete",
        )

        model = repo._to_model(entity)

        assert isinstance(model, PermissionModel)
        assert model.id == entity_id
        assert model.name == "delete:user"
        assert model.resource == "user"
        assert model.action == "delete"

    def test_to_entity_preserves_created_at(self) -> None:
        """_to_entity 应保留 created_at 字段"""
        from datetime import datetime, timezone

        repo = PermissionRepository()
        now = datetime.now(tz=timezone.utc)
        model = _make_permission_model(
            name="read:config",
            resource="config",
            action="read",
            created_at=now,
        )

        entity = repo._to_entity(cast("Any", model))

        assert entity.created_at == now


class TestPermissionRepositoryCrudOperations:
    """PermissionRepository CRUD 操作测试"""

    async def test_save_delegates_to_do_save(
        self,
        repository: PermissionRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """save 应将实体转为模型并通过 _do_save 持久化"""
        entity = Permission(
            id=uuid.uuid4(),
            name="execute:job",
            resource="job",
            action="execute",
        )
        mock_do_save = mock.AsyncMock()
        # 使用 cast 绕过 mypy 对方法赋值的限制
        setattr(repository, "_do_save", mock_do_save)

        result = await repository.save(entity)

        mock_do_save.assert_called_once()
        assert isinstance(result, Permission)

    async def test_save_converts_entity_to_model(
        self,
        repository: PermissionRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """save 应将实体转换为 ORM 模型传递给 _do_save"""
        entity_id = uuid.uuid4()
        entity = Permission(
            id=entity_id,
            name="read:log",
            resource="log",
            action="read",
        )
        mock_do_save = mock.AsyncMock()
        setattr(repository, "_do_save", mock_do_save)

        await repository.save(entity)

        saved_model = mock_do_save.call_args[0][0]
        assert saved_model.id == entity_id
        assert saved_model.name == "read:log"
        assert saved_model.resource == "log"
        assert saved_model.action == "read"

    async def test_hard_delete_calls_execute_and_flush(
        self,
        repository: PermissionRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """delete（硬删除）应查询后调用 session.delete 和 flush"""
        entity_id = uuid.uuid4()
        model = _make_permission_model(id=entity_id, name="update:settings", resource="settings", action="update")

        # 第一次 execute：查询要删除的 model
        mock_select_result = mock.Mock()
        mock_select_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_select_result

        await repository.delete(entity_id)

        mock_session.delete.assert_called_once_with(model)
        mock_session.flush.assert_called()

    async def test_list_all_returns_entity_list(
        self,
        repository: PermissionRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """list_all 应返回实体列表"""
        model1 = _make_permission_model(name="read:doc")
        model2 = _make_permission_model(name="write:doc")

        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = [model1, model2]
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.list_all()

        assert len(result) == 2
        assert all(isinstance(e, Permission) for e in result)
        assert result[0].name == "read:doc"
        assert result[1].name == "write:doc"

    async def test_get_by_id_returns_entity(
        self,
        repository: PermissionRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """get_by_id 应返回对应的实体"""
        model = _make_permission_model(name="read:audit")
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(model.id)

        assert isinstance(result, Permission)
        assert result.id == model.id
        assert result.name == "read:audit"

    async def test_get_by_id_not_found(
        self,
        repository: PermissionRepository,
        mock_session: mock.AsyncMock,
    ) -> None:
        """get_by_id 未找到时应返回 None"""
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(uuid.uuid4())

        assert result is None
