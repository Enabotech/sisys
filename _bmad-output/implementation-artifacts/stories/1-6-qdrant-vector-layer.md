# Story 1.6: Qdrant Vector Layer

**Status:** `done`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。
>
> **🔧 技术约束（v1.0）：**
> 1. **复用 Story 1.3/1.4/1.5 配置模式** — `src/infrastructure/config/qdrant.py` 新建，参考 `PostgreSQLConfig`/`RedisConfig` 模式
> 2. **领域层零 Qdrant 污染** — Qdrant 客户端/Collection 管理仅位于基础设施层，领域层使用 `VectorStorage` Protocol 接口
> 3. **Collection 命名规范** — `sisys:{collection_type}:{namespace}`（如 `sisys:documents:finance`）
> 4. **向量维度固定** — 1024 维（bge-m3 嵌入模型），COSINE 相似度度量
> 5. **多租户隔离** — 按业务域或项目分离 Collection，支持 Collection 级别访问控制
> 6. **Qdrant 客户端库** — PyPI 包名 `qdrant-client`，Python 导入 `qdrant_client.AsyncQdrantClient`

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实现 Qdrant 向量存储层（L3 存储），
**So that** 系统可以存储嵌入向量并执行混合检索（Dense+Sparse），满足检索延迟 P95<800ms 的性能目标。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 3（六层存储架构）的第三个故事，在 Story 1.5（PostgreSQL 关系存储层）基础上实现 L3 向量存储层。Qdrant 作为六层存储架构的向量存储核心，承担以下关键职责：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **嵌入向量存储** | 文档/查询的语义嵌入持久化（bge-m3，1024 维） | Collection 命名规范，COSINE 度量 |
| **Dense 语义检索** | 基于向量相似度的文档检索（Top-K） | P95<500ms，支持 payload 过滤 |
| **BM25 稀疏检索** | 关键词匹配稀疏检索，与 Dense 检索双路召回 | BM25 payload 过滤，延迟<200ms |
| **混合检索基础** | Dense + Sparse 双路召回基座，为 Story 3.1/3.4 提供基础 | RRF 融合排序基础设施 |
| **多租户隔离** | 按业务域分离 Collection，数据隔离 | Collection 级别访问控制 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 3: 六层存储架构

**覆盖 FR:**
- FR-AR-04: 仓储模式（通过 VectorStorage 接口实现）
- NFR-PERF-01: 检索延迟 P95<800ms（MVP 目标）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: Qdrant 连接池与客户端抽象

**Given** Story 1.3/1.4/1.5 已实现 RedisConfig/PostgreSQLConfig 配置模式
**When** 实现 Qdrant 配置模型与通用客户端
**Then** 支持连接池懒初始化、健康检查、优雅关闭
**And** Qdrant 异步客户端（`qdrant-client` 官方异步 API）

**验证标准/Validation Criteria:**
- [x] QdrantConfig 配置模型定义（`src/infrastructure/config/qdrant.py`）
  - 字段: `host: str`, `port: int`, `grpc_port: int`, `api_key: Optional[str]`, `https: bool = False`
  - 字段: `timeout: float = 30.0`, `max_retries: int = 3`
  - 方法: `from_env() -> QdrantConfig`（从环境变量读取）
- [x] QdrantClient 通用接口定义（`src/infrastructure/storage/qdrant/qdrant_manager.py`）
  - 方法: `get_async_client() -> AsyncQdrantClient`, `health_check() -> bool`, `close() -> None`
  - 懒初始化（首次调用时创建客户端）
  - 健康检查（执行 `GET /collections` 验证连接）
  - **客户端库**: PyPI 包 `qdrant-client`，Python 导入 `from qdrant_client import AsyncQdrantClient`
- [x] 单元测试覆盖客户端创建、复用、关闭、健康检查场景

### AC-2: Collection 管理与多租户隔离

**Given** Qdrant 客户端已实现
**When** 实现 Collection 创建、删除、查询管理
**Then** 支持按业务域自动创建 Collection
**And** 多租户隔离（Collection 级别分离）

**验证标准/Validation Criteria:**
- [x] CollectionConfig 数据模型定义（`src/infrastructure/storage/qdrant/models.py`）
  - 字段: `name: str`, `vector_size: int = 1024`, `distance: str = "Cosine"`, `shard_number: int = 1`, `replication_factor: int = 1`
  - 字段: `on_disk: bool = False`（向量是否磁盘存储）, `hnsw_config: dict`（HNSW 索引配置）
- [x] CollectionManager 接口定义（`src/domain/repositories/vector_storage.py`）
  - 方法: `create_collection(name: str, config: CollectionConfig) -> bool`, `delete_collection(name: str) -> bool`, `collection_exists(name: str) -> bool`, `list_collections() -> list[str]`
- [x] QdrantCollectionManager 实现（`src/infrastructure/storage/qdrant/collection_manager.py`）
  - 使用 Qdrant 异步客户端
  - Collection 命名规范: `sisys:{collection_type}:{namespace}`
  - HNSW 索引配置: `m=16`, `ef_construct=128`, `full_scan_threshold=10000`
- [x] 单元测试覆盖创建、删除、查询、列表场景
- [x] Collection 已存在时返回 False（不抛出异常）

### AC-3: 向量点存储与检索（Dense Search）

**Given** Collection 管理已实现
**When** 实现向量点的插入、查询、删除
**Then** 支持批量插入向量（带 payload 元数据）
**And** Dense 语义检索（Top-K 相似度查询，支持 payload 过滤）

**验证标准/Validation Criteria:**
- [x] VectorPoint 数据模型定义（`src/infrastructure/storage/qdrant/models.py`）
  - 字段: `id: str`, `vector: list[float]`, `payload: dict`, `created_at: datetime`
  - Payload 字段规范: `document_id: str`, `chunk_id: str`, `business_domain: str`, `content_hash: str`
- [x] VectorStorage 接口定义（`src/domain/repositories/vector_storage.py`）
  - 方法: `upsert_points(collection: str, points: list[VectorPoint]) -> bool`, `search(collection: str, query_vector: list[float], limit: int = 10, filter_payload: dict = None) -> list[VectorPoint]`, `delete_points(collection: str, point_ids: list[str]) -> bool`, `get_point(collection: str, point_id: str) -> Optional[VectorPoint]`
- [x] QdrantVectorStorage 实现（`src/infrastructure/storage/qdrant/vector_storage.py`）
  - 使用 `upsert` API 批量插入（支持原子操作）
  - 使用 `search` API 执行 Dense 检索（COSINE 相似度）
  - 支持 payload 过滤（使用 Qdrant `Filter` 对象，支持 `match`/`range` 等条件）
    - 示例: `{"must": [{"key": "business_domain", "match": {"value": "finance"}}]}`
  - **HNSW 查询参数建议**: `ef=64~128`（与 `ef_construct=128` 匹配，平衡性能与准确率）
- [x] 批量插入测试（1000 点，延迟<5s）
- [x] 单元测试覆盖插入、查询、删除、过滤场景

### AC-4: BM25 稀疏检索基础

**Given** Dense 语义检索已实现
**When** 实现 BM25 稀疏检索基础设施
**Then** 支持关键词匹配的稀疏检索
**And** 为 Story 3.1/3.4 的 RRF 融合排序提供基础

**验证标准/Validation Criteria:**
- [x] SparseVector 数据模型定义（`src/infrastructure/storage/qdrant/models.py`）
  - 字段: `indices: list[int]`（词项 ID 列表）, `values: list[float]`（词项权重 TF-IDF）
- [x] QdrantVectorStorage 扩展（`src/infrastructure/storage/qdrant/vector_storage.py`）
  - 方法: `search_sparse(collection: str, sparse_vector: SparseVector, limit: int = 10, filter_payload: dict = None) -> list[VectorPoint]`
  - 使用 Qdrant `search` API 的 `sparse_vector` 参数
- [x] BM25 payload 构建工具（`src/infrastructure/storage/qdrant/bm25_builder.py`）
  - 方法: `build_sparse_vector(text: str) -> SparseVector`（文本→BM25 向量）
  - **MVP 实现使用简单 TF-IDF 计算**（不依赖外部 BM25 库，避免额外依赖）
  - **⚠️ 后续优化**: Story 3.4 RRF 融合排序时替换为 Qdrant 原生 BM25 实现
- [x] 单元测试覆盖稀疏检索、payload 构建场景

### AC-5: 架构约束验证测试就绪

**Given** Qdrant 向量存储层已实现
**When** 运行架构约束验证测试
**Then** 领域层不依赖任何 Qdrant 实现
**And** 依赖方向正确（基础设施层→应用层→领域层）
**And** Ruff 检查通过（严重错误=0）
**And** MyPy 类型检查通过（错误率<5%）

**验证标准/Validation Criteria:**
- [x] 领域层无 Qdrant 导入验证（扫描 `src/domain/` 目录）
- [x] 依赖方向测试通过（使用 `import-linter`）
- [x] Collection 命名规范验证（所有 Collection 遵循 `sisys:{type}:{namespace}`）
- [x] Ruff 检查通过（0 错误）
- [x] MyPy 类型检查通过（0 问题）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 配置模型 (Configuration Models)
- [x] QdrantConfig 定义（`src/infrastructure/config/qdrant.py`）
  - 字段: host, port, grpc_port, api_key, https, timeout, max_retries

#### 数据模型 (Data Models) — 基础设施层
- [x] CollectionConfig 定义（`src/infrastructure/storage/qdrant/models.py`）
  - 字段: name, vector_size(1024), distance("Cosine"), shard_number, replication_factor, on_disk, hnsw_config
- [x] VectorPoint 定义（`src/infrastructure/storage/qdrant/models.py`）
  - 字段: id, vector(1024 维 list[float]), payload(dict), created_at
  - Payload 规范: document_id, chunk_id, business_domain, content_hash
- [x] SparseVector 定义（`src/infrastructure/storage/qdrant/models.py`）
  - 字段: indices(list[int]), values(list[float])

#### 仓储接口 (Repository Interfaces)
- [x] CollectionManager 接口（`src/domain/repositories/vector_storage.py`）
- [x] VectorStorage 接口（`src/domain/repositories/vector_storage.py`）

#### 验收标准 Gherkin (Acceptance Tests)
- [x] 功能测试文件：`tests/acceptance/test_story_1.6.feature`
- [ ] 覆盖场景:
  - Collection 创建/删除/查询
  - 向量点插入/查询/删除
  - Dense 语义检索（Top-K，payload 过滤）
  - BM25 稀疏检索基础
  - 多租户隔离验证
  - 领域层零 Qdrant 依赖

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

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | Qdrant 连接池 | 客户端创建、复用、关闭、健康检查 | `test_qdrant_client.py` | Task 1 |
| **TDD 单元测试** | Collection 管理 | 创建、删除、查询、列表、命名规范 | `test_collection_manager.py` | Task 2 |
| **TDD 单元测试** | 向量点存储 | 插入、查询、删除、payload 验证 | `test_vector_storage.py` | Task 3 |
| **TDD 单元测试** | Dense 语义检索 | Top-K 相似度查询、payload 过滤 | `test_dense_search.py` | Task 3 |
| **TDD 单元测试** | BM25 稀疏检索 | 稀疏向量构建、检索、payload 构建 | `test_bm25_builder.py`, `test_sparse_search.py` | Task 4 |
| **TDD 集成测试** | Qdrant 端到端 | 完整存储/检索流程 | `test_qdrant_integration.py` | Task 5 |
| **SDD 架构验证** | 领域层零依赖 | 领域层无 Qdrant 导入 | `test_architecture_constraints.py` | Task 6 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [x] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [x] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）- **P1 阻断门禁**
- [x] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）- **P1 阻断门禁**（接口定义）
- [x] **关键路径覆盖率 100%**（所有分支覆盖）

> ⚠️ **骨架 Story 覆盖率豁免：** 本 Story 为存储层骨架实现（非空接口），需达到标准覆盖率要求。

#### 代码质量门禁
- [x] **Ruff 检查通过**（`ruff check src/`）
- [x] **MyPy 类型检查通过**（`mypy src/`）
- [x] **无 P0/P1 级别问题**（代码审查）
- [x] **预提交 Hooks 通过**（`pre-commit run --all-files`）

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | Qdrant 连接池与客户端 | Task 1 | QdrantConfig + QdrantClient | `test_qdrant_client.py` |
| AC-2 | Collection 管理与多租户 | Task 2 | CollectionManager + QdrantCollectionManager | `test_collection_manager.py` |
| AC-3 | 向量点存储与 Dense 检索 | Task 3 | VectorPoint + VectorStorage + QdrantVectorStorage | `test_vector_storage.py`, `test_dense_search.py` |
| AC-4 | BM25 稀疏检索基础 | Task 4 | SparseVector + BM25Builder + search_sparse | `test_bm25_builder.py`, `test_sparse_search.py` |
| AC-5 | 架构约束验证 | Task 6 | 领域层零 Qdrant 依赖验证 | `test_architecture_constraints.py` |
| AC-1~AC-4 | Qdrant 端到端集成测试 | Task 5 | 完整存储/检索流程验证 | `test_qdrant_integration.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-5

> **目的：** 在进入代码实现前，明确配置模型、数据模型、接口、验收标准。

- [x] Subtask: 定义 QdrantConfig 配置模型
- [x] Subtask: 定义 CollectionConfig 数据模型
- [x] Subtask: 定义 VectorPoint 数据模型
- [x] Subtask: 定义 SparseVector 数据模型
- [x] Subtask: 定义 CollectionManager 接口
- [x] Subtask: 定义 VectorStorage 接口
- [x] Subtask: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1.6.feature`
- [x] Subtask: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕
- [x] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: Qdrant 连接池与客户端抽象

**关联 AC:** AC-1

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**
> **📌 复用说明:** 参考 Story 1.4 的 `RedisConfig` + `_get_pool()` 模式，本 Task 采用相同的配置模式与懒初始化策略。

#### TDD 循环 A：QdrantConfig 配置模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_qdrant_config.py`（字段验证、默认值、from_env 支持） |
| 🟢 绿 | 实现 `QdrantConfig` dataclass 最小代码 |
| 🔄 重构 | 添加类型注解、docstring、from_env 支持 |

- [x] Subtask: 🔴 红 — 编写 QdrantConfig 失败测试
- [x] Subtask: 🟢 绿 — 实现 QdrantConfig 最小代码
- [x] Subtask: 🔄 重构 — 优化 QdrantConfig 代码

#### TDD 循环 B：QdrantClient 通用接口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_qdrant_client.py`（客户端创建、健康检查、关闭） |
| 🟢 绿 | 实现 `QdrantManager` 类最小代码 |
| 🔄 重构 | 添加懒初始化、异常处理、健康检查 |

- [x] Subtask: 🔴 红 — 编写 QdrantClient 失败测试
- [x] Subtask: 🟢 绿 — 实现 QdrantClient 最小代码
- [x] Subtask: 🔄 重构 — 优化 QdrantClient 代码

**完成标准/Definition of Done:**
- [ ] QdrantConfig 和 QdrantClient 实现完成
- [ ] TDD 循环全部通过
- [ ] 基础设施层覆盖率≥10%

---

### Task 2: Collection 管理与多租户隔离

**关联 AC:** AC-2

> ⚠️ **本 Task 包含自己的 TDD 循环。**

#### TDD 循环 A：CollectionConfig 数据模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_collection_config.py`（字段验证、HNSW 配置） |
| 🟢 绿 | 实现 `CollectionConfig` dataclass 最小代码 |
| 🔄 重构 | 添加默认值、类型注解、docstring |

- [x] Subtask: 🔴 红 — 编写 CollectionConfig 失败测试
- [x] Subtask: 🟢 绿 — 实现 CollectionConfig 最小代码
- [x] Subtask: 🔄 重构 — 优化 CollectionConfig 代码

#### TDD 循环 B：CollectionManager 接口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_collection_manager_interface.py`（接口类型检查） |
| 🟢 绿 | 实现 `CollectionManager` Protocol 接口 |
| 🔄 重构 | 添加类型注解、方法签名 |

- [x] Subtask: 🔴 红 — 编写 CollectionManager 接口失败测试
- [x] Subtask: 🟢 绿 — 实现 CollectionManager 接口
- [x] Subtask: 🔄 重构 — 优化接口定义

#### TDD 循环 C：QdrantCollectionManager 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_qdrant_collection_manager.py`（创建、删除、查询、命名规范） |
| 🟢 绿 | 实现 `QdrantCollectionManager` 类最小代码 |
| 🔄 重构 | 添加 Collection 已存在处理、异常处理、HNSW 配置 |

- [x] Subtask: 🔴 红 — 编写 QdrantCollectionManager 失败测试
- [x] Subtask: 🟢 绿 — 实现 QdrantCollectionManager 最小代码
- [x] Subtask: 🔄 重构 — 优化 QdrantCollectionManager 代码

**完成标准/Definition of Done:**
- [ ] CollectionConfig、CollectionManager 接口、QdrantCollectionManager 实现完成
- [ ] TDD 循环全部通过
- [x] Collection 命名规范验证（`sisys:{type}:{namespace}`）
- [ ] 基础设施层覆盖率≥25%

---

### Task 3: 向量点存储与检索（Dense Search）

**关联 AC:** AC-3

> ⚠️ **本 Task 包含自己的 TDD 循环。**

#### TDD 循环 A：VectorPoint 数据模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_vector_point.py`（字段验证、payload 规范） |
| 🟢 绿 | 实现 `VectorPoint` dataclass 最小代码 |
| 🔄 重构 | 添加 payload 字段验证、类型注解 |

- [x] Subtask: 🔴 红 — 编写 VectorPoint 失败测试
- [x] Subtask: 🟢 绿 — 实现 VectorPoint 最小代码
- [x] Subtask: 🔄 重构 — 优化 VectorPoint 代码

#### TDD 循环 B：VectorStorage 接口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_vector_storage_interface.py`（接口类型检查） |
| 🟢 绿 | 实现 `VectorStorage` Protocol 接口 |
| 🔄 重构 | 添加类型注解、方法签名 |

- [x] Subtask: 🔴 红 — 编写 VectorStorage 接口失败测试
- [x] Subtask: 🟢 绿 — 实现 VectorStorage 接口
- [x] Subtask: 🔄 重构 — 优化接口定义

#### TDD 循环 C：QdrantVectorStorage 实现（含 Dense 检索）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_qdrant_vector_storage.py`（upsert、search、delete、get、payload 过滤） |
| 🟢 绿 | 实现 `QdrantVectorStorage` 类最小代码 |
| 🔄 重构 | 添加批量插入优化、payload 过滤构建、异常处理 |

- [x] Subtask: 🔴 红 — 编写 QdrantVectorStorage 失败测试
- [x] Subtask: 🟢 绿 — 实现 QdrantVectorStorage 最小代码
- [x] Subtask: 🔄 重构 — 优化 QdrantVectorStorage 代码

#### TDD 循环 D：Dense 语义检索专项测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_dense_search.py`（Top-K 相似度查询、边界条件、空 Collection） |
| 🟢 绿 | 实现 search 方法核心逻辑 |
| 🔄 重构 | 添加相似度阈值过滤、结果排序优化 |

- [x] Subtask: 🔴 红 — 编写 Dense 检索失败测试
- [x] Subtask: 🟢 绿 — 实现 Dense 检索最小代码
- [x] Subtask: 🔄 重构 — 优化 Dense 检索代码

**完成标准/Definition of Done:**
- [ ] VectorPoint、VectorStorage 接口、QdrantVectorStorage（含 Dense 检索）实现完成
- [ ] TDD 循环全部通过
- [x] 批量插入测试（1000 点，延迟<5s）
- [ ] 基础设施层覆盖率≥45%

---

### Task 4: BM25 稀疏检索基础

**关联 AC:** AC-4

> ⚠️ **本 Task 包含自己的 TDD 循环。**
> **📌 MVP 实现说明:** 本 Story 仅实现 BM25 稀疏检索基础设施，RRF 融合排序在 Story 3.4 实现。

#### TDD 循环 A：SparseVector 数据模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_sparse_vector.py`（字段验证、indices/values 长度匹配） |
| 🟢 绿 | 实现 `SparseVector` dataclass 最小代码 |
| 🔄 重构 | 添加字段验证、类型注解 |

- [x] Subtask: 🔴 红 — 编写 SparseVector 失败测试
- [x] Subtask: 🟢 绿 — 实现 SparseVector 最小代码
- [x] Subtask: 🔄 重构 — 优化 SparseVector 代码

#### TDD 循环 B：BM25Builder 工具类

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_bm25_builder.py`（文本→稀疏向量转换、空文本、特殊字符） |
| 🟢 绿 | 实现 `BM25Builder` 类最小代码（简单 TF-IDF） |
| 🔄 重构 | 添加停用词过滤、词干提取、缓存优化 |

- [x] Subtask: 🔴 红 — 编写 BM25Builder 失败测试
- [x] Subtask: 🟢 绿 — 实现 BM25Builder 最小代码
- [x] Subtask: 🔄 重构 — 优化 BM25Builder 代码

#### TDD 循环 C：QdrantVectorStorage 扩展（search_sparse）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_sparse_search.py`（稀疏检索、payload 过滤、空结果） |
| 🟢 绿 | 实现 `search_sparse` 方法 |
| 🔄 重构 | 添加结果排序、异常处理 |

- [x] Subtask: 🔴 红 — 编写稀疏检索失败测试
- [x] Subtask: 🟢 绿 — 实现 search_sparse 最小代码
- [x] Subtask: 🔄 重构 — 优化 search_sparse 代码

**完成标准/Definition of Done:**
- [ ] SparseVector、BM25Builder、search_sparse 实现完成
- [ ] TDD 循环全部通过
- [ ] 基础设施层覆盖率≥60%

---

### Task 5: Qdrant 端到端集成测试

**关联 AC:** AC-1 ~ AC-4

> **性质说明：** 本 Task 是集成测试，验证所有 Qdrant 服务的端到端流程。

#### 集成测试实现

- [x] Subtask: 创建 `tests/integration/test_qdrant_integration.py`
- [x] Subtask: 实现 Collection 生命周期端到端测试（创建→验证→删除）
- [x] Subtask: 实现向量点存储端到端测试（插入→查询→验证→删除）
- [x] Subtask: 实现 Dense 语义检索端到端测试（写入→相似度查询→Top-K 验证）
- [x] Subtask: 实现 BM25 稀疏检索端到端测试（文本→稀疏向量→检索→验证）
- [x] Subtask: 实现多租户隔离端到端测试（不同 Collection 数据隔离验证）

**完成标准/Definition of Done:**
- [ ] 所有集成测试通过
- [ ] 测试输出完整的流程验证报告
- [ ] 基础设施层覆盖率≥75%

---

### Task 6: 架构约束验证测试

**关联 AC:** AC-5

> **性质说明：** 本 Task 验证 Qdrant 向量存储层实现是否符合六边形架构约束。

#### 架构验证测试实现

- [x] Subtask: 创建 `tests/unit/infrastructure/test_architecture_constraints.py`
- [x] Subtask: 实现领域层零 Qdrant 依赖验证（扫描 `src/domain/` 目录）
- [x] Subtask: 实现依赖方向验证（使用 `import-linter`）
- [x] Subtask: 实现 Collection 命名规范验证（所有 Collection 遵循 `sisys:{type}:{namespace}`）
- [x] Subtask: 运行 Ruff 检查（`ruff check src/`，0 错误）
- [x] Subtask: 运行 MyPy 类型检查（`mypy src/`，0 问题）

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **六层存储架构:** L3 向量存储层（Qdrant 1.7+）存储嵌入向量、混合检索 payload
- **向量维度:** 1024 维（bge-m3 嵌入模型），COSINE 相似度度量
- **Collection 命名规范:** `sisys:{collection_type}:{namespace}`（如 `sisys:documents:finance`）
- **HNSW 索引配置:** `m=16`, `ef_construct=128`, `full_scan_threshold=10000`
- **延迟预算:** P95<500ms（初检 200ms + 精排 250ms + 融合 50ms）
- **多租户隔离:** 按业务域或项目分离 Collection，支持 Collection 级别访问控制
- **领域层零依赖:** 领域层仅定义接口，不依赖任何 Qdrant 实现细节

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 决策 4 (ADR-004): 六层存储架构

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **Qdrant 1.7+** | Rust 实现高性能、原生 COSINE/BM25 支持、HNSW 索引、payload 过滤、多租户 | 相对较新、生态不如 Milvus 成熟 | ✅ 9/10 |
| Milvus 2.x | 成熟度高、分布式扩展 | 部署复杂、对 MVP 过重 | 7/10 |
| pgvector | 与 PostgreSQL 集成、零新依赖 | 性能较低、无原生 BM25 | 5/10 |

**决策理由：**
1. Qdrant 基于 Rust 实现，性能优异，满足检索延迟 P95<500ms 目标
2. 原生支持 COSINE 相似度与 BM25 稀疏检索，适合混合检索场景
3. 内置 HNSW 索引，支持高效 Top-K 查询
4. 提供完善的 payload 过滤能力，支持业务域/时间范围等多维过滤
5. 多租户隔离简单（Collection 级别分离）

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   └── repositories/
│   │       └── vector_storage.py       # CollectionManager + VectorStorage 接口
│   └── infrastructure/
│       ├── config/
│       │   └── qdrant.py               # QdrantConfig 配置模型
│       └── storage/
│           └── qdrant/
│               ├── __init__.py
│               ├── client.py           # QdrantClient 通用接口
│               ├── models.py           # CollectionConfig/VectorPoint/SparseVector
│               ├── collection_manager.py # QdrantCollectionManager 实现
│               ├── vector_storage.py   # QdrantVectorStorage 实现（含 Dense/Sparse 检索）
│               └── bm25_builder.py     # BM25Builder 工具类
├── tests/
│   ├── unit/
│   │   ├── infrastructure/
│   │   │   ├── test_qdrant_config.py
│   │   │   ├── test_qdrant_client.py
│   │   │   ├── test_collection_config.py
│   │   │   ├── test_collection_manager.py
│   │   │   ├── test_vector_point.py
│   │   │   ├── test_sparse_vector.py
│   │   │   ├── test_vector_storage.py
│   │   │   ├── test_dense_search.py
│   │   │   ├── test_bm25_builder.py
│   │   │   ├── test_sparse_search.py
│   │   │   └── test_architecture_constraints.py
│   │   └── domain/
│   │       ├── test_collection_manager_interface.py
│   │       └── test_vector_storage_interface.py
│   ├── integration/
│   │   └── test_qdrant_integration.py
│   └── acceptance/
│       └── test_story_1.6.feature
└── docs/
    └── infrastructure/
        └── qdrant_vector_layer_guide.md # Qdrant 向量层实施指南
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.5-PostgreSQL Relational Layer](./1-5-postgresql-relational-layer.md)

**关键学习/Key Learnings:**
1. **配置模式复用** — Story 1.3/1.4/1.5 已建立 `XxxConfig` + `from_env()` 模式，本 Story 沿用
2. **领域层接口与基础设施层实现分离** — 领域层定义同步接口（Protocol），基础设施层实现
3. **懒初始化连接池** — 首次调用时创建客户端，避免启动时连接失败阻塞业务
4. **多租户隔离策略** — Collection 级别分离（与 PostgreSQL Schema per Tenant 一致）
5. **架构约束验证** — 领域层零外部依赖是硬约束，必须在架构验证测试中覆盖

**应用到本故事/Applied to This Story:**
- [x] QdrantConfig 采用 Story 1.4/1.5 相同的配置模式
- [x] CollectionManager/VectorStorage 接口定义在领域层（Protocol），实现在基础设施层
- [x] QdrantClient 采用懒初始化模式（与 Story 1.5 PostgreSQLManager 一致）
- [x] Collection 命名规范统一为 `sisys:{type}:{namespace}`，与 Story 1.4 Redis 键命名规范（`sisys:{namespace}:{key}`）保持一致
- [x] 架构约束测试验证领域层无 Qdrant 导入

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Qwen Code |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-04-14 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `docs/developer/story-template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-5-postgresql-relational-layer.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] Story 需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] 前一个故事学习经验整合
- [x] 状态设置为 `backlog`（等待 dev-story 实施）
- [ ] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-6-qdrant-vector-layer.md`

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.6 |
| **Story Key** | 1-6-qdrant-vector-layer |
| **File** | `_bmad-output/implementation-artifacts/stories/1-6-qdrant-vector-layer.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 3: 六层存储架构 |
| **优先级** | P0 |
| **覆盖 FR** | FR-AR-04（仓储模式）, NFR-PERF-01（检索延迟） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-6，含 SDD 规范 + TDD 循环）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 ~ AC-5）
3. [x] Architecture constraints extracted 架构约束已提取（六层存储、HNSW 配置、多租户隔离）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（配置模式复用、接口分离、懒初始化）
5. [x] Sprint status synced to `ready-for-dev`（已与 sprint-status.yaml 同步）

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 运行 `dev-story` 开始实施
- [x] 运行 `code-review` 进行代码审查

- [x] 运行 `/bmad:tea:automate` 生成测试（可选）
- [x] 部署 qdrant 实例后验证集成测试（替换 mock 为真实实例）
- [x] 部署 qdrant 实例后最终完成验收测试（禁止使用 mock / fake）

---

**模板版本/Template Version:** 2.0.0
**创建日期/Created:** 2026-04-14
**最后更新/Last Updated:** 2026-04-17
**更新说明:** 基于 story-template.md 创建，整合 architecture.md/epics_v1.0.md 上下文
- v1.1: 实施完成，验收测试通过
- v1.2: 修复 Qdrant v1.7.x API 兼容性问题

### v1.2 修复详情

#### Qdrant v1.7.x API 兼容性修复

| 文件 | 问题 | 修复方案 |
|------|------|---------|
| `src/infrastructure/storage/qdrant/vector_storage.py` | `query_points` API 已废弃 | 改用 `search` 方法 |
| `src/infrastructure/storage/qdrant/vector_storage.py` | `response.points` 访问方式变更 | 直接迭代 `response` 对象 |
| `src/infrastructure/storage/qdrant/vector_storage.py` | Qdrant v1.7.x 要求 ID 为无符号整数 | 添加 `_normalize_point_id()` 方法处理字符串 ID |

**测试结果：** 集成测试通过
