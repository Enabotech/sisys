# Story 3.10: 战略档案库长期存储与归档

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 知识管理专家,
**I want** 系统能够永久存储历年 SP/BP 的关键假设变量、决策依据、实际执行偏差,
**So that** 形成企业长期记忆和知识积累，支持战略决策追溯与历史分析。

### 永久存储语义定义

本 Story 的"长期存储与归档"定义如下：
- **L2 元数据（PostgreSQL）**：物理保留，支持软删除（`deleted_at` 标记），物理数据不删除。
- **L4 证据包（MinIO WORM）**：WORM COMPLIANCE 模式写入，retention 7 年（可延长），不可物理删除或修改。
- **L3/L5 辅助数据**：与元数据同生命周期，可降级重建。
- 档案创建后**不可修改**（不可变记录），但元数据可扩展（通过 `metadata` 扩展字段为后续 Story 预留）。
- `delete()` 方法仅执行软删除（标记 `deleted_at`），不物理删除任何数据。

### 业务价值

本 Story 是 Epic 3（智能检索与知识发现）的**战略档案库基础 Story**，也是 **FR-SA-01（P0）** 的完整实现。它建立企业战略档案库的基础设施，为后续 Story 3.11（事实有效期标签管理）、Story 3.12（数据陈旧标记）提供基础。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **StrategicArchive 实体** | 统一抽象战略档案的元数据+引用结构 | 实体定义完整，携带六层存储引用 |
| **L2 元数据持久化** | 档案元数据永久存储在 PostgreSQL | 元数据 CRUD 准确 100% |
| **L3 向量存储协同** | 档案内容嵌入向量，支持语义检索 | 向量存储协同正确 |
| **L4 对象存储协同** | 原始证据包/快照 WORM 归档 | 对象存储协同正确，WORM 7 年 |
| **L5 图存储协同** | 档案实体间关系图谱构建 | 图谱关系存储正确 |
| **归档事件** | 档案创建事件，驱动下游同步 | 事件发布与消费正常 |
| **异常体系** | 档案专属异常，与项目异常体系集成 | 编码唯一性验证 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 3: 智能检索与知识发现，Story 3.10

**前置依赖:**
- Story 1.5（PostgreSQL ✅ 已实现）— 提供 L2 关系存储用于档案元数据持久化
- Story 1.7（MinIO ✅ 已实现）— 提供 L4 对象存储用于证据包/快照 WORM 归档
- Story 1.6（Qdrant ✅ 已实现）— 提供 L3 向量存储用于档案语义检索
- Story 1.8（Neo4j ✅ 已实现）— 提供 L5 图存储用于档案关系图谱
- Story 1.2/1.3（领域事件 + 事件总线 ✅ 已实现）— 提供事件发布能力
- Story 3.4（RRF 融合排序 ✅ 已实现）— 提供三路检索融合能力
- Story 3.2b（实体抽取 ✅ 已实现）— 实体抽取能力可用于档案内容提取

**后续依赖:** Story 3.11（事实有效期标签管理）、Story 3.12（数据陈旧标记）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 战略档案实体定义

**Given** 系统需要统一的战略档案抽象
**When** 定义 `StrategicArchive` 实体
**Then** 包含档案元数据、六层存储引用（L2+L3+L4+L5）
**And** 提供 `validate()` 和归档业务方法
**And** 领域层零外部依赖（仅 Python 标准库 + dataclasses）

**验证标准/Validation Criteria:**
- [ ] `StrategicArchive` dataclass 定义于 `src/domain/entities/strategic_archive.py`
- [ ] 关键字段：`archive_id: UUID`、`plan_id: UUID | None`（关联 SP/BP）、`plan_type: str`（"SP"/"BP"）、`archive_type: ArchiveType`（ASSUMPTION/DECISION/DEVIATION/EVIDENCE_PACKAGE）、`created_by: UUID`（创建者用户 ID，用于审计追踪）、`version: int`（版本号，乐观锁并发控制）
- [ ] 元数据字段：`assumptions: dict[str, Any]`（关键假设变量）、`decision_basis: dict[str, Any]`（决策依据）、`execution_deviation: dict[str, Any]`（实际执行偏差）
- [ ] 存储引用字段：`metadata_ref: str`（L2 元数据引用）、`embedding_ref: str | None`（L3 向量引用）、`blob_ref: str | None`（L4 对象存储引用）、`graph_ref: str | None`（L5 图存储引用）
- [ ] 时间字段：`created_at: datetime`、`archived_at: datetime`、`deleted_at: datetime | None`（软删除标记）
- [ ] 扩展字段：`metadata: dict[str, Any]`（扩展元数据，为后续 Story 3.11/3.12 预留扩展点）
- [ ] `ArchiveType` 枚举（str, Enum）：`ASSUMPTION = "assumption"`、`DECISION = "decision"`、`DEVIATION = "deviation"`、`EVIDENCE_PACKAGE = "evidence_package"`
- [ ] `validate()` 方法 — 验证 archive_id 为有效 UUID、archive_type 有效、created_at ≤ archived_at
- [ ] 注册于 `src/domain/entities/__init__.py` 和 `__all__`

### AC-2: 档案仓储端口契约

**Given** 需要统一的战略档案仓储抽象
**When** 定义 `ArchiveRepositoryPort` 协议
**Then** 包含档案 CRUD、按规划/类型查询、时间范围查询等核心方法
**And** 携带 `ArchiveQuery` 值对象用于多字段组合查询
**And** 领域层零外部依赖（仅 Python 标准库 + Protocol）

**验证标准/Validation Criteria:**
- [ ] `ArchiveRepositoryPort` Protocol 定义于 `src/domain/ports/archive_repository.py`，**继承 `L2RdbPort[StrategicArchive]`**（获得 `get_by_id`/`save`/`delete` 基础 CRUD，与 `L2MetadataRepositoryPort` 模式一致）
- [ ] `ArchiveQuery` frozen dataclass（plan_id, archive_type, plan_type, start_date, end_date, offset, limit）
- [ ] `save(archive: StrategicArchive) -> StrategicArchive` — 保存档案（继承自 `L2RdbPort`）
- [ ] `get_by_id(archive_id: UUID) -> StrategicArchive | None` — 按 ID 查询（继承自 `L2RdbPort`）
- [ ] `find(query: ArchiveQuery) -> list[StrategicArchive]` — 按条件查询
- [ ] `list_by_plan(plan_id: UUID) -> list[StrategicArchive]` — 按规划 ID 列出
- [ ] `list_by_archive_type(archive_type: ArchiveType) -> list[StrategicArchive]` — 按档案类型列出
- [ ] `delete(archive_id: UUID) -> None` — 删除档案（软删除，设置 `deleted_at` 标记，物理数据不删除）
- [ ] `count(query: ArchiveQuery) -> int` — 统计满足条件的档案数量
- [ ] 端口注册于 `composition_root.py`，通过 `register_port()` 注册

### AC-3: 档案异常体系

**Given** 档案管理过程中可能发生多种错误
**When** 定义档案异常类
**Then** 继承 `BusinessException` 层次结构
**And** 分配唯一异常编码（新增 `archive` 子域 280-289）

**验证标准/Validation Criteria:**
- [ ] `ArchiveNotFoundError`（EXCEPTION_280）— 继承 `NotFoundError`，档案不存在
- [ ] `ArchiveConflictError`（EXCEPTION_281）— 继承 `ConflictError`，档案重复/冲突
- [ ] `ArchiveStorageError`（EXCEPTION_282）— 继承 `BusinessException`，存储层协同失败
- [ ] 异常编码在 `_code_ranges.py` 注册 `archive` 子域 (280, 289)，无碰撞
- [ ] 异常在 `__init__.py` 导出，在 `EXCEPTION_HTTP_MAP` 注册（404/409/500）
- [ ] 新增异常文件 `src/domain/exceptions/archive_exceptions.py`

### AC-4: 档案领域事件

**Given** 档案创建完成（含多存储层协同完成）
**When** 发布 `ArchiveCreated` 领域事件
**Then** 事件携带档案元数据（archive_id, plan_id, archive_type, storage_refs）
**And** 继承 `DomainEvent` 基类，遵循事件标准 Schema

**验证标准/Validation Criteria:**
- [ ] `ArchiveCreated` 定义于 `src/domain/events/archive_events.py`
- [ ] 字段：`archive_id: UUID`、`plan_id: UUID | None`、`plan_type: str`、`archive_type: ArchiveType`、`has_embedding: bool`、`has_blob: bool`、`has_graph: bool`
- [ ] `__post_init__` 设置 `aggregate_type = "StrategicArchive"`
- [ ] 事件注册于 `src/domain/events/__init__.py`、`configs/event_channels.yaml`、`ChannelRouter.DEFAULT_MAPPINGS`（RELIABLE 模式）
- [ ] 新增事件文件 `src/domain/events/archive_events.py`

### AC-5: 应用层档案编排服务

**Given** 领域层端口契约已定义
**When** 实现 `StrategicArchiveService`
**Then** 组合 `ArchiveRepositoryPort`（L2 持久化）+ `L3VectorPort`（向量存储）+ `L4ObjectPort`（对象存储）+ `L5GraphPort`（图存储）+ `EventPublisher`
**And** 提供 `archive_plan()` 完整归档流程（多存储层协同）
**And** 提供 `query_archive()` / `get_archive()` 查询方法

**验证标准/Validation Criteria:**
- [ ] `StrategicArchiveService` 位于 `src/application/services/strategic_archive_service.py`
- [ ] 构造函数注入：`archive_repo`（ArchiveRepositoryPort）、`vector_storage`（L3VectorPort）、`object_storage`（L4ObjectPort）、`graph_storage`（L5GraphPort）、`event_publisher`（EventPublisher）
- [ ] `archive_plan(plan_id, plan_type, assumptions, decision_basis, execution_deviation, evidence_blob) -> StrategicArchive`：
  - 创建 StrategicArchive 实体
  - 调用 `archive_repo.save()` 写入 L2 元数据
  - 调用 `vector_storage.upsert_points()` 写入 L3 向量（含嵌入，参数 `collection="strategic_archive"`）
  - 调用 `object_storage.archive()` 写入 L4 对象（WORM 归档，参数 `bucket_type="archive-evidence"`）
  - 调用 `graph_storage.create_entity()` 写入 L5 图谱（参数 `memory_id=str(archive_id)`，`entity_type="StrategicArchive"`）
  - 发布 `ArchiveCreated` 事件
  - 优雅降级：L3/L5 失败不阻塞 L2+L4 主流程
- [ ] `get_archive(archive_id) -> StrategicArchive` — 按 ID 查询（内部调用 `archive_repo.get_by_id()`，若返回 None 则抛出 `ArchiveNotFoundError(archive_id=archive_id)`）
- [ ] `query_archive(query: ArchiveQuery) -> list[StrategicArchive]` — 按条件查询
- [ ] `archive_plan()` 中 L3/L4/L5 存储异常走 `ArchiveStorageError`（禁止 `ValueError`/原始 Exception）

### AC-6: 基础设施层 PostgreSQL 档案仓储

**Given** 需要持久化档案元数据
**When** 实现 `PostgreSQLArchiveRepository`
**Then** 遵循 `PostgreSQLAdapter` 基类模式（继承 L2 仓储最佳实践）
**And** 档案元数据存单表，包含所有存储引用字段

**验证标准/Validation Criteria:**
- [ ] 仓储实现 `ArchiveRepositoryPort` 位于 `src/infrastructure/storage/postgresql/repository/archive_repository.py`
- [ ] 继承 `PostgreSQLAdapter[StrategicArchive, ArchiveModel]` 泛型基类，复用 `get_by_id`/`save`/`delete` 基础 CRUD
  - 软删除配置：`soft_delete_column = "deleted_at"`（基类自动路由软删除/硬删除）
- [ ] **额外实现** `ArchiveRepositoryPort` 的 `find()`、`list_by_plan()`、`list_by_archive_type()`、`count(query)` 方法（`PostgreSQLAdapter` 基类不提供这些方法）
- [ ] Alembic migration 新增 `strategic_archives` 表（只新增不修改已合入 migration）
- [ ] 表字段：`archive_id`（UUID PK）、`plan_id`（UUID nullable）、`plan_type`、`archive_type`、`created_by`（UUID）、`version`（int）、`metadata`（JSONB）、`deleted_at`（nullable）、`assumptions`（JSONB）、`decision_basis`（JSONB）、`execution_deviation`（JSONB）、`metadata_ref`、`embedding_ref`（nullable）、`blob_ref`（nullable）、`graph_ref`（nullable）、`created_at`、`archived_at`
- [ ] 查询支持 `ArchiveQuery` 多条件组合 + 分页

### AC-7: 多存储层协同集成

**Given** 档案归档时需多存储层协同
**When** 执行 `archive_plan()` 归档流程
**Then** L2（元数据）+ L3（向量）+ L4（对象）+ L5（图谱）按序写入
**And** 部分失败时主流程不受阻（L3/L5 优雅降级，L2+L4 强制成功）

**验证标准/Validation Criteria:**
- [ ] L2 写入：`archive_repo.save()` 同步写入 metadata
- [ ] L3 写入：`vector_storage.upsert_points()` 写入档案内容嵌入向量（collection: `strategic_archive`）
- [ ] L4 写入：`object_storage.archive()` 归档证据包（bucket: `archive-evidence`，retention 7 年）
- [ ] L5 写入：`graph_storage.create_entity()` 创建档案节点（entity_type: `StrategicArchive`）
- [ ] 优雅降级：L3 失败 → 记录日志，`embedding_ref = None`（`embedding_ref` 由应用层在调用前生成，如 `f"strategic_archive:{archive_id}"`，而非从 `upsert_points()` 返回值获取）；L5 失败 → 记录日志，`graph_ref = None`
- [ ] L2 或 L4 失败 → 抛出 `ArchiveStorageError`，归档流程回滚
- [ ] 归档延迟 P95<500ms
- [ ] 存储完整性 100%（L2+L4 强制成功保障）

### AC-8: 接口层 REST API

**Given** 用户需要通过 API 查询和管理档案
**When** 实现档案管理 REST 路由
**Then** 提供档案查询、详情、归档触发接口
**And** 所有接口过认证中间件，遵循统一错误响应

**验证标准/Validation Criteria:**
- [ ] 路由工厂函数 `create_archive_router()`，前缀 `/api/v1/archive`
- [ ] `GET /api/v1/archive/entries` — 档案列表（分页 + 过滤：plan_id, archive_type, plan_type, date_range）
- [ ] `GET /api/v1/archive/entries/{archive_id}` — 档案详情
- [ ] `POST /api/v1/archive/archive` — 手动触发归档
- [ ] `GET /api/v1/archive/plans/{plan_id}` — 按规划 ID 查询档案
- [ ] 请求/响应 Schema 使用 Pydantic，定义于路由同文件
- [ ] 支持 `get_current_user_override` 测试覆盖依赖注入模式
- [ ] 查询延迟 P95<200ms

### AC-9: 端口注册与 DI 集成

**Given** 所有组件实现完成
**When** 在 `composition_root.py` 注册
**Then** `archive_repository`、`strategic_archive_service` 端口注册为 SCOPED
**And** 通过 `Resolver` 可正确解析
**And** 端口契约测试通过

**验证标准/Validation Criteria:**
- [ ] `composition_root.py` 注册 `archive_repository` 端口（PostgreSQLArchiveRepository 实现 ArchiveRepositoryPort）
- [ ] `composition_root.py` 注册 `strategic_archive_service` 端口（StrategicArchiveService 编排服务）
- [ ] 端口契约测试 `tests/contracts/test_port_contract_strategic_archive.py` 通过
- [ ] `src/domain/ports/__init__.py` 导出 `ArchiveRepositoryPort`、`ArchiveQuery` 及值对象
- [ ] `src/domain/entities/__init__.py` 导出 `StrategicArchive`、`ArchiveType`

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

**新建事件：**
- [ ] `ArchiveCreated`（`src/domain/events/archive_events.py`）
  - 继承 `DomainEvent`（`@dataclass(frozen=True)`）
  - 字段: `archive_id: UUID` — 档案标识
  - `plan_id: UUID | None` — 关联的 SP/BP 规划标识
  - `plan_type: str` — 规划类型（"SP" / "BP"）
  - `archive_type: ArchiveType` — 档案类型
  - `has_embedding: bool = False` — 是否有 L3 向量
  - `has_blob: bool = False` — 是否有 L4 对象
  - `has_graph: bool = False` — 是否有 L5 图谱
  - 事件类型: `"ArchiveCreated"`（`field(default="ArchiveCreated", init=False)`）
  - `__post_init__` 设置 `aggregate_type = "StrategicArchive"`
  - Schema 版本: v1.0.0
  - 通道: `RabbitMQ + Outbox`（业务状态型，RELIABLE 模式）
  - 注册于 `src/domain/events/__init__.py`、`configs/event_channels.yaml`、`ChannelRouter.DEFAULT_MAPPINGS`

#### 数据模型 (Data Models)

**新建实体：**
- [ ] `StrategicArchive`（`src/domain/entities/strategic_archive.py`）
  - `@dataclass`（非 frozen，允许归档后状态变更）
  - `ArchiveType` 枚举（str, Enum）：`ASSUMPTION` / `DECISION` / `DEVIATION` / `EVIDENCE_PACKAGE`
  - 字段见 AC-1 定义
  - `validate()` 方法验证不变量，抛出 `EntityValidationError` / `EntityBusinessRuleError`
  - 注册于 `src/domain/entities/__init__.py` 和 `__all__`

**新建值对象：**
- [ ] `ArchiveQuery`（`src/domain/ports/archive_repository.py`）
  - `@dataclass(frozen=True)`
  - 字段: `plan_id: UUID | None = None`、`archive_type: ArchiveType | None = None`、`plan_type: str | None = None`、`start_date: datetime | None = None`、`end_date: datetime | None = None`、`offset: int = 0`、`limit: int = 20`
  - `limit` 取值范围：1-1000，默认 20。仓储层做边界检查：`limit = max(1, min(limit, 1000))`

**新建 SQLAlchemy 模型：**
- [ ] `ArchiveModel`（`src/infrastructure/storage/postgresql/models/archive.py`）
  - 继承 `Base`，表名 `strategic_archives`
  - 字段见 AC-6 定义
  - 注册于 `src/infrastructure/storage/postgresql/models/__init__.py` 和 `__all__`

#### 统一端口定义注册与管理 (Port Contract)

**新建端口：**
- [ ] `ArchiveRepositoryPort`（`src/domain/ports/archive_repository.py`）
  - `@runtime_checkable` Protocol，**继承 `L2RdbPort[StrategicArchive]`**（获得 `get_by_id`/`save`/`delete` 基础 CRUD）
  - 方法：`save()`、`get_by_id()`、`find()`、`list_by_plan()`、`list_by_archive_type()`、`delete()`、`count(query)`
  - 携带 `ArchiveQuery` frozen dataclass
  - 注册于 `src/domain/ports/__init__.py` 和 `__all__`

**端口契约清单执行约束（强制）：**
- [ ] 端口清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

**新建异常：**
- [ ] `ArchiveNotFoundError`（EXCEPTION_280）— `src/domain/exceptions/archive_exceptions.py`，继承 `NotFoundError`
  - 构造参数：`archive_id: UUID`，`message: str = "Archive not found"`
  - `context` 暴露 `archive_id`
- [ ] `ArchiveConflictError`（EXCEPTION_281）— 继承 `ConflictError`
  - 构造参数：`archive_id: UUID`，`message: str = "Archive conflict"`
- [ ] `ArchiveStorageError`（EXCEPTION_282）— 继承 `BusinessException`
  - 构造参数：`message: str = "Archive storage error"`，`layer: str`（指示失败存储层：l2/l3/l4/l5），`cause: Exception | None`
- [ ] 编码分配：`archive` 子域 (280, 289)，已在 `_code_ranges.py` 预留 `# 档案子域（280-289）`
- [ ] 异常在 `_code_ranges.py` 的 `_CLASS_TO_SUBDOMAIN` 注册
- [ ] 异常在 `__init__.py` 导出，在 `EXCEPTION_HTTP_MAP` 注册（404/409/500）
- [ ] 测试覆盖：构造/`to_dict()`/HTTP 映射/编码唯一性 + 子域范围测试

#### API 契约 (API Contract)

- [ ] 路由工厂函数 `create_archive_router()`，前缀 `/api/v1/archive`
- [ ] 端点见 AC-8 定义
- [ ] 所有路由过认证中间件
- [ ] 响应遵循统一错误格式（`error.code` + `error.message` + `request_id`）
- [ ] API 契约测试通过（`tests/contracts/test_api_contract_strategic_archive.py`）

#### 六边形架构约束（必须遵守）

> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖 |
| application | `src/application/` | 用例编排 |
| interfaces | `src/interfaces/` | 适配器 |
| infrastructure | `src/infrastructure/` | 技术实现 |

**领域层零依赖原则**
- 领域层（`src/domain/`）仅使用 Python 标准库
- 禁止导入：包括且不限于 langgraph, prefect, fastapi, pydantic, sqlalchemy, typer, redis, qdrant, minio, neo4j, aio_pika, litellm, instructor, requests, httpx, docker, psycopg2

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | interfaces | infrastructure |
|------------|--------|-------------|------------|----------------|
| **domain** | — | ✗ 禁止 | ✗ 禁止 | ✗ 禁止 |
| **application** | ✓ 允许 | — | ✗ 禁止 | ✗ 禁止 |
| **interfaces** | ✓ 允许 | ✓ 允许 | — | ✗ 禁止 |
| **infrastructure** | ✓ 允许 | ✓ 允许 | ✗ 禁止 | — |

#### 验收标准 Gherkin (Acceptance Tests)

**BDD 场景文件：**
- `tests/acceptance/test_acceptance_strategic_archive.feature`
- `tests/acceptance/test_acceptance_strategic_archive.py`

**必须覆盖的场景：**
- Happy Path: 归档完整流程（L2+L3+L4+L5 协同成功）
- 归档查询: 按 archive_type / plan_id / 时间范围过滤
- 档案详情: 按 archive_id 查询
- 按规划查询: `list_by_plan()`
- Edge Cases: 档案不存在（404）、存储层协同部分失败（L3 降级不影响主流程）
- 异常路径: 资源不存在（404）、权限不足（403）、资源冲突（409）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- Edge Cases 必须包含异常路径

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [ ] 规范文档通过人工评审或自动化校验

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试（违反 TDD 测试先行原则）
- ❌ 将测试编写集中到最后一个 Task（违反 TDD 小步快跑原则）
- ❌ 跳过红阶段验证（未确认测试失败就直接写实现）

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | StrategicArchive 实体 | 实体创建/validate()/字段赋值 | `test_archive_entity.py` | Task 1 |
| **TDD 单元测试** | ArchiveRepositoryPort | 协议方法签名/Query 值对象 | `test_archive_repository_port.py` | Task 0 |
| **TDD 单元测试** | 档案异常 | 构造/属性/to_dict()/HTTP 映射 | `test_archive_exceptions.py` | Task 2 |
| **TDD 单元测试** | ArchiveCreated 事件 | 事件构造/序列化/反序列化 | `test_archive_events.py` | Task 2 |
| **TDD 单元测试** | StrategicArchiveService | 归档编排/优雅降级/查询 | `test_strategic_archive_service.py` | Task 3 |
| **TDD 单元测试** | PostgreSQLArchiveRepository | CRUD/查询/转换 | `test_archive_repository.py` | Task 4 |
| **TDD 单元测试** | 接口层 API 路由 | GET/POST 路由/请求响应 | `test_archive_routes.py` | Task 5 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_strategic_archive.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_strategic_archive.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单确认 | `test_acceptance_strategic_archive.feature` | Task 6 |
| **TDD 契约测试** | 端口契约 | 端口注册/版本/兼容性/解析 | `test_port_contract_strategic_archive.py` | Task 0 |
| **TDD 契约测试** | API 契约 | 请求/响应结构/状态码 | `test_api_contract_strategic_archive.py` | Task 0 |
| **TDD 单元测试** | 编码唯一性 | 异常 code 无碰撞 | `test_error_code_uniqueness.py` | Task 2 |
| **TDD 单元测试** | 编码子域范围 | 子域范围/继承链一致性 | `test_code_ranges.py` | Task 2 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向/零依赖 | `test_arch_strategic_archive.py` | Task 5 |
| **集成测试** | 多存储层协同 | L2+L3+L4+L5 编排 | `test_integration_strategic_archive.py` | Task 3 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）
- [ ] **领域层覆盖率 ≥90%**
- [ ] **应用层覆盖率 ≥85%**
- [ ] **接口层覆盖率 ≥85%**
- [ ] **基础设施层覆盖率 ≥75%**
- [ ] **集成测试覆盖率 ≥70%**

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **事务隔离** | 集成测试使用 transaction rollback | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内完成 Schema 初始化 | 依赖外部迁移，环境不一致 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突或状态污染 |
| **外部服务隔离** | Redis/Neo4j/Qdrant 测试前清理或用 mock | 真实数据被污染 |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **BDD async 配合** | BDD 步骤函数不使用 @pytest.mark.asyncio，用 event_loop.run_until_complete() 运行 async | 直接用 @pytest.mark.asyncio 会导致 BDD context 数据丢失 |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源（如 `test_*`）
- ❌ Fixture 假设清理顺序（必须显式声明依赖）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 战略档案实体定义 | Task 0 | SDD 规范定义 | `test_archive_entity.py` |
| AC-1 | 战略档案实体定义 | Task 1 | TDD 实体实现 | `test_archive_entity.py` |
| AC-2 | 档案仓储端口契约 | Task 0 | SDD 规范定义（端口契约） | `test_archive_repository_port.py` |
| AC-2 | 档案仓储端口契约 | Task 4 | TDD 仓储实现 | `test_archive_repository.py` |
| AC-3 | 档案异常体系 | Task 0 | SDD 规范定义（异常契约） | `test_archive_exceptions.py` |
| AC-3 | 档案异常体系 | Task 2 | TDD 异常实现 | `test_archive_exceptions.py` |
| AC-4 | 档案领域事件 | Task 0 | SDD 规范定义（事件 Schema） | `test_archive_events.py` |
| AC-4 | 档案领域事件 | Task 2 | TDD 事件实现 | `test_archive_events.py` |
| AC-5 | 应用层档案编排服务 | Task 0 | SDD 规范定义 | `test_strategic_archive_service.py` |
| AC-5 | 应用层档案编排服务 | Task 3 | TDD 服务实现 | `test_strategic_archive_service.py` |
| AC-6 | 基础设施层 PostgreSQL 仓储 | Task 0 | SDD 规范定义（数据模型） | `test_archive_repository.py` |
| AC-6 | 基础设施层 PostgreSQL 仓储 | Task 4 | TDD 仓储实现 + Alembic | `test_archive_repository.py` |
| AC-7 | 多存储层协同集成 | Task 0 | SDD 规范定义 | `test_integration_strategic_archive.py` |
| AC-7 | 多存储层协同集成 | Task 3 | TDD 集成测试 | `test_integration_strategic_archive.py` |
| AC-8 | 接口层 REST API | Task 0 | SDD 规范定义（API 契约） | `test_api_contract_strategic_archive.py` |
| AC-8 | 接口层 REST API | Task 5 | TDD API 路由实现 | `test_archive_routes.py` |
| AC-9 | 端口注册与 DI 集成 | Task 0 | SDD 规范定义 | `test_port_contract_strategic_archive.py` |
| AC-9 | 端口注册与 DI 集成 | Task 5 | composition_root 注册 | `test_port_contract_strategic_archive.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 定义 `StrategicArchive` 实体 Schema（`src/domain/entities/strategic_archive.py`）
- [ ] Subtask 0.2: 定义 `ArchiveType` 枚举（`src/domain/entities/strategic_archive.py`）
- [ ] Subtask 0.3: 定义 `ArchiveQuery` 值对象（`src/domain/ports/archive_repository.py`）
- [ ] Subtask 0.4: 定义 `ArchiveRepositoryPort` 协议（`src/domain/ports/archive_repository.py`）
- [ ] Subtask 0.5: 定义 `ArchiveNotFoundError` / `ArchiveConflictError` / `ArchiveStorageError` 异常契约（`src/domain/exceptions/archive_exceptions.py`）
- [ ] Subtask 0.6: 定义 `ArchiveCreated` 事件 Schema（`src/domain/events/archive_events.py`）
- [ ] Subtask 0.7: 定义 `ArchiveModel` SQLAlchemy 模型（`src/infrastructure/storage/postgresql/models/archive.py`）
- [ ] Subtask 0.8: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_strategic_archive.feature`
- [ ] Subtask 0.9: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_strategic_archive.py`
- [ ] Subtask 0.10: 运行验收测试，确认失败（🔴 红阶段验证）
- [ ] Subtask 0.11: 编写端口契约测试 `tests/contracts/test_port_contract_strategic_archive.py`
- [ ] Subtask 0.12: 编写 API 契约测试 `tests/contracts/test_api_contract_strategic_archive.py`

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）
- [ ] 端口契约测试运行失败（预期行为，红阶段确认）

---

### Task 1: StrategicArchive 实体

**关联 AC:** AC-1

#### TDD 循环 A: StrategicArchive 实体

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/entities/test_archive_entity.py`（实体创建、validate()、字段赋值） |
| 🟢 绿 | 实现 `StrategicArchive` dataclass + `ArchiveType` 枚举 |
| 🔄 重构 | 添加类型注解、docstring、运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 StrategicArchive 实体失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 `StrategicArchive` 实体
- [ ] Subtask 1.3: 🔄 重构 — 优化实体代码

**完成标准/Definition of Done:**
- [ ] `StrategicArchive` 实体实现完成
- [ ] `validate()` 方法验证通过
- [ ] TDD 循环全部通过
- [ ] 注册于 `src/domain/entities/__init__.py`

---

### Task 2: 档案异常 + 领域事件

**关联 AC:** AC-3, AC-4

#### TDD 循环 A: 档案异常

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_archive_exceptions.py`（构造/属性/to_dict()） |
| 🟢 绿 | 实现 `ArchiveNotFoundError` / `ArchiveConflictError` / `ArchiveStorageError` |
| 🔄 重构 | 添加 docstring、注册到 `_code_ranges.py` + `EXCEPTION_HTTP_MAP` |

- [ ] Subtask 2.1: 🔴 红 — 编写档案异常失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现档案异常
- [ ] Subtask 2.3: 🔄 重构 — 注册异常到 `_code_ranges.py`、`EXCEPTION_HTTP_MAP`、`__init__.py`

#### TDD 循环 B: ArchiveCreated 领域事件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/events/test_archive_events.py`（事件构造/序列化/反序列化） |
| 🟢 绿 | 实现 `ArchiveCreated` 事件 |
| 🔄 重构 | 注册到 `__init__.py`、`event_channels.yaml`、`ChannelRouter.DEFAULT_MAPPINGS` |

- [ ] Subtask 2.4: 🔴 红 — 编写 ArchiveCreated 事件失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 `ArchiveCreated` 事件
- [ ] Subtask 2.6: 🔄 重构 — 注册事件通道

**完成标准/Definition of Done:**
- [ ] 所有异常实现完成，编码唯一性验证通过
- [ ] ArchiveCreated 事件实现完成
- [ ] 所有 TDD 循环测试通过

---

### Task 3: StrategicArchiveService 应用服务 + 集成测试

**关联 AC:** AC-5, AC-7

#### TDD 循环 A: StrategicArchiveService 单元测试（Mock 端口）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_strategic_archive_service.py`（归档/查询/降级） |
| 🟢 绿 | 实现 `StrategicArchiveService` 应用服务 |
| 🔄 重构 | 添加类型注解、docstring、优雅降级逻辑 |

- [ ] Subtask 3.1: 🔴 红 — 编写 StrategicArchiveService 失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现 `StrategicArchiveService`
- [ ] Subtask 3.3: 🔄 重构 — 优化服务代码

#### TDD 循环 B: 多存储层协同集成测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_strategic_archive.py`（L2+L3+L4+L5 协同） |
| 🟢 绿 | 实现集成测试场景 |
| 🔄 重构 | 优化测试隔离和断言 |

- [ ] Subtask 3.4: 🔴 红 — 编写集成测试（失败阶段）
- [ ] Subtask 3.5: 🟢 绿 — 实现集成测试场景
- [ ] Subtask 3.6: 🔄 重构 — 优化集成测试

**完成标准/Definition of Done:**
- [ ] StrategicArchiveService 实现完成
- [ ] 归档流程正确（L2+L3+L4+L5 协同）
- [ ] 优雅降级验证通过
- [ ] 覆盖率≥85%

---

### Task 4: PostgreSQLArchiveRepository 基础设施仓储

**关联 AC:** AC-2, AC-6

#### TDD 循环 A: ArchiveModel SQLAlchemy 模型 + Alembic

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写模型测试（表结构/字段/约束） |
| 🟢 绿 | 实现 `ArchiveModel` + Alembic migration |
| 🔄 重构 | 优化模型定义 |

- [ ] Subtask 4.1: 🔴 红 — 编写 ArchiveModel 测试
- [ ] Subtask 4.2: 🟢 绿 — 实现 `ArchiveModel` + Alembic migration
- [ ] Subtask 4.3: 🔄 重构 — 优化模型

#### TDD 循环 B: PostgreSQLArchiveRepository

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/test_archive_repository.py`（CRUD/查询/转换） |
| 🟢 绿 | 实现 `PostgreSQLArchiveRepository` |
| 🔄 重构 | 优化查询性能、添加类型注解 |

- [ ] Subtask 4.4: 🔴 红 — 编写仓储失败测试
- [ ] Subtask 4.5: 🟢 绿 — 实现 `PostgreSQLArchiveRepository`
- [ ] Subtask 4.6: 🔄 重构 — 优化仓储代码

**完成标准/Definition of Done:**
- [ ] `ArchiveModel` + Alembic migration 完成
- [ ] `PostgreSQLArchiveRepository` 实现完成
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥75%

---

### Task 5: API 路由 + 端口注册 + 架构验证

**关联 AC:** AC-8, AC-9

#### TDD 循环 A: API 路由

> **注意：** TDD 循环 A 的 API 路由测试使用 `TestClient` + FastAPI `override_dependencies` 注入 mock `StrategicArchiveService`，不依赖 `composition_root` 注册。TDD 循环 B 端口注册完成后，需回归验证路由测试确保 `Resolver` 注入链路正确。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/api/test_archive_routes.py`（GET/POST 路由） |
| 🟢 绿 | 实现 `create_archive_router()` 路由工厂函数 |
| 🔄 重构 | 添加 Pydantic Schema、错误处理 |

- [ ] Subtask 5.1: 🔴 红 — 编写 API 路由失败测试
- [ ] Subtask 5.2: 🟢 绿 — 实现 API 路由
- [ ] Subtask 5.3: 🔄 重构 — 优化路由代码

#### TDD 循环 B: composition_root 端口注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写端口注册测试（Resolver 解析验证） |
| 🟢 绿 | 在 `composition_root.py` 注册 `archive_repository` + `strategic_archive_service` |
| 🔄 重构 | 验证端口生命周期正确 |

- [ ] Subtask 5.4: 🔴 红 — 编写端口注册失败测试
- [ ] Subtask 5.5: 🟢 绿 — 注册端口到 `composition_root.py`
- [ ] Subtask 5.6: 🔄 重构 — 验证 DI 集成

#### TDD 循环 C: 架构验证测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_arch_strategic_archive.py`（架构约束） |
| 🟢 绿 | 实现架构验证测试 |
| 🔄 重构 | 优化验证逻辑 |

- [ ] Subtask 5.7: 🔴 红 — 编写架构验证失败测试
- [ ] Subtask 5.8: 🟢 绿 — 实现架构验证
- [ ] Subtask 5.9: 🔄 重构 — 优化架构验证

**完成标准/Definition of Done:**
- [ ] API 路由实现完成
- [ ] 端口注册完成，Resolver 可正确解析
- [ ] 架构约束测试通过
- [ ] 覆盖率≥85%

---

### Task 6: 开发结束验收测试

**关联 AC:** AC-1 ~ AC-9

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_strategic_archive.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_strategic_archive.py` 的 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达、保持步骤函数可维护性 |

- [ ] Subtask 6.1: 场景 1 — 验证 `src` 完成清单的逐项确认
- [ ] Subtask 6.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单的逐项确认
- [ ] Subtask 6.3: 运行开发结束验收测试并确认通过
- [ ] Subtask 6.4: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters）、事件驱动、六层存储协同
- **设计约束:**
  - 领域层零外部依赖（仅 Python 标准库 + dataclasses + Protocol）
  - 依赖方向：interfaces → application → domain ← infrastructure
  - 所有端口通过 `composition_root.py` 统一注册
  - 新增异常必须注册到 `_code_ranges.py` 和 `EXCEPTION_HTTP_MAP`
- **接口治理:** 端口契约优先（Protocol + @runtime_checkable）、PortSpec 元数据、Registry/Resolver/ContractGate、Composition Root 装配
- **技术栈:** Python 3.11+、FastAPI 0.111+、SQLAlchemy 2.0+、Alembic、PostgreSQL 15+、Qdrant 1.7+、MinIO（WORM）、Neo4j 5.x

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 决策 4 (ADR-004)

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **六层存储协同（L2+L3+L4+L5）** | 完全对齐现有架构，各层职责清晰 | 协同复杂度高 | ✅ 9/10 |
| 仅 L2+L4 两层存储 | 实现简单 | 缺少语义检索和图谱能力 | 6/10 |
| 仅 L2 单层存储 | 最简单 | 无法满足"向量+对象"协同的架构要求 | 3/10 |

**决策理由：**
1. 架构设计（architecture.md §9）明确 StrategicArchive 使用 L0-L5 六层存储
2. epics_v1.0.md 明确要求"向量存储 + 对象存储协同架构"
3. 现有 L3VectorPort、L4ObjectPort、L5GraphPort 均已实现，可直接复用

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── entities/
│   │   ├── strategic_archive.py          # NEW: 战略档案实体
│   │   └── __init__.py                   # UPDATE: 导出 StrategicArchive
│   ├── ports/
│   │   ├── archive_repository.py         # NEW: 档案仓储端口
│   │   └── __init__.py                   # UPDATE: 导出 ArchiveRepositoryPort
│   ├── events/
│   │   ├── archive_events.py             # NEW: 档案领域事件
│   │   └── __init__.py                   # UPDATE: 导出 ArchiveCreated
│   └── exceptions/
│       ├── archive_exceptions.py         # NEW: 档案异常
│       ├── _code_ranges.py              # UPDATE: 注册 archive 子域
│       └── __init__.py                   # UPDATE: 导出档案异常
│
├── application/
│   └── services/
│       └── strategic_archive_service.py  # NEW: 档案编排服务
│
├── infrastructure/
│   └── storage/
│       └── postgresql/
│           ├── models/
│           │   ├── archive.py            # NEW: ArchiveModel
│           │   └── __init__.py           # UPDATE: 导出 ArchiveModel
│           └── repository/
│               └── archive_repository.py # NEW: PostgreSQLArchiveRepository
│
├── interfaces/
│   └── api/
│       ├── strategic_archive.py          # NEW: 档案路由
│       └── app.py                        # UPDATE: 注册路由
│
└── composition_root.py                   # UPDATE: 注册 archive_repository + strategic_archive_service

deploy/
└── postgresql/
    └── alembic/
        └── versions/
            └── 008_strategic_archives.py  # NEW: 档案表迁移

tests/
├── unit/
│   ├── domain/
│   │   ├── entities/
│   │   │   └── test_archive_entity.py   # NEW: 实体测试
│   │   ├── events/
│   │   │   └── test_archive_events.py   # NEW: 事件测试
│   │   └── exceptions/
│   │       └── test_archive_exceptions.py # NEW: 异常测试
│   ├── application/
│   │   └── services/
│   │       └── test_strategic_archive_service.py # NEW: 服务测试
│   ├── interfaces/
│   │   └── api/
│   │       └── test_archive_routes.py    # NEW: 路由测试
│   └── infrastructure/
│       └── storage/
│           └── test_archive_repository.py # NEW: 仓储测试
├── integration/
│   └── test_integration_strategic_archive.py # NEW: 集成测试
├── contracts/
│   ├── test_port_contract_strategic_archive.py # NEW: 端口契约测试
│   └── test_api_contract_strategic_archive.py  # NEW: API 契约测试
├── acceptance/
│   ├── test_acceptance_strategic_archive.feature # NEW: Gherkin 场景
│   └── test_acceptance_strategic_archive.py      # NEW: BDD 步骤
└── unit/architecture/
    └── test_arch_strategic_archive.py   # NEW: 架构验证测试
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** Story 3.3（领域词典管理）、Story 3.4（RRF 融合排序）

**关键学习/Key Learnings:**
1. **端口契约优先原则** — 必须在 Task 0 完成端口契约定义，包括 Protocol 接口、值对象、Query 对象。`DomainDictionaryPort` 和 `DictionaryConsumerPort` 的分离设计（接口隔离原则 ISP）值得借鉴，StrategicArchive 的 `ArchiveRepositoryPort` 应同样遵循单一职责
2. **异常编码注册** — 新增异常必须在 `_code_ranges.py` 注册子域范围，运行 `grep -r "EXCEPTION_NNN"` 验证无碰撞，并在 `_CLASS_TO_SUBDOMAIN` 注册映射
3. **事件通道配置** — 新事件必须同时更新 `configs/event_channels.yaml` 和 `ChannelRouter.DEFAULT_MAPPINGS`，否则事件不会正确路由。注意 `event_bus_config_loader.py` 的预存 bug（`DEFAULT_CONFIG_PATH` 指向不存在的 `config/` 单数目录）
4. **SINGLETON vs SCOPED 生命周期** — 热更新场景需要 SINGLETON，但 StrategicArchive 的仓储和服务使用 SCOPED（每请求独立实例）
5. **优雅降级** — Story 3.4 的 HybridSearchService 中 `resolver.resolve_optional()` 模式值得借鉴，StrategicArchiveService 的 L3/L5 存储层可使用 `resolve_optional()` 实现优雅降级
6. **Alembic migration 只新增不修改** — 已合入的 migration 禁止修改，只允许新增 migration 文件

**应用到本故事/Applied to This Story:**
- [ ] `ArchiveRepositoryPort` 遵循单一职责，包含 `save()`/`get_by_id()`/`find()`/`list_by_plan()` 等方法
- [ ] `ArchiveQuery` frozen dataclass 用于多字段组合查询
- [ ] 异常编码 280-282 在 `_code_ranges.py` 注册，`grep -r "EXCEPTION_28"` 验证无碰撞
- [ ] `ArchiveCreated` 事件同时更新 `event_channels.yaml` 和 `DEFAULT_MAPPINGS`
- [ ] 仓储和服务的生命周期为 SCOPED
- [ ] L3/L5 存储使用 `resolve_optional()` 实现优雅降级

### 环境变量与配置

**新增事件通道配置（`configs/event_channels.yaml`）：**
```yaml
ArchiveCreated:
  rabbitmq_routing_key: "sisys.events.reliable.archive_created"
  delivery_mode: "reliable"
  description: "战略档案创建完成"
```

**新增 `ChannelRouter.DEFAULT_MAPPINGS` 注册（`src/infrastructure/messaging/channel_router.py`）：**
```python
"ArchiveCreated": ChannelMapping(
    event_type="ArchiveCreated",
    rabbitmq_routing_key="sisys.events.reliable.archive_created",
    delivery_mode=DeliveryMode.RELIABLE,
    description="战略档案创建完成",
),
```

**新增 `EXCEPTION_HTTP_MAP` 注册（`src/interfaces/api/exception_handlers.py`）：**
```python
from src.domain.exceptions.archive_exceptions import ArchiveNotFoundError, ArchiveConflictError, ArchiveStorageError

EXCEPTION_HTTP_MAP.update({
    ArchiveNotFoundError: 404,
    ArchiveConflictError: 409,
    ArchiveStorageError: 500,
})
```

**新增 `register_port()` 注册（`src/composition_root.py`）：**
```python
from src.domain.ports.archive_repository import ArchiveRepositoryPort
from src.infrastructure.storage.postgresql.repository.archive_repository import PostgreSQLArchiveRepository
from src.application.services.strategic_archive_service import StrategicArchiveService

# 注册 archive_repository
register_port(
    name="archive_repository",
    version="v1.0.0",
    interface=ArchiveRepositoryPort,
    impl=lambda resolver: PostgreSQLArchiveRepository(),
    module="src.infrastructure.storage.postgresql.repository.archive_repository",
    lifetime=Lifetime.SCOPED,
    owner="foundation-team",
    tags=("archive", "storage", "gateway"),
)

# 注册 strategic_archive_service（注入 L2-L5 各层存储 + 事件发布）
register_port(
    name="strategic_archive_service",
    version="v1.0.0",
    interface=StrategicArchiveService,
    impl=lambda resolver: StrategicArchiveService(
        archive_repo=resolver.resolve("archive_repository"),
        vector_storage=resolver.resolve_optional("l3_vector", fallback=None),
        object_storage=resolver.resolve("l4_object"),
        graph_storage=resolver.resolve_optional("l5_graph", fallback=None),
        event_publisher=resolver.resolve("event_publisher"),
    ),
    module="src.application.services.strategic_archive_service",
    lifetime=Lifetime.SCOPED,
    owner="foundation-team",
    tags=("archive", "service", "application"),
)
```

### 异常编码分配

| 异常类 | 编码 | 继承 | 描述 |
|--------|------|------|------|
| ArchiveNotFoundError | EXCEPTION_280 | NotFoundError | 档案不存在 |
| ArchiveConflictError | EXCEPTION_281 | ConflictError | 档案重复/冲突 |
| ArchiveStorageError | EXCEPTION_282 | BusinessException | 存储层协同失败 |

**`_code_ranges.py` 注册：**
```python
"archive": (280, 289),
```

**`_CLASS_TO_SUBDOMAIN` 注册：**
```python
"ArchiveNotFoundError": "archive",
"ArchiveConflictError": "archive",
"ArchiveStorageError": "archive",
```

### 存储层设计要点

**L2 PostgreSQL 表设计（`strategic_archives`）：**
```sql
CREATE TABLE strategic_archives (
    archive_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID,                          -- 关联 SP/BP（可为空，支持独立归档）
    plan_type VARCHAR(10),                 -- 'SP' / 'BP'
    archive_type VARCHAR(50) NOT NULL,     -- 'assumption' / 'decision' / 'deviation' / 'evidence_package'
    assumptions JSONB DEFAULT '{}',        -- 关键假设变量
    decision_basis JSONB DEFAULT '{}',     -- 决策依据
    execution_deviation JSONB DEFAULT '{}', -- 实际执行偏差
    metadata_ref VARCHAR(500) NOT NULL,    -- L2 自引用
    embedding_ref VARCHAR(500),            -- L3 Qdrant point ID
    blob_ref VARCHAR(500),                 -- L4 MinIO object key
    graph_ref VARCHAR(500),                -- L5 Neo4j node ID
    created_by UUID,                        -- 创建者用户 ID（审计追踪）
    version INTEGER NOT NULL DEFAULT 1,     -- 版本号（乐观锁）
    metadata JSONB DEFAULT '{}',            -- 扩展元数据（预留 Story 3.11/3.12 扩展点）
    deleted_at TIMESTAMP,                   -- 软删除标记
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**L3 Qdrant collection:**
- collection 名称: `strategic_archive`
- 向量维度: 1024（bge-m3）
- payload: `archive_id`, `plan_id`, `plan_type`, `archive_type`, `assumptions` (摘要), `decision_basis` (摘要), `created_at`
- `embedding_ref` 赋值策略：由应用层在调用 `upsert_points()` 前生成（如 `f"strategic_archive:{archive_id}"`），成功写入后保留该值，失败则置 None。不依赖 `upsert_points()` 的返回值（`bool`）。

**L4 MinIO bucket:**
- bucket 类型: `archive-evidence`
- 对象命名: `{archive_id}/{created_at.isoformat()}_{archive_type}.json`
- retention: 2555 天（7 年 WORM 默认，到期后可申请延长）
- 注意：`archive()` 方法参数名为 `bucket_type`（非 `bucket`），传入 `archive-evidence`

**L5 Neo4j 节点:**
- 标签: `StrategicArchive`
- 属性: `archive_id`, `plan_id`, `plan_type`, `archive_type`, `created_at`
- 注意：`create_entity()` 第一个参数为 `memory_id`（主键），将 `str(archive_id)` 传入 `memory_id`，`archive_id` **不放入** `properties` 字典

### 优雅降级策略

| 存储层 | 失败影响 | 降级策略 |
|--------|---------|---------|
| L2 (PostgreSQL) | 高 — 元数据丢失 | ❌ 不可降级，抛出 `ArchiveStorageError` |
| L3 (Qdrant) | 中 — 向量检索不可用 | ✅ 降级，`embedding_ref = None`，记录警告日志 |
| L4 (MinIO) | 高 — 证据包丢失 | ❌ 不可降级，抛出 `ArchiveStorageError` |
| L5 (Neo4j) | 低 — 图查询不可用 | ✅ 降级，`graph_ref = None`，记录警告日志 |

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.2 |
| **Version** | create-story workflow v2.9.0 |
| **Execution Date** | 2026-08-12 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **存储子系统设计** | `docs/architecture/sisys-storage-subsystem-design.md` |
| **核心领域设计** | `docs/architecture/sisys-core-domain-design.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 3.10, 第 1652-1692 行）
- [x] 架构约束从 `architecture.md` 提取（StrategicArchive 实体定义 §9, 六层存储 §11）
- [x] 前一个故事学习经验整合（Story 3.3 + 3.4 模式）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-10-strategic-archive-permanent-storage.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/entities/strategic_archive.py` - 战略档案实体
- `src/domain/ports/archive_repository.py` - 档案仓储端口
- `src/domain/events/archive_events.py` - 档案领域事件
- `src/domain/exceptions/archive_exceptions.py` - 档案异常
- `src/application/services/strategic_archive_service.py` - 档案编排服务
- `src/infrastructure/storage/postgresql/models/archive.py` - ArchiveModel
- `src/infrastructure/storage/postgresql/repository/archive_repository.py` - PostgreSQLArchiveRepository
- `src/interfaces/api/strategic_archive.py` - 档案路由
- `deploy/postgresql/alembic/versions/008_strategic_archives.py` - 档案表迁移
- `tests/unit/domain/entities/test_archive_entity.py` - 实体测试
- `tests/unit/domain/events/test_archive_events.py` - 事件测试
- `tests/unit/domain/exceptions/test_archive_exceptions.py` - 异常测试
- `tests/unit/application/services/test_strategic_archive_service.py` - 服务测试
- `tests/unit/interfaces/api/test_archive_routes.py` - 路由测试
- `tests/unit/infrastructure/storage/test_archive_repository.py` - 仓储测试
- `tests/unit/architecture/test_arch_strategic_archive.py` - 架构验证测试
- `tests/integration/test_integration_strategic_archive.py` - 集成测试
- `tests/contracts/test_port_contract_strategic_archive.py` - 端口契约测试
- `tests/contracts/test_api_contract_strategic_archive.py` - API 契约测试
- `tests/acceptance/test_acceptance_strategic_archive.feature` - Gherkin 场景
- `tests/acceptance/test_acceptance_strategic_archive.py` - BDD 步骤实现

**待更新的文件/To Be Updated:**
- `src/domain/entities/__init__.py` - 导出 StrategicArchive
- `src/domain/ports/__init__.py` - 导出 ArchiveRepositoryPort
- `src/domain/events/__init__.py` - 导出 ArchiveCreated
- `src/domain/exceptions/__init__.py` - 导出档案异常
- `src/domain/exceptions/_code_ranges.py` - 注册 archive 子域
- `src/infrastructure/storage/postgresql/models/__init__.py` - 导出 ArchiveModel
- `src/interfaces/api/exception_handlers.py` - 注册 EXCEPTION_HTTP_MAP
- `src/interfaces/api/app.py` - 注册路由
- `src/composition_root.py` - 注册 archive_repository + strategic_archive_service
- `configs/event_channels.yaml` - 注册 ArchiveCreated 通道
- `src/infrastructure/messaging/channel_router.py` - 注册 DEFAULT_MAPPINGS

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.10 |
| **Story Key** | 3-10-strategic-archive-permanent-storage |
| **File** | `_bmad-output/implementation-artifacts/stories/3-10-strategic-archive-permanent-storage.md` |
| **Status** | `backlog` → `ready-for-dev` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | P1-10 |
| **覆盖 FR** | FR-SA-01（P0） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| — | 初始版本 | — | — |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** (待定)
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策 Decision Needed

- [ ] (待定)

#### 已修复 Patch

- [ ] (待定)

#### 已推迟 Defer

- [ ] (待定)

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-08-12
**最后更新/Last Updated:** 2026-08-12
**更新说明/Description:**
- v1.0.0: 创建故事文件
