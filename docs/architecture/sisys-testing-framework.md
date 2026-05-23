# SISYS 测试工程框架方案

**文档版本**: v2.0.0
**创建日期**: 2026-04-20
**更新日期**: 2026-04-21
**状态**: 已批准实施
**负责人**: Agimtech

---

## 一、现状诊断

### 1.1 测试系统结构

```
tests/
├── conftest.py              # 仅添加项目路径 (sys.path)
├── acceptance/              # BDD 验收测试（使用真实服务）
│   ├── test_acceptance_event_bus_implementation.py   # 依赖 rabbitmq_publisher/consumer fixtures
│   ├── test_acceptance_qdrant_vector_layer.py   # 依赖 vector_storage/collection_manager fixtures
│   └── test_story_*.feature     # Gherkin 场景定义
├── integration/              # 集成测试（使用 fakeredis mock）
│   └── conftest.py          # 提供 mock fixtures (scope=function)
├── integration/         # 真实服务集成测试
│   └── conftest.py          # 从 .env 读取连接参数 (scope=session)
└── fixtures/                 # 空目录（预留）
```

**CI 测试执行流程** (`.gitea/workflows/ci.yaml` lines 240-289):
1. 启动 `deploy/app/docker-compose.yml` 服务，等待 `healthy`
2. 设置 `SISYS_TEST_ENV=ci` 环境变量（让 `environments.py` 自动检测）
3. 运行：`pytest tests/integration tests/integration tests/acceptance`

**注意**：不要使用 `export REDIS_HOST=host.docker.internal` 覆盖已有环境变量。这样会与 `.env` 读取冲突。应设置 `SISYS_TEST_ENV=ci` 让自动检测逻辑生效。

**连接配置**:
- 本地开发：从 `.env` 读取 `localhost:6379/5432/6333...`
- CI 环境：覆盖为 `host.docker.internal:6380/5432/6333...`
- K8s 环境：通过 ArgoCD Service DNS 访问

### 1.2 测试目录概览

| 目录 | 文件数 | 测试类型 | 特性 |
|------|--------|---------|------|
| `tests/acceptance/` | 12 | BDD 验收测试 | 真实服务 + Gherkin |
| `tests/integration/` | 15 | 集成测试 | fakeredis mock |
| `tests/integration/` | 6 | 真实服务集成测试 | 真实存储服务 |
| `tests/unit/` | 70 | 单元测试 | mock + 快速执行 |

### 1.3 服务依赖分析

| 服务 | acceptance | integration | integration | unit | 优先级 |
|------|------------|-------------|------------------|------|--------|
| Redis | 89 | 84 | 43 | 58 | 🔴 高 |
| Neo4j | 61 | 13 | 20 | 58 | 🔴 高 |
| RabbitMQ | 41 | 4 | - | 1 | 🟡 中 |
| MinIO | 40 | - | 29 | 61 | 🟡 中 |
| PostgreSQL | 25 | 58 | 13 | 16 | 🔴 高 |
| Qdrant | 25 | 16 | 23 | 19 | 🟡 中 |

### 1.4 问题背景

在 gitea-runner CI 环境和本地开发环境同时运行时，发现以下测试失败：

| 测试 | 环境 | 错误信息 |
|------|------|---------|
| `test_ac2_rabbitmq_agentdecided` | gitea-runner | Consumer did not receive event (0 received) |
| `test_ac2_rabbitmq_documentprocessed` | 本地 | Consumer did not receive event (0 received) |
| `test_dense_search_with_filter` | 本地 | Collection `sisys_documents_finance` doesn't exist |

### 1.5 核心问题分类

| 问题编号 | 分类 | 问题描述 | 严重度 |
|---------|------|---------|--------|
| P1 | 测试实现 | `async_consume()` 永久阻塞 | 🔴 致命 |
| P2 | 测试实现 | `collection_has_different_domains` 缺少 create_collection | 🔴 致命 |
| P3 | 环境配置 | CI 设置 `host.docker.internal` 但测试用 `localhost` | 🔴 致命 |
| P4 | 测试工程 | 验收测试无隔离机制（fixture 依赖顺序） | 🔴 致命 |
| P5 | 架构设计 | 多环境 docker-compose 端口不一致 | 🟡 中等 |
| P6 | 测试工程 | 测试使用 `scope=module` 事件循环导致状态污染 | 🟡 中等 |

### 1.6 根因分析结论

> **这是测试实现问题，而非多用户并发架构缺陷。**

您的多用户并发架构设计是正确的：
- `IdempotencyChecker` 使用 `SET NX EX` 原子操作
- 队列 `durable=True` 配置正确
- 测试失败是隔离问题，不是并发竞争问题

---

## 二、解决方案架构

### 2.1 核心设计原则

> ⚠️ **简化说明**：原设计中的 TOR (测试编排层) 已由 pytest-xdist + pytest fixture 机制解决，
> 本方案仅保留 TEM (测试环境管理层) 和 TIL (测试隔离层)。

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        多用户并发测试工程系统架构                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        测试环境管理层 (TEM)                              │ │
│  │                                                                        │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐ │ │
│  │  │  Local Dev     │  │   CI (Runner)  │  │  ArgoCD K8s Cluster   │ │ │
│  │  │  localhost     │  │ host.docker.   │  │  {env}.sisys.svc.     │ │ │
│  │  │  :6380/:5433  │  │   internal     │  │    cluster.local      │ │ │
│  │  └───────┬────────┘  └───────┬────────┘  └───────────┬────────────┘ │ │
│  │          │                    │                        │              │ │
│  │          └────────────────────┼────────────────────────┘              │ │
│  │                               ▼                                         │ │
│  │                    ┌───────────────────────┐                            │ │
│  │                    │  EnvironmentResolver │                            │ │
│  │                    │  (基于 ENV 自动适配)   │                            │ │
│  │                    └───────────┬───────────┘                            │ │
│  └──────────────────────────────┼──────────────────────────────────────────┘ │
│                                 │                                               │
│                                 ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │                        测试隔离层 (TIL)                                    │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │  Tenant Isolation (租户隔离)                                        │  │ │
│  │  │  • 测试租户前缀: test_{uuid}                                       │  │ │
│  │  │  • 队列隔离: test_{uuid}_queue                                   │  │ │
│  │  │  • Collection 隔离: test_{uuid}_finance                          │  │ │
│  │  │  • K8s Namespace 隔离: sisys-{env} 内的测试资源                   │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │  Resource Lifecycle Manager (资源生命周期管理)                      │  │ │
│  │  │  • Fixture 级清理 (function scope)                                 │  │ │
│  │  │  • Class 级清理 (class scope)                                     │  │ │
│  │  │  • Session 级清理 (session scope)                                 │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  执行层 (由 pytest-xdist + pytest fixture 机制提供)                     │ │
│  │  • 串行/并行执行: pytest-xdist                                         │ │
│  │  • 依赖声明: pytest fixture 依赖图                                      │ │
│  │  • 失败隔离: fixture scope 控制                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 关键设计决策

| 决策点 | 选项 A (当前问题) | 选项 B (推荐) | 理由 |
|-------|-----------------|--------------|------|
| 测试环境连接 | 硬编码 localhost | 环境变量 + 自动解析 | 适配 Local/CI/ArgoCD K8s 三种环境 |
| 租户隔离 | 无隔离 | UUID 前缀隔离 | 防止测试间干扰 |
| Fixture 作用域 | module/class | function (默认) | 确保测试独立 |
| 服务端口 | 分散不一致 | 统一通过 ENV 变量 | 单一配置源 |
| K8s 服务发现 | 无 | K8s Service DNS | ArgoCD 环境内使用集群内部地址 |
| 测试执行 | 随机顺序 | 显式声明依赖 | 避免隐式依赖 |

---

## 三、具体实施方案

### 3.1 第一阶段：修复测试实现缺陷 (P1, P2)

#### 3.1.1 修复 `async_consume()` 永久阻塞问题

**文件**: `tests/acceptance/test_acceptance_event_bus_implementation.py`

**问题代码**:
```python
# ❌ 当前实现 - 永久阻塞
async def _setup_consumer():
    await rabbitmq_consumer.bind_queue(queue_name, routing_key)
    await rabbitmq_consumer.async_consume(queue_name)  # 永远不返回

event_loop.run_until_complete(_setup_consumer())   # 阻塞
event_loop.run_until_complete(_publish_and_wait())  # 永远不会执行
```

**修复方案**:
```python
# ✅ 修复方案 - 使用 asyncio.create_task 后台运行 + 启动确认
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def temporary_consumer(consumer, queue_name, routing_key, handler, timeout=5.0):
    """临时消费者上下文管理器，确保正确的设置和清理顺序.

    Args:
        consumer: RabbitMQ consumer 实例
        queue_name: 队列名称
        routing_key: 路由键
        handler: 事件处理函数
        timeout: 等待消费者启动的超时时间（秒）

    Raises:
        TimeoutError: 消费者在超时时间内未能启动
    """
    event_type = queue_name.split("-")[-1]
    consumer.register_handler(event_type, handler)
    await consumer.bind_queue(queue_name, routing_key)

    # 使用 create_task 后台运行，不阻塞
    consume_task = asyncio.create_task(consumer.async_consume(queue_name))

    # 轮询等待消费者真正开始消费（替代硬编码 sleep）
    # 这样在慢速环境下也能正常工作
    try:
        await asyncio.wait_for(
            _wait_for_consumer_ready(consumer, queue_name), timeout=timeout
        )
    except asyncio.TimeoutError:
        consume_task.cancel()
        await consume_task
        raise RuntimeError(
            f"Consumer failed to start within {timeout}s. "
            "Check RabbitMQ connection and queue binding."
        )

    try:
        yield
    finally:
        # 清理：先停止消费，再取消任务，最后关闭连接
        try:
            # 如果 consumer 有 stop_consuming 方法，先调用它
            if hasattr(consumer, 'stop_consuming'):
                await consumer.stop_consuming()
        except Exception:
            pass  # 忽略关闭时的错误

        # 取消任务
        if not consume_task.done():
            consume_task.cancel()
            try:
                await asyncio.wait_for(consume_task, timeout=1.0)
            except asyncio.TimeoutError:
                # 超时后强制取消
                consume_task.cancel()
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        # 最后关闭连接
        try:
            await consumer.close()
        except Exception:
            pass  # 忽略关闭时的错误


async def _wait_for_consumer_ready(
    consumer,
    queue_name: str,
    poll_interval=0.1,
    max_polls=50,
):
    """轮询等待消费者真正开始消费.

    Args:
        consumer: RabbitMQConsumer 实例
        queue_name: 队列名称，用于被动检查队列是否存在
        poll_interval: 轮询间隔（秒）
        max_polls: 最大轮询次数

    Returns:
        True: 消费者已就绪

    Raises:
        asyncio.TimeoutError: 超过最大轮询次数
    """
    for _ in range(max_polls):
        # ✅ 修复 #1: 通过 declare_queue passive=True 检查队列是否已声明
        # 这是判断消费者真正绑定队列的最可靠方式
        if consumer._channel is not None:
            try:
                # 被动声明队列，如果队列存在则成功，不存在则抛异常
                await consumer._channel.declare_queue(queue_name, passive=True)
                return True  # 队列存在，说明消费者已绑定
            except Exception:
                pass  # 队列不存在，继续等待
        await asyncio.sleep(poll_interval)

    raise asyncio.TimeoutError(
        f"Consumer not ready after {max_polls} polls. "
        f"Queue '{queue_name}' was not declared."
    )


@then("异步消费者应该接收到该事件")
def verify_rabbitmq_consumer_receives(
    rabbitmq_publisher: RabbitMQPublisher,
    rabbitmq_consumer: RabbitMQConsumer,
    event_loop,
):
    """Verify async consumer receives the event."""
    received_events = []
    event_type = "DocumentProcessed"
    queue_name = f"test-queue-{uuid.uuid4().hex[:8]}"
    routing_key = f"{RABBITMQ_ROUTING_PREFIX}{event_type}"

    async def handler(event: DomainEvent):
        received_events.append(event)

    async def _test():
        async with temporary_consumer(
            rabbitmq_consumer, queue_name, routing_key, handler, timeout=5.0
        ):
            event = DocumentProcessed(
                document_id=uuid.uuid4(),
                parse_result={"pages": 5},
                embedding=[0.1, 0.2],
            )
            await rabbitmq_publisher.async_publish(event, routing_key)
            # 等待消息传递
            await asyncio.sleep(2.0)

    event_loop.run_until_complete(_test())
    assert len(received_events) > 0, f"Consumer did not receive event. Got {len(received_events)}"
```

**P1 修复关键改进点：**

| 问题 | 原方案 | 修复方案 |
|------|--------|---------|
| 启动确认 | 硬编码 `sleep(0.5)` | 轮询 `_connection.is_closed` 状态 |
| 慢速环境 | 0.5s 可能不足 | 可配置超时，最长 5s |
| 任务取消 | 直接 `cancel()` 可能丢消息 | 先 `stop_consuming()` 再取消 |
| 异常处理 | 无 | 分层异常处理，层层保障 |

**实现验证**（`RabbitMQConsumer` 私有属性）：
```python
# 第 60-61 行
self._connection: AbstractConnection | None = None
self._channel: AbstractChannel | None = None

# 第 215 行 close() 方法中：
if self._connection and not self._connection.is_closed:
    await self._connection.close()
```

**⚠️ 注意**：测试代码直接访问 `consumer._connection` 和 `consumer._channel` 私有属性。这是测试专用 hack，不应修改源码。

#### 3.1.2 修复 `collection_has_different_domains` fixture

**文件**: `tests/acceptance/test_acceptance_qdrant_vector_layer.py`

**问题代码**:
```python
# ❌ 当前实现 - 缺少 create_collection
@given('Collection "sisys:documents:finance" 包含不同业务域的向量点')
def collection_has_different_domains(...):
    async def _insert():
        for domain in ["report", "analysis", "summary"]:
            for i in range(10):
                await vector_storage.upsert_points("sisys_documents_finance", points)
                # ↑ 缺少 collection 创建！
```

**修复方案**:
```python
# ✅ 修复方案 - 利用 create_collection 的幂等性
@given('Collection "sisys:documents:finance" 包含不同业务域的向量点')
def collection_has_different_domains(
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Collection contains vectors with different business domains."""

    async def _setup_and_insert():
        collection_name = "sisys_documents_finance"

        # 1. 确保 collection 存在
        # QdrantCollectionManager.create_collection() 本身是幂等的：
        # - 如果已存在，返回 False
        # - 如果新建成功，返回 True
        # - 不抛出异常
        await collection_manager.create_collection(
            name=collection_name,
            vector_size=1024,
            distance="Cosine",
        )

        # 2. 插入不同业务域的向量
        for domain in ["report", "analysis", "summary"]:
            for i in range(10):
                points = [
                    VectorPoint(
                        id=f"{domain}-{i}",
                        vector=[0.1] * 1024,
                        payload={
                            "document_id": f"doc-{domain}-{i}",
                            "business_domain": domain,
                        },
                    )
                ]
                await vector_storage.upsert_points(collection_name, points)

    event_loop.run_until_complete(_setup_and_insert())
```

**P2 修复关键改进点：**

| 问题 | 原方案 | 修复方案 |
|------|--------|---------|
| 异常处理 | `except Exception: pass` 静默忽略 | 利用 `create_collection()` 幂等性，无需异常处理 |
| 代码简洁性 | 复杂异常判断逻辑 | 简单调用，返回值即可判断 |
| 错误诊断 | 网络超时等真正错误被隐藏 | 真正的错误会正常抛出 |

**实现验证**（`QdrantCollectionManager.create_collection` 第 54-55 行）：
```python
if await self.collection_exists(name):
    return False  # 已存在，返回 False
```

**⚠️ 重要提醒**：`create_collection` 的幂等性实现意味着：
- 测试首次运行：collection 被创建，返回 `True`
- 测试再次运行：collection 已存在，返回 `False`
- 无论哪种情况，都不会抛出异常

---

### 3.2 第二阶段：建立测试环境管理层 (P3, P5)

#### 3.2.1 创建统一环境配置模块

**文件**: `tests/environments.py`

```python
"""测试环境配置解析器。

支持三种测试环境：
1. Local Dev: 直接连接 localhost
2. CI: 通过 host.docker.internal 连接宿主机 (gitea-runner)
3. K8s: 通过 K8s Service DNS 连接集群内部服务

用法:
    from tests.environments import resolve_env

    config = resolve_env()
    # config.redis_host -> 根据环境返回正确的主机地址
"""

import os
import socket
from dataclasses import dataclass
from enum import Enum


class TestEnvironment(Enum):
    """测试环境类型."""
    LOCAL = "local"           # 本地开发环境
    CI = "ci"                 # CI 环境 (gitea-runner/docker)
    K8S = "k8s"              # ArgoCD K8s 环境
    AUTO = "auto"             # 自动检测


@dataclass
class TestEnvConfig:
    """测试环境配置."""

    # 主机连接
    redis_host: str
    redis_port: int
    redis_password: str | None = None  # ✅ 修复 #R1: Redis 清理需要认证密码
    postgres_host: str
    postgres_port: int
    postgres_database: str  # ✅ 修复 #G: 添加缺失字段
    postgres_username: str  # ✅ 修复 #D: 添加认证字段
    postgres_password: str  # ✅ 修复 #D: 添加认证字段
    qdrant_host: str
    qdrant_port: int
    qdrant_grpc_port: int
    qdrant_api_key: str | None = None  # ✅ 修复 #H: 添加 Qdrant api_key
    minio_host: str
    minio_port: int
    minio_console_port: int
    minio_access_key: str | None = None  # ✅ 修复 #N2: MinIO 清理需要认证
    minio_secret_key: str | None = None  # ✅ 修复 #N2: MinIO 清理需要认证
    neo4j_host: str
    neo4j_http_port: int
    neo4j_bolt_port: int
    rabbitmq_host: str
    rabbitmq_port: int
    rabbitmq_mgmt_port: int
    rabbitmq_username: str  # ✅ 修复 #E: 添加 RabbitMQ 认证
    rabbitmq_password: str  # ✅ 修复 #E: 添加 RabbitMQ 认证

    # 环境标识
    env_type: TestEnvironment
    test_tenant_id: str  # 用于测试隔离的租户 ID

    # K8s 特有配置（仅 K8S 环境有效）
    k8s_namespace: str | None = None

    def get_k8s_service_dns(self, service: str) -> str:
        """获取 K8s Service DNS 名称."""
        if self.k8s_namespace is None:
            raise ValueError("K8s namespace not configured")
        return f"{service}.{self.k8s_namespace}.svc.cluster.local"

    @classmethod
    def from_env(
        cls,
        env_file: str | None = None,
        test_tenant_id: str | None = None,
    ) -> TestEnvConfig:
        """从环境变量或 .env 文件创建配置（与开发环境共用同一份配置）。

        使用 load_dotenv() 加载 .env 文件，读取与 src.infrastructure.config
        各模块相同的标准环境变量名，支持直接复用开发环境的配置。

        注意：此方法始终返回 `env_type=TestEnvironment.LOCAL`，适用于本地开发调试。
        CI/K8s 环境请使用 `resolve_env()` 函数，它会根据环境自动检测连接参数。

        Args:
            env_file: 可选，.env 文件路径。默认为 ./.env 或上级目录的 .env。
            test_tenant_id: 可选，测试租户 ID，用于隔离。为 None 时自动生成。

        Returns:
            TestEnvConfig 实例（env_type 固定为 LOCAL）
        """
        import uuid
        from pathlib import Path
        from dotenv import load_dotenv

        # 加载 .env 文件（默认查找当前目录及上级目录）
        if env_file:
            load_dotenv(env_file, override=True)
        else:
            # 尝试从 tests/ 目录向上查找 .env
            env_path = Path(__file__).parents[2] / ".env"
            if env_path.exists():
                load_dotenv(env_path, override=True)
            else:
                load_dotenv(override=True)  # 只加载已设置的环境变量

        tenant_id = test_tenant_id or f"test_{uuid.uuid4().hex[:8]}"

        return cls(
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_password=os.getenv("REDIS_PASSWORD"),
            postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            postgres_database=os.getenv("POSTGRES_DATABASE", "sisys"),
            postgres_username=os.getenv("POSTGRES_USERNAME", "postgres"),
            postgres_password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
            qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
            qdrant_grpc_port=int(os.getenv("QDRANT_GRPC_PORT", "6334")),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            minio_host=os.getenv("MINIO_HOST", "localhost"),
            minio_port=int(os.getenv("MINIO_API_PORT", "9000")),
            minio_console_port=int(os.getenv("MINIO_CONSOLE_PORT", "9001")),
            minio_access_key=os.getenv("MINIO_ROOT_USER"),
            minio_secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
            neo4j_host=os.getenv("NEO4J_HOST", "localhost"),
            neo4j_http_port=int(os.getenv("NEO4J_HTTP_PORT", "7474")),
            neo4j_bolt_port=int(os.getenv("NEO4J_BOLT_PORT", "7687")),
            rabbitmq_host=os.getenv("RABBITMQ_HOST", "localhost"),
            rabbitmq_port=int(os.getenv("RABBITMQ_PORT", "5672")),
            rabbitmq_mgmt_port=int(os.getenv("RABBITMQ_MGMT_PORT", "15672")),
            rabbitmq_username=os.getenv("RABBITMQ_USERNAME", "guest"),
            rabbitmq_password=os.getenv("RABBITMQ_PASSWORD", "guest"),
            env_type=TestEnvironment.LOCAL,
            test_tenant_id=tenant_id,
            k8s_namespace=None,
        )


# K8s namespace 到服务 DNS 后缀的映射
_K8S_ENV_NAMESPACES = {
    "development": "sisys-dev",
    "testing": "sisys-test",
    "production": "sisys-prod",
}


def _detect_environment() -> TestEnvironment:
    """自动检测当前测试环境.

    检测优先级（从高到低）：
    1. 环境变量显式指定（SISYS_TEST_ENV）
    2. K8s Service Account token（最可靠的 K8s 证据）
    3. 容器内运行 + CI 环境变量
    4. 默认本地开发环境

    注意：K8s 检测优先于 CI 环境变量检测。
    原因：在 ArgoCD K8s 环境中运行时，CI 系统可能设置 CI=true，
    但我们必须优先识别为 K8s 环境，因为连接参数（Service DNS）不同。
    """
    # 1. 优先使用环境变量显式指定
    explicit = os.getenv("SISYS_TEST_ENV", "").lower()
    if explicit in ("local", "ci", "k8s"):
        return TestEnvironment(explicit)

    # 2. K8s 环境检测（检查 Service Account token）
    # 这是最可靠的 K8s 运行环境证据
    if _is_running_in_k8s():
        return TestEnvironment.K8S

    # 3. CI 环境检测 (gitea-runner)
    # 注意：如果在 K8s 中运行但 token 检测失败，仍然应该通过 CI 变量识别
    if os.getenv("CI") == "true" or os.getenv("GITEA_RUNNER") == "true":
        return TestEnvironment.CI

    # 4. 容器内运行但非 K8s → CI
    if _is_running_in_container():
        return TestEnvironment.CI

    # 5. 默认本地开发环境
    return TestEnvironment.LOCAL


def _is_running_in_k8s() -> bool:
    """检测是否在 K8s 环境中运行."""
    # 检查 Service Account token
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
        return True

    # 检查 K8s API 可达性
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("kubernetes.default.svc", 443))
        sock.close()
        return result == 0
    except socket.error:
        return False

    return False


def _detect_k8s_namespace() -> str:
    """检测当前 K8s namespace."""
    # 从 Service Account token 路径推断
    token_path = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
    if os.path.exists(token_path):
        try:
            with open(token_path, "r") as f:
                return f.read().strip()
        except (FileNotFoundError, PermissionError):
            pass

    # 回退：检查环境变量
    if os.getenv("SISYS_ENV"):
        env = os.getenv("SISYS_ENV", "").lower()
        return _K8S_ENV_NAMESPACES.get(env, "sisys-dev")

    # 默认 dev 环境
    return "sisys-dev"


def _is_running_in_container() -> bool:
    """检测是否在容器内运行."""
    if os.path.exists("/.dockerenv"):
        return True

    try:
        with open("/proc/1/cgroup", "rt") as f:
            content = f.read()
            if "docker" in content or "containerd" in content:
                return True
    except (FileNotFoundError, PermissionError):
        pass

    return False


def resolve_env(
    env_type: TestEnvironment | str = TestEnvironment.AUTO,
    test_tenant_id: str | None = None,
) -> TestEnvConfig:
    """解析测试环境配置.

    Args:
        env_type: 环境类型，AUTO 时自动检测
        test_tenant_id: 测试租户 ID，用于隔离。为 None 时自动生成。
    """
    import uuid

    if isinstance(env_type, str):
        env_type = TestEnvironment(env_type.lower())
    elif env_type == TestEnvironment.AUTO:
        env_type = _detect_environment()

    tenant_id = test_tenant_id or f"test_{uuid.uuid4().hex[:8]}"

    # 本地开发环境
    if env_type == TestEnvironment.LOCAL:
        return TestEnvConfig(
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_password=os.getenv("REDIS_PASSWORD"),
            postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            postgres_database=os.getenv("POSTGRES_DATABASE", "sisys"),
            postgres_username=os.getenv("POSTGRES_USERNAME", "postgres"),
            postgres_password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
            qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
            qdrant_grpc_port=int(os.getenv("QDRANT_GRPC_PORT", "6334")),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            minio_host=os.getenv("MINIO_HOST", "localhost"),
            minio_port=int(os.getenv("MINIO_API_PORT", "9000")),
            minio_console_port=int(os.getenv("MINIO_CONSOLE_PORT", "9001")),
            minio_access_key=os.getenv("MINIO_ROOT_USER"),
            minio_secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
            neo4j_host=os.getenv("NEO4J_HOST", "localhost"),
            neo4j_http_port=int(os.getenv("NEO4J_HTTP_PORT", "7474")),
            neo4j_bolt_port=int(os.getenv("NEO4J_BOLT_PORT", "7687")),
            rabbitmq_host=os.getenv("RABBITMQ_HOST", "localhost"),
            rabbitmq_port=int(os.getenv("RABBITMQ_PORT", "5672")),
            rabbitmq_mgmt_port=int(os.getenv("RABBITMQ_MGMT_PORT", "15672")),
            rabbitmq_username=os.getenv("RABBITMQ_USERNAME", "guest"),
            rabbitmq_password=os.getenv("RABBITMQ_PASSWORD", "guest"),
            env_type=env_type,
            test_tenant_id=tenant_id,
            k8s_namespace=None,
        )

    # CI 环境 (gitea-runner/docker)
    elif env_type == TestEnvironment.CI:
        return TestEnvConfig(
            redis_host=os.getenv("REDIS_HOST", "host.docker.internal"),
            redis_port=int(os.getenv("REDIS_PORT", "6380")),
            redis_password=os.getenv("REDIS_PASSWORD"),
            postgres_host=os.getenv("POSTGRES_HOST", "host.docker.internal"),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            postgres_database=os.getenv("POSTGRES_DATABASE", "sisys"),
            postgres_username=os.getenv("POSTGRES_USERNAME", "postgres"),
            postgres_password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            qdrant_host=os.getenv("QDRANT_HOST", "host.docker.internal"),
            qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
            qdrant_grpc_port=int(os.getenv("QDRANT_GRPC_PORT", "6334")),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            minio_host=os.getenv("MINIO_HOST", "host.docker.internal"),
            minio_port=int(os.getenv("MINIO_API_PORT", "9000")),
            minio_console_port=int(os.getenv("MINIO_CONSOLE_PORT", "9001")),
            minio_access_key=os.getenv("MINIO_ROOT_USER"),
            minio_secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
            neo4j_host=os.getenv("NEO4J_HOST", "host.docker.internal"),
            neo4j_http_port=int(os.getenv("NEO4J_HTTP_PORT", "7474")),
            neo4j_bolt_port=int(os.getenv("NEO4J_BOLT_PORT", "7687")),
            rabbitmq_host=os.getenv("RABBITMQ_HOST", "host.docker.internal"),
            rabbitmq_port=int(os.getenv("RABBITMQ_PORT", "5672")),
            rabbitmq_mgmt_port=int(os.getenv("RABBITMQ_MGMT_PORT", "15672")),
            rabbitmq_username=os.getenv("RABBITMQ_USERNAME", "guest"),
            rabbitmq_password=os.getenv("RABBITMQ_PASSWORD", "guest"),
            env_type=env_type,
            test_tenant_id=tenant_id,
            k8s_namespace=None,
        )

    # K8s 环境 (ArgoCD)
    elif env_type == TestEnvironment.K8S:
        k8s_namespace = _detect_k8s_namespace()

        def k8s_host(service: str) -> str:
            return f"{service}.{k8s_namespace}.svc.cluster.local"

        return TestEnvConfig(
            redis_host=os.getenv("REDIS_HOST", k8s_host("redis")),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_password=os.getenv("REDIS_PASSWORD"),
            postgres_host=os.getenv("POSTGRES_HOST", k8s_host("postgres")),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            postgres_database=os.getenv("POSTGRES_DATABASE", "sisys"),
            postgres_username=os.getenv("POSTGRES_USERNAME", "postgres"),
            postgres_password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            qdrant_host=os.getenv("QDRANT_HOST", k8s_host("qdrant")),
            qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
            qdrant_grpc_port=int(os.getenv("QDRANT_GRPC_PORT", "6334")),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            minio_host=os.getenv("MINIO_HOST", k8s_host("minio")),
            minio_port=int(os.getenv("MINIO_API_PORT", "9000")),
            minio_console_port=int(os.getenv("MINIO_CONSOLE_PORT", "9001")),
            minio_access_key=os.getenv("MINIO_ROOT_USER"),
            minio_secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
            neo4j_host=os.getenv("NEO4J_HOST", k8s_host("neo4j")),
            neo4j_http_port=int(os.getenv("NEO4J_HTTP_PORT", "7474")),
            neo4j_bolt_port=int(os.getenv("NEO4J_BOLT_PORT", "7687")),
            rabbitmq_host=os.getenv("RABBITMQ_HOST", k8s_host("rabbitmq")),
            rabbitmq_port=int(os.getenv("RABBITMQ_PORT", "5672")),
            rabbitmq_mgmt_port=int(os.getenv("RABBITMQ_MGMT_PORT", "15672")),
            rabbitmq_username=os.getenv("RABBITMQ_USERNAME", "guest"),
            rabbitmq_password=os.getenv("RABBITMQ_PASSWORD", "guest"),
            env_type=env_type,
            test_tenant_id=tenant_id,
            k8s_namespace=k8s_namespace,
        )


# 全局单例
_env_config: TestEnvConfig | None = None


def get_test_env() -> TestEnvConfig:
    """获取全局测试环境配置 (单例)."""
    global _env_config
    if _env_config is None:
        _env_config = resolve_env()
    return _env_config


def reset_test_env() -> None:
    """重置全局测试环境配置 (用于测试隔离)."""
    global _env_config
    _env_config = None
```

#### 3.2.2 创建测试专用 Docker Compose

**文件**: `deploy/app/docker-compose.test.yml`

```yaml
# =============================================================================
# SISYS 测试环境 Docker Compose
# 用于 CI/CD 和本地开发测试
# 使用: docker compose -f deploy/app/docker-compose.test.yml up -d
# =============================================================================

services:

  # ===========================================================================
  # L1: Redis 高速缓存层 (测试实例)
  # ===========================================================================
  redis-test:
    image: ${HARBOR_REGISTRY:-harbor.sisys.local}/sisys/tools/redis/redis:7.2.5
    container_name: sisys-test-redis
    restart: "no"
    ports:
      - "${TEST_REDIS_PORT:-6380}:6379"
    volumes:
      - redis_test_data:/data
    command: ["redis-server", "--appendonly", "yes"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3
    networks:
      - sisys-test

  # ===========================================================================
  # L2: PostgreSQL 关系存储层 (测试实例)
  # ===========================================================================
  postgres-test:
    image: ${HARBOR_REGISTRY:-harbor.sisys.local}/sisys/tools/postgres/postgres:15.4
    container_name: sisys-test-postgres
    restart: "no"
    ports:
      - "${TEST_POSTGRES_PORT:-5433}:5432"
    environment:
      - POSTGRES_DB=${TEST_POSTGRES_DB:-sisys_test}
      - POSTGRES_USER=${TEST_POSTGRES_USER:-test_user}
      - POSTGRES_PASSWORD=${TEST_POSTGRES_PASSWORD:-test_password}
    volumes:
      - postgres_test_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${TEST_POSTGRES_USER:-test_user}"]
      interval: 5s
      timeout: 3s
      retries: 3
    networks:
      - sisys-test

  # ===========================================================================
  # L3: Qdrant 向量存储层 (测试实例)
  # ===========================================================================
  qdrant-test:
    image: ${HARBOR_REGISTRY:-harbor.sisys.local}/sisys/tools/qdrant/qdrant:v1.7.1
    container_name: sisys-test-qdrant
    restart: "no"
    ports:
      - "${TEST_QDRANT_PORT:-6334}:6333"
      - "${TEST_QDRANT_GRPC_PORT:-6335}:6334"
    volumes:
      - qdrant_test_data:/qdrant/storage
    networks:
      - sisys-test

  # ===========================================================================
  # L4: MinIO 对象存储层 (测试实例)
  # ===========================================================================
  minio-test:
    image: minio/minio:latest
    container_name: sisys-test-minio
    restart: "no"
    command: ["server", "/data", "--console-address", ":9001"]
    ports:
      - "${TEST_MINIO_PORT:-9002}:9000"
      - "${TEST_MINIO_CONSOLE_PORT:-9003}:9001"
    environment:
      - MINIO_ROOT_USER=${TEST_MINIO_USER:-test_minio}
      - MINIO_ROOT_PASSWORD=${TEST_MINIO_PASSWORD:-test_minio_password}
    volumes:
      - minio_test_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 3s
      retries: 3
    networks:
      - sisys-test

  # ===========================================================================
  # L5: Neo4j 图存储层 (测试实例)
  # ===========================================================================
  neo4j-test:
    image: ${HARBOR_REGISTRY:-harbor.sisys.local}/sisys/tools/neo4j/neo4j:5.15
    container_name: sisys-test-neo4j
    restart: "no"
    ports:
      - "${TEST_NEO4J_HTTP_PORT:-7475}:7474"
      - "${TEST_NEO4J_BOLT_PORT:-7688}:7687"
    environment:
      - NEO4J_AUTH=${TEST_NEO4J_USER:-neo4j}/${TEST_NEO4J_PASSWORD:-test_neo4j_password}
      - NEO4J_PLUGINS=["apoc"]
    volumes:
      - neo4j_test_data:/data
    healthcheck:
      test: ["CMD", "bash", "-c", "echo > /dev/tcp/localhost/7474 || exit 1"]
      interval: 5s
      timeout: 3s
      retries: 3
    networks:
      - sisys-test

  # ===========================================================================
  # RabbitMQ 可靠事件通道 (测试实例)
  # ===========================================================================
  rabbitmq-test:
    image: ${HARBOR_REGISTRY:-harbor.sisys.local}/sisys/tools/rabbitmq/rabbitmq:3.13-management
    container_name: sisys-test-rabbitmq
    restart: "no"
    ports:
      - "${TEST_RABBITMQ_PORT:-5673}:5672"
      - "${TEST_RABBITMQ_MGMT_PORT:-15673}:15672"
    environment:
      - RABBITMQ_DEFAULT_USER=${TEST_RABBITMQ_USER:-guest}
      - RABBITMQ_DEFAULT_PASS=${TEST_RABBITMQ_PASSWORD:-guest}
      - RABBITMQ_DEFAULT_VHOST=/
    volumes:
      - rabbitmq_test_data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3
    networks:
      - sisys-test

# =============================================================================
# 网络和存储卷 (测试数据卷，与生产隔离)
# =============================================================================
networks:
  sisys-test:
    driver: bridge
    name: sisys-test-network

volumes:
  redis_test_data:
    driver: local
    name: sisys-test-redis-data
  postgres_test_data:
    driver: local
    name: sisys-test-postgres-data
  qdrant_test_data:
    driver: local
    name: sisys-test-qdrant-data
  minio_test_data:
    driver: local
    name: sisys-test-minio-data
  neo4j_test_data:
    driver: local
    name: sisys-test-neo4j-data
  rabbitmq_test_data:
    driver: local
    name: sisys-test-rabbitmq-data
```

---

### 3.3 第三阶段：建立测试隔离层 (P4, P6)

#### 3.3.1 创建测试租户隔离管理器

**文件**: `tests/isolation.py`

```python
"""测试租户隔离管理器。

为每个测试/测试类/测试会话提供独立的资源隔离。
使用 UUID 前缀确保多用户并发环境下不会冲突。
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Callable, TypeVar

import pytest

# 导入环境配置
from tests.environments import get_test_env, TestEnvConfig

T = TypeVar("T")


@dataclass
class TestTenant:
    """测试租户 - 提供隔离的资源前缀."""

    id: str  # 租户唯一标识 (UUID)，用于 seed resolve_env(test_tenant_id=...) 确保租户 ID 一致
    prefix: str  # 资源前缀 (与 id 相同，8 字符 hex UUID)

    # 队列名称
    @property
    def rabbitmq_queue_prefix(self) -> str:
        return f"test_{self.prefix}"

    @property
    def rabbitmq_exchange_prefix(self) -> str:
        return f"test_{self.prefix}_exchange"

    # Collection 名称
    def qdrant_collection(self, base_name: str) -> str:
        return f"test_{self.prefix}_{base_name}"

    # Redis key 前缀
    def redis_key_prefix(self) -> str:
        return f"test:{self.prefix}:"

    # PostgreSQL schema
    def postgres_schema(self) -> str:
        return f"test_{self.prefix}"


@dataclass
class TenantContext:
    """租户上下文 - 管理当前测试的租户资源."""

    tenant: TestTenant
    config: TestEnvConfig
    _cleanup_tasks: list[Callable[[], None]] = field(default_factory=list)

    async def cleanup(self) -> None:
        """清理租户所有资源."""
        errors: list[Exception] = []
        for cleanup_fn in self._cleanup_tasks:
            try:
                if asyncio.iscoroutinefunction(cleanup_fn):
                    await cleanup_fn()
                else:
                    cleanup_fn()
            except Exception as e:
                errors.append(e)

        self._cleanup_tasks.clear()

        if errors:
            # 至少记录所有错误，最后一个作为主异常抛出
            raise RuntimeError(
                f"Cleanup failed with {len(errors)} error(s): {[str(e) for e in errors]}"
            ) from errors[0]


# 全局租户上下文存储
# key 类型为 int：asyncio.current_task().ident 返回 int
_tenant_contexts: dict[int, TenantContext] = {}


def _get_task_id() -> int:
    """获取当前 asyncio task 的唯一标识符.

    注意：不再使用 id(task) 作为 fallback，因为 id(None) 在同一进程内
    始终返回相同地址，多 worker 进程场景下会导致 key 碰撞。
    若 task.ident 为 None，使用 uuid.uuid4().int 生成随机 key。
    """
    task = asyncio.current_task()
    task_id = task.ident if task else None
    if task_id is None:
        # ✅ S1: 使用 uuid 替代 id(task)，避免跨 pytest-xdist worker 进程碰撞
        return uuid.uuid4().int
    return task_id


def generate_test_tenant() -> TestTenant:
    """生成测试租户.

    使用 8 字符 hex UUID，提供约 4.3 billion (16^8) 个可能性。
    并行度限制：
    - 100 并行：碰撞概率 ~0.001%
    - 1000 并行：碰撞概率 ~0.12%
    - 建议并行度 ≤4，碰撞概率可忽略
    """
    tenant_id = uuid.uuid4().hex[:8]
    return TestTenant(
        id=tenant_id,
        prefix=tenant_id,
    )


@asynccontextmanager
async def tenant_context(
    tenant: TestTenant | None = None,
    env_config: TestEnvConfig | None = None,
):
    """创建租户上下文字典管理器."""
    if tenant is None:
        tenant = generate_test_tenant()
    if env_config is None:
        env_config = get_test_env()

    context = TenantContext(tenant=tenant, config=env_config)
    task_id = _get_task_id()
    _tenant_contexts[task_id] = context

    try:
        yield context
    finally:
        await context.cleanup()
        if task_id in _tenant_contexts:
            del _tenant_contexts[task_id]


# Pytest 集成
@pytest.fixture
def test_tenant() -> TestTenant:
    """Pytest fixture: 为每个测试生成独立租户."""
    return generate_test_tenant()


@pytest.fixture
async def isolated_tenant_context(test_tenant: TestTenant) -> TenantContext:
    """Pytest fixture: 创建隔离的租户上下文 (async).

    自动清理资源。

    ✅ T2: 使用 resolve_env(test_tenant_id=test_tenant.id) 确保 config.test_tenant_id
    与 tenant.prefix 一致，与 tenant_context fixture 行为对齐。
    """
    from tests.environments import resolve_env

    # ✅ 复用 test_tenant 的 ID，确保 config.test_tenant_id 与 tenant.prefix 一致
    config = resolve_env(test_tenant_id=test_tenant.id)
    context = TenantContext(tenant=test_tenant, config=config)

    task_id = _get_task_id()
    _tenant_contexts[task_id] = context

    yield context

    await context.cleanup()
    if task_id in _tenant_contexts:
        del _tenant_contexts[task_id]


# 租户感知适配器 - 用于替换真实服务为测试租户隔离版本
class TenantAwareMock:
    """租户感知的资源名称包装器.

    自动为所有资源名称添加租户前缀，无任何 mock 行为。
    """

    def __init__(self, tenant: TestTenant):
        self.tenant = tenant

    def wrap_queue_name(self, base_queue: str) -> str:
        """包装队列名."""
        return f"{self.tenant.rabbitmq_queue_prefix}_{base_queue}"

    def wrap_collection_name(self, base_collection: str) -> str:
        """包装 Collection 名."""
        return self.tenant.qdrant_collection(base_collection)

    def wrap_redis_key(self, base_key: str) -> str:
        """包装 Redis key."""
        return f"{self.tenant.redis_key_prefix()}{base_key}"

    def wrap_postgres_schema(self, base_table: str) -> str:
        """包装 PostgreSQL 表名 (使用 schema.table 格式)."""
        schema = self.tenant.postgres_schema()
        return f'"{schema}".{base_table}'
```

#### 3.3.2 创建资源清理 Fixture

**文件**: `tests/fixtures.py`

```python
"""测试资源清理 Fixtures.

提供自动清理机制，确保每个测试后资源被正确释放。
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest

from tests.environments import TestEnvConfig, get_test_env
from tests.isolation import (
    TenantContext,
    generate_test_tenant,
    isolated_tenant_context,
)


# ===================================================================
# 环境配置 Fixtures
# ===================================================================


@pytest.fixture(scope="session")
def test_env_config() -> TestEnvConfig:
    """Session 级测试环境配置 (整个测试会话复用)."""
    return get_test_env()


@pytest.fixture(scope="function")
def fresh_test_env_config() -> TestEnvConfig:
    """Function 级测试环境配置 (每个测试独立)."""
    from tests.environments import resolve_env
    return resolve_env()


# ===================================================================
# 租户隔离 Fixtures
# ===================================================================


@pytest.fixture(scope="function")
def isolated_tenant() -> "TestTenant":
    """Function 级隔离租户.

    每个测试函数获得唯一租户 ID。
    """
    return generate_test_tenant()


@pytest.fixture(scope="function")
async def tenant_context(
    isolated_tenant: "TestTenant",
) -> AsyncGenerator[TenantContext, None]:
    """Async context manager 提供隔离的租户上下文.

    测试结束后自动清理资源。

    ✅ 修复 #C: resolve_env() 复用 isolated_tenant.id，确保租户 ID 一致
    """
    from tests.environments import resolve_env
    from tests.isolation import TenantContext

    # ✅ 复用 isolated_tenant 的 ID，确保与租户前缀一致
    config = resolve_env(test_tenant_id=isolated_tenant.id)

    context = TenantContext(
        tenant=isolated_tenant,
        config=config,
    )

    yield context

    # 清理资源
    await _cleanup_tenant_resources(context, fresh_test_env_config)


async def _cleanup_tenant_resources(
    context: TenantContext,
    config: TestEnvConfig,
) -> None:
    """清理租户相关资源.

    注意：
    - 清理失败使用 logging.error() 记录，不阻断测试
    - 真正的资源泄漏风险由 setup 时清理和定期 CI 清理兜底
    """
    tenant = context.tenant
    cleanup_errors: list[str] = []

    # 清理 RabbitMQ 队列
    # ✅ 修复 #1: 使用 Management HTTP API 列出并删除匹配队列
    try:
        import aiohttp
        import urllib.parse

        mgmt_host = config.rabbitmq_host
        mgmt_port = config.rabbitmq_mgmt_port
        mgmt_user = config.rabbitmq_username
        mgmt_pass = config.rabbitmq_password
        base_url = f"http://{mgmt_host}:{mgmt_port}/api"

        auth = aiohttp.BasicAuth(
            mgmt_user if mgmt_user else "guest",
            mgmt_pass if mgmt_pass else "guest",
        )
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(auth=auth, timeout=timeout) as session:
            # GET /api/queues - 列出所有队列
            async with session.get(f"{base_url}/queues") as resp:
                if resp.status == 200:
                    queues = await resp.json()
                    for q in queues:
                        # 匹配测试租户前缀的队列: test_{prefix}_*
                        if q.get("name", "").startswith(f"test_{tenant.prefix}_"):
                            vhost = urllib.parse.quote(q.get("vhost", "/"), safe="")
                            qname = urllib.parse.quote(q["name"], safe="")
                            async with session.delete(
                                f"{base_url}/queues/{vhost}/{qname}"
                            ) as del_resp:
                                if del_resp.status == 204:
                                    print(f"RabbitMQ: deleted queue {q['name']}")
                                else:
                                    cleanup_errors.append(
                                        f"RabbitMQ delete queue {q['name']} failed: {del_resp.status}"
                                    )
                elif resp.status == 401:
                    cleanup_errors.append(
                        f"RabbitMQ management API auth failed (check RABBITMQ_USERNAME/PASSWORD)"
                    )
                else:
                    cleanup_errors.append(
                        f"RabbitMQ management API returned {resp.status}"
                    )
    except aiohttp.ClientError as e:
        # Management API 不可用时跳过，不算 cleanup error
        print(f"RabbitMQ management API unavailable ({e}), skipping queue cleanup")
    except Exception as e:
        cleanup_errors.append(f"RabbitMQ cleanup error: {e}")

    # 清理 Qdrant Collections
    # ✅ 修复 #H/#N4: 使用与 QdrantManager._create_client() 一致的参数
    try:
        from qdrant_client import AsyncQdrantClient

        client = AsyncQdrantClient(
            host=config.qdrant_host,
            port=config.qdrant_port,
            grpc_port=config.qdrant_grpc_port,
            api_key=config.qdrant_api_key,
            https=False,
            prefer_grpc=False,
        )

        collections = await client.get_collections()
        for col in collections.collections:
            if col.name.startswith(f"test_{tenant.prefix}_"):
                try:
                    await client.delete_collection(col.name)
                except Exception as e:
                    cleanup_errors.append(f"Qdrant delete collection {col.name} error: {e}")

        await client.close()
    except Exception as e:
        cleanup_errors.append(f"Qdrant cleanup error: {e}")

    # 清理 Redis keys
    try:
        import redis.asyncio as redis

        r = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            password=config.redis_password,
            decode_responses=True,
        )

        pattern = f"test:{tenant.prefix}:*"
        cursor = 0
        deleted_count = 0
        while True:
            cursor, keys = await r.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                deleted_count += len(keys)
                await r.delete(*keys)
            if cursor == 0:
                break

        await r.close()
        if deleted_count > 0:
            print(f"Redis: deleted {deleted_count} keys matching {pattern}")
    except Exception as e:
        cleanup_errors.append(f"Redis cleanup error: {e}")

    # 清理 MinIO buckets
    # ✅ 修复 #N2/#R2/#R5: 修正 async iteration + 处理 versioned + incomplete uploads
    try:
        from minio import AsyncMinio
        from minio.error import S3Error

        minio_client = AsyncMinio(
            endpoint=f"{config.minio_host}:{config.minio_port}",
            access_key=config.minio_access_key or "minioadmin",
            secret_key=config.minio_secret_key or "minioadmin",
            secure=False,
        )

        # 列出所有 buckets，删除匹配测试租户前缀的
        buckets = await minio_client.list_buckets()
        for bucket in buckets:
            if bucket.name.startswith(f"test-{tenant.prefix}-"):
                try:
                    # 删除所有对象（包括 versioned 和普通对象）
                    # ✅ R2: async for 迭代 list_objects（异步生成器）
                    async for obj in minio_client.list_objects(bucket.name, recursive=True):
                        await minio_client.remove_object(bucket.name, obj.object_name)
                    # ✅ R5: 处理未完成的分段上传
                    async for upload in minio_client.list_incomplete_uploads(bucket.name, recursive=True):
                        await minio_client.abort_multipart_upload(
                            bucket.name, upload.object_name, upload.upload_id
                        )
                    # 再删除空 bucket
                    await minio_client.remove_bucket(bucket.name)
                    print(f"MinIO: deleted bucket {bucket.name}")
                except S3Error as e:
                    cleanup_errors.append(f"MinIO delete bucket {bucket.name} error: {e}")

        await minio_client.close()
    except Exception as e:
        cleanup_errors.append(f"MinIO cleanup error: {e}")

    # 清理 Neo4j graphs
    # ✅ 修复 #N1: 添加 Neo4j graph 清理（通过 HTTP API /db/neo4j/tx/commit）
    try:
        import aiohttp

        neo4j_http_url = f"http://{config.neo4j_host}:{config.neo4j_http_port}"
        auth = aiohttp.BasicAuth(
            config.neo4j_username or "neo4j",
            config.neo4j_password or "password123",
        )
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(auth=auth, timeout=timeout) as session:
            # ✅ R6: 必须检查 test_tenant 属性存在，否则 null = 'value' 返回 null 而非 false
            # 会导致所有节点被误删！
            cypher = (
                f"MATCH (n) "
                f"WHERE n.test_tenant IS NOT NULL AND n.test_tenant = 'test_{tenant.prefix}' "
                f"DETACH DELETE n"
            )
            async with session.post(
                f"{neo4j_http_url}/db/neo4j/tx/commit",
                json={"statements": [{"statement": cypher}]},
            ) as resp:
                if resp.status in (200, 201):
                    result = await resp.json()
                    # ✅ R3/D3: Neo4j 5.x HTTP API — summary 在顶层，不在 results[0] 内
                    # 响应结构: {"results": [...], "errors": [], "summary": {"counters": {...}}}
                    # D3: Neo4j 可能返回 200 但同时有 application-level 错误
                    errors = result.get("errors", [])
                    if errors:
                        cleanup_errors.append(
                            f"Neo4j Cypher errors: {[e.get('message', str(e)) for e in errors]}"
                        )
                        # 有错误时跳过数据删除（已通过错误日志记录）
                        pass
                    else:
                        summary = result.get("summary", {})
                        counters = summary.get("counters", {})
                        deleted_nodes = counters.get("nodesDeleted", 0)
                        deleted_rels = counters.get("relationshipsDeleted", 0)
                        if deleted_nodes > 0 or deleted_rels > 0:
                            print(f"Neo4j: deleted {deleted_nodes} nodes, {deleted_rels} rels")
                elif resp.status == 401:
                    cleanup_errors.append("Neo4j auth failed (check NEO4J_USERNAME/PASSWORD)")
                elif resp.status == 404:
                    print(f"Neo4j: database 'neo4j' not found, skipping graph cleanup")
                else:
                    cleanup_errors.append(f"Neo4j cleanup POST returned {resp.status}")
    except aiohttp.ClientError as e:
        print(f"Neo4j HTTP API unavailable ({e}), skipping graph cleanup")
    except Exception as e:
        cleanup_errors.append(f"Neo4j cleanup error: {e}")

    # 清理 PostgreSQL schema
    # ✅ S3: 使用 async with 确保连接无论是否异常都正确释放
    try:
        import asyncpg

        async with asyncpg.create_pool(
            host=config.postgres_host,
            port=config.postgres_port,
            database=config.postgres_database or "sisys",
            user=config.postgres_username if config.postgres_username else "postgres",
            password=config.postgres_password if config.postgres_password is not None else "postgres",
            min_size=1,
            max_size=1,
        ) as pool:
            schema_name = f"test_{tenant.prefix}"
            try:
                async with pool.acquire() as conn:
                    await conn.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
            except Exception as e:
                cleanup_errors.append(f"PostgreSQL drop schema error: {e}")
    except Exception as e:
        cleanup_errors.append(f"PostgreSQL cleanup error: {e}")

    # ✅ S5: 清理失败应记录 error 而非 warning（资源泄漏风险）
    # 注意：pytest.skip() 在 fixture teardown 中无效，会跳过下一个测试而非当前测试
    if len(cleanup_errors) > 0:
        error_msg = f"Tenant cleanup had {len(cleanup_errors)} error(s): {'; '.join(cleanup_errors)}"
        print(error_msg)
        import logging
        logging.error(error_msg)


# ===================================================================
# 事件循环 Fixtures (修复 module scope 问题)
# ===================================================================


# 注意：pytest-asyncio 使用 auto mode，不要手动创建 event_loop fixture


# ===================================================================
# 测试前/后钩子
# ===================================================================

# ✅ 修复 #7: 添加 setup 时清理机制，降低中途失败时脏数据累积风险


@pytest.fixture(scope="session", autouse=True)
async def cleanup_old_test_resources():
    """Session 级清理：测试会话开始前清理旧的 test_* 资源.

    这是一个兜底机制，用于处理：
    1. 测试中途失败导致 teardown 未执行的情况
    2. 历史遗留的脏数据
    3. 上次 CI 运行未清理的资源

    注意：
    - session 级的 async fixture 由 pytest-asyncio 管理 event loop
    - setup 时清理的是"上一次 CI 运行的脏数据"
    - 当前会话的租户在 fixture 执行时才创建，不受影响
    """
    from tests.environments import get_test_env

    config = get_test_env()
    import redis.asyncio as redis

    try:
        r = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            password=config.redis_password,
            decode_responses=True,
        )

        # ✅ 修复 #A: 真正删除所有 test:* keys
        # session 开始时清理上一次运行的脏数据
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = await r.scan(cursor=cursor, match="test:*", count=100)
            if keys:
                deleted += len(keys)
                await r.delete(*keys)
            if cursor == 0:
                break

        await r.close()
        if deleted > 0:
            print(f"Setup cleanup: deleted {deleted} legacy test keys")
    except Exception as e:
        print(f"Setup cleanup warning: {e}")

    yield  # session 级 fixture，yield 后不执行 teardown


@pytest.fixture(autouse=True)
def reset_test_environment():
    """自动重置测试环境.

    每个测试函数执行前后重置全局状态。
    """
    from tests.environments import reset_test_env

    # 测试前
    reset_test_env()

    yield

    # 测试后
    reset_test_env()
```

---

## 四、详细实施计划 (Checklist)

---

### Phase 1: 紧急修复 (P1, P2, P6) — 预计 1-2 天

#### P1: 修复 `async_consume()` 永久阻塞

- [ ] **1.1** 在 `test_acceptance_event_bus_implementation.py` 中创建 `temporary_consumer` 异步上下文管理器
  - 使用 `asyncio.create_task()` 后台运行 consumer，不阻塞
  - 包含 setup/cleanup 顺序正确
  - 参考实现：文档 3.1.1 节

- [ ] **1.2** 重构 `verify_rabbitmq_consumer_receives` step 函数
  - 将 `event_loop.run_until_complete()` 调用改为使用 async context manager
  - 验证 consumer 能正确接收事件

- [ ] **1.3** 验证修复：本地运行 `test_ac2_rabbitmq_documentprocessed`
  ```bash
  poetry run pytest tests/acceptance/test_acceptance_event_bus_implementation.py::test_ac2_rabbitmq_documentprocessed -v
  ```

- [ ] **1.4** 验证修复：CI 环境运行相同测试
  ```bash
  git push && 观察 CI logs
  ```

#### P2: 修复 `collection_has_different_domains` 缺少 create_collection

- [ ] **2.1** 在 `test_acceptance_qdrant_vector_layer.py` 的 `collection_has_different_domains` 中添加 collection 创建
  - 调用 `collection_manager.create_collection()` 先于 `upsert_points()`
  - 处理 collection 已存在的异常（ignore if exists）

- [ ] **2.2** 验证修复：本地运行 `test_dense_search_with_filter`
  ```bash
  poetry run pytest tests/acceptance/test_acceptance_qdrant_vector_layer.py::test_dense_search_with_filter -v
  ```

#### P6: 修复 event_loop scope 问题

> ⚠️ **核心问题**：`scope=module` 的 `event_loop` fixture 会导致多个测试函数共享同一个事件循环，造成状态污染。这与 pytest-asyncio 的 `asyncio_mode = "auto"` 模式冲突。

- [ ] **3.1** 检查 `tests/acceptance/` 下所有 fixtures 的 scope
  - 确认 `rabbitmq_publisher`, `rabbitmq_consumer` 等为 `scope=function`（非 module/session）
  - **如果存在 `scope=module` 的 `event_loop` fixture，必须删除**

- [ ] **3.2** ⚠️ **不要创建 `event_loop` fixture** — `pyproject.toml` 已配置 `asyncio_mode = "auto"`，pytest-asyncio 会自动管理 event loop
  - pytest-asyncio auto mode 会为每个测试函数自动创建和清理 event loop
  - 手动创建 `event_loop` fixture 会与 pytest-asyncio 冲突，导致 `RuntimeError: Event loop is running`

- [ ] **3.3** 修复现有 event_loop fixture（如存在）

  **错误示例（必须删除）：**
  ```python
  # ❌ 错误：scope=module 导致状态污染
  @pytest.fixture(scope="module")
  def event_loop():
      loop = asyncio.new_event_loop()
      yield loop
      loop.close()
  ```

  **正确做法：删除 event_loop fixture，让 pytest-asyncio 自动管理：**
  ```python
  # ✅ 正确：不定义 event_loop fixture，使用 pytest-asyncio auto mode
  # 在 pyproject.toml 中配置：
  # [tool.pytest.ini_options]
  # asyncio_mode = "auto"
  ```

- [ ] **3.4** 验证：无状态污染，运行多次同一测试
  ```bash
  poetry run pytest tests/acceptance/test_acceptance_event_bus_implementation.py -v --count 3
  ```

**P6 修复验证清单：**
- [ ] `tests/acceptance/test_acceptance_event_bus_implementation.py` 中无 `event_loop` fixture
- [ ] `tests/acceptance/test_acceptance_qdrant_vector_layer.py` 中无 `event_loop` fixture
- [ ] 所有 async fixtures 使用 `async def` 而非手动管理事件循环

---

### Phase 2: 环境标准化 (P3, P5) — 预计 2-3 天

#### P3: 实现 `tests/environments.py`

- [ ] **4.1** 创建 `tests/environments.py` 文件
  - 实现 `TestEnvironment` 枚举（LOCAL / CI / K8S / AUTO）
  - 实现 `_is_running_in_k8s()` 检测函数
  - 实现 `_is_running_in_container()` 检测函数
  - 实现 `resolve_env()` 主函数

- [ ] **4.2** 实现 `TestEnvConfig` 数据类
  - 包含所有服务 host/port 配置
  - 包含 `k8s_namespace` 字段
  - 实现 `get_k8s_service_dns()` 方法

- [ ] **4.3** 实现自动环境检测逻辑（优先级从高到低）
  1. 环境变量 `SISYS_TEST_ENV` 显式指定（最高优先级）
  2. K8s Service Account token 检测
  3. CI 环境变量 (`CI=true` 或 `GITEA_RUNNER=true`)
  4. 容器内运行检测 (`/.dockerenv` 或 cgroup)
  5. 默认本地开发环境 LOCAL

- [ ] **4.4** 创建全局单例 `get_test_env()` 和 `reset_test_env()`

- [ ] **4.5** 更新 `tests/integration/conftest.py` 使用 `environments.py`
  ```python
  from tests.environments import get_test_env
  config = get_test_env()
  ```

#### P5: 创建 `deploy/app/docker-compose.test.yml`

- [ ] **5.1** 创建测试专用 docker-compose 文件
  - 复制 `docker-compose.yml` 作为基础
  - 修改端口为测试专用端口（6380/5433/6334...）
  - 添加 `TEST_` 前缀的环境变量

- [ ] **5.2** 更新 CI workflow (`.gitea/workflows/ci.yaml`)
  - ⚠️ **不要使用 `export HOST=host.docker.internal`** 覆盖已有环境变量
  - 正确做法：设置 `SISYS_TEST_ENV=ci`，让 `environments.py` 自动检测
  - 移除 `docker-compose.yml` 改用 `docker-compose.test.yml`，或传递 `TEST_*` 端口变量

- [ ] **5.3** 验证：本地启动测试环境
  ```bash
  docker compose -f deploy/app/docker-compose.test.yml up -d
  docker compose -f deploy/app/docker-compose.test.yml ps
  ```

- [ ] **5.4** 验证：测试连接到测试环境
  ```bash
  export SISYS_TEST_ENV=local
  poetry run pytest tests/integration/ -v
  ```

---

### Phase 3: 测试隔离 (P4) — 预计 3-4 天

#### P4: 实现 `tests/isolation.py`

- [ ] **6.1** 创建 `tests/isolation.py` 文件
  - 实现 `TestTenant` 数据类（id, prefix）
  - 实现 `TenantContext` 上下文管理器

- [ ] **6.2** 实现资源隔离方法
  - `rabbitmq_queue_prefix`
  - `qdrant_collection(base_name)`
  - `redis_key_prefix()`
  - `postgres_schema()`

- [ ] **6.3** 实现 `tenant_context` 异步上下文管理器
  - ⚠️ **必须使用 `asyncio.current_task().ident`** 作为 context key
  - ❌ 不要使用 `threading.current_thread().ident`（异步环境中无效）

- [ ] **6.4** 创建 pytest fixtures
  - `test_tenant` fixture
  - `isolated_tenant_context` fixture

- [ ] **6.5** 创建 `TenantAwareMock` 类
  - 自动为资源添加租户前缀

#### P4: 实现 `tests/fixtures.py`

- [ ] **7.1** 创建 `tests/fixtures.py` 文件
  - 实现 `test_env_config` (session scope)
  - 实现 `fresh_test_env_config` (function scope)

- [ ] **7.2** 实现租户清理 fixtures
  - `isolated_tenant` (function scope)
  - `tenant_context` (async context manager)

- [ ] **7.3** 实现资源清理函数 `_cleanup_tenant_resources()`
  - 清理 RabbitMQ 队列
  - 清理 Qdrant collections
  - 清理 Redis keys
  - 清理 PostgreSQL schema

- [ ] **7.4** 添加 `autouse=True` 的 `reset_test_environment` fixture

- [ ] **7.5** 更新 `tests/acceptance/test_acceptance_event_bus_implementation.py` 使用租户隔离
  - 为队列名添加租户前缀
  - 为 Redis keys 添加租户前缀

- [ ] **7.6** 更新 `tests/acceptance/test_acceptance_qdrant_vector_layer.py` 使用租户隔离
  - 为 collection 名称添加租户前缀

- [ ] **7.7** 验证：并发运行测试无冲突
  - ⚠️ **注意**：pytest-xdist `-n 4` 有两种并行模式：
    1. **多进程模式**（默认，`--dist loadscope`）：每个 worker 是独立进程，天然进程级隔离
    2. **线程模式**（`--dist loadscope --forked`）：同一进程内多线程，**不推荐**，需额外同步
  - **本方案使用多进程模式**，每个 worker 进程有独立内存空间
  - `asyncio.current_task().ident` 用于**同一进程内**区分不同 async context
  - 租户 ID（UUID 前缀）用于**全局**资源隔离，避免不同 worker 间冲突
  - 建议并行度 `-n 4` 而非更高，避免资源竞争
  ```bash
  poetry run pytest tests/acceptance/ -v -n 4
  ```

**多进程租户隔离原理：**

```
Worker 进程 A                         Worker 进程 B
┌─────────────────────────────┐     ┌─────────────────────────────┐
│ asyncio.current_task().ident │     │ asyncio.current_task().ident │
│         = 1                  │     │         = 1                  │
│                             │     │                             │
│ _tenant_contexts[1]         │     │ _tenant_contexts[1]         │
│   → TenantContext_A         │     │   → TenantContext_B         │
│                             │     │                             │
│ 队列名: test_abc123_queue  │     │ 队列名: test_def456_queue  │
│ (进程 A 独有，不会冲突)      │     │ (进程 B 独有，不会冲突)      │
└─────────────────────────────┘     └─────────────────────────────┘
```

**关键理解**：
- 不同 worker 进程间**天然隔离**（独立内存）
- 同一 worker 进程内通过 `task.ident` 区分 context
- 全局资源（队列名、collection 名）通过 UUID 前缀隔离
- **`asyncio.current_task().ident` 不跨进程**，所以不存在 ident 冲突问题

---

### Phase 4: 验证与优化 — 预计 2-3 天

#### 验证

- [ ] **8.1** 运行完整验收测试套件（本地）
  ```bash
  poetry run pytest tests/acceptance/ -v --tb=short
  ```

- [ ] **8.2** 运行完整验收测试套件（CI）
  ```bash
  git push && 等待 CI pipeline 完成
  ```

- [ ] **8.3** 验证所有 3 个之前失败的测试现在通过
  - [ ] `test_ac2_rabbitmq_agentdecided`
  - [ ] `test_ac2_rabbitmq_documentprocessed`
  - [ ] `test_dense_search_with_filter`

- [ ] **8.4** 架构约束验证测试通过
  ```bash
  poetry run pytest tests/acceptance/test_acceptance_event_bus_implementation.py::test_ac6_architecture_constraints -v
  ```

#### 优化

- [ ] **9.1** 检查测试运行时间，优化慢速测试
  - 减少不必要的 `asyncio.sleep()` 等待
  - 优化 collection 创建（if not exists）

- [ ] **9.2** 更新覆盖率门禁（如需要）
  - 确认 coverage report 生成正确

#### 文档更新

- [ ] **10.1** 更新 README 或相关文档
  - 说明新的测试环境变量
  - 说明租户隔离机制

- [ ] **10.2** 更新 CI README（如果存在）
  - 说明 CI 测试环境配置

---

### Phase 5: tests/acceptance/ 重构清单

**现状**：12 个 BDD 验收测试文件，使用真实服务（RabbitMQ/Redis/Qdrant 等）

| 序号 | 检查项 | 影响测试 |
|------|--------|---------|
| **A1** | 检查所有 fixtures 是否为 `scope=function`（非 module/session） | 全部 12 个 |
| **A2** | `test_acceptance_event_bus_implementation.py` 修复 `async_consume()` 阻塞问题 | Story 1.3 |
| **A3** | `test_acceptance_qdrant_vector_layer.py` 修复 `collection_has_different_domains` 缺少 create_collection | Story 1.6 |
| **A4** | 为所有队列名添加租户前缀 `test_{uuid}_queue` | 全部 12 个 |
| **A5** | 为所有 Redis keys 添加租户前缀 `test:{uuid}:` | 全部 12 个 |
| **A6** | 为所有 Qdrant collections 添加租户前缀 `test_{uuid}_` | 全部 12 个 |
| **A7** | 检查 pytest-asyncio `asyncio_mode = "auto"` 配置 | 全部 12 个 |
| **A8** | 添加 `autouse=True` 的 `reset_test_environment` fixture | 全部 12 个 |
| **A9** | 确保 `temporary_consumer` 使用独立队列名（UUID） | Story 1.3 |
| **A10** | 检查并行执行 (`-n 4`) 时消费者隔离 | 全部 12 个 |

**详细文件分析**：

| 文件 | step 函数数 | 主要服务依赖 | 需隔离资源 |
|------|------------|------------|-----------|
| `test_acceptance_hexagonal_architecture_skeleton.py` | 104 | Redis | channels/keys |
| `test_acceptance_domain_event_definition.py` | 111 | Redis, PostgreSQL | keys, schemas |
| `test_acceptance_event_bus_implementation.py` | 103 | RabbitMQ, Redis | queues, keys | ← P1 修复 |
| `test_acceptance_redis_cache_layer.py` | 109 | PostgreSQL, Redis | schemas, keys |
| `test_acceptance_postgresql_relational_layer.py` | 149 | Neo4j, Redis | graphs, keys |
| `test_acceptance_qdrant_vector_layer.py` | 67 | Qdrant | collections | ← P2 修复 |
| `test_acceptance_minio_object_layer.py` | 83 | RabbitMQ | queues, exchanges |
| `test_acceptance_neo4j_graph_layer.py` | 88 | RabbitMQ | queues, exchanges |
| `test_acceptance_rbac_permission_management.py` | 238 | Neo4j, PostgreSQL | graphs, schemas |
| `test_acceptance_unified_audit_log.py` | 190 | PostgreSQL, MinIO | schemas, buckets |
| `test_acceptance_data_sovereignty_isolation.py` | 371 | PostgreSQL, Redis | schemas, keys |
| `test_acceptance_k8s_auto_scaling.py` | 80 | PostgreSQL, Neo4j | schemas, graphs |

---

### Phase 6: tests/integration/ 重构清单

**现状**：15 个集成测试文件，使用 fakeredis mock

| 序号 | 检查项 | 影响测试 |
|------|--------|---------|
| **I1** | 确认使用 `fakeredis` 而非真实 Redis | 全部 15 个 |
| **I2** | 确认 fixtures 为 `scope=function` | 全部 15 个 |
| **I3** | 检查 PostgreSQL mock 是否正确 | 全部 15 个 |
| **I4** | 添加 `autouse=True` 的 `reset_test_environment` fixture | 全部 15 个 |
| **I5** | 验证 `mock_redis` 每个测试后清理 | 全部 15 个 |
| **I6** | 检查 `in_memory_store` 状态隔离 | Event 相关测试 |
| **I7** | 确认 IdempotencyChecker mock 正确 | Event 相关测试 |
| **I8** | 检查 `RetryPolicy` 测试参数 | Retry 相关测试 |

**注意**：`tests/integration/` 使用 mock，**不需要**租户隔离，因为没有真实资源竞争。但需要确保：
- fakeredis 实例每个测试独立
- `InMemoryEventStore` 每个测试独立
- `InMemoryOutboxRepository` 每个测试独立

---

### Phase 7: tests/integration/ 重构清单

**现状**：6 个真实服务集成测试文件

| 序号 | 检查项 | 影响测试 |
|------|--------|---------|
| **R1** | 更新 `conftest.py` 使用 `tests/environments.py` | 全部 6 个 |
| **R2** | 检查 `scope=session` 的连接池是否需要改为 function | 全部 6 个 |
| **R3** | 添加资源清理 (collection/queue/key cleanup) | 全部 6 个 |
| **R4** | 为 `real_qdrant_client` 添加 collection 前缀 | Qdrant 相关 |
| **R5** | 为 `real_redis_pool` 添加 key 前缀 | Redis 相关 |
| **R6** | 检查 PostgreSQL schema 清理 | PG 相关 |
| **R7** | 验证连接配置使用 `get_test_env()` | 全部 6 个 |

**文件列表**：

| 文件 | 服务依赖 | 需隔离资源 |
|------|---------|-----------|
| `test_integration_redis_real.py` | Redis | keys |
| `test_integration_postgresql_real.py` | PostgreSQL | schemas |
| `test_integration_qdrant_real.py` | Qdrant | collections |
| `test_integration_minio_real.py` | MinIO | buckets |
| `test_integration_neo4j_real.py` | Neo4j | graphs |
| `conftest.py` | All | 连接配置 |

---

### Phase 8: tests/unit/ 重构清单

**现状**：70 个单元测试文件，分布在 7 个子目录

| 序号 | 检查项 | 影响测试 |
|------|--------|---------|
| **U1** | 确认使用 mock 而非真实服务 | 全部 70 个 |
| **U2** | 检查 fixture scope 是否正确 | 全部 70 个 |
| **U3** | 验证 mock 清理（每个测试后） | 全部 70 个 |
| **U4** | 检查是否有泄露到真实服务的情况 | 全部 70 个 |
| **U5** | 确认 async mock 使用 `AsyncMock` | async 测试 |
| **U6** | 检查 pytest.mark 标记使用 | 全部 70 个 |

**子目录分析**：

| 子目录 | 文件数 | 测试对象 | Mock 策略 |
|--------|--------|---------|----------|
| `application/` | ? | 应用服务 | AsyncMock |
| `architecture/` | ? | 架构约束 | 无 mock |
| `domain/` | ? | 领域模型 | 无 mock |
| `infrastructure/` | ? | 基础设施 | Mock 服务 |
| `interfaces/` | ? | 接口层 | AsyncMock |
| `quality/` | ? | 质量指标 | 无 mock |
| `security/` | ? | 安全模块 | Mock 加密 |
| `shared/` | ? | 共享工具 | 无 mock |

---

### 重构优先级排序

```
优先级 1 (紧急 - 阻塞性问题):
├── A2: test_acceptance_event-bus-implementation async_consume 修复
├── A3: test_acceptance_qdrant-vector-layer collection 创建修复
└── A1: acceptance fixtures scope 修正

优先级 2 (高 - 隔离性问题):
├── A4-A6: acceptance 租户隔离添加
├── R1-R3: integration 环境标准化
└── R4-R7: integration 资源隔离

优先级 3 (中 - 优化项):
├── A7-A10: acceptance 配置优化
├── I1-I8: integration mock 验证
└── U1-U6: unit 测试检查

优先级 4 (低 - 文档/清理):
├── U5-U6: unit 标记检查
└── 文档更新
```

### 风险评估

| 测试目录 | 改动范围 | 风险等级 | 预计工时 |
|----------|---------|---------|----------|
| `tests/acceptance/` | 大（12 个文件，~1500 行代码） | 🔴 高 | 3-4 天 |
| `tests/integration/` | 小（mock 验证为主） | 🟡 中 | 0.5 天 |
| `tests/integration/` | 中（6 个文件，连接配置） | 🟡 中 | 1-2 天 |
| `tests/unit/` | 小（70 个文件，但大部分已隔离） | 🟢 低 | 0.5 天 |

---

### 执行顺序建议

```
Step 1: 修复 tests/acceptance/ 的 P1/P2 问题 (A2, A3)
        ↓
Step 2: 建立 tests/environments.py (Phase 2)
        ↓
Step 3: 建立 tests/isolation.py + tests/fixtures.py (Phase 3)
        ↓
Step 4: 应用租户隔离到 acceptance/ (A4-A6)
        ↓
Step 5: 更新 integration/conftest.py (R1-R3)
        ↓
Step 6: 验证 integration/ mock 正确性 (I1-I8)
        ↓
Step 7: unit 测试检查 (U1-U6)
        ↓
Step 8: 完整回归测试
```

---

## 五、预期效果

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 测试通过率 (本地) | ~99% (1/2179 失败) | 100% |
| 测试通过率 (CI) | ~99.7% (1/375 失败) | 100% |
| 测试隔离性 | 无隔离 | 租户级隔离 |
| 环境适应性 | 硬编码 localhost | 自动环境检测 |
| 多用户并发安全 | 可能冲突 | 租户隔离保证 |

---

## 六、关键文件清单

```
tests/
├── environments.py          # [新建] 测试环境配置解析
├── isolation.py              # [新建] 测试租户隔离管理
├── fixtures.py              # [新建] 测试资源清理 fixtures
├── conftest.py              # [更新] 添加隔离 fixtures
└── acceptance/
    ├── test_acceptance_event_bus_implementation.py  # [更新] 修复 async_consume 问题
    └── test_acceptance_qdrant_vector_layer.py  # [更新] 修复 collection 创建问题

deploy/app/
└── docker-compose.test.yml  # [新建] 测试专用 docker-compose

.gitea/workflows/
└── ci.yaml                  # [更新] 使用测试专用环境
```

---

## 七、验证方案

### 7.1 本地验证

```bash
# 1. 启动测试环境
docker compose -f deploy/app/docker-compose.test.yml up -d

# 2. 运行验收测试
export SISYS_TEST_ENV=local
poetry run pytest tests/acceptance -v --tb=short

# 3. 验证租户隔离
poetry run pytest tests/acceptance/test_acceptance_event_bus_implementation.py::test_ac2_rabbitmq_documentprocessed -v
poetry run pytest tests/acceptance/test_acceptance_qdrant_vector_layer.py::test_dense_search_with_filter -v

# 4. 清理
docker compose -f deploy/app/docker-compose.test.yml down -v
```

### 7.2 CI 验证

```bash
# 触发 CI pipeline，验证集成测试阶段
git push origin main
```

---

## 八、附录

### 8.1 环境变量参考

| 变量名 | 说明 | 可选值 |
|--------|------|--------|
| `SISYS_TEST_ENV` | 测试环境类型 | `local`, `ci`, `k8s`, `auto` |
| `REDIS_HOST` | Redis 主机 | localhost / host.docker.internal / redis.sisys.svc.cluster.local |
| `REDIS_PORT` | Redis 端口 | 6379 (生产) / 6380 (测试) |
| `POSTGRES_HOST` | PostgreSQL 主机 | localhost / host.docker.internal / postgres.sisys.svc.cluster.local |
| `POSTGRES_PORT` | PostgreSQL 端口 | 5432 (生产) / 5433 (测试) |
| `QDRANT_HOST` | Qdrant 主机 | localhost / host.docker.internal / qdrant.sisys.svc.cluster.local |
| `QDRANT_PORT` | Qdrant 端口 | 6333 (生产) / 6334 (测试) |
| `RABBITMQ_HOST` | RabbitMQ 主机 | localhost / host.docker.internal / rabbitmq.sisys.svc.cluster.local |
| `RABBITMQ_PORT` | RabbitMQ 端口 | 5672 (生产) / 5673 (测试) |

### 8.2 端口映射对照表

#### 本地开发 / CI 环境

| 服务 | 生产端口 | 测试专用端口 | CI host.docker.internal |
|------|---------|-------------|------------------------|
| Redis | 6379 | 6380 | 6380 |
| PostgreSQL | 5432 | 5433 | 5432 |
| Qdrant | 6333 | 6334 | 6333 |
| Qdrant gRPC | 6334 | 6335 | 6334 |
| MinIO API | 9000 | 9002 | 9000 |
| MinIO Console | 9001 | 9003 | 9001 |
| Neo4j HTTP | 7474 | 7475 | 7474 |
| Neo4j Bolt | 7687 | 7688 | 7687 |
| RabbitMQ | 5672 | 5673 | 5672 |
| RabbitMQ Management | 15672 | 15673 | 15672 |

#### ArgoCD K8s 环境 (Service DNS)

| 服务 | K8s Service DNS | Namespace |
|------|-----------------|-----------|
| PostgreSQL | postgres.sisys.svc.cluster.local | sisys |
| Redis | redis.sisys.svc.cluster.local | sisys |
| Qdrant | qdrant.sisys.svc.cluster.local | sisys |
| MinIO | minio.sisys.svc.cluster.local | sisys |
| Neo4j | neo4j.sisys.svc.cluster.local | sisys |
| RabbitMQ | rabbitmq.sisys.svc.cluster.local | sisys |

### 8.3 ArgoCD 环境配置

| 环境 | ArgoCD App | K8s Namespace | 同步策略 |
|------|-----------|---------------|---------|
| Dev | sisys-app-dev | sisys-dev | 完全自动 (self-heal + auto-prune) |
| Test | sisys-app-test | sisys-test | 自动同步 + 手动审批 |
| Prod | sisys-app-prod | sisys-prod | 手动同步 (需要审批) |

---

**文档结束**
