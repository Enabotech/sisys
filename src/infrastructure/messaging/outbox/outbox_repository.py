"""基础设施层 PostgreSQL 发件箱仓储模块

实现领域层 OutboxRepository 接口，使用 SQLAlchemy 持久化发件箱实体
提供公开方法（实现接口）和内部方法（供 AsyncOutboxPoller 使用）

Session 通过 ContextVar 由 middleware 或 test fixture 提供，
无需构造器注入 session 参数。

Story 4.7 fallback 独立 session 修复（defer 债清偿——AC-4）：
save 优先 get_session()（HTTP 路径复用请求 session，保持事务性 outbox
原子性——业务状态与事件发布同事务 commit/rollback）；无请求 session 时
（后台/CLI 路径——现状事件 100% 静默丢失的根因）经注入的 session_factory
走 session_context 独立写入（outbox_processor.py:146-155 先例同款）。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import String, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.events.base import DomainEvent
from src.domain.exceptions import InvalidStateTransitionError
from src.domain.ports.outbox import OutboxRepository
from src.infrastructure.messaging.adapters.sqlalchemy_event_outbox_adapter import (
    SQLAlchemyEventOutboxAdapter,
)
from src.infrastructure.storage.postgresql.models import OutboxModel
from src.infrastructure.storage.postgresql.session_context import get_session, session_context

logger = logging.getLogger(__name__)

# 错误消息列宽上界（与 OutboxModel.error_message 的 VARCHAR(1000) 对齐；
# isinstance 收窄使 mypy 可达 .length，or 兜底覆盖无长度声明的方言形态）
_ERROR_MESSAGE_COLUMN_TYPE = OutboxModel.__table__.columns["error_message"].type
if not isinstance(_ERROR_MESSAGE_COLUMN_TYPE, String):
    raise AssertionError("OutboxModel.error_message 列类型须为 String（列定义漂移）")
_ERROR_MESSAGE_MAX_LENGTH: int = _ERROR_MESSAGE_COLUMN_TYPE.length or 1000


class PostgreSQLOutboxRepository(OutboxRepository):
    """PostgreSQL 发件箱仓储实现

    所有公开方法为 async（实现 OutboxRepository Protocol）
    内部方法（_ 前缀）直接操作 OutboxModel，仅 Poller 使用
    """

    def __init__(self, session_factory: Any = None) -> None:
        """初始化实例级别 Lock 与 fallback 会话工厂.

        Args:
            session_factory: 独立会话工厂（后台/CLI 路径 fallback 用——无请求
                session 时经 session_context 独立写入；None 时无 fallback，
                保持 4.4 既有行为直接抛 RuntimeError。async_sessionmaker 形态
                ——session_context 类型契约；outbox_processor 先例同款）
        """
        self._lock = asyncio.Lock()
        self._session_factory = session_factory

    @property
    def _session(self) -> AsyncSession:
        return get_session()

    # ========== 公开方法（实现领域层接口，async） ==========

    async def save(self, event: DomainEvent) -> None:
        """保存事件至发件箱（HTTP 路径同事务；后台路径 fallback 独立写入）.

        Raises:
            RuntimeError: 无请求 session 且未注入 session_factory（无 fallback
                能力——保持既有行为显式失败而非静默丢失）
        """
        model = SQLAlchemyEventOutboxAdapter.from_domain_event(event)
        try:
            session = get_session()
        except RuntimeError:
            # 后台/CLI 路径（无请求 session）——经注入工厂走独立 session 写入
            if self._session_factory is None:
                raise
            await self._save_via_independent_session(model)
            return
        session.add(model)
        await session.flush()

    async def _save_via_independent_session(self, model: OutboxModel) -> None:
        """经 session_context 独立会话写入（正常路径 commit——outbox_processor 先例同款）."""
        event_id = str(model.event_id)  # session 关闭后 detached——提前捕获
        async with session_context(self._session_factory):
            session = get_session()
            session.add(model)
            await session.flush()
        logger.info("Outbox 事件经独立会话落库（后台路径 fallback）: event_id=%s", event_id)

    async def get_unpublished(self, limit: int) -> list[DomainEvent]:
        """获取未发布的事件列表（FIFO 排序，逐条毒消息隔离）。

        单条畸形 payload（反序列化失败）标记 failed 后跳过——防止毒事件卡在
        FIFO 队头阻塞其后全部合法事件（对齐消费侧 redis_subscriber 逐消息
        隔离语义）。SELECT 以 retry_count < max_retries 过滤重试耗尽行——
        超限行不退出选择集会在累积至 batch_size 后恒返回空批，合法事件
        静默停发（队头阻塞隐蔽复发形态）。
        """
        result = await self._session.execute(
            select(OutboxModel)
            .where(
                OutboxModel.status.in_(("pending", "failed")),
                OutboxModel.retry_count < OutboxModel.max_retries,
            )
            .order_by(OutboxModel.created_at.asc())
            .limit(limit)
        )
        models = list(result.scalars().all())
        events: list[DomainEvent] = []
        for model in models:
            try:
                events.append(SQLAlchemyEventOutboxAdapter.to_domain_event(model))
            except Exception as exc:
                if model.retry_count < model.max_retries:
                    logger.error(
                        "Outbox 事件反序列化失败（毒消息隔离，标记失败）: event_id=%s error=%s",
                        model.event_id,
                        exc,
                    )
                    await self.mark_failed(model.event_id, f"deserialization failed: {exc}")
                else:
                    # 防御性保留（真实流程经 SELECT 过滤后不可达；防御行属性与
                    # SELECT 物化值不一致的极端形态）：超限毒行降级单行 warning
                    # 不写库（毒 payload 静态垃圾永不恢复，重试标记纯写放大）
                    logger.warning(
                        "Outbox 毒消息已超重试上限（跳过标记）: event_id=%s retry_count=%d",
                        model.event_id,
                        model.retry_count,
                    )
        return events

    async def mark_published(self, event_id: UUID) -> None:
        """标记事件已发布

        Raises:
            InvalidStateTransitionError: 当当前状态不是 pending 时
        """
        result = await self._session.execute(select(OutboxModel).where(OutboxModel.event_id == event_id))
        model = result.scalar_one_or_none()
        if model:
            if model.status != "pending":
                raise InvalidStateTransitionError(model.status, "published")
            model.status = "published"
            model.published_at = datetime.now(UTC)
            await self._session.flush()

    async def mark_pending(self, event_id: UUID) -> None:
        """将失败事件恢复为待发布状态。"""
        result = await self._session.execute(select(OutboxModel).where(OutboxModel.event_id == event_id))
        model = result.scalar_one_or_none()
        if model:
            if model.status != "failed":
                raise InvalidStateTransitionError(model.status, "pending")
            if model.retry_count >= model.max_retries:
                raise InvalidStateTransitionError(model.status, "pending", f"Max retries ({model.max_retries}) exceeded")
            model.status = "pending"
            model.error_message = None
            await self._session.flush()

    async def mark_failed(self, event_id: UUID, error: str) -> None:
        """标记事件发布失败（错误消息按列宽截断）

        error_message 列为 VARCHAR(1000)，PG 对超长值抛错不截断——未截断的
        超长错误串（如内嵌任意长 payload repr 的反序列化消息）会使整周期
        事务失败，毒标记随回滚丢弃形成永久活锁。

        Raises:
            InvalidStateTransitionError: 当当前状态不是 pending 或 failed 时
        """
        result = await self._session.execute(select(OutboxModel).where(OutboxModel.event_id == event_id))
        model = result.scalar_one_or_none()
        if model:
            if model.status not in ("pending", "failed"):
                raise InvalidStateTransitionError(model.status, "failed")
            model.status = "failed"
            model.retry_count += 1
            model.error_message = error[:_ERROR_MESSAGE_MAX_LENGTH]
            await self._session.flush()

    async def count_by_status(self) -> dict[str, int]:
        """按状态分组统计事件数（运维巡检面——D11-a 清偿）。

        pending 滞留（发布链路健康度）、failed 存量、archived 终态与
        published 待清理量一查可见——SQL 巡检的正式替代，供 CLI/metrics 消费。
        """
        result = await self._session.execute(select(OutboxModel.status, func.count()).group_by(OutboxModel.status))
        return {status: count for status, count in result.all()}

    async def cleanup_old_published_records(self, older_than_days: int = 30) -> int:
        """清理超过保留期的已发布记录

        Args:
            older_than_days: 保留天数（默认 30 天）

        Returns:
            清理的记录数量
        """
        cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
        result = await self._session.execute(
            select(OutboxModel).where(
                OutboxModel.status == "published",
                OutboxModel.published_at < cutoff,
            )
        )
        models = list(result.scalars().all())
        for model in models:
            await self._session.delete(model)
        await self._session.flush()
        return len(models)

    # ========== 内部方法（仅 Poller 使用） ==========

    async def _get_unpublished_entities(self, limit: int) -> list[OutboxModel]:
        """内部方法: 获取未发布的 OutboxModel 列表（FIFO 排序）

        Args:
            limit: 最大返回数量

        Returns:
            未发布的 OutboxModel 列表
        """
        async with self._lock:
            result = await self._session.execute(
                select(OutboxModel).where(OutboxModel.status == "pending").order_by(OutboxModel.created_at.asc()).limit(limit)
            )
            return list(result.scalars().all())

    async def _mark_published_entity(self, model: OutboxModel) -> None:
        """内部方法: 标记 OutboxModel 为 published

        Args:
            model: 要标记的 OutboxModel 实例

        Raises:
            InvalidStateTransitionError: 当当前状态不是 pending 时
        """
        async with self._lock:
            if model.status != "pending":
                raise InvalidStateTransitionError(model.status, "published")
            model.status = "published"
            model.published_at = datetime.now(UTC)

    async def _mark_failed_entity(self, model: OutboxModel, error: str) -> None:
        """内部方法: 标记 OutboxModel 为 failed，递增 retry_count（错误消息按列宽截断，与公开 mark_failed 对称）

        Args:
            model: 要标记的 OutboxModel 实例
            error: 错误信息

        Raises:
            InvalidStateTransitionError: 当当前状态不是 pending 或 failed 时
        """
        async with self._lock:
            if model.status not in ("pending", "failed"):
                raise InvalidStateTransitionError(model.status, "failed")
            model.status = "failed"
            model.retry_count += 1
            model.error_message = error[:_ERROR_MESSAGE_MAX_LENGTH]
