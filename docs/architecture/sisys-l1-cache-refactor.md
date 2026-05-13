# SISYS L1缓存层重构设计方案

**版本:** v2.2
**日期:** 2026-05-13
**状态:** 设计阶段
**审查状态:** 第1轮审查修订

---

## 修订说明 (v2.1)

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
| SemanticCache未继承L1CachePort | P0 | 确认问题存在，规划Phase 4修复 |
| SessionStorage不应继承L1CachePort | P1 | 语义不同，会话管理vs键值缓存，保持独立 |

---

## 一、现状分析

### 1.1 当前接口定义

| 接口 | 位置 | 方法签名 | 问题 |
|------|------|----------|------|
| `L1CachePort` | `src/domain/ports/l1_cache.py` | `get(key: str)`, `set(key, value, ttl)`, `delete(key)` | ✅ 通用接口 |
| `SemanticCache` | `src/application/ports/semantic_cache.py` | `get(query_embedding, threshold)`, `set(query_embedding, result, ttl)`, `invalidate(cache_key)` | ❌ 未继承L1CachePort，方法命名不规范 |
| `SessionStorage` | `src/domain/ports/session_storage.py` | `save(session_id, agent_id, state, ttl)`, `load(session_id)`, `delete(session_id)`, `exists(session_id)` | ❌ 未继承L1CachePort |

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
| `RedisMemoryCache` | `infrastructure/storage/redis/` | 接受外部client | `L1CachePort` | ✅ |
| `RedisSessionStorage` | `infrastructure/storage/redis/` | 自建 | `SessionStorage` | ❌ |
| `RedisSemanticCache` | `infrastructure/storage/redis/` | 自建 | 无（直接实现语义逻辑） | ❌ |
| `RedisPublicBlackboard` | `infrastructure/storage/redis/` | 自建 | `PublicBlackboard` | ❌ |
| `RedisEventPublisher` | `infrastructure/messaging/` | 自建 | 事件发布 | ❌ |
| `RedisEventSubscriber` | `infrastructure/messaging/` | 自建 | 事件订阅 | ❌ |
| `RedisSnapshotStore` | `infrastructure/storage/` | 接受外部client | `SnapshotRepositoryProtocol` | ✅ |
| `RedisEventBus` | `infrastructure/messaging/` | 委托上述两者 | `EventPublisher`+`EventSubscriber` | ⚠️ |

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
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Application/Domain Layer - 具体应用缓存端口              │
│                                                                  │
│  职责：继承L1CachePort，定义特定场景缓存能力                       │
│  位置：src/application/ports/                                     │
│  端口：                                                          │
│    - SemanticCachePort(L1CachePort, ...) ⚠️ 当前为SemanticCache，未继承│
│    - MemoryCachePort ❌ 不存在，实际由RedisMemoryCache直接实现L1CachePort│
│    - SessionStorage ❌ 不应继承L1CachePort（语义不同：会话管理vs缓存）│
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: Infrastructure - Redis技术实现 + 缓存管理                │
│                                                                  │
│  职责：实现L1CachePort接口 + Redis连接池统一管理                   │
│  位置：src/infrastructure/storage/redis/                           │
│  组件：                                                          │
│    - RedisPoolProvider (连接池单例)                               │
│    - RedisL1CacheAdapter (实现L1CachePort)                        │
│  特点：技术可替换（未来可新增MemcachedAdapter等）                  │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: Infrastructure - 具体应用缓存端口实现                     │
│                                                                  │
│  职责：实现具体应用缓存端口（SemanticCachePort等）                 │
│  位置：src/infrastructure/storage/redis/                           │
│  组件：                                                          │
│    - RedisSemanticCacheAdapter (实现SemanticCachePort)           │
│      └─ 组合RedisL1CacheAdapter处理基础缓存                       │
│    - RedisMemoryCache (已有，实现MemoryCachePort)                 │
│      └─ 改为组合RedisL1CacheAdapter                              │
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

# Layer 3: Infrastructure Redis实现
class RedisL1CacheAdapter(L1CachePort):
    """Redis通用缓存实现"""
    def __init__(self, redis_client: aioredis.Redis | None = None): ...

# Layer 4: Infrastructure具体应用实现
class RedisSemanticCacheAdapter(SemanticCachePort):
    """Redis语义缓存实现"""
    def __init__(self, redis_client: aioredis.Redis | None = None):
        self._base = RedisL1CacheAdapter(redis_client)

    async def get_by_embedding(self, query_embedding, threshold):
        # 语义相似度查找
        ...

    async def set_with_embedding(self, query_embedding, result, ttl):
        # 存储向量和结果
        ...

    # 继承L1CachePort基础方法
    async def get(self, key: str) -> str | None:
        return await self._base.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        return await self._base.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        return await self._base.delete(key)
```

### 2.3 四层模型说明

| Layer | 名称 | 职责 | 技术依赖 |
|-------|------|------|----------|
| Layer 1 | Domain Layer | 定义纯抽象接口，零外部依赖 | 无 |
| Layer 2 | Application/Domain Layer | 定义业务语义接口，继承Layer 1 | 无 |
| Layer 3 | Infrastructure - 技术实现 | 实现底层存储能力，管理连接池 | Redis |
| Layer 4 | Infrastructure - 业务实现 | 实现业务接口，委托Layer 3 | Redis + Layer 3组件 |

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
"""L1CachePort — L1 缓存存储抽象端口。

通用缓存抽象，所有具体缓存实现必须实现此接口。
"""

from __future__ import annotations

from typing import Protocol


class L1CachePort(Protocol):
    """L1 缓存存储接口（通用底层抽象）。

    设计原则：
    - 领域层零外部依赖（仅用 abc + typing）
    - 异步优先（async def）
    - 技术无关（可使用Redis/Memcached/内存等实现）

    所有具体缓存实现（如SemanticCache、MemoryCache）继承此接口，
    获得基础缓存能力。
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

### 3.2 Layer 2: 重构SemanticCachePort

**文件：** `src/application/ports/semantic_cache.py`

```python
"""SemanticCache Protocol — 语义缓存应用层接口。

继承L1CachePort，提供基于向量相似度的缓存能力。
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Protocol

from src.domain.ports.l1_cache import L1CachePort


class SemanticCachePort(L1CachePort, Protocol):
    """语义缓存协议接口。

    支持基于向量相似度的缓存查询和存储。
    继承L1CachePort获得基础缓存能力。

    具体实现（如RedisSemanticCacheAdapter）委托L1CacheAdapter
    处理基础缓存操作。
    """

    async def get_by_embedding(
        self,
        query_embedding: list[float],
        threshold: float = 0.9,
    ) -> dict | None:
        """通过向量嵌入查询缓存。

        Args:
            query_embedding: 查询向量嵌入
            threshold: 相似度阈值（0.0-1.0）

        Returns:
            缓存结果，如果未命中则返回 None
        """

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
            ttl: 过期时间（秒），默认24小时
        """

    async def invalidate(self, cache_key: str) -> None:
        """使缓存失效。

        Args:
            cache_key: 缓存键
        """
```

### 3.3 Layer 3: RedisPoolProvider

**文件：** `src/infrastructure/storage/redis/pool_provider.py`

```python
"""Redis连接池统一提供者（单例模式）。

在composition_root初始化时创建单一连接池，
所有Adapter复用此连接池，实现资源统一管理。

遵循六边形架构：
- 资源管理封装在Infrastructure层
- Domain层完全不感知连接池存在

设计考虑：
- 单例模式确保全局唯一连接池
- 支持异步和同步两种关闭方式
- 测试时可替换为mock
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Final

import redis.asyncio as aioredis

from src.infrastructure.config.redis import RedisConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Redis官方推荐：max_connections = CPU_cores * 2，通常50-100
DEFAULT_MAX_CONNECTIONS: Final[int] = 100


class RedisPoolProvider:
    """Redis连接池统一提供者（单例模式）。

    Attributes:
        _instance: 单例实例
        _pool: 连接池
        _config: Redis配置
    """

    _instance: RedisPoolProvider | None = None
    _pool: aioredis.ConnectionPool | None = None
    _config: RedisConfig | None = None

    def __new__(cls) -> RedisPoolProvider:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def init(cls, config: RedisConfig | None = None) -> None:
        """初始化连接池。

        Args:
            config: Redis配置，默认从环境变量加载
        """
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
        cls._pool = None
        cls._config = None
        cls._instance = None
        logger.info("RedisPoolProvider reset")
```

### 3.4 Layer 3: RedisL1CacheAdapter

**文件：** `src/infrastructure/storage/redis/l1_cache_adapter.py`

```python
"""Redis L1 缓存通用适配器。

实现L1CachePort接口，提供通用Redis缓存能力。
所有具体缓存实现（如SemanticCache、MemoryCache）委托此适配器
处理基础缓存操作。

架构来源: architecture.md §11.2.9
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Final

import redis.asyncio as aioredis

from src.domain.ports.l1_cache import L1CachePort
from src.infrastructure.storage.redis.pool_provider import RedisPoolProvider

if TYPE_CHECKING:
    pass

# 默认TTL范围 (秒)
DEFAULT_TTL_MIN: Final[int] = 86400  # 24h
DEFAULT_TTL_MAX: Final[int] = 108000  # 30h


class RedisL1CacheAdapter(L1CachePort):
    """Redis L1 缓存通用适配器。

    实现L1CachePort接口，提供通用Redis缓存能力。
    所有具体缓存实现可委托此适配器处理基础缓存操作。

    设计原则：
    - 单一职责：只处理基础get/set/delete
    - 可测试：支持注入mock redis client
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

### 3.5 Layer 4: RedisSemanticCacheAdapter

**文件：** `src/infrastructure/storage/redis/semantic_cache_adapter.py`

```python
"""Redis 语义缓存适配器。

实现SemanticCachePort接口，提供基于向量相似度的缓存能力。
委托RedisL1CacheAdapter处理基础缓存操作。

使用Redis Hash存储嵌入向量和缓存结果，
支持纯Python余弦相似度计算。
"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import TYPE_CHECKING, Any

import redis.asyncio as aioredis

from src.application.ports.semantic_cache import SemanticCachePort
from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.storage.redis.l1_cache_adapter import RedisL1CacheAdapter
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

    实现SemanticCachePort接口，提供基于向量相似度的缓存能力。
    委托RedisL1CacheAdapter处理基础缓存操作。

    键格式: sisys:cache:semantic:{cache_key}
    支持基于余弦相似度的语义匹配。

    Attributes:
        _base: 基础L1缓存适配器
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
        self._base = RedisL1CacheAdapter(redis_client)
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

    async def get(self, key: str) -> str | None:
        """获取缓存（继承自L1CachePort）。

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在返回None
        """
        return await self._base.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        """设置缓存（继承自L1CachePort）。

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）

        Returns:
            是否成功
        """
        return await self._base.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """删除缓存（继承自L1CachePort）。

        Args:
            key: 缓存键

        Returns:
            是否成功
        """
        return await self._base.delete(key)

    async def get_by_embedding(
        self,
        query_embedding: list[float],
        threshold: float = 0.9,
    ) -> dict | None:
        """通过向量嵌入查询缓存。

        遍历所有缓存条目，找到相似度高于阈值的第一个结果。

        Args:
            query_embedding: 查询向量嵌入
            threshold: 相似度阈值

        Returns:
            缓存结果，如果未命中则返回None
        """
        # 使用SCAN遍历所有缓存键
        pattern = build_key(self._NAMESPACE, "vec:*")
        cursor = 0

        while True:
            cursor, keys = await self._base._redis.scan(
                cursor=cursor,
                match=pattern,
                count=100,
            )

            for key in keys:
                stored_embedding = await self._base._redis.hget(key, "embedding")
                stored_result_data = await self._base._redis.hget(key, "result")

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

        await self._base._redis.hset(key, "embedding", json_dumps(query_embedding))
        await self._base._redis.hset(key, "result", json_dumps(result))
        await self._base._redis.expire(key, ttl)
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

### Phase 1: 创建RedisPoolProvider ✅

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

### Phase 3: 创建RedisL1CacheAdapter ✅

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

### Phase 5: 创建RedisSemanticCacheAdapter ✅

**目标：** 创建语义缓存适配器实现（Layer 4 实现）

- [ ] 5.1 创建 `src/infrastructure/storage/redis/semantic_cache_adapter.py`
- [ ] 5.2 实现 `SemanticCachePort` 接口（继承L1CachePort + 语义方法）
- [ ] 5.3 组合 `RedisL1CacheAdapter`：委托基础缓存操作
- [ ] 5.4 实现纯Python余弦相似度计算（不使用numpy）

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
[ ] Phase 1: RedisPoolProvider
[x] Phase 2: L1CachePort重构
[x] Phase 3: RedisL1CacheAdapter
[x] Phase 4: SemanticCachePort重构
[x] Phase 5: RedisSemanticCacheAdapter
[ ] Phase 6: RedisMemoryCache（可选）
[ ] Phase 7: Messaging层Adapter
[ ] Phase 8: SessionStorage/PublicBlackboard
[ ] Phase 9: composition_root
[ ] Phase 10: 测试更新
```

---

*文档版本: v2.0*
*重构目标: 建立四层缓存架构，统一连接池管理，使用checkbox跟踪执行进度*
