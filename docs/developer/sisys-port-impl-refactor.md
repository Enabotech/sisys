# SISYS 端口开发与管理重构执行方案

**文档版本:** v4.0
**生成时间:** 2026-05-12
**基于:** sisys-port-impl-report.md 全面调研结果

---

## 重要修订说明（v4.0）

### 修订内容

1. **不迁移 application/ports** - application/ports 和 domain/ports 各有用途，独立共存
2. **不创建 src/domain/ports/contracts/** - 契约定义保持在原有位置
3. **注册范围 = domain/ports + application/ports** - 两者都是端口契约的来源

### 架构说明

| 端口来源 | 目录 | 数量 | 说明 |
|----------|------|------|------|
| Domain层 | `src/domain/ports/` | 37 | 领域层核心端口（存储抽象、仓储、认证授权、事件发布等） |
| Application层 | `src/application/ports/` | 7 | 应用层服务端口（语义缓存、公共黑板、沙箱、指标等） |
| 服务内Protocol | `src/domain/services/` | 6 | 待迁移到 domain/ports/ |

**两者职责分离**：
- **domain/ports**: 领域核心业务接口，定义业务能力边界
- **application/ports**: 应用层服务接口，定义技术实现需求

---

---

## 重构背景

### 问题发现

基于 `sisys-port-impl-report.md` 全面调研，发现以下问题：

| 问题类别 | 发现 | 影响 |
|----------|------|------|
| **服务内Protocol定义** | 5个服务文件本地定义了6个Protocol（含1个重复定义的EventPublisherProtocol） | 违反六边形架构，接口重复 |
| **导出完整性** | `domain/ports/__init__.py` 仅导出16个(33.3%)，缺失24个Protocol | 基础设施层无法正确导入 |
| **EventBusFactory** | 3个组件(_redis_publisher/_redis_subscriber/_rabbitmq_publisher)初始化为None | 运行时触发AttributeError |
| **接口冗余** | L3: VectorStorage↔L3VectorPort(缺CollectionManager); L5: GraphManager/GraphStorage↔L5GraphPort(缺get_neighbors); L4: ObjectStorageRepository↔L4ObjectPort | 架构模糊，实现混淆 |
| **Infrastructure依赖Application** | 7处违规导入(role_repository.py的Exception×2 + MetricsPort×1 + ExceptionMetricsPort×1 + SandboxExecutor×2 + EventSubscriber×1) | 违反依赖倒置原则 |
| **跨模块继承** | SQLAlchemy模型继承infrastructure的Base | Domain层绑定具体技术 |
| **无统一注册机制** | 端口分散定义，无中心化管理 | 可插拔系统难以维护 |

### 核心目标

| 目标 | 现状 | 目标状态 |
|------|------|----------|
| 建立统一端口注册管理机制 | 端口分散定义 | 4层架构：契约→注册→解析→门禁 |
| 消除服务内Protocol定义 | 5个服务文件本地定义了6个Protocol(含重复) | 全部迁移到domain/ports/ |
| 补全__init__.py导出 | 16/48符号已导出(33.3%) | 导出所有Protocol(100%) |
| 消除Infrastructure依赖Application | 7处违规导入 | 通过Domain层定义Exception解决（不迁移application/ports） |
| 合并语义重复接口 | L3: VectorStorage↔L3VectorPort; L5: GraphManager/GraphStorage↔L5GraphPort; L4: ObjectStorageRepository↔L4ObjectPort | 统一为单一契约 |
| 修复EventBusFactory | 3个组件为None | 延迟初始化+单例复用 |
| 修复跨模块继承 | SQLAlchemy模型继承infrastructure的Base | Domain层使用无技术绑定Base或DeclarativeBase |

### 重构原则

1. **依赖倒置**: Domain层定义端口，Infrastructure层实现，双方都依赖抽象
2. **统一注册**: 所有端口必须注册到中心registry，业务只拿"契约"不碰"实现"
3. **单一契约**: 同一类能力只保留一个主契约，禁止语义重复接口并存
4. **Composition Root**: 所有端口、适配器、实现类只在组合根完成注册
5. **契约门禁**: 每个端口必须有契约测试，注册表变更必须触发兼容性检查

---

## 一、统一端口注册管理机制（4层架构）

### 1.1 架构概述

```
┌─────────────────────────────────────────────────────────────────────┐
                     Composition Root (组合根)                           │
               所有端口、适配器、实现类在此完成注册                         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 4: Contract Gate (契约门禁层)                                  │
│  - 契约测试验证接口兼容性                                              │
│  - 版本与兼容策略检查                                                 │
│  - 注册表变更触发CI检查                                               │
└─────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 3: Resolver (解析层)                                          │
│  - resolve(port_name) 获取实现                                        │
│  - 依赖注入获取接口实例                                                │
│  - 多实现时按配置/环境/租户/场景选择                                   │
└─────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 2: Registry (注册层)                                          │
│  - PortSpec 元数据中心                                                │
│  - name/version/interface/impl/module/lifetime/owner                 │
└─────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1: Port Contract (契约层)                                      │
│  - 接口定义在 domain/ports/ (37个) 和 application/ports/ (7个)       │
│  - 只定义行为，不含实现                                                │
│  - 两者各有用途，独立共存                                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Layer 1: Port Contract（契约层）

**原则**: 端口契约定义在原有位置（domain/ports/ 和 application/ports/），不放业务实现。同一类能力只保留一个主契约。

**端口契约来源**：
- `src/domain/ports/` - 领域层核心端口（存储抽象、仓储、认证授权、事件发布等）
- `src/application/ports/` - 应用层服务端口（语义缓存、公共黑板、沙箱、指标等）

两者**各有用途，独立共存**，不需要相互迁移。

```python
# src/domain/ports/__init__.py
"""领域层端口 — 核心业务接口定义

按功能模块组织：
- 存储分层: l0_storage, l1_cache, l2_rdb, l3_vector, l4_object, l5_graph
- 仓储: user_repository, role_repository, audit_repository
- 认证授权: auth_service, permission_service, token_blacklist
- 事件: event_publisher
- 合规: compliance_gateway, sensitive_data_detector
"""

# src/application/ports/__init__.py
"""应用层端口 — 应用服务接口定义

按功能模块组织：
- 缓存: semantic_cache
- 协作: public_blackboard
- 沙箱: sandbox_port
- 监控: metrics_port, exception_metrics_port
- 文本处理: text_extractor_service, compressor_service
- 事件: event_subscriber
"""
```

**契约定义规范**:
```python
# src/domain/ports/user_repository.py
"""用户仓储端口契约"""

from __future__ import annotations

from typing import Protocol, UUID
from src.domain.entities.user import User


class UserRepositoryPort(Protocol):
    """用户数据访问接口

    定义用户数据的持久化操作。
    所有用户仓储实现必须实现此接口。
    """

    async def get_by_id(self, user_id: UUID) -> User | None:
        """根据ID获取用户"""
        ...

    async def get_by_username(self, username: str) -> User | None:
        """根据用户名获取用户"""
        ...

    async def save(self, user: User) -> None:
        """保存用户"""
        ...

    async def delete(self, user_id: UUID) -> None:
        """删除用户"""
        ...
```

### 1.3 Layer 2: Registry（注册层）

**原则**: 所有端口统一登记到中心registry，记录元数据。

```python
# src/domain/ports/registry.py
"""端口注册中心 — 统一管理所有端口定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Type
import logging

logger = logging.getLogger(__name__)


class Lifetime(Enum):
    """端口生命周期"""
    TRANSIENT = "transient"  # 每次请求创建新实例
    SCOPED = "scoped"        # 每作用域单例
    SINGLETON = "singleton"   # 全局单例


@dataclass(frozen=True)
class PortSpec:
    """端口规格元数据"""
    name: str                           # 端口唯一名称
    version: str                        # 版本号 (semver)
    interface: Type[Protocol]          # 接口类型
    impl: Type | Callable[..., Any] | str  # 实现类型、工厂函数或模块路径（用于延迟导入）
    module: str                         # 实现所在模块
    lifetime: Lifetime = Lifetime.SCOPED  # 生命周期
    owner: str = ""                     # 负责人/团队
    compatibility: tuple[str, ...] = () # 兼容版本列表
    tags: tuple[str, ...] = ()         # 标签（用于场景选择）
    deprecated: bool = False            # 是否已废弃


class PortRegistry:
    """端口注册中心

    单例模式，确保全局唯一的端口注册表。
    """

    _instance: PortRegistry | None = None
    _ports: dict[str, PortSpec] = field(default_factory=dict)

    def __new__(cls) -> PortRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._ports = {}
        return cls._instance

    def register(self, spec: PortSpec) -> None:
        """注册端口

        Args:
            spec: 端口规格

        Raises:
            ValueError: 端口名称已存在
        """
        if spec.name in self._ports:
            raise ValueError(f"Port already registered: {spec.name}")
        logger.info(f"Registering port: {spec.name} ({spec.version})")
        self._ports[spec.name] = spec

    def get(self, name: str) -> PortSpec | None:
        """获取端口规格"""
        return self._ports.get(name)

    def get_by_interface(self, interface: Type[Protocol]) -> PortSpec | None:
        """根据接口类型获取端口规格"""
        for spec in self._ports.values():
            if spec.interface is interface:
                return spec
            # 防止Protocol的issubclass调用失败
            if isinstance(interface, type) and isinstance(spec.interface, type):
                if issubclass(spec.interface, interface):
                    return spec
        return None

    def list_all(self) -> list[PortSpec]:
        """列出所有已注册端口"""
        return list(self._ports.values())

    def list_by_tag(self, tag: str) -> list[PortSpec]:
        """根据标签筛选端口"""
        return [spec for spec in self._ports.values() if tag in spec.tags]

    def unregister(self, name: str) -> None:
        """取消注册端口"""
        if name in self._ports:
            del self._ports[name]
            logger.info(f"Unregistered port: {name}")

    def __contains__(self, name: str) -> bool:
        return name in self._ports

    def __len__(self) -> int:
        return len(self._ports)


# 全局注册表实例
_global_registry = PortRegistry()


def register_port(
    name: str,
    version: str,
    interface: Type[Protocol],
    impl: Type | Callable[..., Any],
    module: str,
    **kwargs,
) -> None:
    """便捷的端口注册函数

    用法:
        register_port(
            name="user_repo",
            version="v1.0.0",
            interface=UserRepositoryPort,
            impl=SqlAlchemyUserRepository,
            module="infrastructure.user_repo",
            lifetime=Lifetime.SCOPED,
            owner="platform-team",
        )
    """
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

### 1.4 Layer 3: Resolver（解析层）

**原则**: 业务只调用 `resolve()` 或注入接口，不允许直接 import 实现类。

```python
# src/domain/ports/resolver.py
"""端口解析器 — 依赖注入容器"""

from __future__ import annotations

from typing import Any, Generator, Type, TypeVar
import logging

from src.domain.ports.registry import (
    PortRegistry,
    PortSpec,
    Lifetime,
    _global_registry,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Resolver:
    """依赖注入解析器

    负责从注册表获取端口实现并实例化。
    支持构造函数注入和属性注入。
    """

    def __init__(
        self,
        registry: PortRegistry | None = None,
        overrides: dict[str, Any] | None = None,
    ):
        """初始化解析器

        Args:
            registry: 端口注册表，默认使用全局注册表
            overrides: 端口覆盖映射，用于测试
        """
        self._registry = registry or _global_registry
        self._overrides = overrides or {}
        self._instances: dict[str, Any] = {}
        self._scoped_context: dict[str, Any] = {}

    def resolve(self, port_name: str) -> Any:
        """解析端口获取实例

        Args:
            port_name: 端口名称

        Returns:
            端口实例

        Raises:
            KeyError: 端口未注册
            RuntimeError: 端口已废弃
        """
        # 检查覆盖
        if port_name in self._overrides:
            return self._overrides[port_name]

        spec = self._registry.get(port_name)
        if spec is None:
            raise KeyError(f"Port not registered: {port_name}")

        if spec.deprecated:
            logger.warning(f"Using deprecated port: {port_name}")

        return self._create_instance(spec)

    def resolve_by_interface(self, interface: Type[T]) -> T:
        """根据接口类型解析端口

        Args:
            interface: 接口类型

        Returns:
            端口实例
        """
        spec = self._registry.get_by_interface(interface)
        if spec is None:
            raise KeyError(f"Port not found for interface: {interface.__name__}")
        return self._create_instance(spec)

    def _create_instance(self, spec: PortSpec) -> Any:
        """创建端口实例"""
        # 根据生命周期管理实例
        if spec.lifetime == Lifetime.SINGLETON:
            if spec.name not in self._instances:
                self._instances[spec.name] = self._instantiate(spec)
            return self._instances[spec.name]

        elif spec.lifetime == Lifetime.SCOPED:
            if spec.name not in self._scoped_context:
                self._scoped_context[spec.name] = self._instantiate(spec)
            return self._scoped_context[spec.name]

        else:  # TRANSIENT
            return self._instantiate(spec)

    def _instantiate(self, spec: PortSpec) -> Any:
        """实例化端口"""
        if callable(spec.impl) and not isinstance(spec.impl, type):
            # 工厂函数
            return spec.impl(resolver=self)
        else:
            # 直接类型 - 尝试自动注入依赖
            return self._auto_inject(spec.impl)

    def _auto_inject(self, cls: Type[T]) -> T:
        """自动注入构造函数依赖"""
        import inspect
        sig = inspect.signature(cls.__init__)
        kwargs = {}
        failures = []

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            if param.annotation is inspect.Parameter.empty:
                continue

            # 获取参数类型注解
            param_type = param.annotation

            # 尝试解析依赖
            try:
                # 优先按名称查找
                instance = self.resolve(param_name)
                kwargs[param_name] = instance
            except KeyError:
                try:
                    # 按接口类型查找
                    instance = self.resolve_by_interface(param_type)
                    kwargs[param_name] = instance
                except KeyError:
                    # 无法自动注入，使用默认值或记录失败
                    if param.default is inspect.Parameter.empty:
                        failures.append(param_name)
                    else:
                        kwargs[param_name] = param.default

        if failures:
            raise RuntimeError(f"Cannot resolve required dependencies for {cls.__name__}: {failures}")

        return cls(**kwargs)

    def clear_scoped(self) -> None:
        """清除作用域实例（请求结束时调用）"""
        self._scoped_context.clear()

    def clear_singleton(self) -> None:
        """清除单例实例"""
        self._instances.clear()


# 默认全局解析器
_default_resolver: Resolver | None = None


def get_resolver() -> Resolver:
    """获取全局解析器实例"""
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = Resolver()
    return _default_resolver


def resolve(port_name: str) -> Any:
    """全局解析函数"""
    return get_resolver().resolve(port_name)
```

### 1.5 Layer 4: Contract Gate（契约门禁层）

**原则**: 每个端口必须有契约测试，注册表变更必须触发兼容性检查。

```python
# src/domain/ports/contract_gate.py
"""契约门禁 — 端口兼容性检查"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Type
import logging

from src.domain.ports.registry import PortSpec

logger = logging.getLogger(__name__)


@dataclass
class CompatibilityResult:
    """兼容性检查结果"""
    port_name: str
    old_version: str
    new_version: str
    is_compatible: bool
    breaking_changes: list[str]
    warnings: list[str]


class ContractGate:
    """契约门禁

    检查端口变更的兼容性，确保升级不会破坏现有功能。
    """

    def check_compatibility(
        self,
        old_spec: PortSpec,
        new_spec: PortSpec,
    ) -> CompatibilityResult:
        """检查两个版本的兼容性

        Args:
            old_spec: 旧版本规格
            new_spec: 新版本规格

        Returns:
            兼容性检查结果
        """
        breaking_changes = []
        warnings = []

        # 检查接口变更
        if old_spec.interface is not new_spec.interface:
            old_methods = self._get_methods(old_spec.interface)
            new_methods = self._get_methods(new_spec.interface)

            # 检查方法删除
            for method in old_methods:
                if method not in new_methods:
                    breaking_changes.append(f"Removed method: {method}")

            # 检查方法签名变更
            for method in new_methods:
                if method in old_methods:
                    old_sig = old_methods[method]
                    new_sig = new_methods[method]
                    if old_sig != new_sig:
                        breaking_changes.append(
                            f"Changed signature: {method} ({old_sig} -> {new_sig})"
                        )

        # 检查生命周期变更
        if old_spec.lifetime != new_spec.lifetime:
            warnings.append(
                f"Lifetime changed: {old_spec.lifetime} -> {new_spec.lifetime}"
            )

        return CompatibilityResult(
            port_name=old_spec.name,
            old_version=old_spec.version,
            new_version=new_spec.version,
            is_compatible=len(breaking_changes) == 0,
            breaking_changes=breaking_changes,
            warnings=warnings,
        )

    def _get_methods(self, interface: Type) -> dict[str, str]:
        """获取接口的所有方法签名"""
        import inspect
        methods = {}
        for name in dir(interface):
            if name.startswith("_"):
                continue
            obj = getattr(interface, name)
            if callable(obj) or isinstance(obj, property):
                try:
                    sig = inspect.signature(obj)
                    methods[name] = str(sig)
                except (ValueError, TypeError):
                    pass
        return methods


# 契约测试基类
class PortContractTest:
    """端口契约测试基类

    所有端口实现必须继承此类并实现契约测试。
    """

    @classmethod
    def get_port_name(cls) -> str:
        """返回被测试的端口名称"""
        raise NotImplementedError

    @classmethod
    def get_implementation(cls) -> Any:
        """返回被测试的实现实例"""
        raise NotImplementedError

    def run_contract_tests(self) -> None:
        """运行契约测试

        由CI调用，验证实现是否符合契约。
        """
        port_name = self.get_port_name()
        impl = self.get_implementation()

        logger.info(f"Running contract tests for: {port_name}")

        # 获取端口规格
        from src.domain.ports.registry import _global_registry
        spec = _global_registry.get(port_name)
        if spec is None:
            raise RuntimeError(f"Port not registered: {port_name}")

        # 验证实现实现了正确的方法
        self._verify_implements_interface(impl, spec.interface)

        # 运行具体契约测试
        self.test_contract()

    def _verify_implements_interface(
        self,
        impl: Any,
        interface: Type,
    ) -> None:
        """验证实现实现了接口"""
        if not isinstance(impl, interface) and not issubclass(type(impl), interface):
            raise AssertionError(
                f"Implementation {type(impl)} does not implement {interface}"
            )

    def test_contract(self) -> None:
        """子类实现具体契约测试"""
        raise NotImplementedError
```

### 1.6 Composition Root（组合根）

**原则**: 所有端口、适配器、实现类只允许在组合根完成注册。

```python
# src/composition_root.py
"""Composition Root — 组合根

所有端口、适配器、实现类的注册必须在此文件完成。
禁止在其他模块进行注册。

这是唯一允许直接 import infrastructure 实现的文件。
"""

from __future__ import annotations

import logging
from src.domain.ports.registry import (
    register_port,
    Lifetime,
)
from src.domain.ports.contracts.user_repository import UserRepositoryPort
from src.domain.ports.contracts.cache import L1CachePort
from src.domain.ports.contracts.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


def bootstrap() -> None:
    """引导函数 — 初始化所有端口注册

    在应用启动时调用。
    """
    logger.info("Bootstrapping port registry...")

    # === 存储层 ===
    register_port(
        name="l0_storage",
        version="v1.0.0",
        interface=L1CachePort,  # 复用同一接口
        impl="src.infrastructure.storage.file_memory_adapter.FileMemoryAdapter",
        module="src.infrastructure.storage.file_memory_adapter",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
    )

    register_port(
        name="l1_cache",
        version="v1.0.0",
        interface=L1CachePort,
        impl="src.infrastructure.storage.redis.redis_memory_cache.RedisMemoryCache",
        module="src.infrastructure.storage.redis.redis_memory_cache",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
        tags=("redis", "cache"),
    )

    # === 用户仓储 ===
    register_port(
        name="user_repo",
        version="v1.0.0",
        interface=UserRepositoryPort,
        impl="src.infrastructure.storage.postgresql.user_repository.SqlAlchemyUserRepository",
        module="src.infrastructure.storage.postgresql.user_repository",
        lifetime=Lifetime.SCOPED,
        owner="platform-team",
        compatibility=("v0.x",),
    )

    # === 事件发布 ===
    register_port(
        name="event_publisher",
        version="v1.0.0",
        interface=EventPublisher,
        impl="src.infrastructure.messaging.dual_channel_event_bus.DualChannelEventBus",
        module="src.infrastructure.messaging.dual_channel_event_bus",
        lifetime=Lifetime.SINGLETON,
        owner="messaging-team",
        tags=("redis", "rabbitmq"),
    )

    logger.info(f"Registered {len(_global_registry.list_all())} ports")


# 全局注册表引用
__all__ = ["bootstrap", "_global_registry", "resolve", "Resolver"]
```

### 1.7 使用示例

**业务代码（只使用契约）**:
```python
# src/domain/services/user_service.py
"""用户服务 — 业务代码只依赖端口契约"""

from __future__ import annotations

import logging
from uuid import UUID

from src.domain.ports.contracts.user_repository import UserRepositoryPort
from src.domain.ports.resolver import resolve

logger = logging.getLogger(__name__)


class UserService:
    """用户服务

    通过构造函数注入依赖，不直接实例化实现。
    """

    def __init__(self, user_repo: UserRepositoryPort):
        """初始化用户服务

        Args:
            user_repo: 用户仓储端口（由容器注入）
        """
        self._user_repo = user_repo

    async def get_user(self, user_id: UUID) -> dict | None:
        """获取用户"""
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            return None
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
        }


# 工厂函数（用于自动注入）
def create_user_service() -> UserService:
    """创建用户服务实例（由解析器调用）"""
    user_repo = resolve("user_repo")
    return UserService(user_repo=user_repo)
```

**测试代码（使用override）**:
```python
# tests/unit/test_user_service.py
"""用户服务单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.domain.services.user_service import UserService
from src.domain.ports.resolver import Resolver
from src.domain.ports.contracts.user_repository import UserRepositoryPort


@pytest.fixture
def mock_user_repo():
    """模拟用户仓储"""
    repo = AsyncMock(spec=UserRepositoryPort)
    return repo


@pytest.fixture
def user_service(mock_user_repo):
    """创建使用模拟仓储的用户服务"""
    return UserService(user_repo=mock_user_repo)


@pytest.mark.asyncio
async def test_get_user(user_service, mock_user_repo):
    """测试获取用户"""
    # 设置模拟
    mock_user = MagicMock()
    mock_user.id = "test-id"
    mock_user.username = "testuser"
    mock_user.email = "test@example.com"
    mock_user_repo.get_by_id.return_value = mock_user

    # 执行
    result = await user_service.get_user("test-id")

    # 验证
    assert result is not None
    assert result["username"] == "testuser"
    mock_user_repo.get_by_id.assert_called_once()
```

---

## 二、接口清单（契约层）

### 2.0 契约清单执行约束（强制）

> **本清单是唯一合法端口来源（Single Source of Truth），不是文档而是系统约束。**

**端口契约来自两个独立来源（各有用途，不需要迁移）：**
- `src/domain/ports/` - 领域层核心端口（37个）
- `src/application/ports/` - 应用层服务端口（7个）

**所有开发必须满足以下约束：**

1. **禁止定义未在本清单登记的端口**
2. **禁止新增端口未同步更新本清单**
3. **禁止存在语义重复端口**（必须合并）
4. **每个端口必须满足：**
   - 已定义在 domain/ports/ 或 application/ports/
   - 已在 registry 注册
   - 已有 contract test
   - 已声明 owner + version

**违反任一条 → CI 必须失败**

#### 2.0.1 契约清单自动校验

```bash
# 检查1: 禁止service内定义Protocol
grep -r "class.*Protocol" src/domain/services/ src/application/event_handlers/ && exit 1

# 检查2: 禁止未注册端口被使用
python -c "
from src.domain.ports.registry import _global_registry
expected = 48
actual = len(_global_registry.list_all())
assert actual >= expected, f'Ports {actual} < {expected}'
"

# 检查3: 禁止重复接口（名称重复）
python scripts/check_duplicate_ports.py

# 检查4: 禁止废弃接口仍被使用
grep -r "VectorStorage\|GraphManager\|GraphStorage" src/ --include="*.py" | grep -v "__pycache__" && exit 1
```

#### 2.0.2 契约变更流程

| 变更类型 | 必须操作 |
|---------|---------|
| 新增端口 | 定义contract → 注册registry → 写contract test → 更新本清单 → 指定owner |
| 修改端口 | 更新版本(semver) → 运行ContractGate兼容性检查 → 更新本清单 |
| 废弃端口 | 标记deprecated → 更新本清单 → 扫描所有引用 → 迁移后删除 |

### 2.1 契约层端口（实际统计与目标状态）

> **⚠️ 实际统计（Round 1调研结果）**:
> - `src/domain/ports/*.py` 定义: **35个Python文件，~30个Protocol接口**
> - `src/domain/services/*.py` 定义: **5个Protocol**（6个含1个重复EventPublisherProtocol）
> - `src/application/ports/*.py` 定义: **8个Protocol**（不是7个）
> - **合计**: ~43个（不含冗余）
>
> **目标状态**: 清理后约 **43个**
>
> **差异原因**: 部分接口存在冗余定义（VectorStorage≈L3VectorPort等），需合并

**端口契约来源（两者各有用途，独立共存）：**

| 来源 | 目录 | 端口数 | 说明 |
|------|------|--------|------|
| Domain层 | `src/domain/ports/` | ~30 | 领域层核心端口（存储抽象、仓储、认证授权、事件发布等） |
| Application层 | `src/application/ports/` | 8 | 应用层服务端口（语义缓存、公共黑板、沙箱、指标等） |
| 服务内Protocol | `src/domain/services/` | 5 | 待迁移到domain/ports/（不含重复的EventPublisherProtocol，废弃删除EventPublisherProtocol直接引用EventPublisher） |

**P0问题发现（Round 1+2 共22项）：**

| # | 问题 | 影响 | 优先级 |
|---|------|------|--------|
| P0-1 | L3VectorPort缺少Collection管理方法 | VectorStorage可替代，但L3VectorPort不完整 | **必须修复** |
| P0-2 | L4ObjectPort缺少list_objects方法 | ObjectStorageRepository可替代，但L4ObjectPort不完整 | **必须修复** |
| P0-3 | L5GraphPort已完整覆盖GraphManager/GraphStorage功能 | 建议废弃后者 | 建议 |
| P0-4 | EventPublisherProtocol在2个服务内重复定义 | DRY违规 | **必须修复** |
| P0-5 | EventBusFactory 3个组件初始化为None | 运行时AttributeError | **必须修复** |
| P0-6 | EventBusFactory核心依赖未初始化 | RedisEventBus/RabbitMQEventBus使用无效依赖 | **必须修复** |
| P0-7 | RedisEventPublisher.publish()返回None但硬编码成功 | 发布失败也返回成功状态 | **必须修复** |
| P0-8 | RedisEventBus.publish()异常处理逻辑不可达 | publisher吞掉异常，redis_success=False永不触发 | **必须修复** |
| P0-9 | 5个Domain Services Protocol均无实现类 | 接口契约无法验证 | **必须修复** |
| P0-10 | SemanticRouterProtocol.route()为async但HashRouterProtocol.route()为sync | 接口设计不一致 | **建议修复** |
| P0-11 | memory_service.py第475行调用publish无await | async def未正确调用 | **必须修复** |
| P0-12 | UserRepository继承的BaseRepository与domain层BaseRepository同名不同文件 | 混淆风险 | **必须修复** |
| P0-13 | RoleRepository.list_all()签名与RoleRepositoryPort不匹配 | 分页参数缺失 | **必须修复** |
| P0-14 | RoleRepository.delete()返回bool但BaseRepository.delete()返回None | 三者不一致 | **必须修复** |
| P0-15 | UserRepositoryPort缺少save/delete/list_all方法 | 无法使用完整CRUD | **必须修复** |
| P0-16 | PermissionServicePort实现添加了assign_role/revoke_role | 超出接口范围 | **必须修复** |
| P0-17 | TokenBlacklistPort.add()签名不一致 | 接口add(token)实现add(token, ttl=None) | **必须修复** |
| P0-18 | CrossBorderTransferServicePort和WhitelistServicePort实现添加了接口未定义的方法 | 接口契约破损 | **必须修复** |
| P0-19 | 缺少EncryptionPort领域端口 | EncryptionService是具体类，违反依赖倒置 | **必须修复** |
| P0-20 | L4ObjectPort.archive()方法签名不一致 | MinIORepository返回bool与接口str不匹配 | **必须修复** |
| P0-21 | L1CachePort仅定义缓存操作，缺少pub/sub接口定义 | RedisPublicBlackboard未抽象为L1适配器 | **建议修复** |
| P0-22 | AuthServiceImpl.authenticate()存在timing attack防御逻辑缺陷 | result变量未使用 | **建议修复** |

**端口状态更新（Round 2）：**

| 端口名 | 契约文件 | 用途 | 实现模块 | 状态 |
|--------|----------|------|----------|------|
| **Domain层 - 存储分层（L0-L5）** |
| `L0StoragePort` | domain/ports/l0_storage.py | L0文件系统 | infrastructure | **✅接口完整** |
| `L1CachePort` | domain/ports/l1_cache.py | L1 Redis缓存 | infrastructure | **✅接口完整(⚠️缺pub/sub)** |
| `L2MetadataRepositoryPort` | domain/ports/l2_rdb.py | L2元数据 | infrastructure | **✅接口完整** |
| `L2ChangeHistoryRepositoryPort` | domain/ports/l2_rdb.py | L2变更历史 | infrastructure | **✅接口完整** |
| `L2GroupMemberRepositoryPort` | domain/ports/l2_rdb.py | L2群组成员 | infrastructure | **✅接口完整** |
| `L3VectorPort` | domain/ports/l3_vector.py | L3向量存储 | infrastructure | **⚠️缺Collection管理方法** |
| `L4ObjectPort` | domain/ports/l4_object.py | L4对象存储 | infrastructure | **⚠️缺list_objects方法** |
| `L5GraphPort` | domain/ports/l5_graph.py | L5图存储 | infrastructure | **✅已完整** |
| `UnifiedStoragePort` | domain/ports/unified_storage.py | 统一存储入口 | infrastructure | **待注册** |
| `SessionStorage` | domain/ports/session_storage.py | 会话状态存储 | infrastructure | **待注册** |
| `IndexManagerPort` | domain/ports/index_manager.py | MEMORY索引 | infrastructure | **待注册** |
| **废弃接口（待清理）** |
| ~~`VectorStorage`~~ | domain/ports/vector_storage.py | L3向量存储 | — | **废弃** |
| ~~`CollectionManager`~~ | domain/ports/vector_storage.py | Collection管理 | — | **废弃** |
| ~~`ObjectStorageRepository`~~ | domain/ports/storage.py | L4对象存储 | — | **废弃** |
| ~~`GraphManager`~~ | domain/ports/graph_storage.py | L5图管理 | — | **废弃** |
| ~~`GraphStorage`~~ | domain/ports/graph_storage.py | L5图存储 | — | **废弃** |
| **Domain层 - 仓储** |
| `UserRepositoryPort` | domain/ports/user_repository.py | 用户数据访问 | infrastructure | **⚠️缺save/delete/list_all** |
| `RoleRepositoryPort` | domain/ports/role_repository.py | 角色存储 | infrastructure | **⚠️签名不一致** |
| `UserRoleRepositoryPort` | domain/ports/user_role_repository.py | 用户-角色关联 | infrastructure | **待注册** |
| `LoginAttemptRepositoryPort` | domain/ports/login_attempt_repository.py | 登录尝试跟踪 | infrastructure | **待注册** |
| `AuditRepositoryPort` | domain/ports/audit_repository.py | 审计日志存储 | infrastructure | **✅接口完整** |
| `AuditServicePort` | domain/ports/audit_service.py | 审计服务 | infrastructure | **✅接口完整** |
| **Domain层 - 认证授权** |
| `AuthServicePort` | domain/ports/auth_service.py | 认证服务 | infrastructure | **✅接口完整** |
| `PermissionServicePort` | domain/ports/permission_service.py | 权限检查 | infrastructure | **⚠️实现超出接口范围** |
| `TokenBlacklistPort` | domain/ports/token_blacklist.py | JWT黑名单 | infrastructure | **⚠️签名不一致** |
| `PasswordValidationServicePort` | domain/ports/password_validation_service.py | 密码验证 | infrastructure | **✅接口完整** |
| **Domain层 - 事件** |
| `EventPublisher` | domain/ports/event_publisher.py | 领域事件发布 | infrastructure | **✅接口完整** |
| **Domain层 - 合规服务** |
| `ComplianceGatewayPort` | domain/ports/compliance_gateway.py | UDMR合规检查 | infrastructure | **✅接口完整** |
| `SensitiveDataDetectorPort` | domain/ports/sensitive_data_detector.py | 敏感数据检测 | infrastructure | **✅接口完整** |
| `DataResidencyEnforcerPort` | domain/ports/data_residency_enforcer.py | 数据驻留强制 | infrastructure | **✅接口完整** |
| `WhitelistServicePort` | domain/ports/whitelist_service.py | 白名单服务 | infrastructure | **⚠️实现超出接口范围** |
| `PIPLComplianceServicePort` | domain/ports/pipl_compliance_service.py | PIPL合规 | infrastructure | **✅接口完整** |
| `CrossBorderTransferServicePort` | domain/ports/cross_border_transfer_service.py | 跨境传输 | infrastructure | **⚠️实现超出接口范围** |
| **Domain层 - 其他** |
| `OutboxRepository` | domain/ports/outbox.py | 事务发件箱 | infrastructure | **待注册** |
| `UnitOfWork` | domain/ports/unit_of_work.py | 工作单元 | infrastructure | **待注册** |
| `HealthCheckPort` | domain/ports/health_check.py | 健康检查 | infrastructure | **待注册** |
| `IntegrityPort` | domain/ports/integrity.py | 完整性检查 | infrastructure | **待注册** |
| `BaseRepository` | domain/ports/base.py | 通用仓储基类 | — | **⚠️同名不同文件冲突** |
| `StorageLayer` | domain/ports/storage_enums.py | 存储层级枚举 | — | **参考使用** |
| **服务内Protocol（待迁移或引用）** |
| `SandboxExecutorProtocol` | domain/services/auto_execute_service.py | 沙箱执行 | — | **⚠️无实现类** |
| `SnapshotRepositoryProtocol` | domain/services/auto_execute_service.py | 快照存储 | — | **⚠️无实现类** |
| `HashRouterProtocol` | domain/services/auto_route_service.py | 哈希路由 | — | **⚠️无实现类** |
| `SemanticRouterProtocol` | domain/services/auto_route_service.py | 语义路由 | — | **⚠️无实现类** |
| ~~`EventPublisherProtocol`~~ | 2处服务内定义 | 事件发布 | — | **废弃→直接引用EventPublisher** |
| **Application层 - 服务端口（保留，不迁移）** |
| `SemanticCache` | application/ports/semantic_cache.py | 语义缓存 | infrastructure | **待注册** |
| `PublicBlackboard` | application/ports/public_blackboard.py | 公共黑板 | infrastructure | **待注册** |
| `SandboxExecutor` | application/ports/sandbox_port.py | 沙箱执行器 | infrastructure | **待注册** |
| `MetricsPort` | application/ports/metrics_port.py | 指标端口 | infrastructure | **待注册** |
| `ExceptionMetricsPort` | application/ports/exception_metrics_port.py | 异常指标 | infrastructure | **待注册** |
| `EventSubscriber` | application/ports/event_subscriber.py | 事件订阅器 | infrastructure | **✅接口完整** |
| `TextExtractorService` | application/ports/text_extractor_service.py | 文本提取 | infrastructure | **待注册** |
| `CompressorService` | application/ports/compressor_service.py | 压缩服务 | infrastructure | **待注册** |

### 2.1.1 SessionStorage与L1CachePort协作关系

```
SessionStoragePort 与 L1CachePort 关系:
- [ ] L1CachePort: 通用的键值缓存抽象
- [ ] SessionStoragePort: 专用于会话状态，底层可复用L1CachePort实现
- [ ] 建议: SessionStoragePort 实现应委托给 L1CachePort，不独立管理连接
```

### 2.2 禁止的命名模式

以下命名模式禁止使用，禁止语义重复：

```python
# 禁止模式示例
UserService           # 混淆：Service是实现还是接口？
IUserService          # 前缀I是C#风格，不是Python风格
UserServicePort       # Port后缀与实际Protocol重复
UserRepo             # 过短，不够清晰
UserRepository       # 与UserRepositoryPort重复

# 正确模式
UserRepositoryPort   # 明确是Port接口
UserCachePort        # 明确是缓存接口
UserAuthServicePort   # 明确是认证服务接口
```

---

## 三、注册规范

### 3.1 PortSpec 元数据规范

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | str | 是 | 端口唯一名称，格式：`{entity}_{capability}Port` |
| `version` | str | 是 | SemVer格式，如 `v1.0.0` |
| `interface` | Type[Protocol] | 是 | 接口类型 |
| `impl` | Type \| Callable | 是 | 实现类型或工厂函数 |
| `module` | str | 是 | 实现所在模块路径 |
| `lifetime` | Lifetime | 否 | 默认 SCOPED |
| `owner` | str | 否 | 负责团队或个人 |
| `compatibility` | tuple[str] | 否 | 兼容版本列表 |
| `tags` | tuple[str] | 否 | 用于场景/环境选择的标签 |
| `deprecated` | bool | 否 | 是否已废弃 |

### 3.2 生命周期规范

| Lifetime | 使用场景 |
|----------|----------|
| `SINGLETON` | 无状态服务、工厂、事件总线 |
| `SCOPED` | 有状态服务、仓储、HTTP请求级服务 |
| `TRANSIENT` | 每次使用创建新实例、轻量级工具 |

### 3.3 注册检查

```bash
# 验证所有端口已注册
python -c "
from src.composition_root import registry
missing = []

# 检查核心端口
required_ports = [
    'user_repo', 'l1_cache', 'event_publisher',
    'auth_service', 'permission_service'
]

for port in required_ports:
    if port not in registry:
        missing.append(port)

if missing:
    print(f'Missing ports: {missing}')
    exit(1)
print(f'All {len(registry)} ports registered')
"
```

---

## 四、约束规则

### 4.1 绝对禁止规则

| 规则 | 违规示例 | 正确做法 |
|------|----------|----------|
| 禁止业务代码 import 实现 | `from infra.user_repo import SqlAlchemyUserRepo` | `from domain.ports import UserRepositoryPort` |
| 禁止在服务内定义Protocol | `class Service: class Port(Protocol):` | 迁移到 domain/ports/ 目录 |
| 禁止直接实例化 | `repo = SqlAlchemyUserRepo()` | `repo = resolve("user_repo")` |
| 禁止Domain层使用技术绑定Base | `class UserModel(Base)` where Base is DeclarativeBase | 使用无技术绑定Base |
| 禁止使用废弃接口 | `VectorStorage`, `GraphManager`, `GraphStorage`, `ObjectStorageRepository` | 迁移到 L3VectorPort/L5GraphPort/L4ObjectPort |
| 禁止接口返回类型不一致 | 本地Protocol返回None，正式Port返回PublishResult | 统一EventPublisherPort返回类型 |

### 4.2 架构约束集成

**pre-commit hooks**（使用已存在的 hexagonal_arch_guard.py 和 import-linter）:

```yaml
# .pre-commit-config.yaml 添加
- repo: local
  hooks:
    - id: hexagonal-arch-check
      name: "六边形架构检查"
      entry: poetry run python tests/utils/hexagonal_arch_guard.py
      language: system
      types: [python]
      pass_filenames: false
      stages: [push]

    - id: import-linter-check
      name: "Import-Linter 依赖约束"
      entry: poetry run import-linter lint
      language: system
      pass_filenames: false
      stages: [push]
```

### 4.3 允许规则

| 规则 | 示例 |
|------|------|
| 允许工厂函数 | `impl=lambda: SqlAlchemyUserRepo()` |
| 允许配置注入 | `impl=lambda config: SqlAlchemyUserRepo(config.db_url)` |
| 允许测试覆盖 | `resolver = Resolver(overrides={"user_repo": mock_repo})` |

---

## 五、重构执行顺序

### 5.1 Phase与P0问题映射

| Phase | 对应P0问题 | 验证标准 |
|-------|-----------|----------|
| 阶段1 | P0-19, P0-20 | domain/ports/ + application/ports/ 契约完整，无服务内Protocol |
| 阶段2 | P0-7, P0-8, P0-9 | registry包含所有端口(domain+application) |
| 阶段3 | P0-10, P0-11, P0-12 | EventBusFactory正确初始化，3组件非None |
| 阶段4 | P0-1~5, P0-6, P0-18, P0-24 | 服务内无Protocol定义，Exception违规导入修复，AutoRouteHandler事件发布修复 |
| 阶段5 | P0-13~P0-17 | 契约测试通过，覆盖所有端口 |
| 阶段6 | P0-21~P0-23 | 实现类声明实现对应Protocol |

### 5.2 详细执行步骤

```
阶段1: 契约层结构整理
- [ ] 1.1 整理 domain/ports/ 契约清单（37个）
  - [ ] 验证所有契约可被正确import
  - [ ] 验证契约定义无重复
- [ ] 1.2 整理 application/ports/ 契约清单（7个）
  - [ ] 验证所有契约可被正确import
  - [ ] 确认不需要迁移到domain层
- [ ] 1.3 迁移服务内Protocol到 domain/ports/
  - [ ] 迁移 SandboxExecutorProtocol → domain/ports/sandbox_executor_protocol.py
  - [ ] 迁移 SnapshotRepositoryProtocol → domain/ports/snapshot_repository_protocol.py
  - [ ] 废弃删除 EventPublisherProtocol → 直接引用EventPublisher（统一4处重复）
  - [ ] 迁移 HashRouterProtocol → domain/ports/hash_router_protocol.py
  - [ ] 迁移 SemanticRouterProtocol → domain/ports/semantic_router_protocol.py
  - [ ] 更新各服务文件导入
  - [ ] 验证: grep -r "class.*Protocol" src/domain/services/ 应返回空
- [ ] 1.4 废弃语义重复接口（VectorStorage, GraphManager, GraphStorage）
- [ ] 1.5 契约层完整性验证【关键检查点】
    - [ ] 1.5.1 验证所有契约可被正确import（domain + application）
    - [ ] 1.5.2 验证契约定义无重复（名称、接口）
    - [ ] 1.5.3 验证废弃接口(VectorStorage等)已移除
    - [ ] 1.5.4 验证服务内无Protocol定义
    - [ ] 1.5.5 生成契约清单（含name/interface/path/source）供后续registry对照

阶段2: 实现注册中心
- [ ] 2.1 实现 registry.py (PortRegistry, PortSpec, Lifetime)
- [ ] 2.2 实现 resolver.py (Resolver, resolve)
- [ ] 2.3 实现 contract_gate.py (ContractGate, PortContractTest)
- [ ] 2.4 注册中心完整性验证【关键检查点】
    - [ ] 2.4.1 验证registry.list_all()包含domain/ports和application/ports所有契约
    - [ ] 2.4.2 验证每个PortSpec包含完整字段(name/version/interface/impl/module)
    - [ ] 2.4.3 验证无重复注册(同一name)
    - [ ] 2.4.4 验证废弃端口(VectorStorage等)未注册
    - [ ] 2.4.5 验证resolver可正确解析已知端口

阶段3: 创建组合根 + 修复EventBusFactory
- [ ] 3.1 创建 composition_root.py
- [ ] 3.2 注册所有端口（domain/ports + application/ports）
- [ ] 3.3 修复EventBusFactory初始化(基于实际代码分析)
  - [ ] 3.3.1 问题A: _redis_publisher/_redis_subscriber/_rabbitmq_publisher初始化为None
        - [ ] 修复: 在__post_init__中创建RedisEventPublisher/RedisEventSubscriber/RabbitMQPublisher实例
  - [ ] 3.3.2 问题B: _get_outbox_repository()返回None
        - [ ] 修复: outbox_repository从外部注入,工厂使用前校验非None
  - [ ] 3.3.3 问题C: create_dual_channel_bus()中Poller初始化问题
        - [ ] 修复: 明确分离Poller创建逻辑,校验outbox_repository和_rabbitmq_publisher均非None
  - [ ] 3.3.4 使用@dataclass+__post_init__延迟初始化模式
        - [ ] 构造函数接收redis_config/rabbitmq_config/outbox_repository参数
    - [ ] 3.3.5 验证:
        - [ ] EventBusFactory.get_event_bus() 不抛出RuntimeError
        - [ ] EventBusFactory._redis_publisher/_redis_subscriber/_rabbitmq_publisher 非None

阶段3.5: 创建Domain异常定义【Phase 4前置条件】
- [ ] 3.5.1 创建 src/domain/exceptions/__init__.py
- [ ] 3.5.2 创建 src/domain/exceptions/role_exceptions.py
  - [ ] RoleNotFoundError
  - [ ] RoleAlreadyExistsError
- [ ] 3.5.3 修复role_repository.py导入(P0级别违规)
  - [ ] role_repository.py → from domain.exceptions.role_exceptions import RoleNotFoundError
  - [ ] role_repository.py → from domain.exceptions.role_exceptions import RoleAlreadyExistsError
- [ ] 3.5.4 验证: grep -r "from src.application" src/infrastructure/ | grep -v "__pycache__" 应返回空或仅含application层端口导入

阶段4: 服务代码整理
- [ ] 4.1 验证服务内无Protocol定义
    - [ ] 验证: grep -r "class.*Protocol" src/domain/services/ 应返回空
- [ ] 4.2 验证无Exception违规导入
    - [ ] 验证: grep -r "from src.application" src/infrastructure/ | grep -v "ports" 应返回空
- [ ] 4.3 修复L3VectorPort缺少CollectionManager问题
  - [ ] 4.3.1 L3VectorPort补充create_collection/delete_collection/collection_exists/list_collections方法
  - [ ] 4.3.2 废弃VectorStorage
- [ ] 4.4 修复L5GraphPort缺少get_neighbors问题
  - [ ] 4.4.1 L5GraphPort补充get_neighbors方法
  - [ ] 4.4.2 废弃GraphManager和GraphStorage
- [ ] 4.5 修复L4ObjectPort缺少list_objects问题(如需要)
- [ ] 4.6 修复P0-6: AutoRouteHandler事件发布缺失
  - [ ] 4.6.1 检查auto_route_handler.py的on_triggered()方法
  - [ ] 4.6.2 添加缺失的_publish(routed)调用
  - [ ] 4.6.3 验证: grep -A10 "on_triggered" src/domain/services/auto_route_handler.py | grep "_publish(routed)"
- [ ] 4.7 验证服务可正常解析

阶段5: 实现契约测试
- [ ] 5.1 为每个端口创建契约测试基类
- [ ] 5.2 实现具体端口的契约测试
- [ ] 5.3 集成到CI/CD

阶段6: 架构检查
- [ ] 6.1 配置pre-commit检查禁止规则
- [ ] 6.2 配置CI/CD兼容性检查
- [ ] 6.3 编写文档和示例
- [ ] 6.4 最终验证所有验收标准

阶段7: 持续治理（防止回退）
- [ ] 7.1 接口变更必须走流程
  - [ ] 修改契约 → 更新版本（semver）
  - [ ] 更新 registry
  - [ ] 运行 ContractGate 兼容性检查
  - [ ] 更新接口清单
- [ ] 7.2 新增接口必须满足
  - [ ] 不存在语义重复
  - [ ] 在 domain/ports/ 或 application/ports/ 定义
  - [ ] 在 composition_root 注册
  - [ ] 提供 contract test
  - [ ] 指定 owner
- [ ] 7.3 CI 强制检查
  - [ ] 禁止 service 内定义 Protocol
  - [ ] 禁止未注册端口被 resolve
  - [ ] 禁止直接实例化实现类
  - [ ] 禁止重复端口
- [ ] 7.4 定期治理（每周）
  - [ ] 扫描重复接口
  - [ ] 检查废弃端口是否仍被使用
  - [ ] 清理未注册实现
```
  - [ ] 提供 contract test
    - [ ] 指定 owner
- [ ] 7.3 CI 强制检查
  - [ ] 禁止 service 内定义 Protocol
  - [ ] 禁止 infrastructure → application
  - [ ] 禁止未注册端口被 resolve
  - [ ] 禁止直接实例化实现类
    - [ ] 禁止重复端口
- [ ] 7.4 Story模板强制要求
  - [ ] Task 0 必须定义/引用端口
  - [ ] 未定义端口 → 不允许开发
    - [ ] 未通过契约测试 → 不允许合并
- [ ] 7.5 定期治理（每周）
    - [ ] 扫描重复接口
    - [ ] 检查废弃端口是否仍被使用
    - [ ] 清理未注册实现
```

### 5.3 时间估算

| Phase | 建议时间 | 理由 |
|-------|----------|------|
| Phase 1 | 6-8小时 | 48个Protocol契约定义,8个从application迁移 |
| Phase 1.5 | 1-2小时 | 契约层完整性验证（门禁检查） |
| Phase 2 | 3-4小时 | 核心基础设施（registry/resolver/contract_gate） |
| Phase 2.5 | 1-2小时 | 注册中心完整性验证（门禁检查） |
| Phase 3 | 2-3小时 | 组合根+EventBusFactory修复 |
| Phase 3.5 | 2小时 | Domain异常类创建 |
| Phase 4 | 8-10小时 | 迁移服务代码+修复7处违规导入 |
| Phase 5 | 4-6小时 | 48个Protocol的契约测试（建议渐进式，先测5个核心） |
| Phase 6 | 1-2小时 | 架构检查+文档 |
| Phase 7 | 每周60-90分钟 | 持续治理（扫描+审查+修复） |
| **总计** | **28-39小时 + 持续治理** | 初始重构+长期维护 |

### 5.4 验收标准补充

| 补充标准 | 验证命令 |
|----------|----------|
| EventBusFactory不再为None | `python -c "from src.infrastructure.messaging import EventBusFactory; assert EventBusFactory.get_event_bus() is not None"` |
| 无Infrastructure→Application依赖 | `grep -r "from src.application" src/infrastructure/ src/domain/services/` 应返回空 |
| Domain层无技术绑定 | `grep -r "from sqlalchemy" src/domain/` 应返回空 |
| 服务内无Protocol定义 | `grep -r "class.*Protocol" src/domain/services/` 应返回空 |

---

## 六、验收标准

### 6.1 注册验收

| 标准 | 验证方法 |
|------|----------|
| 所有端口已注册 | `python -c "from src.domain.ports.registry import _global_registry; print(len(_global_registry.list_all()))"` 输出 ≥43（37 domain + 6 services - 废弃） |
| 无重复注册 | registry无ValueError |
| 契约测试通过 | `poetry run pytest tests/contracts/ -v` |
| EventBusFactory初始化正确 | `python -c "from src.infrastructure.messaging import EventBusFactory; assert EventBusFactory.get_event_bus() is not None"` 不抛RuntimeError |

### 6.2 架构验收

| 标准 | 验证方法 |
|------|----------|
| 无服务内Protocol定义 | `grep -r "class.*Protocol" src/domain/services/` 应返回空 |
| 契约测试覆盖所有端口 | `poetry run pytest tests/contracts/ --collect-only` |
| Domain层无技术绑定 | `grep -r "from sqlalchemy" src/domain/` 应返回空 |
| 接口返回类型一致性 | EventPublisherPort实现返回PublishResult而非None |
| Protocol实现声明完整 | 实现类声明实现对应Protocol |

### 6.3 接口一致性验收

| 标准 | 验证方法 |
|------|----------|
| EventPublisherPort返回类型统一 | `grep -r "def publish" src/domain/ports/event_publisher.py` 返回PublishResult |
| AutoRouteHandler事件发布 | `grep -A10 "on_triggered" src/domain/services/auto_route_handler.py \| grep "_publish(routed)"` 有结果 |
| 实现类Protocol声明 | 检查实现类正确声明实现对应Protocol |

### 6.4 集成验收

```bash
# 运行契约测试
poetry run pytest tests/contracts/ -v

# 运行单元测试
poetry run pytest tests/unit/domain/services/ -v

# 运行类型检查
poetry run mypy src/domain/ports/ --strict

# 验证无循环依赖
poetry run python -m pylyzer src/domain/ports/
```

### 6.5 持续治理验收（阶段7）

| 验证项 | 验证命令 | 触发条件 |
|--------|----------|----------|
| **Phase 1.5 契约层验证** | | |
| 契约可import | `python -c "from src.domain.ports import *; from src.application.ports import *"` | 每次新增契约后 |
| 无重复契约定义 | `python scripts/check_duplicate_ports.py` | 每次新增契约后 |
| 废弃接口已移除 | `grep -r "class VectorStorage" src/domain/ports/` 应返回空 | 每次新增契约后 |
| **Phase 2.5 注册中心验证** | | |
| 端口数量达标 | `python -c "assert len(_global_registry.list_all()) >= 43"` | 每次注册后 |
| PortSpec字段完整 | 人工检查name/version/interface/impl/module | 每次注册后 |
| 废弃端口未注册 | `python -c "assert 'VectorStorage' not in registry"` | 每次注册后 |
| **持续治理（每次PR）** | | |
| 无新增未登记端口 | `grep -r "Protocol" src/domain/services/` 应返回空 | 每次PR |
| 无废弃接口使用 | `grep -r "VectorStorage\|GraphManager" src/` 应返回空 | 每次PR |
| 无直接实例化 | `grep -r "SqlAlchemyUserRepo()" src/` 应返回空 | 每次PR |
| 接口变更兼容性 | `python -c "run ContractGate.check_compatibility()"` | 每次涉及契约修改的PR |
| 每周扫描重复接口 | `python scripts/check_duplicate_ports.py` | 每周CI |
| Story模板端口定义 | 检查story文件包含端口定义task | 每次新Story |

---

## 七、参考文献

### 核心架构理论
1. [Dependency injection - .NET](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/overview)
2. [Dependency injection guidelines - .NET](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines)
3. [Hexagonal Architecture - Alistair Cockburn](https://alistair.cockburn.us/hexagonal-architecture)
4. [ServiceLoader - Java SE 8](https://docs.oracle.com/javase/8/docs/api/java/util/ServiceLoader.html)
5. [Inversion of Control Containers and the Dependency Injection](https://martinfowler.com/articles/injection.html)
6. [Patterns of Enterprise Application Architecture - Martin Fowler](https://martinfowler.com/books/poea.html)
7. [Clean Architecture - Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

### Python Protocol与类型系统
8. [typing.Protocol - Python Docs](https://docs.python.org/3/library/typing.html#protocol)
9. [PEP 544 - Protocols (Python 3.8+)](https://peps.python.org/pep-0544/)

### 版本管理与兼容性
10. [Semantic Versioning](https://semver.org/)

### 架构验证工具
11. [Import Linter](https://import-linter.readthedocs.io/)

### 契约测试
12. [Pact Framework](https://docs.pact.io/)

---

## 八、版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | 2026-05-12 | 初始版本 - 输出SISYS端口开发与管理重构执行方案 |
| v2.0 | 2026-05-12 | 重构执行方案v2.0 - 消除重复矛盾 |
| v3.0 | 2026-05-12 | 重构执行方案v3.0 - 完善P0问题与4层架构 |
| v3.1 | 2026-05-12 | 重构执行方案v3.1 - 添加Phase 1.5/2.5关键检查点 |
| v3.2 | 2026-05-12 | Round 1审查 - 修正Protocol统计(48→54实际/48目标) |
| v3.3 | 2026-05-12 | Round 2审查 - 接口合并前提条件(L3需补充CollectionManager,L4需补充list_objects) |
| v3.4 | 2026-05-12 | Round 3审查 - 新增Phase 3.5,修正路径格式,补充迁移风险评估,澄清跨模块继承 |
| v3.5 | 2026-05-12 | Round 4审查 - 修正Phase 3.5执行顺序,更新时间估算(18-26h→28-39h),补充契约测试框架建议 |
| v4.0 | 2026-05-12 | **架构修正**: 不迁移application/ports，建立双层端口契约体系(domain/ports + application/ports) |

### 审查修复历史

| 轮次 | 修复内容 |
|------|----------|
| R1-R4 | 补充P0问题映射与代码示例修正(commit哈希略) |
| R5 | 添加Phase 1.5/2.5关键检查点，完善Section 6.5验收标准 |
| R6 | **Round 1审查修正**: Protocol统计澄清(41 domain + 6 services + 7 application = 54实际，清理后48目标) |
| R7 | **Round 2审查修正**: L3VectorPort需补充CollectionManager,L4ObjectPort需补充list_objects; EventPublisherProtocol返回类型不一致 |
| R8 | **Round 3审查修正**: 新增Phase 3.5(domain异常定义); 路径格式修正; 迁移风险等级标注; Section 4.5澄清(无实际违规); scripts/check_duplicate_ports.py需创建 |
| R9 | **Round 4审查修正**: Phase 3.5执行顺序正确(在Phase3后Phase4前),时间估算上调至28-39h,契约测试渐进式建议(先测5个核心) |
| R10 | **v4.0架构修正**: 不迁移application/ports到domain/ports/contracts/，确认双层端口契约体系 |

---

*文档版本: v3.5*
*核心更新: 统一端口注册管理机制（4层架构）*
*- Layer 1: Port Contract (契约层) - 定义在 domain/ports/ 和 application/ports/
*- Layer 2: Registry (注册层) - 统一登记元数据
*- Layer 3: Resolver (解析层) - 依赖注入容器
*- Layer 4: Contract Gate (契约门禁层) - 契约测试+兼容性检查
*- Composition Root: 组合根 - 所有注册在此完成

> **注意**: 本文档第2-4层架构代码示例为**设计方案**，实际代码库中尚未实现。执行重构时需先创建 `src/domain/ports/registry.py`、`src/domain/ports/resolver.py`、`src/composition_root.py` 等文件。

> **v4.0架构说明**: 端口契约定义保持在原有位置（domain/ports/ 和 application/ports/），不迁移、不创建 contracts/ 目录。两者各有用途，独立共存。
