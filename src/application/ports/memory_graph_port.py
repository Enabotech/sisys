"""应用层记忆图端口模块

继承 L5GraphPort，添加记忆关系语义

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.ports.l5_graph import L5GraphPort


@runtime_checkable
class MemoryGraphPort(L5GraphPort, Protocol):
    """记忆图端口 — 继承L5GraphPort，添加记忆关系语义

    继承所有L5方法，额外提供：
    - 记忆关系自动提取（内容→实体→关系）
    - 知识图谱查询
    """

    async def index_memory_relations(
        self,
        memory_id: str,
        content: str,
    ) -> int:
        """提取并索引记忆中的实体关系

        Args:
            memory_id: 记忆 ID
            content: 记忆内容

        Returns:
            创建的关系数量
        """

    async def get_knowledge_graph(
        self,
        memory_id: str,
        depth: int = 2,
    ) -> dict:
        """获取记忆的知识图谱子图

        Args:
            memory_id: 记忆 ID
            depth: 遍历深度（默认 2）

        Returns:
            子图数据（entities + connections）
        """
