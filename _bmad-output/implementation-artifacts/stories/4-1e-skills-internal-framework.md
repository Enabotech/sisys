# Story 4.1e: Skills 内部框架增强（内部用户输入型 Skills 完善）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 工具工程师,
**I want** 7 个纯内部框架 Skills（value-proposition-canvas / business-model-canvas / org-design-framework / dependency-graph / raci-matrix / gantt-chart / strategy-map）达到可实用分析成熟度（结构化用户输入模板 + 框架逻辑引导）,
**So that** Agent 调用这 7 个 Skills 时基于用户输入的内部业务信息（经 `ToolCall.arguments` 进入 Think prompt）输出结构化分析结果。

### 业务价值

Story 4.1a 交付 Skills 骨架（23 个 SKILL.md + 五阶段引擎 + frontmatter 解析），4.1b/4.1c/4.1d 依次交付数据采集基础设施与 16 个 Skill 成熟化（6 外部数据型 + 10 混合数据型，均声明 `data_sources`）。本 Story 是 **Story 线 4.1 的收官**：成熟化最后 7 个「纯内部输入型」Skills——与 4-1c/4-1d 的关键差异：**不声明任何外部数据源（`data_sources` 保持空 tuple）**，分析主体是用户输入的内部业务信息（画布块/组织结构/任务依赖/角色分工/项目计划/战略因果），通过「Schema 模板 + 框架逻辑引导」采集（结构化方法论而非外部数据）。

本 Story 是**纯内容成熟化 Story**：7 个 SKILL.md frontmatter `input_schema`/`output_schema` 声明 + SOP 成熟化 + 模板与框架逻辑资源 + 测试交付，**零引擎/接线/端口/异常层改动**（生产链路已由 4-1a/4-1c 接线完毕；引擎对空 `data_sources` + 无标记代码走直通路径——`tool_execution_engine.py:329-331` 无标记快速返回，声明即生效）；生产 .py 的**唯一**改动 = `strategic_tool_catalog.py` 的 org-design 四维 schema 增强（Task 4.2 / D10，只加不改删的 domain 实体增强——非引擎链路）。

**来源:** [`epics_v1.0.md`](../../planning-artifacts/epics_v1.0.md) - Epic 4: 战略工具箱，Story 4.1e（P0-8，line 1050-1089）
**前置依赖:** Story 4.1a（✅ done，Skills 骨架 + 五阶段引擎）/ 4.1b（✅ done，数据采集基础设施）/ 4.1c（✅ done，6 外部型 + 双入口接线 + 契约库）/ 4.1d（✅ done，10 混合型 + 模板微格式契约 + 编码规范，五轮代码审查收敛）
**后续依赖:** 无被阻塞方（4-2/4-3/4-4 均 done；4-5/4-6/4-7 与 Skills 内容成熟化无耦合）——本 Story 完成即 **23/23 Skills 全部成熟化**（16 声明外部源 + 7 纯内部空声明）

### ⚠️ Story 范围澄清（重要）

**本 Story 交付（范围边界）：**

- 7 个 SKILL.md frontmatter `input_schema`/`output_schema` JSON Schema 声明（**不填 `data_sources` 键——纯内部型保持空 tuple 是一等不变量，非「未成熟化」状态**）
- 7 个 SKILL.md body SOP 成熟化（≤500 行硬约束，9 章节对齐 `REQUIRED_SOP_SECTIONS`）
- 每个 Skill 配套 `templates/` 用户输入模板（目录新建——当前 7 个目标 Skill 的 templates/ 均不存在；既有 references/ 目录 6 个为空，business-model-canvas 有存量资产）与 `references/` 分型三件套（评分型 {framework_logic / scoring_anchors / workshop_guide} ×3，结构型 {framework_logic / validation_rules / workshop_guide} ×4——决策 D4）
- 用户输入模板与 `input_schema` 字段一一对应（双向断言，复用 4-1d 模板微格式机械）+ 条目编码规范与确定性解析锚点（7/7 Skill——决策 D10）
- 共享契约库 `skill_framework_contracts.py`（第三契约库，import 4-1c/4-1d 共享常量与机械，**承接 4-1d R1-D2 defer 的 NON_TARGET_SLUGS 三副本收敛义务**——决策 D2）+ 契约库自检（含失败路径负例，R1-F1 先例）+ 7 个 Skill 单元测试
- IO 契约 SSOT 扩充：`tests/acceptance/contracts/skill_io_schemas.yaml` 追加 7 个条目（16 → 23，单一 SSOT 文件，不新建；**output_schema 不含 `data_sources` 溯源键**——决策 D6）
- 既有回归网调整（**一次性前置**，4-1d D8 先例）：yaml 互锁断言扩三方并集（唯一机制性必红点 `test_slug_set_matches_yaml_contracts`）+ NON_TARGET_SLUGS 三副本派生收敛 + 两套验收「未成熟化 Skill 空白名单」场景改名永久锚定（滚动锚点规则终点态——决策 D8）
- 集成测试（无标记全链路 + 零外部 resolver 触达 + evidence 空溯源 + 207 误用守护（fake resolver 注入场景）+ 缺数据引导面）+ 模板对齐汇总层测试（全 Skill 就绪后落地）+ 架构验证（**23 Skills 最终态闭环** + Schema 合法性强化断言衔接 4-3 基建）+ BDD 验收测试
- bsc-scorecard SKILL.md §2 单行回跳增补（「定性战略因果链：请用 strategy-map」——Subtask 5.7，跨 Story 单行内容增量，R9 登记）
- 文档同步：architecture.md（§17.3 状态翻转 + §17.3.3 集成说明 + 决策表 + 修订历史）

**不在本 Story 范围（明确划出）：**

- **引擎/接线/端口/异常层的 Python 生产代码改动** → 零改动（frontmatter 解析 / 双入口接线 / 引擎五阶段 / 白名单校验均为既有交付物；空 `data_sources` + 无标记代码的直通路径 `tool_execution_engine.py:329-331` 是既有语义）；**唯二例外**：① Task 4.2 catalog org-design 四维增强（D10 登记的生产 .py 增强，只加不改删）② Subtask 3.3 validate_canvas.py 特征串更新（Skill scripts/ 内容资产，非生产链路）；若实施中发现必须改其他代码，先停下核对本文档「端口与数据契约」节
- **任何外部数据源声明** → 7 个 Skill `data_sources` 保持空 tuple（三分法自洽：4-1c 外部源型 6 + 4-1d 混合型 10 + 4-1e 纯内部型 7；声明源将破坏 4 处既有守护并违反分类学）
- **Schema 运行时强校验接线**（Engine 链路消费 frontmatter schema）→ Story 4.3 已交付 `SchemaValidatorPort`（`src/application/ports/schema_validator.py:108-114`，composition_root:2541-2558 已注册，impl=`JsonSchemaValidatorImpl`；生产链路经 `ToolOutputValidator` 消费 output 侧）；`ToolInputValidator` 类存在（`src/application/services/tool_input_validator.py:47`）但**未在 composition_root 注册**（未接线）。本 Story 仅做 Schema 合法性强化断言（测试级直用 `JsonSchemaValidatorImpl.validate_arguments(tool, arguments)`，D11），不改生产链路、不新增接线
- **yaml 既有 16 条目的 data_sources.items 字段级化 + description 命名对齐** → Story 4.3（4-1c R2-F7 既定留项；本 Story 新增条目沿用现行粒度）
- **输入侧自由 object 字段化**（本 Story 涉及 raci `assignments` / gantt `durations`+`resources` / bmc `cost_structure`）→ **4.3 defer 沿用**（4-1d A12 先例：description 编码声明过渡，不结构化）
- **SPACE 分档含义表斜线双语义**（4-1d Round 3 defer 标注「4.1e 顺手」）→ **显式不修**（space-matrix 是 4-1d Skill，跨 Story 边界改动须专 Story 承载；继续 defer 至 space-matrix 下次触碰）
- **StrategicAnalysisUseCase 的 composition_root 注册 + 接口层入口** → 入口 Story（4-1c R1-P2-13 既定 Defer）

### ⚠️ 命名规范声明（强制，覆盖 Epic 字面表述）

**用户约束（4-1c 实施期确立）：禁止使用故事编号命名编码开发。** 全部新增测试/源码文件采用功能性命名（无 `_4_1e` 后缀），即使 epics_v1.0.md line 1074-1081 写了带编号的文件名（`test_skill_framework_4_1e.py` / `test_arch_skill_framework_4_1e.py` 等）。docstring 中引用 "Story 4.1e" 字样不受此限。本 Story 文件所有文件名以「文件清单 File List」节为准。

**Epic 字面勘误（D12 签收）：** epics_v1.0.md AC-1 写 value-proposition-canvas「9 块匹配分析」——**Osterwalder 价值主张画布实为 6 块（客户轮廓 3 块 + 价值图 3 块）双侧匹配**，9 块是 Business Model Canvas；domain catalog（`strategic_tool_catalog.py:504-548`）也是 3+3 结构。本 Story 按 6 块双侧匹配实施，Epic 字面偏差留痕。

**slug 精确性核实（无陷阱）：** 7 个 slug（value-proposition-canvas / business-model-canvas / org-design-framework / dependency-graph / raci-matrix / gantt-chart / strategy-map）与 `skill_manifest.py:27-35` UUID 映射、`architecture.md:2678` 清单完全一致，**无 `-model` 类后缀陷阱**（仓库唯一该陷阱 change-management 已在 4-1d 处理）。

**分型术语同义声明：**「纯内部型 / 纯内部输入型 / 内部用户输入型 / 内部框架型 / 无外部源型 / 纯内部框架 Skill」在本 Story 语义等同（均指 7 个不声明 `data_sources` 的 Skills）；D8 场景改名钉死用「纯内部框架 Skill」，回归网措辞升级目标用「无外部源型 Skill data_sources 恒空不变量」。

**strategy-map ≠ bsc-scorecard（关键分工，D13）：** 二者是两个不同工具——strategy-map（tool_id …0017）input 根键 **`bsc_indicators`**，输出定性因果链图（`strategy_visualization`：nodes/causal_arrows/theme_cards）；bsc-scorecard（…0016）input 根键 `strategic_objectives`，输出定量 KPI 计分卡（`bsc_metrics`：KPI/目标值/权重）。4-1e 的 strategy-map 契约必须锚 `bsc_indicators`，**禁止沿用 bsc-scorecard 的键名**。两 Skill 需建互查映射表（4-1d bsc↔kpi-tree 先例）。

---

## 🛡️ 硬约束声明（CLAUDE.md §5）

### 领域零依赖（FR-AR-01）

- 本 Story **零引擎/端口/异常/接线层改动**（交付物 = YAML/Markdown 资源 + 测试 + 唯一生产 .py 增强：`strategic_tool_catalog.py` org-design 四维（D10 只加不改删））；若实施中发现必须触碰其他 `src/` 下 Python 文件，该文件按其所属层遵守依赖规则——domain 层禁止外部依赖与跨层 import（`.importlinter` 契约 `domain-no-external-dependencies`：20 个外部包黑名单 + 三层禁入，CI 失败）
- **domain catalog 兼容强制**：以 `strategic_tool_catalog.py` 既有 Tool.input_schema/output_schema 为基础按内部框架场景**增强**（可加字段/description/嵌套 required，**禁止删除既有 required 与 properties 键**——4-1d R5 先例）；org-design-framework 的 Galbraith 5 维扩展（D10）是本 Story 唯一预期的 catalog 增强

### 异常体系强制

- **禁止** `raise ValueError` / 手动 `raise HTTPException` / 继承内置 Exception
- 所有异常走 `src/domain/exceptions/` 体系 + `ExceptionHandlers` 自动映射
- 提交前三条 grep 自查（零输出）：
  - `grep -rn "raise ValueError" src/`
  - `grep -rn "raise HTTPException" src/`
  - `grep -rn "class.*Exception)" src/domain/exceptions/ | grep -v "DomainError\|BaseException\|SystemException\|BusinessException\|ExternalException\|ThirdPartyError\|Error)"`

### 抑制告警禁止

- **禁止** `# noqa` / `# type: ignore` / `# pylint: disable`；**禁止**修改阈值/规则消除告警——必须修复根因
- 测试文件同样适用：fixture 与测试参数必须带类型注解（4-1c R1-P0-1 教训）

### Commit & Push 规范

- 提交信息**禁止**任何 AI 辅助署名（Co-Authored-By: Claude 等）
- **禁止** `--no-verify` 绕过 pre-commit hooks
- **禁止** 修改 `.importlinter` 中已合入的架构依赖规则
- 直接在 main 分支开发（项目约定）

### Skills 内容约束

- **L2 SKILL.md ≤500 行**（`SKILL_MD_MAX_LINES=500`，4-1c 契约库单一来源；行数约束由单测断言 + 架构测试承担）；SOP 成熟化膨胀时按 Hub-and-Spoke 拆分到 `references/*.md`
- **frontmatter 必需字段**：`slug`（kebab-case）/ `name` / `version`（SemVer）——`frontmatter.py:32` `REQUIRED_FIELDS` 强制；**version 全部保持 1.0.0**（4-1d A10 先例，成熟化不升版）
- **data_sources 键不写入 frontmatter**：键缺失 → 解析为空 tuple（`frontmatter.py:166-167`/`:252`），这是纯内部型的正确表达（写 `data_sources: []` 也可解析但与 16 个声明型写法混淆，**统一不写键**）
- **负向触发章节强制**：`when_not_to_use` + body「负向触发」章节；本 Story 两对工具需互相负向跳转（D13）：dependency-graph ↔ gantt-chart（纯拓扑 vs 含时间排程）、strategy-map ↔ bsc-scorecard（定性因果链 vs 定量计分卡）
- **SOP 引导沙箱代码零 `$DATA_SOURCE` 标记**（纯内部型 SOP 的 Code 阶段引导不含任何标记示例——标记集恒空由 [C] 断言守护，误写标记执行时将因空白名单抛 207）
- **SOP `input_examples` 章节禁止写入真实 API Key**（本 Story 无 Key 语义，出现即违规）
- **条目编码规范的 YAML 安全红线**（4-1d R2 实测教训）：schema description 为 yaml plain scalar——**禁止半角冒号+空格「: 」与花括号形态**（`{当前: 1-5}` 触发 mapping 解析错误）；编码声明用全角「：」与「=」；落码后 yaml round-trip 复验
- **评审/轮次标记零泄漏**（4-1d R3-F3 教训）：schema description 是运行时契约内容，禁止携带任何审查过程标记（如「R1-F1」类）；勘正出处只留本 Story 文档

### 代码质量门禁

- `poetry run ruff check src/ tests/` 通过（行宽 128，规则 E/F/I/N/W）
- `poetry run mypy src/` 通过
- `poetry run pytest tests/ -n 8` 并行通过，连续 5 次无随机失败
- `pre-commit run --all-files` 通过

---

## 🎯 领域异常契约

> **原则**：异常是领域契约的一部分。本 Story **不新增领域异常**（显式决策，D 系列同 4-1d D4）。

### 不新增异常的决策声明

本 Story 为纯内容成熟化 Story（零引擎链路代码改动），全部失败路径已由 4-1a/4-1b/4-1c 异常体系覆盖，**新增同义异常违反「禁止同义异常重复定义」红线**：

| 场景 | 复用异常 | 编码 | 依据 |
|------|---------|------|------|
| SOP 误写 `$DATA_SOURCE` 标记（空白名单下任何源名） | `BusinessRuleViolationError` | EXCEPTION_207 | 4-1b 既定（`data_source_resolver.py:240-259` `_check_whitelist`；纯内部型 Skill 的标记误用守护态） |
| 标记存在 + resolver 未注入（理论路径） | `ConfigurationError` | EXCEPTION_101 | 4-1b 既定（`tool_execution_engine.py:333-337`） |
| 内部数据不足（模板字段缺失/空洞） | —（状态非异常） | `ToolResultStatus.INSUFFICIENT_DATA` | 4-1a 既定（`src/domain/value_objects/tool_execution.py:29-41`——注意在 value_objects 而非 entities（entities 同名文件的 :33-41 是 `ToolExecutionState` 六状态机枚举）；**该枚举为值对象定义性枚举，生产链路零设置点**（engine 唯一 `ToolResultStatus` 设置点 `tool_execution_engine.py:209` 硬编码 SUCCESS）——本 Story 仅以 SOP 失败处理章节**文档级关键词**承载语义引导（4-1d `test_bsc_scorecard_mixed_data.py:81-84` 同款先例），不作运行时状态断言） |
| SKILL.md frontmatter 解析失败（YAML 语法 / 必需字段非法） | `FrontmatterParseError` | 既有 | `frontmatter.py:45`（解析器仅 fail-fast YAML 语法与 slug/name/version 必需字段——**不校验 input_schema/output_schema 结构**（缺键时 normalize 静默回退 `{}`）；schema 结构合法性由 AC-5 D11 测试级 `jsonschema.check_schema` 断言承载，本 Story 填 schema 后两者各司其职） |

> 与 4-1d 的差异：411/412/413（数据源失败三态）**不适用**——纯内部型无外部采集语义；失败处理断言集替换为 `("207", "INSUFFICIENT_DATA")`（决策 D3，词边界正则保留——4-1c R1-P2-4 教训）。

### 4-1d 留项收敛状态确认（Task 0 必做）

- [ ] R1-D2（NON_TARGET_SLUGS 三副本收敛 → 4-1e）：**本 Story Task 1.4 承接**（派生式收敛 + 语义改名，D2 决策）
- [ ] yaml data_sources.items 字段级化 → Story 4.3（不收敛，沿用粒度）
- [ ] 输入侧自由 object 字段化 → Story 4.3（不收敛，description 编码过渡）
- [ ] SPACE 斜线双语义 → 显式不修（跨 Story 边界，继续 defer）

---

## 🎯 测试隔离约束

### TestTenant UUID 前缀

- 集成/验收测试资源隔离：本 Story 无外部缓存/采集路径（无标记直通），**无 Redis 依赖**、无 `xdist_group("data-source-cache")` 分组（该分组仅共享缓存键测试需要）；ExecutionContext.tenant_id 仍用场景级 UUID（语义保持）

### BDD 步骤函数

- 步骤函数用 `event_loop.run_until_complete()` 运行 async 测试；**禁止** `@pytest.mark.asyncio`（context data 丢失）
- @scenario 显式绑定 + 场景级共享领域对象（`_SkillExecution` 模式，4-1d 范本）
- LLM 按内容特征分派（「生成代码」识别 Code 阶段——非序数，4-1c R2-F1 教训）；Fake 仅限 LLM/Sandbox

### 并发与事件循环

- `asyncio.Lock` 类变量；无跨循环客户端（本 Story 无 Redis 客户端）

---

## 🌐 端口与数据契约

### 端口契约（本 Story 不新增端口 — 显式决策）

- 零端口新增/修改：生产链路（引擎五阶段/白名单校验/双入口接线）为 4-1a/4-1b/4-1c 交付物；`SchemaValidatorPort`（4-3）已有注册，本 Story 仅在**测试级**衔接（D11），不动端口
- **R1-R4 设计规则符合性声明**：本 Story 零端口/零实现层改动（R1 领域端口抽象既有 / R2 无组合注入需求 / R3 无基础设施实现 / R4 无接口层适配）——纯内容 Story 的端口面为空集

### 数据契约（本 Story 核心 SSOT）：7 个内部框架 Skills IO Schema 声明表

> 以 `strategic_tool_catalog.py`（:504-855）既有 Tool 条目为基础增强（**禁止删除既有 required/properties 键**）；分型列决定 references 三件套与模板第三段语义（D4/D5）。

| slug | tool_id 尾号 | input 根键（required） | 结构形态 | 分型 | 编码规范（条目前缀/语法，D10） | 输出根键 |
|---|---|---|---|---|---|---|
| value-proposition-canvas | …0013 | `customer_profile`, `value_map`（两项） | 双容器各 3 叶子（源码序 pains/gains/jobs ↔ products/pain_relievers/gain_creators，:516-527） | 评分型 | 匹配强度分值（1-5）—— 条目描述 | `fit_assessment` |
| business-model-canvas | …0014 | `business_model` | 容器 9 叶子（cost_structure 为自由 object，D6 过渡） | 评分型 | 块成熟度分值（1-5）—— 条目描述 | `canvas_assessment` |
| org-design-framework | …0018 | `org_structure`（**D10 扩展：+ strategy/processes/rewards/people 四维容器**——org_structure 为历史根键，扩展后实际承载 Galbraith Star Model 全五维（structure 维由根容器自身承载），input_schema description 需注明此名实关系） | 容器多叶子（既有 functions/reporting_lines/decentralization_level 保留） | 评分型 | 维度对齐度分值（1-5）—— 条目描述 | `design_recommendation` |
| strategy-map | …0017 | `bsc_indicators`（**锚定此键，禁用 bsc-scorecard 键名**） | 容器 5 叶子（financial/customer/internal_process/learning_growth/causal_relationships） | 结构型 | 因果箭头语法「原因维度 → 结果维度：假设描述」 | `strategy_visualization` |
| dependency-graph | …0019 | `task_list`（**顶层 array-of-objects**） | items{name, dependencies} 两叶子 | 结构型 | 依赖边语法「任务名 ← 前置任务列表」 | `dependency_network` |
| raci-matrix | …0020 | `roles_tasks` | 容器 3 叶子（roles/tasks/assignments——assignments 自由 object） | 结构型 | 角色字母组合（R/A/C/I 单字母或斜线组合如 A/R；恰 1 A 硬规则 + ≥1 R 软规则（A/R 计为已承担 R），违规经 `raci_matrix.conflicts` 结构化呈现非整体失败） | `raci_matrix` |
| gantt-chart | …0021 | `project_plan` | 容器 4 叶子（tasks/dependencies/durations/resources——后两自由 object） | 结构型 | 时长格式「N 天/周/月」——正则 `^\d+ *(天|周|月)$`（禁「个月」与英文单位），归一基准=天（周=5 工作日 / 月=20 工作日） | `gantt_visualization` |

### 内部数据契约（本 Story 特有）

**用户输入模板契约（AC-3 核心，复用 4-1d 微格式机械）：**

- 模板四段式（第三段按分型条件化，D5）：基本信息 / 采集表格 / **评分锚点（评分型）或 校验规则（结构型）** / 数据缺口登记
- 模板采集字段集合 == input_schema 递归展开叶子键集合（双向：`schema_leaf_keys` + `extract_template_fields`，4-1d 库 import 复用——含两结构守卫与分区标题断言）
- required 字段以「（必填）」后缀标注；分区标题字面值 == 顶层容器键
- dependency-graph 的顶层 array-of-objects 形态：`task_list` 容器键以分区标题承载，叶子键 name/dependencies 进比对集（4-1d vrio 二层嵌套先例覆盖）

**条目编码规范契约（7/7 Skill，D10）：**

- 每个字符串/自由 object 字段的 schema description 声明编码格式（「匹配强度分值 = 紧邻首个『——』（两个 U+2014）前的独立 1-5 整数（前缀不得含其它数字，防『P1 —— 4』误判）」类确定性解析锚点——4-1d R2-F7/R3-F8 先例）
- **四方同步**：yaml 条目 + SKILL.md frontmatter description（逐字双写，dict 相等断言锁定）+ §3 表 + §8 示例
- 编码格式与模板现行微格式**逐字一致**（4-1d R3 教训：声明钉模板现行格式）
- **示例三方一致**：模板示例行 ↔ §8 JSON 条目 ↔ framework_logic/scoring_anchors 的分值/枚举（同文本同值——4-1d R3-F5 仲裁先例）

**business-model-canvas 存量资产整合契约（D7，pestel 先例）：**

- 存量 `scripts/validate_canvas.py`（REQUIRED_BLOCKS 9 元组 + 5 条 CRITICAL_LINKS）与 `references/canvas_template.json` **保留并被新 SOP 引用**（4-1a 资产吸收，非删除）
- **命名冲突裁定**：catalog 用 `key_partnerships`（:568）vs 存量资产用 `key_partners`——**以 catalog 为准收敛为 `key_partnerships`**（domain 层零改动），更新 `canvas_template.json` 块名 + `validate_canvas.py` 的 `REQUIRED_BLOCKS`，同步更新 `test_skills_loader.py:219-225`（`TestL3ReferencesLoading`，断言 canvas_template.json 字节内容）的 `key_partners` 特征串断言——**原断言 `b"key_partners" in content` 是子串命中，改键名后会因 `key_partnerships` 前缀包含而静默通过（失去判别力），必须同步收紧为带引号完整键 `b'"key_partnerships"'`**（三文件一处裁定，R1 风险登记）

### 生产链路（零改动声明）

- 五阶段引擎对空 data_sources + 无标记代码的执行语义（4-1e 行为基线，实测确认）：`_resolve_data_sources`（`tool_execution_engine.py:329-331`）无标记快速返回 → 纯 Think→Code→Execute→Observe→Validate 直通，`EvidencePackage.data_sources == ()`
- **用户内部输入的唯一数据通道**：`ToolCall.arguments` → Think prompt（`_build_think_prompt` f-string 注入 arguments，:521-522）——4-1d D5 决策「内部数据经 arguments 进入 Think prompt 是既有语义」在 4-1e 升格为**主通道**（无 DATA_SOURCES preamble 并存）
- 标记误用守护态：SOP 误写 `$DATA_SOURCE` 标记 + 空白名单 → `_check_whitelist` 抛 207（`data_source_resolver.py:240-259`）——BDD Edge 已有场景承载
- **wiring 特征串回归断言**（4-1d A7 复用）：`strategic_analysis.py`/`run_tool_chain.py`/`tool_execution_engine.py` 三文件均含 `tool_metadata` 特征串；`load_sop` 特征串**仅前两个 use case 文件含**（engine 无该字面串——豁免条件对齐 4-1d 既有断言 `test_arch_skill_mixed_data.py:171-176` 的 `if path.name != "tool_execution_engine.py"` 分支，整类复用即继承豁免）+ 零 infrastructure import + `ToolExecutionEngine.__init__` 签名锁定

### 领域事件（本 Story 不新增事件）

- 零事件新增：无采集语义 → 无 DataSourceFetched/Failed 触发面；`config/event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` 零改动

### 契约测试文件清单

| 文件 | 层 | 性质 |
|---|---|---|
| `tests/unit/application/skills/skill_framework_contracts.py` | 单元（非测试收集） | 第三契约库（常量 + 断言函数，import 4-1c/4-1d） |
| `tests/unit/application/skills/test_skill_framework_contracts.py` | 单元 | 契约库自检（含失败路径负例——R1-F1 先例强制） |
| `tests/unit/application/skills/test_<slug>_framework.py` × 7 | 单元 | 每 Skill 四循环 [A][B][C][D] |
| `tests/unit/application/skills/test_schema_template_framework_alignment.py` | 单元 | 模板对齐汇总层（分型四段式） |
| `tests/integration/application/test_skill_framework.py` | 集成 | 无标记全链路 + 207（resolver 注入场景）+ 缺数据引导面 |
| `tests/unit/architecture/test_arch_skill_framework.py` | 架构 | 三方一致 + 23 终态闭环 + Schema 合法性强化 |
| `tests/acceptance/test_acceptance_skill_framework.feature` / `.py` | 验收 | BDD（zh-CN） |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 7 个 Skills IO Schema 声明与空声明守护

**Given** Story 4.1a Skills 骨架已就绪（7 个占位 SKILL.md 无 schema 键）
**When** 在 7 个 SKILL.md frontmatter 填充 `input_schema`/`output_schema`（**不填 data_sources 键**）
**Then**
- 每个Skill 的 schema 与 yaml SSOT 条目**逐字一致**（dict 相等断言，`assert_io_schema_contract` 复用）
- `load_sop(slug).frontmatter.input_schema` 解析成功且 catalog 兼容（既有 required/properties 零删除——org-design 四维扩展为唯一预期增强）
- **「纯内部型零外部源」一等不变量**：`load_sop(slug).frontmatter.data_sources == ()`（7/7 断言——从 4-1d「非目标守护」升格为本 Story 正式 AC）
- 既有 23 Skills 解析回归全绿（`test_skills_loader.py` + `test_frontmatter_data_sources.py` 零回归——7 个空声明物理空者不触发「凡声明必合法」与「并集」断言，天然绿）
- 4-1c/4-1d 既有 16 Skill 契约断言零回归
- **yaml SSOT 扩至 23 条目**且互锁断言扩三方并集（唯一机制性必红点前置调整）

**验证标准/Validation Criteria:**
- [ ] 7 个 Skills 单元测试断言 schema 双写一致 + data_sources == () + catalog 兼容
- [ ] 跨循环一致性 [C]：SOP body `$DATA_SOURCE` 标记集合 == 声明集合 == **∅**（双向断言防误写标记——`assert_cross_consistency` 复用，空集语义下有真实守护价值）
- [ ] 23 条目 yaml 加载 + slug 集合 == 三契约库并集（16+7）
- [ ] version 全部保持 1.0.0

### AC-2: SOP 成熟化（7 个 Skills 内容升级，9 章节对齐 4-1c 契约）

**Given** 7 个 SKILL.md 当前为 55 行占位模板（body 含 `{"placeholder": ...}`）
**When** 编写 7 个 Skills 的完整 SOP 与配套资源
**Then**
- 每个 SKILL.md 含 9 章节（对齐 `REQUIRED_SOP_SECTIONS` import 4-1c 库——**章节集零新增**，「数据采集计划」章节语义承载「用户输入采集计划」：模板路径 + 采集指引 + arguments 构造，无外部源映射表/无内外交叉验证段）
- 每个 Skill 配套分型三件套（评分型 {framework_logic / scoring_anchors / workshop_guide}，结构型 {framework_logic / validation_rules / workshop_guide}）与 templates/ 模板（1 个）
- 每个 SKILL.md ≤500 行；frontmatter 必需字段完备；input_examples 非 placeholder（含编码格式的真实量级示例——四方同步之一）
- **失败处理断言集**（D3）：每 Skill 失败处理章节含 `207`（标记误用守护）与 `INSUFFICIENT_DATA`（内部数据不足引导）词边界关键词（**411/412/413 不适用纯内部型**——断言集在 4-1e 契约库定义，判别力负例强制）
- 条目编码规范（D10）四方同步 + 确定性解析锚点半句
- 两对工具互相负向跳转在位（D13）：dependency-graph ↔ gantt-chart、strategy-map ↔ bsc-scorecard；strategy-map 与 bsc-scorecard 建互查映射表（分工：定性因果链 vs 定量计分卡）
- business-model-canvas 存量资产保留并被 SOP 引用（validate_canvas.py + canvas_template.json，D7 收敛为 key_partnerships）

**验证标准/Validation Criteria:**
- [ ] 7 个 Skills 单元测试断言 SOP 必备章节 + input_examples 非 placeholder + 行数 ≤500 + 失败处理双关键词（207/INSUFFICIENT_DATA 词边界）
- [ ] frontmatter schema 与 yaml 逐字相等
- [ ] 分型三件套 + templates 存在性与非空断言（分型参数化）
- [ ] framework_logic 契约：含框架逻辑引导（系统化思考步骤 + 填写指引——Epic AC 2 字面承接）
- [ ] 评分型 scoring_anchors 契约：刻度声明 + 分档含义 + 锚点示例（4-1d 先例）；结构型 validation_rules 契约：确定性规则 = **分析层评估逻辑**（违规经输出根键下 `conflicts` 类字段结构化呈现，不映射为运行时异常/INSUFFICIENT_DATA）——RACI 恰 1 A 硬规则 + ≥1 R 软规则（A/R 计为已承担 R）/ DAG 无环与依赖方向（关键路径 = 跳数最长链的无时长结构代理）/ 时长归一 CPM（ES/EF/LS/LF 零浮动）/ 因果箭头语法（标准方向自下而上：learning_growth → internal_process → customer → financial；逆向/同层箭头标记 warning 级待澄清假设不硬失败）

### AC-3: 用户输入模板与 input_schema 字段一一对应（双向断言）

**Given** Epic AC 2 要求 7 个 Skills 各自配套用户输入模板
**When** 编写 7 个模板并运行模板对齐测试
**Then**
- 模板采集字段集合 == input_schema 递归叶子键集合（双向：多余=失败，缺失=失败——`schema_leaf_keys`/`extract_template_fields`/`assert_template_schema_alignment` 复用 4-1d 机械）
- 分区标题字面值 == 顶层容器键（dependency-graph 顶层 array-of-objects：task_list 分区标题承载）
- 模板四段式第三段按分型条件化（评分锚点 / 校验规则——引用对应 references 文件字面串）
- required「（必填）」后缀与 required 链严格一致
- **变异演示**（4-1d AC-3 先例）：临时删除任一模板字段 → [D] 断言红后还原；临时改 required 标注语法 → 提取器断言红后还原

**验证标准/Validation Criteria:**
- [ ] `test_schema_template_framework_alignment.py`（7 Skill 参数化，分型四段式）双向断言通过
- [ ] 契约库自检含提取器边界负例与守卫负例（R1-F1 先例）
- [ ] 模板结构与第三段引用断言通过（分型字面串）
- [ ] 变异演示留痕（Dev Agent Record 记录）

### AC-4: 集成测试（真实 Engine + 内部数据主通道 + 零外部源不变量）

**Given** 7 个 Skills 声明就绪 + 生产链路既有（无标记直通路径）
**When** 运行 `tests/integration/application/test_skill_framework.py`
**Then**
- 7 个 Skills 经「真实 Engine + 真实 InMemorySkillLoader（真实 SKILL.md frontmatter）+ AsyncMock LLM/Sandbox」链路验证：LLM 生成**零 `$DATA_SOURCE` 标记**的分析代码 → Think prompt 含 arguments（repr 子串断言，特征串「规划执行步骤」）→ Execute 直通 → SUCCESS
- **零外部源不变量行为面**：`evidence_package.data_sources == ()` + 注入沙箱的代码**不含 DATA_SOURCES 前言**（无 preamble 注入——与 4-1d 双通道并存语义的对照差异）
- 207 误用守护：任一 Skill 的标记代码（SOP 误写场景模拟）→ `EXCEPTION_207`（空白名单校验，error_code 逐字断言——4-1c R1-P1-1 判别力先例；**场景前提：需注入 resolver**（`DataSourceResolverService` 构造同款 4-1c 验收 :225-233）+ 101 对照负例——不注入 resolver 得 `EXCEPTION_101` 非 207，详见 Task 9 [B]）
- 缺数据引导面：空 arguments → Think prompt 含空 dict repr 断言 + 模板缺口登记区语义联动（**INSUFFICIENT_DATA 为 SOP 文档级关键词断言（AC-2 承载）非运行时状态断言**——该枚举生产代码零设置点，engine 唯一 `ToolResultStatus` 设置点 `:209` 硬编码 SUCCESS，4-1d 先例即文档级）
- **无 Redis 依赖**（无标记主链路零 resolver 调用；207 场景的 resolver 为 fake cache 构造、不触达真实缓存；`pytestmark` 仅 `pytest.mark.integration`，无 xdist_group）
- `build_min_arguments(slug)` 复用（yaml required 链程序化构造——import 4-1d 库，防手写漂移）

**验证标准/Validation Criteria:**
- [ ] 集成测试全绿（无标记全链路 7 Skill 参数化 + 207/缺数据引导面场景——Subtask 9.1-9.3）
- [ ] 207 语义断言（error_code == "EXCEPTION_207" 逐字 + 101 对照负例）
- [ ] repr 断言（arguments 进 Think prompt——f-string 注入 dict 单引号形态，非 json.dumps）
- [ ] `pytest -n 8` 并行通过，连续 5 次无随机失败

### AC-5: SDD 架构验证测试（含 23 Skills 最终态闭环）

**Given** 7 个 Skills 声明必须满足六边形架构约束与三方一致性
**When** 运行 `tests/unit/architecture/test_arch_skill_framework.py`
**Then**
- 契约库 SSOT（FRAMEWORK_SKILL_SLUGS）↔ 7 个 SKILL.md frontmatter ↔ `strategic_tool_catalog.py` 三方一致（schema 兼容方向——catalog required ⊆ frontmatter required）
- **23 Skills 最终态闭环**：`SLUG_TO_TOOL_ID` 全集 == 三契约库并集（6+10+7）——16 声明外部源 + 7 空声明的分类学终态断言（本 Story 收官语义）
- wiring 文件特征串回归断言（三文件 `tool_metadata` + 两 use case 文件 `load_sop`（engine 豁免）+ 零 infrastructure import）+ `ToolExecutionEngine.__init__` 签名锁定（4-1d A7 整类复用，豁免条件随类继承）
- 7 个 SKILL.md ≤500 行 + frontmatter 必需字段 + data_sources 空 tuple 终态
- **回归网收敛落地验证**（D2）：NON_TARGET_SLUGS 三副本已改派生式 import 契约库（`NO_EXTERNAL_SOURCE_SLUGS = tuple(sorted(set(SLUG_TO_TOOL_ID) - set(SKILL_DATA_SOURCES) - set(MIXED_SKILL_DATA_SOURCES)))`，派生结果 == 7 非空，判别力保留）
- **Schema 合法性强化**（D11，衔接 4-3 基建）：23 条目 input/output schema 全部通过 `jsonschema` Draft7 `check_schema` + `build_min_arguments(slug)` 实例通过 `JsonSchemaValidatorImpl.validate_arguments` 构造的 Tool 校验（4-3 基建测试级衔接，不改生产链路；**断言面 = frontmatter/yaml 条目侧**——catalog 侧 23 工具 46 schema 已由 4.1 注册验收 `test_acceptance_strategic_tool_registration.py:165-177` 覆盖（对 catalog Tool 实体 schema check_schema），两侧互补不重复）
- SSOT 单一来源：`FRAMEWORK_SKILL_SLUGS` 从 contracts 模块 import（架构/集成/验收三处禁止复制）

**验证标准/Validation Criteria:**
- [ ] 架构测试全绿（三方一致 + 终态闭环 + wiring 回归 + 签名锁定 + Schema 强化）
- [ ] 派生式收敛后三处原字面清单已删（grep 零残留）
- [ ] 23 条目 Schema 合法性断言通过（Draft7 + 最小实例校验；条目侧断言与 4.1 catalog 侧既有覆盖互补）

### AC-6: BDD 验收测试（Gherkin 中文）

**Given** Story 4.1a/4.1c/4.1d 基础设施与生产链路已就绪
**When** Agent 调用 7 个内部框架 Skills
**Then** Skills 通过 Schema 模板引导用户输入内部业务信息（arguments 主通道），LLM 基于框架逻辑生成结构化分析输出，输出无外部溯源（data_sources 空元组）
**And** Edge Cases 覆盖：纯内部 Skill 空白名单标记误用（207 安全失败——**原「未成熟化」场景改名永久锚定**，D8）、内部数据不足（缺口登记引导——INSUFFICIENT_DATA 语义以 SOP 失败处理章节文档级断言承载，4-1d 同款）、负向触发跳转（dependency-graph ↔ gantt-chart / strategy-map ↔ bsc-scorecard 分工）

> **覆盖范围说明**（对齐 4-1d R2-F5 教训）：BDD 承载 AC-1（空声明行为面）/ AC-4（链路行为面）/ AC-6 行为验证；AC-2（SOP 内容）/ AC-3（模板对应）/ AC-5（架构约束）由单元测试 + 架构测试承载。

**验证标准/Validation Criteria:**
- [ ] `tests/acceptance/test_acceptance_skill_framework.feature`（`# language: zh-CN`，按 AC 分节）
- [ ] `.py`（@scenario 显式绑定逐场景——4-1d 范本机械为每场景一个 test_* 函数、无 `scenarios()` 批量导入 + 共享 event_loop + 真实服务 + Fake 仅限 LLM/Sandbox）
- [ ] 全部场景通过
- [ ] 两套既有验收套件（4-1c/4-1d）全绿（双场景改名后语义仍绿——空白名单 207 行为不变）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- 本 Story 零事件新增（「领域事件」节声明）；Task 0 checklist 该项填「不适用——零事件」

#### 数据模型 (Data Models)

- [ ] yaml SSOT 7 条目设计：以 catalog（`strategic_tool_catalog.py:504-855`）为基础逐 Skill 增强嵌套 required + 叶子 description（含编码规范 + 确定性解析锚点半句——D10）；output_schema 不含 data_sources 键（D6 登记）；自由 object 字段（raci assignments / gantt durations+resources / bmc cost_structure）沿用 description 编码过渡（4.3 defer）
- [ ] org-design 四维扩展 schema 设计（D10：+ strategy/processes/rewards/people 容器，既有三字段保留——Galbraith Star 完整性，TOOLS.md L1 已写 5 维佐证）
- [ ] 模板文件命名表钉死（TEMPLATE_FILES 7 项，命名对齐 4-1d `skill_mixed_data_contracts.py:100-111` 风格——缩写前缀 + 采集物名）：`vpc_canvas_matching.md` / `bmc_nine_blocks_canvas.md` / `org_star_model_assessment.md` / `strategy_map_causal_links.md` / `dependency_task_inventory.md` / `raci_roles_tasks.md` / `gantt_project_plan.md`
- [ ] 分型常量表钉死（评分型 3 / 结构型 4 slug 清单 + 各自 references 三件套与模板第三段字面值）
- [ ] required_fields 逐源期望值不适用（无声明源——data_sources 键不写）

#### 统一端口定义注册与管理 (Port Contract)

- 本 Story 零端口新增/修改（「端口契约」节声明）；Task 0 checklist 该项填「不适用——零端口」+ 既有端口零触碰确认（SchemaValidatorPort 仅测试级衔接）

#### 领域异常契约 (Domain Exception Contract)

- 本 Story 零新增异常（「领域异常契约」节复用表：207/101/INSUFFICIENT_DATA/FrontmatterParseError）；Task 0 checklist 按 template.md 异常清单逐项填「不适用——零新增」+ 复用表确认

#### API 契约 (API Contract)

- 不适用——零 API 变更（纯内容 Story）

#### 六边形架构约束（必须遵守）

- 按 template.md 四层定义与依赖方向矩阵执行；本 Story src/ 改动仅限 7 个 Skill 内容目录的 .md/.json/.py（validate_canvas.py 特征串更新）+ `strategic_tool_catalog.py` org-design 四维增强（D10）——**其余生产 .py 一律禁止触碰**（唯二例外：D10 的 catalog 增强——只加不改删的 domain 实体 schema 增强（Task 4.2，R5 守护）；D7 的 validate_canvas.py——scripts/ 内容资产非生产代码）

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 编写 `tests/acceptance/test_acceptance_skill_framework.feature`（zh-CN，按 AC 分节，场景大纲或平铺——4-1d Round 3 用户反馈先例：平铺场景）
- [ ] 编写 BDD 步骤实现骨架（LLM 内容分派 + prompt 捕获 + execution 共享对象——4-1d 骨架模式）
- [ ] 运行确认失败（🔴 红阶段验证）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

---

### TDD 循环约束（适用于每个 Task）

> 每个 Task 依次执行：🔴 红（失败测试）→ 🟢 绿（最小实现）→ 🔄 重构（ruff + mypy + pytest 全绿）。禁止先码后测/跳过红阶段。

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| TDD 单元测试 | 契约库 | 常量 SSOT + 断言函数失败路径负例 + 提取器边界 | `test_skill_framework_contracts.py` | Task 1 |
| TDD 单元测试 | 7 Skills | [A] schema 双写/空声明/catalog 兼容 [B] SOP 成熟化 [C] 标记集==∅ [D] 模板对齐 | `test_<slug>_framework.py` ×7 | Task 2-8 |
| TDD 单元测试 | 模板对齐汇总层 | 分型四段式 + 双向断言参数化 | `test_schema_template_framework_alignment.py`（区别于 4-1d 既有 `test_schema_template_alignment.py`——多 `framework_` 一段） | Task 9（Subtask 9.4，全 Skill 就绪后落地） |
| TDD 验收测试 | Gherkin 场景 | 业务价值验收 | `test_acceptance_skill_framework.feature` | Task 0/11 |
| TDD 验收测试 | BDD 步骤实现 | 步骤函数 | `test_acceptance_skill_framework.py` | Task 0/11 |
| SDD 架构验证 | 六边形 + 终态闭环 | 三方一致/23 闭环/wiring 回归/Schema 强化/派生收敛 | `test_arch_skill_framework.py` | Task 10 |
| 集成测试 | 无标记全链路 | arguments 主通道/零 preamble/evidence 空/207（resolver 注入场景+101 负例）/缺数据引导面 | `test_skill_framework.py` | Task 9 |

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`make test-cov`）- P0 阻断门禁（生产代码仅 catalog 单点增强——既有覆盖率不降验证）
- [ ] **应用层 ≥85%**（`make test-cov-application`）——同上不降验证
- [ ] **关键路径 100%**：本 Story 无代码分支新增，以契约断言覆盖代偿（4-1d 先例）

#### 代码质量门禁

- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> 核心原则同 template.md（自包含/UUID 唯一性/BDD 禁 @pytest.mark.asyncio 等，全表适用）；本 Story 特有：无 Redis/无 xdist_group/无缓存清理面。

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` / `mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | IO Schema 声明 + 空声明守护 | Task 0 / 1 / 2-8 | 0.2 / 1.4（回归网预调整）/ 各 Skill .1-.2 | `test_<slug>_framework.py` ×7 / `test_arch_skill_framework.py` |
| AC-2 | SOP 成熟化 + 分型三件套 + 编码规范 | Task 1 / 2-8 | 1.1-1.2（契约库 assert_sop_maturity / FAILURE_KEYWORDS）/ 各 Skill Task .1-.8 | `test_<slug>_framework.py` ×7 |
| AC-3 | 模板 ↔ schema 叶子键双向 | Task 0 / 1 / 2-8 / 9 | 0.2 / 1.2 / 各 Skill [D] / 9.4 | `test_schema_template_framework_alignment.py` |
| AC-4 | 集成测试（无标记全链路 + 207 + 缺数据引导面） | Task 9 | 9.1-9.7 | `test_skill_framework.py` |
| AC-5 | 架构验证 + 23 终态闭环 + Schema 强化 | Task 1 / 10 | 1.4（互锁扩容）/ 10.1-10.6 | `test_arch_skill_framework.py` |
| AC-6 | BDD 验收 | Task 0 / 11 | 0.4-0.6 / 11.1-11.9 | `test_acceptance_skill_framework.feature` / `.py` |
| 全 AC | 回归网收敛（D2/D8 义务） | Task 1 | 1.4 | 三文件派生收敛 + 双场景改名 |

---

## ⚠️ 风险与缓解策略（Risk Register）

| # | 风险 | 概率 | 影响 | 缓解措施 | 触发 Task |
|---|------|------|------|---------|----------|
| **R1** | business-model-canvas 命名冲突收敛传播（key_partnerships 裁定涉及 catalog 零改动但 canvas_template.json + validate_canvas.py + test_skills_loader 断言三文件联动） | 中 | 中 | D7 一处裁定三文件同批落地；loader 测试特征串同步（`key_partners` → `key_partnerships`）；落码后 grep `key_partners\b` 验证（注意 key_partnerships 前缀误匹配——用词边界） | Task 3 |
| **R2** | 回归网调整时序死锁（yaml 扩容必红点 + 三副本收敛与 7 个 Skill 渐进填声明的并行期红窗口） | 高 | 高 | D8 先例：Task 1.4 一次性前置全部调整（**yaml 7 条目 + 互锁断言扩三方并集同批落即绿** + 派生式收敛 + 双场景改名）；7 个 Skill 空声明不触发「凡声明必合法」/「并集」断言（`test_frontmatter_data_sources.py:149` `if not refs: continue` 与 `:175` `if doc.frontmatter.data_sources:` 双守卫——物理空者跳过，4-1d 中间态安全化语义天然兼容） | Task 1 |
| **R3** | schema description YAML 解析红线（半角冒号+空格/花括号形态触发 mapping 错误） | 中 | 高 | D10 编码声明用全角「：」与「=」；每 Skill 落码后 yaml round-trip 复验 + 契约测试（4-1d value-curve 实测红教训） | Task 2-8 |
| **R4** | 多 Agent 并行编辑共享测试文件冲突（回归网三文件 + yaml SSOT 被多 Task 触碰） | 高 | 中 | D8 先例：共享文件全部调整前置 Task 1；Skill Task 只写各自独立文件（test_<slug>_framework.py + SKILL.md + references/templates）+ **yaml 单点写入**：7 条目全部由 Task 1.4 落地，Skill Task（2-8）零 yaml 触碰 | Task 1-8 |
| **R5** | org-design 四维扩展破坏 catalog 兼容（新增容器与既有字段冲突/required 膨胀） | 中 | 中 | D10 增强约束：只加不改不删；catalog 兼容断言（既有 required ⊆ 新 required）在 [A] 循环先行；TOOLS.md L1 五维表述佐证 | Task 4 |
| **R6** | 分型契约参数化复杂度（两套三件套/两段式语义 × 断言参数化易错） | 中 | 中 | D4/D5 分型常量表落契约库单一来源；断言函数按分型参数化 + 自检负例覆盖两分型各一 | Task 1 |
| **R7** | 编码规范与模板/示例三方漂移（4-1d R3-F5 同型） | 中 | 中 | 示例三方一致断言入 [D] 循环扩展（同文本同分值/枚举）；framework_logic/scoring_anchors 示例与模板对齐抽查入单测 | Task 2-8 |
| **R8** | Epic「9 块」字面误读导致 vpc schema 拍平或错构 | 低 | 中 | D12 勘误签收（6 块双侧匹配）；catalog 3+3 结构为基准 | Task 2 |
| **R9** | strategy-map 误用 bsc-scorecard 键名（strategic_objectives）；bsc-scorecard §2 回跳增补的跨 Story 单行改动 | 低 | 高 | D13 分工声明 + catalog 锚定 `bsc_indicators`（:675-687）+ [A] 断言根键；bsc §2 增补一行属内容级微调（4-1d 守护断言仅断言章节存在性，不锁行数——单行增量零破坏，D8 改名同类先例） | Task 5 |

---

## 📚 配套架构文档同步

| 同步项 | 位置 | 时机 |
|--------|------|------|
| §17.3 状态表翻转：「📋 Story 4.1e backlog」→「✅ 已完成（P0-8，日期）」+ 23/23 收官注记 | `docs/architecture/architecture.md:2677-2678` | Task 11 |
| §17.3.3 追加「Story 4.1e 集成说明」段（空声明直通语义 + 分型契约 + arguments 主通道）+ 关键架构决策表（引用本 Story 决策表 D1-D13） | `architecture.md` §17.3.3 末尾 | Task 11 |
| 修订历史 + 版本号（8.7.1 → 8.8.0，4-1d 8.6.0→8.7.0→8.7.1 惯例延续）+ 统计表 + **三处同源旧值一并校准**：§1.4 :187「0%（设计 100%）」+ §13 目录树 :1830「❌ 未实现」注记 + :1832「0% 实现率」——均更新为 23/23 终态 | `architecture.md` 头部/尾部 | Task 11 |
| `sisys-uni-exception-design.md` §3.3.2 零新增复用声明（blockquote 引用式，4-1c :725-729 / 4-1d :731-737 先例；207/101/INSUFFICIENT_DATA 引用式） | 异常设计文档 | Task 11 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ TDD 循环内化原则：每个 Task 独立完成红→绿→重构；每个 Subtask 组按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部（AC-1 ~ AC-6 的规范输入）

> 目的：进入实现前钉死 Schema SSOT / 分型契约 / 模板命名 / 决策表 / Gherkin 骨架。

- [ ] Subtask 0.1: 确认 4-1d 留项收敛状态（R1-D2 承接确认 + 其余不收敛留痕——「领域异常契约」节 checklist）
- [ ] Subtask 0.2: yaml SSOT 7 条目 Schema 设计——以 catalog（:504-855）为基础逐 Skill 增强（嵌套 required + 叶子 description 含编码规范与解析锚点）；org-design 四维扩展设计（D10）；分型常量表 + TEMPLATE_FILES 命名表钉死（7 项见 Task 0 数据模型 checklist——bmc 为 `bmc_nine_blocks_canvas.md`）；**本轮为设计稿不入库**（Task 1 随契约库 TDD 落地）——4-1d Task 0.2 同款
- [ ] Subtask 0.3: 决策表评审（D1-D13 逐项确认——见 Dev Notes「关键架构决策」节）
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_skill_framework.feature`（zh-CN 按 AC 分节；Happy 路径平铺 7 场景 + Edge：空白名单 207 / 内部数据不足引导（缺口登记 + INSUFFICIENT_DATA 文档级语义——断言面为 SOP 失败处理章节与 Think prompt 空 arguments repr，非运行时状态）/ 负向跳转 ×2——4-1d Round 3 平铺先例）
- [ ] Subtask 0.5: 编写 BDD 步骤实现骨架（`test_acceptance_skill_framework.py`：execution 共享对象 + LLM 内容分派 + prompt 捕获 + event_loop 模式——Fake 仅限 LLM/Sandbox）
- [ ] Subtask 0.6: 运行验收测试确认失败（🔴 红阶段验证——Skill 未成熟化时 given/then 断言红；预期红点形态：schema 断言红以 KeyError 呈现（yaml 7 条目尚未入库、`load_io_contract` 先 KeyError）与断言失败并存——**KeyError 亦为合法红**；另注：空白名单 207 与 data_sources==() 两场景在未成熟化时即为绿（生产行为与成熟度无关），红仅来自 schema/SOP 内容场景）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义（数据模型 checklist / 端口不适用 / 异常不适用 / Gherkin 红）
- [ ] yaml 设计稿与决策表入 Story Dev Notes 供 Task 1-8 引用

---

### Task 1: 共享契约断言库（回归基建 + 网预调整）

**关联 AC:** AC-1, AC-2, AC-3, AC-5

> 范本：4-1d Task 1 + D6/D8 决策；本库是第三契约库，import 4-1c/4-1d 防第三次复制（两库实名 `skill_data_collection_contracts.py`（174 行）/ `skill_mixed_data_contracts.py`（455 行），后者 :10-11 docstring 明写「防 4-1e 第三次复制」；4-1c 库有 load_io_contract + 4 个 assert_*，4-1d 库另有 schema_leaf_keys/extract_template_fields/build_min_arguments/assert_template_schema_alignment）。

#### TDD 循环 [A]：契约库常量与断言函数

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_skill_framework_contracts.py` 骨架（常量 SSOT 双向比对 + 断言函数签名 + **失败路径负例**——每断言函数 ≥1 坏数据 `pytest.raises(AssertionError, match=)`，R1-F1 先例强制） |
| 🟢 绿 | 实现 `skill_framework_contracts.py`：`FRAMEWORK_SKILL_SLUGS`（7 slug 有序元组）/ `TEMPLATE_FILES`（7 项映射）/ 分型常量（`SCORING_TYPE_SLUGS` 3 + `STRUCTURAL_TYPE_SLUGS` 4 + 各自 `REQUIRED_REFERENCES` 三件套与模板第三段字面值）/ `FAILURE_KEYWORDS = ("207", "INSUFFICIENT_DATA")`（D3）/ 断言函数（`assert_framework_data_sources_empty`（== ()）/ `assert_io_schema_contract`（import 4-1c 复用）/ `assert_sop_maturity`（失败处理关键词集换 D3 + 分型三件套）/ `assert_cross_consistency`（空集语义复用）/ `assert_template_schema_alignment`（import 4-1d 机械 + 分型第三段）——**共享常量（REQUIRED_SOP_SECTIONS/SKILL_MD_MAX_LINES/SKILLS_ROOT/load_io_contract/schema_leaf_keys/extract_template_fields/build_min_arguments）一律 import 两既有库，identity 断言自检（`is` 检查，4-1d R2-F2 先例）** |
| 🔄 重构 | 签名注解 + docstring（中文 Google 风格）+ ruff/mypy |

- [ ] Subtask 1.1: 🔴 红 — 契约库自检测试（含 identity 断言 + 失败路径负例 + 提取器边界复跑）
- [ ] Subtask 1.2: 🟢 绿 — 契约库实现（常量 + 五断言函数 + 分型参数化）
- [ ] Subtask 1.3: 🔄 重构 — 优化（命名/注解/`__all__`）

#### TDD 循环 [B]：回归网预调整（一次性前置——D8 先例）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | yaml 追加 7 条目（Task 0.2 设计稿落地，version 1.1.0 → 1.2.0、story 列表 +4-1e）→ `test_slug_set_matches_yaml_contracts` 必红（23 != 16）；改断言为三方并集后绿 |
| 🟢 绿 | ① `test_skill_mixed_data_contracts.py:78-86` 互锁断言扩 `yaml_slugs == mixed ∪ 4-1c ∪ FRAMEWORK_SKILL_SLUGS`（import 4-1e 库）；② **NON_TARGET_SLUGS 三副本派生收敛**：契约库定义 `NO_EXTERNAL_SOURCE_SLUGS = tuple(sorted(set(SLUG_TO_TOOL_ID) - set(SKILL_DATA_SOURCES) - set(MIXED_SKILL_DATA_SOURCES)))`（== 7；`SLUG_TO_TOOL_ID` import 自 `src/application/skills/skill_manifest.py:41`，`SKILL_DATA_SOURCES`/`MIXED_SKILL_DATA_SOURCES` import 自 `skill_data_collection_contracts.py`/`skill_mixed_data_contracts.py` 两既有契约库），三处（`test_pestel_analysis_data_collection.py:34-42` / `test_arch_skill_data_collection.py:53-61` / `test_arch_skill_mixed_data.py:52-60`，字面清单逐字相同）删字面清单改 import + 注释/docstring 措辞升级——**现有措辞是「非目标 Skill / 4-1e 目标 / 未被误改 / 保持空 tuple」（无「未成熟化」字样）**，统一改为「无外部源型 Skill data_sources 恒空不变量」；③ **两套验收双场景改名永久锚定**（D8）：feature 场景名「未成熟化 Skill 空白名单安全失败」→「纯内部框架 Skill 空白名单安全失败」（4-1c feature :91-95 + 4-1d feature :129-133 两处，slug 均 business-model-canvas）+ .py wrapper docstring 同步——**两处实况不同**：4-1c `test_acceptance_skill_data_collection.py:533-543` 含完整「滚动锚点规则」（:537-541，须删规则改永久锚定说明），4-1d `test_acceptance_skill_mixed_data.py:646-649` 仅一行短 docstring（同步改名语义即可）；slug 保持 business-model-canvas（空白名单是纯内部型永久设计态） |
| 🔄 重构 | grep 验证：`NON_TARGET_SLUGS` 字面清单零残留 / 「未成熟化」场景名零残留；全量 skills+architecture 测试绿 |

- [ ] Subtask 1.4: 🔴→🟢 — 回归网三件套调整（yaml 互锁扩容 + 派生收敛 + 双场景改名；落码后全量回归验证）
- [ ] Subtask 1.5: 🔄 重构 — 注释同步（三处用例 docstring 语义更新）+ 全量测试 + ruff

**完成标准/Definition of Done:**
- [ ] 契约库 + 自检全绿（负例判别力实证）
- [ ] 回归网调整落地：唯一必红点消解、三副本收敛、双场景改名
- [ ] `tests/unit/application/skills/ + tests/unit/architecture/` 全绿——**yaml 7 条目在 Subtask 1.4 一次性落地**（4-1d 先例同款：yaml 扩容与互锁断言扩展同批，落即绿）；frontmatter ↔ yaml 的 dict 相等断言位于各 Skill 单测（Task 2-8 编写时 frontmatter 已填），Task 1 自检不读 SKILL.md frontmatter，无中间红窗口；**Task 2-8 各 Skill Task 零 yaml 触碰**（R4：yaml 单点写入收敛在 Task 1）

---

### Task 2: value-proposition-canvas Skill 成熟化（Task 2-8 评分型范本）

**关联 AC:** AC-1, AC-2, AC-3

> 范本：4-1d Task 2（swot-tows 实施范本）；6 块双侧匹配（D12 勘误——Epic「9 块」不采）。

#### TDD 循环 [A]：frontmatter 声明契约

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_value_proposition_canvas_framework.py`：[A] schema 双写一致（yaml 条目 + frontmatter 同批落地）/ data_sources == () / catalog 兼容（customer_profile+value_map 双 required 保留） |
| 🟢 绿 | SKILL.md frontmatter 填 input_schema/output_schema（Task 0.2 设计稿；yaml 条目已由 Task 1.4 一次性入库，本 Task 仅落 frontmatter——R4：Skill Task 零 yaml 触碰） |
| 🔄 重构 | 行宽/注解 |

#### TDD 循环 [B]：SOP 成熟化

| 阶段 | 动作 |
|------|------|
| 🔴 红 | [B] 断言：9 章节 / input_examples 非 placeholder / ≤500 行 / 失败处理含 207+INSUFFICIENT_DATA 词边界 / 评分型三件套存在 / 编码规范四方同步抽查 |
| 🟢 绿 | SOP 编写：§1-§9（§5 = 用户输入采集计划：模板路径 + pains↔pain_relievers/gains↔gain_creators/jobs↔products 三对匹配引导 + arguments 构造）；§7 失败处理（207 误标记守护 + INSUFFICIENT_DATA 缺字段引导——文档级语义）；§8 含编码前缀真实示例；references 三件套（framework_logic：双侧匹配系统化思考——以 customer jobs 为分析起点（jobs→pains→gains 序，三对匹配为镜像结构非时序）+ 填写指引；scoring_anchors：fit 强度 1-5 刻度 + 正反例；workshop_guide：2-4 小时工作坊或轻量访谈变体——纯内部型无外部数据采集环节，以用户结构化输入工作坊替代） |
| 🔄 重构 | 章节打磨 + 编码规范四方核对 |

#### TDD 循环 [C]：跨循环一致性（空集语义）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | [C] 断言：body 标记集合 == 声明集合 == ∅（复用 `assert_cross_consistency`） |
| 🟢 绿 | SOP 无任何 `$DATA_SOURCE` 字面（示例代码块零标记——4-1e 全体 Skill 的 SOP 形态） |
| 🔄 重构 | — |

#### TDD 循环 [D]：模板 ↔ Schema 对齐

| 阶段 | 动作 |
|------|------|
| 🔴 红 | [D] 断言：`templates/vpc_canvas_matching.md` 叶子键双向 + 分区标题（customer_profile/value_map）+ 评分型第三段（引用 scoring_anchors 字面串）+ required 标注一致 |
| 🟢 绿 | 模板编写（四段式评分型；示例行与 §8/锚点三方一致——R7） |
| 🔄 重构 | 变异演示（删字段→红→还原；改标注→红→还原——AC-3 验证标准） |

- [ ] Subtask 2.1-2.8: 四循环 [A][B][C][D] 红→绿→重构（范本粒度对齐 4-1d Task 2 的 .1-.8 拆分）

**完成标准/Definition of Done:**
- [ ] 本 Skill 单测全绿（[A][B][C][D] 四循环）+ yaml 条目入库 + 模板/三件套落地
- [ ] 覆盖率不降（生产代码仅 catalog 单点增强）

---

### Task 3: business-model-canvas Skill 成熟化（存量资产整合范本）

**关联 AC:** AC-1, AC-2, AC-3

> 特有：D7 命名收敛 + 存量资产整合（pestel 先例）。

#### TDD 循环 [A]-[D]（同 Task 2 结构）

特有 Subtask：
- [ ] Subtask 3.3: 🟢 绿 — **D7 命名收敛**：`canvas_template.json` 块名 `key_partners` → `key_partnerships` + `validate_canvas.py` 的 `REQUIRED_BLOCKS` 同步 + `test_skills_loader.py:219-225` 特征串断言更新——原断言 `b"key_partners" in content` 收紧为带引号完整键 `b'"key_partnerships"'`（防旧名残留静默通过，三文件同批）；落码后 `grep -P "key_partners\b"` 验证零残留（词边界防 key_partnerships 前缀误匹配）
- [ ] Subtask 3.7: 🟢 绿 — SOP §9 References 引用存量资产（validate_canvas.py 校验器 + canvas_template.json 模板基型——pestel scoring_matrix.json 先例）；9 块语义（key_partnerships 为 catalog 锚定名）；cost_structure 自由 object 编码过渡声明（D6/4.3 defer）

**完成标准/Definition of Done:**
- [ ] 四循环全绿 + 存量资产保留且被引用 + 命名收敛三文件落地 + loader 测试同步绿

---

### Task 4: org-design-framework Skill 成熟化（catalog 增强范本）

**关联 AC:** AC-1, AC-2, AC-3

> 特有：D10 Galbraith 四维扩展（唯一预期 catalog 增强）。

#### TDD 循环 [A]-[D]（同 Task 2 结构）

特有 Subtask：
- [ ] Subtask 4.2: 🟢 绿 — catalog 增强：`org_structure` 保留既有三字段（functions/reporting_lines/decentralization_level），**新增** strategy/processes/rewards/people 四维容器（嵌套 required + description——Galbraith Star 完整性）；[A] 断言 catalog 兼容（既有 required ⊆ 新 required，R5 缓解）
- [ ] Subtask 4.6: 🟢 绿 — framework_logic 含 5 维对齐评估逻辑（TOOLS.md L1 五维表述为佐证基线）；scoring_anchors 维度对齐度 1-5 刻度

**完成标准/Definition of Done:**
- [ ] 四循环全绿 + catalog 增强落地（零删除）+ 五维完整

---

### Task 5: strategy-map Skill 成熟化（结构型范本 + 分工映射）

**关联 AC:** AC-1, AC-2, AC-3

> 特有：D13 分工（锚 `bsc_indicators`）+ bsc-scorecard 互查映射表。

#### TDD 循环 [A]-[D]（同 Task 2 结构，分型切换结构型）

特有 Subtask：
- [ ] Subtask 5.2: 🟢 绿 — schema 锚定 `bsc_indicators`（R9：[A] 断言根键，禁 strategic_objectives）；causal_relationships 因果箭头编码语法声明（「原因维度 → 结果维度：假设描述」——确定性解析锚点）
- [ ] Subtask 5.6: 🟢 绿 — references 结构型三件套（framework_logic：四层因果假设表述规范 + 战略主题卡设计；validation_rules：箭头语法 + 因果链闭合校验——**标准方向自下而上（learning_growth → internal_process → customer → financial，Kaplan-Norton）**，逆向/同层箭头标记 warning 级待澄清假设不硬失败，量化验证移交 bsc-scorecard（D13 分工闭环）；workshop_guide）；分型第三件为 **validation_rules.md**（非评分型的 scoring_anchors）；与 bsc-scorecard 互查映射表入 framework_logic（定性因果链 vs 定量计分卡分工 + 键名对照 `bsc_indicators`↔`strategic_objectives` + 传递规则——bsc↔kpi-tree 先例的映射表实位于 bsc 侧 scoring_anchors.md:18-30，结构型无评分锚点故落 framework_logic）
- [ ] Subtask 5.7: 🟢 绿 — 负向触发双向（本 Skill when_not_to_use「KPI 数值计算」点名补全指向 bsc-scorecard；**bsc-scorecard 侧回跳需本 Story 新建**——调研证实 4-1d 未建：bsc §2（SKILL.md:113-116）现仅指向 swot-tows/space-matrix/ansoff-matrix/kpi-tree，其余 SKILL.md body 对 `strategy-map` 零交叉引用（全目录命中仅 TOOLS.md:24 索引行 / `skill_manifest.py:31,:99` 映射 / strategy-map 自身 slug 行——均非 body 跳转）；在 bsc-scorecard SKILL.md §2 增补一行「定性战略因果链（不含 KPI 量化）：请用 strategy-map」——跨 Story 单行内容增量，D8 改名同类先例，R9 登记，不破坏 4-1d 守护断言（负向触发章节存在性断言不受行级增量影响））

**完成标准/Definition of Done:**
- [ ] 四循环全绿（结构型分型）+ 互查映射表 + 负向跳转双向

---

### Task 6: dependency-graph Skill 成熟化

**关联 AC:** AC-1, AC-2, AC-3

> 特有：顶层 array-of-objects 模板形态（task_list 分区标题承载——4-1d vrio 二层嵌套先例）+ gantt 分工。

#### TDD 循环 [A]-[D]（同 Task 5 结构型结构）

特有 Subtask：
- [ ] Subtask 6.5: 🟢 绿 — 模板：task_list 分区标题 + name/dependencies 叶子（依赖边编码「任务名 ← 前置任务列表」——前置列表以中文顿号「、」分隔，任务名禁含「、」与「←」）；validation_rules：DAG 无环校验 + 依赖方向规则 + 关键路径推算规则（**= 跳数最长链的无时长结构代理指标**——与 gantt 的时长归一 CPM 语义分工：dependency-graph 输入无时长，`dependency_network.critical_path` 是结构代理，gantt `gantt_visualization.critical_path` 是 ES/EF/LS/LF 零浮动的真 CPM，前者为后者的无时长退化形态）；与 gantt-chart 互相负向跳转（纯拓扑 vs 含时间排程——D13）

**完成标准/Definition of Done:**
- [ ] 四循环全绿 + 顶层 array 形态模板对齐 + 分工跳转

---

### Task 7: raci-matrix Skill 成熟化

**关联 AC:** AC-1, AC-2, AC-3

> 特有：R/A/C/I 枚举编码 + 有效性规则。

#### TDD 循环 [A]-[D]（同 Task 5 结构型结构）

特有 Subtask：
- [ ] Subtask 7.5: 🟢 绿 — assignments 自由 object 编码过渡（角色→RACI 字母组合声明——单字母或斜线组合（如 A/R），D6/4.3 defer）；validation_rules：恰 1 个 A（硬规则）+ ≥1 个 R（软规则，A/R 计为已承担 R——业界 A/R 兼任惯例）+ 无空任务（确定性规则集）；违规经 `raci_matrix.conflicts` 结构化呈现（catalog 既有 conflicts/suggestions 字段为出口）非整体失败；roles/tasks 编码声明

**完成标准/Definition of Done:**
- [ ] 四循环全绿 + RACI 规则集

---

### Task 8: gantt-chart Skill 成熟化

**关联 AC:** AC-1, AC-2, AC-3

> 特有：时长编码 + durations/resources 自由 object 过渡。

#### TDD 循环 [A]-[D]（同 Task 5 结构型结构）

特有 Subtask：
- [ ] Subtask 8.5: 🟢 绿 — 时长编码声明（「N 天/周/月」格式——正则 `^\d+ *(天|周|月)$`（禁「个月」与英文单位），归一基准 = 天（周 = 5 工作日 / 月 = 20 工作日），CPM 前推/后推算术在该单一基准上进行；解析锚点 + 模板示例行↔§8↔正则三方同文本）；durations/resources 编码过渡（D6/4.3 defer）；validation_rules：前推/后推（ES/EF/LS/LF）+ 里程碑 + CPM 关键路径推算（时长归一真 CPM——与 dependency-graph 跳数最长链的结构代理语义分工，见 Task 6.5）；与 dependency-graph 分工跳转核对（Task 6 已建单向，本侧补全双向）

**完成标准/Definition of Done:**
- [ ] 四循环全绿 + 7/7 Skill 完成（23/23 里程碑）

---

### Task 9: 集成测试与模板对齐汇总层（真实 Engine + 内部数据主通道）

**关联 AC:** AC-3, AC-4

> 范本：`test_skill_mixed_data.py` 骨架改造（无 Redis/无适配器/无 xdist_group）。

#### TDD 循环 [A]：无标记全链路（7 Skill 参数化）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/integration/application/test_skill_framework.py`：7 Skill × 真实 Engine + AsyncMock LLM（返回零标记分析代码）+ AsyncMock Sandbox；断言 SUCCESS + arguments 进 Think prompt（repr 子串 + 「规划执行步骤」特征串）+ **沙箱代码不含 DATA_SOURCES 前言** + `evidence_package.data_sources == ()` |
| 🟢 绿 | 实现通过（Skill 已成熟——Task 2-8 交付物；本 Task 验证行为面） |
| 🔄 重构 | 断言提取器复用 |

#### TDD 循环 [B]：207 误用守护 + 缺数据引导面

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 207 场景（任一 Skill 抽样，error_code 逐字断言 `EXCEPTION_207`）：**必须注入 resolver**——构造 `DataSourceResolverService(adapters={}, cache=<fake L1CachePort>, event_publisher=…)` + `engine.set_data_source_resolver`（4-1c 验收 `test_acceptance_skill_data_collection.py:225-233` 构造同款；白名单校验先于任何缓存/适配器访问，fake cache 不会被触达但 cache 为必填位置参数）；标记代码由 AsyncMock LLM 按内容分派返回（「生成代码」→ 含 `$DATA_SOURCE` 标记代码）；tool_metadata 取真实 `load_sop` frontmatter（4-1d 集成 :177-183 同款 extensions 注入）；**判别力负例**：不注入 resolver 时同一标记代码得 `EXCEPTION_101`（`tool_execution_engine.py:333-337`），非 207。缺数据引导面场景：空 arguments（`ToolCall.arguments` 默认空 dict 合法）→ 断言 Think prompt 含空 dict repr + SOP 缺口登记语义引导——**INSUFFICIENT_DATA 是 SOP 文档级关键词断言（AC-2 承载），非运行时状态断言**：该枚举在生产代码零设置点（engine 唯一 `ToolResultStatus` 设置点 `tool_execution_engine.py:209` 硬编码 SUCCESS，其余路径 raise），4-1d 先例（`test_bsc_scorecard_mixed_data.py:81-84`）即文档级 |
| 🟢 绿 | 实现通过 |
| 🔄 重构 | 参数化收敛 |

- [ ] Subtask 9.1: 🔴 红 — 无标记全链路（7 Skill 参数化：SUCCESS + arguments repr + 零 preamble + evidence 空溯源）
- [ ] Subtask 9.2: 🔴 红 — 207 误用守护（resolver 注入前提 + error_code 逐字 + 101 对照负例——[B] 循环形态）
- [ ] Subtask 9.3: 🔴 红 — 缺数据引导面（空 arguments Think prompt repr + 缺口登记引导断言——文档级语义联动）
- [ ] Subtask 9.4: 🟢 绿 — 汇总层模板对齐测试落地（`tests/unit/application/skills/test_schema_template_framework_alignment.py`——单元测试文件，7 Skill 全就绪（Task 2-8 完）后双向断言全绿；分型四段式参数化——「契约测试文件清单」表定义项）
- [ ] Subtask 9.5: 🟢 绿 — 集成全链路验证通过（`build_min_arguments` import 4-1d 库构造 arguments——防手写漂移；依赖 yaml 条目已由 Task 1.4 入库）
- [ ] Subtask 9.6: 🔄 重构 — 参数化收敛 + 断言提取器复用
- [ ] Subtask 9.7: 🔄 重构 — `pytest -n 8` 并行 + 连续 5 次无随机失败

**完成标准/Definition of Done:**
- [ ] 集成测试全绿（无 Redis 依赖验证）+ 汇总层模板对齐测试全绿

---

### Task 10: SDD 架构约束验证测试

**关联 AC:** AC-5

> 性质：SDD 规范验证（非 TDD 单元测试）。

- [ ] Subtask 10.1: 🔴→🟢 — `tests/unit/architecture/test_arch_skill_framework.py`：三方一致（FRAMEWORK_SKILL_SLUGS ↔ frontmatter ↔ catalog 兼容方向）
- [ ] Subtask 10.2: 23 Skills 最终态闭环（`SLUG_TO_TOOL_ID` 全集 == 三库并集 6+10+7；16 声明 + 7 空声明分类学终态）
- [ ] Subtask 10.3: wiring 回归断言（三文件 `tool_metadata` 特征串 + 两 use case 文件 `load_sop`（engine 豁免）+ 零 infrastructure import + `ToolExecutionEngine.__init__` 签名锁定——4-1d A7 整类复用，继承既有豁免条件）
- [ ] Subtask 10.4: 内容约束（7 SKILL.md ≤500 行 + 必需字段 + data_sources 空 tuple 终态 + version 1.0.0）
- [ ] Subtask 10.5: **Schema 合法性强化**（D11：23 条目 Draft7 check_schema + `build_min_arguments` 实例经 `JsonSchemaValidatorImpl.validate_arguments`（构造 Tool 实体）校验通过——4-3 基建测试级衔接；Draft7 先例实在 4.1 注册验收 `test_acceptance_strategic_tool_registration.py:165-177`（catalog 侧）+ 4.3 `test_jsonschema_validator.py:43`，本条目侧断言与其互补不重复）
- [ ] Subtask 10.6: 派生收敛验证（三处原字面清单 grep 零残留 + `NO_EXTERNAL_SOURCE_SLUGS` == 7）+ 运行完整套件报告

**完成标准/Definition of Done:**
- [ ] 架构测试全绿 + 合规报告输出清晰

---

### Task 11: 开发结束验收测试（含文档同步）

**关联 AC:** AC-6 + 全部收尾

> 性质：Story 收尾验收（交付物完成清单最终确认）。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | feature 收尾验收场景（src + tests 四目录完成清单逐项确认） |
| 🟢 绿 | BDD 步骤实现 + 全场景通过（含既有两套验收套件回归——双场景改名后仍绿） |
| 🔄 重构 | 场景命名收敛 |

- [ ] Subtask 11.1-11.9: 收尾场景 + 文档同步（architecture.md 四项——见「配套架构文档同步」表 + 异常设计 §3.3.2 零新增声明）+ 完成清单勾选
- [ ] Subtask 11.10: 收尾校验（`pytest` 全量 + `ruff check` + `mypy` + `make test-cov` 覆盖率不降验证 + pre-commit）

**完成标准/Definition of Done:**
- [ ] 全部完成清单验证确认 + Story 可进入 done

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) + 4-1c/4-1d 收敛范式

- **架构模式:** 六边形（Ports & Adapters）四层；本 Story 零端口/零实现层改动（R1-R4 设计规则符合性——端口面空集）
- **设计约束:** 领域零依赖；catalog 兼容强制（增强不删除）；L2 ≤500 行；frontmatter 必需字段；纯内部型空声明一等不变量
- **技术栈:** Python 3.11+ / pytest + pytest-bdd / jsonschema（4-3 基建测试级衔接）
- **接口治理:** 零端口变更——`SchemaValidatorPort`（4-3 既有注册）仅测试级消费

### 关键架构决策

**来源:** 四视角代码调研（2026-09-29）+ 4-1d 五轮审查收敛范式

| 决策 | 选中方案 ✅ | 备选 | 理由 |
|------|-----------|------|------|
| D1: data_sources 策略 | ✅ **保持空 tuple（不写键）——纯内部型一等不变量**（10/10） | 声明源（破坏三分法+4 处守护必红）（1/10）/ 写空列表键（与声明型写法混淆）（4/10） | 三分法自洽（4-1c 外部 6 + 4-1d 混合 10 + 4-1e 纯内部 7）；7 工具无外部采集语义；空声明下 [C] 断言空集语义仍有真实守护价值（防误写标记）；物理空者天然兼容 4-1d 中间态安全化断言 |
| D2: 契约库组织 + NON_TARGET 收敛 | ✅ **新建第三库 `skill_framework_contracts.py`（共享常量/机械 import 两既有库 + identity 自检）+ `NO_EXTERNAL_SOURCE_SLUGS` 派生式收敛三副本（== 7 非空，判别力保留）+ 语义改名「无外部源型恒空不变量」**（9/10） | 扩展 4-1d 库（混杂语义）（5/10）/ 三副本仅同步不收敛（违 R1-D2 defer 承诺）（3/10）/ 4-1e 库登记 7 slug 后派生式=空删用例（守护移交自检）（6/10） | 4-1d D6 先例 + 其库 docstring 明写「防 4-1e 第三次复制」（`skill_mixed_data_contracts.py:10-11`）；R1-D2 defer 义务承接；派生式语义自然升级（成熟化≠声明源），三处用例判别力不丢；**`test_frontmatter_data_sources.py:170` 的 `len(ssot_union)==16` 硬编码锚点保持字面不动**（4-1e 后声明源集合仍 = 6+10 = 16，判别力保留——纯内部型误声明源即红；语义自动升级为分类学终态 16 声明 + 7 空 = 23，4-1d R1-D2 并列提及项一并交代） |
| D3: 失败处理断言集 | ✅ **("207", "INSUFFICIENT_DATA") 替换 411/412/413**（词边界正则保留）（9/10） | 沿用 411/412/413（无数据源语义，逼 SOP 写无意义话术）（2/10） | 纯内部型失败面 = 标记误用（207）+ 内部数据不足（INSUFFICIENT_DATA——SOP 文档级关键词承载，非运行时状态断言）；契约库自检含断言集判别力负例 |
| D4: references 分型三件套 | ✅ **评分型 {framework_logic, scoring_anchors, workshop_guide} ×3 / 结构型 {framework_logic, validation_rules, workshop_guide} ×4**（8/10） | 统一三件套（scoring_anchors 对无评分 Skill 名实不符）（5/10）/ 两件套（Epic「框架逻辑引导」强制第三件缺失）（4/10） | Epic AC 2「框架逻辑引导文档」→ framework_logic.md 7/7；评分语义分型（vpc fit_score/bmc dimension_scores/org-design 对齐度）；结构型确定性规则（RACI/DAG/CPM/因果语法）承载于 validation_rules.md；**注意 4-1d 三件套实名是 data_fusion/scoring_anchors/workshop_guide——`framework_logic.md` 全仓库零实例系本 Story 首次引入**（替位 4-1d data_fusion.md 的纯内部型语义：内外融合 → 框架逻辑引导；scoring_anchors/workshop_guide 沿用同名），勿照抄 4-1d 文件名 |
| D5: 模板四段式第三段分型 | ✅ **第三段按分型条件化（评分锚点 / 校验规则），四段式骨架统一**（8/10） | 结构型删第三段三段式（断言参数化复杂）（5/10） | 微格式机械复用最大化；分型常量落契约库单一来源（R6 缓解） |
| D6: yaml SSOT 扩容 + output 溯源键 | ✅ **扩至 23 条目（version 1.1.0 → 1.2.0，story 列表 +4-1e）+ output_schema 不含 data_sources 键（惯例偏离登记）**（9/10） | 不扩（破坏 SSOT 模式）（3/10）/ output 沿用 data_sources 键（空溯源语义别扭——EvidencePackage 已空）（5/10） | frontmatter↔yaml 逐字互锁模式延续；**现状对照：既有条目顶层仅 input_schema/output_schema 两键，data_sources 是各 output_schema 内的必填溯源属性（16/16 条均含）——新 7 条目不含该属性即本 Story 偏离点**；纯内部型无外部溯源，output 含空 data_sources 是伪契约；偏离理由随 D6 登记 |
| D7: bmc 命名冲突裁定 | ✅ **以 catalog 为准收敛 `key_partnerships`（domain 零改动），更新存量两资产 + loader 断言三文件同批**（9/10） | 反向（改 catalog 键名——违反「禁删既有 required」）（3/10） | catalog 是 domain 层兼容锚；canvas_template.json/validate_canvas.py 是内容资产可改；pestel 资产保留先例 + 特征串断言同步 |
| D8: 验收双场景迁移（滚动锚点终点） | ✅ **改名永久锚定：「纯内部框架 Skill 空白名单安全失败」，slug 保持 business-model-canvas，2 feature + 2 py docstring 更新**（9/10） | 删除场景（丢失空白名单配置覆盖）（4/10）/ 构造合成空 metadata（违反验收真实服务原则）（3/10） | 23/23 全成熟后无滚动目标——空白名单是纯内部型**永久设计态**非未成熟态；场景语义升级且行为零变化（空 whitelist + world-bank 标记 → 207 依旧）；207 路径覆盖保留 |
| D9: 集成测试形态 | ✅ **无标记全链路（arguments 主通道 + 零 preamble + evidence 空溯源）+ 207（resolver 注入场景 + 101 对照负例）+ 缺数据引导面（空 arguments prompt repr）；无 Redis/无 xdist_group**（9/10） | 照搬 4-1d 双源/缓存/租户场景（无外部路径全不触发）（2/10） | 引擎无标记快速返回（:329-331）——行为面收敛为直通链路；主验证面 = arguments repr 进 Think prompt（4-1d D5 主通道语义——本 Story 升格主通道）；INSUFFICIENT_DATA 集成层不可运行时断言（零生产设置点），降格为文档级（AC-2）+ 空 arguments 引导面 |
| D10: org-design 四维扩展 + 编码规范 7/7 | ✅ **catalog 增强 +strategy/processes/rewards/people 四维容器（既有三字段保留）+ 7/7 Skill 条目编码规范与确定性解析锚点（四方同步）**（8/10） | org-design 沿用 1 维（Galbraith 残缺，TOOLS.md L1 已 5 维失实）（4/10） | 4-1d R5 增强先例（加不改删）；编码规范是框架逻辑可解析前提（分值/枚举/箭头/时长语法）；YAML 安全红线（4-1d R2 教训）|
| D11: Schema 合法性强化 | ✅ **23 条目 Draft7 check_schema + build_min_arguments 实例经 JsonSchemaValidatorImpl 校验（测试级衔接 4-3，不改生产链路）**（8/10） | 仅声明不断言（Draft7 先例已存在可顺势强化——实在 4.1 注册验收 `test_acceptance_strategic_tool_registration.py:165-177` catalog 侧 + 4.3 `test_jsonschema_validator.py:43`，非 4-1d 交付）（6/10）/ Engine 接线运行时校验（越界 4.3 defer）（2/10） | 4-3 基建已注册可用；schema 质量从「仅声明」升「可校验」；**断言面 = frontmatter/yaml 条目侧，与 4.1 catalog 侧既有覆盖互补不重复**；生产边界仅 catalog 单点增强 |
| D12: Epic 字面勘误 | ✅ **vpc「9 块」→ 6 块双侧匹配（catalog 3+3 佐证）+ `_4_1e` 文件名 → 功能性命名（命名规范声明节覆盖）**（签收留痕） | 照 Epic 字面（schema 拍平/命名违规）（2/10） | 4-1d D1「Excel 偏差」与命名声明双先例；Osterwalder VPC 方法论事实 |
| D13: 工具分工与互查 | ✅ **strategy-map ↔ bsc-scorecard 互查映射（定性因果链 vs 定量计分卡，含 bsc 侧 §2 回跳单行新建——调研证实 4-1d 未建）+ dependency-graph ↔ gantt-chart 互相负向跳转（纯拓扑 vs 含时间）**（9/10） | 不建映射（用户易混用，bsc↔kpi-tree 先例已证价值）（5/10） | 两对工具字段形似语义不同（R9 键名陷阱）；4-1d bsc↔kpi-tree 非对称映射先例（映射表在 bsc 侧 scoring_anchors.md:18-30）；**既有 4 处入站负向跳转可复用**（swot-tows:127 / change-management:108 / kpi-tree:102 → gantt/raci；value-chain-analysis:101 → org-design）；gantt 侧已被外部指向，dependency-graph 侧需自建 |

### 项目结构说明 Project Structure（本 Story 新增/修改）

```
src/application/skills/
├── value-proposition-canvas/          # Task 2：SKILL.md 成熟化 + references/ 三件套 + templates/vpc_canvas_matching.md
├── business-model-canvas/             # Task 3：SKILL.md + references/（新增 framework_logic/scoring_anchors/workshop_guide + 存量 canvas_template.json 保留（块键名收敛 key_partnerships））+ templates/bmc_nine_blocks_canvas.md + scripts/validate_canvas.py（REQUIRED_BLOCKS 更新）
├── org-design-framework/              # Task 4：SKILL.md + references/ + templates/org_star_model_assessment.md
├── strategy-map/                      # Task 5：SKILL.md + references/（framework_logic/validation_rules/workshop_guide）+ templates/strategy_map_causal_links.md
├── dependency-graph/                  # Task 6：SKILL.md + references/ + templates/dependency_task_inventory.md
├── raci-matrix/                       # Task 7：SKILL.md + references/ + templates/raci_roles_tasks.md
└── gantt-chart/                       # Task 8：SKILL.md + references/ + templates/gantt_project_plan.md

# 7 目录现状（2026-09-29 调研）：各 55 行占位 SKILL.md（16 键 frontmatter：slug/name/version/tool_name/description/when_to_use/when_not_to_use/capabilities/status/rule_version/reliability_score/execution_count/token_budget_l1/token_budget_l2/depends_on/tags——注意含两个数字键 token_budget_l1/l2，枚举脚本勿用不含数字的字符类误漏；无 data_sources/input_schema/output_schema；成熟态为 19 键 = 16 + 三键）
# + 空 references/ + 空 scripts/（6 个；bmc 的 scripts/ 已有 validate_canvas.py）+ 无 templates/（均需新建）
# TOOLS.md（L1 索引）零触碰：input/output 列是语义粒度非 catalog 根键名（4-1c/4-1d 成熟化先例未做根键对齐），
# org-design 行 description 已含 Galbraith 5 维表述，无需更新

src/domain/entities/strategic_tool_catalog.py   # Task 4 唯一预期增强（org-design 四维——只加不改删）

tests/
├── acceptance/contracts/skill_io_schemas.yaml  # Task 1-8：互锁断言扩展 + 7 条目随 Skill 追加（16→23）
├── unit/application/skills/
│   ├── skill_framework_contracts.py            # Task 1：第三契约库
│   ├── test_skill_framework_contracts.py       # Task 1：自检（负例强制）
│   ├── test_<slug>_framework.py × 7            # Task 2-8
│   └── test_schema_template_framework_alignment.py  # 汇总层
├── unit/architecture/test_arch_skill_framework.py    # Task 10
├── integration/application/test_skill_framework.py   # Task 9
└── acceptance/test_acceptance_skill_framework.feature/.py  # Task 0/11
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 4.1d](./4-1d-skills-framework-enhancement.md)（五轮代码审查收敛）

**关键学习/Key Learnings:**
- **判定映射类修复必须枚举验证等价性**（R3 F1 九宫格证伪教训）——4-1e 的 RACI 规则/DAG 环检测/CPM 推算等确定性规则写进 validation_rules 时要自检可枚举闭合
- **schema description YAML 安全红线**：禁半角「: 」与花括号形态（R2 实测红）；全角「：」与「=」安全；落码后 round-trip 复验
- **编码规范「采集端-解析端」双端验证**（R3 教训）：声明可解析 ≠ 模板可采集——模板必须产得出声明的编码格式（change 阻力列断裂先例）
- **示例分值三方仲裁**（R3-F5）：模板/§8/锚点同文本必须同分值——以锚点判定标准为仲裁
- **评审标记零泄漏**（R3-F3）：schema description 是运行时契约，审查过程标记只留 Story 文档
- **captured 写入必须有读取断言**（4-1c 教训）+ **新断言变异演示**（判别力实证）
- **回归网预调整一次性前置**（D8）：并行期红窗口零容忍——共享文件全部调整前置 Task 1
- **条目编码四方同步**（yaml/frontmatter/§3/§8）逐字双写——dict 相等断言锁定
- **Story 中的行号引用先读代码再改**（v1.1.0 复核教训）：草稿 v1.0.0 的 4 处 P1 事实偏差（bsc 回跳不存在 / ToolResultStatus 在 value_objects / 滚动锚点仅 4-1c 单侧 / ToolInputValidator 未注册）均由独立调研纠正——实施时凡引用 file:line 处先核实再动手

**应用到本故事/Applied to This Story:**
- [x] 回归网三件套调整前置 Task 1.4（D8 先例直接复用）
- [x] 契约库自检失败路径负例强制（R1-F1）
- [x] 编码规范 YAML 安全 + 三方一致断言（R2/R3 教训）
- [x] 分型断言参数化 + 两分型各一负例（R6）
- [x] 命名冲突一处裁定三文件同批（R1/D7）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code（GLM-5.3 驱动） |
| **Version** | create-story workflow v6.3.0 |
| **Execution Date** | 2026-09-29 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md:1050-1089` |
| **架构文档** | `docs/architecture/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/4-1d-skills-framework-enhancement.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **四视角代码调研** | 2026-09-29 第一轮：7 Skill 现状基线 / 成熟化模式复用 / 回归守护面 / AC 解析与方法论基线；同日第二轮（竞争性复核）：①生产链路与 catalog 行号级核验 ②契约库与回归网三副本核验 ③Skill 现状与 bsc 回跳/TOOLS.md 取证 ④BDD 双场景与 Schema 基建/文档同步点（4 P1 + 7 P2 修正落档） |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（AC 3 组映射为 6-AC 结构 + Epic 字面勘误 D12）
- [x] 架构约束从 `architecture.md` 提取（§17.3/§17.3.3/§1.5 L2 约束）
- [x] 前一个故事学习经验整合（4-1d 五轮审查教训全清单）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 四视角代码调研结论落入数据契约/决策表/风险表/守护面清单
- [x] 竞争性质量复核（checklist 模式，四 Agent 独立取证）：4 处 P1 + 7 处 P2 事实修正——Task 1 yaml 落地策略矛盾裁定（一次性落地）、bsc-scorecard 回跳「4-1d 已建」证伪（改本 Story 新建）、ToolResultStatus 路径勘正（value_objects）、滚动锚点规则单侧实况、ToolInputValidator 未注册勘正、`len==16` 锚点处置登记（D2）、loader 断言判别力收紧（带引号完整键）、architecture.md 旧值三处扩充

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/4-1e-skills-internal-framework.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/application/skills/<7 slug>/SKILL.md` 成熟化 ×7（修改）
- `src/application/skills/<7 slug>/references/{framework_logic,workshop_guide}.md` ×7 + `{scoring_anchors|validation_rules}.md` ×7
- `src/application/skills/<7 slug>/templates/<TEMPLATE_FILES[slug]>.md` ×7（命名见 Task 0.2 钉死表——bmc 为 `bmc_nine_blocks_canvas.md`，其余 6 项见「项目结构说明」树）
- `src/application/skills/business-model-canvas/references/canvas_template.json`（块键名收敛 key_partnerships——文件名不变）/ `scripts/validate_canvas.py`（特征串更新）
- `src/domain/entities/strategic_tool_catalog.py`（org-design 四维增强——唯一预期）
- `tests/unit/application/skills/skill_framework_contracts.py` + `test_skill_framework_contracts.py`
- `tests/unit/application/skills/test_<slug>_framework.py` ×7 + `test_schema_template_framework_alignment.py`
- `tests/unit/architecture/test_arch_skill_framework.py`
- `tests/integration/application/test_skill_framework.py`
- `tests/acceptance/test_acceptance_skill_framework.feature` + `.py`
- 修改：`tests/acceptance/contracts/skill_io_schemas.yaml`（+7 条目）/ `tests/unit/application/skills/test_skill_mixed_data_contracts.py`（互锁断言扩展）/ `test_pestel_analysis_data_collection.py` + `test_arch_skill_data_collection.py` + `test_arch_skill_mixed_data.py`（三副本派生收敛）/ `test_skills_loader.py`（D7 特征串）/ 两套既有验收 feature+py（D8 改名）/ `src/application/skills/bsc-scorecard/SKILL.md`（§2 单行回跳增补——Subtask 5.7，跨 Story 单行内容增量）/ `docs/architecture/architecture.md` + `sisys-uni-exception-design.md`

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 4.1e |
| **Story Key** | 4-1e-skills-internal-framework |
| **File** | `_bmad-output/implementation-artifacts/stories/4-1e-skills-internal-framework.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 4: 战略工具箱 |
| **价值组** | Skills 成熟化收官（23/23） |
| **优先级** | P0-8 |
| **覆盖 FR** | FR-ST-*（战略工具箱内部框架类） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-11）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-6）
3. [x] Architecture constraints extracted 架构约束已提取（六边形/catalog 兼容/catalog 单点增强）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（4-1d 教训清单）
5. [ ] Sprint status synced to `ready-for-dev`（创建后同步）

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | 「零 Python 生产代码改动」全称断言与 Task 4.2 catalog org-design 增强（`src/domain/entities/strategic_tool_catalog.py` 是生产代码）自相矛盾；:366 例外清单仅含 validate_canvas.py，照文执行则 Task 4.2 被禁止 | P0（文档级阻断性矛盾） | 全文 8 处统一改为「零引擎/接线/端口/异常层改动 + 唯一生产 .py 增强 = catalog org-design 四维（D10 只加不改删）」；范围澄清与六边形约束节落「唯二例外」显式清单 |
| R1-2 | INSUFFICIENT_DATA 集成场景测试不可满足：该枚举生产代码零设置点（engine 唯一 `ToolResultStatus` 设置点 `:209` 硬编码 SUCCESS），4-1d 先例全部是 SOP 文档级断言——AC-4/Task 9 原表述是无先例的运行时发明 | P1（测试不可满足性） | 集成/验收层降格为「缺数据引导面」（空 arguments Think prompt repr + 缺口登记语义断言）；INSUFFICIENT_DATA 保留为 AC-2 SOP 文档级关键词（异常契约表注明零设置点与 4-1d 先例实位 `test_bsc_scorecard_mixed_data.py:81-84`）；AC-4/AC-6/Task 9/D3/D9/测试清单/矩阵/范围澄清九处联动 |
| R1-3 | 207 集成场景漏写「必须注入 resolver」前提：标记代码 + resolver 未注入得 `EXCEPTION_101` 非 207（`tool_execution_engine.py:333-337`）；且与「零 resolver 调用」表述自相矛盾；tests/integration/ 零 207 先例（先例全在验收层且注入真实 resolver） | P1（测试不可满足性） | Task 9 [B] 补注入前提（`DataSourceResolverService(adapters={}, cache=<fake>, …)` + `set_data_source_resolver`——4-1c 验收 :225-233 构造同款）+ 101 对照负例；「零 resolver 调用」限定为「无标记主链路」 |
| R1-4 | wiring 特征串断言表述错误：`load_sop` 字面串不在 tool_execution_engine.py（零命中），既有 4-1d 断言对 engine 有豁免条件（`test_arch_skill_mixed_data.py:175`）——照「三文件均含两串」实施必红 | P1（照抄必错） | 三处（生产链路节/AC-5/Subtask 10.3）统一改为「三文件 `tool_metadata` + 两 use case 文件 `load_sop`（engine 豁免，对齐既有断言豁免条件，整类复用即继承）」 |
| R1-5 | TEMPLATE_FILES 7 项中 business-model-canvas 模板文件名全文档未定义（Task 1 绿阶段实现常量、Task 0.2「钉死」均无着落） | P1（交付物缺口） | 定名 `bmc_nine_blocks_canvas.md`（对齐 4-1d 命名风格）；Task 0 checklist 落显式 7 行命名表；Subtask 0.2/结构树/File List 三处同步具名 |
| R1-6 | 追溯矩阵 AC-3 行引用不存在的 Subtask 9.6；`test_schema_template_framework_alignment.py` 汇总层测试无任何 Task 正文承载（照 Task 清单实施则永不落地） | P1（追溯断链） | Task 9 重排为 9.1-9.7 显式七项（9.4 = 汇总层落地，全 Skill 就绪后）；矩阵 AC-3 引用改 9.4、测试分类表归属同步；Task 9 关联 AC 补 AC-3 |
| R1-7 | File List/交付清单/结构树漏登 bsc-scorecard SKILL.md 修改（Subtask 5.7 交付物） | P1（文件清单不全） | 三处补登（交付清单单列行 + File List 修改清单 + D7 行同步） |
| R1-8 | AC-6「scenarios() 风格 @scenario 显式绑定」机械失实：两套验收范本 `scenarios` 关键字零命中，仅 @scenario 逐场景绑定 | P2 | 改为「@scenario 显式绑定逐场景（范本无 scenarios() 批量导入）」 |
| R1-9 | D11 备选栏「4-1d 已有 Draft7 先例」归属错误：先例实在 4.1 注册验收（`test_acceptance_strategic_tool_registration.py:165-177`，对 catalog 侧 23×2 schema 覆盖）+ 4.3 单测，4-1d 测试零命中 | P2（归属偏差） | 四处（D11 决策行/AC-5/验证标准/Subtask 10.5）统一为「断言面 = frontmatter/yaml 条目侧，与 4.1 catalog 侧既有覆盖互补不重复」 |
| R1-10 | Subtask 5.7「全目录 grep strategy-map 零命中」字面不实（实 4 处命中：TOOLS.md:24 / manifest:31,99 / 自身 slug 行，均非 body 交叉引用） | P2 | 改为「其余 SKILL.md body 零交叉引用（命中仅索引行/映射/自身 slug，均非 body 跳转）」 |
| R1-11 | 数值偏差 5 组：4-1d 契约库 456→455 行；catalog 区间 :504-856→:504-855（三副本）；composition_root :2540-2557→:2541-2558；epics 带编号文件名 :1077-1084→:1074-1081；Story 区间端点 1090→1089（1090 是 4.2 标题行） | P2 | 六处逐点修正（:504-855 三副本同批） |
| R1-12 | D5'/D13' 为未定义引用（决策表 D1-D13 无带撇号编号；D5' 应指 4-1d D5、D13' 出处不明） | P2 | 改为「4-1d D5」实名引用 / 删除 D13' 改直述（「纯内部型无外部采集环节」） |
| R1-13 | 矩阵 AC-2/AC-5 行漏 Task 1（契约库 `assert_sop_maturity`/互锁扩容正是两 AC 载体） | P2 | 两行补 Task 1 及对应 Subtask |
| R1-14 | RACI 编码口径矛盾（数据契约表「R/A/C/I 枚举」单值 vs Subtask 7.5「字母组合」）且「≥1 R」硬规则严于业界惯例（A/R 兼任通行） | P2 | 统一裁定：单字母或斜线组合（A/R 合法）；恰 1 A 硬规则 + ≥1 R 软规则（A/R 计为已承担 R）；违规经 `raci_matrix.conflicts`（catalog 既有字段）结构化呈现非整体失败 |
| R1-15 | 「确定性规则集」未锚定输出通道（违规如何呈现悬空）；strategy-map 因果方向未钉死（箭头语法允许任意方向）；dependency-graph 与 gantt 双输出 critical_path 语义分工未澄清；时长编码三缺口（「个月」/英文单位/周月→天归一系数未定） | P2 | AC-2 验证标准 + Task 5.6/6.5/7.5/8.5 系统钉死：分析层评估逻辑 + conflicts 出口；Kaplan-Norton 标准方向自下而上（逆向/同层 = warning 不硬失败）；跳数最长链（结构代理）vs 时长归一 CPM 分工；正则 `^\d+ *(天|周|月)$` + 周=5/月=20 工作日归一 |
| R1-16 | 异常表「schema 项非法 → FrontmatterParseError fail-fast 自动生效」与解析器实况不符（frontmatter 不校验 schema 结构，缺键静默回退 `{}`） | P2 | 改写为「解析器仅 fail-fast YAML 语法/必需字段；schema 结构合法性由 AC-5 D11 测试级 check_schema 承载」 |
| R1-17 | Task 9 粒度与 AC-4 口径矛盾（7 子任务 vs 3 场景类映射未定义；207「任一 Skill」vs「×3 场景类」） | P2 | Task 9 重排九项显式子任务 + AC-4 验证标准对齐（全链路 ×7 + 207 抽样 + 缺数据引导面） |
| R1-18 | 评分锚点「首个『——』前的 1-5 整数」存在前缀整数误判（「P1 —— 4」）；依赖边前置列表分隔符未钉死；VPC 未写 jobs 分析起点；org_structure 名实不符未注记；「（改名）」易误读为文件改名；「41c」脱字；汇总层测试名与既有文件近似的防呆 | P3 | 解析锚点收紧（独立整数 + U+2014×2）；顿号分隔 + 禁含字符；jobs 起点入 framework_logic；名实注记入数据契约表；「块键名收敛」措辞；脱字修正；测试名防呆注记（区别于 4-1d `test_schema_template_alignment.py`） |
| R1-19 | Task 0.6 红阶段形态未注（yaml 未入库时 KeyError 亦为合法红；207/空声明场景未成熟化时即绿） | P3 | Subtask 0.6 补预期红点形态说明 |
| R1-20 | 分型术语六变体并存无同义声明；16 键 frontmatter 未枚举键名（防数字键误漏——本轮调研 Agent 即因正则不含数字误报 14 键，主会话实测 16 键定谳） | P3 | 命名规范声明节加同义声明；:784 注释落 16 键逐名枚举 + 成熟态 19 键对照 |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** （待 dev-story 完成后填写）
**审查模式:** （待填写）

#### 需决策 Decision Needed

- [ ] （待填写）

#### 已修复 Patch

- [ ] （待填写）

#### 已推迟 Defer

- [ ] 节点级注入（旁路+误拒双向）→ Story 4.2（4-1c 既定留项）
- [ ] `skill_io_schemas.yaml` data_sources.items 字段级化 + description 命名对齐 → Story 4.3（4-1c R2-F7 既定留项）
- [ ] 输入侧自由 object 字段化（含本 Story raci assignments / gantt durations+resources / bmc cost_structure）→ Story 4.3（4-1d A12 + 本 Story D6 沿用）
- [ ] StrategicAnalysisUseCase 的 composition_root 注册 + 接口层入口 → 入口 Story（4-1c R1-P2-13 既定 Defer）
- [ ] SPACE 分档含义表斜线双语义 → space-matrix 下次触碰（4-1d Round 3 defer——本 Story 显式不修，跨 Story 边界）
- [ ] token 预算无门禁机制 → Story 4.3/Epic 5（4-1d R3 defer 沿用）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `validate-create-story` 进行质量检查（可选）
- [ ] 运行 `dev-story` 开始实施（Task 2-8 可多 Agent 并行——共享文件已前置 Task 1）
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.2.0
**创建日期/Created:** 2026-09-29
**最后更新/Last Updated:** 2026-09-29
**更新说明/Description:**
- v1.0.0: 创建故事文件（基于 epics_v1.0.md Story 4.1e + 4-1a/4-1b/4-1c/4-1d 完成资产 + 四视角并行代码调研：7 Skill 现状基线 / 成熟化模式复用盘点 / 回归守护面穷尽 / AC 解析与方法论基线；13 项决策登记；4-1d R1-D2 留项收敛承接；Epic 字面勘误 2 项签收）
- v1.1.0: 竞争性质量复核定稿（checklist 模式四 Agent 独立取证）：P1×4——Task 1 DoD 与 Subtask 1.4 的 yaml 落地策略自相矛盾裁定（恢复 4-1d 原生「Task 1 一次性落地 7 条目」）/ Subtask 5.7「bsc 回跳 4-1d 已建」证伪（grep 零命中，改本 Story 单行新建）/ ToolResultStatus 路径勘正（value_objects 非 entities）/ 滚动锚点规则仅 4-1c 单侧实况；P2×7——ToolInputValidator 未注册勘正、len(ssot_union)==16 锚点处置登记（保持字面，D2）、D7 loader 断言收紧为带引号完整键、architecture.md 旧值三处（§1.4/§13×2）、NON_TARGET_SLUGS 现有措辞精确化（「非目标」非「未成熟化」）、D4 补 framework_logic.md 首次引入声明、vpc 叶子源码序勘正；另补 4 处入站负向跳转复用清单与 TOOLS.md 零触碰声明
- v1.2.0: 文档审查 Round 1（D1 四视角代码调研 + D2 双评审员并行审查 + D3 系统修订，20 项登记见 Docs Review Fixes 表）：P0×1——「零生产代码改动」全称断言与 Task 4.2 catalog 增强自相矛盾（8 处统一改为「零引擎层改动 + catalog 单点增强」）；P1×6——INSUFFICIENT_DATA 集成场景测试不可满足（生产零设置点，降格文档级 + 缺数据引导面）/ 207 场景漏 resolver 注入前提（不注入得 101，补 4-1c 验收构造同款 + 101 对照负例）/ wiring load_sop 特征串 engine 豁免（三处修正）/ TEMPLATE_FILES bmc 缺名（定名 bmc_nine_blocks_canvas.md）/ 矩阵 9.6 幻影 + 汇总层无承载（Task 9 重排九项）/ File List 漏登 bsc-scorecard；P2×11 与 P3×3——D11 先例归属（实在 4.1/4.3 非 4-1d）、scenarios() 机械失实、数值五组、RACI 口径裁定、因果方向/CPM 分工/时长归一钉死、FrontmatterParseError 范围改写等；另：D1 调研 Agent「14 键」误报经主会话实测定谳为 16 键（含 token_budget_l1/l2 数字键——枚举正则不含数字的伪影，已加防呆枚举）
