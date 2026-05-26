"""领域层存储层级枚举定义模块

对应 architecture.md §11.2.9 存储层级策略：
- StorageLayer: 存储层级（L0-L5）
- StorageTier: 存储温度策略（热/温/冷/冻）
- DataAccessPattern: 数据访问模式

设计原则：
- 领域层零外部依赖（仅用 enum）
"""

from __future__ import annotations

from enum import Enum


class StorageLayer(Enum):
    """存储层级枚举"""

    L0_FILE = "l0_file"  # 文件系统
    L1_CACHE = "l1_cache"  # Redis 缓存
    L2_SQL = "l2_sql"  # PostgreSQL
    L3_VECTOR = "l3_vector"  # Qdrant 向量
    L4_OBJECT = "l4_object"  # MinIO 对象
    L5_GRAPH = "l5_graph"  # Neo4j 图


class StorageTier(Enum):
    """存储层级策略（来自 architecture.md §11.2.9）"""

    HOT = "hot"  # 热数据: L1 缓存优先（访问频率 ≥100/周）
    WARM = "warm"  # 温数据: L1 + L2 + L0（访问频率 10-99/周）
    COLD = "cold"  # 冷数据: L2 + L4（访问频率 1-9/周）
    FROZEN = "frozen"  # 冻结数据: L4 + L5（访问频率 = 0 或 Checkpoint）


class DataAccessPattern(Enum):
    """数据访问模式"""

    FREQUENT = "frequent"  # 高频访问（≥100/周）
    OCCASIONAL = "occasional"  # 偶尔访问（10-99/周）
    RARE = "rare"  # 很少访问（1-9/周）
    ARCHIVED = "archived"  # 归档（0 或 Checkpoint）
