"""Graph storage repository interfaces.

定义图存储层的领域接口，位于领域层，不依赖任何 Neo4j 实现。
遵循依赖倒置原则：领域层定义接口，基础设施层实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol


class GraphNode(Protocol):
    """图节点协议（领域层抽象）。"""

    id: str
    labels: list[str]
    properties: dict
    created_at: Any


class GraphRelationship(Protocol):
    """图关系协议（领域层抽象）。"""

    start_node_id: str
    end_node_id: str
    relationship_type: str
    properties: dict
    created_at: Any


class GraphManager(ABC):
    """图管理器接口（领域层）。

    提供低级别图操作（节点/关系的 CRUD）。
    使用者：应用层用例，直接操作图谱。
    """

    @abstractmethod
    async def create_node(self, node: Any) -> bool:
        """创建节点。

        Args:
            node: 图节点对象

        Returns:
            创建成功返回 True，已存在返回 False（MERGE 语义）
        """

    @abstractmethod
    async def delete_node(self, node_id: str) -> bool:
        """删除节点。

        Args:
            node_id: 节点唯一标识

        Returns:
            删除成功返回 True，不存在返回 False
        """

    @abstractmethod
    async def get_node(self, node_id: str) -> Any | None:
        """获取节点。

        Args:
            node_id: 节点唯一标识

        Returns:
            图节点对象，不存在返回 None
        """

    @abstractmethod
    async def create_relationship(self, relationship: Any) -> bool:
        """创建关系。

        Args:
            relationship: 图关系对象

        Returns:
            创建成功返回 True
        """

    @abstractmethod
    async def delete_relationship(self, start_node_id: str, end_node_id: str, relationship_type: str) -> bool:
        """删除关系。

        Args:
            start_node_id: 起始节点 ID
            end_node_id: 结束节点 ID
            relationship_type: 关系类型

        Returns:
            删除成功返回 True，不存在返回 False
        """


class GraphStorage(ABC):
    """图存储接口（领域层）。

    提供高级别图查询（Cypher 执行、图遍历、检索）。
    使用者：应用层用例，执行复杂查询。
    """

    @abstractmethod
    async def execute_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        """执行只读 Cypher 查询。

        Args:
            cypher: Cypher 查询语句
            params: 查询参数字典

        Returns:
            查询结果列表（字典列表）
        """

    @abstractmethod
    async def execute_write_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        """执行写入 Cypher 查询。

        Args:
            cypher: Cypher 查询语句
            params: 查询参数字典

        Returns:
            查询结果列表（字典列表）
        """

    @abstractmethod
    async def find_path(self, start_id: str, end_id: str, max_depth: int = 3) -> list[dict]:
        """查找两个节点之间的路径。

        Args:
            start_id: 起始节点 ID
            end_id: 结束节点 ID
            max_depth: 最大遍历深度

        Returns:
            路径列表（每个路径包含节点和关系）
        """

    @abstractmethod
    async def get_neighbors(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "BOTH",
    ) -> list[Any]:
        """获取节点的邻居节点。

        Args:
            node_id: 节点 ID
            rel_type: 关系类型过滤（可选）
            direction: 遍历方向（IN/OUT/BOTH）

        Returns:
            邻居节点列表
        """
