# Story 4.1d: Skills 混合数据增强（外部+内部混合数据型 Skills 完善）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 工具工程师,
**I want** 10 个混合数据型 Skills（swot-tows / ansoff-matrix / value-curve-analysis / ge-mckinsey-matrix / space-matrix / value-chain-analysis / vrio-framework / bsc-scorecard / kpi-tree / change-management）达到可实用分析成熟度（Schema 模板 + 工作坊方法论 + 部分外部数据）,
**So that** Agent 调用这 10 个 Skills 时基于结构化 Schema 模板 + 企业内部数据 + 行业基准，输出可执行的分析结果。

### 业务价值

Story 4.1b 已交付数据采集基础设施（DataSourcePort + 8 适配器 + Redis 缓存 + 新鲜度评分 + `$DATA_SOURCE` 标记解析），Story 4.1c 已完成 6 个外部数据型 Skills 成熟化 + 生产链路双入口接线（`StrategicAnalysisUseCase` / `RunToolChainUseCase` 均注入 `extensions["tool_metadata"]`）。本 Story 让 10 个混合数据型 Skills 复用同一基础设施达到可实用成熟度——与 4-1c 的关键差异：**内部数据（企业内部优势/资源/KPI/业务数据）是分析主体，外部数据源（World Bank / IMF 等）仅提供行业基准参照**，内部数据通过「Schema 模板 + 工作坊方法论」采集（业界咨询公司标准做法）。

本 Story 是**纯内容成熟化 Story**：10 个 SKILL.md frontmatter 声明 + SOP 成熟化 + references/templates 资源 + 测试交付，**零 Python 生产代码改动**（生产链路已由 4-1c 接线完毕，声明即生效）。

**来源:** [`epics_v1.0.md`](../../planning-artifacts/epics_v1.0.md) - Epic 4: 战略工具箱，Story 4.1d（P0-7，line 1004-1047）
**前置依赖:** Story 4.1b（✅ done，数据采集基础设施 + 8 适配器）/ Story 4.1a（✅ done，Skills 骨架 + 五阶段引擎）/ Story 4.1c（✅ done，6 Skill 成熟化模式 + 双入口接线 + 共享契约断言库）
**后续依赖:** Story 4.1e（7 个内部框架 Skills，复用本 Story 的模板与工作坊方法论模式）

### ⚠️ Story 范围澄清（重要）

**本 Story 交付（范围边界）：**

- 10 个 SKILL.md frontmatter `data_sources` 白名单声明（统一 2 源外部基准，见「端口与数据契约」SSOT 表）+ `input_schema`/`output_schema` JSON Schema 定义
- 10 个 SKILL.md body SOP 成熟化（≤500 行硬约束，9 章节结构对齐 4-1c 契约）
- 每个 Skill 配套 `references/` 三件套（data_fusion.md 内外数据融合规范 / scoring_anchors.md 评分锚点 / workshop_guide.md 工作坊引导）与 `templates/` 内部数据采集模板（**目录新建**——当前 10 个目标 Skill 的 templates/ 目录均不存在；既有 `references/` 与 `scripts/` 均为空目录，本 Story 不触碰 scripts/）
- 内部 Schema 模板与 `input_schema` 字段一一对应（双向断言，本 Story 核心增值，AC-3）
- 共享契约断言库 `skill_mixed_data_contracts.py` + 10 个 Skill 单元测试 + 集成测试 + 架构验证测试 + BDD 验收测试
- 既有回归网调整（**两处移出 + 一处重构**，Round 1 D1-A 发现第三处回归点 / Round 2 设计重写其处理方式）：`NON_TARGET_SLUGS` 17 → 7（两处：`test_pestel_analysis_data_collection.py` + `test_arch_skill_data_collection.py`，移出 10 个 4-1d 目标；周边 docstring「17 个」字样同步）+ `test_frontmatter_data_sources.py:131-164` **测试语义中间态安全化重构**（原稿「零修改」不成立——其非声明组空 tuple 断言在 10 Skill 填声明后必红；Round 1 曾改为「DECLARING_SLUGS 6→16 扩清单」亦经 Round 2 回归核查证伪——非空断言致并行期必红；最终方案见 Subtask 1.4：断言改为「物理非空者必 ∈ SSOT 并集 16」）
- IO 契约 SSOT 扩充：`tests/acceptance/contracts/skill_io_schemas.yaml` 追加 10 个条目（单一 SSOT 文件，不新建）

**不在本 Story 范围（明确划出）：**

- **任何 Python 生产代码改动** → 零改动（frontmatter 解析链路 `frontmatter.py:154` / 双入口接线 `strategic_analysis.py` + `run_tool_chain.py` / 白名单校验 `data_source_resolver.py:240` 均为 4-1b/4-1c 交付物，本 Story 声明即生效）；若实施中发现必须改代码，先停下核对本文档「端口与数据契约」节
- **新增数据源适配器 / UNSD / OECD** → 后续 Story（4-1b PoC v2 已验证不可用）
- **工具输出 Schema 强制验证（Pydantic 运行时校验）** → Story 4.3
- **`skill_io_schemas.yaml` 既有 6 条目的 data_sources.items 字段级化 + description 命名对齐** → Story 4.3（4-1c R2-F7 既定留项，本 Story 新增条目沿用现行粒度——data_sources.items 保持与 4-1c 条目相同的结构规范，不单独升级）
- **7 个内部框架 Skills** → Story 4.1e
- **StrategicAnalysisUseCase 的 composition_root 注册 + 接口层入口** → 入口 Story（4-1c R1-P2-13 既定 Defer，FR-IF-01 锚点）
- **内部数据的确定性注入通道（类似 `DATA_SOURCES` preamble 的 `INTERNAL_DATA` 机制）** → 显式不实施（决策 D5：内部数据经 `ToolCall.arguments` 进入 Think prompt 是既有语义，模板是「采集期」工具而非「执行期」通道；无生产消费方诉求前不新增机制）

### ⚠️ 命名规范声明（强制，覆盖 Epic 字面表述）

**用户约束（4-1c 实施期确立）：禁止使用故事编号命名编码开发。** 全部新增测试/源码文件采用功能性命名（无 `_4_1d` 后缀），即使 epics_v1.0.md line 1032 / 1038-1041（Round 1 勘正行号）写了带编号的文件名（`test_*_4_1d.py` 等）。docstring 中引用 "Story 4.1d" 字样不受此限。本 Story 文件所有文件名以「文件清单 File List」节为准。

**slug 命名陷阱：** 架构文档 `architecture.md:2676` 与 epics 中写作 `change-management-model`，**实际 slug 是 `change-management`**（`skill_manifest.py:37` UUID 映射 / `TOOLS.md:30` 直接锚定；`strategic_tool_catalog.py` 经 tool_id UUID（…023，name="变革管理模型" :897）**间接**锚定——catalog 全文无 slug 字面量，Round 1 D1-A 勘正措辞）。实施必须沿用现有 slug `change-management`，禁止新建 `change-management-model` 目录。

---

## 🛡️ 硬约束声明（CLAUDE.md §5）

### 领域零依赖（FR-AR-01）

- 本 Story **零 Python 生产代码改动**（纯 YAML/Markdown 资源 + 测试交付）；若实施中发现必须触碰 `src/` 下 Python 文件，该文件按其所属层遵守依赖规则——domain 层仅允许 Python 标准库（`.importlinter` 强制，CI 失败）

### 异常体系强制

- **禁止** `raise ValueError` / 手动 `raise HTTPException` / 继承内置 Exception
- 所有异常走 `src/domain/exceptions/` 体系 + `ExceptionHandlers` 自动映射
- 提交前三条 grep 自查（零输出）：
  - `grep -rn "raise ValueError" src/`
  - `grep -rn "raise HTTPException" src/`
  - `grep -rn "class.*Exception)" src/domain/exceptions/ | grep -v "DomainError\|BaseException\|SystemException\|BusinessException\|ExternalException\|ThirdPartyError\|Error)"`

### 抑制告警禁止

- **禁止** `# noqa` / `# type: ignore` / `# pylint: disable`；**禁止**修改阈值/规则消除告警——必须修复根因
- 测试文件同样适用：fixture 与测试参数必须带类型注解（4-1c R1-P0-1 教训：31 处 `# type: ignore` 全部因缺注解产生）

### Commit & Push 规范

- 提交信息**禁止**任何 AI 辅助署名（Co-Authored-By: Claude 等）
- **禁止** `--no-verify` 绕过 pre-commit hooks
- **禁止** 修改 `.importlinter` 中已合入的架构依赖规则（CLAUDE.md §5）
- **禁止** 修改已合入的 alembic migration（本 Story 不涉及）
- 直接在 main 分支开发（项目约定）

### Skills 内容约束（Anthropic Claude Code Skills 对标）

- **L2 SKILL.md ≤500 行**（架构 §1.5 P2 约束；`validators/line_count_validator.py` 未实现——行数约束由本 Story 单测断言 + 架构测试承担，禁止声称"CI 已有校验"）；SOP 成熟化膨胀时按 Hub-and-Spoke 拆分到 `references/*.md`，SKILL.md 本体保持路由+摘要
- **frontmatter 必需字段**：`slug`（kebab-case）/ `name` / `version`（SemVer）——`frontmatter.py:32` `REQUIRED_FIELDS` 强制
- **负向触发章节强制**（架构原则 P6）：`when_not_to_use` + body「负向触发」章节
- **数据源声明合法值**：`data_sources[].name` 仅限 8 个注册源（kebab-case）：`world-bank` / `imf` / `eurostat` / `uspto` / `ipcc` / `newsapi` / `tavily` / `china-nbs`；`api_type` 仅限 `rest_json` / `sdmx_json` / `csv_download` / `crawler`（`DataSourceApiType` 枚举值）；`ttl_seconds ∈ [60, 2592000]`
- **fail-fast 保护自动生效**：声明 `data_sources` 后，frontmatter 解析失败抛 `SkillLoadError` 而非静默回退（`loader.py:53-75` `_frontmatter_declares_data_sources` 行级探测）——声明务必保证 YAML 语法正确
- **沙箱无网络不变量**：SOP 引导 LLM 生成的沙箱代码通过 `$DATA_SOURCE("name", "query")` 标记采集外部基准，**禁止**引导任何形式的沙箱内网络访问；注入数据经全局 `DATA_SOURCES` dict 读取（`data_source_marker.py` 注入协议：失败位为 `None`、同源多 query 键 `name#k`、防御性 `.get()` 读取）
- **SOP `input_examples` 章节禁止写入真实 API Key 字符串**：必须使用环境变量引用形式或占位符 `<KEY>`；**Key 安全红线**：异常消息/日志/模板文件零 API Key 泄露
- **声明 Key 敏感源（newsapi/tavily）的 Skill 必须在 SOP 失败处理章节文档化 Key 缺失降级话术**（「未注册」411 语义 → 基于内部数据 + 其余源继续分析并标注数据缺口）——本 Story 10 个 Skill 中 **7 个**声明含 newsapi 或 tavily（swot-tows / value-curve / ge-mckinsey / value-chain / vrio / kpi-tree / change-management，见 SSOT 表）

### 代码质量门禁

- `poetry run ruff check src/ tests/` 通过（行宽 128，规则 E/F/I/N/W）
- `poetry run mypy src/` 通过
- `poetry run pytest tests/ -n 8` 并行通过，连续 5 次无随机失败
- `pre-commit run --all-files` 通过

---

## 🎯 领域异常契约

> **原则**：异常是领域契约的一部分。本 Story **不新增领域异常**（显式决策，见决策表 D4）。

### 不新增异常的决策声明

本 Story 为纯内容成熟化 Story（零 Python 生产代码改动），全部失败路径已由 4-1b/4-1c 异常体系覆盖，**新增同义异常违反"禁止同义异常重复定义"红线**：

| 场景 | 复用异常 | 编码 | 依据 |
|------|---------|------|------|
| `$DATA_SOURCE` 标记语法错误 | `ValidationError` | EXCEPTION_201 | 4-1b 既定（标记解析器） |
| 数据源未在白名单声明 / 缺 tool_metadata | `BusinessRuleViolationError` | EXCEPTION_207 | 4-1b 既定（白名单语义） |
| 数据源 5xx/连接失败/未注册（Key 缺失） | `DataSourceUnavailableError` | EXCEPTION_411 | 4-1b 既定 |
| 429 限流 | `DataSourceRateLimitError` | EXCEPTION_412 | 4-1b 既定 |
| 数据源超时（重试耗尽） | `TimeoutError`（external） | EXCEPTION_302 | 4-1b 既定（`data_source_exceptions.py:10` 复用语义；Round 1 D1-C 勘正补行——原稿遗漏，与 Task 0 checklist / D4 决策引用不一致） |
| 响应解析失败（不可重试） | `DataSourceResponseError` | EXCEPTION_413 | 4-1b 既定 |
| 配置缺失（无 API Key / resolver 未注入） | `ConfigurationError` | EXCEPTION_101 | 4-1b 既定 |
| SKILL.md frontmatter 解析失败（含 data_sources 项非法） | `FrontmatterParseError` | 既有 | `frontmatter.py:45`，4-1b 已扩展字段路径 context |
| Skill 不存在 / 加载失败 | `SkillNotFoundError` / `SkillLoadError` | EXCEPTION_387 / 388 | tool 子域既有 |

### 4-1c 留项收敛状态确认（Task 0 必做）

4-1c Defer 节曾登记「frontmatter `required_fields` 无类型校验（R1-P2-10）+ `ttl_seconds` YAML 字符串 TypeError 旁路（R1-P2-11）→ 归属 4-1b 审查周期或 4.1d 前收敛」。**调研确认：已由 4-1b 第三审查周期收敛**（commit `0d550dda` 红线组 G3：`src/domain/value_objects/data_source.py:98-125` `DataSourceRef.__post_init__` 全量类型门禁——name/url/`ttl_seconds` 非 int/`required_fields` 标量均抛 `EntityValidationError` 242，应用层 `except DomainError` 包裹自动收敛为 `FrontmatterParseError`）。本 Story **不重复实施**，仅在 Task 0 执行回归验证：

- [ ] `poetry run pytest tests/unit/application/skills/test_frontmatter_data_sources.py tests/unit/domain/value_objects/ -v` 全绿（既有类型门禁回归网）
- [ ] BDD 异常路径场景纳入 Edge Cases（207/411 断言 `error.code` + `error.message`）

---

## 🎯 测试隔离约束

### TestTenant UUID 前缀

- 集成/验收测试缓存键带租户前缀：`sisys:cache:datasource:{tenant}:{source}:{query_hash}`，租户 = `f"it-{uuid.uuid4().hex[:8]}"` / `f"acc-{uuid.uuid4().hex[:8]}"`
- teardown 仅 `delete_pattern` 清理本测试租户前缀键（多租户场景清理全部创建的前缀），禁止全库 flush
- 范本：`tests/integration/application/test_skill_data_collection.py`（4-1c 交付，双租户形态）

### 外部服务测试策略

- **单元测试（Skill 内容）**：直接真实加载真实 SKILL.md（`InMemorySkillLoader().load_sop(slug)`，**禁止 mock**）；涉及适配器行为一律 stub/fake，禁止真实外网调用
- **集成测试**：真实 Engine + 真实 `DataSourceResolverService` + 真实 Redis（测试端口，`real_redis` fixture，ping 失败 `pytest.skip()`）；Mock 仅限 LLM/Sandbox（`AsyncMock`）/数据源适配器（`_StubAdapter` 可编程替身 + `call_count` 计数）
- **验收测试**：同集成测试真实服务策略 + `_FakeDataSourceAdapter`（behavior: ok/unavailable/rate_limit/bad_response + `call_count`）
- **架构测试**：8 个真实适配器实例化（Key 敏感源用占位 Key、china-nbs 注入 AsyncMock crawler），仅读取 `get_metadata()` 零网络

### BDD 步骤函数

- **禁止** `@pytest.mark.asyncio`（导致 context 数据丢失），使用场景级共享 `event_loop` fixture + `context["_loop"].run_until_complete(coro)` helper
- **Redis 客户端场景级独立创建**（4-1c 探针实测教训：session 级共享客户端跨场景复用抛 RuntimeError "Event loop is closed"——连接池绑定已关闭循环）
- 同一中文文本可能需同时支持 given/when 装饰器

### 并发与事件循环

- `asyncio.Lock` 必须声明为**类变量**（非实例变量）
- pytest-xdist 默认开启（`-n auto --dist loadgroup`），共享 Redis 缓存键的测试文件必须 `pytestmark = [pytest.mark.integration, pytest.mark.xdist_group("data-source-cache")]`（list 形式，**复用 4-1b/4-1c 既有分组**，同一 worker 串行）
- 并发采集断言以 `call_count` 计数断言（Stub 替身计数）

---

## 🌐 端口与数据契约

### 端口契约（本 Story 不新增端口 — 显式决策 D4）

复用既有端口，禁止新增同义端口：

| 端口 | 层 | 文件 | 本 Story 用法 |
|------|----|------|--------------|
| `DataSourcePort` | domain | `src/domain/ports/data_source.py:52` | 8 适配器实现（4-1b 已交付，零改动） |
| `DataSourceResolverPort` | application | `src/application/ports/data_source_resolver.py:19` | Engine 白名单编排（4-1b 已交付，零改动） |
| `SkillLoaderPort` | application | `src/application/ports/skill_loader.py:108`（`load_sop` :134） | L2 `load_sop` 消费（4-1c 已接线，零改动） |

### 数据契约（本 Story 核心 SSOT）：10 个混合数据型 Skills 数据源白名单声明表

> **唯一事实源（Single Source of Truth）**：下表是 10 个 SKILL.md frontmatter `data_sources` 声明的唯一事实源（name 有序集合；url/api_type/ttl 三字段的逐字基准是下方「适配器对齐表」= `ADAPTER_SSOT` 常量，Round 1 D2-A 勘正指代拆分）。Task 0 将其固化为契约断言（`skill_mixed_data_contracts.py` 的 `MIXED_SKILL_DATA_SOURCES` 常量），Task 2-11 实施内容必须与两表逐字一致，禁止实施期临时增删。

**统一 2 源策略（决策 D2）**：混合数据型的内部数据是分析主体，外部源仅提供行业基准参照。每个 Skill 声明 2 个外部源做双源交叉验证（对齐 4-1c disruptive-innovation 2 源终态与 4-1c D4/D8 务实精神——Round 1 勘正加前缀防与本 Story 同编号决策歧义）；映射依据：Epic 明确指定的源优先（swot-tows / ge-mckinsey / change-management），模糊描述（行业增长率/基准/标准/能力）按工具语义匹配适配器数据集能力。

| Skill slug | 声明数据源（有序） | 外部基准采集目标 | 内部数据（模板采集主体） | Key 敏感 |
|------------|------------------|-----------------|------------------------|---------|
| `swot-tows` | `newsapi` + `tavily` | 行业时政新闻（NewsAPI）、Web 竞争情报（Tavily）→ 机会/威胁外部印证 | 内部优势/劣势清单（资源/能力/短板） | ⚠️ 双敏感 |
| `ansoff-matrix` | `world-bank` + `imf` | GDP/行业增长指标（WB `NY.GDP.MKTP.CD` 等）、WEO 增长展望（IMF `NGDP_RPCH`）→ 市场吸引力 | 内部产品 × 市场现有位置（渗透/开发/延伸/多样化） | — |
| `value-curve-analysis` | `tavily` + `newsapi` | 竞品价值要素情报（Tavily）、市场动态（NewsAPI）→ 行业战略轮廓基准 | 内部产品价值要素当前水平 + 目标值 | ⚠️ 双敏感 |
| `ge-mckinsey-matrix` | `world-bank` + `tavily` | 行业吸引力宏观指标（WB，Epic 明确）、市场增速情报（Tavily） | 业务单元数据（市场份额/销售额/利润率） | ⚠️ tavily |
| `space-matrix` | `world-bank` + `imf` | 宏观环境稳定性（WB 治理/通胀指标）、产业实力展望（IMF WEO）→ ES/IS 外部维度 | 4 维度评分（FS 财务实力 / CA 竞争优势） | — |
| `value-chain-analysis` | `tavily` + `china-nbs` | 行业价值链结构情报（Tavily）、行业统计对标（国统局） | 内部活动清单（主要/支持活动）+ 成本数据 | ⚠️ tavily |
| `vrio-framework` | `uspto` + `tavily` | 行业专利/技术能力密度（USPTO）、行业能力情报（Tavily）→ 稀缺性/可模仿性参照 | 内部资源与能力清单 | ⚠️ tavily |
| `bsc-scorecard` | `china-nbs` + `world-bank` | 行业 KPI 统计对标（国统局 `sj/zxfb`）、宏观基准（WB） | 内部 KPI 现值 + 战略规划文件要点 | — |
| `kpi-tree` | `china-nbs` + `newsapi` | 行业指标统计（国统局）、行业绩效动态（NewsAPI）→ KPI 目标值参照 | 内部 KPI 现值 + 数据仓库导出 | ⚠️ newsapi |
| `change-management` | `newsapi` + `tavily` | 行业变革趋势新闻（NewsAPI，Epic 明确）、变革实践情报（Tavily，Epic 明确） | 内部变革数据 + 利益相关者立场评估 | ⚠️ 双敏感 |

**适配器 url/api_type/ttl 对齐表**（复用 4-1c `skill_data_collection_contracts.py` 的 `ADAPTER_SSOT` 常量，本 Story 涉及 6 个源；**禁止复制，必须 import**——R2-F3 单一来源原则）：

| 数据源（name） | url | api_type | ttl_seconds | confidence | 本 Story 消费方 |
|----------------|-----|----------|-------------|------------|---------------|
| `world-bank` | `https://api.worldbank.org/v2` | rest_json | 604800（7d） | 0.95 | ansoff / ge-mckinsey / space / bsc |
| `imf` | `https://www.imf.org/external/datamapper/api/v1` | sdmx_json | 604800（7d） | 0.95 | ansoff / space |
| `uspto` | `https://search.patentsview.org` | rest_json | 2592000（30d） | 0.90 | vrio |
| `newsapi` | `https://newsapi.org` | rest_json | 21600（6h） | 0.75 | swot / value-curve / kpi-tree / change-management |
| `tavily` | `https://api.tavily.com` | rest_json | 86400（1d） | 0.70 | swot / value-curve / ge-mckinsey / value-chain / vrio / change-management |
| `china-nbs` | `https://www.stats.gov.cn` | crawler | 86400（1d） | 0.90 | value-chain / bsc / kpi-tree |

> **三方对齐契约（Task 13 架构测试断言）**：
> 1. frontmatter `data_sources[].name` ⊆ 上述 8 个注册源集合
> 2. frontmatter `data_sources[].url` 字面值 == 适配器 `get_metadata().url`
> 3. frontmatter `data_sources[].api_type` ∈ `DataSourceApiType` 枚举
> 4. frontmatter `data_sources[].ttl_seconds ∈ [60, 2592000]` 且与 `ADAPTER_SSOT` 逐字一致

**DataSourceRef 字段规则（frontmatter 声明格式，对齐 4-1c）：**

```yaml
data_sources:
  - name: world-bank            # 必须与适配器 get_metadata().name 一致（kebab-case）
    url: https://api.worldbank.org/v2   # 必须与对应适配器 get_metadata().url 一致
    api_type: rest_json         # DataSourceApiType 枚举值（小写）
    ttl_seconds: 604800         # 对齐 ADAPTER_SSOT；范围 [60, 2592000]
    required_fields:            # 可选，该 Skill 消费此源时必需的 payload 字段（声明性元数据）
      - indicator
      - value
```

`required_fields` 是声明性元数据（`data_source.py:84-89`：不触发通用运行时校验，运行时结构校验由各适配器 `_extract_*` 承担）；类型门禁已由 4-1b 审查周期收敛（标量 → `EntityValidationError` 242 → `FrontmatterParseError`）。

### 内部数据契约（本 Story 特有）

**内部数据流转（既有语义，零代码改动）：** `StrategicAnalysisRequest.arguments` → `ToolCall.arguments: dict`（语义「符合 Tool.input_schema」）→ Engine `_build_think_prompt`（`tool_execution_engine.py:521`，arguments 进入 Think prompt 文本）→ LLM 结合外部基准（`DATA_SOURCES` dict）与内部数据（prompt）生成分析。`ToolResultStatus.INSUFFICIENT_DATA` 状态可用于内部数据不足语义（SOP 失败处理章节引导）。

**内部 Schema 模板契约（AC-3 核心）：**

- 每个 Skill 的 `templates/<功能名>_template.md` 是工作坊/访谈现场填写的采集模板（Markdown 表格形式）
- **字段一一对应（双向断言）+ 嵌套 Schema 展开约定（Round 1 D1-B 勘正补定——原稿仅写「== properties 键集合」，对嵌套 Schema 必然失败）**：
  - **比对粒度 = 递归展开的叶子键集合**：`input_schema` 为嵌套结构时（如 swot-tows 的 `internal_factors.{strengths,weaknesses}` / `external_factors.{opportunities,threats}`），模板采集字段 ↔ Schema **叶子键**（末端 properties 键，如 strengths/weaknesses/opportunities/threats）一一对应；**顶层键**（internal_factors/external_factors）以模板「采集表格区」的**分区标题**承载（分区标题字面值 == 顶层键名，不进入字段比对集）
  - 平铺 Schema（无嵌套 properties）退化为顶层键即叶子键，约定自然兼容
  - 双向断言：模板字段多于叶子键集 = 失败；叶子键缺失于模板 = 失败
- **模板微格式契约（Round 1 D2-B 勘正补定——多 Agent 并行防发散，Task 1 契约库固化）**：
  - 四段标题字面值：`基本信息` / `采集表格` / `评分锚点` / `数据缺口登记`（`TEMPLATE_REQUIRED_SECTIONS` 常量）
  - `required` 标注统一语法 = 字段名后缀「（必填）」；提取器剥离后缀取纯字段名比对
  - 评分锚点引用断言 = 模板文本含字面串 `references/scoring_anchors.md`
  - 数据缺口登记区断言 = 分区标题存在 + 至少一行表头（`| 字段 | 缺口描述 | 替代来源 |`）
- 模板结构（四段式，工作坊可直接使用）：① 基本信息区（Skill 输入参数对应字段）② 采集表格区（含嵌套顶层键分区标题 + 字段 × 评分/描述列）③ 评分锚点引用（指向 `references/scoring_anchors.md`）④ 数据缺口登记区（内部数据不可得时的降级记录）

**模板文件命名（指导性，实施可在保持功能语义下微调，须与单测断言一致）：**

| Skill slug | 模板文件 | 采集主体 |
|-----------|---------|---------|
| `swot-tows` | `templates/swot_factors_collection.md` | 优势/劣势/机会/威胁四象限采集矩阵 |
| `ansoff-matrix` | `templates/ansoff_product_market_matrix.md` | 产品 × 市场四象限现有位置 |
| `value-curve-analysis` | `templates/value_curve_factors_grid.md` | 价值要素 × 行业/我方/目标三列网格 |
| `ge-mckinsey-matrix` | `templates/ge_business_unit_scoresheet.md` | 业务单元吸引力/竞争力评分表 |
| `space-matrix` | `templates/space_dimension_scoring.md` | FS/CA/IS/ES 四维度因子评分表 |
| `value-chain-analysis` | `templates/value_chain_activities_inventory.md` | 主要/支持活动清单 + 成本归属 |
| `vrio-framework` | `templates/vrio_resources_checklist.md` | 资源/能力 V-R-I-O 逐项核查表 |
| `bsc-scorecard` | `templates/bsc_kpi_scorecard.md` | 四维度 KPI 记分卡 |
| `kpi-tree` | `templates/kpi_tree_decomposition.md` | 战略目标 → 部门 → 个人分解树 |
| `change-management` | `templates/change_stakeholder_assessment.md` | 变革准备度 + 利益相关者立场评估 |

**评分锚点契约：** 每个 Skill 的 `references/scoring_anchors.md` 必须定义：刻度（1-5 / 1-10 / 0-1，按工具业界惯例选择并在文档头声明）+ 每档具体含义（锚点示例，含正反例）+ 加权/聚合规则（如有）。禁止无锚点的裸评分引导。

**工作坊引导契约：** 每个 Skill 的 `references/workshop_guide.md` 必须含：会前准备（T-3 天材料清单，含模板预填指引）/ 2-4 小时结构化流程（环节 × 时长 × 产出物）/ 角色分工（引导者/业务专家/记录员）/ 引导纪律（防锚定/防从众）/ 会后跟进（模板回收 → `input_schema` 参数构造）。Epic AC 2 明确要求「如何召开 2-4 小时结构化工作坊采集数据」。

**references 三件套命名（4-1d 适配混合数据语义）：**

| 文件 | 内容 | 对应 4-1c 角色 |
|------|------|---------------|
| `references/data_fusion.md` | 内外数据融合规范：外部基准（2 源）与内部数据的交叉验证流程、冲突处理（外部基准与内部认知矛盾时的处置）、内外结论权重、**基准粒度限制声明**（Round 1 D1-D 补定——宏观指标近似行业维度处需显式声明粒度边界，如 ansoff/space 的 GDP/WEO 为国家维度非行业维度；bsc 仅财务维度有真实外部基准，客户/流程/学习三维度以历史值/目标值为基准，禁止伪造外部对标） | triangulation.md（多源三角化 → 内外交叉验证） |
| `references/scoring_anchors.md` | 评分锚点（Epic AC 2） | scoring_anchors.md（同名同角色） |
| `references/workshop_guide.md` | 工作坊引导（Epic AC 2） | workshop_guide.md（同名同角色） |

### 生产链路（零改动声明）

4-1c 已完成双入口接线，本 Story 声明即生效。**生效边界注记（Round 1 D1-C 勘正，对齐 4-1c R1-P2-13 已知限制）**：RunToolChainUseCase 已注册于 composition_root（:2650）但无 HTTP/CLI 路由消费；StrategicAnalysisUseCase 接线完毕但无 composition_root 注册与生产调用方——「生效」当前指应用层接线语义 + 测试链路端到端，strategic 半边的生产端到端待入口 Story（FR-IF-01 锚点，Defer 节登记）。

- `StrategicAnalysisUseCase.execute()`（`src/application/use_cases/strategic_analysis.py:103-127`）：`load_sop` → `extensions["tool_metadata"]` 注入（失败容错不阻断）
- `RunToolChainUseCase.execute()`（`src/application/use_cases/run_tool_chain.py:96-117`）：声明序首节点 metadata 注入（链路共享单 ToolMetadata，节点级切换属 Story 4.2）
- Engine `_resolve_data_sources`（`tool_execution_engine.py:297-364`）：标记解析 → 白名单校验 → 并发采集 → preamble 注入 → `EvidencePackage.data_sources` 溯源
- **禁止**改动 `ToolExecutionEngine.__init__` 签名（4.4 BDD AC-7.4 断言保护）

### 领域事件（本 Story 不新增事件）

复用 4-1b 双通道事件：`DataSourceFetched` / `DataSourceFetchFailed`。Skills 成熟化不产生新事件类型。

### 契约测试文件清单

- 本 Story 无新端口 → **无新端口契约测试文件**
- 数据源声明一致性契约断言并入架构测试 `tests/unit/architecture/test_arch_skill_mixed_data.py`（声明 SSOT ↔ 10 个 SKILL.md frontmatter ↔ 适配器 `get_metadata()` 三方一致）
- 既有契约测试回归：`test_port_contract_data_source.py` / `test_port_contract_data_source_resolver.py` 全绿（零修改）；`test_frontmatter_data_sources.py` 含测试语义中间态安全化重构（Task 1.4——Round 1 曾勘正为「DECLARING_SLUGS 6→16 扩清单」、Round 2 证伪重写为中间态安全化，详见范围澄清节）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 10 个 Skills data_sources 白名单声明与解析集成

**Given** Story 4.1b/4.1c 已交付 frontmatter `data_sources` 解析链路与生产链路接线
**When** 在 10 个 SKILL.md frontmatter 填充 `data_sources` 白名单声明（统一 2 源）
**Then**
- 每个 Skill 的声明与「数据契约 SSOT 表」逐字一致（name 有序集合对主表；url/api_type/ttl_seconds 对适配器对齐表 = `ADAPTER_SSOT`）
- `load_sop(slug).frontmatter.data_sources` 解析为 `tuple[DataSourceRef, ...]`，名称有序集合等于声明集合
- 声明的 `url` 与对应适配器 `get_metadata().url` 一致（防漂移契约断言）
- 既有 23 个 Skills 解析回归全绿（`test_frontmatter_data_sources.py` 含中间态安全化重构后 + `test_skills_loader.py` 零回归）
- 回归网调整落地（**两处移出 + 一处重构**，Round 2 设计重写）：`NON_TARGET_SLUGS` 17 → 7（两处：`test_pestel_analysis_data_collection.py:31` + `test_arch_skill_data_collection.py:55` + 周边 docstring「17 个」字样）+ `test_frontmatter_data_sources.py` 测试语义中间态安全化重构（物理非空者必 ∈ SSOT 并集 16，替代 Round 1 的「DECLARING_SLUGS 6→16 扩清单」方案——后者经回归核查证伪：非空断言致并行期必红，详见 Subtask 1.4）；7 个 4-1e 目标 Skill 保持守护
- 既有 6 个 4-1c Skill 声明零回归（`skill_data_collection_contracts.py` 断言全绿）

**验证标准/Validation Criteria:**
- [ ] 10 个 Skills 单元测试（`test_<slug>_mixed_data.py`）断言白名单解析结果 == SSOT 表（全字段：name/api_type/ttl_seconds/url/required_fields）
- [ ] 跨循环一致性（[C] 循环）：SOP body 中所有 `$DATA_SOURCE("name", "query")` 标记提取的 name 集合 == frontmatter.data_sources name 集合（双向断言：白名单过宽/过窄均失败）
- [ ] 声明 url ↔ 适配器 url 一致性断言通过
- [ ] 23 Skills 全量解析回归通过（7 个 4-1e 目标经「物理非空者必 ∈ SSOT 并集」语义守护——误填即 ∉ 并集红，Round 3 措辞勘正）
- [ ] 4-1c 既有 6 Skill 契约断言零回归

### AC-2: SOP 成熟化（10 个 Skills 内容升级，9 章节对齐 4-1c 契约）

**Given** 10 个 SKILL.md 当前为占位模板（~55 行，body 含 `{"placeholder": ...}`）
**When** 编写 10 个 Skills 的完整 SOP 与配套资源
**Then**
- 每个 SKILL.md 含 9 章节（对齐 `REQUIRED_SOP_SECTIONS`）：适用场景 / 负向触发 / 输入字段（input_schema）/ 输出字段（output_schema）/ 数据采集计划（Think 阶段引导：内部数据字段清单 + 外部基准维度 → 数据源映射表 + 内外交叉验证要求）/ SOP 执行步骤（含 `$DATA_SOURCE` 标记使用规范 + `DATA_SOURCES` dict 读取协议 + **内部数据经 arguments 进入 Think prompt 的使用引导**）/ 失败处理（411 降级 / 412 限流 / 413 解析失败 / 207 白名单违规 / **内部数据不足 INSUFFICIENT_DATA 引导**）/ input_examples（≥1 个真实示例，含内部数据字段 + 外部基准 query，非 placeholder；**query 呈现形态（Round 2 澄清）**：对齐 4-1c 范本——章节 8 JSON 块仅含 input_schema 形状的 arguments，外部基准 query 以独立 `$DATA_SOURCE("name", "query")` 标记示例行呈现，**不入 arguments JSON**（schema 无 query 字段，混入即造出 schema 外字段））/ References 指引
- 每个 Skill 配套 `references/` 三件套（data_fusion.md / scoring_anchors.md / workshop_guide.md）与 `templates/` 内部数据采集模板（1 个）
- 每个 SKILL.md ≤500 行（单测 + 架构测试断言），超限内容拆分至 references/
- frontmatter 填充 `input_schema` / `output_schema`（JSON Schema dict，含 required 字段，字段级定义固化于 `skill_io_schemas.yaml`）
- 声明 Key 敏感源（newsapi/tavily）的 7 个 Skill 在 SOP 失败处理章节文档化 Key 缺失降级话术（「未注册」/「数据缺口」）
- **input_schema 与 domain catalog 兼容**：以 `strategic_tool_catalog.py` 既有 Tool.input_schema 为基础按混合数据场景增强（如 swot-tows 的 `internal_factors`/`external_factors` 必填字段保留），禁止删除 domain catalog 已有的 required 字段

**验证标准/Validation Criteria:**
- [ ] 10 个 Skills 单元测试断言 SOP 必备章节存在 + input_examples 非 placeholder + 行数 ≤500
- [ ] frontmatter input_schema/output_schema 与 `skill_io_schemas.yaml` 逐字相等（required 集合 / properties 键 / type / description）
- [ ] references 三件套 + templates 存在性与非空断言
- [ ] 评分锚点契约：scoring_anchors.md 含刻度声明 + 分档含义 + 锚点示例
- [ ] 工作坊契约：workshop_guide.md 含 2-4 小时流程 + 会前准备 + 角色分工

### AC-3: 内部 Schema 模板与 input_schema 字段一一对应（本 Story 核心增值）

**Given** Epic AC 2 要求「10 个 Skills 各自配套模板（input_schema → 模板字段一一对应）」
**When** 编写 10 个内部数据采集模板并运行 `test_schema_template_alignment.py`
**Then**
- 模板采集字段集合 == frontmatter `input_schema` **递归展开的叶子键集合**（嵌套 Schema 展开约定见「内部数据契约」节；顶层键以模板分区标题承载；**双向断言**：模板多余字段=失败，叶子键缺失于模板=失败）
- `required` 字段在模板中以后缀「（必填）」标注（统一语法）
- 模板四段式结构完整（基本信息区 / 采集表格区 / 评分锚点引用 / 数据缺口登记区，微格式契约见「内部数据契约」节）

**验证标准/Validation Criteria:**
- [ ] `tests/unit/application/skills/test_schema_template_alignment.py`（10 Skill 参数化）双向断言通过
- [ ] 模板字段提取器（Markdown 表格字段列 + 「（必填）」后缀剥离 + 嵌套叶子键递归展开）与 frontmatter Schema 叶子键集合相等断言
- [ ] 模板结构与锚点引用断言通过（四段标题字面值 + `references/scoring_anchors.md` 字面串 + 缺口区表头）
- [ ] **变异演示（Round 1 D2-B 补定，4-1c 判别力先例承接）**：临时删除任一模板字段 → [D] 断言变红后还原；临时改模板 required 标注语法 → 提取器断言变红后还原

### AC-4: 集成测试（真实服务 + 双源基准 + 内外数据融合 + 新鲜度）

**Given** 10 个 Skills 声明已就绪 + 生产链路已接线（4-1c）
**When** 运行 `tests/integration/application/test_skill_mixed_data.py`
**Then**
- 10 个 Skills 各自经「真实 Engine + 真实 Resolver + 真实 Redis（测试端口）+ Stub 适配器（call_count 计数）+ AsyncMock LLM/Sandbox」链路验证：LLM 生成含 `$DATA_SOURCE` 标记代码 → 双源并发采集 → preamble 注入 → `EvidencePackage.data_sources` 溯源元数据完备（source_name/freshness_score/confidence）
- **每个 Skill 的 2 个声明源均被采集**（每源 `call_count == 1`，去重语义），注入 `DATA_SOURCES` dict 键集合 == 声明集合
- **内外数据融合语义验证**：Engine 构造的 Think prompt 携带 arguments（内部数据），LLM Stub 按 Skill 分派 Code 阶段标记代码（外部基准）——断言 Think prompt 含 arguments repr 子串且 DATA_SOURCES 注入成功（双通道并存；断言机制见 Subtask 12.1/14.8 三要素）
- **新鲜度评分**：`EvidencePackage.data_sources[].freshness_score ∈ [0,1]`，缓存命中二次执行时外部调用次数不增
- Key 缺失场景（**单敏感源 Skill 限定**，Round 2 R2-D1B 勘正——原稿「声明含 newsapi/tavily 的 Skill，adapters Mapping 物理缺源」对双敏感 Skill（swot/value-curve/change-management 两源全敏感）不可满足：fetch_many 全失败直传首个异常（`data_source_resolver.py:233-235`，Round 3 行号勘正），不会得到「SUCCESS + 部分收敛」）：**用 kpi-tree（缺 newsapi 留 china-nbs）或 ge-mckinsey/value-chain/vrio 任一单敏感 Skill，物理缺其中 1 个敏感源** → 部分失败收敛（SUCCESS + `DataSourceFetchFailed` 事件且 `error_code == "EXCEPTION_411"`），分析基于内部数据 + 其余源 + 标注数据缺口继续；**双敏感全缺语义**（2 源全失败 → 411 直传不收敛）作为对照用例显式断言（锁死 fetch_many 全失败契约）
- 跨租户缓存隔离（双租户交叉断言：tenant_b 二次执行 `call_count == first + 1`）

**验证标准/Validation Criteria:**
- [ ] 集成测试全绿（真实 Redis 不可用时 `pytest.skip()` 动态跳过）
- [ ] 双源覆盖断言：10 个 Skill 注入源数 == 2
- [ ] 411 语义断言（`error_code == "EXCEPTION_411"`，4-1c R1-P1-1 判别力先例）
- [ ] `pytest -n 8` 并行通过（`xdist_group("data-source-cache")`），连续 5 次无随机失败

### AC-5: SDD 架构验证测试

**Given** 10 个 Skills 声明必须满足六边形架构约束与三方一致性
**When** 运行 `tests/unit/architecture/test_arch_skill_mixed_data.py`
**Then**
- 声明 SSOT ↔ 10 个 SKILL.md frontmatter ↔ 适配器 `get_metadata()` 三方一致（name/url/api_type/ttl）
- `ToolExecutionEngine.__init__` 签名不变（inspect.signature 锁定，对齐 4-1c 模式）
- 本 Story 零 Python 生产代码改动声明：wiring 文件（`strategic_analysis.py` / `run_tool_chain.py` / `tool_execution_engine.py`）源码文本含既有特征串（`tool_metadata` / `load_sop`）——**回归断言既有接线未被破坏**（三文件一致，Round 1 D2-A 勘正 AC-5 与 13.3 的文件集差异；注：不复制 4-1c 已删除的 `test_domain_layer_untouched_by_story` git status 恒真模式，R1-P1-2 教训）
- 10 个 SKILL.md ≤500 行 + frontmatter 必需字段完备 + data_sources 非空
- 7 个 4-1e 目标 Skill 未被误改（data_sources 空 tuple）
- SSOT 单一来源：`MIXED_SKILL_DATA_SOURCES` 从 contracts 模块 import（架构/集成/验收三处禁止复制，R2-F3 先例）

### AC-6: BDD 验收测试（Gherkin 中文）

**Given** Story 4.1b/4.1c 数据采集基础设施与生产链路已就绪
**When** Agent 调用 10 个混合数据型 Skills
**Then** Skills 通过 Schema 模板收集内部数据（工作坊方法论）+ 双源外部基准自动采集，LLM 融合内外数据生成结构化分析输出，输出含 source/freshness/confidence 元数据
**And** Edge Cases 覆盖：白名单外数据源（207）、数据源不可用部分失败收敛、Key 缺失降级（411 语义 + 内部数据继续分析 + 数据缺口标注）、缓存命中、未成熟化 Skill（4-1e 目标）空白名单 207 安全失败、内外数据融合双通道并存（arguments 进入 Think prompt + DATA_SOURCES 注入并存断言）

> **覆盖范围说明**（对齐 4-1c R2-F5 教训）：BDD 承载 AC-1（声明行为面）/ AC-4（链路行为面）/ AC-6 行为验证；AC-2（SOP 内容）/ AC-3（模板对应）/ AC-5（架构约束）由单元测试 + 架构测试承载（`test_<slug>_mixed_data.py` / `test_schema_template_alignment.py` / `test_arch_skill_mixed_data.py`）。

**验证标准/Validation Criteria:**
- [ ] `tests/acceptance/test_acceptance_skill_mixed_data.feature`（`# language: zh-CN`，按 AC 分节）
- [ ] `tests/acceptance/test_acceptance_skill_mixed_data.py`（scenarios() + context dict + 共享 event_loop + 真实服务 + Fake 仅限适配器/LLM/Sandbox）
- [ ] 全部场景通过

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有内容实施 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 本 Story 不新增领域事件（复用 `DataSourceFetched`/`DataSourceFetchFailed`），Task 0 显式登记该决策

#### 数据模型 (Data Models)
- [ ] 本 Story 不新增值对象/实体/端口（复用 `DataSourceRef`/`ToolMetadata.data_sources`/`EvidencePackage.data_sources`）
- [ ] **10 个 Skills 的 `input_schema`/`output_schema` JSON Schema 字段级定义固化**：扩充 `tests/acceptance/contracts/skill_io_schemas.yaml`（追加 10 个条目，字段级：required/properties/类型/description；以 `strategic_tool_catalog.py` 既有 Tool.input_schema 为基础增强）
- [ ] 字段级定义作为各 Skill TDD 红阶段断言输入（Task 2-11 [A] 循环断言 input_schema 与契约逐字相等）

#### 统一端口定义注册与管理 (Port Contract)
- [ ] 本 Story 不新增端口（显式决策 D4）；复用 `DataSourcePort`/`DataSourceResolverPort`/`SkillLoaderPort`
- [ ] 禁止在服务文件中本地定义 Protocol / Port 抽象
- [ ] 既有端口契约测试回归全绿（`test_port_contract_data_source*.py`）

#### 端口契约清单执行约束（强制）
- [ ] 本 Story「端口与数据契约」节是唯一事实源（含 10 Skills 数据源声明 SSOT 表 + 模板契约）
- [ ] 禁止新增未登记端口；禁止语义重复端口
- [ ] 10 Skills 声明与 SSOT 表逐字一致，实施期增删源必须先修订本 Story 文档

#### 领域异常契约 (Domain Exception Contract)
- [ ] 见「🎯 领域异常契约」节：不新增异常（显式决策 D4），复用 201/207/101/302/411/412/413 + FrontmatterParseError + 387/388
- [ ] 4-1c 留项 R1-P2-10/11 收敛状态确认（已由 4-1b `0d550dda` 收敛，回归验证通过）
- [ ] BDD 异常路径场景纳入 Edge Cases（207/411）

#### API 契约 (API Contract)
- [ ] 本 Story 不新增 REST 端点，无 `openapi.yaml` 变更（纯 Skills 内容，零代码改动）

#### 六边形架构约束（必须遵守）

**四层架构定义**
| 层次 | 目录 | 本 Story 交付物 |
|------|------|----------------|
| domain | `src/domain/` | 无改动（复用 4-1b/4-1c 全部领域资产） |
| application | `src/application/` | 10 个 SKILL.md + references/templates 资源（纯 YAML/Markdown，零 Python 改动） |
| infrastructure | `src/infrastructure/` | 无改动 |
| interfaces | `src/interfaces/` | 无改动 |

**领域层零依赖原则**：四层 Python 代码零改动；新增内容仅 YAML/Markdown 资源，不引入新第三方依赖

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_skill_mixed_data.feature`（`# language: zh-CN`）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_skill_mixed_data.py`
- [ ] Happy Path + Edge Cases 全覆盖（白名单外 207 / 部分失败收敛 / Key 缺失降级 / 缓存命中 / 空白名单安全失败 / **内外数据融合双通道并存** 共 6 个 Edge Cases——Round 1 D2-A 勘正：原稿「模板对应破坏」与 AC-6/Subtask 14.8「模板对应不入 BDD」冲突，模板↔Schema 对应由 `test_schema_template_alignment.py` 单元层承载）

**BDD 步骤实现约束：**
- 步骤函数使用场景级共享 `event_loop` + `run_until_complete()`（禁止 `@pytest.mark.asyncio`）
- 同一中文文本可能需要同时支持 given/when 装饰器
- Edge Cases 必须包含异常路径断言 `error.code` + `error.message`

**Task 0 完成标志：**
- [ ] 规范项全部定义完毕（10 Skills Schema 契约 + 声明 SSOT 表固化 + 模板契约 + 决策登记）
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [ ] "不新增端口/异常/事件 + 零代码改动"四项显式决策已登记（Round 1 D2-A 勘正：原稿「三项」为 4-1c 模板残留，Subtask 0.1/DoD 均按四项）

---

### TDD 循环约束（适用于每个 Task）

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写内容后写测试（Skills 内容 Task 同样适用：先写"断言 SKILL.md 内容"的失败测试，再编写 SKILL.md 内容使其转绿）
- ❌ 将测试编写集中到最后一个 Task
- ❌ 跳过红阶段验证

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | 契约断言库 | SSOT 常量 + 断言函数（非测试模块） | `tests/unit/application/skills/skill_mixed_data_contracts.py` | Task 1 |
| **TDD 单元测试** | Skills 内容 ×10 | frontmatter 白名单解析/Schema 契约/SOP 章节/行数/references 三件套/templates 存在性 | `tests/unit/application/skills/test_<slug>_mixed_data.py` ×10 | Task 2-11 |
| **TDD 单元测试** | 模板对应专项 | 模板字段 ↔ input_schema **叶子键**双向断言（10 Skill 参数化） | `tests/unit/application/skills/test_schema_template_alignment.py` | Task 2-11 [D] / 12 |
| **TDD 验收测试** | Gherkin 场景 + BDD 步骤 | 业务价值验收 | `tests/acceptance/test_acceptance_skill_mixed_data.feature` + `.py` | Task 0 / 14 |
| **集成测试** | 10 Skills 全链路 | 双源覆盖/内外融合/新鲜度/缓存命中/Key 缺失降级 | `tests/integration/application/test_skill_mixed_data.py` | Task 12 |
| **SDD 架构验证** | 六边形约束 + 声明一致性 | 三方一致/签名锁定/行数/回归网/SSOT 单一来源 | `tests/unit/architecture/test_arch_skill_mixed_data.py` | Task 13 |
| **回归（修改）** | 既有回归网 | `NON_TARGET_SLUGS` 17→7（两处）+ `test_frontmatter_data_sources.py` 中间态安全化重构 | `test_pestel_analysis_data_collection.py` / `test_arch_skill_data_collection.py` / `test_frontmatter_data_sources.py` | Task 1.4 |
| **回归** | 既有资产 | 23 Skills 解析 / 4-1c 6 Skill 契约 / 4.1a/4.4 既有测试 | 既有测试套件 | 每个 Task |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`make test-cov`）- **P0 阻断门禁**
- [ ] **应用层 ≥85%**（`make test-cov-application`）——本 Story 应用层零 Python 改动，既有覆盖率不降（新增纯资源文件不计入分母恶化）
- [ ] **关键路径 100%**：本 Story 无代码分支新增，以契约断言覆盖代偿（声明/模板/Schema 三向对应全断言）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）
- [ ] 测试文件类型注解完备（fixture 返回类型 + 测试参数注解，4-1c R1-P0-1 教训：禁止 `# type: ignore`）

#### 测试隔离约束

> 见「🎯 测试隔离约束」节全文。核心：TestTenant UUID 前缀、真实 Redis 测试端口 + delete_pattern 租户级清理、适配器一律 Stub/Fake、BDD 禁 `@pytest.mark.asyncio` + Redis 场景级独立客户端、`xdist_group("data-source-cache")` 复用。

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 10 Skills data_sources 声明与解析集成 | Task 0 / 1 / 2-11 / 13 | 0.2 / **1.4（回归网三处调整，Round 1 D2-A 勘正补）** / 各 Skill Task .1-.2 / 13.2 | `test_<slug>_mixed_data.py` ×10 / `test_arch_skill_mixed_data.py` / 回归网三文件 |
| AC-2 | SOP 成熟化 + references 三件套 + 模板 | Task 2-11 | 各 Skill Task .1-.8（.1-.2 含 Schema 逐字断言，Round 1 D2-A 勘正补） | `test_<slug>_mixed_data.py` ×10 |
| AC-3 | 模板字段 ↔ input_schema 叶子键一一对应 | Task 0 / 1 / 2-11 / 12 | 0.2 / 1.2 / 各 Skill Task [D] 循环 / 12.6 | `test_schema_template_alignment.py` |
| AC-4 | 集成测试（双源/融合/新鲜度） | Task 12 | 12.1-12.7 | `test_skill_mixed_data.py` |
| AC-5 | 架构验证测试 | Task 13 | 13.1-13.5 | `test_arch_skill_mixed_data.py` |
| AC-6 | BDD 验收测试 | Task 0 / 14 | 0.4-0.6 / 14.1-14.9 | `test_acceptance_skill_mixed_data.feature` / `.py` |

---

## ⚠️ 风险与缓解策略（Risk Register）

| ID | 风险描述 | 等级 | 触发条件 | 缓解策略 | 关联 Task |
|----|---------|------|---------|---------|----------|
| **R1** | newsapi/tavily Key 缺失导致声明源未注册（10 个 Skill 中 7 个声明含 Key 敏感源） | 中 | dev/CI 无 `NEWSAPI_API_KEY`/`TAVILY_API_KEY` | ① 运行时 Resolver「未注册 411」部分失败收敛（4-1b 既定语义）；② 7 个 Skill SOP 失败处理章节显式登记降级话术（内部数据为主体，外部基准缺失时标注数据缺口继续分析——混合数据型的天然降级优势）；③ 集成测试用 Stub 适配器注入 adapters Mapping（不依赖条件注册）；④ BDD Edge Case 显式覆盖 | Task 2-11 / 12 / 14 |
| **R2** | SKILL.md SOP 成熟化超 500 行硬约束（10 个 Skill 含模板字段说明+内外融合方法论，内容量大） | 中 | SOP + 工作坊方法论内容膨胀 | Hub-and-Spoke 拆分：SKILL.md 仅路由+摘要（9 章节骨架），详情入 references/ 三件套；每 Skill Task 含行数断言 + Task 13 架构测试兜底 | Task 2-11 / 13 |
| **R3** | 回归网调整引入中间态破口 | 低 | Subtask 1.4 调整回归网时 10 个 Skill 尚未声明（Round 2 勘正：调整位已从 Task 2 前置至 1.4） | NON_TARGET 移出后空 tuple 断言不再检查 4-1d 目标（前置安全）；`test_frontmatter_data_sources.py` 重构为中间态安全语义（物理非空者必 ∈ SSOT 并集，不要求已填）；每个 Skill 独立测试文件断言自身声明逐个转绿；最终态 16 全非空由 Task 13.4 闭环 | Task 1.4 / 13 |
| **R4** | frontmatter 声明与适配器 `get_metadata()` 漂移（url/api_type/ttl 不一致） | 低 | 声明值手写错误 | Task 0 固化 SSOT 表（ADAPTER_SSOT import 4-1c 契约库，禁止复制）；Task 13 架构测试三方一致性断言 | Task 0 / 13 |
| **R5** | input_schema 与 domain catalog 既有 required 字段漂移（frontmatter 增强时误删 domain 字段） | 中 | Task 0 Schema 契约设计时遗漏 catalog 既有字段 | Task 0.2 以 `strategic_tool_catalog.py` 既有 schema 为基础逐 Skill 核对（swot-tows :308 / value-chain :195 / vrio :231 / ansoff :270 / ge-mckinsey :354 / space :393 / value-curve :473 等）；AC-2 验证标准含「禁止删除 domain catalog 已有 required 字段」断言 | Task 0 / 2-11 |
| **R6** | Epic 字面「Excel 模板」与 Markdown 模板落地偏差被质疑 | 低 | 评审质疑模板格式 | 决策 D1 显式登记（对齐 4-1c templates/*.md 先例；L3 渐进加载/文本可断言/git 友好；Excel 二进制不可断言不可 diff），Story 文档留痕 | Task 0 |
| **R7** | Epic 字面「test_*_4_1d.py」文件名与功能性命名约束冲突 | 低 | 实施期照抄 Epic 文件名 | 「命名规范声明」节显式覆盖（用户约束优先，4-1c File List 留痕先例） | 全部 Task |
| **R8** | china-nbs crawler 服务不可用（value-chain/bsc/kpi-tree 3 个 Skill 声明） | 中 | dev/CI 未运行 crawler daemon | 集成测试用 Stub 适配器（不依赖真实 crawler）；SOP 失败处理章节文档化 crawler 不可用降级；真实 crawler 链路属 4-1b 推迟项 P0-7 范畴 | Task 12 |
| **R9** | 嵌套 Schema ↔ 模板字段映射失效 + 多 Agent 并行模板微格式发散（Round 1 D1-B/D2-B 补登——原稿风险表未覆盖） | 中 | Task 2-11 并行 Agent 对叶子键展开/必填标注语法/锚点引用形态各自理解 | 嵌套展开约定 + 微格式契约在「内部数据契约」节固化（Task 0.2/1.2 钉死）；契约库提取器先行（Task 1 前置于全部 Skill Task）；[D] 循环变异演示实证判别力 | Task 0/1/2-11 |

---

## 📚 配套架构文档同步

> **文档同步硬约束（Task 14 收尾）：** Story 4.1d 完成时必须同步更新以下架构文档。

| Task | 文档同步动作 | 文档 | 锚定位置 |
|------|------------|------|---------|
| Task 14 收尾 | `architecture.md` §17.3 状态块：`📋 Story 4.1d backlog` → `✅ Story 4.1d 已完成` | architecture.md | line 2675 附近 |
| Task 14 收尾 | `architecture.md` §17.3.3 末尾追加 4.1d 集成说明（10 Skills 双源声明 + 模板契约 + 决策 D1-D8，Round 1 D2-A 勘正：原稿「D1-D7」漏 D8） | architecture.md | §17.3.3 末尾 |
| Task 14 收尾 | `architecture.md` §17.3.3 关键架构决策表追加本 Story 决策（引用本 Story 决策表） | architecture.md | 决策表末尾 |
| Task 14 收尾 | `sisys-uni-exception-design.md` **§3.3.2「完整编码分配表」**（该文档存在两个 §3.3.2 重号——Round 1 D1-C 勘正消歧：目标为 :649 编码分配表节，4-1c 复用声明段落之后追加）引用本 Story「领域异常契约」节表格，段落引用而非重新列举——4-1c R1-P1-3 双维护漂移教训 | sisys-uni-exception-design.md | §3.3.2（完整编码分配表）末尾 |
| Task 14 收尾 | `architecture.md` 修订历史表追加新版本行 + 文档统计版本号/日期更新 | architecture.md | 文末修订历史 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> **并行实施建议**：Task 2-11 相互独立（各 Skill 独立目录与测试文件），可参照 4-1c 实施经验由多个 Agent 并行（4-1c 曾以 3 并行 Agent + 主会话实施 6 Skill）；Task 1 是全部 Skill Task 的前置。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部（AC-1 ~ AC-6 的规范输入）

> **目的：** 在进入内容实施前，固化 10 Skills 数据源声明 SSOT、input/output Schema 契约、模板契约、Gherkin 验收场景与"三不新增 + 零代码改动"决策登记。

- [ ] Subtask 0.1: 登记**八项决策全量确认**（四项显式决策：不新增端口 / 不新增异常 / 不新增事件 / 零 Python 生产代码改动 + D1 模板载体 Markdown + D2 统一 2 源 + D3 data_fusion 语义 + D5 内部通道不新增 + D6 契约库组织 + D7 IO SSOT 扩充 + D8 回归网调整机制——Round 1 D2-A 勘正：原稿仅列 D1/D2/D6，决策登记与 8 项决策表不闭合）
- [ ] Subtask 0.2: 定义 10 个 Skills 的 `input_schema`/`output_schema` JSON Schema 契约——扩充 `tests/acceptance/contracts/skill_io_schemas.yaml`（追加 10 条目；**逐 Skill 核对 `strategic_tool_catalog.py` 既有 required 字段**，R5 风险收敛；**同步更新该 yaml 文件头注释与 `story:` 字段为 `[4-1c, 4-1d]` 列表**——Round 1 D1-A 勘正 + Round 2 钉死列表形态），作为 Task 2-11 红阶段断言输入；**嵌套 Schema 展开约定在此固化**（叶子键递归展开规则，见「内部数据契约」节）；**output_schema 基准（Round 2 补定）**：以 catalog 既有 output_schema 为基础（无 required 键，需补全）+ `required` 必含 `data_sources`（type array/items object，对齐 4-1c 六条目惯例——工具输出自带溯源元数据的文档级约定，防 10 Agent 风格分叉）；**required_fields 逐源 SSOT（Round 2 补定）**：全部声明源统一 `[indicator, value]`（对齐 4-1c 实际惯例，语义为「该源 payload 的通用最小字段」——4-1c 六 Skill 全源实测如此），SSOT 表下方对齐表补此约定列说明，防实施期各自发明
- [ ] Subtask 0.3: 确认 6 个涉及源的 url/api_type/ttl 与 `ADAPTER_SSOT`（import `tests/unit/application/skills/skill_data_collection_contracts.py`）实际值一致（禁止复制粘贴常量值）
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_skill_mixed_data.feature`（Happy Path + 6 个 Edge Cases，`# language: zh-CN`；第 6 个 Edge = 内外数据融合双通道并存）
- [ ] Subtask 0.5: 编写 BDD 步骤实现骨架 `tests/acceptance/test_acceptance_skill_mixed_data.py`（scenarios() + context + 共享 event_loop + Fake 适配器骨架）
- [ ] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证，**预期红/绿拆分**——Round 1 D2-B 勘正补定：场景 1/2/4/5/6/8 红（根因 = 声明未填写 → 207）；场景 3（白名单外 207）与场景 7（未成熟化 207）为安全失败不变量、骨架期即绿，对齐 4-1c 实测「10 failed + 2 passed」形态）
- [ ] Subtask 0.7: 执行 4-1c 留项回归验证（`pytest tests/unit/application/skills/test_frontmatter_data_sources.py tests/unit/domain/value_objects/ -v` 全绿，确认 R1-P2-10/11 已收敛态）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕（Schema 契约 10 条目 + SSOT 表 + 模板契约 + 四项决策登记）
- [ ] 验收测试运行失败（预期行为，红阶段确认）
- [ ] 留项回归验证通过

---

### Task 1: 共享契约断言库（回归基建）

**关联 AC:** AC-1, AC-2, AC-3, AC-5

> **性质说明：** 非测试模块（无 test_ 前缀，pytest 不收集）。对齐 4-1c `skill_data_collection_contracts.py` 模式（R2-F3 单一来源原则）；本 Story 新建独立库避免污染 4-1c 语义，`ADAPTER_SSOT` 从 4-1c 库 import 复用。

#### TDD 循环 [A]：契约库构建

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/skills/test_skill_mixed_data_contracts.py` **永久自检测试**（Round 1 D2-B 勘正：原稿「临时导入断言」未定去向；改为永久断言 `MIXED_SKILL_DATA_SOURCES` 10 条目与 SSOT 表逐字一致——防实施期擅改 SSOT，有长期判别价值） |
| 🟢 绿 | 实现契约库：**新库仅自定义** `MIXED_SKILL_DATA_SOURCES`（slug→声明源有序元组，SSOT 表固化）/ `TEMPLATE_REQUIRED_SECTIONS`（模板四段式）/ `assert_template_schema_alignment`（模板字段 ↔ 叶子键双向 + 微格式断言）；**跨 Story 共享常量一律 import**（Round 1 D1-B/D2-B 勘正：原稿将四常量列为新库自定义违反 R2-F3 单一来源教训）：`from skill_data_collection_contracts import ADAPTER_SSOT, KEY_SENSITIVE_SOURCES, DATA_SOURCE_MARKER_PATTERN, REQUIRED_SOP_SECTIONS, SKILL_MD_MAX_LINES`；断言函数 `assert_data_sources_contract` / `assert_io_schema_contract` / `assert_sop_maturity`（含 references 三件套 data_fusion/scoring_anchors/workshop_guide 断言）/ `assert_cross_consistency` 按混合数据语义重写（Key 话术条件门控天然适配 7 断言 3 跳过） |
| 🔄 重构 | 类型注解完备 + ruff/mypy 通过 |

- [ ] Subtask 1.1: 🔴 红 — 编写契约库永久自检测试（断言常量与 SSOT 表逐字一致）
- [ ] Subtask 1.2: 🟢 绿 — 实现契约库（新库仅含混合数据特有常量/断言 + 共享常量 import）
- [ ] Subtask 1.3: 🔄 重构 — 类型注解 + ruff + mypy
- [ ] Subtask 1.4: 🟢 绿 — **回归网一次性预调整（D8 执行位；Round 2 设计重写——Round 1 方案「DECLARING_SLUGS 6→16 前置扩充」经回归核查证伪：`test_declaring_skills_frontmatter_carries_data_sources:141-149` 对清单成员断言**非空**，前置扩清单后 10 个未填 Skill 必红、红窗口贯穿整个并行期，死锁被搬家而非消除）**：
  - **NON_TARGET_SLUGS 17→7（两处 + docstring「17 个」字样）**：移出 10 个 4-1d 目标（移出后空 tuple 断言不再检查它们，前置安全——R3 论证仍成立）；7 个 4-1e 目标保持守护
  - **`test_frontmatter_data_sources.py` 测试语义中间态安全化重构（替代原「扩清单」方案）**：`test_all_23_skills_parse_without_data_sources` 的「非 DECLARING 组空 tuple」断言改为「**物理 data_sources 非空者必 ∈ SSOT 并集（`SKILL_DATA_SOURCES` ∪ `MIXED_SKILL_DATA_SOURCES` = 16 slug，从两契约库 import 动态派生）**」——中间态既防 4-1e 目标误填（∉ 并集即红）又不要求 4-1d 目标已填；`test_declaring_skills_frontmatter_carries_data_sources` 的静态 `DECLARING_SLUGS` 同步改为「物理非空者逐个校验合法性（name/ttl）」（凡声明必合法，不绑定静态清单）；**最终态完整性（16 Skill 全非空且 == SSOT）由 Task 13 架构测试全量断言闭环**；各 Skill Task 全程零触碰该共享文件（消除 10 Agent 并发编辑冲突面）

**完成标准/Definition of Done:**
- [ ] 契约库可被 10 个 Skill 测试与架构/集成/验收测试统一 import（SSOT 单一来源）
- [ ] 断言函数与 4-1c 契约库风格一致（中文失败消息带 slug 上下文、词边界正则防伪满足）
- [ ] **回归网三处调整落地**（Task 2-11 并行的前置条件；4-1c 6 Skill + 7 个 4-1e Skill 断言不变全绿）

---

### Task 2: swot-tows Skill 成熟化（Task 2-11 实施范本）

**关联 AC:** AC-1, AC-2, AC-3

> **数据源（SSOT）：** `newsapi` + `tavily`（2 源，双 Key 敏感——降级话术必写）
> **内部数据主体：** 优势/劣势（内部资源能力）/ 机会/威胁（外部印证）四象限
> **注意：回归网调整已前置至 Subtask 1.4**（Round 1 D2-B 勘正——原稿置于本 Task 2.9 造成并行时序死锁：Task 3-11 的并行 Agent 在 2.9 合入前填声明必触 `test_non_target_skills_empty_data_sources` 等回归红且其 DoD 不可满足）；本 Task 仅实施 swot-tows 自身四循环

#### TDD 循环 [A]：frontmatter 声明 + Schema 契约

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/skills/test_swot_tows_mixed_data.py`（load_sop 解析 data_sources == SSOT 2 源有序集合 / url/api_type/ttl 与 ADAPTER_SSOT 逐字一致 / input_schema 与 skill_io_schemas.yaml 契约逐字相等 / domain catalog `internal_factors`/`external_factors` required 字段保留断言） |
| 🟢 绿 | 填充 SKILL.md frontmatter（data_sources + input_schema + output_schema） |
| 🔄 重构 | 23 Skills 解析回归全绿（回归网调整已前置至 Subtask 1.4，本 Task 零触碰共享回归文件——Round 2 勘正残留） |

#### TDD 循环 [B]：SOP 内容成熟化

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩充测试（SOP 9 章节断言 + input_examples 非 placeholder 含内部数据字段与外部 query + 行数 ≤500 + references 三件套存在 + templates 存在 + 双 Key 敏感源降级话术「未注册」「数据缺口」） |
| 🟢 绿 | 编写 SKILL.md body + references/（data_fusion.md 内外交叉验证 + scoring_anchors.md SWOT 强度 1-5 锚点 + workshop_guide.md 战略工作坊 2-4 小时流程）+ templates/swot_factors_collection.md（四象限采集矩阵） |
| 🔄 重构 | 行数校验 + 内容评审 |

#### TDD 循环 [C]：跨循环一致性

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写断言：SOP body 中 `$DATA_SOURCE` 标记 name 集合 == frontmatter 声明集合（双向） |
| 🟢 绿 | 调整 SOP body 标记与 frontmatter 对齐 |
| 🔄 重构 | 契约库 `assert_cross_consistency` 复用化 |

#### TDD 循环 [D]：模板字段 ↔ Schema 对应（本 Story 特有）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写断言：`templates/swot_factors_collection.md` 采集字段集合 == input_schema **递归叶子键集合**（swot 顶层键 internal_factors/external_factors 以模板分区标题承载，比对集为 strengths/weaknesses/opportunities/threats 四叶子键——Round 2 勘正残留）+ required「（必填）」后缀标注 + 四段式结构 |
| 🟢 绿 | 调整模板字段与 Schema 对齐 |
| 🔄 重构 | 断言提取器逻辑（Markdown 表格字段解析 + 必填后缀剥离 + 叶子键展开）在本 Skill 测试内定型；`test_schema_template_alignment.py` 汇总参数化文件于 Task 12.6 创建（Round 1 D2-A 勘正：原稿此处即要求纳入该文件与 File List 的 Task 12.6 创建时点矛盾） |

- [ ] Subtask 2.1: 🔴 红 — 编写 frontmatter 声明失败测试（含 domain catalog 兼容断言）
- [ ] Subtask 2.2: 🟢 绿 — 填充 frontmatter（data_sources/Schema）
- [ ] Subtask 2.3: 🔴 红 — 编写 SOP 内容失败测试
- [ ] Subtask 2.4: 🟢 绿 — 编写 SOP + references 三件套 + templates 模板
- [ ] Subtask 2.5: 🔴 红 — 编写跨循环一致性 [C] 失败测试
- [ ] Subtask 2.6: 🟢 绿 — SOP 标记集合与 frontmatter 对齐
- [ ] Subtask 2.7: 🔴 红 — 编写模板对应 [D] 失败测试
- [ ] Subtask 2.8: 🟢 绿 — 模板字段与 Schema 双向对齐
- [ ] Subtask 2.9: 🔄 重构 — 行数 ≤500 + 全部循环回归全绿（回归网调整已在 Subtask 1.4 前置完成）

**完成标准/Definition of Done:**
- [ ] swot-tows 声明与 SOP 成熟化完成，单测全绿
- [ ] [C] 跨循环一致性 + [D] 模板对应双向断言通过（**含嵌套叶子键展开**——swot 的 strengths/weaknesses/opportunities/threats 四字段对 internal/external_factors 顶层键分区）
- [ ] 23 Skills 解析回归零失败

---

### Task 3: ansoff-matrix Skill 成熟化

**关联 AC:** AC-1, AC-2, AC-3

> **范本引用（Round 2 钉死）**：[A]-[D] 循环定义与红阶段断言清单**同 Task 2 范本**（[A] 四件套：SSOT 逐字 / ADAPTER_SSOT 对齐 / yaml 契约逐字 / catalog required 保留；[B] 9 章节+三件套+模板；[C] 标记双向；[D] 叶子键双向+微格式）。Task 3-11 的 [C]/[D] 采用「双红并立 → 合并转绿」节奏（Subtask .5/.6 红 + .7 绿），与 Task 2 的严格交替等价——TDD「每 Task 独立完整红→绿」约束下允许的合并形态（红阶段在绿之前完成，循环完整性不变）。

> **数据源（SSOT）：** `world-bank` + `imf`（2 源，免 Key）
> **内部数据主体：** 产品 × 市场四象限现有位置（渗透/开发/延伸/多样化）
> **SOP 核心：** 增长率基准（WB `NY.GDP.MKTP.CD` / IMF `NGDP_RPCH`）+ 风险等级评估 + 战略工作坊

- [ ] Subtask 3.1: 🔴 红 — 编写 `test_ansoff_matrix_mixed_data.py` 声明失败测试（[A] 循环：2 源解析 + Schema 契约 + catalog 兼容）
- [ ] Subtask 3.2: 🟢 绿 — 填充 frontmatter（data_sources/Schema）
- [ ] Subtask 3.3: 🔴 红 — 编写 SOP 内容失败测试（[B] 循环：9 章节 + 三件套 + templates/ansoff_product_market_matrix.md）
- [ ] Subtask 3.4: 🟢 绿 — 编写 SOP + references（data_fusion 增长率内外对照 / scoring_anchors 风险等级锚点 / workshop_guide）+ templates
- [ ] Subtask 3.5: 🔴 红 — 编写跨循环一致性 [C] 失败测试（2 源 ↔ 2 标记对齐）
- [ ] Subtask 3.6: 🔴 红 — 编写模板对应 [D] 失败测试
- [ ] Subtask 3.7: 🟢 绿 — SOP 标记与模板字段对齐（[C]+[D] 转绿）
- [ ] Subtask 3.8: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] ansoff-matrix 声明与 SOP 成熟化完成，单测全绿
- [ ] [C] + [D] 双向断言通过 + 23 Skills 解析回归零失败

---

### Task 4: value-curve-analysis Skill 成熟化

**关联 AC:** AC-1, AC-2, AC-3

> **数据源（SSOT）：** `tavily` + `newsapi`（2 源，双 Key 敏感——降级话术必写）
> **内部数据主体：** 内部产品价值要素当前水平 + 目标值（客户调研输入）
> **SOP 核心：** 行业战略轮廓绘制（竞品要素情报）+ 消除-减少-增加-创造四行动 + 客户调研引导

- [ ] Subtask 4.1: 🔴 红 — 编写 `test_value_curve_analysis_mixed_data.py` 声明失败测试（[A]）
- [ ] Subtask 4.2: 🟢 绿 — 填充 frontmatter
- [ ] Subtask 4.3: 🔴 红 — 编写 SOP 内容失败测试（[B]：含 templates/value_curve_factors_grid.md 三列网格）
- [ ] Subtask 4.4: 🟢 绿 — 编写 SOP + references + templates
- [ ] Subtask 4.5: 🔴 红 — 编写 [C] 跨循环一致性失败测试
- [ ] Subtask 4.6: 🔴 红 — 编写 [D] 模板对应失败测试
- [ ] Subtask 4.7: 🟢 绿 — SOP 标记与模板字段对齐
- [ ] Subtask 4.8: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] value-curve-analysis 成熟化完成，单测全绿（[A]/[B]/[C]/[D] 四循环）
- [ ] 23 Skills 解析回归零失败

---

### Task 5: ge-mckinsey-matrix Skill 成熟化

**关联 AC:** AC-1, AC-2, AC-3

> **数据源（SSOT）：** `world-bank` + `tavily`（2 源，Epic 明确 World Bank 行业吸引力；tavily Key 敏感）
> **内部数据主体：** 业务单元数据（市场份额/销售额/利润率）
> **SOP 核心：** 行业吸引力（外部）× 业务实力（内部）九宫格 + 高管访谈引导

- [ ] Subtask 5.1: 🔴 红 — 编写 `test_ge_mckinsey_matrix_mixed_data.py` 声明失败测试（[A]）
- [ ] Subtask 5.2: 🟢 绿 — 填充 frontmatter
- [ ] Subtask 5.3: 🔴 红 — 编写 SOP 内容失败测试（[B]：含 templates/ge_business_unit_scoresheet.md）
- [ ] Subtask 5.4: 🟢 绿 — 编写 SOP + references（scoring_anchors 含 1-10 吸引力锚点）+ templates
- [ ] Subtask 5.5: 🔴 红 — 编写 [C] 失败测试
- [ ] Subtask 5.6: 🔴 红 — 编写 [D] 失败测试
- [ ] Subtask 5.7: 🟢 绿 — 对齐转绿
- [ ] Subtask 5.8: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] ge-mckinsey-matrix 成熟化完成，单测全绿（四循环）
- [ ] 23 Skills 解析回归零失败

---

### Task 6: space-matrix Skill 成熟化

**关联 AC:** AC-1, AC-2, AC-3

> **数据源（SSOT）：** `world-bank` + `imf`（2 源，免 Key）
> **内部数据主体：** FS 财务实力 / CA 竞争优势内部评分（问卷打分 + 专家访谈）
> **SOP 核心：** 四维度因子评分（外部 ES/IS 由基准数据支撑）→ 坐标定向（进取/保守/防御/竞争）

- [ ] Subtask 6.1: 🔴 红 — 编写 `test_space_matrix_mixed_data.py` 声明失败测试（[A]）
- [ ] Subtask 6.2: 🟢 绿 — 填充 frontmatter
- [ ] Subtask 6.3: 🔴 红 — 编写 SOP 内容失败测试（[B]：含 templates/space_dimension_scoring.md 四维度评分表）
- [ ] Subtask 6.4: 🟢 绿 — 编写 SOP + references（scoring_anchors 按 SPACE 惯例刻度）+ templates
- [ ] Subtask 6.5: 🔴 红 — 编写 [C] 失败测试
- [ ] Subtask 6.6: 🔴 红 — 编写 [D] 失败测试
- [ ] Subtask 6.7: 🟢 绿 — 对齐转绿
- [ ] Subtask 6.8: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] space-matrix 成熟化完成，单测全绿（四循环）
- [ ] 23 Skills 解析回归零失败

---

### Task 7: value-chain-analysis Skill 成熟化

**关联 AC:** AC-1, AC-2, AC-3

> **数据源（SSOT）：** `tavily` + `china-nbs`（2 源，tavily Key 敏感；china-nbs crawler 降级话术必写）
> **内部数据主体：** 内部主要/支持活动清单 + 成本数据（ERP 导出 + 流程访谈）
> **SOP 核心：** 价值链分解 + 成本/价值驱动分析 + 行业基准对照

- [ ] Subtask 7.1: 🔴 红 — 编写 `test_value_chain_analysis_mixed_data.py` 声明失败测试（[A]）
- [ ] Subtask 7.2: 🟢 绿 — 填充 frontmatter
- [ ] Subtask 7.3: 🔴 红 — 编写 SOP 内容失败测试（[B]：含 templates/value_chain_activities_inventory.md）
- [ ] Subtask 7.4: 🟢 绿 — 编写 SOP + references + templates
- [ ] Subtask 7.5: 🔴 红 — 编写 [C] 失败测试
- [ ] Subtask 7.6: 🔴 红 — 编写 [D] 失败测试
- [ ] Subtask 7.7: 🟢 绿 — 对齐转绿
- [ ] Subtask 7.8: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] value-chain-analysis 成熟化完成，单测全绿（四循环）
- [ ] 23 Skills 解析回归零失败

---

### Task 8: vrio-framework Skill 成熟化

**关联 AC:** AC-1, AC-2, AC-3

> **数据源（SSOT）：** `uspto` + `tavily`（2 源，tavily Key 敏感）
> **内部数据主体：** 内部资源与能力清单（内部审计 + 高管访谈）
> **SOP 核心：** V-R-I-O 逐项核查 → 持续竞争优势判定 + 行业专利密度参照（稀缺性/可模仿性外部印证）

- [ ] Subtask 8.1: 🔴 红 — 编写 `test_vrio_framework_mixed_data.py` 声明失败测试（[A]）
- [ ] Subtask 8.2: 🟢 绿 — 填充 frontmatter
- [ ] Subtask 8.3: 🔴 红 — 编写 SOP 内容失败测试（[B]：含 templates/vrio_resources_checklist.md）
- [ ] Subtask 8.4: 🟢 绿 — 编写 SOP + references（scoring_anchors V/R/I/O 判定锚点）+ templates
- [ ] Subtask 8.5: 🔴 红 — 编写 [C] 失败测试
- [ ] Subtask 8.6: 🔴 红 — 编写 [D] 失败测试
- [ ] Subtask 8.7: 🟢 绿 — 对齐转绿
- [ ] Subtask 8.8: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] vrio-framework 成熟化完成，单测全绿（四循环）
- [ ] 23 Skills 解析回归零失败

---

### Task 9: bsc-scorecard Skill 成熟化

**关联 AC:** AC-1, AC-2, AC-3

> **数据源（SSOT）：** `china-nbs` + `world-bank`（2 源，免 Key；china-nbs crawler 降级话术必写）
> **内部数据主体：** 内部 KPI 现值 + 战略规划文件要点（高管工作坊）
> **SOP 核心：** 财务/客户/内部流程/学习成长四维度 KPI 体系 + 因果链假设 + 行业 KPI 对标

- [ ] Subtask 9.1: 🔴 红 — 编写 `test_bsc_scorecard_mixed_data.py` 声明失败测试（[A]）
- [ ] Subtask 9.2: 🟢 绿 — 填充 frontmatter
- [ ] Subtask 9.3: 🔴 红 — 编写 SOP 内容失败测试（[B]：含 templates/bsc_kpi_scorecard.md）
- [ ] Subtask 9.4: 🟢 绿 — 编写 SOP + references（scoring_anchors KPI 目标档位锚点）+ templates
- [ ] Subtask 9.5: 🔴 红 — 编写 [C] 失败测试
- [ ] Subtask 9.6: 🔴 红 — 编写 [D] 失败测试
- [ ] Subtask 9.7: 🟢 绿 — 对齐转绿
- [ ] Subtask 9.8: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] bsc-scorecard 成熟化完成，单测全绿（四循环）
- [ ] 23 Skills 解析回归零失败

---

### Task 10: kpi-tree Skill 成熟化

**关联 AC:** AC-1, AC-2, AC-3

> **数据源（SSOT）：** `china-nbs` + `newsapi`（2 源，newsapi Key 敏感）
> **内部数据主体：** 内部 KPI 现值 + 数据仓库导出
> **SOP 核心：** 战略目标 → 部门目标 → 个人目标分解树 + 指标口径定义 + 行业指标参照

- [ ] Subtask 10.1: 🔴 红 — 编写 `test_kpi_tree_mixed_data.py` 声明失败测试（[A]）
- [ ] Subtask 10.2: 🟢 绿 — 填充 frontmatter
- [ ] Subtask 10.3: 🔴 红 — 编写 SOP 内容失败测试（[B]：含 templates/kpi_tree_decomposition.md）
- [ ] Subtask 10.4: 🟢 绿 — 编写 SOP + references + templates
- [ ] Subtask 10.5: 🔴 红 — 编写 [C] 失败测试
- [ ] Subtask 10.6: 🔴 红 — 编写 [D] 失败测试
- [ ] Subtask 10.7: 🟢 绿 — 对齐转绿
- [ ] Subtask 10.8: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] kpi-tree 成熟化完成，单测全绿（四循环）
- [ ] 23 Skills 解析回归零失败

---

### Task 11: change-management Skill 成熟化（注意 slug 无 -model 后缀）

**关联 AC:** AC-1, AC-2, AC-3

> **slug 强制：** `change-management`（非 `change-management-model`——manifest/TOOLS.md/catalog 三处锚定，见「命名规范声明」）
> **数据源（SSOT）：** `newsapi` + `tavily`（2 源，Epic 双源明确指定；双 Key 敏感——降级话术必写）
> **内部数据主体：** 内部变革数据 + 利益相关者立场评估（访谈）
> **SOP 核心：** 变革准备度评估 + 利益相关者矩阵 + 沟通计划 + 行业变革趋势参照

- [ ] Subtask 11.1: 🔴 红 — 编写 `test_change_management_mixed_data.py` 声明失败测试（[A]）
- [ ] Subtask 11.2: 🟢 绿 — 填充 frontmatter
- [ ] Subtask 11.3: 🔴 红 — 编写 SOP 内容失败测试（[B]：含 templates/change_stakeholder_assessment.md）
- [ ] Subtask 11.4: 🟢 绿 — 编写 SOP + references（scoring_anchors 准备度/影响力锚点）+ templates
- [ ] Subtask 11.5: 🔴 红 — 编写 [C] 失败测试
- [ ] Subtask 11.6: 🔴 红 — 编写 [D] 失败测试
- [ ] Subtask 11.7: 🟢 绿 — 对齐转绿
- [ ] Subtask 11.8: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] change-management 成熟化完成，单测全绿（四循环）
- [ ] 23 Skills 解析回归零失败

---

### Task 12: 集成测试（真实服务 + 双源基准 + 内外融合）

**关联 AC:** AC-4

> **性质说明：** 真实 Engine + 真实 Resolver + 真实 Redis（测试端口）；Mock 仅限 LLM/Sandbox/数据源适配器（Stub 可编程替身注入 adapters Mapping，规避 Key 条件注册依赖）。范本：4-1c `test_skill_data_collection.py`（7 用例结构 + 双租户 fixture + 内容分派 LLM Stub）。

#### 集成测试实现

- [ ] Subtask 12.1: 🔴 红 — 编写 `tests/integration/application/test_skill_mixed_data.py` 骨架（`pytestmark = [pytest.mark.integration, pytest.mark.xdist_group("data-source-cache")]` + 双租户隔离 fixture + Stub 适配器工厂 + AsyncMock LLM 内容分派按 Skill 生成含标记代码（**分派对象是 Code 阶段返回代码**——Round 2 勘正 AC-4 概念错位：Think prompt 由 Engine 构造，LLM Stub 是接收方）+ **arguments 内部数据进入 Think prompt 断言辅助（机制同场景 8 三要素：prompt 捕获 + 「规划执行步骤」识别 + repr 子串断言；`_run_skill` 扩签名传 arguments，per-slug 代表性 arguments 从 `skill_io_schemas.yaml` required 字段程序化构造最小合法实例——SSOT 防漂移，Round 2 钉死）**）
- [ ] Subtask 12.2: 🟢 绿 — 10 个 Skills 全链路用例（10-slug 参数化：每 Skill 2 源 `call_count == 1` + `EvidencePackage.data_sources` 溯源元数据断言 source_name/freshness_score/confidence ∈ [0,1]）
- [ ] Subtask 12.3: 🟢 绿 — 缓存与租户断言（首轮绝对计数守卫 `>= 1` + 二次执行不增 + 跨租户 `tenant_b == first + 1` 绝对断言，4-1c R2-F1 判别力先例）
- [ ] Subtask 12.4: 🟢 绿 — Key 缺失降级用例（**单敏感 Skill 参数化：ge-mckinsey/value-chain/vrio/kpi-tree，物理缺其中 1 个敏感源**——Round 2 勘正：双敏感 Skill 全缺会 411 直传；→ SUCCESS + `DataSourceFetchFailed` 且 `evt.error_code == "EXCEPTION_411"`——4-1c R1-P1-1 判别力先例；另设双敏感全缺对照用例断言 411 直传）
- [ ] Subtask 12.5: 🟢 绿 — 源不可用部分失败收敛用例（behavior=unavailable → 其余源正常注入）
- [ ] Subtask 12.6: 🔄 重构 — 模板对应专项收尾：`tests/unit/application/skills/test_schema_template_alignment.py`（10 Skill 参数化双向断言 + 四段式结构 + required 标注）全绿（Task 2-11 [D] 循环的汇总参数化文件，复用契约库断言函数）
- [ ] Subtask 12.7: 🔄 重构 — `pytest -n 8` 并行验证 + 连续 5 次无随机失败

**完成标准/Definition of Done:**
- [ ] 集成测试全绿（真实 Redis 不可用时动态 skip）
- [ ] 双源覆盖/缓存/租户/降级断言全部通过（411 语义断言含 error_code）
- [ ] 模板对应专项测试全绿
- [ ] 并行稳定（-n 8 连续 5 次零随机失败）

---

### Task 13: SDD 架构约束验证测试

**关联 AC:** AC-5

> **性质说明：** SDD 规范验证测试（非 TDD 单元测试）。范本：4-1c `test_arch_skill_data_collection.py`（三测试类 + 常量区结构；**不复刻已删除的恒真模式**：`test_domain_layer_untouched_by_story` / `TestComplianceReport`——R1-P1-2 / R1-P2-1 教训）。

#### 架构验证测试实现

- [ ] Subtask 13.1: 创建 `tests/unit/architecture/test_arch_skill_mixed_data.py`（常量区：`TARGET_SLUGS`（10）/ `NON_TARGET_SLUGS`（7，import 或对齐调整后清单）/ SSOT 从契约库 import——禁止复制，R2-F3）
- [ ] Subtask 13.2: 实现三方一致性校验（SSOT 表 ↔ 10 个 SKILL.md frontmatter data_sources ↔ 适配器 `get_metadata()` name/url/api_type/ttl；适配器真实实例化——Key 敏感源占位 Key、china-nbs 注入 AsyncMock crawler，仅读元数据零网络）
- [ ] Subtask 13.3: 实现生产链路回归校验（wiring 文件 `strategic_analysis.py` / `run_tool_chain.py` / `tool_execution_engine.py` 三文件零 `src.infrastructure` import + 源码含 `tool_metadata`/`load_sop` 特征串（Engine 文件含 `tool_metadata`）+ `inspect.signature(ToolExecutionEngine.__init__)` 签名锁定——Round 1 D2-A 勘正与 AC-5 文件集统一为三文件）
- [ ] Subtask 13.4: 实现 Skills 内容约束校验（10 个 SKILL.md ≤500 行 + frontmatter 必需字段 + data_sources 非空 + **16 Skill 最终态全量断言：`SKILL_DATA_SOURCES` ∪ `MIXED_SKILL_DATA_SOURCES` 并集内全部 Skill 物理声明非空且 name 集合 == SSOT（Subtask 1.4 中间态安全化的最终态闭环，Round 2 补定）** + 7 个 4-1e 目标空 tuple + 4-1c 6 Skill 声明不变 + **10 个 SKILL.md `version: 1.0.0` 保持不变断言（Round 2 提示项固化——4-1c 先例成熟化不升版，防 Agent 自作主张）**）
- [ ] Subtask 13.5: 运行完整测试套件并确认全绿

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过
- [ ] 任何违规导致测试失败（三方漂移/签名变更/行数超限/回归网破坏均可检出）
- [ ] 循环依赖检测使用 ruff/isort（不引入额外工具）

---

### Task 14: 开发结束验收测试（含文档同步）

**关联 AC:** AC-6

> **性质说明：** 对 Story 收尾阶段交付物与完成清单的最终验收 + 配套架构文档同步。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | Task 0 已编写 feature + BDD 骨架（确认失败）；本 Task 补齐全部场景步骤实现 |
| 🟢 绿 | 完成 `tests/acceptance/test_acceptance_skill_mixed_data.py` 全部步骤（真实服务 + Fake 仅限适配器/LLM/Sandbox + Redis 场景级独立客户端） |
| 🔄 重构 | 收敛场景命名、统一断言表达 + 文档同步 |

- [ ] Subtask 14.1: 场景 1 — Happy Path：swot-tows 全链路（2 源并发采集 + arguments 内部数据融合 + 溯源元数据）
- [ ] Subtask 14.2: 场景 2 — Happy Path：其余 9 个 Skills 参数化验证（**场景大纲 + Examples 表 slug 单列**——Round 2 钉死：对齐 4-1c 场景 2 形态（feature :35-41 slug 单列，源集合运行时查 SSOT 常量），断言双源采集 + DATA_SOURCES 键集合；内外融合断言不入本场景，仅场景 1/8 + 集成 Task 12 承载）
- [ ] Subtask 14.3: 场景 3 — Edge：白名单外数据源 → `BusinessRuleViolationError(207)`，断言 error.code + error.message
- [ ] Subtask 14.4: 场景 4 — Edge：数据源不可用 → 部分失败收敛 + `DataSourceFetchFailed` 事件（error_code 断言）
- [ ] Subtask 14.5: 场景 5 — Edge：Key 缺失降级（**限定单敏感源 Skill：kpi-tree 物理缺 newsapi 留 china-nbs**——Round 2 勘正：双敏感 Skill 全缺会 411 直传而非部分收敛；断言 SUCCESS + `DataSourceFetchFailed` `error_code == "EXCEPTION_411"` + 内部数据继续分析 + 数据缺口标注——混合数据型特有降级路径；可另加「双敏感全缺 → 411 直传」对照断言锁死全失败契约）
- [ ] Subtask 14.6: 场景 6 — Edge：缓存命中（二次执行 cache_hit=True，外部调用次数不增）+ 新鲜度元数据
- [ ] Subtask 14.7: 场景 7 — Edge：未成熟化 Skill（4-1e 目标，data_sources 空 tuple）含标记 → 207（安全失败）
- [ ] Subtask 14.8: 场景 8 — Edge：内外数据融合双通道并存（arguments 内部数据进入 Think prompt + 外部基准 DATA_SOURCES 注入同时成立；**观测机制三要素（Round 2 钉死）**：① Fake LLM `_llm_dispatch` 内 append `context["llm_prompts"]` 捕获全部 prompt；② Think 阶段识别特征串「规划执行步骤」（对齐 4-1c 用「生成代码」识别 Code 阶段的先例，`tool_execution_engine.py:521`）；③ 断言 Think prompt 含 arguments 的 **Python repr 子串**（Engine 以 f-string 注入 dict repr 单引号形态，**非 json.dumps**——断言 json 序列化子串必假红）+ 断言注入代码 preamble 含 `DATA_SOURCES`。场景分工：场景 1 = 链路 Happy（swot 全链路），场景 8 = 双通道并存专项断言；模板字段↔Schema 对应由 `test_schema_template_alignment.py` 单元层承载，不入 BDD）
- [ ] Subtask 14.9: 运行开发结束验收测试并确认通过 + 配套文档同步（architecture.md §17.3 状态 + §17.3.3 追加 + 决策表 + 修订历史 + sisys-uni-exception-design.md §3.3.2 复用声明）+ 完成清单逐项确认
- [ ] Subtask 14.10: 运行 `pytest`、`ruff check`、`mypy`、**`pre-commit run --all-files`** 收尾校验（Round 1 D2-B 勘正补定：原稿收尾清单缺 pre-commit；DoD 勾选证据形态 = 逐提交 hooks 全项 Passed + 收尾 all-files 实跑输出或等效独立复跑证据，4-1c Round 5 教训前置承接）

**完成标准/Definition of Done:**
- [ ] 全部 Gherkin 场景通过（8 场景）
- [ ] 配套文档同步完成
- [ ] 完成清单逐项验证确认
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md) §17.3 工具箱架构 + §17.3.3 数据采集基础设施 + §1.5 CLI+Skills 设计原则 + §13.11 Skills 目录结构

- **架构模式:** 六边形架构（Ports & Adapters）+ Anthropic Claude Code Skills 渐进式披露（L1 ≤1.2K tokens / L2 ≤500 行 / L3 按需）+ Hub-and-Spoke 单根目录（`src/application/skills/<slug>/`）
- **设计约束:** 领域层零依赖；依赖方向 interfaces→application→domain←infrastructure；端口仅经 composition_root 注册；本 Story 四层 Python 代码零改动（纯内容成熟化）
- **Skills 触发原则（P5/P6）:** description 即触发器（Less scaffolding）；负向触发章节强制
- **代码优先（P7）:** 确定性任务迁出 SKILL.md 到 `scripts/*.py`（pestel `aggregate_scores.py` 为先例；本 Story 10 Skill 以模板采集为主，scripts/ 保持空目录可接受——确定性聚合需求出现时再迁出）
- **技术栈:** Python 3.11+ / PyYAML（frontmatter）/ pytest-bdd（验收）—— 本 Story 不引入新依赖

### 关键架构决策

**来源:** 本 Story 设计调研（2026-09-28，3 视角并行代码调研：Skills 基础设施与结构 / 数据源端口与引擎链路 / 测试实现模式）

| 决策点 | 选中方案 | 备选方案 | 依据 |
|--------|---------|---------|------|
| D1: 内部模板载体 | ✅ **Markdown 模板（templates/*.md，表格形式）**（9/10） | Excel/XLSX 二进制模板（Epic AC 2 字面）（3/10） | 4-1c 先例（templates/*.md ×6）；L3 渐进加载按需读取；文本资产可断言（[D] 循环双向断言依赖）；git diff 友好；Excel 二进制不可断言不可 diff；Epic 字面偏差留痕（R6） |
| D2: 外部数据源策略 | ✅ **统一 2 源双源交叉验证（10/10 Skill）**（9/10） | 按 Epic 字面单源（ge-mckinsey 仅 WB）（5/10）/ 凑 3 源（4/10） | 混合数据型内部数据是主体、外部源仅行业基准参照；4-1c D4/D8 已确立 2 源双源交叉为可接受终态（Epic owner 签收先例）；单源无交叉验证；凑同质源违背三角化本意 |
| D3: references 三件套语义 | ✅ **data_fusion.md（内外数据融合规范）替代 4-1c triangulation.md 角色**（8/10） | 沿用 triangulation.md 命名（6/10） | 混合数据型的交叉验证主轴是「外部基准 ↔ 内部数据」而非「外部多源」；data_fusion.md 含冲突处理（外部基准与内部认知矛盾处置）与内外权重；沿用命名则名实不符（2 源外部谈不上多源三角化） |
| D4: 新异常/端口/事件 | ✅ **三不新增 + 零 Python 生产代码改动**（10/10） | 新增内部数据采集异常/通道（1/10） | 纯内容 Story；全部失败路径已被 201/207/101/302/411/412/413 覆盖；内部数据经 `ToolCall.arguments` → Think prompt 是既有语义；同义异常/端口重复定义是红线 |
| D5: 内部数据执行期通道 | ✅ **不新增 `INTERNAL_DATA` 注入机制（决策 D4 展开）**（9/10） | 类比 `DATA_SOURCES` preamble 新增确定性注入（4/10） | 模板是「采集期」工具（工作坊填写 → 构造 arguments），非「执行期」通道；arguments 进 Think prompt 既有语义已满足；无生产消费方诉求前不新增机制（Simplicity First） |
| D6: SSOT 契约库组织 | ✅ **新建 `skill_mixed_data_contracts.py`，跨 Story 共享常量（`ADAPTER_SSOT`/`KEY_SENSITIVE_SOURCES`/`DATA_SOURCE_MARKER_PATTERN`/`REQUIRED_SOP_SECTIONS`/`SKILL_MD_MAX_LINES`）一律从 4-1c 库 import**（Round 1 D1-B/D2-B 勘正收窄边界：新库仅自定义混合数据特有常量与断言，防 4-1e 第三次复制）（9/10） | 扩展 4-1c `skill_data_collection_contracts.py`（6/10）/ 新库全量自定义常量（原稿形态，4/10——四常量复制违反 R2-F3） | 4-1c 库语义绑定「外部数据型 6 Skill」（其 `SKILL_DATA_SOURCES` 常量被 3 处 import，扩展污染既有语义）；跨 Story 稳定事实必须单一来源；新库承载 `MIXED_SKILL_DATA_SOURCES` + `TEMPLATE_REQUIRED_SECTIONS` + 模板断言函数 |
| D7: IO 契约 SSOT 载体 | ✅ **扩充既有 `skill_io_schemas.yaml`（追加 10 条目）**（9/10） | 新建独立 yaml（5/10） | 单一 SSOT 文件（16 个 Skill 契约一处可查）；4-1c 已建解析与断言链路（**按 slug 索引**——Round 2 勘正：`load_io_contract` 以 `contracts["skills"][slug]` 取条目，顶层 `story:` 字段是无消费方的文档标识，非区分键；Task 0.2 将其更新为 `story: [4-1c, 4-1d]` 列表形态）；新建则双文件漂移 |
| D8: 回归网调整机制 | ✅ **Task 1.4（契约库 Task 内）一次性预调整：NON_TARGET_SLUGS 17→7 两处 + `test_frontmatter_data_sources.py` 中间态安全化重构**（Round 1 勘正时序死锁 + Round 2 重写 DECLARING 处理——「6→16 扩清单」经回归核查证伪：`:141-149` 非空断言致扩清单后 10 个未填 Skill 必红、红窗口贯穿并行期，死锁被搬家而非消除；重构方案「物理非空者必 ∈ SSOT 并集」两向安全）（9/10） | 每 Skill Task 逐个移除（5/10，多 Agent 并发编辑共享文件冲突）/ 维持原稿 Task 2.9 位置（3/10，并行 DoD 不可满足）/ Round 1 的扩清单方案（2/10，非空断言中间态必红） | 一次调整 + 各 Skill 独立测试文件断言自身声明（TDD 渐进转绿）；中间态断言两向安全（防误填 ∉ 并集即红 / 不要求已填）；最终态 16 全非空由 Task 13.4 闭环；4-1e 实施期同理演进 |

### 项目结构说明 Project Structure（本 Story 新增/修改）

```
src/
├── application/
│   └── skills/
│       ├── swot-tows/
│       │   ├── SKILL.md                              # [修改] frontmatter +2 源声明 + IO Schema + SOP 成熟化
│       │   ├── references/                           # [新增三件套]
│       │   │   ├── data_fusion.md                    # 内外数据融合规范（冲突处理/内外权重）
│       │   │   ├── scoring_anchors.md                # SWOT 强度 1-5 锚点
│       │   │   └── workshop_guide.md                 # 战略工作坊 2-4 小时引导
│       │   └── templates/                            # [目录新建]
│       │       └── swot_factors_collection.md        # 四象限采集矩阵（字段 ↔ input_schema）
│       ├── ansoff-matrix/                            # [修改+新增] 同结构（2 源 wb+imf）
│       ├── value-curve-analysis/                     # 同结构（2 源 tavily+newsapi）
│       ├── ge-mckinsey-matrix/                       # 同结构（2 源 wb+tavily）
│       ├── space-matrix/                             # 同结构（2 源 wb+imf）
│       ├── value-chain-analysis/                     # 同结构（2 源 tavily+china-nbs）
│       ├── vrio-framework/                           # 同结构（2 源 uspto+tavily）
│       ├── bsc-scorecard/                            # 同结构（2 源 china-nbs+wb）
│       ├── kpi-tree/                                 # 同结构（2 源 china-nbs+newsapi）
│       └── change-management/                        # 同结构（2 源 newsapi+tavily，slug 无 -model）
tests/
├── unit/
│   ├── application/
│   │   └── skills/
│   │       ├── skill_mixed_data_contracts.py         # [新增] 共享契约断言库（混合数据特有常量 + 断言函数；共享常量 import 4-1c 库）
│   │       ├── test_skill_mixed_data_contracts.py    # [新增] 契约库永久自检测试（Round 1 D2-B 勘正）
│   │       ├── test_<slug>_mixed_data.py             # [新增] ×10 Skills 内容测试
│   │       ├── test_schema_template_alignment.py     # [新增] 模板字段↔Schema 叶子键双向断言（10 参数化，Task 12.6 创建）
│   │       ├── test_pestel_analysis_data_collection.py  # [修改] NON_TARGET_SLUGS 17→7（Task 1.4）
│   │       └── test_frontmatter_data_sources.py      # [修改] 测试语义中间态安全化重构（Task 1.4，Round 2 设计重写）
│   └── architecture/
│       ├── test_arch_skill_mixed_data.py             # [新增] 三方一致/签名锁定/行数/回归网
│       └── test_arch_skill_data_collection.py        # [修改] NON_TARGET_SLUGS 17→7（Task 1.4）
├── integration/
│   └── application/
│       └── test_skill_mixed_data.py                  # [新增] 10 Skills 全链路 + 双源 + 降级
└── acceptance/
    ├── contracts/
    │   └── skill_io_schemas.yaml                     # [修改] 追加 10 条目（16 Skill 单一 SSOT）
    ├── test_acceptance_skill_mixed_data.feature      # [新增] 8 场景
    └── test_acceptance_skill_mixed_data.py           # [新增] BDD 步骤
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 4.1c](./4-1c-skills-data-collection-integration.md)（✅ done，5 轮文档审查 + 5 轮代码审查收敛）+ [Story 4.1b](./4-1b-skills-feat-enhancement.md)（✅ done，第三审查周期 5 轮收敛 v1.7.0）

**关键学习/Key Learnings:**
- **文件命名红线**：实施期用户明确约束「禁止使用故事编号命名」，4-1c 曾发生批量重命名返工——新文件一律功能性命名（`test_<slug>_mixed_data.py` 等），Epic 字面文件名不作数
- **类型注解完整性**：4-1c Round 1 P0 教训——32 处 `# type: ignore` 全部因 fixture/测试参数缺注解产生；新增测试文件从第一行就带齐注解（fixture `-> SkillDocument`、测试参数 `document: SkillDocument`、工厂 `-> dict[str, DataSourcePort]`）
- **判别力优先**：断言必须能检出真实缺陷（4-1c R1-P1-1 语义断言 `error_code == "EXCEPTION_411"`、R1-P1-4 首节点钉住、R2-F1 缓存首轮绝对守卫 + 双租户交叉）；禁止恒真断言（R1-P1-2/R1-P2-1 已删除模式勿复刻）、禁止裸子串匹配（用词边界正则）
- **SSOT 单一来源**：常量（`ADAPTER_SSOT`/`MIXED_SKILL_DATA_SOURCES`）统一 import 契约库，禁止架构/集成/验收三处复制（R2-F3）
- **Redis 场景级独立客户端**：session 级共享客户端跨场景复用抛 "Event loop is closed"（连接池绑定已关闭循环）；BDD 步骤禁 `@pytest.mark.asyncio`，用共享 `event_loop` + `run_until_complete()`
- **xdist 分组**：共享 Redis 缓存键的测试复用 `xdist_group("data-source-cache")`，pytestmark 用 list 形式
- **Key 安全**：SOP/模板/日志/异常消息零 API Key 泄露；input_examples 用环境变量引用形式
- **LLM Stub 内容分派**：集成/验收测试的 LLM AsyncMock 按 prompt 内容特征分派（对阶段重排稳健），禁止序数分派（4-1c R2-F1 教训：序数分派错位时测试空转通过）
- **captured 死参数禁令**（Round 1 D1-B 勘正补定——4-1c R1-P2-3 教训未承接）：凡测试内 `captured["..."] = ...` 写入必须有对应读取/断言（场景 8 的 prompt 捕获与集成内外融合断言正是同型高危区），写入无消费即删除
- **新断言变异演示**（Round 1 D1-B 勘正补定——4-1c 判别力经验未承接）：本 Story 全新断言（`assert_template_schema_alignment` / 双通道并存断言 / data_fusion 三件套断言）至少各做一次变异演示实证（删模板字段 → 红 / 去 arguments → 双通道红 / 删锚点章节 → 红）后还原
- **并行实施可行但有时序前置**：4-1c 曾以 3 并行 Agent + 主会话实施 6 Skill；4-1d 的 10 Skill 并行前置 = **Task 1（契约库 + Subtask 1.4 回归网预调整）完成**（Round 1 D2-B 勘正：仅契约库前置不够，回归网未预调整时并行 Agent 填声明必触既有回归红）；并行期各 Agent 回归范围限自有测试文件 + 两个解析回归文件，全量回归合入后主会话执行

**应用到本故事/Applied to This Story:**
- [ ] 全部新文件功能性命名（「命名规范声明」节强制，File List 留痕）
- [ ] 测试文件类型注解从第一行写齐（DoD 检查项）
- [ ] 411 语义断言（error_code）+ 模板对应双向断言 + 缓存绝对守卫（判别力三先例全复用）
- [ ] `ADAPTER_SSOT` import 复用 + `MIXED_SKILL_DATA_SOURCES` 单一来源（D6）
- [ ] BDD/集成沿用 4-1b/4-1c 基建（共享 event_loop、场景级 Redis 客户端、xdist_group、双租户 fixture、_FakeDataSourceAdapter 范本）
- [ ] Task 14 同步 architecture.md + sisys-uni-exception-design.md（对齐 4-1c 文档同步先例）
- [ ] Task 2-11 可多 Agent 并行实施（前置 = **Task 1 全部完成含 Subtask 1.4 回归网预调整**，Round 1 勘正；并行期各 Agent 回归范围限自有测试文件 + 两个解析回归文件）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code（glm-5.3[1m]） |
| **Version** | create-story workflow（template.md v2.9.0 结构） |
| **Execution Date** | 2026-09-28（create-story） |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/config.yaml` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Story 4.1d 定义，line 771 / 1004-1047） |
| **架构文档** | `docs/architecture/architecture.md`（§17.3 工具箱 / §17.3.3 数据采集基础设施 / §1.5 Skills 原则 / §13.11 目录结构） |
| **异常设计** | `docs/architecture/sisys-uni-exception-design.md`（§3.3 编码分配策略） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/4-1c-skills-data-collection-integration.md`（✅ done） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` Story 4.1d 提取（10 个混合数据型 Skills，line 1004-1047）
- [x] 架构约束从 `architecture.md` §17.3/§17.3.3/§1.5/§13.11 提取
- [x] 前一个故事学习经验整合（4.1c 五轮文档 + 五轮代码审查沉淀 + 4.1b 第三审查周期收敛态）
- [x] 多 Agent 并行调研整合（Skills 基础设施与 10 Skill 现状 / DataSource 端口与引擎链路 / 4-1c 测试实现模式 3 视角，全部结论附文件:行号证据）
- [x] **4-1c 留项 R1-P2-10/11 收敛状态确认**：已由 4-1b 第三审查周期收敛（commit `0d550dda`，`DataSourceRef.__post_init__` 全量类型门禁），本 Story 仅回归验证（Task 0.7）
- [x] **8 项显式决策登记**：D1 Markdown 模板（Epic「Excel」字面偏差留痕）/ D2 统一 2 源 / D3 data_fusion.md 语义 / D4 三不新增+零代码改动 / D5 不新增内部数据执行期通道 / D6 契约库组织 / D7 IO 契约扩充 / D8 回归网调整机制
- [x] **命名规范声明**：功能性命名强制（覆盖 Epic `_4_1d` 字面）+ `change-management` slug 陷阱（无 -model 后缀）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（Task 0 + Task 1-14，每 Skill Task 含 [A]/[B]/[C]/[D] 四循环）
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/4-1d-skills-framework-enhancement.md`

**待创建的文件/To Be Created (Dev Story 实施):**

源码（修改，纯资源零 Python）：
- `src/application/skills/<slug>/SKILL.md` ×10 — frontmatter 2 源声明 + IO Schema + SOP 成熟化（Task 2-11）
- `tests/acceptance/contracts/skill_io_schemas.yaml` — 追加 10 条目（Task 0.2）

源码（新增资源）：
- `src/application/skills/<slug>/references/data_fusion.md` ×10 — 内外数据融合规范
- `src/application/skills/<slug>/references/scoring_anchors.md` ×10 — 评分锚点
- `src/application/skills/<slug>/references/workshop_guide.md` ×10 — 工作坊引导
- `src/application/skills/<slug>/templates/<功能名>_template.md` ×10 — 内部数据采集模板（命名见「内部数据契约」表）

测试（新增）：
- `tests/unit/application/skills/skill_mixed_data_contracts.py` — 共享契约断言库（Task 1）
- `tests/unit/application/skills/test_skill_mixed_data_contracts.py` — 契约库永久自检测试（Task 1.1，Round 1 D2-B 勘正）
- `tests/unit/application/skills/test_<slug>_mixed_data.py` ×10 — Skills 内容单元测试（Task 2-11）
- `tests/unit/application/skills/test_schema_template_alignment.py` — 模板↔Schema 叶子键双向断言（Task 12.6）
- `tests/unit/architecture/test_arch_skill_mixed_data.py` — 三方一致/签名锁定/行数/回归网（Task 13）
- `tests/integration/application/test_skill_mixed_data.py` — 10 Skills 全链路集成（Task 12）
- `tests/acceptance/test_acceptance_skill_mixed_data.feature` + `.py` — BDD 8 场景（Task 0/14）

测试（修改，回归网三处，Task 1.4 一次性预调整）：
- `tests/unit/application/skills/test_pestel_analysis_data_collection.py` — `NON_TARGET_SLUGS` 17→7 + docstring「17 个」字样
- `tests/unit/architecture/test_arch_skill_data_collection.py` — `NON_TARGET_SLUGS` 17→7 + docstring「17 个」字样
- `tests/unit/application/skills/test_frontmatter_data_sources.py` — 测试语义中间态安全化重构（Task 1.4；Round 3 勘正：原记「6→16 扩清单」方案已被 Round 2 证伪重写）

文档（同步，Task 14.9）：
- `docs/architecture/architecture.md` — §17.3 状态块 + §17.3.3 追加 + 决策表 + 修订历史
- `docs/architecture/sisys-uni-exception-design.md` — §3.3.2 追加 4-1d 零新增复用声明（引用式）
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — 状态流转

> **命名规范说明**：全部交付文件功能性命名（无 `_4_1d` 后缀），epics_v1.0.md line 1032 / 1038-1041 的
> `test_*_4_1d.py` 等字面文件名以用户约束为准不作数（4-1c 实施期确立 + 记忆 feedback_no_story_number_in_filenames）。

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 4.1d |
| **Story Key** | 4-1d-skills-framework-enhancement |
| **File** | `_bmad-output/implementation-artifacts/stories/4-1d-skills-framework-enhancement.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 4: 战略工具箱 |
| **价值组** | 战略工具执行能力（工具数据驱动化） |
| **优先级** | P0-7 |
| **覆盖 FR** | FR-ST-01（工具分析数据驱动化）+ FR-IF-02（Skills 渐进式加载增强） |
| **前置 Story** | 4-1b-skills-feat-enhancement（✅ done）/ 4-1a-strategic-tool-impl（✅ done）/ 4-1c-skills-data-collection-integration（✅ done） |
| **后续 Story** | 4-1e-skills-internal-framework（7 个内部框架 Skills） |
| **估算工作量** | **15-21 人天**（Epic 估算每 Skill 1-1.5 人天 ×10 = 10-15 + Task 0/1 契约 1.5 + 集成/架构/验收测试 2.5-3 + 文档同步 0.5 + 缓冲；Task 2-11 可并行压缩墙钟周期。**单价下修理由（Round 1 D2-B 勘正登记）**：虽每 Skill 范围为 4-1c 超集（+templates +[D] 循环 +data_fusion），但零代码改动 + 全部模式有 4-1c 先例可循 + 契约库/回归网前置消除返工，低端 1 人天仅在严格复用范本时可达；若实施期发现单 Skill 超 1.5 人天应回溯本估算） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0 + Task 1-14，共 15 个 Task）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 至 AC-6，含 6 个 Edge Cases）
3. [x] Architecture constraints extracted 架构约束已提取（六边形 4 层零 Python 改动声明 + Skills 内容约束 + 签名保护）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（4.1c 双五轮审查 + 4.1b 收敛态 + 命名/注解/判别力三红线）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 本 Story 经 5 轮 D1~D5 循环文档审查（2026-09-28 起），逐轮记录修复项。

#### Round 1（D1 四视角调研 + D2 双视角审查，P1×8 + P2×24 全修——Round 3 对账勘正计数）

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| D-R1-P1-1 | **第三处回归调整点未识别**：`test_frontmatter_data_sources.py:131-164` `DECLARING_SLUGS` 硬编码 6 + 非声明组空 tuple 断言，10 Skill 填声明后必红——与故事「零修改」承诺直接矛盾 | **P1** | 范围澄清/AC-1/契约测试清单/归属表/File List 五处补第三处调整（DECLARING_SLUGS 6→16，Task 1.4 执行位） |
| D-R1-P1-2 | **嵌套 Schema ↔ 模板字段映射约定缺失**：swot-tows catalog `input_schema` 为嵌套结构（`internal_factors.{strengths,...}`），按原稿「模板字段 == properties 顶层键」断言必然失败或倒逼拍平 Schema（违反 catalog 兼容强制），首个 Skill 即卡壳 | **P1** | 「内部数据契约」节固化**嵌套展开约定**：比对粒度 = 递归叶子键集合，顶层键以模板分区标题承载；AC-3/Task 0.2/1.2/[D] 循环同步 |
| D-R1-P1-3 | 复用异常表缺 EXCEPTION_302 行，与 Task 0 checklist / D4 决策「复用 302」自相矛盾，且将传播至架构文档 | **P1** | 异常表补「数据源超时 \| TimeoutError \| EXCEPTION_302」行 |
| D-R1-P1-4 | 共享常量（KEY_SENSITIVE_SOURCES/DATA_SOURCE_MARKER_PATTERN/REQUIRED_SOP_SECTIONS/SKILL_MD_MAX_LINES）列为新库自定义——复制违反 R2-F3 单一来源教训（4-1e 将第三次复制） | **P1** | Task 1.2/D6 决策收窄：新库仅自定义混合数据特有常量（MIXED_SKILL_DATA_SOURCES/TEMPLATE_REQUIRED_SECTIONS）+ 断言函数，五共享常量一律 import 4-1c 库 |
| D-R1-P1-5 | captured 死参数 + 变异演示两条 4-1c 审查经验未承接（场景 8 prompt 捕获正是同型高危区；全新断言无判别力实证要求） | **P1** | 学习经验节补「captured 写入必须有读取断言」+「新断言变异演示」；AC-3 验证标准补变异演示项 |
| D-R1-P1-6 | **并行时序死锁**：回归网调整在 Task 2.9（首个 Skill 末尾），Task 3-11 并行 Agent 在其合入前填声明必触既有回归红且 DoD 不可满足；更坏路径是多 Agent 并发改共享回归文件 | **P1** | 调整前置至 **Subtask 1.4**（Task 1 内一次性预调整三处），「先调网再并行」；D8 决策/Task 2/学习经验/并行声明同步更新 |
| D-R1-P1-7 | 适配器对齐表 tavily 消费方漏 value-chain（5 应为 6），破坏与「7 个 Key 敏感」的交叉核算 | **P1** | 补 value-chain（6 个消费方） |
| D-R1-P1-8 | Task 0 Gherkin checklist 第 6 个 Edge 写「模板对应破坏」，与 AC-6/Subtask 14.8「内外融合双通道并存 + 模板对应不入 BDD」冲突 | **P1** | 统一为「内外数据融合双通道并存」并注勘正说明 |
| D-R1-P2 批 | 行号/指代/计数瑕疵 17 项：来源链接断链（多一层 `_bmad-output`）；skill_loader.py:94→:108；「SSOT 表逐字一致」四字段指代未拆分（主表无 url/api_type/ttl）；「D4/D8」缺「4-1c」前缀防歧义；catalog 锚定措辞（无 slug 字面量，经 UUID 间接）；scripts/ 空目录现状未述；「三项/四项」决策计数冲突；文档同步「D1-D7」漏 D8；§3.3.2 重号消歧（完整编码分配表）；Epic 编号文件名行号 1038-1044→1032/1038-1041；io_schemas.yaml 头部/story 字段同步未登记；docstring「17 个」字样；Task 0.6 红/绿拆分（场景 3/7 骨架期即绿）；Task 1.1 临时导入断言去向未定（改永久自检测试）；模板微格式三处断言语义未钉死（必填后缀/锚点字面串/缺口区表头）；Task 14.10 缺 pre-commit；AC-5 vs 13.3 文件集不统一；alignment 文件创建时点矛盾（Task 2 vs 12.6）；追溯矩阵 AC-1 漏 1.4 与回归网文件/AC-2 漏 .1-.2；估算单价低于 4-1c 先例未登记理由；勾选状态不同步；Subtask 0.1 决策登记不闭合（8 项）；data_fusion 基准粒度限制未声明；风险表缺 R9（嵌套映射+并行发散） | P2 | 逐项修正（含 D1-D 主会话分析补的基准粒度限制条款与 R9 风险） |

**Round 1 调研确认无需修复项**：D1-A 的 10 Skill 现状/SSOT 六源对齐/17→7 算术/解析能力/23 目录计数全部事实一致；D1-C 的 Epic 提取完整性/D8 承接一致（零 WIPO/EPO 字样）/slug 三处锚定/Defer 台账吻合（20 处 file:line 19 处命中）；D1-D 的 2 源语义匹配整体成立/三角化语义承接恰当（未把内部数据凑进来源数）/4-1d/4-1e 边界清单权威互补。

#### Round 2（D1A 修订回归核查 + D1B 残留深挖，P1×5 + P2×12 修复）

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| D-R2-P1-1 | **Round 1 修复「DECLARING_SLUGS 6→16 前置扩充」经回归核查证伪（设计级）**：`test_declaring_skills_frontmatter_carries_data_sources:141-149` 对清单成员断言**非空**，Task 1.4 扩清单后 10 个未填 Skill 必红、红窗口贯穿整个并行期——R1-P1-6 要消除的死锁被搬家而非消除（两个 P1 修复组合时未交叉核对） | **P1** | Subtask 1.4 设计重写为**测试语义中间态安全化重构**：非声明组空 tuple 断言 → 「物理非空者必 ∈ SSOT 并集 16（动态派生）」；非空断言改「凡声明必合法」；最终态 16 全非空由 Task 13.4 闭环；各 Skill Task 零触碰共享文件（消除并发编辑冲突）。全文 7 处「6→16」表述同步重写 |
| D-R2-P1-2 | **场景 5「Key 缺失降级」对双敏感 Skill 不可满足**：swot/value-curve/change-management 两源全敏感，adapters 物理缺源 → fetch_many 全失败直传 411（resolver:233-235，Round 3 行号勘正），不会得到「SUCCESS + 部分收敛」 | **P1** | AC-4/12.4/14.5 钉死单敏感 Skill（kpi-tree 缺 newsapi 留 china-nbs；集成参数化限定 4 个单敏感 Skill）+ 补「双敏感全缺 → 411 直传」对照断言（锁死全失败契约） |
| D-R2-P1-3 | Round 1 修复传播漏网：Task 2 标题「（含回归网调整）」+ [A] 重构行「回归网调整落地（两处）」残留——实施者照做重新引入 D8 死锁 | P1 | 两处清除（标题改「Task 2-11 实施范本」；重构行改「零触碰共享回归文件」） |
| D-R2-P1-4 | Round 1 修复传播漏网：Task 2 [D] 循环红行仍写「properties 键集合」——Round 1 自己定性为「必然失败」的原稿表述，写出来永远无法转绿 | P1 | 改「递归叶子键集合」并注 swot 四叶子键示例 |
| D-R2-P1-5 | R3 风险行仍写「Task 2 调整回归网」旧时序 | P1 | 更新为 Task 1.4 + 中间态安全化语义 + Task 13.4 闭环 |
| D-R2-P2 批 | 12 项：归属表 properties 残留；修复表「17 项」vs 实际枚举 24 项对账（v1.1.0 changelog 同步勘正）；场景 2 Examples 列未定（钉死 slug 单列）；场景 8 观测机制未给（三要素：prompt 捕获/「规划执行步骤」识别串/**repr 陷阱**——Engine f-string 注入 dict repr 单引号，断言 json.dumps 子串必假红）；12.1 断言机制 + per-slug arguments fixture 来源未定（钉死：yaml required 程序化构造）；AC-4 措辞概念错位（Stub 是 prompt 接收方非构造方）；Task 3-11 无范本显式引用 + TDD 节奏两套无解释；D7「按 story 字段区分」事实错误（实际按 slug 索引，story 字段无消费方）+ 其值未定（钉死 `[4-1c, 4-1d]` 列表）；output_schema 基准缺失（catalog 无 required 需补全 + data_sources 字段惯例未明说）；required_fields 逐源 SSOT 空洞（钉死全源统一 `[indicator, value]` 对齐 4-1c）；version 升版无断言（钉死保持 1.0.0）；input_examples query 混入 arguments JSON 的歧义（钉死独立标记行呈现） | P2 | 逐项钉死（详见各节 Round 2 勘正注记） |

**Round 2 调研确认**：Round 1 修订事实锚点质量极高（抽查 11 项 P2 + 8 处 file:line 全部实证命中、零虚构）；表格列数/Markdown 语法零破坏；R5 全部 catalog 行号命中；Task 0.6 红绿拆分与 fetch_many 语义自洽。

#### Round 3（Round 2 修订回归核查 + 设计独立推演，P1×1 + P2×3 修复）

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| D-R3-P1-1 | Round 2 修复传播漏网：契约测试清单（:288）与 File List（:1130）两处「DECLARING_SLUGS 6→16」**活性指令**残留（非勘正注记）——实施者照 File List 操作会重新引入 Round 2 已证伪的并行期必红死锁；D-R2-P1-1 声称「全文 7 处同步重写」不完备（实为 9 处） | **P1** | 两处改写为「测试语义中间态安全化重构（Task 1.4）」口径 |
| D-R3-P2-1 | 「P2×17」计数残留 ×2（修复表表头 + Next Steps）与 Round 2 对账后的「P2×24」矛盾 | P2 | 统一改 P2×24 |
| D-R3-P2-2 | resolver 全失败判定行号错误：3 处写 `:238-240`，实测正确锚点 `:233-235`（`if first_error is not None and not any(results): raise first_error`） | P2 | 行号勘正 |
| D-R3-P2-3 | AC-1 验证标准「7 个未触碰 Skill 空 tuple 断言」为重构前旧机制措辞（重构后空 tuple 断言已被并集语义包含） | P2 | 改「经『物理非空者必 ∈ SSOT 并集』语义守护——误填即 ∉ 并集红」 |

**Round 3 设计独立推演确认（不轻信 Round 2 论证）**：中间态安全化重构在 Task 1.4/Task 5/Task 11 后三个时间点**无红窗口**（实测推演）；场景 5 kpi-tree 部分收敛 SUCCESS 可达（fetch_many gather return_exceptions + `any(results)` 实测 :233-235）；场景 8 三要素命中（Engine f-string 实测 ：521-522）；守护无损（7 个 4-1e 空守护被并集语义包含且更强）；全部契约锚点抽查命中（story 字段/load_io_contract/required_fields 21 处/version 1.0.0）。**结论：三轮全部设计级风险已真实消除，本轮修完 4 项传播层问题即达收敛条件。**

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** （待 dev-story 完成后填写）
**审查模式:** （待填写）

#### 需决策 Decision Needed

- [ ] （待填写）

#### 已修复 Patch

- [ ] （待填写）

#### 已推迟 Defer

- [ ] 节点级注入（旁路+误拒双向）→ Story 4.2（4-1c 既定留项，本 Story 不收敛）
- [ ] `skill_io_schemas.yaml` data_sources.items 字段级化 + description 命名对齐 → Story 4.3（4-1c R2-F7 既定留项；本 Story 新增条目沿用现行粒度）
- [ ] StrategicAnalysisUseCase 的 composition_root 注册 + 接口层入口 → 入口 Story（4-1c R1-P2-13 既定留项，FR-IF-01 锚点）
- [ ] 异常 `to_dict()` 自动脱敏 → Story 5.x 安全专项
- [ ] `tests/unit/domain/ports/test_sandbox_session_query.py:38` 既有 `# type: ignore[misc]` → 归属 Story（4-4 遗留，4-1c R1-P2-14 留痕）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 文档审查 Round 1 完成（D1 四视角 + D2 双视角，P1×8 + P2×24 修复）
- [ ] 运行 `validate-create-story` 进行质量检查（可选）
- [ ] 运行 `dev-story` 开始实施（Task 2-11 可多 Agent 并行）
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.3.0
**创建日期/Created:** 2026-09-28
**最后更新/Last Updated:** 2026-09-28
**更新说明/Description:**
- v1.0.0: 创建故事文件（基于 epics_v1.0.md Story 4.1d + 4-1b/4-1c 完成资产 + 3 视角并行代码调研：Skills 基础设施与 10 Skill 现状 / DataSource 端口与引擎链路 / 4-1c 测试实现模式；8 项决策登记；4-1c 留项 R1-P2-10/11 收敛状态确认）
- v1.1.0: 文档审查 Round 1 完成（D1 四视角调研 + D2 双视角审查，全部结论附 file:line 证据并经主会话独立复核）：
  - **P1×8 修复**：① 第三处回归点识别（原稿「零修改」矛盾）② 嵌套 Schema 叶子键展开约定（原断言必然失败）③ 异常表补 302 行 ④ 共享常量 import 边界收窄 ⑤ captured 死参数 + 变异演示经验承接 ⑥ 并行时序死锁解消（回归网预调整前置至 Task 1.4）⑦ tavily 消费方补 value-chain ⑧ Edge 6 定义统一（内外融合双通道）
  - **P2×24 修正**（Round 2 对账勘正：原记 17 项实际枚举 24 项）：行号/指代/计数/断链/微格式契约/红绿拆分/永久自检/ pre-commit 证据链等（详见「文档审查修复」表）
- v1.2.0: 文档审查 Round 2 完成（D1A Round 1 修订回归核查 + D1B 残留深挖）：
  - **P1×5 修复**：① **Round 1「DECLARING_SLUGS 扩清单」方案证伪重写**（非空断言致并行期必红——死锁被搬家而非消除；改为测试语义中间态安全化重构 + Task 13.4 最终态闭环）② 场景 5 钉死单敏感 Skill（双敏感全缺会 411 直传而非部分收敛——原场景不可满足）③④⑤ Round 1 修复传播漏网清除（Task 2 标题/[A] 重构行/[D] 红行/R3 风险行）
  - **P2×12 修正**：场景 8 repr 陷阱与观测机制三要素/arguments fixture SSOT/AC-4 概念错位/Task 3 范本引用/D7 slug 索引事实勘正/output_schema 基准 + data_sources 惯例/required_fields 逐源 SSOT/version 锁定 1.0.0/input_examples query 形态等
- v1.3.0: 文档审查 Round 3 完成（Round 2 修订回归核查 + 设计独立推演）：
  - Round 2 设计级重写经独立推演与代码实测**全部成立**（中间态三时间点无红窗口/场景 5 SUCCESS 可达/三要素命中/守护无损/锚点全对）——三轮设计级风险全部真实消除
  - **P1×1 + P2×3 传播层修复**：6→16 活性指令残留 ×2（契约清单 + File List）/P2×17→24 计数残留 ×2/resolver 行号 233-235 勘正/AC-1 旧机制措辞
