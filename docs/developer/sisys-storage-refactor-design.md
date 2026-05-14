# SISYS 存储子系统重构详细设计与执行方案

**文档版本:** v4.4 (Round 3架构约束验证)
**生成时间:** 2026-05-14
**审查状态:** Round 3 完成 — 统一Rule 1/4签名风格，L3/L5完整签名匹配实际代码

---

## 四条设计规则与四层架构映射

| 规则 | 架构层 | 职责 | 位置 |
|------|--------|------|------|
| **1** | Domain Layer | 统一抽象存储基础端口 `L[n][XXX]Port`，零依赖，技术无关 | `src/domain/ports/` |
| **2** | Domain + Application Layer | 具体应用端口**继承或组合注入**基础端口，定义业务语义 | `src/domain/ports/` + `src/application/ports/` |
| **3** | Infrastructure Layer-1 | 基础端口的技术实现 + 连接管理，可替换 | `src/infrastructure/storage/{tech}/` |
| **4** | Infrastructure Layer-2 | 应用端口的技术实现，**组合注入**Layer-1适配器 | `src/infrastructure/storage/{tech}/` |

---

## 架构总览（六层存储 × 四层规则）

```
┌─────────────────────────────────────────────────────────────────────┐
│  Rule 1: Domain Layer — 存储基础端口（技术无关，零依赖）               │
│                                                                      │
│  L0StoragePort     L1CachePort       L2RdbPort[T]                     │
│  (5 async)         (4 async)         (4 async泛型CRUD)                │
│  L3VectorPort      L4ObjectPort      L5GraphPort                      │
│  (9 async)         (5 async+1 sync)  (9 async)                        │
│  UnifiedStoragePort（组合注入L0-L5）                                  │
│  BaseRepository[T]（遗留sync，需重构为L2RdbPort[T]）                    │
│                                                                      │
│  位置: src/domain/ports/l{n}_{xxx}.py                                │
│  ⚠️ 无@runtime_checkable，ContractGate运行时验证需Phase 1补全          │
└─────────────────────────────────────────────────────────────────────┘
                              ↑ 继承
┌─────────────────────────────────────────────────────────────────────┐
│  Rule 2: Domain + Application Layer — 具体应用端口                    │
│                  （继承或组合注入基础端口+业务语义）                     │
│                                                                      │
│  ──── domain/ports/ 中的具体端口（L2领域概念）────                     │
│  继承L2: L2MetadataRepositoryPort(L2RdbPort[MemoryMetadata])         │
│          L2ChangeHistoryRepositoryPort(L2RdbPort[MemoryChangeHistory])│
│          L2GroupMemberRepositoryPort(Protocol，组合注入L2RdbPort)      │
│                                                                      │
│  ──── application/ports/ 中的具体端口（应用层语义）────                │
│  继承L0: MemoryFilePort(L0StoragePort)                                │
│  继承L1: SessionCachePort(L1CachePort)                               │
│  继承L3: MemoryVectorPort(L3VectorPort)                              │
│  继承L4: DocumentStoragePort(L4ObjectPort)                           │
│  继承L5: MemoryGraphPort(L5GraphPort)                                │
│                                                                      │
│  位置: src/domain/ports/l2_rdb.py (L2具体端口)                        │
│        src/application/ports/ (其他层级具体端口)                       │
└─────────────────────────────────────────────────────────────────────┘
                              ↑ 实现
┌─────────────────────────────────────────────────────────────────────┐
│  Rule 3: Infrastructure Layer-1 — 基础端口实现 + 连接管理              │
│                                                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │
│  │ FileAdapter  │ │ RedisAdapter │ │ PostgreSQL   │                 │
│  │ (L0StoragePort)│ │ (L1CachePort)│ │ Adapter(L2Rdb)│                 │
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
│  │ PgMetadataRepo       │ │ QdrantMemoryVector    │                  │
│  │ (L2MetadataRepoPort) │ │ (MemoryVectorPort)    │                  │
│  │ ← 继承 PgAdapter     │ │ ← 组合 QdrantAdapter │                  │
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

L4ObjectPort(Protocol)  # 已有，保持不变，无@runtime_checkable
  ├── store(bucket_type: str, object_key: str, file_path: str,
  │          content_type: str = "application/octet-stream",
  │          tags: dict[str, str] | None = None) → str
  ├── retrieve(bucket_type: str, object_key: str,
  │            version_id: str | None = None) → AsyncIterator[bytes]  # sync方法
  ├── delete(bucket_type: str, object_key: str,
  │          version_id: str | None = None) → bool
  ├── get_metadata(bucket_type: str, object_key: str,
  │                version_id: str | None = None) → dict
  ├── archive(bucket_type: str, object_key: str,
  │           content: bytes | None = None,          # 可选content
  │           retention_days: int = 2555) → str       # 返回str(非bool)
  └── list_objects(bucket_type: str, prefix: str = "",
                   recursive: bool = True) → list[dict]
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
├── client_adapter.py        MinioClientAdapter — 延迟初始化sync Minio客户端、健康检查
├── bucket_manager.py         BucketManager — Bucket CRUD、命名验证、WORM配置
├── worm_lifecycle.py         WORMManager — 合规锁定、生命周期管理
├── object_operations.py      ObjectOperations — 流式上传/下载、分片上传、断点续传
├── entities.py               MinIO实体定义
├── minio_repository.py       MinIORepository — 组合上述组件，实现ObjectStorageRepository
│                            ⚠️ 当前实现ObjectStorageRepository(遗留)，非L4ObjectPort
│                            ⚠️ archive()返回bool且无content参数（与L4ObjectPort不匹配）
└── minio_adapter.py          MinIOAdapter(L4ObjectPort) — 薄适配器，委托Repository
                             ⚠️ archive()静默丢弃content参数，bool→str隐式转换
                             ⚠️ 缺少list_objects()方法（底层Repository已有）
```

**连接管理**: MinioClientAdapter 已实现延迟初始化 + 健康检查。注意：使用**同步**Minio客户端。

**⚠️ Phase 3需修复**: 将MinIORepository基类改为L4ObjectPort，修复archive签名，补全list_objects委托。

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

    def retrieve(self, bucket_type, object_key, **kwargs):
        # retrieve是sync方法（返回AsyncIterator），不可await
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

    async def update_index(self, entry: dict) -> None:
        """更新MEMORY.md索引。entry为索引条目dict。"""
        ...

    async def remove_from_index(self, memory_id: str) -> None:
        """从索引移除条目。"""
        ...

    async def search_index(self, query: str) -> list[dict]:
        """搜索索引。"""
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

    async def write(self, memory_id: str, memory_type: str, content: str) -> bool:
        return await self._file.write(memory_id, memory_type, content)

    async def read(self, memory_id: str, memory_type: str) -> str:
        return await self._file.read(memory_id, memory_type)

    async def delete(self, memory_id: str, memory_type: str) -> bool:
        return await self._file.delete(memory_id, memory_type)

    async def exists(self, memory_id: str, memory_type: str) -> bool:
        return await self._file.exists(memory_id, memory_type)

    async def list_memories(self, memory_type: str) -> list[str]:
        return await self._file.list_memories(memory_type)

    # === MemoryFilePort扩展方法 ===

    async def update_index(self, entry: dict) -> None:
        await self._index.update_entry(entry)

    async def remove_from_index(self, memory_id: str) -> None:
        await self._index.remove_entry(memory_id)

    async def search_index(self, query: str) -> list[dict]:
        return await self._index.search(query)
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

    async def get(self, memory_type: str, owner_id: str, name: str) -> str | None:
        return await self._cache.get(memory_type, owner_id, name)

    async def set(self, memory_type: str, owner_id: str, name: str,
                  content: str, ttl: int | None = None) -> bool:
        return await self._cache.set(memory_type, owner_id, name, content, ttl)

    async def delete(self, memory_type: str, owner_id: str, name: str) -> bool:
        return await self._cache.delete(memory_type, owner_id, name)

    async def invalidate_pattern(self, memory_type: str, owner_id: str) -> int:
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

### Rule 1: Domain Layer — L2RdbPort[T]（重构BaseRepository）

**⚠️ 两个同名 BaseRepository 需区分**:
- **Domain层** `BaseRepository[T]`(src/domain/ports/base.py): Protocol，方法为**sync**，**无人继承**，将重命名为`L2RdbPort[T]`并改async
- **Infrastructure层** `BaseRepository[T]`(src/infrastructure/storage/postgresql/repository/base_repository.py): 具体类，方法已为**async**，被UserRepository/PermissionRepository继承，将重构为`PostgreSQLAdapter[TEntity,TModel]`

**当前状态**: Domain层`BaseRepository[T]`是sync泛型CRUD基座，但L2全部实际端口(Metadata/ChangeHistory/GroupMember)均为async。没有任何L2端口继承它。

**按规则1重构**: 将Domain层`BaseRepository[T]`重构为`L2RdbPort[T]`(async)，作为L2统一基础端口。

```python
# src/domain/ports/base.py — 重构
# 重命名: BaseRepository[T] → L2RdbPort[T]
# 重构: sync方法全部改为async

@runtime_checkable
class L2RdbPort(Generic[T], Protocol):
    """L2关系数据库统一基础端口 — 泛型async CRUD。"""

    async def get_by_id(self, id: UUID) -> T | None: ...
    async def save(self, entity: T) -> None: ...
    async def delete(self, id: UUID) -> None: ...
    async def list_all(self) -> list[T]: ...
```

**遗留兼容**: `BaseRepository`标记deprecated，别名指向`L2RdbPort`。

### Rule 2: Application Layer — 三个具体端口继承或组合L2RdbPort[T]

```python
# src/domain/ports/l2_rdb.py — 重构（从独立Protocol改为继承L2RdbPort）

# 1. L2MetadataRepositoryPort — 继承L2RdbPort[MemoryMetadata]
class L2MetadataRepositoryPort(L2RdbPort[MemoryMetadata], Protocol):
    """记忆元数据端口 — 继承L2RdbPort，扩展记忆业务方法。

    继承: get_by_id, save, delete, list_all（全部async）
    扩展: get_by_name, list_by_user, list_by_type
    """
    async def get_by_name(self, name: str) -> MemoryMetadata | None: ...
    async def list_by_user(self, user_id: str) -> list[MemoryMetadata]: ...
    async def list_by_type(self, memory_type: str) -> list[MemoryMetadata]: ...

# 2. L2ChangeHistoryRepositoryPort — 继承L2RdbPort[MemoryChangeHistory]
class L2ChangeHistoryRepositoryPort(L2RdbPort[MemoryChangeHistory], Protocol):
    """变更历史端口 — 继承L2RdbPort，扩展历史查询方法。

    继承: get_by_id, save, delete, list_all（全部async）
    注意: delete在Protocol层作为签名约束存在，实现层覆写为raise NotImplementedError(append-only)
    扩展: get_by_memory_id
    """
    async def get_by_memory_id(self, memory_id: UUID) -> list[MemoryChangeHistory]: ...

# 3. L2GroupMemberRepositoryPort — 组合注入L2RdbPort（方法无交集，不继承）
class L2GroupMemberRepositoryPort(Protocol):
    """组成员端口 — 无CRUD交集，独立Protocol。

    注意: is_group_member/is_group_admin/add_member/remove_member
    与L2RdbPort[T]的CRUD模式无交集，无法继承，保持独立Protocol。
    实现层可组合注入L2RdbPort复用基础设施。
    """
    async def is_group_member(self, group_id: str, user_id: str) -> bool: ...
    async def is_group_admin(self, group_id: str, user_id: str) -> bool: ...
    async def add_member(self, group_id: str, user_id: str, role: str = "member") -> None: ...
    async def remove_member(self, group_id: str, user_id: str) -> None: ...
```

### Rule 3: Infrastructure Layer-1 — PostgreSQLAdapter（重构Infrastructure层BaseRepository[T])

**当前问题**: Infrastructure层`BaseRepository[T]`(base_repository.py)绑定ORM模型层，PK列硬编码`id`，无实体转换，无软删除支持。
三个L2仓储因此无法继承它，直接实现端口——**违反四条规则**。

**重构方案**: 将Infrastructure层`BaseRepository[T]`重构为`PostgreSQLAdapter[TEntity, TModel]`双泛型基座，
实现`L2RdbPort[TEntity]`，提供领域实体/ORM模型转换层+可配置行为。

```python
# src/infrastructure/storage/postgresql/repository/base_repository.py — 重构

TEntity = TypeVar("TEntity")
TModel = TypeVar("TModel", bound=Base)

class PostgreSQLAdapter(Generic[TEntity, TModel]):
    """领域仓储基座 — 实现L2RdbPort[TEntity]，提供ORM↔Entity转换。

    子类只需实现:
    - _to_entity(model: TModel) -> TEntity
    - _to_model(entity: TEntity) -> TModel
    - pk_column: str = "id"  （可覆写为"memory_id"等）
    """

    pk_column: str = "id"                    # 可覆写
    soft_delete_column: str | None = None     # 可覆写为"deleted_at"

    def __init__(self, model_class: type[TModel], session: AsyncSession):
        self._model_class = model_class
        self._session = session

    # === 抽象方法 — 子类必须实现 ===

    def _to_entity(self, model: TModel) -> TEntity:
        raise NotImplementedError

    def _to_model(self, entity: TEntity) -> TModel:
        raise NotImplementedError

    # === L2RdbPort[TEntity] 实现 ===

    async def get_by_id(self, id: UUID) -> TEntity | None:
        stmt = select(self._model_class).where(
            getattr(self._model_class, self.pk_column) == id
        )
        stmt = self._apply_soft_delete_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, entity: TEntity) -> None:
        model = self._to_model(entity)
        await self._do_save(model, entity)    # 钩子方法，子类可覆写

    async def delete(self, id: UUID) -> None:
        if self.soft_delete_column:
            await self._soft_delete(id)        # 软删除
        else:
            await self._hard_delete(id)        # 硬删除

    async def list_all(self) -> list[TEntity]:
        stmt = select(self._model_class)
        stmt = self._apply_soft_delete_filter(stmt)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    # === 可覆写钩子方法 ===

    async def _do_save(self, model: TModel, entity: TEntity) -> None:
        """默认简单插入。子类可覆写为UPSERT/乐观锁/append-only。"""
        self._session.add(model)
        await self._session.flush()

    # === 内部工具方法 ===

    def _apply_soft_delete_filter(self, stmt):
        if self.soft_delete_column:
            col = getattr(self._model_class, self.soft_delete_column)
            return stmt.where(col.is_(None))
        return stmt

    async def _soft_delete(self, id: UUID) -> None:
        from datetime import datetime, timezone
        stmt = update(self._model_class).where(
            getattr(self._model_class, self.pk_column) == id
        ).values(**{self.soft_delete_column: datetime.now(timezone.utc)})
        await self._session.execute(stmt)
        await self._session.flush()

    async def _hard_delete(self, id: UUID) -> None:
        entity = await self.get_by_id(id)
        if entity:
            await self._session.delete(await self._session.get(
                self._model_class, id))
            await self._session.flush()
```

**UserRepository/PermissionRepository兼容**: 保持继承PostgreSQLAdapter[TModel, TModel]，
`_to_entity`/`_to_model`为恒等转换。

### Rule 4: Infrastructure Layer-2 — 三个L2仓储（继承PostgreSQLAdapter）

```python
# === 1. PostgreSQLMemoryMetadataRepository — 继承PostgreSQLAdapter ===

class PostgreSQLMemoryMetadataRepository(
    PostgreSQLAdapter[MemoryMetadata, MemoryMetadataModel]
):
    pk_column = "memory_id"               # PK列名覆写
    soft_delete_column = "deleted_at"      # 软删除列覆写

    def __init__(self, session: AsyncSession):
        super().__init__(MemoryMetadataModel, session)

    def _to_entity(self, model) -> MemoryMetadata:
        # 已有转换逻辑迁移至此
        ...

    def _to_model(self, entity) -> MemoryMetadataModel:
        # 已有转换逻辑迁移至此
        ...

    async def _do_save(self, model, entity) -> None:
        """覆写为UPSERT + 乐观锁。"""
        existing = await self._find_existing(entity.memory_id)
        if existing:
            if entity.version <= existing.version:
                raise MemoryVersionConflictError(...)
            # UPDATE with version bump
            ...
        else:
            self._session.add(model)
        await self._session.flush()

    # === 继承的L2RdbPort方法（get_by_id/save/delete/list_all自动获得） ===

    # === L2MetadataRepositoryPort扩展方法 ===

    async def get_by_name(self, name: str) -> MemoryMetadata | None:
        stmt = select(MemoryMetadataModel).where(
            MemoryMetadataModel.name == name
        )
        stmt = self._apply_soft_delete_filter(stmt)
        ...

    async def list_by_user(self, user_id: str) -> list[MemoryMetadata]: ...
    async def list_by_type(self, memory_type: str) -> list[MemoryMetadata]: ...


# === 2. PostgreSQLMemoryChangeHistoryRepository — 继承PostgreSQLAdapter ===

class PostgreSQLMemoryChangeHistoryRepository(
    PostgreSQLAdapter[MemoryChangeHistory, MemoryChangeHistoryModel]
):
    def __init__(self, session: AsyncSession):
        super().__init__(MemoryChangeHistoryModel, session)

    async def _do_save(self, model, entity) -> None:
        """覆写为append-only插入（无update路径）。"""
        self._session.add(model)
        await self._session.flush()

    async def delete(self, id: UUID) -> None:
        """变更历史不可删除 — 覆写为空操作或抛异常。"""
        raise NotImplementedError("Change history is append-only")

    # === L2ChangeHistoryRepositoryPort扩展方法 ===

    async def get_by_memory_id(self, memory_id: UUID) -> list[MemoryChangeHistory]: ...


# === 3. PostgreSQLMemoryGroupMemberRepository — 组合注入PostgreSQLAdapter ===

class PostgreSQLMemoryGroupMemberRepository:
    """组成员仓储 — 组合注入PostgreSQLAdapter复用Session管理。

    组合注入而非继承：无单一主键（复合PK: group_id+user_id），
    无标准CRUD方法（is_member/add_member而非get_by_id/save），
    但通过组合注入共享PostgreSQLAdapter的Session基础设施。
    """

    def __init__(self, session: AsyncSession):
        self._session = session   # 共享同一Session

    async def is_group_member(self, group_id: str, user_id: str) -> bool: ...
    async def is_group_admin(self, group_id: str, user_id: str) -> bool: ...
    async def add_member(self, group_id: str, user_id: str, role: str = "member") -> None: ...
    async def remove_member(self, group_id: str, user_id: str) -> None: ...
```

**L2特殊性**:
- PostgreSQLAdapter提供领域实体/ORM模型转换+可配置PK列名+软删除+UPSERT钩子
- MetadataRepository继承：覆写`_do_save`(UPSERT)、`pk_column="memory_id"`、`soft_delete_column="deleted_at"`
- ChangeHistoryRepository继承：覆写`_do_save`(append-only)、`delete`(禁止)
- GroupMemberRepository组合注入：无标准CRUD，共享Session基础设施
- DatabaseEngine统一提供AsyncSession（延迟初始化AsyncEngine, health_check）

**⚠️ Infrastructure层BaseRepository迁移影响**:
- `save()`返回值从`T`变为`None` — UserRepository/PermissionRepository的调用者需检查是否依赖返回值
- `list_all`从`(skip, limit)`变为无参数 — 调用者需检查分页依赖
- `get_by_id`参数从`str`变为`UUID` — 实际上是修复现有类型不一致（UserModel.id已是UUID）
- `count()`方法在新基座中未提供 — 如有调用者使用需在子类中补全

---

## L3 向量存储

### Rule 1: Domain Layer — L3VectorPort（已有）

```python
# src/domain/ports/l3_vector.py — 已有

class L3VectorPort(Protocol):
    async def upsert_points(self, collection: str, points: list[dict]) -> bool: ...
    async def delete_points(self, collection: str, point_ids: list[str]) -> bool: ...
    async def get_point(self, collection: str, point_id: str) -> dict | None: ...
    async def search(self, collection: str, query_vector: list[float],
                     limit: int = 10, filter_payload: dict | None = None) -> list[dict]: ...
    async def search_sparse(self, collection: str, sparse_vector: dict,
                            limit: int = 10, filter_payload: dict | None = None) -> list[dict]: ...
    async def create_collection(self, collection: str, vector_size: int,
                                vector_params: dict | None = None) -> bool: ...
    async def delete_collection(self, collection: str) -> bool: ...
    async def collection_exists(self, collection: str) -> bool: ...
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
├── collection_manager.py   QdrantCollectionManager — Collection生命周期（已有）
├── vector_storage.py        QdrantVectorStorage — 核心向量操作（5方法）
├── bm25_builder.py          BM25稀疏向量构建
├── models.py                VectorPoint, SparseVector
└── qdrant_vector_adapter.py QdrantVectorAdapter(L3VectorPort) — 薄适配器
    连接管理: QdrantClientWrapper（延迟初始化AsyncQdrantClient）
```

**⚠️ 当前缺口**: QdrantVectorAdapter仅实现5/9方法，缺少4个Collection方法：
- `create_collection`, `delete_collection`, `collection_exists`, `list_collections`

**已有组件**: `QdrantCollectionManager`已实现这4个方法，但**未注入Adapter**。

**参数映射表**（CollectionManager → L3VectorPort）:

| QdrantCollectionManager | L3VectorPort | 映射方式 |
|------------------------|--------------|---------|
| `create_collection(name, vector_size, distance, **kwargs)` | `create_collection(collection, vector_size, vector_params)` | `name=collection`, `vector_params→distance+**kwargs` |
| `delete_collection(name)` | `delete_collection(collection)` | `name=collection` |
| `collection_exists(name)` | `collection_exists(collection)` | `name=collection` |
| `list_collections()` | `list_collections()` | 直接委托 |

**Phase 3修复**: 在QdrantVectorAdapter构造函数中注入QdrantCollectionManager，补全委托，参数映射在Adapter层完成。

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

    async def upsert_points(self, collection: str, points: list[dict]) -> bool:
        return await self._adapter.upsert_points(collection, points)

    async def delete_points(self, collection: str, point_ids: list[str]) -> bool:
        return await self._adapter.delete_points(collection, point_ids)

    async def get_point(self, collection: str, point_id: str) -> dict | None:
        return await self._adapter.get_point(collection, point_id)

    async def search(self, collection: str, query_vector: list[float],
                     limit: int = 10, filter_payload: dict | None = None) -> list[dict]:
        return await self._adapter.search(collection, query_vector, limit, filter_payload)

    async def search_sparse(self, collection: str, sparse_vector: dict,
                            limit: int = 10, filter_payload: dict | None = None) -> list[dict]:
        return await self._adapter.search_sparse(collection, sparse_vector, limit, filter_payload)

    async def create_collection(self, collection: str, vector_size: int,
                                vector_params: dict | None = None) -> bool:
        return await self._adapter.create_collection(collection, vector_size, vector_params)

    async def delete_collection(self, collection: str) -> bool:
        return await self._adapter.delete_collection(collection)

    async def collection_exists(self, collection: str) -> bool:
        return await self._adapter.collection_exists(collection)

    async def list_collections(self) -> list[str]:
        return await self._adapter.list_collections()

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
    async def create_entity(self, memory_id: str, entity_type: str,
                            properties: dict[str, Any]) -> bool: ...
    async def get_entity(self, memory_id: str) -> dict | None: ...
    async def delete_entity(self, memory_id: str) -> bool: ...
    async def create_relationship(self, source_memory_id: str, target_memory_id: str,
                                  relationship_type: str,
                                  properties: dict[str, Any] | None = None) -> bool: ...
    async def delete_relationship(self, source_memory_id: str, target_memory_id: str,
                                  relationship_type: str) -> bool: ...
    async def find_related(self, memory_id: str, max_depth: int = 2,
                          relationship_type: str | None = None) -> list[dict]: ...
    async def execute_query(self, cypher: str,
                            params: dict[str, Any] | None = None) -> list[dict]: ...
    async def execute_write_query(self, cypher: str,
                                  params: dict[str, Any] | None = None) -> list[dict]: ...
    async def get_neighbors(self, memory_id: str, max_depth: int = 1,
                            edge_type: str | None = None) -> list[dict]: ...
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
│                     ⚠️ get_neighbors(node_id, rel_type, direction) 签名与L5GraphPort不兼容
│                     ⚠️ L5GraphPort: get_neighbors(memory_id, max_depth, edge_type)
│                     ⚠️ 参数名不同: node_id vs memory_id, direction vs max_depth
├── graph_manager.py   图管理器（遗留）
├── graph_retriever.py 图检索器（遗留）
├── models.py          Neo4j模型
└── neo4j_adapter.py   Neo4jAdapter(L5GraphPort) — 薄适配器，MERGE语义
    连接管理: Neo4jClientWrapper（延迟初始化AsyncDriver）
```

**⚠️ 当前缺口**: Neo4jAdapter缺少`get_neighbors()`方法（8/9实现）。
底层`Neo4jGraphStorage.get_neighbors(node_id, rel_type, direction)`签名与L5GraphPort不兼容。

**⚠️ Cypher注入漏洞**（严重安全问题）:
- `neo4j_adapter.py` 第143行 `create_relationship`: `MERGE (source)-[r:{relationship_type}]->(target)`
- `neo4j_adapter.py` 第173行 `delete_relationship`: `MATCH ... [r:{relationship_type}]`
- `neo4j_adapter.py` 第203/211行 `find_related`: `MATCH ... [:{relationship_type}*1..{max_depth}]`
- `graph_storage.py` 第80-81行 `find_path`: `[*1..{max_depth}]`
- **修复方案**: 使用参数化查询或whitelist验证relationship_type（仅允许字母数字）

**Phase 3修复**: 在Neo4jAdapter中实现`get_neighbors(memory_id, max_depth, edge_type)`，桥接参数映射到底层；修复Cypher注入漏洞。

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

    async def create_entity(self, memory_id: str, entity_type: str,
                            properties: dict[str, Any]) -> bool:
        return await self._adapter.create_entity(memory_id, entity_type, properties)

    async def get_entity(self, memory_id: str) -> dict | None:
        return await self._adapter.get_entity(memory_id)

    async def delete_entity(self, memory_id: str) -> bool:
        return await self._adapter.delete_entity(memory_id)

    async def create_relationship(self, source_memory_id: str, target_memory_id: str,
                                  relationship_type: str,
                                  properties: dict[str, Any] | None = None) -> bool:
        return await self._adapter.create_relationship(
            source_memory_id, target_memory_id, relationship_type, properties)

    async def delete_relationship(self, source_memory_id: str, target_memory_id: str,
                                  relationship_type: str) -> bool:
        return await self._adapter.delete_relationship(
            source_memory_id, target_memory_id, relationship_type)

    async def find_related(self, memory_id: str, max_depth: int = 2,
                          relationship_type: str | None = None) -> list[dict]:
        return await self._adapter.find_related(memory_id, max_depth, relationship_type)

    async def execute_query(self, cypher: str,
                            params: dict[str, Any] | None = None) -> list[dict]:
        return await self._adapter.execute_query(cypher, params)

    async def execute_write_query(self, cypher: str,
                                  params: dict[str, Any] | None = None) -> list[dict]:
        return await self._adapter.execute_write_query(cypher, params)

    async def get_neighbors(self, memory_id: str, max_depth: int = 1,
                            edge_type: str | None = None) -> list[dict]:
        return await self._adapter.get_neighbors(memory_id, max_depth, edge_type)

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
        memory_metadata: L2MetadataRepositoryPort,  # Rule 2应用端口
        memory_history: L2ChangeHistoryRepositoryPort,  # Rule 2应用端口
        # 以下可选
        memory_group: L2GroupMemberRepositoryPort | None = None,
        memory_vector: MemoryVectorPort | None = None,
        document_storage: DocumentStoragePort | None = None,
        memory_graph: MemoryGraphPort | None = None,
        event_publisher=None,
    ):
        self._file = memory_file
        self._cache = session_cache
        self._meta = memory_metadata
        self._hist = memory_history
        self._group = memory_group
        self._vector = memory_vector
        self._docs = document_storage
        self._graph = memory_graph
        self._event_publisher = event_publisher
```

**关键变化**:
- Gateway依赖**Rule 2应用端口**，而非直接依赖Rule 1基础端口
- 当前Gateway依赖8个Rule 1端口(l0_storage, l1_cache, l2_metadata等)，Phase 4需逐步过渡
- L2的Metadata/ChangeHistory端口保留在domain层（按四条规则，它们继承L2RdbPort[T]）
- L2GroupMember端口保留在domain层（独立Protocol，实现层可组合注入L2RdbPort）

---

## Composition Root 注册

```python
# src/composition_root.py

def bootstrap() -> None:
    # === Rule 3: 基础端口实现注册 ===
    # 注意: impl使用字符串路径(延迟加载)或直接类引用
    # Resolver支持递归自动注入：构造函数参数按名称/类型解析

    register_port(name="l0_storage", interface=L0StoragePort,
        impl="src.infrastructure.storage.file_memory_adapter.FileMemoryAdapter",
        module="src.infrastructure.storage.file_memory_adapter",
        lifetime=Lifetime.SCOPED, owner="storage-team")

    register_port(name="l1_cache", interface=L1CachePort,
        impl="src.infrastructure.storage.redis.redis_memory_cache.RedisMemoryCache",
        module="src.infrastructure.storage.redis.redis_memory_cache",
        lifetime=Lifetime.SCOPED, owner="storage-team")

    # 注意: PostgreSQLAdapter[TEntity,TModel]是泛型基座，无法独立实例化
    # L2端口的具体实现由三个子仓储直接注册（见下方Rule 4区域）

    register_port(name="l3_vector", interface=L3VectorPort,
        impl="src.infrastructure.storage.qdrant.qdrant_vector_adapter.QdrantVectorAdapter",
        module="src.infrastructure.storage.qdrant.qdrant_vector_adapter",
        lifetime=Lifetime.SCOPED, owner="storage-team")

    register_port(name="l4_object", interface=L4ObjectPort,
        impl="src.infrastructure.storage.minio.minio_adapter.MinIOAdapter",
        module="src.infrastructure.storage.minio.minio_adapter",
        lifetime=Lifetime.SCOPED, owner="storage-team")

    register_port(name="l5_graph", interface=L5GraphPort,
        impl="src.infrastructure.storage.neo4j.neo4j_adapter.Neo4jAdapter",
        module="src.infrastructure.storage.neo4j.neo4j_adapter",
        lifetime=Lifetime.SCOPED, owner="storage-team")

    # === Rule 4: 应用端口实现注册（Resolver自动递归注入Rule 3适配器） ===
    # Resolver._auto_inject()按构造函数参数名/类型递归解析依赖链

    register_port(name="memory_file", interface=MemoryFilePort,
        impl="src.infrastructure.storage.memory_file_storage.MemoryFileStorage",
        module="src.infrastructure.storage.memory_file_storage",
        lifetime=Lifetime.SCOPED, owner="storage-team")
    # ← Resolver自动注入: file_adapter参数→解析"l0_storage"

    register_port(name="session_cache", interface=SessionCachePort,
        impl="src.infrastructure.storage.redis.session_cache.RedisSessionCache",
        module="src.infrastructure.storage.redis.session_cache",
        lifetime=Lifetime.SCOPED, owner="storage-team")
    # ← Resolver自动注入: cache_adapter参数→解析"l1_cache"

    register_port(name="memory_metadata", interface=L2MetadataRepositoryPort,
        impl="src.infrastructure.storage.postgresql.repository.memory_metadata_repository.PostgreSQLMemoryMetadataRepository",
        module="src.infrastructure.storage.postgresql.repository.memory_metadata_repository",
        lifetime=Lifetime.SCOPED, owner="platform-team")
    # ← 继承PostgreSQLAdapter[MemoryMetadata,MemoryMetadataModel]，Resolver注入session

    register_port(name="memory_change_history", interface=L2ChangeHistoryRepositoryPort,
        impl="src.infrastructure.storage.postgresql.repository.memory_change_history_repository.PostgreSQLMemoryChangeHistoryRepository",
        module="src.infrastructure.storage.postgresql.repository.memory_change_history_repository",
        lifetime=Lifetime.SCOPED, owner="platform-team")
    # ← 继承PostgreSQLAdapter[MemoryChangeHistory,MemoryChangeHistoryModel]，delete覆写为raise NotImplementedError

    register_port(name="memory_group_member", interface=L2GroupMemberRepositoryPort,
        impl="src.infrastructure.storage.postgresql.repository.memory_group_member_repository.PostgreSQLMemoryGroupMemberRepository",
        module="src.infrastructure.storage.postgresql.repository.memory_group_member_repository",
        lifetime=Lifetime.SCOPED, owner="platform-team")
    # ← 组合注入共享Session（复合PK，不继承PostgreSQLAdapter）

    register_port(name="memory_vector", interface=MemoryVectorPort,
        impl="src.infrastructure.storage.qdrant.memory_vector_storage.QdrantMemoryVectorStorage",
        module="src.infrastructure.storage.qdrant.memory_vector_storage",
        lifetime=Lifetime.SCOPED, owner="storage-team")
    # ← Resolver自动注入: vector_adapter参数→解析"l3_vector"

    register_port(name="document_storage", interface=DocumentStoragePort,
        impl="src.infrastructure.storage.minio.document_storage.MinIODocumentStorage",
        module="src.infrastructure.storage.minio.document_storage",
        lifetime=Lifetime.SCOPED, owner="storage-team")
    # ← Resolver自动注入: object_adapter参数→解析"l4_object"

    register_port(name="memory_graph", interface=MemoryGraphPort,
        impl="src.infrastructure.storage.neo4j.memory_graph_storage.Neo4jMemoryGraphStorage",
        module="src.infrastructure.storage.neo4j.memory_graph_storage",
        lifetime=Lifetime.SCOPED, owner="storage-team")
    # ← Resolver自动注入: graph_adapter参数→解析"l5_graph"

    # === 统一网关 ===
    register_port(name="unified_storage", interface=UnifiedStoragePort,
        impl="src.application.services.unified_storage_gateway.UnifiedStorageGateway",
        module="src.application.services.unified_storage_gateway",
        lifetime=Lifetime.SINGLETON, owner="platform-team")
    # ← Resolver自动注入所有应用端口
```

**Resolver嵌套注入机制**:
- `_auto_inject(cls)` 检查构造函数参数
- 按参数**名称**→`resolve(param_name)` 解析注册表
- 按参数**类型注解**→`resolve_by_interface(param_type)` 兜底
- 递归解析：Rule4实现→发现Rule3类型参数→自动实例化Rule3→注入Rule4
- `_load_from_module_path` 返回class供`_auto_inject`处理，非缺陷

## 详细执行步骤

### Phase 1: Rule 1 — 端口抽象完善

- [ ] 1.1 重构 `BaseRepository[T]` → `L2RdbPort[T]`（sync→async，添加@runtime_checkable）
- [ ] 1.2 修改三个L2端口继承 `L2RdbPort[T]`（Metadata/ChangeHistory继承，GroupMember组合）
- [ ] 1.3 废弃 `ObjectStorageRepository`（`src/domain/ports/storage.py`标记deprecated）
- [ ] 1.4 所有Domain端口添加 `@runtime_checkable`（10个Protocol文件）
- [ ] 1.5 补全 `src/domain/ports/__init__.py` 导出至100%（L0StoragePort, BaseRepository, IndexManagerPort）
- [ ] 1.6 创建 `src/application/ports/__init__.py`（当前缺失）
- [ ] 1.7 验证 Resolver `_load_from_module_path` → `_auto_inject` 链路：当前返回class供`_auto_inject`递归解析构造函数参数后实例化，属设计意图（非缺陷），需确保Rule 4嵌套注入场景正确
- [ ] 1.8 验证: 所有端口可导入，ContractGate isinstance()检查生效

### Phase 2: Rule 2 — 应用端口定义

- [ ] 2.1 新增 `src/application/ports/memory_file_port.py` — MemoryFilePort(L0StoragePort)
- [ ] 2.2 新增 `src/application/ports/session_cache_port.py` — SessionCachePort(L1CachePort)
  - 注意: RedisSessionStorage已存在(save/load/delete/exists)，SessionCachePort为新应用层抽象
- [ ] 2.3 新增 `src/application/ports/memory_vector_port.py` — MemoryVectorPort(L3VectorPort)
- [ ] 2.4 新增 `src/application/ports/document_storage_port.py` — DocumentStoragePort(L4ObjectPort)
- [ ] 2.5 新增 `src/application/ports/memory_graph_port.py` — MemoryGraphPort(L5GraphPort)
- [ ] 2.6 L2端口保持在domain层，继承L2RdbPort[T]（Phase 1已完成）
- [ ] 2.7 补全 `src/application/ports/__init__.py` 导出全部应用端口
- [ ] 2.8 验证: 所有应用端口继承基础端口，方法签名兼容，Protocol无@abstractmethod混用

### Phase 3: Rule 3 — 基础端口实现完善

- [ ] 3.1 补全 `QdrantVectorAdapter` 的4个Collection方法（注入QdrantCollectionManager）
- [ ] 3.2 修复 `MinIORepository.archive()` 签名（添加content参数，返回str而非bool）
- [ ] 3.3 补全 `MinIOAdapter.list_objects()` 方法（委托Repository已有实现）
- [ ] 3.4 补全 `Neo4jAdapter.get_neighbors()` 方法（桥接参数映射: memory_id→node_id）；修复 `Neo4jAdapter` + `Neo4jGraphStorage` 的 Cypher 注入漏洞（4处f-string拼接→参数化查询）
- [ ] 3.5 重构 Infrastructure层 `BaseRepository[T]` → `PostgreSQLAdapter[TEntity, TModel]` 双泛型基座（实现Domain层L2RdbPort[TEntity]，提供_to_entity/_to_model转换、可配置pk_column/soft_delete_column、_do_save钩子）。注意：save返回值从T→None、list_all去除skip/limit、get_by_id参数str→UUID，需检查UserRepository/PermissionRepository调用者影响
- [ ] 3.6 创建统一 `ConnectionManager` 抽象基类（可选，已有各ClientWrapper延迟初始化）
- [ ] 3.7 注册所有 Rule 3 基础端口到 Composition Root（含L2相关端口）
- [ ] 3.8 验证: 所有基础端口有实现，缺失方法补全，签名匹配

### Phase 4: Rule 4 — 应用端口实现

- [ ] 4.1 新增 `src/infrastructure/storage/memory_file_storage.py` — MemoryFileStorage(MemoryFilePort)
- [ ] 4.2 新增 `src/infrastructure/storage/redis/redis_session_cache.py` — RedisSessionCache(SessionCachePort)
  - 注意: 与现有RedisSessionStorage区分，SessionCachePort继承L1CachePort语义
- [ ] 4.3 新增 `src/infrastructure/storage/qdrant/memory_vector_storage.py` — QdrantMemoryVectorStorage(MemoryVectorPort)
- [ ] 4.4 新增 `src/infrastructure/storage/minio/document_storage.py` — MinIODocumentStorage(DocumentStoragePort)
- [ ] 4.5 新增 `src/infrastructure/storage/neo4j/memory_graph_storage.py` — Neo4jMemoryGraphStorage(MemoryGraphPort)
- [ ] 4.6 重构三个L2仓储继承PostgreSQLAdapter[TEntity, TModel]：
  - `PostgreSQLMemoryMetadataRepository(PostgreSQLAdapter[MemoryMetadata, MemoryMetadataModel])` — 覆写_do_save(UPSERT+乐观锁)、pk_column="memory_id"、soft_delete_column="deleted_at"
  - `PostgreSQLMemoryChangeHistoryRepository(PostgreSQLAdapter[MemoryChangeHistory, MemoryChangeHistoryModel])` — 覆写_do_save(append-only)、delete(raise NotImplementedError)
  - `PostgreSQLMemoryGroupMemberRepository` — 组合注入共享Session（复合PK，不继承PostgreSQLAdapter）
- [ ] 4.7 注册所有 Rule 4 应用端口到 Composition Root（含L2三个仓储）
- [ ] 4.8 调整 `UnifiedStorageGateway` 依赖应用端口（逐步过渡）
- [ ] 4.9 验证: Resolver嵌套注入生效（Rule4→Rule3自动解析），L2仓储继承PostgreSQLAdapter

### Phase 5: 清理与测试

- [ ] 5.1 删除废弃接口（ObjectStorageRepository，标记deprecated后清理引用）
- [ ] 5.2 修复 `SemanticCache`/`PublicBlackboard` 的 Protocol+@abstractmethod 反模式
- [ ] 5.3 更新现有代码引用（MinIORepository基类改为L4ObjectPort）
- [ ] 5.4 创建端口契约测试（覆盖所有L0-L5端口）
- [ ] 5.5 创建架构约束测试（四层规则合规）
- [ ] 5.6 端到端集成验证（Resolver解析全链路）

---

## 关键文件清单

| 文件 | 类型 | Phase | 规则 | P0问题修复 |
|------|------|-------|------|-----------|
| `src/domain/ports/base.py` | 重构 | Phase 1 | Rule 1 | BaseRepository→L2RdbPort[T] sync→async |
| `src/domain/ports/l2_rdb.py` | 重构 | Phase 1 | Rule 1 | 三端口继承L2RdbPort[T] |
| `src/domain/ports/l{0,1,3-5}_*.py` | 修改 | Phase 1 | Rule 1 | 添加@runtime_checkable |
| `src/domain/ports/storage.py` | 废弃 | Phase 1 | Rule 1 | ObjectStorageRepository deprecated |
| `src/domain/ports/__init__.py` | 补全导出 | Phase 1 | Rule 1 | L0/Base/IndexManagerPort导出 |
| `src/application/ports/__init__.py` | **新增** | Phase 1 | Rule 2 | 创建缺失的package文件 |
| `src/domain/ports/resolver.py` | 验证 | Phase 1 | Rule 3-4 | 验证class→instance链路正确（非缺陷） |
| `src/application/ports/memory_file_port.py` | **新增** | Phase 2 | Rule 2 | |
| `src/application/ports/session_cache_port.py` | **新增** | Phase 2 | Rule 2 | |
| `src/application/ports/memory_vector_port.py` | **新增** | Phase 2 | Rule 2 | |
| `src/application/ports/document_storage_port.py` | **新增** | Phase 2 | Rule 2 | |
| `src/application/ports/memory_graph_port.py` | **新增** | Phase 2 | Rule 2 | |
| `src/infrastructure/storage/qdrant/qdrant_vector_adapter.py` | 修改 | Phase 3 | Rule 3 | 补全4 Collection方法 |
| `src/infrastructure/storage/minio/minio_repository.py` | 修改 | Phase 3 | Rule 3 | archive签名修复 |
| `src/infrastructure/storage/minio/minio_adapter.py` | 修改 | Phase 3 | Rule 3 | list_objects/archive修复 |
| `src/infrastructure/storage/neo4j/neo4j_adapter.py` | 修改 | Phase 3 | Rule 3 | get_neighbors桥接 |
| `src/infrastructure/storage/postgresql/repository/base_repository.py` | 重构 | Phase 3 | Rule 3 | BaseRepository[T]→PostgreSQLAdapter[TEntity,TModel]双泛型基座 |
| `src/infrastructure/storage/postgresql/repository/memory_metadata_repository.py` | 重构 | Phase 4 | Rule 4 | 继承PostgreSQLAdapter，覆写_do_save/pk_column/soft_delete |
| `src/infrastructure/storage/postgresql/repository/memory_change_history_repository.py` | 重构 | Phase 4 | Rule 4 | 继承PostgreSQLAdapter，覆写_do_save(append-only)/delete |
| `src/infrastructure/storage/postgresql/repository/memory_group_member_repository.py` | 重构 | Phase 4 | Rule 4 | 组合注入共享Session，保留独立Protocol |
| `src/infrastructure/storage/memory_file_storage.py` | **新增** | Phase 4 | Rule 4 | |
| `src/infrastructure/storage/redis/redis_session_cache.py` | **新增** | Phase 4 | Rule 4 | 与RedisSessionStorage区分 |
| `src/infrastructure/storage/qdrant/memory_vector_storage.py` | **新增** | Phase 4 | Rule 4 | |
| `src/infrastructure/storage/minio/document_storage.py` | **新增** | Phase 4 | Rule 4 | |
| `src/infrastructure/storage/neo4j/memory_graph_storage.py` | **新增** | Phase 4 | Rule 4 | |
| `src/composition_root.py` | 修改 | Phase 3-4 | Rule 3-4 | 注册格式+L2端口注册 |
| `src/application/services/unified_storage_gateway.py` | 修改 | Phase 4 | Rule 4 | 依赖应用端口 |
| `src/application/ports/semantic_cache.py` | 修复 | Phase 5 | Rule 1 | Protocol+abstractmethod反模式 |
| `src/application/ports/public_blackboard.py` | 修复 | Phase 5 | Rule 1 | Protocol+abstractmethod反模式 |

---

## 验证方案

```bash
# Rule 1: 端口抽象（需Phase 1完成后@runtime_checkable生效）
poetry run python -c "from src.domain.ports import *; print('Rule 1 OK')"

# Rule 2: 应用端口继承（Protocol继承用@runtime_checkable后issubclass可用）
poetry run python -c "
from src.application.ports.document_storage_port import DocumentStoragePort
from src.domain.ports.l4_object import L4ObjectPort
# Protocol继承关系通过结构化子类型验证
print('Rule 2 OK')
"

# Rule 3: 基础实现可解析
poetry run python -c "
from src.composition_root import bootstrap
from src.domain.ports.registry import _global_registry
bootstrap()
for p in ['l0_storage','l1_cache','l3_vector','l4_object','l5_graph']:
    assert _global_registry.get(p), f'{p} not registered'
# L2无独立Rule 3注册（PostgreSQLAdapter是泛型基座，由具体子仓储在Rule 4区域注册）
for p in ['memory_metadata','memory_change_history','memory_group_member']:
    assert _global_registry.get(p), f'{p} not registered'
print('Rule 3 OK')
"

# Rule 4: 应用端口实现可解析（Resolver嵌套注入验证）
poetry run python -c "
from src.composition_root import bootstrap
from src.domain.ports.resolver import get_resolver
bootstrap()
resolver = get_resolver()
# 验证Rule4实现可解析（自动注入Rule3适配器）
for p in ['memory_file','session_cache','memory_vector',
           'document_storage','memory_graph',
           'memory_metadata','memory_change_history','memory_group_member']:
    spec = resolver._registry.get(p)
    assert spec, f'{p} not registered'
print('Rule 4 OK')
"
```

---

## 时间估算

| Phase | 规则 | 工时 | 风险 | P0修复项 |
|-------|------|------|------|---------|
| Phase 1 | Rule 1 | 4-6h | 中 | L2RdbPort重构+@runtime_checkable+Resolver修复 |
| Phase 2 | Rule 2 | 4-6h | 低 | 5个应用端口+__init__.py |
| Phase 3 | Rule 3 | 5-7h | 中 | 4个适配器补全+PostgreSQLAdapter[TEntity,TModel]双泛型基座 |
| Phase 4 | Rule 4 | 6-8h | 中 | 5个应用端口实现+3个L2仓储重构+Gateway调整 |
| Phase 5 | 测试 | 4-5h | 低 | 契约测试+反模式修复 |
| **总计** | — | **23-32h** | — | 15个P0问题 |
