# Story 3-2: 实体抽取（LLM + 规则混合）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 知识工程师,
**I want** 系统抽取实体（LLM + 规则混合策略），输出三元组（实体-关系-实体）,
**So that** 构建知识图谱的实体和关系。

### 业务价值

Story 3-2 是 Epic 3（智能检索与知识发现）的第三个故事（P0-2），在 Story 3-1a（Dense 语义检索）和 Story 3-1b（BM25 稀疏检索 + RRF 融合）交付双路检索能力之后，引入实体抽取能力。

**实体抽取对于后续 Story 至关重要：**
- Story 3-4（RRF 融合排序）：将图信号融合到 RRF（Dense+Sparse+Graph 三路融合）
- Story 3-5（分层检索 L1-L4）：Graph 层提供实体关联关系增强检索
- Story 12-5（知识图谱构建 GraphRAG）：实体关系直接构成知识图谱
- Story 3-3（战略领域词典库）：为规则基抽取提供领域专用词典

**核心设计：LLM + 规则混合策略**
- **规则基路径**（高精确率路径）：AC 自动机/正则/依存句法 — 高精确率（≥80%），确定性抽取
- **LLM 语义路径**（高召回率路径）：Few-Shot + CoT + Schema 约束 — 高召回率（≥90%），覆盖规则无法处理的模糊表达
- **冲突仲裁器**：规则基和 LLM 结果并集 + 加权置信度融合 → 三元组列表
- **融合权重** (`rule_weight=0.6`, `llm_weight=0.4`): 初始经验值，定义于 `ConflictArbiter` 构造参数，V1+ 通过标注数据集校准

**关键假设：**
- LLM 调用：`LLMExtractor` 通过 `LLMInvocationPort`（新增领域端口）调用 LLM，由基础设施层 `OllamaAdapter` / `LiteLLMAdapter` 实现。UDMR 路由通过 `udmr_service.decide()` 获取路由决策（`RoutingDecided` 事件），LLMExtractor 据此选择调用目标
- 规则基的 AC 自动机使用 `pyahocorasick` 库（Python C 扩展），正则/依存句法使用 `spaCy`（zh_core_web_sm 中文模型）
- 输出三元组写入 L5 Neo4j 图存储：通过 `L5GraphPort.create_entity()` 创建实体节点，通过 `L5GraphPort.create_relationship()` 创建关系边。`MemoryGraphPort.index_memory_relations()` 用于其他记忆索引场景，非本 Story 实体批量写入入口
- MVP 阶段以中文语料为主要处理目标（战略文档、市场报告、会议纪要）
- **种子词典**：MVP 阶段内嵌静态种子词典文件（`seed_data/entities.json`，50-100 条按实体类型均匀分布），Story 3-3 交付后将替换为动态词典管理。AC 自动机构造函数接受 `seed_dict: dict[str, list[str]] | None = None` 参数，支持空词典启动

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 实体类型与关系类型定义

**Given** 领域层定义了实体和关系的值对象体系
**When** 系统执行实体抽取
**Then** 使用以下实体类型体系：

| 实体类型 | 含义 | 识别示例 |
|---------|------|---------|
| `ORGANIZATION` | 组织/公司/机构 | 华为、财政部、中国证监会、Apple |
| `PERSON` | 人物 | 任正非、马斯克、张经理 |
| `PRODUCT` | 产品/服务 | P60手机、ChatGPT、微信支付 |
| `MARKET` | 市场/行业/赛道 | 新能源汽车、AI芯片、欧洲市场 |
| `METRIC` | 指标/数值型事实 | 年营收300亿、市占率35%、ROI 150% |
| `STRATEGY` | 战略/策略/行动 | 差异化战略、全球化布局、成本领先 |
| `REGULATION` | 法规/政策 | 《数据安全法》、GDPR、反垄断法 |
| `EVENT` | 事件/时间关键点 | 2024年Q3发布、A轮融资、品牌升级 |
| `OTHER` | 无法归入上述8类的实体 | 深圳（地名）、2025年（时间） |

**And** 使用以下关系类型（在本 Story 中扩展 `RelationshipType` 枚举至 13 种 -- 保留全部 6 种已有值 + 新增 7 种）：

| 关系类型 | 已有/新增 | 说明 |
|---------|----------|------|
| `COMPETES_WITH` | 新增 | 竞争关系（A vs B） |
| `SUPPLIES_TO` | 新增 | 供应关系（A → B） |
| `INVESTS_IN` | 新增 | 投资关系 |
| `OWNS` | 新增 | 拥有关系（母子公司） |
| `LAUNCHED` | 新增 | 发布关系（公司→产品） |
| `OPERATES_IN` | 新增 | 经营地域/市场 |
| `REGULATED_BY` | 新增 | 受法规约束 |
| `INFLUENCES` | 已有 | 影响关系 |
| `PART_OF` | 已有 | 包含关系 |
| `DEPENDS_ON` | 已有 | 依赖关系 |

**验证标准/Validation Criteria:**
- [ ] 领域层 `src/domain/value_objects/entity_types.py` — `EntityType` StrEnum（9 种实体类型，含 `OTHER` 兜底类型）
- [ ] 领域层 `src/domain/value_objects/entity_relation.py` — `EntityRelation` frozen dataclass（subject/relation/object/confidence/source）。注意：`EntityRelation` 使用 name/string 引用实体，用于提取阶段输出；`Triple` 使用 entity_id 引用实体，用于持久化阶段
- [ ] `RelationshipType` 枚举扩展至 13 种（保留全部 6 种已有值：`MENTIONS`, `DEPENDS_ON`, `RELATES_TO`, `PART_OF`, `INFLUENCES`, `CONTRADICTS` + 新增 7 种：`COMPETES_WITH`, `SUPPLIES_TO`, `INVESTS_IN`, `OWNS`, `LAUNCHED`, `OPERATES_IN`, `REGULATED_BY`），更新 `src/infrastructure/storage/neo4j/models.py`（基础设施层 DTO，不违反六边形架构）
- [ ] 新增 `Triple` frozen dataclass 于 `src/domain/value_objects/triple.py` — `(subject_entity_id: str, relation_type: str, object_entity_id: str, confidence: float, evidence_text: str, source: str)`

### AC-2: 实体抽取端口定义

**Given** 领域层定义了实体抽取的核心端口
**When** 基础设施层实现该端口
**Then** 满足以下契约：

**领域端口** `src/domain/ports/entity_extractor.py` — `EntityExtractorPort` (Protocol):

| 方法 | 签名 | 说明 |
|------|------|------|
| `extract` | `async def extract(text: str, context: dict[str, Any] \| None = None) -> EntityExtractionResult` | 异步方法 — 内部并行执行规则基路径（`asyncio.to_thread` 卸载同步 AC/正则/spaCy）和 LLM 路径，await 返回完整结果 |
| `extract_batch` | `async def extract_batch(texts: list[str]) -> list[EntityExtractionResult]` | 批量抽取 |

**值对象定义** `src/domain/value_objects/extraction_result.py`:

| 类型 | 字段 |
|------|------|
| `EntityExtractionResult` (frozen dataclass) | `triples: tuple[Triple, ...]`, `entities: tuple[ExtractedEntity, ...]`, `statistics: ExtractionStatistics`, `persisted: bool` |
| `ExtractedEntity` (frozen dataclass) | `entity_id: str` (SHA-256 哈希), `name: str`, `type: EntityType`, `mentions: tuple[str, ...]` (原文提及), `properties: dict[str, Any]` |
| `ExtractionStatistics` (frozen dataclass) | `rule_based_count: int`, `llm_count: int`, `merged_count: int`, `conflict_count: int`, `elapsed_ms: float` |

**注意:** 本 Story 的 `EntityExtractionResult` 与已有 `src/application/ports/text_extractor_service.py` 中的 `ExtractionResult`（L1 文本记忆提取结果，字段: `content/pattern/original`）是不同值对象，避免命名冲突。

**应用服务** `src/application/services/entity_extraction_service.py` — `EntityExtractionService`：

- 构造注入：`EntityExtractorPort`（领域端口实现）+ `L5GraphPort`（图写入）+ `EventPublisher`（事件发布）
- `extract_and_persist(text: str, document_id: str, tenant_id: str) -> EntityExtractionResult` — 抽取 + 直接写入 Neo4j
- `extract_and_persist_batch(texts: list[str], document_id: str, tenant_id: str) -> list[EntityExtractionResult]`

**验证标准/Validation Criteria:**
- [ ] 领域层 `EntityExtractorPort` 仅依赖 Python 标准库（Protocol, typing），符合六边形架构约束
- [ ] 应用层 `entity_extraction_service.py` 依赖 `EntityExtractorPort` + `L5GraphPort`（图写入）
- [ ] `Triple.confidence` 值 ∈ [0.0, 1.0]，验证在 `__post_init__` 中

### AC-3: 规则基抽取（AC 自动机 + 依存句法）

**Given** 加载了领域词典（包含约 500 条种子实体：公司名/人名/产品/政策）
**When** 系统执行规则基抽取
**Then** AC 自动机扫描文本识别已知实体
**And** 正则模式匹配 `METRIC` 类型（数字+单位模式：`\d+[\.\d]*\s*(亿|万|%|倍|美元|元|人|家|个)`）
**And** spaCy 依存句法解析 `主谓宾` 三元组（nsubj → ROOT → dobj）
**And** 规则基抽取准确率 ≥ 80%（组织/人物/产品 ≥ 90%，策略/事件 ≥ 70%）
**And** 每次调用延迟 P95 < 500ms（纯规则路径，不含 LLM）

**验证标准/Validation Criteria:**
- [ ] 规则基引擎位于 `src/infrastructure/extraction/rule_engine/` 目录
- [ ] `AhoCorasickMatcher` 类：封装 `pyahocorasick.Automaton`，支持构建/匹配/按类型过滤
- [ ] `RegexPatternMatcher` 类：至少包含 METRIC（数字+单位）、日期百分比（如 `2024年Q3`）、金额（如 `300亿元`）
- [ ] `DependencyParserMatcher` 类：封装 spaCy `zh_core_web_sm`，提取 SVO 三元组，合并共指关系
- [ ] `RuleBasedExtractor` 类：组合上述三个匹配器，输出 `RawTriple`（subject_text/relation_text/object_text/confidence）
- [ ] AC 自动机词典初始化在构造函数中完成（一次性加载），`extract()` 调用不重复构建

### AC-4: LLM 语义抽取（Few-Shot + CoT + Schema 约束）

**Given** LLM 通过 UDMR 路由可用（本地 Qwen2.5 或云端 LLM）
**When** 系统执行 LLM 语义抽取
**Then** 构建以下 Few-Shot Prompt 模板：

```
系统提示词：
"你是企业战略知识图谱构建专家。从给定文本中抽取实体及其关系，
以 JSON 格式输出。实体类型包括：ORGANIZATION, PERSON, PRODUCT,
MARKET, METRIC, STRATEGY, REGULATION, EVENT。关系类型包括：
COMPETES_WITH, SUPPLIES_TO, INVESTS_IN, OWNS, LAUNCHED,
OPERATES_IN, REGULATED_BY, INFLUENCES, PART_OF, DEPENDS_ON。

CoT 步骤：
1. 识别文本中所有实体提及（mention level）
2. 将实体提及规范化到唯一实体（entity level），区分同名实体
3. 识别实体间的关系，标注关系类型和方向
4. 评估每个三元组的置信度（0.0-1.0）：
   - 显式陈述（"X 投资了 Y"）：≥ 0.9
   - 强暗示（"Y 是 X 的全资子公司"）：≥ 0.7
   - 弱暗示（需要推理）：0.5-0.7"
```

**And** Schema 约束输出（JSON Schema）：
```json
{
  "entities": [{"name": "...", "type": "ORGANIZATION", "mentions": ["..."]}],
  "triples": [{"subject": "...", "relation": "INVESTS_IN", "object": "...", "confidence": 0.95, "evidence": "原文证据"}]
}
```

**And** LLM 语义抽取召回率 ≥ 90%

**验证标准/Validation Criteria:**
- [ ] `LLMExtractor` 类位于 `src/infrastructure/extraction/llm_extractor.py`
- [ ] 构造函数注入 `udmr_service: UDMRService`（用于路由决策）+ `llm_invoker: LLMInvocationPort`（新增领域端口，用于实际 LLM API 调用）
- [ ] `extract(text, context)` 方法：
  - 构建 Few-Shot Prompt（含 8-10 个精选示例，每个关系类型至少 1 个，覆盖全部实体类型）
  - 调用 `await udmr_service.decide(task)` 获取 `RoutingDecided`（`route_type` + `selected_model`）
  - 通过 `llm_invoker.invoke(model, prompt)` 发送 LLM 请求（基础设施层 `OllamaAdapter` / `LiteLLMAdapter` 实现）
  - 解析 JSON 输出 → `jsonschema.validate()` 验证 Schema → 类型转换修复 → 返回 `list[RawTriple]` + `list[RawEntity]`
- [ ] LLM 输出 JSON 解析 + Schema 验证失败时重试 2 次（重新请求 + 强调 Schema），第 3 次失败抛出 `LLMExtractionError`，由上游 `EntityExtractionService` 降级到纯规则基结果
- [ ] Few-Shot 示例存储在 `src/infrastructure/extraction/prompts/entity_extraction_examples.py` 中（8-10 个示例，每个关系类型至少 1 个）
- [ ] CoT 推理链嵌入每个 Few-Shot 示例的 `reasoning` 字段中，展示完整推理过程：实体识别 → 规范化 → 关系判断 → 置信度评估
- [ ] 使用 `ollama` 的 `format: json` 参数确保输出合法 JSON；引入 `jsonschema.validate()` 做 Schema 后处理验证

### AC-5: 冲突仲裁与融合

**Given** 规则基和 LLM 各产生一组实体和三元组
**When** 系统执行冲突仲裁
**Then** 按以下规则融合：

**实体融合：**
1. 精确名称匹配 → 合并，类型取高置信度源（规则 > LLM）
2. 模糊匹配（编辑距离 ≤ 2 或包含关系）→ 标记为潜在冲突，保留两个变体，以高优先级标记待 Story 12-1（实体消歧）处理

**三元组融合：**
1. 完全匹配（subject/relation/object 全部相同）→ 保留一个，confidence = rule.confidence * 0.6 + llm.confidence * 0.4（加权求和融合）
2. 部分匹配（两元素相同，一元素不同）→ 均保留，标记来源
3. 规则独有 → 保留（高置信度）
4. LLM 独有 → 保留（可能发现新知识）

**And** 冲突仲裁准确率 ≥ 85%

**验证标准/Validation Criteria:**
- [ ] `ConflictArbiter` 类位于 `src/domain/services/conflict_arbiter.py`（领域服务，纯 Python）
- [ ] `merge_entities(rule_entities, llm_entities) -> list[ExtractedEntity]`
- [ ] `merge_triples(rule_triples, llm_triples) -> list[Triple]`
- [ ] 编辑距离计算使用 Python 标准库 `difflib.SequenceMatcher`（不引入新依赖）
- [ ] 融合后的 triple 包含 `source` 属性标记（"rule" / "llm" / "both"）

### AC-6: 知识图谱持久化

**Given** 实体抽取产生了规范化三元组
**When** 系统执行持久化
**Then** 通过 `L5GraphPort` 写入 Neo4j：
  - 每个 `ExtractedEntity` → 调用 `L5GraphPort.create_entity()` 创建节点（`entity_type` 参数传入 `EntityType` 值）
  - 每个 `Triple` → 调用 `L5GraphPort.create_relationship()` 创建关系边
**And** 节点属性包含：`name`, `type`, `mentions`, `properties`, `source`, `created_at`
**And** 边属性包含：`confidence`, `evidence`, `source`, `created_at`
**And** 写入失败不中断抽取流程（L5 降级为 optional）

**验证标准/Validation Criteria:**
- [ ] `EntityExtractionService` 应用服务位于 `src/application/services/entity_extraction_service.py`
- [ ] `extract_and_persist()` 流程：规则基抽取 → LLM 抽取（并行）→ 冲突仲裁 → Neo4j 写入
- [ ] `extract_and_persist()` 返回完整 `ExtractionResult`（含持久化状态）
- [ ] Neo4j 写入失败时降级策略：WARNING 日志 + 不中断 + 结果中 `persisted=False` 标记
- [ ] 已存在的节点/边使用 `MERGE` 语义（不产生重复数据）

### AC-7: 事件驱动集成

**Given** `DocumentProcessed` 事件已触发
**When** 事件处理器执行
**Then** 自动触发 `EntityExtractionService.extract_and_persist()`
**And** 抽取失败不阻塞文档处理流程（事件处理器内部 try/except + 日志）
**And** 发布 `EntitiesExtracted` 领域事件（含 `document_id`, `triple_count`, `entity_count`, `statistics`）

**验证标准/Validation Criteria:**
- [ ] 新增领域事件 `EntitiesExtracted` 于 `src/domain/events/extraction_events.py`
  - 继承 `DomainEvent`（`@dataclass(frozen=True)`），遵循项目事件模式：`event_type: str = field(default="EntitiesExtracted", init=False)`，`__post_init__` 中设置 `aggregate_id=document_id`, `aggregate_type="Document"`
  - 字段：`document_id: UUID`, `tenant_id: str`, `triple_count: int`, `entity_count: int`, `statistics: dict[str, Any]`（由 `ExtractionStatistics` 通过 `dataclasses.asdict()` 转换传入）
  - 通道：RabbitMQ + Outbox（业务状态型）
- [ ] `configs/event_channels.yaml` 新增 `EntitiesExtracted` 通道配置（`rabbitmq` 通道，`reliable` 投递模式）
- [ ] `src/infrastructure/messaging/channel_router.py` 同步更新 `DEFAULT_MAPPINGS`
- [ ] 新增事件处理器 `EntityExtractionHandler` 于 `src/application/event_handlers/entity_extraction_handler.py`
  - 监听 `DocumentProcessed` 事件
  - 调用 `entity_extraction_service.extract_and_persist()`
- [ ] `EntityExtractionService.extract_and_persist()` 内部完成统计日志记录，不再需要独立 `EntityExtractedHandler` 监听自己发布的事件，避免同进程内事件回环

### AC-8: Composition Root 注册

**Given** 所有端口实现已完成
**When** 在 `src/composition_root.py` 注册
**Then** 以下端口注册到位：

| 端口名称 | 接口 | 实现 | 生命周期 | Tags |
|---------|------|------|----------|------|
| `entity_extractor` | `EntityExtractorPort` | `HybridEntityExtractor`（基础设施层组合类，lambda 工厂注入 `RuleBasedExtractor` + `LLMExtractor` + `ConflictArbiter`） | SCOPED | `extraction, entity, infrastructure` |
| `entity_extraction_service` | `EntityExtractionService` | lambda 工厂注入 `entity_extractor` + `l5_graph` + `event_publisher` | SCOPED | `extraction, entity, application` |
| `entity_extraction_event_handler` | （事件处理器） | `EntityExtractionHandler`（lambda 工厂注入 `entity_extraction_service`） | SINGLETON | `extraction, handler, application` |

**And** 已有 `l5_graph`, `memory_graph_storage`, `udmr_service`, `event_publisher`, `event_subscriber` 端口复用

**验证标准/Validation Criteria:**
- [ ] `entity_extractor` 端口注册到 Composition Root（SCOPED lifetime）
- [ ] `EntityExtractionHandler` 订阅 `DocumentProcessed` 事件（通过 `event_subscriber`）
- [ ] `EntityExtractedHandler` 订阅 `EntitiesExtracted` 事件
- [ ] 端口契约测试更新
- [ ] 已有测试全部保持通过（无回归）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] **新增** `EntitiesExtracted` 事件类（`src/domain/events/extraction_events.py`）：
  - 字段：`document_id: UUID`, `triple_count: int`, `entity_count: int`, `statistics: dict`
  - 继承 `DomainEvent`（`src/domain/events/base.py`）
  - AC-7 规范
- [ ] **事件通道配置**（`configs/event_channels.yaml`）：`EntitiesExtracted` → RabbitMQ + Outbox
- [ ] **通道路由更新**（`src/infrastructure/messaging/channel_router.py`）：`DEFAULT_MAPPINGS` 新增映射

#### 数据模型 (Data Models)
- [ ] **新增** `EntityType` StrEnum（`src/domain/value_objects/entity_types.py`）：
  - 9 种实体类型（AC-1 规范，含 `OTHER` 兜底类型）
- [ ] **新增** `Triple` frozen dataclass（`src/domain/value_objects/triple.py`）：
  - `subject_entity_id: str`, `relation_type: str`, `object_entity_id: str`, `confidence: float`, `evidence_text: str`, `source: str`
  - `__post_init__` 验证 confidence ∈ [0.0, 1.0]
- [ ] **新增** `EntityExtractionResult` frozen dataclass（`src/domain/value_objects/extraction_result.py`）：
  - `triples: tuple[Triple, ...]`, `entities: tuple[ExtractedEntity, ...]`, `statistics: ExtractionStatistics`, `persisted: bool`
  - 注意：与已有 `src/application/ports/text_extractor_service.py` 中的 `ExtractionResult`（L1 文本提取）不同，避免命名冲突
- [ ] **新增** `ExtractedEntity` frozen dataclass（`src/domain/value_objects/extraction_result.py`）：
  - `entity_id: str`, `name: str`, `type: EntityType`, `mentions: tuple[str, ...]`, `properties: dict[str, Any]`
- [ ] **新增** `ExtractionStatistics` frozen dataclass（`src/domain/value_objects/extraction_result.py`）：
  - `rule_based_count: int`, `llm_count: int`, `merged_count: int`, `conflict_count: int`, `elapsed_ms: float`
- [ ] **新增** `EntityRelation` frozen dataclass（`src/domain/value_objects/entity_relation.py`）：
  - `subject: str`, `relation: str`, `object: str`, `confidence: float`, `source: str`
  - 使用字符串引用实体（提取阶段），区别于 `Triple`（持久化阶段，使用 entity_id）
- [ ] **扩展** `RelationshipType` StrEnum（`src/infrastructure/storage/neo4j/models.py`）：
  - 新增 7 种关系类型：`COMPETES_WITH`, `SUPPLIES_TO`, `INVESTS_IN`, `OWNS`, `LAUNCHED`, `OPERATES_IN`, `REGULATED_BY`（保留全部 6 种已有值，总计 13 种）
  - 注意：`RelationshipType` 作为基础设施层 DTO 的枚举，其扩展不影响领域层

#### 统一端口定义注册与管理 (Port Contract)
- [ ] **新增** `EntityExtractorPort` 领域端口（`src/domain/ports/entity_extractor.py`）：
  - `extract(text, context) -> ExtractionResult`（async）
  - `extract_batch(texts) -> list[ExtractionResult]`（async）
- [ ] **新增** `EntityExtractionService` 应用服务（`src/application/services/entity_extraction_service.py`）：
  - 构造注入：`EntityExtractorPort`, `L5GraphPort`, `EventPublisher`
  - `extract_and_persist(text, document_id, tenant_id) -> ExtractionResult`
  - `extract_and_persist_batch(texts, document_id, tenant_id) -> list[ExtractionResult]`
- [ ] **端口注册** — 在 `src/composition_root.py` 注册（AC-8 规范）
- [ ] **端口契约门禁**（`src/domain/ports/contract_gate.py`）：新端口通过兼容性检查
- [ ] **端口契约测试**（`tests/contracts/test_port_contract_entity_extraction.py`）

**端口契约清单：**

| 端口名称 | 版本 | 接口 | 实现模块 | 生命周期 | Owner |
|---------|------|------|----------|----------|-------|
| `entity_extractor` | v1.0.0 | `EntityExtractorPort` | `src.infrastructure.extraction.hybrid_entity_extractor` | SCOPED | search-team |
| `entity_extraction_service` | v1.0.0 | `EntityExtractionService` | `src.application.services.entity_extraction_service` | SCOPED | search-team |
| `l5_graph` | v1.0.0（不变） | `L5GraphPort` | `Neo4jAdapter` | SCOPED | storage-team |
| `memory_graph_storage` | v1.0.0（不变） | `MemoryGraphPort` | `Neo4jMemoryGraphStorage` | SCOPED | storage-team |
| `udmr_service` | v1.0.0（不变） | `UDMRService` | — | SINGLETON | routing-team |
| `event_publisher` | v1.0.0（不变） | `EventPublisher` | — | SINGLETON | messaging-team |
| `event_subscriber` | v1.0.0（不变） | `EventSubscriber` | — | SINGLETON | messaging-team |

#### API 契约 (API Contract)
- [x] MVP 阶段不新增 REST API 端点 — 实体抽取由 `DocumentProcessed` 事件驱动，内部服务
- [x] V1+ 可按需新增 `POST /api/v1/extraction` 端点（非本 Story 范围）

#### 领域异常契约 (Domain Exception Contract)

> **策略：新增 2 个 entity 子域异常，复用已有基类。**

**新增异常：**

| 异常类型 | 编码 | 继承 | HTTP | 使用场景 |
|---------|------|------|------|----------|
| `EntityExtractionError` | EXCEPTION_245 | `EntityBusinessRuleError` (entity 子域) | 422 | 实体抽取全流程失败（规则基 + LLM 均不可用） |
| `LLMExtractionError` | EXCEPTION_304 | `ThirdPartyError` (external 子域) | 502 | LLM 抽取调用失败（LLM API 返回无效 JSON 超过重试次数） |

**复用已有异常：**

| 异常类型 | 编码 | 使用场景 |
|---------|------|----------|
| `ValidationError` | EXCEPTION_201 | 输入文本为空/过长（>50K tokens）、Schema 验证失败 |
| `EntityBusinessRuleError` | EXCEPTION_244 | 抽取结果违反业务约束（如三元组 subject==object） |
| `ConfigurationError` | EXCEPTION_101 | AC 自动机词典文件不存在/spaCy 模型未安装 |

**设计决策：**
- `EntityExtractionError` 使用 entity 子域编码 245，继承 `EntityBusinessRuleError`（entity 子域），表示抽取失败是 entity 层面的业务异常
- `LLMExtractionError` 使用 external 子域编码 304，继承 `ThirdPartyError`（external 子域，编码 301），符合 `_code_ranges.py` 的子域编码归属规则。LLM 调用失败本质是外部服务异常，HTTP 502（Bad Gateway）语义正确
- `_CLASS_TO_SUBDOMAIN` 注册：`"EntityExtractionError": "entity"`，`"LLMExtractionError": "external"`
- `EXCEPTION_HTTP_MAP` 精确注册：`EntityExtractionError: 422`，`LLMExtractionError: 502`

#### 六边形架构约束（必须遵守）
> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖 |
| application | `src/application/` | 用例编排 |
| interfaces | `src/interfaces/` | 适配器 |
| infrastructure | `src/infrastructure/` | 技术实现 |

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | interfaces | infrastructure |
|-------------|--------|-------------|------------|----------------|
| **domain** | — | ✗ 禁止 | ✗ 禁止 | ✗ 禁止 |
| **application** | ✓ 允许 | — | ✗ 禁止 | ✗ 禁止 |
| **interfaces** | ✓ 允许 | ✓ 允许 | — | ✗ 禁止 |
| **infrastructure** | ✓ 允许 | ✓ 允许 | ✗ 禁止 | — |

**本 Story 依赖约束：**
- `src/domain/value_objects/entity_types.py` → 仅 `enum` 标准库
- `src/domain/value_objects/triple.py` → 仅 `dataclasses` 标准库
- `src/domain/ports/entity_extractor.py` → 仅 `typing` 标准库
- `src/infrastructure/extraction/rule_engine/` → 可依赖 `pyahocorasick`, `spacy`（第三方库）
- `src/infrastructure/extraction/llm_extractor.py` → 可依赖 `httpx`（通过 UDMR 间接调用 LLM）

---

## 📋 Tasks / Subtasks

### Task 0: SDD 规范定义 (AC: 全部)
- [ ] **0.1** 创建 `EntityType` StrEnum 值对象（8 种实体类型）
- [ ] **0.2** 创建 `Triple` frozen dataclass 值对象（含 `__post_init__` 验证）
- [ ] **0.3** 创建 `ExtractedEntity`、`ExtractionResult`、`ExtractionStatistics` frozen dataclass
- [ ] **0.4** 创建 `EntityRelation` frozen dataclass 值对象
- [ ] **0.5** 创建 `EntityExtractorPort` 领域端口 Protocol
- [ ] **0.6** 扩展 `RelationshipType` StrEnum（基础设施层 DTO）
- [ ] **0.7** 新增 `EntityExtractionError` (245) 和 `LLMExtractionError` (304) 领域异常
- [ ] **0.8** 更新异常体系：`__all__`、`__init__.py`、`_code_ranges.py`（`_CLASS_TO_SUBDOMAIN`: `"EntityExtractionError": "entity"`, `"LLMExtractionError": "external"`）、`EXCEPTION_HTTP_MAP`（精确注册: `EntityExtractionError: 422`, `LLMExtractionError: 502`）
- [ ] **0.9** 新增 `EntitiesExtracted` 领域事件定义
- [ ] **0.10** 更新 `config/event_channels.yaml` 和 `channel_router.py`

### Task 1: 规则基抽取引擎 (AC-3)
- [ ] **1.1** TDD 红：编写 `AhoCorasickMatcher` 单元测试（构建/匹配/类型过滤）
- [ ] **1.2** TDD 绿：实现 `AhoCorasickMatcher` — 封装 `pyahocorasick.Automaton`
- [ ] **1.3** TDD 红：编写 `RegexPatternMatcher` 单元测试（METRIC/日期百分比/金额 3 个模式）
- [ ] **1.4** TDD 绿：实现 `RegexPatternMatcher` — 编译预定义正则模式
- [ ] **1.5** TDD 红：编写 `DependencyParserMatcher` 单元测试（SVO 三元组提取）
- [ ] **1.6** TDD 绿：实现 `DependencyParserMatcher` — 封装 spaCy 依存句法
- [ ] **1.7** TDD 红：编写 `RuleBasedExtractor` 单元测试（三匹配器组合 + 准确率验证）
- [ ] **1.8** TDD 绿：实现 `RuleBasedExtractor` — 组合匹配器，产出 `RawTriple`
- [ ] **1.9** TDD 绿：集成 AC 词典种子数据文件（JSON 格式，按实体类型组织）

### Task 2: LLM 语义抽取 (AC-4)
- [ ] **2.1** TDD 红：编写 `LLMExtractor` 单元测试（Mock UDMR Service 验证 Prompt 构建）
- [ ] **2.2** TDD 绿：实现 `LLMExtractor` — UDMR 路由 → LLM 调用 → JSON Schema 解析
- [ ] **2.3** TDD 绿：实现 Few-Shot 示例集（3 个精选示例，覆盖 5+ 实体类型）
- [ ] **2.4** TDD 绿：实现 JSON 解析重试机制（失败 1 次 → 重试 → 第 2 次失败返回空结果 + 记录异常）
- [ ] **2.5** TDD 绿：实现 `LLMExtractionError` 抛出逻辑（超过重试次数）

### Task 3: 冲突仲裁领域服务 (AC-5)
- [ ] **3.1** TDD 红：编写 `ConflictArbiter.merge_entities()` 单元测试（精确匹配/模糊匹配/独有实体）
- [ ] **3.2** TDD 绿：实现 `merge_entities()` — 编辑距离模糊匹配 + 类型优先级
- [ ] **3.3** TDD 红：编写 `ConflictArbiter.merge_triples()` 单元测试（完全/部分/独有匹配）
- [ ] **3.4** TDD 绿：实现 `merge_triples()` — 加权置信度融合（规则 0.6/LLM 0.4）
- [ ] **3.5** TDD 绿：融合后 `source` 标记（"rule"/"llm"/"both"）

### Task 4: EntityExtractionService 应用服务 (AC-6)
- [ ] **4.1** TDD 红：编写 `EntityExtractionService.extract_and_persist()` 单元测试（Mock 端口注入）
- [ ] **4.2** TDD 绿：实现 `extract_and_persist()` — 规则基 + LLM 并行 → 仲裁 → Neo4j 写入
- [ ] **4.3** TDD 绿：实现 L5 写入降级逻辑（失败不中断）
- [ ] **4.4** TDD 红：编写 `extract_and_persist_batch()` 单元测试
- [ ] **4.5** TDD 绿：实现批量抽取（`asyncio.gather` 并行处理）
- [ ] **4.6** TDD 绿：发布 `EntitiesExtracted` 领域事件

### Task 5: 事件驱动集成 (AC-7)
- [ ] **5.1** TDD 红：编写 `EntityExtractionHandler` 单元测试
- [ ] **5.2** TDD 绿：实现 `EntityExtractionHandler.handle(DocumentProcessed)` — 监听→抽取→统计日志

### Task 6: Composition Root 注册 (AC-8)
- [ ] **6.1** 注册 `entity_extractor` 端口（SCOPED lifetime，lambda 工厂注入 `RuleBasedExtractor` + `LLMExtractor` + `ConflictArbiter`）
- [ ] **6.2** 注册 `entity_extraction_service` 端口（SCOPED lifetime，lambda 工厂注入 `entity_extractor` + `l5_graph` + `event_publisher`）
- [ ] **6.3** 注册 `entity_extraction_event_handler`（SINGLETON，订阅 `DocumentProcessed`）
- [ ] **6.4** 端口契约测试更新（`tests/contracts/test_port_contract_entity_extraction.py`）
- [ ] **6.5** 验证已有测试全部通过（无回归）

### Task 7: 集成与验收测试
- [ ] **7.1** 集成测试：`tests/integration/test_entity_extraction_integration.py`
  - 端到端：text → rule extract → llm extract → arbitrate → neo4j persist
  - 使用真实 Neo4j（测试 Schema 隔离），Mock LLM（避免依赖 LLM 运行时）
- [ ] **7.2** 架构测试：`tests/unit/architecture/test_entity_extraction.py`
  - 验证领域层零外部依赖
  - 验证端口契约合规
  - 验证异常编码唯一性

---

## 📊 性能要求汇总

| 指标 | 目标 | 测量方式 |
|------|------|---------|
| 规则基抽取准确率 | ≥ 80%（ORGANIZATION/PERSON/PRODUCT ≥ 90%，文本长度 < 2000 tokens） | 最小标注测试集验证（≥50 句中文战略文本） |
| LLM 语义抽取召回率 | ≥ 85%（MVP 阶段，Qwen2.5-7B 本地模型） | 测试集验证 |
| 冲突仲裁准确率 | ≥ 85% | 测试集验证 |
| 规则基抽取延迟 P95 | < 1000ms（不含 LLM，文本长度 < 2000 tokens） | `time.perf_counter()` |
| 端到端抽取延迟 P95 | < 10s（MVP 阶段，含 LLM 调用） | 集成测试测量 |

## 📊 覆盖率要求

| 层级 | 目标 | 说明 |
|------|------|------|
| domain | ≥ 90% | 值对象 + 冲突仲裁器 |
| application | ≥ 85% | EntityExtractionService + 事件处理器 |
| infrastructure | ≥ 80% | 规则引擎 + LLM Extractor |
| 整体 | ≥ 85% | 新增代码覆盖率 |

## 📊 代码质量要求

- [ ] Ruff 检查通过（`poetry run ruff check src/ tests/`）
- [ ] Ruff 格式化（`poetry run ruff format src/ tests/`）
- [ ] MyPy 类型检查通过（`poetry run mypy src/`）
- [ ] 架构约束验证（`.importlinter`）
- [ ] 异常编码唯一性测试通过（`poetry run pytest tests/unit/domain/exceptions/ -v`）
- [ ] 禁止 `# noqa`、`# type: ignore`、`# pylint: disable` 等抑制注释

---

## 🗂️ 测试文件清单

| 文件 | 测试类型 | 覆盖目标 |
|------|---------|---------|
| `tests/unit/domain/value_objects/test_entity_types.py` | 单元 | EntityType 枚举 |
| `tests/unit/domain/value_objects/test_triple.py` | 单元 | Triple frozen dataclass |
| `tests/unit/domain/value_objects/test_extraction_result.py` | 单元 | ExtractionResult/ExtractedEntity/ExtractionStatistics |
| `tests/unit/domain/services/test_conflict_arbiter.py` | 单元 | ConflictArbiter 融合逻辑 |
| `tests/unit/infrastructure/extraction/test_ac_matcher.py` | 单元 | AhoCorasickMatcher |
| `tests/unit/infrastructure/extraction/test_regex_matcher.py` | 单元 | RegexPatternMatcher |
| `tests/unit/infrastructure/extraction/test_dep_parser_matcher.py` | 单元 | DependencyParserMatcher |
| `tests/unit/infrastructure/extraction/test_rule_extractor.py` | 单元 | RuleBasedExtractor 组合 |
| `tests/unit/infrastructure/extraction/test_llm_extractor.py` | 单元 | LLMExtractor（Mock UDMR + LLMInvocationPort） |
| `tests/unit/application/services/test_entity_extraction_service.py` | 单元 | EntityExtractionService（Mock 端口） |
| `tests/unit/application/event_handlers/test_entity_extraction_handler.py` | 单元 | EntityExtractionHandler |
| `tests/unit/domain/exceptions/test_code_ranges.py` | 单元 | 异常编码唯一性验证（更新已注册异常） |
| `tests/contracts/test_port_contract_entity_extraction.py` | 契约 | 端口契约兼容性 |
| `tests/integration/test_entity_extraction_integration.py` | 集成 | 端到端集成测试 |
| `tests/unit/architecture/test_entity_extraction.py` | 架构 | 领域层零外部依赖 + 端口契约合规 |

---

## 🔗 依赖关系

**前置依赖：**
- [x] Story 3-1a (Dense 语义检索) — done
- [x] Story 3-1b (BM25 稀疏检索 + RRF 融合) — done
- [x] Story 1-8 (Neo4j L5 图存储层) — done
- [x] Story 1-17 (UDMR 路由基础设施) — done

**交叉依赖：**
- Story 3-3 (战略领域词典库管理) — 依赖本 Story 的规则基抽取管道（词典 consume）
- Story 3-4 (RRF 融合排序三路) — 依赖本 Story 的三元组数据（Graph 信号 consume）
- Story 12-5 (知识图谱构建 GraphRAG) — 直接依赖本 Story 的实体关系

**不依赖：**
- Epic 4-20（可以独立交付）

---

## 📁 关键文件路径参考

### 已有文件（需了解/复用）

| 文件 | 用途 | 复用方式 |
|------|------|---------|
| `src/domain/ports/l5_graph.py` | `L5GraphPort` Protocol | 图实体写入端口（AC-6） |
| `src/application/ports/memory_graph_port.py` | `MemoryGraphPort` Protocol | 记忆关系索引端口 |
| `src/infrastructure/storage/neo4j/neo4j_adapter.py` | `Neo4jAdapter` | L5 图存储实现 |
| `src/infrastructure/storage/neo4j/models.py` | `GraphNode`, `GraphRelationship`, `RelationshipType` | 图数据模型（需扩展） |
| `src/infrastructure/storage/neo4j/graph_manager.py` | `Neo4jGraphManager` | 节点关系 CRUD |
| `src/infrastructure/storage/neo4j/graph_retriever.py` | `GraphRetriever` | 图检索（后续 Story 用） |
| `src/domain/ports/udmr_policy.py` | `UdmrPolicyPort` | LLM 路由策略 |
| `src/domain/services/udmr_service.py` | `UDMRService` | LLM 三层决策路由 |
| `src/domain/events/base.py` | `DomainEvent` 基类 | 事件继承基类 |
| `src/domain/exceptions/_code_ranges.py` | 编码范围约束 | entity 子域 245/246 注册 |
| `src/domain/exceptions/business_exceptions.py` | 业务异常基类 | EntityBusinessRuleError 复用于 245 |
| `src/domain/exceptions/external_exceptions.py` | 外部异常基类 | ThirdPartyError 复用于 246 |
| `src/composition_root.py` | DI 容器 | 端口注册位置 |
| `configs/event_channels.yaml` | 事件通道配置 | 新增 EntitiesExtracted 通道 |
| `src/infrastructure/messaging/channel_router.py` | 通道路由 | 新增 EntitiesExtracted 映射 |

### 新增文件（本 Story 创建）

| 文件 | 层级 | 职责 |
|------|------|------|
| `src/domain/value_objects/entity_types.py` | domain | `EntityType` StrEnum（9 种实体类型，含 `OTHER`） |
| `src/domain/value_objects/triple.py` | domain | `Triple` frozen dataclass |
| `src/domain/value_objects/extraction_result.py` | domain | `EntityExtractionResult`/`ExtractedEntity`/`ExtractionStatistics` |
| `src/domain/value_objects/entity_relation.py` | domain | `EntityRelation` frozen dataclass |
| `src/domain/ports/entity_extractor.py` | domain | `EntityExtractorPort` Protocol |
| `src/domain/ports/llm_invocation.py` | domain | `LLMInvocationPort` Protocol（新增领域端口，LLM API 调用抽象） |
| `src/domain/services/conflict_arbiter.py` | domain | `ConflictArbiter` 领域服务 |
| `src/domain/events/extraction_events.py` | domain | `EntitiesExtracted` 领域事件 |
| `src/application/services/entity_extraction_service.py` | application | `EntityExtractionService` 应用服务 |
| `src/application/event_handlers/entity_extraction_handler.py` | application | `EntityExtractionHandler`（监听 DocumentProcessed） |
| `src/infrastructure/extraction/__init__.py` | infrastructure | 抽取模块初始化 |
| `src/infrastructure/extraction/hybrid_entity_extractor.py` | infrastructure | `HybridEntityExtractor`（实现 `EntityExtractorPort`，组合 RuleBasedExtractor + LLMExtractor + ConflictArbiter） |
| `src/infrastructure/extraction/rule_engine/__init__.py` | infrastructure | 规则引擎模块初始化 |
| `src/infrastructure/extraction/rule_engine/ac_matcher.py` | infrastructure | `AhoCorasickMatcher` |
| `src/infrastructure/extraction/rule_engine/regex_matcher.py` | infrastructure | `RegexPatternMatcher` |
| `src/infrastructure/extraction/rule_engine/dep_parser_matcher.py` | infrastructure | `DependencyParserMatcher` |
| `src/infrastructure/extraction/rule_engine/rule_extractor.py` | infrastructure | `RuleBasedExtractor` 组合引擎 |
| `src/infrastructure/extraction/rule_engine/seed_data/entities.json` | infrastructure | AC 自动机种子词典（MVP 50-100 条） |
| `src/infrastructure/extraction/llm_extractor.py` | infrastructure | `LLMExtractor`（UDMR 路由 + Few-Shot + CoT） |
| `src/infrastructure/extraction/prompts/__init__.py` | infrastructure | Prompt 模板初始化 |
| `src/infrastructure/extraction/prompts/entity_extraction_examples.py` | infrastructure | Few-Shot 示例集（8-10 个） |
| `src/infrastructure/external_services/llm/ollama_adapter.py` | infrastructure | `OllamaAdapter`（实现 `LLMInvocationPort`） |

---

## ⚠️ 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM 中文实体抽取质量不稳定 | 召回率 < 90% | 3 个精心设计的中文战略领域 Few-Shot 示例 + CoT 分步推理 |
| spaCy `zh_core_web_sm` 在战略文本上精度不足 | 依存句法 SVO 提取准确率低 | `DependencyParserMatcher` 添加领域特定规则补充（如 "X投资Y"、"X收购Y" 式模板） |
| LLM 调用延迟超 10s | 整体延迟超标 | UDMR 本地路由（Ollama+Qwen2.5）优先；重试策略增加超时控制，MVP 接受 < 15s |
| AC 自动机内存占用过大（>100MB） | 容器内存不足 | 种子词典限 500 条；超出时按频率 Top-K 筛选 |

---

## 📝 Dev Notes

### 领域知识要点
- 实体抽取准确率不追求 100%——接受噪声，Story 3-3（领域词典）和 Story 12-1（实体消歧）将迭代改进
- `Triple.confidence` 不是最终信仰——下游 Story（3-4 RRF 融合）会把它当做 Graph 信号的权重
- Neo4j 写入是 optional 的——如果 Neo4j 不可用，抽取结果仍在 `ExtractionResult` 中可用

### 测试约定
- Mock LLM/UDMR 调用（除非集成测试显式启用本地 LLM），Mock 策略见 `tests/unit/infrastructure/extraction/` fixture
- 单元测试中 `RuleBasedExtractor` 需 mock `spaCy` 模型（`Morphology` 需 `label_data`），参考 `tests/conftest.py` 中的 `mock_nlp` fixture
- `ConflictArbiter` 使用固定测试数据（`src.domain.services.conflict_arbiter`），不依赖外部模型
- 测试覆盖率门禁：领域层 ≥ 90%、应用层 ≥ 85%、基础设施层 ≥ 80%

### 注意事项
- `pyahocorasick` 和 `spaCy` 需要添加至 `pyproject.toml` 依赖并安装。`pyahocorasick` 是 C 扩展，需要编译环境（Linux: gcc/python3-dev；Windows: Visual C++ Build Tools）
- spaCy 模型需在测试前下载：`python -m spacy download zh_core_web_sm`（约 45MB）
- 应确认 `zh_core_web_sm` 已在 CI runner 镜像中预装（参见 Epic 0）
- Task 0（SDD 规范定义）中新增子任务 0.0：验证并安装所有第三方依赖，确认 CI runner 编译环境

---

## 🔧 技术栈

| 组件 | 版本 | 用途 |
|------|------|------|
| `pyahocorasick` | ^2.0+ | AC 自动机——规则基匹配（需添加至 pyproject.toml 依赖） |
| `spaCy` | ^3.7+ | 依存句法解析（需添加至 pyproject.toml 依赖） |
| `zh_core_web_sm` | latest | spaCy 中文模型 |
| `httpx` | ^0.27+ (已有) | LLM HTTP 调用（LLMInvocationPort 的实现层） |
| LiteLLM | ^1.28+ (已有) | LLM 统一接口（LLMInvocationPort 的云端实现，间接依赖） |

---

## 📝 Dev Agent Record

### Agent Model Used

GPT-5.2 / Claude Opus 5 (选择理由：complex architecture context + multi-agent research required)

### Debug Log References

### Completion Notes List

### File List
