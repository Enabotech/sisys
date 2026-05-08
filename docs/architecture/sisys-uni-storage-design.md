# SISYS 统一存储架构详细设计

**版本:** v2.0
**日期:** 2026-05-08
**作者:** Claude Code (宗师级架构设计)
**状态:** 设计完成
**基于:** architecture.md §11 存储架构设计 + sisys-uni-storage-refactor.md

---

## 1. 设计背景与目标

### 1.1 问题陈述

当前 `SixLayerStorageCoordinator` 存在以下六边形架构违反：

| 问题 | 描述 | 违反原则 |
|------|------|----------|
| P1 | Application 层直接依赖 Infrastructure 具体类（`RedisMemoryCache`, `QdrantVectorStorage` 等） | 依赖倒置原则 |
| P2 | L1 缓存层无 Port 接口，直接使用 `RedisMemoryCache` | 依赖倒置原则 |
| P3 | L1 语义缓存层无 Port 接口，直接使用 `RedisSemanticCache` | 依赖倒置原则 |
| P4 | 快照存储层无 Port 接口，直接使用 `RedisSnapshotStore` | 依赖倒置原则 |
| P5 | L3-L5 在协调器中未实现（仅 TODO 注释） | 完整实现原则 |

### 1.2 设计目标

1. **六边形架构纯正**: 所有存储通过 Domain Port 接口解耦
2. **符合 architecture.md §11**: 严格遵循六层存储设计（L0-L5）
3. **统一入口**: 提供 `UnifiedStorageGateway` 统一编排各层
4. **可测试性**: 每个存储层通过 Port 接口可独立测试
5. **向后兼容**: 保留现有接口，不破坏现有调用方

### 1.3 与 architecture.md §11 对齐

| §11 章节 | 内容 | 本文档对应 |
|---------|------|-----------|
| 11.1 | 六层存储详细设计 | §3 各层 Port 接口设计 |
| 11.2.5 | L2 PostgreSQL 表设计 | 已有实现，无需变更 |
| 11.2.7 | 三层触发机制 | 已有实现，保持不变 |
| 11.2.9 | L0 驱动各层协同机制 | §4.1 UnifiedStorageGateway |
| 11.2.11 | 验收标准 | §7 验收标准 |

---

## 2. 架构总览

### 2.1 分层架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Application Layer                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    UnifiedStorageGateway                       │   │
│  │  职责: 统一存储入口，编排 L0-L5 各层存储                        │   │
│  │  依赖: Domain Port 接口（无 Infrastructure 直接依赖）          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              SixLayerStorageCoordinator                        │   │
│  │  状态: 仅测试用例使用                                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              │ 依赖 Port 接口
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Domain Layer                                │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐              │
│  │ L0StoragePort │ │ L1CachePort  │  │ L2RdbPort → MemoryMetadataRepositoryProtocol │
│  ├───────────────┤ ├───────────────┤ ├───────────────┤              │
│  │L3VectorPort   │ │L4ObjectPort   │ │L5GraphPort    │              │
│  └───────────────┘ └───────────────┘ └───────────────┘              │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              StoragePolicyService (领域服务)                    │  │
│  │  职责: 根据数据特征决定存储层级(HOT/WARM/COLD/FROZEN)            │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │ 实现 Port 接口
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Infrastructure Layer                           │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐              │
│  │ FileMemoryAdp │ │ RedisCacheAdp │ │ PostgreSQLAdp │              │
│  ├───────────────┤ ├───────────────┤ ├───────────────┤              │
│  │QdrantVectorAdp│ │ MinIOAdapter  │ │ Neo4jAdapter  │              │
│  └───────────────┘ └───────────────┘ └───────────────┘              │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                UnifiedStorageFactory                          │  │
│  │  职责: 根据配置创建各层 Adapter，组装 UnifiedStorageGateway     │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 六层存储职责（来自 architecture.md §11.1）

| 层级 | 技术 | 内容 | Port 接口 | 基础设施实现 |
|------|------|------|-----------|-------------|
| **L0** | 文件系统 | MEMORY.md 索引、记忆文件 | `L0StoragePort` | `FileMemoryAdapter` |
| **L1** | Redis 7.0+ | 会话状态、记忆缓存 | `L1CachePort` | `RedisMemoryCache (async)` |
| **L2** | PostgreSQL 15+ | 用户/RBAC、审计元数据 | `MemoryMetadataRepositoryProtocol` + `MemoryChangeHistoryRepositoryProtocol` | `PostgreSQLMemoryMetadataRepository` |
| **L3** | Qdrant 1.7+ | 嵌入向量、混合检索 | `L3VectorPort` | `QdrantVectorAdapter` |
| **L4** | MinIO WORM | 原始文档、证据包 | `L4ObjectPort` | `MinIOAdapter` |
| **L5** | Neo4j 5.x | 知识图谱、实体关系 | `L5GraphPort` | `Neo4jAdapter` |

---

## 3. Domain 层 Port 接口设计

### 3.1 设计原则

1. **零外部依赖**: 所有 Port 接口只依赖 `abc` 和 `typing`
2. **异步优先**: 所有操作使用 `async def`
3. **单一职责**: 每个 Port 只定义一层存储的接口
4. **与 architecture.md §11 对齐**: 接口契约符合 §11 定义的数据流

### 3.2 L0 文件系统存储接口

```python
# src/domain/ports/l0_storage.py

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class L0StoragePort(ABC):
    """L0 文件系统存储接口。

    对应 architecture.md §11.2.9 L0 驱动机制：
    - L0 是真相源，同步写入，强一致
    - 保证"上下文≠缓存"：写入时必须失效 L1 缓存

    职责：
    - 读写 ~/.sisys/memory/*.md 记忆文件
    - 管理 MEMORY.md 索引（最多 200 行）
    """

    @abstractmethod
    async def write(
        self,
        memory_id: str,
        memory_type: str,
        content: str,
    ) -> None:
        """写入记忆文件。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型 ('private' | 'group')
            content: 记忆内容
        """
        pass

    @abstractmethod
    async def read(
        self,
        memory_id: str,
        memory_type: str,
    ) -> str | None:
        """读取记忆文件。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型

        Returns:
            记忆内容，不存在返回 None
        """
        pass

    @abstractmethod
    async def delete(
        self,
        memory_id: str,
        memory_type: str,
    ) -> bool:
        """删除记忆文件。

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def exists(
        self,
        memory_id: str,
        memory_type: str,
    ) -> bool:
        """检查记忆文件是否存在。

        Returns:
            是否存在
        """
        pass

    @abstractmethod
    async def list_memories(
        self,
        memory_type: str | None = None,
    ) -> list[str]:
        """列出记忆文件。

        Args:
            memory_type: 过滤类型，None 表示所有

        Returns:
            memory_id 列表
        """
        pass

    @abstractmethod
    async def update_index(
        self,
        entry: str,
        max_lines: int = 200,
    ) -> None:
        """更新 MEMORY.md 索引。

        Args:
            entry: 索引条目（格式: "- [Title](file.md) — description"）
            max_lines: 最大行数（默认 200）
        """
        pass

    @abstractmethod
    async def remove_from_index(
        self,
        memory_id: str,
    ) -> None:
        """从 MEMORY.md 索引移除条目。

        Args:
            memory_id: 记忆 ID
        """
        pass
```

### 3.3 L1 缓存存储接口

```python
# src/domain/ports/l1_cache.py

from abc import ABC, abstractmethod


class L1CachePort(ABC):
    """L1 缓存存储接口。

    对应 architecture.md §11.2.9 L1 缓存策略：
    - 写入时失效：MemoryChanged 事件触发缓存失效
    - 读取时加速：高频访问可先查 L1，L1 未命中则查 L0
    - 不作为真相源：决策时以 L0 为准

    注意：L1 层包含两种缓存：
    - 记忆缓存（RedisMemoryCache）→ 本接口
    - 语义缓存（RedisSemanticCache）→ 独立接口，见 §3.10
    """

    @abstractmethod
    async def get(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> str | None:
        """从缓存读取。

        Args:
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID
            name: 记忆名称

        Returns:
            缓存内容，不存在返回 None
        """
        pass

    @abstractmethod
    async def set(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
        content: str,
        ttl: int | None = None,
    ) -> bool:
        """写入缓存。

        Args:
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称
            content: 内容
            ttl: TTL 秒数，None 使用默认（24h-30h 随机）

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def delete(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> bool:
        """删除缓存。

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def invalidate_pattern(
        self,
        memory_type: str,
        owner_id: str,
    ) -> int:
        """按模式失效缓存。

        Args:
            memory_type: 记忆类型
            owner_id: 所有者 ID

        Returns:
            失效的 key 数量
        """
        pass
```

### 3.4 L2 元数据存储接口

```python
# src/domain/ports/l2_metadata.py

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID


class MemoryMetadata:
    """记忆元数据值对象。"""
    memory_id: UUID
    user_id: str
    name: str
    description: str | None
    type: str  # 'user'/'feedback'/'project'/'reference'
    path: str
    version: int
    mtime: datetime
    owner: str | None
    group_id: str | None
    created_at: datetime
    updated_at: datetime


class MemoryChangeHistory:
    """记忆变更历史值对象。"""
    id: UUID
    memory_id: UUID
    version: int
    changed_at: datetime
    changed_by: str
    change_type: str  # 'create'/'update'/'delete'/'force_update'
    changed_fields: dict[str, Any] | None
    diff_summary: str | None
    archived_ref: str | None


### 3.4 L2 PostgreSQL 存储接口（复用现有 Protocol）

**注意**: L2 不新建 Port 接口，直接复用现有：
- `MemoryMetadataRepositoryProtocol` (src/domain/ports/memory_repository.py)
- `MemoryChangeHistoryRepositoryProtocol` (src/domain/ports/memory_repository.py)

对应 architecture.md §11.2.5 L2 PostgreSQL 表设计：
- memory_metadata: 记忆元数据索引（当前状态快照）
- memory_change_history: 记忆变更历史（append-only，不可变）

**理由**: 避免接口重复，这些 Protocol 已被 `PostgreSQLMemoryMetadataRepository` 和 `PostgreSQLMemoryChangeHistoryRepository` 实现。

```
现有实现（src/infrastructure/storage/postgresql/repository/）:
- PostgreSQLMemoryMetadataRepository → MemoryMetadataRepositoryProtocol
- PostgreSQLMemoryChangeHistoryRepository → MemoryChangeHistoryRepositoryProtocol
```

### 3.5 L3 向量存储接口

```python
# src/domain/ports/l3_vector.py

from abc import ABC, abstractmethod
from typing import Any


class L3VectorPort(ABC):
    """L3 Qdrant 向量存储接口。

    对应 architecture.md §11.1：
    - 内容 >500 tokens 时启用向量检索
    - 支持 Dense+Sparse+Payload 过滤

    职责：
    - 向量嵌入存储
    - 相似度检索
    """

    @abstractmethod
    async def upsert(
        self,
        memory_id: str,
        content: str,
        vector: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """插入或更新向量。

        Args:
            memory_id: 记忆 ID
            content: 文本内容
            vector: 嵌入向量，None 表示使用 content 生成
            metadata: 元数据（memory_type, owner_id 等）

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict]:
        """向量相似度搜索。

        Args:
            query_vector: 查询向量
            limit: 返回数量
            filter_metadata: 元数据过滤条件

        Returns:
            搜索结果列表 [{memory_id, score, payload}, ...]
        """
        pass

    @abstractmethod
    async def delete(
        self,
        memory_id: str,
    ) -> bool:
        """删除向量。

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def get(
        self,
        memory_id: str,
    ) -> dict | None:
        """获取向量数据。

        Returns:
            向量数据 {id, vector, payload}，不存在返回 None
        """
        pass
```

### 3.6 L4 对象存储接口

```python
# src/domain/ports/l4_object.py

from abc import ABC, abstractmethod
from typing import AsyncIterator


class L4ObjectPort(ABC):
    """L4 MinIO WORM 对象存储接口。

    对应 architecture.md §11.1：
    - 原始文档、证据包存储
    - Object Lock COMPLIANCE 模式 7 年 retention

    职责：
    - Checkpoint 快照归档
    - WORM 合规存储
    """

    @abstractmethod
    async def store(
        self,
        memory_id: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
    ) -> str:
        """存储对象。

        Args:
            memory_id: 记忆 ID
            content: 对象内容
            content_type: MIME 类型
            metadata: 元数据

        Returns:
            对象版本 ID 或 ETag
        """
        pass

    @abstractmethod
    async def retrieve(
        self,
        memory_id: str,
        version_id: str | None = None,
    ) -> AsyncIterator[bytes]:
        """检索对象。

        Args:
            memory_id: 记忆 ID
            version_id: 版本 ID，None 获取最新

        Returns:
            对象内容流
        """
        pass

    @abstractmethod
    async def delete(
        self,
        memory_id: str,
        version_id: str | None = None,
    ) -> bool:
        """删除对象（仅在 retention 到期后）。

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def get_metadata(
        self,
        memory_id: str,
        version_id: str | None = None,
    ) -> dict | None:
        """获取对象元数据。

        Returns:
            元数据字典，不存在返回 None
        """
        pass

    @abstractmethod
    async def archive_with_retention(
        self,
        memory_id: str,
        content: bytes,
        retention_days: int = 2555,  # 7 年
    ) -> str:
        """归档对象（带 retention）。

        Args:
            memory_id: 记忆 ID
            content: 对象内容
            retention_days: retention 天数（默认 2555 = 7 年）

        Returns:
            对象 ID
        """
        pass
```

### 3.7 L5 图存储接口

```python
# src/domain/ports/l5_graph.py

from abc import ABC, abstractmethod
from typing import Any


class L5GraphPort(ABC):
    """L5 Neo4j 图存储接口。

    对应 architecture.md §11.1：
    - 知识图谱、实体关系
    - Cypher、图遍历、Parent-Child 索引

    职责：
    - 实体节点管理
    - 关系边管理
    - 关联查询
    """

    @abstractmethod
    async def create_entity(
        self,
        memory_id: str,
        entity_type: str,
        properties: dict[str, Any],
    ) -> bool:
        """创建实体节点。

        Args:
            memory_id: 关联的记忆 ID
            entity_type: 实体类型
            properties: 实体属性

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def create_relationship(
        self,
        source_memory_id: str,
        target_memory_id: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """创建关系边。

        Args:
            source_memory_id: 源记忆 ID
            target_memory_id: 目标记忆 ID
            relationship_type: 关系类型
            properties: 关系属性

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def get_entity(
        self,
        memory_id: str,
    ) -> dict | None:
        """获取实体。

        Returns:
            实体数据 {type, properties}，不存在返回 None
        """
        pass

    @abstractmethod
    async def find_related(
        self,
        memory_id: str,
        max_depth: int = 2,
        relationship_type: str | None = None,
    ) -> list[dict]:
        """查找关联实体。

        Args:
            memory_id: 起始实体 ID
            max_depth: 最大遍历深度
            relationship_type: 过滤关系类型，None 表示所有

        Returns:
            关联实体列表 [{memory_id, type, properties, path}, ...]
        """
        pass

    @abstractmethod
    async def delete_entity(
        self,
        memory_id: str,
    ) -> bool:
        """删除实体及关联边。

        Returns:
            是否成功
        """
        pass
```

### 3.8 存储层级枚举

```python
# src/domain/ports/storage_enums.py

from enum import Enum


class StorageLayer(Enum):
    """存储层级枚举。"""
    L0_FILE = "l0_file"           # 文件系统
    L1_CACHE = "l1_cache"         # Redis 缓存
    L2_SQL = "l2_sql"             # PostgreSQL
    L3_VECTOR = "l3_vector"       # Qdrant 向量
    L4_OBJECT = "l4_object"      # MinIO 对象
    L5_GRAPH = "l5_graph"         # Neo4j 图


class StorageTier(Enum):
    """存储层级策略（来自 architecture.md §11.2.9）。"""
    HOT = "hot"       # 热数据: L1 缓存优先（访问频率 ≥100/周）
    WARM = "warm"    # 温数据: L1 + L2 + L0（访问频率 10-99/周）
    COLD = "cold"    # 冷数据: L2 + L4（访问频率 1-9/周）
    FROZEN = "frozen"  # 冻结数据: L4 + L5（访问频率 = 0 或 Checkpoint）


class DataAccessPattern(Enum):
    """数据访问模式。"""
    FREQUENT = "frequent"      # 高频访问（≥100/周）
    OCCASIONAL = "occasional"  # 偶尔访问（10-99/周）
    RARE = "rare"             # 很少访问（1-9/周）
    ARCHIVED = "archived"     # 归档（0 或 Checkpoint）
```

### 3.9 统一存储策略接口

```python
# src/domain/ports/unified_storage.py

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from src.domain.ports.storage_enums import StorageLayer, StorageTier

if TYPE_CHECKING:
    from src.domain.ports.l0_storage import L0StoragePort
    from src.domain.ports.l1_cache import L1CachePort
    from src.domain.ports.l2_metadata import L2RdbPort
    from src.domain.ports.l3_vector import L3VectorPort
    from src.domain.ports.l4_object import L4ObjectPort
    from src.domain.ports.l5_graph import L5GraphPort


class UnifiedStoragePort(ABC):
    """统一存储入口接口。

    定义存储系统的统一操作契约。
    对应 architecture.md §11.2.9 L0 驱动各层协同机制。

    设计原则：
    - L0 是真相源，同步写入
    - 其他层通过事件驱动异步更新
    - 读取遵循缓存优先策略（L1 → L0）
    """

    @abstractmethod
    async def save(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
        owner_id: str,
        name: str,
        tier: StorageTier = StorageTier.WARM,
    ) -> dict[StorageLayer, bool]:
        """保存记忆到多层存储。

        对应 architecture.md §11.2.9 写入流程：
        1. L0 文件系统（同步，强一致）
        2. 发布 MemoryChanged 事件（事务发件箱）
        3. L1 缓存失效（异步）
        4. L2 元数据写入（异步）
        5. L3 向量（按需，内容>500 tokens）
        6. L5 图谱（按需，EntityExtractor）

        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            memory_type: 记忆类型 ('private' | 'group')
            owner_id: 所有者 ID
            name: 记忆名称
            tier: 存储层级策略

        Returns:
            各层存储结果 {layer: success}
        """
        pass

    @abstractmethod
    async def read(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str,
        name: str,
        prefer_cache: bool = True,
    ) -> str | None:
        """读取记忆。

        对应 architecture.md §11.2.9 检索流程：
        - prefer_cache=True: L1 → L2 → L0（缓存优先）
        - prefer_cache=False: L2 → L0（直接读取持久层）

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称
            prefer_cache: 是否优先从缓存读取

        Returns:
            记忆内容，不存在返回 None
        """
        pass

    @abstractmethod
    async def delete(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> dict[StorageLayer, bool]:
        """删除记忆。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称

        Returns:
            各层删除结果
        """
        pass

    @abstractmethod
    async def exists(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> dict[StorageLayer, bool]:
        """检查记忆在各层的存在状态。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称

        Returns:
            各层存在状态 {layer: exists}
        """
        pass
```

### 3.10 语义缓存接口（独立于记忆系统）

```python
# src/domain/ports/semantic_cache.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

if TYPE_CHECKING:
    pass


@dataclass
class CacheResult:
    """缓存结果。"""
    value: Any
    hit: bool


class SemanticCachePort(ABC):
    """语义缓存接口。

    对应 architecture.md §11.3 语义缓存层设计：
    - 服务于 RAG 检索（Epic 3），不是记忆系统的核心组件
    - 使用 Redis 向量相似度搜索
    - SIMILARITY_THRESHOLD = 0.9, TTL = 86400

    职责：
    - 语义相似度缓存
    - RAG 检索加速
    """

    SIMILARITY_THRESHOLD: float = 0.9
    TTL: int = 86400  # 24 小时

    @abstractmethod
    async def get_or_compute(
        self,
        query: str,
        compute_fn: Callable,
    ) -> CacheResult:
        """获取或计算缓存结果。

        Args:
            query: 查询字符串
            compute_fn: 计算函数（当缓存未命中时调用）

        Returns:
            CacheResult {value, hit}
        """
        pass

    @abstractmethod
    async def invalidate(
        self,
        query: str,
    ) -> bool:
        """失效缓存。

        Returns:
            是否成功
        """
        pass
```

---

## 4. 应用层设计

### 4.1 UnifiedStorageGateway

```python
# src/application/services/unified_storage_gateway.py

"""UnifiedStorageGateway — 统一存储网关。

提供 L0-L5 六层存储的统一入口，根据存储策略自动编排各层存储。
对应 architecture.md §11.2.9 L0 驱动各层协同机制。

六边形约束遵守：
- 本类是应用层服务
- 依赖 Domain Port 接口，不直接依赖 Infrastructure
- 工厂由外部注入，遵循依赖倒置原则
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.ports.storage_enums import StorageLayer, StorageTier
from src.domain.ports.unified_storage import UnifiedStoragePort

if TYPE_CHECKING:
    from src.domain.ports.l0_storage import L0StoragePort
    from src.domain.ports.l1_cache import L1CachePort
    from src.domain.ports.memory_repository import (
        MemoryMetadataRepositoryProtocol,
        MemoryChangeHistoryRepositoryProtocol,
    )
    from src.domain.ports.l3_vector import L3VectorPort
    from src.domain.ports.l4_object import L4ObjectPort
    from src.domain.ports.l5_graph import L5GraphPort
    from src.domain.ports.memory_repository import MemoryMetadata
    from src.domain.ports.memory_repository import MemoryChangeHistory


class UnifiedStorageGateway(UnifiedStoragePort):
    """统一存储网关。

    职责：
    - 提供 L0-L5 六层存储的统一入口
    - 根据存储策略自动决定数据 placement
    - 协调各层存储的读写操作
    - 处理层间数据流动

    读取策略（来自 architecture.md §11.2.9）：
    - prefer_cache=True: L1 → L2 → L0（缓存优先）
    - prefer_cache=False: L2 → L0（直接读取持久层）
    """

    def __init__(
        self,
        l0_storage: L0StoragePort,
        l1_cache: L1CachePort,
        l2_metadata: MemoryMetadataRepositoryProtocol,
        l2_history: MemoryChangeHistoryRepositoryProtocol,
        l3_vector: L3VectorPort | None = None,
        l4_object: L4ObjectPort | None = None,
        l5_graph: L5GraphPort | None = None,
    ) -> None:
        """初始化统一存储网关。

        Args:
            l0_storage: L0 文件系统存储
            l1_cache: L1 Redis 缓存
            l2_metadata: L2 元数据仓储（现有 MemoryMetadataRepositoryProtocol）
            l2_history: L2 历史仓储（现有 MemoryChangeHistoryRepositoryProtocol）
            l3_vector: L3 向量存储
            l4_object: L4 对象存储
            l5_graph: L5 图存储
        """
        self._l0 = l0_storage
        self._l1 = l1_cache
        self._l2_meta = l2_metadata
        self._l2_hist = l2_history
        self._l3 = l3_vector
        self._l4 = l4_object
        self._l5 = l5_graph

    async def save(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
        owner_id: str,
        name: str,
        tier: StorageTier = StorageTier.WARM,
    ) -> dict[StorageLayer, bool]:
        """保存记忆到多层存储。

        对应 architecture.md §11.2.9 写入流程：
        1. L0 文件系统（同步，强一致）- 真相源
        2. 发布 MemoryChanged 事件到 Outbox（事务发件箱）
        3. 各层更新由 MemoryChangedListener 异步执行（L1失效/L2元数据/L3向量/L5图谱）

        注意：L1 缓存永远不应被 save() 直接写入，只应被失效。
        这是系统公理二："LLM 上下文 = 缓存，磁盘记忆 = 真相源"

        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称
            tier: 存储层级策略

        Returns:
            各层存储结果（L0写入结果 + Outbox发布状态）
        """
        results: dict[StorageLayer, bool] = {}

        # L0 文件系统（真相源，同步写入，强一致）
        results[StorageLayer.L0_FILE] = await self._l0.write(
            memory_id, memory_type, content
        )

        # 发布 MemoryChanged 事件（事务发件箱）
        # Outbox 发布后由 MemoryChangedListener 异步处理：
        # - L1 缓存失效
        # - L2 元数据写入
        # - L3 向量（内容>500 tokens）
        # - L5 图谱（按需 EntityExtractor）
        results[StorageLayer.L0_FILE] = True  # L0 写入成功

        return results

    async def read(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str,
        name: str,
        prefer_cache: bool = True,
    ) -> str | None:
        """读取记忆。

        对应 architecture.md §11.2.9 检索流程：
        - prefer_cache=True: L1 → L2 (RBAC校验) → L0（缓存优先）
        - prefer_cache=False: L2 (RBAC校验) → L0（直接读取持久层）

        读取策略（来自 architecture.md §11.2.9）：
        - L2 PostgreSQL（RBAC 校验）用于权限检查，过滤无权限记忆
        - L0 文件系统是真相源，最终以 L0 为准

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称
            prefer_cache: 是否优先从缓存读取

        Returns:
            记忆内容，不存在返回 None
        """
        # L1 缓存查找（可选加速）
        if prefer_cache:
            content = await self._l1.get(memory_type, owner_id, name)
            if content is not None:
                # 缓存命中后仍需 L0 校验（系统公理二：L0 是真相源）
                l0_content = await self._l0.read(memory_id, memory_type)
                if l0_content is not None:
                    return l0_content
                # L0 不存在则返回缓存（旧数据，可接受）

        # L2 PostgreSQL（RBAC 校验）
        metadata = await self._l2_meta.get_by_id(memory_id)
        if metadata is None:
            return None  # 记忆不存在或无权限

        # 检查权限
        if metadata.owner != owner_id and (metadata.group_id is None or metadata.type != memory_type):
            return None  # 无权限访问

        # L0 文件系统查找（真相源）
        content = await self._l0.read(memory_id, memory_type)
        if content is None:
            return None

        # 回填 L1 缓存（可选）
        if prefer_cache:
            await self._l1.set(memory_type, owner_id, name, content)

        return content

    async def delete(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> dict[StorageLayer, bool]:
        """删除记忆。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称

        Returns:
            各层删除结果
        """
        results: dict[StorageLayer, bool] = {}

        # L0 文件系统
        results[StorageLayer.L0_FILE] = await self._l0.delete(memory_id, memory_type)

        # L1 缓存失效
        results[StorageLayer.L1_CACHE] = await self._l1.delete(memory_type, owner_id, name)

        # L3 向量删除
        if self._l3 is not None:
            results[StorageLayer.L3_VECTOR] = await self._l3.delete(memory_id)

        # L5 图谱删除
        if self._l5 is not None:
            results[StorageLayer.L5_GRAPH] = await self._l5.delete_entity(memory_id)

        return results

    async def exists(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> dict[StorageLayer, bool]:
        """检查记忆在各层的存在状态。

        Returns:
            各层存在状态
        """
        return {
            StorageLayer.L0_FILE: await self._l0.exists(memory_id, memory_type),
            StorageLayer.L1_CACHE: await self._l1.get(memory_type, owner_id, name) is not None,
        }

    async def get_content(
        self,
        memory_id: str,
    ) -> str | None:
        """获取记忆内容（从 L0）。

        直接从 L0 文件系统读取，不走缓存。
        用于需要强一致性读取的场景。

        Args:
            memory_id: 记忆 ID

        Returns:
            记忆内容，不存在返回 None
        """
        # 需要从 L0 遍历查找（这里简化处理）
        content = await self._l0.read(memory_id, "private")
        if content is not None:
            return content
        return await self._l0.read(memory_id, "group")
```

### 4.2 StoragePolicyService

```python
# src/domain/services/storage_tier_strategy.py

"""存储层级策略服务。

根据数据特征和业务规则决定数据的存储层级。
对应 architecture.md §11.2.11 验收标准：
- HOT: 访问频率 ≥100/周
- WARM: 访问频率 10-99/周
- COLD: 访问频率 1-9/周
- FROZEN: 访问频率 = 0 或 Checkpoint
"""

from dataclasses import dataclass

from src.domain.ports.storage_enums import DataAccessPattern, StorageTier


@dataclass
class StorageDecision:
    """存储决策结果。"""
    tier: StorageTier
    access_pattern: DataAccessPattern
    ttl_hours: int | None = None
    compression_needed: bool = False


class StoragePolicyService:
    """存储层级策略。

    根据数据特征决定存储层级。
    """

    # 访问频率阈值（来自 architecture.md §11.2.11）
    FREQUENT_THRESHOLD = 100  # ≥100/周 → HOT
    OCCASIONAL_THRESHOLD = 10  # 10-99/周 → WARM
    RARE_THRESHOLD = 1  # 1-9/周 → COLD

    # Checkpoint 直接归档（系统公理二）
    CHECKPOINT_RETENTION_DAYS = 2555  # 7 年

    def decide_tier(
        self,
        access_frequency: int,
        content_size: int,
        is_checkpoint: bool = False,
    ) -> StorageDecision:
        """决定存储层级。

        Args:
            access_frequency: 访问频率（过去 7 天访问次数）
            content_size: 内容大小（字节）
            is_checkpoint: 是否为检查点快照

        Returns:
            存储决策
        """
        # 检查点直接归档（系统公理二约束）
        if is_checkpoint:
            return StorageDecision(
                tier=StorageTier.FROZEN,
                access_pattern=DataAccessPattern.ARCHIVED,
                compression_needed=True,
            )

        # 高频访问 → HOT
        if access_frequency >= self.FREQUENT_THRESHOLD:
            return StorageDecision(
                tier=StorageTier.HOT,
                access_pattern=DataAccessPattern.FREQUENT,
                ttl_hours=24,  # L1 缓存 TTL
            )

        # 中频访问 → WARM
        if access_frequency >= self.OCCASIONAL_THRESHOLD:
            return StorageDecision(
                tier=StorageTier.WARM,
                access_pattern=DataAccessPattern.OCCASIONAL,
            )

        # 低频访问 → COLD
        if access_frequency >= self.RARE_THRESHOLD:
            return StorageDecision(
                tier=StorageTier.COLD,
                access_pattern=DataAccessPattern.RARE,
                compression_needed=content_size > 10000,  # >10KB 启用压缩
            )

        # 很久未访问 → FROZEN
        return StorageDecision(
            tier=StorageTier.FROZEN,
            access_pattern=DataAccessPattern.ARCHIVED,
            compression_needed=True,
        )
```

---

## 5. 基础设施层设计

### 5.1 统一存储工厂

```python
# src/infrastructure/storage/unified_storage_factory.py

"""统一存储工厂。

根据配置创建各层存储适配器，并组装 UnifiedStorageGateway。
遵循六边形架构：工厂在 Infrastructure 层，创建 Application 层需要的对象。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.services.unified_storage_gateway import UnifiedStorageGateway
    from src.infrastructure.config.memory import MemoryConfig
    from src.infrastructure.config.redis import RedisConfig
    from src.infrastructure.config.postgresql import PostgreSQLConfig


class UnifiedStorageFactory:
    """统一存储工厂。

    负责创建各层存储适配器并组装网关。

    设计原则：
    - 工厂在 Infrastructure 层
    - 创建 Application 层需要的 UnifiedStorageGateway
    - 各层 Adapter 实现 Domain Port 接口
    """

    def __init__(
        self,
        memory_config: MemoryConfig,
        redis_config: RedisConfig,
        postgresql_config: PostgreSQLConfig,
        # L3-L5 配置可选
        qdrant_config=None,
        minio_config=None,
        neo4j_config=None,
    ) -> None:
        self._memory_config = memory_config
        self._redis_config = redis_config
        self._postgresql_config = postgresql_config
        self._qdrant_config = qdrant_config
        self._minio_config = minio_config
        self._neo4j_config = neo4j_config

    def create_gateway(self) -> UnifiedStorageGateway:
        """创建统一存储网关。

        Returns:
            组装好的网关实例
        """
        # L0: FileMemoryAdapter
        from src.infrastructure.storage.file_memory_adapter import FileMemoryAdapter
        l0_storage = FileMemoryAdapter(
            base_path=self._memory_config.l0_path,
        )

        # L1: RedisMemoryCache (async)
        from src.infrastructure.storage.redis.redis_memory_cache import RedisMemoryCache
        l1_cache = RedisMemoryCache(
            host=self._redis_config.host,
            port=self._redis_config.port,
            db=self._redis_config.db,
            password=self._redis_config.password,
        )

        # L2: PostgreSQL（实现 L2RdbPort）
        from src.infrastructure.storage.postgresql.repository.memory_metadata_repository import (
            PostgreSQLMemoryMetadataRepository,
        )
        l2_storage = PostgreSQLMemoryMetadataRepository(
            dsn=self._postgresql_config.dsn,
        )

        # L3-L5 可选创建
        l3_vector = None
        if self._qdrant_config:
            from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage
            l3_vector = QdrantVectorStorage(...)

        l4_object = None
        if self._minio_config:
            from src.infrastructure.storage.minio.minio_repository import MinIORepository
            l4_object = MinIORepository(...)

        l5_graph = None
        if self._neo4j_config:
            from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage
            l5_graph = Neo4jGraphStorage(...)

        # 组装网关
        from src.application.services.unified_storage_gateway import UnifiedStorageGateway
        return UnifiedStorageGateway(
            l0_storage=l0_storage,
            l1_cache=l1_cache,
            l2_storage=l2_storage,
            l3_vector=l3_vector,
            l4_object=l4_object,
            l5_graph=l5_graph,
        )
```

### 5.2 适配器实现映射

| Port 接口 | Adapter 实现 | 状态 |
|-----------|-------------|------|
| `L0StoragePort` | `FileMemoryAdapter` | ✅ 已有 |
| `L1CachePort` | `RedisMemoryCache (async)` | ✅ 已实现（重构为 async） |
| `L2RdbPort` | `PostgreSQLAdapter` | ✅ 已有（`PostgreSQLMemoryMetadataRepository`） |
| `L3VectorPort` | `QdrantVectorAdapter` | ⚠️ 需新增（包装现有 `QdrantVectorStorage`） |
| `L4ObjectPort` | `MinIOAdapter` | ⚠️ 需新增（包装现有 `MinIORepository`） |
| `L5GraphPort` | `Neo4jAdapter` | ⚠️ 需新增（包装现有 `Neo4jGraphStorage`） |

### 5.3 L1 缓存异步重构

由于 `RedisMemoryCache` 是 sync 实现，需要一步到位重构为 async：

```python
# src/infrastructure/storage/redis/redis_memory_cache.py

"""RedisMemoryCache — L1 记忆缓存（异步版）。

基于 Redis 的 L1 记忆缓存实现，所有方法均为异步。
使用 `redis.asyncio` 替代 sync `redis`。
"""

import redis.asyncio as aioredis


class RedisMemoryCache:
    """Redis 记忆缓存（异步版）。

    负责 L1 层记忆缓存的读写和失效。
    所有方法均为异步方法。
    """

    def __init__(self, redis_client: aioredis.Redis):
        self._redis = redis_client

    async def get(self, memory_type: str, owner_id: str, name: str) -> str | None:
        key = self._build_key(memory_type, owner_id, name)
        value = await self._redis.get(key)
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else value

    async def set(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
        content: str,
        ttl: int | None = None,
    ) -> None:
        key = self._build_key(memory_type, owner_id, name)
        effective_ttl = ttl if ttl is not None else self._generate_ttl()
        await self._redis.setex(key, effective_ttl, content)

    async def delete(self, memory_type: str, owner_id: str, name: str) -> None:
        key = self._build_key(memory_type, owner_id, name)
        await self._redis.delete(key)

    async def invalidate_pattern(self, memory_type: str, owner_id: str) -> None:
        pattern = self._build_pattern(memory_type, owner_id)
        keys = [key async for key in self._redis.scan_iter(match=pattern)]
        if keys:
            await self._redis.delete(*keys)

    def _build_key(self, memory_type: str, owner_id: str, name: str) -> str:
        if memory_type == "group":
            return f"memory:group:{owner_id}:{name}"
        return f"memory:user:{owner_id}:{name}"

    def _build_pattern(self, memory_type: str, owner_id: str) -> str:
        if memory_type == "group":
            return f"memory:group:{owner_id}:*"
        return f"memory:user:{owner_id}:*"

    def _generate_ttl(self) -> int:
        import random
        return 86400 + random.randint(0, 21600)
```

---

## 6. 六边形架构验证

### 6.1 依赖方向检查

```
Domain Layer（零外部依赖）
├── L0StoragePort        ← abc.ABC
├── L1CachePort          ← abc.ABC
├── L2RdbPort       ← abc.ABC, datetime, typing, uuid
├── L3VectorPort         ← abc.ABC, typing
├── L4ObjectPort         ← abc.ABC, typing
├── L5GraphPort          ← abc.ABC, typing
├── StoragePolicyService   ← 纯业务逻辑
└── UnifiedStoragePort  ← abc.ABC, typing, StorageLayer/StorageTier

Application Layer（依赖 Domain Port）
└── UnifiedStorageGateway
    ├── 依赖 L0StoragePort（Domain）
    ├── 依赖 L1CachePort（Domain）
    ├── 依赖 L2RdbPort（Domain）
    └── 不直接依赖 Infrastructure

Infrastructure Layer（实现 Domain Port）
├── FileMemoryAdapter    → L0StoragePort
├── RedisMemoryCache (async) → L1CachePort
├── PostgreSQLAdapter    → L2RdbPort
├── QdrantVectorAdapter  → L3VectorPort
├── MinIOAdapter         → L4ObjectPort
└── Neo4jAdapter         → L5GraphPort
```

### 6.2 检查清单

| 检查项 | 约束 | 状态 |
|--------|------|------|
| Domain 层不导入 Infrastructure | 零外部依赖 | ✅ |
| Domain 层不导入 Application | 单向依赖 | ✅ |
| Application 层依赖 Domain Port | 依赖倒置 | ✅ |
| Infrastructure 实现 Domain Port | 接口实现 | ✅ |
| Application 不直接创建 Infrastructure | 依赖注入 | ✅ |
| 向后兼容现有调用方 | 保留现有接口 | ✅ |

---

## 7. 验收标准（来自 architecture.md §11.2.11）

| 指标 | 标准 | 对应设计 |
|------|------|----------|
| L0 MEMORY.md 行数 | ≤200 行，超出自动截断 | `L0StoragePort.update_index(max_lines=200)` |
| L0→L2 写入延迟 | <100ms | L2 异步写入，不阻塞 L0 |
| L0→L1 缓存命中率 | >80%（高频记忆） | `StoragePolicyService` 层级决策 |
| L0→L3 向量检索 P95 | <300ms（内容>500 tokens） | L3 可选启用 |
| L0→L4 Checkpoint | 必须先归档再压缩（系统公理二） | `StoragePolicyService.is_checkpoint` |
| L1 压缩率 | ≥70%（用户输入≤500字→≥150字） | 已有实现 |
| 端到端检索 P95 | <800ms | 设计目标 |

---

## 8. 迁移路径

### Phase 1: 定义 Port 接口（不破坏现有代码）

1. 新增 `src/domain/ports/l1_cache.py` → `L1CachePort`
2. 新增 `src/domain/ports/l3_vector.py` → `L3VectorPort`
3. 新增 `src/domain/ports/l4_object.py` → `L4ObjectPort`
4. 新增 `src/domain/ports/l5_graph.py` → `L5GraphPort`
5. 新增 `src/domain/ports/unified_storage.py` → `UnifiedStoragePort`
6. 新增 `src/domain/ports/storage_enums.py` → `StorageLayer`, `StorageTier`

### Phase 2: 实现 Adapter / 直接重构（不破坏现有代码）

1. `RedisMemoryCache` 一步到位重构为 async（使用 `redis.asyncio`）
2. `QdrantVectorAdapter` 实现 `L3VectorPort`（包装现有 `QdrantVectorStorage`）
3. `MinIOAdapter` 实现 `L4ObjectPort`（包装现有 `MinIORepository`）
4. `Neo4jAdapter` 实现 `L5GraphPort`（包装现有 `Neo4jGraphStorage`）

### Phase 3: 创建网关（不破坏现有代码）

1. 新增 `UnifiedStorageGateway`
2. 新增 `UnifiedStorageFactory`
3. 新增 `StoragePolicyService`
4. 旧代码通过 `SixLayerStorageCoordinator` 继续使用

### Phase 4: 逐步迁移

1. 新代码使用 `UnifiedStorageGateway`
2. 旧代码通过 `SixLayerStorageCoordinator` 继续使用
3. 稳定后废弃 `SixLayerStorageCoordinator`（仅测试用例使用）

---

## 9. 关键设计决策记录

### ADR-001: 是否需要统一存储网关？

**问题**: 是否需要 `UnifiedStorageGateway` 还是直接使用各层存储？

**决策**: 需要统一网关
**理由**:
- 调用方不应关注存储细节
- 网关提供统一的读写抽象
- 符合 architecture.md §11.2.9 L0 驱动协同机制

### ADR-002: Adapter 包装 vs 直接实现

**问题**: 现有实现（如 `RedisMemoryCache`）没有 Port 接口，如何处理？

**决策**: 直接重构为 async（针对 L1）
**理由**:
- `RedisMemoryCache` 是 L1 核心组件，使用广泛
- 项目趋势是从 sync Redis 向 async 演进（已有 `RedisSessionStorage`、`RedisSemanticCache` 等 async 实现）
- 一步到位重构为 async，与 L1CachePort 接口一致，无需适配器层

### ADR-003: L1/L3/L4/L5 是否必须实现？

**问题**: SixLayerStorageCoordinator 中 L3-L5 是 TODO 状态，是否必须实现？

**决策**: 可选实现
**理由**:
- L0-L2 是核心（真相源 + 缓存 + 元数据）
- L3-L5 是扩展（向量检索、对象存储、图谱）
- 通过 Optional 参数支持可选实现

---

## 六、关键问题汇总

| 优先级 | 问题 | 位置 | 状态 |
|--------|------|------|------|
| **P0** | ~~L2RdbPort 缺少 `get_content()` 方法，与 `read()` 逻辑矛盾~~ | §3.4 | ✅ 已修复：直接复用现有 Protocol |
| **P0** | ~~save() 直接调用 L1/L2/L3，违反 §11.2.9 事件驱动架构~~ | §4.1 | ✅ 已修复：save() 只写 L0 + 发布 Outbox |
| **P0** | ~~read() 遗漏 L2 RBAC 校验和 L0 真相源校验~~ | §4.1 | ✅ 已修复：read() 实现 L1→L2→L0 完整流程 |
| **P1** | `RedisMemoryCache` 是 sync 实现，与 async Port 不兼容 | §3.3 / §5.1 | 决策：一步到位重构为 async |
| **P1** | `UnifiedStorageGateway` 构造函数参数过多（6+2） | §4.1 | 待修复：使用 `StorageConfig` 配置对象 |
| **P1** | L3/L4/L5 Port 接口与实际实现语义不兼容 | §3.5-3.7 | 待修复：重新设计接口适配现有实现 |
| **P2** | `StoragePolicyService` 阈值硬编码 | §4.2 | 待修复：支持配置注入 |
| **P2** | ~~L2RdbPort 与现有 `MemoryMetadataRepositoryProtocol` 重复~~ | §3.4 | ✅ 已修复：直接使用现有 Protocol |

### P1 问题决策：RedisMemoryCache 一步到位重构为异步

**决策**：一步到位将 `RedisMemoryCache` 重构为 async 实现，名字保持不变。

**变更要点**：
- `import redis` → `import redis.asyncio as aioredis`
- `redis.Redis` → `aioredis.Redis`
- 所有方法改为 `async def`，使用 `await` 调用 Redis 操作
- `keys()` 替换为 `async for ... scan_iter()` 避免阻塞

**架构合理性**：
- 与 L2-L5 Port 保持一致（全 async）
- 符合项目从 sync Redis 向 async 演进的趋势
- UnifiedStorageGateway 作为 async 网关，自然调用 async Port

### 本轮 P0 修复说明

**1. save() 事件驱动架构修复**
- 修改前：save() 直接同步调用 `self._l1.set()`、`self._l2.save_metadata()`、`self._l3.upsert()`
- 修改后：save() 只做 L0 写入 + 发布 MemoryChanged 事件到 Outbox
- 各层更新由 MemoryChangedListener 异步执行（符合 §11.2.9）

**2. L2 Port 接口重复修复**
- 删除 `L2RdbPort` 新接口定义
- 直接复用现有 `MemoryMetadataRepositoryProtocol` + `MemoryChangeHistoryRepositoryProtocol`
- UnifiedStorageGateway 构造函数使用这两个 Protocol

**3. read() 完整流程修复**
- 修改前：只实现 L1 → L0 二层读取
- 修改后：实现 L1 → L2(RBAC校验) → L0 完整流程
- 增加 L0 真相源校验（缓存命中后仍需 L0 校验）

---

**文档状态**: 第二轮审查修复完成
**下一步**: Phase 1 实现（定义 Port 接口 + 事件驱动改造 + L3/L4/L5 接口重新设计）
