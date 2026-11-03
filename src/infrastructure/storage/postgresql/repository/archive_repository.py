"""基础设施层 PostgreSQL 档案仓储模块

实现 ArchiveRepositoryPort 端口，使用 PostgreSQL 持久化战略档案元数据。
继承 PostgreSQLAdapter 泛型基类，支持软删除和 ArchiveQuery 查询。

双模式 session（6-4 代码审查 CR1-F1——照抄 isolation DC-5 / audit R1-DF1 修复
形态，家族第五个补齐 fallback 的成员）：
- 请求路径： ``get_session()`` 命中 ContextVar（HTTP 请求事务内）→ 行为与
  既有逐字节等价（merge+flush，持久性随外层请求事务）；
- fallback 路径： ``get_session()`` 抛 ``RuntimeError``（CLI/后台上下文）→
  经注入 ``session_factory`` 走 ``session_context()`` 独立会话 commit——
  CLI ``blm-plan`` 思维链归档（save×2：Step1 落行 + 引用回写 merge UPSERT）
  与 ``chain-query`` 追溯检索（find）的可达性前提。

⚠️ 防呆： fallback 分派直调 ``session_context.get_session()`` 并 catch
``RuntimeError``（isolation 模板 L12-14 同款）——经 ``PostgreSQLAdapter._session``
property 则会把 RuntimeError 包成 InvalidStateError（``from None``），except
永不命中。

范围注记（调用图已核）：仅 save/find 两方法补 fallback（6-4 两 CLI 场景的
唯一触达面）；其余 ``self._session`` 直用方法（find_for_update/mark_stale/
list_by_plan/list_by_archive_type/count 及继承 get_by_id/delete）的消费方均
无 CLI 入口，维持 206 显式失败。相对 isolation 模板不移植
SQLAlchemyError → StorageError 包装链——ArchiveRepositoryPort 无 Raises
声明（端口契约面），且 archive_plan Step1/Step5 均 ``except Exception`` 宽捕
包 284，原生异常透传对消费面行为等价。
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.ports.archive_repository import ArchiveQuery
from src.infrastructure.storage.postgresql.models.archive import ArchiveModel
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import PostgreSQLAdapter
from src.infrastructure.storage.postgresql.session_context import get_session, session_context

logger = logging.getLogger(__name__)


class PostgreSQLArchiveRepository(PostgreSQLAdapter[StrategicArchive, ArchiveModel]):
    """战略档案仓储实现

    继承 PostgreSQLAdapter[StrategicArchive, ArchiveModel]，
    通过 _to_entity/_to_model 隔离领域层与 ORM 层。
    支持软删除（deleted_at 列）和 ArchiveQuery 多条件组合查询。
    双模式 session（请求 ContextVar 优先 + factory fallback——类 docstring 见模块头）。
    """

    pk_column: str = "archive_id"
    soft_delete_column: str = "deleted_at"

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        """初始化档案仓储.

        Args:
            session_factory: fallback 独立会话工厂（CLI/后台路径——None 时无
                ContextVar session 则 RuntimeError 上抛，配置缺失显式失败——
                R1-DF3 有意设计同款；组合根恒注入使生产 CLI 不落此形态）。
        """
        super().__init__(ArchiveModel)
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # 实体/模型转换
    # ------------------------------------------------------------------

    def _to_entity(self, model: ArchiveModel) -> StrategicArchive:
        """将 ORM 模型转换为领域实体"""
        try:
            archive_type = ArchiveType(model.archive_type) if model.archive_type else ArchiveType.ASSUMPTION
        except ValueError:
            logger.warning(
                "Invalid archive_type %r in DB for archive %s, defaulting to ASSUMPTION",
                model.archive_type,
                model.archive_id,
            )
            archive_type = ArchiveType.ASSUMPTION
        return StrategicArchive(
            archive_id=model.archive_id,
            plan_id=model.plan_id,
            plan_type=model.plan_type or "",
            archive_type=archive_type,
            created_by=model.created_by,
            version=model.version,
            assumptions=model.assumptions or {},
            decision_basis=model.decision_basis or {},
            execution_deviation=model.execution_deviation or {},
            metadata_ref=model.metadata_ref or "",
            embedding_ref=model.embedding_ref,
            blob_ref=model.blob_ref,
            graph_ref=model.graph_ref,
            created_at=model.created_at,
            archived_at=model.archived_at,
            deleted_at=model.deleted_at,
            valid_from=model.valid_from,
            valid_until=model.valid_until,
            metadata=model.metadata_ or {},
        )

    def _to_model(self, archive: StrategicArchive) -> ArchiveModel:
        """将领域实体转换为 ORM 模型"""
        return ArchiveModel(
            archive_id=archive.archive_id,
            plan_id=archive.plan_id,
            plan_type=archive.plan_type,
            archive_type=archive.archive_type.value if archive.archive_type else "assumption",
            assumptions=archive.assumptions,
            decision_basis=archive.decision_basis,
            execution_deviation=archive.execution_deviation,
            metadata_ref=archive.metadata_ref,
            embedding_ref=archive.embedding_ref,
            blob_ref=archive.blob_ref,
            graph_ref=archive.graph_ref,
            created_by=archive.created_by,
            version=archive.version,
            metadata_=archive.metadata,
            deleted_at=archive.deleted_at,
            created_at=archive.created_at,
            archived_at=archive.archived_at,
            valid_from=archive.valid_from,
            valid_until=archive.valid_until,
        )

    # ------------------------------------------------------------------
    # ArchiveRepositoryPort 实现
    # ------------------------------------------------------------------

    def _apply_filters(self, stmt: Any, query: ArchiveQuery) -> Any:
        """应用 ArchiveQuery 过滤条件到 statement

        Args:
            stmt: SQLAlchemy select/count statement
            query: ArchiveQuery 查询条件

        Returns:
            添加了过滤条件的 statement
        """
        from datetime import UTC, datetime, timedelta

        if query.plan_id is not None:
            stmt = stmt.where(ArchiveModel.plan_id == query.plan_id)
        if query.archive_type is not None:
            stmt = stmt.where(ArchiveModel.archive_type == query.archive_type.value)
        if query.plan_type is not None:
            stmt = stmt.where(ArchiveModel.plan_type == query.plan_type)
        if query.start_date is not None:
            stmt = stmt.where(ArchiveModel.archived_at >= query.start_date)
        if query.end_date is not None:
            stmt = stmt.where(ArchiveModel.archived_at <= query.end_date)
        if query.valid_from is not None:
            stmt = stmt.where(ArchiveModel.valid_from >= query.valid_from)
        if query.valid_until is not None:
            stmt = stmt.where(ArchiveModel.valid_until <= query.valid_until)
        if query.validity_status is not None:
            now = datetime.now(UTC)
            if query.validity_status.value == "valid":
                # (valid_from IS NULL OR valid_from <= now) AND (valid_until >= now OR valid_until IS NULL)
                stmt = stmt.where((ArchiveModel.valid_from.is_(None)) | (ArchiveModel.valid_from <= now))
                stmt = stmt.where((ArchiveModel.valid_until >= now) | (ArchiveModel.valid_until.is_(None)))
            elif query.validity_status.value == "expired":
                stmt = stmt.where(ArchiveModel.valid_until < now)
        # 排除已标记陈旧的档案（幂等保证）
        if query.exclude_staleness:
            stmt = stmt.where(func.coalesce(ArchiveModel.metadata_["staleness"].astext, "") != "stale")
        # 仅返回满足实体 is_stale() 判定的候选，避免服务层重复扫描 fresh 档案
        if query.stale_before is not None:
            cutoff = query.stale_before - timedelta(days=365)
            stmt = stmt.where(
                (ArchiveModel.valid_until < query.stale_before)
                | ((ArchiveModel.valid_until.is_(None)) & (ArchiveModel.archived_at < cutoff))
            )
        # staleness_status 过滤（Story 3.12 AC-6）
        if query.staleness_status is not None:
            if query.staleness_status == "stale":
                stmt = stmt.where(ArchiveModel.metadata_["staleness"].astext == "stale")
            elif query.staleness_status == "fresh":
                stmt = stmt.where(ArchiveModel.metadata_["staleness"].astext.is_distinct_from("stale"))
        # archive_ids 批量查询（Story 3.12 - StalenessWeightService 兜底链）
        if query.archive_ids is not None:
            stmt = stmt.where(ArchiveModel.archive_id.in_(query.archive_ids))
        return stmt

    async def save(self, entity: StrategicArchive) -> StrategicArchive:
        """保存实体（双模式 session——请求路径优先，CLI/后台走独立会话 commit）.

        子类覆写仅做 fallback 分派（tool_execution_repository :64-93 同款）——
        merge 语义复用基类 PostgreSQLAdapter.save（主键 UPSERT，引用回写二次
        save 亦经此路径，不先按 archive_id 查行）。

        Args:
            entity: 领域实体

        Returns:
            持久化后的领域实体（含数据库生成的 id、时间戳等）
        """
        try:
            get_session()
        except RuntimeError:
            # CLI/后台路径（无请求 session）——经注入工厂走独立会话 commit
            if self._session_factory is None:
                raise
            async with session_context(self._session_factory):
                return await super().save(entity)
        return await super().save(entity)

    async def find(self, query: ArchiveQuery) -> list[StrategicArchive]:
        """按条件查询档案（双模式 session——请求路径优先，CLI/后台走独立会话）.

        Args:
            query: 查询条件（ArchiveQuery 值对象）

        Returns:
            符合条件的档案列表
        """
        try:
            get_session()
        except RuntimeError:
            # CLI 检索路径（chain-query）——find 也必须走 fallback 才可达
            if self._session_factory is None:
                raise
            async with session_context(self._session_factory):
                return await self._do_find(query)
        return await self._do_find(query)

    async def _do_find(self, query: ArchiveQuery) -> list[StrategicArchive]:
        """在当前上下文 session 上执行档案查询（find 的查询体——双模式共用）.

        Args:
            query: 查询条件（ArchiveQuery 值对象）

        Returns:
            符合条件的档案列表
        """
        stmt = select(ArchiveModel)
        stmt = self._apply_soft_delete_filter(stmt)
        stmt = self._apply_filters(stmt, query)
        # 分页
        stmt = stmt.order_by(ArchiveModel.archived_at.desc()).offset(query.offset).limit(query.limit)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def find_for_update(self, query: ArchiveQuery, skip_locked: bool = False) -> list[StrategicArchive]:
        """按条件查询档案（带 FOR UPDATE 悲观锁）

        Args:
            query: 查询条件（ArchiveQuery 值对象）
            skip_locked: 跳过已被其他事务锁定的行（默认 False 阻塞等待）。
                         批量扫描场景（mark_stale_archives）传 True 避免并发实例互相阻塞；
                         冲突检测场景（set_validity_period）必须保持 False，
                         否则被锁定的同组行被跳过会导致有效期冲突漏报。

        Returns:
            符合条件的档案列表
        """
        stmt = select(ArchiveModel)
        stmt = self._apply_soft_delete_filter(stmt)
        stmt = self._apply_filters(stmt, query)
        stmt = stmt.order_by(ArchiveModel.archived_at.desc())
        stmt = stmt.with_for_update(skip_locked=skip_locked)
        stmt = stmt.offset(query.offset).limit(query.limit)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def mark_stale(self, archive_id: UUID, stale_since: str | None = None, stale_reason: str | None = None) -> bool:
        """条件标记档案为陈旧（并发安全）

        使用 UPDATE ... WHERE ... AND metadata->>'staleness' IS DISTINCT FROM 'stale'
        条件更新，确保仅当档案尚未标记时才写入。并发环境下被其他实例抢先标记时
        返回 False，避免重复事件。

        Args:
            archive_id: 档案 ID
            stale_since: 标记时间（ISO 8601 字符串，None 时由实现自行生成）
            stale_reason: 陈旧原因（"expired"/"archived_too_long"，None 时不写入）

        Returns:
            标记成功返回 True，已被其他实例抢先标记返回 False
        """
        from datetime import UTC, datetime

        from sqlalchemy import text

        if stale_since is None:
            stale_since = datetime.now(UTC).isoformat()
        if stale_reason is None:
            stale_reason = "stale"
        new_meta = json.dumps({"staleness": "stale", "stale_reason": stale_reason, "stale_since": stale_since})
        # raw UPDATE 精确控制 SQL 语义，避免 ORM 的 jsonb_set 类型转换问题
        # COALESCE(metadata, '{}'::jsonb) || CAST(:new_meta AS jsonb) 合并保留已有 key
        # WHERE metadata->>'staleness' != 'stale' 保证并发场景仅一个实例抢占成功
        result = await self._session.execute(
            text(
                "UPDATE strategic_archives "
                "SET metadata = COALESCE(metadata, '{}'::jsonb) || CAST(:new_meta AS jsonb) "
                "WHERE archive_id = CAST(:archive_id AS uuid) "
                "AND COALESCE(metadata ->> 'staleness', '') != 'stale'"
            ),
            {"new_meta": new_meta, "archive_id": str(archive_id)},
        )
        await self._session.flush()
        updated = getattr(result, "rowcount", 0)
        return int(updated or 0) == 1

    async def list_by_plan(self, plan_id: UUID) -> list[StrategicArchive]:
        """按规划 ID 列出档案

        Args:
            plan_id: 规划 ID

        Returns:
            该规划关联的所有档案
        """
        stmt = select(ArchiveModel).where(ArchiveModel.plan_id == plan_id)
        stmt = self._apply_soft_delete_filter(stmt)
        stmt = stmt.order_by(ArchiveModel.archived_at.desc())
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def list_by_archive_type(self, archive_type: ArchiveType) -> list[StrategicArchive]:
        """按档案类型列出

        Args:
            archive_type: 档案类型

        Returns:
            指定类型的档案列表
        """
        stmt = select(ArchiveModel).where(ArchiveModel.archive_type == archive_type.value)
        stmt = self._apply_soft_delete_filter(stmt)
        stmt = stmt.order_by(ArchiveModel.archived_at.desc())
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def count(self, query: ArchiveQuery | None = None) -> int:
        """统计满足条件的档案数量

        query 为 None 时统计全部档案数量（兼容父类 PostgreSQLAdapter.count() 无参签名）。

        Args:
            query: 查询条件（None 时使用全量统计）

        Returns:
            符合条件的档案数量
        """
        if query is None:
            query = ArchiveQuery()

        stmt = select(func.count()).select_from(ArchiveModel)
        stmt = self._apply_soft_delete_filter(stmt)
        stmt = self._apply_filters(stmt, query)

        result = await self._session.execute(stmt)
        return int(result.scalar() or 0)


__all__ = [
    "PostgreSQLArchiveRepository",
]
