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
- **规则基路径**（高精确率路径）：spaCy PhraseMatcher/正则/依存句法 — 高精确率（≥80%），确定性抽取
- **LLM 语义路径**（高召回率路径）：Few-Shot + CoT + Schema 约束 — 高召回率（≥90%），覆盖规则无法处理的模糊表达
- **冲突仲裁器**：规则基和 LLM 结果并集 + 加权置信度融合 → 三元组列表
- **融合权重** (`rule_weight=0.6`, `llm_weight=0.4`): 初始经验值，定义于 `ConflictArbiter` 构造参数。最终公式：`weighted_confidence = alpha * rule.confidence + (1-alpha) * llm.confidence`，其中 `alpha` 作为可配置参数（默认 0.6），V1+ 通过标注数据集校准。权重支持运行时通过 `configs/extraction.yaml` 覆盖

**关键假设：**
- LLM 调用通过已有 UDMR 路由（`udmr_service.decide()` → `RoutingDecided` 事件），优先本地 Ollama+Qwen2.5，云端兜底
- 规则基统一使用 `spaCy` + `zh_core_web_sm` 中文模型：PhraseMatcher（实体短语匹配）+ 正则（METRIC 模式）+ DependencyParser（SVO 三元组），三者复用同一个 `nlp` 对象，避免重复分词和额外依赖
- 输出三元组写入 L5 Neo4j 图存储：通过 `L5GraphPort.create_entity()` 创建实体节点，通过 `L5GraphPort.create_relationship()` 创建关系边。`MemoryGraphPort.index_memory_relations()` 用于其他记忆索引场景，非本 Story 实体批量写入入口
- MVP 阶段以中文语料为主要处理目标（战略文档、市场报告、会议纪要）
- **种子词典**：MVP 阶段内嵌静态种子词典文件（`seed_data/entities.json`，50-100 条按实体类型均匀分布），Story 3-3 交付后将替换为动态词典管理。PhraseMatcher 初始化接受 `seed_dict: dict[str, list[str]] | None = None` 参数，支持空词典启动
  - JSON 格式：`{"ORGANIZATION": ["华为", "财政部", "中国证监会"], "PERSON": ["任正非", "马斯克"], "PRODUCT": ["P60手机", "ChatGPT"], ...}` — 顶层键为 `EntityType` 值，值为实体名称列表。完整示例见 Task 0.11 子任务

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

| 关系类型 | 已有/新增 | 方向性 | 说明 |
|---------|----------|--------|------|
| `COMPETES_WITH` | 新增 | 无向 | 竞争关系（A vs B），双向等价 |
| `SUPPLIES_TO` | 新增 | 有向 | 供应关系（A → B） |
| `INVESTS_IN` | 新增 | 有向 | 投资关系（A → B） |
| `OWNS` | 新增 | 有向 | 拥有关系（母公司 → 子公司） |
| `LAUNCHED` | 新增 | 有向 | 发布关系（公司 → 产品） |
| `OPERATES_IN` | 新增 | 有向 | 经营地域/市场（公司 → 市场） |
| `REGULATED_BY` | 新增 | 有向 | 受法规约束（实体 → 法规） |
| `INFLUENCES` | 已有 | 双向 | 影响关系（A ↔ B），Neo4j 建模中标注 `bidirectional: true` 属性 |
| `PART_OF` | 已有 | 有向 | 包含关系（子 → 父） |
| `DEPENDS_ON` | 已有 | 有向 | 依赖关系（A → B） |

**注：** 上表仅展示与实体抽取直接相关的关系类型。已有类型 `MENTIONS`、`RELATES_TO`、`CONTRADICTS` 在本 Story 中不会被实体抽取引擎产出，但其枚举值在 `RelationshipType` 中保留不变（总计 13 种 = 7 新增 + 6 已有）。

**无向关系 Neo4j 建模策略：** `COMPETES_WITH` 在语义上是双向等价的无向关系。Neo4j 原生仅支持有向边，建模策略为：按 `entity_id` 字典序确定方向（`source_id < target_id`），边始终从字典序较小的节点指向较大的节点。查询时使用 `(a)-[:COMPETES_WITH]-(b)`（忽略方向）获取完整竞争关系。此转换在 `HybridEntityExtractor` 持久化阶段执行，对 `ConflictArbiter` 透明。`INFLUENCES` 作为双向关系同样遵循此策略，并在边属性中标注 `bidirectional: true`。

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

### AC-3: 规则基抽取（spaCy PhraseMatcher + 正则 + 依存句法）

**Given** 加载了领域种子词典（MVP 阶段约 50-100 条种子实体，按实体类型均匀分布；V1+ 阶段通过 Story 3-3 动态词典扩展至 500 条）
**When** 系统执行规则基抽取
**Then** spaCy PhraseMatcher 基于 Token 序列匹配已知实体（词边界由 `zh_core_web_sm` 分词器保证）
**And** 正则模式匹配 `METRIC` 类型（数字+单位模式：`\d+[\.\d]*\s*(亿|万|%|倍|美元|元|人|家|个)`）
**And** spaCy 依存句法解析 `主谓宾` 三元组（nsubj → ROOT → dobj）
**And** 规则基抽取精确率 (Precision) ≥ 80%（ORGANIZATION/PERSON/PRODUCT ≥ 90%，策略/事件 ≥ 70%）
**And** 每次调用延迟 P95 < 1000ms（纯规则路径，不含 LLM，文本长度 < 2000 tokens）

**验证标准/Validation Criteria:**
- [ ] 规则基引擎位于 `src/infrastructure/extraction/rule_engine/` 目录
- [ ] `PhraseMatcherAdapter` 类：封装 spaCy `PhraseMatcher`，支持 `add_patterns(seed_dict)` 按类型批量注册 + `match(doc) -> list[dict]` 返回匹配实体
- [ ] `RegexPatternMatcher` 类：至少包含 METRIC（数字+单位）、日期百分比（如 `2024年Q3`）、金额（如 `300亿元`）
- [ ] `DependencyParserMatcher` 类：封装 spaCy `zh_core_web_sm`，提取 SVO 三元组，合并共指关系
- [ ] `RuleBasedExtractor` 类：组合上述三个匹配器（复用同一个 `nlp` 对象），输出 `RawTriple`（subject_text/relation_text/object_text/confidence）
- [ ] PhraseMatcher 词典初始化在构造函数中完成（一次性加载，`nlp` 对象在三个匹配器间共享），`extract()` 调用不重复构建

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

**And** LLM 语义抽取召回率 ≥ 85%（MVP 阶段，Qwen2.5-7B 本地模型；V1+ 目标 ≥ 90%）

**验证标准/Validation Criteria:**
- [ ] `LLMExtractor` 类位于 `src/infrastructure/extraction/llm_extractor.py`
- [ ] 构造函数注入 `udmr_service: UDMRService`（用于路由决策）+ `llm_invoker: LLMInvocationPort`（新增领域端口，用于实际 LLM API 调用）
- [ ] `extract(text, context)` 方法：
  - 构建 Few-Shot Prompt（含 3 个精选中文战略领域示例，覆盖 5+ 实体类型和主要关系类型）
  - 调用 `await udmr_service.decide(task)` 获取 `RoutingDecided`（`route_type` + `selected_model`）
  - 通过 `llm_invoker.invoke(model, prompt)` 发送 LLM 请求（基础设施层 `OllamaAdapter` / `LiteLLMAdapter` 实现）
  - 解析 JSON 输出 → `jsonschema.validate()` 验证 Schema → 类型转换修复 → 返回 `list[RawTriple]` + `list[RawEntity]`
- [ ] LLM 输出 JSON 解析 + Schema 验证失败时重试 1 次（重新请求 + 强调 Schema），第 2 次失败抛出 `LLMExtractionError`，由上游 `HybridEntityExtractor.extract()` 捕获并降级为纯规则基结果
- [ ] LLM 返回合法 JSON 且 Schema 验证通过但 `entities`/`triples` 为空数组时：记录 WARNING 日志（`"LLM returned valid but empty extraction result"`），不触发重试（避免无效调用浪费），直接返回空结果。此场景表明文本中无可识别实体，属于正常业务结果而非错误
- [ ] Few-Shot 示例存储在 `src/infrastructure/extraction/prompts/entity_extraction_examples.py` 中（3 个示例，覆盖 5+ 实体类型和高频关系类型）
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
  - 每个 `ExtractedEntity` → 将 `entity_id`（SHA-256 哈希）作为节点主键（对应 `L5GraphPort.create_entity()` 的 `memory_id` 参数），`entity_type` 映射为 Neo4j 标签，构建节点属性 `dict` 传入。注意：已有 `GraphNode.__post_init__` 要求 `properties` 含 `business_domain`/`entity_type`/`content_hash` 三个字段，需传入填充值以满足此契约
  - 每个 `Triple` → 调用 `L5GraphPort.create_relationship()` 创建关系边
**And** 节点属性包含：`name`, `type`, `mentions`, `properties`, `source`, `created_at`, `business_domain`（固定 `"knowledge"`）, `entity_type`, `content_hash`
**And** 边属性包含：`confidence`, `evidence`, `source`, `created_at`
**And** 写入失败不中断抽取流程（L5 降级为 optional）

**验证标准/Validation Criteria:**
- [ ] `EntityExtractionService` 应用服务位于 `src/application/services/entity_extraction_service.py`
- [ ] `extract_and_persist()` 流程：规则基抽取 → LLM 抽取（并行）→ 冲突仲裁 → Neo4j 写入
- [ ] `extract_and_persist()` 返回完整 `EntityExtractionResult`（含持久化状态）
- [ ] Neo4j 写入失败时降级策略：WARNING 日志 + 不中断 + 结果中 `persisted=False` 标记（通过 `dataclasses.replace(result, persisted=False)` 构造新实例）
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
  - 监听 `DocumentProcessed` 事件（通过 `event_subscriber.subscribe_async()` 异步订阅模式）
  - 调用 `entity_extraction_service.extract_and_persist()`
  - 幂等性：Neo4j 节点/边通过 `MERGE` 语义保证最终一致性。RabbitMQ at-least-once 投递产生的重复 `DocumentProcessed` 事件可接受——重复抽取可能因 LLM 随机性产生略有不同的三元组，但节点 MERGE 避免数据重复。如需严格去重，可在 V1+ 引入 Redis SETNX 幂等性键（`extraction:dedup:{document_id}`）
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

**Composition Root 注册参考模式（lambda 工厂注入）：**

```python
# entity_extractor — SCOPED（每次请求新建，组合三个组件）
container.register(
    "entity_extractor",
    EntityExtractorPort,
    lambda: HybridEntityExtractor(
        rule_extractor=RuleBasedExtractor(nlp=spacy.load("zh_core_web_sm")),
        llm_extractor=LLMExtractor(
            udmr_service=container["udmr_service"],
            llm_invoker=container.get("llm_invoker", _create_ollama_adapter()),
        ),
        arbiter=ConflictArbiter(rule_weight=0.6),
    ),
    lifetime=LifeTime.SCOPED,
    tags=["extraction", "entity", "infrastructure"],
)

# entity_extraction_service — SCOPED
container.register(
    "entity_extraction_service",
    EntityExtractionService,
    lambda: EntityExtractionService(
        extractor=container["entity_extractor"],
        graph_port=container["l5_graph"],
        event_publisher=container["event_publisher"],
    ),
    lifetime=LifeTime.SCOPED,
    tags=["extraction", "entity", "application"],
)

# entity_extraction_event_handler — SINGLETON（启动时注册订阅）
handler = EntityExtractionHandler(
    extraction_service=container["entity_extraction_service"],
    subscriber=container["event_subscriber"],
)
handler.register()  # 内部调用 subscriber.subscribe_async("DocumentProcessed", handler.handle)
container.register(
    "entity_extraction_event_handler",
    lambda: handler,
    lifetime=LifeTime.SINGLETON,
    tags=["extraction", "handler", "application"],
)
```

**验证标准/Validation Criteria:**
- [ ] `entity_extractor` 端口注册到 Composition Root（SCOPED lifetime）
- [ ] `EntityExtractionHandler` 订阅 `DocumentProcessed` 事件（通过 `event_subscriber.subscribe_async()` 异步订阅模式）
- [ ] `EntitiesExtracted` 事件用于跨服务/跨进程通知（如通知 Story 3-4 RRF 融合服务），不在本 Story 内注册同进程 handler 监听
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
  - **注意：** `EntityRelation` 等同于 AC-3 中引用的 `RawTriple`——两者是同一概念的不同命名。规则基和 LLM 抽取器均产出一组 `EntityRelation`，输入到 `ConflictArbiter` 进行融合。
- [ ] **新增** `RawEntity` frozen dataclass（`src/domain/value_objects/extraction_result.py`）：
  - `name: str`, `type: EntityType`, `mentions: tuple[str, ...]`, `properties: dict[str, Any]`, `source: str`
  - 提取阶段的临时实体表示（不含 entity_id），由 `RuleBasedExtractor` 和 `LLMExtractor` 产出，输入到 `ConflictArbiter` 融合后生成 `ExtractedEntity`（含 entity_id）
  - `entity_id` 生成放在 `HybridEntityExtractor`（基础设施层），在 `ConflictArbiter` 融合之后统一计算 SHA-256 哈希（`name + type.value` 为输入）
- [ ] **扩展** `RelationshipType` StrEnum（`src/infrastructure/storage/neo4j/models.py`）：
  - 新增 7 种关系类型：`COMPETES_WITH`, `SUPPLIES_TO`, `INVESTS_IN`, `OWNS`, `LAUNCHED`, `OPERATES_IN`, `REGULATED_BY`（保留全部 6 种已有值，总计 13 种）
  - 注意：`RelationshipType` 作为基础设施层 DTO 的枚举，其扩展不影响领域层

#### 统一端口定义注册与管理 (Port Contract)
- [ ] **新增** `EntityExtractorPort` 领域端口（`src/domain/ports/entity_extractor.py`）：
  - `extract(text, context) -> EntityExtractionResult`（async）
  - `extract_batch(texts) -> list[EntityExtractionResult]`（async）
- [ ] **新增** `EntityExtractionService` 应用服务（`src/application/services/entity_extraction_service.py`）：
  - 构造注入：`EntityExtractorPort`, `L5GraphPort`, `EventPublisher`
  - `extract_and_persist(text, document_id, tenant_id) -> EntityExtractionResult`
  - `extract_and_persist_batch(texts, document_id, tenant_id) -> list[EntityExtractionResult]`
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
| `ConfigurationError` | EXCEPTION_101 | spaCy 模型未安装/种子词典文件不存在 |

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
- `src/domain/ports/llm_invocation.py` → 仅 `typing` 标准库。`LLMInvocationPort` Protocol 定义了 LLM API 调用抽象：
  ```python
  @runtime_checkable
  class LLMInvocationPort(Protocol):
      async def invoke(self, model: str, messages: list[dict[str, str]],
                       temperature: float = 0.1, max_tokens: int = 4096,
                       response_format: dict[str, str] | None = None) -> str:
          """调用 LLM API 并返回原始文本响应（通常为 JSON 字符串）。
           败时抛出 LLMExtractionError。"""
      async def health_check(self) -> bool:
          """检查 LLM 服务可用性。"""
  ```
  `OllamaAdapter`（基础设施层）和 `LiteLLMAdapter` 均实现此端口。`response_format` 参数透传 `{"type": "json_object"}` 等 Ollama/OpenAI 格式参数
- `src/infrastructure/extraction/rule_engine/` → 可依赖 `spacy`（第三方库，三个匹配器共享 nlp 对象）
- `src/infrastructure/extraction/llm_extractor.py` → 可依赖 `httpx`（通过 UDMR 间接调用 LLM）

---

## 📋 Tasks / Subtasks

### Task 0: SDD 规范定义 (AC: 全部)
- [ ] **0.1** 创建 `EntityType` StrEnum 值对象（9 种实体类型，含 `OTHER` 兜底类型）
- [ ] **0.2** 创建 `Triple` frozen dataclass 值对象（含 `__post_init__` 验证）
- [ ] **0.3** 创建 `ExtractedEntity`、`EntityExtractionResult`、`ExtractionStatistics` frozen dataclass
- [ ] **0.4** 创建 `EntityRelation` frozen dataclass 值对象
- [ ] **0.5** 创建 `EntityExtractorPort` 领域端口 Protocol
- [ ] **0.6** 扩展 `RelationshipType` StrEnum（基础设施层 DTO）
- [ ] **0.7** 新增 `EntityExtractionError` (245) 和 `LLMExtractionError` (304) 领域异常
- [ ] **0.8** 更新异常体系：`__all__`、`__init__.py`、`_code_ranges.py`（`_CLASS_TO_SUBDOMAIN`: `"EntityExtractionError": "entity"`, `"LLMExtractionError": "external"`）、`EXCEPTION_HTTP_MAP`（精确注册: `EntityExtractionError: 422`, `LLMExtractionError: 502`）
- [ ] **0.9** 新增 `EntitiesExtracted` 领域事件定义
- [ ] **0.10** 更新 `configs/event_channels.yaml` 和 `channel_router.py`

### Task 1: 规则基抽取引擎 (AC-3)
- [ ] **1.1** TDD 红：编写 `PhraseMatcherAdapter` 单元测试（按类型批量注册/匹配/空词典）
- [ ] **1.2** TDD 绿：实现 `PhraseMatcherAdapter` — 封装 spaCy `PhraseMatcher`，共享 `nlp` 对象
- [ ] **1.3** TDD 红：编写 `RegexPatternMatcher` 单元测试（METRIC/日期百分比/金额 3 个模式）
- [ ] **1.4** TDD 绿：实现 `RegexPatternMatcher` — 编译预定义正则模式
- [ ] **1.5** TDD 红：编写 `DependencyParserMatcher` 单元测试（SVO 三元组提取）
- [ ] **1.6** TDD 绿：实现 `DependencyParserMatcher` — 封装 spaCy 依存句法
- [ ] **1.7** TDD 红：编写 `RuleBasedExtractor` 单元测试（三匹配器共享 nlp + 准确率验证）
- [ ] **1.8** TDD 绿：实现 `RuleBasedExtractor` — 组合匹配器，产出 `RawTriple`
- [ ] **1.9** TDD 绿：集成实体种子词典文件（JSON 格式，按实体类型组织）

### Task 2: LLM 语义抽取 (AC-4)
- [ ] **2.1** TDD 红：编写 `LLMExtractor` 单元测试（Mock UDMR Service 验证 Prompt 构建）
- [ ] **2.2** TDD 绿：实现 `LLMExtractor` — UDMR 路由 → LLM 调用 → JSON Schema 解析
- [ ] **2.3** TDD 绿：实现 Few-Shot 示例集（3 个精选示例，覆盖 5+ 实体类型）
- [ ] **2.4** TDD 绿：实现 JSON 解析重试机制（失败 → 重试 1 次（3s 退避）→ 第 2 次失败抛出 `LLMExtractionError`）
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
| 规则基抽取精确率 (Precision) | ≥ 80%（ORGANIZATION/PERSON/PRODUCT ≥ 90%，文本长度 < 2000 tokens） | 标注测试集验证（≥50 句中文战略文本，全实体+三元组标注） |
| LLM 语义抽取召回率 (Recall) | ≥ 85%（MVP 阶段，Qwen2.5-7B 本地模型） | 同上标注测试集（≥50 句，按关系类型分层抽样） |
| 冲突仲裁 F1 | ≥ 85% | 同上标注测试集（人工标注的三元组作为金标） |
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
| `tests/unit/domain/value_objects/test_raw_entity.py` | 单元 | RawEntity/EntityRelation 值对象 |
| `tests/unit/domain/value_objects/test_extraction_result.py` | 单元 | EntityExtractionResult/ExtractedEntity/ExtractionStatistics |
| `tests/unit/domain/services/test_conflict_arbiter.py` | 单元 | ConflictArbiter 融合逻辑 |
| `tests/unit/infrastructure/extraction/test_phrase_matcher_adapter.py` | 单元 | PhraseMatcherAdapter |
| `tests/unit/infrastructure/extraction/test_regex_matcher.py` | 单元 | RegexPatternMatcher |
| `tests/unit/infrastructure/extraction/test_dep_parser_matcher.py` | 单元 | DependencyParserMatcher |
| `tests/unit/infrastructure/extraction/test_rule_extractor.py` | 单元 | RuleBasedExtractor 组合 |
| `tests/unit/infrastructure/extraction/test_llm_extractor.py` | 单元 | LLMExtractor（Mock UDMR + LLMInvocationPort） |
| `tests/unit/application/services/test_entity_extraction_service.py` | 单元 | EntityExtractionService（Mock 端口） |
| `tests/unit/application/event_handlers/test_entity_extraction_handler.py` | 单元 | EntityExtractionHandler |
| `tests/unit/domain/exceptions/test_code_ranges.py` | 单元 | 异常编码唯一性验证（更新已注册异常） |
| `tests/contracts/test_port_contract_entity_extraction.py` | 契约 | 端口契约兼容性 |
| `tests/integration/test_entity_extraction_integration.py` | 集成 | 端到端集成测试（含并发场景：5 并发 DocumentProcessed 事件 → 验证无重复节点/边） |
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
| `src/domain/exceptions/external_exceptions.py` | 外部异常基类 | ThirdPartyError（EXCEPTION_301），LLMExtractionError（EXCEPTION_304）继承自此 |
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
| `src/infrastructure/extraction/rule_engine/phrase_matcher_adapter.py` | infrastructure | `PhraseMatcherAdapter`（spaCy 内置 PhraseMatcher） |
| `src/infrastructure/extraction/rule_engine/regex_matcher.py` | infrastructure | `RegexPatternMatcher` |
| `src/infrastructure/extraction/rule_engine/dep_parser_matcher.py` | infrastructure | `DependencyParserMatcher` |
| `src/infrastructure/extraction/rule_engine/rule_extractor.py` | infrastructure | `RuleBasedExtractor` 组合引擎 |
| `src/infrastructure/extraction/rule_engine/seed_data/entities.json` | infrastructure | 种子实体词典（PhraseMatcher 用，MVP 50-100 条） |
| `src/infrastructure/extraction/llm_extractor.py` | infrastructure | `LLMExtractor`（UDMR 路由 + Few-Shot + CoT） |
| `src/infrastructure/extraction/prompts/__init__.py` | infrastructure | Prompt 模板初始化 |
| `src/infrastructure/extraction/prompts/entity_extraction_examples.py` | infrastructure | Few-Shot 示例集（3 个） |
| `src/infrastructure/external_services/llm/ollama_adapter.py` | infrastructure | `OllamaAdapter`（实现 `LLMInvocationPort`） |

---

## ⚠️ 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM 中文实体抽取质量不稳定 | 召回率 < 90% | 3 个精心设计的中文战略领域 Few-Shot 示例 + CoT 分步推理 |
| spaCy `zh_core_web_sm` 在战略文本上精度不足 | 依存句法 SVO 提取准确率低 | `DependencyParserMatcher` 添加领域特定规则补充（如 "X投资Y"、"X收购Y" 式模板） |
| LLM 调用延迟超 10s | 整体延迟超标 | UDMR 本地路由（Ollama+Qwen2.5）优先；重试策略增加超时控制，MVP 接受 < 15s |
| PhraseMatcher 词典过大导致 spaCy pipeline 启动慢 | Doc 处理延迟增加 | 种子词典限 500 条（spaCy PhraseMatcher 在 500 条规模下匹配耗时 < 1ms）；超出时按频率 Top-K 筛选 |

---

## 📝 Dev Notes

### 领域知识要点
- 实体抽取准确率不追求 100%——接受噪声，Story 3-3（领域词典）和 Story 12-1（实体消歧）将迭代改进
- `Triple.confidence` 不是最终信仰——下游 Story（3-4 RRF 融合）会把它当做 Graph 信号的权重
- Neo4j 写入是 optional 的——如果 Neo4j 不可用，抽取结果仍在 `EntityExtractionResult` 中可用（`persisted=False`）

### 测试约定
- Mock LLM/UDMR 调用（除非集成测试显式启用本地 LLM），Mock 策略见 `tests/unit/infrastructure/extraction/` fixture
- 单元测试中 `RuleBasedExtractor` 需 mock `spaCy` 模型（`Morphology` 需 `label_data`），参考 `tests/conftest.py` 中的 `mock_nlp` fixture
- `ConflictArbiter` 使用固定测试数据（`src.domain.services.conflict_arbiter`），不依赖外部模型
- 测试覆盖率门禁：领域层 ≥ 90%、应用层 ≥ 85%、基础设施层 ≥ 80%

### 注意事项
- spaCy `zh_core_web_sm` 模型需在测试前下载：`python -m spacy download zh_core_web_sm`（约 45MB）；应确认 CI runner 镜像已预装（参见 Epic 0）
- 三个规则基匹配器共享同一个 `nlp` 对象以降低内存和初始化成本，`RuleBasedExtractor` 构造函数接受 `nlp` 参数注入
- 单元测试中 `RuleBasedExtractor` 需 mock `nlp` 对象（`Morphology` 需 `label_data`），参考 `tests/conftest.py` 中的 `mock_nlp` fixture
- **nlp 对象并发安全：** spaCy `nlp` 对象在 C 扩展层释放 GIL（通过 `nogil`），允许 `asyncio.to_thread` 中并发调用。但 tokenizer 缓存等内部状态不是线程安全的。对于 `extract_batch` 的高并发（50+ 文本），建议每个 worker 使用独立 `nlp` pipeline 或 `threading.Lock` 序列化调用
- **spaCy 依赖：** 需将 `spacy = "^3.7.0"` 添加到 `pyproject.toml` 的 `[tool.poetry.dependencies]` 中（Task 0 前置步骤）。在 `tests/conftest.py` 中添加 `spacy` 可用性跳过标记，当 `zh_core_web_sm` 模型未安装时跳过相关测试并给出明确提示
- **Mock 策略补充：** 单元测试中 `UDMRService.decide()` Mock 返回 `RoutingDecided(route_type="local", selected_model="qwen2.5:7b")`；`LLMInvocationPort.invoke()` Mock 返回固定 JSON 字符串（含 entities + triples）；失败场景 Mock `invoke()` 抛出 `LLMExtractionError` 或返回不合规 JSON

---

## 🔧 技术栈

| 组件 | 版本 | 用途 |
|------|------|------|
| `spaCy` | ^3.7+ | PhraseMatcher（实体短语匹配）+ DependencyParser（SVO 三元组）— 需添加至 pyproject.toml 依赖 |
| `zh_core_web_sm` | latest | spaCy 中文模型（分词/词性标注/依存句法） |
| `httpx` | ^0.27+ (已有) | LLM HTTP 调用（通过 UDMR 路由间接） |
| LiteLLM | ^1.28+ (已有) | LLM 统一接口（LLMInvocationPort 的云端实现，间接依赖） |

---

## 📝 Dev Agent Record

### Agent Model Used

GPT-5.2 / Claude Opus 5 (选择理由：complex architecture context + multi-agent research required)

### Debug Log References

### Completion Notes List

### File List
