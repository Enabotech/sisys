# Story 3.1a: Dense 语义检索

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 分析师,
**I want** 系统执行 Dense 语义检索（bge-m3 嵌入，余弦相似度），
**So that** 支持语义相似度检索，理解查询的深层含义。

### 业务价值

本 Story 是 Epic 3（智能检索与知识发现）价值组的第一部分，在 Story 1.6（Qdrant 向量存储层）基础上实现 Dense 语义检索核心功能。作为混合检索的基础，Dense 检索承担以下关键职责：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **查询嵌入生成** | 将用户查询文本转换为 1024 维向量（bge-m3） | 延迟 P95<50ms |
| **语义相似度检索** | 基于向量余弦相似度的 Top-K 文档检索 | 检索延迟 P95<200ms（初检） |
| **Payload 过滤** | 支持元数据条件过滤（业务域/时间范围等） | 过滤条件准确率 100% |
| **混合检索基座** | 为 Story 3.1b（BM25+RRF 融合）提供 Dense 检索通道 | 与 BM25 双路召回协同 |
| **多租户隔离** | 按 Collection 分离不同租户/业务的向量数据 | Collection 级别访问控制 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 3: 智能检索与知识发现，Story 3.1a

**覆盖 FR:**
- FR-SR-01: 混合检索（Dense bge-m3 + BM25 稀疏检索），双路召回
- NFR-PERF-01: 检索延迟 P95<800ms（MVP 目标）

**依赖关系:**
- 前置依赖: Epic 1 Story 1.6（Qdrant 向量存储层）✅ 已完成
- 后续Story: Story 3.1b（BM25 稀疏检索 + RRF 融合）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 查询嵌入生成（bge-m3）

**Given** 用户输入检索查询文本
**When** 系统执行 Dense 语义检索
**Then** 使用 bge-m3 模型生成查询嵌入向量（1024 维）
**And** 嵌入生成延迟 P95<50ms

**验证标准/Validation Criteria:**
- [ ] EmbeddingServicePort 接口定义（`src/domain/ports/embedding_service.py`）
  - 方法: `encode_text(text: str) -> list[float]`（文本→嵌入向量）
  - 方法: `encode_texts(texts: list[str]) -> list[list[float]]`（批量编码）
  - **注意:** 当前 `src/infrastructure/external_services/embedding/` 目录为空，bge-m3 实现待新建
- [ ] BGE3EmbeddingService 实现（`src/infrastructure/external_services/embedding/bge3_embedding_service.py`）
  - 使用 `sentence-transformers` 库加载 bge-m3 模型
  - 模型加载懒初始化（首次调用时加载）
  - 向量维度固定 1024（bge-m3 规范）
  - **依赖:** 需在 `pyproject.toml` 添加 `sentence-transformers` 依赖
- [ ] 嵌入生成单元测试（100 条查询，平均延迟<50ms）

### AC-2: Dense 语义检索（Qdrant + Cosine Similarity）

**Given** 查询嵌入向量已生成
**When** 系统执行 Dense 语义检索
**Then** 在 Qdrant Collection 中执行余弦相似度检索（Top-K）
**And** 检索延迟 P95<200ms（初检，不含 RRF 融合）
**And** 返回结构化 SearchResult 列表

**验证标准/Validation Criteria:**
- [ ] DenseRetrievalService 接口定义（`src/domain/services/dense_retrieval_service.py`）
  - 方法: `search(query: str, collection: str, limit: int = 10, filter_payload: dict = None) -> list[SearchResult]`
  - **架构决策:** 放置在 `domain/services/` 因为它是核心业务编排逻辑（embedding + vector search 协调）
- [ ] DenseRetrievalService 实现
  - 调用 EmbeddingService 生成查询向量
  - 调用 L3VectorPort.search() 执行 Qdrant 检索
  - 支持 Payload 过滤条件
  - **字段映射:** result["payload"]["document_id"] → SearchResult.document_id, result["payload"]["chunk_id"] → SearchResult.chunk_id
  - 返回结构化 SearchResult 列表
- [ ] Dense 检索集成测试（1000 向量点，Top-10 检索，延迟 P95<200ms）

### AC-3: 检索结果结构化输出

**Given** Dense 检索返回原始结果
**When** 系统处理检索结果
**Then** 输出结构化 SearchResult 列表，包含 id/score/payload/document_id/chunk_id
**And** 支持按 score 降序排列

**验证标准/Validation Criteria:**
- [ ] SearchResult 值对象实现（`src/domain/value_objects/search_result.py`）
  - frozen=True（不可变）
  - 字段验证：score 范围 [0.0, 1.0]
- [ ] 检索结果排序逻辑实现（按 score 降序）
- [ ] 空结果处理（返回空列表，不抛异常）

### AC-4: Payload 过滤能力

**Given** 用户指定过滤条件
**When** 执行 Dense 检索
**Then** 仅返回符合 Payload 过滤条件的向量点

**验证标准/Validation Criteria:**
- [ ] Payload 过滤数据结构定义（`filter_payload: dict | None`）
  - 支持字段: business_domain, document_id, created_at 范围等
  - 示例: `{"business_domain": "finance", "created_at": {"gte": "2026-01-01"}}`
- [ ] L3VectorPort.search() filter_payload 参数传递验证
- [ ] Payload 过滤集成测试（多条件组合）

### AC-5: 架构约束验证测试就绪

**Given** Dense 语义检索已实现
**When** 运行架构约束验证测试
**Then** 领域层不依赖任何外部嵌入实现
**And** 依赖方向正确（应用层→领域层→基础设施层）
**And** Ruff 检查通过（严重错误=0）
**And** MyPy 类型检查通过（错误率<5%）

**验证标准/Validation Criteria:**
- [ ] 领域层无 sentence-transformers 导入验证（扫描 `src/domain/` 目录）
- [ ] 依赖方向测试通过（使用 `import-linter`）
- [ ] Ruff 检查通过（0 错误）
- [ ] MyPy 类型检查通过（0 问题）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] DenseSearchInitiated 事件定义（`src/domain/events/dense_search_events.py`）
  - **说明:** 如果检索是同步响应型操作（非异步长流程），此事件可能冗余。检查是否有异步监听器需要
- [ ] DenseSearchCompleted 事件定义
- [ ] 事件使用标准库实现（dataclass + Enum），禁止在领域层依赖 Pydantic
- [ ] **决策点:** 如果使用同步检索（直接返回结果），建议删除此事件定义，简化架构

#### 数据模型 (Data Models)
- [ ] SearchResult 值对象定义（`src/domain/value_objects/search_result.py`）
  - 字段: id, score, payload, document_id, chunk_id
  - frozen=True, 字段验证
- [ ] EmbeddingRequest/EmbeddingResponse 定义（如需要）

#### 统一端口定义注册与管理 (Port Contract)
- [ ] EmbeddingServicePort 接口定义（`src/domain/ports/embedding_service.py`）
  - 方法: `encode_text(text: str) -> list[float]`
  - 方法: `encode_texts(texts: list[str]) -> list[list[float]]`
  - 位置: 领域层（Protocol），遵循六边形架构
- [ ] DenseRetrievalService 接口定义（`src/domain/services/dense_retrieval_service.py`）
  - 方法: `search(query: str, collection: str, limit: int, filter_payload: dict | None) -> list[SearchResult]`
  - **架构决策:** 放置在 `domain/services/` 因为它是核心业务逻辑（编排 embedding + vector search）
- [ ] 端口注册中心更新（`src/composition_root.py`）
  - 添加 `embedding_service` 端口（BGE3EmbeddingService 实现）
  - 添加 `dense_retrieval_service` 端口
  - **注意:** `l3_vector` 端口已存在（行 347-355），无需重复注册
- [ ] 端口契约测试（`tests/unit/domain/ports/test_embedding_service_port.py`）

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_dense_semantic_search.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_dense_semantic_search.py`（BDD 步骤实现）
- [ ] 运行验收测试，确认失败（🔴 红阶段验证）

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

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | EmbeddingService | 查询嵌入生成、批量编码、延迟 | `tests/unit/infrastructure/test_bge3_embedding_service.py` | Task 1 |
| **TDD 单元测试** | DenseRetrievalService | 检索编排、结果处理、过滤 | `tests/unit/infrastructure/test_dense_retrieval_service_impl.py` | Task 2 |
| **TDD 单元测试** | SearchResult | 值对象验证、score 范围 | `tests/unit/domain/value_objects/test_search_result.py` | Task 3 |
| **端口契约测试** | Port Contracts | EmbeddingServicePort/DenseRetrievalService 接口契约 | `tests/contracts/test_port_contract_embeddingService.py` | Task 0/1 |
| **集成测试** | Dense 检索端到端 | 完整检索流程（嵌入→检索→结果） | `tests/integration/test_integration_dense_search.py` | Task 4 |
| **架构验证测试** | 领域层零依赖 | 领域层无外部嵌入库导入 | `tests/unit/architecture/test_arch_dense_search.py` | Task 5 |
| **验收测试** | Gherkin 场景 | 业务价值验收 | `tests/acceptance/test_acceptance_dense_semantic_search.feature` | Task 0 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁：

- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application --cov-fail-under=85`）- **P1 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain --cov-fail-under=90`）- **P1 阻断门禁**
- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration`）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 性能要求
- [ ] 嵌入生成延迟 P95<50ms
- [ ] Dense 检索延迟 P95<200ms（初检）
- [ ] 并发检索≥50

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 查询嵌入生成（bge-m3） | Task 1 | EmbeddingServicePort + BGE3EmbeddingService | `test_embedding_service.py` |
| AC-2 | Dense 语义检索 | Task 2 | DenseRetrievalService + L3VectorPort 集成 | `test_dense_retrieval_service.py` |
| AC-3 | 检索结果结构化输出 | Task 3 | SearchResult 值对象 | `test_search_result.py` |
| AC-4 | Payload 过滤能力 | Task 2 | filter_payload 参数处理 | `test_dense_retrieval_service.py` |
| AC-5 | 架构约束验证 | Task 5 | 领域层零依赖验证 | `test_architecture_constraints.py` |
| AC-1~AC-4 | Dense 检索端到端 | Task 4 | 完整流程集成测试 | `test_integration_dense_search.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-5

> **目的：** 在进入代码实现前，明确 Schema、数据模型、端口契约、验收标准与六边形架构边界。

- [ ] Subtask: 定义 DenseSearchInitiated / DenseSearchCompleted 领域事件
  - **注意:** 如果检索是同步响应型操作（直接返回结果），此事件可能冗余。建议先实现核心功能，事件作为可选扩展
- [ ] Subtask: 定义 SearchResult 值对象（frozen=True，score 验证）
- [ ] Subtask: 定义 EmbeddingServicePort 接口（encode_text / encode_texts）
- [ ] Subtask: 定义 DenseRetrievalService 接口（search 方法）
- [ ] Subtask: 更新端口注册中心（composition_root.py）
- [ ] Subtask: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_dense_semantic_search.feature`
- [ ] Subtask: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_dense_semantic_search.py`
- [ ] Subtask: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 查询嵌入生成（bge-m3）

**关联 AC:** AC-1

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：EmbeddingServicePort 接口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_embedding_service_port.py`（接口类型检查、方法签名验证） |
| 🟢 绿 | 实现 `EmbeddingServicePort` Protocol 接口 |
| 🔄 重构 | 添加类型注解、方法文档字符串 |

- [ ] Subtask: 🔴 红 — 编写 EmbeddingServicePort 接口失败测试
- [ ] Subtask: 🟢 绿 — 实现 EmbeddingServicePort 接口
- [ ] Subtask: 🔄 重构 — 优化接口定义

#### TDD 循环 B：BGE3EmbeddingService 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_bge3_embedding_service.py`（单条/批量编码、延迟验证、模型加载） |
| 🟢 绿 | 实现 `BGE3EmbeddingService` 类最小代码 |
| 🔄 重构 | 添加懒初始化、异常处理、缓存优化 |

- [ ] Subtask: 🔴 红 — 编写 BGE3EmbeddingService 失败测试
- [ ] Subtask: 🟢 绿 — 实现 BGE3EmbeddingService 最小代码
- [ ] Subtask: 🔄 重构 — 优化 BGE3EmbeddingService 代码

**完成标准/Definition of Done:**
- [ ] EmbeddingServicePort 和 BGE3EmbeddingService 实现完成
- [ ] TDD 循环全部通过
- [ ] 嵌入生成延迟 P95<50ms 验证

---

### Task 2: Dense 语义检索服务

**关联 AC:** AC-2, AC-4

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：DenseRetrievalService 接口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_dense_retrieval_service_interface.py`（接口类型检查） |
| 🟢 绿 | 实现 `DenseRetrievalService` Protocol 接口 |
| 🔄 重构 | 添加类型注解、方法签名 |

- [ ] Subtask: 🔴 红 — 编写 DenseRetrievalService 接口失败测试
- [ ] Subtask: 🟢 绿 — 实现 DenseRetrievalService 接口
- [ ] Subtask: 🔄 重构 — 优化接口定义

#### TDD 循环 B：DenseRetrievalService 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_dense_retrieval_service_impl.py`（检索编排、过滤、结果处理） |
| 🟢 绿 | 实现 `DenseRetrievalServiceImpl` 类最小代码 |
| 🔄 重构 | 添加 EmbeddingService 调用、L3VectorPort 集成、异常处理 |

- [ ] Subtask: 🔴 红 — 编写 DenseRetrievalServiceImpl 失败测试
- [ ] Subtask: 🟢 绿 — 实现 DenseRetrievalServiceImpl 最小代码
- [ ] Subtask: 🔄 重构 — 优化 DenseRetrievalServiceImpl 代码

**完成标准/Definition of Done:**
- [ ] DenseRetrievalService 接口和实现完成
- [ ] TDD 循环全部通过
- [ ] Payload 过滤验证通过

---

### Task 3: 检索结果值对象

**关联 AC:** AC-3

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：SearchResult 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_search_result.py`（字段验证、frozen 约束、score 范围） |
| 🟢 绿 | 实现 `SearchResult` dataclass 最小代码 |
| 🔄 重构 | 添加类型注解、字段验证、score 范围检查 |

- [ ] Subtask: 🔴 红 — 编写 SearchResult 失败测试
- [ ] Subtask: 🟢 绿 — 实现 SearchResult 最小代码
- [ ] Subtask: 🔄 重构 — 优化 SearchResult 代码

**完成标准/Definition of Done:**
- [ ] SearchResult 值对象实现完成
- [ ] TDD 循环通过
- [ ] score 范围 [0.0, 1.0] 验证

---

### Task 4: Dense 检索端到端集成测试

**关联 AC:** AC-1 ~ AC-4

> **性质说明：** 本 Task 是集成测试，验证完整的 Dense 检索流程。

#### 集成测试实现

- [ ] Subtask: 创建 `tests/integration/test_integration_dense_search.py`
- [ ] Subtask: 实现嵌入生成→Qdrant 检索→结果处理完整流程测试
- [ ] Subtask: 实现 Payload 过滤组合测试
- [ ] Subtask: 实现性能基准测试（P95<200ms）
- [ ] Subtask: 实现多租户隔离验证（不同 Collection 数据隔离）

**完成标准/Definition of Done:**
- [ ] 所有集成测试通过
- [ ] 检索延迟 P95<200ms 验证
- [ ] 基础设施层覆盖率≥75%

---

### Task 5: 架构约束验证测试

**关联 AC:** AC-5

> **性质说明：** 本 Task 验证 Dense 语义检索实现是否符合六边形架构约束。

#### 架构验证测试实现

- [ ] Subtask: 创建 `tests/unit/architecture/test_arch_dense_search.py`
- [ ] Subtask: 实现领域层零外部嵌入库导入验证（扫描 `src/domain/` 目录）
- [ ] Subtask: 实现依赖方向验证（使用 `import-linter`）
- [ ] Subtask: 运行 Ruff 检查（0 错误）
- [ ] Subtask: 运行 MyPy 类型检查（0 问题）

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过
- [ ] 测试输出清晰的合规报告

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **六层存储架构:** L3 向量存储层（Qdrant 1.7+）存储嵌入向量、混合检索 payload
- **向量维度:** 1024 维（bge-m3 嵌入模型），COSINE 相似度度量
- **检索延迟预算:** P95<200ms（初检）+ P95<250ms（精排）+ P95<50ms（融合）= P95<500ms 总预算
- **延迟预算分解:** 嵌入生成<50ms + Qdrant 检索<200ms = 总计<250ms
- **领域层零依赖:** 领域层仅定义接口，不依赖任何 bge-m3/sentence-transformers 实现细节

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 决策 4 (ADR-004): 六层存储架构

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **bge-m3（BAAI/bge-m3）** | 中英文多语言支持、1024 维向量、高语义相关性 | 模型体积大（~2GB） | ✅ 9/10 |
| text-embedding-3-large | OpenAI 官方、API 简单 | 英文为主、中文支持弱 | 6/10 |
| Jina AI Embeddings | 开源、中文优化 | 向量维度较低（1024） | 7/10 |

**决策理由：**
1. bge-m3 由 BAAI 开源，中英文多语言支持优秀
2. 1024 维向量与 Qdrant Collection 配置兼容（COSINE 度量）
3. sentence-transformers 库支持本地加载，无 API 依赖
4. 模型懒加载避免启动时阻塞

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── events/
│   │   │   └── dense_search_events.py    # DenseSearchInitiated/Completed 事件
│   │   ├── ports/
│   │   │   └── embedding_service.py       # EmbeddingServicePort 接口
│   │   ├── services/
│   │   │   └── dense_retrieval_service.py # DenseRetrievalService 接口（领域层）
│   │   └── value_objects/
│   │       └── search_result.py          # SearchResult 值对象
│   └── infrastructure/
│       └── external_services/
│           └── embedding/
│               ├── __init__.py
│               └── bge3_embedding_service.py # BGE3EmbeddingService 实现
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── ports/
│   │   │   │   └── test_embedding_service_port.py
│   │   │   ├── services/
│   │   │   │   └── test_dense_retrieval_service.py
│   │   │   └── value_objects/
│   │   │       └── test_search_result.py
│   │   ├── infrastructure/
│   │   │   ├── test_bge3_embedding_service.py
│   │   │   └── test_dense_retrieval_service_impl.py
│   │   └── architecture/
│   │       └── test_arch_dense_search.py
│   ├── integration/
│   │   └── test_integration_dense_search.py
│   └── acceptance/
│       ├── test_acceptance_dense_semantic_search.feature
│       └── test_acceptance_dense_semantic_search.py
└── docs/
    └── architecture/
        └── dense_semantic_search_guide.md # Dense 检索实施指南
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.6-Qdrant Vector Layer](./1-6-qdrant-vector-layer.md)

**关键学习/Key Learnings:**
1. **配置模式复用** — `XxxConfig` + `from_env()` 模式，Story 1.4/1.5/1.6 已建立
2. **懒初始化连接池** — 首次调用时创建客户端，避免启动时连接失败阻塞业务
3. **L3VectorPort 接口设计** — 领域层定义 Protocol，基础设施层实现（QdrantAdapter）
4. **Collection 命名规范** — `sisys:{collection_type}:{namespace}`（如 `sisys:documents:finance`）
5. **架构约束验证** — 领域层零外部依赖是硬约束，必须在架构验证测试中覆盖

**应用到本故事/Applied to This Story:**
- [ ] BGE3EmbeddingService 采用懒初始化模式（首次调用时加载模型）
- [ ] EmbeddingServicePort 定义在领域层（Protocol），实现在基础设施层
- [ ] DenseRetrievalService 调用 L3VectorPort.search() 执行 Qdrant 检索
- [ ] 架构约束测试验证领域层无 sentence-transformers 导入

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Qwen Code |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-05-31 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前置 Story** | `_bmad-output/implementation-artifacts/stories/1-6-qdrant-vector-layer.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] Story 需求从 `epics_v1.0.md` 提取
- [ ] 架构约束从 `architecture.md` 提取
- [ ] 前一个故事学习经验整合
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-1a-dense-semantic-search.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/events/dense_search_events.py` - DenseSearchInitiated/Completed 事件
- `src/domain/value_objects/search_result.py` - SearchResult 值对象
- `src/domain/ports/embedding_service.py` - EmbeddingServicePort 接口
- `src/domain/services/dense_retrieval_service.py` - DenseRetrievalService 接口
- `src/infrastructure/external_services/embedding/bge3_embedding_service.py` - BGE3EmbeddingService 实现
- `tests/unit/domain/ports/test_embedding_service_port.py` - 端口契约测试
- `tests/unit/domain/services/test_dense_retrieval_service.py` - 服务接口测试
- `tests/unit/domain/value_objects/test_search_result.py` - 值对象测试
- `tests/unit/infrastructure/test_bge3_embedding_service.py` - 嵌入服务实现测试
- `tests/unit/infrastructure/test_dense_retrieval_service_impl.py` - 检索服务实现测试
- `tests/integration/test_integration_dense_search.py` - 集成测试
- `tests/unit/architecture/test_arch_dense_search.py` - 架构验证测试
- `tests/acceptance/test_acceptance_dense_semantic_search.feature` - Gherkin 场景
- `tests/acceptance/test_acceptance_dense_semantic_search.py` - BDD 步骤实现

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.1a |
| **Story Key** | 3-1a-dense-semantic-search |
| **File** | `_bmad-output/implementation-artifacts/stories/3-1a-dense-semantic-search.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 价值组 1: 智能检索与溯源 |
| **优先级** | P0（关键路径） |
| **覆盖 FR** | FR-SR-01（混合检索 - Dense 通道）, NFR-PERF-01（检索延迟） |

### 完成总结 Completion Summary

1. [ ] All tasks defined 所有任务定义完成（Task 0-5，含 SDD 规范 + TDD 循环）
2. [ ] All acceptance criteria specified 所有验收标准已定义（AC-1 ~ AC-5）
3. [ ] Architecture constraints extracted 架构约束已提取（六层存储、延迟预算、零依赖）
4. [ ] Previous story learnings integrated 前一个故事学习经验已整合（懒初始化、接口分离）
5. [ ] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 本 Story 为新建，暂无审查修复记录

---

## 📚 相关文档 Related Documents

| 文档 | 说明 |
|------|------|
| [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) | Epic 3 Story 3.1a 完整定义 |
| [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) | 六层存储架构、L3 向量存储层设计 |
| [Story 1.6-Qdrant Vector Layer](./1-6-qdrant-vector-layer.md) | Qdrant 向量存储层实现（前置依赖） |
| [Story 3.1b-BM25 Sparse Search](./3-1b-bm25-sparse-search-rrf-fusion.md) | BM25 稀疏检索 + RRF 融合（后续 Story） |
| [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) | SDD+TDD 融合开发模式指南 |
| [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md) | SDD+TDD 实施检查清单 |

---

**故事版本/Story Version:** v0.0.0
**创建日期/Created:** 2026-05-31
**最后更新/Last Updated:** 2026-05-31
**更新说明/Description:**
- v0.0.0: 创建故事文件
