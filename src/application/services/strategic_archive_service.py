"""应用层战略档案编排服务模块

实现战略档案归档、查询等核心业务流程的编排。
组合 ArchiveRepositoryPort（L2）+ L3VectorPort + L4ObjectPort + L5GraphPort + EventPublisher。
支持 L3/L5 优雅降级。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any
from uuid import UUID

from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.events.archive_events import ArchiveCreated
from src.domain.exceptions import EntityValidationError
from src.domain.exceptions.archive_exceptions import ArchiveNotFoundError, ArchiveStorageError
from src.domain.ports.archive_repository import ArchiveQuery, ArchiveRepositoryPort
from src.domain.ports.event_publisher import EventPublisher, PublishResult
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.l4_object import L4ObjectPort
from src.domain.ports.l5_graph import L5GraphPort

logger = logging.getLogger(__name__)


class StrategicArchiveService:
    """战略档案编排服务

    组合 L2-L5 存储层及事件发布，提供完整的战略档案归档与查询能力。
    L3/L5 存储层失败时优雅降级，不影响 L2+L4 主流程。
    """

    L3_COLLECTION = "strategic_archive"
    L4_BUCKET_TYPE = "archive-evidence"

    def __init__(
        self,
        archive_repo: ArchiveRepositoryPort,
        vector_storage: L3VectorPort | None = None,
        object_storage: L4ObjectPort | None = None,
        graph_storage: L5GraphPort | None = None,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        """初始化战略档案编排服务

        Args:
            archive_repo: 档案仓储端口（L2 持久化）
            vector_storage: 向量存储端口（L3，可选，None 时降级）
            object_storage: 对象存储端口（L4）
            graph_storage: 图存储端口（L5，可选，None 时降级）
            event_publisher: 事件发布器
        """
        self._archive_repo = archive_repo
        self._vector_storage = vector_storage
        self._object_storage = object_storage
        self._graph_storage = graph_storage
        self._event_publisher = event_publisher

    async def archive_plan(
        self,
        plan_id: UUID,
        plan_type: str,
        archive_type: ArchiveType = ArchiveType.ASSUMPTION,
        assumptions: dict[str, Any] | None = None,
        decision_basis: dict[str, Any] | None = None,
        execution_deviation: dict[str, Any] | None = None,
        evidence_blob: bytes | None = None,
    ) -> StrategicArchive:
        """归档战略规划

        创建 StrategicArchive 实体，按序写入 L2（元数据）+ L3（向量）+ L4（对象）+ L5（图谱）。
        L3/L5 失败优雅降级，L2/L4 失败抛出 ArchiveStorageError。

        Args:
            plan_id: 规划 ID
            plan_type: 规划类型（"SP"/"BP"）
            archive_type: 档案类型（默认 ASSUMPTION）
            assumptions: 关键假设变量
            decision_basis: 决策依据
            execution_deviation: 实际执行偏差
            evidence_blob: 证据包内容（bytes）

        Returns:
            已持久化的 StrategicArchive 实体

        Raises:
            ArchiveStorageError: L2 或 L4 存储失败时抛出
        """
        from datetime import UTC, datetime

        if plan_type not in ("SP", "BP"):
            raise EntityValidationError(
                message="plan_type must be 'SP' or 'BP'",
                context={"entity": "StrategicArchive", "field": "plan_type"},
            )

        now = datetime.now(UTC)
        archive = StrategicArchive(
            archive_id=uuid.uuid4(),
            plan_id=plan_id,
            plan_type=plan_type,
            archive_type=archive_type,
            assumptions=assumptions or {},
            decision_basis=decision_basis or {},
            execution_deviation=execution_deviation or {},
            metadata_ref=f"strategic_archives:{uuid.uuid4()}",
            created_at=now,
            archived_at=now,
        )
        archive.validate()

        # Step 1: L2 元数据持久化（强制成功）
        try:
            saved = await self._archive_repo.save(archive)
        except Exception as e:
            logger.error("L2 metadata save failed: %s", e)
            raise ArchiveStorageError(layer="l2", cause=e)

        # 生成存储引用
        embedding_point_id = f"strategic_archive:{saved.archive_id}"
        embedding_ref: str | None = embedding_point_id
        blob_key = f"{saved.archive_id}/{now.isoformat()}_{saved.archive_type.value}.json"
        blob_ref: str | None = blob_key
        graph_node_id = str(saved.archive_id)
        graph_ref: str | None = graph_node_id
        # 修正 metadata_ref 为真实 archive_id
        saved.metadata_ref = f"strategic_archives:{saved.archive_id}"

        # Step 2: L3 向量存储（可降级）
        has_embedding = False
        if self._vector_storage is not None:
            try:
                point = {
                    "id": embedding_point_id,
                    "vector": [0.0] * 1024,  # 占位向量，实际由 embedding service 生成
                    "payload": {
                        "archive_id": str(saved.archive_id),
                        "plan_id": str(plan_id),
                        "plan_type": plan_type,
                        "archive_type": saved.archive_type.value,
                        "assumptions": str(assumptions or {}),
                        "decision_basis": str(decision_basis or {}),
                        "created_at": now.isoformat(),
                    },
                }
                success = await self._vector_storage.upsert_points(
                    collection=self.L3_COLLECTION,
                    points=[point],
                )
                if success:
                    has_embedding = True
                else:
                    # upsert_points 返回 False 表示部分失败，清理脏数据
                    logger.warning("L3 upsert_points returned False for archive %s, cleaning up", saved.archive_id)
                    try:
                        await self._vector_storage.delete_points(
                            collection=self.L3_COLLECTION,
                            point_ids=[embedding_point_id],
                        )
                    except Exception as cleanup_err:
                        logger.warning("L3 cleanup failed for archive %s: %s", saved.archive_id, cleanup_err)
                    embedding_ref = None
            except Exception as e:
                logger.warning("L3 vector storage failed for archive %s (degraded): %s", saved.archive_id, e)
                embedding_ref = None
        else:
            embedding_ref = None

        # Step 3: L4 对象存储（强制成功）
        blob_ref_val: str | None = blob_ref
        if evidence_blob and self._object_storage is not None:
            try:
                await self._object_storage.archive(
                    bucket_type=self.L4_BUCKET_TYPE,
                    object_key=blob_key,
                    content=evidence_blob,
                    retention_days=2555,
                )
            except Exception as e:
                logger.error("L4 object archive failed for archive %s: %s", saved.archive_id, e)
                # L4 失败时清理已写入的 L3 向量点，避免脏数据残留
                if self._vector_storage is not None and embedding_ref is not None:
                    try:
                        await self._vector_storage.delete_points(
                            collection=self.L3_COLLECTION,
                            point_ids=[embedding_point_id],
                        )
                    except Exception as cleanup_err:
                        logger.warning("L3 cleanup after L4 failure failed for archive %s: %s", saved.archive_id, cleanup_err)
                raise ArchiveStorageError(layer="l4", cause=e)
        else:
            blob_ref_val = None

        # Step 4: L5 图存储（可降级）
        has_graph = False
        graph_ref_val: str | None = graph_ref
        if self._graph_storage is not None:
            try:
                success = await self._graph_storage.create_entity(
                    memory_id=graph_node_id,
                    entity_type="StrategicArchive",
                    properties={
                        "plan_id": str(plan_id),
                        "plan_type": plan_type,
                        "archive_type": saved.archive_type.value,
                        "created_at": now.isoformat(),
                    },
                )
                if success:
                    has_graph = True
                else:
                    logger.warning("L5 create_entity returned False for archive %s, degrading", saved.archive_id)
                    graph_ref_val = None
            except Exception as e:
                logger.warning("L5 graph storage failed for archive %s (degraded): %s", saved.archive_id, e)
                graph_ref_val = None
        else:
            graph_ref_val = None

        # 更新存储引用
        saved.embedding_ref = embedding_ref
        saved.blob_ref = blob_ref_val
        saved.graph_ref = graph_ref_val
        # 将更新后的存储引用写回 L2（失败时需清理 L3/L4/L5 脏数据）
        try:
            saved = await self._archive_repo.save(saved)
        except Exception as e:
            logger.error("L2 metadata update failed for archive %s: %s", saved.archive_id, e)
            # 尽力清理 L3/L4/L5 脏数据
            if self._vector_storage is not None and embedding_ref is not None:
                try:
                    await self._vector_storage.delete_points(collection=self.L3_COLLECTION, point_ids=[embedding_point_id])
                except Exception:
                    logger.warning("L3 cleanup after L2 ref-update failure failed for archive %s", saved.archive_id)
            if self._graph_storage is not None and graph_ref_val is not None:
                try:
                    await self._graph_storage.delete_entity(memory_id=graph_node_id)
                except Exception:
                    logger.warning("L5 cleanup after L2 ref-update failure failed for archive %s", saved.archive_id)

        # Step 5: 发布 ArchiveCreated 事件
        if self._event_publisher is not None:
            try:
                event = ArchiveCreated(
                    archive_id=saved.archive_id,
                    plan_id=plan_id,
                    plan_type=plan_type,
                    archive_type=saved.archive_type,
                    has_embedding=has_embedding,
                    has_blob=blob_ref_val is not None,
                    has_graph=has_graph,
                )
                result: PublishResult = await self._event_publisher.publish(event)
                if not result.is_success:
                    logger.warning("ArchiveCreated event publish partial failure: %s", result.partial_error)
            except Exception as e:
                logger.warning("ArchiveCreated event publish failed: %s", e)

        return saved

    async def get_archive(self, archive_id: UUID) -> StrategicArchive:
        """按 ID 获取档案详情

        Args:
            archive_id: 档案 ID

        Returns:
            StrategicArchive 实体

        Raises:
            ArchiveNotFoundError: 档案不存在时抛出
        """
        archive = await self._archive_repo.get_by_id(archive_id)
        if archive is None:
            raise ArchiveNotFoundError(archive_id=archive_id)
        return archive

    async def query_archive(self, query: ArchiveQuery) -> list[StrategicArchive]:
        """按条件查询档案

        Args:
            query: 查询条件（ArchiveQuery 值对象）

        Returns:
            符合条件的档案列表
        """
        return await self._archive_repo.find(query)


__all__ = [
    "StrategicArchiveService",
]
