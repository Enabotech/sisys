# Story 3.4: RRF 融合排序

**Status:** `done`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 搜索工程师,
**I want** 系统融合三路检索结果（Dense + Sparse + Graph/metadata signals），使用 RRF 融合排序并支持 ColBERT 重排序,
**So that** 综合多种检索信号提升相关性，Top-K 结果经精排后更精准。

### 业务价值

本 Story 是 Epic 3（智能检索与知识发现）关键路径的第四个故事（P0-4），也是 FR-SR-04（RRF 融合排序）的完整实现。

在 Story 3.1b 已交付两路（Dense + Sparse）RRF 融合的基础上，本 Story 引入**第三路 Graph 信号**（基于 Story 3.2b 的实体抽取结果和 L5GraphPort/GraphRetriever），实现**三路加权 RRF 融合**，并增加 **ColBERT 重排序**对 Top-K 候选进行精排。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **三路 RRF 融合** | 引入 Graph 信号，综合语义+关键词+图谱关系三重信号 | 三路加权融合结果正确，延迟 P95<50ms |
| **Graph 检索服务** | 将实体关系作为第三路检索信号，提升关联文档召回 | 输出与 SearchResult 格式兼容 |
| **ColBERT 重排序** | 对 Top-K 候选进行精排，提升头部结果精准度 | 重排序延迟 P95<200ms |
| **可配置权重** | 支持按业务场景调整 Dense/Sparse/Graph 权重 | 权重从外部传入，合并公式正确 |
| **异常体系** | 重排序专用异常，与项目异常体系集成 | 编码唯一性验证 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 3: 智能检索与知识发现，Story 3.4

**前置依赖:**
- Story 3.1b（BM25 稀疏检索 + RRF 融合 ✅ 已实现）— 提供两路 RRF 融合基础（`fuse()` 函数 + `HybridSearchService`）
- Story 3.2b（实体抽取 ✅ 已实现）— 提供实体抽取结果，作为 Graph 检索的实体数据源
- Story 1.8（Neo4j 图存储层 ✅ 已实现）— 提供 `L5GraphPort` 和 `GraphRetriever`
- Story 1.6（Qdrant 向量层 ✅ 已实现）— 提供 `L3VectorPort`

**后续依赖:** Story 3.5（分层检索）、Story 3.6（契约化摘要）、Story 3.7（检索相关性评估）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: Graph 检索服务（第三路信号）

**Given** 实体抽取结果已通过 Story 3.2b 写入 Neo4j（L5GraphPort）
**When** 用户输入查询文本执行 Graph 检索
**Then** 通过 `L5GraphPort.search_entities()` 解析查询文本中的实体，再经 `find_related()` 获取关联文档
**And** 输出与 `SearchResult` 格式兼容的结果列表（`id`/`score`/`payload`）
**And** Graph 检索延迟 P95 < 200ms（含 Neo4j 图遍历）

> **架构决策（对标六边形架构）：** GraphSearchService **仅注入 `L5GraphPort`**（领域端口），**不使用 `GraphRetriever`**。理由：
> 1. `GraphRetriever` 是基础设施具象类（直接依赖 `AsyncDriver`），非端口实现，注入它违反"应用层仅依赖领域端口"约束；
> 2. `L5GraphPort` 是 Story 1.8 已合入的领域端口，应用层经端口访问图存储，保持依赖方向一致。
> 因此需在 `L5GraphPort` 上**新增 `search_entities()` 方法**（见下方），补齐 `query_text → memory_id` 的解析桥梁。

**验证标准/Validation Criteria:**
- [ ] `GraphSearchService` 位于 `src/application/services/graph_search_service.py`
- [ ] 实现 `search(collection, query_text, limit, tenant_id, filter_payload)` 方法，签名与 Dense/Sparse 服务一致
- [ ] 注入 `L5GraphPort` 进行图遍历检索（**不使用 GraphRetriever**）
- [ ] 新增端口方法 `L5GraphPort.search_entities(query_text, limit=10) -> list[dict]`，按实体名模糊匹配返回候选实体（含 `memory_id`）
- [ ] 检索流程：`search_entities(query_text)` → 对候选实体逐个 `find_related(memory_id)` → 聚合并去重 → 转换为 `SearchResult`
- [ ] 输出结果转换为 `SearchResult` 格式（`id` 取实体 `memory_id`，`score` 取 `type_weight / (1 + hops)`，`payload` 含实体元数据）
- [ ] 无匹配实体时返回空列表
- [ ] `L5GraphPort` 异常时透明降级返回空列表（不抛出，由编排层处理）

### AC-2: 三路加权 RRF 融合

**Given** Dense、Sparse、Graph 三路检索结果均已获取
**When** 执行 RRF 融合排序
**Then** 使用 `fuse(dense, sparse, graph, weights=[w_dense, w_sparse, w_graph])` 三路加权融合
**And** 默认权重为 `[1.0, 1.0, 0.5]`（Graph 信号权重减半，因其召回量通常较小）
**And** 权重可通过 `HybridSearchService` 构造参数或 `search()` 方法参数配置
**And** RRF 融合延迟 P95 < 50ms（三路各 ≤ 50 结果）

**验证标准/Validation Criteria:**
- [ ] 复用 `src/domain/services/rrf_fusion.fuse()` 可变参数 `*result_lists` 支持三路
- [ ] `weights` 参数支持三路加权（默认 `[1.0, 1.0, 0.5]`）
- [ ] 跨通道去重：同文档 ID 在三路中出现时 RRF 分数叠加
- [ ] 降级策略：Graph 通道失败时降级为两路（Dense + Sparse）融合
- [ ] 单路空结果正常参与 RRF 融合（分数为 0）
- [ ] 性能测试：`time.perf_counter()` 采样 ≥ 100 次，P95 < 50ms

### AC-3: 升级后的混合检索编排服务

**Given** Dense、Sparse、Graph 三路检索服务均可用
**When** 调用升级后的 `HybridSearchService.search()`
**Then** 三路通过 `asyncio.gather` 并行执行
**And** 结果经三路加权 RRF 融合后返回
**And** 支持降级策略（Graph 通道失败→两路，Dense+Sparse 均失败→单路 Graph）
**And** 总检索延迟 P95 < 800ms（含嵌入生成 + Dense 检索 + Sparse 检索 + Graph 检索 + RRF 融合 + 可选重排序）
**And** 三路均失败时抛出 `HybridSearchError`（领域异常，非 `RuntimeError`）

> **异常合规说明：** 项目 Hard Constraints 禁止使用裸内置异常（`RuntimeError`）。三路均失败属于检索编排业务异常，定义 `HybridSearchError`（继承 `BusinessException`，编码 EXCEPTION_209）作为专用领域异常，由 `ExceptionHandlers` 自动映射为 HTTP 500。**同步修正现有 `hybrid_search_service.py` 中的 `RuntimeError` 历史违规。**
>
> **编码合规说明：** business 子域当前范围 `(201, 208)` 已全部占用，EXCEPTION_209 落在该范围外。实施时需将 `_code_ranges.py` 的 `CODE_RANGES` 中 business 范围扩展为 `(201, 209)`，并在 `_CLASS_TO_SUBDOMAIN` 中添加 `"HybridSearchError": "business"` 映射。CI 的 `test_code_ranges.py` 会校验子域范围，**必须同步更新** `allowed_child_parent_subdomains` 登记 `("hybrid_search", "business")` 或 `HybridSearchError` 归入 `reranker` 子域。

**验证标准/Validation Criteria:**
- [ ] `HybridSearchService` 升级为三路编排（新增 `graph_search` 注入）
- [ ] 构造函数签名：`__init__(self, dense_search, sparse_search, fuse, graph_search=None, weights=None, reranker=None)` — 新参数全部具名默认，保证向后兼容
- [ ] 使用 `asyncio.gather` 并行执行三路检索
- [ ] 降级策略完整：
  - 三路均成功 → 三路加权 RRF
  - Graph 失败 → 两路 RRF（Dense + Sparse），WARNING 日志
  - Dense + Sparse 均失败 → 单路 Graph 结果
  - 三路均失败 → `HybridSearchError("三路检索通道均失败")`
- [ ] 输入验证复用原有逻辑（空查询/空 Collection/无效 limit）

### AC-4: ColBERT 重排序端口与实现

**Given** RRF 融合后的 Top-K 候选结果
**When** 执行 ColBERT 重排序
**Then** 对 Top-K 候选（默认 K=20）进行精排
**And** 返回按重排序分数降序排列的结果列表（长度不超过 `top_k`）
**And** ColBERT 重排序延迟 P95 < 200ms（MVP 轻量级实现）

> **架构决策（对标业界最佳实践）：** 重排序是**独立的评分任务**，与文本生成本质不同。业界标准做法（如 Cohere Rerank、bge-reranker、Jina Reranker）均提供**专用重排序 API**（输入 query+documents，返回 score 数组），而非复用文本生成端点。因此：
> - **弃用** `LLMClientPort`（仅含 `generate()`/`structured_generate()`，无法返回数值分数）作为重排序后端；
> - 新建 **`RerankerPort` 的独立基础设施客户端**（`LiteLLMRerankerClient`），直接调用 `litellm.rerank()` 专用端点，注入 `RerankerConfig`（model/base_url/api_key/timeout）；
> - `RerankerPort` 作为领域端口，`LiteLLMRerankerClient` 作为其基础设施实现。

**验证标准/Validation Criteria:**
- [ ] `RerankerPort` Protocol 定义于 `src/domain/ports/reranker.py`
- [ ] 方法：`async rerank(query: str, results: list[SearchResult], top_k: int = 20) -> list[SearchResult]`
- [ ] **`top_k` 语义：截断参数** — 对全部输入结果重排序，仅返回分数最高的前 `top_k` 个；`top_k >= len(results)` 时返回全部（结果数量不变）
- [ ] **删除冗余的 `RerankResult` 值对象**（端口统一返回 `SearchResult`），`original_score` 存入 `payload["original_score"]`
- [ ] `LiteLLMRerankerClient` 实现位于 `src/infrastructure/external_services/reranker/litellm_reranker_client.py
- [ ] 使用**专用重排序 API**（如 `BAAI/bge-reranker-v2-m3` 的 `rerank` 端点），通过 `litellm.rerank()` 调用，**不经过 LLMClientPort**
- [ ] 注入 `RerankerConfig.from_env()`（model/base_url/api_key/timeout，非"可选"）
- [ ] 分数契约：`score = 归一化重排序分数`，`payload["original_score"] = 原 RRF 分数`，`payload["rerank_score"] = 重排序分数`
- [ ] 降级策略：重排序失败时返回原始 RRF 融合结果（不阻断主流程）
- [ ] 领域层零外部依赖（`RerankerPort` 仅使用 Python 标准库）

### AC-5: 重排序异常体系

**Given** 重排序过程中可能发生多种错误
**When** 定义重排序异常类
**Then** 继承项目统一异常层次结构
**And** 分配唯一异常编码

**HTTP 映射机制说明（关键）：** 项目 `EXCEPTION_HTTP_MAP` 按**具体异常类**精确注册，`_get_http_status` 先 `type(exc) is exc_type` 精确匹配、再 `isinstance` 回退。因此 `RerankError` 继承 `ExternalException`（基类映射 502）但显式注册为 500 是**合法的**——只要在 map 中注册 `RerankError: 500`，精确命中即返回 500。先例：`EntityExtractionError`（继承 ExternalException，映射 500）。**测试必须断言精确类型 `type(exc) is RerankError`，而非 `isinstance`**，否则会命中基类 502。选择 500 而非 502 的理由：重排序失败是服务端内部处理失败，非上游服务问题。

**验证标准/Validation Criteria:**
- [ ] `RerankError`（EXCEPTION_350）— 继承 `ExternalException`，在 `EXCEPTION_HTTP_MAP` **精确注册为 500**
- [ ] 异常编码在 `_code_ranges.py` 注册，无碰撞（新增 `reranker` 子域 350-359）
- [ ] 异常在 `__init__.py` 导出，在 `EXCEPTION_HTTP_MAP` 注册
- [ ] 测试断言精确类型 `type(exc) is RerankError`（HTTP 500），避免 `isinstance` 回退到基类 502

### AC-6: 端口注册与 DI 集成

**Given** 所有组件实现完成
**When** 在 `composition_root.py` 注册
**Then** `graph_search_service`、`reranker`、升级后的 `hybrid_search_service` 端口注册为 SCOPED
**And** 通过 `Resolver` 可正确解析
**And** 端口契约测试通过

> **端口升级机制说明（关键）：** `PortRegistry.register()` 对同名端口比较整个 `PortSpec`，版本/impl 不同则抛 `ConflictError`。`hybrid_search_service` 从 v1.0.0 升级到 v1.1.0 时，**必须显式处理版本迁移**：注册 v1.1.0 时设置 `compatibility=("v1.0.0",)`，并在 bootstrap 中先 `unregister("hybrid_search_service")` 旧端口再注册新端口（或使用 registry 既定的升级流程）。AC-6 契约测试需覆盖此升级路径。

**验证标准/Validation Criteria:**
- [ ] `composition_root.py` 注册 `graph_search_service` 端口（GraphSearchService，SCOPED）
- [ ] `composition_root.py` 注册 `reranker` 端口（`LiteLLMRerankerClient` 实现 RerankerPort，注入 `RerankerConfig`，非 LLMClientPort）
- [ ] `composition_root.py` 升级 `hybrid_search_service` 端口注册（三路注入 + 版本升级处理 compatibility）
- [ ] 端口契约测试 `tests/contracts/test_port_contract_search_services.py` 更新通过
- [ ] `src/domain/ports/__init__.py` 导出 `RerankerPort`

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

本 Story **不新增**领域事件。Graph 检索和重排序是检索流程中的技术环节，不产生领域事件。
- （跳过）事件定义位于 `src/domain/events/`

#### 数据模型 (Data Models)

**不新建独立值对象（架构决策）：**
- 端口统一返回 `SearchResult`（`src/domain/ports/l3_vector.py` 的 TypedDict `{id, score, payload}`），**删除冗余的 `RerankResult` dataclass**。理由：`rerank()` 返回类型为 `list[SearchResult]`，`RerankResult` 无任何消费方（死代码）；`original_score` 作为附加字段存入 `payload["original_score"]`，不引入独立值对象。
- 重排序分数契约：`score` = 归一化重排序分数（降序排序依据），`payload["original_score"]` = 原 RRF 分数（对比分析），`payload["rerank_score"]` = 重排序分数。

**新建应用层值对象（`src/application/services/graph_search_service.py`）：**
- [ ] `GraphSearchResult` TypedDict（可复用 `SearchResult`，无需额外定义）
- 本 Story 不新增实体，Graph 检索输出兼容 `SearchResult`

#### 统一端口定义注册与管理 (Port Contract)

**新建端口：**
- [ ] `RerankerPort`（`src/domain/ports/reranker.py`）
  - 方法: `async rerank(query: str, results: list[SearchResult], top_k: int = 20) -> list[SearchResult]`
  - 版本: v1.0.0, owner: search-team
  - 端口契约测试: `tests/contracts/test_port_contract_reranker.py`

**端口契约清单（强制）：**

| 端口名称 | 版本 | Owner | 注册 | 解析 | 契约测试 | 状态 |
|---------|------|-------|------|------|---------|------|
| RerankerPort | v1.0.0 | search-team | 新建（reranker） | 新建 | 新建 | **新建** |
| GraphSearchService | v1.0.0 | search-team | 新建（graph_search_service） | 新建 | 已有（更新） | **新建** |
| HybridSearchService | v1.1.0 | search-team | 升级（hybrid_search_service） | 升级 | 已有（更新） | **升级** |

#### 领域异常契约 (Domain Exception Contract)

**新建异常类（`src/domain/exceptions/reranker_exceptions.py` + `src/domain/exceptions/hybrid_search_exceptions.py`）：**

| 异常类 | 编码 | 继承 | HTTP 映射 | 说明 |
|--------|------|------|-----------|------|
| `RerankError` | EXCEPTION_350 | `ExternalException` | 500 | 重排序失败（模型加载失败/调用超时/结果异常）。继承 `ExternalException` 理由：重排序是外部模型服务，属于外部异常范畴。HTTP 500 理由：服务端处理失败 |
| `HybridSearchError` | EXCEPTION_209 | `BusinessException` | 500 | 三路检索通道均失败（替换 RuntimeError 历史违规）。继承 `BusinessException` 理由：检索编排属于业务子域，非外部服务错误。HTTP 500 理由：服务端处理失败 |

**编码分配验证：**
- `external` 子域范围：301-399 ✅
- `business` 子域范围：201-208（**需扩展为 201-209** 以容纳 HybridSearchError EXCEPTION_209）
- `embedding` 306-308, `sandbox` 309-319, `ocr` 320-329, `llm` 330-339, `entity_extraction` 340-349
- **重排序分配 350** — 紧接实体抽取之后，预留 350-359 范围
- 运行 `grep -r "EXCEPTION_35[0-9]" src/domain/exceptions/` 确认无碰撞

### HybridSearchError 编码注册（EXCEPTION_209）

- [ ] **business 子域范围扩展** — 将 `_code_ranges.py` 的 `CODE_RANGES["business"]` 从 `(201, 208)` 扩展为 `(201, 209)`，容纳 EXCEPTION_209
- [ ] **`_CLASS_TO_SUBDOMAIN` 注册** — 添加 `"HybridSearchError": "business"` 映射
- [ ] **CI 子域登记同步** — 更新 `tests/unit/domain/exceptions/test_code_ranges.py` 的 `allowed_child_parent_subdomains`，登记 `("hybrid_search", "business")` 或 `("reranker", "business")`（取决于子域命名），否则 `test_subclass_code_in_same_subdomain_as_parent` 会因"非法跨子域继承"失败
- [ ] 归属模块与基类 — 检索编排属于业务子域，继承 `BusinessException`（非 `ExternalException`）
- [ ] 导出完整性 — `__init__.py` + `EXCEPTION_HTTP_MAP`（500）
- [ ] 测试覆盖 — 构造/`to_dict()`/HTTP 映射/编码唯一性/子域范围

### RerankError 编码注册（EXCEPTION_350）

- [ ] 归属模块与基类 — 重排序属于外部模型服务，继承 `ExternalException`
- [ ] 唯一编码分配 — 350，确认无碰撞
- [ ] 构造器参数设计 — 携带 `model_name`、`top_k`、`result_count` 等上下文
  - `model_name: str` — 重排序模型名称
  - `top_k: int` — 重排序的 Top-K 数量
  - `result_count: int` — 输入结果数量
- [ ] 编码注册 — 在 `_code_ranges.py` 的 `CODE_RANGES` 新增 `"reranker": (350, 359)` + `_CLASS_TO_SUBDOMAIN` 注册 `RerankError`
- [ ] CI 子域登记同步 — 更新 `tests/unit/domain/exceptions/test_code_ranges.py` 的 `allowed_child_parent_subdomains` 登记 `("reranker", "external")` + `nested_subdomains` 登记 `"reranker": "external"`
- [ ] 导出完整性 — `__init__.py` + `EXCEPTION_HTTP_MAP`
- [ ] 测试覆盖 — 构造/`to_dict()`/HTTP 映射/编码唯一性

#### 六边形架构约束（必须遵守）

> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 本 Story 职责 |
|------|------|-------------|
| domain | `src/domain/` | RerankerPort 端口 + 重排序异常 |
| application | `src/application/` | GraphSearchService（第三路） + HybridSearchService 升级（三路+重排序编排） |
| infrastructure | `src/infrastructure/` | LiteLLMRerankerClient 实现（重排序 API 客户端，不经过 LLMClientPort） |
| interfaces | `src/interfaces/` | 无新增 |

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | infrastructure |
|------------|--------|-------------|----------------|
| **domain (RerankerPort)** | — | ✗ 禁止 | ✗ 禁止 |
| **application (GraphSearchService/HybridSearchService)** | ✓ 允许 | — | ✗ 禁止 |
| **infrastructure (LiteLLMRerankerClient)** | ✓ 允许 | ✗ 禁止 | — |

> **严格六边形架构：** infrastructure → application 为 **✗ 禁止**。基础设施层直接实现领域端口，不依赖应用层编排逻辑。所有跨层依赖通过领域层端口（Protocol）进行。

**领域层零依赖原则** — `src/domain/ports/reranker.py` 仅依赖：
- Python 标准库（`dataclasses`, `typing`）
- `typing.Protocol` / `@runtime_checkable`
- `SearchResult`（来自 `src/domain/ports/l3_vector.py`，纯 TypedDict，仅标准库）
- 不依赖：`pydantic`, `litellm`, `torch`, `sentence_transformers`, `transformers`

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_hybrid_search.feature`（更新）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_hybrid_search.py`（更新）
- [ ] 业务方评审通过
- [ ] 覆盖场景:
  - Happy Path: 三路（Dense+Sparse+Graph）混合检索成功
  - Happy Path: 三路加权 RRF 融合结果正确
  - Happy Path: ColBERT 重排序成功返回精排结果
  - Edge Case: Graph 通道失败降级为两路融合
  - Edge Case: 空内容输入返回空结果
  - Edge Case: 重排序失败降级为 RRF 结果
  - Edge Case: 自定义权重配置

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
| **TDD 单元测试** | RerankerPort | 端口契约、方法签名 | `test_reranker_port.py` | Task 1 |
| **TDD 单元测试** | 重排序异常 | 构造/属性/to_dict()/HTTP 映射 | `test_reranker_exceptions.py` | Task 1 |
| **TDD 单元测试** | GraphSearchService | L5GraphPort 注入、SearchResult 转换 | `test_graph_search_service.py` | Task 2 |
| **TDD 单元测试** | LiteLLMRerankerClient | 重排序逻辑、降级策略 | `test_litellm_reranker_client.py` | Task 2 |
| **TDD 单元测试** | 升级 HybridSearchService | 三路编排、加权融合、降级 | `test_hybrid_search_service.py`（更新） | Task 3 |
| **TDD 回归验证** | 三路 RRF 融合 | 补充三路加权融合缺失用例 | `test_rrf_fusion.py`（更新，不新建文件） | Task 1 |
| **TDD 验收测试** | Gherkin 场景（更新） | 业务价值验收 | `test_acceptance_hybrid_search.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现（更新） | 步骤函数实现 | `test_acceptance_hybrid_search.py` | Task 0 |
| **TDD 契约测试** | RerankerPort | 端口注册/解析/契约门禁 | `test_port_contract_reranker.py` | Task 4 |
| **TDD 契约测试** | GraphSearchService | 端口注册/解析/契约门禁 | `test_port_contract_search_services.py`（更新） | Task 4 |
| **TDD 契约测试** | HybridSearchService（升级） | 端口注册/解析/版本升级 | `test_port_contract_search_services.py`（更新） | Task 4 |
| **TDD 领域异常测试** | 重排序异常 | 编码唯一性/子域范围 | `test_error_code_uniqueness.py` + `test_code_ranges.py` | Task 1 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖 | `test_arch_hybrid_search.py`（更新） | Task 4 |
| **集成测试** | 混合检索管线 | 端到端检索流程 | `test_integration_hybrid_search.py`（更新） | Task 4 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain/`）
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application/services/`）
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure/external_services/reranker/`）
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration/`）

> ⚠️ 本 Story 为非骨架 Story，需达到标准覆盖率要求。

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **外部服务隔离（单元测试）** | 单元测试用 AsyncMock(spec=L5GraphPort) 隔离 Neo4j，重排序用 Mock 隔离 API | 真实调用导致失败 |
| **外部服务隔离（集成/验收测试）** | 集成/验收测试**真实服务优先**（与项目规范一致）：Neo4j/重排序 API 不可用时用 `pytest.skip()` 动态跳过，**禁止全局 Mock**；仅 Graph 服务无法在 CI 环境运行时才以 Mock 作为例外 | 违反项目"真实服务优先"约束 |
| **配置隔离** | 每个测试使用独立的权重配置实例 | 配置污染 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突 |
| **BDD async 配合** | BDD 步骤函数用 event_loop.run_until_complete() | context 数据丢失 |

> **Mock 与 P95 性能口径区分：** 单元测试用 Mock 验证功能正确性；**P95 性能验收（如重排序 <200ms）需在真实/本地模型上断言**，不在 Mock 上测延迟（Mock 不反映真实 API 延迟）。

**验证要求：**
- [ ] 并行测试 `poetry run pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | Graph 检索服务（第三路信号） | Task 2 | Subtask 2.1-2.3 | `test_graph_search_service.py` |
| AC-2 | 三路加权 RRF 融合 | Task 1 | Subtask 1.1-1.3 | `test_rrf_fusion.py`（更新，补充三路用例） |
| AC-3 | 升级后的混合检索编排服务 | Task 3 | Subtask 3.1-3.3 | `test_hybrid_search_service.py`（更新） |
| AC-4 | ColBERT 重排序端口与实现 | Task 2 | Subtask 2.4-2.6 | `test_reranker_port.py` + `test_litellm_reranker_client.py` |
| AC-5 | 重排序异常体系 | Task 1 | Subtask 1.7-1.9 | `test_reranker_exceptions.py` |
| AC-6 | 端口注册与 DI 集成 | Task 4 | Subtask 4.1-4.3 | `test_port_contract_reranker.py` + `test_port_contract_search_services.py` |
| AC-6 | 架构约束验证 + 集成测试 | Task 4 | Subtask 4.4-4.6 | `test_arch_hybrid_search.py` + `test_integration_hybrid_search.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 定义 RerankerPort 端口契约（`rerank` 方法签名 + `top_k` 截断语义）设计
- [ ] Subtask 0.2: 定义 GraphSearchService 接口设计（与 Dense/Sparse 服务签名对齐）
- [ ] Subtask 0.3: 定义 HybridSearchService 升级设计（三路注入 + 可配置权重 + 重排序集成）
- [ ] Subtask 0.4: 定义重排序异常体系设计（RerankError EXCEPTION_350）
- [ ] Subtask 0.5: 定义 `_code_ranges.py` 新增 `reranker` 子域（350-359）
- [ ] Subtask 0.6: 更新 Gherkin 验收测试 `tests/acceptance/test_acceptance_hybrid_search.feature`
- [ ] Subtask 0.7: 更新 BDD 步骤实现 `tests/acceptance/test_acceptance_hybrid_search.py`
- [ ] Subtask 0.8: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 领域层 — 三路 RRF 融合测试 + RerankerPort + 异常体系

**关联 AC:** AC-2, AC-4, AC-5

> **领域层零外部依赖：** 本 Task 所有代码位于 `src/domain/`，仅使用 Python 标准库。
> 禁止导入：pydantic, torch, sentence_transformers 等任何第三方库。

#### 回归验证 [A]：三路加权 RRF 融合测试（补充现有测试）

> **非 TDD 循环说明：** `fuse()` 的 `*result_lists` 可变参数和 `weights` 参数已天然支持三路加权融合。现有 `test_rrf_fusion.py` 已包含三路加权、参数校验、性能测试等覆盖。本阶段为**回归验证 + 补充缺失用例**，不适用 TDD 红→绿循环（功能已存在，测试不会在红阶段失败）。

| 阶段 | 动作 |
|------|------|
| 🔍 回归 | 验证现有 `test_rrf_fusion.py` 中三路融合测试已通过（`test_weighted_fusion_three_lists`、`test_weighted_fusion_different_weights` 等） |
| ➕ 补充 | 在现有 `test_rrf_fusion.py` 中补充缺失的三路用例 |
| 🔄 重构 | 运行 `ruff check` + `mypy` + `pytest tests/unit/domain/services/ -v` |

- [ ] Subtask 1.1: 🔍 回归验证 — 确认现有 `test_rrf_fusion.py` 已覆盖以下用例（无需新建文件）：
  - ✅ 三路对称融合（`fuse(dense, sparse, graph)`）
  - ✅ 三路加权融合（`fuse(dense, sparse, graph, weights=[0.4, 0.4, 0.2])`）
  - ✅ 不同权重组合（`weights=[0.5, 0.3, 0.2]`）
  - ✅ weights 长度不匹配 → ValidationError
  - ✅ weights 含负值 → ValidationError
  - ✅ 单路直通 / 空输入
  - ✅ 跨通道去重（payload 保留首次出现）
  - ✅ 分数验证（`math.isclose`）
  - ✅ 性能测试（P95 < 50ms）
- [ ] Subtask 1.2: ➕ 补充 — 在现有 `test_rrf_fusion.py` 中补充缺失用例：
  - **默认权重三路测试**：`fuse(dense, sparse, graph, weights=None)` 或默认 `[1.0, 1.0, 0.5]` 显式传参
  - **三路对称无权重测试**：`fuse(dense, sparse, graph)` 验证对称融合行为
  - **三路性能测试**：三路各 50 结果，P95 < 50ms
- [ ] Subtask 1.3: 🔄 重构 — 运行 `ruff check` + `mypy` + `pytest tests/unit/domain/services/ -v`

#### TDD 循环 [B]：RerankerPort（端口契约）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_reranker_port.py`（端口契约验证） |
| 🟢 绿 | 实现 `src/domain/ports/reranker.py`（RerankerPort Protocol） |
| 🔄 重构 | 优化类型注解，运行 `ruff` + `mypy` |

- [ ] Subtask 1.4: 🔴 红 — 编写 RerankerPort 失败测试
  - `RerankerPort` Protocol 结构验证（`rerank()` 方法签名）
  - `@runtime_checkable` 可用
  - 方法签名：`async rerank(query: str, results: list[SearchResult], top_k: int = 20) -> list[SearchResult]`
  - **不定义 `RerankResult` 值对象**（端口统一返回 `SearchResult`，`original_score` 存入 `payload["original_score"]`）
- [ ] Subtask 1.5: 🟢 绿 — 实现 RerankerPort（仅 Protocol，不含值对象）
- [ ] Subtask 1.6: 🔄 重构 — 优化代码，运行 `ruff` + `mypy`

#### TDD 循环 [C]：重排序异常体系

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_reranker_exceptions.py`（异常构造 + to_dict + HTTP 映射） |
| 🟢 绿 | 实现 `src/domain/exceptions/reranker_exceptions.py`（RerankError） |
| 🔄 重构 | 更新 `__init__.py` + `_code_ranges.py` + `EXCEPTION_HTTP_MAP`，运行 `ruff` + `mypy` |

- [ ] Subtask 1.7: 🔴 红 — 编写重排序异常失败测试
  - `RerankError` 构造（含 model_name, top_k, result_count 上下文）
  - `to_dict()` 序列化正确（含 cause 链）
  - HTTP 映射正确（350→500）
  - 编码唯一性（`test_error_code_uniqueness.py` 中确认无碰撞）
  - 子域范围（`test_code_ranges.py` 中新增 reranker 子域）
- [ ] Subtask 1.8: 🟢 绿 — 实现重排序异常类
  - 创建 `src/domain/exceptions/reranker_exceptions.py`
  - 更新 `src/domain/exceptions/__init__.py` 导出
  - 更新 `src/domain/exceptions/_code_ranges.py` 新增 `reranker` 子域 (350, 359)
  - 更新 `src/interfaces/api/exception_handlers.py` 的 `EXCEPTION_HTTP_MAP`
- [ ] Subtask 1.9: 🔄 重构 — 运行 `ruff check` + `mypy` + `pytest tests/unit/domain/exceptions/ -v`

**完成标准/Definition of Done:**
- [ ] 三路加权 RRF 融合回归验证通过（补充缺失用例到现有 `test_rrf_fusion.py`）
- [ ] RerankerPort Protocol 实现完成（无 RerankResult 值对象）
- [ ] RerankError 异常实现完成（HTTP 500，精确映射）
- [ ] TDD 循环全部通过
- [ ] 编码无碰撞验证通过
- [ ] 领域层覆盖率≥90%

---

### Task 2: 应用层 + 基础设施层 — GraphSearchService + 重排序客户端

**关联 AC:** AC-1, AC-4

> **GraphSearchService** 在应用层，**仅注入 `L5GraphPort`**（领域端口），不使用 `GraphRetriever`（基础设施具象类，违反六边形架构）。
> **重排序客户端** 在基础设施层，使用 `litellm.rerank()` 专用 API，**不经过 LLMClientPort**。

#### TDD 循环 [A]：GraphSearchService（应用层，第三路检索）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_graph_search_service.py` |
| 🟢 绿 | 实现 `src/application/services/graph_search_service.py` |
| 🔄 重构 | 优化图遍历逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 2.1: 🔴 红 — 编写 GraphSearchService 失败测试
  - **Happy Path:** 通过 `L5GraphPort.search_entities()` 解析查询文本 → 获取候选实体 → `find_related()` 获取关联文档 → 转换为 `SearchResult`
  - **Happy Path:** 返回结果包含正确的 `id`/`score`/`payload` 字段
  - **Edge Case:** 无匹配实体返回空列表
  - **Edge Case:** 空查询文本返回空列表（与 Dense/Sparse 行为一致）
  - **Edge Case:** `L5GraphPort` 抛出异常时透明降级返回空列表
  - **签名对齐:** 验证 `search(collection, query_text, limit, tenant_id, filter_payload)` 签名与 Dense/Sparse 一致
  - **性能:** Graph 检索延迟 P95 < 200ms（通过 AsyncMock 模拟）
- [ ] Subtask 2.2: 🟢 绿 — 实现 GraphSearchService
  - 构造函数注入 `L5GraphPort`（**仅 L5GraphPort，不使用 GraphRetriever**）
  - 实现 `search()` 方法，签名严格对齐 `DenseSemanticSearchService`
  - 检索流程：
    1. `L5GraphPort.search_entities(query_text, limit=limit)` → 候选实体列表（按实体名模糊匹配）
    2. 对每个候选实体调用 `L5GraphPort.find_related(memory_id, max_depth=2)` → 关联实体列表
    3. 聚合所有关联实体，按 `memory_id` 去重
  - 分数映射：`score = type_weight * connection_count / (1 + hops)`
    - `type_weight`：concept=0.8, person=0.6, organization=0.7, default=0.5
    - `hops`：取自 `find_related()` 返回的 `path` 长度（`hops = len(path)`）
    - `connection_count`：取自 retriever 返回（无 connection_count 时默认为 1）
  - 输出格式转换为 `SearchResult`（`id` 使用 `memory_id`，`score` 使用上述公式，`payload` 包含实体元数据）
  - 异常处理：`L5GraphPort` 失败时返回空列表（不抛出异常，由编排层处理）
- [ ] Subtask 2.3: 🔄 重构 — 运行 `ruff` + `mypy`

#### TDD 循环 [B]：LiteLLMRerankerClient（基础设施层，重排序 API 客户端）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/reranker/test_litellm_reranker_client.py` |
| 🟢 绿 | 实现 `src/infrastructure/external_services/reranker/litellm_reranker_client.py` |
| 🔄 重构 | 优化重排序逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 2.4: 🔴 红 — 编写 LiteLLMRerankerClient 失败测试
  - **Happy Path:** 对 Top-K 结果进行重排序，返回按新分数降序排列的结果
  - **Happy Path:** 重排序后分数分布在 [0, 1] 范围内
  - **Happy Path:** `top_k` 截断语义正确（输入 > top_k 时仅返回前 top_k 个）
  - **Edge Case:** 输入空列表返回空列表
  - **Edge Case:** 重排序 API 调用失败（`RerankError`）→ 返回原始结果（透明降级），`payload["original_score"]` 保留
  - **Edge Case:** 输入结果数量 < top_k 时全部重排序并返回
  - **Edge Case:** 重排序分数映射到 `SearchResult.score`，`payload["original_score"]` 保留原 RRF 分数
  - **性能:** 重排序延迟 P95 < 200ms（MVP 轻量级实现，通过真实/本地模型断言）
- [ ] Subtask 2.5: 🟢 绿 — 实现 LiteLLMRerankerClient
  - 实现 `RerankerPort` 接口（`rerank(query, results, top_k=20)`）
  - **API 方案：** 使用 `litellm.rerank()` 专用端点（如 `BAAI/bge-reranker-v2-m3`），**不经过 LLMClientPort**
  - **注入 `RerankerConfig`**（model/base_url/api_key/timeout，来自 `from_env()`），**非"可选"**（见端口注册）
  - 降级策略：调用失败时返回原始 `results`（不阻断主流程），WARNING 日志
  - 分数契约：`score = 归一化重排序分数`，`payload["original_score"] = 原 RRF 分数`，`payload["rerank_score"] = 重排序分数`
  - `top_k` 语义：截断参数——对全部输入重排序，仅返回前 `top_k` 个；`top_k >= len(results)` 时返回全部
- [ ] Subtask 2.6: 🔄 重构 — 运行 `ruff` + `mypy`

**完成标准/Definition of Done:**
- [ ] GraphSearchService 实现完成（L5GraphPort 仅端口注入 + search_entities→find_related 检索流程）
- [ ] LiteLLMRerankerClient 实现完成（RerankerPort 接口 + litellm.rerank() 专用 API + 降级策略）
- [ ] TDD 循环全部通过
- [ ] 应用层覆盖率≥85%
- [ ] 基础设施层覆盖率≥75%

---

### Task 3: 应用层 — HybridSearchService 三路升级

**关联 AC:** AC-3

> **应用层编排：** 本 Task 升级 `HybridSearchService`，从两路（Dense+Sparse）扩展到三路（Dense+Sparse+Graph），并集成重排序。

#### TDD 循环 [A]：HybridSearchService 三路升级

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_hybrid_search_service.py`（更新，新增三路测试） |
| 🟢 绿 | 升级 `src/application/services/hybrid_search_service.py`（三路注入 + 可配置权重 + 重排序集成） |
| 🔄 重构 | 优化编排逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 3.1: 🔴 红 — 编写三路混合检索升级失败测试
  - **Happy Path:** 三路（Dense + Sparse + Graph）并行检索，RRF 加权融合
  - **Happy Path:** 三路均成功，默认权重 `[1.0, 1.0, 0.5]` 融合正确
  - **Happy Path:** 自定义权重（如 `[0.5, 0.3, 0.2]`）通过 `search()` 参数传入
  - **Happy Path:** 三路融合后结果按 RRF 分数降序排列
  - **降级: Graph 失败** → 两路（Dense + Sparse）RRF 融合，日志 WARNING
  - **降级: Dense + Sparse 均失败** → 单路 Graph 结果返回
  - **降级: 三路均失败** → `HybridSearchError`（领域异常，非 RuntimeError）
  - **降级: Graph 空结果** → 正常参与 RRF 融合（空列表，分数为 0）
  - **重排序集成:** 三路融合后，对结果调用 `RerankerPort.rerank()` 重排序
  - **重排序降级:** 重排序失败时返回原始 RRF 融合结果
  - **输入验证:** 空查询/空 Collection/无效 limit 抛出 `ValidationError`
  - **向后兼容:** 原有两路（Dense + Sparse）调用方式仍正常工作
  - **权重覆盖优先级:** `search()` 方法参数权重覆盖构造参数权重
- [ ] Subtask 3.2: 🟢 绿 — 升级 HybridSearchService
  - 构造函数签名：`__init__(self, dense_search, sparse_search, fuse, graph_search=None, weights=None, reranker=None)` — 新参数全部具名默认，保证向后兼容
  - `search()` 方法 `asyncio.gather` 从两路升级为三路并行
  - 降级策略实现（见测试用例）
  - 重排序集成：三路融合后，若 `reranker` 注入则调用 `rerank()` 精排
  - 向后兼容：两路注入时保持原有行为
- [ ] Subtask 3.3: 🔄 重构 — 运行 `ruff` + `mypy`

**完成标准/Definition of Done:**
- [ ] HybridSearchService 三路升级完成
- [ ] 可配置权重支持完成
- [ ] 重排序集成完成（含降级）
- [ ] TDD 循环全部通过
- [ ] 向后兼容验证通过
- [ ] 应用层覆盖率≥85%

---

### Task 4: 端口注册 + 架构验证 + 集成测试

**关联 AC:** AC-6

> **性质说明：** 本 Task 包含 DI 注册、端口契约测试、架构约束验证和集成测试。

#### 端口注册与 DI 集成

- [ ] Subtask 4.1: 更新 `src/domain/ports/__init__.py` 导出 `RerankerPort`（**不导出 RerankResult**，已删除）
- [ ] Subtask 4.2: 更新 `src/composition_root.py` 注册相关端口
  ```python
  # 注册 GraphSearchService（第三路检索，仅注入 L5GraphPort）
  # ⚠️ 注意：l5_graph 端口当前注册为字符串路径（Neo4jAdapter），
  #   其构造参数 `storage: Any` 无法通过 Resolver._auto_inject 自动解析。
  #   实施时需先将 l5_graph 注册改为 lambda 工厂函数：
  #   register_port(name="l5_graph", ..., impl=lambda r: Neo4jAdapter(storage=r.resolve("neo4j_graph_storage")))
  register_port(
      name="graph_search_service",
      version="v1.0.0",
      interface=GraphSearchService,
      impl=lambda resolver: GraphSearchService(
          l5_graph=resolver.resolve("l5_graph"),
      ),
      module="src.application.services.graph_search_service",
      lifetime=Lifetime.SCOPED,
      owner="search-team",
      tags=("search", "graph", "neo4j"),
  )

  # 注册重排序器（LiteLLMRerankerClient 实现 RerankerPort，注入 RerankerConfig）
  register_port(
      name="reranker",
      version="v1.0.0",
      interface=RerankerPort,
      impl=lambda resolver: LiteLLMRerankerClient(
          config=RerankerConfig.from_env(),
      ),
      module="src.infrastructure.external_services.reranker.litellm_reranker_client",
      lifetime=Lifetime.SCOPED,
      owner="search-team",
      tags=("reranker", "colbert", "search"),
  )

  # 升级 HybridSearchService 注册（三路注入 + 可配置权重 + 重排序）
  # 注意：v1.0.0 → v1.1.0 必须先 unregister 旧端口再 register，否则 PortRegistry
  #       对同名不同 spec 抛 ConflictError。compatibility 为可选元数据标记。
  # 正确升级流程：
  #   _global_registry.unregister("hybrid_search_service")
  #   然后 register_port(...) 注册 v1.1.0
  register_port(
      name="hybrid_search_service",
      version="v1.1.0",
      interface=HybridSearchService,
      impl=lambda resolver: HybridSearchService(
          dense_search=resolver.resolve("dense_search_service"),
          sparse_search=resolver.resolve("sparse_search_service"),
          fuse=fuse,
          graph_search=resolver.resolve("graph_search_service"),
          weights=[1.0, 1.0, 0.5],
          reranker=resolver.resolve("reranker"),
      ),
      module="src.application.services.hybrid_search_service",
      lifetime=Lifetime.SCOPED,
      owner="search-team",
      tags=("search", "hybrid", "rrf", "three-way"),
      compatibility=("v1.0.0",),  # 可选元数据，仅用于追溯/契约测试
  )
  ```
  - 生命周期: SCOPED
  - Owner: search-team
  - **版本升级前置条件：** `hybrid_search_service` 从 `v1.0.0` 升级到 `v1.1.0`，因 `PortRegistry.register()` 对同名不同 spec 抛 `ConflictError`，**必须在 bootstrap 中先 `_global_registry.unregister("hybrid_search_service")` 旧端口，再注册新端口**。`compatibility=("v1.0.0",)` 为**可选元数据标记**（供契约测试/追溯用），非注册必需步骤
  - **RERANKER_ENABLED=false 时：** composition_root 不注册 `reranker` 端口（或注册为返回 None 的占位），`hybrid_search_service` 注入 `reranker=None` 跳过精排（其逻辑已支持可选）

#### 端口契约测试

- [ ] Subtask 4.3: 创建 `tests/contracts/test_port_contract_reranker.py`
  - 验证 `reranker` 端口已注册到 Registry
  - 验证 `Resolver` 可解析 `reranker`
  - 验证 `RerankerPort` 方法签名正确
- [ ] Subtask 4.4: 更新 `tests/contracts/test_port_contract_search_services.py`
  - 新增 `TestGraphSearchServicePortContract` 测试类（参考现有 `TestSparseSearchServicePortContract` 模式）
  - 验证 `graph_search_service` 端口已注册
  - 验证 `hybrid_search_service` 端口已注册且版本为 v1.1.0（含 compatibility）
  - 验证 `Resolver` 可解析各端口

#### 架构验证测试

- [ ] Subtask 4.5: 更新 `tests/unit/architecture/test_arch_hybrid_search.py`
  - 验证 `src/domain/ports/reranker.py` 零外部依赖（仅标准库）
  - 验证 `RerankerPort` 位于领域层
  - 验证 `LiteLLMRerankerClient` 位于基础设施层
  - 验证 `GraphSearchService` 位于应用层
  - 验证依赖方向正确（infrastructure → domain，application → domain）

#### 集成测试

- [ ] Subtask 4.6: 更新 `tests/integration/test_integration_hybrid_search.py`
  - 端到端：三路混合检索完整流程（Mock Dense/Sparse/Graph 服务）
  - 三路 RRF 加权融合
  - ColBERT 重排序（Mock 重排序服务）
  - 降级策略（Graph 通道失败、重排序失败）
  - 异常链路（RerankError 抛出）

**完成标准/Definition of Done:**
- [ ] `composition_root.py` 注册 `graph_search_service` / `reranker` / 升级 `hybrid_search_service` 端口
- [ ] 端口契约测试通过
- [ ] 所有架构约束测试通过
- [ ] 集成测试通过
- [ ] 领域层零外部依赖

---

### Task 5: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6

> **性质说明：** 本 Task 是对 Story 收尾阶段的交付物与完成清单进行最终验收。

- [ ] Subtask 5.1: 场景 1 — 验证 `src` 完成清单的逐项确认
  - `src/domain/ports/reranker.py` — RerankerPort（不含 RerankResult 值对象，已删除）
  - `src/domain/exceptions/reranker_exceptions.py` — RerankError（EXCEPTION_350，HTTP 500 精确映射）
  - `src/domain/exceptions/__init__.py` — 导出重排序异常
  - `src/domain/exceptions/_code_ranges.py` — 新增 reranker 子域 (350, 359)
  - `src/domain/ports/__init__.py` — 导出 RerankerPort
  - `src/application/services/graph_search_service.py` — GraphSearchService（仅注入 L5GraphPort）
  - `src/application/services/hybrid_search_service.py` — 升级（三路 + 权重 + 重排序，HybridSearchError 替换 RuntimeError）
  - `src/infrastructure/external_services/reranker/litellm_reranker_client.py` — LiteLLMRerankerClient（litellm.rerank() 专用 API，不经过 LLMClientPort）
  - `src/infrastructure/external_services/reranker/__init__.py` — 模块导出
  - `src/infrastructure/external_services/reranker/config.py` — RerankerConfig（必需，非可选）
  - `src/domain/exceptions/hybrid_search_exceptions.py` — HybridSearchError（EXCEPTION_209，继承 BusinessException，替换 RuntimeError 历史违规）
  - `src/composition_root.py` — 注册 graph_search_service / reranker / 升级 hybrid_search_service 端口（含 compatibility 处理）
  - `src/interfaces/api/exception_handlers.py` — EXCEPTION_HTTP_MAP 更新（RerankError→500, HybridSearchError→500）
- [ ] Subtask 5.2: 场景 2 — 验证 `tests/unit`、`tests/contracts`、`tests/acceptance` 完成清单
  - `tests/unit/domain/ports/test_reranker_port.py`（无 RerankResult 测试）
  - `tests/unit/domain/services/test_rrf_fusion.py`（更新，补充三路默认权重/对称权重用例）
  - `tests/unit/domain/exceptions/test_reranker_exceptions.py`（含精确类型断言 HTTP 500）
  - `tests/unit/domain/exceptions/test_hybrid_search_exceptions.py`（HybridSearchError 异常测试）
  - `tests/unit/application/test_graph_search_service.py`（新建）
  - `tests/unit/application/test_hybrid_search_service.py`（更新）
  - `tests/unit/infrastructure/external_services/reranker/test_litellm_reranker_client.py`
  - `tests/unit/architecture/test_arch_hybrid_search.py`（更新，覆盖 reranker/GraphSearchService/LiteLLMRerankerClient）
  - `tests/contracts/test_port_contract_reranker.py`
  - `tests/contracts/test_port_contract_search_services.py`（更新，新增 GraphSearchService 端口契约）
  - `tests/integration/test_integration_hybrid_search.py`（更新，三路集成测试）
  - `tests/acceptance/test_acceptance_hybrid_search.feature`（更新，三路场景）
  - `tests/acceptance/test_acceptance_hybrid_search.py`（更新，三路步骤实现）
- [ ] Subtask 5.3: 运行开发结束验收测试并确认通过
- [ ] Subtask 5.4: 运行 `poetry run pytest --tb=short -q`、`poetry run ruff check src/`、`poetry run mypy src/`

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 三路 RRF 融合架构设计

**核心架构模式：`HybridSearchService` 三路编排 + 可选重排序**

```
用户查询文本
    │
    ├─→ Dense 通道（3.1a 已实现）
    │   └─→ DenseSemanticSearchService.search()
    │       └─→ embed_query → search() → DenseSearchResult[]
    │
    ├─→ Sparse 通道（3.1b 已实现）
    │   └─→ Bm25SparseSearchService.search()
    │       └─→ embed_sparse → search_sparse() → SearchResult[]
    │
    └─→ Graph 通道（本 Story 新增）
        └─→ GraphSearchService.search()
            └─→ L5GraphPort.find_related() → SearchResult[]
                │
                ▼
        asyncio.gather（三路并行）
            │
            ▼
        RRF 融合（domain/services/rrf_fusion.py）
            fuse(dense, sparse, graph, weights=[1.0, 1.0, 0.5])
            │
            ▼
        ColBERT 重排序（可选，本 Story 新增）
            reranker.rerank(query, fused_results, top_k=20)
            │
            ▼
        最终结果（截断至 limit）
```

### 与 Story 3.1b 现有 RRF 融合的集成

**现有 `fuse()` 函数（已支持三路，无需修改核心代码）：**

```python
from src.domain.services.rrf_fusion import fuse

# MVP 两路对称融合（Story 3.1b 现有）
fused = fuse(dense_results, sparse_results)

# V1 三路加权融合（Story 3.4 新增）
fused = fuse(dense_results, sparse_results, graph_results, weights=[1.0, 1.0, 0.5])
```

**向后兼容性：**
- `fuse()` 的 `*result_lists` 可变参数天然支持 1~N 路
- 两路调用不受影响（`fuse(dense, sparse)` 行为不变）
- `weights=None` 时使用对称融合 `[1.0] * N`（与原有行为一致）
- 默认权重从 `[1.0, 1.0]` 变为 `[1.0, 1.0, 0.5]`（三路时）

### GraphSearchService 设计

**Graph 检索作为第三路信号的策略（仅注入 L5GraphPort，不使用 GraphRetriever）：**

```
GraphSearchService
    │
    ├─→ 注入 L5GraphPort（领域端口，非 GraphRetriever）
    │
    ├─→ search(collection, query_text, limit, ...)
    │   │
    │   ├─→ 步骤1：L5GraphPort.search_entities(query_text, limit)
    │   │   （新增端口方法，按实体名模糊匹配，返回候选实体列表）
    │   │
    │   ├─→ 步骤2：对每个候选实体
    │   │   └─→ L5GraphPort.find_related(memory_id, max_depth=2)
    │   │       └─→ 返回关联实体 [{memory_id, type, properties, path}]
    │   │
    │   ├─→ 步骤3：聚合去重（按 memory_id），计算分数
    │   │   └─→ score = type_weight * connection_count / (1 + hops)
    │   │       type_weight: concept=0.8, person=0.6, organization=0.7, default=0.5
    │   │       hops = len(path)  # 从 path 长度计算
    │   │
    │   └─→ 转换为 SearchResult[]
    │       ├─→ id = entity["memory_id"]
    │       ├─→ score = 上述公式
    │       └─→ payload = {entity_type, properties, hops, connection_count}
    │
    └─→ 异常时返回空列表（透明降级）
```

**关键设计决策：**
- Graph 检索使用 `search_entities()` 将 `query_text` 解析为实体 ID（补齐 `query_text → memory_id` 的桥梁），再通过 `find_related()` 获取关联文档
- 分数公式统一为 `type_weight * connection_count / (1 + hops)`，融合了实体类型权重和遍历深度两个维度，**删除之前矛盾的两种独立方案**
- Graph 通道默认权重 0.5（低于 Dense/Sparse 的 1.0），因为其召回量通常较小
- 权重为线性乘子，仅相对比例影响排序，无需归一化（`fuse()` 已支持）

### 重排序设计（LiteLLMRerankerClient）

**MVP 轻量级重排序实现方案（使用 litellm.rerank() 专用 API，不经过 LLMClientPort）：**

```
LiteLLMRerankerClient
    │
    ├─→ 注入 RerankerConfig（model/base_url/api_key/timeout，from_env()）
    │
    ├─→ rerank(query, results, top_k=20)
    │   │
    │   ├─→ 调用 litellm.rerank() 专用端点
    │   │   （如 BAAI/bge-reranker-v2-m3，输入 query + documents 返回 score 数组）
    │   │
    │   ├─→ 分数映射：
    │   │   ├─→ score = 归一化重排序分数
    │   │   ├─→ payload["original_score"] = 原 RRF 分数
    │   │   └─→ payload["rerank_score"] = 重排序分数
    │   │
    │   ├─→ top_k 语义：截断参数
    │   │   （对全部输入重排序，仅返回前 top_k 个；top_k >= len 时返回全部）
    │   │
    │   └─→ 返回 list[SearchResult]（按 score 降序）
    │
    └─→ 失败时返回原始 results（透明降级）
```

**性能目标：**
- 重排序延迟 P95 < 200ms（Top-K=20，MVP 轻量级实现）
- 重排序不改变结果数量上限（受 `top_k` 截断约束）

### 延迟预算策略

**总延迟 P95 < 800ms 的预算分配：**

| 阶段 | 延迟预算 | 说明 |
|------|---------|------|
| 嵌入生成（Dense + Sparse 共享） | ~150ms | 单次 embed_query + embed_sparse 调用 |
| Dense 检索 | ~100ms | Qdrant search 调用 |
| Sparse 检索 | ~100ms | Qdrant search_sparse 调用 |
| Graph 检索 | ~200ms | Neo4j 图遍历（含 search_entities + find_related） |
| **并行 max** | **~400ms** | 四路（嵌入 + Dense + Sparse + Graph）并行，取最慢 |
| RRF 融合 | ~50ms | 三路各 ≤50 结果 |
| 重排序（可选） | ~200ms | litellm.rerank() Top-K=20 |
| **总延迟** | **~650ms** | `max(并行) + RRF + 重排序` < 800ms ✅ |

**公式：** `总延迟 = max(并行四路) + RRF 融合 + 重排序(可选)`
- 重排序分数映射到 `SearchResult.score` 字段

### 权重配置设计

**可配置权重支持：**

```python
# 默认权重（三路）
DEFAULT_WEIGHTS = [1.0, 1.0, 0.5]  # [dense, sparse, graph]

# 通过 HybridSearchService 构造参数配置
service = HybridSearchService(
    dense_search=...,
    sparse_search=...,
    graph_search=...,
    fuse=fuse,
    weights=[0.5, 0.3, 0.2],  # 自定义权重
    reranker=...,
)

# 通过 search() 方法参数覆盖（可选）
await service.search(
    collection="docs",
    query_text="市场分析",
    weights=[0.6, 0.3, 0.1],  # 单次查询权重覆盖
)
```

### 与已有可复用组件的集成

| 组件 | 文件路径 | 本 Story 用途 |
|------|---------|--------------|
| `fuse()` | `src/domain/services/rrf_fusion.py` | 三路加权 RRF 融合（复用，无需修改） |
| `L5GraphPort` | `src/domain/ports/l5_graph.py` | Graph 检索端口（需新增 `search_entities()` 方法） |
| `LiteLLMRerankerClient` | `src/infrastructure/external_services/reranker/litellm_reranker_client.py` | 重排序实现（使用 `litellm.rerank()` 专用 API，**不经过 LLMClientPort**） |
| `RerankerConfig` | `src/infrastructure/external_services/reranker/config.py` | 重排序配置（必需，非可选） |
| `DenseSemanticSearchService` | `src/application/services/dense_search_service.py` | Dense 通道（Story 3.1a 已实现） |
| `Bm25SparseSearchService` | `src/application/services/sparse_search_service.py` | Sparse 通道（Story 3.1b 已实现） |
| `HybridSearchService` | `src/application/services/hybrid_search_service.py` | 升级双路→三路编排（HybridSearchError 替换 RuntimeError） |
| `SearchResult` | `src/domain/ports/l3_vector.py` | 统一检索结果格式 |
| `ValidationError` | `src/domain/exceptions/` | 输入验证异常复用 |
| `HybridSearchError` | `src/domain/exceptions/hybrid_search_exceptions.py` | 三路均失败时专用异常（EXCEPTION_209） |

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── ports/
│   │   │   ├── __init__.py                    # 更新：导出 RerankerPort（不导出 RerankResult）
│   │   │   └── reranker.py                    # 新建：RerankerPort（不含 RerankResult）
│   │   ├── services/
│   │   │   └── rrf_fusion.py                  # 无需修改（已有 *result_lists 支持三路）
│   │   └── exceptions/
│   │       ├── __init__.py                    # 更新：导出 RerankError + HybridSearchError
│   │       ├── _code_ranges.py                # 更新：新增 reranker 子域 (350,359)
│   │       ├── reranker_exceptions.py          # 新建：RerankError (EXCEPTION_350)
│   │       └── hybrid_search_exceptions.py     # 新建：HybridSearchError (EXCEPTION_209)
│   ├── application/
│   │   └── services/
│   │       ├── graph_search_service.py         # 新建：GraphSearchService（仅注入 L5GraphPort）
│   │       └── hybrid_search_service.py        # 更新：三路 + 权重 + 重排序（HybridSearchError 替换 RuntimeError）
│   ├── infrastructure/
│   │   └── external_services/
│   │       └── reranker/                      # 新建目录
│   │           ├── __init__.py                # 新建：模块导出
│   │           ├── litellm_reranker_client.py # 新建：LiteLLMRerankerClient（litellm.rerank() 专用 API）
│   │           └── config.py                  # 新建：RerankerConfig（必需，非可选）
│   ├── interfaces/
│   │   └── api/
│   │       └── exception_handlers.py          # 更新：EXCEPTION_HTTP_MAP 新增 RerankError→500 + HybridSearchError→500
│   └── composition_root.py                    # 更新：注册 graph_search/reranker/升级 hybrid（含 compatibility 处理）
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── ports/
│   │   │   │   └── test_reranker_port.py      # 新建：端口测试（无 RerankResult）
│   │   │   ├── services/
│   │   │   │   └── test_rrf_fusion.py         # 更新：补充三路默认权重/对称权重用例（不新建文件）
│   │   │   └── exceptions/
│   │   │       ├── test_reranker_exceptions.py  # 新建：RerankError 异常测试（含精确类型断言 HTTP 500）
│   │   │       └── test_hybrid_search_exceptions.py # 新建：HybridSearchError 异常测试
│   │   ├── application/
│   │   │   └── test_graph_search_service.py   # 新建：Graph 检索服务测试（路径遵循项目结构）
│   │   │   └── test_hybrid_search_service.py  # 更新：三路测试（路径遵循项目结构）
│   │   └── infrastructure/
│   │       └── external_services/
│   │           └── reranker/
│   │               └── test_litellm_reranker_client.py # 新建：重排序客户端测试
│   ├── contracts/
│   │   ├── test_port_contract_reranker.py      # 新建：重排序端口契约测试
│   │   └── test_port_contract_search_services.py # 更新：新增 graph_search 端口 + 版本升级 compatibility
│   ├── integration/
│   │   └── test_integration_hybrid_search.py   # 更新：三路集成测试
│   └── acceptance/
│       ├── test_acceptance_hybrid_search_3_4.feature # 新建：三路场景（独立文件，不覆盖原 Story 3-1b）
│       └── test_acceptance_hybrid_search_3_4.py      # 新建：三路步骤实现（独立文件，不覆盖原 Story 3-1b）
```

### 环境变量设计

```bash
# 重排序配置（必需，通过 RerankerConfig.from_env() 加载）
export RERANKER_ENABLED=true
export RERANKER_MODEL=BAAI/bge-reranker-v2-m3   # 重排序模型
export RERANKER_TOP_K=20                          # 默认 Top-K 数量
export RERANKER_TIMEOUT=10                        # 重排序超时（秒）
export RERANKER_API_KEY=...                       # 重排序 API 密钥
export RERANKER_BASE_URL=...                      # 重排序 API 端点
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 3.1b: BM25 稀疏检索 + RRF 融合](./3-1b-bm25-sparse-search-rrf-fusion.md)
**来源:** [Story 3.2b: 实体抽取（LLM+ 规则混合）](./3-2b-entity-extraction-llm-rules.md)

**关键学习/Key Learnings:**
1. **`fuse()` 可变参数设计** — Story 3.1b 的 `fuse(*result_lists)` 可变参数天然支持三路扩展，无需修改核心函数签名。这是良好的前置设计。
2. **`SearchResult` 统一格式** — 所有检索通道输出统一 `SearchResult` 格式，Graph 检索可直接复用，无需额外适配。
3. **`HybridSearchService` 降级模式** — Story 3.1b 的 `_safe_dense_search()` / `_safe_sparse_search()` 模式是优秀的异常隔离设计，三路扩展遵循相同模式。
4. **L5GraphPort 复用** — Story 3.2b 已通过 `L5GraphPort` 持久化实体到 Neo4j，Story 3.4 的 Graph 检索可直接复用这些实体数据。
5. **端口契约测试模式** — 遵循"三方法"测试模式（注册验证、方法签名验证、元数据验证）。
6. **领域层零依赖** — `RerankerPort` 仅使用 Python 标准库和 `SearchResult`。
7. **异常合规红线** — 禁止裸内置异常（`RuntimeError`），必须走领域异常体系。Story 3.1b 遗留的 `RuntimeError` 历史违规在本 Story 同步修复。

**应用到本故事/Applied to This Story:**
- [ ] 直接复用 `fuse()` 的可变参数实现三路融合（回归验证，不新建测试文件）
- [ ] 复用 `SearchResult` 统一格式（删除冗余的 RerankResult 值对象）
- [ ] 遵循 `_safe_*_search()` 模式实现三路异常隔离
- [ ] 通过 `L5GraphPort` 接入 Neo4j 实体数据（仅端口注入，不使用 GraphRetriever）
- [ ] 严格遵循异常编码注册流程（350 + 209）
- [ ] 领域层端口仅使用 Python 标准库
- [ ] 重排序使用 `litellm.rerank()` 专用 API，不经过 LLMClientPort
- [ ] 三路均失败抛 `HybridSearchError` 替换 RuntimeError 历史违规

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
| **需求规格** | `_bmad-output/planning-artifacts/prd.md` |
| **异常设计** | `docs/architecture/sisys-uni-exception-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/3-1b-bm25-sparse-search-rrf-fusion.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/3-2b-entity-extraction-llm-rules.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] 前一个故事学习经验整合（Story 3.1b RRF + Story 3.2b 实体抽取）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 已有可复用组件清单明确（fuse()、L5GraphPort、RerankerConfig）
- [x] 端口契约清单定义完成（RerankerPort v1.0.0、GraphSearchService v1.0.0、HybridSearchService v1.1.0）
- [x] 异常体系设计完成（RerankError 编码 350 + HybridSearchError 编码 209）
- [x] 与 Story 3.1b RRF 融合的向后兼容设计完成
- [x] 三路加权融合设计完成（默认权重 [1.0, 1.0, 0.5]）
- [x] 重排序方案设计完成（litellm.rerank() 专用 API，不经过 LLMClientPort）
- [x] 文档审查修复完成（P0-1~3 RuntimeError/HTTP映射/LLM重排序 + P1/P2 共 26 项问题已修复）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-4-rrf-fusion-ranking.md`

**待创建的文件 (Dev Story 实施):**
- `src/domain/ports/reranker.py` — RerankerPort（不含 RerankResult 值对象）
- `src/domain/exceptions/reranker_exceptions.py` — RerankError（EXCEPTION_350）
- `src/domain/exceptions/hybrid_search_exceptions.py` — HybridSearchError（EXCEPTION_209）
- `src/application/services/graph_search_service.py` — GraphSearchService（仅注入 L5GraphPort）
- `src/infrastructure/external_services/reranker/litellm_reranker_client.py` — LiteLLMRerankerClient（litellm.rerank() 专用 API）
- `src/infrastructure/external_services/reranker/__init__.py` — 模块导出
- `src/infrastructure/external_services/reranker/config.py` — RerankerConfig（必需，非可选）
- `tests/unit/domain/ports/test_reranker_port.py`
- `tests/unit/domain/exceptions/test_reranker_exceptions.py`
- `tests/unit/domain/exceptions/test_hybrid_search_exceptions.py`
- `tests/unit/application/test_graph_search_service.py`
- `tests/unit/infrastructure/external_services/reranker/test_litellm_reranker_client.py`
- `tests/contracts/test_port_contract_reranker.py`

**更新的文件/Updated Files:**
- `src/domain/ports/__init__.py` — 导出 RerankerPort（不导出 RerankResult）
- `src/domain/exceptions/__init__.py` — 导出 RerankError + HybridSearchError
- `src/domain/exceptions/_code_ranges.py` — 新增 reranker 子域 (350-359)
- `src/domain/services/rrf_fusion.py` — 无需修改（已有 *result_lists 支持三路）
- `src/domain/ports/l5_graph.py` — 新增 `search_entities()` 方法（补齐 query_text→memory_id 桥梁）
- `src/application/services/hybrid_search_service.py` — 三路 + 权重 + 重排序升级（HybridSearchError 替换 RuntimeError）
- `src/interfaces/api/exception_handlers.py` — EXCEPTION_HTTP_MAP 新增 RerankError→500 + HybridSearchError→500
- `src/composition_root.py` — 注册 graph_search_service / reranker / 升级 hybrid_search_service（含 compatibility 处理）
- `tests/unit/domain/services/test_rrf_fusion.py` — 补充三路默认权重/对称权重用例（不新建文件）
- `tests/unit/application/test_hybrid_search_service.py` — 三路测试更新
- `tests/unit/architecture/test_arch_hybrid_search.py` — 架构约束更新（覆盖 reranker/GraphSearchService/LiteLLMRerankerClient）
- `tests/contracts/test_port_contract_search_services.py` — 端口契约更新（新增 GraphSearchService 端口契约）
- `tests/integration/test_integration_hybrid_search.py` — 集成测试更新
- `tests/acceptance/test_acceptance_hybrid_search.feature` — 更新 AC-6 RuntimeError→HybridSearchError 说明
- `tests/acceptance/test_acceptance_hybrid_search.py` — 更新 AC-6 步骤实现（RuntimeError→HybridSearchError）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.4 |
| **Story Key** | 3-4-rrf-fusion-ranking |
| **File** | `_bmad-output/implementation-artifacts/stories/3-4-rrf-fusion-ranking.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | P0-4 |
| **覆盖 FR** | FR-SR-04（RRF 融合排序） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`
6. [x] **Epic 3 架构对齐重构（2026-08-21）**：
   - [x] `HybridSearchService` 成为生产检索链路核心 — `LayeredRetrievalService`（Story 3.5）注入其作为 L3/L4/L1/L2 检索实现
   - [x] 三路 RRF 融合能力经 `LayeredRetrievalService.retrieve()` 统一入口对外暴露

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 运行 `dev-story` 开始实施
- [x] **Epic 3 架构对齐重构（2026-08-21）**：HybridSearchService 接入生产检索链路（被 LayeredRetrievalService 消费）
- [x] 运行 `code-review` 进行代码审查
- [x] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.2.1
**创建日期/Created:** 2026-08-10
**最后更新/Last Updated:** 2026-08-21
**更新说明/Description:**
- v1.2.1: Epic 3 架构对齐重构 — HybridSearchService 接入生产检索链路
  - LayeredRetrievalService（Story 3.5）注入 HybridSearchService，L3/L4/L1/L2 检索经三路 RRF 融合
  - LayeredRetrievalService.retrieve() 统一检索入口暴露三路能力
  - SemanticCacheMiddleware 包装的 HybridSearchService 获得生产消费者
- v1.2.0: 第3轮审查修复（异常契约表补全 + AC追溯矩阵修正 + 编码注册细节完善）
  - 异常契约表新增 HybridSearchError(EXCEPTION_209) 行
  - AC-5 追溯矩阵 Subtask 引用修正（1.4-1.6→1.7-1.9）
  - 编码注册细化：business 子域扩展至 209、CI 子域登记（allowed_child_parent_subdomains/nested_subdomains）同步说明
  - L5GraphPort.search_entities 方法签名与 Cypher 实现、契约测试更新说明
  - 验收测试需新增 Graph/重排序 fixtures（参考 embedding_service 的 skip 模式）
- v1.1.0: 文档审查修复（对标实际代码实现，修复 P0×3 + P1×7 + P2×16 共 26 项问题）
  - P0-1: 异常合规 — RuntimeError→HybridSearchError(EXCEPTION_209)
  - P0-2: HTTP 映射 — RerankError 精确注册 500 说明
  - P0-3: 重排序方案 — LLMClientPort→litellm.rerank() 专用 API
  - P1: GraphSearchService 仅注入 L5GraphPort（弃用 GraphRetriever）、search_entities() 新增、分数公式统一、构造签名向后兼容、端口升级 compatibility、延迟预算口径、RerankResult 删除
  - P2: 测试路径统一、重复测试文件合并、依赖方向矩阵严格化、RerankerConfig 必需化、环境变量行为定义、权重归一化说明等

<!-- 仅用作跟踪故事文件模板修订记录，故事开发时[务必删除]此段 -->
