# SISYS 端口开发与管理详细设计

**文档版本:** v1.0
**生成时间:** 2026-05-19
**基于:** architecture.md v8.3.1 + sisys-port-impl-refactor.md v4.0 + 现有代码实现全面调研
**状态:** 现有系统已完整实现（50+ 端口注册）

---

## 1. 设计概述

### 1.1 端口管理系统职责

端口管理系统是 SISYS 六边形架构的核心基础设施，负责：

| 职责 | 技术实现 | 当前状态 |
|------|---------|---------|
| **端口契约定义** | Protocol + @runtime_checkable | ✅ 已实现 |
| **统一注册管理** | PortRegistry 单例模式 | ✅ 已实现 |
| **依赖注入解析** | Resolver 生命周期管理 | ✅ 已实现 |
| **自动注入** | 构造函数参数扫描 + 双重解析 | ✅ 已实现 |
| **契约测试验证** | contracts/ 目录测试套件 | ✅ 已实现 |

### 1.2 端口来源

| 来源 | 目录 | 数量 | 说明 |
|------|------|------|------|
| Domain 层 | `src/domain/ports/` | ~35 | 领域核心端口（存储抽象、仓储、认证授权等） |
| Application 层 | `src/application/ports/` | 14 | 应用服务端口（语义缓存、沙箱、指标等） |
| **合计** | | **~49** | |

### 1.3 核心设计原则

- **依赖倒置**：Domain/Application 层定义端口，Infrastructure 层实现
- **统一注册**：所有端口注册到 PortRegistry，业务只拿"契约"不碰"实现"
- **自动注入**：Resolver 自动解析构造函数依赖
- **生命周期管理**：SINGLETON / SCOPED / TRANSIENT 三种策略
- **幂等注册**：相同 spec 重复注册自动跳过

---

## 2. 架构总览图

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Composition Root                              │
│                   src/composition_root.py                            │
│                         bootstrap()                                  │
│         register_port(name, interface, impl, lifetime, ...)         │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ register_port()
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Layer 2: PortRegistry                            │
│                    (Singleton - _global_registry)                    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  _ports: dict[str, PortSpec]                                  │   │
│  │  PortSpec: name/version/interface/impl/module/lifetime/owner  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ resolve() / resolve_by_interface()
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Layer 3: Resolver (DI Container)                 │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  _instances: dict[str, Any]     # SINGLETON cache           │   │
│  │  _scoped_context: dict[str, Any] # SCOPED cache             │   │
│  │  _overrides: dict[str, Any]     # test overrides           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  resolve(port_name) ──► _create_instance() ──► _instantiate()      │
│        │                       │                    │               │
│        ▼                       ▼                    ▼               │
│  1. overrides 优先     Lifetime.SINGLETON    ┌─────────────────┐  │
│  2. registry.get()     Lifetime.SCOPED        │ impl 类型判断    │  │
│  3. KeyError            Lifetime.TRANSIENT   │ - callable →    │  │
│                                             │   factory()      │  │
│                                             │ - str →         │  │
│                                             │   lazy load      │  │
│                                             │ - type →        │  │
│                                             │   _auto_inject   │  │
│                                             └─────────────────┘  │
│                                                   │               │
│        resolve(param_name) ◄──────────────────────┘           │
│              │                                                   │
│              ▼                                                   │
│  _auto_inject():                                                 │
│    for param in __init__ signature:                              │
│      1. resolve(param_name)    ← 按参数名称                      │
│      2. resolve_by_interface(param_type) ← 按类型注解            │
│      3. use default or fail                                      │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Layer 1: Port Contracts                          │
│                                                                      │
│  ┌─────────────────────────┐  ┌─────────────────────────────────┐  │
│  │   Domain Ports          │  │   Application Ports               │  │
│  │   src/domain/ports/    │  │   src/application/ports/         │  │
│  │                         │  │                                   │  │
│  │  L0StoragePort         │  │  MemoryCachePort ← L1CachePort  │  │
│  │  L1CachePort           │  │  SessionCachePort ← L1CachePort │  │
│  │  L2RdbPort[T]          │  │  MemoryVectorPort ← L3VectorPort│  │
│  │  L3VectorPort          │  │  DocumentStoragePort ← L4Object │  │
│  │  L4ObjectPort          │  │  MemoryGraphPort ← L5GraphPort  │  │
│  │  L5GraphPort           │  │  SemanticCache (独立)            │  │
│  │  ConnectionManager     │  │  SandboxExecutor (独立)         │  │
│  │  UserRepositoryPort    │  │  MetricsPort (独立)              │  │
│  │  AuthServicePort       │  │  ...                              │  │
│  └─────────────────────────┘  └─────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Layer 4: Contract Tests                           │
│                    tests/contracts/test_port_contract_*.py          │
│                                                                      │
│  test_port_contract_storage.py    - L0-L5 + UnifiedStorage          │
│  test_port_contract_repositories.py - RBAC + Outbox + Memory        │
│  test_port_contract_services.py   - Auth + Compliance + Sandbox     │
│  test_port_contract_application.py - App Ports (14个)              │
│  test_port_infrastructure.py      - PortRegistry + Resolver        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Layer 2: PortRegistry

### 3.1 Lifetime 枚举

**文件:** `src/domain/ports/registry.py`

```python
class Lifetime(Enum):
    """端口生命周期管理策略"""

    TRANSIENT = "transient"  # 每次请求新建实例
    SCOPED = "scoped"        # 每个作用域单实例
    SINGLETON = "singleton"  # 全局单实例
```

### 3.2 PortSpec 元数据

```python
@dataclass(frozen=True)
class PortSpec:
    """端口规格元数据

    Attributes:
        name: 唯一端口名称
        version: 语义化版本号 (semver)
        interface: 协议接口类型
        impl: 实现类型、工厂函数或模块路径字符串（用于延迟加载）
        module: 实现所在的模块路径
        lifetime: 实例生命周期（默认 SCOPED）
        owner: 负责团队或个人
        compatibility: 兼容版本元组
        tags: 场景/环境选择标签
        deprecated: 是否已废弃
    """

    name: str
    version: str
    interface: Type
    impl: Type | Callable[..., Any] | str
    module: str
    lifetime: Lifetime = Lifetime.SCOPED
    owner: str = ""
    compatibility: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    deprecated: bool = False
```

**设计要点：**
- `frozen=True` 确保不可变性，线程安全
- `impl` 支持三种形式：直接类、工厂函数、模块路径字符串（延迟加载）

### 3.3 PortRegistry 单例实现

```python
class PortRegistry:
    """端口注册中心（单例模式）

    确保所有端口注册的唯一数据源
    """

    _instance: PortRegistry | None = None
    _ports: dict[str, PortSpec] = field(default_factory=dict)

    def __new__(cls) -> PortRegistry:
        """使用 __new__ 实现单例（而非 __init__）"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._ports = {}
        return cls._instance
```

### 3.4 核心方法

| 方法 | 功能 | 幂等性 |
|------|------|--------|
| `register(spec)` | 注册端口，相同 spec 跳过 | ✅ |
| `get(name)` | 按名称查找 | - |
| `get_by_interface(interface)` | 按接口类型查找，支持子类匹配 | - |
| `list_all()` | 返回所有已注册端口 | - |
| `list_by_tag(tag)` | 按标签过滤 | - |
| `unregister(name)` | 注销端口 | - |

### 3.5 便捷注册函数

```python
def register_port(
    name: str,
    version: str,
    interface: Type,
    impl: Type | Callable[..., Any] | str,
    module: str,
    **kwargs: Any,
) -> None:
    """便捷的端口注册函数"""
    spec = PortSpec(
        name=name,
        version=version,
        interface=interface,
        impl=impl,
        module=module,
        **kwargs,
    )
    _global_registry.register(spec)
```

---

## 4. Layer 3: Resolver

### 4.1 Resolver 类结构

**文件:** `src/domain/ports/resolver.py`

```python
class Resolver:
    """依赖注入端口解析器，从注册中心解析端口实现并管理其生命周期"""

    def __init__(
        self,
        registry: PortRegistry | None = None,
        overrides: dict[str, Any] | None = None,
    ):
        self._registry = registry or _global_registry
        self._overrides = overrides or {}       # 测试覆盖
        self._instances: dict[str, Any] = {}     # 单例缓存
        self._scoped_context: dict[str, Any] = {}  # 作用域缓存
```

### 4.2 解析方法

#### resolve(port_name) - 按名称解析

```python
def resolve(self, port_name: str) -> Any:
    """通过名称解析端口并返回实例

    解析顺序：
    1. overrides（测试覆盖）优先
    2. registry.get() 获取 PortSpec
    3. _create_instance() 创建实例
    """
    if port_name in self._overrides:
        return self._overrides[port_name]  # 优先返回测试覆盖

    spec = self._registry.get(port_name)
    if spec is None:
        raise KeyError(f"Port not registered: {port_name}")

    if spec.deprecated:
        logger.warning("Using deprecated port: %s", port_name)

    return self._create_instance(spec)
```

#### resolve_by_interface(interface) - 按类型解析

```python
def resolve_by_interface(self, interface: Type[T] | str) -> Any:
    """通过接口类型解析端口

    用于构造函数参数无名称匹配时，按类型注解查找
    """
    if isinstance(interface, str):
        raise KeyError("Cannot resolve forward-reference annotation")
    spec = self._registry.get_by_interface(interface)
    if spec is None:
        raise KeyError(f"Port not found for interface: {interface.__name__}")
    return self._create_instance(spec)
```

### 4.3 生命周期管理

```python
def _create_instance(self, spec: PortSpec) -> Any:
    """根据生命周期策略创建实例"""
    if spec.lifetime == Lifetime.SINGLETON:
        if spec.name not in self._instances:
            self._instances[spec.name] = self._instantiate(spec)
        return self._instances[spec.name]

    if spec.lifetime == Lifetime.SCOPED:
        if spec.name not in self._scoped_context:
            self._scoped_context[spec.name] = self._instantiate(spec)
        return self._scoped_context[spec.name]

    # TRANSIENT - 每次新建
    return self._instantiate(spec)
```

### 4.4 实例化逻辑

```python
def _instantiate(self, spec: PortSpec) -> Any:
    """实例化端口实现

    impl 支持三种形式：
    1. callable (非 type) → 工厂函数，传入 resolver
    2. str → 模块路径字符串，延迟加载后再 _auto_inject
    3. type → 直接类，通过 _auto_inject 注入依赖
    """
    if callable(spec.impl) and not isinstance(spec.impl, type):
        return spec.impl(resolver=self)  # 工厂函数
    if isinstance(spec.impl, str):
        cls = self._load_from_module_path(spec.impl)  # 延迟加载
        return self._auto_inject(cls)
    return self._auto_inject(spec.impl)  # 直接类
```

### 4.5 自动注入

```python
def _auto_inject(self, cls: Type[T]) -> T:
    """自动注入构造函数依赖

    双重解析策略：
    1. 按参数名称 resolve(param_name)
    2. 失败后按类型注解 resolve_by_interface(param_type)
    3. 仍失败则使用默认值（如果有）
    """
    sig = inspect.signature(cls.__init__)
    kwargs = {}
    failures = []

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        if param.annotation is inspect.Parameter.empty:
            continue

        param_type = param.annotation

        try:
            instance = self.resolve(param_name)  # 按名称解析
            kwargs[param_name] = instance
        except KeyError:
            try:
                instance = self.resolve_by_interface(param_type)  # 按类型解析
                kwargs[param_name] = instance
            except KeyError:
                if param.default is inspect.Parameter.empty:
                    failures.append(param_name)
                else:
                    kwargs[param_name] = param.default

    if failures:
        raise RuntimeError(f"Cannot resolve required dependencies for {cls.__name__}: {failures}")

    return cls(**kwargs)
```

### 4.6 生命周期管理方法

```python
def clear_scoped(self) -> None:
    """清除作用域实例（请求结束时调用）"""
    self._scoped_context.clear()

def clear_singleton(self) -> None:
    """清除单例实例"""
    self._instances.clear()
```

---

## 5. Layer 1: Port Contracts

### 5.1 Domain 层端口

**位置:** `src/domain/ports/`

| 端口 | 继承 | 说明 |
|------|------|------|
| `L0StoragePort` | Protocol | 文件系统存储 |
| `L1CachePort` | Protocol | KV 缓存 |
| `L2RdbPort[T]` | Generic[Protocol] | 关系数据库 |
| `L3VectorPort` | Protocol | 向量存储 |
| `L4ObjectPort` | Protocol | 对象存储 |
| `L5GraphPort` | Protocol | 图存储 |
| `ConnectionManager` | Protocol | 连接管理器 |
| `UserRepositoryPort` | Protocol | 用户仓储 |
| `RoleRepositoryPort` | Protocol | 角色仓储 |
| `AuthServicePort` | Protocol | 认证服务 |
| `PermissionServicePort` | Protocol | 权限服务 |
| `OutboxRepository` | Protocol | 发件箱仓储 |
| `UnitOfWork` | Protocol | 工作单元 |
| `UnitOfWorkFactory` | Protocol | 工作单元工厂 |
| `SagaRepositoryProtocol` | Protocol | Saga 仓储 |
| `SagaStep` | Protocol | Saga 步骤 |

### 5.2 Application 层端口

**位置:** `src/application/ports/`

#### 继承 Domain Port 的端口

| 端口 | 继承 | 添加方法 |
|------|------|---------|
| `MemoryFilePort` | ← L0StoragePort | update_index, remove_from_index, search_index |
| `MemoryCachePort` | ← L1CachePort | get_memory, set_memory, delete_memory, invalidate_owner |
| `SessionCachePort` | ← L1CachePort | save_session, load_session, delete_session, session_exists |
| `MemoryVectorPort` | ← L3VectorPort | index_memory, search_similar_memories |
| `DocumentStoragePort` | ← L4ObjectPort | store_document, list_user_documents, get_document_metadata |
| `MemoryGraphPort` | ← L5GraphPort | index_memory_relations, get_knowledge_graph |

#### 独立 Protocol

| 端口 | 说明 |
|------|------|
| `SemanticCache` | 向量相似度缓存（基于 Redis RediSearch） |
| `SandboxExecutor` | 沙箱执行器（Docker/gVisor） |
| `PublicBlackboard` | 多 Agent 信息共享 |
| `MetricsPort` | Prometheus 指标采集 |
| `ExceptionMetricsPort` | 异常指标记录 |
| `EventSubscriber` | 事件订阅（对标 NServiceBus） |
| `CompressorService` | 文本压缩服务 |
| `TextExtractorService` | 文本提取服务 |

### 5.3 继承层次结构

```
L0StoragePort
└── MemoryFilePort (+ update_index, remove_from_index, search_index)

L1CachePort
├── MemoryCachePort (+ get_memory, set_memory, delete_memory, invalidate_owner)
└── SessionCachePort (+ save_session, load_session, delete_session, session_exists)

L3VectorPort
└── MemoryVectorPort (+ index_memory, search_similar_memories)

L4ObjectPort
└── DocumentStoragePort (+ store_document, list_user_documents, get_document_metadata)

L5GraphPort
└── MemoryGraphPort (+ index_memory_relations, get_knowledge_graph)

独立 Protocol:
├── SemanticCache
├── SandboxExecutor
├── PublicBlackboard
├── MetricsPort
├── ExceptionMetricsPort
├── EventSubscriber
├── CompressorService
└── TextExtractorService
```

---

## 6. Composition Root

### 6.1 Bootstrap 流程

**文件:** `src/composition_root.py`

```python
def bootstrap() -> None:
    """引导端口注册表，注册所有已知端口

    在应用启动时调用一次
    """
    logger.info("Bootstrapping port registry...")

    # 导入所有 Domain 和 Application 层端口接口（仅类型定义）
    from src.domain.ports.connection_manager import ConnectionManager
    from src.domain.ports.l0_storage import L0StoragePort
    # ... 其他导入

    # 导入所有 Infrastructure 层实现
    from src.infrastructure.storage.redis.redis_manager import RedisManager
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
    # ... 其他导入

    # 按依赖顺序注册端口
    # 1. 连接管理器（最高优先级）
    register_port(
        name="redis_connection_manager",
        version="v1.0.0",
        interface=ConnectionManager,
        impl=lambda resolver: RedisManager(RedisConfig.from_env()),
        module="...",
        lifetime=Lifetime.SINGLETON,
    )

    # 2. 客户端端口
    register_port(name="redis_client", ...)

    # 3. Session 工厂
    register_port(name="session_factory", ...)

    # 4. 存储层端口
    register_port(name="l0_storage", ...)
    register_port(name="l1_cache", ...)

    # 5. 仓储层端口
    register_port(name="user_repo", ...)
    register_port(name="role_repo", ...)

    # 6. 服务层端口
    register_port(name="auth_service", ...)
    register_port(name="permission_service", ...)

    # ... 更多端口

    logger.info("Port registry bootstrap complete.")
```

### 6.2 三种 impl 注册形式

```python
# 形式1: 直接类引用（TRANSIENT）
register_port(
    name="user_repo",
    interface=UserRepositoryPort,
    impl=UserRepository,  # 直接类
    lifetime=Lifetime.SCOPED,
)

# 形式2: 工厂 Lambda（SINGLETON 常用）
register_port(
    name="redis_connection_manager",
    interface=ConnectionManager,
    impl=lambda resolver: RedisManager(RedisConfig.from_env()),  # 工厂函数
    lifetime=Lifetime.SINGLETON,
)

# 形式3: 模块路径字符串（延迟加载）
register_port(
    name="outbox_repo",
    interface=OutboxRepository,
    impl="src.infrastructure.messaging.outbox.outbox_repository.PostgreSQLOutboxRepository",
    lifetime=Lifetime.SINGLETON,
)
```

### 6.3 注册顺序设计

| 阶段 | 端口类型 | 示例 |
|------|---------|------|
| 1 | 连接管理器 | redis_connection_manager, postgresql_connection_manager |
| 2 | 客户端端口 | redis_client, postgresql_async_engine |
| 3 | Session 工厂 | session_factory |
| 4 | 基础存储端口 | l0_storage, l1_cache, l3_vector, l4_object, l5_graph |
| 5 | L2 仓储 | memory_metadata, memory_change_history |
| 6 | Repository 层 | user_repo, role_repo, audit_repo |
| 7 | Service 层 | auth_service, permission_service |
| 8 | Event/Messaging 层 | event_publisher, outbox_repo, outbox_poller |
| 9 | Transaction/Saga | uow_factory, saga_repository |
| 10 | Compliance 层 | compliance_gateway, sensitive_data_detector |
| 11 | Application 层端口 | semantic_cache, metrics, sandbox_executor |
| 12 | 统一存储网关 | unified_storage |

### 6.4 Shutdown 流程

```python
async def shutdown() -> None:
    """优雅关闭所有连接管理器"""
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    managers = [
        "redis_connection_manager",
        "postgresql_connection_manager",
        "qdrant_connection_manager",
        "neo4j_connection_manager",
    ]

    for name in managers:
        try:
            manager = resolver.resolve(name)
            await manager.close()
        except Exception as e:
            logger.warning("Failed to close %s: %s", name, e)

    # 清除缓存
    resolver.clear_singleton()
    resolver.clear_scoped()
```

---

## 7. 测试体系

### 7.1 测试分层架构

```
tests/
├── unit/
│   ├── domain/ports/
│   │   └── test_resolver.py          # Resolver 单元测试
│   └── architecture/
│       ├── test_hexagonal_architecture_constraints.py
│       ├── test_messaging_architecture_constraints.py
│       └── test_event_loop_blocking.py
├── contracts/                        # 契约测试
│   ├── conftest.py
│   ├── verify_contracts.py
│   ├── test_port_contract_*.py
│   └── test_api_contract_*.py
└── integration/
    ├── conftest.py
    └── test_integration_async_port.py
```

### 7.2 契约测试模式

```python
# tests/contracts/test_port_contract_storage.py

class TestL0StoragePortContract:
    PORT_NAME = "l0_storage"
    INTERFACE = L0StoragePort
    REQUIRED_METHODS = ["write", "read", "delete", "exists", "list_memories"]

    def test_port_is_registered(self, registry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.interface is self.INTERFACE

    def test_interface_has_required_methods(self) -> None:
        """接口必须有核心方法"""
        for method in self.REQUIRED_METHODS:
            assert hasattr(self.INTERFACE, method)

    def test_metadata_complete(self, registry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec.version
        assert spec.owner
        assert spec.module
```

### 7.3 Resolver 生命周期测试

```python
# tests/unit/domain/ports/test_resolver.py

class TestResolverLifecycle:
    def test_transient_creates_new_instance(self, registry) -> None:
        """TRANSIENT 每次创建新实例"""
        spec = PortSpec(name="test", version="v1", interface=Protocol,
                        impl=SomeClass, module="...", lifetime=Lifetime.TRANSIENT)
        registry.register(spec)

        r = Resolver(registry)
        inst1 = r.resolve("test")
        inst2 = r.resolve("test")
        assert inst1 is not inst2

    def test_singleton_returns_same_instance(self, registry) -> None:
        """SINGLETON 返回相同实例"""
        spec = PortSpec(name="test", version="v1", interface=Protocol,
                        impl=SomeClass, module="...", lifetime=Lifetime.SINGLETON)
        registry.register(spec)

        r = Resolver(registry)
        inst1 = r.resolve("test")
        inst2 = r.resolve("test")
        assert inst1 is inst2

    def test_scoped_returns_same_within_scope(self, registry) -> None:
        """SCOPED 在同一作用域返回相同实例"""
        spec = PortSpec(name="test", version="v1", interface=Protocol,
                        impl=SomeClass, module="...", lifetime=Lifetime.SCOPED)
        registry.register(spec)

        r = Resolver(registry)
        inst1 = r.resolve("test")
        inst2 = r.resolve("test")
        assert inst1 is inst2

        r.clear_scoped()
        inst3 = r.resolve("test")
        assert inst1 is not inst3
```

### 7.4 运行命令

```bash
# 契约测试
poetry run pytest tests/contracts/ -v

# Resolver 单元测试
poetry run pytest tests/unit/domain/ports/test_resolver.py -v

# 架构约束测试
poetry run pytest tests/unit/architecture/ -v

# 全量测试
poetry run pytest --tb=short
```

---

## 8. 设计模式汇总

| 模式 | 应用位置 | 说明 |
|------|---------|------|
| **单例模式** | PortRegistry | 全局唯一注册表实例 |
| **工厂模式** | Resolver._instantiate | 工厂函数支持 |
| **延迟加载** | Resolver._load_from_module_path | 字符串路径模块懒加载 |
| **自动注入** | Resolver._auto_inject | 构造函数依赖自动解析 |
| **双重解析** | Resolver._auto_inject | 先按名称，再按类型 |
| **幂等注册** | PortRegistry.register | 相同 spec 跳过 |
| **生命周期管理** | Resolver._create_instance | SINGLETON/SCOPED/TRANSIENT |

---

## 9. 关键文件索引

### 9.1 核心文件

| 文件 | 说明 |
|------|------|
| `src/domain/ports/registry.py` | PortRegistry 单例 + PortSpec 元数据 + register_port() |
| `src/domain/ports/resolver.py` | Resolver DI 容器 + 生命周期管理 + 自动注入 |
| `src/composition_root.py` | bootstrap() + shutdown() + 所有端口注册 |

### 9.2 Domain 层端口

| 文件 | 端口 |
|------|------|
| `src/domain/ports/l0_storage.py` | L0StoragePort |
| `src/domain/ports/l1_cache.py` | L1CachePort |
| `src/domain/ports/l2_rdb.py` | L2RdbPort[T] |
| `src/domain/ports/l3_vector.py` | L3VectorPort |
| `src/domain/ports/l4_object.py` | L4ObjectPort |
| `src/domain/ports/l5_graph.py` | L5GraphPort |
| `src/domain/ports/connection_manager.py` | ConnectionManager |
| `src/domain/ports/user_repository.py` | UserRepositoryPort |
| `src/domain/ports/role_repository.py` | RoleRepositoryPort |
| `src/domain/ports/auth_service.py` | AuthServicePort |
| `src/domain/ports/outbox.py` | OutboxRepository |
| `src/domain/ports/unit_of_work.py` | UnitOfWork, UnitOfWorkFactory |

### 9.3 Application 层端口

| 文件 | 端口 |
|------|------|
| `src/application/ports/memory_cache_port.py` | MemoryCachePort |
| `src/application/ports/session_cache_port.py` | SessionCachePort |
| `src/application/ports/semantic_cache.py` | SemanticCache |
| `src/application/ports/memory_vector_port.py` | MemoryVectorPort |
| `src/application/ports/document_storage_port.py` | DocumentStoragePort |
| `src/application/ports/memory_graph_port.py` | MemoryGraphPort |
| `src/application/ports/metrics_port.py` | MetricsPort |
| `src/domain/ports/sandbox_executor.py` | SandboxExecutor |
| `src/application/ports/compressor_service.py` | CompressorService |

### 9.4 测试文件

| 文件 | 说明 |
|------|------|
| `tests/unit/domain/ports/test_resolver.py` | Resolver 单元测试（生命周期/自动注入） |
| `tests/contracts/test_port_contract_storage.py` | L0-L5 存储契约测试 |
| `tests/contracts/test_port_contract_services.py` | 服务端口契约测试 |
| `tests/contracts/test_port_contract_application.py` | Application 端口契约测试 |
| `tests/unit/architecture/test_hexagonal_architecture_constraints.py` | 六边形架构约束验证 |

---

## 10. 与现有架构文档一致性

### 10.1 与 `sisys-port-impl-refactor.md` 一致性

| 项目 | Refactor 文档描述 | 实际代码 | 状态 |
|------|------------------|---------|------|
| Layer 1: Port Contract | Domain + Application Ports | `src/domain/ports/` + `src/application/ports/` | ✅ |
| Layer 2: Registry | PortRegistry 单例 + register_port() | `registry.py:61-159` | ✅ |
| Layer 3: Resolver | DI 容器 + 生命周期管理 | `resolver.py:27-202` | ✅ |
| Layer 4: Contract Gate | 契约测试 + CI 检查 | `tests/contracts/` | ✅ |
| 三种 impl 形式 | 类/工厂/路径字符串 | `composition_root.py` | ✅ |
| 依赖顺序注册 | 连接管理器优先 | `composition_root.py:114-190` | ✅ |
| 幂等注册 | 相同 spec 跳过 | `registry.py:85-90` | ✅ |

### 10.2 与 `architecture.md` 一致性

| 约束 | 实现 | 状态 |
|------|------|------|
| 领域层零外部依赖 | `registry.py` / `resolver.py` 仅使用标准库 | ✅ |
| 六边形架构 | Protocol 在 domain/app，Impl 在 infrastructure | ✅ |
| 依赖方向正确 | domain → application → infrastructure | ✅ |

---

## 11. 已知限制与注意事项

| 项目 | 说明 |
|------|------|
| Forward Reference | `resolve_by_interface` 不支持字符串类型注解 |
| 循环依赖 | 自动注入不处理循环依赖，需使用工厂函数打破 |
| 异步构造 | 自动注入不支持异步 `__init__`，需使用工厂函数 |
| 模块路径延迟加载 | 首次解析时 import 可能失败，需确保模块可导入 |
