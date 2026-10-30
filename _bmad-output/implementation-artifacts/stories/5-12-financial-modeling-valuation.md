# Story 5.12: 财务建模与估值基础

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 财务分析师,
**I want** 系统支持财务建模与估值基础——领域层确定性估值计算引擎（DCF 现金流折现[NPV/IRR/终值两法] + 可比公司倍数法 + 先例交易法，`decimal.Decimal` 全程精确计算）+ 财务数据输入 Schema 契约（应用层 Pydantic v2）+ 估值用例统一编排（三方法一次执行汇总输出）,
**So that** 战略规划中的财务量化分析可自动计算并验证（计算结果与 Excel 基准公式对齐，误差 < 0.01%）。

### 业务价值

Epic 5「单 Agent 战略规划能力」价值组收官 Story（计算能力面）：5-1~5-10 交付了 Agent 实例化/身份/工作流/隔离/评估/漂移/检查点全链，5-11 交付 SAP 协议运行时（FR-ST-08），本 Story 交付 FR-ST-09（财务建模与估值基础——P1/V1 承诺）——战略规划「业绩差距分析→财务量化」的核心计算基座（or.md L378-382 五.2[1]：业绩差距分析阶段 CFO AGENT 负责财务差距量化）。V1 交付**确定性计算能力层**（三种估值方法 100% 可验证——与 Excel 基准对齐），LLM 参数推荐面（WACC 估计/可比公司筛选建议）与 Agent 编排消费面（CFO Agent 调用/BLM 流程接线/REST 端点）归后续 Story（范围边界表逐项切分——5-11 OD-3「协议能力层 vs 场景编排层」同构裁定）。

**范围权威**：epics_v1.0.md L1951-1996（Story 5.12 定义 + AC 四项 L1964-1967 + 性能三锚 L1970-1972 + 覆盖率 L1975-1976 + 质量 L1978-1981[含 L1981「数值精度校验（金融计算禁止浮点误差）」钦定] + 测试文件 L1984-1986 + Given/When/Then L1992-1995「输出 DCF/可比公司/先例交易三种估值结果 + NPV/IRR 与 Excel 公式对齐」）、L1448（依赖 Story 4.1a/4.3/3.2a——**兑现口径见 OD-2/OD-3**）、L1414-1416（自 Epic 4 Story 4.9 迁移声明）、L520（FR-ST-09 → Story 5.12 P1）、L1454；prd.md L1824（FR-ST-09 P1/V1：「DCF/可比公司/先例交易**基础**」）、L492（V1 里程碑「基础财务量化」行——NPV/IRR 自动计算）、L528（V2 里程碑「财务建模与估值」完整版行——龙卷风图/估值准确率≥90% 归 V2）、L385（财务量化覆盖率 100% 指标）；or.md L377-382（五、战略规划——FR-ST-09 引用 [or.md 五.3] 之节基）；interface-design.md §8.2.4 L1452-1457（财务量化分析端点 P0 表——**REST 面归属见 OD-6**）；architecture.md L2114/L2126/L2138（financial_routes/controller/schemas **规划树——实际目录结构不同，见 OD-1 勘误**）、L2477-2479（API 清单）、L2794（CFO 工具映射）、L3298（CFO 用户旅程）；sisys-core-domain-design.md §17.3.1 L964-970（CFO 职责设计真源：财务量化/投资评估/风险控制 + expertise「估值建模」）。

### 范围边界（与后续 Story 的精确切分）

| 能力 | 本 Story（5.12） | 后续 Story |
|------|------------------|------------|
| DCF 引擎（现金流折现：NPV + 终值两法[永续增长 Gordon / 退出倍数] + IRR 二分法求解；年末贴现口径；`Decimal` 全程） | ✅ 新建 `src/domain/services/financial_modeling.py` | — |
| 可比公司引擎（倍数描述统计 min/median/mean/max + 隐含企业价值区间） | ✅ 同上文件（`calculate_comparable_valuation`） | — |
| 先例交易引擎（交易对价倍数统计 + 隐含价值参考区间） | ✅ 同上文件（`calculate_precedent_valuation`） | — |
| 财务估值值对象（现金流表/DCF 假设/三方法输入输出 VO + 构造不变量守卫 242） | ✅ 新建 `src/domain/value_objects/financial_valuation.py` | — |
| 财务计算异常 `FinancialCalculationError`（EXCEPTION_470——financial 子域 470-479 新段；V1 唯一触发 = IRR 数值求解失败） | ✅ 注册四件套 | — |
| 输入 Schema 契约（应用层 Pydantic v2：三段请求 Schema + 跨字段校验 + 字符串数字 wire 契约） | ✅ 新建 `src/application/services/financial_schemas.py` | — |
| 估值用例（统一入口三段可选载荷 → 三方法编排 → 汇总结果 DTO） | ✅ 新建 `src/application/use_cases/financial_modeling.py` | — |
| 组合根 `# === Story 5.12 ===` 区段（`financial_modeling_service` + `financial_modeling_use_case` 两注册）+ 契约测试 | ✅ | — |
| Excel 基准对齐测试（基准用例 JSON + 相对误差 < 0.01% 断言） | ✅ | — |
| 性能三锚（单次估值 P95<5s + 精度误差<0.01% + 并发估值≥10） | ✅ 集成委托计时 | — |
| **LLM 参数推荐**（WACC 估计/可比公司筛选/增长假设建议——LLM 推理面） | ❌ 不做（OD-2：LLM 生成数值不可能 100% 与 Excel 对齐——确定性计算与 LLM 推理分面；epics L1953「财务建模依赖 LLM 推理」的 V1 兑现 = 参数由调用方显式提供[确定性输入]，LLM 推荐是 V2+ 增值面） | V2+ / Epic 9 |
| **Tool catalog / Skills 接入**（TOOL_CATALOG 增条目 + skill_manifest 映射 + SKILL.md 目录 + ToolCategory.FINANCIAL 枚举） | ❌ 不做（OD-3：catalog 注册的唯一执行消费链是 LLM Think/Code + Docker 沙箱[tool_execution_engine 五阶段]——与 OD-2 确定性裁定矛盾；CFO Agent 未开放[SUPPORTED_ROLES 仅 CEO——agent_instantiation.py L48]、cfo_agent.yaml 不存在、allowed_tools 白名单无消费方——接入面归 CFO 开放/Agent 编排 Story 整体接线） | CFO Agent 开放 Story / Epic 9 |
| **REST 端点**（`/api/v1/financial/analyze` + `/financial/sensitivity`——interface-design §8.2.4 P0） | ❌ 不做（OD-6：嵌入式计算能力；REST 面含认证/限流/openapi 契约整链——5-11 OD 同款「REST 面 7-2 立项时评估」；工具域先例：工具执行亦无执行端点[tools.py 仅 4-6 版本管理 5 端点]） | Story 7-2 / REST 面专项 |
| **敏感性分析**（单变量/龙卷风图——prd L492 V1 表「基础敏感性分析（单变量）」提及但 epics 5.12 范围权威 AC 未含） | ❌ 不做（OD-8：epics L1964-1967 AC 四项 + Gherkin L1992-1995 均无敏感性面——范围权威裁定；龙卷风图 prd L528 明确归 V2） | V2（龙卷风图）/ 后续估值深度 Story（单变量） |
| 压力测试建模（宏观经济变量情景——FR-ST-11） | ❌ 不做（prd L1826：FR-ST-11 P2/V2） | V2 |
| 估值结果与 BLM 流程/Checkpoint/报告的集成消费 | ❌ 不做（Epic 6 消费面） | Epic 6 |
| 多币种/税务调整/净债务精确口径（EV 股权价值桥接） | ❌ 不做（V1 基础：企业价值口径直出，股权桥接归估值深度面） | V2+ |

### 偏离声明（Deviation Declarations）

| # | 偏离 | 规划原文 | 偏离理由与归宿 |
|---|------|---------|---------------|
| OD-1 | 测试文件命名与落位从仓内惯例不从 epics 占位名：①单元测试拆为按层归目录三件——`tests/unit/domain/services/test_financial_modeling.py`（三引擎）+ `tests/unit/domain/value_objects/test_financial_valuation.py`（VO 不变量）+ `tests/unit/application/use_cases/test_financial_modeling_use_case.py`（用例编排）②架构验证 `tests/unit/architecture/test_arch_financial_modeling.py`（`test_arch_*` 前缀——既有 57 个同款）③集成 `tests/integration/test_integration_financial_modeling.py`（`test_integration_*` 前缀）④**epics 实施指南引用的 `src/interfaces/api/v1/schemas/financial_schemas.py`「Schema 骨架已存在」是失效引用**（四视角调研实证：`src/interfaces/api/v1/` 目录不存在、`src/interfaces/api/` 是平铺结构、全仓 `find -iname "*financial"` 零命中、git 历史无任何财务代码提交）——Schema 为本 Story 全新交付，落位改从应用层先例 `src/application/services/summary_schemas.py`（L8-12 注明「定义在应用层允许依赖 Pydantic」——仓内「财务类 Schema 放哪层」的直接既有惯例）→ `src/application/services/financial_schemas.py`；architecture.md L2101-2152 的 `v1/routes/controllers/schemas` 树是未落地目标设计（同树 financial_routes/financial_controller/main.py 均不存在），非本 Story 义务 | epics_v1.0.md L1984-1986（测试文件占位名）+ L1990（「Schema 骨架已存在」失效断言）+ architecture.md L2114/L2126/L2138（规划树） | 5-8 OD-1 / 5-9 OD-1 / 5-10 OD-1 / 5-11 OD-1 同款注记：epics 占位名是规划文本，仓内惯例（unit 按层归目录 / test_arch_* 前缀 / test_integration_* 前缀 / 应用层 Schema 拆文件）是活代码事实源；失效引用经四视角调研实证必须勘误（防 dev agent 按 epics L1990 找不存在的骨架） |
| OD-2 | **确定性计算裁定（本 Story 核心架构裁定）**：三种估值方法的数值计算是**领域层纯标准库 `decimal.Decimal` 确定性引擎**（`src/domain/services/financial_modeling.py`——cost_calculator/rrf_fusion 纯算法先例族），**不经** LLM 生成代码（tool_execution_engine Think/Code 阶段）、**不经** Docker 沙箱执行。依赖「Story 3.2a（LLM 客户端）」的兑现口径 = **边界确认而非消费**（5-11 对 Story 1.3 事件总线的 OD-6 同款：llm_client 端口就绪[组合根 L2004-2017 SINGLETON]但本 Story 零 LLM 调用——epics AC「计算准确率 100%（NPV/IRR 与 Excel 公式对齐）」+ L1981「金融计算禁止浮点误差」与 LLM 生成数值根本矛盾[LLM 输出不可复现非确定性]；确定性输入[调用方显式提供现金流/折现率等]→确定性输出是 100% 对齐的唯一实现路径） | epics_v1.0.md L1448（「依赖 Story 4.1a, Story 4.3, Story 3.2a（LLM 客户端）」）+ L1953（「财务建模依赖 LLM 推理和领域知识」迁移理由）+ L1964（「DCF 计算测试 - 验证现金流折现模型计算准确率 100%（与 Excel 对齐）」） | ①「计算准确率 100% 与 Excel 对齐」是 epics AC 钦定的硬验收——LLM Think/Code/沙箱链（tool_execution_engine 五阶段：LLM generate→沙箱 execute_code）每次生成不同代码，确定性不可证；②prd L492 V1 表「NPV/IRR **自动计算**」——自动计算 = 确定性代码计算（非 LLM 生成）；③「依赖 LLM 推理」的 V1 兑现 = 领域知识固化为确定性公式（DCF/倍数法是标准金融数学，无 LLM 自由度），LLM 推理增值面（参数推荐/非结构化财报→参数抽取）归 V2+/Epic 6 消费面；④零新运行时依赖（Decimal 标准库——5.7 OD-1 家族原则第六 Story 延续；无 scipy/numpy[pyproject 实证无 scipy，numpy 仅传递依赖且 domain 禁用——.importlinter L34-35]） |
| OD-3 | **零 Tool catalog / Skills 接入**：不注册 TOOL_CATALOG 条目、不加 `ToolCategory.FINANCIAL` 枚举值、不建 `src/application/skills/<slug>/` 目录、不动 skill_manifest.py。依赖「Story 4.1a/4.3」的兑现口径 = **4-3 的输入契约验证思想经应用层 Pydantic v2 Schema 承载**（本 Story 输入 Schema 契约 + 跨字段校验器——AC-3 锚），4-1a Skills 体系归 Agent 编排消费面整体接线 | epics_v1.0.md L1448（「依赖 Story 4.1a, Story 4.3」）+ L1454（「Story 5.11/5.12 依赖 Epic 4 Story 4.1a 和 Story 4.3（工具执行能力与 Schema 验证）」） | ①catalog 注册的唯一执行消费链是 `tool_execution_service`（装饰链 ValidationFeedbackDecorator > SandboxSecurityDecorator > ToolOutputValidator > Engine——LLM 生成代码 + Docker 沙箱），与 OD-2 确定性裁定直接矛盾；②注册即误导：Agent 工作流 plan 阶段从 tools_l1 选择工具后 execute 走沙箱链[agent_workflow_service.py L257-272]——注册财务工具会诱导非确定性执行路径；③CFO Agent 未开放（SUPPORTED_ROLES 仅 CEO——use_cases/agent_instantiation.py L48「V1 开放 CFO 时仅改此一处」钦定扩展点；configs/agents/ 仅 ceo_agent.yaml），allowed_tools 白名单无真实消费方；④4-1e org-design 是「唯一预期 catalog 增强」先例（strategic_tool_catalog.py L721 注释）——catalog 增强应随 CFO 开放/Agent 接线 Story 整体做（含 4 处 SSOT 同步：catalog/skill_manifest/TOOLS.md/SKILL.md）；⑤epics AC 四项（L1964-1967）零「经工具链执行」表述——执行主体是系统估值服务非 Agent 工具调用 |
| OD-4 | 覆盖率口径：epics L1975「应用层覆盖率≥85%」执行 + **domain 层 ≥90%**（本 Story 主交付面是领域层三引擎+VO——domain 门禁本身 ≥90%，双层门并存非互斥）；epics L1976「集成测试覆盖率≥75%」原样执行；整体 ≥80%（CI 门禁） | epics_v1.0.md L1975-1976 | 5-11 OD-2 同族注记：规划文本写就时（Epic 4 期）财务建模预期落应用层；实际架构裁定（OD-2）主交付面在 domain（确定性引擎）+ application（Schema/用例）双层——两层门禁都适用（85% 门保留不降，domain 90% 门由引擎/VO/异常测试族全覆盖承载） |
| OD-5 | **数值精度三钦定**：①计算全程 `decimal.Decimal`（字符串构造——`Decimal("0.1")` 仓内唯一先例 schema_validator.py L25/L138 同款构造形态；禁 float 中转）②**外部输入一律字符串数字形态**（请求 JSON 与测试基准 JSON 的数字字段全部 str——`"discount_rate": "0.1"`；pydantic v2 Decimal 字段从 str 解析零精度损失——JSON number 经 float 中转会产生二进制近似污染[0.1 → 55 位噪声]，金融工程标准 wire 契约）③**基准对齐断言用 Decimal 域相对误差断言**：`abs(calc − excel) / excel < EXCEL_ALIGNMENT_TOLERANCE`（容差 `Decimal("0.0001")` = 0.01%——epics L1971 钦定），**禁 `pytest.approx`**（仓内 float 惯例 66 处——本 Story 差异点：approx 是 float 容差断言，与「禁止浮点误差」红线冲突；解析式[NPV/终值/倍数统计]与迭代式[IRR]统一相对误差口径——Excel 基准值本身是 IEEE 754 double，逐位精确相等不可达也非必要，0.01% 容差双侧余量 ≥3 个数量级） | epics_v1.0.md L1971（「计算精度与 Excel 基准对齐（误差 < 0.01%）」）+ L1981（「数值精度校验（金融计算禁止浮点误差）」）+ L1964（「计算准确率 100%（与 Excel 对齐）」） | ①「100% 准确率」= 基准用例全集通过（N/N 全绿）口径；「误差<0.01%」= 单用例相对误差门——两锚分立不矛盾；②仓内既有金额计算先例 cost_calculator.py 用 float（L4 docstring「注入原始浮点值」）——本 Story 是精度标准升级首个 Decimal 算术面（全仓唯一 Decimal 先例仅做序列化脱敏非算术——差异显式声明防 dev 照抄 float 先例）；③Decimal context 精度钦定：计算内 `localcontext` 提升 prec=50（默认 28 位在长序列幂运算下可能截断——DCF 十年现金流 (1+r)^10 连乘位数增长；风险登记 R1） |
| OD-6 | **零 REST 端点**：openapi.yaml 零改动，不建 financial_routes/controller（architecture.md L2114/L2126 规划树不落地——同树整体未落地）；interface-design §8.2.4 两 P0 端点（`/financial/analyze` + `/financial/sensitivity`）归 REST 面专项。交付形态 = 嵌入式计算能力（组合根 resolve 可达 + 用例统一入口——5-11「嵌入式协议基础设施零 REST」同款） | interface-design.md L1452-1457（§8.2.4 财务量化分析 P0 端点表）+ architecture.md L2477-2479（API 清单） | ①epics AC 零 REST 表述（L1964-1967 四项全是计算/Schema 测试）；②REST 面含认证中间件[所有 API 路由必须过认证——CLAUDE.md 硬约束]/限流/openapi 契约测试整链，单 Story 范围爆炸；③工具域先例：工具执行本身亦无执行端点（tools.py 仅 4-6 版本管理 5 端点）——能力先行 REST 后接是仓内惯例；④`/financial/sensitivity` 依赖的敏感性分析本身不在范围（OD-8）——端点更无落地语义 |
| OD-7 | **基准夹具落位**：Excel 基准用例 JSON 落 `tests/unit/domain/services/financial_test_cases.json`（贴近主消费测试[三引擎 Excel 对齐断言]），**不建 `tests/fixtures/` 目录**（epics 占位路径） | epics_v1.0.md L1986（`tests/fixtures/financial_test_cases.json`） | **同名冲突实证**：`tests/fixtures.py` 是既有 pytest fixture 模块（12.8KB——test_env_config/test_tenant/isolated_tenant，Story 90-1 交付被多测试消费）；`tests/` 是 regular package（含 `__init__.py`），新建 `tests/fixtures/` 目录（即使无 `__init__.py`）会被解析为 namespace package 并在导入查找中**优先于同名模块**——`import tests.fixtures` 将解析到空目录，破坏既有导入（回归灾难）。仓内 tests 树无任何 .json 数据文件先例（find 实证零命中），基准 JSON 放 `tests/unit/domain/services/` 无技术障碍（pytest 不自动导入 json，测试内 `json.load` 读取）且贴近唯一消费方 |
| OD-8 | **敏感性分析不在范围**：单变量敏感性分析（prd L492 V1 表提及）与龙卷风图（prd L528 V2 表）均不做。锚位归后续估值深度 Story / V2 | prd.md L492（「NPV/IRR 自动计算 + 基础敏感性分析（单变量）」） | epics L1951-1996 范围权威零敏感性表述（AC 四项 + Gherkin 均无）——5-11 范围裁定先例（epics 与落地冲突时以范围权威为准）；prd L492 是 V1 里程碑能力盘点表（描述性）非 Story 切分表；敏感性分析是独立计算面（参数扫描循环）单独立项更符合单 Story 单价值组纪律 |

> 优先级锚说明（非偏离）：epics L1448 执行优先级 P1-12（执行序）；prd L1824 FR-ST-09 定级 P1（功能等级——V1 承诺）。双锚不矛盾（5-10/5-11 同款注记先例）。

---

## 🔗 前置依赖（全部 ✅ 无阻塞——4.1a/4.3/3.2a 为 done 交付 Story；「就绪」= 既有资产本 Story 直接消费或边界确认，无需先行动作）

| 依赖 | 组件 | 用途 | 状态 |
|------|------|------|------|
| Story 4.1a | Skills 三级体系 + Tool 聚合根 + ToolExecutionEngine（use_cases/strategic_analysis.py 等） | **边界确认非消费**（OD-3：零 catalog/Skills 接入——接入面归 CFO 开放/Agent 编排 Story；本 Story 不触碰 src/application/skills/ 与 strategic_tool_catalog.py） | ✅ done |
| Story 4.3 | SchemaValidatorPort + JsonSchemaValidatorImpl（jsonschema Draft 7+——工具 IO 契约面） | **兑现形态注记**（OD-3：工具 IO 的 JSON Schema 体系服务于沙箱工具链，本 Story 输入契约经应用层 Pydantic v2 Schema 承载[AC-3]——「验证输入契约」的 AC 思想由 pydantic Field 约束 + model_validator 跨字段校验器兑现；零 schema_validator 端口消费） | ✅ done |
| Story 3.2a | LLMClientPort（domain/ports/llm_client.py L129-199 三方法）+ LitellmLLMClient + 组合根 `llm_client` 注册（L2004-2017 SINGLETON） | **边界确认非消费**（OD-2：V1 确定性计算零 LLM 调用；端口就绪供 V2+ 参数推荐面消费——5-11 对 Story 1.3 的 OD-6 同款「依赖声明的边界确认」兑现形态） | ✅ done |
| 领域层计算服务先例族 | `cost_calculator.py`（类形态 + `for_pricing()` 组合根工厂 classmethod L92-104）+ `rrf_fusion.py`（模块级纯函数 + ValidationError 守卫 L25）+ `debate_evaluator.py`（无状态领域服务「类即接口」字符串 impl 注册——组合根 L2637-2650 SINGLETON） | FinancialModelingService 的形态模板（类即接口注册先例——本 Story 服务照抄此注册形态） | ✅ 就绪 |
| 应用层 Schema 先例 | `src/application/services/summary_schemas.py`（L8-12 设计决策注释「定义在应用层允许依赖 Pydantic；领域层零外部依赖约束不适用」+ FinancialSummary Pydantic 模型 L20-76——**含「Financial」命名的唯一既有 pydantic Schema**[结构化摘要契约，非估值]） | financial_schemas.py 落位与形态模板（Schema/prompts 拆文件惯例：debate_schemas/agent_workflow_schemas 同族） | ✅ 就绪 |
| 用例形态先例 | `use_cases/agent_instantiation.py`（frozen Result DTO 就地定义 L51-61 + 构造注入 + 组合根 interface 绑自身注册 L2722-2742）+ `use_cases/run_agent_workflow.py`（@trace 装饰 + 可选依赖尾追形态） | FinancialModelingUseCase 结构模板 | ✅ 就绪 |
| 异常体系 | financial 子域 470-479 **空闲段**（_code_ranges.py CODE_RANGES 实测：agent 440-449 全满 + evaluation 450-459 预留 453-459 + sap 460-469 预留 463-469；`grep 'EXCEPTION_(4[7-9]\|...)`' 全仓仅 999 兜底——**470-998 全部空闲**）+ `DomainError` 基类体系 + `EXCEPTION_HTTP_MAP`（BusinessRuleViolationError→422 惯例锚 L168）+ CI 校验（test_code_ranges.py + test_error_code_uniqueness.py 自动 8 项）+ 计算失败类异常先例 `AgentEvaluationError`（EXCEPTION_450，kwargs 构造 context 三键诊断锚——evaluation_exceptions.py） | FinancialCalculationError 470 落位（第七段先例：前段语义独立→开独立段——410/420/430/440/450/460 六段同款） | ✅ 就绪 |
| 组合根注册族 | Epic 5 区段（`# === Story 5.11 ===` sap_bus L3107-3119 最新形态 + owner="platform" 惯例 + 装配工厂禁放组合根[组合根零私有函数纪律——build_* 工厂下沉 application 域模块，build_tool_execution_engine/_build_agent_workflow_use_case 先例]） | `# === Story 5.12 ===` 区段写法参照 | ✅ 就绪 |
| 测试基建 | R6 现代形态（test_acceptance_sap_protocol.py L1-33 文件头钦定：「PG 模板 R6 三要素[多行 @scenario 字面量路径+场景绑定与步骤实现交替+AC 横幅分组] + 5-3/5-5/5-10 改造三件套[真实断言禁 then-pass + context dict fixture + 模块级 event_loop + _run_async 同循环——禁 @pytest.mark.asyncio]」）+ conftest 文件名服务 marker 机制（`financial` 不含服务关键词→仅自动挂 acceptance——**纯计算零外部服务依赖，全部场景可跑零 skip**）+ 契约测试 11 维度模板（test_port_contract_sap_bus.py）+ `_PERF_CACHE` 委托计时最新形态（嵌套 dict 单 key + 常量单源集成定义 + 验收延迟 import + 常量等值断言变异锚）+ xdist 16 组清单（sap-protocol-perf 最新）+ TestTenant（tests/isolation.py） | 测试骨架全套参照 | ✅ 就绪 |

**移交给本 Story 的留项**：无（deferred-work.md 全文 grep「5-12/5.12/financial/财务/估值」零钦定条目——与 5-11 对照[其承接 R1-DF2/OD-4·P3 两条]，本 Story 无留项处置义务）。

---

## 🔗 现有代码继承（必须复用，禁止重复定义）

> ⚠️ **防重复造轮子清单**——以下组件已存在，dev agent 只可「直接复用 / 参考照抄」，禁止新建同义组件。

| 组件 | 文件路径 | 复用方式 |
|------|---------|---------|
| 领域计算服务形态 | `src/domain/services/cost_calculator.py`（类 + 纯计算 calculate + `for_pricing()` 工厂 L92-104——「组合根负责从配置对象提取值保持领域层零外部依赖」注释形态） | **参考照抄形态，禁照抄精度**——cost_calculator 用 float（L4 docstring「注入原始浮点值」），本 Story 是全仓首个 Decimal 算术面（OD-5 精度升级——差异点显式声明） |
| 模块纯函数 + 守卫先例 | `src/domain/services/rrf_fusion.py`（`fuse()` 模块级函数 + ValidationError 守卫） | 参考守卫写法（本 Story VO 守卫走 242 非裸 ValidationError——异常红线） |
| 类即接口注册先例 | `src/domain/services/debate_evaluator.py` + 组合根 L2637-2650（`impl="src.domain.services.debate_evaluator.DebateEvaluator"` 字符串路径 + Lifetime.SINGLETON——无状态领域服务注册三件套） | **参考照抄**——`financial_modeling_service` 注册同款（无状态纯计算 SINGLETON 安全——DC-9） |
| 应用层 Pydantic Schema 先例 | `src/application/services/summary_schemas.py`（L8-12 层归属决策注释 + Field 约束形态） | **参考照抄**——financial_schemas.py 文件头同款层归属注记 + 拆文件惯例（debate_schemas/agent_workflow_schemas 族） |
| 用例结构先例 | `src/application/use_cases/agent_instantiation.py`（Result DTO 就地 frozen dataclass + 构造注入 + execute 单入口） | **参考照抄**——FinancialModelingUseCase + FinancialValuationResult DTO 形态 |
| 实体不变量守卫先例 | `EntityValidationError`（EXCEPTION_242——business_exceptions.py L95-107「用于实体 validate() 和 __post_init__() 中的构造器守卫」） | **直接消费**——全部 VO `__post_init__` 守卫的异常面（context 携 field/entity 键——sap reason 闭集拒绝先例同款 context 形态） |
| 异常构造先例 | `AgentEvaluationError`（EXCEPTION_450，kwargs 构造 `agent_id/phase/reason` → context 三键诊断锚——evaluation_exceptions.py L36+） | **参考照抄**——FinancialCalculationError 构造 `method/detail` → context 两键（计算失败类异常 kwargs 形态模板） |
| 组合根注册先例 | `agent_instantiation_use_case` L2722-2742（interface 绑用例类自身——「对齐 orchestration_service 先例」注）+ `# === Story 5.11 ===` 区段 L3107-3119（最新区段形态 + 决策记录式长注释） | **参考照抄**——`# === Story 5.12 ===` 区段（决策注释 + 两注册） |
| 契约测试模板 | `tests/contracts/test_port_contract_sap_bus.py`（模块常量六件 + _DummyResolver + 11 维度 + REQUIRED_METHODS） | **参考照抄**——test_port_contract_financial_modeling.py（REQUIRED_METHODS=["execute"]；11 维度 + financial_modeling_service resolve 可达追加维度） |
| R6 验收骨架 | `tests/acceptance/test_acceptance_sap_protocol.py`（文件头三属性分档 docstring L1-33 + pytestmark L53-56 + 模块级 event_loop L59-64 + context fixture L67-93 + _run_async L96-98 + @scenario 字面量绑定 + 延迟 import 纪律） | **参考照抄裁剪**——test_acceptance_financial_modeling.py 取 docstring/pytestmark/context fixture/@scenario/延迟 import 五件；**event_loop/_run_async 两件不适用省略**（本 Story 全同步交付面——零 async 步骤）；纯计算零外部服务：无 Redis/LLM 探测 skip、无 redis marker 分档——比 5-11 更简 |
| 性能委托计时 | `tests/integration/test_integration_sap_protocol.py`（常量单源 L45-53 + `_PERF_CACHE` 嵌套 dict L56 + cache-or-compute helper L212-259 + warmup 1 + 20 采样 `quantiles(latencies, n=20)[18]` exclusive + xdist_group 文件级） | **参考照抄**——单 key `financial_perf` 载三指标（延迟/精度汇总/并发）；**常量单源分层钦定**：`EXCEL_ALIGNMENT_TOLERANCE = Decimal("0.0001")` 定义于单测文件 `tests/unit/domain/services/test_financial_modeling.py` 模块级（Task 3 先建——单测/集成/验收三面共用禁双真源；委托链：单测[源]→集成[re-export]→验收[import 集成]）；`FINANCIAL_VALUATION_P95_LIMIT_SECONDS = 5.0` / `FINANCIAL_CONCURRENCY_FLOOR = 10` 定义于集成模块（仅性能面使用——Task 6 建立时序成立，验收 import 禁双真源——5-11 惯例原样） |
| AST 架构验证器 | `tests/unit/architecture/test_arch_sap_protocol.py`（白名单/实例化收窄/静态锚/零抑制四验证器 + `_scan_file_top_imports` helper） | **参考照抄**——test_arch_financial_modeling.py（验证器 A：domain 两文件第三方 import 白名单**空集**[纯标准库——比 sap 的 {pydantic} 更严，Decimal/math/statistics/json 均标准库] / B：组合根外零实例化 + C：Decimal 静态锚 + 零抑制注释） |
| 手写零 IO 替身族 | `_RecordingEventPublisher`（全仓 15+ 文件 duck-typing 先例） | 参考形态——本 Story 用例测试替身：`_StubModelingService`（duck-typing 捕获三方法调用——单测编排断言用） |
| xdist 组清单（16 组实名） | agent-workflow-perf / agent-isolation-perf / agent-triple-isolation-perf / isolation-switch-log-perf / phoenix-tracer-perf / agent-evaluation-perf / drift-detection-perf / checkpoint-evaluation-perf / agent-instantiation / agent-profile-loading / data-source-cache / sandbox-daemon / tool-executions-pg / tool-versions-pg / validation-feedback-pg / sap-protocol-perf | **新组 `financial-modeling-perf` 与 16 组互异**（全仓 grep 断言——5-9/5-10/5-11 同款；存量子集断言形态零同步义务） |
| 用例工厂纪律 | 组合根零私有函数纪律（build_* 工厂下沉 application 域模块——`build_tool_execution_engine` 先例 engine 文件 L621-652） | 知悉——本 Story 用例无复杂装配（lambda 单表达式足够），不引入工厂 |
| `statistics` 标准库 | 均值/中位数原生支持 Decimal 输入（`statistics.mean/median`——Python 3.11 官方支持 Decimal） | **直接消费**——可比/先例倍数统计（domain 零依赖合规——标准库白名单天然过 import-linter；domain 现无 statistics 使用先例，本 Story 是首个——白名单无需变更） |

**明确不存在、本 Story 需新建**（四视角调研实证：`find /home/agimtech/sisys -iname "*financial"` 全仓零命中[排除 .git]；`DCF|NPV|IRR|WACC` 在 src 的 *.py 零命中[仅 rule_extractor.py L72-94 NER 词典文本与 entity_extraction 测试语料——非计算实现]；`valuation|comparable|precedent` src+tests 零命中；git log 全历史 grep financial/DCF/NPV/估值 仅 3 个文档提交零代码；TOOL_CATALOG 23 条无财务工具；ToolCategory 无 FINANCIAL 枚举；skill_manifest 无财务 slug；SUPPORTED_ROLES 仅 CEO；组合根 grep financial 零占用；CODE_RANGES 无 "financial" 子域行；470-998 全空闲；`EXCEPTION_470` 全仓零命中）：

1. `src/domain/value_objects/financial_valuation.py`——财务估值 VO 族（frozen dataclass + `__post_init__` 不变量守卫 242）
2. `src/domain/services/financial_modeling.py`——`FinancialModelingService` 类即接口三方法（calculate_dcf / calculate_comparable_valuation / calculate_precedent_valuation）
3. `src/domain/exceptions/financial_exceptions.py`（EXCEPTION_470——新文件）+ 异常注册三动作（`_code_ranges.py` CODE_RANGES 增 `"financial": (470, 479)` 行 + 段注释 + `_CLASS_TO_SUBDOMAIN` 增一行；`domain/exceptions/__init__.py` 导出；`interfaces/api/exception_handlers.py` EXCEPTION_HTTP_MAP 470→422）
4. `src/application/services/financial_schemas.py`——三段请求 Pydantic v2 Schema 族 + 跨字段校验器
5. `src/application/use_cases/financial_modeling.py`——`FinancialModelingUseCase` + `FinancialValuationResult` DTO
6. 组合根 `# === Story 5.12 ===` 区段（financial_modeling_service + financial_modeling_use_case 两注册）
7. 测试资产（新建十件[.feature/.py 分计]）：`tests/unit/domain/services/test_financial_modeling.py` / `tests/unit/domain/services/financial_test_cases.json`（OD-7 落位）/ `tests/unit/domain/value_objects/test_financial_valuation.py` / `tests/unit/domain/exceptions/test_financial_exceptions.py` / `tests/unit/application/use_cases/test_financial_modeling_use_case.py` / `tests/contracts/test_port_contract_financial_modeling.py` / `tests/unit/architecture/test_arch_financial_modeling.py` / `tests/integration/test_integration_financial_modeling.py` / `tests/acceptance/test_acceptance_financial_modeling.feature` + `test_acceptance_financial_modeling.py`
8. 文档联动：`docs/architecture/sisys-uni-exception-design.md` §3.3.2（编码分配表插 financial 470 行 + 子域范围表更新）
9. 存量触碰（异常注册面）：`tests/unit/interfaces/api/test_exception_handlers.py`（expected_types 集合追加 470——穷举等值断言，尾部追加策略 + import 块同步追加 FinancialCalculationError——5-11 Task 1「两处同步」教训）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: DCF 现金流折现引擎——NPV + 终值两法 + IRR，与 Excel 基准对齐

**Given** 真实 `FinancialModelingService`（手工直接实例化——无状态纯计算服务，验收/单测均手工构造）与基准用例集 `tests/unit/domain/services/financial_test_cases.json`（`dcf_cases` 数组——每条含 name / input[cash_flows: [{period, amount}] 全字符串数字 / discount_rate / terminal_value_method / terminal_growth_rate 或 exit_multiple+terminal_exit_metric] / expected[npv / terminal_value / irr]——expected 值来源 docstring 注明 Excel 公式形态如 `=NPV(rate, CF1:CFn) + TV/(1+rate)^n` 与 `=IRR(CF0:CFn)`，基准值人工以 Excel 逐例核验后固化）
**When** ①对每条 DCF 基准用例：构造 `CashFlowSchedule` + `DcfAssumptions`（VO 构造即验）→ `service.calculate_dcf(schedule, assumptions)`②终值两法各至少一条用例（perpetual_growth 与 exit_multiple）③IRR 路径：每条用例结果的 `irr` 字段④异常路径：现金流无符号变更（全正/全负）构造 `CashFlowSchedule`；`terminal_growth_rate ≥ discount_rate` 构造 `DcfAssumptions`；多次符号变更病态序列（如 [−100, 230, −132]——NPV 在 bracket 端点同号）触发引擎求解失败
**Then** ①**NPV/终值对齐**：`abs(result.npv − expected_npv) / abs(expected_npv) < EXCEL_ALIGNMENT_TOLERANCE`（Decimal("0.0001")——OD-5③ 相对误差断言；终值 terminal_value 同口径——terminal_value 是**未折现**名义值）；**NPV 分解自洽锚**：`result.npv == sum(result.present_values) + result.terminal_value / (1+r)^n`（Decimal 域**精确相等**断言——逐期现值 + 折现终值之和恒等于 npv，同源算术分解内部自洽；`terminal_value_weight` 语义钦定 = 折现终值占 npv 比 `PV(TV)/npv`，基准用例选正常正值 NPV 使 weight ∈ (0,1) 可断言）②**终值两法各自对齐**（永续增长 TV = CF_n×(1+g)/(r−g)；退出倍数 TV = exit_multiple × terminal_exit_metric——两法各至少 1 条基准）③**IRR 对齐**：`abs(result.irr − expected_irr) / abs(expected_irr) < EXCEL_ALIGNMENT_TOLERANCE`（IRR 是迭代解——Excel IRR 内部同样迭代[Newton+bisect 回退]，0.01% 容差双侧余量充分）④**异常路径三段式**：无符号变更 → `EntityValidationError`（EXCEPTION_242——VO `__post_init__` 守卫[IRR 可解必要条件：现金流序列至少一次符号变更——Descartes 符号规则]，context 携 field="cash_flows"）；g≥r → 242（context field="terminal_growth_rate"——构造期静态可判定的不变量归 VO 层钦定）；病态序列 bracket 失败 → `FinancialCalculationError`（EXCEPTION_470，context 携 method="dcf" + detail 含求解失败描述——Excel `#NUM!` 语义对齐钦定）
**And** **贴现口径钦定**：年末惯例（end-of-year——PV_t = CF_t/(1+r)^t，t=1..n，与 Excel `NPV()` 函数口径一致；期初口径[Excel NPV×(1+r) 或 XNPV]不在 V1——知悉注记）；**计算精度钦定（OD-5③）**：引擎内 `localcontext` 设 `prec=50`（默认 28 位在十年期 (1+r)^10 连乘下可能截断——风险 R1）；**IRR 求解钦定（DC-4）**：二分法 + bracket 前提[NPV(r_lo) 与 NPV(r_hi) 异号，r_lo=Decimal("-0.99")、r_hi=Decimal("10")] + 收敛判据区间宽度 < Decimal("1e-12") + 最大迭代 256 次；**输入零 float 钦定**：VO/引擎签名全部 `Decimal` 类型注解（mypy 强制），JSON/str 入口经 pydantic Decimal 字段从字符串解析（OD-5②）；**`DcfValuationResult` 字段面**：present_values: tuple[Decimal, ...]（逐期现值——可观测中间量）/ npv / terminal_value / terminal_value_weight / irr 五字段 frozen dataclass

**验证标准/Validation Criteria:**
- [ ] DCF 基准用例全过（含两终值法各≥1 条——N/N 全绿 = epics L1964「计算准确率 100%」口径）
- [ ] NPV/TV/IRR 三值相对误差断言（Decimal 域——零 pytest.approx）
- [ ] 终值占比关系断言（weight == tv/npv）
- [ ] 无符号变更 → 242 三段式（raises + code + context.field）
- [ ] g≥r → 242（DcfAssumptions 跨字段守卫）
- [ ] 病态 bracket 失败 → 470 三段式（raises + code + context.method="dcf"）
- [ ] 贴现口径/精度/二分法参数落 docstring（三钦定注记）

### AC-2: 可比公司与先例交易引擎——倍数统计 + 隐含价值区间

**Given** 真实 `FinancialModelingService` + 基准用例集 `comparable_cases` / `precedent_cases` 数组（comparable 输入：comparables[{name, ev_ebitda}] + target_ebitda；precedent 输入：transactions[{target_name, ev_ebitda}] + target_ebitda——全字符串数字；expected：multiples 的 min/median/mean/max + implied_ev 区间[low=median? 钦定见 And]）
**When** ①`service.calculate_comparable_valuation(comparable_set, target)`（`ComparableSet` VO + 目标指标）②`service.calculate_precedent_valuation(transaction_set, target)`③异常路径：空 comparables / 空 transactions 构造 VO；非正倍数（ev_ebitda ≤ 0）构造集合成员
**Then** ①**可比统计**：`result.multiples_stats.min/median/mean/max` 四值与 expected 逐一相对误差断言（Excel `MIN/MEDIAN/AVERAGE/MAX` 基准）；`implied_ev_low == stats.min × target_ebitda` / `implied_ev_median == stats.median × target_ebitda` / `implied_ev_high == stats.max × target_ebitda`（Decimal 域精确相等断言——乘法解析式内部自洽，同源 Decimal 乘法可精确断言）②**先例统计**：同构断言（`PrecedentValuationResult`——对价倍数统计 + 隐含参考区间三值）③**异常路径**：空集合 → 242（VO `min_length` 守卫——ComparableSet/PrecedentTransactionSet 非空不变量）；非正倍数 → 242（成员级守卫 ev_ebitda > 0——倍数域正值不变量）
**And** **统计语义钦定**：median 偶数样本取中间两数均值（`statistics.median` 官方语义——Decimal 域原生支持）；mean 用 `statistics.mean`（Decimal 精确和/个数——无 float 中转）；**两引擎共享私有 helper 允许**（`_multiple_stats` 内部函数——数学同构[倍数集合统计]但语义入口分立[交易对价 vs 交易市场倍数]，VO/结果类型独立）；**V1 统计口径**：全集统计无离群值剔除、无行业细分（V1 基础口径——prd L528 完整版归 V2 知悉注记）；**隐含区间语义注记**：low/median/high 是倍数区间×目标指标的机械映射（投资判断口径[剔除/加权]是 LLM 推荐面——OD-2 V2+）

**验证标准/Validation Criteria:**
- [ ] 可比/先例基准用例全过（统计四值 + 隐含区间三值——Excel MIN/MEDIAN/AVERAGE/MAX 基准）
- [ ] 隐含区间乘法精确相等断言（Decimal 同源乘法）
- [ ] 偶数样本 median 语义用例（如 4 家可比——中间两数均值）
- [ ] 空集合 → 242（两类 VO 参数化）
- [ ] 非正倍数 → 242（成员级守卫）

### AC-3: 财务数据输入 Schema 契约——应用层 Pydantic v2 三段请求 + 字符串数字 wire 契约

**Given** `src/application/services/financial_schemas.py` 的 `FinancialValuationRequest` Schema 族（`DcfRequestSection` / `ComparableRequestSection` / `PrecedentRequestSection` 三段 + 顶层请求——epics L1967「输入 Schema 测试 - 验证财务数据输入契约」+ L1992 Given「企业财务数据已上传解析」的结构化承载）
**When** ①合法全量请求构造（三段齐备——数字字段全部字符串形态 `"0.1"`）②合法部分请求（单段 DCF——另两段 None 缺省）③非法输入六类逐一构造：负折现率（discount_rate="-0.1"）/ 折现率≥1（"1.5"）/ g≥r 跨字段（terminal_growth_rate="0.12" + discount_rate="0.10"）/ 空现金流列表（dcf.cash_flows=[]）/ 空可比列表（comparables=[]）/ 三段全 None。**Schema 字段面钦定无冗余期数字段**（期数由 cash_flows 长度承载——不设 projection_periods，故无「期数不一致」非法类）；**float 入口知悉注记**：pydantic Decimal 字段接受裸 float 输入是官方行为（不启用 Strict 拒绝——float→Decimal 带二进制噪声，由 wire 契约[Then④ docstring 钦定字符串形态]约束而非类型拒绝；单测断言字符串路径精确性，float 路径知悉不测）
**Then** ①**合法构造**：`FinancialValuationRequest.model_validate(payload)` 通过——Decimal 字段值 `== Decimal("0.1")` 精确相等断言（字符串→Decimal 零精度损失验证锚——OD-5② 核心断言）；`to_value_objects()`（Schema 就地方法或用例内转换函数——**钦定：转换函数在用例文件 `to_value_objects(request) -> 三 VO 元组`**，Schema 保持纯契约）②**部分请求**：缺省段 None——用例按 None 跳过该方法（AC-4 编排）③**非法输入**：`pydantic.ValidationError` 原样抛出（Field gt/lt 约束 + `model_validator(mode="after")` 跨字段守卫[「至少一段非 None」+ DcfSection 内 g<r 二次守卫]——**框架原生异常透传不包装**：5-11 AC-4「坏 JSON → pydantic ValidationError 原样透传」先例同款；应用层入参契约失败是框架面非领域异常面——三层异常语义分立钦定：Schema 层 pydantic.ValidationError / VO 层 242 / 引擎层 470）④**wire 契约 docstring**：Schema 文件头注记「数字字段一律字符串形态（金融工程标准——JSON number 经 float 中转产生二进制近似污染，str→Decimal 解析零损失）」
**And** **Schema 字段面钦定**：`DcfRequestSection{cash_flows: list[DcfCashFlowItem{period: int≥1, amount: Decimal}], discount_rate: Decimal gt=0 lt=1, terminal_value_method: Literal["perpetual_growth","exit_multiple"], terminal_growth_rate: Decimal ge=0 | None, exit_multiple: Decimal gt=0 | None, terminal_exit_metric: Decimal gt=0 | None}`（法配套跨字段校验：perpetual_growth 法必填 g 且 exit 两字段须 None；exit_multiple 法反之——`model_validator` 实现）；`ComparableRequestSection{comparables: list[ComparableCompanyInput{name: str min_length=1, ev_ebitda: Decimal gt=0}] min_length=1, target_ebitda: Decimal gt=0}`；`PrecedentRequestSection` 同构（transactions min_length=1）；**Schema 与 VO 约束镜像关系**：Schema 是外部契约面（pydantic 约束），VO 是领域不变量面（`__post_init__` 242）——**双层守卫刻意冗余钦定**：外部输入经 Schema 先拦（框架异常可读性好），领域层 VO 独立守卫防绕过 Schema 的内部构造（防御纵深——两层测试各自覆盖，VO 守卫不经「Schema 已拦」豁免）

**验证标准/Validation Criteria:**
- [ ] 合法全量/部分请求构造通过 + Decimal 精确相等断言（str→Decimal 零损失锚）
- [ ] 非法输入六类 pydantic.ValidationError（负折现率/折现率≥1/g≥r 跨字段/空现金流/空可比/三段全 None）
- [ ] 终值两法字段配套校验（perpetual 法带 exit 字段拒绝 / exit 法缺 exit_multiple 拒绝）
- [ ] wire 契约（字符串数字）落 docstring + 基准 JSON 同口径
- [ ] 三层异常语义分立（pydantic.ValidationError / 242 / 470 各自触发面互不越界——单测断言异常类型）

### AC-4: 端口接线与契约——组合根注册 + 契约测试 11 维度 + 架构合规

**Given** ①组合根 bootstrap 后的端口注册中心②真实 `FinancialValuationRequest` 三段全量 payload（验收用 5 期现金流 + 4 家可比 + 3 笔先例的自包含样例）
**When** ①`resolver.resolve("financial_modeling_use_case")` → `execute(request)` 全链（三方法编排）②`resolver.resolve("financial_modeling_service")`③契约测试与架构验证器运行
**Then** ①**全链输出**：`FinancialValuationResult` 含 dcf/comparables/precedents 三段结果（三段各自与直接调服务结果逐一相等——编排零变换锚：用例是纯编排[Schema→VO→服务→DTO]，同输入同输出）；**fail-loud 编排**：任一方法抛 470 → 整个 execute 上抛（不吞不降级不返回部分结果——OD-7 5-11 fail-loud 哲学同族：调用方拿到明确失败自行处置）②**接线四件**：resolve 两端口非 None；`financial_modeling_service` PortSpec（version v1.0.0 / lifetime SINGLETON[无状态纯计算——DC-9 论证] / owner=platform[Epic 5 族惯例] / tags=("financial","valuation","domain-service")，字符串 impl 延迟加载——debate_evaluator 先例）；`financial_modeling_use_case` PortSpec（v1.0.0 / SINGLETON / owner=platform / tags=("financial","valuation","usecase")，lambda 注入 service，interface 绑用例类自身——agent_instantiation_use_case 先例）+ 注入链断言（用例实例 `_service` 非 None）③**契约测试**（test_port_contract_financial_modeling.py——11 维度 + REQUIRED_METHODS=["execute"] + `_DummyResolver` 分发 service 替身 + 追加维度：resolve("financial_modeling_service") 可达与类名断言[双端口单文件钦定——use_case 主端口 11 维度 + service 依赖可达维度]）；**架构合规**（test_arch_financial_modeling.py 四验证器：A domain 两文件[financial_valuation.py + financial_modeling.py]第三方 import 白名单**空集**——纯标准库[decimal/math/statistics/dataclasses/typing 白名单天然过]；B 组合根外零实例化[FinancialModelingService/FinancialModelingUseCase 构造点仅 composition_root.py + tests/] + financial_exceptions.py 仅在异常注册三件内；C Decimal 静态锚[两 domain 文件含 `decimal` import + 关键签名 Decimal 注解——grep/AST 双形态] + 值对象 frozen 锚；D 零抑制注释[交付文件 noqa/type: ignore/pylint: disable 零命中]）
**And** **零事件面**（计算服务无领域事件——cost_calculator/rrf_fusion 无事件先例；event_channels.yaml/ChannelRouter/domain/events 零改动——链路接线断言清单注记「零事件发布面」与 5-11 Task 0 同款形态）；**零 REST 面**（OD-6——openapi.yaml 零改动）；**零 Tool catalog 触碰**（OD-3——strategic_tool_catalog.py/skill_manifest.py/skills/ 目录零改动——验证器断言可选）；**装配失败语义**：service 是字符串 impl（无需依赖 resolve），use_case lambda 单依赖 resolve 失败 → KeyError 自然传播（**与 5-11 DC-12 fail-fast 翻译差异注记**：本 Story 用例依赖是既有必注册端口[financial_modeling_service 同区段先行注册]，无 ImportError 形态[非 __import__ 内联]——零包装让 KeyError 传播是组合根既有惯例，5-11 的 ConfigurationError 翻译是其自造 fail-fast 形态的义务，本 Story 不复制不引用）

**验证标准/Validation Criteria:**
- [ ] resolve 两端口四件断言（可达/PortSpec 元数据/SINGLETON/注入链）
- [ ] 全链三段结果与直接服务调用逐一相等（编排零变换锚——`_StubModelingService` 替身捕获三方法各自被调 + 真实服务全量对照）
- [ ] fail-loud：stub 抛 470 → execute 上抛同异常（raises + code 断言）
- [ ] 契约测试 11 维度 + service 可达追加维度全绿
- [ ] 架构验证器 A/B/C/D 全绿（含白名单空集与 Decimal 静态锚）
- [ ] 零事件/零 REST/零 catalog 三零断言（验证器 + grep）

### AC-5: 性能三锚——单次估值 P95<5s + Excel 基准精度误差<0.01% + 并发估值≥10

**Given** ①延迟口径 = **单次全量估值全程**（三方法一次 execute——5 期现金流 + 4 可比 + 3 先例标准载荷；纯 Decimal 计算 ms 级——**5s 门是回归绊线非容量预算**[本地进程口径注记——5-11 AC-5 同款诚实注记形态：纯计算与网络/IO 无关]）②精度口径 = 基准用例相对误差（AC-1/AC-2 已逐例断言——本 AC 汇总锚：基准全集误差最大值 < 0.0001）③并发口径 = **10 路并发估值全成功**（epics L1972「并发估值请求≥10」——**ThreadPoolExecutor 10 线程并发调用 execute**[同步契约配套钦定：execute 是同步纯计算[Task 0.1]，asyncio.gather 不适用同步函数；10 线程同时调用——GIL 下 CPU-bound 实际串行，验证面是**并发调用不互扰 + 全成功 + 结果隔离**，非并行加速——口径注记落 docstring]，每路独立请求实例；**并发安全论证 DC-9**：服务无状态纯计算零共享可变状态，SINGLETON 并发安全）④委托计时三件（常量单源分层：`EXCEL_ALIGNMENT_TOLERANCE = Decimal("0.0001")` **单测文件定义**[Task 3 先建——单测/集成/验收三面共用，委托链 单测→集成 re-export→验收 import 集成]；`FINANCIAL_VALUATION_P95_LIMIT_SECONDS = 5.0` / `FINANCIAL_CONCURRENCY_FLOOR = 10` 集成模块定义[验收 import 禁双真源]；`_PERF_CACHE` 单 key `financial_perf` 载三指标 summary dict；`xdist_group("financial-modeling-perf")` 同 worker 串行——组名与既有 16 组互异）
**When** ①延迟测量（warmup 1 + 20 采样 `statistics.quantiles(latencies, n=20)[18]` exclusive——5-8/5-9/5-10/5-11 同款口径；单次采样 = 构造请求 → execute → 结果返回全程 monotonic 计时；**全同步采样循环**——execute 同步契约配套）②精度汇总（基准 JSON 全用例跑一遍取最大相对误差）③并发（**ThreadPoolExecutor 10 线程** 10 路独立请求 submit + 全部成功断言 + 结果互不串扰[每路用不同 target_ebitda，断言各自结果匹配各自输入——并发隔离锚]）
**Then** ①P95 < 5.0s（epics L1970 钦定）②max_relative_error < Decimal("0.0001")（epics L1971 钦定——与逐例断言双保险汇总面）③10/10 全成功 + 每路结果正确（epics L1972 钦定）
**And** **正向锚**：延迟轮收到计数 == warmup + 采样数（21——防静默跳过假绿）；**零外部服务依赖**（纯计算性能面——集成文件不挂 redis/database marker，验收文件名 financial 不含服务关键词 conftest 自动仅挂 acceptance——**零 skip 场景全部可跑**，与 5-11 的 Redis 探测 skip 形态对比是本 Story 简化面）；**常量等值断言变异锚**（验收步骤含 `== 5.0` / `== "0.0001"` / `== 10` 等值断言——「常量改错值→红」充分条件，5-11 v1.3.0 补注同款）；口径声明落 docstring（进程内口径/绊线定位/20 样本方差知悉/标准载荷定义四注记）

**验证标准/Validation Criteria:**
- [ ] P95<5s：常量单源 + 委托形态 + 20 采样 quantiles[18] 口径 docstring
- [ ] 精度汇总锚：基准全集 max_relative_error < 0.0001
- [ ] 并发 10/10 全成功 + 每路结果匹配各自输入（并发隔离锚）
- [ ] 正向锚 21 + 常量等值断言变异锚
- [ ] xdist 组互异断言（grep——financial-modeling-perf 与 16 组互异）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] **本 Story 零领域事件**（确定性计算服务无事件——cost_calculator/rrf_fusion 先例；event_channels.yaml/ChannelRouter/domain/events 零改动——AC-4 零事件断言面）

#### 数据模型 (Data Models)
- [ ] VO 族定义位于 `src/domain/value_objects/financial_valuation.py`（frozen dataclass + `__post_init__` 242 守卫）：`CashFlow`（period: int≥1 / amount: Decimal）/ `CashFlowSchedule`（items 非空 + period 从 1 严格连续 + **至少一次符号变更**[IRR 可解必要条件]）/ `DcfAssumptions`（discount_rate 0<r<1 + terminal_value_method 二值枚举 + 法配套参数守卫[g≥0 且 g<r / exit_multiple>0 且 terminal_exit_metric>0] + 法-参数互斥配套）/ `DcfValuationResult`（present_values/npv/terminal_value/terminal_value_weight/irr）/ `ComparableCompany`（name 非空 + ev_ebitda>0）/ `ComparableSet`（非空 min 1）/ `MultiplesStats`（min/median/mean/max 四 Decimal）/ `ComparableValuationResult`（multiples_stats + implied_ev_low/median/high）/ `PrecedentTransaction`（target_name 非空 + ev_ebitda>0）/ `PrecedentTransactionSet`（非空）/ `PrecedentValuationResult`（同 Comparable 结果形态）
- [ ] 值对象不可变（frozen——schema_validator.py SchemaValidationResult L158-169 先例）；Decimal 类型注解全程

#### 统一端口定义注册与管理 (Port Contract)
- [ ] `FinancialModelingService` 类即接口（domain/services——debate_evaluator「无状态领域服务类即接口」先例：无独立 Protocol 文件，类自身即接口）
- [ ] 端口注册中心：组合根 `register_port(name="financial_modeling_service", version="v1.0.0", interface=FinancialModelingService, impl="src.domain.services.financial_modeling.FinancialModelingService"[字符串延迟加载], module=..., lifetime=SINGLETON, owner="platform", tags=("financial","valuation","domain-service"))`
- [ ] `register_port(name="financial_modeling_use_case", ...)` interface 绑用例类自身（agent_instantiation_use_case 先例）+ lambda 注入 service
- [ ] 端口契约测试 `tests/contracts/test_port_contract_financial_modeling.py`（11 维度 + REQUIRED_METHODS + service 可达追加维度）
- [ ] R2 组合注入：FinancialModelingUseCase（application）← FinancialModelingService（domain 服务经 resolver 注入——application→domain 合法面）
- [ ] 唯一名称 financial_modeling_service / financial_modeling_use_case（grep 实证零占用）、version v1.0.0、owner platform、SINGLETON（无状态论证 DC-9）

#### 端口契约清单执行约束（强制）
- [ ] 本故事文件「现有代码继承」表是唯一事实源；禁新建估值计算同义端口/服务；未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

- [ ] 归属模块与基类：**financial 子域新段 470-479**（第七段先例——data_source 410/debate 420/tool_version 430/agent 440/evaluation 450/sap 460 六段同款「前段满/语义独立→开独立段」）；`FinancialCalculationError`（EXCEPTION_470，**BusinessException**——计算失败是调用方可处理结果[调整输入/换方法]；直接先例 AgentEvaluationError 450[BusinessException + kwargs context 诊断锚]；与 BusinessRuleViolationError 422 族语义同源[业务约束不可满足]）
- [ ] 唯一编码分配：470（grep `EXCEPTION_47` src/ 零碰撞——创建期已实证 470-998 空闲）；`_code_ranges.py` CODE_RANGES 增 `"financial": (470, 479)` + 段注释（471-479 预留 financial 域）+ `_CLASS_TO_SUBDOMAIN` 增一行
- [ ] 构造器参数：`FinancialCalculationError(method: str, detail: str = "", message: str | None = None, cause: Exception | None = None, context_extra: dict | None = None)`——method 闭集语义 {"dcf", "comparable", "precedent"}（docstring 注明，V1 唯一实际触发 method="dcf"[IRR 求解失败]——comparable/precedent 统计面零失败路径[V1 全集统计无除零/空集合已 VO 拦截]；**method 不做闭集校验**[与 SAPBusStateError reason 闭集校验差异钦定：reason 是协议契约错误面需 fail-loud 拒绝，method 是诊断标注面自由字符串容错更好]）；context 暴露 {"method", "detail"}
- [ ] 消息安全性：错误文案面向调用方（计算语义），零内部实现细节（禁泄露迭代内部量/区间端点值）
- [ ] 编码注册：`_CLASS_TO_SUBDOMAIN` + `sisys-uni-exception-design.md` §3.3.2 编码分配表 + 子域范围表
- [ ] 导出完整性：financial_exceptions.py `__all__` + domain/exceptions/__init__.py 导出（按字母序插入——sap 先例 L125-129）+ EXCEPTION_HTTP_MAP（470→422——BusinessRuleViolationError 422 惯例锚 L168「业务约束不可满足」语义就近映射）
- [ ] 测试覆盖：`tests/unit/domain/exceptions/test_financial_exceptions.py`（构造/属性/to_dict/context 两键/cause 链/frozen 继承链 BusinessException 基类断言）+ `poetry run pytest tests/unit/domain/exceptions/ -v`（8 项自动）+ `test_exception_handlers.py`（expected_types 追加 470 + import 块追加——两处同步）
- [ ] BDD 验收场景：异常路径纳入 Edge Cases（AC-1④ IRR 470 场景——Gherkin 见验收标准）

#### API 契约 (API Contract)
- [ ] **本 Story 零 REST 端点**（OD-6——openapi.yaml 零改动；REST 面 7-2 立项时评估——范围边界表 ❌ 行）

#### 六边形架构约束（必须遵守）
- [ ] 依赖方向：financial_valuation.py + financial_modeling.py（domain）纯标准库零第三方（import-linter domain-no-external-dependencies 既有契约承载——白名单空集验证器 A）；financial_schemas.py + financial_modeling.py 用例（application）依赖 pydantic + src.domain ✓ 合法；infrastructure/interfaces **零触碰**（本 Story 无基础设施实现——计算纯进程内）
- [ ] 领域层零依赖：financial VO/服务/异常纯标准库（decimal/math/statistics/dataclasses/typing）

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] `tests/acceptance/test_acceptance_financial_modeling.feature`（13 场景：AC-1×3 + AC-2×3 + AC-3×2 + AC-4×2 + AC-5×2 + 收尾×1——R6 现代形态：`# language: zh-CN` + AC 横幅分节注释 + `场景: AC-x.y - 描述` 前缀命名）
- [ ] `tests/acceptance/test_acceptance_financial_modeling.py`（三属性分档 docstring + @scenario 字面量绑定 + **context dict fixture 单件**[**全同步交付面注记**：本 Story execute/引擎全同步[Task 0.1 钦定]，R6 改造三件套中 event_loop/_run_async 两件**不适用纯同步步骤**——省略不引入（5-9~5-11 三件套是 async 服务面；context dict 照抄）；**禁 @pytest.mark.asyncio 红线仍然全效**——零 async 步骤即零违例面] + 延迟 import 纪律[本 Story 新交付模块一律步骤函数体内 import——Task 0-5 窗口期运行期 ModuleNotFoundError 逐场景 failed 非 collection error]；**零外部服务探测零 skip**——纯计算全场景可跑）
- [ ] Happy Path + Edge Cases 全覆盖（242 三类 + 470 IRR + pydantic 六类异常路径入场景）

**BDD 步骤实现约束：**
- 步骤函数**全同步直调**（本 Story 零 async 面——execute/引擎/性能采样全同步；`event_loop.run_until_complete()` 三件套不适用不引入；禁 `@pytest.mark.asyncio` 红线仍然全效——零 async 步骤即零违例面）
- 同一中文文本双装饰器支持（given/when 复用）
- Edge Cases 含异常路径（242/470/pydantic ValidationError 三层异常三段式断言——raises 形态[嵌入式组件无 HTTP 面]）

#### Task 0 完成标志：
- [ ] 规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——逐场景 failed 非 collection error；红因核对：ModuleNotFoundError[缺生产模块]；全部步骤函数必须 Task 0 就位——5-11 Subtask 0.5 红因核对口径）
- [ ] **链路接线断言清单**已定义：①组合根 register_port 两端口装配验证（resolve 可达 + 注入链——AC-4）②**零事件发布面**（计算服务无事件——「已实现未接线」检查不适用，注记与 5-11 同款）③**零中间件面**；消费方接线（CFO Agent/BLM/REST）在范围边界表显式登记非「未接线遗留」

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🟡 变异** | 对新行为契约的断言做突变注入-还原实证（Epic 4 回顾行动项 7.1-2） | 改坏生产代码 → 测试红 → 还原 → 绿（证明断言活着） |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试 / 测试集中最后 Task / 跳过红阶段 / 跳过变异实证
- ❌ **浮点 approx / 断言放空（本 Story 红线强化——OD-5③：全部数值断言 Decimal 域相对误差或精确相等，pytest.approx 零引入——变异锚的充分性由相对误差比较承载）**
- ❌ float 中转构造 Decimal（`Decimal(0.1)` 禁——一律 `Decimal("0.1")` 字符串构造；ruff/mypy 无此 lint，靠测试断言精确性反向守护 + 评审自查）

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| TDD 单元测试 | financial 异常族 | 470 构造/属性/to_dict/context/cause 链/BusinessException 继承 | `tests/unit/domain/exceptions/test_financial_exceptions.py` | Task 1 |
| TDD 单元测试 | VO 族 | 11 类 VO 构造/不变量守卫 242/冻结性/Decimal 注解 | `tests/unit/domain/value_objects/test_financial_valuation.py` | Task 2 |
| TDD 单元测试 | DCF 引擎 | NPV/终值两法/IRR/Excel 基准对齐/bracket 失败 470 | `tests/unit/domain/services/test_financial_modeling.py`（第一/二批） | Task 3 |
| TDD 单元测试 | 可比+先例引擎 | 统计四值/隐含区间/偶数 median/异常 | 同上文件（第三批） | Task 4 |
| TDD 单元测试 | 应用层 Schema | 三段请求/字符串数字/六类非法/跨字段校验器 | `tests/unit/application/use_cases/test_financial_modeling_use_case.py`（Schema 用例类） | Task 5 |
| TDD 单元测试 | 估值用例 | 编排零变换/fail-loud/部分请求跳过 | 同上文件（用例用例类） | Task 5 |
| TDD 契约测试 | use_case 端口 | 11 维度 + REQUIRED_METHODS + service 可达 | `tests/contracts/test_port_contract_financial_modeling.py` | Task 5 |
| TDD 验收测试 | Gherkin 场景 | 业务价值验收（13 场景） | `test_acceptance_financial_modeling.feature` | Task 0 |
| TDD 验收测试 | BDD 步骤实现 | 步骤函数 + 真实服务场景 | `test_acceptance_financial_modeling.py` | Task 0 |
| TDD 验收测试 | 收尾验收场景 | src 与测试目录完成清单确认 | 同上两文件 | Task 7 |
| SDD 架构验证 | 六边形架构 | 白名单空集/零实例化/Decimal 锚/三零/零抑制 | `tests/unit/architecture/test_arch_financial_modeling.py` | Task 6 |
| 集成测试 | 性能三锚 | P95<5s + 精度汇总 + 并发 10 | `tests/integration/test_integration_financial_modeling.py` | Task 6 |
| 存量追加 | 异常 HTTP 映射 | expected_types 穷举等值 | `tests/unit/interfaces/api/test_exception_handlers.py` | Task 1 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（CI 门禁）- P0
- [ ] **domain 层 ≥90%**（OD-4——主交付面：三引擎+VO+异常测试族全覆盖承载）- P1
- [ ] **application 层 ≥85%**（epics L1975 原文——Schema+用例）- P1（两段式命令：`poetry run pytest tests/unit/ --cov=src -q && poetry run coverage report --include="src/domain/*" --fail-under=90` 同款分母陷阱注记——Makefile L278-282 / 5-11 OD-2 同款）
- [ ] **集成测试覆盖交付行为**（≥75% 口径——性能三锚 + 精度汇总承载）
- [ ] **关键路径 100%**（DCF 两终值法/IRR 两路径[收敛+bracket 失败]/统计引擎/VO 守卫全分支/用例编排三路径[全量/部分/fail-loud]）

#### 代码质量门禁
- [ ] `poetry run ruff check src/ tests/` 通过
- [ ] `poetry run mypy .`（**全仓含 tests/**——5-9 Task 6.4 漏 tests 面 ×9 教训）
- [ ] `pre-commit run --all-files` 通过
- [ ] 零抑制注释（noqa/type: ignore/pylint: disable——红线 grep 自查：本 Story 新文件零命中）

#### 测试隔离约束（本 Story 特化）

| 约束类型 | 规则 |
|---------|------|
| 纯计算零外部服务 | 全部测试零 Redis/PG/LLM/Docker 依赖——零 pytest.skip 场景（与 5-11 Redis 探测 skip 形态对比是本 Story 简化面；CI 无外部服务环境全绿） |
| 无状态服务 | SINGLETON 服务可安全共享实例（测试直接构造即可）；并发场景 10 路独立请求实例（互不串扰锚——每路异 target_ebitda 断言各自结果） |
| 基准 JSON 只读 | `financial_test_cases.json` 测试内 `json.load` 只读（禁修改回写）；dev 环境零写入 |
| Decimal 构造纪律 | 全部 `Decimal("...")` 字符串构造（禁 float 构造——OD-5）；基准 JSON 数字字段全字符串 |
| BDD 全同步 | 零 async 步骤（execute 同步直调）；禁 `@pytest.mark.asyncio` 红线全效（零 async 即零违例面）；event_loop/_run_async 不适用不引入 |
| 性能委托 | `_PERF_CACHE` + xdist_group 逐字同组（集成/验收两文件）；「命中或首次采样」禁先跑断言 |
| 验收禁 mock | 手写零 IO duck-typing 替身（`_StubModelingService`）；真实服务场景（引擎真算）不可跳过 |

**验证要求：**
- [ ] `poetry run pytest tests/ -n 8` 通过（并行隔离）
- [ ] 连续 5 次运行无随机失败（financial 测试族 5 连发）
- [ ] ruff + mypy 全仓通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | DCF NPV+终值两法 Excel 对齐 | Task 3 | 3.1-3.2 | test_financial_modeling.py + 验收 AC-1.1 |
| AC-1 | IRR 对齐 + bracket 失败 470 | Task 3 | 3.1-3.3 | 同上 + 验收 AC-1.2/1.3 |
| AC-1 | VO 守卫（符号变更/g≥r → 242） | Task 2 | 2.1-2.2 | test_financial_valuation.py + 验收 AC-1.3 |
| AC-2 | 可比统计+隐含区间 | Task 4 | 4.1-4.2 | test_financial_modeling.py + 验收 AC-2.1 |
| AC-2 | 先例统计+参考区间 | Task 4 | 4.1-4.2 | 同上 + 验收 AC-2.2 |
| AC-2 | 空集合/非正倍数 242 | Task 2/4 | 2.2/4.1 | test_financial_valuation.py + 验收 AC-2.3 |
| AC-3 | 三段 Schema 合法构造+精确解析 | Task 5 | 5.1 | Schema 用例类 + 验收 AC-3.1 |
| AC-3 | 六类非法 pydantic 拒绝 + wire 契约 | Task 5 | 5.1 | 同上 + 验收 AC-3.2 |
| AC-4 | 组合根两注册+注入链+契约 11 维度 | Task 5 | 5.2-5.3 | test_port_contract + 验收 AC-4.1 |
| AC-4 | 编排零变换 + fail-loud + 架构四验证器 | Task 5/6 | 5.2/6.1-6.3 | 用例测试 + test_arch + 验收 AC-4.2 |
| AC-5 | P95<5s + 精度汇总锚 | Task 6 | 6.1-6.2 | 集成 + 验收 AC-5.1 |
| AC-5 | 并发 10/10 + 隔离锚 + xdist 互异 | Task 6 | 6.1-6.3 | 集成 + 验收 AC-5.2 |
| 收尾 | 完成清单逐项确认 | Task 7 | 7.1-7.4 | 验收收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-5（Gherkin 全场景）

> **目的：** 在进入代码实现前，明确 VO 契约、引擎签名、异常契约、Schema 契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 定义 VO 契约规范（11 类 frozen dataclass 清单与守卫不变量——见「数据模型」节；`FinancialModelingService` 三方法签名钦定：`calculate_dcf(schedule: CashFlowSchedule, assumptions: DcfAssumptions) -> DcfValuationResult` / `calculate_comparable_valuation(comparables: ComparableSet, target_ebitda: Decimal) -> ComparableValuationResult` / `calculate_precedent_valuation(transactions: PrecedentTransactionSet, target_ebitda: Decimal) -> PrecedentValuationResult`——全部同步方法[纯计算无 IO，async 无谓开销；用例层 execute 亦同步——**与既有用例 async execute 形态差异钦定**：agent_instantiation 等是 IO 编排故 async，本 Story 纯计算同步即契约；若 Epic 6 消费面需 await 包装由消费方 `asyncio.to_thread` 或直接同步调用]）
- [ ] Subtask 0.2: 定义领域异常契约（FinancialCalculationError 470——method/detail 构造 + HTTP 422）
- [ ] Subtask 0.3: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_financial_modeling.feature`（13 场景：AC-1×3[NPV+终值对齐 / IRR 对齐 / DCF 异常路径] + AC-2×3[可比统计 / 先例区间 / 集合异常] + AC-3×2[合法构造 / 非法拒绝] + AC-4×2[组合根接线 / 架构合规] + AC-5×2[延迟+精度 / 并发] + 收尾×1）
- [ ] Subtask 0.4: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_financial_modeling.py`（三属性分档 docstring + @scenario 绑定 + **context dict fixture 单件**[全同步交付面——event_loop/_run_async 不适用省略，注记同「验收标准 Gherkin」节] + **延迟 import 钦定**：模块顶部仅 stdlib+pytest+pytest_bdd；本 Story 新交付模块[VO/引擎/异常/Schema/用例/集成常量]一律步骤函数体内 import + **零服务探测零 skip**——纯计算全场景可跑）
- [ ] Subtask 0.5: 运行验收测试，确认失败（🔴 红阶段验证——预期红因 ModuleNotFoundError[缺生产模块]；全部步骤函数必须 Task 0 就位——pytest-bdd 8.1.0 StepDefinitionNotFoundError 非预期红——5-11 Subtask 0.5 口径）
- [ ] Subtask 0.6: 定义链路接线断言清单（三件——Task 0 完成标志项：两端口 resolve 装配 / 零事件面注记 / 零中间件面注记 + 消费方接线在范围边界表登记）
- [ ] Subtask 0.7: 定义 Excel 基准用例集骨架 `tests/unit/domain/services/financial_test_cases.json`（OD-7 落位——三数组 dcf_cases/comparable_cases/precedent_cases 的 JSON Schema 骨架 + 首条样例用例[dev 期以 Excel 逐例核验后填充全量——**基准值固化纪律**：expected 值必须可复算[docstring 注明 Excel 公式形态]，禁拍脑袋值；建议 dcf≥3[两终值法各≥1+常规 1]/comparable≥2[奇偶样本各 1]/precedent≥2]）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认——13 场景逐场景 failed 非 collection error）
- [ ] 基准 JSON 骨架就位（首条样例可跑通红流程）

---

### Task 1: FinancialCalculationError（470）+ 注册四件套

**关联 AC:** AC-1（IRR 470）/ AC-4（异常注册面）

#### TDD 循环 A：financial_exceptions.py 单异常

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_financial_exceptions.py`（构造/属性/code=="EXCEPTION_470"/to_dict/context dict[method+detail 两键]/cause 链/frozen 继承链[BusinessException 基类断言]/message 缺省回落类属性文案） |
| 🟢 绿 | 实现 `src/domain/exceptions/financial_exceptions.py`（evaluation_exceptions.py 构造风格模板：领域参数在前 + `message: str \| None = None` 缺省回落 + `cause: Exception \| None = None` + context_extra 合并；模块 docstring 含开段论证[470-479 第七段——前段语义独立]） |
| 🟡 变异 | context method 键删 → to_dict 断言红 → 还原 |
| 🔄 重构 | 注册三动作：`_code_ranges.py`（CODE_RANGES `"financial": (470, 479)` + 段注释[471-479 预留] + `_CLASS_TO_SUBDOMAIN` 一行）+ `domain/exceptions/__init__.py` 导出（按字母序插入）+ `exception_handlers.py` EXCEPTION_HTTP_MAP 一行（470→422——行尾 `# 470 — 财务计算失败（业务约束不可满足）` 注释 + 精确注册措辞）+ `sisys-uni-exception-design.md` §3.3.2 两处更新 + `test_exception_handlers.py` **两处同步**（expected_types 追加 470 + import 块追加——5-11 Task 1「两处同步」教训） |

- [ ] Subtask 1.1: 🔴 红 — 异常失败测试
- [ ] Subtask 1.2: 🟢 绿 — financial_exceptions.py 实现
- [ ] Subtask 1.3: 🟡🔄 变异实证 + 注册四件套 + 文档联动

**完成标准/Definition of Done:**
- [ ] `poetry run pytest tests/unit/domain/exceptions/ tests/unit/interfaces/api/test_exception_handlers.py -v` 全绿（含自动 8 项）
- [ ] grep `EXCEPTION_470` src/ 仅注册三件命中（零碰撞）

---

### Task 2: 财务估值值对象族——11 类 frozen dataclass + 242 守卫

**关联 AC:** AC-1（VO 守卫）/ AC-2（集合守卫）

#### TDD 循环 A：VO 族

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_financial_valuation.py`（11 类构造成功路径 + 守卫失败路径参数化：CashFlowSchedule 空集合/period 非连续/period 重复/无符号变更[全正+全负两形态] → 242 context.field="cash_flows"；DcfAssumptions r≤0/r≥1/perpetual 法缺 g/g<0/**g≥r**/exit 法缺 exit_multiple/exit_multiple≤0/terminal_exit_metric≤0/法-参数互斥[perpetual 带 exit 字段] → 242；ComparableSet 空/成员 ev_ebitda≤0/name 空 → 242；PrecedentTransactionSet 同构参数化；结果类 6 个构造+frozen 断言[赋值抛 FrozenInstanceError]） |
| 🟢 绿 | 实现 `src/domain/value_objects/financial_valuation.py`（11 类 frozen dataclass + `__post_init__` 守卫统一 raise `EntityValidationError` 携 `context={"entity": 类名, "field": 字段名}`——sap reason 闭集拒绝先例 context 形态；`DcfAssumptions` 跨字段守卫在 `__post_init__` 内[构造期静态可判定钦定——法配套互斥用「非本法参数须 None」检查]） |
| 🟡 变异 | 符号变更守卫删 → 全正现金流用例红；g<r 守卫反转 → g≥r 用例红；frozen 去掉 → 赋值断言红 → 还原 |
| 🔄 重构 | docstring（每类业务语义[现金流表/终值两法假设/倍数集合] + Decimal 注解纪律注解）+ ruff/mypy |

- [ ] Subtask 2.1: 🔴 红 — VO 族失败测试
- [ ] Subtask 2.2: 🟢 绿 — financial_valuation.py 实现
- [ ] Subtask 2.3: 🟡🔄 变异实证（三锚：符号变更/g 守卫/frozen）+ 重构

**完成标准/Definition of Done:**
- [ ] 11 类 VO 全绿（守卫参数化全过 + frozen 断言）
- [ ] 覆盖率：VO 文件分支 100%（全守卫分支覆盖）

---

### Task 3: DCF 引擎——NPV + 终值两法 + IRR 二分法 + Excel 基准对齐

**关联 AC:** AC-1（全部）

#### TDD 循环 A：NPV + 终值两法

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_financial_modeling.py` 第一批（**模块级常量 `EXCEL_ALIGNMENT_TOLERANCE = Decimal("0.0001")` 在本文件定义**——容差单源[AC-5 Given④ 分层钦定：单测是源，集成 re-export，验收 import 集成]；TestDcfNpv：基准 JSON `dcf_cases` 逐例——npv/terminal_value 相对误差断言 + present_values 逐期现值独立断言 + **NPV 分解自洽锚**[npv == ΣPV + TV/(1+r)^n 精确相等——AC-1①]；**本批不断言 irr**[循环 A 绿阶段 _solve_irr 是占位 0——循环 B 红批次补 IRR 断言]；两终值法各≥1 例参数化；`localcontext prec=50` 口径下 Decimal 精确性锚[str→Decimal→引擎→str 回读比较]）——**红形态注记**：顶部 import 不存在的 financial_modeling → collection error 形态的红合法[TDD 单元红非验收面——5-11 Task 2 同款注记] |
| 🟢 绿 | 实现 `src/domain/services/financial_modeling.py`（`FinancialModelingService.calculate_dcf`：`localcontext` prec=50 → 逐期 PV_t = CF_t/(1+r)^t → 终值[perpetual: CF_n×(1+g)/(r−g)——r−g 分母；exit: exit_multiple×terminal_exit_metric] → npv = Σ PV + TV/(1+r)^n → weight[PV(TV)/npv] → **`_solve_irr` 占位返回 `Decimal("0")`**[循环 B 兑现真实现——**占位值钦定非 NotImplementedError**：calculate_dcf 单方法一次返回全字段，循环 A 用例虽不断言 irr 但调用必经 IRR 路径，raise 会使 npv 断言误红——占位 0 值零干扰，循环 B 红批次加 irr 断言后替换]；全 Decimal 算术零 float） |
| 🟡 变异 | 贴现公式 (1+r)^t 改 (1+r)^(t−1)[期初口径] → 基准用例红[口径漂移锚]；终值不折现[漏 /(1+r)^n] → npv 断言红；prec 降 10 → 长序列用例红[精度锚——若基准不敏感则构造 10 期大额用例使 28 位截断可观测] → 还原 |
| 🔄 重构 | docstring（年末贴现口径/两终值公式/prec=50 理由/Excel NPV 函数对齐注记——四钦定落文字）+ ruff/mypy |

#### TDD 循环 B：IRR 二分法

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 第二批（TestDcfIrr：基准逐例 irr 相对误差断言；bracket 失败病态序列[如 (−100, 230, −132)——NPV(−0.99) 与 NPV(10) 同号] → FinancialCalculationError 470 三段式[raises + code + context.method=="dcf"]；收敛性锚——构造已知 IRR 用例[如 (−100, 110) → IRR=0.1 精确解]验证迭代收敛到容差内；**迭代次数上界断言**——max_iterations=256 违例路径经 monkeypatch 构造超浅收敛区间用例或直接断言常量） |
| 🟢 绿 | `_solve_irr(schedule, discount_rate)` 私有方法（bracket 检查[NPV(r_lo)×NPV(r_hi) < 0 否则 470 method="dcf" detail 描述 bracket 失败] → 二分循环[区间宽度 < Decimal("1e-12") 或 NPV 中点近零收敛] → 256 次上限防御[超限 470——理论 bracket 下二分必收敛，防御分支经 monkeypatch 常量触发测试]；r_lo=Decimal("-0.99")/r_hi=Decimal("10") 模块常量） |
| 🟡 变异 | bracket 检查删 → 病态用例红[返回错值或死循环被 pytest-timeout 拦]；收敛判据放宽 0.1 → 精度断言红；470 改 return None → raises 断言红 → 还原 |
| 🔄 重构 | docstring（二分法选型论证[DC-4：bracket 下必然收敛可证——牛顿法发散风险]/Excel IRR #NUM! 语义对齐/符号变更必要条件与 VO 守卫分工）+ ruff/mypy |

- [ ] Subtask 3.1: 🔴 红 — NPV/终值失败测试（第一批）
- [ ] Subtask 3.2: 🟢 绿 — calculate_dcf 实现
- [ ] Subtask 3.3: 🔴🟢 IRR 红绿（第二批 + _solve_irr）
- [ ] Subtask 3.4: 🟡🔄 变异实证（三锚：贴现公式/bracket/收敛判据）+ 重构（docstring 四钦定）

**完成标准/Definition of Done:**
- [ ] DCF 基准用例全绿（N/N——含两终值法各≥1 例 + IRR 全例）
- [ ] 470 bracket 路径三段式 + 收敛锚全绿
- [ ] 覆盖率：calculate_dcf + _solve_irr 分支 100%（两终值法/IRR 收敛/bracket 失败/迭代上限防御）

---

### Task 4: 可比公司与先例交易引擎——倍数统计 + 隐含区间

**关联 AC:** AC-2（全部）

#### TDD 循环 A：统计引擎（两方法）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 第三批（TestComparableValuation：基准 `comparable_cases` 逐例——multiples_stats 四值相对误差 + implied_ev 三值**精确相等**断言[同源 Decimal 乘法] + 偶数样本 median 语义[≥4 家可比用例]；TestPrecedentValuation：基准 `precedent_cases` 同构断言；统计语义锚——min/median/mean/max 与手算 Decimal 对照[statistics.mean/median Decimal 原生]） |
| 🟢 绿 | `calculate_comparable_valuation` + `calculate_precedent_valuation`（共享私有 `_multiple_stats(values: tuple[Decimal, ...]) -> MultiplesStats`——statistics.mean/median/min/max 四值 Decimal 域；implied = stat × target_ebitda 乘法） |
| 🟡 变异 | median 改取下中位 → 偶数样本用例红；implied_high 用 min × target → 区间断言红[顺序锚]；_multiple_stats 供两引擎共享改单引擎私有 → 另一引擎用例红 → 还原 |
| 🔄 重构 | docstring（两方法语义分立注记[交易市场倍数 vs 交易对价倍数] + V1 全集统计口径[无剔除/细分] + V2 知悉[龙卷风图/剔除加权归 V2——prd L528]）+ ruff/mypy |

- [ ] Subtask 4.1: 🔴 红 — 两引擎失败测试（第三批）
- [ ] Subtask 4.2: 🟢 绿 — 两方法实现 + _multiple_stats
- [ ] Subtask 4.3: 🟡🔄 变异实证（三锚：median 语义/区间顺序/共享 helper）+ 重构

**完成标准/Definition of Done:**
- [ ] 可比/先例基准用例全绿（统计四值 + 区间三值 + 偶数 median）
- [ ] 覆盖率：两方法分支 100%（含空集合防御路径——VO 拦截后引擎不重复守卫[单层守卫钦定]，统计主路径全覆盖）

---

### Task 5: 应用层 Schema + 估值用例 + 组合根注册 + 契约测试

**关联 AC:** AC-3（全部）/ AC-4（接线与编排面）

#### TDD 循环 A：financial_schemas.py 三段请求族

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/use_cases/test_financial_modeling_use_case.py` 第一批（TestFinancialSchemas：合法全量构造 + `Decimal 字段 == Decimal("0.1")` 精确相等[str→Decimal 零损失锚] + 部分请求[单段] + 非法六类 pydantic.ValidationError 参数化[负折现率/折现率≥1/g≥r/空现金流/空可比/三段全 None] + 法-参数配套校验[perpetual 带 exit 字段拒绝/exit 缺 exit_multiple 拒绝]) |
| 🟢 绿 | 实现 `src/application/services/financial_schemas.py`（文件头层归属注记[summary_schemas.py L8-12 同款] + wire 契约注记[字符串数字] + 三段 Schema 族[Field gt/lt/min_length + `model_validator(mode="after")` 跨字段守卫]） |
| 🟡 变异 | g<r 校验器删 → g≥r 用例红；min_length 删 → 空可比用例红 → 还原 |
| 🔄 重构 | docstring（三层异常语义分立注记[pydantic/242/470] + Schema-VO 镜像冗余论证[防御纵深]）+ ruff/mypy |

#### TDD 循环 B：FinancialModelingUseCase + to_value_objects + 组合根 + 契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 第二批（TestFinancialModelingUseCase：`_StubModelingService` duck-typing 替身捕获三方法调用——全量请求三方法各被调一次 + 参数与 VO 转换结果一致[to_value_objects 零变换锚] + 部分请求跳过 None 段[仅 DCF 段 → 只 calculate_dcf 被调] + fail-loud[stub 抛 470 → execute 上抛同异常三段式] + stub 返回预置结果时 DTO 三段组装逐字段断言[编排零变换——stub 返回什么 DTO 就装什么]；**真实服务对照用例**——用例注入真实 FinancialModelingService，同输入下 execute 结果三段与直接调真实服务三方法结果逐一相等[真实链零变换总锚]）+ `tests/contracts/test_port_contract_financial_modeling.py`（11 维度 + REQUIRED_METHODS=["execute"] + _DummyResolver 分发 service 替身 + service resolve 可达追加维度） |
| 🟢 绿 | 实现 `src/application/use_cases/financial_modeling.py`（`FinancialValuationResult` frozen DTO 就地定义[三段结果 Optional 字段——None=该方法未请求] + `to_value_objects(request)` 模块级转换函数 + `FinancialModelingUseCase(service: FinancialModelingService)` 构造注入 + `execute(request: FinancialValuationRequest) -> FinancialValuationResult`——转换 → 按段分派服务方法 → 组装 DTO；470 零捕获上抛）；composition_root.py `# === Story 5.12 ===` 区段（决策记录式长注释[SINGLETON 无状态论证 DC-9 + 字符串 impl 先例引据 + interface 绑自身先例引据] + 两 register_port） |
| 🟡 变异 | 分派删一段[DCF 段跳过] → 全量请求用例红[三方法各被调锚]；try/except 470 吞掉 → fail-loud 用例红[5-11 OD-7 fail-loud 哲明的变异面]；PortSpec tags 改错 → 契约断言红 → 还原 |
| 🔄 重构 | docstring（编排职责边界[零业务逻辑纯分派] + fail-loud 论证 + 三层异常分工重申）+ ruff/mypy |

- [ ] Subtask 5.1: 🔴 红 — Schema 失败测试（第一批）
- [ ] Subtask 5.2: 🟢 绿 — financial_schemas.py 实现
- [ ] Subtask 5.3: 🔴🟢 用例+注册+契约测试红绿（第二批）
- [ ] Subtask 5.4: 🟡🔄 变异实证（三锚：分派完整性/fail-loud/契约 tags）+ 重构

**完成标准/Definition of Done:**
- [ ] Schema 六类非法 + 配套校验全绿 + 精确解析锚全绿
- [ ] 用例编排三路径（全量/部分/fail-loud）+ 契约 11 维度全绿
- [ ] resolve 两端口可达 + 注入链断言（验收 AC-4.1 转绿）
- [ ] application 层覆盖率 ≥85%（两段式命令复核）

---

### Task 6: 集成性能三锚 + SDD 架构约束验证测试

**关联 AC:** AC-5（全部）/ AC-4（架构合规面）

> **套件型豁免条款（5-9/5-10/5-11 先例）**：本 Task 是验证型测试套件（对 Task 1-5 已交付行为做计时与架构验证）——首跑即绿，红阶段由 Task 0 验收红前置承担；断言活性由变异实证承担（Subtask 6.3 变异锚：常量单源改错值 → 验收 import 消费断言红）。

#### 集成与性能实现

- [ ] Subtask 6.1: `tests/integration/test_integration_financial_modeling.py`——文件级 `pytestmark = [pytest.mark.integration, pytest.mark.xdist_group("financial-modeling-perf")]`（**不挂任何服务 marker——纯计算零外部依赖**）；常量：`FINANCIAL_VALUATION_P95_LIMIT_SECONDS = 5.0` / `FINANCIAL_CONCURRENCY_FLOOR = 10` 集成定义（注释「单源定义——验收侧 import 本常量断言，禁双真源」）+ `from tests.unit.domain.services.test_financial_modeling import EXCEL_ALIGNMENT_TOLERANCE` **re-export**（容差单源在单测文件——AC-5 Given④ 分层钦定，集成/验收经此链取值禁双真源）；`_PERF_CACHE` 单 key `financial_perf` 载三指标 summary dict + cache-or-compute helper `sample_financial_perf()`（**全同步 helper**——标准载荷 = 5 期现金流 + 4 可比 + 3 先例全量请求；warmup 1 + 20 采样 `quantiles(latencies, n=20)[18]` exclusive 口径 docstring；精度汇总 = 基准 JSON 全用例 max_relative_error；并发 = **ThreadPoolExecutor 10 线程** 10 路独立请求全成功 + 每路异 target_ebitda 各自结果匹配[并发隔离锚——GIL 串行知悉注记落 docstring]）
- [ ] Subtask 6.2: 创建 `tests/unit/architecture/test_arch_financial_modeling.py`——验证器 A：domain 两文件第三方 import 白名单**空集**（forbidden ∩ modules == ∅——decimal/math/statistics/dataclasses/typing 标准库天然过）；验证器 B：组合根外零实例化（`FinancialModelingService(`/`FinancialModelingUseCase(` 构造点 grep——仅 composition_root.py + tests/）+ financial_exceptions.py 仅在异常注册三件内 + **三零断言**（event_channels.yaml/ChannelRouter/domain/events 零 financial 条目 + openapi.yaml 零 financial 路径 + strategic_tool_catalog.py/skill_manifest.py/skills/ 零触碰——OD-3/OD-6 契约承载）；验证器 C：Decimal 静态锚（两 domain 文件 `from decimal import` 存在 + calculate_dcf 签名含 Decimal 注解——AST/grep 双形态）+ VO frozen 锚（11 类 `@dataclass(frozen=True)`）；验证器 D：零抑制注释（交付文件五件 noqa/type: ignore/pylint: disable 零命中）+ 循环依赖检测用 ruff/isort 既有钩子（不引入新工具）
- [ ] Subtask 6.3: 变异锚实证（常量单源改错值 → 验收 import 消费断言红 → 还原）+ 全仓 xdist 组 grep 断言（financial-modeling-perf 与 16 组互异——expected_existing 子集断言 + 新组 in）
- [ ] Subtask 6.4: 口径声明落 docstring（进程内绊线定位/20 样本方差知悉/标准载荷定义/精度汇总口径四注记）+ 验证 AC-5.* 场景绿（委托计时消费确认 import 集成常量与 helper 禁双真源）+ `poetry run mypy .` 全仓（含 tests/——5-9 教训）

**完成标准/Definition of Done:**
- [ ] 三锚达标 + 正向锚 21 + 变异锚（P95 ms 级大裕量 + max_error 汇总 + 10/10）
- [ ] 架构验证器 A/B/C/D 全绿 + 活性实证（注入 noqa → 红 → 还原 → 绿）
- [ ] xdist 组互异断言 + mypy 全仓零错 + ruff 全清

---

### Task 7: 开发结束验收测试

**关联 AC:** 全 AC 收尾

> **性质说明：** 对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | feature 收尾场景（完成清单逐项——src 六件 + tests 十件存在性） |
| 🟢 绿 | py 步骤实现（文件存在性 + 关键符号断言） |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 7.1: 场景 1 — 验证 `src` 完成清单（financial_valuation.py / financial_modeling.py / financial_exceptions.py / financial_schemas.py / use_cases/financial_modeling.py / 组合根区段两注册——关键符号可导入 + EXCEPTION_470 断言）
- [ ] Subtask 7.2: 场景 2 — 验证 `tests` 完成清单（unit 五件 + contracts 一件 + integration 一件 + architecture 一件 + acceptance 两件 + exception_handlers 追加——十件存在性断言）
- [ ] Subtask 7.3: 运行开发结束验收测试确认通过 + 全量 `poetry run pytest tests/ -n 8` 并行绿 + financial 测试族 5 连发零随机失败
- [ ] Subtask 7.4: `poetry run ruff check src/ tests/` + `poetry run mypy .` 收尾校验 + 零抑制 grep 三连（noqa/type: ignore/pylint: disable）+ 禁 AI 署名 grep

**完成标准/Definition of Done:**
- [ ] 完成清单逐项验证确认
- [ ] 全量测试 + 质量门禁全绿
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md) + [`sisys-uni-exception-design.md`](../../../docs/architecture/sisys-uni-exception-design.md)

- **架构模式:** 六边形架构；财务估值是**领域层确定性计算服务**（R1：领域层统一抽象——计算引擎纯标准库 Decimal；无基础设施实现[纯进程内计算零技术适配]——本 Story 无 infrastructure 触碰面）；R2：用例（application）组合注入领域服务（resolver → domain 服务）
- **设计约束:** 领域层零依赖（import-linter domain-no-external-dependencies——decimal/math/statistics 均标准库合规）；组合根唯一注册（两端口）；类即接口注册先例（debate_evaluator——字符串 impl SINGLETON）；**零事件/零 REST/零 catalog 三零边界**（OD-2/OD-3/OD-6）
- **接口治理:** PortSpec 元数据（financial_modeling_service v1.0.0 SINGLETON owner=platform / financial_modeling_use_case v1.0.0 SINGLETON owner=platform + lambda 注入链）；接口稳定性：V1 端口契约是 CFO Agent/BLM/REST 消费面（Epic 6/9/7-2）的稳定基座——演进走 contract_gate
- **技术栈:** Python 3.11+ 标准库（decimal/math/statistics/dataclasses）+ pydantic v2（应用层 Schema）——**零新运行时依赖**（5.7 OD-1 家族原则第六 Story 延续；pyproject 无 scipy、numpy 仅传递依赖且 domain 禁用）

### 关键架构决策 Key Design Decisions

| # | 决策 | 理由 | 备选（弃） |
|---|------|------|-----------|
| DC-1 | 确定性计算落 domain 纯标准库（OD-2） | 「100% 与 Excel 对齐 + 禁浮点误差」与 LLM 生成代码根本矛盾；DCF/倍数法是标准金融数学零 LLM 自由度；零新依赖 | 走工具执行链 LLM Think/Code+沙箱（弃——输出不可复现）；application 层计算（弃——估值数学是领域知识非编排，R1 领域层承载） |
| DC-2 | 单类三方法 `FinancialModelingService` + 类即接口注册 | 聚合「财务建模」域服务语义（三方法共享 _multiple_stats/_solve_irr 私有 helper）；debate_evaluator 无状态领域服务注册三件套先例逐字照抄；无独立 Protocol 文件（domain 服务类即接口仓内先例——rrf_fusion/cost_calculator/debate_evaluator 全族无 Protocol） | 三类三文件（弃——共享 helper 跨文件私有化尴尬）；Protocol+实现分离（弃——无多实现预期[V1 单进程纯计算]，YAGNI） |
| DC-3 | Decimal 全程 + 字符串数字 wire 契约 + 相对误差断言（OD-5） | epics L1981「禁止浮点误差」红线；JSON number→float→Decimal 二进制污染链唯一规避 = str 入口；Excel 基准本身 double——0.01% 相对误差是诚实口径（精确相等不可达非必要）；statistics.mean/median 原生 Decimal 支持 | float+pytest.approx（弃——仓内 66 处惯例与本 Story 红线冲突，显式差异声明）；numpy/scipy（弃——domain 禁用 + 新依赖） |
| DC-4 | IRR 二分法 + bracket 前提 + 242/470 分层 | bracket[NPV 端点异号]下二分必然收敛（数学可证——迭代减半区间）；牛顿法发散风险（导数近零区域）；VO 拦静态必要条件[符号变更 242]、引擎拦数值求解失败[bracket 470]——两层语义分立各司其职；Excel `#NUM!` 语义对齐（错误而非 None） | 牛顿法（弃——发散+导数实现复杂）；返回 None（弃——静默缺值违背 fail-loud；Excel 语义是错误） |
| DC-5 | 年末贴现 + 终值两法（Excel NPV 口径） | Excel `NPV(rate, range)` 是年末惯例（t=1..n）——对齐基准的唯一口径；永续增长/退出倍数是投行标准两法（prd L492/L528 语义承载）；期初口径/XNPV 归 V2+（知悉注记） | 期初口径（弃——与 Excel NPV 基准不齐） |
| DC-6 | pydantic Schema 落应用层 + to_value_objects 用例内转换 | summary_schemas.py L8-12 层归属决策先例（领域零 pydantic）；Schema 是外部契约面/VO 是领域不变量面——双层守卫防御纵深（Schema 拦外部输入可读性好，VO 独立守卫防绕过）；转换函数在用例文件（Schema 保持纯契约零行为） | Schema 内嵌 to_vo 方法（弃——Schema 混行为职责）；VO 用 pydantic（弃——domain 红线） |
| DC-7 | financial 子域 470-479 新段单异常 + 422 映射 | 第七段先例（410/420/430/440/450/460）；BusinessException[计算失败调用方可处理——AgentEvaluationError 450 直接先例]；422 语义就近映射（BusinessRuleViolationError 惯例锚——业务约束不可满足）；method 自由字符串不做闭集校验（诊断标注面 vs SAPBusStateError reason 协议契约面的差异钦定） | 复用 BusinessRuleViolationError（弃——financial 语义独立子域分立——sap 460 不复用 event 段同款论证）；多异常多码（弃——V1 唯一触发面 IRR，YAGNI） |
| DC-8 | 用例三段可选载荷统一入口 + fail-loud 编排 | epics Gherkin「输出三种估值结果」全跑形态直译 + 单法请求自由度（至少一法 Schema 守卫）；任一方法 470 上抛不吞（调用方拿明确失败自行处置——OD-7 5-11 fail-loud 哲学同族）；同步 execute（纯计算无 IO——async 无谓开销；消费方需异步自行 to_thread） | 三独立用例类（弃——三入口三注册膨胀）；部分结果降级返回（弃——静默半失败违背 fail-loud） |
| DC-9 | SINGLETON + 无状态并发安全论证 | 纯计算零共享可变状态（VO in/VO out 全 frozen）；10 路并发隔离锚直接验证；字符串 impl 延迟加载零装配依赖（与 5-11 DC-6 有状态总线 SINGLETON 论证对照——本 Story 无状态更简单） | SCOPED（弃——无状态服务每次 resolve 新实例无收益纯开销） |
| DC-10 | 三零边界（零事件/零 REST/零 catalog） | 计算服务无状态变化事件（cost_calculator/rrf_fusion 先例）；REST 面整链归 7-2（OD-6）；catalog 接入与 LLM 沙箱链矛盾且 CFO 未开放（OD-3）——消费面接线全部显式登记范围边界表非「未接线遗留」 | 注册事件/端点/catalog（弃——范围爆炸+与 OD-2 矛盾） |

### 风险登记

| # | 风险 | 缓解 |
|---|------|------|
| 1 | **Decimal context 精度截断**（默认 prec=28——十年期 (1+r)^10 连乘 + 大额现金流可能截断尾部） | 引擎内 `localcontext` prec=50 钦定；变异锚构造长序列大额用例使截断可观测（Task 3 变异设计）；0.01% 容差双侧余量 ≥3 数量级兜底 |
| 2 | **基准值本身错误**（expected 拍脑袋值 → 对齐断言形同虚设） | 基准固化纪律：expected 必须可复算（docstring 注明 Excel 公式形态逐例）+ 用例自含手算对照（如 (−100, 110) → IRR=0.1 精确解锚）；dev 期以 Excel 逐例核验 |
| 3 | **pydantic Decimal float 入口污染**（调用方传裸 float 0.1） | wire 契约 docstring 钦定字符串形态；单测断言 str 路径精确性；float 路径知悉不测（pydantic 官方行为——外部契约约定约束非类型拒绝） |
| 4 | **IRR 病态输入死循环**（bracket 失败仍迭代） | bracket 前置检查[同号即 470 不进循环] + 256 次迭代上限防御 + pytest-timeout 兜底 |
| 5 | **tests/fixtures/ 同名遮蔽回归**（误建目录破坏 tests.fixtures 模块导入） | OD-7 落位 tests/unit/domain/services/；架构验证器 B 可选断言 tests/fixtures/ 目录不存在（防后续误建） |
| 6 | **并发性能面与 xdist 分发**（_PERF_CACHE 命中依赖同 worker） | 集成/验收逐字同组 financial-modeling-perf（loadgroup）；组名 16 组互异 grep 断言；「命中或首次采样」形态 |
| 7 | **mypy Decimal 类型推断**（`Decimal \| None` 跨字段/冻结 dataclass 泛型） | Schema Optional 字段显式注解；VO 构造后非 None 断言收紧；mypy 全仓含 tests 门禁（Task 6.4） |
| 8 | **组合根区段冲突**（financial 名占用/注册顺序） | 创建期 grep 实证 financial 零占用；service 字符串 impl 零 resolve 依赖[顺序无关]；use_case lambda 单依赖同区段先行注册 |
| 9 | **Epic 6/9 消费面演进冲突**（引擎签名被消费方推翻） | 端口契约 v1.0.0 + 类即接口稳定面；VO frozen 契约；演进走 contract_gate 兼容检查；范围边界表登记消费方 Story 锚 |
| 10 | **Excel 基准的偶数 median 语义分歧**（Excel MEDIAN 与 statistics.median 偶数样本行为） | 两者同语义[中间两数均值]——用例显式断言偶数样本（Task 4 变异锚改下中位必红）；基准用例含奇偶两形态 |

### 项目结构说明 Project Structure

```
src/
├── application/
│   ├── services/
│   │   └── financial_schemas.py        # ★ 5.12 新建：三段请求 Pydantic v2 Schema 族（OD-1 落位——summary_schemas 先例）
│   └── use_cases/
│       └── financial_modeling.py       # ★ 5.12 新建：FinancialModelingUseCase + FinancialValuationResult DTO + to_value_objects
├── domain/
│   ├── exceptions/
│   │   ├── financial_exceptions.py     # ★ 5.12 新建：FinancialCalculationError（EXCEPTION_470）
│   │   ├── __init__.py                 # ▲ 修改：导出（按字母序插入）
│   │   └── _code_ranges.py             # ▲ 修改：CODE_RANGES "financial": (470, 479) + _CLASS_TO_SUBDOMAIN 一行 + 段注释
│   ├── services/
│   │   └── financial_modeling.py       # ★ 5.12 新建：FinancialModelingService（calculate_dcf/comparable/precedent + _solve_irr + _multiple_stats）
│   └── value_objects/
│       └── financial_valuation.py      # ★ 5.12 新建：11 类 frozen dataclass VO 族 + 242 守卫
├── interfaces/
│   └── api/
│       └── exception_handlers.py       # ▲ 修改：EXCEPTION_HTTP_MAP 470→422 一行（其余零触碰——OD-6 零 REST）
└── composition_root.py                 # ▲ 修改：# === Story 5.12 === 区段（两注册）

tests/
├── acceptance/
│   ├── test_acceptance_financial_modeling.feature   # ★ 13 场景（R6 现代形态）
│   └── test_acceptance_financial_modeling.py        # ★ BDD 步骤实现（零 skip 全场景可跑）
├── contracts/
│   └── test_port_contract_financial_modeling.py     # ★ 11 维度 + service 可达维度
├── integration/
│   └── test_integration_financial_modeling.py       # ★ 性能三锚 + 常量单源 + _PERF_CACHE
├── unit/
│   ├── application/use_cases/
│   │   └── test_financial_modeling_use_case.py      # ★ Schema 六类非法 + 用例编排三路径
│   ├── architecture/
│   │   └── test_arch_financial_modeling.py          # ★ 四验证器（白名单空集/零实例化/Decimal 锚/零抑制）
│   └── domain/
│       ├── exceptions/
│       │   └── test_financial_exceptions.py         # ★ 470 异常族
│       ├── services/
│       │   ├── test_financial_modeling.py           # ★ 三引擎 + Excel 基准对齐
│       │   └── financial_test_cases.json            # ★ Excel 基准用例（OD-7 落位）
│       └── value_objects/
│           └── test_financial_valuation.py          # ★ VO 不变量
└── unit/interfaces/api/
    └── test_exception_handlers.py       # ▲ 存量追加：expected_types + import 两处同步
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 5.11 SAP 协议支持](./5-11-sap-protocol-support.md)

**关键学习/Key Learnings:**
- 验收文件延迟 import 纪律（Task 0-4 窗口期运行期 ModuleNotFoundError 逐场景 failed 非 collection error——Subtask 0.5 红因核对口径：全部步骤函数必须 Task 0 就位，StepDefinitionNotFoundError 非预期红）
- 契约测试两处同步教训（test_exception_handlers.py 的 expected_types 与 import 块漏任一处即红——Task 1 重演义务）
- 常量等值断言是变异锚充分条件（仅 `p95 < limit` 对改大不红——`== 5.0` 等值断言钦定）
- pydantic ValidationError 原样透传零包装先例（AC-4 序列化场景——本 Story Schema 层沿用）
- 性能委托计时全套形态（常量单源集成定义 + 验收延迟 import + xdist 逐字同组 + 正向锚 21 + 四注记 docstring）
- mypy 全仓含 tests/（5-9 ×9 教训——Task 6.4 重演义务）
- 5-5 isolation_access 消费方白名单教训：新增合法消费方须同步白名单——本 Story 零隔离面触碰（无新消费方，风险不适用但知悉）

**应用到本故事/Applied to This Story:**
- [x] 验收文件 context dict fixture（全同步交付面——event_loop/_run_async 不适用省略）+ 延迟 import + 红因核对（Task 0.4/0.5）
- [x] 异常注册存量追加两处同步（Task 1.3）
- [x] 性能委托 + 常量等值断言变异锚 + xdist 组互异（Task 6.1/6.3）
- [x] mypy 全仓 + 零抑制 grep 三连 + 禁 AI 署名 grep（Task 7.4）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (glm-5.3) |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-10-30 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（L1951-1996 / L1448 / L520） |
| **架构文档** | `docs/architecture/architecture.md` + `interface-design.md` §8.2.4 + `sisys-core-domain-design.md` §17.3.1 |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/5-11-sap-protocol-support.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` L1951-1996 提取（范围权威锚定）
- [x] 架构约束从 `architecture.md` + import-linter + 代码先例提取
- [x] 前一个故事（5-11）学习经验整合
- [x] 四视角并行代码调研（工具链框架/LLM 与用例编排/数值精度与既有财务代码/测试模板与注册异常体系）——零财务实现/Decimal 零算术先例/470 空闲段/tests/fixtures 同名冲突四项关键事实实证
- [x] epics 失效引用勘误（L1990「Schema 骨架已存在」——OD-1）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/5-12-financial-modeling-valuation.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/value_objects/financial_valuation.py` - 11 类 VO 族
- `src/domain/services/financial_modeling.py` - 三引擎领域服务
- `src/domain/exceptions/financial_exceptions.py` - FinancialCalculationError 470
- `src/application/services/financial_schemas.py` - 三段请求 Schema
- `src/application/use_cases/financial_modeling.py` - 估值用例
- `src/composition_root.py`（修改）- Story 5.12 区段
- `tests/unit/domain/value_objects/test_financial_valuation.py` - VO 单测
- `tests/unit/domain/services/test_financial_modeling.py` - 引擎单测
- `tests/unit/domain/services/financial_test_cases.json` - Excel 基准（OD-7）
- `tests/unit/domain/exceptions/test_financial_exceptions.py` - 异常单测
- `tests/unit/application/use_cases/test_financial_modeling_use_case.py` - Schema+用例单测
- `tests/contracts/test_port_contract_financial_modeling.py` - 契约测试
- `tests/unit/architecture/test_arch_financial_modeling.py` - 架构验证
- `tests/integration/test_integration_financial_modeling.py` - 性能三锚
- `tests/acceptance/test_acceptance_financial_modeling.feature` - Gherkin 场景
- `tests/acceptance/test_acceptance_financial_modeling.py` - BDD 步骤实现
- `tests/unit/interfaces/api/test_exception_handlers.py`（修改）- 470 追加
- `docs/architecture/sisys-uni-exception-design.md`（修改）- §3.3.2 编码表

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 5.12 |
| **Story Key** | 5-12-financial-modeling-valuation |
| **File** | `_bmad-output/implementation-artifacts/stories/5-12-financial-modeling-valuation.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 5: Agent 协作系统 |
| **价值组** | 单 Agent 战略规划能力（收官计算面） |
| **优先级** | P1-12（执行序）/ FR-ST-09 P1（功能等级） |
| **覆盖 FR** | FR-ST-09（V1 基础口径） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-7）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-5）
3. [x] Architecture constraints extracted 架构约束已提取（六边形/零依赖/三零边界）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | （待审查轮次回填） | — | — |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

（dev 交付后由 code-review 回填）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-10-30
**最后更新/Last Updated:** 2026-10-30
**更新说明/Description:**
- v1.0.0: 创建故事文件（四视角并行调研 + OD-1~OD-8 偏离声明 + AC-1~AC-5 + Task 0-7）
