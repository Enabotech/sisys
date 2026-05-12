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

## 六、接口清单与合并方案

### 6.1 接口清单（Domain层）

| 接口名 | 文件 | 用途 | 实现类 | 状态 |
|--------|------|------|--------|------|
| **仓储/存储层** |
| `BaseRepository[T]` | base.py | 通用仓储抽象（泛型） | PostgreSQLRepository | **待修复** |
| `UnitOfWork` | unit_of_work.py | 工作单元，事务边界 | PostgreSQLUnitOfWork | OK |
| `OutboxRepository` | outbox.py | 事务发件箱 | PostgreSQLOutboxRepository, InMemoryOutboxRepository | OK |
| `UserRepositoryPort` | user_repository.py | 用户数据访问 | PostgreSQLUserRepository | OK |
| `RoleRepositoryPort` | role_repository.py | 角色数据访问 | RoleRepository | OK |
| `UserRoleRepositoryPort` | user_role_repository.py | 用户-角色关联 | UserRoleRepository | OK |
| `LoginAttemptRepositoryPort` | login_attempt_repository.py | 登录尝试跟踪 | LoginAttemptRepository | OK |
| `AuditRepositoryPort` | audit_repository.py | 审计日志存储 | AuditRepository | OK |
| **存储分层端口** |
| `L0StoragePort` | l0_storage.py | L0文件系统存储 | FileMemoryAdapter | OK |
| `L1CachePort` | l1_cache.py | L1 Redis缓存 | RedisMemoryCache | OK |
| `L2MetadataRepositoryPort` | l2_rdb.py | L2记忆元数据 | PostgreSQLMemoryMetadataRepository | OK |
| `L2ChangeHistoryRepositoryPort` | l2_rdb.py | L2变更历史 | PostgreSQLMemoryChangeHistoryRepository | OK |
| `L2GroupMemberRepositoryPort` | l2_rdb.py | L2群组成员 | PostgreSQLMemoryGroupMemberRepository | OK |
| `L3VectorPort` | l3_vector.py | L3向量存储 | QdrantVectorAdapter | OK |
| `L4ObjectPort` | l4_object.py | L4对象存储 | MinIOAdapter | OK |
| `L5GraphPort` | l5_graph.py | L5图存储 | Neo4jAdapter | OK |
| `UnifiedStoragePort` | unified_storage.py | 统一存储入口 | UnifiedStorageGateway | OK |
| `SessionStorage` | session_storage.py | 会话状态存储 | RedisSessionStorage | OK |
| `IndexManagerPort` | index_manager.py | MEMORY.md索引 | MemoryIndex | OK |
| `IntegrityPort` | integrity.py | 数据完整性验证 | - | 待实现 |
| `HealthCheckPort` | health_check.py | 健康检查 | - | 待实现 |
| **服务/业务层端口** |
| `AuthServicePort` | auth_service.py | 认证服务 | AuthServiceImpl | OK |
| `AuditServicePort` | audit_service.py | 审计服务 | AuditServiceImpl | OK |
| `PermissionServicePort` | permission_service.py | 权限检查 | PermissionServiceImpl | OK |
| `PasswordValidationServicePort` | password_validation_service.py | 密码验证 | PasswordValidationService | OK |
| `TokenBlacklistPort` | token_blacklist.py | JWT黑名单 | RedisTokenBlacklist | OK |
| `EventPublisher` | event_publisher.py | 领域事件发布 | DualChannelEventBus, RabbitMQEventBus, RedisEventBus | OK |
| `InMemoryEventPublisher` | event_publisher.py | 内存事件发布 | InMemoryEventBus | OK |
| `SensitiveDataDetectorPort` | sensitive_data_detector.py | 敏感数据检测 | SensitiveDataDetectorImpl | OK |
| `ComplianceGatewayPort` | compliance_gateway.py | UDMR合规检查 | ComplianceGatewayImpl | OK |
| `DataResidencyEnforcerPort` | data_residency_enforcer.py | 数据驻留强制 | DataResidencyEnforcerImpl | OK |
| `WhitelistServicePort` | whitelist_service.py | API白名单 | WhitelistServiceImpl | OK |
| `PIPLComplianceServicePort` | pipl_compliance_service.py | PIPL合规服务 | PIPLComplianceServiceImpl | OK |
| `CrossBorderTransferServicePort` | cross_border_transfer_service.py | 跨境传输 | CrossBorderTransferServiceImpl | OK |

### 6.2 接口清单（Application层）

| 接口名 | 文件 | 用途 | 实现类 | 状态 |
|--------|------|------|--------|------|
| `MetricsPort` | metrics_port.py | 指标收集 | MetricsPortImpl | **待迁移** |
| `ExceptionMetricsPort` | exception_metrics_port.py | 异常跟踪 | ExceptionMetricsImpl | **待迁移** |
| `EventSubscriber` | event_subscriber.py | 事件订阅 | - | **待迁移** |
| `SandboxExecutor` | sandbox_port.py | 沙箱执行 | DockerSandboxAdapter | **待迁移** |
| `TextExtractorService` | text_extractor_service.py | 文本提取 | L1TextExtractor | OK |
| `CompressorService` | compressor_service.py | 文本压缩 | L1Compressor | OK |

### 6.3 接口合并方案

#### M1: 合并VectorStorage与L3VectorPort

**问题**: L3层存在`VectorStorage`(vector_storage.py)和`L3VectorPort`(l3_vector.py)两个语义相同的接口

| 接口 | 方法 | 关系 |
|------|------|------|
| `VectorStorage` | `upsert_points`, `search`, `search_sparse`, `delete_points`, `get_point` | 职责视角 |
| `L3VectorPort` | `upsert_points`, `search`, `search_sparse`, `delete_points`, `get_point` | 分层视角 |

**合并方案**:
```python
# src/domain/ports/l3_vector.py
# 保留L3VectorPort作为统一接口，VectorStorage作为别名

class L3VectorPort(Protocol):
    """L3向量存储端口 - 统一接口"""

    async def upsert_points(self, collection: str, points: list[dict]) -> None: ...
    async def search(self, collection: str, query_vector: list[float], limit: int, filter_payload: dict | None = None) -> list[dict]: ...
    async def search_sparse(self, collection: str, sparse_vector: dict, limit: int, filter_payload: dict | None = None) -> list[dict]: ...
    async def delete_points(self, collection: str, point_ids: list[str]) -> None: ...
    async def get_point(self, collection: str, point_id: str) -> dict | None: ...

# src/domain/ports/vector_storage.py
# 简化为类型别名
from src.domain.ports.l3_vector import L3VectorPort

# VectorStorage 已废弃，使用 L3VectorPort 代替
VectorStorage = L3VectorPort  # type: ignore[misc]
```

#### M2: 合并ObjectStorageRepository与L4ObjectPort

**问题**: L4层存在`ObjectStorageRepository`(storage.py)和`L4ObjectPort`(l4_object.py)功能重叠

**合并方案**:
```python
# src/domain/ports/l4_object.py
# 保留L4ObjectPort作为统一接口

class L4ObjectPort(Protocol):
    """L4对象存储端口 - 统一接口"""

    async def store(self, bucket_type: str, object_key: str, file_path: str | None = None, content: bytes | None = None, content_type: str = "application/octet-stream", tags: dict | None = None) -> str: ...
    async def retrieve(self, bucket_type: str, object_key: str, version_id: str | None = None) -> AsyncIterator[bytes]: ...
    async def delete(self, bucket_type: str, object_key: str, version_id: str | None = None) -> bool: ...
    async def get_metadata(self, bucket_type: str, object_key: str, version_id: str | None = None) -> dict: ...
    async def archive(self, bucket_type: str, object_key: str, content: bytes | None = None, retention_days: int = 30) -> str: ...
    async def list_objects(self, bucket_type: str, prefix: str = "") -> list[str]: ...  # 从ObjectStorageRepository迁移

# src/domain/ports/storage.py
# ObjectStorageRepository 已废弃
```

#### M3: 合并GraphManager/GraphStorage与L5GraphPort

**问题**: L5层存在`GraphManager`(低级节点管理)和`GraphStorage`(低级Cypher)与`L5GraphPort`(高级语义)职责边界模糊

**合并方案**:
```python
# src/domain/ports/l5_graph.py
# 统一为L5GraphPort，GraphManager和GraphStorage作为内部实现细节

class L5GraphPort(Protocol):
    """L5图存储端口 - 统一接口

    高级语义接口，内部委托给Neo4jAdapter。
    低级Cypher操作通过execute_query/execute_write_query暴露。
    """

    # 高级语义操作
    async def create_entity(self, memory_id: str, entity_type: str, properties: dict) -> dict: ...
    async def get_entity(self, memory_id: str) -> dict | None: ...
    async def delete_entity(self, memory_id: str) -> bool: ...
    async def create_relationship(self, source_id: str, target_id: str, relationship_type: str, properties: dict | None = None) -> dict: ...
    async def delete_relationship(self, source_id: str, target_id: str, relationship_type: str) -> bool: ...
    async def find_related(self, memory_id: str, max_depth: int = 3, relationship_type: str | None = None) -> list[dict]: ...

    # 低级Cypher操作（保留用于高级场景）
    async def execute_query(self, cypher: str, params: dict | None = None) -> list[dict]: ...
    async def execute_write_query(self, cypher: str, params: dict | None = None) -> list[dict]: ...
```

---

## 七、模块依赖约束

### 7.1 允许的依赖关系

```
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure 层                         │
│  (实现 Domain/Application 层定义的端口，依赖外部服务)          │
└─────────────────────────────────────────────────────────────┘
                              ▲ 实现
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Domain 层                                 │
│  (定义端口接口，零外部依赖，纯业务逻辑)                         │
└─────────────────────────────────────────────────────────────┘
                              ▲ 依赖
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Application 层                             │
│  (编排领域服务，实现应用用例，依赖Domain层端口)                  │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 各模块允许的依赖

| 模块 | 允许依赖 | 禁止依赖 |
|------|---------|---------|
| **domain/ports/** | Python标准库, typing | application/, infrastructure/, 外部服务 |
| **domain/services/** | domain/ports/, domain/events/, domain/entities/ | application/, infrastructure/, 外部服务 |
| **domain/events/** | domain/base/, Python标准库 | application/, infrastructure/ |
| **application/ports/** | domain/ports/, Python标准库 | infrastructure/, 外部服务 |
| **application/services/** | domain/ports/, application/ports/, domain/services/ | infrastructure/直接导入 |
| **application/event_handlers/** | domain/ports/, domain/events/, domain/services/ | infrastructure/直接导入 |
| **infrastructure/** | domain/ports/, application/ports/, 外部服务SDK | domain/services/直接导入（通过端口间接） |

### 7.3 具体约束规则

**规则1: 禁止跨层继承**
```python
# 禁止：Infrastructure层类继承Domain层具体类
class PostgreSQLRepository(BaseRepository):  # BaseRepository是Domain端口
    pass  # 这是允许的（实现端口）

# 禁止：Infrastructure层类继承Application层具体类
class MyService(MetricsPort):  # 禁止 - Application层端口应由Application层实现
    pass
```

**规则2: 禁止Infrastructure直接导入Application Use Cases**
```python
# 禁止
from src.application.use_cases.role_management import RoleNotFoundError

# 允许：Infrastructure抛出Domain异常
from src.domain.exceptions import DomainException
```

**规则3: 禁止Domain层导入Infrastructure**
```python
# 禁止
from src.infrastructure.storage.redis import RedisClient

# 允许：通过端口注入实现
class MyService:
    def __init__(self, cache: L1CachePort):  # 端口由外部注入
        self._cache = cache
```

---

## 八、跨模块继承修复方案

### 8.1 问题识别

**问题**: SQLAlchemy模型继承infrastructure层的Base类，导致Domain层绑定具体技术实现

```python
# src/infrastructure/storage/postgresql/models/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# src/infrastructure/storage/postgresql/models/user.py
class UserModel(Base):  # 继承infrastructure的Base
    pass
```

### 8.2 修复方案：适配器模式

**将Domain实体与SQLAlchemy模型解耦**:

```python
# src/domain/entities/user.py
"""Domain实体 - 不绑定任何基础设施"""

from dataclasses import dataclass
from uuid import UUID
from datetime import datetime

@dataclass
class User:
    id: UUID
    username: str
    email: str
    created_at: datetime
    is_active: bool
```

```python
# src/infrastructure/storage/postgresql/models/user.py
"""Infrastructure模型 - 继承SQLAlchemy Base"""

from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from .base import Base

class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 不再继承domain实体
```

```python
# src/infrastructure/storage/postgresql/mappers/user_mapper.py
"""Domain实体与Infrastructure模型映射"""

from uuid import UUID
from src.domain.entities.user import User
from src.infrastructure.storage.postgresql.models.user import UserModel

class UserMapper:
    @staticmethod
    def to_domain(model: UserModel) -> User:
        return User(
            id=model.id,
            username=model.username,
            email=model.email,
            created_at=model.created_at,
            is_active=model.is_active,
        )

    @staticmethod
    def to_model(entity: User) -> UserModel:
        return UserModel(
            id=entity.id,
            username=entity.username,
            email=entity.email,
            created_at=entity.created_at,
            is_active=entity.is_active,
        )
```

**依赖方向修正**:
```
Domain (User) ← 无依赖
    ↑
    │
Infrastructure (UserModel + UserMapper) → 继承Base，使用Mapper转换
```

---

## 九、公共接口契约测试

### 9.1 契约测试框架

**使用 `pytest-playwright` 或 `behave` 进行接口契约测试**

### 9.2 端口契约测试模板

```python
# tests/contracts/domain/ports/test_l1_cache_port.py
"""L1CachePort契约测试"""

import pytest
from typing import Protocol
from src.domain.ports.l1_cache import L1CachePort

class L1CachePortContract:
    """L1CachePort契约测试套件

    所有实现L1CachePort的类必须通过此测试套件。
    """

    @pytest.fixture
    def port(self) -> L1CachePort:
        """由子类实现，返回被测端口实例"""
        raise NotImplementedError

    async def test_get_returns_none_for_missing_key(self, port: L1CachePort):
        """未存在的key应返回None"""
        result = await port.get("nonexistent_type", "user123", "nonexistent")
        assert result is None

    async def test_set_and_get_returns_value(self, port: L1CachePort):
        """设置后应能获取相同值"""
        await port.set("memory", "user123", "test_key", "test_value", ttl=3600)
        result = await port.get("memory", "user123", "test_key")
        assert result == "test_value"

    async def test_delete_removes_value(self, port: L1CachePort):
        """删除后应返回None"""
        await port.set("memory", "user123", "test_key", "test_value")
        await port.delete("memory", "user123", "test_key")
        result = await port.get("memory", "user123", "test_key")
        assert result is None

    async def test_invalidate_pattern_removes_matching(self, port: L1CachePort):
        """模式失效应删除所有匹配项"""
        await port.set("memory", "user123", "key1", "value1")
        await port.set("memory", "user123", "key2", "value2")
        await port.set("memory", "user123", "key3", "value3")
        count = await port.invalidate_pattern("memory", "user123")
        assert count == 3
        assert await port.get("memory", "user123", "key1") is None


class TestRedisMemoryCacheContract(L1CachePortContract):
    """RedisMemoryCache契约测试"""

    @pytest.fixture
    def port(self) -> L1CachePort:
        from src.infrastructure.storage.redis.redis_memory_cache import RedisMemoryCache
        return RedisMemoryCache()
```

### 9.3 关键端口契约测试清单

| 端口 | 测试文件 | 测试项 |
|------|---------|--------|
| `L1CachePort` | test_l1_cache_port.py | get/set/delete/invalidate_pattern |
| `L3VectorPort` | test_l3_vector_port.py | upsert_points/search/delete_points/get_point |
| `EventPublisher` | test_event_publisher.py | publish返回PublishResult |
| `OutboxRepository` | test_outbox_repository.py | save/get_unpublished/mark_published |
| `UnifiedStoragePort` | test_unified_storage_port.py | save/read/delete/exists |

### 9.4 契约测试执行

```bash
# 运行所有契约测试
poetry run pytest tests/contracts/ -v

# 运行特定端口契约测试
poetry run pytest tests/contracts/domain/ports/test_l1_cache_port.py -v

# 生成契约测试报告
poetry run pytest tests/contracts/ --cov=src --cov-report=html
```

---

## 十、架构检查规则

### 10.1 检查工具配置

```yaml
# pyproject.toml 或 .archy.toml
[tool.archi]
rules:
  - id: no-service-protocol
    description: "服务文件内部禁止定义Protocol"
    pattern: "src/domain/services/*.py"
    check: "class.*Protocol"
    severity: error

  - id: no-infra-depends-on-app
    description: "Infrastructure层禁止依赖Application层"
    pattern: "src/infrastructure/**/*.py"
    forbidden_imports:
      - "src.application.ports"
      - "src.application.use_cases"
    severity: error

  - id: no-domain-depends-on-infra
    description: "Domain层禁止依赖Infrastructure层"
    pattern: "src/domain/**/*.py"
    forbidden_imports:
      - "src.infrastructure"
    severity: error

  - id: port-must-be-exported
    description: "所有端口必须在__init__.py中导出"
    pattern: "src/domain/ports/*.py"
    check: "class.*Port"
    severity: warning
```

### 10.2 pre-commit检查

```yaml
# .git/hooks/pre-commit
#!/bin/bash
echo "Running architecture checks..."

# 检查1: 服务文件无Protocol定义
if grep -r "class.*Protocol" src/domain/services/ src/application/event_handlers/ 2>/dev/null | grep -v "from src.domain.ports"; then
    echo "ERROR: Service files contain local Protocol definitions"
    exit 1
fi

# 检查2: Infrastructure不依赖Application
if grep -r "from src.application" src/infrastructure/ 2>/dev/null; then
    echo "ERROR: Infrastructure depends on Application layer"
    exit 1
fi

# 检查3: Domain不依赖Infrastructure
if grep -r "from src.infrastructure" src/domain/ 2>/dev/null; then
    echo "ERROR: Domain depends on Infrastructure layer"
    exit 1
fi

echo "Architecture checks passed"
```

### 10.3 CI/CD架构检查

```yaml
# .github/workflows/architecture.yml
name: Architecture Check

on: [push, pull_request]

jobs:
  architecture:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Run architecture checks
        run: |
          # 服务文件无Protocol定义
          ! grep -r "class.*Protocol" src/domain/services/ src/application/event_handlers/ | grep -v "from src.domain.ports"

          # Infrastructure不依赖Application
          ! grep -r "from src.application" src/infrastructure/

          # Domain不依赖Infrastructure
          ! grep -r "from src.infrastructure" src/domain/
```

### 10.4 阻止新混乱的机制

| 机制 | 触发条件 | 行为 |
|------|---------|------|
| pre-commit hook | git commit | 检查违规则拒绝提交 |
| CI/CD check | PR/push | 运行架构检查，失败则阻止合并 |
| IDE警告 | 保存.py文件 | 实时检查依赖方向 |
| mypy严格模式 | 类型检查 | 检查导入依赖 |

---

## 十一、重构执行顺序（更新）

```
阶段1: 基础设施准备
├── 1.1 创建routing.py和sandbox.py
├── 1.2 创建domain层端口（迁移Application端口）
└── 1.3 创建application/ports/__init__.py

阶段2: 服务文件迁移
├── 2.1 更新auto_route_service.py
├── 2.2 更新auto_trigger_service.py
├── 2.3 更新auto_execute_service.py
├── 2.4 更新auto_route_handler.py
└── 2.5 更新auto_execute_completed_handler.py

阶段3: 导出补全
└── 3.1 重写__init__.py（49个符号）

阶段4: EventBusFactory修复
└── 4.1 重构EventBusFactory（延迟初始化）

阶段5: 接口合并
├── 5.1 合并VectorStorage与L3VectorPort
├── 5.2 合并ObjectStorageRepository与L4ObjectPort
└── 5.3 统一GraphManager/GraphStorage与L5GraphPort

阶段6: 跨模块继承修复
├── 6.1 创建Domain实体映射器
├── 6.2 重构BaseRepository泛型约束
└── 6.3 替换SQLAlchemy模型继承

阶段7: 契约测试
└── 7.1 为关键端口编写契约测试

阶段8: 架构检查
├── 8.1 配置pre-commit hooks
└── 8.2 配置CI/CD架构检查
```

---

*文档版本: v1.1*
*更新内容:*
*- 第六章: 接口清单与合并方案*
*- 第七章: 模块依赖约束*
*- 第八章: 跨模块继承修复方案（适配器模式）*
*- 第九章: 公共接口契约测试*
*- 第十章: 架构检查规则*
*- 第十一章: 更新执行顺序*

*执行状态: 待执行*
