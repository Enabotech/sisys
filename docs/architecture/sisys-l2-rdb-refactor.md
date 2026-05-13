# SISYS L2 RDB 重构详细设计

**版本：** 1.8.0
**状态：** 设计中
**日期：** 2026-05-13
**架构师：** Claude Code
**审查状态：** 第7轮审查完成

---

## 0. 方案评估结果

### 0.0 审查修正说明（v1.4.0）

| 问题编号 | 问题描述 | 修正方案 |
|---------|---------|---------|
| R-1 | `execute_in_transaction` 归属歧义 | 该方法在代码库中**完全不存在**，原文档描述了未实现的功能；修正为删除相关描述（见§4.2.1） |
| R-2 | `UserRepositoryPort` 接口不完整 | 补充 `save`/`delete`/`list_all` 标准 CRUD，与 `RoleRepositoryPort` 一致 |
| R-3 | 会话管理机制不明 | 明确 `BaseRepository` 通过构造器注入 `AsyncSession` |
| R-4 | `PostgreSqlRdbAdapter` 角色定位 | `PostgreSqlRdbAdapter` 在代码库中**不存在**，是可选重构目标；当前系统使用 `PostgreSQLUnitOfWork` 管理事务 |
| R-5 | 系统使用 **UnitOfWork** 而非 `execute_in_transaction` | 事务边界通过 `PostgreSQLUnitOfWork` 管理，非 adapter 方法 |
| R-6 | `get_by_email` 方法错误定义 | User 实体无 `email` 字段，移除该方法定义 |
| R-7 | UserModel 与 User 实体字段不一致 | 需领域层与基础设施层对齐（见 §1.6） |
| R-8 | architecture.md 与本文档不一致 | 明确两文档定位：前者宏观架构，后者详细设计 |
| R-9 | L2RdbPort 重构价值明确 | 既能提供统一契约约束（强制一致性），又为未来复用扩展提供良好基础 |

### 0.1 业界最佳实践对照

| 维度 | 方案设计 | 业界实践（Spring Data JPA） | 评估 |
|------|---------|---------------------------|------|
| 统一基类 | `L2RdbPort` | `JpaRepository` | ✅ 正确 |
| 端口继承 | 具体端口继承基类 | `XxxRepository extends JpaRepository` | ✅ 正确 |
| 会话管理 | `DatabaseEngine` + `PostgreSQLUnitOfWork` | `EntityManager` 注入 | ✅ 正确（修正） |
| CRUD 复用 | `BaseRepository` | `SimpleJpaRepository` | ✅ 正确 |
| 事务边界 | `PostgreSQLUnitOfWork` (应用层管理) | `@Transactional` 在 Service 层 | ✅ 正确（修正） |

### 0.2 事务边界决策

| 选项 | 描述 | 推荐度 | 本系统选择 |
|------|------|--------|-----------|
| A. Repository 层 | 每个 Repository 方法自己管理事务 | ⭐⭐ | - |
| B. **应用层/UseCase 层** | 在用例编排层开启事务 | ⭐⭐⭐ | **✅ 采用** |
| C. 基础设施层 Adapter | PostgreSqlRdbAdapter 统一控制 | ⭐⭐ | - |

**决策理由**：
- 符合 DDD 事务边界原则，UseCase 是业务事务的边界，Repository 只负责数据访问
- 实际系统使用 `PostgreSQLUnitOfWork` 作为事务边界（非 adapter 方法）
- 不在 `L2RdbPort` 接口中暴露事务方法，避免污染领域接口契约

### 0.3 优化点说明

| 优化点 | 原方案 | 优化后 | 理由 |
|--------|-------|--------|------|
| 命名 | - | 保持 `L2RdbPort` | 与系统 L0-L5 存储层级语义一致 |
| 事务控制 | 无 | `PostgreSQLUnitOfWork` | 事务边界在应用层，Repository 不感知事务 |
| 会话管理 | - | `BaseRepository` 构造器注入 | 明确依赖，不隐藏依赖关系 |
| 接口完整性 | `UserRepositoryPort` 缺 CRUD | 补充完整 | 与 `RoleRepositoryPort` 一致 |

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
│   ├── role_repository.py      # RoleRepository(RoleRepositoryPort) ✅ 已实现 RoleRepositoryPort
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
| `UserRepository` | repository/user_repository.py | BaseRepository | ⚠️ 未声明实现 UserRepositoryPort | ⚠️ 需修复 |
| `RoleRepository` | repository/role_repository.py | RoleRepositoryPort | ✅ RoleRepositoryPort | ✅ 已实现 |
| `PostgreSQLMemoryMetadataRepository` | repository/memory_metadata_repository.py | L2MetadataRepositoryPort | ✅ L2MetadataRepositoryPort | ✅ 已实现 |
| `LoginAttemptRepository` | repository/login_attempt_repository.py | LoginAttemptRepositoryPort | ✅ LoginAttemptRepositoryPort | ✅ 已实现 |
| `UserRoleRepository` | repository/user_role_repository.py | UserRoleRepositoryPort | ✅ UserRoleRepositoryPort | ✅ 已实现 |
| `AuditRepository` | infrastructure/security/ | AuditRepositoryPort | ✅ AuditRepositoryPort | ✅ 已实现 |
| `PostgreSQLMemoryChangeHistoryRepository` | repository/memory_change_history_repository.py | L2ChangeHistoryRepositoryPort | ✅ L2ChangeHistoryRepositoryPort | ✅ 已实现 |
| `PostgreSQLMemoryGroupMemberRepository` | repository/memory_group_member_repository.py | L2GroupMemberRepositoryPort | ✅ L2GroupMemberRepositoryPort | ✅ 已实现 |
| `PostgreSQLUnitOfWork` | infrastructure/messaging/unit_of_work/ | UnitOfWork | ✅ UnitOfWork | ✅ 已实现 |

### 1.5 关键发现：设计与实现脱节

**问题根因分析：**

1. **L2RdbPort 基类缺失**：文档定义了基类，但代码未创建（是**重构目标**，非当前状态）
2. **领域层端口未统一**：8个端口各自独立，未继承基类（是**待解决问题**，但价值存疑）
3. **UserRepository 未声明实现端口**：继承 BaseRepository 但未声明实现 UserRepositoryPort
4. **PostgreSqlRdbAdapter 不存在**：文档定义的适配器未实现（但系统有 PostgreSQLUnitOfWork）
5. **领域模型与基础设施模型不一致**：User 实体无 email 字段，但 UserModel 有

### 1.6 领域模型与基础设施模型一致性问题

| 模型 | email | 密码字段 | 锁定机制 |
|------|-------|---------|---------|
| User (domain) | ❌ 无 | `password_hash` (必填) | `is_locked`, `failed_login_attempts`, `locked_until` |
| UserModel (infrastructure) | ✅ 有 | `hashed_password` (可空) | `is_locked`（缺 `failed_login_attempts`/`locked_until`） |

**需决策**：方案A添加email到User实体（需评估领域层零依赖），方案B移除UserModel的email

### 1.7 重构价值评估（Round 4 新增）

**评估结论：L2RdbPort 基类重构有价值**

| 维度 | 分析 |
|------|------|
| 一致性约束 | 统一的L2RdbPort定义标准CRUD契约，确保所有端口一致 |
| 完整性 | UserRepositoryPort现在缺少save/delete/list_all，继承L2RdbPort后必须补充完整 |
| 可扩展性 | 新增端口只需继承基类，符合开闭原则，为未来复用扩展提供良好基础 |
| 开销 | 5人天 |

**推荐方案**：继续推动L2RdbPort重构，实现架构一致性约束

### 1.8 端口-实现完整映射（Round 4 新增）

| 端口 | 定义 | 实现 | 状态 |
|------|------|------|------|
| L0StoragePort → FileMemoryAdapter | ✅ | ✅ |
| L1CachePort → RedisMemoryCache | ✅ | ✅ |
| L2MetadataRepositoryPort → PostgreSQLMemoryMetadataRepository | ✅ | ✅ |
| L2ChangeHistoryRepositoryPort → PostgreSQLMemoryChangeHistoryRepository | ✅ | ✅ |
| L2GroupMemberRepositoryPort → PostgreSQLMemoryGroupMemberRepository | ✅ | ✅ |
| UnitOfWork → PostgreSQLUnitOfWork | ✅ | ✅ |
| UserRepositoryPort → ⚠️ UserRepository (未声明实现) | ✅ | ⚠️ |

**需决策**：
- 方案A：在 User 实体中添加 `email` 字段，使领域模型与基础设施模型一致
- 方案B：移除 UserModel 的 `email` 字段，保持领域模型的纯净性

**推荐方案A**（保持与现有系统兼容，但需评估是否违反领域层零依赖原则）

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
- 业务事务边界由 **应用层/UseCase** 通过 `PostgreSQLUnitOfWork` 控制
- `L2RdbPort` 不包含事务方法，避免污染领域接口契约
- Repository 只做数据访问，不感知事务边界

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
│    - L2MetadataRepositoryPort(L2RdbPort, ...)     (记忆系统)       │
│    - L2ChangeHistoryRepositoryPort(L2RdbPort, ...)                │
│    - L2GroupMemberRepositoryPort(L2RdbPort, ...)                 │
│    - UserRepositoryPort(L2RdbPort, ...)          (用户系统)       │
│    - RoleRepositoryPort(L2RdbPort, ...)           (角色系统)      │
│    - AuditRepositoryPort(L2RdbPort, ...)           (审计系统)     │
│    - LoginAttemptRepositoryPort(L2RdbPort, ...)   (登录系统)      │
│    - UserRoleRepositoryPort(L2RdbPort, ...)        (用户角色系统) │
└─────────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: Infrastructure - PostgreSQL 事务管理 + 连接管理        │
│                                                                  │
│  职责：数据库连接池管理 + 事务边界控制（由应用层编排）            │
│  位置：src/infrastructure/                                       │
│  组件：                                                          │
│    - storage/postgresql/engine.py                                │
│    │     DatabaseEngine (数据库引擎单例)                          │
│    │     └── 职责：连接池初始化 / 健康检查 / 优雅关闭             │
│    - messaging/unit_of_work/postgresql_unit_of_work.py           │
│    │     PostgreSQLUnitOfWork (实现 UnitOfWork Protocol)          │
│    │     └── 职责：事务边界(begin/commit/rollback) / session提供  │
│  特点：事务边界由应用层控制，Repository 不感知事务               │
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
│  特点：通过 DatabaseEngine 获取会话，委托 BaseRepository       │
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

# Layer 2: Domain 具体应用端口
class UserRepositoryPort(L2RdbPort, Protocol):
    """用户仓储接口 - 继承 L2RdbPort"""
    async def get_by_username(self, username: str) -> User | None: ...

class RoleRepositoryPort(L2RdbPort, Protocol):
    """角色仓储接口 - 继承 L2RdbPort"""
    pass

# Layer 3: Infrastructure 事务管理（应用层控制）
class PostgreSQLUnitOfWork(UnitOfWork):
    """PostgreSQL 工作单元实现"""
    def __init__(self, session: AsyncSession):
        self._session = session

    @property
    def session(self) -> AsyncSession: ...
    async def begin(self) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...

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
| **Layer 3** | `RedisL1CacheAdapter` (Redis 实现) | `PostgreSQLUnitOfWork` (事务管理) |
| | `DatabaseEngine` (连接管理) | `DatabaseEngine` (连接管理) |
| **Layer 4** | `RedisSemanticCacheAdapter` | `PostgreSQLUserRepository` |

**注**：PostgreSqlRdbAdapter 是文档定义的重构目标，当前系统使用 PostgreSQLUnitOfWork 管理事务。

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
│  src/infrastructure/
│  ├── messaging/unit_of_work/
│  │   └── postgresql_unit_of_work.py  # PostgreSQLUnitOfWork ✅ 已实现
│  └── storage/postgresql/repository/  # Repository 实现
│      ├── base_repository.py  # BaseRepository
│      ├── memory_metadata_repository.py
│      ├── user_repository.py
│      └── role_repository.py
└─────────────────────────────────────────────────────────────┘
```

### 3.2 验收标准

| 标准 | 描述 | 测量方式 |
|------|------|---------|
| R1 | 所有 RDB 端口定义 L2RdbPort 基类（重构目标） | 代码审查 |
| R2 | 事务由 PostgreSQLUnitOfWork 管理（DatabaseEngine 提供会话） | 实现验证 |
| R3 | 现有功能保持不变 | 回归测试通过率 100% |
| R4 | 数据库会话通过 DatabaseEngine 获取，事务由 PostgreSQLUnitOfWork 管理 | 代码审查 |
| R5 | 可扩展支持其他 RDB 实现（如 MySQL） | 架构验证 |
| R6 | 事务边界在应用层/UseCase 层 | 代码审查 |

---

## 4. 详细设计

### 4.1 L2RdbPort 基类设计

```python
# src/domain/ports/l2_rdb.py

from __future__ import annotations

from typing import Any, Generic, TypeVar, Protocol
from uuid import UUID

T = TypeVar("T")


class L2RdbPort(Protocol):
    """统一 RDB 存储抽象基类。

    定义所有 RDB 仓储的通用接口契约。
    所有具体应用端口应继承此基类。

    设计原则：
    - 领域层零外部依赖（仅用 Protocol + typing）
    - 通用 CRUD 操作统一定义
    - 事务由 PostgreSQLUnitOfWork 在应用层管理，不在此接口暴露
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

    所有具体应用端口应继承此基类，获得通用 CRUD 契约。
    """

    async def get_by_id(self, id: UUID) -> T | None: ...
    async def save(self, entity: T) -> T: ...
    async def delete(self, id: UUID) -> bool: ...
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[T]: ...


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
    完整定义标准 CRUD + 专用查询方法。
    """

    # === 标准 CRUD（继承自 L2RdbPort）===
    async def get_by_id(self, user_id: UUID) -> User | None: ...
    async def save(self, user: User) -> User: ...
    async def delete(self, user_id: UUID) -> bool: ...
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[User]: ...

    # === 专用查询 ===
    async def get_by_username(self, username: str) -> User | None: ...
```

**注意**：`get_by_email` 方法已移除，因为 User 实体不包含 email 字段。

**说明**：`UserRepositoryPort` 需完整实现 `L2RdbPort` 定义的 CRUD 接口，与 `RoleRepositoryPort` 保持一致性。

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

#### 4.3.1 PostgreSQLUnitOfWork（已实现）

```python
# src/infrastructure/messaging/unit_of_work/postgresql_unit_of_work.py

"""PostgreSQLUnitOfWork - PostgreSQL 工作单元实现。

职责：
- 事务控制（begin/commit/rollback）
- 提供 session 属性供 Repository 使用
"""

from sqlalchemy.ext.asyncio import AsyncSession


class PostgreSQLUnitOfWork(UnitOfWork):
    """PostgreSQL 工作单元实现。"""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._committed = False
        self._rolled_back = False

    @property
    def session(self) -> AsyncSession: ...

    async def begin(self) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
    async def begin_nested(self) -> None: ...
```

**说明**：
- 实现 `UnitOfWork` Protocol（`src/domain/ports/unit_of_work.py`）
- 事务边界由应用层控制，幂等性防护防止重复操作
- **PostgreSqlRdbAdapter（可选重构目标）**：在代码库中不存在，与 PostgreSQLUnitOfWork 职责重叠，当前不计划实施

#### 4.3.2 base_repository.py（更新）

```python
# src/infrastructure/storage/postgresql/repository/base_repository.py

"""BaseRepository — 通用仓储基类。

所有具体仓储类继承此基类，复用 CRUD 操作。

设计原则：
- 泛型类型参数 T 为 SQLAlchemy 模型
- 会话通过构造器注入，不依赖 PostgreSqlRdbAdapter
- 具体 Repository 在构造时注入 session，实现数据访问
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
            session: 异步数据库会话（由调用方注入，通常来自 UseCase 层）
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
    - UserRepositoryPort (领域层接口) → 定义 CRUD + 专用查询契约
    - BaseRepository (通用 CRUD) → 提供 CRUD 实现复用
    """

    def __init__(self, session: AsyncSession):
        """初始化 PostgreSQLUserRepository。

        Args:
            session: 异步数据库会话（由 UseCase 层通过 PostgreSqlRdbAdapter 获取并注入）
        """
        BaseRepository.__init__(self, UserModel, session)

    # === 实现 L2RdbPort 定义的 CRUD ===

    async def get_by_id(self, user_id: UUID) -> User | None:
        """根据 ID 获取用户。"""
        result = await self._session.execute(select(UserModel).where(UserModel.id == user_id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, user: User) -> User:
        """保存用户（创建或更新）。"""
        model = self._to_model(user)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, user_id: UUID) -> bool:
        """删除用户。"""
        model = await self._session.get(UserModel, user_id)
        if model:
            await self._session.delete(model)
            await self._session.flush()
            return True
        return False

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        """获取所有用户。"""
        result = await self._session.execute(select(UserModel).offset(skip).limit(limit))
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    # === 实现 UserRepositoryPort 专用查询 ===

    def _to_entity(self, model: UserModel) -> User:
        """模型转领域实体。"""
        return User(
            id=model.id,
            username=model.username,
            password_hash=model.hashed_password or "",
            is_active=model.is_active,
            is_locked=model.is_locked,
            failed_login_attempts=0,
            locked_until=None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: User) -> UserModel:
        """领域实体转模型。"""
        return UserModel(
            id=entity.id,
            username=entity.username,
            hashed_password=entity.password_hash,
            is_active=entity.is_active,
            is_locked=entity.is_locked,
        )

    async def get_by_username(self, username: str) -> User | None:
        """根据用户名获取用户。"""
        result = await self._session.execute(select(UserModel).where(UserModel.username == username))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
```

**说明**：由于 User 实体无 email 字段，模型转换时 email 字段被忽略。password_hash 与 hashed_password 字段名不一致也已在转换中处理。

**说明**：
- `PostgreSQLUserRepository` 同时继承 `UserRepositoryPort` 和 `BaseRepository`
- `BaseRepository` 提供 CRUD 实现骨架，`UserRepositoryPort` 提供接口契约
- `save`/`get_by_id`/`delete`/`list_all` 覆盖 `BaseRepository` 的默认实现以返回领域实体类型
- 会话由 UseCase 层获取并通过构造器注入，不直接依赖 `PostgreSqlRdbAdapter`

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

src/infrastructure/
├── messaging/unit_of_work/
│   └── postgresql_unit_of_work.py  # PostgreSQLUnitOfWork ✅ 已实现
├── storage/postgresql/
├── engine.py                # 保持不变 ✅
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
| Phase 4 | 验证 PostgreSQLUnitOfWork 已实现 | 低 | 0.25d | Phase 2 |
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

#### Phase 4: 验证 PostgreSQLUnitOfWork 已实现

**注**：PostgreSqlRdbAdapter 文档定义为重构目标，但实际系统使用 PostgreSQLUnitOfWork 管理事务。

- [x] 确认 `src/infrastructure/messaging/unit_of_work/postgresql_unit_of_work.py` 已存在
- [x] 验证 `PostgreSQLUnitOfWork` 实现 `UnitOfWork` 接口
- [x] 验证 `begin()`/`commit()`/`rollback()` 事务方法实现
- [x] 验证 UnitOfWork 提供 `session` 属性给 Repository 使用
- [ ] （可选）如需统一存储适配器接口，创建 `PostgreSqlRdbAdapter` 包装现有 UnitOfWork

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
| `PostgreSqlRdbAdapter` | ❌ 不存在（可选重构目标） | - | - | 不计划实施 |
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
# MySQL UnitOfWork 示例（未来扩展）

class MySqlUnitOfWork(UnitOfWork):
    """MySQL 工作单元实现。"""

    def __init__(self, session):
        self._session = session

    async def begin(self) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
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
| PostgreSqlRdbAdapter | 可选重构目标，在代码库中不存在，当前不计划实施 |
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
| 1.3.0 | 2026-05-13 | - | 审查修正：明确 execute_in_transaction 归属、补充 UserRepositoryPort CRUD、澄清会话管理机制 |
| 1.4.0 | 2026-05-13 | - | 第2轮审查：修正 UnitOfWork、移除 get_by_email、修正 UserModel/Entity 不一致、更新基础设施层状态 |
