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

Story 3-1a 是 Epic 3（智能检索与知识发现）的关键路径首个故事。它在已完成的 Story 1.6（Qdrant 向量层）基础上，
构建从"用户输入文本"到"返回语义相关结果"的完整 Dense 检索管道，为后续 BM25 稀疏检索（3-1b）、RRF 融合排序（3-4）、
分层检索（3-5）提供基础 Dense 检索信号。

---

## ✅ Acceptance Criteria 验收标准

### AC-1: bge-m3 嵌入生成

**Given** EmbeddingService 已加载 bge-m3 模型
**When** 调用 `encode_text("企业战略规划报告")`
**Then** 返回 1024 维浮点向量
**And** 向量经过 L2 归一化（||v||₂ ≈ 1.0）

**验证标准/Validation Criteria:**
- [ ] 单文本编码返回 1024 维向量
- [ ] 批量编码返回正确数量的 1024 维向量
- [ ] 向量 L2 范数 ≈ 1.0（BGE-M3 经对比学习训练，Dense 输出近似 L2 归一化，容差约 1%；Qdrant 内部使用 Cosine 距离自动处理余量）
- [ ] 空文本抛出 ValueError（零向量在余弦相似度检索中会触发未定义行为，快速失败是更安全的策略）

### AC-2: 余弦相似度检索

**Given** Collection 包含已嵌入的文档向量
**When** 执行 Dense 语义检索（query_text, limit=5）
**Then** 使用 bge-m3 生成查询嵌入（1024 维）
**And** 在 Qdrant 中执行余弦相似度检索
**And** 返回最多 5 个结果，按相似度降序排列

**验证标准/Validation Criteria:**
- [ ] 端到端：text → embed → search → ranked results
- [ ] 结果包含 id, score, payload 字段
- [ ] 结果按 score 降序排列
- [ ] 无匹配结果返回空列表

### AC-3: 检索延迟 P95<200ms

**Given** Collection 包含 100 个文档向量
**When** 执行 50 次 Dense 语义检索（不含模型首次加载）
**Then** P95 延迟 < 200ms（嵌入生成 + Qdrant 检索，查询文本 ≤ 512 字符，GPU 模式）

**验证标准/Validation Criteria:**
- [ ] 50 次查询 P95 < 200ms（GPU 模式，查询文本 ≤ 512 字符）
- [ ] CPU 模式下放宽至 P95 < 500ms（CI 环境回退）
- [ ] 排除首次模型加载时间（SINGLETON 懒加载）
- [ ] 集成测试(Subtask 5.4)使用短文本（≤ 512 字符）进行性能测量
- [ ] **注意：** AC-3 为非功能性需求，无对应 Gherkin 场景，仅通过集成测试中的 `test_search_latency` 验证；50 次采样为 CI 快速验证基线，生产环境需 ≥500 次采样以获取统计可靠 P95

### AC-4: Payload 过滤

**Given** Collection 包含不同业务域的文档向量（business_domain 字段）
**When** 执行 Dense 语义检索并过滤 business_domain="finance"
**Then** 所有结果的 payload.business_domain 为 "finance"

**验证标准/Validation Criteria:**
- [ ] filter_payload 传递到 L3VectorPort.search()
- [ ] 支持 tenant_id 自动注入到 filter
- [ ] 现有 filter_payload 保留，tenant_id 追加

### AC-encode_sparse: Sparse 嵌入生成（v1.1.0 FlagEmbedding 迁移新增）

**Given** EmbeddingService 已加载 bge-m3 模型
**When** 调用 `encode_sparse("企业战略规划报告")`
**Then** 返回 `{"indices": list[int], "values": list[float]}` 格式的稀疏向量
**And** indices 为排序后的词汇 token ID
**And** values 为对应的词汇权重

**验证标准/Validation Criteria:**
- [ ] `encode_sparse()` 返回 `{"indices": list[int], "values": list[float]}`
- [ ] indices 列表按升序排列
- [ ] 所有 values > 0
- [ ] 空文本抛出 ValueError（与 Dense 编码保持一致）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 数据模型 (Data Models)
- [x] `EmbeddingConfig` — 嵌入模型配置 dataclass：model_name, model_path, device, dimension
- [x] `DenseSearchResult` — 检索结果 TypedDict：id, score, payload
- [x] 无新领域实体（本 Story 不涉及持久化实体）

#### 统一端口定义注册与管理 (Port Contract)
- [x] `EmbeddingServicePort` — 领域端口 Protocol（`src/domain/ports/embedding_service.py`）
  - `encode_text(text: str) -> list[float]` — 单文本 Dense 编码
  - `encode_texts(texts: list[str]) -> list[list[float]]` — 批量 Dense 编码
  - `encode_sparse(text: str) -> dict` — 单文本 Sparse 编码（v1.1.0 FlagEmbedding 迁移新增）
  - `dimension: int` — 嵌入维度属性（1024）
- [x] 端口注册中心 `src/domain/ports/registry.py` 中登记 `embedding_service` PortSpec
- [x] 端口实现 `src/composition_root.py` 统一注册
- [x] 端口契约测试通过（`tests/contracts/test_port_contract_embedding_service.py`）

**端口契约清单：**

| 端口名称 | 版本 | 接口 | 实现模块 | 生命周期 | Owner |
|---------|------|------|---------|---------|-------|
| `embedding_service` | v1.1.0 | `EmbeddingServicePort` | `src.infrastructure.external_services.embedding.bge3_embedding_service.BGE3EmbeddingService` | SINGLETON | search-team |
| `dense_search_service` | v1.0.0 | `DenseSemanticSearchService`（服务类自身，参考 document_upload_service 模式） | `src.application.services.dense_search_service.DenseSemanticSearchService` | SCOPED | search-team |

**已有端口（复用，不修改）：**

| 端口名称 | 版本 | 接口 | 复用方式 |
|---------|------|------|---------|
| `l3_vector` | v1.0.0 | `L3VectorPort` | DenseSemanticSearchService 注入 search() |
| `qdrant_connection_manager` | v1.0.0 | `ConnectionManager` | Qdrant 连接管理 |

#### API 契约 (API Contract)
- [x] 本 Story 不涉及 REST API 路由（纯应用层服务，API 路由由 Epic 7 提供）

#### 六边形架构约束（必须遵守）

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | EmbeddingServicePort Protocol（零外部依赖） |
| application | `src/application/` | DenseSemanticSearchService（编排 embed + search） |
| interfaces | `src/interfaces/` | 本 Story 不涉及 |
| infrastructure | `src/infrastructure/` | EmbeddingConfig + BGE3EmbeddingService（FlagEmbedding BGEM3FlagModel 实现） |

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | interfaces | infrastructure |
|---|---|---|---|---|
| **domain** (`embedding_service.py`) | — | ✗ | ✗ | ✗ |
| **application** (`dense_search_service.py`) | ✓ 导入 EmbeddingServicePort + L3VectorPort | — | ✗ | ✗ |
| **infrastructure** (`bge3_embedding_service.py`) | ✓ 实现 EmbeddingServicePort（含 encode_sparse） | ✗ | ✗ | — |

#### 验收标准 Gherkin (Acceptance Tests)
- [x] 功能测试文件：`tests/acceptance/test_acceptance_dense_semantic_search.feature`
- [x] 步骤实现文件：`tests/acceptance/test_acceptance_dense_semantic_search.py`
- [x] 所有场景覆盖（AC-1 至 AC-4 + AC-encode_sparse + 领域零依赖验证）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 不使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）

**Task 0 完成标志：**
- [x] 上述规范项全部定义完毕
- [x] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试
- ❌ 将测试编写集中到最后一个 Task
- ❌ 跳过红阶段验证

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 契约测试** | EmbeddingServicePort | 端口注册、方法签名、元数据 | `tests/contracts/test_port_contract_embedding_service.py` | Task 0 + Task 4 |
| **TDD 单元测试** | BGE3EmbeddingService | 编码维度、归一化、配置解析 | `tests/unit/infrastructure/external_services/embedding/test_bge3_embedding_service.py` | Task 2 |
| **TDD 单元测试** | DenseSemanticSearchService | embed→search 编排、tenant_id 注入 | `tests/unit/application/test_dense_search_service.py` | Task 3 |
| **TDD 单元测试** | generate_embedding task | Prefect task 接入 embedding_service | `tests/unit/infrastructure/external_services/embedding/test_generate_embedding.py` | Task 4 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `tests/acceptance/test_acceptance_dense_semantic_search.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `tests/acceptance/test_acceptance_dense_semantic_search.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单最终确认 | `tests/acceptance/test_acceptance_dense_semantic_search.feature` | Task 6 |
| **集成测试** | Embedding + Qdrant 端到端 + AC-3 性能基准 | 真实 bge-m3 + 真实 Qdrant + 性能测量 | `tests/integration/test_integration_embedding_qdrant_dense_search.py` | Task 5 |
| **SDD 架构验证** | 领域零依赖 | domain/ 无 FlagEmbedding 导入 | 包含在验收测试 Subtask 6.3 中 | Task 6 |
| **TDD 单元测试** | EmbeddingAPIClient | HTTP 请求/响应、错误处理、空值验证 | `tests/unit/infrastructure/external_services/embedding/test_embedding_api_client.py` | Task 7 |
| **TDD 单元测试** | Embedding API Server | FastAPI TestClient、Health check、编码端点 | `tests/unit/infrastructure/external_services/embedding/test_embedding_api_server.py` | Task 8 |
| **TDD 契约测试** | 双策略 DI | Local/API 模式 implementation 解析验证 | `tests/contracts/test_port_contract_embedding_service.py` | Task 9 |
| **TDD 验收测试** | API 模式 Gherkin | 嵌入 API 服务端到端验证 | `tests/acceptance/test_acceptance_dense_semantic_search.feature` | Task 10 |
| **TDD 验收测试** | 收尾验收场景 | src 与 tests 完成清单最终确认 | `tests/acceptance/test_acceptance_dense_semantic_search.feature` | Task 10 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

| 约束类型 | 规则 |
|---------|------|
| **资源唯一性** | 测试 Collection 使用 UUID 后缀：`test_{uuid}_dense_search` |
| **外部服务隔离** | Qdrant 测试前清理旧 Collection，测试后删除新 Collection |
| **并行隔离** | 并行测试使用 `TestTenant.qdrant_collection_prefix` 隔离 |
| **BDD async 配合** | BDD 步骤函数使用 `event_loop.run_until_complete()`，不用 `@pytest.mark.asyncio` |
| **模型加载隔离** | BGE3EmbeddingService SINGLETON 生命周期，测试 fixture 控制初始化 |
| **清理粒度** | 每个测试只清理自己创建的 Collection |

**验证要求：**
- [ ] 并行测试 `poetry run pytest tests/ -n 8` 通过
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | bge-m3 嵌入生成 | Task 1 | EmbeddingServicePort 定义 | `test_port_contract_embedding_service.py` |
| AC-1 | 编码维度与归一化 | Task 2 | BGE3EmbeddingService 实现 | `test_bge3_embedding_service.py` |
| AC-1 | 端口注册 + DI 装配 | Task 4 | Composition Root 注册 | `test_port_contract_embedding_service.py` |
| AC-1 | generate_embedding 替换 | Task 4 | Prefect task 接入 | `test_generate_embedding.py` |
| AC-2 | 余弦相似度检索 | Task 3 | DenseSemanticSearchService | `test_dense_search_service.py` |
| AC-2 | 端到端检索验证 | Task 5 | 集成测试 | `test_integration_embedding_qdrant_dense_search.py` |
| AC-3 | 检索延迟 P95<200ms | Task 5 | 性能基准测试 | `test_integration_embedding_qdrant_dense_search.py` |
| AC-4 | Payload 过滤 | Task 3 | tenant_id + filter 注入 | `test_dense_search_service.py` |
| AC-4 | 真实 Payload 过滤 | Task 5 | 集成测试 | `test_integration_embedding_qdrant_dense_search.py` |
| AC-encode_sparse | Sparse 嵌入生成（进程内） | Task 2 | BGE3EmbeddingService.encode_sparse() | `test_bge3_embedding_service.py` + `test_acceptance_dense_semantic_search.py` |
| AC-encode_sparse | Sparse 嵌入生成（API） | Task 7 | EmbeddingAPIClient | `test_embedding_api_client.py` |
| AC-encode_sparse | Sparse API 服务 | Task 8 | Embedding API Server | `test_embedding_api_server.py` |
| AC-1 | 双策略 DI（API/Local） | Task 9 | Composition Root 分支注册 | `test_port_contract_embedding_service.py` |
| 全部 | API 模式 BDD 验收 | Task 10 | Gherkin 场景 | `test_acceptance_dense_semantic_search.*` |
| 全部 | 收尾验收 | Task 10 | 完成清单确认 | `test_acceptance_dense_semantic_search.*` |

**Task 间执行依赖：**
```
Task 0（SDD 规范）→ Task 1（端口 + 配置）→ Task 2（Embedding 实现）
                                         ↘ Task 3（Search 服务）→ Task 4（注册装配）→ Task 5（集成测试）→ Task 6（收尾）→ Task 7（API Client）↘ Task 9（双策略DI）→ Task 10（验收）
                                                                                                                          Task 8（API Server）↗
```
- Task 0-6 为阶段一（MVP 进程内嵌入），已完成
- Task 7-10 为阶段二（API 化扩展），Task 7 依赖 Task 6 完成
- Task 7 和 Task 8 可并行
- Task 9 依赖 Task 7+8 全部完成
- Task 10 依赖 Task 9 完成

---

## 📋 Tasks / Subtasks 任务分解

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-encode_sparse

> **目的：** 在进入代码实现前，明确端口契约、配置模型、Gherkin 验收标准与六边形架构边界。

- [x] Subtask 0.1: 定义 `EmbeddingServicePort` Protocol 签名（`encode_text`, `encode_texts`, `dimension`）
- [x] Subtask 0.2: 定义 `EmbeddingConfig` 数据模型字段（model_name, model_path, device, dimension）
- [x] Subtask 0.3: 定义 `DenseSemanticSearchService` API 签名（`search(collection, query_text, limit, tenant_id, filter_payload)`）
- [x] Subtask 0.4: 定义 `DenseSearchResult` TypedDict（id, score, payload）
- [x] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_dense_semantic_search.feature`
- [x] Subtask 0.6: 编写 BDD 步骤实现骨架 `tests/acceptance/test_acceptance_dense_semantic_search.py`
- [x] Subtask 0.7: 编写端口契约测试 `tests/contracts/test_port_contract_embedding_service.py`
  > **契约测试模式参考**：项目无 PortContractTest 基类，使用独立三方法模式：
  > `test_port_is_registered`（验证注册）+ `test_implementation_has_required_methods`（验证方法签名）
  > + `test_metadata_complete`（验证 version/owner/module）。参考 `tests/contracts/test_port_contract_services.py`。
- [x] Subtask 0.8: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕
- [x] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: EmbeddingServicePort + EmbeddingConfig 实现

**关联 AC:** AC-1, AC-encode_sparse

#### TDD 循环 A：EmbeddingServicePort Protocol

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写契约测试（端口注册、方法签名、元数据） |
| 🟢 绿 | 创建 `src/domain/ports/embedding_service.py` |
| 🔄 重构 | 更新 `src/domain/ports/__init__.py` 导出 |

- [x] Subtask 1.1: 🔴 红 — 编写 `tests/contracts/test_port_contract_embedding_service.py` 失败测试
  - 验证 `embedding_service` 在 registry 注册
  - 验证实现类包含 `encode_text`, `encode_texts`, `dimension`
  - 验证 PortSpec 元数据（version, owner, lifetime）
- [x] Subtask 1.2: 🟢 绿 — 创建 `src/domain/ports/embedding_service.py`
  ```python
  @runtime_checkable
  class EmbeddingServicePort(Protocol):
      @property
      def dimension(self) -> int: ...
      def encode_text(self, text: str) -> list[float]: ...
      def encode_texts(self, texts: list[str]) -> list[list[float]]: ...
      def encode_sparse(self, text: str) -> dict: ...
  ```
- [x] Subtask 1.3: 🟢 绿 — 更新 `src/domain/ports/__init__.py` 添加导入和 `__all__` 导出
- [x] Subtask 1.4: 🔄 重构 — 运行 `ruff check` + `mypy` 确认通过

#### TDD 循环 B：EmbeddingConfig

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写配置解析失败测试 |
| 🟢 绿 | 创建 `src/infrastructure/config/embedding.py` |
| 🔄 重构 | 更新 config `__init__.py` 导出 |

- [x] Subtask 1.5: 🔴 红 — 编写 EmbeddingConfig 单元测试（from_env 解析、默认值、dimension 校验）
- [x] Subtask 1.6: 🟢 绿 — 创建 `src/infrastructure/config/embedding.py`
  ```python
  @dataclass
  class EmbeddingConfig:
      model_name: str = "BAAI/bge-m3"
      model_path: str = ""
      device: str = "cuda"
      dimension: int = 1024
      @classmethod
      def from_env(cls) -> EmbeddingConfig: ...
  ```
  > **设计决策：** 使用 `@dataclass`（非 frozen），与 `QdrantConfig`、`RedisConfig` 等基础设施连接配置保持一致。
- [x] Subtask 1.7: 🟢 绿 — 更新 `src/infrastructure/config/__init__.py` 添加导入和 `__all__`
- [x] Subtask 1.8: 🔄 重构 — 运行 `ruff check` + `mypy`

**完成标准/Definition of Done:**
- [x] EmbeddingServicePort Protocol 定义完成
- [x] EmbeddingConfig dataclass + from_env() 完成
- [x] 契约测试通过
- [x] domain/ports/__init__.py 和 config/__init__.py 导出已更新

---

### Task 2: BGE3EmbeddingService 实现

**关联 AC:** AC-1, AC-encode_sparse

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：BGE3EmbeddingService 核心功能

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/embedding/test_bge3_embedding_service.py` |
| 🟢 绿 | 创建 `src/infrastructure/external_services/embedding/bge3_embedding_service.py` |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [x] Subtask 2.1: 🔴 红 — 编写 BGE3EmbeddingService 失败测试
  - mock BGEM3FlagModel 实例
  - 验证 `encode_text` 返回 1024 维 float list
  - 验证 `encode_texts` 批量返回
  - 验证 `dimension` 属性
  - 验证 `encode_text` 调用 `model.encode(text, return_dense=True)`
  - 验证空文本处理
- [x] Subtask 2.2: 🟢 绿 — 创建 `src/infrastructure/external_services/embedding/__init__.py`
- [x] Subtask 2.3: 🟢 绿 — 创建 `src/infrastructure/external_services/embedding/bge3_embedding_service.py`
  ```python
  class BGE3EmbeddingService:
      """BGE-M3 嵌入服务实现"""
      def __init__(self, config: EmbeddingConfig | None = None): ...
      @property
      def dimension(self) -> int: return self._config.dimension
      def encode_text(self, text: str) -> list[float]: ...
      def encode_texts(self, texts: list[str]) -> list[list[float]]: ...
      def encode_sparse(self, text: str) -> dict[str, list[Any]]: ...
  ```
  - **模型加载逻辑**：`model_path` 非空时直接从本地路径加载，否则从 HuggingFace Hub 下载：
    ```python
    model_path = config.model_path if config.model_path and os.path.isdir(config.model_path) else config.model_name
    use_fp16 = config.device == "cuda"
    model = BGEM3FlagModel(model_path, use_fp16=use_fp16)
    ```
  - `model.encode(text, return_dense=True)` 返回 dict，取 `result["dense_vecs"]` 转为 `list[float]`
  - `encode_texts()` 使用 `batch_size=12`（GPU 显存效率与吞吐量的平衡值；`encode_text` 单文本使用 FlagEmbedding 默认值，不设 batch_size）
  - BGE-M3 Dense 输出经对比学习训练自然近似 L2 归一化（||v||₂ ≈ 1.0，容差 < 1%），无需显式 normalize_embeddings 参数；Qdrant 的 Cosine 距离内部归一化提供额外容错
- [x] Subtask 2.4: 🔄 重构 — 优化代码，运行 `ruff check` + `mypy`

**完成标准/Definition of Done:**
- [x] BGE3EmbeddingService 实现完成
- [x] 单元测试全部通过
- [x] 覆盖率≥75%（基础设施层）

---

### Task 3: DenseSemanticSearchService 实现

**关联 AC:** AC-2, AC-4

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：DenseSemanticSearchService

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_dense_search_service.py` |
| 🟢 绿 | 创建 `src/application/services/dense_search_service.py` |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [x] Subtask 3.1: 🔴 红 — 编写 DenseSemanticSearchService 失败测试
  - mock EmbeddingServicePort + L3VectorPort
  - 验证 `search()` 调用 `embed.encode_text` 一次
  - 验证 `search()` 调用 `vector.search` 一次并传入正确向量
  - 验证 `tenant_id` 自动注入到 `filter_payload`
  - 验证现有 `filter_payload` 保留
  - 验证 `limit` 传递正确
  - 验证空结果返回空列表
- [x] Subtask 3.2: 🟢 绿 — 创建 `src/application/services/dense_search_service.py`
  ```python
  class DenseSearchResult(TypedDict):
      id: str | int
      score: float
      payload: dict[str, Any]

  class DenseSemanticSearchService:
      def __init__(self, embedding_service: EmbeddingServicePort, vector_storage: L3VectorPort): ...
      async def search(self, collection: str, query_text: str, limit: int = 10,
                       tenant_id: str | None = None, filter_payload: dict | None = None) -> list[DenseSearchResult]:
          query_vector = await asyncio.to_thread(self._embedding.encode_text, query_text)
          combined_filter = ...
          return await self._vector.search(...)
  ```
  - 使用 `asyncio.to_thread()` 包装同步 embed 调用
  - ⚠️ **tenant_id 过滤注意**：当前 Qdrant upsert payload 中不含 `tenant_id` 字段。`DenseSemanticSearchService` 的 tenant_id 过滤逻辑需与后续 Story 的 index_document 实现对齐（确保 upsert 时写入 tenant_id）。本 Story 中 tenant_id 注入仅作为接口预留，过滤效果取决于 payload 中是否包含该字段。
- [x] Subtask 3.3: 🔄 重构 — 优化代码，运行 `ruff check` + `mypy`

**完成标准/Definition of Done:**
- [x] DenseSemanticSearchService 实现完成
- [x] 单元测试全部通过
- [x] 覆盖率≥85%（应用层）
- [x] `DenseSearchResult` TypedDict 定义在 `dense_search_service.py` 内部（当前未通过 `__init__.py` 导出，因其仅作为 `search()` 返回类型注解使用，外部调用者通过 `list[dict]` 兼容即可）

---

### Task 4: Composition Root 注册 + generate_embedding 替换

**关联 AC:** AC-1, AC-2

#### TDD 循环 A：Composition Root 注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写端口注册契约测试（验证 embedding_service + dense_search_service 注册） |
| 🟢 绿 | 修改 `src/composition_root.py` 注册两个新端口 |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [x] Subtask 4.1: 🔴 红 — 在 `tests/contracts/test_port_contract_embedding_service.py` 中添加 dense_search_service 注册验证
  - 验证 `embedding_service` 在 registry 注册（Task 0 已创建此文件，此处扩展）
  - 验证 `dense_search_service` 在 registry 注册
  - 验证 embedding_service 生命周期为 SINGLETON
  - 验证 dense_search_service 生命周期为 SCOPED
- [x] Subtask 4.2: 🟢 绿 — 修改 `src/composition_root.py` 添加：
  ```python
  # embedding_service — SINGLETON（模型加载昂贵）
  register_port(name="embedding_service", version="v1.1.0",
      interface=EmbeddingServicePort,
      impl=lambda r: BGE3EmbeddingService(EmbeddingConfig.from_env()),
      module="src.infrastructure.external_services.embedding.bge3_embedding_service",
      lifetime=Lifetime.SINGLETON, owner="search-team",
      tags=("embedding", "search"))

  # dense_search_service — SCOPED（轻量编排）
  # 注意：应用服务使用服务类自身作为 interface（参考 document_upload_service 模式）
  register_port(name="dense_search_service", version="v1.0.0",
      interface=DenseSemanticSearchService,
      impl=lambda r: DenseSemanticSearchService(
          embedding_service=r.resolve("embedding_service"),
          vector_storage=r.resolve("l3_vector")),
      module="src.application.services.dense_search_service",
      lifetime=Lifetime.SCOPED, owner="search-team",
      tags=("search", "dense"))
  ```
- [x] Subtask 4.3: 🔄 重构 — 运行 `ruff check` + `mypy`

#### TDD 循环 B：generate_embedding 占位替换

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 generate_embedding 使用 embedding_service 的测试 |
| 🟢 绿 | 替换 `src/infrastructure/workflow/tasks/document_tasks.py` 中的占位实现 |
| 🔄 重构 | 优化代码 |

- [x] Subtask 4.4: 🔴 红 — 编写 generate_embedding 单元测试 `tests/unit/infrastructure/external_services/embedding/test_generate_embedding.py`（mock resolver，验证调用 embedding_service）
- [x] Subtask 4.5: 🟢 绿 — 替换 `generate_embedding` 从 `return []` 改为使用 resolver 获取 embedding_service
  - ⚠️ **数据断裂问题**：`parse_document` task 返回精简 dict `{status, document_id, tenant_id, pages(数量)}`，不含文本内容
  - 需通过 `resolver.resolve("document_repository")` 获取完整文档，使用 `DocumentQuery(tenant_id=..., document_id=...)` 查询
  - 从 `doc.metadata["parse_result"]["pages"]` 提取文本
  - `await asyncio.to_thread(service.encode_text, text)`（BGE-M3 支持长文本，无需显式截断）
  - 异常时返回 `[]`（保持向后兼容）
- [x] Subtask 4.6: 🔄 重构 — 运行 `ruff check` + `mypy`

**完成标准/Definition of Done:**
- [x] composition_root.py 注册完成
- [x] generate_embedding 替换完成
- [x] 所有测试通过
- [x] **v1.2.2 已修复：** `generate_embedding` 现已同时提取 `page["texts"]` 和 `page["tables"]`（展平 `rows` 为空格分隔 cell 文本）。表格中的数值和结构化数据将纳入嵌入向量的语义空间。注意：`page["images"]` 仍被忽略——图像语义提取需依赖多模态模型，不在本 Story 范围内。

---

### Task 5: 集成测试（真实 bge-m3 + 真实 Qdrant）

**关联 AC:** AC-2, AC-3, AC-4

> **性质说明：** 端到端集成测试，验证 Embedding + Qdrant 在真实环境下的协作。
> **依赖：** Task 4 完成（所有端口注册就绪）。

#### TDD 循环 A：集成测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写集成测试（预期因服务未连接或数据不存在而失败） |
| 🟢 绿 | 实现测试逻辑，运行确认通过 |
| 🔄 重构 | 优化测试结构，添加性能基准 |

- [x] Subtask 5.1: 🔴 红 — 创建 `tests/integration/test_integration_embedding_qdrant_dense_search.py`
  - 使用 `TestTenant` 隔离（参考 `test_integration_qdrant_real.py` 模式：`f"test_{uuid.uuid4().hex[:8]}"` fixture）
  - Fixture：创建 Collection → 插入 5 个嵌入向量（覆盖不同业务域）→ 测试后 try/finally 删除
- [x] Subtask 5.2: 🟢 绿 — 实现端到端检索测试
  - embed 5 个中文文本（覆盖多业务域）→ upsert 到 Qdrant → 查询 → 验证排序
- [x] Subtask 5.3: 🟢 绿 — 实现 Payload 过滤测试
  - 插入不同 business_domain 的向量 → 过滤 → 验证结果
- [x] Subtask 5.4: 🟢 绿 — 实现性能基准测试
  - 预热 5 次查询 → 50 次查询（查询文本 ≤ 512 字符）→ 统计 P95 延迟
  - GPU: P95 < 200ms / CPU: P95 < 500ms（根据 `EmbeddingConfig.device` 自动选择阈值）
  - 标记 `@pytest.mark.slow`（CI 可选跳过）
- [x] Subtask 5.5: 🔄 重构 — 运行完整集成测试并确认通过，优化测试结构

**完成标准/Definition of Done:**
- [x] 集成测试全部通过
- [x] 端到端检索正确
- [x] Payload 过滤正确
- [x] P95 延迟满足 GPU<200ms / CPU<500ms 条件

---

### Task 6: 开发结束验收测试

**关联 AC:** 全部 AC

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写收尾验收场景（完成清单断言） |
| 🟢 绿 | 编写 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [x] Subtask 6.1: 场景 — 验证 `src` 完成清单
  - `src/domain/ports/embedding_service.py` 存在且包含 `EmbeddingServicePort`
  - `src/infrastructure/config/embedding.py` 存在且包含 `EmbeddingConfig`
  - `src/infrastructure/external_services/embedding/bge3_embedding_service.py` 存在且包含 `BGE3EmbeddingService`
  - `src/application/services/dense_search_service.py` 存在且包含 `DenseSemanticSearchService`
  - `src/composition_root.py` 包含 `embedding_service` 和 `dense_search_service` 注册
- [x] Subtask 6.2: 场景 — 验证 `tests/` 完成清单
  - 契约测试、单元测试、集成测试、验收测试文件均存在
- [x] Subtask 6.3: 场景 — 验证领域层零外部依赖
  - `src/domain/` 不导入 FlagEmbedding / sentence_transformers
- [x] Subtask 6.4: 运行开发结束验收测试并确认通过
- [x] Subtask 6.5: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验

**完成标准/Definition of Done:**
- [x] `src` 完成清单已逐项验证确认
- [x] `tests/` 完成清单已逐项验证确认
- [x] 开发结束验收测试通过
- [x] Story 可进入 `done`

---

### Task 7: EmbeddingAPIClient 实现

**关联 AC:** AC-1, AC-encode_sparse

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：EmbeddingAPIClient

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/embedding/test_embedding_api_client.py` |
| 🟢 绿 | 创建 `src/infrastructure/external_services/embedding/embedding_api_client.py` |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 7.1: 🔴 红 — 编写 EmbeddingAPIClient 失败测试
  - mock httpx.AsyncClient，验证 `encode_text()` 发送 `POST /v1/embeddings` 并返回 1024-dim
  - 验证 `encode_texts()` 批量编码返回正确数量
  - 验证 `encode_sparse()` 返回 `{"indices": [...], "values": [...]}`
  - 验证空文本抛出 `ValueError`（不发送 HTTP 请求）
  - 验证 HTTP 4xx/5xx 异常传播
  - 验证 `api_url` 为空时构造抛出 `ValueError`
  - 验证 `dimension` 属性返回 `config.dimension`
- [ ] Subtask 7.2: 🟢 绿 — 创建 `src/infrastructure/external_services/embedding/embedding_api_client.py`
  ```python
  class EmbeddingAPIClient:
      """BGE-M3 嵌入 API 客户端

      实现 EmbeddingServicePort，通过 HTTP POST /v1/embeddings 调用独立 API 服务。
      """
      def __init__(self, config: EmbeddingConfig | None = None): ...
      @property
      def dimension(self) -> int: return self._config.dimension
      async def encode_text(self, text: str) -> list[float]: ...
      async def encode_texts(self, texts: list[str]) -> list[list[float]]: ...
      async def encode_sparse(self, text: str) -> dict: ...
      async def _encode(self, texts: list[str], *, return_sparse: bool) -> dict: ...
      async def close(self) -> None: ...
  ```
  - 使用 `httpx.AsyncClient` 异步 HTTP 调用，方法签名使用 `async def`（不同于 BGE3EmbeddingService 的同步方法）
  - `_encode()` 私有方法统一处理 Dense/Sparse，避免重复 HTTP 逻辑
- [ ] Subtask 7.3: 🔄 重构 — 优化代码，运行 `ruff check` + `mypy`

#### TDD 循环 B：EmbeddingConfig 扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 补充 `EmbeddingConfig.from_env()` 测试（验证 `api_url`/`api_timeout` 环境变量解析） |
| 🟢 绿 | 修改 `src/infrastructure/config/embedding.py` |
| 🔄 重构 | 更新 `.env.example`，运行 `ruff` + `mypy` |

- [ ] Subtask 7.4: 🔴 红 — 补充 `test_from_env_defaults` 验证 `api_url=""`、`api_timeout=30.0`
- [ ] Subtask 7.5: 🔴 红 — 补充 `test_from_env_custom` 验证环境变量 `EMBEDDING_API_URL`、`EMBEDDING_API_TIMEOUT` 覆盖
- [ ] Subtask 7.6: 🟢 绿 — `EmbeddingConfig` dataclass 新增 `api_url: str = ""`、`api_timeout: float = 30.0`
- [ ] Subtask 7.7: 🟢 绿 — `.env.example` 新增 `EMBEDDING_API_URL`、`EMBEDDING_API_TIMEOUT` 注释项
- [ ] Subtask 7.8: 🔄 重构 — 运行 `ruff check` + `mypy`

**完成标准/Definition of Done:**
- [ ] EmbeddingAPIClient 实现完成
- [ ] EmbeddingConfig 扩展完成（`api_url`、`api_timeout`）
- [ ] 单元测试 7 个场景全部通过
- [ ] 覆盖率≥75%（基础设施层）

---

### Task 8: Embedding API Server 实现

**关联 AC:** AC-1, AC-encode_sparse

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：Embedding API Server

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/embedding/test_embedding_api_server.py` |
| 🟢 绿 | 创建 `src/infrastructure/external_services/embedding/embedding_api_server.py` |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask 8.1: 🔴 红 — 编写 Embedding API Server 失败测试（FastAPI `TestClient`）
  - 验证 `GET /health` 返回 `{"status": "ok", "model": "BAAI/bge-m3"}`
  - 验证 `POST /v1/embeddings`（`return_sparse=false`）返回 `{"dense": [[...], ...]}`，维度 1024
  - 验证 `POST /v1/embeddings`（`return_sparse=true`）同时返回 `dense` 和 `sparse`
  - 验证 `sparse` 各元素含 `indices` 和 `values` 字段
  - 验证空 `texts` 列表返回 422（Pydantic `min_length=1` 校验）
  - 验证 `texts` 超过 64 条返回 422（Pydantic `max_length=64` 校验）
- [ ] Subtask 8.2: 🟢 绿 — 创建 `src/infrastructure/external_services/embedding/embedding_api_server.py`
  ```python
  """BGE-M3 嵌入 API 服务端

  通过 FastAPI + FlagEmbedding 将 BGE-M3 封装为独立 HTTP 服务，Docker Compose 独立部署。
  """

  from fastapi import FastAPI
  from pydantic import BaseModel, Field
  from FlagEmbedding import BGEM3FlagModel

  app = FastAPI(title="SISYS Embedding API", version="1.0.0")

  class EmbedRequest(BaseModel):
      texts: list[str] = Field(..., min_length=1, max_length=64)
      return_sparse: bool = False

  class EmbedResponse(BaseModel):
      dense: list[list[float]]
      sparse: list[dict] | None = None

  @app.on_event("startup")
  async def load_model(): ...

  @app.get("/health")
  async def health(): ...

  @app.post("/v1/embeddings", response_model=EmbedResponse)
  async def embed(req: EmbedRequest): ...
  ```
  - 模型在 `@app.on_event("startup")` 中懒加载，请求间复用
  - Pydantic V2 自动校验请求体，非法输入返回 422
  - `response_model=EmbedResponse` 强制输出 schema 校验
- [ ] Subtask 8.3: 🔄 重构 — 优化代码，运行 `ruff check` + `mypy`

**完成标准/Definition of Done:**
- [ ] Embedding API Server 暴露 `GET /health` 和 `POST /v1/embeddings`
- [ ] FastAPI `TestClient` 测试 6 个场景全部通过
- [ ] Pydantic 请求校验自动拒绝非法输入
- [ ] 覆盖率≥75%（基础设施层）

---

### Task 9: 双策略 DI 注册 + Docker Compose 部署

**关联 AC:** AC-1, AC-2

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 A：双策略 DI 注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 在 `tests/contracts/test_port_contract_embedding_service.py` 中补充 API 模式注册验证 |
| 🟢 绿 | 修改 `src/composition_root.py` 双策略注册 |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [ ] Subtask 9.1: 🔴 红 — 补充契约测试验证双策略
  - 验证 `EMBEDDING_API_URL` 为空时 `embedding_service` 解析为 `BGE3EmbeddingService`
  - 验证 `EMBEDDING_API_URL` 非空时 `embedding_service` 解析为 `EmbeddingAPIClient`
  - 验证两种实现的 `interface` 均为 `EmbeddingServicePort`
- [ ] Subtask 9.2: 🟢 绿 — 修改 `src/composition_root.py`
  ```python
  # === Search Ports (Epic 3) ===
  EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL", "")

  if EMBEDDING_API_URL:
      from src.infrastructure.external_services.embedding.embedding_api_client import (
          EmbeddingAPIClient,
      )
      register_port(
          name="embedding_service", version="v1.1.0",
          interface=EmbeddingServicePort,
          impl=lambda resolver: EmbeddingAPIClient(EmbeddingConfig.from_env()),
          module="src.infrastructure.external_services.embedding.embedding_api_client",
          lifetime=Lifetime.SINGLETON, owner="search-team",
          tags=("embedding", "search", "api"),
      )
  else:
      from src.infrastructure.external_services.embedding.bge3_embedding_service import (
          BGE3EmbeddingService,
      )
      register_port(
          name="embedding_service", version="v1.1.0",
          interface=EmbeddingServicePort,
          impl=lambda resolver: BGE3EmbeddingService(EmbeddingConfig.from_env()),
          module="src.infrastructure.external_services.embedding.bge3_embedding_service",
          lifetime=Lifetime.SINGLETON, owner="search-team",
          tags=("embedding", "search", "local"),
      )
  ```
  - 双策略在 `composition_root.py` 中通过环境变量分支实现，不引入额外抽象层
  - `DenseSemanticSearchService` 仍通过 `resolver.resolve("embedding_service")` 获取，对两种实现透明
- [ ] Subtask 9.3: 🔄 重构 — 运行 `ruff check` + `mypy`

#### TDD 循环 B：Docker Compose 部署配置

| 阶段 | 动作 |
|------|------|
| 🟢 绿 | 创建 `deploy/docker-compose.embedding.yml` 和 `deploy/Dockerfile.embedding` |
| 🔄 重构 | 更新 `.env.example` 集成说明 |

- [ ] Subtask 9.4: 🟢 绿 — 创建 `deploy/docker-compose.embedding.yml`
  ```yaml
  services:
    embedding-api:
      build:
        context: ..
        dockerfile: deploy/Dockerfile.embedding
      ports: ["8001:8000"]
      environment:
        - EMBEDDING_MODEL_NAME=${EMBEDDING_MODEL_NAME:-BAAI/bge-m3}
        - EMBEDDING_MODEL_PATH=${EMBEDDING_MODEL_PATH:-}
      deploy:
        resources:
          reservations:
            devices:
              - driver: nvidia
                count: 1
                capabilities: [gpu]
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
        interval: 30s
        retries: 3
  ```
- [ ] Subtask 9.5: 🟢 绿 — 创建 `deploy/Dockerfile.embedding`
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  RUN pip install fastapi uvicorn FlagEmbedding
  COPY src/infrastructure/external_services/embedding/embedding_api_server.py /app/
  CMD ["uvicorn", "embedding_api_server:app", "--host", "0.0.0.0", "--port", "8000"]
  ```
  > **设计决策：** Dockerfile 独立于主项目 Dockerfile，仅含 FlagEmbedding + FastAPI 最小依赖。不依赖 `src/domain/` 或 `src/composition_root.py`，保持 API 服务完全自包含。
- [ ] Subtask 9.6: 🔄 重构 — 更新 `.env.example` 新增 `EMBEDDING_API_URL=http://embedding-api:8000` 注释说明

**完成标准/Definition of Done:**
- [ ] `composition_root.py` 双策略注册完成（按 `EMBEDDING_API_URL` 切换）
- [ ] 契约测试验证两种模式均正确注册
- [ ] `docker compose -f deploy/docker-compose.embedding.yml config` 语法通过
- [ ] ruff + mypy 通过

---

### Task 10: 开发结束验收测试

**关联 AC:** 全部 AC

> **性质说明：** 本 Task 不是功能实现，是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 在 `tests/acceptance/test_acceptance_dense_semantic_search.feature` 中新增 API 模式验收场景 |
| 🟢 绿 | 编写 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 10.1: 🔴 红 — 新增 Gherkin 场景：AC-api — 嵌入 API 服务健康检查
- [ ] Subtask 10.2: 🔴 红 — 新增 Gherkin 场景：AC-api — 嵌入 API 服务 Dense 编码
- [ ] Subtask 10.3: 🔴 红 — 新增 Gherkin 场景：AC-api — 嵌入 API 服务 Sparse 编码
- [ ] Subtask 10.4: 🟢 绿 — 编写 BDD 步骤实现（FastAPI `TestClient` 启动 embedding_api_server.app）
- [ ] Subtask 10.5: 🔄 重构 — 运行验收测试并确认通过

- [ ] Subtask 10.6: 场景 — 验证 `src` 完成清单
  - `src/infrastructure/external_services/embedding/embedding_api_client.py` 存在且包含 `EmbeddingAPIClient`
  - `src/infrastructure/external_services/embedding/embedding_api_server.py` 存在且包含 FastAPI `app`
  - `src/infrastructure/config/embedding.py` 包含 `api_url`、`api_timeout` 字段
  - `src/composition_root.py` 包含双策略注册（`EMBEDDING_API_URL` 分支）
- [ ] Subtask 10.7: 场景 — 验证 `tests/` 和部署完成清单
  - `test_embedding_api_client.py` 和 `test_embedding_api_server.py` 存在
  - `test_acceptance_dense_semantic_search.feature` 含 API 模式场景
  - `deploy/docker-compose.embedding.yml` 和 `deploy/Dockerfile.embedding` 存在
- [ ] Subtask 10.8: 运行 `poetry run pytest`、`poetry run ruff check src/`、`poetry run mypy src/` 收尾校验

**完成标准/Definition of Done:**
- [ ] `src` 和 `tests` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束

**来源:** `docs/architecture/architecture.md`

- **架构模式:** 六边形架构（Ports & Adapters），CQRS（查询端）
- **设计约束:** 领域层零外部依赖，依赖方向 domain←application←infrastructure
- **接口治理:** 统一端口注册、PortSpec 元数据、Registry/Resolver/ContractGate、Composition Root 装配
- **技术栈:** Python 3.11+, FlagEmbedding ^1.2.8 (BGEM3FlagModel), qdrant-client 1.7.1, torch 2.7.1
- **统一错误处理策略:**
  - 空/空白文本输入 → `ValueError`（嵌入层统一快速失败，避免零向量触发检索未定义行为）
  - 基础设施异常 → `return []`（如 `generate_embedding` 保持向后兼容，避免中断 Prefect 流）
  - HTTP 错误 → 异常传播（未来 `EmbeddingAPIClient` 中由 `httpx` 原生抛出）
  - 请求校验失败 → Pydantic 422（未来 `Embedding API Server` 中 `min_length=1`/`max_length=64` 自动校验）
  - 模型加载失败 → 构造时 `ValueError`（维度不匹配 / 路径不可达 / GPU 能力不足）

> **迁移记录（2026-06-02）：** Story 3-1a 初始实现使用 `SentenceTransformers` 加载 BGE-M3 模型。
> 经对标业界最佳实践分析（BGE-M3 是 BAAI 发布的模型，FlagEmbedding 是 BAAI 官方第一方库），
> 在 Story 3-1b 启动前完成重构，迁移至 `FlagEmbedding`（BGEM3FlagModel）。
> 同时新增 `encode_sparse()` 方法，为 Story 3-1b BM25 稀疏检索提供原生 Sparse 嵌入能力。
> 详见 Story 3-1b Dev Notes。
>
> **⚠️ 依赖残留说明：** 当前 `pyproject.toml` 同时保留 `sentence-transformers = "^2.2.2"` 和 `FlagEmbedding = "^1.2.8"`。
> `sentence-transformers` 可能被其他 Story（如 ST-1.17 语义路由）使用，需在相应 Story 迁移后移除。
> 项目约定：禁止新增 `sentence_transformers` 导入，所有新代码统一使用 `FlagEmbedding`。

### 关键架构决策

**来源:** `docs/architecture/architecture.md` — ADR-004（向量数据库选型 Qdrant）

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **Qdrant（选中）** | 高性能 Dense/Sparse 混合检索，原生余弦相似度，gRPC 支持 | 需独立部署 | ✅ 9/10 |
| Milvus | 功能全面 | Java 依赖重，部署复杂 | 7/10 |
| Weaviate | GraphQL API | 扩展性一般 | 6/10 |

### 嵌入库选型决策：FlagEmbedding vs SentenceTransformers

| 方案 | 优点 | 缺点 | 决策 |
|------|------|------|------|
| **FlagEmbedding / BGEM3FlagModel（选中）** | BAAI 第一方库，一次推理同时产出 Dense+Sparse+ColBERT；原生多语言 tokenizer | 锁定 BGE 系列模型 | ✅ 采用 |
| SentenceTransformers（初始方案） | 模型无关，支持 500+ 模型，生态成熟 | Sparse/ColBERT 支持不如 FlagEmbedding 原生；需额外代码实现 | 已迁移 |

**原因：** SISYS 架构中 BGE-M3 是硬编码默认模型，短期内不会切换。FlagEmbedding 在中文分词、Sparse 嵌入质量、架构简洁性上均占优势。

### EmbeddingServicePort 方法设计：同步 vs 异步

| 方案 | 优点 | 缺点 | 决策 |
|------|------|------|------|
| **同步方法 + asyncio.to_thread**（本地模式） | BGEM3FlagModel.encode() 本身同步；接口简洁 | 调用者需包装 | ✅ 阶段一采用 |
| **异步方法**（API 模式） | 适合 HTTP 客户端非阻塞调用 | 与同步端口签名不一致 | ✅ 阶段二 API 模式采用 |

**设计说明：**
- **阶段一（Task 0-6）**：`BGE3EmbeddingService` 使用同步方法，通过 `asyncio.to_thread()` 包装，端口 Protocol 定义同步签名
- **阶段二（Task 7-10）**：`EmbeddingAPIClient` 使用异步方法（`async def`），因为 HTTP 调用天然异步
- **⚠️ 兼容策略（Task 9 待解决）**：Python Protocol 不能同时兼容 `def` 和 `async def` 签名。当前方案选项：
  1. **适配器包装（推荐）**：`EmbeddingAPIClient` 暴露异步方法，注册端口的 lambda 中包装一个同步适配器（内部使用 `asyncio.run()` 或持有 event loop 引用）。由于 `asyncio.to_thread()` 在独立线程中执行，可在该线程内创建临时 event loop。
  2. **统一 async Protocol**：将 `EmbeddingServicePort` 方法改为 `async def`，本地模式在实现层内部用 `asyncio.to_thread` 包装。需要同步所有调用者。
  3. **`inspect.iscoroutinefunction()` 动态判断**：`DenseSemanticSearchService` 在运行时检测 `encode_text` 是否为协程，选择合适的调用方式。增加运行时开销但保持最大兼容性。
  **决策待 Task 9 实施时根据性能基准和复杂度最终确定。**

### .env 配置设计

```env
# Embedding Model
EMBEDDING_MODEL_NAME=BAAI/bge-m3
EMBEDDING_MODEL_PATH=/mnt/x/.cache/BAAI/bge-m3/models--BAAI--bge-m3/
EMBEDDING_MODEL_DEVICE=cuda
EMBEDDING_MODEL_DIMENSION=1024
```

- `EMBEDDING_MODEL_NAME/PATH/DEVICE` 已在 `.env.example` 第 82-84 行存在
- `EMBEDDING_MODEL_DIMENSION` 为新增项
- `EMBEDDING_MODEL_PATH` 指向包含 `config.json` 和 `pytorch_model.bin` 的模型目录（本地 git clone 结构）
- **需同步更新** `tests/environments.py` 中 `EmbeddingConfig` 添加 `dimension: int = 1024` 字段（当前只有 model_name/model_path/device）

### 已有组件复用说明

| 组件 | 路径 | 复用方式 |
|------|------|---------|
| `L3VectorPort.search()` | `src/domain/ports/l3_vector.py` | DenseSemanticSearchService 直接调用 |
| `QdrantVectorStorage.search()` | `src/infrastructure/storage/qdrant/vector_storage.py` | Dense search 已完整实现；**注意**：`create_collection`/`delete_collection`/`collection_exists`/`list_collections` 为空 stub，实际 Collection 管理由 `QdrantAdapter` → `QdrantCollectionManager` 链路完成 |
| `L3VectorPort.search_sparse()` | `src/domain/ports/l3_vector.py` | **注意**：`search_sparse()` 的 filter 实现仅支持精确匹配（`MatchValue`），不支持数值范围过滤（`Range`），与 `search()` 的 filter 能力不对称 |
| `QdrantAdapter` | `src/infrastructure/storage/qdrant/qdrant_adapter.py` | l3_vector 端口实现 |
| `QdrantCollectionManager` | `src/infrastructure/storage/qdrant/collection_manager.py` | 测试中创建 Collection |
| `VectorPoint` (1024维) | `src/infrastructure/storage/qdrant/models.py` | 测试中构造向量点 |
| `EmbeddingModelProtocol` | `src/infrastructure/routing/semantic_router.py` | 设计参考（本 Story 不直接使用） |
| `EmbeddingConfig` (测试) | `tests/environments.py` | 测试环境已有配置；**注意**：`tests/environments.py` 和 `src/infrastructure/config/embedding.py` 各自维护独立的 `EmbeddingConfig` dataclass，需手动同步字段变更 |

### generate_embedding MVP 占位

**文件：** `src/infrastructure/workflow/tasks/document_tasks.py` 第 58-71 行

```python
# 替换后：通过 resolver 获取真实 EmbeddingService
# 注意：parse_document task 返回精简 dict {status, document_id, tenant_id, pages(数量)}，
# 不含文本内容。需通过 DocumentRepository + DocumentQuery 获取完整文档的 metadata["parse_result"]。
async def generate_embedding(parse_result: dict[str, Any]) -> list[float]:
    from src.domain.ports.document_repository import DocumentQuery
    from src.domain.ports.resolver import get_resolver
    if parse_result.get("status") == "failed":
        return []
    tenant_id = parse_result.get("tenant_id", "")
    if not tenant_id:
        return []
    resolver = get_resolver()
    service = resolver.resolve("embedding_service")
    repo = resolver.resolve("document_repository")
    doc = await repo.find(
        DocumentQuery(
            tenant_id=tenant_id,
            document_id=uuid.UUID(parse_result["document_id"]),
        )
    )
    if not doc or not doc.metadata.get("parse_result"):
        return []
    pages = doc.metadata["parse_result"].get("pages", [])
    text_parts = [elem.get("content", "") for page in pages for elem in page.get("texts", []) if isinstance(elem, dict)]
    # v1.2.2: 补充表格文本提取（展平 rows 为空格分隔 cell 文本）
    for page in pages:
        for table in page.get("tables", []):
            if isinstance(table, dict):
                for row in table.get("rows", []):
                    if isinstance(row, list):
                        text_parts.append(" ".join(str(cell) for cell in row if cell))
    text = " ".join(text_parts)
    if not text.strip():
        return []
    embedding = await asyncio.to_thread(service.encode_text, text)
    return embedding
```

### 项目结构说明

```
src/
├── domain/ports/
│   ├── embedding_service.py          # [新建] EmbeddingServicePort Protocol
│   ├── l3_vector.py                  # [已有] L3VectorPort — search() 复用
│   ├── __init__.py                   # [修改] 添加 EmbeddingServicePort 导出
│   ├── registry.py                   # [已有] 端口注册中心
│   ├── resolver.py                   # [已有] DI 解析器
│   └── contract_gate.py              # [已有] 契约门禁
├── application/services/
│   ├── dense_search_service.py       # [新建] DenseSemanticSearchService
│   └── document_upload_service.py    # [已有] 参考模式
├── infrastructure/
│   ├── config/
│   │   ├── embedding.py              # [新建] EmbeddingConfig
│   │   ├── __init__.py               # [修改] 添加 EmbeddingConfig 导出
│   │   └── qdrant.py                 # [已有] 参考模式
│   ├── external_services/embedding/
│   │   ├── __init__.py                  # [新建] 包初始化
│   │   ├── bge3_embedding_service.py    # [新建] BGE3EmbeddingService (FlagEmbedding 进程内)
│   │   ├── embedding_api_client.py      # [新建] EmbeddingAPIClient (HTTP API 客户端)
│   │   └── embedding_api_server.py      # [新建] FastAPI 嵌入服务 (独立部署)
│   ├── storage/qdrant/
│   │   ├── vector_storage.py         # [已有] Dense search 实现复用
│   │   ├── qdrant_adapter.py         # [已有] l3_vector 适配器复用
│   │   ├── collection_manager.py     # [已有] 测试中创建 Collection
│   │   └── models.py                 # [已有] VectorPoint/CollectionConfig 复用
│   └── workflow/tasks/
│       └── document_tasks.py         # [修改] 替换 generate_embedding 占位
└── composition_root.py               # [修改] 注册 embedding 端口（后扩展为双策略分支）

tests/
├── contracts/
│   └── test_port_contract_embedding_service.py  # [新建] 端口契约测试
├── unit/
│   ├── infrastructure/
│   │   └── external_services/embedding/
│   │       ├── test_bge3_embedding_service.py   # [新建] 嵌入服务单元测试
│   │       └── test_generate_embedding.py       # [新建] generate_embedding 单元测试
│   └── application/
│       └── test_dense_search_service.py          # [新建] 检索服务单元测试
├── integration/
│   └── test_integration_embedding_qdrant_dense_search.py     # [新建] 端到端集成测试
├── acceptance/
│   ├── test_acceptance_dense_semantic_search.feature  # [新建] Gherkin 场景
│   └── test_acceptance_dense_semantic_search.py       # [新建] BDD 步骤定义
└── environments.py                               # [修改] EmbeddingConfig 添加 dimension 字段
```

> **额外修改文件**（项目根目录）：`.env.example` — 添加 EMBEDDING_MODEL_DIMENSION=1024

### BDD 测试参考模式

**参考文件：** `tests/acceptance/test_acceptance_qdrant_vector_layer.py`

核心模式：
```python
scenarios("test_acceptance_dense_semantic_search.feature")

@scenario("...feature", "AC-1 - bge-m3 嵌入生成")
def test_ac1_embedding_generation():
    pass

@pytest.fixture
def context() -> dict[str, Any]:
    return {}

@pytest.fixture
def embedding_service():
    """尝试加载 bge-m3 模型，不可用时 pytest.skip"""
    config = EmbeddingConfig(model_name="BAAI/bge-m3", device="cpu")
    try:
        return BGE3EmbeddingService(config)
    except Exception as e:
        pytest.skip(f"bge-m3 模型不可用: {e}")

# AC-1: 同步方法在 BDD 步骤中直接调用（无需 asyncio.to_thread 包装）
@when("我使用 EmbeddingService 编码文本")
def encode_text(context, embedding_service):
    result = embedding_service.encode_text("测试文本")  # 同步方法，直接调用
    context["embedding"] = result

# AC-2: async 检索操作使用 event_loop.run_until_complete
@when("我执行 Dense 语义检索")
def perform_dense_search(context, dense_search_service, event_loop):
    async def _search():
        return await dense_search_service.search(collection, "企业战略规划", limit=5)
    results = event_loop.run_until_complete(_search())
    context["search_results"] = results
```

> **关键设计点：**
> - `encode_text` 是同步方法，在 BDD 同步步骤函数中直接调用，无需 `asyncio.to_thread` 包装
> - `DenseSemanticSearchService.search()` 是 async 方法，通过 `event_loop.run_until_complete()` 调用
> - 遵循项目现有模式：模型/服务不可用时 `pytest.skip()`
> - P95 延迟测试放在验收测试中符合项目既定规范（至少 6 个现有 Story 采用）

### 前一个故事学习经验

**来源:** [Story 2-2a-document-parsing-basic-formats](./2-2a-document-parsing-basic-formats.md)

**关键学习/Key Learnings:**
1. **DI 注册延迟加载陷阱** — impl 字符串拼写错误不立即报错，需契约测试覆盖
2. **事件双注册** — 新增事件需同时更新 `configs/event_channels.yaml` 和 `ChannelRouter.DEFAULT_MAPPINGS`（**本 Story 不新增事件**，无需修改）
3. **TestTenant 隔离** — 并行测试 UUID 前缀隔离，新端口测试也必须使用
4. **仓储无 update_* 方法** — 项目统一使用 `save()` 全量更新

**来源:** [Story 1-6-qdrant-vector-layer](./1-6-qdrant-vector-layer.md)

**关键学习/Key Learnings:**
1. **Qdrant v1.7.x ID 要求** — 无符号整数，需 `_normalize_point_id()` 处理字符串 ID
2. **query_points API 已废弃** — 改用 `search` 方法
3. **配置模式复用** — `XxxConfig` + `from_env()` 模式
4. **懒初始化连接池** — 首次调用时创建客户端

**应用到本故事/Applied to This Story:**
- [x] embedding_service impl 字符串拼写纳入契约测试
- [x] BGE3EmbeddingService SINGLETON 生命周期（模型加载昂贵）
- [x] 测试使用 TestTenant 进行租户隔离
- [x] EmbeddingConfig 遵循 `from_env()` 模式（参考 QdrantConfig）
- [x] 向量维度固定 1024，Collection 使用 Cosine 距离

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.1 |
| **Version** | create-story workflow v2.7.0 |
| **Execution Date** | 2026-06-01 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Checklist** | `.claude/skills/bmad-create-story/checklist.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/2-2a-document-parsing-basic-formats.md` |
| **依赖 Story** | `_bmad-output/implementation-artifacts/stories/1-6-qdrant-vector-layer.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Epic 3 Story 3.1a 第 1126-1167 行）
- [x] 架构约束从 `architecture.md` 提取（L3 向量层、bge-m3、余弦相似度）
- [x] 前一个故事学习经验整合（2-2a 解析经验 + 1-6 Qdrant 经验）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] .env 配置设计完成（新增 EMBEDDING_MODEL_DIMENSION）
- [x] 端口契约清单完整（EmbeddingServicePort + dense_search_service）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-1a-dense-semantic-search.md`

**待创建的文件/To Be Created (Dev Story 实施):**

> **阶段一（Task 0-6）文件已创建 ✅，阶段二（Task 7-10）文件待创建。**

| 文件 | 类型 | Task | 状态 |
|------|------|------|------|
| `src/domain/ports/embedding_service.py` | 领域端口 Protocol | Task 1 | ✅ 已创建 |
| `src/infrastructure/config/embedding.py` | 基础设施配置 | Task 1 | ✅ 已创建 |
| `src/infrastructure/external_services/embedding/__init__.py` | 包初始化 | Task 2 | ✅ 已创建 |
| `src/infrastructure/external_services/embedding/bge3_embedding_service.py` | 嵌入服务实现 | Task 2 | ✅ 已创建 |
| `src/application/services/dense_search_service.py` | 应用层服务 | Task 3 | ✅ 已创建 |
| `tests/contracts/test_port_contract_embedding_service.py` | 契约测试 | Task 0 | ✅ 已创建 |
| `tests/unit/infrastructure/external_services/embedding/test_bge3_embedding_service.py` | 单元测试 | Task 2 | ✅ 已创建 |
| `tests/unit/application/test_dense_search_service.py` | 单元测试 | Task 3 | ✅ 已创建 |
| `tests/unit/infrastructure/external_services/embedding/test_generate_embedding.py` | 单元测试 | Task 4 | ✅ 已创建 |
| `tests/integration/test_integration_embedding_qdrant_dense_search.py` | 集成测试 | Task 5 | ✅ 已创建 |
| `tests/acceptance/test_acceptance_dense_semantic_search.feature` | Gherkin 场景 | Task 0 | ✅ 已创建 |
| `tests/acceptance/test_acceptance_dense_semantic_search.py` | BDD 步骤 | Task 0 | ✅ 已创建 |
| `src/infrastructure/external_services/embedding/embedding_api_client.py` | API 客户端 | Task 7 | 待创建 |
| `src/infrastructure/external_services/embedding/embedding_api_server.py` | API 服务端 | Task 8 | 待创建 |
| `tests/unit/infrastructure/external_services/embedding/test_embedding_api_client.py` | 单元测试 | Task 7 | 待创建 |
| `tests/unit/infrastructure/external_services/embedding/test_embedding_api_server.py` | 单元测试 | Task 8 | 待创建 |
| `deploy/docker-compose.embedding.yml` | Docker Compose 部署 | Task 9 | 待创建 |
| `deploy/Dockerfile.embedding` | Docker 镜像 | Task 9 | 待创建 |

**待修改的文件/To Be Modified:**

> **阶段一修改已完成 ✅，阶段二修改（api_url/api_timeout 字段、双策略 DI 分支）待 Task 7-9 实施。**

- `src/domain/ports/__init__.py` — 添加 EmbeddingServicePort 导出 ✅
- `src/infrastructure/config/__init__.py` — 添加 EmbeddingConfig 导出 ✅
- `src/infrastructure/config/embedding.py` — 新增 `api_url`、`api_timeout` 字段（待 Task 7）
- `src/composition_root.py` — 注册 embedding_service + dense_search_service ✅（双策略分支待 Task 9）
- `src/infrastructure/workflow/tasks/document_tasks.py` — 替换 generate_embedding 占位 ✅
- `.env.example` — 添加 EMBEDDING_MODEL_DIMENSION=1024 ✅（EMBEDDING_API_URL/TIMEOUT 待 Task 7）
- `tests/environments.py` — EmbeddingConfig 添加 dimension: int = 1024 字段 ✅

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.1a |
| **Story Key** | 3-1a-dense-semantic-search |
| **File** | `_bmad-output/implementation-artifacts/stories/3-1a-dense-semantic-search.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | P0-1a（关键路径） |
| **覆盖 FR** | FR-SR-01（混合检索 Dense 部分） |
| **依赖 Story** | Story 1-6-qdrant-vector-layer（已完成） |
| **后续 Story** | Story 3-1b-bm25-sparse-search-rrf-fusion |

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

---

**故事版本/Story Version:** v1.2.3
**创建日期/Created:** 2026-06-01
**最后更新/Last Updated:** 2026-06-03
**更新说明/Description:**
- v1.2.3: 5轮审查修订第3轮 — 修复 Task 0/1 AC-encode_sparse 关联缺失、集成测试分类表补充 AC-3、Feature 文件 Gherkin 场景与步骤代码一致（AC-6 补充 FlagEmbedding 校验）、新增统一错误处理策略章节；第4轮对抗性审查无新发现；第5轮最终精修通过
- v1.2.2: 5轮审查修订第2轮 — 代码：FP16 GPU 计算能力检测（Pascal 架构安全降级）、generate_embedding 补充表格文本提取、BGE3EmbeddingService 显式实现 EmbeddingServicePort、契约测试补充 dense_search_service 接口类型验证；文档：search_sparse filter 不对称说明、EmbeddingConfig 双定义同步风险、性能基准统计局限性
- v1.2.1: 5轮审查修订第1轮 — 修正 L2 归一化科学描述、空文本处理规范（统一 ValueError）、SentenceTransformers 选型描述、Task 依赖图矛盾；代码修复 composition_root 版本号 v1.0.0→v1.1.0、契约测试补充 encode_sparse、清理孤儿 pyc；新增 sync/async 兼容策略分析、batch_size 说明、表格忽略限制、依赖残留说明
- v1.2.0: 嵌入模型 API 化扩展 — 新增 Task 7-10
- v1.1.0: FlagEmbedding 迁移 — SentenceTransformers→BGEM3FlagModel，新增 encode_sparse()
- v1.0.0: 创建故事文件（初始 SentenceTransformers 实现）
