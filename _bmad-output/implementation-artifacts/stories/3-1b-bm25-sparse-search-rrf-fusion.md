# Story 3-1b: BM25 稀疏检索 + RRF 融合

**Status:** `done` (code-review complete, 7 patches fixed, 5 deferred, 2 dismissed)

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 分析师,
**I want** 系统执行 BM25 稀疏检索并与 Dense 检索融合（RRF 算法）,
**So that** 同时支持语义检索和关键词检索，综合提升相关性。

### 业务价值

Story 3-1b 是 Epic 3（智能检索与知识发现）关键路径的第二个故事（P0-1b）。
在 Story 3-1a（Dense 语义检索）已交付 bge-m3 嵌入生成 + Qdrant 余弦相似度检索的基础上，
本 Story 引入 BM25 稀疏检索通道和 RRF（Reciprocal Rank Fusion）两路融合，实现混合检索（Hybrid Search）。

**双通道召回策略：**
- **Dense 通道**（Story 3-1a 已交付）：bge-m3 1024 维语义向量 → Qdrant 余弦相似度 → 语义理解检索
- **Sparse 通道**（Story 3-1b 新增）：bge-m3 词法权重 / BM25 → Qdrant 稀疏向量 → 关键词精确匹配

两路结果经 RRF（k=60）融合排序，共同提升检索相关性（Dense 覆盖语义相似、Sparse 覆盖关键词精确匹配）。

**核心假设：** MVP 阶段 RRF 融合为两路（Dense + Sparse），预留三路扩展接口（Story 3-4 将加入 Graph 信号 + ColBERT-v2 重排序）。
稀疏向量使用 bge-m3 `encode(return_sparse=True)` 输出的词法权重 [Source: src/infrastructure/external_services/embedding/embedding_api_client.py]，
BM25Builder（TF-IDF）作为降级方案 [Source: src/infrastructure/storage/qdrant/bm25_builder.py]。

---

## ✅ Acceptance Criteria 验收标准

### AC-1: BM25 稀疏检索

**Given** Qdrant Collection 已配置稀疏向量索引（`sparse_vectors_config`）
**And** 文档已存储稀疏向量（bge-m3 词法权重或 BM25 TF-IDF）
**When** 用户输入查询文本执行 BM25 稀疏检索
**Then** 调用 `EmbeddingServicePort.embed_sparse([query_text])[0]` 生成查询稀疏向量（`SparseEmbedding`：`indices`/`values`，批量接口取首元素）
**And** 在 Qdrant 中通过 `NamedSparseVector` 执行稀疏检索
**And** 返回按 BM25 相似度排序的结果列表（`id`/`score`/`payload`）
**And** BM25 检索延迟 P95 < 100ms（不含嵌入 API 调用，Qdrant 纯检索时间）

**性能测试方法论（与 Story 3-1a 一致）：**
- 采样次数 ≥ 50 次，排除首次冷启动
- Task 7 集成测试中通过 `time.perf_counter()` 测量 Qdrant 检索延迟
- CPU 环境下目标不变（Qdrant 检索为内存操作，不依赖 GPU）

**验证标准/Validation Criteria:**
- [ ] 应用层 `Bm25SparseSearchService` 位于 `src/application/services/sparse_search_service.py`
- [ ] `search(collection, query_text, limit, tenant_id, filter_payload)` 方法严格镜像 `DenseSemanticSearchService` 签名和参数顺序 [Source: src/application/services/dense_search_service.py:51-58]
- [ ] 使用 `asyncio.to_thread()` 包装同步 `embed_sparse([query_text])` 调用（批量接口取首元素）
- [ ] 自动注入 `tenant_id` 过滤器（复用 `_build_filter()` 模式，与 Dense 检索安全要求一致）
- [ ] 空查询文本抛出 `ValidationError`（与 `DenseSemanticSearchService` 异常类型一致 [Source: src/application/services/dense_search_service.py:75]）
- [ ] 空集合名称抛出 `ValidationError`（与 `DenseSemanticSearchService` 一致）
- [ ] 无效 limit 抛出 `ValidationError`（与 `DenseSemanticSearchService` 一致）
- [ ] 无匹配结果返回空列表

### AC-2: RRF 融合算法

**Given** Dense 检索和 Sparse 检索各自返回排序结果列表
**When** 调用 RRF 融合算法
**Then** 对每个文档计算 RRF 分数：`score(doc) = Σ w_i / (k + rank_i(doc))`
**And** 默认参数 `k = 60`, `weights = None`（对称融合，`w_i = 1.0`）
**And** rank 从 **1** 开始计数（论文标准：top-1 = rank 1，非 rank 0）
**And** 结果按 RRF 分数降序排列
**And** 同文档在多个通道中出现时，取 RRF 分数之和（自动去重）
**And** RRF 融合延迟 P95 < 50ms（两路各 ≤ 50 结果）

**性能测试方法论：**
- RRF 融合为纯内存计算，Task 1 单元测试中通过 `time.perf_counter()` 测量
- 采样次数 ≥ 100 次（无 I/O，纯计算，快速采样）
- 两路各 ≤ 50 结果（MVP 典型负载）

**验证标准/Validation Criteria:**
- [ ] RRF 融合领域服务位于 `src/domain/services/rrf_fusion.py`（纯 Python，零外部依赖）
- [ ] 函数签名：`fuse(*result_lists: list[SearchResult], k: int = 60, weights: list[float] | None = None) -> list[SearchResult]`
  - `k=60`：平滑常数默认值，出自 Cormack et al. SIGIR 2009 论文 [Source: https://doi.org/10.1145/1571941.1572114]
  - `weights=None`：MVP 对称融合（等权），V1（Story 3-4）传入 `[w_dense, w_sparse, w_graph]` 实现加权 RRF
  - `*result_lists`：可变参数，MVP 两路、V1 三路
- [ ] rank 从 **1** 开始计数（`enumerate(results, start=1)`），match 论文公式
- [ ] `weights` 非 None 时长度必须与 `result_lists` 一致，否则抛出 `ValueError`（领域层纯函数参数校验，非业务验证，使用标准库异常）
- [ ] `SearchResult` 为 TypedDict（`id: str | int` / `score: float` / `payload: dict[str, Any]`），定义在 `src/domain/ports/l3_vector.py`，与 Qdrant `ScoredPoint.id` 返回类型对齐（`str | int`，非仅 `str`）
- [ ] `DenseSearchResult`（`src/application/services/dense_search_service.py`）后续迁移为 `SearchResult` 别名，保持向后兼容
- [ ] 处理空输入（无结果列表、空列表、单列表）不抛出异常，单列表直接返回（跳过融合）
- [ ] 处理重复文档 ID（同文档跨通道出现时 RRF 分数累加）
- [ ] 预留三路融合接口（`*result_lists` 可变参数 + `weights` 参数）
- [ ] 与 Story 3-4（三路融合 + ColBERT 重排序）接口兼容

### AC-3: 混合检索编排（Dense + Sparse → RRF）

**Given** Dense 检索服务（Story 3-1a 已交付）和 Sparse 检索服务（AC-1 新增）均可用
**When** 用户输入查询文本触发混合检索
**Then** Dense 检索和 Sparse 检索并行执行（`asyncio.gather`）
**And** 两路结果通过 RRF 融合算法合并为单一排序列表
**And** 返回融合后的结果（含 `id`/`score`/`payload`，`score` 为 RRF 分数）
**And** 总检索延迟 P95 < 800ms（嵌入生成 + Dense 检索 + Sparse 检索 + RRF 融合，MVP 目标）

**性能测试方法论：**
- 采样次数 ≥ 50 次，排除首次模型加载
- Task 7 集成测试端到端测量（embed→search→RRF fusion→ranked results）
- GPU 环境 P95 < 800ms，CPU 环境 P95 < 1500ms（与 Story 3-1a AC-3 基准对齐）

**验证标准/Validation Criteria:**
- [ ] 应用层 `HybridSearchService` 位于 `src/application/services/hybrid_search_service.py`
- [ ] `search(collection, query_text, limit, tenant_id, filter_payload)` 方法签名与 Dense/Sparse 服务一致
- [ ] 构造函数注入 `DenseSemanticSearchService`、`Bm25SparseSearchService`、RRF 融合函数（`fuse` 作为可调用对象直接注入）
- [ ] `search()` 方法使用 `asyncio.gather()` 并行执行两路检索
- [ ] 一路检索失败时降级为单路结果（WARNING 日志 + 不中断）
- [ ] 两路均失败时抛出 `RuntimeError("Dense 和 Sparse 检索通道均失败")`（无可用信号，基础设施级异常）

### AC-4: 稀疏向量索引管线

**Given** 文档解析完成（Story 2-2a/2-2b），内容已分块
**When** 系统为文档生成索引向量
**Then** 并行生成 Dense 嵌入（已有，`embed_documents()`）和 Sparse 嵌入（新增，`embed_sparse()`）
**And** 将 Dense 向量和 Sparse 向量同时 upsert 至 Qdrant 同一 Collection
**And** Collection 创建时配置 `SparseVectorParams`（`sparse_vectors_config={"sparse": SparseVectorParams()}`）
**And** `index_document` Prefect 任务从 mock 占位替换为真实 Qdrant upsert 实现

**验证标准/Validation Criteria:**
- [ ] `generate_embedding` 任务扩展为返回 `EmbeddingResult` TypedDict（`dense_vectors: list[list[float]]` / `sparse_vectors: list[SparseEmbedding]`），替代原 `list[float]` 返回类型
- [ ] `index_document` 任务签名改为 `index_document(embedding_result: EmbeddingResult)`，内部提取 dense + sparse 向量
- [ ] `document_processing_flow.py` 同步更新（`embedding` 变量类型变更 + `index_document` 参数适配）[Source: src/infrastructure/workflow/flows/document_processing_flow.py:46-47]
- [ ] `index_document` 任务实现真实 Qdrant upsert（`PointStruct` + `NamedSparseVector`）
- [ ] Collection 创建时自动配置稀疏向量索引（`SparseVectorParams`，从 `qdrant_client.models` 导入）
- [ ] 稀疏嵌入失败时降级为仅 Dense 索引（WARNING 日志，`sparse_vectors` 为空列表）
- [ ] `generate_embedding` 已有调用方通过 `EmbeddingResult.dense_vectors` 访问保持兼容

### AC-5: Composition Root 注册

**Given** 混合检索功能已实现
**When** 在 `src/composition_root.py` 注册新端口
**Then** `sparse_search_service` 端口注册为 `Bm25SparseSearchService`（SCOPED lifetime）
**And** `hybrid_search_service` 端口注册为 `HybridSearchService`（SCOPED lifetime）
**And** `embedding_service` 和 `l3_vector` 端口复用于新服务（无需重复注册）
**And** `dense_search_service` 版本号不变（v1.0.0，无接口变更）
**And** 已有测试全部保持通过（无回归）

**验证标准/Validation Criteria:**
- [ ] `sparse_search_service` 端口在 Composition Root 中注册（SCOPED）
- [ ] `hybrid_search_service` 端口在 Composition Root 中注册（SCOPED）
- [ ] Composition Root lambda 工厂注入 `dense_search_service` 和 `sparse_search_service` 到 `hybrid_search_service`
- [ ] 端口契约测试同步更新
- [ ] 已有 `dense_search_service` 测试全部通过（无回归）

### AC-6: 降级策略

**Given** 稀疏嵌入 API（`EmbeddingAPIClient.embed_sparse()`）可能不可用或超时
**When** 混合检索中稀疏通道失败
**Then** Dense 通道继续执行，返回 Dense 单路结果
**And** 日志记录降级原因（WARNING 级别 + 异常类型）
**And** 混合检索整体不中断
**And** RRF 融合检测到仅单路结果时直接返回该路结果（跳过融合）

**验证标准/Validation Criteria:**
- [ ] Sparse 检索异常时 `HybridSearchService.search()` 降级为 Dense-only 结果
- [ ] Dense 检索异常时降级为 Sparse-only 结果
- [ ] 两路均异常时抛出 `RuntimeError("Dense 和 Sparse 检索通道均失败")`
- [ ] 降级事件日志包含异常类型和通道名称
- [ ] 注意：`QdrantVectorStorage.search_sparse()` 异常时静默返回空列表（不抛异常），`Bm25SparseSearchService` 需将空结果视为"通道可用但无匹配"而非降级场景 [Source: src/infrastructure/storage/qdrant/vector_storage.py:210-212]

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 复用已有事件，**不新增事件** — BM25 稀疏检索和 RRF 融合为纯查询操作，不产生领域事件
- [ ] `generate_embedding` 任务扩展为返回 `(dense_vectors, sparse_vectors)`，不改变现有事件

#### 数据模型 (Data Models)
- [ ] **新增** `SearchResult` TypedDict（`src/domain/ports/l3_vector.py`，与 `L3VectorPort` 同文件）：
  - 字段：`id: str | int` / `score: float` / `payload: dict[str, Any]`
  - `id` 类型为 `str | int`，与 Qdrant `ScoredPoint.id` 和现有 `DenseSearchResult.id` 对齐 [Source: src/application/services/dense_search_service.py:26]
  - 后续 `DenseSearchResult` 迁移为 `SearchResult` 的类型别名，保持向后兼容
- [ ] **新增** `EmbeddingResult` TypedDict（`src/infrastructure/workflow/tasks/document_tasks.py`，索引管线内部类型）：
  - 字段：`dense_vectors: list[list[float]]` / `sparse_vectors: list[SparseEmbedding]`
  - 替代 `generate_embedding` 原 `list[float]` 返回类型
- [ ] **复用** `SparseEmbedding` TypedDict（`src/domain/ports/embedding_service.py`）—— 已存在，无需修改
- [ ] **复用** `SparseVector` dataclass（`src/infrastructure/storage/qdrant/models.py`）—— 用于 Qdrant 存储层

#### 统一端口定义注册与管理 (Port Contract)
- [ ] **新增** `Bm25SparseSearchService` 应用服务契约（`src/application/services/sparse_search_service.py`）：
  - 类定义（非 Protocol，直接类，严格镜像 `DenseSemanticSearchService` 模式）
  - `search(collection: str, query_text: str, limit: int = 10, tenant_id: str | None = None, filter_payload: dict | None = None) -> list[SearchResult]`
  - 参数顺序与 `DenseSemanticSearchService.search()` 完全一致 [Source: src/application/services/dense_search_service.py:51-58]
  - 异常类型使用 `ValidationError`（与 Dense 服务一致）
- [ ] **新增** `HybridSearchService` 应用服务契约（`src/application/services/hybrid_search_service.py`）：
  - 类定义
  - `search(collection: str, query_text: str, limit: int = 10, tenant_id: str | None = None, filter_payload: dict | None = None) -> list[SearchResult]`
  - 构造函数注入 `DenseSemanticSearchService`、`Bm25SparseSearchService`、`fuse` 可调用对象（`Callable[..., list[SearchResult]]`）
- [ ] **新增** RRF 融合函数（`src/domain/services/rrf_fusion.py`）：
  - `fuse(*result_lists: list[SearchResult], k: int = 60, weights: list[float] | None = None) -> list[SearchResult]`
  - MVP 阶段 `weights=None`（对称融合），V1（Story 3-4）传入权重实现加权 RRF
  - `weights` 长度不匹配时抛出 `ValueError`（纯函数参数校验，非业务验证）
- [ ] **端口注册** — 在 `src/composition_root.py` 中注册 `sparse_search_service` 和 `hybrid_search_service`
- [ ] **端口契约门禁**（`src/domain/ports/contract_gate.py`）：新端口变更通过兼容性检查
- [ ] **端口契约测试**（`tests/contracts/test_port_contract_search_services.py`）

**端口契约清单：**

| 端口名称 | 版本 | 接口 | 实现模块 | 生命周期 | Owner |
|---------|------|------|----------|----------|-------|
| `embedding_service` | v1.1.0（不变） | `EmbeddingServicePort` | EmbeddingAPIClient | SINGLETON | search-team |
| `l3_vector` | v1.0.0（不变） | `L3VectorPort` | QdrantAdapter | SCOPED | search-team |
| `dense_search_service` | v1.0.0（不变） | `DenseSemanticSearchService` | — | SCOPED | search-team |
| `sparse_search_service` | v1.0.0 | `Bm25SparseSearchService` | `src.application.services.sparse_search_service` | SCOPED | search-team |
| `hybrid_search_service` | v1.0.0 | `HybridSearchService` | `src.application.services.hybrid_search_service` | SCOPED | search-team |

> **版本说明：** `embedding_service` 的 `embed_sparse()` 方法已在 Story 3-1a v1.1.0 中定义，本 Story 仅消费。`l3_vector` 的 `search_sparse()` 方法已在 Story 3-1a 中定义和实现，本 Story 仅消费。

#### API 契约 (API Contract)
- [x] 复用现有 REST API 检索端点（不变）— 混合检索作为内部服务调用，通过 `DenseSemanticSearchService` 的扩展暴露
- [x] 检索结果通过 `SearchResult` TypedDict 标准化输出（Dense/Sparse/混合统一格式）

#### 领域异常契约 (Domain Exception Contract)

> **策略：本 Story 复用已有异常，不新增领域异常。**

**异常使用清单：**

| 异常类型 | 编码 | 使用场景 | 归属层 |
|---------|------|----------|--------|
| `ValidationError` | EXCEPTION_201 | 空查询文本/空集合名称/无效 limit | 应用层（Dense/Sparse/Hybrid 三个服务） |
| `ValueError` | —（标准库） | `fuse()` 函数 `weights` 长度不匹配 | 领域层（纯函数参数校验，非业务异常） |
| `RuntimeError` | —（标准库） | Dense 和 Sparse 检索通道均失败 | 应用层（HybridSearchService，基础设施级异常） |
| `EmbeddingAPIError` | EXCEPTION_306 | 嵌入 API HTTP 传输错误 | 应用层降级捕获（已有，不新增） |
| `TimeoutError` | EXCEPTION_205 | 嵌入 API 超时 | 应用层降级捕获（已有，不新增） |

**设计决策：**
- `ValidationError` 复用 `src/domain/exceptions/business_exceptions.py` 已有定义（EXCEPTION_201），与 `DenseSemanticSearchService` 保持一致
- `fuse()` 领域函数使用 `ValueError` 而非 `ValidationError`，因为 `weights` 长度不匹配是函数参数契约违反（编程错误），非业务实体验证失败
- `RuntimeError` 用于双通道均失败场景，属于基础设施级异常而非业务异常，不占用领域异常编码

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
- RRF 融合算法（`rrf_fusion.py`）：纯数学计算，零外部依赖（`defaultdict`/`dataclasses`）
- 禁止导入：包括且不限于 qdrant-client, fastembed, FlagEmbedding, numpy, fastapi, sqlalchemy 等

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_hybrid_search.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_hybrid_search.py`
- [ ] HAPPY PATH: BM25 稀疏检索返回关键词匹配结果
- [ ] HAPPY PATH: Dense + Sparse → RRF 融合返回混合排序结果
- [ ] EDGE CASE: Sparse 通道失败降级为 Dense-only 结果
- [ ] EDGE CASE: 两路均失败抛出异常
- [ ] EDGE CASE: 空查询文本抛出 ValidationError
- [ ] EDGE CASE: 无匹配结果返回空列表

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）

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
| **TDD 单元测试** | RRF 融合算法 | 两路融合/单路处理/空输入/重复 ID/k 值参数 | `test_rrf_fusion.py` | Task 1 |
| **TDD 单元测试** | Bm25SparseSearchService | embed_sparse 调用/search_sparse 调用/tenant_id 注入/错误处理 | `test_sparse_search_service.py` | Task 2 |
| **TDD 单元测试** | HybridSearchService | 并行检索/RRF 融合/降级策略/mock 依赖 | `test_hybrid_search_service.py` | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_hybrid_search.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_hybrid_search.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | `src` 与测试目录完成清单最终确认 | `test_acceptance_hybrid_search.feature` | Task 7 |
| **TDD 验收测试** | 收尾 BDD 步骤实现 | 完成清单断言与步骤函数 | `test_acceptance_hybrid_search.py` | Task 7 |
| **TDD 契约测试** | 端口契约 / 搜索服务 | 注册/版本/解析 | `test_port_contract_search_services.py` | Task 0 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向/零依赖/RRF 在 domain | `test_arch_hybrid_search.py` | Task 6 |
| **集成测试** | 端到端混合检索 | embed→search→RRF fusion→ranked results | `test_integration_hybrid_search.py` | Task 7 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）- 新增 RRF 融合算法
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）- `Bm25SparseSearchService` + `HybridSearchService`
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）- 索引管线扩展
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration`）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

- [ ] 领域服务（RRF fusion）测试：纯函数测试，无外部依赖，可并行运行
- [ ] 应用层服务测试：使用 `MagicMock(spec=Protocol)` + `AsyncMock(spec=L3VectorPort)` mock 外部依赖
- [ ] 索引管线测试：mock Qdrant client 和 EmbeddingServicePort
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] BDD 步骤函数：使用 `event_loop.run_until_complete()` 运行 async 测试（不使用 `@pytest.mark.asyncio`）

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | BM25 稀疏检索 | Task 2 | 2a: Bm25SparseSearchService 实现 | `test_sparse_search_service.py` |
| AC-2 | RRF 融合算法 | Task 1 | 1a: RRF 融合算法实现 | `test_rrf_fusion.py` |
| AC-3 | 混合检索编排 | Task 3 | 3a: HybridSearchService 实现 | `test_hybrid_search_service.py` |
| AC-4 | 稀疏向量索引管线 | Task 4 | 4a: embed_sparse + 4b: index_document + 4c: flow 调用链 | `test_document_tasks.py`（扩展）+ `test_document_processing_flow.py`（扩展） |
| AC-5 | Composition Root 注册 | Task 5 | 5a: 端口注册 + 契约验证 | `test_port_contract_search_services.py` |
| AC-6 | 降级策略 | Task 3 | 3a: HybridSearchService 降级逻辑 | `test_hybrid_search_service.py` |

### Task 间执行依赖

```
Task 0（SDD 规范定义）
  ├─→ Task 1（RRF 融合算法，领域层）
  ├─→ Task 2（Bm25SparseSearchService，应用层）
  │     └─→ Task 3（HybridSearchService）← 依赖 Task 1（fuse 函数）+ Task 2（Sparse 服务）
  ├─→ Task 4（索引管线扩展）← 可与 Task 2/3 并行
  └─→ Task 5（Composition Root 注册）← 依赖 Task 1 + Task 2 + Task 3
        └─→ Task 6（SDD 架构约束验证）← 依赖 Task 1-5 全部完成
              └─→ Task 7（开发结束验收测试）
```

**并行策略：** Task 1/Task 2/Task 4 三者无相互依赖，可并行开发。Task 3 需等待 Task 1 + Task 2 完成。Task 5 需等待 Task 1-3 全部完成。

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6

> **目的：** 在进入代码实现前，明确 Schema、端口契约、验收标准与六边形架构边界。

- [x] Subtask 0.1: 定义 `SearchResult` TypedDict（`id: str | int` / `score: float` / `payload: dict[str, Any]`，位于 `src/domain/ports/l3_vector.py`）
- [x] Subtask 0.2: 定义 RRF 融合函数签名（`fuse(*result_lists, k=60, weights=None) -> list[SearchResult]`）
- [x] Subtask 0.3: 定义 `Bm25SparseSearchService` 和 `HybridSearchService` 类契约（签名严格对齐 `DenseSemanticSearchService`）
- [x] Subtask 0.4: 定义 `EmbeddingResult` TypedDict（`dense_vectors` / `sparse_vectors`，索引管线内部类型）
- [x] Subtask 0.5: 更新端口注册中心（`registry.py`）与端口契约门禁（`contract_gate.py`）
- [x] Subtask 0.6: 编写端口契约测试 `tests/contracts/test_port_contract_search_services.py`
- [x] Subtask 0.7: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_hybrid_search.feature`（6 个 Scenario）
- [x] Subtask 0.8: 编写 BDD 步骤实现骨架 `tests/acceptance/test_acceptance_hybrid_search.py`
- [x] Subtask 0.9: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕
- [x] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 领域层 — RRF 融合算法

**关联 AC:** AC-2

> **说明：** RRF（Reciprocal Rank Fusion）是纯数学算法，位于领域层（零外部依赖）。
> 出自 Cormack, Clarke, Büttcher 于 SIGIR 2009 发表的论文 [Source: https://doi.org/10.1145/1571941.1572114]。
> 论文原文明确写道：*"k = 60 was fixed during a pilot investigation and not altered during subsequent validation"*。

#### RRF 融合公式

```
RRF_score(d) = Σ w_i / (k + rank_i(d))
               i
```

其中：
- `rank_i(d)`：文档 `d` 在第 `i` 个检索列表中的排名，**从 1 开始计数**（论文标准）
- `k`：平滑常数，默认 60（论文经验值）
- `w_i`：第 `i` 个检索列表的权重，默认 `None`（对称融合，`w_i = 1.0`）

#### k=60 设计决策

**为什么 SISYS MVP 使用 k=60：**
1. **同模型产出**：Dense 和 Sparse 均来自 bge-m3 同一模型，信号质量对等，无需通过 k 值偏向任一通道
2. **无标注数据**：MVP 阶段没有检索质量标注数据集，无法通过 NDCG@10 实验校准 k 值
3. **学术界鲁棒默认值**：k=60 是唯一经过大量 TREC 基准和 LETOR 3 数据集验证的通用默认值（Elasticsearch（`rank_constant` 社区实践设为 60）、PyTerrier、Pyserini 均推荐 k=60）
4. **平滑衰减**：rank 1→rank 2 差约 1.6%，防止任一路的 top-1 绝对主导融合
5. **可配置**：k 作为默认参数暴露，有标注数据后可随时调优

**与 Qdrant 社区 k=2 的区别：** Qdrant 社区部分实践者主张 k=2（更强 top-heavy 偏向），但那适用于检索器质量差异大的场景（如手动 RRF 实现）。SISYS 的 Dense 和 Sparse 同源（bge-m3），质量对等，k=2 会过度惩罚排名稍低的高质量结果。

#### 对称融合 → 加权 RRF 演进路线

| 阶段 | Story | k 值 | 权重策略 | 理由 |
|------|-------|------|---------|------|
| **MVP** | 3-1b | k=60 | 对称融合 `weights=None`（`w_i=1.0`） | 两路同模型产出，质量对等 |
| **V1** | 3-4 | k=60 | 可配置权重 `weights=[w_dense, w_sparse, w_graph]` | 三路信号质量差异大：Graph 信号稀疏但高价值，需降低权重（建议 0.4:0.4:0.2） |
| **V2** | 远期 | 标注数据 grid search [0,2,10,30,60,100] | 查询自适应权重 | 不同查询类型（关键词 vs 语义）最优策略不同 |

#### TDD 循环 A：RRF 融合算法核心实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_rrf_fusion.py`（对称两路融合/加权两路融合/对称三路融合/加权三路融合/单路直接返回/空输入/重复文档 ID RRF 分数累加/自定义 k 值/空列表/混合场景/weights 长度不一致→ValueError/全部权重为 0/rank 从 1 开始验证） |
| 🟢 绿 | 在 `src/domain/services/rrf_fusion.py` 实现 `fuse(*result_lists: list[SearchResult], k: int = 60, weights: list[float] | None = None) -> list[SearchResult]` |
| 🔄 重构 | Google 中文注释、docstring、`RRF_K_DEFAULT = 60` 常量提取、k=60 决策注释链接论文 |

- [x] Subtask 1.1: 🔴 红 — 编写 `test_rrf_fusion.py`（≥15 个 test case）
  - `test_symmetric_fusion_two_lists` — 两路对称融合，验证 `enumerate(results, start=1)` 确保 rank 从 1 开始
  - `test_weighted_fusion` — 加权融合 `weights=[0.4, 0.4, 0.2]` 验证权重生效
  - `test_weights_length_mismatch_raises_value_error` — weights 长度不匹配
  - `test_single_list_passthrough` — 单路直接返回（跳过融合）
  - `test_empty_input` — 空输入不抛异常
  - `test_duplicate_document_across_lists` — 同文档跨通道 RRF 分数累加
  - `test_custom_k_value` — 自定义 k=2/10/100
  - `test_empty_result_lists` — 某路空列表
  - `test_all_zero_weights` — 全零权重的边界行为
  - `test_rank_starts_at_one` — 验证 `enumerate(results, start=1)`
- [x] Subtask 1.2: 🟢 绿 — 实现 RRF 融合算法最小代码
  ```python
  from collections import defaultdict
  from typing import Any

  from src.domain.ports.l3_vector import SearchResult

  RRF_K_DEFAULT = 60

  def fuse(
      *result_lists: list[SearchResult],
      k: int = RRF_K_DEFAULT,
      weights: list[float] | None = None,
  ) -> list[SearchResult]:
      """RRF 对称/加权融合。

      MVP（对称融合）: fuse(dense_results, sparse_results)
      V1（加权融合）: fuse(dense, sparse, graph, weights=[0.4, 0.4, 0.2])
      """
      if not result_lists:
          return []
      if weights is not None and len(weights) != len(result_lists):
          raise ValueError(
              f"weights 长度({len(weights)})与 result_lists 长度({len(result_lists)})不匹配"
          )
      if len(result_lists) == 1:
          return list(result_lists[0])

      effective_weights = weights or [1.0] * len(result_lists)
      scores: dict[str | int, tuple[float, SearchResult]] = {}

      for w, results in zip(effective_weights, result_lists):
          for rank, doc in enumerate(results, start=1):
              doc_id = doc["id"]
              rrf_score = w / (k + rank)
              if doc_id in scores:
                  old_score, old_doc = scores[doc_id]
                  scores[doc_id] = (old_score + rrf_score, old_doc)  # payload 保留首次出现
              else:
                  scores[doc_id] = (rrf_score, doc)

      return [
          SearchResult(id=doc["id"], score=score, payload=doc["payload"])
          for doc_id, (score, doc) in
          sorted(scores.items(), key=lambda x: x[1][0], reverse=True)
      ]
  ```
- [x] Subtask 1.3: 🔄 重构 — 完善 Google 中文 docstring、添加 `RRF_K_DEFAULT = 60` 常量

**完成标准/Definition of Done:**
- [x] RRF 融合算法实现完成，`fuse(*result_lists, k=60, weights=None)`
- [x] 领域服务测试通过，覆盖率 ≥ 90%
- [x] 领域层零外部依赖（仅 Python 标准库 `defaultdict`/`typing` + 领域内部 `SearchResult`）
- [x] rank 从 1 计数（`enumerate(results, start=1)`），match 论文公式
- [x] `weights=None`（对称融合 MVP）和 `weights=[...]`（加权融合 V1）两种模式均测试通过
- [x] `weights` 长度不匹配时抛出 `ValueError`（纯函数参数校验）
- [x] 重复文档 ID 跨通道 RRF 分数累加，payload 取首次出现
- [x] 接口兼容 Story 3-4 三路融合（`*result_lists` 可变参数 + `weights` 参数）
- [x] `src/domain/services/__init__.py` 更新导出 `fuse` 函数和 `RRF_K_DEFAULT` 常量

---

### Task 2: 应用层 — Bm25SparseSearchService

**关联 AC:** AC-1

> **说明：** 严格镜像 `DenseSemanticSearchService` [Source: src/application/services/dense_search_service.py] 的架构模式。
> 注入 `EmbeddingServicePort` 和 `L3VectorPort`，编排 `embed_sparse([query_text])[0]` → `search_sparse()` 流程。
> 使用 `asyncio.to_thread()` 包装同步 `embed_sparse()` 调用。
> 注意：`embed_sparse()` 是批量接口（`texts: list[str] -> list[SparseEmbedding]`），单查询需 `embed_sparse([query_text])[0]` 提取首元素。

#### TDD 循环 A：Bm25SparseSearchService 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_sparse_search_service.py`（正常搜索/mock embed_sparse 批量接口/mock search_sparse/tenant_id 注入/空查询 ValidationError/空集合 ValidationError/无效 limit ValidationError/空结果/过滤器透传/embed_sparse 失败传播/search_sparse 过滤器仅支持 MatchValue 的行为验证） |
| 🟢 绿 | 在 `src/application/services/sparse_search_service.py` 实现 `Bm25SparseSearchService.search()` |
| 🔄 重构 | Google 中文注释、类型注解完善 |

- [x] Subtask 2.1: 🔴 红 — 编写 `TestBm25SparseSearchService`（≥12 个 test case，mock 模式参考 `test_dense_search_service.py`）
  - 验证 `embed_sparse([query_text])[0]` 批量接口调用模式
  - 验证 `search(collection, query_text, limit, tenant_id, filter_payload)` 参数顺序与 Dense 一致
  - 验证空查询/空集合/无效 limit 均抛出 `ValidationError`
- [x] Subtask 2.2: 🟢 绿 — 实现 `Bm25SparseSearchService` 最小代码
- [x] Subtask 2.3: 🔄 重构 — 添加 docstring、对齐 `DenseSemanticSearchService` 命名风格

**完成标准/Definition of Done:**
- [x] `Bm25SparseSearchService` 实现完成
- [x] 应用层测试通过，覆盖率 ≥ 85%
- [x] 与 `DenseSemanticSearchService` 接口一致（同名方法、同参数顺序 `collection, query_text, limit, tenant_id, filter_payload`、同异常类型 `ValidationError`）
- [x] `embed_sparse([query_text])[0]` 批量接口调用模式正确
- [x] `search_sparse()` 过滤器仅支持 `MatchValue` 的行为已在测试中文档化

---

### Task 3: 应用层 — HybridSearchService（混合检索编排）

**关联 AC:** AC-3, AC-6

> **说明：** 注入 `DenseSemanticSearchService`、`Bm25SparseSearchService` 和 RRF `fuse` 可调用对象。
> `search(collection, query_text, limit, tenant_id, filter_payload)` 方法签名与两路服务一致。
> 使用 `asyncio.gather()` 并行执行两路检索，RRF 融合后返回统一结果。
> 降级策略：单路失败 → WARNING 日志 + 降级为单路结果；两路均失败 → `RuntimeError`。
> 注意：`search_sparse()` 在 Qdrant 层异常时静默返回空列表，不抛异常。降级逻辑应在应用层捕获 `embed_sparse()` 调用异常（`EmbeddingAPIError`/`TimeoutError`）而非底层检索异常。

#### TDD 循环 A：HybridSearchService 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_hybrid_search_service.py`（正常混合搜索/mock dense + sparse/RRF 融合调用验证/并行执行验证/Sparse 降级/Dense 降级/双路失败 RuntimeError/空查询 ValidationError/空集合 ValidationError/无效 limit ValidationError/过滤器透传） |
| 🟢 绿 | 在 `src/application/services/hybrid_search_service.py` 实现 `HybridSearchService.search()` |
| 🔄 重构 | 降级策略常量化、日志完善 |

- [x] Subtask 3.1: 🔴 红 — 编写 `TestHybridSearchService`（≥12 个 test case）
- [x] Subtask 3.2: 🟢 绿 — 实现 `HybridSearchService` 最小代码
- [x] Subtask 3.3: 🔄 重构 — 降级策略 + 日志完善

**完成标准/Definition of Done:**
- [x] `HybridSearchService` 实现完成
- [x] 输入验证与 Dense/Sparse 服务一致（空查询/空集合/无效 limit 抛出 `ValidationError`）
- [x] 两路并行检索 + RRF 融合编排正确
- [x] 降级策略三种场景测试通过（Sparse 降级/Dense 降级/双路失败 RuntimeError）
- [x] 应用层覆盖率 ≥ 85%

---

### Task 4: 基础设施层 — 索引管线扩展

**关联 AC:** AC-4

> **说明：** 文档索引管线当前只生成 Dense 向量（`generate_embedding`），且 `index_document` 为 mock。
> 本 Task 扩展管线以支持稀疏向量生成和 Qdrant 双向量 upsert。
> **关键级联变更：** `generate_embedding` 返回类型从 `list[float]` 变更为 `EmbeddingResult` TypedDict，
> 需同步更新 `index_document` 签名和 `document_processing_flow.py` 调用链。
>
> ⚠️ **2026-08-21 Epic 3 架构对齐重构说明**：`generate_embedding`/`index_document` 已从 `document_tasks.py` 删除。
> 文档向量索引统一由事件驱动链承担（`DocumentProcessed → SemanticChunking → RAGIndexed → ChunkIndexingHandler`）。
> 本 Task 的历史实现（EmbeddingResult TypedDict、双向量 upsert 逻辑）已迁移至 `ChunkIndexingHandler`。
> 以下 TDD 循环为历史记录保留，新代码禁止调用这些函数。

#### TDD 循环 A：generate_embedding 扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/infrastructure/workflow/test_document_tasks.py`（generate_embedding 返回 dense + sparse/embed_sparse 调用验证/embed_sparse 失败降级） |
| 🟢 绿 | 修改 `src/infrastructure/workflow/tasks/document_tasks.py`：`generate_embedding` 并行调用 `embed_documents()` 和 `embed_sparse()` |
| 🔄 重构 | 向后兼容检查（已有调用方不受影响） |

- [x] Subtask 4.1: 🔴 红 — 编写 `generate_embedding` 稀疏扩展测试
- [x] Subtask 4.2: 🟢 绿 — 实现 `generate_embedding` 双向量生成（返回 `EmbeddingResult` TypedDict）
- [x] Subtask 4.3: 🔄 重构 — 降级策略（sparse 失败→仅 dense，`sparse_vectors` 为空列表）

#### TDD 循环 B：index_document 真实实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `index_document` 测试（mock Qdrant client：upsert 调用 PointStruct + NamedSparseVector/稀疏向量写入验证） |
| 🟢 绿 | 实现 `index_document` 真实 Qdrant upsert（替换 mock `return {"indexed": False, "chunk_count": 0}`） |
| 🔄 重构 | Collection sparse_vectors_config 创建逻辑 |

- [x] Subtask 4.4: 🔴 红 — 编写 `index_document` 真实实现测试（mock Qdrant client：upsert 调用 PointStruct + NamedSparseVector/稀疏向量写入验证）
- [x] Subtask 4.5: 🟢 绿 — 实现 `index_document(embedding_result: EmbeddingResult)` 真实 Qdrant upsert（替换 mock `return {"indexed": False, "chunk_count": 0}`）
- [x] Subtask 4.6: 🔄 重构 — Collection 创建时自动配置 sparse vectors（`SparseVectorParams` 从 `qdrant_client.models` 导入）
- [x] Subtask 4.7: 🔴 红 — 编写 `document_processing_flow.py` 调用链更新测试（`generate_embedding` 返回 `EmbeddingResult` → `index_document` 参数适配）
- [x] Subtask 4.8: 🟢 绿 — 更新 `document_processing_flow.py` 调用链适配新返回类型 [Source: src/infrastructure/workflow/flows/document_processing_flow.py:46-47]

**完成标准/Definition of Done:**
- [x] `generate_embedding` 扩展为产出 `EmbeddingResult`（Dense + Sparse 双向量 TypedDict）
- [x] `index_document` 从 mock 替换为真实 Qdrant upsert（接受 `EmbeddingResult` 参数）
- [x] `document_processing_flow.py` 调用链已更新适配新返回类型
- [x] 基础设施层覆盖率 ≥ 75%

---

### Task 5: Composition Root 注册 + 端口契约验证

**关联 AC:** AC-5

> **说明：** 注册新应用服务端口，注入依赖链。遵循现有 `search-team` owner 约定。

#### TDD 循环 A：Composition Root 注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 contract test 验证端口可解析（`test_port_contract_search_services.py` 中 `test_sparse_search_service_registered` 和 `test_hybrid_search_service_registered`） |
| 🟢 绿 | 修改 `src/composition_root.py`：注册 `sparse_search_service` 和 `hybrid_search_service`，注入依赖（`fuse` 函数作为可调用对象 `from src.domain.services.rrf_fusion import fuse` 直接注入） |
| 🔄 重构 | 版本号确认、端口契约清单更新 |

- [x] Subtask 5.1: 🔴 红 — 编写端口注册验证测试
- [x] Subtask 5.2: 🟢 绿 — 实现 Composition Root 注册
- [x] Subtask 5.3: 🔄 重构 — 运行全部已有测试确认无回归

**完成标准/Definition of Done:**
- [x] `sparse_search_service` 和 `hybrid_search_service` 端口注册完成
- [x] 端口契约测试通过
- [x] 已有 `dense_search_service` 测试全部通过（无回归）

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** AC-2, AC-3, AC-5

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [x] Subtask 6.1: 创建 `tests/unit/architecture/test_arch_hybrid_search.py`
- [x] Subtask 6.2: 实现领域层零外部依赖验证（`rrf_fusion.py` 仅使用 Python 标准库）
- [x] Subtask 6.3: 实现依赖方向验证（application → domain ✓，application → infrastructure ✗）
- [x] Subtask 6.4: 实现 RRF 融合函数在 domain/services 中定义验证
- [x] Subtask 6.5: 实现 `Bm25SparseSearchService` 和 `HybridSearchService` 在 application/services 中定义验证
- [x] Subtask 6.6: 实现循环依赖检测（使用 ruff `E` 规则或 `isort --check-only`）
- [x] Subtask 6.7: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**
- [x] 所有架构/约束测试通过
- [x] 测试输出清晰的合规报告
- [x] 任何违规都会导致测试失败

---

### Task 7: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-6

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_hybrid_search.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_hybrid_search.py` 的 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达、保持步骤函数可维护性 |

- [x] Subtask 7.1: 场景 1 — 验证 `src` 完成清单的逐项确认
- [x] Subtask 7.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单的逐项确认
- [x] Subtask 7.3: 运行集成测试 `tests/integration/test_integration_hybrid_search.py`（端到端：embed→Dense search + Sparse search→RRF fusion）
- [x] Subtask 7.4: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验

**完成标准/Definition of Done:**
- [x] `src` 完成清单已逐项验证确认
- [x] `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单已逐项验证确认
- [x] 开发结束验收测试通过
- [x] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../docs/architecture/architecture.md) — §17.1.5 混合检索架构

- **架构模式:** 六边形架构（Ports & Adapters）— RRF 融合算法在领域层（纯数学），搜索服务在应用层（编排），Qdrant 实现在基础设施层
- **检索管线目标架构**：`Query → Dense (BGE-M3) + Sparse (BM25) → RRF Fusion (k=60) → Ranked Results`
- **设计约束:** 领域层零外部依赖；依赖方向 domain ← application ← infrastructure
- **接口治理:** 统一端口注册（`PortSpec` 元数据 + `register_port()`）→ `composition_root.py` 唯一注册入口 → `search-team` owner
- **镜像模式（Story 3-1a 复用）:** `Bm25SparseSearchService` 镜像 `DenseSemanticSearchService` 的构造函数注入 + `asyncio.to_thread()` + `tenant_id` 注入模式
- **技术栈:** Python 3.11+; bge-m3（FlagEmbedding）稀疏词法权重; Qdrant 1.7+ NamedSparseVector; rank-bm25 0.2.2+（备用）

### 关键架构决策

**来源:** [Cormack et al., SIGIR 2009](https://doi.org/10.1145/1571941.1572114) — Reciprocal Rank Fusion 原始论文

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **RRF 对称融合（k=60）MVP** | 无需调参、不依赖分数分布、同模型产出（bge-m3）质量对等无需加权、学术界大量验证 | 忽略原始分值大小信息，无法区分强信号的 rank1 和弱信号的 rank1 | ✅ 9/10 |
| 线性加权融合 | 简单直观、可解释性强 | Dense 余弦相似度 [0,1] 与 BM25 [0,∞) 不可直接比较，需归一化 | 5/10 |
| 学习排序（LTR） | 理论上最优、可利用标注数据 | 需要训练数据、部署复杂、MVP 阶段过度设计 | 4/10 |

**RRF 公式：**

```
RRF_score(d) = Σ w_i / (k + rank_i(d))
               i
```

- `rank_i(d)`：文档 `d` 在第 `i` 个检索列表中的排名，**从 1 开始计数**
- `k`：平滑常数，默认 60（论文经验值）
- `w_i`：MVP 阶段 `None`（对称融合，`w_i = 1.0`）；V1 阶段传入 `[w_dense, w_sparse, w_graph]`

**决策理由：**
1. RRF（k=60）是信息检索领域公认的融合算法，出自 Cormack et al. SIGIR 2009 论文（被广泛引用）
2. 无需分数归一化（Dense 余弦相似度 `[0,1]` 与 BM25 分值 `[0,∞)` 不可直接比较）——这是 RRF 相比线性加权的核心优势
3. SISYS Dense 和 Sparse 均来自 bge-m3 同一模型，信号质量对等，k=60 对称融合不偏向任一通道
4. 论文原文：*"k = 60 was fixed during a pilot investigation and not altered during subsequent validation"*——k=60 是经过大量 TREC 基准验证的鲁棒默认值
5. Elasticsearch 8.16+ 使用 `rank_constant` 参数（语义等价于 k，社区实践常设 `rank_constant=60` 对齐论文）、PyTerrier、Pyserini 均以 k=60 为默认值或推荐值
6. **函数签名一次到位**：`fuse(*result_lists, k=60, weights=None)` —— `*result_lists` 可变参数预留三路扩展，`weights` 参数预留加权 RRF

**三阶段演进路线：**

| 阶段 | Story | k 值 | 权重策略 | 理由 |
|------|-------|------|---------|------|
| **MVP** | 3-1b | k=60 | 对称融合 `weights=None`（`w_i = 1.0`） | 两路同模型产出，质量对等 |
| **V1** | 3-4 | k=60 | 可配置 `weights=[w_dense, w_sparse, w_graph]` | 三路信号质量差异大：建议 0.4:0.4:0.2 |
| **V2** | 远期 | grid search [0,2,10,30,60,100] | 查询自适应 | 基于 NDCG@10 标注数据校准 |

**k=60 vs 业界 k=2 的区别：** Qdrant 社区部分实践者主张 k=2（更强 top-heavy 偏向），但那适用于检索器质量差异大的场景。SISYS 的 Dense 和 Sparse 同源（bge-m3），质量对等，k=2 会过度惩罚排名稍低的高质量结果。k=60 的平滑衰减确保"多路共识"优于"单路主导"。

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── ports/
│   │   ├── embedding_service.py          # [已有] EmbeddingServicePort（含 embed_sparse）
│   │   └── l3_vector.py                  # [MODIFY] 新增 SearchResult TypedDict（id: str | int）
│   └── services/
│       ├── __init__.py                   # [MODIFY] 导出 fuse + RRF_K_DEFAULT
│       └── rrf_fusion.py                 # [NEW] RRF 融合算法（纯 Python，零外部依赖）
│
├── application/
│   └── services/
│       ├── dense_search_service.py       # [已有] DenseSemanticSearchService（v1.0.0，不变）
│       ├── sparse_search_service.py      # [NEW] Bm25SparseSearchService
│       └── hybrid_search_service.py      # [NEW] HybridSearchService
│
├── infrastructure/
│   ├── storage/qdrant/
│   │   ├── vector_storage.py             # [已有] search_sparse() 已实现
│   │   ├── qdrant_adapter.py             # [已有] search_sparse() 已实现
│   │   ├── models.py                     # [已有] SparseVector dataclass
│   │   ├── bm25_builder.py              # [已有] BM25Builder（TF-IDF 降级方案）
│   │   └── collection_manager.py         # [已有] sparse_vectors_config 透传
│   └── workflow/tasks/
│       └── document_tasks.py             # [MODIFY] generate_embedding + index_document + EmbeddingResult
│
├── infrastructure/workflow/flows/
│   └── document_processing_flow.py       # [MODIFY] 调用链适配 EmbeddingResult
│
└── composition_root.py                   # [MODIFY] 注册新搜索服务 + 注入 fuse 可调用对象

tests/
├── unit/
│   ├── domain/
│   │   └── services/test_rrf_fusion.py                # [NEW] RRF 融合单元测试
│   ├── application/
│   │   ├── test_sparse_search_service.py               # [NEW]（与 test_dense_search_service.py 同目录）
│   │   ├── test_hybrid_search_service.py               # [NEW]
│   │   └── test_dense_search_service.py                # [已有，不修改]
│   ├── infrastructure/
│   │   └── workflow/
│   │       ├── test_document_tasks.py                  # [MODIFY] 扩展索引管线测试
│   │       └── test_document_processing_flow.py        # [MODIFY] Flow 调用链适配测试
│   └── architecture/
│       └── test_arch_hybrid_search.py                  # [NEW] 架构约束测试
├── integration/
│   └── test_integration_hybrid_search.py               # [NEW] 端到端集成测试
├── acceptance/
│   ├── test_acceptance_hybrid_search.feature           # [NEW] Gherkin 场景
│   └── test_acceptance_hybrid_search.py                # [NEW] BDD 步骤实现
└── contracts/
    └── test_port_contract_search_services.py           # [NEW] 端口契约验证
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 3-1a-Dense语义检索](./3-1a-dense-semantic-search.md)

**关键学习/Key Learnings:**
1. **EmbeddingServicePort 双模式设计** — `embed_query()`/`embed_documents()` 用于 Dense，`embed_sparse()` 用于 Sparse。两者通过同一 FlagEmbedding API 服务，`return_sparse=True` 参数区分。Story 3-1b 消费 `embed_sparse()` 方法（已在 Story 3-1a v1.1.0 迁移中实现）
2. **asyncio.to_thread() 包装同步调用** — `EmbeddingAPIClient` 的 embed 方法是同步的，`DenseSemanticSearchService` 使用 `asyncio.to_thread()` 包装以避免阻塞事件循环。Story 3-1b 的 `Bm25SparseSearchService` 必须遵循同一模式
3. **tenant_id 安全注入** — 检索服务自动注入 `tenant_id` 过滤器，防止跨租户数据泄露。Story 3-1b 的 Sparse 检索必须同样注入
4. **Mock 模式** — 应用层测试使用 `MagicMock(spec=EmbeddingServicePort)` + `AsyncMock(spec=L3VectorPort)` mock 外部依赖，不启动真实 Qdrant/API
5. **BGE-M3 稀疏词法权重优于简单 TF-IDF** — `BM25Builder`（TF-IDF）是降级方案，主路径使用 bge-m3 的 `encode(return_sparse=True)` 词法权重 [Source: Story 3-1a Dev Notes]
6. **search_sparse() 过滤器限制** — `search_sparse()` 的 filter 实现仅支持 `MatchValue`（精确匹配），不支持 `Range`（数值范围）。与 `search()` 功能不对称，Story 3-1b 需注意此限制 [Source: Story 3-1a Dev Notes §已知限制]
7. **index_document 为 mock 占位** — 当前 `index_document` 返回 `{"indexed": False, "chunk_count": 0}`（硬编码 mock），Story 3-1b 需实现真实 Qdrant upsert [Source: src/infrastructure/workflow/tasks/document_tasks.py:135]
8. **Collection 稀疏配置** — `create_collection()` 支持 `sparse_vectors_config` 透传，但未在索引管线中连线。索引管线需要在创建 Collection 时配置 `SparseVectorParams()` [Source: src/infrastructure/storage/qdrant/collection_manager.py:73]
9. **search_sparse() 异常静默吞没** — `QdrantVectorStorage.search_sparse()` 在异常时返回空列表而非抛出异常（`vector_storage.py:210-212`）。`HybridSearchService` 的降级逻辑应捕获 `embed_sparse()` 调用层的异常（`EmbeddingAPIError`/`TimeoutError`），而非依赖底层检索异常传播

**应用到本故事/Applied to This Story:**
- [x] `Bm25SparseSearchService` 严格镜像 `DenseSemanticSearchService`（参数顺序 `collection, query_text, limit, tenant_id, filter_payload`、异常类型 `ValidationError`）
- [x] `tenant_id` 过滤器自动注入（复用 `_build_filter()` 模式）
- [x] 主路径使用 bge-m3 `embed_sparse([query_text])[0]`（批量接口取首元素），`BM25Builder` 作为降级方案
- [x] `index_document` 替换 mock 为真实 Qdrant upsert（`PointStruct` + `NamedSparseVector`）
- [x] `generate_embedding` 返回 `EmbeddingResult` TypedDict，同步更新 `document_processing_flow.py` 调用链
- [x] 应用层测试使用 `MagicMock(spec=...)` + `AsyncMock(spec=...)` mock 模式
- [x] RRF 融合算法在 domain/services 中（纯 Python），遵循领域零依赖原则
- [x] `fuse` 函数作为可调用对象注入 `HybridSearchService`（非类实例）
- [x] `HybridSearchService` 降级逻辑捕获嵌入层异常（`embed_sparse` 失败），而非底层 `search_sparse` 异常（已被静默吞没）
- [x] `SearchResult.id` 类型为 `str | int`，与 `DenseSearchResult` 和 Qdrant `ScoredPoint.id` 对齐

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Opus 4.8 |
| **Version** | dev-story workflow — SDD+TDD 融合模式模板 v2.8.0 |
| **Execution Date** | 2026-06-05 |
| **Completion Date** | 2026-06-05 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-dev-story/workflow.md` |
| **Template** | `docs/developer/story-template.md` (v2.8.0) |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` + `docs/architecture/sisys-core-domain-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/3-1a-dense-semantic-search.md` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` §Epic 3, Story 3-1b 提取
- [x] 架构约束从 `architecture.md` §17.1.5 和 `story-template.md` §六边形架构约束 提取
- [x] 前一个故事学习经验从 Story 3-1a 整合（8 条关键经验）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范（Story 3-1a 镜像模式）
- [x] AC→Task→Subtask 追溯矩阵完整（6 AC × 7 Task）
- [x] 每个 Task 含独立 TDD 红→绿→重构循环
- [x] RRF 融合算法 k=60 来自架构文档
- [x] Story 3-4 接口预留（`*result_lists` 可变参数）
- [x] **实施完成：Task 0-7 全部完成，118 tests passed, 1 skipped (E2E)**

### 实施摘要 Implementation Summary

**已完成实现（2026-06-05）：**

- **Task 0 (SDD)：** SearchResult/EmbeddingResult TypedDict 定义，Gherkin 验收测试（7 场景），BDD 步骤骨架，端口契约测试
- **Task 1 (RRF 融合)：** `src/domain/services/rrf_fusion.py` — 纯 Python RRF 算法，k=60 默认值，21 单元测试全部通过
- **Task 2 (Sparse 检索)：** `src/application/services/sparse_search_service.py` — 严格镜像 DenseSemanticSearchService，19 单元测试
- **Task 3 (混合检索)：** `src/application/services/hybrid_search_service.py` — asyncio.gather 并行 + 降级策略，12 单元测试
- **Task 4 (索引管线)：** `generate_embedding` 双向量生成 + `index_document` 真实 Qdrant upsert，8 新测试 + 11 已有测试适配
- **Task 5 (Composition Root)：** 注册 `sparse_search_service` 和 `hybrid_search_service`，注入 fuse 可调用对象
- **Task 6 (架构验证)：** 领域层零依赖/依赖方向正确/服务位于正确层次，9 架构测试
- **Task 7 (验收)：** 集成测试（RRF 融合 + Composition 验证），7 测试通过

**测试总览：118 passed, 1 skipped (E2E 需真实基础设施)**

### 文件清单 File List

**创建的新文件/Created Files:**
- `src/domain/services/rrf_fusion.py` — RRF 融合算法（纯 Python，零外部依赖）
- `src/application/services/sparse_search_service.py` — Bm25SparseSearchService
- `src/application/services/hybrid_search_service.py` — HybridSearchService
- `tests/unit/domain/services/test_rrf_fusion.py` — RRF 融合单元测试（21 tests）
- `tests/unit/application/test_sparse_search_service.py` — Sparse 服务单元测试（19 tests）
- `tests/unit/application/test_hybrid_search_service.py` — Hybrid 服务单元测试（12 tests）
- `tests/unit/infrastructure/workflow/test_document_tasks.py` — 索引管线测试（8 tests）
- `tests/unit/architecture/test_arch_hybrid_search.py` — 架构约束验证（9 tests）
- `tests/contracts/test_port_contract_search_services.py` — 端口契约测试（12 tests）
- `tests/integration/test_integration_hybrid_search.py` — 集成测试（7 tests）
- `tests/acceptance/test_acceptance_hybrid_search.feature` — Gherkin 验收场景（7 Scenarios）
- `tests/acceptance/test_acceptance_hybrid_search.py` — BDD 步骤实现

**修改的文件/Modified Files:**
- `src/domain/ports/l3_vector.py` — 新增 `SearchResult` TypedDict
- `src/domain/services/__init__.py` — 导出 `fuse` + `RRF_K_DEFAULT`
- `src/infrastructure/workflow/tasks/document_tasks.py` — `generate_embedding` 返回 `EmbeddingResult`，`index_document` 真实 Qdrant upsert
- `src/infrastructure/workflow/flows/document_processing_flow.py` — 导入 `EmbeddingResult`
- `src/composition_root.py` — 注册 `sparse_search_service` + `hybrid_search_service`
- `tests/unit/infrastructure/workflow/test_document_processing_flow.py` — 适配 `EmbeddingResult` 类型变更

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
| **覆盖 FR** | FR-SR-01（混合检索 — BM25 稀疏通道）/ FR-SR-04（部分 — 两路 RRF 融合基础） |
| **覆盖 NFR** | NFR-PERF-01（检索延迟 P95<800ms MVP） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-7，8 个 Task）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 至 AC-6，6 个 AC）
3. [x] Architecture constraints extracted 架构约束已提取（六边形架构/RRF k=60/领域零依赖）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（Story 3-1a，8 条关键经验）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | `Bm25SparseSearchService.search()` 参数顺序与 Dense 不一致，缺少 `tenant_id` | P0 | 对齐 `DenseSemanticSearchService` 签名：`(collection, query_text, limit, tenant_id, filter_payload)` |
| 2 | 应用层验证异常使用 `ValueError`，与 Dense 服务 `ValidationError` 不一致 | P0 | 统一为 `ValidationError`，领域层 `fuse()` 的 `weights` 校验保留 `ValueError`（纯函数参数校验） |
| 3 | `SearchResult.id` 类型为 `str`，与 `DenseSearchResult.id: str \| int` 不一致 | P0 | 修正为 `str \| int`，对齐 Qdrant `ScoredPoint.id` |
| 4 | `generate_embedding` 返回类型从 `list[float]` 变更但未规划级联影响 | P0 | 新增 `EmbeddingResult` TypedDict + 更新 `index_document` 签名 + 更新 `document_processing_flow.py` |
| 5 | RRF 代码示例使用 `dict[str, Any]` 与声明的 `SearchResult` 类型矛盾 | P0 | 代码示例统一使用 `SearchResult` TypedDict |
| 6 | `embed_sparse()` 批量接口调用模式未说明 | P1 | 明确 `embed_sparse([query_text])[0]` 取首元素 |
| 7 | `HybridSearchService` 注入 `fuse` 函数的方式未说明 | P1 | 明确为可调用对象注入 `Callable[..., list[SearchResult]]` |
| 8 | Task 0 缺失「领域异常契约」子节 | P2 | 新增异常使用清单和设计决策 |
| 9 | 缺失 Task 间执行依赖图 | P2 | 新增依赖图 + 并行策略说明 |
| 10 | 依赖方向矩阵缺少 `interfaces` 行 | P2 | 补充 `interfaces → domain ✓, interfaces → application ✓` |
| 11 | RRF 代码 payload 取最后出现，文档说首次出现 | P2 | 修正代码：`old_doc` 保留首次出现的 payload |
| 12 | Elasticsearch k=60 默认值声明不准确 | P2 | 修正为 `rank_constant` 参数（社区实践常设 60） |
| 13 | 模板版本 v2.7.0 应为 v2.8.0 | P2 | 更新版本引用 |

---

### 🔍 代码审查发现 Review Findings

> 审查日期: 2026-06-06 | 并行审查层: Blind Hunter + Edge Case Hunter + Acceptance Auditor

#### Patch（待修复）

- [x] **[Review][Patch] P1: 协程泄漏 — generate_embedding 中 sparse_task 在 dense 异常时未 cancel** [P0] [document_tasks.py:148-160] — 已修复: asyncio.gather(return_exceptions=True)
- [x] **[Review][Patch] P2: QdrantAdapter.upsert_points() 丢弃 dict 输入的 sparse_vector** [P0] [qdrant_adapter.py:54-63] — 已修复: VectorPoint(sparse_vector=point.get("sparse_vector"))
- [x] **[Review][Patch] P3: AC-1 验收测试 Collection 创建未配置 sparse_vectors_config** [P0] — 改为 P7 自动配置修复
- [x] **[Review][Patch] P4: 验收测试"日志记录降级原因"步骤体为空 pass** [P1] [test_acceptance_hybrid_search.py] — 已修复: caplog 断言
- [x] **[Review][Patch] P5: fuse() 函数 k<0 + weights 非负校验缺失** [P2] [rrf_fusion.py:27-31] — 已修复: k>=0 + all(w>=0 for w in weights)
- [x] **[Review][Patch] P6: QdrantAdapter.search_sparse() 无保护 dict 键访问** [P2] [qdrant_adapter.py:147-149] — 已修复: ValidationError 替代 raw KeyError
- [x] **[Review][Patch] P7: Collection 创建未自动配置 sparse_vectors_config** [P0] [collection_manager.py:73] — 已修复: create_collection 默认 SparseVectorParams()

#### Defer（已知设计 / 非本 Story 引入）

- [x] **[Review][Defer] D1: search_sparse 异常静默吞没** [vector_storage.py:210-212] — 故事明文设计决策
- [x] **[Review][Defer] D2: L3VectorPort.search_sparse 返回 list[dict] 无结构化契约** [l3_vector.py:120] — 架构层面，需单独 Story
- [x] **[Review][Defer] D3: search_sparse filter 无 Range 支持** [vector_storage.py:200-201] — 故事已文档化已知限制
- [x] **[Review][Defer] D4: httpx.Client 并发不安全** [sparse_search_service.py:74] — 既存于 DenseSemanticSearchService
- [x] **[Review][Defer] D5: DenseSearchResult 未迁移为 SearchResult 别名** [dense_search_service.py:17-28] — 故事中明确后续迁移

#### Dismiss（误报 / 已修复）

- [x] ~~get_event_loop() 废弃写法~~ — `acf955d3` 已修复
- [x] ~~embed_sparse[0] 无保护 IndexError~~ — API 保证非空返回

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查

---

**故事版本/Story Version:** v2.0.0
**创建日期/Created:** 2026-06-04
**最后更新/Last Updated:** 2026-06-05
**更新说明/Description:**
- v2.0.0: **Story 3-1b 实施完成** — Task 0-7 全部完成，118 测试通过 + 1 E2E skipped
  - Task 0: SDD 规范定义（SearchResult/EmbeddingResult TypedDict、Gherkin 验收测试）
  - Task 1: RRF 融合算法（src/domain/services/rrf_fusion.py，21 单元测试）
  - Task 2: Bm25SparseSearchService（src/application/services/sparse_search_service.py，19 单元测试）
  - Task 3: HybridSearchService（src/application/services/hybrid_search_service.py，12 单元测试）
  - Task 4: 索引管线扩展（generate_embedding 双向量 + index_document 真实 upsert，8+11 测试）
  - Task 5: Composition Root 注册（sparse_search_service + hybrid_search_service）
  - Task 6: 架构约束验证（9 架构测试全部通过）
  - Task 7: 集成测试 + 端到端验收（7 集成测试通过）
- v1.1.0: 文档审查修订（5轮迭代审查，修正P0/P1/P2共40+项问题）
  - P0: 方法签名对齐 DenseSemanticSearchService（参数顺序/tenant_id/异常类型）
  - P0: SearchResult.id 类型修正为 str | int（对齐 Qdrant ScoredPoint）
  - P0: generate_embedding 返回类型变更级联影响（EmbeddingResult + flow 调用链）
  - P1: embed_sparse 批量接口调用模式明确
  - P1: 领域异常契约/Task 依赖图/性能测试方法论补充
  - P2: 依赖方向矩阵 interfaces 行修正/模板版本更新至 v2.8.0
  - P2: RRF payload 取首次出现行为修正/Elasticsearch rank_constant 声明修正
- v1.0.0: 创建故事文件（遵循 SDD+TDD 融合模式模板 v2.7.0）
