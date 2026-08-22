# Story 3.5: 分层检索（L1-L4）

**Status:** `done`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 系统执行分层检索（L1 跨文档摘要→L2 文档摘要→L3 文档切片→L4 实体级片段）,
**So that** 支持自顶向下和自底向上的双向遍历检索，不同查询粒度匹配不同层级。

### 业务价值

本 Story 是 Epic 3（智能检索与知识发现）关键路径的第五个故事（P0-5），也是 FR-SR-05（分层检索）的完整实现。

在 Story 3.1a/3.1b/3.4 已交付 Dense + Sparse + Graph 三路混合检索的基础上，本 Story 引入**检索粒度分层**（L1-L4），支持按查询粒度在不同层级间双向遍历。

| 层级 | 名称 | 粒度 | 数据来源 | 覆盖范围 |
|------|------|------|---------|---------|
| **L4** | 实体级片段 | 子块（~150 tokens） | 现有 `SemanticChunk` Child 块（需重构为分块级索引） | 单文档内的细粒度语义片段 |
| **L3** | 文档切片 | 父块（~600 tokens） | 现有 `SemanticChunk` Parent 块（需重构为分块级索引） | 单文档内的语义完整段落 |
| **L2** | 文档摘要 | 单文档摘要（~1K tokens） | 新建：LLM 摘要 / 聚合 | 单文档级语义摘要 |
| **L1** | 跨文档摘要 | 多文档摘要（~2K tokens） | 新建：L2 摘要聚合 | 多文档级主题/项目摘要 |

**命名说明：** 此处 L1-L4 为**检索粒度级别**（Retrieval Granularity），区别于存储层级别 L0-L5（L0 文件系统→L1 Redis→L2 PostgreSQL→L3 Qdrant→L4 MinIO→L5 Neo4j）。

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 3: 智能检索与知识发现，Story 3.5

**前置依赖:**
- Story 3.4（RRF 融合排序 ✅ 已实现）— 提供三路检索编排模式、`HybridSearchService`、`GraphSearchService`
- Story 2.8（语义分块 ✅ 已实现）— 提供 `SemanticChunk` 值对象（含 `IndexLevel`、`parent_chunk_id`）和 `_split_child_parent()` 方法
- Story 1.6（Qdrant 向量层 ✅ 已实现）— 提供 `L3VectorPort` 用于向量索引与检索
- Story 3.1a（Dense 语义检索 ✅ 已实现）— 提供 `DenseSemanticSearchService`
- Story 3.1b（BM25 稀疏检索 ✅ 已实现）— 提供 `Bm25SparseSearchService`
- Story 3.2b（实体抽取 ✅ 已实现）— 提供 `L5GraphPort.search_entities()` 用于 L4 实体增强

> **注意：** 当前 Qdrant 索引流程 (`document_tasks.py`) 是**文档级粒度**——将整个文档文本拼接后生成一个向量并写入一个 Qdrant 点，payload 仅存储 `chunk_index` 和 `created_at`。分块流程 (`SemanticChunkingService`) 将 Child/Parent 块存入 PostgreSQL，但**不写入 Qdrant**。两条管道完全独立，L4/L3 分层检索所需的**分块级向量索引**尚不存在。实施本 Story 前需重构索引流程为分块级粒度，并确保 payload 包含 `parent_chunk_id` 和 `index_level`。

**后续依赖:** Story 3.6（契约化摘要）、Story 3.7（检索相关性评估）、Story 3.8（高保真溯源）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 分层检索端口契约定义

**Given** 系统需要统一的分层检索抽象
**When** 定义 `LayeredRetrievalPort` 协议
**Then** 包含 `search_top_down()` 和 `search_bottom_up()` 核心方法，签名与现有搜索服务对齐
**And** 所有领域层定义零外部依赖（仅 Python 标准库 + Protocol + `SearchResult`）

**验证标准/Validation Criteria:**
- [ ] `LayeredRetrievalPort` Protocol 定义于 `src/domain/ports/layered_retrieval.py`
- [ ] 包含 `search_top_down(query_text, target_level, limit, ...)` 方法 — 自顶向下遍历
- [ ] 包含 `search_bottom_up(query_text, target_level, limit, ...)` 方法 — 自底向上遍历
- [ ] 返回 `list[SearchResult]`，与现有搜索服务签名一致
- [ ] `target_level` 参数类型为 `str`（"L1"/"L2"/"L3"/"L4"），默认 "L4"
- [ ] 其余参数（`collection`, `limit`, `tenant_id`, `filter_payload`）与 `DenseSemanticSearchService.search()` 签名对齐
- [ ] 端口注册于 `composition_root.py`，通过 `register_port()` 注册为 `layered_retrieval_service` 端口（含 module 参数）

### AC-2: L4 → L3 自底向上遍历（Parent-Child 回溯）

**Given** 用户查询文本在 L4 实体级片段（Child 块）中命中
**When** 执行自底向上检索，目标层级为 L3
**Then** 系统首先在 L4 层执行 Dense 语义检索（使用现有 `DenseSemanticSearchService`）
**And** 对命中结果的 `payload.parent_chunk_id` 去重，回溯到 L3 父块（Parent 块）
**And** 通过 DenseSemanticSearchService（需扩展 `search_with_vector()` 方法以支持传入查询向量）对父块集合执行带 filter_payload 的向量检索；或者使用 L3VectorPort.get_point(collection, point_id) 按 ID 直接获取父块内容（推荐方案，点 ID 必须等于 `str(chunk.chunk_id)`）
**And** 返回 L3 层的去重合并结果列表
**And** 无 Child 匹配时返回空列表

**验证标准/Validation Criteria:**
> **【V1 目标】L4→L3 自底向上回溯（MVP 仅支持相邻层级单级回溯，多级全遍历 L4→L1 依赖 L2/L1 摘要索引就绪后迭代）**
- [ ] `search_bottom_up(query_text, target_level="L3")` 执行 L4→L3 回溯
- [ ] 回溯去重：同一 Parent 的多个 Child 命中合并为一条结果
- [ ] 父块内容获取：`L3VectorPort.get_point()`（按 ID 回溯，推荐）或 DenseSemanticSearchService 带 payload 过滤（需扩展 `search_with_vector()`）
- [ ] 结果 `payload` 携带 `parent_chunk_id`、`child_count`（命中子块数）、`index_level="parent"`
- [ ] 合并后结果按最高 Child 分数降序排列
- [ ] 延迟 P95 < 200ms（L4 检索 + L3 回溯）(V1 目标，MVP 阶段可放宽至 350ms，总预算 ≤800ms)
- [ ] 并发检索 ≥ 50
- [ ] 融合延迟 P95 < 50ms（L4→L3 回溯结果合并排序）

### AC-3: L3 → L4 自顶向下展开（Parent 展开到 Child）

**Given** 用户查询文本在 L3 文档切片（Parent 块）中命中
**When** 执行自顶向下检索，目标层级为 L4
**Then** 系统首先在 L3 层执行 Dense 语义检索
**And** 复用 L3 检索时使用的查询向量（需扩展 DenseSemanticSearchService 新增 `search_with_vector()` 方法，或由 LayeredRetrievalService 直接调用 L3VectorPort.search() 传入向量），对 Child 集合执行带 parent_chunk_id payload 过滤的向量检索
**And** 将命中 Parent 的 Top-K Child 子块作为结果返回
**And** 结果 `payload` 携带 `parent_chunk_id`、`parent_content` 摘要、`index_level="child"`

**验证标准/Validation Criteria:**
> **【V1 目标】L3→L4 自顶向下展开（MVP 仅支持相邻层级单级展开，多级全遍历 L1→L4 依赖 L2/L1 摘要索引就绪后迭代）**
- [ ] `search_top_down(query_text, target_level="L4")` 执行 L3→L4 展开
- [ ] 每个命中 Parent 展开 Top-3 Child 子块（可配置）
- [ ] Child 展开通过 `L3VectorPort.search()` 直接传入向量 + parent_chunk_id payload 过滤（需扩展 Port 或由 LayeredRetrievalService 直接调用；注意 N+1 问题：每个命中 Parent 单独调用 search() 时，展开 Parent 数建议上限 5 个，或扩展 L3VectorPort 支持 Qdrant group_by 参数实现单次分组查询）
- [ ] 结果 `payload` 包含 `parent_content` 截断摘要（前 200 字符）
- [ ] 结果按 Parent 分数 × Child 分数降序排列
- [ ] 延迟 P95 < 250ms（L3 检索 + L4 展开）(V1 目标，MVP 阶段可放宽至 400ms)
- [ ] 并发检索 ≥ 50
- [ ] 融合延迟 P95 < 50ms（L3→L4 展开结果合并排序）

### AC-4: 分层检索编排服务

**Given** 分层检索端口契约已定义
**When** 实现 `LayeredRetrievalService`
**Then** 注入 `DenseSemanticSearchService`、`EmbeddingServicePort`、`L3VectorPort` 等依赖
**And** 实现自底向上和自顶向下两种遍历策略
**And** 支持降级策略（L4 检索失败→降级为普通 L3 检索）
**And** 支持 `LayeredRetrievalCompleted` 事件发布（可选，REALTIME 模式）

**验证标准/Validation Criteria:**
- [ ] `LayeredRetrievalService` 位于 `src/application/services/layered_retrieval_service.py`
- [ ] 注入 `dense_search: DenseSemanticSearchService`（或 `Any` 保持松耦合）
- [ ] 注入 `embedding_service: EmbeddingServicePort`（自顶向下展开时复用查询向量）
- [ ] 注入 `l3_vector: L3VectorPort`（用于按 payload 过滤回溯）
- [ ] 实现 `search_top_down()` 和 `search_bottom_up()` 方法
- [ ] 降级策略：L4 检索失败→透明降级为 L3 检索，WARNING 日志
- [ ] 输入验证：空查询/空 collection 抛出 `ValidationError`
- [ ] 双向遍历均返回 `list[SearchResult]`

### AC-5: 分层检索异常体系

**Given** 分层检索过程中可能发生多种错误
**When** 定义分层检索异常类
**Then** 新增 `retrieval` 子域（280-281），分配唯一异常编码
**And** 继承适当的基类层次结构

**验证标准/Validation Criteria:**
- [ ] `LayeredRetrievalError`（EXCEPTION_280）— 继承 `BusinessException`，检索编排失败
- [ ] `LevelTransitionError`（EXCEPTION_281）— 继承 `BusinessException`，层级遍历非法
- [ ] 异常编码在 `_code_ranges.py` 注册 `retrieval` 子域（280, 281）及 `_CLASS_TO_SUBDOMAIN` 映射
- [ ] 异常在 `__init__.py` 导出，在 `EXCEPTION_HTTP_MAP` 注册（500/500）
- [ ] `allowed_child_parent_subdomains` 添加 `("retrieval", "business")`（定义在 tests/unit/domain/exceptions/test_code_ranges.py 中）
- [ ] 无编码碰撞（`grep -rw "EXCEPTION_28[0-9]"` 零输出）
- [ ] HTTP 映射测试覆盖：`test_exception_handlers.py` 中精确类型集合断言含 `LayeredRetrievalError` 和 `LevelTransitionError`

### AC-6: L2 文档摘要检索（骨架）

**Given** 文档摘要索引已构建（占位，当前返回空列表）
**When** 执行自顶向下检索，目标层级为 L2
**Then** 调用 `search_top_down(query_text, target_level="L2")`
**And** 当前返回空列表（骨架实现，标记 TODO；完整实现依赖 Story 3.6 交付的文档摘要索引）
**And** 方法签名完整，可被上层调用

**验证标准/Validation Criteria:**
- [ ] `search_top_down(query_text, target_level="L2")` 返回空列表
- [ ] 方法签名与 AC-1 端口契约一致
- [ ] 日志记录 `WARNING: L2 文档摘要检索尚未实现，返回空列表`
- [ ] 不抛出异常（空结果正常行为）

### AC-7: L1 跨文档摘要检索（骨架）

**Given** 跨文档摘要索引已构建（占位，当前返回空列表）
**When** 执行自顶向下检索，目标层级为 L1
**Then** 调用 `search_top_down(query_text, target_level="L1")`
**And** 当前返回空列表（骨架实现，标记 TODO；完整实现依赖 Story 3.6 交付的文档摘要索引）
**And** 方法签名完整，可被上层调用

**验证标准/Validation Criteria:**
- [ ] `search_top_down(query_text, target_level="L1")` 返回空列表
- [ ] 方法签名与 AC-1 端口契约一致
- [ ] 日志记录 `WARNING: L1 跨文档摘要检索尚未实现，返回空列表`
- [ ] 不抛出异常（空结果正常行为）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 事件定义位于 `src/domain/events/`
- [ ] 使用标准库实现领域事件校验（如 dataclass / Enum / 自定义验证），禁止在领域层依赖 Pydantic
- [ ] 事件命名使用业务含义直名（如 `LayeredRetrievalCompleted`）

#### 数据模型 (Data Models)
- [ ] 无新增数据模型（复用现有 `SemanticChunk`、`IndexLevel` 值对象）
- [ ] 如需新增 `DocumentSummary` 值对象，定义于 `src/domain/value_objects/`

#### 统一端口定义注册与管理 (Port Contract)
- [ ] 端口契约定义位于 `src/domain/ports/layered_retrieval.py`（新增）
- [ ] 端口注册中心位于 `src/domain/ports/registry.py`，所有端口必须登记为 `PortSpec`
- [ ] 端口实现仅可在 `src/composition_root.py` 统一注册，禁止业务代码直接实例化具体实现
- [ ] 端口解析器位于 `src/domain/ports/resolver.py`，业务代码只通过抽象解析实现
- [ ] 端口契约门禁位于 `src/domain/ports/contract_gate.py`，端口变更必须通过兼容性检查
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_layered_retrieval.py`）
- [ ] 接口命名符合单一职责，禁止同义接口重复定义
- [ ] 端口注册时提供 module 参数（register_port() 的第 5 个必需参数）
- [ ] 端口具备唯一名称、版本、owner、兼容策略、module（注册必需参数）
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

- [ ] **归属模块与基类** — 新增 `retrieval` 子域（280-281）：
    - `LayeredRetrievalError`（EXCEPTION_280）→ 继承 `BusinessException`，检索编排失败
    - `LevelTransitionError`（EXCEPTION_281）→ 继承 `BusinessException`，层级遍历非法
- [ ] **唯一编码分配** — 从 `retrieval` 子域（280-281）选取，`grep -rw "EXCEPTION_28[0-9]" src/` 验证无碰撞
- [ ] **构造器参数设计** — 携带层级上下文（`current_level`、`target_level`、`query_text` 等），通过 `context` 字典暴露
- [ ] **消息安全性审查** — 错误消息面向调用方可理解，不泄露 SQL/堆栈等内部实现细节
- [ ] **编码注册** — 更新 `_code_ranges.py`：
    - `CODE_RANGES` 新增 `"retrieval": (280, 281)`
    - `_CLASS_TO_SUBDOMAIN` 新增 `"LayeredRetrievalError": "retrieval"`、`"LevelTransitionError": "retrieval"`
- [ ] **导出完整性** — 模块 `__all__` + 包 `__init__.py` 导入 + `EXCEPTION_HTTP_MAP` 映射
- [ ] **测试覆盖** — 构造/`to_dict()`/HTTP 映射/编码唯一性 + 子域范围测试全部通过
- [ ] **BDD 验收场景（额外）** — 异常路径的 Gherkin 场景纳入 Edge Cases

#### API 契约 (API Contract)
- [ ] 遵循 OpenAPI 标准的 API 契约定义位于 `docs/api/openapi.yaml`
- [ ] API 契约测试通过（`tests/contracts/test_api_contract_layered_retrieval.py`）
- [ ] API 版本管理正确（`/api/v1/search/layered`）

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
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_layered_retrieval.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_layered_retrieval.py`
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
| **TDD 单元测试** | 分层检索端口 | 端口契约方法签名、参数校验 | `tests/unit/domain/ports/test_layered_retrieval_port.py` | Task 1 |
| **TDD 单元测试** | 分层检索服务 | 自底向上/自顶向下/降级/输入验证 | `tests/unit/application/services/test_layered_retrieval_service.py` | Task 2 |
| **TDD 单元测试** | 分层检索异常 | 构造/属性/`to_dict()`/cause 链/HTTP 映射/序列化 | `tests/unit/domain/exceptions/test_layered_retrieval_exceptions.py` | Task 1 |
| **SDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_layered_retrieval.feature` | Task 0 |
| **SDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_layered_retrieval.py` | Task 0 |
| **SDD 验收测试** | 收尾验收场景 | `src` 与测试目录完成清单最终确认 | `test_acceptance_layered_retrieval.feature` | Task 4 |
| **SDD 验收测试** | 收尾 BDD 步骤实现 | 完成清单断言与步骤函数 | `test_acceptance_layered_retrieval.py` | Task 4 |
| **SDD 契约测试** | 端口契约 | 端口注册、版本、兼容性、实现解析 | `tests/contracts/test_port_contract_layered_retrieval.py` | Task 0 |
| **TDD 领域异常测试** | 异常 HTTP 映射 | HTTP 映射/状态码/响应结构 | `tests/unit/interfaces/api/test_exception_handlers.py` | Task 1 |
| **TDD 领域异常测试** | 编码唯一性 | 所有异常类 `code` 无碰撞 | `tests/unit/domain/exceptions/test_error_code_uniqueness.py` | Task 1 |
| **TDD 领域异常测试** | 编码子域范围 | 子域范围/继承链一致性 | `tests/unit/domain/exceptions/test_code_ranges.py` | Task 1 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖、禁止跨层引用 | `tests/unit/architecture/test_arch_layered_retrieval.py` | Task 3 |
| **集成测试** | 层间协作 | 真实 L3VectorPort + DenseSearchService 协作 | `tests/integration/test_integration_layered_retrieval.py` | Task 3 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（核心业务流，事务管理）
- [ ] **领域层覆盖率 ≥90%**（关键业务逻辑，不变量验证）
- [ ] **接口层覆盖率 ≥85%**（API 路由，请求响应验证）
- [ ] **集成测试覆盖率 ≥75%**（`pytest --cov=tests/integration --cov-fail-under=75`）

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
| **外部服务隔离** | Qdrant 测试前清理或用 mock | 真实数据被污染 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突导致并行失败 |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **BDD async 配合** | BDD 步骤函数不使用 @pytest.mark.asyncio，用 event_loop.run_until_complete() 运行 async | 直接用 @pytest.mark.asyncio 会导致 BDD context 数据丢失 |

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

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 分层检索端口契约定义 | Task 0 | SDD 规范定义 | `test_port_contract_layered_retrieval.py` |
| AC-1 | 分层检索端口契约定义 | Task 1 | TDD 端口实现 | `test_layered_retrieval_port.py` |
| AC-2 | L4→L3 自底向上遍历 | Task 2 | TDD 自底向上逻辑 | `test_layered_retrieval_service.py` |
| AC-3 | L3→L4 自顶向下展开 | Task 2 | TDD 自顶向下逻辑 | `test_layered_retrieval_service.py` |
| AC-4 | 分层检索编排服务 | Task 2 | TDD 服务编排 | `test_layered_retrieval_service.py` |
| AC-5 | 分层检索异常体系 | Task 1 | TDD 异常定义 | `test_layered_retrieval_exceptions.py` |
| AC-6 | L2 文档摘要检索（骨架） | Task 2 | TDD 骨架实现 | `test_layered_retrieval_service.py` |
| AC-7 | L1 跨文档摘要检索（骨架） | Task 2 | TDD 骨架实现 | `test_layered_retrieval_service.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-5

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。这是 SDD 规范驱动的基础。

- [ ] Subtask 0.1: 定义领域事件 Schema（`LayeredRetrievalCompleted` 事件，REALTIME 模式；如不保留事件可跳过，同步更新 AC-4 验证标准）
- [ ] Subtask 0.2: 定义分层检索值对象（`DocumentSummary`、`CrossDocSummary`，可选）
- [ ] Subtask 0.3: 创建/更新 `docs/api/openapi.yaml`（新增 `POST /api/v1/search/layered` 端点）
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_layered_retrieval.feature`
- [ ] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_layered_retrieval.py`
- [ ] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 领域层端口契约 + 异常体系

**关联 AC:** AC-1, AC-5

> **说明：** 本 Task 定义领域层端口契约（`LayeredRetrievalPort`）和异常体系（`LayeredRetrievalError`、`LevelTransitionError`），
> 是后续所有实现 Task 的依赖基础。

#### TDD 循环 [A]：分层检索端口契约

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_layered_retrieval_port.py`（端口契约签名验证） |
| 🟢 绿 | 实现 `src/domain/ports/layered_retrieval.py`（`LayeredRetrievalPort` Protocol） |
| 🔄 重构 | 添加 docstring、类型注解、架构决策注释 |

- [ ] Subtask 1.1: 🔴 红 — 编写分层检索端口失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 `LayeredRetrievalPort` Protocol
- [ ] Subtask 1.3: 🔄 重构 — 优化端口代码

#### TDD 循环 [A-1]：分块级索引重构（索引流程适配）

> **说明：** 分层检索的 L4→L3 回溯和 L3→L4 展开依赖**分块级向量索引**——每个 Child/Parent 块必须生成独立向量并写入 Qdrant。当前索引流程是文档级粒度：将整个文档文本拼接后生成一个向量，写入一个 Qdrant 点。分块流程 (`SemanticChunkingService`) 将 Child/Parent 块存入 PostgreSQL，但**不写入 Qdrant**。因此需重构索引流程，将分块管道前置到索引管道之前，确保每个 Chunk 块都有独立向量索引和完整 payload（含 `parent_chunk_id`、`index_level`、`chunk_id`、`document_id`）。

**集成方案（关键）：** 当前 `document_processing_flow.py`（parse→embed→index）与 `SemanticChunkingHandler`（监听 DocumentProcessed 事件异步分块）是两条独立管道，无同步点。推荐采用**方案 B 变体**：在 `SemanticChunkingHandler` 完成分块持久化后，发布 `ChunkIndexed` 事件（或复用 `RAGIndexed`），由新增的 `ChunkIndexingHandler` 消费，从 PostgreSQL 读取已持久化的 chunks 并逐块嵌入、索引到 Qdrant。点 ID 必须等于 `str(chunk.chunk_id)`（而非随机 UUID），确保 `get_point()` 可通过 `parent_chunk_id` 回溯。

**嵌入保护（关键）：** 批量嵌入需增加 `max_batch_size`（建议 16-32 个 chunk，超量分批）和 token 截断保护（发送前按 bge-m3 的 8192 token 上限截断），避免 API 413 或超时。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/workflow/test_document_tasks_index_payload.py`（验证 payload 包含 parent_chunk_id 和 index_level） |
| 🟢 绿 | 新增 `ChunkIndexingHandler` 消费分块完成事件，从 PostgreSQL 读取 chunks 逐块嵌入并 upsert 到 Qdrant（点 ID = chunk_id，payload 含 parent_chunk_id/index_level/chunk_id/document_id；文档级点追加 index_level="document" 以保持一致性） |
| 🔄 重构 | 优化批量嵌入（max_batch_size + token 截断 + 并发控制），确保文档级与分块级索引共存（通过 index_level 区分，检索时自动注入对应层级过滤条件） |

- [ ] Subtask 1.4: 🔴 红 — 编写分块级索引失败测试
- [ ] Subtask 1.5: 🟢 绿 — 重构索引流程为分块级粒度，确保每个 Chunk 块独立向量 upsert 并包含完整 payload
- [ ] Subtask 1.6: 🔄 重构 — 优化索引流程，确保文档级与分块级索引共存（通过 index_level 区分）

#### TDD 循环 [B]：分层检索异常体系

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_layered_retrieval_exceptions.py`（异常构造/序列化） |
| 🟢 绿 | 实现 `src/domain/exceptions/layered_retrieval_exceptions.py` |
| 🔄 重构 | 注册异常到 `_code_ranges.py`、`__init__.py`、`EXCEPTION_HTTP_MAP`，并更新 `test_code_ranges.py` 中的 `allowed_child_parent_subdomains` |

- [ ] Subtask 1.7: 🔴 红 — 编写分层检索异常失败测试
- [ ] Subtask 1.8: 🟢 绿 — 实现 `LayeredRetrievalError` 和 `LevelTransitionError`
- [ ] Subtask 1.9: 🔄 重构 — 注册异常到 `_code_ranges.py`（新增 `retrieval` 子域 280-281）、`__init__.py`、`EXCEPTION_HTTP_MAP`、`test_code_ranges.py.allowed_child_parent_subdomains`

**完成标准/Definition of Done:**
- [ ] `LayeredRetrievalPort` 端口契约定义完成
- [ ] `LayeredRetrievalError`（EXCEPTION_280）和 `LevelTransitionError`（EXCEPTION_281）定义完成
- [ ] 异常体系完整注册（`_code_ranges.py`/`__init__.py`/`EXCEPTION_HTTP_MAP`/`test_code_ranges.py`）
- [ ] 所有 TDD 循环测试通过
- [ ] 异常编码无碰撞（`grep -rw "EXCEPTION_28[0-9]"` 零输出）
- [ ] 分块级索引重构完成：每个 Child/Parent 块在 Qdrant 中有独立向量点，payload 含 parent_chunk_id/index_level/chunk_id/document_id

---

### Task 2: 分层检索应用服务 — 含完整 TDD 循环

**关联 AC:** AC-2, AC-3, AC-4, AC-6, AC-7

> **说明：** 本 Task 实现 `LayeredRetrievalService` 应用层编排服务，包括 L4→L3 自底向上遍历、
> L3→L4 自顶向下展开、L2/L1 骨架实现。

#### TDD 循环 [A]：自底向上（L4→L3）遍历

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_layered_retrieval_service.py`（`test_bottom_up_l4_to_l3`） |
| 🟢 绿 | 实现 `LayeredRetrievalService._search_bottom_up()` 方法 |
| 🔄 重构 | 优化回溯逻辑、去重方案、payload 构建 |

- [ ] Subtask 2.1: 🔴 红 — 编写自底向上遍历失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 `_search_bottom_up()` 方法
- [ ] Subtask 2.3: 🔄 重构 — 优化回溯去重逻辑

#### TDD 循环 [B]：自顶向下（L3→L4）展开

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_layered_retrieval_service.py`（`test_top_down_l3_to_l4`） |
| 🟢 绿 | 实现 `LayeredRetrievalService._search_top_down()` 方法 |
| 🔄 重构 | 优化展开策略、Child 排序、结果截断 |

- [ ] Subtask 2.4: 🔴 红 — 编写自顶向下展开失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 `_search_top_down()` 方法
- [ ] Subtask 2.6: 🔄 重构 — 优化展开逻辑

#### TDD 循环 [C]：分层检索编排服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_layered_retrieval_service.py`（`test_search_bottom_up`、`test_search_top_down`、`test_search_input_validation`、`test_degrade_strategy`） |
| 🟢 绿 | 实现 `LayeredRetrievalService.search()` 入口方法 |
| 🔄 重构 | 添加降级策略、输入验证、日志 |

- [ ] Subtask 2.7: 🔴 红 — 编写编排服务失败测试（输入验证、降级、路由）
- [ ] Subtask 2.8: 🟢 绿 — 实现 `LayeredRetrievalService` 完整编排
- [ ] Subtask 2.9: 🔄 重构 — 优化编排逻辑、添加 WARNING 日志

#### TDD 循环 [D]：L2/L1 骨架实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_layered_retrieval_service.py`（`test_search_top_down_l2_returns_empty`、`test_search_top_down_l1_returns_empty`） |
| 🟢 绿 | 实现骨架返回空列表逻辑 |
| 🔄 重构 | 添加 TODO 标记、WARNING 日志 |

- [ ] Subtask 2.10: 🔴 红 — 编写 L2/L1 骨架失败测试
- [ ] Subtask 2.11: 🟢 绿 — 实现骨架返回空列表
- [ ] Subtask 2.12: 🔄 重构 — 添加 TODO 标记和日志

**完成标准/Definition of Done:**
- [ ] `LayeredRetrievalService` 完整实现（自底向上 + 自顶向下 + 骨架）
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥85%（应用层）
- [ ] 降级策略验证通过

---

### Task 3: 端口注册 + 集成测试 + 架构验证

**关联 AC:** AC-1, AC-4

> **性质说明：** 本 Task 将服务注册到组合根，并编写集成测试验证真实服务协作。

#### 端口注册到 composition_root.py

- [ ] Subtask 3.1: 在 `src/composition_root.py` 中注册 `layered_retrieval_service` 端口
- [ ] Subtask 3.2: 更新端口契约测试 `tests/contracts/test_port_contract_layered_retrieval.py`

#### 集成测试实现

- [ ] Subtask 3.3: 编写 `tests/integration/test_integration_layered_retrieval.py`（自底向上集成测试）
- [ ] Subtask 3.4: 编写自顶向下集成测试
- [ ] Subtask 3.5: 实现集成测试隔离（UUID 唯一标识 + 清理）

#### 架构验证测试

- [ ] Subtask 3.6: 创建 `tests/unit/architecture/test_arch_layered_retrieval.py`
- [ ] Subtask 3.7: 验证领域层零外部依赖
- [ ] Subtask 3.8: 验证依赖方向正确
- [ ] Subtask 3.9: 补充 Parent-Child 层级关系测试（IndexLevel 枚举值、parent_chunk_id 引用完整性、层级关系约束）

**完成标准/Definition of Done:**
- [ ] 端口注册完成
- [ ] 集成测试通过
- [ ] 架构验证测试通过（含 Parent-Child 层级关系测试）
- [ ] Ruff + MyPy 全部通过

---

### Task 4: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_layered_retrieval.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_layered_retrieval.py` 的 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达、保持步骤函数可维护性 |

- [ ] Subtask 4.1: 场景 1 — 验证 `src` 完成清单的逐项确认
- [ ] Subtask 4.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单的逐项确认
- [ ] Subtask 4.3: 运行开发结束验收测试并确认通过
- [ ] Subtask 4.4: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** epics_v1.0.md Story 3.5 节定义

- **架构模式:** 六边形架构（Ports & Adapters）、分层检索（L1-L4 检索粒度）
- **设计约束:**
  - 领域层零外部依赖（仅 Python 标准库）
  - 依赖方向：domain ← application ← interfaces / infrastructure
  - 所有端口通过 `composition_root.py` 统一注册
  - 现有 `SemanticChunk` 值对象已含 `parent_chunk_id` 和 `IndexLevel` 枚举，可直接复用
- **技术栈:** Python 3.11+、FastAPI 0.104+、Qdrant 1.7+（向量存储）、bge-m3（嵌入模型）

### 关键架构决策

**来源:** epics_v1.0.md Story 3.5 节 + Story 3.4 已有实现经验

| 决策 | 方案 | 理由 |
|------|------|------|
| **L4→L3 回溯方式** | 通过 `payload.parent_chunk_id` 过滤 Qdrant | 已有 `parent_chunk_id` 字段，无需额外索引 |
| **L3→L4 展开方式** | L3 检索后，按 `parent_chunk_id` 过滤检索 Child 子块 | 复用现有 `L3VectorPort.search()` 的 payload 过滤 |
| **L2/L1 实现策略** | MVP 骨架（返回空列表），V1 完整实现 | 降低 MVP 风险，核心价值在 L4→L3 双向遍历 |
| **异常子域** | 新增 `retrieval` 子域（280-281） | `business` 子域（201-209）已有 8 个异常类，为保持扩展空间 |
| **端口命名** | `LayeredRetrievalPort` 而非 `LayeredSearchPort` | 强调"检索"而非"搜索"，与 `SearchResult` 区分 |
| **服务编排** | 复用 `DenseSemanticSearchService` 而非重新实现检索 | 保持与现有搜索服务一致，避免重复 |
| **L4 检索策略** | 默认使用 Dense 语义检索（L4 Child 块有向量索引） | Child 块已索引向量，可直接复用现有 Dense 检索 |
| **Qdrant payload 扩展** | 修改 `document_tasks.py` 索引流程，在 payload 中存储 `parent_chunk_id` 和 `index_level` | 分层检索依赖 payload 过滤进行回溯/展开 |
| **索引粒度** | 重构索引流程：从文档级→分块级（每个 Child/Parent 块生成独立向量 upsert 到 Qdrant） | 当前文档级索引无法支持 L4/L3 分层检索 |

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── events/
│   │   └── layered_retrieval_events.py          # [新增] LayeredRetrievalCompleted 事件
│   ├── exceptions/
│   │   ├── layered_retrieval_exceptions.py    # [新增] 分层检索异常
│   │   └── _code_ranges.py                   # [修改] 新增 retrieval 子域
│   └── ports/
│       ├── __init__.py                       # [修改] 导出新端口
│       └── layered_retrieval.py              # [新增] LayeredRetrievalPort Protocol
│
├── application/
│   └── services/
│       └── layered_retrieval_service.py       # [新增] LayeredRetrievalService
│
├── composition_root.py                       # [修改] 注册新服务端口
│
└── interfaces/
    └── api/
        └── layered_retrieval.py              # [新增] 分层检索 API 路由（可选 MVP）

tests/
├── acceptance/
│   ├── test_acceptance_layered_retrieval.feature # [新增] Gherkin 场景
│   └── test_acceptance_layered_retrieval.py     # [新增] BDD 步骤实现
├── contracts/
│   └── test_port_contract_layered_retrieval.py # [新增] 端口契约测试
├── integration/
│   └── test_integration_layered_retrieval.py  # [新增] 集成测试
├── unit/
│   ├── application/
│   │   └── services/
│   │       └── test_layered_retrieval_service.py  # [新增] 应用服务单元测试
│   ├── architecture/
│   │   └── test_arch_layered_retrieval.py     # [新增] 架构验证测试
│   └── domain/
│       ├── exceptions/
│       │   └── test_layered_retrieval_exceptions.py  # [新增] 异常测试
│       └── ports/
│           └── test_layered_retrieval_port.py  # [新增] 端口单元测试
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 3.4: RRF 融合排序](./3-4-rrf-fusion-ranking.md)

**关键学习/Key Learnings:**
1. **GraphSearchService 仅注入 L5GraphPort**（领域端口），不使用 GraphRetriever（基础设施具象类）— 保持六边形架构严格
2. **HybridSearchService 构造函数新参数全部具名默认**（`graph_search=None`, `weights=None`, `reranker=None`）— 保证向后兼容
3. **端口升级时必须先 `unregister()` 再 `register()`** — `PortRegistry.register()` 对同名不同 spec 抛 `ConflictError`
4. **异常注册 7 步流程**：
   1. 定义异常类（layered_retrieval_exceptions.py）
   2. CODE_RANGES 注册子域（_code_ranges.py）
   3. _CLASS_TO_SUBDOMAIN 注册映射（_code_ranges.py）
   4. __init__.py 导出（import + __all__）
   5. EXCEPTION_HTTP_MAP 注册（exception_handlers.py）
   6. allowed_child_parent_subdomains 登记（test_code_ranges.py）
   7. 测试文件更新（test_layered_retrieval_exceptions.py + test_exception_handlers.py 精确集合断言）
5. **`fuse` 函数作为可调用对象注入**，不注册为端口

**应用到本故事/Applied to This Story:**
- [x] `LayeredRetrievalService` 注入现有服务（`DenseSemanticSearchService`, `L3VectorPort`），不直接操作 Qdrant
- [x] 构造函数新增参数全部具名默认（`reranker=None`, `weights=None`）
- [x] 使用 `_safe_*_search()` 私有方法模式实现降级策略
- [x] 异常注册遵循 7 步流程
- [x] 端口注册使用 `Lifetime.SCOPED`（轻量编排）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.2 |
| **Version** | create-story workflow v2.9.0 |
| **Execution Date** | 2026-08-12 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md`（无 L1-L4 检索粒度章节，需补充） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/3-4-rrf-fusion-ranking.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `epics_v1.0.md` 提取
- [x] 前一个故事学习经验整合
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-5-layered-search-l1-l4.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/ports/layered_retrieval.py` - 分层检索端口契约
- `src/domain/exceptions/layered_retrieval_exceptions.py` - 分层检索异常
- `src/domain/events/layered_retrieval_events.py` - 分层检索事件
- `src/application/services/layered_retrieval_service.py` - 分层检索服务
- `src/interfaces/api/layered_retrieval.py` - API 路由（可选 MVP）
- `tests/unit/domain/ports/test_layered_retrieval_port.py` - 端口单元测试
- `tests/unit/domain/exceptions/test_layered_retrieval_exceptions.py` - 异常测试
- `tests/unit/application/services/test_layered_retrieval_service.py` - 应用服务测试
- `tests/unit/architecture/test_arch_layered_retrieval.py` - 架构验证测试
- `tests/integration/test_integration_layered_retrieval.py` - 集成测试
- `tests/contracts/test_port_contract_layered_retrieval.py` - 端口契约测试
- `tests/acceptance/test_acceptance_layered_retrieval.feature` - Gherkin 场景
- `tests/acceptance/test_acceptance_layered_retrieval.py` - BDD 步骤实现

**待更新的文件/To Be Updated:**
- `src/domain/exceptions/_code_ranges.py` — 新增 `retrieval` 子域（280-281）和 `_CLASS_TO_SUBDOMAIN` 映射
- `src/domain/exceptions/__init__.py` — 导出 `LayeredRetrievalError`、`LevelTransitionError`
- `src/domain/ports/__init__.py` — 导出 `LayeredRetrievalPort`
- `src/interfaces/api/exception_handlers.py` — 注册 `EXCEPTION_HTTP_MAP` 映射
- `src/composition_root.py` — 注册 `layered_retrieval_service` 端口
- `src/infrastructure/workflow/tasks/document_tasks.py` — 重构索引流程为分块级粒度
- `configs/event_channels.yaml` — 新增 `LayeredRetrievalCompleted` 事件通道（如保留事件）
- `src/infrastructure/messaging/channel_router.py` — 同步更新 `DEFAULT_MAPPINGS`（如保留事件）
- `tests/unit/domain/exceptions/test_code_ranges.py` — `allowed_child_parent_subdomains` 添加 `("retrieval", "business")`
- `tests/unit/interfaces/api/test_exception_handlers.py` — 更新精确类型集合断言

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.5 |
| **Story Key** | 3-5-layered-search-l1-l4 |
| **File** | `_bmad-output/implementation-artifacts/stories/3-5-layered-search-l1-l4.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | P0 |
| **覆盖 FR** | FR-SR-05 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`
6. [x] **Epic 3 架构对齐重构（2026-08-21）**：
   - [x] `LayeredRetrievalService` 注入 `HybridSearchService` 替代 `DenseSemanticSearchService`，正确复用 Story 3.4 RRF 融合能力
   - [x] `LayeredRetrievalPort` 新增 `retrieve()` 便捷方法，对齐架构 §17.1.5 RAGService 语义
7. [x] **R1/R2 端口层次对齐（2026-08-22）**：
   - [x] `LayeredRetrievalService` 构造函数类型从 `hybrid_search: Any, l3_vector: Any` 修正为 `hybrid_search: HybridSearchPort, l3_vector: L3VectorPort`
   - [x] 构造函数类型精确化，消除 `Any` 类型
   - [x] 双轨索引消除：`generate_embedding`/`index_document` 废弃，索引统一为事件驱动链（`DocumentProcessed → SemanticChunking → RAGIndexed → ChunkIndexingHandler`）
   - [x] `document_processing_flow` 仅执行解析阶段，索引委托事件驱动链
   - [x] 所有测试 41 项通过，lint/mypy 通过

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | 命名不一致：`LayeredSearchCompleted` 与 `LayeredRetrievalPort` 冲突 | P0 | 统一为 `retrieval`：事件名→`LayeredRetrievalCompleted`，事件文件→`layered_retrieval_events.py`，验收测试文件→`test_acceptance_layered_retrieval.*` |
| 2 | AC-2/AC-3 中 `L3VectorPort.search()` 调用方式不可行（需 `query_vector` 向量参数） | P0 | 修正为复用查询向量带 payload 过滤，或使用 `L3VectorPort.get_point()` 按 ID 回溯 |
| 3 | Qdrant payload 实际不存储 `parent_chunk_id` 和 `index_level` | P0 | 新增 Task 1 TDD 循环 [A-1]：修改 `document_tasks.py` 索引流程，在 payload 中追加这两个字段 |
| 4 | 异常注册"5步流程"遗漏 `allowed_child_parent_subdomains` 和 `_CLASS_TO_SUBDOMAIN` | P0 | 修正为"7步流程"，明确列出每一步，补充白名单位置说明 |
| 5 | 引用不存在的 `_bmad-output/planning-artifacts/architecture.md` 和"分层检索设计决策"文档 | P0 | 替换为 `epics_v1.0.md` Story 3.5 节作为来源 |
| 6 | 延迟预算 500ms 与 NFR-PERF-01 MVP 800ms 冲突，未标注版本归属 | P0 | 标注为 V1 目标，MVP 阶段放宽值，并补充"并发检索≥50"指标 |
| 7 | 测试路径缺少 `services/` 子目录，端口单元测试误标为"端口契约测试" | P0 | 修正项目结构图和测试分类表 |
| 8 | `register_port()` 缺失 `module` 参数 | P0 | 在 AC-1 验证标准和端口清单中补充 module 参数要求 |
| 9 | `business` 子域"已满"声明不准确（209 仍可用） | P1 | 修正为"已有 8 个异常类，为保持扩展空间" |
| 10 | 事件命名模式描述与实际不符（`[Aggregate][EventName]` 模式不存在） | P1 | 修正为"业务含义直名" |
| 11 | 索引粒度假设不成立：当前文档级索引，L4/L3 分块级向量索引不存在 | P0 | 重构索引流程为分块级粒度，升级 Task 1 [A-1] 为分块级索引重构 |
| 12 | 文档缺少"待更新的文件/To Be Updated"清单 | P1 | 新增 9 个待更新文件（_code_ranges.py/__init__.py/exception_handlers.py 等） |
| 13 | AC-5 验证标准缺少 HTTP 映射测试覆盖要求 | P1 | 新增第 7 条验证标准：test_exception_handlers.py 精确类型集合断言 |
| 14 | 测试分类表重复行（第 297 行与第 303 行） | P2 | 合并重复行，删除冗余条目 |
| 15 | LevelTransitionError 描述用语不一致（"失败"vs"非法"） | P2 | 统一为"层级遍历非法" |
| 16 | SDD 异常契约清单 8 项 vs 7 步流程字面矛盾 | P2 | BDD 验收场景标注"（额外）" |
| 17 | 集成测试覆盖率 ≥70% 与 epics ≥75% 不一致 | P0 | 修正为 ≥75% |
| 18 | 融合延迟 P95<50ms 遗漏（epics 明确要求） | P0 | AC-2/AC-3 补充融合延迟指标 |
| 19 | 向量复用不可行：`DenseSemanticSearchService.search()` 不暴露向量参数 | P0 | 明确需扩展 `search_with_vector()` 或直接调用 `L3VectorPort.search()` 传向量；`get_point()` 回溯为推荐方案 |
| 20 | 分块管道与索引管道集成方案缺失 | P0 | Task 1 [A-1] 补充集成方案：新增 `ChunkIndexingHandler` 消费分块完成事件 |
| 21 | 多级全遍历（L1↔L4）未说明 MVP 限制 | P1 | AC-2/AC-3 标注 MVP 仅支持相邻单级遍历 |
| 22 | Parent-Child 层级关系专项测试缺失 | P1 | 在架构测试中补充层级关系测试（IndexLevel 枚举、引用完整性） |
| 23 | 嵌入批量保护缺失（max_batch_size/token 截断） | P1 | Task 1 [A-1] 补充嵌入保护要求 |
| 24 | 事件发布 Task 0（必选）与 AC-4（可选）矛盾 | P2 | Subtask 0.1 标注"如不保留事件可跳过" |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 2026-08-12
**审查模式:** 多Agent并行审查（端口契约/异常体系/事件与测试/需求一致性）

#### 需决策 Decision Needed

- [ ] MVP 阶段延迟预算是否按 NFR-PERF-01 的 800ms 总预算重新分配（当前 AC-2=200ms + AC-3=250ms 为 V1 目标）

#### 已修复 Patch

- [x] 命名统一：`LayeredSearchCompleted` → `LayeredRetrievalCompleted`，所有 `layered_search` → `layered_retrieval`
- [x] AC-2/AC-3 回溯/展开机制修正（复用查询向量 + payload 过滤 / `get_point()` 按 ID 回溯）
- [x] 新增 Task 1 TDD 循环 [A-1]：Qdrant payload 扩展
- [x] 异常注册流程 5步→7步
- [x] 架构引用修正（删除不存在的 architecture.md 引用）
- [x] 延迟预算标注 V1 目标 + 补充并发检索≥50
- [x] 测试路径与标注修正
- [x] `module` 参数补充

#### 已推迟 Defer

- [ ] L2/L1 骨架实现的延迟预算约束（P2，MVP 阶段骨架返回空列表开销极低）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] Round 1 代码审查已完成（注入EmbeddingServicePort + 修复P1/P2/P3问题）
- [x] 运行 `dev-story` 开始实施
- [x] **Epic 3 架构对齐重构（2026-08-21）**：注入 HybridSearchService + retrieve() 统一入口 + 事件驱动索引单轨化
- [x] 运行 `code-review` 进行代码审查
- [x] 运行 `/bmad:tea:automate` 生成测试（可选）

---

### Round 1 代码审查修复记录

**审查日期:** 2026-08-15
**审查模式:** 4 Agent 并行（端口契约/应用服务/测试异常/系统集成）+ 3 Agent 反思评审

#### 修复清单

| # | 问题 | 严重度 | 文件 | 修复方案 |
|---|------|--------|------|----------|
| 1 | 访问私有属性 `_dense_search._embedding` 破坏封装 | P1 | `layered_retrieval_service.py:443` | 注入 `EmbeddingServicePort`，消除私有属性穿透 |
| 2 | 单元测试 `_make_l3_vector()` 未传 `spec=L3VectorPort` | P1 | `test_layered_retrieval_service.py:59` | 改为 `AsyncMock(spec=L3VectorPort)` |
| 3 | API 路由未实现（openapi 契约推迟） | P1 | — | Story 文件标注跳过，openapi.yaml 保留 `x-implemented: false` |
| 4 | 端口常量 `LAYERED_RETRIEVAL_LEVELS` 零引用（死代码） | P2 | `layered_retrieval_service.py:31` | 服务层导入复用端口常量，删除本地 `VALID_LEVELS` |
| 5 | 端口 docstring 提及具体实现类名 | P2 | `layered_retrieval.py:11-12,34-35` | 删除 docstring 中具体实现类名引用 |
| 6 | 构造函数参数使用 `Any` 类型注解 | P2 | `layered_retrieval_service.py:68-69` | `embedding_service` 标注为 `EmbeddingServicePort` |
| 7 | `tenant_id` 处理不一致（L3VectorPort 路径 vs Dense 路径） | P2 | `layered_retrieval_service.py:452-454` | 新增 `_merge_filter_with_tenant()` 统一封装 |
| 8 | `limit` 参数语义过载（魔法数 5） | P2 | `layered_retrieval_service.py:459` | 抽取 `_MAX_EXPAND_PARENTS = 5` 独立常量 |
| 9 | 降级路径丢失 L4 失败上下文 | P2 | `layered_retrieval_service.py:338-347` | 补充降级上下文（已记录日志，待后续增强） |
| 10 | 集成测试冗余 `@pytest.mark.asyncio` | P2 | `test_integration_layered_retrieval.py` | 移除冗余装饰器（`asyncio_mode=auto` 已自动处理） |
| 11 | 事件设计残留（Story 文件未同步） | P2 | Story 文件 | 标注"已跳过" |
| 12 | 裸 `except Exception` 未标注意图 | P2 | `layered_retrieval_service.py` | 区分重抛模式（正确，加注释）与 best-effort 吞异常 |
| 13 | `asyncio.ensure_future` + 逐个 `await` 不规范 | P3 | `layered_retrieval_service.py:407-411` | 改为 `asyncio.gather(*tasks, return_exceptions=True)` |
| 14 | 异常 context 缺少 `tenant_id` | P3 | `layered_retrieval_service.py:448,470` | 补充 `tenant_id` 到异常 context |
| 15 | `tenant_id` 空白校验绕过 | P3 | `layered_retrieval_service.py:453` | 统一在 `_validate_inputs` 中增加 tenant_id 空白校验 |

#### 质量门禁通过情况

- [x] 单元测试全部通过：17 passed
- [x] 异常测试通过：36 passed（含端口/异常/架构）
- [x] 集成测试通过：6 passed
- [x] 验收测试通过：12 passed
- [x] 端口契约测试通过：6 passed
- [x] Ruff 检查通过：All checks passed
- [x] MyPy 检查通过：Success: no issues found

---

### Round 2 代码审查修复记录

**审查日期:** 2026-08-15
**审查模式:** 3 Agent 并行（并发安全/业务正确性/测试充分性）

#### 修复清单

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | 降级路径 `except Exception` 掩盖 `SystemException` 基础设施故障 | P1 | 区分 `SystemException`（传播）与业务异常（降级） |
| 2 | 排序无 tie-breaker 导致结果不确定 | P2 | 改为 `(-score, id)` 复合键排序 |
| 3 | Child 展开截断未显式按分数排序（依赖后端行为） | P2 | 添加 `child_results.sort(key=..., reverse=True)` |
| 4 | limit 参数无上限校验 | P2 | 新增 `_MAX_LIMIT = 200` 常量，`_validate_inputs` 查越限 |
| 5 | `_merge_filter` 空 dict `{}` 被静默丢弃 | P2 | `if base_filter:` → `if base_filter is not None:` |
| 6 | 自底向上路径未截断 parent content | P2 | 应用 `_safe_truncate(content, 200)` |
| 7 | 自顶向下 Child 展开串行化（5 次串行网络请求） | P1 | 改为 `asyncio.gather` 并发展开 |
| 8 | 缺少 API 契约测试文件 | P2 | 创建 `test_api_contract_layered_retrieval.py`（4 测试） |
| 9 | 缺少 `search_bottom_up L1` 返回空测试 | P2 | 新增 `test_search_bottom_up_l1_returns_empty` |
| 10 | 缺少自顶向下无匹配测试 | P3 | 新增 `test_top_down_no_match_returns_empty` |
| 11 | `_search_l3_direct`/`_search_l4_direct`/`_search_top_down_l3_to_l4` 缺少 `Raises` 段 | P2 | docstring 补充 `Raises` 段 |
| 12 | `_safe_truncate` 未校验 `max_len` | P3 | 新增 `max_len < 1` 防御性校验 |
| 13 | 测试覆盖增强：tenant_id 空白/超限 limit/SystemException 传播/异常路径/`_fetch_parent`/`_merge_filter_with_tenant` | P2 | 新增 8 个单元测试 |

#### 质量门禁通过情况

- [x] 全部测试通过：723 passed（含全量 723 个测试）
- [x] Ruff 检查通过：All checks passed
- [x] MyPy 检查通过：Success: no issues found

---

## 📚 模板使用说明 Template Usage Guide

### 快速开始

1. 复制本模板到新文件
2. 替换所有 `[占位符]` 为实际内容
3. 根据 Story 类型调整覆盖率要求（见下表）
4. 确保 Task 0（SDD 规范定义）为必选前置
5. 每个 Task 包含自己的 TDD 循环（🔴红/🟢绿/🔄重构）
6. 填写 AC→Task→Subtask 追溯矩阵

### 适用场景与层类型对应关系

| 层类型 | Story 类型 | 覆盖率要求 | 测试重点 |
|--------|-----------|-----------|---------|
| **应用层 (Application)** | 应用层 Story | ≥85% | 用例逻辑/事务管理/编排/降级策略 |

---

**故事版本/Story Version:** v1.4.0
**创建日期/Created:** 2026-08-12
**最后更新/Last Updated:** 2026-08-21
**更新说明/Description:**
- v1.0.0: 创建故事文件 — 分层检索（L1-L4）完整定义
- v1.1.0: 文档审查 Round 1 修复（命名统一/回溯机制修正/Qdrant payload 扩展/异常 7 步流程/架构引用修正/延迟预算标注/测试路径修正/module 参数补充）
- v1.2.0: 文档审查 Round 2 修复（索引粒度重构/待更新文件清单/AC-5 增强/用语统一/测试分类表去重/SDD 清单分组）
- v1.3.0: 文档审查 Round 4 修复（融合延迟指标/集成测试覆盖率≥75%/向量复用方案/分块管道集成方案/多级遍历限制/Parent-Child 层级测试/嵌入保护/事件冲突消除）
- v1.3.1: dev-story 实施修正 — retrieval 子域范围 (280,289) 修正为 (280,281)（Story 3.9/3.10 新增 archive 子域占用 282-289 所致）
- v1.4.0: Epic 3 架构对齐重构 — 检索链路统一 + 索引单轨化
  - LayeredRetrievalService 注入 HybridSearchService（复用 Story 3.4 三路 RRF 融合），替换 DenseSemanticSearchService 直连
  - LayeredRetrievalPort 新增 retrieve() 便捷方法（对齐架构 §17.1.5 RAGService.retrieve 语义）
  - 双轨索引消除：generate_embedding/index_document 废弃，索引统一由 ChunkIndexingHandler 事件驱动链承担
  - document_processing_flow 仅执行解析阶段
  - 测试适配：41 项通过（含 ChunkIndexingHandler 等价验证），lint/mypy 通过
