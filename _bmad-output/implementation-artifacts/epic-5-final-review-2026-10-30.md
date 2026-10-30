# Epic 5 终局审查（Final Review）2026-10-30

> **任务**：EPIC 5（Agent 协作系统，12 Story 全 done）全交付件终局审查——聚焦科学性、合理性、正确性、一致性、可行性，验证「EPIC 5 的所有交付件科学、合理、正确解决了相关遗留项」。工作流：C1 调研 → C2 方案 → C3 评审 → C4 提交 → C5 循环，共 5 轮（Round 1~5）。
> **基线**：main@c0f060d9（5-12 收敛提交）；审查产出同时承载 `epic-5-retrospective: optional` 的遗留项收口职责（5-12 OD-8 显式移交锚）。

---

## Round 1 — 四视角并行调研（C1）

### 调研方法

| 视角 | 职责 | 关键动作 |
|------|------|---------|
| A 遗留项台账核查 | deferred-work.md EPIC 5 相关 ~60 条处置 vs 仓库现实 | 核销 7 项/兑现注记 3 组/顺延链 ~9 条/维持类逐项代码级验证；2026-10-12 普查「触发=Epic 5」族终态判定；10 个 Story 文件 ↔ 台账双向对账 |
| B 跨 Story 一致性 | 四条交付链组合面 | 评估链（5-7→5-8→5-9→5-10）/隔离链（5-4→5-5→5-6）/实例化链（5-1→5-2→5-3）契约比对；组合根 174 条注册查重 + 41 条字符串 impl 双重验证；12 Story File List ~300 路径逐条核验 |
| C epics 范围符合性 | 规划权威面 vs 交付终态 | epics L1420-1997 全量提取；FR 13 条映射逐条核验；合规偏离 80+ 项四要素检查；静默缺口专项 |
| D 运行面验证 | 门禁 + 接线 + CLI | ruff/mypy/红线三条实跑；EPIC 5 定向 2451 测试全绿；组合根 182 端口探针；CLI --help 验证 |

### 调研总评（四视角共识）

- **交付质量**：FR 13/13 全兑现、静默缺口 **0**、四条链契约面健康、零 P0/P1（EPIC 5 交付面）、门禁全绿、组合根 EPIC 5 核心 20 端口零失败。
- **遗留项处置质量**：核销 7 项抽查一致率 100%、兑现注记 3 组全部代码实证、顺延链 ~9 条引用架构事实 100% 成立、Story↔台账双向同步零缺漏。
- **核心缺口**：同根因簇——**Epic 5 完结时点（2026-10-30）「触发=Epic 5」族台账条目未做终局收口**（部分条目现实已向好而台账表述失实）；外加组合根存量幽灵 impl 族（非 Epic 5 引入但落在接线完整性审查面）。

### Round 1 发现清单（去重合并，16 项）

| 编号 | 级别 | 来源 | 发现 | 位置 |
|------|------|------|------|------|
| R1-N1 | P2 | A-5/C-1/B-1/D-1 四视角互证 | Story 5-7 文件头 `Status: review` 未翻转——与自身 v2.2.0 变更日志、sprint-status done、收敛提交 1d339a91 三方矛盾；12 Story 中唯一头部失真者 | stories/5-7-phoenix-evaluation-harness.md L3 |
| R1-N2 | P2 | A-1 | 普查条目「Epic 4 工具执行链零入口——触发=Epic 5」到期未闭环且表述失实：7 项已经 5-3 主链接线激活（agent_cli:493→agent_workflow_use_case→agent_workflow_service→tool_execution_service 装饰链+12 适配器），「零入口」不再成立；5 项仍休眠缺再锚定（StrategicAnalysisUseCase 未注册、run_tool_chain_use_case/red_blue_debate_service/schema_validation_record_repository 注册未消费、sandbox_session_reaper 无启动挂点） | deferred-work.md L125 |
| R1-N3 | P2 | A-2 | 普查条目「orchestration_service/workflow_engine/agent_engine 休眠——触发=Epic 5」部分失实：agent_engine 已被 5-3 消费（组合根 :1551 注入+:3254 resolve）；orchestration_service（零 resolve）与 workflow_engine（仅自锚 lambda 内 resolve）仍休眠无完结注记 | deferred-work.md L129 |
| R1-N4 | P2 | A-3 | 普查条目「AutoTriggerHandler 不在 handler_names——触发=Epic 5」到期未闭环：1.14 管线生产休眠如故；5-7 story L78 有「不接线、归其消费语义立项」决策但明确不进 deferred-work——决策与台账脱节 | deferred-work.md L120 |
| R1-N5 | P2 | A-4 | 工具熔断顺延锚位悬空：触发条件「Epic 5 sprint planning 重估」已随 12/12 done 消亡，两去向中「sprint planning 重估」已不可能；5-4 Task 0「挂点不成立」评估（2026-10-22）后无再锚定 | deferred-work.md L18/L92 |
| R1-N6 | P2（定级分歧 B:P1/D:P3→主会话裁 P2） | B-3/D-2/D-3 | 组合根 8 条幽灵字符串 impl（resolve 必 RuntimeError）：`metrics`/`l0_storage`/`memory_file_storage`/`text_extractor`/`compressor`/`storage_encryption_service`/`api_security_service`/`container_security_service`——其中仅 l0_storage/memory_file_storage 已登记（L175），**6 条零登记**；**活缺陷**：cost_metrics_handler 在 handler_names 激活清单（:3180）但其 lambda resolve "metrics"（:1700）必炸、被 :3183 except 静默吞为 warning——每次生产 bootstrap 必现，L3176-3178 注释「激活 1-17/1-19 成本追踪」半失实（udmr 单边生效）。主会话复核确认全链条（真实类 metrics_port_impl.py:15 MetricsPortImpl 存在、record_token_usage/record_cost 接口齐备、EventMetricsCollector/BusinessMetricsCollector 无参可构造、依赖链可解） | src/composition_root.py L890-897/L1696-1702/L3180-3186 |
| R1-N7 | P2 | B-2 | 5-9 CUSUM 检测器全局混流 vs 5-10 Recorder per-agent 键控——同一评估流两个跨 run 累积器隔离语义不对称（5-10 代码审查 R1 修复同类缺陷未回灌 5-9）；且 5-1 instantiate 非幂等（use_cases/agent_instantiation.py:26 docstring 明示）使 V1-EV14 的「MVP 单 CEO 独占——混流实际不可达」前提论证偏差：多 CEO 实例混流在 MVP 内经 CLI 人工操作真实可达 | cusum_detector.py（无 agent 维度）/V1-EV14 条目 |
| R1-N8 | P3 | A-6/C-2 | sprint-status `epic-5: in-progress`（注释「🚧 进行中」）与 12/12 done 矛盾；`epic-5-retrospective: optional` 未处置——恰是 N2~N5 的最后自然收口窗口 | sprint-status.yaml L156-158/L172 |
| R1-N9 | P3 | B-4 | 5-1 File List 记 `src/interfaces/cli/agent_cli.py`，文件实际已迁 `src/entrypoints/agent_cli.py`（D1 方案 A，c176da99）——迁移在 5-1 自身 v1.13.0 日志有载但 File List 未加注，~300 条路径唯一漂移 | stories/5-1 L973 |
| R1-N10 | P3 | C-3 | 5-6 Task 3 Subtask 3.1~3.5 未勾（3.6/3.7 已勾）、5-5 Subtask 0.1~0.8 未勾（L909 有 `[x] Task 0` 汇总行）——交付证据齐全，纯勾选卫生 | stories/5-6 L512-516/5-5 L431-438 |
| R1-N11 | P3 | C-4 | FR-EV-02 定义句「五维评分模型」vs 交付四字段（三维+overall）口径——epics 自身 Story 5.8 AC（L1780）已钦定四字段，非静默缺口，但 5-8 偏离声明未显式点名「五维」对齐 | epics L120 vs 5-8 story |
| R1-N12 | P3 | B-5 | AgentStatus 五值状态机（agent.py:105-173 四迁移方法）全仓零调用——5-3 工作流状态经 evidence.status 独立承载，「双状态体系并行、其一长眠」，V1 多 Agent 编排需择一归一——无台账登记 | src/domain/entities/agent.py |
| R1-N13 | P3 | D-4 | 组合根 8 处连接类注册（redis/postgresql/qdrant/neo4j 各 2）`module=` 元数据串指向不存在模块——impl 均 lambda 无运行实害，纯元数据漂移（诊断面） | src/composition_root.py 8 处 |
| R1-N14 | P3 | 主会话 P-1/P-3 | deferred-work 头部锚点句「Epic 1-4 done、Epic 5 未启动」（L6）过时；数据触发型区段「共同链：Epic 5-8 交付」（L20）无 Epic 5 完结进度注记 | deferred-work.md L6/L20 |
| R1-N15 | P3 | 主会话 P-5（5-12 OD-8 移交） | prd L492 V1 单变量敏感性分析无具名 Story 承接（孤儿承诺）——5-12 明确「交 Epic 5 retrospective 处置」但 deferred-work 无登记，本次终局审查为该移交锚的承载方 | deferred-work.md（缺条） |
| R1-N16 | — 证伪留痕 | 主会话 P-4 | 「5-10 前向依赖 Epic 6 Story 6.3」疑点证伪——5-10 OD-2 依赖倒置裁定已合规处置（视角 C 确认交付完整），非缺口 | — |

### Round 1 修复方案 v2（C2 — 已吸收双评审员放行条件）

**分派原则**：文档/台账级修复本轮落码；唯一运行时修复 N6（活缺陷——CLAUDE.md「修复根因禁止掩盖」+ 组合根为共享资产非 1-19 独占文件——评审员②考证：幽灵 impl 源自 19fbf461 组合根重构期 2026-05-12，早于 Story 1-19 本体；激活失效由 d49261b0 UDMR 审计修复 F2 引入 2026-10-12，从未被任何 Story 收敛周期覆盖）；N7 运行时行为修复不动（5-9 已收敛交付面 + V1-EV14 已有 V1 归宿承载），仅修正其前提论证注记。

**C3 评审记录**：评审员①（技术正确性）「合格附条件」——F6 三处必改（工厂 resolver 签名/必红测试适配/新测试形态）+ F2 两处锚点失准修正 + F4 措辞注意；评审员②（纪律与价值）「合格附条件」——Q1~Q5 五项放行条件（F6 修复义务成立裁定/V1-EV14 死锚同批修/Story 版本步进/注记显式化/bootstrap 冒烟）。v2 全部吸收。

| 方案 | 对应发现 | 修复内容（v2） | 文件 | 形态 |
|------|---------|---------|------|------|
| F1 | N1 | 5-7 头部 Status `review` → `done`；**+版本步进 v2.2.1→v2.2.2 + Change Log 行**（注明 Epic 5 终局审查 Round 1，证据锚：v2.2.0 日志/sprint-status/1d339a91 三方） | 5-7 story L3 | 文档 |
| F2 | N2 | 普查「工具执行链」条目补 Epic 5 完结处置注记：①激活事实（7 项清单+激活链锚——**评审员①修正：composition_root.py:2816**（agent_workflow_service 注册 lambda 内 resolve tool_execution_service）**+ tool_execution_engine.py:651**（set_data_source_resolver 注入）——写全限定文件名防悬空锚）；②休眠 5 项再锚定（StrategicAnalysisUseCase→**Epic 6 规划评审/首个 BLM Story 立项时评估注册或废弃**；run_tool_chain_use_case/red_blue_debate_service/schema_validation_record_repository→**Epic 6+ 首个编排消费方或 Story 10-6 红蓝全量**；sandbox_session_reaper→**V1 部署专项**——L138 既有登记同锚） | deferred-work.md L125 区段 | 台账 |
| F3 | N3 | 普查「编排引擎」条目补注：agent_engine 已激活（组合根 :1551 注入 + :3254 resolve——5-3 链锚）；orchestration_service/workflow_engine 维持休眠再锚（触发改写为「Epic 6+ 工作流编排消费需求或 **6-1 立项决策时点废弃评估**」；workflow_engine 自锚死链注记） | deferred-work.md L129 区段 | 台账 |
| F4 | N4 | 普查「AutoTriggerHandler」条目（**既有 L120 条目终局收口注记，非新建条目**——与 5-7 story L78 决策「不进 deferred-work——无 gap，仅决定记录」字面协调：本注记是普查条目到期收口，5-7 决策的不登记语义指不新建独立条目）：1.14 管线维持休眠、归自动触发消费语义 Story（可判定锚：Epic 13 heartbeat 规划位或首个自动触发消费方立项） | deferred-work.md L120 区段 | 台账 |
| F5 | N5 | 工具熔断锚位再锚定：主登记位 L18 触发条件改「独立小 Story 立项或 V1 弹性需求驱动」（Epic 5 sprint planning 窗口已消亡）；L92 重复登记位同步去重注记 | deferred-work.md L18/L92 | 台账 |
| F6 | N6 | **运行时修复（v2 三处必改吸收）**：metrics 端口 impl 改模块级工厂函数——**签名 `def _build_metrics_port(resolver: Any) -> MetricsPortImpl`（评审员①：resolver.py L196-197 以 `spec.impl(resolver=self)` 调用，零参签名必 TypeError 且被 bootstrap except 静默吞——修复静默失效；先例 `_build_agent_workflow_use_case(resolver: Any)` 同款 + 注册行 `impl=_build_metrics_port` 前向引用）**；函数体：BusinessMetricsCollector 单实例共享（结构性必需——二构必抛 Duplicated timeseries）+ MetricsAggregator(EventMetricsCollector(), bm) + MetricsPortImpl(aggregator, bm)；module= 元数据同步指向 metrics_port_impl。**测试三件**：①接线测试用 **get_resolver()**（bootstrap 已缓存 metrics 单例；新建 Resolver() 空缓存会二次构造同款 ValueError）+ isinstance 断言针对 **MetricsPortImpl 具体类**（MetricsPort Protocol 非 runtime_checkable）+ record_token_usage/record_cost 可调；②**bootstrap 激活冒烟**（handler_names 循环零 cost_metrics_handler warning——钉死 L3176 注释修复后真实性）；③**适配 tests/unit/infrastructure/monitoring/test_business_metrics.py::test_default_registry_full_lifecycle**（评审员①实验证明：session autouse _bootstrap_once 先注册 sisys_* 进默认 REGISTRY，该测试二构必红；其 docstring 自认「registry=None 仅适用于单例模式（DI 容器 SINGLETON）」——修复后 resolver 恰是该单例持有者，改断言 resolver 持有的单例属测试语义适配非抑制） | src/composition_root.py L890-897 + tests | 代码 |
| F7 | N6 存量面 | 其余 5 条幽灵 impl（text_extractor/compressor/storage_encryption_service/api_security_service/container_security_service）**以「impl 路径失效」注记并入既有普查条目 L126-127/L132-133（照 L175 l0_storage 先例形态，防重复登记）**，按 gap 四要素补归宿/承接方（检索-压缩循环/Epic 6 unified_storage/等保安全接线各归其链）；cost_metrics_handler 修复事实同步注记 | deferred-work.md 普查区段 | 台账 |
| F8 | N7 | V1-EV14 条目补三注：①前提论证修正（instantiate 非幂等 agent_instantiation.py L26 docstring——多 CEO 实例混流 MVP 内 CLI 可达，「不可达」改「人工单发操作面低概率」）；②5-10 per-agent 键控先例交叉引用（`agent-evaluation-{agent_id}` 命名空间 + Dict[agent_id, detector] 形态成熟可直接复用）；③**触发锚改写（评审员②：「Epic 5 CFO/CTO 等角色开放」已随 Epic 5 完结死亡——同 F5/N5 族——改「Epic 9 多 Agent 编排 / V1 CFO 开放 Story 立项」）** | deferred-work.md V1-EV14 条目（L284） | 台账 |
| F9 | N8 | sprint-status `epic-5: in-progress` → `done` + `epic-5-retrospective` 处置——**注记显式二选一**：认定本终局审查为 retro 等价承载则翻 done 并注明依据；或维持 optional 并注明「遗留项收口已由 epic-5-final-review 承载、正式 retro 永不强制」——**放 Round 5 收敛时执行**（评审员②考证：abe00b4f Epic 4 先例——Epic 级状态在收口产出物落地的同一提交中翻转，不在过程中途） | sprint-status.yaml | 台账（R5） |
| F10 | N9 | 5-1 File List agent_cli.py 行加迁移注记（→ src/entrypoints/，D1 方案 A c176da99）；**+5-1 版本步进 v1.14.0→v1.14.1 + Change Log 行** | 5-1 story L973 | 文档 |
| F11 | N10 | 5-6 Subtask 3.1~3.5、5-5 Subtask 0.1~0.8 补勾——**禁静默翻勾**：每处带「终局审查补勾 2026-10-30 + 证据锚」（agent_cli.py:329 isolation-logs / audit_events.py:75 ISOLATION_SWITCH 等）；**+5-6 v1.4.3→v1.4.4 / 5-5 v2.2.1→v2.2.2 各自版本步进 + Change Log 行** | 5-6/5-5 story | 文档 |
| F12 | N11 | 5-8 偏离声明补「五维→四字段」口径注记一行（FR 定义句 L120 五维 vs AC L1780 四字段的规划件内部口径差，非交付缺口）；**+5-8 版本步进 v2.3.1→v2.3.2 + Change Log 行** | 5-8 story OD 表 | 文档 |
| F13 | N12 | AgentStatus 状态机长眠登记 deferred-work——**行号 L99-173（含 L99 start，评审员①修正）**；四要素补齐（归宿=V1、承接方=Epic 9 多 Agent 编排 Story）；**与 D1-5.1 互链**（AgentStatus 第六态登记同族防重复） | deferred-work.md 新条 | 台账 |
| F14 | N13 | 连接类 8 处 module= 元数据漂移登记注记（redis/postgresql/qdrant/neo4j 各 2；修复归组合根元数据卫生专项——验收测试有 `spec.module` 字面断言先例锁定风险，本周期不动） | deferred-work.md 普查区段注记 | 台账 |
| F15 | N14 | deferred-work L6 锚点句更新（Epic 1-5 done，V1 覆盖 Epic 1-8 进行中）；L20 共同链补「Epic 5 已交付 2026-10-30」进度注记 | deferred-work.md L6/L20 | 文档 |
| F16 | N15 | 单变量敏感性孤儿承诺登记 deferred-work（描述+触发=V1 立项 sprint-change 定锚+归宿 V1+承接方=规划专项，**具名承接候选 Story 20-2（sensitivity-analysis-api-tornado-chart，backlog）**；5-12 OD-8 移交锚闭环） | deferred-work.md 新条 | 台账 |

**不修复留痕**：N16（证伪）；B-2 运行时修复（归 V1-EV14 专项——跨 5-9 已收敛交付面的行为变更需专项测试设计，本轮注记承载；评审员②裁定正当）；D-5（chunk_indexing 环境条件性，非缺陷）。

### Round 1 落码记录（C3 放行后执行，2026-10-31）

- **F6 代码修复**：composition_root.py metrics 注册块（impl=_build_metrics_port 前向引用 + module 指向 metrics_port_impl）+ 模块级工厂函数（TYPE_CHECKING 类型注解——函数内 import + 裸注解 ruff F821/mypy name-defined 双红后修正）+ BusinessMetricsCollector 单实例共享。
- **F6 测试三件**：①新增 tests/unit/infrastructure/monitoring/test_metrics_port_wiring.py（resolve 真实实现 + isinstance MetricsPortImpl + 激活链前提[handler resolve + async register callable]）；②test_default_registry_full_lifecycle 适配（resolver 单例 + set 语义绝对断言/累加语义增量断言）；③**落码中新发现并修复**：tests/contracts/test_port_contract_application.py `_get_impl` 的 `Resolver()` 新建形态对 SINGLETON 端口绕过生命周期缓存强制重构造——metrics 修复后该 helper 实例化必红（契约测试此前因幽灵路径 `impl is None: return` 静默跳过——被架空的测试又一实证）；改 `get_resolver()` 复用全局缓存，contracts 全量 1431 passed。
- **文档/台账**：F1（5-7 v2.2.2）/F10（5-1 v1.14.1）/F11（5-6 v1.4.4 + 5-5 v2.2.2，补勾带注记非静默）/F12（5-8 v2.3.2）；F2/F3/F4/F5/F7/F8/F14/F15 内联注记 + F13/F16 新条目（「Epic 5 终局审查 Round 1」区段）；F9 留待 Round 5。
- **门禁**：ruff src/ tests/ 零输出；mypy src/ 719 文件零问题；monitoring + contracts 定向 241 passed。

---

## Round 2 —（待执行）

## Round 3 —（待执行）

## Round 4 —（待执行）

## Round 5 —（待执行）
