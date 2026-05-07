"""GraphRAG 图检索器实现。

提供实体关联检索、文档关联和社区发现基础功能。
"""

from __future__ import annotations

from src.infrastructure.storage.neo4j.client import Neo4jClientWrapper


class GraphRetriever:
    """GraphRAG 图检索器。

    提供高级图检索功能，为 Story 3.4/3.13/3.17 的 GraphRAG 提供基础。
    """

    def __init__(self, client_wrapper: Neo4jClientWrapper, database: str = "neo4j"):
        """初始化图检索器。

        Args:
            client_wrapper: Neo4j 客户端封装
            database: 数据库名称
        """
        self._client_wrapper = client_wrapper
        self._database = database

    def _get_driver(self):
        """获取异步驱动。"""
        return self._client_wrapper.get_async_driver()

    async def find_related_entities(
        self,
        entity_id: str,
        max_depth: int = 2,
        limit: int = 20,
    ) -> list[dict]:
        """查找与指定实体相关的其他实体。

        Args:
            entity_id: 实体节点 ID
            max_depth: 最大遍历深度
            limit: 返回结果数量限制

        Returns:
            相关实体列表，按关系权重/置信度排序
        """
        driver = self._get_driver()
        # Cypher doesn't support parameters in variable-length patterns,
        # so we construct the pattern with literal value
        cypher = f"""
        MATCH path = (start {{id: $entity_id}})-[*1..{max_depth}]-(related)
        WHERE start <> related
        WITH related, length(path) as hops, count(*) as connection_count
        ORDER BY connection_count DESC, hops ASC
        LIMIT $limit
        RETURN related, hops, connection_count
        """
        async with driver.session(database=self._database) as session:
            result = await session.run(
                cypher,
                entity_id=entity_id,
                limit=limit,
            )
            records = await result.data()
            return [
                {
                    "entity": dict(record["related"]),
                    "hops": record["hops"],
                    "connection_count": record["connection_count"],
                }
                for record in records
            ]

    async def find_related_documents(self, entity_id: str, limit: int = 10) -> list[dict]:
        """查找与指定实体相关的文档。

        Args:
            entity_id: 实体节点 ID
            limit: 返回结果数量限制

        Returns:
            相关文档列表
        """
        driver = self._get_driver()
        cypher = """
        MATCH (entity {id: $entity_id})-[:MENTIONS*1..2]-(doc:sisys:Document)
        WITH doc, count(*) as mention_count
        ORDER BY mention_count DESC
        LIMIT $limit
        RETURN doc, mention_count
        """
        async with driver.session(database=self._database) as session:
            result = await session.run(
                cypher,
                entity_id=entity_id,
                limit=limit,
            )
            records = await result.data()
            return [
                {
                    "document": dict(record["doc"]),
                    "mention_count": record["mention_count"],
                }
                for record in records
            ]

    async def find_community(self, node_ids: list[str]) -> list[dict]:
        """查找节点所属的社区（连通分量）。

        MVP 使用 BFS/DFS 遍历实现 Connected Components 算法。
        复杂度 O(V+E)。

        Args:
            node_ids: 节点 ID 列表

        Returns:
            社区成员列表
        """
        if not node_ids:
            return []

        driver = self._get_driver()
        cypher = """
        MATCH (start)
        WHERE start.id IN $node_ids
        CALL {
            WITH start
            MATCH (start)-[*]-(community_member)
            RETURN DISTINCT community_member
        }
        RETURN DISTINCT community_member
        """
        async with driver.session(database=self._database) as session:
            result = await session.run(cypher, node_ids=node_ids)
            records = await result.data()
            return [{"node": dict(record["community_member"])} for record in records]
