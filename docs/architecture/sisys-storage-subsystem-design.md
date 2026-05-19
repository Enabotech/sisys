# SISYS 存储子系统详细设计

**文档版本:** v1.0
**生成时间:** 2026-05-19
**基于:** architecture.md v8.3.1 + sisys-storage-refactor-design.md v6.0 + 现有代码实现全面调研
**状态:** Phase 1-5 已完成（3066 tests passed）

---

## 1. 设计概述

### 1.1 六层存储架构

SISYS 采用六层分级存储架构（L0-L5），遵循"磁盘记忆 = 真相源，LLM 上下文 = 缓存"的系统公理：

| 层级 | 技术 | 职责 | 连接管理器 | 默认端口 |
|------|------|------|-----------|---------|
| **L0 文件系统** | aiofiles + asyncio.to_thread | MEMORY.md 索引、记忆文件存储 | 无（文件系统直接操作） | N/A |
| **L1 高速缓存** | Redis Stack 7.2 | KV 缓存、会话状态、语义缓存 | RedisManager (SINGLETON) | 6379 |
| **L2 关系存储** | PostgreSQL 15 + SQLAlchemy | 元数据索引、RBAC、审计、Outbox | PostgreSQLManager (SINGLETON) | 5432 |
| **L3 向量存储** | Qdrant v1.7 | 嵌入向量、Dense+Sparse 混合检索 | QdrantManager (SINGLETON) | 6333/6334 |
| **L4 对象存储** | MinIO (WORM) | 文档归档、Checkpoint 证据包 | MinioManager | 9000 |
| **L5 图存储** | Neo4j 5.x | 知识图谱、实体关系 | Neo4jManager (SINGLETON) | 7687 |

### 1.2 四层规则映射

存储子系统严格遵循四层规则（来自 sisys-storage-refactor-design.md）：

| 规则 | 架构层 | 职责 | 位置 |
|------|--------|------|------|
| **Rule 1** | Domain Layer | 统一抽象存储基础端口 `L[n][XXX]Port`，零依赖，技术无关 | `src/domain/ports/` |
| **Rule 2** | Domain + Application Layer | 具体应用端口**组合注入或继承**基础端口，定义业务语义 | `src/domain/ports/` + `src/application/ports/` |
| **Rule 3** | Infrastructure Layer-1 | 基础端口的技术实现 + 连接管理，可替换 | `src/infrastructure/storage/{tech}/` |
| **Rule 4** | Infrastructure Layer-2 | 应用端口的技术实现，**组合（优先）或继承（谨慎）** Layer-1 适配器 | `src/infrastructure/storage/{tech}/` |

### 1.3 核心设计原则

- **依赖倒置 (DIP)**：Domain/Application 层仅依赖 Port 接口，不知道 Infrastructure 的存在
- **Protocol 结构化子类型**：所有 Port 使用 `typing.Protocol` + `@runtime_checkable`，鸭子类型兼容
- **组合优于继承**：Rule 4 实现组合注入 Rule 3 适配器，仅在有明确需求时（如 Session 管理、软删除）才使用继承
- **领域层零外部依赖**：`src/domain/ports/` 仅使用 `abc` + `typing`
- **懒初始化单例**：所有连接管理器通过懒初始化创建连接池/引擎

---

## 2. 架构总览图

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Composition Root                              │
│                   src/composition_root.py                            │
│         register_port(name, interface, impl, lifetime)              │
│         Resolver._auto_inject(cls) → 按参数名/类型递归解析           │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ 装配
                           v
┌──────────────────────────────────────────────────────────────────────┐
│                  UnifiedStorageGateway (应用层)                       │
│         src/application/services/unified_storage_gateway.py         │
│                                                                      │
│  save()  → L0 同步写 + MemoryChanged 事件（事务发件箱）               │
│  read()  → L2 RBAC 校验 → L1 缓存优先 → L0 回源 + 缓存回填          │
│  delete() → L0 删除 + L1 缓存失效 + MemoryChanged 事件              │
│  exists() → L2 校验 → L0/L1 存在检查                                │
│                                                                      │
│  依赖应用端口：L0StoragePort, MemoryCachePort, L2MetadataPort,       │
│               L2HistoryPort, L2GroupMemberPort, MemoryVectorPort,    │
│               DocumentStoragePort, MemoryGraphPort                   │
└──────────────────────────────────────────────────────────────────────┘
                           │ 依赖
                           v
┌──────────────────────────────────────────────────────────────────────┐
│  Rule 2: 应用端口（继承 Rule 1 基础端口 + 业务语义）                  │
│                                                                      │
│  MemoryFilePort(L0StoragePort)        MemoryCachePort(L1CachePort)  │
│  SessionCachePort(L1CachePort)        MemoryVectorPort(L3VectorPort) │
│  DocumentStoragePort(L4ObjectPort)    MemoryGraphPort(L5GraphPort)  │
│  L2MetadataPort(L2RdbPort[T])         L2HistoryPort(L2RdbPort[T])   │
│  L2GroupMemberPort(Protocol, 独立)    SemanticCache(Protocol, 独立) │
│                                                                      │
│  位置: src/application/ports/ + src/domain/ports/memory_repository.py│
└──────────────────────────────────────────────────────────────────────┘
                           │ 实现
                           v
┌──────────────────────────────────────────────────────────────────────┐
│  Rule 4: Infrastructure Layer-2 — 应用端口实现                        │
│  （组合注入 Rule 3 适配器）                                           │
│                                                                      │
│  MemoryFileStorage ← FileMemoryAdapter     RedisMemoryCache ← Redis  │
│                                                Adapter               │
│  RedisSessionCache ← RedisAdapter          QdrantMemoryVectorStorage │
│                                              ← QdrantAdapter         │
│  MinIODocumentStorage ← MinIOAdapter       Neo4jMemoryGraphStorage   │
│                                              ← Neo4jAdapter          │
│  PgMetadataRepo ← PostgreSQLAdapter       PgHistoryRepo ← PgAdapter  │
│  PgGroupMemberRepo（组合注入共享 Session）                            │
└──────────────────────────────────────────────────────────────────────┘
                           │ 组合注入
                           v
┌──────────────────────────────────────────────────────────────────────┐
│  Rule 3: Infrastructure Layer-1 — 基础端口实现 + 连接管理             │
│                                                                      │
│  FileMemoryAdapter(L0StoragePort)    RedisAdapter(L1CachePort)      │
│  PostgreSQLAdapter(L2RdbPort[T])     QdrantAdapter(L3VectorPort)    │
│  MinIOAdapter(L4ObjectPort)          Neo4jAdapter(L5GraphPort)      │
│                                                                      │
│  连接管理器：RedisManager / PostgreSQLManager / QdrantManager /      │
│             MinioManager / Neo4jManager — 均实现 ConnectionManager   │
└──────────────────────────────────────────────────────────────────────┘
                           │ 依赖
                           v
┌──────────────────────────────────────────────────────────────────────┐
│  外部技术栈                                                           │
│  Redis Stack 7.2 | PostgreSQL 15 | Qdrant v1.7 | MinIO | Neo4j 5.x │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. L0 文件系统存储

### 3.1 Rule 1: L0StoragePort

**文件:** `src/domain/ports/l0_storage.py`

```python
@runtime_checkable
class L0StoragePort(Protocol):
    async def write(self, memory_id: str, memory_type: str, content: str) -> bool
    async def read(self, memory_id: str, memory_type: str) -> str
    async def delete(self, memory_id: str, memory_type: str) -> bool
    async def exists(self, memory_id: str, memory_type: str) -> bool
    async def list_memories(self, memory_type: str) -> list[str]
```

**辅助端口:** `src/domain/ports/index_manager.py` — `IndexManagerPort`

```python
@runtime_checkable
class IndexManagerPort(Protocol):
    async def update_entry(self, entry: dict) -> None
    async def remove_entry(self, memory_id: str) -> None
    async def read_entries(self) -> list[dict]
    async def search(self, query: str) -> list[dict]
    async def truncate(self) -> None
```

**设计要点:**
- 5 个异步方法，零外部依赖
- `memory_type` 支持 `user` / `feedback` / `project` / `reference`
- 文件路径模式: `{base}/{memory_type}/{memory_id}.md`
- 索引格式: `- [name](type/id.md) -- description`

### 3.2 Rule 2: MemoryFilePort

**文件:** `src/application/ports/memory_file_port.py`

```python
@runtime_checkable
class MemoryFilePort(L0StoragePort, Protocol):
    async def update_index(self, entry: dict) -> None
    async def remove_from_index(self, memory_id: str) -> None
    async def search_index(self, query: str) -> list[dict]
```

继承 L0StoragePort 全部方法，添加 MEMORY.md 索引管理语义。

### 3.3 Rule 3: FileMemoryAdapter

**文件:** `src/infrastructure/storage/fs/file_memory_adapter.py`

**设计:**
- 实现 `L0StoragePort`
- 写入/读取: `aiofiles` 异步 I/O
- 删除/存在/列表: `asyncio.to_thread()` 包装 `Path` 操作
- 无连接管理器（文件系统直接操作）
- 保留向后兼容的 `write_sync` / `read_sync` 同步方法

### 3.4 Rule 4: MemoryFileStorage

**文件:** `src/infrastructure/storage/fs/memory_file_storage.py`

**设计:**
- 实现 `MemoryFilePort`
- **组合注入** `FileMemoryAdapter`
- L0 基础方法全部委托给 adapter
- 索引管理方法通过 `asyncio.to_thread()` 调用 adapter 的同步索引操作

### 3.5 DI 注册

```python
# Rule 3
register_port(name="l0_storage", interface=L0StoragePort,
    impl="...file_memory_adapter.FileMemoryAdapter", lifetime=SCOPED)

# Rule 4
register_port(name="memory_file_storage", interface=MemoryFilePort,
    impl="...memory_file_storage.MemoryFileStorage", lifetime=SCOPED)
```

---

## 4. L1 缓存存储

### 4.1 Rule 1: L1CachePort

**文件:** `src/domain/ports/l1_cache.py`

```python
@runtime_checkable
class L1CachePort(Protocol):
    async def get(self, key: str) -> str | None
    async def set(self, key: str, value: str, ttl: int | None = None) -> bool
    async def delete(self, key: str) -> bool
    async def exists(self, key: str) -> bool
    async def delete_pattern(self, pattern: str) -> int
    async def set_with_ttl(self, key: str, value: str, ttl: int) -> bool
```

**设计要点:**
- 6 个通用 KV 异步方法
- `delete_pattern` 使用 SCAN（非 KEYS）避免阻塞
- 技术无关，可替换为 Memcached 等实现

### 4.2 Rule 2: 应用端口

**MemoryCachePort** (`src/application/ports/memory_cache_port.py`):

```python
@runtime_checkable
class MemoryCachePort(L1CachePort, Protocol):
    async def get_memory(self, memory_type: str, owner_id: str, name: str) -> str | None
    async def set_memory(self, memory_type: str, owner_id: str, name: str,
                         content: str, ttl: int | None = None) -> bool
    async def delete_memory(self, memory_type: str, owner_id: str, name: str) -> bool
    async def invalidate_owner(self, memory_type: str, owner_id: str) -> int
```

**SessionCachePort** (`src/application/ports/session_cache_port.py`):

```python
@runtime_checkable
class SessionCachePort(L1CachePort, Protocol):
    async def save_session(self, session_id: str, agent_id: str, state: dict, ttl: int = 86400) -> None
    async def load_session(self, session_id: str) -> dict | None
    async def delete_session(self, session_id: str) -> None
    async def session_exists(self, session_id: str) -> bool
```

**SemanticCache** (`src/application/ports/semantic_cache.py`) — **独立端口**，不继承 L1CachePort（因 `get(query_embedding, threshold)` 签名不兼容）:

```python
class SemanticCache(Protocol):
    async def get(self, query_embedding: list[float], threshold: float = 0.9) -> dict | None
    async def set(self, query_embedding: list[float], result: dict, ttl: int = 86400) -> None
    async def invalidate(self, cache_key: str) -> None
```

### 4.3 Rule 3: RedisAdapter + RedisManager

**RedisAdapter** (`src/infrastructure/storage/redis/redis_adapter.py`):

```python
class RedisAdapter(L1CachePort):
    def __init__(self, redis_client: aioredis.Redis) -> None
    @property
    def raw_client(self) -> aioredis.Redis  # 暴露底层客户端
```

- 实现 L1CachePort 全部 6 个方法
- `raw_client` 属性供 Rule 4 组件访问 Redis 专属操作（HSET/ZADD/FT.SEARCH）
- `delete_pattern` 使用 `scan_iter`（非 KEYS）避免阻塞

**RedisManager** (`src/infrastructure/storage/redis/redis_manager.py`):

- 实现 `ConnectionManager` Protocol
- 懒初始化 `aioredis.ConnectionPool`，提供共享 `aioredis.Redis` 实例
- `health_check()`: PING 命令

**RedisConfig** (`src/infrastructure/config/redis.py`):

```python
@dataclass
class RedisConfig:
    host: str = "localhost"       # REDIS_HOST
    port: int = 6379              # REDIS_PORT
    db: int = 0                   # REDIS_DB
    password: str | None = None   # REDIS_PASSWORD
    max_connections: int = 10     # REDIS_MAX_CONNECTIONS
    default_ttl: int = 86400      # REDIS_DEFAULT_TTL (24h)
```

### 4.4 Rule 4: 缓存应用实现

**RedisMemoryCache** (`src/infrastructure/storage/redis/redis_memory_cache.py`):

- **组合注入** `RedisAdapter`
- L1CachePort 通用方法全部委托给 `self._adapter`
- 记忆方法通过 `_build_key()` 构建键（格式: `memory:{type}:{owner_id}:{name}`）
- TTL 随机化: 86400-108000 秒（24h-30h），防止缓存雪崩

**RedisSessionCache** (`src/infrastructure/storage/redis/redis_session_cache.py`):

- **组合注入** `RedisAdapter`
- 通用方法委托给 adapter
- 会话方法使用 `adapter.raw_client` 直接调用 HSET/HGET 操作
- 键格式: `sisys:session:{session_id}`

**RedisSemanticCache** (`src/infrastructure/storage/redis/semantic_cache.py`):

- 独立实现 `SemanticCache`，不继承 L1CachePort
- 基于 RediSearch FT.SEARCH 向量索引实现
- 向量二进制序列化: `struct.pack` FLOAT32 little-endian
- 集成 `EventMetricsCollector` 进行 hit/miss 监控
- 优雅降级: 连接错误时记录日志返回 None

### 4.5 辅助模块

| 模块 | 文件 | 职责 |
|------|------|------|
| `CacheEntry` | `redis/cache_entry.py` | 语义缓存存储实体，`to_dict()`/`from_dict()` 序列化 |
| `build_key` | `redis/key_builder.py` | 统一键构建: `sisys:{namespace}:{parts}` |
| `RedisCleanup` | `redis/cleanup.py` | 按 namespace 批量清理，SCAN 分批删除 |

### 4.6 DI 注册

```python
# 连接管理器 (SINGLETON)
register_port(name="redis_connection_manager", interface=ConnectionManager,
    impl=lambda: RedisManager(RedisConfig.from_env()), lifetime=SINGLETON)

# Redis 客户端 (SINGLETON)
register_port(name="redis_client", interface=aioredis.Redis,
    impl=lambda r: r.resolve("redis_connection_manager").get_client(), lifetime=SINGLETON)

# Rule 3: 基础适配器 (SINGLETON)
register_port(name="redis_adapter", interface=L1CachePort,
    impl="...redis_adapter.RedisAdapter", lifetime=SINGLETON, tags=("redis","cache"))

# Rule 4: 应用端口实现 (SCOPED)
register_port(name="memory_cache", interface=MemoryCachePort,
    impl=lambda r: RedisMemoryCache(adapter=r.resolve("redis_adapter")), lifetime=SCOPED)
register_port(name="session_cache", interface=SessionCachePort,
    impl=lambda r: RedisSessionCache(adapter=r.resolve("redis_adapter")), lifetime=SCOPED)
register_port(name="semantic_cache", interface=SemanticCache,
    impl="...semantic_cache.RedisSemanticCache", lifetime=SCOPED)
register_port(name="session_storage", interface=SessionStorage,
    impl="...session_storage.RedisSessionStorage", lifetime=SCOPED)
```

### 4.7 部署配置

**Redis Stack Server 7.2.0-v20**（含 RediSearch/RedisBloom/RedisTimeSeries/RedisJSON）:
- `maxmemory 2gb`，淘汰策略 `volatile-lru`
- 加载 `redisearch.so` 模块（semantic_cache FT.SEARCH 依赖）

---

## 5. L2 关系数据库存储

### 5.1 Rule 1: L2RdbPort[T]

**文件:** `src/domain/ports/l2_rdb.py`

```python
@runtime_checkable
class L2RdbPort(Generic[T], Protocol):
    async def get_by_id(self, id: UUID) -> T | None
    async def save(self, entity: T) -> T
    async def delete(self, id: UUID) -> None
    async def list_all(self) -> list[T]
```

**设计要点:**
- 泛型 async CRUD 基座
- `BaseRepository = L2RdbPort` 为向后兼容别名（已弃用）
- 领域层零 SQLAlchemy 依赖

### 5.2 Rule 2: 具体端口

**记忆业务端口** (`src/domain/ports/memory_repository.py`):

```python
# 继承 L2RdbPort
class L2MetadataRepositoryPort(L2RdbPort[MemoryMetadata], Protocol):
    async def get_by_name(self, name: str) -> MemoryMetadata | None
    async def list_by_user(self, user_id: str) -> list[MemoryMetadata]
    async def list_by_type(self, memory_type: str) -> list[MemoryMetadata]

class L2ChangeHistoryRepositoryPort(L2RdbPort[MemoryChangeHistory], Protocol):
    async def get_by_memory_id(self, memory_id: UUID) -> list[MemoryChangeHistory]

# 独立 Protocol（方法无 CRUD 交集）
class L2GroupMemberRepositoryPort(Protocol):
    async def is_group_member(self, group_id: str, user_id: str) -> bool
    async def is_group_admin(self, group_id: str, user_id: str) -> bool
    async def add_member(self, group_id: str, user_id: str, role: str = "member") -> None
    async def remove_member(self, group_id: str, user_id: str) -> None
```

**RBAC 端口**（`src/domain/ports/`）:

| 端口 | 文件 | 扩展方法 |
|------|------|---------|
| `UserRepositoryPort` | `user_repository.py` | `get_by_username()`, `get_by_id()` |
| `RoleRepositoryPort` | `role_repository.py` | `get_by_name()`, `get_permissions_for_role()` |
| `PermissionRepositoryPort` | `permission_repository.py` | `get_by_name()` |
| `UserRoleRepositoryPort` | `user_role_repository.py` | `assign_role()`, `revoke_role()`, `get_user_roles()` |
| `LoginAttemptRepositoryPort` | `login_attempt_repository.py` | `record_attempt()`, `is_account_locked()` |

**其他端口**:
- `AuditRepositoryPort` (`audit_repository.py`) — `save()`, `search()`, `update_archive_status()`
- `OutboxRepository` (`outbox.py`) — 事务发件箱模式
- `SagaRepositoryProtocol` (`saga.py`) — Saga 持久化
- `UnitOfWork` / `UnitOfWorkFactory` (`unit_of_work.py`) — 工作单元模式

### 5.3 Rule 3: PostgreSQLAdapter + PostgreSQLManager

**PostgreSQLAdapter[TEntity, TModel]** (`src/infrastructure/storage/postgresql/repository/postgresql_adapter.py`):

```python
class PostgreSQLAdapter(L2RdbPort[TEntity], Generic[TEntity, TModel]):
    pk_column: str = "id"                      # 可覆写为 "memory_id"
    soft_delete_column: str | None = None       # 可覆写为 "deleted_at"

    def __init__(self, model_class: type[TModel])
    def _to_entity(self, model: TModel) -> TEntity      # 子类必须实现
    def _to_model(self, entity: TEntity) -> TModel      # 子类必须实现
    async def _do_save(self, model, entity) -> None      # 钩子，默认简单 add+flush
```

**设计模式:**
- **模板方法模式**: 子类实现 `_to_entity` / `_to_model` / `_do_save`
- **Session 通过 ContextVar 注入**: `_session` 从 `session_context.get_session()` 获取
- **软删除支持**: 通过 `soft_delete_column` 类属性控制
- **UPSERT 钩子**: `_do_save` 可被子类覆写

**PostgreSQLManager** (`src/infrastructure/storage/postgresql/postgresql_manager.py`):

- 实现 `ConnectionManager` Protocol
- 懒初始化 async engine（asyncpg）和 sync engine（psycopg2）
- `health_check()`: `SELECT 1`
- `get_async_session()`: 异步上下文管理器

**Session 管理** (`src/infrastructure/storage/postgresql/session_context.py`):

- `_session_ctx: ContextVar[AsyncSession | None]` — 全局上下文变量
- `session_context(session_factory)` — 异步上下文管理器，自动 commit/rollback/close

**SessionMiddleware** (`src/infrastructure/middleware/session_middleware.py`):

- 每个 HTTP 请求创建新 session
- 成功时检查 `session.in_transaction()` 决定是否 commit
- 异常时 rollback

**PostgreSQLConfig** (`src/infrastructure/config/postgresql.py`):

```python
@dataclass
class PostgreSQLConfig:
    host: str = "localhost"           # POSTGRES_HOST
    port: int = 5432                  # POSTGRES_PORT
    database: str = ""                # POSTGRES_DATABASE
    username: str = ""                # POSTGRES_USERNAME
    password: str = ""                # POSTGRES_PASSWORD
    pool_size: int = 5                # POSTGRES_POOL_SIZE
    max_overflow: int = 10            # POSTGRES_MAX_OVERFLOW
```

### 5.4 Rule 4: 仓储实现

| 仓储 | 文件 | 继承方式 | 特殊行为 |
|------|------|---------|---------|
| `UserRepository` | `repository/user_repository.py` | `PostgreSQLAdapter[User, UserModel]` | `_to_entity/_to_model` 实体转换 |
| `PermissionRepository` | `repository/permission_repository.py` | `PostgreSQLAdapter[Permission, PermissionModel]` | 多重继承端口 |
| `RoleRepository` | `repository/role_repository.py` | 直接实现端口 | ContextVar session |
| `UserRoleRepository` | `repository/user_role_repository.py` | 直接实现端口 | 复合关联表 |
| `LoginAttemptRepository` | `repository/login_attempt_repository.py` | 直接实现端口 | 锁定逻辑 |
| `PgMetadataRepo` | `repository/memory_metadata_repository.py` | `PostgreSQLAdapter + L2MetadataPort` | UPSERT+乐观锁, `pk_column="memory_id"`, `soft_delete_column="deleted_at"` |
| `PgHistoryRepo` | `repository/memory_change_history_repository.py` | `PostgreSQLAdapter + L2HistoryPort` | append-only, `delete()` 抛 NotImplementedError |
| `PgGroupMemberRepo` | `repository/memory_group_member_repository.py` | 直接实现端口 | 组合注入共享 Session，复合 PK |
| `AuditRepository` | `security/audit_repository_impl.py` | 直接实现端口 | 位于 security 子系统 |
| `PostgreSQLOutboxRepository` | `messaging/outbox/outbox_repository.py` | 直接实现端口 | 事务发件箱 |
| `PostgreSQLSagaRepository` | `saga/saga_repository.py` | 直接实现端口 | 使用 raw SQL (`text()`) |

### 5.5 SQLAlchemy ORM Models

**Base 定义** (`src/infrastructure/storage/postgresql/models/outbox.py`):

```python
pg_registry = registry()
class Base(DeclarativeBase):
    registry = pg_registry
```

| ORM 模型 | 表名 | 主键 |
|----------|------|------|
| `OutboxModel` | `event_outbox` | UUID `id` |
| `UserModel` | `users` | UUID `id` |
| `RoleModel` | `roles` | UUID `id` |
| `PermissionModel` | `permissions` | UUID `id` |
| `AuditLogModel` | `audit_log` | 自增 `id` |
| `AuditOutboxModel` | `audit_outbox` | 自增 `id` |
| `LoginAttemptModel` | `login_attempts` | UUID `id` |
| `MemoryMetadataModel` | `memory_metadata` | UUID `memory_id` |
| `MemoryChangeHistoryModel` | `memory_change_history` | UUID `id` |
| `MemoryGroupMemberModel` | `memory_group_members` | 复合 `(group_id, user_id)` |
| `user_roles_table` | `user_roles` | 复合 `(user_id, role_id)` |
| `role_permissions_table` | `role_permissions` | 复合 `(role_id, permission_id)` |

### 5.6 Alembic Migrations

**位置:** `deploy/postgresql/alembic/versions/`

| 版本 | 内容 |
|------|------|
| 001_initial | `event_outbox`, `users`, `roles`, `permissions`, `user_roles`, `role_permissions` |
| 002_audit_tables | `audit_log` + `audit_outbox`，含 Row-Level Security (RLS) |
| 003_rbac_extensions | RBAC 扩展：`is_active/is_system_reserved/is_locked`, `login_attempts` |
| 004_saga_tables | `saga_instance` 表，含状态 CHECK 约束 |

**注意:** `memory_metadata`, `memory_change_history`, `memory_group_members` 表尚无 Alembic 迁移。

### 5.7 DI 注册

```python
# 连接管理器 (SINGLETON)
register_port(name="postgresql_connection_manager", interface=ConnectionManager,
    impl=PostgreSQLManager, lifetime=SINGLETON)
register_port(name="postgresql_async_engine", interface=AsyncEngine,
    impl=lambda r: r.resolve("postgresql_connection_manager").get_client(), lifetime=SINGLETON)
register_port(name="session_factory", interface=async_sessionmaker,
    impl=..., lifetime=SINGLETON)

# RBAC 仓储 (SCOPED)
register_port(name="user_repo", interface=UserRepositoryPort, impl=UserRepository, lifetime=SCOPED)
register_port(name="role_repo", interface=RoleRepositoryPort, impl=RoleRepository, lifetime=SCOPED)
register_port(name="user_role_repo", interface=UserRoleRepositoryPort, impl=UserRoleRepository, lifetime=SCOPED)
register_port(name="login_attempt_repo", interface=LoginAttemptRepositoryPort, impl=LoginAttemptRepository, lifetime=SCOPED)
register_port(name="audit_repo", interface=AuditRepositoryPort, impl=AuditRepository, lifetime=SCOPED)

# 记忆仓储 (SCOPED)
register_port(name="memory_metadata", interface=L2MetadataRepositoryPort,
    impl=PgMetadataRepo, lifetime=SCOPED)
register_port(name="memory_change_history", interface=L2ChangeHistoryRepositoryPort,
    impl=PgHistoryRepo, lifetime=SCOPED)
register_port(name="memory_group_member", interface=L2GroupMemberRepositoryPort,
    impl=PgGroupMemberRepo, lifetime=SCOPED)

# 事务/Outbox (SINGLETON)
register_port(name="outbox_repo", interface=OutboxRepository, impl=PostgreSQLOutboxRepository, lifetime=SINGLETON)
register_port(name="saga_repository", interface=SagaRepositoryProtocol, impl=PostgreSQLSagaRepository, lifetime=SCOPED)

# UoW (TRANSIENT)
register_port(name="uow_factory", interface=UnitOfWorkFactory, impl=PostgreSQLUnitOfWork, lifetime=TRANSIENT)
```

---

## 6. L3 向量存储

### 6.1 Rule 1: L3VectorPort

**文件:** `src/domain/ports/l3_vector.py`

```python
@runtime_checkable
class L3VectorPort(Protocol):
    async def upsert_points(self, collection: str, points: list[dict]) -> bool
    async def delete_points(self, collection: str, point_ids: list[str]) -> bool
    async def get_point(self, collection: str, point_id: str) -> dict | None
    async def search(self, collection: str, query_vector: list[float],
                     limit: int = 10, filter_payload: dict | None = None) -> list[dict]
    async def search_sparse(self, collection: str, sparse_vector: dict,
                            limit: int = 10, filter_payload: dict | None = None) -> list[dict]
    async def create_collection(self, collection: str, vector_size: int,
                                vector_params: dict | None = None) -> bool
    async def delete_collection(self, collection: str) -> bool
    async def collection_exists(self, collection: str) -> bool
    async def list_collections(self) -> list[str]
```

**设计要点:**
- 9 个异步方法，涵盖向量 CRUD + Collection 生命周期 + Dense/Sparse 检索
- `points` 使用 `list[dict]`（鸭子类型），不耦合 VectorPoint 值对象

### 6.2 Rule 2: MemoryVectorPort

**文件:** `src/application/ports/memory_vector_port.py`

```python
@runtime_checkable
class MemoryVectorPort(L3VectorPort, Protocol):
    async def index_memory(self, memory_id: str, content: str,
                           memory_type: str, owner_id: str) -> bool
    async def search_similar_memories(self, query: str, owner_id: str | None = None,
                                      memory_type: str | None = None, limit: int = 10) -> list[dict]
```

### 6.3 Rule 3: QdrantAdapter + QdrantManager

**QdrantAdapter** (`src/infrastructure/storage/qdrant/qdrant_adapter.py`):

```python
class QdrantAdapter(L3VectorPort):
    def __init__(self, storage: Any, collection_manager: Any | None = None)
```

- 薄适配器层，包装 `QdrantVectorStorage` + `QdrantCollectionManager`
- `upsert_points`: `list[dict]` → `list[VectorPoint]`（添加 `created_at`）
- `search_sparse`: `dict` → `SparseVector` 对象
- Collection 方法委托给 `collection_manager`

**QdrantVectorStorage** (`src/infrastructure/storage/qdrant/vector_storage.py`):

- 核心向量操作，使用 `qdrant_client.AsyncQdrantClient`
- `_normalize_point_id`: 字符串 ID → 整数 ID（Qdrant v1.7.x 要求）
- `search`: 构建 Qdrant Filter（支持 MatchValue + Range）
- `search_sparse`: 构建 `NamedSparseVector`，异常返回空列表

**QdrantCollectionManager** (`src/infrastructure/storage/qdrant/collection_manager.py`):

- Collection 生命周期管理
- 支持 Cosine/Euclidean/Dot 距离，配置 HNSW 索引

**QdrantManager** (`src/infrastructure/storage/qdrant/qdrant_manager.py`):

- 实现 `ConnectionManager` Protocol
- 懒初始化 `AsyncQdrantClient`

**数据模型** (`src/infrastructure/storage/qdrant/models.py`):

| 模型 | 关键参数 |
|------|---------|
| `VectorPoint` | `id: str, vector: list[float]` (维度=1024), `payload: dict` |
| `SparseVector` | `indices: list[int], values: list[float]` |
| `CollectionConfig` | `vector_size=1024, distance="Cosine", HNSW: m=16, ef_construct=128` |

**BM25Builder** (`src/infrastructure/storage/qdrant/bm25_builder.py`):

- TF-IDF 变体构建稀疏向量
- 120+ 英文停用词过滤

**QdrantConfig** (`src/infrastructure/config/qdrant.py`):

```python
@dataclass
class QdrantConfig:
    host: str = "localhost"        # QDRANT_HOST
    port: int = 6333               # QDRANT_PORT
    grpc_port: int = 6334          # QDRANT_GRPC_PORT
    api_key: str | None = None     # QDRANT_API_KEY
    timeout: float = 30.0          # QDRANT_TIMEOUT
```

### 6.4 Rule 4: QdrantMemoryVectorStorage

**文件:** `src/infrastructure/storage/qdrant/qdrant_memory_vector_storage.py`

```python
class QdrantMemoryVectorStorage(MemoryVectorPort):
    MEMORY_COLLECTION = "sisys_memories"
    def __init__(self, adapter: QdrantAdapter, embed_fn: Callable | None = None,
                 collection: str = MEMORY_COLLECTION)
```

- **组合注入** `QdrantAdapter`
- L3VectorPort 方法全部委托给 `self._adapter`
- `index_memory`: 调用 `embed_fn(content)` 生成向量 → 构造 points → `adapter.upsert_points`
- `search_similar_memories`: 调用 `embed_fn(query)` → 构建过滤条件 → `adapter.search`
- `_deterministic_embed`: SHA256 → 128 维伪向量（仅测试/开发用）

### 6.5 DI 注册

```python
# 连接管理器 (SINGLETON)
register_port(name="qdrant_connection_manager", interface=ConnectionManager,
    impl=lambda: QdrantManager(QdrantConfig.from_env()), lifetime=SINGLETON)
register_port(name="qdrant_client", interface=AsyncQdrantClient,
    impl=lambda r: r.resolve("qdrant_connection_manager").get_client(), lifetime=SINGLETON)

# Rule 3 (SCOPED)
register_port(name="l3_vector", interface=L3VectorPort,
    impl="...qdrant_adapter.QdrantAdapter", lifetime=SCOPED)

# Rule 4 (SCOPED)
register_port(name="memory_vector_storage", interface=MemoryVectorPort,
    impl="...qdrant_memory_vector_storage.QdrantMemoryVectorStorage", lifetime=SCOPED)
```

### 6.6 部署配置

**Qdrant v1.7.1**:
- REST 6333, gRPC 6334
- 资源限制: 开发 memory 2G/cpus 1.0, 生产 memory 8G/cpus 2.0
- 默认嵌入模型: `BAAI/bge-m3`（1024 维）

---

## 7. L4 对象存储

### 7.1 Rule 1: L4ObjectPort

**文件:** `src/domain/ports/l4_object.py`

```python
@runtime_checkable
class L4ObjectPort(Protocol):
    async def store(self, bucket_type: str, object_key: str, file_path: str,
                    content_type: str = "application/octet-stream",
                    tags: dict[str, str] | None = None) -> str
    def retrieve(self, bucket_type: str, object_key: str,
                 version_id: str | None = None) -> AsyncIterator[bytes]  # 同步方法
    async def delete(self, bucket_type: str, object_key: str,
                     version_id: str | None = None) -> bool
    async def get_metadata(self, bucket_type: str, object_key: str,
                           version_id: str | None = None) -> dict
    async def archive(self, bucket_type: str, object_key: str,
                      content: bytes | None = None, retention_days: int = 2555) -> str
    async def list_objects(self, bucket_type: str, prefix: str = "",
                           recursive: bool = True) -> list[dict]
```

**设计要点:**
- `retrieve` 是同步方法返回 `AsyncIterator[bytes]`（流式下载防 OOM）
- `store` 接受 `file_path`（流式上传防 OOM）
- `archive` 支持 WORM 合规归档（默认 2555 天 = 7 年）
- `bucket_type` 映射为物理 bucket: `{prefix}-{bucket_type}-{tenant_id}`

### 7.2 Rule 2: DocumentStoragePort

**文件:** `src/application/ports/document_storage_port.py`

```python
@runtime_checkable
class DocumentStoragePort(L4ObjectPort, Protocol):
    async def store_document(self, user_id: str, doc_type: str, file_path: str,
                             metadata: dict | None = None) -> str
    async def list_user_documents(self, user_id: str, doc_type: str | None = None) -> list[dict]
    async def get_document_metadata(self, user_id: str, document_id: str) -> dict | None
```

### 7.3 Rule 3: MinIOAdapter + MinioManager

**MinIOAdapter** (`src/infrastructure/storage/minio/minio_adapter.py`):

```python
class MinIOAdapter(L4ObjectPort):
    def __init__(self, repository: MinIORepository)
```

- 薄适配器，委托给 `MinIORepository`
- 所有方法一一对应委托

**MinIORepository** (`src/infrastructure/storage/minio/minio_repository.py`):

```python
class MinIORepository:
    def __init__(self, bucket_manager, object_operations, worm_manager,
                 tenant_id=None, redis_client=None)
```

- 组合 `BucketManager` + `ObjectOperations` + `WORMManager`
- `_resolve_bucket_name()`: `{prefix}-{bucket_type}-{tenant_id}`

**BucketManager** (`src/infrastructure/storage/minio/bucket_manager.py`):

- Bucket CRUD、命名验证（正则 `^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$`）
- 版本控制、Object Lock

**ObjectOperations** (`src/infrastructure/storage/minio/object_operations.py`):

- 流式上传/下载，大文件自动分片
- 分片策略: <100MB 不分片, 100MB-1GB 10MB 分片, 1GB-10GB 50MB 分片, >10GB 100MB 分片
- 断点续传: Redis 存储分片上传状态

**WORMManager** (`src/infrastructure/storage/minio/worm_lifecycle.py`):

- GOVERNANCE 模式 WORM 锁定
- 默认 2555 天（SOX 合规）
- 生命周期规则管理

**MinioManager** (`src/infrastructure/storage/minio/minio_manager.py`):

- 同步 Minio 客户端封装
- S3 错误到领域异常映射

**MinIOConfig** (`src/infrastructure/config/minio.py`):

```python
@dataclass
class MinIOConfig:
    host: str = "localhost"        # MINIO_HOST
    port: int = 9000               # MINIO_API_PORT
    access_key: str = ""           # MINIO_ROOT_USER
    secret_key: str = ""           # MINIO_ROOT_PASSWORD
    bucket_prefix: str = "sisys"   # MINIO_BUCKET_PREFIX
```

### 7.4 Rule 4: MinIODocumentStorage

**文件:** `src/infrastructure/storage/minio/minio_document_storage.py`

```python
class MinIODocumentStorage(DocumentStoragePort):
    def __init__(self, adapter: MinIOAdapter)
```

- **组合注入** `MinIOAdapter`
- L4ObjectPort 方法委托给 adapter
- `store_document`: 自动生成路径 `documents/{user_id}/{doc_type}/{YYYY-MM}/{timestamp}`
- `list_user_documents`: 前缀过滤

### 7.5 Bucket 类型映射

| bucket_type | 物理 Bucket | 保留策略 |
|-------------|------------|---------|
| `raw-documents` | `sisys-raw-documents-{tenant_id}` | 版本控制 |
| `processed-documents` | `sisys-processed-documents-{tenant_id}` | 版本控制 |
| `audit-archives` | `sisys-audit-archives-{tenant_id}` | WORM 7年 |
| `backups` | `sisys-backups-{tenant_id}` | WORM 7年 |
| `branches` | `sisys-branches-{tenant_id}` | 版本控制 |

### 7.6 DI 注册

```python
# Rule 3 (SCOPED)
register_port(name="l4_object", interface=L4ObjectPort,
    impl="...minio_adapter.MinIOAdapter", lifetime=SCOPED)

# Rule 4 (SCOPED)
register_port(name="document_storage", interface=DocumentStoragePort,
    impl="...minio_document_storage.MinIODocumentStorage", lifetime=SCOPED)
```

---

## 8. L5 图存储

### 8.1 Rule 1: L5GraphPort

**文件:** `src/domain/ports/l5_graph.py`

```python
@runtime_checkable
class L5GraphPort(Protocol):
    async def create_entity(self, memory_id: str, entity_type: str, properties: dict) -> bool
    async def get_entity(self, memory_id: str) -> dict | None
    async def delete_entity(self, memory_id: str) -> bool
    async def create_relationship(self, source_memory_id: str, target_memory_id: str,
                                  relationship_type: str, properties: dict | None = None) -> bool
    async def delete_relationship(self, source_memory_id: str, target_memory_id: str,
                                  relationship_type: str) -> bool
    async def find_related(self, memory_id: str, max_depth: int = 2,
                          relationship_type: str | None = None) -> list[dict]
    async def execute_query(self, cypher: str, params: dict | None = None) -> list[dict]
    async def execute_write_query(self, cypher: str, params: dict | None = None) -> list[dict]
    async def get_neighbors(self, memory_id: str, max_depth: int = 1,
                            edge_type: str | None = None) -> list[dict]
```

**设计要点:**
- `memory_id` 作为实体主键
- MERGE 语义: 实体已存在时更新
- 支持原生 Cypher 查询
- Cypher 注入防护: `_validate_rel_type()` + `_sanitize_property_keys()`

### 8.2 Rule 2: MemoryGraphPort

**文件:** `src/application/ports/memory_graph_port.py`

```python
@runtime_checkable
class MemoryGraphPort(L5GraphPort, Protocol):
    async def index_memory_relations(self, memory_id: str, content: str) -> int
    async def get_knowledge_graph(self, memory_id: str, depth: int = 2) -> dict
```

### 8.3 Rule 3: Neo4jAdapter + Neo4jManager

**Neo4jAdapter** (`src/infrastructure/storage/neo4j/neo4j_adapter.py`):

```python
class Neo4jAdapter(L5GraphPort):
    def __init__(self, storage: Any)
```

- 包装 `Neo4jGraphStorage`
- MERGE 语义创建实体/关系
- Cypher 参数化查询防注入
- `_validate_rel_type()`: `[A-Z_][A-Z0-9_]*` 命名规范
- `_sanitize_property_keys()`: 清洗属性键名

**Neo4jGraphStorage** (`src/infrastructure/storage/neo4j/graph_storage.py`):

- 底层 Cypher 执行器
- `execute_query` / `execute_write_query`: 参数化查询
- `find_path`: 可变长度模式路径查找
- `get_neighbors`: 支持方向 IN/OUT/BOTH

**Neo4jGraphManager** (`src/infrastructure/storage/neo4j/graph_manager.py`):

- MERGE 语义创建/删除节点和关系

**GraphRetriever** (`src/infrastructure/storage/neo4j/graph_retriever.py`):

- `find_related_entities`: 按连接数排序
- `find_related_documents`: MENTIONS 关系
- `find_community`: BFS/DFS 社区发现

**Neo4jManager** (`src/infrastructure/storage/neo4j/neo4j_manager.py`):

- 实现 `ConnectionManager` Protocol
- 构造函数注入 `AsyncDriver`
- `from_config()` 工厂方法

**数据模型** (`src/infrastructure/storage/neo4j/models.py`):

| 关系类型 | 说明 |
|---------|------|
| `MENTIONS` | 提及 |
| `DEPENDS_ON` | 依赖 |
| `RELATES_TO` | 相关 |
| `PART_OF` | 部分属于 |
| `INFLUENCES` | 影响 |
| `CONTRADICTS` | 矛盾 |

**Neo4jConfig** (`src/infrastructure/config/neo4j.py`):

```python
@dataclass
class Neo4jConfig:
    host: str = "localhost"               # NEO4J_HOST
    bolt_port: int = 7687                 # NEO4J_BOLT_PORT
    username: str = "neo4j"               # NEO4J_USERNAME
    password: str = ""                    # NEO4J_PASSWORD
    database: str = "neo4j"               # NEO4J_DATABASE
    max_connection_pool_size: int = 50    # NEO4J_MAX_POOL_SIZE
```

### 8.4 Rule 4: Neo4jMemoryGraphStorage

**文件:** `src/infrastructure/storage/neo4j/neo4j_memory_graph_storage.py`

```python
class Neo4jMemoryGraphStorage(MemoryGraphPort):
    def __init__(self, adapter: Neo4jAdapter)
```

- **组合注入** `Neo4jAdapter`
- L5GraphPort 方法全部委托给 `self._adapter`
- `index_memory_relations`: 创建 Memory 实体节点 + content_hash
- `get_knowledge_graph`: 获取实体 + `find_related` 关联实体
- `_content_hash()`: SHA256 短哈希

### 8.5 DI 注册

```python
# 连接管理器 (SINGLETON)
register_port(name="neo4j_connection_manager", interface=ConnectionManager,
    impl=lambda: Neo4jManager.from_config(Neo4jConfig.from_env()), lifetime=SINGLETON)
register_port(name="neo4j_driver", interface=AsyncDriver,
    impl=lambda r: r.resolve("neo4j_connection_manager").get_client(), lifetime=SINGLETON)

# Rule 3 (SCOPED)
register_port(name="l5_graph", interface=L5GraphPort,
    impl="...neo4j_adapter.Neo4jAdapter", lifetime=SCOPED)

# Rule 4 (SCOPED)
register_port(name="memory_graph_storage", interface=MemoryGraphPort,
    impl="...neo4j_memory_graph_storage.Neo4jMemoryGraphStorage", lifetime=SCOPED)
```

---

## 9. 统一存储网关

### 9.1 UnifiedStoragePort

**文件:** `src/domain/ports/unified_storage.py`

```python
@runtime_checkable
class UnifiedStoragePort(Protocol):
    async def save(self, memory_id, content, memory_type, owner_id, name, tier) -> dict[StorageLayer, bool]
    async def read(self, memory_id, memory_type, owner_id, name, prefer_cache) -> str | None
    async def delete(self, memory_id, memory_type, owner_id, name) -> dict[StorageLayer, bool]
    async def exists(self, memory_id, memory_type, owner_id, name) -> dict[StorageLayer, bool]
```

### 9.2 UnifiedStorageGateway

**文件:** `src/application/services/unified_storage_gateway.py`

**构造函数注入全部六层存储端口:**

```python
def __init__(
    self,
    l0_storage: L0StoragePort,                      # L0 文件系统
    memory_cache: MemoryCachePort,                   # L1 缓存
    l2_metadata: L2MetadataRepositoryPort,           # L2 元数据
    l2_history: L2ChangeHistoryRepositoryPort,       # L2 历史
    l2_group_member: L2GroupMemberRepositoryPort | None = None,  # L2 群组
    l3_vector: MemoryVectorPort | None = None,       # L3 向量
    l4_object: DocumentStoragePort | None = None,    # L4 对象
    l5_graph: MemoryGraphPort | None = None,         # L5 图
    event_publisher = None,                          # 事件发布器
)
```

**写入流程** (`save`):
1. `StoragePolicyService.decide_tier()` 确定存储策略
2. L0 文件系统同步写入（强一致，真相源）
3. L1 缓存写入（`set_memory`）
4. 发布 `MemoryChanged` 事件到 Outbox（事务发件箱）

**读取流程** (`read`):
1. L2 RBAC 校验（`_check_read_permission`）
2. L1 缓存优先（`prefer_cache=True` 时）
3. L0 回源 + 缓存回填

**删除流程** (`delete`):
1. L0 文件删除
2. L1 缓存失效
3. 发布 `MemoryChanged(change_type="delete")` 事件

**RBAC 校验** (`_check_read_permission`):
- private 记忆: 仅 owner 可读
- group 记忆: owner 或 group 成员可读
- 通过 `L2GroupMemberRepositoryPort` 检查成员关系

### 9.3 事件驱动更新

**MemoryChangedHandler** (`src/application/event_handlers/memory_changed_handler.py`):

```
MemoryChanged 事件
    ├── L1 Redis 缓存失效（立即）
    ├── L2 PostgreSQL 元数据/历史写入（异步）
    ├── L3 Qdrant 向量（按需，内容>500 tokens）[TODO #Story6.3]
    └── L5 Neo4j 图谱（按需）[TODO #Story1.17]
```

### 9.4 StoragePolicyService

**文件:** `src/domain/services/storage_tier_strategy.py`

| 访问频率 | 存储层级 | TTL |
|---------|---------|-----|
| ≥100/周 | HOT | 24h |
| 10-99/周 | WARM | 无 |
| 1-9/周 | COLD | 无（>10KB 压缩） |
| 0 或 Checkpoint | FROZEN | 无（压缩） |

### 9.5 DI 注册

```python
register_port(name="unified_storage", interface=UnifiedStoragePort,
    impl=lambda r: UnifiedStorageGateway(
        l0_storage=r.resolve("l0_storage"),
        memory_cache=r.resolve("memory_cache"),
        l2_metadata=r.resolve("memory_metadata"),
        l2_history=r.resolve("memory_change_history"),
        l2_group_member=r.resolve("memory_group_member"),
        l3_vector=r.resolve("memory_vector_storage"),
        l4_object=r.resolve("document_storage"),
        l5_graph=r.resolve("memory_graph_storage"),
        event_publisher=r.resolve("event_publisher"),
    ), lifetime=SCOPED)
```

---

## 10. 依赖注入体系

### 10.1 Resolver 机制

**文件:** `src/domain/ports/resolver.py`

`Resolver` 类支持三种生命周期:

| 生命周期 | 说明 |
|---------|------|
| **TRANSIENT** | 每次创建新实例 |
| **SCOPED** | 同一 scope 内共享实例 |
| **SINGLETON** | 全局唯一实例 |

**自动注入机制** (`_auto_inject`):
1. 检查构造函数参数
2. 按参数**名称** → `resolve(param_name)` 解析
3. 按参数**类型注解** → `resolve_by_interface(param_type)` 兜底
4. 递归解析: Rule 4 实现 → 发现 Rule 3 类型参数 → 自动实例化 Rule 3 → 注入 Rule 4

### 10.2 连接管理器统一协议

**文件:** `src/domain/ports/connection_manager.py`

```python
@runtime_checkable
class ConnectionManager(Protocol):
    async def health_check(self) -> bool
    async def close(self) -> None
    def get_client(self) -> Any
```

所有存储层的连接管理器均实现此协议，支持统一的生命周期管理和健康检查。

### 10.3 Shutdown 流程

```python
async def shutdown():
    await resolver.resolve("neo4j_connection_manager").close()
    await resolver.resolve("qdrant_connection_manager").close()
    await resolver.resolve("postgresql_connection_manager").close()
    await resolver.resolve("redis_connection_manager").close()
```

---

## 11. 测试体系

### 11.1 测试分层

| 测试类型 | 位置 | 覆盖内容 |
|---------|------|---------|
| **端口契约测试** | `tests/contracts/` | 端口注册、方法存在、元数据完整性 |
| **单元测试** | `tests/unit/` | Protocol 签名验证、Mock 行为、适配器委托 |
| **集成测试** | `tests/integration/` | Mock/真实后端端到端 |
| **验收测试 (BDD)** | `tests/acceptance/` | pytest-bdd 特性文件 |
| **架构约束测试** | `tests/unit/architecture/` | domain 层零 SQLAlchemy 依赖、依赖方向 |

### 11.2 各层测试覆盖

**L1 缓存:**
- `test_l1_cache_port.py` — Protocol 签名验证
- `test_redis_memory_cache.py` — 5 个测试类（L1 委托/Memory 方法/Port 合规/TTL 随机化/键构建）
- `test_redis_session_cache.py` — L1 委托 + Session 方法
- `test_semantic_cache.py` — FT.SEARCH mock/hit/miss/metrics
- `test_redis_integration.py` — 真实 Redis 集成

**L2 关系数据库:**
- `test_repository.py` — L2RdbPort async 签名验证
- `test_postgresql_adapter.py` — CRUD + 事务回滚
- `test_user_repository.py` / `test_role_repository.py` — RBAC 仓储
- `test_postgresql_manager.py` — 引擎创建/健康检查
- `test_session_middleware.py` — per-request session 管理
- `test_sqlalchemy_architecture.py` — domain 层零依赖验证

**L3 向量:**
- `test_l3_vector_port.py` — Protocol 签名验证
- `test_qdrant_adapter.py` — 适配器委托（6 个测试类）
- `test_qdrant_memory_vector_storage.py` — 完整测试（5 个测试类）
- `test_vector_storage.py` — QdrantVectorStorage CRUD + 检索
- `test_bm25_builder.py` — BM25 构建器
- Story 1.6 BDD 验收测试（7 个场景）

**L4 对象:**
- `test_l4_object_port.py` — Protocol 签名验证
- `test_minio_adapter.py` — L4ObjectPort 实现验证
- `test_minio_document_storage.py` — DocumentStoragePort 业务语义
- `test_object_operations.py` — 流式上传/下载/分片
- `test_bucket_management.py` — Bucket CRUD + WORM
- Story 1.7 BDD 验收测试

**L5 图:**
- `test_l5_graph_port.py` — Protocol 签名验证
- `test_neo4j_adapter.py` — 适配器委托验证
- `test_neo4j_memory_graph_storage.py` — 委托 + 特有语义
- `test_neo4j_graph_storage.py` — Cypher 执行
- `test_graph_retriever.py` — 检索器
- `test_graph_models.py` — GraphNode/GraphRelationship 模型
- Story 1.8 BDD 验收测试

---

## 12. 设计模式汇总

| 模式 | 应用位置 | 说明 |
|------|---------|------|
| **六边形架构 (Ports & Adapters)** | 全部六层 | Domain 定义 Protocol，Infrastructure 实现 |
| **Protocol 结构化子类型** | 所有 Port | `typing.Protocol` + `@runtime_checkable`，鸭子类型兼容 |
| **组合优于继承** | Rule 4 实现 | 组合注入 Rule 3 适配器，通用方法委托 |
| **模板方法模式** | PostgreSQLAdapter | 子类实现 `_to_entity` / `_to_model` / `_do_save` |
| **ContextVar Session 注入** | L2 仓储 | Session 不通过构造器传入，通过全局上下文变量获取 |
| **懒初始化单例** | 所有连接管理器 | 首次调用时创建连接池/引擎 |
| **工厂模式** | 所有 Config | `from_env()` 从环境变量构建配置 |
| **策略模式** | QdrantMemoryVectorStorage | `embed_fn` 参数注入支持不同 embedding 策略 |
| **事务发件箱 (Outbox)** | L2 + 事件系统 | 保证事件可靠发布 |
| **工作单元 (Unit of Work)** | PostgreSQLUnitOfWork | 管理事务边界，幂等 commit/rollback |
| **乐观锁** | PgMetadataRepository | 版本冲突检测 |
| **软删除模式** | PostgreSQLAdapter | `soft_delete_column` 可配置 |
| **Append-only 模式** | PgHistoryRepository | `delete()` 抛 NotImplementedError |
| **Row-Level Security** | audit_log/audit_outbox | PostgreSQL RLS 不可变策略 |
| **命名空间隔离** | Redis key_builder | `sisys:{namespace}:{parts}` 统一键格式 |
| **TTL 随机化** | RedisMemoryCache | 86400-108000 秒，防缓存雪崩 |
| **MERGE 语义** | Neo4jAdapter/L5 | 幂等创建 |
| **流式处理防 OOM** | MinIO | `file_path` 上传，`AsyncIterator[bytes]` 下载 |
| **WORM 合规** | MinIO | GOVERNANCE 模式 2555 天保留 |
| **端口注册表 (Registry)** | composition_root | `register_port()` + `Resolver` 统一装配 |

---

## 13. 关键文件索引

### 13.1 Domain 层端口

| 文件 | 端口 | Rule |
|------|------|------|
| `src/domain/ports/l0_storage.py` | `L0StoragePort` | Rule 1 |
| `src/domain/ports/index_manager.py` | `IndexManagerPort` | Rule 1 |
| `src/domain/ports/l1_cache.py` | `L1CachePort` | Rule 1 |
| `src/domain/ports/l2_rdb.py` | `L2RdbPort[T]` | Rule 1 |
| `src/domain/ports/l3_vector.py` | `L3VectorPort` | Rule 1 |
| `src/domain/ports/l4_object.py` | `L4ObjectPort` | Rule 1 |
| `src/domain/ports/l5_graph.py` | `L5GraphPort` | Rule 1 |
| `src/domain/ports/unified_storage.py` | `UnifiedStoragePort` | Rule 1 |
| `src/domain/ports/connection_manager.py` | `ConnectionManager` | Rule 1 |
| `src/domain/ports/storage_enums.py` | `StorageLayer`, `StorageTier`, `DataAccessPattern` | Rule 1 |
| `src/domain/ports/memory_repository.py` | `L2MetadataPort`, `L2HistoryPort`, `L2GroupMemberPort` | Rule 2 |
| `src/domain/ports/resolver.py` | `Resolver`, `PortRegistry` | DI 基础设施 |
| `src/domain/ports/registry.py` | `register_port`, `_global_registry` | DI 基础设施 |

### 13.2 Application 层端口

| 文件 | 端口 | Rule |
|------|------|------|
| `src/application/ports/memory_file_port.py` | `MemoryFilePort` | Rule 2 |
| `src/application/ports/memory_cache_port.py` | `MemoryCachePort` | Rule 2 |
| `src/application/ports/session_cache_port.py` | `SessionCachePort` | Rule 2 |
| `src/application/ports/semantic_cache.py` | `SemanticCache` | Rule 2 |
| `src/application/ports/memory_vector_port.py` | `MemoryVectorPort` | Rule 2 |
| `src/application/ports/document_storage_port.py` | `DocumentStoragePort` | Rule 2 |
| `src/application/ports/memory_graph_port.py` | `MemoryGraphPort` | Rule 2 |
| `src/application/services/unified_storage_gateway.py` | `UnifiedStorageGateway` | 统一网关 |

### 13.3 Infrastructure 层适配器

| 层级 | Rule 3 文件 | Rule 4 文件 |
|------|------------|------------|
| **L0** | `infrastructure/storage/fs/file_memory_adapter.py` | `infrastructure/storage/fs/memory_file_storage.py` |
| **L1** | `infrastructure/storage/redis/redis_adapter.py` | `infrastructure/storage/redis/redis_memory_cache.py` |
| | `infrastructure/storage/redis/redis_manager.py` | `infrastructure/storage/redis/redis_session_cache.py` |
| | `infrastructure/storage/redis/semantic_cache.py` | |
| **L2** | `infrastructure/storage/postgresql/repository/postgresql_adapter.py` | `infrastructure/storage/postgresql/repository/memory_metadata_repository.py` |
| | `infrastructure/storage/postgresql/postgresql_manager.py` | `infrastructure/storage/postgresql/repository/memory_change_history_repository.py` |
| | `infrastructure/storage/postgresql/session_context.py` | `infrastructure/storage/postgresql/repository/memory_group_member_repository.py` |
| | `infrastructure/storage/postgresql/models/*.py` | `infrastructure/storage/postgresql/repository/user_repository.py` |
| **L3** | `infrastructure/storage/qdrant/qdrant_adapter.py` | `infrastructure/storage/qdrant/qdrant_memory_vector_storage.py` |
| | `infrastructure/storage/qdrant/qdrant_manager.py` | |
| | `infrastructure/storage/qdrant/vector_storage.py` | |
| | `infrastructure/storage/qdrant/collection_manager.py` | |
| **L4** | `infrastructure/storage/minio/minio_adapter.py` | `infrastructure/storage/minio/minio_document_storage.py` |
| | `infrastructure/storage/minio/minio_repository.py` | |
| | `infrastructure/storage/minio/bucket_manager.py` | |
| | `infrastructure/storage/minio/object_operations.py` | |
| | `infrastructure/storage/minio/worm_lifecycle.py` | |
| **L5** | `infrastructure/storage/neo4j/neo4j_adapter.py` | `infrastructure/storage/neo4j/neo4j_memory_graph_storage.py` |
| | `infrastructure/storage/neo4j/neo4j_manager.py` | |
| | `infrastructure/storage/neo4j/graph_storage.py` | |
| | `infrastructure/storage/neo4j/graph_manager.py` | |

### 13.4 配置文件

| 层级 | 配置类 | 文件 |
|------|--------|------|
| L1 | `RedisConfig` | `src/infrastructure/config/redis.py` |
| L2 | `PostgreSQLConfig` | `src/infrastructure/config/postgresql.py` |
| L3 | `QdrantConfig` | `src/infrastructure/config/qdrant.py` |
| L4 | `MinIOConfig` | `src/infrastructure/config/minio.py` |
| L5 | `Neo4jConfig` | `src/infrastructure/config/neo4j.py` |
| - | `MemoryConfig` | `src/infrastructure/config/memory.py` |

---

## 14. 已知限制与 TODO

| 项目 | 状态 | 说明 |
|------|------|------|
| Memory 表 Alembic 迁移 | 缺失 | `memory_metadata`/`memory_change_history`/`memory_group_members` 表 ORM 已定义但无迁移脚本 |
| L3 向量索引触发 | TODO #Story6.3 | MemoryChangedHandler 中 L3 向量索引标记为 TODO |
| L5 图谱索引触发 | TODO #Story1.17 | MemoryChangedHandler 中 L5 图谱索引标记为 TODO |
| 仓储实现不一致 | 已知 | 部分仓储继承 PostgreSQLAdapter，部分直接实现端口（功能等价但风格不同） |
| SagaRepository raw SQL | 已知 | 使用 `text()` 原生 SQL，与其他仓储 ORM 风格不同 |
| MinIO 连接管理器 | 已知 | 使用同步 Minio 客户端，非异步 |
| L4 archive 签名 | 已修复 | archive() 静默丢弃 content 参数已修复 |
| L5 Cypher 注入 | 已修复 | whitelist 验证 + property key 清洗 |
