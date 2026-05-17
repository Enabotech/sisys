"""基础设施层 Neo4j 图管理模块

负责节点和关系的 CRUD 操作，支持 MERGE 语义

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import cast

from neo4j import AsyncDriver

from src.infrastructure.storage.neo4j.models import GraphNode, GraphRelationship


class Neo4jGraphManager:
    """Neo4j 图管理器

    实现 GraphManager 接口，提供节点和关系生命周期管理
    """

    def __init__(self, driver: AsyncDriver, database: str = "neo4j"):
        """初始化图管理器

        Args:
            driver: Neo4j 异步驱动实例
            database: 数据库名称
        """
        self._driver = driver
        self._database = database

    async def create_node(self, node: GraphNode) -> bool:
        """创建节点（MERGE 语义）

        如果节点已存在（通过 id 匹配），则更新属性（ON MATCH SET）并返回 False
        如果节点不存在，则创建节点（ON CREATE SET）并返回 True

        Args:
            node: 图节点对象

        Returns:
            创建成功返回 True，已存在返回 False
        """
        async with self._driver.session(database=self._database) as session:
            labels_str = ":".join(node.labels)
            cypher = f"""
            MERGE (n:{labels_str} {{id: $node_id}})
            ON CREATE SET n += $properties, n.created_at = $created_at
            ON MATCH SET n += $properties
            RETURN n, n.created_at, count {{ (n)-[]-() }} as rel_count
            """
            result = await session.run(
                cypher,
                node_id=node.id,
                properties=node.properties,
                created_at=node.created_at.isoformat(),
            )
            record = await result.single()
            if record is None:
                return False
            return True

    async def delete_node(self, node_id: str) -> bool:
        """删除节点及其所有关系

        Args:
            node_id: 节点唯一标识

        Returns:
            删除成功返回 True，不存在返回 False
        """
        async with self._driver.session(database=self._database) as session:
            cypher = """
            MATCH (n {id: $node_id})
            DETACH DELETE n
            RETURN count(n) as deleted
            """
            result = await session.run(cypher, node_id=node_id)
            record = await result.single()
            if record is None:
                return False
            return cast(bool, record["deleted"] > 0)

    async def get_node(self, node_id: str) -> dict | None:
        """获取节点

        Args:
            node_id: 节点唯一标识

        Returns:
            节点数据字典，不存在返回 None
        """
        async with self._driver.session(database=self._database) as session:
            cypher = """
            MATCH (n {id: $node_id})
            RETURN n
            """
            result = await session.run(cypher, node_id=node_id)
            record = await result.single()
            if record is None:
                return None
            node = dict(record["n"])
            return node

    async def create_relationship(self, relationship: GraphRelationship) -> bool:
        """创建关系

        Args:
            relationship: 图关系对象

        Returns:
            创建成功返回 True
        """
        rel_type = str(relationship.relationship_type).upper().replace(" ", "_")
        async with self._driver.session(database=self._database) as session:
            cypher = f"""
            MATCH (a {{id: $start_id}}), (b {{id: $end_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            ON CREATE SET r += $properties, r.created_at = $created_at
            ON MATCH SET r += $properties
            RETURN r
            """
            result = await session.run(
                cypher,
                start_id=relationship.start_node_id,
                end_id=relationship.end_node_id,
                properties=relationship.properties,
                created_at=relationship.created_at.isoformat(),
            )
            record = await result.single()
            return record is not None

    async def delete_relationship(self, start_node_id: str, end_node_id: str, relationship_type: str) -> bool:
        """删除关系

        Args:
            start_node_id: 起始节点 ID
            end_node_id: 结束节点 ID
            relationship_type: 关系类型

        Returns:
            删除成功返回 True，不存在返回 False
        """
        rel_type = str(relationship_type).upper().replace(" ", "_")
        async with self._driver.session(database=self._database) as session:
            cypher = f"""
            MATCH (a {{id: $start_id}})-[r:{rel_type}]->(b {{id: $end_id}})
            DELETE r
            RETURN count(r) as deleted
            """
            result = await session.run(
                cypher,
                start_id=start_node_id,
                end_id=end_node_id,
            )
            record = await result.single()
            if record is None:
                return False
            return cast(bool, record["deleted"] > 0)
