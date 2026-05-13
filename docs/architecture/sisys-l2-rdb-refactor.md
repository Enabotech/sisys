# SISYS L2 RDB 重构详细设计

**版本：** 1.2.0
**状态：** 设计中
**日期：** 2026-05-13
**架构师：** Claude Code

---

## 0. 方案评估结果

### 0.1 业界最佳实践对照

| 维度 | 方案设计 | 业界实践（Spring Data JPA） | 评估 |
|------|---------|---------------------------|------|
| 统一基类 | `L2RdbPort` | `JpaRepository` | ✅ 正确 |
| 端口继承 | 具体端口继承基类 | `XxxRepository extends JpaRepository` | ✅ 正确 |
| 会话管理 | `PostgreSqlRdbAdapter` 统一管理 | `EntityManager` 注入 | ✅ 正确 |
| CRUD 复用 | `BaseRepository` | `SimpleJpaRepository` | ✅ 正确 |

### 0.2 事务边界决策

| 选项 | 描述 | 推荐度 | 本系统选择 |
|------|------|--------|-----------|
| A. Repository 层 | 每个 Repository 方法自己管理事务 | ⭐⭐ | - |
| B. **应用层/UseCase 层** | 在用例编排层开启事务 | ⭐⭐⭐ | **✅ 采用** |
| C. 基础设施层 Adapter | PostgreSqlRdbAdapter 统一控制 | ⭐⭐ | - |

**决策理由**：符合 DDD 事务边界原则，UseCase 是业务事务的边界，Repository 只负责数据访问。

### 0.3 优化点说明

| 优化点 | 原方案 | 优化后 | 理由 |
|--------|-------|--------|------|
| 命名 | - | 保持 `L2RdbPort` | 与系统 L0-L5 存储层级语义一致 |
| 接口签名 | `execute_in_transaction(func, *args)` | 保持当前设计 | FastAPI/SQLAlchemy 生态函数式事务更灵活 |
| 事务控制 | - | 应用层/UseCase 层 | 符合 DDD 事务边界原则 |

### 0.4 核心架构确认

```
┌─────────────────────────────────────────────────────────────┐
│  Spring Data JPA 模式 (业界标准)                          │
│                                                             │
│  Repository (marker)                                        │
│      ↓                                                     │
│  CrudRepository<T, ID>  ← 提供 CRUD 基石                    │
│      ↓                                                     │
│  PagingAndSortingRepository  ← 分页排序支持                 │
│      ↓                                                     │
│  JpaRepository<T, ID>  ← JPA 特定能力（flush/batch）        │
│                                                             │
│  具体业务仓储继承：                                          │
│  UserRepository extends JpaRepository<User, Long>           │
└─────────────────────────────────────────────────────────────┘

                          ↕ 对应本系统

┌─────────────────────────────────────────────────────────────┐
│  本系统 L2RdbPort 模式                                    │
│                                                             │
│  L2RdbPort (统一抽象基类)  ← 等同于 CrudRepository        │
│      ↓                                                     │
│  L2MemoryRepositoryPort(L2RdbPort)  ← 等同于 JpaRepository │
│      ↓                                                     │
│  PostgreSQLMemoryMetadataRepository  ← 具体实现              │
│                                                             │
│  具体业务仓储继承：                                          │
│  UserRepositoryPort(L2RdbPort)                            │
│  PostgreSQLUserRepository(UserRepositoryPort)              │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. 现状分析

### 1.1 现有问题

| 问题编号 | 问题描述 | 影响范围 |
|---------|---------|---------|
| P1 | `l2_rdb.py` 仅包含记忆系统三个端口，缺少统一抽象基类 `L2RdbPort` | 无法统一管理所有 RDB 仓储 |
| P2 | `user_repository.py`、`role_repository.py`、`audit_repository.py` 等独立定义，未继承任何基类 | 违背 DRY 原则，无法统一管控 |
| P3 | `base.py` 定义 `BaseRepository` Protocol，但未与 `l2_rdb.py` 关联 | 领域层与 L2 存储抽象割裂 |
| P4 | 基础设施层 `base_repository.py` 无领域层基类对应 | 依赖倒置不完整 |
| P5 | 各 Repository 自己管理 Session，无统一数据库连接管理 | 数据库连接管理混乱 |

### 1.2 现有代码结构

```
src/domain/ports/
├── l2_rdb.py              # 仅含 L2MemoryMetadataRepositoryPort 等 3 个端口，缺少 L2RdbPort 基类
├── base.py                # BaseRepository Protocol（未与 l2_rdb 关联）
├── user_repository.py     # UserRepositoryPort（独立定义，未继承任何基类）
├── role_repository.py     # RoleRepositoryPort（独立定义，未继承任何基类）
├── audit_repository.py    # AuditRepositoryPort（独立定义，未继承任何基类）
├── login_attempt_repository.py  # LoginAttemptRepositoryPort（独立定义，未继承任何基类）
└── user_role_repository.py      # UserRoleRepositoryPort（独立定义，未继承任何基类）

src/infrastructure/storage/postgresql/
├── engine.py              # DatabaseEngine（数据库引擎）✅ 已实现
├── repository/
│   ├── base_repository.py # BaseRepository（基础设施层 CRUD 基类）✅ 已实现
│   ├── user_repository.py      # UserRepository(BaseRepository) ❌ 未实现 UserRepositoryPort
│   ├── role_repository.py      # RoleRepository(BaseRepository) ❌ 未实现 RoleRepositoryPort
│   └── memory_metadata_repository.py  # PostgreSQLMemoryMetadataRepository ✅ 已实现 L2MetadataRepositoryPort
```

### 1.3 现有端口清单（代码现状）

| 端口名称 | 文件位置 | 当前基类 | 目标基类 | 状态 |
|---------|---------|---------|---------|------|
| `L2RdbPort` | **不存在** | - | 统一抽象基类 | ❌ 缺失 |
| `L2MetadataRepositoryPort` | l2_rdb.py | 无 | L2RdbPort | ❌ 待升级 |
| `L2ChangeHistoryRepositoryPort` | l2_rdb.py | 无 | L2RdbPort | ❌ 待升级 |
| `L2GroupMemberRepositoryPort` | l2_rdb.py | 无 | L2RdbPort | ❌ 待升级 |
| `UserRepositoryPort` | user_repository.py | 无 | L2RdbPort | ❌ 待升级 |
| `RoleRepositoryPort` | role_repository.py | 无 | L2RdbPort | ❌ 待升级 |
| `AuditRepositoryPort` | audit_repository.py | 无 | L2RdbPort | ❌ 待升级 |
| `LoginAttemptRepositoryPort` | login_attempt_repository.py | 无 | L2RdbPort | ❌ 待升级 |
| `UserRoleRepositoryPort` | user_role_repository.py | 无 | L2RdbPort | ❌ 待升级 |

### 1.4 基础设施层实现状态

| 实现类 | 位置 | 继承基类 | 实现端口 | 状态 |
|-------|------|---------|---------|------|
| `BaseRepository` | repository/base_repository.py | Generic[T] | 无 | ✅ 已有 |
| `UserRepository` | repository/user_repository.py | BaseRepository | ❌无 | ❌ 未实现端口 |
| `RoleRepository` | repository/role_repository.py | BaseRepository | ❌无 | ❌ 未实现端口 |
| `PostgreSQLMemoryMetadataRepository` | repository/memory_metadata_repository.py | 无 | L2MetadataRepositoryPort | ✅ 已实现 |

### 1.5 关键发现：设计与实现脱节

**问题根因分析：**

1. **L2RdbPort 基类缺失**：文档定义了基类，但代码未创建
2. **领域层端口未统一**：8个端口各自独立，未继承基类
3. **基础设施层未实现端口**：BaseRepository 是 CRUD 实现，不是端口实现
4. **无 PostgreSqlRdbAdapter**：文档定义的适配器未实现

---

## 2. 业界最佳实践对标

### 2.1 DDD 六边形架构标准模式

```
┌─────────────────────────────────────────────────────────────┐
│  领域层 (Domain) - 纯抽象，无外部依赖                       │
│                                                             │
│  ports/                                                     │
│  └── l2_rdb.py                                              │
│      ├── L2RdbPort (统一抽象基类) ← 所有具体端口继承此       │
│      ├── L2MemoryRepositoryPort(L2RdbPort)                  │
│      ├── UserRepositoryPort(L2RdbPort)                      │
│      ├── RoleRepositoryPort(L2RdbPort)                      │
│      └── AuditRepositoryPort(L2RdbPort)                      │
└─────────────────────────────────────────────────────────────┘
                              ↕ 依赖倒置
┌─────────────────────────────────────────────────────────────┐
│  基础设施层 (Infrastructure)                                 │
│                                                             │
│  rdb/                                                      │
│  ├── rdb_adapter.py         # PostgreSqlRdbAdapter(L2RdbPort)│
│  │   └── 连接管理 / 会话管理 / 事务控制                     │
│  └── repository/                                             │
│      ├── base_repository.py # BaseRepository                │
│      ├── user_repository.py  # implements UserRepositoryPort│
│      └── role_repository.py  # implements RoleRepositoryPort │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心设计原则

| 原则 | 描述 | 实现方式 |
|------|------|---------|
| **依赖倒置** | 领域层定义接口，基础设施层实现 | 所有端口继承 `L2RdbPort` |
| **单一职责** | 每个端口只负责一种实体的数据访问 | 按实体类型分离端口 |
| **开闭原则** | 对扩展开放，对修改关闭 | 新增端口只需继承 `L2RdbPort` |
| **接口隔离** | 专用接口优于通用接口 | 保持专用端口，仅共享基类契约 |
| **事务边界** | 业务事务边界在应用层/UseCase 层 | Repository 只做数据访问 |

### 2.3 事务边界设计

```
┌─────────────────────────────────────────────────────────────┐
│  应用层 (Application Layer)                                 │
│                                                             │
│  UseCase / Service                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ async def create_user(cmd: CreateUserCommand):        │ │
│  │     async with unit_of_work.transaction():           │ │
│  │         user = await user_repo.get_by_username(...)  │ │
│  │         await user_repo.save(user)                   │ │
│  │         await audit_repo.save(...)                   │ │
│  └─────────────────────────────────────────────────────┘ │
│                      ↑                                     │
│              事务边界在此层                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  领域层 (Domain Layer)                                     │
│                                                             │
│  Repository Port (L2RdbPort)  ← 仅定义接口，不管理事务    │
│  ├── get_by_id()                                          │
│  ├── save()                                               │
│  └── delete()                                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  基础设施层 (Infrastructure Layer)                          │
│                                                             │
│  PostgreSQLUserRepository  ← 实现接口，不管理事务          │
│  BaseRepository  ← 通用 CRUD                              │
└─────────────────────────────────────────────────────────────┘
```

**关键原则**：
- `L2RdbPort.execute_in_transaction()` 仅作为基础设施内部使用
- 业务事务边界由 **应用层/UseCase** 控制
- 遵循 DDD "事务脚本 vs 领域模型" 原则

### 2.4 业界参考实现

| 参考项目 | 模式 | 本系统适配 |
|---------|------|----------|
| **Spring Data JPA** | `JpaRepository` 基类 + 专用接口继承 | `L2RdbPort` 基类 + 专用端口继承 |
| **SQLAlchemy** | `DeclarativeBase` + `MappedColumn` | 领域实体与模型分离映射 |
| **Laravel Eloquent** | `Model` 基类 + `EloquentBuilder` | `BaseRepository` 通用 CRUD |

---

### 2.5 四层职责模型

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Domain Layer - L2RdbPort（统一抽象 RDB 端口）        │
│                                                                  │
│  职责：定义最底层通用 RDB 接口（get_by_id/save/delete/list_all）│
│  位置：src/domain/ports/l2_rdb.py                               │
│  特点：领域层零依赖，纯抽象协议                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Domain Layer - 具体应用 RDB 端口                       │
│                                                                  │
│  职责：继承 L2RdbPort，定义特定实体数据访问契约                   │
│  位置：src/domain/ports/                                          │
│  端口：                                                          │
│    - L2MetadataRepositoryPort(L2RdbPort)     (记忆系统)           │
│    - L2ChangeHistoryRepositoryPort(L2RdbPort)                    │
│    - L2GroupMemberRepositoryPort(L2RdbPort)                     │
│    - UserRepositoryPort(L2RdbPort)          (用户系统)           │
│    - RoleRepositoryPort(L2RdbPort)           (角色系统)          │
│    - AuditRepositoryPort(L2RdbPort)           (审计系统)         │
│    - LoginAttemptRepositoryPort(L2RdbPort)   (登录系统)          │
│    - UserRoleRepositoryPort(L2RdbPort)        (用户角色系统)      │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: Infrastructure - PostgreSQL 技术实现 + RDB 管理        │
│                                                                  │
│  职责：实现 L2RdbPort 接口 + 数据库连接池统一管理                 │
│  位置：src/infrastructure/storage/postgresql/                     │
│  组件：                                                          │
│    - rdb_adapter.py                                             │
│    │     PostgreSqlRdbAdapter (实现 L2RdbPort)                   │
│    │     └── 职责：连接管理 / 会话管理 / 事务控制                  │
│    - engine.py                                                   │
│    │     DatabaseEngine (数据库引擎单例)                          │
│    │     └── 职责：连接池初始化 / 健康检查 / 优雅关闭             │
│  特点：技术可替换（未来可新增 MySqlAdapter 等）                   │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: Infrastructure - 具体应用 RDB 端口实现                  │
│                                                                  │
│  职责：实现具体应用 RDB 端口（UserRepositoryPort 等）            │
│  位置：src/infrastructure/storage/postgresql/repository/           │
│  组件：                                                          │
│    - PostgreSQLUserRepository(UserRepositoryPort)                │
│    │     └─ 继承 BaseRepository，复用 CRUD                      │
│    - PostgreSQLRoleRepository(RoleRepositoryPort)                │
│    - PostgreSQLMemoryMetadataRepository(L2MetadataRepositoryPort) │
│    - PostgreSQLAuditRepository(AuditRepositoryPort)              │
│    - PostgreSQLLoginAttemptRepository(LoginAttemptRepositoryPort)│
│    - PostgreSQLUserRoleRepository(UserRoleRepositoryPort)       │
│  特点：组合 PostgreSqlRdbAdapter 获取会话，委托 BaseRepository   │
│        处理通用 CRUD，专注实现业务特定查询                        │
└─────────────────────────────────────────────────────────────────┘
```

### 2.6 接口继承关系

```python
# Layer 1: Domain 统一抽象
class L2RdbPort(Protocol):
    """通用 RDB 接口 - 最底层抽象"""
    async def get_by_id(self, id: UUID) -> Any | None: ...
    async def save(self, entity: Any) -> Any: ...
    async def delete(self, id: UUID) -> bool: ...
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Any]: ...
    async def execute_in_transaction(self, func: Callable, *args, **kwargs) -> Any: ...

# Layer 2: Domain 具体应用端口
class UserRepositoryPort(L2RdbPort, Protocol):
    """用户仓储接口 - 继承 L2RdbPort"""
    async def get_by_username(self, username: str) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...

class RoleRepositoryPort(L2RdbPort, Protocol):
    """角色仓储接口 - 继承 L2RdbPort"""
    pass

# Layer 3: Infrastructure PostgreSQL 技术实现
class PostgreSqlRdbAdapter(L2RdbPort):
    """PostgreSQL RDB 适配器"""
    def __init__(self, engine: DatabaseEngine):
        self._engine = engine
        self._session: AsyncSession | None = None

    async def get_session(self) -> AsyncSession: ...

class DatabaseEngine:
    """数据库引擎单例"""
    def get_async_engine(self) -> AsyncEngine: ...
    async def get_async_session(self) -> AsyncIterator[AsyncSession]: ...
    async def health_check(self) -> bool: ...

# Layer 4: Infrastructure 具体应用实现
class PostgreSQLUserRepository(UserRepositoryPort, BaseRepository[UserModel]):
    """PostgreSQL 用户仓储实现"""
    def __init__(self, session: AsyncSession):
        BaseRepository.__init__(self, UserModel, session)

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(select(UserModel).where(...))
        ...
```

### 2.7 与 L1 Cache 四层模型对照

| 层级 | L1 Cache | L2 RDB |
|------|----------|--------|
| **Layer 1** | `L1CachePort` (统一缓存抽象) | `L2RdbPort` (统一 RDB 抽象) |
| **Layer 2** | `SemanticCachePort` (语义缓存) | `UserRepositoryPort` (用户仓储) |
| | `MemoryCachePort` (记忆缓存) | `RoleRepositoryPort` (角色仓储) |
| | `SessionStoragePort` (会话存储) | `AuditRepositoryPort` (审计仓储) |
| **Layer 3** | `RedisL1CacheAdapter` (Redis 实现) | `PostgreSqlRdbAdapter` (PG 适配器) |
| | `DatabaseEngine` (连接管理) | `DatabaseEngine` (连接管理) |
| **Layer 4** | `RedisSemanticCacheAdapter` | `PostgreSQLUserRepository` |

---

## 3. 重构目标

### 3.1 架构目标

```
┌─────────────────────────────────────────────────────────────┐
│  目标架构                                                   │
│                                                             │
│  src/domain/ports/                                         │
│  └── l2_rdb.py                                             │
│      ├── L2RdbPort (统一基类) ← 所有具体端口继承此         │
│      ├── L2MetadataRepositoryPort(L2RdbPort)               │
│      ├── L2ChangeHistoryRepositoryPort(L2RdbPort)          │
│      ├── L2GroupMemberRepositoryPort(L2RdbPort)            │
│      ├── UserRepositoryPort(L2RdbPort)                     │
│      ├── RoleRepositoryPort(L2RdbPort)                     │
│      ├── AuditRepositoryPort(L2RdbPort)                    │
│      ├── LoginAttemptRepositoryPort(L2RdbPort)             │
│      └── UserRoleRepositoryPort(L2RdbPort)                  │
│                                                             │
│  src/infrastructure/storage/postgresql/                     │
│  ├── rdb_adapter.py          # PostgreSqlRdbAdapter(L2RdbPort)│
│  └── repository/                                             │
│      ├── base_repository.py  # BaseRepository               │
│      ├── memory_metadata_repository.py                    │
│      ├── user_repository.py                                │
│      └── role_repository.py                                │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 验收标准

| 标准 | 描述 | 测量方式 |
|------|------|---------|
| R1 | 所有 RDB 端口继承 `L2RdbPort` 基类 | 代码审查 |
| R2 | 基础设施层提供统一的 `PostgreSqlRdbAdapter` | 实现验证 |
| R3 | 现有功能保持不变 | 回归测试通过率 100% |
| R4 | 数据库连接管理统一到 `PostgreSqlRdbAdapter` | 代码审查 |
| R5 | 可扩展支持其他 RDB 实现（如 MySQL） | 架构验证 |
| R6 | 事务边界在应用层/UseCase 层 | 代码审查 |

---

## 4. 详细设计

### 4.1 L2RdbPort 基类设计

```python
# src/domain/ports/l2_rdb.py

from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar, Protocol
from uuid import UUID

T = TypeVar("T")


class L2RdbPort(Protocol):
    """统一 RDB 存储抽象基类。

    定义所有 RDB 仓储的通用接口契约。
    所有具体应用端口应继承此基类。

    设计原则：
    - 领域层零外部依赖（仅用 Protocol + typing）
    - 通用 CRUD 操作统一定义
    - 事务支持通过 execute_in_transaction 实现
    """

    # === 通用 CRUD ===

    async def get_by_id(self, id: UUID) -> Any | None:
        """通过 ID 获取实体。

        Args:
            id: 实体 UUID

        Returns:
            实体实例，不存在返回 None
        """

    async def save(self, entity: Any) -> Any:
        """保存实体（插入或更新）。

        Args:
            entity: 领域实体

        Returns:
            保存后的实体
        """

    async def delete(self, id: UUID) -> bool:
        """删除实体。

        Args:
            id: 实体 UUID

        Returns:
            True 删除成功，False 不存在
        """

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Any]:
        """列出所有实体。

        Args:
            skip: 跳过数量
            limit: 返回数量上限

        Returns:
            实体列表
        """

    # === 事务支持 ===

    async def execute_in_transaction(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """在事务内执行操作。

        Args:
            func: 要执行的异步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值

        Raises:
            事务内任意异常自动回滚
        """
```

### 4.2 端口文件重组

#### 4.2.1 l2_rdb.py（统一基类 + 记忆系统端口）

```python
# src/domain/ports/l2_rdb.py
# ============================================================================
# L2RdbPort — 统一 RDB 存储抽象基类
# ============================================================================

from __future__ import annotations

from typing import Any, Callable, Protocol, TypeVar
from uuid import UUID

T = TypeVar("T")


class L2RdbPort(Protocol):
    """统一 RDB 存储抽象基类。

    所有具体应用端口应继承此基类，获得通用 CRUD 和事务支持。
    """

    async def get_by_id(self, id: UUID) -> T | None: ...
    async def save(self, entity: T) -> T: ...
    async def delete(self, id: UUID) -> bool: ...
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[T]: ...

    async def execute_in_transaction(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any: ...


# ============================================================================
# 记忆系统仓储端口（L2 存储层）
# ============================================================================

class L2MetadataRepositoryPort(L2RdbPort, Protocol):
    """L2 记忆元数据仓储端口。

    架构来源: architecture.md §11.2.5
    """

    async def get_by_name(self, name: str) -> "MemoryMetadata | None": ...
    async def list_by_user(self, user_id: str) -> list["MemoryMetadata"]: ...
    async def list_by_type(self, memory_type: str) -> list["MemoryMetadata"]: ...


class L2ChangeHistoryRepositoryPort(L2RdbPort, Protocol):
    """L2 记忆变更历史仓储端口。"""
    pass


class L2GroupMemberRepositoryPort(L2RdbPort, Protocol):
    """L2 群组成员关系仓储端口。"""

    async def is_group_member(self, group_id: str, user_id: str) -> bool: ...
    async def is_group_admin(self, group_id: str, user_id: str) -> bool: ...
    async def add_member(self, group_id: str, user_id: str, role: str = "member") -> None: ...
    async def remove_member(self, group_id: str, user_id: str) -> None: ...
```

#### 4.2.2 user_repository.py（继承 L2RdbPort）

```python
# src/domain/ports/user_repository.py

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.entities.user import User


class UserRepositoryPort(L2RdbPort, Protocol):
    """用户仓储端口（继承 L2RdbPort）。

    遵循六边形架构：领域层零依赖。
    """

    async def get_by_username(self, username: str) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...
```

#### 4.2.3 role_repository.py（继承 L2RdbPort）

```python
# src/domain/ports/role_repository.py

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.entities.role import Role


class RoleRepositoryPort(L2RdbPort, Protocol):
    """角色仓储端口（继承 L2RdbPort）。"""
    pass
```

#### 4.2.4 其他端口文件（继承 L2RdbPort）

| 文件 | 端口名 | 需继承 L2RdbPort |
|------|--------|-----------------|
| audit_repository.py | AuditRepositoryPort | 是 |
| login_attempt_repository.py | LoginAttemptRepositoryPort | 是 |
| user_role_repository.py | UserRoleRepositoryPort | 是 |

### 4.3 基础设施层设计

#### 4.3.1 rdb_adapter.py（PostgreSQL RDB 适配器）

```python
# src/infrastructure/storage/postgresql/rdb_adapter.py

"""PostgreSqlRdbAdapter — PostgreSQL RDB 适配器。

实现 L2RdbPort 接口，提供统一的数据库连接和事务管理。
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ports.l2_rdb import L2RdbPort
from src.infrastructure.storage.postgresql.engine import DatabaseEngine

T = TypeVar("T")


class PostgreSqlRdbAdapter(L2RdbPort):
    """PostgreSQL RDB 适配器实现。

    职责：
    - 数据库会话管理
    - 事务控制
    - 委托具体 Repository 执行数据操作

    使用方式：
    - 注入到具体 Repository
    - 通过 execute_in_transaction 提供事务支持
    """

    def __init__(self, engine: DatabaseEngine):
        """初始化 PostgreSqlRdbAdapter。

        Args:
            engine: 数据库引擎实例
        """
        self._engine = engine
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        """获取当前会话（延迟初始化）。"""
        if self._session is None:
            raise RuntimeError("Session not initialized. Use get_session() first.")
        return self._session

    async def get_session(self) -> AsyncSession:
        """获取或创建会话。"""
        if self._session is None:
            async with self._engine.get_async_session() as session:
                self._session = session
        return self._session

    async def execute_in_transaction(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """在事务内执行操作。

        Args:
            func: 要执行的异步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值
        """
        async with self._engine.get_async_session() as session:
            self._session = session
            try:
                result = await func(*args, **kwargs)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
            finally:
                self._session = None

    async def get_by_id(self, id: UUID) -> Any | None:
        """通用 get_by_id（由具体 Repository 覆盖）。"""
        raise NotImplementedError("Use specific repository implementation")

    async def save(self, entity: Any) -> Any:
        """通用 save（由具体 Repository 覆盖）。"""
        raise NotImplementedError("Use specific repository implementation")

    async def delete(self, id: UUID) -> bool:
        """通用 delete（由具体 Repository 覆盖）。"""
        raise NotImplementedError("Use specific repository implementation")

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Any]:
        """通用 list_all（由具体 Repository 覆盖）。"""
        raise NotImplementedError("Use specific repository implementation")
```

#### 4.3.2 base_repository.py（更新）

```python
# src/infrastructure/storage/postgresql/repository/base_repository.py

"""BaseRepository — 通用仓储基类。

所有具体仓储类继承此基类，复用 CRUD 操作。
需要配合 PostgreSqlRdbAdapter 使用。

设计原则：
- 泛型类型参数 T 为 SQLAlchemy 模型
- 依赖注入 PostgreSqlRdbAdapter 获取会话
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.models import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """通用仓储基类。

    泛型类型参数 T 必须是 SQLAlchemy 模型（继承自 Base）。
    """

    def __init__(self, model_class: type[T], session: AsyncSession):
        """初始化 BaseRepository。

        Args:
            model_class: SQLAlchemy 模型类
            session: 异步数据库会话
        """
        self._model_class: type[T] = model_class
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """获取当前会话。"""
        return self._session

    async def get_by_id(self, id: str) -> T | None:
        """根据 ID 获取实体。"""
        result = await self._session.execute(
            select(self._model_class).where(cast(Any, self._model_class).id == id)
        )
        return result.scalar_one_or_none()

    async def save(self, entity: T) -> T:
        """保存实体（插入或更新）。"""
        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def delete(self, id: str) -> None:
        """删除实体。"""
        entity = await self.get_by_id(id)
        if entity:
            await self._session.delete(entity)
            await self._session.flush()

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[T]:
        """获取实体列表。"""
        result = await self._session.execute(
            select(self._model_class).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        """获取实体总数。"""
        result = await self._session.execute(
            select(func.count()).select_from(self._model_class)
        )
        return int(result.scalar() or 0)
```

#### 4.3.3 具体 Repository 实现模板

```python
# src/infrastructure/storage/postgresql/repository/user_repository.py

"""PostgreSQLUserRepository — 用户仓储实现。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user import User
from src.domain.ports.user_repository import UserRepositoryPort
from src.infrastructure.storage.postgresql.models import UserModel
from src.infrastructure.storage.postgresql.repository.base_repository import BaseRepository


class PostgreSQLUserRepository(UserRepositoryPort, BaseRepository[UserModel]):
    """用户仓储 PostgreSQL 实现。

    继承关系：
    - UserRepositoryPort (领域层接口)
    - BaseRepository (通用 CRUD)
    """

    def __init__(self, session: AsyncSession):
        """初始化 PostgreSQLUserRepository。

        Args:
            session: 异步数据库会话
        """
        BaseRepository.__init__(self, UserModel, session)

    def _to_entity(self, model: UserModel) -> User:
        """模型转领域实体。"""
        return User(
            id=model.id,
            username=model.username,
            password_hash=model.password_hash,
            is_active=model.is_active,
            is_locked=model.is_locked,
            failed_login_attempts=model.failed_login_attempts,
            locked_until=model.locked_until,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: User) -> UserModel:
        """领域实体转模型。"""
        return UserModel(
            id=entity.id,
            username=entity.username,
            password_hash=entity.password_hash,
            is_active=entity.is_active,
            is_locked=entity.is_locked,
            failed_login_attempts=entity.failed_login_attempts,
            locked_until=entity.locked_until,
        )

    async def get_by_username(self, username: str) -> User | None:
        """根据用户名获取用户。"""
        result = await self._session.execute(
            select(UserModel).where(UserModel.username == username)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        """根据邮箱获取用户。"""
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
```

---

## 5. 目录结构

### 5.1 重构后结构

```
src/domain/ports/
├── __init__.py              # 更新：导出 L2RdbPort
├── base.py                   # 保留（供其他场景使用）
├── l2_rdb.py                 # ★ 重构：统一基类 + 记忆系统端口
├── user_repository.py        # ★ 更新：继承 L2RdbPort
├── role_repository.py        # ★ 更新：继承 L2RdbPort
├── audit_repository.py       # ★ 更新：继承 L2RdbPort
├── login_attempt_repository.py  # ★ 更新：继承 L2RdbPort
├── user_role_repository.py   # ★ 更新：继承 L2RdbPort
└── ...

src/infrastructure/storage/postgresql/
├── __init__.py              # 更新：导出 PostgreSqlRdbAdapter
├── engine.py                # 保持不变 ✅
├── rdb_adapter.py           # ★ 新增：PostgreSqlRdbAdapter
├── models/                  # 保持不变
│   ├── __init__.py
│   ├── user.py
│   ├── role.py
│   └── memory.py
└── repository/
    ├── __init__.py          # 更新：导出
    ├── base_repository.py   # ★ 更新：补充文档
    ├── user_repository.py   # ★ 更新：实现 UserRepositoryPort
    ├── role_repository.py   # ★ 更新：实现 RoleRepositoryPort
    ├── memory_metadata_repository.py  # ★ 更新：实现 L2MetadataRepositoryPort
    └── ...
```

---

## 6. 执行步骤

### 6.1 阶段划分

| 阶段 | 任务 | 风险 | 预计工时 | 依赖 |
|------|------|------|---------|------|
| Phase 0 | 代码现状审计 | 低 | 0.25d | 无 |
| Phase 1 | 设计评审与确认 | 低 | 0.25d | Phase 0 |
| Phase 2 | 创建 L2RdbPort 基类 | 低 | 0.5d | Phase 1 |
| Phase 3 | 更新领域层端口（继承基类） | 中 | 1d | Phase 2 |
| Phase 4 | 创建 PostgreSqlRdbAdapter | 低 | 0.5d | Phase 2 |
| Phase 5 | 更新基础设施层 Repository | 中 | 1d | Phase 3, Phase 4 |
| Phase 6 | 更新 __init__.py 导出 | 低 | 0.25d | Phase 5 |
| Phase 7 | 回归测试 | 中 | 1d | Phase 6 |
| Phase 8 | 文档更新 | 低 | 0.25d | Phase 7 |

### 6.2 详细执行步骤

#### Phase 0: 代码现状审计

- [ ] 确认 `src/domain/ports/l2_rdb.py` 当前内容（3个端口，无基类）
- [ ] 确认 `src/domain/ports/user_repository.py` 当前内容
- [ ] 确认 `src/domain/ports/role_repository.py` 当前内容
- [ ] 确认 `src/domain/ports/audit_repository.py` 当前内容
- [ ] 确认 `src/domain/ports/login_attempt_repository.py` 当前内容
- [ ] 确认 `src/domain/ports/user_role_repository.py` 当前内容
- [ ] 确认 `src/infrastructure/storage/postgresql/repository/` 下实现类
- [ ] 确认 `src/infrastructure/storage/postgresql/engine.py` 实现状态
- [ ] 列出需要修改的所有文件清单

#### Phase 1: 设计评审与确认

- [ ] 评审本文档
- [ ] 确认重构范围
- [ ] 获取 Stakeholder 批准

#### Phase 2: 创建 L2RdbPort 基类

- [ ] 更新 `src/domain/ports/l2_rdb.py`
- [ ] 添加 `L2RdbPort` Protocol 基类
- [ ] 保留现有 `L2MetadataRepositoryPort` 等三个端口（继承基类）
- [ ] 添加类型注解

#### Phase 3: 更新领域层端口（继承基类）

- [ ] 更新 `src/domain/ports/user_repository.py` - `UserRepositoryPort` 继承 `L2RdbPort`
- [ ] 更新 `src/domain/ports/role_repository.py` - `RoleRepositoryPort` 继承 `L2RdbPort`
- [ ] 更新 `src/domain/ports/audit_repository.py` - `AuditRepositoryPort` 继承 `L2RdbPort`
- [ ] 更新 `src/domain/ports/login_attempt_repository.py` - `LoginAttemptRepositoryPort` 继承 `L2RdbPort`
- [ ] 更新 `src/domain/ports/user_role_repository.py` - `UserRoleRepositoryPort` 继承 `L2RdbPort`

#### Phase 4: 创建 PostgreSqlRdbAdapter

- [ ] 创建 `src/infrastructure/storage/postgresql/rdb_adapter.py`
- [ ] 实现 `PostgreSqlRdbAdapter` 类
- [ ] 实现 `execute_in_transaction` 方法
- [ ] 添加会话管理逻辑

#### Phase 5: 更新基础设施层 Repository

- [ ] 更新 `base_repository.py` - 补充文档注释
- [ ] 更新 `user_repository.py` - 实现 `UserRepositoryPort`
- [ ] 更新 `role_repository.py` - 实现 `RoleRepositoryPort`
- [ ] 更新 `memory_metadata_repository.py` - 实现 `L2MetadataRepositoryPort`
- [ ] 更新其他 Repository 实现

#### Phase 6: 更新 __init__.py 导出

- [ ] 更新 `src/domain/ports/__init__.py` - 导出 `L2RdbPort`
- [ ] 更新 `src/infrastructure/storage/postgresql/__init__.py` - 导出 `PostgreSqlRdbAdapter`
- [ ] 更新 `src/infrastructure/storage/postgresql/repository/__init__.py` - 导出

#### Phase 7: 回归测试

- [ ] 运行单元测试
- [ ] 运行集成测试
- [ ] 验证数据库操作正常
- [ ] 验证事务回滚正常

#### Phase 8: 文档更新

- [ ] 更新 `architecture.md` 存储架构章节
- [ ] 更新 `CLAUDE.md` 如有必要
- [ ] 更新相关注释

### 6.3 实施追踪表

| 端口/实现 | 当前状态 | Phase 2 | Phase 3 | Phase 5 |
|-----------|---------|---------|---------|---------|
| `L2RdbPort` | ❌ 不存在 | ✅ 创建 | - | - |
| `L2MetadataRepositoryPort` | 独立定义 | → 继承基类 | - | - |
| `L2ChangeHistoryRepositoryPort` | 独立定义 | → 继承基类 | - | - |
| `L2GroupMemberRepositoryPort` | 独立定义 | → 继承基类 | - | - |
| `UserRepositoryPort` | 独立定义 | - | → 继承基类 | - |
| `RoleRepositoryPort` | 独立定义 | - | → 继承基类 | - |
| `AuditRepositoryPort` | 独立定义 | - | → 继承基类 | - |
| `LoginAttemptRepositoryPort` | 独立定义 | - | → 继承基类 | - |
| `UserRoleRepositoryPort` | 独立定义 | - | → 继承基类 | - |
| `PostgreSqlRdbAdapter` | ❌ 不存在 | - | - | ✅ 创建 |
| `PostgreSQLMemoryMetadataRepository` | ✅ 已实现 | - | - | → 验证 |
| `PostgreSQLUserRepository` | 未实现端口 | - | - | → 实现端口 |

---

## 7. 风险评估与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| R1: 破坏现有功能 | 中 | 高 | 完整的回归测试；每次修改后运行测试 |
| R2: 类型注解错误 | 中 | 中 | 使用 mypy 检查；IDE 类型提示验证 |
| R3: 事务语义变化 | 低 | 高 | 详细测试事务 commit/rollback 场景 |
| R4: 循环导入 | 低 | 中 | 遵循 Python import 顺序；类型注解使用字符串 |
| R5: 多个端口同时修改 | 中 | 中 | 按 Phase 顺序执行；每个 Phase 独立测试 |

---

## 8. 兼容性考虑

### 8.1 向后兼容

| 组件 | 变更类型 | 兼容策略 |
|------|---------|---------|
| `L2MetadataRepositoryPort` | 接口扩展 | 保持原有方法签名 |
| `UserRepositoryPort` | 基类变更 | 新增继承，不改变接口 |
| 所有 Repository 实现 | 实现更新 | 保持原有方法实现 |
| `BaseRepository` | 无变更 | 保持现有 CRUD |

### 8.2 依赖方适配

需要适配的模块：

| 模块 | 适配内容 |
|------|---------|
| `UnifiedStorageGateway` | 无需变更（依赖端口接口） |
| `AuthService` | 无需变更（依赖端口接口） |
| `RoleService` | 无需变更（依赖端口接口） |

---

## 9. 扩展性设计

### 9.1 支持其他 RDB 实现

```python
# MySQL 适配器示例（未来扩展）

class MySqlRdbAdapter(L2RdbPort):
    """MySQL RDB 适配器实现。"""

    def __init__(self, config: MySQLConfig):
        self._config = config
        # MySQL 连接逻辑

    async def execute_in_transaction(self, func: Callable, *args, **kwargs) -> Any:
        # MySQL 事务逻辑
        pass
```

### 9.2 单元测试 Mock

```python
# 测试中使用 Mock 实现

class MockL2RdbAdapter(L2RdbPort):
    """测试用 Mock RDB 适配器。"""

    def __init__(self):
        self._storage: dict[str, Any] = {}

    async def get_by_id(self, id: UUID) -> Any | None:
        return self._storage.get(str(id))

    async def save(self, entity: Any) -> Any:
        self._storage[str(entity.id)] = entity
        return entity

    # ... 其他方法实现
```

---

## 10. 附录

### 10.1 术语表

| 术语 | 定义 |
|------|------|
| L2RdbPort | 统一 RDB 存储抽象基类 |
| PostgreSqlRdbAdapter | PostgreSQL 的 L2RdbPort 实现 |
| BaseRepository | 基础设施层通用 CRUD 基类 |
| 六边形架构 | 领域驱动架构模式，又名端口与适配器 |

### 10.2 参考文档

- [架构文档 - 存储架构设计](../../architecture/architecture.md)
- [六边形架构模式 - Martin Fowler](https://martinfowler.com/articles/hexagonal-architecture.html)
- [DDD 仓储模式 - Eric Evans](https://domainlanguage.com/)

---

**审批记录**

| 版本 | 日期 | 审批人 | 状态 |
|------|------|--------|------|
| 1.0.0 | 2026-05-13 | - | 初始版本 |
| 1.1.0 | 2026-05-13 | - | 补充业界最佳实践对照 + 事务边界设计 |
| 1.2.0 | 2026-05-13 | - | 补充现状审计 + 实施追踪表 + Phase 0 |
