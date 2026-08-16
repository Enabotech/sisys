# Story 3.7: 检索相关性评估（LLM-as-a-Judge）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 质量工程师,
**I want** 系统评估检索相关性（LLM-as-a-Judge 实时多维评估），相关性 < 0.6 标注"数据不足",
**So that** 防止基于不足数据生成幻觉内容，确保摘要生成质量。

### 业务价值

本 Story 是 Epic 3（智能检索与知识发现）的第七个故事（P1-7），对应 **FR-SR-07**（检索相关性评估，P0）。它填补了检索流水线（Story 3.4→3.5→3.6）与生成之间的质量守卫空白，在检索结果被传递给摘要生成（Story 3.6）之前，执行 LLM-as-a-Judge 多维评估（相关性、完整性、时效性），当综合评分 < 0.6 时拦截生成并标注"数据不足"，防止幻觉内容。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **LLM-as-a-Judge 多维评估** | 实时评估检索结果质量 | 相关性/完整性/时效性三维评分，综合分 < 0.6 阻断 |
| **检索质量守卫** | 防止基于不足数据生成幻觉 | 阻断准确率 100% |
| **规则预检** | 快速过滤明显不足结果 | 规则预检 P95 < 100ms |
| **评估结果可追溯** | 质量评估过程可审计 | 评估结果携带各维度分数与 LLM 判断理由 |

**来源:** [`epics_v1.0.md`](../../planning-artifacts/epics_v1.0.md) - Epic 3 Story 3.7，第 1529-1568 行

**前置依赖（已就绪）:**
- Story 3.2a（LLM Client 基础设施 ✅ done）— 提供 `LLMClientPort.structured_generate()` 方法，支持 Pydantic Schema 驱动的结构化输出，用于 LLM-as-a-Judge 评估
- Story 3.6（契约化摘要生成 ✅ review）— 提供 `SummaryGenerationPort`、`SummaryGenerationService`，本 Story 为其提供检索质量守卫
- Story 3.4（RRF 融合排序 ✅ done）— 提供 `HybridSearchService` 三路检索编排，评估对象为混合检索结果
- Story 3.5（分层检索 L1-L4 ✅ review）— 提供 `LayeredRetrievalPort`，评估对象为分层检索结果
- Story 3.1a（Dense 语义检索 ✅ done）— 提供 `SearchResult` 统一检索结果类型

**后续依赖:** Story 3.8（高保真溯源）、Story 3.11（事实有效期标签管理）、Story 3.12（数据陈旧标记）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: LLM-as-a-Judge 多维评估 Schema 定义

**Given** 系统需要评估检索结果质量
**When** 定义多维评估 Schema
**Then** 定义三个评估维度（相关性/完整性/时效性）的结构化 Schema
**And** 每个维度包含 `score`（0-1 浮点数）和 `reason`（判断理由）
**And** 返回综合评分 `overall_score` 和阻断标记 `should_block`

**验证标准/Validation Criteria:**
- [ ] `RelevanceEvaluation` Pydantic BaseModel 定义在 `src/application/services/relevance_schemas.py`（应用层可依赖 Pydantic）
  - `context_relevance: float` — 上下文相关性评分（0-1，`Field(ge=0.0, le=1.0)`）
  - `context_relevance_reason: str` — 相关性判断理由
  - `completeness: float` — 完整性评分（0-1，`Field(ge=0.0, le=1.0)`）
  - `completeness_reason: str` — 完整性判断理由
  - `timeliness: float` — 时效性评分（0-1，`Field(ge=0.0, le=1.0)`）
  - `timeliness_reason: str` — 时效性判断理由
  - `overall_score: float` — 综合评分（0-1，`Field(ge=0.0, le=1.0)`，使用 `@computed_field` 自动计算为 `(context_relevance + completeness + timeliness) / 3.0`，服务端计算不依赖 LLM 输出，阻断守卫以此为准）
  - `should_block: bool` — 是否阻断生成（使用 `@computed_field` 自动计算为 `overall_score < 0.6`，阻断准确率 100%）
  - `block_reason: str | None` — 阻断理由（`should_block=True` 时必填，内容为"数据不足"；使用 `@model_validator(mode="after")` 实现跨字段条件必填验证）
- [ ] `RuleBasedEvaluation` Pydantic BaseModel 定义在 `src/application/services/relevance_schemas.py`
  - `has_valid_results: bool` — 检索结果是否有效（非空列表）
  - `min_score: float` — 检索结果最低分（`has_valid_results=False` 时归一化为 0.0）
  - `max_score: float` — 检索结果最高分（`has_valid_results=False` 时归一化为 0.0）
  - `avg_score: float` — 检索结果平均分（`has_valid_results=False` 时归一化为 0.0）
  - `result_count: int` — 检索结果数量（`has_valid_results=False` 时为 0）
  - `quick_block: bool` — 快速阻断标记（结果为空或平均分 < 0.3 时阻断）
  - （实现顺序：**先判空再取 min/max/avg**，空列表不进入统计计算，避免 `min([])` 抛 `ValueError`；空结果归一化：`min_score = max_score = avg_score = 0.0`，`result_count = 0`）
- [ ] Schema 验证通过率 100%（Pydantic V2 严格模式）

### AC-2: 检索相关性评估端口契约

**Given** 系统需要统一的检索质量评估抽象
**When** 定义 `RelevanceEvaluationPort` 协议
**Then** 包含 `evaluate()` 核心方法，接收检索结果，返回多维评估结果
**And** 包含 `quick_rule_check()` 规则预检方法，快速过滤明显不足结果
**And** 领域层定义零外部依赖（仅 Python 标准库 + Protocol）

**验证标准/Validation Criteria:**
- [ ] `RelevanceEvaluationPort` 定义于 `src/domain/ports/relevance_evaluation.py`（Protocol，`@runtime_checkable`）
- [ ] `SearchResult` 从 `src/domain/ports/l3_vector.py` 导入（与 `LayeredRetrievalPort` 相同的现有模式，同域内类型引用）
- [ ] 方法签名：
  - `async evaluate(query_text: str, search_results: list[SearchResult], config: LLMConfig | None = None) -> RelevanceEvaluationResult` — LLM 多维评估
    - 返回 `RelevanceEvaluationResult`（TypedDict 或 dataclass，与 `SearchResult` 风格一致）
  - `async quick_rule_check(query_text: str, search_results: list[SearchResult]) -> RuleBasedResult` — 规则预检
    - 返回 `RuleBasedResult`（TypedDict 或 dataclass）
- [ ] 结果类型定义：
  - `RelevanceEvaluationResult`（TypedDict）：
    - `context_relevance: float`（0-1）
    - `context_relevance_reason: str`
    - `completeness: float`（0-1）
    - `completeness_reason: str`
    - `timeliness: float`（0-1）
    - `timeliness_reason: str`
    - `overall_score: float`（0-1）
    - `should_block: bool`
    - `block_reason: str | None`
  - **不变式**：`should_block=True` 时 `block_reason` 必填（非 None）；`should_block=False` 时 `block_reason` 必须为 `None`（TypedDict 类型系统无法表达，由 Pydantic `RelevanceEvaluation` `@model_validator` 强制 + 端口测试断言）
  - `RuleBasedResult`（TypedDict）：
    - `has_valid_results: bool`
    - `min_score: float`（0-1，空结果时为 0.0）
    - `max_score: float`（0-1，空结果时为 0.0）
    - `avg_score: float`（0-1，空结果时为 0.0）
    - `result_count: int`（空结果时为 0）
    - `quick_block: bool`
  - **边界值约定**：`has_valid_results=False`（空列表）时，`min_score = max_score = avg_score = 0.0`，`result_count = 0`，`quick_block = True`（"无数据即为无相关性"的中性值）；**先判空再取 min/max/avg**，避免 `min([])`/`max([])` 抛 `ValueError`
- [ ] 端口注册于 `composition_root.py`，通过 `register_port()` 注册为 `relevance_evaluation_service` 端口
- [ ] 端口具备唯一名称、版本、interface、impl、module（必填五参数）及 owner、兼容策略（可选元数据）
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_relevance_evaluation.py`）

### AC-3: 检索相关性评估异常体系

**Given** 评估过程中可能发生多种错误
**When** 定义相关性评估异常类
**Then** 新增 `relevance` 子域，分配唯一异常编码
**And** 继承适当的基类层次结构

**验证标准/Validation Criteria:**
- [ ] `RelevanceEvaluationError`（EXCEPTION_360）— 继承 `ExternalException`，LLM 评估调用失败
  - 构造器参数：`query_text: str`（查询文本，截断至 100 字符）、`result_count: int`（检索结果数）、`message: str | None = None`、`cause: Exception | None = None`（遵循 `DomainError` 基类标准契约）
  - `query_text`/`result_count` 通过 `context` 字典暴露
- [ ] `RelevanceEvaluationBlockedError`（EXCEPTION_361）— 继承 `BusinessException`，检索结果不足被阻断
  - 构造器参数：`query_text: str`（查询文本，截断至 100 字符）、`overall_score: float`（综合评分）、`block_reason: str`（阻断理由，如"数据不足"）、`message: str | None = None`、`cause: Exception | None = None`
  - `query_text`/`overall_score`/`block_reason` 通过 `context` 字典暴露
- [ ] **设计理由：** `RelevanceEvaluationError`（EXCEPTION_360）继承 `ExternalException` 因为 LLM 调用属外部服务，映射 HTTP 500（与 `RerankError` 模式一致，重排序/评估失败视为服务端处理失败，避免 `isinstance` 回退到 `ExternalException` 基类 502）；`RelevanceEvaluationBlockedError`（EXCEPTION_361）继承 `BusinessException` 因为阻断属业务规则，**必须显式注册** HTTP 422 到 `EXCEPTION_HTTP_MAP`（否则会回退到 `BusinessException` 基类 400 映射）
- [ ] 异常编码在 `_code_ranges.py` 注册 `relevance` 子域（360, 369）及 `_CLASS_TO_SUBDOMAIN` 映射
- [ ] 异常在 `__init__.py` 导出，在 `EXCEPTION_HTTP_MAP` 注册
- [ ] 无编码碰撞（`grep -rw "EXCEPTION_36[0-9]" src/` 零输出）
- [ ] HTTP 映射测试覆盖

### AC-4: 检索相关性评估应用服务

**Given** 评估端口契约已定义
**When** 实现 `RelevanceEvaluationService`
**Then** 注入 `LLMClientPort` 用于 LLM-as-a-Judge 评估
**And** 先执行规则预检快速过滤，再执行 LLM 多维评估
**And** 综合评分 < 0.6 时标注"数据不足"并阻断

**验证标准/Validation Criteria:**
- [ ] `RelevanceEvaluationService` 位于 `src/application/services/relevance_evaluation_service.py`
- [ ] 构造函数注入 `llm_client: LLMClientPort`（或 `Any` 保持松耦合）
- [ ] 实现 `evaluate()` 方法：
  1. 先调用 `quick_rule_check()` 规则预检
  2. 若 `quick_block=True`，直接返回阻断结果（`should_block=True`, `block_reason="数据不足"`，各维度分数为 0.0）
  3. 否则调用 `LLMClientPort.structured_generate()` 传入评估 Prompt 和 `RelevanceEvaluation` Schema
  4. 返回 `RelevanceEvaluationResult`
  - **返回类型承诺**：`evaluate()` **永远不抛 `RelevanceEvaluationBlockedError`**，阻断信息通过 `RelevanceEvaluationResult.should_block` / `block_reason` 字段传递；`RelevanceEvaluationBlockedError` 由调用方（`SummaryGenerationService` / API 路由）检查 `should_block == True` 时抛出
  - `config` 参数直接透传给 `LLMClientPort.structured_generate()`（不重新构造 / 覆盖 `LLMConfig`）
- [ ] 实现 `quick_rule_check()` 方法：
  - 空检索结果 → `quick_block=True`
  - 检索结果平均分 < 0.3 → `quick_block=True`
  - 其他情况 → `quick_block=False`
  - **防御性计算**：计算 `avg_score` 前过滤 NaN/负值/缺失 score（score 无效时视为 0.0，使用 `math.isfinite()` + `result.get("score", 0.0)` + `max(0.0, s)`），避免 NaN 传播 (`NaN < 0.3` 返回 False) 导致阻断失效
- [ ] 规则预检延迟 P95 < 100ms（纯计算，无外部调用）
- [ ] LLM 评估延迟 P95 < 3s（含 LLM 调用）
- [ ] 评估准确率 ≥ 90%（端到端多维评估与人工标注一致率）
- [ ] 阻断准确率 100%（`overall_score < 0.6` 时必然阻断，`overall_score >= 0.6` 时必然不阻断）
- [ ] LLM 调用失败抛出 `RelevanceEvaluationError`（包装原始 LLM 异常，携带 `result_count` 和 `query_text` 上下文）
- [ ] 阻断业务规则违反由调用方（`SummaryGenerationService` 或 API 路由）基于 `RelevanceEvaluationResult.should_block` 抛出 `RelevanceEvaluationBlockedError`（携带 `overall_score` 和 `block_reason`）；`evaluate()` 本身不抛出该异常
- [ ] LLM 异常处理：捕获 `LLMAPIError` 和 `ServiceUnavailableError` → 包装为 `RelevanceEvaluationError`；`LLMResponseError` → 同样包装为 `RelevanceEvaluationError`；`LLMConfigError` → 透传不包装

### AC-5: 评估 Prompt 模板

**Given** LLM-as-a-Judge 需要结构化的评估 Prompt
**When** 定义评估 Prompt 模板
**Then** 每个维度有独立的评估标准和评分规则
**And** Prompt 模板注入查询文本和检索结果上下文

**验证标准/Validation Criteria:**
- [ ] Prompt 模板定义在 `src/application/services/relevance_prompts.py`
- [ ] System Prompt 包含：
  - 角色定义（"你是一位检索质量评估专家，负责评估检索结果的相关性、完整性和时效性"）
  - 输出格式约束（强制遵守 JSON Schema）
  - 评分标准（每个维度 0-1 分，0.6 为合格线）
  - 阻断规则（综合评分 < 0.6 应阻断；服务端以 `overall_score` 的 `@computed_field` 计算结果为准，Prompt 中的评分仅供 LLM 参考，不决定阻断行为）
- [ ] User Prompt 包含：
  - 用户查询文本
  - 检索结果列表（格式化的文档片段列表，含 score 和内容摘要）
  - 评估要求（逐条评估每个结果，给出综合评分）
- [ ] 评分标准详细说明：
  - **相关性（context_relevance）**：检索结果是否与查询语义相关。1.0 = 完全匹配查询意图，0.0 = 完全不相关。0.6+ = 可接受的相关性。
  - **完整性（completeness）**：检索结果是否覆盖查询的各个子主题。1.0 = 全部信息覆盖，0.0 = 无必要信息。0.6+ = 核心信息已覆盖。
  - **时效性（timeliness）**：检索结果是否足够新（基于 payload 中的 `updated_at` 或 `created_at` 字段，若不存在则默认 1.0）。1.0 = 最新信息，0.0 = 完全过时。
- [ ] 模板使用 Python f-string 格式，支持动态注入
- [ ] 所有 Prompt 模板通过单元测试验证（变量替换正确性）

### AC-6: 与摘要生成服务的集成

**Given** 检索相关性评估已就绪
**When** 摘要生成服务调用前执行评估
**Then** 评估结果影响摘要生成流程
**And** 综合评分 < 0.6 时阻断并返回"数据不足"响应

**验证标准/Validation Criteria:**
- [ ] `SummaryGenerationService` 注入 `relevance_evaluation_service`（可选依赖，`__init__` 参数 `relevance_evaluation_service: Any | None = None`；`resolve_optional` 调用在 composition_root 工厂 lambda 中执行，不在服务内部，见 Subtask 3.7 说明）
- [ ] 在 `generate_summary()` 中调用评估守卫：
  - 先执行 `quick_rule_check()` 规则预检
  - 若 `quick_block=True`，直接返回阻断结果，不调用 LLM 生成
  - 否则调用 `evaluate()` 进行 LLM 多维评估
  - 若 `should_block=True`，不调用 LLM 生成，返回 "数据不足" 的阻断响应
- [ ] 阻断响应格式：`{"error": "数据不足", "details": {"overall_score": float, "block_reason": str, "dimensions": {...}}}`
- [ ] 降级策略：
  - `relevance_evaluation_service` 为 None（构造失败或 composition_root 中未注入）→ 跳过评估，直接生成摘要（WARNING 日志记录"相关性评估服务未注册，跳过评估"）
  - LLM 评估调用失败 → 捕获 `RelevanceEvaluationError`，跳过评估，直接生成摘要（WARNING 日志记录"LLM 评估调用失败，跳过评估"），不可抛出阻断异常
  - **关键边界**：仅捕获 `RelevanceEvaluationError`（`ExternalException` 派生）降级；`RelevanceEvaluationBlockedError`（`BusinessException` 派生）与规则预检阻断必然而向调用方抛出，禁止进入降级分支——两类异常的基类层次天然分离，正好利用
  - 规则预检阻断 → 必然阻断，不降级
- [ ] 评估延迟 P95 < 3s（含 LLM 调用，规则预检 P95 < 100ms）
- [ ] 阻断准确率 100%

### AC-7: 检索相关性评估 API 端点

**Given** 评估服务已就绪
**When** 用户通过 API 请求相关性评估
**Then** 返回多维评估结果
**And** 包含各维度分数、综合评分、阻断状态

**验证标准/Validation Criteria:**
- [ ] API 路由位于 `src/interfaces/api/relevance_evaluation.py`（新增文件，遵循现有按功能命名的约定，如 `summary.py`、`strategic_archive.py`、`audit.py`）
- [ ] `POST /api/v1/search/evaluate` 端点
  - 请求体：`{"query_text": str, "tenant_id": str | None (可选)}`
  - **安全设计**：系统内部通过 `resolver.resolve("layered_retrieval_service")` 执行真实检索后评估，不接受客户端直接传入 `search_results`（防止客户端伪造高分结果绕过质量守卫）
  - 响应体：`{"overall_score": float, "context_relevance": float, "completeness": float, "timeliness": float, "context_relevance_reason": str, "completeness_reason": str, "timeliness_reason": str, "should_block": bool, "block_reason": str | None}`
  - **错误处理**：领域异常透传到全局 `ExceptionHandlers`（不捕获异常抛 `HTTPException`，避免丢失 `code`/`request_id`/`X-Error-Code` 响应头）
- [ ] 在 `src/interfaces/api/app.py` 中通过 `app.include_router()` 注册路由
- [ ] 更新 `docs/api/openapi.yaml` 添加 `/api/v1/search/evaluate` 端点
- [ ] API 契约测试通过（`tests/contracts/test_api_contract_relevance_evaluation.py`）
- [ ] 所有 API 路由通过认证中间件

### AC-8: 检索结果时效性处理

**Given** 检索结果 payload 可能包含时效性信息
**When** 执行时效性评估
**Then** 从 payload 中提取 `created_at`/`updated_at`/`valid_from`/`valid_until` 等字段
**And** 若字段缺失，默认时效性评分 1.0（不惩罚）
**And** 未来 Story 3.11/3.12 完善后可直接使用

**验证标准/Validation Criteria:**
- [ ] 时效性评估从 `SearchResult.payload` 中提取如下字段（按优先级）：
  1. `valid_until` — 若存在且 `valid_until < now`，时效性评分 0.0（完全过期）
  2. `updated_at` — 若存在，计算距今天数，>365天时效性 0.3，>180天 0.6，>30天 0.8，否则 1.0
  3. `created_at` — 若存在且 `updated_at` 不存在，同上逻辑
  4. 以上字段均不存在 — 默认 1.0（不惩罚）
- [ ] 综合时效性评分 = 所有检索结果时效性评分的平均值
- [ ] 时效性评估逻辑在 `RelevanceEvaluationService` 中实现（`_evaluate_timeliness()` 方法），服务端计算时效性引用值
- [ ] **职责边界约定**：服务端计算的时效性评分作为 `{search_context}` 中嵌入的补充信息注入 Prompt（每个检索结果附带 `[时效性: updated_at=2026-01-15]` 标记），供 LLM 在评估时效性时参考；最终 `timeliness` 分数由 LLM 输出。服务端引用值不覆盖 LLM 输出（避免双重评估冲突）。若 LLM 未输出时效性评估所需信息，服务端引用值可直接作为 `timeliness` 兜底
- [ ] **注入形式**：时效性字段信息嵌入在 `{search_context}` 中，**不需要新增独立 `{timeliness_context}` 占位符**；User Prompt 模板通过 `_build_search_context_with_timeliness()` 方法构建，该方法在标准 `_build_search_context()` 基础上为每个检索结果条目附加时效性标记

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 事件定义位于 `src/domain/events/`
- [ ] 使用标准库实现领域事件校验（如 dataclass / Enum / 自定义验证），禁止在领域层依赖 Pydantic
- [ ] 本 Story **不新增**领域事件（检索相关性评估是同步调用，不触发异步事件）
- [ ] 如需异步评估日志，定义 `RelevanceEvaluated` 事件（可选，MVP 暂不实现）

#### 数据模型 (Data Models)
- [ ] 评估结果类型定义位于 `src/domain/ports/relevance_evaluation.py`（TypedDict，领域层零外部依赖）
- [ ] 评估 Schema 定义位于 `src/application/services/relevance_schemas.py`（Pydantic BaseModel，应用层允许依赖 Pydantic）
- [ ] 评估 Schema 包括：`RelevanceEvaluation`、`RuleBasedEvaluation`
- [ ] 所有 Schema 通过 Pydantic V2 严格模式验证

#### 统一端口定义注册与管理 (Port Contract)
- [ ] 端口契约定义位于 `src/domain/ports/relevance_evaluation.py`（新增）
- [ ] 端口注册中心位于 `src/domain/ports/registry.py`，所有端口必须登记为 `PortSpec`
- [ ] 端口实现仅可在 `src/composition_root.py` 统一注册，禁止业务代码直接实例化具体实现
- [ ] 端口解析器位于 `src/domain/ports/resolver.py`，业务代码只通过抽象解析实现
- [ ] 端口契约门禁位于 `src/domain/ports/contract_gate.py`，端口变更必须通过兼容性检查
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_relevance_evaluation.py`）
- [ ] 接口命名符合单一职责，禁止同义接口重复定义
- [ ] 端口注册时提供 module 参数（register_port() 的必需参数）
- [ ] 端口具备唯一名称、版本、owner、兼容策略、module
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

- [ ] **归属模块与基类** — 新增 `relevance` 子域（360-369）：
    - `RelevanceEvaluationError`（EXCEPTION_360）→ 继承 `ExternalException`，LLM 评估调用失败（与 `RerankError`/`LLMAPIError` 模式一致，外部服务错误）
    - `RelevanceEvaluationBlockedError`（EXCEPTION_361）→ 继承 `BusinessException`，检索结果不足被阻断（业务规则违反）
- [ ] **唯一编码分配** — 从 `relevance` 子域（360-361）选取，`grep -rw "EXCEPTION_36[0-9]" src/` 验证无碰撞
  - 编码范围选择理由：360-369 属于 `external` 父域（301-399）内的空闲段，与 `reranker`（350-359）相邻，语义一致（评估类异常与重排序类异常同属检索质量评估子域）；`RelevanceEvaluationBlockedError` 继承 `BusinessException` 但编码仍落在 `relevance` 子域（360-369），`nested_subdomains` 仅关心范围是否在父域内（[360,369] 确实在 [301,399] 内），不关心继承链
- [ ] **构造器参数设计** — 携带查询上下文（`query_text`、`result_count`、`overall_score`、`block_reason` 等），通过 `context` 字典暴露
- [ ] **消息安全性审查** — 错误消息面向调用方可理解，不泄露 SQL/堆栈等内部实现细节
- [ ] **编码注册** — 更新 `_code_ranges.py` 和 `test_code_ranges.py`：
    - `CODE_RANGES` 新增 `"relevance": (360, 369)`
    - `_CLASS_TO_SUBDOMAIN` 新增 `"RelevanceEvaluationError": "relevance"`、`"RelevanceEvaluationBlockedError": "relevance"`
    - `test_code_ranges.py` 中 `allowed_child_parent_subdomains` 新增 `("relevance", "external")`（注意：`RelevanceEvaluationBlockedError` 继承的 `BusinessException` 是抽象基类，Rule 2 会跳过，因此 `("relevance", "business")` 白名单非必需，但添加无害）
    - `test_code_ranges.py` 中 `nested_subdomains` 新增 `"relevance": "external"`（格式为 `dict[str, str]`：子域名 → 父域名，验证 [360,369] 在 [301,399] 范围内）
- [ ] **HTTP 状态码映射** — `EXCEPTION_HTTP_MAP` 注册（**必须显式注册**，否则 `isinstance` 回退到基类映射）：
    - `RelevanceEvaluationError`（EXCEPTION_360）→ `500`（服务端评估失败，与 `RerankError` 模式一致，精确注册避免 `isinstance` 回退到 `ExternalException` 基类 502）
    - `RelevanceEvaluationBlockedError`（EXCEPTION_361）→ `422`（业务规则违反，检索结果不足，与 `BusinessRuleViolationError` 模式一致，精确注册避免回退到 `BusinessException` 基类 400）
- [ ] **导出完整性** — 模块 `__all__` + 包 `__init__.py` 导入 + `EXCEPTION_HTTP_MAP` 映射
- [ ] **测试覆盖** — 构造/`to_dict()`/HTTP 映射/编码唯一性 + 子域范围测试全部通过：
    - `poetry run pytest tests/unit/domain/exceptions/ -v`（含 `test_error_code_uniqueness.py` + `test_code_ranges.py`）
    - `poetry run pytest tests/unit/interfaces/api/test_exception_handlers.py -v`
- [ ] **BDD 验收场景** — 异常路径的 Gherkin 场景纳入 Edge Cases

#### API 契约 (API Contract)
- [ ] 遵循 OpenAPI 标准的 API 契约定义位于 `docs/api/openapi.yaml`
- [ ] API 契约测试通过（`tests/contracts/test_api_contract_relevance_evaluation.py`）
- [ ] API 版本管理正确（`/api/v1/search/evaluate`）

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
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_relevance_evaluation.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_relevance_evaluation.py`
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
| **TDD 单元测试** | 评估 Schema | Pydantic Schema 定义、字段验证、反序列化 | `tests/unit/application/services/test_relevance_schemas.py` | Task 1 |
| **TDD 单元测试** | 评估端口 | 端口契约方法签名、参数校验 | `tests/unit/domain/ports/test_relevance_evaluation_port.py` | Task 1 |
| **TDD 单元测试** | 评估 Prompt 模板 | 模板变量替换、评估标准完整性 | `tests/unit/application/services/test_relevance_prompts.py` | Task 2 |
| **TDD 单元测试** | 规则预检 | 空结果/低分快速阻断、规则预检逻辑 | `tests/unit/application/services/test_relevance_rule_check.py` | Task 2 |
| **TDD 单元测试** | 评估服务 | LLM 评估调用、多维评分、阻断逻辑、时效性评估 | `tests/unit/application/services/test_relevance_evaluation_service.py` | Task 2 |
| **TDD 单元测试** | 评估异常 | 构造/属性/`to_dict()`/cause 链/HTTP 映射 | `tests/unit/domain/exceptions/test_relevance_exceptions.py` | Task 1 |
| **SDD 验收测试** | Gherkin 场景 | 业务价值验收 | `tests/acceptance/test_acceptance_relevance_evaluation.feature` | Task 0 |
| **SDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `tests/acceptance/test_acceptance_relevance_evaluation.py` | Task 0 |
| **SDD 验收测试** | 收尾验收场景 | `src` 与测试目录完成清单最终确认 | `tests/acceptance/test_acceptance_relevance_evaluation.feature` | Task 5 |
| **SDD 验收测试** | 收尾 BDD 步骤实现 | 完成清单断言与步骤函数 | `tests/acceptance/test_acceptance_relevance_evaluation.py` | Task 5 |
| **SDD 契约测试** | 端口契约 | 端口注册、版本、兼容性、实现解析 | `tests/contracts/test_port_contract_relevance_evaluation.py` | Task 0 |
| **SDD 契约测试** | API 契约 | OpenAPI 端点、请求/响应结构 | `tests/contracts/test_api_contract_relevance_evaluation.py` | Task 0 |
| **TDD 领域异常测试** | 异常 HTTP 映射 | HTTP 映射/状态码/响应结构 | `tests/unit/interfaces/api/test_exception_handlers.py` | Task 1 |
| **TDD 领域异常测试** | 编码唯一性 | 所有异常类 `code` 无碰撞 | `tests/unit/domain/exceptions/test_error_code_uniqueness.py` | Task 1 |
| **TDD 领域异常测试** | 编码子域范围 | 子域范围/继承链一致性 | `tests/unit/domain/exceptions/test_code_ranges.py` | Task 1 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖、禁止跨层引用 | `tests/unit/architecture/test_arch_relevance_evaluation.py` | Task 4 |
| **集成测试** | 层间协作 | LLMClientPort + RelevanceEvaluationService 协作 | `tests/integration/test_integration_relevance_evaluation.py` | Task 3 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（核心业务流，评估编排，CI 通过 `scripts/check_coverage_gates.py` 校验）
- [ ] **领域层覆盖率 ≥90%**（端口契约协议，CI 通过 `scripts/check_coverage_gates.py` 校验）
- [ ] **接口层覆盖率 ≥85%**（API 路由，请求响应验证；项目级建议指标，非 CI 强制门禁）
- [ ] **集成测试覆盖率 ≥75%**（`pytest --cov=tests/integration --cov-fail-under=75`；项目级建议指标，非 CI 强制门禁）

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
| **外部服务隔离** | LLM 调用使用 Mock（单元测试）或真实 API（集成测试） | 真实数据被污染 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突导致并行失败 |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **BDD async 配合** | BDD 步骤函数不使用 @pytest.mark.asyncio，用 event_loop.run_until_complete() 运行 async | 直接用 @pytest.mark.asyncio 会导致 BDD context 数据丢失 |
| **LLM Mock 策略** | 单元测试使用 `AsyncMock(spec=LLMClientPort)` 模拟 LLM 调用；集成测试使用真实 `LitellmLLMClient`（需配置 LLM 环境变量） | 测试不可重复或依赖外部 API |

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

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 多维评估 Schema 定义 | Task 0 | SDD 规范定义 | `test_relevance_schemas.py` |
| AC-1 | 多维评估 Schema 定义 | Task 1 | TDD Schema 实现 | `test_relevance_schemas.py` |
| AC-2 | 评估端口契约 | Task 0 | SDD 规范定义 | `test_port_contract_relevance_evaluation.py` |
| AC-2 | 评估端口契约 | Task 1 | TDD 端口实现 | `test_relevance_evaluation_port.py` |
| AC-3 | 评估异常体系 | Task 0 | SDD 规范定义（异常契约设计） | `test_relevance_exceptions.py` |
| AC-3 | 评估异常体系 | Task 1 | TDD 异常定义 | `test_relevance_exceptions.py` |
| AC-4 | 评估应用服务（LLM 评估） | Task 2 | TDD 服务实现 | `test_relevance_evaluation_service.py` |
| AC-4 | 规则预检 | Task 2 | TDD 规则预检 | `test_relevance_rule_check.py` |
| AC-5 | 评估 Prompt 模板 | Task 2 | TDD Prompt 模板 | `test_relevance_prompts.py` |
| AC-6 | 与摘要生成集成 | Task 3 | TDD 集成实现 | `test_integration_relevance_evaluation.py` |
| AC-7 | 评估 API 端点 | Task 0 | SDD 规范定义（API 契约设计） | `test_api_contract_relevance_evaluation.py` |
| AC-7 | 评估 API 端点 | Task 3 | TDD API 端点 | `test_api_contract_relevance_evaluation.py` |
| AC-8 | 时效性评估 | Task 2 | TDD 时效性逻辑（合并入评估服务） | `test_relevance_evaluation_service.py` |
| AC-1,2,3,4 | 架构约束验证 | Task 4 | SDD 架构验证 | `test_arch_relevance_evaluation.py` |
| AC-1~8 | 开发结束验收 | Task 5 | 收尾验收 | `test_acceptance_relevance_evaluation.feature` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-7

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。这是 SDD 规范驱动的基础。

- [ ] Subtask 0.1: 定义评估 Schema 契约（`RelevanceEvaluation`、`RuleBasedEvaluation`）
- [ ] Subtask 0.2: 创建/更新 `docs/api/openapi.yaml`（新增 `POST /api/v1/search/evaluate` 端点）
- [ ] Subtask 0.3: 编写端口契约测试 `tests/contracts/test_port_contract_relevance_evaluation.py`（遵循项目标准四方法模式：`test_port_is_registered` + `test_implementation_has_required_methods` + `test_metadata_complete` + `test_lifetime_is_scoped`（断言 `Lifetime.SCOPED`））
- [ ] Subtask 0.4: 编写 API 契约测试 `tests/contracts/test_api_contract_relevance_evaluation.py`
- [ ] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_relevance_evaluation.feature`
- [ ] Subtask 0.6: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_relevance_evaluation.py`
- [ ] Subtask 0.7: 运行所有 Task 0 测试（端口契约测试 + API 契约测试 + 验收测试），确认全部失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 所有 Task 0 测试（端口契约测试 + API 契约测试 + 验收测试）运行失败（预期行为，红阶段确认）

---

### Task 1: 领域层端口契约 + 评估 Schema + 异常体系

**关联 AC:** AC-1, AC-2, AC-3

> **说明：** 本 Task 定义领域层端口契约（`RelevanceEvaluationPort`）、应用层评估 Schema（`RelevanceEvaluation`/`RuleBasedEvaluation`）和异常体系（`RelevanceEvaluationError`、`RelevanceEvaluationBlockedError`），是后续所有实现 Task 的依赖基础。

#### TDD 循环 [A]：评估 Schema 契约

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_relevance_schemas.py`（Schema 字段验证、分数范围、should_block 计算逻辑、block_reason 必填约束） |
| 🟢 绿 | 实现 `src/application/services/relevance_schemas.py`（`RelevanceEvaluation`、`RuleBasedEvaluation`） |
| 🔄 重构 | 添加 docstring、类型注解、字段验证器 |

- [ ] Subtask 1.1: 🔴 红 — 编写评估 Schema 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现评估 Schema
- [ ] Subtask 1.3: 🔄 重构 — 优化 Schema 代码

#### TDD 循环 [B]：评估端口契约

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_relevance_evaluation_port.py`（端口契约签名验证、结果 TypedDict 字段验证） |
| 🟢 绿 | 实现 `src/domain/ports/relevance_evaluation.py`（`RelevanceEvaluationPort` Protocol + `RelevanceEvaluationResult`/`RuleBasedResult` TypedDict） |
| 🔄 重构 | 添加 docstring、类型注解、架构决策注释 |

- [ ] Subtask 1.4: 🔴 红 — 编写评估端口失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 `RelevanceEvaluationPort` Protocol
- [ ] Subtask 1.6: 🔄 重构 — 优化端口代码

#### TDD 循环 [C]：评估异常体系

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_relevance_exceptions.py`（异常构造/序列化/context 字典） |
| 🟢 绿 | 实现 `src/domain/exceptions/relevance_exceptions.py` |
| 🔄 重构 | 注册异常到 `_code_ranges.py`、`__init__.py`、`EXCEPTION_HTTP_MAP`，更新 `test_code_ranges.py` |

- [ ] Subtask 1.7: 🔴 红 — 编写评估异常失败测试
- [ ] Subtask 1.8: 🟢 绿 — 实现 `RelevanceEvaluationError` 和 `RelevanceEvaluationBlockedError`
- [ ] Subtask 1.9: 🔄 重构 — 注册异常到 `_code_ranges.py`（新增 `relevance` 子域 360-369）、`__init__.py`、`EXCEPTION_HTTP_MAP`、`test_code_ranges.py`

**完成标准/Definition of Done:**
- [ ] `RelevanceEvaluation`、`RuleBasedEvaluation` Schema 定义完成
- [ ] `RelevanceEvaluationPort` 端口契约定义完成
- [ ] `RelevanceEvaluationResult`、`RuleBasedResult` TypedDict 定义完成
- [ ] `RelevanceEvaluationError`（EXCEPTION_360）和 `RelevanceEvaluationBlockedError`（EXCEPTION_361）定义完成
- [ ] 异常体系完整注册（`_code_ranges.py`/`__init__.py`/`EXCEPTION_HTTP_MAP`）
- [ ] 所有 TDD 循环测试通过
- [ ] 异常编码无碰撞（`grep -rw "EXCEPTION_36[0-9]" src/` 零输出）

---

### Task 2: 评估应用服务 + Prompt 模板 + 规则预检 + 时效性 — 含完整 TDD 循环

**关联 AC:** AC-4, AC-5, AC-8

> **说明：** 本 Task 实现 `RelevanceEvaluationService` 应用层编排服务，注入 `LLMClientPort` 驱动 LLM-as-a-Judge 多维评估，定义评估 Prompt 模板，实现规则预检和时效性评分逻辑。

#### TDD 循环 [A]：评估 Prompt 模板

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_relevance_prompts.py`（模板变量替换、每个维度的评估标准完整性、评分规则） |
| 🟢 绿 | 实现 `src/application/services/relevance_prompts.py`（System Prompt + User Prompt 模板） |
| 🔄 重构 | 统一 Prompt 格式、提取公共模板、添加注释说明 |

- [ ] Subtask 2.1: 🔴 红 — 编写 Prompt 模板失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 Prompt 模板
- [ ] Subtask 2.3: 🔄 重构 — 优化 Prompt 格式

#### TDD 循环 [B]：规则预检逻辑

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_relevance_rule_check.py`（空结果阻断、低分阻断、有效结果不阻断、边界分数） |
| 🟢 绿 | 实现 `RelevanceEvaluationService.quick_rule_check()` 方法 |
| 🔄 重构 | 优化预检逻辑、添加日志 |

- [ ] Subtask 2.4: 🔴 红 — 编写规则预检失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现规则预检
- [ ] Subtask 2.6: 🔄 重构 — 优化预检逻辑

#### TDD 循环 [C]：评估应用服务（含时效性评估合并）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_relevance_evaluation_service.py`（多维评估、LLM 调用验证、Schema 验证、阻断逻辑、LLM 调用失败异常、空检索结果边界、LLM 返回无效分数、**时效性字段提取、过期判定、默认值**） |
| 🟢 绿 | 实现 `src/application/services/relevance_evaluation_service.py`（`RelevanceEvaluationService` 类，含 `_evaluate_timeliness()` 方法） |
| 🔄 重构 | 添加降级策略、日志、异常链包装 |

- [ ] Subtask 2.7: 🔴 红 — 编写评估服务失败测试（含时效性评估）
- [ ] Subtask 2.8: 🟢 绿 — 实现 `RelevanceEvaluationService`（含 `_evaluate_timeliness()`）
- [ ] Subtask 2.9: 🔄 重构 — 优化服务代码

**完成标准/Definition of Done:**
- [ ] `RelevanceEvaluationService` 完整实现（含 evaluate、quick_rule_check、_evaluate_timeliness）
- [ ] 评估 Prompt 模板定义完成（相关性/完整性/时效性三维度评分标准）
- [ ] 规则预检逻辑完整（空结果/低分阻断）
- [ ] 时效性评估逻辑完整（payload 字段提取/过期判定/默认值）
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥85%（应用层）
- [ ] LLM 调用失败时抛出 `RelevanceEvaluationError`，阻断时抛出 `RelevanceEvaluationBlockedError`

---

### Task 3: 与摘要生成集成 + 评估 API 端点

**关联 AC:** AC-6, AC-7

> **说明：** 本 Task 将 `RelevanceEvaluationService` 集成到 `SummaryGenerationService` 中作为检索质量守卫，并暴露 API 端点。

#### TDD 循环 [A]：与摘要生成集成

> **前置依赖：** Story 3.6 的 `SummaryGenerationService` 必须已实现。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_relevance_evaluation.py`（`RelevanceEvaluationService` + 真实 `LLMClientPort` 端到端 LLM 评估验证）+ `tests/integration/test_integration_contractual_summary.py` 追加用例（`SummaryGenerationService` + `RelevanceEvaluationService` 评估守卫阻断/降级验证） |
| 🟢 绿 | 修改 `SummaryGenerationService` 注入 `relevance_evaluation_service`（可选依赖），在 `generate_summary()` 中插入评估守卫 |
| 🔄 重构 | 优化降级策略、添加日志 |

> **⚠️ 构造签名变更影响面**：`SummaryGenerationService.__init__()` 新增 `relevance_evaluation_service: Any | None = None` 参数（位置在现有 4 个必选参数之后）。此变更影响以下文件：
> 1. `src/composition_root.py` — 注册 lambda 中通过 `resolver.resolve_optional()` 注入（Subtask 3.7 处理）
> 2. `tests/unit/application/services/test_summary_generation_service.py` — 现有 4 参数构造调用保持兼容（默认 None，无需修改测试断言）
> 3. `tests/acceptance/test_acceptance_contractual_summary.py` — 现有构造调用保持兼容（默认 None）
> 4. `tests/integration/test_integration_contractual_summary.py` — 现有构造调用保持兼容（默认 None）

- [ ] Subtask 3.1: 🔴 红 — 编写集成失败测试
- [ ] Subtask 3.2: 🟢 绿 — 修改 `SummaryGenerationService` 集成评估守卫
- [ ] Subtask 3.3: 🔄 重构 — 优化集成逻辑

#### TDD 循环 [B]：评估 API 端点

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/contracts/test_api_contract_relevance_evaluation.py`（请求/响应 Schema、状态码、认证） |
| 🟢 绿 | 实现 `src/interfaces/api/relevance_evaluation.py`（`POST /api/v1/search/evaluate` 路由）+ 注册到 `app.py` |
| 🔄 重构 | 统一错误处理、添加请求验证 |

- [ ] Subtask 3.4: 🔴 红 — 编写 API 端点失败测试
- [ ] Subtask 3.5: 🟢 绿 — 实现评估 API 路由
- [ ] Subtask 3.6: 🔄 重构 — 优化 API 响应格式

#### 端口注册到 composition_root.py

> **⚠️ 前置依赖：** Subtask 3.7 必须在 TDD 循环 [B]（API 端点）之前完成。API 路由处理器依赖 `resolver.resolve("relevance_evaluation_service")` 获取服务实例，未注册端口将导致路由初始化失败。

- [ ] Subtask 3.7: 在 `src/composition_root.py` 中注册 `relevance_evaluation_service` 端口，并**同步修改 `summary_generation_service` 注册**（`resolve_optional` 调用在 composition_root 工厂 lambda 中执行，不在服务内部）：
  - 端口名称：`relevance_evaluation_service`
  - 生命周期：`Lifetime.SCOPED`（与 `summary_generation_service`、`layered_retrieval_service` 等同类服务保持一致）
  - 实现：工厂函数 `lambda resolver: RelevanceEvaluationService(llm_client=resolver.resolve("llm_client"))` 注入依赖
  - `summary_generation_service` 注册修改为：`SummaryGenerationService(..., relevance_evaluation_service=resolver.resolve_optional("relevance_evaluation_service"))`
  - **注意**：`resolve_optional` 对未注册端口抛 `RuntimeError`（包装 `KeyError`），None 分支仅覆盖注册后构造失败（`ImportError`/`RuntimeError`）。生产路径 Subtask 3.7 总会注册该端口，因此 "未注册" 降级分支实际不可达；构造失败降级分支可达。集成测试模拟降级时应通过真实构造 `SummaryGenerationService(relevance_evaluation_service=None)` 而非依赖 resolver 行为
- [ ] Subtask 3.8: 更新端口契约测试 `tests/contracts/test_port_contract_relevance_evaluation.py` — **端口契约测试由红转绿**（Task 0 编写时端口未注册，测试断言失败；Subtask 3.7 注册后，测试通过）

**完成标准/Definition of Done:**
- [ ] `SummaryGenerationService` 集成评估守卫（可选依赖注入，降级策略）
- [ ] 评估阻断时返回"数据不足"响应
- [ ] `POST /api/v1/search/evaluate` API 端点可用
- [ ] 端口注册完成，集成测试通过

---

### Task 4: SDD 架构约束验证测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [ ] Subtask 4.1: 创建 `tests/unit/architecture/test_arch_relevance_evaluation.py`
- [ ] Subtask 4.2: 验证领域层零外部依赖（`RelevanceEvaluationPort` 仅导入标准库）
- [ ] Subtask 4.3: 验证依赖方向正确（domain → application → interfaces/infrastructure）
- [ ] Subtask 4.4: 验证 `composition_root.py` 注册完整性
- [ ] Subtask 4.5: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**
- [ ] 所有架构/约束测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败

---

### Task 5: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

> **性质说明：** 验收测试场景与 BDD 步骤已在 Task 0 定义并完成红阶段验证，本 Task 验证已完成的实现满足全部验收场景，不编写新的功能测试。

| 阶段 | 动作 |
|------|------|
| ✅ 验证 | 运行 Task 0 定义的 `tests/acceptance/test_acceptance_relevance_evaluation.feature` 全部场景，确认通过 |
| ✅ 验证 | 逐项核对 `src` 与 `tests/` 完成清单 |
| ✅ 验证 | 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验 |

- [ ] Subtask 5.1: 验证 `src` 完成清单（`RelevanceEvaluationPort` 已注册、Schema 已定义可导入、异常编码无碰撞、API 端点可访问）
- [ ] Subtask 5.2: 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单文件全部存在且可通过 pytest 发现
- [ ] Subtask 5.3: 运行 Task 0 定义的验收测试并确认全部通过
- [ ] Subtask 5.4: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`epics_v1.0.md`](../../planning-artifacts/epics_v1.0.md) Story 3.7 节定义，[`or.md`](../../planning-artifacts/or.md)

- **架构模式:** 六边形架构（Ports & Adapters）、LLM-as-a-Judge（LLM 作为评估器）、守卫模式（Guard Pattern）
- **设计约束:**
  - 领域层零外部依赖（仅 Python 标准库）
  - 依赖方向：domain ← application ← interfaces / infrastructure
  - 所有端口通过 `composition_root.py` 统一注册
  - Schema 定义在应用层（`src/application/`），允许使用 Pydantic
  - 端口契约定义在领域层（`src/domain/ports/`），仅使用 Protocol
  - 评估结果 TypedDict 定义在领域层端口文件（与 `SearchResult` 风格一致）
  - LLM 评估使用 `LLMClientPort.structured_generate()`，不直接调用 LLM API
  - 评估 Prompt 注入检索结果上下文，LLM 输出结构化评估结果
- **技术栈:** Python 3.11+、FastAPI 0.104+、Pydantic V2（Schema 验证）、LiteLLM（LLM 调用）

### 关键架构决策

**来源:** [`epics_v1.0.md`](../../planning-artifacts/epics_v1.0.md) Story 3.7，[`architecture.md`](../../planning-artifacts/architecture.md)

| 决策 | 方案 | 理由 |
|------|------|------|
| **评估模式** | LLM-as-a-Judge + 规则预检双层 | 规则预检快速过滤明显不足结果（P95 < 100ms），LLM 评估深度分析（P95 < 3s） |
| **Schema 定义位置** | 应用层（`src/application/services/relevance_schemas.py`） | Schema 使用 Pydantic BaseModel，领域层不允许依赖 Pydantic |
| **结果 TypedDict 位置** | 领域层端口文件（`src/domain/ports/relevance_evaluation.py`） | 与 `SearchResult` 风格一致，端口契约直接引用结果类型 |
| **端口类型** | 新增 `RelevanceEvaluationPort` Protocol | 遵循六边形架构，保持端口契约与实现分离 |
| **异常子域** | 新增 `relevance` 子域（360-369） | `RelevanceEvaluationError` 继承 `ExternalException`（LLM 调用失败），`RelevanceEvaluationBlockedError` 继承 `BusinessException`（业务规则阻断），编码 360-369 属于 `external` 父域 301-399 内的空闲段，与 `reranker`（350-359）相邻 |
| **阻断阈值** | `overall_score < 0.6` 阻断 | 与 epics_v1.0.md 一致，0.6 为合格线 |
| **综合评分计算** | `(context_relevance + completeness + timeliness) / 3`，使用 `@computed_field` 服务端计算 | 服务端独立计算，不依赖 LLM 输出的一致性；阻断守卫以 `@computed_field` 计算结果为准，阻断准确率 100% 可验证 |
| **时效性默认值** | 字段缺失时默认 1.0（不惩罚） | 当前 payload 无时效性字段，Story 3.11/3.12 完善后可直接使用 |
| **集成方式** | 可选依赖注入 `SummaryGenerationService`，`resolve_optional` 调用在 composition_root 工厂 lambda 中执行 | 服务构造函数参数保持 `relevance_evaluation_service: Any | None = None`，不依赖 resolver |
| **降级策略** | 服务为 None/LLM 失败 → 跳过评估（WARNING 日志），规则预检阻断 → 必然阻断；仅捕获 `RelevanceEvaluationError` 降级，`RelevanceEvaluationBlockedError` 禁止降级 | 确保系统可用性，LLM 服务不可用时不影响摘要生成；两类异常基类层次天然分离 |
| **阻断响应** | 阻断时返回"数据不足"结构化响应 | 与 epics_v1.0.md 的"相关性<0.6 标注'数据不足'"一致 |
| **Prompt 模板位置** | 独立模块 `relevance_prompts.py` | 清晰分离 Prompt 与业务逻辑，方便迭代 |
| **LLM 调用方式** | 复用 `LLMClientPort.structured_generate()`（Story 3.2a） | 统一基础设施，获得熔断器和重试保护 |
| **API 端点设计** | `POST /api/v1/search/evaluate`，路由文件命名 `relevance_evaluation.py` | 独立评估端点，文件名遵循现有按功能命名约定（`summary.py`、`strategic_archive.py`、`audit.py`） |
| **评估维度数量** | MVP 三个维度（相关性/完整性/时效性） | 覆盖核心评估场景，后续可扩展（如准确性、权威性） |
| **HTTP 映射** | `RelevanceEvaluationError` → 500（与 `RerankError` 一致），`RelevanceEvaluationBlockedError` → 422（与 `BusinessRuleViolationError` 一致） | 精确注册避免 `isinstance` 回退到基类映射 |
| **Prompt 阻断规则** | 服务端以 `@computed_field` 计算结果为准，Prompt 仅供 LLM 评分参考 | 避免 Prompt 与代码逻辑不一致（原文档"任何维度<0.6"与代码"综合<0.6"矛盾已修正） |

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── exceptions/
│   │   ├── __init__.py                       # [修改] 导入 RelevanceEvaluationError/RelevanceEvaluationBlockedError，更新 __all__
│   │   ├── relevance_exceptions.py            # [新增] 相关性评估异常类
│   │   └── _code_ranges.py                   # [修改] 新增 relevance 子域 (360-369)
│   └── ports/
│       └── relevance_evaluation.py            # [新增] RelevanceEvaluationPort Protocol + 结果 TypedDict
│
├── application/
│   └── services/
│       ├── relevance_schemas.py              # [新增] 评估 Pydantic Schema
│       ├── relevance_prompts.py              # [新增] 评估 Prompt 模板
│       └── relevance_evaluation_service.py   # [新增] RelevanceEvaluationService
│
├── composition_root.py                       # [修改] 注册 relevance_evaluation_service 端口
│
└── interfaces/
    └── api/
        ├── relevance_evaluation.py          # [新增] 检索/评估 API 路由
        └── app.py                            # [修改] include_router(relevance_evaluation_router)

tests/
├── acceptance/
│   ├── test_acceptance_relevance_evaluation.feature     # [新增] Gherkin 场景
│   └── test_acceptance_relevance_evaluation.py         # [新增] BDD 步骤实现
├── contracts/
│   ├── test_port_contract_relevance_evaluation.py      # [新增] 端口契约测试
│   └── test_api_contract_relevance_evaluation.py       # [新增] API 契约测试
├── integration/
│   └── test_integration_relevance_evaluation.py        # [新增] 集成测试
└── unit/
    ├── domain/
    │   ├── exceptions/
    │   │   └── test_relevance_exceptions.py           # [新增] 异常测试
    │   └── ports/
    │       └── test_relevance_evaluation_port.py       # [新增] 端口测试
    ├── application/
    │   └── services/
    │       ├── test_relevance_schemas.py               # [新增] Schema 测试
    │       ├── test_relevance_prompts.py               # [新增] Prompt 测试
    │       ├── test_relevance_rule_check.py            # [新增] 规则预检测试
    │       └── test_relevance_evaluation_service.py    # [新增] 服务+时效性测试
    └── architecture/
        └── test_arch_relevance_evaluation.py           # [新增] 架构验证

docs/
└── api/
    └── openapi.yaml                          # [修改] 新增 /api/v1/search/evaluate 端点

需要修改的已有文件（非新增）：
- src/application/services/summary_generation_service.py  # [修改] 注入评估服务（可选依赖），添加评估守卫
- src/domain/exceptions/__init__.py                       # [修改] 导出新异常类
- src/domain/exceptions/_code_ranges.py                   # [修改] 新增 relevance 子域
- src/interfaces/api/app.py                               # [修改] 注册 relevance_evaluation_router
- src/composition_root.py                                 # [修改] 注册 relevance_evaluation_service 端口 + 修改 summary_generation_service 注册
- tests/integration/test_integration_contractual_summary.py  # [修改] 追加 SummaryGenerationService + RelevanceEvaluationService 评估守卫集成用例（Subtask 3.1）
- tests/acceptance/test_acceptance_contractual_summary.py    # [修改] SummaryGenerationService 构造签名变更（新增可选参数，默认 None，现有调用保持兼容）

测试依赖文件（已存在，无需修改但需通过校验）：
- tests/unit/domain/exceptions/test_code_ranges.py         # [校验] allowed_child_parent_subdomains 新增 (relevance, external) 和 (relevance, business)
- tests/unit/domain/exceptions/test_error_code_uniqueness.py # [校验] 新异常编码需通过唯一性校验
- tests/unit/interfaces/api/test_exception_handlers.py      # [校验] HTTP 映射测试需覆盖新异常
- tests/unit/application/services/test_summary_generation_service.py  # [校验] SummaryGenerationService 构造签名变更（新增可选参数，默认 None，现有 4 参数调用保持兼容，无需修改测试断言）
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 3.6 - 契约化结构化摘要生成](./3-6-contractual-summary-generation.md)

**关键学习/Key Learnings:**
1. **端口注册模式**：`register_port()` 必须提供 `module` 参数（第 5 个必需参数），端口契约测试检查 `register_port` 调用的 `module` 参数
2. **异常子域注册流程**：新增子域需同时更新 `_code_ranges.py` 的 `CODE_RANGES`、`_CLASS_TO_SUBDOMAIN`、`__init__.py` 导出、`EXCEPTION_HTTP_MAP`、`test_code_ranges.py` 的 `allowed_child_parent_subdomains` 和 `nested_subdomains`
3. **BDD 测试异步模式**：BDD 步骤函数使用 `event_loop.run_until_complete()` 运行 async 代码，不要使用 `@pytest.mark.asyncio`
4. **LLM 调用模式**：`LLMClientPort.structured_generate()` 接收 `response_schema`（Pydantic BaseModel 子类），返回 Schema 实例，通过 `Schema.model_validate()` 验证
5. **可选依赖注入**：通过 `resolver.resolve_optional("port_name")` 注入可选依赖，服务未注册时降级处理

**应用到本故事/Applied to This Story:**
- [ ] 使用 Story 3.6 建立的 `SummaryGenerationPort` 协议，通过可选依赖注入评估守卫
- [ ] 复用 `LLMClientPort.structured_generate()` 进行 LLM-as-a-Judge 评估
- [ ] 异常注册遵循 `_code_ranges.py` + `__init__.py` + `EXCEPTION_HTTP_MAP` + `test_code_ranges.py` 四步流程
- [ ] BDD 测试使用 `event_loop.run_until_complete()` 而非 `@pytest.mark.asyncio`
- [ ] 评估 Schema 使用 Pydantic BaseModel 定义在应用层（`src/application/`）
- [ ] 评估结果 TypedDict 定义在领域层端口文件（与 `SearchResult` 风格一致）
- [ ] **纠正 Story 3.6 遗留问题**：`resolve_optional` 对未注册端口抛 `RuntimeError`（非返回 None），None 分支仅覆盖构造失败；`SummaryGenerationService` 构造函数参数使用 `relevance_evaluation_service: Any | None = None`，`resolve_optional` 在 composition_root 工厂 lambda 中执行

### 已有资产（可直接复用）

**端口层：**
- **LLMClientPort** — `src/domain/ports/llm_client.py`，`structured_generate(prompt, response_schema, config=None, system_prompt=None)` 方法已就绪，用于 LLM-as-a-Judge 评估
- `SummaryGenerationPort` — `src/domain/ports/summary_generation.py`，`generate_summary()` 方法已就绪，本 Story 在其上游增加评估守卫
- `LayeredRetrievalPort` — `src/domain/ports/layered_retrieval.py`，`search_top_down()` 和 `search_bottom_up()` 方法已就绪，评估对象为检索结果

**服务层：**
- `SummaryGenerationService` — `src/application/services/summary_generation_service.py`，本 Story 注入可选评估守卫
- `SummaryGenerationService` 的 `LLMClientPort` 注入模式可直接参考

**异常层：**
- `LLMAPIError`（EXCEPTION_330）— LLM API 传输层错误
- `LLMResponseError`（EXCEPTION_331）— 响应格式错误
- `LLMConfigError`（EXCEPTION_332）— 配置错误
- `RerankError`（EXCEPTION_350）— 重排序服务错误（参考 ExternalException 继承模式）
- `SummaryGenerationError`（EXCEPTION_290）— 摘要生成异常（参考 BusinessException 继承模式）

**SearchResult 结构：**
- `SearchResult` 是 TypedDict，字段：`id: str | int`、`score: float`、`payload: dict[str, Any]`
- `payload` 中包含：`content`、`document_id`、`chunk_id`、`index_level`、`metadata` 等字段
- `score` 范围 0-1（余弦相似度），RRF 融合后为 RRF 分数

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.2 |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-08-16 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Template** | `_bmad-output/implementation-artifacts/stories/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/3-6-contractual-summary-generation.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] 前一个故事学习经验整合
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] **Round 2 D2 审查发现并修复** 1 个 P0 + 2 个 P1 问题：
  - P0#8: 请求体 `search_results` 安全缺陷 — 改为纯服务端检索后评估
  - P0#9: `evaluate()` 返回类型承诺矛盾 — 明确永远不抛 BlockedError，只返回 result
  - P1: quick_rule_check 防御性计算（NaN/缺失 score）
  - P1: 时效性注入形式明确（嵌入 `{search_context}`，无需独立占位符）
  - P1: 集成测试职责拆分（AC-4 和 AC-6 分离）
  - P1: 响应体 `dimension_reasons` 改为顶层 `*_reason` 字段
  - P1: 错误处理透传全局 ExceptionHandlers
  - P2: 时效性测试合并入 `test_relevance_evaluation_service.py`

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-7-search-relevance-evaluation.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/ports/relevance_evaluation.py` — RelevanceEvaluationPort Protocol + 结果 TypedDict
- `src/domain/exceptions/relevance_exceptions.py` — 评估异常
- `src/application/services/relevance_schemas.py` — 评估 Pydantic Schema
- `src/application/services/relevance_prompts.py` — 评估 Prompt 模板
- `src/application/services/relevance_evaluation_service.py` — 评估服务
- `src/interfaces/api/relevance_evaluation.py` — 检索/评估 API 路由
- `tests/unit/domain/ports/test_relevance_evaluation_port.py` — 端口单元测试
- `tests/unit/domain/exceptions/test_relevance_exceptions.py` — 异常单元测试
- `tests/unit/application/services/test_relevance_schemas.py` — Schema 单元测试
- `tests/unit/application/services/test_relevance_prompts.py` — Prompt 单元测试
- `tests/unit/application/services/test_relevance_rule_check.py` — 规则预检单元测试
- `tests/unit/application/services/test_relevance_evaluation_service.py` — 服务+时效性单元测试
- `tests/unit/architecture/test_arch_relevance_evaluation.py` — 架构验证测试
- `tests/integration/test_integration_relevance_evaluation.py` — 集成测试
- `tests/acceptance/test_acceptance_relevance_evaluation.feature` — Gherkin 场景
- `tests/acceptance/test_acceptance_relevance_evaluation.py` — BDD 步骤实现
- `tests/contracts/test_port_contract_relevance_evaluation.py` — 端口契约测试
- `tests/contracts/test_api_contract_relevance_evaluation.py` — API 契约测试

**待修改的文件/To Be Modified:**
- `src/application/services/summary_generation_service.py` — 注入评估服务（可选依赖），添加评估守卫
- `src/domain/exceptions/__init__.py` — 导出新异常类
- `src/domain/exceptions/_code_ranges.py` — 新增 relevance 子域（360-369）
- `src/interfaces/api/app.py` — 注册 relevance_evaluation_router
- `src/composition_root.py` — 注册 relevance_evaluation_service 端口
- `docs/api/openapi.yaml` — 新增 /api/v1/search/evaluate 端点

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.7 |
| **Story Key** | 3-7-search-relevance-evaluation |
| **File** | `_bmad-output/implementation-artifacts/stories/3-7-search-relevance-evaluation.md` |
| **Status** | `backlog` → `ready-for-dev` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | P1 (MVP P0 — FR-SR-07) |
| **覆盖 FR** | FR-SR-07 |
| **依赖 Story** | Story 3.6（契约化摘要生成） |
| **评估维度** | 相关性（context_relevance）、完整性（completeness）、时效性（timeliness） |
| **阻断阈值** | `overall_score < 0.6` → 标注"数据不足" |
| **性能要求** | 规则预检 P95 < 100ms，LLM 评估 P95 < 3s |
| **质量要求** | 评估准确率 ≥ 90%，阻断准确率 100% |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.1.0
**创建日期/Created:** 2026-08-16
**最后更新/Last Updated:** 2026-08-16
**更新说明/Description:**
- v1.1.0: Round 1 审查修订（修复 7 个 P0 问题：Schema computed_field/条件必填验证、Prompt-代码阻断规则一致、resolve_optional 语义、降级捕获边界、nested_subdomains 格式、HTTP 映射、API 文件命名）
- v1.0.0: 创建故事文件
