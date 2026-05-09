# SISYS 统一存储架构设计文档

**版本:** v1.0
**日期:** 2026-05-07
**作者:** Claude Code (宗师级架构设计)
**状态:** 设计中

---

## 1. 现状分析

### 1.1 现有存储实现概览

| 层级 | 存储类型 | Port 接口 | 基础设施实现 | 状态 |
|------|----------|-----------|-------------|------|
| L0 | 文件系统 | `L0StoragePort` | `FileMemoryAdapter` | ✅ 已实现 |
| L0索引 | 文件系统 | `IndexManagerPort` | `MemoryIndex` | ✅ 已实现 |
| L1 | Redis缓存 | ❌ 无接口 | `RedisMemoryCache` | ⚠️ 违反六边形 |
| L1语义 | Redis | ❌ 无接口 | `RedisSemanticCache` | ⚠️ 违反六边形 |
| L2 | PostgreSQL | ✅ `L2MetadataRepositoryProtocol` | `PostgreSQLMemoryMetadataRepository` | ✅ 已实现 |
| L2历史 | PostgreSQL | ✅ `L2ChangeHistoryRepositoryProtocol` | `PostgreSQLMemoryChangeHistoryRepository` | ✅ 已实现 |
| L3 | Qdrant | ✅ `VectorStorage` (Protocol) | `QdrantVectorStorage` | ✅ 已实现 |
| L4 | MinIO | ✅ `ObjectStorageRepository` | `MinIORepository` | ✅ 已实现 |
| L5 | Neo4j | ✅ `GraphStorage`, `GraphManager` | `Neo4jGraphStorage`, `Neo4jGraphManager` | ✅ 已实现 |
| 会话 | Redis | ✅ `SessionStorage` (Protocol) | `RedisSessionStorage` | ✅ 已实现 |
| 快照 | Redis | ❌ 无接口 | `RedisSnapshotStore` | ⚠️ 违反六边形 |

### 1.2 核心问题

#### 问题 1: SixLayerStorageCoordinator 违反六边形架构

```python
# ❌ 当前实现：Application 层直接依赖 Infrastructure 具体类
class SixLayerStorageCoordinator:
    def __init__(
        self,
        l1_cache: RedisMemoryCache,           # Infrastructure 具体类
        l3_vector_store: QdrantVectorStorage, # Infrastructure 具体类
        l4_object_store: MinIORepository,      # Infrastructure 具体类
        l5_graph_store: Neo4jGraphStorage,     # Infrastructure 具体类
    ):
```

#### 问题 2: L1/L1语义/快照层缺少 Port 接口

这三个存储没有定义 Domain Port 接口，直接使用具体实现，违反依赖倒置原则。

#### 问题 3: L3-L5 在协调器中未实现

```python
def _save_to_l3(...):  # TODO: L3 向量存储由 Story 6.3 实现
def _save_to_l4(...):  # TODO: L4 对象存储由 Story 6.3 实现
def _save_to_l5(...):  # TODO: L5 知识图谱由后续 LLM 集成 Story 实现
```

#### 问题 4: L2 读取方法未实现

```python
def _read_from_l2(self, memory_id: str) -> str | None:
    if self._l2_repository is None:
        return None
    return None  # 硬编码返回 None
```

---

## 2. 统一存储架构设计

### 2.1 设计目标

1. **六边形架构纯正**: 所有存储通过 Port 接口解耦
2. **统一入口**: 提供统一的 Storage Gateway
3. **可测试性**: 每个存储层可独立测试和替换
4. **可扩展性**: 新增存储层不影响现有代码
5. **异步优先**: 全面支持 async/await

### 2.2 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              UnifiedStorageGateway                    │   │
│  │         (统一存储入口，编排各层存储)                   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Domain Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ L0Port   │  │ L1Port   │  │ L2Port   │  │ L3Port   │   │
│  │ L4Port   │  │ L5Port   │  │CachePort │  │GraphPort │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              StorageCoordinatorService                 │   │
│  │         (领域服务，存储策略决策编排)                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  File    │  │  Redis   │  │ Postgre  │  │  Qdrant  │   │
│  │ Adapter  │  │  Cache   │  │   SQL    │  │ VectorSt │   │
│  │          │  │ Adapter  │  │  Adapter │  │ Adapter  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐                                │
│  │  MinIO   │  │  Neo4j   │                                │
│  │ Adapter  │  │ Adapter  │                                │
│  └──────────┘  └──────────┘                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Domain 层 Port 接口设计

### 3.1 统一存储策略接口

```python
# src/domain/ports/unified_storage.py

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from src.domain.value_objects.memory.py import Memory

class StorageLayer(Enum):
    """存储层级枚举。"""
    L0_FILE = "l0_file"           # 文件系统
    L1_CACHE = "l1_cache"         # Redis 缓存
    L2_SQL = "l2_sql"             # PostgreSQL
    L3_VECTOR = "l3_vector"       # Qdrant 向量
    L4_OBJECT = "l4_object"        # MinIO 对象
    L5_GRAPH = "l5_graph"         # Neo4j 图


class StorageTier(Enum):
    """存储层级策略。"""
    HOT = "hot"      # 热数据: L1 缓存优先
    WARM = "warm"   # 温数据: L2 SQL
    COLD = "cold"   # 冷数据: L4 对象存储
    FROZEN = "frozen"  # 冻结数据: L5 图关系


class UnifiedStoragePort(ABC):
    """统一存储入口接口。

    定义存储系统的统一操作契约。
    """

    @abstractmethod
    async def save(
        self,
        memory_id: str,
        content: str,
        layer: StorageLayer,
        memory_type: str,
        owner_id: str,
        name: str,
        tier: StorageTier = StorageTier.WARM,
    ) -> dict[str, bool]:
        """保存记忆到指定层。

        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            layer: 目标存储层
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
        layer: StorageLayer,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> str | None:
        """从指定层读取记忆。

        Args:
            memory_id: 记忆 ID
            layer: 源存储层
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称

        Returns:
            记忆内容，不存在返回 None
        """
        pass

    @abstractmethod
    async def delete(
        self,
        memory_id: str,
        layer: StorageLayer | None = None,  # None 表示删除所有层
        memory_type: str | None = None,
        owner_id: str | None = None,
        name: str | None = None,
    ) -> dict[str, bool]:
        """删除记忆。

        Args:
            memory_id: 记忆 ID
            layer: 目标层，None 表示所有层
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称

        Returns:
            各层删除结果 {layer: success}
        """
        pass

    @abstractmethod
    async def exists(
        self,
        memory_id: str,
        layer: StorageLayer,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> bool:
        """检查记忆是否存在。

        Args:
            memory_id: 记忆 ID
            layer: 存储层
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称

        Returns:
            是否存在
        """
        pass

    @abstractmethod
    async def get_layer_status(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str | None = None,
        name: str | None = None,
    ) -> dict[StorageLayer, bool]:
        """获取各层存储状态。

        Returns:
            各层是否存在 {layer: exists}
        """
        pass
```

### 3.2 各层存储 Port 接口

#### L1 缓存 Port (新增)

```python
# src/domain/ports/l1_cache.py

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class L1CachePort(ABC):
    """L1 缓存层接口。

    定义缓存的读写和失效操作。
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
            ttl: TTL 秒数，None 使用默认

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

#### L3 向量存储 Port (增强现有)

```python
# src/domain/ports/vector_storage.py

from abc import ABC, abstractmethod
from typing import Any

class VectorStoragePort(ABC):
    """向量存储层接口。

    定义向量存储的读写操作。
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
            metadata: 元数据

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
            搜索结果列表
        """
        pass

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """删除向量。

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def get(self, memory_id: str) -> dict | None:
        """获取向量数据。

        Returns:
            向量数据，不存在返回 None
        """
        pass
```

#### L4 对象存储 Port (增强现有)

```python
# src/domain/ports/object_storage.py

from abc import ABC, abstractmethod
from typing import AsyncIterator

class ObjectStoragePort(ABC):
    """对象存储层接口。

    定义对象存储的读写操作。
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
            对象版本 ID
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
        """删除对象。

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
```

#### L5 图存储 Port (增强现有)

```python
# src/domain/ports/graph_storage.py

from abc import ABC, abstractmethod
from typing import Any

class GraphStoragePort(ABC):
    """图存储层接口。

    定义知识图谱的读写操作。
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
        source_id: str,
        target_id: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """创建关系边。

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    async def get_entity(self, memory_id: str) -> dict | None:
        """获取实体。

        Returns:
            实体数据，不存在返回 None
        """
        pass

    @abstractmethod
    async def find_related(
        self,
        memory_id: str,
        max_depth: int = 2,
    ) -> list[dict]:
        """查找关联实体。

        Args:
            memory_id: 起始实体 ID
            max_depth: 最大遍历深度

        Returns:
            关联实体列表
        """
        pass

    @abstractmethod
    async def delete_entity(self, memory_id: str) -> bool:
        """删除实体及关联边。

        Returns:
            是否成功
        """
        pass
```

---

## 4. 统一存储网关设计

### 4.1 UnifiedStorageGateway (应用层)

```python
# src/application/services/unified_storage_gateway.py

"""UnifiedStorageGateway — 统一存储网关。

提供 L0-L5 六层存储的统一入口，根据存储策略自动编排各层存储。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.ports.unified_storage import (
    StorageLayer,
    StorageTier,
    UnifiedStoragePort,
)
from src.domain.ports.l1_cache import L1CachePort

if TYPE_CHECKING:
    from src.domain.ports.l0_storage import L0StoragePort
    from src.domain.ports.l2_storage import L2StoragePort
    from src.domain.ports.vector_storage import VectorStoragePort
    from src.domain.ports.object_storage import ObjectStoragePort
    from src.domain.ports.graph_storage import GraphStoragePort


class UnifiedStorageGateway:
    """统一存储网关。

    职责：
    - 提供 L0-L5 六层存储的统一入口
    - 根据存储策略自动决定数据 placement
    - 协调各层存储的读写操作
    - 处理层间数据流动（缓存失效、向量更新等）

    设计原则：
    - 应用层编排，不包含业务逻辑
    - 依赖 Domain Port 接口，不直接依赖 Infrastructure
    """

    def __init__(
        self,
        l0_storage: L0StoragePort,
        l1_cache: L1CachePort,
        l2_storage: L2StoragePort,
        l3_vector: VectorStoragePort | None = None,
        l4_object: ObjectStoragePort | None = None,
        l5_graph: GraphStoragePort | None = None,
    ) -> None:
        """初始化统一存储网关。

        Args:
            l0_storage: L0 文件系统存储
            l1_cache: L1 Redis 缓存
            l2_storage: L2 PostgreSQL
            l3_vector: L3 向量存储
            l4_object: L4 对象存储
            l5_graph: L5 图存储
        """
        self._l0 = l0_storage
        self._l1 = l1_cache
        self._l2 = l2_storage
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

        存储策略：
        - HOT: L1 缓存优先
        - WARM: L1 + L2 + L0
        - COLD: L2 + L4
        - FROZEN: L4 + L5

        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称
            tier: 存储层级策略

        Returns:
            各层存储结果
        """
        results: dict[StorageLayer, bool] = {}

        # L1 缓存（所有热数据都写缓存）
        if tier in (StorageTier.HOT, StorageTier.WARM):
            results[StorageLayer.L1_CACHE] = await self._l1.set(
                memory_type, owner_id, name, content
            )

        # L2 SQL（温冷数据都写 SQL）
        if tier in (StorageTier.WARM, StorageTier.COLD, StorageTier.FROZEN):
            results[StorageLayer.L2_SQL] = await self._l2.save_metadata(
                memory_id, content, memory_type, owner_id, name
            )

        # L0 文件系统（温数据写 L0）
        if tier in (StorageTier.WARM,):
            results[StorageLayer.L0_FILE] = await self._l0.write(
                memory_id, memory_type, content
            )

        # L3 向量存储（需要时由调用方触发）
        # L4 对象存储（冷数据触发）
        # L5 图存储（冻结数据触发）

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

        读取策略：
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
        # L1 缓存查找
        if prefer_cache:
            content = await self._l1.get(memory_type, owner_id, name)
            if content is not None:
                return content

        # L2 SQL 查找
        content = await self._l2.get_content(memory_id)
        if content is not None:
            # 回填 L1 缓存
            if prefer_cache:
                await self._l1.set(memory_type, owner_id, name, content)
            return content

        # L0 文件系统查找
        content = await self._l0.read(memory_id, memory_type)
        if content is not None:
            # 回填 L1 缓存
            if prefer_cache:
                await self._l1.set(memory_type, owner_id, name, content)
            return content

        return None

    async def invalidate(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> None:
        """失效缓存。

        Args:
            memory_id: 记忆 ID
            memory_type: 记忆类型
            owner_id: 所有者 ID
            name: 记忆名称
        """
        await self._l1.delete(memory_type, owner_id, name)

    async def get_layer_status(
        self,
        memory_id: str,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> dict[StorageLayer, bool]:
        """获取各层存储状态。

        Returns:
            各层是否存在
        """
        return {
            StorageLayer.L0_FILE: await self._l0.exists(memory_id, memory_type),
            StorageLayer.L1_CACHE: await self._l1.get(memory_type, owner_id, name) is not None,
            StorageLayer.L2_SQL: await self._l2.exists(memory_id),
            # L3/L4/L5 类似...
        }
```

### 4.2 StorageTierStrategy (存储策略)

```python
# src/domain/services/storage_tier_strategy.py

"""存储层级策略服务。

根据数据特征和业务规则决定数据的存储层级。
"""

from dataclasses import dataclass
from enum import Enum

from src.domain.ports.unified_storage import StorageTier


class DataAccessPattern(Enum):
    """数据访问模式。"""
    FREQUENT = "frequent"      # 高频访问
    OCCASIONAL = "occasional"  # 偶尔访问
    RARE = "rare"             # 很少访问
    ARCHIVED = "archived"     # 归档


@dataclass
class StorageDecision:
    """存储决策结果。"""
    tier: StorageTier
    access_pattern: DataAccessPattern
    ttl_hours: int | None = None
    compression_needed: bool = False


class StorageTierStrategy:
    """存储层级策略。

    根据数据特征决定存储层级。
    """

    def decide_tier(
        self,
        access_frequency: int,  # 过去 7 天访问次数
        content_size: int,     # 内容大小（字节）
        is_checkpoint: bool = False,
    ) -> StorageDecision:
        """决定存储层级。

        Args:
            access_frequency: 访问频率
            content_size: 内容大小
            is_checkpoint: 是否为检查点快照

        Returns:
            存储决策
        """
        # 检查点直接归档
        if is_checkpoint:
            return StorageDecision(
                tier=StorageTier.FROZEN,
                access_pattern=DataAccessPattern.ARCHIVED,
                compression_needed=True,
            )

        # 高频访问 → HOT
        if access_frequency >= 100:
            return StorageDecision(
                tier=StorageTier.HOT,
                access_pattern=DataAccessPattern.FREQUENT,
                ttl_hours=24,
            )

        # 中频访问 → WARM
        if access_frequency >= 10:
            return StorageDecision(
                tier=StorageTier.WARM,
                access_pattern=DataAccessPattern.OCCASIONAL,
            )

        # 低频访问 → COLD
        if access_frequency >= 1:
            return StorageDecision(
                tier=StorageTier.COLD,
                access_pattern=DataAccessPattern.RARE,
                compression_needed=content_size > 10000,
            )

        # 很久未访问 → FROZEN
        return StorageDecision(
            tier=StorageTier.FROZEN,
            access_pattern=DataAccessPattern.ARCHIVED,
            compression_needed=True,
        )
```

---

## 5. 工厂模式设计

### 5.1 统一存储工厂

```python
# src/infrastructure/storage/unified_storage_factory.py

"""统一存储工厂。

根据配置创建各层存储适配器，并组装 UnifiedStorageGateway。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.services.unified_storage_gateway import UnifiedStorageGateway
    from src.infrastructure.config.memory import MemoryConfig
    from src.infrastructure.config.redis import RedisConfig


class UnifiedStorageFactory:
    """统一存储工厂。

    负责创建各层存储适配器并组装网关。
    """

    def __init__(
        self,
        memory_config: MemoryConfig,
        redis_config: RedisConfig,
        # ... 其他配置
    ) -> None:
        self._memory_config = memory_config
        self._redis_config = redis_config

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

        # L1: RedisMemoryCache（需要新增 Port）
        from src.infrastructure.storage.redis.redis_memory_cache import RedisMemoryCache
        l1_cache = RedisMemoryCache(
            host=self._redis_config.host,
            port=self._redis_config.port,
            db=self._redis_config.db,
            password=self._redis_config.password,
        )

        # L2: PostgreSQL（通过 Repository Pattern）
        from src.infrastructure.storage.postgresql.repository.memory_metadata_repository import (
            PostgreSQLMemoryMetadataRepository,
        )
        l2_storage = PostgreSQLMemoryMetadataRepository(...)

        # L3-L5 可选创建

        return UnifiedStorageGateway(
            l0_storage=l0_storage,
            l1_cache=l1_cache,
            l2_storage=l2_storage,
            # L3-L5 ...
        )
```

---

## 6. 架构约束遵守检查

### 6.1 六边形架构约束

```
┌──────────────────────────────────────────────────────────────┐
│                     Domain Layer                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  UnifiedStoragePort      ← 抽象接口（无外部依赖）     │    │
│  │  L1CachePort            ← 抽象接口（无外部依赖）     │    │
│  │  L2StoragePort          ← 抽象接口（无外部依赖）     │    │
│  │  VectorStoragePort      ← 抽象接口（无外部依赖）     │    │
│  │  ObjectStoragePort      ← 抽象接口（无外部依赖）     │    │
│  │  GraphStoragePort       ← 抽象接口（无外部依赖）     │    │
│  └────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  StorageTierStrategy    ← 领域服务（纯业务逻辑）    │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
                              │
                              │ 依赖接口
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                   Application Layer                           │
│  ┌────────────────────────────────────────────────────┐    │
│  │  UnifiedStorageGateway  ← 应用编排（依赖 Domain）   │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
                              │
                              │ 依赖注入
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │  FileMemoryAdapter      → 实现 L0StoragePort       │    │
│  │  RedisMemoryCache       → 实现 L1CachePort          │    │
│  │  PostgreSQL...          → 实现 L2StoragePort        │    │
│  │  QdrantVectorStorage    → 实现 VectorStoragePort    │    │
│  │  MinIORepository        → 实现 ObjectStoragePort    │    │
│  │  Neo4jGraphStorage      → 实现 GraphStoragePort     │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 依赖方向检查清单

| 检查项 | 约束 | 状态 |
|--------|------|------|
| Domain 层不导入 Infrastructure | 零外部依赖 | ✅ |
| Domain 层不导入 Application | 单向依赖 | ✅ |
| Application 层依赖 Domain Port | 依赖倒置 | ✅ |
| Infrastructure 实现 Domain Port | 接口实现 | ✅ |
| Application 不直接创建 Infrastructure | 依赖注入 | ✅ |
| Infrastructure 可替换 | 策略模式 | ✅ |

---

## 7. 迁移路径

### 7.1 Phase 1: 定义 Port 接口（不破坏现有代码）

1. 新增 `L1CachePort` 接口
2. 新增 `VectorStoragePort` 接口（从现有 Protocol 改造）
3. 新增 `ObjectStoragePort` 接口（从现有接口改造）
4. 新增 `GraphStoragePort` 接口（从现有接口改造）

### 7.2 Phase 2: 实现适配器（不破坏现有代码）

1. `RedisMemoryCacheAdapter` 实现 `L1CachePort`
2. `QdrantVectorStorageAdapter` 实现 `VectorStoragePort`
3. `MinIOAdapter` 实现 `ObjectStoragePort`
4. `Neo4jAdapter` 实现 `GraphStoragePort`

### 7.3 Phase 3: 创建网关（不破坏现有代码）

1. 新增 `UnifiedStorageGateway`
2. 新增 `UnifiedStorageFactory`
3. 保留 `SixLayerStorageCoordinator` 向后兼容

### 7.4 Phase 4: 逐步迁移

1. 新代码使用 `UnifiedStorageGateway`
2. 旧代码通过适配器继续使用 `SixLayerStorageCoordinator`
3. 稳定后废弃 `SixLayerStorageCoordinator`

---

## 8. 测试策略

### 8.1 单元测试

- 每个 Port 接口有对应 Mock 实现
- `StorageTierStrategy` 可独立测试
- `UnifiedStorageGateway` 使用 Mock Port 测试

### 8.2 集成测试

- 每个 Infrastructure 适配器独立集成测试
- 端到端存储流程测试
- 层间数据一致性测试

### 8.3 性能测试

- 各层存储性能基准
- 跨层读取延迟 P95
- 缓存命中率监控

---

## 9. 关键设计决策记录

### ADR-001: 是否需要统一存储网关？

**问题**: 是否需要 `UnifiedStorageGateway` 还是直接使用各层存储？

**选项 A**: 统一网关（当前设计）
- 优点: 统一入口，策略集中
- 缺点: 可能成为瓶颈

**选项 B**: 直接使用各层存储
- 优点: 简单直接
- 缺点: 调用方需要了解各层差异

**决策**: 选项 A
**理由**: 调用方不应关注存储细节，网关提供统一抽象

### ADR-002: L1 缓存是否需要 Port 接口？

**问题**: `RedisMemoryCache` 是否需要抽象为 Port？

**选项 A**: 需要抽象
- 优点: 可替换实现（六边形正确）
- 缺点: 增加一层间接

**选项 B**: 不需要抽象
- 优点: 简单
- 缺点: 违反依赖倒置

**决策**: 选项 A
**理由**: 所有外部依赖都应通过 Port 解耦

---

**文档状态**: 草稿
**下一步**: 用户评审后确定架构决策
