"""应用层词典编排服务模块

编排 CRUD → 热更新 → 事件发布完整流程。
遵循六边形架构：依赖领域层端口，不依赖基础设施层具体实现。
设计约束：
- 注入 DomainDictionaryPort（持久化）+ DictionaryConsumerPort（热更新消费端）+ EventPublisher
- 不注入 EntityExtractionPort（接口隔离原则）
- 事件发布失败仅记录日志，不阻止主流程返回
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.domain.events.dictionary_events import DictionaryUpdated
from src.domain.exceptions import DictionaryNotFoundError

if TYPE_CHECKING:
    from src.domain.ports.domain_dictionary import (
        DictionaryConsumerPort,
        DictionaryEntry,
        DictionaryQuery,
        DictionarySnapshot,
        DomainDictionaryPort,
    )
    from src.domain.ports.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


class DomainDictionaryService:
    """领域词典编排服务

    组合 DomainDictionaryPort（持久化）+ DictionaryConsumerPort（热更新消费端）+ EventPublisher。
    提供 CRUD、热更新、快照/回滚、事件发布等完整词典管理能力。

    Attributes:
        dictionary_repo: 词典持久化仓储
        dictionary_consumer: 词典消费端（热更新）
        event_publisher: 事件发布器
    """

    def __init__(
        self,
        dictionary_repo: DomainDictionaryPort,
        dictionary_consumer: DictionaryConsumerPort,
        event_publisher: EventPublisher,
    ) -> None:
        """初始化词典编排服务

        Args:
            dictionary_repo: 词典持久化仓储
            dictionary_consumer: 词典消费端（热更新）
            event_publisher: 事件发布器
        """
        self._dictionary_repo = dictionary_repo
        self._dictionary_consumer = dictionary_consumer
        self._event_publisher = event_publisher

    async def list_entries(self, query: DictionaryQuery) -> list[DictionaryEntry]:
        """按查询条件列出词条

        Args:
            query: 查询条件

        Returns:
            符合条件的词条列表
        """
        return await self._dictionary_repo.list_entries(query)

    async def get_entry(self, term: str) -> DictionaryEntry | None:
        """按词条名查询

        Args:
            term: 词条文本

        Returns:
            DictionaryEntry 或 None
        """
        return await self._dictionary_repo.get_entry(term)

    async def add_entry(
        self,
        entry: DictionaryEntry,
        trigger: str = "api",
    ) -> DictionaryEntry:
        """添加词条

        Args:
            entry: 待添加的词条
            trigger: 触发源

        Returns:
            已保存的词条
        """
        saved = await self._dictionary_repo.add_entry(entry)
        await self._publish_event(term=entry.term, action="add", trigger=trigger)
        return saved

    async def update_entry(
        self,
        term: str,
        entry: DictionaryEntry,
        trigger: str = "api",
    ) -> DictionaryEntry:
        """修改词条

        Args:
            term: 要修改的词条名
            entry: 新的词条数据
            trigger: 触发源

        Returns:
            更新后的词条
        """
        updated = await self._dictionary_repo.update_entry(term, entry)
        await self._publish_event(term=term, action="update", trigger=trigger)
        return updated

    async def delete_entry(self, term: str, trigger: str = "api") -> None:
        """删除词条

        Args:
            term: 要删除的词条名
            trigger: 触发源

        Raises:
            DictionaryNotFoundError: 词条不存在
        """
        existing = await self._dictionary_repo.get_entry(term)
        if existing is None:
            raise DictionaryNotFoundError(term=term)
        await self._dictionary_repo.delete_entry(term)
        await self._publish_event(term=term, action="delete", trigger=trigger)

    async def refresh_dictionary(self) -> None:
        """触发热更新

        读取活动词典，调用 DictionaryConsumerPort.reload_dictionary() 注入运行时。
        """
        active = await self._dictionary_repo.get_active_dictionary()
        self._dictionary_consumer.reload_dictionary(active)

    async def create_snapshot(self, created_by: str) -> DictionarySnapshot:
        """创建词典快照

        Args:
            created_by: 创建者

        Returns:
            创建的词典快照
        """
        return await self._dictionary_repo.create_snapshot(created_by)

    async def rollback(self, version: int, trigger: str = "api") -> None:
        """回滚至指定版本

        Args:
            version: 目标词典版本号
            trigger: 触发源

        Raises:
            DictionaryNotFoundError: 目标版本不存在
        """
        await self._dictionary_repo.rollback(version)
        # 回滚后自动刷新
        await self.refresh_dictionary()
        await self._publish_event(term="", action="rollback", trigger=trigger)

    async def list_snapshots(self) -> list[DictionarySnapshot]:
        """列出所有快照

        Returns:
            快照列表
        """
        return await self._dictionary_repo.list_snapshots()

    async def _publish_event(
        self,
        term: str,
        action: str,
        trigger: str = "api",
    ) -> None:
        """发布 DictionaryUpdated 事件

        事件发布失败仅记录日志，不阻止主流程返回。

        Args:
            term: 变更词条
            action: 操作类型
            trigger: 触发源
        """
        try:
            event = DictionaryUpdated(term=term, action=action, trigger=trigger)
            await self._event_publisher.publish(event)
        except Exception:
            logger.warning("词典事件发布失败: term=%s, action=%s", term, action)
