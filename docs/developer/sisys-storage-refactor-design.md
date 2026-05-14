# SISYS 存储子系统重构详细设计与执行方案

**文档版本:** v3.0
**生成时间:** 2026-05-14

---

## 四条设计规则与四层架构映射

| 规则 | 架构层 | 职责 | 位置 |
|------|--------|------|------|
| **1** | Domain Layer | 统一抽象存储基础端口 `L[n][XXX]Port`，零依赖，技术无关 | `src/domain/ports/` |
| **2** | Application Layer | 具体应用端口**继承**基础端口，定义业务语义 | `src/application/ports/` |
| **3** | Infrastructure Layer-1 | 基础端口的技术实现 + 连接管理，可替换 | `src/infrastructure/storage/{tech}/` |
| **4** | Infrastructure Layer-2 | 应用端口的技术实现，**组合注入**Layer-1适配器 | `src/infrastructure/storage/{tech}/` |

---

## 架构总览（六层存储 × 四层规则）

```
┌─────────────────────────────────────────────────────────────────────┐
│  Rule 1: Domain Layer — 存储基础端口（技术无关，零依赖）               │
│                                                                      │
│  L0FilePort        L1CachePort       L2RdbPort                      │
│  L3VectorPort      L4ObjectPort      L5GraphPort                    │
│  UnifiedStoragePort（组合注入L0-L5）                                  │
│                                                                      │
│  位置: src/domain/ports/l{n}_{xxx}.py                                │
└─────────────────────────────────────────────────────────────────────┘
                              ↑ 继承
┌─────────────────────────────────────────────────────────────────────┐
│  Rule 2: Application Layer — 具体应用端口（继承基础端口+业务语义）      │
│                                                                      │
│  继承L0: MemoryFilePort(L0FilePort)                                  │
│  继承L1: SessionCachePort(L1CachePort)                               │
│  继承L2: MemoryMetadataPort(L2RdbPort)                            │
│  继承L3: MemoryVectorPort(L3VectorPort)                              │
│  继承L4: DocumentStoragePort(L4ObjectPort)                           │
│  继承L5: MemoryGraphPort(L5GraphPort)                                │
│                                                                      │
│  位置: src/application/ports/                                        │
└─────────────────────────────────────────────────────────────────────┘
                              ↑ 实现
┌─────────────────────────────────────────────────────────────────────┐
│  Rule 3: Infrastructure Layer-1 — 基础端口实现 + 连接管理              │
│                                                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │
│  │ FileAdapter  │ │ RedisAdapter │ │ PostgreSQL   │                 │
│  │ (L0FilePort) │ │ (L1CachePort)│ │ Repos(L2RdbPort)│                 │
│  └──────────────┘ └──────────────┘ └──────────────┘                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │
│  │ QdrantAdapter│ │ MinIOAdapter │ │ Neo4jAdapter │                 │
│  │ (L3VectorPort)│ │ (L4ObjectPort)│ │ (L5GraphPort)│                 │
│  └──────────────┘ └──────────────┘ └──────────────┘                 │
│  + ConnectionManagers（连接池、健康检查、生命周期）                     │
│                                                                      │
│  位置: src/infrastructure/storage/{tech}/                            │
└─────────────────────────────────────────────────────────────────────┘
                              ↑ 实现（组合注入Rule 3的适配器）
┌─────────────────────────────────────────────────────────────────────┐
│  Rule 4: Infrastructure Layer-2 — 应用端口实现                        │
│                                                                      │
│  ┌──────────────────────┐ ┌──────────────────────┐                  │
│  │ MemoryFileStorage    │ │ RedisSessionCache     │                  │
│  │ (MemoryFilePort)     │ │ (SessionCachePort)    │                  │
│  │ ← 组合 FileAdapter   │ │ ← 组合 RedisAdapter  │                  │
│  └──────────────────────┘ └──────────────────────┘                  │
│  ┌──────────────────────┐ ┌──────────────────────┐                  │
│  │ PgMemoryMetadataRepo │ │ QdrantMemoryVector    │                  │
│  │ (MemoryMetadataPort) │ │ (MemoryVectorPort)    │                  │
│  │ ← 组合 PgBaseRepo    │ │ ← 组合 QdrantAdapter │                  │
│  └──────────────────────┘ └──────────────────────┘                  │
│  ┌──────────────────────┐ ┌──────────────────────┐                  │
│  │ MinIODocumentStorage │ │ Neo4jMemoryGraph      │                  │
│  │ (DocumentStoragePort)│ │ (MemoryGraphPort)     │                  │
│  │ ← 组合 MinIOAdapter  │ │ ← 组合 Neo4jAdapter  │                  │
│  └──────────────────────┘ └──────────────────────┘                  │
│                                                                      │
│  位置: src/infrastructure/storage/{tech}/                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## L4 对象存储（参考设计，直接落地）

### Rule 1: Domain Layer — L4ObjectPort

```
src/domain/ports/l4_object.py

L4ObjectPort(Protocol)  # 已有，保持不变
  ├── store(bucket_type, object_key, file_path, content_type, tags) → str
  ├── retrieve(bucket_type, object_key, version_id) → AsyncIterator[bytes]
  ├── delete(bucket_type, object_key, version_id) → bool
  ├── get_metadata(bucket_type, object_key, version_id) → dict
  ├── archive(bucket_type, object_key, content?, retention_days) → str
  └── list_objects(bucket_type, prefix, recursive) → list[dict]
```

### Rule 2: Application Layer — DocumentStoragePort

```python
# src/application/ports/document_storage_port.py — 新增

from typing import Protocol
from src.domain.ports.l4_object import L4ObjectPort

class DocumentStoragePort(L4ObjectPort, Protocol):
    """文档存储端口 — 继承L4ObjectPort，添加文档业务语义。

    继承所有L4ObjectPort方法，额外提供：
    - 自动路径生成（documents/{user_id}/{type}/YYYY-MM）
    - 文档元数据管理
    - 用户文档列表
    """

    async def store_document(
        self,
        user_id: str,
        doc_type: str,
        file_path: str,
        metadata: dict | None = None,
    ) -> str:
        """存储文档（自动生成对象路径）。"""
        ...

    async def list_user_documents(
        self,
        user_id: str,
        doc_type: str | None = None,
    ) -> list[dict]:
        """列出用户文档。"""
        ...

    async def get_document_metadata(
        self,
        user_id: str,
        document_id: str,
    ) -> dict | None:
        """获取文档元数据。"""
        ...
```

### Rule 3: Infrastructure Layer-1 — MinIOAdapter + 连接管理

```
src/infrastructure/storage/minio/  （已有，保持三层委托）
├── client_adapter.py        MinioClientAdapter — 连接池管理、S3错误映射、健康检查
├── bucket_manager.py         BucketManager — Bucket CRUD、命名验证、WORM配置
├── worm_lifecycle.py         WORMManager — 合规锁定、生命周期管理
├── object_operations.py      ObjectOperations — 流式上传/下载、分片上传、断点续传
├── minio_repository.py       MinIORepository — 组合上述组件，实现L4ObjectPort
└── minio_adapter.py          MinIOAdapter(L4ObjectPort) — 薄适配器，委托Repository
```

**连接管理**: MinioClientAdapter 已实现延迟初始化 + 健康检查。

### Rule 4: Infrastructure Layer-2 — MinIODocumentStorage

```python
# src/infrastructure/storage/minio/document_storage.py — 新增

from src.application.ports.document_storage_port import DocumentStoragePort
from src.domain.ports.l4_object import L4ObjectPort

class MinIODocumentStorage(DocumentStoragePort):
    """MinIO文档存储实现 — 组合注入MinIOAdapter。"""

    def __init__(self, object_adapter: L4ObjectPort):
        self._adapter = object_adapter  # 组合注入Rule 3的适配器

    # === 继承的L4ObjectPort方法 — 委托给适配器 ===

    async def store(self, bucket_type, object_key, file_path, **kwargs) -> str:
        return await self._adapter.store(bucket_type, object_key, file_path, **kwargs)

    async def retrieve(self, bucket_type, object_key, **kwargs):
        return self._adapter.retrieve(bucket_type, object_key, **kwargs)

    async def delete(self, bucket_type, object_key, **kwargs) -> bool:
        return await self._adapter.delete(bucket_type, object_key, **kwargs)

    async def get_metadata(self, bucket_type, object_key, **kwargs) -> dict:
        return await self._adapter.get_metadata(bucket_type, object_key, **kwargs)

    async def archive(self, bucket_type, object_key, **kwargs) -> str:
        return await self._adapter.archive(bucket_type, object_key, **kwargs)

    async def list_objects(self, bucket_type, **kwargs) -> list[dict]:
        return await self._adapter.list_objects(bucket_type, **kwargs)

    # === DocumentStoragePort扩展方法 — 业务语义 ===

    async def store_document(
        self, user_id: str, doc_type: str, file_path: str,
        metadata: dict | None = None,
    ) -> str:
        from datetime import date
        today = date.today().strftime("%Y-%m")
        object_key = f"documents/{user_id}/{doc_type}/{today}/{uuid4().hex[:8]}"
        version = await self._adapter.store("documents", object_key, file_path)
        return object_key  # 返回文档路径作为ID

    async def list_user_documents(
        self, user_id: str, doc_type: str | None = None,
    ) -> list[dict]:
        prefix = f"documents/{user_id}/"
        if doc_type:
            prefix += f"{doc_type}/"
        return await self._adapter.list_objects("documents", prefix=prefix)

    async def get_document_metadata(
        self, user_id: str, document_id: str,
    ) -> dict | None:
        try:
            return await self._adapter.get_metadata("documents", document_id)
        except Exception:
            return None
```

---

## L0 文件存储

### Rule 1: Domain Layer — L0FilePort（已有 L0StoragePort）

```python
# src/domain/ports/l0_storage.py — 已有，无需修改

class L0StoragePort(Protocol):
    async def write(self, memory_id: str, memory_type: str, content: str) -> bool: ...
    async def read(self, memory_id: str, memory_type: str) -> str: ...
    async def delete(self, memory_id: str, memory_type: str) -> bool: ...
    async def exists(self, memory_id: str, memory_type: str) -> bool: ...
    async def list_memories(self, memory_type: str) -> list[str]: ...
```

### Rule 2: Application Layer — MemoryFilePort

```python
# src/application/ports/memory_file_port.py — 新增

from typing import Protocol
from src.domain.ports.l0_storage import L0StoragePort

class MemoryFilePort(L0StoragePort, Protocol):
    """记忆文件端口 — 继承L0StoragePort，添加记忆管理语义。

    继承所有L0方法，额外提供：
    - MEMORY.md索引管理
    - 按类型搜索记忆
    """

    async def update_index(self, entry: str, max_lines: int = 200) -> None:
        """更新MEMORY.md索引。"""
        ...

    async def remove_from_index(self, memory_id: str) -> None:
        """从索引移除条目。"""
        ...
```

### Rule 3: Infrastructure Layer-1 — FileMemoryAdapter（已有）

```
src/infrastructure/storage/file_memory_adapter.py
  FileMemoryAdapter(L0StoragePort) — aiofiles + asyncio.to_thread()
  连接管理: 无（文件系统直接操作）
```

### Rule 4: Infrastructure Layer-2 — MemoryFileStorage

```python
# src/infrastructure/storage/memory_file_storage.py — 新增

from src.application.ports.memory_file_port import MemoryFilePort
from src.domain.ports.l0_storage import L0StoragePort
from src.domain.ports.index_manager import IndexManagerPort

class MemoryFileStorage(MemoryFilePort):
    """记忆文件存储实现 — 组合注入FileMemoryAdapter + IndexManager。"""

    def __init__(self, file_adapter: L0StoragePort, index_manager: IndexManagerPort):
        self._file = file_adapter      # 组合注入Rule 3适配器
        self._index = index_manager     # 组合注入索引管理

    # === 继承的L0StoragePort方法 — 委托 ===

    async def write(self, memory_id, memory_type, content) -> bool:
        return await self._file.write(memory_id, memory_type, content)

    async def read(self, memory_id, memory_type) -> str:
        return await self._file.read(memory_id, memory_type)

    async def delete(self, memory_id, memory_type) -> bool:
        return await self._file.delete(memory_id, memory_type)

    async def exists(self, memory_id, memory_type) -> bool:
        return await self._file.exists(memory_id, memory_type)

    async def list_memories(self, memory_type) -> list[str]:
        return await self._file.list_memories(memory_type)

    # === MemoryFilePort扩展方法 ===

    async def update_index(self, entry: str, max_lines: int = 200) -> None:
        await self._index.update_entry(entry, max_lines)

    async def remove_from_index(self, memory_id: str) -> None:
        await self._index.remove_entry(memory_id)
```

---

## L1 缓存存储

### Rule 1: Domain Layer — L1CachePort（已有）

```python
# src/domain/ports/l1_cache.py — 已有，无需修改

class L1CachePort(Protocol):
    async def get(self, memory_type: str, owner_id: str, name: str) -> str | None: ...
    async def set(self, memory_type: str, owner_id: str, name: str,
                  content: str, ttl: int | None = None) -> bool: ...
    async def delete(self, memory_type: str, owner_id: str, name: str) -> bool: ...
    async def invalidate_pattern(self, memory_type: str, owner_id: str) -> int: ...
```

### Rule 2: Application Layer — SessionCachePort

```python
# src/application/ports/session_cache_port.py — 新增

from typing import Protocol
from src.domain.ports.l1_cache import L1CachePort

class SessionCachePort(L1CachePort, Protocol):
    """会话缓存端口 — 继承L1CachePort，添加会话管理语义。

    继承所有L1方法，额外提供：
    - 会话状态save/load语义
    - 会话TTL管理
    """

    async def save_session(self, session_id: str, agent_id: str,
                           state: dict, ttl: int = 86400) -> None:
        """保存会话状态。"""
        ...

    async def load_session(self, session_id: str) -> dict | None:
        """加载会话状态。"""
        ...

    async def delete_session(self, session_id: str) -> None:
        """删除会话。"""
        ...

    async def session_exists(self, session_id: str) -> bool:
        """检查会话是否存在。"""
        ...
```

**注意**: `SemanticCache` 的 `get(query_embedding, threshold)` 签名与 `L1CachePort.get(memory_type, owner_id, name)` 不兼容，**不能继承**。SemanticCache 作为独立应用端口存在，其内部实现可**组合注入** `L1CachePort` 复用Redis连接。

### Rule 3: Infrastructure Layer-1 — RedisCacheAdapter（已有 RedisMemoryCache）

```
src/infrastructure/storage/redis/redis_memory_cache.py
  RedisMemoryCache(L1CachePort) — redis.asyncio, 注入aioredis.Redis
  连接管理: 外部注入Redis客户端（ConnectionPool由调用方管理）
```

### Rule 4: Infrastructure Layer-2 — RedisSessionCache

```python
# src/infrastructure/storage/redis/session_cache.py — 新增

from src.application.ports.session_cache_port import SessionCachePort
from src.domain.ports.l1_cache import L1CachePort

class RedisSessionCache(SessionCachePort):
    """Redis会话缓存实现 — 组合注入RedisCacheAdapter。"""

    def __init__(self, cache_adapter: L1CachePort):
        self._cache = cache_adapter  # 组合注入Rule 3适配器

    # === 继承的L1CachePort方法 — 委托 ===

    async def get(self, memory_type, owner_id, name) -> str | None:
        return await self._cache.get(memory_type, owner_id, name)

    async def set(self, memory_type, owner_id, name, content, ttl=None) -> bool:
        return await self._cache.set(memory_type, owner_id, name, content, ttl)

    async def delete(self, memory_type, owner_id, name) -> bool:
        return await self._cache.delete(memory_type, owner_id, name)

    async def invalidate_pattern(self, memory_type, owner_id) -> int:
        return await self._cache.invalidate_pattern(memory_type, owner_id)

    # === SessionCachePort扩展方法 — 会话语义 ===

    async def save_session(self, session_id, agent_id, state, ttl=86400) -> None:
        import json
        data = json.dumps({"agent_id": agent_id, "state": state})
        await self._cache.set("session", session_id, session_id, data, ttl)

    async def load_session(self, session_id) -> dict | None:
        import json
        data = await self._cache.get("session", session_id, session_id)
        if data is None:
            return None
        return json.loads(data)

    async def delete_session(self, session_id) -> None:
        await self._cache.delete("session", session_id, session_id)

    async def session_exists(self, session_id) -> bool:
        data = await self._cache.get("session", session_id, session_id)
        return data is not None
```

---

## L2 关系数据库

### Rule 1: Domain Layer — L2RdbPort + 具体仓储端口（已有）

```python
# src/domain/ports/base.py — 已有
class BaseRepository[T](Protocol):
    async def get_by_id(self, id: UUID) -> T | None: ...
    async def save(self, entity: T) -> None: ...
    async def delete(self, id: UUID) -> None: ...
    async def list_all(self) -> list[T]: ...

# src/domain/ports/l2_rdb.py — 已有
class L2MetadataRepositoryPort(Protocol): ...
class L2ChangeHistoryRepositoryPort(Protocol): ...
class L2GroupMemberRepositoryPort(Protocol): ...
```

### Rule 2: Application Layer — MemoryMetadataPort（已有，命名规范化）

当前 `L2MetadataRepositoryPort` 已在 domain 层，且包含业务语义。按规则2，可将其提升为应用端口：

```python
# src/application/ports/memory_metadata_port.py — 新增

from typing import Protocol
from src.domain.ports.base import BaseRepository
from src.domain.entities.memory_metadata import MemoryMetadata

class MemoryMetadataPort(BaseRepository[MemoryMetadata], Protocol):
    """记忆元数据端口 — 继承BaseRepository，添加记忆业务语义。

    继承: get_by_id, save, delete, list_all
    扩展: get_by_name, list_by_user, list_by_type
    """

    async def get_by_name(self, name: str) -> MemoryMetadata | None: ...
    async def list_by_user(self, user_id: str) -> list[MemoryMetadata]: ...
    async def list_by_type(self, memory_type: str) -> list[MemoryMetadata]: ...
```

### Rule 3: Infrastructure Layer-1 — PostgreSQLBaseRepository

```python
# src/infrastructure/storage/postgresql/repository/base_repository.py — 已有
# 提供泛型CRUD: get_by_id, save, delete, list_all
```

### Rule 4: Infrastructure Layer-2 — PostgreSQLMemoryMetadataRepository

```python
# src/infrastructure/storage/postgresql/repository/memory_metadata_repository.py — 已有
# 继承PgBaseRepository，扩展: get_by_name, list_by_user, list_by_type
# 组合注入: AsyncSession（由DatabaseEngine提供）
```

**L2特殊性**: PostgreSQL的Session管理已由 `DatabaseEngine` 统一提供，Repository直接接收Session，无需额外连接管理层。

---

## L3 向量存储

### Rule 1: Domain Layer — L3VectorPort（已有）

```python
# src/domain/ports/l3_vector.py — 已有

class L3VectorPort(Protocol):
    async def upsert_points(self, collection, points) -> bool: ...
    async def delete_points(self, collection, point_ids) -> bool: ...
    async def get_point(self, collection, point_id) -> dict | None: ...
    async def search(self, collection, query_vector, limit, filter_payload) -> list[dict]: ...
    async def search_sparse(self, collection, sparse_vector, limit, filter_payload) -> list[dict]: ...
    async def create_collection(self, collection, vector_size, vector_params) -> bool: ...
    async def delete_collection(self, collection) -> bool: ...
    async def collection_exists(self, collection) -> bool: ...
    async def list_collections(self) -> list[str]: ...
```

### Rule 2: Application Layer — MemoryVectorPort

```python
# src/application/ports/memory_vector_port.py — 新增

from typing import Protocol
from src.domain.ports.l3_vector import L3VectorPort

class MemoryVectorPort(L3VectorPort, Protocol):
    """记忆向量端口 — 继承L3VectorPort，添加记忆检索语义。

    继承所有L3方法，额外提供：
    - 记忆向量自动索引（embedding + 存储一步完成）
    - 语义相似记忆检索
    - 按用户/类型过滤
    """

    async def index_memory(
        self,
        memory_id: str,
        content: str,
        memory_type: str,
        owner_id: str,
    ) -> bool:
        """索引记忆内容（自动生成embedding并存储）。"""
        ...

    async def search_similar_memories(
        self,
        query: str,
        owner_id: str | None = None,
        memory_type: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """语义相似记忆检索。"""
        ...
```

### Rule 3: Infrastructure Layer-1 — QdrantVectorAdapter（已有）

```
src/infrastructure/storage/qdrant/
├── client.py               QdrantClientWrapper — 延迟初始化、健康检查
├── collection_manager.py   QdrantCollectionManager — Collection生命周期
├── vector_storage.py        QdrantVectorStorage — 核心向量操作
├── bm25_builder.py          BM25稀疏向量构建
├── models.py                VectorPoint, SparseVector
└── qdrant_vector_adapter.py QdrantVectorAdapter(L3VectorPort) — 薄适配器
    连接管理: QdrantClientWrapper（延迟初始化AsyncQdrantClient）
```

**需补全**: QdrantVectorAdapter 添加 `collection_manager` 参数，实现 Collection 方法。

### Rule 4: Infrastructure Layer-2 — QdrantMemoryVectorStorage

```python
# src/infrastructure/storage/qdrant/memory_vector_storage.py — 新增

from src.application.ports.memory_vector_port import MemoryVectorPort
from src.domain.ports.l3_vector import L3VectorPort

class QdrantMemoryVectorStorage(MemoryVectorPort):
    """Qdrant记忆向量存储 — 组合注入QdrantVectorAdapter。"""

    COLLECTION_NAME = "sisys_memories"

    def __init__(self, vector_adapter: L3VectorPort, embedding_service=None):
        self._adapter = vector_adapter  # 组合注入Rule 3适配器
        self._embedding = embedding_service

    # === 继承的L3VectorPort方法 — 委托 ===

    async def upsert_points(self, collection, points) -> bool:
        return await self._adapter.upsert_points(collection, points)

    async def delete_points(self, collection, point_ids) -> bool:
        return await self._adapter.delete_points(collection, point_ids)

    # ... 其他L3方法同理委托 ...

    # === MemoryVectorPort扩展方法 — 业务语义 ===

    async def index_memory(self, memory_id, content, memory_type, owner_id) -> bool:
        if self._embedding is None:
            return False
        vector = await self._embedding.embed(content)
        point = {
            "id": memory_id,
            "vector": vector,
            "payload": {"memory_type": memory_type, "owner_id": owner_id},
        }
        return await self._adapter.upsert_points(self.COLLECTION_NAME, [point])

    async def search_similar_memories(self, query, owner_id=None,
                                       memory_type=None, limit=10) -> list[dict]:
        if self._embedding is None:
            return []
        vector = await self._embedding.embed(query)
        filter_payload = {}
        if owner_id:
            filter_payload["owner_id"] = owner_id
        if memory_type:
            filter_payload["memory_type"] = memory_type
        return await self._adapter.search(
            self.COLLECTION_NAME, vector, limit, filter_payload or None
        )
```

---

## L5 图存储

### Rule 1: Domain Layer — L5GraphPort（已有）

```python
# src/domain/ports/l5_graph.py — 已有

class L5GraphPort(Protocol):
    async def create_entity(self, memory_id, entity_type, properties) -> bool: ...
    async def get_entity(self, memory_id) -> dict | None: ...
    async def delete_entity(self, memory_id) -> bool: ...
    async def create_relationship(self, source, target, rel_type, properties) -> bool: ...
    async def delete_relationship(self, source, target, rel_type) -> bool: ...
    async def find_related(self, memory_id, max_depth, rel_type) -> list[dict]: ...
    async def execute_query(self, cypher, params) -> list[dict]: ...
    async def execute_write_query(self, cypher, params) -> list[dict]: ...
    async def get_neighbors(self, memory_id, max_depth, edge_type) -> list[dict]: ...
```

### Rule 2: Application Layer — MemoryGraphPort

```python
# src/application/ports/memory_graph_port.py — 新增

from typing import Protocol
from src.domain.ports.l5_graph import L5GraphPort

class MemoryGraphPort(L5GraphPort, Protocol):
    """记忆图端口 — 继承L5GraphPort，添加记忆关系语义。

    继承所有L5方法，额外提供：
    - 记忆关系自动提取（内容→实体→关系）
    - 知识图谱查询
    """

    async def index_memory_relations(
        self,
        memory_id: str,
        content: str,
    ) -> int:
        """提取并索引记忆中的实体关系。返回创建的关系数量。"""
        ...

    async def get_knowledge_graph(
        self,
        memory_id: str,
        depth: int = 2,
    ) -> dict:
        """获取记忆的知识图谱子图。"""
        ...
```

### Rule 3: Infrastructure Layer-1 — Neo4jAdapter（已有）

```
src/infrastructure/storage/neo4j/
├── client.py          Neo4jClientWrapper — 延迟初始化AsyncDriver、连接池
├── graph_storage.py   Neo4jGraphStorage — Cypher执行、路径遍历、邻居查询
└── neo4j_adapter.py   Neo4jAdapter(L5GraphPort) — 薄适配器，MERGE语义
    连接管理: Neo4jClientWrapper（延迟初始化AsyncDriver）
```

**需补全**: Neo4jAdapter 实现 `get_neighbors` 方法。

### Rule 4: Infrastructure Layer-2 — Neo4jMemoryGraphStorage

```python
# src/infrastructure/storage/neo4j/memory_graph_storage.py — 新增

from src.application.ports.memory_graph_port import MemoryGraphPort
from src.domain.ports.l5_graph import L5GraphPort

class Neo4jMemoryGraphStorage(MemoryGraphPort):
    """Neo4j记忆图存储 — 组合注入Neo4jAdapter。"""

    def __init__(self, graph_adapter: L5GraphPort):
        self._adapter = graph_adapter  # 组合注入Rule 3适配器

    # === 继承的L5GraphPort方法 — 委托 ===

    async def create_entity(self, memory_id, entity_type, properties) -> bool:
        return await self._adapter.create_entity(memory_id, entity_type, properties)

    # ... 其他L5方法同理委托 ...

    # === MemoryGraphPort扩展方法 ===

    async def index_memory_relations(self, memory_id, content) -> int:
        # 使用NLP/LLM提取实体和关系，然后调用适配器创建
        ...

    async def get_knowledge_graph(self, memory_id, depth=2) -> dict:
        related = await self._adapter.find_related(memory_id, max_depth=depth)
        neighbors = await self._adapter.get_neighbors(memory_id, max_depth=depth)
        return {"entities": related, "connections": neighbors}
```

---

## 统一存储网关

```python
# src/application/services/unified_storage_gateway.py — 调整

class UnifiedStorageGateway(UnifiedStoragePort):
    """统一存储网关 — 组合注入所有应用端口（Rule 2端口）。"""

    def __init__(
        self,
        memory_file: MemoryFilePort,        # Rule 2应用端口
        session_cache: SessionCachePort,     # Rule 2应用端口
        memory_metadata: MemoryMetadataPort, # Rule 2应用端口
        # 以下可选
        memory_vector: MemoryVectorPort | None = None,
        document_storage: DocumentStoragePort | None = None,
        memory_graph: MemoryGraphPort | None = None,
    ):
        self._file = memory_file
        self._cache = session_cache
        self._metadata = memory_metadata
        self._vector = memory_vector
        self._docs = document_storage
        self._graph = memory_graph
```

**关键变化**: Gateway 现在依赖**应用端口**（Rule 2），而非直接依赖基础端口（Rule 1）。通过应用端口获得业务语义，同时底层自动拥有基础存储能力。

---

## Composition Root 注册

```python
# src/composition_root.py

def bootstrap() -> None:
    # === Rule 3: 基础端口实现注册 ===
    register_port(name="l0_file", interface=L0StoragePort,
                  impl=FileMemoryAdapter, ...)
    register_port(name="l1_cache", interface=L1CachePort,
                  impl=RedisMemoryCache, ...)
    register_port(name="l2_pg_base", interface=BaseRepository,
                  impl=PgBaseRepository, ...)
    register_port(name="l3_vector", interface=L3VectorPort,
                  impl=QdrantVectorAdapter, ...)
    register_port(name="l4_object", interface=L4ObjectPort,
                  impl=MinIOAdapter, ...)
    register_port(name="l5_graph", interface=L5GraphPort,
                  impl=Neo4jAdapter, ...)

    # === Rule 4: 应用端口实现注册（组合注入Rule 3适配器） ===
    register_port(name="memory_file", interface=MemoryFilePort,
                  impl=MemoryFileStorage, ...)          # ← 注入l0_file
    register_port(name="session_cache", interface=SessionCachePort,
                  impl=RedisSessionCache, ...)          # ← 注入l1_cache
    register_port(name="memory_metadata", interface=MemoryMetadataPort,
                  impl=PostgreSQLMemoryMetadataRepository, ...)
    register_port(name="memory_vector", interface=MemoryVectorPort,
                  impl=QdrantMemoryVectorStorage, ...)  # ← 注入l3_vector
    register_port(name="document_storage", interface=DocumentStoragePort,
                  impl=MinIODocumentStorage, ...)       # ← 注入l4_object
    register_port(name="memory_graph", interface=MemoryGraphPort,
                  impl=Neo4jMemoryGraphStorage, ...)    # ← 注入l5_graph

    # === 统一网关 ===
    register_port(name="unified_storage", interface=UnifiedStoragePort,
                  impl=UnifiedStorageGateway, ...)      # ← 注入所有应用端口
```

---

## 详细执行步骤

### Phase 1: Rule 1 — 端口抽象完善

- [ ] 1.1 废弃 `ObjectStorageRepository`（`src/domain/ports/storage.py`标记deprecated）
- [ ] 1.2 修改 `MinIORepository` 基类为 `L4ObjectPort`
- [ ] 1.3 修复 `MinIORepository.archive()` 签名（添加content参数，返回str）
- [ ] 1.4 补全 `__init__.py` 导出至100%
- [ ] 1.5 所有Protocol端口添加 `@runtime_checkable`
- [ ] 1.6 验证: 所有端口可导入且ContractGate可工作

### Phase 2: Rule 2 — 应用端口定义

- [ ] 2.1 新增 `src/application/ports/memory_file_port.py` — MemoryFilePort(L0StoragePort)
- [ ] 2.2 新增 `src/application/ports/session_cache_port.py` — SessionCachePort(L1CachePort)
- [ ] 2.3 新增 `src/application/ports/memory_metadata_port.py` — MemoryMetadataPort(BaseRepository[T])
- [ ] 2.4 新增 `src/application/ports/memory_vector_port.py` — MemoryVectorPort(L3VectorPort)
- [ ] 2.5 新增 `src/application/ports/document_storage_port.py` — DocumentStoragePort(L4ObjectPort)
- [ ] 2.6 新增 `src/application/ports/memory_graph_port.py` — MemoryGraphPort(L5GraphPort)
- [ ] 2.7 验证: 所有应用端口继承基础端口，方法签名兼容

### Phase 3: Rule 3 — 基础端口实现完善

- [ ] 3.1 补全 `QdrantVectorAdapter` 的 Collection 方法（注入 `QdrantCollectionManager`）
- [ ] 3.2 补全 `MinIOAdapter` 的 `list_objects` 方法
- [ ] 3.3 修复 `MinIOAdapter.archive()` 签名
- [ ] 3.4 补全 `Neo4jAdapter` 的 `get_neighbors` 方法
- [ ] 3.5 创建统一 `ConnectionManager` 抽象基类
- [ ] 3.6 注册所有 Rule 3 基础端口到 Composition Root
- [ ] 3.7 验证: 所有基础端口有实现且可解析

### Phase 4: Rule 4 — 应用端口实现

- [ ] 4.1 新增 `src/infrastructure/storage/memory_file_storage.py` — MemoryFileStorage(MemoryFilePort)
- [ ] 4.2 新增 `src/infrastructure/storage/redis/session_cache.py` — RedisSessionCache(SessionCachePort)
- [ ] 4.3 调整 `PostgreSQLMemoryMetadataRepository` 实现 MemoryMetadataPort
- [ ] 4.4 新增 `src/infrastructure/storage/qdrant/memory_vector_storage.py` — QdrantMemoryVectorStorage(MemoryVectorPort)
- [ ] 4.5 新增 `src/infrastructure/storage/minio/document_storage.py` — MinIODocumentStorage(DocumentStoragePort)
- [ ] 4.6 新增 `src/infrastructure/storage/neo4j/memory_graph_storage.py` — Neo4jMemoryGraphStorage(MemoryGraphPort)
- [ ] 4.7 注册所有 Rule 4 应用端口到 Composition Root
- [ ] 4.8 调整 `UnifiedStorageGateway` 依赖应用端口
- [ ] 4.9 验证: 所有应用端口有实现，Gateway可正确注入

### Phase 5: 清理与测试

- [ ] 5.1 删除废弃接口（ObjectStorageRepository）
- [ ] 5.2 更新现有代码引用
- [ ] 5.3 创建端口契约测试
- [ ] 5.4 创建架构约束测试（四层规则合规）
- [ ] 5.5 端到端集成验证

---

## 关键文件清单

| 文件 | 类型 | Phase | 规则 |
|------|------|-------|------|
| `src/domain/ports/l{0-5}_*.py` | 修改（@runtime_checkable） | Phase 1 | Rule 1 |
| `src/domain/ports/storage.py` | 废弃 | Phase 1 | Rule 1 |
| `src/domain/ports/__init__.py` | 补全导出 | Phase 1 | Rule 1 |
| `src/application/ports/memory_file_port.py` | **新增** | Phase 2 | Rule 2 |
| `src/application/ports/session_cache_port.py` | **新增** | Phase 2 | Rule 2 |
| `src/application/ports/memory_metadata_port.py` | **新增** | Phase 2 | Rule 2 |
| `src/application/ports/memory_vector_port.py` | **新增** | Phase 2 | Rule 2 |
| `src/application/ports/document_storage_port.py` | **新增** | Phase 2 | Rule 2 |
| `src/application/ports/memory_graph_port.py` | **新增** | Phase 2 | Rule 2 |
| `src/infrastructure/storage/qdrant/qdrant_vector_adapter.py` | 修改 | Phase 3 | Rule 3 |
| `src/infrastructure/storage/minio/minio_adapter.py` | 修改 | Phase 3 | Rule 3 |
| `src/infrastructure/storage/neo4j/neo4j_adapter.py` | 修改 | Phase 3 | Rule 3 |
| `src/infrastructure/storage/connection_manager.py` | **新增** | Phase 3 | Rule 3 |
| `src/infrastructure/storage/memory_file_storage.py` | **新增** | Phase 4 | Rule 4 |
| `src/infrastructure/storage/redis/session_cache.py` | **新增** | Phase 4 | Rule 4 |
| `src/infrastructure/storage/qdrant/memory_vector_storage.py` | **新增** | Phase 4 | Rule 4 |
| `src/infrastructure/storage/minio/document_storage.py` | **新增** | Phase 4 | Rule 4 |
| `src/infrastructure/storage/neo4j/memory_graph_storage.py` | **新增** | Phase 4 | Rule 4 |
| `src/composition_root.py` | 修改 | Phase 3-4 | Rule 3-4 |
| `src/application/services/unified_storage_gateway.py` | 修改 | Phase 4 | Rule 4 |

---

## 验证方案

```bash
# Rule 1: 端口抽象
poetry run python -c "from src.domain.ports import *; print('Rule 1 OK')"

# Rule 2: 应用端口继承
poetry run python -c "
from src.application.ports.document_storage_port import DocumentStoragePort
from src.domain.ports.l4_object import L4ObjectPort
assert issubclass(DocumentStoragePort, L4ObjectPort)  # 继承关系
print('Rule 2 OK')
"

# Rule 3: 基础实现可解析
poetry run python -c "
from src.composition_root import bootstrap
from src.domain.ports.registry import _global_registry
bootstrap()
for p in ['l0_file','l1_cache','l3_vector','l4_object','l5_graph']:
    assert _global_registry.get(p), f'{p} not registered'
print('Rule 3 OK')
"

# Rule 4: 应用端口实现可解析
poetry run python -c "
from src.composition_root import bootstrap
from src.domain.ports.registry import _global_registry
bootstrap()
for p in ['memory_file','session_cache','memory_vector',
           'document_storage','memory_graph']:
    assert _global_registry.get(p), f'{p} not registered'
print('Rule 4 OK')
"
```

---

## 时间估算

| Phase | 规则 | 工时 | 风险 |
|-------|------|------|------|
| Phase 1 | Rule 1 | 3-4h | 低 |
| Phase 2 | Rule 2 | 4-6h | 低 |
| Phase 3 | Rule 3 | 4-6h | 中 |
| Phase 4 | Rule 4 | 6-8h | 中 |
| Phase 5 | 测试 | 3-4h | 低 |
| **总计** | — | **20-28h** | — |
