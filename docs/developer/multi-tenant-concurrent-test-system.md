# 多用户并发测试工程系统实施方案

**文档版本**: v1.0.0
**创建日期**: 2026-04-20
**状态**: 已批准实施
**负责人**: Agimtech

---

## 一、现状诊断

### 1.1 测试系统结构

```
tests/
├── conftest.py              # 仅添加项目路径 (sys.path)
├── acceptance/              # BDD 验收测试（使用真实服务）
│   ├── test_story_1_3_steps.py   # 依赖 rabbitmq_publisher/consumer fixtures
│   ├── test_story_1_6_steps.py   # 依赖 vector_storage/collection_manager fixtures
│   └── test_story_*.feature     # Gherkin 场景定义
├── integration/              # 集成测试（使用 fakeredis mock）
│   └── conftest.py          # 提供 mock fixtures (scope=function)
├── integration_real/         # 真实服务集成测试
│   └── conftest.py          # 从 .env 读取连接参数 (scope=session)
└── fixtures/                 # 空目录（预留）
```

**CI 测试执行流程** (`.gitea/workflows/ci.yaml` lines 240-289):
1. 启动 `deploy/app/docker-compose.yml` 服务，等待 `healthy`
2. 覆盖环境变量：`REDIS_HOST=host.docker.internal` 等
3. 运行：`pytest tests/integration tests/integration_real tests/acceptance`

**连接配置**:
- 本地开发：从 `.env` 读取 `localhost:6379/5432/6333...`
- CI 环境：覆盖为 `host.docker.internal:6380/5432/6333...`
- K8s 环境：通过 ArgoCD Service DNS 访问

### 1.2 问题背景

在 gitea-runner CI 环境和本地开发环境同时运行时，发现以下测试失败：

| 测试 | 环境 | 错误信息 |
|------|------|---------|
| `test_ac2_rabbitmq_agentdecided` | gitea-runner | Consumer did not receive event (0 received) |
| `test_ac2_rabbitmq_documentprocessed` | 本地 | Consumer did not receive event (0 received) |
| `test_dense_search_with_filter` | 本地 | Collection `sisys_documents_finance` doesn't exist |

### 1.3 核心问题分类

| 问题编号 | 分类 | 问题描述 | 严重度 |
|---------|------|---------|--------|
| P1 | 测试实现 | `async_consume()` 永久阻塞 | 🔴 致命 |
| P2 | 测试实现 | `collection_has_different_domains` 缺少 create_collection | 🔴 致命 |
| P3 | 环境配置 | CI 设置 `host.docker.internal` 但测试用 `localhost` | 🔴 致命 |
| P4 | 测试工程 | 验收测试无隔离机制（fixture 依赖顺序） | 🔴 致命 |
| P5 | 架构设计 | 多环境 docker-compose 端口不一致 | 🟡 中等 |
| P6 | 测试工程 | 测试使用 `scope=module` 事件循环导致状态污染 | 🟡 中等 |

### 1.4 根因分析结论

> **这是测试实现问题，而非多用户并发架构缺陷。**

您的多用户并发架构设计是正确的：
- `IdempotencyChecker` 使用 `SET NX EX` 原子操作
- 队列 `durable=True` 配置正确
- 测试失败是隔离问题，不是并发竞争问题

---

## 二、解决方案架构

### 2.1 核心设计原则

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
│                                 │                                               │
│                                 ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │                        测试编排层 (TOR)                                    │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │  Test Orchestrator                                                │  │ │
│  │  │  • 串行/并行执行控制                                               │  │ │
│  │  │  • 依赖声明与拓扑排序                                              │  │ │
│  │  │  • 失败隔离与恢复                                                  │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
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

**文件**: `tests/acceptance/test_story_1_3_steps.py`

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
# ✅ 修复方案 - 使用 asyncio.create_task 后台运行
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def temporary_consumer(consumer, queue_name, routing_key, handler):
    """临时消费者上下文管理器，确保正确的设置和清理顺序."""
    event_type = queue_name.split("-")[-1]
    consumer.register_handler(event_type, handler)
    await consumer.bind_queue(queue_name, routing_key)

    # 使用 create_task 后台运行，不阻塞
    consume_task = asyncio.create_task(consumer.async_consume(queue_name))

    # 短暂等待消费者真正开始消费
    await asyncio.sleep(0.5)

    try:
        yield
    finally:
        # 清理：取消任务并关闭连接
        consume_task.cancel()
        try:
            await consume_task
        except asyncio.CancelledError:
            pass
        await consumer.close()

@then("异步消费者应该接收到该事件")
def verify_rabbitmq_consumer_receives(
    rabbitmq_publisher: AsyncRabbitMQPublisher,
    rabbitmq_consumer: AsyncRabbitMQConsumer,
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
        async with temporary_consumer(rabbitmq_consumer, queue_name, routing_key, handler):
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

#### 3.1.2 修复 `collection_has_different_domains` fixture

**文件**: `tests/acceptance/test_story_1_6_steps.py`

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
# ✅ 修复方案 - 添加 collection 创建
@given('Collection "sisys:documents:finance" 包含不同业务域的向量点')
def collection_has_different_domains(
    collection_manager: QdrantCollectionManager,
    vector_storage: QdrantVectorStorage,
    event_loop,
):
    """Collection contains vectors with different business domains."""

    async def _setup_and_insert():
        # 1. 确保 collection 存在
        try:
            await collection_manager.create_collection(
                name="sisys_documents_finance",
                vector_size=1024,
                distance="Cosine",
            )
        except Exception:
            pass

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
                await vector_storage.upsert_points("sisys_documents_finance", points)

    event_loop.run_until_complete(_setup_and_insert())
```

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
from dataclasses import dataclass, field
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
    postgres_host: str
    postgres_port: int
    qdrant_host: str
    qdrant_port: int
    qdrant_grpc_port: int
    minio_host: str
    minio_port: int
    minio_console_port: int
    neo4j_host: str
    neo4j_http_port: int
    neo4j_bolt_port: int
    rabbitmq_host: str
    rabbitmq_port: int
    rabbitmq_mgmt_port: int

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


# K8s namespace 到服务 DNS 后缀的映射
_K8S_ENV_NAMESPACES = {
    "development": "sisys-dev",
    "testing": "sisys-test",
    "production": "sisys-prod",
}


def _detect_environment() -> TestEnvironment:
    """自动检测当前测试环境."""

    # 1. 优先使用环境变量显式指定
    explicit = os.getenv("SISYS_TEST_ENV", "").lower()
    if explicit in ("local", "ci", "k8s"):
        return TestEnvironment(explicit)

    # 2. K8s 环境检测（检查 Service Account token）
    if _is_running_in_k8s():
        return TestEnvironment.K8S

    # 3. CI 环境检测 (gitea-runner)
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
    if isinstance(env_type, str):
        env_type = TestEnvironment(env_type.lower())
    elif env_type == TestEnvironment.AUTO:
        env_type = _detect_environment()

    import uuid
    tenant_id = test_tenant_id or f"test_{uuid.uuid4().hex[:8]}"

    # 本地开发环境
    if env_type == TestEnvironment.LOCAL:
        return TestEnvConfig(
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            qdrant_host=os.getenv("QDRANT_HOST", "localhost"),
            qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
            qdrant_grpc_port=int(os.getenv("QDRANT_GRPC_PORT", "6334")),
            minio_host=os.getenv("MINIO_HOST", "localhost"),
            minio_port=int(os.getenv("MINIO_API_PORT", "9000")),
            minio_console_port=int(os.getenv("MINIO_CONSOLE_PORT", "9001")),
            neo4j_host=os.getenv("NEO4J_HOST", "localhost"),
            neo4j_http_port=int(os.getenv("NEO4J_HTTP_PORT", "7474")),
            neo4j_bolt_port=int(os.getenv("NEO4J_BOLT_PORT", "7687")),
            rabbitmq_host=os.getenv("RABBITMQ_HOST", "localhost"),
            rabbitmq_port=int(os.getenv("RABBITMQ_PORT", "5672")),
            rabbitmq_mgmt_port=int(os.getenv("RABBITMQ_MGMT_PORT", "15672")),
            env_type=env_type,
            test_tenant_id=tenant_id,
            k8s_namespace=None,
        )

    # CI 环境 (gitea-runner/docker)
    elif env_type == TestEnvironment.CI:
        return TestEnvConfig(
            redis_host=os.getenv("REDIS_HOST", "host.docker.internal"),
            redis_port=int(os.getenv("REDIS_PORT", "6380")),
            postgres_host=os.getenv("POSTGRES_HOST", "host.docker.internal"),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            qdrant_host=os.getenv("QDRANT_HOST", "host.docker.internal"),
            qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
            qdrant_grpc_port=int(os.getenv("QDRANT_GRPC_PORT", "6334")),
            minio_host=os.getenv("MINIO_HOST", "host.docker.internal"),
            minio_port=int(os.getenv("MINIO_API_PORT", "9000")),
            minio_console_port=int(os.getenv("MINIO_CONSOLE_PORT", "9001")),
            neo4j_host=os.getenv("NEO4J_HOST", "host.docker.internal"),
            neo4j_http_port=int(os.getenv("NEO4J_HTTP_PORT", "7474")),
            neo4j_bolt_port=int(os.getenv("NEO4J_BOLT_PORT", "7687")),
            rabbitmq_host=os.getenv("RABBITMQ_HOST", "host.docker.internal"),
            rabbitmq_port=int(os.getenv("RABBITMQ_PORT", "5672")),
            rabbitmq_mgmt_port=int(os.getenv("RABBITMQ_MGMT_PORT", "15672")),
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
            postgres_host=os.getenv("POSTGRES_HOST", k8s_host("postgres")),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            qdrant_host=os.getenv("QDRANT_HOST", k8s_host("qdrant")),
            qdrant_port=int(os.getenv("QDRANT_PORT", "6333")),
            qdrant_grpc_port=int(os.getenv("QDRANT_GRPC_PORT", "6334")),
            minio_host=os.getenv("MINIO_HOST", k8s_host("minio")),
            minio_port=int(os.getenv("MINIO_API_PORT", "9000")),
            minio_console_port=int(os.getenv("MINIO_CONSOLE_PORT", "9001")),
            neo4j_host=os.getenv("NEO4J_HOST", k8s_host("neo4j")),
            neo4j_http_port=int(os.getenv("NEO4J_HTTP_PORT", "7474")),
            neo4j_bolt_port=int(os.getenv("NEO4J_BOLT_PORT", "7687")),
            rabbitmq_host=os.getenv("RABBITMQ_HOST", k8s_host("rabbitmq")),
            rabbitmq_port=int(os.getenv("RABBITMQ_PORT", "5672")),
            rabbitmq_mgmt_port=int(os.getenv("RABBITMQ_MGMT_PORT", "15672")),
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
  # 测试专用网络
  # ===========================================================================
  networks:
    sisys-test:
      driver: bridge
      name: sisys-test-network

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
# 存储卷 (测试数据卷，与生产隔离)
# =============================================================================
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
import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar
from unittest.mock import AsyncMock, patch

import pytest

# 导入环境配置
from tests.environments import get_test_env, TestEnvConfig

T = TypeVar("T")


@dataclass
class TestTenant:
    """测试租户 - 提供隔离的资源前缀."""

    id: str  # 租户唯一标识 (UUID)
    prefix: str  # 资源前缀 (简短版)

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
    _resources: list[str] = field(default_factory=list)
    _cleanup_tasks: list[Callable] = field(default_factory=list)

    def register_resource(self, resource_id: str, cleanup_fn: Callable | None = None) -> str:
        """注册需要清理的资源."""
        self._resources.append(resource_id)
        if cleanup_fn:
            self._cleanup_tasks.append(cleanup_fn)
        return resource_id

    async def cleanup(self) -> None:
        """清理租户所有资源."""
        for cleanup_fn in self._cleanup_tasks:
            try:
                if asyncio.iscoroutinefunction(cleanup_fn):
                    await cleanup_fn()
                else:
                    cleanup_fn()
            except Exception as e:
                print(f"Cleanup error: {e}")

        self._resources.clear()
        self._cleanup_tasks.clear()


# 全局租户上下文存储
_tenant_contexts: dict[str, TenantContext] = {}


def generate_test_tenant() -> TestTenant:
    """生成测试租户."""
    tenant_id = uuid.uuid4().hex[:8]
    return TestTenant(
        id=tenant_id,
        prefix=tenant_id,
    )


def get_current_tenant() -> TestTenant | None:
    """获取当前租户 (如果存在)."""
    import threading
    thread_id = threading.current_thread().ident
    context = _tenant_contexts.get(thread_id)
    return context.tenant if context else None


def get_current_context() -> TenantContext | None:
    """获取当前上下文 (如果存在)."""
    import threading
    thread_id = threading.current_thread().ident
    return _tenant_contexts.get(thread_id)


@asynccontextmanager
async def tenant_context(
    tenant: TestTenant | None = None,
    env_config: TestEnvConfig | None = None,
):
    """创建租户上下文字典管理器."""
    import threading

    if tenant is None:
        tenant = generate_test_tenant()
    if env_config is None:
        env_config = get_test_env()

    context = TenantContext(tenant=tenant, config=env_config)
    thread_id = threading.current_thread().ident
    _tenant_contexts[thread_id] = context

    try:
        yield context
    finally:
        await context.cleanup()
        if thread_id in _tenant_contexts:
            del _tenant_contexts[thread_id]


# Pytest 集成
@pytest.fixture
def test_tenant() -> TestTenant:
    """Pytest fixture: 为每个测试生成独立租户."""
    return generate_test_tenant()


@pytest.fixture
async def isolated_tenant_context(test_tenant: TestTenant) -> TenantContext:
    """Pytest fixture: 创建隔离的租户上下文 (async).

    自动清理资源。
    """
    from tests.environments import get_test_env
    env_config = get_test_env()
    context = TenantContext(tenant=test_tenant, config=env_config)

    import threading
    thread_id = threading.current_thread().ident
    _tenant_contexts[thread_id] = context

    yield context

    await context.cleanup()
    if thread_id in _tenant_contexts:
        del _tenant_contexts[thread_id]


# Mock 适配器 - 用于替换真实服务为测试租户隔离版本
class TenantAwareMock:
    """租户感知的 Mock 适配器.

    自动为所有资源添加租户前缀。
    """

    def __init__(self, tenant: TestTenant):
        self.tenant = tenant
        self._mocks: dict[str, Any] = {}

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
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import pytest

from tests.environments import TestEnvConfig, get_test_env
from tests.isolation import (
    TenantContext,
    generate_test_tenant,
    get_current_tenant,
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
    fresh_test_env_config: TestEnvConfig,
) -> AsyncGenerator[TenantContext, None]:
    """Async context manager 提供隔离的租户上下文.

    测试结束后自动清理资源。
    """
    from tests.isolation import TenantContext

    context = TenantContext(
        tenant=isolated_tenant,
        config=fresh_test_env_config,
    )

    yield context

    # 清理资源
    await _cleanup_tenant_resources(context, fresh_test_env_config)


async def _cleanup_tenant_resources(
    context: TenantContext,
    config: TestEnvConfig,
) -> None:
    """清理租户相关资源."""
    tenant = context.tenant

    # 清理 RabbitMQ 队列
    try:
        import aio_pika
        connection = await aio_pika.connect_robust(
            host=config.rabbitmq_host,
            port=config.rabbitmq_port,
        )
        channel = await connection.channel()
        await connection.close()
    except Exception as e:
        print(f"RabbitMQ cleanup error: {e}")

    # 清理 Qdrant Collections
    try:
        from qdrant_client import AsyncQdrantClient

        client = AsyncQdrantClient(
            host=config.qdrant_host,
            port=config.qdrant_port,
        )

        collections = await client.get_collections()
        for col in collections.collections:
            if col.name.startswith(f"test_{tenant.prefix}_"):
                try:
                    await client.delete_collection(col.name)
                except Exception:
                    pass

        await client.close()
    except Exception as e:
        print(f"Qdrant cleanup error: {e}")

    # 清理 Redis keys
    try:
        import redis.asyncio as redis

        r = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            decode_responses=True,
        )

        pattern = f"test:{tenant.prefix}:*"
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break

        await r.close()
    except Exception as e:
        print(f"Redis cleanup error: {e}")

    # 清理 PostgreSQL schema
    try:
        import asyncpg

        conn = await asyncpg.connect(
            host=config.postgres_host,
            port=config.postgres_port,
            database=config.postgres_database or "sisys",
            user=config.postgres_username or "postgres",
            password=config.postgres_password or "postgres",
        )

        schema_name = f"test_{tenant.prefix}"
        try:
            await conn.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
        except Exception:
            pass

        await conn.close()
    except Exception as e:
        print(f"PostgreSQL cleanup error: {e}")


# ===================================================================
# 事件循环 Fixtures (修复 module scope 问题)
# ===================================================================


@pytest.fixture(scope="function")
def event_loop():
    """Function 级事件循环.

    替代 module 级事件循环，确保测试隔离。
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ===================================================================
# 测试前/后钩子
# ===================================================================


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

## 四、实施路线图

### 4.1 实施阶段

```
Phase 1: 紧急修复 (1-2 天)
├── P1: 修复 async_consume 永久阻塞
├── P2: 修复 collection_has_different_domains
└── P6: 修复 event_loop scope 问题

Phase 2: 环境标准化 (2-3 天)
├── P3: 实现 tests/environments.py
├── P5: 创建 deploy/app/docker-compose.test.yml
└── 更新 CI workflow 使用统一配置

Phase 3: 测试隔离 (3-4 天)
├── P4: 实现 tests/isolation.py
├── P4: 实现 tests/fixtures.py
└── 更新所有 acceptance test fixtures

Phase 4: 验证与优化 (2-3 天)
├── 运行完整测试套件验证
├── 性能优化
└── 文档更新
```

### 4.2 预期效果

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 测试通过率 (本地) | ~99% (1/2179 失败) | 100% |
| 测试通过率 (CI) | ~99.7% (1/375 失败) | 100% |
| 测试隔离性 | 无隔离 | 租户级隔离 |
| 环境适应性 | 硬编码 localhost | 自动环境检测 |
| 多用户并发安全 | 可能冲突 | 租户隔离保证 |

---

## 五、关键文件清单

```
tests/
├── environments.py          # [新建] 测试环境配置解析
├── isolation.py              # [新建] 测试租户隔离管理
├── fixtures.py              # [新建] 测试资源清理 fixtures
├── conftest.py              # [更新] 添加隔离 fixtures
└── acceptance/
    ├── test_story_1_3_steps.py  # [更新] 修复 async_consume 问题
    └── test_story_1_6_steps.py  # [更新] 修复 collection 创建问题

deploy/app/
└── docker-compose.test.yml  # [新建] 测试专用 docker-compose

.gitea/workflows/
└── ci.yaml                  # [更新] 使用测试专用环境
```

---

## 六、验证方案

### 6.1 本地验证

```bash
# 1. 启动测试环境
docker compose -f deploy/app/docker-compose.test.yml up -d

# 2. 运行验收测试
export SISYS_TEST_ENV=local
poetry run pytest tests/acceptance -v --tb=short

# 3. 验证租户隔离
poetry run pytest tests/acceptance/test_story_1_3_steps.py::test_ac2_rabbitmq_documentprocessed -v
poetry run pytest tests/acceptance/test_story_1_6_steps.py::test_dense_search_with_filter -v

# 4. 清理
docker compose -f deploy/app/docker-compose.test.yml down -v
```

### 6.2 CI 验证

```bash
# 触发 CI pipeline，验证集成测试阶段
git push origin main
```

---

## 七、附录

### 7.1 环境变量参考

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

### 7.2 端口映射对照表

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

### 7.3 ArgoCD 环境配置

| 环境 | ArgoCD App | K8s Namespace | 同步策略 |
|------|-----------|---------------|---------|
| Dev | sisys-app-dev | sisys-dev | 完全自动 (self-heal + auto-prune) |
| Test | sisys-app-test | sisys-test | 自动同步 + 手动审批 |
| Prod | sisys-app-prod | sisys-prod | 手动同步 (需要审批) |

---

**文档结束**
