# Story 3.11: 事实有效期标签管理

**Status:** `backlog`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 分析师,
**I want** 系统管理事实有效期标签（valid_from/valid_until）,
**So that** 支持时间轴演进的动态知识网络查询。

### 业务价值

本 Story 是 Epic 3（智能检索与知识发现）的**战略档案库增强 Story**，也是 **FR-SA-02（P0）** 的完整实现。它在 Story 3.10 战略档案库基础之上，为每个档案添加事实有效期标签管理能力，支持按时间轴查询历史决策。同时为 Story 3.12（数据陈旧标记）提供前置基础。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **有效期标签扩展** | 为战略档案添加 valid_from/valid_until 字段 | 有效期标签管理完整 |
| **时间轴查询** | 支持按时间范围查询历史决策 | 时间轴查询延迟 P95<200ms |
| **数据陈旧自动标记** | 超 12 个月数据自动标记"数据陈旧"并降权 | 标记准确率 100% |
| **有效期事件** | 有效期设置/过期事件，驱动下游同步 | 事件发布与消费正常 |
| **异常体系** | 有效期专属异常，与项目异常体系集成 | 编码唯一性验证 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 3: 智能检索与知识发现，Story 3.11

**前置依赖:**
- Story 3.10（战略档案库长期存储与归档 ✅ 已实现）— 提供 StrategicArchive 实体、ArchiveRepositoryPort、StrategicArchiveService 等基础组件

**后续依赖:**
- Story 3.12（数据陈旧标记）— 依赖本 Story 的有效期标签管理能力

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 有效期标签实体扩展

**Given** 战略档案实体已定义
**When** 为 StrategicArchive 添加有效期标签字段
**Then** 实体包含 valid_from（生效时间）和 valid_until（失效时间）字段
**And** 提供 is_valid()、is_expired()、days_until_expiry() 业务方法
**And** 领域层零外部依赖（仅 Python 标准库 + dataclasses）

**验证标准/Validation Criteria:**
- [ ] StrategicArchive 新增 `valid_from: datetime | None` 字段（默认 `None`，表示创建时生效）
- [ ] StrategicArchive 新增 `valid_until: datetime | None` 字段（默认 `None`，表示永久有效）
- [ ] `is_valid() -> bool` 方法 — 检查当前时间是否在有效期内（valid_from 为 None 时仅检查 valid_until，valid_until 为 None 时仅检查 valid_from，两者均为 None 时返回 True 视为永久有效）
- [ ] `is_expired() -> bool` 方法 — 检查是否已过期（now > valid_until，valid_until 为 None 时返回 False）
- [ ] `days_until_expiry() -> int | None` 方法 — 计算距离过期的天数（valid_until 为 None 时返回 None；已过期时返回负数，与 `ExternalAPIWhitelist.days_until_expiry()` 的负数行为一致；注意返回类型为 `int | None`，因 StrategicArchive 的 valid_until 可为 None，与 ExternalAPIWhitelist 的 `int` 返回类型不同）
- [ ] `validate()` 方法扩展 — 验证 valid_until 必须晚于或等于 valid_from（如果两者均非 None）
- [ ] 字段类型为 `datetime`（非 `date`），使用时区感知（UTC）；在 `is_valid()`/`is_expired()`/`days_until_expiry()` 中通过模块级可变变量 `_now` 获取当前时间，支持测试注入：
  ```python
  # 模块级：默认 datetime.now(UTC)，测试中可整体替换（方案 A）
  _now: Callable[[], datetime] = lambda: datetime.now(UTC)
  ```
  测试中通过 `strategic_archive._now = lambda: fixed_time` 整体替换实现时钟注入，配合 pytest fixture 的 `yield` + `finally` 自动恢复原值，避免污染其他测试（禁止使用 `mock.patch` 之外的硬编码修改且不恢复）
- [ ] 遵循 `ExternalAPIWhitelist` 的 `valid_from`/`valid_until` 模式（`src/domain/entities/external_api_whitelist.py`），但注意 StrategicArchive 的 valid_from/valid_until 为 `datetime | None`（非必填），而 ExternalAPIWhitelist 为 `datetime`（必填）

### AC-2: 有效期领域事件

**Given** 档案有效期被设置或过期
**When** 触发有效期相关事件
**Then** 事件携带档案标识和有效期信息
**And** 继承 DomainEvent 基类，遵循事件标准 Schema

**验证标准/Validation Criteria:**
- [ ] `ValidityPeriodSet` 事件（`src/domain/events/archive_events.py`）— 有效期设置时发布
  - 字段：`archive_id: UUID`（必填，无默认值）、`plan_id: UUID | None`、`archive_type: ArchiveType`、`valid_from: datetime | None`、`valid_until: datetime | None`
  - `event_type: str = "ValidityPeriodSet"`（`field(default="ValidityPeriodSet", init=False)`）
  - 通过 `__post_init__` 无条件设置 `aggregate_id = archive_id` 与 `aggregate_type = "StrategicArchive"`（archive_id 为必填参数，aggregate_id 恒为 None，条件判断分支恒为 True；采用 **无条件赋值** 与 ArchiveCreated 的条件写法结果等价，但语义更清晰——domain event 事件携带的聚合标识必须是实际档案 ID，不允许为空）
  - 通道：RabbitMQ + Outbox（RELIABLE 模式）
- [ ] `FactBecameStale` 事件（`src/domain/events/archive_events.py`）— 事实变为陈旧时发布
  - 字段：`archive_id: UUID`（必填，无默认值）、`plan_id: UUID | None`、`archive_type: ArchiveType`、`valid_until: datetime | None`（基于 archived_at 标记陈旧时为 None）、`stale_since: datetime`（标记为陈旧的时间，`field(default_factory=lambda: datetime.now(UTC))`）、`stale_reason: str`（陈旧原因，取值 `"expired"` 表示 valid_until 过期，`"archived_too_long"` 表示归档超 12 个月自动陈旧，用于消费方区分陈旧原因以决定降权策略）
  - `event_type: str = "FactBecameStale"`
  - 通过 `__post_init__` 设置 `aggregate_id = archive_id` 与 `aggregate_type = "StrategicArchive"`（与 ArchiveCreated 一致的赋值逻辑）
  - 通道：RabbitMQ + Outbox（RELIABLE 模式）
- [ ] 两事件注册于 `src/domain/events/__init__.py`、`configs/event_channels.yaml`、`ChannelRouter.DEFAULT_MAPPINGS`（参见下方"环境变量与配置"章节的完整配置模板）

### AC-3: 有效期异常体系

**Given** 有效期管理过程中可能发生错误
**When** 定义有效期异常类
**Then** 继承 BusinessException 层次结构
**And** 分配唯一异常编码（archive 子域 282-289 范围内，使用可用编码 285/286）

**验证标准/Validation Criteria:**
- [ ] `ValidityPeriodConflictError`（EXCEPTION_285）— 继承 `ConflictError`，有效期冲突（同一 `plan_id` + 同一 `archive_type` 下，与其他档案的有效期区间存在重叠）
  - 构造参数：`archive_id: UUID`、`message: str | None = None`、`cause: Exception | None = None`
  - `message` 默认构造：`f"Validity period conflict for archive: {archive_id}"`
  - `context` 暴露 `archive_id`（`context={"archive_id": str(archive_id)}`）
- [ ] 编码在 `_code_ranges.py` 注册，`grep -r "EXCEPTION_285"` 验证无碰撞
- [ ] 异常在 `_CLASS_TO_SUBDOMAIN` 注册子域 `"archive"`
- [ ] 异常在 `__init__.py` 导出，在 `EXCEPTION_HTTP_MAP` 注册（409）
- [ ] 测试覆盖：构造/`to_dict()`/HTTP 映射/编码唯一性

> **触发规则（冲突判定）：** `set_validity_period()` 在更新前需查询同一 `plan_id`、同一 `archive_type`、不同 `archive_id` 的既有档案，若新区间 `[valid_from, valid_until)`（半开区间，None 视为开区间端点，即 valid_from=None 表示"从无限早开始"，valid_until=None 表示"直到无限远"）与任一既有区间存在交集，则抛出 `ValidityPeriodConflictError`。**半开区间规则**：区间包含 valid_from 端点、不包含 valid_until 端点；端点相接不视为冲突（档案 A 的 valid_until == 档案 B 的 valid_from 时，两者自然衔接，允许共存）。该判定在应用服务层完成（复用 `archive_repo.find()` 按 plan_id+archive_type 查询后内存比较）。
>
> > **并发安全（P0 强制）：** 应用层内存比较存在 TOCTOU 竞态，必须采用三层防御策略：
> > 1. **（强制）PostgreSQL EXCLUDE 约束**：使用 `btree_gist` 扩展 + `EXCLUDE USING gist (plan_id WITH =, archive_type WITH =, tstzrange(COALESCE(valid_from, '-infinity'::timestamptz), COALESCE(valid_until, 'infinity'::timestamptz), '[)') WITH &&)`，数据库层面强制区间不重叠。违反时抛出 `exclusion_violation`，应用层捕获后转为 `ValidityPeriodConflictError`。
> > 2. **（强制）SELECT FOR UPDATE 悲观锁**：冲突检测查询使用 `SELECT ... FOR UPDATE` 锁定同一 `plan_id+archive_type` 的所有相关行，防止并发读取。需在 `ArchiveRepositoryPort` 中新增 `find_for_update(query)` 方法或在 `find` 中增加可选锁参数。
> > 3. **（建议）应用层内存比较**：作为第一道防线，快速失败减少不必要的数据库操作。

### AC-4: ArchiveQuery 扩展（时间轴查询）

**Given** 需要按有效期查询档案
**When** 扩展 ArchiveQuery 值对象
**Then** 支持按 valid_from/valid_until 时间范围过滤
**And** 支持按 is_valid（当前有效）/is_expired（已过期）状态过滤

**验证标准/Validation Criteria:**
- [ ] ArchiveQuery 新增 `valid_from: datetime | None = None` 字段 — 按 valid_from 范围过滤（>= valid_from）
- [ ] ArchiveQuery 新增 `valid_until: datetime | None = None` 字段 — 按 valid_until 范围过滤（<= valid_until）
- [ ] ArchiveQuery 新增 `validity_status: ValidityStatus | None = None` 字段 — 按有效期状态过滤（使用 `ValidityStatus` 枚举：`VALID="valid"`/`EXPIRED="expired"`，默认 `None` 表示不过滤；不设 `ALL` 枚举值，因 `None` 本身已表达"不按有效期过滤"的语义，避免语义重复）
- [ ] 新增 `ValidityStatus` 枚举（`class ValidityStatus(str, Enum)`），定义在 `src/domain/ports/archive_repository.py` 中（作为查询过滤参数，与 `ArchiveQuery` 同文件；注意 `ArchiveType` 定义在实体层，`ValidityStatus` 定义在端口层，两者定位不同，但枚举定义模式一致）
- [ ] `__post_init__` 验证 `validity_status` 取值必须为 `ValidityStatus` 枚举成员或 None
- [ ] 向后兼容：所有新增字段均为可选，默认 None，不影响现有查询

### AC-5: 应用层有效期管理服务

**Given** 战略档案服务已存在
**When** 扩展 StrategicArchiveService 或新建有效期管理服务
**Then** 提供有效期设置、查询、陈旧检测能力
**And** 支持超 12 个月自动标记陈旧

**验证标准/Validation Criteria:**
- [ ] `set_validity_period(archive_id, valid_from, valid_until) -> StrategicArchive` 方法 — 设置档案有效期
  - 调用 `archive_repo.get_by_id()` 获取档案
  - 若档案不存在，抛出 `ArchiveNotFoundError`
  - 更新档案的 `valid_from`/`valid_until` 字段
  - 调用 `archive.validate()` 验证 `valid_from <= valid_until`（若两者均非 None），防止无效数据写入
  - **冲突检测**：查询同一 `plan_id` + 同一 `archive_type` 下、不同 `archive_id` 的档案，检查新区间与既有区间是否存在重叠（None 视为开区间端点）。若存在重叠，抛出 `ValidityPeriodConflictError`
  - **并发安全**：冲突检测使用 `archive_repo.find_for_update()`（SELECT FOR UPDATE 悲观锁）锁定同一 plan_id+archive_type 下的相关档案，防止 TOCTOU 竞态；数据库层通过 EXCLUDE 约束兜底强制执行区间不重叠
  - 调用 `archive_repo.save()` 持久化
  - 发布 `ValidityPeriodSet` 事件
- [ ] 复用现有 `query_archive(query: ArchiveQuery) -> list[StrategicArchive]` 方法 — 按有效期查询（通过 ArchiveQuery 新增的 `valid_from`/`valid_until`/`validity_status` 字段自然支持，无需新增方法）
- [ ] `is_stale(archive_id: UUID) -> bool` 方法 — 检查单个档案是否陈旧（**委托实体方法 `StrategicArchive.is_stale()`，统一陈旧判定标准**；命名采用 `is_` 前缀，与 `is_valid()`/`is_expired()` 保持一致）
  - 获取档案后调用 `archive.is_stale()`，实体内部判断：
    - `valid_until` 非 None：`valid_until < now` → 陈旧
    - `valid_until` 为 None 且 `archived_at` 非 None：`archived_at < now - 12个月` → 陈旧
    - 两者均为 None：返回 False（"未设置有效期"，该状态在 Story 3.12 处理）
- [ ] `mark_stale_archives(batch_size: int = 100) -> list[StrategicArchive]` 方法 — 批量标记陈旧档案（**幂等设计**）
  - 应用层循环调用 `archive_repo.find()` 并配合 `offset`/`limit` 实现分批查询（batch_size 映射为 limit 参数），每次查询一批后处理并发布事件，再查下一批
  - 逐批处理：查询所有 valid_until < now（或 valid_until IS NULL AND archived_at < now - 12个月）**且 `metadata->>'staleness' IS DISTINCT FROM 'stale'`（排除已标记档案，保证幂等）** 的档案
  - 仅对首次标记的档案写入 `metadata` 字典 `{"staleness": "stale", "stale_since": <isoformat>}`（已标记档案跳过 stale_since 覆盖）
  - 发布 `FactBecameStale` 事件（每个档案一个事件，事件携带 `stale_reason` 区分陈旧原因）
  - 返回被标记为陈旧的档案列表
- [ ] 有效期设置方法在 L2 失败时抛出 `ArchiveStorageError(layer="l2")`
- [ ] 有效期设置方法在有效期冲突时抛出 `ValidityPeriodConflictError`

### AC-6: 基础设施层有效期查询扩展

**Given** ArchiveRepositoryPort 已实现
**When** 扩展 PostgreSQLArchiveRepository
**Then** 支持按有效期字段过滤查询
**And** 支持 validity_status 状态过滤

**验证标准/Validation Criteria:**
- [ ] `_apply_filters()` 方法扩展 — 支持 `valid_from`、`valid_until`、`validity_status` 过滤
  - `valid_from`：`ArchiveModel.valid_from >= query.valid_from`
  - `valid_until`：`ArchiveModel.valid_until <= query.valid_until`
  - `validity_status="valid"`：`(ArchiveModel.valid_from IS NULL OR ArchiveModel.valid_from <= now)` AND `(ArchiveModel.valid_until >= now OR ArchiveModel.valid_until IS NULL)` — **注意 NULL 安全处理**，确保已有档案（valid_from=NULL）被正确包含
  - `validity_status="expired"`：`ArchiveModel.valid_until < now`
- [ ] 新增的过滤条件与现有 plan_id/archive_type/plan_type/start_date/end_date 组合兼容
- [ ] 扩展 `ArchiveModel` 添加 `valid_from` 和 `valid_until` 列（方案 A：显式列，已决策通过）
- [ ] `_to_entity()` 和 `_to_model()` 转换方法同步更新，新增 valid_from/valid_until 字段映射（`src/infrastructure/storage/postgresql/repository/archive_repository.py`）
- [ ] **新增 `find_for_update(query)` 方法** — 用于冲突检测的悲观锁查询（`SELECT ... FOR UPDATE`），锁定同一 `plan_id+archive_type` 的所有相关行，防止 TOCTOU 竞态

### AC-7: 有效期变更事件处理

**Given** 有效期事件已定义
**When** 事件处理器接收到有效期事件
**Then** 执行相应的下游处理逻辑

**验证标准/Validation Criteria:**
- [ ] `ValidityPeriodSet` 事件处理器（`src/application/event_handlers/archive_handlers.py`）
  - 收到事件后，记录日志
  - 后续可扩展为触发缓存失效、通知下游等
  - 预留 L3/L5 同步钩子（TODO: Story 3.12 - sync valid_from/valid_until to L3/L5 payload）
- [ ] `FactBecameStale` 事件处理器（`src/application/event_handlers/archive_handlers.py`）
  - 收到事件后，记录日志
  - 后续可扩展为触发降权处理、通知前端等
- [ ] 事件处理器遵循 `InMemoryEventListener.on_event()` + `register_handlers()` 模式注册：
  - Handler 类构造函数注入 `event_listener: EventListener` 端口
  - 在 `register_handlers()` 方法中调用 `self._event_listener.on_event("EventType", handler_callback)`
  - 回调函数签名遵循 `Callable[[DomainEvent], None]` 约束
  - 异步处理逻辑通过 `_wrap_handler()` 模式包装为同步回调（参照 `DocumentVersionHandler` 实现）
- [ ] 在 `composition_root.py` 的 `handler_names` 列表中注册新处理器（如 `"archive_validity_handler"`）
- [ ] 事件处理器在 `src/application/event_handlers/__init__.py` 中导出

### AC-8: 接口层有效期管理 API

**Given** 档案管理 API 已存在
**When** 扩展有效期管理 API
**Then** 提供有效期设置、查询接口
**And** 所有接口过认证中间件，遵循统一错误响应

**验证标准/Validation Criteria:**
- [ ] `PUT /api/v1/archive/entries/{archive_id}/validity-period` — 设置档案有效期
  - 请求体 Pydantic Schema：`ValidityRequest(BaseModel)` — 包含 `valid_from: datetime | None = None`、`valid_until: datetime | None = None`
  - 响应 200：更新后的档案详情（`ArchiveResponse` 新增 `valid_from`、`valid_until` 字段）
  - 响应 404：档案不存在
  - 响应 409：有效期冲突
- [ ] `GET /api/v1/archive/entries` 扩展查询参数 — 支持 `valid_from`、`valid_until`、`validity_status` 过滤
  - 与现有 `plan_id`、`archive_type`、`plan_type` 参数组合使用（注：现有路由未暴露 `start_date`/`end_date` 查询参数，此处不新增）
  - 向后兼容：不传参时行为不变
- [ ] `POST /api/v1/archive/staleness/check` — 手动触发陈旧标记检查
  - 响应 Pydantic Schema：`StalenessCheckResponse(BaseModel)` — 包含 `marked: list[str]`、`count: int`
  - 返回 200 + 标记结果列表
- [ ] 请求/响应 Schema 使用 Pydantic，定义于路由同文件或共享 Schema 模块
- [ ] `ArchiveResponse` 新增 `valid_from: str | None = None`、`valid_until: str | None = None` 字段，`_to_archive_response()` 中通过 `.isoformat()` 转换（与 `created_at`/`archived_at` 的转换方式一致）
- [ ] 查询延迟 P95<200ms（通过索引保障，性能验证见 `tests/unit/performance/test_perf_archive_validity.py`；测试数据量级≥10,000 条档案记录，连续执行 100 次查询取 P95 百分位，执行 10 次预热后开始测量；CI 环境下默认跳过，本地开发手动触发；对齐项目现有 `test_compression_performance.py` 先例）

### AC-9: 端口注册与 DI 集成

**Given** 所有组件实现完成
**When** 在 composition_root.py 注册
**Then** 新端口注册为 SCOPED
**And** 通过 Resolver 可正确解析
**And** 端口契约测试通过

**验证标准/Validation Criteria:**
- [ ] `composition_root.py` 注册（如有新端口）
- [ ] 端口契约测试通过
- [ ] 所有新增组件在 `__init__.py` 导出

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

**新增事件（在 `src/domain/events/archive_events.py` 中追加）：**
- [ ] `ValidityPeriodSet`（`@dataclass(frozen=True)`）
  - 继承 `DomainEvent`
  - 字段: `archive_id: uuid.UUID`（必填，无默认值 — 有效期事件须由调用方显式传入）
  - `plan_id: uuid.UUID | None = None`
  - `archive_type: ArchiveType = ArchiveType.ASSUMPTION`
  - `valid_from: datetime | None = None`
  - `valid_until: datetime | None = None`
  - `event_type: str = field(default="ValidityPeriodSet", init=False)`
  - `__post_init__` 设置 `aggregate_id = self.archive_id`（无条件赋值，archive_id 必填故恒非空）和 `aggregate_type = "StrategicArchive"`（无条件赋值）
  - Schema 版本: v1.0.0
  - 通道: RabbitMQ + Outbox（RELIABLE 模式）

- [ ] `FactBecameStale`（`@dataclass(frozen=True)`）
  - 继承 `DomainEvent`
  - 字段: `archive_id: uuid.UUID`（必填，无默认值 — 有效期事件须由调用方显式传入）
  - `plan_id: uuid.UUID | None = None`
  - `archive_type: ArchiveType = ArchiveType.ASSUMPTION`
  - `valid_until: datetime | None = None`（基于 `archived_at` 标记陈旧时为 None，与实体字段类型一致）
  - `stale_since: datetime`（标记为陈旧的时间，`field(default_factory=lambda: datetime.now(UTC))`）
  - `stale_reason: str`（陈旧原因，取值 `"expired"` 表示 valid_until 过期，`"archived_too_long"` 表示归档超 12 个月自动陈旧，用于消费方区分陈旧原因以决定降权策略）
  - `event_type: str = field(default="FactBecameStale", init=False)`
  - `__post_init__` 设置 `aggregate_id = self.archive_id`（无条件赋值，archive_id 必填故恒非空）和 `aggregate_type = "StrategicArchive"`（无条件赋值）
  - Schema 版本: v1.0.0
  - 通道: RabbitMQ + Outbox（RELIABLE 模式）

#### 数据模型 (Data Models)

**扩展实体（修改 `src/domain/entities/strategic_archive.py`）：**

`StrategicArchive` 新增字段：
- [ ] `valid_from: datetime | None = None` — 生效时间（None 表示创建时生效）
- [ ] `valid_until: datetime | None = None` — 失效时间（None 表示永久有效）

新增方法：
- [ ] `is_valid() -> bool` — 检查当前时间是否在有效期内
  ```python
  def is_valid(self) -> bool:
      now = _now()
      if self.valid_from is not None and self.valid_from > now:
          return False
      if self.valid_until is not None and self.valid_until < now:
          return False
      return True
  ```
  （`_now()` 为模块级函数，默认 `lambda: datetime.now(UTC)`，测试可注入固定时间）
- [ ] `is_expired() -> bool` — 检查是否已过期
  ```python
  def is_expired(self) -> bool:
      if self.valid_until is None:
          return False
      return _now() > self.valid_until
  ```
- [ ] `days_until_expiry() -> int | None` — 计算距离过期的天数（当日不足 24h 的部分向下取整；已过期返回负数）
  ```python
  def days_until_expiry(self) -> int | None:
      if self.valid_until is None:
          return None
      delta = self.valid_until - _now()
      return delta.days
  ```

`validate()` 方法扩展：
- [ ] 新增验证：如果 `valid_from` 和 `valid_until` 均非 None，则 `valid_from <= valid_until`

新增陈旧判断方法（与 `is_valid()`/`is_expired()` 并列，统一陈旧判定标准）：
- [ ] `is_stale(ref_date: datetime | None = None) -> bool` — 检查实体是否陈旧
  ```python
  def is_stale(self, ref_date: datetime | None = None) -> bool:
      now = ref_date or _now()
      if self.valid_until is not None:
          return self.valid_until < now
      if self.archived_at is not None:
          return self.archived_at < now - timedelta(days=365)
      return False  # 两者均为 None，不标记
  ```
  （`is_stale()` 是实体方法，与应用层服务方法 `is_stale(archive_id)` 委托调用关系：服务方法获取实体后调用 `archive.is_stale()`）

**扩展值对象（修改 `src/domain/ports/archive_repository.py`）：**

`ArchiveQuery` 新增字段：
- [ ] `valid_from: datetime | None = None` — 按 valid_from 范围过滤（>= valid_from）
- [ ] `valid_until: datetime | None = None` — 按 valid_until 范围过滤（<= valid_until）
- [ ] ArchiveQuery 新增 `validity_status: ValidityStatus | None = None` 字段 — 有效期状态过滤（使用 `ValidityStatus` 枚举：`VALID="valid"`/`EXPIRED="expired"`；不设 `ALL`，因 `None` 已表达"不过滤"语义）

`__post_init__` 扩展：
- [ ] 验证 `validity_status` 取值必须为 `ValidityStatus` 枚举成员或 None
- [ ] 新增 `ValidityStatus` 枚举定义（`class ValidityStatus(str, Enum)` 含 `VALID="valid"`/`EXPIRED="expired"`，不设 `ALL`），放在 `src/domain/ports/archive_repository.py` 中，与 `ArchiveQuery` 同文件

**扩展 SQLAlchemy 模型（修改 `src/infrastructure/storage/postgresql/models/archive.py`）：**

`ArchiveModel` 新增字段（方案 A：显式列，已决策通过）：
- [ ] 方案 A：新增 `valid_from` 和 `valid_until` 列
  ```python
  valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  ```

> **架构决策：** 采用方案 A（显式列）。原因：
> 1. `valid_from`/`valid_until` 是核心业务字段，频繁用于时间轴查询过滤
> 2. 显式列可创建索引，保障时间轴查询 P95<200ms 的性能要求
> 3. 与 `ExternalAPIWhitelist` 实体的 `valid_from`/`valid_until` 显式字段模式一致
> 4. `metadata` 字段保留给 Story 3.12 的陈旧标记扩展使用
>
> **备选方案 B（不采用）：** 通过 `metadata_` JSONB 字段存储（`metadata_["valid_from"]`、`metadata_["valid_until"]`）— 查询性能差、类型不安全、无法索引，已排除。

#### 统一端口定义注册与管理 (Port Contract)

**扩展端口（修改 `src/domain/ports/archive_repository.py`）：**
- [ ] `ArchiveRepositoryPort` 无新增方法签名，但 `ArchiveQuery` 值对象扩展了过滤字段
- [ ] 端口契约测试需更新以验证新的 ArchiveQuery 字段

**端口契约清单执行约束（强制）：**
- [ ] 端口清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

**新增异常（在 `src/domain/exceptions/archive_exceptions.py` 中追加）：**
- [ ] `ValidityPeriodConflictError`（EXCEPTION_285）
  - 继承 `ConflictError`，有效期冲突
  - 构造参数：`archive_id: UUID`，`message: str | None = None`，`cause: Exception | None = None`
  - `message` 默认构造：`f"Validity period conflict for archive: {archive_id}"`
  - `context` 暴露 `archive_id`（`context={"archive_id": str(archive_id)}`）

**编码分配：**
| 异常类 | 编码 | 继承 | 描述 |
|--------|------|------|------|
| ValidityPeriodConflictError | EXCEPTION_285 | ConflictError | 有效期冲突 |

**注册事项：**
- [ ] `_code_ranges.py` 的 `_CLASS_TO_SUBDOMAIN` 注册 `"ValidityPeriodConflictError": "archive"`
- [ ] `src/domain/exceptions/__init__.py` 导出
- [ ] `EXCEPTION_HTTP_MAP` 注册：`ValidityPeriodConflictError: 409`

#### API 契约 (API Contract)

- [ ] `PUT /api/v1/archive/entries/{archive_id}/validity-period` — 设置有效期
  - 请求体：`{ "valid_from": "2026-01-01T00:00:00Z" | null, "valid_until": "2027-01-01T00:00:00Z" | null }`
  - 响应 200：更新后的档案详情（`ArchiveResponse` 新增 `valid_from`、`valid_until` 字段，字段值使用 `.isoformat()` 转换为 ISO 字符串，与 `created_at`/`archived_at` 的转换方式一致）
  - 响应 404：档案不存在
  - 响应 409：有效期冲突
- [ ] `GET /api/v1/archive/entries` 扩展参数
  - 新增可选查询参数：`valid_from`、`valid_until`、`validity_status`
  - 向后兼容：不传参时行为不变
- [ ] `POST /api/v1/archive/staleness/check` — 手动触发陈旧标记检查
  - 响应 200：`{ "marked": [archive_id, ...], "count": N }`
- [ ] API 契约测试通过（`tests/contracts/test_api_contract_archive_validity.py`）

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
- `tests/acceptance/test_acceptance_archive_validity.feature`
- `tests/acceptance/test_acceptance_archive_validity.py`

**必须覆盖的场景：**
- Happy Path: 设置档案有效期标签（valid_from/valid_until），验证有效期查询
- 时间轴查询: 按时间范围查询历史决策档案，返回有效期标签信息
- 数据陈旧标记: 超 12 个月数据自动标记"数据陈旧"并降权
- 有效期查询: 按有效/过期状态过滤档案
- 事件验证: `ValidityPeriodSet` 和 `FactBecameStale` 事件被正确发布
- Edge Cases（含异常路径）: 永久有效（valid_until=None）、立即过期（valid_from=valid_until）、无效有效期（valid_from>valid_until）、档案不存在（404）、有效期冲突（409）

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
| **TDD 单元测试** | StrategicArchive 实体扩展 | valid_from/valid_until/is_valid/is_expired/days_until_expiry | `test_archive_entity.py` | Task 1 |
| **TDD 单元测试** | 有效期事件 | ValidityPeriodSet/FactBecameStale 构造/序列化/反序列化 | `test_archive_events.py` | Task 2 |
| **TDD 单元测试** | 有效期异常 | ValidityPeriodConflictError 构造/to_dict/HTTP 映射 | `test_archive_exceptions.py` | Task 2 |
| **TDD 单元测试** | ArchiveQuery 扩展 | valid_from/valid_until/validity_status 字段 + ValidityStatus 枚举 | `test_archive_query.py` | Task 0 |
| **TDD 单元测试** | StrategicArchiveService 扩展 | set_validity_period/is_stale/mark_stale | `test_strategic_archive_service.py` | Task 3 |
| **TDD 单元测试** | 事件处理器 | ValidityPeriodSet/FactBecameStale 事件处理逻辑 | `test_archive_handlers.py` | Task 3 |
| **TDD 单元测试** | PostgreSQLArchiveRepository 扩展 | 有效期过滤/状态过滤查询 | `test_archive_repository.py` | Task 4 |
| **TDD 单元测试** | 接口层 API 路由 | PUT validity/GET 扩展参数/POST staleness-check | `test_archive_routes.py` | Task 5 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_archive_validity.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_archive_validity.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单确认 | `test_acceptance_archive_validity.feature` | Task 6 |
| **TDD 契约测试** | 端口契约 | 端口注册/版本/兼容性/解析 | `test_port_contract_strategic_archive.py` | Task 0 |
| **TDD 契约测试** | API 契约 | 请求/响应结构/状态码 | `test_api_contract_archive_validity.py` | Task 0 |
| **TDD 单元测试** | 编码唯一性 | 异常 code 无碰撞 | `test_error_code_uniqueness.py` | Task 2 |
| **TDD 单元测试** | 编码子域范围 | 子域范围/继承链一致性 | `test_code_ranges.py` | Task 2 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向/零依赖 | `test_arch_archive_validity.py` | Task 5 |
| **SDD 性能验证** | 有效期查询性能 | P95<200ms（时间轴查询延迟，≥10,000 条记录，100 次迭代取 P95，10 次预热后测量，CI 默认跳过） | `test_perf_archive_validity.py` | Task 5 |
| **集成测试** | 有效期管理集成 | 有效期设置+查询+陈旧标记 | `test_integration_archive_validity.py` | Task 3 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）
- [ ] **领域层覆盖率 ≥90%**
- [ ] **应用层覆盖率 ≥85%**
- [ ] **接口层覆盖率 ≥85%**
- [ ] **基础设施层覆盖率 ≥75%**
- [ ] 集成测试覆盖率建议 ≥70%（通过 `pytest tests/integration/ --cov=src --cov-report=term-missing` 单独测量；不作为 CI 门禁，仅作为开发者自检参考）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **事务隔离** | 集成测试使用 transaction rollback | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内通过 `Base.metadata.create_all()` 完成 Schema 初始化（与现有集成测试模式一致） | 依赖外部迁移，环境不一致 |
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
| AC-1 | 有效期标签实体扩展 | Task 0 | SDD 规范定义 | `test_archive_entity.py` |
| AC-1 | 有效期标签实体扩展 | Task 1 | TDD 实体实现 | `test_archive_entity.py` |
| AC-2 | 有效期领域事件 | Task 0 | SDD 规范定义（事件 Schema） | `test_archive_events.py` |
| AC-2 | 有效期领域事件 | Task 2 | TDD 事件实现 | `test_archive_events.py` |
| AC-3 | 有效期异常体系 | Task 0 | SDD 规范定义（异常契约） | `test_archive_exceptions.py` |
| AC-3 | 有效期异常体系 | Task 2 | TDD 异常实现 | `test_archive_exceptions.py` |
| AC-4 | ArchiveQuery 扩展 | Task 0 | SDD 规范定义（ValidityStatus 枚举） | `test_archive_query.py` |
| AC-4 | ArchiveQuery 扩展 | Task 4 | TDD 仓储实现 | `test_archive_repository.py` |
| AC-5 | 应用层有效期管理服务 | Task 0 | SDD 规范定义 | `test_strategic_archive_service.py` |
| AC-5 | 应用层有效期管理服务 | Task 3 | TDD 服务实现 | `test_strategic_archive_service.py` |
| AC-6 | 基础设施层有效期查询扩展 | Task 0 | SDD 规范定义（数据模型） | `test_archive_repository.py` |
| AC-6 | 基础设施层有效期查询扩展 | Task 4 | TDD 仓储实现 + Alembic | `test_archive_repository.py` |
| AC-7 | 有效期变更事件处理 | Task 0 | SDD 规范定义 | `test_archive_handlers.py` |
| AC-7 | 有效期变更事件处理 | Task 3 | TDD 事件处理器实现 | `test_archive_handlers.py` |
| AC-8 | 接口层有效期管理 API | Task 0 | SDD 规范定义（API 契约） | `test_api_contract_archive_validity.py` |
| AC-8 | 接口层有效期管理 API | Task 5 | TDD API 路由实现 | `test_archive_routes.py` |
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

- [ ] Subtask 0.1: 扩展 `StrategicArchive` 实体 Schema — 新增 valid_from/valid_until 字段及业务方法
- [ ] Subtask 0.2: 扩展 `ArchiveQuery` 值对象 — 新增 valid_from/valid_until/validity_status 字段 + ValidityStatus 枚举（同时新增 `tests/unit/domain/ports/test_archive_query.py` 单元测试）
- [ ] Subtask 0.3: 定义 `ValidityPeriodConflictError` 异常契约（EXCEPTION_285）
- [ ] Subtask 0.4: 定义 `ValidityPeriodSet` / `FactBecameStale` 事件 Schema
- [ ] Subtask 0.5: 扩展 `ArchiveModel` SQLAlchemy 模型 — 新增 valid_from/valid_until 列
- [ ] Subtask 0.6: 定义有效期 API 契约（PUT validity-period / GET 扩展参数 / POST staleness-check）
- [ ] Subtask 0.7: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_archive_validity.feature`
- [ ] Subtask 0.8: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_archive_validity.py`
- [ ] Subtask 0.9: 运行验收测试，确认失败（🔴 红阶段验证）
- [ ] Subtask 0.10: 编写端口契约测试 `tests/contracts/test_port_contract_strategic_archive.py`（更新）
- [ ] Subtask 0.11: 编写 API 契约测试 `tests/contracts/test_api_contract_archive_validity.py`
- [ ] Subtask 0.12: 编写 ArchiveQuery 单元测试 `tests/unit/domain/ports/test_archive_query.py`（与端口契约测试分离，纯领域层值对象验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）
- [ ] 端口契约测试运行失败（预期行为，红阶段确认）

---

### Task 1: StrategicArchive 实体有效期扩展

**关联 AC:** AC-1

#### TDD 循环 A: StrategicArchive 实体有效期扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/domain/entities/test_archive_entity.py`（valid_from/valid_until/is_valid/is_expired/days_until_expiry/validate 扩展） |
| 🟢 绿 | 扩展 `StrategicArchive` dataclass — 新增 valid_from/valid_until 字段及业务方法 |
| 🔄 重构 | 添加类型注解、docstring、运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写实体有效期扩展失败测试
- [ ] Subtask 1.2: 🟢 绿 — 扩展 `StrategicArchive` 实体
- [ ] Subtask 1.3: 🔄 重构 — 优化实体代码

**完成标准/Definition of Done:**
- [ ] `StrategicArchive` 有效期字段实现完成
- [ ] `is_valid()` / `is_expired()` / `days_until_expiry()` 方法验证通过
- [ ] `validate()` 扩展验证通过
- [ ] TDD 循环全部通过

---

### Task 2: 有效期异常 + 有效期领域事件

**关联 AC:** AC-2, AC-3

#### TDD 循环 A: 有效期异常

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/domain/exceptions/test_archive_exceptions.py`（ValidityPeriodConflictError 构造/属性/to_dict()） |
| 🟢 绿 | 实现 `ValidityPeriodConflictError`（EXCEPTION_285） |
| 🔄 重构 | 注册到 `_code_ranges.py` + `EXCEPTION_HTTP_MAP` + `__init__.py` |

- [ ] Subtask 2.1: 🔴 红 — 编写有效期异常失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 `ValidityPeriodConflictError`
- [ ] Subtask 2.3: 🔄 重构 — 注册异常到 `_code_ranges.py`、`EXCEPTION_HTTP_MAP`、`__init__.py`

#### TDD 循环 B: ValidityPeriodSet / FactBecameStale 领域事件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/domain/events/test_archive_events.py`（ValidityPeriodSet/FactBecameStale 构造/序列化/反序列化） |
| 🟢 绿 | 实现 `ValidityPeriodSet` 和 `FactBecameStale` 事件 |
| 🔄 重构 | 注册到 `__init__.py`、`event_channels.yaml`、`ChannelRouter.DEFAULT_MAPPINGS` |

- [ ] Subtask 2.4: 🔴 红 — 编写有效期事件失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 `ValidityPeriodSet` 和 `FactBecameStale` 事件
- [ ] Subtask 2.6: 🔄 重构 — 注册事件通道

**完成标准/Definition of Done:**
- [ ] `ValidityPeriodConflictError` 实现完成，编码唯一性验证通过
- [ ] `ValidityPeriodSet` 和 `FactBecameStale` 事件实现完成
- [ ] 所有 TDD 循环测试通过

---

### Task 3: 有效期管理服务 + 事件处理器 + 集成测试

**关联 AC:** AC-5, AC-7

#### TDD 循环 A: StrategicArchiveService 有效期扩展（Mock 端口）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/application/services/test_strategic_archive_service.py`（set_validity_period/is_stale/mark_stale） |
| 🟢 绿 | 扩展 `StrategicArchiveService` — 实现有效期管理方法 |
| 🔄 重构 | 添加类型注解、docstring、优雅降级逻辑 |

- [ ] Subtask 3.1: 🔴 红 — 编写有效期服务失败测试
- [ ] Subtask 3.2: 🟢 绿 — 扩展 `StrategicArchiveService`
- [ ] Subtask 3.3: 🔄 重构 — 优化服务代码

#### TDD 循环 B: 有效期事件处理器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/event_handlers/test_archive_handlers.py`（ValidityPeriodSet/FactBecameStale 处理逻辑） |
| 🟢 绿 | 实现事件处理器 `src/application/event_handlers/archive_handlers.py` |
| 🔄 重构 | 注册事件处理器到 EventBus |

- [ ] Subtask 3.4: 🔴 红 — 编写事件处理器失败测试
- [ ] Subtask 3.5: 🟢 绿 — 实现事件处理器
- [ ] Subtask 3.6: 🔄 重构 — 注册事件处理器

#### TDD 循环 C: 有效期管理集成测试

> **注意：** 集成测试依赖 Task 4 仓储扩展完成后才能完全通过。本循环的绿阶段仅实现**应用层服务方法**（`set_validity_period`/`is_stale`/`mark_stale_archives`），仓储层的有效期过滤扩展在 Task 4 完成。集成测试的红阶段验证方法签名可调用和基本流程（测试预期因方法未实现而失败），绿阶段先实现服务方法使测试通过，仓储扩展在 Task 4 完善后集成测试自动覆盖完整链路。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_archive_validity.py`（有效期设置+查询+陈旧标记，验证方法签名存在且可调用） |
| 🟢 绿 | 实现应用层有效期管理服务方法，使集成测试通过（仓储层依赖 Task 4 扩展） |
| 🔄 重构 | 优化测试隔离和断言 |

- [ ] Subtask 3.7: 🔴 红 — 编写集成测试（验证方法签名存在且可调用，业务功能未实现，测试预期失败）
- [ ] Subtask 3.8: 🟢 绿 — 实现应用层服务方法（set_validity_period/is_stale/mark_stale_archives），使集成测试通过（仓储有效期过滤扩展在 Task 4 完善）
- [ ] Subtask 3.9: 🔄 重构 — 优化集成测试隔离和断言

**完成标准/Definition of Done:**
- [ ] 有效期管理服务实现完成
- [ ] 有效期事件处理器实现完成
- [ ] 集成测试覆盖有效期设置+查询+陈旧标记
- [ ] 覆盖率≥85%

---

### Task 4: 基础设施层有效期查询扩展 + Alembic 迁移

**关联 AC:** AC-4, AC-6

#### TDD 循环 A: ArchiveModel 扩展 + Alembic

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展模型测试（valid_from/valid_until 列/约束） |
| 🟢 绿 | 扩展 `ArchiveModel` + 新增 Alembic migration |
| 🔄 重构 | 优化模型定义 |

- [ ] Subtask 4.1: 🔴 红 — 编写 ArchiveModel 扩展测试
- [ ] Subtask 4.2: 🟢 绿 — 扩展 `ArchiveModel` + Alembic migration（新增 valid_from/valid_until 列）
- [ ] Subtask 4.3: 🔄 重构 — 优化模型

#### TDD 循环 B: PostgreSQLArchiveRepository 有效期查询扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/infrastructure/storage/test_archive_repository.py`（有效期过滤/状态过滤） |
| 🟢 绿 | 扩展 `PostgreSQLArchiveRepository._apply_filters()` — 支持有效期过滤条件 |
| 🔄 重构 | 优化查询性能、添加索引 |

- [ ] Subtask 4.4: 🔴 红 — 编写仓储有效期查询失败测试
- [ ] Subtask 4.5: 🟢 绿 — 扩展 `PostgreSQLArchiveRepository`
- [ ] Subtask 4.6: 🔄 重构 — 优化仓储代码

**完成标准/Definition of Done:**
- [ ] `ArchiveModel` valid_from/valid_until 列 + Alembic migration 完成
- [ ] `PostgreSQLArchiveRepository` 有效期查询扩展完成
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥75%

---

### Task 5: API 路由 + 端口注册 + 架构验证

**关联 AC:** AC-8, AC-9

#### TDD 循环 A: 有效期管理 API 路由

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/interfaces/api/test_archive_routes.py`（PUT validity/GET 扩展参数/POST staleness-check） |
| 🟢 绿 | 扩展 `create_archive_router()` — 新增有效期管理端点 |
| 🔄 重构 | 添加 Pydantic Schema、错误处理 |

- [ ] Subtask 5.1: 🔴 红 — 编写 API 路由失败测试
- [ ] Subtask 5.2: 🟢 绿 — 扩展 API 路由
- [ ] Subtask 5.3: 🔄 重构 — 优化路由代码

#### TDD 循环 B: composition_root 服务扩展验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写测试验证 `StrategicArchiveService` 扩展方法可解析（`set_validity_period`/`is_stale`/`mark_stale_archives` 存在且可调用） |
| 🟢 绿 | 验证服务已注册并可解析（无新端口需注册，复用现有 `strategic_archive_service` 端口） |
| 🔄 重构 | 验证端口生命周期正确 |

- [ ] Subtask 5.4: 🔴 红 — 编写服务扩展方法解析失败测试
- [ ] Subtask 5.5: 🟢 绿 — 验证 DI 容器可正确解析扩展后的服务
- [ ] Subtask 5.6: 🔄 重构 — 验证端口生命周期正确

#### TDD 循环 C: 架构验证测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_arch_archive_validity.py`（架构约束） |
| 🟢 绿 | 实现架构验证测试 |
| 🔄 重构 | 优化验证逻辑 |

- [ ] Subtask 5.7: 🔴 红 — 编写架构验证失败测试
- [ ] Subtask 5.8: 🟢 绿 — 实现架构验证
- [ ] Subtask 5.9: 🔄 重构 — 优化架构验证

**完成标准/Definition of Done:**
- [ ] API 路由扩展完成（PUT validity / GET 扩展参数 / POST staleness-check）
- [ ] 端口注册完成，Resolver 可正确解析
- [ ] 架构约束测试通过
- [ ] 覆盖率≥85%

---

### Task 6: 开发结束验收测试

**关联 AC:** AC-1 ~ AC-9

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_archive_validity.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_archive_validity.py` 的 BDD 步骤实现 |
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
- **技术栈:** Python 3.11+、FastAPI 0.111+、SQLAlchemy 2.0+、Alembic、PostgreSQL 15+

### 关键架构决策

**决策 1：有效期字段存放位置**

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **方案 A：显式列（valid_from/valid_until 列）** | 类型安全、可索引、查询性能优、与 ExternalAPIWhitelist 模式一致 | 需要新增 Migration | ✅ 9/10 |
| 方案 B：metadata JSONB 字段 | 无需 Schema 变更、向后兼容好 | 查询性能差、类型不安全、无法索引 | 5/10 |

**决策理由：**
1. 时间轴查询需要 P95<200ms 的性能要求，显式列可创建索引
2. `ExternalAPIWhitelist` 实体已使用显式 `valid_from`/`valid_until` 列模式，保持一致
3. `metadata` 字段保留给 Story 3.12 的陈旧标记扩展

**决策 2：有效期管理服务的位置**

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **方案 A：扩展 StrategicArchiveService** | 保持服务一致性、复用现有注入 | 服务职责略增 | ✅ 8/10 |
| 方案 B：新建 ValidityPeriodService | 单一职责清晰 | 需额外端口注册、复用 L2 注入较复杂 | 7/10 |

**决策理由：**
1. 有效期管理是 StrategicArchive 的自然扩展，与现有服务职责高度相关
2. 复用现有 `archive_repo` 注入，无需新增端口注册
3. 避免服务间交叉依赖

### 数据陈旧标记策略说明

Story 3.11 的数据陈旧标记逻辑与 Story 3.12 的分工如下：

| 能力 | Story 3.11 范围 | Story 3.12 范围 |
|------|-----------------|-----------------|
| 有效期标签管理 | ✅ 设置 valid_from/valid_until | ✗ |
| 时间轴查询 | ✅ 按时间范围过滤查询 | ✗ |
| 陈旧标记检测 | ✅ 检测并标记 metadata 中的 staleness 标志 | ✗ |
| FactBecameStale 事件 | ✅ 发布事件通知下游 | ✗ |
| 陈旧数据降权 | ✗ | ✅ 排序分数降低 |
| 前端提示"数据陈旧" | ✗ | ✅ 生成结果中提示 |
| 降权处理 | ✗ | ✅ 权重应用 |

**陈旧标记规则：**
1. 优先检查 `valid_until`：如果 `valid_until < now`，标记为陈旧（`stale_reason="expired"`）
2. 如果 `valid_until` 为 None，检查 `archived_at`：如果 `archived_at < now - 12个月`，标记为陈旧（`stale_reason="archived_too_long"`）
3. 如果 `valid_until` 和 `archived_at` 均为 None，标记为"未设置有效期"（本 Story 不处理，Story 3.12 处理）
4. 陈旧标记存储在 `metadata` 字典中：`{"staleness": "stale", "stale_since": "2026-08-14T00:00:00Z"}`

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── entities/
│   │   ├── strategic_archive.py          # UPDATE: 新增 valid_from/valid_until 字段 + is_valid/is_expired/days_until_expiry
│   │   └── __init__.py                   # no change
│   ├── ports/
│   │   ├── archive_repository.py         # UPDATE: ArchiveQuery 新增 valid_from/valid_until/validity_status(ValidityStatus枚举)
│   │   └── __init__.py                   # no change
│   ├── events/
│   │   ├── archive_events.py             # UPDATE: 新增 ValidityPeriodSet / FactBecameStale
│   │   └── __init__.py                   # UPDATE: 导出新事件
│   └── exceptions/
│       ├── archive_exceptions.py         # UPDATE: 新增 ValidityPeriodConflictError (EXCEPTION_285)
│       ├── _code_ranges.py              # UPDATE: 注册 ValidityPeriodConflictError
│       └── __init__.py                   # UPDATE: 导出 ValidityPeriodConflictError
│
├── application/
│   ├── services/
│   │   └── strategic_archive_service.py  # UPDATE: 新增 set_validity_period/is_stale/mark_stale（复用query_archive）
│   └── event_handlers/
│       ├── archive_handlers.py           # NEW: ValidityPeriodSet / FactBecameStale 事件处理器
│       └── __init__.py                   # UPDATE: 导出新处理器
│
├── infrastructure/
│   └── storage/
│       └── postgresql/
│           ├── models/
│           │   ├── archive.py            # UPDATE: 新增 valid_from/valid_until 列
│           │   └── __init__.py           # no change
│           └── repository/
│               └── archive_repository.py # UPDATE: _apply_filters 扩展有效期过滤
│
├── interfaces/
│   └── api/
│       ├── strategic_archive.py          # UPDATE: 新增 PUT validity-period / POST staleness-check 端点
│       └── app.py                        # no change（路由已注册）
│
└── composition_root.py                   # UPDATE: 注册 archive_handlers 端口 + 新增 handler_names 条目

deploy/
└── postgresql/
    └── alembic/
        └── versions/
            └── 010_archive_validity_period.py  # NEW: 新增 valid_from/valid_until 列迁移

# 文档结构变更
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── ports/
│   │   │   │   └── test_archive_query.py         # NEW: ArchiveQuery + ValidityStatus 枚举单元测试
│   │   │   ├── entities/
│   │   │   │   └── test_archive_entity.py   # UPDATE: 有效期字段测试
│   │   │   ├── events/
│   │   │   │   └── test_archive_events.py   # UPDATE: 新事件测试
│   │   │   └── exceptions/
│   │   │       └── test_archive_exceptions.py # UPDATE: 新异常测试
│   │   ├── application/
│   │   │   ├── services/
│   │   │   │   └── test_strategic_archive_service.py # UPDATE: 有效期服务测试
│   │   │   └── event_handlers/
│   │   │       └── test_archive_handlers.py  # NEW: 事件处理器测试
│   │   ├── interfaces/
│   │   │   └── api/
│   │   │       └── test_archive_routes.py    # UPDATE: 有效期 API 路由测试
│   │   └── infrastructure/
│   │       └── storage/
│   │           └── test_archive_repository.py # UPDATE: 有效期查询测试
│   │   └── performance/
│   │       └── test_perf_archive_validity.py   # NEW: 有效期查询性能验证测试（P95<200ms）（对齐 test_compression_performance.py 先例）
│   ├── integration/
│   │   └── test_integration_archive_validity.py # NEW: 有效期管理集成测试
│   ├── contracts/
│   │   ├── test_port_contract_strategic_archive.py # UPDATE: 端口契约测试
│   │   └── test_api_contract_archive_validity.py   # NEW: API 契约测试
│   ├── acceptance/
│   │   ├── test_acceptance_archive_validity.feature # NEW: Gherkin 场景
│   │   └── test_acceptance_archive_validity.py      # NEW: BDD 步骤实现
│   └── unit/architecture/
│       └── test_arch_archive_validity.py   # NEW: 架构验证测试
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** Story 3.10（战略档案库长期存储与归档）

**关键学习/Key Learnings:**
1. **metadata 字段预留扩展** — StrategicArchive 的 `metadata` 字段和 ArchiveModel 的 `metadata_` 列明确标注"预留 Story 3.11/3.12 扩展点"，但本 Story 的 valid_from/valid_until 作为核心业务字段采用显式列而非 metadata 字段
2. **ArchiveConflictError 已定义未使用** — Story 3.10 的代码审查中 `ArchiveConflictError` 被延期到 Story 3.11/3.12 使用。本 Story 的 `ValidityPeriodConflictError` 应独立定义，而非复用 `ArchiveConflictError`
3. **异常编码可用** — archive 子域 (282-289) 已使用 282/283/284，可用编码 285/286/287/288/289。本 Story 使用 285
4. **事件通道配置** — 新事件必须同时更新 `configs/event_channels.yaml` 和 `ChannelRouter.DEFAULT_MAPPINGS`，否则事件不会正确路由
5. **Alembic migration 只新增不修改** — 已合入的 migration 禁止修改，只允许新增 migration 文件
6. **`_apply_filters()` 提取模式** — Story 3.10 的代码审查中，`find()` 和 `count()` 的重复过滤逻辑被提取为 `_apply_filters()` 共享方法。本 Story 扩展该方法即可
7. **ArchiveConflictError 已注册但未使用** — 在 Story 3.10 的代码审查中被标记为"延期到 Story 3.11/3.12 使用"，但本 Story 的 `ValidityPeriodConflictError` 是独立的有效期冲突异常，不应复用 `ArchiveConflictError`

**应用到本故事/Applied to This Story:**
- [ ] 实体扩展采用显式 valid_from/valid_until 列（非 metadata 字段）
- [ ] `ValidityPeriodConflictError` 独立定义（EXCEPTION_285），不复用 `ArchiveConflictError`
- [ ] `ValidityPeriodSet` 和 `FactBecameStale` 事件同时更新 `event_channels.yaml` 和 `DEFAULT_MAPPINGS`
- [ ] 新增 Alembic migration（只新增不修改已合入 migration）
- [ ] `_apply_filters()` 扩展有效期过滤条件，保持与现有过滤逻辑一致

### 环境变量与配置

**新增事件通道配置（`configs/event_channels.yaml`）：**
```yaml
ValidityPeriodSet:
  rabbitmq_routing_key: "sisys.events.reliable.validity_period_set"
  redis_channel: "sisys:rt:validity_period_set"
  delivery_mode: "reliable"
  description: "档案有效期设置完成"

FactBecameStale:
  rabbitmq_routing_key: "sisys.events.reliable.fact_became_stale"
  redis_channel: "sisys:rt:fact_became_stale"
  delivery_mode: "reliable"
  description: "事实变为陈旧"
```

**新增 `ChannelRouter.DEFAULT_MAPPINGS` 注册（`src/infrastructure/messaging/channel_router.py`）：**
```python
"ValidityPeriodSet": ChannelMapping(
    event_type="ValidityPeriodSet",
    rabbitmq_routing_key="sisys.events.reliable.validity_period_set",
    redis_channel="sisys:rt:validity_period_set",
    delivery_mode=DeliveryMode.RELIABLE,
    description="档案有效期设置完成",
),
"FactBecameStale": ChannelMapping(
    event_type="FactBecameStale",
    rabbitmq_routing_key="sisys.events.reliable.fact_became_stale",
    redis_channel="sisys:rt:fact_became_stale",
    delivery_mode=DeliveryMode.RELIABLE,
    description="事实变为陈旧",
),
```

**新增 `EXCEPTION_HTTP_MAP` 注册（`src/interfaces/api/exception_handlers.py`）：**
```python
# 在现有导入后追加新增异常的导入
from src.domain.exceptions.archive_exceptions import (
    ArchiveNotFoundError,
    ArchiveConflictError,
    ArchiveStorageError,
    ValidityPeriodConflictError,  # 新增
)

# 在 EXCEPTION_HTTP_MAP 中追加有效期冲突异常映射
EXCEPTION_HTTP_MAP.update({
    ValidityPeriodConflictError: 409,  # 新增 — 有效期冲突
})
```

### 异常编码分配

| 异常类 | 编码 | 继承 | 描述 |
|--------|------|------|------|
| ArchiveNotFoundError | EXCEPTION_282 | NotFoundError | 档案不存在（已有） |
| ArchiveConflictError | EXCEPTION_283 | ConflictError | 档案重复/冲突（已有，未使用） |
| ArchiveStorageError | EXCEPTION_284 | BusinessException | 存储层协同失败（已有） |
| **ValidityPeriodConflictError** | **EXCEPTION_285** | **ConflictError** | **有效期冲突（新增）** |

**`_CLASS_TO_SUBDOMAIN` 注册：**
```python
"ValidityPeriodConflictError": "archive",
```

### 存储层设计要点

**ArchiveModel 扩展（`strategic_archives` 表新增列）：**
```sql
ALTER TABLE strategic_archives
ADD COLUMN valid_from TIMESTAMP WITH TIME ZONE,   -- 生效时间（None 表示创建时生效）
ADD COLUMN valid_until TIMESTAMP WITH TIME ZONE;  -- 失效时间（None 表示永久有效）

-- 索引1：valid_until 单列索引，加速 validity_status="expired" 查询（WHERE valid_until < now）
CREATE INDEX ix_strategic_archives_valid_until ON strategic_archives(valid_until);
-- 索引2：valid_from 单列索引，加速 OR 查询中的 valid_from 条件过滤
CREATE INDEX ix_strategic_archives_valid_from ON strategic_archives(valid_from);
```

> **索引设计说明：** `validity_status="valid"` 查询涉及 `(valid_from IS NULL OR valid_from <= now) AND (valid_until >= now OR valid_until IS NULL)` 混合 OR + IS NULL 条件，PostgreSQL B-tree 复合索引无法有效加速。采用**两个单列索引**分别覆盖 `valid_until` 和 `valid_from` 过滤条件，PostgreSQL 查询优化器可对两个索引做 Bitmap Combine。`validity_status="expired"` 查询仅需 `valid_until < now`，单列索引最优。P95<200ms 的性能目标通过索引 + 数据量级控制保障。

**新旧数据兼容性：**
- 已有档案的 `valid_from` 和 `valid_until` 均为 None
- `is_valid()` 方法在两者均为 None 时返回 True（视为永久有效）
- `is_expired()` 方法在 `valid_until` 为 None 时返回 False
- 查询时 `validity_status=None` 表示不按有效期过滤，与现有行为一致

### 有效期状态过滤逻辑

| validity_status | SQL 过滤条件 |
|----------------|-------------|
| `"valid"` | `(valid_from IS NULL OR valid_from <= now) AND (valid_until >= now OR valid_until IS NULL)` — NULL 安全，已有档案（valid_from=NULL 且 valid_until=NULL）被包含 |
| `"expired"` | `valid_until < now` |
| `None` | 无有效期过滤（默认，向后兼容） |

### 陈旧标记逻辑

```
mark_stale_archives(batch_size=100):
  1. 应用层循环调用 archive_repo.find()，batch_size 映射为 limit 参数，offset 逐批递增，分批查询待标记档案：
     - valid_until < now（已过期，stale_reason="expired"）
     - OR (valid_until IS NULL AND archived_at < now - 12个月)（归档超期，stale_reason="archived_too_long"）
     - AND (metadata->>'staleness' IS DISTINCT FROM 'stale')（排除已标记档案，保证幂等）
     - 注：valid_until IS NULL AND archived_at IS NULL 的档案不参与批量标记（"未设置有效期"状态）
  2. 对每个首次标记的档案：
     a. 更新 metadata 字段（仅首次写入，重复执行不覆盖 stale_since）：
        metadata["staleness"] = "stale"
        metadata["stale_since"] = now.isoformat()
     b. 保存到 L2
     c. 发布 FactBecameStale 事件（valid_until 为 None 时事件中该字段为 None，stale_reason 区分陈旧原因）
  3. 返回被标记的档案列表
```

> **Outbox 事务边界说明：** `mark_stale_archives` 中 L2 save 与 FactBecameStale 事件发布存在双写不一致风险。RELIABLE 模式使用 RabbitMQ + Outbox，事件应通过事务性 Outbox 与 L2 元数据在**同一数据库事务**内持久化，由 Outbox 发布器异步投递，确保最终一致性。事件发布失败时由 Outbox 重试机制保障（非仅日志警告）。

### 优雅降级策略

| 场景 | 失败影响 | 降级策略 |
|------|---------|---------|
| is_stale L2 失败 | 陈旧检查失败 | 抛出 `ArchiveStorageError(layer="l2")` |
| mark_stale_archives 部分失败 | 部分档案陈旧标记失败 | 记录日志，继续处理下一批 |
| 事件发布失败 | 下游无法感知有效期变更 | Outbox 重试机制保障最终一致性；若 Outbox 不可用则记录警告日志，不影响主流程 |

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.2 |
| **Version** | create-story workflow v2.9.0 |
| **Execution Date** | 2026-08-14 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/3-10-strategic-archive-permanent-storage.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 3.11, 第 1693-1732 行）
- [x] 架构约束从 `architecture.md` 提取（StrategicArchive 实体定义 §9, 六层存储 §11）
- [x] 前一个故事学习经验整合（Story 3.10 模式）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-11-fact-validity-period-management.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/application/event_handlers/archive_handlers.py` - 有效期事件处理器
- `deploy/postgresql/alembic/versions/010_archive_validity_period.py` - valid_from/valid_until 列迁移 + EXCLUDE 约束（btree_gist）
- `tests/unit/domain/ports/test_archive_query.py` - ArchiveQuery + ValidityStatus 枚举单元测试
- `tests/unit/application/event_handlers/test_archive_handlers.py` - 事件处理器测试
- `tests/integration/test_integration_archive_validity.py` - 集成测试
- `tests/contracts/test_api_contract_archive_validity.py` - API 契约测试
- `tests/acceptance/test_acceptance_archive_validity.feature` - Gherkin 场景
- `tests/acceptance/test_acceptance_archive_validity.py` - BDD 步骤实现
- `tests/unit/architecture/test_arch_archive_validity.py` - 架构验证测试
- `tests/unit/performance/test_perf_archive_validity.py` - 有效期查询性能验证测试（P95<200ms）

**待更新的文件/To Be Updated:**
- `src/domain/entities/strategic_archive.py` - 新增 valid_from/valid_until 字段 + is_valid/is_expired/days_until_expiry
- `src/domain/ports/archive_repository.py` - ArchiveQuery 新增 valid_from/valid_until/validity_status(ValidityStatus枚举) + 新增 ValidityStatus 枚举
- `src/domain/events/archive_events.py` - 新增 ValidityPeriodSet / FactBecameStale
- `src/domain/events/__init__.py` - 导出新事件
- `src/domain/exceptions/archive_exceptions.py` - 新增 ValidityPeriodConflictError (EXCEPTION_285)
- `src/domain/exceptions/__init__.py` - 导出 ValidityPeriodConflictError
- `src/domain/exceptions/_code_ranges.py` - 注册 ValidityPeriodConflictError
- `src/application/services/strategic_archive_service.py` - 新增有效期管理方法（set_validity_period/is_stale/mark_stale_archives，复用query_archive）
- `src/application/event_handlers/__init__.py` - 导出新处理器
- `src/infrastructure/storage/postgresql/models/archive.py` - 新增 valid_from/valid_until 列
- `src/infrastructure/storage/postgresql/repository/archive_repository.py` - 扩展 _apply_filters + 更新 _to_entity/_to_model
- `src/interfaces/api/strategic_archive.py` - 新增 PUT validity / POST staleness-check 端点
- `src/interfaces/api/exception_handlers.py` - 注册 ValidityPeriodConflictError 映射
- `configs/event_channels.yaml` - 注册 ValidityPeriodSet / FactBecameStale 通道
- `src/infrastructure/messaging/channel_router.py` - 注册 DEFAULT_MAPPINGS
- `tests/unit/domain/entities/test_archive_entity.py` - 有效期字段测试
- `tests/unit/domain/events/test_archive_events.py` - 新事件测试
- `tests/unit/domain/exceptions/test_archive_exceptions.py` - 新异常测试
- `tests/unit/application/services/test_strategic_archive_service.py` - 有效期服务测试
- `tests/unit/interfaces/api/test_archive_routes.py` - 有效期 API 路由测试
- `tests/unit/infrastructure/storage/test_archive_repository.py` - 有效期查询测试
- `tests/contracts/test_port_contract_strategic_archive.py` - 端口契约测试更新

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.11 |
| **Story Key** | 3-11-fact-validity-period-management |
| **File** | `_bmad-output/implementation-artifacts/stories/3-11-fact-validity-period-management.md` |
| **Status** | `backlog` → `ready-for-dev` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | P1-11 |
| **覆盖 FR** | FR-SA-02（P0） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

**Round 1 审查修复（2026-08-14）：**

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | ValidityPeriodSet/FactBecameStale 的 `__post_init__` 缺少 `aggregate_id = self.archive_id` 赋值 | P0 | 增加 aggregate_id 赋值逻辑，与 ArchiveCreated 一致 |
| 2 | FactBecameStale.valid_until 类型为 `datetime`（非可选），与 valid_until=None 场景冲突 | P0 | 改为 `datetime \| None = None`，与实体字段类型一致 |
| 3 | `set_validity_period` 流程未调用 `archive.validate()` | P0 | 在 save 之前显式调用 `archive.validate()` |
| 4 | `query_by_validity` 与现有 `query_archive` 功能完全重复 | P0 | 删除 `query_by_validity`，复用 `query_archive` |
| 5 | `validity_status="valid"` 的 SQL 条件未处理 valid_from IS NULL 场景 | P0 | 改为 NULL 安全形式：`(valid_from IS NULL OR valid_from <= now)` |
| 6 | `ArchiveResponse` 未新增 valid_from/valid_until 字段 | P0 | 新增字段 + `_to_archive_response()` 映射 |
| 7 | ValidityPeriodConflictError 无触发规则（"重叠有效期"未定义） | P1 | 定义冲突判定：同一 plan_id+archive_type 下区间重叠 |
| 8 | valid_from_filter/valid_until_filter 命名与现有字段不一致 | P1 | 改为 valid_from/valid_until（去 _filter 后缀） |
| 9 | validity_status 使用 str 而非枚举 | P1 | 新增 ValidityStatus 枚举（VALID/EXPIRED/ALL） |
| 10 | 事件缺少 redis_channel 配置 | P1 | 补充 redis_channel 配置 |
| 11 | _to_entity/_to_model 未显式要求更新 | P1 | 在 AC-6 和项目结构中明确标注 |
| 12 | 索引设计可优化为复合索引 | P1 | 改为复合索引 `(valid_from, valid_until)` |
| 13 | 文档引用不存在的 date_range 参数 | P1 | 修正为实际参数名 |
| 14 | P95<200ms 无测试载体 | P1 | 新增性能测试文件 `test_perf_archive_validity.py` |
| 15 | Task 3 TDD 循环 C 红绿语义颠倒 | P1 | 修正绿阶段为"实现服务方法+仓储扩展使测试通过" |
| 16 | Task 5 TDD 循环 B 是空转循环（无新端口） | P1 | 改为"验证服务扩展方法可解析" |
| 17 | 集成测试覆盖率门禁口径未定义 | P1 | 明确测量命令和范围 |
| 18 | AC-1 方法缺少可测试性设计（datetime.now 直接硬编码） | P1 | 增加模块级 `_now()` 函数支持测试注入 |

**Round 2 审查修复（2026-08-15）：**

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | ValidityStatus.ALL 与 None 语义重复，造成 API 设计混淆 | P1 | 删除 `ALL="all"` 枚举值，仅保留 VALID/EXPIRED，None 即表示"不过滤" |
| 2 | FactBecameStale 缺少陈旧原因字段，消费方无法区分两种陈旧机制 | P1 | 新增 `stale_reason: str` 字段（`"expired"` / `"archived_too_long"`） |
| 3 | 冲突判定中"含开区间边界"表述自相矛盾 | P1 | 明确采用半开区间 `[valid_from, valid_until)`，端点相接不视为冲突 |
| 4 | `check_staleness` 命名与 `is_valid()`/`is_expired()` 不一致 | P1 | 改为 `is_stale()` 保持 `is_` 前缀一致 |
| 5 | 性能测试文件 `test_perf_archive_validity.py` 分类归属不当（混入 architecture 目录） | P1 | 移至 `tests/performance/` 目录（后修正为 `tests/unit/performance/` 对齐项目先例 `test_compression_performance.py`） |
| 6 | 性能测试缺少数据量级与执行策略要求 | P1 | 补充：≥10,000 条记录、100 次迭代取 P95、10 次预热、CI 默认跳过 |
| 7 | ArchiveQuery 单元测试混入端口契约测试文件 `test_port_contract_strategic_archive.py` | P1 | 拆分到独立文件 `tests/unit/domain/ports/test_archive_query.py` |
| 8 | Task 3 TDD 循环 C 集成测试绿阶段要求同时实现服务+仓储两层，跨度不合理 | P1 | 明确绿阶段仅实现应用层服务方法，仓储依赖 Task 4 |
| 9 | Schema 自创建方式未明确（create_all vs alembic upgrade） | P1 | 在测试隔离约束中明确集成测试使用 `Base.metadata.create_all()` |
| 10 | 索引设计无法有效支撑 validity_status 查询（复合索引对 OR+IS NULL 无效） | P1 | 改为两个单列索引 `(valid_until)` + `(valid_from)` |
| 11 | 事件 `__post_init__` 中 `aggregate_id` 条件判断逻辑（archive_id 必填，条件恒 True） | P1 | 改为无条件赋值，语义更清晰 |
| 12 | 集成测试覆盖率≥70% 定位模糊（硬门禁 vs 软参考） | P2 | 明确为"不作为 CI 门禁，仅作为开发者自检参考" |
| 13 | Edge Cases 与异常路径边界划分不清晰 | P2 | 统一将异常路径归入 Edge Cases 子集 |
| 14 | `_to_archive_response()` 中 valid_from/valid_until 的 ISO 格式转换未明确 | P2 | 明确使用 `.isoformat()` 转换，与 created_at 一致 |
| 15 | `EXCEPTION_HTTP_MAP` 文档示例重复导入已有异常 | P2 | 仅展示 ValidityPeriodConflictError 新增行 |
| 16 | 项目结构图中 `test_perf_archive_validity.py` 仍在 architecture 目录下 | P2 | 移至 `tests/performance/` 目录 |
| 17 | 集成测试 Schema 自创建方式未明确 | P2 | 明确使用 `Base.metadata.create_all()` |
| 18 | AC-1 `days_until_expiry` 返回类型表述歧义 | P2 | 明确"与 ExternalAPIWhitelist 的负数行为一致，但返回类型为 `int \| None`" |

**Round 3 审查修复（2026-08-15）：**

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | set_validity_period 冲突检测存在 TOCTOU 竞态（应用层内存比较无数据库约束兜底） | P0 | 三层防御：PostgreSQL EXCLUDE 约束（btree_gist）+ find_for_update() 悲观锁 + 应用层内存比较 |
| 2 | 事件处理器注册机制描述与实际架构不符（文档写"注册到 EventBus 或 ChannelRouter"，实际是 InMemoryEventListener + register_handlers()） | P0 | 修正 AC-7：更改为 on_event() + register_handlers() 模式，明确 handler_names 注册和 _wrap_handler() 回调包装 |
| 3 | composition_root 标注为"no change"但实际需注册 archive_handlers 端口 + handler_names 条目 | P1 | 修正项目结构图标注为 UPDATE |
| 4 | L3/L5 无有效期初始快照，3.12 无法增量同步 | P1 | archive_plan() 的 L3 payload/L5 properties 写入 valid_from/valid_until 初始值；ValidityPeriodSet 处理器预留同步钩子 |
| 5 | mark_stale_archives 非幂等（重复执行覆盖 stale_since + 重复发布事件） | P1 | 查询排除已标记档案（metadata->>'staleness' IS DISTINCT FROM 'stale'）+ 仅首次写入 stale_since |
| 6 | is_stale 与 mark_stale_archives 陈旧判断逻辑重复，存在语义分裂风险 | P1 | 提取实体方法 `StrategicArchive.is_stale()` 统一判定标准，服务方法委托实体 |
| 7 | FactBecameStale 事件与 metadata 双写不一致（Outbox 事务边界未明确） | P1 | 明确 L2 save 与事件通过事务性 Outbox 同事务持久化，Outbox 重试保障最终一致性 |
| 8 | 性能测试路径应与项目现有先例 `tests/unit/performance/` 对齐 | P1 | 统一改为 `tests/unit/performance/test_perf_archive_validity.py` |
| 9 | 端口契约测试需补充 ArchiveQuery 新字段验证 + StrategicArchiveService 扩展方法验证 | P2 | AC-9 补充契约测试验证范围说明 |
| 10 | ValidityPeriodSet 事件发布失败后的补偿机制未说明 | P2 | 补充最终一致性说明（Outbox 重试）+ 建议 replay 手段 |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 2026-08-14
**审查模式:** full（Blind Hunter + Edge Case Hunter）

#### 需决策 Decision Needed

- [ ] [3-11-决策-1] **有效期字段存放位置** — 方案 A（显式列）vs 方案 B（metadata JSONB）已选择方案 A，理由已在关键架构决策中说明。确认是否同意。

#### 已修复 Patch

- 暂无

#### 已推迟 Defer

- [ ] [3-11-Defer-1][Review][Defer] **Qdrant/Neo4j 有效期同步** — 档案有效期变更时，L3 向量存储和 L5 图存储的 payload 是否需要同步更新有效期的讨论。当前 Story 3.11 仅处理 L2 元数据有效期，L3/L5 同步延期到 Story 3.12 处理。**延期影响分析**：在 3.12 完成 L3/L5 同步前，L3 向量搜索无法通过向量层 payload 过滤有效期，检索结果可能包含已过期档案，须依赖 L2 二次过滤兜底。
  >
  > **补充（Round 2 审查发现）：** 当前 `archive_plan()` 的 L3 payload 和 L5 properties 中**未写入 valid_from/valid_until 初始快照值**。即使 Story 3.12 要实现 L3/L5 同步，也没有初始基线可供比对增量。建议在本 Story 的 `archive_plan()` 中向 L3 payload 追加 `"valid_from": None, "valid_until": None` 字段，L5 properties 同理，为 3.12 提供兼容基础。同时在 ValidityPeriodSet 事件处理器中预留 `TODO: Story 3.12 - sync valid_from/valid_until to L3/L5 payload` 钩子。

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `validate-create-story` 进行质量检查
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-08-14
**最后更新/Last Updated:** 2026-08-15
**更新说明/Description:**
- v1.0.0: 创建故事文件
- v1.0.1: Round 1 审查修订 — 修复 6 个 P0 + 12 个 P1 问题（事件 aggregate_id、事件字段类型、validity_status NULL 安全、ArchiveResponse 扩展、冲突规则定义、枚举类型、时钟注入等）
- v1.1.0: Round 2 审查修订 — 修复 0 个 P0 + 12 个 P1 + 6 个 P2 问题（ValidityStatus 删除 ALL、FactBecameStale 新增 stale_reason、冲突判定半开区间 + 端点说明、check_staleness→is_stale 重命名 + 剥离实体方法、性能测试对齐 tests/unit/performance/、ArchiveQuery 测试独立、索引策略优化、事件 __post_init__ 无条件赋值、集成测试循环跨度修正、覆盖率门禁定位明确等）
- v1.2.0: Round 3 审查修订 — 修复 1 个 P0 + 5 个 P1 + 1 个 P2 问题（TOCTOU 竞态三层防御 + EXCLUDE 约束 + FOR UPDATE、事件 handler 注册机制修正为 InMemoryEventListener + register_handlers 模式、composition_root 标注修正、L3 payload 初始快照、mark_stale_archives 幂等设计 + 实体 is_stale 方法、陈旧标记逻辑排除已标记档案 + Outbox 事务边界说明、性能测试路径对齐 tests/unit/performance/）
