# SISYS L3 向量存储层重构设计方案

**版本:** v11.0
**日期:** 2026-05-14
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

## 二、设计原则与约束

### 2.1 架构原则

| 原则 | 说明 |
|------|------|
| **六边形架构** | Ports & Adapters 模式，Domain 层定义端口，Infrastructure 层提供适配器 |
| **Domain 零依赖** | `src/domain/ports/` 仅使用 `abc` + `typing`，禁止引入任何外部包 |
| **依赖方向** | Infrastructure → Domain → 无（单向依赖，禁止反向） |

### 2.2 接口设计原则

| 原则 | 说明 |
|------|------|
| **Protocol 优先** | 使用 `typing.Protocol`（结构化子类型），而非 `abc.ABC`（名义子类型） |
| **组合优于继承** | SemanticCachePort 独立于 L3VectorPort，通过组合调用其能力 |
| **异步优先** | 所有 Port 方法均为 `async def` |
| **最小接口** | 每个 Port 只定义调用方需要的方法，不预设实现需求 |

### 2.3 实现原则

| 原则 | 说明 |
|------|------|
| **委托模式** | QdrantL3VectorStore 不重写逻辑，委托给已有的 QdrantVectorStorage 和 QdrantCollectionManager |
| **优雅降级** | 缓存/向量操作失败时降级而非抛异常，保证主流程不中断 |
| **渐进迁移** | 旧接口（`SemanticCache`）与新接口（`SemanticCachePort`）并存，逐步废弃 |

### 2.4 约束条件

| 约束 | 说明 |
|------|------|
| **Qdrant 职责** | 向量存储与语义检索（Dense + Sparse） |
| **Redis 职责** | 缓存实际响应内容（带 TTL 管理） |
| **embedding 生成** | 职责归于上游服务（UnifiedStorageGateway / 应用层），Port 层不耦合 |
| **L3 启用条件** | 内容 >500 tokens 时启用向量检索（对应 architecture.md §11.1） |

---

## 三、四层模型设计

### 3.1 层级概览

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Domain - L3VectorPort                                  │
│  职责：定义最底层通用向量存储接口（CRUD + 检索 + Collection 管理） │
│  文件：src/domain/ports/l3_vector.py                             │
│  依赖：零外部依赖（仅 abc + typing）                             │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Domain - SemanticCachePort                              │
│  职责：定义语义缓存能力接口（组合调用 L3VectorPort，不继承）      │
│  文件：src/domain/ports/semantic_cache.py                        │
│  依赖：零外部依赖（仅 abc + typing）                             │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: Infrastructure - QdrantL3VectorStore                   │
│  职责：完整实现 L3VectorPort（委托 QdrantVectorStorage +        │
│        QdrantCollectionManager）                                  │
│  文件：src/infrastructure/storage/qdrant/qdrant_l3_vector_store.py│
│  依赖：qdrant-client, QdrantVectorStorage, QdrantCollectionManager│
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: Infrastructure - QdrantSemanticCacheStore             │
│  职责：实现 SemanticCachePort，使用 QdrantL3VectorStore + Redis   │
│       （双层架构：Qdrant 负责向量检索，Redis 负责内容缓存）       │
│  文件：src/infrastructure/storage/qdrant/semantic_cache_store.py │
│  依赖：L3VectorPort, aioredis, CacheResult                       │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Layer 1: L3VectorPort — 向量存储端口

**定位**: Domain 层最底层通用向量存储抽象。

**设计说明**:
- 与现有 `VectorStorage` ABC 语义完全兼容
- `collection` 参数由调用方管理（不在此层耦合 Collection 生命周期）
- `points` 使用 `list[dict]`（duck typing），实际 `VectorPoint` 由 Adapter 转换

#### I/O 接口契约（9 个方法）

**向量点 CRUD:**

| 方法 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `upsert_points` | `collection: str`, `points: list[dict]`（每项含 id, vector, payload） | `bool` | 批量插入或更新 |
| `delete_points` | `collection: str`, `point_ids: list[str]` | `bool` | 批量删除 |
| `get_point` | `collection: str`, `point_id: str` | `dict \| None`（{id, vector, payload}） | 获取单个向量点 |

**检索:**

| 方法 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `search` | `collection: str`, `query_vector: list[float]`, `limit: int = 10`, `filter_payload: dict?` | `list[dict]`（每项含 id, score, payload） | Dense 语义检索 |
| `search_sparse` | `collection: str`, `sparse_vector: dict`（含 indices + values）, `limit: int = 10`, `filter_payload: dict?` | `list[dict]`（每项含 id, score, payload） | BM25 稀疏检索 |

**Collection 管理:**

| 方法 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `create_collection` | `name: str`, `vector_size: int`, `distance: str = "Cosine"`, `**kwargs` | `bool` | 创建（支持 hnsw_config 等扩展参数） |
| `delete_collection` | `name: str` | `bool` | 删除 |
| `collection_exists` | `name: str` | `bool` | 检查存在性 |
| `list_collections` | 无 | `list[str]` | 列出所有 Collection 名称 |

> **签名变更**: `create_collection` 参数从旧签名 `(collection, vector_size, vector_params)` 统一为新签名 `(name, vector_size, distance, **kwargs)`。理由：`name` 更通用（不暴露引擎细节），`distance` 显式声明与 Qdrant SDK 对齐。

### 3.3 Layer 2: SemanticCachePort — 语义缓存端口

**定位**: Domain 层语义缓存抽象，独立于 L3VectorPort。

**设计说明**:
- 不继承 L3VectorPort（Redis 实现无法满足向量检索契约）
- 使用组合方式在实现层调用 L3VectorPort
- 定义语义相似度阈值（SIMILARITY_THRESHOLD = 0.95）和 TTL（3600s）

#### 数据结构

```
CacheResult:
  value: dict    — 缓存值（计算结果）
  hit: bool      — 是否命中缓存
```

#### I/O 接口契约（3 个方法）

| 方法 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `get_or_compute` | `query_embedding: list[float]`, `compute_fn: Callable → dict` | `CacheResult` | 缓存命中返回 {value, hit=True}，未命中调用 compute_fn 并写入缓存返回 {value, hit=False} |
| `invalidate` | `cache_key: str` | `bool` | 按 key 失效缓存 |
| `invalidate_by_embedding` | `query_embedding: list[float]` | `bool` | 按 embedding 哈希失效缓存 |

#### 旧接口迁移关系

```
旧接口 (src/application/ports/semantic_cache.py):
  SemanticCache.get(query_embedding, threshold) → dict | None
  SemanticCache.set(query_embedding, result, ttl) → None
  SemanticCache.invalidate(cache_key) → None

新接口 (src/domain/ports/semantic_cache.py):
  SemanticCachePort.get_or_compute(query_embedding, compute_fn) → CacheResult
  SemanticCachePort.invalidate(cache_key) → bool

迁移策略: 双接口并存，旧接口标注废弃，逐步迁移调用方
```

### 3.4 Layer 3: QdrantL3VectorStore — 向量存储实现

**定位**: Infrastructure 层 L3VectorPort 的完整 Qdrant 实现。

**设计说明**:
- 组合 `QdrantVectorStorage`（向量操作）和 `QdrantCollectionManager`（Collection 管理）
- 不重写底层逻辑，纯委托模式
- search_sparse 不再吞异常，向上传播由调用方处理

#### 组合结构

```
QdrantL3VectorStore 实现 L3VectorPort:
  依赖:
    QdrantClientWrapper ← 构造注入
  组合:
    _vector_storage ← QdrantVectorStorage(client_wrapper)
    _collection_manager ← QdrantCollectionManager(client_wrapper)
```

#### 方法委托映射

```
向量点 CRUD（委托 → _vector_storage）:
  upsert_points(collection, points)
    → _vector_storage.upsert_points(collection, points)
    类型转换: list[dict] → list[VectorPoint]（由 QdrantVectorStorage 处理）

  delete_points(collection, point_ids)
    → _vector_storage.delete_points(collection, point_ids)

  get_point(collection, point_id)
    → _vector_storage.get_point(collection, point_id)

检索（委托 → _vector_storage）:
  search(collection, query_vector, limit, filter_payload?)
    → _vector_storage.search(collection, query_vector, limit, filter_payload?)

  search_sparse(collection, sparse_vector, limit, filter_payload?)
    → _vector_storage.search_sparse(collection, sparse_vector, limit, filter_payload?)
    ⚠️ 异常处理变更: 原实现 except Exception: return [] → 改为向上抛出异常

Collection 管理（委托 → _collection_manager）:
  create_collection(name, vector_size, distance, **kwargs)
    → _collection_manager.create_collection(name, vector_size, distance, **kwargs)

  delete_collection(name)
    → _collection_manager.delete_collection(name)

  collection_exists(name)
    → _collection_manager.collection_exists(name)

  list_collections()
    → _collection_manager.list_collections()
```

### 3.5 Layer 4: QdrantSemanticCacheStore — 语义缓存实现

**定位**: Infrastructure 层 SemanticCachePort 的 Qdrant+Redis 双层实现。

**设计说明**:
- **双层架构**: Qdrant 负责向量检索，Redis 负责缓存实际响应内容（带 TTL）
- Qdrant payload 存储 `{cache_key, result}`，其中 result 作为 Redis 过期后的降级数据源
- Redis 依赖通过构造注入（aioredis.Redis 实例）

#### 组合结构

```
QdrantSemanticCacheStore 实现 SemanticCachePort:
  依赖（构造注入）:
    l3_vector: L3VectorPort          — 向量检索能力
    redis_client: aioredis.Redis     — 内容缓存 + TTL
  配置:
    collection: str = "semantic_cache"
    similarity_threshold: float = 0.95
    ttl: int = 3600（秒）
  常量:
    _CACHE_VECTOR_SIZE = 1024        — bge-m3 向量维度
    _CACHE_PREFIX = "sem_cache:"     — Redis key 前缀
```

#### get_or_compute 工作流程（伪码）

```
输入: query_embedding, compute_fn

Step 1: Qdrant 向量检索
  results ← l3_vector.search(collection, query_embedding, limit=1)
  失败 → 记录警告，results = []，进入 Step 3

Step 2: 命中判定
  if results[0].score ≥ similarity_threshold:
    cache_key ← results[0].payload.cache_key
    cached ← redis_client.GET(prefix + cache_key)
    if cached → return CacheResult(value=cached, hit=True)
    Redis 失败 → 降级返回 CacheResult(value=payload.result, hit=True)

Step 3: 未命中 → 调用 compute_fn
  result ← compute_fn()
  cache_key ← hash_embedding(query_embedding)

Step 4: 写入 Redis（带 TTL）
  redis_client.SETEX(prefix + cache_key, ttl, serialize(result))
  失败 → 记录警告（不阻塞）

Step 5: 写入 Qdrant（payload 含 cache_key + result）
  l3_vector.upsert_points(collection, [{
    id: cache_key,
    vector: query_embedding,
    payload: {cache_key, result}
  }])
  失败 → 记录警告（不阻塞）

输出: CacheResult(value=result, hit=False)
```

#### invalidate 工作流程（双删策略）

```
输入: cache_key

Step 1: Qdrant 删除
  l3_vector.delete_points(collection, [cache_key])
  失败 → 记录警告

Step 2: Redis 删除
  redis_client.DELETE(prefix + cache_key)
  失败 → 记录警告

输出: 两步均成功 → True，任一失败 → False
```

#### invalidate_by_embedding 工作流程

```
输入: query_embedding

cache_key ← hash_embedding(query_embedding)
→ 委托 invalidate(cache_key)
```

#### 辅助方法

```
hash_embedding(embedding):
  取前10个维度，精度截断到6位小数
  → MD5 哈希 → 取前16字符作为 cache_key
```

#### Redis 依赖注入方案

`register_port` 无法自动注入非 Port 类型（如 `aioredis.Redis`），需使用工厂函数：

```
// composition_root.py 中使用工厂函数模式
semantic_cache_factory():
  redis_client ← 从 Resolver 获取或创建 aioredis.Redis 实例
  l3_vector ← 从 Resolver 获取 L3VectorPort 实例
  return QdrantSemanticCacheStore(l3_vector, redis_client)
```

### 3.6 端口注册

在 `composition_root.py` 中注册 3 个端口：

```
register_port("l3_vector"):
  interface: L3VectorPort
  impl: QdrantL3VectorStore
  lifetime: SCOPED

register_port("semantic_cache"):
  interface: SemanticCachePort
  impl: QdrantSemanticCacheStore
  lifetime: SCOPED
  ⚠️ 需工厂函数注入 Redis 依赖

register_port("semantic_cache_redis"):
  interface: SemanticCachePort
  impl: RedisSemanticCacheAdapter
  lifetime: SCOPED
```

### 3.7 UnifiedStorageGateway 集成

在 `UnifiedStorageGateway.save()` 中启用 L3 向量存储：

```
save(memory_id, content, memory_type, owner_id, name, tier?):
  ...
  // L3 向量存储（内容 >500 tokens 时按需启用）
  if self._l3 存在 AND len(content) > 500:
    embedding ← _generate_embedding(content)
    l3_vector.upsert_points("memories", [{
      id: memory_id,
      vector: embedding,
      payload: {memory_id, owner: owner_id}
    }])
    成功 → results[L3_VECTOR] = True
    失败 → 记录警告, results[L3_VECTOR] = False
  ...
```

---

## 四、关键设计决策

### 决策 1: L3VectorPort.create_collection 参数统一

**问题**: Port 定义 `(collection, vector_size, vector_params)` 与 QdrantCollectionManager 实现 `(name, vector_size, distance, **kwargs)` 不一致。

**方案**: 统一为新签名。

```
旧: create_collection(collection: str, vector_size: int, vector_params: dict?)
新: create_collection(name: str, vector_size: int, distance: str = "Cosine", **kwargs)
```

**理由**: `name` 比 `collection` 更通用（不暴露存储引擎细节）；`distance` 参数显式声明与 Qdrant SDK 对齐；`**kwargs` 支持扩展参数。

### 决策 2: QdrantL3VectorStore 组合策略

**问题**: `QdrantVectorAdapter` 仅包装 `QdrantVectorStorage`，缺少 Collection 管理方法。

**方案**: 新建 `QdrantL3VectorStore`，组合两个已有组件。

```
QdrantL3VectorStore:
  组合 QdrantVectorStorage（5 个向量操作方法）
       + QdrantCollectionManager（4 个 Collection 管理方法）
  → 完整实现 L3VectorPort 的 9 个方法
```

**理由**: QdrantCollectionManager 已完整实现，组合优于继承，保留 QdrantVectorAdapter 向后兼容。

### 决策 3: SemanticCachePort 不继承 L3VectorPort

**问题**: 若 SemanticCachePort 继承 L3VectorPort，Redis 实现无法满足 `search()` 等向量检索方法的契约。

**方案**: SemanticCachePort 保持独立接口，通过构造注入 L3VectorPort 实例实现组合调用。

**理由**: 不同实现的底层能力不同（Qdrant 支持向量检索，Redis 不支持），强制继承导致接口契约无法满足。

---

## 五、执行步骤

### Phase 1: P0 修复（阻塞性问题）

| Step | 文件 | 变更 |
|------|------|------|
| 1.1 | `vector_storage.py` | `search_sparse` 异常处理：`except Exception: return []` → 记录日志并 `raise` |
| 1.2 | `l3_vector.py` | `create_collection` 签名：`(collection, vector_size, vector_params)` → `(name, vector_size, distance, **kwargs)` |
| 1.3 | `qdrant_l3_vector_store.py`（新建） | 创建 QdrantL3VectorStore，组合委托实现 9 个方法（详见 §3.4） |
| 1.4 | `composition_root.py` | 添加 `l3_vector` 端口注册（详见 §3.6） |
| 1.5 | `unified_storage_gateway.py` | `save()` 中添加 L3 向量存储逻辑（详见 §3.7） |

**P0 修复依赖链**: P0-1（独立）→ P0-4 → P0-2 → P0-3

### Phase 2: P1 修复（重要问题）

| Step | 文件 | 变更 |
|------|------|------|
| 2.1 | `domain/ports/semantic_cache.py`（新建） | 创建 SemanticCachePort 接口 + CacheResult 数据结构（详见 §3.3） |
| 2.2 | `qdrant/semantic_cache_store.py`（新建） | 创建 QdrantSemanticCacheStore 双层实现（详见 §3.5） |
| 2.3 | `redis/semantic_cache_adapter.py` | RedisSemanticCache 适配 SemanticCachePort 新接口 |
| 2.4 | `application/ports/semantic_cache.py` | 旧 SemanticCache 标注废弃，保留方法签名不变 |

### Phase 3: 验证

| Step | 验证项 | 通过条件 |
|------|--------|----------|
| 3.1 | 架构验证 | Domain 层零依赖；QdrantL3VectorStore 实现 9 个方法；SemanticCachePort 不继承 L3VectorPort |
| 3.2 | 集成验证 | `l3_vector` 和 `semantic_cache` 端口注册成功 |
| 3.3 | 向后兼容 | 旧 SemanticCache 接口的 `get`/`set`/`invalidate` 仍可导入 |

---

## 六、风险与缓解

| ID | 风险 | 影响 | 缓解措施 |
|----|------|------|----------|
| R1 | L3 接口参数变更破坏现有调用 | 中 | 保留旧参数名作为别名 |
| R2 | UnifiedStorageGateway 使用 l3 导致异常 | 中 | 添加 try/catch 降级 |
| R3 | search_sparse 异常抛出破坏现有流程 | 低 | 确认所有调用方已处理异常 |
| R4 | SemanticCachePort 接口迁移影响调用方 | 高 | 渐进迁移，提供废弃警告 |

---

## 七、验收标准

### 7.1 架构验证

```
验证 Domain 层零依赖:
  l3_vector.py 不包含任何外部包 import
  semantic_cache.py 不包含任何外部包 import

验证 QdrantL3VectorStore 完整实现:
  9 个方法全部存在（upsert_points, delete_points, get_point,
    search, search_sparse, create_collection, delete_collection,
    collection_exists, list_collections）

验证 SemanticCachePort 独立性:
  SemanticCachePort 不是 L3VectorPort 的子类
```

### 7.2 功能验证

```
L3 向量存储 CRUD:
  create_collection → collection_exists == True
  upsert_points → get_point 返回正确数据
  search → 返回包含 score 的结果
  delete_points → get_point 返回 None
  delete_collection → collection_exists == False

语义缓存:
  get_or_compute (cache miss) → hit == False
  get_or_compute (cache hit) → hit == True
  invalidate → 缓存被清除
```

### 7.3 向后兼容验证

```
旧接口仍可导入:
  from src.application.ports.semantic_cache import SemanticCache
  SemanticCache 具有 get / set / invalidate 方法
```

---

## 八、语义缓存工作流程

### 8.1 端到端流程

```
1. 计算 embedding
2. Qdrant.search(embedding, limit=1, score_threshold=0.95)
   ↓命中
3. 获得 payload 中的 cache_key → Redis.GET(cache_key) → 返回缓存响应
   ↓未命中
4. 调用 LLM → 生成响应 → 写入 Redis(SET cache_key response EX 3600)
                                → 写入 Qdrant(embedding + payload{cache_key, result})
```

### 8.2 设计合理性

| 设计点 | 评价 |
|--------|------|
| cache_key 存储在 Qdrant payload | ✅ 合理 — 查询效率高，避免 Redis 全表扫描 |
| result 存储在 Qdrant payload | ✅ 合理 — Redis 过期后的降级数据源，避免"幽灵向量" |
| embedding → cache_key 哈希生成 | ✅ 确定性哈希，同一查询生成相同 key |
| Qdrant + Redis 分离存储 | ✅ 合理 — 各司其职，Qdrant 向量检索，Redis 内容缓存 |

### 8.3 一致性风险

| 场景 | 风险 | 严重程度 |
|------|------|---------|
| Qdrant 写入失败 + Redis 成功 | 幽灵缓存 — Qdrant 有向量但 Redis 无数据 | 高 |
| Redis 写入失败 + Qdrant 成功 | 调用方不知道缓存未写入 | 中 |
| Qdrant 搜索失败 | 请求直接失败，无降级 | 高 |
| Redis 读取失败与未命中混淆 | 返回 None 无法区分两种情况 | 中 |

### 8.4 发现的问题

| 问题 | 严重程度 | 说明 |
|------|---------|------|
| QdrantSemanticCacheStore 不存在 | 高 | 设计文档中的实现未创建 |
| score_threshold 参数不支持 | 中 | `QdrantVectorStorage.search()` 无此参数，需后过滤 |
| Redis 依赖注入缺失 | 中 | composition_root 未展示 redis_client 注入方式 |

### 8.5 改进建议

1. 实现 QdrantSemanticCacheStore（详见 §3.5）
2. 扩展 `QdrantVectorStorage.search()` 添加 `score_threshold` 参数支持
3. 统一 TTL 配置为 3600s（或暴露为配置参数）
4. 添加写入后读取验证
5. 考虑 Outbox Pattern 确保 Qdrant 和 Redis 写入一致性

---

## 九、审查附录

### 9.1 P0 问题验证结果

| 问题 | 状态 | 验证方法 |
|------|------|---------|
| P0-1: QdrantVectorAdapter 缺 4 个 Collection 方法 | **未修复** | qdrant_vector_adapter.py 无 create_collection/delete_collection/collection_exists/list_collections |
| P0-2: l3_vector 未注册 | **未修复** | composition_root.py 中无 l3_vector 注册 |
| P0-3: self._l3 未使用 | **未修复** | UnifiedStorageGateway.save() 未调用 self._l3 |
| P0-4: search_sparse 异常吞没 | **未修复** | vector_storage.py:200 仍是 `except Exception: return []` |

### 9.2 接口签名验证

| 接口 | 位置 | 当前签名 | 问题 |
|------|------|---------|------|
| L3VectorPort.create_collection | domain/ports/l3_vector.py | `collection, vector_size, vector_params` | **旧签名** |
| QdrantCollectionManager.create_collection | infrastructure/collection_manager.py | `name, vector_size, distance, **kwargs` | **新签名** |

### 9.3 新文件存在性验证

| 文件（计划创建） | 状态 |
|----------------------|------|
| `src/infrastructure/storage/qdrant/qdrant_l3_vector_store.py` | **不存在** |
| `src/infrastructure/storage/qdrant/semantic_cache_store.py` | **不存在** |
| `src/domain/ports/semantic_cache.py` | **不存在** |

### 9.4 架构验证结果

- Domain 层零依赖：✅ 正确（l3_vector.py 仅使用 typing.Protocol）
- 六边形架构约束测试：✅ 27/27 通过
- qdrant-client 1.7.1 API 兼容性：✅ 无问题

### 9.5 UnifiedStorageGateway L3 使用差距

| 差距项 | 严重程度 |
|--------|---------|
| self._l3 在 save/read/delete 中从未被调用 | P0 |
| 缺少 _generate_embedding 方法 | P0 |
| 缺少内容大小判断逻辑（>500 tokens） | P0 |
| 缺少 Collection 管理 | P1 |
| 缺少 L3 错误处理和降级策略 | P1 |

---

## 十、修正记录

| 版本 | 日期 | 修正项 | 说明 |
|------|------|--------|------|
| v2.0 | 2026-05-13 | SemanticCachePort 不继承 L3VectorPort | Redis 实现无法满足向量检索契约 |
| v2.0 | 2026-05-13 | QdrantVectorStore 完整实现 create_collection | 移除占位符 |
| v3.0 | 2026-05-13 | P0 问题系统性修复 | search_sparse 异常处理、接口参数统一 |
| v3.0 | 2026-05-13 | QdrantL3VectorStore 组合策略 | 组合 QdrantVectorStorage + QdrantCollectionManager |
| v3.0 | 2026-05-13 | UnifiedStorageGateway self._l3 使用 | L3 功能不再虚设 |
| v3.0 | 2026-05-13 | L3VectorPort 接口参数统一 | collection → name, vector_params → distance |
| v4.0 | 2026-05-13 | 代码验证发现 v3.0 计划变更未实现 | 所有 P0/P1 问题仍未修复 |
| v5.0 | 2026-05-13 | 第二轮5轮审查完成 | SemanticVectorPort 歧义；Redis 连接池问题；P0 修复依赖关系 |
| v6.0 | 2026-05-13 | 语义缓存工作流程评审 | Qdrant+Redis 分离式设计确认 |
| v7.0 | 2026-05-13 | §3.2.2 重写为双层设计 | 修正架构矛盾；统一 TTL=3600；添加 invalidate_by_embedding |
| v8.0 | 2026-05-13 | 第3轮审查残留修正 | Layer 4 描述；过时注释；Redis 依赖注入 |
| v9.0 | 2026-05-13 | 第4轮审查修正 | 渐进迁移方案；payload {cache_key, result}；降级数据源 |
| v10.0 | 2026-05-13 | 第5轮审查最终修正 | P0 编号对齐；向后兼容验证；移除已解决问题 |
| v11.0 | 2026-05-14 | **文档结构重构** | 新增设计原则章节；扩展四层模型I/O契约；实际代码转伪码 |

---

**文档状态**: v11.0 设计文档重构完成
**下一步**: 执行 P0 问题的实际代码实现
