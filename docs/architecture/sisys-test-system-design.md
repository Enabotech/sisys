# SISYS 测试系统框架详细设计

**版本：** 1.0.0
**状态：** 已批准
**创建日期：** 2026-05-24
**审核依据：** 对标 Matthias Noback 六边形测试策略、Martin Fowler Testing Pyramid/Honeycomb、Google Hermetic Testing、Testcontainers 模式

---

## 目录

1. [系统概述与设计哲学](#1-系统概述与设计哲学)
2. [测试分层架构](#2-测试分层架构)
3. [TEM 测试环境管理层](#3-tem-测试环境管理层)
4. [TIL 测试隔离层](#4-til-测试隔离层)
5. [核心组件设计](#5-核心组件设计)
6. [测试类型规范](#6-测试类型规范)
7. [事件驱动系统测试](#7-事件驱动系统测试)
8. [最佳实践指南](#8-最佳实践指南)
9. [CI/CD 集成与配置](#9-cicd-集成与配置)
10. [质量指标与门禁](#10-质量指标与门禁)
11. [与主架构的集成](#11-与主架构的集成)
12. [标杆实践对标](#12-标杆实践对标)

---

## 1. 系统概述与设计哲学

### 1.1 设计哲学

测试系统遵循"**架构即测试，测试即架构**"的核心理念。六边形架构的 Port/Adapter 分层天然对应测试分层策略——每一层有独立的测试方法、隔离手段和覆盖率目标。测试不仅是质量保障工具，更是架构约束的执行器。

### 1.2 核心目标

| 目标 | 说明 | 行业对标 |
|------|------|---------|
| 架构约束执行 | 通过 AST 扫描 + import-linter + 契约测试强制执行六边形分层 | Google Testing Blog: "Architecture Tests as First-Class Citizens" |
| 多环境零适配 | 一份测试代码运行于 Local/CI/K8s 三种环境 | Hermetic Testing (Google) |
| 并行安全隔离 | UUID 租户前缀 + xdist worker 隔离，支持 `-n auto` | pytest-xdist 官方推荐模式 |
| 分层覆盖率门禁 | domain ≥90% / application ≥85% / overall ≥80% | Martin Fowler: "Test Coverage with Per-Module Gates" |

### 1.3 测试规模全景

```
tests/
├── environments.py              # TEM: 多环境配置解析
├── isolation.py                 # TIL: 租户隔离管理
├── fixtures.py                  # Fixture 组织体系
├── conftest.py                  # 全局配置与 bootstrap
├── unit/                        # 259 文件 — 单元测试
│   ├── domain/                  #   领域模型（零 mock）
│   ├── application/             #   用例编排（mock outbound ports）
│   ├── infrastructure/          #   适配器实现（mock 外部服务）
│   ├── interfaces/              #   API/CLI（AsyncMock）
│   ├── architecture/            #   15 文件 — 架构约束（AST 扫描）
│   ├── performance/             #   性能基准
│   └── quality/                 #   代码质量
├── integration/                 # 35 文件 — 集成测试
│   ├── conftest.py              #   mock + real 双模式 fixture
│   ├── test_integration_*.py    #   mock 模式（fakeredis）
│   └── test_integration_*_real.py # real 模式（真实服务）
├── contracts/                   # 20 文件 — 契约测试
│   ├── conftest.py              #   registry + resolver fixture
│   └── test_port_contract_*.py  #   端口契约验证
├── acceptance/                  # 25 文件 — BDD 验收测试
│   └── test_acceptance_*.py     #   Gherkin + 真实服务
├── deploy/                      # 27 文件 — 部署测试
│   └── test_{gitea,argocd,harbor}_*.py
└── e2e/                         # 预留 — 端到端测试
```

---

## 2. 测试分层架构

### 2.1 测试菱形（Testing Honeycomb）

传统测试金字塔假设单元测试占比 70-80%，但六边形架构下适配器层的行为需要更多集成测试验证。业界对标（Martin Fowler [Testing Honeycomb](https://martinfowler.com/articles/practical-test-pyramid.html)、Ham Vocke [Testing Honeycomb for DDD](https://www.thoughtworks.com/insights/blog/testing-strategy-hexagonal-architecture)）推荐六边形项目采用**菱形分布**：

```
                    /\
                   /E2E\           tests/e2e/           (预留)
                  /------\
                 /Accept-\         tests/acceptance/     25 文件
                /  ance    \       BDD + 真实服务
               /────────────\
              /   Contracts   \    tests/contracts/      20 文件
             / (Port 协议验证)\   Protocol 行为验证
            /──────────────────\
           /    Integration     \  tests/integration/    35 文件
          /  (mock + real svc)   \ fakeredis + Testcontainers
         /────────────────────────\
        /        Unit Tests        \ tests/unit/          259 文件
       /  (domain 纯逻辑 + mock)   \ 含 15 个架构约束测试
      /──────────────────────────────\
```

**各层职责与对标**：

| 层级 | 行业对标 | 测试对象 | 依赖 | 速度 |
|------|---------|---------|------|------|
| Unit (Domain) | Matthias Noback "Domain Unit Test" | 纯业务逻辑 | 零外部依赖 | <10ms |
| Unit (Application) | Noback "Application Unit Test" | 用例编排 | mock outbound ports | <50ms |
| Unit (Architecture) | Architecture Fitness Functions | 依赖方向、端口契约 | AST 扫描 | <100ms |
| Integration | Noback "Narrow Integration Test" | 单个适配器 | fakeredis / 真实服务 | 100ms-5s |
| Contracts | Samman Coaching "Port Contract" | Protocol 行为合规 | Resolver | <50ms |
| Acceptance | BDD (Gherkin) | 用户场景 | 真实 6 服务 | 1-30s |
| Deploy | K8s/ArgoCD 验证 | 基础设施正确性 | K8s 集群 | 变动 |

### 2.2 六边形架构的测试映射

对标 Matthias Noback [A Testing Strategy for Hexagonal Applications](https://matthiasnoback.nl/talk/a-testing-strategy-for-hexagonal-applications/)，每个架构层对应独立的测试策略：

```
┌─────────────────────────────────────────────────────────────────────┐
│                        六边形架构测试映射                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  Driving Adapters (interfaces/)                              │  │
│  │  测试：FastAPI TestClient + ASGITransport                    │  │
│  │  覆盖率目标：≥70%                                            │  │
│  │  Mock 策略：Mock application 层端口                           │  │
│  ├─────────────────────────────────────────────────────────────┤  │
│  │  Application Layer (application/)                            │  │
│  │  测试：用例编排 Unit Test                                     │  │
│  │  覆盖率目标：≥85%                                            │  │
│  │  Mock 策略：Mock 所有 outbound ports (Protocol)               │  │
│  ├─────────────────────────────────────────────────────────────┤  │
│  │  Domain Layer (domain/)                                      │  │
│  │  测试：纯 Unit Test，零 mock                                  │  │
│  │  覆盖率目标：≥90%                                            │  │
│  │  Mock 策略：无（纯 Python 对象）                               │  │
│  ├─────────────────────────────────────────────────────────────┤  │
│  │  Driven Adapters (infrastructure/)                           │  │
│  │  测试：Narrow Integration Test + Contract Test                │  │
│  │  覆盖率目标：≥75%                                            │  │
│  │  Mock 策略：fakeredis / Testcontainers / 真实服务              │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  关键约束：                                                         │
│  • Domain 层测试禁止 import 任何外部库                                │
│  • Application 层测试只 mock outbound ports（Protocol 接口）          │
│  • Infrastructure 层测试使用真实基础设施验证适配器行为                   │
│  • 契约测试验证 adapter 满足 port 的 Protocol 规范                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. TEM 测试环境管理层

### 3.1 设计概览

TEM (Test Environment Management Layer) 解决的核心问题：**同一份测试代码在 3 种环境下运行，无需修改任何测试文件**。

对标 Google [Hermetic Testing](https://testing.googleblog.com/) 理念——测试环境应是"密封的"（自包含、无外部依赖干扰），TEM 通过 3 层配置覆盖链实现。

**实现文件**：`tests/environments.py` (489 行)

### 3.2 三层配置覆盖链

配置解析遵循严格的优先级，高优先级覆盖低优先级：

```
┌──────────────────────────────────────────────────────┐
│ Layer 3（最高）：os.environ 显式设置                    │
│   → 用户显式 export REDIS_HOST=xxx                     │
│   → 绝对最高优先级，不可被任何机制覆盖                    │
├──────────────────────────────────────────────────────┤
│ Layer 2：.env 文件填充                                  │
│   → dotenv_values() 加载项目根目录 .env                 │
│   → 仅填充 Layer 1 输出中的空值/默认值                   │
├──────────────────────────────────────────────────────┤
│ Layer 1（最低）：环境检测 + 预设配置                     │
│   → resolve_env() 自动检测环境类型                      │
│   → 选择预设配置：LOCAL / TEST / CI / K8S               │
│   → SISYS_USE_TEST_PORTS=1 切换到独立测试端口            │
└──────────────────────────────────────────────────────┘
```

**三层解析流程**：

```
get_test_env()
  │
  ├─ Layer 1: resolve_env() → 选择预设配置
  │    ├─ SISYS_TEST_ENV=ci         → CI_CONFIG   (host.docker.internal)
  │    ├─ SISYS_TEST_ENV=k8s        → K8S_CONFIG  (K8s Service DNS)
  │    ├─ SISYS_USE_TEST_PORTS=1    → TEST_CONFIG (localhost + 端口偏移+1)
  │    └─ (default)                 → LOCAL_CONFIG(localhost 标准端口)
  │
  ├─ Layer 2: _apply_dotenv_if_empty()
  │    └─ .env 文件填充预设中的默认值（不覆盖已有值）
  │
  ├─ Layer 3: _override_config_from_env()
  │    └─ os.environ 显式设置覆盖一切
  │
  └─ _sync_config_to_environ()
       └─ 将最终结果 setdefault() 回 os.environ，确保生产代码也能读取
```

**关键设计决策**：

1. **三层而非五层**：环境检测（resolve_env）、预设选择（LOCAL/CI/K8S/TEST）、端口切换（SISYS_USE_TEST_PORTS）本质上是同一个决策——"确定运行环境"，合并为 Layer 1。消除"先选预设、再检测环境、再覆盖"的循环依赖。

2. **`_sync_config_to_environ()` 使用 `os.environ.setdefault()` 而非直接赋值**——尊重用户显式设置的环境变量为绝对最高优先级，同时确保生产代码的 `Config.from_env()` 也能读取到一致的值。

3. **线程安全单例**：`get_test_env()` 使用双重检查锁（double-checked locking），`pytest-xdist` 每个 worker 是独立进程，天然隔离。

### 3.3 环境配置数据模型

```
TestEnvConfig
├── env: TestEnvironment          # LOCAL / CI / K8S
├── redis: RedisConfig            # host, port, password, db, ssl, url
├── postgres: PostgreSQLConfig    # host, port, username, password, database, ssl, url
├── qdrant: QdrantConfig          # host, port, grpc_port, api_key, https, timeout, url
├── minio: MinIOConfig            # endpoint, access_key, secret_key, bucket, region, secure
├── neo4j: Neo4jConfig            # host, http_port, bolt_port, username, password, database, bolt_url
├── rabbitmq: RabbitMQConfig      # host, port, mgmt_port, username, password, vhost, url
└── app: AppConfig                # jwt_secret_key, secret_key, algorithm, access_token_expire_minutes
```

每个子配置类提供 `url` / `bolt_url` 属性生成标准连接 URL。

### 3.4 四套预设配置（Layer 1 输出）

| 预设 | 触发条件 | Host 模式 | 端口策略 |
|------|---------|----------|---------|
| `LOCAL_CONFIG` | 本地开发 | `localhost` | 标准端口 (6379/5432/6333...) |
| `TEST_CONFIG` | 本地专用测试 | `localhost` | 偏移+1 (6380/5433/6335...) |
| `CI_CONFIG` | gitea-runner | `host.docker.internal` | 标准端口 |
| `K8S_CONFIG` | ArgoCD 集群 | `sisys-{service}` K8s DNS | 标准端口 |

切换方式：
- 本地专用测试：`SISYS_USE_TEST_PORTS=1`
- CI 环境：`SISYS_TEST_ENV=ci`
- K8s 环境：自动检测或 `SISYS_TEST_ENV=k8s`

### 3.5 对标优化：Testcontainers 集成（规划）

对标业界 [Testcontainers](https://testcontainers.com/) 模式，规划在 CI 环境引入 `testcontainers-python`：

**价值**：消除"先手动启动 Docker 服务"的前置依赖，CI 环境完全自包含。

**规划模式**：
```python
# 规划：tests/integration/conftest.py 中可选的 Testcontainers fixture
@pytest.fixture(scope="session")
def postgres_container():
    """CI 模式：自动启动 PostgreSQL 容器"""
    from testcontainers.postgres import PostgresContainer
    with PostgresContainer("postgres:15") as pg:
        yield pg
```

**与现有 TEM 的集成**：Testcontainers fixture 生成连接参数后注入 Layer 3（os.environ），保持统一的三层配置解析路径。

---

## 4. TIL 测试隔离层

### 4.1 设计概览

TIL (Test Isolation Layer) 解决的核心问题：**并行执行时测试间互不干扰，支持 `-n auto` 全并行**。

**实现文件**：`tests/isolation.py` (223 行)

### 4.2 TestTenant 租户隔离模型

每个测试函数获得唯一的 `TestTenant`，通过 UUID 前缀隔离所有存储层资源：

| 服务 | 前缀格式 | 示例 |
|------|---------|------|
| Redis keys | `test:{uuid}:` | `test:a1b2c3d4e5f6:cache_key` |
| PostgreSQL schemas | `test_{uuid}` | `test_a1b2c3d4e5f6` |
| Qdrant collections | `test_{uuid}_` | `test_a1b2c3d4e5f6_documents` |
| MinIO buckets | `test-{uuid}` | `test-a1b2c3d4e5f6` |
| Neo4j nodes | `test_tenant` 属性 | `n.test_tenant = 'test_{uuid}'` |
| RabbitMQ queues | `test_{uuid}_` | `test_a1b2c3d4e5f6_my_queue` |

### 4.3 多进程隔离原理

对标 pytest-xdist 官方文档和 [SQLAlchemy xdist 讨论](https://github.com/sqlalchemy/sqlalchemy/discussions/13109)，并行隔离分两层：

```
┌─────────────────────────────────────────────────────────────────────┐
│                    并行隔离双层模型                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Layer 1: 进程级隔离（pytest-xdist 多进程）                           │
│  ┌──────────────────────┐  ┌──────────────────────┐                │
│  │  Worker Process A    │  │  Worker Process B    │                │
│  │  独立内存空间         │  │  独立内存空间         │                │
│  │  独立 _test_env_config│  │  独立 _test_env_config│               │
│  │  独立 _tenant_contexts│  │  独立 _tenant_contexts│               │
│  │  独立 bootstrap()     │  │  独立 bootstrap()     │               │
│  └──────────────────────┘  └──────────────────────┘                │
│                                                                     │
│  Layer 2: 资源级隔离（UUID 前缀）                                     │
│  Worker A: test_aaa_queue, test_aaa_collection, test:aaa:key        │
│  Worker B: test_bbb_queue, test_bbb_collection, test:bbb:key        │
│  → 不同前缀，全局资源（Redis/PG/Qdrant 等）无冲突                      │
│                                                                     │
│  分发模式：--dist loadscope（同模块测试分配到同一 worker）               │
└─────────────────────────────────────────────────────────────────────┘
```

**关键理解**：
- xdist 每个 worker 是独立进程，`scope="session"` 的 fixture（如 `bootstrap()`）在每个 worker 中各执行一次
- `TenantContext._tenants` 字典是进程内的，跨 worker 天然隔离
- 全局资源（Redis/PG/Qdrant）通过 UUID 前缀隔离

### 4.4 TenantContext 协程级上下文

```python
# 使用 asyncio.current_task() 的 identity 作为上下文 key
class TenantContext:
    _tenants: dict[int, TestTenant] = {}  # task_id → TestTenant
    _lock: asyncio.Lock = asyncio.Lock()  # 类变量（CLAUDE.md 要求）
```

**上下文管理模式**：
```python
# 同步上下文管理器
with tenant_context() as tenant:
    # 自动设置/清除当前租户
    assert TenantContext.get_current_tenant() is tenant

# pytest fixture 模式
def test_something(isolated_tenant):
    # isolated_tenant 自动设置到 TenantContext
    # 测试结束自动清除
```

### 4.5 TenantAwareMock 资源名称自动前缀

根据资源类型自动添加对应的隔离前缀：

| 输入格式 | 前缀规则 | 输出示例 |
|---------|---------|---------|
| `queue:my_queue` | RabbitMQ 前缀 | `test_{uuid}_my_queue` |
| `collection:docs` | Qdrant 前缀 | `test_{uuid}_docs` |
| `redis:cache_key` | Redis 前缀 | `test:{uuid}:cache_key` |
| `schema:my_table` | PG schema 前缀 | `test_{uuid}.my_table` |
| `bucket:data` | MinIO 前缀 | `test-{uuid}/data` |

### 4.6 对标优化：worker_id 融合（规划）

对标 pytest-xdist 最佳实践，规划将 `worker_id` 融入 TestTenant ID，进一步增强跨 worker 隔离的可追溯性：

```python
# 规划优化
@pytest.fixture
def isolated_tenant(test_tenant: TestTenant, request) -> Generator[TestTenant, None, None]:
    worker_id = getattr(request.config, "workerinput", {}).get("workerid", "master")
    # 将 worker_id 融入 tenant id，便于问题诊断
    enhanced = TestTenant(id=f"{worker_id}_{test_tenant.id}")
    TenantContext.set_current_tenant(enhanced)
    yield enhanced
    TenantContext.clear_current_tenant()
```

---

## 5. 核心组件设计

### 5.1 Resolver 端口解析系统

**实现文件**：`src/domain/ports/resolver.py`

Resolver 是测试系统与六边形架构的桥梁。测试通过 `Resolver` 访问所有端口，与生产环境使用完全相同的 DI 路径。

**三种生命周期**：

| 生命周期 | 行为 | 测试影响 |
|---------|------|---------|
| `SINGLETON` | 全局唯一实例（连接管理器、事件总线） | 测试间共享，需注意状态清理 |
| `SCOPED` | 每个 Resolver 实例缓存 | 测试可用 `Resolver(overrides=...)` 替换 |
| `TRANSIENT` | 每次 resolve 创建新实例 | 天然隔离 |

**测试替换机制**：
```python
# 通过 overrides 注入 mock，无需修改生产代码
resolver = Resolver(overrides={"redis_adapter": mock_redis})
service = resolver.resolve("unified_storage")
```

**自动注入**：`_auto_inject()` 检查构造函数参数注解，按参数名或类型自动 resolve，测试中直接实例化的类也能获得依赖注入。

### 5.2 Fixture 组织体系

对标 [pytest 官方 Fixture 最佳实践](https://docs.pytest.org/en/stable/explanation/fixtures.html)，SISYS 采用分层 fixture 链：

```
Session Scope（每个 worker 一次）
├── _bootstrap_once()            # composition_root.bootstrap()
├── test_env_config              # TestEnvConfig 单例
├── cleanup_old_test_resources   # session 级旧资源清理
└── registry / resolver          # contracts 专用

Function Scope（每个测试函数）
├── test_tenant                  # 新 TestTenant（UUID 前缀）
├── isolated_tenant              # TestTenant + TenantContext 设置/清除
├── tenant_context_fixture       # 上下文管理器变体
├── cleanup_test_tenant          # 自动清理 6 服务资源
├── reset_test_environment       # autouse=True，重置全局状态
├── pg_session                   # mock AsyncSession + ContextVar 管理
├── resolver                     # 端口解析器
└── unique_id / unique_*_name    # 唯一名称生成器
```

**conftest 分层链**：

| 文件 | 职责 | 导出 |
|------|------|------|
| `tests/conftest.py` | 全局 bootstrap、pg_session、fixture 重导出 | `from tests.fixtures import *` |
| `tests/integration/conftest.py` | mock + real 双模式 fixture、测试数据 | mock_redis, real_redis, sample_event... |
| `tests/contracts/conftest.py` | 端口注册表 + 解析器 | registry, resolver |

### 5.3 六服务资源清理机制

**实现文件**：`tests/fixtures.py` (`_cleanup_tenant_resources`)

每个测试结束后，`cleanup_test_tenant` fixture 按租户前缀清理所有 6 个服务的测试资源：

| 服务 | 清理策略 | 错误处理 |
|------|---------|---------|
| Redis | `SCAN` + `DELETE` 匹配 `test:{uuid}:*` | `logger.error` |
| PostgreSQL | `DROP SCHEMA IF EXISTS ... CASCADE` | `logger.warning` |
| Qdrant | 列出 + 删除匹配 `test_{uuid}_*` 的 collection | `logger.warning` |
| MinIO | 列出 + 删除对象 + 删除 bucket `test-{uuid}` | `logger.warning` |
| Neo4j | 参数化 Cypher `DETACH DELETE` | `logger.error` |
| RabbitMQ | 列出 + 删除匹配 `test_{uuid}_` 的队列 | `logger.error` |

**设计原则**：
- 清理失败记录日志但不阻断测试（`pytest.skip()` 在 fixture teardown 中无效）
- 同步桥接函数 `_cleanup_tenant_resources_sync()` 处理从同步 fixture 调用异步清理的场景
- session 级 `cleanup_old_test_resources` 作为兜底，清理上次运行遗留的脏数据

### 5.4 pg_session ContextVar 管理

```python
@pytest.fixture
async def pg_session() -> AsyncGenerator[AsyncMock, None]:
    """mock AsyncSession，自动管理 ContextVar 生命周期"""
    from src.infrastructure.storage.postgresql.session_context import with_session
    mock = _create_mock_session()
    async with with_session(mock):  # 设置 ContextVar
        yield mock                   # 测试中使用 mock
    # with_session 退出时自动重置 ContextVar
```

---

## 6. 测试类型规范

### 6.1 单元测试（tests/unit/）

**对标**：Matthias Noback "Domain Unit Test" + "Application Unit Test"

#### Domain 层（零 mock）

```python
@pytest.mark.unit
class TestFlowStatus:
    def test_transition_from_pending_to_approved(self):
        """纯业务逻辑测试，零外部依赖"""
        status = FlowStatus.PENDING
        result = status.transition(Action.APPROVE)
        assert result == FlowStatus.APPROVED
```

#### Application 层（mock outbound ports）

```python
@pytest.mark.unit
class TestDocumentProcessingUseCase:
    async def test_process_document(self, pg_session):
        """用例编排测试，mock outbound ports"""
        use_case = DocumentProcessingUseCase()
        result = await use_case.execute(document_id="doc-1")
        pg_session.flush.assert_called()
```

#### Architecture 约束（AST 扫描）

15 个架构约束测试文件，对标 [Architecture Fitness Functions](https://www.thoughtworks.com/insights/blog/fitness-function-driven-development)：

| 测试文件 | 验证内容 |
|---------|---------|
| `test_hexagonal_architecture_constraints.py` | 依赖方向矩阵、domain 零外部依赖、端口方法存在 |
| `test_event_bus_architecture.py` | 事件总线架构约束 |
| `test_sqlalchemy_architecture.py` | SQLAlchemy 使用约束 |
| `test_langgraph_architecture.py` | LangGraph 集成约束 |
| `test_messaging_architecture_constraints.py` | 消息系统约束 |

### 6.2 集成测试（tests/integration/）

**对标**：Matthias Noback "Narrow Integration Test" + [Samman Coaching](https://sammancoaching.org/learning_hours/test_doubles/narrow_integration_tests.html)

#### 双模式设计

```
┌─────────────────────────────────────────────────────────┐
│               集成测试双模式                               │
├──────────────────────┬──────────────────────────────────┤
│  Mode 1: Mock 模式    │  Mode 2: Real 模式               │
│  (快速，无外部服务)    │  (真实服务，验证适配器行为)          │
├──────────────────────┼──────────────────────────────────┤
│  fakeredis.aioredis  │  real Redis 连接                  │
│  AsyncMock session   │  real PostgreSQL 引擎              │
│  InMemoryEventStore  │  real Qdrant client               │
│  InMemoryOutbox      │  real MinIO/Neo4j/RabbitMQ        │
├──────────────────────┼──────────────────────────────────┤
│  命名: test_integration_*.py           │  命名: test_integration_*_real.py  │
│  无服务不可用问题       │  pytest.skip() 不可用时跳过         │
└──────────────────────┴──────────────────────────────────┘
```

#### 真实服务 fixture 模式

```python
@pytest.fixture
async def real_redis() -> AsyncGenerator[redis.Redis, None]:
    """function scope，每个测试独立连接"""
    config = get_test_env()
    client = redis.Redis(host=config.redis.host, ...)
    try:
        await client.ping()
    except Exception as e:
        await client.close()
        pytest.skip(f"Redis not available: {e}")  # 服务不可用时跳过
    yield client
    await client.close()
```

**对标优化**：规划将 `real_*` fixture 从 `function` scope 提升为 `session` scope（配合 TestTenant 隔离），减少连接开销。

### 6.3 契约测试（tests/contracts/）

**对标**：Samman Coaching "Narrow Integration Tests for Outbound Ports" + Pact 消费者驱动契约

#### 三断言模式

每个端口契约测试遵循三个断言：

```python
class TestMyPortContract:
    PORT_NAME = "my_port"
    INTERFACE = MyPortProtocol
    REQUIRED_METHODS = ["method_a", "method_b"]

    def test_port_is_registered(self, registry):
        """断言 1：端口已注册且接口类型正确"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry):
        """断言 2：实现类包含所有端口方法"""
        spec = registry.get(self.PORT_NAME)
        impl = spec.impl
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method)
            assert callable(getattr(impl, method))

    def test_metadata_complete(self, registry):
        """断言 3：PortSpec 元数据完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module
```

#### 契约测试覆盖范围

| 文件 | 覆盖端口 |
|------|---------|
| `test_port_contract_repositories.py` | 9 个仓储端口 |
| `test_port_contract_storage.py` | 6 层存储端口 |
| `test_port_contract_event_publisher.py` | 事件发布端口 |
| `test_port_contract_auth_security.py` | 认证安全端口 |
| `test_port_contract_agent_engine.py` | Agent 引擎端口 |
| `test_port_contract_workflow_engine.py` | 工作流引擎端口 |
| `test_api_contract_*.py` | API 契约（audit/rbac/equilibrium） |

### 6.4 验收测试（tests/acceptance/）

**对标**：BDD (Gherkin) + pytest-bdd

#### 结构模式

每个验收测试文件对应一个 Story，包含：
1. `scenarios("*.feature")` 导入
2. 真实服务 fixture（通过 `get_test_env()` 获取连接参数）
3. `@given` / `@when` / `@then` step 定义

```python
# BDD step 定义模式
@given('Redis 缓存服务可用')
def redis_available(test_env_config):
    config = test_env_config.redis
    try:
        client = redis.Redis(host=config.host, port=config.port)
        client.ping()
    except redis.ConnectionError:
        pytest.skip(f"Redis not available at {config.host}:{config.port}")

@when('写入缓存数据')
def write_cache(test_tenant, test_env_config):
    key = f"{test_tenant.redis_key_prefix}test_key"
    # 写入操作...

@then('应能读取到正确数据')
def verify_cache(test_tenant, test_env_config):
    # 验证操作...
```

### 6.5 部署测试（tests/deploy/）

**对标**：K8s/ArgoCD 基础设施验证

| 类别 | 文件数 | 验证内容 |
|------|--------|---------|
| Gitea | 7 | 部署、runner 持久化、token、监控 |
| ArgoCD | 8 | 应用配置、安全、多环境、性能 |
| Harbor | 4 | 部署、架构合规、镜像推送 |
| CI/CD | 2 | Pipeline 模板、GPU 调度 |

**基础设施**：`config.py` (389 行) + `k8s_helpers.py` (422 行)，提供 `run_kubectl()`、`wait()`、`temporary_resource()` 等工具。

---

## 7. 事件驱动系统测试

### 7.1 双通道事件总线测试策略

对标业界事件驱动测试最佳实践，针对 SISYS 的双通道架构（REALTIME: Redis pub/sub + RELIABLE: RabbitMQ + Outbox）：

```
┌─────────────────────────────────────────────────────────────────────┐
│                     双通道事件测试策略                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  REALTIME 通道（Redis pub/sub）                                      │
│  ├── 单元测试：InMemoryEventBus mock                                 │
│  ├── 集成测试：fakeredis pub/sub 验证                                │
│  └── 验收测试：真实 Redis pub/sub + 消费者确认                        │
│                                                                     │
│  RELIABLE 通道（RabbitMQ + Outbox）                                  │
│  ├── 单元测试：OutboxStateMachine 状态转换                           │
│  ├── 集成测试：InMemoryOutbox + IdempotencyChecker                  │
│  ├── 集成测试：真实 RabbitMQ 投递 + ACK 确认                         │
│  └── 验收测试：完整 Outbox → Poller → RabbitMQ → Consumer 链路       │
│                                                                     │
│  跨通道测试                                                          │
│  └── ChannelRouter 路由决策：验证事件类型到通道的正确映射               │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Outbox 模式测试清单

对标业界 Outbox 事务性测试要求：

| 测试场景 | 验证内容 | 实现位置 |
|---------|---------|---------|
| 原子性 | 事务提交时 Outbox 记录与业务数据同时持久化 | `test_integration_event_messaging.py` |
| 回滚一致性 | 事务回滚时 Outbox 记录也被回滚 | `test_integration_event_messaging.py` |
| 幂等性 | `IdempotencyChecker` 的 `SET NX EX` 原子操作 | `test_integration_event_bus.py` |
| 状态转换 | `pending → published | failed → archived` | OutboxStateMachine 测试 |
| 重试策略 | 指数退避、最大重试次数 | `retry_policy` fixture |
| 并发竞争 | 多 Poller 竞争同一事件 | 规划中 |

### 7.3 DomainEvent 多态反序列化测试

```python
# 21 种领域事件的序列化/反序列化测试
class TestDomainEventSerialization:
    def test_event_registry_auto_populated(self):
        """验证所有事件子类自动注册到 _registry"""
        assert len(DomainEvent._registry) >= 21

    def test_round_trip_serialization(self):
        """验证 to_dict() → from_dict() 往返一致性"""
        event = MemoryChanged(...)
        serialized = event.to_dict()
        deserialized = DomainEvent.from_dict(serialized)
        assert deserialized.event_type == "MemoryChanged"
```

---

## 8. 最佳实践指南

### 8.1 测试隔离三原则

**原则 1：每个测试获得唯一租户**
```python
def test_something(test_tenant):  # function-scoped, 唯一 UUID
    queue_name = f"{test_tenant.rabbitmq_queue_prefix}my_queue"
```

**原则 2：禁止跨测试共享可变状态**
- `reset_test_environment` fixture（autouse=True）在每次测试前后重置全局状态
- `InMemoryEventStore.clear()` 在 fixture teardown 中调用
- `pg_session` fixture 使用 `async with with_session(mock)` 管理 ContextVar 生命周期

**原则 3：真实资源必须清理**
```python
def test_with_real_redis(cleanup_test_tenant):
    # cleanup_test_tenant 在测试后自动清理 6 个服务的资源
```

### 8.2 并行测试安全规则

对标 pytest-xdist 官方文档：

| 规则 | 说明 |
|------|------|
| 禁止硬编码资源名 | 始终使用 `test_tenant` 前缀 |
| 禁止假设其他测试状态 | 每个测试完全独立 |
| `loadscope` 分发 | 同模块测试在同一 worker，共享 session fixture |
| 建议并行度 `-n 4` | 避免资源竞争，UUID 碰撞概率可忽略 |

**对标优化**：规划引入 `pytest-random-order`，在 CI 中定期以随机顺序执行测试，检测隐式依赖。

### 8.3 异步测试处理

对标 [pytest-asyncio](https://pypi.org/project/pytest-asyncio/) 最佳实践：

**核心规则**：不要手动定义 `event_loop` fixture。`asyncio_mode = "auto"` 自动管理。

```python
# ✅ 正确：直接使用 async def
async def test_async_operation(pg_session):
    repo = MyRepository()
    await repo.save(entity)
    pg_session.flush.assert_called()

# ❌ 错误：手动 event_loop fixture（导致状态污染）
@pytest.fixture(scope="module")  # 与 auto mode 冲突
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

**BDD 步骤中的异步处理**（CLAUDE.md 硬约束）：
```python
# ✅ 使用 event_loop.run_until_complete()
@then("异步消费者应该接收到该事件")
def verify_consumer(event_loop, rabbitmq_consumer):
    async def _test():
        async with temporary_consumer(...) as consumer:
            await rabbitmq_publisher.async_publish(event)
            await asyncio.sleep(2.0)
    event_loop.run_until_complete(_test())

# ❌ 禁止在 BDD 步骤中使用 @pytest.mark.asyncio
```

### 8.4 Mock 策略分层

对标业界 Mock 策略，SISYS 采用 4 级 Mock 分层：

| 级别 | 工具 | 适用场景 | 速度 |
|------|------|---------|------|
| Tier 1: fakeredis | `fakeredis.aioredis.FakeRedis` | Redis 相关代码 | 极快 |
| Tier 2: AsyncMock | `unittest.mock.AsyncMock(spec=...)` | 端口/接口 mock | 极快 |
| Tier 3: InMemory | `InMemoryEventStore` / `InMemoryOutbox` | 复杂有状态行为 | 快 |
| Tier 4: 真实服务 | `real_redis` / `real_postgres_engine` | 适配器行为验证 | 慢 |

**使用原则**：
- `spec=` 参数强制 mock 与真实接口保持一致，防止 mock drift
- Tier 1-3 用于单元测试和 mock 模式集成测试
- Tier 4 用于 real 模式集成测试和验收测试
- 真实服务不可用时使用 `pytest.skip()` 跳过

### 8.5 测试数据管理

| 工具 | 用途 | 位置 |
|------|------|------|
| `TestTenant` | 租户隔离前缀 | `tests/isolation.py` |
| `event_id` / `sample_event` | 事件测试数据 | `tests/integration/conftest.py` |
| `unique_id` / `unique_*_name` | 唯一名称生成 | `tests/fixtures.py` |
| `StrategicPlanFactory` | 领域实体工厂 | `tests/factories/__init__.py` |

---

## 9. CI/CD 集成与配置

### 9.1 CI 测试执行流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CI Pipeline                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Step 1: 启动测试服务                                                │
│  docker compose -f deploy/app/docker-compose.test.yml up -d         │
│  → 等待所有服务 healthy (redis/pg/qdrant/minio/neo4j/rabbitmq)       │
│                                                                     │
│  Step 2: 设置环境变量                                                │
│  export SISYS_TEST_ENV=ci                                           │
│  → environments.py 自动使用 host.docker.internal 连接宿主机服务       │
│                                                                     │
│  Step 3: 执行测试                                                    │
│  poetry run pytest tests/unit tests/integration tests/contracts \   │
│    tests/acceptance \                                               │
│    -v --strict-markers --tb=short \                                 │
│    --cov=src --cov-report=term-missing:skip-covered \               │
│    -n auto --dist loadscope                                         │
│                                                                     │
│  Step 4: 覆盖率门禁                                                  │
│  → 整体 ≥80%，domain ≥90%，application ≥85%                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.2 Docker Compose 测试环境

**文件**：`deploy/app/docker-compose.test.yml`

| 服务 | 容器名 | 端口映射 | 健康检查 |
|------|--------|---------|---------|
| Redis | `sisys-test-redis` | `6380:6379` | `redis-cli ping` |
| PostgreSQL | `sisys-test-postgres` | `5433:5432` | `pg_isready` |
| Qdrant | `sisys-test-qdrant` | `6334:6333`, `6335:6334` | - |
| MinIO | `sisys-test-minio` | `9002:9000`, `9003:9001` | `mc ready local` |
| Neo4j | `sisys-test-neo4j` | `7475:7474`, `7688:7687` | TCP check |
| RabbitMQ | `sisys-test-rabbitmq` | `5673:5672`, `15673:15672` | `rabbitmq-diagnostics` |

**隔离设计**：专用网络 `sisys-test-network` + 独立命名卷 `sisys-test-*-data`，与生产环境完全隔离。

### 9.3 K8s 测试环境

| 服务 | K8s Service DNS | Namespace |
|------|-----------------|-----------|
| Redis | `sisys-redis.sisys.svc.cluster.local` | sisys |
| PostgreSQL | `sisys-postgres.sisys.svc.cluster.local` | sisys |
| Qdrant | `sisys-qdrant.sisys.svc.cluster.local` | sisys |
| MinIO | `sisys-minio.sisys.svc.cluster.local` | sisys |
| Neo4j | `sisys-neo4j.sisys.svc.cluster.local` | sisys |
| RabbitMQ | `sisys-rabbitmq.sisys.svc.cluster.local` | sisys |

### 9.4 Pre-commit Hooks 集成

| Hook | 检查内容 | 阶段 |
|------|---------|------|
| ruff | Lint + Format | commit |
| mypy | 类型检查 | commit |
| bandit | 安全扫描 | commit |
| detect-secrets | 密钥检测 | commit |
| validate-schemas | 领域事件 Schema 验证 | push |
| validate-openapi | OpenAPI 3.1 规范验证 | push |
| pytest-bdd | BDD 验收测试 | push |

---

## 10. 质量指标与门禁

### 10.1 覆盖率门禁

对标 Martin Fowler [Test Coverage](https://martinfowler.com/bliki/TestCoverage.html) 和业界共识，设定分层覆盖率门禁：

| 层级 | 最低覆盖率 | 理由 |
|------|-----------|------|
| domain | ≥90% | 核心业务逻辑，零容忍未测试路径 |
| application | ≥85% | 用例编排，高价值业务流 |
| infrastructure | ≥75% | 适配器层，部分外部服务行为难以测试 |
| interfaces | ≥70% | API 路由，依赖框架行为 |
| **overall** | **≥80%** | **系统级质量基线** |

**对标优化**：由于 `pytest-cov` 的 `--cov-fail-under` 不支持按模块设置不同阈值（[GitHub Issue #728](https://github.com/pytest-dev/pytest-cov/issues/728)），规划创建自定义 CI 覆盖率门禁脚本：

```bash
# 规划：分层覆盖率检查脚本
coverage report --include="src/domain/*" --fail-under=90
coverage report --include="src/application/*" --fail-under=85
coverage report --include="src/*" --fail-under=80
```

### 10.2 架构约束验证体系

对标 [Architecture Fitness Functions](https://www.thoughtworks.com/insights/blog/fitness-function-driven-development)，SISYS 采用三层验证：

| 验证层 | 工具 | 检查内容 | 失败级别 |
|--------|------|---------|---------|
| 静态分析 | import-linter | 依赖方向规则（`.importlinter`） | CI 失败 |
| AST 扫描 | `hexagonal_arch_guard.py` (854 行) | domain 零依赖、目录结构、端口方法 | CI 失败 |
| 运行时验证 | 契约测试 (20 文件) | 端口注册、方法存在、元数据完整 | CI 失败 |
| 单元测试 | `test_hexagonal_architecture_constraints.py` | 依赖方向矩阵、禁止导入、ruff/mypy | CI 失败 |

### 10.3 pytest 标记体系

18 个 marker 提供灵活的测试选择：

| 标记 | 用途 | 选择命令 |
|------|------|---------|
| `unit` / `integration` / `e2e` | 测试类型分层 | `-m unit` / `-m integration` |
| `asyncio` | 异步测试（auto mode 自动标记） | 自动处理 |
| `slow` | 慢速测试（>1s） | `-m "not slow"` |
| `k8s` | 需要 K8s 集群 | `-m k8s` |
| `database` / `redis` / `qdrant` / `minio` / `neo4j` | 服务依赖标记 | 按服务选择 |
| `llm` | 需要 LLM API | `-m "not llm"` |
| `AC-1` ~ `AC-9` | 验收标准编号 | `-m AC-1` |
| `edge-case` | 边界场景 | `-m edge-case` |

### 10.4 对标优化：Flaky Test 隔离（规划）

对标 Google [Test Quarantine](https://testing.googleblog.com/) 策略，规划引入 Flaky Test 隔离机制：

1. **检测**：CI 中追踪连续失败 ≥2 次的测试
2. **隔离**：自动标记 `@pytest.mark.flaky`，移入 `tests/quarantine/` 目录
3. **修复**：定期修复并移出隔离区
4. **监控**：Dashboard 追踪 flaky rate 指标

---

## 11. 与主架构的集成

### 11.1 三个集成锚点

测试系统通过三个锚点与六边形架构集成：

**锚点 1：Port Registry Bootstrap**
```python
# tests/conftest.py
@pytest.fixture(scope="session", autouse=True)
def _bootstrap_once():
    from src.composition_root import bootstrap
    bootstrap()  # 注册所有 70+ 端口到 _global_registry
```

**锚点 2：Resolver-Based Test Access**
```python
# tests 通过 Resolver 访问端口，与生产环境使用相同 DI 路径
resolver = Resolver()
service = resolver.resolve("unified_storage")
```

**锚点 3：Architecture Constraint Tests**
```python
# AST 扫描验证六边形架构约束
# import-linter 验证依赖方向
# 契约测试验证端口协议
```

### 11.2 覆盖率与主架构分层映射

```
src/
├── domain/          ← domain ≥90%  (tests/unit/domain/)
├── application/     ← application ≥85%  (tests/unit/application/)
├── infrastructure/  ← infrastructure ≥75%  (tests/unit/infrastructure/ + tests/integration/)
└── interfaces/      ← interfaces ≥70%  (tests/unit/interfaces/ + tests/contracts/)
```

---

## 12. 标杆实践对标

### 12.1 已采纳的业界标杆

| 标杆实践 | 来源 | SISYS 实现位置 |
|---------|------|---------------|
| 六边形测试五层策略 | Matthias Noback | tests/unit/domain/application/infrastructure/ 分层 |
| Testing Honeycomb | Martin Fowler | 菱形分布：259 unit + 35 integration + 20 contracts |
| Narrow Integration Test | Samman Coaching | tests/integration/ 的 mock + real 双模式 |
| Hermetic Testing | Google | TEM 三层配置链，3 环境零适配 |
| Architecture Fitness Functions | ThoughtWorks | 15 个 AST 扫描 + import-linter + 20 契约测试 |
| 端口契约三断言 | Pact 启发 | test_port_is_registered + test_methods + test_metadata |
| BDD 验收测试 | Dan North | pytest-bdd + Gherkin scenarios |
| Outbox 事务性测试 | 业界共识 | 原子性/幂等性/状态转换/重试策略 |

### 12.2 规划优化项

| 优化项 | 行业对标 | 优先级 | 说明 |
|--------|---------|--------|------|
| Testcontainers 集成 | Testcontainers Python | 中 | CI 自动启动 6 服务容器 |
| worker_id 融合 TestTenant | pytest-xdist 最佳实践 | 中 | 增强并行可追溯性 |
| 分层覆盖率门禁脚本 | pytest-cov multi-module | 中 | domain 90% / application 85% 自动检查 |
| Flaky Test 隔离 | Google Test Quarantine | 低 | 检测-隔离-修复-监控闭环 |
| pytest-random-order | 业界共识 | 低 | CI 定期随机顺序执行，检测隐式依赖 |
| 分层超时配置 | pytest-timeout | 低 | unit:5s / integration:30s / e2e:300s |
| 测试报告增强 | pytest-html + Allure | 低 | CI 中发布 HTML 覆盖率报告 |

### 12.3 与 sisys-testing-framework.md 的关系

本文档是 `sisys-testing-framework.md`（v2.0.0, 2156 行）的**架构设计补充**：

| 文档 | 定位 | 内容 |
|------|------|------|
| `sisys-testing-framework.md` | **实施方案** | 现状诊断、问题分类(P1-P6)、具体修复代码、Phase 1-8 Checklist |
| 本文档 | **架构设计** | 设计哲学、分层架构、核心组件、测试规范、标杆对标、质量指标 |

两份文档互补：framework 侧重"怎么做"，design 侧重"为什么这样设计"。

---

## 附录 A：关键文件索引

| 文件 | 行数 | 职责 |
|------|------|------|
| `tests/environments.py` | 489 | TEM: 多环境配置解析、三层覆盖链、线程安全单例 |
| `tests/isolation.py` | 223 | TIL: TestTenant、TenantContext、TenantAwareMock |
| `tests/fixtures.py` | 382 | Fixture 体系、6 服务资源清理、Resolver fixture |
| `tests/conftest.py` | 90 | 全局 bootstrap、pg_session mock |
| `tests/integration/conftest.py` | 376 | mock + real 双模式 fixture、测试数据 |
| `tests/contracts/conftest.py` | 46 | 端口注册表 + 解析器 fixture |
| `tests/utils/hexagonal_arch_guard.py` | 854 | AST 扫描架构守卫 |
| `src/composition_root.py` | - | 70+ 端口注册、bootstrap/shutdown |
| `src/domain/ports/resolver.py` | - | Resolver: resolve/resolve_by_interface/_auto_inject |

## 附录 B：pytest 配置参考

```toml
# pyproject.toml 关键配置
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "unit", "integration", "e2e", "asyncio", "slow", "k8s",
    "database", "redis", "qdrant", "minio", "neo4j", "llm",
    "AC-1", "AC-2", "AC-3", "AC-4", "AC-5", "AC-6", "AC-7", "AC-8", "AC-9",
    "edge-case",
]
addopts = "-v --strict-markers --tb=short --cov=src --cov-report=term-missing:skip-covered -n auto --dist loadscope"

[tool.coverage.run]
source = ["src"]
omit = ["tests/*", "*/__init__.py", "*/conftest.py"]

[tool.coverage.report]
fail_under = 80
exclude_lines = ["pragma: no cover", "__repr__", "NotImplementedError", "TYPE_CHECKING", "@abstractmethod"]
```

## 附录 C：环境变量参考

| 变量 | 说明 | 可选值 |
|------|------|--------|
| `SISYS_TEST_ENV` | 测试环境类型 | `local` / `ci` / `k8s` |
| `SISYS_USE_TEST_PORTS` | 启用独立测试端口 | `1` / `true` |
| `REDIS_HOST` | Redis 主机覆盖 | localhost / host.docker.internal / K8s DNS |
| `POSTGRES_HOST` | PostgreSQL 主机覆盖 | 同上 |
| `QDRANT_HOST` | Qdrant 主机覆盖 | 同上 |
| `MINIO_HOST` | MinIO 主机覆盖 | 同上 |
| `NEO4J_HOST` | Neo4j 主机覆盖 | 同上 |
| `RABBITMQ_HOST` | RabbitMQ 主机覆盖 | 同上 |

---

**文档结束**
