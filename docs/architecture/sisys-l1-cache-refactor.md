# SISYS L1缓存层重构设计方案

**版本:** v4.0
**日期:** 2026-05-14
**状态:** 设计阶段
**审查状态:** v4.0 文档完善

---

## 修订说明 (v4.0)

| 审查问题 | 严重程度 | 修订内容 |
|----------|----------|----------|
| 执行步骤缺少进度跟踪 | P0 | 详细步骤使用checkbox格式，便于跟踪 |
| 保持四层模型 | P1 | 明确四层架构：Domain→Application→Infrastructure技术→Infrastructure实现 |
| SemanticCache未继承L1CachePort | P0 | 确认问题存在，规划Phase 4修复 |
| 方法命名不规范 | P1 | get→get_by_embedding, set→set_with_embedding |
| RedisConfig默认值不一致 | P0 | 添加问题说明：class=10 vs from_env()=100 |
| 6个Adapter独立ConnectionPool | P0 | 添加问题说明，规划Phase 1-9统一连接池 |
| IdempotencyChecker硬编码参数 | P0 | 添加问题说明，纳入连接池统一管理 |
| Layer 2 MemoryCachePort不存在 | P0 | 实际代码中不存在此接口 |
| SessionStorage不应继承L1CachePort | P1 | 语义不同，会话管理vs键值缓存，保持独立 |
| Phase 1/3/5文件不存在 | P0 | pool_provider.py/l1_cache_adapter.py/semantic_cache_adapter.py 均不存在 |
| Phase 2/4未完成 | P0 | L1CachePort仍是专用接口，SemanticCache未继承L1CachePort |
| 接口变更影响12+处调用 | P0 | unified_storage_gateway.py等业务代码直接调用旧接口 |
| Qdrant/Redis TTL不一致导致伪命中 | **P0** | Qdrant payload 存 {cache_key, response}，Redis过期后从payload回填 |
| Qdrant写入失败导致孤儿Redis key | **P1** | 写入顺序：先写Qdrant再写Redis |
| §3.5 旧实现使用全表扫描O(n) | **P0** | 替换为Qdrant ANN索引 + Redis双组件设计 |
| 四层模型MemoryCachePort自相矛盾 | **P0** | Layer 2/4移除不存在的MemoryCachePort，RedisMemoryCache直接实现L1CachePort |
| Phase 5.4与Qdrant设计矛盾 | **P0** | "实现纯Python余弦相似度"改为"集成Qdrant ANN检索" |
| §2.2缺少invalidate方法 | **P0** | SemanticCachePort补充invalidate(cache_key)方法 |
| Layer 2引用Layer 3具体类名 | **P1** | §3.2设计说明改为"组合L1CachePort实例" |
| §1.1 L1CachePort标记不准 | **P1** | 改为"⚠️专用接口，待重构为通用接口" |
| §1.1补充遗漏端口 | **P1** | 补充PublicBlackboard/EventPublisher/EventSubscriber接口行 |

---

## 一、现状分析

### 1.1 当前接口定义

| 接口 | 位置 | 方法签名 | 问题 |
|------|------|----------|------|
| `L1CachePort` | `src/domain/ports/l1_cache.py` | `get(memory_type, owner_id, name)`, `set(...)`, `delete(...)`, `invalidate_pattern(...)` | ⚠️ 专用接口，待重构为通用接口 |
| `SemanticCache` | `src/application/ports/semantic_cache.py` | `get(query_embedding, threshold)`, `set(query_embedding, result, ttl)`, `invalidate(cache_key)` | ❌ 未继承L1CachePort，方法命名不规范 |
| `SessionStorage` | `src/domain/ports/session_storage.py` | `save/load/delete/exists` | — 独立接口，不应继承L1CachePort |
| `PublicBlackboard` | `src/application/ports/public_blackboard.py` | `post/get/get_by_agent/get_latest` | — 独立接口 |
| `EventPublisher` | `src/application/ports/event_subscriber.py` | `publish(event)` | — 独立接口 |
| `EventSubscriber` | `src/application/ports/event_subscriber.py` | `subscribe/start/close` | — 独立接口 |

**问题说明：**
- `SemanticCache` 应改名为 `SemanticCachePort` 并继承 `L1CachePort`
- `get` 方法应改名为 `get_by_embedding`，`set` 应改名为 `set_with_embedding`

### 1.2 当前实现（8个Adapter现状）

**当前状态：8个Adapter × 独立ConnectionPool**

```
┌─────────────────────────────────────────────────────┐
│  RedisMemoryCache        → ConnectionPool #1        │
│  RedisSessionStorage     → ConnectionPool #2        │
│  RedisSemanticCache      → ConnectionPool #3        │
│  RedisPublicBlackboard  → ConnectionPool #4        │
│  RedisEventPublisher    → ConnectionPool #5        │
│  RedisEventSubscriber   → ConnectionPool #6        │
│  RedisSnapshotStore     → ConnectionPool #7        │
│  RedisEventBus          → ConnectionPool #8        │
└─────────────────────────────────────────────────────┘
                    ↓
         连接数 = 8 × max_connections
         可能耗尽Redis服务器连接限制
```

**详细实现清单：**

| 实现类 | 位置 | ConnectionPool | 实现接口 | 状态 |
|--------|------|---------------|----------|------|
| `RedisMemoryCache` | `infrastructure/storage/redis/` | 接受外部client ✅ | `L1CachePort` | ✅ |
| `RedisSessionStorage` | `infrastructure/storage/redis/` | 自建 ❌ | `SessionStorage` | ❌ |
| `RedisSemanticCache` | `infrastructure/storage/redis/` | 自建 ❌ | 无（直接实现语义逻辑） | ❌ |
| `RedisPublicBlackboard` | `infrastructure/storage/redis/` | 自建 ❌ | `PublicBlackboard` | ❌ |
| `RedisEventPublisher` | `infrastructure/messaging/` | 自建 ❌ | 事件发布 | ❌ |
| `RedisEventSubscriber` | `infrastructure/messaging/` | 自建 ❌ | 事件订阅 | ❌ |
| `RedisSnapshotStore` | `infrastructure/storage/` | 接受外部client ✅ | `SnapshotRepositoryProtocol` | ✅ |
| `RedisEventBus` | `infrastructure/messaging/` | 委托上述两者 ⚠️ | `EventPublisher`+`EventSubscriber` | ⚠️ |

**P0问题补充（Round 4发现）：**
- `RedisSemanticCache` 不使用 Qdrant，使用纯 Python 全表扫描 + 余弦相似度计算，性能极差（O(n)）
- `RedisSemanticCache` 无 `RedisL1CacheAdapter` 组合关系，直接管理连接池
- 构造函数签名不统一：`RedisMemoryCache(redis_client)` vs `RedisSemanticCache(config)`

**说明：**
- ✅ 已支持外部注入，无需改造
- ❌ 自建ConnectionPool，需要改造
- ⚠️ 混合模式，通过委托实现

### 1.3 问题根因

```
当前架构问题：

Domain Layer
└── L1CachePort (通用接口: key/value) ✅
    SemanticCache (独立接口，未继承) ❌
    SessionStorage (独立接口，未继承)

Infrastructure Layer
├── RedisMemoryCache → 接受外部client ✅
├── RedisSemanticCache → 自建ConnectionPool ❌
├── RedisPublicBlackboard → 自建ConnectionPool ❌
├── RedisSessionStorage → 自建ConnectionPool ❌
├── RedisEventPublisher → 自建ConnectionPool ❌
├── RedisEventSubscriber → 自建ConnectionPool ❌
├── RedisSnapshotStore → 接受外部client ✅
└── RedisEventBus → 委托上述两者 ⚠️

问题：
1. SemanticCache 未继承 L1CachePort（违反四层架构）
2. SemanticCache 方法命名不规范（get/set 应为 get_by_embedding/set_with_embedding）
3. 6个Adapter各自管理ConnectionPool（除RedisMemoryCache和RedisSnapshotStore）
4. RedisConfig max_connections 默认值不一致：class=10 vs from_env()=100 ⚠️ P0
5. IdempotencyChecker 硬编码连接参数，绕过 RedisConfig ⚠️ P0
6. composition_root 未初始化共享连接池 ⚠️ P0
```

### 1.4 连接池配置现状

**硬编码问题：** 每个Adapter独立管理连接池，配置分散：

```python
# 各Adapter的_get_pool()方法重复相同的配置逻辑
max_connections=10  # 硬编码，未统一
socket_timeout=5.0  # 重复
decode_responses=True  # 重复
```

---

## 二、目标架构

### 2.1 四层职责模型

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Domain Layer - L1CachePort（统一抽象缓存端口）           │
│                                                                  │
│  职责：定义最底层通用缓存接口（get/set/delete）                    │
│  位置：src/domain/ports/l1_cache.py                              │
│  特点：领域层零依赖，纯抽象协议                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↑ 继承
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Application Layer - 语义缓存端口                        │
│                                                                  │
│  职责：继承L1CachePort，扩展语义检索能力                           │
│  位置：src/application/ports/semantic_cache.py                    │
│  端口：SemanticCachePort(L1CachePort, Protocol)                   │
│  新增方法：get_by_embedding / set_with_embedding / invalidate    │
│                                                                  │
│  不纳入四层继承的端口（保持独立）：                                 │
│    - SessionStorage (会话管理，语义不同，不继承L1CachePort)         │
│    - PublicBlackboard (公共黑板，独立端口)                         │
│    - EventPublisher/EventSubscriber (事件通道，独立端口)           │
└─────────────────────────────────────────────────────────────────┘
                              ↑ 实现
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: Infrastructure - Redis技术实现 + 连接池管理              │
│                                                                  │
│  职责：实现L1CachePort接口 + Redis连接池统一管理                   │
│  位置：src/infrastructure/storage/redis/                           │
│  组件：                                                          │
│    - RedisPoolProvider (连接池单例)                               │
│    - RedisL1CacheAdapter (实现L1CachePort)                        │
│  特点：技术可替换（未来可新增MemcachedAdapter等）                  │
└─────────────────────────────────────────────────────────────────┘
                              ↑ 实现 + 组合
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: Infrastructure - 语义缓存端口实现                       │
│                                                                  │
│  职责：实现SemanticCachePort，组合Layer 3组件                      │
│  位置：src/infrastructure/storage/redis/                           │
│  组件：                                                          │
│    - RedisSemanticCacheAdapter (实现SemanticCachePort)           │
│      ├─ QdrantClient: 向量存储与语义检索（ANN索引）               │
│      └─ RedisL1CacheAdapter: 基础缓存能力（带TTL管理）            │
│    - RedisMemoryCache (直接实现L1CachePort，无中间端口)           │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 接口继承关系

```python
# Layer 1: Domain统一抽象
class L1CachePort(Protocol):
    """通用缓存接口 - 最底层抽象"""
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int | None = None) -> bool: ...
    async def delete(self, key: str) -> bool: ...

# Layer 2: Application具体缓存端口
class SemanticCachePort(L1CachePort, Protocol):
    """语义缓存接口 - 继承L1CachePort"""
    async def get_by_embedding(self, query_embedding: list[float], threshold: float) -> dict | None: ...
    async def set_with_embedding(self, query_embedding: list[float], result: dict, ttl: int) -> None: ...
    async def invalidate(self, cache_key: str) -> None: ...

# Layer 3: Infrastructure Redis技术实现
class RedisL1CacheAdapter(L1CachePort):
    """Redis通用缓存实现 — 支持 PoolProvider 注入"""
    def __init__(self, redis_client=None): ...          # 委托 RedisPoolProvider.get_client()

# Layer 4: Infrastructure Qdrant + Redis 双组件实现
class RedisSemanticCacheAdapter(SemanticCachePort):
    """语义缓存适配器 — Qdrant(语义检索) + Redis(内容缓存)"""
    def __init__(self, qdrant_client, redis_client=None):
        self._qdrant = qdrant_client                    # Qdrant: 向量存储与语义检索
        self._base = RedisL1CacheAdapter(redis_client)  # Redis: 基础缓存能力

    # L1CachePort 继承方法（委托给 _base）
    async def get(key):        → self._base.get(key)
    async def set(key, v, ttl): → self._base.set(key, v, ttl)
    async def delete(key):     → self._base.delete(key)

    # SemanticCachePort 语义方法（见 §2.2.1 工作流程）
    async def get_by_embedding(query_embedding, threshold): ...
    async def set_with_embedding(query_embedding, result, ttl): ...
```

### 2.2.1 语义缓存工作流程

```
新请求 → 计算 embedding
       → Qdrant.search(embedding, limit=1, score_threshold=0.95)
           ↓命中
           从 payload 获取 {cache_key, response}
           ├─ Redis.GET(cache_key) 命中 → 直接返回缓存响应（热路径，低延迟）
           └─ Redis.GET(cache_key) 未命中 → 从 payload 取 response
                → 回填 Redis(SET cache_key response EX ttl)
                → 返回缓存响应
           ↓未命中
           调用 LLM → 生成响应
                → 写入 Qdrant(embedding, payload={cache_key, response})
                → 写入 Redis(SET cache_key response EX ttl)
```

**Qdrant payload 存储方案：** `{cache_key, response}`（而非仅存 `cache_key`）

| 字段 | 说明 |
|------|------|
| `cache_key` | Redis key，用于热路径加速查询 |
| `response` | 完整缓存响应，用于 Redis 过期后的降级回填 |

### 2.2.2 TTL 一致性设计

**问题：** Redis 有 TTL 自动过期，Qdrant 向量点无过期机制，导致"幽灵向量"（指向已过期 Redis key 的向量点）。

**解决方案：** Qdrant payload 同时存储 `cache_key + response`，作为降级数据源。

| 场景 | 处理方式 |
|------|----------|
| Redis 命中 + Qdrant 命中 | 直接返回 Redis 内容（热路径，低延迟） |
| Redis 未命中 + Qdrant 命中 | 从 payload 取 response 回填 Redis，返回缓存响应 |
| Redis 未命中 + Qdrant 未命中 | 调用 LLM，写入 Qdrant + Redis |

**写入顺序：** 先写 Qdrant → 再写 Redis

| 顺序 | 失败场景 | 影响 |
|------|----------|------|
| 先 Qdrant 后 Redis | Redis 写入失败 | Qdrant 有完整 payload，下次仍可命中并回填 |
| 先 Redis 后 Qdrant | Qdrant 写入失败 | Redis 有数据但无法被语义检索（孤儿 key） |

### 2.3 四层模型说明

| Layer | 名称 | 职责 | 技术依赖 |
|-------|------|------|----------|
| Layer 1 | Domain Layer | 定义纯抽象接口，零外部依赖 | 无 |
| Layer 2 | Application Layer | 定义业务语义接口，继承Layer 1 | 无 |
| Layer 3 | Infrastructure - 技术实现 | 实现底层存储能力，管理连接池 | Redis |
| Layer 4 | Infrastructure - 业务实现 | 实现业务接口，组合Layer 3组件 | Redis + Qdrant |

### 2.4 SessionStorage评估

**问题：** SessionStorage是否应该继承L1CachePort？

| 分析维度 | 结论 |
|----------|------|
| 接口差异 | `SessionStorage`: save/load/delete/exists<br>`L1CachePort`: get/set/delete |
| 数据结构 | SessionStorage存储复杂对象(state dict)<br>L1CachePort存储字符串 |
| 用途 | SessionStorage: 会话状态管理<br>L1CachePort: 通用缓存 |

**决策：** SessionStorage **不**继承L1CachePort，原因：
1. 接口语义不同（会话管理 vs 键值缓存）
2. SessionStorage实现有自己的设计（Hash结构存储）
3. 保持职责分离，符合单一职责原则

---

## 三、详细设计

### 3.1 Layer 1: 重构L1CachePort

**文件：** `src/domain/ports/l1_cache.py`

```python
class L1CachePort(Protocol):
    """L1 通用缓存接口 — 领域层零依赖，技术无关"""

    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int | None = None) -> bool: ...
    async def delete(self, key: str) -> bool: ...
```

**设计原则：**
- 领域层零外部依赖（仅用 `typing.Protocol`）
- 异步优先（`async def`）
- 技术无关（可使用 Redis/Memcached/内存等实现）
- `ttl=None` 时由实现方决定默认值（如 24h-30h 随机避免雪崩）

### 3.2 Layer 2: 重构SemanticCachePort

**文件：** `src/application/ports/semantic_cache.py`

```python
class SemanticCachePort(L1CachePort, Protocol):
    """语义缓存接口 — 继承L1CachePort，扩展语义检索能力"""

    async def get_by_embedding(
        self, query_embedding: list[float], threshold: float = 0.95,
    ) -> dict | None: ...
    async def set_with_embedding(
        self, query_embedding: list[float], result: dict, ttl: int = 3600,
    ) -> None: ...
    async def invalidate(self, cache_key: str) -> None: ...
```

**设计说明：**
- 继承 `L1CachePort` 获得基础缓存能力（`get/set/delete`）
- `threshold=0.95`：语义相似度阈值，越高越精确
- `ttl=3600`：默认1小时过期
- 具体实现通过组合 `L1CachePort` 实例获得基础缓存能力

### 3.3 Layer 3: RedisPoolProvider

**文件：** `src/infrastructure/storage/redis/pool_provider.py`

**职责：** Redis 连接池单例，在 `composition_root` 初始化时创建，所有 Adapter 复用。

```python
class RedisPoolProvider:                          # 单例模式
    _pool: ConnectionPool | None                  # 全局唯一连接池

    @classmethod
    def init(cls, config: RedisConfig): ...       # 初始化连接池（仅一次）
    @classmethod
    def get_client(cls) -> redis.asyncio.Redis: ...    # 获取客户端（未初始化则抛RuntimeError）
    @classmethod
    async def close_async(cls): ...               # 异步关闭连接池
    @classmethod
    def reset(cls): ...                           # 重置状态（用于测试）
```

**关键约束：**
- `DEFAULT_MAX_CONNECTIONS = 100`（Redis 官方推荐：CPU cores × 2）
- `get_client()` 未初始化时抛 `RuntimeError`
- `reset()` 仅用于测试环境，清理单例状态

### 3.4 Layer 3: RedisL1CacheAdapter

**文件：** `src/infrastructure/storage/redis/l1_cache_adapter.py`

**职责：** 实现 `L1CachePort` 通用缓存接口，提供 Redis 基础 `get/set/delete` 能力。Layer 4 具体实现可组合委托此适配器。

```python
class RedisL1CacheAdapter(L1CachePort):
    def __init__(self, redis_client=None):
        self._redis = redis_client or RedisPoolProvider.get_client()

    async def get(key) -> str | None:     # Redis.GET → 解码bytes
    async def set(key, value, ttl):       # Redis.SETEX → ttl=None时随机24-30h
    async def delete(key) -> bool:        # Redis.DELETE → 返回是否实际删除
```

**关键设计：**
- 可测试：构造函数支持注入 mock `redis_client`
- 可组合：Layer 4 实现委托此适配器处理基础缓存操作
- TTL 随机化：`DEFAULT_TTL = random(86400, 108000)` 避免缓存雪崩

### 3.5 Layer 4: RedisSemanticCacheAdapter

**文件：** `src/infrastructure/storage/redis/semantic_cache_adapter.py`

**设计核心：** Qdrant + Redis 双组件（§2.2.1 工作流程，§2.2.2 TTL 一致性设计）

```python
class RedisSemanticCacheAdapter(SemanticCachePort):
    """Qdrant(语义检索) + Redis(内容缓存+TTL) 双组件"""

    def __init__(self, qdrant_client, redis_client=None, metrics_collector=None):
        self._qdrant = qdrant_client          # Qdrant: 向量存储与语义检索
        self._base = RedisL1CacheAdapter(...)  # Redis: 基础缓存能力

    # --- L1CachePort 继承方法（委托给 _base）---
    async def get(key) -> str | None:          return await self._base.get(key)
    async def set(key, value, ttl) -> bool:    return await self._base.set(key, value, ttl)
    async def delete(key) -> bool:             return await self._base.delete(key)

    # --- SemanticCachePort 语义方法 ---
    async def get_by_embedding(query_embedding, threshold=0.95) -> dict | None:
        # 1. Qdrant.search(embedding, limit=1, score_threshold) → 命中
        # 2. Redis.GET(cache_key) 命中 → 直接返回（热路径）
        # 3. Redis 未命中 → 从 payload 取 response 回填 Redis → 返回
        # 4. Qdrant 未命中 → 返回 None

    async def set_with_embedding(query_embedding, result, ttl=3600) -> None:
        # 写入顺序：先 Qdrant → 再 Redis（§2.2.2 写入顺序）
        # 1. Qdrant.upsert(embedding, payload={cache_key, response, ttl})
        # 2. Redis.SET(cache_key, response, EX=ttl)

    async def invalidate(cache_key) -> None:
        # 删除 Qdrant 点 + Redis key
```

**组件职责划分：**

| 组件 | 职责 | 存储内容 |
|------|------|----------|
| Qdrant | 向量存储与语义检索（ANN索引） | `{cache_key, response, ttl}` |
| Redis | 热路径加速缓存（带 TTL 管理） | `cache_key → response` |
| RedisL1CacheAdapter | 基础缓存操作 | 通用 key/value |

---

## 四、详细执行步骤

> **执行跟踪说明：** 每个任务前使用 `[ ]` 表示待完成，`[x]` 表示已完成。

### Phase 1: 创建RedisPoolProvider

**目标：** 创建连接池单例（Layer 3 基础设施）

- [ ] 1.1 创建 `src/infrastructure/storage/redis/pool_provider.py`
- [ ] 1.2 实现单例模式 + `init()`/`get_client()`/`close_async()`/`close()`/`reset()`
- [ ] 1.3 验证单例正常：`p1 = RedisPoolProvider(); p2 = RedisPoolProvider(); assert p1 is p2`
- [ ] 1.4 验证异步关闭：`asyncio.run(RedisPoolProvider.close_async())`
- [ ] 1.5 验证reset：`RedisPoolProvider.reset()`

**验证命令：**
```bash
poetry run python -c "
from src.infrastructure.storage.redis.pool_provider import RedisPoolProvider
from src.infrastructure.config.redis import RedisConfig
RedisPoolProvider.init(RedisConfig())
client = RedisPoolProvider.get_client()
print(f'Pool: {client.connection_pool}')
import asyncio
asyncio.run(RedisPoolProvider.close_async())
print('Phase 1: SUCCESS')
"
```

---

### Phase 2: 重构L1CachePort（Layer 1）

**目标：** 将L1CachePort从专用接口改为通用缓存接口

- [ ] 2.1 重构 `L1CachePort` 接口为通用 `get(key)`/`set(key, value, ttl)`/`delete(key)`
- [ ] 2.2 更新 `RedisMemoryCache` 实现适配新接口（可选）
- [ ] 2.3 验证接口：`poetry run python -c "from src.domain.ports.l1_cache import L1CachePort; print('OK')"`

**注意：** 原 `L1CachePort` 接口针对记忆缓存（memory_type/owner_id/name），重构后为通用接口（key/value）。

---

### Phase 3: 创建RedisL1CacheAdapter

**目标：** 创建通用Redis缓存适配器（Layer 3 实现）

- [ ] 3.1 创建 `src/infrastructure/storage/redis/l1_cache_adapter.py`
- [ ] 3.2 实现 `L1CachePort` 接口：`get`/`set`/`delete`
- [ ] 3.3 支持外部注入redis client（构造函数参数）
- [ ] 3.4 委托 `RedisPoolProvider.get_client()` 获取连接

---

### Phase 4: 重构SemanticCachePort（Layer 2）

**目标：** SemanticCachePort继承L1CachePort

- [ ] 4.1 重构 `SemanticCachePort` 继承 `L1CachePort`
- [ ] 4.2 保留 `get_by_embedding`/`set_with_embedding`/`invalidate` 方法
- [ ] 4.3 验证继承关系：`issubclass(SemanticCachePort, L1CachePort)`

---

### Phase 5: 创建RedisSemanticCacheAdapter

**目标：** 创建语义缓存适配器实现（Layer 4 实现）

- [ ] 5.1 创建 `src/infrastructure/storage/redis/semantic_cache_adapter.py`
- [ ] 5.2 实现 `SemanticCachePort` 接口（继承L1CachePort + 语义方法）
- [ ] 5.3 组合 `RedisL1CacheAdapter`：委托基础缓存操作
- [ ] 5.4 集成 Qdrant 客户端进行 ANN 向量检索（替代旧版全表扫描）

---

### Phase 6: 更新RedisMemoryCache（Layer 4 可选）

**目标：** RedisMemoryCache可委托RedisL1CacheAdapter

- [ ] 6.1 （可选）修改 `RedisMemoryCache` 组合 `RedisL1CacheAdapter`
- [ ] 6.2 （可选）移除独立连接池管理：删除 `_get_pool()`
- [ ] 6.3 保留现有接口兼容：`get`/`set`/`delete`/`invalidate_pattern`

**注意：** `RedisMemoryCache` 已接受外部client，可直接传入 `RedisPoolProvider.get_client()`，无需强制改造。

---

### Phase 7: 更新Messaging层Adapter

**目标：** 改造EventPublisher/Subscriber使用共享连接池

- [ ] 7.1 更新 `RedisEventPublisher`：接受外部redis_client，委托 `RedisPoolProvider`
- [ ] 7.2 更新 `RedisEventSubscriber`：接受外部redis_client，委托 `RedisPoolProvider`
- [ ] 7.3 移除自建ConnectionPool逻辑
- [ ] 7.4 验证Pub/Sub功能正常

---

### Phase 8: 更新SessionStorage和PublicBlackboard

**目标：** 改造两个Adapter使用共享连接池

- [ ] 8.1 更新 `RedisSessionStorage`：接受外部redis_client
- [ ] 8.2 更新 `RedisPublicBlackboard`：接受外部redis_client
- [ ] 8.3 移除自建ConnectionPool逻辑
- [ ] 8.4 验证存储功能正常

---

### Phase 9: 更新composition_root

**目标：** 注册新端口和Provider初始化

- [ ] 9.1 添加 `RedisPoolProvider.init()` 到 `bootstrap()`
- [ ] 9.2 添加 `shutdown()` 函数调用 `RedisPoolProvider.close_async()`
- [ ] 9.3 更新 `semantic_cache` 端口实现为 `RedisSemanticCacheAdapter`
- [ ] 9.4 更新 `l1_cache` 端口实现为 `RedisL1CacheAdapter`（可选）

**新增注册：**
```python
# composition_root.py
from src.infrastructure.storage.redis.pool_provider import RedisPoolProvider

def bootstrap() -> None:
    # 初始化Redis连接池
    from src.infrastructure.config.redis import RedisConfig
    RedisPoolProvider.init(RedisConfig.from_env())
    # ... 注册端口 ...

def shutdown() -> None:
    """应用关闭时调用，清理资源。"""
    import asyncio
    asyncio.run(RedisPoolProvider.close_async())
```

---

### Phase 10: 更新测试

**目标：** 确保测试通过

- [ ] 10.1 更新mock注入模式：适配器接受外部redis client
- [ ] 10.2 添加Provider reset测试工具：`RedisPoolProvider.reset()`
- [ ] 10.3 运行单元测试：`poetry run pytest tests/unit/infrastructure/storage/redis/ -v`
- [ ] 10.4 运行集成测试：`poetry run pytest tests/integration/ -v`
- [ ] 10.5 全量测试：`poetry run pytest tests/ -x -q`

---

## 五、接口变更汇总

### 5.1 L1CachePort变更

| 操作 | 方法 | 变更 |
|------|------|------|
| 修改 | `get(memory_type, owner_id, name)` | → `get(key: str)` |
| 修改 | `set(memory_type, owner_id, name, content, ttl)` | → `set(key: str, value: str, ttl)` |
| 修改 | `delete(memory_type, owner_id, name)` | → `delete(key: str)` |
| 删除 | `invalidate_pattern(memory_type, owner_id)` | 移动到具体实现 |

### 5.2 SemanticCachePort变更

| 操作 | 方法 | 变更 |
|------|------|------|
| 继承 | - | 新增继承 `L1CachePort` |
| 保留 | `get(query_embedding, threshold)` | → `get_by_embedding(query_embedding, threshold)` |
| 保留 | `set(query_embedding, result, ttl)` | → `set_with_embedding(query_embedding, result, ttl)` |
| 保留 | `invalidate(cache_key)` | 保留 |

---

## 六、向后兼容性

### 6.1 旧接口迁移

| 旧接口 | 新接口 | 迁移策略 |
|--------|--------|----------|
| `L1CachePort.get(memory_type, owner_id, name)` | `L1CachePort.get(key)` | 调用方需要组合key |
| `RedisMemoryCache(config)` | `RedisMemoryCache(redis_client)` | 注入client或使用Provider |

### 6.2 影响范围

| 组件 | 影响 | 迁移工作 |
|------|------|----------|
| `RedisMemoryCache` 调用方 | 低 | key组合逻辑移到调用方 |
| `SemanticCache` 调用方 | 中 | 方法名变更 get→get_by_embedding |
| composition_root | 中 | 新增Provider初始化 |
| 测试代码 | 中 | mock模式调整 |

---

## 七、风险控制

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 接口变更破坏现有调用 | 高 | 渐进式变更，先保证向后兼容 |
| 连接池未初始化 | 高 | Provider抛出RuntimeError |
| 测试mock失效 | 中 | 所有Adapter支持外部注入 |
| 并发连接数超限 | 低 | max_connections=100满足需求 |
| Qdrant/Redis TTL不一致导致伪命中 | 高 | Qdrant payload 存 {cache_key, response}，Redis过期后从payload回填（§2.2.2） |
| Qdrant写入失败导致孤儿Redis key | 中 | 写入顺序：先写Qdrant再写Redis（§2.2.2） |

---

## 八、验证清单

| Phase | 验证项 | 命令 |
|-------|--------|------|
| 1 | Provider单例正常 | `python -c "from src.infrastructure.storage.redis.pool_provider import RedisPoolProvider; p1 = RedisPoolProvider(); p2 = RedisPoolProvider(); assert p1 is p2"` |
| 1 | Provider可初始化 | `RedisPoolProvider.init()` → `get_client()` |
| 2 | L1CachePort通用接口 | `poetry run python -c "from src.domain.ports.l1_cache import L1CachePort; print('OK')"` |
| 3 | RedisL1CacheAdapter实现 | `hasattr(RedisL1CacheAdapter, 'get') and hasattr(RedisL1CacheAdapter, 'set')` |
| 4 | SemanticCachePort继承 | `issubclass(SemanticCachePort, L1CachePort)` |
| 5 | RedisSemanticCacheAdapter实现 | `isinstance(adapter, SemanticCachePort)` |
| 6 | RedisMemoryCache委托（可选） | `hasattr(RedisMemoryCache, '_base')` |
| 7 | Messaging层改造 | RedisEventPublisher/Subscriber接受redis_client |
| 8 | SessionStorage/PublicBlackboard改造 | 接受redis_client |
| 9 | bootstrap/shutdown | `from src.composition_root import bootstrap; bootstrap()` |
| 10 | 全量测试 | `poetry run pytest tests/ -x -q` |

---

## 九、预期收益

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| ConnectionPool数量 | 6个独立 | 1个共享 |
| 最大连接数 | 6 × 10 = 60 | 100 |
| 代码重复 | 6处连接池管理 | 0处 |
| 接口层次 | 扁平，无继承 | 四层分层继承 |
| 可测试性 | 中 | 高（支持外部注入） |
| 可扩展性 | 低 | 高（可替换缓存技术） |

---

## 十、文件清单

### 新增文件

| 文件路径 | 职责 | Layer |
|----------|------|-------|
| `src/infrastructure/storage/redis/pool_provider.py` | Redis连接池单例 | Layer 3 |
| `src/infrastructure/storage/redis/l1_cache_adapter.py` | RedisL1CacheAdapter实现 | Layer 3 |
| `src/infrastructure/storage/redis/semantic_cache_adapter.py` | RedisSemanticCacheAdapter实现 | Layer 4 |

### 修改文件

| 文件路径 | 变更 | Layer |
|----------|------|-------|
| `src/domain/ports/l1_cache.py` | 重构为通用接口 | Layer 1 |
| `src/application/ports/semantic_cache.py` | 继承L1CachePort | Layer 2 |
| `src/infrastructure/storage/redis/redis_memory_cache.py` | 委托RedisL1CacheAdapter（可选） | Layer 4 |
| `src/infrastructure/storage/redis/semantic_cache.py` | 重命名为legacy，保留兼容 | - |
| `src/infrastructure/storage/redis/session_storage.py` | 接受外部redis_client | Layer 4 |
| `src/infrastructure/storage/redis/public_blackboard.py` | 接受外部redis_client | Layer 4 |
| `src/infrastructure/messaging/redis_publisher.py` | 接受外部redis_client | Layer 4 |
| `src/infrastructure/messaging/redis_subscriber.py` | 接受外部redis_client | Layer 4 |
| `src/composition_root.py` | 添加Provider初始化和shutdown hook | Bootstrap |

### 删除文件（重构完成后）

| 文件路径 | 原因 |
|----------|------|
| `src/infrastructure/storage/redis/semantic_cache.py` | 被semantic_cache_adapter.py替代 |

---

## 执行进度总览

```
[ ] Phase 1: RedisPoolProvider ⚠️ P0 文件不存在
[ ] Phase 2: L1CachePort重构 ⚠️ P0 仍是memory_type/owner_id/name专用接口
[ ] Phase 3: RedisL1CacheAdapter ⚠️ P0 文件不存在
[ ] Phase 4: SemanticCachePort重构 ⚠️ P0 未继承L1CachePort，方法名未改
[ ] Phase 5: RedisSemanticCacheAdapter ⚠️ P0 文件不存在
[ ] Phase 6: RedisMemoryCache（可选）
[ ] Phase 7: Messaging层Adapter
[ ] Phase 8: SessionStorage/PublicBlackboard
[ ] Phase 9: composition_root
[ ] Phase 10: 测试更新
```

---

## 十一、P0问题汇总与修复方案

### P0问题清单

| # | 问题 | 严重性 | 文件位置 |
|---|------|--------|----------|
| 1 | SemanticCache未继承L1CachePort，方法名不规范(get→get_by_embedding) | P0 | src/application/ports/semantic_cache.py |
| 2 | L1CachePort仍是专用接口(memory_type/owner_id/name)，未重构为通用接口 | P0 | src/domain/ports/l1_cache.py |
| 3 | Phase 1/3/5文件不存在(pool_provider.py, l1_cache_adapter.py, semantic_cache_adapter.py) | P0 | src/infrastructure/storage/redis/ |
| 4 | 6个Adapter独立ConnectionPool，max_connections硬编码 | P0 | infrastructure/storage/redis/*.py |
| 5 | RedisConfig默认值不一致(class=10 vs from_env()=100) | P0 | src/infrastructure/config/redis.py |
| 6 | RedisSemanticCache不使用Qdrant，使用低效全表扫描O(n) | P0 | src/infrastructure/storage/redis/semantic_cache.py |

### P1问题清单

| # | 问题 | 严重性 | 文件位置 |
|---|------|--------|----------|
| 7 | IdempotencyChecker硬编码连接参数，绕过RedisConfig | P1 | src/infrastructure/messaging/retry/checker.py |
| 8 | 构造函数签名不统一(RedisMemoryCache vs RedisSemanticCache) | P1 | - |
| 9 | SessionStorage不应继承L1CachePort（语义不同）— 已明确为独立接口 | P1 | 文档已修正 |

### 修复方案

| # | 问题 | 修复方案 | 优先级 |
|---|------|----------|--------|
| 1 | SemanticCache未继承L1CachePort | 将SemanticCache重命名SemanticCachePort，继承L1CachePort，方法名改为get_by_embedding/set_with_embedding/invalidate | P0 |
| 2 | L1CachePort专用接口 | 重构为通用接口get(key)/set(key,value,ttl)/delete(key)，调用方组合key | P0 |
| 3 | Phase文件不存在 | 创建pool_provider.py(单例连接池)、l1_cache_adapter.py、semantic_cache_adapter.py | P0 |
| 4 | 独立ConnectionPool | 各Adapter接受外部redis_client注入，委托RedisPoolProvider获取连接 | P0 |
| 5 | RedisConfig默认值不一致 | 统一为max_connections=100，修复from_env()逻辑 | P0 |
| 6 | 全表扫描低效 | 接入Qdrant向量数据库做语义检索，Redis仅负责缓存内容 | P0 |
| 7 | IdempotencyChecker硬编码 | 重构为接受RedisConfig，复用连接池管理 | P1 |
| 8 | 构造函数签名不统一 | 统一为接受外部redis_client注入模式 | P1 |

---

*文档版本: v4.0*
*重构目标: 建立四层缓存架构，统一连接池管理，使用checkbox跟踪执行进度*
