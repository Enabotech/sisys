"""Neo4jMemoryGraphStorage — MemoryGraphPort 实现（Rule 4）。

组合注入 Neo4jAdapter（Rule 3），添加记忆关系语义：
实体关系提取、知识图谱查询。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.application.ports.memory_graph_port import MemoryGraphPort

if TYPE_CHECKING:
    from src.infrastructure.storage.neo4j.neo4j_adapter import Neo4jAdapter

logger = logging.getLogger(__name__)


class Neo4jMemoryGraphStorage(MemoryGraphPort):
    """Neo4j 记忆图存储 — 实现 MemoryGraphPort。

    组合 Neo4jAdapter（Rule 3，L5GraphPort 实现），
    添加记忆关系语义：内容→实体→关系提取、知识图谱查询。
    """

    def __init__(self, adapter: Neo4jAdapter):
        """初始化 Neo4jMemoryGraphStorage。

        Args:
            adapter: Neo4jAdapter 实例（Rule 3）
        """
        self._adapter = adapter

    # -- L5GraphPort methods (delegate to adapter) --

    async def create_entity(
        self,
        memory_id: str,
        entity_type: str,
        properties: dict[str, Any],
    ) -> bool:
        """创建实体节点。"""
        return await self._adapter.create_entity(memory_id, entity_type, properties)

    async def get_entity(self, memory_id: str) -> dict | None:
        """获取实体。"""
        return await self._adapter.get_entity(memory_id)

    async def delete_entity(self, memory_id: str) -> bool:
        """删除实体及关联边。"""
        return await self._adapter.delete_entity(memory_id)

    async def create_relationship(
        self,
        source_memory_id: str,
        target_memory_id: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """创建关系边。"""
        return await self._adapter.create_relationship(source_memory_id, target_memory_id, relationship_type, properties)

    async def delete_relationship(
        self,
        source_memory_id: str,
        target_memory_id: str,
        relationship_type: str,
    ) -> bool:
        """删除关系边。"""
        return await self._adapter.delete_relationship(source_memory_id, target_memory_id, relationship_type)

    async def find_related(
        self,
        memory_id: str,
        max_depth: int = 2,
        relationship_type: str | None = None,
    ) -> list[dict]:
        """查找关联实体。"""
        return await self._adapter.find_related(memory_id, max_depth, relationship_type)

    async def execute_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行只读 Cypher 查询。"""
        return await self._adapter.execute_query(cypher, params)

    async def execute_write_query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict]:
        """执行写入 Cypher 查询。"""
        return await self._adapter.execute_write_query(cypher, params)

    async def get_neighbors(
        self,
        memory_id: str,
        max_depth: int = 1,
        edge_type: str | None = None,
    ) -> list[dict]:
        """获取邻居节点。"""
        return await self._adapter.get_neighbors(memory_id, max_depth, edge_type)

    # -- MemoryGraphPort specific methods --

    async def index_memory_relations(
        self,
        memory_id: str,
        content: str,
    ) -> int:
        """提取并索引记忆中的实体关系。

        简单实现：将记忆内容注册为实体节点。
        生产环境应集成 NER 服务提取实体和关系。
        """
        await self._adapter.create_entity(
            memory_id=memory_id,
            entity_type="Memory",
            properties={"content_hash": _content_hash(content)},
        )
        return 1

    async def get_knowledge_graph(
        self,
        memory_id: str,
        depth: int = 2,
    ) -> dict:
        """获取记忆的知识图谱子图。"""
        entity = await self._adapter.get_entity(memory_id)
        if entity is None:
            return {"entities": [], "connections": []}

        related = await self._adapter.find_related(memory_id, max_depth=depth)
        entities = [entity] + [
            {
                "id": r.get("memory_id"),
                "type": r.get("type"),
                "properties": r.get("properties", {}),
            }
            for r in related
        ]

        return {
            "entities": entities,
            "connections": related,
        }


def _content_hash(content: str) -> str:
    """计算内容短 hash。"""
    import hashlib

    return hashlib.sha256(content.encode()).hexdigest()[:16]
