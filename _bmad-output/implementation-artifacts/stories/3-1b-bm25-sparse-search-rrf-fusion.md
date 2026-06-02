# Story 3-1b: BM25 稀疏检索 + RRF 融合

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 分析师,
**I want** 系统执行 BM25 稀疏检索并与 Dense 检索融合（RRF 算法）,
**So that** 同时支持语义检索和关键词检索，综合提升相关性。

### 业务价值

Story 3-1b 是 Epic 3（智能检索与知识发现）关键路径的第 2 个故事。它在已完成 Story 3-1a（Dense 语义检索）基础上，构建 BM25 稀疏检索管道和双路 RRF 融合机制，形成完整的 "Dense + Sparse → RRF 融合" 混合检索管道。

本 Story 交付后，后续 Story 3-4（RRF 融合排序）将扩展为三路（Dense + Sparse + Graph）+ ColBERT 重排序。

**Epic 3 内部依赖链：** 3-1a（Dense）→ **3-1b（BM25 + 双路 RRF）** → 3-4（三路 RRF + ColBERT）→ 3-5（分层检索）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: BM25 稀疏向量构建

**Given** BM25Builder 已加载停用词表
**When** 调用 `build_sparse_vector("企业战略规划报告")`
**Then** 返回 SparseVector 实例
**And** indices 和 values 长度一致且非空
**And** 英文停用词（如 "the"/"is"）被过滤（注：当前仅支持英文停用词，中文停用词待 Story 3-3 补充）
**And** 空文本返回空稀疏向量（indices=[], values=[]）

**验证标准/Validation Criteria:**
- [ ] SparseVector.indices 和 values 长度一致
- [ ] TF-IDF 权重计算正确（实际公式：`tf * (1.0 + log(1 + total_terms/(1 + freq)))`，其中 tf=freq/total_terms，total_terms 为当前文档词元数，freq 为词频——单文档内近似 IDF，非标准跨文档 IDF）
- [ ] 英文停用词正确过滤
- [ ] 空文本边界处理
- [ ] 词汇哈希映射稳定性（hash(term) % 1000000）

### AC-2: BM25 稀疏检索

**Given** Collection 包含已索引的文档（含稀疏向量）
**When** 执行 BM25 稀疏检索（query_text, limit=5）
**Then** 使用 BM25Builder 构建查询稀疏向量
**And** 在 Qdrant 中执行稀疏检索（NamedSparseVector）
**And** 返回最多 5 个结果，按 score 降序排列

**验证标准/Validation Criteria:**
- [ ] 端到端：text → sparse_vector → search_sparse → ranked results
- [ ] 结果包含 id, score, payload 字段
- [ ] 结果按 score 降序排列
- [ ] 空查询文本抛出 ValueError（与 DenseSemanticSearchService 一致）
- [ ] Payload 过滤正确传递（tenant_id, filter_payload）

### AC-3: Dense + Sparse 并行双路召回

**Given** DenseSemanticSearchService（Story 3-1a）和 SparseSearchService 均已注册
**When** 执行混合检索（query_text, limit=10）
**Then** Dense 检索与 Sparse 检索并行执行（asyncio.gather）
**And** 两路结果独立返回，互不影响
**And** 单路失败不影响另一路（异常隔离）

**验证标准/Validation Criteria:**
- [ ] 两路检索并发执行（验证 asyncio.gather 调用）
- [ ] Dense 检索失败时 Sparse 仍正常返回
- [ ] Sparse 检索失败时 Dense 仍正常返回
- [ ] 仅 Dense 结果不为空时的降级行为正确

### AC-4: RRF 双路融合排序

**Given** Dense 检索和 Sparse 检索均已返回结果
**When** 执行 RRF 融合排序（k=60）
**Then** 使用 RRF 算法 `score(d) = Σ 1/(k + rank_i(d))` 计算融合分数
**And** 返回结果按融合分数降序排列
**And** 同一文档在 Dense 和 Sparse 中均出现时，RRF 分数为两路贡献之和
**And** 仅在单路出现的文档仍保留在融合结果中

**验证标准/Validation Criteria:**
- [ ] RRF 公式实现正确（k=60 默认值，可配置）
- [ ] 融合结果按 score 降序
- [ ] 去重逻辑正确（按文档 ID 聚合两路 rank）
- [ ] 空结果处理（两路均为空时返回空列表）
- [ ] limit 参数正确截断融合结果

### AC-5: 检索延迟 P95<800ms

**Given** Collection 包含 100 个文档向量（Dense + Sparse）
**When** 执行 50 次混合检索（不含模型/服务首次加载）
**Then** 端到端延迟 P95 < 800ms（MVP，含 Dense embed + BM25 sparse + RRF 融合）
**And** BM25 稀疏检索延迟 P95 < 100ms
**And** RRF 融合延迟 P95 < 50ms

**验证标准/Validation Criteria:**
- [ ] 50 次查询 P95 < 800ms（GPU 模式，查询文本 ≤ 512 字符）
- [ ] CPU 模式下放宽至 P95 < 1500ms（CI 环境回退）
- [ ] BM25 单路检索 P95 < 100ms
- [ ] RRF 融合 P95 < 50ms
- [ ] 排除首次服务加载时间
- [ ] 集成测试使用短文本（≤ 512 字符）进行性能测量

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 数据模型 (Data Models)
- [ ] `SparseSearchResult` — TypedDict：id, score, payload（与 DenseSearchResult 结构对称）
- [ ] `HybridSearchResult` — TypedDict：id, score, payload, source（标记来源：dense/sparse/both）
- [ ] 复用已有 `SparseVector` dataclass（`src/infrastructure/storage/qdrant/models.py`，无需新建）
- [ ] 复用已有 `DenseSearchResult` TypedDict（`src/application/services/dense_search_service.py`）

#### 统一端口定义注册与管理 (Port Contract)

> **架构决策（2026-06-02）：** Story 3-1a 重构完成，`EmbeddingServicePort` 已新增 `encode_sparse()` 方法（BGE-M3 原生 Sparse 嵌入）。
> 因此 Story 3-1b **无需新建 BM25BuilderPort** — `SparseSearchService` 直接注入 `EmbeddingServicePort` 调用 `encode_sparse()`，
> 与 `DenseSemanticSearchService` 注入 `EmbeddingServicePort` 调用 `encode_text()` 的模式完全对称。
> 原有 `BM25Builder`（`src/infrastructure/storage/qdrant/bm25_builder.py`）降级为 fallback（模型不可用时可选回退），不进入正常检索路径。

- [ ] `sparse_search_service` — 新增应用服务端口
  - 端口名称：`sparse_search_service`，接口：`SparseSearchService`（服务类自身作为 interface）
  - 生命周期：SCOPED，Owner：search-team
  - 构造函数注入 `EmbeddingServicePort`（domain Protocol，调用 `encode_sparse()`）和 `L3VectorPort`（domain Protocol，调用 `search_sparse()`）
- [ ] `hybrid_search_service` — 新增应用服务端口
  - 端口名称：`hybrid_search_service`，接口：`HybridSearchService`（服务类自身作为 interface）
  - 生命周期：SCOPED，Owner：search-team
- [ ] `rrf_fusion` — RRF 融合算法（`src/shared/rrf_fusion.py` 纯函数，无端口注册）
- [ ] 端口注册中心 `src/domain/ports/registry.py` 中登记新端口（无需修改，自动通过 register_port 注册）
- [ ] 端口实现 `src/composition_root.py` 统一注册
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_sparse_hybrid_search.py`）

**端口契约清单：**

| 端口名称 | 版本 | 接口 | 实现模块 | 生命周期 | Owner |
|---------|------|------|---------|---------|-------|
| `sparse_search_service` | v1.0.0 | `SparseSearchService`（服务类自身作为 interface） | `src.application.services.sparse_search_service.SparseSearchService` | SCOPED | search-team |
| `hybrid_search_service` | v1.0.0 | `HybridSearchService`（服务类自身作为 interface） | `src.application.services.hybrid_search_service.HybridSearchService` | SCOPED | search-team |

**已有端口（复用，不修改）：**

| 端口名称 | 版本 | 接口 | 复用方式 |
|---------|------|------|---------|
| `embedding_service` | v1.0.0 | `EmbeddingServicePort` | **SparseSearchService 注入调用 `encode_sparse()`**（Story 3-1a 重构新增） |
| `l3_vector` | v1.0.0 | `L3VectorPort` | SparseSearchService 注入 search_sparse()；HybridSearchService 注入 search() |
| `dense_search_service` | v1.0.0 | `DenseSemanticSearchService` | HybridSearchService 注入 Dense 检索 |
| `qdrant_connection_manager` | v1.0.0 | `ConnectionManager` | Qdrant 连接管理（已有） |

**端口简化对比：**

| 维度 | 原设计（BM25BuilderPort） | 简化后（复用 EmbeddingServicePort） |
|------|--------------------------|-------------------------------------|
| 新增 domain Protocol | `BM25BuilderPort` | 无（复用已有 EmbeddingServicePort） |
| Sparse 向量来源 | `BM25Builder.build_sparse_vector()` | `EmbeddingServicePort.encode_sparse()` |
| 中文分词 | ❌ 空格切分 | ✅ BGE-M3 原生多语言 tokenizer |
| 一次推理产出 | 仅 Sparse | **Dense + Sparse 同时产出** |
| 新增端口数 | 3 | 2（减少 1 个） |

#### API 契约 (API Contract)
- [ ] 本 Story 不涉及 REST API 路由（纯应用层服务，API 路由由 Epic 7 提供）

#### 六边形架构约束（必须遵守）

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 复用已有 `EmbeddingServicePort`（含 `encode_sparse()`）和 `L3VectorPort` |
| application | `src/application/` | SparseSearchService + HybridSearchService + RRF 融合纯函数 |
| interfaces | `src/interfaces/` | 本 Story 不涉及 |
| infrastructure | `src/infrastructure/` | 本 Story 不新增基础设施实现（BGE3EmbeddingService 已实现 encode_sparse） |
| shared | `src/shared/` | rrf_fusion.py 纯函数（零外部依赖） |

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | interfaces | infrastructure | shared |
|---|---|---|---|---|---|
| **domain** | — | ✗ | ✗ | ✗ | ✗ |
| **application** (`sparse_search_service.py`) | ✓ 导入 EmbeddingServicePort + L3VectorPort | — | ✗ | ✗ | ✗ |
| **application** (`hybrid_search_service.py`) | ✗（通过注入 DenseSearch + SparseSearch 间接使用） | ✓ 导入 DenseSemanticSearchService + SparseSearchService | ✗ | ✗ | ✓ 导入 rrf_fusion |
| **shared** (`rrf_fusion.py`) | ✗ | ✗ | ✗ | ✗ | —（纯 Python 标准库） |

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_sparse_hybrid_search.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_sparse_hybrid_search.py`
- [ ] 所有场景覆盖（AC-1 至 AC-5 + 领域零依赖验证）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 不使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- `BM25Builder.build_sparse_vector()` 是同步方法，在 BDD 同步步骤函数中直接调用
- `SparseSearchService.search()` 和 `HybridSearchService.search()` 是 async 方法，通过 `event_loop.run_until_complete()` 调用

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

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
| **TDD 契约测试** | 端口注册 | sparse_search_service, hybrid_search_service 注册验证 | `tests/contracts/test_port_contract_sparse_hybrid_search.py` | Task 0 + Task 4 |
| **TDD 单元测试** | encode_sparse 质量 | 中文文本编码、indices/values 一致性、权重正值 | `tests/unit/.../test_encode_sparse_quality.py`（新增）/ `tests/unit/.../test_bge3_embedding_service.py`（已有） | Task 1 |
| **TDD 单元测试** | SparseSearchService | text→sparse→search_sparse 编排、tenant_id 注入 | `tests/unit/application/test_sparse_search_service.py` | Task 2 |
| **TDD 单元测试** | RRF 融合算法 | 双路融合、去重、k 参数、空结果 | `tests/unit/shared/test_rrf_fusion.py` | Task 3 |
| **TDD 单元测试** | HybridSearchService | Dense+Sparse 并行调用 + RRF 融合编排 | `tests/unit/application/test_hybrid_search_service.py` | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `tests/acceptance/test_acceptance_sparse_hybrid_search.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `tests/acceptance/test_acceptance_sparse_hybrid_search.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单最终确认 | `tests/acceptance/test_acceptance_sparse_hybrid_search.feature` | Task 7 |
| **集成测试** | BM25 + Qdrant 端到端 | 真实 Qdrant sparse search | `tests/integration/test_integration_sparse_hybrid_search.py` | Task 5 |
| **SDD 架构验证** | 领域零依赖 | domain/ 无 qdrant_client 等外部依赖 | 包含在验收测试中 | Task 7 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）— **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **资源唯一性** | 测试 Collection 使用 UUID 后缀：`test_{uuid}_sparse_search` / `test_{uuid}_hybrid_search` | ID 冲突或状态污染 |
| **外部服务隔离** | Qdrant 测试前清理旧 Collection，测试后删除新 Collection | 真实数据被污染 |
| **并行隔离** | 并行测试使用 `TestTenant.qdrant_collection_prefix` 隔离 | 资源冲突导致并行失败 |
| **BDD async 配合** | BDD 步骤函数使用 `event_loop.run_until_complete()`，不用 `@pytest.mark.asyncio` | 直接用 @pytest.mark.asyncio 会导致 BDD context 数据丢失 |
| **服务加载隔离** | 服务实例通过 fixture 控制初始化，SINGLETON 懒加载 | 测试间状态泄漏 |
| **清理粒度** | 每个测试只清理自己创建的 Collection | 误删其他测试资源 |

**验证要求：**
- [ ] 并行测试 `poetry run pytest tests/ -n 8` 通过
- [ ] 连续5次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | BM25 稀疏向量构建 | Task 1 | 验证 EmbeddingServicePort.encode_sparse() | `test_bge3_embedding_service.py`（已有） |
| AC-2 | BM25 稀疏检索 | Task 2 | SparseSearchService | `test_sparse_search_service.py` |
| AC-2 | 端到端稀疏检索 | Task 5 | 集成测试 | `test_integration_sparse_hybrid_search.py` |
| AC-3 | Dense+Sparse 并行召回 | Task 3 | HybridSearchService | `test_hybrid_search_service.py` |
| AC-3 | 并行召回集成验证 | Task 5 | 集成测试 | `test_integration_sparse_hybrid_search.py` |
| AC-4 | RRF 双路融合 | Task 3 | RRF 融合算法 + HybridSearchService | `test_rrf_fusion.py` + `test_hybrid_search_service.py` |
| AC-5 | 检索延迟 P95<800ms | Task 5 | 性能基准测试 | `test_integration_sparse_hybrid_search.py` |
| 全部 | BDD 验收 | Task 0 | Gherkin 场景 | `test_acceptance_sparse_hybrid_search.*` |
| 全部 | 收尾验收 | Task 6 | 完成清单确认 | `test_acceptance_sparse_hybrid_search.*` |

**Task 间执行依赖：**
```
Task 0（SDD 规范）→ Task 1（encode_sparse 验证）→ Task 2（SparseSearchService）
                                                      ↘ Task 3（RRF + HybridSearchService）→ Task 4（注册装配）→ Task 5（集成测试）→ Task 6（收尾）
```
- Task 0 必须最先完成（定义所有 TypedDict 和 API 签名）
- Task 1 验证 EmbeddingServicePort.encode_sparse() 质量（Story 3-1a 重构已完成，本 Task 仅验证）
- Task 2 和 Task 3 可并行（Task 3 单元测试 mock SparseSearchService）
- Task 4 依赖 Task 2+3 全部完成（所有实现类已创建）
- Task 5 依赖 Task 4 完成（端口注册就绪）
- Task 6 依赖 Task 5 完成

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-5

> **目的：** 在进入代码实现前，明确数据模型、端口契约、API 签名、Gherkin 验收标准与六边形架构边界。

> **架构决策（2026-06-02）：** Story 3-1a 重构完成，`EmbeddingServicePort` 已含 `encode_sparse()`。
> 本 Story **不再需要 BM25BuilderPort** — SparseSearchService 直接注入 `EmbeddingServicePort` 调用 `encode_sparse()`。

- [ ] Subtask 0.1: 定义 `SparseSearchResult` TypedDict（id, score, payload）— 与 DenseSearchResult 结构对称
- [ ] Subtask 0.2: 定义 `HybridSearchResult` TypedDict（id, score, payload, source）
- [ ] Subtask 0.3: 定义 `SparseSearchService` API 签名（`search(collection, query_text, limit, tenant_id, filter_payload)`）
  - 构造函数注入 `EmbeddingServicePort`（调用 `encode_sparse()`）+ `L3VectorPort`（调用 `search_sparse()`）
- [ ] Subtask 0.4: 定义 `HybridSearchService` API 签名（`search(collection, query_text, limit, rrf_k, tenant_id, filter_payload)`）
- [ ] Subtask 0.5: 定义 RRF 融合纯函数签名（`rrf_fusion(result_lists, k=60) -> list[dict]`）
- [ ] Subtask 0.6: 编写端口契约测试 `tests/contracts/test_port_contract_sparse_hybrid_search.py`
  > **契约测试模式参考**：项目无 PortContractTest 基类，使用独立三方法模式。
  > 参考 `tests/contracts/test_port_contract_embedding_service.py`（Story 3-1a）。
- [ ] Subtask 0.7: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_sparse_hybrid_search.feature`
- [ ] Subtask 0.8: 编写 BDD 步骤实现骨架 `tests/acceptance/test_acceptance_sparse_hybrid_search.py`
- [ ] Subtask 0.9: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: encode_sparse 质量验证（已有能力确认）

**关联 AC:** AC-1

> **说明：** `EmbeddingServicePort.encode_sparse()` 已在 Story 3-1a 重构中实现并测试（22 个单元测试覆盖）。
> 本 Task 验证 Sparse 嵌入质量满足 Story 3-1b 需求。`BM25Builder`（`src/infrastructure/storage/qdrant/bm25_builder.py`）降级为 fallback。
> 本 Task 为已有代码补充完整单元测试（TDD 红→绿→重构，红阶段先确认测试失败是通过而非因代码存在而通过），
> 并为后续端口注册做准备。

#### TDD 循环 A：encode_sparse 质量验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/embedding/test_encode_sparse_quality.py` |
| 🟢 绿 | 确认已有 BGE3EmbeddingService.encode_sparse() 通过测试 |
| 🔄 重构 | 如有必要优化已有代码，运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 encode_sparse 质量测试（中文文本、indices/values 一致性、排序验证、空文本边界）
  - 测试 `build_sparse_vector()` 返回正确 SparseVector 结构
  - 测试 TF-IDF 权重计算（验证权重 > 0 且非 NaN）
  - 测试英文停用词过滤（"the"/"is"/"and" 等不在 indices 对应词中）
  - 测试空文本返回空稀疏向量
  - 测试纯空格文本返回空稀疏向量
  - 测试词汇哈希稳定性（同一 term 多次调用返回相同 hash index）
  - 测试 indices 和 values 长度一致性
  - 测试中英文混合文本（如 "AI 人工智能 strategy 战略"，验证英文 token 经停用词过滤、中文 token 作为整体保留且权重 > 0）
- [ ] Subtask 1.2: 🟢 绿 — 确认已有 BGE3EmbeddingService.encode_sparse() 通过质量测试
- [ ] Subtask 1.3: 🔄 重构 — 如有必要优化已有代码，运行 `ruff check` + `mypy`

**完成标准/Definition of Done:**
- [ ] encode_sparse 质量测试全部通过
- [ ] 覆盖率≥75%（基础设施层）

---

### Task 2: SparseSearchService 实现

**关联 AC:** AC-2

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：SparseSearchService

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_sparse_search_service.py` |
| 🟢 绿 | 创建 `src/application/services/sparse_search_service.py` |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 2.1: 🔴 红 — 编写 SparseSearchService 失败测试
  - mock EmbeddingServicePort（domain Protocol）+ L3VectorPort
  - 验证 `search()` 调用 `embedding_service.encode_sparse(query_text)` 一次
  - 验证 `search()` 调用 `vector_storage.search_sparse()` 一次并传入正确的 sparse vector dict
  - 验证 `tenant_id` 自动注入到 `filter_payload`
  - 验证现有 `filter_payload` 保留（与 tenant_id 合并）
  - 验证 `limit` 传递正确
  - 验证空查询文本抛出 ValueError("查询文本不能为空")（与 DenseSemanticSearchService 行为一致）
  - 验证 search_sparse 异常时返回空列表（异常隔离）
- [ ] Subtask 2.2: 🟢 绿 — 创建 `src/application/services/sparse_search_service.py`
  ```python
  from src.domain.ports.embedding_service import EmbeddingServicePort
  from src.domain.ports.l3_vector import L3VectorPort

  class SparseSearchResult(TypedDict):
      id: str | int
      score: float
      payload: dict[str, Any]

  class SparseSearchService:
      """稀疏检索应用服务

      编排流程：text → EmbeddingServicePort.encode_sparse → L3VectorPort.search_sparse
      encode_sparse() 使用 BGE-M3 原生多语言 tokenizer，中文分词质量优于自建 BM25。
      """
      def __init__(self, embedding_service: EmbeddingServicePort, vector_storage: L3VectorPort): ...

      async def search(
          self, collection: str, query_text: str, limit: int = 10,
          tenant_id: str | None = None, filter_payload: dict | None = None,
      ) -> list[SparseSearchResult]: ...
  ```
  - 使用 `asyncio.to_thread()` 包装同步 `encode_sparse()` 调用
  - `encode_sparse()` 直接返回 `{"indices": [...], "values": [...]}` dict，无需额外转换
  - tenant_id 注入逻辑与 DenseSemanticSearchService 保持一致
  - 空查询抛出 ValueError("查询文本不能为空")（与 DenseSemanticSearchService 行为一致）
- [ ] Subtask 2.3: 🔄 重构 — 优化代码，运行 `ruff check` + `mypy`

**完成标准/Definition of Done:**
- [ ] SparseSearchService 实现完成
- [ ] 单元测试全部通过
- [ ] 覆盖率≥85%（应用层）

---

### Task 3: RRF 融合算法 + HybridSearchService 实现

**关联 AC:** AC-3, AC-4

> ⚠️ **本 Task 包含两个 TDD 循环：RRF 融合算法（纯函数）和 HybridSearchService（编排服务）。**

#### TDD 循环 A：RRF 融合算法

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/shared/test_rrf_fusion.py` |
| 🟢 绿 | 实现 RRF 融合纯函数 |
| 🔄 重构 | 优化算法，运行 `ruff` + `mypy` |

- [ ] Subtask 3.1: 🔴 红 — 编写 RRF 融合算法失败测试
  - 测试双路结果融合（Dense 5 个 + Sparse 5 个，有重叠文档）
  - 测试去重逻辑（同一文档 ID 在 Dense 和 Sparse 中均出现）
  - 测试仅单路出现文档的正确融合
  - 测试 k 参数可配置（默认 60，验证不同 k 值的排序差异）
  - 测试空输入（两路均为空返回空列表）
  - 测试单路为空（仅 Dense 有结果或仅 Sparse 有结果）
  - 测试 limit 参数截断
  - 测试 rank 从 0 开始的一致性（项目决策：使用 Python 0-indexed 惯例，`rank_i(d)` 为文档 d 在第 i 路结果列表中的索引位置，即第一个文档 rank=0）
- [ ] Subtask 3.2: 🟢 绿 — 实现 RRF 融合纯函数
  - 位置：`src/shared/rrf_fusion.py`（纯函数，无外部依赖）
    > **设计决策：** RRF 作为纯函数放在 `src/shared/` 而非 `src/domain/`。符合 RRF 作为通用算法（非领域概念）的定位。
    > 参考项目惯例：`src/shared/` 用于跨层共享的工具函数。
  ```python
  def rrf_fusion(
      result_lists: list[list[dict]],
      k: int = 60,
      limit: int = 10,
  ) -> list[dict]:
      """Reciprocal Rank Fusion 融合排序

      Args:
          result_lists: 各路检索结果列表，每个元素为 [{id, score, payload}, ...]
          k: RRF 平滑参数（默认 60，按 Qdrant/Elasticsearch 行业惯例）
          limit: 返回结果数量限制

      Returns:
          融合排序后的结果列表，每个元素为 {"id": str|int, "score": float, "payload": dict}
      """
  ```
  - RRF 公式：`score(d) = Σ 1/(k + rank_i(d))`
  - `rank_i(d)` 为文档 d 在第 i 路结果中的排名（从 0 开始）
  - 文档未在某路出现时，该路贡献为 0
- [ ] Subtask 3.3: 🔄 重构 — 优化算法，运行 `ruff check` + `mypy`

#### TDD 循环 B：HybridSearchService

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_hybrid_search_service.py` |
| 🟢 绿 | 创建 `src/application/services/hybrid_search_service.py` |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 3.4: 🔴 红 — 编写 HybridSearchService 失败测试
  - mock DenseSemanticSearchService + SparseSearchService
  - 验证 `search()` 同时调用 Dense 和 Sparse 检索（asyncio.gather）
  - 验证 RRF 融合被调用（传入两路结果）
  - 验证 `source` 字段标记正确（"dense"/"sparse"/"both"）
  - 验证 `rrf_k` 参数传递到 RRF 融合
  - 验证 Dense 失败时 Sparse 仍正常返回（异常隔离）
  - 验证 Sparse 失败时 Dense 仍正常返回（异常隔离）
  - 验证两路均为空返回空列表
- [ ] Subtask 3.5: 🟢 绿 — 创建 `src/application/services/hybrid_search_service.py`
  ```python
  from src.application.services.dense_search_service import DenseSemanticSearchService
  from src.application.services.sparse_search_service import SparseSearchService
  from src.shared.rrf_fusion import rrf_fusion

  class HybridSearchResult(TypedDict):
      id: str | int
      score: float
      payload: dict[str, Any]
      source: str  # "dense" | "sparse" | "both"

  class HybridSearchService:
      """混合检索应用服务

      编排流程：
      1. 并行执行 Dense（Story 3-1a）和 Sparse（本 Story Task 2）检索
      2. RRF 融合双路结果
      3. 返回按融合分数排序的结果
      """
      def __init__(
          self,
          dense_search: DenseSemanticSearchService,
          sparse_search: SparseSearchService,
          rrf_k: int = 60,
      ): ...

      async def search(
          self, collection: str, query_text: str, limit: int = 10,
          tenant_id: str | None = None, filter_payload: dict | None = None,
      ) -> list[HybridSearchResult]: ...
  ```
  - 空查询校验：`if not query_text or not query_text.strip(): raise ValueError("查询文本不能为空")`（与 Dense/Sparse 一致）
  - 使用 `asyncio.gather(..., return_exceptions=True)` 并行调用两路检索
  - 过滤异常结果，保留正常返回的检索结果
  - 调用 `rrf_fusion()` 进行融合
  - `source` 字段：根据文档在 Dense/Sparse 中的出现情况标记
- [ ] Subtask 3.6: 🔄 重构 — 优化代码，运行 `ruff check` + `mypy`

**完成标准/Definition of Done:**
- [ ] RRF 融合算法实现完成
- [ ] HybridSearchService 实现完成
- [ ] 所有单元测试通过
- [ ] 覆盖率≥85%（应用层）

---

### Task 4: Composition Root 注册 + 端口契约测试

**关联 AC:** AC-1, AC-2, AC-3

#### TDD 循环 A：Composition Root 注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写端口注册契约测试（验证 sparse_search_service, hybrid_search_service 注册） |
| 🟢 绿 | 修改 `src/composition_root.py` 注册三个新端口 |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [ ] Subtask 4.1: 🔴 红 — 在 `tests/contracts/test_port_contract_sparse_hybrid_search.py` 中添加注册验证测试
  - 验证 `sparse_search_service` 在 registry 注册（生命周期 SCOPED）
  - 验证 `hybrid_search_service` 在 registry 注册（生命周期 SCOPED）
  - 验证各端口 PortSpec 元数据（version, owner, module）
- [ ] Subtask 4.2: 🟢 绿 — 修改 `src/composition_root.py`，在 "Search Ports (Epic 3)" 区块添加：
  ```python
  # sparse_search_service — SCOPED（编排 EmbeddingServicePort.encode_sparse + L3VectorPort.search_sparse）
  from src.application.services.sparse_search_service import SparseSearchService
  register_port(
      name="sparse_search_service",
      version="v1.0.0",
      interface=SparseSearchService,
      impl=lambda resolver: SparseSearchService(
          embedding_service=resolver.resolve("embedding_service"),
          vector_storage=resolver.resolve("l3_vector"),
      ),
      module="src.application.services.sparse_search_service",
      lifetime=Lifetime.SCOPED,
      owner="search-team",
      tags=("search", "sparse"),
  )

  # hybrid_search_service — SCOPED（编排 Dense + Sparse + RRF 融合）
  from src.application.services.hybrid_search_service import HybridSearchService
  register_port(
      name="hybrid_search_service",
      version="v1.0.0",
      interface=HybridSearchService,
      impl=lambda resolver: HybridSearchService(
          dense_search=resolver.resolve("dense_search_service"),
          sparse_search=resolver.resolve("sparse_search_service"),
          rrf_k=int(os.getenv("RRF_K", "60")),
      ),
      module="src.application.services.hybrid_search_service",
      lifetime=Lifetime.SCOPED,
      owner="search-team",
      tags=("search", "hybrid", "rrf"),
  )
  ```
  - `rrf_k` 从环境变量读取（默认 60），便于运维调整
- [ ] Subtask 4.3: 🔄 重构 — 运行 `ruff check` + `mypy`

**完成标准/Definition of Done:**
- [ ] composition_root.py 三个新端口注册完成
- [ ] 端口契约测试全部通过
- [ ] ruff + mypy 通过

---

### Task 5: 集成测试（真实 Qdrant + 真实 BM25Builder + 真实 BGE-M3）

**关联 AC:** AC-2, AC-3, AC-4, AC-5

> **性质说明：** 端到端集成测试，验证 BM25 稀疏检索 + Hybrid 混合检索在真实环境下的协作。
> **依赖：** Task 4 完成（所有端口注册就绪）。

#### TDD 循环 A：集成测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写集成测试（预期因 Collection 不存在或数据未插入而失败） |
| 🟢 绿 | 实现测试逻辑，运行确认通过 |
| 🔄 重构 | 添加性能基准，优化测试结构 |

- [ ] Subtask 5.1: 🔴 红 — 创建 `tests/integration/test_integration_sparse_hybrid_search.py`
  - 使用 `TestTenant` 隔离（参考 `test_integration_embedding_qdrant_dense_search.py` 模式）
  - Fixture：创建 Collection → 插入测试数据（Dense + Sparse 向量）→ 测试后 try/finally 删除
  - Collection 需同时支持 Dense 和 Sparse 向量：
    ```python
    from qdrant_client.models import SparseVectorParams
    await collection_manager.create_collection(
        name=collection,
        vector_size=1024,
        distance="Cosine",
        sparse_vectors_config={"sparse": SparseVectorParams()},
    )
    ```
- [ ] Subtask 5.2: 🟢 绿 — 实现 BM25 稀疏检索端到端测试
  - 构建稀疏向量 → upsert 到 Qdrant（含 sparse_vectors）→ 查询 → 验证排序
  - ⚠️ **upsert 时需同时写入 Dense 和 Sparse 向量**（Qdrant NamedVectors），vector 字段格式：
    ```python
    # Dense + Sparse 双向量 upsert 格式
    vector = {
        "": dense_vector_list,  # 默认 Dense 向量（空字符串键名）
        "sparse": models.SparseVector(indices=sv.indices, values=sv.values),
    }
    ```
  - 插入不同 business_domain 的数据 → 过滤 → 验证结果
  - 设计测试数据使部分文档同时在 Dense 和 Sparse 检索中出现（验证 RRF 重叠加权）
- [ ] Subtask 5.3: 🟢 绿 — 实现 Hybrid 混合检索端到端测试
  - 插入 10 个文档（Dense + Sparse 向量均写入）
  - 执行 Hybrid 检索 → 验证返回结果包含 Dense 和 Sparse 来源
  - 验证 RRF 融合排序正确（重叠文档排名高于单路文档）
- [ ] Subtask 5.4: 🟢 绿 — 实现异常隔离测试
  - 验证 Dense/Sparse 单路失败不影响另一路
  - 验证空查询文本抛出 ValueError（与 DenseSemanticSearchService 一致）
- [ ] Subtask 5.5: 🟢 绿 — 实现性能基准测试
  - 预热 5 次查询 → 50 次查询（查询文本 ≤ 512 字符）→ 统计 P95 延迟
  - GPU: P95 < 800ms / CPU: P95 < 1500ms（根据 EmbeddingConfig.device 自动选择阈值）
  - BM25 单路检索 P95 < 100ms
  - RRF 融合 P95 < 50ms
  - 标记 `@pytest.mark.slow`（CI 可选跳过）
- [ ] Subtask 5.6: 🔄 重构 — 运行完整集成测试并确认通过，优化测试结构

**完成标准/Definition of Done:**
- [ ] 集成测试全部通过
- [ ] BM25 稀疏检索端到端正确
- [ ] Hybrid 混合检索端到端正确
- [ ] 异常隔离正确
- [ ] P95 延迟满足目标

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** 全部 AC

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [ ] Subtask 6.1: 验证领域层零外部依赖
  - `src/domain/` 不导入 qdrant_client, sentence_transformers, BM25Builder
  - `src/shared/rrf_fusion.py` 不导入任何基础设施层模块
- [ ] Subtask 6.2: 验证六边形架构依赖方向
  - application → domain（允许）
  - application → shared（允许，但 shared 必须零外部依赖）
  - infrastructure → domain（允许）
  - application → infrastructure（禁止，HybridSearchService 不直接导入 BM25Builder）
  - domain → application/infrastructure/interfaces/shared（禁止）
  - shared → domain/application/infrastructure（禁止，仅 Python 标准库）
- [ ] Subtask 6.3: 验证端口注册完整性
  - sparse_search_service, hybrid_search_service 均在 registry 中
  - 实现模块路径正确可导入
- [ ] Subtask 6.4: 运行完整测试套件并生成报告
  - `poetry run pytest tests/ -x` 确认全量测试通过
  - `poetry run ruff check src/` 通过
  - `poetry run mypy src/` 通过

**完成标准/Definition of Done:**
- [ ] 所有架构/约束测试通过
- [ ] 任何违规都会导致测试失败

---

### Task 7: 开发结束验收测试

**关联 AC:** 全部 AC

> **性质说明：** 对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_sparse_hybrid_search.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_sparse_hybrid_search.py` 的 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达、保持步骤函数可维护性 |

- [ ] Subtask 7.1: 场景 1 — 验证 `src` 完成清单的逐项确认
  - `src/application/services/sparse_search_service.py` 存在且包含 `SparseSearchService`
  - `src/application/services/hybrid_search_service.py` 存在且包含 `HybridSearchService`
  - `src/shared/rrf_fusion.py` 存在且包含 `rrf_fusion` 函数
  - `src/composition_root.py` 包含 `sparse_search_service`, `hybrid_search_service` 注册
- [ ] Subtask 7.2: 场景 2 — 验证 `tests/` 完成清单的逐项确认
  - 契约测试、单元测试（BM25Builder/SparseSearchService/RRF/HybridSearchService）、集成测试、验收测试文件均存在
- [ ] Subtask 7.3: 场景 3 — 验证领域层零外部依赖
  - `src/domain/` 不导入 qdrant_client / BM25Builder
  - `src/shared/rrf_fusion.py` 仅使用 Python 标准库
- [ ] Subtask 7.4: 运行开发结束验收测试并确认通过
- [ ] Subtask 7.5: 运行 `poetry run pytest`、`poetry run ruff check src/`、`poetry run mypy src/` 进行收尾校验

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** `docs/architecture/architecture.md` + `docs/architecture/sisys-core-domain-design.md`

- **架构模式:** 六边形架构（Ports & Adapters），CQRS（查询端）
- **设计约束:** 领域层零外部依赖，依赖方向 domain←application←infrastructure
- **接口治理:** 统一端口注册、PortSpec 元数据、Registry/Resolver/ContractGate、Composition Root 装配
- **技术栈:** Python 3.11+, qdrant-client 1.7.1, sentence-transformers ^2.2.2, FlagEmbedding ^1.2.8, torch 2.7.1

### 关键架构决策

**来源:** `docs/architecture/architecture.md` — ADR-004（向量数据库选型 Qdrant）

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **Qdrant（选中）** | 高性能 Dense/Sparse 混合检索，原生余弦相似度，gRPC 支持，原生 SparseVector API | 需独立部署 | ✅ 9/10 |
| Milvus | 功能全面 | Java 依赖重，部署复杂 | 7/10 |
| Weaviate | GraphQL API | 扩展性一般 | 6/10 |

### RRF 算法设计决策

**来源:** `docs/architecture/sisys-core-domain-design.md` §17.1.5

| 方案 | 优点 | 缺点 | 决策 |
|------|------|------|------|
| **RRF k=60（选中）** | Qdrant/Elasticsearch 行业默认，学术论文推荐 | - | ✅ 采用 |
| 线性加权融合 | 权重可调 | 分数尺度不一致问题严重（Dense cosine vs BM25 分数分布差异大） | 不采用 |
| 学习排序（LTR） | 理论最优 | 需要标注数据，MVP 不可行 | V2 考虑 |

**RRF 公式：** `score(d) = Σ 1/(k + rank_i(d))`，其中 k=60，rank 从 0 开始（Python 0-indexed 惯例）

**rank 起始值说明：** 学术论文 Cormack et al. (2009) 使用 1-based rank，本项目采用 0-based（与 Python enumerate 惯例一致）。两种方式的排序等价，仅绝对分值有微小差异（0-based 首位 1/60 vs 1-based 首位 1/61）。

**设计原因：**
- RRF 是 rank-based 融合，不依赖原始分数的绝对值，天然处理 Dense（cosine 0-1）和 Sparse（BM25 0-N）分数尺度差异
- k=60 是 Qdrant 推荐值（Qdrant 官方文档 + Elasticsearch 8.x 默认），已在工业界大规模验证
- 与后续 Story 3-4（三路 + ColBERT 重排序）保持一致

### 已有组件复用说明

| 组件 | 路径 | 复用方式 |
|------|------|---------|
| `L3VectorPort.search_sparse()` | `src/domain/ports/l3_vector.py` | SparseSearchService 直接调用（接受 `sparse_vector: dict`） |
| `QdrantAdapter.search_sparse()` | `src/infrastructure/storage/qdrant/qdrant_adapter.py` | l3_vector 端口实现（已有），内部 dict→SparseVector 转换 |
| `QdrantVectorStorage.search_sparse()` | `src/infrastructure/storage/qdrant/vector_storage.py` | 已有稀疏检索实现（NamedSparseVector，异常时返回空列表） |
| `BM25Builder` | `src/infrastructure/storage/qdrant/bm25_builder.py` | SparseSearchService 通过 BM25BuilderPort（domain Protocol）注入 |
| `SparseVector` dataclass | `src/infrastructure/storage/qdrant/models.py` | BM25Builder 输出类型（application 层不直接引用，转为 dict 传递） |
| `EmbeddingServicePort` | `src/domain/ports/embedding_service.py` | HybridSearchService 通过 dense_search_service 间接使用 |
| `DenseSemanticSearchService` | `src/application/services/dense_search_service.py` | HybridSearchService 注入 |
| `DenseSearchResult` TypedDict | `src/application/services/dense_search_service.py` | 结果结构参考 |
| `QdrantCollectionManager` | `src/infrastructure/storage/qdrant/collection_manager.py` | 测试中创建支持 sparse_vectors_config 的 Collection |

### Collection 创建注意事项（sparse_vectors_config）

**关键约束：** Qdrant Collection 必须创建时指定 `sparse_vectors_config`，否则无法存储稀疏向量。

已有代码支持但不完整：
- `QdrantCollectionManager.create_collection()` 已支持 `**kwargs` 中的 `sparse_vectors_config`（`collection_manager.py:73`）
- 但 composition_root 中 `l3_vector` 端口注册未传递此配置
- **本 Story 的测试中需要显式传入 sparse_vectors_config**：
  ```python
  from qdrant_client.models import SparseVectorParams
  await collection_manager.create_collection(
      name=collection,
      vector_size=1024,
      distance="Cosine",
      sparse_vectors_config={"sparse": SparseVectorParams()},
  )
  ```
- 生产环境 Collection 创建需在后续 Story 的索引管道中处理

### BM25Builder 已知限制

| 限制 | 影响 | 改进计划 |
|------|------|---------|
| TF-IDF 变体（非真正 BM25） | 无 k1/b 参数调优 | 后续 Story 替换为 scikit-learn TfidfVectorizer 或 Qdrant 原生 BM25 |
| 简单空白分词 | 中文分词未处理 | Story 3-3（领域词典管理）将补充中文分词 |
| 单文档 IDF 计算 | 跨文档 IDF 不准确 | 后续 Story 引入全局词汇统计 |
| 仅英文停用词 | 中文停用词缺失 | 本 Story 可补充基础中文停用词（"的"/"了"/"是"/"在"/"和"） |
| hash(term) % 1000000 | 词汇冲突概率 ~0（100 万桶） | 后续 Story 可引入词汇表映射 |

### 项目结构说明 Project Structure

```
src/
├── domain/
│   └── ports/
│       └── bm25_builder.py           # [NEW] BM25BuilderPort Protocol
├── shared/
│   └── rrf_fusion.py                # [NEW] RRF 融合纯函数
├── application/
│   └── services/
│       ├── dense_search_service.py   # [已有] Dense 检索（Story 3-1a）
│       ├── sparse_search_service.py  # [NEW] Sparse 检索（注入 EmbeddingServicePort）
│       └── hybrid_search_service.py  # [NEW] 混合检索 + RRF 融合
├── domain/
│   └── ports/
│       ├── embedding_service.py      # [已有] EmbeddingServicePort（含 encode_sparse()）
│       └── l3_vector.py             # [已有] L3VectorPort（含 search_sparse()）
├── infrastructure/
│   └── storage/
│       └── qdrant/
│           ├── bm25_builder.py        # [已有] BM25 稀疏向量构建（fallback，非正常路径）
│           ├── vector_storage.py      # [已有] search_sparse() 实现
│           ├── qdrant_adapter.py      # [已有] search_sparse() 适配
│           ├── models.py             # [已有] SparseVector, VectorPoint
│           └── collection_manager.py  # [已有] sparse_vectors_config 支持
└── composition_root.py               # [MODIFY] 新增 2 个端口注册

tests/
├── unit/
│   ├── application/
│   │   ├── test_sparse_search_service.py   # [NEW] SparseSearchService 单元测试（mock EmbeddingServicePort）
│   │   └── test_hybrid_search_service.py   # [NEW] HybridSearchService 单元测试
│   └── shared/
│       └── test_rrf_fusion.py       # [NEW] RRF 融合算法单元测试
├── integration/
│   └── test_integration_sparse_hybrid_search.py  # [NEW] 集成测试
├── contracts/
│   └── test_port_contract_sparse_hybrid_search.py  # [NEW] 端口契约测试
└── acceptance/
    ├── test_acceptance_sparse_hybrid_search.feature # [NEW] Gherkin 场景
    └── test_acceptance_sparse_hybrid_search.py      # [NEW] BDD 步骤实现
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** Story 3-1a-dense-semantic-search

**关键学习/Key Learnings:**

1. **DI 注册延迟加载陷阱** — impl 字符串拼写错误不立即报错，需契约测试覆盖 impl 字符串验证
2. **同步方法 + asyncio.to_thread 模式** — BM25Builder.build_sparse_vector() 是同步方法，在 async 上下文中使用 asyncio.to_thread() 包装
3. **tenant_id 过滤预留** — Qdrant upsert payload 中可能不含 tenant_id 字段，过滤逻辑作为接口预留
4. **服务类自身作为 interface** — 应用服务注册时使用服务类自身作为 interface（参考 dense_search_service），而非抽象 Protocol
5. **SCOPED 生命周期** — 轻量编排服务使用 SCOPED（非 SINGLETON）
6. **性能基准排除首次加载** — 预热 5 次查询 → 50 次查询 → 统计 P95
7. **TestTenant UUID 后缀隔离** — `f"test_{uuid.uuid4().hex[:8]}"`
8. **BDD async 配合** — 步骤函数使用 event_loop.run_until_complete()，不用 @pytest.mark.asyncio

**应用到本故事/Applied to This Story:**
- [ ] sparse_search_service/hybrid_search_service impl 字符串纳入契约测试
- [ ] encode_sparse() 使用 asyncio.to_thread() 包装（Task 2）
- [ ] tenant_id 过滤逻辑与 DenseSemanticSearchService 保持一致（Task 2, 3）
- [ ] 应用服务使用服务类自身作为 interface（Task 4）
- [ ] 新服务生命周期使用 SCOPED（Task 4）
- [ ] 集成测试预热 5 次排除首次加载（Task 5）
- [ ] 测试 Collection 使用 UUID 后缀隔离（Task 5）
- [ ] BDD 步骤使用 event_loop.run_until_complete()（Task 0, 7）

### 前一个故事学习经验 Lessons Learned from Previous Story (Story 1-6 Qdrant)

**关键学习/Key Learnings:**
1. Qdrant v1.7.x ID 要求 — 无符号整数，需 `_normalize_point_id()` 处理字符串 ID
2. query_points API 已废弃 — 改用 `search` 方法
3. 配置模式复用 — `XxxConfig + from_env()` 模式
4. 懒初始化连接池 — 首次调用时创建客户端

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Opus 4.8 |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-06-02 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` |
| **核心领域设计** | `docs/architecture/sisys-core-domain-design.md` |
| **存储子系统设计** | `docs/architecture/sisys-storage-subsystem-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/3-1a-dense-semantic-search.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] 故事需求从 `epics_v1.0.md` 提取
- [ ] 架构约束从 `architecture.md` + `sisys-core-domain-design.md` 提取
- [ ] 已有代码分析完成（BM25Builder, L3VectorPort.search_sparse, QdrantAdapter/VectorStorage, DenseSemanticSearchService）
- [ ] 前一个故事学习经验整合（Story 3-1a + Story 1-6）
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-1b-bm25-sparse-search-rrf-fusion.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/shared/rrf_fusion.py` — RRF 融合纯函数
- `src/application/services/sparse_search_service.py` — 稀疏检索服务（注入 EmbeddingServicePort）
- `src/application/services/hybrid_search_service.py` — 混合检索 + RRF 融合服务
- `tests/unit/infrastructure/external_services/embedding/test_encode_sparse_quality.py` — encode_sparse 质量测试
- `tests/unit/application/test_sparse_search_service.py` — SparseSearchService 单元测试
- `tests/unit/shared/test_rrf_fusion.py` — RRF 融合算法单元测试
- `tests/unit/application/test_hybrid_search_service.py` — HybridSearchService 单元测试
- `tests/integration/test_integration_sparse_hybrid_search.py` — 集成测试
- `tests/contracts/test_port_contract_sparse_hybrid_search.py` — 端口契约测试
- `tests/acceptance/test_acceptance_sparse_hybrid_search.feature` — Gherkin 场景
- `tests/acceptance/test_acceptance_sparse_hybrid_search.py` — BDD 步骤实现

**待修改的文件/To Be Modified (Dev Story 实施):**
- `src/composition_root.py` — 新增 sparse_search_service, hybrid_search_service 注册

**已有文件（复用，不修改）：**
- `src/domain/ports/embedding_service.py` — EmbeddingServicePort（含 encode_sparse()，Story 3-1a 重构）
- `src/domain/ports/l3_vector.py` — L3VectorPort.search_sparse() 已有
- `src/infrastructure/external_services/embedding/bge3_embedding_service.py` — BGE3EmbeddingService（FlagEmbedding 实现）
- `src/infrastructure/storage/qdrant/qdrant_adapter.py` — search_sparse 适配已有
- `src/infrastructure/storage/qdrant/vector_storage.py` — NamedSparseVector 检索已有
- `src/infrastructure/storage/qdrant/models.py` — SparseVector 已有
- `src/application/services/dense_search_service.py` — DenseSemanticSearchService 已有
- `src/infrastructure/storage/qdrant/bm25_builder.py` — BM25Builder 保留为 fallback（非正常检索路径）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.1b |
| **Story Key** | 3-1b-bm25-sparse-search-rrf-fusion |
| **File** | `_bmad-output/implementation-artifacts/stories/3-1b-bm25-sparse-search-rrf-fusion.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | P0-1b（关键路径） |
| **覆盖 FR** | FR-SR-01（混合检索） |
| **前置依赖** | Story 3-1a（Dense 语义检索） |
| **后续依赖** | Story 3-4（RRF 融合排序 — 三路 + ColBERT） |

### 完成总结 Completion Summary

1. [ ] All tasks defined 所有任务定义完成（Task 0-7，8 个任务）
2. [ ] All acceptance criteria specified 所有验收标准已定义（AC-1 ~ AC-5）
3. [ ] Architecture constraints extracted 架构约束已提取
4. [ ] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Sprint status synced to `ready-for-dev`

### 下一步 Next Steps

- [ ] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.5.0
**创建日期/Created:** 2026-06-02
**最后更新/Last Updated:** 2026-06-02
**更新说明/Description:**
- v1.0.0: 创建故事文件，基于 6 Agent 并行全量调研
- v1.1.0: 第1轮审查 - 7项P0架构/一致性修正（BM25BuilderPort Protocol、IDF公式、空查询行为、RRF rank、依赖方向矩阵）
- v1.2.0: Story 3-1a 重构后同步 — 移除 BM25BuilderPort（改为复用 EmbeddingServicePort.encode_sparse()）；端口数从3减至2；SparseSearchService 注入 EmbeddingServicePort；BM25Builder 降级为 fallback
- v1.2.0: 第2轮审查 - 6项P0正确性修正（类名命名、停用词范围、Collection API、mock spec）
- v1.3.0: 第3轮审查 - 4项P0可行性修正（Task依赖图、代码模板导入、追溯矩阵）
- v1.4.0: 第4轮审查 - 4项P0细节修正（NamedVectors格式、空查询校验、rrf_fusion返回类型、shared约束）
- v1.5.0: 第5轮审查 - 最终一致性扫描修正（依赖方向矩阵P1、Status就绪）
