"""基础设施层 Neo4j 适配器模块

包装 Neo4jGraphStorage，实现 L5GraphPort 接口。使用 memory_id 作为实体主键，
高级语义方法通过 Cypher MERGE 实现
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, cast

from src.domain.exceptions import ValidationError
from src.domain.ports.l5_graph import L5GraphPort

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Neo4j relationship type: uppercase letters, digits, underscores
_REL_TYPE_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class Neo4jAdapter(L5GraphPort):
    """Neo4j 图存储适配器

    包装现有 Neo4jGraphStorage，实现 L5GraphPort 接口
    使用 memory_id 作为实体主键
    """

    def __init__(self, storage: Any):
        """初始化适配器

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
        """创建实体节点（MERGE 语义）

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
        """获取实体

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
        """删除实体及关联边

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
        """创建关系边（MERGE 语义）

        Args:
            source_memory_id: 源实体 ID
            target_memory_id: 目标实体 ID
            relationship_type: 关系类型
            properties: 关系属性

        Returns:
            是否成功
        """
        _validate_rel_type(relationship_type)

        safe_props = _sanitize_property_keys(properties or {})
        props_clause = ", ".join([f"r.{k} = ${k}" for k in safe_props])
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
        """删除关系边

        Args:
            source_memory_id: 源实体 ID
            target_memory_id: 目标实体 ID
            relationship_type: 关系类型

        Returns:
            是否成功
        """
        _validate_rel_type(relationship_type)

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
        """查找关联实体（多跳遍历）

        Args:
            memory_id: 起始实体 ID
            max_depth: 最大遍历深度
            relationship_type: 过滤关系类型

        Returns:
            关联实体列表
        """
        depth = max(1, min(int(max_depth), 10))
        if relationship_type:
            _validate_rel_type(relationship_type)
            cypher = f"""
            MATCH path = (start:Memory {{id: $memory_id}})-[:{relationship_type}*1..{depth}]-(end)
            WITH path, end
            RETURN end.id as memory_id, end.type as type, properties(end) as properties, path
            LIMIT 50
            """
        else:
            cypher = f"""
            MATCH path = (start:Memory {{id: $memory_id}})-[*1..{depth}]-(end)
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
        """执行只读 Cypher 查询

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
        """执行写入 Cypher 查询

        Args:
            cypher: Cypher 查询语句
            params: 查询参数字典

        Returns:
            查询结果列表
        """
        return cast("list[dict[Any, Any]]", await self._storage.execute_write_query(cypher, params))

    async def get_neighbors(
        self,
        memory_id: str,
        max_depth: int = 1,
        edge_type: str | None = None,
    ) -> list[dict]:
        """获取邻居节点（直接关联的实体）

        桥接 L5GraphPort.get_neighbors(memory_id, max_depth, edge_type)
        到 Neo4jGraphStorage.get_neighbors(node_id, rel_type, direction)

        Args:
            memory_id: 实体主键
            max_depth: 最大深度（默认 1，只看直接邻居）
            edge_type: 过滤边类型，None 表示所有

        Returns:
            邻居节点列表 [{memory_id, type, properties}, ...]
        """
        if max_depth <= 1:
            # 直接委托给底层 get_neighbors（单跳）
            return cast(
                "list[dict[Any, Any]]",
                await self._storage.get_neighbors(
                    node_id=memory_id,
                    rel_type=edge_type,
                ),
            )
        # 多跳：使用 find_related 的语义遍历
        return await self.find_related(memory_id, max_depth=max_depth, relationship_type=edge_type)

    async def search_entities(
        self,
        query_text: str,
        limit: int = 10,
    ) -> list[dict]:
        """按实体名模糊匹配搜索实体

        通过 Neo4j 全文索引以实体 name 属性进行不区分大小写的模糊匹配，
        返回候选实体列表。若全文索引不存在，降级为 Cypher CONTAINS 子串匹配。

        Args:
            query_text: 查询文本（按实体名模糊匹配）
            limit: 最多返回的候选实体数量

        Returns:
            候选实体列表 [{memory_id, type, properties, ...}, ...]
        """
        if not query_text or not query_text.strip():
            return []

        params: dict[str, Any] = {}
        # 优先使用全文索引（若存在）
        fuzzy_search = f"""
        CALL db.index.fulltext.queryNodes('entity_names', $query_text)
        YIELD node, score
        RETURN node.id AS memory_id, node.type AS type, properties(node) AS properties, score
        ORDER BY score DESC
        LIMIT {int(limit)}
        """
        params["query_text"] = query_text.strip()

        try:
            result = await self._storage.execute_query(fuzzy_search, params)
            if result:
                return [
                    {
                        "memory_id": r.get("memory_id"),
                        "type": r.get("type"),
                        "properties": r.get("properties", {}),
                        "score": r.get("score", 0.0),
                    }
                    for r in result
                    if r.get("memory_id")
                ]
        except Exception:
            # 全文索引不存在，降级为 CONTAINS 子串匹配
            logger.debug("全文索引不可用，降级为 CONTAINS 子串匹配")

        # 降级方案：Cypher CONTAINS 子串匹配
        contains_search = f"""
        MATCH (n)
        WHERE n.name CONTAINS $query_text
        RETURN n.id AS memory_id, n.type AS type, properties(n) AS properties
        LIMIT {int(limit)}
        """
        try:
            result = await self._storage.execute_query(contains_search, params)
        except Exception as e:
            logger.warning("search_entities CONTAINS 降级查询失败: %s", e)
            return []

        return [
            {
                "memory_id": r.get("memory_id"),
                "type": r.get("type"),
                "properties": r.get("properties", {}),
            }
            for r in result
            if r.get("memory_id")
        ]


def _validate_rel_type(rel_type: str) -> None:
    """验证关系类型是否符合 Neo4j 命名规范

    Args:
        rel_type: 关系类型字符串

    Raises:
        ValidationError: 关系类型不符合 [A-Z_][A-Z0-9_]* 模式时抛出
    """
    if not _REL_TYPE_RE.match(rel_type):
        raise ValidationError(message=f"Invalid relationship type: {rel_type!r}. Must match [A-Z_][A-Z0-9_]*")


def _sanitize_property_keys(props: dict) -> dict:
    """清洗属性键名，防止 Cypher 注入

    Args:
        props: 原始属性字典

    Returns:
        清洗后的属性字典

    Raises:
        ValidationError: 属性键名不符合 [a-zA-Z_][a-zA-Z0-9_]* 模式时抛出
    """
    safe = {}
    for k, v in props.items():
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", k):
            raise ValidationError(message=f"Invalid property key: {k!r}")
        safe[k] = v
    return safe
