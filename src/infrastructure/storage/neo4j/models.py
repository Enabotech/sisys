"""基础设施层 Neo4j 图存储数据模型模块

包含 GraphNode、GraphRelationship 和 RelationshipType 定义，所有模型位于基础设施层

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class RelationshipType(StrEnum):
    """Neo4j 关系类型枚举

    定义系统中允许的关系类型，确保图谱数据的一致性
    """

    MENTIONS = "MENTIONS"
    DEPENDS_ON = "DEPENDS_ON"
    RELATES_TO = "RELATES_TO"
    PART_OF = "PART_OF"
    INFLUENCES = "INFLUENCES"
    CONTRADICTS = "CONTRADICTS"


@dataclass
class GraphNode:
    """图节点数据模型

    用于存储实体节点（Entity/Document/Concept）及其属性

    字段说明:
        id: 节点唯一标识
        labels: 节点标签列表（应遵循 sisys:{entity_type} 规范）
        properties: 节点属性字典
        created_at: 创建时间（UTC）
    """

    id: str
    labels: list[str] = field(default_factory=list)
    properties: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """验证节点数据是否有效

        Raises:
            ValueError: ID 为空、labels 为空或缺少必需属性时抛出
        """
        if not self.id or not self.id.strip():
            raise ValueError("Node id must be a non-empty string")
        if not self.labels:
            raise ValueError("Node must have at least one label")
        # 验证 properties 包含必需字段
        required_props = {"business_domain", "entity_type", "content_hash"}
        missing = required_props - set(self.properties.keys())
        if missing:
            raise ValueError(f"Node properties must include: {missing}")


@dataclass
class GraphRelationship:
    """图关系数据模型

    用于存储实体之间的关系边

    字段说明:
        start_node_id: 起始节点 ID
        end_node_id: 结束节点 ID
        relationship_type: 关系类型
        properties: 关系属性字典
        created_at: 创建时间（UTC）
    """

    start_node_id: str
    end_node_id: str
    relationship_type: RelationshipType | str
    properties: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """验证关系数据是否有效

        Raises:
            ValueError: 起始/结束节点 ID 为空或关系类型未指定时抛出
        """
        if not self.start_node_id or not self.start_node_id.strip():
            raise ValueError("start_node_id must be a non-empty string")
        if not self.end_node_id or not self.end_node_id.strip():
            raise ValueError("end_node_id must be a non-empty string")
        if not self.relationship_type:
            raise ValueError("relationship_type must be specified")
