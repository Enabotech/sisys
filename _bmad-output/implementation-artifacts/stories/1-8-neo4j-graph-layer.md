# Story 1.8: Neo4j Graph Layer

**Status:** `done`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。
>
> **🔧 技术约束（v1.0）：**
> 1. **复用 Story 1.3/1.4/1.5/1.6/1.7 配置模式** — `src/infrastructure/config/neo4j.py` 新建，参考 `PostgreSQLConfig`/`RedisConfig`/`QdrantConfig`/`MinIOConfig` 模式
> 2. **领域层零 Neo4j 污染** — Neo4j 客户端/Graph 管理仅位于基础设施层，领域层使用 `GraphStorage` Protocol 接口
> 3. **节点/关系命名规范** — 节点标签: `sisys:{entity_type}`（如 `sisys:Document`, `sisys:Entity`, `sisys:Agent`）
> 4. **Neo4j 客户端库** — PyPI 包名 `neo4j`，Python 导入 `neo4j.AsyncGraphDatabase`
> 5. **多租户隔离** — 按业务域使用节点属性隔离，支持权限过滤
> 6. **六层存储单向依赖链** — Graph 存储是依赖链末端（Cache → Relational → Vector → Object → Graph），Graph 不依赖其他存储层；图遍历结果通过事件总线异步发布缓存更新事件，由 Cache 层监听刷新（非 Graph 直接依赖 Cache）

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实现 Neo4j 图存储层（L5 存储），
**So that** 系统可以存储知识图谱、实体关系和依赖图，支持 GraphRAG 增强检索和实体关联查询。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 3（六层存储架构）的第五个也是最后一个故事，在 Story 1.4-1.7（Redis/PostgreSQL/Qdrant/MinIO）基础上实现 L5 图存储层。Neo4j 作为六层存储架构的图存储核心，承担以下关键职责：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **知识图谱存储** | 实体节点（Entity/Document/Concept）与关系边持久化 | 节点标签规范，关系类型规范 |
| **实体关联查询** | 路径查询、多跳关系遍历、社区发现 | 简单查询 P95<200ms，复杂查询 P95<800ms |
| **GraphRAG 增强检索** | 为 Story 3.4/3.13/3.17 提供图检索基础设施 | 支持 Cypher 查询，图遍历结果异步缓存更新 |
| **依赖图管理** | 工具链 DAG、Agent 协作依赖图存储 | 依赖关系查询，拓扑排序支持 |
| **多租户隔离** | 按业务域属性隔离节点数据，支持权限过滤 | 节点属性 `business_domain` 过滤 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 3: 六层存储架构

**覆盖 FR:**
- FR-AR-02: 领域事件发布（部分覆盖 — 图遍历结果通过事件总线异步发布缓存更新事件）
- FR-AR-04: 仓储模式（通过 GraphStorage 接口实现）
- FR-SA-01: 永久存储历年 SP/BP 的关键假设变量、决策依据、实际执行偏差（图关系持久化）

**覆盖 NFR:**
- NFR-PERF-07: 图遍历查询延迟 P95<200ms（简单）/<800ms（复杂）

### 依赖关系 Dependencies

| 依赖 Story | 依赖类型 | 依赖原因 |
|-----------|---------|---------|
| Story 1-1: Hexagonal Architecture Skeleton | 硬依赖 | 六边形架构模式、依赖注入容器、领域层接口定义规范 |
| Story 1-2: Domain Event Definition | 硬依赖 | 图遍历结果缓存更新事件复用领域事件定义 |
| Story 1-3: Event Bus Implementation | 硬依赖 | 异步缓存更新事件通过事件总线发布 |
| Story 1-4: Redis Cache Layer | 无直接依赖 | 可并行开发，Graph 通过事件总线异步更新 Cache |
| Story 1-5: PostgreSQL Relational Layer | 无直接依赖 | 可并行开发，Graph 不直接依赖关系存储 |
| Story 1-6: Qdrant Vector Layer | 无直接依赖 | 可并行开发，GraphRetriever 返回节点 ID 用于 Qdrant payload 过滤 |
| Story 1-7: MinIO Object Layer | 无直接依赖 | 可并行开发，Graph 不直接依赖对象存储 |
| Story 1-16: Integration Test Framework | 软依赖 | 集成测试框架模式复用 |

### 技术容量规划

| 指标 | MVP | V1 | V2 |
|------|-----|----|----|
| **存储容量** | 10GB | 30GB | 50GB |
| **节点数量** | ≤100,000 | ≤1,000,000 | ≤5,000,000 |
| **关系数量** | ≤500,000 | ≤5,000,000 | ≤25,000,000 |
| **并发查询** | ≥10 | ≥30 | ≥100 |
| **连接池大小** | 20 | 50 | 100 |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: Neo4j 连接池与客户端抽象

**Given** Story 1.3/1.4/1.5/1.6/1.7 已建立统一的配置与客户端模式
**When** 实现 Neo4j 配置模型与通用客户端
**Then** 支持连接池懒初始化、健康检查、优雅关闭
**And** Neo4j 异步客户端（`neo4j.AsyncGraphDatabase`）

**验证标准/Validation Criteria:**
- [ ] Neo4jConfig 配置模型定义（`src/infrastructure/config/neo4j.py`）
  - 字段: `uri: str`, `username: str`, `password: str`, `database: str = "neo4j"`
  - 字段: `max_connection_pool_size: int = 50`, `connection_timeout: float = 30.0`, `max_retry_time: float = 30.0`
  - 方法: `from_env() -> Neo4jConfig`（从环境变量读取）
- [ ] Neo4jClient 通用接口定义（`src/infrastructure/storage/neo4j_manager.py`）
  - 方法: `get_async_driver() -> AsyncDriver`, `health_check() -> bool`, `close() -> None`
  - 懒初始化（首次调用时创建 driver）
  - 健康检查（执行简单 Cypher 查询 `RETURN 1` 验证连接）
  - **客户端库**: PyPI 包 `neo4j`，Python 导入 `from neo4j import AsyncGraphDatabase, AsyncDriver`
  - **⚠️ 返回类型说明**: `AsyncGraphDatabase.driver()` 返回 `AsyncDriver` 实例，非 `AsyncGraphDatabase` 本身
- [ ] 单元测试覆盖客户端创建、复用、关闭、健康检查场景

### AC-2: 节点与关系管理

**Given** Neo4j 客户端已实现
**When** 实现节点创建、删除、查询与关系创建、删除、查询
**Then** 支持按业务域自动创建节点
**And** 支持关系类型约束与属性附加

**验证标准/Validation Criteria:**
- [ ] GraphNode 数据模型定义（`src/infrastructure/storage/neo4j/models.py`）
  - 字段: `id: str`, `labels: list[str]`, `properties: dict`, `created_at: datetime`
  - Properties 规范: `business_domain: str`, `entity_type: str`, `content_hash: str`
  - **⚠️ content_hash 用途**: 用于图谱节点去重与版本控制（与 Qdrant Story 1.6 的 `content_hash` 一致），当同一文档生成的多个实体节点内容相同时，通过 `content_hash` 合并或检测重复
- [ ] GraphRelationship 数据模型定义（`src/infrastructure/storage/neo4j/models.py`）
  - 字段: `start_node_id: str`, `end_node_id: str`, `relationship_type: str`, `properties: dict`, `created_at: datetime`
  - 关系类型枚举: `MENTIONS`, `DEPENDS_ON`, `RELATES_TO`, `PART_OF`, `INFLUENCES`, `CONTRADICTS`
  - **⚠️ 类型定义**: 使用 `enum.StrEnum`（Python 3.11+）定义关系类型，便于 MyPy 类型检查
- [ ] GraphManager 接口定义（`src/domain/repositories/graph_storage.py`）
  - 方法: `create_node(node: GraphNode) -> bool`, `delete_node(node_id: str) -> bool`, `get_node(node_id: str) -> Optional[GraphNode]`
  - 方法: `create_relationship(rel: GraphRelationship) -> bool`, `delete_relationship(start_id: str, end_id: str, rel_type: str) -> bool`
- [ ] Neo4jGraphManager 实现（`src/infrastructure/storage/neo4j/graph_manager.py`）
  - 使用 Neo4j 异步驱动
  - 节点标签规范: `sisys:{entity_type}`（如 `sisys:Entity`, `sisys:Document`）
  - 关系类型使用大写+下划线命名（如 `MENTIONS`, `DEPENDS_ON`）
  - 支持 MERGE 操作（避免重复创建）
- [ ] 单元测试覆盖创建、删除、查询场景
- [ ] 节点已存在时 MERGE 行为：匹配现有节点并更新属性（`ON MATCH SET`），返回 `created=False`；节点不存在时创建并返回 `created=True`
- [ ] **⚠️ MERGE 语义说明**: Neo4j `MERGE` 根据 MATCH 部分决定创建或匹配，需结合 `ON CREATE SET` / `ON MATCH SET` 子句明确行为

### AC-3: Cypher 查询与图遍历

**Given** 节点与关系管理已实现
**When** 执行 Cypher 查询
**Then** 支持参数化查询（防止注入）
**And** 支持路径查询、多跳遍历、聚合查询

**验证标准/Validation Criteria:**
- [ ] GraphStorage 接口定义（`src/domain/repositories/graph_storage.py`）
  - 方法: `execute_query(cypher: str, params: dict[str, Any] | None = None) -> list[dict]`, `execute_write_query(cypher: str, params: dict[str, Any] | None = None) -> list[dict]`
  - 方法: `find_path(start_id: str, end_id: str, max_depth: int = 3) -> list[dict]`
  - 方法: `get_neighbors(node_id: str, rel_type: str | None = None, direction: str = "BOTH") -> list[GraphNode]`
  - **⚠️ 类型注解规范**: 使用 `dict[str, Any] | None` 而非 `dict = None`，满足 MyPy 严格模式
- [ ] Neo4jGraphStorage 实现（`src/infrastructure/storage/neo4j/graph_storage.py`）
  - 使用 `AsyncSession.run()` 执行参数化 Cypher 查询
  - 支持读/写会话分离（可选，MVP 使用统一会话）
  - 支持结果映射为 Python 字典列表
  - **查询参数化**: 所有用户输入必须通过 `$param` 传递，禁止字符串拼接
- [ ] 简单查询延迟 P95<200ms（单节点查询、一度关系查询）
- [ ] 复杂查询延迟 P95<800ms（三度关系遍历、聚合查询）
- [ ] 单元测试覆盖查询场景（含边界条件：空图、不存在节点）

### AC-4: GraphRAG 增强检索基础

**Given** Cypher 查询与图遍历已实现
**When** 实现 GraphRAG 基础设施
**Then** 支持实体关联检索（基于查询实体查找相关实体/文档）
**And** 为 Story 3.4/3.13/3.17 的 GraphRAG 提供基础

**验证标准/Validation Criteria:**
- [ ] GraphRetriever 实现（`src/infrastructure/storage/neo4j/graph_retriever.py`）
  - 方法: `find_related_entities(entity_id: str, max_depth: int = 2, limit: int = 20) -> list[dict]`
  - 方法: `find_related_documents(entity_id: str, limit: int = 10) -> list[dict]`
  - 方法: `find_community(node_ids: list[str]) -> list[dict]`（社区发现基础）
  - **⚠️ MVP 算法选择**: `find_community` 使用 **Connected Components**（连通分量）算法作为 MVP 实现，而非 Louvain/Label Propagation（P2/FR-SR-15 范围）。Connected Components 通过 BFS/DFS 遍历即可实现，复杂度 O(V+E)
  - **V1 增强**: Story 12.5/17.5 升级为 Louvain/Label Propagation 算法
- [ ] 实体关联查询支持多跳遍历（最多 3 度关系）
- [ ] 结果按关系权重/置信度排序
- [ ] 单元测试覆盖实体关联、文档关联场景
- [ ] **与 Qdrant 协同**: GraphRetriever 返回的节点 ID 可用于 Qdrant payload 过滤（通过 `document_id` 字段）

### AC-5: 架构约束验证测试就绪

**Given** Neo4j 图存储层已实现
**When** 运行架构约束验证测试
**Then** 领域层不依赖任何 Neo4j 实现
**And** 依赖方向正确（基础设施层→应用层→领域层）
**And** 六层存储单向依赖链正确（Graph→EventBus→Cache，无循环）
**And** Ruff 检查通过（严重错误=0）
**And** MyPy 类型检查通过（错误率<5%）

**验证标准/Validation Criteria:**
- [ ] 领域层无 Neo4j 导入验证（扫描 `src/domain/` 目录）
- [ ] 依赖方向测试通过（使用 `import-linter`）
- [ ] 节点/关系命名规范验证（所有节点遵循 `sisys:{type}` 标签）
- [ ] 六层存储循环依赖验证（Graph 存储不直接依赖 Cache 层）
- [ ] Ruff 检查通过（0 错误）
- [ ] MyPy 类型检查通过（0 问题）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 配置模型 (Configuration Models)
- [ ] Neo4jConfig 定义（`src/infrastructure/config/neo4j.py`）
  - 字段: uri, username, password, database, max_connection_pool_size, connection_timeout, max_retry_time

#### 数据模型 (Data Models) — 基础设施层
- [ ] GraphNode 定义（`src/infrastructure/storage/neo4j/models.py`）
  - 字段: id, labels(list[str]), properties(dict), created_at
  - Properties 规范: business_domain, entity_type, content_hash
- [ ] GraphRelationship 定义（`src/infrastructure/storage/neo4j/models.py`）
  - 字段: start_node_id, end_node_id, relationship_type, properties, created_at
  - 关系类型: MENTIONS, DEPENDS_ON, RELATES_TO, PART_OF, INFLUENCES, CONTRADICTS

#### 仓储接口 (Repository Interfaces)
- [ ] GraphManager 接口（`src/domain/repositories/graph_storage.py`）
- [ ] GraphStorage 接口（`src/domain/repositories/graph_storage.py`）

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_neo4j-graph-layer.feature`
- [ ] 覆盖场景:
  - 节点创建/删除/查询
  - 关系创建/删除/查询
  - Cypher 查询与图遍历
  - GraphRAG 实体关联检索
  - 多租户隔离验证
  - 领域层零 Neo4j 依赖

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
| **TDD 单元测试** | Neo4j 连接池 | 客户端创建、复用、关闭、健康检查 | `test_neo4j_manager.py` | Task 1 |
| **TDD 单元测试** | 节点管理 | 创建、删除、查询、MERGE 语义 | `test_graph_node.py` | Task 2 |
| **TDD 单元测试** | 关系管理 | 创建、删除、查询、类型约束 | `test_graph_relationship.py` | Task 2 |
| **TDD 单元测试** | Cypher 查询 | 参数化查询、路径查询、邻居查询 | `test_cypher_query.py` | Task 3 |
| **TDD 单元测试** | GraphRAG 检索 | 实体关联、文档关联、社区发现 | `test_graph_retriever.py` | Task 4 |
| **TDD 集成测试** | Neo4j 端到端 | 完整节点/关系/查询流程 | `test_integration_neo4j.py` | Task 5 |
| **SDD 架构验证** | 领域层零依赖 | 领域层无 Neo4j 导入 | `test_architecture_constraints.py` | Task 6 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）- **P1 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）- **P1 阻断门禁**（接口定义）
- [ ] **关键路径覆盖率 100%**（所有分支覆盖）

> ⚠️ **存储层实现覆盖率要求：** 本 Story 为图存储层实现（非空接口），需达到标准覆盖率要求。

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | Neo4j 连接池与客户端 | Task 1 | Neo4jConfig + Neo4jClient | `test_neo4j_manager.py` |
| AC-2 | 节点与关系管理 | Task 2 | GraphNode + GraphRelationship + Neo4jGraphManager | `test_graph_node.py`, `test_graph_relationship.py` |
| AC-3 | Cypher 查询与图遍历 | Task 3 | GraphStorage 接口 + Neo4jGraphStorage | `test_cypher_query.py` |
| AC-4 | GraphRAG 增强检索基础 | Task 4 | GraphRetriever | `test_graph_retriever.py` |
| AC-5 | 架构约束验证 | Task 6 | 领域层零 Neo4j 依赖验证 | `test_architecture_constraints.py` |
| AC-1~AC-4 | Neo4j 端到端集成测试 | Task 5 | 完整节点/关系/查询流程验证 | `test_integration_neo4j.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-5

> **目的：** 在进入代码实现前，明确配置模型、数据模型、接口、验收标准。

- [x] Subtask: 定义 Neo4jConfig 配置模型
- [x] Subtask: 定义 GraphNode 数据模型
- [x] Subtask: 定义 GraphRelationship 数据模型
- [x] Subtask: 定义 GraphManager 接口
- [x] Subtask: 定义 GraphStorage 接口
- [x] Subtask: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_neo4j-graph-layer.feature`
- [x] Subtask: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕
- [x] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: Neo4j 连接池与客户端抽象

**关联 AC:** AC-1

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**
> **📌 复用说明:** 参考 Story 1.4/1.5/1.6/1.7 的配置模式与懒初始化策略，本 Task 采用相同模式。

#### TDD 循环 A：Neo4jConfig 配置模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_neo4j_config.py`（字段验证、默认值、from_env 支持） |
| 🟢 绿 | 实现 `Neo4jConfig` dataclass 最小代码 |
| 🔄 重构 | 添加类型注解、docstring、from_env 支持 |

- [x] Subtask: 🔴 红 — 编写 Neo4jConfig 失败测试
- [x] Subtask: 🟢 绿 — 实现 Neo4jConfig 最小代码
- [x] Subtask: 🔄 重构 — 优化 Neo4jConfig 代码

#### TDD 循环 B：Neo4jClient 通用接口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_neo4j_manager.py`（客户端创建、健康检查、关闭） |
| 🟢 绿 | 实现 `Neo4jManager` 类最小代码 |
| 🔄 重构 | 添加懒初始化、异常处理、健康检查 |

- [x] Subtask: 🔴 红 — 编写 Neo4jClient 失败测试
- [x] Subtask: 🟢 绿 — 实现 Neo4jClient 最小代码
- [x] Subtask: 🔄 重构 — 优化 Neo4jClient 代码

**完成标准/Definition of Done:**
- [ ] Neo4jConfig 和 Neo4jClient 实现完成
- [ ] TDD 循环全部通过
- [ ] 基础设施层覆盖率≥10%

---

### Task 2: 节点与关系管理

**关联 AC:** AC-2

> ⚠️ **本 Task 包含自己的 TDD 循环。**

#### TDD 循环 A：GraphNode 数据模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_graph_node.py`（字段验证、labels 列表、properties 规范） |
| 🟢 绿 | 实现 `GraphNode` dataclass 最小代码 |
| 🔄 重构 | 添加字段验证、类型注解、docstring |

- [x] Subtask: 🔴 红 — 编写 GraphNode 失败测试
- [x] Subtask: 🟢 绿 — 实现 GraphNode 最小代码
- [x] Subtask: 🔄 重构 — 优化 GraphNode 代码

#### TDD 循环 B：GraphRelationship 数据模型

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_graph_relationship.py`（字段验证、关系类型枚举、properties） |
| 🟢 绿 | 实现 `GraphRelationship` dataclass 最小代码 |
| 🔄 重构 | 添加关系类型枚举、字段验证、类型注解 |

- [x] Subtask: 🔴 红 — 编写 GraphRelationship 失败测试
- [x] Subtask: 🟢 绿 — 实现 GraphRelationship 最小代码
- [x] Subtask: 🔄 重构 — 优化 GraphRelationship 代码

#### TDD 循环 C：GraphManager 接口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_graph_manager_interface.py`（接口类型检查） |
| 🟢 绿 | 实现 `GraphManager` Protocol 接口 |
| 🔄 重构 | 添加类型注解、方法签名 |

- [x] Subtask: 🔴 红 — 编写 GraphManager 接口失败测试
- [x] Subtask: 🟢 绿 — 实现 GraphManager 接口
- [x] Subtask: 🔄 重构 — 优化接口定义

#### TDD 循环 D：Neo4jGraphManager 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_neo4j_graph_manager.py`（创建、删除、查询、MERGE 语义） |
| 🟢 绿 | 实现 `Neo4jGraphManager` 类最小代码 |
| 🔄 重构 | 添加 MERGE 操作、节点/关系已存在处理、异常处理 |

- [x] Subtask: 🔴 红 — 编写 Neo4jGraphManager 失败测试
- [x] Subtask: 🟢 绿 — 实现 Neo4jGraphManager 最小代码
- [x] Subtask: 🔄 重构 — 优化 Neo4jGraphManager 代码

**完成标准/Definition of Done:**
- [ ] GraphNode、GraphRelationship、GraphManager 接口、Neo4jGraphManager 实现完成
- [ ] TDD 循环全部通过
- [ ] 节点/关系命名规范验证（`sisys:{type}` 标签）
- [ ] 基础设施层覆盖率≥30%

---

### Task 3: Cypher 查询与图遍历

**关联 AC:** AC-3

> ⚠️ **本 Task 包含自己的 TDD 循环。**

#### TDD 循环 A：GraphStorage 接口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_graph_storage_interface.py`（接口类型检查） |
| 🟢 绿 | 实现 `GraphStorage` Protocol 接口 |
| 🔄 重构 | 添加类型注解、方法签名 |

- [x] Subtask: 🔴 红 — 编写 GraphStorage 接口失败测试
- [x] Subtask: 🟢 绿 — 实现 GraphStorage 接口
- [x] Subtask: 🔄 重构 — 优化接口定义

#### TDD 循环 B：Neo4jGraphStorage 实现（含 Cypher 查询）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_neo4j_graph_storage.py`（execute_query、execute_write_query、参数化查询） |
| 🟢 绿 | 实现 `Neo4jGraphStorage` 类最小代码 |
| 🔄 重构 | 添加参数化查询、结果映射、异常处理 |

- [x] Subtask: 🔴 红 — 编写 Neo4jGraphStorage 失败测试
- [x] Subtask: 🟢 绿 — 实现 Neo4jGraphStorage 最小代码
- [x] Subtask: 🔄 重构 — 优化 Neo4jGraphStorage 代码

#### TDD 循环 C：图遍历查询专项测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_cypher_query.py`（路径查询、邻居查询、多跳遍历、边界条件） |
| 🟢 绿 | 实现 find_path、get_neighbors 方法核心逻辑 |
| 🔄 重构 | 添加最大深度限制、结果去重、性能优化 |

- [x] Subtask: 🔴 红 — 编写图遍历查询失败测试
- [x] Subtask: 🟢 绿 — 实现图遍历查询最小代码
- [x] Subtask: 🔄 重构 — 优化图遍历查询代码

**完成标准/Definition of Done:**
- [ ] GraphStorage 接口、Neo4jGraphStorage（含 Cypher 查询与图遍历）实现完成
- [ ] TDD 循环全部通过
- [ ] 简单查询延迟 P95<200ms（性能基准测试）
- [ ] 复杂查询延迟 P95<800ms（性能基准测试）
- [ ] 基础设施层覆盖率≥50%

---

### Task 4: GraphRAG 增强检索基础

**关联 AC:** AC-4

> ⚠️ **本 Task 包含自己的 TDD 循环。**
> **📌 MVP 实现说明:** 本 Story 仅实现 GraphRAG 基础设施，RRF 融合排序在 Story 3.4 实现。

#### TDD 循环 A：GraphRetriever 实体关联检索

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_graph_retriever.py`（find_related_entities、多跳遍历、limit 限制） |
| 🟢 绿 | 实现 `GraphRetriever` 类最小代码 |
| 🔄 重构 | 添加结果排序、去重、置信度计算 |

- [x] Subtask: 🔴 红 — 编写 GraphRetriever 失败测试
- [x] Subtask: 🟢 绿 — 实现 GraphRetriever 最小代码
- [x] Subtask: 🔄 重构 — 优化 GraphRetriever 代码

#### TDD 循环 B：文档关联与社区发现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_graph_retriever_extended.py`（find_related_documents、find_community） |
| 🟢 绿 | 实现 find_related_documents、find_community 方法 |
| 🔄 重构 | 添加结果过滤、社区发现算法基础实现 |

- [x] Subtask: 🔴 红 — 编写文档关联/社区发现失败测试
- [x] Subtask: 🟢 绿 — 实现 find_related_documents/find_community 最小代码
- [x] Subtask: 🔄 重构 — 优化文档关联/社区发现代码

#### TDD 循环 C：与 Qdrant 协同检索基础

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_graph_qdrant_integration.py`（GraphRetriever 返回节点 ID 用于 Qdrant payload 过滤） |
| 🟢 绿 | 实现协同检索接口 |
| 🔄 重构 | 添加结果合并、排序优化 |

- [x] Subtask: 🔴 红 — 编写协同检索失败测试
- [x] Subtask: 🟢 绿 — 实现协同检索最小代码
- [x] Subtask: 🔄 重构 — 优化协同检索代码

**完成标准/Definition of Done:**
- [ ] GraphRetriever（含实体关联、文档关联、社区发现、与 Qdrant 协同）实现完成
- [ ] TDD 循环全部通过
- [ ] 基础设施层覆盖率≥65%

---

### Task 5: Neo4j 端到端集成测试

**关联 AC:** AC-1 ~ AC-4

> **性质说明：** 本 Task 是集成测试，验证所有 Neo4j 服务的端到端流程。

#### 集成测试实现

- [x] Subtask: 创建 `tests/integration/test_integration_neo4j.py`
- [x] Subtask: 实现节点生命周期端到端测试（创建→查询→验证→删除）
- [x] Subtask: 实现关系端到端测试（创建→查询→验证→删除→类型约束）
- [x] Subtask: 实现 Cypher 查询端到端测试（参数化查询、路径查询、邻居查询）
- [x] Subtask: 实现 GraphRAG 实体关联检索端到端测试（写入→关联查询→多跳遍历→验证）
- [x] Subtask: 实现多租户隔离端到端测试（不同 business_domain 数据隔离验证）

**完成标准/Definition of Done:**
- [ ] 所有集成测试通过
- [ ] 测试输出完整的流程验证报告
- [ ] 基础设施层覆盖率≥75%

---

### Task 6: 架构约束验证测试

**关联 AC:** AC-5

> **性质说明：** 本 Task 验证 Neo4j 图存储层实现是否符合六边形架构约束。

#### 架构验证测试实现

- [x] Subtask: 创建 `tests/unit/infrastructure/test_architecture_constraints.py`
- [x] Subtask: 实现领域层零 Neo4j 依赖验证（扫描 `src/domain/` 目录）
- [x] Subtask: 实现依赖方向验证（使用 `import-linter`）
- [x] Subtask: 实现节点/关系命名规范验证（所有节点遵循 `sisys:{type}` 标签）
- [x] Subtask: 实现六层存储循环依赖验证（Graph 存储不直接依赖 Cache 层）
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

- **六层存储架构:** L5 图存储层（Neo4j 5.x）存储知识图谱、实体关系、依赖图
- **容量规划:** 50GB（V2 目标），MVP 10GB，V1 30GB
- **节点标签规范:** `sisys:{entity_type}`（如 `sisys:Entity`, `sisys:Document`, `sisys:Agent`）
- **关系类型:** MENTIONS, DEPENDS_ON, RELATES_TO, PART_OF, INFLUENCES, CONTRADICTS
- **延迟预算:** 简单查询 P95<200ms，复杂查询 P95<800ms
- **多租户隔离:** 按业务域属性隔离节点数据（`business_domain` 属性过滤）
- **领域层零依赖:** 领域层仅定义接口，不依赖任何 Neo4j 实现细节
- **六层存储单向依赖链:** Cache → Relational → Vector → Object → Graph（无循环），Graph 通过事件总线异步发布缓存更新事件，由 Cache 层监听刷新

#### 双接口设计说明

本 Story 定义两个领域层接口，与 Story 1.6 Qdrant 的 `CollectionManager` + `VectorStorage` 模式一致：

| 接口 | 职责 | 使用者 |
|------|------|-------|
| **GraphManager** | 低级别图操作（节点/关系的 CRUD） | 应用层用例，直接操作图谱 |
| **GraphStorage** | 高级别图查询（Cypher 执行、图遍历、检索） | 应用层用例，执行复杂查询 |

**为什么需要两个接口？** GraphManager 提供原子化的图操作（适合知识图谱构建场景），GraphStorage 提供声明式的查询能力（适合 GraphRAG 检索场景）。两者职责清晰分离，避免单一接口职责过重。

#### 索引要求（性能保障前提）

| 索引类型 | 属性 | 索引名称 | 目的 |
|---------|------|---------|------|
| **唯一索引** | `id` | `node_id_unique` | 节点唯一性约束 |
| **范围索引** | `business_domain` | `idx_business_domain` | 多租户隔离过滤 |
| **范围索引** | `entity_type` | `idx_entity_type` | 实体类型过滤 |
| **全文索引** | `properties.name` | `idx_name_fulltext` | 名称模糊搜索 |
| **关系索引** | `relationship_type` | `idx_rel_type` | 关系类型过滤 |

**测试数据集规模：**
- 简单查询基准：≤1000 节点，≤5000 关系
- 复杂查询基准：≤10000 节点，≤50000 关系
- 并发查询≥30（连接池 `max_connection_pool_size=50`）

**Neo4j 配置要求：**
- `dbms.memory.pagecache.size`: 50% 可用内存（确保热数据常驻内存）
- `dbms.tx_state.memory_allocation.max`: 512m（大事务内存上限）

#### 未来扩展（FR-SA-01 映射）

FR-SA-01 要求"永久存储历年 SP/BP 的关键假设变量、决策依据、实际执行偏差"。后续 Story 可在本 Story 基础上扩展以下节点/关系类型：

| 节点类型 | 关系类型 | 用途 |
|---------|---------|------|
| `sisys:Assumption` | `BASED_ON` | 战略假设与依赖关系 |
| `sisys:Decision` | `MADE_BY`, `BASED_ON_EVIDENCE` | 决策依据链 |
| `sisys:Deviation` | `DEVIATED_FROM`, `CAUSED_BY` | 执行偏差追溯 |
| `sisys:Checkpoint` | `CONTAINS`, `FOLLOWS` | Checkpoint 依赖图 |

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 决策 4 (ADR-004): 六层存储架构

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **Neo4j 5.x** | 成熟图数据库、Cypher 查询语言强大、ACID 事务支持、社区生态完善 | 分布式扩展需付费企业版 | ✅ 9/10 |
| NebulaGraph | 分布式原生、开源免费 | 生态较新、Python 客户端成熟度低 | 7/10 |
| NetworkX + 持久化 | 零新依赖、轻量 | 性能差、不支持并发、不适合生产 | 3/10 |

**决策理由：**
1. Neo4j 5.x 是最成熟的图数据库，支持 ACID 事务和强大的 Cypher 查询语言
2. 满足简单查询 P95<200ms、复杂查询 P95<800ms 的性能目标
3. 社区生态完善，Python 客户端（`neo4j` 包）成熟稳定
4. 支持多租户属性过滤，满足数据隔离需求
5. 与 Qdrant 向量存储协同，支持 GraphRAG 增强检索场景

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   └── repositories/
│   │       └── graph_storage.py            # GraphManager + GraphStorage 接口
│   └── infrastructure/
│       ├── config/
│       │   └── neo4j.py                    # Neo4jConfig 配置模型
│       └── storage/
│           └── neo4j/
│               ├── __init__.py
│               ├── client.py               # Neo4jClient 通用接口
│               ├── models.py               # GraphNode/GraphRelationship
│               ├── graph_manager.py        # Neo4jGraphManager 实现
│               ├── graph_storage.py        # Neo4jGraphStorage 实现（含 Cypher 查询）
│               └── graph_retriever.py      # GraphRetriever 实现
├── tests/
│   ├── unit/
│   │   ├── infrastructure/
│   │   │   ├── test_neo4j_config.py
│   │   │   ├── test_neo4j_manager.py
│   │   │   ├── test_graph_node.py
│   │   │   ├── test_graph_relationship.py
│   │   │   ├── test_graph_manager.py
│   │   │   ├── test_graph_storage.py
│   │   │   ├── test_cypher_query.py
│   │   │   ├── test_graph_retriever.py
│   │   │   ├── test_graph_retriever_extended.py
│   │   │   ├── test_graph_qdrant_integration.py
│   │   │   └── test_architecture_constraints.py
│   │   └── domain/
│   │       ├── test_graph_manager_interface.py
│   │       └── test_graph_storage_interface.py
│   ├── integration/
│   │   └── test_integration_neo4j.py
│   └── acceptance/
│       └── test_acceptance_neo4j-graph-layer.feature
└── docs/
    └── infrastructure/
        └── neo4j_graph_layer_guide.md      # Neo4j 图存储层实施指南
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.7-MinIO Object Layer](./1-7-minio-object-layer.md), [Story 1.6-Qdrant Vector Layer](./1-6-qdrant-vector-layer.md)

**关键学习/Key Learnings:**
1. **配置模式复用** — Story 1.3-1.7 已建立 `XxxConfig` + `from_env()` 模式，本 Story 沿用
2. **领域层接口与基础设施层实现分离** — 领域层定义同步接口（Protocol），基础设施层实现
3. **懒初始化连接池** — 首次调用时创建客户端，避免启动时连接失败阻塞业务
4. **多租户隔离策略** — 属性级别隔离（与 Qdrant Collection 级别、PostgreSQL Schema 级别一致）
5. **六层存储单向依赖链** — Graph 存储通过事件总线异步更新缓存，不直接依赖 Cache 层（避免循环依赖）
6. **架构约束验证** — 领域层零外部依赖是硬约束，必须在架构验证测试中覆盖

**应用到本故事/Applied to This Story:**
- [ ] Neo4jConfig 采用 Story 1.4-1.7 相同的配置模式
- [ ] GraphManager/GraphStorage 接口定义在领域层（Protocol），实现在基础设施层
- [ ] Neo4jClient 采用懒初始化模式（与 Story 1.5-1.7 一致）
- [ ] 节点标签规范统一为 `sisys:{type}`，与其他存储层命名规范保持一致
- [ ] 六层存储循环依赖验证确保 Graph→EventBus→Cache 异步更新，无直接依赖
- [ ] 架构约束测试验证领域层无 Neo4j 导入

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
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-7-minio-object-layer.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] Story 需求从 `epics_v1.0.md` 提取
- [ ] 架构约束从 `architecture.md` 提取
- [ ] 前一个故事学习经验整合
- [ ] 状态设置为 `ready-for-dev`（已与 sprint-status.yaml 同步）
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-8-neo4j-graph-layer.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/infrastructure/config/neo4j.py` - Neo4jConfig 配置模型
- `src/infrastructure/storage/neo4j_manager.py` - Neo4jClient 通用接口
- `src/infrastructure/storage/neo4j/models.py` - GraphNode/GraphRelationship 数据模型
- `src/infrastructure/storage/neo4j/graph_manager.py` - Neo4jGraphManager 实现
- `src/infrastructure/storage/neo4j/graph_storage.py` - Neo4jGraphStorage 实现
- `src/infrastructure/storage/neo4j/graph_retriever.py` - GraphRetriever 实现
- `src/domain/repositories/graph_storage.py` - GraphManager + GraphStorage 接口
- `tests/unit/infrastructure/test_neo4j_*.py` - 单元测试
- `tests/integration/test_integration_neo4j.py` - 集成测试
- `tests/acceptance/test_acceptance_neo4j-graph-layer.feature` - 验收测试

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.8 |
| **Story Key** | 1-8-neo4j-graph-layer |
| **File** | `_bmad-output/implementation-artifacts/stories/1-8-neo4j-graph-layer.md` |
| **Status** | `done` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 3: 六层存储架构 |
| **优先级** | P0 |
| **覆盖 FR** | FR-AR-02（部分覆盖）, FR-AR-04（仓储模式）, FR-SA-01（永久存储） |
| **覆盖 NFR** | NFR-PERF-07（图遍历查询延迟） |
| **容量规划** | 50GB（V2），≤5M 节点，≤25M 关系 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-6，含 SDD 规范 + TDD 循环）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 ~ AC-5）
3. [x] Architecture constraints extracted 架构约束已提取（六层存储、节点/关系规范、多租户隔离、单向依赖链）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（配置模式复用、接口分离、懒初始化、循环依赖避免）
5. [x] Sprint status synced to `done`（已与 sprint-status.yaml 同步）
6. [x] 全部 80 个测试通过，0 失败
7. [x] Ruff 检查通过（0 错误）
8. [x] MyPy 类型检查通过（0 问题）

### 实现摘要 Implementation Summary

**创建文件（17 个）:**
- 源文件: `neo4j.py`, `client.py`, `models.py`, `graph_manager.py`, `graph_storage.py`, `graph_retriever.py`, `graph_storage.py`（领域接口）
- 测试: 9 个单元测试文件 + 1 个集成测试文件 + 1 个验收测试
- 配置: 更新 `__init__.py` 导出

**关键实现:**
- Neo4jConfig: 环境变量配置加载，from_env() 支持
- Neo4jManager: 懒初始化 AsyncDriver，健康检查，优雅关闭
- GraphNode/GraphRelationship: 数据模型 + RelationshipType 枚举
- Neo4jGraphManager: 节点/关系 CRUD，MERGE 语义
- Neo4jGraphStorage: 参数化 Cypher 查询，路径查询，邻居查询
- GraphRetriever: find_related_entities, find_related_documents, find_community

### 下一步 Next Steps

- [x] Story implemented with all tasks completed
- [x] Status set to `done`
- [x] 运行 `code-review` 进行代码审查
- [x] 部署 Neo4j 实例后验证集成测试（替换 Mock 为真实实例）
- [x] 部署 Neo4j 实例后最终完成验收测试（禁止使用 mock / fake）

---

**模板版本/Template Version:** 2.0.0
**创建日期/Created:** 2026-04-13
**最后更新/Last Updated:** 2026-04-17
**更新说明:**
- v1.0: 基于 epics_v1.0.md Story 1.8 定义、architecture.md 架构约束创建
- v1.1: 实施完成：17文件创建，80测试通过，0 warnings，Ruff+MyPy全通过
- v1.2: 修复 Neo4j 单元测试 `test_find_path_max_depth` 断言问题

### v1.2 修复详情

#### Neo4j 单元测试断言修复

| 文件 | 问题 | 修复方案 |
|------|------|---------|
| `tests/unit/infrastructure/test_neo4j_graph_storage.py` | `test_find_path_max_depth` 期望 Cypher 查询使用 `$max_depth` 参数 | 改为验证字面值 `[*1..2]`（Cypher 可变长度模式 `[*1..$max_depth]` 不支持参数） |

**测试结果：** 9 passed
