# Story 3.9: 语义缓存

**Status:** `backlog`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 性能工程师,
**I want** 系统执行语义缓存（相似度>0.9 直接返回缓存结果）,
**So that** 减少重复检索和 LLM 调用，降低 Token 消耗。

### 业务价值

本 Story 是 Epic 3（智能检索与知识发现）的第九个故事（P1-9），对应 FR-CP-02（语义缓存基础）和 NFR-PERF-06（缓存命中率≥40%，Token 消耗降低 40-50%）。

**现有资产（已就绪，本 Story 直接利用）：**
- `SemanticCache` 应用层端口已定义（`src/application/ports/semantic_cache.py`）
- `RedisSemanticCache` 基础设施实现已完成（`src/infrastructure/storage/redis/semantic_cache.py`，基于 RediSearch KNN）
- 已在 `composition_root.py` 注册为 `semantic_cache` 端口（SCOPED，cache-team 负责）
- 单元测试已存在（`tests/unit/infrastructure/storage/test_semantic_cache.py` + `tests/unit/domain/services/test_semantic_cache_interface.py`）

**本 Story 的核心任务：**
- 语义缓存目前是"已就绪但未接入"状态——**端口已定义、实现已注册，但没有任何业务逻辑调用它**
- 本 Story 将其接入混合检索流水线（`HybridSearchService`），实现缓存的自动查询/写入/失效
- 建立事件驱动缓存失效机制（订阅 `DocumentProcessed` 事件，见下方【事件选择说明】）
- 暴露缓存指标（命中率、延迟、节省 Token 数）

> **⚠️ 事件选择说明（P0 修正）**：语义缓存缓存的是**文档检索结果**，因此失效触发事件必须与**文档变更**相关。原稿误用 `MemoryChanged`（用户记忆变更事件，字段为 `memory_id`/`user_id`/`name`），与文档检索结果无关——文档变更时该事件不会触发，过时缓存将持续返回。本 Story 改用**已有的 `DocumentProcessed` 事件**（`src/domain/events/document_events.py`，字段含 `document_id`、`tenant_id`）作为缓存失效触发源。`DocumentProcessed` 在文档解析/索引完成后发布（RELIABLE，RabbitMQ + Outbox），符合"文档内容变更后缓存需刷新"的语义。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **缓存优先检索** | 相似查询直接返回缓存，跳过完整检索管线 | 相似度>0.9 命中，延迟 P95<50ms |
| **缓存自动写入** | 首次查询结果自动缓存，后续查询受益 | 检索后自动缓存 |
| **事件驱动失效** | 文档变更时缓存自动失效，保证一致性 | DocumentProcessed → 缓存失效 |
| **缓存指标** | 可观测缓存效率，支撑 NFR 目标 | 命中率≥40%，Token 节省 40-50% |
| **降级策略** | 缓存不可用时不阻断检索主流程 | 缓存异常透明降级 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 3: 智能检索与知识发现，Story 3.9

**前置依赖:**
- Story 3.1a（Dense 语义检索 ✅ 已实现）— 提供 `EmbeddingServicePort` 用于生成查询向量，作为缓存键
- Story 3.4（RRF 融合排序 ✅ 已实现）— 提供 `HybridSearchService` 三路检索编排，缓存包装的目标服务
- Story 1.4（Redis 缓存层 ✅ 已实现）— 提供 `RedisSemanticCache` 基础设施
- Story 1.15a（事件总线 ✅ 已实现）— 提供 `DocumentProcessed` 事件（`src/domain/events/document_events.py`）订阅用于缓存失效。**注意**：本 Story 使用 `DocumentProcessed` 而非 `MemoryChanged`，因为语义缓存缓存的是文档检索结果，文档变更时 `DocumentProcessed` 触发，`MemoryChanged`（用户记忆变更）不会触发

**后续依赖:** Story 3.10（战略档案库永久存储）、Story 3.11（事实有效期标签管理）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 语义缓存中间件（缓存优先检索 + 自动写入）

**Given** 系统已初始化语义缓存中间件，`HybridSearchService` 被缓存中间件包装
**When** 用户发送查询 Q1
**Then** 缓存查询 Q1 的嵌入向量在语义缓存中查找
**And** 未命中时执行完整 `HybridSearchService.search()` 检索
**And** 检索结果自动写入缓存（以查询嵌入为键，TTL 24h）
**And** 返回检索结果

**Given** 同一查询 Q1（或相似度>0.9 的查询 Q2）再次到达
**When** 系统执行查询
**Then** 语义缓存命中，直接返回缓存结果
**And** 不执行 `HybridSearchService.search()` 检索
**And** 缓存命中延迟 P95<50ms（仅含向量搜索 + 反序列化，排除嵌入生成）

> **⚠️ 性能指标说明（P0 修正）**：嵌入生成（`EmbeddingServicePort.embed_query()`）调用外部 LLM Embedding API，延迟通常为 100-500ms，无法纳入 P95<50ms 指标。因此 P95<50ms 仅衡量**缓存查找阶段**（向量搜索 + 反序列化），不包含嵌入生成耗时。嵌入生成延迟单独记录在 `cache_hit_latency_seconds` 指标中，不设 P95 门禁。

**验证标准/Validation Criteria:**
- [ ] `SemanticCacheMiddleware` 位于 `src/application/services/semantic_cache_middleware.py`
- [ ] 包装 `HybridSearchService`，实现 `search()` 签名兼容（`collection, query_text, limit, tenant_id, filter_payload, weights`）
- [ ] 缓存优先策略：先查缓存，命中直接返回，未命中执行检索并写入缓存
- [ ] 缓存键使用查询嵌入向量（通过 `EmbeddingServicePort.embed_query()` 生成），含 `weights` 哈希后缀（不同 weights 生成不同缓存键，避免 RRF 融合结果错误）
- [ ] 缓存值使用 `dict` 格式 JSON 序列化：`{"results": list[SearchResult], "query_text": str, "weights": list[float] | None}`（`SemanticCache.set()` 签名要求 `result: dict`，不支持裸列表）
- [ ] 默认 TTL 86400 秒（24h），可通过构造参数配置
- [ ] 默认相似度阈值 0.9，可通过构造参数配置
- [ ] 嵌入生成失败时透明降级为直接检索（不缓存）
- [ ] 缓存写入失败时仅记录日志，不阻断检索结果返回
- [ ] 缓存命中延迟 P95<50ms（仅含向量搜索 + 反序列化，排除嵌入生成）

### AC-2: 事件驱动缓存失效

**Given** 文档已缓存（检索结果已存储在语义缓存中）
**When** `DocumentProcessed` 事件被发布（文档解析/索引完成，含文档 ID 和租户信息）
**Then** 缓存失效处理器收到事件
**And** 对受影响的 collection 执行缓存失效

**Given** 缓存已失效
**When** 重新查询相关文档内容
**Then** 语义缓存未命中
**And** 执行完整检索

**验证标准/Validation Criteria:**
- [ ] 缓存失效监听器位于 `src/infrastructure/messaging/event_handlers/cache_invalidation_handler.py`
- [ ] 监听 `DocumentProcessed` 事件（`event_type == "DocumentProcessed"`）
- [ ] 失效策略：通过 `SemanticCache.invalidate_by_document_id()` 端口方法维护"文档 ID → 缓存键"二级索引（Redis Set），缓存写入时记录关联关系，失效时通过文档 ID 查关联缓存键后逐一删除
- [ ] 失效操作仅记录日志，不抛出异常（事件处理不阻塞主流程）
- [ ] 支持手动触发全量缓存清理（`invalidate_all` 方法，删除 `sisys:cache:semantic:*` 前缀下所有键，含缓存 + 二级索引）
- [ ] 支持按 collection 前缀匹配清理（`invalidate_pattern` 方法，基于 SCAN 模式匹配，使用 `COUNT` 参数控制批量大小，默认 100）

> **⚠️ 失效策略设计说明（原稿 P0 修正）**：`RedisSemanticCache._build_cache_key()` 基于**嵌入向量 MD5 哈希**生成缓存键（`vec:{md5[:16]}`），**无法通过文档 ID 直接反查**。因此原稿的 `cache_key = f"doc:{event.aggregate_id}"` 完全失效——构造的键与任何实际缓存键都不匹配。本修正方案采用二级索引（Redis Set）维护文档 ID ↔ 缓存键的关联关系，实现按文档 ID 精确失效。

### AC-3: 缓存指标与可观测性

**Given** 语义缓存中间件正在运行
**When** 查询执行（命中或未命中）
**Then** 记录以下指标：
- 缓存命中次数（`cache_hits_total`）
- 缓存未命中次数（`cache_misses_total`）
- 缓存命中率（`hit_rate` = `hits / (hits + misses)`）
- 缓存命中延迟 P95（`cache_hit_latency_seconds`）
- 预估节省 Token 数（`estimated_tokens_saved` = 命中次数 × `avg_tokens_per_search`，`avg_tokens_per_search` 为 `SemanticCacheMiddleware` 构造参数，默认 5000）

**Given** 缓存指标已记录
**When** 查询缓存命中率
**Then** 命中率≥40%（NFR-PERF-06 目标）
**And** Token 消耗降低 40-50%

**验证标准/Validation Criteria:**
- [ ] 通过应用层 `CacheMetricsPort` 指标端口（`src/application/ports/cache_metrics_port.py`）采集缓存指标，**禁止**直接依赖基础设施层 `EventMetricsCollector`（六边形架构约束）
- [ ] `CacheMetricsPort` 定义 `record_cache_hit()` / `record_cache_miss()` / `record_cache_latency(latency_seconds)` / `hit_rate` 属性
- [ ] 新增 `estimated_tokens_saved` 属性（基于 `avg_tokens_per_search` 配置参数，作为 `SemanticCacheMiddleware` 构造参数注入，默认值 5000）
- [ ] 指标可通过 `SemanticCacheMiddleware.metrics` 属性访问（返回 `CacheMetricsPort` 实例）
- [ ] 缓存命中延迟 P95<50ms（仅向量搜索 + 反序列化，排除嵌入生成）

> **⚠️ 性能指标说明（P0 修正）**：P95<50ms 为**性能基线目标**，在真实 Redis 环境中通过基准测试验证（预热后 N≥100 次命中采样），**不纳入自动化 CI 测试门禁**。UI 应说明此指标，"排除嵌入生成"。
- [ ] 缓存命中率≥40%

> **⚠️ 架构合规说明（Round 2 P0 修正）**：`EventMetricsCollector` 位于基础设施层（`src/infrastructure/monitoring/`），`SemanticCacheMiddleware` 位于应用层（`src/application/services/`），应用层直接引用基础设施层类型违反六边形架构约束（import-linter 将阻断 CI）。本 Story **新建** 应用层指标端口 `CacheMetricsPort`（Protocol），`SemanticCacheMiddleware` 仅注入该端口。`RedisSemanticCache` 内部仍可继续使用 `EventMetricsCollector`（基础设施层内部依赖合法）。在 `composition_root.py` 中注册 `cache_metrics` 端口，将 `EventMetricsCollector` 实例作为 `CacheMetricsPort` 实现注入。

### AC-4: 降级策略

**Given** Redis 服务不可用（连接失败/超时）
**When** 查询请求到达语义缓存中间件
**Then** 缓存中间件透明降级为直接检索（不缓存）
**And** 返回 `HybridSearchService.search()` 的完整检索结果
**And** 缓存不可用期间记录 WARNING 日志
**And** Redis 恢复后自动恢复缓存功能

**Given** 缓存中存储了损坏的数据（JSON 反序列化失败）
**When** 查询命中该缓存条目
**Then** 缓存中间件跳过损坏条目，视为未命中
**And** 执行完整检索
**And** 记录 WARNING 日志

**验证标准/Validation Criteria:**
- [ ] Redis 连接异常时透明降级，不抛出异常
- [ ] 缓存数据损坏时跳过该条目，视为未命中
- [ ] 缓存不可用期间记录 WARNING 日志（不写 INFO 或 ERROR）
- [ ] 自动恢复：下次请求自动重试缓存查询

### AC-5: 端口注册与 DI 集成

**Given** 所有组件实现完成
**When** 在 `composition_root.py` 注册
**Then** `semantic_cache_middleware` 端口注册为 `SCOPED`，注入 `hybrid_search_service` 和 `semantic_cache`
**And** 通过 `Resolver` 可正确解析
**And** 端口契约测试通过

**验证标准/Validation Criteria:**
- [ ] `composition_root.py` 注册 `semantic_cache_middleware` 端口
- [ ] 注入 `embedding_service` 用于生成查询向量
- [ ] 注入 `semantic_cache` 端口（已有的 `RedisSemanticCache`）
- [ ] 注入 `hybrid_search_service`（已有的 `HybridSearchService`）
- [ ] `semantic_cache` 端口生命周期从 `SCOPED` 改为 `SINGLETON`（缓存实例全局共享）
- [ ] 端口契约测试 `tests/contracts/test_port_contract_semantic_cache.py` 通过

### AC-6: 异常体系

**Given** 语义缓存操作可能发生错误
**When** 定义缓存异常类
**Then** 继承项目统一异常层次结构
**And** 分配唯一异常编码

**验证标准/Validation Criteria:**
- [ ] **不新增缓存领域异常** — 语义缓存失败是技术基础设施问题，已有 `StorageError`（EXCEPTION_103）和 `NetworkError`（EXCEPTION_102）可覆盖；缓存命中/未命中是正常流程，非异常场景
- [ ] 缓存异常透明降级（WARNING 日志），不抛出异常
- [ ] 嵌入生成失败使用已有的 `EmbeddingAPIError`（EXCEPTION_306）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

本 Story 涉及的领域事件：

- **`DocumentProcessed`**（`src/domain/events/document_events.py`）— 文档解析/索引完成后发布，`document_id: uuid.UUID` 标识变更文档，RELIABLE 通道（RabbitMQ + Outbox）
- 缓存失效监听器订阅 `DocumentProcessed` 事件，按文档 ID 关联的缓存键执行失效
- **不新增**领域事件，缓存操作是技术基础设施环节，不产生领域事件

#### 数据模型 (Data Models)

**不新建数据模型，复用现有类型：**
- `SearchResult`（`src/domain/ports/l3_vector.py` 的 TypedDict）— 缓存值的 JSON 序列化格式
- `dict` 作为缓存值类型，序列化为 JSON 字符串存储（`SemanticCache.set()` 签名要求 `result: dict`）
- 缓存键使用查询嵌入向量的 MD5 哈希（`RedisSemanticCache._build_cache_key` 已实现）
- **缓存值包装格式**：`{"results": list[SearchResult], "query_text": str, "weights": list[float] | None}`

#### 统一端口定义注册与管理 (Port Contract)

**新增端口（应用层）：**
- `SemanticCacheMiddleware`（`src/application/services/semantic_cache_middleware.py`）— 非 Protocol，是具体应用服务类，但需在 `composition_root.py` 注册

**端口契约清单（强制）：**

| 端口名称 | 版本 | Owner | 注册 | 解析 | 契约测试 | 状态 |
|---------|------|-------|------|------|---------|------|
| semantic_cache | v1.0.0 | cache-team | 已有（composition_root） | 已有 | 已有（更新） | **已有，升级生命周期** |
| semantic_cache_middleware | v1.0.0 | cache-team | 新建 | 新建 | 新建 | **新建** |
| embedding_service | v1.0.0 | foundation-team | 已有 | 已有 | 已有 | **已有（复用）** |
| hybrid_search_service | v1.1.0 | search-team | 已有 | 已有 | 已有 | **已有（包装）** |

**生命周期变更：**
- `semantic_cache` 端口从 `Lifetime.SCOPED` 改为 `Lifetime.SINGLETON` — 语义缓存实例必须在所有请求间共享，否则缓存失去意义（每个请求创建独立缓存实例，无法命中其他请求写入的缓存）。因 `PortRegistry.register()` 对同名端口抛出 `ConflictError`，需先 `unregister("semantic_cache")` 再重新注册。
- **SINGLETON 安全性说明**：`RedisSemanticCache` 使用注入的 `aioredis.Redis` 连接池（线程安全），`_index_ready` 的竞态因 `FT.CREATE` 幂等性不影响功能；Redis 重启后 `_index_ready` 可能失效，但 `get()`/`set()` 的异常处理会触发降级。

#### 领域异常契约 (Domain Exception Contract)

本 Story **不新增**领域异常。理由：
- 缓存命中/未命中是正常流程分支，非异常场景
- 缓存 Redis 连接失败透明降级为直接检索，不抛出异常
- 嵌入生成失败使用已有的 `EmbeddingAPIError`（EXCEPTION_306，继承 `ExternalException`）
- 缓存数据损坏视为未命中，不抛出异常

#### 六边形架构约束（必须遵守）

> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 本 Story 职责 |
|------|------|-------------|
| domain | `src/domain/` | 无新增（复用 `SemanticCache` 应用层端口、`EmbeddingServicePort` 领域端口） |
| application | `src/application/` | `SemanticCacheMiddleware` 缓存编排（包装 `HybridSearchService`） |
| infrastructure | `src/infrastructure/` | 缓存失效监听器（订阅 `DocumentProcessed` 事件触发缓存清理） |
| interfaces | `src/interfaces/` | 无新增 |

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | infrastructure |
|------------|--------|-------------|----------------|
| **domain** | — | ✗ 禁止 | ✗ 禁止 |
| **application (SemanticCacheMiddleware)** | ✓ 允许（EmbeddingServicePort, SemanticCache） | — | ✗ 禁止 |
| **infrastructure (cache invalidation handler)** | ✓ 允许（SemanticCache, DocumentProcessed） | ✗ 禁止 | — |

**领域层零依赖原则** — 本 Story 不新增领域层代码。

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_semantic_cache.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_semantic_cache.py`
- [ ] 业务方评审通过
- [ ] 覆盖场景:
  - Happy Path: 首次查询未命中 → 执行检索 → 自动缓存 → 再次查询命中
  - Happy Path: 相似查询（相似度>0.9）命中缓存
  - Edge Case: 相似度<0.9 不命中缓存
  - Edge Case: Redis 不可用时透明降级
  - Edge Case: 缓存 TTL 过期后自动失效
  - Edge Case: 事件驱动缓存失效（DocumentProcessed → 缓存清除）
  - Metrics: 缓存命中率指标采集正确

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
| **TDD 单元测试** | SemanticCacheMiddleware | 缓存优先/自动写入/降级/指标 | `test_semantic_cache_middleware.py` | Task 1 |
| **TDD 单元测试** | 缓存失效监听器 | DocumentProcessed 事件处理 | `test_cache_invalidation_handler.py` | Task 2 |
| **TDD 回归验证** | 已有 RedisSemanticCache | 验证现有功能未破坏 | `test_semantic_cache.py`（已有） | Task 1 |
| **TDD 验收测试** | Gherkin 场景（新建） | 业务价值验收 | `test_acceptance_semantic_cache.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现（新建） | 步骤函数实现 | `test_acceptance_semantic_cache.py` | Task 0 |
| **TDD 契约测试** | SemanticCacheMiddleware | 端口注册/解析/契约门禁 | `test_port_contract_semantic_cache.py` | Task 3 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖 | `test_arch_semantic_cache.py` | Task 3 |
| **集成测试** | 语义缓存全流程 | 端到端缓存流程 | `test_integration_semantic_cache.py` | Task 3 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application/services/`）
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure/messaging/event_handlers/`）
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration/`）

> ⚠️ 本 Story 主要为"接入已有基础设施"，代码量相对较小，但需覆盖缓存中间件的完整状态空间（命中/未命中/降级）。如果上述覆盖率无法达到，请将整体覆盖率临时调整为≥60%，应用层≥70%。

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **外部服务隔离（单元测试）** | 单元测试用 `AsyncMock(spec=RedisSemanticCache)` 隔离 Redis，`AsyncMock(spec=HybridSearchService)` 隔离检索服务 | 真实调用导致失败 |
| **外部服务隔离（集成测试）** | 集成测试**真实 Redis 优先**；Redis 不可用时用 `pytest.skip()` 动态跳过，**禁止全局 Mock** | 违反项目"真实服务优先"约束 |
| **缓存隔离** | 集成测试使用独立 Redis key 前缀（`test:cache:semantic:`），测试结束后清理 | 缓存污染导致随机失败 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离缓存键 | 缓存冲突导致并行失败 |
| **BDD async 配合** | BDD 步骤函数用 `event_loop.run_until_complete()` | context 数据丢失 |
| **Mock 与 P95 口径区分** | 单元测试用 Mock 验证功能正确性；P95 性能验收（缓存命中<50ms）在真实 Redis 上断言 | Mock 不反映真实延迟 |

**验证要求：**
- [ ] 并行测试 `poetry run pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 语义缓存中间件（缓存优先检索 + 自动写入） | Task 1 | Subtask 1.1-1.3 | `test_semantic_cache_middleware.py` |
| AC-2 | 事件驱动缓存失效 | Task 2 | Subtask 2.1-2.3 | `test_cache_invalidation_handler.py` |
| AC-3 | 缓存指标与可观测性 | Task 1 | Subtask 1.4-1.5 | `test_semantic_cache_middleware.py` |
| AC-4 | 降级策略 | Task 1 | Subtask 1.1-1.2 | `test_semantic_cache_middleware.py` |
| AC-1~AC-5 | 开发结束验收 | Task 4 | Subtask 4.1-4.3 | `test_acceptance_semantic_cache.feature` |
| AC-5 | 端口注册与 DI 集成 | Task 3 | Subtask 3.1-3.4 | `test_port_contract_semantic_cache.py` |
| AC-6 | 异常体系（不新增异常） | Task 0 | Subtask 0.1 | 架构验证 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 确认异常体系设计（确认不新增异常，复用 StorageError/NetworkError 透明降级）
- [ ] Subtask 0.2: 定义 `SemanticCacheMiddleware` 接口设计（`search()` 签名对齐 `HybridSearchService`）
- [ ] Subtask 0.3: 定义 `semantic_cache` 端口生命周期从 SCOPED 改为 SINGLETON 的迁移方案
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_semantic_cache.feature`
- [ ] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_semantic_cache.py`
- [ ] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 应用层 — SemanticCacheMiddleware（缓存优先检索 + 自动写入 + 指标）

**关联 AC:** AC-1, AC-3, AC-4

> **核心设计：** `SemanticCacheMiddleware` 是 `HybridSearchService` 的装饰器，遵循**装饰器模式**。
> 它不修改 `HybridSearchService` 的代码，而是通过包装实现缓存逻辑。
> 注入 `EmbeddingServicePort`（生成查询向量作为缓存键）+ `SemanticCache`（缓存存储/查询）+ `HybridSearchService`（被包装的检索服务）。

#### TDD 循环 [A]：SemanticCacheMiddleware 缓存优先逻辑

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_semantic_cache_middleware.py`（缓存优先/自动写入/降级） |
| 🟢 绿 | 实现 `src/application/services/semantic_cache_middleware.py`（`SemanticCacheMiddleware` 类） |
| 🔄 重构 | 优化缓存逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 SemanticCacheMiddleware 失败测试
  - **Happy Path: 缓存未命中 → 执行检索 → 自动写入**
    - 注入 `AsyncMock(spec=SemanticCache)` 的 `get()` 返回 `None`
    - 注入 `AsyncMock(spec=HybridSearchService)` 的 `search()` 返回结果列表
    - 调用 `middleware.search(collection, query_text)`
    - 验证 `cache.get()` 被调用 → 返回 None → `search_service.search()` 被调用 → `cache.set()` 被调用
    - 验证返回结果来自 `search_service`
  - **Happy Path: 缓存命中 → 直接返回**
    - `cache.get()` 返回模拟的缓存结果数据
    - 调用 `middleware.search(collection, query_text)`
    - 验证 `cache.get()` 被调用 → `search_service.search()` **未被调用**
    - 验证返回结果来自缓存
  - **Happy Path: 相似查询（相似度>0.9）命中**
    - 构造相似度>0.9 的两个查询文本
    - 首次查询未命中，自动缓存
    - 第二次查询命中，直接返回
  - **Edge Case: 嵌入生成失败 → 直接检索，不缓存**
    - `embedding_service.embed_query()` 抛出异常
    - 验证 `search_service.search()` 被调用（降级为直接检索）
    - 验证 `cache.set()` 未被调用
    - 验证结果正常返回，不抛出异常
  - **Edge Case: Redis 不可用 → 透明降级**
    - `cache.get()` 抛出 `ConnectionError`
    - 验证 `search_service.search()` 被调用
    - 验证结果正常返回，不抛出异常
  - **Edge Case: 缓存数据损坏 → 视为未命中**
    - `cache.get()` 返回不可 JSON 反序列化的数据
    - 验证视为未命中，执行完整检索
  - **Edge Case: 缓存写入失败 → 仅日志，不阻断**
    - `cache.set()` 抛出异常
    - 验证检索结果正常返回

- [ ] Subtask 1.2: 🟢 绿 — 实现 SemanticCacheMiddleware
  ```python
  class SemanticCacheMiddleware:
      def __init__(
          self,
          search_service: HybridSearchService,
          cache: SemanticCache,
          embedding_service: EmbeddingServicePort,
          threshold: float = 0.9,
          ttl: int = 86400,
          avg_tokens_per_search: int = 5000,  # 预估 Token 节省计算基数
          metrics: CacheMetricsPort | None = None,  # 应用层指标端口（Protocol 注入）
      ):
  ```
  > **⚠️ 架构合规说明（Round 3 P0 修正）**：`SemanticCacheMiddleware` 构造参数**不包含** `redis_client: aioredis.Redis`。二级索引的写入（SADD）与读取/删除（SMEMBERS/DELETE）统一封装在 `RedisSemanticCache`（基础设施层）内部——通过扩展 `SemanticCache.set()` 增加可选参数 `doc_ids: list[str] | None = None`，缓存写入时由中间件提取结果中的文档 ID 列表传给 `cache.set(..., doc_ids=...)`，中间件不直接操作 Redis。指标通过 `CacheMetricsPort`（应用层 Protocol）注入，禁止直接依赖基础设施层类型。
  - `search()` 方法签名：`(collection, query_text, limit=10, tenant_id=None, filter_payload=None, weights=None) -> list[SearchResult]`
  - 缓存优先流程：
    1. 调用 `embedding_service.embed_query(query_text)` 生成查询向量
    2. 调用 `cache.get(query_embedding, threshold)` 查询缓存
    3. 命中 → 反序列化 → 返回缓存结果
    4. 未命中 → 调用 `search_service.search()` → 序列化结果 → `cache.set()` → 返回
  - **缓存键设计（P1 修正）**：缓存键包含 `weights` 参数的哈希后缀，不同 weights 产生不同缓存键，避免不同 weights 返回错误融合结果。`_build_cache_key(query_embedding, weights)` 在中间件层实现。
  - **二级索引维护**：缓存写入时从 `SearchResult` 结果中提取文档 ID 列表，通过 `SemanticCache.set()` 扩展的 `doc_ids` 参数传入（`cache.set(embedding, result, doc_ids=extracted_doc_ids)`），二级索引的 SADD 写入统一封装在 `RedisSemanticCache` 内部，使用 Redis pipeline 批量操作。`SemanticCacheMiddleware` 不直接操作 Redis。
  - 异常安全：嵌入/缓存异常时降级为直接检索，记录 WARNING 日志
  - 指标采集：命中/未命中计数、延迟记录

- [ ] Subtask 1.3: 🔄 重构 — 优化代码，运行 `ruff check` + `mypy` + `pytest`

#### TDD 循环 [B]：缓存指标与可观测性

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 在 `test_semantic_cache_middleware.py` 中补充指标验证测试 |
| 🟢 绿 | 在 `SemanticCacheMiddleware` 中添加指标采集逻辑 |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [ ] Subtask 1.4: 🔴 红 — 编写指标采集失败测试
  - **缓存命中次数递增**：命中后 `metrics.cache_hits_total` 加 1
  - **缓存未命中次数递增**：未命中后 `metrics.cache_misses_total` 加 1
  - **命中率计算**：`hit_rate = hits / (hits + misses)` 正确
  - **延迟记录**：命中后 `cache_hit_latency_seconds` 有记录
  - **预估节省 Token**：`estimated_tokens_saved` = 命中次数 × `avg_tokens_per_search`
  - **metrics 属性可访问**：`middleware.metrics` 返回 `CacheMetricsPort` 实例（通过 Protocol 注入，**非** `EventMetricsCollector` 具体类型）
  - **不同 weights 缓存隔离**：相同查询文本 + 不同 weights → 不同缓存键，互不影响
  - **缓存键碰撞检测**：MD5 哈希碰撞时自动检测并覆盖

- [ ] Subtask 1.5: 🟢 绿 — 实现指标采集
  - 通过应用层 `CacheMetricsPort` 端口（`src/application/ports/cache_metrics_port.py`）采集指标，**禁止**直接引用基础设施层 `EventMetricsCollector`
  - `CacheMetricsPort` 定义：`record_cache_hit()` / `record_cache_miss()` / `record_cache_latency(latency_seconds)` / `hit_rate` 属性
  - 新增 `estimated_tokens_saved` 属性（基于 `avg_tokens_per_search` 构造参数）
  - 暴露 `metrics` 属性（返回 `CacheMetricsPort` 实例）

- [ ] Subtask 1.6: 🔄 重构 — 运行 `ruff check` + `mypy` + `pytest`

**完成标准/Definition of Done:**
- [ ] SemanticCacheMiddleware 实现完成（缓存优先 + 自动写入 + 降级 + 指标）
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥70%（应用层）

---

### Task 2: 基础设施层 — 事件驱动缓存失效监听器

**关联 AC:** AC-2

> **设计说明：** 缓存失效监听器订阅 `DocumentProcessed` 事件，当文档解析/索引完成后触发缓存清理。
> 监听器位于基础设施层的事件处理模块，通过 `EventSubscriber` 端口注册。
> 采用**二级索引精确失效**策略：缓存写入时维护"文档 ID → 缓存键"的 Redis Set 映射，失效时先查文档 ID 关联的所有缓存键，再逐一删除。避免全量缓存清理带来的性能冲击。

#### TDD 循环 [A]：缓存失效监听器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/messaging/test_cache_invalidation_handler.py` |
| 🟢 绿 | 实现 `src/infrastructure/messaging/event_handlers/cache_invalidation_handler.py` |
| 🔄 重构 | 优化失效逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 2.1: 🔴 红 — 编写缓存失效监听器失败测试
  - **Happy Path: DocumentProcessed 事件触发缓存失效**
    - 构造 `DocumentProcessed` 事件（含 `document_id`）
    - 调用 handler 处理事件
    - 验证 `cache.invalidate()` 被调用（通过文档 ID 查询关联缓存键后逐一删除）
  - **Edge Case: 非 DocumentProcessed 事件 → 忽略**
    - 发送 `EntitiesExtracted` 事件
    - 验证 `cache.invalidate()` **未被调用**
  - **Edge Case: 缓存失效失败 → 仅日志，不抛出异常**
    - `cache.invalidate()` 抛出异常
    - 验证 handler 不抛出异常
    - 验证 WARNING 日志被记录
  - **Edge Case: document_id 为空 → 跳过**
    - 构造 `document_id` 为空的 DocumentProcessed 事件
    - 验证 `cache.invalidate()` 未被调用
  - **Edge Case: 支持按 collection 前缀批量失效**
    - 构造含 `collection` 标识的事件上下文
    - 验证 `cache.invalidate_pattern()` 被调用
  - **Edge Case: 二级索引缺失 → 降级为全量清理**
    - 文档 ID 关联的 Redis Set 不存在
    - 验证 `cache.invalidate_all()` 被调用（降级方案）

- [ ] Subtask 2.2: 🟢 绿 — 实现缓存失效监听器
  ```python
  class CacheInvalidationHandler:
      """缓存失效事件处理器

      监听 DocumentProcessed 事件，触发语义缓存失效。
      通过 SemanticCache.invalidate_by_document_id() 端口方法封装二级索引逻辑。
      """

      def __init__(self, cache: SemanticCache):
          self._cache = cache

      async def handle(self, event: DomainEvent) -> None:
          """处理 DocumentProcessed 事件，触发缓存失效"""
          if event.event_type != "DocumentProcessed":
              return
          doc_id = getattr(event, "document_id", None)
          if doc_id is None:
              return
          try:
              await self._cache.invalidate_by_document_id(str(doc_id))
          except Exception:
              logger.warning("缓存失效失败: %s", doc_id)
  ```

- [ ] Subtask 2.3: 🔄 重构 — 运行 `ruff check` + `mypy` + `pytest`

**完成标准/Definition of Done:**
- [ ] 缓存失效监听器实现完成
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥75%

---

### Task 3: 端口注册 + 架构验证 + 集成测试

**关联 AC:** AC-5, AC-6

> **生命周期变更说明（关键）：** `semantic_cache` 端口当前注册为 `Lifetime.SCOPED`（每请求作用域一个实例）。
> 语义缓存必须在所有请求间共享才能生效，因此需改为 `Lifetime.SINGLETON`。
> 因 `PortRegistry.register()` 对同名端口抛出 `ConflictError`，需先 `unregister("semantic_cache")` 再重新注册。

#### 端口注册与 DI 集成

- [ ] Subtask 3.1: 更新 `composition_root.py`
  - 先 `unregister("semantic_cache")` 再重新注册 `semantic_cache` 端口，生命周期改为 `SINGLETON`
  - 注册 `semantic_cache_middleware` 端口（SCOPED），注入：
    - `embedding_service`（领域端口，已有）
    - `semantic_cache`（应用层端口，已有，生命周期已改为 SINGLETON）
    - `hybrid_search_service`（应用层服务，已有）
    - 可选：`cache_metrics`（`CacheMetricsPort` 指标采集，通过 `composition_root` 注册的 `cache_metrics` 端口注入）
  - 注册 `cache_invalidation_handler` 端口（SCOPED），注入 `semantic_cache`（通过 `invalidate_by_document_id()` 间接操作二级索引，无需直接注入 `redis_client`）
  - 注册事件监听：`document_processed` → `cache_invalidation_handler.handle()`

- [ ] Subtask 3.2: 扩展 `SemanticCache` 协议 + `RedisSemanticCache` 实现 + 新建 `CacheMetricsPort`
  - **新建** `src/application/ports/cache_metrics_port.py`，定义 `CacheMetricsPort` Protocol：
    - `record_cache_hit() -> None`
    - `record_cache_miss() -> None`
    - `record_cache_latency(latency_seconds: float) -> None`
    - `hit_rate` 属性（返回 `float`）
    - `cache_hits_total` 属性（返回 `int`）
    - `cache_misses_total` 属性（返回 `int`）
  - 在 `SemanticCache` 协议中新增：
    - `invalidate_pattern(pattern: str) -> None` — 按模式匹配批量失效（基于 SCAN，默认 COUNT=100）
    - `invalidate_all() -> None` — 全量缓存清理（删除 `sisys:cache:semantic:*` 前缀下的所有键，含缓存数据 + 二级索引）
    - `invalidate_by_document_id(doc_id: str) -> None` — 按文档 ID 使关联的缓存条目失效（封装二级索引逻辑，避免 CacheInvalidationHandler 直接操作 redis_client）
    - `set()` 扩展可选参数 `doc_ids: list[str] | None = None` — 缓存写入时一并维护文档 ID 二级索引（SADD 使用 Redis pipeline 批量操作）
  - 在 `RedisSemanticCache` 中实现：
    - `invalidate_pattern()`: 基于 Redis SCAN + DELETE 模式匹配，使用 `COUNT` 参数控制批量大小
    - `invalidate_all()`: 通过 `scan(match="sisys:cache:semantic:*")` 批量删除
    - `invalidate_by_document_id()`: 内部维护二级索引（`SMEMBERS` 读取 + 逐个 `invalidate()` 删除缓存 + `DELETE` 清理索引），使用 `build_key("cache:semantic", "idx:doc", doc_id)` 规范构建键名
    - `set(doc_ids=...)`: 内部将缓存主数据（HSET + EXPIRE）与二级索引（SADD + EXPIRE）用 pipeline 打包为一次网络往返
  - 在 `SemanticCacheMiddleware` 中：
    - 从 `SearchResult` 结果提取文档 ID 列表，传给 `cache.set(..., doc_ids=...)`，不直接操作 Redis
    - 缓存键包含 `weights` 参数的哈希后缀（不同 weights 隔离缓存）
  - 二级索引 key 命名空间分层：
    - `sisys:cache:semantic:vec:{md5}` — 缓存数据（已有）
    - `sisys:cache:semantic:idx:doc:{doc_id}` — 文档 ID 二级索引（新增，`idx:` 中间段与 `vec:` 精确区分）

> **⚠️ 二级索引命名说明（Round 2 P1 修正）**：使用 `idx:doc:` 而非 `doc:` 作为中间段，确保 `invalidate_pattern("vec:*")` 只匹配缓存数据、`invalidate_pattern("idx:*")` 只匹配二级索引，避免误删。`invalidate()` 的文档注释增加警告：传入的 `cache_key` 应是缓存条目键，不要传入二级索引键。

- [ ] Subtask 3.3: 端口契约测试
  - 创建 `tests/contracts/test_port_contract_semantic_cache.py`
  - 验证 `semantic_cache` 端口已注册且生命周期为 `SINGLETON`
  - 验证 `semantic_cache_middleware` 端口已注册
  - 验证 `cache_invalidation_handler` 端口已注册
  - 验证通过 `Resolver` 可正确解析各端口

- [ ] Subtask 3.4: 架构验证测试
  - 创建 `tests/unit/architecture/test_arch_semantic_cache.py`
  - 验证 `SemanticCacheMiddleware` 不直接依赖基础设施层
  - 验证依赖方向正确（application → domain, infrastructure → domain）
  - 验证 `CacheInvalidationHandler` 仅依赖领域层事件和端口

#### 集成测试

- [ ] Subtask 3.5: 集成测试 `tests/integration/test_integration_semantic_cache.py`
  - **测试环境：** 使用真实 Redis（通过 `RedisConnectionManager` 获取），独立测试 key 前缀
  - **场景 1: 缓存优先检索**
    - 创建 `RedisSemanticCache` 实例
    - 创建 `SemanticCacheMiddleware` 实例（注入 mock 的 `HybridSearchService` 和真实 `EmbeddingServicePort`）
    - 发送查询 → 未命中 → 执行检索 → 缓存写入
    - 发送相同查询 → 命中 → 直接返回
  - **场景 2: 缓存 TTL 过期**
    - 设置 TTL=1s
    - 等待 1.5s
    - 验证缓存自动过期（未命中）
  - **场景 3: 缓存失效**
    - 写入缓存
    - 调用 `cache.invalidate()`
    - 验证缓存已清除
  - **场景 4: 并发查询隔离**
    - 并行发送 5 个不同查询
    - 验证每个查询独立缓存，互不干扰
    - **同一查询并发首次访问**：两个并发请求同时查询同一文本（缓存未命中），验证最终缓存中有一份有效数据，后续查询命中（无脏数据）
  - **场景 5: 降级策略**
    - 断开 Redis 连接
    - 发送查询 → 验证降级为直接检索
    - 恢复 Redis 连接（`redis-py` 连接池采用懒连接模式，下次请求自动创建新连接，无需手动重连）
    - 发送查询 → 验证自动恢复缓存功能
  - **场景 6: 二级索引失效**
    - 写入缓存（含多个文档 ID 的检索结果）
    - 验证 `sisys:cache:semantic:idx:doc:{doc_id}` 二级索引已维护
    - 触发 `DocumentProcessed` 事件 → 验证关联缓存键被删除，索引被清理
  - **场景 7: 不同 weights 缓存隔离**
    - 相同查询 + 不同 weights → 验证产生不同缓存键，互不影响

- [ ] Subtask 3.6: 更新端口导出
  - 确保 `src/application/ports/__init__.py` 正确导出 `SemanticCache`（已有）
  - 确保 `src/domain/ports/__init__.py` 正确导出 `L1CachePort`（已有）

**完成标准/Definition of Done:**
- [ ] `composition_root.py` 注册完成（生命周期变更 + 新端口注册 + `CacheMetricsPort` 注册）
- [ ] `SemanticCache` 协议扩展完成（`invalidate_pattern()` + `invalidate_all()` + `invalidate_by_document_id()`）
- [ ] `CacheMetricsPort` 应用层指标端口创建完成
- [ ] 端口契约测试通过
- [ ] 架构验证测试通过
- [ ] 集成测试通过（真实 Redis）
- [ ] 所有代码质量门禁通过

---

### Task 4: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段进行最终验收。

> **⚠️ 验收方式说明（Round 2 P2 修正）**：原稿 Subtask 4.1/4.2 使用 BDD/Gherkin 场景验证"文件存在性"，这是反模式——BDD 的作用是验证**业务行为**而非文件清单（参考 `test_acceptance_hybrid_search.feature` 无此类场景）。现将文件清单验证改为 **Definition of Done checklist 条目**（非 BDD 测试），Task 4 聚焦端到端行为验证与收尾校验。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_semantic_cache.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_semantic_cache.py` 的 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达、保持步骤函数可维护性 |

- [ ] Subtask 4.1: 端到端行为验证场景
  - **业务行为**：给定语义缓存已运行，当混合检索执行时，缓存命中率指标正确记录
  - **降级行为**：给定 Redis 不可用，当混合检索执行时，系统降级且不抛出异常
  - **一致行为**：给定文档已缓存，当 DocumentProcessed 事件发布时，缓存正确失效
- [ ] Subtask 4.2: 运行开发结束验收测试并确认通过
- [ ] Subtask 4.3: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验

**完成标准（含文件清单 checklist，非 BDD 场景）/Definition of Done:**
- [ ] `src` 完成清单已逐项验证：
  - `src/application/services/semantic_cache_middleware.py`
  - `src/application/ports/cache_metrics_port.py`
  - `src/infrastructure/messaging/event_handlers/cache_invalidation_handler.py`
  - `src/composition_root.py` 注册完成
- [ ] `tests/` 完成清单已逐项验证：
  - `tests/unit/application/services/test_semantic_cache_middleware.py`
  - `tests/unit/infrastructure/messaging/test_cache_invalidation_handler.py`
  - `tests/contracts/test_port_contract_semantic_cache.py`
  - `tests/unit/architecture/test_arch_semantic_cache.py`
  - `tests/integration/test_integration_semantic_cache.py`
  - `tests/acceptance/test_acceptance_semantic_cache.feature`
  - `tests/acceptance/test_acceptance_semantic_cache.py`
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 装饰器模式（`SemanticCacheMiddleware` 包装 `HybridSearchService`）
- **设计约束:**
  - 语义缓存是"已就绪但未接入"状态，本 Story 不修改已有端口和实现（除 `SemanticCache` 协议扩展外）
  - `SemanticCache` 端口生命周期从 `SCOPED` 改为 `SINGLETON`（缓存实例全局共享，`aioredis.Redis` 连接池线程安全，`_index_ready` 竞态因 `FT.CREATE` 幂等不影响功能）
  - 缓存失效监听器采用**二级索引精确失效**策略：通过 `SemanticCache.invalidate_by_document_id()` 端口方法封装，`CacheInvalidationHandler` 不直接操作 `redis_client`
  - 缓存失效触发事件：`DocumentProcessed`（文档解析/索引完成后发布），而非 `MemoryChanged`（用户记忆变更事件，与文档检索结果无关）
  - 缓存异常透明降级（WARNING 日志），不抛出异常
  - 不新增缓存领域异常（复用 `StorageError` / `NetworkError`）
  - **指标采集**：`SemanticCacheMiddleware` 通过应用层 `CacheMetricsPort` 端口注入，**禁止**直接引用基础设施层 `EventMetricsCollector`（六边形架构约束，import-linter 强制校验）
  - **二级索引封装**：二级索引的写入（SADD）与读取/删除（SMEMBERS/DELETE）统一封装在 `RedisSemanticCache` 内部，通过 `SemanticCache.set()` 的 `doc_ids` 参数传入文档 ID 列表，`SemanticCacheMiddleware` 和 `CacheInvalidationHandler` 均不直接操作 `redis_client`（六边形架构约束）
  - **二级索引命名空间**：`sisys:cache:semantic:idx:doc:{doc_id}`（`idx:` 中间段与 `vec:` 精确区分，避免 `invalidate_pattern` 误删）
  - **Redis pipeline 批量操作**：二级索引维护使用 `async with self._redis.pipeline(transaction=True) as pipe` 打包所有 SADD 命令，减少网络往返
- **技术栈:** Redis 7.0+（RediSearch FT.SEARCH 向量索引）、bge-m3 嵌入（1024 维）

### 关键架构决策

**来源:** 本 Story 设计决策

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **✅ 装饰器模式包装 HybridSearchService** | 不修改已有代码，关注点分离，可独立测试 | 引入一层包装调用开销 | ✅ 9/10 |
| 在 HybridSearchService 内部直接集成缓存 | 无额外调用开销 | 修改已有代码，违反开闭原则 | 5/10 |

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **✅ 二级索引精确失效（文档 ID → 缓存键 Redis Set）** | 精确失效，不影响其他缓存；可处理跨文档聚合查询 | 需维护二级索引，增加写入开销和代码复杂度 | ✅ 8/10 |
| 按 aggregate_id 直接构造缓存键 | 实现简单 | 缓存键格式不匹配，完全无法生效（P0 缺陷） | 0/10 |
| 全量缓存清理 | 实现简单，保证一致性 | 大量缓存被清空，缓存命中率骤降 | 4/10 |

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **✅ 不新增缓存领域异常** | 保持异常体系简单，复用已有异常类 | 缓存异常无法被调用方精确捕获 | ✅ 8/10 |
| 新增 `CacheError` 领域异常 | 调用方可精确捕获缓存异常 | 增加异常体系复杂度，违反 YAGNI | 5/10 |

### 项目结构说明 Project Structure

```
.\
├── src/
│   ├── application/
│   │   ├── ports/
│   │   │   └── cache_metrics_port.py               # [新建] 应用层缓存指标端口
│   │   └── services/
│   │       └── semantic_cache_middleware.py   # [新建] 语义缓存中间件
│   │
│   ├── infrastructure/
│   │   └── messaging/
│   │       └── event_handlers/
│   │           └── cache_invalidation_handler.py  # [新建] 缓存失效监听器
│   │
│   └── composition_root.py                     # [修改] 注册新端口 + 生命周期变更
│
└── tests/
    ├── contracts/
    │   └── test_port_contract_semantic_cache.py  # [新建] 端口契约测试
    ├── unit/
    │   ├── application/services/
    │   │   └── test_semantic_cache_middleware.py  # [新建] 中间件单元测试
    │   ├── infrastructure/messaging/
    │   │   └── test_cache_invalidation_handler.py # [新建] 失效监听器单元测试
    │   └── architecture/
    │       └── test_arch_semantic_cache.py        # [新建] 架构验证测试
    ├── integration/
    │   └── test_integration_semantic_cache.py     # [新建] 集成测试
    └── acceptance/
        ├── test_acceptance_semantic_cache.feature # [新建] Gherkin 场景
        └── test_acceptance_semantic_cache.py      # [新建] BDD 步骤实现
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 3.4 - RRF 融合排序](./3-4-rrf-fusion-ranking.md)

**关键学习/Key Learnings:**
1. **端口升级机制** — `PortRegistry.register()` 对同名端口冲突则抛 `ConflictError`，必须先 `unregister()` 再重新注册。Story 3.4 中 `hybrid_search_service` 从 v1.0.0 升级到 v1.1.0 时采用了此模式。本 Story 中 `semantic_cache` 的生命周期变更（SCOPED→SINGLETON）也需走此流程。
2. **降级策略是非功能性需求的核心** — Story 3.4 的 `LiteLLMRerankerClient` 展示了"API 调用失败时返回原始结果，不阻断主流程"的降级模式。本 Story 的缓存降级设计应遵循相同原则。
3. **异常体系设计** — Story 3.4 新增 `RerankError`（EXCEPTION_350）和 `HybridSearchError`（EXCEPTION_209），展示了异常编码分配和子域注册的完整流程。本 Story 确认不新增异常（合理决策）。

**应用到本故事/Applied to This Story:**
- [x] 使用 `unregister()` + `register()` 模式变更 `semantic_cache` 生命周期
- [x] 缓存异常透明降级（WARNING 日志，不抛出异常）
- [x] 确认不新增缓存领域异常（复用已有异常类）

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
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/3-4-rrf-fusion-ranking.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] 前一个故事学习经验整合（Story 3.4）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 已有代码调研完成（SemanticCache 端口 + RedisSemanticCache 实现 + 已有单元测试）
- [x] 确认不新增异常（复用已有异常体系）
- [x] 生命周期变更方案已记录（SCOPED → SINGLETON）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-9-semantic-cache.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/application/ports/cache_metrics_port.py` - 应用层缓存指标端口
- `src/application/services/semantic_cache_middleware.py` - 语义缓存中间件
- `src/infrastructure/messaging/event_handlers/cache_invalidation_handler.py` - 缓存失效监听器
- `tests/unit/application/services/test_semantic_cache_middleware.py` - 中间件单元测试
- `tests/unit/infrastructure/messaging/test_cache_invalidation_handler.py` - 失效监听器单元测试
- `tests/contracts/test_port_contract_semantic_cache.py` - 端口契约测试
- `tests/unit/architecture/test_arch_semantic_cache.py` - 架构验证测试
- `tests/integration/test_integration_semantic_cache.py` - 集成测试
- `tests/acceptance/test_acceptance_semantic_cache.feature` - Gherkin 场景
- `tests/acceptance/test_acceptance_semantic_cache.py` - BDD 步骤实现

**待修改的文件/To Be Modified:**
- `src/composition_root.py` - 注册新端口 + 生命周期变更

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.9 |
| **Story Key** | 3-9-semantic-cache |
| **File** | `_bmad-output/implementation-artifacts/stories/3-9-semantic-cache.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | P1-9 |
| **覆盖 FR** | FR-CP-02, NFR-PERF-06 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（Story 3.4）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 本 Story 经过 5 轮循环审查修订（Round 1: 代码调研 + 文档审查 + 修复）。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | 事件概念错配：使用 `MemoryChanged`（用户记忆变更事件）而非 `DocumentProcessed`（文档变更事件）作为缓存失效触发源。语义缓存缓存的是文档检索结果，文档变更时 `MemoryChanged` 不会触发，过时缓存持续返回 | **P0** | 全文替换 `MemoryChanged` → `DocumentProcessed`；更新 AC-2、SDD 规范、Task 2 设计、代码示例、架构约束、依赖矩阵、Dev Notes |
| 2 | 缓存失效键策略根本性错误：`cache_key = f"doc:{event.aggregate_id}"` 构造的键与 `RedisSemanticCache._build_cache_key()` 的 `vec:{md5[:16]}` 格式完全不匹配，失效永远无效 | **P0** | 重新设计失效策略：采用二级索引（Redis Set）维护"文档 ID → 缓存键"映射，失效时先查关联缓存键再逐一删除。新增 `invalidate_pattern()` / `invalidate_all()` 协议扩展 |
| 3 | AC-1 P95<50ms 含嵌入生成不可达：嵌入生成（LLM Embedding API）延迟 100-500ms，远超 50ms | **P0** | 拆分指标：P95<50ms 仅衡量向量搜索 + 反序列化（排除嵌入生成），嵌入延迟单独记录 `cache_hit_latency_seconds` 不设门禁 |
| 4 | 缓存值类型不匹配：文档说 `list[SearchResult]` 但 `SemanticCache.set()` 签名要求 `result: dict` | **P1** | 缓存值使用 `{"results": list[SearchResult], "query_text": str, "weights": list[float] | None}` 包装格式 |
| 5 | `weights` 参数未纳入缓存键：相同查询文本不同 weights 返回错误融合结果 | **P1** | 缓存键包含 `weights` 参数的哈希后缀，不同 weights 产生不同缓存键 |
| 6 | `avg_tokens_per_search` 未定义：`estimated_tokens_saved` 计算公式依赖的配置项未定义 | **P1** | 作为 `SemanticCacheMiddleware` 构造参数注入，默认值 5000 |
| 7 | `invalidate_pattern` / `invalidate_all` 不存在：端口协议和实现均不支持 AC-2 要求的功能 | **P1** | Subtask 3.2 新增协议扩展和实现 |
| 8 | 测试覆盖缺口：缺少并发查询竞态、缓存键碰撞、嵌入生成超时降级、不同 weights 缓存隔离、TTL 续期测试 | **P1** | 补充缺失的测试场景（Subtask 1.4/3.5） |
| 9 | SINGLETON 生命周期安全性未说明：`_index_ready` 竞态和 Redis 重启后状态不正确 | **P2** | 补充 SINGLETON 安全性说明文档 |
| 10 | 六边形架构违反：SemanticCacheMiddleware 直接引用基础设施层 EventMetricsCollector | **P0** | 新建应用层 `CacheMetricsPort` Protocol，SemanticCacheMiddleware 通过端口注入，禁止直接依赖 EventMetricsCollector |
| 11 | 二级索引 key 与缓存 key 共享前缀，invalidate_pattern 存在误删风险 | **P1** | 索引 key 增加 `idx:` 中间分段（`idx:doc:{doc_id}`），文档明确 invalidate 方法边界契约 |
| 12 | CacheInvalidationHandler 直接操作 redis_client 处理二级索引，缓存实现细节暴露给事件处理器 | **P2** | 新增 `SemanticCache.invalidate_by_document_id()` 端口方法，封装二级索引逻辑，CacheInvalidationHandler 仅注入 SemanticCache |
| 13 | Task 4 使用 BDD 场景验证文件存在性，是反模式（BDD 应验证业务行为而非文件清单） | **P2** | 移除 Task 4 文件清单 BDD 场景，改为 Definition of Done checklist 条目 |
| 14 | 二级索引写入无 pipeline 批量操作，100 个文档需 100 次 Redis SADD 增加延迟 | **P1** | 文档补充 Redis pipeline 批量操作要求 |
| 15 | SCAN 无 COUNT 参数控制，大键空间下迭代次数过多 | **P2** | 文档补充 COUNT 参数约定（默认 100） |
| 16 | invalidate_all() 缺少安全声明，未说明是否清理二级索引 | **P2** | 文档补充 invalidate_all() 安全声明（仅影响 `sisys:cache:semantic:*` 前缀） |
| 17 | Redis 断连恢复测试缺少机制说明 | **P2** | 文档补充 `redis-py` 连接池懒连接恢复机制说明 |
| 18 | SemanticCacheMiddleware 构造参数含 `redis_client: aioredis.Redis`（应用层依赖基础设施层） | **P0** | 移除构造参数中的 `redis_client`；二级索引统一封装在 `RedisSemanticCache` 内部，通过 `SemanticCache.set(doc_ids=...)` 扩展参数传递文档 ID |
| 19 | 追溯矩阵 AC-4 引用不存在的 Subtask 1.7，且缺失 Task 4 行 | **P2** | AC-4 改为 `Subtask 1.1-1.2`；补充 Task 4 行 |
| 20 | P95<50ms 和命中率≥40% 不可在自动化测试中验证 | **P1** | P95 改为性能基线非 CI 门禁；命中率≥40% 改为生产监控目标，自动化测试仅验证 `hit_rate` 属性计算正确 |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 2026-08-12
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策 Decision Needed

- [ ] [{故事编号}-{优先级}-{问题编号}][Review][Patch | Defer] **[问题精准描述]** — 决策：[决策精准描述] [blind | edge | audit] `[相对路径]:[行号范围]`

#### 已修复 Patch

- [ ] [{故事编号}-{优先级}-{问题编号}][Review][Patch] [问题精准描述] [相对路径:行号] — [解决方案精准描述]

#### 已推迟 Defer

- [ ] [{故事编号}-{优先级}-{问题编号}][Review][Defer] [问题精准描述] — deferred，[原因精准描述]

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

## 📚 模板使用说明 Template Usage Guide

### 快速开始

1. 复制本模板到新文件
2. 替换所有 `[占位符]` 为实际内容
3. 根据 Story 类型调整覆盖率要求（见下表）
4. 确保 Task 0（SDD 规范定义）为必选前置
5. 每个 Task 包含自己的 TDD 循环（🔴红/🟢绿/🔄重构）
6. 填写 AC→Task→Subtask 追溯矩阵

### 适用场景与层类型对应关系

本模板适用于所有 Story 创建。根据六边形架构约束和 prd.md NFR 测试覆盖计划，Story 按层类型分类，每层有不同的测试要求：

| 层类型 | Story 类型 | 覆盖率要求 | 测试重点 | 示例 |
|--------|-----------|-----------|---------|------|
| **应用层 (Application)** | 应用层 Story | ≥85% | 用例逻辑/命令处理/查询处理/事务管理 | 本 Story（缓存编排） |
| **基础设施层 (Infrastructure)** | 基础设施层 Story | ≥75% | 连接测试/CRUD 操作/外部适配器/性能基准 | 本 Story（缓存失效监听器） |

> **骨架 Story 覆盖率豁免：** 本 Story 非骨架 Story，但代码量相对较小。如果标准覆盖率无法达到，临时调整为整体≥60%，应用层≥70%。

---

**故事版本/Story Version:** v1.3.0
**创建日期/Created:** 2026-08-12
**最后更新/Last Updated:** 2026-08-12
**更新说明/Description:**
- v1.3.0: Round 3 残留问题修复 — 移除 `SemanticCacheMiddleware` 构造参数中的 `redis_client`（P0，二级索引封装在 `RedisSemanticCache` 内部）；修正追溯矩阵 AC-4 引用不存在的 Subtask 1.7 并补充 Task 4 行（P2）；P95 改为性能基线非 CI 门禁、命中率≥40% 改为生产监控目标（P1）；补充 Gherkin 场景覆盖 weights 隔离和缓存数据损坏（P1）
- v1.2.0: Round 2 架构审查修复 — 引入 `CacheMetricsPort` 解耦应用层与基础设施层 `EventMetricsCollector`（P0）；明确二级索引 key 命名空间分层策略（`idx:doc:`）和 invalidate 边界契约（P1）；新增 `SemanticCache.invalidate_by_document_id()` 端口方法优化 `CacheInvalidationHandler` 注入（P2）；移除 Task 4 非 BDD 风格的文件清单验收场景（P2）；补充 Redis pipeline 批量操作（P1）、SCAN COUNT 参数（P2）、`invalidate_all()` 安全声明（P2）、Redis 断连恢复机制（P2）
- v1.1.0: Round 1 文档审查修订 — 修复 9 项问题（P0×3 + P1×5 + P2×1），包括：事件概念错配（MemoryChanged→DocumentProcessed）、缓存失效键策略重设计（二级索引）、P95 指标修正、缓存值类型修正、weights 纳入缓存键、avg_tokens_per_search 定义、协议扩展补充、测试覆盖补充、SINGLETON 安全性说明
- v1.0.0: 创建故事文件 — 语义缓存接入混合检索流水线
