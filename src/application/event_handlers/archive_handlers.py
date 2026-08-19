"""应用层档案事件处理器模块

处理 ValidityPeriodSet / FactBecameStale 领域事件。
遵循 InMemoryEventListener.on_event() + register_handlers() 模式。

Story 3.12 扩展：
- ValidityPeriodSet 事件同步 L3/L5 payload/properties 中的 valid_from/valid_until（AC-2）
- FactBecameStale 事件触发 L3 payload 降权标记 is_stale/stale_reason/stale_since（AC-3）
- L3/L5 依赖可选注入（None 时降级记录日志）
- _run_async 辅助函数适配同步回调与异步端口方法
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any, Callable

from src.domain.events.archive_events import FactBecameStale, ValidityPeriodSet
from src.domain.events.base import DomainEvent
from src.domain.ports.event_listener import EventListener
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.l5_graph import L5GraphPort

logger = logging.getLogger(__name__)


class ArchiveValidityHandler:
    """档案有效期事件处理器

    处理 ValidityPeriodSet 和 FactBecameStale 事件。
    Story 3.12 起支持 L3/L5 有效期同步和降权标记。

    异步适配说明：
    EventListener.on_event 回调为同步签名，而 L3/L5 端口方法为 async。
    通过 _run_async() 辅助函数适配三种事件循环场景：
    - 无运行循环：asyncio.run(coro) 创建并关闭新循环
    - 有运行循环：get_running_loop().create_task(coro) fire-and-forget
    """

    L3_COLLECTION = "strategic_archive"

    def __init__(
        self,
        event_listener: EventListener,
        l3_vector: L3VectorPort | None = None,
        l5_graph: L5GraphPort | None = None,
    ) -> None:
        """初始化档案有效期事件处理器

        Args:
            event_listener: 事件监听器端口
            l3_vector: L3 向量存储端口（可选，None 时降级记录日志）
            l5_graph: L5 图存储端口（可选，None 时降级记录日志）
        """
        self._event_listener = event_listener
        self._l3_vector = l3_vector
        self._l5_graph = l5_graph

    @staticmethod
    def _run_async(coro: Coroutine[Any, Any, Any]) -> Any:
        """在同步上下文中运行异步协程

        适配三种事件循环场景：
        - 无运行循环（如测试函数直接调用 dispatch）：asyncio.run(coro) 创建并关闭新循环
        - 有运行循环（如 InMemoryEventBus.publish() 在 async 上下文调用 dispatch）：
          get_running_loop().create_task(coro) 调度到当前循环（fire-and-forget）

        注意：fire-and-forget 语义下协程可能在返回时尚未执行完毕。
        协程内部 try/except 确保异常不会传播到调用方。

        Args:
            coro: 待执行的异步协程

        Returns:
            asyncio.run 路径下返回协程结果；create_task 路径下返回 None
        """
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            # 无运行循环：使用 asyncio.run() 创建并关闭新循环
            return asyncio.run(coro)

        # 有运行循环：create_task 调度（fire-and-forget，异常由 task 内部消化）
        task = running_loop.create_task(coro)

        # 为未处理的 task 异常注册回调，记录日志避免 "Task exception was never retrieved" 警告
        def _log_task_exception(task: asyncio.Task[Any]) -> None:
            if task.cancelled():
                logger.warning("异步任务被取消: %s", coro)
                return
            exc = task.exception()
            if exc is not None:
                logger.warning("异步任务执行失败: %s", exc, exc_info=exc)

        task.add_done_callback(_log_task_exception)
        return None

    def register_handlers(self) -> None:
        """注册事件处理器到事件监听器

        注册 ValidityPeriodSet 和 FactBecameStale 事件的处理回调。
        """
        self._event_listener.on_event("ValidityPeriodSet", self._wrap_handler("validity_set"))
        self._event_listener.on_event("FactBecameStale", self._wrap_handler("fact_stale"))

    def _wrap_handler(self, handler_type: str) -> Callable[[DomainEvent], None]:
        """包装异步 handler 为同步回调

        Args:
            handler_type: 处理器类型标识

        Returns:
            同步回调闭包
        """
        del handler_type  # 预留：便于区分不同类型处理器

        def _handle(event: DomainEvent) -> None:
            try:
                if isinstance(event, ValidityPeriodSet):
                    self._handle_validity_period_set(event)
                elif isinstance(event, FactBecameStale):
                    self._handle_fact_became_stale(event)
                else:
                    logger.warning("Unknown event type received: %s", type(event).__name__)
            except BaseException:
                logger.exception("Error handling event %s", event.event_type)

        return _handle

    # ===================================================================
    # AC-2: ValidityPeriodSet → L3/L5 同步
    # ===================================================================

    def _handle_validity_period_set(self, event: ValidityPeriodSet) -> None:
        """处理 ValidityPeriodSet 事件

        记录有效期变更日志，并同步 L3/L5 中的 valid_from/valid_until。

        Args:
            event: ValidityPeriodSet 事件
        """
        logger.info(
            "Validity period set for archive %s: [%s, %s]",
            event.archive_id,
            event.valid_from.isoformat() if event.valid_from else "None",
            event.valid_until.isoformat() if event.valid_until else "None",
        )
        # L3/L5 同步独立执行，一个失败不影响另一个
        self._sync_l3_validity(event)
        self._sync_l5_validity(event)

    def _sync_l3_validity(self, event: ValidityPeriodSet) -> None:
        """同步有效期到 L3 向量存储 payload

        采用"读-改-写"三步：get_point 读取现有 payload → 合并 valid_from/valid_until → upsert_points。
        避免对未知现有 payload 的全量覆盖。

        Args:
            event: ValidityPeriodSet 事件
        """
        if self._l3_vector is None:
            logger.warning("L3 vector storage not available, skip valid_from/valid_until sync")
            return

        point_id = f"strategic_archive:{event.archive_id}"
        try:
            coro = self._update_l3_validity(point_id, event)
            self._run_async(coro)
        except Exception as e:
            logger.warning("L3 validity sync failed for archive %s: %s", event.archive_id, e)

    async def _update_l3_validity(self, point_id: str, event: ValidityPeriodSet) -> None:
        """异步执行 L3 payload 读-改-写更新

        Args:
            point_id: 向量点 ID
            event: ValidityPeriodSet 事件
        """
        if self._l3_vector is None:
            return
        existing = await self._l3_vector.get_point(
            collection=self.L3_COLLECTION,
            point_id=point_id,
        )
        if existing is None:
            logger.warning("L3 point %s not found, skip validity sync", point_id)
            return

        payload = dict(existing.get("payload", {}))
        new_valid_from = event.valid_from.isoformat() if event.valid_from else None
        new_valid_until = event.valid_until.isoformat() if event.valid_until else None

        # 幂等检查：已同步则跳过 upsert（避免 Outbox 重试导致重复 I/O）
        if payload.get("valid_from") == new_valid_from and payload.get("valid_until") == new_valid_until:
            logger.info("L3 point %s validity already synced, skip", point_id)
            return

        payload["valid_from"] = new_valid_from
        payload["valid_until"] = new_valid_until

        vector = existing.get("vector")
        if vector is None:
            logger.warning("L3 point %s has no vector, skip validity sync", point_id)
            return

        await self._l3_vector.upsert_points(
            collection=self.L3_COLLECTION,
            points=[
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": payload,
                }
            ],
        )

    def _sync_l5_validity(self, event: ValidityPeriodSet) -> None:
        """同步有效期到 L5 图存储 properties

        使用 execute_write_query() 的 Cypher SET 子句局部更新，天然不覆盖其他属性。

        Args:
            event: ValidityPeriodSet 事件
        """
        if self._l5_graph is None:
            logger.warning("L5 graph storage not available, skip valid_from/valid_until sync")
            return

        try:
            coro = self._update_l5_validity(event)
            self._run_async(coro)
        except Exception as e:
            logger.warning("L5 validity sync failed for archive %s: %s", event.archive_id, e)

    async def _update_l5_validity(self, event: ValidityPeriodSet) -> None:
        """异步执行 L5 properties SET 更新

        Args:
            event: ValidityPeriodSet 事件
        """
        if self._l5_graph is None:
            return
        await self._l5_graph.execute_write_query(
            cypher=("MATCH (n {memory_id: $memory_id}) SET n.valid_from = $valid_from, n.valid_until = $valid_until"),
            params={
                "memory_id": str(event.archive_id),
                "valid_from": event.valid_from.isoformat() if event.valid_from else None,
                "valid_until": event.valid_until.isoformat() if event.valid_until else None,
            },
        )

    # ===================================================================
    # AC-3: FactBecameStale → L3 降权标记
    # ===================================================================

    def _handle_fact_became_stale(self, event: FactBecameStale) -> None:
        """处理 FactBecameStale 事件

        记录陈旧标记日志，并触发 L3 降权标记（is_stale/stale_reason/stale_since）。

        Args:
            event: FactBecameStale 事件
        """
        logger.info(
            "Fact became stale for archive %s: reason=%s, stale_since=%s",
            event.archive_id,
            event.stale_reason,
            event.stale_since.isoformat(),
        )
        self._mark_stale_on_l3(event)

    def _mark_stale_on_l3(self, event: FactBecameStale) -> None:
        """更新 L3 payload 标记陈旧状态（幂等）

        更新目标为 strategic_archive collection（payload 含 archive_id 字段，供降权服务兜底查询）。
        L3 payload 使用 is_stale: bool（True/False），与 L2 metadata 的 staleness: str（"stale"）区分。

        幂等实现细节：
        - is_stale 已为 True 且 stale_reason 相同 → 跳过更新
        - is_stale 已为 True 但 stale_reason 不同 → 允许更新 stale_reason（保证最新原因）
        - get_point 返回 None（点不存在）→ 记录 WARNING 并跳过
        - is_stale 为 False 或不存在 → 读-改-写三步合并标记

        Args:
            event: FactBecameStale 事件
        """
        if self._l3_vector is None:
            logger.warning("L3 vector storage not available, skip stale marking")
            return

        point_id = f"strategic_archive:{event.archive_id}"
        try:
            coro = self._update_l3_stale(point_id, event)
            self._run_async(coro)
        except Exception as e:
            logger.warning("L3 stale marking failed for archive %s: %s", event.archive_id, e)

    async def _update_l3_stale(self, point_id: str, event: FactBecameStale) -> None:
        """异步执行 L3 payload 陈旧标记更新（读-改-写三步）

        Args:
            point_id: 向量点 ID
            event: FactBecameStale 事件
        """
        if self._l3_vector is None:
            return
        existing = await self._l3_vector.get_point(
            collection=self.L3_COLLECTION,
            point_id=point_id,
        )
        if existing is None:
            logger.warning("L3 point %s not found, skip stale marking", point_id)
            return

        payload = dict(existing.get("payload", {}))
        # 幂等检查：已标记且原因相同则跳过
        if payload.get("is_stale") is True:
            if payload.get("stale_reason") == event.stale_reason:
                logger.info("L3 point %s already marked stale, skip", point_id)
                return

        payload["is_stale"] = True
        payload["stale_reason"] = event.stale_reason
        payload["stale_since"] = event.stale_since.isoformat()

        vector = existing.get("vector")
        if vector is None:
            logger.warning("L3 point %s has no vector, skip stale marking", point_id)
            return

        await self._l3_vector.upsert_points(
            collection=self.L3_COLLECTION,
            points=[
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": payload,
                }
            ],
        )


__all__ = [
    "ArchiveValidityHandler",
]
