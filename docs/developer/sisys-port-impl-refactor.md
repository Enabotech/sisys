# SISYS 端口开发与管理重构执行方案

**文档版本:** v2.0
**生成时间:** 2026-05-12
**基于:** sisys-port-impl-report.md 全面调研结果

---

## 一、接口清单

### 1.1 Domain层端口（41个）

| 端口名 | 文件 | 用途 | 实现类 | 状态 |
|--------|------|------|--------|------|
| **仓储基础** |
| `BaseRepository[T]` | base.py | 通用仓储抽象 | PostgreSQLRepository | **待修复** |
| `UnitOfWork` | unit_of_work.py | 工作单元 | PostgreSQLUnitOfWork | OK |
| `OutboxRepository` | outbox.py | 事务发件箱 | PostgreSQLOutboxRepository | OK |
| **用户与认证** |
| `UserRepositoryPort` | user_repository.py | 用户数据访问 | PostgreSQLUserRepository | OK |
| `AuthServicePort` | auth_service.py | 认证服务 | AuthServiceImpl | OK |
| `LoginAttemptRepositoryPort` | login_attempt_repository.py | 登录尝试跟踪 | LoginAttemptRepository | OK |
| `TokenBlacklistPort` | token_blacklist.py | JWT黑名单 | RedisTokenBlacklist | OK |
| `PasswordValidationServicePort` | password_validation_service.py | 密码验证 | PasswordValidationService | OK |
| **角色与权限** |
| `RoleRepositoryPort` | role_repository.py | 角色数据访问 | RoleRepository | OK |
| `UserRoleRepositoryPort` | user_role_repository.py | 用户-角色关联 | UserRoleRepository | OK |
| `PermissionServicePort` | permission_service.py | 权限检查 | PermissionServiceImpl | OK |
| **审计** |
| `AuditRepositoryPort` | audit_repository.py | 审计日志存储 | AuditRepository | OK |
| `AuditServicePort` | audit_service.py | 审计服务 | AuditServiceImpl | OK |
| **存储分层（L0-L5）** |
| `L0StoragePort` | l0_storage.py | L0文件系统 | FileMemoryAdapter | OK |
| `L1CachePort` | l1_cache.py | L1 Redis缓存 | RedisMemoryCache | OK |
| `L2MetadataRepositoryPort` | l2_rdb.py | L2元数据 | PostgreSQLMemoryMetadataRepository | OK |
| `L2ChangeHistoryRepositoryPort` | l2_rdb.py | L2变更历史 | PostgreSQLMemoryChangeHistoryRepository | OK |
| `L2GroupMemberRepositoryPort` | l2_rdb.py | L2群组成员 | PostgreSQLMemoryGroupMemberRepository | OK |
| `L3VectorPort` | l3_vector.py | L3向量存储 | QdrantVectorAdapter | OK |
| `L4ObjectPort` | l4_object.py | L4对象存储 | MinIOAdapter | OK |
| `L5GraphPort` | l5_graph.py | L5图存储 | Neo4jAdapter | OK |
| `UnifiedStoragePort` | unified_storage.py | 统一存储入口 | UnifiedStorageGateway | OK |
| `SessionStorage` | session_storage.py | 会话状态存储 | RedisSessionStorage | OK |
| `IndexManagerPort` | index_manager.py | MEMORY索引 | MemoryIndex | OK |
| **其他存储** |
| `CollectionManager` | vector_storage.py | Collection管理 | QdrantCollectionManager | OK |
| `IntegrityPort` | integrity.py | 数据完整性验证 | - | 待实现 |
| `HealthCheckPort` | health_check.py | 健康检查 | - | 待实现 |
| **事件发布** |
| `EventPublisher` | event_publisher.py | 领域事件发布 | DualChannelEventBus等 | OK |
| `InMemoryEventPublisher` | event_publisher.py | 内存事件发布 | InMemoryEventBus | OK |
| **合规服务** |
| `ComplianceGatewayPort` | compliance_gateway.py | UDMR合规检查 | ComplianceGatewayImpl | OK |
| `SensitiveDataDetectorPort` | sensitive_data_detector.py | 敏感数据检测 | SensitiveDataDetectorImpl | OK |
| `DataResidencyEnforcerPort` | data_residency_enforcer.py | 数据驻留强制 | DataResidencyEnforcerImpl | OK |
| `WhitelistServicePort` | whitelist_service.py | API白名单 | WhitelistServiceImpl | OK |
| `PIPLComplianceServicePort` | pipl_compliance_service.py | PIPL合规服务 | PIPLComplianceServiceImpl | OK |
| `CrossBorderTransferServicePort` | cross_border_transfer_service.py | 跨境传输 | CrossBorderTransferServiceImpl | OK |
| **枚举类型** |
| `StorageLayer` | storage_enums.py | 存储层级枚举 | - | OK |
| `StorageTier` | storage_enums.py | 存储层级类型 | - | OK |
| `DataAccessPattern` | storage_enums.py | 访问模式枚举 | - | OK |

### 1.2 Application层端口（6个）

| 端口名 | 文件 | 用途 | 实现类 | 状态 |
|--------|------|------|--------|------|
| `MetricsPort` | metrics_port.py | 指标收集 | MetricsPortImpl | **待迁移到Domain** |
| `ExceptionMetricsPort` | exception_metrics_port.py | 异常跟踪 | ExceptionMetricsImpl | **待迁移到Domain** |
| `EventSubscriber` | event_subscriber.py | 事件订阅 | - | **待迁移到Domain** |
| `SandboxExecutor` | sandbox_port.py | 沙箱执行 | DockerSandboxAdapter | **待迁移到Domain** |
| `TextExtractorService` | text_extractor_service.py | 文本提取 | L1TextExtractor | OK |
| `CompressorService` | compressor_service.py | 文本压缩 | L1Compressor | OK |

### 1.3 服务文件本地Protocol（8个 - 待迁移）

| 文件 | Protocol名称 | 行号 | 应迁移至 |
|------|------------|------|---------|
| `auto_route_service.py` | `EventPublisherProtocol` | 15 | domain/ports/event_publisher.py |
| `auto_route_service.py` | `HashRouterProtocol` | 21 | domain/ports/routing.py |
| `auto_route_service.py` | `SemanticRouterProtocol` | 36 | domain/ports/routing.py |
| `auto_trigger_service.py` | `EventPublisherProtocol` | 15 | domain/ports/event_publisher.py |
| `auto_execute_service.py` | `SandboxExecutorProtocol` | 25 | domain/ports/sandbox.py |
| `auto_execute_service.py` | `SnapshotRepositoryProtocol` | 41 | domain/ports/sandbox.py |
| `auto_route_handler.py` | `EventPublisherProtocol` | 27 | domain/ports/event_publisher.py |
| `auto_execute_completed_handler.py` | `EventPublisherProtocol` | 18 | domain/ports/event_publisher.py |

---

## 二、接口合并方案

### 2.1 M1: VectorStorage 与 L3VectorPort 合并

**问题**: L3层存在两个语义相同的接口

| 接口 | 方法 | 关系 |
|------|------|------|
| `VectorStorage` (vector_storage.py) | `upsert_points`, `search`, `search_sparse`, `delete_points`, `get_point` | 职责视角命名 |
| `L3VectorPort` (l3_vector.py) | `upsert_points`, `search`, `search_sparse`, `delete_points`, `get_point` | 分层视角命名 |

**合并方案**:
```python
# src/domain/ports/l3_vector.py
class L3VectorPort(Protocol):
    """L3向量存储端口 - 统一接口"""

    async def upsert_points(self, collection: str, points: list[dict]) -> None: ...
    async def search(self, collection: str, query_vector: list[float], limit: int, filter_payload: dict | None = None) -> list[dict]: ...
    async def search_sparse(self, collection: str, sparse_vector: dict, limit: int, filter_payload: dict | None = None) -> list[dict]: ...
    async def delete_points(self, collection: str, point_ids: list[str]) -> None: ...
    async def get_point(self, collection: str, point_id: str) -> dict | None: ...

# src/domain/ports/vector_storage.py
# 简化为类型别名（向后兼容）
from src.domain.ports.l3_vector import L3VectorPort
VectorStorage = L3VectorPort  # type: ignore[misc]
```

### 2.2 M2: ObjectStorageRepository 与 L4ObjectPort 合并

**问题**: L4层存在功能重叠的两个接口

**合并方案**:
```python
# src/domain/ports/l4_object.py
class L4ObjectPort(Protocol):
    """L4对象存储端口 - 统一接口"""

    async def store(self, bucket_type: str, object_key: str, file_path: str | None = None, content: bytes | None = None, content_type: str = "application/octet-stream", tags: dict | None = None) -> str: ...
    async def retrieve(self, bucket_type: str, object_key: str, version_id: str | None = None) -> AsyncIterator[bytes]: ...
    async def delete(self, bucket_type: str, object_key: str, version_id: str | None = None) -> bool: ...
    async def get_metadata(self, bucket_type: str, object_key: str, version_id: str | None = None) -> dict: ...
    async def archive(self, bucket_type: str, object_key: str, content: bytes | None = None, retention_days: int = 30) -> str: ...
    async def list_objects(self, bucket_type: str, prefix: str = "") -> list[str]: ...

# src/domain/ports/storage.py
# ObjectStorageRepository 已废弃
```

### 2.3 M3: GraphManager/GraphStorage 与 L5GraphPort 统一

**问题**: L5层低级接口与高级接口职责边界模糊

**合并方案**:
```python
# src/domain/ports/l5_graph.py
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

## 三、模块依赖约束

### 3.1 允许的依赖关系

```
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure 层                         │
│  (实现 Domain/Application 层定义的端口，依赖外部服务SDK)       │
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

### 3.2 各模块允许/禁止依赖

| 模块 | 允许依赖 | 禁止依赖 |
|------|---------|---------|
| `domain/ports/` | Python标准库, typing | application/, infrastructure/, 外部服务 |
| `domain/services/` | domain/ports/, domain/events/, domain/entities/ | application/, infrastructure/, 外部服务 |
| `domain/events/` | domain/base/, Python标准库 | application/, infrastructure/ |
| `application/ports/` | domain/ports/, Python标准库 | infrastructure/, 外部服务 |
| `application/services/` | domain/ports/, application/ports/, domain/services/ | infrastructure/直接导入 |
| `infrastructure/` | domain/ports/, application/ports/, 外部服务SDK | domain/services/直接导入 |

### 3.3 约束规则

**规则1: 服务文件禁止定义Protocol**
```python
# 禁止：服务文件内部定义Protocol
class AutoRouteService:
    class EventPublisherProtocol(Protocol):  # 违规
        pass

# 正确：通过端口文件导入
from src.domain.ports.event_publisher import EventPublisher
```

**规则2: Infrastructure禁止依赖Application端口**
```python
# 禁止
from src.application.ports.metrics_port import MetricsPort

# 正确：应迁移到Domain层
from src.domain.ports.metrics_port import MetricsPort
```

**规则3: Infrastructure禁止导入Application Use Cases**
```python
# 禁止
from src.application.use_cases.role_management import RoleNotFoundError

# 正确：使用Domain异常
from src.domain.exceptions import DomainException
```

**规则4: Domain禁止依赖Infrastructure**
```python
# 禁止
from src.infrastructure.storage.redis import RedisClient

# 正确：通过端口注入
def __init__(self, cache: L1CachePort):
    self._cache = cache
```

---

## 四、跨模块继承修复

### 4.1 问题识别

**问题**: SQLAlchemy模型继承infrastructure层的Base类，导致Domain层绑定具体技术实现

```python
# src/infrastructure/storage/postgresql/models/base.py
from sqlalchemy.orm import DeclarativeBase
class Base(DeclarativeBase):
    pass

# src/infrastructure/storage/postgresql/models/user.py
class UserModel(Base):  # 继承infrastructure的Base - 违规
    pass
```

### 4.2 修复方案：Domain实体与Infrastructure模型解耦

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
from .base import Base

class UserModel(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    email: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
```

```python
# src/infrastructure/storage/postgresql/mappers/user_mapper.py
"""Domain实体与Infrastructure模型映射"""
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

---

## 五、公共接口契约测试

### 5.1 端口契约测试模板

```python
# tests/contracts/domain/ports/test_l1_cache_port.py
"""L1CachePort契约测试 - 所有实现必须通过"""

import pytest
from src.domain.ports.l1_cache import L1CachePort

class L1CachePortContract:
    """L1CachePort契约测试套件"""

    @pytest.fixture
    def port(self) -> L1CachePort:
        raise NotImplementedError

    async def test_get_returns_none_for_missing_key(self, port: L1CachePort):
        result = await port.get("nonexistent_type", "user123", "nonexistent")
        assert result is None

    async def test_set_and_get_returns_value(self, port: L1CachePort):
        await port.set("memory", "user123", "test_key", "test_value", ttl=3600)
        result = await port.get("memory", "user123", "test_key")
        assert result == "test_value"

    async def test_delete_removes_value(self, port: L1CachePort):
        await port.set("memory", "user123", "test_key", "test_value")
        await port.delete("memory", "user123", "test_key")
        assert await port.get("memory", "user123", "test_key") is None

    async def test_invalidate_pattern_removes_matching(self, port: L1CachePort):
        await port.set("memory", "user123", "key1", "value1")
        await port.set("memory", "user123", "key2", "value2")
        count = await port.invalidate_pattern("memory", "user123")
        assert count == 2


class TestRedisMemoryCacheContract(L1CachePortContract):
    @pytest.fixture
    def port(self) -> L1CachePort:
        from src.infrastructure.storage.redis.redis_memory_cache import RedisMemoryCache
        return RedisMemoryCache()
```

### 5.2 关键端口契约测试清单

| 端口 | 测试文件 | 测试项 |
|------|---------|--------|
| `L1CachePort` | test_l1_cache_port.py | get/set/delete/invalidate_pattern |
| `L3VectorPort` | test_l3_vector_port.py | upsert_points/search/delete_points/get_point |
| `EventPublisher` | test_event_publisher.py | publish返回PublishResult |
| `OutboxRepository` | test_outbox_repository.py | save/get_unpublished/mark_published |
| `UnifiedStoragePort` | test_unified_storage_port.py | save/read/delete/exists |

### 5.3 契约测试执行

```bash
# 运行所有契约测试
poetry run pytest tests/contracts/ -v

# 运行特定端口契约测试
poetry run pytest tests/contracts/domain/ports/test_l1_cache_port.py -v
```

---

## 六、架构检查规则

### 6.1 检查规则

| 规则ID | 描述 | 模式 | 严重性 |
|--------|------|------|--------|
| `no-service-protocol` | 服务文件内部禁止定义Protocol | `src/domain/services/*.py` | error |
| `no-infra-depends-on-app` | Infrastructure禁止依赖Application | `src/infrastructure/**/*.py` | error |
| `no-domain-depends-on-infra` | Domain禁止依赖Infrastructure | `src/domain/**/*.py` | error |
| `port-must-be-exported` | 所有端口必须在__init__.py导出 | `src/domain/ports/*.py` | warning |

### 6.2 pre-commit检查脚本

```bash
#!/bin/bash
# .git/hooks/pre-commit

# 检查1: 服务文件无Protocol定义
if grep -r "class.*Protocol" src/domain/services/ src/application/event_handlers/ 2>/dev/null | grep -v "from src.domain.ports" | grep -v "from src.application.ports"; then
    echo "ERROR: Service files contain local Protocol definitions"
    exit 1
fi

# 检查2: Infrastructure不依赖Application
if grep -r "from src.application.ports" src/infrastructure/ 2>/dev/null; then
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

### 6.3 CI/CD架构检查

```yaml
# .github/workflows/architecture.yml
name: Architecture Check

on: [push, pull_request]

jobs:
  architecture:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Run architecture checks
        run: |
          ! grep -r "class.*Protocol" src/domain/services/ src/application/event_handlers/ | grep -v "from src.domain.ports" | grep -v "from src.application.ports"
          ! grep -r "from src.application" src/infrastructure/
          ! grep -r "from src.infrastructure" src/domain/
```

---

## 七、重构执行顺序

```
阶段1: 服务内Protocol迁移
├── 1.1 创建 domain/ports/routing.py
├── 1.2 创建 domain/ports/sandbox.py
└── 1.3 更新5个服务文件导入

阶段2: 补全__init__.py导出
└── 2.1 重写domain/ports/__init__.py（41个符号）

阶段3: 修复EventBusFactory
└── 3.1 实现延迟初始化

阶段4: 迁移Application端口到Domain
├── 4.1 创建 domain/ports/metrics_port.py
├── 4.2 创建 domain/ports/exception_metrics_port.py
├── 4.3 创建 domain/ports/event_subscriber.py
├── 4.4 创建 domain/ports/sandbox_port.py
└── 4.5 更新infrastructure导入路径

阶段5: 接口合并
├── 5.1 合并VectorStorage与L3VectorPort
├── 5.2 合并ObjectStorageRepository与L4ObjectPort
└── 5.3 统一GraphManager/GraphStorage与L5GraphPort

阶段6: 跨模块继承修复
├── 6.1 创建Domain实体映射器
└── 6.2 重构BaseRepository泛型约束

阶段7: 契约测试
└── 7.1 为关键端口编写契约测试

阶段8: 架构检查
├── 8.1 配置pre-commit hooks
└── 8.2 配置CI/CD架构检查
```

---

## 八、验收标准

### 8.1 功能验收

| 标准 | 验证方法 |
|------|----------|
| 服务内无Protocol定义 | `grep -r "class.*Protocol" src/domain/services/ src/application/event_handlers/` 应无结果 |
| __init__.py导出41个符号 | `python -c "from src.domain.ports import *; print(len(__all__))"` 应输出41 |
| EventBusFactory组件非None | `factory.create_redis_bus()._publisher is not None` |
| Infrastructure不依赖Application | `grep -r "from src.application.ports" src/infrastructure/` 应无结果 |

### 8.2 集成验收

```bash
# 运行单元测试
poetry run pytest tests/unit/domain/services/ -v

# 运行集成测试
poetry run pytest tests/integration/ -v

# 运行契约测试
poetry run pytest tests/contracts/ -v

# 运行类型检查
poetry run mypy src/domain/ports/ --strict
```

---

*文档版本: v2.0*
*更新内容:*
*- 第一章: 接口清单（41 Domain + 6 Application + 8 待迁移）*
*- 第二章: 接口合并方案（M1/M2/M3）*
*- 第三章: 模块依赖约束（允许/禁止依赖）*
*- 第四章: 跨模块继承修复（适配器模式）*
*- 第五章: 公共接口契约测试*
*- 第六章: 架构检查规则*
*- 第七章: 重构执行顺序（8阶段）*
*- 第八章: 验收标准*

*执行状态: 待执行*
