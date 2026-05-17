"""SISYS 应用层统一存储网关模块

提供 L0-L5 六层存储的统一入口，根据存储策略自动编排各层存储
对应 architecture.md §11.2.9 L0 驱动各层协同机制

六边形约束遵守：
- 本类是应用层服务
- 依赖 Domain Port 接口，不直接依赖 Infrastructure
- 工厂由外部注入，遵循依赖倒置原则

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from src.domain.ports.storage_enums import StorageLayer, StorageTier
from src.domain.ports.unified_storage import UnifiedStoragePort

if TYPE_CHECKING:
    # Rule 4: 应用层端口（继承 Rule 1 基础端口）
    from src.application.ports.document_storage_port import DocumentStoragePort
    from src.application.ports.memory_cache_port import MemoryCachePort
    from src.application.ports.memory_graph_port import MemoryGraphPort
    from src.application.ports.memory_vector_port import MemoryVectorPort
    from src.domain.entities.memory_metadata import MemoryMetadata
    from src.domain.ports.l0_storage import L0StoragePort
    from src.domain.ports.memory_repository import (
        L2ChangeHistoryRepositoryPort,
        L2GroupMemberRepositoryPort,
        L2MetadataRepositoryPort,
    )


class UnifiedStorageGateway(UnifiedStoragePort):
    """统一存储网关

    职责：
    - 提供 L0-L5 六层存储的统一入口
    - 根据存储策略自动决定数据 placement
    - 协调各层存储的读写操作
    - 处理层间数据流动

    读取策略（来自 architecture.md §11.2.9）：
    - prefer_cache=True: L1 → L2 (RBAC校验) → L0（缓存优先）
    - prefer_cache=False: L2 (RBAC校验) → L0（直接读取持久层）

    Attributes:
        _l0: L0 文件系统存储
        _memory_cache: 记忆缓存端口
        _l2_meta: L2 元数据仓储
        _l2_hist: L2 历史仓储
        _l3: L3 向量存储
        _l4: L4 对象存储
        _l5: L5 图存储
        _l2_group_member: L2 群组成员关系仓储
        _event_publisher: 事件发布器
        _policy: 存储策略服务（延迟初始化）
    """

    def __init__(
        self,
        l0_storage: L0StoragePort,
        memory_cache: MemoryCachePort,
        l2_metadata: L2MetadataRepositoryPort,
        l2_history: L2ChangeHistoryRepositoryPort,
        l2_group_member: L2GroupMemberRepositoryPort | None = None,
        l3_vector: MemoryVectorPort | None = None,
        l4_object: DocumentStoragePort | None = None,
        l5_graph: MemoryGraphPort | None = None,
        event_publisher=None,
    ) -> None:
        """初始化统一存储网关

        Args:
            l0_storage: L0 文件系统存储
            memory_cache: 记忆缓存端口
            l2_metadata: L2 元数据仓储（现有 L2MetadataRepositoryPort）
            l2_history: L2 历史仓储（现有 L2ChangeHistoryRepositoryPort）
            l3_vector: L3 向量存储
            l4_object: L4 对象存储
            l5_graph: L5 图存储
            l2_group_member: L2 群组成员关系仓储（可选，用于 group 记忆 RBAC 校验）
            event_publisher: 事件发布器（Outbox 模式需要）
        """
        self._l0 = l0_storage
        self._memory_cache = memory_cache
        self._l2_meta = l2_metadata
        self._l2_hist = l2_history
        self._l3 = l3_vector
        self._l4 = l4_object
        self._l5 = l5_graph
        self._l2_group_member = l2_group_member
        self._event_publisher = event_publisher

        self._policy = None  # 延迟初始化

    @property
    def _storage_policy(self):
        """延迟加载 StoragePolicyService"""
        if self._policy is None:
            from src.domain.services.storage_tier_strategy import StoragePolicyService

            self._policy = StoragePolicyService()
        return self._policy

    async def save(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
        owner_id: str,
        name: str,
        tier: StorageTier | None = None,
    ) -> dict[StorageLayer, bool]:
        """保存记忆到多层存储

        对应 architecture.md §11.2.9 写入流程：
        1. L0 文件系统（同步，强一致）- 真相源
        2. 发布 MemoryChanged 事件到 Outbox（事务发件箱）
        3. 各层更新由 MemoryChangedListener 异步执行

        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称
            tier: 存储层级策略

        Returns:
            各层存储结果（L0写入结果 + Outbox发布状态）
        """
        results: dict[StorageLayer, bool] = {}

        effective_tier = tier
        if effective_tier is None:
            decision = self._storage_policy.decide_tier(
                access_frequency=0,
                content_size=len(content.encode("utf-8")),
                is_checkpoint=False,
            )
            effective_tier = decision.tier

        l0_success = await self._l0.write(memory_id, memory_type, content)
        results[StorageLayer.L0_FILE] = l0_success

        if l0_success:
            await self._memory_cache.set_memory(memory_type, owner_id, name, content)
            results[StorageLayer.L1_CACHE] = True

        if hasattr(self, "_event_publisher") and self._event_publisher is not None:
            from src.domain.events.memory_events import MemoryChanged

            event = MemoryChanged(
                memory_id=memory_id,
                user_id=owner_id,
                name=name,
                change_type="create",
                is_automatic=False,
                old_value=None,
                new_value={"memory_type": memory_type, "content": content[:100]},
            )
            self._event_publisher.publish(event)

        return results

    async def read(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str,
        name: str,
        prefer_cache: bool = True,
    ) -> str | None:
        """读取记忆

        对应 architecture.md §11.2.9 检索流程：
        1. RBAC 校验（L2 元数据，必须）
        2. L1 缓存优先（prefer_cache=True）
        3. L0 回源 + 缓存回填
        """
        metadata = await self._l2_meta.get_by_id(UUID(memory_id))
        if metadata is None:
            return None

        if not await self._check_read_permission(metadata, owner_id, memory_type):
            return None

        if prefer_cache:
            content = await self._memory_cache.get_memory(memory_type, owner_id, name)
            if content is not None:
                return content

        content = await self._l0.read(memory_id, memory_type)
        if content is not None and prefer_cache:
            await self._memory_cache.set_memory(memory_type, owner_id, name, content)

        return content

    async def _check_read_permission(
        self,
        metadata: MemoryMetadata,
        owner_id: str,
        memory_type: str,
    ) -> bool:
        """检查读取权限

        可见性由 group_id 区分（不是 type 字段）：
        - group_id == NULL/empty → private 记忆，仅 owner 可读
        - group_id != NULL/empty → group 记忆，owner 或 group 成员可读

        type 字段（user/feedback/project/reference）只是记忆分类，不是可见性
        """
        is_group_memory = metadata.group_id is not None and metadata.group_id != ""
        if is_group_memory:
            # Group 记忆：owner 或 group 成员可读
            if metadata.owner == owner_id:
                return True
            # 检查是否是 group 成员
            if self._l2_group_member is not None:
                return await self._l2_group_member.is_group_member(metadata.group_id, owner_id)
            return False
        else:
            # Private 记忆：仅 owner 可读
            return metadata.owner == owner_id

    async def delete(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> dict[StorageLayer, bool]:
        """删除记忆

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称

        Returns:
            各层删除结果
        """
        results: dict[StorageLayer, bool] = {}

        results[StorageLayer.L0_FILE] = await self._l0.delete(memory_id, memory_type)

        await self._memory_cache.delete_memory(memory_type, owner_id, name)
        results[StorageLayer.L1_CACHE] = True

        if hasattr(self, "_event_publisher") and self._event_publisher is not None:
            from src.domain.events.memory_events import MemoryChanged

            event = MemoryChanged(
                memory_id=memory_id,
                user_id=owner_id,
                name=name,
                change_type="delete",
                is_automatic=False,
                old_value={"memory_type": memory_type},
                new_value=None,
            )
            self._event_publisher.publish(event)

        return results

    async def exists(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> dict[StorageLayer, bool]:
        """检查记忆在各层的存在状态

        Returns:
            各层存在状态
        """
        metadata = await self._l2_meta.get_by_id(UUID(memory_id))
        if metadata is None or not await self._check_read_permission(metadata, owner_id, memory_type):
            return {StorageLayer.L0_FILE: False, StorageLayer.L1_CACHE: False}

        l0_exists = await self._l0.exists(memory_id, memory_type)
        l1_exists = await self._memory_cache.get_memory(memory_type, owner_id, name) is not None

        return {
            StorageLayer.L0_FILE: l0_exists,
            StorageLayer.L1_CACHE: l1_exists,
        }

    async def get_content(
        self,
        memory_id: str,
    ) -> str | None:
        """获取记忆内容（从 L0）

        直接从 L0 文件系统读取，不走缓存
        """
        content = await self._l0.read(memory_id, "private")
        if content is not None:
            return content
        return await self._l0.read(memory_id, "group")
