# Story 6.1: BLM 前两阶段流程（业绩差距分析 + 市场洞察）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 企业战略人员,
**I want** 系统执行 BLM 前两阶段流程（业绩差距分析 + 市场洞察，含流程可视化；MVP 阶段 CEO AGENT 替代流程中所有 AGENT 角色）,
**So that** 完成战略规划的基础分析阶段。

### 业务价值

BLM（Business Leadership Model）前两阶段是战略规划（SP）的入口分析面：阶段 1 业绩差距分析量化「实际业绩 vs 目标业绩」的差距与根因；阶段 2 市场洞察经六子步骤（看趋势/看市场与客户/看竞争/看自己/看机会/机会差距分析）扫描外部环境与内部能力。本 Story 交付 Epic 6 的流程骨架——后续 Checkpoint（6.3）、思维链规范化（6.4）、报告生成（6.5a/b）全部以本流程为宿主。MVP 口径下由 CEO Agent 单角色承担完整版设计中的 CFO/COO/CMO 等全部角色（PRD L453：MVP 用 CEO Agent 覆盖主要场景）。

**范围权威**（冲突时以先者为尊）：
- epics_v1.0.md L2040-2077（Story 6.1 全节：用户故事/AC/TDD 要求）
- epics_v1.0.md L1999-2036（Epic 6 头部：目标/FR/依赖验证）
- prd.md L1866-1871（FR-SP-01 P0 定义）+ L420（MVP 功能集合行）
- or.md L379-415（五.2 BLM 六阶段总纲：阶段 1/2 的角色/工具/产出权威定义）
- docs/architecture/architecture.md L397-404（编排流程 23-29）+ L2998-3032（§17.5 战略规划架构）+ L2451/L3244（图落位钦定 `src/infrastructure/agent_orch/graphs/sp_blm_graph.py`；BLM 状态机伪码权威在 sisys-core-domain-design.md §17.4——该文件无 §17.5，§17.5 在 architecture.md）
- sisys-core-domain-design.md L1803-1974（§17.4 BLM 状态机伪码——完整版蓝图，见 OD-3 裁定）

### 范围边界（与后续 Story 的精确切分）

| 能力 | 本 Story（6.1） | 后续 Story |
|------|----------------|-----------|
| 业绩差距分析流程（差距量化→根因→组合健康度） | ✅ 单 Agent 流程执行 + 产物 VO（`src/infrastructure/agent_orch/graphs/sp_blm_graph.py` 节点承载） | ❌ CFO/COO 多角色实例化——V1（Story 9-x 多 Agent） |
| 市场洞察六子步骤**基础**流程（顺序执行+综合洞察） | ✅ 六子步骤顺序执行（or.md L385-415 顺序；每步产出**通用信封** `InsightStepResult`——step/summary/findings/tool_used/evidence_refs/degraded，结构化程度止于信封层） + `synthesize_insights` 综合 | ❌ 每步**类型化 Schema** 结果（PESTEL 六维度等领域结构——6.1 仅通用信封）+ 每步 Checkpoint——Story 6-2（epics L2089-2090）；❌ 六子步骤深化工具面（epics 6.2 节实际口径为结构化输出与 Checkpoint 触发；「工具矩阵」系 or.md「建议工具组合」的解释性概括）——6-2 |
| Checkpoint 快照机制（持久化笔记→压缩→快照→Redis Hash） | ❌ 机制创建面明确不归本 Story（architecture.md L1587 钦定 6.3）——6.1 仅将阶段产物落图 state 供 6.3 快照消费 | Story 6-3（PersistentNoteTaker→压缩→CheckpointSnapshot 全链） |
| 阶段位点推进语义（流程到达 Checkpoint 位点即停/即续） | ✅ 流程面：阶段完成状态可查询（`BlmPlanningStatus`） | ❌ 用户反馈/恢复执行——6-3/6-6；❌ CHECKPOINTED 第六态——已裁定不引入（deferred-work D1-5.1 锚 6.3 再评估） |
| JSON 思维链输出规范化（Input→Reflection→Tools_Used→Constraints_Check→JSON） | ❌ 5-3 已内建思维链（epics L1560），本 Story 复用不规范化 | Story 6-4（BLM 面输出规范化） |
| 报告生成（Markdown/PDF/引文索引） | ❌ 报告归 Prefect 数据管线 | Story 6-5a/6-5b（FR-UI-11） |
| 流程可视化**数据面**（当前阶段/子步骤/进度） | ✅ 状态查询接口 + CLI 进度输出（后端数据面；epics L2060「前端指标，后端不定义」） | ❌ 完整 UI（分析师视图 BLM 进度可视化）——Story 6-9 |
| 溯源树/高管简化视图 | ❌ 展示层 | Story 6-7/6-8 |
| BLM 阶段 3-6（战略意图/创新焦点/业务设计/执行设计） | ❌ MVP 明确排除（PRD L454「前两阶段覆盖 80% 场景，手动补充后四阶段」） | Epic 10 Story 10-1（FR-SP-05 完整六阶段，同文件扩展见 OD-4） |
| REST API 入口（`/api/v1/plans`） | ❌ 本 Story 入口为 CLI（OD-5） | Story 7-2 |

### 偏离声明（Deviation Declarations）

| # | 偏离 | 规划原文 | 偏离理由与归宿 |
|---|------|---------|---------------|
| OD-1 | 测试文件命名从仓内惯例不从 epics 占位名 | epics L2072-2074：`tests/unit/architecture/test_blm_process.py`、`tests/integration/test_blm_process_integration.py` | 仓内惯例功能性命名（记忆 feedback_no_story_number_in_filenames）：本 Story 测试以 blm_/planning **功能名族**命名（代表性示例：`test_blm_planning_service.py`/`test_run_blm_planning.py`/`test_integration_blm_planning.py`/`test_acceptance_blm_planning.feature/.py`——全量以「测试分类与归属」表为准） |
| OD-2 | 市场洞察第 6 步口径钉死为「机会差距分析」 | core-domain-design §17.4.2 L1938 子步骤配置写作「2.6_看风险」 | **or.md L411/PRD FR-SP-02（L1869）为权威**：六子步骤=看趋势/看市场与客户/看竞争/看自己/看机会/**机会差距分析**。「看风险」为架构稿过时表述不采用；本 Story 落地后建议在文档审查轮同步勘误 core-domain-design（他文档资产，不在本 Story 代码 scope） |
| OD-3 | §17.4.2 伪码仅取流程结构，不取多角色/Checkpoint 调用形态 | 伪码含 `LEAD_AGENTS=["CFO","COO"]`（L1846）、`checkpoint_repo.save()`（L1890 阶段 1 / L1964 每子步骤）、每子步骤 Checkpoint | 伪码是完整版（V1）蓝图：多角色归 Epic 9（MVP 由 CEO Agent 全替代，FR-SP-01 括注）；Checkpoint 机制归 6.3（architecture L1587）。6.1 取其阶段/子步骤划分、产物字段语义（financial_gap/operational_gap/root_causes/portfolio_health 等）与执行顺序 |
| OD-4 | 图文件按 architecture 落位名 `sp_blm_graph.py` 先建前两阶段版 | architecture L3244 将 `sp_blm_graph.py` 标注为 FR-SP-05（完整六阶段，Epic 10） | 文件演进而非另建：6.1 交付前两阶段图于钦定落位，Epic 10 Story 10-1 在同文件扩展阶段 3-6 节点（docstring 注明扩展锚）；避免 Epic 10 时出现 `blm_graph.py`/`sp_blm_graph.py` 双文件分裂 |
| OD-5 | MVP 入口为 CLI，REST API 不在本 Story | architecture L2481-2489 规划 `GET/POST /api/v1/plans` | epics Story 6.1 节零 API 交付要求；7-2 才是 REST 入口 Story。CLI 入口沿用 `agent_cli.py`（**argparse 标准库实现**——文件头自证「零额外依赖」，非 Typer）接线模式（resolve + `_ensure_bootstrapped`） |

---

## 🔗 前置依赖

| 依赖 | 提供能力 | 就绪状态 |
|------|---------|---------|
| Story 1.4 Redis 缓存层 | 状态缓存（BlmPlanningStatus latest 快照落位） | ✅ done |
| Story 1.7 MinIO 对象层 | 证据包落盘位（本 Story 仅内存态证据 VO，落盘归 6.5） | ✅ done |
| Story 1.18b LangGraph 编排 | `LangGraphEngine` 状态机执行引擎（`submit_graph`/`get_graph_result`） | ✅ done |
| Story 2.2a 文档解析 | AC Given「文档已解析并索引」——分析语料前置 | ✅ done |
| Story 3-1a Dense 语义检索 | bge-m3 嵌入 + Qdrant 检索（市场洞察取数证据） | ✅ done |
| Story 4.1 战略工具注册 | 23 种工具注册面（SWOT-TOWS/KPI 树/PESTEL/波特五力/$APPEALS/VRIO/安索夫等 BLM 建议工具均已注册） | ✅ done |
| Story 5.3 单 Agent 工作流 | CEO Agent 执行骨架：六阶段服务方法/图适配器模式/CLI 接线/思维链内建 | ✅ done |

### 现有代码继承（必须复用，禁止重复定义）

| 组件 | 位置 | 复用方式 |
|------|------|---------|
| `RunAgentWorkflowUseCase` 编排骨架 | `src/application/use_cases/run_agent_workflow.py:67` | 七步编排模式平移：存在守卫 443→角色守卫 441→隔离 fail-closed 447→档案加载→build_context→`submit_graph`→终态 state 直读组装 |
| `AgentWorkflowServicePort` 六阶段 + `_structured_call` 444 纪律 | `src/application/ports/agent_workflow.py` + `src/application/services/agent_workflow_service.py:107,430-487` | BLM 阶段方法同构（per-call timeout 8s、温度五档、444 包装先例全部沿用） |
| `LangGraphEngine` + 图适配器模式 | `src/infrastructure/agent_orch/langgraph_engine.py:30` + `graphs/single_agent_workflow_graph.py:33-121` | 图挂载**双点**：`_SUPPORTED_GRAPHS` 集合增名（仅消告警）**＋ `_build_graph` 增显式 `if graph_name == "SpBlmGraph"` 分派分支**（`langgraph_engine.py:174-212`——SingleAgentWorkflow 先例 L189-197；集合只是告警判据，漏加分支将**静默回退 BasicAgent**）＋构造器尾部追加 `blm_planning_service: BlmPlanningServicePort \| None = None` 注入位（L51 `workflow_service` 尾部可选先例平移）；节点适配器 DC-1 模式（服务阶段方法→dict 部分更新）平移 |
| `LoadAgentProfileUseCase`（5-2） | `src/application/use_cases/agent_profile_loading.py:75` | CEO 档案加载（六档案 VO + tools_l1 + startup_context_tokens）直接注入 |
| 工具调用链 | `agent_workflow_service.py:246-274`（全量隔离预检 449 + `get_tool` + `tool_execution_service.execute`） | 六子步骤工具调用走同链；`tool_name` 空步骤直接推理（L252-254）先例沿用 |
| 检索取数 | `resolve("hybrid_search_service")`（`composition_root.py:1815`；async 签名 `search(collection, query_text, limit=10, tenant_id=None, filter_payload=None, weights=None)`——`hybrid_search_service.py:71-79`） | 市场洞察证据注入直接 resolve，**不新建检索端口** |
| CLI 接线模式 | `src/entrypoints/agent_cli.py:100-111,491-558` | `_ensure_bootstrapped`/resolve/摘要输出模式平移 |
| 评估块 span 键 | `src/application/ports/agent_tracing.py:125-128` | BLM 阶段 span 属性（`blm.current_stage` 等新增键入同注册表） |
| `EvaluationCheckpointRecorder` 键控 + RedisSnapshotStore latest 快照 | `src/application/ports/agent_checkpoint.py:55`（前缀常量单源）+ `src/application/services/evaluation_checkpoint_recorder.py:135`（session_id 拼接）+ `src/infrastructure/storage/redis/redis_snapshot_store.py:111-122`（最终键落库：`build_key("snapshot", session_id)` + pipeline hset `"latest"`+TTL 原子提交） | `BlmPlanningStatus` 快照**三层形态**先例：端口文件单源前缀常量 → session_id=`blm-planning-{plan_id}` → 经快照存储落最终键 `sisys:snapshot:blm-planning-{plan_id}`（hset latest+TTL——非裸键 SET 直写） |

**明确不存在、本 Story 需新建**：
1. BLM 领域概念（阶段/子步骤枚举、流程状态 VO）——domain 层从零（GAP-CRITICAL-06：BLM 状态机未实现）。注：`PlanningStarted`/`BlmStageCompleted` 落入**已存在的** `src/domain/events/planning_events.py`（现含 `StrategicDeviationWarning`）——是**新增事件类**而非新建文件
2. `BlmPlanningServicePort` + `BlmPlanningService`（阶段/子步骤方法 + prompt 模板）
3. `RunBlmPlanningUseCase` + `GetBlmPlanningStatusUseCase`
4. `SpBlmGraph` 图工厂（前两阶段节点拓扑）
5. `PlanningStarted`/`BlmStageCompleted` 领域事件类（扩展现有 `planning_events.py` + `events/__init__.py` 导出）+ 通道接线（`event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS` 双登记）
6. BLM 规划异常（`planning_exceptions.py`）
7. CLI `blm-plan` 子命令 + 组合根注册族

### 移交给本 Story 的留项（前置留项清单——Epic 5 回顾行动项 1a 首秀；deferred-work 钦定/毗邻候选，Task 0 逐条裁定 + deferred-work.md 落注记）

| # | 留项 | 来源 | 本 Story 处置 |
|---|------|------|---------------|
| 1 | **事件消费基建四件**（R1-DF2 主条）：outbox poller 宿主未部署 / RabbitMQConsumer 组合根零注册 / register_handler 队列名 vs 事件类型键语义错位 / realtime start 零调用——台账钦点「6-1 BLM 流程或审计消费 Story 专项定夺」 | deferred-work.md L170 | **Task 0 裁定（预判：锚位顺延）**——6.1 BLM 流程是**纯事件生产方**（同步阻塞执行、零事件订阅面：流程推进不依赖消费任何领域事件，调研实证 5-3 链路同构）；四件基建不在本 Story 接线，且 **register_handler 键语义错位未修复前禁止激活消费基建**（激活即隐性故障）。锚位顺延（候选：6-3 Checkpoint 恢复消费面 / 6-6 审批 / Epic 8 审计消费 Story——Task 0 履行锚位调研义务[回顾行动项 1b]：核实锚位 Story 真消费事件后落锚）；Task 0.7 在 L170 追加 6-1 处置注记 |
| 2 | **StrategicAnalysisUseCase 评估注册或废弃**（组合根零注册的休眠用例）——台账钦点「Epic 6 规划评审/首个 BLM Story 立项时评估」 | deferred-work.md L125 | **Task 0 裁定（预判：保留 + 取代注记，不删除）**——事实修正：①「组合根零注册」核实为真；②与 5-3 execute 链的**重复面仅为工具执行链本体**（get_tool→tool_execution_service），**差异面为该用例独有**：SOP 白名单注入（`skill_loader.load_sop`→`extensions["tool_metadata"]`，4.1c 接线在 5-3 链上不活跃——5-3 的 `skill_loader` 注入后零使用）与 `ToolExecuted` 发布（唯一交互链发布方，喂 `ToolExecutedEventHandler`→`update_tool_statistics` 统计数据链——留项 #6 数据源），「零能力损失」不成立；③删除爆炸半径**非零**：src 引用 4 处（`run_tool_chain.py:98/128`、`tool_executed_event_handler.py:6`、`agent_instantiation.py:53`）+ 测试面 7 文件（单测 import×2：`test_strategic_analysis_usecase.py`/`test_strategic_analysis_datasource.py`；集成 import+实例化×1：`test_integration_strategic_tool_e2e.py`；架构测试路径断言×4：`test_arch_strategic_tool_impl.py:42`/`test_arch_skill_framework.py:49`/`test_arch_skill_data_collection.py:62`/`test_arch_skill_mixed_data.py:60`）。处置：**保留不删**（休眠零持有成本），Task 0.7 在 L125 追加取代事实注记（「工具执行链被 5-3/6.1 直接消费；SOP 白名单与 ToolExecuted 统计链能力归宿：工具矩阵深化 6-2 评估 / 留项 #6 产品立项」），最终废弃定夺与留项 #3 同批锚 Epic 7 API 入口立项——正式裁定落 DC-9，Task 0 复核 |
| 3 | **orchestration_service / workflow_engine 废弃评估**——台账钦点「6-1 BLM 流程 Story 立项决策时点一并做废弃评估（document_tasks.py 死链同批处置）」 | deferred-work.md L129 | **Task 0 裁定（预判：保留 data_pipeline 轨 + 注记，不删除）**——**事实修正**：document_tasks.py 非死链（`document_tasks.py:36` 的 `parse_document` @task 已是 2-2a 真实实现，被 `document_processing_flow.py:23` 引用，仅缺 Prefect 生产触发方）；`orchestration_service` 的 agent_reasoning 分支（task_type 路由→LangGraph 薄壳）对 BLM 无增益——6.1 直接经 use case→`submit_graph` 路径，不经路由壳。处置：保留（data_pipeline 轨是 Epic 6.5 报告管线候选宿主），Task 0.7 在 L129 追加「agent_reasoning 分支已被 5-3/6.1 直接 submit_graph 路径取代」事实注记，最终废弃定夺锚 Epic 7 API 入口立项（届时若无消费方则删除） |
| 4 | **记忆链路 12 端口**（unified_storage + L0/memory 子系统；触发=Epic 6；K5 已消雷 l0/memory_file_storage 两件） | deferred-work.md L127/L176 | **Task 0 裁定（预判：不触发，锚位顺延）**——BLM 前两阶段单 run 内闭合：阶段间上下文经图 state 传递（DC-4），不跨 run；档案态 MEMORY.md 经 5-2 loader 注入（现状沿用）。锚位顺延至真正的跨 run 记忆消费 Story（6.3 恢复面或 Epic 9） |
| 5 | **text_extractor/compressor impl 改串**（真类在 application 层，改串零重建；触发=检索-压缩循环接线 Story 立项时核实） | deferred-work.md L132 | **Task 0 裁定（预判：不触发）**——市场洞察取数直接 resolve 检索服务（继承表），不经压缩循环。锚位保持 |
| 6 | **灰度推进/per-version 统计视图评估**（建议 Epic 6 BLM 流程实施时评估） | deferred-work.md L13 | **Task 0 裁定（预判：不触发）**——纯缺需求方（数据面 `list_by_tool` 已就绪），6.1 无工具灰度消费面。锚位保持「产品立项」 |
| 7 | **langgraph retry/timeout 字段语义定稿**（锚 6.6 checkpoint_table 消费方） | deferred-work.md L17 | 不触发——6.1 图重试语义对齐既有 `MAX_RETRIES=2` 先例（`single_agent_workflow_graph.py:30`），字段级定稿仍归 6.6 |
| 8 | **R1-DF5 checkpointer / D1-5.1 CHECKPOINTED 第六态**（均锚 6.3） | deferred-work.md L195/L293 | 不触发——6.1 图 `compile()` 不加 checkpointer（对齐 SingleAgentWorkflow 先例 + R1-DF5 语义分立裁定）；阶段产物落 state 供 6.3 快照消费 |

**知悉注记（不占处置行）**：
- 幻觉工具名 380 穿透（L190，5-3 链触发=工具选择韧性 Story）：6.1 在 **BLM 面局部核销**——BlmPlanningService 步级捕获 449/380 记 degraded 继续推进（AC-6⑤，5-3 链 `L252-254` 的空工具名分支是正常路径非降级路径，不可作 380 先例引用）；5-3 链面的穿透现状不变，专项韧性仍归后续 Story——Task 0.7 在 L190 追加「BLM 面 6.1 局部核销」注记
- 性能口径教训（5-2 R1-DF3）：6.1 P95 计量口径在测试 docstring 显式声明（DC-7）
- CLI 无 poller → RELIABLE 事件滞留 outbox（L170 既有登记）：本 Story 新增事件的验收测试清理走 fixture teardown（K8 先例），测试面残留量级注记归 L170 锚

---

## ✅ Acceptance Criteria 验收标准

### AC-1: BLM 前两阶段流程执行

**Given** 文档已解析并索引（2-2a/3-1a 产物在位——构造序列与检索门控档位 Task 0.3 钦定：复用 3-1a 验收 embedding 探测+upsert 先例建租户隔离 collection，检索不可达环境该类场景动态 skip）
**And** CEO Agent 已实例化（Story 5.1）且档案已加载（Story 5.2）
**When** 启动 BLM 规划（`blm-plan` 提交规划任务）
**Then** ①阶段 1 业绩差距分析执行：产出差距量化产物（financial_gap/operational_gap/root_causes/portfolio_health 四字段语义对齐 §17.4.2 伪码产物定义）
**And** ②阶段 2 市场洞察六子步骤按 or.md 顺序依次执行（看趋势→看市场与客户→看竞争→看自己→看机会→机会差距分析——OD-2 口径）
**And** ③`synthesize_insights` 综合洞察报告生成（聚合六子步骤产物的结构化结论）
**And** ④结果 DTO 返回阶段 1+2 全部产物（终态 state 直读组装，5-3 同构）

**验证标准/Validation Criteria:**
- [ ] 阶段 1 产物含四字段语义（值可为 LLM 生成文本/结构化对象，字段名对齐伪码）
- [ ] 六子步骤执行顺序断言**双锚**：①`insight_steps[i].step == EXPECTED_ORDER[i]`（枚举序期望独立构造自 or.md 六步序——真正的顺序判别；时间戳单调**无法证伪乱序串行**）②时间戳非重叠断言 `started_at[i] >= completed_at[i-1]`（证伪并行；时间戳为运行期值不可独立构造——5-12 循环自证红线）
- [ ] 综合洞察**双锚**：①注入侧——synthesize prompt 含六步产物摘要（Fake 捕获 prompt 断言，可判别漏传；产出侧非空断言在 Fake 可控输出下近自证）②`degraded_inputs` 为空（正常路径）
- [ ] 全链在 CEO Agent 单实例上执行（agent_id 全程单一）

### AC-2: CEO Agent 单角色替代（MVP）

**Given** 完整版设计为多角色（阶段 1 CFO/COO 主导、阶段 2 各子步骤 CEO/CTO/CMO/COO/CFO 交替主导——or.md L380-415）
**When** 6.1 流程执行
**Then** 全部阶段/子步骤由 CEO Agent 单角色承担——角色语义经**阶段 prompt 视角前缀**承载（如「以 CFO 财务视角量化业绩差距…」），不实例化任何其他角色 Agent
**And** 5.3 单 Agent 标准工作流骨架（守卫→档案→装配→图执行）全量复用

**验证标准/Validation Criteria:**
- [ ] 全仓 grep 零新增非 CEO 角色实例化（SUPPORTED_ROLES 不扩展）
- [ ] 阶段 prompt 含角色视角前缀**与该步工具候选白名单**（第 N 步 prompt 含第 N 步前缀与候选——六子步骤语义配置表 Task 0.1 钦定；persona 研究证据：任务化角色框架优于纯身份宣称）
- [ ] 5.3 守卫链（存在 443/角色 441/隔离 fail-closed 447）对 BLM 入口同样生效

### AC-3: 流程可视化数据面

**Given** BLM 规划任务执行中/已完成
**When** 查询规划状态（`GetBlmPlanningStatusUseCase`）
**Then** 返回当前阶段（phase）/当前子步骤（step）/已完成步骤进度（completed_steps/total_steps + 百分比，**total_steps=8 钦定**：performance_gap+六子步骤+synthesis）/各步骤摘要（由 timeline 条目 `summary_excerpt` 承载）
**And** 状态可经 Redis latest 快照查询（三层键形态：端口文件单源前缀常量 → session_id=`blm-planning-{plan_id}` → 最终键 `sisys:snapshot:blm-planning-{plan_id}`，pipeline hset `"latest"`+TTL 原子提交——5-10 先例形态）
**And** CLI 输出阶段进度摘要（`_print_blm_progress` 模式）

**验证标准/Validation Criteria:**
- [ ] 执行中（**步骤边界快照点**——同步阻塞流程下 use case 看不到步骤内部，「任一时点」物理不可达；测试构造=`asyncio.create_task` 后台跑规划 + 主协程轮询快照，Fake LLM 经 `asyncio.Event` 挂起制造窗口）状态可查询（阶段/子步骤/进度百分比非空）
- [ ] 执行完成后状态为终态（total_steps=8 全部 completed：performance_gap+六子步骤+synthesis）
- [ ] Redis latest 快照读写一致（写后读回断言）
- [ ] 后端仅提供数据面，零 UI 交付（epics L2060「前端指标，后端不定义」）

### AC-4: 领域事件发布（通道登记与投递）

**Given** BLM 规划流程执行
**When** ①规划启动 ②阶段 1 完成 ③各子步骤完成 ④阶段 2 综合（含全流程完成）
**Then** 发布 `PlanningStarted`（①）与 `BlmStageCompleted`（②③④——`stage` 字段区分 performance_gap/market_insight_{step}/market_insight_synthesis）领域事件
**And** 事件按 `event_channels.yaml` 钦定的 delivery_mode 经对应通道投递（**两事件均钦定 reliable**——对齐 AgentDecided 先例 `configs/event_channels.yaml`，经 RabbitMQ/Outbox；`DualChannelEventBus.publish` 按事件**单模式**分派：REALTIME 仅 Redis pub/sub、RELIABLE 仅 Outbox——一事件不走双通道，CLAUDE.md「双通道」指体系提供两种通道非单事件双投）
**And** `configs/event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` 同步登记（CLAUDE.md 纪律）

**验证标准/Validation Criteria:**
- [ ] 新事件契约测试通过（命名/字段/序列化 roundtrip）
- [ ] event_channels.yaml + ChannelRouter 双登记断言（守护测试防漏登）
- [ ] 集成场景：真实 event_publisher 路径 PG event_outbox 落行断言（5-3 场景⑤先例，PG 门控动态 skip）——**全集断言**：一次全流程 `BlmStageCompleted` 的 8 个 stage 值（performance_gap+market_insight_{六步}+market_insight_synthesis）各恰发布一次，另 `PlanningStarted` 恰一行
- [ ] CheckpointReached **不发布**（6.3 语义分立——5-10 OD-6/DC-8 裁定先例：`5-10-checkpoint-with-evaluation-integration.md` L53/L624；负向断言入 Task 4 循环 A）

### AC-5: 性能与成功率

**Given** BLM 前两阶段完整流程执行
**When** 计量性能
**Then** ①全流程执行延迟 P95<30s（epics L2059）②市场洞察六子步骤成功率≥95%（epics L2061——成功口径：子步骤产出非空且无未捕获异常，降级成功计入）
**And** 计量口径在测试 docstring 显式声明：**Fake LLM 管线自身开销口径**（真实 LLM 延迟显式出栈——5-8 AC-5/5-2 R1-DF3 先例；真实 LLM 全链计时归部署验证）

**验证标准/Validation Criteria:**
- [ ] Fake LLM 口径 P95<30s 断言（分级断言形态，4-6/4-7 基准先例）
- [ ] 六子步骤成功率≥95% 批量执行统计断言（**受控失败注入采样**：≥20 次中随机注入单步失败→降级成功计入后断言≥95%——零注入采样在 Fake 可控输出下恒 100% 零鉴别力；与 AC-6⑤ 口径衔接）
- [ ] 口径差声明落测试 docstring
- [ ] 单调用 8s 上限以**配置传递断言**验证：Fake LLM 捕获 `structured_generate` 收到的 config 实参逐次断言 `timeout == 8.0` **且温度==语义配置表该步钦定档**（8 步温度映射入 Task 0.1 配置表温度列——5-3 五档键（perceive/plan/verify/reflect/package）与 BLM 8 步无直接映射，期望值以配置表为唯一源；真实超时执行在 LLM 客户端内——Fake 口径下行为断言不可达，真实行为归部署验证，DC-7 口径差声明覆盖本条）

### AC-6: 异常与步级降级

**Given** BLM 流程执行中 LLM 调用失败/工具调用失败（隔离预检 449——验收层真实可达锚；幻觉工具名 380 在「确定性工具候选白名单」设计下**生产不可达**（白名单 slug 必已注册），其降级锚定单测层，见验证标准注）/检索取数失败
**When** 单步失败
**Then** ①步级降级：失败步骤产物标记 `degraded` 并记录失败原因，流程继续推进后续步骤（六子步骤间无硬依赖中断）②降级步骤计入状态查询可见性（AC-3 摘要含降级标记）③全流程结果 DTO 携带 `degraded_steps` 清单
**And** ④顶层异常走统一异常体系（`src/domain/exceptions/` planning 子域新异常，禁止 ValueError——红线）
**And** ⑤幻觉工具名/隔离预检失败步骤由 BlmPlanningService **步级捕获** 449/380 记 degraded 并以直接推理续行（449=全量隔离预检 `agent_workflow_service.py:247-249` / 380=ToolNotFoundError；即 R1-DF1 台账 L190 在 BLM 面的局部核销——5-3 链 `L252-254` 为空工具名正常分支，非降级先例）
**And** ⑥降级下游消费三规则：degraded 步骤产物以「[降级]+原因」显式标注注入下游 prompt；`synthesize_insights` 结论必须列举 degraded 输入（不可无标注吞并）；阶段 1 全降级时阶段 2 照常执行但综合报告携带标记

**验证标准/Validation Criteria:**
- [ ] 单步注入失败（Fake LLM 抛错/隔离预检 449/检索取数失败——三类注入落点矩阵 Task 0.3 钦定；验收层 449 构造=tools_l1 受限的真实 CEO Agent；**380 降级锚单测层**（Mock 注册表注入未注册名——`AsyncMock(spec=...)` 合规域）→ 流程完成且 `degraded_steps` 恰含该步
- [ ] 上游降级 → 下游产物含降级标注（⑥规则断言：下游 prompt 或 synthesis 含 degraded 步骤标注）
- [ ] **全部 8 步降级**（len(degraded_steps)==total_steps——**抛出点钦定**：RunBlmPlanningUseCase 终态组装处，归 Task 2 红）→ 顶层 PlanningExecutionError(481)（领域异常，HTTP 映射注册）
- [ ] **部分降级**（如 7/8，含仅 synthesis 降级）返回成功 DTO + degraded_steps（成文语义——防「部分降级误抛 481」多解；补 7/8 降级终态期望断言）
- [ ] 新异常五件套齐备（定义文件/`_code_ranges.py` 子域映射/`__init__.py` 暴露+EXCEPTION_HTTP_MAP/子域码段校验/`sisys-uni-exception-design.md` §3.3.2 编码表同步）
- [ ] 三条红线 grep 自查零输出（`raise ValueError`/手动 HTTPException/继承内置 Exception）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] `PlanningStarted`：`src/domain/events/planning_events.py`——**扩展既有文件**（现含 `StrategicDeviationWarning`，勿整文件覆盖）——plan_id/agent_id/tenant_id/started_at（dataclass，继承 DomainEvent 基类；命名对齐 story-template.md L50 `[Aggregate][EventName]` 规范，事件链语义对齐 or.md L138 规划事件流转）
- [ ] `BlmStageCompleted`：同文件——plan_id/agent_id/stage（`performance_gap`/`market_insight_{trend|market_customer|competition|self|opportunity|opportunity_gap}`/`market_insight_synthesis`）/completed_at/summary_excerpt（截断纪律参照 fix_attempts violations_excerpt 先例：≤200 字符）
- [ ] 事件类经 `event_type: str = field(default="X", init=False)` 字段声明由 `DomainEvent.__init_subclass__` **自动注册**进 `DomainEvent._registry`（仓内无 `__event_registry__` 符号——`src/domain/events/base.py:77-90`）+ `events/__init__.py` 导出与序列化 roundtrip 约束（既有 DomainEvent 契约）
- [ ] domain 层零第三方依赖（dataclass + 标准库）

#### 数据模型 (Data Models)

- [ ] `BlmPhase` 枚举（`src/domain/value_objects/blm_phases.py`）：`PERFORMANCE_GAP`/`MARKET_INSIGHT`（前两阶段；枚举预留六阶段扩展注释锚 Epic 10）
- [ ] `MarketInsightStep` 枚举（同文件）：六值按 or.md 顺序（TREND/MARKET_CUSTOMER/COMPETITION/SELF/OPPORTUNITY/OPPORTUNITY_GAP——OD-2 口径）
- [ ] `BlmPlanningStatus` VO：plan_id/phase/current_step/completed_steps/**total_steps=8 钦定**（performance_gap+六子步骤+synthesis——进度百分比分母）/degraded_steps/timeline（frozen dataclass；**current_step 语义钦定**=最近完成步标识（快照写点在方法末尾——挂起第 N 步时轮询读到第 N-1 步），阶段 1 期间取 `"performance_gap"`（与 stage 值域同源，无 None 哨兵）；**timeline 条目结构钦定**：step/started_at/completed_at/status/summary_excerpt/degraded——兼作 AC-3「各步骤摘要」载体与 AC-1 顺序断言数据源，对齐 5-3 `ExecutionResult.step_summaries` 先例）
- [ ] `PerformanceGapArtifacts` VO：financial_gap/operational_gap/root_causes/portfolio_health（§17.4.2 产物字段语义——L1856-1896）+ **degraded/degrade_reason 两字段**（阶段 1 降级标记与 InsightStepResult 信封对称——VO 自身可判降级，免交叉查 degraded_steps）
- [ ] `InsightStepResult` VO（通用信封）：step/summary/findings/tool_used/evidence_refs/degraded/degrade_reason（结构化程度止于信封层——类型化 Schema 归 6-2；**降级步=完整信封**：degraded=True+degrade_reason+空 summary/findings，`insight_steps` 恒满 6 元素）
- [ ] `InsightSynthesis` VO：conclusions/degraded_inputs（列举降级输入——AC-6⑥ 规则载体；**synthesis 自身降级**时 conclusions=空列表+degraded_inputs 自含标记）
- [ ] `BlmPlanningContext`（`src/application/ports/blm_planning.py` 端口文件内定义）：profile/task/retrieved_evidence/prior_outputs（阶段 1 差距量化数据源口径——检索证据经此入上下文）
- [ ] **快照序列化契约**（Task 2 种子与 Task 3 写入同源——不先钦定则两侧各自为政）：BlmPlanningStatus ↔ 快照存储 `state_data` dict 的键名/枚举与 datetime 的 JSON 形态入本 SSOT；读径=经快照存储端口 load（hget 在存储实现内部，用例只持 session_id——不自持 Redis 客户端）
- [ ] 图 state schema 钦定（Task 0.1）：`SpBlmGraph` 专属 state（agent_id/plan_id/task/context/gap_artifacts/insight_step_results/synthesis/degraded_steps/timeline——**plan_id 必入 parameters 与 state**，事件与快照写入方依赖）
- [ ] `BlmPlanningResult` DTO（application 层）：plan_id/agent_id/gap_artifacts/insight_steps（六步产物列表，元素携带 started_at/completed_at——顺序断言观测面）/synthesis/degraded_steps/execution_ms

#### 统一端口定义注册与管理 (Port Contract)

- [ ] `BlmPlanningServicePort`：`src/application/ports/blm_planning.py`——`run_performance_gap_analysis(context) -> PerformanceGapArtifacts`、`run_insight_step(step, context, prior_outputs) -> InsightStepResult`、`synthesize_insights(step_outputs) -> InsightSynthesis`、`build_planning_context(profile_result, task) -> BlmPlanningContext`（组合注入既有端口：LLMClientPort/tool_execution_service/hybrid 检索/**EventPublisher（BlmStageCompleted 发布）/快照存储通道（步骤边界快照写）**——R2 规则：应用层端口组合注入 R1 基础端口）
- [ ] `GetBlmPlanningStatusPort` 或并入用例（Task 0 钦定最小面）
- [ ] 端口注册 `PortSpec`（name/version/interface/impl/lifetime/tags）+ registry 登记 + contract_gate 兼容检查
- [ ] 复用既有端口零重复定义：AgentEnginePort/LLMClientPort/ToolExecutionServicePort/检索端口/agent_tracing（继承表清单为准）
- [ ] 端口契约测试 `tests/contracts/test_port_contract_blm_planning.py`

#### 端口契约清单执行约束（强制）

- [ ] 本 Story 端口清单是唯一事实源：新增端口仅 `BlmPlanningServicePort`（+可选状态查询）；禁止新增与既有端口语义重复的接口
- [ ] registry/resolver/contract test/owner/version 五要素齐备；未过 Contract Gate 不得进实现 Task

#### 领域异常契约 (Domain Exception Contract)

- [ ] 归属 **planning 新子域**（物理码段 **(480,489)**——410/420/430/440/450/460/470 七代开段先例链的第八段；语义继承 `BusinessException` 基类）：`src/domain/exceptions/planning_exceptions.py`
- [ ] 候选编码 **480~482**：`PlanningNotFoundError`（480，plan_id 不存在）、`PlanningExecutionError`（481，全流程失败终态）、`PlanningStateError`（482，状态机非法推进——预留）。钦定流程（**唯一性+码段归属双查**）：读 `_code_ranges.py` CODE_RANGES+预留注释——business (201,209) 已满、financial (470,479) 为**双重成文预留**（`_code_ranges.py:167` 预留注释（L169 段条目行）+ `sisys-uni-exception-design.md` §3.3.2 编码表，471-479 不可占用）→ 取空闲段 480 开 planning 子域（全仓 `grep -rn "EXCEPTION_48" src/` 零占用验证——注：`grep EXCEPTION_47` 会命中 470 属预期勿混淆）
- [ ] 构造器携带领域上下文（plan_id/stage 等，`context` 字典暴露）；消息不泄露内部实现
- [ ] 完整 5 项 checklist：定义文件 / `_code_ranges.py` 子域映射（CODE_RANGES 条目 + `_CLASS_TO_SUBDOMAIN` 三条 + 段注释）/ `__init__.py` 暴露 + EXCEPTION_HTTP_MAP（`src/interfaces/api/exception_handlers.py:147`）/ 子域码段校验（`test_code_ranges.py` Rule 1 + `test_all_subdomain_ranges_are_valid`（同级子域段不重叠校验）——planning 段与 financial 段不重叠）/ `sisys-uni-exception-design.md §3.3.2` 编码表同步（逐码行+段表双处）
- [ ] 测试：构造/to_dict/HTTP 映射/编码唯一性（`test_error_code_uniqueness.py` + `test_code_ranges.py` 8 项全过）

#### API 契约 (API Contract)

- [ ] 本 Story 零 REST API（OD-5）——CLI 入口无 OpenAPI 面；`docs/api/openapi.yaml` 零改动（守护断言：文件 diff 为空）

#### 六边形架构约束（必须遵守）

四层定义与依赖方向矩阵按 template.md 全量执行。特别约束：
- [ ] domain 新增（枚举/VO/事件/异常）零第三方依赖
- [ ] `sp_blm_graph.py` 在 infrastructure/agent_orch/graphs/（R3：基础设施实现应用层端口）
- [ ] BlmPlanningService 在 application/services/（编排语义）——LLM/工具/检索经端口注入，不直连 infrastructure 实现
- [ ] CLI 在 entrypoints（D1 方案 A：入口在 `src/entrypoints/`，interfaces 层零组合根引用）

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] `tests/acceptance/test_acceptance_blm_planning.feature` + `.py`（OD-1 命名；R6 模板 `test_acceptance_postgresql_relational_layer.feature/.py` + 5-11 现代三件套形态）
- [ ] 场景配比（Task 0.3 钦定，目标 14 场景）：AC-1×3（流程执行/顺序断言/综合洞察）+ AC-2×2（单角色/守卫链）+ AC-3×2（状态查询中/终态）+ AC-4×2（事件发布/outbox 落行）+ AC-5×1（性能口径）+ AC-6×3（步级降级/顶层异常/449 降级——380 单测层锚）+ 收尾×1
- [ ] BDD 步骤：`event_loop.run_until_complete()`（禁 `@pytest.mark.asyncio`）；context dict fixture + 模块级 event_loop + `_run_async` 同循环三件套；延迟 import（Task 0-N 窗口期逐场景 failed 非 collection error）
- [ ] 真实服务优先：CEO Agent 真实实例化（Redis）+ 真实图引擎 + Fake LLM（可控结构化输出 + 失败注入）；检索/PG 门控动态 skip
- [ ] Edge Cases 含异常路径（AC-6 三场景，注入落点矩阵 Task 0.3 钦定：LLM 失败/工具 449/检索失败 × 采样步——验收层锚 449，380 单测层）
- [ ] 场景构造四钦定：执行中场景门控构造（`asyncio.Event` 挂起 Fake LLM + `asyncio.create_task` 后台执行 + 主协程轮询——**挂起步骤须 ≥第 2 步**，首步完成前无快照会 480）；事件场景 8 个 stage 值全集各恰一次断言+PlanningStarted 恰一行；降级场景注入落点矩阵（LLM 失败/449/检索失败 × 采样步——**验收层锚 449**，380 单测层）；检索门控档位清单（依赖检索的场景逐一标档动态 skip）
- [ ] 业务方评审通过（feature 文件确认）

**Task 0 完成标志：**
- [ ] 规范项全部定义完毕；Gherkin 已编写并确认失败（红阶段验证——预期红因=ModuleNotFoundError，StepDefinitionNotFoundError 非预期红，步骤函数 Task 0 全就位）
- [ ] **链路接线断言清单**已定义：①组合根 `register_port("blm_planning_service")`/`("blm_planning_use_case")`/`("blm_planning_status_use_case")` 装配验证（resolve 可达 + 注入链非 None + `agent_engine` lambda 增 `blm_planning_service` 注入）②新事件 reliable 通道真实发布验证（发布点代码位——**PlanningStarted 由 RunBlmPlanningUseCase 三守卫通过后、submit_graph 前发布（守卫前发布则 443 失败 run 留孤儿事件）、BlmStageCompleted 由 BlmPlanningService 各阶段/子步骤方法末尾发布** + event_channels.yaml/ChannelRouter.DEFAULT_MAPPINGS 双登记 + outbox 落行；一次全流程 outbox 落行量级=10 行：PlanningStarted 1+BlmStageCompleted 8+AgentDecided 1——Task 0.7 落 L170 锚注记）③图挂载**双点**验证（`_build_graph` SpBlmGraph 分派分支存在 + **图身份锚断言**：终态 state 含 BLM 专属键（insight_steps/synthesis）而非 BasicAgent 状态——5-3 验收图身份锚先例）④CLI `blm-plan` 子命令接线（entrypoints bootstrap 链）⑤StrategicAnalysisUseCase 保留注记落档核验（处置 #2 改判保留：deferred-work L125 注记 + 组合根零注册状态不变）⑥「已实现未接线」检查：本 Story 交付件零休眠（全部激活或显式登记）⑦SpBlmGraph 路径 AgentDecided 形态断言（投影键纯标量——DC-11）
- [ ] **前置留项清单八条裁定落档**（Subtask 0.7）

### TDD 循环约束（适用于每个 Task）

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过（**限本 Task 测试范围**——持续红文件除外：契约测试绿点在 Task 4 循环 A（与组合根注册同 Task 闭合——5-12 R1-19 同族教训），14 验收场景 Task 0 红至 Task 7 转绿，中途 Task DoD 不以全量跑为门） |
| **🟡 变异** | 对新行为契约的断言做突变注入-还原实证 | 改坏生产代码 → 测试红 → 还原 → 绿 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

禁止行为：先码后测 / 测试集中最后 Task / 跳过红阶段 / 跳过变异实证（Epic 4 教训：8/13 Story 恒真断言）。

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | Task |
|---------|------|----------|----------|------|
| TDD 单元测试 | domain VO/枚举/事件 | 枚举序/VO 不变量/事件 roundtrip | `tests/unit/domain/test_blm_domain_models.py` | Task 1 |
| TDD 单元测试 | planning 异常 | 构造/to_dict/HTTP 映射/编码唯一 | `tests/unit/domain/exceptions/test_planning_exceptions.py` | Task 1 |
| TDD 单元测试 | BlmPlanningService | 阶段方法/prompt 前缀/降级语义 | `tests/unit/application/test_blm_planning_service.py` | Task 3 |
| TDD 单元测试 | RunBlmPlanningUseCase | 编排顺序/守卫/状态推进/结果组装 | `tests/unit/application/test_run_blm_planning.py` | Task 2 |
| TDD 契约测试 | 端口契约 | 注册/版本/解析/兼容 | `tests/contracts/test_port_contract_blm_planning.py` | Task 0 编写 / **Task 4 循环 A 转绿** |
| TDD 契约测试 | 事件双登记守护 | yaml+DEFAULT_MAPPINGS 双登记/键一致/mode 一致 | `tests/contracts/test_event_channel_mapping_blm_planning.py` | Task 4 |
| TDD 验收测试 | Gherkin 场景 | 业务价值验收 | `test_acceptance_blm_planning.feature/.py` | Task 0/7 |
| SDD 架构验证 | 六边形约束 | 依赖方向/零依赖/图落位 | `tests/unit/architecture/test_blm_planning_arch.py` | Task 6 |
| TDD 单元测试 | CLI blm-plan | 命令注册/参数解析/进度输出/exit 语义（argparse 进程内直调 main+capsys+monkeypatch 先例） | `tests/unit/interfaces/cli/test_agent_cli.py`（▲ 扩展既有文件） | Task 4 |
| 集成测试 | 真实服务链 | 真实例化+图引擎+事件发布+状态快照 | `tests/integration/test_integration_blm_planning.py` | Task 5 |

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] 整体覆盖率 ≥80%（P0 阻断）；domain 层 ≥90%；应用层 ≥85%（epics L2064）、集成测试覆盖率 ≥75%（L2065）

#### 代码质量门禁

- [ ] `ruff check`/`mypy`/pre-commit 全过（mypy 含 tests/——5-9 教训）；无 P0/P1 审查问题
- [ ] 并行 `pytest tests/unit tests/integration tests/acceptance tests/contracts -n 8` 通过（显式四目录，禁裸 `tests/`——会挂起）；连续 5 次无随机失败

#### 测试隔离约束

- [ ] 测试隔离全约束按 template.md 执行（UUID 前缀租户隔离/BDD event_loop 模式/禁手动 delete）
- [ ] 本 Story 验收测试事件清理走 fixture teardown（K8 先例——断言失败也执行；outbox 事件无 poller 残留知悉注记归 L170 锚）

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 前两阶段流程执行 | Task 1 | VO/枚举/事件定义 | `test_blm_domain_models.py` |
| AC-1 | 前两阶段流程执行 | Task 2 | 用例编排（七步平移） | `test_run_blm_planning.py` |
| AC-1 | 前两阶段流程执行 | Task 3 | 阶段方法+图拓扑 | `test_blm_planning_service.py` |
| AC-1 | 前两阶段流程执行 | Task 5 | 真实服务链集成 | `test_integration_blm_planning.py` |
| AC-3 | 可视化数据面 | Task 5 | 状态快照执行中轮询（门控构造） | `test_integration_blm_planning.py` |
| AC-2 | CEO 单角色替代 | Task 3 | prompt 视角前缀（DC-2） | `test_blm_planning_service.py` |
| AC-2 | CEO 单角色替代 | Task 2 | 5.3 守卫链复用 | `test_run_blm_planning.py` |
| AC-3 | 可视化数据面 | Task 2 | 状态查询用例+Redis latest | `test_run_blm_planning.py` |
| AC-3 | 可视化数据面 | Task 4 | CLI 进度输出 | `test_agent_cli.py`（扩展） |
| AC-4 | 事件通道 | Task 1 | 事件 Schema | `test_blm_domain_models.py` |
| AC-4 | 事件通道 | Task 4 | 双登记守护+发布接线 | `test_event_channel_mapping_blm_planning.py` |
| AC-4 | 事件通道 | Task 5 | 真实 outbox 落行+stage 全集 | `test_integration_blm_planning.py` |
| AC-5 | 性能与成功率 | Task 3 | 8s 配置传递/温度档纪律 | `test_blm_planning_service.py` |
| AC-5 | 性能与成功率 | Task 5 | Fake LLM 口径基准+受控注入采样 | `test_integration_blm_planning.py` |
| AC-6 | 异常与降级 | Task 1 | planning 异常五件套 | `test_planning_exceptions.py` |
| AC-6 | 异常与降级 | Task 3 | 步级降级语义 | `test_blm_planning_service.py` |
| 全部 | 架构约束/收尾 | Task 6/7 | 架构验证/完成清单 | `test_blm_planning_arch.py`/收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部（规范输入源）

- [ ] Subtask 0.1: 数据模型/端口契约签名钦定（BlmPhase/MarketInsightStep 枚举 + **四 VO**——BlmPlanningStatus/PerformanceGapArtifacts/InsightStepResult/InsightSynthesis + BlmPlanningContext（端口文件内定义）+ BlmPlanningState 图 state（含 plan_id）+ **六子步骤语义配置表**（每步=视角前缀句（or.md 主导角色）/工具候选 slug 白名单（or.md 钦定映射，23 工具在位）/检索 query 模板/产物要点/**温度档**（8 步各档值或映射规则——AC-5 温度断言期望值唯一源）——prompt 模板按表参数化）+ BlmPlanningServicePort 四方法 + BlmPlanningResult DTO——本 Story 端口清单 SSOT）
- [ ] Subtask 0.2: 领域异常契约（**480~482 + planning 子域段 (480,489) 新开**——码段唯一性+归属双查（business (201,209) 已满、financial (470,479) 双重成文预留不可占）+ 五件套设计 + HTTP 映射预案）
- [ ] Subtask 0.3: Gherkin feature 编写（14 场景配比：AC-1×3 + AC-2×2 + AC-3×2 + AC-4×2 + AC-5×1 + AC-6×3[步级降级/顶层异常/**449 降级**——380 单测层锚] + 收尾×1；**检索门控档位清单钦定**：依赖检索可用性的场景逐一标档，检索不可达环境动态 skip；AC-1 Given 构造序列=3-1a 验收 embedding 探测+upsert 先例）
- [ ] Subtask 0.4: BDD 步骤实现三件套（context dict fixture/模块级 event_loop/`_run_async` + 延迟 import + 检索/PG 探测 skip 分档 + marker 分档）
- [ ] Subtask 0.5: 红阶段验证（全部场景 failed 非 collection error；红因核对口径记录）
- [ ] Subtask 0.6: 链路接线断言清单七件（见 Task 0 完成标志）
- [ ] Subtask 0.7: **前置留项清单八条裁定落档**（deferred-work.md 注记：#1 消费基建四件顺延+锚位调研 / #2 StrategicAnalysisUseCase **保留+取代注记**（改判——DC-9）+ L190 BLM 面局部核销注记 / #3 orchestration_service 保留+取代注记 / #4 记忆链路顺延 / #5 改串不触发 / #6 灰度评估不触发 / #7 retry-timeout 保持 6.6 / #8 checkpointer 保持 6.3）
- [ ] Subtask 0.8: DC 决策表复核落定（DC-1~DC-11，含 DC-5 差距分析工具归属终审——3-body/Alice 评审位；DC-11 为文档审查 Round 1 新增需重点复核）+ OD 五条登记
- [ ] Subtask 0.9: StrategicAnalysisUseCase **保留裁定核验**（处置 #2 改判保留——DC-9：组合根零注册状态不变（回归 grep 断言）+ deferred-work L125 取代事实注记落档（SOP 白名单（4.1c）与 ToolExecuted 统计链两独有能力归宿登记：工具面 6-2 评估 / 统计留项 #6）；**不删除**任何文件与测试——删除爆炸半径 7 测试文件+4 引用已实证，删除论据（5-3 全链内嵌）失实）

**完成标准/Definition of Done:**
- [ ] 规范全部定义；验收测试红阶段确认；deferred-work.md 八条注记落档；DC/OD 落定
- [ ] **提交时序纪律**（pre-commit mypy 对延迟 import 的未建模块报 import-not-found 阻断提交、CI 三测试 job 无 continue-on-error——5-5 先例）：`.feature` 于 Task 0 入仓；`test_acceptance_blm_planning.py` 随 Task 4（CLI/组合根落地后）批入仓；`test_port_contract_blm_planning.py` 同批（其「Task 0 编写」指规格设计，文件入仓随首个落地 Task）

### Task 1: 领域层——BLM 概念与异常（含完整 TDD 循环）

**关联 AC:** AC-1/AC-4/AC-6

#### TDD 循环 A：枚举与值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/test_blm_domain_models.py`（枚举序=or.md 顺序断言/VO frozen 不变量/事件 roundtrip + stage 字段枚举域断言 + `DomainEvent._registry` 自动注册断言） |
| 🟢 绿 | 实现 `src/domain/value_objects/blm_phases.py` + **扩展** `src/domain/events/planning_events.py`（新增两类事件——保留既有 `StrategicDeviationWarning` 勿整文件覆盖）+ `events/__init__.py` 导出更新 |
| 🟡 变异 | 枚举序打乱 → 顺序断言红；事件 stage 越域值 → 断言红 → 还原 |
| 🔄 重构 | docstring（Google 全中文）+ 类型注解 |

#### TDD 循环 B：planning 异常 + 注册五件套

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_planning_exceptions.py`（构造/context/to_dict/cause 链/frozen 继承链） |
| 🟢 绿 | 实现 `src/domain/exceptions/planning_exceptions.py`（480~482 + planning 段 (480,489) 新开） |
| 🟡 变异 | code 改碰撞值 → 唯一性断言红 → 还原 |
| 🔄 重构 | 注册四动作（CODE_RANGES planning 段+`_CLASS_TO_SUBDOMAIN` 三条/`__init__`/EXCEPTION_HTTP_MAP）+ `test_code_ranges.py` 校验 + 文档 §3.3.2 双表同步 + `test_exception_handlers.py` 联动 |

- [ ] Subtask 1.1: 🔴🟢🟡🔄 循环 A
- [ ] Subtask 1.2: 🔴🟢🟡🔄 循环 B

**完成标准/Definition of Done:**
- [ ] `poetry run pytest tests/unit/domain/ -v` 全绿（含 8 项自动校验）；grep 新码零碰撞

### Task 2: 应用层——用例与状态查询（含完整 TDD 循环）

**关联 AC:** AC-1/AC-2/AC-3

#### TDD 循环 A：RunBlmPlanningUseCase 编排

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_run_blm_planning.py`（七步编排顺序/守卫 443·441·447 触发/agent_id str 序列化/终态组装/**PlanningStarted 发布调用断言（三守卫通过后、submit_graph 前——守卫前发布则 443 失败 run 留孤儿事件）**/**全降级→481 抛出断言（终态组装处，len(degraded_steps)==total_steps）**/7-8 降级→成功 DTO——AsyncMock spec=Port 工厂模式） |
| 🟢 绿 | 实现 `src/application/use_cases/run_blm_planning.py`（Mock 端口注入最小实现） |
| 🟡 变异 | 守卫顺序交换 → 断言红；degraded_steps 漏记 → 断言红 → 还原 |
| 🔄 重构 | docstring + 端口类型注解 |

#### TDD 循环 B：GetBlmPlanningStatusUseCase + Redis latest

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写状态查询测试（**读侧**：执行中/终态/快照读取一致/**无快照→PlanningNotFoundError(480) raise**（FakeRedis 空键）——写入方唯一归 BlmPlanningService 各方法末尾（DC-6/Task 3 循环 A），本用例只读、种子按序列化契约预置） |
| 🟢 绿 | 实现状态查询用例（**读侧**——三层键形态读取：`BLM_PLANNING_SESSION_PREFIX` 单源常量 → session_id=`blm-planning-{plan_id}` → 最终键 `sisys:snapshot:blm-planning-{plan_id}`，hget `"latest"`；「写读一致」断言由 Task 3 写入方测试与集成 Subtask 5.2 承载，本 Task 零写入） |
| 🟡 变异 | 进度计算改错 → 百分比断言红 → 还原 |
| 🔄 重构 | 5-10 Recorder 键控先例对齐注记 |

- [ ] Subtask 2.1: 🔴🟢🟡🔄 循环 A
- [ ] Subtask 2.2: 🔴🟢🟡🔄 循环 B

**完成标准/Definition of Done:**
- [ ] 用例层测试全绿；覆盖率 ≥85%

### Task 3: BLM 规划服务与图实现（含完整 TDD 循环）

**关联 AC:** AC-1/AC-2/AC-5/AC-6

#### TDD 循环 A：BlmPlanningService 阶段方法

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_blm_planning_service.py`（阶段 1 四字段产物/六子步骤顺序/角色视角前缀+工具候选白名单 prompt 断言（语义配置表驱动）/检索证据注入调用/`_structured_call` 444 纪律/8s 配置传递断言/步级降级（449/380 捕获+直接推理续行）/降级下游标注注入（⑥规则）/各方法末尾快照写+事件发布调用断言） |
| 🟢 绿 | 实现 `src/application/services/blm_planning_service.py` + `blm_planning_prompts.py`（按六子步骤语义配置表参数化；LLM/工具/检索/EventPublisher/快照通道经端口注入；每步时序钦定：确定性工具候选→工具先行执行（失败/未选→直接推理）→检索证据+工具输出注入→单次结构化 LLM 调用；**瞬时故障两级设计=服务内重试**：每步 asyncio 单次重试循环（瞬时 LLM/网络失败）→仍败则步级降级——**不用 per-node RetryPolicy**（其重试耗尽=异常上抛=图失败中断，与 AC-6①「继续推进」语义互斥，且服务全捕获下恒不触发=死配置）） |
| 🟡 变异 | 降级分支删除 → degraded_steps 断言红；prompt 前缀删 → AC-2 断言红 → 还原 |
| 🔄 重构 | 温度分档纪律对齐（档值以语义配置表为唯一源——五档键与 BLM 8 步无直接映射）+ 8s timeout 复用 + docstring |

#### TDD 循环 B：SpBlmGraph 图拓扑

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写图拓扑测试（节点集=阶段1+六子步骤+综合；**图形态钦定：8 节点+7 条直连边+END**——降级在 BlmPlanningService 方法内全量捕获（AC-6①），节点永不因业务失败抛错，顺序段无条件分支点，永真条件边与直连边行为完全等价（先例 `single_agent_workflow_graph.py:107-120` 条件边仅用于 verify 分流/reflect 重试两个**真**分支点，纯顺序段全部直连）；节点集完整性/边序/`compile()` 无 checkpointer 断言——R1-DF5 对齐） |
| 🟢 绿 | 实现 `src/infrastructure/agent_orch/graphs/sp_blm_graph.py` + 引擎挂载**双点**（`_SUPPORTED_GRAPHS` 增名 + `_build_graph` 增 `if graph_name == "SpBlmGraph"` 分派分支——含 `blm_planning_service` 未注入守卫（L190-197 ValidationError 先例），漏分支将静默回退 BasicAgent）+ 构造器尾部 `blm_planning_service: BlmPlanningServicePort \| None = None` 注入位 + 节点适配器（SingleAgentWorkflow 先例模式）+ **AgentDecided 投影分支**（DC-11：SpBlmGraph 五键纯标量投影——防 VO 实例入事件 payload） |
| 🟡 变异 | **边序交换/漏节点** → 图身份锚或枚举序断言红（「条件边改直连」变异在本图形态下行为等价、物理不可红——不设）；**分派分支删除 → 图身份锚断言红**（终态 state 含 BLM 专属键非 BasicAgent 状态）→ 还原 |
| 🔄 重构 | docstring 注明 Epic 10 六阶段扩展锚（OD-4） |

- [ ] Subtask 3.1: 🔴🟢🟡🔄 循环 A
- [ ] Subtask 3.2: 🔴🟢🟡🔄 循环 B

**完成标准/Definition of Done:**
- [ ] 服务+图测试全绿；`submit_graph("SpBlmGraph")` 全链可达

### Task 4: 组合根接线 + 事件通道登记 + CLI（含完整 TDD 循环）

**关联 AC:** AC-3/AC-4

#### TDD 循环 A：组合根与事件双登记

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写接线测试（resolve("blm_planning_service"/"blm_planning_use_case"/"blm_planning_status_use_case") 可达且注入链非 None/`agent_engine` lambda 增 `blm_planning_service` 注入断言/event_channels.yaml + ChannelRouter.DEFAULT_MAPPINGS 含 PlanningStarted·BlmStageCompleted **双登记守护断言**（形态对齐 `test_event_channel_mapping_drift.py`：存在性×2/键一致/mode 一致（**两事件均 reliable 钦定**）/description 非空）/CheckpointReached 零发布负向断言——**注**：strategic_analysis 零注册核验**不入契约测试**（DC-9 最终定夺锚 Epic 7 三向未定——固化「零注册」为回归面会形成跨 Story 耦合，归 Subtask 0.9 时点单次核验）） |
| 🟢 绿 | `composition_root.py` 注册族（含 `agent_engine` lambda 增 `blm_planning_service=resolver.resolve(...)`——`langgraph_engine` L51 尾部可选注入位消费）+ `configs/event_channels.yaml` + ChannelRouter 同步 + **契约测试转绿**（绿点本 Task 闭合——5-12 R1-19 教训） |
| 🟡 变异 | yaml 删一行事件 → 守护断言红 → 还原 |
| 🔄 重构 | PortSpec 元数据齐备（name/version/lifetime/tags） |

#### TDD 循环 B：CLI blm-plan 子命令

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 CLI 测试（**argparse 进程内直调** `main([...])` + capsys + monkeypatch 模块级 bootstrap/resolve 替身——`tests/unit/interfaces/cli/test_agent_cli.py` 先例（1138 行，5-1 起）：命令注册/参数解析（`-a/--agent-id`、`-t/--task`——run-task 先例）/摘要输出含进度/失败 exit 语义——成功失败均退出可观测；UUID 守卫先于 bootstrap、`type=` 禁用 uuid.UUID（argparse 会把 ValueError 转 usage error exit 2 绕过异常体系——CLI 文件头纪律）） |
| 🟢 绿 | `src/entrypoints/agent_cli.py` 增 `blm-plan`（`-a/--agent-id` + `-t/--task` + 可选 `--plan-id`）+ `_print_blm_progress`（`_print_workflow_summary` 先例模式） |
| 🟡 变异 | 输出删进度行 → 断言红 → 还原 |
| 🔄 重构 | `_ensure_bootstrapped`/`_close_connection_pools` 模式对齐 |

- [ ] Subtask 4.1: 🔴🟢🟡🔄 循环 A
- [ ] Subtask 4.2: 🔴🟢🟡🔄 循环 B

**完成标准/Definition of Done:**
- [ ] 链路接线断言**七件**全绿（Task 0.6 清单——①②④⑦由本 Task 交付；③图挂载归 Task 3 DoD、⑤保留核验归 Task 0.9、⑥零休眠归 Task 7 收尾）；本 Story 交付件零休眠

### Task 5: 集成测试——真实服务链（验证型）

**关联 AC:** AC-1/AC-3/AC-4/AC-5

> 套件型豁免条款（5-9/5-10 先例）：本 Task 为验证型集成测试，以变异替代 TDD 红绿——对关键断言做突变注入-还原实证。

- [ ] Subtask 5.1: 场景①真实实例化链（Redis 真 CEO Agent + 真档案加载 + 真图引擎 + Fake LLM 可控输出——全流程跑通 + 顺序断言**双锚**（`insight_steps[i].step == EXPECTED_ORDER[i]` 枚举序独立构造 + 时间戳非重叠 `started_at[i] >= completed_at[i-1]`——与 AC-1 同构）+ 图身份锚断言（终态含 BLM 专属键））
- [ ] Subtask 5.2: 场景②状态快照（**执行中轮询——门控构造**：`asyncio.Event` 挂起 Fake LLM + `asyncio.create_task` 后台执行 + 主协程轮询快照；终态断言 total_steps=8 全 completed + Redis latest 写读一致——FakeRedis 真跑）
- [ ] Subtask 5.3: 场景③真实事件发布（resolve 真实 event_publisher/DualChannelEventBus + PG event_outbox 落行断言——PG 门控连接+表存在双预检动态 skip，5-4 R1-F07 先例）
- [ ] Subtask 5.4: 场景④性能基准（Fake LLM 口径 P95<30s 分级断言 + 六子步骤 ≥20 次**受控失败注入**采样成功率≥95%（降级成功计入——零注入恒 100% 无鉴别力）+ 8s 配置传递断言 + 口径差 docstring 声明）
- [ ] Subtask 5.5: 变异实证四锚（顺序断言/进度计算/outbox 落行/降级清单——各改坏→红→还原→绿）
- [ ] Subtask 5.6: 清理 fixture teardown 化（K8 先例——断言失败也执行；outbox 残留知悉注记）

### Task 6: SDD 架构约束验证测试（验证型）

**关联 AC:** 六边形约束

- [ ] Subtask 6.1: `tests/unit/architecture/test_blm_planning_arch.py`——domain 新增文件零第三方 import（AST 扫描验证器 A 先例）/依赖方向矩阵/`sp_blm_graph.py` 落位断言/CLI 在 entrypoints 层断言
- [ ] Subtask 6.2: 架构验证器实跑 + 违规即失败报告

### Task 7: 开发结束验收测试

**关联 AC:** 全部收尾

- [ ] Subtask 7.1: 收尾验收场景（feature 收尾场景：`src` 完成清单 + 四测试目录完成清单逐项确认）
- [ ] Subtask 7.2: BDD 步骤实现 + 全场景绿
- [ ] Subtask 7.3: `pytest tests/unit tests/integration tests/acceptance tests/contracts` 四目录全绿 + `ruff check` + `mypy` 收尾校验
- [ ] Subtask 7.4: deferred-work.md 留项台账更新（本 Story 新增留项按 gap 四要素登记；前置清单八条处置核销注记核对）

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束

- **六边形四层 + 依赖方向矩阵**：domain 零外部依赖；application 仅依赖 domain；图实现在 infrastructure；入口在 entrypoints（D1 方案 A）
- **设计规则**（用户钦定 R1~R4）：R1 领域层统一抽象基础端口；R2 应用层具体应用端口组合注入/继承 R1 端口（BlmPlanningServicePort 组合注入 LLMClientPort/工具/检索）；R3 基础设施层实现应用层端口（SpBlmGraph/服务实现）且支持同类技术扩展；R4 接口层/入口适配外部请求与响应格式化（CLI blm-plan）
- **事件双登记纪律**：新事件必须同时更新 `configs/event_channels.yaml` 和 `ChannelRouter.DEFAULT_MAPPINGS`（单事件按 delivery_mode 走单通道——DC-8）
- **异常体系红线**：三条 grep 自查零输出；新异常五件套
- **测试隔离**：TestTenant UUID 前缀；BDD `event_loop.run_until_complete()`；禁手动 delete/truncate

### 关键架构决策（DC——Task 0.8 复核落定）

| # | 决策 | 预判结论 | 依据 |
|---|------|---------|------|
| DC-1 | BLM 图骨架 | 新建 `SpBlmGraph`（前两阶段专用），经 `LangGraphEngine.submit_graph` 通道执行，节点适配器模式平移 SingleAgentWorkflow 先例 | architecture L333/L3244 落位钦定 + 5-3 图模式成熟 |
| DC-2 | CEO 单角色替代 | 角色语义经阶段 prompt 视角前缀承载，零多 Agent 实例化 | FR-SP-01 括注 + PRD L453 MVP 排除 |
| DC-3 | 六子步骤执行口径 | 顺序执行（or.md 语义依赖）+ 每步时序钦定：确定性工具候选（语义配置表白名单）→工具先行执行（失败/未选→直接推理）→检索证据+工具输出注入→**单次**结构化 LLM 调用；synthesize_insights 为单次 LLM 聚合调用（计入级联）；「基础」=通用信封无类型化 Schema 无每步 Checkpoint | 6.1/6.2 边界（epics L2089-2090）+ 30s 预算（8 次串行调用均值目标 ≤3.75s/次） |
| DC-4 | 阶段间上下文 | 图 state 累积传递（prior_outputs 注入下一步），单 run 闭合；跨 run/记忆归 6.3+ | 调研：BLM 两阶段独立 run 零携带 + 记忆链路正交 |
| DC-5 | 差距分析工具归属 | **CEO 裸推理 + 既有 23 工具复用**（六子步骤语义配置表钦定每步工具候选白名单——or.md 建议工具映射；白名单外/未选→直接推理）；不新增 gap 专用工具。**两套工具名单机制并存钦定**：system 面注入档案 tools_l1 全量（5-3 先例——R2 幻觉名缓解），user 面注入该步候选子集（语义配置表），AC-2 断言锚 user 面 | 调研：无 gap 工具但相邻能力齐备（kpi-tree/bsc-scorecard/swot-tows/pestel/five-forces/appeals/vrio 全在位）；YAGNI——**3-body/Alice 终审位（Task 0.8）** |
| DC-6 | 可视化数据面 | `BlmPlanningStatus` 内存真源 + Redis latest 快照（**三层键形态**：`BLM_PLANNING_SESSION_PREFIX` 单源常量→session_id `blm-planning-{plan_id}`→最终键 `sisys:snapshot:blm-planning-{plan_id}`，pipeline hset `"latest"`+TTL 原子——5-10 先例形态）+ CLI 进度输出；**粒度=步骤边界快照点**（BlmPlanningService 各方法末尾写入——同步阻塞链下「任一时点」物理不可达；无订阅面无实时推送，realtime 订阅面可选归 6-9 评估） | 5-10 Recorder 键控三层先例 + epics L2060 后端数据面口径 |
| DC-7 | 性能计量口径 | P95<30s 以 Fake LLM 管线开销计量；真实 LLM 延迟显式出栈（docstring 声明）；真实全链归部署验证 | 5-8 AC-5 + 5-2 R1-DF3 先例 |
| DC-8 | 事件面 | `PlanningStarted` + `BlmStageCompleted` 两事件**均 reliable 单通道**（对齐 AgentDecided 配置先例——`DualChannelEventBus.publish` 按事件单模式分派，REALTIME 仅 Redis / RELIABLE 仅 Outbox，一事件不走双通道；低延迟订阅面如 6-9 需要，届时评估升级）；「双登记」=event_channels.yaml + DEFAULT_MAPPINGS 两处（契约测试形态对齐 `test_event_channel_mapping_drift.py`）；CheckpointReached 不发布（6.3 语义分立——5-10 OD-6/DC-8 裁定） | or.md L138 事件链 + AgentDecided 配置先例 + 5-10 裁定 |
| DC-9 | StrategicAnalysisUseCase | **保留 + 取代注记，不删除**——删除论据失实（5-3 链无 SOP 白名单——`skill_loader` 注入后零使用；无 ToolExecuted 发布——「零能力损失」不成立）+ 爆炸半径非零（src 引用 4 处 + 测试 7 文件）；休眠零持有成本，最终废弃定夺与 DC-10 同批锚 Epic 7 | 前置留项 #2 文档审查轮复核改判；Task 0.9 核验 |
| DC-10 | orchestration_service | 保留不删；agent_reasoning 分支追加取代事实注记，最终定夺锚 Epic 7 | 前置留项 #3：data_pipeline 轨是 6.5 报告管线候选宿主 |
| DC-11 | SpBlmGraph 的 AgentDecided 处置 | 引擎对全部图**无条件发布** AgentDecided（`langgraph_engine.py:127-131`）且投影分支只认 SingleAgentWorkflow（L237）——SpBlmGraph 增**五键纯标量投影分支**（planning_status/摘要截断键等，L241-247 先例平移），防 VO 实例入事件 payload（4-5 UUID/VO 禁入事件教训——序列化炸且被 try/except 吞）；**confidence 显式钦定**：引擎默认回落 0.9 常量（`result.get("confidence", 0.9)`）正是 5-3 DC-6 修掉的假置信度——SpBlmGraph 投影显式置真实值（state 无置信度面则置 0.0+注记），勿吃默认 | Task 0.6 ⑦形态断言 + 5-3 五键投影先例 |

### 风险登记表

| # | 风险 | 缓解 |
|---|------|------|
| R1 | 30s 预算 vs 8s 单调用上限 × **8 次串行级联**：无重试口径最坏 64s；服务内瞬时重试（Task 3 循环 A 两级设计）叠加口径最坏 128s（2×8s/步），均值目标 ≤3.75s/次（不含重试轮） | DC-3 轻量化（每步单次调用+精简 prompt+上下文截断）；Fake LLM 口径计量（DC-7）；真实口径余量声明归部署验证项 |
| R2 | 幻觉工具名 380 穿透（L190 台账——5-3 链面现状不变） | prompt 工具名单约束（tools_l1 注入）+ 步级捕获 449/380 记 degraded（AC-6⑤——6.1 新增，BLM 面局部核销 R1-DF1；5-3 L252-254 为空工具名正常分支非降级先例） |
| R3 | InMemorySaver TTL 1h/1000 条 + 图无 checkpointer | 结果即取即用（终态 state 直读组装返回）；跨 run 恢复零依赖（归 6.3） |
| R4 | CLI 无 poller → 新增 RELIABLE 事件滞留 outbox | 既有登记（L170）知悉；验收清理 teardown 化；测试面残留量级注记归 L170 锚 |
| R5 | 消费基建键语义错位被误激活 | 前置留项 #1 裁定：禁激活；锚位顺延+调研义务 |
| R6 | 上下文膨胀（七步产物累积注入） | 每步产物摘要化注入（summary_excerpt ≤200 截断先例）；完整产物仅入结果 DTO |
| R7 | 双状态体系陷阱（AgentStatus 长眠先例 R1-F13） | BLM 流程状态用独立 `BlmPlanningStatus` VO（不触碰 AgentStatus 五态机）；状态体系归一留 Epic 9 |

### 代码审查周期知悉注记

- 汇总数字禁概数（Epic 5 回顾行动项 3）：本 Story 全部计数逐行点数；机器复算在 R5 终审轮执行
- 「X 先例」引用前核对先例台账状态（模板审计义务——行动项 4）
- 游离提交禁令：审查周期内所有变更走本 Story 记录

### 项目结构说明（★新建 ▲修改 零删除）

```
src/
├── domain/
│   ├── value_objects/blm_phases.py                    ★ BlmPhase/MarketInsightStep 枚举 + 四 VO（BlmPlanningStatus/PerformanceGapArtifacts/InsightStepResult/InsightSynthesis）
│   ├── events/planning_events.py                      ▲ 扩展：新增 PlanningStarted/BlmStageCompleted（保留既有 StrategicDeviationWarning）
│   ├── events/__init__.py                             ▲ 导出更新
│   ├── exceptions/planning_exceptions.py              ★ 480~482（planning 子域段 (480,489) 新开）
│   ├── exceptions/_code_ranges.py                     ▲ planning 段 + _CLASS_TO_SUBDOMAIN 三条
│   └── exceptions/__init__.py                         ▲ 暴露新异常
├── application/
│   ├── ports/blm_planning.py                          ★ BlmPlanningServicePort + BlmPlanningContext + BLM_PLANNING_SESSION_PREFIX 单源常量（文件随 Task 2 绿创建——Task 0 仅规格钦定）
│   ├── use_cases/run_blm_planning.py                  ★ RunBlmPlanningUseCase
│   ├── use_cases/get_blm_planning_status.py           ★ 状态查询用例
│   ├── services/blm_planning_service.py               ★ 阶段/子步骤方法实现（含步骤边界快照写入+事件发布）
│   └── services/blm_planning_prompts.py               ★ prompt 模板（六子步骤语义配置表参数化：视角前缀+工具候选白名单）
├── infrastructure/
│   └── agent_orch/
│       ├── graphs/sp_blm_graph.py                     ★ 前两阶段图（OD-4 落位，Epic 10 扩展锚；8 节点 7 直连边——重试/降级在服务内）
│       └── langgraph_engine.py                        ▲ _SUPPORTED_GRAPHS 增名 + _build_graph 分派分支 + 构造器 blm_planning_service 注入位 + AgentDecided 投影分支（DC-11）
├── composition_root.py                                ▲ 注册族（blm_planning_service/use_case/status_use_case + agent_engine lambda 注入）
├── configs/event_channels.yaml                        ▲ 两事件登记（均 reliable）——位于**仓根** configs/，非 src/ 子树（树形并列示意）
│   （ChannelRouter 所在 messaging 模块）               ▲ DEFAULT_MAPPINGS
├── interfaces/api/exception_handlers.py               ▲ EXCEPTION_HTTP_MAP 登记三异常
└── entrypoints/agent_cli.py                           ▲ blm-plan 子命令（argparse，-a/-t 参数风格）
tests/
├── unit/domain/test_blm_domain_models.py              ★
├── unit/domain/exceptions/test_planning_exceptions.py ★
├── unit/application/test_blm_planning_service.py      ★
├── unit/application/test_run_blm_planning.py          ★
├── unit/architecture/test_blm_planning_arch.py        ★
├── unit/interfaces/cli/test_agent_cli.py              ▲ blm-plan 用例扩展
├── integration/test_integration_blm_planning.py       ★
├── contracts/test_port_contract_blm_planning.py       ★（Task 0 编写 / Task 4 循环 A 转绿）
├── contracts/test_event_channel_mapping_blm_planning.py ★ 双登记守护断言
└── acceptance/test_acceptance_blm_planning.feature/.py ★
```

### 前一个故事学习经验（Story 5-12 → 6.1）

**来源:** [Story 5-12-financial-modeling-valuation](./5-12-financial-modeling-valuation.md)（Fraction 双源纪律在案）+ Epic 5 审查周期通例 + Story 5-3 直承遗产（分源如实标注：5-12 学习节正式来源为 5-11，下列四条中仅第一条在 5-12 实质在案）

**关键学习/Key Learnings:**
- 【5-12 在案】Fraction 独立复算双源纪律（禁被测引擎生成 expected 的循环自证）——BLM 产物断言用独立构造的期望形态
- 【Epic 5 周期通例】「汇总数字失实族」是审查周期最高频问题族——本 Story 计数全部点数 + R5 机器复算预留
- 【5-12 L74 重组表述】验收测试基建：多行 @scenario 字面量路径+场景绑定与步骤实现交替+AC 横幅分组三要素；真实断言禁 then-pass + context dict fixture + 模块级 event_loop + `_run_async` 同循环；验收文件延迟 import
- 【5-3 直承】agent_id 必须 str 序列化进 parameters；`executed_phases` 末元素语义对齐；per-call 8s 上限纪律

**应用到本故事/Applied to This Story:**
- [ ] 循环自证红线：六子步骤顺序断言不经被测服务生成期望
- [ ] 全部计数点数 + R5 机器复算预留
- [ ] 5-3 八项遗产逐条对齐（见 Dev Notes 风险表与 DC 表）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.3 |
| **Version** | create-story workflow v2.9.0 模板 |
| **Execution Date** | 2026-10-31 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（L1999-2077） |
| **架构文档** | `docs/architecture/architecture.md`（§17.5 战略规划架构）+ `docs/architecture/sisys-core-domain-design.md` §17.4（BLM 状态机伪码——该文件无 §17.5） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/5-12-financial-modeling-valuation.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **前置留项台账** | `_bmad-output/implementation-artifacts/deferred-work.md`（八条出处见前置依赖节） |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` L2040-2077 提取（含 FR-SP-01/or.md L379-415 溯源）
- [x] 架构约束从 architecture.md §17.5 + core-domain-design §17.4 提取
- [x] 前一个故事学习经验整合（5-12 + 5-3 八项遗产）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（Task 0~7 + 变异实证）
- [x] 项目结构对齐统一规范
- [x] 前置留项清单八条编制（Epic 5 回顾行动项 1a 首秀）
- [x] 三路并行调研（规划权威面/现有代码七视角/范式与模板）事实锚定

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/6-1-blm-first-two-phases.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- 见「项目结构说明」★/▲ 清单（**18 新建 + 11 修改 + 0 删除**——src 8★10▲、tests 10★1▲；DC-9 改判保留后零删除）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 6.1 |
| **Story Key** | 6-1-blm-first-two-phases |
| **File** | `_bmad-output/implementation-artifacts/stories/6-1-blm-first-two-phases.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 6: 战略规划流程 (BLM 前两阶段) |
| **价值组** | 战略规划与审批能力 |
| **优先级** | P0-1 |
| **覆盖 FR** | FR-SP-01（P0） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0~7，Subtask 29）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-6）
3. [x] Architecture constraints extracted 架构约束已提取（R1~R4 + 六边形矩阵 + 落位钦定）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`
6. [x] 前置留项清单八条 + 知悉注记三条编制完毕
7. [x] 范围边界 10 行（✅4 + ❌6）+ OD 五条 + DC 十一条（R1 新增 DC-11）+ 风险七条

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 编号规则：R<轮>-<序>（与本 Story 风险表 R1~R7 及先例 Story 的 R1-DFn/R1-Fn 命名空间分立）。Round 1：三视角调研（4 Agent）+ 三视角审查（一致性/可行性/科学性）+ 主会话 6 组实测定谳。Round 2：回归核查 + 增量正确性双视角（含 R1 台账勘误两处：R1-1/R1-6 所引「Rule 5」实为 `test_all_subdomain_ranges_are_valid`（test_code_ranges.py 仅命名 Rule 1~4）、构造器尾参行号 L57 实为 L51）。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | 异常码段 471~473 落在 financial **双重成文预留段** (470,479)（`_code_ranges.py:169` 注释 + `sisys-uni-exception-design.md` §3.3.2 双表），business 物理段 (201,209) 已满——CI Rule 1/Rule 5 必红；「grep EXCEPTION_47」会命中 470，流程自相矛盾 | P0 | 改钦定 **planning 新子域段 (480,489)**（八代开段先例链），异常 480~482；验证法升级「唯一性+码段归属双查」；异常契约节/Subtask 0.2/Task 1 循环 B/结构清单/Task 0.2 五处传播位同步；四件套扩五件套 |
| R1-2 | StrategicAnalysisUseCase「删除爆炸半径实证为零」失实（src 引用实为 4 处 + 测试面 7 文件：2 单测 import/1 集成实例化/4 架构路径断言）；「5-3 已内嵌 SOP 白名单→ToolExecuted 全链」论据两环失实（5-3 的 `skill_loader` 注入后零使用、ExecutionContext 无 extensions、零 ToolExecuted 发布）——「零能力损失」不成立（SOP 白名单 4.1c 接线与 ToolExecuted→统计链均该用例独有） | P0 | DC-9 **改判保留 + 取代注记**（休眠零持有成本，最终定夺与 DC-10 同批锚 Epic 7）；留项 #2/Subtask 0.9（改核验型）/Task 0.6⑤/结构清单（✂ 移除，0 删除）四处同步；能力归宿登记（SOP 白名单→6-2 评估 / ToolExecuted 统计链→留项 #6） |
| R1-3 | `agent_cli.py` 实为 **argparse 标准库**（文件头自证「零额外依赖」），Task 4 循环 B「Typer runner」测试载具错误（仓内 CLI 测试先例=进程内直调 `main([...])`+capsys+monkeypatch） | P0 | 测试形态改 argparse 直调先例；参数风格 `-a/--agent-id`、`-t/--task`（run-task 先例）；传承「UUID 守卫先于 bootstrap」「`type=` 禁 uuid.UUID（argparse 转 exit 2 绕过异常体系）」纪律；测试归属 `tests/unit/interfaces/cli/test_agent_cli.py`（▲ 扩展） |
| R1-4 | `src/domain/events/planning_events.py` **已存在**（含 StrategicDeviationWarning）——「新建文件」口径按字面执行将毁既有事件类 | P0 | 六处传播位改「**扩展既有文件**」：需新建清单①⑤/事件 Schema 节/Task 1 循环 A 绿/结构清单 ★→▲+`__init__.py` ▲/文件计数 |
| R1-5 | AC-4「事件经双通道投递」与 `DualChannelEventBus.publish` 机制不符（实测定谳：按事件**单模式**分派——REALTIME 仅 Redis / RELIABLE 仅 Outbox，一事件不走双通道） | P0 | 改「按 delivery_mode 经对应通道投递」；两事件**均钦定 reliable**（AgentDecided 配置先例，outbox 落行断言对两事件适用）；DC-8 同步 + 契约守护测试形态对齐 `test_event_channel_mapping_drift.py`；补 8 个 stage 值全集恰一次断言 |
| R1-6 | 图挂载描述不完整：`_SUPPORTED_GRAPHS` 仅告警判据，真分派在 `_build_graph` 显式 if 分支——只加集合漏分支将**静默回退 BasicAgent**；引擎构造器仅单一 `workflow_service` 注入位，SpBlmGraph 所需 `BlmPlanningServicePort` 无注入通道 | P1 | 挂载**双点**+构造器尾部 `blm_planning_service` 可选注入位（L57 先例）+组合根 `agent_engine` lambda 注入+**图身份锚断言**（继承表/Task 0.6③/Task 3 循环 B 绿与变异/结构清单四处同步） |
| R1-7 | 引擎对全部图**无条件发布** AgentDecided（`langgraph_engine.py:127-131`）且五键投影分支只认 SingleAgentWorkflow（L237）——SpBlmGraph 将全量 state 透传，VO 实例入事件 payload（4-5 UUID/VO 禁入事件教训：序列化炸且被 try/except 吞） | P1 | 新增 **DC-11**：SpBlmGraph 五键纯标量投影分支（L241-247 先例平移）；Task 0.6 清单六件→**七件**；AC-4 验证标准补形态断言 |
| R1-8 | AC-3「执行中任一时点状态可查询」物理不可达（CLI→use case→submit_graph 同步阻塞链看不到步骤边界）；状态快照与事件的**写入点/发布点**全文未钦定；Redis 键 `blm-planning-{plan_id}` 裸键形态不合三层先例（前缀常量单源→session_id→`sisys:snapshot:` 命名空间+hset latest+TTL） | P1 | 改「**步骤边界快照点**」+ 门控构造法（`asyncio.Event` 挂起 Fake LLM+`asyncio.create_task`+主协程轮询）；写入点钦定（BlmPlanningService 各方法末尾写快照+发事件，use case 发 PlanningStarted+终态组装）；三层键形态定稿（DC-6/AC-3/Task 2 循环 B/继承表四处） |
| R1-9 | AC-6⑤「380 降级按 5-3 `L252-254` 先例」引用失实——该行为**空工具名正常分支**非降级；幻觉名（非空未注册）实走 449 预检或 380 **穿透**（R1-DF1 台账原文），与知悉注记自相矛盾；降级的下游消费语义未定义（prior_outputs 含 degraded 产物时下游/synthesis/阶段间如何处理） | P1 | AC-6⑤ 改写为 6.1 **新增步级 449/380 捕获**（BLM 面局部核销 R1-DF1——L190 台账注记联动）；补 **⑥降级下游三规则**（降级标注注入下游/synthesis 列举 degraded 输入/阶段 1 全降级阶段 2 照常带标记）+「上游降级→下游含标注」断言 |
| R1-10 | BlmPlanningStatus 规格三缺口（timeline 条目结构未定义——AC-1 顺序断言数据源悬空；「各步骤摘要」无载体字段；total_steps 口径未钉死）；端口返回类型 InsightStepResult/InsightSynthesis/BlmPlanningContext **无 Schema 定义**（6.1/6.2 结构化边界不可判，「三 VO」指代不明）；图 state schema 未钦定（plan_id 不入 state 则事件/快照无锚） | P1 | Task 0.1 钦定：timeline 条目结构（step/started_at/completed_at/status/summary_excerpt/degraded——兼摘要载体）+ **total_steps=8** + **四 VO**（+InsightStepResult 通用信封/InsightSynthesis）+ BlmPlanningContext（端口文件内）+ **BlmPlanningState**（plan_id 入 parameters 与 state）；范围边界 6.2 行补「通用信封 vs 类型化 Schema」 |
| R1-11 | AC-5 两断言在 Fake 口径下不可达/无鉴别力（8s 超时执行在真实 LLM 客户端内——Fake 只能验参数；零注入 20 次采样恒 100%）；风险 R1 算术错误（「7+ 次×8s 最坏 56s」自相矛盾——级联实为 8 次，最坏 64s） | P1 | 8s 改**配置传递断言**（Fake 捕获 structured_generate 实参 `timeout==8.0` 含温度档）；采样改**受控失败注入**口径（降级成功计入≥95%）；R1 改 8 次×8s=64s + 均值目标 ≤3.75s/次（真实口径预算声明归部署验证） |
| R1-12 | 一致性缺口族（P1×1+P2×6+P3×9 归并）：文件计数失实（「12 新建+5 修改+1 删除」→实测重算 **18 新建+11 修改+0 删除**）；追溯矩阵缺 3 行（AC-5/Task 3、AC-3/Task 5、AC-4/Task 5）；Task 4 两循环测试无归属文件；契约测试绿点与组合根注册分 Task（5-12 R1-19 同族再引入）——中途 DoD「pytest 全部通过」撞持续红；模板三小节结构缺失+domain≥90% 门禁缺；学习来源失实（5-12 学习节正式来源为 5-11，四条仅 Fraction 在案）；`__event_registry__` 符号不存在（实为 `__init_subclass__` 自动注册）；行号漂移族（OD-2 L1912→L1938、PRD L1867→L1869、or.md L413→L411、OD-3 L1893→L1890/L1964、覆盖率 L2063/2064→L2064/2065、document_tasks L31→L36）；§17.5 归属错挂（core-domain 无 §17.5）；architecture.md 旧路径；「5.10 L1784」锚点失效（实为 5-10 OD-6 L53/DC-8 L624）；`[Aggregate][EventName]` 出处错挂（实为 story-template.md L50）；六子步骤语义配置表缺失（方法论忠实度全押无约束 LLM 自选——persona 研究支持任务化框架）；per-node RetryPolicy 缺失（瞬时故障先重试再降级两级设计——LangGraph 标准形态）；search 签名缺 async+weights；OD-1 文件名族与清单不一致 | P1/P2/P3 | 逐项清偿：计数重算+矩阵补行+测试归属钦定（`test_agent_cli.py` ▲/`test_event_channel_mapping_blm_planning.py` ★）+契约测试绿点归 Task 4 循环 A（TDD 表「绿」限定本 Task 范围）+质量门禁拆三小节+domain≥90%+学习分源标注+`__init_subclass__` 机制改写+行号批量校正+§17.5/路径/锚点/出处修正+语义配置表入 Task 0.1（DC-3 时序/DC-5 白名单）+RetryPolicy 入 Task 3 循环 B+search 签名补全+OD-1 改「功能名族」表述 |
| R2-1 | Round 1 修复的**快照写入方双钦定冲突**：Task 2 循环 B 绿仍写「状态查询用例 + 快照写入」与 DC-6/Task 3 循环 A（写入方=BlmPlanningService 各方法末尾）形成两个写入方；「快照存储通道按 Task 0.1 钦定」为悬空引用（Task 0.1 无此钦定） | P1 | Task 2 循环 B 改**读侧**用例（三层键读取、零写入）；写入方唯一归 Task 3；「写读一致」断言归 Task 3 与集成 5.2；悬空引用删除 |
| R2-2 | Round 1 修复表声称的传播 4 处未落地：Subtask 0.6 仍「六件」（应七件）；「四件套」残留 4 处（AC-6 验证标准/追溯矩阵/Task 1 循环 B 标题/Dev Notes——且 AC-6 处条目集缺 2 项）；document_tasks 行号 L31 残留于留项 #3（实为 L36）；Subtask 0.8 复核范围「DC-1~DC-10」漏 Round 1 新增的 DC-11 | P2 | 五处全部落地：七件/五件套（条目集按 5 项 checklist 对齐）/L36/DC-1~DC-11（附 DC-11 重点复核注记） |
| R2-3 | Round 1 新引入的钦定参数名错误：`add_node(retry=...)` 在仓内 langgraph 1.2.9 **不存在**（实为 `retry_policy=RetryPolicy(...)`——`.venv` state.py L375 实测；仓内无节点级重试先例，MAX_RETRIES=2 是条件边自管）——按字面实施将 TypeError | P2 | 改 `add_node(..., retry_policy=RetryPolicy(max_attempts=2, ...))` 并注「仓内首个节点级重试」 |
| R2-4 | 任务面发布点/断言缺口：PlanningStarted 的发布点（use case 启动点）未落 Task 0.6②与 Task 2 循环 A 红（正文唯一钦定只含服务侧）；AC-4③ outbox 全集断言漏 PlanningStarted 恰一行；Task 4 循环 A 红 resolve 断言漏第三注册名 `blm_planning_status_use_case`（零测试覆盖） | P2 | Task 0.6② 补双发布点钦定；Task 2 循环 A 红补 PlanningStarted 发布断言；AC-4③ 补「PlanningStarted 恰一行」；Task 4 红补第三 resolve 名 |
| R2-5 | 锚点/结构级瑕疵族：引擎构造器尾参行号 L57 实为 **L51**（两处正文+R1-6 台账）；「Rule 5」规则名不存在（实为 `test_all_subdomain_ranges_are_valid`）；AC-4 所引 5-10 文件名前缀错误（`5-10-financial-...`→`5-10-checkpoint-with-evaluation-integration.md`）；结构清单图例「零改动」应为「零删除」；DC-11 行序倒置在 DC-10 前；结构树 langgraph_engine.py 缩进使其字面读作 graphs/ 子级（实际在 agent_orch/ 级） | P3 | 六处逐一修正（R1 台账原文保留、勘误内联标注于表头注记） |
| R3-1 | **图形态钦定自相矛盾**：AC-6①降级在服务方法内全量捕获→节点永不因业务失败抛错→六子步骤间无条件分支点，永真条件边与直连边行为完全等价——「条件边改直连」变异物理不可红（行为不变）；「条件边推进/降级边不断流」钦定无意义（先例条件边仅用于 verify 分流/reflect 重试两个真分支点） | P1 | 钦定 **8 节点+7 直连边+END**；删除条件边表述与对应变异，变异改「边序交换/漏节点→图身份锚或枚举序断言红」 |
| R3-2 | **per-node RetryPolicy × 步级降级互斥**：RetryPolicy 重试耗尽=异常上抛=图失败中断（无「耗尽后降级」钩子），与 AC-6①「流程继续推进」冲突；且服务全量捕获下节点不抛→RetryPolicy 恒不触发（死配置）——「瞬时先重试再降级且不断流」在节点级重试语义下不可实现（R2-3 引入的设计缺陷，推演证伪） | P1 | 删 per-node RetryPolicy，改**服务内两级**（每步 asyncio 单次重试循环→仍败步级降级）；R1 风险算术改双口径（无重试 64s/重试叠加 128s，均值不含重试轮） |
| R3-3 | **380 注入路径在白名单设计下生产不可达**：语义配置表工具候选白名单（or.md→23 已注册 slug）确定性先行执行，`get_tool` 的 380 无自然触发面（白名单内必已注册）；449（隔离预检）与 380 是两条码路不可互替——AC-6 验收场景「380 降级」注入手段缺失 | P1 | 验收层降级场景改锚 **449**（构造 tools_l1 受限真实 CEO Agent——真实路径可达）；380 降级锚**单测层**（Mock 注册表注入未注册名）；场景配比 AC-6×3 第三场景改「449 降级」；AC-6 Given 同步 |
| R3-4 | **全步骤失败边界与 481 抛出点未钦定**：谁检测「全降级」并抛 PlanningExecutionError 无 Task 归属（矩阵只挂 Task 1 异常类）；「全步骤」精确定义、7/8 部分降级终态（成功 DTO 还是异常）、仅 synthesis 降级形态均未成文——「部分降级误抛 481」多解 | P1 | 钦定：抛出点=RunBlmPlanningUseCase 终态组装处（len(degraded_steps)==total_steps，归 Task 2 红）；部分降级返回成功 DTO 成文；补 7/8 降级终态期望断言；仅 synthesis 降级=conclusions 空+degraded_inputs 自含 |
| R3-5 | **顺序断言观测面不可判序**：时间戳单调只能证伪并行、无法证伪乱序串行（错序串行时间戳照样严格单调）；「期望独立构造」挂时间戳不成立（运行期值）——边序接错的实现可全绿通过 | P1 | 改**双锚**：`insight_steps[i].step == EXPECTED_ORDER[i]`（枚举序独立构造自 or.md——真正顺序判别）+ 时间戳非重叠断言（证伪并行）；Subtask 5.1 同步 |
| R3-6 | **检索依赖必填性与 Given 构造未钦定**：hybrid 检索列为必填注入且「检索失败→降级」——无检索环境下 7 步全 degraded 的「成功」使 AC-1/AC-5 断言失真；约 11/14 场景依赖检索可用但门控清单未钦定；AC-1 Given 构造序列（2.2a/3.1a 链路）零交代 | P1 | Task 0.3 钦定：检索在服务构造的必填性、「连接失败=降级 vs 空结果=正常空证据」判别语义、检索门控场景清单（逐一标档动态 skip）、Given 构造序列（3-1a embedding 探测+upsert 先例） |
| R3-7 | 推演坐实的规格/断言缺口族（P2×7+P3×5 归并）：降级产物 VO 不对称（PerformanceGapArtifacts/InsightSynthesis 无降级标记、insight_steps 恒满 6 未成文）；current_step 值域与「最近完成步」语义（挂起第 N 步读到第 N-1 步）；快照序列化契约（Task 2 种子与 Task 3 写入可各自为政）与读径通道（端口 vs 裸 hget）；480 触发路径零测试锚（无「不存在」第三态用例）；温度断言期望值无源（五档键与 8 步无映射——语义配置表缺温度列）；「零注册回归 grep」钉进契约测试锁死 Epic 7 三向未定的 deferred 决策；AgentDecided confidence 回落 0.9 常量（5-3 DC-6 修掉的假置信度复发）；端口组合 SSOT 漏 EventPublisher/快照通道两注入位；端口文件创建 Task 归属未指派；PlanningStarted 发布位置（守卫前=孤儿事件）未钦定；两套工具名单（tools_l1/步候选）关系未说明；AC-1③ 综合洞察非空断言 Fake 下近自证；Task 0 提交时序（pre-commit mypy 阻断延迟 import 缺失模块+CI 无 continue-on-error——.py/.feature 入仓纪律未承载，5-5 先例）；outbox 10 行/run 量级未成文 | P1~P3 | 逐项钦定：VO 补 degraded 字段+恒满 6 成文；current_step=最近完成步（阶段 1 取 performance_gap）；序列化契约入 SSOT+读径经端口；Task 2 红补「无快照→480」；语义配置表增温度列；零注册断言移出契约测试归 Subtask 0.9 单次核验；DC-11 补 confidence 显式钦定；SSOT 补两注入位；端口文件随 Task 2 绿；发布位置=三守卫后 submit 前；DC-5 补两机制并存；AC-1③ 改注入侧双锚；Task 0 DoD 补提交时序纪律；outbox 量级入 Task 0.6② |
| R4-1 | 纯验证轮抓到的**前轮修复传播漏网 4 处**（修复表声称已修、正文漏改——与文档内已正确的权威表述直接矛盾，实施代理按字面执行会踩回已修掉的坑）：Gherkin 场景配比行仍「380 降级」（应 449——Subtask 0.3 已改）；Edge Cases 注入矩阵仍「工具 380」（应 449——与相邻行直接矛盾）；Subtask 5.1 顺序断言仍单锚时间戳+「期望独立构造」（R3-5 已判该形态不可判序——AC-1 已改双锚本行漏同步）；风险 R2 缓解仍引「5-3 L252-254 先例」（R1-9 已改口该行为正常分支非降级先例） | P2×4 | 四处逐一同步：449 口径×2 / Subtask 5.1 双锚（与 AC-1 同构）/ R2 缓解改「6.1 新增步级捕获（BLM 面局部核销）」 |
| R4-2 | 验证轮 P3 三项：`_code_ranges.py:169` 标签微偏（注释实在 L167，L169 是段条目行）；风险 R1「DC-3 两级」指向松散（两级设计钦定在 Task 3 循环 A 绿，DC-3 本体无重试字样）；结构树 configs/event_channels.yaml 嵌在 src/ 子树下（实际位于仓根 configs/） | P3×3 | 三处修正（:167 预留注释注记 / 改指 Task 3 循环 A / 树行注明仓根位置）。**验证通过面**：正文 file:line 88 处 87 精确命中（1 处即本条标签偏）；结构/计数全过（Subtask 29/场景 14/OD×5/DC×11/风险×7/留项×8/18★11▲0✂/矩阵 17 行全覆盖）；三轮提交完整零游离；5 处关键修复终态在位 |
| R5-1 | 终审特权发现 P3×2（五节全过后的记录级清偿）：Story key 写法混用（依赖表「Story 3.1a」vs 正文「3-1a」——sprint-status 正式 key 为 3-1a-dense-semantic-search，统一为 3-1a/2-2a）；Task 3 循环 A 重构行「温度五档/8s timeout 复用对齐」与 AC-5「五档键与 8 步无直接映射」字面张力（改「纪律对齐+配置表唯一源」） | P3×2 | 两处统一/改写。**终审通过面**：周期闭合（4 提交零游离+4 簇修复表↔diff 抽验吻合）/关键修复双向取证 10/10 一致/file:line 抽验 55+ 处零失实/独立快扫零新 P0-P2/门禁红线全承载/结构计数全复算吻合 |

#### 收敛声明（Round 5 独立终审——2026-10-31）

Story 6-1（v1.3.1）四轮文档审查收敛：R1 三视角调研修订（P0×5+P1×11）、R2 回归+增量正确性（P1×1+簇）、R3 深度推演四轴（P1×6+归并簇）、R4 纯验证传播清偿（P2×4+P3×3）；关键改判：异常码段 480 新开 planning 子域、DC-9 改判保留、图形态钉死 8 节点 7 直连边+服务内两级重试、降级验收锚 449/380 单测层。独立终审五节全过：周期闭合 4 提交零游离、4 簇修复表↔diff 抽验吻合；关键修复双向取证 10/10 一致，file:line 抽验 55+ 处零失实；门禁红线全承载、结构计数全复算吻合。终审新增仅 P3×2（记录级，随收敛提交清偿——R5-1），零 P0/P1 残留——**ready-for-dev 放行成立**。

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 待定
**审查模式:** 待定

（待代码审查轮填写——格式按 5-12 先例 R1/R2/R3 轮表）

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施（Task 0 起步——前置留项八条裁定 + DC-5 终审为首个动作）
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.3.2
**创建日期/Created:** 2026-10-31
**最后更新/Last Updated:** 2026-10-31
**更新说明/Description:**
- v1.0.0: 创建故事文件（三路并行调研：规划权威面 epics/prd/or.md/architecture §17.4-17.5 + 现有代码七视角 + 范式与模板；范围边界 10 行（✅4/❌6）+ OD×5 + DC×10 + 风险×7 + 前置留项清单×8[含 2 项钦定处置：StrategicAnalysisUseCase 废弃评估/orchestration_service 保留注记] + 1 项事实修正[document_tasks 非死链]；AC×6；Task 0~7/Subtask 29；验收场景配比 14）
- v1.1.0: 文档审查 Round 1（4 调研 Agent + 3 审查视角 + 主会话 6 组实测定谳）——P0×5 全修（异常码段 471~473→480~482+planning 段 (480,489) / DC-9 改判保留[爆炸半径 7 测试+论据失实] / CLI argparse 测试载具 / planning_events.py 扩展非新建 / 双通道→delivery_mode 单模式分派）+ P1×11（图挂载双点+注入位 / DC-11 AgentDecided 投影 / 步骤边界快照点+写入点钦定 / 380 局部核销+降级下游三规则 / 四 VO+BlmPlanningState+语义配置表 / 8s 配置断言+受控注入采样+R1 算术 64s / 计数 18★11▲0✂ 重算+矩阵补 3 行+契约测试绿点归位+三小节+domain≥90%+学习分源+行号族校正+§17.5/路径/锚点修正+RetryPolicy）；DC×10→×11；文件清单 12/5/1→18/11/0
- v1.2.0: 文档审查 Round 2（回归核查+增量正确性双视角）——R2×5 修复（快照写入方双钦定冲突→读侧改造[P1] / R1 声称未落地 4 处清偿[六件→七件·四件套→五件套×4·L31→L36·DC-8 补 DC-11] / add_node retry=→retry_policy=[langgraph 1.2.9 实测] / PlanningStarted 发布点+恰一行断言+第三 resolve 名三缺口 / L51·Rule 名·5-10 文件名·图例·DC 行序·结构树六锚点级修正）+ R1 台账勘误两处内联标注；核验通过 40+ 锚点零偏差
- v1.3.0: 文档审查 Round 3（深度推演轮——14 场景期望唯一性/测试可满足性/R1×R2 组合交互面/Task 依赖干跑四轴）——R3×7 修复（P1×6：图形态钦定自相矛盾→8 节点 7 直连边[条件边与直连等价、变异物理不可红] / per-node RetryPolicy×步级降级互斥→删改服务内两级重试[R2-3 引入的设计缺陷推演证伪] / 380 白名单下生产不可达→验收锚 449+380 单测层 / 全降级 481 抛出点+部分降级终态成文 / 顺序断言时间戳不可判序→枚举序+非重叠双锚 / 检索必填性+Given 构造+门控清单钦定；P2×7+P3×5 归并 R3-7：降级 VO 对称/current_step 语义/序列化契约/480 触发锚/温度列/零注册断言移出/confidence 0.9/SSOT 两注入位/端口文件归属/发布位置/两套工具名单/综合洞察双锚/提交时序纪律/outbox 10 行量级）；另留「推演不成立疑点」留痕 5 项（Task 2 读侧可测/滞留与 L170 不冲突/场景计数无误/契约测试红 CI 可容/DC-11 已修——防后续轮重推）
- v1.3.1: 文档审查 Round 4（纯验证轮——R3 传播验证+file:line 全量实地核验 88 处+结构/计数终核+三轮存续）——R4×2 修复（R4-1 前轮修复传播漏网 4 处[P2]：场景配比 380→449/Edge Cases 380→449/Subtask 5.1 双锚同步/风险 R2 先例引用改口；R4-2 P3×3：_code_ranges 注释行号 L169→L167 标签/R1 交叉引用改指 Task 3 循环 A/结构树 configs 仓根注记）；验证通过面：正文锚点 87/88 精确命中、结构与计数全过、三轮提交完整零游离、5 处关键修复终态在位
- v1.3.2: 文档审查 Round 5（独立终审五节——周期闭合/双向取证/独立快扫/门禁红线/状态流转）——五节全过，ready-for-dev 放行成立；R5-1 终审特权发现 P3×2 随收敛清偿（Story key 统一 3-1a/2-2a、温度重构行措辞与 AC-5 对齐）；收敛声明入档（修复表末节）
