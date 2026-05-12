# SISYS 端口开发与管理重构执行方案

**文档版本:** v1.0
**生成时间:** 2026-05-12
**基于:** sisys-port-impl-report.md 全面调研结果

---

## 一、重构目标

### 1.1 核心目标

| 目标 | 现状 | 目标状态 |
|------|------|----------|
| 消除服务内Protocol定义 | 5个服务文件定义8个Protocol | 全部迁移到domain/ports/ |
| 补全__init__.py导出 | 16/49符号已导出(32.7%) | 导出所有49个符号(100%) |
| 修复EventBusFactory | publisher/subscriber为None | 延迟初始化+单例复用 |
| 消除Infrastructure依赖Application | 6处违规 | 迁移到Domain层 |

### 1.2 重构原则

1. **依赖倒置**: Domain层定义端口，Infrastructure层实现
2. **端口集中**: 所有Protocol定义在domain/ports/或application/ports/
3. **单向依赖**: 层级依赖只能从外到内
4. **最小变更**: 保持现有接口兼容，逐步迁移

---

## 二、重构任务清单

### 任务1: 服务内Protocol迁移

**问题**: 5个服务文件在内部定义了8个Protocol，违反六边形架构

#### 1.1 创建新端口文件

**T1.1.1 创建 routing.py**
```python
# src/domain/ports/routing.py
"""路由协议端口 — 六边形架构路由接口定义"""

from __future__ import annotations

from typing import Any, Protocol


class HashRouterProtocol(Protocol):
    """基于session_id哈希的路由协议"""

    def route(self, session_id: str) -> str:
        """根据session_id哈希选择目标节点

        Args:
            session_id: 会话标识符

        Returns:
            目标节点ID
        """
        ...


class SemanticRouterProtocol(Protocol):
    """基于任务上下文语义相似度的路由协议"""

    async def route(self, task_context: dict[str, Any]) -> tuple[str, float]:
        """根据任务上下文选择最匹配的目标

        Args:
            task_context: 任务上下文字典

        Returns:
            (目标节点ID, 相似度分数)
        """
        ...
```

**T1.1.2 创建 sandbox.py**
```python
# src/domain/ports/sandbox.py
"""沙箱执行器端口 — 六边形架构沙箱接口定义"""

from __future__ import annotations

from typing import Any, Protocol


class SandboxExecutor(Protocol):
    """沙箱执行器协议"""

    async def execute(self, code: str, context: dict[str, Any]) -> dict[str, Any]:
        """在沙箱中执行代码

        Args:
            code: 待执行的代码字符串
            context: 执行上下文

        Returns:
            执行结果字典
        """
        ...


class SnapshotRepository(Protocol):
    """快照仓储协议"""

    async def save(self, snapshot: dict[str, Any]) -> str:
        """保存快照

        Args:
            snapshot: 快照数据

        Returns:
            快照ID
        """
        ...

    async def load(self, snapshot_id: str) -> dict[str, Any] | None:
        """加载快照

        Args:
            snapshot_id: 快照ID

        Returns:
            快照数据，不存在则返回None
        """
        ...
```

#### 1.2 更新服务文件导入

**T1.2.1 auto_route_service.py**
```python
# 删除: 第6-7行 (typing.Protocol)
# 删除: 第15-18行 (EventPublisherProtocol)
# 删除: 第21-33行 (HashRouterProtocol)
# 删除: 第36-48行 (SemanticRouterProtocol)

# 添加导入:
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.routing import HashRouterProtocol, SemanticRouterProtocol

# 修改类签名:
def __init__(
    self,
    publisher: EventPublisher | None = None,
    hash_router: HashRouterProtocol | None = None,
    semantic_router: SemanticRouterProtocol | None = None,
) -> None:
```

**T1.2.2 auto_trigger_service.py**
```python
# 删除: 第6-7行 (typing.Protocol)
# 删除: 第15-18行 (EventPublisherProtocol)

# 添加导入:
from src.domain.ports.event_publisher import EventPublisher

# 修改类签名:
def __init__(self, publisher: EventPublisher | None = None) -> None:
```

**T1.2.3 auto_execute_service.py**
```python
# 删除: 第6-7行 (typing.Protocol)
# 删除: 第25-38行 (SandboxExecutorProtocol)
# 删除: 第41-54行 (SnapshotRepositoryProtocol)

# 添加导入:
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.sandbox import SandboxExecutor, SnapshotRepository

# 修改类签名:
def __init__(
    self,
    executor: SandboxExecutor | None = None,
    snapshot_repo: SnapshotRepository | None = None,
) -> None:
```

**T1.2.4 auto_route_handler.py**
```python
# 删除: 第27-30行 (EventPublisherProtocol)

# 添加导入:
from src.domain.ports.event_publisher import EventPublisher

# 修改类签名:
def __init__(self, auto_route_service: AutoRouteService, publisher: EventPublisher | None = None) -> None:
```

**T1.2.5 auto_execute_completed_handler.py**
```python
# 删除: 第18-21行 (EventPublisherProtocol)

# 添加导入:
from src.domain.ports.event_publisher import EventPublisher

# 修改类签名:
def __init__(self, auto_execute_service: AutoExecuteService, publisher: EventPublisher | None = None) -> None:
```

#### 1.3 验证步骤

```bash
# 验证1: 服务文件无本地Protocol定义
grep -n "class.*Protocol" src/domain/services/*.py src/application/event_handlers/*.py | grep -v "from src.domain.ports"

# 验证2: 所有迁移后的Protocol可导入
python -c "
from src.domain.ports.routing import HashRouterProtocol, SemanticRouterProtocol
from src.domain.ports.sandbox import SandboxExecutor, SnapshotRepository
from src.domain.ports.event_publisher import EventPublisher
print('All protocols importable')
"
```

---

### 任务2: 补全__init__.py导出

**问题**: __init__.py仅导出16/49符号(32.7%)，缺失33个

#### 2.1 重写__init__.py

```python
# src/domain/ports/__init__.py
"""Domain ports package — 六边形架构领域层端口定义

所有领域层端口必须通过此模块导出，确保统一导入路径。
导出格式: from src.domain.ports import PortName
"""

from __future__ import annotations

# === L0-L5 存储层端口 ===
from src.domain.ports.graph_storage import GraphManager, GraphStorage
from src.domain.ports.l0_storage import L0StoragePort
from src.domain.ports.l1_cache import L1CachePort
from src.domain.ports.l2_rdb import (
    L2ChangeHistoryRepositoryPort,
    L2GroupMemberRepositoryPort,
    L2MetadataRepositoryPort,
)
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.l4_object import L4ObjectPort
from src.domain.ports.l5_graph import L5GraphPort
from src.domain.ports.vector_storage import CollectionManager, VectorStorage
from src.domain.ports.storage import ObjectStorageRepository
from src.domain.ports.unified_storage import UnifiedStoragePort
from src.domain.ports.unit_of_work import UnitOfWork
from src.domain.ports.outbox import OutboxRepository
from src.domain.ports.session_storage import SessionStorage

# === 事件与消息端口 ===
from src.domain.ports.event_publisher import EventPublisher, InMemoryEventPublisher

# === 完整性保障端口 ===
from src.domain.ports.integrity import IntegrityPort
from src.domain.ports.index_manager import IndexManagerPort
from src.domain.ports.health_check import HealthCheckPort

# === 基础架构端口 ===
from src.domain.ports.base import BaseRepository

# === 用户与认证端口 ===
from src.domain.ports.user_repository import UserRepositoryPort
from src.domain.ports.auth_service import AuthServicePort, AuthTokens
from src.domain.ports.login_attempt_repository import LoginAttemptRepositoryPort
from src.domain.ports.token_blacklist import TokenBlacklistPort
from src.domain.ports.password_validation_service import PasswordValidationServicePort

# === 角色与权限端口 ===
from src.domain.ports.role_repository import RoleRepositoryPort
from src.domain.ports.user_role_repository import UserRoleRepositoryPort
from src.domain.ports.permission_service import PermissionServicePort

# === 审计端口 ===
from src.domain.ports.audit_repository import (
    AuditRepositoryPort,
    AuditSearchCriteria,
    AuditSearchResult,
)
from src.domain.ports.audit_service import AuditServicePort, AuditRecord

# === 合规服务端口 ===
from src.domain.ports.compliance_gateway import ComplianceGatewayPort
from src.domain.ports.sensitive_data_detector import SensitiveDataDetectorPort
from src.domain.ports.data_residency_enforcer import DataResidencyEnforcerPort
from src.domain.ports.whitelist_service import WhitelistServicePort
from src.domain.ports.pipl_compliance_service import PIPLComplianceServicePort
from src.domain.ports.cross_border_transfer_service import CrossBorderTransferServicePort

# === 路由端口 ===
from src.domain.ports.routing import HashRouterProtocol, SemanticRouterProtocol

# === 沙箱端口 ===
from src.domain.ports.sandbox import SandboxExecutor, SnapshotRepository

# === 枚举类型 ===
from src.domain.ports.storage_enums import DataAccessPattern, StorageLayer, StorageTier

__all__ = [
    # L0-L5 存储层
    "CollectionManager",
    "DataAccessPattern",
    "GraphManager",
    "GraphStorage",
    "IntegrityPort",
    "IndexManagerPort",
    "L0StoragePort",
    "L1CachePort",
    "L2ChangeHistoryRepositoryPort",
    "L2GroupMemberRepositoryPort",
    "L2MetadataRepositoryPort",
    "L3VectorPort",
    "L4ObjectPort",
    "L5GraphPort",
    "ObjectStorageRepository",
    "OutboxRepository",
    "SessionStorage",
    "StorageLayer",
    "StorageTier",
    "UnifiedStoragePort",
    "UnitOfWork",
    "VectorStorage",
    # 事件与消息
    "EventPublisher",
    "InMemoryEventPublisher",
    # 完整性保障
    "HealthCheckPort",
    # 基础架构
    "BaseRepository",
    # 用户与认证
    "AuthServicePort",
    "AuthTokens",
    "LoginAttemptRepositoryPort",
    "PasswordValidationServicePort",
    "TokenBlacklistPort",
    "UserRepositoryPort",
    # 角色与权限
    "PermissionServicePort",
    "RoleRepositoryPort",
    "UserRoleRepositoryPort",
    # 审计
    "AuditRecord",
    "AuditRepositoryPort",
    "AuditSearchCriteria",
    "AuditSearchResult",
    "AuditServicePort",
    # 合规服务
    "ComplianceGatewayPort",
    "CrossBorderTransferServicePort",
    "DataResidencyEnforcerPort",
    "PIPLComplianceServicePort",
    "SensitiveDataDetectorPort",
    "WhitelistServicePort",
    # 路由
    "HashRouterProtocol",
    "SemanticRouterProtocol",
    # 沙箱
    "SandboxExecutor",
    "SnapshotRepository",
]
```

#### 2.2 验证步骤

```bash
# 验证1: 导出数量
python -c "from src.domain.ports import *; print(f'Exported: {len(__all__)} symbols')"

# 验证2: 所有符号可导入
python -c "
from src.domain.ports import *
missing = [name for name in __all__ if name not in dir()]
if missing:
    print(f'Missing: {missing}')
else:
    print(f'All {len(__all__)} symbols exported correctly')
"
```

---

### 任务3: 修复EventBusFactory

**问题**: 3个组件初始化为None，_get_outbox_repository返回None

#### 3.1 重构EventBusFactory

```python
# src/infrastructure/messaging/event_bus_factory.py
"""EventBusFactory — 事件总线工厂，负责创建和复用事件总线组件"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.infrastructure.messaging.channel_router import ChannelRouter

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from src.domain.ports.outbox import OutboxRepository
    from src.infrastructure.messaging.rabbitmq_config import RabbitMQConfig

logger = logging.getLogger(__name__)


class EventBusFactory:
    """事件总线工厂

    设计原则:
    1. 组件延迟初始化 - 直到首次使用时才创建真实组件
    2. 单例复用 - 同一类型的组件只创建一次
    3. 运行时检查 - 使用前验证组件是否已初始化

    使用示例:
        factory = EventBusFactory(redis_client=redis, rabbitmq_config=config)
        redis_bus = factory.create_redis_bus()
        rabbitmq_bus = factory.create_rabbitmq_bus()
    """

    _instance: EventBusFactory | None = None

    def __init__(
        self,
        redis_client: Redis | None = None,
        rabbitmq_config: RabbitMQConfig | None = None,
    ) -> None:
        """初始化事件总线工厂

        Args:
            redis_client: Redis客户端实例，用于创建Redis发布/订阅组件
            rabbitmq_config: RabbitMQ配置，用于创建RabbitMQ发布组件
        """
        self._router = ChannelRouter()
        self._redis_client = redis_client
        self._rabbitmq_config = rabbitmq_config

        # 组件缓存（延迟初始化）
        self._redis_publisher: Any = None
        self._redis_subscriber: Any = None
        self._rabbitmq_publisher: Any = None
        self._outbox_repository: OutboxRepository | None = None

    @classmethod
    def get_instance(cls, **kwargs: Any) -> EventBusFactory:
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    @property
    def redis_publisher(self) -> Any:
        """获取Redis发布者（延迟初始化）"""
        if self._redis_publisher is None:
            if self._redis_client is None:
                raise RuntimeError(
                    "Redis publisher not available: redis_client not configured"
                )
            from src.infrastructure.messaging.publishers import RedisPublisher
            self._redis_publisher = RedisPublisher(self._redis_client)
            logger.info("Redis publisher initialized")
        return self._redis_publisher

    @property
    def redis_subscriber(self) -> Any:
        """获取Redis订阅者（延迟初始化）"""
        if self._redis_subscriber is None:
            if self._redis_client is None:
                raise RuntimeError(
                    "Redis subscriber not available: redis_client not configured"
                )
            from src.infrastructure.messaging.subscribers import RedisSubscriber
            self._redis_subscriber = RedisSubscriber(self._redis_client)
            logger.info("Redis subscriber initialized")
        return self._redis_subscriber

    @property
    def rabbitmq_publisher(self) -> Any:
        """获取RabbitMQ发布者（延迟初始化）"""
        if self._rabbitmq_publisher is None:
            if self._rabbitmq_config is None:
                raise RuntimeError(
                    "RabbitMQ publisher not available: rabbitmq_config not configured"
                )
            from src.infrastructure.messaging.publishers import RabbitMQPublisher
            self._rabbitmq_publisher = RabbitMQPublisher(self._rabbitmq_config)
            logger.info("RabbitMQ publisher initialized")
        return self._rabbitmq_publisher

    @property
    def outbox_repository(self) -> OutboxRepository:
        """获取Outbox仓储（延迟初始化）"""
        if self._outbox_repository is None:
            from src.infrastructure.storage.postgresql.repository.outbox_repository import (
                PostgreSQLOutboxRepository,
            )
            self._outbox_repository = PostgreSQLOutboxRepository()
            logger.info("Outbox repository initialized")
        return self._outbox_repository

    def create_redis_bus(self) -> RedisEventBus:
        """创建Redis事件总线

        Returns:
            RedisEventBus实例，持有已初始化的publisher和subscriber

        Raises:
            RuntimeError: 当Redis客户端未配置时
        """
        from src.infrastructure.messaging.redis_event_bus import RedisEventBus
        return RedisEventBus(
            publisher=self.redis_publisher,
            subscriber=self.redis_subscriber,
            router=self._router,
        )

    def create_rabbitmq_bus(self) -> RabbitMQEventBus:
        """创建RabbitMQ事件总线

        Returns:
            RabbitMQEventBus实例

        Raises:
            RuntimeError: 当RabbitMQ配置未提供时
        """
        from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
        return RabbitMQEventBus(
            outbox_repository=self.outbox_repository,
            router=self._router,
        )

    def create_dual_channel_bus(
        self,
    ) -> tuple[DualChannelEventBus, AsyncOutboxPoller]:
        """创建双通道事件总线

        Returns:
            (DualChannelEventBus, AsyncOutboxPoller) 元组
        """
        from src.infrastructure.messaging.dual_channel_event_bus import (
            DualChannelEventBus,
        )
        from src.infrastructure.messaging.outbox_poller import AsyncOutboxPoller

        redis_bus = self.create_redis_bus()
        rabbitmq_bus = self.create_rabbitmq_bus()

        bus = DualChannelEventBus(
            redis_bus=redis_bus,
            rabbitmq_bus=rabbitmq_bus,
            router=self._router,
        )

        poller = AsyncOutboxPoller(
            outbox_repository=self.outbox_repository,
            publisher=self.rabbitmq_publisher,
        )

        return bus, poller

    def reset(self) -> None:
        """重置工厂状态（用于测试）"""
        self._redis_publisher = None
        self._redis_subscriber = None
        self._rabbitmq_publisher = None
        self._outbox_repository = None
        EventBusFactory._instance = None
```

#### 3.2 验证步骤

```bash
# 验证1: publisher/subscriber不为None
python -c "
from src.infrastructure.messaging.event_bus_factory import EventBusFactory
factory = EventBusFactory()
bus = factory.create_redis_bus()
assert bus._publisher is not None, 'publisher should not be None'
assert bus._subscriber is not None, 'subscriber should not be None'
print('EventBusFactory: publisher/subscriber initialized correctly')
"

# 验证2: outbox_repository不为None
python -c "
from src.infrastructure.messaging.event_bus_factory import EventBusFactory
factory = EventBusFactory()
bus = factory.create_rabbitmq_bus()
assert bus._outbox_repo is not None, 'outbox_repo should not be None'
print('EventBusFactory: outbox_repository initialized correctly')
"
```

---

### 任务4: 迁移Application端口到Domain层

**问题**: Infrastructure层依赖Application层定义的端口，违反依赖倒置原则

#### 4.1 创建Domain层端口

**T4.1.1 创建domain层端口文件**

```python
# src/domain/ports/metrics_port.py
"""指标端口 — 领域层指标收集接口定义"""

from __future__ import annotations

from typing import Protocol


class MetricsPort(Protocol):
    """指标收集接口"""

    async def increment(self, metric_name: str, value: float = 1.0) -> None:
        """递增指标

        Args:
            metric_name: 指标名称
            value: 递增值
        """
        ...

    async def gauge(self, metric_name: str, value: float) -> None:
        """设置仪表值

        Args:
            metric_name: 指标名称
            value: 仪表值
        """
        ...
```

```python
# src/domain/ports/exception_metrics_port.py
"""异常指标端口 — 领域层异常跟踪接口定义"""

from __future__ import annotations

from typing import Protocol


class ExceptionMetricsPort(Protocol):
    """异常跟踪接口"""

    async def record_exception(
        self,
        exception_type: str,
        message: str,
        stack_trace: str | None = None,
    ) -> None:
        """记录异常

        Args:
            exception_type: 异常类型名称
            message: 异常消息
            stack_trace: 堆栈跟踪（可选）
        """
        ...
```

```python
# src/domain/ports/sandbox_port.py (重命名sandbox.py为sandbox_port.py)
"""沙箱执行器端口 — 领域层沙箱执行接口定义"""

from __future__ import annotations

from typing import Any, Protocol


class SandboxExecutor(Protocol):
    """沙箱执行器协议"""

    async def execute(self, code: str, context: dict[str, Any]) -> dict[str, Any]:
        """在沙箱中执行代码"""
        ...


class ContainerStartError(Exception):
    """容器启动错误"""
    pass


class ContainerStopError(Exception):
    """容器停止错误"""
    pass


class ExecutionError(Exception):
    """执行错误"""
    pass
```

```python
# src/domain/ports/event_subscriber.py
"""事件订阅端口 — 领域层事件订阅接口定义"""

from __future__ import annotations

from typing import Callable, Coroutine, Any

from src.domain.events.base import DomainEvent


class EventSubscriber(Protocol):
    """事件订阅接口"""

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Coroutine[Any, Any, None]],
    ) -> None:
        """订阅事件

        Args:
            event_type: 事件类型
            handler: 事件处理器
        """
        ...

    def unsubscribe(self, event_type: str) -> None:
        """取消订阅

        Args:
            event_type: 事件类型
        """
        ...
```

#### 4.2 更新Infrastructure层导入

**T4.2.1 metrics_port_impl.py**
```python
# 修改前
from src.application.ports.metrics_port import MetricsPort

# 修改后
from src.domain.ports.metrics_port import MetricsPort
```

**T4.2.2 exception_metrics_impl.py**
```python
# 修改前
from src.application.ports.exception_metrics_port import ExceptionMetricsPort

# 修改后
from src.domain.ports.exception_metrics_port import ExceptionMetricsPort
```

**T4.2.3 docker_sandbox_adapter.py**
```python
# 修改前
from src.application.ports.sandbox_port import SandboxExecutor, ContainerStartError, ContainerStopError, ExecutionError

# 修改后
from src.domain.ports.sandbox_port import SandboxExecutor, ContainerStartError, ContainerStopError, ExecutionError
```

**T4.2.4 session_namespace_manager.py**
```python
# 修改前
from src.application.ports.sandbox_port import SandboxExecutor

# 修改后
from src.domain.ports.sandbox_port import SandboxExecutor
```

**T4.2.5 redis_event_bus.py**
```python
# 修改前
from src.application.ports.event_subscriber import EventSubscriber

# 修改后
from src.domain.ports.event_subscriber import EventSubscriber
```

#### 4.3 创建application/ports/__init__.py

```python
# src/application/ports/__init__.py
"""Application ports package — 应用层端口定义

注意: 这些端口是应用层专用，不属于领域逻辑。
大部分端口已迁移到 domain/ports/，此处仅保留应用层特有端口。
"""

from __future__ import annotations

from src.application.ports.text_extractor_service import TextExtractorService
from src.application.ports.compressor_service import CompressorService

__all__ = [
    "CompressorService",
    "TextExtractorService",
]
```

#### 4.4 验证步骤

```bash
# 验证1: Infrastructure不再依赖Application
grep -r "from src.application.ports" src/infrastructure/ | grep -v "__pycache__"

# 验证2: Domain端口可导入
python -c "
from src.domain.ports.metrics_port import MetricsPort
from src.domain.ports.exception_metrics_port import ExceptionMetricsPort
from src.domain.ports.sandbox_port import SandboxExecutor
from src.domain.ports.event_subscriber import EventSubscriber
print('All domain ports importable')
"
```

---

## 三、执行顺序

```
阶段1: 基础设施准备 (可并行)
├── T1.1 创建routing.py和sandbox.py
└── T1.2 创建domain层端口文件

阶段2: 服务文件迁移 (可并行)
├── T1.3.1 更新auto_route_service.py
├── T1.3.2 更新auto_trigger_service.py
├── T1.3.3 更新auto_execute_service.py
├── T1.3.4 更新auto_route_handler.py
└── T1.3.5 更新auto_execute_completed_handler.py

阶段3: 导出补全
└── T2.1 重写__init__.py

阶段4: EventBusFactory修复
└── T3.1 重构EventBusFactory

阶段5: 端口迁移
├── T4.1 创建domain层端口
├── T4.2 更新infrastructure导入
└── T4.3 创建application/ports/__init__.py

阶段6: 验证
└── 运行所有验证脚本
```

---

## 四、风险与回滚

### 4.1 风险识别

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 服务文件导入路径变更 | 运行时ImportError | 保持旧导入路径作为别名 |
| __init__.py导出冲突 | 名称冲突 | 使用as重命名解决 |
| EventBusFactory行为变更 | 事件发布失败 | 保留旧接口兼容 |

### 4.2 回滚方案

每个阶段完成后，执行：
```bash
git checkout HEAD~1 -- src/domain/ports/__init__.py
git checkout HEAD~1 -- src/domain/services/
```

---

## 五、验收标准

### 5.1 功能验收

| 标准 | 验证方法 |
|------|----------|
| 服务内无Protocol定义 | `grep -r "class.*Protocol" src/domain/services/ src/application/event_handlers/` 应无结果 |
| __init__.py导出49个符号 | `python -c "from src.domain.ports import *; print(len(__all__))"` 应输出49 |
| EventBusFactory组件非None | `factory.create_redis_bus()._publisher is not None` |
| Infrastructure不依赖Application | `grep -r "from src.application.ports" src/infrastructure/` 应无结果 |

### 5.2 集成验收

```bash
# 运行单元测试
poetry run pytest tests/unit/domain/services/ -v

# 运行集成测试
poetry run pytest tests/integration/ -v

# 运行类型检查
poetry run mypy src/domain/ports/ --strict
```

---

*文档版本: v1.0*
*执行状态: 待执行*
*前置条件: 已完成代码调研，参考sisys-port-impl-report.md*
