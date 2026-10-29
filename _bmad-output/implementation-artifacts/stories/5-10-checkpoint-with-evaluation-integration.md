# Story 5.10: CheckpointWithEvaluation 集成（评估历史存入 Checkpoint）

**Status:** `review`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 可观测性工程师,
**I want** 实现 CheckpointWithEvaluation 集成（评估历史累积器 + `to_checkpoint_snapshot()` 快照转换 + 真实持久化/恢复 + 主链第八可选依赖接入）,
**So that** 评估历史（eval_history / hallucination_trend / confidence_accuracy_trend）随 Checkpoint 持久化，支持漂移趋势追踪与历史质量回溯（趋势数据面的消费方是 V1-EV12——5.9 检测器本体零消费，见 OD-4④）。

### 业务价值

Epic 5「单 Agent 战略规划能力」价值组可观测性族第四 Story（收官面）：5.7 交付追踪基础设施（span 通道 + 14 键常量注册表），5.8 交付评估面（`EvaluationHarness.evaluate` 三维质量画像——评估结果目前是**局部变量即弃**），5.9 交付漂移检测面（`CUSUMDriftDetector.update` 双侧累积和——检测器状态**进程内易失**）。本 Story 交付**持久化面**——评估链数据流的最终断点清偿：`EvaluationCheckpointRecorder.record()` 在主链评估块内累积评估历史（含 predicted 置信度——V1-EV3 钦定「只存 EvaluationResult 会丢 predicted」的兑现）+ 打包 `CheckpointWithEvaluation → CheckpointSnapshot`（复用既有 `SnapshotRepositoryProtocol`/`RedisSnapshotStore` 基建，评估数据经 `state_data` 键承载）+ `restore()` 从快照恢复评估历史。这是 FR-EV-04 的闭环 Story：评估历史重启存活、趋势序列可回溯，为 5.9 CUSUM 的「漂移趋势追踪」提供数据面，也为 V1-EV3 真值校准（predicted/actual 双序列）与 V2-EV1 真实历史回测预置数据基建。

**范围权威**：epics_v1.0.md L1857-1900（AC + 实现内容 + 性能锚 L1883 快照创建 P95<100ms / L1884 评估历史查询 P95<50ms + 覆盖率 L1887 应用层≥85% / L1888 集成≥75%）、L204/L532（FR-EV-04 P1）、L1446（依赖 Story 5.8 + Epic 6 Story 6.3——**依赖倒置见 OD-2**）；sisys-core-domain-design.md §17.3.8 L1711-1725（CheckpointWithEvaluation 伪码 + to_checkpoint_snapshot 三字段）+ L1044-1048（Story 5-1 偏离声明 D-1：CHECKPOINTED 态延至 5.10 评估——**见 OD-5 与留项处置 #4**）；architecture.md L1768（checkpoint 实体钦定位置——已存在）+ L1798（checkpoint_repository 钦定位置——实际以 snapshot_repository_protocol.py 落地）；sisys-checkpoint-timetravel-design.md §2.1（CheckpointSnapshot 设计——其中持久化笔记/压缩/Replay/Override 是 6.3 BLM 面，本 Story 不做）。

### 范围边界（与后续 Story 的精确切分）

| 能力 | 本 Story（5.10） | 后续 Story |
|------|----------------|-----------|
| `AgentCheckpointPort`（record + restore）+ `EvaluationCheckpoint` DTO + `CheckpointWithEvaluation` 聚合（src/application/ports/agent_checkpoint.py） | ✅ 新建 + 契约测试 | — |
| `EvaluationCheckpointRecorder`（src/application/services/evaluation_checkpoint_recorder.py）：内存累积（窗口滚动）+ to_checkpoint_snapshot 打包 + save 持久化 + restore 恢复 | ✅ 组合注入 SnapshotRepositoryProtocol（R2） | — |
| `EvaluationHistoryError`（EXCEPTION_452——evaluation 子域 452-459 预留段首个取用） | ✅ evaluation_exceptions.py 追加 + 注册四件套 | — |
| 主链接入（use case 第八可选依赖 + 评估块内 record 块[独立降级网] + predicted 持久化） | ✅ 纯附加（None 默认向后兼容） | — |
| 持久化与恢复：session_id 命名空间（`agent-evaluation-{agent_id}`）+ 真实 Redis 往返 + 自清理 | ✅ 集成 + 验收 AC-3 | — |
| 性能双锚：快照创建 P95<100ms + 评估历史查询 P95<50ms | ✅ 委托集成计时 | — |
| CheckpointSnapshot 实体扩展（evaluation_history 等三字段进实体签名）/ RedisSnapshotStore 序列化扩字段 | ❌ 不做（OD-3——评估数据经 state_data 键承载，实体与序列化零改动） | 6.3 视 BLM 面需要评估 |
| BLM 阶段 Checkpoint 创建（PersistentNoteTaker 持久化笔记 / 上下文压缩 50K→2K / msgpack+checksum / Replay-Override 双模式恢复） | ❌ 不做（epics 6.3——重量级 BLM 阶段面） | Story 6.3 |
| `CHECKPOINTED` 第六态（AgentStatus 五态扩展 + 守卫改造） | ❌ 不做（OD-5——评估快照是可观测附加面非执行中断恢复面；锚位随 6.3 评估） | Story 6.3（中断恢复面） |
| `CheckpointReached` 事件发布（评估快照创建时） | ❌ 不做（OD-6——BLM 审批语义 vs 可观测附加面，事件通道零改动） | Story 6.3（BLM 检查点） |
| `CUSUMDriftDetector.get_trend()` / 检测器状态 Redis 持久化（重启存活） | ❌ 不做（OD-4——趋势序列由 Recorder 自持累积；检测器零改动；V1-EV12 数据面就绪注记） | V1-EV12 专项（deferred-work） |
| SingleAgentWorkflow 图工厂 checkpointer 注入（R1-DF5[5-3] 核销） | ❌ 不做（留项处置 #2——LangGraph 执行态中断恢复与评估历史快照语义分立，锚位顺延 6.3） | Story 6.3 |
| langgraph retry/timeout 字段级语义定稿 | ❌ 不做（留项处置 #1——评估快照携带 use case 层 retry_count 零图引擎字段语义需求，锚位顺延 6.6） | Story 6.6（checkpoint_table 消费方） |
| Time-Travel / 分支合并 / 差异对比（§3/§4） | ❌ 不做（Epic 10/22 面） | Epic 10 / Epic 22 |
| 评估快照 REST API / CLI 命令 | ❌ 不做（嵌入式可观测基础设施——5.7/5.8/5.9 同款定位；消费方出现时立项） | 无规划（消费方出现时立项） |
| Prometheus 指标导出 / Grafana 仪表盘（§17.3.8 监控集成表） | ❌ 不做（V1 监控域扩展） | V1 按需 |

### 偏离声明（Deviation Declarations）

| # | 偏离 | 规划原文 | 偏离理由与归宿 |
|---|------|---------|---------------|
| OD-1 | 测试文件命名从仓内惯例不从 epics 占位名：`tests/unit/application/test_agent_checkpoint_model.py` + `tests/unit/application/services/test_evaluation_checkpoint_recorder.py`（epics 占位 `tests/unit/architecture/test_checkpoint_evaluation.py`）+ `tests/unit/architecture/test_arch_checkpoint_evaluation.py`（AST 架构验证器——per-story 惯例）+ `tests/integration/test_integration_checkpoint_evaluation.py`（epics 占位 `test_checkpoint_evaluation_integration.py`）+ `tests/acceptance/test_acceptance_checkpoint_evaluation.feature/.py` | epics_v1.0.md L1896-1897（测试文件占位名） | 5-8 OD-1 / 5-9 OD-1 同款注记：epics 占位名是规划文本，仓内惯例（unit 按层归目录 / test_arch_* 前缀 / test_integration_* 前缀 / test_acceptance_* 功能性命名）是活代码事实源；规划占位名与仓内惯例的正常偏差，随本 OD 知悉不进台账 |
| OD-2 | **依赖倒置裁定**：epics「依赖 Story 5.8, Epic 6 Story 6.3」中 6.3 前置不成立——本 Story 改依赖既有 Checkpoint 基建（CheckpointSnapshot 实体 + SnapshotRepositoryProtocol + RedisSnapshotStore + 组合根 snapshot_repository 注册，均 1-14a/1-15 期交付）+ 5.8/5.9 评估链（done）；6.3 届时在本 Story 交付的评估快照层之上叠加 BLM 阶段面（持久化笔记/压缩/双模式恢复） | epics_v1.0.md L1446（「依赖 Story 5.8, Epic 6 Story 6.3」）+ 5-8/5-9 范围边界表「5.10（依赖 6.3）」注记 | ①规划时序错位：6.3 是 backlog 且排在 5-11/5-12 之后，若等 6.3 则 5.10 评估族（FR-EV-04 V1 承诺）无法闭环；②epics L1868-1873 的验收对象（CheckpointSnapshot 携带三评估序列 + 恢复评估历史）的全部基建已就绪——5.10 是**评估数据扩展面**非 Checkpoint 机制创建面（CheckpointSnapshot 基建本体已在 1-14a/1-15 交付）；③6.3 的 BLM 面（阶段触发/persistent_note_ref/压缩/Replay-Override）与本 Story 的评估历史面正交——三序列经 state_data 通用 KV 承载（OD-3），6.3 扩展零冲突；④依赖改写：实际前置 = Story 5.8（评估产物 EvaluationResult）+ 5.9（邻接面语义）+ 既有 snapshot 基建（全部 ✅） |
| OD-3 | 三评估字段经 `CheckpointSnapshot.state_data` 键承载（`evaluation_history`/`hallucination_trend`/`confidence_accuracy_trend` 三键 + `agent_id` 元数据键），**不扩实体字段**——`CheckpointWithEvaluation.to_checkpoint_snapshot()` 负责结构化字段→state_data dict 打包、`from_snapshot()` 负责解包 | sisys-core-domain-design.md §17.3.8 L1717-1724（伪码将三字段作 CheckpointSnapshot 构造参数传入——与现有实体签名不兼容）+ epics L1872（「CheckpointSnapshot 包含 evaluation_history、hallucination_trend、confidence_accuracy_trend」） | ①现有实体是 frozen 7 字段通用快照（state_data docstring「The actual state as key-value pairs」——通用 KV 是设计意图非权宜），扩字段须带默认值且 `RedisSnapshotStore._snapshot_to_hash/_hash_to_snapshot` 七字段哈希序列化同步扩——既有消费方（AutoExecuteService/测试族）回归面大且零收益；②评估快照与执行快照同实体同端口同存储——6.3 BLM 面可无缝复用同基建；③epics AC「CheckpointSnapshot 包含三序列」以「快照 state_data 含三序列键」语义承载（快照的包含性不等于实体字段性）；④结构化类型安全由应用层 DTO（CheckpointWithEvaluation frozen dataclass）承担——state_data 只在序列化边界是 dict，业务消费方经 from_snapshot 取回类型化聚合 |
| OD-4 | 伪码 `hallucination_trend=self.cusum_detector.get_trend()` 的检测器 getter 不实现——三趋势序列由 Recorder 自持累积（每次 record 从 EvaluationResult 逐次追加 hallucination_score / confidence_accuracy_trend 序列），`CUSUMDriftDetector` 零改动 | sisys-core-domain-design.md §17.3.8 L1722（cusum_detector.get_trend() 调用） | ①检测器私有窗口语义是「检测算法状态」非「历史趋势源」——基线窗 30 样本冻结后不清空滚动、确认窗 5 样本滚动覆盖，都不是完整历史序列（拿它们当 trend 会丢历史）；②检测器有状态（SINGLETON——5.9 DC-6「状态即功能」），给它加历史职责违反单一职责且与 V1-EV12（检测器状态持久化）纠缠；③评估历史与检测器窗口是同一评估流的两个投影——Recorder 自持累积即得全量趋势，检测器保持纯检测职责；④「评估历史（CUSUM 用）」的伪码语义反向承载：5.10 持久化的评估历史正是 CUSUM 序列（overall_score 可从三键派生——5.8 L204-206 注记）的数据留存面，V1-EV12 的「从评估历史回放重建基线」通道由此就绪 |
| OD-5 | `CHECKPOINTED` 第六态不引入——AgentStatus 维持五态（IDLE/RUNNING/WAITING/COMPLETED/FAILED） | sisys-core-domain-design.md L1044-1048（Story 5-1 偏离声明 D-1：「CHECKPOINTED 态延至 Story 5.10 时随 Checkpoint 机制一并评估引入」）+ L1050-1109（六态 AgentLifecycle 规划） | ①本 Story 评估后裁定：5.10 的 Checkpoint 是「评估历史快照」——可观测附加面，评估块内自动触发、每 run 一次、不中断执行；CHECKPOINTED 的规划语义是「WAITING 态中断保存后的状态」（L1082 save_checkpoint 在 waiting_user_confirm 分支）——执行中断恢复面，属 6.3 BLM 阶段审批；两者语义分立，5.10 引入 CHECKPOINTED 无状态转换可达路径（评估快照不改变 Agent 执行状态）；②AgentStatus 五态改六态需动 start/complete/fail/restart/wait 五守卫 + 既有状态机测试（5-1 DC-2 明示「改动属回归风险」）——无消费方的守卫扩展违反 YAGNI；③D-1 的「评估引入」义务经本 OD 履行（评估结论=不引入），锚位更新至 6.3（中断恢复面落地时再评估）——deferred-work 落注记（留项处置 #4） |
| OD-6 | 评估快照创建**不发布** `CheckpointReached` 事件（事件通道 yaml + DEFAULT_MAPPINGS 零改动） | docs/architecture/sisys-checkpoint-timetravel-design.md L697（CheckpointReached 归档时机表——「检查点到达」）+ 既有事件定义（checkpoint_events.py——src 内无发布点） | ①CheckpointReached 字段语义是 BLM 规划检查点（phase_identifier + user_feedback_request——阶段审批面），评估历史快照不是规划阶段检查点——语义误植会污染事件消费方（未来 WORM 归档按「检查点到达」归档评估数据）；②评估历史持久化是可观测附加面（5.8 DC-5/5.9 同族哲学）——附加面失败降级不告警，无事件语义需求；③MVP 无 CheckpointReached 消费方（src 内零发布点零订阅方）——发布是纯开销；④6.3 BLM 检查点落地时该事件获得真实发布点（届时 user_feedback_request 语义配套） |
| OD-7 | 端口接口形态：`async def record(agent_id, evaluation_result, predicted) -> CheckpointSnapshot`（单方法原子完成：内存累积 + 快照打包 + 持久化）+ `async def restore(session_id) -> CheckpointWithEvaluation | None` 两方法端口——伪码的 CheckpointWithEvaluation 聚合类与 to_checkpoint_snapshot() 方法保留为 frozen DTO + 纯转换方法（聚合数据类在端口文件，累积器职责在 Recorder 实现） | sisys-core-domain-design.md L1714-1724（CheckpointWithEvaluation 类 + to_checkpoint_snapshot 方法伪码）+ L1094-1101（CheckpointManager 规划） | ①原子性（5-9 OD-7 同款论证）：累积与持久化两方法形态存在中间态（累积成功 save 失败——内存与存储不一致）无消费语义；record 一次调用完成累积→打包→save，返回保存的快照供调用方断言；②CheckpointWithEvaluation 保持设计命名的 frozen 聚合 DTO（三序列 tuple + 元数据 + to_checkpoint_snapshot/from_snapshot 纯转换）——伪码形态保留；有状态累积（deque 滚动窗口）归 Recorder 实现（应用服务实现应用端口——evaluation_harness.py 实现 AgentEvaluationPort 同款先例）；③restore 是**恢复式语义非只读查询**：load → 解包聚合 → 灌回内部三 deque（deque maxlen 同窗裁剪）→ 返回聚合——AC-3②「restore 后 record → 历史 = 恢复 + 新记录」的机制承载（state_version 计数器同步续接 snapshot.state_version + 1）；restore 返回 None 而非抛异常（快照不存在是正常态——首次评估前无历史，AutoExecuteService.load 同款 None 语义）；④CheckpointManager（L1066 规划）不新建——其 save_checkpoint/load 职责已由 SnapshotRepositoryProtocol + Recorder 组合承载，禁同义组件重复定义 |
| OD-8 | 评估历史窗口上限 `MAX_HISTORY_SIZE = 100`（模块常量单源，deque maxlen——最旧滚动丢弃，三序列同窗同步滚动） | 规划无窗口上限语义（伪码 eval_history 无界列表） | ①每次 record 全量重写 Redis Hash（snapshot 存储是 latest 覆盖语义——redis_snapshot_store.py L119-121），无界历史 = 快照体积随 run 数线性膨胀（IO 延迟击穿 P95<100ms 门）+ Redis 单键体积失控；②100 条评估记录（每条 7 字段 JSON）≈ 数 KB——Redis Hash 单键安全量级；③100 run 量级覆盖 MVP 单 Agent 阶段回溯需求（5.9 OD-3 预热 30 样本锚的可回放窗口）；④窗口外完整序列的留存通道是 OTel span（eval.* 三键 per-run 留痕——Phoenix 查询面，保留期随部署配置）；DriftDetected 事件仅在确认漂移时发布（稀疏锚点——单确认样本 + CUSUM 统计，非历史序列通道）——通道语义分述注记落 docstring（R1-F 修正：原「经事件通道留存历史」表述失实——绝大多数被逐出窗口的评估不出现在任何事件里）；⑤上限值 V1 可调（配置化非本 Story 面）；恢复聚合 ≤ 窗口上限由结构保证（快照由 maxlen deque 产出）——上限值将来调小时旧快照恢复被 deque 静默截断的版本偏斜知悉（V1 配置化时注记） |
| OD-9 | **代码审查 R1 修正（对 v2.0.0 交付形态的设计变更）**：Recorder 累积窗口从全局单窗口（三 deque 实例级共享）改为 **per-agent 键控窗口**（`_windows: dict[session_id → _AgentWindow]`——各 Agent 三 deque + 窗口级 state_version 计数器）；连带收敛面扩 ValidationError（restore 结构异常族 452）+ record 输入域违规收敛 452（invalid_input）+ trend 元素 [0,1] 域守卫 + `EVALUATION_SESSION_PREFIX` 常量单源 | v2.0.0 交付形态（全局单窗口 + reason=missing_keys + catch 三元组）+ 5.9 检测器「SINGLETON 跨 Agent 混流知悉、per-agent 键控 V1」先例 | ①v2.0.0 全局单窗口与 DC-6 per-agent 命名空间落盘键错配——同进程多 Agent（use case/Recorder 双 SINGLETON 下七角色常态路径）B 键快照混入 A 的记录[双 Agent 实测复现]，restore 后前向永续污染，FR-EV-04「历史质量回溯」与 V1-EV12 回放数据面失真；②5.9 知悉登记先例不适用——5.9 是进程级信号统计质量面（σ₀ 渐进膨胀不落盘）、5.10 是 per-agent 数据档案正确性面（键即契约）；③窗口数 = agent 实体数无上界知悉（instantiate 非幂等——~60KB/窗慢泄漏，V1 LRU/TTL 治理锚）；④异常收敛是契约闭合非新设计——端口 docstring「唯一异常 EvaluationHistoryError」承诺对ValidationError 路径从假变真（451 防御层哲学第三次适用）；⑤多 worker 分叉/Redis 最后写者胜仍是 V1 面（风险 #9 保留）——本 OD 仅兑现进程内隔离 |

> 优先级锚说明（非偏离）：epics L532 将 FR-EV-04 定级 P1（功能等级），epics L1446 执行优先级 P1-10（执行序）。双锚不矛盾（5.8/5.9 同款注记）。

---

## 🔗 前置依赖（全部 ✅ 无阻塞——5.8/5.9/5.7 为 done 交付 Story；snapshot 基建为既有资产；「就绪」= 既有资产本 Story 直接消费无需先行动作）

| 依赖 | 组件 | 用途 | 状态 |
|------|------|------|------|
| Story 5.8 | `EvaluationResult` 四字段 frozen DTO（src/application/ports/agent_evaluation.py L84-138——hallucination_score/context_relevance/confidence_accuracy/overall_score，[0,1] 域守卫抛 201）+ 评估块宿主（run_agent_workflow.py L220-237——L220 None 守卫 → L221 try → L222 `evaluate` → L224-226 三键 span → L230-235 漂移块 → L236 共享 catch `(AgentEvaluationError, LLMConfigError, DriftDetectionError)` → L237 warning；L238 是块外 `return result`；**record 块的内嵌宿主**）+ `EvaluationHarness` 应用服务实现应用端口先例（src/application/services/evaluation_harness.py——Recorder 落位形态模板） | 评估历史的数据源 + 接入宿主 + 服务落位先例 | ✅ done（v2.3.1） |
| Story 5.9 | `DriftAssessment` 十字段 DTO + DriftDetectionPort（agent_drift.py——端口文件结构模板：模块 docstring 讲 Story/FR/端口族/R1R2R3 规则落地/纯标准库声明）+ 主链漂移块形态（record 块与漂移块的顺序协定见 AC-2）+ 452-459 预留段钦定（_code_ranges.py L139-140 段注释「452-459 预留/后续评估域异常——5.10 评估历史如需新码在此段取」——5.9 取 451，5.10 取 452）+ evaluation_exceptions.py 单文件续段惯例 | 端口文件风格 + 异常码归宿 + 主链块形态 | ✅ done（v2.3.1） |
| Story 5.7 | `SpanAttributeKeys` 14 键注册表（agent_tracing.py L105-128——**本 Story 零改动零新增键**：checkpoint 无 span 键需求，5.7 键表契约不动）+ OTel 链级测试通道 SSOT（场景级 initialize + InMemorySpanExporter + reset_for_testing 双复位义务）+ 延迟 import 纪律 | span 契约边界 + 测试通道 | ✅ done |
| Checkpoint 基建（1-14a/1-15） | `CheckpointSnapshot` 实体（domain/entities/checkpoint_snapshot.py——frozen 7 字段 + with_updated_state 合并语义）+ `SnapshotRepositoryProtocol`（domain/ports/snapshot_repository_protocol.py——save/load/delete，R1 领域基础端口）+ `RedisSnapshotStore` 实现（infrastructure/storage/redis/redis_snapshot_store.py——pipeline 原子 hset+expire、json_dumps/json_loads 序列化、build_key("snapshot", session_id)）+ 组合根 `snapshot_repository` 注册（composition_root.py L941-955——**SCOPED**，注入 redis_adapter）+ `AutoExecuteService` 可选注入消费先例（domain/services/auto_execute_service.py——构造器可选 snapshot_repo + create_snapshot version 递增 + restore_snapshot None 语义） | 持久化端口与存储实现——**直接复用禁新建同义端口**（R2 组合注入） | ✅ 就绪 |
| 序列化工具 | `json_dumps/json_loads`（infrastructure/utils/json_ser.py——RedisJSONEncoder；state_data dict 直接可序列化，Python json float 往返保真）+ `build_key`（infrastructure/storage/redis/key_builder.py） | state_data 序列化边界 | ✅ 就绪 |
| predicted 数据源 | `TaskEvidencePackage.confidence: float`（domain/value_objects/task_evidence.py L59——[0,1] 验证阶段产物，**V1-EV3 钦定必须随快照持久化的 predicted**）+ 主链 `result.evidence.confidence` 可达性（run_agent_workflow.py L202 已写 span `eval.confidence` 键——L202 属根 span MVP 十属性块 L192-203，非评估块三键 L224-226（`EVAL_CONFIDENCE` 与 `EVAL_CONFIDENCE_ACCURACY` 两键分立）；predicted 与 span 键同源双写） | record 的 predicted 形参来源 | ✅ 就绪 |
| 异常体系 | evaluation 子域 452-459 预留段（_code_ranges.py——451 已占 DriftDetectionError）+ `AgentEvaluationError` 风格模板（evaluation_exceptions.py 构造 agent_id/phase/reason/message/cause/context_extra）+ `ValidationError`（201——DTO 分数域守卫）+ `EXCEPTION_HTTP_MAP`（exception_handlers.py）+ CI 校验（test_code_ranges.py + test_error_code_uniqueness.py） | EvaluationHistoryError 452 落位 | ✅ 就绪 |
| 测试基建 | tests/acceptance/conftest.py（文件名服务 marker 自动挂载——checkpoint_evaluation 文件名不含服务关键词，仅自动挂 acceptance marker）+ 模块级 event_loop fixture + `_run_async` 同循环调度 + 集成委托计时三件（`_PERF_CACHE` + xdist_group 同组串行 + 常量单源集成定义/验收 import）+ AST 验证器 helper（test_arch_evaluation.py `_scan_file_top_imports`/`_scan_instantiation_sites`）+ TestTenant 租户隔离（tests/isolation.py——redis_key_prefix） | 测试骨架 | ✅ 就绪 |

**移交给本 Story 的留项（必须处置——deferred-work 钦定 5.10 为触发方，Task 0 逐条裁定 + deferred-work.md 落注记）：**

| # | 留项 | 来源 | 本 Story 处置 |
|---|------|------|--------------|
| 1 | **langgraph retry/timeout 字段语义定稿**——「触发 = Story 5.10（CheckpointWithEvaluation）或 6.6 实施（两处是 checkpoint_table/编排引擎行为的规划消费方，届时字段语义定稿）」 | deferred-work.md L17（路线图触发型） | **Task 0 裁定：本 Story 不触发定稿**——评估快照携带的执行上下文是 use case 层 `AgentWorkflowResult.retry_count/executed_phases`（主链已组装的既有字段，零图引擎 per-node retry/timeout 字段级语义需求）；规划消费方 checkpoint_table 是 BLM 阶段面（6.6）；锚位顺延至 6.6，Task 0.7 在 deferred-work L17 条目追加注记 |
| 2 | **R1-DF5[5-3]** SingleAgentWorkflow 新图 compile 无 checkpointer（图工厂裸 compile 与 BasicAgent `compile(checkpointer=...)` 分叉，thread_id 被静默忽略）——「核销触发：5-10 checkpoint 系列立项（图工厂接受可选 checkpointer 参数由引擎传入，与 BasicAgent 对齐）」 | deferred-work.md L194 | **Task 0 裁定：本 Story 不核销、锚位顺延 6.3**——规划时点预期「checkpoint 系列」含执行中断恢复；实际落地形态（OD-2 依赖倒置裁定）中 5.10 是评估历史快照面（应用层评估数据序列），LangGraph checkpointer（InMemorySaver）是图执行态中断恢复机制——两者语义分立，评估快照不消费也不需要图执行态 checkpointer；核销动作（图工厂接受可选 checkpointer）属执行中断恢复面=6.3；Task 0.7 在 R1-DF5 条目追加顺延注记（锚位 5.10 → 6.3，理由如上） |
| 3 | **V1-EV12** 检测器状态 Redis 持久化（重启存活）——「触发条件：……或 5.10 评估历史持久化落地时一并评估」 | deferred-work.md L282 + 5-9 OD-3（「V1 Redis 持久化随 5.10/监控域评估」） | **Task 0 裁定：检测器状态持久化本体不做，登记「数据面就绪」注记**——①检测器状态（基线窗/Sₕ/Sₗ/确认窗）与评估历史是两个状态体（算法态 vs 数据序列），5.10 持久化的是后者；②V1-EV12 的实质（重启后从持久化数据回放重建基线）所需的评估历史序列经本 Story 落地——数据面就绪，重建通道（检测器启动时从 restore 的历史回放 update 或直接统计基线）是 V1-EV12 专项实现面；③MVP 检测器重启归零重新预热 30 样本的盲区知悉不变；Task 0.7 在 V1-EV12 条目追加「5.10 数据面就绪」注记 |
| 4 | **Story 5-1 D-1**：CHECKPOINTED 态延至 5.10 评估引入 | sisys-core-domain-design.md L1044-1048 | **本 Story 兑现评估义务：裁定不引入**（OD-5——评估快照是可观测附加面非执行中断恢复面，无状态转换可达路径；AgentStatus 守卫扩展无消费方违反 YAGNI；锚位随 6.3 中断恢复面再评估）；Task 0.7 在 deferred-work 落注记（如无既有条目则新增：CHECKPOINTED 态评估结论 + 6.3 锚位） |
| 5 | **V1-EV3 附带义务**：「CheckpointWithEvaluation 快照需同时持久化 predicted=evidence.confidence 与 actual 序列——只存 EvaluationResult 会丢 predicted，5-10 立项时评估随快照持久化 evidence.confidence」 | deferred-work.md L261（V1-EV3 承接方栏）+ 5-8 OD-4④ 移交注记 | **本 Story 兑现**：`EvaluationCheckpoint` DTO 七字段含 `predicted_confidence`（AC-1.1 域守卫 + AC-2.1 主链 record 传参断言）；actual 序列经 hallucination/context_relevance 键可派生（OD-4[5.8] 口径 (1-h)×0.5+cr×0.5）；Task 0.7 在 V1-EV3 条目追加兑现注记（predicted 持久化已落地——真值校准通道的 V1 数据前提就绪，条目本体保持 V1） |

---

## 🔗 现有代码继承（必须复用，禁止重复定义）

> ⚠️ **防重复造轮子清单**——以下组件已存在，dev agent 只可「直接复用 / 参考照抄」，禁止新建同义组件。

| 组件 | 文件路径 | 复用方式 |
|------|---------|---------|
| 快照仓储端口 | `src/domain/ports/snapshot_repository_protocol.py`（SnapshotRepositoryProtocol——save/load/delete） | **直接消费**——Recorder 构造注入（R2：应用层端口组合注入领域基础端口）；禁新建 checkpoint_repository/evaluation_history_store 等同义端口 |
| Redis 快照存储 | `src/infrastructure/storage/redis/redis_snapshot_store.py`（RedisSnapshotStore） | **直接消费**——组合根既有 `snapshot_repository` 注册（L941-955）resolve 注入；序列化（_snapshot_to_hash 七字段 → **单 field "latest" 承载 7 字段 dict 的 JSON 串**——`hget(key, "latest")` 取全量后需两层 json_loads：外层 7 字段 dict、state_data 值本身已是内层 JSON 字符串）零改动（OD-3——评估数据在 state_data JSON blob 内）；**load 侧任何异常（含 Redis 故障）均捕获返回 None**（L162-164——故障与快照不存在不可区分，restore 返 None 双义知悉）；save/delete 异常包装 StorageError；回归面含 contracts 层 `test_port_contract_repositories.py` L313-335（断言注册 interface 同一性——组合根注册变更会被感知） |
| 快照实体 | `src/domain/entities/checkpoint_snapshot.py`（CheckpointSnapshot + with_updated_state） | **直接消费**——to_checkpoint_snapshot 构造目标 / restore 解包来源；实体零改动；**时间字段名是 `timestamp`**（L36，非 created_at——recorded_at 是本 Story 新 DTO 字段，json_loads 不自动还原 datetime、from_snapshot 须自行 fromisoformat）；七字段**全带默认值**（state_version 默认 **0**——「≥1」值由构造方显式传入[AutoExecuteService L171-177 先例：load existing → version+1 if existing else 1]；session_id 默认空串）；实体零校验（TTL 范围守卫只在 store.set_ttl） |
| 可选注入消费先例 | `src/domain/services/auto_execute_service.py`（构造器可选 snapshot_repo + create_snapshot version 递增语义 + restore None 语义） | **形态参考**——Recorder 的注入与 version 语义照此（差异①：AutoExecuteService 是 domain 服务，Recorder 是 application 服务——评估是应用可观测面；差异②[机制知悉]：先例 version 递增是 **load-derived**[每次 create 前 load existing → +1，L172-173——天然重启安全]，Recorder 改用**零 load 内存计数器**[性能选择：避免每 record 一次 Redis 读]——反面是重启后未 restore 直接 record 会版本回退，风险 #9 登记） |
| 应用服务落位先例 | `src/application/services/evaluation_harness.py`（EvaluationHarness 实现 AgentEvaluationPort——端口在 application/ports、实现在 application/services） | **落位照抄**——EvaluationCheckpointRecorder 实现 AgentCheckpointPort 同款布局 |
| 端口文件风格模板 | `src/application/ports/agent_drift.py`（模块 docstring：Story/FR/端口族/R1R2R3 规则落地/纯标准库声明 + Protocol + frozen DTO + 域守卫 + __all__） | **参考照抄**——agent_checkpoint.py 同款形态（Agent 可观测族第四端口，文件名=端口名先例延续：agent_tracing[5.7]/agent_evaluation[5.8]/agent_drift[5.9]/agent_checkpoint[5.10]） |
| 主链评估块宿主 | `src/application/use_cases/run_agent_workflow.py` L220-237（evaluate L222 → 三键 L224-226 → 漂移块 L230-235 → 共享 catch L236） | **原地扩展**——record 块内嵌：三键写入后、漂移块前（**同在 try 体内**——evaluation_result 存活域内）；独立降级网（内层 except EvaluationHistoryError——见 AC-2 Then）；**共享 catch 元组零改动**（450/332/451 三元组不动，452 由 record 块专属内层 catch 承载） |
| 组合根 def 工厂 | `src/composition_root.py` `_build_agent_workflow_use_case`（resolve_optional + ConfigurationError 防护降级 None） | **原地扩展**——工厂尾部追加 `resolve_optional("agent_checkpoint")` 第八依赖注入 |
| EvaluationResult | `src/application/ports/agent_evaluation.py` L84-138 | **直接消费**——record 形参类型；frozen 实例直传，四分数不重算 |
| 异常风格模板 | `src/domain/exceptions/evaluation_exceptions.py`（AgentEvaluationError/DriftDetectionError 构造 + context dict） | **续段追加**——EvaluationHistoryError 452 同款构造（agent_id/phase/reason + context_extra） |
| 事件契约先例 | `tests/contracts/test_port_contract_agent_drift.py`（11 维度 + _DummyResolver） | **参考照抄**——test_port_contract_agent_checkpoint.py 同款（REQUIRED_METHODS=["record", "restore"]；Dummy 分发 snapshot_repository） |
| AST 架构验证器形态 | `tests/unit/architecture/test_arch_drift_detection.py`（REPO_ROOT + 扫描 helper + 参数化验证器 A/B/C + 词边界正则） | **参考照抄**——test_arch_checkpoint_evaluation.py |
| 集成委托计时模式 | `tests/integration/test_integration_drift_detection.py`（_PERF_CACHE 双 key + 常量单源 + xdist_group 同组 + quantiles exclusive [18] P95） | **参考照抄**——P95 双锚版本：快照创建/评估历史查询两 key；常量 `CHECKPOINT_SAVE_P95_LIMIT_SECONDS = 0.1` + `CHECKPOINT_QUERY_P95_LIMIT_SECONDS = 0.05` |
| Fake LLM 手工装配链 | `tests/acceptance/test_acceptance_agent_evaluation.py` `_assemble_evaluation_workflow_chain`（真实 AgentWorkflowService/LangGraphEngine/RunAgentWorkflowUseCase + Fake LLM Schema 身份分派 + 手写零 IO stub） | **参考照抄 + 第八依赖扩展**——AC-2 链级场景装配（+ checkpoint_recorder 真实 Recorder 注入） |
| 手写零 IO 替身族 | `_RecordingEventPublisher`（全仓 15+ 文件同款）/ `_StubAgentRepository`（duck-typing 返回真实 Agent 实体） | **参考照抄**——验收替身；存储替身 `_RecordingSnapshotRepo`（duck-typing 实现 SnapshotRepositoryProtocol 捕获 save 快照列表——集成 MockSnapshotRepo 先例 tests/integration/test_integration_execute.py L242） |
| xdist 组清单（14 组实名） | agent-workflow-perf / agent-isolation-perf / agent-triple-isolation-perf / isolation-switch-log-perf / phoenix-tracer-perf / agent-evaluation-perf / drift-detection-perf / agent-instantiation / agent-profile-loading / data-source-cache / sandbox-daemon / tool-executions-pg / tool-versions-pg / validation-feedback-pg | **新组 `checkpoint-evaluation-perf` 与 14 组互异**（全仓 grep 断言——5-9 AC-5 同款）；**存量同步义务（创建期已实证消解）**：5-9 验收组断言实测为**子集断言**（`expected_existing <= existing_groups` + 自组存在性 + 自组消费方恰 2——test_acceptance_drift_detection.py L1586-1617，非穷举等值），新增第 15 组零破坏、**零同步动作** |

**明确不存在、本 Story 需新建**（全仓 grep 验证：`CheckpointWithEvaluation|AgentCheckpointPort|EvaluationCheckpointRecorder|EvaluationHistoryError|EXCEPTION_452|evaluation_history` 在 `src/` 零命中[仅规划性注释锚点——evaluation_harness.py L70「无 eval_history 累积——5.9/5.10 范围」、composition_root.py L2991 同款]；`get_trend` 零代码命中[仅设计文档伪码]；application/ports 下无 checkpoint 端口）：

1. `AgentCheckpointPort` + `EvaluationCheckpoint` DTO + `CheckpointWithEvaluation` 聚合（src/application/ports/agent_checkpoint.py——端口聚合文件）
2. `EvaluationCheckpointRecorder`（src/application/services/evaluation_checkpoint_recorder.py——AgentCheckpointPort 实现，组合注入 SnapshotRepositoryProtocol）
3. `EvaluationHistoryError`（EXCEPTION_452——src/domain/exceptions/evaluation_exceptions.py 追加 + 注册四件套）
4. 主链 record 块（修改：run_agent_workflow.py——第八可选依赖 + record 调用 + 内层降级 catch；纯附加 None 默认向后兼容）
5. 组合根 `# === Story 5.10 ===` 区段（agent_checkpoint 注册 + use case 工厂第八依赖）
6. 测试资产（新建七件[.feature/.py 分计]）：`tests/unit/application/test_agent_checkpoint_model.py` / `tests/unit/application/services/test_evaluation_checkpoint_recorder.py` / `tests/contracts/test_port_contract_agent_checkpoint.py` / `tests/integration/test_integration_checkpoint_evaluation.py` / `tests/unit/architecture/test_arch_checkpoint_evaluation.py` / `tests/acceptance/test_acceptance_checkpoint_evaluation.feature` + `test_acceptance_checkpoint_evaluation.py`；追加：`tests/unit/domain/exceptions/test_evaluation_exceptions.py`（452 用例）
7. 异常注册四件套之注册三动作（四件套 = 定义文件[见 item 3] + 以下三件——File List 同口径）：`_code_ranges.py`（_CLASS_TO_SUBDOMAIN 增 EvaluationHistoryError → evaluation 行——CODE_RANGES evaluation 行已存在零改动）+ `domain/exceptions/__init__.py`（导出）+ `interfaces/api/exception_handlers.py`（EXCEPTION_HTTP_MAP 452→500）
8. 端口导出：`src/application/ports/__init__.py`（AgentCheckpointPort/EvaluationCheckpoint/CheckpointWithEvaluation 聚合导出）
9. 存量触碰（构造签名八依赖联动——**断言同步全清单[创建期 grep 实证：`grep -rn "inspect.signature(RunAgentWorkflowUseCase\|inspect.signature(use_case_cls" tests/` 当前 **16 行命中归七处**（__init__ 签名相关 14 行 + execute 签名 2 行[L1377/L312——不受第八参影响]）；字面行口径 `grep -rn '"drift_detector",' tests/` 12 行/7 文件]**）：①`tests/acceptance/test_acceptance_phoenix_tracer.py`（L1367 参数清单 + L1375 字面行——尾部追加第八行）②`tests/unit/application/use_cases/test_run_agent_workflow.py`（L261/L685/L693/L695 六七依赖清单 + L915/L923/L925 漂移块用例七依赖清单——第八参数追加，record 块用例同文件追加）③`tests/unit/architecture/test_arch_phoenix_tracer.py`（L108 `_USE_CASE_INIT_PARAMS` 常量 + L305 签名断言）④`tests/acceptance/test_acceptance_agent_evaluation.py`（L1308/L1310/L1327——5.8 自身验收资产）⑤`tests/acceptance/test_acceptance_drift_detection.py`（L1188 签名 + L1207 字面行——**5.9 自身验收资产，最易漏处**；其 targets dict 另以裸 `'"drift_detector"'` 锚锁 ①③②④⑥ 字面[L1230-1232/L1711-1713]——尾部追加策略下天然满足零改动）⑥`tests/unit/architecture/test_arch_evaluation.py`（L234/L236 断言行 + **L54-62 `_USE_CASE_INIT_PARAMS` 常量本体——追第八项否则断言红**）⑦`tests/unit/architecture/test_arch_drift_detection.py`（L245 断言行 + **L50-58 `_USE_CASE_INIT_PARAMS` 常量本体——追第八项**——5.9 架构验证器签名基线）⑧`tests/unit/interfaces/api/test_exception_handlers.py`（expected_types 集合追加 452——穷举等值断言[插入点 L354/L355 之间]——**⑧ 属异常注册面不计入签名同步 ×7**）；**回执耦合防线（P0 级处方——5-9 教训延续）**：①③文件中 `"drift_detector",  # Story 5.9 第七可选依赖` 字面行被 5-9 验收 L1228-1229/L1709-1710 文本断言锁死——更新一律**尾部追加** `"checkpoint_recorder",  # Story 5.10 第八可选依赖` 行、禁改写/重排既有行；核验命令：`grep -rn "inspect.signature(RunAgentWorkflowUseCase\|inspect.signature(use_case_cls" tests/` + `grep -rn '"drift_detector",' tests/`；**行号锚漂移知悉（5-9 R3-1 教训）**：上列行号是创建期 grep 实证，dev 时以 grep 重新定位为准

---

## ✅ Acceptance Criteria 验收标准

### AC-1: CheckpointWithEvaluation 聚合与快照转换（DTO 域守卫 + 三序列累积滚动 + 打包/恢复往返）

**Given** 真实 `EvaluationCheckpoint` / `CheckpointWithEvaluation` frozen DTO（手工构造——纯数据类零外部依赖；**每场景新实例**）与模块常量单源（`MAX_HISTORY_SIZE = 100`——OD-8 窗口上限锚）
**When** 构造 `EvaluationCheckpoint`（七字段：`recorded_at: datetime` / `agent_id: str` / `hallucination_score: float` / `context_relevance: float` / `confidence_accuracy: float` / `overall_score: float` / `predicted_confidence: float`——**V1-EV3 兑现：predicted 必存**）与 `CheckpointWithEvaluation` 聚合（`agent_id: str` + `evaluation_history: tuple[EvaluationCheckpoint, ...]` + `hallucination_trend: tuple[float, ...]` + `confidence_accuracy_trend: tuple[float, ...]`），并调用 `to_checkpoint_snapshot(session_id, state_version=1)` 打包 / `CheckpointWithEvaluation.from_snapshot(snapshot)` 解包
**Then** ①**DTO 域守卫**：EvaluationCheckpoint 四分数 + predicted_confidence 共**五分数字段** [0,1] 数值域守卫（越界/bool/非数值抛 `ValidationError` EXCEPTION_201——`context` 携 `{字段名: str(实际值)}`，DriftAssessment/EvaluationResult 守卫同款形态[agent_evaluation.py L127-138 实测形态]；recorded_at 是 datetime、agent_id 是非空守卫——均非 [0,1] 分数域）；agent_id 非空守卫；`CheckpointWithEvaluation.__post_init__` 三序列等长守卫（history 长度 == 两 trend 长度——不等抛 201）+ **trend 元素 [0,1] 数值域守卫**（代码审查 R1 补——等长先验元素后验；bool 显式排除 + NaN 链式比较天然拦截[json allow_nan 穿越防线]，与 history 五分数守卫对称）；②**打包**：`to_checkpoint_snapshot()` 返回 `CheckpointSnapshot`（既有实体构造——session_id 形参承载 + `stage_id="evaluation"` + `state_version` 形参默认 1（聚合纯转换无状态——递增语义归 Recorder：内存计数器初始 1、record 打包传当前值后 +1、restore 续接 `snapshot.state_version + 1`，AC-1 断言默认值 1）+ `state_data` 四键：`agent_id`/`evaluation_history`（记录 dict 列表——recorded_at 经 isoformat 字符串化）/`hallucination_trend`/`confidence_accuracy_trend`，OD-3 键契约）；③**往返**：`from_snapshot(to_checkpoint_snapshot(...))` 三序列逐值相等（**纯内存往返同值传递恒等**——json 序列化双程保真验证由 AC-3 真实 Redis 场景承载[Python json repr 往返保证]；断言一律精确等式禁 approx[仓内无 approx 先例]）+ recorded_at datetime isoformat 往返相等 + agent_id 相等
**And** **窗口滚动**（Recorder 行为经端口方法验证——滚动覆盖在 **Task 2 单测②（灌 101 条）**，AC-2 验证累积跨 run、AC-3 验证恢复延续，本 AC 锚定常量与语义）：`MAX_HISTORY_SIZE == 100` 模块常量单源断言（防参数漂移）；滚动语义 = 最旧丢弃（deque maxlen 形态——docstring 注记「窗口外完整序列的留存通道是 OTel span（eval.* 三键 per-run 留痕——Phoenix 查询面）；DriftDetected 事件仅留存确认漂移的稀疏锚点——通道语义分述[OD-8④]」）；**手算锚钦定**：构造 3 条评估记录（分数取 0.1/0.3/0.5 类一位小数——避开浮点边界）→ 打包 → 快照 state_data 三序列长度 == 3 + 逐值断言；**退化锚**：空历史聚合（零记录）→ 打包快照 state_data 三序列为空列表 + from_snapshot 恢复空聚合（restore 边界态——首次评估前无历史是正常态）

**验证标准/Validation Criteria:**
- [x] EvaluationCheckpoint 域守卫：五分数字段（hallucination_score/context_relevance/confidence_accuracy/overall_score/predicted_confidence）[-0.01/1.01/True/"0.5"] 参数化 → 201 三段式断言（raises → code EXCEPTION_201 → context 携字段名）；agent_id 空串 → 201
- [x] frozen 不可变断言（setattr 抛 FrozenInstanceError——EvaluationResult/DriftAssessment 同款）
- [x] 三序列等长守卫：构造长度不齐聚合（history 3 + trend 2）→ 201
- [x] to_checkpoint_snapshot：stage_id=="evaluation" + state_data 四键存在 + 三序列逐值断言（手算锚 3 记录）+ snapshot_id 非空 UUID + ttl_seconds 为实体默认（86400）+ state_version == 1（默认值断言——递增语义归 Recorder 计数器，AC-2/AC-3 承载）
- [x] 往返一致性：from_snapshot 解包三序列逐值精确相等 + recorded_at 相等 + 空历史退化锚
- [x] MAX_HISTORY_SIZE==100 常量单源断言

### AC-2: 主链接入——第八可选依赖 + record 块（predicted 持久化）+ 独立降级网 + None 默认向后兼容

**Given** 工作流链 = 5.8/5.9 手工装配形态（Fake LLM Schema 身份分派[幻觉分注入控制评估分数] + 真实 AgentWorkflowService/LangGraphEngine/RunAgentWorkflowUseCase + 手写零 IO stub 仓储 + **drift_detector 注入**[第七依赖——AC-2.2「漂移块仍执行」断言面：drift 预填充场景依赖真实检测器场景私有实例] + **OTel 观测通道**[场景级 initialize + InMemorySpanExporter + teardown 双复位——eval 三键 span 与 drift.detected 断言的观测面，5-9 验收同款；NoOp tracer 下 is_recording False 无属性可断]）+ use case 构造注入 `checkpoint_recorder`（真实 `EvaluationCheckpointRecorder` + 手写零 IO `_RecordingSnapshotRepo` 替身[duck-typing 实现 SnapshotRepositoryProtocol，save 捕获快照列表——test_integration_execute.py MockSnapshotRepo 先例形态]）
**When** 调用 `RunAgentWorkflowUseCase.execute(agent_id, task)` 执行工作流
**Then** 评估块内（`evaluate` 成功 + 三键写入之后、**漂移块之前**——顺序钦定：record 失败不得阻断漂移检测、漂移失败不得丢评估历史，两独立可观测附加面）record 块执行：`if self._checkpoint_recorder is not None:` → `await self._checkpoint_recorder.record(agent_id=str(agent_id), evaluation_result=evaluation_result, predicted=result.evidence.confidence)`（**V1-EV3 兑现锚——predicted 从 result.evidence.confidence 取**）→ record 内层独立降级网 `except EvaluationHistoryError:` → logger.warning 继续漂移块（**共享 catch 元组零改动**——外层 `(AgentEvaluationError, LLMConfigError, DriftDetectionError)` 三元组不动，452 由 record 块专属内层 catch 承载：漂移检测与历史持久化互不牵连）；工作流返回值与 record 块零耦合（result 原样返回）
**And** **降级路径**（可观测附加面哲学——两级 catch 形态）：①record 失败（`_RaisingSnapshotRepo` save 抛 **StorageError** 注入[定义于 src/domain/exceptions/system_exceptions.py L31、经 src.domain.exceptions 包导出——import 面注记]——Recorder 捕获包装 452 上抛，完整真实路径[Redis 故障在存储面即 StorageError——redis_snapshot_store L131-133；替身直抛 452 会跳过包装环节，与 Task 2 单测⑥统一 StorageError 口径]）→ 主链正常返回 + **eval 三键仍在**（record 前已写——InMemorySpanExporter 断言三键属性存在）+ **漂移块仍执行**（drift.detected 确认路径不受影响——独立降级网验证锚）+ warning 日志（caplog 断言存在 WARNING 级记录且文本含 **452 静态 message 锚**——钦定 `EvaluationHistoryError.message = "评估历史持久化失败"`[Task 1 定义时落定]，断言该文案 in warning 文本；**str(领域异常) 恒等于 message**[DomainError 构造传 message 给 super——cause 链只进 to_dict 不进 str]，注入 StorageError 的动态文案不出现在 warning 文本[R2-A 修正：5-9「注入异常 str 同款」的前提（注入物 == 被记录物）在统一 StorageError 注入深度后不成立——替身直抛形态才有 str 同一]；包装链根因断言 `exc.__cause__ is 注入的 StorageError` 由 Task 2⑥ 单测承载）；②评估降级联动（evaluate 抛 450 → record 块天然跳过）+ 452 零捕获（外层 catch 不含 452——**record 块位于 evaluate 之后同一 try 体内，evaluate 抛出时控制流直接跳转外层 catch，record 块不执行[结构保证]**）；③漂移失败联动（漂移块抛 451 → 外层 catch 降级 → **record 已完成**[record 在漂移块前]——`_RecordingSnapshotRepo` 捕获断言快照已保存，漂移失败不丢评估历史）；**未注入路径**（`checkpoint_recorder=None`——八参默认）：record 块整体跳过 + 行为与 5.9 交付态完全一致（存量零破坏前提）；**构造签名扩展**：use case 第八可选依赖 `checkpoint_recorder: AgentCheckpointPort | None = None`（尾部追加——存量七参构造调用零破坏）；**存量断言同步 ×7**（创建期 grep 实证清单见「现有代码继承」第 9 条——含 5-9 自身验收资产 L1188/L1207 最易漏处）；**回执耦合防线**：①③文件追加一律尾部追加禁改写既有行

**验证标准/Validation Criteria:**
- [x] 主链 record 断言：execute 后 `_RecordingSnapshotRepo` 捕获 1 个 CheckpointSnapshot + state_data 四键 + evaluation_history 末条记录五分数字段与 Fake LLM 注入的评估分数逐值相等 + agent_id 相等 + recorded_at 为近期时刻（**predicted_confidence == result.evidence.confidence 断言**——V1-EV3 兑现锚）+ stage_id=="evaluation" + session_id=="agent-evaluation-{agent_id}"（命名空间锚）
- [x] 连续执行累积：同 agent 连续 execute 2 次 → 第二次快照 evaluation_history 长度 == 2 + hallucination_trend 长度 == 2（Recorder 内存累积跨 run 保持——SINGLETON 语义）
- [x] record 失败降级：save 抛 StorageError → record 包装 452 上抛 → 内层降级 → 主链正常返回 + 三键仍在 + 漂移块仍执行（drift 预填充场景的 drift.detected==True 断言——独立降级网验证锚）+ WARNING 日志断言
- [x] 漂移失败联动：漂移块抛 451 → record 已完成（替身捕获非空）+ 主链正常返回
- [x] 评估降级联动：evaluate 抛 450 → record 零调用（替身零捕获）+ 主链正常返回
- [x] None 默认路径：七参构造（不注入 checkpoint_recorder）→ execute 行为与 5.9 基线一致（回归锚）+ record 块零执行
- [x] 构造签名：八依赖签名断言（inspect.signature 参数清单尾部 == checkpoint_recorder + 默认 None）+ 外层共享 catch 三元组不变断言 + 存量断言同步 ×7 更新后全绿 + 核验 grep 双命令零漏
- [x] **5-3/5-7/5-8/5-9 存量全家回归绿**：逐一登记（5.3 全家 / 5.7 全家[AC-4.3 签名断言更新后 15 场景] / 5.8 全家[13 场景] / 5.9 全家[14 场景]）

### AC-3: 持久化与恢复——真实 Redis 往返 + 命名空间隔离 + 从 Checkpoint 恢复评估历史

**Given** 真实 Redis 服务（本地 .env Redis 连接——`RedisSnapshotStore` 经组合根 `snapshot_repository` resolve 或手工构造 `RedisAdapter` 装配；**场景级独立客户端**——session 级客户端跨循环不可用[记忆：acceptance_redis_client_cross_loop_issue]；Redis 不可用 → `pytest.skip` 动态跳过）与 TestTenant/UUID 前缀隔离（session_id 含唯一前缀——`agent-evaluation-{agent_id}`，agent_id 用 `uuid.uuid4()` 测试实体，多测试零键冲突）
**When** ①`record()` 多次（≥3 次——累积后持久化）→ 真实 Redis `hget(build_key("snapshot", session_id), "latest")` 验证落键；②新构造 Recorder 实例（**模拟重启**——内存累积清零）→ `restore(session_id)` 从快照恢复（**恢复式语义**——restore 同时灌回新实例内部三 deque，OD-7③）
**Then** ①**落键验证**：Redis 中快照 JSON 可解析 + 三序列与 record 传入逐值相等（save 真实路径——json_dumps 序列化 + pipeline 原子写；**"latest" field 值是 7 字段 dict 的 JSON 串、其中 state_data 已是内层 JSON 字符串——断言需两层 json_loads**）；②**恢复语义**（epics AC「支持从 Checkpoint 恢复评估历史」承载）：restore 返回 `CheckpointWithEvaluation` 非空 + evaluation_history 长度 == 最后一次快照的历史长度 + 逐值精确相等（**重启存活验证锚**——内存清零后历史完整恢复）+ restore 后继续 record → 新快照历史 = 恢复历史 + 新记录（**累积延续语义**——restore 是累积的恢复不是只读查询[机制：restore 灌回三 deque + state_version 计数器续接 snapshot.state_version + 1——Task 2 单测③b 红前置锚]）；③**恢复后趋势可回溯**：hallucination_trend 序列**顺序保持**断言（值序 == record 注入序——deque 追加序即时间序；非值单调性）
**And** **快照不存在**：restore 未 record 过的 session_id → 返回 None（AutoExecuteService.load 同款 None 语义——首次评估前无历史是正常态，非异常；**知悉注记**：store.load 侧任何异常含 Redis 故障均捕获返回 None[redis_snapshot_store L162-164]——故障与不存在不可区分，restore 返 None 双义下「故障静默为空历史」是既定行为，风险 #9 登记）；**自清理**：场景 teardown `delete(session_id)`（只清理自己创建的键——snapshot namespace 键级隔离，禁 delete/truncate 全局模式）；**TTL 语义**：快照携带实体默认 ttl_seconds=86400（24h——评估历史 MVP 生命周期；30 天窗口是 6.3 BLM 面参数，本 Story 用实体默认不动；评估间隔 >24h 的低频 agent 历史整键过期 → restore 返 None 走正常态路径静默清零——边界知悉注记）；**SCOPED 注入注记**：组合根 lambda 内 `resolver.resolve("snapshot_repository")` 在 SINGLETON 端口首次 resolve 时执行一次并固定实例——RedisSnapshotStore 无状态（委托 adapter，连接由 adapter 持有）固定实例安全，docstring 注记生命周期匹配论证

**验证标准/Validation Criteria:**
- [x] 真实落键：record ≥3 次后 Redis hget latest 非空 + JSON 解析 + 三序列逐值相等
- [x] 重启恢复：新 Recorder 实例 restore → 历史长度与逐值精确相等（重启存活锚）
- [x] 恢复后累积延续：restore 后 record 1 次 → 新快照历史 == 恢复历史 + 1
- [x] 快照不存在 → None（未 record 的 UUID session_id）
- [x] 趋势时序：hallucination_trend 顺序 == record 注入顺序
- [x] 自清理：teardown 后真实 `RedisSnapshotStore.exists(session_id) is False`（exists 是 store 具体类方法[L185-195]非协议面——duck-typing 替身不加协议外方法）
- [x] TTL：快照 ttl_seconds == 86400 断言（实体默认不动）

### AC-4: 端口接线、架构合规与组合根注册

**Given** 端口、实现、主链 record 块全部交付
**When** 验证接线与合规
**Then** 新端口经组合根 `# === Story 5.10 ===` 区段注册且 resolve 可达（PortSpec 元数据对齐 5.9 形态）：`agent_checkpoint`：v1.0.0 / `AgentCheckpointPort` / lambda 注入 `EvaluationCheckpointRecorder(snapshot_repository=resolver.resolve("snapshot_repository"))` / module=src.application.services.evaluation_checkpoint_recorder / **SINGLETON**（跨 run 累积——状态即功能，5.9 DC-6 同款论证[检测器有状态 SINGLETON]；SCOPED snapshot_repository 固定实例注入论证见 AC-3）/ owner=platform / tags=("agent", "checkpoint", "observability")；use case 工厂 `_build_agent_workflow_use_case` 扩展：`resolve_optional("agent_checkpoint")` 注入第八依赖（接线失败降级 None 不阻断 bootstrap——5.6/5.8/5.9 可选依赖先例延续）；**同窗落地纪律（5-8 R1-F1/5-9 两连教训）**：组合根 lambda 与第八构造参数必须同一 Task 同窗落地（提前注入 kwarg 在参数未交付窗口每次 resolve 即 TypeError）；契约测试（端口维度——test_port_contract_agent_checkpoint.py：PORT_NAME/EXPECTED_TAGS/REQUIRED_METHODS=["record", "restore"] 等 11 维度 + _DummyResolver 分发 snapshot_repository）
**And** **接线测试场景覆盖工厂降级防护面**（CR1-DF2[5.8] 家族延续）：_DummyResolver 未注册 agent_checkpoint → resolve_optional None → use case 构造成功 + `_checkpoint_recorder` is None；架构合规：application 触碰文件第三方白名单（agent_checkpoint.py / evaluation_checkpoint_recorder.py / run_agent_workflow.py——**零新增第三方**：agent_checkpoint.py 纯标准库、evaluation_checkpoint_recorder.py 纯标准库[asyncio + dataclass——存储委托注入端口，无 redis import]、run_agent_workflow.py 既有面零新 import[AgentCheckpointPort 同层 import]）；domain 触碰面（evaluation_exceptions.py 追加 + _code_ranges.py + __init__.py——**零 events 触碰**[OD-6：无新事件——本 Story 与 5.9 的差异面：5.9 新增 DriftDetected 事件，5.10 事件零改动；AST 验证器 B 回落 5.8 五目录扫描形态（含 events 目录全域扫描——非 5.9 的 events 白名单差分面）]）；组合根外零实例化（EvaluationCheckpointRecorder 构造点仅 composition_root.py + tests/）；依赖方向：EvaluationCheckpointRecorder（application）→ AgentCheckpointPort（application 同层）+ SnapshotRepositoryProtocol/CheckpointSnapshot（domain）合法 ✓（application→domain 允许面）；`.env.example` 零改动（无新环境变量——MAX_HISTORY_SIZE 是代码常量）；**xdist 组登记**：`checkpoint-evaluation-perf` 与既有 14 组互异（全仓 grep 断言）+ 5-9 组断言为子集断言实证（L1586-1617——新增组零破坏，无同步动作）

**验证标准/Validation Criteria:**
- [x] 组合根注册 + resolve 四件断言（可达/isinstance/PortSpec 元数据/lifetime==SINGLETON——5.9 AC-4.1 同款）
- [x] use case 工厂注入断言（resolve("agent_workflow_use_case") 实例的 `_checkpoint_recorder` 非 None 且 isinstance AgentCheckpointPort——接线可达性）
- [x] 降级防护：未注册形态 → resolve_optional None → use case 构造成功 + `_checkpoint_recorder` is None
- [x] 契约测试全绿（端口 11 维度 + REQUIRED_METHODS=["record", "restore"]）
- [x] AST 验证器 A：application 触碰文件第三方白名单（零新增断言）
- [x] AST 验证器 B：domain 触碰面收窄断言（EvaluationHistoryError 仅在 exceptions 三件内 + **events 零触碰断言**[OD-6 契约]）+ 组合根外零实例化 + 依赖方向
- [x] AST 验证器 C：主链 record 块静态锚（execute 体内 record 调用 + predicted=result.evidence.confidence 引用 + 内层 except EvaluationHistoryError 分支在位 + 漂移块之前顺序锚[AST 兄弟节点序]）+ use case 八依赖签名基线 + agent_checkpoint.py/evaluation_checkpoint_recorder.py 标准库零外部依赖断言
- [x] .env.example 零改动断言（收尾场景断言面）+ xdist 组互异断言 + 5-9 组断言同步核实

### AC-5: 性能双锚——快照创建 P95<100ms + 评估历史查询 P95<50ms

**Given** ①快照创建口径 = **record 全路径**（内存累积 + to_checkpoint_snapshot 打包 + RedisSnapshotStore.save 持久化——真实 Redis 写路径含网络 RTT；**本地 Redis 口径**[单机 RTT <1ms——100ms 门宽松；网络 Redis 部署形态 RTT 依赖知悉注记——5.8 DC-8④ 诚实注记同款：门定位是回归绊线非容量预算]）；②评估历史查询口径 = **restore 全路径**（RedisSnapshotStore.load + from_snapshot 解包——epics L1884「评估历史查询延迟」语义锚定读路径）；③委托计时三件（常量单源 `CHECKPOINT_SAVE_P95_LIMIT_SECONDS = 0.1` + `CHECKPOINT_QUERY_P95_LIMIT_SECONDS = 0.05` 定义于集成模块验收 import 禁双真源 / `_PERF_CACHE` 单 key `checkpoint_perf` 载双指标 summary dict 的 cache-or-compute[代码审查 R1 口径修正——原「双 key」系 5.9 形态描述，实际单 key 一次采样产双锚，功能等价] / `xdist_group("checkpoint-evaluation-perf")` 同 worker 串行——组名与既有 14 组互异）
**When** ①测量快照创建延迟（warmup 1 + **20 采样**——P95 需 95 分位 `statistics.quantiles(latencies, n=20)[18]` exclusive[5-8 EVALUATION_SAMPLE_ROUNDS=20 同款口径]；单次采样 = 完整 record 调用[Recorder 预填充至窗口常态——每采样含累积+打包+真实 Redis save]）②测量查询延迟（同批 20 采样 = 完整 restore 调用[load+解包]）
**Then** ①save P95 < 0.1s（epics L1883 钦定 100ms）②query P95 < 0.05s（epics L1884 钦定 50ms）；**正向锚**：采样轮 save/load 调用计数 == warmup + 采样数（21——防静默跳过假绿；**warmup 轮 = 一次 record + 一次 restore**[双计数同达 21——warmup 只 warm 单锚会使另一锚计数 20≠21 假红，R2-B 注记]；计数形态 = 采样循环内手工递增计数[每轮恰一次 record 内一次 save / 一次 restore 内一次 load——5-9 L116-134 同款，真实 Redis 路径下循环计数即调用计数]；Redis 不可达时采样前置探测 skip 而非静默零采样）；**满窗锚**（性能真实性）：采样前 Recorder 历史预填充至 MAX_HISTORY_SIZE（100 条——满窗快照是最大体积形态，P95 门在满窗下成立才是有效锚——OD-8 窗口与性能的耦合验证；**预填充经 record 公共路径 ×100**——不计时不计入采样轮调用计数[5-9 预填充口径同款]，禁直灌私有 deque[测试形态污染]）
**And** 采样入口自包含（每采样批次独立 session_id——UUID 前缀隔离，批次间零键冲突；teardown 清理）；口径声明落 docstring（save 路径含 Redis RTT vs 纯内存管线分述 + 满窗锚口径 + 网络部署形态知悉 + 20 样本 P95 估计量方差大知悉[绊线口径——门与实测差两个数量级，估计噪声不淹没数量级劣化检出]——防后续误读）；Redis 不可用 → `pytest.skip`（动态跳过禁写死）

**验证标准/Validation Criteria:**
- [x] save P95<100ms：常量单源（集成定义/验收 import）+ 委托形态对齐 5-8/5-9 先例「命中或首次采样」+ 20 采样 quantiles[18] exclusive 口径 docstring 声明
- [x] query P95<50ms：同批采样口径 + 常量单源
- [x] 正向锚：采样批次 save/load 调用计数 == warmup + 采样数
- [x] 满窗锚：预填充 100 条历史下双锚成立 + MAX_HISTORY_SIZE 耦合注记落 docstring
- [x] xdist 组 checkpoint-evaluation-perf 与既有 14 组互异（全仓 grep 断言）+ 5-9 组断言子集形态实证注记（L1586-1617——零同步动作）
- [x] 口径声明落 docstring（save 含 RTT / 满窗 / 本地 Redis 前提 / 20 样本方差知悉五注记）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [x] **本 Story 零新事件**（OD-6——CheckpointReached 不发布，事件通道 yaml + DEFAULT_MAPPINGS 零改动；AST 验证器 B 含 events 零触碰断言）

#### 数据模型 (Data Models)
- [x] `EvaluationCheckpoint` frozen dataclass 七字段（recorded_at/agent_id + 四分数 + predicted_confidence——V1-EV3 兑现）定义于 `src/application/ports/agent_checkpoint.py`（应用层 DTO——评估是可观测应用面非领域概念，EvaluationResult 同层同论证）
- [x] `CheckpointWithEvaluation` frozen 聚合（agent_id + evaluation_history/hallucination_trend/confidence_accuracy_trend 三 tuple 序列）+ `to_checkpoint_snapshot(session_id, state_version=1)` 打包（state_version 默认 1——递增语义归 Recorder 计数器，AC-1 Then②）+ `from_snapshot()` classmethod 解包（OD-3——state_data 四键契约：agent_id/evaluation_history/hallucination_trend/confidence_accuracy_trend）
- [x] 序列化边界：recorded_at 经 isoformat 字符串化（JSON 可序列化）；float 经 json_dumps/json_loads 往返保真（Python json repr 保证——精确等式断言）

#### 统一端口定义注册与管理 (Port Contract)
- [x] `AgentCheckpointPort` Protocol 定义于 `src/application/ports/agent_checkpoint.py`（Agent 可观测族第四端口——文件名=端口名先例：agent_tracing[5.7]/agent_evaluation[5.8]/agent_drift[5.9]/agent_checkpoint[5.10]）
- [x] 端口方法：`async def record(agent_id: str, evaluation_result: EvaluationResult, predicted: float) -> CheckpointSnapshot`（OD-7 原子形态；Recorder 内存 state_version 计数器初始 1——record 打包传当前值后 +1）+ `async def restore(session_id: str) -> CheckpointWithEvaluation | None`（**恢复式语义**——load → 解包 → 灌回内部三 deque[deque maxlen 同窗裁剪] → 返回聚合；state_version 计数器续接 snapshot.state_version + 1；端口 docstring 注记状态恢复副作用[OD-7③——AC-3② 累积延续的机制承载]）
- [x] 端口注册中心 `src/domain/ports/registry.py` PortSpec 登记（经 composition_root.py register_port——name=agent_checkpoint / v1.0.0 / SINGLETON / owner=platform / tags）——Task 2 交付
- [x] 实现仅 `src/application/services/evaluation_checkpoint_recorder.py`（组合注入 SnapshotRepositoryProtocol——R2 应用端口组合注入领域基础端口）——Task 2 交付
- [x] 端口契约测试 `tests/contracts/test_port_contract_agent_checkpoint.py`（REQUIRED_METHODS=["record", "restore"] + _DummyResolver 分发 snapshot_repository）——Task 2 交付
- [x] 禁止新建 checkpoint_repository / evaluation_history_store 等同义端口（SnapshotRepositoryProtocol 是唯一快照仓储真源）

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增异常在 Task 0 完成设计。
> **适用范围**：定义在 `src/domain/exceptions/` 下、继承 `DomainError` 的领域异常。

- [x] 归属模块与基类：`EvaluationHistoryError`（evaluation 子域——evaluation_exceptions.py 单文件续段，5.9 DC-4 钦定「5.10 续段同文件」）继承 `SystemException`（评估管线基础设施失败——与 AgentEvaluationError 450/DriftDetectionError 451 同族：可观测附加面的运行期失败，非业务规则违反）
- [x] 唯一编码分配：EXCEPTION_452（evaluation 子域 452-459 预留段——451 已占 DriftDetectionError；运行 `grep -r "EXCEPTION_452" src/domain/exceptions/` 验证零碰撞）
- [x] 构造器参数设计：`agent_id: str` + `phase: str`（"record"/"restore"）+ `reason: str`（**取值闭集 save_failed/invalid_structure/invalid_input**——代码审查 R1 收敛：结构异常族[缺键/类型错/分数值域/trend 元素/等长]单值收敛 invalid_structure，cause 链携精确原异常；原 missing_keys/type_mismatch/serialize 闭集与实发漂移已清偿）+ context_extra 携带 session_id/记录数（AgentEvaluationError 构造签名同款——context dict 纪律 dict[str,str]）；**message 钦定**：`message = "评估历史持久化失败"`（静态文案与 450/451 族模板一致——AC-2 warning 文本断言锚[R2-A：str(领域异常) 恒等于 message，cause 动态文案不进 str]）
- [x] 触发场景（BDD Edge Cases 覆盖）：①record 时存储 save 失败（StorageError 链路透传包装）；②restore 时快照结构不完整（state_data 缺键/类型错误——反序列化失败）；③打包时序列化域违规（不可序列化值——防御性，正常路径 DTO 守卫已拦截）
- [x] 消息安全性审查：错误消息面向调用方可理解（不泄露 Redis 内部细节——StorageError cause 链保留）
- [x] 编码注册：`_code_ranges.py` `_CLASS_TO_SUBDOMAIN` 增 EvaluationHistoryError → evaluation 行（CODE_RANGES evaluation 行已存在零改动）+ `sisys-uni-exception-design.md §3.3.2` **两处**更新（①编码分配表：L743/L744 预留行之间插 452 具体行 + 预留行收缩为 453~459；②子域范围表 L823 evaluation 行尾「452-459 预留 5.10 评估历史」说明同步——5.9 先例两处同更手法）
- [x] 导出完整性：`evaluation_exceptions.py` __all__ + `domain/exceptions/__init__.py` 导入 + `EXCEPTION_HTTP_MAP` 452→500（450/451 同族映射——**452 休眠映射注记**：主链内层 catch 降级 warning 无 HTTP 浮现路径，登记是注册完备性要求[与 450/451 同构——expected_types 穷举等值断言硬约束]）；docstring 措辞限定「452-459 预留段首个取用」（451 已自封 450-459 段首个取用——避免撞语）
- [x] 测试覆盖：`tests/unit/domain/exceptions/test_evaluation_exceptions.py` 追加 452 用例（构造/属性/to_dict/context）+ `tests/unit/interfaces/api/test_exception_handlers.py` expected_types 集合追加（穷举等值断言——**不更新即 CI 红**）+ 编码唯一性/子域范围 8 项自动通过
- [x] BDD 验收场景：452 降级路径 Gherkin 场景（AC-2.2）+ restore 失败场景（AC-3 边界）

#### API 契约 (API Contract)
- [x] **本 Story 零 API 面**（嵌入式可观测基础设施——5.7/5.8/5.9 同款定位；REST/CLI 立项待消费方出现）

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

**本 Story 落位判定（R1-R4 规则映射）**
- R1：SnapshotRepositoryProtocol（domain/ports——既有）是快照仓储基础端口唯一真源
- R2：AgentCheckpointPort（application/ports）组合注入 SnapshotRepositoryProtocol——EvaluationCheckpointRecorder 编排「累积→打包→持久化」
- R3：存储技术实现已由 RedisSnapshotStore（infrastructure/storage/redis）承载——本 Story 零新基础设施实现（可扩展其他存储实现是端口语义的自然收益）
- R4：零接口层触碰（无 API/CLI 面）

#### 验收标准 Gherkin (Acceptance Tests)
- [x] 功能测试文件：`tests/acceptance/test_acceptance_checkpoint_evaluation.feature`（功能性命名禁故事编号后缀；`# language: zh-CN`；AC 注释块分隔；无 @tag 无背景[5-8/5-9 先例]；场景命名 `AC-N.M - 描述`；收尾场景固定「收尾 - 完成清单逐项确认」）
- [x] 步骤实现文件：`tests/acceptance/test_acceptance_checkpoint_evaluation.py`（@scenario 逐场景显式绑定[5-7/5-8/5-9 路线，**不用** scenarios() 批量]；模块 docstring 三属性分档表开篇[场景|外部服务依赖|前置状态（Given 装配）|断言面（Then）——5-9 表头同款]；context fixture + 模块级 event_loop + _run_async 三件套；BDD 步骤禁 @pytest.mark.asyncio；**pytestmark=[acceptance, redis, xdist_group("checkpoint-evaluation-perf")]**——`pytest.mark.redis` 显式声明[文件名 checkpoint_evaluation 不命中 conftest 服务关键词映射、AC-3/AC-5 场景用真实 Redis——isolation_switch_log 先例验收 L76-80 同处境同款；**混合文件知悉**：本文件 AC-1×3（纯内存）与 AC-4×2（组合根/架构）不依赖 Redis 却被文件级 marker 覆盖——CI 无 -m 反选零行为影响（场景级 pytest.skip 才是跳过机制；`-m "not redis"` 环境会连纯内存场景一并排除——与先例[全文件 Redis 依赖]的差异知悉，分档表 AC-1/AC-2/AC-4 行服务依赖列标「无」]；延迟 import 纪律[新交付模块函数体内 import——红阶段 ModuleNotFoundError 承载]；真实服务自包含创建→执行→清理；Redis 不可用 pytest.skip 动态跳过）
- [ ] 业务方评审通过
- [x] 所有场景覆盖（Happy Path + Edge Cases——14 场景：AC-1×3 + AC-2×3 + AC-3×3 + AC-4×2 + AC-5×2 + 收尾×1）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试（`_run_async(context["_loop"], coro)` 同循环调度）
- 同一中文文本可能需要同时支持 given/when 装饰器（两函数各挂一装饰器形态——`test_acceptance_event_messaging_refactor.py` L1367-1376 最干净先例）
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径**——452 降级（record 失败）/ restore None（快照不存在）/ 评估降级联动（450 → record 零调用）
- **Redis 跨循环陷阱**（记忆：acceptance_redis_client_cross_loop_issue）：Redis 客户端场景级独立创建，禁 session 级共享

**Task 0 完成标志：**
- [x] 上述规范项全部定义完毕
- [x] Gherkin 验收测试已编写，运行确认失败（红阶段验证——延迟 import 下逐场景 failed 非 collection error）
- [x] 规范文档通过人工评审或自动化校验
- [x] **链路接线断言清单**已定义（Epic 4 回顾行动项 7.1-1）：①`agent_checkpoint` 组合根 register_port 装配验证（resolve 可达 + isinstance + PortSpec 元数据 + SINGLETON）②use case 工厂第八依赖注入确认（resolve 实例 `_checkpoint_recorder` 非 None）③主链 record 块静态锚（AST/inspect 扫描——record 调用 + predicted 引用 + 内层 452 catch + 漂移块前序）④持久化落键真值验证（真实 Redis hget——AC-3）⑤restore 恢复可达验证（新实例 restore 逐值断言）；「已实现未接线」组件在 deferred-work.md 登记（本 Story 无预期未接线件——record 块经工厂接线闭环）
- [x] **留项处置五条裁定落档**（deferred-work.md 注记 ×5——langgraph retry/timeout 顺延 6.6 / R1-DF5 顺延 6.3 / V1-EV12 数据面就绪 / 5-1 D-1 CHECKPOINTED 不引入 / V1-EV3 predicted 兑现）

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🟡 变异** | 对新行为契约的断言做突变注入-还原实证（Epic 4 回顾行动项 7.1-2） | 改坏生产代码 → 测试红 → 还原 → 绿（证明断言活着） |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy .`（**全仓含 tests/**——5-9 教训：只跑 src/ 漏 tests 面）+ `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试（违反 TDD 测试先行原则）
- ❌ 将测试编写集中到最后一个 Task（违反 TDD 小步快跑原则）
- ❌ 跳过红阶段验证（未确认测试失败就直接写实现）
- ❌ 跳过变异实证（新断言未经突变验证即视为不可信——Epic 4 教训：8/13 Story 存在恒真断言）
- ❌ 浮点断言用 pytest.approx / 十进制字面量假红形态（仓内纪律：精确等式 + 同式表达式——5-9 R1/R2 实战修正：计算序也要同形，n 次累积断言用逐次累加同式复算或区间比较）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | EvaluationCheckpoint/CheckpointWithEvaluation DTO | 七字段构造/[0,1] 域守卫/frozen/三序列等长/打包解包往返/常量单源 | `tests/unit/application/test_agent_checkpoint_model.py` | Task 1 |
| **TDD 单元测试** | EvaluationHistoryError 452 | 构造/属性/to_dict/context/HTTP 映射 | `tests/unit/domain/exceptions/test_evaluation_exceptions.py`（追加） | Task 1 |
| **TDD 单元测试** | EvaluationCheckpointRecorder | record 原子路径/窗口滚动/restore 恢复式（灌回+version 续接+累积延续）/452 包装/None 语义/StorageError 包装 | `tests/unit/application/services/test_evaluation_checkpoint_recorder.py` | Task 2 |
| **TDD 单元测试** | RunAgentWorkflowUseCase record 块 | 三键后漂移前顺序/452 独立降级/漂移失败不丢记录/评估降级联动/None 默认/第八参默认 | `tests/unit/application/use_cases/test_run_agent_workflow.py`（追加 TestExecuteCheckpointBlock） | Task 3 |
| **TDD 契约测试** | AgentCheckpointPort / registry / resolver | 端口注册、版本、兼容性、实现解析、方法签名 | `tests/contracts/test_port_contract_agent_checkpoint.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（14 场景） | `test_acceptance_checkpoint_evaluation.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_checkpoint_evaluation.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单最终确认 | 同 .feature/.py | Task 6 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖、组合根外零实例化、events 零触碰、主链静态锚 | `tests/unit/architecture/test_arch_checkpoint_evaluation.py` | Task 5 |
| **集成测试** | 真实 Redis 全链 | 落键/重启恢复/累积延续/命名空间隔离/自清理/P95 双锚 | `tests/integration/test_integration_checkpoint_evaluation.py` | Task 4 |
| **集成测试（存量）** | 5-9 漂移全家回归 | 存量断言同步后全绿 | `test_integration_drift_detection.py` 等 | Task 3 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和本 Story 覆盖率锚（epics L1887-1888）：

- [x] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [x] **应用层覆盖率 ≥85%**（epics L1887 钦定——新增 agent_checkpoint.py/evaluation_checkpoint_recorder.py/run_agent_workflow.py 扩展段）
- [x] **集成测试覆盖率 ≥75%**（epics L1888）
- [x] **关键路径覆盖率 100%**（record 原子路径/降级路径/restore 路径全分支）

#### 代码质量门禁
- [x] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [x] **MyPy 类型检查通过**（`poetry run mypy .`——**全仓含 tests/**）
- [x] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）
- [x] **三条 grep 自查零输出**（ValueError/手动 HTTPException/继承内置 Exception + noqa/type:ignore/pylint:disable）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则（本 Story 特化）：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **Redis 键隔离** | session_id 含 UUID 前缀（`agent-evaluation-{uuid}`）；场景级独立 Redis 客户端（session 级跨循环不可用——记忆锚） | 键冲突或跨循环异常 |
| **SINGLETON 累积器** | Recorder 跨 run 累积是设计意图——验收/集成测试**每场景新实例**（手工构造不走 resolve——SINGLETON 状态跨场景污染防线，5-9 检测器同款）；「连续执行累积」场景显式同实例两 execute | 跨场景历史污染 |
| **真实 Redis 清理** | teardown `delete(session_id)` 只清自己创建的键；禁 delete/truncate 全局模式 | 误删他测数据 |
| **OTel 双复位** | 凡链级场景 initialize 一律 teardown `reset_for_testing()` 双复位 + 文件级 autouse 兜底（5-7 SSOT）；env 不带 PHOENIX_TRACING_ENABLED=true | 全局 tracer 污染 |
| **xdist 组串行** | `checkpoint-evaluation-perf` 集成/验收逐字同组（loadgroup 同 worker 串行——_PERF_CACHE 命中前提）；组名与既有 14 组互异 grep 断言 | 计时缓存 miss 双跑 |
| **BDD async 配合** | 步骤函数禁 @pytest.mark.asyncio，用 `_run_async(context["_loop"], coro)`；禁 asyncio.run()（xdist 并行关错循环） | context 数据丢失 |
| **延迟 import** | 新交付模块一律函数体内 import（红阶段 ModuleNotFoundError 逐场景承载） | collection error 掩盖红形态 |
| **手写替身纪律** | 验收禁 mock 红线：替身 = 手写零 IO duck-typing 类（`_RecordingSnapshotRepo`/`_RaisingSnapshotRepo`——test_integration_execute.py MockSnapshotRepo 先例族）；AsyncMock(spec=) 仅限 tests/unit | 验收红线违规 |

**验证要求：**
- [x] 并行测试 `pytest tests/ -n 8` 通过
- [x] 连续5次运行无随机失败
- [x] `poetry run ruff check` 通过
- [x] `poetry run mypy .` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | DTO 域守卫（五分数字段 [0,1] + agent_id 非空 + 三序列等长） | Task 1 | 1.1-1.3 | test_agent_checkpoint_model.py |
| AC-1 | to_checkpoint_snapshot 打包（state_data 四键契约） | Task 1 | 1.2-1.3 | test_agent_checkpoint_model.py |
| AC-1 | from_snapshot 往返一致性 + 空历史退化锚 | Task 1 | 1.3 | test_agent_checkpoint_model.py |
| AC-1 | MAX_HISTORY_SIZE 常量单源 | Task 1 | 1.2 | test_agent_checkpoint_model.py |
| AC-2 | 第八可选依赖 + record 块（三键后漂移前 + predicted） | Task 3 | 3.1-3.3 | test_run_agent_workflow.py + 验收 AC-2.* |
| AC-2 | 452 独立降级网（漂移不丢记录/记录不阻漂移） | Task 3 | 3.2 | test_run_agent_workflow.py + 验收 AC-2.2 |
| AC-2 | None 默认向后兼容 + 构造签名 ×7 同步 + 存量全家回归 | Task 3 | 3.3-3.5 | ×7 存量文件 + 验收 AC-2.3 |
| AC-3 | 真实 Redis 落键 + 重启恢复 + 累积延续 | Task 4 | 4.1 | test_integration_checkpoint_evaluation.py + 验收 AC-3.* |
| AC-3 | restore None 语义 + 命名空间隔离 + 自清理 | Task 4 | 4.1 | 同上 |
| AC-4 | 组合根注册 + 工厂注入 + 降级防护 + 契约测试 | Task 2/3 | 2.3/3.2/3.4 | test_port_contract_agent_checkpoint.py + 验收 AC-4.1 |
| AC-4 | AST 架构合规（events 零触碰 + 主链静态锚） | Task 5 | 5.1-5.3 | test_arch_checkpoint_evaluation.py + 验收 AC-4.2 |
| AC-5 | 快照创建 P95<100ms + 查询 P95<50ms（满窗锚） | Task 4 | 4.2-4.4 | test_integration_checkpoint_evaluation.py + 验收 AC-5.* |
| 收尾 | 完成清单逐项确认 | Task 6 | 6.1-6.4 | 验收收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-5（Gherkin 全场景）+ 留项处置五条

> **目的：** 在进入代码实现前，明确数据模型、端口契约、异常契约、验收标准与六边形架构边界。

- [x] Subtask 0.1: 定义数据模型规范（EvaluationCheckpoint 七字段 + CheckpointWithEvaluation 三序列聚合 + state_data 四键序列化契约——OD-3/OD-7/OD-8 落档）
- [x] Subtask 0.2: 定义端口契约（AgentCheckpointPort record/restore 两方法 + registry PortSpec 元数据 + R2 组合注入关系图）
- [x] Subtask 0.3: 定义领域异常契约（EvaluationHistoryError 452——四件套清单 + 触发场景三分）
- [x] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_checkpoint_evaluation.feature`（14 场景：AC-1×3 + AC-2×3 + AC-3×3 + AC-4×2 + AC-5×2 + 收尾×1）
- [x] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_checkpoint_evaluation.py`（三属性分档表 docstring + @scenario 绑定 + context/event_loop/_run_async 三件套 + 延迟 import + Redis 探测 skip）
- [x] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证——逐场景 failed 非 collection error）
- [x] Subtask 0.7: **留项处置五条裁定落档**（deferred-work.md 注记：langgraph retry/timeout 顺延 6.6 / R1-DF5[5-3] 顺延 6.3 / V1-EV12 数据面就绪 / 5-1 D-1 CHECKPOINTED 不引入[无既有条目则新增] / V1-EV3 predicted 兑现注记）
- [x] Subtask 0.8: 定义链路接线断言清单（五件——Task 0 完成标志项）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕
- [x] 验收测试运行失败（预期行为，红阶段确认）
- [x] deferred-work.md 五条注记落档
- [x] Gherkin 场景与 AC 追溯齐备

---

### Task 1: EvaluationHistoryError 452 + DTO 双件 + 端口定义 + 异常注册四件套

**关联 AC:** AC-1（DTO 域守卫/打包/往返）

#### TDD 循环 A：EvaluationHistoryError（EXCEPTION_452）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_evaluation_exceptions.py` 追加 452 用例（构造/属性/to_dict/context dict/cause 链） |
| 🟢 绿 | `src/domain/exceptions/evaluation_exceptions.py` 追加 EvaluationHistoryError（SystemException 子类，agent_id/phase/reason 构造——AgentEvaluationError 签名同款） |
| 🟡 变异 | 删 context_extra 键 → to_dict 断言红 → 还原 |
| 🔄 重构 | docstring 全中文 Google 风格 + 注册四件套（evaluation_exceptions.py 定义/_code_ranges.py `_CLASS_TO_SUBDOMAIN` 增行[CODE_RANGES evaluation 行已存在零改动]/exceptions `__init__.py` 导出/EXCEPTION_HTTP_MAP 452→500——File List 同口径）+ `sisys-uni-exception-design.md` §3.3.2 两处更新（编码分配表插行 + 子域范围表 L823 行说明——5.9 先例同款）+ `test_exception_handlers.py` expected_types 追加 |

#### TDD 循环 B：EvaluationCheckpoint + CheckpointWithEvaluation DTO + AgentCheckpointPort

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_agent_checkpoint_model.py`（七字段构造/五分数 [0,1] 参数化 201/agent_id 非空/frozen/三序列等长 201/to_checkpoint_snapshot 四键打包[state_version 默认 1 断言]/手算锚 3 记录逐值/from_snapshot 往返精确等式/空历史退化/MAX_HISTORY_SIZE==100） |
| 🟢 绿 | 实现 `src/application/ports/agent_checkpoint.py`（模块 docstring R1-R4 落地声明 + Protocol + 双 frozen DTO + 域守卫 + __all__——agent_drift.py 风格模板）+ `src/application/ports/__init__.py` 导出 |
| 🟡 变异 | state_data 键名改错一字 → 往返断言红；MAX_HISTORY_SIZE 改 101 → 常量断言红 → 还原 |
| 🔄 重构 | docstring + 序列化边界注记（isoformat/json 保真）+ ruff/mypy |

- [x] Subtask 1.1: 🔴 红 — 452 异常用例 + DTO/端口失败测试
- [x] Subtask 1.2: 🟢 绿 — 异常四件套 + agent_checkpoint.py 端口文件
- [x] Subtask 1.3: 🟡🔄 变异实证 + 重构 — 断言活性证明 + 质量门禁

**完成标准/Definition of Done:**
- [x] 452 注册四件套全绿（含 test_code_ranges/test_error_code_uniqueness 自动 8 项 + test_exception_handlers expected_types）
- [x] DTO 域守卫/打包/往返全绿
- [x] `poetry run pytest tests/unit/domain/exceptions/ tests/unit/application/test_agent_checkpoint_model.py -v` 通过

---

### Task 2: EvaluationCheckpointRecorder 应用服务 + 组合根注册 + 端口契约测试

**关联 AC:** AC-1（窗口滚动）/ AC-3（恢复语义）/ AC-4（注册与契约）

#### TDD 循环 A：Recorder 核心（累积 + 打包 + 持久化委托 + 恢复）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_evaluation_checkpoint_recorder.py`（AsyncMock(spec=SnapshotRepositoryProtocol) 存储替身——unit 层合法：①record 单调：累积→打包→save 委托→返回快照 + **连续 record 2 次第二次快照 state_version == 2**（计数器递增锚）②窗口滚动：灌 101 条 → history 长度 100 + 最旧丢弃 + 三序列同窗 ③restore 恢复式：save 捕获快照 → 新 Recorder → restore 逐值恢复（**构造恢复历史长度 3——< MAX_HISTORY_SIZE；R3 注记：③b 的「长度+1/首条不变」断言在满窗恢复下数学不可满足[灌回 100 → record 触发滚动 → 长度仍 100 ≠ 101]，满窗边界归 ② 承载**）+ **③b restore 后 record 1 次 → 新快照 evaluation_history 长度 == 恢复历史长度 + 1 且首条 == 恢复首条 + state_version == 恢复快照 state_version + 1**（累积延续——AC-3② 红前置锚，防纯查询式 restore 假绿）④restore 快照不存在（load 返 None）→ None ⑤restore 结构不完整（state_data 缺键 dict）→ EvaluationHistoryError 452 ⑥save 抛 StorageError → record 包装 452 上抛[内存累积保留断言——最终一致 docstring 语义] + **`exc.__cause__ is 注入的 StorageError`**（包装链锚——AC-2 warning 文本断言的根因验证归此） ⑦session_id 构造 =="agent-evaluation-{agent_id}"） |
| 🟢 绿 | 实现 `src/application/services/evaluation_checkpoint_recorder.py`（class EvaluationCheckpointRecorder: `_history: deque[EvaluationCheckpoint]`/`_h_trend: deque[float]`/`_ca_trend: deque[float]` 全 maxlen=MAX_HISTORY_SIZE + **`_state_version: int = 1` 内存计数器**（record 打包传当前值、**save 成功后 +1**[R3 钦定：失败不消耗版本号——版本数 == 成功落盘数，跳号面归零；与 AutoExecuteService load-derived 惯例同构]；restore 续接 snapshot.state_version + 1——重启后版本延续递增）+ `async def record(...)` 原子三步 + `async def restore(...)` 解包并**灌回三 deque**（`deque(聚合序列, maxlen=MAX_HISTORY_SIZE)`——恢复式语义非只读查询[OD-7③]，恢复聚合 ≤ 窗口上限由快照产出端 maxlen 结构保证）+ StorageError→452 包装 + 结构校验→452） |
| 🟡 变异 | deque maxlen 改 99 → 滚动断言红；restore 缺键校验删 → 452 用例红；restore 灌回删（改纯查询式）→ ③b 累积延续用例红；_state_version 递增删 → ①计数器断言红 → 还原 |
| 🔄 重构 | docstring（SCOPED 注入注记 + 通道语义分述注记[窗口外留存通道是 OTel span、DriftDetected 仅稀疏锚点——OD-8④] + 最终一致语义 + 多进程边界注记[SINGLETON 累积是进程内的——多 worker 分叉知悉，风险 #9]）+ ruff/mypy |

#### TDD 循环 B：组合根注册 + 端口契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/contracts/test_port_contract_agent_checkpoint.py`（11 维度 + REQUIRED_METHODS=["record","restore"] + _DummyResolver 分发 snapshot_repository） |
| 🟢 绿 | composition_root.py `# === Story 5.10 ===` 区段（register_port agent_checkpoint——SINGLETON/lambda resolve snapshot_repository 注入）；**注意：use case 工厂第八依赖归 Task 3 同窗落地（R1-F1 纪律——本 Task 只注册端口不碰工厂）** |
| 🟡 变异 | PortSpec tags 改错 → 契约断言红 → 还原 |
| 🔄 重构 | 对齐 5.9 区段形态 |

- [x] Subtask 2.1: 🔴 红 — Recorder 七场景失败测试
- [x] Subtask 2.2: 🟢 绿 — Recorder 实现 + 组合根注册
- [x] Subtask 2.3: 🔴🟢 契约测试红绿（端口 11 维度）
- [x] Subtask 2.4: 🟡🔄 变异实证 + 重构

**完成标准/Definition of Done:**
- [x] Recorder 单测七场景全绿（含窗口滚动与 452 两路径）
- [x] 契约测试全绿 + resolve 可达
- [x] 覆盖率：新文件行覆盖 ≥85%（应用层门）

---

### Task 3: 主链第八依赖 + record 块 + use case 工厂同窗落地 + 存量断言同步 ×7 + 全家回归

**关联 AC:** AC-2（全部）

> ⚠️ **同窗纪律（R1-F1 两连教训）**：use case 第八构造参数 + 组合根工厂 resolve_optional("agent_checkpoint") + record 块三者必须本 Task 同窗落地。

#### TDD 循环 A：record 块 + 降级网

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/application/use_cases/test_run_agent_workflow.py` 追加 TestExecuteCheckpointBlock（①record 调用与顺序[三键后漂移前——替身捕获 + drift 预填充场景共存断言] ②452 独立降级[**save 抛 StorageError** → Recorder 包装 452 → 主链正常 + 漂移块仍执行 + WARNING——与 AC-2 And①/Task 2⑥ 同口径] ③漂移失败联动[drift port 抛 451 → record 替身捕获非空] ④评估降级联动[evaluate 抛 450 → record 零调用] ⑤None 默认[八参默认断言——test_constructor_eighth_param_default_none 同款] ⑥共享 catch 元组不变断言[inspect 源码或行为——外层 catch 不含 452]） |
| 🟢 绿 | run_agent_workflow.py：第八可选依赖 `checkpoint_recorder: AgentCheckpointPort | None = None`（尾部追加）+ record 块（三键后漂移前 + 内层 `except EvaluationHistoryError: logger.warning` 继续）+ 存字段；composition_root.py 工厂第八依赖 resolve_optional（同窗） |
| 🟡 变异 | record 块移到漂移块后 → 「漂移失败不丢记录」用例红；内层 catch 删 → 452 降级用例红 → 还原 |
| 🔄 重构 | 注释块全中文（Story 5.10 块注释——5.9 漂移块注释形态延续：顺序论证 + 独立降级网论证）+ ruff/mypy |

#### 存量断言同步 ×7 + 回归（非 TDD——资产同步）

- [x] Subtask 3.1: 🔴 红 — TestExecuteCheckpointBlock 六场景失败测试
- [x] Subtask 3.2: 🟢 绿 — 第八依赖 + record 块 + 工厂同窗
- [x] Subtask 3.3: 🟡🔄 变异实证（顺序锚 + catch 面两变异）+ 重构（注释块全中文——5.9 漂移块注释形态延续）
- [x] Subtask 3.4: 存量断言同步 ×7 文件（尾部追加防线——grep 双命令核验：`inspect.signature` 命中行 + `"drift_detector",` 字面行受 5-9 锁死的两文件）+ test_exception_handlers expected_types（Task 1 已做则核验）
- [x] Subtask 3.5: 5-3/5-7/5-8/5-9 存量全家回归（逐一登记：单测/契约/架构/集成/验收全文件清单）

**完成标准/Definition of Done:**
- [x] TestExecuteCheckpointBlock 六场景全绿
- [x] 存量断言 ×7 同步后全绿（5.7 验收 15 场景 / 5.8 验收 13 场景 / 5.9 验收 14 场景全绿）
- [x] 构造签名 grep 核验双命令零漏
- [x] 行为回归：七参构造（None 默认）与 5.9 交付态一致

---

### Task 4: 集成测试与性能——真实 Redis 全链 + P95 双锚 + xdist 组

**关联 AC:** AC-3（全部）/ AC-5（全部）

> **套件型豁免条款（5-9 先例）**：本 Task 是验证型测试套件（对 Task 1-3 已交付行为做真实 Redis 与计时验证）——首跑即绿，红阶段由 Task 0 验收红前置承担；断言活性由关键断言的变异实证承担（Subtask 4.2 变异锚：常量单源改错值 → 验收 AC-5 import 消费断言红）。

#### 集成与性能实现

- [x] Subtask 4.1: `tests/integration/test_integration_checkpoint_evaluation.py`——TestRealRedisCheckpointRoundtrip（真实 RedisAdapter+RedisSnapshotStore 装配：①record ≥3 次落键验证[hget latest + JSON 解析 + 三序列逐值] ②重启恢复[新 Recorder restore 逐值] ③累积延续[restore 后 record → 历史+1] ④restore None ⑤趋势时序 ⑥自清理[teardown delete + exists False]——session_id UUID 前缀隔离 + Redis 探测 skip）
- [x] Subtask 4.2: TestCheckpointPerformance（`pytestmark=[integration, redis, xdist_group("checkpoint-evaluation-perf")]`——redis marker 显式声明[isolation_switch_log 集成 L51 同款]；常量单源 CHECKPOINT_SAVE_P95_LIMIT_SECONDS=0.1 / CHECKPOINT_QUERY_P95_LIMIT_SECONDS=0.05 / 采样 20[warmup 1 + 20]；`_PERF_CACHE` 单 key `checkpoint_perf` 载双指标 summary dict 的 cache-or-compute helper[代码审查 R1 口径修正——功能等价形态]；**满窗锚**：采样前预填充 100 条历史[经 record 公共路径 ×100——不计时不计入调用计数，5-9 预填充口径同款]；正向锚：save/load 调用计数 == 21[采样循环内手工递增——每轮恰一次 record/restore]；quantiles(latencies, n=20)[18] exclusive P95 口径 docstring）+ 全仓 xdist 组 grep 断言（与 14 组互异）+ 5-9 组断言子集形态实证注记（L1586-1617——零同步动作）
- [x] Subtask 4.3: 口径声明落 docstring（save 含 Redis RTT / 满窗口径 / 本地 Redis 前提 / 门=回归绊线 / 20 样本方差知悉五注记——5.8 DC-8④ 诚实注记形态）
- [x] Subtask 4.4: 验收 AC-5.* 场景接线（委托计时消费——import 集成常量与 helper 禁双真源）

**完成标准/Definition of Done:**
- [x] 真实 Redis 六场景全绿（Redis 不可用环境 skip 且 CI 绿）
- [x] P95 双锚达标 + 正向锚 + 满窗锚
- [x] xdist 组互异断言 + 5-9 组断言处置
- [x] 集成覆盖率 ≥75%

---

### Task 5: SDD 架构约束验证测试

**关联 AC:** AC-4（架构合规面）

> **性质说明：** 本 Task 是 **SDD 规范验证测试**（验证架构约束是否被遵守），非 TDD 单元测试。

#### 架构验证测试实现

- [x] Subtask 5.1: 创建 `tests/unit/architecture/test_arch_checkpoint_evaluation.py`——AST 验证器 A：application 触碰文件（agent_checkpoint.py/evaluation_checkpoint_recorder.py/run_agent_workflow.py）第三方 import 白名单（零新增——黑名单断言）
- [x] Subtask 5.2: AST 验证器 B：domain 触碰面收窄（EvaluationHistoryError 仅在 exceptions 三件 + **events 零触碰断言**[OD-6 契约——本 Story 与 5.9 差异面] + 组合根外零实例化[grep EvaluationCheckpointRecorder( 构造点] + 依赖方向[evaluation_checkpoint_recorder.py import src.domain 断言——application→domain 合法面]）
- [x] Subtask 5.3: AST 验证器 C：主链 record 块静态锚（execute 体内 record 调用 + `result.evidence.confidence` 引用 + 内层 except EvaluationHistoryError + **漂移块之前顺序锚**[AST 兄弟节点序——drift 调用索引 > record 调用索引断言]）+ use case 八依赖签名基线 + 两新文件标准库零外部依赖断言（词边界正则——test_arch_evaluation.py helper 族）
- [x] Subtask 5.4: 运行完整测试套件并生成报告（`poetry run pytest tests/unit/architecture/ -v`）

**完成标准/Definition of Done:**
- [x] 所有架构/约束测试通过
- [x] 测试输出清晰的合规报告
- [x] 任何违规都会导致测试失败
- [x] 循环依赖检测使用 ruff/isort（不引入额外工具）

---

### Task 6: 开发结束验收测试

**关联 AC:** 全 AC 收尾

> **性质说明：** 本 Task 对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 完善 `test_acceptance_checkpoint_evaluation.feature` 收尾验收场景（src 新建/修改清单 + tests 四目录完成清单逐项存在性断言）
| 🟢 绿 | BDD 步骤实现（收尾场景断言面——文件清单与「待创建」清单一致性；套件型豁免条款知悉[首跑即绿——红由 Task 0 前置承担]）
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [x] Subtask 6.1: 收尾场景——src 完成清单逐项确认（**2 新建**：agent_checkpoint.py / evaluation_checkpoint_recorder.py；**7 修改**：evaluation_exceptions.py / _code_ranges.py / domain/exceptions/__init__.py / exception_handlers.py / run_agent_workflow.py / composition_root.py / application/ports/__init__.py；另 docs 面：sisys-uni-exception-design.md §3.3.2 两处 + sisys-core-domain-design.md §17.3.8 注记）
- [x] Subtask 6.2: 收尾场景——tests 四目录完成清单逐项确认（**7 新建** + **3 追加**[test_run_agent_workflow.py（追加块+签名同步重叠）/ test_evaluation_exceptions.py（452 用例）/ test_exception_handlers.py（expected_types）] + **6 存量签名同步文件**[= 继承清单第 9 条 ×7 减 run_agent_workflow（已计入 3 追加）——phoenix 验收/arch phoenix/arch evaluation/arch drift/agent_evaluation 验收/drift 验收]）
- [x] Subtask 6.3: 运行开发结束验收测试并确认通过（14 场景全绿）
- [x] Subtask 6.4: 收尾校验三件套：`poetry run pytest tests/ -n 8`（并行 + 连续 5 次无随机失败）+ `poetry run ruff check src/ tests/` + `poetry run mypy .`（**全仓含 tests**——5-9 教训）+ 三条 grep 自查零输出
- [x] Subtask 6.5: 文档同步（sisys-uni-exception-design.md §3.3.2 两处[编码分配表 + 子域范围表——Task 1 重构行已列] + sisys-core-domain-design.md §17.3.8 追加 Story 5.10 实现注记[5.9 注记形态延续——OD-2/3/4/7 落地口径] + deferred-work.md 五条注记核验[Task 0.7 已落] + sprint-status 状态流转 + 本故事文件变更日志）

**完成标准/Definition of Done:**
- [x] src 完成清单已逐项验证确认
- [x] tests 四目录完成清单已逐项验证确认
- [x] 开发结束验收测试通过（14 场景）
- [x] Story 可进入 `review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md) + [`sisys-core-domain-design.md §17.3.8`](../../../docs/architecture/sisys-core-domain-design.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ 可观测附加面附加哲学（5.8 DC-5/5.9 延续——附加面边界=catch 边界，失败降级不阻断主链）
- **设计约束:** 领域层零依赖；application→domain 允许/禁 interfaces·infrastructure；端口唯一注册（composition_root）；R1 基础端口（SnapshotRepositoryProtocol）+ R2 应用端口组合注入（AgentCheckpointPort）+ R3 存储实现既有（RedisSnapshotStore）+ R4 零接口层
- **接口治理:** PortSpec 元数据（name/version/interface/impl/module/lifetime/owner/tags）；SINGLETON 论证（跨 run 累积——状态即功能）；resolve_optional 可选依赖接线（5.6/5.8/5.9 先例族）
- **技术栈:** Python 3.11+ 纯标准库（deque/dataclass/asyncio/json）——**零新运行时依赖**（5.7 OD-1 家族原则第四 Story 延续）

### 关键架构决策 Key Design Decisions

| # | 决策 | 理由 | 备选（弃） |
|---|------|------|-----------|
| DC-1 | 评估数据经 state_data 键承载不扩实体字段（OD-3） | frozen 实体兼容 + 序列化零改动 + 6.3 无冲突复用 | 扩 CheckpointSnapshot 三字段（弃——回归面大零收益） |
| DC-2 | record 原子单方法（累积+打包+save 一次调用）（OD-7） | 无中间态语义；调用方可断言返回快照 | record/save 两方法（弃——累积成功 save 失败的中间态无消费语义） |
| DC-3 | record 块位序：三键后、漂移块前 + 独立内层 452 catch | 两独立可观测附加面互不牵连：record 失败不阻漂移、漂移失败不丢记录；共享 catch 元组零改动（对 5-9 交付形态最小侵入） | record 放漂移块后共享 catch（弃——漂移 451 抛出丢记录）；平级双 try（弃——evaluation_result 存活域破坏 NameError） |
| DC-4 | 趋势序列 Recorder 自持（OD-4） | 检测器窗口是算法态非历史源；检测器零改动；与 V1-EV12 解耦 | cusum_detector.get_trend()（弃——窗口语义不匹配且职责纠缠） |
| DC-5 | 窗口上限 100 常量单源（OD-8） | Redis latest 覆盖写语义下防快照体积线性膨胀；满窗性能锚有效化 | 无界历史（弃——IO 延迟击穿 P95 门） |
| DC-6 | session_id 命名空间 `agent-evaluation-{agent_id}` | 实测 AutoExecuteService 路由快照用 per-run session_id（UUID 形态无前缀——auto_execute_service L62/L93）：前缀 vs 无前缀、per-agent 聚合滚动 vs per-run 单发的基数差异——键冲突面为零；docstring 注记防按 run 查评估快照 | 直接 str(agent_id)（弃——语义混入路由快照键空间） |
| DC-7 | SINGLETON 生命周期 + SCOPED snapshot_repository 固定实例注入 + **per-agent 键控窗口**（OD-9——代码审查 R1 修正：`_windows` 按 session_id 键控，各 Agent 三 deque + 窗口级版本计数器隔离；同进程多 Agent 混串缺陷结构性修复） | Recorder 跨 run 累积（进程生命周期=历史生命周期）；RedisSnapshotStore 无状态委托 adapter 固定实例安全（docstring 注记论证——论证靠「无状态」而非 clear_scoped 未接线环境巧合）；**MVP 单进程前提显式声明**（多 worker 下各进程窗口分叉 + Redis latest 覆盖写最后写者胜——风险 #9；进程内键控已落地，跨进程键控/粘性路由是 V1 多进程面）；窗口数 = agent 实体数无上界知悉（instantiate 非幂等——V1 LRU/TTL 治理锚） | TRANSIENT（弃——每 resolve 新累积器历史清零）；全局单窗口（弃——代码审查 R1 P1：跨 Agent 混串） |
| DC-8 | 不发布 CheckpointReached / 不引入 CHECKPOINTED（OD-5/OD-6） | BLM 审批语义 vs 可观测附加面语义分立；无状态转换可达路径；锚位 6.3 | 照设计字面引入（弃——无消费方守卫扩展+语义误植） |
| DC-9 | restore 返回 None 非异常 | 快照不存在是正常态（首次评估前）；AutoExecuteService.load 同款 | 抛 452（弃——正常态异常化） |
| DC-10 | predicted 从 result.evidence.confidence 主链直传 | V1-EV3 钦定兑现（只存 EvaluationResult 会丢 predicted）；span `eval.confidence` 键同源（L202） | 快照只存 EvaluationResult（弃——V1-EV3 明示缺陷形态） |

### 风险登记

| # | 风险 | 缓解 |
|---|------|------|
| 1 | **真实 Redis 环境依赖**（验收/集成 AC-3/AC-5 需本地 Redis——.env 配置；CI 无 Redis 时 skip） | 场景级 Redis 探测（TCP ping）→ pytest.skip 动态跳过；单元面（Task 2）AsyncMock 存储替身全绿不依赖 Redis |
| 2 | **主链同步路径新增 Redis IO**（record 内联 save——每评估一次网络往返） | 本地 Redis RTT<1ms vs P95<100ms 门（两个数量级余量）；452 独立降级网兜底（Redis 故障不阻断主链——评估链其余面照常）；部署形态知悉注记（远程 Redis RTT 是 V1 容量评估面） |
| 3 | **组合根工厂与参数同窗**（R1-F1/5-9 两连重演面） | Task 3 显式同窗纪律（参数+工厂+record 块三件一 Task）；Task 2 只注册端口不碰工厂 |
| 4 | **存量断言同步遗漏**（×7 文件——5-8 预登记 2 实施发现 3 / 5-9 预登记 3 grep 补全 5 的教训） | 创建期已 grep 实证 16 行命中归 7 处（inspect.signature 口径 + 字面行 12 行/7 文件双清单——含 5-9 自身资产 L1188/L1207 最易漏处与 ⑥⑦ `_USE_CASE_INIT_PARAMS` 常量本体）；dev 时重新 grep 定位（行号锚漂移知悉）；核验双命令写入 AC-2 |
| 5 | **浮点往返保真**（state_data JSON 序列化 float 往返） | Python json repr 往返保证（float→str→float 精确）；断言纪律精确等式 + 手算锚用一位小数避开边界；Task 1 往返测试锚定 |
| 6 | **SINGLETON 累积器跨场景污染**（验收/集成并行） | 每场景手工新实例（不走 resolve）；「连续累积」场景显式同实例；xdist 组串行隔离计时面 |
| 7 | **_PERF_CACHE 与 xdist 分发**（缓存命中依赖同 worker） | 集成/验收逐字同组 checkpoint-evaluation-perf（loadgroup）；组名 14 组互异 grep 断言；「命中或首次采样」形态禁先跑断言 |
| 8 | **evaluations 域语义膨胀**（CheckpointWithEvaluation 与 6.3 BLM 快照的边界） | 范围边界表显式切分（BLM 面全列 ❌ 不做）；边界真实依据 = state_data 四键契约显式钦定（OD-3）+ stage_id="evaluation" 语义分界——6.3 BLM 键经新键扩展进入零冲突（R1-E 修正：四键中仅 evaluation_history 带 evaluation_ 前缀，原「evaluation_* 前缀键留净空间」表述与 OD-3 键名不符） |
| 9 | **多 worker 部署累积器分叉 + Redis 故障双义 + 重启回退**：SINGLETON 累积是进程内的——uvicorn 多 worker 下各进程**各 Agent 窗口**分叉、Redis latest 覆盖写（最后写者胜）使其他 worker 的窗口外谱系静默丢失；store.load 任何异常（含 Redis 故障）均返回 None（L162-164）——restore 返 None 双义下「故障静默为空历史」是既定行为；**单进程异常重启后未 restore 直接 record**：新进程计数器归 1 + 空窗，首 record 以 state_version=1/单条历史覆盖 Redis latest（**历史与版本双回退**——内存计数器与 AutoExecuteService load-derived 递增[天然重启安全]的机制差异反面；主链不调 restore，「重启存活」的完整兑现依赖未来消费方[V1-EV12/6.3]启动时 restore——AC-3 场景覆盖边界即此：只测 restore 后 record）。**[代码审查 R1 已修复] 单进程内跨 Agent 混流**：v2.0.0 全局单窗口形态下同进程多 Agent 共享窗口混串——OD-9 per-agent 键控窗口已结构性修复（多 worker 分叉/最后写者胜仍是本风险残余面） | MVP 单进程前提显式声明（Recorder docstring 注记——DC-7）；**进程内 per-agent 键控已落地（OD-9）**，跨进程键控/粘性路由是 V1 多进程面（6.3/容量评估再议）；同 agent 并发 record 的落盘序竞争后果良性（打包含对方记录后落盘收敛、仅服务端到达序反转时 Redis 短暂少一条且下次 record 自愈——内存是全窗真源）；重启回退知悉注记落 Recorder docstring（回退形态语义 = 覆盖写既有行为，无需 CAS——state_version 仅排序语义非乐观锁）；窗口数无上界知悉（instantiate 非幂等——慢泄漏，V1 LRU/TTL 治理锚） |
| 10 | **state_data 键结构演进向后兼容**：6.3 改键结构/增键后，旧快照经 from_snapshot 严格四键校验会 452（restore 失败）；state_data 内无 schema 版本标记（state_version 是排序语义非 schema 版本） | 旧快照读兼容策略随 6.3 定（当前既定行为：缺键 → 452 fail-loud）；TTL 24h 自然收窄旧快照存量（>24h 历史整键过期） |

### 项目结构说明 Project Structure

```
src/
├── application/
│   ├── ports/
│   │   ├── agent_tracing.py          # 5.7 追踪端口（零改动）
│   │   ├── agent_evaluation.py       # 5.8 评估端口（零改动——EvaluationResult 消费）
│   │   ├── agent_drift.py            # 5.9 漂移端口（零改动）
│   │   ├── agent_checkpoint.py       # ★ 5.10 新建：AgentCheckpointPort + EvaluationCheckpoint + CheckpointWithEvaluation
│   │   └── __init__.py               # ▲ 修改：三符号导出（agent_checkpoint 组按字母序插导入块最前——c<d）
│   ├── services/
│   │   ├── evaluation_harness.py     # 5.8（零改动）
│   │   └── evaluation_checkpoint_recorder.py  # ★ 5.10 新建：EvaluationCheckpointRecorder（组合注入 SnapshotRepositoryProtocol）
│   └── use_cases/
│       └── run_agent_workflow.py     # ▲ 修改：第八可选依赖 + record 块（纯附加）
├── domain/
│   ├── entities/checkpoint_snapshot.py   # 零改动（OD-3）
│   ├── ports/snapshot_repository_protocol.py  # 零改动（直接消费）
│   ├── exceptions/
│   │   ├── evaluation_exceptions.py  # ▲ 修改：EvaluationHistoryError 452 追加
│   │   ├── __init__.py               # ▲ 修改：EvaluationHistoryError 导出
│   │   └── _code_ranges.py           # ▲ 修改：_CLASS_TO_SUBDOMAIN 一行
│   └── events/                       # 零改动（OD-6——events 零触碰）
├── infrastructure/
│   └── storage/redis/redis_snapshot_store.py  # 零改动（直接消费）
├── interfaces/
│   └── api/exception_handlers.py     # ▲ 修改：EXCEPTION_HTTP_MAP 452→500
└── composition_root.py               # ▲ 修改：Story 5.10 区段 + 工厂第八依赖

tests/
├── unit/
│   ├── application/
│   │   ├── test_agent_checkpoint_model.py          # ★ 新建
│   │   ├── services/test_evaluation_checkpoint_recorder.py  # ★ 新建
│   │   └── use_cases/test_run_agent_workflow.py    # ▲ 追加 TestExecuteCheckpointBlock + 签名同步
│   ├── domain/exceptions/test_evaluation_exceptions.py  # ▲ 追加 452
│   ├── architecture/test_arch_checkpoint_evaluation.py  # ★ 新建（AST 验证器 A/B/C）
│   └── architecture/test_arch_phoenix_tracer.py 等三件  # ▲ 签名同步 ×3（arch phoenix/arch evaluation/arch drift）
├── contracts/test_port_contract_agent_checkpoint.py  # ★ 新建
├── integration/test_integration_checkpoint_evaluation.py  # ★ 新建（真实 Redis + P95 双锚）
├── acceptance/
│   ├── test_acceptance_checkpoint_evaluation.feature  # ★ 新建（14 场景）
│   ├── test_acceptance_checkpoint_evaluation.py       # ★ 新建
│   └── test_acceptance_phoenix_tracer.py 等三件      # ▲ 签名同步 ×3
└── unit/interfaces/api/test_exception_handlers.py    # ▲ expected_types 追加
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 5-9 CUSUM 漂移检测与触发重校准](./5-9-cusum-drift-detection-recalibration.md) + [Story 5-8](./5-8-agent-output-quality-evaluation.md)

**关键学习/Key Learnings:**
- 构造签名扩展的存量断言面必须 grep 数清（5-8 预登记 2 实施发现 3；5-9 预登记 3 补全 5——本 Story 创建期已实证 7 处含 5-9 自身资产）
- 组合根工厂注入与构造参数必须同窗落地（R1-F1/5-9 两连重演——提前注入 kwarg 窗口期每次 resolve TypeError）
- 断言可满足性推演先行（5-9 文档审查 3 个 P0 全是数学不可满足锚）；浮点纪律：同式表达式 + 计算序同形 + 禁 approx + 禁十进制字面量
- 嵌入式可观测组件定位（5.7/5.8/5.9 同族）：无 API/CLI 面、span 键最小集、事件仅在领域告警语义时发布
- 附加面降级哲学：None 默认纯附加、失败降级不阻断主链、键/记录缺席=常态勿误读
- mypy 必须 `mypy .` 全仓含 tests/（5-9 Task 6.4 只跑 src/ 漏 tests 面 ×9 教训）
- 行号锚随 dev 漂移——后续引用以 grep 定位法替代（5-9 R3-1）

**应用到本故事/Applied to This Story:**
- [x] 存量断言 ×7 清单创建期 grep 实证（含核验双命令——AC-2）
- [x] 同窗纪律显式写入 Task 3（DC-3/Risk #3）
- [x] 浮点纪律写入 TDD 禁止行为（禁 approx/十进制字面量/计算序不同形）
- [x] 嵌入式定位写入范围边界（REST/CLI ❌ 不做）
- [x] 独立降级网两级 catch 形态（DC-3——附加面独立性的结构化承载）
- [x] mypy 全仓口径写入 TDD 重构行与 Task 6.4
- [x] 行号锚漂移知悉写入存量触碰清单尾注
- [x] [R1] restore 恢复式语义机制显式定稿（防纯查询式实现假绿——Task 2 红③b/绿灌回/变异三锚 + state_version 计数器续接）
- [x] [R1] 计数可对账纪律（四处计数实证修正：9→7 件/六→五分数/13→16 行/2+5→2+7 修改）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.3（Claude Code） |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-10-29 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（L1857-1900/L1446/L532/L204） |
| **架构文档** | `docs/architecture/sisys-core-domain-design.md` §17.3.8 + `architecture.md` + `sisys-checkpoint-timetravel-design.md` |
| **前一个 Story** | `5-9-cusum-drift-detection-recalibration.md`（+5-8/5-7） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **留项台账** | `_bmad-output/implementation-artifacts/deferred-work.md`（L17/L194/L261/L282 + 5-1 D-1） |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（L1857-1900 全锚）
- [x] 架构约束从 architecture.md / core-domain-design §17.3.8 / checkpoint-timetravel-design 提取
- [x] 前一个故事学习经验整合（5-9 十条教训清单逐条应用）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 留项处置五条裁定（deferred-work 钦定 5.10 触发方全处置）
- [x] 存量断言同步 ×7 创建期 grep 实证
- [x] 多 Agent 并行调研（checkpoint 基建/评估链/前故事经验/验收测试风格四视角）
- [x] **Task 0**：Gherkin 14 场景 + BDD 步骤实现（延迟 import 红验证 14/14 failed 逐场景承载）+ deferred-work 五条注记落档 + 链路接线断言清单五件
- [x] **Task 1**：EvaluationHistoryError 452 注册四件套（红 14→绿 145→变异 context_extra）+ agent_checkpoint.py 端口文件（红 35→绿→变异×2 键名/常量）+ §3.3.2 两处更新 + expected_types 追加
- [x] **Task 2**：EvaluationCheckpointRecorder（红 12→绿→变异×4[maxlen/结构校验/灌回删/计数器]）+ 组合根 Story 5.10 区段 SINGLETON 注册 + 契约 11 维度（红 12→绿→变异 tags）
- [x] **Task 3**：主链第八依赖 + record 块（三键后漂移前 + 内层 452 独立 catch）+ 工厂 resolve_optional 同窗三件 + TestExecuteCheckpointBlock 六场景（红 6→绿→变异×2 顺序锚/catch 面）+ 存量断言同步 ×7（尾部追加）+ 全家回归（架构 921 + 验收 42 全绿）
- [x] **Task 4**：真实 Redis 六场景（落键两层 json/重启恢复/累积延续/None/趋势时序/自清理）+ P95 双锚（save ~1ms<100ms / query ~1ms<50ms——满窗 100 条预填充）+ 正向锚 21 + xdist 组互异（首跑即绿——套件型豁免；变异锚：常量 0.05→验收红→还原）
- [x] **Task 5**：AST 验证器 A（application 白名单零新增 + 端口/Recorder 纯标准库）+ B（业务四目录零命中 + events 全域零触碰[OD-6] + 452 仅 exceptions 三件 + 组合根外零实例化 + 依赖方向）+ C（record 块四静态锚含 AST 行号序 + 八依赖签名 + 零外部依赖）+ 零抑制守卫 parametrize 20 文件[代码审查 R1 勘误——原「45 文件」失实：9 src + 11 tests；42 用例]
- [x] **Task 6**：验收 14 场景全绿 + 收尾清单场景（src 2+7 / tests 7+3+6 逐项）+ mypy 全仓 1806 files 零错 + ruff 全清 + 三条 grep 自查零输出（触碰文件）+ 单元面 5 轮连续绿 + 文档同步（§17.3.8 注记 + sprint-status 流转）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/5-10-checkpoint-with-evaluation-integration.md`
- `src/application/ports/agent_checkpoint.py` - 端口 + 双 DTO（AgentCheckpointPort + EvaluationCheckpoint + CheckpointWithEvaluation + MAX_HISTORY_SIZE）
- `src/application/services/evaluation_checkpoint_recorder.py` - 端口实现（累积器 + record/restore + 452 包装）
- `tests/unit/application/test_agent_checkpoint_model.py` - DTO 单测（35 用例）
- `tests/unit/application/services/test_evaluation_checkpoint_recorder.py` - Recorder 单测（12 用例七场景）
- `tests/contracts/test_port_contract_agent_checkpoint.py` - 端口契约（11 维度）
- `tests/integration/test_integration_checkpoint_evaluation.py` - 真实 Redis 集成 + P95 双锚（10 用例 + sample_checkpoint_perf 委托 helper）
- `tests/unit/architecture/test_arch_checkpoint_evaluation.py` - AST 架构验证（A/B/C + 零抑制守卫 42 用例[代码审查 R1 勘误——原报 45 失实]）
- `tests/acceptance/test_acceptance_checkpoint_evaluation.feature` - Gherkin 14 场景
- `tests/acceptance/test_acceptance_checkpoint_evaluation.py` - BDD 步骤实现（14 场景 @scenario 显式绑定）

**修改的文件/Modified Files (Dev Story 实施):**
- `src/domain/exceptions/evaluation_exceptions.py`（EvaluationHistoryError 452 追加 + 模块 docstring 扩段）
- `src/domain/exceptions/_code_ranges.py`（_CLASS_TO_SUBDOMAIN 增行 + 段注释 452 取用更新）
- `src/domain/exceptions/__init__.py`（EvaluationHistoryError 导入 + __all__）
- `src/interfaces/api/exception_handlers.py`（EXCEPTION_HTTP_MAP 452→500 休眠映射 + 导入）
- `src/application/use_cases/run_agent_workflow.py`（第八可选依赖 + record 块[三键后漂移前 + 内层 452 catch] + AgentCheckpointPort/EvaluationHistoryError import）
- `src/composition_root.py`（`# === Story 5.10 ===` 区段 agent_checkpoint 注册 + 工厂第八依赖 resolve_optional）
- `src/application/ports/__init__.py`（AgentCheckpointPort/CheckpointWithEvaluation/EvaluationCheckpoint 导出——字母序块首）
- `tests/unit/domain/exceptions/test_evaluation_exceptions.py`（452 用例三组 14 个追加）
- `tests/unit/interfaces/api/test_exception_handlers.py`（expected_types 追加 + 导入）
- `tests/unit/application/use_cases/test_run_agent_workflow.py`（TestExecuteCheckpointBlock 六场景追加 + 两处签名清单尾部追加）
- 存量断言同步 ×7（test_acceptance_phoenix_tracer L1375 后 + test_arch_phoenix_tracer 常量本体 + test_arch_evaluation 常量本体 + test_arch_drift_detection 常量本体 + test_acceptance_agent_evaluation L1327 后 + test_acceptance_drift_detection L1207 后——**尾部追加为主 + 4 文件签名基线断言块内消息/注释行必要同步改写**[代码审查 R1 口径修正：断言消息「七依赖→八依赖」与常量注释行的改写是被测签名从七变八的语义必要同步，无功能性改写；5.9 回执锁死字面行原样保留零触碰]）
- `docs/architecture/sisys-uni-exception-design.md` §3.3.2 两处（编码分配表 452 具体行插入 + 预留行收缩 453~459 + 子域范围表 evaluation 行说明）
- `docs/architecture/sisys-core-domain-design.md` §17.3.8（Story 5.10 实现注记 blockquote——OD-2/3/4/7 落地口径 + CHECKPOINTED 不引入 + 性能实测）
- `_bmad-output/implementation-artifacts/deferred-work.md`（五条注记：langgraph retry/timeout 顺延 6.6 + R1-DF5 顺延 6.3 + V1-EV12 数据面就绪 + V1-EV3 predicted 兑现 + 新增 D1-5.1 CHECKPOINTED 区段）
- `_bmad-output/implementation-artifacts/sprint-status.yaml`（5-10 状态流转）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 5.10 |
| **Story Key** | 5-10-checkpoint-with-evaluation-integration |
| **File** | `_bmad-output/implementation-artifacts/stories/5-10-checkpoint-with-evaluation-integration.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 5: 单 Agent 战略规划能力 |
| **价值组** | Agent 评估与可观测性（EV 族第四 Story——收官面） |
| **优先级** | P1（FR-EV-04）/ 执行序 P1-10 |
| **覆盖 FR** | FR-EV-04 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-6）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-5 + 收尾）
3. [x] Architecture constraints extracted 架构约束已提取（R1-R4 落位判定 + 六边形矩阵）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（十条逐条应用）
5. [x] Sprint status synced to `ready-for-dev`（sprint-status.yaml L168 已更新）

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | restore「累积延续」语义缺机制处方：端口 restore 返回纯 DTO，AC-3②「restore 后 record → 历史=恢复+1」要求 restore 灌回内部三 deque——Task 2 按字面实现纯查询式会让 Task 4 首跑即红（破坏套件型豁免前提） | P1 | OD-7③ 升格恢复式语义 + 端口契约 docstring 注记副作用 + Task 2 红补 ③b 用例（restore 后 record 断言）+ 绿明写灌回三 deque + 变异补第三锚；联动定稿 state_version 机制（Recorder 内存计数器初始 1 / restore 续接 snapshot.state_version+1——AC-1 Then② 与 to_checkpoint_snapshot(session_id, state_version=1) 签名同步） |
| R1-2 | 测试资产计数错位：「新建九件」枚举仅 7 件（9 混入 2 个 src 文件）；Subtask 6.2「9 新建+3 追加」漏 6 个签名同步文件——Task 6.2 收尾按「9 新建」断言必红 | P1 | item 6 改「七件」；Subtask 6.2 改「7 新建 + 3 追加 + 6 存量签名同步（run_agent_workflow 重叠）」；Subtask 6.1 同步改枚举式「2 新建 + 7 修改」（原「2 新建 + 5 修改」任何读法对不到 7） |
| R1-3 | sisys-uni-exception-design.md §3.3.2 更新仅异常契约节一处承诺——File List/Subtask 6.5/Task 1 重构行/项目结构全部缺失（注册文档面会被执行遗漏）；且该文档有双同号 3.3.2 节、5.9 先例是分配表+子域范围表两处同更 | P1 | 四处传播补齐（File List/6.5/Task 1 重构行明确两处更新点：编码分配表 L743/L744 插行 + 子域范围表 L823 行说明） |
| R1-4 | agent_evaluation.py L102-104 被列为 5.10 规划注释锚——实证该处是 5.9 CUSUM 消费注记（全文件 grep "5.10" 零命中），引用错位 | P1 | 「明确不存在」节 grep 锚点清单删除该项（真锚点 evaluation_harness.py L70 与 composition_root.py L2991 保留） |
| R1-5 | 验收/集成 pytestmark 疑缺 pytest.mark.redis：文件名 checkpoint_evaluation 不命中 conftest 服务关键词映射、AC-3/AC-5 场景用真实 Redis——同处境先例 isolation_switch_log 两侧均显式声明 | P1 | 两侧 pytestmark 补 redis marker（验收骨架节 + Task 4.2，附先例锚） |
| R1-6 | 「六分数字段」计数错：EvaluationCheckpoint 七字段中 [0,1] 数值字段是 5 个（四分数+predicted），「六」无字段支撑且与 SDD 数据模型节自相矛盾 | P2 | 三处「六」→「五」+ 参数化钦定 5 字段名清单 + 矩阵行「七字段 [0,1]」→「五分数字段 [0,1] + agent_id 非空」 |
| R1-7 | 「13 行命中归七处」计数失实：实测 inspect.signature 16 行/7 文件（execute 签名 2 行不受影响）；清单编号列到 ⑧ 与 ×7 打架；⑥⑦ 漏登 _USE_CASE_INIT_PARAMS 常量本体（只改断言行漏常量则架构测试红） | P2 | 头部改 16 行口径 + 两 grep 分列；⑧ 注记「异常注册面不计入 ×7」；⑥⑦ 补常量本体行号（L54-62/L50-58）+ ⑤ targets dict 裸锚信息补全 |
| R1-8 | OD-8④「窗口外历史经 DriftDetected 事件通道留存」论证半失实：事件仅在确认漂移时发布且只携带单确认样本——绝大多数窗口外评估不出现在任何事件里（真留存通道只有 OTel span/Phoenix） | P2 | OD-8④/AC-1 And docstring 注记/Task 2 重构行三处改「通道语义分述」（span 留存/事件稀疏锚点）——保持窗口裁定不动 |
| R1-9 | 多 worker 部署累积器分叉 + Redis latest 覆盖写边界未声明；store.load 吞一切异常返 None（故障≠不存在）双义未登记；state_data 演进向后兼容未登记 | P2 | 风险表补 #9（多进程分叉 + load 双义 + 并发落盘序良性论证）与 #10（state_data 演进兼容 + TTL 收窄）；DC-7 补 MVP 单进程前提声明 |
| R1-10 | 风险 #8「evaluation_* 前缀键为 6.3 留净空间」与 OD-3 四键名矛盾（agent_id/hallucination_trend 无该前缀） | P2 | 改真实边界依据（四键契约钦定 + stage_id 语义分界 + 6.3 新键扩展零冲突） |
| R1-11 | AC-2 可观测面与注入深度：Given 装配未列 OTel 通道（三键 span 断言无观测面）；「_RaisingSnapshotRepo save 抛 452」跳过 Recorder 包装环节（真实路径是 StorageError→Recorder 包装 452）；「按实际写死文本断言」在红阶段循环指涉；「record 块在 try 体外不可达」措辞倒置（实际在体内） | P2/P3 | Given 补 OTel 通道（InMemorySpanExporter + 双复位）；注入统一 StorageError 口径（与 Task 2⑥ 一致）；WARNING 断言改 str 包含形态（5-9 451 同款——红绿皆可写）；措辞改正「同一 try 体内控制流跳转」 |
| R1-12 | 杂项澄清批：评估块口径 L220-237（L238 是块外 return）；L202 属根 span 十属性块；Redis latest 单 field 双层 JSON（两层 json_loads）；实体时间字段名 timestamp/state_version 默认 0 显式传参/load 吞异常/exists 是具体类方法非协议面（删「替身 exists」）；AC-1③ json 机理错位（纯内存往返 vs AC-3 json 双程）；AC-3「单调时序」→「顺序保持」；满窗预填充路径钦定（record 公共路径 ×100 不计时）；P95 20 样本方差注记；矩阵 Task 4 指派错格修正 + 3.5/4.4 漏行补 + AC-4 行 2.4→2.3；结构树 ×4→×3 + 补 3 个 src 修改文件；checkbox 补齐（state_version/catch 三元组不变）；Subtask 3.3 🔄 标记；「注册四件套」三口径统一（File List 四文件口径）；「存量同步义务」条件落空改实证结论（5-9 子集断言零动作）；452 休眠映射注记 + docstring 撞语限定；DC-6 per-agent/per-run 基数注记；业务价值句 V1-EV12 括注；AC-2 窗口滚动指向改 Task 2 | P2/P3 | 各出现位逐一修正（本表合并登记） |

> Round 1 审查投入：D1 四视角调研（Checkpoint 基建/主链评估块/异常端口体系/测试基建——P0 全零）+ D2 三视角审查（一致性传播/可行性可测试性/科学性业界对标）。总计发现：P0×0 + P1×5 + P2×约12 + P3×约15；修复如上（全部文档级，零设计变更——F 视角确认 DC-1~10 与异常契约/性能锚全部科学成立）。
>
> | # | 问题 | 严重度 | 修复方案 |
> |---|------|--------|----------|
> | R2-1 | R1-11 StorageError 注入统一使 AC-2 WARNING 断言不可满足：str(领域异常) 恒等于 message（DomainError 构造——cause 链只进 to_dict 不进 str）、注入物（StorageError 动态文案）≠ 被记录物（452 静态文案）、5-9「注入异常 str 同款」成立前提（注入物==被记录物）被 R1 自己打破 | P1 | 断言锚改 452 静态 message 锚（钦定 message="评估历史持久化失败"——异常契约节落定）+ 包装链根因断言 `exc.__cause__ is 注入 StorageError` 归 Task 2⑥ 单测（不改生产行为、与 450/451 族静态文案模板一致） |
> | R2-2 | 「重启/分叉后未 restore 直接 record → state_version=1 + 单条历史覆盖 Redis latest（历史与版本双回退）」形态无知悉注记——风险 #9「MVP 单进程前提」措辞暗示单进程安全但跨重启同构失真；AutoExecuteService 是 load-derived 递增（天然重启安全）与 Recorder 内存计数器的机制差异未点破 | P2 | 风险 #9 追加回退形态知悉（主链不调 restore——重启存活完整兑现依赖未来消费方启动时 restore；AC-3 场景覆盖边界即此）+ 继承表先例行补「差异②机制知悉」（load-derived vs 零 load 计数器） |
> | R2-3 | Task 3 循环 A 红处方②「save 抛」无类型限定——与 AC-2/Task 2⑥ 统一 StorageError 口径脱节（dev 按字面注入裸 Exception 会红因错位、注入 452 直抛则弱化） | P2 | 红处方② 补「save 抛 StorageError」+ 同口径注记 |
> | R2-4 | P3 批：AC-5 warmup 轮复合构成未钦定（双锚下 warmup 只 warm 单锚使另一锚计数 20≠21 假红）；6.2 括注「已含」读法费解；redis marker 混合文件（AC-1×3/AC-4×2 纯内存被文件级 marker 覆盖——-m "not redis" 环境会排除纯内存场景）；矩阵 AC-4 行 3.4 半修（工厂注入在 3.2）；结构树 tests/application 双「└──」字符画；StorageError import 面提示缺失；OD-7/Task 3 绿行表格内未转义「\|」（v1.0.0 既有、GFM 渲染裂列但纯文本消费无实害——登记不改） | P3 | 逐一清偿（前六项）；末项登记知悉 |
>
> Round 2 审查投入：回归核查（R2-A——git diff 取证 R1-1~R1-12 传播完备性全过 + 新引入矛盾扫描）+ 组合交互（R2-B——七组组合推演五组全过）。总计发现：P0×0 + P1×1 + P2×2 + P3×7（含登记 1）；R1 修复传播完备性零漏网实证。
>
> | # | 问题 | 严重度 | 修复方案 |
> |---|------|--------|----------|
> | R3-1 | Task 2 单测③b 在满窗恢复构造下断言数学不可满足：③未钦定恢复历史长度——L=100 时「长度==恢复+1 且首条==恢复首条」在正确实现下恒红（deque 滚动），相邻②恰是 101 条灌装存在状态复用路径；死红破坏 TDD 闭环并连带推翻 Task 4 套件型豁免前提（R1-1 修复引入的断言缺构造约束） | P1 | ③ 补「构造恢复历史长度 3（< MAX_HISTORY_SIZE）——③b 断言满窗不可满足，满窗边界归 ② 承载」（AC-3② 由「≥3 次」钦定天然安全——证明缺口是遗漏非设计） |
> | R3-2 | P3 批：`_state_version` +1 时点相对 save 失败未钦定（α 失败即跳号 / β 失败不消耗两实现均过现有断言——非判别式）；AC-2.1「末条记录七字段与评估分数逐值相等」措辞（七字段中仅 5 个是分数）；AC-2 Given 未显式列第七依赖 drift_detector 注入（AC-2.2 断言依赖，隐式覆盖） | P3 | 逐一清偿：绿行钦定 β「save 成功后 +1（版本数==成功落盘数，跳号面归零）」；断言措辞改五分数字段+agent_id+recorded_at 分述；Given 补 drift_detector 注入 |
>
> Round 3 审查投入：单深度推演（14 场景三轴逐个推演全过 + 四时间线状态机逐字段自洽[重复 restore 替换语义幂等实证/降级链内存最终一致/结构不完整零部分灌回事务性] + 数学完备性[唯一条件性不可满足即 R3-1] + TDD 红绿变异链全链可执行 + R2 修复零深化缺陷 + 存量行号锚 HEAD 全真实复核）。总计发现：P0×0 + P1×1 + P2×0 + P3×3。
>
> Round 4 审查投入：纯验证零发现（18 项修复关键词存续双落点 + 33/33 file:line 锚点向 HEAD 全精确 + 台账 18 行算术自洽 + 格式完整 + 周期闭合无游离提交）——按纪律零提交不强行造。
>
> Round 5 审查投入：独立终审五节取证全过（周期闭合 ✓ / 关键修复双向取证 10/10 ✓[全部以仓库现实复算非采信自报] / 特权快扫零新发现[计数算术专项 13 项抽查全过 + sprint-status L168 联动一致 + 5-9 边界交叉 8 处零矛盾] / 门禁三项全绿[提交链零 AI 署名/零抑制词/结构完好] / 收敛判定 ✓）。

### 🏁 五轮文档审查收敛声明（v1.3.1 终态）

- **周期间隔**：2026-10-29 单日闭环（v1.0.0 创建 → v1.1.0 → v1.2.0 → v1.3.0 → v1.3.1；edacf6f9 → 387acd33 + 收敛提交，每提交文件面仅本故事文件）
- **轮次投入**：R1 四视角调研 + 三视角审查（一致性传播/可行性可测试性/科学性业界对标）→ R2 回归核查 + 组合交互双审（R1 修复传播完备性零漏网实证）→ R3 单深度推演（14 场景三轴 + 四时间线逐字段 + 数学完备性）→ R4 纯验证零发现 → R5 独立终审五节取证
- **发现与修复分级统计**：总计 P0×0 + P1×7 + P2×约14 + P3×约25（约 46 项，全部清偿；另登记不改 1 项——OD-7/Task 3 绿行表格未转义 `\|`，纯文本消费无实害）
- **关键修复一句话版**：restore 恢复式机制定稿（灌回三 deque 替换式构造 + state_version 计数器续接——红③b/绿/变异三锚）｜452 静态 message 钦定「评估历史持久化失败」（str≡message 论证 + cause 链断言归 Task 2⑥）｜③b 满窗不可满足构造缺口补钦定（恢复历史长度 3 < MAX_HISTORY_SIZE）｜state_version「save 成功后 +1」时点钦定｜计数对账批修（9→7 件/六→五分数/13→16 行/2+5→2+7 修改）｜§3.3.2 两处更新四处传播｜redis marker 两侧补登（含混合文件知悉）｜风险 #9/#10 扩登（重启回退/演进兼容）
- **收敛判据核验**：零 P0/P1 残留 ✓｜R5 独立双向取证 10/10 通过（grep 口径 16 行/12 行/14 组、行号锚 30+ 处、子集断言形态、场景数 15/13/14、sprint-status L168 全部仓库实证零偏差）✓｜门禁三项全绿 ✓｜5-9 边界交叉零矛盾（「依赖 6.3」系 OD-2 显式偏离源）✓
- **Status**：保持 `ready-for-dev`（文档审查周期不改变 dev 就绪态——5-8 v1.3.1 先例同款）
- **转 dev 建议**：可即运行 `dev-story` 开始实施；dev 时按故事内既定纪律执行（存量断言尾部追加防线、同窗三件、grep 重定位行号锚）

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 2026-10-29（Round 1）
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor + 架构合规四视角并行——C1~C5 循环审查工作流）

#### 需决策 Decision Needed

- [ ] （无——全部发现经三视角评审仲裁定案，无需用户决策）

#### 已修复 Patch

- [x] **[P1] 跨 Agent 历史混串**（Recorder 全局单窗口 + session_id 按 agent 分键落盘错配——同进程多 Agent 共享 SINGLETON Recorder 时 B 键快照混入 A 的记录[实测复现]，双源确认；组合根 use case/agent_checkpoint 双 SINGLETON 下多 Agent 混流是常态路径非边界；5.9 检测器知悉登记先例不适用于本 Story——5.9 是进程级信号统计质量面[σ₀ 渐进膨胀]、5.10 是 per-agent 数据档案正确性面[B 键字面含 A 记录 + restore 前向永续污染]，且 DC-6 命名空间契约自身承诺 per-agent 档案）→ **F1 per-agent 键控窗口**：`_windows: dict[session_id → _AgentWindow]`（三 deque + 窗口级 state_version 计数器——连带修复全局计数器跨键顶号伴生缺陷）；窗口数无上界知悉（instantiate 非幂等——agent_cli 实证，~60KB/窗慢泄漏，V1 LRU/TTL 锚）；新增回归锁 2 用例（交错 record 隔离 + restore 不串窗）；OD-9 偏离登记 [src/application/services/evaluation_checkpoint_recorder.py]
- [x] **[P2] restore 收敛面泄漏 ValidationError**（`except (KeyError, ValueError, TypeError)` 捕不到 DTO 守卫的 ValidationError——继承 DomainError 体系非 ValueError 子类；腐坏快照分数越界/bool/等长破坏时 201 裸逃逸而非契约承诺的 452，实测复现）→ **F2** catch 元组补 ValidationError + reason 收敛 `invalid_structure`（四类结构异常单值收敛——cause 链携精确原异常；闭集同步 evaluation_exceptions.py 两处 + sisys-uni-exception-design.md L744）[src/application/services/evaluation_checkpoint_recorder.py:171]
- [x] **[P2] 集成测试泄漏未关闭 Redis 客户端**（`restarted, _, _ = await _make_real_stack()` 丢弃第三返回值 + 空 `finally: pass` 死脚手架——第二客户端连接池永不关闭，双源确认）→ **F3** 捕获 restarted_client + finally close [tests/integration/test_integration_checkpoint_evaluation.py:154]
- [x] **[P2] AC-2.1 五分数断言缺 overall_score**（验收/单测仅断 4/5 分数——feature 文本「五分数字段逐值相等」与实现不符）→ **F9** 验收补 overall 三维加权同式表达式（import HALLUCINATION_WEIGHT/CONTEXT_RELEVANCE_WEIGHT/CONFIDENCE_ACCURACY_WEIGHT 镜像——(1-0.2)*0.4+0.0*0.35+0.55*0.25，禁字面量禁 approx）+ 单测补 overall 透传锚；**评审纠错**：方案草案公式 (1-h)×0.5+cr×0.5 是 actual-quality 中间步非 overall 公式[回归风险评审 P1 级拦截]
- [x] **[P3] trend 元素零校验双标**（history 五分数有守卫、trend 全无——腐坏字符串元素静默灌回并随 record 永续前向传播；NaN 经 json allow_nan=True 穿越存储往返——科学性评审实证）→ **F4** 聚合 `__post_init__` 扩 trend 元素 [0,1] 数值域校验（bool 显式排除 + NaN 链式比较天然拦截；等长先验元素后验顺序钦定）+ 参数化 10 用例（两 trend × 越界/bool/字符串/NaN）[src/application/ports/agent_checkpoint.py]
- [x] **[P3] 主链 record 块 catch 面宽度**（record 抛 ValidationError 时穿透内层 catch + 外层三元组 catch 逃出 execute——当前三重上游守卫下不可达，但端口公共契约对直调消费方为假）→ **F6** record 内构造段 except ValidationError 收敛 452（phase=record/reason=invalid_input——451「理论不可达防御层」同款哲学第三次适用；端口「唯一异常」契约成立，主链 catch 零改动）+ 2 用例（predicted 越界 452 + 窗口零污染事务锚）[src/application/services/evaluation_checkpoint_recorder.py]
- [x] **[P3] AC-3.1 evaluation_history 未逐值断言**（集成/验收仅断 len + 首条 predicted——序列化字段值漂移可静默通过唯一验证两层 json 落键的断言面）→ **F9** 集成/验收补四分数 + predicted 逐值循环断言
- [x] **[P3] agent_id 空串守卫一段式断言**（DTO 单测 + 验收仅 raises，姊妹步骤是三段式）→ 补 code==201 + context 断言（两处）
- [x] **[P3] 前缀字面量双源漂移风险**（`"agent-evaluation-"` 在 record 构造单点使用但命名空间是跨消费方契约值）→ `EVALUATION_SESSION_PREFIX` 模块常量单源（端口文件导出——6.3/V1-EV12 消费方锚）[src/application/ports/agent_checkpoint.py]
- [x] **[P3] 自报数字失准**（Dev Agent Record「零抑制 45 用例」实测 42、「45 文件」实测 20[parametrize 实为 9 src + 11 tests]）→ 本表勘误：42 用例 / 20 文件
- [x] **[P3] 「全部尾部追加防线」口径失准**（4/7 文件存在签名基线断言块内消息/注释行必要同步改写——验收审计与架构合规双源核实：改写仅限断言消息「七依赖→八依赖」与常量注释行，无功能性改写；5.9 回执锁死字面行原样保留零触碰）→ File List 口径修正为「尾部追加为主 + 签名基线断言块内消息/注释行必要同步改写」
- [x] **[P3] `_PERF_CACHE` 形态自报失实**（故事三处自报「双 key["save_p95"/"query_p95"]」——实际单 key `checkpoint_perf` 载双指标 summary dict，功能等价）→ AC-5 Given/Subtask 4.2 口径修正为实际形态

#### 已推迟 Defer

- [x] [Review][Defer] 验收文件 AsyncMock（LLM SaaS/沙箱豁免面）——5.8/5.9 先例逐字延续，核心被测面（Recorder + RedisSnapshotStore + 真实 Redis）全真实服务 [tests/acceptance/test_acceptance_checkpoint_evaluation.py:347] — 族系既定模式，非本 Story 引入
- [x] [Review][Defer] restore 返 None 双义契约绑定 RedisSnapshotStore catch-all 实现细节（SnapshotRepositoryProtocol 协议面无此保证——实现切换为上抛形态时需复核）——MVP 唯一实现下无实害，V1 多实现时随 6.3 评估
- [x] [Review][Defer] 多 worker 部署窗口分叉 + Redis latest 最后写者胜（跨进程键控/粘性路由 V1 面——与 5.9 V1-EV14 检测器键控同族）——风险 #9 保留登记

> **Round 1 审查投入**：C1 四视角并行调研（盲审对抗/边缘用例猎手/验收审计/架构合规——全绿基线 13569 passed 锚定）+ C2 方案 F1~F9 + C3 三视角评审（科学正确性【需改→6 必改采纳】/回归风险【可落码+3 前置——F9 公式 P1 级纠错】/最小性规范【5 必改——F5 降级 docstring、F7 维持不修仲裁】）+ 红测试 18 用例先行（8+10 红实证缺陷）+ 绿实现 219 passed + 文档联动（Recorder/端口/组合根/异常设计/领域设计五处）。
>
> 发现分级：**P0×0 + P1×1 + P2×3 + P3×10**（另登记不改 3 项见 Defer）；四视角正向确认：架构八项硬约束全合规、AC 46 项逐条核对 39 ✓、File List 30 文件零偏差、ruff/mypy 全绿。

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

### 📋 变更日志 Change Log [dev-story 必填]

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0.0 | 2026-10-29 | 创建故事文件（create-story——多 Agent 四视角调研 + OD×8 偏离声明 + 留项处置五条 + 存量断言 ×7 实证） |
| v1.1.0 | 2026-10-29 | 文档审查 Round 1（四调研+三审查——P0×0/P1×5/P2×12/P3×15）：restore 恢复式语义机制定稿（灌回三 deque + state_version 计数器——Task 2 红绿变异三锚落地）+ 计数对账批修（9→7/六→五/13→16 行/2+5→2+7）+ §3.3.2 两处传播 + redis marker 补 + OD-8④ 通道分述修正 + 风险表扩 #9/#10 + 杂项澄清批（Docs Review Fixes R1-1~R1-12） |
| v1.2.0 | 2026-10-29 | 文档审查 Round 2（回归核查+组合交互双审——P0×0/P1×1/P2×2/P3×7，R1 修复传播完备性零漏网实证）：WARNING 断言锚修正（452 静态 message 钦定 + cause 链断言归 Task 2⑥——R1-11 注入深度变化后断言形式重推导）+ 风险 #9 扩重启回退形态（未 restore 直接 record 双回退知悉）+ AutoExecuteService 机制差异注记（load-derived vs 内存计数器）+ Task 3 红处方 StorageError 限定 + warmup 复合构成钦定 + P3 批清偿（Docs Review Fixes R2-1~R2-4） |
| v1.3.0 | 2026-10-29 | 文档审查 Round 3（单深度推演——P0×0/P1×1/P2×0/P3×3）：③b 满窗恢复构造约束补钦定（恢复历史长度 3 < MAX_HISTORY_SIZE——满窗下「长度+1/首条不变」数学不可满足，R1-1 引入断言的构造缺口）+ state_version +1 时点钦定（save 成功后——失败不消耗版本号）+ AC-2.1 断言措辞分述（五分数字段+agent_id+recorded_at）+ Given 补 drift_detector 注入显式化；14 场景三轴全过 + 四时间线逐字段自洽 + R2 零深化缺陷（Docs Review Fixes R3-1~R3-2） |
| v1.3.1 | 2026-10-29 | 文档审查收敛：R4 纯验证零发现（33/33 锚点全精确）+ R5 独立终审五节全过（双向取证 10/10 + 特权快扫零新发现 + 门禁全绿）——五轮收敛声明入档（总计 P0×0 + P1×7 + P2×约14 + P3×约25 全清偿），Status 保持 ready-for-dev |
| v2.0.0 | 2026-10-29 | **dev-story 实施完成**（Task 0-6 全闭环，Status → review）：四视角并行调研 → Task 0（Gherkin 14 场景 + BDD 骨架红验证 14/14 + deferred-work 五条注记）→ Task 1（452 注册四件套 + agent_checkpoint.py 端口/DTO——变异 ×3）→ Task 2（EvaluationCheckpointRecorder 七场景 + 组合根 SINGLETON 注册 + 契约 11 维度——变异 ×5）→ Task 3（主链第八依赖 + record 块[三键后漂移前 + 452 内层独立降级] + 工厂同窗三件 + 存量断言同步 ×7 尾部追加 + 全家回归——变异 ×2）→ Task 4（真实 Redis 六场景 + P95 双锚[save ~1ms<100ms/query ~1ms<50ms 满窗锚] + 正向锚 21 + xdist 组互异——常量变异锚）→ Task 5（AST 验证器 A/B/C + 零抑制 ×45 文件）→ Task 6（验收 14 场景全绿 + 全量 13568 passed + 整体覆盖率 93% + 新文件 100% + mypy 1806 files 零错 + ruff 全清 + 三条 grep 自查零输出 + 单元面 5 轮连续绿 + 文档同步：§3.3.2 两处/§17.3.8 注记/sprint-status 流转） |
| v2.1.0 | 2026-10-29 | **代码审查 Round 1**（C1~C5 循环——四视角调研 + 三视角评审 + 红绿落码）：**P1×1 + P2×3 + P3×10 清偿**——OD-9 per-agent 键控窗口（跨 Agent 混串结构性修复 + 窗口级版本计数器）+ restore 收敛面补 ValidationError（reason 收敛 invalid_structure + 闭集三处同步）+ record 输入域违规收敛 452（invalid_input——端口唯一异常契约）+ trend 元素 [0,1] 域守卫（NaN 穿越防线）+ EVALUATION_SESSION_PREFIX 常量单源 + 集成泄漏 client 修复 + AC-2.1 overall 同式断言/AC-3.1 逐值/agent_id 三段式断言补强 + 自报数字/尾追口径/_PERF_CACHE 形态勘误；红测试 18 用例先行（8+10 红实证）→ 绿 219 passed；评审仲裁：F5 降级 docstring（450 空串先例）/F7 维持不加守卫（Simplicity First）/F9 公式纠错（0.5/0.5 中间步→0.4/0.35/0.25 三维加权——回归风险评审 P1 级拦截）；文档联动五处（Recorder/端口/组合根/uni-exception L744/core-domain §17.3.8） |

---

**故事版本/Story Version:** v2.1.0
**创建日期/Created:** 2026-10-29
**最后更新/Last Updated:** 2026-10-29
**更新说明/Description:**
- v1.0.0: 创建故事文件——Ultimate context engine analysis completed（comprehensive developer guide created）
- v1.1.0: 文档审查 Round 1——D1 四视角调研 + D2 三视角审查（P0×0 + P1×5 + P2×12 + P3×15，修复见 Docs Review Fixes 表 R1-1~R1-12；零设计变更）
- v1.2.0: 文档审查 Round 2——回归核查 + 组合交互双审（P0×0 + P1×1 + P2×2 + P3×7，修复见 R2-1~R2-4；R1 修复传播完备性零漏网实证）
- v1.3.0: 文档审查 Round 3——单深度推演（P0×0 + P1×1 + P2×0 + P3×3，修复见 R3-1~R3-2；③b 满窗不可满足构造缺口清偿——清偿后可进 dev）
- v1.3.1: 文档审查收敛——R4 纯验证零发现 + R5 独立终审五节全过，五轮收敛声明入档（零 P0/P1 残留），Status 保持 ready-for-dev
- v2.1.0: 代码审查 Round 1——四视角调研 + 三视角评审 + 红绿落码（P1×1 + P2×3 + P3×10 清偿，修复见 Review Findings；OD-9 per-agent 键控窗口登记；Status 保持 review）
