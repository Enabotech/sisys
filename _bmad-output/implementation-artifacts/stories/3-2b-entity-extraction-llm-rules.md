# Story 3.2b: 实体抽取（LLM+ 规则混合）

**Status:** `done`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 知识工程师,
**I want** 系统抽取实体（LLM+ 规则混合策略），输出三元组,
**So that** 构建知识图谱的实体和关系，支持 GraphRAG 增强检索。

### 业务价值

本 Story 是 Epic 3（智能检索与知识发现）的**实体抽取 Story**，也是 FR-SR-02（实体抽取）的完整实现。它为后续 Story 3.3（领域词典管理）、Story 3.5（分层检索）、Epic 12（知识图谱与 GraphRAG）提供实体抽取能力。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **规则基实体抽取** | 高准确率保障，领域词典 AC 自动机确保关键实体不遗漏 | 准确率≥80% |
| **LLM 语义实体抽取** | 高召回率覆盖，LLM 理解上下文语义抽取非结构化实体 | 召回率≥90% |
| **冲突仲裁器** | 规则+LLM 双路融合，置信度加权输出最终三元组 | 仲裁准确率≥85% |
| **Neo4j 持久化** | 抽取结果通过 L5GraphPort 写入 Neo4j，支持知识图谱查询 | 写入成功率 100% |
| **异常体系** | 实体抽取专用异常，与项目异常体系集成 | 编码唯一性验证 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 3: 智能检索与知识发现，Story 3.2b

**前置依赖:**
- Story 3.2a（LLM Client 基础设施 ✅ 已实现）— 提供 `LLMClientPort` 用于 LLM 语义抽取
- Story 1.8（Neo4j 图存储层 ✅ 已实现）— 提供 `L5GraphPort` 用于结果持久化

**后续依赖:** Story 3.3（领域词典管理）、Story 3.5（分层检索）、Epic 12（知识图谱与 GraphRAG）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 实体抽取领域端口契约

**Given** 系统需要统一的实体抽取抽象
**When** 定义 `EntityExtractionPort` 协议
**Then** 包含 `extract_entities()` 核心方法
**And** `ExtractionResult` / `ExtractedEntity` / `ExtractedRelation` 值对象封装抽取结果
**And** 所有领域层定义零外部依赖（仅 Python 标准库 + Protocol）

**验证标准/Validation Criteria:**
- [ ] `EntityExtractionPort` Protocol 定义于 `src/domain/ports/entity_extraction.py`
- [ ] `ExtractedEntity` frozen dataclass（name, entity_type, confidence, extraction_source, metadata, normalized_name）
- [ ] `ExtractedRelation` frozen dataclass（source, target, relation_type, confidence, extraction_source, metadata）
- [ ] `ExtractionResult` frozen dataclass（entities, relations, extraction_metadata）
- [ ] `extract_entities(content, domain_context?)` — 核心抽取方法
- [ ] 端口注册于 `composition_root.py`，通过 `register_port()` 注册为 `entity_extraction` 端口

### AC-2: 实体抽取领域事件

**Given** 实体抽取完成
**When** 发布 `EntitiesExtracted` 领域事件
**Then** 事件携带完整的抽取结果（entity_count, relation_count, memory_id）
**And** 继承 `DomainEvent` 基类，遵循事件标准 Schema

**验证标准/Validation Criteria:**
- [ ] `EntitiesExtracted` 定义于 `src/domain/events/entity_extraction_events.py`
- [ ] 字段：`memory_id`（str）、`entity_count`（int）、`relation_count`（int）、`extraction_type`（str）
- [ ] `__post_init__` 设置 `aggregate_id = self.memory_id`、`aggregate_type = "EntityExtraction"`
- [ ] 事件注册于 `src/domain/events/__init__.py` 和 `configs/event_channels.yaml`

### AC-3: 实体抽取异常体系

**Given** 实体抽取过程中可能发生多种错误
**When** 定义实体抽取异常类
**Then** 继承项目统一异常层次结构
**And** 分配唯一异常编码

**验证标准/Validation Criteria:**
- [ ] `EntityExtractionError`（EXCEPTION_340）— 继承 `ExternalException`，对应抽取失败
- [ ] 异常编码在 `_code_ranges.py` 注册，无碰撞
- [ ] 异常在 `__init__.py` 导出，在 `EXCEPTION_HTTP_MAP` 注册

### AC-4: 规则基实体抽取（AC 自动机 + 正则）

**Given** 已配置领域词典和正则规则
**When** 对文本内容执行规则基抽取
**Then** AC 自动机匹配命名实体（人员、组织、地点、产品、概念）
**And** 正则模式匹配结构化实体（日期、金额、百分比、联系方式）
**And** 准确率≥80%，输出结构化的 `ExtractedEntity` 列表

**验证标准/Validation Criteria:**
- [ ] `RuleBasedExtractor` 实现 `EntityExtractionPort` 位于 `src/infrastructure/external_services/entity_extraction/rule_extractor.py`
- [ ] 使用 `pyahocorasick` 构建 AC 自动机词典匹配器
- [ ] 使用 `re` 正则模式匹配结构化实体
- [ ] 内置基础战略领域词典（战略管理、财务、市场等基本词条）
- [ ] 支持规则可配置（词典可扩展、正则可追加）
- [ ] 匹配结果映射为 `ExtractedEntity` 值对象（`extraction_source="rule"`）

### AC-5: LLM 语义实体抽取

**Given** `LLMClientPort` 已可用（Story 3.2a）
**When** 调用 `LLMClientPort.structured_generate()` 进行语义实体抽取
**Then** 使用 Few-Shot+CoT 提示策略，Pydantic Schema 约束输出
**And** 召回率≥90%，覆盖规则基无法识别的语义实体

**验证标准/Validation Criteria:**
- [ ] `LLMEntityExtractor` 位于 `src/infrastructure/external_services/entity_extraction/llm_extractor.py`
- [ ] 实现 `EntityExtractionPort` 接口（`extract_entities(content, domain_context?)`），注入 `LLMClientPort` 调用 `structured_generate()`
- [ ] 使用 `LLMClientPort.structured_generate()` 而非裸 httpx
- [ ] 定义 `EntityExtractionSchema`（Pydantic BaseModel）作为结构化输出 Schema
- [ ] 提示模板包含 Few-Shot 示例和 CoT 推理步骤
- [ ] 错误处理：LLM 调用失败时透明降级至规则基结果（返回空结果，不抛出异常）

### AC-6: 冲突仲裁器（规则 + LLM 融合）

**Given** 规则基和 LLM 语义两路抽取结果
**When** 执行冲突仲裁
**Then** 按实体类型差异化配置权重（规则权重 0.6 / LLM 权重 0.4）
**And** 输出最终融合的三元组列表（实体-关系-实体）

**验证标准/Validation Criteria:**
- [ ] `ConflictArbitrator` 位于 `src/infrastructure/external_services/entity_extraction/conflict_arbitrator.py`
- [ ] 支持按实体类型差异化配置权重
- [ ] 相同实体合并策略：置信度加权平均，保留较高置信度来源
- [ ] 关系抽取：规则基关系 + LLM 语义关系融合
- [ ] 仲裁准确率≥85%

### AC-7: 应用层实体抽取编排服务

**Given** 系统需要执行完整实体抽取流程
**When** 调用 `EntityExtractionService` 应用服务
**Then** 依次执行：规则基抽取 → LLM 语义抽取 → 冲突仲裁 → L5 Neo4j 持久化
**And** 发布 `EntitiesExtracted` 领域事件
**And** 返回完整 `ExtractionResult`

**验证标准/Validation Criteria:**
- [ ] `EntityExtractionService` 位于 `src/application/services/entity_extraction_service.py`
- [ ] 构造函数注入：`rule_extractor`（EntityExtractionPort）、`llm_extractor`（EntityExtractionPort）、`l5_graph`（L5GraphPort）、`event_publisher`、`arbitrator`（ConflictArbitrator）
- [ ] LLM 实体抽取通过 `LLMEntityExtractor`（实现 EntityExtractionPort）间接调用 `LLMClientPort`，不在服务中直接依赖 LLMClientPort
- [ ] 异常处理：抽取失败时抛出 `EntityExtractionError`
- [ ] 输入验证：空内容或无效内容返回空结果而非抛出异常
- [ ] 事件发布失败时记录日志（不阻止主流程返回 ExtractionResult）

### AC-8: 端口注册与 DI 集成

**Given** 所有组件实现完成
**When** 在 `composition_root.py` 注册
**Then** `entity_extraction_rule`（SINGLETON，热更新语义要求全局共享）、`entity_extraction_llm`、`conflict_arbitrator`、`entity_extraction_service` 四个端口注册
**And** 通过 `Resolver` 可正确解析
**And** 端口契约测试通过

**验证标准/Validation Criteria:**
- [ ] `composition_root.py` 注册 `entity_extraction_rule` 端口（RuleBasedExtractor 实现 EntityExtractionPort）
- [ ] `composition_root.py` 注册 `entity_extraction_llm` 端口（LLMEntityExtractor 实现 EntityExtractionPort）
- [ ] `composition_root.py` 注册 `conflict_arbitrator` 端口（ConflictArbitrator）
- [ ] `composition_root.py` 注册 `entity_extraction_service` 端口（EntityExtractionService 编排服务）
- [ ] 端口契约测试 `tests/contracts/test_port_contract_entity_extraction.py` 通过
- [ ] `src/domain/ports/__init__.py` 导出 `EntityExtractionPort`

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

**新建事件：**
- [ ] `EntitiesExtracted`（`src/domain/events/entity_extraction_events.py`）
  - 继承 `DomainEvent`
  - 字段: `memory_id: uuid.UUID` — 关联记忆 ID（UUID 类型，与 `DocumentProcessed` 模式一致）
  - `entity_count: int` — 抽取实体数量
  - `relation_count: int` — 抽取关系数量
  - `extraction_type: str` — 抽取类型（"rule_only" / "llm_only" / "hybrid"）
  - 事件类型: `"EntitiesExtracted"`（`field(default="EntitiesExtracted", init=False)`）
  - `__post_init__` 设置 `aggregate_id = self.memory_id`（UUID 类型赋值给 `aggregate_id`，与 `DocumentProcessed` 模式一致；使用 `if aggregate_id is None` 保护）、`aggregate_type = "EntityExtraction"`
  - Schema 版本: v1.0.0
  - 通道: `RabbitMQ + Outbox`（业务状态型）
  - 注册于 `src/domain/events/__init__.py` 和 `configs/event_channels.yaml`
  - 同时更新 `ChannelRouter.DEFAULT_MAPPINGS`（`src/infrastructure/messaging/channel_router.py`），新增事件同时更新两处，保持同步

#### 数据模型 (Data Models)

**新建值对象（领域层 `src/domain/ports/entity_extraction.py`）：**
- [ ] `ExtractedEntity` frozen dataclass
  - 字段: `name: str` — 实体名称
  - `entity_type: str` — 实体类型（PERSON/ORG/LOC/PRODUCT/CONCEPT/DATE/AMOUNT/etc）
  - `confidence: float` — 置信度 [0.0, 1.0]
  - `extraction_source: str` — 来源（"rule" / "llm" / "hybrid"）
  - `metadata: dict` — 额外元数据（位置、频率等）
  - `normalized_name: str = ""` — 归一化名称（可选）

- [ ] `ExtractedRelation` frozen dataclass
  - 字段: `source: str` — 源实体名称
  - `target: str` — 目标实体名称
  - `relation_type: str` — 关系类型（MENTIONS / DEPENDS_ON / RELATES_TO / PART_OF / INFLUENCES / CONTRADICTS）
  - `confidence: float` — 置信度 [0.0, 1.0]
  - `extraction_source: str` — 来源（"rule" / "llm" / "hybrid"）
  - `metadata: dict` — 额外元数据

> **⚠️ 字段命名约束：** `ExtractedRelation.source` 专指**源实体名称**（与 `target` 配对），
> 来源标识（"rule"/"llm"/"hybrid"）必须使用 `extraction_source` 字段，避免与 `source` 语义冲突。
> `ExtractedEntity` 同样使用 `extraction_source` 表示来源，保持两个值对象命名一致。

- [ ] `ExtractionResult` frozen dataclass
  - 字段: `entities: tuple[ExtractedEntity, ...]` — 抽取的实体列表
  - `relations: tuple[ExtractedRelation, ...]` — 抽取的关系列表
  - `extraction_metadata: dict` — 抽取元数据（耗时、策略、token 消耗等）

#### 统一端口定义注册与管理 (Port Contract)

**新建端口：**
- [ ] `EntityExtractionPort`（`src/domain/ports/entity_extraction.py`）
  - 方法: `async extract_entities(content: str, domain_context: dict | None = None) -> ExtractionResult`
  - 版本: v1.0.0, owner: foundation-team
  - 端口契约测试: `tests/contracts/test_port_contract_entity_extraction.py`

**端口契约清单（强制）：**

| 端口名称 | 版本 | Owner | 注册 | 解析 | 契约测试 | 状态 |
|---------|------|-------|------|------|---------|------|
| EntityExtractionPort | v1.0.0 | foundation-team | 新建（2个实现：entity_extraction_rule + entity_extraction_llm） | 新建 | 新建 | **新建** |
| ConflictArbitrator | v1.0.0 | foundation-team | 新建（conflict_arbitrator） | 新建 | 新建 | **新建** |
| EntityExtractionService | v1.0.0 | foundation-team | 新建（entity_extraction_service） | 新建 | 新建 | **新建** |

#### 领域异常契约 (Domain Exception Contract)

**新建异常类（`src/domain/exceptions/entity_extraction_exceptions.py`）：**

| 异常类 | 编码 | 继承 | HTTP 映射 | 说明 |
|--------|------|------|-----------|------|
| `EntityExtractionError` | EXCEPTION_340 | `ExternalException` | 500 | 实体抽取失败（规则引擎/LLM 调用/仲裁异常）。继承 `ExternalException` 理由：与 `LLMConfigError(332)`→`ExternalException` 一致，属于外部抽取服务异常。HTTP 500 理由：服务端处理失败 |

**编码分配验证：**
- `external` 子域范围：301-399 ✅
- `embedding` 306-308, `sandbox` 309-319, `ocr` 320-329, `llm` 330-339
- **实体抽取分配 340** — 紧接 LLM 之后，预留 340-349 范围
- 运行 `grep -r "EXCEPTION_34[0-9]" src/domain/exceptions/` 确认无碰撞

- [ ] 归属模块与基类 — 实体抽取属于外部抽取服务，继承 `ExternalException`
- [ ] 唯一编码分配 — 340，确认无碰撞
- [ ] 构造器参数设计 — 携带 `content_preview`、`extraction_strategy`、`entity_count` 等上下文
  - `content_preview` 应截断至 200 字符（对标 OCR 的 `response_body[:200]` 模式），避免在 context 中泄露完整内容
  - 建议添加 `content_preview_truncated: bool` 标记，指示是否被截断
- [ ] 编码注册 — 在 `_code_ranges.py` 的 `_CLASS_TO_SUBDOMAIN` 中注册；新增 `entity_extraction` 子域范围 (340, 349)
- [ ] 导出完整性 — `__init__.py` + `EXCEPTION_HTTP_MAP`
- [ ] 测试覆盖 — 构造/`to_dict()`/HTTP 映射/编码唯一性

#### 六边形架构约束（必须遵守）

> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 本 Story 职责 |
|------|------|-------------|
| domain | `src/domain/` | EntityExtractionPort + 值对象 + EntitiesExtracted 事件 + 实体抽取异常 |
| application | `src/application/` | EntityExtractionService 编排（规则+LLM+仲裁+持久化+事件发布） |
| infrastructure | `src/infrastructure/` | RuleBasedExtractor + LLMEntityExtractor + ConflictArbitrator + Neo4j 持久化 |
| interfaces | `src/interfaces/` | 无新增（本 Story 专注后端能力） |

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | infrastructure |
|------------|--------|-------------|----------------|
| **domain (EntityExtractionPort)** | — | ✗ 禁止 | ✗ 禁止 |
| **application (EntityExtractionService)** | ✓ 允许 | — | ✗ 禁止 |
| **infrastructure (RuleBasedExtractor)** | ✓ 允许 | ✓ 允许 | — |

**领域层零依赖原则** — `src/domain/ports/entity_extraction.py` 仅依赖：
- Python 标准库（`dataclasses`, `uuid`, `typing`）
- `typing.Protocol` / `@runtime_checkable`
- 领域值对象（`ExtractedEntity`, `ExtractedRelation`, `ExtractionResult`）
- 不依赖：`pydantic`, `litellm`, `pyahocorasick`, `neo4j`

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_entity_extraction.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_entity_extraction.py`
- [ ] 业务方评审通过
- [ ] 覆盖场景:
  - Happy Path: 混合实体抽取成功（规则+LLM 融合）
  - Happy Path: 纯规则基抽取（无 LLM 配置）
  - Happy Path: 抽取结果通过 L5GraphPort 写入 Neo4j
  - Edge Case: 空内容输入返回空结果
  - Edge Case: LLM 调用失败降级至规则基结果
  - Edge Case: 无匹配实体返回空结果

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
| **TDD 单元测试** | EntityExtractionPort + 值对象 | 端口契约、值对象构造、工厂方法 | `test_entity_extraction_port.py` | Task 1 |
| **TDD 单元测试** | EntitiesExtracted 事件 | 事件构造、序列化、注册 | `test_entity_extraction_events.py` | Task 1 |
| **TDD 单元测试** | 实体抽取异常 | 构造/属性/to_dict()/HTTP 映射 | `test_entity_extraction_exceptions.py` | Task 1 |
| **TDD 单元测试** | RuleBasedExtractor | AC 自动机匹配、正则匹配、准确率 | `test_rule_extractor.py` | Task 2 |
| **TDD 单元测试** | LLMEntityExtractor | LLM 调用、降级、Schema 验证 | `test_llm_extractor.py` | Task 2 |
| **TDD 单元测试** | ConflictArbitrator | 权重融合、去重、置信度排序 | `test_conflict_arbitrator.py` | Task 2 |
| **TDD 单元测试** | EntityExtractionService | 编排流程、异常处理、事件发布 | `test_entity_extraction_service.py` | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_entity_extraction.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_entity_extraction.py` | Task 0 |
| **TDD 契约测试** | EntityExtractionPort | 端口注册/解析/契约门禁 | `test_port_contract_entity_extraction.py` | Task 0 |
| **TDD 领域异常测试** | 实体抽取异常 | 编码唯一性/子域范围 | `test_error_code_uniqueness.py` + `test_code_ranges.py` | Task 1 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖 | `test_arch_entity_extraction.py` | Task 4 |
| **集成测试** | 实体抽取管线 | 端到端抽取流程 | `test_integration_entity_extraction.py` | Task 4 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain/ports/entity_extraction.py`）
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application/services/entity_extraction_service.py`）
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure/external_services/entity_extraction/`）
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration/test_integration_entity_extraction.py`）

> ⚠️ **骨架 Story 覆盖率豁免：** 本 Story 为基础设施层实现，非骨架 Story，需达到标准覆盖率要求。

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **外部服务隔离** | LLM API 使用 aiohttp 本地 HTTP 服务器（参照 Story 3.2a 集成测试模式），Neo4j 使用 AsyncMock(spec=L5GraphPort) | 真实调用导致失败 |
| **配置隔离** | 每个测试使用独立的提取配置实例 | 配置污染 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突 |
| **BDD async 配合** | BDD 步骤函数用 event_loop.run_until_complete() | context 数据丢失 |

**验证要求：**
- [ ] 并行测试 `poetry run pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 实体抽取端口契约（EntityExtractionPort + 值对象） | Task 1 | Subtask 1.1-1.3 | `test_entity_extraction_port.py` |
| AC-2 | EntitiesExtracted 领域事件 | Task 1 | Subtask 1.2 | `test_entity_extraction_events.py` |
| AC-3 | 实体抽取异常体系（EntityExtractionError） | Task 1 | Subtask 1.4-1.6 | `test_entity_extraction_exceptions.py` |
| AC-4 | 规则基实体抽取（AC 自动机 + 正则） | Task 2 | Subtask 2.1-2.3 | `test_rule_extractor.py` |
| AC-5 | LLM 语义实体抽取（LLMClientPort） | Task 2 | Subtask 2.4-2.6 | `test_llm_extractor.py` |
| AC-6 | 冲突仲裁器（规则+LLM 融合） | Task 2 | Subtask 2.7-2.9 | `test_conflict_arbitrator.py` |
| AC-7 | 应用层实体抽取编排服务 | Task 3 | Subtask 3.1-3.3 | `test_entity_extraction_service.py` |
| AC-8 | 端口注册与 DI 集成 | Task 4 | Subtask 4.1-4.3 | `test_port_contract_entity_extraction.py` |
| AC-8 | 架构约束验证 + 集成测试 | Task 4 | Subtask 4.4-4.6 | `test_arch_entity_extraction.py` + `test_integration_entity_extraction.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 定义实体抽取端口契约（EntityExtractionPort/ExtractedEntity/ExtractedRelation/ExtractionResult）设计
- [ ] Subtask 0.2: 定义 EntitiesExtracted 领域事件设计
- [ ] Subtask 0.3: 定义实体抽取异常体系设计（EntityExtractionError）
- [ ] Subtask 0.4: 定义 `_code_ranges.py` 新增 `entity_extraction` 子域（340-349）
- [ ] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_entity_extraction.feature`
- [ ] Subtask 0.6: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_entity_extraction.py`
- [ ] Subtask 0.7: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 领域层端口 + 事件 + 值对象 + 异常（领域层）

**关联 AC:** AC-1, AC-2, AC-3

> **领域层零外部依赖：** 本 Task 所有代码位于 `src/domain/`，仅使用 Python 标准库。
> 禁止导入：pydantic, litellm, pyahocorasick, neo4j 等任何第三方库。

#### TDD 循环 [A]：EntityExtractionPort + 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_entity_extraction_port.py`（端口契约 + 值对象构造） |
| 🟢 绿 | 实现 `src/domain/ports/entity_extraction.py`（EntityExtractionPort + 值对象） |
| 🔄 重构 | 优化类型注解，运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 EntityExtractionPort 失败测试
  - `ExtractedEntity` frozen dataclass 构造（所有字段默认值正确）
  - `ExtractedRelation` frozen dataclass 构造
  - `ExtractionResult` frozen dataclass 构造
  - `EntityExtractionPort` Protocol 结构验证（`extract_entities()` 方法签名）
  - `@runtime_checkable` 可用
- [ ] Subtask 1.2: 🟢 绿 — 实现 EntityExtractionPort + 值对象
- [ ] Subtask 1.3: 🔄 重构 — 优化代码，运行 `ruff` + `mypy`

#### TDD 循环 [B]：EntitiesExtracted 领域事件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/events/test_entity_extraction_events.py`（事件构造 + 序列化 + 注册） |
| 🟢 绿 | 实现 `src/domain/events/entity_extraction_events.py`（EntitiesExtracted 事件） |
| 🔄 重构 | 更新 `__init__.py` + 事件注册，运行 `ruff` + `mypy` |

- [ ] Subtask 1.4: 🔴 红 — 编写 EntitiesExtracted 事件失败测试
  - `EntitiesExtracted` 继承 `DomainEvent`，关键字段（memory_id, entity_count, relation_count）
  - 事件自动注册到 `_registry`
  - `to_dict()` / `from_dict()` 序列化正确
- [ ] Subtask 1.5: 🟢 绿 — 实现 EntitiesExtracted 事件
- [ ] Subtask 1.6: 🔄 重构 — 运行 `ruff` + `mypy`

#### TDD 循环 [C]：实体抽取异常体系

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_entity_extraction_exceptions.py`（异常构造 + to_dict + HTTP 映射） |
| 🟢 绿 | 实现 `src/domain/exceptions/entity_extraction_exceptions.py`（EntityExtractionError） |
| 🔄 重构 | 更新 `__init__.py` + `_code_ranges.py` + `EXCEPTION_HTTP_MAP`，运行 `ruff` + `mypy` |

- [ ] Subtask 1.7: 🔴 红 — 编写实体抽取异常失败测试
  - `EntityExtractionError` 构造（含 content_preview, extraction_strategy, entity_count 上下文）
  - `to_dict()` 序列化正确（含 cause 链）
  - HTTP 映射正确（340→500）
  - 编码唯一性（`test_error_code_uniqueness.py` 中确认无碰撞）
  - 子域范围（`test_code_ranges.py` 中新增 entity_extraction 子域）
- [ ] Subtask 1.8: 🟢 绿 — 实现实体抽取异常类
  - 创建 `src/domain/exceptions/entity_extraction_exceptions.py`
  - 更新 `src/domain/exceptions/__init__.py` 导出
  - 更新 `src/domain/exceptions/_code_ranges.py` 新增 `entity_extraction` 子域 (340, 349)
  - 更新 `src/interfaces/api/exception_handlers.py` 的 `EXCEPTION_HTTP_MAP`
- [ ] Subtask 1.9: 🔄 重构 — 运行 `ruff check` + `mypy` + `pytest tests/unit/domain/exceptions/ -v`

**完成标准/Definition of Done:**
- [ ] EntityExtractionPort + 值对象实现完成
- [ ] EntitiesExtracted 领域事件实现完成
- [ ] EntityExtractionError 异常实现完成
- [ ] TDD 循环全部通过
- [ ] 编码无碰撞验证通过
- [ ] 领域层覆盖率≥90%

---

### Task 2: 基础设施层实体抽取组件实现

**关联 AC:** AC-4, AC-5, AC-6

> **基础设施层依赖：** 本 Task 代码位于 `src/infrastructure/`，可使用 pyahocorasick、re、litellm 等第三方库。
> **⚠️ 依赖前置条件：** `pyahocorasick` 当前**未安装**（非任何依赖的传递依赖）。实施前**必须**在 `pyproject.toml` 显式声明并安装 `pyahocorasick`（`poetry add pyahocorasick@^2.1.0`），否则 `import pyahocorasick` 会失败。
> **规则基参考：** or.md §二.3 明确使用 pyahocorasick 构建 AC 自动机。
> **LLM 调用：** 通过 Story 3.2a 的 `LLMClientPort`，不使用裸 httpx。

#### TDD 循环 [A]：RuleBasedExtractor（AC 自动机 + 正则）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/entity_extraction/test_rule_extractor.py` |
| 🟢 绿 | 实现 `src/infrastructure/external_services/entity_extraction/rule_extractor.py` |
| 🔄 重构 | 优化匹配逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 2.1: 🔴 红 — 编写 RuleBasedExtractor 失败测试
  - **Happy Path:** AC 自动机匹配战略领域实体（"市场增长率"、"PESTEL"、"SWOT"等）
  - **Happy Path:** 正则匹配结构化实体（"2024 年"、"15%"、"¥100 亿"等）
  - **Happy Path:** 多实体同时匹配
  - **Edge Case:** 无匹配内容返回空列表
  - **Edge Case:** 空字符串输入返回空列表
  - **Edge Case:** 词典热更新后匹配新实体
  - **准确率验证:** 预定义测试集准确率≥80%
  - **内置词典:** 验证基础战略领域词典包含: 战略管理(BLM/BEM/SWOT/PESTEL 等)、财务(NPV/IRR/ROI 等)、市场(市场份额/增长率/竞争等)、技术(AI/云计算/大数据等)
- [ ] Subtask 2.2: 🟢 绿 — 实现 RuleBasedExtractor
  - AC 自动机构建器（`pyahocorasick.Automaton`）
  - 正则模式集合（日期、金额、百分比、联系方式等）
  - 内置基础战略领域词典（~100+ 核心词条）
  - 词典热更新支持（`reload_dictionary()`）
  - 匹配结果转为 `ExtractedEntity` 值对象
- [ ] Subtask 2.3: 🔄 重构 — 优化代码，运行 `ruff` + `mypy`

#### TDD 循环 [B]：LLMEntityExtractor（LLM 语义抽取）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/entity_extraction/test_llm_extractor.py` |
| 🟢 绿 | 实现 `src/infrastructure/external_services/entity_extraction/llm_extractor.py` |
| 🔄 重构 | 优化提示策略，运行 `ruff` + `mypy` |

- [ ] Subtask 2.4: 🔴 红 — 编写 LLMEntityExtractor 失败测试
  - **Happy Path:** `LLMClientPort.structured_generate()` 成功返回实体和关系
  - **Happy Path:** 返回的 Pydantic 对象正确转换为 `ExtractionResult`
  - **Edge Case:** LLM 调用失败（`LLMAPIError`）→ 返回空结果（透明降级）
  - **Edge Case:** LLM 返回空实体列表 → 返回空结果
  - **Edge Case:** Schema 验证失败 → 降级至空结果
  - **召回率验证:** 模拟 LLM 返回结果，验证正确解析
- [ ] Subtask 2.5: 🟢 绿 — 实现 LLMEntityExtractor
  - 实现 `EntityExtractionPort` 接口（`extract_entities(content, domain_context?)`）
  - 构造函数注入 `LLMClientPort` 调用 `structured_generate()`
  - 定义 `EntityExtractionSchema`（Pydantic BaseModel，结构化输出 Schema）
  - Few-Shot 提示模板（含 3-5 个示例）
  - CoT 推理步骤提示
  - 错误处理：LLM 失败时返回空结果（非抛出异常，由编排层决策）
  - 匹配结果映射为 `ExtractedEntity` / `ExtractedRelation` 值对象（`extraction_source="llm"`）
- [ ] Subtask 2.6: 🔄 重构 — 运行 `ruff` + `mypy`

#### TDD 循环 [C]：ConflictArbitrator（规则+LLM 融合）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/entity_extraction/test_conflict_arbitrator.py` |
| 🟢 绿 | 实现 `src/infrastructure/external_services/entity_extraction/conflict_arbitrator.py` |
| 🔄 重构 | 优化融合算法，运行 `ruff` + `mypy` |

- [ ] Subtask 2.7: 🔴 红 — 编写 ConflictArbitrator 失败测试
  - **Happy Path:** 规则+LLM 相同实体融合（置信度加权平均）
  - **Happy Path:** 规则+LLM 不同实体合并（保留两者）
  - **Happy Path:** 按实体类型差异化权重（默认 0.6/0.4，可配置）
  - **Edge Case:** 仅规则基结果（无 LLM 结果）→ 直接返回规则结果
  - **Edge Case:** 仅 LLM 结果（无规则结果）→ 直接返回 LLM 结果
  - **Edge Case:** 两者均为空 → 返回空结果
  - **Edge Case:** 同一实体置信度冲突 → 采用置信度加权平均（规则权重 0.6 / LLM 权重 0.4）
  - **关系融合:** 规则基关系 + LLM 语义关系去重合并
  - **仲裁准确率:** 预定义测试集准确率≥85%
- [ ] Subtask 2.8: 🟢 绿 — 实现 ConflictArbitrator
  - 实体合并策略（按名称归一化匹配）
  - 置信度加权平均公式
  - 关系去重合并
  - 可配置权重（按实体类型）
- [ ] Subtask 2.9: 🔄 重构 — 运行 `ruff` + `mypy`

**完成标准/Definition of Done:**
- [ ] RuleBasedExtractor 实现完成（AC 自动机 + 正则 + 内置词典）
- [ ] LLMEntityExtractor 实现完成（LLMClientPort + 提示模板 + 降级）
- [ ] ConflictArbitrator 实现完成（权重融合 + 去重）
- [ ] TDD 循环全部通过
- [ ] 基础设施层覆盖率≥75%

---

### Task 3: 应用层实体抽取编排服务

**关联 AC:** AC-7

> **应用层编排：** 本 Task 实现 `EntityExtractionService`，编排规则基→LLM→仲裁→持久化→事件发布完整流程。

#### TDD 循环 [A]：EntityExtractionService 编排

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_entity_extraction_service.py` |
| 🟢 绿 | 实现 `src/application/services/entity_extraction_service.py` |
| 🔄 重构 | 优化编排逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 3.1: 🔴 红 — 编写 EntityExtractionService 失败测试
  - **Happy Path:** 完整流程执行（规则→LLM→仲裁→持久化→事件发布）
  - **Happy Path:** 抽取结果正确写入 Neo4j（调用 `L5GraphPort.create_entity()` 和 `create_relationship()`）
  - **Happy Path:** 发布 `EntitiesExtracted` 事件（含 entity_count, relation_count）
  - **Edge Case:** LLM 调用失败 → 降级至仅规则基结果
  - **Edge Case:** 空内容输入 → 返回空 `ExtractionResult`（不抛出异常）
  - **Edge Case:** 规则基返回空 → 仅使用 LLM 结果
  - **Edge Case:** 持久化失败 → 抛出 `EntityExtractionError`
  - **Edge Case:** 事件发布失败 → 记录日志（不阻止主流程）
- [ ] Subtask 3.2: 🟢 绿 — 实现 EntityExtractionService
  - 构造函数注入: `rule_extractor`（EntityExtractionPort）、`llm_extractor`（EntityExtractionPort）、`l5_graph`（L5GraphPort）、`arbitrator`（ConflictArbitrator）、`event_publisher`
  - 编排流程：
    1. 规则基抽取 → `rule_result`
    2. LLM 语义抽取 → `llm_result`（失败时透明降级）
    3. 冲突仲裁 → `final_result`
    4. Neo4j 持久化（实体 + 关系）
    5. 事件发布
  - 返回 `ExtractionResult` 完整结果
- [ ] Subtask 3.3: 🔄 重构 — 运行 `ruff` + `mypy`

**完成标准/Definition of Done:**
- [ ] EntityExtractionService 实现完成（完整编排流程）
- [ ] TDD 循环全部通过
- [ ] 应用层覆盖率≥85%

---

### Task 4: 端口注册 + 架构验证 + 集成测试

**关联 AC:** AC-8

> **性质说明：** 本 Task 包含 DI 注册、端口契约测试、架构约束验证和集成测试。

#### 端口注册与 DI 集成

- [ ] Subtask 4.1: 更新 `src/domain/ports/__init__.py` 导出 `EntityExtractionPort`、`ExtractedEntity`、`ExtractedRelation`、`ExtractionResult`
- [ ] Subtask 4.2: 更新 `src/composition_root.py` 注册相关端口
  ```python
  # 注册规则基实体抽取器（RuleBasedExtractor 实现 EntityExtractionPort）
  register_port(
      name="entity_extraction_rule",
      version="v1.0.0",
      interface=EntityExtractionPort,
      impl=lambda resolver: RuleBasedExtractor(
          builtin_dictionary=create_builtin_dictionary(),
      ),
      module="src.infrastructure.external_services.entity_extraction.rule_extractor",
      lifetime=Lifetime.SINGLETON,  # 热更新语义要求词典全局共享
      owner="foundation-team",
      tags=("entity_extraction", "rule", "nlp"),
  )

  # 注册 LLM 语义实体抽取器（LLMEntityExtractor 实现 EntityExtractionPort）
  register_port(
      name="entity_extraction_llm",
      version="v1.0.0",
      interface=EntityExtractionPort,
      impl=lambda resolver: LLMEntityExtractor(
          llm_client=resolver.resolve("llm_client"),
      ),
      module="src.infrastructure.external_services.entity_extraction.llm_extractor",
      lifetime=Lifetime.SCOPED,
      owner="foundation-team",
      tags=("entity_extraction", "llm"),
  )

  # 注册冲突仲裁器
  register_port(
      name="conflict_arbitrator",
      version="v1.0.0",
      interface=ConflictArbitrator,
      impl=lambda resolver: ConflictArbitrator(),
      module="src.infrastructure.external_services.entity_extraction.conflict_arbitrator",
      lifetime=Lifetime.SCOPED,
      owner="foundation-team",
      tags=("entity_extraction", "arbitrator"),
  )

  # 注册 EntityExtractionService 应用服务（注入所需的端口）
  register_port(
      name="entity_extraction_service",
      version="v1.0.0",
      interface=EntityExtractionService,
      impl=lambda resolver: EntityExtractionService(
          rule_extractor=resolver.resolve("entity_extraction_rule"),
          llm_extractor=resolver.resolve("entity_extraction_llm"),
          l5_graph=resolver.resolve("l5_graph"),
          arbitrator=resolver.resolve("conflict_arbitrator"),
          event_publisher=resolver.resolve("event_publisher"),
      ),
      module="src.application.services.entity_extraction_service",
      lifetime=Lifetime.SCOPED,
      owner="foundation-team",
      tags=("entity_extraction", "service"),
  )
  ```
  - 生命周期: `entity_extraction_rule` 为 SINGLETON（热更新语义要求词典全局共享），其余为 SCOPED
  - Owner: foundation-team
  - 注意：RuleBasedExtractor 和 LLMEntityExtractor 各自实现 EntityExtractionPort，分别注册为独立端口。EntityExtractionService 通过 resolver 注入所有依赖。

#### 端口契约测试

- [ ] Subtask 4.3: 创建 `tests/contracts/test_port_contract_entity_extraction.py`
  - 验证 `entity_extraction_rule` 端口已注册到 Registry
  - 验证 `entity_extraction_llm` 端口已注册到 Registry
  - 验证 `conflict_arbitrator` 端口已注册到 Registry
  - 验证 `entity_extraction_service` 端口已注册到 Registry
  - 验证 `Resolver` 可解析各端口
  - 验证 `EntityExtractionPort` 方法签名正确

#### 架构验证测试

- [ ] Subtask 4.4: 创建 `tests/unit/architecture/test_arch_entity_extraction.py`
  - 验证 `src/domain/ports/entity_extraction.py` 零外部依赖（仅标准库）
  - 验证 `EntityExtractionPort` 位于领域层
  - 验证 `RuleBasedExtractor` 位于基础设施层
  - 验证依赖方向正确（infrastructure → domain）

#### 集成测试

- [ ] Subtask 4.5: 创建 `tests/integration/test_integration_entity_extraction.py`
  - 端到端：实体抽取完整流程（使用真实 AC 自动机规则基抽取 + aiohttp 本地 HTTP 服务器模拟 LLM API）
  - 规则基 + LLM 混合抽取（参照 Story 3.2a 集成测试的 aiohttp 模式）
  - 冲突仲裁逻辑
  - Neo4j 持久化调用验证（通过 Mock L5GraphPort）
  - 异常链路（EntityExtractionError 抛出）

**完成标准/Definition of Done:**
- [ ] `composition_root.py` 注册 `entity_extraction_rule` / `entity_extraction_llm` / `conflict_arbitrator` / `entity_extraction_service` 端口
- [ ] 端口契约测试通过
- [ ] 所有架构约束测试通过
- [ ] 集成测试通过
- [ ] 领域层零外部依赖

---

### Task 5: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8

> **性质说明：** 本 Task 是对 Story 收尾阶段的交付物与完成清单进行最终验收。

- [ ] Subtask 5.1: 场景 1 — 验证 `src` 完成清单的逐项确认
  - `src/domain/ports/entity_extraction.py` — EntityExtractionPort + 值对象
  - `src/domain/events/entity_extraction_events.py` — EntitiesExtracted 事件
  - `src/domain/exceptions/entity_extraction_exceptions.py` — EntityExtractionError
  - `src/domain/exceptions/__init__.py` — 导出实体抽取异常
  - `src/domain/exceptions/_code_ranges.py` — 新增 entity_extraction 子域
  - `src/domain/ports/__init__.py` — 导出 EntityExtractionPort
  - `src/domain/events/__init__.py` — 导出 EntitiesExtracted
  - `src/infrastructure/external_services/entity_extraction/rule_extractor.py` — RuleBasedExtractor
  - `src/infrastructure/external_services/entity_extraction/llm_extractor.py` — LLMEntityExtractor
  - `src/infrastructure/external_services/entity_extraction/conflict_arbitrator.py` — ConflictArbitrator
  - `src/application/services/entity_extraction_service.py` — EntityExtractionService
  - `src/composition_root.py` — 注册 entity_extraction_rule / entity_extraction_llm / conflict_arbitrator / entity_extraction_service 端口
- `src/interfaces/api/exception_handlers.py` — EXCEPTION_HTTP_MAP 更新
- `configs/event_channels.yaml` — 新增 EntitiesExtracted 事件通道
- `src/infrastructure/messaging/channel_router.py` — DEFAULT_MAPPINGS 新增 EntitiesExtracted
- [ ] Subtask 5.2: 场景 2 — 验证 `tests/unit`、`tests/contracts`、`tests/acceptance` 完成清单
  - `tests/unit/domain/ports/test_entity_extraction_port.py`
  - `tests/unit/domain/events/test_entity_extraction_events.py`
  - `tests/unit/domain/exceptions/test_entity_extraction_exceptions.py`
  - `tests/unit/infrastructure/external_services/entity_extraction/test_rule_extractor.py`
  - `tests/unit/infrastructure/external_services/entity_extraction/test_llm_extractor.py`
  - `tests/unit/infrastructure/external_services/entity_extraction/test_conflict_arbitrator.py`
  - `tests/unit/application/services/test_entity_extraction_service.py`
  - `tests/unit/architecture/test_arch_entity_extraction.py`
  - `tests/contracts/test_port_contract_entity_extraction.py`
  - `tests/integration/test_integration_entity_extraction.py`
  - `tests/acceptance/test_acceptance_entity_extraction.feature`
  - `tests/acceptance/test_acceptance_entity_extraction.py`
- [ ] Subtask 5.3: 运行开发结束验收测试并确认通过
- [ ] Subtask 5.4: 运行 `poetry run pytest --tb=short -q`、`poetry run ruff check src/`、`poetry run mypy src/`

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 实体抽取架构设计

**核心架构模式：流水线编排（Pipeline Orchestration）**

```
输入文本内容
    │
    ├─→ 规则基抽取（AC 自动机 + 正则）
    │   └─→ ExtractedEntity[] (rule)
    │
    ├─→ LLM 语义抽取（LLMClientPort.structured_generate）
    │   └─→ ExtractedEntity[] (llm)
    │
    └─→ 冲突仲裁器（ConflictArbitrator）
        │
        ├─→ 实体合并（按名称归一化匹配）
        ├─→ 置信度加权平均（规则权重 0.6 / LLM 权重 0.4）
        └─→ 关系去重合并
            │
            ▼
        ExtractionResult（最终输出）
            │
            ├─→ L5GraphPort 持久化（Neo4j MERGE 语义）
            └─→ EntitiesExtracted 事件发布
```

### 与 Story 3.2a LLMClientPort 的集成

**LLM 调用通过 Story 3.2a 的 `LLMClientPort`，不直接使用 httpx/litellm：**

```
LLMEntityExtractor
    │
    ├─→ 注入 LLMClientPort
    ├─→ 构造 EntityExtractionSchema（Pydantic BaseModel）
    ├─→ 构建 Few-Shot + CoT 提示模板
    └─→ 调用 structured_generate(prompt, EntityExtractionSchema, config)
        │
        ├─→ 成功 → 解析为 ExtractionResult
        └─→ 失败 → 返回空结果（透明降级）
```

**LLM 抽取 Schema 设计（EntityExtractionSchema）：**

```python
from pydantic import BaseModel, Field

class ExtractedEntitySchema(BaseModel):
    """单个实体 Schema"""
    name: str = Field(description="实体名称")
    entity_type: str = Field(description="实体类型: PERSON/ORG/LOC/PRODUCT/CONCEPT/DATE/AMOUNT/PERCENT")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")

class ExtractedRelationSchema(BaseModel):
    """单个关系 Schema"""
    source: str = Field(description="源实体名称")
    target: str = Field(description="目标实体名称")
    relation_type: str = Field(description="关系类型: MENTIONS/DEPENDS_ON/RELATES_TO/PART_OF/INFLUENCES/CONTRADICTS")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")

class EntityExtractionSchema(BaseModel):
    """实体抽取结果 Schema"""
    entities: list[ExtractedEntitySchema] = Field(description="抽取的实体列表")
    relations: list[ExtractedRelationSchema] = Field(description="抽取的关系列表")
```

### 与 L5GraphPort 的集成

**持久化通过现有 `L5GraphPort` 接口，复用 Neo4jAdapter 实现：**

```
EntityExtractionService
    │
    └─→ L5GraphPort.create_entity(memory_id, entity_type, properties)
    │   └─→ MERGE (n:Memory {id: $memory_id}) SET n.type = $entity_type, ...
    │
    └─→ L5GraphPort.create_relationship(source, target, rel_type, properties)
        └─→ MATCH (s:Memory {id: $source}), (t:Memory {id: $target})
             MERGE (s)-[r:REL_TYPE]->(t) SET ...
```

**持久化策略关键约束：**
- `create_entity` 的 `memory_id` 是节点唯一主键（MERGE 匹配键），一个抽取实体对应一个独立 node id
- `create_relationship` 的 `relationship_type` 必须符合 Neo4j 命名规范 `[A-Z_][A-Z0-9_]*`（大写蛇形），来自 `RelationshipType` 枚举（MENTIONS/DEPENDS_ON/RELATES_TO/PART_OF/INFLUENCES/CONTRADICTS）
- 抽取的 `relation_type`（来自 `ExtractedRelation`）需映射到 `RelationshipType` 枚举值，非法关系类型会触发 `ValidationError`
- 实体属性键名必须符合 `[a-zA-Z_][a-zA-Z0-9_]*`（`_sanitize_property_keys` 校验），避免 Cypher 注入

**实体类型映射：**
| 抽取实体类型 | Neo4j 标签 | entity_type 属性值 | 说明 |
|-------------|-----------|-------------------|------|
| PERSON | `Memory` | `person` | 人员实体 |
| ORG | `Memory` | `organization` | 组织实体 |
| LOC | `Memory` | `location` | 地点实体 |
| PRODUCT | `Memory` | `product` | 产品实体 |
| CONCEPT | `Memory` | `concept` | 概念/术语实体 |
| DATE | `Memory` | `date` | 日期实体 |
| AMOUNT | `Memory` | `amount` | 金额实体 |
| PERCENT | `Memory` | `percent` | 百分比实体 |
| CONTACT | `Memory` | `contact` | 联系方式实体（电话、邮箱，由正则模式产出） |

> **注意：** `CONTACT` 类型由规则基抽取器的正则模式匹配产出（电话、邮箱），
> 在 `_ENTITY_TYPE_MAP` 中映射为 `contact` 属性值。

> **注意：** `Neo4jAdapter.create_entity()` 使用统一 `Memory` 标签，`entity_type` 作为节点属性 `n.type` 存储。
> 不使用 `Memory:Person` 复合标签。`entity_type` 属性值使用小写蛇形命名。

### 内置战略领域词典设计

**基础词典（~100+ 词条），覆盖核心战略管理领域：**

| 类别 | 示例词条 |
|------|---------|
| 战略管理 | BLM, BEM, SP, BP, 战略规划, 市场洞察, 战略意图, 创新焦点, 业务设计, 执行设计 |
| 战略工具 | PESTEL, SWOT, TOWS, 波特五力, 价值链, VRIO, 安索夫矩阵, GE-麦肯锡矩阵, SPACE 矩阵 |
| 财务指标 | NPV, IRR, ROI, 现金流, 利润率, 资产负债率, 营业收入, 净利润, EBITDA, ROCE |
| 市场概念 | 市场份额, 增长率, 市场规模, 竞争格局, 蓝海, 红海, 差异化, 成本领先 |
| 技术概念 | AI, 人工智能, 云计算, 大数据, 物联网, 区块链, 5G, 数字化转型, SaaS, PaaS |
| 组织角色 | CEO, CFO, CTO, COO, CMO, CHO, 董事会, 高管团队, 事业部, 子公司 |

### 异常流设计

```
RuleBasedExtractor 失败
    │
    └─→ EntityExtractionError(content_preview="...", extraction_strategy="rule", entity_count=0)

LLMEntityExtractor 调用失败
    │
    └─→ 透明降级（返回空结果，不抛出异常）
    │   EntityExtractionService 记录警告日志
    │
    └─→ 继续使用规则基结果

Neo4j 持久化失败
    │
    └─→ EntityExtractionError(content_preview="...", extraction_strategy="hybrid", entity_count=N)
    │   cause = L5GraphPort 异常
    │
    └─→ 事件不发布，返回 ExtractionResult（含抽取结果但不含持久化确认）
```

### 依赖配置

**新增依赖（pyproject.toml）：**
- `pyahocorasick` — AC 自动机实现（⚠️ 当前**未安装**，**不是任何已有依赖的传递依赖**，需在 `pyproject.toml` 显式声明并执行 `poetry add pyahocorasick@^2.1.0`）

**需确认的依赖：**
- `pyahocorasick` 版本选择：最新稳定版（^2.1.0）

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（端口与适配器）+ 流水线编排
- **设计约束:**
  - 领域层零外部依赖（`EntityExtractionPort` 仅使用 Python 标准库）
  - 依赖倒置：领域层定义 `EntityExtractionPort`，基础设施层实现
  - LLM 调用通过 `LLMClientPort`（Story 3.2a），不直接使用 httpx/litellm
  - Neo4j 持久化通过 `L5GraphPort`（Story 1.8），不直接使用 neo4j driver
- **技术栈:**
  - Python 3.11+
  - pyahocorasick（⚠️ 当前**未安装**，需在 `pyproject.toml` 显式声明后 `poetry add pyahocorasick@^2.1.0`）
  - re（Python 标准库）
  - litellm（通过 LLMClientPort 间接使用）

### 关键架构决策

**来源:** architecture.md §17.1（数据处理架构）, or.md §二.3.(2)

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **AC 自动机（pyahocorasick）+ 正则 + LLM 混合** | 准确率高（规则≥80%）、召回率高（LLM≥90%）、符合架构设计 | 实现复杂度中等 | ✅ 8/10 |
| 纯规则基（AC 自动机 + 正则） | 实现简单、速度快 | 召回率低、无法处理语义实体 | 5/10 |
| 纯 LLM 语义抽取 | 召回率高、灵活 | 成本高、准确率不稳定 | 5/10 |
| 纯基于 spaCy/NLTK 的 NLP 流水线 | 生态成熟 | 需额外依赖、领域适应差 | 4/10 |

### 已有可复用组件

| 组件 | 文件路径 | 说明 |
|------|---------|------|
| LLMClientPort | `src/domain/ports/llm_client.py` | Story 3.2a 提供，用于 LLM 语义抽取 |
| L5GraphPort | `src/domain/ports/l5_graph.py` | Story 1.8 提供，用于 Neo4j 持久化 |
| Neo4jAdapter | `src/infrastructure/storage/neo4j/neo4j_adapter.py` | L5GraphPort 实现 |
| MemoryGraphPort | `src/application/ports/memory_graph_port.py` | 扩展 L5GraphPort，含 `index_memory_relations()` 桩方法 |
| RelationshipType | `src/infrastructure/storage/neo4j/models.py` | 关系类型枚举（MENTIONS/DEPENDS_ON/RELATES_TO 等） |
| L1TextExtractor | `src/application/use_cases/text_processing/l1_text_extractor.py` | 参考模式：规则基文本提取 |

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── ports/
│   │   │   ├── __init__.py                    # 更新：导出 EntityExtractionPort
│   │   │   └── entity_extraction.py           # 新建：EntityExtractionPort + 值对象
│   │   ├── events/
│   │   │   ├── __init__.py                    # 更新：导出 EntitiesExtracted
│   │   │   └── entity_extraction_events.py    # 新建：EntitiesExtracted 事件
│   │   └── exceptions/
│   │       ├── __init__.py                    # 更新：导出 EntityExtractionError
│   │       ├── _code_ranges.py                # 更新：新增 entity_extraction 子域
│   │       └── entity_extraction_exceptions.py # 新建：EntityExtractionError
│   ├── application/
│   │   └── services/
│   │       └── entity_extraction_service.py   # 新建：EntityExtractionService 编排
│   ├── infrastructure/
│   │   └── external_services/
│   │       └── entity_extraction/             # 新建目录
│   │           ├── __init__.py                # 新建：模块导出
│   │           ├── rule_extractor.py          # 新建：RuleBasedExtractor（AC 自动机+正则）
│   │           ├── llm_extractor.py           # 新建：LLMEntityExtractor（LLM 语义）
│   │           └── conflict_arbitrator.py     # 新建：ConflictArbitrator（融合仲裁）
│   ├── interfaces/
│   │   └── api/
│   │       └── exception_handlers.py          # 更新：EXCEPTION_HTTP_MAP 新增
│   └── composition_root.py                    # 更新：注册 entity_extraction 端口
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── ports/
│   │   │   │   └── test_entity_extraction_port.py    # 新建：端口 + 值对象测试
│   │   │   ├── events/
│   │   │   │   └── test_entity_extraction_events.py  # 新建：事件测试
│   │   │   └── exceptions/
│   │   │       └── test_entity_extraction_exceptions.py # 新建：异常测试
│   │   ├── application/
│   │   │   └── services/
│   │   │       └── test_entity_extraction_service.py  # 新建：服务测试
│   │   └── infrastructure/
│   │       └── external_services/
│   │           └── entity_extraction/
│   │               ├── test_rule_extractor.py          # 新建：规则基测试
│   │               ├── test_llm_extractor.py           # 新建：LLM 抽取测试
│   │               └── test_conflict_arbitrator.py     # 新建：仲裁测试
│   ├── contracts/
│   │   └── test_port_contract_entity_extraction.py     # 新建：端口契约测试
│   ├── integration/
│   │   └── test_integration_entity_extraction.py       # 新建：集成测试
│   └── acceptance/
│       ├── test_acceptance_entity_extraction.feature   # 新建：Gherkin 验收测试
│       └── test_acceptance_entity_extraction.py        # 新建：BDD 步骤实现
```

### 环境变量设计

本 Story 复用 Story 3.2a 的 LLM 配置，无需新增环境变量。如需独立配置 LLM 模型：

```bash
# 实体抽取 LLM 配置（可选，默认使用 LLMClientPort 默认配置）
export ENTITY_EXTRACTION_MODEL=qwen2.5:7b       # 实体抽取专用模型
export ENTITY_EXTRACTION_TEMPERATURE=0.1          # 低温度保证确定性
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 3.2a: LLM Client 基础设施](./3-2a-llm-client-infrastructure.md)

**关键学习/Key Learnings:**
1. **LLMClientPort 模式** — Story 3.2a 定义了 `LLMClientPort`，本 Story 的 LLM 语义抽取直接复用 `structured_generate()`，不重新实现 LLM 调用逻辑
2. **结构化输出 Schema 设计** — 使用 Pydantic BaseModel 作为 Schema 约束，通过 `structured_generate(response_schema=...)` 确保输出格式可控
3. **异常编码注册流程** — 新异常必须遵循 `_code_ranges.py` → `__init__.py` → `EXCEPTION_HTTP_MAP` 完整注册流程
4. **端口契约测试模式** — 遵循"三方法"测试模式（注册验证、方法签名验证、元数据验证）
5. **领域层零依赖** — 端口定义（`EntityExtractionPort`）和值对象（`ExtractedEntity`/`ExtractedRelation`/`ExtractionResult`）仅使用 Python 标准库
6. **透明降级模式** — 外部服务失败时提供降级策略（而非抛出异常），保证主流程不受影响

**应用到本故事/Applied to This Story:**
- [ ] 直接复用 `LLMClientPort.structured_generate()` 进行 LLM 语义抽取
- [ ] 设计 `EntityExtractionSchema` Pydantic Schema 作为结构化输出契约
- [ ] 严格遵循异常编码注册流程（340）
- [ ] 通过 `register_port()` 注册 `entity_extraction` 端口
- [ ] 领域层值对象仅使用 Python 标准库
- [ ] LLM 失败时透明降级至规则基结果

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.2 (create-story workflow) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-08-09 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **需求规格** | `_bmad-output/planning-artifacts/or.md` |
| **异常设计** | `docs/architecture/sisys-uni-exception-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/3-2a-llm-client-infrastructure.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 和 `or.md` 提取
- [x] 前一个故事学习经验整合（Story 3.2a LLM Client）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 已有可复用组件清单明确（LLMClientPort、L5GraphPort、Neo4jAdapter）
- [x] 端口契约清单定义完成
- [x] 异常体系设计完成（编码 340）
- [x] 与 Story 3.2a LLMClientPort 集成设计完整
- [x] 新增 pyahocorasick 依赖标注

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-2b-entity-extraction-llm-rules.md`

**待创建的文件 (Dev Story 实施):**
- `src/domain/ports/entity_extraction.py` — EntityExtractionPort + 值对象
- `src/domain/events/entity_extraction_events.py` — EntitiesExtracted 事件
- `src/domain/exceptions/entity_extraction_exceptions.py` — EntityExtractionError
- `src/application/services/entity_extraction_service.py` — EntityExtractionService
- `src/infrastructure/external_services/entity_extraction/rule_extractor.py` — RuleBasedExtractor
- `src/infrastructure/external_services/entity_extraction/llm_extractor.py` — LLMEntityExtractor
- `src/infrastructure/external_services/entity_extraction/conflict_arbitrator.py` — ConflictArbitrator
- `tests/unit/domain/ports/test_entity_extraction_port.py`
- `tests/unit/domain/events/test_entity_extraction_events.py`
- `tests/unit/domain/exceptions/test_entity_extraction_exceptions.py`
- `tests/unit/application/services/test_entity_extraction_service.py`
- `tests/unit/infrastructure/external_services/entity_extraction/test_rule_extractor.py`
- `tests/unit/infrastructure/external_services/entity_extraction/test_llm_extractor.py`
- `tests/unit/infrastructure/external_services/entity_extraction/test_conflict_arbitrator.py`
- `tests/unit/architecture/test_arch_entity_extraction.py`
- `tests/contracts/test_port_contract_entity_extraction.py`
- `tests/integration/test_integration_entity_extraction.py`
- `tests/acceptance/test_acceptance_entity_extraction.feature`
- `tests/acceptance/test_acceptance_entity_extraction.py`

**更新的文件/Updated Files:**
- `src/domain/ports/__init__.py` — 导出 EntityExtractionPort
- `src/domain/events/__init__.py` — 导出 EntitiesExtracted
- `src/domain/exceptions/__init__.py` — 导出 EntityExtractionError
- `src/domain/exceptions/_code_ranges.py` — 新增 entity_extraction 子域 (340-349)
- `src/interfaces/api/exception_handlers.py` — EXCEPTION_HTTP_MAP 新增
- `src/composition_root.py` — 注册 entity_extraction_rule / entity_extraction_llm / conflict_arbitrator / entity_extraction_service 端口
- `pyproject.toml` — 新增 pyahocorasick 直接依赖
- `configs/event_channels.yaml` — 新增 EntitiesExtracted 事件通道
- `src/infrastructure/messaging/channel_router.py` — DEFAULT_MAPPINGS 新增 EntitiesExtracted

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.2b |
| **Story Key** | 3-2b-entity-extraction-llm-rules |
| **File** | `_bmad-output/implementation-artifacts/stories/3-2b-entity-extraction-llm-rules.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | P0-2 |
| **覆盖 FR** | FR-SR-02（实体抽取） |

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
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.4.0
**创建日期/Created:** 2026-08-09
**最后更新/Last Updated:** 2026-08-09
**更新说明/Description:**
- v1.4.0: Round 5 文档审查修复 — P1: AC-1 值对象验证标准补充 `normalized_name` 字段（与 SDD 数据模型一致）；P1: AC-7 去除重复项并补充事件发布失败处理（日志记录不阻塞主流程）；P1: 端口契约清单扩展（拆分 EntityExtractionPort × 2 实现 + ConflictArbitrator + EntityExtractionService 四端口）；P1: 端口契约测试 Subtask 扩展为验证 4 个端口注册；P2: 删除重复的"异常处理"验证项（AC-7 第 139-140 行重复）
- v1.3.0: Round 4 文档审查修复 — P1: 修正 AC-8 端口注册设计（RuleBasedExtractor/LLMEntityExtractor 各自实现 EntityExtractionPort 分别注册为独立端口）；P1: 修正 Subtask 4.2 注册代码（拆分 4 个端口注册）；P2: 修正 `pyahocorasick` 依赖状态
- v1.2.0: Round 3 文档审查修复 — P1: 修正 AC-2 领域事件验证标准；P1: 修正集成测试描述为 aiohttp 模式；P1: 修正测试隔离约束
- v1.1.0: Round 2 文档审查修复 — P1: 补充事件/LLM抽取/异常脱敏规范
- v1.0.0: 创建故事文件

<!-- 仅用作跟踪故事文件模板修订记录，故事开发时[务必删除]此段 -->
