"""应用层战略档案编排服务模块

实现战略档案归档、查询等核心业务流程的编排。
组合 ArchiveRepositoryPort（L2）+ L3VectorPort + L4ObjectPort + L5GraphPort + EventPublisher。
支持 L3/L5 优雅降级。
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.events.archive_events import ArchiveCreated, FactBecameStale, ValidityPeriodSet
from src.domain.exceptions import EntityValidationError
from src.domain.exceptions.archive_exceptions import ArchiveNotFoundError, ArchiveStorageError, ValidityPeriodConflictError
from src.domain.ports.archive_repository import ArchiveQuery, ArchiveRepositoryPort
from src.domain.ports.event_publisher import EventPublisher, PublishResult
from src.domain.ports.l3_vector import L3VectorPort, SearchResult
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
        staleness_service: Any | None = None,
    ) -> None:
        """初始化战略档案编排服务

        Args:
            archive_repo: 档案仓储端口（L2 持久化）
            vector_storage: 向量存储端口（L3，可选，None 时降级）
            object_storage: 对象存储端口（L4）
            graph_storage: 图存储端口（L5，可选，None 时降级）
            event_publisher: 事件发布器
            staleness_service: 陈旧数据降权服务（可选，None 时跳过降权）
        """
        self._archive_repo = archive_repo
        self._vector_storage = vector_storage
        self._object_storage = object_storage
        self._graph_storage = graph_storage
        self._event_publisher = event_publisher
        self._staleness_service = staleness_service

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
                        # Story 3.12: L3 payload 有效期初始快照（直接赋值 None，不经过 str() 转换，
                        # 与 assumptions/decision_basis 的 str(...) 序列化模式相区分）
                        "valid_from": None,
                        "valid_until": None,
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
                        # Story 3.12: L5 properties 有效期初始快照（直接赋值 None，不经过 str() 转换）
                        "valid_from": None,
                        "valid_until": None,
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
            if self._object_storage is not None and blob_ref_val is not None:
                try:
                    await self._object_storage.delete(bucket_type=self.L4_BUCKET_TYPE, object_key=blob_key)
                except Exception:
                    logger.warning("L4 cleanup after L2 ref-update failure failed for archive %s", saved.archive_id)
            raise ArchiveStorageError(layer="l2", cause=e)

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

    async def search_vectors(
        self,
        query_vector: list[float],
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """战略档案向量检索

        通过 L3VectorPort.search() 检索 strategic_archive collection，
        返回 SearchResult 列表，返回前集成 StalenessWeightService 降权。

        Args:
            query_vector: 查询向量
            limit: 返回结果数量限制
            filter_payload: Payload 过滤条件

        Returns:
            降权后的 SearchResult 列表

        Raises:
            ArchiveStorageError: L3 向量存储未注入（None）时抛出
        """
        if self._vector_storage is None:
            raise ArchiveStorageError(layer="l3", cause=RuntimeError("l3_vector not injected"))
        raw = await self._vector_storage.search(
            collection=self.L3_COLLECTION,
            query_vector=query_vector,
            limit=limit,
            filter_payload=filter_payload,
        )
        results = [SearchResult(id=r["id"], score=r["score"], payload=r.get("payload", {})) for r in raw]
        if self._staleness_service is not None:
            results = await self._staleness_service.apply_staleness_weight(results)
        return results

    async def set_validity_period(
        self,
        archive_id: UUID,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
    ) -> StrategicArchive:
        """设置档案有效期

        获取档案，设置有效期，冲突检测，持久化，发布事件。
        使用 find_for_update() 前置锁定同一 plan_id+archive_type 的所有行，
        消除 get_by_id 与冲突检测之间的 TOCTOU 窗口期。

        Args:
            archive_id: 档案 ID
            valid_from: 生效时间（timezone-aware datetime 或 None）
            valid_until: 失效时间（timezone-aware datetime 或 None）

        Returns:
            更新后的 StrategicArchive 实体

        Raises:
            ArchiveNotFoundError: 档案不存在时抛出
            ValidityPeriodConflictError: 有效期冲突时抛出
            ArchiveStorageError: L2 存储失败时抛出
        """
        # 获取档案（用于构造查询条件）
        archive = await self._archive_repo.get_by_id(archive_id)
        if archive is None:
            raise ArchiveNotFoundError(archive_id=archive_id)

        # 冲突检测：同一 plan_id + 同一 archive_type 下，不同 archive_id 的档案
        if archive.plan_id is not None:
            query = ArchiveQuery(
                plan_id=archive.plan_id,
                archive_type=archive.archive_type,
                limit=1000,
            )
            # 使用 find_for_update 悲观锁查询（前置锁定，消除 TOCTOU 窗口期）
            try:
                existing = await self._archive_repo.find_for_update(query)
            except AttributeError:
                # 若 find_for_update 未实现，回退到普通 find
                existing = await self._archive_repo.find(query)

            # 从锁定结果集中重新获取目标档案（获取最新锁定状态，防止 lost update）
            locked = next((a for a in existing if a.archive_id == archive_id), None)
            if locked is None:
                raise ArchiveNotFoundError(archive_id=archive_id)
            archive = locked

            for existing_archive in existing:
                if existing_archive.archive_id == archive_id:
                    continue
                # 半开区间 [valid_from, valid_until) 冲突检测
                if _intervals_overlap(
                    valid_from,
                    valid_until,
                    existing_archive.valid_from,
                    existing_archive.valid_until,
                ):
                    raise ValidityPeriodConflictError(archive_id=archive_id)

        # 更新有效期
        archive.valid_from = valid_from
        archive.valid_until = valid_until

        # 验证有效期
        archive.validate()

        # 持久化
        try:
            saved = await self._archive_repo.save(archive)
        except Exception as e:
            logger.error("L2 save failed for archive %s: %s", archive_id, e)
            raise ArchiveStorageError(layer="l2", cause=e)

        # 发布 ValidityPeriodSet 事件
        if self._event_publisher is not None:
            try:
                event = ValidityPeriodSet(
                    archive_id=saved.archive_id,
                    plan_id=saved.plan_id,
                    archive_type=saved.archive_type,
                    valid_from=saved.valid_from,
                    valid_until=saved.valid_until,
                )
                result: PublishResult = await self._event_publisher.publish(event)
                if not result.is_success:
                    logger.warning("ValidityPeriodSet event publish partial failure: %s", result.partial_error)
            except Exception as e:
                logger.warning("ValidityPeriodSet event publish failed: %s", e)

        return saved

    async def is_stale(self, archive_id: UUID) -> bool:
        """检查单个档案是否陈旧

        委托实体方法 StrategicArchive.is_stale()，统一陈旧判定标准。

        Args:
            archive_id: 档案 ID

        Returns:
            陈旧返回 True，否则返回 False

        Raises:
            ArchiveNotFoundError: 档案不存在时抛出
            ArchiveStorageError: L2 查询失败时抛出
        """
        try:
            archive = await self._archive_repo.get_by_id(archive_id)
        except Exception as e:
            logger.error("L2 query failed for archive %s: %s", archive_id, e)
            raise ArchiveStorageError(layer="l2", cause=e)
        if archive is None:
            raise ArchiveNotFoundError(archive_id=archive_id)
        return archive.is_stale()

    async def mark_stale_archives(self, batch_size: int = 100) -> list[StrategicArchive]:
        """批量标记陈旧档案（幂等设计）

        查询所有 valid_until < now 或 valid_until IS NULL AND archived_at < now - 12个月
        且尚未标记陈旧的档案，逐批标记并发布 FactBecameStale 事件。

        Story 3.12 并发安全：查询使用 find_for_update() 悲观锁，
        避免与 set_validity_period() 的竞态（读取陈旧判断后有效期被更新导致错误标记）。

        Args:
            batch_size: 每批查询数量（默认 100）

        Returns:
            被标记为陈旧的档案列表
        """
        now = datetime.now(UTC)
        marked: list[StrategicArchive] = []
        offset = 0

        while True:
            # 结果集会因本轮标记而动态缩小；offset 只累计本轮保留的 fresh 记录，
            # 不累计被标记后从结果集中消失的记录。
            query = ArchiveQuery(
                limit=batch_size,
                offset=offset,
                exclude_staleness=True,
            )
            try:
                # find_for_update() 悲观锁：锁定待标记行，避免 TOCTOU 竞态
                batch = await self._archive_repo.find_for_update(query)
            except Exception as e:
                logger.error("L2 query failed while scanning stale archives: %s", e)
                break

            if not batch:
                break

            retained_count = 0
            for archive in batch:
                # 陈旧判定（复用实体统一判定标准，区分陈旧原因）
                if archive.is_stale(ref_date=now):
                    stale_reason = "expired" if archive.valid_until is not None else "archived_too_long"
                else:
                    retained_count += 1
                    continue

                # 实体自包含行为：通过 mark_stale() 封装 metadata 写入
                # （含 stale_reason 持久化，供 API 响应 stale_reason 字段读取）
                archive.mark_stale(now, stale_reason)

                # 条件标记：SQL 层原子判定，被并发实例抢先标记时跳过事件
                claimed = await self._archive_repo.mark_stale(
                    archive.archive_id,
                    stale_since=now.isoformat(),
                    stale_reason=stale_reason,
                )
                if not claimed:
                    logger.info(
                        "Archive %s already marked stale by another instance, skip event",
                        archive.archive_id,
                    )
                    continue

                # 重新获取实体以获取最新 metadata 状态
                saved = await self._archive_repo.get_by_id(archive.archive_id)
                if saved is None:
                    logger.warning("Archive %s disappeared before mark_stale readback", archive.archive_id)
                    continue

                marked.append(saved)

                # 发布 FactBecameStale 事件
                if self._event_publisher is not None:
                    try:
                        event = FactBecameStale(
                            archive_id=saved.archive_id,
                            plan_id=saved.plan_id,
                            archive_type=saved.archive_type,
                            valid_until=saved.valid_until,
                            stale_reason=stale_reason,
                            stale_since=now,
                        )
                        result: PublishResult = await self._event_publisher.publish(event)
                        if not result.is_success:
                            logger.warning("FactBecameStale event publish partial failure: %s", result.partial_error)
                    except Exception as e:
                        logger.warning("FactBecameStale event publish failed for archive %s: %s", saved.archive_id, e)

            offset += retained_count

        return marked


def _intervals_overlap(
    a_from: Any,
    a_until: Any,
    b_from: Any,
    b_until: Any,
) -> bool:
    """检测两个半开区间 [valid_from, valid_until) 是否有重叠

    None 表示开区间端点（无限远）。
    端点相接（a_until == b_from）不视为冲突。

    Returns:
        重叠返回 True，否则返回 False
    """
    # 处理 None 为无限远端点（使用 timezone-aware 的 min/max 避免与 aware datetime 比较时崩溃）
    a_start = a_from if a_from is not None else datetime.min.replace(tzinfo=UTC)
    a_end = a_until if a_until is not None else datetime.max.replace(tzinfo=UTC)
    b_start = b_from if b_from is not None else datetime.min.replace(tzinfo=UTC)
    b_end = b_until if b_until is not None else datetime.max.replace(tzinfo=UTC)

    # 半开区间 [start, end)：a_start < b_end and a_end > b_start
    return a_start < b_end and a_end > b_start


__all__ = [
    "StrategicArchiveService",
]
