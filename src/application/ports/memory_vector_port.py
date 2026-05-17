"""应用层记忆向量端口模块

继承 L3VectorPort，添加记忆检索语义

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.ports.l3_vector import L3VectorPort


@runtime_checkable
class MemoryVectorPort(L3VectorPort, Protocol):
    """记忆向量端口 — 继承L3VectorPort，添加记忆检索语义

    继承所有L3方法，额外提供：
    - 记忆向量自动索引（embedding + 存储一步完成）
    - 语义相似记忆检索
    - 按用户/类型过滤
    """

    async def index_memory(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
        owner_id: str,
    ) -> bool:
        """索引记忆内容（自动生成embedding并存储）

        Args:
            memory_id: 记忆 ID
            content: 记忆内容文本
            memory_type: 记忆类型
            owner_id: 所有者 ID

        Returns:
            是否索引成功
        """

    async def search_similar_memories(
        self,
        query: str,
        owner_id: str | None = None,
        memory_type: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """语义相似记忆检索

        Args:
            query: 查询文本
            owner_id: 过滤所有者 ID
            memory_type: 过滤记忆类型
            limit: 返回结果数量限制

        Returns:
            相似记忆列表
        """
