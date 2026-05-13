# SISYS L1缓存层重构设计方案

**版本:** v3.3
**日期:** 2026-05-13
**状态:** 设计阶段
**审查状态:** 第四轮宗师级审查修订版（新增5个架构问题）

---

## 修订说明 (v3.2)

| 审查问题 | 严重程度 | 修订内容 |
|----------|----------|----------|
| Phase 1-5 标记已完成但代码未实现 | P0 | 重置所有 Phase 为待执行 `[ ]` |
| L1CachePort 接口变更为通用 key 不合理 | P0 | 保持专用接口，新增 `GenericCachePort` 通用抽象 |
| SemanticCachePort 继承 L1CachePort 违反里氏替换 | P0 | 取消继承，维持独立接口 |
| RedisPoolProvider 单例线程不安全 | P1 | 添加 `threading.Lock` 保护 |
| 四层模型术语与六边形架构矛盾 | P1 | 采用标准六边形架构术语 |
| Phase 执行缺少验证机制 | P1 | 每 Phase 增加强制验证命令 |
| SessionStorage/PublicBlackboard 连接池未纳入改造 | P2 | 补充 Phase 5/6 覆盖两类 Adapter |
| 语义缓存余弦相似度 O(n) 效率问题 | P1 | 增加优化方案说明 |
| 向后兼容性风险被低估 | P1 | 增加渐进式迁移方案 |
| RedisConfig 默认值矛盾 | P0 | 新增问题：类定义=10，from_env=100，需统一 |
| RetryChecker 连接池配置缺失 | P0 | 新增问题：max_connections/socket_timeout 未设置 |
| composition_root 未初始化 Redis | P0 | 新增问题：RedisMemoryCache 需外部 client |
| IdempotencyChecker 连接池配置缺失 | P0 | 新增问题：硬编码 ConnectionPool，未使用 RedisConfig |
| PortSpec.impl 字符串路径无实例化机制 | P0 | 新增问题：l1_cache 注册为字符串但无法创建实例 |
| SemanticCache 接口位置不符合六边形架构 | P1 | 新增问题：位于 application/ports 而非 domain/ports |

## 修订说明 (v3.3)

| 审查问题 | 严重程度 | 修订内容 |
|----------|----------|----------|
| Infrastructure 层导入 Application 层端口 | P0 | 新增问题：5处违规，违反六边形架构 |
| __init__ 签名模式不一致 | P1 | 新增问题：4种模式混用（config/redis_client/复合/组件） |
| EventSubscriber 注册路径不一致 | P1 | 新增问题：RedisEventSubscriber vs DualChannelEventBus |
| EventBusFactory 存在但未使用 | P2 | 新增问题：两套创建路径并行 |
| L2-L5 存储层端口未注册 | P0 | 新增问题：12个端口缺失 registration |

---

## 一、现状分析

### 1.1 当前接口定义

| 接口 | 位置 | 方法签名 | 问题 |
|------|------|----------|------|
| `L1CachePort` | `src/domain/ports/l1_cache.py` | `get(memory_type, owner_id, name)`, `set(memory_type, owner_id, name, content, ttl)`, `delete(memory_type, owner_id, name)`, `invalidate_pattern(memory_type, owner_id)` | 专用接口，非通用缓存 |
| `SemanticCache` | `src/application/ports/semantic_cache.py` | `get(query_embedding, threshold)`, `set(query_embedding, result, ttl)`, `invalidate(cache_key)` | 独立接口，无继承关系 |
| `SessionStorage` | `src/domain/ports/session_storage.py` | `save(session_id, agent_id, state, ttl)`, `load(session_id)`, `delete(session_id)`, `exists(session_id)` | 独立接口，未统一连接池 |

### 1.2 当前实现（8个Adapter现状）

**当前状态：8个Adapter × 独立ConnectionPool**

```
┌─────────────────────────────────────────────────────┐
│  RedisMemoryCache        → ConnectionPool #1        │
│  RedisSessionStorage     → ConnectionPool #2        │
│  RedisSemanticCache      → ConnectionPool #3        │
│  RedisPublicBlackboard   → ConnectionPool #4        │
│  RedisEventPublisher     → ConnectionPool #5        │
│  RedisEventSubscriber    → ConnectionPool #6        │
│  RedisSnapshotStore      → ConnectionPool #7        │
│  RedisEventBus           → ConnectionPool #8        │
└─────────────────────────────────────────────────────┘
                    ↓
         连接数 = 8 × max_connections
         可能耗尽Redis服务器连接限制
```

**详细实现清单：**

| 实现类 | 位置 | ConnectionPool | 实现接口 | 状态 |
|--------|------|---------------|----------|------|
| `RedisMemoryCache` | `infrastructure/storage/redis/` | 接受外部client | `L1CachePort` | ✅ 已支持外部注入 |
| `RedisSessionStorage` | `infrastructure/storage/redis/` | 自建 ❌ | `SessionStorage` | ❌ 需改造 |
| `RedisSemanticCache` | `infrastructure/storage/redis/` | 自建 ❌ | `SemanticCache` | ❌ 需改造 |
| `RedisPublicBlackboard` | `infrastructure/storage/redis/` | 自建 ❌ | `PublicBlackboard` | ❌ 需改造 |
| `RedisEventPublisher` | `infrastructure/messaging/` | 自建 ❌ | 事件发布 | ❌ 需改造 |
| `RedisEventSubscriber` | `infrastructure/messaging/` | 自建 ❌ | 事件订阅 | ❌ 需改造 |
| `RedisSnapshotStore` | `infrastructure/storage/` | 接受外部client | `SnapshotRepositoryProtocol` | ✅ 已支持外部注入 |
| `RedisEventBus` | `infrastructure/messaging/` | 委托上述两者 ⚠️ | `EventPublisher`+`EventSubscriber` | ⚠️ 混合模式 |

### 1.3 问题根因

```
当前架构问题：

Domain Layer
├── L1CachePort (专用接口: memory_type/owner_id/name)
├── GenericCachePort (缺失: 通用缓存抽象)
├── SemanticCache (独立接口，未继承)
└── SessionStorage (独立接口，未继承)

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
1. 缺少通用缓存抽象（GenericCachePort）
2. 6个Adapter各自管理ConnectionPool（除RedisMemoryCache和RedisSnapshotStore）
3. 接口无继承关系，无法统一抽象
4. 连接数 = 6 × max_connections (默认10) = 60，可能耗尽Redis连接限制
5. SemanticCache 与 L1CachePort 接口语义不同，不应继承
6. RedisConfig 默认值矛盾：类定义=10，from_env=100
7. RetryChecker 连接池配置缺失：max_connections/socket_timeout 未设置
8. composition_root 未初始化 Redis：RedisMemoryCache 需要外部 client
```

### 1.4 新发现P0问题（第二轮审查）

#### 问题 6: RedisConfig 默认值矛盾

**位置:** `src/infrastructure/config/redis.py`

```python
# 类定义默认值
max_connections: int = 10

# from_env() 默认值
max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "100")),
```

**影响:** 同一配置类两处默认值不一致，可能导致连接数估算错误。

---

#### 问题 7: RetryChecker 连接池配置缺失

**位置:** `src/infrastructure/messaging/retry/checker.py`

```python
self._pool = aioredis.ConnectionPool(
    host=self._config.host,
    port=self._config.port,
    db=self._config.db,
    password=self._config.password,
    # 缺少 max_connections 和 socket_timeout
)
```

**影响:** 使用库默认值（可能不符合项目要求），且与其他 Adapter 不一致。

---

#### 问题 8: composition_root 未初始化 Redis 连接

**位置:** `src/composition_root.py:93-100`

```python
register_port(
    name="l1_cache",
    interface=L1CachePort,
    impl="...RedisMemoryCache",
    ...
)
```

**问题:** `RedisMemoryCache` 需要外部传入 `aioredis.Redis` 实例，但 composition_root 只注册端口，未实际初始化。

**影响:** 运行时可能抛出异常，无法正常创建 RedisMemoryCache 实例。

---

#### 问题 9: RedisSemanticCache 未显式继承接口

**位置:** `src/infrastructure/storage/redis/semantic_cache.py:61`

```python
class RedisSemanticCache:  # 未声明 implements SemanticCache
```

**对比:** `RedisMemoryCache(L1CachePort)` 显式继承

**影响:** 接口实现不明确，依赖隐式 duck typing，类型检查无法验证。

---

#### 问题 10: get_by_agent 效率问题

**位置:** `src/infrastructure/storage/redis/public_blackboard.py:174`

```python
async def get_by_agent(self, conversation_id: str, agent_id: str) -> dict | None:
    all_entries = await self.get(conversation_id)  # 获取全部条目
    agent_entries = [e for e in all_entries if e.get("agent_id") == agent_id]
```

**问题:** 先获取全部条目再过滤，未使用 Redis 命令直接过滤。

**影响:** 数据量大时性能差。

---

#### 问题 11: IdempotencyChecker 连接池配置缺失

**位置:** `src/infrastructure/messaging/retry/checker.py:44-51`

```python
pool = aioredis.ConnectionPool(
    host=host,
    port=port,
    db=db,
    password=password,
    decode_responses=True,
    # 完全缺少 max_connections, socket_timeout, retry_on_timeout
)
```

**影响:** 使用库默认值，且未使用 RedisConfig，与其他 Adapter 不一致。

---

#### 问题 12: PortSpec.impl 字符串路径无实例化机制

**位置:** `src/composition_root.py:92-101`

```python
register_port(
    name="l1_cache",
    interface=L1CachePort,
    impl="src.infrastructure.storage.redis.redis_memory_cache.RedisMemoryCache",
    ...
)
```

**问题:** `impl` 存储为字符串路径，但 `PortRegistry` 无 `create_instance()` 方法，无法实例化。

**影响:** `l1_cache` 端口注册后无法创建实例，运行时失败。

---

#### 问题 13: SemanticCache 接口位置不符合六边形架构

**位置:** `src/application/ports/semantic_cache.py`

**问题:** SemanticCache 位于 `application/ports/`，但其他 Domain 缓存接口位于 `domain/ports/`

**影响:** 违反六边形架构分层，Domain 层不应依赖 Application 层。

---

#### 问题 14: _get_pool 未使用 _pool_lock 保护

**位置:** `src/infrastructure/storage/redis/public_blackboard.py:48-60`

```python
def _get_pool(self) -> aioredis.ConnectionPool:
    if self._pool is None:  # 无锁保护
        self._pool = aioredis.ConnectionPool(...)
    return self._pool
```

**问题:** `_pool_lock` 定义但未使用，高并发时可能重复创建连接池。

**影响:** 竞态条件，资源浪费。

---

#### 问题 15: Infrastructure 层导入 Application 层端口（5处违规）

**位置:** 多个文件

```python
# src/infrastructure/monitoring/metrics_port_impl.py
from src.application.ports.metrics_port import MetricsPort  # 违规

# src/infrastructure/messaging/redis_event_bus.py
from src.application.ports.event_subscriber import EventSubscriber  # 违规

# src/infrastructure/external_services/sandbox/session_namespace_manager.py
from src.application.ports.sandbox_port import SandboxExecutor  # 违规

# src/infrastructure/external_services/sandbox/docker_sandbox_adapter.py
from src.application.ports.sandbox_port import ...  # 违规

# src/infrastructure/logging/exception_metrics_impl.py
from src.application.ports.exception_metrics_port import ExceptionMetricsPort  # 违规
```

**问题:** Infrastructure 层（最外层）依赖 Application 层，违反六边形架构。

**影响:** 架构侵蚀，模块耦合增强，难以替换基础设施实现。

---

#### 问题 16: __init__ 签名模式不一致

**位置:** 各 Redis Adapter

| 模式 | 类 | 参数 |
|------|-----|------|
| Pattern A | RedisSessionStorage, RedisSemanticCache, RedisPublicBlackboard, RedisCleanup, RedisEventPublisher, RedisEventSubscriber | `config: RedisConfig` |
| Pattern B | RedisMemoryCache, RedisRetryQueue | `redis_client: aioredis.Redis` |
| Pattern C | DualIdempotencyChecker | `redis_client + session` |
| Pattern D | RedisEventBus | `publisher + subscriber + router` |

**问题:** 4种模式混用，无法统一抽象。

**影响:** 调用方需要知道每种类的构造方式，增加耦合。

---

#### 问题 17: EventSubscriber 注册路径不一致

**位置:** `src/composition_root.py`

```python
# 两条独立路径
register_port(name="event_subscriber", impl="...RedisEventSubscriber")  # 独立订阅
register_port(name="event_publisher", impl="...DualChannelEventBus")   # 门面订阅
```

**问题:** `event_subscriber` 和 `event_publisher` 独立注册，但 `DualChannelEventBus` 内部也组合了 `RedisEventSubscriber`。

**影响:** 生命周期管理不一致，可能导致重复订阅或消息丢失。

---

#### 问题 18: EventBusFactory 存在但未使用

**位置:** `src/infrastructure/messaging/event_bus_factory.py`

```python
def create_dual_channel_bus() -> (DualChannelEventBus, AsyncOutboxPoller)
    # 工厂方法存在，但 composition_root 直接注册具体类
```

**问题:** 工厂方法与直接注册两条路径并行。

**影响:** 难以通过配置替换实现，维护成本增加。

---

#### 问题 19: L2-L5 存储层端口未注册

**位置:** `src/domain/ports/` 多个接口

| 未注册端口 | 文件 |
|-----------|------|
| `L2MetadataRepositoryPort` | l2_rdb.py |
| `L2ChangeHistoryRepositoryPort` | l2_rdb.py |
| `L2GroupMemberRepositoryPort` | l2_rdb.py |
| `L3VectorPort` | l3_vector.py |
| `L4ObjectPort` | l4_object.py |
| `L5GraphPort` | l5_graph.py |
| `UnifiedStoragePort` | unified_storage.py |
| `UnitOfWork` | unit_of_work.py |
| `IndexManagerPort` | index_manager.py |
| `IntegrityPort` | integrity.py |
| `ObjectStorageRepository` | storage.py |

**问题:** 12个 Domain 端口在 composition_root 中未注册。

**影响:** 无法通过端口注册机制统一管理，依赖散乱。

---

## 二、目标架构

### 2.1 六边形架构分层模型

```
┌─────────────────────────────────────────────────────────────────┐
│  Domain Layer - 领域层（零外部依赖）                              │
│                                                                  │
│  职责：定义纯抽象接口，领域层零外部依赖                            │
│  组件：                                                          │
│    - L1CachePort（专用记忆缓存接口）                              │
│    - GenericCachePort（通用缓存接口）- 新增                        │
│    - SessionStoragePort（会话存储接口）                           │
│    - PublicBlackboardPort（公共黑板接口）                         │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Application Layer - 应用层（用例编排）                           │
│                                                                  │
│  职责：定义业务语义接口                                           │
│  组件：                                                          │
│    - SemanticCachePort（语义缓存接口）- 独立，不继承             │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Infrastructure Layer - 基础设施层（技术实现）                     │
│                                                                  │
│  职责：实现所有端口接口 + 连接池统一管理                          │
│  组件：                                                          │
│    - RedisPoolProvider（连接池单例）                              │
│    - RedisL1CacheAdapter（实现 L1CachePort）                     │
│    - RedisGenericCacheAdapter（实现 GenericCachePort）- 新增      │
│    - RedisSemanticCacheAdapter（实现 SemanticCachePort）         │
│    - RedisSessionStorageAdapter（实现 SessionStoragePort）       │
│    - RedisPublicBlackboardAdapter（实现 PublicBlackboardPort）   │
│    - RedisEventPublisherAdapter（实现 EventPublisher）           │
│    - RedisEventSubscriberAdapter（实现 EventSubscriber）         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 接口继承关系

```python
# Domain Layer: 专用接口（保持原有设计，不破坏现有实现）
class L1CachePort(Protocol):
    """L1 记忆缓存接口 - 专用接口"""

    async def get(self, memory_type: str, owner_id: str, name: str) -> str | None: ...
    async def set(self, memory_type: str, owner_id: str, name: str, content: str, ttl: int | None = None) -> bool: ...
    async def delete(self, memory_type: str, owner_id: str, name: str) -> bool: ...
    async def invalidate_pattern(self, memory_type: str, owner_id: str) -> int: ...

# Domain Layer: 新增通用接口
class GenericCachePort(Protocol):
    """通用缓存接口 - 新增抽象"""

    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int | None = None) -> bool: ...
    async def delete(self, key: str) -> bool: ...

# Application Layer: 语义缓存（独立接口，不继承 L1CachePort）
class SemanticCachePort(Protocol):
    """语义缓存接口 - 独立接口，不继承任何缓存接口"""

    async def get_by_embedding(self, query_embedding: list[float], threshold: float) -> dict | None: ...
    async def set_with_embedding(self, query_embedding: list[float], result: dict, ttl: int) -> None: ...
    async def invalidate(self, cache_key: str) -> None: ...
```

### 2.3 六层模型说明

| 层级 | 名称 | 职责 | 技术依赖 |
|-------|------|------|----------|
| Domain | 领域层 | 定义纯抽象接口，零外部依赖 | 无 |
| Application | 应用层 | 定义业务语义接口 | 无 |
| Infrastructure | 基础设施层 | 实现所有端口接口 + 连接池统一管理 | Redis |

---

## 三、详细设计

### 3.1 新增: GenericCachePort（通用缓存抽象）

**文件：** `src/domain/ports/generic_cache.py`

```python
"""GenericCachePort — 通用缓存抽象端口。

提供键值缓存的基础抽象，供需要通用缓存能力的组件使用。
与 L1CachePort（专用记忆缓存）不同，GenericCachePort 是通用键值接口。

设计原则：
- 领域层零外部依赖（仅用 Protocol + typing）
- 异步优先（async def）
- 技术无关（可使用 Redis/Memcached/内存等实现）
"""

from __future__ import annotations

from typing import Protocol


class GenericCachePort(Protocol):
    """通用缓存接口。

    提供基础的 get/set/delete 操作。
    具体实现（如 RedisGenericCacheAdapter）委托 RedisPoolProvider
    获取连接池。
    """

    async def get(self, key: str) -> str | None:
        """获取缓存。

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在返回None
        """

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        """设置缓存。

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None使用默认TTL

        Returns:
            是否成功
        """

    async def delete(self, key: str) -> bool:
        """删除缓存。

        Args:
            key: 缓存键

        Returns:
            是否成功
        """
```

### 3.2 L1CachePort 保持不变（不破坏现有实现）

**结论：** L1CachePort 保持现有专用接口不变，不进行接口通用化改造。

**理由：**
1. 现有 `RedisMemoryCache` 实现了 L1CachePort（memory_type/owner_id/name），改动会破坏大量调用方
2. 专用接口携带业务语义，通用化后调用方需要自己组合 key
3. 新增 `GenericCachePort` 满足通用缓存需求，不影响现有实现

### 3.3 SemanticCachePort 保持独立（不继承 L1CachePort）

**结论：** SemanticCachePort 维持独立接口，不继承任何缓存接口。

**理由：**
1. 接口语义完全不同：L1CachePort 是键值缓存，SemanticCachePort 是向量相似度搜索
2. 违反里氏替换原则：语义缓存的 `get_by_embedding` 无法替代 L1CachePort 的 `get`
3. 组合优于继承：RedisSemanticCacheAdapter 可组合 RedisL1CacheAdapter 处理基础缓存

### 3.4 RedisPoolProvider（线程安全单例）

**文件：** `src/infrastructure/storage/redis/pool_provider.py`

```python
"""Redis连接池统一提供者（线程安全单例模式）。

在composition_root初始化时创建单一连接池，
所有Adapter复用此连接池，实现资源统一管理。

遵循六边形架构：
- 资源管理封装在Infrastructure层
- Domain层完全不感知连接池存在

设计考虑：
- 线程安全单例模式确保全局唯一连接池
- 使用 threading.Lock 保护初始化过程
- 支持异步和同步两种关闭方式
- 测试时可替换为mock
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING, Final

import redis.asyncio as aioredis

from src.infrastructure.config.redis import RedisConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Redis官方推荐：max_connections = CPU_cores * 2，通常50-100
DEFAULT_MAX_CONNECTIONS: Final[int] = 100


class RedisPoolProvider:
    """Redis连接池统一提供者（线程安全单例模式）。

    Attributes:
        _instance: 单例实例
        _pool: 连接池
        _config: Redis配置
        _lock: 线程锁，保护初始化过程
    """

    _instance: RedisPoolProvider | None = None
    _pool: aioredis.ConnectionPool | None = None
    _config: RedisConfig | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> RedisPoolProvider:
        """线程安全单例获取"""
        if cls._instance is None:
            with cls._lock:
                # 双重检查锁定（Double-Checked Locking）
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def init(cls, config: RedisConfig | None = None) -> None:
        """初始化连接池（线程安全）。

        Args:
            config: Redis配置，默认从环境变量加载
        """
        with cls._lock:
            if cls._pool is not None:
                logger.warning("RedisPoolProvider already initialized, skipping")
                return

            config = config or RedisConfig.from_env()
            cls._config = config

            cls._pool = aioredis.ConnectionPool(
                host=config.host,
                port=config.port,
                db=config.db,
                password=config.password,
                max_connections=config.max_connections or DEFAULT_MAX_CONNECTIONS,
                socket_timeout=config.socket_timeout,
                socket_connect_timeout=5.0,
                retry_on_timeout=config.retry_on_timeout,
                decode_responses=True,
            )
            logger.info(
                "RedisPoolProvider initialized: %s:%d (max_connections=%d)",
                config.host,
                config.port,
                config.max_connections,
            )

    @classmethod
    def get_client(cls) -> aioredis.Redis:
        """获取Redis客户端实例。

        Returns:
            Redis异步客户端

        Raises:
            RuntimeError: 如果provider未初始化
        """
        if cls._pool is None:
            raise RuntimeError(
                "RedisPoolProvider not initialized. "
                "Call RedisPoolProvider.init() before use."
            )
        return aioredis.Redis(connection_pool=cls._pool)

    @classmethod
    def is_initialized(cls) -> bool:
        """检查provider是否已初始化。"""
        return cls._pool is not None

    @classmethod
    async def close_async(cls) -> None:
        """异步关闭连接池。"""
        with cls._lock:
            if cls._pool is not None:
                await cls._pool.aclose()
                cls._pool = None
                cls._config = None
                cls._instance = None
                logger.info("RedisPoolProvider closed (async)")

    @classmethod
    def close(cls) -> None:
        """同步关闭连接池（包装异步方法）。"""
        if cls._pool is not None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(cls.close_async())
                else:
                    asyncio.run(cls.close_async())
            except Exception as e:
                logger.error("Error closing RedisPoolProvider: %s", e)

    @classmethod
    def reset(cls) -> None:
        """重置Provider状态（用于测试）。"""
        with cls._lock:
            cls._pool = None
            cls._config = None
            cls._instance = None
            logger.info("RedisPoolProvider reset")
```

### 3.5 RedisGenericCacheAdapter

**文件：** `src/infrastructure/storage/redis/generic_cache_adapter.py`

```python
"""Redis 通用缓存适配器。

实现 GenericCachePort 接口，提供通用 Redis 缓存能力。
供需要通用键值缓存的组件使用。

架构来源: architecture.md §11.2.9
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Final

import redis.asyncio as aioredis

from src.domain.ports.generic_cache import GenericCachePort
from src.infrastructure.storage.redis.pool_provider import RedisPoolProvider

if TYPE_CHECKING:
    pass

# 默认TTL范围 (秒)
DEFAULT_TTL_MIN: Final[int] = 86400  # 24h
DEFAULT_TTL_MAX: Final[int] = 108000  # 30h


class RedisGenericCacheAdapter(GenericCachePort):
    """Redis 通用缓存适配器。

    实现 GenericCachePort 接口，提供通用 Redis 缓存能力。

    设计原则：
    - 单一职责：只处理基础 get/set/delete
    - 可测试：支持注入 mock redis client
    - 可组合：具体缓存实现委托此适配器

    Attributes:
        _redis: Redis异步客户端
    """

    def __init__(self, redis_client: aioredis.Redis | None = None):
        """初始化Redis缓存适配器。

        Args:
            redis_client: 可选，测试时注入mock client
        """
        self._redis = redis_client or RedisPoolProvider.get_client()

    async def get(self, key: str) -> str | None:
        """获取缓存。

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在返回None
        """
        value = await self._redis.get(key)
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else value

    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
    ) -> bool:
        """设置缓存。

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None使用随机TTL（24-30h）

        Returns:
            是否成功
        """
        effective_ttl = ttl if ttl is not None else self._generate_ttl()
        await self._redis.setex(key, effective_ttl, value)
        return True

    async def delete(self, key: str) -> bool:
        """删除缓存。

        Args:
            key: 缓存键

        Returns:
            是否成功（key存在且删除返回True）
        """
        result = await self._redis.delete(key)
        return result > 0

    def _generate_ttl(self) -> int:
        """生成随机TTL。

        Returns:
            TTL秒数 (86400-108000)
        """
        return DEFAULT_TTL_MIN + random.randint(0, DEFAULT_TTL_MAX - DEFAULT_TTL_MIN)  # nosec B311
```

### 3.6 RedisSemanticCacheAdapter

**文件：** `src/infrastructure/storage/redis/semantic_cache_adapter.py`

```python
"""Redis 语义缓存适配器。

实现 SemanticCachePort 接口，提供基于向量相似度的缓存能力。
组合 RedisGenericCacheAdapter 处理基础缓存操作。

使用 Redis Hash 存储嵌入向量和缓存结果，
支持纯 Python 余弦相似度计算。

注意：当前实现使用 SCAN 遍历所有缓存键，复杂度 O(n)。
      大规模部署建议使用 Redis Search (RediSearch) 或向量索引。
"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import TYPE_CHECKING

import redis.asyncio as aioredis

from src.application.ports.semantic_cache import SemanticCachePort
from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.storage.redis.generic_cache_adapter import RedisGenericCacheAdapter
from src.infrastructure.utils import json_dumps, json_loads

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """计算两个向量的余弦相似度（纯Python实现，不使用numpy）。

    Args:
        vec1: 第一个向量
        vec2: 第二个向量

    Returns:
        余弦相似度值（-1.0到1.0），零向量或空向量返回0.0
    """
    if len(vec1) != len(vec2):
        raise ValueError(f"Vector dimensions must match: {len(vec1)} != {len(vec2)}")
    if not vec1:
        return 0.0

    dot_product = 0.0
    norm1 = 0.0
    norm2 = 0.0

    for v1, v2 in zip(vec1, vec2):
        dot_product += v1 * v2
        norm1 += v1 * v1
        norm2 += v2 * v2

    norm1 = math.sqrt(norm1)
    norm2 = math.sqrt(norm2)

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0

    sim = dot_product / (norm1 * norm2)
    return max(-1.0, min(1.0, sim))


class RedisSemanticCacheAdapter(SemanticCachePort):
    """Redis 语义缓存适配器。

    实现 SemanticCachePort 接口，提供基于向量相似度的缓存能力。
    组合 RedisGenericCacheAdapter 处理基础缓存操作。

    键格式: sisys:cache:semantic:{cache_key}
    支持基于余弦相似度的语义匹配。

    效率说明：当前实现使用 SCAN 遍历所有缓存键，复杂度 O(n)。
    大规模部署建议使用 Redis Search (RediSearch) 替代方案。

    Attributes:
        _base: 基础通用缓存适配器
        _metrics_collector: 可选的指标收集器
    """

    _NAMESPACE = "cache:semantic"

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        metrics_collector: EventMetricsCollector | None = None,
    ):
        """初始化Redis语义缓存适配器。

        Args:
            redis_client: 可选，测试时注入mock client
            metrics_collector: 可选的指标收集器
        """
        self._base = RedisGenericCacheAdapter(redis_client)
        self._metrics_collector = metrics_collector

    def _build_cache_key(self, query_embedding: list[float]) -> str:
        """根据查询向量生成缓存键。

        使用MD5哈希向量的量化版本作为键标识。
        """
        quantized = [round(v, 6) for v in query_embedding[:10]]
        vector_id = hashlib.md5(
            str(quantized).encode(),
            usedforsecurity=False,
        ).hexdigest()[:16]
        return f"vec:{vector_id}"

    async def get_by_embedding(
        self,
        query_embedding: list[float],
        threshold: float = 0.9,
    ) -> dict | None:
        """通过向量嵌入查询缓存。

        遍历所有缓存条目，找到相似度高于阈值的第一个结果。

        注意：当前实现复杂度 O(n)，大规模部署需要优化。

        Args:
            query_embedding: 查询向量嵌入
            threshold: 相似度阈值

        Returns:
            缓存结果，如果未命中则返回None
        """
        client = self._base._redis
        pattern = build_key(self._NAMESPACE, "vec:*")
        cursor = 0

        while True:
            cursor, keys = await client.scan(
                cursor=cursor,
                match=pattern,
                count=100,
            )

            for key in keys:
                stored_embedding = await client.hget(key, "embedding")
                stored_result_data = await client.hget(key, "result")

                if stored_embedding is None or stored_result_data is None:
                    continue

                try:
                    stored_vec: list[float] = json_loads(stored_embedding)
                    raw_result = json_loads(stored_result_data)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning("Corrupt data in cache key %s: %s", key, e)
                    continue

                if not isinstance(stored_vec, list) or not isinstance(raw_result, dict):
                    logger.warning("Unexpected data types in cache key %s", key)
                    continue

                similarity = cosine_similarity(query_embedding, stored_vec)

                if similarity >= threshold:
                    if self._metrics_collector:
                        self._metrics_collector.record_cache_hit()
                    logger.debug("Cache hit with similarity %.4f", similarity)
                    return raw_result

            if cursor == 0:
                break

        if self._metrics_collector:
            self._metrics_collector.record_cache_miss()
        logger.debug("Cache miss")
        return None

    async def set_with_embedding(
        self,
        query_embedding: list[float],
        result: dict,
        ttl: int = 86400,
    ) -> None:
        """存储带向量嵌入的缓存。

        Args:
            query_embedding: 查询向量嵌入
            result: 缓存结果数据
            ttl: 过期时间（秒）
        """
        cache_key = self._build_cache_key(query_embedding)
        key = build_key(self._NAMESPACE, cache_key)
        client = self._base._redis

        await client.hset(key, "embedding", json_dumps(query_embedding))
        await client.hset(key, "result", json_dumps(result))
        await client.expire(key, ttl)
        logger.debug("Cached result with key %s and TTL %d", cache_key, ttl)

    async def invalidate(self, cache_key: str) -> None:
        """使缓存失效。

        Args:
            cache_key: 缓存键
        """
        prefix = build_key(self._NAMESPACE, "")
        if cache_key.startswith(prefix):
            key = cache_key
        else:
            key = build_key(self._NAMESPACE, cache_key)

        await self._base.delete(key)
        logger.debug("Invalidated cache key %s", cache_key)
```

---

## 四、详细执行步骤

> **执行跟踪说明：** 每个任务前使用 `[ ]` 表示待完成，`[x]` 表示已完成。
> **验证要求：** 每个 Phase 必须通过验证才能进入下一阶段，失败则停止并回滚。

### Phase 1: 创建RedisPoolProvider

**目标：** 创建线程安全连接池单例（Infrastructure层）

- [ ] 1.1 创建 `src/infrastructure/storage/redis/pool_provider.py`
- [ ] 1.2 实现线程安全单例模式 + `init()`/`get_client()`/`close_async()`/`close()`/`reset()`
- [ ] 1.3 验证单例正常：`p1 = RedisPoolProvider(); p2 = RedisPoolProvider(); assert p1 is p2`
- [ ] 1.4 验证线程安全：`threading.Thread(target=RedisPoolProvider.init).start()` 并发调用
- [ ] 1.5 验证异步关闭：`asyncio.run(RedisPoolProvider.close_async())`
- [ ] 1.6 验证reset：`RedisPoolProvider.reset()`

**验证命令：**
```bash
poetry run python -c "
import threading
from src.infrastructure.storage.redis.pool_provider import RedisPoolProvider
from src.infrastructure.config.redis import RedisConfig

# 测试单例
p1 = RedisPoolProvider()
p2 = RedisPoolProvider()
assert p1 is p2, 'Singleton failed'
print('Singleton: OK')

# 测试线程安全初始化
def init_provider():
    RedisPoolProvider.init(RedisConfig())

threads = [threading.Thread(target=init_provider) for _ in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()

client = RedisPoolProvider.get_client()
print(f'Pool: {client.connection_pool}')
print('Thread-safe init: OK')

# 测试重置
RedisPoolProvider.reset()
assert not RedisPoolProvider.is_initialized(), 'Reset failed'
print('Reset: OK')

print('Phase 1: ALL PASSED')
"
```

---

### Phase 2: 创建GenericCachePort

**目标：** 新增通用缓存抽象接口（Domain层）

- [ ] 2.1 创建 `src/domain/ports/generic_cache.py`
- [ ] 2.2 定义 `GenericCachePort` 接口：`get(key)`/`set(key, value, ttl)`/`delete(key)`
- [ ] 2.3 验证接口定义：`from src.domain.ports.generic_cache import GenericCachePort; print('OK')`

**验证命令：**
```bash
poetry run python -c "
from src.domain.ports.generic_cache import GenericCachePort
print('GenericCachePort: OK')
"
```

---

### Phase 3: 创建RedisGenericCacheAdapter

**目标：** 创建通用Redis缓存适配器（Infrastructure层）

- [ ] 3.1 创建 `src/infrastructure/storage/redis/generic_cache_adapter.py`
- [ ] 3.2 实现 `GenericCachePort` 接口：`get`/`set`/`delete`
- [ ] 3.3 支持外部注入 redis client（构造函数参数）
- [ ] 3.4 委托 `RedisPoolProvider.get_client()` 获取连接
- [ ] 3.5 验证实现：`hasattr(RedisGenericCacheAdapter, 'get') and hasattr(RedisGenericCacheAdapter, 'set')`

**验证命令：**
```bash
poetry run python -c "
from src.infrastructure.storage.redis.generic_cache_adapter import RedisGenericCacheAdapter
from src.domain.ports.generic_cache import GenericCachePort

# 验证实现接口
adapter = RedisGenericCacheAdapter.__new__(RedisGenericCacheAdapter)
assert isinstance(adapter, GenericCachePort), 'Must implement GenericCachePort'
print('RedisGenericCacheAdapter: OK')
"
```

---

### Phase 4: 创建RedisSemanticCacheAdapter

**目标：** 创建语义缓存适配器（Infrastructure层）

- [ ] 4.1 创建 `src/infrastructure/storage/redis/semantic_cache_adapter.py`
- [ ] 4.2 实现 `SemanticCachePort` 接口
- [ ] 4.3 组合 `RedisGenericCacheAdapter`：委托基础缓存操作
- [ ] 4.4 实现纯Python余弦相似度计算（不使用numpy）
- [ ] 4.5 验证：`isinstance(adapter, SemanticCachePort)`

**验证命令：**
```bash
poetry run python -c "
from src.infrastructure.storage.redis.semantic_cache_adapter import RedisSemanticCacheAdapter, cosine_similarity
from src.application.ports.semantic_cache import SemanticCachePort

# 测试余弦相似度
v1 = [1.0, 0.0, 0.0]
v2 = [1.0, 0.0, 0.0]
assert cosine_similarity(v1, v2) == 1.0, 'Identical vectors should return 1.0'

v3 = [0.0, 1.0, 0.0]
assert abs(cosine_similarity(v1, v3)) < 0.001, 'Orthogonal vectors should return ~0'

print('cosine_similarity: OK')

# 验证实现接口
adapter = RedisSemanticCacheAdapter.__new__(RedisSemanticCacheAdapter)
assert isinstance(adapter, SemanticCachePort), 'Must implement SemanticCachePort'
print('RedisSemanticCacheAdapter: OK')
"
```

---

### Phase 5: 更新RedisSessionStorage

**目标：** 改造SessionStorage使用共享连接池

- [ ] 5.1 修改 `RedisSessionStorage.__init__` 接受外部redis_client
- [ ] 5.2 移除自建ConnectionPool逻辑：删除 `_get_pool()`/`_pool`/`_pool_lock`
- [ ] 5.3 委托 `RedisPoolProvider.get_client()` 获取连接
- [ ] 5.4 保留现有接口：`save`/`load`/`delete`/`exists`
- [ ] 5.5 移除 `close()` 方法（连接池由Provider统一管理）

**新增构造参数：**
```python
def __init__(self, redis_client: aioredis.Redis | None = None):
    self._redis = redis_client or RedisPoolProvider.get_client()
```

**验证命令：**
```bash
poetry run python -c "
from src.infrastructure.storage.redis.session_storage import RedisSessionStorage
# 验证接受redis_client参数
import inspect
sig = inspect.signature(RedisSessionStorage.__init__)
params = list(sig.parameters.keys())
assert 'redis_client' in params, 'Must accept redis_client parameter'
print('RedisSessionStorage update: OK')
"
```

---

### Phase 6: 更新RedisPublicBlackboard

**目标：** 改造PublicBlackboard使用共享连接池

- [ ] 6.1 修改 `RedisPublicBlackboard.__init__` 接受外部redis_client
- [ ] 6.2 移除自建ConnectionPool逻辑
- [ ] 6.3 委托 `RedisPoolProvider.get_client()` 获取连接
- [ ] 6.4 保留现有接口：`post`/`get`/`get_by_agent`/`get_latest`
- [ ] 6.5 移除 `close()` 方法

**新增构造参数：**
```python
def __init__(self, redis_client: aioredis.Redis | None = None):
    self._redis = redis_client or RedisPoolProvider.get_client()
```

**验证命令：**
```bash
poetry run python -c "
from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard
import inspect
sig = inspect.signature(RedisPublicBlackboard.__init__)
params = list(sig.parameters.keys())
assert 'redis_client' in params, 'Must accept redis_client parameter'
print('RedisPublicBlackboard update: OK')
"
```

---

### Phase 7: 更新RedisEventPublisher

**目标：** 改造EventPublisher使用共享连接池

- [ ] 7.1 修改 `RedisEventPublisher.__init__` 接受外部redis_client
- [ ] 7.2 移除自建ConnectionPool逻辑
- [ ] 7.3 委托 `RedisPoolProvider.get_client()` 获取连接
- [ ] 7.4 保留现有接口：`publish`/`close`
- [ ] 7.5 更新测试用例

**新增构造参数：**
```python
def __init__(self, redis_client: aioredis.Redis | None = None):
    self._redis = redis_client or RedisPoolProvider.get_client()
```

**验证命令：**
```bash
poetry run python -c "
from src.infrastructure.messaging.redis_publisher import RedisEventPublisher
import inspect
sig = inspect.signature(RedisEventPublisher.__init__)
params = list(sig.parameters.keys())
assert 'redis_client' in params, 'Must accept redis_client parameter'
print('RedisEventPublisher update: OK')
"
```

---

### Phase 8: 更新RedisEventSubscriber

**目标：** 改造EventSubscriber使用共享连接池

- [ ] 8.1 修改 `RedisEventSubscriber.__init__` 接受外部redis_client
- [ ] 8.2 移除自建ConnectionPool逻辑
- [ ] 8.3 委托 `RedisPoolProvider.get_client()` 获取连接
- [ ] 8.4 保留现有接口：`subscribe`/`start`/`close`
- [ ] 8.5 更新测试用例

**新增构造参数：**
```python
def __init__(self, redis_client: aioredis.Redis | None = None):
    self._redis = redis_client or RedisPoolProvider.get_client()
```

**验证命令：**
```bash
poetry run python -c "
from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber
import inspect
sig = inspect.signature(RedisEventSubscriber.__init__)
params = list(sig.parameters.keys())
assert 'redis_client' in params, 'Must accept redis_client parameter'
print('RedisEventSubscriber update: OK')
"
```

---

### Phase 9: 更新RedisSemanticCache（旧实现）

**目标：** 改造旧RedisSemanticCache使用共享连接池（向后兼容）

- [ ] 9.1 修改 `RedisSemanticCache.__init__` 接受外部redis_client
- [ ] 9.2 移除自建ConnectionPool逻辑
- [ ] 9.3 委托 `RedisPoolProvider.get_client()` 获取连接
- [ ] 9.4 保留现有接口：`get`/`set`/`invalidate`/`close`
- [ ] 9.5 最终删除此文件（当 RedisSemanticCacheAdapter 完全替代后）

**新增构造参数：**
```python
def __init__(self, redis_client: aioredis.Redis | None = None):
    self._redis = redis_client or RedisPoolProvider.get_client()
```

**验证命令：**
```bash
poetry run python -c "
from src.infrastructure.storage.redis.semantic_cache import RedisSemanticCache
import inspect
sig = inspect.signature(RedisSemanticCache.__init__)
params = list(sig.parameters.keys())
assert 'redis_client' in params, 'Must accept redis_client parameter'
print('RedisSemanticCache update: OK')
"
```

---

### Phase 10: 更新composition_root

**目标：** 注册新Provider初始化和shutdown hook

- [ ] 10.1 添加 `RedisPoolProvider.init()` 到 `bootstrap()`
- [ ] 10.2 添加 `shutdown()` 函数调用 `RedisPoolProvider.close_async()`
- [ ] 10.3 更新所有 Adapter 的构造方式，使用共享连接池

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

**验证命令：**
```bash
poetry run python -c "
from src.composition_root import bootstrap, shutdown
print('composition_root update: OK')
"
```

---

### Phase 11: 更新测试

**目标：** 确保测试通过，覆盖率达标

- [ ] 11.1 更新所有mock模式：适配器接受外部redis client
- [ ] 11.2 添加Provider reset测试工具
- [ ] 11.3 运行单元测试：`poetry run pytest tests/unit/infrastructure/storage/redis/ -v`
- [ ] 11.4 运行单元测试：`poetry run pytest tests/unit/infrastructure/messaging/ -v`
- [ ] 11.5 运行集成测试：`poetry run pytest tests/integration/ -v`
- [ ] 11.6 全量测试：`poetry run pytest tests/ -x -q`
- [ ] 11.7 覆盖率验证：`poetry run pytest --cov=src --cov-fail-under=80`

---

### Phase 12: 修复RedisConfig默认值矛盾

**目标：** 统一 RedisConfig 默认值，解决配置矛盾

- [ ] 12.1 检查 `src/infrastructure/config/redis.py` 中 `max_connections` 默认值
- [ ] 12.2 统一为 `100`（与 from_env 保持一致）
- [ ] 12.3 验证：类定义和 from_env 默认值一致

**验证命令：**
```bash
poetry run python -c "
from src.infrastructure.config.redis import RedisConfig

# 检查类定义默认值
import inspect
sig = inspect.signature(RedisConfig.__init__)
print(f'__init__ defaults: {sig}')

# 检查 from_env 默认值
config = RedisConfig()
print(f'max_connections={config.max_connections}')
assert config.max_connections == 100, 'Default should be 100'
print('Phase 12: OK')
"
```

---

### Phase 13: 修复RetryChecker连接池配置缺失

**目标：** 补全 RetryChecker 连接池配置

- [ ] 13.1 修改 `src/infrastructure/messaging/retry/checker.py`
- [ ] 13.2 添加 `max_connections` 和 `socket_timeout` 配置
- [ ] 13.3 使用 `RedisConfig` 而非硬编码参数

**新增修复代码：**
```python
# 替换原有的 ConnectionPool 创建
self._pool = aioredis.ConnectionPool(
    host=self._config.host,
    port=self._config.port,
    db=self._config.db,
    password=self._config.password,
    max_connections=self._config.max_connections,  # 新增
    socket_timeout=self._config.socket_timeout,    # 新增
    decode_responses=True,
)
```

**验证命令：**
```bash
poetry run python -c "
from src.infrastructure.messaging.retry.checker import RetryChecker
import inspect
sig = inspect.signature(RetryChecker.__init__)
print(f'RetryChecker params: {sig}')
print('Phase 13: OK')
"
```

---

### Phase 14: 修复composition_root初始化

**目标：** 在 composition_root 中正确初始化 Redis 连接

- [ ] 14.1 在 `bootstrap()` 中初始化 `RedisPoolProvider`
- [ ] 14.2 修改 `RedisMemoryCache` 注册，传入 redis_client
- [ ] 14.3 添加 shutdown hook 清理连接池

**新增代码：**
```python
# composition_root.py
from src.infrastructure.storage.redis.pool_provider import RedisPoolProvider

def bootstrap() -> None:
    # 初始化Redis连接池（新增）
    from src.infrastructure.config.redis import RedisConfig
    RedisPoolProvider.init(RedisConfig.from_env())

    # 注册 l1_cache 端口时传入 redis_client（修复）
    register_port(
        name="l1_cache",
        interface=L1CachePort,
        impl=RedisMemoryCache,
        factory=lambda: RedisMemoryCache(RedisPoolProvider.get_client()),
    )

def shutdown() -> None:
    """应用关闭时调用，清理资源。"""
    import asyncio
    if RedisPoolProvider.is_initialized():
        asyncio.run(RedisPoolProvider.close_async())
```

**验证命令：**
```bash
poetry run python -c "
from src.composition_root import bootstrap, shutdown
print('composition_root: OK')
"
```

---

### Phase 15: 补充RedisSemanticCache接口声明

**目标：** RedisSemanticCache 显式声明实现 SemanticCache 接口

- [ ] 15.1 修改 `src/infrastructure/storage/redis/semantic_cache.py`
- [ ] 15.2 添加 `implements SemanticCache` 声明
- [ ] 15.3 验证类型检查通过

**新增声明：**
```python
class RedisSemanticCache implements SemanticCache):  # 添加接口声明
    """Redis 语义缓存。

    实现 Story 1.4 定义的 SemanticCache 接口。
    """
```

**验证命令：**
```bash
poetry run python -c "
from src.infrastructure.storage.redis.semantic_cache import RedisSemanticCache
from src.application.ports.semantic_cache import SemanticCache
import inspect

# 检查是否实现接口方法
methods = ['get', 'set', 'invalidate']
for m in methods:
    assert hasattr(RedisSemanticCache, m), f'Missing method: {m}'
print('RedisSemanticCache interface: OK')
"
```

---

### Phase 16: 修复IdempotencyChecker连接池配置

**目标：** IdempotencyChecker 使用 RedisConfig 而非硬编码

- [ ] 16.1 修改 `src/infrastructure/messaging/retry/checker.py`
- [ ] 16.2 接受 `RedisConfig` 参数
- [ ] 16.3 配置 `max_connections` 和 `socket_timeout`
- [ ] 16.4 移除硬编码 ConnectionPool

**修复代码：**
```python
def __init__(self, config: RedisConfig | None = None):
    self._config = config or RedisConfig.from_env()
    self._pool: aioredis.ConnectionPool | None = None

def _get_pool(self) -> aioredis.ConnectionPool:
    if self._pool is None:
        self._pool = aioredis.ConnectionPool(
            host=self._config.host,
            port=self._config.port,
            db=self._config.db,
            password=self._config.password,
            max_connections=self._config.max_connections,  # 新增
            socket_timeout=self._config.socket_timeout,    # 新增
            decode_responses=True,
        )
    return self._pool
```

**验证命令：**
```bash
poetry run python -c "
from src.infrastructure.messaging.retry.checker import IdempotencyChecker
import inspect
sig = inspect.signature(IdempotencyChecker.__init__)
assert 'config' in str(sig), 'Must accept config parameter'
print('IdempotencyChecker: OK')
"
```

---

### Phase 17: 修复PortSpec.impl实例化机制

**目标：** 修复 composition_root 端口注册与实例化机制

- [ ] 17.1 修改 `PortSpec` 添加 `factory` 字段
- [ ] 17.2 在 `PortRegistry` 添加 `create_instance()` 方法
- [ ] 17.3 为 `l1_cache` 添加 factory 函数传入 redis_client

**修复代码：**
```python
# src/domain/ports/registry.py
@dataclass
class PortSpec:
    name: str
    version: str
    interface: Type
    impl: Type | Callable[..., Any] | str
    module: str
    lifetime: Lifetime
    owner: str
    tags: tuple[str, ...]
    factory: Callable[..., Any] | None = None  # 新增

class PortRegistry:
    def create_instance(self, name: str, **kwargs) -> Any:
        spec = self._ports.get(name)
        if spec is None:
            raise KeyError(f"Port not found: {name}")
        if spec.factory:
            return spec.factory(**kwargs)
        # 回退到类型实例化
        return spec.impl()

# composition_root.py
def create_l1_cache() -> L1CachePort:
    from src.infrastructure.storage.redis.pool_provider import RedisPoolProvider
    from src.infrastructure.storage.redis.redis_memory_cache import RedisMemoryCache
    return RedisMemoryCache(RedisPoolProvider.get_client())

register_port(
    name="l1_cache",
    interface=L1CachePort,
    impl=RedisMemoryCache,
    factory=create_l1_cache,  # 新增
    ...
)
```

**验证命令：**
```bash
poetry run python -c "
from src.domain.ports.registry import PortRegistry
from src.composition_root import bootstrap
bootstrap()
registry = PortRegistry()
instance = registry.create_instance('l1_cache')
print(f'Created: {type(instance).__name__}')
"
```

---

### Phase 18: 移动SemanticCache到domain层

**目标：** 将 SemanticCache 接口移至 domain/ports/，符合六边形架构

- [ ] 18.1 创建 `src/domain/ports/semantic_cache.py`
- [ ] 18.2 移动接口定义（保持方法签名不变）
- [ ] 18.3 更新所有引用

**新增文件：**
```python
# src/domain/ports/semantic_cache.py
"""SemanticCache Protocol — 领域层语义缓存接口。

定义语义缓存的接口，基础设施层负责实现（如 Redis 实现）。
"""
from __future__ import annotations

from abc import abstractmethod
from typing import Protocol


class SemanticCache(Protocol):
    """语义缓存协议接口。

    支持基于向量相似度的缓存查询和存储。
    """

    @abstractmethod
    async def get(self, query_embedding: list[float], threshold: float = 0.9) -> dict | None: ...

    @abstractmethod
    async def set(self, query_embedding: list[float], result: dict, ttl: int = 86400) -> None: ...

    @abstractmethod
    async def invalidate(self, cache_key: str) -> None: ...
```

**验证命令：**
```bash
poetry run python -c "
from src.domain.ports.semantic_cache import SemanticCache
print('SemanticCache in domain layer: OK')
"
```

---

### Phase 19: 修复_get_pool竞态条件

**目标：** 所有 Adapter 的 _get_pool 使用 _pool_lock 保护

- [ ] 19.1 修改 `RedisPublicBlackboard._get_pool` 使用 `_pool_lock`
- [ ] 19.2 修改 `RedisSessionStorage._get_pool` 使用 `_pool_lock`
- [ ] 19.3 修改 `RedisSemanticCache._get_pool` 使用 `_pool_lock`
- [ ] 19.4 移除未使用的 `_pool_lock` 变量（如已正确使用）

**修复代码：**
```python
async def _get_pool(self) -> aioredis.ConnectionPool:
    if self._pool is None:
        async with self._pool_lock:
            # 双重检查
            if self._pool is None:
                self._pool = aioredis.ConnectionPool(...)
    return self._pool
```

**验证命令：**
```bash
poetry run python -c "
import asyncio
from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard
# 验证 _pool_lock 被正确使用
bb = RedisPublicBlackboard.__new__(RedisPublicBlackboard)
assert hasattr(bb, '_pool_lock'), 'Must have _pool_lock'
print('_pool_lock protection: OK')
"
```

---

### Phase 20: 修复Infrastructure层架构违规

**目标：** 将 Application 层端口上移至 Domain 层

- [ ] 20.1 移动 `MetricsPort` 从 `application/ports/` 到 `domain/ports/`
- [ ] 20.2 移动 `EventSubscriber` 从 `application/ports/` 到 `domain/ports/`
- [ ] 20.3 移动 `SandboxExecutor` 从 `application/ports/` 到 `domain/ports/`
- [ ] 20.4 移动 `ExceptionMetricsPort` 从 `application/ports/` 到 `domain/ports/`
- [ ] 20.5 更新所有 Infrastructure 层导入

**验证命令：**
```bash
poetry run python -c "
from src.domain.ports.metrics_port import MetricsPort
from src.domain.ports.event_subscriber import EventSubscriber
from src.domain.ports.sandbox_port import SandboxExecutor
from src.domain.ports.exception_metrics_port import ExceptionMetricsPort
print('Infrastructure -> Domain port migration: OK')
"
```

---

### Phase 21: 统一Adapter初始化模式

**目标：** 所有 Redis Adapter 支持统一初始化模式

- [ ] 21.1 定义 `AdapterFactory` 统一创建接口
- [ ] 21.2 所有 Adapter 支持 `redis_client` 或 `config` 参数
- [ ] 21.3 所有 Adapter 实现 `__aenter__`/`__aexit__`

**统一初始化协议：**
```python
def __init__(
    self,
    redis_client: aioredis.Redis | None = None,
    config: RedisConfig | None = None,
):
    if redis_client:
        self._redis = redis_client
    elif config:
        self._redis = aioredis.Redis(connection_pool=self._get_pool(config))
    else:
        self._redis = RedisPoolProvider.get_client()
```

**验证命令：**
```bash
poetry run python -c "
from src.infrastructure.storage.redis.session_storage import RedisSessionStorage
from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard
# 验证支持统一初始化
import inspect
for cls in [RedisSessionStorage, RedisPublicBlackboard]:
    sig = inspect.signature(cls.__init__)
    params = list(sig.parameters.keys())
    assert 'redis_client' in params or 'config' in params
print('Adapter initialization: OK')
"
```

---

### Phase 22: 统一EventBus注册路径

**目标：** 修复 EventSubscriber 和 EventPublisher 注册不一致

- [ ] 22.1 删除独立的 `event_subscriber` 注册
- [ ] 22.2 通过 `DualChannelEventBus` 统一提供订阅能力
- [ ] 22.3 更新 `EventBusFactory` 并在 composition_root 中使用

**验证命令：**
```bash
poetry run python -c "
from src.infrastructure.messaging.event_bus_factory import EventBusFactory
factory = EventBusFactory()
bus, poller = factory.create_dual_channel_bus()
assert hasattr(bus, 'subscribe'), 'Must support subscribe'
print('EventBus factory: OK')
"
```

---

### Phase 23: 注册L2-L5存储层端口

**目标：** 在 composition_root 中注册所有存储层端口

- [ ] 23.1 注册 `L2MetadataRepositoryPort`
- [ ] 23.2 注册 `L2ChangeHistoryRepositoryPort`
- [ ] 23.3 注册 `L2GroupMemberRepositoryPort`
- [ ] 23.4 注册 `L3VectorPort`
- [ ] 23.5 注册 `L4ObjectPort`
- [ ] 23.6 注册 `L5GraphPort`
- [ ] 23.7 其他缺失端口

**验证命令：**
```bash
poetry run python -c "
from src.composition_root import bootstrap, _global_registry
bootstrap()
registered = [name for name in _global_registry.list_all().keys()]
expected = ['l2_metadata', 'l3_vector', 'l4_object', 'l5_graph']
for e in expected:
    assert e in registered, f'Missing: {e}'
print(f'Registered {len(registered)} ports')
"
```

---

## 五、接口变更汇总

### 5.1 新增接口

| 接口 | 文件 | 描述 |
|------|------|------|
| `GenericCachePort` | `src/domain/ports/generic_cache.py` | 通用缓存抽象接口 |
| `RedisGenericCacheAdapter` | `src/infrastructure/storage/redis/generic_cache_adapter.py` | 通用缓存Redis实现 |

### 5.2 修改接口

| 类 | 构造参数变更 | 说明 |
|----|------------|------|
| `RedisSessionStorage` | 新增 `redis_client` 参数 | 使用共享连接池 |
| `RedisPublicBlackboard` | 新增 `redis_client` 参数 | 使用共享连接池 |
| `RedisEventPublisher` | 新增 `redis_client` 参数 | 使用共享连接池 |
| `RedisEventSubscriber` | 新增 `redis_client` 参数 | 使用共享连接池 |
| `RedisSemanticCache` | 新增 `redis_client` 参数 | 使用共享连接池 |

### 5.3 不变接口

| 接口 | 说明 |
|------|------|
| `L1CachePort` | 保持专用接口不变，不通用化 |
| `SemanticCache` (application层) | 保持独立接口，不继承任何缓存接口 |
| `RedisMemoryCache` | 已支持外部client，无需改造 |

---

## 六、向后兼容性

### 6.1 迁移策略

| 旧实现 | 新实现 | 迁移策略 |
|--------|--------|----------|
| `RedisSessionStorage(config)` | `RedisSessionStorage(redis_client)` | 渐进式迁移，config仍支持 |
| `RedisPublicBlackboard(config)` | `RedisPublicBlackboard(redis_client)` | 渐进式迁移 |
| `RedisEventPublisher(config)` | `RedisEventPublisher(redis_client)` | 渐进式迁移 |
| `RedisEventSubscriber(config)` | `RedisEventSubscriber(redis_client)` | 渐进式迁移 |
| `RedisSemanticCache(config)` | `RedisSemanticCache(redis_client)` | 迁移后删除 |

### 6.2 渐进式迁移方案

**第一步：** 所有Adapter增加 `redis_client` 可选参数
```python
def __init__(self, redis_client: aioredis.Redis | None = None, config: RedisConfig | None = None):
    if redis_client:
        self._redis = redis_client
    elif config:
        self._redis = aioredis.Redis(connection_pool=self._get_pool(config))
    else:
        self._redis = RedisPoolProvider.get_client()
```

**第二步：** 调用方逐步切换到注入 redis_client

**第三步：** 移除 config 参数和自建连接池逻辑

### 6.3 影响范围

| 组件 | 影响 | 迁移工作 |
|------|------|----------|
| composition_root | 中 | 新增Provider初始化 |
| SessionStorage 调用方 | 中 | 构造参数变更 |
| PublicBlackboard 调用方 | 中 | 构造参数变更 |
| EventPublisher/Subscriber 调用方 | 中 | 构造参数变更 |
| 测试代码 | 中 | mock模式调整 |

---

## 七、风险控制

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 并发初始化竞争 | 高 | RedisPoolProvider 使用双重检查锁定 |
| 旧代码不兼容 | 中 | 渐进式迁移，保留config参数 |
| 测试mock失效 | 中 | 所有Adapter支持外部注入 |
| 并发连接数超限 | 低 | max_connections=100满足需求 |
| 向后兼容性破坏 | 高 | Phase验证通过后才进入下一阶段 |

---

## 八、验证清单

| Phase | 验证项 | 命令 |
|-------|--------|------|
| 1 | Provider单例正常 | `python -c "from src.infrastructure.storage.redis.pool_provider import RedisPoolProvider; p1 = RedisPoolProvider(); p2 = RedisPoolProvider(); assert p1 is p2"` |
| 1 | Provider线程安全 | 并发调用 `init()` 无竞争 |
| 1 | Provider可初始化 | `RedisPoolProvider.init()` → `get_client()` |
| 2 | GenericCachePort定义 | `from src.domain.ports.generic_cache import GenericCachePort; print('OK')` |
| 3 | RedisGenericCacheAdapter实现 | `hasattr(RedisGenericCacheAdapter, 'get')` |
| 4 | RedisSemanticCacheAdapter实现 | `isinstance(adapter, SemanticCachePort)` |
| 5 | RedisSessionStorage改造 | `redis_client` 参数存在 |
| 6 | RedisPublicBlackboard改造 | `redis_client` 参数存在 |
| 7 | RedisEventPublisher改造 | `redis_client` 参数存在 |
| 8 | RedisEventSubscriber改造 | `redis_client` 参数存在 |
| 9 | RedisSemanticCache（旧）改造 | `redis_client` 参数存在 |
| 10 | bootstrap/shutdown | `from src.composition_root import bootstrap; bootstrap()` |
| 11 | 全量测试 | `poetry run pytest tests/ -x -q` |
| 11 | 覆盖率达标 | `poetry run pytest --cov=src --cov-fail-under=80` |

---

## 九、预期收益

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| ConnectionPool数量 | 6个独立 | 1个共享 |
| 最大连接数 | 6 × 10 = 60 | 100 |
| 代码重复 | 6处连接池管理 | 0处 |
| 接口层次 | 扁平，无继承 | 六边形分层 |
| 可测试性 | 中 | 高（支持外部注入） |
| 可扩展性 | 低 | 高（可替换缓存技术） |

---

## 十、文件清单

### 新增文件

| 文件路径 | 职责 | Layer |
|----------|------|-------|
| `src/domain/ports/generic_cache.py` | GenericCachePort定义 | Domain |
| `src/infrastructure/storage/redis/pool_provider.py` | RedisPoolProvider实现 | Infrastructure |
| `src/infrastructure/storage/redis/generic_cache_adapter.py` | RedisGenericCacheAdapter实现 | Infrastructure |
| `src/infrastructure/storage/redis/semantic_cache_adapter.py` | RedisSemanticCacheAdapter实现 | Infrastructure |

### 修改文件

| 文件路径 | 变更 | 说明 |
|----------|------|------|
| `src/infrastructure/storage/redis/session_storage.py` | 接受外部redis_client | 使用共享连接池 |
| `src/infrastructure/storage/redis/public_blackboard.py` | 接受外部redis_client | 使用共享连接池 |
| `src/infrastructure/messaging/redis_publisher.py` | 接受外部redis_client | 使用共享连接池 |
| `src/infrastructure/messaging/redis_subscriber.py` | 接受外部redis_client | 使用共享连接池 |
| `src/infrastructure/storage/redis/semantic_cache.py` | 接受外部redis_client | 临时兼容，最终删除 |
| `src/composition_root.py` | 添加Provider初始化和shutdown hook | Bootstrap |

### 删除文件（重构完成后）

| 文件路径 | 原因 |
|----------|------|
| `src/infrastructure/storage/redis/semantic_cache.py` | 被semantic_cache_adapter.py替代 |

---

## 执行进度总览

```
[ ] Phase 1: RedisPoolProvider（线程安全单例）
[ ] Phase 2: GenericCachePort（新增通用缓存抽象）
[ ] Phase 3: RedisGenericCacheAdapter
[ ] Phase 4: RedisSemanticCacheAdapter
[ ] Phase 5: RedisSessionStorage（共享连接池）
[ ] Phase 6: RedisPublicBlackboard（共享连接池）
[ ] Phase 7: RedisEventPublisher（共享连接池）
[ ] Phase 8: RedisEventSubscriber（共享连接池）
[ ] Phase 9: RedisSemanticCache旧版（共享连接池）
[ ] Phase 10: composition_root（Bootstrap更新）
[ ] Phase 11: 测试更新（全量验证）
[ ] Phase 12: 修复RedisConfig默认值矛盾
[ ] Phase 13: 修复RetryChecker连接池配置缺失
[ ] Phase 14: 修复composition_root初始化
[ ] Phase 15: 补充RedisSemanticCache接口声明
[ ] Phase 16: 修复IdempotencyChecker连接池配置
[ ] Phase 17: 修复PortSpec.impl实例化机制
[ ] Phase 18: 移动SemanticCache到domain层
[ ] Phase 19: 修复_get_pool竞态条件
[ ] Phase 20: 修复Infrastructure层架构违规
[ ] Phase 21: 统一Adapter初始化模式
[ ] Phase 22: 统一EventBus注册路径
[ ] Phase 23: 注册L2-L5存储层端口
```

---

*文档版本: v3.3*
*重构目标: 建立六边形架构分层，统一连接池管理，线程安全单例，渐进式迁移，修复配置矛盾，修复5个架构违规问题*
