# SISYS L3 向量存储层重构设计方案

**版本:** v8.0
**日期:** 2026-05-13
**状态:** 设计阶段（代码未实现）
**基于:** architecture.md §11.1 L3 向量存储设计 + sisys-uni-storage-design.md
**修订:** 基于5轮代码审查的系统性修正 + 代码验证

---

## 一、现状分析

### 1.1 当前架构

```
src/domain/ports/
├── l3_vector.py              # L3VectorPort（Protocol，定义向量基础操作）
└── storage_enums.py          # StorageLayer 枚举

src/application/ports/
└── semantic_cache.py          # SemanticCache（Protocol，位于应用层）⚠️ 位置错误

src/infrastructure/storage/
├── qdrant/
│   ├── vector_storage.py     # QdrantVectorStorage（功能完整）
│   ├── collection_manager.py  # QdrantCollectionManager（完整实现 Collection 管理）
│   ├── qdrant_vector_adapter.py  # QdrantVectorAdapter → L3VectorPort ⚠️ 缺少 Collection 方法
│   └── models.py             # VectorPoint, SparseVector
└── redis/
    └── semantic_cache.py     # RedisSemanticCache（实现 SemanticCache Protocol）

src/application/services/
└── unified_storage_gateway.py # UnifiedStorageGateway ⚠️ self._l3 未使用

src/composition_root.py       # 端口注册（l3_vector 未注册）
```

### 1.2 当前接口定义

| 接口 | 位置 | 方法签名 | 状态 |
|------|------|----------|------|
| `L3VectorPort` | `src/domain/ports/l3_vector.py` | 9 个方法 | ✅ Protocol 定义完整 |
| `SemanticCache` | `src/application/ports/semantic_cache.py` | `get()`, `set()`, `invalidate()` | ⚠️ 位于应用层 |
| `QdrantVectorStorage` | `src/infrastructure/storage/qdrant/vector_storage.py` | 向量 CRUD + 检索 | ✅ 功能完整 |
| `QdrantCollectionManager` | `src/infrastructure/storage/qdrant/collection_manager.py` | Collection CRUD | ✅ 完整实现 |
| `QdrantVectorAdapter` | `src/infrastructure/storage/qdrant/qdrant_vector_adapter.py` | 实现 L3VectorPort（缺 4 个方法） | ⚠️ 不完整 |
| `RedisSemanticCache` | `src/infrastructure/storage/redis/semantic_cache.py` | 实现 SemanticCache | ✅ 完整 |

### 1.3 问题清单（P0-P2）

#### P0 问题（必须修复）

| ID | 问题 | 位置 | 影响 |
|----|------|------|------|
| P0-1 | `QdrantVectorAdapter` 缺少 `create_collection`、`delete_collection`、`collection_exists`、`list_collections` 方法 | `qdrant_vector_adapter.py` | 无法通过 Port 接口管理 Collection |
| P0-2 | L3VectorPort 未在 `composition_root.py` 注册 | `composition_root.py` | 无法通过依赖注入使用 |
| P0-3 | `UnifiedStorageGateway` 中 `self._l3` 存储但从未使用 | `unified_storage_gateway.py:77` | L3 功能完全虚设 |
| P0-4 | `search_sparse` 异常被吞掉 (`except Exception: return []`) | `vector_storage.py:200` | 无法区分"无结果"和"错误" |

#### P1 问题（应该修复）

| ID | 问题 | 位置 | 影响 |
|----|------|------|------|
| P1-1 | `L3VectorPort.create_collection` 参数与 `QdrantCollectionManager` 不一致 | `l3_vector.py` vs `collection_manager.py` | 参数名 `collection` vs `name`，类型 `vector_params` vs `distance` |
| P1-2 | `QdrantCollectionManager` 已完整实现 Collection 管理，但 `QdrantVectorAdapter` 未委托给它 | `qdrant_vector_adapter.py` | 代码重复，违反 DRY |
| P1-3 | `SemanticCache` 新接口 (`get_or_compute`) 与旧接口 (`get`/`set`) 语义不兼容 | `semantic_cache.py` | 向后兼容方案不可行 |
| P1-4 | `arch-appendix.md` 引用无效 API `OptimizerConfig` | `arch-appendix.md` | 文档与 SDK 不符 |
| P1-5 | 6个 Redis adapter 各自创建独立连接池 | `redis/*.py` | 连接数 = N × max_connections，RedisPoolProvider 设计文档存在但代码未实现 |

#### P2 问题（建议修复）

| ID | 问题 | 位置 | 影响 |
|----|------|------|------|
| P2-1 | `create_collection` 实现使用 `**kwargs` 传递配置 | `collection_manager.py:36` | 接口不够显式 |
| P2-2 | 缺少六边形架构验证测试 | `tests/` | 无法验证架构原则 |
| P2-3 | `SemanticCachePort` 接口文档未创建 | `src/domain/ports/semantic_cache.py` | 设计尚未实现 |

### 1.4 根因分析

```
架构问题根因：

Domain Layer
├── L3VectorPort（定义完整）
└── SemanticCache（位于错误层次）

Infrastructure Layer
├── QdrantVectorStorage（功能完整，但无 Port 实现）
├── QdrantCollectionManager（完整实现 Collection 管理）
├── QdrantVectorAdapter（透传层，缺少 Collection 方法）
└── RedisSemanticCache（向后兼容）

问题：
1. QdrantVectorAdapter 缺少 4 个 Collection 管理方法（接口不完整）
2. QdrantCollectionManager 已完整实现，但适配器未委托
3. composition_root.py 缺少 L3 相关注册
4. UnifiedStorageGateway self._l3 未使用
```

---

## 二、目标架构

### 2.1 职责模型

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Domain Layer - L3VectorPort（统一抽象向量存储端口）     │
│                                                                  │
│  职责：定义最底层通用向量存储接口（CRUD + 检索 + Collection 管理） │
│  位置：src/domain/ports/l3_vector.py                             │
│  特点：领域层零依赖，纯抽象协议（Protocol）                       │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Domain Layer - SemanticCachePort                        │
│                                                                  │
│  职责：Qdrant 负责向量存储与语义检索，Redis 负责缓存实际响应内容（带 TTL 管理）│
│  位置：src/domain/ports/                                         │
│  注意：SemanticCachePort 是独立接口，使用组合而非继承关系来调用 L3VectorPort│
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: Infrastructure - QdrantL3VectorStore                   │
│                                                                  │
│  职责：完整实现 L3VectorPort（组合 QdrantVectorStorage +        │
│        QdrantCollectionManager）                                  │
│  位置：src/infrastructure/storage/qdrant/                         │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: Infrastructure - QdrantSemanticCacheStore             │
│                                                                  │
│  职责：实现 SemanticCachePort，使用 QdrantL3VectorStore + Redis   │
│       （双层架构：Qdrant 负责向量检索，Redis 负责内容缓存）       │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 接口定义

```python
# Layer 1: Domain 统一抽象（L3VectorPort - Protocol）
class L3VectorPort(Protocol):
    """通用向量存储接口 - 最底层抽象"""
    async def upsert_points(self, collection: str, points: list[dict]) -> bool: ...
    async def delete_points(self, collection: str, point_ids: list[str]) -> bool: ...
    async def get_point(self, collection: str, point_id: str) -> dict | None: ...
    async def search(self, collection: str, query_vector: list[float], limit: int, ...) -> list[dict]: ...
    async def search_sparse(self, collection: str, sparse_vector: dict, limit: int, ...) -> list[dict]: ...
    async def create_collection(self, name: str, vector_size: int, distance: str = "Cosine", **kwargs) -> bool: ...
    async def delete_collection(self, name: str) -> bool: ...
    async def collection_exists(self, name: str) -> bool: ...
    async def list_collections(self) -> list[str]: ...

# Layer 2: Domain 应用接口（SemanticCachePort - 独立）
class SemanticCachePort(Protocol):
    """语义缓存接口 - 应用层抽象"""
    SIMILARITY_THRESHOLD: float = 0.95
    TTL: int = 3600

    async def get_or_compute(self, query_embedding: list[float], compute_fn: Callable) -> CacheResult: ...
    async def invalidate(self, cache_key: str) -> bool: ...
    async def invalidate_by_embedding(self, query_embedding: list[float]) -> bool: ...

@dataclass
class CacheResult:
    value: dict
    hit: bool

# Layer 3: Infrastructure Qdrant 实现
class QdrantL3VectorStore(L3VectorPort):
    """Qdrant 完整向量存储实现。

    组合 QdrantVectorStorage（向量操作）和 QdrantCollectionManager（Collection 管理），
    完整实现 L3VectorPort 的 9 个方法。
    """
    def __init__(self, client_wrapper: QdrantClientWrapper):
        self._vector_storage = QdrantVectorStorage(client_wrapper)
        self._collection_manager = QdrantCollectionManager(client_wrapper)
```

### 2.3 关键设计决策

#### 决策 1: L3VectorPort 接口参数统一

**问题**: `L3VectorPort` 定义 `create_collection(collection, vector_size, vector_params)`，但 `QdrantCollectionManager` 实现 `create_collection(name, vector_size, distance, **kwargs)`

**解决方案**: 统一为 `create_collection(name, vector_size, distance = "Cosine", **kwargs)`

**理由**:
- `name` 比 `collection` 更通用（不暴露存储引擎细节）
- `distance` 参数显式声明，与 Qdrant SDK 对齐
- `**kwargs` 支持扩展参数（hnsw_config, shard_number 等）

#### 决策 2: QdrantL3VectorStore 组合策略

**问题**: `QdrantVectorAdapter` 只包装 `QdrantVectorStorage`，缺少 Collection 管理方法

**解决方案**: 新建 `QdrantL3VectorStore`，组合 `QdrantVectorStorage` + `QdrantCollectionManager`

**理由**:
- `QdrantCollectionManager` 已完整实现 Collection 管理
- 组合优于继承（Composition over Inheritance）
- 保留 `QdrantVectorAdapter` 向后兼容

#### 决策 3: SemanticCachePort 不继承 L3VectorPort

**问题**: Redis 实现使用 O(n) 扫描，无法实现 `search()` 等向量检索方法

**解决方案**: `SemanticCachePort` 保持独立接口

**理由**:
- 不同实现的底层能力不同
- 强制继承会导致接口契约无法满足

---

## 三、详细设计

### 3.1 Domain 层设计

#### 3.1.1 更新 `src/domain/ports/l3_vector.py`

**修正 `create_collection` 方法签名**:

```python
# src/domain/ports/l3_vector.py

async def create_collection(
    self,
    name: str,              # 统一使用 name
    vector_size: int,
    distance: str = "Cosine",  # 显式 distance 参数
    **kwargs,                # 扩展参数 hnsw_config, shard_number 等
) -> bool:
    """创建 Collection。

    Args:
        name: Collection 名称
        vector_size: 向量维度（bge-m3 为 1024）
        distance: 距离度量 ("Cosine" | "Euclidean" | "Dot")
        **kwargs: 扩展参数

    Returns:
        创建成功返回 True
    """
```

**注意**: 原参数名 `collection` 改为 `name`，`vector_params` 改为显式 `distance` 参数。

#### 3.1.2 新建 `src/domain/ports/semantic_cache.py`

```python
"""SemanticCachePort — 语义缓存抽象端口。

定义语义缓存能力，用于 RAG 检索加速（Story 1.4 Epic 3）。

设计原则：
- 语义相似度缓存（SIMILARITY_THRESHOLD = 0.95）
- TTL = 1h（3600s）
- query embedding 哈希作为 cache key
- 不继承 L3VectorPort（Redis 实现无法满足向量检索契约）

迁移说明（v3.0）：
- 旧接口: get(query_embedding, threshold), set(query_embedding, result, ttl)
- 新接口: get_or_compute(query_embedding, compute_fn), invalidate(cache_key)
- 旧接口已废弃，请迁移到新接口
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import Callable, Protocol


class SemanticCachePort(Protocol):
    """语义缓存端口。"""

    SIMILARITY_THRESHOLD: float = 0.95
    TTL: int = 3600

    @abstractmethod
    async def get_or_compute(
        self,
        query_embedding: list[float],
        compute_fn: Callable,
    ) -> CacheResult:
        """获取或计算缓存结果。

        Args:
            query_embedding: 查询向量嵌入
            compute_fn: 计算函数（当缓存未命中时调用）

        Returns:
            CacheResult {value, hit}
        """

    @abstractmethod
    async def invalidate(self, cache_key: str) -> bool:
        """失效缓存。

        Args:
            cache_key: 缓存键

        Returns:
            是否成功
        """


@dataclass
class CacheResult:
    """缓存结果。"""
    value: dict
    hit: bool
```

### 3.2 Infrastructure 层设计

#### 3.2.1 新建 `src/infrastructure/storage/qdrant/qdrant_l3_vector_store.py`

```python
"""QdrantL3VectorStore — L3VectorPort 的完整 Qdrant 实现。

组合 QdrantVectorStorage（向量操作）和 QdrantCollectionManager（Collection 管理），
完整实现 L3VectorPort 的 9 个方法。

职责：
- Qdrant 客户端管理
- Collection 管理（委托 QdrantCollectionManager）
- 向量点 CRUD（委托 QdrantVectorStorage）
- Dense/Sparse 检索
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Any, cast

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    NamedSparseVector,
    PointIdsList,
    PointStruct,
    Range,
)

from src.domain.ports.l3_vector import L3VectorPort
from src.infrastructure.storage.qdrant.client import QdrantClientWrapper
from src.infrastructure.storage.qdrant.collection_manager import QdrantCollectionManager
from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage

logger = logging.getLogger(__name__)


class QdrantL3VectorStore(L3VectorPort):
    """Qdrant 完整向量存储实现。

    组合 QdrantVectorStorage（向量操作）和 QdrantCollectionManager（Collection 管理），
    完整实现 L3VectorPort 的 9 个方法。
    """

    def __init__(self, client_wrapper: QdrantClientWrapper):
        """初始化 Qdrant 向量存储。

        Args:
            client_wrapper: Qdrant 客户端封装
        """
        self._vector_storage = QdrantVectorStorage(client_wrapper)
        self._collection_manager = QdrantCollectionManager(client_wrapper)

    # ===== 向量点 CRUD（委托给 QdrantVectorStorage）=====

    async def upsert_points(
        self,
        collection: str,
        points: list[dict],
    ) -> bool:
        """批量插入或更新向量点。"""
        return await self._vector_storage.upsert_points(collection, points)

    async def delete_points(
        self,
        collection: str,
        point_ids: list[str],
    ) -> bool:
        """批量删除向量点。"""
        return await self._vector_storage.delete_points(collection, point_ids)

    async def get_point(
        self,
        collection: str,
        point_id: str,
    ) -> dict | None:
        """获取单个向量点。"""
        return await self._vector_storage.get_point(collection, point_id)

    # ===== 检索（委托给 QdrantVectorStorage）=====

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        """Dense 语义检索。"""
        return await self._vector_storage.search(
            collection,
            query_vector,
            limit=limit,
            filter_payload=filter_payload,
        )

    async def search_sparse(
        self,
        collection: str,
        sparse_vector: dict,
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        """BM25 稀疏检索。

        注意：此方法会在发生错误时重新抛出异常，而非返回空列表。
        调用方应处理可能的异常。
        """
        return await self._vector_storage.search_sparse(
            collection,
            sparse_vector,
            limit=limit,
            filter_payload=filter_payload,
        )

    # ===== Collection 管理（委托给 QdrantCollectionManager）=====

    async def create_collection(
        self,
        name: str,
        vector_size: int,
        distance: str = "Cosine",
        **kwargs,
    ) -> bool:
        """创建 Collection。

        Args:
            name: Collection 名称
            vector_size: 向量维度
            distance: 距离度量 ("Cosine" | "Euclidean" | "Dot")
            **kwargs: 扩展参数（hnsw_config, shard_number 等）

        Returns:
            创建成功返回 True
        """
        return await self._collection_manager.create_collection(
            name=name,
            vector_size=vector_size,
            distance=distance,
            **kwargs,
        )

    async def delete_collection(self, name: str) -> bool:
        """删除 Collection。"""
        return await self._collection_manager.delete_collection(name)

    async def collection_exists(self, name: str) -> bool:
        """检查 Collection 是否存在。"""
        return await self._collection_manager.collection_exists(name)

    async def list_collections(self) -> list[str]:
        """列出所有 Collection。"""
        return await self._collection_manager.list_collections()

    # ===== 过滤条件构建 =====

    def _build_filter(self, filter_payload: dict | None) -> Filter | None:
        """构建 Qdrant 过滤条件。"""
        return self._vector_storage._build_filter(filter_payload)
```

#### 3.2.2 新建 `src/infrastructure/storage/qdrant/semantic_cache_store.py`

> **v6.0 修正**：原设计（纯 Qdrant）与 §九 工作流程（Qdrant+Redis 双层）矛盾，
> 已统一为双层设计：Qdrant 负责向量检索，Redis 负责缓存实际响应内容（带 TTL）。

```python
"""QdrantSemanticCacheStore — SemanticCachePort 的 Qdrant+Redis 双层实现。

双层缓存架构（对应 §九 工作流程）：
- Qdrant: 向量存储与语义检索，payload 仅存储 cache_key
- Redis: 缓存实际响应内容（带 TTL 管理）

工作流程：
1. 计算 embedding
2. Qdrant.search(embedding, limit=1, score_threshold=0.95)
   ↓命中 → payload 中获取 cache_key → Redis.GET(cache_key) → 返回缓存响应
   ↓未命中 → 调用 compute_fn → 写入 Redis(SET cache_key response EX ttl)
                                → 写入 Qdrant(embedding + payload{cache_key})
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING, Callable

import redis.asyncio as aioredis

from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.semantic_cache import CacheResult, SemanticCachePort

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class QdrantSemanticCacheStore(SemanticCachePort):
    """语义缓存的 Qdrant+Redis 双层实现。"""

    _CACHE_COLLECTION = "semantic_cache"
    _CACHE_VECTOR_SIZE = 1024  # bge-m3 向量维度
    _CACHE_PREFIX = "sem_cache:"

    def __init__(
        self,
        l3_vector: L3VectorPort,
        redis_client: aioredis.Redis,
        collection: str = _CACHE_COLLECTION,
        similarity_threshold: float = 0.95,
        ttl: int = 3600,
    ):
        self._l3 = l3_vector
        self._redis = redis_client
        self._collection = collection
        self._threshold = similarity_threshold
        self._ttl = ttl

    async def get_or_compute(
        self,
        query_embedding: list[float],
        compute_fn: Callable,
    ) -> CacheResult:
        """获取或计算缓存结果（双层：Qdrant 检索 + Redis 内容缓存）。"""
        # Step 1: Qdrant 向量检索
        try:
            results = await self._l3.search(
                collection=self._collection,
                query_vector=query_embedding,
                limit=1,
            )
        except Exception as e:
            logger.warning("Qdrant search failed, fallback to compute: %s", e)
            results = []

        # Step 2: 命中 → 从 payload 获取 cache_key → Redis.GET
        if results and results[0].get("score", 0) >= self._threshold:
            payload = results[0].get("payload", {})
            cache_key = payload.get("cache_key")
            if cache_key:
                try:
                    cached = await self._redis.get(f"{self._CACHE_PREFIX}{cache_key}")
                    if cached:
                        return CacheResult(value=json.loads(cached), hit=True)
                except Exception as e:
                    logger.warning("Redis GET failed, use payload fallback: %s", e)
                    return CacheResult(value=payload.get("result", {}), hit=True)

        # Step 3: 未命中 → 调用 compute_fn
        result = await compute_fn()
        cache_key = self._hash_embedding(query_embedding)

        # Step 4: 写入 Redis（带 TTL）
        try:
            await self._redis.setex(
                f"{self._CACHE_PREFIX}{cache_key}",
                self._ttl,
                json.dumps(result),
            )
        except Exception as e:
            logger.warning("Redis SET failed: %s", e)

        # Step 5: 写入 Qdrant（payload 仅存 cache_key）
        try:
            await self._l3.upsert_points(
                self._collection,
                [{
                    "id": cache_key,
                    "vector": query_embedding,
                    "payload": {
                        "cache_key": cache_key,
                        "result": result,  # 降级数据源（Redis 过期后仍可从 payload 读取）
                    },
                }],
            )
        except Exception as e:
            logger.warning("Qdrant upsert failed: %s", e)

        return CacheResult(value=result, hit=False)

    async def invalidate(self, cache_key: str) -> bool:
        """失效缓存（双删：Qdrant + Redis）。"""
        success = True
        try:
            await self._l3.delete_points(self._collection, [cache_key])
        except Exception as e:
            logger.warning("Qdrant delete failed: %s", e)
            success = False
        try:
            await self._redis.delete(f"{self._CACHE_PREFIX}{cache_key}")
        except Exception as e:
            logger.warning("Redis DELETE failed: %s", e)
            success = False
        return success

    async def invalidate_by_embedding(
        self,
        query_embedding: list[float],
    ) -> bool:
        """基于 embedding 使缓存失效。"""
        cache_key = self._hash_embedding(query_embedding)
        return await self.invalidate(cache_key)

    def _hash_embedding(self, embedding: list[float]) -> str:
        """计算 embedding 的哈希作为缓存键。"""
        quantized = [round(v, 6) for v in embedding[:10]]
        return hashlib.md5(str(quantized).encode(), usedforsecurity=False).hexdigest()[:16]
```

#### 3.2.3 更新 `src/infrastructure/storage/redis/semantic_cache_adapter.py`

**实现 SemanticCachePort 接口**:

```python
class RedisSemanticCacheAdapter(SemanticCachePort):
    """Redis 语义缓存适配器。

    使用 Redis Hash 存储嵌入向量和缓存结果。
    注意：此实现性能较差（O(n)），仅用于轻量级场景。
    """

    async def get_or_compute(
        self,
        query_embedding: list[float],
        compute_fn: Callable,
    ) -> CacheResult:
        """获取或计算缓存结果。"""
        # O(n) 扫描实现相似度匹配
        ...

    async def invalidate(self, cache_key: str) -> bool:
        """失效缓存。"""
        ...
```

### 3.3 更新 `src/application/ports/semantic_cache.py`

```python
"""SemanticCache Protocol — 应用层定义（已废弃）。

⚠️ 警告：此文件已废弃，请使用 src.domain.ports.semantic_cache.SemanticCachePort

迁移路径（v3.0）：
- 旧: cache.get(embedding, threshold), cache.set(embedding, result, ttl)
- 新: cache.get_or_compute(embedding, compute_fn)

此文件仅用于向后兼容，将在后续版本中移除。
"""

from src.domain.ports.semantic_cache import SemanticCachePort as SemanticCache
from src.domain.ports.semantic_cache import CacheResult

__all__ = ["SemanticCache", "CacheResult"]
```

### 3.4 更新 `src/composition_root.py`

```python
# === L3 Vector Storage Ports ===
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.semantic_cache import SemanticCachePort
from src.infrastructure.storage.qdrant.qdrant_l3_vector_store import QdrantL3VectorStore
from src.infrastructure.storage.qdrant.semantic_cache_store import QdrantSemanticCacheStore

register_port(
    name="l3_vector",
    version="v1.0.0",
    interface=L3VectorPort,
    impl="src.infrastructure.storage.qdrant.qdrant_l3_vector_store.QdrantL3VectorStore",
    module="src.infrastructure.storage.qdrant.qdrant_l3_vector_store",
    lifetime=Lifetime.SCOPED,
    owner="storage-team",
    tags=("qdrant", "vector"),
)

register_port(
    name="semantic_cache",
    version="v1.0.0",
    interface=SemanticCachePort,
    impl="src.infrastructure.storage.qdrant.semantic_cache_store.QdrantSemanticCacheStore",
    module="src.infrastructure.storage.qdrant.semantic_cache_store",
    lifetime=Lifetime.SCOPED,
    owner="cache-team",
    tags=("qdrant", "vector", "cache"),
)

register_port(
    name="semantic_cache_redis",
    version="v1.0.0",
    interface=SemanticCachePort,
    impl="src.infrastructure.storage.redis.semantic_cache_adapter.RedisSemanticCacheAdapter",
    module="src.infrastructure.storage.redis.semantic_cache_adapter",
    lifetime=Lifetime.SCOPED,
    owner="cache-team",
    tags=("redis", "cache"),
)
```

### 3.5 更新 `UnifiedStorageGateway`

```python
# 在 save() 方法中添加 L3 向量存储逻辑
async def save(
    self,
    memory_id: str,
    content: str,
    memory_type: str,
    owner_id: str,
    name: str,
    tier: StorageTier | None = None,
) -> dict[StorageLayer, bool]:
    results: dict[StorageLayer, bool] = {}

    # L0 文件系统（真相源，同步写入）
    l0_success = await self._l0.write(memory_id, memory_type, content)
    results[StorageLayer.L0_FILE] = l0_success

    # L3 向量存储（内容 >500 tokens 时按需启用）
    if self._l3 is not None and len(content.encode('utf-8')) > 500:
        try:
            # 生成 embedding 并存储到 L3
            embedding = await self._generate_embedding(content)
            await self._l3.upsert_points(
                collection="memories",
                points=[{
                    "id": memory_id,
                    "vector": embedding,
                    "payload": {"memory_id": memory_id, "owner": owner_id}
                }]
            )
            results[StorageLayer.L3_VECTOR] = True
        except Exception as e:
            logger.warning("L3 vector storage failed: %s", e)
            results[StorageLayer.L3_VECTOR] = False

    # ... 其他代码
    return results
```

---

## 四、执行步骤

### Phase 1: P0 修复（阻塞性问题）

#### Step 1.1: 修复 search_sparse 异常处理

**文件**: `src/infrastructure/storage/qdrant/vector_storage.py`

```python
# 修改前
except Exception:
    return []

# 修改后
except Exception as e:
    logger.error("Sparse search failed for collection %s: %s", collection, e)
    raise  # 重新抛出异常
```

#### Step 1.2: 统一 create_collection 接口参数

**文件**: `src/domain/ports/l3_vector.py`

```python
# 修改前
async def create_collection(self, collection: str, vector_size: int, vector_params: dict | None = None) -> bool:

# 修改后
async def create_collection(self, name: str, vector_size: int, distance: str = "Cosine", **kwargs) -> bool:
```

#### Step 1.3: 创建 QdrantL3VectorStore

**文件**: `src/infrastructure/storage/qdrant/qdrant_l3_vector_store.py`

完整实现（见 §3.2.1）

#### Step 1.4: 注册 L3VectorPort

**文件**: `src/composition_root.py`

添加 `l3_vector` 端口注册（见 §3.4）

#### Step 1.5: 实现 UnifiedStorageGateway 的 L3 使用

**文件**: `src/application/services/unified_storage_gateway.py`

在 `save()` 方法中添加 L3 向量存储逻辑（见 §3.5）

---

### Phase 2: P1 修复（重要问题）

#### Step 2.1: 创建 SemanticCachePort

**文件**: `src/domain/ports/semantic_cache.py`

完整实现（见 §3.1.2）

#### Step 2.2: 创建 QdrantSemanticCacheStore

**文件**: `src/infrastructure/storage/qdrant/semantic_cache_store.py`

完整实现（见 §3.2.2）

#### Step 2.3: 更新 Redis 语义缓存适配器

**文件**: `src/infrastructure/storage/redis/semantic_cache_adapter.py`

实现 `SemanticCachePort` 接口（见 §3.2.3）

#### Step 2.4: 更新应用层旧接口

**文件**: `src/application/ports/semantic_cache.py`

标记为废弃（见 §3.3）

---

### Phase 3: 验证

#### Step 3.1: 架构验证

```bash
poetry run python -c "
from src.domain.ports.l3_vector import L3VectorPort
from src.infrastructure.storage.qdrant.qdrant_l3_vector_store import QdrantL3VectorStore

# 验证 QdrantL3VectorStore 实现所有 9 个方法
store = QdrantL3VectorStore(None)  # 需要 mock
assert hasattr(store, 'upsert_points')
assert hasattr(store, 'delete_points')
assert hasattr(store, 'get_point')
assert hasattr(store, 'search')
assert hasattr(store, 'search_sparse')
assert hasattr(store, 'create_collection')
assert hasattr(store, 'delete_collection')
assert hasattr(store, 'collection_exists')
assert hasattr(store, 'list_collections')
print('✅ 9 个方法全部实现')
"
```

#### Step 3.2: 集成验证

```bash
poetry run python -c "
from src.composition_root import bootstrap
bootstrap()
from src.domain.ports.registry import _global_registry
ports = [p['name'] for p in _global_registry.list_all()]
assert 'l3_vector' in ports
assert 'semantic_cache' in ports
print('✅ 端口注册成功:', ports)
"
```

---

## 五、风险与缓解

| ID | 风险 | 影响 | 缓解措施 |
|----|------|------|----------|
| R1 | L3 接口参数变更破坏现有调用 | 中 | 保留旧参数名作为别名 |
| R2 | UnifiedStorageGateway 使用 l3 导致异常 | 中 | 添加 try/catch 降级 |
| R3 | search_sparse 异常抛出破坏现有流程 | 低 | 确认所有调用方已处理异常 |
| R4 | SemanticCachePort 接口迁移影响调用方 | 高 | 渐进迁移，提供废弃警告 |

---

## 六、验收标准

### 6.1 架构验证

```python
def test_hexagon_architecture():
    """六边形架构依赖方向验证。"""

    # 1. Domain 层零外部依赖
    import src.domain.ports.l3_vector as l3
    import src.domain.ports.semantic_cache as sc
    assert "qdrant" not in dir(l3)
    assert "qdrant" not in dir(sc)

    # 2. QdrantL3VectorStore 实现 L3VectorPort（9 个方法）
    from src.infrastructure.storage.qdrant.qdrant_l3_vector_store import QdrantL3VectorStore
    store = QdrantL3VectorStore(None)
    for method in ['upsert_points', 'delete_points', 'get_point', 'search',
                    'search_sparse', 'create_collection', 'delete_collection',
                    'collection_exists', 'list_collections']:
        assert hasattr(store, method), f"Missing method: {method}"

    # 3. SemanticCachePort 独立于 L3VectorPort
    from src.domain.ports.semantic_cache import SemanticCachePort
    from src.domain.ports.l3_vector import L3VectorPort
    assert not issubclass(SemanticCachePort, L3VectorPort)

    print("✅ 六边形架构验证通过")
```

### 6.2 功能验证

```python
async def test_l3_vector_crud():
    """L3 向量存储 CRUD 功能验证。"""
    # 1. create_collection → collection_exists == True
    # 2. upsert_points → get_point 返回正确数据
    # 3. search 返回包含 score 的结果
    # 4. delete_points → get_point 返回 None
    # 5. delete_collection → collection_exists == False
    pass

async def test_semantic_cache():
    """语义缓存功能验证。"""
    # 1. get_or_compute (cache miss) → hit == False
    # 2. get_or_compute (cache hit) → hit == True
    # 3. invalidate → 缓存被清除
    pass
```

### 6.3 向后兼容验证

```python
def test_backward_compatibility():
    """向后兼容验证。"""
    from src.application.ports.semantic_cache import SemanticCache
    from src.domain.ports.semantic_cache import SemanticCachePort
    # SemanticCache 作为别名指向 SemanticCachePort
    assert SemanticCache is SemanticCachePort
    print("✅ 向后兼容：旧导入路径仍可用")
```

---

## 七、关键修正记录

| 版本 | 日期 | 修正项 | 说明 |
|------|------|--------|------|
| v2.0 | 2026-05-13 | SemanticCachePort 不继承 L3VectorPort | Redis 实现无法满足向量检索契约 |
| v2.0 | 2026-05-13 | QdrantVectorStore 完整实现 create_collection | 移除占位符 |
| v3.0 | 2026-05-13 | P0 问题系统性修复 | search_sparse 异常处理、接口参数统一 |
| v3.0 | 2026-05-13 | QdrantL3VectorStore 组合策略 | 组合 QdrantVectorStorage + QdrantCollectionManager |
| v3.0 | 2026-05-13 | UnifiedStorageGateway self._l3 使用 | L3 功能不再虚设 |
| v3.0 | 2026-05-13 | L3VectorPort 接口参数统一 | collection → name, vector_params → distance |
| v4.0 | 2026-05-13 | **代码验证发现 v3.0 计划变更未实现** | 所有 P0/P1 问题仍未修复，需开始实际代码实现 |
| v5.0 | 2026-05-13 | **第二轮5轮审查完成** | 发现设计文档内部矛盾：SemanticVectorPort(L3VectorPort, ...) 是歧义；发现 Redis 连接池问题；确认 P0 修复依赖关系 |
| v6.0 | 2026-05-13 | **语义缓存工作流程评审** | 确认 Qdrant+Redis 分离式设计合理；发现一致性风险；TTL 不一致；缺少 invalidate_by_embedding |
| v7.0 | 2026-05-13 | **§3.2.2 重写为双层设计** | 修正与 §九 的架构矛盾；统一 TTL=3600；添加 invalidate_by_embedding；添加 Redis 依赖 |
| v8.0 | 2026-05-13 | **第3轮审查残留修正** | 更新 §2.1 Layer 4 描述；修正 §3.1.2 过时注释；更新 §九 问题表格；标记 Redis 依赖注入缺失 |

---

## 九、语义缓存工作流程评审

### 9.1 工作流程定义

```
1. 计算 embedding
2. Qdrant.search(embedding, limit=1, score_threshold=0.95)
   ↓命中
3. 获得 payload 中的 cache_key → Redis.GET(cache_key) → 返回缓存响应
   ↓未命中
4. 调用 LLM → 生成响应 → 写入 Redis(SET cache_key response EX 3600)
                                → 写入 Qdrant(embedding + payload{cache_key})
```

### 9.2 设计合理性评估

| 设计点 | 评价 |
|--------|------|
| cache_key 存储在 Qdrant payload | ✅ 合理 - 查询效率高，避免 Redis 全表扫描 |
| embedding → cache_key 生成 | ✅ 确定性哈希，同一查询生成相同 key |
| Qdrant + Redis 分离存储 | ✅ 合理 - Qdrant 负责向量检索，Redis 负责内容缓存 |

### 9.3 发现的问题

| 问题 | 严重程度 | 说明 |
|------|---------|------|
| **QdrantSemanticCacheStore 不存在** | 高 | 设计文档中的实现未创建 |
| **score_threshold 参数不支持** | 中 | `QdrantVectorStorage.search()` 签名无此参数，需后过滤 |
| **缺少 invalidate_by_embedding** | 中 | 调用方只有 embedding 无法失效缓存（v7.0 已添加） |
| **Redis 依赖注入缺失** | 中 | §3.4 composition_root 未展示 redis_client 如何注入 |

### 9.4 一致性风险

| 场景 | 风险 | 严重程度 |
|------|------|---------|
| Qdrant 写入失败 + Redis 成功 | 幽灵缓存 - Qdrant 有向量但 Redis 无数据 | 高 |
| Redis 写入失败 + Qdrant 成功 | 调用方不知道缓存未写入 | 中 |
| Qdrant 搜索失败 | 请求直接失败，无降级 | 高 |
| Redis 读取失败与未命中混淆 | 返回 None 无法区分两种情况 | 中 |

### 9.5 改进建议

1. **实现 QdrantSemanticCacheStore** - 参考 §3.2.2 的设计
2. **扩展 QdrantVectorStorage.search()** - 添加 `score_threshold` 参数支持
3. **统一 TTL 配置** - 建议使用 3600s（1小时）或暴露为配置参数
4. **添加写入验证** - 写入后读取验证数据存在性
5. **添加 invalidate_by_embedding 方法** - 支持 embedding 级别的失效
6. **考虑 Outbox Pattern** - 确保 Qdrant 和 Redis 写入一致性

---

## 八、Round 5 审查发现（代码验证）

### 8.1 P0 问题验证结果

| 问题 | 状态 | 验证方法 |
|------|------|---------|
| P0-1: search_sparse 异常吞没 | **未修复** | 代码检查 vector_storage.py:200 仍是 `except Exception: return []` |
| P0-2: l3_vector 未注册 | **未修复** | composition_root.py 中无 l3_vector 注册 |
| P0-3: self._l3 未使用 | **未修复** | UnifiedStorageGateway.save() 未调用 self._l3 |
| P0-4: L3VectorPort 实现不完整 | **未修复** | qdrant_vector_adapter.py 缺4个 collection 方法 |

### 8.2 接口签名验证结果

| 接口 | 位置 | 当前签名 | 问题 |
|------|------|---------|------|
| L3VectorPort.create_collection | domain/ports/l3_vector.py | `collection, vector_size, vector_params` | **旧签名** |
| QdrantCollectionManager.create_collection | infrastructure/collection_manager.py | `name, vector_size, distance, **kwargs` | **新签名** |

### 8.3 新文件存在性验证

| 文件（v3.0 计划创建） | 状态 |
|----------------------|------|
| `src/infrastructure/storage/qdrant/qdrant_l3_vector_store.py` | **不存在** |
| `src/infrastructure/storage/qdrant/semantic_cache_store.py` | **不存在** |
| `src/domain/ports/semantic_cache.py` | **不存在** |

### 8.4 架构验证结果

- Domain 层零依赖：✅ 正确（l3_vector.py 仅使用 typing.Protocol）
- 六边形架构约束测试：✅ 27/27 通过
- qdrant-client 1.7.1 API 兼容性：✅ 无问题

### 8.5 UnifiedStorageGateway L3 使用差距

| 差距项 | 严重程度 |
|--------|---------|
| self._l3 在 save/read/delete 中从未被调用 | P0 |
| 缺少 _generate_embedding 方法 | P0 |
| 缺少内容大小判断逻辑（>500 tokens） | P0 |
| 缺少 Collection 管理 | P1 |
| 缺少 L3 错误处理和降级策略 | P1 |

---

**文档状态**: v8.0 已完成第3轮审查残留修正
**审查摘要**:
- 修正 §2.1 Layer 4 描述：添加 "+ Redis"
- 修正 §3.1.2 过时文档注释：threshold=0.95, TTL=3600s
- 更新 §九 问题表格：移除已修正的 TTL 不一致，添加 Redis 依赖注入缺失
- P0 问题状态：6个全部未修复

**下一步**: 执行 P0 问题的实际代码实现
**关键设计澄清**: `SemanticCachePort` 使用**组合关系**调用 `L3VectorPort`，不是继承关系
