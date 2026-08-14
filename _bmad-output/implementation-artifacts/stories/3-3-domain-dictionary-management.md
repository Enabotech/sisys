# Story 3.3: 战略领域词典库管理

**Status:** `done`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 领域专家,
**I want** 系统管理战略领域词典库（词条 CRUD + 热更新 + 版本管理）,
**So that** 实体抽取准确率持续提升，新词/变化无需重启系统即可生效且可安全回滚。

### 业务价值

本 Story 是 Epic 3（智能检索与知识发现）的**领域词典管理 Story**，也是 FR-SR-03（战略领域词典库管理）的完整实现。它为 Story 3.2b 已交付的 `RuleBasedExtractor` 提供**可管理的词典数据源**，连接"业务专家维护词典"与"实体抽取引擎消费词典"两个环节。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **词典 CRUD** | 领域专家可添加/修改/删除词条，持续丰富实体抽取语料 | 词条增删改查准确 100% |
| **热更新** | 词典变更无需重启系统即生效，实体抽取立即使用新词 | 热更新延迟 P95<100ms |
| **版本管理** | 词典快照 + 回滚，异常变更可快速恢复 | 回滚延迟 P95<200ms |
| **与规则基抽取集成** | 动态词典喂给 `RuleBasedExtractor.reload_dictionary()` | 核心战略概念覆盖率≥95% |
| **异常体系** | 词典专属异常，与项目异常体系集成 | 编码唯一性验证 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 3: 智能检索与知识发现，Story 3.3

**前置依赖:**
- Story 3.2b（实体抽取 ✅ 已实现）— 提供 `RuleBasedExtractor`（含 `reload_dictionary()` 热更新方法）作为词典消费端
- Story 1.5（PostgreSQL ✅ 已实现）— 提供 L2 关系存储用于词典/快照持久化
- Story 1.4（Redis ✅ 已实现）— 提供 `RedisAdapter` 用于词典热缓存（可选优化）
- Story 1.2/1.3（领域事件 + 事件总线 ✅ 已实现）— 提供事件发布能力

**后续依赖:** Story 3.5（分层检索 L1-L4，消费领域词典）、Epic 12 Story 12.1（实体对齐与消歧，复用词典归一化能力）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 领域词典端口契约定义

**Given** 系统需要统一的领域词典管理抽象
**When** 定义 `DomainDictionaryPort` 协议
**Then** 包含词条 CRUD、快照、回滚、获取活动词典等核心方法
**And** 携带领域值对象（`DictionaryEntry`/`DictionaryQuery`/`DictionarySnapshot`）
**And** 所有领域层定义零外部依赖（仅 Python 标准库 + Protocol）

**验证标准/Validation Criteria:**
- [ ] `DomainDictionaryPort` Protocol 定义于 `src/domain/ports/domain_dictionary.py`
- [ ] `DictionaryConsumerPort` Protocol 定义于同一文件，包含 `reload_dictionary(dictionary: list[tuple[str, str]]) -> None` 方法
- [ ] `DictionaryEntry` frozen dataclass（term, entity_type, category, active, version, created_by, created_at, updated_at）
- [ ] `DictionaryQuery` frozen dataclass（category, entity_type, active_only, page, page_size）
- [ ] `DictionarySnapshot` frozen dataclass（snapshot_id, version, entries, created_by, created_at, change_summary）
- [ ] `get_active_dictionary() -> list[tuple[str, str]]` — 返回 (词条, 实体类型) 列表，**直接对接 `RuleBasedExtractor` 的 `reload_dictionary()` 输入格式**
- [ ] `get_entry(term) -> DictionaryEntry | None` — 按词条名查询
- [ ] `add_entry()` / `update_entry()` / `delete_entry()` / `list_entries()` — 词条 CRUD
- [ ] `count_entries(query: DictionaryQuery) -> int` — 按查询条件统计词条总数（支持分页总数统计）
- [ ] `create_snapshot()` / `rollback()` / `list_snapshots()` — 版本管理
- [ ] 端口注册于 `composition_root.py`，通过 `register_port()` 注册为 `domain_dictionary` 端口

### AC-2: 领域词典异常体系

**Given** 词典管理过程中可能发生多种错误
**When** 定义词典异常类
**Then** 继承 `BusinessException` 层次结构（业务管理，非外部服务）
**And** 分配唯一异常编码（新增 `dictionary` 子域 270-279）

**验证标准/Validation Criteria:**
- [ ] `DictionaryNotFoundError`（EXCEPTION_270）— 继承 `NotFoundError`，词条/快照不存在
- [ ] `DictionaryEntryConflictError`（EXCEPTION_271）— 继承 `ConflictError`，词条重复/冲突
- [ ] `DictionaryVersionConflictError`（EXCEPTION_272）— 继承 `ConflictError`，版本号不匹配（乐观锁）
- [ ] 异常编码在 `_code_ranges.py` 注册 `dictionary` 子域 (270, 279)，无碰撞
- [ ] 异常在 `__init__.py` 导出，在 `EXCEPTION_HTTP_MAP` 注册（404/409/409）

### AC-3: 领域词典领域事件

**Given** 词典发生变更（新增/修改/删除/回滚）
**When** 发布 `DictionaryUpdated` 领域事件
**Then** 事件携带变更元数据（term, action, trigger, version）
**And** 继承 `DomainEvent` 基类，遵循事件标准 Schema

**验证标准/Validation Criteria:**
- [ ] `DictionaryUpdated` 定义于 `src/domain/events/dictionary_events.py`
- [ ] 字段：`term`（str）、`action`（str: add/update/delete/rollback）、`trigger`（str）、`dictionary_version`（int）
- [ ] `__post_init__` 设置 `aggregate_type = "Dictionary"`
- [ ] 事件注册于 `src/domain/events/__init__.py`、`configs/event_channels.yaml`、`ChannelRouter.DEFAULT_MAPPINGS`（RELIABLE 模式）

### AC-4: 应用层词典编排服务

**Given** 领域层端口契约已定义
**When** 实现 `DomainDictionaryService`
**Then** 组合 `DomainDictionaryPort`（持久化）+ 规则抽取器热更新能力
**And** 提供 `refresh_dictionary()`（触发热更新到 `RuleBasedExtractor`）
**And** 提供 `create_snapshot()` / `rollback()` 版本管理
**And** 词条变更后自动发布 `DictionaryUpdated` 事件

**验证标准/Validation Criteria:**
- [ ] `DomainDictionaryService` 位于 `src/application/services/domain_dictionary_service.py`
- [ ] 构造函数注入：`dictionary_repo`（DomainDictionaryPort）、`dictionary_consumer`（DictionaryConsumerPort）、`event_publisher`（EventPublisher）
- [ ] `refresh_dictionary()` 调用 `dictionary_consumer.reload_dictionary(repo.get_active_dictionary())`（复用 Story 3.2b 已交付的 `RuleBasedExtractor.reload_dictionary()` 能力）
- [ ] `add_entry()`/`update_entry()`/`delete_entry()` → 变更后自动发布 `DictionaryUpdated` 事件
- [ ] `rollback(version)` → 恢复该版本词典 + 触发热更新 + 发布事件
- [ ] 空输入/无效词条校验走领域异常体系（禁止 `ValueError`）

> **⚠️ 端口契约（P0 关键设计决策）：** `DomainDictionaryService` **不得**注入 `EntityExtractionPort` 并调用其 `reload_dictionary()`。`EntityExtractionPort` 协议（`src/domain/ports/entity_extraction.py`）**仅声明 `extract_entities()` 一个方法**，`reload_dictionary()` 是 `RuleBasedExtractor` 具体类的方法（`rule_extractor.py:218`），**不在**端口协议上。若直接注入 `EntityExtractionPort` 却调用 `reload_dictionary()`，将违反六边形架构依赖倒置原则（应用层依赖具体类方法），且触发 mypy 报错（项目禁止 `# type: ignore`）。**方案：遵循接口隔离原则（ISP），新建独立 `DictionaryConsumerPort` 协议**（见 SDD 规范"统一端口定义"章节），`RuleBasedExtractor` 同时实现 `EntityExtractionPort` 与 `DictionaryConsumerPort`，`DomainDictionaryService` 注入 `DictionaryConsumerPort`。

### AC-5: 基础设施层 PostgreSQL 词典仓储

**Given** 需要持久化词典数据
**When** 实现 `PostgreSQLDomainDictionaryRepository`
**Then** 遵循 `PostgreSQLAdapter` 基类模式（继承 L2 仓储最佳实践）
**And** 词条存单表、快照存独立表，支持乐观锁版本控制

**验证标准/Validation Criteria:**
- [ ] 仓储实现 `DomainDictionaryPort` 位于 `src/infrastructure/storage/postgresql/repository/domain_dictionary_repository.py`
- [ ] 继承 `PostgreSQLAdapter` 泛型基类（或遵循相同 CRUD 模式）
- [ ] 词条主键 `term`（业务唯一键），版本号单调递增
- [ ] `merge` 语义幂等保存（INSERT-or-UPDATE）
- [ ] `rollback` 通过快照表恢复词条
- [ ] Alembic migration 新增词典表 + 快照表（只新增不修改已合入 migration）
- [ ] 乐观锁：`UPDATE ... WHERE version = :expected`，rowcount==0 抛 `DictionaryVersionConflictError`

### AC-6: 词典热更新（与 RuleBasedExtractor 集成）

**Given** 词典数据发生变更且调用刷新
**When** 执行 `refresh_dictionary()`
**Then** 新词典立即注入 `RuleBasedExtractor`
**And** **无需重启系统**即对后续实体抽取生效
**And** 核心战略概念覆盖率≥95%

**验证标准/Validation Criteria:**
- [ ] 热更新延迟 P95<100ms
- [ ] 通过 `RuleBasedExtractor.reload_dictionary()` 实现运行时注入
- [ ] 热更新后立即抽取包含新增词条
- [ ] 热更新后不匹配已删除词条

### AC-7: 接口层 REST API（领域专家维护词典）

**Given** 领域专家需要通过 API 维护词典
**When** 实现字典管理 REST 路由
**Then** 提供词条 CRUD + 热更新 + 快照 + 回滚接口
**And** 所有接口过认证中间件，遵循统一错误响应

**验证标准/Validation Criteria:**
- [ ] 路由名为 `document_dictionary_router`，工厂函数 `create_document_dictionary_router()`，前缀 `/api/v1/documents/dictionary`
- [ ] `GET /api/v1/documents/dictionary/entries` — 列表词条（分页 + 过滤）
- [ ] `POST /api/v1/documents/dictionary/entries` — 添加词条
- [ ] `PUT /api/v1/documents/dictionary/entries/{term}` — 修改词条
- [ ] `DELETE /api/v1/documents/dictionary/entries/{term}` — 删除词条
- [ ] `POST /api/v1/documents/dictionary/refresh` — 触发热更新
- [ ] `POST /api/v1/documents/dictionary/snapshots` — 创建快照
- [ ] `POST /api/v1/documents/dictionary/rollback/{version}` — 回滚
- [ ] 请求/响应 Schema 使用 Pydantic，定义于路由同文件
- [ ] 支持 `get_current_user_override` 测试覆盖依赖注入模式

### AC-8: 端口注册与 DI 集成

**Given** 所有组件实现完成
**When** 在 `composition_root.py` 注册
**Then** `domain_dictionary_repo`、`domain_dictionary_service` 端口注册为 SCOPED
**And** 通过 `Resolver` 可正确解析
**And** 端口契约测试通过

**验证标准/Validation Criteria:**
- [ ] `composition_root.py` 注册 `domain_dictionary_repo` 端口（PostgreSQLDomainDictionaryRepository 实现 DomainDictionaryPort）
- [ ] `composition_root.py` 注册 `domain_dictionary_service` 端口（DomainDictionaryService 编排服务）
- [ ] **`entity_extraction_rule` 端口生命周期改为 `Lifetime.SINGLETON`**（确保词典热更新跨请求全局生效）
- [ ] 端口契约测试 `tests/contracts/test_port_contract_domain_dictionary.py` 通过
- [ ] **`DictionaryConsumerPort` 契约验证通过**：`RuleBasedExtractor` 同时实现 `EntityExtractionPort` 与 `DictionaryConsumerPort`，`reload_dictionary()` 签名正确
- [ ] `src/domain/ports/__init__.py` 导出 `DomainDictionaryPort`、`DictionaryConsumerPort` 及值对象

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

**新建事件：**
- [ ] `DictionaryUpdated`（`src/domain/events/dictionary_events.py`）
  - 继承 `DomainEvent`
  - 字段: `term: str` — 变更词条
  - `action: str` — 动作（"add" / "update" / "delete" / "rollback"）
  - `trigger: str` — 触发源（"api" / "ingest" / "manual"）
  - `dictionary_version: int = 0` — 变更后的词典版本号（独立字段，不覆盖基类 `version`）
  - 事件类型: `"DictionaryUpdated"`（`field(default="DictionaryUpdated", init=False)`）
  - `__post_init__` 设置 `aggregate_type = "Dictionary"`
  - Schema 版本: v1.0.0
  - 通道: `RabbitMQ + Outbox`（业务状态型，RELIABLE 模式）
  - 注册于 `src/domain/events/__init__.py`、`configs/event_channels.yaml`、`ChannelRouter.DEFAULT_MAPPINGS`
  - **`event_channels.yaml` 配置指引：** 参照 `MemoryChanged` / `EntitiesExtracted` 模式，仅配置 `rabbitmq_routing_key`，不配置 `redis_channel`。示例：`rabbitmq_routing_key: "sisys.events.reliable.dictionary_updated"` + `delivery_mode: "reliable"`。**注意预存 bug：** `event_bus_config_loader.py` 的 `DEFAULT_CONFIG_PATH` 指向不存在的 `config/`（单数），YAML 实际未加载，需在实施时一并修复（见下方"环境变量设计"章节的预存 Bug 提示）；`DEFAULT_MAPPINGS` 注册是 DictionaryUpdated 通道生效的可靠保证。

> **⚠️ `dictionary_version` 字段说明：** `DomainEvent` 基类已有 `version: int = 0`（事件版本号）。**DictionaryUpdated 使用独立字段名 `dictionary_version: int`** 表示词典版本，避免与基类 `version`（事件单调版本）语义冲突。`dictionary_version` 不在 `_CORE_FIELD_NAMES` 中，序列化时会自动进入 `merged_payload`，反序列化时从 payload 提取。`__post_init__` 中不覆盖基类 `version`。

#### 数据模型 (Data Models)

**新建值对象（领域层 `src/domain/ports/domain_dictionary.py`）：**
- [ ] `DictionaryEntry` frozen dataclass
  - 字段: `term: str` — 词条文本（业务唯一键，必填非空）
  - `entity_type: str` — 实体类型（PERSON/ORG/LOC/PRODUCT/CONCEPT/...）
  - `category: str = "general"` — 词条类别（strategy/finance/market/tech/org/general）
  - `active: bool = True` — 是否启用
  - `version: int = 1` — 词条版本
  - `created_by: str = ""` — 创建者
  - `created_at: str = ""` — 创建时间（ISO 字符串，保持领域层零依赖）
  - `updated_at: str = ""` — 更新时间（ISO 字符串）

- [ ] `DictionaryQuery` frozen dataclass（DDD Query Object 模式）
  - 字段: `category: str | None = None` — 按类别过滤
  - `entity_type: str | None = None` — 按实体类型过滤
  - `active_only: bool = True` — 仅返回启用词条
  - `page: int = 1` — 页码
  - `page_size: int = 50` — 每页条数（≤100）

- [ ] `DictionarySnapshot` frozen dataclass
  - 字段: `snapshot_id: str` — 快照 ID
  - `version: int` — 词典版本号
  - `entries: tuple[DictionaryEntry, ...]` — 快照词条
  - `created_by: str = ""` — 创建者
  - `created_at: str = ""` — 创建时间
  - `change_summary: dict = field(default_factory=dict)` — 变更摘要（added/updated/removed 计数）

#### 统一端口定义注册与管理 (Port Contract)

**新建端口：**
- [ ] `DomainDictionaryPort`（`src/domain/ports/domain_dictionary.py`）
  - 方法: `async list_entries(query: DictionaryQuery) -> list[DictionaryEntry]`
  - 方法: `async get_entry(term: str) -> DictionaryEntry | None`
  - 方法: `async add_entry(entry: DictionaryEntry) -> DictionaryEntry`
  - 方法: `async update_entry(term: str, entry: DictionaryEntry) -> DictionaryEntry`
  - 方法: `async delete_entry(term: str) -> None`
  - 方法: `async get_active_dictionary() -> list[tuple[str, str]]`（返回 (词条, 实体类型)，对接 RuleBasedExtractor）
  - 方法: `async create_snapshot(created_by: str) -> DictionarySnapshot`
  - 方法: `async rollback(version: int) -> None`
  - 方法: `async list_snapshots() -> list[DictionarySnapshot]`
  - 方法: `async count_entries(query: DictionaryQuery) -> int` — 统计符合条件的词条总数（支持分页总数统计）
  - 版本: v1.0.0, owner: foundation-team
  - 端口契约测试: `tests/contracts/test_port_contract_domain_dictionary.py`

**新建消费端端口（P0 关键设计）：**
- [ ] `DictionaryConsumerPort`（`src/domain/ports/domain_dictionary.py`，与 `DomainDictionaryPort` 同文件）
  - 方法: `def reload_dictionary(dictionary: list[tuple[str, str]]) -> None`
  - 语义: 将完整词典 `(词条, 实体类型)` 列表热注入消费端运行时状态（如 `RuleBasedExtractor` 的 AC 自动机）
  - 目的: 遵循接口隔离原则（ISP），抽象"词典消费端"能力，避免 `DomainDictionaryService` 依赖 `EntityExtractionPort` 协议之外的 `RuleBasedExtractor.reload_dictionary()` 具体方法
  - 实现: `RuleBasedExtractor` 同时实现 `EntityExtractionPort` 与 `DictionaryConsumerPort`（`RuleBasedExtractor.reload_dictionary()` 已存在，仅需在类声明中追加 `DictionaryConsumerPort` 基类即可，无需改动方法体）
  - 版本: v1.0.0, owner: foundation-team

**端口契约清单（强制）：**

| 端口名称 | 版本 | Owner | 注册 | 解析 | 契约测试 | 状态 |
|---------|------|-------|------|------|---------|------|
| DomainDictionaryPort | v1.0.0 | foundation-team | 新建（domain_dictionary_repo） | 新建 | 新建 | **新建** |
| DictionaryConsumerPort | v1.0.0 | foundation-team | 复用（RuleBasedExtractor 实现） | 复用 | 复用/扩展 | **新建** |
| DomainDictionaryService | v1.0.0 | foundation-team | 新建（domain_dictionary_service） | 新建 | 新建 | **新建** |

#### 领域异常契约 (Domain Exception Contract)

**新建异常类（`src/domain/exceptions/dictionary_exceptions.py`）：**

| 异常类 | 编码 | 继承 | HTTP 映射 | 说明 |
|--------|------|------|-----------|------|
| `DictionaryNotFoundError` | EXCEPTION_270 | `NotFoundError` | 404 | 词条/快照不存在。继承 `NotFoundError` 理由：与 `RoleNotFoundError(221)`→`NotFoundError` 一致，词典词条是有业务标识的资源 |
| `DictionaryEntryConflictError` | EXCEPTION_271 | `ConflictError` | 409 | 词条重复/冲突（如新增已存在词条）。继承 `ConflictError` 理由：与 `RoleAlreadyExistsError(222)`→`ConflictError` 一致 |
| `DictionaryVersionConflictError` | EXCEPTION_272 | `ConflictError` | 409 | 词典版本号不匹配（乐观锁冲突）。继承 `ConflictError` 理由：与 `DocumentVersionConflictError(216)`→`ConflictError` 一致 |

**编码分配验证：**
- 业务子域可用空白范围分析（`_code_ranges.py`）：
  - `business` 201-208 已满
  - `storage` 211-219 / `role` 221-229 / `service` 231-239 / `permission` 241 / `entity` 242-249 / `event` 251-259 / `transfer` 261-269
  - **250 和 270-279 为业务空白**。250 与 event（251 起）相邻且区间过小
  - **推荐新增 `dictionary` 子域 (270, 279)** — 紧接 transfer 之后，预留 10 个编码
- 运行 `grep -r "EXCEPTION_27[0-9]" src/domain/exceptions/` 确认无碰撞

- [ ] 归属模块与基类 — 词典管理是**业务子域**，继承 `BusinessException` 层次（`NotFoundError`/`ConflictError`），不继承 `ExternalException`
- [ ] 唯一编码分配 — 270/271/272，确认无碰撞
- [ ] 构造器参数设计 — 携带 `term`、`expected_version`、`actual_version` 等上下文
- [ ] 编码注册 — 在 `_code_ranges.py` 的 `CODE_RANGES` 新增 `dictionary` 子域 (270, 279) + `_CLASS_TO_SUBDOMAIN` 注册三个异常类
- [ ] **⚠️ 同步更新 `tests/unit/domain/exceptions/test_code_ranges.py` 的 `allowed_child_parent_subdomains`** — 新增 `("dictionary", "business")`，否则 CI 的 `test_subclass_code_in_same_subdomain_as_parent` 会因"非法跨子域继承"失败（三个异常均继承 `business` 子域的 `NotFoundError`/`ConflictError`，子域为 `dictionary），必须登记合法父子域关系
- [ ] 导出完整性 — `__init__.py` + `EXCEPTION_HTTP_MAP`
- [ ] 测试覆盖 — 构造/`to_dict()`/HTTP 映射/编码唯一性/子域范围

#### 六边形架构约束（必须遵守）

> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 本 Story 职责 |
|------|------|-------------|
| domain | `src/domain/` | DomainDictionaryPort + 值对象 + DictionaryUpdated 事件 + 词典异常 |
| application | `src/application/` | DomainDictionaryService 编排（CRUD+热更新+版本管理+事件发布） |
| infrastructure | `src/infrastructure/` | PostgreSQLDomainDictionaryRepository + Alembic migration |
| interfaces | `src/interfaces/` | Dictionary 路由（词条 CRUD + 热更新 + 快照 + 回滚） |

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | infrastructure |
|------------|--------|-------------|----------------|
| **domain (DomainDictionaryPort)** | — | ✗ 禁止 | ✗ 禁止 |
| **application (DomainDictionaryService)** | ✓ 允许 | — | ✗ 禁止 |
| **infrastructure (PG Repository)** | ✓ 允许 | ✓ 允许 | — |

**领域层零依赖原则** — `src/domain/ports/domain_dictionary.py` 仅依赖：
- Python 标准库（`dataclasses`, `typing`）
- `typing.Protocol` / `@runtime_checkable`
- 领域值对象（`DictionaryEntry`, `DictionaryQuery`, `DictionarySnapshot`）
- 不依赖：`pydantic`, `sqlalchemy`, `redis`, `pyahocorasick`

**R1-R5 设计规则对齐：**
- **R1** 领域层统一抽象基础端口：`DomainDictionaryPort` 定义于 `src/domain/ports/`，value objects 同文件
- **R2** 应用层具体端口组合：`DomainDictionaryService` 组合注入 `DomainDictionaryPort`（字典数据）+ **`DictionaryConsumerPort`**（RuleBasedExtractor 词典消费端）+ 事件发布。**不注入 `EntityExtractionPort`**（见 AC-4 端口契约 P0 决策）
- **R3** 基础设施层实现端口：`PostgreSQLDomainDictionaryRepository` 实现 `DomainDictionaryPort`，负责 PostgreSQL 技术实现
- **R4** 接口层适配外部请求：Dictionary 路由负责格式化请求/响应，适配 REST 到端口调用
- **R5** 严格遵循异常设计：新增异常走 `_code_ranges.py` → `__init__.py` → `EXCEPTION_HTTP_MAP` 完整流程

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_domain_dictionary.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_domain_dictionary.py`
- [ ] 业务方评审通过
- [ ] 覆盖场景:
  - Happy Path: 添加词条 → 热更新 → 实体抽取识别新词
  - Happy Path: 修改词条 → 热更新 → 抽取使用新实体类型
  - Happy Path: 创建快照 → 回滚 → 词典恢复至目标版本
  - Happy Path: 删除词条 → 热更新 → 抽取不再匹配
  - Edge Case: 添加已存在词条 → 409 `DictionaryEntryConflictError`
  - Edge Case: 词条不存在修改/删除 → 404 `DictionaryNotFoundError`
  - Edge Case: 回滚到不存在的版本 → 404 `DictionaryNotFoundError`
  - Edge Case: 并发修改版本冲突 → 409 `DictionaryVersionConflictError`
  - Edge Case: 空词条/非法实体类型 → 422/400（领域异常）

> **⚠️ 验收测试禁止 mock（遵循项目硬约束）：** 词典服务为自包含业务逻辑（PG 仓储 + 领域字典），不涉及 LLM/外部网络调用。验收测试必须使用**真实 `DomainDictionaryService` + 真实 `PostgreSQLAdapter` 仓储**，通过测试 schema 隔离 + savepoint rollback 保证自包含。仅当 PG 不可用时可 `pytest.skip()` 动态跳过，禁止 `@pytest.mark.skip` 写死。热更新端到端验证使用 `RuleBasedExtractor` 真实实例（无外部依赖）。

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
| **TDD 单元测试** | DomainDictionaryPort + 值对象 + DictionaryConsumerPort | 端口契约、值对象构造、Query 默认值、消费端端口签名 | `test_domain_dictionary_port.py` | Task 1 |
| **TDD 单元测试** | DictionaryUpdated 事件 | 事件构造、序列化、注册 | `test_dictionary_events.py` | Task 1 |
| **TDD 单元测试** | 词典异常 | 构造/属性/to_dict()/HTTP 映射 | `test_dictionary_exceptions.py` | Task 1 |
| **TDD 单元测试** | DomainDictionaryService | CRUD 编排、热更新 `reload_dictionary()` 调用验证、快照/回滚、事件发布（**mock `DictionaryConsumerPort`**） | `test_domain_dictionary_service.py` | Task 2 |
| **TDD 单元测试** | PostgreSQLDomainDictionaryRepository | 词条 CRUD、版本快照、乐观锁 | `test_domain_dictionary_repository.py` | Task 3 |
| **TDD 单元测试** | Dictionary 路由 | 请求/响应、错误映射、认证 | `test_domain_dictionary_api.py` | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_domain_dictionary.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_domain_dictionary.py` | Task 0 |
| **TDD 契约测试** | DomainDictionaryPort | 端口注册/解析/契约门禁 | `test_port_contract_domain_dictionary.py` | Task 0 |
| **TDD 领域异常测试** | 词典异常 | 编码唯一性/子域范围 | `test_error_code_uniqueness.py` + `test_code_ranges.py` | Task 1 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖 | `test_arch_domain_dictionary.py` | Task 4 |
| **集成测试** | 词典存储 + 热更新管线 | 端到端 CRUD/快照/回滚 + 热更新（含真实 `RuleBasedExtractor` 热更新→抽取端到端验证，吸收 Subtask 2.4 用例） | `test_integration_domain_dictionary.py` | Task 4 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src --cov-fail-under=90 --cov=src/domain/`）
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src --cov-fail-under=85 --cov=src/application/`）
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src --cov-fail-under=75 --cov=src/infrastructure/storage/postgresql/repository/domain_dictionary_repository.py`）
- [ ] **接口层覆盖率 ≥85%**（`pytest --cov=src --cov-fail-under=85 --cov=src/interfaces/api/domain_dictionary.py`）

> ⚠️ **覆盖率说明：** `pyproject.toml` 中 `[tool.coverage.run] omit = ["*/tests/*"]`，覆盖率仅对 `src` 测量，逐层 `--cov-fail-under` 门禁配合 `--cov=src` 整体覆盖。集成测试文件不在 `src` 中，不单独设置覆盖率阈值。

> ⚠️ **骨架 Story 覆盖率豁免：** 本 Story 为应用层实现，非骨架 Story，需达到标准覆盖率要求。

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **事务隔离** | 集成测试使用 transaction rollback（session_context） | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内完成 Schema 初始化，独立 PG schema | 依赖外部迁移，环境不一致 |
| **资源唯一性** | 测试词条使用 UUID/时间戳唯一标识 | 词条冲突 |
| **并行隔离** | 并行测试使用独立测试词条 + 独立 schema | 资源冲突 |
| **提交流程** | 测试环境按 TestTenant 隔离超集（schema） | 交叉污染 |
| **BDD async 配合** | BDD 步骤函数用 event_loop.run_until_complete() | context 数据丢失 |
| **禁止手动清理** | 不手动 delete/truncate（用 savepoint rollback） | 误删共享数据 |

**验证要求：**
- [ ] 并行测试 `poetry run pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | DomainDictionaryPort + DictionaryConsumerPort + 值对象契约 | Task 1 | Subtask 1.1-1.3 | `test_domain_dictionary_port.py` |
| AC-2 | 词典异常体系（270-272） | Task 1 | Subtask 1.4-1.6 | `test_dictionary_exceptions.py` |
| AC-3 | DictionaryUpdated 领域事件 | Task 1 | Subtask 1.7-1.9 | `test_dictionary_events.py` |
| AC-4 | DomainDictionaryService 编排 | Task 2 | Subtask 2.1-2.3 | `test_domain_dictionary_service.py` |
| AC-5 | PostgreSQL 词典仓储 | Task 3 | Subtask 3.1-3.3 | `test_domain_dictionary_repository.py` |
| AC-6 | 词典热更新集成 | Task 2 | Subtask 2.5-2.6（mock 侧）+ Subtask 4.5（真实热更新，原 Subtask 2.4 并入） | `test_domain_dictionary_service.py` + `test_integration_domain_dictionary.py` |
| AC-7 | Dictionary REST API | Task 3 | Subtask 3.4-3.6 | `test_domain_dictionary_api.py` |
| AC-8 | 端口注册与 DI 集成 | Task 4 | Subtask 4.1-4.3 | `test_port_contract_domain_dictionary.py` |
| AC-8 | 架构约束验证 + 集成测试 | Task 4 | Subtask 4.4-4.6 | `test_arch_domain_dictionary.py` + `test_integration_domain_dictionary.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 定义领域词典端口契约（DomainDictionaryPort + DictionaryEntry/DictionaryQuery/DictionarySnapshot）设计
- [ ] Subtask 0.2: 定义词典异常体系设计（DictionaryNotFoundError/DictionaryEntryConflictError/DictionaryVersionConflictError）
- [ ] Subtask 0.3: 定义 `_code_ranges.py` 新增 `dictionary` 子域（270-279）
- [ ] Subtask 0.4: 定义 DictionaryUpdated 领域事件设计
- [ ] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_domain_dictionary.feature`
- [ ] Subtask 0.6: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_domain_dictionary.py`
- [ ] Subtask 0.7: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 领域层端口 + 值对象 + 异常 + 事件（领域层）

**关联 AC:** AC-1, AC-2, AC-3

> **领域层零外部依赖：** 本 Task 所有代码位于 `src/domain/`，仅使用 Python 标准库。
> 禁止导入：pydantic, sqlalchemy, redis, pyahocorasick 等任何第三方库。

#### TDD 循环 [A]：DomainDictionaryPort + 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_domain_dictionary_port.py`（端口契约 + 值对象构造） |
| 🟢 绿 | 实现 `src/domain/ports/domain_dictionary.py`（DomainDictionaryPort + DictionaryConsumerPort + 值对象） |
| 🔄 重构 | 优化类型注解，运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 DomainDictionaryPort 失败测试
  - `DictionaryEntry` frozen dataclass 构造（所有字段默认值正确，term 必填非空校验）
  - `DictionaryQuery` frozen dataclass 构造（默认 category=None, active_only=True, page=1, page_size=50，page_size 上限 100）
  - `DictionarySnapshot` frozen dataclass 构造
  - `DomainDictionaryPort` Protocol 结构验证（`list_entries`/`add_entry`/`update_entry`/`delete_entry`/`get_active_dictionary`/`create_snapshot`/`rollback`/`list_snapshots` 方法签名）
  - `DictionaryConsumerPort` Protocol 结构验证（`reload_dictionary` 方法签名，参数为 `list[tuple[str, str]]`，返回 `None`）
  - `@runtime_checkable` 可用
- [ ] Subtask 1.2: 🟢 绿 — 实现 DomainDictionaryPort + DictionaryConsumerPort + 值对象
  - `DictionaryEntry`：用 `__post_init__` 校验 term 非空（违反时抛 `EntityValidationError`，领域异常体系）
  - `DictionaryQuery`：`__post_init__` 钳制 page_size ≤100、page ≥1（抛 `EntityValidationError`）
  - `DomainDictionaryPort` Protocol 定义全部方法
  - `DictionaryConsumerPort` Protocol 定义 `reload_dictionary()` 方法
- [ ] Subtask 1.3: 🔄 重构 — 优化代码，运行 `ruff` + `mypy`

#### TDD 循环 [B]：词典异常体系

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_dictionary_exceptions.py`（异常构造 + to_dict + HTTP 映射） |
| 🟢 绿 | 实现 `src/domain/exceptions/dictionary_exceptions.py` |
| 🔄 重构 | 更新 `__init__.py` + `_code_ranges.py` + `EXCEPTION_HTTP_MAP`，运行 `ruff` + `mypy` |

- [ ] Subtask 1.4: 🔴 红 — 编写词典异常失败测试
  - `DictionaryNotFoundError` 构造（含 term 上下文）→ HTTP 404
  - `DictionaryEntryConflictError` 构造（含 term 上下文）→ HTTP 409
  - `DictionaryVersionConflictError` 构造（含 expected_version/actual_version 上下文）→ HTTP 409
  - `to_dict()` 序列化正确（含 cause 链）
  - 编码唯一性（`test_error_code_uniqueness.py` 中确认无碰撞）
  - 子域范围（`test_code_ranges.py` 中新增 dictionary 子域）
- [ ] Subtask 1.5: 🟢 绿 — 实现词典异常类
  - 创建 `src/domain/exceptions/dictionary_exceptions.py`
  - 更新 `src/domain/exceptions/__init__.py` 导出
  - 更新 `src/domain/exceptions/_code_ranges.py` 新增 `dictionary` 子域 (270, 279) + `_CLASS_TO_SUBDOMAIN` 映射
  - 更新 `src/interfaces/api/exception_handlers.py` 的 `EXCEPTION_HTTP_MAP`
  - **⚠️ 更新 `tests/unit/domain/exceptions/test_code_ranges.py` 的 `allowed_child_parent_subdomains`** 新增 `("dictionary", "business")`（否则 CI 的 `test_subclass_code_in_same_subdomain_as_parent` 会因 DictionaryNotFoundError 等的子域 `dictionary` 继承自 `business` 子域的父类而报"非法跨子域继承"）
- [ ] Subtask 1.6: 🔄 重构 — 运行 `ruff check` + `mypy` + `pytest tests/unit/domain/exceptions/ -v`

#### TDD 循环 [C]：DictionaryUpdated 领域事件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/events/test_dictionary_events.py`（事件构造 + 序列化 + 注册） |
| 🟢 绿 | 实现 `src/domain/events/dictionary_events.py`（DictionaryUpdated 事件） |
| 🔄 重构 | 更新 `__init__.py` + 事件注册，运行 `ruff` + `mypy` |

- [ ] Subtask 1.7: 🔴 红 — 编写 DictionaryUpdated 事件失败测试
  - `DictionaryUpdated` 继承 `DomainEvent`，关键字段（term, action, trigger, dictionary_version）
  - 事件自动注册到 `_registry`
  - `to_dict()` / `from_dict()` 序列化正确
  - `__post_init__` 设置 `aggregate_type = "Dictionary"`
- [ ] Subtask 1.8: 🟢 绿 — 实现 DictionaryUpdated 事件
  - 字段使用 `dictionary_version`（不用 `version`，避免与基类 `version` 冲突）
  - `event_type` 固定为 `"DictionaryUpdated"`
- [ ] Subtask 1.9: 🔄 重构 — 运行 `ruff` + `mypy`

**完成标准/Definition of Done:**
- [ ] DomainDictionaryPort + 值对象实现完成
- [ ] 词典异常体系实现完成（270/271/272）
- [ ] DictionaryUpdated 事件实现完成
- [ ] TDD 循环全部通过
- [ ] 编码无碰撞验证通过
- [ ] 领域层覆盖率≥90%

---

### Task 2: 应用层词典编排服务（热更新 + 版本管理）

**关联 AC:** AC-4, AC-6

> **应用层编排：** 本 Task 实现 `DomainDictionaryService`，组合 `DomainDictionaryPort`（持久化）与 **`DictionaryConsumerPort`**（RuleBasedExtractor 热更新消费端）。**不注入 `EntityExtractionPort`**（见 AC-4 端口契约 P0 决策）。

#### TDD 循环 [A]：DomainDictionaryService 编排 + 热更新

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_domain_dictionary_service.py` |
| 🟢 绿 | 实现 `src/application/services/domain_dictionary_service.py` |
| 🔄 重构 | 优化编排逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 2.1: 🔴 红 — 编写 DomainDictionaryService 失败测试
  - **Happy Path:** `add_entry()` 添加词条 → 调用 repo.add_entry + 发布 DictionaryUpdated 事件（action=add）
  - **Happy Path:** `update_entry()` 修改词条 → 调用 repo.update_entry + 发布事件（action=update）
  - **Happy Path:** `delete_entry()` 删除词条 → 调用 repo.delete_entry + 发布事件（action=delete）
  - **Happy Path:** `refresh_dictionary()` → 调用 repo.get_active_dictionary() + dictionary_consumer.reload_dictionary(entries)
  - **Happy Path:** `create_snapshot()` 创建快照 → 调用 repo.create_snapshot
  - **Happy Path:** `rollback(version)` 回滚 → 调用 repo.rollback + reload_dictionary + 发布事件（action=rollback）
  - **Edge Case:** 添加空词条 → 抛 `DictionaryEntryConflictError` 或校验异常（走领域异常）
  - **Edge Case:** 回滚到不存在版本 → 抛 `DictionaryNotFoundError`
  - **Edge Case:** 事件发布失败 → 记录日志（不阻止主流程返回结果）
  - **热更新验证:** refresh 后 dictionary_consumer 实际加载了新词条（mock `DictionaryConsumerPort`，断言 `reload_dictionary()` 被调用且参数为 `repo.get_active_dictionary()` 返回值）
- [ ] Subtask 2.2: 🟢 绿 — 实现 DomainDictionaryService
  - 构造函数注入: `dictionary_repo`（DomainDictionaryPort）、`dictionary_consumer`（DictionaryConsumerPort）、`event_publisher`
  - CRUD 编排：add/update/delete 均委托 repo，成功后发布事件
  - `refresh_dictionary()`：读取活动词典 → 调用 dictionary_consumer.reload_dictionary(list[tuple[str,str]])
  - 快照/回滚：create_snapshot 委托 repo；rollback(version) 委托 repo 后自动 refresh + 发布事件
  - 事件发布失败仅记录日志（不抛出），遵循 Story 3.2b 模式
- [ ] Subtask 2.3: 🔄 重构 — 运行 `ruff` + `mypy`

#### TDD 循环 [B]：热更新正确性验证（跟 RuleBasedExtractor 集成）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 在 `tests/unit/application/services/test_domain_dictionary_service.py` 完成 mock 单元测试（Subtask 2.1 已含）；**Subtask 2.4 的真实热更新验证移至 `tests/integration/test_integration_domain_dictionary.py`**（见下文说明） |
| 🟢 绿 | 完善 DomainDictionaryService 热更新逻辑 |
| 🔄 重构 | 优化 reload 触发，运行 `ruff` + `mypy` |

- [ ] Subtask 2.4: 🔴 红 — 编写热更新失败测试（**归属调整：移至集成测试 `tests/integration/test_integration_domain_dictionary.py`**）
  - **为什么放集成测试：** 本用例使用真实 `RuleBasedExtractor` 做端到端"热更新→抽取"断言，属于真实服务集成验证。虽然 `RuleBasedExtractor` 是纯内存、无外部依赖，但项目 Testing 策略明确"单元测试 Mock 端口，禁止真实服务；集成测试真实服务优先"。为避免与 `tests/unit/application/services/test_domain_dictionary_service.py` 中 mock 端口的单元测试混淆分层，本用例归入集成测试（Subtask 4.5 同一文件，合并为热更新管线用例）。
  - 注册真实 `RuleBasedExtractor`（同时实现 `DictionaryConsumerPort`），初始词典不含 "元宇宙"
  - 添加 "元宇宙" 词条 → `refresh_dictionary()` → 用真实 `RuleBasedExtractor.extract_entities("元宇宙技术趋势")` 断言返回 CONCEPT 实体
  - 热更新后不再匹配已删除词条
  - 热更新延迟 P95<100ms（性能断言，宽松阈值）
  - 核心战略概念覆盖率≥95%（预置词条集验证：BLM/BEM/SWOT/NPV/IRR/PESTEL 等均被识别；注意：**内置词典不含"元宇宙"**，其余预置词条 BLM/BEM/SWOT/NPV/IRR/PESTEL 均已存在，覆盖率断言基于这些已存在词条）
- [ ] Subtask 2.5: 🟢 绿 — 确保 refresh_dictionary 正确注入 list[tuple[str,str]]
- [ ] Subtask 2.6: 🔄 重构 — 运行 `ruff` + `mypy`

**完成标准/Definition of Done:**
- [ ] DomainDictionaryService 实现完成（CRUD + 热更新 + 快照/回滚 + 事件发布）
- [ ] 热更新与 RuleBasedExtractor 真实集成验证通过
- [ ] TDD 循环全部通过
- [ ] 应用层覆盖率≥85%

---

### Task 3: 基础设施仓储 + 接口层 REST API

**关联 AC:** AC-5, AC-7

> **基础设施层依赖：** 仓储代码位于 `src/infrastructure/`，可使用 sqlalchemy。
> **接口层适配：** 路由代码位于 `src/interfaces/api/`，遵循工厂函数 + 双重注入模式。

#### TDD 循环 [A]：PostgreSQLDomainDictionaryRepository

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/postgresql/repository/test_domain_dictionary_repository.py` |
| 🟢 绿 | 实现 `src/infrastructure/storage/postgresql/repository/domain_dictionary_repository.py` |
| 🔄 重构 | 优化 CRUD 逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 3.1: 🔴 红 — 编写仓储失败测试（需真实 PG 或遵循现有仓储测试模式）
  - `add_entry()` 新增词条 → 可被 `get_entry()` 检索到
  - `update_entry()` 修改词条 → 词条 entity_type 变更，版本号递增
  - `delete_entry()` 删除词条 → 不再可检索
  - `list_entries(query)` 分页 + 过滤（category/entity_type/active_only）
  - `get_active_dictionary()` 仅返回 active=True 的 (term, entity_type)
  - `create_snapshot()` 生成快照
  - `rollback(version)` 恢复到目标版本
  - **乐观锁:** 并发更新版本冲突 → 抛 `DictionaryVersionConflictError`（含 expected/actual）
  - **不存在:** get_entry 不存在 → None；update/delete 不存在 → 抛 `DictionaryNotFoundError`
- [ ] Subtask 3.2: 🟢 绿 — 实现 PostgreSQLDomainDictionaryRepository
  - 遵循 `PostgreSQLAdapter` 基类模式（ContextVar session，`merge` 幂等，flush 不 commit）
  - 词条表 + 快照表两个 SQLAlchemy Model
  - 版本递增 + 乐观锁（`UPDATE ... WHERE version = :expected`）
  - 快照表存完整词条 JSON，rollback 时重建词条表
- [ ] Subtask 3.3: 🔄 重构 — 运行 `ruff` + `mypy`

> **⚠️ Alembic migration：** 需新增 `dictionary_entries` + `dictionary_snapshots` 两张表。已合入的 migration 禁止修改，只允许新增 migration 文件。

#### TDD 循环 [B]：Dictionary REST API

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/api/test_domain_dictionary_api.py` |
| 🟢 绿 | 实现 `src/interfaces/api/domain_dictionary.py`（工厂函数路由） |
| 🔄 重构 | 优化错误映射，运行 `ruff` + `mypy` |

- [ ] Subtask 3.4: 🔴 红 — 编写路由失败测试
  - **Happy Path:** `POST /api/v1/documents/dictionary/entries` 添加词条 → 201/200
  - **Happy Path:** `GET /api/v1/documents/dictionary/entries` 列表 → 200
  - **Happy Path:** `PUT /api/v1/documents/dictionary/entries/{term}` 修改 → 200
  - **Happy Path:** `DELETE /api/v1/documents/dictionary/entries/{term}` 删除 → 200/204
  - **Happy Path:** `POST /api/v1/documents/dictionary/refresh` 热更新 → 200
  - **Happy Path:** `POST /api/v1/documents/dictionary/snapshots` 快照 → 201
  - **Happy Path:** `POST /api/v1/documents/dictionary/rollback/{version}` 回滚 → 200
  - **Edge Case:** 添加重复词条 → 409，error.code=EXCEPTION_271 + error.message + request_id
  - **Edge Case:** 修改不存在词条 → 404，error.code=EXCEPTION_270
  - **Edge Case:** 认证失败 → 401（`get_current_user_override` 可跳过）
- [ ] Subtask 3.5: 🟢 绿 — 实现 Dictionary 路由
  - `create_document_dictionary_router()` 工厂函数，前缀 `/api/v1/documents/dictionary`
  - 请求/响应 Schema 用 Pydantic 定义于同文件
  - 双重注入：构造器参数（测试 mock）/ `get_resolver().resolve("domain_dictionary_service")`（生产）
  - 认证：`Depends(get_current_user)` + `get_current_user_override` 支持
- [ ] Subtask 3.6: 🔄 重构 — 运行 `ruff` + `mypy`

**完成标准/Definition of Done:**
- [ ] PostgreSQLDomainDictionaryRepository 实现完成（CRUD + 快照 + 乐观锁）
- [ ] Dictionary REST API 实现完成
- [ ] TDD 循环全部通过
- [ ] 基础设施层覆盖率≥75%，接口层覆盖率≥85%

---

### Task 4: 端口注册 + 架构验证 + 集成测试

**关联 AC:** AC-8

> **性质说明：** 本 Task 包含 DI 注册、端口契约测试、架构约束验证和集成测试。

#### 端口注册与 DI 集成

- [ ] Subtask 4.1: 更新 `src/domain/ports/__init__.py` 导出 `DomainDictionaryPort`、`DictionaryConsumerPort`、`DictionaryEntry`、`DictionaryQuery`、`DictionarySnapshot`
- [ ] Subtask 4.2: 更新 `src/composition_root.py` 注册相关端口
  ```python
  # 注册领域词典仓储（PostgreSQLDomainDictionaryRepository 实现 DomainDictionaryPort）
  register_port(
      name="domain_dictionary_repo",
      version="v1.0.0",
      interface=DomainDictionaryPort,
      impl="src.infrastructure.storage.postgresql.repository.domain_dictionary_repository.PostgreSQLDomainDictionaryRepository",
      module="src.infrastructure.storage.postgresql.repository.domain_dictionary_repository",
      lifetime=Lifetime.SCOPED,
      owner="foundation-team",
      tags=("dictionary", "gateway", "application"),
  )

  # 注册 DomainDictionaryService 应用服务（注入仓储 + 词典消费端 + 事件发布）
  register_port(
      name="domain_dictionary_service",
      version="v1.0.0",
      interface=DomainDictionaryService,
      impl=lambda resolver: DomainDictionaryService(
          dictionary_repo=resolver.resolve("domain_dictionary_repo"),
          dictionary_consumer=resolver.resolve("entity_extraction_rule"),
          event_publisher=resolver.resolve("event_publisher"),
      ),
      module="src.application.services.domain_dictionary_service",
      lifetime=Lifetime.SCOPED,
      owner="foundation-team",
      tags=("dictionary", "service", "application"),
  )
  ```
  - 生命周期: SCOPED
  - Owner: foundation-team
  - **端口契约（P0）：** `DomainDictionaryService` 注入 `dictionary_consumer` 端口，其运行时类型为 `RuleBasedExtractor`（同时实现 `EntityExtractionPort` 与 `DictionaryConsumerPort`）。`entity_extraction_rule` 端口在 composition_root 中以 `interface=EntityExtractionPort` 注册——由于 `RuleBasedExtractor` 同时实现 `DictionaryConsumerPort`，`resolver.resolve("entity_extraction_rule")` 返回的实例可安全作为 `DictionaryConsumerPort` 注入（`RuleBasedExtractor` 已实现 `reload_dictionary()`）。**不需要**为 `DictionaryConsumerPort` 单独注册新端口，复用 `entity_extraction_rule` 即可。

  > **⚠️ 生命周期（P1 关键决策）：** `entity_extraction_rule` 端口当前以 **`Lifetime.SCOPED`** 注册（`composition_root.py:1713`）。**热更新语义要求词典全局共享**——若 SCOPED，每个请求作用域新建 `RuleBasedExtractor` 实例，`refresh_dictionary()` 只更新当前作用域实例的词典，其他并发请求仍持有旧词典，**热更新跨请求不生效**。**必须将 `entity_extraction_rule` 生命周期改为 `Lifetime.SINGLETON`**，确保所有请求共享同一词典自动机实例。改生命周期时需注意：`RuleBasedExtractor` 非线程安全，`reload_dictionary()` 替换 `_automaton` 与 `extract_entities()` 读取 `_automaton` 并发访问需用 `asyncio.Lock`（**声明为类变量**，见项目 Gotchas）或 copy-on-write 模式保护。

#### 端口契约测试

- [ ] Subtask 4.3: 创建 `tests/contracts/test_port_contract_domain_dictionary.py`
  - 验证 `domain_dictionary_repo` 端口已注册到 Registry
  - 验证 `domain_dictionary_service` 端口已注册到 Registry
  - 验证 `Resolver` 可解析各端口
  - 验证 `DomainDictionaryPort` 方法签名正确
  - 验证 `RuleBasedExtractor` 实现 `DictionaryConsumerPort`（`hasattr(extractor, "reload_dictionary")` + 签名检查）
  - 遵循"三方法"模式（注册验证、实现方法签名验证、元数据验证）

#### 架构验证测试

- [ ] Subtask 4.4: 创建 `tests/unit/architecture/test_arch_domain_dictionary.py`
  - 验证 `src/domain/ports/domain_dictionary.py` 零外部依赖（仅标准库）
  - 验证 `DomainDictionaryPort` 位于领域层
  - 验证 `PostgreSQLDomainDictionaryRepository` 位于基础设施层
  - 验证 `DomainDictionaryService` 位于应用层
  - 验证依赖方向正确（infrastructure → domain，application → domain）

#### 集成测试

- [ ] Subtask 4.5: 创建 `tests/integration/test_integration_domain_dictionary.py`
  - 端到端：真实 PG 仓储 CRUD（遵循测试 schema 隔离 + savepoint rollback）
  - 词条 → 快照 → 回滚 全链路
  - 乐观锁并发冲突
  - 热更新管线（真实 RuleBasedExtractor + 词典服务）——**吸收原 Subtask 2.4 的真实热更新验证用例**（见 Task 2 TDD 循环 [B] 归属调整说明）

**完成标准/Definition of Done:**
- [ ] `composition_root.py` 注册 `domain_dictionary_repo` / `domain_dictionary_service` 端口
- [ ] 端口契约测试通过
- [ ] 所有架构约束测试通过
- [ ] 集成测试通过
- [ ] 领域层零外部依赖

---

### Task 5: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8

> **性质说明：** 本 Task 是对 Story 收尾阶段的交付物与完成清单进行最终验收。

- [ ] Subtask 5.1: 场景 1 — 验证 `src` 完成清单的逐项确认
  - `src/domain/ports/domain_dictionary.py` — DomainDictionaryPort + DictionaryConsumerPort + 值对象
  - `src/domain/exceptions/dictionary_exceptions.py` — DictionaryNotFoundError/DictionaryEntryConflictError/DictionaryVersionConflictError
  - `src/domain/exceptions/__init__.py` — 导出词典异常
  - `src/domain/exceptions/_code_ranges.py` — 新增 dictionary 子域 (270-279)
  - `src/domain/events/dictionary_events.py` — DictionaryUpdated 事件
  - `src/domain/ports/__init__.py` — 导出 DomainDictionaryPort + DictionaryConsumerPort + 值对象
  - `src/domain/events/__init__.py` — 导出 DictionaryUpdated
  - `src/application/services/domain_dictionary_service.py` — DomainDictionaryService
  - `src/infrastructure/storage/postgresql/repository/domain_dictionary_repository.py` — PostgreSQLDomainDictionaryRepository
  - `src/interfaces/api/domain_dictionary.py` — Dictionary 路由
  - `src/interfaces/api/exception_handlers.py` — EXCEPTION_HTTP_MAP 更新
  - `src/composition_root.py` — 注册 domain_dictionary_repo / domain_dictionary_service 端口
  - `configs/event_channels.yaml` — 新增 DictionaryUpdated 事件通道
  - `src/infrastructure/messaging/channel_router.py` — DEFAULT_MAPPINGS 新增 DictionaryUpdated
  - `deploy/postgresql/alembic/versions/` — 新增词典表 + 快照表 migration
- [ ] Subtask 5.2: 场景 2 — 验证 `tests/unit`、`tests/contracts`、`tests/acceptance` 完成清单
  - `tests/unit/domain/ports/test_domain_dictionary_port.py`
  - `tests/unit/domain/exceptions/test_dictionary_exceptions.py`
  - `tests/unit/domain/events/test_dictionary_events.py`
  - `tests/unit/application/services/test_domain_dictionary_service.py`
  - `tests/unit/infrastructure/storage/postgresql/repository/test_domain_dictionary_repository.py`
  - `tests/unit/interfaces/api/test_domain_dictionary_api.py`
  - `tests/unit/architecture/test_arch_domain_dictionary.py`
  - `tests/contracts/test_port_contract_domain_dictionary.py`
  - `tests/integration/test_integration_domain_dictionary.py`
  - `tests/acceptance/test_acceptance_domain_dictionary.feature`
  - `tests/acceptance/test_acceptance_domain_dictionary.py`
- [ ] Subtask 5.3: 运行开发结束验收测试并确认通过
- [ ] Subtask 5.4: 运行 `poetry run pytest --tb=short -q`、`poetry run ruff check src/`、`poetry run mypy src/`、`poetry run pre-commit run --all-files`

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 领域词典管理架构设计

**核心架构模式：领域数据 + 消费端热更新（Managed Dictionary + Hot-Reload Consumer）**

```
领域专家 (REST API)
    │
    ▼  add/update/delete entry
DomainDictionaryService (Application)
    ├─→ 委托 domain_dictionary_repo (PG 持久化)
    ├─→ 发布 DictionaryUpdated 事件
    │
    ├─→ refresh_dictionary()
    │       │
    │       ▼  get_active_dictionary() → list[tuple[str, str]]
    │   DictionaryConsumerPort.reload_dictionary(entries)  ← 通过端口契约调用，非具体类方法
    │       │
    │       ▼  AC 自动机重建（无需重启）
    │   后续实体抽取立即使用新词典
    │
    └─→ 版本管理
        ├─ create_snapshot() → 快照持久化
        └─ rollback(version) → 恢复快照 → 重新热更新
```

**端口契约架构（P0 设计决策）：**
- `EntityExtractionPort` 协议（`src/domain/ports/entity_extraction.py`）**仅声明 `extract_entities()`**，`reload_dictionary()` 不在其上
- 新建 **`DictionaryConsumerPort`**（`src/domain/ports/domain_dictionary.py`，与 `DomainDictionaryPort` 同文件），抽象"词典消费端热更新能力"
- `RuleBasedExtractor` 同时实现 `EntityExtractionPort` 与 `DictionaryConsumerPort`
- `DomainDictionaryService` 注入 `DictionaryConsumerPort`，调用 `reload_dictionary()` 通过端口契约进行
- 遵循接口隔离原则（ISP），不污染 `EntityExtractionPort` 的职责边界

**与 Story 3.2b RuleBasedExtractor 的集成：**
- `RuleBasedExtractor.reload_dictionary(dictionary: list[tuple[str, str]])` 已存在，本 Story 直接复用
- `DomainDictionaryService.refresh_dictionary()` 调用 `repo.get_active_dictionary()`（返回 `list[tuple[str, str]]`）→ `dictionary_consumer.reload_dictionary(entries)`
- **`RuleBasedExtractor` 仅需在类声明中追加 `DictionaryConsumerPort` 基类**，无需改动方法体（Surgical Changes 原则）
- 热更新延迟 P95<100ms：`reload_dictionary()` 仅为重建 AC 自动机（O(n)），性能满足

### 领域事件设计（DictionaryUpdated）

**注意 `version` 字段命名权衡：**
- `DomainEvent` 基类已有 `version: int = 0`（事件单调版本号）
- 词典变更需要携带"词典版本号"，但**不应用** `version`（会与事件版本语义冲突）
- **采用独立字段 `dictionary_version: int = 0`** 标识词典版本号
- `__post_init__` 设置 `aggregate_type = "Dictionary"`，不覆盖基类 `version`
- 序列化时 `dictionary_version` 自动并入 payload（`_CORE_FIELD_NAMES` 之外）

### 异常编码分配决策

**新增 `dictionary` 子域 (270, 279)：**

| 异常类 | 编码 | 继承 | HTTP | 参考对标 |
|--------|------|------|------|---------|
| DictionaryNotFoundError | 270 | NotFoundError | 404 | RoleNotFoundError(221)→NotFoundError |
| DictionaryEntryConflictError | 271 | ConflictError | 409 | RoleAlreadyExistsError(222)→ConflictError |
| DictionaryVersionConflictError | 272 | ConflictError | 409 | DocumentVersionConflictError(216)→ConflictError |

**子域选择推理：**
- 词典管理是**业务子域**，必须继承 `BusinessException`，不继承 `ExternalException`
- 业务空白范围：250（单点，过小）、270-279（紧接 transfer 后，10 个编码充裕）
- 新增 `_code_ranges.py` 条目：`"dictionary": (270, 279)`
- `_CLASS_TO_SUBDOMAIN` 注册三个异常类

### 数据模型与存储设计

**词条表 `dictionary_entries`：**
| 列 | 类型 | 说明 |
|----|------|------|
| term | VARCHAR(200) PK | 词条文本（业务唯一键） |
| entity_type | VARCHAR(50) | 实体类型 |
| category | VARCHAR(50) | 类别（strategy/finance/market/tech/org/general） |
| active | BOOLEAN | 是否启用 |
| version | INTEGER | 词条版本（乐观锁） |
| created_by | VARCHAR(100) | 创建者 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

**快照表 `dictionary_snapshots`：**
| 列 | 类型 | 说明 |
|----|------|------|
| snapshot_id | UUID PK | 快照 ID |
| version | INTEGER UNIQUE | 词典版本号（单调递增） |
| entries | JSONB | 完整词条快照（dict 序列化） |
| created_by | VARCHAR(100) | 创建者 |
| created_at | TIMESTAMPTZ | 创建时间 |
| change_summary | JSONB | 变更摘要 |

**乐观锁：** 词条 `version` + `UPDATE ... WHERE version = :expected`，rowcount==0 → 抛 `DictionaryVersionConflictError`

**回滚：** 读取目标版本快照 `entries` JSON → 重建词条表（先软删/清空再批量插入）→ 版本号递增

### 性能要求

| 指标 | 目标 | 验证方式 |
|------|------|---------|
| 词典热更新延迟 | P95<100ms | `reload_dictionary()` 计时单元测试 |
| 版本回滚延迟 | P95<200ms | `rollback()` 集成测试计时 |
| 核心战略概念覆盖率 | ≥95% | 预置词条集（BLM/BEM/SWOT/NPV/IRR/PESTEL/市场份额/AI 等）识别验证 |

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（端口与适配器）+ 领域数据管理
- **设计约束:**
  - 领域层零外部依赖（`DomainDictionaryPort` / `DictionaryConsumerPort` 仅使用 Python 标准库）
  - 依赖倒置：领域层定义 `DomainDictionaryPort`，基础设施层实现 `PostgreSQLDomainDictionaryRepository`
  - 热更新复用 Story 3.2b 的 `RuleBasedExtractor.reload_dictionary()`，仅追加 `DictionaryConsumerPort` 基类，不重写方法体
  - 事件发布复用 Story 1.2/1.3 的事件基础设施（RELIABLE 双通道）
- **技术栈:**
  - Python 3.11+
  - SQLAlchemy 2.0+（PG 持久化）
  - FastAPI 0.104+（REST API）
  - pyahocorasick（通过 RuleBasedExtractor 间接使用）

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) §17.1（数据处理架构）

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **PG 持久化 + 内存/自动机热更新** | 权威数据源持久化、回滚可靠、热更新复用现有方法 | 需迁移/快照表 | ✅ 8/10 |
| 纯内存词典（无持久化） | 实现最简单、热更新最快 | 重启丢失、无法版本管理、无审计 | 4/10 |
| Redis 词典为主存储 | 读取快、天然支持缓存 | 无强一致、回滚复杂、非权威源 | 6/10 |

**结论：** PostgreSQL 作为词典权威数据源（支持事务、快照、回滚、审计），热更新通过内存 AC 自动机重建实现。Redis 缓存可选，本 Story 不强制（MVP 聚焦核心能力）。

### 已有可复用组件

| 组件 | 文件路径 | 说明 |
|------|---------|------|
| RuleBasedExtractor | `src/infrastructure/external_services/entity_extraction/rule_extractor.py` | Story 3.2b 交付，含 `reload_dictionary()`；本 Story 追加实现 `DictionaryConsumerPort` |
| `_create_builtin_dictionary()` | 同上 | 内置战略词典（~100 词条），作为初始词典种子 |
| EntityExtractionPort | `src/domain/ports/entity_extraction.py` | Story 3.2b 端口（实体抽取能力，**不含** `reload_dictionary`） |
| **DictionaryConsumerPort** | `src/domain/ports/domain_dictionary.py` | **新建**：词典消费端热更新契约，`RuleBasedExtractor` 实现 |
| PostgreSQLAdapter | `src/infrastructure/storage/postgresql/repository/postgresql_adapter.py` | L2 仓储泛型基类，可继承遵循 CRUD 模式 |
| EventPublisher | `src/domain/ports/event_publisher.py` | 事件发布端口 |
| DomainEvent | `src/domain/events/base.py` | 事件基类 |
| session_context | `src/infrastructure/storage/postgresql/session_context.py` | ContextVar session 管理（仓储 flush 不 commit） |

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── ports/
│   │   │   ├── __init__.py                    # 更新：导出 DomainDictionaryPort + DictionaryConsumerPort + 值对象
│   │   │   └── domain_dictionary.py           # 新建：DomainDictionaryPort + DictionaryConsumerPort + DictionaryEntry/DictionaryQuery/DictionarySnapshot
│   │   ├── events/
│   │   │   ├── __init__.py                    # 更新：导出 DictionaryUpdated
│   │   │   └── dictionary_events.py           # 新建：DictionaryUpdated 事件
│   │   └── exceptions/
│   │       ├── __init__.py                    # 更新：导出词典异常
│   │       ├── _code_ranges.py                # 更新：新增 dictionary 子域 (270-279)
│   │       └── dictionary_exceptions.py       # 新建：词典异常
│   ├── application/
│   │   └── services/
│   │       └── domain_dictionary_service.py   # 新建：DomainDictionaryService 编排
│   ├── infrastructure/
│   │   └── storage/
│   │       └── postgresql/
│   │           └── repository/
│   │               ├── models/                # 更新/新建：词典 + 快照 SQLAlchemy Model
│   │               └── domain_dictionary_repository.py  # 新建：PostgreSQLDomainDictionaryRepository
│   ├── interfaces/
│   │   └── api/
│   │       ├── domain_dictionary.py           # 新建：Dictionary 路由
│   │       └── exception_handlers.py          # 更新：EXCEPTION_HTTP_MAP 新增词典异常
│   └── composition_root.py                    # 更新：注册 domain_dictionary_repo / domain_dictionary_service 端口
├── deploy/postgresql/alembic/versions/        # 新增：词典表 + 快照表 migration
├── configs/event_channels.yaml                # 更新：新增 DictionaryUpdated 事件通道
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── ports/
│   │   │   │   └── test_domain_dictionary_port.py    # 新建：端口 + 值对象测试
│   │   │   ├── events/
│   │   │   │   └── test_dictionary_events.py         # 新建：事件测试
│   │   │   └── exceptions/
│   │   │       └── test_dictionary_exceptions.py     # 新建：词典异常测试
│   │   ├── application/
│   │   │   └── services/
│   │   │       └── test_domain_dictionary_service.py # 新建：服务测试
│   │   ├── infrastructure/
│   │   │   └── storage/postgresql/repository/
│   │   │       └── test_domain_dictionary_repository.py # 新建：仓储测试
│   │   └── interface/api/
│   │       └── test_domain_dictionary_api.py         # 新建：路由测试
│   ├── contracts/
│   │   └── test_port_contract_domain_dictionary.py   # 新建：端口契约测试
│   ├── integration/
│   │   └── test_integration_domain_dictionary.py     # 新建：集成测试
│   └── acceptance/
│       ├── test_acceptance_domain_dictionary.feature # 新建：Gherkin 验收测试
│       └── test_acceptance_domain_dictionary.py      # 新建：BDD 步骤实现
```

### 环境变量设计

本 Story 无需新增环境变量。复用现有：
- `PostgreSQLConfig.from_env()` — PG 连接（仓储）
- 事件配置 — 复用 `event_publisher`

> **⚠️ 预存 Bug 提示（DictionaryUpdated 事件通道配置）：** `src/infrastructure/messaging/event_bus_config_loader.py` 第18行 `DEFAULT_CONFIG_PATH` 硬编码为 `"config" / "event_channels.yaml"`（单数 `config`），但项目实际路径为 `configs/event_channels.yaml`（复数 `configs`），且 `config/` 目录不存在。导致 `EventBusConfigLoader.load()` 因 `if not path.exists(): return` **静默返回，YAML 配置从未被加载**，系统仅依赖 `ChannelRouter.DEFAULT_MAPPINGS`。
>
> **对 DictionaryUpdated 的影响：** 本 Story 在 `DEFAULT_MAPPINGS` 中注册 `DictionaryUpdated` 即可保证事件通道可用（回退到 baseline），**功能不受影响**。但"配置驱动"机制（YAML 覆盖）实际失效。**建议实施时一并修复**：将 `DEFAULT_CONFIG_PATH` 的 `"config"` 改为 `"configs"`（一行字符串，成本极低），并同步修正 `CLAUDE.md` 第48/50行的 `config/event_channels.yaml` 引用为 `configs/event_channels.yaml`。此为 Story 3.3 之外但对 DictionaryUpdated 事件相关的预存问题，需在 Task 1 事件注册时记录决策。

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 3.2b: 实体抽取 LLM+规则](./3-2b-entity-extraction-llm-rules.md)

**关键学习/Key Learnings:**
1. **RuleBasedExtractor 已含热更新能力** — `reload_dictionary()` 方法已在 Story 3.2b 实现，本 Story 直接复用，不重写
2. **词典数据结构 = `list[tuple[str, str]]`** — `(词条, 实体类型)`，`get_active_dictionary()` 必须返回此格式以对接 `reload_dictionary()`
3. **异常编码注册流程** — 新异常必须遵循 `_code_ranges.py` → `__init__.py` → `EXCEPTION_HTTP_MAP` 完整流程
4. **端口契约测试"三方法"模式** — 注册验证、实现方法签名验证、元数据验证
5. **领域层零依赖** — 值对象（`DictionaryEntry` 等）仅使用 Python 标准库，禁止 pydantic
6. **事件发布失败不阻塞主流程** — Story 3.2b 的 `EntityExtractionService` 模式：事件发布失败仅记录日志，不抛出
7. **透明降级/容错理念** — 外部能力失败时保主流程，词典服务同样遵循

**应用到本故事/Applied to This Story:**
- [x] 复用 `RuleBasedExtractor.reload_dictionary()` 实现热更新，仅追加 `DictionaryConsumerPort` 基类，不改动方法体
- [x] `get_active_dictionary()` 返回 `list[tuple[str, str]]` 精确对接
- [x] 严格遵循异常编码注册流程（270/271/272）
- [x] 通过 `register_port()` 注册 `domain_dictionary_repo` / `domain_dictionary_service` 端口
- [x] 领域层值对象仅使用 Python 标准库
- [x] 事件发布失败时记录日志（不阻止主流程返回）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.2 (create-story workflow) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-08-10 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **异常设计** | `docs/architecture/sisys-uni-exception-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/3-2b-entity-extraction-llm-rules.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（FR-SR-03）
- [x] 架构约束从 `architecture.md` 提取
- [x] 前一个故事学习经验整合（Story 3.2b RuleBasedExtractor）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 已有可复用组件清单明确（RuleBasedExtractor/reload_dictionary）
- [x] 端口契约清单定义完成（2 个新端口）
- [x] 异常体系设计完成（dictionary 子域 270-272）
- [x] 领域事件设计完成（DictionaryUpdated）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-3-domain-dictionary-management.md`

**待创建的文件 (Dev Story 实施):**
- `src/domain/ports/domain_dictionary.py` — DomainDictionaryPort + DictionaryConsumerPort + 值对象
- `src/domain/events/dictionary_events.py` — DictionaryUpdated 事件
- `src/domain/exceptions/dictionary_exceptions.py` — 词典异常
- `src/application/services/domain_dictionary_service.py` — DomainDictionaryService
- `src/infrastructure/storage/postgresql/repository/domain_dictionary_repository.py` — PostgreSQLDomainDictionaryRepository
- `src/interfaces/api/domain_dictionary.py` — Dictionary 路由
- `deploy/postgresql/alembic/versions/` — 词典 + 快照表 migration
- `tests/unit/domain/ports/test_domain_dictionary_port.py`
- `tests/unit/domain/events/test_dictionary_events.py`
- `tests/unit/domain/exceptions/test_dictionary_exceptions.py`
- `tests/unit/application/services/test_domain_dictionary_service.py`
- `tests/unit/infrastructure/storage/postgresql/repository/test_domain_dictionary_repository.py`
- `tests/unit/interfaces/api/test_domain_dictionary_api.py`
- `tests/unit/architecture/test_arch_domain_dictionary.py`
- `tests/contracts/test_port_contract_domain_dictionary.py`
- `tests/integration/test_integration_domain_dictionary.py`
- `tests/acceptance/test_acceptance_domain_dictionary.feature`
- `tests/acceptance/test_acceptance_domain_dictionary.py`

**更新的文件/Updated Files:**
- `src/domain/ports/__init__.py` — 导出 DomainDictionaryPort + DictionaryConsumerPort + 值对象
- `src/domain/events/__init__.py` — 导出 DictionaryUpdated
- `src/domain/exceptions/__init__.py` — 导出词典异常
- `src/domain/exceptions/_code_ranges.py` — 新增 dictionary 子域 (270-279)
- `src/interfaces/api/exception_handlers.py` — EXCEPTION_HTTP_MAP 新增词典异常
- `src/infrastructure/messaging/channel_router.py` — DEFAULT_MAPPINGS 新增 DictionaryUpdated
- `configs/event_channels.yaml` — 新增 DictionaryUpdated 事件通道
- `src/composition_root.py` — 注册 domain_dictionary_repo / domain_dictionary_service 端口

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.3 |
| **Story Key** | 3-3-domain-dictionary-management |
| **File** | `_bmad-output/implementation-artifacts/stories/3-3-domain-dictionary-management.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | P1-3 |
| **覆盖 FR** | FR-SR-03（战略领域词典库管理） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（Story 3.2b）
5. [x] Sprint status synced to `ready-for-dev`

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

## 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | `EntityExtractionPort` 协议无 `reload_dictionary()`，但文档 AC-4/Subtask 2.1/2.2 让 `DomainDictionaryService` 注入 `EntityExtractionPort` 并调用 `reload_dictionary()`，违反六边形架构依赖倒置原则，且 mypy 报错、mock 无法构造 | P0 | 新建独立 `DictionaryConsumerPort` 协议（含 `reload_dictionary()`），`RuleBasedExtractor` 同时实现 `EntityExtractionPort` 与 `DictionaryConsumerPort`，`DomainDictionaryService` 注入 `DictionaryConsumerPort`。同步修正 AC-4、SDD 端口定义、Subtask 2.1/2.2、composition_root 注入、架构图、可复用组件清单、项目结构 |
| 2 | 文档中 `version` / `dictionary_version` 字段命名自相矛盾（AC-3 第84行 `version`、SDD 第186行 `version`、第193/816行 `dictionary_version`） | P0 | 统一为 `dictionary_version: int`（独立字段，不覆盖基类 `version`），同步修改 AC-3 验证标准、SDD 事件字段、Subtask 1.7/1.8 |
| 3 | 文档 Subtask 1.5 只提更新 `_code_ranges.py`，遗漏 `tests/unit/domain/exceptions/test_code_ranges.py` 的 `allowed_child_parent_subdomains` 需新增 `("dictionary", "business")`，否则 CI 的 `test_subclass_code_in_same_subdomain_as_parent` 会报"非法跨子域继承" | P0 | 在 Subtask 1.5 和 SDD 异常契约中明确补充更新 `test_code_ranges.py` 的 `allowed_child_parent_subdomains` |
| 4 | `entity_extraction_rule` 端口生命周期为 SCOPED，热更新语义要求词典全局共享，SCOPED 导致热更新跨请求不生效 | P1 | 明确将 `entity_extraction_rule` 生命周期改为 `Lifetime.SINGLETON`，并说明 `RuleBasedExtractor` 非线程安全的并发保护（`asyncio.Lock` 类变量或 copy-on-write） |
| 5 | DictionaryUpdated RELIABLE 模式未明确是否配置 `redis_channel` | P1 | 明确参照 `MemoryChanged`/`EntitiesExtracted` 模式，仅配置 `rabbitmq_routing_key`，不配置 `redis_channel` |
| 6 | 路由命名二选一"`document_dictionary`（或 `dictionary`）"不明确 | P1 | 统一为 `document_dictionary_router` / `create_document_dictionary_router()`，与 `document_upload_router` 命名对称 |
| 7 | "集成测试覆盖率 ≥70%" 对测试文件测覆盖率无意义，且与 `pyproject.toml` 的 `omit = ["*/tests/*"]` 冲突 | P1 | 删除对测试文件测覆盖率的条目，修正为仅对 `src` 测量（domain/application/infrastructure/interfaces 分层阈值） |

---

**故事版本/Story Version:** v1.2.0
**创建日期/Created:** 2026-08-10
**最后更新/Last Updated:** 2026-08-11
**更新说明/Description:**
- v1.2.0: Round 5 最终审查通过 — 文档质量达标，所有 P0/P1 问题已修复，适配器代码准备就绪
- v1.1.1: Round 2 修复 — 将 Subtask 2.4 真实 RuleBasedExtractor 热更新验证从单元测试移至集成测试 Subtask 4.5，避免与"单元测试 Mock 端口"规则语义冲突；更新测试分类表对应描述
- v1.1.0: Round 1 审查修复 — P0: 新增 DictionaryConsumerPort 端口契约修复六边形架构违规/统一 dictionary_version 字段名/补充 test_code_ranges.py 的 allowed_child_parent_subdomains；P1: 明确 entity_extraction_rule 生命周期为 SINGLETON/明确 event_channels 配置/统一路由命名/修正覆盖率门禁

<!-- 仅用作跟踪故事文件模板修订记录，故事开发时[务必删除]此段 -->
