# Story 3.4: RRF 融合排序

**Status:** `backlog`

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
**Then** 通过 `L5GraphPort.find_related()` 或 `GraphRetriever` 获取关联实体和文档
**And** 输出与 `SearchResult` 格式兼容的结果列表（`id`/`score`/`payload`）
**And** Graph 检索延迟 P95 < 200ms（含 Neo4j 图遍历）

**验证标准/Validation Criteria:**
- [ ] `GraphSearchService` 位于 `src/application/services/graph_search_service.py`
- [ ] 实现 `search(collection, query_text, limit, tenant_id, filter_payload)` 方法，签名与 Dense/Sparse 服务一致
- [ ] 注入 `L5GraphPort` 或 `GraphRetriever` 进行图遍历检索
- [ ] 输出结果转换为 `SearchResult` 格式（`id`/`score`/`payload`）
- [ ] 无匹配实体时返回空列表
- [ ] 异常时抛出 `SearchResult` 兼容的异常

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
**And** 总检索延迟 P95 < 800ms（含嵌入生成 + Dense 检索 + Sparse 检索 + Graph 检索 + RRF 融合）

**验证标准/Validation Criteria:**
- [ ] `HybridSearchService` 升级为三路编排（新增 `graph_search` 注入）
- [ ] 构造函数签名：`__init__(self, dense_search, sparse_search, graph_search, fuse, weights=None)`
- [ ] 使用 `asyncio.gather` 并行执行三路检索
- [ ] 降级策略完整：
  - 三路均成功 → 三路加权 RRF
  - Graph 失败 → 两路 RRF（Dense + Sparse）
  - Dense + Sparse 失败 → 单路 Graph 结果
  - 三路均失败 → `RuntimeError`
- [ ] 输入验证复用原有逻辑（空查询/空 Collection/无效 limit）

### AC-4: ColBERT 重排序端口与实现

**Given** RRF 融合后的 Top-K 候选结果
**When** 执行 ColBERT 重排序
**Then** 对 Top-K 候选（默认 K=20）进行精排
**And** 返回按重排序分数降序排列的结果列表
**And** ColBERT 重排序延迟 P95 < 200ms（MVP 轻量级实现）

**验证标准/Validation Criteria:**
- [ ] `RerankerPort` Protocol 定义于 `src/domain/ports/reranker.py`
- [ ] 方法：`async rerank(query: str, results: list[SearchResult], top_k: int = 20) -> list[SearchResult]`
- [ ] `RerankResult` 值对象（可选，可复用 SearchResult 的 score 字段存储重排序分数）
- [ ] `CrossEncoderReranker` 实现位于 `src/infrastructure/external_services/reranker/cross_encoder_reranker.py`
- [ ] 使用轻量级交叉编码器模型（如 `BAAI/bge-reranker-v2-m3`）或通过 LiteLLM 调用重排序 API
- [ ] 降级策略：重排序失败时返回原始 RRF 融合结果（不阻断主流程）
- [ ] 领域层零外部依赖（`RerankerPort` 仅使用 Python 标准库）

### AC-5: 重排序异常体系

**Given** 重排序过程中可能发生多种错误
**When** 定义重排序异常类
**Then** 继承项目统一异常层次结构
**And** 分配唯一异常编码

**验证标准/Validation Criteria:**
- [ ] `RerankError`（EXCEPTION_350）— 继承 `ExternalException`，对应重排序失败
- [ ] 异常编码在 `_code_ranges.py` 注册，无碰撞
- [ ] 异常在 `__init__.py` 导出，在 `EXCEPTION_HTTP_MAP` 注册

### AC-6: 端口注册与 DI 集成

**Given** 所有组件实现完成
**When** 在 `composition_root.py` 注册
**Then** `graph_search_service`、`reranker`、升级后的 `hybrid_search_service` 端口注册为 SCOPED
**And** 通过 `Resolver` 可正确解析
**And** 端口契约测试通过

**验证标准/Validation Criteria:**
- [ ] `composition_root.py` 注册 `graph_search_service` 端口（GraphSearchService）
- [ ] `composition_root.py` 注册 `reranker` 端口（CrossEncoderReranker 实现 RerankerPort）
- [ ] `composition_root.py` 升级 `hybrid_search_service` 端口注册（三路注入）
- [ ] 端口契约测试 `tests/contracts/test_port_contract_hybrid_search.py` 更新通过
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

**新建值对象（领域层 `src/domain/ports/reranker.py`）：**
- [ ] `RerankResult` frozen dataclass
  - 字段: `id: str | int` — 文档 ID
  - `score: float` — 重排序得分
  - `payload: dict[str, Any]` — 元数据
  - `original_score: float` — 原始 RRF 分数（用于对比分析）

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

**新建异常类（`src/domain/exceptions/reranker_exceptions.py`）：**

| 异常类 | 编码 | 继承 | HTTP 映射 | 说明 |
|--------|------|------|-----------|------|
| `RerankError` | EXCEPTION_350 | `ExternalException` | 500 | 重排序失败（模型加载失败/调用超时/结果异常）。继承 `ExternalException` 理由：重排序是外部模型服务，属于外部异常范畴。HTTP 500 理由：服务端处理失败 |

**编码分配验证：**
- `external` 子域范围：301-399 ✅
- `embedding` 306-308, `sandbox` 309-319, `ocr` 320-329, `llm` 330-339, `entity_extraction` 340-349
- **重排序分配 350** — 紧接实体抽取之后，预留 350-359 范围
- 运行 `grep -r "EXCEPTION_35[0-9]" src/domain/exceptions/` 确认无碰撞

- [ ] 归属模块与基类 — 重排序属于外部模型服务，继承 `ExternalException`
- [ ] 唯一编码分配 — 350，确认无碰撞
- [ ] 构造器参数设计 — 携带 `model_name`、`top_k`、`result_count` 等上下文
  - `model_name: str` — 重排序模型名称
  - `top_k: int` — 重排序的 Top-K 数量
  - `result_count: int` — 输入结果数量
- [ ] 编码注册 — 在 `_code_ranges.py` 的 `_CLASS_TO_SUBDOMAIN` 中注册；新增 `reranker` 子域范围 (350, 359)
- [ ] 导出完整性 — `__init__.py` + `EXCEPTION_HTTP_MAP`
- [ ] 测试覆盖 — 构造/`to_dict()`/HTTP 映射/编码唯一性

#### 六边形架构约束（必须遵守）

> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 本 Story 职责 |
|------|------|-------------|
| domain | `src/domain/` | RerankerPort 端口 + RerankResult 值对象 + 重排序异常 |
| application | `src/application/` | GraphSearchService（第三路） + HybridSearchService 升级（三路+重排序编排） |
| infrastructure | `src/infrastructure/` | CrossEncoderReranker 实现 + GraphRetriever 复用 |
| interfaces | `src/interfaces/` | 无新增 |

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | infrastructure |
|------------|--------|-------------|----------------|
| **domain (RerankerPort)** | — | ✗ 禁止 | ✗ 禁止 |
| **application (GraphSearchService/HybridSearchService)** | ✓ 允许 | — | ✗ 禁止 |
| **infrastructure (CrossEncoderReranker)** | ✓ 允许 | ✓ 允许 | — |

**领域层零依赖原则** — `src/domain/ports/reranker.py` 仅依赖：
- Python 标准库（`dataclasses`, `typing`）
- `typing.Protocol` / `@runtime_checkable`
- 领域值对象（`RerankResult`）
- `SearchResult`（来自 `src/domain/ports/l3_vector.py`）
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
| **TDD 单元测试** | RerankerPort + RerankResult | 端口契约、值对象构造 | `test_reranker_port.py` | Task 1 |
| **TDD 单元测试** | 重排序异常 | 构造/属性/to_dict()/HTTP 映射 | `test_reranker_exceptions.py` | Task 1 |
| **TDD 单元测试** | GraphSearchService | L5GraphPort 包装、SearchResult 转换 | `test_graph_search_service.py` | Task 2 |
| **TDD 单元测试** | CrossEncoderReranker | 重排序逻辑、降级策略 | `test_cross_encoder_reranker.py` | Task 2 |
| **TDD 单元测试** | 升级 HybridSearchService | 三路编排、加权融合、降级 | `test_hybrid_search_service.py` | Task 3 |
| **TDD 单元测试** | 三路 RRF 融合 | 加权融合正确性、跨通道去重 | `test_rrf_fusion_three_way.py` | Task 1 |
| **TDD 验收测试** | Gherkin 场景（更新） | 业务价值验收 | `test_acceptance_hybrid_search.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现（更新） | 步骤函数实现 | `test_acceptance_hybrid_search.py` | Task 0 |
| **TDD 契约测试** | RerankerPort | 端口注册/解析/契约门禁 | `test_port_contract_reranker.py` | Task 0 |
| **TDD 契约测试** | HybridSearchService（升级） | 端口注册/解析/契约门禁 | `test_port_contract_search_services.py` | Task 0 |
| **TDD 领域异常测试** | 重排序异常 | 编码唯一性/子域范围 | `test_error_code_uniqueness.py` + `test_code_ranges.py` | Task 1 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖 | `test_arch_hybrid_search.py` | Task 4 |
| **集成测试** | 混合检索管线 | 端到端检索流程 | `test_integration_hybrid_search.py` | Task 4 |

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
| **外部服务隔离** | Neo4j 使用 AsyncMock(spec=L5GraphPort)，重排序模型使用本地 Mock 服务 | 真实调用导致失败 |
| **配置隔离** | 每个测试使用独立的权重配置实例 | 配置污染 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突 |
| **BDD async 配合** | BDD 步骤函数用 event_loop.run_until_complete() | context 数据丢失 |

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
| AC-2 | 三路加权 RRF 融合 | Task 1 | Subtask 1.1-1.3 | `test_rrf_fusion_three_way.py` |
| AC-3 | 升级后的混合检索编排服务 | Task 3 | Subtask 3.1-3.3 | `test_hybrid_search_service.py` |
| AC-4 | ColBERT 重排序端口与实现 | Task 2 | Subtask 2.4-2.6 | `test_reranker_port.py` + `test_cross_encoder_reranker.py` |
| AC-5 | 重排序异常体系 | Task 1 | Subtask 1.4-1.6 | `test_reranker_exceptions.py` |
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

- [ ] Subtask 0.1: 定义 RerankerPort 端口契约（rerank 方法签名 + RerankResult 值对象）设计
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

#### TDD 循环 [A]：三路加权 RRF 融合测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_rrf_fusion_three_way.py`（三路加权融合 + 参数校验） |
| 🟢 绿 | 验证已有 `fuse()` 函数支持三路加权（无需修改代码，仅验证和补全测试） |
| 🔄 重构 | 如需要，优化 `fuse()` 参数校验逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写三路 RRF 融合失败测试
  - **Happy Path:** 三路对称融合（`fuse(dense, sparse, graph)`）— 验证 `fuse()` 可变参数支持三路
  - **Happy Path:** 三路加权融合（`fuse(dense, sparse, graph, weights=[0.4, 0.4, 0.2])`）
  - **Happy Path:** 默认权重 `[1.0, 1.0, 0.5]` 测试
  - **Edge Case:** 某路空列表（如 `graph=[]`）— 正常参与融合，分数为 0
  - **Edge Case:** weights 长度与 result_lists 不匹配 — 抛出 `ValidationError`
  - **Edge Case:** weights 含负值 — 抛出 `ValidationError`
  - **Edge Case:** 单路直通（`fuse(dense)`）— 直接返回
  - **Edge Case:** 空输入（`fuse()`）— 返回空列表
  - **跨通道去重:** 同文档在三路中出现，RRF 分数三路叠加，payload 保留首次出现
  - **分数验证:** 使用 `math.isclose` 验证 RRF 分数计算正确性
  - **性能测试:** `time.perf_counter()` 采样 ≥ 100 次，三路各 ≤ 50 结果，P95 < 50ms
- [ ] Subtask 1.2: 🟢 绿 — 验证 `fuse()` 函数
  - 已有 `fuse()` 的 `*result_lists` 可变参数天然支持三路
  - 已有 `weights` 参数支持加权配置
  - 无需修改核心代码，仅需验证现有实现满足三路需求
  - 如有必要，增强 `fuse()` 的权重校验逻辑（如警告日志记录）
- [ ] Subtask 1.3: 🔄 重构 — 运行 `ruff check` + `mypy` + `pytest tests/unit/domain/services/ -v`

#### TDD 循环 [B]：RerankerPort + RerankResult

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_reranker_port.py`（端口契约 + 值对象构造） |
| 🟢 绿 | 实现 `src/domain/ports/reranker.py`（RerankerPort + RerankResult） |
| 🔄 重构 | 优化类型注解，运行 `ruff` + `mypy` |

- [ ] Subtask 1.4: 🔴 红 — 编写 RerankerPort 失败测试
  - `RerankResult` frozen dataclass 构造（所有字段默认值正确）
  - `RerankerPort` Protocol 结构验证（`rerank()` 方法签名）
  - `@runtime_checkable` 可用
  - 方法签名：`async rerank(query: str, results: list[SearchResult], top_k: int = 20) -> list[SearchResult]`
- [ ] Subtask 1.5: 🟢 绿 — 实现 RerankerPort + RerankResult
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
- [ ] 三路加权 RRF 融合测试通过（验证已有 `fuse()` 函数支持三路）
- [ ] RerankerPort + RerankResult 实现完成
- [ ] RerankError 异常实现完成
- [ ] TDD 循环全部通过
- [ ] 编码无碰撞验证通过
- [ ] 领域层覆盖率≥90%

---

### Task 2: 基础设施层 — GraphSearchService + CrossEncoderReranker

**关联 AC:** AC-1, AC-4

> **基础设施层依赖：** 本 Task 代码位于 `src/infrastructure/` 和 `src/application/`。
> **GraphSearchService** 在应用层，注入 `L5GraphPort` 或 `GraphRetriever`。
> **CrossEncoderReranker** 在基础设施层，使用交叉编码器模型或 LiteLLM。

#### TDD 循环 [A]：GraphSearchService（应用层，第三路检索）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_graph_search_service.py` |
| 🟢 绿 | 实现 `src/application/services/graph_search_service.py` |
| 🔄 重构 | 优化图遍历逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 2.1: 🔴 红 — 编写 GraphSearchService 失败测试
  - **Happy Path:** 通过 `L5GraphPort.find_related()` 获取关联实体，转换为 `SearchResult` 格式
  - **Happy Path:** 返回结果包含正确的 `id`/`score`/`payload` 字段
  - **Edge Case:** 无关联实体返回空列表
  - **Edge Case:** 空查询文本返回空列表（与 Dense/Sparse 行为一致）
  - **Edge Case:** `L5GraphPort` 抛出异常时透明降级返回空列表
  - **签名对齐:** 验证 `search(collection, query_text, limit, tenant_id, filter_payload)` 签名与 Dense/Sparse 一致
  - **性能:** Graph 检索延迟 P95 < 200ms（通过 AsyncMock 模拟）
- [ ] Subtask 2.2: 🟢 绿 — 实现 GraphSearchService
  - 构造函数注入 `L5GraphPort`（或 `GraphRetriever`）
  - 实现 `search()` 方法，签名严格对齐 `DenseSemanticSearchService`
  - 核心逻辑：通过 `L5GraphPort.find_related()` 获取关联实体，构建 `SearchResult`
  - 实体类型 → 分数映射规则（如 `concept` 类型权重 0.8，`person` 类型权重 0.6）
  - 输出格式转换为 `SearchResult`（`id` 使用实体 `memory_id`，`score` 使用关系权重，`payload` 包含实体元数据）
  - 异常处理：`L5GraphPort` 失败时返回空列表（不抛出异常，由编排层处理）
- [ ] Subtask 2.3: 🔄 重构 — 运行 `ruff` + `mypy`

#### TDD 循环 [B]：CrossEncoderReranker（基础设施层，重排序实现）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/reranker/test_cross_encoder_reranker.py` |
| 🟢 绿 | 实现 `src/infrastructure/external_services/reranker/cross_encoder_reranker.py` |
| 🔄 重构 | 优化重排序逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 2.4: 🔴 红 — 编写 CrossEncoderReranker 失败测试
  - **Happy Path:** 对 Top-K 结果进行重排序，返回按新分数降序排列的结果
  - **Happy Path:** 重排序后分数分布在 [0, 1] 范围内
  - **Happy Path:** 输入结果数量 > top_k 时仅重排序前 top_k 个
  - **Edge Case:** 输入空列表返回空列表
  - **Edge Case:** 重排序模型调用失败（`RerankError`）→ 返回原始结果（透明降级）
  - **Edge Case:** 输入结果数量 < top_k 时全部重排序
  - **Edge Case:** 重排序不改变结果数量（仅重排序分数）
  - **性能:** 重排序延迟 P95 < 200ms（MVP 轻量级实现）
- [ ] Subtask 2.5: 🟢 绿 — 实现 CrossEncoderReranker
  - 实现 `RerankerPort` 接口（`rerank(query, results, top_k=20)`）
  - MVP 轻量级实现方案：
    - 方案 A：通过 LiteLLM 调用云端重排序 API（如 `BAAI/bge-reranker-v2-m3`）
    - 方案 B：本地交叉编码器（如 `sentence-transformers` 的 `cross-encoder` 模型）
  - 选择方案 A（LiteLLM 云端）作为默认实现，避免本地模型依赖
  - 降级策略：调用失败时返回原始 `results`（不阻断主流程）
  - 重排序分数映射回 `SearchResult.score` 字段
  - `original_score` 可选保留在 `payload` 中
- [ ] Subtask 2.6: 🔄 重构 — 运行 `ruff` + `mypy`

**完成标准/Definition of Done:**
- [ ] GraphSearchService 实现完成（L5GraphPort 包装 + SearchResult 格式）
- [ ] CrossEncoderReranker 实现完成（RerankerPort 接口 + 降级策略）
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
| 🔴 红 | 编写 `tests/unit/application/services/test_hybrid_search_service.py`（更新，新增三路测试） |
| 🟢 绿 | 升级 `src/application/services/hybrid_search_service.py`（三路注入 + 可配置权重 + 重排序集成） |
| 🔄 重构 | 优化编排逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 3.1: 🔴 红 — 编写三路混合检索升级失败测试
  - **Happy Path:** 三路（Dense + Sparse + Graph）并行检索，RRF 加权融合
  - **Happy Path:** 三路均成功，默认权重 `[1.0, 1.0, 0.5]` 融合正确
  - **Happy Path:** 自定义权重（如 `[0.5, 0.3, 0.2]`）通过 `search()` 参数传入
  - **Happy Path:** 三路融合后结果按 RRF 分数降序排列
  - **降级: Graph 失败** → 两路（Dense + Sparse）RRF 融合，日志 WARNING
  - **降级: Dense + Sparse 均失败** → 单路 Graph 结果返回
  - **降级: 三路均失败** → `RuntimeError`
  - **降级: Graph 空结果** → 正常参与 RRF 融合（空列表，分数为 0）
  - **重排序集成:** 三路融合后，对结果调用 `RerankerPort.rerank()` 重排序
  - **重排序降级:** 重排序失败时返回原始 RRF 融合结果
  - **输入验证:** 空查询/空 Collection/无效 limit 抛出 `ValidationError`
  - **向后兼容:** 原有两路（Dense + Sparse）调用方式仍正常工作
- [ ] Subtask 3.2: 🟢 绿 — 升级 HybridSearchService
  - 构造函数新增 `graph_search` 参数（`GraphSearchService` 类型）
  - 构造函数新增 `weights` 参数（`list[float] | None = None`，默认 `[1.0, 1.0, 0.5]`）
  - 构造函数新增 `reranker` 参数（`RerankerPort | None = None`，可选）
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

- [ ] Subtask 4.1: 更新 `src/domain/ports/__init__.py` 导出 `RerankerPort`、`RerankResult`
- [ ] Subtask 4.2: 更新 `src/composition_root.py` 注册相关端口
  ```python
  # 注册 GraphSearchService（第三路检索）
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

  # 注册 CrossEncoderReranker（重排序器）
  register_port(
      name="reranker",
      version="v1.0.0",
      interface=RerankerPort,
      impl=lambda resolver: CrossEncoderReranker(
          llm_client=resolver.resolve("llm_client"),
          config=RerankerConfig.from_env(),
      ),
      module="src.infrastructure.external_services.reranker.cross_encoder_reranker",
      lifetime=Lifetime.SCOPED,
      owner="search-team",
      tags=("reranker", "colbert", "search"),
  )

  # 升级 HybridSearchService 注册（三路注入 + 可配置权重 + 重排序）
  register_port(
      name="hybrid_search_service",
      version="v1.1.0",
      interface=HybridSearchService,
      impl=lambda resolver: HybridSearchService(
          dense_search=resolver.resolve("dense_search_service"),
          sparse_search=resolver.resolve("sparse_search_service"),
          graph_search=resolver.resolve("graph_search_service"),
          fuse=fuse,
          weights=[1.0, 1.0, 0.5],
          reranker=resolver.resolve("reranker"),
      ),
      module="src.application.services.hybrid_search_service",
      lifetime=Lifetime.SCOPED,
      owner="search-team",
      tags=("search", "hybrid", "rrf", "three-way"),
  )
  ```
  - 生命周期: SCOPED
  - Owner: search-team
  - 注意：`HybridSearchService` 版本从 `v1.0.0` 升级到 `v1.1.0`

#### 端口契约测试

- [ ] Subtask 4.3: 创建 `tests/contracts/test_port_contract_reranker.py`
  - 验证 `reranker` 端口已注册到 Registry
  - 验证 `Resolver` 可解析 `reranker`
  - 验证 `RerankerPort` 方法签名正确
- [ ] Subtask 4.4: 更新 `tests/contracts/test_port_contract_search_services.py`
  - 验证 `graph_search_service` 端口已注册
  - 验证 `hybrid_search_service` 端口已注册且版本为 v1.1.0
  - 验证 `Resolver` 可解析各端口

#### 架构验证测试

- [ ] Subtask 4.5: 更新 `tests/unit/architecture/test_arch_hybrid_search.py`
  - 验证 `src/domain/ports/reranker.py` 零外部依赖（仅标准库）
  - 验证 `RerankerPort` 位于领域层
  - 验证 `CrossEncoderReranker` 位于基础设施层
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
  - `src/domain/ports/reranker.py` — RerankerPort + RerankResult
  - `src/domain/exceptions/reranker_exceptions.py` — RerankError
  - `src/domain/exceptions/__init__.py` — 导出重排序异常
  - `src/domain/exceptions/_code_ranges.py` — 新增 reranker 子域
  - `src/domain/ports/__init__.py` — 导出 RerankerPort
  - `src/application/services/graph_search_service.py` — GraphSearchService
  - `src/application/services/hybrid_search_service.py` — 升级（三路 + 权重 + 重排序）
  - `src/infrastructure/external_services/reranker/cross_encoder_reranker.py` — CrossEncoderReranker
  - `src/infrastructure/external_services/reranker/__init__.py` — 模块导出
  - `src/infrastructure/external_services/reranker/config.py` — RerankerConfig（可选）
  - `src/composition_root.py` — 注册 graph_search_service / reranker / 升级 hybrid_search_service 端口
  - `src/interfaces/api/exception_handlers.py` — EXCEPTION_HTTP_MAP 更新
- [ ] Subtask 5.2: 场景 2 — 验证 `tests/unit`、`tests/contracts`、`tests/acceptance` 完成清单
  - `tests/unit/domain/ports/test_reranker_port.py`
  - `tests/unit/domain/services/test_rrf_fusion_three_way.py`
  - `tests/unit/domain/exceptions/test_reranker_exceptions.py`
  - `tests/unit/application/services/test_graph_search_service.py`
  - `tests/unit/application/services/test_hybrid_search_service.py`（更新）
  - `tests/unit/infrastructure/external_services/reranker/test_cross_encoder_reranker.py`
  - `tests/unit/architecture/test_arch_hybrid_search.py`（更新）
  - `tests/contracts/test_port_contract_reranker.py`
  - `tests/contracts/test_port_contract_search_services.py`（更新）
  - `tests/integration/test_integration_hybrid_search.py`（更新）
  - `tests/acceptance/test_acceptance_hybrid_search.feature`（更新）
  - `tests/acceptance/test_acceptance_hybrid_search.py`（更新）
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

**Graph 检索作为第三路信号的策略：**

```
GraphSearchService
    │
    ├─→ 注入 L5GraphPort
    │
    ├─→ search(collection, query_text, limit, ...)
    │   │
    │   ├─→ 解析 query_text 中的实体关键词
    │   │   （简化 MVP：使用 query_text 直接搜索实体名称）
    │   │
    │   ├─→ L5GraphPort.find_related(entity_id, max_depth=2, limit=limit)
    │   │   │
    │   │   └─→ 返回关联实体列表 [{memory_id, type, properties, path}, ...]
    │   │
    │   └─→ 转换为 SearchResult[]
    │       ├─→ id = entity["memory_id"]
    │       ├─→ score = 1.0 / (1 + hops)  # 深度越近分数越高
    │       └─→ payload = {entity_type, properties, ...}
    │
    └─→ 异常时返回空列表（透明降级）
```

**关键设计决策：**
- Graph 检索使用 `query_text` 中的实体名称匹配 Neo4j 节点
- MVP 阶段简化：Graph 检索作为"实体关联推荐"，不执行复杂的图查询解析
- 分数基于遍历深度（hops）：越近的关联实体分数越高
- Graph 通道默认权重 0.5（低于 Dense/Sparse 的 1.0），因为其召回量通常较小

### ColBERT 重排序设计

**MVP 轻量级重排序实现方案：**

```
CrossEncoderReranker
    │
    ├─→ 注入 LLMClientPort（Story 3.2a 提供）
    │
    ├─→ rerank(query, results, top_k=20)
    │   │
    │   ├─→ 取前 top_k 个结果
    │   │   （input length > top_k 时截断，否则全部重排序）
    │   │
    │   ├─→ 对每个 (query, result.payload.text) 对计算相关性分数
    │   │   │
    │   │   └─→ 使用交叉编码器（cross-encoder）模型
    │   │       方案 A（默认）：通过 LiteLLM 调用云端重排序 API
    │   │       方案 B（备选）：本地 sentence-transformers cross-encoder
    │   │
    │   ├─→ 按新分数降序排列
    │   │
    │   └─→ 返回重排序后的 SearchResult[]（保留原始 payload）
    │
    └─→ 失败时返回原始 results（透明降级）
```

**性能目标：**
- 重排序延迟 P95 < 200ms（Top-K=20，MVP 轻量级实现）
- 重排序不改变结果数量（仅重排序分数）
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
| `L5GraphPort` | `src/domain/ports/l5_graph.py` | Graph 检索端口（`find_related()` 方法） |
| `GraphRetriever` | `src/infrastructure/storage/neo4j/graph_retriever.py` | 图检索实现（可选，也可通过 L5GraphPort 实现） |
| `LLMClientPort` | `src/domain/ports/llm_client.py` | 重排序模型的 LLM 调用（Story 3.2a 提供） |
| `DenseSemanticSearchService` | `src/application/services/dense_search_service.py` | Dense 通道（Story 3.1a 已实现） |
| `Bm25SparseSearchService` | `src/application/services/sparse_search_service.py` | Sparse 通道（Story 3.1b 已实现） |
| `HybridSearchService` | `src/application/services/hybrid_search_service.py` | 升级双路→三路编排 |
| `SearchResult` | `src/domain/ports/l3_vector.py` | 统一检索结果格式 |
| `ValidationError` | `src/domain/exceptions/` | 输入验证异常复用 |

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── ports/
│   │   │   ├── __init__.py                    # 更新：导出 RerankerPort
│   │   │   └── reranker.py                    # 新建：RerankerPort + RerankResult
│   │   ├── services/
│   │   │   └── rrf_fusion.py                  # 无需修改（已有 *result_lists 支持三路）
│   │   └── exceptions/
│   │       ├── __init__.py                    # 更新：导出 RerankError
│   │       ├── _code_ranges.py                # 更新：新增 reranker 子域
│   │       └── reranker_exceptions.py          # 新建：RerankError
│   ├── application/
│   │   └── services/
│   │       ├── graph_search_service.py         # 新建：GraphSearchService
│   │       └── hybrid_search_service.py        # 更新：三路 + 权重 + 重排序
│   ├── infrastructure/
│   │   └── external_services/
│   │       └── reranker/                      # 新建目录
│   │           ├── __init__.py                # 新建：模块导出
│   │           ├── cross_encoder_reranker.py  # 新建：CrossEncoderReranker
│   │           └── config.py                  # 新建：RerankerConfig（可选）
│   ├── interfaces/
│   │   └── api/
│   │       └── exception_handlers.py          # 更新：EXCEPTION_HTTP_MAP 新增
│   └── composition_root.py                    # 更新：注册 graph_search/reranker/升级 hybrid
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── ports/
│   │   │   │   └── test_reranker_port.py      # 新建：端口 + 值对象测试
│   │   │   ├── services/
│   │   │   │   └── test_rrf_fusion_three_way.py # 新建：三路融合测试
│   │   │   └── exceptions/
│   │   │       └── test_reranker_exceptions.py  # 新建：异常测试
│   │   ├── application/
│   │   │   └── services/
│   │   │       ├── test_graph_search_service.py # 新建：Graph 检索服务测试
│   │   │       └── test_hybrid_search_service.py # 更新：三路测试
│   │   └── infrastructure/
│   │       └── external_services/
│   │           └── reranker/
│   │               └── test_cross_encoder_reranker.py # 新建：重排序测试
│   ├── contracts/
│   │   ├── test_port_contract_reranker.py      # 新建：重排序端口契约测试
│   │   └── test_port_contract_search_services.py # 更新：新增 graph_search 端口
│   ├── integration/
│   │   └── test_integration_hybrid_search.py   # 更新：三路集成测试
│   └── acceptance/
│       ├── test_acceptance_hybrid_search.feature # 更新：三路场景
│       └── test_acceptance_hybrid_search.py      # 更新：三路步骤实现
```

### 环境变量设计

```bash
# 重排序配置（可选，默认使用 LLMClientPort 默认配置）
export RERANKER_ENABLED=true
export RERANKER_MODEL=BAAI/bge-reranker-v2-m3   # 重排序模型
export RERANKER_TOP_K=20                          # 默认 Top-K 数量
export RERANKER_TIMEOUT=10                        # 重排序超时（秒）
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

**应用到本故事/Applied to This Story:**
- [ ] 直接复用 `fuse()` 的可变参数实现三路融合
- [ ] 复用 `SearchResult` 统一格式
- [ ] 遵循 `_safe_*_search()` 模式实现三路异常隔离
- [ ] 通过 `L5GraphPort` 接入 Neo4j 实体数据
- [ ] 严格遵循异常编码注册流程（350）
- [ ] 领域层端口仅使用 Python 标准库

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
- [x] 已有可复用组件清单明确（fuse()、L5GraphPort、GraphRetriever、LLMClientPort）
- [x] 端口契约清单定义完成（RerankerPort v1.0.0、GraphSearchService v1.0.0、HybridSearchService v1.1.0）
- [x] 异常体系设计完成（编码 350）
- [x] 与 Story 3.1b RRF 融合的向后兼容设计完成
- [x] 三路加权融合设计完成（默认权重 [1.0, 1.0, 0.5]）
- [x] ColBERT 重排序 MVP 轻量级方案设计完成

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-4-rrf-fusion-ranking.md`

**待创建的文件 (Dev Story 实施):**
- `src/domain/ports/reranker.py` — RerankerPort + RerankResult
- `src/domain/exceptions/reranker_exceptions.py` — RerankError
- `src/application/services/graph_search_service.py` — GraphSearchService
- `src/infrastructure/external_services/reranker/cross_encoder_reranker.py` — CrossEncoderReranker
- `src/infrastructure/external_services/reranker/__init__.py` — 模块导出
- `src/infrastructure/external_services/reranker/config.py` — RerankerConfig（可选）
- `tests/unit/domain/ports/test_reranker_port.py`
- `tests/unit/domain/services/test_rrf_fusion_three_way.py`
- `tests/unit/domain/exceptions/test_reranker_exceptions.py`
- `tests/unit/application/services/test_graph_search_service.py`
- `tests/unit/infrastructure/external_services/reranker/test_cross_encoder_reranker.py`
- `tests/contracts/test_port_contract_reranker.py`

**更新的文件/Updated Files:**
- `src/domain/ports/__init__.py` — 导出 RerankerPort
- `src/domain/exceptions/__init__.py` — 导出 RerankError
- `src/domain/exceptions/_code_ranges.py` — 新增 reranker 子域 (350-359)
- `src/application/services/hybrid_search_service.py` — 三路 + 权重 + 重排序升级
- `src/interfaces/api/exception_handlers.py` — EXCEPTION_HTTP_MAP 新增
- `src/composition_root.py` — 注册 graph_search_service / reranker / 升级 hybrid_search_service
- `tests/unit/application/services/test_hybrid_search_service.py` — 三路测试更新
- `tests/unit/architecture/test_arch_hybrid_search.py` — 架构约束更新
- `tests/contracts/test_port_contract_search_services.py` — 端口契约更新
- `tests/integration/test_integration_hybrid_search.py` — 集成测试更新
- `tests/acceptance/test_acceptance_hybrid_search.feature` — 验收场景更新
- `tests/acceptance/test_acceptance_hybrid_search.py` — 步骤实现更新

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

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-08-10
**最后更新/Last Updated:** 2026-08-10
**更新说明/Description:**
- v1.0.0: 创建故事文件

<!-- 仅用作跟踪故事文件模板修订记录，故事开发时[务必删除]此段 -->
