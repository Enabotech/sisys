# Story 3-1a: Dense 语义检索

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 分析师,
**I want** 系统执行 Dense 语义检索（bge-m3 嵌入，余弦相似度）,
**So that** 支持语义相似度检索，理解查询的深层含义。

### 业务价值

本 Story 是 Epic 3（智能检索与知识发现）的第一个故事，实现混合检索管道的基础：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **Dense 语义检索** | 基于 bge-m3 嵌入的语义相似度检索 | P95<200ms，支持 payload 过滤 |
| **bge-m3 嵌入生成** | 1024 维语义向量生成 | P95<50ms，支持批量编码 |
| **检索流水线基座** | 为 Story 3.1b/3.4/3.9 提供检索基础 | 与现有 Qdrant Infrastructure 集成 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 3: 智能检索与知识发现

**覆盖 FR:**
- FR-SR-01: 混合检索（Dense bge-m3 + BM25 稀疏检索）
- NFR-PERF-01: 检索延迟 P95<800ms（MVP）→<200ms（本 Story 目标）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: bge-m3 嵌入生成

**Given** 用户输入查询文本
**When** 系统执行 Dense 检索
**Then** 使用 bge-m3 生成 1024 维查询嵌入
**And** 嵌入生成延迟 P95<50ms

**验证标准/Validation Criteria:**
- [ ] EmbeddingModelPort 领域协议定义（`src/domain/ports/embedding_model.py`）
- [ ] BGEM3EmbeddingService 实现（`src/infrastructure/external_services/embedding/bge_m3_embedding_service.py`）
- [ ] BGEConfig 配置模型（`src/infrastructure/config/embedding.py`）
- [ ] 单文本嵌入测试（1024 维向量输出）
- [ ] 批量嵌入测试（batch size=32）
- [ ] 嵌入维度验证（1024 维）

### AC-2: Dense 语义检索（余弦相似度）

**Given** 已索引的记忆数据在 Qdrant 中
**When** 用户执行语义检索查询
**Then** 在 Qdrant 中执行余弦相似度检索
**And** 检索延迟 P95<200ms（初检）
**And** 返回 Top-K 结果（默认 K=10）

**验证标准/Validation Criteria:**
- [ ] DenseRetrievalService 应用层服务（`src/application/services/dense_retrieval_service.py`）
- [ ] QdrantMemoryVectorStorage 支持 EmbeddingModelPort 注入
- [ ] Payload 过滤支持（元数据过滤）
- [ ] 检索延迟 P95<200ms 验证
- [ ] 余弦相似度排序验证

### AC-3: 多租户隔离

**Given** 多用户并发检索场景
**When** 执行语义检索
**Then** 按 owner_id/memory_type 过滤结果
**And** 并发检索>=50

**验证标准/Validation Criteria:**
- [ ] owner_id 过滤测试
- [ ] memory_type 过滤测试
- [ ] 并发检索>=50 负载测试

### AC-4: 架构约束验证

**Given** 实现完成后的代码库
**When** 运行架构验证测试
**Then** 领域层不依赖任何外部框架（qdrant-client/sentence-transformers）
**And** 依赖方向正确（infrastructure→application→domain）
**And** Ruff 检查通过
**And** MyPy 类型检查通过

**验证标准/Validation Criteria:**
- [ ] 领域层无 qdrant-client 导入扫描
- [ ] 领域层无 sentence-transformers 导入扫描
- [ ] import-linter 依赖方向验证
- [ ] Ruff 检查通过（0 错误）
- [ ] MyPy 类型检查通过（0 问题）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写推迟到单独 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 端口契约 (Port Contracts)
- [ ] EmbeddingModelPort 领域协议定义（`src/domain/ports/embedding_model.py`）
  - 方法: `async embed(texts: list[str]) -> list[list[float]]`
  - 属性: `embedding_dim: int`（返回 1024）
  - 领域层零依赖（仅用 abc + typing）
- [ ] 端口注册至 `src/domain/ports/registry.py`（PortSpec 元数据）
- [ ] 端口解析至 `src/domain/ports/resolver.py`
- [ ] 端口契约测试 `tests/contracts/test_port_contract_embedding_model.py`

#### 配置模型 (Configuration Models)
- [ ] BGEConfig 定义（`src/infrastructure/config/embedding.py`）
  - 字段: `model_name: str = "BAAI/bge-m3"`, `device: str`, `normalize_embeddings: bool`
  - 字段: `batch_size: int = 32`, `max_length: int = 512`
  - 方法: `from_env() -> BGEConfig`（从环境变量读取）

#### 数据模型 (Data Models)
- [ ] 无新增数据模型（复用 VectorPoint from Story 1.6）

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_dense_semantic_search.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_dense_semantic_search.py`
- [ ] 覆盖场景:
  - bge-m3 嵌入生成（1024 维验证）
  - Dense 语义检索（余弦相似度）
  - Payload 过滤（owner_id/memory_type）
  - 性能要求（P95<200ms，P95<50ms）
  - 多租户隔离
  - 架构约束验证

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（🔴 红阶段验证）
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
| **TDD 单元测试** | BGEM3EmbeddingService | 嵌入生成、维度验证 | `test_bge_m3_service.py` | Task 2 |
| **TDD 单元测试** | DenseRetrievalService | 检索编排、过滤构建 | `test_dense_retrieval_service.py` | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_dense_semantic_search.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_dense_semantic_search.py` | Task 0 |
| **TDD 契约测试** | EmbeddingModelPort | 端口注册、版本、兼容性 | `test_port_contract_embedding_model.py` | Task 0 |
| **SDD 架构验证** | 六边形架构约束 | 领域层零外部依赖 | `test_arch_dense_retrieval.py` | Task 5 |
| **集成测试** | Qdrant + bge-m3 | 端到端检索流程 | `test_integration_dense_retrieval.py` | Task 4 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration`）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **无 P0/P1 级别问题**
- [ ] **预提交 Hooks 通过**（`poetry run pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**关键约束：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续5次运行无随机失败
- [ ] BDD 步骤函数使用 `event_loop.run_until_complete()` 运行 async（不用 `@pytest.mark.asyncio`）
- [ ] asyncio.Lock 使用**类变量**而非实例变量

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | bge-m3 嵌入生成（1024维，P95<50ms） | Task 1, Task 2 | Port定义/Config/Service实现 | `test_bge_m3_service.py` |
| AC-2 | Dense 语义检索（余弦相似度，P95<200ms） | Task 3, Task 4 | Service编排/集成测试 | `test_dense_retrieval_service.py` |
| AC-3 | 多租户隔离（owner_id/memory_type过滤，并发>=50） | Task 3, Task 4 | 过滤逻辑/负载测试 | `test_integration_dense_retrieval.py` |
| AC-4 | 架构约束验证（领域层零外部依赖） | Task 5 | 架构验证测试 | `test_arch_dense_retrieval.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4

> **目的：** 在进入代码实现前，明确端口契约、配置模型、验收标准与六边形架构边界。

#### TDD 循环 [A]：端口契约与配置模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/contracts/test_port_contract_embedding_model.py`（端口契约测试） |
| 🟢 绿 | 实现 `src/domain/ports/embedding_model.py`（EmbeddingModelPort） |
| 🔄 重构 | 添加 PortSpec 注册、运行契约测试 |

- [ ] Subtask 0.1: 🔴 红 — 编写 EmbeddingModelPort 契约测试框架
- [ ] Subtask 0.2: 🟢 绿 — 实现 EmbeddingModelPort 协议（`src/domain/ports/embedding_model.py`）
- [ ] Subtask 0.3: 🟢 绿 — 实现 BGEConfig（`src/infrastructure/config/embedding.py`）
- [ ] Subtask 0.4: 🔄 重构 — 注册 PortSpec、验证契约测试通过

#### TDD 循环 [B]：BDD 验收测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_dense_semantic_search.feature`（Gherkin 场景） |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_dense_semantic_search.py`（BDD 步骤实现） |
| 🔄 重构 | 验证 BDD 场景覆盖完整性 |

- [ ] Subtask 0.5: 🔴 红 — 编写 Gherkin 验收测试场景
- [ ] Subtask 0.6: 🟢 绿 — 实现 BDD 步骤函数（使用 `event_loop.run_until_complete()`）
- [ ] Subtask 0.7: 🔄 重构 — 运行验收测试，确认失败（红阶段验证）

**完成标准/Definition of Done:**
- [ ] EmbeddingModelPort 协议定义完毕
- [ ] BGEConfig 配置模型定义完毕
- [ ] Gherkin 验收测试场景完备
- [ ] BDD 步骤函数实现完毕
- [ ] 所有测试运行失败（🔴 红阶段验证）

---

### Task 1: EmbeddingModelPort + BGEConfig

**关联 AC:** AC-1

> **目的：** 定义领域层嵌入协议和配置模型

#### TDD 循环 [A]：EmbeddingModelPort 协议

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_embedding_model_port.py` |
| 🟢 绿 | 实现 `src/domain/ports/embedding_model.py` |
| 🔄 重构 | 添加 PortSpec 注册、类型注解 |

- [ ] Subtask 1.1: 🔴 红 — 编写 EmbeddingModelPort 单元测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 EmbeddingModelPort（领域层零依赖）
- [ ] Subtask 1.3: 🔄 重构 — PortSpec 注册、ruff + mypy 通过

#### TDD 循环 [B]：BGEConfig 配置

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/config/test_embedding_config.py` |
| 🟢 绿 | 实现 `src/infrastructure/config/embedding.py` |
| 🔄 重构 | 添加 from_env() 方法、类型注解 |

- [ ] Subtask 1.4: 🔴 红 — 编写 BGEConfig 单元测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 BGEConfig（参考 RedisConfig/PostgreSQLConfig 模式）
- [ ] Subtask 1.6: 🔄 重构 — 验证 from_env()、环境变量解析

**完成标准/Definition of Done:**
- [ ] EmbeddingModelPort 实现完成
- [ ] BGEConfig 实现完成
- [ ] TDD 循环全部通过
- [ ] 领域层覆盖率≥90%

---

### Task 2: BGEM3EmbeddingService 实现

**关联 AC:** AC-1

> **目的：** 实现 bge-m3 嵌入服务（使用 sentence-transformers）

#### TDD 循环 [A]：BGEM3EmbeddingService

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/embedding/test_bge_m3_service.py` |
| 🟢 绿 | 实现 `src/infrastructure/external_services/embedding/bge_m3_embedding_service.py` |
| 🔄 重构 | 添加模型缓存、错误处理、类型注解 |

- [ ] Subtask 2.1: 🔴 红 — 编写 BGEM3EmbeddingService 单元测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 BGEM3EmbeddingService（懒加载模型）
- [ ] Subtask 2.3: 🔄 重构 — 模型缓存、异步优化、ruff + mypy 通过

#### TDD 循环 [B]：嵌入维度与性能验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写性能测试（嵌入延迟 P95<50ms） |
| 🟢 绿 | 优化嵌入服务性能 |
| 🔄 重构 | 性能基准验证 |

- [ ] Subtask 2.4: 🔴 红 — 编写嵌入性能测试
- [ ] Subtask 2.5: 🟢 绿 — 性能优化（批量编码、缓存）
- [ ] Subtask 2.6: 🔄 重构 — P95<50ms 性能验证

**完成标准/Definition of Done:**
- [ ] BGEM3EmbeddingService 实现完成
- [ ] 嵌入生成 P95<50ms
- [ ] 1024 维输出验证
- [ ] 基础设施层覆盖率≥75%

---

### Task 3: DenseRetrievalService + QdrantMemoryVectorStorage 集成

**关联 AC:** AC-2, AC-3

> **目的：** 实现检索编排服务，集成嵌入服务与 Qdrant 存储

#### TDD 循环 [A]：DenseRetrievalService

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_dense_retrieval_service.py` |
| 🟢 绿 | 实现 `src/application/services/dense_retrieval_service.py` |
| 🔄 重构 — 添加过滤逻辑、错误处理 |

- [ ] Subtask 3.1: 🔴 红 — 编写 DenseRetrievalService 单元测试
- [ ] Subtask 3.2: 🟢 绿 — 实现 DenseRetrievalService
- [ ] Subtask 3.3: 🔄 重构 — owner_id/memory_type 过滤、ruff + mypy 通过

#### TDD 循环 [B]：QdrantMemoryVectorStorage 增强

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/test_qdrant_memory_vector_storage.py` |
| 🟢 绿 | 修改 `src/infrastructure/storage/qdrant/qdrant_memory_vector_storage.py` |
| 🔄 重构 — 支持 EmbeddingModelPort 注入 |

- [ ] Subtask 3.4: 🔴 红 — 编写 QdrantMemoryVectorStorage 增强测试
- [ ] Subtask 3.5: 🟢 绿 — 修改支持 EmbeddingModelPort（替换 _deterministic_embed）
- [ ] Subtask 3.6: 🔄 重构 — 异步嵌入支持、类型注解

**完成标准/Definition of Done:**
- [ ] DenseRetrievalService 实现完成
- [ ] QdrantMemoryVectorStorage 增强完成
- [ ] Payload 过滤功能正常
- [ ] 应用层覆盖率≥85%

---

### Task 4: 集成测试

**关联 AC:** AC-2, AC-3

> **目的：** 端到端验证 Dense 检索全流程

#### TDD 循环 [A]：集成测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_dense_retrieval.py` |
| 🟢 绿 | 验证端到端检索流程 |
| 🔄 重构 — 并发测试、性能基准 |

- [ ] Subtask 4.1: 🔴 红 — 编写集成测试（真实 Qdrant + bge-m3）
- [ ] Subtask 4.2: 🟢 绿 — 验证端到端流程通过
- [ ] Subtask 4.3: 🔄 重构 — 并发>=50 负载测试、P95<200ms 验证

**完成标准/Definition of Done:**
- [ ] 集成测试覆盖所有验收场景
- [ ] 并发检索>=50 通过
- [ ] 检索延迟 P95<200ms 验证
- [ ] 集成测试覆盖率≥70%

---

### Task 5: SDD 架构约束验证测试

**关联 AC:** AC-4

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**

#### 架构验证测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_arch_dense_retrieval.py` |
| 🟢 绿 | 验证架构约束 |
| 🔄 重构 — 生成架构合规报告 |

- [ ] Subtask 5.1: 🔴 红 — 编写架构验证测试
- [ ] Subtask 5.2: 🟢 绿 — 验证领域层零外部依赖
- [ ] Subtask 5.3: 🔄 重构 — import-linter 验证、依赖方向报告

**验证项：**
- [ ] 领域层无 qdrant-client 导入
- [ ] 领域层无 sentence-transformers 导入
- [ ] 依赖方向正确（infrastructure→application→domain）
- [ ] Ruff 检查通过
- [ ] MyPy 类型检查通过

**完成标准/Definition of Done:**
- [ ] 架构验证测试通过
- [ ] 领域层零外部依赖验证通过
- [ ] 架构层覆盖率≥85%

---

### Task 6: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_dense_semantic_search.feature` 收尾场景 |
| 🟢 绿 | 验证所有完成清单 |
| 🔄 重构 — 收敛场景命名、统一断言表达 |

- [ ] Subtask 6.1: 🔴 红 — 验证 src 完成清单的逐项确认
- [ ] Subtask 6.2: 🟢 绿 — 验证 tests/unit/integration/contracts/acceptance 完成清单
- [ ] Subtask 6.3: 🟢 绿 — 运行开发结束验收测试
- [ ] Subtask 6.4: 🔄 重构 — 运行 `pytest`、`ruff check`、`mypy` 收尾校验

**完成标准/Definition of Done:**
- [ ] src 完成清单已逐项验证确认
- [ ] tests 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters）、依赖倒置
- **设计约束:** 领域层零外部依赖（仅用 abc + typing）
- **接口治理:** 统一端口注册、PortSpec 元数据、Registry/Resolver/ContractGate
- **技术栈:** Python 3.11+, bge-m3 (1024-dim), Qdrant 1.7+, sentence-transformers, FlagEmbedding

### ⚠️ 端口位置说明

| 端口 | 故事假设路径 | 实际路径 |
|------|------------|---------|
| `L3VectorPort` | `src/domain/ports/l3_vector.py` | ✅ 正确 |
| `MemoryVectorPort` | 假设在 `src/domain/ports/` | ❌ 实际在 `src/application/ports/memory_vector_port.py` |
| `EmbeddingModelPort` | `src/domain/ports/embedding_model.py` | ❌ 待创建（本 Story） |

**说明:** `MemoryVectorPort` 位于应用层（而非领域层）是合理设计，因为记忆语义属于应用层关注点，不属于领域核心业务规则。本 Story 应保持此设计决策，在 `src/domain/ports/` 创建 `EmbeddingModelPort`（领域层协议）。

### 关键架构决策

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **BGEM3EmbeddingService** | 领域层零污染、插拔式嵌入 | 需额外依赖 sentence-transformers | ✅ 9/10 |
| 本地模型 vs 云端API | 本地：隐私、低延迟 | 本地：GPU资源需求 | - |
| 异步 vs 同步 | 异步：不阻塞事件循环 | 异步：复杂性增加 | 异步 ✅ |

**架构约束：sentence-transformers 在 FORBIDDEN_DOMAIN_IMPORTS**

`FORBIDDEN_DOMAIN_IMPORTS`（`tests/unit/architecture/test_hexagonal_architecture_constraints.py` 第46-88行）定义了领域层禁止导入的外部框架。当前列表中**不包含** `sentence-transformers`，但项目约束领域层零外部依赖，**禁止**在领域层（`src/domain/`）直接导入任何外部模型库。

- `EmbeddingModelPort` 协议定义在领域层，仅使用 `abc` + `typing`（✅ 符合约束）
- `BGEM3EmbeddingService` 实现位于 `infrastructure/external_services/embedding/`，可使用 sentence-transformers（✅ 符合约束）
- Task 5 架构验证需确保领域层无 sentence-transformers 导入

### ⚠️ 已知实现缺口（Dev 须知）

**缺口1：QdrantMemoryVectorStorage._deterministic_embed() 维度不匹配**

当前 `QdrantMemoryVectorStorage._deterministic_embed()` 返回 128 维向量，但 `VectorPoint` 模型强制验证 1024 维向量。这意味着：
- 当前 `index_memory()` 使用默认 `_deterministic_embed` 会导致 `VectorPoint.__post_init__` 抛出 `ValueError`
- **Dev 必须**：在 Task 3 修改 `QdrantMemoryVectorStorage`，使 `embed_fn` 类型支持 `EmbeddingModelPort`，或确保使用 1024 维嵌入函数

**缺口2：QdrantCollectionManager 默认 collection 维度**

创建 collection 时使用 `vector_size=1024`（bge-m3），需确保：
- 所有向量索引操作使用 1024 维向量
- 批量插入前验证向量维度

**缺口3：依赖已存在（无需新增）**

以下依赖已在 `pyproject.toml` 中存在，无需额外添加：
- `sentence-transformers = "^2.2.2"`（第61行）
- `FlagEmbedding = "^1.2.8"`（第64行）- 可选使用 BGE-M3 原生实现

**解决方案：**
1. Task 2 的 `BGEM3EmbeddingService` 生成 1024 维向量
2. Task 3 修改 `QdrantMemoryVectorStorage.__init__` 接受 `EmbeddingModelPort` 类型参数
3. 移除或重命名 `_deterministic_embed`（当前 128 维是开发/测试占位符）

### 项目结构说明 Project Structure

```
src/
├── domain/
│   └── ports/
│       ├── embedding_model.py     # [NEW] EmbeddingModelPort (领域层协议)
│       ├── l3_vector.py            # [EXISTING] L3VectorPort
│       └── registry.py            # [MODIFY] PortSpec 注册
├── application/
│   └── ports/
│       └── memory_vector_port.py   # [EXISTING] MemoryVectorPort (应用层)
│   └── services/
│       └── dense_retrieval_service.py  # [NEW] DenseRetrievalService
├── infrastructure/
│   ├── config/
│   │   └── embedding.py            # [NEW] BGEConfig
│   ├── external_services/
│   │   └── embedding/
│   │       ├── __init__.py         # [NEW] Package init
│   │       └── bge_m3_embedding_service.py  # [NEW] BGEM3EmbeddingService
│   └── storage/qdrant/
│       └── qdrant_memory_vector_storage.py  # [MODIFY] 支持 EmbeddingModelPort
└── composition_root.py             # [MODIFY] 注册 embedding 服务

tests/
├── contracts/
│   └── test_port_contract_embedding_model.py  # [NEW] 端口契约测试
├── unit/
│   ├── domain/ports/
│   │   └── test_embedding_model_port.py       # [NEW]
│   ├── application/services/
│   │   └── test_dense_retrieval_service.py    # [NEW]
│   └── infrastructure/
│       ├── config/
│       │   └── test_embedding_config.py       # [NEW]
│       └── embedding/
│           └── test_bge_m3_service.py          # [NEW]
├── integration/
│   └── test_integration_dense_retrieval.py    # [NEW]
├── acceptance/
│   ├── test_acceptance_dense_semantic_search.feature  # [NEW] Gherkin
│   └── test_acceptance_dense_semantic_search.py       # [NEW] BDD步骤
└── unit/architecture/
    └── test_arch_dense_retrieval.py           # [NEW] 架构验证
```

---

## 🤖 开发代理记录 Dev Agent Record

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] Epic 3 Story 3-1a 详情已分析
- [x] Story 1.6 Qdrant 向量层实现参考
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 依赖关系 Dependencies

| 依赖项 | 类型 | 状态 |
|--------|------|------|
| Epic 1 Story 1.6 (Qdrant) | 前置依赖 | ✅ 已完成 |
| Story 3.1b (BM25+RRF) | 被阻塞 | 📋 backlog |
| Story 3.9 (语义缓存) | 被阻塞 | 📋 backlog |

---

## 📚 模板使用说明 Template Usage Guide

### 相关文档 Related Documents

| 文档 | 说明 |
|------|------|
| [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md) | 开发模式详细说明与各层测试模板 |
| [SDD+TDD 实施检查清单](./sdd-tdd-checklist.md) | 实施步骤检查 |
| [预提交 Hooks 规范](./pre-commit-hooks.md) | 代码质量保障 |
| [架构设计文档](../../_bmad-output/planning-artifacts/architecture.md) | 六边形架构详细说明 |
| [Story 1.6 Qdrant向量层](../1-6-qdrant-vector-layer.md) | 参考实现 |

---

**故事版本/Story Version:** v0.0.4
**创建日期/Created:** 2026-05-30
**最后更新/Last Updated:** 2026-05-30
**更新说明/Description:**
- v0.0.4: [S1-S5 第3轮] 修正架构决策表格格式问题；明确 sentence-transformers 不在 FORBIDDEN_DOMAIN_IMPORTS 但领域层零依赖约束仍适用
- v0.0.3: [S1-S5 第2轮] 补充架构决策：sentence-transformers 在 FORBIDDEN_DOMAIN_IMPORTS
- v0.0.2: [S1-S5 审查修复] 修正技术栈（FlagEmbedding已存在）、标注已知实现缺口
- v0.0.1: 创建故事文件
