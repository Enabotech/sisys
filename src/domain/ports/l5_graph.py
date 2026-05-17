"""领域层 L5 图存储端口模块

对应 architecture.md §11.1：
- 知识图谱、实体关系
- Cypher、图遍历、Parent-Child 索引

设计说明：
- 本接口是高级语义层，内部委托给 GraphStorage（低级 Cypher 执行）
- 使用 memory_id 作为实体主键（id 属性）
- 保留 execute_query/execute_write_query 入口以支持灵活查询

设计原则：
- 领域层零外部依赖（仅用 abc + typing）
- 异步优先（async def）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class L5GraphPort(Protocol):
    """L5 Neo4j 图存储接口（高级实体语义）

    对应 architecture.md §11.1：
    - 知识图谱、实体关系
    - Cypher、图遍历、Parent-Child 索引
    """

    async def create_entity(
        self,
        memory_id: str,
        entity_type: str,
        properties: dict[str, Any],
    ) -> bool:
        """创建实体节点（MERGE 语义）

        Args:
            memory_id: 关联的记忆 ID（主键）
            entity_type: 实体类型（如 'project', 'reference'）
            properties: 实体属性

        Returns:
            是否成功（MERGE 语义：已存在返回 True）
        """

    async def get_entity(
        self,
        memory_id: str,
    ) -> dict | None:
        """获取实体

        Args:
            memory_id: 实体主键

        Returns:
            实体数据 {id, type, properties}，不存在返回 None
        """

    async def delete_entity(
        self,
        memory_id: str,
    ) -> bool:
        """删除实体及关联边

        Args:
            memory_id: 实体主键

        Returns:
            是否成功
        """

    async def create_relationship(
        self,
        source_memory_id: str,
        target_memory_id: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """创建关系边（MERGE 语义）

        Args:
            source_memory_id: 源实体 ID
            target_memory_id: 目标实体 ID
            relationship_type: 关系类型（如 'DEPENDS_ON'）
            properties: 关系属性

        Returns:
            是否成功
        """

    async def delete_relationship(
        self,
        source_memory_id: str,
        target_memory_id: str,
        relationship_type: str,
    ) -> bool:
        """删除关系边

        Args:
            source_memory_id: 源实体 ID
            target_memory_id: 目标实体 ID
            relationship_type: 关系类型

        Returns:
            是否成功
        """

    async def find_related(
        self,
        memory_id: str,
        max_depth: int = 2,
        relationship_type: str | None = None,
    ) -> list[dict]:
        """查找关联实体（多跳遍历）

        Args:
            memory_id: 起始实体 ID
            max_depth: 最大遍历深度（默认 2）
            relationship_type: 过滤关系类型，None 表示所有

        Returns:
            关联实体列表 [{memory_id, type, properties, path}, ...]
        """

    async def execute_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行只读 Cypher 查询

        Args:
            cypher: Cypher 查询语句
            params: 查询参数字典

        Returns:
            查询结果列表（字典列表）
        """

    async def execute_write_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行写入 Cypher 查询

        Args:
            cypher: Cypher 查询语句
            params: 查询参数字典

        Returns:
            查询结果列表（字典列表）
        """

    async def get_neighbors(
        self,
        memory_id: str,
        max_depth: int = 1,
        edge_type: str | None = None,
    ) -> list[dict]:
        """获取邻居节点（直接关联的实体）

        Args:
            memory_id: 实体主键
            max_depth: 最大深度（默认 1，只看直接邻居）
            edge_type: 过滤边类型，None 表示所有

        Returns:
            邻居节点列表 [{memory_id, type, properties}, ...]
        """
