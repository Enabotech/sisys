# SISYS 端口开发与管理重构执行方案

**文档版本:** v3.0
**生成时间:** 2026-05-12
**基于:** sisys-port-impl-report.md 全面调研结果

---

## 重构背景

### 问题发现

基于 `sisys-port-impl-report.md` 全面调研，发现以下问题：

| 问题类别 | 发现 | 影响 |
|----------|------|------|
| **服务内Protocol定义** | 6个服务文件本地定义了9个Protocol | 违反六边形架构，接口重复 |
| **导出完整性** | `domain/ports/__init__.py` 仅导出16个(32.7%)，缺失≥42个 | 基础设施层无法正确导入 |
| **EventBusFactory** | 3个组件初始化为None | 运行时触发AttributeError |
| **接口冗余** | L3/L4/L5层存在语义重复的端口 | 架构模糊，实现混淆 |
| **Infrastructure依赖Application** | 6处违规导入 | 违反依赖倒置原则 |
| **跨模块继承** | SQLAlchemy模型继承infrastructure的Base | Domain层绑定具体技术 |
| **无统一注册机制** | 端口分散定义，无中心化管理 | 可插拔系统难以维护 |

### 核心目标

| 目标 | 现状 | 目标状态 |
|------|------|----------|
| 建立统一端口注册管理机制 | 端口分散定义 | 4层架构：契约→注册→解析→门禁 |
| 消除服务内Protocol定义 | 6个服务文件定义9个Protocol | 全部迁移到domain/ports/contracts/ |
| 补全__init__.py导出 | 16/49符号已导出(32.7%) | 导出所有49个符号(100%) |
| 消除Infrastructure依赖Application | 6处违规 | 迁移SemanticCache/PublicBlackboard/SandboxExecutor到Domain层 |
| 合并语义重复接口 | L3: VectorStorage↔L3VectorPort; L5: GraphManager/GraphStorage↔L5GraphPort; L1: SessionStorage↔L1CachePort | 统一为单一契约 |
| 修复EventBusFactory | 3个组件为None | 延迟初始化+单例复用 |
| 修复跨模块继承 | SQLAlchemy Base在infrastructure | 迁移Base到Domain或使用无技术绑定Base |

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
│                    Composition Root (组合根)                           │
│              所有端口、适配器、实现类在此完成注册                         │
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
│  - 接口、Protocol、DTO、错误码                                        │
│  - 只定义行为，不含实现                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Layer 1: Port Contract（契约层）

**原则**: 只放接口、Protocol、DTO、错误码，不放业务实现。同一类能力只保留一个主契约。

```python
# src/domain/ports/contracts/__init__.py
"""契约层 — 领域层端口定义

所有端口必须定义在此目录，按功能模块组织。
禁止在此目录定义任何实现类。
"""

from src.domain.ports.contracts.user_repository import UserRepositoryPort
from src.domain.ports.contracts.cache import L1CachePort
from src.domain.ports.contracts.event_publisher import EventPublisher
# ... 其他端口
```

**契约定义规范**:
```python
# src/domain/ports/contracts/user_repository.py
"""用户仓储端口契约"""

from __future__ import annotations

from typing import Protocol, UUID
from src.domain.entities.user import User
from src.domain.ports.contracts.errors import NotFoundError


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

### 2.1 契约层端口（35个核心 + 14个待废弃 = 49个）

| 端口名 | 契约文件 | 用途 | 实现模块 | 状态 |
|--------|----------|------|----------|------|
| **仓储基础** |
| `UserRepositoryPort` | contracts/user_repository.py | 用户数据访问 | infrastructure/user_repo | **待注册** |
| `UserRoleRepositoryPort` | contracts/user_role_repository.py | 用户-角色关联 | infrastructure/user_role_repo | **待注册** |
| `LoginAttemptRepositoryPort` | contracts/login_attempt_repository.py | 登录尝试跟踪 | infrastructure/login_attempt_repo | **待注册** |
| `AuditRepositoryPort` | contracts/audit_repository.py | 审计日志存储 | infrastructure/audit_repo | **待注册** |
| **存储分层（L0-L5）** |
| `L0StoragePort` | contracts/l0_storage.py | L0文件系统 | infrastructure/l0_file_adapter | **待注册** |
| `L1CachePort` | contracts/l1_cache.py | L1 Redis缓存 | infrastructure/l1_redis_cache | **待注册** |
| `L2MetadataRepositoryPort` | contracts/l2_metadata.py | L2元数据 | infrastructure/l2_postgresql | **待注册** |
| `L2ChangeHistoryRepositoryPort` | contracts/l2_change_history.py | L2变更历史 | infrastructure/l2_postgresql | **待注册** |
| `L2GroupMemberRepositoryPort` | contracts/l2_group_member.py | L2群组成员 | infrastructure/l2_postgresql | **待注册** |
| `L3VectorPort` | contracts/l3_vector.py | L3向量存储 | infrastructure/l3_qdrant | **待注册** |
| ~~`VectorStorage`~~ | — | L3向量存储(废弃) | — | **废弃→合并到L3VectorPort** |
| `L4ObjectPort` | contracts/l4_object.py | L4对象存储 | infrastructure/l4_minio | **待注册** |
| `L5GraphPort` | contracts/l5_graph.py | L5图存储 | infrastructure/l5_neo4j | **待注册** |
| ~~`GraphManager`~~ | — | L5图管理(废弃) | — | **废弃→合并到L5GraphPort** |
| ~~`GraphStorage`~~ | — | L5图存储(废弃) | — | **废弃→合并到L5GraphPort** |
| `UnifiedStoragePort` | contracts/unified_storage.py | 统一存储入口 | infrastructure/unified_storage | **待注册** |
| `SessionStoragePort` | contracts/session_storage.py | 会话状态存储 | infrastructure/session_redis | **待整合** |
| `IndexManagerPort` | contracts/index_manager.py | MEMORY索引 | infrastructure/memory_index | **待注册** |
| **事件发布** |
| `EventPublisherPort` | contracts/event_publisher.py | 领域事件发布 | infrastructure/event_publisher | **待注册** |
| **认证授权** |
| `AuthServicePort` | contracts/auth_service.py | 认证服务 | infrastructure/auth_service | **待注册** |
| `PermissionServicePort` | contracts/permission_service.py | 权限检查 | infrastructure/permission_service | **待注册** |
| `TokenBlacklistPort` | contracts/token_blacklist.py | JWT黑名单 | infrastructure/token_blacklist | **待注册** |
| **合规服务** |
| `ComplianceGatewayPort` | contracts/compliance_gateway.py | UDMR合规检查 | infrastructure/compliance_gateway | **待注册** |
| `SensitiveDataDetectorPort` | contracts/sensitive_data_detector.py | 敏感数据检测 | infrastructure/sensitive_data_detector | **待注册** |
| `DataResidencyEnforcerPort` | contracts/data_residency_enforcer.py | 数据驻留强制 | infrastructure/data_residency_enforcer | **待注册** |
| **Application层待迁移** |
| `SemanticCache` | contracts/semantic_cache.py | 语义缓存(从application迁移) | — | **迁移中→Domain层** |
| `PublicBlackboard` | contracts/public_blackboard.py | 公共黑板(从application迁移) | — | **迁移中→Domain层** |
| `SandboxExecutor` | contracts/sandbox.py | 沙箱执行器(从application迁移) | — | **迁移中→Domain层** |

### 2.1.1 SessionStorage与L1CachePort协作关系

```
SessionStoragePort 与 L1CachePort 关系:
├── L1CachePort: 通用的键值缓存抽象
├── SessionStoragePort: 专用于会话状态，底层可复用L1CachePort实现
└── 建议: SessionStoragePort 实现应委托给 L1CachePort，不独立管理连接
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
| 禁止业务代码 import 实现 | `from infra.user_repo import SqlAlchemyUserRepo` | `from ports import UserRepositoryPort` |
| 禁止在契约外定义接口 | `class MyPort(Protocol)` 在其他文件 | 所有接口在 `contracts/` 目录 |
| 禁止在服务内定义Protocol | `class Service: class Port(Protocol):` | 导入已注册的端口 |
| 禁止直接实例化 | `repo = SqlAlchemyUserRepo()` | `repo = resolve("user_repo")` |

### 4.2 允许规则

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
| 阶段1 | P0-19, P0-20, V1, V2, V3 | contracts/目录包含全部49个端口契约 |
| 阶段2 | P0-7, P0-8, P0-9 | registry包含全部49个端口 |
| 阶段3 | P0-10, P0-11, P0-12 | EventBusFactory正确初始化，3组件非None |
| 阶段4 | P0-1~6, P0-18, V4, V5, V6 | 服务内无Protocol定义，无违规导入 |
| 阶段5 | P0-13~P0-17 | 契约测试通过，覆盖全部49个端口 |
| 阶段6 | P0-21~P0-24 | 实现类声明实现对应Protocol |

### 5.2 详细执行步骤

```
阶段1: 创建契约层结构
├── 1.1 创建 src/domain/ports/contracts/ 目录
├── 1.2 迁移application/ports定义到Domain层
│   ├── 迁移 SemanticCache → contracts/semantic_cache.py
│   ├── 迁移 PublicBlackboard → contracts/public_blackboard.py
│   └── 迁移 SandboxExecutor → contracts/sandbox.py
├── 1.3 定义35个核心端口契约
├── 1.4 废弃语义重复接口（VectorStorage, GraphManager, GraphStorage）
└── 1.5 验证: contracts/目录包含49个端口

阶段2: 实现注册中心
├── 2.1 实现 registry.py (PortRegistry, PortSpec, Lifetime)
├── 2.2 实现 resolver.py (Resolver, resolve)
├── 2.3 实现 contract_gate.py (ContractGate, PortContractTest)
└── 2.4 验证: registry包含全部49个端口

阶段3: 创建组合根 + 修复EventBusFactory
├── 3.1 创建 composition_root.py
├── 3.2 注册所有49个端口
├── 3.3 修复EventBusFactory初始化
│   ├── 3.3.1 识别3个问题组件(publisher/subscriber/event_bus)
│   ├── 3.3.2 修复初始化顺序(延迟初始化+单例复用)
│   └── 3.3.3 验证不再触发AttributeError
└── 3.4 验证: EventBusFactory.get_instance() 返回非None实例

阶段4: 迁移服务代码
├── 4.1 迁移服务内Protocol定义到契约层
│   ├── 迁移 auto_execute_service.py 的 SandboxExecutorProtocol
│   └── 迁移其他服务的本地Protocol
├── 4.2 更新Infrastructure层导入(指向Domain层)
│   ├── grep -r "from src.application.ports" src/infrastructure/
│   └── 更新为 "from src.domain.ports.contracts"
├── 4.3 修复跨模块继承
│   ├── 4.3.1 识别SQLAlchemy模型继承infrastructure Base的位置
│   ├── 4.3.2 将Base迁移到Domain层或使用无技术绑定的Base
│   └── 4.3.3 验证: grep -r "from sqlalchemy" src/domain/ 无结果
├── 4.4 验证服务可正常解析
└── 4.5 验证: 无Infrastructure→Application依赖

阶段5: 实现契约测试
├── 5.1 为每个端口创建契约测试基类
├── 5.2 实现具体端口的契约测试
└── 5.3 集成到CI/CD

阶段6: 架构检查
├── 6.1 配置pre-commit检查禁止规则
├── 6.2 配置CI/CD兼容性检查
├── 6.3 编写文档和示例
└── 6.4 最终验证所有验收标准
```

### 5.3 时间估算

| Phase | 建议时间 | 理由 |
|-------|----------|------|
| Phase 1 | 4-6小时 | 49个契约定义，部分需从application迁移 |
| Phase 2 | 2-3小时 | 核心基础设施开发 |
| Phase 3 | 2-3小时 | 组合根+EventBusFactory修复 |
| Phase 4 | 6-8小时 | 迁移服务代码+修复依赖+跨模块继承 |
| Phase 5 | 3-4小时 | 49个端口的契约测试 |
| Phase 6 | 1-2小时 | 架构检查+文档 |
| **总计** | **18-26小时** | — |

### 5.4 验收标准补充

| 补充标准 | 验证命令 |
|----------|----------|
| EventBusFactory不再为None | `python -c "from src.infrastructure.messaging import EventBusFactory; assert EventBusFactory.get_instance() is not None"` |
| 无Infrastructure→Application依赖 | `grep -r "from src.application.ports" src/infrastructure/ src/domain/services/` 应返回空 |
| Domain层无技术绑定 | `grep -r "from sqlalchemy" src/domain/` 应返回空 |

---

## 六、验收标准

### 6.1 注册验收

| 标准 | 验证方法 |
|------|----------|
| 所有35个端口已注册 | `python -c "from src.composition_root import registry; print(len(registry))"` 输出 35 |
| 无重复注册 | registry无ValueError |
| 契约测试通过 | `poetry run pytest tests/contracts/ -v` |

### 6.2 架构验收

| 标准 | 验证方法 |
|------|----------|
| 业务代码不直接import实现 | `grep -r "from src.infrastructure" src/domain/services/` 无结果 |
| 无服务内Protocol定义 | `grep -r "class.*Protocol" src/domain/services/` 无结果 |
| 契约测试覆盖所有端口 | `poetry run pytest tests/contracts/ --collect-only` |

### 6.3 集成验收

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

---

## 七、参考文献

1. [Dependency injection - .NET](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/overview)
2. [Dependency injection guidelines - .NET](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines)
3. [Hexagonal Architecture - Alistair Cockburn](https://alistair.cockburn.us/hexagonal-architecture)
4. [ServiceLoader - Java SE 8](https://docs.oracle.com/javase/8/docs/api/java/util/ServiceLoader.html)
5. [Inversion of Control Containers and the Dependency Injection](https://martinfowler.com/articles/injection.html)

---

*文档版本: v3.0*
*核心更新: 统一端口注册管理机制（4层架构）*
*- Layer 1: Port Contract (契约层) - 只定义接口*
*- Layer 2: Registry (注册层) - 统一登记元数据*
*- Layer 3: Resolver (解析层) - 依赖注入容器*
*- Layer 4: Contract Gate (契约门禁层) - 契约测试+兼容性检查*
*- Composition Root: 组合根 - 所有注册在此完成*
