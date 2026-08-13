"""StrategicArchiveService 应用服务单元测试

使用 Mock 端口验证归档编排、优雅降级和查询逻辑。
遵循 Mock 端口策略（仅单元测试允许）。
"""

from __future__ import annotations

import uuid
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from src.application.services.strategic_archive_service import StrategicArchiveService
from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.exceptions import ArchiveNotFoundError
from src.domain.exceptions.archive_exceptions import ArchiveStorageError as ArchiveStoreErr
from src.domain.ports.archive_repository import ArchiveQuery, ArchiveRepositoryPort
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.l4_object import L4ObjectPort
from src.domain.ports.l5_graph import L5GraphPort


def _make_archive(overrides: dict[str, Any] | None = None) -> StrategicArchive:
    """创建测试用档案实体"""
    archive_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    archive = StrategicArchive(
        archive_id=archive_id,
        plan_id=plan_id,
        plan_type="SP",
        archive_type=ArchiveType.ASSUMPTION,
        assumptions={"market": "grow"},
        decision_basis={"method": "A"},
        execution_deviation={"cost": 0.1},
        metadata_ref="strategic_archives:test",
    )
    if overrides:
        for key, value in overrides.items():
            setattr(archive, key, value)
    return archive


def _make_repo() -> Any:
    """创建 Mock 仓储"""
    repo = AsyncMock(spec=ArchiveRepositoryPort)
    repo.save.side_effect = lambda a: a
    return repo


def _make_vector() -> Any:
    """创建 Mock 向量存储"""
    return AsyncMock(spec=L3VectorPort)


def _make_object_storage() -> Any:
    """创建 Mock 对象存储"""
    return AsyncMock(spec=L4ObjectPort)


def _make_graph() -> Any:
    """创建 Mock 图存储"""
    return AsyncMock(spec=L5GraphPort)


def _make_publisher() -> Any:
    """创建 Mock 事件发布器"""
    return AsyncMock(spec=EventPublisher)


class TestArchivePlan:
    """archive_plan() 归档编排测试"""

    @pytest.fixture
    def service(self) -> StrategicArchiveService:
        """创建 Mock 服务实例"""
        return StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, _make_repo()),
            vector_storage=cast(L3VectorPort, _make_vector()),
            object_storage=cast(L4ObjectPort, _make_object_storage()),
            graph_storage=cast(L5GraphPort, _make_graph()),
            event_publisher=cast(EventPublisher, _make_publisher()),
        )

    @pytest.mark.asyncio
    async def test_archive_plan_calls_all_layers(self, service: StrategicArchiveService) -> None:
        """归档流程调用 L2+L3+L4+L5"""
        plan_id = uuid.uuid4()
        await service.archive_plan(
            plan_id=plan_id,
            plan_type="SP",
            assumptions={"key": "value"},
            decision_basis={},
            execution_deviation={},
            evidence_blob=b"evidence",
        )
        repo = cast(Any, service._archive_repo)
        vector = cast(Any, service._vector_storage)
        obj = cast(Any, service._object_storage)
        graph = cast(Any, service._graph_storage)
        publisher = cast(Any, service._event_publisher)
        assert repo.save.called
        assert vector.upsert_points.called
        assert obj.archive.called
        assert graph.create_entity.called
        assert publisher.publish.called

    @pytest.mark.asyncio
    async def test_archive_plan_sets_storage_refs(self, service: StrategicArchiveService) -> None:
        """存储引用字段正确设置"""
        plan_id = uuid.uuid4()
        archive = await service.archive_plan(
            plan_id=plan_id,
            plan_type="SP",
            assumptions={},
            decision_basis={},
            execution_deviation={},
            evidence_blob=b"evidence",
        )
        assert archive.metadata_ref == f"strategic_archives:{archive.archive_id}"
        assert archive.embedding_ref == f"strategic_archive:{archive.archive_id}"
        assert archive.blob_ref is not None
        assert archive.graph_ref == str(archive.archive_id)

    @pytest.mark.asyncio
    async def test_archive_plan_l2_failure_raises(self) -> None:
        """L2 失败抛出 ArchiveStorageError"""
        repo = AsyncMock(spec=ArchiveRepositoryPort)
        repo.save.side_effect = RuntimeError("db down")
        service = StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, repo),
            vector_storage=cast(L3VectorPort, _make_vector()),
            object_storage=cast(L4ObjectPort, _make_object_storage()),
            graph_storage=cast(L5GraphPort, _make_graph()),
            event_publisher=cast(EventPublisher, _make_publisher()),
        )
        with pytest.raises(ArchiveStoreErr):
            await service.archive_plan(
                plan_id=uuid.uuid4(),
                plan_type="SP",
                assumptions={},
                decision_basis={},
                execution_deviation={},
            )

    @pytest.mark.asyncio
    async def test_archive_plan_l4_failure_raises(self, service: StrategicArchiveService) -> None:
        """L4 失败抛出 ArchiveStorageError"""
        obj = cast(Any, service._object_storage)
        obj.archive.side_effect = RuntimeError("minio down")
        with pytest.raises(ArchiveStoreErr):
            await service.archive_plan(
                plan_id=uuid.uuid4(),
                plan_type="SP",
                assumptions={},
                decision_basis={},
                execution_deviation={},
                evidence_blob=b"evidence",
            )


class TestDegradation:
    """优雅降级测试"""

    @pytest.mark.asyncio
    async def test_l3_failure_degrades(self) -> None:
        """L3 失败时 embedding_ref 为 None，主流程继续"""
        repo = _make_repo()
        vector = _make_vector()
        obj = _make_object_storage()
        graph = _make_graph()
        publisher = _make_publisher()
        vector.upsert_points.side_effect = RuntimeError("qdrant down")
        service = StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, repo),
            vector_storage=cast(L3VectorPort, vector),
            object_storage=cast(L4ObjectPort, obj),
            graph_storage=cast(L5GraphPort, graph),
            event_publisher=cast(EventPublisher, publisher),
        )
        archive = await service.archive_plan(
            plan_id=uuid.uuid4(),
            plan_type="SP",
            assumptions={},
            decision_basis={},
            execution_deviation={},
            evidence_blob=b"evidence",
        )
        assert archive.embedding_ref is None
        assert repo.save.called
        assert obj.archive.called
        assert publisher.publish.called

    @pytest.mark.asyncio
    async def test_l5_failure_degrades(self) -> None:
        """L5 失败时 graph_ref 为 None，主流程继续"""
        repo = _make_repo()
        vector = _make_vector()
        obj = _make_object_storage()
        graph = _make_graph()
        publisher = _make_publisher()
        graph.create_entity.side_effect = RuntimeError("neo4j down")
        service = StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, repo),
            vector_storage=cast(L3VectorPort, vector),
            object_storage=cast(L4ObjectPort, obj),
            graph_storage=cast(L5GraphPort, graph),
            event_publisher=cast(EventPublisher, publisher),
        )
        archive = await service.archive_plan(
            plan_id=uuid.uuid4(),
            plan_type="SP",
            assumptions={},
            decision_basis={},
            execution_deviation={},
            evidence_blob=b"evidence",
        )
        assert archive.graph_ref is None
        assert repo.save.called
        assert obj.archive.called
        assert publisher.publish.called

    @pytest.mark.asyncio
    async def test_l3_partial_failure_cleans_up(self) -> None:
        """L3 upsert_points 返回 False 时调用 delete_points 清理脏数据"""
        repo = _make_repo()
        vector = _make_vector()
        vector.upsert_points.return_value = False
        service = StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, repo),
            vector_storage=cast(L3VectorPort, vector),
            object_storage=cast(L4ObjectPort, _make_object_storage()),
            graph_storage=cast(L5GraphPort, _make_graph()),
            event_publisher=cast(EventPublisher, _make_publisher()),
        )
        archive = await service.archive_plan(
            plan_id=uuid.uuid4(),
            plan_type="SP",
            assumptions={},
            decision_basis={},
            execution_deviation={},
            evidence_blob=b"evidence",
        )
        assert vector.delete_points.called
        assert archive.embedding_ref is None

    @pytest.mark.asyncio
    async def test_l5_partial_failure_degrades(self) -> None:
        """L5 create_entity 返回 False 时 graph_ref 为 None"""
        repo = _make_repo()
        vector = _make_vector()
        obj = _make_object_storage()
        graph = _make_graph()
        publisher = _make_publisher()
        graph.create_entity.return_value = False
        service = StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, repo),
            vector_storage=cast(L3VectorPort, vector),
            object_storage=cast(L4ObjectPort, obj),
            graph_storage=cast(L5GraphPort, graph),
            event_publisher=cast(EventPublisher, publisher),
        )
        archive = await service.archive_plan(
            plan_id=uuid.uuid4(),
            plan_type="SP",
            assumptions={},
            decision_basis={},
            execution_deviation={},
            evidence_blob=b"evidence",
        )
        assert archive.graph_ref is None


class TestQuery:
    """get_archive()/query_archive() 查询测试"""

    @pytest.fixture
    def service(self) -> StrategicArchiveService:
        """创建 Mock 服务实例"""
        return StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, _make_repo()),
            vector_storage=cast(L3VectorPort, _make_vector()),
            object_storage=cast(L4ObjectPort, _make_object_storage()),
            graph_storage=cast(L5GraphPort, _make_graph()),
            event_publisher=cast(EventPublisher, _make_publisher()),
        )

    @pytest.mark.asyncio
    async def test_get_archive_found(self, service: StrategicArchiveService) -> None:
        """get_archive 返回实体"""
        archive = _make_archive()
        repo = cast(Any, service._archive_repo)
        repo.get_by_id.return_value = archive
        result = await service.get_archive(archive.archive_id)
        assert result == archive
        assert repo.get_by_id.called

    @pytest.mark.asyncio
    async def test_get_archive_not_found_raises(self, service: StrategicArchiveService) -> None:
        """get_archive 不存在时抛出 ArchiveNotFoundError"""
        repo = cast(Any, service._archive_repo)
        repo.get_by_id.return_value = None
        with pytest.raises(ArchiveNotFoundError):
            await service.get_archive(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_query_archive_delegates(self, service: StrategicArchiveService) -> None:
        """query_archive 委托仓储 find"""
        query = ArchiveQuery(archive_type=ArchiveType.ASSUMPTION)
        expected = [_make_archive()]
        repo = cast(Any, service._archive_repo)
        repo.find.return_value = expected
        result = await service.query_archive(query)
        assert result == expected
        assert repo.find.called
