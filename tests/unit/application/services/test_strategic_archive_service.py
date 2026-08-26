"""StrategicArchiveService 应用服务单元测试

使用 Mock 端口验证归档编排、优雅降级和查询逻辑。
遵循 Mock 端口策略（仅单元测试允许）。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from src.application.services.strategic_archive_service import StrategicArchiveService
from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.exceptions import ArchiveNotFoundError
from src.domain.exceptions.archive_exceptions import ArchiveStorageError as ArchiveStoreErr
from src.domain.exceptions.archive_exceptions import ValidityPeriodConflictError
from src.domain.ports.archive_repository import ArchiveQuery, ArchiveRepositoryPort
from src.domain.ports.embedding_service import EmbeddingServicePort
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


def _make_embedding() -> Any:
    """创建 Mock 嵌入服务"""
    mock = AsyncMock(spec=EmbeddingServicePort)
    mock.embed_query.return_value = [0.1] * 1024
    return mock


def _make_staleness_service() -> Any:
    """创建 Mock 降权服务"""
    from src.application.services.staleness_weight_service import StalenessWeightService

    mock = AsyncMock(spec=StalenessWeightService)
    mock.apply_staleness_weight.side_effect = lambda results: results
    return mock


class TestArchivePlan:
    """archive_plan() 归档编排测试"""

    @pytest.fixture
    def service(self) -> StrategicArchiveService:
        """创建 Mock 服务实例"""
        return StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, _make_repo()),
            embedding_service=_make_embedding(),
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
    async def test_archive_plan_l3_payload_contains_validity_fields(self, service: StrategicArchiveService) -> None:
        """L3 payload 包含 valid_from/valid_until 初始值 None（Story 3.12 AC-1）"""
        plan_id = uuid.uuid4()
        await service.archive_plan(
            plan_id=plan_id,
            plan_type="SP",
            assumptions={"key": "value"},
            decision_basis={},
            execution_deviation={},
        )
        vector = cast(Any, service._vector_storage)
        assert vector.upsert_points.called
        call_args = vector.upsert_points.call_args[1]
        points = call_args["points"]
        assert len(points) == 1
        payload = points[0].get("payload", {})
        # valid_from/valid_union 直接赋值为 None（不经过 str() 转换）
        assert "valid_from" in payload
        assert payload["valid_from"] is None
        assert "valid_until" in payload
        assert payload["valid_until"] is None

    @pytest.mark.asyncio
    async def test_archive_plan_l5_properties_contains_validity_fields(self, service: StrategicArchiveService) -> None:
        """L5 properties 包含 valid_from/valid_until 初始值 None（Story 3.12 AC-1）"""
        plan_id = uuid.uuid4()
        await service.archive_plan(
            plan_id=plan_id,
            plan_type="SP",
            assumptions={},
            decision_basis={},
            execution_deviation={},
        )
        graph = cast(Any, service._graph_storage)
        assert graph.create_entity.called
        call_args = graph.create_entity.call_args[1]
        properties = call_args.get("properties", {})
        assert "valid_from" in properties
        assert properties["valid_from"] is None
        assert "valid_until" in properties
        assert properties["valid_until"] is None

    @pytest.mark.asyncio
    async def test_archive_plan_l2_failure_raises(self) -> None:
        """L2 失败抛出 ArchiveStorageError"""
        repo = AsyncMock(spec=ArchiveRepositoryPort)
        repo.save.side_effect = RuntimeError("db down")
        service = StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, repo),
            embedding_service=_make_embedding(),
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
            embedding_service=_make_embedding(),
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
            embedding_service=_make_embedding(),
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
            embedding_service=_make_embedding(),
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
            embedding_service=_make_embedding(),
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

    @pytest.mark.asyncio
    async def test_archive_plan_event_publish_partial_failure_raises(self) -> None:
        """archive_plan 事件发布返回 is_success=False 时抛出 ArchiveStorageError（原子性）"""
        from src.domain.events.publish_result import ChannelResult, PublishResult

        repo = _make_repo()
        vector = _make_vector()
        obj = _make_object_storage()
        graph = _make_graph()
        publisher = _make_publisher()
        publisher.publish.return_value = PublishResult(
            event_id="test",
            results=(ChannelResult(channel_name="reliable", success=False, error="outbox full"),),
        )
        service = StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, repo),
            embedding_service=_make_embedding(),
            vector_storage=cast(L3VectorPort, vector),
            object_storage=cast(L4ObjectPort, obj),
            graph_storage=cast(L5GraphPort, graph),
            event_publisher=cast(EventPublisher, publisher),
        )
        with pytest.raises(ArchiveStoreErr) as exc_info:
            await service.archive_plan(
                plan_id=uuid.uuid4(),
                plan_type="SP",
                assumptions={},
                decision_basis={},
                execution_deviation={},
            )
        assert "event publish" in str(exc_info.value.cause).lower()

    @pytest.mark.asyncio
    async def test_archive_plan_event_publish_exception_raises(self) -> None:
        """archive_plan 事件发布抛出异常时抛出 ArchiveStorageError（原子性）"""
        repo = _make_repo()
        vector = _make_vector()
        obj = _make_object_storage()
        graph = _make_graph()
        publisher = _make_publisher()
        publisher.publish.side_effect = RuntimeError("broker unreachable")
        service = StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, repo),
            embedding_service=_make_embedding(),
            vector_storage=cast(L3VectorPort, vector),
            object_storage=cast(L4ObjectPort, obj),
            graph_storage=cast(L5GraphPort, graph),
            event_publisher=cast(EventPublisher, publisher),
        )
        with pytest.raises(ArchiveStoreErr):
            await service.archive_plan(
                plan_id=uuid.uuid4(),
                plan_type="SP",
                assumptions={},
                decision_basis={},
                execution_deviation={},
            )


class TestQuery:
    """get_archive()/query_archive() 查询测试"""

    @pytest.fixture
    def service(self) -> StrategicArchiveService:
        """创建 Mock 服务实例"""
        return StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, _make_repo()),
            embedding_service=_make_embedding(),
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


class TestSetValidityPeriod:
    """set_validity_period() 有效期管理测试"""

    @pytest.mark.asyncio
    async def test_sets_validity_and_saves(self) -> None:
        """设置有效期并持久化"""
        service, repo, archive = _make_validity_service()
        vf = datetime(2026, 1, 1, tzinfo=UTC)
        vu = datetime(2027, 12, 31, tzinfo=UTC)
        # find_for_update 返回目标档案（无冲突）
        repo.find_for_update.return_value = [archive]
        result = await service.set_validity_period(archive.archive_id, vf, vu)
        assert result.valid_from == vf
        assert result.valid_until == vu
        assert repo.save.called

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        """档案不存在抛出 ArchiveNotFoundError"""
        service, repo, _ = _make_validity_service()
        repo.get_by_id.return_value = None
        with pytest.raises(ArchiveNotFoundError):
            await service.set_validity_period(uuid.uuid4(), None, None)

    @pytest.mark.asyncio
    async def test_conflict_detected(self) -> None:
        """有效期冲突抛出 ValidityPeriodConflictError"""
        service, repo, archive = _make_validity_service()
        # 存在另一档案，其有效期与新区间重叠
        other = _make_archive(
            {"valid_from": datetime(2026, 6, 1, tzinfo=UTC), "valid_until": datetime(2026, 12, 31, tzinfo=UTC)}
        )
        # find_for_update 返回目标档案 + 冲突档案
        repo.find_for_update.return_value = [other, archive]
        with pytest.raises(ValidityPeriodConflictError):
            await service.set_validity_period(
                archive.archive_id,
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2027, 6, 1, tzinfo=UTC),
            )

    @pytest.mark.asyncio
    async def test_no_conflict_when_adjacent(self) -> None:
        """端点相接不视为冲突"""
        service, repo, archive = _make_validity_service()
        # 其他档案 valid_until == 新区间 valid_from，半开区间不重叠
        other = _make_archive({"valid_from": datetime(2025, 1, 1, tzinfo=UTC), "valid_until": datetime(2026, 1, 1, tzinfo=UTC)})
        # find_for_update 返回目标档案 + 相邻档案
        repo.find_for_update.return_value = [other, archive]
        result = await service.set_validity_period(
            archive.archive_id,
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2027, 6, 1, tzinfo=UTC),
        )
        assert result.valid_from == datetime(2026, 1, 1, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_publishes_validity_event(self) -> None:
        """发布 ValidityPeriodSet 事件"""
        service, repo, archive = _make_validity_service()
        repo.find_for_update.return_value = [archive]
        vf = datetime(2026, 1, 1, tzinfo=UTC)
        vu = datetime(2027, 12, 31, tzinfo=UTC)
        await service.set_validity_period(archive.archive_id, vf, vu)
        publisher = cast(Any, service._event_publisher)
        assert publisher.publish.called
        event = publisher.publish.call_args[0][0]
        assert event.event_type == "ValidityPeriodSet"
        assert event.archive_id == archive.archive_id
        assert event.valid_from == vf
        assert event.valid_until == vu

    @pytest.mark.asyncio
    async def test_l2_failure_raises_archive_storage_error(self) -> None:
        """L2 保存失败抛出 ArchiveStorageError(layer=l2)"""
        service, repo, archive = _make_validity_service()
        repo.find_for_update.return_value = [archive]
        repo.save.side_effect = RuntimeError("db down")
        with pytest.raises(ArchiveStoreErr) as exc_info:
            await service.set_validity_period(archive.archive_id, None, datetime(2027, 12, 31, tzinfo=UTC))
        assert exc_info.value.layer == "l2"

    @pytest.mark.asyncio
    async def test_event_publish_partial_failure_raises(self) -> None:
        """事件发布返回 is_success=False 时抛出 ArchiveStorageError（原子性）"""
        from src.domain.events.publish_result import ChannelResult, PublishResult

        service, repo, archive = _make_validity_service()
        repo.find_for_update.return_value = [archive]
        publisher = cast(Any, service._event_publisher)
        publisher.publish.return_value = PublishResult(
            event_id="test",
            results=(ChannelResult(channel_name="reliable", success=False, error="outbox full"),),
        )
        with pytest.raises(ArchiveStoreErr) as exc_info:
            await service.set_validity_period(
                archive.archive_id,
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2027, 12, 31, tzinfo=UTC),
            )
        assert "event publish" in str(exc_info.value.cause).lower()

    @pytest.mark.asyncio
    async def test_event_publish_exception_raises(self) -> None:
        """事件发布抛出异常时抛出 ArchiveStorageError（原子性）"""
        service, repo, archive = _make_validity_service()
        repo.find_for_update.return_value = [archive]
        publisher = cast(Any, service._event_publisher)
        publisher.publish.side_effect = RuntimeError("broker unreachable")
        with pytest.raises(ArchiveStoreErr):
            await service.set_validity_period(
                archive.archive_id,
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2027, 12, 31, tzinfo=UTC),
            )


class TestIsStale:
    """is_stale() 陈旧检查测试"""

    @pytest.mark.asyncio
    async def test_stale_when_expired(self) -> None:
        """valid_until 过期标记为陈旧"""
        service, repo, archive = _make_validity_service(valid_until=datetime(2021, 1, 1, tzinfo=UTC))
        repo.get_by_id.return_value = archive
        assert await service.is_stale(archive.archive_id) is True

    @pytest.mark.asyncio
    async def test_not_stale_when_in_validity(self) -> None:
        """有效期内不标记陈旧"""
        service, repo, archive = _make_validity_service(valid_until=datetime(2099, 12, 31, tzinfo=UTC))
        repo.get_by_id.return_value = archive
        assert await service.is_stale(archive.archive_id) is False

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        """档案不存在抛出 ArchiveNotFoundError"""
        service, repo, _ = _make_validity_service()
        repo.get_by_id.return_value = None
        with pytest.raises(ArchiveNotFoundError):
            await service.is_stale(uuid.uuid4())


class TestMarkStaleArchives:
    """mark_stale_archives() 批量陈旧标记测试"""

    @pytest.mark.asyncio
    async def test_marks_expired_archives(self) -> None:
        """标记过期档案"""
        service, repo, _ = _make_validity_service()
        expired = _make_archive({"valid_until": datetime(2021, 1, 1, tzinfo=UTC)})
        valid = _make_archive({"valid_until": datetime(2099, 12, 31, tzinfo=UTC)})
        repo.find_for_update.side_effect = [[expired, valid], []]
        repo.mark_stale.return_value = True
        repo.get_by_id.return_value = expired
        marked = await service.mark_stale_archives()
        # 仅过期档案被标记
        assert len(marked) == 1
        assert marked[0].archive_id == expired.archive_id

    @pytest.mark.asyncio
    async def test_marks_archived_too_long(self) -> None:
        """valid_until 为 None 且归档超 12 个月标记陈旧"""
        service, repo, _ = _make_validity_service()
        old = _make_archive({"valid_until": None, "archived_at": datetime.now(UTC) - timedelta(days=400)})
        repo.find_for_update.side_effect = [[old], []]
        repo.mark_stale.return_value = True
        repo.get_by_id.return_value = old
        marked = await service.mark_stale_archives()
        assert len(marked) == 1
        assert marked[0].archive_id == old.archive_id

    @pytest.mark.asyncio
    async def test_skips_already_marked(self) -> None:
        """已标记档案跳过（幂等）"""
        service, repo, _ = _make_validity_service()
        # exclude_staleness=True 在 SQL 层已过滤已标记档案，find_for_update 返回空
        repo.find_for_update.side_effect = [[], []]
        marked = await service.mark_stale_archives()
        assert len(marked) == 0
        # 已被过滤，无需调用 mark_stale
        assert not repo.mark_stale.called

    @pytest.mark.asyncio
    async def test_skips_when_mark_stale_returns_false(self) -> None:
        """mark_stale 返回 False（被并发实例抢占）时跳过事件"""
        service, repo, _ = _make_validity_service()
        expired = _make_archive({"valid_until": datetime(2021, 1, 1, tzinfo=UTC)})
        repo.find_for_update.side_effect = [[expired], []]
        repo.mark_stale.return_value = False  # 被其他实例抢先标记
        marked = await service.mark_stale_archives()
        assert len(marked) == 0
        publisher = cast(Any, service._event_publisher)
        assert not publisher.publish.called

    @pytest.mark.asyncio
    async def test_publishes_fact_became_stale(self) -> None:
        """发布 FactBecameStale 事件"""
        service, repo, _ = _make_validity_service()
        expired = _make_archive({"valid_until": datetime(2021, 1, 1, tzinfo=UTC)})
        repo.find_for_update.side_effect = [[expired], []]
        repo.mark_stale.return_value = True
        repo.get_by_id.return_value = expired
        await service.mark_stale_archives()
        publisher = cast(Any, service._event_publisher)
        assert publisher.publish.called
        event = publisher.publish.call_args[0][0]
        assert event.event_type == "FactBecameStale"
        assert event.stale_reason == "expired"

    @pytest.mark.asyncio
    async def test_marks_none_for_skipped_archived_too_long(self) -> None:
        """valid_until 和 archived_at 均为 None 不标记"""
        service, repo, _ = _make_validity_service()
        neither = _make_archive({"valid_until": None, "archived_at": None})
        repo.find_for_update.side_effect = [[neither], []]
        marked = await service.mark_stale_archives()
        assert len(marked) == 0

    @pytest.mark.asyncio
    async def test_mark_stale_persists_stale_reason(self) -> None:
        """标记陈旧时持久化 stale_reason 到 metadata（Story 3.12 AC-3）"""
        service, repo, _ = _make_validity_service()
        expired = _make_archive({"valid_until": datetime(2021, 1, 1, tzinfo=UTC)})
        repo.find_for_update.side_effect = [[expired], []]
        repo.mark_stale.return_value = True
        repo.get_by_id.return_value = expired
        marked = await service.mark_stale_archives()
        assert len(marked) == 1
        # 实体 mark_stale() 方法写入 metadata 的 stale_reason
        assert marked[0].metadata["stale_reason"] == "expired"
        assert marked[0].metadata["staleness"] == "stale"
        assert "stale_since" in marked[0].metadata

    @pytest.mark.asyncio
    async def test_mark_stale_passes_stale_since_and_reason(self) -> None:
        """mark_stale 调用时传递 stale_since 和 stale_reason 参数（Fix 2 回归验证）"""
        service, repo, _ = _make_validity_service()
        expired = _make_archive({"valid_until": datetime(2021, 1, 1, tzinfo=UTC)})
        repo.find_for_update.side_effect = [[expired], []]
        repo.mark_stale.return_value = True
        repo.get_by_id.return_value = expired
        await service.mark_stale_archives()
        assert repo.mark_stale.called
        call_kwargs = repo.mark_stale.call_args[1]
        assert "stale_since" in call_kwargs
        assert call_kwargs["stale_since"] is not None
        assert "T" in call_kwargs["stale_since"]
        assert call_kwargs["stale_reason"] == "expired"


def _make_validity_service(
    valid_until: Any = None,
    valid_from: Any = None,
) -> tuple[StrategicArchiveService, Any, StrategicArchive]:
    """构造带有有效期字段的 Mock 服务"""
    repo = _make_repo()
    repo.get_by_id.side_effect = None
    repo.find.return_value = []
    repo.find_for_update.return_value = []
    repo.mark_stale.return_value = True
    archive = _make_archive(
        {
            "valid_from": valid_from,
            "valid_until": valid_until,
        }
    )
    repo.get_by_id.return_value = archive
    publisher = _make_publisher()
    service = StrategicArchiveService(
        archive_repo=repo,
        vector_storage=None,
        object_storage=None,
        graph_storage=None,
        event_publisher=publisher,
    )
    return service, repo, archive


class TestSearchVectors:
    """search_vectors() 向量检索降权集成测试（Story 3.12 AC-4）"""

    @pytest.fixture
    def service(self) -> StrategicArchiveService:
        """创建带降权服务的 Mock 服务实例"""
        return StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, _make_repo()),
            embedding_service=_make_embedding(),
            vector_storage=cast(L3VectorPort, _make_vector()),
            object_storage=cast(L4ObjectPort, _make_object_storage()),
            graph_storage=cast(L5GraphPort, _make_graph()),
            event_publisher=cast(EventPublisher, _make_publisher()),
            staleness_service=_make_staleness_service(),
        )

    @pytest.mark.asyncio
    async def test_search_vectors_returns_search_results(self, service: StrategicArchiveService) -> None:
        """search_vectors() 返回 list[SearchResult]（类型正确）"""
        vector = cast(Any, service._vector_storage)
        vector.search.return_value = [
            {"id": "strategic_archive:1111", "score": 0.9, "payload": {"archive_id": "1111"}},
        ]
        results = await service.search_vectors(
            query_vector=[0.1] * 1024,
            limit=10,
        )
        assert len(results) == 1
        assert isinstance(results[0], dict)
        assert "id" in results[0]
        assert "score" in results[0]
        assert "payload" in results[0]

    @pytest.mark.asyncio
    async def test_search_vectors_calls_staleness_weight(self, service: StrategicArchiveService) -> None:
        """search_vectors() 返回前调用 apply_staleness_weight()"""
        vector = cast(Any, service._vector_storage)
        vector.search.return_value = [
            {"id": "strategic_archive:1111", "score": 0.9, "payload": {"archive_id": "1111"}},
        ]
        stale = cast(Any, service._staleness_service)
        await service.search_vectors(query_vector=[0.1] * 1024)
        assert stale.apply_staleness_weight.called

    @pytest.mark.asyncio
    async def test_search_vectors_no_staleness_service(self) -> None:
        """staleness_service 为 None 时跳过降权（透明降级）"""
        svc = StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, _make_repo()),
            embedding_service=_make_embedding(),
            vector_storage=cast(L3VectorPort, _make_vector()),
            object_storage=cast(L4ObjectPort, _make_object_storage()),
            graph_storage=cast(L5GraphPort, _make_graph()),
            event_publisher=cast(EventPublisher, _make_publisher()),
            staleness_service=None,
        )
        vector = cast(Any, svc._vector_storage)
        vector.search.return_value = [
            {"id": "strategic_archive:1111", "score": 0.9, "payload": {"archive_id": "1111"}},
        ]
        results = await svc.search_vectors(query_vector=[0.1] * 1024)
        assert len(results) == 1
        assert results[0]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_search_vectors_stale_after_fresh(self, service: StrategicArchiveService) -> None:
        """降权后排序正确性：陈旧数据 score 降低，排序位置变化"""
        vector = cast(Any, service._vector_storage)
        stale_svc = cast(Any, service._staleness_service)
        from src.application.services.staleness_weight_service import STALE_WEIGHT_FACTOR

        # 模拟降权：陈旧数据 score *= 0.5
        async def _weight(results):
            for r in results:
                payload = r.get("payload", {})
                if payload.get("is_stale"):
                    r["score"] = r["score"] * STALE_WEIGHT_FACTOR
            results.sort(key=lambda x: (-x["score"], str(x["id"])))
            return results

        stale_svc.apply_staleness_weight.side_effect = _weight
        vector.search.return_value = [
            {"id": "strategic_archive:1111", "score": 0.9, "payload": {"archive_id": "1111", "is_stale": True}},
            {"id": "strategic_archive:2222", "score": 0.8, "payload": {"archive_id": "2222", "is_stale": False}},
        ]
        results = await service.search_vectors(query_vector=[0.1] * 1024)
        # 新鲜 0.8 > 陈旧 0.45
        assert len(results) == 2
        assert results[0]["id"] == "strategic_archive:2222"  # fresh 0.8
        assert results[1]["id"] == "strategic_archive:1111"  # stale 0.45

    @pytest.mark.asyncio
    async def test_search_vectors_result_count_unchanged(self, service: StrategicArchiveService) -> None:
        """返回结果数量不变（只调整 score 和顺序）"""
        vector = cast(Any, service._vector_storage)
        vector.search.return_value = [
            {"id": "a", "score": 0.9, "payload": {"archive_id": "a", "is_stale": True}},
            {"id": "b", "score": 0.8, "payload": {"archive_id": "b", "is_stale": False}},
            {"id": "c", "score": 0.7, "payload": {"archive_id": "c", "is_stale": True}},
        ]
        results = await service.search_vectors(query_vector=[0.1] * 1024)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_vectors_empty_results(self, service: StrategicArchiveService) -> None:
        """空结果集返回空列表"""
        vector = cast(Any, service._vector_storage)
        vector.search.return_value = []
        results = await service.search_vectors(query_vector=[0.1] * 1024)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_vectors_l3_not_injected_raises(self) -> None:
        """L3 未注入时抛出 ArchiveStorageError"""
        svc = StrategicArchiveService(
            archive_repo=cast(ArchiveRepositoryPort, _make_repo()),
            embedding_service=_make_embedding(),
            vector_storage=None,
            object_storage=cast(L4ObjectPort, _make_object_storage()),
            graph_storage=cast(L5GraphPort, _make_graph()),
            event_publisher=cast(EventPublisher, _make_publisher()),
        )
        with pytest.raises(ArchiveStoreErr):
            await svc.search_vectors(query_vector=[0.1] * 1024)
