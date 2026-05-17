"""基础设施层 Neo4j 图数据库存储模块

提供 L5 图存储层的 Neo4j 实现，包括图管理、图检索和知识图谱功能

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from src.infrastructure.storage.neo4j.neo4j_adapter import Neo4jAdapter

__all__ = [
    "Neo4jAdapter",
]
