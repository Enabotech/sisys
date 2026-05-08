"""Neo4jAdapter — L5GraphPort 实现。

包装现有 Neo4jGraphStorage，实现 L5GraphPort 接口。

设计说明：
- 使用 memory_id 作为实体主键
- 高级语义方法（create_entity 等）通过 Cypher MERGE 实现
- 委托低级查询给内部存储

设计原则：
- 薄适配器层，仅做接口转换
- 所有方法使用 async/await
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from src.domain.ports.l5_graph import L5GraphPort

if TYPE_CHECKING:
    pass


class Neo4jAdapter(L5GraphPort):
    """Neo4j 图存储适配器。

    包装现有 Neo4jGraphStorage，实现 L5GraphPort 接口。
    使用 memory_id 作为实体主键。
    """

    def __init__(self, storage: Any):
        """初始化适配器。

        Args:
            storage: Neo4jGraphStorage 实例
        """
        self._storage = storage

    async def create_entity(
        self,
        memory_id: str,
        entity_type: str,
        properties: dict[str, Any],
    ) -> bool:
        """创建实体节点（MERGE 语义）。

        Args:
            memory_id: 关联的记忆 ID（主键）
            entity_type: 实体类型
            properties: 实体属性

        Returns:
            是否成功
        """
        cypher = """
        MERGE (n:Memory {id: $memory_id})
        SET n.type = $entity_type, n += $properties
        RETURN n
        """
        result = await self._storage.execute_write_query(
            cypher,
            {"memory_id": memory_id, "entity_type": entity_type, "properties": properties},
        )
        return len(result) > 0

    async def get_entity(
        self,
        memory_id: str,
    ) -> dict | None:
        """获取实体。

        Args:
            memory_id: 实体主键

        Returns:
            实体数据，不存在返回 None
        """
        cypher = """
        MATCH (n:Memory {id: $memory_id})
        RETURN n.id as id, n.type as type, properties(n) as properties
        """
        result = await self._storage.execute_query(
            cypher,
            {"memory_id": memory_id},
        )
        if not result:
            return None
        record = result[0]
        return {
            "id": record.get("id"),
            "type": record.get("type"),
            "properties": record.get("properties", {}),
        }

    async def delete_entity(
        self,
        memory_id: str,
    ) -> bool:
        """删除实体及关联边。

        Args:
            memory_id: 实体主键

        Returns:
            是否成功
        """
        cypher = """
        MATCH (n:Memory {id: $memory_id})
        DETACH DELETE n
        """
        await self._storage.execute_write_query(
            cypher,
            {"memory_id": memory_id},
        )
        return True

    async def create_relationship(
        self,
        source_memory_id: str,
        target_memory_id: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """创建关系边（MERGE 语义）。

        Args:
            source_memory_id: 源实体 ID
            target_memory_id: 目标实体 ID
            relationship_type: 关系类型
            properties: 关系属性

        Returns:
            是否成功
        """
        props_clause = ", ".join([f"r.{k} = ${k}" for k in (properties or {})])
        if props_clause:
            props_clause = f"SET {props_clause}"

        cypher = f"""
        MATCH (source:Memory {{id: $source_memory_id}})
        MATCH (target:Memory {{id: $target_memory_id}})
        MERGE (source)-[r:{relationship_type}]->(target)
        {props_clause}
        RETURN r
        """
        params = {
            "source_memory_id": source_memory_id,
            "target_memory_id": target_memory_id,
        }
        if properties:
            params.update(properties)

        result = await self._storage.execute_write_query(cypher, params)
        return len(result) > 0

    async def delete_relationship(
        self,
        source_memory_id: str,
        target_memory_id: str,
        relationship_type: str,
    ) -> bool:
        """删除关系边。

        Args:
            source_memory_id: 源实体 ID
            target_memory_id: 目标实体 ID
            relationship_type: 关系类型

        Returns:
            是否成功
        """
        cypher = f"""
        MATCH (source:Memory {{id: $source_memory_id}})-[r:{relationship_type}]->(target:Memory {{id: $target_memory_id}})
        DELETE r
        """
        await self._storage.execute_write_query(
            cypher,
            {
                "source_memory_id": source_memory_id,
                "target_memory_id": target_memory_id,
            },
        )
        return True

    async def find_related(
        self,
        memory_id: str,
        max_depth: int = 2,
        relationship_type: str | None = None,
    ) -> list[dict]:
        """查找关联实体（多跳遍历）。

        Args:
            memory_id: 起始实体 ID
            max_depth: 最大遍历深度
            relationship_type: 过滤关系类型

        Returns:
            关联实体列表
        """
        if relationship_type:
            cypher = f"""
            MATCH path = (start:Memory {{id: $memory_id}})-[:{relationship_type}*1..{max_depth}]-(end)
            WITH path, end
            RETURN end.id as memory_id, end.type as type, properties(end) as properties, path
            LIMIT 50
            """
        else:
            cypher = f"""
            MATCH path = (start:Memory {{id: $memory_id}})-[*1..{max_depth}]-(end)
            WITH path, end
            RETURN end.id as memory_id, end.type as type, properties(end) as properties, path
            LIMIT 50
            """

        result = await self._storage.execute_query(cypher, {"memory_id": memory_id})
        return [
            {
                "memory_id": r.get("memory_id"),
                "type": r.get("type"),
                "properties": r.get("properties", {}),
                "path": r.get("path", []),
            }
            for r in result
        ]

    async def execute_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行只读 Cypher 查询。

        Args:
            cypher: Cypher 查询语句
            params: 查询参数字典

        Returns:
            查询结果列表
        """
        return cast("list[dict[Any, Any]]", await self._storage.execute_query(cypher, params))

    async def execute_write_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行写入 Cypher 查询。

        Args:
            cypher: Cypher 查询语句
            params: 查询参数字典

        Returns:
            查询结果列表
        """
        return cast("list[dict[Any, Any]]", await self._storage.execute_write_query(cypher, params))
