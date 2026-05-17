"""SISYS 领域层统一存储端口模块

定义存储系统的统一操作契约
对应 architecture.md §11.2.9 L0 驱动各层协同机制

设计原则：
- L0 是真相源，同步写入
- 其他层通过事件驱动异步更新
- 读取遵循缓存优先策略（L1 → L0）
- 领域层零外部依赖（仅用 abc + typing）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from src.domain.ports.storage_enums import StorageLayer, StorageTier

if TYPE_CHECKING:
    pass


@runtime_checkable
class UnifiedStoragePort(Protocol):
    """统一存储入口接口

    定义存储系统的统一操作契约
    对应 architecture.md §11.2.9 L0 驱动各层协同机制

    设计原则：
    - L0 是真相源，同步写入
    - 其他层通过事件驱动异步更新
    - 读取遵循缓存优先策略（L1 → L0）
    """

    async def save(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
        owner_id: str,
        name: str,
        tier: StorageTier = StorageTier.WARM,
    ) -> dict[StorageLayer, bool]:
        """保存记忆到多层存储

        对应 architecture.md §11.2.9 写入流程：
        1. L0 文件系统（同步，强一致）
        2. 发布 MemoryChanged 事件（事务发件箱）
        3. L1 缓存失效（异步）
        4. L2 元数据写入（异步）
        5. L3 向量（按需，内容>500 tokens）
        6. L5 图谱（按需，EntityExtractor）

        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID
            name: 记忆名称
            tier: 存储层级策略

        Returns:
            各层存储结果 {layer: success}
        """

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
        - prefer_cache=True: L1 → L2 → L0（缓存优先）
        - prefer_cache=False: L2 → L0（直接读取持久层）

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称
            prefer_cache: 是否优先从缓存读取

        Returns:
            记忆内容，不存在返回 None
        """

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

    async def exists(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> dict[StorageLayer, bool]:
        """检查记忆在各层的存在状态

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称

        Returns:
            各层存在状态 {layer: exists}
        """
