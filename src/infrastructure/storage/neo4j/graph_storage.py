"""Neo4j 图存储实现。

提供 Cypher 查询执行和图遍历功能。
"""

from __future__ import annotations

from typing import Any, cast

from src.infrastructure.storage.neo4j.client import Neo4jClientWrapper


class Neo4jGraphStorage:
    """Neo4j 图存储实现。

    实现 GraphStorage 接口，提供 Cypher 查询和图遍历功能。
    """

    def __init__(self, client_wrapper: Neo4jClientWrapper, database: str = "neo4j"):
        """初始化图存储。

        Args:
            client_wrapper: Neo4j 客户端封装
            database: 数据库名称
        """
        self._client_wrapper = client_wrapper
        self._database = database

    def _get_driver(self):
        """获取异步驱动。"""
        return self._client_wrapper.get_async_driver()

    async def execute_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        """执行只读 Cypher 查询。

        Args:
            cypher: Cypher 查询语句
            params: 查询参数字典

        Returns:
            查询结果列表（字典列表）
        """
        driver = self._get_driver()
        query_params = params or {}
        async with driver.session(database=self._database) as session:
            result = await session.run(cypher, **query_params)
            records = cast(list[dict[str, Any]], await result.data())
            return records

    async def execute_write_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        """执行写入 Cypher 查询。

        Args:
            cypher: Cypher 查询语句
            params: 查询参数字典

        Returns:
            查询结果列表（字典列表）
        """
        driver = self._get_driver()
        query_params = params or {}
        async with driver.session(database=self._database) as session:
            result = await session.run(cypher, **query_params)
            records = cast(list[dict[str, Any]], await result.data())
            return records

    async def find_path(self, start_id: str, end_id: str, max_depth: int = 3) -> list[dict]:
        """查找两个节点之间的路径。

        Args:
            start_id: 起始节点 ID
            end_id: 结束节点 ID
            max_depth: 最大遍历深度

        Returns:
            路径列表（每个路径包含节点和关系信息）
        """
        # Cypher doesn't support parameters in variable-length patterns,
        # so we construct the pattern with literal value
        cypher = f"""
        MATCH path = (start {{id: $start_id}})-[*1..{max_depth}]-(end {{id: $end_id}})
        RETURN path
        LIMIT 10
        """
        return await self.execute_query(
            cypher,
            {
                "start_id": start_id,
                "end_id": end_id,
            },
        )

    async def get_neighbors(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[dict]:
        """获取节点的邻居节点。

        Args:
            node_id: 节点 ID
            rel_type: 关系类型过滤（可选）
            direction: 遍历方向（IN/OUT/BOTH）

        Returns:
            邻居节点数据列表
        """
        if rel_type:
            rel_type_str = f":{rel_type.upper()}"
        else:
            rel_type_str = ""

        if direction == "BOTH":
            cypher = f"""
            MATCH (n {{id: $node_id}}){rel_type_str}-(neighbor)
            RETURN DISTINCT neighbor
            """
        elif direction == "OUT":
            cypher = f"""
            MATCH (n {{id: $node_id}}){rel_type_str}->(neighbor)
            RETURN DISTINCT neighbor
            """
        else:  # IN
            if rel_type_str:
                cypher = f"""
                MATCH (n {{id: $node_id}})<-{rel_type_str}-(neighbor)
                RETURN DISTINCT neighbor
                """
            else:
                cypher = """
                MATCH (n {id: $node_id})<--(neighbor)
                RETURN DISTINCT neighbor
                """

        return await self.execute_query(cypher, {"node_id": node_id})
