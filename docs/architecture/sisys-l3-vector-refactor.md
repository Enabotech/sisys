# SISYS L3 向量存储层重构设计方案

**版本:** v1.0
**日期:** 2026-05-13
**状态:** 设计阶段
**基于:** architecture.md §11.1 L3 向量存储设计 + sisys-uni-storage-design.md

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
│   ├── vector_storage.py     # QdrantVectorStorage（实现类，未实现 Port）
│   ├── qdrant_vector_adapter.py  # QdrantVectorAdapter → L3VectorPort
│   └── models.py             # VectorPoint, SparseVector
└── redis/
    └── semantic_cache.py     # RedisSemanticCache → SemanticCache

src/composition_root.py       # 端口注册（L3 未注册）
```

### 1.2 当前接口定义

| 接口 | 位置 | 方法签名 | 问题 |
|------|------|----------|------|
| `L3VectorPort` | `src/domain/ports/l3_vector.py` | `upsert_points`, `delete_points`, `get_point`, `search`, `search_sparse`, `create_collection`, `delete_collection`, `collection_exists`, `list_collections` | Protocol 定义完整，但无实现类实现 |
| `SemanticCache` | `src/application/ports/semantic_cache.py` | `get(query_embedding, threshold)`, `set(query_embedding, result, ttl)`, `invalidate(cache_key)` | 位于应用层而非领域层，未继承 L3VectorPort |
| `QdrantVectorStorage` | `src/infrastructure/storage/qdrant/vector_storage.py` | 向量 CRUD + 检索 | 未实现任何 Port 接口 |
| `QdrantVectorAdapter` | `src/infrastructure/storage/qdrant/qdrant_vector_adapter.py` | 透传 QdrantVectorStorage | 薄适配器，无实际价值 |

### 1.3 当前实现清单

| 实现类 | 位置 | 实现接口 | 状态 |
|--------|------|----------|------|
| `QdrantVectorStorage` | `infrastructure/storage/qdrant/` | 无 | ❌ 未实现 Port |
| `QdrantVectorAdapter` | `infrastructure/storage/qdrant/` | `L3VectorPort` | ⚠️ 仅透传 |
| `RedisSemanticCache` | `infrastructure/storage/redis/` | `SemanticCache` | ⚠️ 位置错误 |

### 1.4 问题清单

| ID | 问题 | 严重度 | 影响 |
|----|------|--------|------|
| P1 | `SemanticCache` 位于 `application/ports` 而非 `domain/ports` | P1 | 违反六边形架构分层原则 |
| P2 | `QdrantVectorStorage` 未实现任何 Port | P1 | 无法注入 Mock，测试困难 |
| P3 | `QdrantVectorAdapter` 只是透传，无实际价值 | P2 | 增加复杂度，无意义 |
| P4 | L3VectorPort 未在 composition_root.py 注册 | P1 | 无法通过依赖注入使用 |
| P5 | 语义缓存未继承 L3VectorPort | P1 | 无法替换底层实现 |
| P6 | RedisSemanticCache 使用 O(n) 扫描，语义搜索性能差 | P2 | 仅用于轻量级场景 |

### 1.5 根因分析

```
架构问题根因：

Domain Layer
├── L3VectorPort（定义完整，但无实现）
└── SemanticCache（位于错误层次，且无继承关系）

Infrastructure Layer
├── QdrantVectorStorage（功能完整，但无 Port 实现）
├── QdrantVectorAdapter（透传层，增加复杂度）
└── RedisSemanticCache（向后兼容，位置错误）

问题：
1. 领域层接口未被基础设施层实现（依赖倒置失败）
2. 具体应用接口（语义缓存）与基础接口（向量存储）无继承关系
3. composition_root.py 缺少 L3 相关注册
```

---

## 二、目标架构

### 2.1 四层职责模型

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Domain Layer - L3VectorPort（统一抽象向量存储端口）     │
│                                                                  │
│  职责：定义最底层通用向量存储接口（CRUD + 检索）                   │
│  位置：src/domain/ports/l3_vector.py                             │
│  特点：领域层零依赖，纯抽象协议                                    │
│  方法：                                                          │
│    - upsert_points / delete_points / get_point                  │
│    - search / search_sparse                                      │
│    - create_collection / delete_collection                      │
│    - collection_exists / list_collections                       │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Domain Layer - 具体应用向量存储端口                      │
│                                                                  │
│  职责：继承L3VectorPort，定义特定场景向量存储能力                  │
│  位置：src/domain/ports/                                          │
│  端口：                                                          │
│    - SemanticCachePort (语义缓存) ← 本次重构重点                   │
│    - MemoryVectorPort (记忆向量) ← 未来扩展                       │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: Infrastructure - Qdrant技术实现 + 向量存储管理            │
│                                                                  │
│  职责：实现L3VectorPort接口 + Qdrant客户端管理                     │
│  位置：src/infrastructure/storage/qdrant/                         │
│  组件：                                                          │
│    - QdrantVectorStore (实现L3VectorPort)                        │
│    - QdrantClientWrapper (Qdrant客户端单例)                       │
│  特点：技术可替换（未来可新增MilvusAdapter等）                     │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: Infrastructure - 具体应用向量存储端口实现                 │
│                                                                  │
│  职责：实现具体应用向量存储端口（SemanticCachePort等）             │
│  位置：src/infrastructure/storage/qdrant/                          │
│  组件：                                                          │
│    - QdrantSemanticCacheStore (实现SemanticCachePort)            │
│      └─ 组合QdrantVectorStore处理基础向量操作                     │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 接口继承关系

```python
# Layer 1: Domain统一抽象
class L3VectorPort(Protocol):
    """通用向量存储接口 - 最底层抽象"""
    async def upsert_points(self, collection: str, points: list[dict]) -> bool: ...
    async def delete_points(self, collection: str, point_ids: list[str]) -> bool: ...
    async def get_point(self, collection: str, point_id: str) -> dict | None: ...
    async def search(self, collection: str, query_vector: list[float], limit: int, ...) -> list[dict]: ...
    async def search_sparse(self, collection: str, sparse_vector: dict, limit: int, ...) -> list[dict]: ...
    async def create_collection(self, collection: str, vector_size: int, ...) -> bool: ...
    async def delete_collection(self, collection: str) -> bool: ...
    async def collection_exists(self, collection: str) -> bool: ...
    async def list_collections(self) -> list[str]: ...

# Layer 2: Domain具体应用端口
class SemanticCachePort(L3VectorPort, Protocol):
    """语义缓存接口 - 继承L3VectorPort"""
    SIMILARITY_THRESHOLD: float = 0.9
    TTL: int = 86400

    async def get_or_compute(self, query_embedding: list[float], compute_fn: Callable) -> CacheResult: ...
    async def invalidate(self, cache_key: str) -> bool: ...

@dataclass
class CacheResult:
    value: dict
    hit: bool

# Layer 3: Infrastructure Qdrant实现
class QdrantVectorStore(L3VectorPort):
    """Qdrant通用向量存储实现"""
    def __init__(self, client_wrapper: QdrantClientWrapper): ...

    async def upsert_points(self, collection: str, points: list[dict]) -> bool: ...
    async def search(self, collection: str, query_vector: list[float], limit: int, ...) -> list[dict]: ...
    # ... 其他L3VectorPort方法实现

# Layer 4: Infrastructure具体应用实现
class QdrantSemanticCacheStore(SemanticCachePort):
    """Qdrant语义缓存实现"""
    def __init__(self, l3_vector: L3VectorPort, collection: str = "semantic_cache", ...):
        self._l3 = l3_vector

    async def get_or_compute(self, query_embedding, compute_fn):
        # 1. 搜索相似缓存
        results = await self._l3.search(collection=self._collection, query_vector=query_embedding, limit=1)
        if results and results[0]["score"] >= self._threshold:
            return CacheResult(value=results[0]["payload"]["result"], hit=True)
        # 2. 缓存未命中，执行计算并存储
        result = await compute_fn()
        await self._l3.upsert_points(self._collection, [{"id": self._hash_embedding(query_embedding), ...}])
        return CacheResult(value=result, hit=False)

    # 继承L3VectorPort基础方法
    async def upsert_points(self, collection: str, points: list[dict]) -> bool:
        return await self._l3.upsert_points(collection, points)

    async def search(self, collection: str, query_vector: list[float], limit: int, ...) -> list[dict]:
        return await self._l3.search(collection, query_vector, limit, ...)
```

### 2.4 与L1层缓存的对比

| 维度 | L1 Cache (Redis) | L3 Vector (Qdrant) |
|------|------------------|-------------------|
| **基础接口** | `L1CachePort` | `L3VectorPort` |
| **应用接口** | `SemanticCachePort` (Redis实现) | `SemanticCachePort` (Qdrant实现) |
| **存储类型** | 键值缓存 | 向量存储 + 相似度检索 |
| **检索方式** | 精确匹配 / 模式扫描 | 向量相似度搜索 |
| **技术实现** | `RedisMemoryCache` | `QdrantVectorStore` |
| **应用实现** | `RedisSemanticCacheAdapter` | `QdrantSemanticCacheStore` |

### 2.5 文件结构

```
src/domain/ports/
├── l3_vector.py                  # L3VectorPort（基础抽象，不变）
├── semantic_cache.py             # SemanticCachePort（继承 L3VectorPort）⚡ 新建
└── storage_enums.py              # StorageLayer 等（不变）

src/infrastructure/storage/
├── qdrant/
│   ├── qdrant_vector_store.py    # QdrantVectorStore → L3VectorPort ⚡ 合并重构
│   ├── semantic_cache_store.py   # QdrantSemanticCacheStore → SemanticCachePort ⚡ 新建
│   ├── qdrant_vector_adapter.py  # ⚡ 删除（合并到 qdrant_vector_store.py）
│   └── models.py                 # VectorPoint, SparseVector（不变）
├── redis/
│   └── semantic_cache_adapter.py # RedisSemanticCacheAdapter → SemanticCachePort ⚡ 重命名+重构
└── __init__.py

src/application/ports/
└── semantic_cache.py             # ⚡ 删除（迁移到 domain 层）

src/composition_root.py           # ⚡ 添加 L3 相关注册
```

---

## 三、详细设计

### 3.1 Domain 层设计

#### 3.1.1 新建 `src/domain/ports/semantic_cache.py`

```python
"""SemanticCachePort — 语义缓存抽象端口。

继承 L3VectorPort，提供语义相似度缓存能力。
用于 RAG 检索加速（Story 1.4 Epic 3）。

设计原则：
- 语义相似度缓存（SIMILARITY_THRESHOLD = 0.9）
- TTL = 24h
- query embedding 哈希作为 cache key
- 继承 L3VectorPort，支持底层实现切换
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.domain.ports.l3_vector import L3VectorPort


class SemanticCachePort(L3VectorPort):
    """语义缓存端口。

    继承 L3VectorPort，提供语义相似度缓存能力。
    所有具体实现必须实现 L3VectorPort 的基础方法。

    设计原则：
    - 语义相似度缓存（SIMILARITY_THRESHOLD = 0.9）
    - TTL = 24h（86400秒）
    - query embedding 哈希作为 cache key
    """

    SIMILARITY_THRESHOLD: float = 0.9
    TTL: int = 86400

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

#### 3.1.2 更新 `src/domain/ports/l3_vector.py`

在现有 L3VectorPort 中添加 `list_collections()` 方法（如果缺失）：

```python
async def list_collections(self) -> list[str]:
    """列出所有 Collection。

    Returns:
        Collection 名称列表
    """
```

### 3.2 Infrastructure 层设计

#### 3.2.1 新建 `src/infrastructure/storage/qdrant/qdrant_vector_store.py`

合并 `QdrantVectorStorage` 和 `QdrantVectorAdapter`，直接实现 `L3VectorPort`。

```python
"""QdrantVectorStore — L3VectorPort 的 Qdrant 实现。

合并 QdrantVectorStorage 和 QdrantVectorAdapter，
直接实现 L3VectorPort 接口。

职责：
- Qdrant 客户端管理
- Collection 管理
- 向量点 CRUD
- Dense/Sparse 检索
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
    NamedSparseVector,
    PointIdsList,
    PointStruct,
    Range,
)
from qdrant_client.models import SparseVector as QdrantSparseVector

from src.domain.ports.l3_vector import L3VectorPort
from src.infrastructure.storage.qdrant.client import QdrantClientWrapper


class QdrantVectorStore(L3VectorPort):
    """Qdrant 向量存储，直接实现 L3VectorPort。"""

    def __init__(self, client_wrapper: QdrantClientWrapper):
        self._client_wrapper = client_wrapper

    def _get_client(self) -> AsyncQdrantClient:
        return self._client_wrapper.get_async_client()

    def _normalize_point_id(self, point_id: str) -> int:
        """规范化向量点 ID，确保 Qdrant 接受。

        Qdrant v1.7.x 要求 ID 为无符号整数或 UUID。
        - 纯数字字符串转换为整数
        - 小整数（<1000）使用 hash 映射到有效范围避免被拒绝
        """
        try:
            pid = int(point_id)
            if pid < 1000:
                return abs(hash(point_id)) % (2**31)
            return pid
        except ValueError:
            return abs(hash(point_id)) % (2**31)

    async def upsert_points(
        self,
        collection: str,
        points: list[dict],
    ) -> bool:
        """批量插入或更新向量点。"""
        client = self._get_client()
        point_structs = []
        for point in points:
            pid = self._normalize_point_id(point["id"])
            point_structs.append(
                PointStruct(
                    id=pid,
                    vector=point["vector"],
                    payload={
                        **point.get("payload", {}),
                        "created_at": datetime.now().isoformat(),
                    },
                )
            )
        await client.upsert(collection_name=collection, points=point_structs)
        return True

    async def delete_points(
        self,
        collection: str,
        point_ids: list[str],
    ) -> bool:
        """批量删除向量点。"""
        client = self._get_client()
        converted_ids = [self._normalize_point_id(pid) for pid in point_ids]
        await client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=cast(Any, converted_ids)),
        )
        return True

    async def get_point(
        self,
        collection: str,
        point_id: str,
    ) -> dict | None:
        """获取单个向量点。"""
        client = self._get_client()
        normalized_id = self._normalize_point_id(point_id)
        points = await client.retrieve(
            collection_name=collection,
            ids=[normalized_id],
            with_payload=True,
        )
        if not points:
            return None
        point = points[0]
        return {"id": point.id, "vector": point.vector, "payload": point.payload}

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        """Dense 语义检索。"""
        client = self._get_client()
        query_filter = self._build_filter(filter_payload)
        response = await client.search(
            collection_name=collection,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return [
            {"id": point.id, "score": point.score, "payload": point.payload or {}}
            for point in response
        ]

    async def search_sparse(
        self,
        collection: str,
        sparse_vector: dict,
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        """BM25 稀疏检索。"""
        client = self._get_client()
        query_filter = self._build_filter(filter_payload)
        try:
            qdrant_sparse = QdrantSparseVector(
                indices=sparse_vector["indices"],
                values=sparse_vector["values"],
            )
            named_sparse = NamedSparseVector(name="sparse", vector=qdrant_sparse)
            response = await client.search(
                collection_name=collection,
                query_vector=named_sparse,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            return [
                {"id": point.id, "score": point.score, "payload": point.payload or {}}
                for point in response
            ]
        except Exception:
            return []

    async def create_collection(
        self,
        collection: str,
        vector_size: int,
        vector_params: dict | None = None,
    ) -> bool:
        """创建 Collection。"""
        # 实现创建逻辑
        return True

    async def delete_collection(self, collection: str) -> bool:
        """删除 Collection。"""
        client = self._get_client()
        await client.delete_collection(collection_name=collection)
        return True

    async def collection_exists(self, collection: str) -> bool:
        """检查 Collection 是否存在。"""
        client = self._get_client()
        collections = await client.get_collections()
        return collection in [c.name for c in collections.collections]

    async def list_collections(self) -> list[str]:
        """列出所有 Collection。"""
        client = self._get_client()
        collections = await client.get_collections()
        return [c.name for c in collections.collections]

    def _build_filter(self, filter_payload: dict | None) -> Filter | None:
        """构建 Qdrant 过滤条件。"""
        if not filter_payload:
            return None
        conditions = []
        for key, value in filter_payload.items():
            if isinstance(value, (str, bool)):
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                conditions.append(FieldCondition(key=key, match=MatchValue(value=int(value))))
            elif isinstance(value, dict) and "gte" in value and "lte" in value:
                conditions.append(
                    FieldCondition(key=key, range=Range(gte=value["gte"], lte=value["lte"]))
                )
            else:
                conditions.append(FieldCondition(key=key, match=MatchValue(value=str(value))))
        return Filter(must=conditions) if conditions else None
```

#### 3.2.2 新建 `src/infrastructure/storage/qdrant/semantic_cache_store.py`

```python
"""QdrantSemanticCacheStore — SemanticCachePort 的 Qdrant 实现。

使用 Qdrant 向量检索实现语义缓存，支持相似度匹配。

Collection 结构：
- id: query embedding hash (string)
- vector: query embedding (用于相似度检索)
- payload: {"query_embedding": [...], "result": {...}}

设计原则：
- 使用向量相似度搜索而非哈希匹配
- 支持任意 query_embedding 的相似度查找
- 底层委托给 QdrantVectorStore
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, cast

from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.semantic_cache import CacheResult, SemanticCachePort

if TYPE_CHECKING:
    pass


class QdrantSemanticCacheStore(SemanticCachePort):
    """语义缓存的 Qdrant 实现。

    使用 Qdrant 向量相似度搜索实现语义缓存。
    底层委托给 QdrantVectorStore。

    特点：
    - 支持任意 query_embedding 的相似度匹配
    - SIMILARITY_THRESHOLD = 0.9
    - TTL = 24h
    """

    _CACHE_COLLECTION = "semantic_cache"
    _CACHE_VECTOR_SIZE = 1536  # 默认 embedding 维度，可配置

    def __init__(
        self,
        l3_vector: L3VectorPort,
        collection: str = _CACHE_COLLECTION,
        similarity_threshold: float = 0.9,
        ttl: int = 86400,
    ):
        """初始化 Qdrant 语义缓存。

        Args:
            l3_vector: L3VectorPort 实现（QdrantVectorStore）
            collection: Collection 名称
            similarity_threshold: 相似度阈值
            ttl: 过期时间（秒）
        """
        self._l3 = l3_vector
        self._collection = collection
        self._threshold = similarity_threshold
        self._ttl = ttl

    async def get_or_compute(
        self,
        query_embedding: list[float],
        compute_fn: Callable,
    ) -> CacheResult:
        """获取或计算缓存结果。

        使用向量相似度搜索找到最接近的缓存条目。

        Args:
            query_embedding: 查询向量
            compute_fn: 缓存未命中时的计算函数

        Returns:
            CacheResult {value, hit}
        """
        # 搜索相似缓存
        results = await self._l3.search(
            collection=self._collection,
            query_vector=query_embedding,
            limit=1,
            filter_payload=None,
        )

        if results and results[0]["score"] >= self._threshold:
            payload = results[0].get("payload", {})
            return CacheResult(value=payload.get("result", {}), hit=True)

        # 缓存未命中，执行计算
        result = await compute_fn()

        # 存储到缓存
        cache_key = self._hash_embedding(query_embedding)
        await self._l3.upsert_points(
            self._collection,
            [{
                "id": cache_key,
                "vector": query_embedding,
                "payload": {
                    "query_embedding": query_embedding,
                    "result": result,
                },
            }],
        )

        return CacheResult(value=result, hit=False)

    async def invalidate(self, cache_key: str) -> bool:
        """失效缓存。

        Args:
            cache_key: 缓存键（embedding hash）

        Returns:
            是否成功
        """
        await self._l3.delete_points(self._collection, [cache_key])
        return True

    def _hash_embedding(self, embedding: list[float]) -> str:
        """计算 embedding 的哈希作为缓存键。"""
        emb_str = ",".join([str(x) for x in embedding[:10]])
        return hashlib.md5(emb_str.encode(), usedforsecurity=False).hexdigest()[:16]

    # ===== L3VectorPort 方法实现（委托给内部 l3）=====

    async def upsert_points(
        self,
        collection: str,
        points: list[dict],
    ) -> bool:
        return await self._l3.upsert_points(collection, points)

    async def delete_points(
        self,
        collection: str,
        point_ids: list[str],
    ) -> bool:
        return await self._l3.delete_points(collection, point_ids)

    async def get_point(
        self,
        collection: str,
        point_id: str,
    ) -> dict | None:
        return await self._l3.get_point(collection, point_id)

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        return await self._l3.search(collection, query_vector, limit, filter_payload)

    async def search_sparse(
        self,
        collection: str,
        sparse_vector: dict,
        limit: int = 10,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        return await self._l3.search_sparse(collection, sparse_vector, limit, filter_payload)

    async def create_collection(
        self,
        collection: str,
        vector_size: int,
        vector_params: dict | None = None,
    ) -> bool:
        return await self._l3.create_collection(collection, vector_size, vector_params)

    async def delete_collection(self, collection: str) -> bool:
        return await self._l3.delete_collection(collection)

    async def collection_exists(self, collection: str) -> bool:
        return await self._l3.collection_exists(collection)

    async def list_collections(self) -> list[str]:
        return await self._l3.list_collections()
```

#### 3.2.3 重构 `src/infrastructure/storage/redis/semantic_cache.py`

重命名为 `semantic_cache_adapter.py`，更新类名为 `RedisSemanticCacheAdapter`，实现 `SemanticCachePort` 接口。

```python
class RedisSemanticCacheAdapter(SemanticCachePort):
    """语义缓存的 Redis 实现（向后兼容）。

    使用 Redis Hash 存储向量和结果，通过余弦相似度扫描实现匹配。
    性能较差（O(n)），仅用于不需要 Qdrant 的轻量级场景。

    注意：此实现不符合 SemanticCachePort 继承 L3VectorPort 的设计
    因为 Redis 不具备向量检索能力。此为过渡方案。
    """
```

### 3.3 Application 层变更

#### 3.3.1 删除 `src/application/ports/semantic_cache.py`

该文件已迁移到 `src/domain/ports/semantic_cache.py`。

### 3.4 Composition Root 变更

#### 3.4.1 更新 `src/composition_root.py`

添加 L3 向量存储相关注册：

```python
# === L3 Vector Storage Ports ===
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.semantic_cache import SemanticCachePort
from src.infrastructure.storage.qdrant.qdrant_vector_store import QdrantVectorStore
from src.infrastructure.storage.qdrant.semantic_cache_store import QdrantSemanticCacheStore

register_port(
    name="l3_vector",
    version="v1.0.0",
    interface=L3VectorPort,
    impl="src.infrastructure.storage.qdrant.qdrant_vector_store.QdrantVectorStore",
    module="src.infrastructure.storage.qdrant.qdrant_vector_store",
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

---

## 四、执行步骤

### Phase 1: Domain 层重构

#### Step 1.1: 创建 `src/domain/ports/semantic_cache.py`

1. 创建文件 `src/domain/ports/semantic_cache.py`
2. 定义 `SemanticCachePort` 类继承 `L3VectorPort`
3. 定义 `CacheResult` 数据类
4. 定义 `SIMILARITY_THRESHOLD = 0.9` 和 `TTL = 86400` 常量
5. 定义抽象方法 `get_or_compute` 和 `invalidate`

#### Step 1.2: 更新 `src/domain/ports/l3_vector.py`

1. 添加 `list_collections()` 方法声明（如果缺失）

#### Step 1.3: 更新 `src/domain/ports/__init__.py`

1. 添加 `SemanticCachePort` 导出

**验证标准**:
```bash
poetry run python -c "from src.domain.ports.semantic_cache import SemanticCachePort; print('OK')"
```

---

### Phase 2: Infrastructure 层重构

#### Step 2.1: 创建 `src/infrastructure/storage/qdrant/qdrant_vector_store.py`

1. 合并 `QdrantVectorStorage` 和 `QdrantVectorAdapter` 逻辑
2. 实现 `L3VectorPort` 所有方法
3. 使用 `datetime` 处理 `created_at`
4. 保留 `_normalize_point_id` 逻辑

#### Step 2.2: 更新 `src/infrastructure/storage/qdrant/__init__.py`

```python
from src.infrastructure.storage.qdrant.qdrant_vector_store import QdrantVectorStore

__all__ = [
    "QdrantVectorStore",
]
```

#### Step 2.3: 删除 `src/infrastructure/storage/qdrant/qdrant_vector_adapter.py`

```
1. 确认所有方法已迁移到 qdrant_vector_store.py
2. 删除文件
```

#### Step 2.4: 创建 `src/infrastructure/storage/qdrant/semantic_cache_store.py`

1. 创建 `QdrantSemanticCacheStore` 类
2. 实现 `L3VectorPort` 所有方法（委托）
3. 实现 `get_or_compute`（核心业务逻辑）
4. 实现 `invalidate`
5. 实现 `_hash_embedding` 辅助方法

#### Step 2.5: 重构 Redis 语义缓存

1. 重命名为 `semantic_cache_adapter.py`
2. 更新类名为 `RedisSemanticCacheAdapter`
3. 实现 `SemanticCachePort` 接口
4. 添加警告注释说明这是过渡方案

**验证标准**:
```bash
poetry run python -c "
from src.infrastructure.storage.qdrant.qdrant_vector_store import QdrantVectorStore
from src.infrastructure.storage.qdrant.semantic_cache_store import QdrantSemanticCacheStore
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.semantic_cache import SemanticCachePort
print('OK')
"
```

---

### Phase 3: Application 层清理

#### Step 3.1: 删除 `src/application/ports/semantic_cache.py`

```
1. 确认无其他文件引用
2. 删除文件
```

#### Step 3.2: 更新所有引用

```bash
# 查找所有引用
grep -r "from src.application.ports.semantic_cache import" --include="*.py"
grep -r "from application.ports.semantic_cache import" --include="*.py"
```

```
1. 更新为 from src.domain.ports.semantic_cache import SemanticCachePort
2. 或更新为 from src.domain.ports.semantic_cache import SemanticCachePort as SemanticCache
```

---

### Phase 4: Composition Root 更新

#### Step 4.1: 更新 `src/composition_root.py`

```
1. 添加 L3VectorPort 注册（l3_vector）
2. 添加 SemanticCachePort 注册（semantic_cache -> Qdrant 实现）
3. 添加 SemanticCachePort Redis 实现注册（semantic_cache_redis -> 向后兼容）
```

**验证标准**:
```bash
poetry run python -c "
from src.composition_root import bootstrap
bootstrap()
from src.domain.ports.registry import _global_registry
ports = [p['name'] for p in _global_registry.list_all()]
assert 'l3_vector' in ports
assert 'semantic_cache' in ports
print('Registered ports:', ports)
"
```

---

### Phase 5: 测试更新

#### Step 5.1: 更新单元测试

```bash
# 查找相关测试
find tests -name "*qdrant*" -o -name "*semantic*" -o -name "*vector*"
```

```
1. 重命名 test_qdrant_vector_adapter.py → test_qdrant_vector_store.py
2. 更新测试以使用新的类名和接口
3. 添加 L3VectorPort 接口一致性测试
```

#### Step 5.2: 更新集成测试

```
1. 更新 test_qdrant_real_integration.py
2. 确保 L3VectorPort 和 SemanticCachePort 测试覆盖
```

---

### Phase 6: 文档更新

#### Step 6.1: 更新架构文档

```
1. 更新 docs/architecture/sisys-uni-storage-design.md
   - 反映新的 L3VectorPort + SemanticCachePort 继承关系
   - 更新 L3 层实现表格

2. 更新 docs/architecture/architecture.md §11 存储架构
```

#### Step 6.2: 更新 README

```
1. 更新 deploy/qdrant/README.md
2. 更新 deploy/redis/README.md
```

---

## 五、风险与缓解

| ID | 风险 | 影响 | 缓解措施 |
|----|------|------|----------|
| R1 | 删除 `application/ports/semantic_cache.py` 可能破坏现有功能 | 高 | 逐步迁移，先保留再删除 |
| R2 | QdrantVectorStore 合并后测试覆盖不足 | 中 | 添加完整的单元测试和集成测试 |
| R3 | RedisSemanticCacheAdapter 无法真正实现 L3VectorPort | 低 | 添加明确注释，标记为过渡方案 |
| R4 | composition_root.py 注册冲突 | 中 | 使用不同的 name（如 semantic_cache_redis） |

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
    assert "redis" not in dir(l3)
    assert "redis" not in dir(sc)

    # 2. SemanticCachePort 继承 L3VectorPort
    from src.domain.ports.semantic_cache import SemanticCachePort
    from src.domain.ports.l3_vector import L3VectorPort
    assert issubclass(SemanticCachePort, L3VectorPort)

    # 3. 具体实现实现 Port 接口
    from src.infrastructure.storage.qdrant.qdrant_vector_store import QdrantVectorStore
    from src.infrastructure.storage.qdrant.semantic_cache_store import QdrantSemanticCacheStore

    # QdrantVectorStore 实现 L3VectorPort
    assert hasattr(QdrantVectorStore, 'upsert_points')
    assert hasattr(QdrantVectorStore, 'search')

    # QdrantSemanticCacheStore 实现 SemanticCachePort
    assert hasattr(QdrantSemanticCacheStore, 'get_or_compute')
    assert hasattr(QdrantSemanticCacheStore, 'invalidate')

    print("✅ 六边形架构验证通过")
```

### 6.2 功能验证

```python
async def test_vector_crud():
    """向量存储 CRUD 功能验证。"""
    # 1. upsert_points
    # 2. get_point
    # 3. search
    # 4. delete_points
    pass

async def test_semantic_cache():
    """语义缓存功能验证。"""
    # 1. get_or_compute (cache miss)
    # 2. get_or_compute (cache hit)
    # 3. invalidate
    pass
```

### 6.3 向后兼容验证

```python
def test_backward_compatibility():
    """向后兼容验证。"""
    # 旧的导入路径应报错（推动迁移）
    try:
        from src.application.ports.semantic_cache import SemanticCache
        print("⚠️ 旧导入路径仍可用（应迁移）")
    except ImportError:
        print("✅ 旧导入路径已移除")
```

---

## 七、业界最佳实践对标

| 实践 | LangChain/Haystack | 本系统现状 | 改进方向 |
|------|-------------------|-----------|---------|
| 分层抽象 | VectorStore 基础抽象 + 特定场景扩展 | 混合在一起 | ✅ 分离 L3VectorPort 和 SemanticCachePort |
| 继承关系 | BaseVectorStore → SemanticCacheVectorStore | 无继承 | ✅ SemanticCachePort 继承 L3VectorPort |
| 实现注册 | 统一 registry 模式 | 不完整 | ✅ 完善 composition_root 注册 |
| 接口设计 | Protocol 而非 ABC | Protocol | ✅ 保持 Protocol 风格 |

---

## 八、后续优化方向（可选）

1. **移除 RedisSemanticCacheAdapter**：当 Qdrant 成熟后，可移除 Redis 实现
2. **新增 MilvusAdapter**：支持 Milvus 作为另一个 L3VectorPort 实现
3. **添加 MemoryVectorPort**：专门用于记忆向量的存储和检索

---

**文档状态**: 待评审
**下一步**: 等待用户确认后开始执行
