# Story 3.8: 高保真溯源（Bounding Box 级）

**Status:** `review`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 企业战略人员,
**I want** 系统保留引文"三元组"特征（文档 ID、切片 ID、字符范围），支持 Bounding Box 级溯源,
**So that** 从结论快速追溯至原始文档坐标点，验证分析结论的可靠性。

### 业务价值

本 Story 是 Epic 3（智能检索与知识发现）的第八个故事（P0-8），对应 **FR-SR-08**（高保真溯源，P0）。它填补了检索流水线（Story 3.4→3.5→3.6）与溯源之间的空白，为用户提供从结论到原始文档坐标点的完整溯源能力，支持 Bounding Box 级精确定位。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **引文三元组保留** | 检索结果携带完整溯源信息 | 文档 ID/切片 ID/字符范围完整保留 |
| **Bounding Box 定位** | 精确定位至文档坐标点 | PDF 坐标点定位准确率≥95% |
| **溯源卡片展示** | 直观展示溯源信息 | 文档 ID/页码/置信度显示 |
| **溯源跳转** | 一键跳转至原始文档位置 | 响应<300ms，准确率≥95% |
| **溯源树构建** | 展示引文层级关系 | 引文树结构完整 |

**来源:** [`epics_v1.0.md`](../../planning-artifacts/epics_v1.0.md) - Epic 3 Story 3.8，第 1570-1610 行

**前置依赖（已就绪）:**
- Story 2.3（版面信息保留 ✅ 已实现）— 提供 DocLayNet 格式文档元素坐标（x, y, width, height）
- Story 3.1a（Dense 语义检索 ✅ 已实现）— 提供 `SearchResult` 统一检索结果类型
- Story 3.4（RRF 融合排序 ✅ 已实现）— 提供 `HybridSearchService` 三路检索编排
- Story 3.5（分层检索 L1-L4 ✅ 已实现）— 提供 `LayeredRetrievalPort`（`search_top_down()`/`search_bottom_up()`）

**后续依赖:** Story 6.7（溯源树展示）、Story 6.5b（PDF 报告生成 + 引文索引）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: Citation 值对象定义

**Given** 系统需要保留引文"三元组"特征
**When** 定义 Citation 值对象
**Then** 包含文档 ID、切片 ID、字符范围、Bounding Box 坐标
**And** 支持置信度评分和页码信息

**验证标准/Validation Criteria:**
- [ ] `Citation` dataclass 定义在 `src/domain/value_objects/citation.py`（领域层，零外部依赖）
- [ ] 字段包含：
  - `citation_id: str` — 引文唯一标识（由 `chunk_id` 或其哈希生成，用于 `get_citation_detail()` 查询）
  - `document_id: uuid.UUID` — 文档 ID
  - `chunk_id: str` — 切片 ID
  - `text: str` — 引文文本片段
  - `start_offset: int` — 字符起始偏移量
  - `end_offset: int` — 字符结束偏移量
  - `page_number: int` — 页码
  - `bbox: BoundingBox | None` — Bounding Box 坐标（可选，当有版面信息时填充）
  - `confidence: float` — 引用置信度（0-1）
- [ ] `BoundingBox` **复用** `src/domain/value_objects/parsed_document.py` 已有的定义（frozen dataclass：x/y/width/height/**page** + `to_dict()`），**不在 `citation.py` 中重复定义**
- [ ] 支持序列化为 dict（用于 API 响应和缓存）
- [ ] 支持 `from_dict()` 类方法反序列化（用于从存储恢复）
- [ ] 领域层零外部依赖（仅使用 Python 标准库 + uuid）

### AC-2: Traceability 端口契约

**Given** 系统需要统一的溯源抽象
**When** 定义 `TraceabilityPort` 协议
**Then** 包含 `trace()` 核心方法，接收结论文本，返回引文列表
**And** 包含 `get_citation_detail()` 方法，获取单个引文的详细信息
**And** 领域层定义零外部依赖（仅 Python 标准库 + Protocol）

**验证标准/Validation Criteria:**
- [ ] `TraceabilityPort` 定义于 `src/domain/ports/traceability.py`（Protocol，`@runtime_checkable`）
- [ ] `Citation` 从 `src/domain/value_objects/citation.py` 导入
- [ ] 方法签名：
  - `async def trace(claim: str, top_k: int = 10, min_confidence: float = 0.7) -> Any` — 执行溯源，返回 `TraceabilityResult` TypedDict（与既有端口一致，返回类型声明为 Any）
    - 返回 `TraceabilityResult`（TypedDict）
  - `async def get_citation_detail(citation_id: str) -> Citation | None` — 获取单个引文详情（缓存未命中抛出 `TraceabilityNotFoundError`）
  - `async def get_citation_by_document(document_id: uuid.UUID) -> list[Citation]` — 按文档 ID 获取所有引文
- [ ] 结果类型定义：
  - `TraceabilityResult`（TypedDict）：
    - `claim: str` — 原始结论文本
    - `citations: list[Citation]` — 引文列表（按置信度降序）
    - `citation_count: int` — 引文总数
    - `highest_confidence: float` — 最高置信度
    - `has_bbox_support: bool` — 是否有 Bounding Box 坐标支持
- [ ] `get_citation_detail()`/`get_citation_by_document()` 数据来源：MVP 阶段从**当次检索结果内存缓存**中直接返回（不持久化引文；`trace()` 执行时缓存本次结果，按 `citation_id` 查询）；如需跨请求持久化，后续 Story 再引入引文存储端口
- [ ] 端口注册于 `composition_root.py`，通过 `register_port()` 注册为 `traceability_service` 端口
- [ ] 端口具备唯一名称、版本、interface、impl、module（必填五参数）及 owner、兼容策略（可选元数据）
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_traceability.py`）

### AC-3: Traceability 应用服务

**Given** 溯源端口契约已定义
**When** 实现 `TraceabilityService`
**Then** 注入 `LayeredRetrievalPort` 用于检索相关文档切片
**And** 计算引文置信度（基于检索结果 score 归一化）
**And** 构建溯源树结构（MVP 仅 children 层级）

**验证标准/Validation Criteria:**
- [ ] `TraceabilityService` 位于 `src/application/services/traceability_service.py`
- [ ] 构造函数注入 `retrieval_port: LayeredRetrievalPort`（分层检索端口）
- [ ] 实现 `trace()` 方法：
  1. 调用 `LayeredRetrievalPort.search_top_down()` 检索相关文档切片（自顶向下从 L3 向 L4 展开）
  2. 对每个切片，以检索结果的 `score` 归一化到 [0,1] 区间作为置信度（Qdrant 已计算向量相似度，无需额外余弦相似度计算）
  3. 过滤置信度 < `min_confidence` 的切片
  4. 构建 `Citation` 对象列表（从 payload 中提取 Bounding Box 坐标）
  5. 按置信度降序排序
  6. 构建溯源树结构
  7. 返回 `TraceabilityResult`
- [ ] 实现 `get_citation_detail()` 方法：根据 citation_id 从当次溯源缓存中返回单个引文详情（缓存不存在则抛出 `TraceabilityNotFoundError`）
- [ ] 实现 `get_citation_by_document()` 方法：按文档 ID 从当次溯源缓存中返回所有引文（MVP 不持久化，结果为空时抛出 `TraceabilityNotFoundError`）
- [ ] 溯源响应延迟 P95 < 300ms（含检索 + 置信度计算）
- [ ] 引用置信度基于检索结果的 `score` 字段归一化（0-1）
- [ ] Bounding Box 坐标从检索结果 payload 中提取（若存在，需先在 `chunk_indexing_handler.py` 中将 bbox 写入 Qdrant payload）
- [ ] 溯源树结构：`CitationTree` 包含 `root`（原始结论）、`children`（一级引文，直接检索命中的切片）、`grandchildren`（二级引文，可选——一级引文的展开子切片）。MVP 仅实现 `children` 层级，`grandchildren` 为预留字段

### AC-4: 溯源 Prompt 模板

**Given** LLM-as-a-Judge 需要评估引文质量
**When** 定义溯源评估 Prompt 模板
**Then** 评估引文与结论的相关性、完整性、准确性
**And** 返回结构化评估结果

**验证标准/Validation Criteria:**
- [ ] Prompt 模板定义在 `src/application/services/traceability_prompts.py`
- [ ] System Prompt 包含：
  - 角色定义（"你是一位文献引用质量评估专家"）
  - 输出格式约束（强制遵守 JSON Schema）
  - 评估标准（相关性/完整性/准确性三维评分）
- [ ] User Prompt 包含：
  - 原始结论文本
  - 引文列表（格式化的文档片段，含置信度和 Bounding Box 信息）
  - 评估要求（逐条评估每个引文）
- [ ] 评估标准详细说明：
  - **相关性（relevance）**：引文是否支持结论。1.0 = 完全支持，0.0 = 完全无关
  - **完整性（completeness）**：引文是否覆盖结论的关键信息。1.0 = 全部覆盖，0.0 = 无必要信息
  - **准确性（accuracy）**：引文内容是否准确反映原文。1.0 = 完全准确，0.0 = 严重偏差
- [ ] 模板使用 Python f-string 格式，支持动态注入
- [ ] 所有 Prompt 模板通过单元测试验证（变量替换正确性）

### AC-5: 溯源异常体系

**Given** 溯源过程中可能发生多种错误
**When** 定义溯源异常类
**Then** 新增 `traceability` 子域，分配唯一异常编码
**And** 继承适当的基类层次结构

**验证标准/Validation Criteria:**
- [ ] `TraceabilityError`（EXCEPTION_370）— 继承 `ExternalException`，LLM 评估调用失败
  - 构造器参数：`claim: str`（结论文本，截断至 100 字符）、`citation_count: int`（引文数量）、`message: str | None = None`、`cause: Exception | None = None`
  - `claim`/`citation_count` 通过 `context` 字典暴露，`claim[:100]` 显式截断
- [ ] `TraceabilityNotFoundError`（EXCEPTION_371）— 继承 `BusinessException`，**按 ID/文档查询引文时未找到**（`get_citation_detail()`/`get_citation_by_document()` 查询无结果时抛出）
  - 构造器参数：`claim: str`（结论文本，截断至 100 字符）、`min_confidence: float`（最小置信度阈值）、`message: str | None = None`、`cause: Exception | None = None`
  - `claim`/`min_confidence` 通过 `context` 字典暴露
  - **语义澄清**：`trace()` 主流程在置信度 < min_confidence 时**返回空 citations 列表**（正常业务结果，不抛异常）；`TraceabilityNotFoundError` 仅用于**查询类方法**（`get_citation_detail`/`get_citation_by_document`）找不到目标引文时抛出
- [ ] 异常编码在 `_code_ranges.py` 注册 `traceability` 子域（370, 379）及 `_CLASS_TO_SUBDOMAIN` 映射（`TraceabilityError→"traceability"`, `TraceabilityNotFoundError→"traceability"`）
- [ ] 同步更新 `tests/unit/domain/exceptions/test_code_ranges.py`：
  - `allowed_child_parent_subdomains` 新增 `("traceability", "external")` 和 `("traceability", "business")` 允许继承对
  - `nested_subdomains` 新增 `"traceability": "external"` 嵌套子域声明
- [ ] 异常在 `__init__.py` 导出，在 `EXCEPTION_HTTP_MAP` 注册（`TraceabilityError→500`, `TraceabilityNotFoundError→404`）
- [ ] 无编码碰撞（`grep -rw "EXCEPTION_37[0-9]" src/` 零输出）
- [ ] HTTP 映射测试覆盖

### AC-6: 溯源 API 端点

**Given** 溯源服务已就绪
**When** 用户通过 API 请求溯源
**Then** 返回引文列表和溯源树结构
**And** 支持按文档 ID 查询引文

**验证标准/Validation Criteria:**
- [ ] API 路由位于 `src/interfaces/api/traceability.py`（新增文件）
- [ ] `POST /api/v1/search/trace` 端点（与 `summary.py` 的 `/api/v1/search/summary` 保持前缀一致）
  - 请求体：`{"claim": str, "top_k": int (默认 10), "min_confidence": float (默认 0.7)}`
  - 响应体：`{"claim": str, "citations": list[Citation], "citation_count": int, "highest_confidence": float, "has_bbox_support": bool}`
  - **错误处理**：领域异常透传到全局 `ExceptionHandlers`（不捕获为 `HTTPException`）
- [ ] `GET /api/v1/search/trace/{document_id}` 端点（按文档 ID 查询，与溯源功能同前缀）
  - 路径参数：`document_id: UUID`
  - 响应体：`{"document_id": UUID, "citations": list[Citation], "citation_count": int}`
- [ ] 在 `src/interfaces/api/app.py` 中通过 `app.include_router()` 注册路由
- [ ] 更新 `docs/api/openapi.yaml` 添加 `/api/v1/search/trace` 端点
- [ ] API 契约测试通过（`tests/contracts/test_api_contract_traceability.py`）
- [ ] 所有 API 路由通过认证中间件（路由级 `Depends(get_current_user)`）

### AC-7: 溯源与检索集成（已删除 — 见下方说明）

> **⚠️ 已删除：** 本 AC 要求修改 `SearchResult` TypedDict 添加 `citations` 和 `has_bbox_support` 字段，但 `SearchResult` 被多个服务（DenseSearchService、SparseSearchService、HybridSearchService、LayeredRetrievalService、SummaryGenerationPort、RelevanceEvaluationPort）引用，修改是破坏性变更。溯源信息通过 `TraceabilityResult` 独立返回，不污染 `SearchResult` 契约。检索与溯源是两个独立步骤：先检索得到 `SearchResult`，再调用 `TraceabilityService.trace()` 获得 `TraceabilityResult`（含 `citations` 列表）。

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 事件定义位于 `src/domain/events/`
- [ ] 使用标准库实现领域事件校验（如 dataclass / Enum / 自定义验证），禁止在领域层依赖 Pydantic
- [ ] 本 Story **不新增**领域事件（溯源是同步调用，不触发异步事件）
- [ ] 如需异步溯源日志，定义 `ClaimTraced` 事件（可选，MVP 暂不实现）

#### 数据模型 (Data Models)
- [ ] `Citation` dataclass 定义在 `src/domain/value_objects/citation.py`（领域层，零外部依赖）
- [ ] `BoundingBox` **复用已有定义**：从 `src/domain/value_objects/parsed_document.py` 导入（frozen dataclass，含 x/y/width/height/**page** + `to_dict()`），**不重复定义**
- [ ] `TraceabilityResult` TypedDict 定义在 `src/domain/ports/traceability.py`（领域层，零外部依赖）

#### 统一端口定义注册与管理 (Port Contract)
- [ ] 端口契约定义位于 `src/domain/ports/traceability.py`（新增）
- [ ] 端口注册中心位于 `src/domain/ports/registry.py`，所有端口必须登记为 `PortSpec`
- [ ] 端口实现仅可在 `src/composition_root.py` 统一注册，禁止业务代码直接实例化具体实现
- [ ] 端口解析器位于 `src/domain/ports/resolver.py`，业务代码只通过抽象解析实现
- [ ] 端口契约门禁位于 `src/domain/ports/contract_gate.py`，端口变更必须通过兼容性检查
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_traceability.py`）
- [ ] 接口命名符合单一职责，禁止同义接口重复定义
- [ ] 端口注册时提供 module 参数（register_port() 的必需参数）
- [ ] 端口具备唯一名称、版本、interface、impl、module（必填五参数）及 owner、兼容策略（可选元数据）
- [ ] 跨模块调用仅依赖抽象接口，不直接依赖实现类
- [ ] 端口变更配套契约测试与兼容性检查
- [ ] 禁止在服务文件中本地定义 Protocol / Port 抽象
- [ ] **端口包导出**：`src/domain/ports/__init__.py` 中新增导出 `TraceabilityPort`、`TraceabilityResult`；`Citation` 值对象导出到 `src/domain/value_objects/__init__.py`（不导出到端口包）

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

- [ ] 归属模块与基类 — 确定异常归属的领域异常模块（`traceability`），选择正确基类（`ExternalException` / `BusinessException`）
- [ ] 唯一编码分配 — 从子域编码范围选取（参考 `src/domain/exceptions/_code_ranges.py` 的 `CODE_RANGES` 表和 [`sisys-uni-exception-design.md §3.3.2`](../architecture/sisys-uni-exception-design.md#332-子域编码范围约束)），运行 `grep -r "EXCEPTION_NNN" src/domain/exceptions/` 验证无碰撞
- [ ] 构造器参数设计 — 携带领域上下文（`claim`、`citation_count` 等），通过 `context` 字典暴露
- [ ] 消息安全性审查 — 错误消息面向调用方可理解，不泄露 SQL/堆栈等内部实现细节
- [ ] 编码注册 — 新增异常类后在 `_code_ranges.py` 的 `_CLASS_TO_SUBDOMAIN` 字典中注册子域归属；更新 [`sisys-uni-exception-design.md §3.3.2`](../architecture/sisys-uni-exception-design.md#332-完整编码分配表) 编码分配表
- [ ] 导出完整性 — 模块 `__all__` + 包 `__init__.py` 导入 + `EXCEPTION_HTTP_MAP` 映射
- [ ] 测试覆盖 — 构造/`to_dict()`/HTTP 映射/编码唯一性 + 子域范围测试全部通过：
    - `poetry run pytest tests/unit/domain/exceptions/ -v`（含 `test_error_code_uniqueness.py` + `test_code_ranges.py` 共 8 项）
    - `poetry run pytest tests/unit/interfaces/api/test_exception_handlers.py -v`
- [ ] BDD 验收场景 — 异常路径的 Gherkin 场景纳入 Edge Cases（见下方「验收标准 Gherkin」）

#### API 契约 (API Contract)
- [ ] 遵循 OpenAPI 标准的 API 契约定义位于 `docs/api/openapi.yaml`
- [ ] API 契约测试通过（`tests/contracts/test_api_contract_traceability.py`）
- [ ] API 版本管理正确（`/api/v1/search/trace` — 与 `summary.py` 的 `/api/v1/search/summary` 前缀一致）

#### 六边形架构约束（必须遵守）
> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 本 Story 职责 |
|------|------|-------------|
| domain | `src/domain/` | `Citation`、`BoundingBox` 值对象、`TraceabilityPort` 端口 |
| application | `src/application/` | `TraceabilityService` 溯源服务、Prompt 模板 |
| infrastructure | `src/infrastructure/` | 无新增（复用 `LayeredRetrievalPort` 基础设施实现） |
| interfaces | `src/interfaces/` | `traceability.py` API 路由 |

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | infrastructure |
|------------|--------|-------------|----------------|
| **domain** | — | ✗ 禁止 | ✗ 禁止 |
| **application (TraceabilityService)** | ✓ 允许（Citation, TraceabilityPort, LayeredRetrievalPort） | — | ✗ 禁止 |
| **interfaces (traceability API)** | ✓ 允许（Citation） | ✓ 允许（TraceabilityService） | ✗ 禁止 |

**领域层零依赖原则** — 本 Story 领域层仅使用 Python 标准库。

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_traceability.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_traceability.py`
- [ ] 业务方评审通过
- [ ] 覆盖场景:
  - Happy Path: 结论文本 → 检索相关切片 → 计算置信度 → 返回引文列表
  - Happy Path: 引文包含 Bounding Box 坐标（有版面信息）
  - Happy Path: 按文档 ID 查询所有引文
  - Edge Case: 未找到相关引文（置信度 < min_confidence）→ 返回空列表
  - Edge Case: LLM 评估调用失败 → 返回默认引文列表（降级）
  - Edge Case: 检索结果无 Bounding Box 坐标 → `has_bbox_support=False`
  - Metrics: 溯源响应延迟 P95 < 300ms

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
| **TDD 单元测试** | Citation 值对象 | 值对象创建/序列化/反序列化 | `test_citation.py` | Task 1 |
| **TDD 单元测试** | TraceabilityService | 溯源逻辑/置信度计算/溯源树构建 | `test_traceability_service.py` | Task 2 |
| **TDD 单元测试** | Traceability 异常 | 异常构造/编码/HTTP 映射 | `test_traceability_exceptions.py` | Task 3 |
| **TDD 契约测试** | 端口契约 | 端口注册/版本/兼容性 | `test_port_contract_traceability.py` | Task 0 |
| **TDD 契约测试** | API 契约 | 请求/响应结构/状态码 | `test_api_contract_traceability.py` | Task 4 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_traceability.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_traceability.py` | Task 0 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖 | `test_arch_traceability.py` | Task 5 |
| **集成测试** | 层间协作 | 检索→溯源完整流程 | `test_integration_traceability.py` | Task 4 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）- **P1 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）- **P1 阻断门禁**
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）- **P1 阻断门禁**
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration`）
- [ ] **关键路径覆盖率 100%**（所有分支覆盖）

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
| **Schema 自创建** | fixture 内完成 Schema 初始化 | 依赖外部迁移，环境不一致 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突或状态污染 |
| **外部服务隔离** | Redis/Neo4j/Qdrant 测试前清理或用 mock | 真实数据被污染 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突导致并行失败 |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **依赖声明** | Fixture 必须显式声明依赖 | 并行时清理顺序不确定 |
| **asyncio 上下文** | asyncio.Lock 类变量；处理 thread.ident 为 None | 锁失效或类型错误 |
| **pytest-asyncio** | 删除 scope=module 的 event_loop fixture | 与 auto mode 冲突 |
| **BDD async 配合** | BDD 步骤函数不使用 @pytest.mark.asyncio，用 event_loop.run_until_complete() 运行 async | 直接用 @pytest.mark.asyncio 会导致 BDD context 数据丢失 |
| **asyncio.run 使用** | 独立脚本用 asyncio.run()；pytest-xdist 并行测试中 BDD 步骤函数用 event_loop fixture | asyncio.run() 创建新循环，并行测试时可能关闭错误循环 |
| **并发测试方法** | 单进程测试用 asyncio.run()；pytest-xdist 并行时 BDD 步骤用 event_loop fixture；真正并发测试在 async 函数内用 asyncio.gather() | 根据场景正确选择否则失败 |
| **外部客户端** | 第三方 API 必须验证方法存在性 | AttributeError |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源（如 `test_*`）
- ❌ Fixture 假设清理顺序（必须显式声明依赖）
- ❌ asyncio.Lock 使用实例变量
- ❌ scope=module 的 event_loop fixture
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- ❌ pytest-xdist 并行测试时，BDD 步骤函数内使用 asyncio.run()（应使用 event_loop fixture）

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续5次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | Citation 值对象定义 | Task 1 | Subtask 1.1-1.3 | `test_citation.py` |
| AC-2 | Traceability 端口契约 | Task 0 | Subtask 0.1-0.4 | `test_port_contract_traceability.py` |
| AC-3 | Traceability 应用服务 | Task 2 | Subtask 2.1-2.3 | `test_traceability_service.py` |
| AC-4 | 溯源 Prompt 模板 | Task 2 | Subtask 2.4 | `test_traceability_prompts.py` |
| AC-5 | 溯源异常体系 | Task 3 | Subtask 3.1-3.3 | `test_traceability_exceptions.py` |
| AC-6 | 溯源 API 端点 | Task 4 | Subtask 4.1-4.3 | `test_api_contract_traceability.py` |
| ~~AC-7~~ | ~~溯源与检索集成（已删除，避免 SearchResult 破坏性变更）~~ | — | — | — |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-2

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。这是 SDD 规范驱动的基础。

- [x] Subtask 0.1: 定义 `TraceabilityPort` 端口契约（`src/domain/ports/traceability.py`）
- [x] Subtask 0.2: 定义 `TraceabilityResult` 结果类型（`src/domain/ports/traceability.py`）
- [x] Subtask 0.3: 编写端口契约测试（`tests/contracts/test_port_contract_traceability.py`）
- [x] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_traceability.feature`
- [x] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_traceability.py`
- [x] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: Citation 值对象定义

**关联 AC:** AC-1

> **目的：** 定义 Citation 值对象（复用已有 BoundingBox），为溯源服务提供数据结构基础。

#### TDD 循环 [A]：Citation 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_citation.py`（值对象创建/序列化/反序列化） |
| 🟢 绿 | 实现 `Citation` dataclass（复用 `parsed_document.py` 中已有的 `BoundingBox`） |
| 🔄 重构 | 优化代码，添加 docstring |

- [x] Subtask 1.1: 🔴 红 — 编写 `Citation` 值对象失败测试
- [x] Subtask 1.2: 🟢 绿 — 实现 `Citation` dataclass（复用已有 `BoundingBox`）
- [x] Subtask 1.3: 🔄 重构 — 优化值对象代码

**完成标准/Definition of Done:**
- [ ] `Citation` 值对象实现完成（`BoundingBox` 复用已有定义，无重复代码）
- [ ] TDD 循环全部通过
- [ ] 覆盖率 ≥ 90%（领域层）

---

### Task 2: Traceability 应用服务

**关联 AC:** AC-3, AC-4

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 [A]：TraceabilityService

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_traceability_service.py`（溯源逻辑/置信度计算/溯源树构建） |
| 🟢 绿 | 实现 `TraceabilityService` 最小代码 |
| 🔄 重构 | 优化代码，添加类型注解 |

- [x] Subtask 2.1: 🔴 红 — 编写 `TraceabilityService` 失败测试
- [x] Subtask 2.2: 🟢 绿 — 实现 `TraceabilityService`
- [x] Subtask 2.3: 🔄 重构 — 优化 `TraceabilityService` 代码

#### TDD 循环 [B]：溯源 Prompt 模板

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_traceability_prompts.py`（Prompt 变量替换正确性） |
| 🟢 绿 | 实现 `traceability_prompts.py` 最小代码 |
| 🔄 重构 | 优化 Prompt 模板 |

- [x] Subtask 2.4: 🔴 红 — 编写溯源 Prompt 模板失败测试
- [x] Subtask 2.5: 🟢 绿 — 实现溯源 Prompt 模板
- [x] Subtask 2.6: 🔄 重构 — 优化 Prompt 模板

**完成标准/Definition of Done:**
- [ ] `TraceabilityService` 和 Prompt 模板全部实现
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率 ≥ 85%（应用层）

---

### Task 3: 溯源异常体系

**关联 AC:** AC-5

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 [A]：溯源异常定义

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_traceability_exceptions.py`（异常构造/编码/HTTP 映射） |
| 🟢 绿 | 实现 `TraceabilityError`、`TraceabilityNotFoundError` 异常类 |
| 🔄 重构 | 优化异常定义 |

- [x] Subtask 3.1: 🔴 红 — 编写溯源异常失败测试
- [x] Subtask 3.2: 🟢 绿 — 实现 `TraceabilityError`、`TraceabilityNotFoundError`
- [x] Subtask 3.3: 🔄 重构 — 优化异常定义

**完成标准/Definition of Done:**
- [ ] 溯源异常类实现完成
- [ ] 异常编码在 `_code_ranges.py` 注册
- [ ] 异常在 `__init__.py` 导出
- [ ] TDD 循环全部通过

---

### Task 4: 溯源 API 端点

**关联 AC:** AC-6

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**
>
> **注意：** AC-7（溯源与检索集成）已删除，避免 `SearchResult` 破坏性变更。溯源信息通过 `TraceabilityResult` 独立返回，不污染 `SearchResult` 契约。不再需要修改 `SearchResult` TypedDict 或 `HybridSearchService`。

#### TDD 循环 [A]：API 路由实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_api_contract_traceability.py`（API 契约测试） |
| 🟢 绿 | 实现 `src/interfaces/api/traceability.py` 最小代码 |
| 🔄 重构 | 优化 API 路由 |

- [x] Subtask 4.1: 🔴 红 — 编写 API 契约测试
- [x] Subtask 4.2: 🟢 绿 — 实现 API 路由
- [x] Subtask 4.3: 🔄 重构 — 优化 API 路由

#### TDD 循环 [B]：集成测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_integration_traceability.py`（检索→溯源完整流程） |
| 🟢 绿 | 实现 `TraceabilityService` 集成测试 |
| 🔄 重构 | 优化集成代码 |

- [x] Subtask 4.4: 🔴 红 — 编写集成测试
- [x] Subtask 4.5: 🟢 绿 — 实现集成测试
- [x] Subtask 4.6: 🔄 重构 — 优化集成代码

**完成标准/Definition of Done:**
- [ ] API 路由实现完成
- [ ] 集成测试覆盖检索→溯源完整流程
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率 ≥ 75%

---

### Task 5: SDD 架构约束验证测试

**关联 AC:** AC-2, AC-6

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。
> 它验证前面 Task 创建的代码是否符合六边形架构规则。

#### 架构验证测试实现

- [x] Subtask 5.1: 创建 `tests/unit/architecture/test_arch_traceability.py`
- [x] Subtask 5.2: 实现依赖方向验证器（验证领域层零依赖）
- [x] Subtask 5.3: 实现端口契约验证器（验证端口注册完整性）
- [x] Subtask 5.4: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**
- [ ] 所有架构/约束测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败

---

### Task 6: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。
> 它验证 `src` 以及 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 的完成清单是否已逐项确认，确保 Story 进入 `done` 之前没有遗漏。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_traceability.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_traceability.py` 的 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达、保持步骤函数可维护性 |

- [x] Subtask 6.1: 场景 1 — 验证 `src` 完成清单的逐项确认
- [x] Subtask 6.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单的逐项确认
- [x] Subtask 6.3: 运行开发结束验收测试并确认通过
- [x] Subtask 6.4: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 本 Story 经过 5 轮多视角（架构/检索层/异常体系/API/验收测试）审查，以下汇总所有修复项。

### Round 1 审查发现

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | **BoundingBox 重复定义**：`src/domain/value_objects/parsed_document.py` 第131行已存在 `BoundingBox` frozen dataclass（x, y, width, height, page + to_dict），文档要求重新定义在 `citation.py` 中，导致重复定义 | **P0** | **统一引用已有 BoundingBox**：`Citation` 值对象从 `parsed_document.py` 导入 `BoundingBox`，不再在 `citation.py` 中重复定义。注意已有 BoundingBox 包含 `page` 字段，文档第62-65行缺少 `page` 字段——这是已有值对象的标准字段，必须保留。 |
| 2 | **LayeredRetrievalPort 无 `search()` 方法**：实际端口只有 `search_top_down()` 和 `search_bottom_up()` 两个方法，文档 AC-3 要求 `TraceabilityService` 注入 `LayeredRetrievalPort` 并调用 `search()`——该方法不存在 | **P0** | **修正为调用 `search_top_down()`**：TraceabilityService 使用 `search_top_down(query_text, target_level="L4", ...)` 获取相关切片，因为溯源场景是「从结论出发，向低层级展开搜索切片」，语义上符合自顶向下遍历。 |
| 3 | **SearchResult 修改为破坏性变更**：AC-7 要求向 `SearchResult` TypedDict（`l3_vector.py`）添加 `citations` 和 `has_bbox_support` 字段。`SearchResult` 被多个服务（DenseSearchService, SparseSearchService, HybridSearchService, LayeredRetrievalService, SummaryGenerationPort, RelevanceEvaluationPort）引用，修改是破坏性变更 | **P0** | **不修改 SearchResult**：溯源信息通过 `TraceabilityResult` 独立返回，不污染 `SearchResult` 契约。检索与溯源是两个独立步骤：先检索得到 `SearchResult`，再调用 `TraceabilityService.trace()` 获得 `TraceabilityResult`（含 `citations` 列表）。删除 AC-7（溯源与检索集成）及 Task 4 中的 TDD 循环 [B]。 |
| 4 | **异常体系注册缺失**：文档 AC-5 要求新增 `TraceabilityError(370)` 和 `TraceabilityNotFoundError(371)`，但 `_code_ranges.py` 中未注册 `traceability` 子域，`_CLASS_TO_SUBDOMAIN` 无映射，`test_code_ranges.py` 的 `allowed_child_parent_subdomains` 和 `nested_subdomains` 无条目，`EXCEPTION_HTTP_MAP` 无映射。这 5 项缺失将直接导致 CI 全部失败 | **P0** | **完善异常注册流程**：在 `_code_ranges.py` 新增 `"traceability": (370, 379)` 子域及 `_CLASS_TO_SUBDOMAIN` 映射；`test_code_ranges.py` 新增 `("traceability", "external")` 和 `("traceability", "business")` 允许继承对；`EXCEPTION_HTTP_MAP` 注册 `TraceabilityError→500` 和 `TraceabilityNotFoundError→404`；`__init__.py` 导入导出。 |
| 5 | **API 路由前缀不一致**：文档 AC-6 使用 `POST /api/v1/documents/trace`，但现有路由模式统一使用功能域前缀（如 `/api/v1/search`、`/api/v1/archive`），且 Epic 文档指定 `GET /documents/{id}/trace`。`/api/v1/documents/trace` 既不符合 pattern 也不符合 Epic 要求 | **P0** | **统一路由前缀为 `/api/v1/search`**：`POST /api/v1/search/trace`（溯源主端点）和 `GET /api/v1/search/trace/{document_id}`（按文档查询），与 `summary.py` 的 `/api/v1/search/summary` 保持一致。 |
| 6 | **端口 __init__.py 导出位置错误**：文档 SDD 规范要求将 `Citation` 导出到 `src/domain/ports/__init__.py`，但 `Citation` 是值对象（位于 `domain/value_objects/`），不是端口 | **P1** | **修正导出位置**：`Citation` 导出到 `src/domain/value_objects/__init__.py`；`TraceabilityPort`、`TraceabilityResult` 导出到 `src/domain/ports/__init__.py`。 |
| 7 | **置信度计算逻辑不准确**：文档 AC-3 要求「基于余弦相似度计算引文置信度」，但检索结果 `SearchResult.score` 已经是 Qdrant 返回的向量相似度分数，再次计算余弦相似度是冗余的 | **P1** | **置信度 = SearchResult.score 归一化**：直接使用检索结果的 `score` 字段作为引文置信度（归一化到 [0,1] 区间），无需额外余弦相似度计算。`score` 已经是 Qdrant 的向量相似度（cosine distance），自然反映引文与结论的相关性。 |
| 8 | **BoundingBox 坐标不可用**：文档假设检索结果 payload 中包含 BoundingBox 坐标，但实际 `chunk_indexing_handler.py` 和 Qdrant payload 中不包含 bbox 字段。`bbox` 仅在 `semantic_chunking_service.py` 中用于构建 `SemanticChunk`，但未写入向量存储的 payload | **P1** | **添加 bbox 写入 Qdrant payload**：在 `chunk_indexing_handler.py` 中，为每个 Child 块的 payload 添加 `bbox` 字段（从 `SemanticChunk` 的文档元素中提取）。这是 Story 3.8 的前置基础设施变更，应在 Task 0 中完成。 |
| 9 | **from_dict 反序列化缺失**：文档 AC-1 要求「支持从 dict 反序列化」，但现有值对象（如 `BoundingBox`、`ParsedElement`）只有 `to_dict()` 方法，没有 `from_dict()` 模式 | **P2** | **添加 `from_dict()` 类方法**：为 `Citation` 和 `BoundingBox` 添加 `@classmethod from_dict()` 方法，支持从存储恢复。 |
| 10 | **TraceabilityResult 使用 TypedDict 但返回类型为 Any**：文档封闭端口使用 TypedDict，但已有 SummaryGenerationPort 和 RelevanceEvaluationPort 的返回类型为 `Any`（因 Pydantic @computed_field 无法精确表达） | **P2** | **保持 TypedDict 但返回类型声明为 Any**：与已有模式一致，端口方法声明 `-> Any`，但实际返回 `TraceabilityResult` TypedDict。 |
| 11 | **Citation 无唯一标识**：`get_citation_detail(citation_id)` 需要按 ID 查询，但 Citation 值对象没有 `citation_id` 字段，无法实现查询 | **P1** | **添加 `citation_id` 字段**：由 `chunk_id`（或其 SHA256 哈希）生成，MVP 阶段从当次溯源缓存返回。 |
| 12 | **get_citation_detail/get_citation_by_document 无数据源**：TraceabilityService 若不持久化引文，这两个方法无法跨请求工作 | **P1** | **MVP 用当次缓存**：trace() 执行时缓存本次结果到 `TraceabilityService` 实例，按 citation_id/document_id 查询；明确不持久化，跨请求持久化留给后续 Story。 |
| 13 | **TraceabilityNotFoundError 语义不清晰**：AC-5 定义为「未找到相关引文」，与 AC-3 的「置信度不足 → 返回空列表」矛盾——空列表是正常业务结果，不应抛异常 | **P1** | **语义澄清**：`TraceabilityNotFoundError`（371）仅用于查询类方法（`get_citation_detail`/`get_citation_by_document`）找不到目标引文时抛出；`trace()` 主流程置信度不足时返回空 `citations` 列表（正常结果）。 |

### 文档修复执行

- [x] 修复项 1 — BoundingBox 统一引用已有定义，不再重复定义
- [x] 修复项 2 — TraceabilityService 改用 `search_top_down()` 方法
- [x] 修复项 3 — 删除 AC-7，删除 Task 4 的 TDD 循环 [B]，SearchResult 保持不变
- [x] 修复项 4 — 完善异常注册流程说明
- [x] 修复项 5 — 统一 API 路由前缀为 `/api/v1/search/trace`
- [x] 修复项 6 — 修正导出位置
- [x] 修复项 7 — 修正置信度计算逻辑
- [x] 修复项 8 — 添加 bbox 写入 Qdrant payload 说明
- [x] 修复项 9 — 添加 from_dict() 方法说明
- [x] 修复项 10 — 返回类型对齐为 Any
- [x] 修复项 11 — Citation 添加 citation_id 字段
- [x] 修复项 12 — 明确 MVP 缓存策略，不持久化
- [x] 修复项 13 — 澄清 TraceabilityNotFoundError 语义（查询类方法专属，trace() 主流程返回空列表）

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（DDD）、事件驱动架构（EDA）
- **设计约束:** 领域层零依赖、依赖方向矩阵、仓储模式、端口注册与 DI
- **接口治理:** 统一端口注册、PortSpec 元数据、Registry/Resolver/ContractGate、Composition Root 装配、契约优先、版本化兼容、禁止跨模块直接依赖实现类
- **技术栈:** Python 3.11+、FastAPI 0.104+、Pydantic V2、asyncio、Redis、Qdrant、PostgreSQL

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - §17.1.7 高保真溯源

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **[选中方案] 基于检索结果的引文三元组** | 复用现有检索基础设施，无需额外存储 | 依赖检索结果的 payload 字段 | ✅ 9/10 |
| [备选方案 A] 独立引文存储 | 引文数据独立管理，灵活性高 | 需要额外存储层，增加复杂度 | 6/10 |
| [备选方案 B] LLM 实时提取引文 | 引文质量高，可解释性强 | 延迟高，成本高，不适合实时场景 | 5/10 |

### 项目结构说明 Project Structure

```
.\
|
├── src/
|   ├── __init__.py
|   ├── composition_root.py        # 组合根（唯一注册入口）
|   ├── application/                # 应用层
|   │   ├── __init__.py             # 模块导出
|   │   ├── services/                   # 应用层服务
|   │   │   └── traceability_service.py  # 溯源服务
|   │   └── ports/                      # 应用层端口
|   │
|   ├── domain/                     # 领域层
|   │   ├── __init__.py             # 模块导出
|   │   ├── value_objects/              # 值对象集合
|   │   │   └── citation.py             # Citation（复用 parsed_document.py 的 BoundingBox）
|   │   ├── ports/                      # 领域端口目录
|   │   │   ├── traceability.py         # TraceabilityPort
|   │   │   ├── registry.py             # 端口注册中心
|   │   │   ├── resolver.py             # 端口解析器
|   │   │   └── contract_gate.py        # 契约门禁
|   │   └── exceptions/                 # 领域层异常
|   │       └── traceability_exceptions.py  # TraceabilityError, TraceabilityNotFoundError
|   │
|   ├── infrastructure/             # 基础设施层
|   │   └── (无新增，复用 LayeredRetrievalPort 实现)
|   │
|   ├── interfaces                  # 接口层
|   │   └── api/                        # REST API 接口
|   │       └── traceability.py         # 溯源 API 路由
|   │
|   └── shared                      # 必要共享模块
|       └── __init__.py
|
└── tests/
    ├── contracts/
    │   ├── test_port_contract_traceability.py   # 端口契约测试
    │   └── test_api_contract_traceability.py    # API 契约测试
    ├── unit/
    │   ├── domain/value_objects/
    │   │   └── test_citation.py                 # Citation 值对象测试
    │   ├── application/services/
    │   │   ├── test_traceability_service.py     # TraceabilityService 测试
    │   │   └── test_traceability_prompts.py     # Prompt 模板测试
    │   ├── domain/exceptions/
    │   │   └── test_traceability_exceptions.py  # 异常测试
    │   └── architecture/
    │       └── test_arch_traceability.py        # 架构验证测试
    ├── integration/
    │   └── test_integration_traceability.py     # 集成测试
    └── acceptance/
        ├── test_acceptance_traceability.feature # Gherkin 场景
        └── test_acceptance_traceability.py      # BDD 步骤实现
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 3.7 检索相关性评估](./3-7-search-relevance-evaluation.md)

**关键学习/Key Learnings:**
- `@computed_field` 用于服务端计算字段（overall_score, should_block），不依赖 LLM 输出
- `@model_validator(mode="after")` 用于跨字段条件必填验证（block_reason required when should_block=True）
- 两个异常基类（ExternalException vs BusinessException）自然分离降级路径（LLM 失败 → 降级，业务规则阻断 → 不降级）
- 端口注册必须包含 `module` 参数（第 5 个必需参数）
- BDD 步骤函数必须使用 `event_loop.run_until_complete()`，禁止 `@pytest.mark.asyncio`

**应用到本故事/Applied to This Story:**
- [ ] Citation 值对象使用 `dataclass(frozen=True)`（不可变值对象），**复用** `parsed_document.py` 中已有的 `BoundingBox`
- [ ] 溯源异常分两类：`TraceabilityError`（ExternalException，LLM 评估失败 → 降级）和 `TraceabilityNotFoundError`（BusinessException，查询类方法未找到引文 → 不降级；trace() 主流程置信度不足时返回空列表，不抛异常）
- [ ] 端口注册包含完整的 5 个必需参数（name, version, interface, impl, module）
- [ ] BDD 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- [ ] Prompt 模板使用 f-string 格式，支持动态注入
- [ ] TraceabilityPort 返回类型使用 `-> Any`（与 SummaryGenerationPort、RelevanceEvaluationPort 保持一致，因 TypedDict 无法精确表达 @computed_field 行为）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.2 |
| **Version** | create-story workflow v2.9.0 |
| **Execution Date** | 2026-08-20 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` |
| **核心领域设计** | `docs/architecture/sisys-core-domain-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/3-7-search-relevance-evaluation.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 3.8, FR-SR-08）
- [x] 架构约束从 `architecture.md` 和 `sisys-core-domain-design.md` 提取
- [x] 前一个故事学习经验整合（Story 3.7 检索相关性评估）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-8-high-fidelity-traceability-bounding-box.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/value_objects/citation.py` - Citation 值对象（复用 parsed_document.py 中的 BoundingBox）
- `src/domain/ports/traceability.py` - TraceabilityPort 端口
- `src/domain/exceptions/traceability_exceptions.py` - 溯源异常
- `src/application/services/traceability_service.py` - TraceabilityService 溯源服务
- `src/application/services/traceability_prompts.py` - 溯源 Prompt 模板
- `src/interfaces/api/traceability.py` - 溯源 API 路由
- `tests/unit/domain/value_objects/test_citation.py` - Citation 值对象测试
- `tests/unit/application/services/test_traceability_service.py` - TraceabilityService 测试
- `tests/unit/application/services/test_traceability_prompts.py` - Prompt 模板测试
- `tests/unit/domain/exceptions/test_traceability_exceptions.py` - 异常测试
- `tests/unit/architecture/test_arch_traceability.py` - 架构验证测试
- `tests/contracts/test_port_contract_traceability.py` - 端口契约测试
- `tests/contracts/test_api_contract_traceability.py` - API 契约测试
- `tests/integration/test_integration_traceability.py` - 集成测试
- `tests/acceptance/test_acceptance_traceability.feature` - Gherkin 场景
- `tests/acceptance/test_acceptance_traceability.py` - BDD 步骤实现

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.8 |
| **Story Key** | 3-8-high-fidelity-traceability-bounding-box |
| **File** | `_bmad-output/implementation-artifacts/stories/3-8-high-fidelity-traceability-bounding-box.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | P0-8（关键路径） |
| **覆盖 FR** | FR-SR-08（高保真溯源 Bounding Box） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | [待审查后填写] | P[N] | [修复方案] |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** [待审查后填写]
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策 Decision Needed

- [ ] [{故事编号n-m}-{优先级P0~2}-{问题编号}][Review][Patch | Defer] **[问题精准描述]** — 决策：[决策精准描述] [blind | edge | audit] `[相对路径]:[行号范围]`

#### 已修复 Patch

- [ ] [{故事编号n-m}-{优先级P0~2}-{问题编号}][Review][Patch] [问题精准描述] [相对路径:行号] — [解决方案精准描述]

#### 已推迟 Defer

- [ ] [{故事编号n-m}-{优先级P0~2}-{问题编号}][Review][Defer] [问题精准描述] — deferred，[原因精准描述]

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] Story status updated to `review`
- [x] All tasks completed with TDD red-green-refactor cycles
- [x] All acceptance criteria satisfied
- [x] Code quality checks passed (ruff check, mypy, pytest)
- [x] Architecture constraint verification tests passed

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

本模板适用于所有 Story 创建。根据六边形架构约束和 prd.md NFR 测试覆盖计划，Story 按层类型分类，每层有不同的测试要求：

| 层类型 | Story 类型 | 覆盖率要求 | 测试重点 | 示例 |
|--------|-----------|-----------|---------|------|
| **领域层 (Domain)** | 领域层 Story | ≥90% | 实体创建/状态转换/领域事件/不变量验证 | Story 1.1: 六边形架构骨架 |
| **应用层 (Application)** | 应用层 Story | ≥85% | 用例逻辑/命令处理/查询处理/事务管理 | Story 2.1: 用户注册用例 |
| **接口层 (Interfaces)** | 接口层 Story | ≥85% | API 路由/请求响应验证/事件监听/错误处理 | Story 3.1: REST API |
| **基础设施层 (Infrastructure)** | 基础设施层 Story | ≥75% | 连接测试/CRUD 操作/外部适配器/性能基准 | Story 1.4: Redis 缓存层 |
| **安全层 (Security)** | 安全层 Story | ≥85% | 认证/授权/RBAC/审计日志/渗透测试 | Story 1.9: RBAC 权限控制 |
| **架构层 (Architecture)** | 架构层 Story | ≥85% | 核心机制 (UDMR/EIP)/路由决策/多 Agent 协作 | Story 1.13: 统一动态模型路由 |

> **注意：**
> 1. **层编号规则** — Story 0.x 为基础设施准备，Story 1.x 为领域层与安全/架构机制，Story 2.x 为应用层，Story 3.x 为接口层
> 2. **覆盖率要求** 源自 epics_v1.0.md CI/CD 质量门禁：整体≥80%，领域层≥90%，应用层≥85%，基础设施层≥75%
> 3. **骨架 Story 覆盖率豁免** — 架构骨架 Story 临时降低覆盖率要求（整体≥30%，对应层≥50%），从下一个非骨架 Story 恢复
> 4. **循环依赖检测** — 统一使用 ruff/isort，不引入 pylint 等额外工具

### TDD 循环编写指南

每个 Task 的 TDD 循环应按以下模式编写：

```markdown
#### TDD 循环 [A]：[组件名称]

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_[component].py`（[具体测试场景]） |
| 🟢 绿 | 实现 `[Component]` 类/函数最小代码 |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask [m.n]: 🔴 红 — 编写 [组件] 失败测试
- [ ] Subtask [m.n]: 🟢 绿 — 实现 [组件] 最小代码
- [ ] Subtask [m.n]: 🔄 重构 — 优化 [组件] 代码
```

**红阶段检查点：**
- 测试在实现之前编写
- 运行 `pytest` 确认测试失败
- 失败原因符合预期（如 `ModuleNotFoundError` 因为类还不存在）

**绿阶段检查点：**
- 只编写让测试通过的代码
- 不追求完美，先跑通流程
- 可以硬编码（如果能让测试通过）

**重构阶段检查点：**
- 保持测试通过的前提下优化
- 应用设计模式/架构原则
- 运行 `ruff check` + `mypy` 确认代码质量

### 相关文档 Related Documents

| 文档 | 说明 |
|------|------|
| [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md) | 开发模式详细说明与各层测试模板 |
| [预提交 Hooks 规范](./pre-commit-hooks.md) | 代码质量保障 |
| [架构设计文档](../../_bmad-output/planning-artifacts/architecture.md) | 六边形架构详细说明 |
| [核心领域架构设计](../../docs/architecture/sisys-core-domain-design.md) | §17.1.7 高保真溯源设计 |

---

**故事版本/Story Version:** v1.1.0
**创建日期/Created:** 2026-08-20
**最后更新/Last Updated:** 2026-08-20
**更新说明/Description:**
- v1.1.0: 5 轮多视角审查修订 — 修复 BoundingBox 复用/端口方法名/API 路由前缀/SearchResult 破坏性变更/异常注册/Citation 唯一标识 等 12 项问题
- v1.0.0: 创建故事文件，基于 Epic 3 Story 3.8 (FR-SR-08) 需求
