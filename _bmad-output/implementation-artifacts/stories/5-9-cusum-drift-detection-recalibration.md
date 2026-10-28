# Story 5.9: CUSUM 漂移检测与触发重校准

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 可观测性工程师,
**I want** 实现 CUSUM 漂移检测与触发重校准机制（CUSUMDriftDetector 双侧累积和 + N中M 确认 + DriftDetected 事件 + 主链接入）,
**So that** 自动检测模型性能漂移并触发重校准，保证输出质量稳定。

### 业务价值

Epic 5「单 Agent 战略规划能力」价值组可观测性族第三 Story：5.7 交付追踪基础设施（span 通道 + eval.*/drift.* 键常量注册），5.8 交付评估面（`EvaluationHarness.evaluate` 三维质量画像 + `overall_score` 连续序列——**特意将 binary 宽化为连续量，本 Story 累积和消费的前提**）。本 Story 交付**漂移检测面**——`CUSUMDriftDetector.update(overall_score)` 双侧累积和计算（附录 I 钦定公式）→ 预热基线（30 样本动态估计 μ₀/σ₀）→ N中M 确认（3 中 5——单点异常误报抑制）→ 确认漂移时 span 写 `drift.detected=True`（**OD-2[5.7] 兑现——5.7 键常量注册以来唯一空白的生产填值面**）+ `trigger_recalibration()` 发布 `DriftDetected` 领域事件（reliable 通道 RabbitMQ + Outbox——「提示人工介入」通道）。这是 FR-EV-03 的闭环 Story，也是 ADR-012 在 Agent 输出质量维度的落地：5.10（评估历史入 Checkpoint）以本 Story 的检测器序列语义为邻接面。

**范围权威**：epics_v1.0.md L1812-1855（AC + 实现内容 + 测试要求 + 性能锚 L1838 检测延迟 P99<100ms / L1839 漂移检测准确率≥85%[V2 指标回测口径]）、L203/L531（FR-EV-03 P1）、L1445（依赖 Story 5.8，P1-9）；arch-appendix.md 附录 I（§29.1 双侧 CUSUM 公式 / §29.3.1.1 k=0.5σ h=5σ / §29.3.2.1 漂移分级 / §29.3.2.2 N中M 确认 / §29.3.3.2 质量指标阈值表 / §29.7.1 参考实现）；sisys-core-domain-design.md §17.3.8（L1667-1671 update→is_drifted→drift.detected→trigger_recalibration 四步伪码 + L1637-1638「CUSUMDriftDetector/is_drifted/trigger_recalibration 归 5.9」）；architecture.md L2594（实现位置钦定 `src/infrastructure/monitoring/cusum_detector.py`）+ L3658-3662（ADR-012）+ §14.4 L2661（CUSUM 漂移检测归 5.9——消费 overall_score 连续序列）。

### 范围边界（与后续 Story 的精确切分）

| 能力 | 本 Story（5.9） | 后续 Story |
|------|----------------|-----------|
| `DriftDetectionPort`（update + trigger_recalibration）+ `DriftAssessment` DTO（application/ports/agent_drift.py） | ✅ 新建 + 契约测试 | — |
| `CUSUMDriftDetector`（src/infrastructure/monitoring/cusum_detector.py——architecture.md L2594 钦定位置）：双侧累积和 + 预热基线 + N中M 确认 + 分级 + 确认后复位 | ✅ 纯标准库实现 | — |
| `DriftDetected` 领域事件（domain/events/drift_events.py）+ event_channels.yaml + ChannelRouter.DEFAULT_MAPPINGS 双登记 | ✅ reliable 单通道 | — |
| `DriftDetectionError`（EXCEPTION_451——evaluation 子域 451-459 预留段首个取用） | ✅ evaluation_exceptions.py 追加 + 注册四件套 | — |
| 主链接入（use case 第七可选依赖 + 评估块内漂移检测块 + drift.detected span 填值 + 降级网扩 451） | ✅ 纯附加（None 默认向后兼容） | — |
| 检测延迟 P99<100ms（纯内存检测管线口径——DC-8）+ 合成序列回测准确率≥85% | ✅ 集成 + 验收 AC-5 | — |
| 评估历史 eval_history / hallucination_trend / 趋势追踪 / CheckpointWithEvaluation | ❌ 不做（epics 5.10） | 5.10（依赖 6.3） |
| 多指标并行检测（附录 I Dict[metric_name] 三键逐指标归因通道） | ❌ 不做（OD-4——MVP 唯一序列源是 overall_score；5.8 移交注记「逐指标归因更优」是 V1 通道） | V1 按需（deferred-work 登记） |
| 基线定期更新（24h）/ 滑动基线 / 季节性调整（附录 I §29.6）/ 分时段 144 基线 | ❌ 不做（OD-3——MVP 冻结基线） | V1 按需（deferred-work 登记） |
| trigger_recalibration 的「更新模型配置」自动重校准（UDMR 配置变更面） | ❌ 不做（OD-6——需独立配置变更能力面） | V1 按需（deferred-work 登记） |
| 告警分级 P0-P3 通知渠道（电话/短信/IM）/ AlertCenter / 变更窗口豁免 / 告警疲劳抑制（附录 I §29.5.2/§29.6.3） | ❌ 不做（告警中心是 Epic 11 面；本 Story 事件即告警载体） | Epic 11 / V1 |
| Prometheus 指标导出（cusum_drift_detected_total 等 §29.7.3）+ Grafana 仪表盘 | ❌ 不做（span + 事件双通道是本 Story 交付面） | V1 按需（监控域扩展） |
| 性能指标 CUSUM（FR-CP-10——latency_p95/error_rate 等 Prometheus 指标漂移） | ❌ 不做（NFR-REL-05 P1 V1——指标采集体系是前提，归 Epic 11 Story 11.6） | Epic 11 Story 11.6 |
| 漂移检测 REST API / CLI 命令 | ❌ 不做（嵌入式可观测基础设施——5.7/5.8 同款定位） | 无规划（消费方出现时立项） |
| 真实历史数据回测（V2 指标本义） | ❌ 不做（MVP 无生产历史序列——合成序列回测替代承载 OD-7 注记） | V2（数据积累后） |

### 偏离声明（Deviation Declarations）

| # | 偏离 | 规划原文 | 偏离理由与归宿 |
|---|------|---------|---------------|
| OD-1 | 测试文件命名从仓内惯例不从 epics 占位名：`tests/unit/infrastructure/monitoring/test_cusum_drift_detector.py`（epics 占位 `tests/unit/architecture/test_cusum_detector.py`）+ `tests/unit/architecture/test_arch_drift_detection.py`（AST 架构验证器——per-story 惯例）+ `tests/integration/test_integration_drift_detection.py`（epics 占位 `test_drift_detection_integration.py`） | epics_v1.0.md L1851-1852（测试文件占位名） | 5-8 OD-1 / 5-7 OD-3 同款注记：epics 占位名是规划文本，仓内惯例（unit 按层归目录 / test_arch_* 前缀 / test_integration_* 前缀 / test_acceptance_drift_detection 命名族）是活代码事实源；规划占位名与仓内惯例的正常偏差，随本 OD 知悉不进台账 |
| OD-2 | numpy/scipy 不引入——纯标准库 `statistics`（mean/stdev）实现基线统计；附录 I §29.7.1 参考实现的 `import numpy as np` + `from scipy import stats`（L4256-4257）不照抄 | arch-appendix.md §29.7.1 L4256-4257（示例 import）+ §29.2.2.1 BaselineStatistics（np.mean/np.std/percentile + scipy.stats.norm.ppf 置信区间） | ①5.7 OD-1 确立「零新运行时依赖」家族原则、5.8 延续（agent_evaluation.py L18「纯标准库零第三方」）——numpy/scipy 在 pyproject 主依赖零声明（仅 poetry.lock 传递存在——sentence-transformers 生态引入，非显式依赖不可依赖[传递依赖随时被上游解析变更移除]）；②CUSUM 是 O(1) 增量更新 + 基线仅需 mean/std[ddof=1]——`statistics.mean`/`statistics.stdev`（样本标准差）完整达成，无向量化需求；③scipy.stats 仅置信区间用——MVP 基线砍 CI/median/p95/p99 字段（YAGNI——CUSUM 只消费 μ₀/σ₀，附录 I BaselineResult 七字段收窄为两字段）；④零新依赖 = 零架构白名单变更 |
| OD-3 | 基线建立流程 MVP 裁定：进程内**预热窗口 30 样本冻结基线**（前 30 个 overall_score 样本经 statistics.mean/stdev 估计 μ₀/σ₀，检测期不更新；样本不足 30 时不判定 is_drifted 恒 False）——附录 I 的 14 天采集期（≥1000 样本）/验证基线（≥500）/min_samples=100 不采用 | arch-appendix.md §29.2.1.1（采集期时长表：初始基线 14 天 ≥1000 样本）+ §29.7.1 BaselineConfig（min_samples=100）+ ADR-012「滑动窗口 7 天」（architecture.md L3662） | ①MVP 无生产历史数据（评估面 5.8 刚交付——历史序列零积累），14 天采集期在本 Story 验收窗口内不可满足——死规范；②30 样本锚定附录 I 自身 §29.2.3.2 正态性检验的最小样本量下限（`len(data) < 30 → ValidationReport(valid=False)`）；③per-run 评估频率（每 execute 一样本）下 30 样本 ≈ MVP 阶段单 Agent 可达运行量级；④冻结基线（检测期不滚动）语义正确性：漂移检测的前提是基线不随漂移漂移——滑动基线 V1（deferred-work 登记）；⑤ADR-012「滑动窗口 7 天」时间窗语义 → 样本计数窗（30 样本）形态承载：进程内无时间戳序列持久化（重启归零——MVP 可接受知悉，V1 Redis 持久化随 5.10/监控域评估），时间窗与样本窗在 per-run 频率下等价换算注记 |
| OD-4 | 多指标并行检测收窄为单指标 `overall_score`（检测器构造绑定 METRIC_NAME="overall_score"，update(score) 单参数——附录 I `detect(metric_name, value)` 双参数多指标 API 不采用） | arch-appendix.md §29.7.1 L4355（detect(metric_name, value) 签名）+ §29.4 监控指标体系（性能/质量/成本 30+ 指标） | ①MVP 唯一连续序列源是评估块内存返回的 `evaluation_result.overall_score`（伪码 L1668 钦定 update(eval_result.overall_score)）——span 三键逐指标序列需 Phoenix 查询回读通道（R1-DF4[5.7]：OTLP 真实通路零行为覆盖），MVP 不可达；②5.8 风险 #6 移交注记明示「CUSUM 以 overall_score 为总览/告警级序列，三键序列逐指标归因更优」——逐指标归因是 V1 通道（本 Story Task 0.7 deferred-work 登记 V1-EV9）；③单指标收窄使状态管理从 Dict[metric] 退化为标量字段——复杂度减半；④§29.4 指标体系是 FR-CP-10 性能面（Epic 11 Story 11.6）的完整愿景，非本 Story 范围 |
| OD-5 | 漂移确认后**立即复位**统计量（Sₕ/Sₗ 归零 + 确认窗清空——基线保持）+ severity 确认后仅 moderate/severe 两档 + 参考实现 `raise ValueError` 改领域异常体系 | arch-appendix.md §29.7.1（参考实现确认后无 reset——持续漂移下后续每样本均再确认 → 告警风暴；_determine_severity 四档 none/minor/moderate/severe；update_baseline L4342 `raise ValueError`） | ①参考实现确认触发后 CUSUM 统计量不清零：持续漂移（如模型降级未处理）下 S 持续 >h，每个后续样本都满足 N中M → 每 run 发一次 DriftDetected 事件——告警风暴（附录 I §29.6.3.4 告警疲劳抑制的存在本身即此问题的佐证）；裁定确认即复位：重复告警间隔 = 重新累积到确认的样本数，与漂移幅度反比（R1 实测修正——原「≈2-5 样本」低估：δ=0.4[下漂锚]≈5 样本、δ=0.2[≈3.4σ]≈6、δ=0.16[≈2.7σ]≈7，间隔 ≈⌈h/(δ−k)⌉+确认窗填充）——节奏受控且漂移持续时周期性再告警（语义正确：持续漂移应持续可见）；②severity 判定阈 S>h=5σ 已排除 minor 观察档（3σ<S≤5σ 按 §29.3.1.2 是「记录日志，不告警」——不进确认历史）→ **R1 论证修正：确认条件含「当前样本 detection=True」（AC-1 Then②——N中M 确认要求当前样本在告警态[ISA-18.2 M-of-N 告警宣告语义]），该前提下确认时 max(Sₕ,Sₗ)>h=5σ₀（ratio 用的与 detection 判定是同一个含本样本增量的 S）→ ratio 必 >5，仅 moderate（5σ<S≤8σ）/severe（S>8σ）可达——四档完整语义保留于 docstring 注记（原论证在纯 N中M 无当前样本条件下不成立：确认可落在非 detection 样本、ratio 可 ≤5[实证反例 ratio=4.40]——正是当前样本条件的必要性所在）；③`raise ValueError` 违反项目异常红线（sisys-uni-exception-design——禁止 raise ValueError）→ 输入域校验走 `ValidationError`（201）/ 管线失败走 `DriftDetectionError`（451）；④「基线重建 API」不暴露（人工介入闭环前重校准后新分布 vs 旧基线会立即再触发——语义上正确：配置变更后系统确实在漂移，人工介入流程 V1 闭环时配套） |
| OD-6 | `trigger_recalibration()` 的「更新模型配置」MVP 不做——裁定「提示人工介入」单通道：发布 `DriftDetected` 事件（reliable 通道，`recommended_action="manual_review"`）+ logger.warning | epics_v1.0.md L1821（「trigger_recalibration() 更新模型配置或提示人工介入」——「或」语义下 MVP 取后者）+ arch-appendix.md §29.5.3（根因分析与响应执行——自动降级/配置变更） | ①「更新模型配置」需要 UDMR 配置变更面（cloud_configs 运行时变更 + 热生效）——独立能力面（当前 UDMRConfig.from_env 是 bootstrap 定格，无运行时变更通道）；②自动重校准的风险面：误报驱动的自动模型切换比人工确认更危险（附录 I §29.5.1 多级确认流程的「深度分析→根因定位」前置——MVP 无归因数据）；③reliable 事件（RabbitMQ + Outbox）是不丢的人工介入通知通道——比同步变更更符合 MVP 可控性；④自动重校准 V1（deferred-work 登记——依赖：漂移归因[链接 V1-EV4 golden set] + UDMR 运行时配置面） |
| OD-7 | 接口形态：伪码/epics 的 `update(x)` + `is_drifted()` 两方法 → 端口单方法 `update(score) -> DriftAssessment`（is_drifted 判定语义由返回值字段承载）+ 独立方法 `trigger_recalibration(assessment)` | sisys-core-domain-design.md §17.3.8 L1668-1671（update + is_drifted() 两步伪码）+ epics_v1.0.md L1820/L1826（is_drifted() 接口锚） | ①原子性——累积+判定+N中M 确认一次调用完成，两方法形态在并发/异常路径下存在中间态（update 成功 is_drifted 未调）语义模糊；②`DriftAssessment` 携带完整上下文（is_drifted/direction/level/cusum_high/cusum_low/baseline_mean/baseline_std/sample_count/baseline_ready）——事件构造、span 判定、测试断言的统一数据源；is_drifted() 独立 bool 方法丢失全部上下文；③N中M 确认状态机内化（确认窗不暴露为端口调用面）；④epics AC「is_drifted() 检测到漂移」验收语义由 `assessment.is_drifted is True` 字段断言承载（AC-1/AC-3 Gherkin 措辞对齐）；⑤类名 `CUSUMDriftDetector` 保持（AC/伪码/附录 I 三重锚——零偏离）；「漂移检测准确率≥85%（V2 指标，回测历史数据验证）」MVP 以**合成序列回测**承载（无生产历史数据——确定性种子生成稳定/漂移序列各半，TP/TN 统计准确率断言；真实历史回测 V2 数据积累后） |

> 优先级锚说明（非偏离）：epics L531 将 FR-EV-03 定级 P1（功能等级），epics L1445 执行优先级 P1-9（执行序——依赖 5.8 完成后执行）。双锚不矛盾（5.8 同款注记）。

---

## 🔗 前置依赖（全部 ✅ 无阻塞——5.8/5.7/5.3 为 done 交付 Story；「就绪」= 既有资产本 Story 直接消费无需先行动作）

| 依赖 | 组件 | 用途 | 状态 |
|------|------|------|------|
| Story 5.8 | `EvaluationResult.overall_score`（src/application/ports/agent_evaluation.py L118——[0,1] 单调正向质量分，L102-104 docstring「5.9 CUSUM 消费本键做漂移累积——方向一致性前提」）+ 评估块接入点（src/application/use_cases/run_agent_workflow.py L201-210（R1 行号修正——L192-200 为注释块）——`if self._evaluation_harness is not None:` → evaluate → is_recording 三键写入 → `except (AgentEvaluationError, LLMConfigError)` 降级；**漂移检测块的内嵌宿主**）+ 评估块单测先例（tests/unit/application/use_cases/test_run_agent_workflow.py TestExecuteEvaluationBlock——类级 function-scope autouse initialize 通道形态）+ 组合根 5.8 注册区段形态（composition_root.py L2989-3034 双注册 + `_build_agent_workflow_use_case` def 工厂 L3075-3111——第七依赖扩展宿主） | 漂移检测的序列数据源 + 接入宿主 + 注册形态模板 | ✅ done（v2.3.1） |
| Story 5.7 | `SpanAttributeKeys.DRIFT_DETECTED = "drift.detected"`（src/application/ports/agent_tracing.py L128——**已预注册零改动，本 Story 生产填值**）+ `SpanAttributeValue` 类型窄化契约（L21-25——bool 合法值）+ 根 span 写入块先例（run_agent_workflow.py L180-191（十属性）`get_current_span()` + `is_recording()` 守卫）+ OTel 测试通道分派 SSOT（链级 initialize 全局通道 + reset_for_testing 双复位义务）+ AST 架构验证器形态（test_arch_phoenix_tracer.py——本 Story 验证器 A/B/C 照抄结构） | span 键契约 + 写入通道 + 测试形态 | ✅ done（v2.2.1） |
| Story 5.3 | `RunAgentWorkflowUseCase` 六依赖构造器（L67-94——**第七可选依赖追加宿主**）+ `AgentWorkflowResult` 五字段 DTO + Fake LLM 手工装配链先例（test_acceptance_agent_workflow.py L185-284（R1 行号修正）——Schema 身份分派，AC-3 链级场景复用） | 主链宿主 + 测试装配 | ✅ done |
| 事件总线资产（Epic 1） | `EventPublisher` 协议（src/domain/ports/event_publisher.py L15-36——`async def publish(event) -> PublishResult`）+ `DualChannelEventBus`（infrastructure/messaging/dual_channel_event_bus.py L20-65——router 分派 reliable→Outbox）+ Outbox 链路（rabbitmq_event_bus.py L39-63 落 Outbox → outbox_processor.py 轮询投递）+ **`ChannelRouter.DEFAULT_MAPPINGS`**（infrastructure/messaging/channel_router.py L54-399——新事件双登记第二处）+ `configs/event_channels.yaml`（313 行——新事件双登记第一处；头注 L1-7「新增事件应同时更新两处」）+ 发布失败不阻塞先例（agent_profile_loading.py L151-169——publish 失败 logger.error 继续）+ 事件契约测试两族先例（tests/contracts/test_event_contract_tool_version_events.py + test_event_channel_mapping_tool_version.py——双登记逐字段一致门禁形态） | DriftDetected 事件发布链 | ✅ 就绪 |
| 领域事件基建 | `DomainEvent` 基类（domain/events/base.py L46-74——event_id/event_type/timestamp/aggregate_id/aggregate_type/version/correlation_id/causation_id；`__init_subclass__` 自动注册多态表 L79-90）+ 数值告警事件最近先例 `StrategicDeviationWarning`（domain/events/planning_events.py L15-42——数值+阈值+级别字段形态）+ `AgentProfileLoaded` kw_only 模式（agent_events.py L70-100——必填字段 `field(kw_only=True)` + event_type init=False + __post_init__ 设 aggregate）+ 事件单测落位（tests/unit/domain/events/——test_agent_events.py 等同族） | DriftDetected 事件模板 | ✅ 就绪 |
| 异常体系 | evaluation 子域 450-459 预留段（_code_ranges.py L133-141——**L137-138 注释钦定「451-459 预留给 5.9 漂移检测/5.10 评估历史」**；450 已占 AgentEvaluationError）+ `SystemException` 基类 + AgentEvaluationError 风格模板（evaluation_exceptions.py L21-80——构造 agent_id/phase/reason/message/cause/context_extra + context dict）+ `ValidationError`（201——应用层输入校验，DriftAssessment/入参域守卫）+ `EXCEPTION_HTTP_MAP`（interfaces/api/exception_handlers.py L141-287（R1 行号修正））+ CI 校验（test_code_ranges.py Rule 1-4 + test_error_code_uniqueness.py 自动反射） | DriftDetectionError 451 落位 | ✅ 就绪 |
| 数值先例 | `_compute_overall` 纯 Python 算术（evaluation_harness.py L276-306——5.8 零 numpy 佐证）+ 浮点断言纪律（test_evaluation_harness.py L433-446——同式表达式禁十进制字面量 R3-F1 锚）+ `statistics` 标准库（集成计时 quantiles 先例 test_integration_agent_evaluation.py L645-676） | 纯标准库算法 + 断言纪律 | ✅ 就绪 |
| 测试基建 | tests/acceptance/conftest.py（文件名服务 marker 自动挂载——drift_detection 文件名零服务关键词，仅自动挂 acceptance marker）+ 模块级 event_loop fixture + `_run_async` 同循环调度 + 延迟 import 纪律 + 收尾清单场景形态（5.8）+ 委托计时三件（`_PERF_CACHE` 单槽缓存 + xdist_group 同组串行 + 常量单源集成定义/验收 import）+ AST 验证器 helper（test_arch_evaluation.py L64-87 _scan_file_top_imports/_scan_instantiation_sites） | 验收/集成/架构测试骨架 | ✅ 就绪 |

**移交给本 Story 的留项（必须处置——来自 5.8/5.7 deferred-work 与故事注记）：**

| # | 留项 | 来源 | 本 Story 处置 |
|---|------|------|--------------|
| 1 | **OD-2[5.7]** drift.detected 属性生产填值——归宿 5.9 | deferred-work.md L241 + 5-8 故事 L79 | **本 Story 兑现闭环**：漂移块确认漂移时经 `SpanAttributeKeys.DRIFT_DETECTED` 常量写 True（AC-3.1）；Task 0.7 在 deferred-work OD-2[5.7] 条目追加 5.9 兑现注记（drift.* 核销——**条目整体闭环**，eval.* 部分 5.8 已核销） |
| 2 | **R1-DF3[5.7]** agent_tracing 端口降级态「注册态 + impl 永抛」缝隙——锚位顺延至「首个 resolve 消费方（预计 5.9 CUSUM 或独立消费 Story）」 | deferred-work.md L250 + 5-8 故事 L80 | **Task 0 裁定：本 Story 消费面不触发缝隙**——5.9 的 span 写入与 5.8 同通道（`get_current_span()` OTel 全局 API + is_recording 守卫），不 resolve agent_tracing 端口；缝隙本体保持登记，锚位继续顺延（下一候选：首个真实 resolve 消费方立项时定夺 fallback_on 扩 ConfigurationError 或降级注册 NoOp 替身）；Task 0.7 追加处置注记 |
| 3 | **CR1-DF2[5.8]** 组合根级评估接线降级测试缺口——「可随 5.9 立项的接线测试一并」 | deferred-work.md L273 + 5.8 Round 1 审查 | **本 Story 采纳一并**：AC-4.1 接线测试场景扩展覆盖 `_build_agent_workflow_use_case` 工厂的降级防护面（drift 接线 resolve_optional 失败 → `_drift_detector` None 不阻断 use case 构造——与评估接线降级同窗断言）；Task 0.7 追加核销注记 |
| 4 | **5.8 风险 #6 移交注记四条**（CUSUM 消费须知）：①三键逐指标归因更优（V1 通道）②序列缺口策略（评估降级 run 不进序列——CUSUM 连续性假设敏感）③judge 温度 0.1 非确定——阈值需预热窗口估 σ ④overall 可达域压缩（两病态角分数带重叠 [0.525,0.60]——阈值勿按 [0,1] 全域假设；恒等式 overall ≡ 0.25·ca + 0.8·a − 0.05·cr）+ 六档锚定多峰（h 序列聚集 6 锚点值——σ 估计呈多峰、累积和呈阶梯） | 5-8 故事风险表 #6 | **Task 0 逐条处置**：①OD-4 已裁定（overall 总览 + V1-EV9 登记）；②缺口策略裁定 = 跳过（评估降级 run 漂移块不执行——序列缺口不计入累积；缺口计数器 V1 登记）；③预热窗口 30 样本 σ 估计即本 Story DC-7 承载；④**阈值相对化天然适配**——k/h 均为 σ₀ 倍数（0.5σ/5σ），与 overall 绝对域无关（可达域压缩只影响 σ₀ 估计值不影响检测机制）——docstring 注记 + 多峰知悉（σ 估计如实反映样本离散度，阶梯累积是量化序列的正常形态）落检测器 docstring |

---

## 🔗 现有代码继承（必须复用，禁止重复定义）

> ⚠️ **防重复造轮子清单**——以下组件已存在，dev agent 只可「直接复用 / 参考照抄」，禁止新建同义组件。

| 组件 | 文件路径 | 复用方式 |
|------|---------|---------|
| drift.detected span 键常量 | `src/application/ports/agent_tracing.py` L128（SpanAttributeKeys.DRIFT_DETECTED） | **直接复用——禁新建同义键常量**（键字符串单一真源——5.7 契约；本 Story 是其唯一生产写入方） |
| 根 span 写入块模式 | `src/application/use_cases/run_agent_workflow.py` L180-185（get_current_span + is_recording 守卫 + set_attribute） | **参考照抄**——漂移块 DRIFT_DETECTED 写入与 eval 三键同通道同形态（span 在 execute 返回时 end——写入必须在方法体内） |
| 评估块宿主与降级网 | `run_agent_workflow.py` L201-210（R1 行号修正） | **原地扩展**——漂移块内嵌评估块 try 内（evaluate 成功后）；catch 元组扩 DriftDetectionError（CR1-F1[5.8] 同款论证：三层降级网 评估失败/评估配置失败/漂移检测失败） |
| `EvaluationResult` + EVALUATION_WEIGHTS | `src/application/ports/agent_evaluation.py` L84-138 | **直接消费**——漂移块取 `evaluation_result.overall_score`（不重算不缓存；frozen 实例直传） |
| 端口文件风格模板 | `src/application/ports/agent_tracing.py`（149 行——模块 docstring Story 注记 + 类型别名 + Protocol + 常量注册表 + __all__，纯标准库） | **参考照抄**——agent_drift.py 同款形态（Protocol + DriftAssessment dataclass + 常量） |
| `StrategicDeviationWarning` 事件模板 | `src/domain/events/planning_events.py` L15-42（数值+阈值+级别 + warning_id default_factory + __post_init__ aggregate） | **结构参照**——DriftDetected 事件字段组织照此形态（数值告警事件最近先例） |
| `AgentProfileLoaded` kw_only 模式 | `src/domain/events/agent_events.py` L70-100（必填字段 field(kw_only=True) + event_type init=False 自动注册 + aggregate 设置） | **纪律照抄**——DomainEvent 基类字段全带默认值，子类无默认值非 kw_only 字段会 TypeError（先例注释原文） |
| 事件发布失败不阻塞先例 | `src/application/use_cases/agent_profile_loading.py` L151-169（try publish → publish_result.is_success 检查 → except Exception logger.error 继续） | **纪律照抄**——trigger_recalibration 内事件发布失败 logger.error 不上抛（漂移检测是可观测附加面） |
| 事件契约测试两族 | `tests/contracts/test_event_contract_tool_version_events.py`（注册/aggregate_type/to_dict 契约）+ `test_event_channel_mapping_tool_version.py`（yaml vs DEFAULT_MAPPINGS 逐字段一致） | **参考照抄**——DriftDetected 双契约测试（reliable 通道版：rabbitmq_routing_key 断言替换 redis_channel 断言） |
| 端口契约测试 11 维度 | `tests/contracts/test_port_contract_agent_evaluation.py`（PORT_NAME/EXPECTED_TAGS/REQUIRED_METHODS 类常量 + 11 维度 + _DummyResolver） | **参考照抄**——test_port_contract_agent_drift.py 同款（REQUIRED_METHODS=["update", "trigger_recalibration"]；Dummy 分发 event_publisher） |
| 组合根 def 工厂函数 | `src/composition_root.py` L3075-3111（`_build_agent_workflow_use_case`——resolve_optional + ConfigurationError 防护形态） | **原地扩展**——工厂内追加 `resolve_optional("agent_drift")` 第七依赖注入（检测器 lambda 无 env 依赖[纯常量构造]，ConfigurationError 防护形态保持同款扩展） |
| AST 架构验证器形态 | `tests/unit/architecture/test_arch_evaluation.py`（REPO_ROOT 常量 + _scan_file_top_imports/_scan_instantiation_sites + 参数化验证器 A/B/C + 词边界正则 + 零抑制注释验证器） | **参考照抄**——test_arch_drift_detection.py（差异：application 白名单是**零第三方**[纯标准库]；domain 触碰含 events/drift_events.py[5.8 是零 events 触碰——本 Story 有新事件，验证器 B 白名单域要加 events]） |
| 集成委托计时模式 | `tests/integration/test_integration_agent_evaluation.py`（_PERF_CACHE 单槽缓存 L54 + 常量单源 L38-57 + xdist_group 同组 + quantiles P95 [18]） | **参考照抄**——P99 版本：`statistics.quantiles(latencies, n=100)[98]`（exclusive P99——100 采样；epics L1838 钦定 P99<100ms）+ 常量单源 DRIFT_P99_LIMIT_SECONDS = 0.1 |
| Fake LLM 手工装配链 | `tests/acceptance/test_acceptance_agent_workflow.py` L185-284（R1 行号修正）（AsyncMock spec + Schema 身份分派） | **直接复用**——AC-3 链级场景工作流装配（幻觉分注入控制 overall_score 序列） |
| 手写零 IO 事件替身 | `_RecordingEventPublisher`（test_acceptance_phoenix_tracer.py L202 先例——全仓 15 文件同款（R1 计数修正）） | **参考照抄**——trigger_recalibration 事件发布断言替身（publish 失败注入变体：抛异常形态测降级） |
| 域名甄别：agent_drift 命名族 | `agent_tracing.py`（5.7）/ `agent_evaluation.py`（5.8） | **命名对齐**——新端口文件 `agent_drift.py` + 注册名 `agent_drift`（Agent 可观测族第三端口，文件名=端口名先例延续）；**区别注记**：drift 检测消费评估产物（5.8 下游）但独立成端口——检测状态生命周期与评估编排解耦（评估无状态[5.8 DC-9] vs 检测器有状态[本 Story DC-6——状态即功能]） |

**明确不存在、本 Story 需新建**（全仓 grep 验证：`CUSUMDriftDetector|DriftDetectionPort|DriftAssessment|DriftDetected|DriftDetectionError|is_drifted|trigger_recalibration` 在 `src/` 零命中[仅规划性注释锚点——agent_tracing.py L56/L111-112/L128 docstring 预告、agent_evaluation.py L102-104 方向注记、evaluation_harness.py L281/L290 可达域注记、composition_root.py L2990-2991 范围注记]；`cusum` 在 src/infrastructure/monitoring/ 零文件；`drift_events|EXCEPTION_451` 零命中）：

1. `DriftDetectionPort` + `DriftAssessment`（src/application/ports/agent_drift.py——漂移检测端口聚合文件）
2. `CUSUMDriftDetector`（src/infrastructure/monitoring/cusum_detector.py——DriftDetectionPort 实现，architecture.md L2594 钦定位置）
3. `DriftDetected` 领域事件（src/domain/events/drift_events.py）
4. `DriftDetectionError`（EXCEPTION_451——src/domain/exceptions/evaluation_exceptions.py 追加[evaluation 子域单文件惯例] + 注册三件）
5. 主链漂移检测块（修改：run_agent_workflow.py——第七可选依赖 + 评估块内漂移块 + catch 扩；纯附加 None 默认向后兼容）
6. 事件通道双登记（configs/event_channels.yaml + channel_router.py DEFAULT_MAPPINGS 各增 DriftDetected 条目）
7. 组合根 `# === Story 5.9 ===` 区段（agent_drift 注册 + use case 工厂第七依赖）
8. 测试资产（**新建十件[.feature/.py 分计] + 追加一件——R1 计数修正**）：`tests/unit/domain/events/test_drift_events.py` / `tests/unit/application/test_agent_drift_model.py` / `tests/unit/infrastructure/monitoring/test_cusum_drift_detector.py` / `tests/contracts/test_port_contract_agent_drift.py` + `test_event_contract_drift_events.py` + `test_event_channel_mapping_drift.py` / `tests/integration/test_integration_drift_detection.py` / `tests/unit/architecture/test_arch_drift_detection.py` / `tests/acceptance/test_acceptance_drift_detection.feature` + `test_acceptance_drift_detection.py`；追加：`tests/unit/domain/exceptions/test_evaluation_exceptions.py`（451 用例）
9. 存量触碰（构造签名七依赖联动——**断言同步 ×5 全清单[R1 全仓实证]**）：①`tests/acceptance/test_acceptance_phoenix_tracer.py`（AC-4.3 构造签名断言基线——L1367-1377 六→七）②`tests/unit/architecture/test_arch_phoenix_tracer.py`（`_USE_CASE_INIT_PARAMS`——L101-108/L304-305 六→七）③`tests/unit/architecture/test_arch_evaluation.py`（use case 六依赖签名基线——L54-61/L229-236 六→七）④**`tests/unit/application/use_cases/test_run_agent_workflow.py`（`test_constructor_sixth_param_default_none` L683-693 内联六清单+默认断言[漂移块用例追加同文件——最易漏处]）**⑤**`tests/acceptance/test_acceptance_agent_evaluation.py`（AC-3.3 六依赖清单断言——L1308-1328，5.8 自身验收资产）**⑥`tests/unit/interfaces/api/test_exception_handlers.py`（expected_types 集合追加——L212/L355 穷举等值断言）；**回执耦合防线（P0 级处方——R1 发现）**：①②文件中 `"evaluation_harness",  # Story 5.8 第六可选依赖` 字面行被 5.8 验收 L1368/1370/1773/1774 文本断言锁死——更新一律**尾部追加** `"drift_detector",  # Story 5.9 第七可选依赖` 行、禁改写/重排既有行；核验命令：`grep -rn "inspect.signature(RunAgentWorkflowUseCase\|inspect.signature(use_case_cls" tests/`（五处直命中）+ `grep -rn '"evaluation_harness",' tests/`
10. 异常注册三件：`src/domain/exceptions/_code_ranges.py`（_CLASS_TO_SUBDOMAIN 增 DriftDetectionError → evaluation 行——CODE_RANGES evaluation 行已存在[5.8 建]零改动）+ `src/domain/exceptions/__init__.py`（导出）+ `src/interfaces/api/exception_handlers.py`（EXCEPTION_HTTP_MAP 451→500）
11. 事件导出：`src/domain/events/__init__.py`（DriftDetected import + __all__）+ `src/application/ports/__init__.py`（DriftDetectionPort/DriftAssessment 聚合导出）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: CUSUMDriftDetector 双侧累积和算法（预热基线 + N中M 确认 + 分级 + 确认后复位）

**Given** 真实 `CUSUMDriftDetector` 实例（手工构造——检测器无外部依赖纯内存计算；**每场景新实例**——SINGLETON 状态跨场景污染防线）与附录 I 钦定参数（模块常量单源：`K_MULTIPLIER=0.5` / `H_MULTIPLIER=5.0` / `CONFIRMATION_N=3` / `CONFIRMATION_M=5` / `WARMUP_SAMPLES=30`——§29.3.1.1 默认值 + §29.2.3.2 样本量 30 锚）
**When** 依序调用 `await detector.update(score)` 灌入评估分数序列（[0,1] 域 float——overall_score 语义）
**Then** 检测管线按三阶段执行：①**预热期**（前 30 样本）——样本入基线窗（deque maxlen=30），返回 `DriftAssessment(baseline_ready=False, is_drifted=False, sample_count=N, baseline_mean/baseline_std=预热期当前统计)`——预热期不判定不累积（σ₀ 未立即判定必是噪声误报；**N=1 时 baseline_std=0.0**[R1 钉死——statistics.stdev 需 ≥2 样本，单样本以 0.0 返回，与 degenerate ε 防线语义一致]）；第 30 样本后基线冻结（μ₀/σ₀ 经 `statistics.mean/stdev`——样本标准差 ddof=1 语义）；②**检测期**——双侧累积和增量更新（附录 I §29.1.1.1 钦定公式）：`Sₕ = max(0, Sₕ + (x - μ₀ - k))`、`Sₗ = max(0, Sₗ + (μ₀ - k - x))`，其中 `k = 0.5×σ₀`、`h = 5×σ₀`；每样本判定 `detection = max(Sₕ, Sₗ) > h` 记入确认窗（deque maxlen=5）；**N中M 确认**（§29.3.2.2）：确认窗满 5 且最近 5 样本中 detection 次数 ≥3 **且当前样本 detection=True**（R1 新增条件——ISA-18.2 M-of-N 告警宣告语义[确认时刻必在告警态]；该条件使确认时 max(Sₕ,Sₗ)>h 恒成立 → ratio/σ₀ >5、level 两档域完备——纯 N中M 下确认可落在非 detection 样本、ratio 可 ≤5[实证反例：基线后 [0.239,0.239,1.0,1.0,1.0] → 窗 (T,T,T,T,F) 计数 4 确认而 ratio=4.40，level 无合法值击穿 DriftAssessment 自身守卫]）→ `is_drifted=True`；③**确认后复位**（OD-5）——确认即 Sₕ/Sₗ 归零 + 确认窗清空（基线保持），返回 `DriftAssessment(is_drifted=True, drift_direction="up"|"down", drift_level="moderate"|"severe", cusum_high/cusum_low=确认时统计量, baseline_mean/std, observed_value, sample_count, baseline_ready=True)`；direction 按 Sₕ vs Sₗ 大者（§29.7.1 _determine_direction）；level 按 `ratio = max(Sₕ,Sₗ)/σ₀`：`>8 severe` / `5<r≤8 moderate`（§29.3.2.1 两档——minor 观察档不可达注记 OD-5）
**And** **degenerate 基线防御**：基线窗全同值样本（σ₀ < 1e-12）时检测期样本不判定（detection 恒 False 继续累积样本计数——可观测降级非异常）；**入参域守卫**：score 非 [0,1]（越界/bool/非数值）抛 `ValidationError`（EXCEPTION_201——应用层输入校验，5.8 EvaluationResult 分数域守卫同款；context 携 `{score: 实际值}`）；**手算锚钦定**（R1 数值修正——σ₀=statistics.stdev=√(0.3/29)≈0.1017 **非 0.1**：k=0.5σ₀≈0.0509、h=5σ₀≈0.5085；测试断言一律钦定同式表达式 `(0.8 - 0.5*sigma0 - 0.4) * n`[σ₀ 经 statistics.stdev(baseline) 实算]——**禁 `0.8-0.05-0.4` 类 k 写死 0.05 的假红形态、禁 pytest.approx[仓内无 approx 先例——纪律是精确等式+同式表达式]**、禁十进制字面量；正文数值为舍入示意）：基线序列 = `[0.7, 0.9]×15`（μ₀=0.8，σ₀≈0.1017[交替序列样本标准差]），漂移注入 = 样本 31-35 全 0.4 → 逐样本 Sₗ 演算 ≈0.349/0.698/1.047/1.397/1.746（增量 = μ₀−k−x ≈ 0.349）→ s31 detection=False（0.349<h≈0.509）、s32 起连续 4 次 True → s35 确认窗满（F,T,T,T,T）计数 4≥3 且当前样本 T → **确认 drift_direction="down"、ratio=Sₗ/σ₀≈17.2>8 → severe**；对照锚：基线后继续交替序列（0.7/0.9 续灌 10 样本）→ Sₕ/Sₗ 增量交替 ≈+0.049/−0.151 不累积（S 在 0↔0.049 震荡）→ 恒不触发；正向漂移锚（R1 修正——原 0.95×6 **数学上不可确认**：首 detection 在第 6 样本、窗计数 1<3）：基线后灌 **0.95×8** → Sₕ 增量 = 0.95−0.8−0.5σ₀≈0.099/样本 → 前 5 样本 Sₕ≈0.496<h≈0.509（余量 2.5% 不触发——非边界形态）→ 第 6 样本 Sₕ≈0.595 首次 detection → 第 8 样本窗 (F,F,T,T,T) 计数 3 且当前样本 T → **确认 direction="up"、Sₕ≈0.793、ratio≈7.80 → moderate**

**验证标准/Validation Criteria:**
- [ ] 预热期行为：前 30 样本 baseline_ready=False + is_drifted=False + sample_count 递增 + baseline_mean/std = 预热统计（statistics.mean/stdev 手算对照；**N=1 时 baseline_std=0.0 断言**——R1 钉死）；第 31 样本起 baseline_ready=True
- [ ] 双侧累积和手算锚：漂移注入序列逐样本 Sₗ 断言（≈0.349/0.698/1.047/1.397/1.746——**钦定同式表达式 `(0.8 - 0.5*sigma0 - 0.4) * n`**[σ₀=statistics.stdev(baseline) 实算；禁 `0.8 - 0.05 - 0.4` 假红形态与 approx]）；s35 确认 is_drifted=True + direction="down" + level="severe"（ratio 断言 `(0.8 - 0.5*sigma0 - 0.4) * 5 / sigma0 > 8` 同式表达）
- [ ] N中M 确认逻辑：确认窗未满 5 不确认（s32-s34 detection True 但 is_drifted=False）；**当前样本条件**（R1 语义修正）：窗满 5 且计数 ≥3 但当前样本 F → 不确认（(F,T,T,T,F) 参数化）；正形态 (F,T,T,F,T) → 计数 3 且当前 T → 确认（参数化补充）；(F,T,T,F,F) → 计数 2 不确认
- [ ] 确认后复位：确认返回的 assessment 之后新序列从零累积（后续 update 的 cusum_low 从 0 重启——重复告警节奏锚）；基线保持（复位后 baseline_mean/std 与复位前相等断言）
- [ ] 无漂移对照：交替序列续灌不触发（is_drifted 恒 False + Sₕ/Sₗ 有界）
- [ ] 正向漂移：up 方向确认 + level=moderate 判定（**0.95×8** 序列手算锚——R1 修正：原 0.95×6 不可确认[首 detection 在第 6 样本、窗计数 1<3]；s38 确认、Sₕ≈0.793、ratio≈7.80→moderate；前 5 样本 Sₕ≈0.496<h 余量 2.5% 不触发断言）
- [ ] degenerate 防御：全同值基线（[0.8]×30）后漂移注入 → 恒不判定（σ₀≈0 → k/h≈0 防线）+ sample_count 继续递增
- [ ] 入参域守卫：score=-0.01/1.01/True/"0.8" 参数化 → 201 三段式断言（raises → code EXCEPTION_201 → context["score"]）
- [ ] 模块常量单源断言（五常量值锁定附录 I——防参数漂移：K_MULTIPLIER==0.5 等逐项）

### AC-2: trigger_recalibration 与 DriftDetected 事件（发布 + 通道双登记 + 发布失败降级）

**Given** 真实 `CUSUMDriftDetector`（构造注入手写零 IO `_RecordingEventPublisher` 替身——EventPublisher 协议 duck-typing 实现，publish 捕获事件列表）+ 确认漂移的 `DriftAssessment` 实例（AC-1 手算锚序列产出）
**When** 调用 `await detector.trigger_recalibration(assessment)`
**Then** 构造并发布 `DriftDetected` 领域事件：frozen dataclass 继承 `DomainEvent`（kw_only 必填字段 + event_type init=False 自动注册）；字段 = `drift_id: uuid4 default_factory`（aggregate 锚——StrategicDeviationWarning.warning_id 模式）+ **`agent_id: str | None = field(kw_only=True, default=None)`（R1 新增——人工介入定位维度：SINGLETON 检测器跨 Agent 混流知悉[多 Agent 质量分布差异膨胀 σ₀——docstring 注记 + per-agent 键控 V1-EV14 登记]，由调用方[use case execute 形参]透传，None=未知/混合）** + `metric_name: str`（"overall_score"——检测器绑定常量）+ `drift_direction/drift_level: str` + `cusum_high/cusum_low/baseline_mean/baseline_std/observed_value: float` + `sample_count: int` + `recommended_action: str = "manual_review"`（OD-6——人工介入通道）；`aggregate_type="AgentEvaluation"`（漂移的监控对象是 Agent 评估质量）；**未确认守卫（R1 裁定——取消原「仍发布/不发布二选一」悬空决策）**：trigger_recalibration 对 `is_drifted=False` 的 assessment 直接 return None **零发布**（调用方守卫[DC-5]与 trigger 内守卫双保险——防 drift_level="none" 泄入事件语义污染）；发布经注入 publisher 的 `publish(event)` 单次调用（替身捕获断言）
**And** **发布失败降级**：替身 publish 抛 Exception 注入 → trigger_recalibration 捕获 logger.error **不上抛**（agent_profile_loading.py L151-169 先例——漂移检测是可观测附加面，事件失败不阻断主链）+ 返回 None 正常；**通道双登记**：`configs/event_channels.yaml` 增 `DriftDetected: {rabbitmq_routing_key: "sisys.events.reliable.drift_detected", delivery_mode: "reliable", description: "CUSUM 漂移检测确认（触发重校准——人工介入通道）"}` + `ChannelRouter.DEFAULT_MAPPINGS` 增同字段 ChannelMapping（reliable 单通道——告警不可丢；rabbitmq_routing_key 命名对齐 `sisys.events.reliable.<snake_case>` 惯例）——**双处逐字段一致**（test_event_channel_mapping_tool_version.py 先例门禁形态）；无 routing_key 映射时 RabbitMQEventBus.publish 返回失败 ChannelResult（调研实证——双登记是事件可达性前提非装饰）

**验证标准/Validation Criteria:**
- [ ] 事件字段真值：发布的事件 isinstance DriftDetected + metric_name=="overall_score" + direction/level/cusum/基线/observed_value/sample_count 与 assessment 逐字段相等 + recommended_action=="manual_review" + **agent_id 透传断言**（注入 agent_id="agent-x" → 事件 agent_id=="agent-x"；None 默认透传 None）+ **未确认 assessment → 零发布断言**（is_drifted=False 注入 → 替身零捕获 + returns None）
- [ ] 事件契约：DomainEvent._registry 自动注册断言（event_type init=False 写法）+ aggregate_type=="AgentEvaluation" + to_dict 序列化含全部业务字段（payload 并入——test_event_contract_tool_version_events.py 先例三断言）
- [ ] 发布失败降级：替身抛 RuntimeError → trigger_recalibration 不上抛（returns None）+ caplog error 断言
- [ ] 通道映射契约：yaml 与 DEFAULT_MAPPINGS 双处存在 + rabbitmq_routing_key 两处一致 =="sisys.events.reliable.drift_detected" + delivery_mode 两处一致 =="reliable"（test_event_channel_mapping_drift.py——reliable 版先例形态）
- [ ] 事件单测：构造（kw_only 必填）/frozen/默认值（recommended_action）/drift_id 自动生成（tests/unit/domain/events/test_drift_events.py）

### AC-3: 主链接入——第七可选依赖 + 漂移检测块 + drift.detected span 填值 + 降级网扩 451（OD-2[5.7] 兑现）

**Given** 工作流链 = 5.8 手工装配形态（Fake LLM Schema 身份分派[幻觉分注入控制 overall] + 真实 AgentWorkflowService/LangGraphEngine/RunAgentWorkflowUseCase + 零 IO stub 仓储）+ use case 构造注入 `drift_detector`（真实 CUSUMDriftDetector + 手写零 IO publisher 替身——**链级场景检测器预填充形态**：场景内先手工 `update()` 灌入 34 样本[30 基线交替 + 4 个 0.4 漂移]，链上最后 1 样本由 execute 的评估块提供 → 单次 execute 即确认漂移——多 run 循环驱动形态的轻量替代，35 样本手算锚尾样本即 s35）+ 链级 initialize 全局通道（场景级新 TracerProvider + SimpleSpanProcessor + InMemorySpanExporter——5.7 SSOT）
**When** 调用 `RunAgentWorkflowUseCase.execute(agent_id, task)` 执行六阶段工作流
**Then** 评估块内（`evaluate` 成功 + 三键写入之后、评估块 try 体内）漂移检测块执行：`if self._drift_detector is not None:` → `assessment = await self._drift_detector.update(evaluation_result.overall_score)` → `if assessment.is_drifted:` → `span.is_recording()` 守卫下经 `SpanAttributeKeys.DRIFT_DETECTED` 常量写 True（**OD-2[5.7] 全量兑现——drift.* 生产填值**；仅确认漂移时写——预热期/无漂移/降级跳过均不写[键缺席=本 run 无确认漂移，与 eval 三键「缺席=降级」语义分立——docstring 注记]）→ `await self._drift_detector.trigger_recalibration(assessment, agent_id=agent_id)`（事件发布——agent_id 从 execute 形参透传[R1 新增：DriftDetected 人工介入定位维度]）；工作流返回值与漂移块零耦合（result 原样返回）
**And** **降级路径**（可观测附加面哲学——5.8 DC-5 同款延续）：漂移块抛 `DriftDetectionError`（451——Fake drift port update side_effect 注入）→ 评估块 catch 元组已扩 `(AgentEvaluationError, LLMConfigError, DriftDetectionError)` → logger.warning 降级跳过 → 主链正常返回 + **eval 三键仍在**（评估先于漂移成功——三键写入在漂移块之前）+ drift.detected 缺席 + MVP 十属性不受影响；**评估降级联动**（评估失败 → EvaluationResult 不可得 → 漂移块天然跳过——序列缺口策略 MVP=跳过[5.8 风险 #6 处置②]）；**未注入路径**（`drift_detector=None`——七参默认）：漂移块整体跳过 + 行为与 5.8 交付态完全一致（存量零破坏前提）；**构造签名扩展**：use case 第七可选依赖 `drift_detector: DriftDetectionPort | None = None`（尾部追加——存量六参构造调用零破坏）；**存量断言同步 ×5**（R1 全仓实证清单[调研期 `grep -rn "inspect.signature(RunAgentWorkflowUseCase\|inspect.signature(use_case_cls" tests/` 直命中五处——原 ×3 漏两处，恰是 5.8「实施才发现」教训重演面]）：①test_acceptance_phoenix_tracer.py AC-4.3 构造签名断言基线（L1367-1377 六→七）；②test_arch_phoenix_tracer.py `_USE_CASE_INIT_PARAMS` 常量（L101-108/L304-305 六→七）；③test_arch_evaluation.py use case 六依赖签名基线（L54-61/L229-236 六→七）；④**test_run_agent_workflow.py `test_constructor_sixth_param_default_none`（L683-693 内联六清单+默认断言——漂移块用例同文件追加，最易漏）**；⑤**test_acceptance_agent_evaluation.py AC-3.3 六依赖清单断言（L1308-1328——5.8 自身验收资产）**；**回执耦合防线（P0 级处方）**：①②文件中 `"evaluation_harness",  # Story 5.8 第六可选依赖` 字面行被 5.8 验收 L1368/1370/1773/1774 文本断言锁死——更新一律**尾部追加** `"drift_detector",  # Story 5.9 第七可选依赖` 行、禁改写/重排既有行；核验命令 = `grep -rn "inspect.signature(RunAgentWorkflowUseCase\|inspect.signature(use_case_cls" tests/`（五处直命中）+ `grep -rn '"evaluation_harness",' tests/`（清单字面量行）——R1 修正：原 grep 模式（中文注释「六依赖」）依赖巧合、对 L1367 不命中

**验证标准/Validation Criteria:**
- [ ] 主链漂移确认：预填充 34 样本 + execute（Fake 幻觉分注入使 overall 落**病态角带 [0.475,0.65] 漂移侧**——R1 措辞修正：5.8 交付注记 agent_evaluation.py L104-109 明示常规形态落病态角带、勿空耗调 Fake 追 0.4 精确值；**末样本精确值不苛求**：预填充 4×0.4 已使 Sₗ≈1.397>h，末样本取 [0,1] 内 ≤0.7 任意值均确认 down[R1 演算——Sₗ 预累积主导]）→ agent_execution 根 span `attributes["drift.detected"] is True`（键字符串逐字对照——5.7 契约兑现锚）+ DriftDetected 事件发布断言（替身捕获 + direction=="down" + agent_id==execute 形参值）
- [ ] 无漂移路径：预填充 34 样本后 execute（幻觉分注入正常 0.8 邻域 overall）→ drift.detected 缺席断言（span.attributes 不含键）+ 事件零发布
- [ ] 降级路径：Fake drift port（AsyncMock spec=DriftDetectionPort——单测层 mock 合规）update 抛 DriftDetectionError → 主链正常返回 + 三键仍在 + drift.detected 缺席 + warning 日志（caplog）+ 十属性不受影响
- [ ] 评估降级联动：Fake LLM 幻觉分支抛 LLMAPIError → 漂移块跳过（update 零调用断言——Fake drift port 调用计数）+ drift.detected 缺席
- [ ] None 默认路径：六参构造（不注入 drift_detector）→ execute 行为与 5.8 基线一致（回归锚）+ 漂移块零执行
- [ ] 构造签名：七依赖签名断言（inspect.signature 参数清单 == [agent_repository, agent_profile_use_case, agent_engine, agent_workflow_service, isolation_guard, evaluation_harness, drift_detector]——第七参数默认 None）+ 存量断言同步 ×5 更新后全绿
- [ ] **5-3/5-7/5-8 存量全家回归绿**：5.3 全家（单测/契约×3/图/引擎/集成/验收）+ 5.7 全家（单测×3/契约/test_arch[资产同步②更新后]/集成/验收 15 场景[AC-4.3 更新后]）+ 5.8 全家（单测×4/契约×2/test_arch_evaluation[资产同步③更新后]/集成/验收 13 场景）逐一登记

### AC-4: 端口接线、架构合规与组合根注册

**Given** 端口、实现、事件、主链漂移块全部交付
**When** 验证接线与合规
**Then** 新端口经组合根 `# === Story 5.9 ===` 区段注册且 resolve 可达（PortSpec 元数据对齐 5.8 形态；**R1 实测注记**：resolve 链会真实构造 DualChannelEventBus——其构造器纯依赖注入零连接[dual_channel_event_bus.py L36-42 + Redis/RabbitMQ 总线同形态]，连接惰性在 publish 面——验收「零外部服务依赖」前提成立）：`agent_drift`：v1.0.0 / `DriftDetectionPort` / lambda 注入 `CUSUMDriftDetector(event_publisher=resolver.resolve("event_publisher"))` / module=src.infrastructure.monitoring.cusum_detector / **SINGLETON**（有状态检测器——状态即功能：跨 run 序列累积是设计意图，与 5.8 无状态 SINGLETON 论证分立[DC-6]）/ owner=platform / tags=("agent", "drift", "observability")；use case 工厂 `_build_agent_workflow_use_case` 扩展：`resolve_optional("agent_drift")` 注入第七依赖（可选依赖先例——5.6 audit_service/5.8 evaluation 同款；接线失败降级 None 不阻断 bootstrap）；契约测试 ×3（端口 11 维度 + 事件契约 + 通道映射契约）
**And** **CR1-DF2[5.8] 一并处置**：接线测试场景覆盖工厂降级防护面（agent_drift 注册缺失/构造失败注入 → `_drift_detector` None + use case 正常构造——与评估接线降级同窗断言）；架构合规：application 触碰文件第三方白名单（agent_drift.py / run_agent_workflow.py——**零新增第三方**：agent_drift.py 纯标准库、run_agent_workflow.py 既有 opentelemetry + 新增 agent_drift import[application 同层] 均在 5.8 验证器 A+ 基线内）；domain 触碰面（drift_events.py[标准库零依赖——DomainEvent 基类同族] + evaluation_exceptions.py 追加 + _code_ranges.py + __init__.py 两处——**events 触碰是本 Story 与 5.8 的差异面**：5.8 零 events 触碰，本 Story 新增 DriftDetected[漂移是领域告警语义——与 StrategicDeviationWarning 同族论证：数值偏离告警是领域概念；评估是应用可观测面 vs 漂移告警是领域事件的分界——评估结果服务于单 run 观测、漂移确认是跨 run 聚合的领域级异常状态]）；组合根外零实例化（CUSUMDriftDetector 构造点仅 composition_root.py + tests/）；依赖方向：CUSUMDriftDetector（infrastructure）→ DriftDetectionPort（application）+ EventPublisher/DriftDetected（domain）合法 ✓；`.env.example` 零改动（无新环境变量——CUSUM 参数是代码常量）

**验证标准/Validation Criteria:**
- [ ] 组合根注册 + resolve 四件断言（可达/isinstance/PortSpec 元数据/lifetime==SINGLETON——5.8 AC-4.1 同款）
- [ ] use case 工厂注入断言（resolve("agent_workflow_use_case") 实例的 `_drift_detector` 非 None 且 isinstance DriftDetectionPort——接线可达性）
- [ ] CR1-DF2 降级防护：_DummyResolver 未注册 agent_drift 形态 → resolve_optional None → use case 构造成功 + `_drift_detector` is None
- [ ] 契约测试 ×3 全绿（端口 11 维度 REQUIRED_METHODS=["update", "trigger_recalibration"]；事件注册/aggregate/to_dict；通道双登记一致）
- [ ] AST 验证器 A：application 触碰文件第三方白名单（零新增断言——黑名单新第三方零引入）
- [ ] AST 验证器 B：domain 触碰面收窄断言（业务符号在 domain/ports|services|entities|value_objects 零命中 + **events 白名单域含 drift_events.py** + DriftDetectionError 仅在 exceptions 三件内）+ 组合根外零实例化 + 依赖方向（cusum_detector.py import src.application/src.domain 断言——infrastructure→application/domain 合法面锚定）
- [ ] AST 验证器 C：主链漂移块静态锚（execute 体内 update 调用 + DRIFT_DETECTED 常量引用[ast.Attribute 属性形态——5.8 R3 钉死双形态接受] + is_drifted 分支 + trigger_recalibration 调用在位）+ use case 七依赖签名基线 + drift_events.py/cusum_detector.py 标准库零外部依赖断言
- [ ] .env.example 零改动断言（收尾场景断言面）

### AC-5: 性能双锚——检测延迟 P99<100ms + 合成序列回测准确率≥85%

**Given** ①检测延迟口径 = **纯内存检测管线开销**（update 双侧累积 + N中M 确认 + DriftAssessment 构造——单次 update 调用；**事件发布不在口径内**[Outbox 写 PG 是 IO——发布是确认后的重校准触发动作，非检测延迟面；epics L1838「检测延迟」语义锚定判定时延]；μs 级预期——0.1s 上限对纯内存管线宽松，门定位是回归绊线[意外同步阻塞/算法误入 O(n) 全量重算会击穿]——5.8 DC-8④同款诚实注记）；②合成回测口径（**R1 参数定稿**——原稿序列长度/分布形态/漂移段样本数/移位抽取方式四参数未钉死，FP 率实测敏感[蒙特卡洛：评估段长 70 时最坏 acc=0.775 击穿门]）：确定性种子 `random.Random(20261028)` 生成 40 条序列（**前 20 稳定/后 20 漂移按序生成，每条总长 60 样本 = 前 30 基线期 i.i.d. `rng.uniform(0.7, 0.9)`**[预热恰好消费全部基线期样本估计 μ₀/σ₀，σ̂₀≈0.058]**+ 后 30 评估期**——稳定序列评估期同分布续灌；漂移序列先抽 `delta = rng.uniform(0.3, 0.5)`、再 i.i.d. `rng.uniform(0.7-delta, 0.9-delta)`[均值移位 ≈4.9σ~8.1σ——R1 口径修正：σ̂₀ 按 uniform 实算 ≈0.058，-0.3 实为 ≈4.9σ **非原稿「≈3σ」**[原稿套用了手算锚的 σ₀≈0.1]；全部样本天然落 [0,1] 域——**禁未截断正态**：实测 normal(0.8,0.1) 每 2400 抽样约 68 次越域触发 201]]），每条独立检测器实例跑全序列，统计 TP[漂移序列评估期出现任一确认]/FP[稳定序列出现任一确认]/TN——**准确率 = (TP+TN)/40 ≥ 0.85**（epics L1839「漂移检测准确率≥85%」的合成回测承载——OD-7；真实历史回测 V2；**钦定种子基准实测 TP=20/FP=1/acc=0.975，2000 种子鲁棒性 acc<0.85 概率 0%**）
**When** ①测量检测管线延迟（warmup 1 + **100 采样**——P99 需 99 分位 `statistics.quantiles(latencies, n=100)[98]` exclusive[5.8 P95 [18] 的 P99 版；100 采样纯内存仍是 ms 级总耗时]；单次采样 = detector 完整 update 调用[检测器预填充至检测态——每采样含双侧计算+判定+确认窗更新]）②跑合成回测矩阵
**Then** ①P99 < `DRIFT_P99_LIMIT_SECONDS = 0.1`（epics L1838 钦定 100ms——常量单源定义于集成模块，验收侧 import 禁双真源）；委托计时（`_PERF_CACHE` 单槽缓存 + `xdist_group("drift-detection-perf")` 同 worker 串行——组名与既有 13 组互异[全仓 grep 断言——13 组**实名**清单（R1 修正——六组带 -perf 后缀，原清单漏写后缀照抄必错）：agent-workflow-perf/agent-isolation-perf/agent-triple-isolation-perf/isolation-switch-log-perf/phoenix-tracer-perf/agent-evaluation-perf/agent-instantiation/agent-profile-loading/data-source-cache/sandbox-daemon/tool-executions-pg/tool-versions-pg/validation-feedback-pg——drift-detection-perf 未占用]）；**正向锚**：采样轮 update 调用计数 == 采样数（防静默跳过假绿）；②回测准确率 ≥0.85 断言 + TP/FP/TN 分项可观测（assert 消息携带分项计数——失败可诊断）+ 确定性（同种子重跑同结果——固定种子断言锚）
**And** 采样入口自包含（每采样批次独立构造检测器——无跨场景状态残留）；回测序列生成器为纯函数（seed 入参——同函数同输出）；漂移注入幅度按 uniform σ̂₀≈0.058 计 ≈4.9σ~8.1σ（强漂移注入——检测器设计检测灵敏度 0.5σ-2σ[§29.1.1.2 CUSUM 优势区间]的保守上界侧，小漂移检出是 V1 调参面；**评估段长 30 是定稿值禁拉长**——FP 随评估段长线性增长[蒙特卡洛实测 L=70 最坏 acc 0.775]；FP 主因是 n=30 基线 σ̂₀ 低估[相对标准误 ≈1/√(2×30)≈13%]非算法缺陷——docstring 知悉注记）

**验证标准/Validation Criteria:**
- [ ] P99<100ms：常量单源（集成定义/验收 import）+ 委托缓存命中（验收 AC-5.1 不自跑采样）+ 100 采样 quantiles[98] exclusive 口径 docstring 声明
- [ ] 正向锚：采样批次 update 调用计数 == warmup + 采样数
- [ ] 回测准确率 ≥0.85（TP+TN)/40 + 分项计数断言消息 + 固定种子确定性（两次跑同结果）+ **60 样本/30 评估段参数定稿与评估段长禁拉长注记落 docstring**（R1 定稿口径）
- [ ] xdist 组 drift-detection-perf 与既有 13 组互异（全仓 grep 断言）
- [ ] 口径声明落 docstring（检测管线开销 vs 事件发布延迟分述 + 合成回测 vs 真实历史回测分述——防后续误读）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] `DriftDetected`（`src/domain/events/drift_events.py`，`@dataclass(frozen=True)` 继承 `DomainEvent`——StrategicDeviationWarning 数值告警先例 + AgentProfileLoaded kw_only 纪律）：
  - 字段：`drift_id: uuid.UUID = field(default_factory=uuid.uuid4)` / **`agent_id: str | None = field(kw_only=True, default=None)`（R1 新增——SINGLETON 跨 Agent 混流知悉：检测器不感知 Agent、由调用方[use case execute 形参]透传，None=未知/混合；per-agent 键控 V1-EV14 登记）** / `metric_name: str = field(kw_only=True)` / `drift_direction: str = field(kw_only=True)`（"up"|"down"）/ `drift_level: str = field(kw_only=True)`（"moderate"|"severe"）/ `cusum_high: float = field(kw_only=True)` / `cusum_low: float = field(kw_only=True)` / `baseline_mean: float = field(kw_only=True)` / `baseline_std: float = field(kw_only=True)` / `observed_value: float = field(kw_only=True)` / `sample_count: int = field(kw_only=True)` / `recommended_action: str = "manual_review"` / `event_type: str = field(default="DriftDetected", init=False)`
  - `__post_init__`：aggregate_id ← drift_id；aggregate_type = "AgentEvaluation"（漂移监控对象是 Agent 评估质量——与 5.8「评估非领域概念」分界：评估结果是单 run 应用观测、漂移确认是跨 run 聚合的领域级告警状态[StrategicDeviationWarning 同族]）
  - **事件通道双登记（CLAUDE.md 硬约束）**：`configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS` 各增 `DriftDetected` 条目（`rabbitmq_routing_key: "sisys.events.reliable.drift_detected"` / `delivery_mode: "reliable"` / description）——reliable 单通道（告警不可丢——Outbox 投递；realtime Redis pub/sub 对告警消费方无订阅面，不双通道）
- [ ] **不修改既有事件**（RoutingDecided/AgentDecided 等零触碰——漂移检测无既有事件语义扩展需求）

#### 数据模型 (Data Models)

- [ ] `DriftAssessment`（`src/application/ports/agent_drift.py`，`@dataclass(frozen=True)`——与 EvaluationResult 同层同风格[application/ports DTO 族]）：
  - 字段：`is_drifted: bool` / `baseline_ready: bool`（预热态可观测）/ `drift_direction: str`（"up"|"down"|"none"）/ `drift_level: str`（"moderate"|"severe"|"none"）/ `cusum_high: float`（≥0）/ `cusum_low: float`（≥0）/ `baseline_mean: float`（预热期当前统计或冻结基线）/ `baseline_std: float`（**N=1 时 0.0——statistics.stdev 需 ≥2 样本[R1 钉死]**）/ `observed_value: float`（[0,1]）/ `sample_count: int`（≥1）
  - **可观测性注记（R1）**：逐样本 detection 布尔不进 DTO——AC-1 验证标准的 detection 断言经 `cusum_high/low 与 h=5×baseline_std 同式比较`推导断言；Sₕ==Sₗ==0 平局时 direction 归 "none"（未确认态语义）
  - `__post_init__` 守卫：`observed_value` 数值类型（bool 拒）+ [0,1] 闭区间；`cusum_high/cusum_low ≥ 0`；`sample_count ≥ 1`；`drift_direction ∈ {"up","down","none"}`、`drift_level ∈ {"moderate","severe","none"}`（Literal 域）；一致性守卫（`is_drifted=False → drift_level=="none" and drift_direction in {"none","up","down"}`[方向在未确认时可带探测值——确认语义只锁 level]；`is_drifted=True → drift_direction != "none" and drift_level != "none"`）——违规抛 `ValidationError`（EXCEPTION_201——应用层输入校验；context 携 `{字段名: 实际值}`——242 惯例形态）
- [ ] CUSUM 参数常量（`src/infrastructure/monitoring/cusum_detector.py` 模块级单源——`EVALUATION_TEMPERATURE` 先例形态）：`METRIC_NAME = "overall_score"` / `K_MULTIPLIER = 0.5` / `H_MULTIPLIER = 5.0`（附录 I §29.3.1.1 + §29.3.3.2 质量指标 accuracy 行）/ `CONFIRMATION_N = 3` / `CONFIRMATION_M = 5`（§29.3.2.2 警告级 3中5）/ `WARMUP_SAMPLES = 30`（§29.2.3.2 样本量下限锚——OD-3）/ `_DEGENERATE_STD_EPSILON = 1e-12`（σ₀ 退化防线）
- [ ] **本 Story domain 层数据模型零新增业务实体**（DriftAssessment 是应用层 DTO；DriftDetected 是事件非实体；domain 触碰 = events/drift_events.py + exceptions 三件——见六边形约束节）

#### 统一端口定义注册与管理 (Port Contract)

- [ ] `DriftDetectionPort`（`src/application/ports/agent_drift.py`，`@runtime_checkable Protocol`——**R2 具体应用端口**：Agent 评估可观测族[5.7-5.9]第三端口，与 agent_tracing/agent_evaluation 同层同族；**R1 组合**：实现方组合注入 EventPublisher[domain 基础端口]；**R3 落点**：CUSUMDriftDetector 在 infrastructure/monitoring 实现（architecture.md L2594 钦定位置）——检测状态管理（进程内累积/预热/复位）是技术实现面，可替换[Redis 持久化实现/多指标扩展——V1 演化轴]，支持扩展其他同类技术实现）：
  - `async def update(self, score: float) -> DriftAssessment`——灌入单个评估分数并执行漂移检测（双侧累积和增量 + N中M 确认 + 确认后复位；OD-7——update+is_drifted 两方法伪码的单方法原子化，is_drifted 判定语义由返回值承载）。Args: score 本次评估 overall_score（[0,1]）。Returns: DriftAssessment 本次检测评估。Raises: `ValidationError`（201——score 域校验）；`DriftDetectionError`（451——检测管线状态异常防御面）
  - `async def trigger_recalibration(self, assessment: DriftAssessment, agent_id: str | None = None) -> None`——触发重校准（**is_drifted=True 守卫：未确认 assessment 直接 return None 零发布**[R1 裁定——与调用方守卫双保险，取消原「二选一」悬空；防 level="none" 泄入事件]；确认漂移后：构造并发布 DriftDetected 领域事件[reliable 通道——人工介入通知，agent_id 透传] + logger.warning；OD-6——MVP「提示人工介入」单通道，自动配置变更 V1）。Args: assessment 确认漂移的检测评估（事件字段数据源）。agent_id 漂移监控对象 Agent 标识（execute 形参透传；None=未知——SINGLETON 跨 Agent 混流知悉）。Raises: 无（发布失败内部 logger.error 降级不上抛——可观测附加面）
- [ ] 组合根注册元数据（Task 0 定义、Task 1 落地）：`agent_drift`：v1.0.0 / DriftDetectionPort / CUSUMDriftDetector（lambda：`resolver.resolve("event_publisher")` 单依赖注入）/ module=src.infrastructure.monitoring.cusum_detector / SINGLETON（**有状态单例——状态即功能**[DC-6]：跨 run 序列累积；重启归零 MVP 知悉[OD-3⑤]，V1 Redis 持久化）/ owner=platform / tags=("agent", "drift", "observability")
- [ ] **既有组件消费方变更（契约变更登记 ×1）**：`RunAgentWorkflowUseCase.__init__` 第七可选依赖 `drift_detector: DriftDetectionPort | None = None`（尾部追加——存量六参调用零破坏）+ 评估块内漂移块（~8 行：None 守卫 + update + is_drifted 分支 + DRIFT_DETECTED 写入 + trigger_recalibration）+ 评估块 catch 元组扩 DriftDetectionError——**存量断言同步 ×5**（5-7 验收 AC-4.3 + 5-7 test_arch `_USE_CASE_INIT_PARAMS` + **5-8 test_arch_evaluation 六依赖基线**——预防性全清单登记）
- [ ] 端口契约测试三份（`tests/contracts/test_port_contract_agent_drift.py`[11 维度 + _DummyResolver **加 event_publisher 分发分支**——R1 注记：分发面是扩展非照抄（先例 _DummyResolver 仅 llm_client/evaluation_model_resolver 两分支），llm_client 双分发先例可循；**归 Task 2 落地**] + `test_event_contract_drift_events.py`[注册/aggregate/to_dict——Task 1] + `test_event_channel_mapping_drift.py`[双登记逐字段一致——Task 1]）
- [ ] **禁止**在服务文件本地定义 Protocol/Port 抽象（DriftAssessment/端口定义在端口文件，检测器只 import）；**禁止**新建语义重复端口（禁新建 drift/detector/monitoring 同义端口；MetricsPort[Prometheus 计量]与 ExceptionMetricsPort 既有面不碰——语义分立：计量导出 vs 漂移判定）

#### 端口契约清单执行约束（强制）
- [ ] 本 Story 端口清单唯一真源 = 本 Task 0 定义（`agent_drift` 一新端口 + 一项既有组件消费方变更：use case 第七依赖——契约变更登记）
- [ ] 禁止新增未登记端口；禁止未同步 registry/resolver/contract test
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> 原则/适用范围/禁止条款同模板基线。**本 Story 新增领域异常 ×1**（evaluation 子域预留段取用——_code_ranges.py L137-138 注释钦定「451-459 预留给 5.9 漂移检测」）：

- [ ] **归属模块与基类**：evaluation 子域既有段（CODE_RANGES `"evaluation": (450, 459)` 5.8 已建**零改动**——451 是段内取用非新开段）；基类 **`SystemException`**（漂移检测是系统侧可观测行为——AgentEvaluationError[450] 同族论证延续：检测管线编排失败的系统级语义面）；**文件落位**：`src/domain/exceptions/evaluation_exceptions.py` **追加**（子域单文件惯例——文件名=子域名[data_source/debate/tool_version/agent/evaluation 五代先例]；5.10 评估历史异常同文件续段）
- [ ] **唯一编码分配**：`DriftDetectionError` = EXCEPTION_451；`grep -r "EXCEPTION_451" src/domain/exceptions/` 验证无碰撞（调研实证：当前全仓零占用）
- [ ] **构造器参数设计**：`metric_name/phase/reason/message/cause/context_extra`（对齐 AgentEvaluationError 构造形态——phase 默认 "drift_detection"）；context dict 暴露 `{metric_name, phase, reason}`；reason 描述失败环节[invalid_state/degenerate_baseline]
- [ ] **消息安全性**：错误消息面向调用方可理解（不泄露内部统计量全序列——仅 phase/reason 语义面）
- [ ] **编码注册四件套**：①evaluation_exceptions.py 追加类定义（Google 风格全中文 docstring）；②`_code_ranges.py` `_CLASS_TO_SUBDOMAIN` 增 `DriftDetectionError → evaluation` 行（CODE_RANGES 表零改动 + 段注释更新[450 已占/451 已占注记]）；③`__init__.py` 导入 + `__all__`；④`EXCEPTION_HTTP_MAP` 451→500（SystemException 族惯例——**精确注册防回退歧义**[450 行 L284 注释先例原话]；R1 论证修正：fallback[SystemException isinstance + 默认 500 双路]本已兜底，显式注册是惯例而非功能必要）+ `tests/unit/interfaces/api/test_exception_handlers.py` expected_types 集合追加（L212 集合 + L355 穷举等值断言——不更新即 CI 红[R1 补]）；文档同步 sisys-uni-exception-design.md §3.3.2 编码分配表（**三步处方[R1 修正——原「插在 450 与 999 之间」漏预留行改写]**：L742 450 行后插 451 行 + **L743「EXCEPTION_451~459 预留」行收缩为 452~459** + 子域表 evaluation 行 ~L822「451-459 预留 5.9」注记同步改 452-459）；test_code_ranges.py 两表**无需增行**（直接继承 SystemException 抽象基类——450 同构先例两表零行且 CI 绿；_CLASS_TO_SUBDOMAIN 增行仍是必须[450 在 L306 有行先例]）
- [ ] **测试覆盖**：451 构造/code/context 三键/to_dict/HTTP 映射 500（追加 test_evaluation_exceptions.py）+ 编码唯一性（test_error_code_uniqueness 自动反射）+ 子域范围（test_code_ranges Rule 1-4）全绿
- [ ] **复用清单**：`ValidationError`（201——score 入参域守卫 + DriftAssessment 字段守卫，应用层输入校验）；降级网 catch 面（use case 评估块 catch 元组扩 451——三层降级网）
- [ ] BDD 验收场景：451 降级路径（AC-3.2）纳入验收 Edge Cases

#### API 契约 (API Contract)

- [ ] 本 Story 无 REST API / 无 CLI 命令（漂移检测是嵌入式可观测基础设施——5.7/5.8 同款定位）。`docs/api/openapi.yaml` 零改动
- [ ] 环境契约：`.env.example` **零改动**（无新环境变量——CUSUM 参数是代码常量[附录 I §29.7.2 配置管理 yaml 面不采用——MVP 常量单源，配置文件化 V1 按需]）

#### 六边形架构约束（必须遵守）

> 四层定义/零依赖原则/依赖方向矩阵同模板基线。本 Story 特别注意：

- [ ] `agent_drift.py`（端口 + DriftAssessment）在 application 层——**纯标准库零第三方**（Protocol + dataclass + 常量——agent_tracing/agent_evaluation 同款形态）
- [ ] `run_agent_workflow.py` 修改——新增 DriftDetectionPort/DriftDetectionError import（application 同层 + domain）合法；**禁止 import infrastructure**（检测器经端口注入）
- [ ] `cusum_detector.py` 在 infrastructure 层（monitoring/ 归口——architecture.md L2594 钦定 + §29.7.1 示例文件头同款）——实现 application 端口（infrastructure→application 依赖方向合法——5.8 UdmrEvaluationModelResolver 同款）；import DriftDetectionPort/DriftAssessment（application）+ EventPublisher（domain 端口）+ DriftDetected（domain 事件）合法；**纯标准库零第三方**（statistics/collections/math/dataclasses——OD-2）
- [ ] `drift_events.py` 在 domain/events——标准库零外部依赖（体系铁律；uuid/dataclasses/field——DomainEvent 基类同族）
- [ ] `evaluation_exceptions.py` 追加在 domain/exceptions——标准库零外部依赖；**domain 业务域触碰收窄**：events/drift_events.py（本 Story 新事件——白名单域）+ exceptions 三件（evaluation_exceptions.py/_code_ranges.py/__init__.py）；ports/services/entities/value_objects **零触碰**（AST 验证器断言）
- [ ] 接口层零改动（无 CLI/API 面）；组合根是唯一注册与实例化点

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_drift_detection.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_drift_detection.py`
- [ ] 场景组织：AC 注释横幅分组 + 全场景逐一 `@scenario` 显式绑定（多行字面量路径——R6 形态，禁 `scenarios()` 批量绑定与 then-pass 占位）；场景名 `AC-x.y - 中文描述`（feature 与 .py 逐字一致）；**禁 Background 背景块**（步骤化门控——本 Story 外部服务门控 = 零外部服务[纯内存检测器 + Fake LLM + 零 IO 手写替身]）；Gherkin Given 钉「检测器已装配」类前置步骤
- [ ] 14 场景规划（终态 = Task 0 编写 13 + Task 6 追加收尾 1；三属性分档表[组件级零服务/链级 OTel 通道/委托计时]Task 0.6 定稿落 docstring——**R1 补全归属**：AC-4 两场景=静态+接线档[零 OTel 全局触碰]、收尾×1=组件级零服务档）：
  - AC-1 ×3（组件级，零服务依赖——真实检测器手工构造 + 手算锚序列）：CUSUM 双侧累积和与预热基线（30 预热 + 漂移注入逐样本 Sₗ 演算 + 确认 severe down）/ N中M 确认与确认后复位（窗未满不确认 + **当前样本 F 不确认[(F,T,T,T,F)]/(F,T,T,F,T) 确认正形态**[R1 语义修正] + 复位后重新累积 + 基线保持）/ 无漂移对照与正向漂移 + degenerate 防御（交替序列不触发 + **up 方向[0.95×8 → moderate 锚]** + σ₀≈0 防线 + 入参域 201 守卫）
  - AC-2 ×3（组件级——真实检测器 + 手写零 IO publisher 替身）：trigger_recalibration 发布 DriftDetected 事件（字段真值 + 契约注册/aggregate/to_dict）/ 事件通道双登记契约（yaml + DEFAULT_MAPPINGS reliable 一致——reliable 版先例形态）/ 发布失败降级不阻断（替身抛异常 → logger.error 不上抛）
  - AC-3 ×3（链级——Fake LLM 手工装配 + 检测器预填充 + initialize 全局通道）：主链漂移检测执行与 drift.detected span 填值（OD-2[5.7] 兑现锚）/ 漂移检测降级不阻断主链（451 注入 → catch 扩 + 三键仍在 + warning）/ 构造签名七依赖与存量回归基线（None 兼容 + 断言同步 ×5——全量回归绿在 Task 6 收尾跑）
  - AC-4 ×2（静态 + 接线）：组合根接线（resolve 四件 + 工厂第七依赖 + CR1-DF2 降级防护 + 契约 11 维度）/ 架构静态扫描（AST 验证器承载形态：验收 .py 内联轻量版 + 全量验证器三件归 tests/unit/architecture/test_arch_drift_detection.py 双层承载）
  - AC-5 ×2（委托集成计时 + 合成回测）：检测延迟 P99<100ms（委托缓存命中）/ 合成序列回测准确率≥85%（委托回测缓存命中——同 _PERF_CACHE 形态扩展）
  - 收尾 ×1：完成清单逐项确认（src + tests 四目录——5.8 收尾同款）
- [ ] BDD 步骤约束：全部同步 `def` + `_run_async(context["_loop"], ...)`（禁 `@pytest.mark.asyncio`——context 数据丢失）；参数化步骤显式 `parsers.parse`；异常断言三段式（raises 捕获存 `context["caught"]` → then 断言 isinstance + code + context——451/201 场景）；**span 断言锚（5.7 SSOT 全文唯一口径）**：链级场景（AC-3 ×3）统一通道 = 场景级新 `TracerProvider + SimpleSpanProcessor + InMemorySpanExporter` 经 `PhoenixTracer(config=测试配置, tracer_provider=注入).initialize()` → 断言 → teardown 强制 `reset_for_testing()` 双复位（凡 initialize 一律双复位义务）；组件级场景（AC-1/AC-2）零全局触碰
- [ ] 显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.xdist_group("drift-detection-perf")]`（文件名不含服务关键词且零外部服务——无 redis/database marker）+ 延迟 import 纪律（本 Story 新交付模块一律在步骤函数体内 import——Task 0 红阶段逐场景 failed 非 collection error）
- [ ] teardown：span 面零资源（凡 initialize 场景 teardown 双复位 + exporter 清空）；计时/回测场景委托缓存防双跑；检测器状态零残留（每场景新实例——SINGLETON 污染防线）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——红形态钉死：13 场景逐一 failed[场景级延迟 import 的 ModuleNotFoundError/断言红]而非 collection error——5.8 Task 0 同款纪律）
- [ ] 规范文档通过人工评审或自动化校验
- [ ] **链路接线断言清单**已定义（Epic 4 回顾行动项 7.1-1）：①`agent_drift` 组合根 register_port 装配验证（resolve 可达 + isinstance + PortSpec + SINGLETON）②use case 工厂第七依赖注入确认（resolve("agent_workflow_use_case") 实例 `_drift_detector` 非 None——接线可达性）③主链漂移块静态锚（execute 体内 update 调用 + DRIFT_DETECTED 常量引用 + is_drifted 分支 + trigger_recalibration 调用——AST/inspect 扫描）④drift.detected span 落链验证（链级场景经 initialize 全局通道后 InMemory exporter 取到 drift.detected=True 真值——AC-3.1 场景承载）⑤DriftDetected 事件发布验证（trigger_recalibration → publish 调用 + 事件字段——AC-2.1 场景承载）+ 事件通道映射验证（双登记一致——AC-2.2 契约承载）

---

### TDD 循环约束（适用于每个 Task）

> 每 Task 依次执行 🔴红→🟢绿→🟡变异→🔄重构；变异实证 = 对新行为契约的断言改坏→红→还原→绿（Epic 4 行动项 7.1-2 强制）。禁止行为四条同模板基线。
>
> **套件型 Task 豁免条款**（Task 4 性能场景 / Task 5 架构验证 / Task 6 收尾场景）：验证型测试层首跑即绿——红由 Task 0 验收红阶段前置承担；断言活性由 🟡 变异实证强制（如：k 乘数改错→累积和手算断言红；确认阈值 3 改 5→确认用例红；drift.detected 写入删除→span 断言红；P99 常量突变→阈值断言红；漂移块删除→静态锚红）。

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| TDD 单元测试 | DriftDetectionError | 构造/code 451/context 三键/to_dict/HTTP 映射 500 | `tests/unit/domain/exceptions/test_evaluation_exceptions.py`（追加） | Task 1 |
| TDD 单元测试 | DriftDetected 事件 | 构造 kw_only/frozen/默认值/drift_id/aggregate/to_dict | `tests/unit/domain/events/test_drift_events.py` | Task 1 |
| TDD 单元测试 | DriftAssessment | 构造/字段域 201 守卫（越界/Literal 域/一致性）/frozen | `tests/unit/application/test_agent_drift_model.py` | Task 1 |
| TDD 契约测试 | agent_drift | 11 维度 + _DummyResolver（分发 event_publisher） | `tests/contracts/test_port_contract_agent_drift.py` | Task 2（R1 时序修正——impl 类交付后） |
| TDD 契约测试 | DriftDetected 事件 | 注册/aggregate_type/to_dict payload | `tests/contracts/test_event_contract_drift_events.py` | Task 1 |
| TDD 契约测试 | 事件通道映射 | yaml + DEFAULT_MAPPINGS 双登记逐字段一致 | `tests/contracts/test_event_channel_mapping_drift.py` | Task 1 |
| TDD 单元测试 | CUSUMDriftDetector | 预热/双侧累积和手算锚/N中M 确认/分级/复位/无漂移对照/正向漂移/degenerate/入参 201/常量单源 | `tests/unit/infrastructure/monitoring/test_cusum_drift_detector.py` | Task 2 |
| TDD 单元测试 | trigger_recalibration | 事件发布字段真值/发布失败降级/未确认不触发 | `tests/unit/infrastructure/monitoring/test_cusum_drift_detector.py`（同文件第二循环） | Task 3 |
| TDD 单元测试 | 主链漂移块 | use case 第七依赖/漂移块 span 填值/451 降级/评估降级联动/None 默认 | `tests/unit/application/use_cases/test_run_agent_workflow.py`（追加） | Task 3 |
| 集成测试 | 全链漂移检测 | 六阶段真实链 + 漂移确认 + drift.detected span 真值 + 事件发布 + P99 计时委托 + 合成回测准确率 | `tests/integration/test_integration_drift_detection.py` | Task 4 |
| SDD 架构验证 | 六边形约束 | application 零新第三方/domain 触碰白名单[含 events]/组合根外零实例化/依赖方向/主链静态锚/七依赖签名 | `tests/unit/architecture/test_arch_drift_detection.py` | Task 5 |
| TDD 验收测试 | Gherkin + BDD | 13 场景 Task 0 编写（收尾 Task 6 追加成 14 终态）；各 Task 转绿——AC-1 随 Task 2、AC-2 随 Task 1（模型面 + AC-2.2 通道契约）/3（发布面）、AC-3 随 Task 3、AC-4 随 Task 2（注册面——R1 时序修正）/3（接线面）/5、AC-5 随 Task 4 | `test_acceptance_drift_detection.feature/.py` | Task 0-6 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] 整体 ≥80%（P0 阻断）；**应用层 ≥85%**（agent_drift 端口 + use case 漂移块主战场——epics L1842「应用层覆盖率≥85%」）；infrastructure ≥75%（cusum_detector——epics L1843「集成测试覆盖率≥75%」按仓内门禁体系落为 infrastructure 层 ≥75%[`scripts/check_coverage_gates.py` L69]——5.7/5.8 口径映射注记同款）；domain ≥90% 维持（drift_events 新文件 + 451 追加全覆盖）；四档与 `scripts/check_coverage_gates.py` 一致
- [ ] 关键分支可执行口径：检测器三阶段分支（预热/检测/确认复位）+ degenerate 分支 + 入参域拒绝分支 + 漂移块四分支（None 跳过/确认写入/451 降级/评估降级联动跳过）+ 发布失败分支各配独立命名测试用例（用例名即分支清单）

#### 代码质量门禁

- [ ] `ruff check src/ tests/` + `mypy src/`（零新第三方依赖——零 stubs 新增需求；**use case 构造签名扩展后全仓 mypy**[5.8 教训：组件改签名后必须 mypy . 全仓]）+ `pre-commit run` 全过
- [ ] 三条红线自查零输出（`raise ValueError`/手动 `HTTPException`/继承内置 Exception——注意 score 域守卫必须 201 非 ValueError、DriftDetectionError 必须继承 SystemException 体系）+ 零抑制注释（noqa/type: ignore/pylint: disable 全禁）
- [ ] 提交信息零 AI 署名

#### 测试隔离约束

> 基线同模板。本 Story 特别注意：

- [ ] **检测器状态隔离（本 Story 最大隔离面——SINGLETON 有状态）**：单元/集成/验收全部**手工构造新实例**（不走 resolve——组合根 SINGLETON 仅接线断言消费[AC-4.1 isinstance 断言，不执行 update]）；场景内序列灌入经场景私有实例——零跨场景/零跨文件状态残留；链级场景预填充形态（34 样本 + execute 收尾样本）场景级独立装配
- [ ] **OTel 全局状态隔离（AC-3 链级场景 + 主链单测）**：凡 `initialize()` 一律「前置 reset 双复位 → act → teardown reset 双复位」（复位义务正交条款——5.7 SSOT）；已知同进程泄漏源 `tests/unit/infrastructure/monitoring/test_event_monitoring.py::TestInitTracing`——凡断言「全局未 set」前提的测试前置双复位；文件级 function-scope autouse 双复位 fixture 兜底（5.8 机制化形态）；**环境前提**：验收/集成进程 env 不带 `PHOENIX_TRACING_ENABLED=true`（场景级 monkeypatch.delenv 钉死）
- [ ] **本 Story 零外部服务依赖**：无 Redis/PG/RabbitMQ/LLM API 硬依赖（漂移检测纯内存算法 + Fake LLM + 零 IO 手写替身——Outbox/RabbitMQ 真实投递不在测试面[通道映射经契约测试双登记断言承载]；5.8 先例边界延续）；验收禁 mock 红线豁免面 = llm_client（外部 SaaS——5.3 先例）+ 零 IO 事件替身（手写 duck-typing 类——_RecordingEventPublisher 15 文件先例（R1 计数修正））+ 单测层 AsyncMock spec（tests/unit 合规面——漂移块 use case 单测的 Fake drift port）
- [ ] **浮点断言纪律（CUSUM 累积和必循——R1 修正）**：全部数值断言用同式 Python 表达式（**钦定形态 `(0.8 - 0.5*sigma0 - 0.4) * n`——σ₀ 经 statistics.stdev(baseline) 实算；禁 `0.8 - 0.05 - 0.4` 类把 k 写死 0.05 的形态[k=0.5σ₀≈0.0509，字面形态必假红]；禁 pytest.approx——仓内无 approx 先例，纪律是精确等式+同式表达式[test_evaluation_harness.py L433-446 锚]**）——禁十进制字面量（5.8 R3-F1 教训：组合链实算 0.7000000000000001 类假红）；手算锚序列选二进制安全值对优先（0.35 累积非精确——一律同式表达）
- [ ] **pytest-xdist 计时组**：`xdist_group("drift-detection-perf")` 与既有 13 组互异（全仓 grep 断言——AC-5 验证标准清单）；`_PERF_CACHE` 委托缓存（P99 采样 + 回测矩阵双委托槽——key 分立）+ benchmark 场景级标记；P99/回测常量单源（集成定义/验收 import）
- [ ] BDD 步骤禁 `@pytest.mark.asyncio`；步骤函数同步 def + `_run_async` 调度；模块级 event_loop fixture（5.8 显式定义形态）
- [ ] **5-3/5-7/5-8 存量回归**：use case 构造签名扩展（第七可选依赖 None 默认——存量六参构造零破坏）+ 存量断言同步 ×5 更新后三家全家回归绿——回归清单 Task 3 登记

**验证要求：** `pytest tests/` 通过（仓库默认 `-n auto --dist loadgroup`）；连续 5 次无随机失败；`ruff check` + `mypy`（全仓）通过；5-3/5-7/5-8 全家回归绿；异常体系 CI 测试（test_code_ranges/test_error_code_uniqueness/test_exception_handlers）全绿。

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 预热基线 + 双侧累积和手算锚 | Task 2 | 检测器预热/累积实现 | test_cusum_drift_detector + 验收 AC-1.1 |
| AC-1 | N中M 确认 + 分级 + 确认后复位 | Task 2 | 确认机制/复位实现 | 同上 + 验收 AC-1.2 |
| AC-1 | 无漂移对照 + 正向漂移 + degenerate + 201 守卫 | Task 2 | 防御面实现 | 同上 + 验收 AC-1.3 |
| AC-2 | DriftDetected 事件模型 + 发布字段真值 | Task 1（模型）/ Task 3（发布） | 事件定义 + trigger 实现 | test_drift_events + test_cusum_drift_detector + 验收 AC-2.1 |
| AC-2 | 事件通道双登记契约 | Task 1 | yaml + DEFAULT_MAPPINGS | test_event_channel_mapping_drift + 验收 AC-2.2 |
| AC-2 | 发布失败降级不阻断 | Task 3 | 发布降级 catch | test_cusum_drift_detector + 验收 AC-2.3 |
| AC-3 | 主链漂移块 + drift.detected span（OD-2[5.7] 兑现） | Task 3 | use case 漂移块 | test_run_agent_workflow（追加）+ 验收 AC-3.1 |
| AC-3 | 451 降级 + 评估降级联动 + None 默认 | Task 3 | 降级网扩 | 同上 + 验收 AC-3.2 |
| AC-3 | 构造签名七依赖 + 断言同步 ×5 + 存量回归 | Task 3 | 七依赖 + 回归清单 | 同上 + 验收 AC-3.3 |
| AC-4 | 组合根注册 + 工厂第七依赖 + CR1-DF2 防护 + 契约 ×3 | Task 2（注册 + 端口契约——R1 时序修正）/ Task 1（事件契约 + 通道映射）/ Task 3（工厂注入——R1-F1[5.8] 时序同款） | 注册 + 契约测试 | 契约 ×3 + 验收 AC-4.1 |
| AC-4 | 架构静态扫描（白名单/domain 白名单域含 events/静态锚） | Task 5 | AST 三验证器 | test_arch_drift_detection + 验收 AC-4.2 |
| AC-5 | 检测延迟 P99<100ms（委托计时） | Task 4 | P99 委托 helper | 集成 + 验收 AC-5.1 |
| AC-5 | 合成序列回测准确率≥85% | Task 4 | 回测矩阵 | 集成 + 验收 AC-5.2 |
| 全 AC | 收尾清单 | Task 6 | 完成清单场景 | 验收收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则**同模板。每 Subtask 组内按领域粒度拆分红绿循环。

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部

- [ ] Subtask 0.1: 定义数据模型规范——DriftAssessment（frozen 十字段 + 201 域/Literal/一致性守卫）+ CUSUM 参数六常量（本文件「数据模型」节为唯一真源）
- [ ] Subtask 0.2: 定义端口契约——DriftDetectionPort（update + trigger_recalibration[**含 agent_id 透传参数与 is_drifted 零发布守卫——R1 裁定落端口定义，取消原「二选一」悬空**]）+ 组合根注册元数据 + 契约变更登记 ×1（use case 第七依赖——含存量断言同步 ×5 全清单）+ 命名甄别（vs MetricsPort 计量语义分立）
- [ ] Subtask 0.3: 定义异常契约——DriftDetectionError（451，evaluation_exceptions.py 追加 + 注册四件套）+ 复用清单（201）+ 降级网 catch 扩登记
- [ ] Subtask 0.4: 定义领域事件规范——DriftDetected（kw_only 十二字段[含 agent_id——R1 新增] + aggregate_type="AgentEvaluation"）+ 通道双登记条目（reliable）+ 发布失败降级纪律
- [ ] Subtask 0.5: 定义性能双锚口径——P99 纯内存检测管线（100 采样 quantiles[98] + 常量单源 + 正向锚）+ 合成回测（**R1 参数定稿**：固定种子 40 序列 × 60 样本[30 基线 uniform(0.7,0.9) + 30 评估段；漂移 delta=uniform(0.3,0.5)] + (TP+TN)/40 ≥0.85[钦定种子基准 acc=0.975] + 分项计数 + 评估段长 30 禁拉长）
- [ ] Subtask 0.6: 编写 Gherkin `test_acceptance_drift_detection.feature`（13 场景）+ BDD 步骤实现 `.py`（@scenario 全显式绑定 + context dict fixture + 链级 initialize 全局通道 fixture + 检测器预填充 fixture + Fake LLM 手工装配链 fixture + 文件级 autouse 双复位兜底 + **模块级 event_loop fixture 与 _run_async 自备**[R1 注记：conftest 不提供——26/16 处先例均各文件自定义，照 5-8 验收 L53/L88 形态]）+ **13 场景三属性分档表**定稿（docstring）
- [ ] Subtask 0.7: 运行验收测试确认失败（🔴 红阶段——红形态钉死：13 场景逐一 failed 非 collection error）+ **deferred-work.md 处置注记 ×4**（OD-2[5.7] drift.* 兑现闭环[条目核销] + R1-DF3[5.7] 不触发锚位继续顺延 + CR1-DF2[5.8] 本 Story 采纳核销 + 5-2 R1-DF1 ACTIVE 基线消费面核销评估[来源 deferred-work L181——条目原文点名「5.9 漂移检测立项[ACTIVE 基线数消费该面]」为触发候选；R1 预评：5.9 实际消费 overall_score 评估序列、不触碰 skills L1 缓存——**预期结论=不触发锚位顺延**，核销注记如实登记]）+ **本 Story V1 升级通道登记**（V1-EV9 多指标逐键检测 + V1-EV10 滑动基线/定期更新/季节性调整 + V1-EV11 自动重校准[模型配置变更——依赖漂移归因 + UDMR 运行时配置面] + V1-EV12 检测器状态 Redis 持久化[重启存活——随 5.10/监控域评估] + V1-EV13 序列缺口计数器[评估降级缺口可观测——5.8 风险 #6②] + V2-EV1 真实历史数据回测[数据积累后]——gap 四要素齐备）+ 本 Story OD-1~OD-7 知悉登记（OD-1/OD-2 命名/依赖裁定不进台账[5-8 OD-1 同款]；OD-3~OD-7 设计裁定不进台账[非 gap——规范不可行面的必要裁定]）
- [ ] Subtask 0.8: 移交留项处置落盘（前置依赖表四项逐一登记处置结果）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义；验收测试红阶段确认（13 场景逐一 failed）；链路接线断言清单 L1-L5 定义

---

### Task 1: DriftDetectionError + DriftAssessment/端口 + DriftDetected 事件 + 通道双登记 + 事件契约 ×2（组合根注册与端口契约归 Task 2——R1 时序修正）

**关联 AC:** AC-2（模型面 + 通道契约）、AC-1（DriftAssessment 模型面单测）

#### TDD 循环 A：DriftDetectionError（evaluation 段 451 取用）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_evaluation_exceptions.py` 追加 451 用例（构造 metric_name/phase/reason context 三键 / code == "EXCEPTION_451" / to_dict 序列化 / message 默认与自定义 / HTTP 映射 500——EXCEPTION_HTTP_MAP 注册断言） |
| 🟢 绿 | `src/domain/exceptions/evaluation_exceptions.py` 追加 DriftDetectionError + `_code_ranges.py` _CLASS_TO_SUBDOMAIN 增行 + 段注释更新 + `__init__.py` 导出 + `exception_handlers.py` 451→500 + **`tests/unit/interfaces/api/test_exception_handlers.py` expected_types 集合追加 DriftDetectionError**（L212 集合 + L355 穷举等值断言——不更新即 CI 红[R1 补]） |
| 🟡 变异 | code 改 "EXCEPTION_452"→唯一性测试红（自动反射）；_CLASS_TO_SUBDOMAIN 行删除→test_code_ranges 红；还原→绿 |
| 🔄 重构 | Google 风格全中文 docstring（触发场景/Raises 契约）+ sisys-uni-exception-design.md §3.3.2 编码分配表同步（**三步处方**：插 451 行 + 预留行收缩 452~459 + 子域表注记——见异常契约节[R1 修正]）+ ruff+mypy |

#### TDD 循环 B：DriftDetected 事件 + DriftAssessment + 端口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/events/test_drift_events.py`（构造 kw_only 必填 / frozen 不可变 / drift_id 自动生成 / recommended_action 默认 "manual_review" / aggregate_type=="AgentEvaluation" / DomainEvent._registry 注册断言 / to_dict payload 含业务字段）+ `tests/unit/application/test_agent_drift_model.py`（DriftAssessment 构造 / observed_value 越界参数化→201 三段式 / bool 拒 / cusum 负值→201 / Literal 域外→201 / 一致性守卫[is_drifted=False + level≠none→201] / frozen / 双端口 REQUIRED_METHODS callable 断言） |
| 🟢 绿 | 实现 `src/domain/events/drift_events.py` + `src/application/ports/agent_drift.py`（DriftAssessment + DriftDetectionPort——纯标准库）+ 两处 `__init__.py` 导出（domain/events + application/ports） |
| 🟡 变异 | 201 守卫删除→越界用例红；aggregate_type 改错→事件契约红；event_type init=False 改普通默认→注册断言红；还原→绿 |
| 🔄 重构 | docstring（字段语义对照表[OD-5/OD-7 锚] + 端口命名甄别注记）+ ruff+mypy |

#### TDD 循环 C：通道双登记 + 事件契约 ×2（组合根注册与端口契约移 Task 2——R1 时序修正：端口契约维度 9b `spec.impl(_DummyResolver())` 真实构造 impl 类、维度 10 调其方法[5-8 契约先例 L107-110]，CUSUMDriftDetector 归 Task 2，Task 1 落注册/端口契约必红）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/contracts/test_event_channel_mapping_drift.py`（yaml 与 DEFAULT_MAPPINGS 双处存在 + rabbitmq_routing_key 两处一致 =="sisys.events.reliable.drift_detected" + delivery_mode 两处 =="reliable"——reliable 版先例形态）+ `test_event_contract_drift_events.py`（注册/aggregate/to_dict 三断言）（`test_port_contract_agent_drift.py` 归 Task 2——impl 类未交付时维度 9b/10 必红） |
| 🟢 绿 | `configs/event_channels.yaml` 增 DriftDetected 条目 + `channel_router.py` DEFAULT_MAPPINGS 增 ChannelMapping（**组合根注册移 Task 2**；use case 工厂本 Task 不动——第七构造参数 Task 3 才交付，提前注入 kwarg 必 TypeError[5.8 R1-F1 时序同款]） |
| 🟡 变异 | yaml 条目删除→映射契约红；routing_key 拼写错→一致断言红；还原→绿（注册名变异随 Task 2 端口契约轮） |
| 🔄 重构 | 通道条目设计注释（reliable 单通道依据 + 命名惯例锚）+ ruff+mypy |

- [ ] Subtask 1.1: 🔴 红 — DriftDetectionError 451 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 异常注册四件套
- [ ] Subtask 1.3: 🟡 变异 — code/子域注册突变实证
- [ ] Subtask 1.4: 🔴 红 — 事件 + DriftAssessment + 端口失败测试
- [ ] Subtask 1.5: 🟢 绿 — drift_events.py + agent_drift.py 实现
- [ ] Subtask 1.6: 🟡 变异 — 守卫/注册突变实证
- [ ] Subtask 1.7: 🔴🔴🟢 — 通道双登记 + 契约 ×2（事件契约 + 通道映射；端口契约与组合根注册归 Task 2、use case 工厂归 Task 3——R1 时序约束）
- [ ] Subtask 1.8: 🔄 重构 — 导出/docstring/编码分配表（三步处方）/门禁

**完成标准/Definition of Done:**
- [ ] 异常/事件/端口文件/通道双登记四件交付（组合根注册随 Task 2——R1 时序修正）；事件契约 + 通道映射契约 ×2 全绿；异常体系 CI 全绿（含 expected_types 伴随更新）；验收 AC-2.2 转绿（AC-4.1 注册面随 Task 2、AC-1.1 检测器面随 Task 2——DriftAssessment 模型面单测本 Task 绿）

---

### Task 2: CUSUMDriftDetector 核心 + 组合根注册 + 端口契约（R1 归位）——双侧累积和 + 预热基线 + N中M 确认[含当前样本条件] + 分级 + 复位

**关联 AC:** AC-1（全部算法面）、AC-4.1（注册面 + 端口契约）

#### TDD 循环 A：预热基线 + 双侧累积和 + 手算锚

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/monitoring/test_cusum_drift_detector.py` 循环 A 用例（预热期：前 30 样本 baseline_ready=False + sample_count 递增 + baseline_mean/std 预热统计手算对照[statistics.mean/stdev；**N=1 时 baseline_std=0.0 断言——R1 钉死**] / 第 31 样本起 baseline_ready=True + 基线冻结断言[后续样本 baseline_mean 不变] / 双侧累积和手算锚：`[0.7,0.9]×15` 基线[σ₀=statistics.stdev 实算 ≈0.1017] + 样本 31-35 全 0.4 → 逐样本 Sₗ 断言 ≈0.349/0.698/1.047/1.397/1.746[**钦定同式表达式 `(0.8 - 0.5*sigma0 - 0.4) * n`——禁字面量、禁 approx（仓内无 approx 先例——精确等式纪律）**] / Sₕ 对称锚 / detection 判定 S>h 严格大于[上漂 0.95×5 处 Sₕ≈0.496<h≈0.509 余量 2.5% 不触发——R1 修正：非「0.50 边界」形态] / 常量单源六项断言） |
| 🟢 绿 | 实现 `src/infrastructure/monitoring/cusum_detector.py`（模块常量 + CUSUMDriftDetector 类：构造器 event_publisher 注入 + 内部状态[基线窗 deque/Sₕ/Sₗ/确认窗 deque/样本计数] + update 预热/检测两阶段 + 双侧公式 + DriftAssessment 构造） |
| 🟡 变异 | K_MULTIPLIER 0.5 改 0.6→累积和手算断言红；max(0,...) 删负累积→复位特性红；预热阈值 30 改 29→baseline_ready 断言红；还原→绿 |
| 🔄 重构 | docstring（三阶段流程图 + 附录 I 公式锚 + OD-3/OD-5 裁定注记 + 5.8 风险 #6④ 可达域/多峰知悉）+ ruff+mypy |

#### TDD 循环 B：N中M 确认 + 分级 + 确认后复位 + 防御面

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 追加循环 B 用例（N中M：确认窗未满 5 不确认[s32-s34 detection True 但 is_drifted=False] / s35 确认（F,T,T,T,T 计数 4≥3 **且当前样本 T**——当前样本条件[R1]）/ 边界参数化（**F,T,T,T,F→不确认[当前样本 F]**；F,T,T,F,T→确认[计数 3+当前 T]；F,T,T,F,F→不确认）/ 分级：s35 ratio=`(0.8-0.5*sigma0-0.4)*5/sigma0`≈17.2>8→severe[同式表达] / moderate 档构造[**0.62×10 锚——R1 实测**：s36 确认、ratio≈7.6→moderate] / 复位：确认后 S 归零断言 + 确认窗清空 + 基线保持[baseline_mean 相等] + 后续样本重新累积 + **再确认间隔锚**[复位后 0.4 续灌 5 样本再确认——OD-5① 实测] / 无漂移对照：交替序列续灌 10 样本恒不触发 + S 有界 / 正向漂移：**0.95×8 → up 确认 moderate**[s38 确认、Sₕ≈0.793、ratio≈7.80——R1 修正：原 0.95×6 不可确认] / degenerate：[0.8]×30 基线后 0.4 注入 → 恒不判定 + sample_count 递增 / 入参域：-0.01/1.01/True/"0.8" 参数化→201 三段式） |
| 🟢 绿 | 实现确认窗逻辑（含当前样本 detection 条件）+ _determine_direction + _determine_severity + 复位 + degenerate 防御 + score 域守卫 |
| 🟡 变异 | CONFIRMATION_N 3 改 5→边界用例红；**当前样本 detection 条件删除→(F,T,T,T,F) 边界用例红[确认发生在 F 样本——R1 新增变异锚]**；确认后复位删除→重新累积断言红[后续样本 S 从旧值续累]；severity 阈 8 改 6→severe 用例红；还原→绿 |
| 🔄 重构 | docstring（确认机制 §29.3.2.2 锚 + 复位语义 OD-5 锚）+ ruff+mypy |

#### TDD 循环 C：组合根注册 + 端口契约（R1 自 Task 1 移入——impl 类本 Task 已交付，契约维度 9b/10 可达）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/contracts/test_port_contract_agent_drift.py`（11 维度[5-8 形态：注册可达/名称/版本/接口类型/生命周期/owner/module 路径/tags/impl 可调用/impl 产出端口实例+类名/方法齐备] + `_DummyResolver` **加 event_publisher 分发分支**[扩展非照抄——先例仅 llm_client/evaluation_model_resolver 两分支，llm_client 双分发先例可循]） |
| 🟢 绿 | 组合根 `# === Story 5.9 ===` 区段 agent_drift 注册（v1.0.0 / DriftDetectionPort / lambda `CUSUMDriftDetector(event_publisher=resolver.resolve("event_publisher"))` / module=src.infrastructure.monitoring.cusum_detector / SINGLETON / owner=platform / tags=("agent","drift","observability")——use case 工厂仍不动[Task 3 同窗]） |
| 🟡 变异 | 注册名拼写错→契约维度 1 红；lifetime 改 TRANSIENT→生命周期维度红；还原→绿 |
| 🔄 重构 | 注册区段设计注释（SINGLETON 有状态依据[DC-6] + lambda 依赖清单）+ ruff+mypy |

- [ ] Subtask 2.1: 🔴 红 — 预热/累积/手算锚失败测试
- [ ] Subtask 2.2: 🟢 绿 — 检测器最小实现
- [ ] Subtask 2.3: 🟡 变异 — 常量/公式突变实证
- [ ] Subtask 2.4: 🔴 红 — 确认/分级/复位/防御失败测试
- [ ] Subtask 2.5: 🟢 绿 — 确认机制实现
- [ ] Subtask 2.6: 🟡 变异 — 确认/复位/分级突变实证
- [ ] Subtask 2.7: 🔄 重构 — docstring/门禁
- [ ] Subtask 2.8: 🔴🟢🟡 — 组合根注册 + 端口契约 11 维度（R1 自 Task 1 移入——_DummyResolver 扩 event_publisher 分支）

**完成标准/Definition of Done:**
- [ ] CUSUMDriftDetector 三循环全绿（算法/确认/注册契约）；组合根注册 + 端口契约 11 维度全绿；验收 AC-1.1/1.2/1.3 + AC-4.1 注册面转绿（接线面随 Task 3）；infrastructure 覆盖率 ≥75% 主战场达标面

---

### Task 3: trigger_recalibration 事件发布 + 主链第七依赖 + 漂移块 + 5-3/5-7/5-8 存量回归

**关联 AC:** AC-2（发布面全部）、AC-3（全部）、AC-4.1（接线面）

#### TDD 循环 A：trigger_recalibration（事件发布 + 降级）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 追加 `test_cusum_drift_detector.py` 循环 C 用例（手写 `_RecordingEventPublisher` 替身：trigger_recalibration(确认 assessment, agent_id="agent-x") → publish 单次调用 + 事件 isinstance DriftDetected + metric_name/direction/level/cusum/基线/observed_value/sample_count 与 assessment 逐字段相等 + recommended_action=="manual_review" + **agent_id=="agent-x" 透传断言 + agent_id=None 默认透传 None**[R1 新增] / **未确认 assessment 注入[is_drifted=False]→零发布断言**[替身零捕获 + returns None——R1 裁定：trigger 内 is_drifted 守卫与调用方守卫双保险，取消原「二选一」悬空；防 level="none" 泄入事件] / 替身 publish 抛 RuntimeError → 不上抛 returns None + caplog error 断言） |
| 🟢 绿 | 实现 trigger_recalibration（is_drifted 守卫 → assessment+agent_id → DriftDetected 构造[metric_name=METRIC_NAME, agent_id 透传] → try publish → publish_result.is_success 检查 → except Exception logger.error 降级） |
| 🟡 变异 | 事件字段装配错位[cusum_high/low 互换]→字段断言红；降级 catch 删除→RuntimeError 上抛用例红；还原→绿 |
| 🔄 重构 | docstring（OD-6 人工介入单通道锚 + 发布失败不阻塞先例锚）+ ruff+mypy |

#### TDD 循环 B：use case 第七依赖 + 漂移块 + 降级网扩 + 断言同步 ×5

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/application/use_cases/test_run_agent_workflow.py` 追加（**类级 function-scope autouse initialize 通道 fixture——5.8 TestExecuteEvaluationBlock 同文件同形态镜像**）：注入真实检测器（预填充 34 样本）+ Fake LLM（幻觉分注入使 overall 落 0.4 邻域）→ execute → agent_execution span attributes["drift.detected"] is True + 替身 publisher 捕获 DriftDetected / Fake drift port[AsyncMock spec] update 抛 DriftDetectionError → 主链正常返回 + eval 三键仍在 + drift.detected 缺席 + caplog warning / Fake LLM 幻觉分支抛 LLMAPIError → drift port update 零调用断言[调用计数] / 六参构造（None 默认）→ 行为与 5.8 基线一致 + 漂移块零执行 / 七依赖签名断言（inspect.signature） |
| 🟢 绿 | `run_agent_workflow.py`：第七可选依赖 + 评估块内漂移块（None 守卫 → update → is_drifted 分支 → DRIFT_DETECTED 写入[is_recording 守卫] → trigger_recalibration[**agent_id=agent_id 透传——R1**]）+ catch 元组扩 DriftDetectionError + **组合根工厂更新**（`_build_agent_workflow_use_case` 追加 resolve_optional("agent_drift") 第七依赖——与第七参数同窗落地[时序约束]）+ **存量断言同步 ×5 全清单**（R1 实证）：①test_acceptance_phoenix_tracer.py AC-4.3 基线（L1367-1377）②test_arch_phoenix_tracer.py `_USE_CASE_INIT_PARAMS`（L101-108）③test_arch_evaluation.py 六依赖基线（L54-61）④test_run_agent_workflow.py `test_constructor_sixth_param_default_none`（L683-693）⑤test_acceptance_agent_evaluation.py AC-3.3 清单断言（L1308-1328）——**①②保留 `"evaluation_harness",  # Story 5.8 第六可选依赖` 字面行原样、仅尾部追加 `"drift_detector",  # Story 5.9 第七可选依赖` 行**（5.8 验收 L1368/1370/1773/1774 回执文本断言锁死该行[R1 回执耦合防线]）；核验 `grep -rn "inspect.signature(RunAgentWorkflowUseCase\|inspect.signature(use_case_cls" tests/` 五处直命中 |
| 🟡 变异 | DRIFT_DETECTED 写入删除→span 断言红；漂移块 catch 未扩 451[元组回退两元素]→451 注入用例红[主链击穿]；None 守卫删除→六参构造用例红；还原→绿 |
| 🔄 重构 | 漂移块注释（OD-2[5.7] 兑现注记 + 三层降级网 + 序列缺口跳过策略锚）+ ruff+mypy（**全仓 mypy——构造签名扩展**[5.8 教训]） |

#### TDD 循环 C：5-3/5-7/5-8 存量全家回归

| 阶段 | 动作 |
|------|------|
| 🔴→🟢 | 回归绿清单执行：**5.3 全家**（test_agent_workflow_service 存量 + 契约×3 + 图/引擎单测×2 + 集成 + 验收[含 Fake 分派表]）+ **5.7 全家**（单测×3 + 契约 + test_arch_phoenix_tracer[资产同步②更新后] + 集成 + 验收 15 场景[AC-4.3 更新后]）+ **5.8 全家**（单测×4 + 契约×2 + test_arch_evaluation[资产同步③更新后] + 集成 + 验收 13 场景）——第七可选依赖 None 默认 + 漂移块 None 守卫使存量零破坏预期全绿；**异常项逐一登记**（实施时以实际清单为准甄别修复——适配器契约变更回归面纪律） |

- [ ] Subtask 3.1: 🔴 红 — trigger_recalibration 失败测试
- [ ] Subtask 3.2: 🟢 绿 — 事件发布 + 降级实现
- [ ] Subtask 3.3: 🟡 变异 — 字段装配/降级突变实证
- [ ] Subtask 3.4: 🔴 红 — 主链漂移块失败测试（五面：确认/451 降级/评估降级联动/None/签名）
- [ ] Subtask 3.5: 🟢 绿 — 第七依赖 + 漂移块 + catch 扩 + 断言同步 ×5
- [ ] Subtask 3.6: 🟡 变异 — span 写入/降级网/守卫突变实证
- [ ] Subtask 3.7: 🟢 — 5-3/5-7/5-8 存量全家回归绿（清单登记）
- [ ] Subtask 3.8: 🔄 重构 — docstring/全仓门禁

**完成标准/Definition of Done:**
- [ ] trigger_recalibration + 主链漂移块交付；验收 AC-2.1/2.3 + AC-3 ×3 + AC-4.1 接线面转绿；三家存量零回归；组合根工厂接线完整生效

---

### Task 4: 集成测试与性能——全链漂移 + P99 + 合成回测

**关联 AC:** AC-5（全部）、AC-3（集成面）

> 性质说明：本 Task 对 Task 1-3 已交付链编写验证型测试（套件型豁免——红由 Task 0 前置，活性由变异保证）。

- [ ] Subtask 4.1: 编写 `tests/integration/test_integration_drift_detection.py`（Fake LLM 手工装配六阶段链 + 真实 CUSUMDriftDetector[手写零 IO publisher 替身] + 链级 initialize 全局通道[场景级 reset 双复位 → initialize → 断言 → teardown 双复位]）：场景① 全链漂移确认（检测器预填充 34 样本 + execute[幻觉分注入 overall 0.4 邻域] → 根 span drift.detected is True + 键字符串逐字对照 + DriftDetected 事件发布 + direction=="down"）② 无漂移对照（预填充 + execute[正常 overall] → drift.detected 缺席 + 事件零发布 + eval 三键正常——5.8 回归锚）③ 451 降级链（drift port 替身注入抛 DriftDetectionError → 主链正常 + 三键在 + drift 缺席 + warning）④ None 路径对比（六参构造 → 与 5.8 基线 span 树等价）⑤ P99<100ms（`_PERF_CACHE["p99"]` + warmup 1 + 100 采样 + 每采样完整 update[检测器预填充至检测态] + `statistics.quantiles(latencies, n=100)[98]` exclusive P99 + 正向锚[update 调用计数 == 101] + `DRIFT_P99_LIMIT_SECONDS = 0.1` 常量单源 + benchmark 场景级标记）⑥ 合成回测准确率（**R1 参数定稿**：`random.Random(20261028)` 生成 40 序列[前 20 稳定/后 20 漂移按序]，每条 60 样本 = 30 基线期 uniform(0.7,0.9) + 30 评估期[稳定同分布续灌/漂移先抽 delta=uniform(0.3,0.5) 再 uniform(0.7-delta,0.9-delta)——全部样本天然 [0,1] 域，禁未截断正态] + 每序列独立检测器全序列灌入 + TP/FP/TN 统计 + `(TP+TN)/40 ≥ 0.85`[钦定种子基准 TP=20/FP=1/acc=0.975] + 分项计数断言消息 + 评估段长 30 禁拉长 docstring 注记 + `_PERF_CACHE["backtest"]` 委托 + 确定性[同种子两次生成相等断言]）
- [ ] Subtask 4.2: 变异实证——K_MULTIPLIER 改错→场景①手算断言红；drift.detected 写入删除→场景①红；P99 常量突变（0.1→0.000001）→场景⑤红；回测漂移注入幅度归零→场景⑥准确率塌缩红；还原→绿
- [ ] Subtask 4.3: 验收 AC-5.1/5.2 场景转绿（委托缓存命中验证——双委托槽）+ AC-3 集成对应场景转绿

**完成标准/Definition of Done:**
- [ ] 集成六场景全绿；P99 达标（μs~ms 级预期——100ms 裕量充足）；回测准确率 ≥0.85 实测；xdist 组与既有 13 组不冲突；验收对应场景全绿

---

### Task 5: SDD 架构约束验证测试

**关联 AC:** AC-4.2

> 性质说明：SDD 规范验证测试（验证架构约束是否被遵守），非 TDD 单元测试。

- [ ] Subtask 5.1: 创建 `tests/unit/architecture/test_arch_drift_detection.py`——验证器 A：application 触碰文件（agent_drift.py / run_agent_workflow.py / application/ports/__init__.py）第三方 import 白名单（**零新增第三方断言**——本 Story application 触碰面纯标准库 + 既有 opentelemetry；黑名单新第三方零引入）；验证器 B：domain 触碰白名单域（_STORY59 业务符号[CUSUMDriftDetector/DriftDetectionPort/DriftAssessment]在 domain/ports|services|entities|value_objects 零命中[词边界正则] + **DriftDetected 允许在 domain/events 命中**[本 Story 与 5.8 的差异面——白名单域] + DriftDetectionError 仅在 domain/exceptions 三件内命中）+ 组合根外零实例化（CUSUMDriftDetector( 构造点仅 composition_root.py + tests/）+ 依赖方向（cusum_detector.py import src.application/src.domain 断言——infrastructure→application/domain 合法面锚定）+ drift_events.py/evaluation_exceptions.py 标准库零外部依赖断言；验证器 C：主链漂移块静态锚（execute 体内 update 调用 + DRIFT_DETECTED 常量引用[ast.Attribute.attr 与 ast.Name.id 双形态——5.8 R3 钉死] + is_drifted 分支 + trigger_recalibration 调用在位——AST/inspect 扫描）+ use case 七依赖签名基线（inspect.signature 对照——第七参数默认 None）+ cusum_detector.py 标准库零外部依赖断言（OD-2 实现面证据——numpy/scipy 零引入）
- [ ] Subtask 5.2: 变异实证——cusum_detector.py 注入 numpy import→验证器 A/B[零外部依赖断言]红；domain/services 下放置检测器符号→验证器 B 红；漂移块 DRIFT_DETECTED 引用删除→验证器 C 红；还原→绿
- [ ] Subtask 5.3: 零抑制注释验证器（本 Story 触碰文件七件零 noqa/type: ignore/pylint: disable——test_arch_evaluation.py TestArchNoSuppressionComments 同款）

**完成标准/Definition of Done:**
- [ ] 架构/约束测试全绿；任何违规都会导致测试失败；验证器 B 白名单域含 events（与 5.8 验证器的 domain 零 events 触碰断言形成本 Story 差异锚）

---

### Task 6: 开发结束验收测试

**关联 AC:** 全部

> 性质说明：本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/acceptance/test_acceptance_drift_detection.feature` 中的收尾验收场景 |
| 🟢 绿 | 编写 `tests/acceptance/test_acceptance_drift_detection.py` 的收尾 BDD 步骤实现 |
| 🔄 重构 | 收敛场景命名、统一断言表达、保持步骤函数可维护性 |

- [ ] Subtask 6.1: 场景 1 — 验证 `src` 完成清单的逐项确认（检测器/端口/事件/异常/组合根/通道双登记 + 修改文件清单锚[run_agent_workflow.py 漂移块文本锚——5.8 收尾同款 `"drift_detector",  # Story 5.9 第七可选依赖` 形态]）
- [ ] Subtask 6.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单的逐项确认（**十件新建[.feature/.py 分计] + 六件存量触碰更新文本锚——R1 计数修正**：断言同步 ×5 全部 + test_exception_handlers expected_types + test_evaluation_exceptions 451 追加）
- [ ] Subtask 6.3: 运行开发结束验收测试并确认通过（14 场景全绿）
- [ ] Subtask 6.4: 运行 `pytest tests/`（全量回归 + 连续 5 次无随机失败）、`ruff check`、`mypy .`（全仓）进行收尾校验 + 覆盖率四档门禁（scripts/check_coverage_gates.py）+ 三红线自查零输出
- [ ] Subtask 6.5: 文档终态四件——architecture.md §14.4 交付注记（Story 5.9 漂移检测面）+ sisys-core-domain-design.md §17.3.8 实现注记（OD-3~OD-7 裁定映射）+ deferred-work.md（处置注记 ×4 + V1/V2 通道登记核验）+ sprint-status.yaml 状态流转（in-progress → review）

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests` 四目录完成清单已逐项验证确认
- [ ] 开发结束验收测试通过（14 场景全绿）
- [ ] Story 可进入 `review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ 漂移检测即端口（DriftDetectionPort 应用契约[R2]——EventPublisher[R1 domain 基础端口]组合注入 + CUSUMDriftDetector infrastructure 实现[R3——可替换 Redis 持久化/多指标]）+ 可观测附加面（漂移检测降级哲学——5.7 DC-7/5.8 DC-5 延续：三层降级网）
- **设计约束:** 领域层零依赖（drift_events/exceptions 标准库）；`.importlinter` application-no-infrastructure（检测器在 infrastructure 实现 application 端口——依赖方向矩阵 infrastructure→application 合法）；端口注册 PortSpec + 组合根唯一实例化点；OTel 全局 TracerProvider 单次设置约束（凡 initialize 一律双复位——5.7 SSOT）
- **接口治理:** 统一端口注册/Registry/Resolver/ContractGate、Composition Root 装配、契约优先（11 维度 + 事件契约 + 通道映射契约 ×3）、版本化兼容、禁止跨模块直接依赖实现类；事件双通道治理（新事件必须双处登记 event_channels.yaml + DEFAULT_MAPPINGS——CLAUDE.md 硬约束）
- **技术栈:** Python 3.11+ / 纯标准库（statistics/collections/dataclasses/uuid——OD-2 零新依赖）/ opentelemetry ^1.21（span 写入——既有依赖）/ **零新运行时依赖**（5.7 OD-1 家族原则第三 Story 延续）

### 关键架构决策 Key Design Decisions

**DC-1 漂移检测端口族——单端口双方法（检测 + 重校准触发）**
- 选定：`DriftDetectionPort`（application/ports/agent_drift.py）双方法：`update(score) -> DriftAssessment`（检测——OD-7 单方法原子化）+ `trigger_recalibration(assessment, agent_id=None) -> None`（重校准触发——伪码动词保真 + agent_id 透传[R1 新增：DriftDetected 人工介入定位维度，SINGLETON 跨 Agent 混流知悉]）；`CUSUMDriftDetector`（infrastructure/monitoring/cusum_detector.py——architecture.md L2594 钦定）实现
- 论证：①**R1/R2/R3 规则落地**——EventPublisher（domain 基础端口 R1）被检测器组合注入（R2——事件发布是重校准触发的组成部分）；CUSUM 状态管理（进程内累积/预热/复位生命周期）是技术实现面（R3——infrastructure 实现 application 端口，V1 可替换 Redis 持久化实现[重启存活]或多指标实现——支持扩展其他同类技术实现）；②trigger_recalibration 归端口而非 use case 内联：伪码钦定动词（L1671 `await self.trigger_recalibration()`）+ 重校准策略演化（未来自动配置变更）在端口实现内演化不触碰 use case + 事件发布归检测器（use case 只编排——_RecordingEventPublisher 替身注入面统一）；③评估与检测端口分立（不复用 agent_evaluation）：状态生命周期分立（评估无状态[5.8 DC-9] vs 检测器有状态[DC-6]）+ 演化轴分立（评估模型路由 vs 检测算法/存储）；④**架构钦定位置零偏离**——cusum_detector.py 在 infrastructure/monitoring/（L2594 + §29.7.1 示例文件头 L4248 双锚），对齐 PhoenixTracer 同目录先例
- 备选：评估端口复用（agent_evaluation 加方法——弃：状态语义冲突 + 5.8 资产触碰面扩大）；trigger 内联 use case（弃：伪码动词失锚 + 演化耦合）；算法上提 domain/services（弃：architecture.md L2594 钦定 infrastructure——检测器状态生命周期是技术管理面[DebateEvaluator 纯算法无状态先例不适用——本检测器状态即功能]）

**DC-2 CUSUM 算法——纯标准库 + 冻结基线三阶段状态机**
- 选定：预热（30 样本 statistics.mean/stdev 估计 μ₀/σ₀，baseline_ready=False 不判定）→ 检测（双侧累积和 O(1) 增量 + N中M 确认）→ 确认复位（Sₕ/Sₗ/确认窗清零，基线保持）三阶段；模块常量单源（K/H_MULTIPLIER/CONFIRMATION_N/M/WARMUP_SAMPLES/METRIC_NAME）
- 论证：①纯标准库（OD-2——零新依赖家族原则 + statistics.mean/stdev[ddof=1] 语义精确匹配 + O(1) 增量无向量化需求）；②冻结基线（OD-3——漂移检测前提是基线不随漂移漂移；滑动基线 V1）；③三阶段显式状态机（预热/检测/复位）可测试性——每阶段独立断言锚；④degenerate 防御（σ₀ < 1e-12 不判定）——全同值样本下 k=h=0 恒触发的数学病态防线（可观测降级非异常——样本继续累积）；⑤入参域守卫 201（[0,1]——overall_score 语义域，5.8 EvaluationResult 同款守卫）
- 备选：numpy 向量化全量重算（弃——OD-2 依赖面 + O(n) 每次）；min_samples=100（弃——OD-3 MVP 不可达）；std=0 抛 451（弃——数学病态是数据形态非管线错误，降级语义更正确）

**DC-3 DriftDetected 事件——reliable 单通道 + 领域告警语义**
- 选定：domain/events/drift_events.py `DriftDetected`（kw_only 十二字段[R1：+agent_id——人工介入定位；检测器不感知 Agent、调用方透传，None=未知；**混流知悉**：SINGLETON 单实例跨 Agent 共享序列，多 Agent 质量分布差异膨胀 σ₀/伪造漂移——docstring 注记 + per-agent 键控 V1-EV14 登记] + aggregate_type="AgentEvaluation" + recommended_action="manual_review"）；event_channels.yaml + DEFAULT_MAPPINGS 双登记（rabbitmq_routing_key="sisys.events.reliable.drift_detected"、delivery_mode="reliable"）
- 论证：①漂移确认是领域级告警状态（跨 run 聚合的数值偏离——StrategicDeviationWarning 同族先例：数值+阈值+级别字段 + reliable 投递）——与 5.8「评估非领域概念」的分界：评估结果服务单 run 应用观测[span 属性即载体]，漂移确认是系统级质量状态变迁[事件是载体]；②reliable 单通道（RabbitMQ + Outbox）——告警不可丢（实时 Redis pub/sub 无持久订阅面，漂移告警消费方[人工介入流程]离线时必须可补投）；③**事件是 MVP 唯一的「提示人工介入」通道**（OD-6——无 AlertCenter/通知渠道抽象[调研实证零存在]——事件即告警载体，Epic 11 告警中心面消费）；④发布失败 logger.error 不上抛（agent_profile_loading.py L151-169 先例——可观测附加面：事件失败不阻断主链也不阻断已确认的检测语义）
- 备选：realtime 双通道（弃——告警语义 unreliable 投递）；span 事件双载体（弃——span 是观测面非告警通道[Phoenix 查询回读 R1-DF4 零覆盖]）；手动 HTTP 回调通知（弃——无消费方 + 外部依赖面）

**DC-4 DriftDetectionError 451——evaluation 段取用 + 三层降级网**
- 选定：`DriftDetectionError`（EXCEPTION_451，SystemException，evaluation_exceptions.py 追加——子域单文件惯例）；use case 评估块 catch 元组扩 `(AgentEvaluationError, LLMConfigError, DriftDetectionError)`
- 论证：①451-459 预留段钦定（_code_ranges.py L137-138 注释原文「5.9 漂移检测/5.10 评估历史如需新码在此段取」）；②SystemException 同族论证（450 延续——检测管线是系统侧可观测行为）；③三层降级网（评估失败 450/评估配置失败 332/漂移检测失败 451——CR1-F1[5.8] 论证形态延续：451 的现实可达源是检测器状态异常防御面，主链可用性 > 漂移检测完整性）；④子域单文件追加 vs 新文件：文件名=子域名五代先例（data_source/debate/tool_version/agent/evaluation）——451 归 evaluation 段则 evaluation_exceptions.py 承载（5.10 续段同文件）
- 备选：drift_exceptions.py 新文件（弃——子域映射 evaluation 段但文件名 drift 形成「文件名≠子域名」首例外）；复用 450（弃：评估失败 vs 检测失败语义分立——降级网诊断需要区分）；BusinessException（弃——检测是系统侧行为非业务规则违反）

**DC-5 主链接入——第七可选依赖 + 漂移块内嵌评估块 + 断言同步 ×5**
- 选定：`RunAgentWorkflowUseCase.__init__` 尾部 `drift_detector: DriftDetectionPort | None = None`（存量六参零破坏）；漂移块内嵌评估块 try 内（evaluate 成功 + 三键写入后）：None 守卫 → update(overall_score) → is_drifted 分支 → DRIFT_DETECTED 写入[is_recording 守卫] → trigger_recalibration；**存量断言同步 ×5**（5-7 验收 AC-4.3 + 5-7 test_arch `_USE_CASE_INIT_PARAMS` + **5-8 test_arch_evaluation 六依赖基线**）
- 论证：①可选 None 默认 = 存量零苦役（5.6 十四构造点/5.8 DC-5 教训链第三迭代）；②漂移块内嵌评估块 try 内的位置语义：漂移消费评估产物（evaluation_result 局部变量存活域内）+ 评估失败时漂移天然跳过（序列缺口 MVP=跳过——5.8 风险 #6②处置：缺口不入累积[CUSUM 连续性假设知悉——缺口计数器 V1-EV13]）+ 451 降级网共享评估块 catch（三层网单一 catch 点）；③span 写入仅确认漂移时（键缺席=本 run 无确认漂移——与 eval 三键「缺席=降级」语义分立：drift.detected 缺席是常态[正常运营绝大多数 run 无漂移]，docstring 注记防语义误读）；④**断言同步 ×5 预防性登记（R1 修正）**——5.8 教训「第三处存量触碰实施才发现」在本 Story 创建期即重演（×3 漏两处，调研期 grep 补全为 ×5）：预先全仓 grep 构造签名断言点（**结构化模式 `inspect.signature(RunAgentWorkflowUseCase`/`inspect.signature(use_case_cls` 直命中五处——原中文注释模式（`六依赖`）对 L1367 不命中属巧合依赖**）+ **回执耦合防线**（`"evaluation_harness",  # Story 5.8 第六可选依赖` 字面行被 5.8 验收文本断言锁死——尾部追加禁改写）核验清单落 Task 3 循环 B
- 备选：必选第七依赖（弃——存量苦役）；漂移块独立 try（弃——三层网分裂双 catch 点 + evaluation_result 作用域出界）；漂移块放 AgentWorkflowService（弃——评估产物在 use case 层 + span 根上下文）；每 run 写 drift.detected=False（弃——常态 run 的 span 噪声 + 语义歧义[预热/正常/降级三态不可区分]）

**DC-6 生命周期——SINGLETON 有状态检测器（状态即功能）**
- 选定：`agent_drift` SINGLETON（Epic 5 全家政策延续）+ 手工装配测试新实例（组合根单例仅接线断言消费）
- 论证：①**有状态 SINGLETON 与 5.8 无状态 SINGLETON 论证分立**：状态即功能——跨 run 序列累积（预热 30 + 检测期）必须跨 execute 调用存活，SCOPED[请求域]/TRANSIENT[每次新建]都会使序列归零检测失效；②测试隔离对策：SINGLETON 状态跨测试污染是本 Story 最大隔离面——单元/集成/验收全部手工构造新实例（不走 resolve），组合根单例仅 AC-4.1 isinstance 断言（不执行 update——状态不进测试）；③重启归零知悉（进程生命周期 = 检测序列生命周期——重启后重新预热 30 样本；MVP 可接受[漂移是持续监控面非关键数据]，V1 Redis 持久化 V1-EV12 登记）
- 备选：SCOPED/TRANSIENT（弃——序列归零）；Redis 持久化 MVP（弃——外部依赖面 + 5.10 Checkpoint 集成才是评估数据持久化的规划归宿）

**DC-7 基线与确认参数——附录 I 钦定值 + 样本量 30 锚**
- 选定：K_MULTIPLIER=0.5 / H_MULTIPLIER=5.0（§29.3.1.1 标准 CUSUM 参数 + §29.3.3.2 质量指标 accuracy 行[overall 是合成质量分——对齐 accuracy 类而非 hallucination_rate 类：后者 k=0.3/h=4 是更敏感配置，overall 合成分噪声更大取标准档；R1 业界核验：k=δ/2=0.5σ 对 1σ 移位最优、h=5↔ARL₀≈465 保守档[Montgomery Ch.9 / Hawkins-Olwell 教科书域]——取值无异议]）/ CONFIRMATION_N=3 / CONFIRMATION_M=5（§29.3.2.2 警告级默认）/ WARMUP_SAMPLES=30（§29.2.3.2 正态性检验样本量下限）
- 论证：①全部参数锚定附录 I 表格（防拍脑袋参数）；②k/h 是 σ₀ 相对量——**5.8 风险 #6④ 可达域压缩的天然适配**：overall 两病态角带包络 [0.475,0.65]（R1 措辞修正——真实可达域是 [0,1]，[0.475,0.65] 是 5-8 注记 agent_evaluation.py L104-109 的病态角带包络；前置依赖表 [0.525,0.60] 是两角带之交的重叠带——两数各有所指）压缩只影响 σ₀ 估计值（更小 σ₀ → 更小绝对阈值——灵敏度自适应），检测机制与绝对域无关；③六档锚定多峰知悉（5.8 风险 #6：h 序列聚集 6 锚点值 → σ₀ 估计呈多峰、累积和呈阶梯——量化序列的正常形态，非缺陷；V1 连续化评分[两步法 claim 分解]可缓解）；④配置常量模块级单源（TEMPERATURE_PROFILE 先例）——yaml 配置面 V1（§29.7.2 形态不采用——MVP 常量单源 + 配置文件化是运维需求时再引入）；⑤**σ̂₀ 抽样误差注记（R1 新增）**：n=30 时 stdev 相对标准误 ≈1/√(2×30)≈13% → h 绝对值 ±13% 波动、名义 ARL₀ 可漂一个量级——合成回测 FP 主因（实测 FP≈5%），docstring 知悉注记 + judge 温度非确定[处置③]同族登记
- 备选：hallucination_rate 档 k=0.3/h=4（弃——那是单键幻觉率配置；overall 合成分取标准档）；yaml 配置（弃——YAGNI + 零环境变量面）

**DC-8 性能口径——纯内存检测管线 P99 + 合成回测准确率**
- 选定：①P99<100ms 口径 = 单次 update 调用开销（双侧增量 + 确认窗 + DriftAssessment 构造——**事件发布不在口径**[Outbox IO 是确认后触发动作非检测延迟]）；warmup 1 + 100 采样 + `statistics.quantiles(n=100)[98]` exclusive P99 + 委托缓存 + xdist_group("drift-detection-perf")——**quantiles[98] 是近最大值估计量注记（R1）**：100 样本下即前 2 大样本插值、方差大、保守方向[高估分位→更严门]，门定位「回归绊线非精确分位」落 docstring；②准确率≥85% 口径 = 合成序列回测（**R1 参数定稿**：固定种子 40 序列 × 60 样本[30 基线 uniform(0.7,0.9)+30 评估段；漂移 delta=uniform(0.3,0.5)≈4.9σ~8.1σ——σ̂₀≈0.058 实算口径，非原稿「≈3σ」]，每序列独立检测器，(TP+TN)/40 ≥0.85[钦定种子基准 TP=20/FP=1/acc=0.975；2000 种子 acc<0.85 概率 0%]，分项计数断言消息，确定性双跑同结果；**评估段长 30 禁拉长**——FP 随段长线性增长[L=70 最坏 acc 0.775]）
- 论证：①P99 需 99 分位——5.8 P95 [18] 的 20 采样不足以估 P99（n=20 的 [18] 是 95 分位），100 采样 [98] 是 quantiles exclusive 法对应口径（纯内存 100 采样总耗时 ms 级——CI 可行）；②**准确率是 V2 指标的 MVP 承载裁定**（OD-7——epics L1839「漂移检测准确率≥85%（V2 指标，回测历史数据验证）」：V2 本义是生产历史数据回测，MVP 无历史序列——合成回测是**合成形态下的统计检出能力验证**（R1 措辞修正——「数学等价」过强：合成 uniform ≠ 真实多峰形态[5-8 风险 #6④ 知悉]），真实回测 V2 数据积累后补）；③回测设计效度知悉：合成漂移注入幅度 ≥3σ 是保守注入（CUSUM 设计检测灵敏度 0.5σ-2σ——小漂移检出需要更长序列/调参，V1 调参面）；固定种子保证 CI 确定性（同种子同序列同结果——防 flaky）；④正向锚（update 调用计数 == 采样数——防静默跳过假绿——5.8 DC-8③ 先例延续）
- 备选：真实 LLM 全链 P99（弃——网络主导不可控——5.8 DC-8 同款口径声明）；20 采样 [18] 冒充 P99（弃——分位口径错位）；回测含小漂移序列（弃——0.5σ 漂移下 35 样本窗口检出率不稳定 → CI flaky——V1 调参后引入）

**关键决策对照表（选中方案 vs 备选）：**

| 决策点 | 选中 | 备选（弃因） |
|--------|------|-------------|
| 端口族 | 单端口双方法 + infrastructure 实现（DC-1） | 评估端口复用（状态语义冲突）；trigger 内联（伪码失锚）；domain 算法（钦定位置偏离） |
| 算法实现 | 纯标准库三阶段状态机（DC-2） | numpy（OD-2 依赖面）；100 样本基线（不可达）；std=0 抛异常（降级语义更正确） |
| 事件 | DriftDetected reliable 单通道（DC-3） | realtime（告警不可丢性）；span 载体（查询通道零覆盖） |
| 异常 | 451 段内取用 + 三层降级网（DC-4） | 新文件（文件名≠子域首例）；复用 450（语义分立） |
| 主链接入 | 第七可选依赖 + 内嵌评估块 + 断言同步 ×5（DC-5） | 必选（存量苦役）；独立 try（双 catch 点）；写 False（语义噪声） |
| 生命周期 | 有状态 SINGLETON + 测试新实例（DC-6） | SCOPED/TRANSIENT（序列归零）；Redis MVP（外部依赖面） |
| 参数 | 附录 I 钦定值 + σ 相对量（DC-7） | 幻觉率档（配置错位）；yaml（YAGNI） |
| 性能 | 纯内存 P99[98] + 合成回测（DC-8） | 真实 LLM（不可控）；[18] 冒充（口径错位）；小漂移回测（flaky） |

### 风险登记

| # | 风险 | 处置 |
|---|------|------|
| 1 | **SINGLETON 有状态检测器的测试隔离**（跨测试序列污染——A 场景灌入的序列影响 B 场景基线/累积） | 测试全形态手工新实例（不走 resolve——DC-6②）；组合根单例仅 isinstance 断言不执行 update；链级场景预填充形态场景级私有实例；验收/集成/单测三层的隔离约束节钉死 |
| 2 | use case 构造签名七依赖回归面（存量断言点遗漏更新——5.8「第三处实施才发现」教训重演） | 断言同步 **×5 预防性全清单（R1 实证）**：5-7 验收 AC-4.3 + 5-7 test_arch + 5-8 test_arch_evaluation + **test_run_agent_workflow `test_constructor_sixth_param_default_none`[L683-693]** + **5-8 验收 AC-3.3[L1308-1328]**——本 Story 现有代码继承#9/AC-3/DC-5④/Task 3 循环 B 多处登记）+ **回执字面行保留防线**（`"evaluation_harness",  # Story 5.8 第六可选依赖` 行被 5-8 验收文本断言锁死——尾部追加禁改写）+ Task 3 结构化 grep 核验（`inspect.signature(RunAgentWorkflowUseCase`/`inspect.signature(use_case_cls` 五处直命中——原中文注释模式对 L1367 不命中）；全仓 **11** 构造点（六参 3 + 五参 8[R1 实证]）None 默认零破坏 |
| 3 | N中M 确认语义边界（确认窗 maxlen=5 的前 4 样本永不确认；确认与 detection 的时序错位；**确认落在非 detection 样本时 level 无合法值[R1 新增——纯 N中M 下 ratio 可 ≤5 击穿 DriftAssessment 守卫，实证反例 ratio=4.40]**） | **确认条件含当前样本 detection=True（R1 案 A 裁定——ISA-18.2 M-of-N 告警宣告语义：确认时刻必在告警态 → ratio>5 恒成立、level 域完备；业界对标 Prometheus for/Argo failureLimit 同构；对回测 TP/FP 零影响[蒙特卡洛 500 种子逐数相同]**）+ 手算锚钦定（s31-s35 逐样本演算——AC-1 F,T,T,T,T 计数 4≥3 且当前 T 确认）+ 边界参数化（**F,T,T,T,F 不确认[当前样本 F]**/F,T,T,F,T 确认/F,T,T,F,F 不确认）+ 当前样本条件变异锚（删除→边界用例红）+ 确认后复位断言（后续样本从零累积 + 再确认间隔锚）；CONFIRMATION_N/M 变异实证锚 |
| 4 | 浮点断言假红/假绿（CUSUM 累积和 0.35×3=1.05 类二进制不精确；σ₀=交替序列 stdd 的近似性） | 浮点纪律全文钉死（R1 修正）：**钦定同式表达式 `(0.8 - 0.5*sigma0 - 0.4) * n`**[σ₀ 经 statistics.stdev(baseline) 实算]——**禁 k 写死 0.05 的假红形态[σ₀=√(0.3/29)≈0.1017 非 0.1，k≈0.0509]、禁 pytest.approx[仓内无先例——纪律是精确等式+同式表达式]**、禁十进制字面量（5.8 R3-F1 教训——组合链实算 0.7000000000000001 类）；手算锚序列值选择与断言形态在 AC-1/测试隔离约束节双登记 |
| 5 | degenerate 基线（全同值样本 σ₀≈0 → k=h≈0 → max(0, x-μ₀-0) 恒正累积 → 恒触发） | _DEGENERATE_STD_EPSILON=1e-12 防线（σ₀ < ε 时 detection 恒 False——AC-1 degenerate 用例 + Task 2 循环 B）；docstring 数学病态注记（R1 补强：防线失效后果不止「恒触发」——确认路径 ratio=S/σ₀ 先 ZeroDivisionError 崩溃，防线必要性强于原述） |
| 6 | 事件发布失败面（Outbox 不可用/发布异常——漂移告警丢失） | 发布失败 logger.error 不上抛（DC-3④——主链不阻断）+ 知悉：单次发布失败即告警丢失（无重试——Outbox 内部已有 RetryPolicy，publish 入 Outbox 失败是存储面故障）；检测器复位已发生——该轮漂移不重发（语义知悉：确认即复位使告警一次性——重复告警依赖持续漂移再累积；V1 发布重试/告警持久化随监控域评估） |
| 7 | 评估降级的序列缺口（评估失败 run 不进 CUSUM 序列——连续性假设受损：高失败率期漂移检出延迟/漏检） | MVP 跳过策略钉死（AC-3 评估降级联动——update 零调用断言）；缺口计数器 V1-EV13 登记（deferred-work——触发条件：缺口率可观测需求）；知悉注记 docstring（缺口期间检测灵敏度下降是跳过策略的代价） |
| 8 | mypy 对检测器状态字段/Protocol 组合的类型窄化（deque 泛型/float 与 int 混算） | 标准形态（dataclass 状态字段显式注解——float 全程；sample_count: int 隔离）；实施时 ruff+mypy 门禁即验 + 全仓 mypy（构造签名扩展——Task 3 收尾） |
| 9 | xdist 并行下委托缓存竞态（P99 采样 + 回测矩阵双委托槽——组内串行前提） | `xdist_group("drift-detection-perf")` 同组同 worker 串行（loadgroup——_PERF_CACHE 命中前提）+ 组名 13 组互异 grep 断言 + 双委托槽 key 分立（"p99"/"backtest"） |
| 10 | 正向漂移（direction="up"）的语义误读（质量提升也告警——消费方误当系统故障处理） | 事件 direction 字段显式区分（up/down 语义注记 docstring：up 可能是真实改进[重校准成功信号]或评估器漂移[judge 变更/自评偏差——V1-EV4 golden set 关联]）；recommended_action="manual_review" 是中性人工复核非故障响应 |

### 项目结构说明 Project Structure

```
src/
├── application/
│   ├── ports/
│   │   ├── agent_drift.py                 # 新建：DriftDetectionPort（update + trigger_recalibration）+ DriftAssessment
│   │   └── __init__.py                    # 修改：聚合导出（DriftDetectionPort/DriftAssessment）
│   └── use_cases/
│       └── run_agent_workflow.py          # 修改：第七可选依赖 + 评估块内漂移块 + catch 扩 451（纯附加）
├── domain/
│   ├── events/
│   │   ├── drift_events.py                # 新建：DriftDetected 领域事件
│   │   └── __init__.py                    # 修改：导入 + __all__
│   └── exceptions/
│       ├── evaluation_exceptions.py       # 修改：追加 DriftDetectionError（EXCEPTION_451）
│       ├── _code_ranges.py                # 修改：_CLASS_TO_SUBDOMAIN 增行 + 段注释更新
│       └── __init__.py                    # 修改：导出
├── infrastructure/
│   ├── monitoring/
│   │   └── cusum_detector.py              # 新建：CUSUMDriftDetector（DriftDetectionPort 实现——架构钦定位置）
│   └── messaging/
│       └── channel_router.py              # 修改：DEFAULT_MAPPINGS 增 DriftDetected 条目
├── interfaces/
│   └── api/
│       └── exception_handlers.py          # 修改：EXCEPTION_HTTP_MAP 451→500
└── composition_root.py                     # 修改：# === Story 5.9 === agent_drift 注册 + use case 工厂第七依赖

configs/
└── event_channels.yaml                     # 修改：DriftDetected 条目（reliable 双登记其一）

tests/
├── unit/
│   ├── domain/
│   │   ├── events/
│   │   │   └── test_drift_events.py       # 新建（事件构造/注册/aggregate/to_dict）
│   │   └── exceptions/
│   │       └── test_evaluation_exceptions.py  # 追加（451 构造/映射/注册）
│   ├── application/
│   │   ├── test_agent_drift_model.py      # 新建（DriftAssessment 域守卫 + 端口形态）
│   │   └── use_cases/
│   │       └── test_run_agent_workflow.py # 追加（漂移块五面）
│   ├── infrastructure/
│   │   └── monitoring/
│   │       └── test_cusum_drift_detector.py  # 新建（三循环：算法/确认/发布）
│   └── architecture/
│       ├── test_arch_drift_detection.py   # 新建（验证器 A/B/C + 零抑制注释）
│       ├── test_arch_evaluation.py        # 修改：use case 签名基线六→七（5-8 资产同步③）
│       └── test_arch_phoenix_tracer.py    # 修改：_USE_CASE_INIT_PARAMS 六→七（5-7 资产同步②）
├── contracts/
│   ├── test_port_contract_agent_drift.py          # 新建（11 维度）
│   ├── test_event_contract_drift_events.py        # 新建（注册/aggregate/to_dict）
│   └── test_event_channel_mapping_drift.py        # 新建（双登记一致）
├── integration/
│   └── test_integration_drift_detection.py        # 新建（六场景 + P99 + 回测常量单源）
└── acceptance/
    ├── test_acceptance_drift_detection.feature    # 新建（13+收尾=14 场景）
    ├── test_acceptance_drift_detection.py         # 新建（BDD 步骤）
    └── test_acceptance_phoenix_tracer.py          # 修改：AC-4.3 构造签名基线六→七（5-7 资产同步①）

docs/architecture/sisys-uni-exception-design.md   # 修改：§3.3.2 编码分配表 451 行（Task 1）
docs/architecture/architecture.md                 # 修改：§14.4 交付注记（Task 6）
docs/architecture/sisys-core-domain-design.md     # 修改：§17.3.8 实现注记（Task 6）
_bmad-output/implementation-artifacts/deferred-work.md  # 修改：处置注记 ×4 + V1/V2 通道（Task 0/6）
_bmad-output/implementation-artifacts/sprint-status.yaml  # 修改：5-9 状态流转
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 5.8](./5-8-agent-output-quality-evaluation.md)（v2.3.1 done 收敛态——文档审查 5 轮 + 代码审查 5 轮完整教训链）+ [Story 5.7](./5-7-phoenix-evaluation-harness.md)（追踪面——本 Story span 通道直接依赖）

**关键学习/Key Learnings:**
- **构造签名扩展的存量断言面要在故事里数清**（5.8 预登记两处、实施发现第三处[test_arch_evaluation 六依赖基线]；**本 Story 创建期 ×3 仍漏两处[R1 实证]——调研期结构化 grep（`inspect.signature(RunAgentWorkflowUseCase`）才数清为 ×5，且发现 5-8 验收回执文本断言的字面行耦合**）——本 Story 对策：断言同步 ×5 全清单 + 回执字面行保留防线（现有代码继承#9/AC-3/DC-5④/Task 3 循环 B 多处登记）+ Task 3 结构化 grep 核验
- **断言可满足性断层是最大实施陷阱**（5.6 端口 Raises 不可满足；5.7 span 机制自相矛盾；**本 Story 创建期即中两招[R1 实证]：0.95×6 锚数学不可确认 + k 写死 0.05 假红形态**）——本 Story 对策：手算锚序列逐样本演算钉死（s31-s35 Sₗ 五值 + 确认窗 F,T,T,T,T 演算——σ₀ 经 statistics.stdev 实算 ≈0.1017 同式表达）；正向漂移 0.95×8 锚（s38 确认 moderate——原 0.95×6 不可确认）+ 0.95×5 处 Sₕ≈0.496<h≈0.509 余量 2.5% 语义显式化（防 off-by-one 断言错位——原「0.50 边界」按 σ₀=0.1 舍入失真[R1 修正]）
- **断言恒真防范**（Epic 4 8/13 恒真；5.8 变异实验暴露恒真断言三条）——本 Story 对策：常量单源六项断言（参数漂移防线）+ P99 正向锚（update 调用计数）+ 回测分项计数断言消息（TP/FP/TN 可诊断）+ 每 TDD 循环变异表行（k/确认阈/复位/severity 阈/装配错位五类变异锚）
- **浮点断言纪律**（5.8 R3-F1：0.6475000000000001 假红根修）——本 Story CUSUM 累积和全程同式表达式/approx 禁字面量（风险 #4 + 测试隔离约束节双登记）
- **测试环境前提钉死**（5.7 OTel Once 闩锁 + TestInitTracing 泄漏源）——本 Story 继承：凡 initialize 一律双复位 + 文件级 autouse 兜底 + env 不带 PHOENIX_TRACING_ENABLED=true
- **组合根工厂时序**（5.8 R1-F1：lambda 提前注入 kwarg 必 TypeError）——本 Story 对策：agent_drift 注册 Task 1 落地 / use case 工厂第七依赖 Task 3 与第七参数同窗（Task 1 完成标准明示）
- **mypy 全仓验证盲区**（5.8：组件改签名后必须 mypy . 全仓）——本 Story 对策：use case 七依赖扩展后全仓 mypy（Task 3 收尾 + Task 6.4 复验）
- **零新依赖家族原则**（5.7 OD-1/5.8 延续）——本 Story 第三延续：纯标准库 statistics（OD-2——附录 I 示例 numpy/scipy 的显式不采用论证）

**应用到本故事/Applied to This Story:**
- [ ] 断言同步 ×5 + 全仓 grep 核验（Task 3 循环 B）
- [ ] 手算锚逐样本演算 + 边界语义显式化（AC-1 + Task 2 循环 A）
- [ ] 常量单源/正向锚/分项计数/五类变异锚（Task 2/4 + AC-5）
- [ ] 浮点纪律全程（测试隔离约束节 + AC-1）
- [ ] OTel 双复位纪律全套继承（测试隔离约束节）
- [ ] 组合根注册/工厂注入时序分离（Task 1 vs Task 3——R1-F1[5.8] 同款）
- [ ] 全仓 mypy（Task 3 收尾 + Task 6.4）
- [ ] 纯标准库零新依赖（OD-2 + 验证器 A 零新增断言）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (glm-5.3) |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-10-28 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（L1812-1855） |
| **架构文档** | `docs/architecture/architecture.md`（§14.4/L2594/L2661/ADR-012 L3658-3662） |
| **架构附录 I** | `docs/architecture/arch-appendix.md`（§29.1-29.7——CUSUM 全规范） |
| **核心域设计** | `docs/architecture/sisys-core-domain-design.md`（§17.3.8 L1594-1725） |
| **统一异常设计** | `docs/architecture/sisys-uni-exception-design.md`（§3.3/§3.12） |
| **前一个 Story** | `5-8-agent-output-quality-evaluation.md`（v2.3.1 done——直接依赖）+ `5-7-phoenix-evaluation-harness.md`（span 通道依赖）+ `5-3-single-agent-workflow.md`（宿主依赖） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（含范围边界表——与 5.10/V1/V2/Epic 11 精确切分）
- [x] 架构约束从 architecture.md/arch-appendix.md 附录 I/sisys-core-domain-design.md 提取（§17.3.8 伪码 + 附录 I 算法规范 + §29.7.1 参考实现 + L2594 钦定位置 + ADR-012）
- [x] 前一个故事学习经验整合（5.8 教训链 + 四条移交留项处置 + 风险 #6 移交注记四条逐条落点）
- [x] 四视角并行代码调研（评估域交付物与接入点 / tracing 与事件通道基建 / 端口与异常体系 / 测试风格与模板——关键事实独立验证：评估历史零持久化 / overall 不写 span / DRIFT_DETECTED 键已注册 / 451-459 段钦定预留 / numpy 非直接依赖 / 双登记是事件可达性前提 / 存量断言三处清单）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（DC-1~DC-8 设计决策 + OD-1~OD-7 偏离声明 + 风险十项）
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/5-9-cusum-drift-detection-recalibration.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/application/ports/agent_drift.py` - 漂移检测端口（DriftDetectionPort + DriftAssessment）
- `src/domain/events/drift_events.py` - DriftDetected 领域事件
- `src/infrastructure/monitoring/cusum_detector.py` - CUSUMDriftDetector（算法核心）
- `tests/unit/domain/events/test_drift_events.py` - 事件单测
- `tests/unit/application/test_agent_drift_model.py` - 端口模型单测
- `tests/unit/infrastructure/monitoring/test_cusum_drift_detector.py` - 检测器单测（三循环）
- `tests/contracts/test_port_contract_agent_drift.py` - 端口契约（11 维度）
- `tests/contracts/test_event_contract_drift_events.py` - 事件契约
- `tests/contracts/test_event_channel_mapping_drift.py` - 通道映射契约
- `tests/integration/test_integration_drift_detection.py` - 集成（六场景 + P99 + 回测）
- `tests/unit/architecture/test_arch_drift_detection.py` - AST 架构验证器
- `tests/acceptance/test_acceptance_drift_detection.feature` - Gherkin（13+收尾=14 场景）
- `tests/acceptance/test_acceptance_drift_detection.py` - BDD 步骤实现

**待修改的文件/To Be Modified:**
- `src/application/use_cases/run_agent_workflow.py` - 第七可选依赖 + 漂移块 + catch 扩 451
- `src/application/ports/__init__.py` / `src/domain/events/__init__.py` / `src/domain/exceptions/__init__.py` - 聚合导出
- `src/domain/exceptions/evaluation_exceptions.py` - 追加 DriftDetectionError（451）
- `src/domain/exceptions/_code_ranges.py` - _CLASS_TO_SUBDOMAIN 增行
- `src/interfaces/api/exception_handlers.py` - EXCEPTION_HTTP_MAP 451→500
- `src/infrastructure/messaging/channel_router.py` + `configs/event_channels.yaml` - DriftDetected 双登记
- `src/composition_root.py` - Story 5.9 区段注册 + use case 工厂第七依赖
- `tests/unit/domain/exceptions/test_evaluation_exceptions.py` - 追加 451 用例
- `tests/unit/application/use_cases/test_run_agent_workflow.py` - 漂移块五面追加
- `tests/acceptance/test_acceptance_phoenix_tracer.py` / `tests/unit/architecture/test_arch_phoenix_tracer.py` / `tests/unit/architecture/test_arch_evaluation.py` / `tests/unit/application/use_cases/test_run_agent_workflow.py`（追加面同文件）/ `tests/acceptance/test_acceptance_agent_evaluation.py`（AC-3.3 清单断言）- 构造签名断言同步 ×5（R1 补全两处——回执字面行保留防线见「现有代码继承」#9）
- `tests/unit/interfaces/api/test_exception_handlers.py` - expected_types 集合追加 DriftDetectionError（映射表完整性伴随更新——L212/L355 穷举等值断言，5.8 同款）
- `docs/architecture/sisys-uni-exception-design.md` / `architecture.md` / `sisys-core-domain-design.md` / `deferred-work.md` / `sprint-status.yaml` - 文档终态

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 5.9 |
| **Story Key** | 5-9-cusum-drift-detection-recalibration |
| **File** | `_bmad-output/implementation-artifacts/stories/5-9-cusum-drift-detection-recalibration.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 5: Agent 协作系统（价值组：单 Agent 战略规划能力——EV 可观测族第三 Story） |
| **优先级** | P1-9（epics 执行序；FR-EV-03 功能 P1——双锚） |
| **覆盖 FR** | FR-EV-03（CUSUM 漂移检测与触发重校准） |
| **性能锚** | epics L1838（检测延迟 P99<100ms——纯内存检测管线口径 DC-8）+ L1839（漂移检测准确率≥85%——合成序列回测承载 OD-7/V2 真实回测） |
| **覆盖率锚** | 应用层 ≥85%（epics L1842）/ infrastructure ≥75%（epics L1843 口径映射）/ domain ≥90% 维持 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-6）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-5 + 14 验收场景）
3. [x] Architecture constraints extracted 架构约束已提取（六边形约束 + 附录 I 算法规范 + 通道双登记硬约束）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（5.8/5.7 教训链 + 四条移交留项）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | AC-1 验证标准「正向漂移 0.95×6 手算锚」数学不可满足（σ₀=0.1017 下首 detection 在第 6 样本、确认窗计数 1<3，is_drifted 恒 False） | P0 | 改 0.95×8（s38 确认、Sₕ≈0.793、ratio≈7.80→moderate）；AC-1 And 正向锚段/验证标准/Task 2 循环 B/风险 #3 四处同步 |
| R1-2 | level 判定空档：纯 N中M 确认可落在非 detection 样本（文档自设 (F,T,T,T,F) 参数化即此形态），ratio 可 ≤5（实证 4.40）→ is_drifted=True 而 level 无合法值，击穿 DriftAssessment 自身一致性守卫 | P0 | 采案 A：确认条件追加「当前样本 detection=True」（ISA-18.2 M-of-N 告警宣告语义；ratio>5 恒成立、level 域完备；蒙特卡洛实证对回测 TP/FP 零影响）；AC-1/OD-5②/风险 #3/Task 2 变异锚同步；(F,T,T,T,F) 翻转为不确认 + 补 (F,T,T,F,T) 正形态 |
| R1-3 | 手算锚十进制字面量与 ddof=1 不自洽：σ₀=√(0.3/29)≈0.1017 非 0.1，钦定示例表达式 `0.8-0.05-0.4`（k 写死 0.05）对正确实现必假红，与 Task 2 正确形态自相矛盾；「0.50 边界严格大于」叙事失真（0.4957 vs 0.5085） | P0 | 全文统一钦定同式表达式 `(0.8 - 0.5*sigma0 - 0.4) * n`（σ₀ 实算）；锚值改 ≈ 舍入示意；删 pytest.approx 通道（仓内无先例）；「边界」改「余量 2.5%」；AC-1/验证标准/浮点纪律节/风险 #4/Lessons 同步 |
| R1-4 | 构造签名断言点实为 5 处非 3 处（漏 test_run_agent_workflow L683-693 `test_constructor_sixth_param_default_none` 与 test_acceptance_agent_evaluation L1308-1328 AC-3.3）——5.8「实施才发现」教训重演面 | P0 | 全文 ×3→×5 + 五处全清单登记（现有代码继承#9/AC-3/DC-5④/Task 3 循环 B/风险 #2/File List）；grep 模式改结构化（`inspect.signature(RunAgentWorkflowUseCase`/`use_case_cls` 五处直命中——原中文注释模式对 L1367 不命中） |
| R1-5 | 隐藏回执耦合：5-8 验收 L1368/1370/1773/1774 以文本断言锁死 5-7 两文件 `"evaluation_harness",  # Story 5.8 第六可选依赖` 字面行——六→七更新若改写该行则 5-8 验收红 | P0 | 处方钉死：①②文件原样保留既有行、仅尾部追加 drift_detector 行（回执耦合防线——AC-3/继承#9/Task 3 循环 B/风险 #2 登记） |
| R1-6 | Task 1 时序不可达：端口契约维度 9b `spec.impl(_DummyResolver())` 真实构造 impl 类、维度 10 调其方法、AC-4.1 resolve 四件构造实例——而 CUSUMDriftDetector 归 Task 2，Task 1 DoD「契约全绿 + AC-4.1 注册面转绿」必红 | P0 | 组合根 agent_drift 注册 + test_port_contract_agent_drift + AC-4.1 注册面整体移 Task 2（新增循环 C + Subtask 2.8）；Task 1 收窄为异常/事件/端口文件/通道双登记 + 契约 ×2；Task 1 DoD/AC→Task 矩阵/测试分类表同步 |
| R1-7 | 合成回测四参数未钉死（序列长度/稳定段分布/漂移段样本数/移位抽取）——FP 率实测敏感（评估段 70 最坏 acc=0.775 击穿门）；「-0.3≈3σ」套错 σ₀（uniform σ̂₀≈0.058 → 实为 ≈4.9σ） | P1 | 参数定稿：60 样本=30 基线 uniform(0.7,0.9)+30 评估段；delta=uniform(0.3,0.5)；钦定种子基准 TP=20/FP=1/acc=0.975、2000 种子 acc<0.85 概率 0%；评估段长禁拉长注记；AC-5/DC-8/Task 0.5/Task 4.1 同步 |
| R1-8 | OD-5「重复告警间隔 ≈2-5 样本」失实（实测 down 0.4=5、up 0.95=8、δ=0.2=6、δ=0.16=7——与幅度反比） | P1 | 改「与漂移幅度反比」+ 实测表 + 间隔公式；Task 2 循环 B 补再确认间隔锚 |
| R1-9 | DriftDetected 缺 Agent 维度 + SINGLETON 检测器跨 Agent 混流（人工介入无法定位 Agent；多 Agent 分布差异膨胀 σ₀） | P1 | 事件加 `agent_id: str | None = None` + 端口 trigger_recalibration 加 agent_id 透传参数 + use case execute 形参透传；混流 docstring 知悉 + per-agent 键控 V1-EV14 登记 |
| R1-10 | 预热期第 1 样本 baseline_std 未定义（statistics.stdev 需 ≥2 样本，N=1 抛 StatisticsError——首个 update 即崩） | P1 | 数据模型/AC-1/Task 2 钉死 N<2 时 baseline_std=0.0（与 degenerate ε 语义一致） |
| R1-11 | test_exception_handlers.py（expected_types 穷举等值断言）无任务归属（仅 File List 挂名，Task 1 绿动作/存量触碰清单缺） | P1 | Task 1 循环 A 绿动作 + 继承#9⑥ + Task 6.2 计数修正（六件存量触碰） |
| R1-12 | sisys-uni-exception-design.md §3.3.2 同步处方不完整（L743 是「451~459 预留」行——只插行不改预留段则重叠） | P1 | 三步处方：插 451 行 + 预留行收缩 452~459 + 子域表 L822 注记同步（异常契约节 + Task 1 重构行） |
| R1-13 | xdist 13 组清单 6 名漏 -perf 后缀（照抄写 grep 断言必错）；_RecordingEventPublisher 计数 12 实为 15 文件；「测试九件」实为新建十件+追加一件；构造点「8+」实为 11 | P2 | 实名清单/计数逐一修正（AC-5/继承#3/继承#5/风险 #2/Task 6.2） |
| R1-14 | event_loop fixture 与 _run_async 是各验收文件自带（conftest 不提供）——Subtask 0.6 fixture 清单漏 | P2 | 0.6 补「模块级 event_loop + _run_async 自备」注记（26/16 处先例） |
| R1-15 | 悬空决策「未确认 assessment 是否发布（Task 0.2 定稿二选一）」+ 30 样本锚误引 §29.2.3.1（正态性检验实在 §29.2.3.2，四处） | P2 | 裁定 trigger 内 is_drifted 守卫零发布（双保险）；§29.2.3.1→§29.2.3.2 全局替换 |
| R1-16 | AC-3.1「overall=0.4 形态」与可达域冲突（病态角带 [0.475,0.65]——dev 可能空耗调 Fake 追 0.4）；DC-7「可达域 [0.475,0.65]」措辞失准（那是病态角带包络，真实可达域 [0,1]） | P2 | AC-3.1 注记「末样本带内任意值均可确认（Sₗ 预累积主导）」；DC-7 措辞改「两病态角带包络」并与前置依赖表重叠带 [0.525,0.60] 口径分立 |
| R1-17 | σ₀ 抽样误差注记缺失（n=30 RSE≈13% → h ±13%、FP 主因）；OD-3 冻结基线缺「慢漂移检出优势」论据；quantiles[98] 近最大值估计量注记缺失；DC-8「数学等价」措辞过强 | P2 | DC-7⑤ σ̂₀ 误差注记 + DC-8 P99 注记 + 「数学等价」→「合成形态下的统计检出能力验证」（业界对标：Evidently 固定 reference/Alibi-Detect 同构） |
| R1-18 | 杂项行号漂移与计数（评估块 if 实在 L201[非 L192]；span 块 L180-191[十属性]；Fake LLM 链 L185-284；EXCEPTION_HTTP_MAP L141-287；451→500 论证改「惯例非功能必要」；451 resolve 四件总线构造期纯注入注记；_DummyResolver 无 event_publisher 分支[扩展非照抄]） | P2/P3 | 逐一修正/补注（前置依赖表/继承表/异常契约节/AC-4/契约测试行） |

> **R1 审查配置**：D1 四视角并行调研（主链接入面/事件异常基建/测试基建/规划文档+算法科学性）+ D2 三视角并行审查（一致性/科学性业界对标/可行性）+ 主会话独立数学实测定谳；处置 P0×6 + P1×6 + P2/P3 若干，版本 v1.0.0 → v1.1.0。

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** （待实施后填写）
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策 Decision Needed

- [ ] （待实施后填写）

#### 已修复 Patch

- [ ] （待实施后填写）

#### 已推迟 Defer

- [ ] （待实施后填写）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

### 📋 变更日志 Change Log [dev-story 必填]

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| v1.0.0 | 2026-10-28 | 创建故事文件（create-story workflow——四视角并行调研 + DC-1~DC-8 + OD-1~OD-7 + Task 0-6 + 14 验收场景规划） | SM (Claude Code) |
| v1.1.0 | 2026-10-28 | 文档审查 Round 1（四调研 + 三审查 + 主会话实测定谳）：P0×6（0.95×6 锚不可满足→0.95×8 / level 空档→确认含当前样本 detection[案 A] / 手算锚 σ₀ 同式表达根修 / 断言同步 ×3→×5 / 5-8 回执字面行耦合防线 / Task 1 注册+端口契约时序移 Task 2）+ P1×6（回测参数定稿 / OD-5 间隔实测 / DriftDetected 加 agent_id / N=1 baseline_std / exception_handlers 归属 / §3.3.2 三步处方）+ P2/P3 若干（xdist 实名清单 / 计数修正 / 行号锚修正 / 悬空决策裁定 / 可达域措辞 / σ̂₀ 误差注记等） | SM (Claude Code) |

**故事版本/Story Version:** v1.1.0
**创建日期/Created:** 2026-10-28
**最后更新/Last Updated:** 2026-10-28
**更新说明/Description:**
- v1.0.0: 创建故事文件——CUSUMDriftDetector（双侧累积和 + 预热基线 30 + N中M 3中5 确认 + moderate/severe 分级 + 确认后复位）+ DriftDetected 领域事件（reliable 双登记）+ DriftDetectionError 451 + use case 第七可选依赖主链接入（drift.detected span 填值——OD-2[5.7] 兑现闭环）+ 性能双锚（P99<100ms + 合成回测准确率≥85%）
- v1.1.0: 文档审查 R1 收敛——P0×6 全清（数学可满足性两处根修 + 断言面 ×5 + 回执耦合防线 + Task 时序重构）+ P1×6（回测定稿/agent_id 维度/N=1 防崩/§3.3.2 三步处方等）+ P2/P3 批量；确认语义升格「当前样本 detection=True」（ISA-18.2 对标）；手算锚全文改 σ₀ 实算同式表达
