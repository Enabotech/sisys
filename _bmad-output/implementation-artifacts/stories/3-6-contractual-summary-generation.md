# Story 3.6: 契约化结构化摘要生成

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 分析师,
**I want** 系统生成契约化结构化摘要（财务/市场/技术视角），输出符合预定义 JSON Schema,
**So that** 摘要质量可控且可验证，满足不同视角的战略分析需求。

### 业务价值

本 Story 是 Epic 3（智能检索与知识发现）的第六个故事（P0-6），对应 **FR-SR-06**（契约化摘要生成）。它填补了分层检索（Story 3.5）中 **L1 跨文档摘要**和 **L2 文档摘要**的骨架实现，将检索结果转化为符合预定义 JSON Schema 的结构化摘要。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **契约化摘要生成** | 摘要质量可控且可验证 | 输出强制遵守 JSON Schema 契约 |
| **多视角支持** | 财务/市场/技术不同视角的结构化摘要 | 三个视角独立 Schema，按需选择 |
| **L1/L2 分层检索就绪** | 填充 Story 3.5 的分层检索骨架 | `search_top_down(target_level="L1"/"L2")` 返回真实摘要 |
| **LLM 结构化输出** | 复用 Story 3.2a 的 `LLMClientPort.structured_generate()` | 通过 Pydantic Schema 验证的结构化输出 |
| **摘要存储** | 摘要结果持久化至 Qdrant 向量索引 | 摘要向量 upsert 至 Qdrant，支持后续检索 |

**来源:** [`epics_v1.0.md`](../../planning-artifacts/epics_v1.0.md) - Epic 3 Story 3.6，[`or.md` §5[1]`](../../planning-artifacts/or.md) - 契约化结构化摘要生成

**前置依赖（已就绪）:**
- Story 3.2a（LLM Client 基础设施 ✅ done）— 提供 `LLMClientPort.structured_generate()` 方法，支持 Pydantic Schema 驱动的结构化输出
- Story 3.5（分层检索 L1-L4 ✅ review）— 提供 `LayeredRetrievalPort` 协议、`LayeredRetrievalService` 骨架（L1/L2 返回空列表，需本 Story 填充）
- Story 3.4（RRF 融合排序 ✅ done）— 提供 `HybridSearchService` 三路检索编排，用于获取检索上下文
- Story 1.6（Qdrant 向量层 ✅ done）— 提供 `L3VectorPort` 用于摘要向量索引
- Story 3.1a（Dense 语义检索 ✅ done）— 提供 `DenseSemanticSearchService` 和 `EmbeddingServicePort`
- Story 3.8（高保真溯源 ✅ done）— 提供引文三元组特征，摘要可携带溯源信息

**后续依赖:** Story 3.7（检索相关性评估）、Story 3.11（事实有效期标签管理）、Story 12.3（摘要质量评估）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 摘要 Schema 契约定义（财务/市场/技术视角）

**Given** 系统需要预定义的结构化摘要 Schema
**When** 定义财务/市场/技术三个视角的摘要 Schema
**Then** 每个 Schema 是 Pydantic BaseModel 子类，定义在应用层（`src/application/`）
**And** 每个 Schema 包含三个必需字段：`summary_text`（摘要正文，`Field(min_length=10, max_length=5000)` 防止空摘要或超长内容）、`key_points`（关键要点列表，`Field(min_length=1, max_length=10)` 限制列表项数，单个字符串 `Field(min_length=1, max_length=200)` 防止空要点）、`confidence_score`（置信度 0-1，`Field(ge=0.0, le=1.0)`，语义为"LLM 自评置信度，基于检索结果相关性和生成质量"）
**And** 每个 Schema 包含视角特有字段（见下文）
**And** 所有 Schema 通过 Pydantic V2 验证，Schema 验证通过率 100%

**验证标准/Validation Criteria:**
- [ ] `FinancialSummary` Schema 位于 `src/application/services/summary_schemas.py`（或 `src/application/use_cases/` 下）
  - 固有字段：`summary_text: str`、`key_points: list[str]`、`confidence_score: float`
  - 视角特有字段：`revenue_trend: str`（收入趋势描述）、`profit_analysis: str`（利润分析）、`risk_factors: list[str]`（风险因素）、`market_position: str`（市场地位）
- [ ] `MarketSummary` Schema
  - 固有字段同上
  - 视角特有字段：`market_size: str`（市场规模）、`competitive_landscape: str`（竞争格局）、`growth_drivers: list[str]`（增长驱动力）、`customer_insights: str`（客户洞察）
- [ ] `TechnicalSummary` Schema
  - 固有字段同上
  - 视角特有字段：`technology_stack: str`（技术栈）、`innovation_points: list[str]`（创新点）、`technical_risks: list[str]`（技术风险）、`architecture_overview: str`（架构概述）
- [ ] Schema 定义在 `src/application/`（非 domain 层），应用层可依赖 Pydantic
- [ ] 所有字段类型正确，`confidence_score` 范围约束 `Field(ge=0.0, le=1.0)`，语义为"LLM 自评置信度，基于检索结果相关性和生成质量"
- [ ] Schema 验证通过率 100%（Pydantic V2 严格模式）

### AC-2: 摘要生成服务端口契约

**Given** 系统需要统一的摘要生成抽象
**When** 定义 `SummaryGenerationPort` 协议
**Then** 包含 `generate_summary()` 核心方法，支持视角选择
**And** 领域层定义零外部依赖（仅 Python 标准库 + Protocol）
**And** 输入：检索结果列表 + 视角类型 + 可选配置
**And** 输出：对应视角 Schema 实例

**验证标准/Validation Criteria:**
- [ ] `SummaryGenerationPort` 定义于 `src/domain/ports/summary_generation.py`（Protocol，`@runtime_checkable`）
- [ ] `SearchResult` 从 `src/domain/ports/l3_vector.py` 导入（与 `LayeredRetrievalPort` 相同的现有模式，同域内类型引用，不引入新抽象）
- [ ] 方法签名：`async generate_summary(query_text, search_results, perspective, config=None, tenant_id=None) -> Any`
  - `query_text: str` — 原始查询文本
  - `search_results: list[SearchResult]` — 分层检索结果（L3/L4 内容）
  - `perspective: str` — 视角类型（"financial"/"market"/"technical"）
  - `config: LLMConfig | None` — 可选 LLM 调用配置
  - `tenant_id: str | None` — 可选租户 ID（多租户隔离，摘要存储/检索需透传，与 `LayeredRetrievalPort.search_top_down()` 的租户隔离模式一致）
  - 返回对应视角 Schema 的 Pydantic 实例（`Any` 类型，领域层不依赖 pydantic）
- [ ] 端口注册于 `composition_root.py`，通过 `register_port()` 注册为 `summary_generation_service` 端口
- [ ] 端口具备唯一名称、版本、interface、impl、module（必填五参数）及 owner、兼容策略（可选元数据）
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_summary_generation.py`）

### AC-3: 摘要生成异常体系

**Given** 摘要生成过程中可能发生多种错误
**When** 定义摘要生成异常类
**Then** 新增 `summary` 子域，分配唯一异常编码
**And** 继承适当的基类层次结构

**验证标准/Validation Criteria:**
- [ ] `SummaryGenerationError`（EXCEPTION_290）— 继承 `BusinessException`，摘要生成整体失败
  - 构造器参数：`perspective: str`（视图类型）、`query_text: str`（查询文本，截断至 100 字符）
- [ ] `SummaryPerspectiveNotSupportedError`（EXCEPTION_291）— 继承 `ValidationError`，不支持的视角类型
  - 构造器参数：`perspective: str`（不支持的视角）
- [ ] 异常编码在 `_code_ranges.py` 注册 `summary` 子域（290, 299）及 `_CLASS_TO_SUBDOMAIN` 映射
- [ ] 异常在 `__init__.py` 导出，在 `EXCEPTION_HTTP_MAP` 注册
- [ ] 无编码碰撞（`grep -rw "EXCEPTION_29[0-9]" src/` 零输出）
- [ ] HTTP 映射测试覆盖

### AC-4: 摘要生成应用服务

**Given** 摘要生成端口契约已定义
**When** 实现 `SummaryGenerationService`
**Then** 注入 `LLMClientPort` 和 `LayeredRetrievalPort` 等依赖
**And** 根据视角类型生成结构化摘要
**And** 输出通过 Pydantic Schema 验证

**验证标准/Validation Criteria:**
- [ ] `SummaryGenerationService` 位于 `src/application/services/summary_generation_service.py`
- [ ] 构造函数注入 `llm_client: LLMClientPort`（或 `Any` 保持松耦合）
- [ ] 构造函数注入 `layered_retrieval: LayeredRetrievalPort`（必需，用于获取检索上下文和填充 L1/L2 骨架）
- [ ] 构造函数注入 `embedding_service: EmbeddingServicePort`（必需，用于摘要向量生成）
- [ ] 构造函数注入 `l3_vector: L3VectorPort`（或 `Any`，必需，用于摘要向量持久化 upsert 和 L1/L2 检索）
- [ ] 实现 `generate_summary()` 方法，签名与端口契约一致
- [ ] 内部根据 `perspective` 参数选择对应的 Pydantic Schema 和 Prompt 模板
- [ ] 调用 `LLMClientPort.structured_generate()` 传入 Schema 和 Prompt
- [ ] 返回验证后的 Pydantic Schema 实例
- [ ] 支持视角映射：`"financial"` → `FinancialSummary`，`"market"` → `MarketSummary`，`"technical"` → `TechnicalSummary`
- [ ] 不支持的视角抛出 `SummaryPerspectiveNotSupportedError`
- [ ] LLM 调用失败抛出 `SummaryGenerationError`（包装原始 LLM 异常）
- [ ] 摘要生成延迟 P95 < 30 秒（含 LLM 调用）
- [ ] LLM 异常处理：捕获 `LLMAPIError` 和 `ServiceUnavailableError` → 包装为 `SummaryGenerationError`（业务失败）；`LLMResponseError`（Schema 验证失败）→ 同样包装为 `SummaryGenerationError`（附录原始异常信息）；`LLMConfigError` → 透传不包装（配置错误不属于摘要生成失败）
- [ ] 降级策略：LLM 调用失败时记录 WARNING 日志，抛出 `SummaryGenerationError`

### AC-5: 摘要 Prompt 模板

**Given** 不同视角需要不同的摘要 Prompt
**When** 定义 Prompt 模板
**Then** 每个视角有独立的 System Prompt 和 User Prompt 模板
**And** Prompt 模板注入检索上下文

**验证标准/Validation Criteria:**
- [ ] Prompt 模板定义在 `src/application/services/summary_prompts.py`（或与 Service 同文件）
- [ ] 每个视角的 System Prompt 包含：
  - 角色定义（如 "你是一位资深财务分析师"）
  - 输出格式约束（强制遵守 JSON Schema）
  - 质量要求（准确性、完整性、简洁性）
- [ ] 每个视角的 User Prompt 包含：
  - 查询文本
  - 检索结果上下文（格式化的文档内容列表）
  - 输出要求
- [ ] 模板使用 Python f-string 格式，支持动态注入（统一格式，无需额外依赖，与项目技术栈一致）
- [ ] 所有 Prompt 模板通过单元测试验证（变量替换正确性）

### AC-6: 摘要结果存储与检索（L2 文档摘要实现）

**Given** 摘要生成完成
**When** 摘要结果持久化至 Qdrant 向量索引
**Then** 摘要向量可被 `LayeredRetrievalService.search_top_down(target_level="L2")` 检索
**And** 替换 Story 3.5 的 L2 骨架实现（返回空列表）

**验证标准/Validation Criteria:**
- [ ] 摘要结果通过 `EmbeddingServicePort.embed_documents()` 生成向量
- [ ] 摘要向量通过 `L3VectorPort.upsert_points()` 写入 Qdrant
  - collection 名称：`"document_summaries"`（独立 collection，与文档切片分离）
  - collection 创建策略：懒创建（首次 upsert 前调用 `l3_vector.collection_exists()` 检查，不存在时调用 `l3_vector.create_collection()` 创建，vector_size=1024 对齐 bge-m3 维度）
  - payload 包含：`perspective`（视角类型）、`summary_text`（摘要文本）、`key_points`（关键要点列表）、`confidence_score`（置信度）、`source_document_ids`（来源文档 ID 列表）、`index_level`（"L2"）、`created_at`（时间戳）
  - 点 ID 使用 `f"summary-{perspective}-{uuid4}"` 格式
- [ ] 更新 `LayeredRetrievalService.search_top_down(target_level="L2")`：
  - 在 `document_summaries` collection 中执行 Dense 检索（**L2 硬编码 collection 名为 `"document_summaries"`，与顶层 `collection` 参数解耦**，避免 L3/L4 检索语义冲突）
  - 返回 `list[SearchResult]`，payload 包含摘要元数据
  - 移除原有骨架（返回空列表）逻辑
  - 日志记录 `INFO: L2 文档摘要检索执行成功`
- [ ] **同步更新 `search_bottom_up` 骨架**：`LayeredRetrievalService.search_bottom_up()` 第 179-185 行包含与 `search_top_down` 完全相同的 L1/L2 骨架逻辑。实现时**必须同步填充** `search_bottom_up(target_level="L1"/"L2")`：复用 `_search_l4_direct` 的 `self._dense_search.search()` Dense 检索模式，在对应 collection 中执行检索，移除骨架逻辑，日志记录 `INFO: L1/L2 文档摘要检索执行成功`，降级策略与 `search_top_down` 一致（collection 不存在或 Qdrant 异常时降级返回空列表 + WARNING 日志）。
- [ ] 摘要检索延迟 P95 < 200ms（Dense 检索）
- [ ] 降级策略：摘要 collection 不存在时降级为骨架（返回空列表，WARNING 日志）；Qdrant 查询异常时捕获 `Exception` 降级返回空列表 + WARNING 日志
- [ ] **L1/L2 Dense 检索调用模式**：复用 `_search_l3_direct`/`_search_l4_direct` 的 `self._dense_search.search()` 模式（端到端 Dense 检索：内部自动 `embed_query()` + `vector.search()`），**禁止**使用 `_search_top_down_l3_to_l4` 的私有属性访问模式（`self._dense_search._embedding.embed_query()`）

### AC-7a: 跨文档摘要生成（L1 生成）

**Given** 多个文档摘要已存储
**When** 执行多文档摘要聚合
**Then** 系统聚合相关文档摘要生成跨文档摘要

**验证标准/Validation Criteria:**
- [ ] `SummaryGenerationService` 扩展 `generate_cross_document_summary()` 方法（可选，或复用 `generate_summary` 加 `cross_document=True` 参数）
- [ ] 跨文档摘要生成流程：
  1. 调用 `LayeredRetrievalPort.search_top_down(target_level="L2")` 获取已有 L2 摘要（L2 硬编码 `document_summaries` collection，与顶层 `collection` 参数解耦）
  2. 聚合 Top-K 摘要结果作为上下文
  3. 调用 `LLMClientPort.structured_generate()` 生成跨文档摘要
  4. 通过 `EmbeddingServicePort.embed_documents()` 生成向量
  5. 通过 `L3VectorPort.upsert_points()` 写入 Qdrant（collection: `"cross_document_summaries"`，懒创建策略）
  6. payload 包含：`perspective`、`summary_text`、`key_points`、`confidence_score`、`source_document_ids`、`index_level`（"L1"）、`created_at`
- [ ] 降级策略：L2 摘要不足（< 2 条）时降级为骨架（返回空列表，WARNING 日志）

### AC-7b: 跨文档摘要检索（L1 检索实现）

**Given** 跨文档摘要已存储至 Qdrant
**When** 执行 L1 层级检索
**Then** 返回跨文档摘要结果
**And** 替换 Story 3.5 的 L1 骨架实现（返回空列表）

**验证标准/Validation Criteria:**
- [ ] 更新 `LayeredRetrievalService.search_top_down(target_level="L1")`：
  - 在 `cross_document_summaries` collection 中执行 Dense 检索（**L1 硬编码 collection 名为 `"cross_document_summaries"`，与顶层 `collection` 参数解耦**）
  - 返回 `list[SearchResult]`，payload 包含跨文档摘要元数据（含 `index_level: "L1"`）
  - 移除原有骨架（返回空列表）逻辑
  - 日志记录 `INFO: L1 跨文档摘要检索执行成功`
- [ ] 降级策略：L1 collection 不存在时降级为骨架（返回空列表，WARNING 日志）；Qdrant 查询异常时捕获 `Exception` 降级返回空列表 + WARNING 日志
- [ ] **同步更新 `search_bottom_up` 骨架**：`LayeredRetrievalService.search_bottom_up(target_level="L1")` 的骨架逻辑同样同步填充，复用 `self._dense_search.search()` 模式在 `cross_document_summaries` collection 中检索，降级策略与 `search_top_down` 一致

### AC-8: 摘要 API 端点

**Given** 摘要生成服务已就绪
**When** 用户通过 API 请求摘要生成
**Then** 返回结构化摘要结果
**And** 包含元数据（视角、置信度、来源文档）

**验证标准/Validation Criteria:**
- [ ] API 路由位于 `src/interfaces/api/summary.py`（或与 `search.py` 合并）
- [ ] `POST /api/v1/search/summary` 端点
  - 请求体：`{"query_text": str, "perspective": str, "top_k": int (可选, 默认10, 控制检索结果数量), "tenant_id": str | None (可选)}`
  - 响应体：`{"summary": Schema实例, "query_text": str, "perspective": str, "confidence_score": float, "source_documents": list[str]}`
- [ ] 在 `src/interfaces/api/app.py` 中通过 `app.include_router()` 注册路由
- [ ] 更新 `docs/api/openapi.yaml` 添加 `/api/v1/search/summary` 端点
- [ ] API 契约测试通过（`tests/contracts/test_api_contract_summary.py`）
- [ ] 所有 API 路由通过认证中间件

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 事件定义位于 `src/domain/events/`
- [ ] 使用标准库实现领域事件校验（如 dataclass / Enum / 自定义验证），禁止在领域层依赖 Pydantic
- [ ] 本 Story **不新增**领域事件（摘要生成是同步调用，不触发异步事件）
- [ ] 如需异步摘要生成，定义 `SummaryGenerated` 事件（可选，MVP 暂不实现）

#### 数据模型 (Data Models)
- [ ] 摘要 Schema 定义位于 `src/application/services/summary_schemas.py`（Pydantic BaseModel，应用层允许依赖 Pydantic）
- [ ] 摘要 Schema 包括：`FinancialSummary`、`MarketSummary`、`TechnicalSummary`
- [ ] 每个 Schema 包含固有字段 + 视角特有字段（见 AC-1）
- [ ] 所有 Schema 通过 Pydantic V2 严格模式验证

#### 统一端口定义注册与管理 (Port Contract)
- [ ] 端口契约定义位于 `src/domain/ports/summary_generation.py`（新增）
- [ ] 端口注册中心位于 `src/domain/ports/registry.py`，所有端口必须登记为 `PortSpec`
- [ ] 端口实现仅可在 `src/composition_root.py` 统一注册，禁止业务代码直接实例化具体实现
- [ ] 端口解析器位于 `src/domain/ports/resolver.py`，业务代码只通过抽象解析实现
- [ ] 端口契约门禁位于 `src/domain/ports/contract_gate.py`，端口变更必须通过兼容性检查
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_summary_generation.py`）
- [ ] 接口命名符合单一职责，禁止同义接口重复定义
- [ ] 端口注册时提供 module 参数（register_port() 的必需参数）
- [ ] 端口具备唯一名称、版本、owner、兼容策略、module
- [ ] 跨模块调用仅依赖抽象接口，不直接依赖实现类
- [ ] 端口变更配套契约测试与兼容性检查
- [ ] 禁止在服务文件中本地定义 Protocol / Port 抽象

#### 端口契约清单执行约束（强制）
- [ ] 本模板中的端口清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口，禁止未同步更新 registry / resolver / contract test
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增/修改的领域异常必须在 Task 0 中完成设计，禁止在实现 Task 中临时定义。
> **适用范围：** 本清单仅针对定义在 `src/domain/exceptions/` 下、继承自 `DomainError`（别名 `BaseException`）的**领域异常**。
> **不在本清单范围：** FastAPI/Pydantic 框架原生异常、第三方 SDK 原始异常（由 `ErrorMapper` 映射）。
> **禁止 `raise ValueError`：** 所有验证失败均使用领域异常体系。
> 完整检查清单与全量异常分类详见 [`sisys-uni-exception-design.md §3.12`](../architecture/sisys-uni-exception-design.md#312-异常注册检查清单)。

- [ ] **归属模块与基类** — 新增 `summary` 子域（290-299）：
    - `SummaryGenerationError`（EXCEPTION_290）→ 继承 `BusinessException`，摘要生成整体失败
    - `SummaryPerspectiveNotSupportedError`（EXCEPTION_291）→ 继承 `ValidationError`，不支持的视角
- [ ] **唯一编码分配** — 从 `summary` 子域（290-291）选取，`grep -rw "EXCEPTION_29[0-9]" src/` 验证无碰撞
- [ ] **构造器参数设计** — 携带视角上下文（`perspective`、`query_text` 等），通过 `context` 字典暴露
- [ ] **消息安全性审查** — 错误消息面向调用方可理解，不泄露 SQL/堆栈等内部实现细节
- [ ] **编码注册** — 更新 `_code_ranges.py` 和 `test_code_ranges.py`：
    - `CODE_RANGES` 新增 `"summary": (290, 299)`
    - `_CLASS_TO_SUBDOMAIN` 新增 `"SummaryGenerationError": "summary"`、`"SummaryPerspectiveNotSupportedError": "summary"`
    - `test_code_ranges.py` 中 `allowed_child_parent_subdomains` 新增 `("summary", "business")`（因 `summary` 子域继承 `BusinessException`/`ValidationError`，均属 `business` 域）
- [ ] **HTTP 状态码映射** — `EXCEPTION_HTTP_MAP` 注册：
    - `SummaryGenerationError`（EXCEPTION_290）→ `500`（继承 `BusinessException` 但语义为服务端摘要生成失败，非请求方错误）
    - `SummaryPerspectiveNotSupportedError`（EXCEPTION_291）→ `400`（参数校验错误，继承 `ValidationError` 合理）
- [ ] **导出完整性** — 模块 `__all__` + 包 `__init__.py` 导入 + `EXCEPTION_HTTP_MAP` 映射
- [ ] **测试覆盖** — 构造/`to_dict()`/HTTP 映射/编码唯一性 + 子域范围测试全部通过：
    - `poetry run pytest tests/unit/domain/exceptions/ -v`（含 `test_error_code_uniqueness.py` + `test_code_ranges.py`）
    - `poetry run pytest tests/unit/interfaces/api/test_exception_handlers.py -v`
- [ ] **BDD 验收场景** — 异常路径的 Gherkin 场景纳入 Edge Cases

#### API 契约 (API Contract)
- [ ] 遵循 OpenAPI 标准的 API 契约定义位于 `docs/api/openapi.yaml`
- [ ] API 契约测试通过（`tests/contracts/test_api_contract_summary.py`）
- [ ] API 版本管理正确（`/api/v1/search/summary`）

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
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_contractual_summary.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_contractual_summary.py`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径** — 响应体验证 `error.code` + `error.message` + `request_id`

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

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | 摘要 Schema | Pydantic Schema 定义、字段验证、反序列化 | `tests/unit/application/services/test_summary_schemas.py` | Task 1 |
| **TDD 单元测试** | 摘要生成端口 | 端口契约方法签名、参数校验 | `tests/unit/domain/ports/test_summary_generation_port.py` | Task 1 |
| **TDD 单元测试** | 摘要生成服务 | 多视角生成、LLM 调用、Schema 验证 | `tests/unit/application/services/test_summary_generation_service.py` | Task 2 |
| **TDD 单元测试** | 摘要异常 | 构造/属性/`to_dict()`/cause 链/HTTP 映射 | `tests/unit/domain/exceptions/test_summary_exceptions.py` | Task 1 |
| **TDD 单元测试** | 摘要 Prompt 模板 | 模板变量替换、每个视角的 Prompt 完整性 | `tests/unit/application/services/test_summary_prompts.py` | Task 2 |
| **SDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_contractual_summary.feature` | Task 0 |
| **SDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_contractual_summary.py` | Task 0 |
| **SDD 验收测试** | 收尾验收场景 | `src` 与测试目录完成清单最终确认 | `test_acceptance_contractual_summary.feature` | Task 5 |
| **SDD 验收测试** | 收尾 BDD 步骤实现 | 完成清单断言与步骤函数 | `test_acceptance_contractual_summary.py` | Task 5 |
| **SDD 契约测试** | 端口契约 | 端口注册、版本、兼容性、实现解析 | `tests/contracts/test_port_contract_summary_generation.py` | Task 0 |
| **SDD 契约测试** | API 契约 | OpenAPI 端点、请求/响应结构 | `tests/contracts/test_api_contract_summary.py` | Task 0 |
| **TDD 领域异常测试** | 异常 HTTP 映射 | HTTP 映射/状态码/响应结构 | `tests/unit/interfaces/api/test_exception_handlers.py` | Task 1 |
| **TDD 领域异常测试** | 编码唯一性 | 所有异常类 `code` 无碰撞 | `tests/unit/domain/exceptions/test_error_code_uniqueness.py` | Task 1 |
| **TDD 领域异常测试** | 编码子域范围 | 子域范围/继承链一致性 | `tests/unit/domain/exceptions/test_code_ranges.py` | Task 1 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖、禁止跨层引用 | `tests/unit/architecture/test_arch_summary_generation.py` | Task 4 |
| **集成测试** | 层间协作 | LLMClientPort + SummaryGenerationService 协作 | `tests/integration/test_integration_contractual_summary.py` | Task 3 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（核心业务流，摘要生成编排，CI 通过 `scripts/check_coverage_gates.py` 校验）
- [ ] **领域层覆盖率 ≥90%**（端口契约协议，CI 通过 `scripts/check_coverage_gates.py` 校验）
- [ ] **接口层覆盖率 ≥85%**（API 路由，请求响应验证；项目级建议指标，非 CI 强制门禁）
- [ ] **集成测试覆盖率 ≥75%**（`pytest --cov=tests/integration --cov-fail-under=75`；项目级建议指标，非 CI 强制门禁）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **事务隔离** | 集成测试使用 transaction rollback | 数据泄漏导致随机失败 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突或状态污染 |
| **外部服务隔离** | LLM 调用使用 Mock（单元测试）或真实 API（集成测试） | 真实数据被污染 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突导致并行失败 |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **BDD async 配合** | BDD 步骤函数不使用 @pytest.mark.asyncio，用 event_loop.run_until_complete() 运行 async | 直接用 @pytest.mark.asyncio 会导致 BDD context 数据丢失 |
| **LLM Mock 策略** | 单元测试使用 `AsyncMock(spec=LLMClientPort)` 模拟 LLM 调用；集成测试使用真实 `LitellmLLMClient`（需配置 LLM 环境变量） | 测试不可重复或依赖外部 API |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源（如 `test_*`）
- ❌ Fixture 假设清理顺序（必须显式声明依赖）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续5次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 摘要 Schema 契约定义 | Task 0 | SDD 规范定义 | `test_summary_schemas.py` |
| AC-1 | 摘要 Schema 契约定义 | Task 1 | TDD Schema 实现 | `test_summary_schemas.py` |
| AC-2 | 摘要生成服务端口契约 | Task 0 | SDD 规范定义 | `test_port_contract_summary_generation.py` |
| AC-2 | 摘要生成服务端口契约 | Task 1 | TDD 端口实现 | `test_summary_generation_port.py` |
| AC-3 | 摘要生成异常体系 | Task 1 | TDD 异常定义 | `test_summary_exceptions.py` |
| AC-4 | 摘要生成应用服务 | Task 2 | TDD 服务实现 | `test_summary_generation_service.py` |
| AC-5 | 摘要 Prompt 模板 | Task 2 | TDD Prompt 模板 | `test_summary_prompts.py` |
| AC-6 | 摘要结果存储与检索（L2） | Task 3 | TDD 存储实现 | `test_integration_contractual_summary.py` |
| AC-7a | 跨文档摘要生成（L1 生成） | Task 3 | TDD 跨文档实现 | `test_integration_contractual_summary.py` |
| AC-7b | 跨文档摘要检索（L1 检索） | Task 3 | TDD L1 填充 | `test_integration_contractual_summary.py` |
| AC-8 | 摘要 API 端点 | Task 3 | TDD API 端点 | `test_api_contract_summary.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-8

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。这是 SDD 规范驱动的基础。

- [ ] Subtask 0.1: 定义摘要 Schema 契约（`FinancialSummary`、`MarketSummary`、`TechnicalSummary`）
- [ ] Subtask 0.2: 创建/更新 `docs/api/openapi.yaml`（新增 `POST /api/v1/search/summary` 端点）
- [ ] Subtask 0.3: 编写端口契约测试 `tests/contracts/test_port_contract_summary_generation.py`
- [ ] Subtask 0.4: 编写 API 契约测试 `tests/contracts/test_api_contract_summary.py`
- [ ] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_contractual_summary.feature`
- [ ] Subtask 0.6: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_contractual_summary.py`
- [ ] Subtask 0.7: 运行所有 Task 0 测试（端口契约测试 + API 契约测试 + 验收测试），确认全部失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 所有 Task 0 测试（端口契约测试 + API 契约测试 + 验收测试）运行失败（预期行为，红阶段确认）

---

### Task 1: 领域层端口契约 + 摘要 Schema + 异常体系

**关联 AC:** AC-1, AC-2, AC-3

> **说明：** 本 Task 定义领域层端口契约（`SummaryGenerationPort`）、应用层摘要 Schema（`FinancialSummary`/`MarketSummary`/`TechnicalSummary`）和异常体系（`SummaryGenerationError`、`SummaryPerspectiveNotSupportedError`），是后续所有实现 Task 的依赖基础。

#### TDD 循环 [A]：摘要 Schema 契约

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_summary_schemas.py`（Schema 字段验证、反序列化、`confidence_score` 范围） |
| 🟢 绿 | 实现 `src/application/services/summary_schemas.py`（`FinancialSummary`、`MarketSummary`、`TechnicalSummary`） |
| 🔄 重构 | 添加 docstring、类型注解、字段验证器 |

- [ ] Subtask 1.1: 🔴 红 — 编写摘要 Schema 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现摘要 Schema
- [ ] Subtask 1.3: 🔄 重构 — 优化 Schema 代码

#### TDD 循环 [B]：摘要生成端口契约

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_summary_generation_port.py`（端口契约签名验证） |
| 🟢 绿 | 实现 `src/domain/ports/summary_generation.py`（`SummaryGenerationPort` Protocol） |
| 🔄 重构 | 添加 docstring、类型注解、架构决策注释 |

- [ ] Subtask 1.4: 🔴 红 — 编写摘要生成端口失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 `SummaryGenerationPort` Protocol
- [ ] Subtask 1.6: 🔄 重构 — 优化端口代码

#### TDD 循环 [C]：摘要生成异常体系

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_summary_exceptions.py`（异常构造/序列化） |
| 🟢 绿 | 实现 `src/domain/exceptions/summary_exceptions.py` |
| 🔄 重构 | 注册异常到 `_code_ranges.py`、`__init__.py`、`EXCEPTION_HTTP_MAP`，更新 `test_code_ranges.py` |

- [ ] Subtask 1.7: 🔴 红 — 编写摘要异常失败测试
- [ ] Subtask 1.8: 🟢 绿 — 实现 `SummaryGenerationError` 和 `SummaryPerspectiveNotSupportedError`
- [ ] Subtask 1.9: 🔄 重构 — 注册异常到 `_code_ranges.py`（新增 `summary` 子域 290-299）、`__init__.py`、`EXCEPTION_HTTP_MAP`、`test_code_ranges.py`

**完成标准/Definition of Done:**
- [ ] `FinancialSummary`、`MarketSummary`、`TechnicalSummary` Schema 定义完成
- [ ] `SummaryGenerationPort` 端口契约定义完成
- [ ] `SummaryGenerationError`（EXCEPTION_290）和 `SummaryPerspectiveNotSupportedError`（EXCEPTION_291）定义完成
- [ ] 异常体系完整注册（`_code_ranges.py`/`__init__.py`/`EXCEPTION_HTTP_MAP`）
- [ ] 所有 TDD 循环测试通过
- [ ] 异常编码无碰撞（`grep -rw "EXCEPTION_29[0-9]" src/` 零输出）

---

### Task 2: 摘要生成应用服务 + Prompt 模板 — 含完整 TDD 循环

**关联 AC:** AC-4, AC-5

> **说明：** 本 Task 实现 `SummaryGenerationService` 应用层编排服务，注入 `LLMClientPort` 驱动结构化摘要生成，并定义每个视角的 Prompt 模板。

#### TDD 循环 [A]：摘要 Prompt 模板

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_summary_prompts.py`（模板变量替换、每个视角的 System/User Prompt 完整性、HTML/特殊字符转义） |
| 🟢 绿 | 实现 `src/application/services/summary_prompts.py`（三个视角的 System/User Prompt 模板字典） |
| 🔄 重构 | 统一 Prompt 格式、提取公共模板、添加注释说明 |

- [ ] Subtask 2.1: 🔴 红 — 编写 Prompt 模板失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 Prompt 模板
- [ ] Subtask 2.3: 🔄 重构 — 优化 Prompt 格式

#### TDD 循环 [B]：摘要生成服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_summary_generation_service.py`（多视角生成、LLM 调用验证、Schema 验证、视角不支持异常、LLM 调用失败异常、空检索结果边界、空查询文本、LLM 返回空摘要、Top-K 无效值） |
| 🟢 绿 | 实现 `src/application/services/summary_generation_service.py`（`SummaryGenerationService` 类） |
| 🔄 重构 | 添加降级策略、日志、异常链包装 |

- [ ] Subtask 2.4: 🔴 红 — 编写摘要生成服务失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 `SummaryGenerationService`
- [ ] Subtask 2.6: 🔄 重构 — 优化服务代码

**完成标准/Definition of Done:**
- [ ] `SummaryGenerationService` 完整实现
- [ ] 三个视角的 Prompt 模板定义完成
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥85%（应用层）
- [ ] LLM 调用失败时抛出 `SummaryGenerationError`，不支持的视角抛出 `SummaryPerspectiveNotSupportedError`

---

### Task 3: L1/L2 分层检索填充 + 摘要存储 + API 端点

**关联 AC:** AC-6, AC-7a, AC-7b, AC-8

> **说明：** 本 Task 将摘要结果持久化至 Qdrant，填充 Story 3.5 的 L1/L2 骨架实现，并暴露 API 端点。

#### TDD 循环 [A]：摘要结果存储与 L2 检索

> **Qdrant 策略：** 集成测试使用 Mock L3VectorPort（`AsyncMock(spec=L3VectorPort)` + `_make_l3_vector()` 工厂函数，Qdrant 为重型基础设施依赖，遵循项目惯例）。Mock 验证 `upsert_points()` 调用参数（collection 名称、点 ID 格式、payload 字段完整性），`search()` 返回预定义结果集验证检索逻辑。如需真实 Qdrant 验证，使用 `TestTenant` UUID 前缀隔离 + `pytest.skip("Qdrant 服务不可用")` 动态跳过。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_contractual_summary.py`（摘要向量 upsert 到 Qdrant、L2 检索返回摘要） |
| 🟢 绿 | 实现摘要存储逻辑（`SummaryGenerationService._store_summary()`）+ 修改 `LayeredRetrievalService` 的 L2 骨架 |
| 🔄 重构 | 优化存储性能、添加降级策略 |

- [ ] Subtask 3.1: 🔴 红 — 编写摘要存储 + L2 检索失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现摘要存储和 L2 检索
- [ ] Subtask 3.3: 🔄 重构 — 优化存储和检索逻辑

#### TDD 循环 [B]：跨文档摘要（L1）

> **⚠️ 前置依赖：** TDD 循环 [B] 依赖 [A] 的完成。L1 跨文档摘要生成需调用 `LayeredRetrievalPort.search_top_down(target_level="L2")` 获取已有 L2 摘要，因此 L2 存储逻辑必须先在 [A] 中实现并验证通过。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_contractual_summary.py`（跨文档摘要生成、L1 检索） |
| 🟢 绿 | 实现跨文档摘要生成 + 修改 `LayeredRetrievalService` 的 L1 骨架 |
| 🔄 重构 | 优化聚合逻辑、添加降级策略 |

- [ ] Subtask 3.4: 🔴 红 — 编写跨文档摘要 + L1 检索失败测试
- [ ] Subtask 3.5: 🟢 绿 — 实现跨文档摘要和 L1 检索
- [ ] Subtask 3.6: 🔄 重构 — 优化跨文档聚合逻辑

#### TDD 循环 [C]：摘要 API 端点

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/contracts/test_api_contract_summary.py`（请求/响应 Schema、状态码、认证） |
| 🟢 绿 | 实现 `src/interfaces/api/summary.py`（`POST /api/v1/search/summary` 路由）+ 注册到 `app.py` |
| 🔄 重构 | 统一错误处理、添加请求验证 |

- [ ] Subtask 3.7: 🔴 红 — 编写 API 端点失败测试
- [ ] Subtask 3.8: 🟢 绿 — 实现摘要 API 路由
- [ ] Subtask 3.9: 🔄 重构 — 优化 API 响应格式

#### 端口注册到 composition_root.py

> **⚠️ 前置依赖：** Subtask 3.10 必须在 TDD 循环 [C]（API 端点）之前完成。API 路由处理器依赖 `resolver.resolve("summary_generation_service")` 获取服务实例，未注册端口将导致路由初始化失败。

- [ ] Subtask 3.10: 在 `src/composition_root.py` 中注册 `summary_generation_service` 端口
  - 端口名称：`summary_generation_service`
  - 生命周期：`Lifetime.SCOPED`（与 `layered_retrieval_service`、`dense_search_service` 等同类服务保持一致）
  - 实现：工厂函数 `lambda resolver: SummaryGenerationService(...)` 注入依赖
- [ ] Subtask 3.11: 更新端口契约测试 `tests/contracts/test_port_contract_summary_generation.py`

**完成标准/Definition of Done:**
- [ ] 摘要结果存储至 Qdrant（`document_summaries` collection）
- [ ] `LayeredRetrievalService.search_top_down(target_level="L2")` 返回真实摘要结果
- [ ] `LayeredRetrievalService.search_bottom_up(target_level="L2")` 同步返回真实摘要结果
- [ ] 跨文档摘要存储至 Qdrant（`cross_document_summaries` collection）
- [ ] `LayeredRetrievalService.search_top_down(target_level="L1")` 返回真实跨文档摘要
- [ ] `LayeredRetrievalService.search_bottom_up(target_level="L1")` 同步返回真实跨文档摘要
- [ ] `POST /api/v1/search/summary` API 端点可用
- [ ] 端口注册完成，集成测试通过

---

### Task 4: SDD 架构约束验证测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [ ] Subtask 4.1: 创建 `tests/unit/architecture/test_arch_summary_generation.py`
- [ ] Subtask 4.2: 验证领域层零外部依赖（`SummaryGenerationPort` 仅导入标准库）
- [ ] Subtask 4.3: 验证依赖方向正确（domain → application → interfaces/infrastructure）
- [ ] Subtask 4.4: 验证 `composition_root.py` 注册完整性
- [ ] Subtask 4.5: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**
- [ ] 所有架构/约束测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败

---

### Task 5: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7a, AC-7b, AC-8

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

> **性质说明：** 验收测试场景与 BDD 步骤已在 Task 0 定义并完成红阶段验证，本 Task 验证已完成的实现满足全部验收场景，不编写新的功能测试。

| 阶段 | 动作 |
|------|------|
| ✅ 验证 | 运行 Task 0 定义的 `tests/acceptance/test_acceptance_contractual_summary.feature` 全部场景，确认通过 |
| ✅ 验证 | 逐项核对 `src` 与 `tests/` 完成清单 |
| ✅ 验证 | 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验 |

- [ ] Subtask 5.1: 验证 `src` 完成清单（`SummaryGenerationPort` 已注册、Schema 已定义可导入、异常编码无碰撞、API 端点可访问）
- [ ] Subtask 5.2: 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单文件全部存在且可通过 pytest 发现
- [ ] Subtask 5.3: 运行 Task 0 定义的验收测试并确认全部通过
- [ ] Subtask 5.4: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`epics_v1.0.md`](../../planning-artifacts/epics_v1.0.md) Story 3.6 节定义，[`or.md` §5[1]`](../../planning-artifacts/or.md)

- **架构模式:** 六边形架构（Ports & Adapters）、契约化输出（Schema-driven generation）
- **设计约束:**
  - 领域层零外部依赖（仅 Python 标准库）
  - 依赖方向：domain ← application ← interfaces / infrastructure
  - 所有端口通过 `composition_root.py` 统一注册
  - Schema 定义在应用层（`src/application/`），允许使用 Pydantic
  - 端口契约定义在领域层（`src/domain/ports/`），仅使用 Protocol
  - 摘要生成使用 `LLMClientPort.structured_generate()`，不直接调用 LLM API
- **技术栈:** Python 3.11+、FastAPI 0.104+、Pydantic V2（Schema 验证）、LiteLLM（LLM 调用）、Qdrant 1.7+（摘要向量存储）、bge-m3（嵌入模型）

### 关键架构决策

**来源:** [`or.md` §5[1]`](../../planning-artifacts/or.md)、[`epics_v1.0.md`](../../planning-artifacts/epics_v1.0.md) Story 3.6

| 决策 | 方案 | 理由 |
|------|------|------|
| **Schema 定义位置** | 应用层（`src/application/services/summary_schemas.py`） | Schema 使用 Pydantic BaseModel，领域层不允许依赖 Pydantic |
| **端口类型** | 新增 `SummaryGenerationPort` Protocol | 遵循六边形架构，保持端口契约与实现分离 |
| **异常子域** | 新增 `summary` 子域（290-299） | 已有 BusinessException 子域均在 2XX 段，summary 异常继承 BusinessException 故编码落入 2XX 段，290-299 当前未占用 |
| **L1/L2 Collection 策略** | L1/L2 硬编码独立 collection 名（`cross_document_summaries`/`document_summaries`），与顶层 `collection` 参数解耦；`search_top_down` 与 `search_bottom_up` 同步填充 | 避免 L3/L4 检索语义冲突，L1/L2 搜索固定集合，不影响 L3/L4 的 `collection` 参数传递；`search_bottom_up` 包含相同骨架代码需同步修改 |
| **L1/L2 Dense 检索模式** | 复用 `_search_l3_direct`/`_search_l4_direct` 的 `self._dense_search.search()` 端到端模式 | 内部自动 `embed_query()` + `vector.search()`，禁止使用 `_search_top_down_l3_to_l4` 的私有属性访问模式 |
| **L1 实现策略** | 聚合 L2 摘要 → LLM 生成跨文档摘要 | 直接从 L2 摘要聚合，不重复从原始文档生成 |
| **L2 实现策略** | 检索结果 → LLM 生成文档摘要 → 向量化存储 | 复用 `LLMClientPort.structured_generate()`，与 `LayeredRetrievalService` 集成 |
| **摘要存储方式** | 独立 Qdrant collection（`document_summaries`、`cross_document_summaries`） | 与文档切片分离，避免 payload 冲突 |
| **Prompt 模板位置** | 独立模块 `summary_prompts.py` | 清晰分离 Prompt 与业务逻辑，方便迭代 |
| **LLM 调用方式** | 复用 `LLMClientPort.structured_generate()`（Story 3.2a） | 统一基础设施，获得熔断器和重试保护 |
| **API 端点设计** | `POST /api/v1/search/summary` | 与 `search/layered` 保持 RESTful 风格一致 |
| **视角数量** | MVP 三个视角（财务/市场/技术） | 覆盖核心分析场景，后续可扩展 |

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── exceptions/
│   │   ├── summary_exceptions.py              # [新增] 摘要异常类
│   │   └── _code_ranges.py                   # [修改] 新增 summary 子域
│   └── ports/
│       └── summary_generation.py             # [新增] SummaryGenerationPort Protocol
│
├── application/
│   └── services/
│       ├── summary_schemas.py                # [新增] 摘要 Pydantic Schema
│       ├── summary_prompts.py                # [新增] 摘要 Prompt 模板
│       └── summary_generation_service.py     # [新增] SummaryGenerationService
│
├── composition_root.py                       # [修改] 注册 summary_generation_service 端口
│
└── interfaces/
    └── api/
        ├── summary.py                        # [新增] 摘要 API 路由
        └── app.py                            # [修改] include_router

tests/
├── acceptance/
│   ├── test_acceptance_contractual_summary.feature # [新增] Gherkin 场景
│   └── test_acceptance_contractual_summary.py     # [新增] BDD 步骤实现
├── contracts/
│   ├── test_port_contract_summary_generation.py   # [新增] 端口契约测试
│   └── test_api_contract_summary.py               # [新增] API 契约测试
├── integration/
│   └── test_integration_contractual_summary.py    # [新增] 集成测试
└── unit/
    ├── domain/
    │   ├── exceptions/
    │   │   └── test_summary_exceptions.py        # [新增] 异常测试
    │   └── ports/
    │       └── test_summary_generation_port.py    # [新增] 端口测试
    ├── application/
    │   └── services/
    │       ├── test_summary_schemas.py            # [新增] Schema 测试
    │       ├── test_summary_prompts.py            # [新增] Prompt 测试
    │       └── test_summary_generation_service.py # [新增] 服务测试
    └── architecture/
        └── test_arch_summary_generation.py        # [新增] 架构验证

docs/
└── api/
    └── openapi.yaml                      # [修改] 新增 /api/v1/search/summary 端点
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 3.5 - 分层检索（L1-L4）](./3-5-layered-search-l1-l4.md)

**关键学习/Key Learnings:**
1. **Story 3.5 的 L1/L2 骨架标记**：LayeredRetrievalService 中 L1 和 L2 是骨架实现，明确标注 `# L2 文档摘要检索尚未实现，返回空列表`，本 Story 填充这些骨架
2. **端口注册模式**：`register_port()` 必须提供 `module` 参数（第 5 个必需参数），端口契约测试检查 `register_port` 调用的 `module` 参数
3. **异常子域注册流程**：新增子域需同时更新 `_code_ranges.py` 的 `CODE_RANGES`、`_CLASS_TO_SUBDOMAIN`、`__init__.py` 导出、`EXCEPTION_HTTP_MAP`
4. **分块级索引教训**：Story 3.5 需要重构索引流程为分块级粒度，本 Story 的摘要存储应避免同样问题——直接使用独立 collection
5. **BDD 测试异步模式**：BDD 步骤函数使用 `event_loop.run_until_complete()` 运行 async 代码，不要使用 `@pytest.mark.asyncio`

**应用到本故事/Applied to This Story:**
- [ ] 使用 Story 3.5 建立的 `LayeredRetrievalPort` 协议，通过 `search_top_down()` 获取 L3/L4 检索上下文
- [ ] 复用 `SummaryGenerationPort` 的端口注册模式，确保 `module` 参数完整
- [ ] 异常注册遵循 `_code_ranges.py` + `__init__.py` + `EXCEPTION_HTTP_MAP` 三步流程
- [ ] 摘要存储使用独立 Qdrant collection，避免与文档切片混用
- [ ] BDD 测试使用 `event_loop.run_until_complete()` 而非 `@pytest.mark.asyncio`

### 已有资产（可直接复用）

**端口层：**
- **LLMClientPort** — `src/domain/ports/llm_client.py`，`structured_generate(prompt, response_schema, config=None, system_prompt=None)` 方法已就绪
- `LayeredRetrievalPort` — `src/domain/ports/layered_retrieval.py`，`search_top_down()` 和 `search_bottom_up()` 方法已就绪
- `L3VectorPort` — `src/domain/ports/l3_vector.py`，`upsert_points()` 和 `search()` 方法已就绪
- `EmbeddingServicePort` — `src/domain/ports/embedding_service.py`，`embed_documents()` 方法已就绪

**服务层：**
- `LayeredRetrievalService` — `src/application/services/layered_retrieval_service.py`，L1/L2 为骨架
- `LitellmLLMClient` — `src/infrastructure/external_services/llm/litellm_llm_client.py`，`structured_generate()` 已实现

**异常层：**
- `LLMAPIError`（EXCEPTION_330）— LLM API 传输层错误
- `LLMResponseError`（EXCEPTION_331）— 响应格式错误
- `LLMConfigError`（EXCEPTION_332）— 配置错误
- LLM 子域（330-339）已占用 330/331/332，剩余 333-339 可用

**Qdrant 策略：**
- 摘要向量存储在独立 collection（`document_summaries`、`cross_document_summaries`），不与文档切片混用
- payload 中 `index_level` 字段标识层级（"L1"/"L2"），供 `LayeredRetrievalService` 过滤
- 点 ID 格式：`summary-{perspective}-{uuid4}`

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.2 |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-08-14 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Template** | `_bmad-output/implementation-artifacts/stories/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/3-5-layered-search-l1-l4.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] 前一个故事学习经验整合
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-6-contractual-summary-generation.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/ports/summary_generation.py` — SummaryGenerationPort Protocol
- `src/domain/exceptions/summary_exceptions.py` — 摘要异常
- `src/application/services/summary_schemas.py` — 摘要 Pydantic Schema
- `src/application/services/summary_prompts.py` — 摘要 Prompt 模板
- `src/application/services/summary_generation_service.py` — 摘要生成服务
- `src/interfaces/api/summary.py` — 摘要 API 路由
- `tests/unit/domain/ports/test_summary_generation_port.py` — 端口单元测试
- `tests/unit/domain/exceptions/test_summary_exceptions.py` — 异常单元测试
- `tests/unit/application/services/test_summary_schemas.py` — Schema 单元测试
- `tests/unit/application/services/test_summary_prompts.py` — Prompt 单元测试
- `tests/unit/application/services/test_summary_generation_service.py` — 服务单元测试
- `tests/unit/architecture/test_arch_summary_generation.py` — 架构验证测试
- `tests/integration/test_integration_contractual_summary.py` — 集成测试
- `tests/acceptance/test_acceptance_contractual_summary.feature` — Gherkin 场景
- `tests/acceptance/test_acceptance_contractual_summary.py` — BDD 步骤实现
- `tests/contracts/test_port_contract_summary_generation.py` — 端口契约测试
- `tests/contracts/test_api_contract_summary.py` — API 契约测试

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.6 |
| **Story Key** | 3-6-contractual-summary-generation |
| **File** | `_bmad-output/implementation-artifacts/stories/3-6-contractual-summary-generation.md` |
| **Status** | `backlog` → `ready-for-dev` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | P0 (MVP) |
| **覆盖 FR** | FR-SR-06 |
| **依赖 Story** | Story 3.5（分层检索 L1-L4） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-08-14
**最后更新/Last Updated:** 2026-08-14
**更新说明/Description:**
- v1.0.0: 创建故事文件
