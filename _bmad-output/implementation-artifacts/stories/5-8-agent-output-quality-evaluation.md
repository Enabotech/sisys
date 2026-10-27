# Story 5.8: Agent 输出质量评估（幻觉检测、上下文相关性、置信度校准）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 可观测性工程师,
**I want** 实现 Agent 输出质量评估（EvaluationHarness：幻觉检测 + 上下文相关性 + 置信度校准 + overall 加权，评估模型经 UDMR 动态路由获取）,
**So that** Agent 工作流输出质量可量化评估，评估指标写入 span 属性（eval.* 三键生产填值——兑现 5.7 OD-2），支持基于评估结果的质量改进与漂移检测（FR-EV-02——5.9 CUSUM / 5.10 Checkpoint 集成的评估数据源）。

### 业务价值

Epic 5「单 Agent 战略规划能力」价值组可观测性族第二 Story：5.7 交付了全链路追踪基础设施（span 通道 + eval.*/drift.* 键常量注册——**值生产归本 Story**），本 Story 交付**评估面**——`EvaluationHarness.evaluate(AgentWorkflowResult)` 返回 `EvaluationResult(hallucination_score, context_relevance, confidence_accuracy, overall_score)`，三维质量画像（幻觉/证据支撑/校准）经 UDMR in-band 动态路由选择评估模型（区别于既有 bootstrap 定格的 SSOT 静态接线——**仓内首个 per-call 动态路由消费方**），评估结果写入 agent_execution 根 span 的 `eval.hallucination_score`/`eval.context_relevance`/`eval.confidence_accuracy` 三键（5.7 SpanAttributeKeys 契约兑现）。主链接入采用可观测附加面哲学（评估失败降级 warning 不阻断工作流）。这是 FR-EV-02 的闭环 Story，也是 sisys-core-domain-design.md §17.3.8（L1594-1702）评估面的落地：5.9（CUSUM 漂移检测消费 overall_score 连续序列 + drift.detected 填值）、5.10（评估历史入 Checkpoint）全部以本 Story 的 EvaluationResult 为数据源。

**范围权威**：epics_v1.0.md L1765-1811（AC + 实现内容 + 测试要求 + 性能锚 L1794 评估延迟 P95<500ms）、L466（FR-EV-02 P0）、L1444（依赖 Story 5.7，P0-8）、L685（Epic 5 含 EV-01/02）；sisys-core-domain-design.md §17.3.8（L1594-1702——EvaluationHarness.evaluate/compute_context_relevance/compute_confidence_accuracy/L1681 校准公式钦定/OD-1 实现注记 L1600-1611——5.7 嵌入）、§17.4（L2954 Agent 评估 + CUSUM）；architecture.md §14.4 可观测性设计（L2626-2643 交付注记——「评估指标面（eval.* 生产填值）归 Story 5.8」）、L2944（Agent 评估：Phoenix/Arize 开源方案）；5-7 故事范围边界表（L35-46 与 5.8 的精确切分）+ OD-1/OD-2 承接声明（L52-53）+ R1-DF3 缝隙登记（L919）+ R3-6 白名单前瞻（L910）。

### 范围边界（与后续 Story 的精确切分）

| 能力 | 本 Story（5.8） | 后续 Story |
|------|----------------|-----------|
| `AgentEvaluationPort` + `EvaluationModelResolverPort` 双端口 + `EvaluationResult` DTO + 权重常量（application/ports/agent_evaluation.py） | ✅ 新建 + 契约测试 ×2 | — |
| `EvaluationHarness` 应用服务（幻觉检测 LLM 调用 + compute_context_relevance + compute_confidence_accuracy + overall 加权 + evaluate 编排） | ✅ application/services | — |
| 幻觉检测 Schema + prompt 模块（evaluation_schemas.py + evaluation_prompts.py——扁平 Schema） | ✅ | — |
| 评估模型 UDMR in-band 动态路由（UdmrEvaluationModelResolver——decide() → selected_model → per-call LLMConfig） | ✅ infrastructure/routing | — |
| `AgentEvaluationError`（EXCEPTION_450——evaluation 子域 450-459 新开） | ✅ domain/exceptions 四件套 | — |
| 主链接入（use case 第六可选依赖 + execute 末尾评估块 + eval.* 三键写根 span + 降级） | ✅ 纯附加（None 默认向后兼容） | — |
| 评估延迟 P95<500ms（Fake LLM 评估管线口径——委托计时） | ✅ 集成 + 验收 AC-5 | — |
| 5-7 AC-4.3 构造签名断言更新（五依赖 → 六依赖基线） | ✅ 5-7 资产触碰登记 | — |
| eval.* 三键生产填值（OD-2[5.7] 兑现——经 SpanAttributeKeys 常量） | ✅ | — |
| CUSUMDriftDetector / is_drifted / trigger_recalibration / drift.detected 填值 | ❌ 不做（ADR-012——epics 5.9） | 5.9（消费本 Story overall_score） |
| 评估历史 eval_history / hallucination_trend / 趋势追踪 | ❌ 不做（epics 5.10） | 5.10（CheckpointWithEvaluation——依赖 6.3） |
| CheckpointWithEvaluation / to_checkpoint_snapshot | ❌ 不做 | 5.10 |
| eval.* 指标 Prometheus 导出 + Grafana 仪表盘（§17.3.8 L1708-1715 §2.5 集成表） | ❌ 不做（愿景面——epics 5.8 AC 未要求；span 通道是本 Story 交付面） | V1 按需立项（监控域扩展） |
| OpenInference LLM span 语义约定（llm.* 属性族）/ arize-phoenix-client / phoenix.evals 内置评估器 | ❌ 不做（OD-1[5.7] 触发条件裁定**不满足**——自有 Schema + structured_generate 同构达成，零新依赖零白名单变更） | V1 按需评估（deferred-work OD-1[5.7] 条目保持） |
| 上下文相关性 LLM-as-a-Judge / embedding 向量相似度通道 | ❌ 不做（OD-3——伪码算法空白的 MVP 启发式裁定） | V1 按需（deferred-work 登记） |
| 评估 REST API / CLI 命令 | ❌ 不做（嵌入式可观测基础设施——5.7 同款定位） | 无规划（消费方出现时立项） |
| 评估开关环境变量（AGENT_EVALUATION_ENABLED 类） | ❌ 不做（YAGNI——组合根必选注入 + 失败降级；UDMR_ENABLED 既有开关面已覆盖模型路由层） | 运维需求出现时评估 |
| `run_with_evaluation` 独立包装类形态（§17.3.8 伪码 L1629 形态） | ❌ 不做（5.7 DC-4 已裁定接入形态=use case 内嵌装饰器/写入块——伪码形态演化归宿） | — |
| RoutingDecided 事件语义扩展（评估专用路由事件类型） | ❌ 不做（复用既有 RoutingDecided——评估调用成本经 CostMetricsListener 既有订阅面统计） | — |

### 偏离声明（Deviation Declarations）

| # | 偏离 | 规划原文 | 偏离理由与归宿 |
|---|------|---------|---------------|
| OD-1 | 测试文件命名从仓内惯例不从 epics 占位名：`tests/unit/application/services/test_evaluation_harness.py`（epics 占位 `tests/unit/architecture/test_evaluation_harness.py`）+ `tests/unit/architecture/test_arch_evaluation.py`（AST 架构验证器——per-story 惯例）+ `tests/integration/test_integration_agent_evaluation.py`（epics 占位 `test_evaluation_integration.py`） | epics_v1.0.md L1803-1804（测试文件占位名） | 5-7 OD-3 同款注记：epics 占位名是规划文本，仓内惯例（unit 按层归目录/test_arch_* 前缀/test_integration_* 前缀/test_acceptance_agent_evaluation 命名族）是活代码事实源；规划占位名与仓内惯例的正常偏差，随本 OD 知悉不进台账 |
| OD-2 | 幻觉检测不引入 `phoenix.evals.llm_eval_binary_classifier`——以 `LLMClientPort.structured_generate(prompt, response_schema=HallucinationEvaluationSchema, config=UDMR 路由产物)` 实现同构语义（LLM 结构化输出幻觉评分 [0,1] + rationale） | sisys-core-domain-design.md §17.3.8 L1615（`from phoenix.evals import llm_eval_binary_classifier` 伪码）+ L1651-1654 | ①5.7 OD-1 已裁定不引入 arize-phoenix 运行时依赖（依赖树钉 opentelemetry-sdk==1.45.0 强制升级仓内 ^1.21.0 栈——回归面不可控）；②**OD-1[5.7] 触发条件本 Story 裁定不满足**：幻觉检测只需「LLM 结构化评分」语义，自有扁平 pydantic Schema（ge/le 域约束）+ structured_generate 三策略级联解析（litellm_llm_client.py L729-785）完整达成——无需 OpenInference llm.* 语义约定、无需 Phoenix evals 内置评估器；③零新依赖 = 零架构白名单变更（5.7 验证器 A/A+ 白名单 {opentelemetry}/{opentelemetry,pydantic,yaml} 不动——R3-6[5.7] 前瞻的「设计内治理点」不触发）；④deferred-work OD-1[5.7] 条目追加处置注记（触发条件裁定记录），条目本体保持 V1 按需评估归宿。**binary_classifier → [0,1] 连续评分的语义宽化**：Phoenix binary 分类（hallucinated/factual 二值）在 span 属性与 CUSUM 连续序列消费（5.9 累积和算法需要连续量）下连续评分信息量更优——评分语义钉死见 OD-5 |
| OD-3 | `compute_context_relevance` 算法 MVP 裁定为**证据支撑度确定性启发式**：`citations 非空 +0.4 / artifacts_snapshot 非空 +0.3 / tool_trace 非空 +0.3`（三元加权，空元组零分，域 [0,1]） | sisys-core-domain-design.md §17.3.8 L1657-1659（`compute_context_relevance(result.evidence_package)` 伪码——**算法体空白**，未定义计算方式）+ epics L1778 | ①伪码只给方法签名未给算法——MVP 必须裁定可实施口径；②确定性启发式零外部依赖（无 LLM/embedding 调用——评估延迟预算内、测试确定性、无网络失败面）；③语义可辩护：Agent 回答的「上下文相关性」MVP 形态 = 证据包支撑度（引用源/工件快照/工具轨迹三要素——TaskEvidencePackage 九字段中 citations/artifacts_snapshot/tool_trace 恰是证据三元组）；④可测试性：全空 0.0 / 全满 1.0 / 部分组合——参数化精确断言。**V1 升级通道**：LLM-as-a-Judge（RelevanceEvaluationService 先例——同为「回答 vs 证据」评估语义）或 embedding 余弦（EmbeddingServicePort + cosine_similarity——注意后者在 infrastructure 层需抽提纯函数）。**Task 0.7 随 deferred-work.md 登记**（gap 四要素：描述/触发条件/归宿/承接方链接） |
| OD-4 | `compute_confidence_accuracy` 的 `actual` 口径裁定：`actual_quality = (1.0 - hallucination_score) × 0.5 + context_relevance × 0.5`（幻觉事实性与证据支撑的均权「实际质量」）；校准公式照抄 §17.3.8 钦定 `1.0 - min(abs(predicted - actual), 1.0)` | sisys-core-domain-design.md §17.3.8 L1662-1665（`actual=eval_result.quality_score`——伪码自身缺陷：eval_result 尚未构造完成即被引用，**循环依赖 bug**）+ L1674-1681（公式钦定） | ①伪码 L1664 引用未构造的 eval_result.quality_score——照抄必 NameError；②「实际质量」的合理口径 = 证据面可观测质量（幻觉事实性 + 证据支撑）——置信度校准语义即「Agent 自报置信度与证据面实际质量的偏差」；③均权 0.5/0.5 是最小假设形态（无先验偏置——与 overall 三维加权 0.4/0.35/0.25 刻意不同权，避免 actual 与 overall 同构循环强化）；④predicted = `result.evidence.confidence`（verify 阶段 LLM 结构化输出折算——TaskEvidencePackage 字段，[0,1] VO 校验）。权重常量单源（EVALUATION_WEIGHTS——Task 0.1 定义） |
| OD-5 | `hallucination_score` 语义钉死为**字面幻觉程度**：0.0 = 无幻觉（完全事实）、1.0 = 完全幻觉（越高越坏）——与 eval.context_relevance / eval.confidence_accuracy（越高越好）方向相反；`overall_score = (1 - hallucination_score) × 0.4 + context_relevance × 0.35 + confidence_accuracy × 0.25`（反转加权——三键方向归一后求和） | epics_v1.0.md L1778（EvaluationResult 字段名——语义未定义）+ §17.3.8 L1671（`overall_score=self.weighted_sum(...)`——权重未定义） | ①字段名 hallucination_score 的字面语义即幻觉程度（Phoenix 生态惯例：hallucination 评估器输出幻觉概率——越高越坏）；②若反转为「事实性评分」则字段名与语义相反（hallucination_score 高 = 幻觉少——误导性更强）；③overall_score 必须是「越高越好」的质量分（5.9 CUSUM 消费 overall_score 做漂移累积——方向一致性前提），故公式显式反转 (1 - hallucination_score)；④三维权重 0.4/0.35/0.25（幻觉检测是质量核心 > 证据支撑 > 校准）——SYS AGENT 五维评分先例形态（architecture.md §17.4 L2950——加权和是既有设计语言）；⑤权重常量单源 + 和为 1.0 断言（防漂移） |

> 优先级双锚说明（非偏离）：epics L466 将 FR-EV-02 定级 P0（功能等级），epics L1444 执行优先级 P0-8（执行序——依赖 5.7 完成后执行）。两者不矛盾：功能等级与执行序双锚（5.7 同款注记）。

---

## 🔗 前置依赖（全部 ✅ 已完成，无阻塞）

| 依赖 | 组件 | 用途 | 状态 |
|------|------|------|------|
| Story 5.7 | `AgentTracingPort` + `SpanHandle` + `SpanAttributeKeys`（src/application/ports/agent_tracing.py——L125-127 三键 `EVAL_HALLUCINATION_SCORE`/`EVAL_CONTEXT_RELEVANCE`/`EVAL_CONFIDENCE_ACCURACY` **本 Story 生产填值**；L131-139 SpanNames）+ `@trace` 装饰器（src/application/tracing.py——agent_execution 根 span 在 execute 方法体外层存活）+ 根 span 属性写入块先例（run_agent_workflow.py L169-185——`get_current_span()` + `is_recording()` 守卫 + MVP 十属性逐键写入）+ 组合根注册区段形态（composition_root.py L2964-2993）+ `_wire_agent_tracing` 降级接线先例（L3037-3054）+ OTel 测试通道分派 SSOT（链级 initialize 全局通道/组件级注入通道 + reset_for_testing 双复位——5-7 测试隔离约束节） | span 写入通道 + 键常量契约 + 测试形态 | ✅ done（v2.2.1） |
| Story 5.3 | `AgentWorkflowResult` 五字段 DTO（src/application/ports/agent_workflow.py L224-238——chain/evidence/workflow_status/retry_count/executed_phases——**evaluate 的输入**）+ `RunAgentWorkflowUseCase`（src/application/use_cases/run_agent_workflow.py L66-73 五依赖构造器 + L90 `@trace` execute + L162-186 结果组装与属性写入块——**主链接入点**）+ `AgentWorkflowService._structured_call` 444 包装纪律（L430-487——LLM 族异常传播模板）+ Fake LLM 手工装配先例（tests/acceptance/test_acceptance_agent_workflow.py L185-276——AsyncMock(spec=LLMClientPort) + Schema 身份分派） | 评估输入模型 + 接入宿主 + 调用纪律模板 | ✅ done |
| UDMR 资产（Story 1.17 + 审计修复 F1/F2） | `UdmrPolicyPort`（src/domain/ports/udmr_policy.py L14-41）+ `UDMRService.decide()`（src/domain/services/udmr_service.py L63-134——L1 合规→policy.route→健康检查→RoutingDecided 发布→决策日志；**评估模型路由的决策入口**）+ `UDMRTask` VO（src/domain/value_objects/udmr_task.py L14-61）+ `RoutingDecided` 事件（src/domain/events/routing_events.py L15-61——route_type/selected_model/fallback_reason）+ `UDMRConfig`/`CloudModelConfig`（src/infrastructure/config/udmr.py——cloud_configs/local_model/llm_timeout）+ 组合根注册（composition_root.py L1595-1707——udmr_policy/cloud_health_checker/udmr_service/udmr_handler 四注册块）+ `StaticUdmrPolicy`（src/infrastructure/routing/udmr_policy.py L18-74）+ `ComplianceGatewayImpl`（src/infrastructure/security/compliance_gateway_impl.py L57-141——纯本地正则计算，无外部 IO） | 评估模型 in-band 路由决策链 | ✅ 就绪 |
| LLM 调用面 | `LLMClientPort.structured_generate`（src/domain/ports/llm_client.py L162-191——response_schema type[Any] 零 pydantic 依赖 + 三策略级联 JSON 解析 L729-785 + anthropic tools 通道 L644-655——**扁平 Schema 约束**：嵌套 Schema 服务端栈溢出，litellm_llm_client.py L630-637 注记）+ `LLMConfig` frozen dataclass（L23-109）+ `_build_llm_config_from_cloud_model` 转换器先例（litellm_llm_client.py L312-332——CloudModelConfig→LLMConfig 字段映射模板）+ `build_default_llm_config` SSOT 工厂（src/infrastructure/config/llm.py L13-41——**区别锚**：本 Story per-call 动态路由 vs 既有 bootstrap 定格）+ 温度分档先例（agent_workflow_service.py L94-100 TEMPERATURE_PROFILE——verify 档 0.1）+ per-call timeout 先例（L104 `_DEFAULT_PER_CALL_TIMEOUT_SEC = 8.0`） | 幻觉检测 LLM 调用 + config 派生纪律 | ✅ 就绪 |
| 评估型服务先例 | `RelevanceEvaluationService`（src/application/services/relevance_evaluation_service.py L59-160——单依赖注入 + prompt 模块 + pydantic Schema + isinstance 守卫 + LLM 族异常包装——**评估型 LLM-as-a-Judge 最近先例**）+ `relevance_schemas.py`/`relevance_prompts.py`（Schema/prompt 模块分文件先例）+ `RelevanceEvaluationError(360, ExternalException)`（src/domain/exceptions/relevance_exceptions.py——评估异常先例）+ `DebateEvaluator`（src/domain/services/debate_evaluator.py——纯算法评估器先例） | 服务/Schema/prompt/异常四件形态模板 | ✅ 就绪 |
| 异常体系 | `SystemException`/`BusinessException`/`ExternalException` 三基类 + `_code_ranges.py` CODE_RANGES 表（L18-135——**agent 段 440-449 已满**[L131 注记]，450-459 未被占用——新开 evaluation 段依据）+ `LLMAPIError(330)`/`LLMResponseError(331)`/`LLMConfigError(332)`（llm_exceptions.py）+ `AgentWorkflowError(444)`（agent_exceptions.py L200-248——LLM 族传播策略 docstring L207-209：330/331 包装携 phase、332/CancelledError 透传）+ `EXCEPTION_HTTP_MAP`（src/interfaces/api/exception_handlers.py L140-283）+ 新增异常 4 项 checklist + `test_code_ranges.py`/`test_error_code_uniqueness.py` CI 校验 | AgentEvaluationError 落位 | ✅ 就绪 |
| 数据模型 | `TaskEvidencePackage` 九字段 VO（src/domain/value_objects/task_evidence.py L39-150——confidence [0,1] VO 校验 L116-125 / citations / artifacts_snapshot / tool_trace 三元组）+ `ChainOfThought` 五字段 VO（src/domain/value_objects/chain_of_thought.py L33-106——input_summary 任务理解参照 / final_answer 被评估回答[JSON 尾段]）+ `AgentWorkflowResult`（application/ports/agent_workflow.py L224-238） | 评估输入材料 | ✅ 就绪 |
| 测试基建 | `tests/acceptance/conftest.py`（acceptance_env_config L99-106 + 文件名服务 marker 自动挂载 L110-140 + `_bootstrap_once` session 闩）+ 模块级 event_loop fixture 惯例（5-7 显式定义形态 phoenix_tracer.py L61-66）+ `_run_async` 同循环调度 + 步骤化门控 skip 先例（5-6 最新形态）+ 验收 R6 骨架（test_acceptance_phoenix_tracer.py——@scenario 多行字面量显式绑定 + context dict fixture + 延迟 import + 禁 then-pass + 收尾清单场景）+ 集成委托计时模式（`_PERF_CACHE` 单槽缓存 + xdist_group 同 worker 串行 + 常量单源集成定义/验收 import）+ AST 架构验证器形态（test_arch_phoenix_tracer.py——REPO_ROOT + _scan_file_imports + 参数化验证器）+ OTel 全局状态隔离 SSOT（reset_for_testing 双复位 + 凡 initialize 一律双复位义务 + 已知泄漏源 TestInitTracing 点名——5-7 测试隔离约束节） | 验收/集成/架构测试骨架 | ✅ 就绪 |

**移交给本 Story 的留项（必须处置——全部来自 5-7）：**

| # | 留项 | 来源 | 本 Story 处置 |
|---|------|------|--------------|
| 1 | **OD-1[5.7]** OpenInference llm.* 语义约定 / Phoenix evals 内置评估器——触发条件 = 5.8 评估指标 span 化需要时（届时引入 openinference-semantic-conventions / arize-phoenix-client 将击穿 5.7 验证器 A/A+ 白名单——设计内治理点） | deferred-work.md L240 + 5-7 故事 L52/L910 | **Task 0 裁定：触发条件不满足**——幻觉检测以自有 HallucinationEvaluationSchema + structured_generate 同构达成（OD-2），零新依赖零白名单变更；Task 0.7 在 deferred-work OD-1[5.7] 条目追加处置注记（条目本体保持 V1 按需评估归宿——未来 llm.* 语义需求出现时再触发） |
| 2 | **OD-2[5.7]** eval.*/drift.detected 属性生产填值——归宿 5.8（eval.* 三键）/ 5.9（drift.detected） | deferred-work.md L241 + 5-7 故事 L53/L38 | **本 Story 兑现 eval.* 三键**：execute 末尾评估块经 SpanAttributeKeys.EVAL_HALLUCINATION_SCORE/EVAL_CONTEXT_RELEVANCE/EVAL_CONFIDENCE_ACCURACY 常量填值（AC-3.1）；drift.detected 仍归 5.9；Task 0.7 在 deferred-work OD-2[5.7] 条目追加 5.8 兑现注记（eval.* 部分核销） |
| 3 | **R1-DF3** agent_tracing 端口降级态「注册态 + impl 永抛」缝隙（`_wire_agent_tracing` 配置错误时 warning 跳过，但端口仍注册且 impl lambda 每次 resolve 重抛 ConfigurationError——resolve_optional fallback_on 默认不含 ConfigurationError） | deferred-work.md L250 + 5-7 故事 L919 | **Task 0 裁定：本 Story 消费面不触发缝隙**——5.8 的 span 写入走 `get_current_span()` OTel 全局 API（5-7 MVP 十属性块同款先例 run_agent_workflow.py L174-185），**不 resolve agent_tracing 端口**（评估块写入与十属性块同通道同形态）；缝隙本身保持登记（锚位顺延至首个 resolve 消费方——预计 5.9 CUSUM 或独立消费 Story 立项时定夺 fallback_on 扩 ConfigurationError 或降级注册 NoOp 替身）；Task 0.7 在 deferred-work R1-DF3 条目追加 5.8 处置注记（锚位顺延） |
| 4 | **trace_id 全零防呆复核**（NoOp 态全零 32 位 hex 与空串散列进不同版本桶——canary 活跃时 NoOp 流量路由可能翻转——5-7 AC-3 注记「5.8 立项复核时基于此正确事实评估」） | 5-7 故事 L151 | **Task 0 复核结论：评估面零风险**——评估链不消费 trace_id 做路由（幻觉检测 LLM 调用不走工具版本灰度路由——tool_version_policy 是工具执行面通道，评估是 LLM 直调面）；ExecutionContext.trace_id 仅为 span 关联标识。知悉登记（不进 deferred-work——无 gap，复核结论记录于本表） |

---

## 🔗 现有代码继承（必须复用，禁止重复定义）

> ⚠️ **防重复造轮子清单**——以下组件已存在，dev agent 只可「直接复用 / 参考照抄」，禁止新建同义组件。

| 组件 | 文件路径 | 复用方式 |
|------|---------|---------|
| eval.* span 键常量（三键契约） | `src/application/ports/agent_tracing.py` L125-127（SpanAttributeKeys.EVAL_HALLUCINATION_SCORE/EVAL_CONTEXT_RELEVANCE/EVAL_CONFIDENCE_ACCURACY）+ L105-128 常量注册表 docstring（值生产归 5.8） | **直接复用——禁新建同义键常量**（键字符串单一真源——5.7 契约）；评估块逐键引用填值 |
| 根 span 写入块模式 | `src/application/use_cases/run_agent_workflow.py` L169-185（`get_current_span()` + `is_recording()` 守卫 + set_attribute 逐键） | **参考照抄**——评估块紧随 MVP 十属性块之后同形态追加（span 在 execute 返回时 end——end 后写入 no-op，写入必须在方法体内） |
| `_structured_call` LLM 族异常传播纪律 | `src/application/services/agent_workflow_service.py` L430-487（LLMConfigError/CancelledError 透传 L468-473；LLMAPIError/LLMResponseError/TimeoutError/ServiceUnavailableError 包装 L474-480；isinstance Schema 守卫 L481-486） | **纪律照抄**（包装异常改为 AgentEvaluationError 450——评估失败面）；`_build_call_config` 派生形态（L414-428——dataclasses.replace 只覆写温度/超时，连接字段随基底继承）同款 |
| `RelevanceEvaluationService` 评估服务形态 | `src/application/services/relevance_evaluation_service.py` L59-160（单 LLMClientPort 注入 + prompt 构造 + structured_generate + isinstance 守卫 + 异常包装） | **结构参照**——EvaluationHarness 的幻觉检测调用面照此形态（差异：config 来自 UDMR 路由产物而非入参透传/基底派生） |
| `relevance_schemas.py` / `relevance_prompts.py` 分文件先例 | `src/application/services/relevance_schemas.py`（pydantic BaseModel + ge/le 域约束 + reason min_length/max_length）+ `relevance_prompts.py`（SYSTEM_PROMPT + USER_TEMPLATE 模块级常量） | **参考照抄**——evaluation_schemas.py + evaluation_prompts.py 同款分文件 |
| `_build_llm_config_from_cloud_model` 字段映射 | `src/infrastructure/external_services/llm/litellm_llm_client.py` L312-332（api_type/model/endpoint/api_key/temperature/max_tokens/timeout ← CloudModelConfig + llm_timeout） | **参考照抄**——UdmrEvaluationModelResolver 的 cloud→LLMConfig 转换照此字段映射（差异：按 selected_model 匹配而非固定第一 enabled；resolver 是独立类非 llm_client 实例方法） |
| `build_default_llm_config` SSOT 工厂 | `src/infrastructure/config/llm.py` L13-41（UDMR 云端配置优先 → LLMConfig.from_env() 回退） | **区别锚（非照抄）**——既有形态是 bootstrap 定格取第一个 enabled；本 Story 是 per-call 按 decide() 路由产物匹配（UDMRTask→decide→selected_model→匹配 cloud_configs）；两形态并存（执行模型 SSOT 静态 / 评估模型 in-band 动态——epics L1782 AC 钦定「评估模型通过 UDMR 动态路由获取（非硬编码）」） |
| `UDMRService.decide()` 决策入口 | `src/domain/services/udmr_service.py` L63-134（构造签名 `decide(task: UDMRTask, causation_id=None) -> RoutingDecided`；构造器 L39-61 注入原始值） | **直接复用**——resolver 注入既有组合根注册的 udmr_service（composition_root.py L1627-1647）实例 |
| `UDMRTask` VO / `RoutingDecided` 事件 | `src/domain/value_objects/udmr_task.py` L14-61（task_id/input/data_residency/preferred_model/allowed_models）/ `src/domain/events/routing_events.py` L15-61（route_type/selected_model/fallback_reason） | **直接复用**——resolver 构造 UDMRTask(input=评估文本) → decide() → 读 .route_type/.selected_model |
| `UDMRConfig` / `CloudModelConfig` | `src/infrastructure/config/udmr.py`（cloud_configs 列表 / local_model / llm_timeout / from_env） | **直接复用**——resolver 组合根 lambda 构造时传 UDMRConfig.from_env() 原始值（UDMRService 注册先例 L1627-1647 同款「构造器注入原始值」纪律） |
| 端口契约测试 11 维度 + `_DummyResolver` | `tests/contracts/test_port_contract_agent_tracing.py`（112 行——PORT_NAME/EXPECTED_TAGS/REQUIRED_METHODS 类常量 + 11 维度[9 拆 9a/9b] + Dummy 分发） | **参考照抄**——test_port_contract_agent_evaluation.py + test_port_contract_evaluation_model_resolver.py 两份同款结构（Dummy 分发：agent_evaluation 消费 llm_client + evaluation_model_resolver 两端口名；resolver 消费 udmr_service） |
| 验收 R6 骨架 + OTel 通道 SSOT | `tests/acceptance/test_acceptance_phoenix_tracer.py`（模块级 event_loop fixture L61-66 + context dict fixture L88-96 + `_run_async` L98-100 + @scenario 多行字面量绑定 + `_enable_test_tracing` L134-143 链级 initialize 全局通道 + autouse 双复位 L69-85 + Fake LLM 手工装配链 `_assemble_workflow_chain` L361-465 + 延迟 import + 禁 then-pass + 收尾清单场景 L1476-1524） | **参考照抄**——R6 主体基准（PG 模板取 Gherkin 中文关键字与场景组织形态——then-pass/Background 块是 PG 模板历史缺陷禁复制）；eval.* span 断言锚：**装饰器/@trace 链路 span 只经全局 provider 可观测**——链级场景统一 initialize 全局通道 + teardown 双复位 |
| 集成委托计时模式 | `tests/integration/test_integration_phoenix_tracer.py`（`_PERF_CACHE` 单槽缓存 L63-65 + `sample_span_record_perf` L567-610 + warmup 1 + 20 采样 + `statistics.quantiles(latencies, n=20)[18]` exclusive P95 + 常量单源 L39-61） | **参考照抄**——`sample_evaluation_pipeline_perf()` + 常量单源（EVALUATION_P95_LIMIT_SECONDS = 0.5——epics L1794 钦定 500ms）+ xdist_group("agent-evaluation-perf") |
| AST 架构验证器形态 | `tests/unit/architecture/test_arch_phoenix_tracer.py`（REPO_ROOT/SRC_DIR 常量 + `_scan_file_imports`/`_scan_file_full_import_names`/`_scan_instantiation_sites` AST helper + 参数化验证器 A/A+/B/C + 构造签名基线 `_USE_CASE_INIT_PARAMS` L92-107） | **参考照抄**——test_arch_evaluation.py（验证器维度不同：domain 触碰收窄[仅 exceptions 注册三件] + 组合根外零实例化 + use case 六依赖签名基线[扩展 5.7 五依赖基线] + 主链评估块静态锚） |
| Fake LLM 替身（Schema 身份分派） | `tests/acceptance/test_acceptance_agent_workflow.py` L185-276（`AsyncMock(spec=LLMClientPort)` + side_effect 按 `response_schema is XxxSchema` 身份分派返回真实 Schema 实例 + 未预期 Schema 抛 AssertionError） | **参考照抄**——5.8 幻觉检测替身新增 `HallucinationEvaluationSchema` 分派分支（**Schema 两两不同前提**——agent_workflow_schemas.py L9-11 设计决策；评估 Schema 独立新类保前提）；调用断言按 Schema 身份过滤 call_args_list（L555-560 形态） |
| `_RecordingEventPublisher` / 零 IO 仓储替身 | `tests/acceptance/test_acceptance_agent_workflow.py` L163-182（手写 duck-typing 事件捕获锚）+ 5-6 `_StubIsolationSwitchLogRepository`（L146-160） | **参考照抄**——UDMR 链手工装配的事件/决策日志替身（验收禁 mock 豁免面：零 IO 端口替身手写类——5-7 豁免口径 llm_client + sandbox + 零 IO 替身） |
| 域名先例：评估服务命名族 | `relevance_evaluation_service.py`（服务）+ `agent_tracing.py`（端口）+ `agent_workflow.py`（DTO） | **命名甄别**——新端口 `agent_evaluation`（Agent 评估可观测族——与 `agent_tracing` 同族命名；**区别于检索域 `RelevanceEvaluationPort`**：后者评估「查询 vs SearchResult 检索质量」[domain/ports/relevance_evaluation.py L71-127——字段 context_relevance 同名但语义是检索结果相关性]，本 Story 评估「Agent 回答 vs 证据包输出质量」——两端口语义分立，字段名撞车已在 Task 0.2 契约文档显式甄别登记） |

**明确不存在、本 Story 需新建**（全仓 grep 验证：`EvaluationHarness|AgentEvaluationPort|EvaluationModelResolver|AgentEvaluationError|HallucinationEvaluationSchema|compute_context_relevance|compute_confidence_accuracy` 在 `src/` 零命中[仅 5-7 注释锚点 agent_tracing.py L56 docstring 预告]；`evaluation_exceptions`/`evaluation(450` 零命中；per-call UDMR 消费模式[decide() → LLMConfig → structured_generate]全仓零先例——Agent A 调研确认 RoutingDecided.selected_model 无任何 LLMConfig 构造消费方）：

1. `AgentEvaluationPort` + `EvaluationModelResolverPort` + `EvaluationResult` + `EVALUATION_WEIGHTS` 常量（src/application/ports/agent_evaluation.py——评估族端口聚合文件）
2. `EvaluationHarness`（src/application/services/evaluation_harness.py——AgentEvaluationPort 实现）
3. `HallucinationEvaluationSchema`（src/application/services/evaluation_schemas.py——扁平 pydantic Schema）
4. 幻觉检测 prompt 模块（src/application/services/evaluation_prompts.py）
5. `UdmrEvaluationModelResolver`（src/infrastructure/routing/udmr_evaluation_model_resolver.py——EvaluationModelResolverPort 实现）
6. `AgentEvaluationError`（src/domain/exceptions/evaluation_exceptions.py——EXCEPTION_450 + evaluation 子域 450-459 新开）
7. 主链评估块（修改：run_agent_workflow.py——第六可选依赖 + execute 评估块；**纯附加 None 默认向后兼容**）
8. 组合根 `# === Story 5.8 ===` 区段（双端口注册 + use case lambda 更新）
9. 测试八件：`tests/unit/domain/exceptions/test_evaluation_exceptions.py` / `tests/unit/application/services/test_evaluation_harness.py` / `tests/unit/infrastructure/routing/test_udmr_evaluation_model_resolver.py` / `tests/contracts/test_port_contract_agent_evaluation.py` / `tests/contracts/test_port_contract_evaluation_model_resolver.py` / `tests/integration/test_integration_agent_evaluation.py`（全链 + 计时委托常量单源）/ `tests/unit/architecture/test_arch_evaluation.py` / `tests/acceptance/test_acceptance_agent_evaluation.{feature,py}`
10. 5-7 资产触碰：`tests/acceptance/test_acceptance_phoenix_tracer.py`（AC-4.3 构造签名基线更新——五依赖 → 六依赖）
11. 异常注册三件：`src/domain/exceptions/_code_ranges.py`（evaluation 子域 + _CLASS_TO_SUBDOMAIN）+ `src/domain/exceptions/__init__.py`（导出）+ `src/interfaces/api/exception_handlers.py`（EXCEPTION_HTTP_MAP 450→500）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: EvaluationResult 模型与三维指标计算（幻觉检测 LLM 调用 + 证据支撑度 + 校准公式）

**Given** Agent 工作流执行完成产出 `AgentWorkflowResult`（chain 五字段 + evidence 九字段——confidence ∈[0,1] VO 校验 + executed_phases）与评估链装配完成（Fake LLM[AsyncMock spec=LLMClientPort + HallucinationEvaluationSchema 身份分派] + 权重常量）
**When** 调用 `EvaluationHarness.evaluate(result)`
**Then** 返回 `EvaluationResult(hallucination_score, context_relevance, confidence_accuracy, overall_score)` 四字段 frozen dataclass（[0,1] 分数域校验——越界抛 `ValidationError` 201）：①**幻觉检测**——经 `llm_client.structured_generate(prompt=三要素 prompt, response_schema=HallucinationEvaluationSchema, config=UDMR 路由产物派生 config)` 返回 Schema 实例（hallucination_score ge=0.0 le=1.0 + rationale 非空——扁平 Schema 零嵌套），`isinstance(result, HallucinationEvaluationSchema)` 守卫（非实例包 AgentEvaluationError 450）；prompt 三要素 = `chain.input_summary`（任务理解参照）+ 证据摘要（evidence.citations/tool_trace/confidence_rationale 简编）+ `chain.final_answer`（被评估回答——JSON 尾段）；②**上下文相关性**——`compute_context_relevance(evidence)` 证据支撑度三元加权（citations 非空 +0.4 / artifacts_snapshot 非空 +0.3 / tool_trace 非空 +0.3——OD-3 裁定，纯同步计算零外部调用）；③**置信度校准**——`compute_confidence_accuracy(predicted=result.evidence.confidence, actual=actual_quality)` 钦定公式 `1.0 - min(abs(predicted - actual), 1.0)`（§17.3.8 L1681），actual_quality = `(1.0 - hallucination_score) × 0.5 + context_relevance × 0.5`（OD-4 口径）；④**overall**——`(1.0 - hallucination_score) × 0.4 + context_relevance × 0.35 + confidence_accuracy × 0.25`（OD-5 反转加权——三键方向归一）；权重常量单源（EVALUATION_WEIGHTS——和为 1.0 断言）
**And** 幻觉检测 config 派生纪律：`dataclasses.replace(resolver 产物, temperature=0.1, timeout=8.0)`——评估温度低温（verify 档 0.1 先例——评估判定任务需要确定性）+ per-call timeout 显式 ≤8.0s（`_DEFAULT_PER_CALL_TIMEOUT_SEC` 先例——禁依赖 from_env 默认 600s）；连接字段（api_type/model/endpoint/api_key/max_tokens）随路由产物继承（`_build_call_config` L414-428 同款纪律——防裸 LLMConfig() 丢连接字段）；异常契约：`LLMConfigError`/`asyncio.CancelledError` 透传不包装，`LLMAPIError`/`LLMResponseError`/`TimeoutError`/`ServiceUnavailableError` 包装为 `AgentEvaluationError`（EXCEPTION_450）携 context（`{phase: "evaluation", reason: ...}` 形态）`from error`

**验证标准/Validation Criteria:**
- [ ] EvaluationResult 构造/四分数域 [0,1] 校验（越界参数化——201 三段式断言：isinstance → code EXCEPTION_201 → context 字段名）/ frozen 不可变断言
- [ ] 幻觉检测：Fake LLM 按 Schema 身份分派返回真实 Schema 实例 → evaluate 返回 hallucination_score 与 Fake 注入值相等 + structured_generate 调用断言（prompt 含三要素 + response_schema is HallucinationEvaluationSchema + config.temperature == 0.1 + config.timeout == 8.0）
- [ ] Schema 校验失败路径（Fake 返回非 Schema 实例 → isinstance 守卫 → 450）+ LLM 族异常包装矩阵（LLMAPIError→450 包装 / LLMConfigError 透传 / CancelledError 透传——三段式 context["caught"] 断言）
- [ ] compute_context_relevance 参数化四态（全空 0.0 / 仅 citations 0.4 / citations+tool_trace 0.7 / 全满 1.0——精确值断言）
- [ ] compute_confidence_accuracy 数值矩阵（predicted==actual → 1.0 / |diff|≥1.0 → 0.0 / |diff|=0.3 → 0.7——公式钦定锚）
- [ ] overall 加权数值断言（给定三指标输入 → overall 精确值 == 公式手算值）+ EVALUATION_WEIGHTS 和为 1.0 元断言（防权重漂移）
- [ ] HallucinationEvaluationSchema 扁平性（零嵌套模型——anthropic 通道约束）+ ge/le 域约束（越界 pydantic 校验失败用例）+ 与既有五 Schema 类对象两两不同（身份分派前提——`is not` 断言）

### AC-2: 评估模型 UDMR in-band 动态路由（非硬编码）

**Given** 真实 UDMR 决策链手工装配（真实 `UDMRService`[domain service 真实实例——构造器十参数对齐组合根 L1627-1647 装配形态] + 真实 `StaticUdmrPolicy`（注入测试 cloud_configs）+ 真实 `ComplianceGatewayImpl`（纯本地正则）+ 真实 `StaticTokenEstimator` + 真实 `build_cost_calculator()`（两者纯计算零 IO——决策日志 Token/成本计算依赖）+ 手写零 IO 事件替身 `_RecordingEventPublisher` + 手写零 IO 决策日志替身 + 健康检查替身[True/False 可控——路由方向控制]）构造 `UdmrEvaluationModelResolver`
**When** 调用 `resolver.resolve_config(input_text=chain.final_answer)`
**Then** 内部执行 in-band 消费链：构造 `UDMRTask(task_id=uuid4(), input=input_text, data_residency="CHINA_DOMESTIC", preferred_model="", allowed_models=[])` → `await udmr_service.decide(task)` → 依 `RoutingDecided.route_type/selected_model` 构造评估 `LLMConfig`：**cloud 路由**——从注入 cloud_configs 按 `model == selected_model` 匹配（**非「第一个 enabled」**——区别于 build_default_llm_config SSOT 形态）→ LLMConfig(api_type/model/endpoint/api_key/temperature/max_tokens ← 匹配条目 + timeout ← llm_timeout——`_build_llm_config_from_cloud_model` L312-332 字段映射同款）；**local 路由**——`dataclasses.replace(LLMConfig.from_env(), model=selected_model)`（本地连接字段随 from_env，模型名对齐路由产物）；**匹配失败**（selected_model 不在 cloud_configs——配置漂移）→ `AgentEvaluationError` 450 携 context（`{selected_model, available_models}`——诊断信息）——禁静默回退
**And** 路由决策副作用真实发生：`RoutingDecided` 事件经 publisher 发布（零 IO 替身捕获断言——事件 route_type/selected_model 与返回 config 对应）；决策日志持久化调用发生（零 IO 替身捕获）；**非硬编码判别性**：注入两套不同 cloud_configs（模型 A/B）→ resolve_config 返回的 `config.model` 随路由决策变化（硬编码实现则不变——变异实证锚点）；云端健康检查失败 → decide() 内部回退 local（UDMRService 既有行为 L97-104——resolver 消费回退后的 route_type=="local" 走 local 分支）；合规注意：UDMRTask.input 过 ComplianceGateway 敏感数据/PIPL 正则（compliance_gateway_impl.py L87-108——评估文本命中即 forced_local，是合法路由行为非缺陷）

**验证标准/Validation Criteria:**
- [ ] cloud 路由：健康检查替身 True + 单云端配置 → config.model == cloud.model + endpoint/api_key 逐字段相等 + timeout == llm_timeout
- [ ] local 路由：健康检查替身 False（云端不可用回退）→ config.route 对应 local 分支（config.model == selected_model == local_model + 连接字段来自 from_env 形态）
- [ ] 非硬编码判别（双配置矩阵：cloud_configs=[模型A] → config.model==A；cloud_configs=[模型B] → config.model==B——同一 resolver 代码不同注入即不同模型）
- [ ] 匹配失败 450（monkeypatch decide 返回不存在于 cloud_configs 的 selected_model → AgentEvaluationError + context 含 selected_model 与可用清单）
- [ ] RoutingDecided 事件发布断言（替身捕获事件 isinstance + route_type/selected_model 与 config 对应）
- [ ] UDMRTask 构造断言（decide 收到的 task.input == input_text——经 Fake UDMRService 或替身捕获；真实链场景经决策日志替身捕获 task 上下文）

### AC-3: 主链接入——评估执行 + eval.* 三键写根 span + 降级（5.7 OD-2 兑现）

**Given** 工作流链 = 5-7 手工装配形态（Fake LLM[六阶段 Schema 身份分派 + **HallucinationEvaluationSchema 分派分支新增**] + 真实 AgentWorkflowService/LangGraphEngine/RunAgentWorkflowUseCase + 零 IO stub 仓储）+ use case 构造注入 `evaluation_harness`（真实 EvaluationHarness + Fake LLM + resolver 链）+ **链级 initialize 全局通道**（场景级新 TracerProvider + SimpleSpanProcessor + InMemorySpanExporter 经 `PhoenixTracer(config=测试配置, tracer_provider=注入).initialize()`——装饰器/@trace 链路 span 只经全局 provider 可观测，5-7 SSOT）
**When** 调用 `RunAgentWorkflowUseCase.execute(agent_id, task)` 执行六阶段工作流
**Then** execute 末尾（结果组装 L162-168 → MVP 十属性写入块 L169-185 之后、`return result` 之前）评估块执行：`if self._evaluation_harness is not None:` → `await self._evaluation_harness.evaluate(result)` → `span.is_recording()` 守卫下经 `SpanAttributeKeys.EVAL_HALLUCINATION_SCORE`/`EVAL_CONTEXT_RELEVANCE`/`EVAL_CONFIDENCE_ACCURACY` 三常量写入根 span（值 = EvaluationResult 对应字段——**5.7 OD-2 兑现：三键生产填值**）；overall_score 不写 span（5.7 SpanAttributeKeys 契约键表零改动——三键可派生 overall，YAGNI）；工作流返回值与评估块零耦合（result 原样返回——评估不改写工作流结果）
**And** **降级路径**（可观测附加面哲学——5.7 DC-7 同款）：evaluate 抛 `AgentEvaluationError`（450——LLM 调用失败/Schema 校验失败注入）→ `except AgentEvaluationError → logger.warning("评估降级跳过...")` → 主链正常返回 result + span 三键**缺席**（不写哨兵值——OD-2[5.7] 语义歧义论证同款：0.0 可能是合法幻觉分）+ 既有 MVP 十属性不受影响；**未注入路径**（`evaluation_harness=None`——向后兼容默认）：评估块整体跳过 + 行为与 5-3/5-7 完全一致（存量零破坏前提）；**构造签名扩展**：use case 第六可选依赖 `evaluation_harness: AgentEvaluationPort | None = None`（尾部追加——存量五参构造调用零破坏）；**5-7 资产同步**：test_acceptance_phoenix_tracer.py AC-4.3 构造签名断言基线更新（五依赖 → 六依赖——`inspect.signature` 对照，L1351-1376）

**验证标准/Validation Criteria:**
- [ ] 真实链评估执行：InMemory exporter 取 agent_execution span → attributes 含三键且值 == EvaluationResult 字段（Fake LLM 注入的幻觉分 + 启发式计算值 + 校准值逐项手算对照）
- [ ] 三键经 SpanAttributeKeys 常量写入（键字符串逐字 "eval.hallucination_score"/"eval.context_relevance"/"eval.confidence_accuracy"——5.7 契约兑现锚）
- [ ] 降级路径：Fake LLM 幻觉检测分支抛 LLMAPIError → 主链返回正常 result（工作流断言全绿）+ 三键缺席断言（span.attributes 不含三键）+ warning 日志断言（caplog）+ MVP 十属性仍在（降级不伤既有属性块）
- [ ] None 默认路径：不注入 evaluation_harness 构造 use case → execute 行为与 5-7 基线一致（span 树 + 十属性——回归锚）+ 三键缺席
- [ ] 构造签名：六依赖签名断言（inspect.signature 参数清单 == [agent_repository, agent_profile_use_case, agent_engine, agent_workflow_service, isolation_guard, evaluation_harness]——第六参数默认 None）+ 5-7 AC-4.3 断言更新后全绿
- [ ] **5-3/5-7 存量全家回归绿**：test_agent_workflow_service 单测 + 契约×3（service/use_case/engine）+ 图/引擎单测×2 + 5-3 集成/验收 + 5-7 全家（unit×3 + 契约 + integration + acceptance 15 场景——含 AC-4.3 更新后）逐一登记

### AC-4: 端口接线、架构合规与组合根注册

**Given** 双端口、实现、主链评估块全部交付
**When** 验证接线与合规
**Then** 新端口经组合根 `# === Story 5.8 ===` 区段注册且 resolve 可达（PortSpec 元数据对齐 5.7 形态）：①`agent_evaluation`：v1.0.0 / `AgentEvaluationPort` / lambda 注入 `EvaluationHarness(llm_client=resolver.resolve("llm_client"), model_resolver=resolver.resolve("evaluation_model_resolver"))` / module=src.application.services.evaluation_harness / **SINGLETON**（Epic 5 全家政策） / owner=platform / tags=("agent", "evaluation", "observability")；②`evaluation_model_resolver`：v1.0.0 / `EvaluationModelResolverPort` / lambda 注入 `UdmrEvaluationModelResolver(udmr_service=resolver.resolve("udmr_service"), cloud_configs=UDMRConfig.from_env().cloud_configs, local_model=..., llm_timeout=...)`（原始值注入——UDMRService 注册先例 L1627-1647 纪律） / module=src.infrastructure.routing.udmr_evaluation_model_resolver / SINGLETON / owner=platform / tags=("agent", "evaluation", "udmr")；③use case 注册 lambda 更新：`resolve_optional("agent_evaluation")` 注入第六依赖（可选依赖先例——5.6 audit_service resolve_optional composition_root.py L2903）；契约测试 ×2（11 维度 + _DummyResolver——agent_evaluation 的 Dummy 分发 llm_client/evaluation_model_resolver 两端口名，resolver 的分发 udmr_service）
**And** 架构合规：application 触碰文件第三方 import 白名单（evaluation_harness.py/evaluation_schemas.py/evaluation_prompts.py/agent_evaluation.py/run_agent_workflow.py——pydantic[Schema] 与 opentelemetry[span 写入] 均在 5.7 验证器 A+ 全层基线 {opentelemetry, pydantic, yaml} 内，**零白名单变更——OD-1[5.7] 触发条件裁定不满足的实现面证据**）；`agent_evaluation.py` 端口文件零第三方依赖（纯 Protocol + dataclass + 常量）；domain 触碰面收窄（本 Story domain 新增仅 `exceptions/evaluation_exceptions.py` + `_code_ranges.py` + `__init__.py` 异常注册三件——业务域[ports/services/entities/value_objects/events] 零触碰断言）；组合根外零实例化（EvaluationHarness/UdmrEvaluationModelResolver 构造点仅 composition_root.py + tests/）；依赖方向：UdmrEvaluationModelResolver（infrastructure）→ AgentEvaluationPort/LLMConfig（application/domain）合法 ✓；`event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` 零改动（评估不经事件总线——RoutingDecided 是既有事件由 UDMRService 内部发布）；`.env.example` 零改动（无新环境变量——评估温度/超时是代码常量、评估模型经既有 UDMR_* 变量、无评估开关[范围边界表裁定]）

**验证标准/Validation Criteria:**
- [ ] 组合根双注册 + resolve 四件断言（可达/isinstance/PortSpec 元数据/lifetime==SINGLETON——5-7 AC-4.1 同款）
- [ ] use case lambda 注入断言（resolve("agent_workflow_use_case") 实例的 `_evaluation_harness` 非 None 且 isinstance AgentEvaluationPort——**接线可达性**；测试环境 resolve_optional 拿到注册实例）
- [ ] 契约测试 ×2 全绿（11 维度 + REQUIRED_METHODS：agent_evaluation=["evaluate"] / evaluation_model_resolver=["resolve_config"]）
- [ ] AST 验证器 A：application 触碰文件第三方白名单（pydantic/opentelemetry 允许——A+ 基线内；黑名单 pydantic 外新第三方零引入断言）
- [ ] AST 验证器 B：domain 业务域零触碰（_STORY58 业务符号在 domain/ports|services|entities|value_objects|events 零命中 + 评估异常符号仅在 exceptions/ 三件）+ 组合根外零实例化（src/ 扫描构造点）
- [ ] AST 验证器 C：主链评估块静态锚（execute 体内评估调用 + 三常量引用 + is_recording 守卫在位——inspect/AST 扫描）+ use case 六依赖签名基线
- [ ] .env.example 与 event_channels.yaml 零改动断言（git diff 范围守卫或文件内容锚——收尾场景断言面）

### AC-5: 评估延迟 P95<500ms（Fake LLM 评估管线口径——委托计时）

**Given** Fake LLM 即时返回（HallucinationEvaluationSchema 分派零延迟）+ 真实 EvaluationHarness + resolver 链（**计时口径 = 评估管线自身开销**：幻觉检测 structured_generate 调用编排 + 三元启发式 + 校准公式 + overall 加权 + EvaluationResult 构造——LLM 网络延迟不在口径内[外部不可控——真实 LLM 单次调用秒级，epics 500ms 预算对真实网络不可行；5-7 AC-5「测纯进程内开销」同款口径声明]）
**When** 测量评估管线延迟（warmup 1 + 20 采样——`statistics.quantiles(latencies, n=20)[18]` exclusive P95——5-7 委托模式照抄；单次采样 = 完整 evaluate(result) 调用，输入用固定构造的 AgentWorkflowResult）
**Then** P95 < `EVALUATION_P95_LIMIT_SECONDS = 0.5`（epics L1794 钦定 500ms——常量单源定义于集成模块，验收侧 import 禁双真源）；委托计时（`_PERF_CACHE` 单槽缓存 + `xdist_group("agent-evaluation-perf")` 同 worker 串行——验收 AC-5.1 不自跑采样）；采样入口自包含（每次采样独立构造 harness/Fake LLM——无跨场景状态）；**正向锚**：采样轮中 Fake LLM structured_generate 调用计数 == 采样数（防静默降级假绿——评估调用真实发生）；**若实测不达标排查序**：resolver decide() 链路耗时（健康检查 TTL 缓存未命中→每次真探测——健康检查替身 True 固定 + 决策日志替身零 IO）→ prompt 构造字符串拼接量级 → Fake LLM side_effect 分派开销
**And** 真实 LLM 面不承担 P95 断言（验收 LLM 可达场景[若有]仅验证端到端评估产出真值不计时——网络主导不可控；无 LLM 环境按 5-3 先例 Fake 豁免）

**验证标准/Validation Criteria:**
- [ ] P95<500ms：常量单源（集成定义/验收 import）+ 委托缓存命中（验收场景不重复采样）
- [ ] 正向锚：采样批次 structured_generate 调用计数 == warmup + 采样数（Fake LLM call 计数断言）
- [ ] benchmark 场景级标记 + xdist_group 与既有 12 组互异（全仓 grep 断言——agent-workflow-perf/agent-isolation-perf/agent-triple-isolation-perf/isolation-switch-log-perf/phoenix-tracer-perf/agent-instantiation/agent-profile-loading/data-source-cache/sandbox-daemon/tool-executions-pg/tool-versions-pg 等）
- [ ] 口径声明落 docstring（管线开销 vs 网络延迟分述——防后续误读）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] **不新建领域事件、不修改既有事件**——评估是进程内同步可观测面，评估结果经 span 属性 + 返回值传递，不经事件总线；`event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` 零改动。`RoutingDecided`（routing_events.py L15-61）是既有事件，由 UDMRService.decide() 内部发布（评估路由决策复用——其成本统计经既有 CostMetricsListener 订阅面自然覆盖，零新增消费基建）。

#### 数据模型 (Data Models)

- [ ] `EvaluationResult`（`src/application/ports/agent_evaluation.py`，`@dataclass(frozen=True)` 四字段——与 AgentWorkflowResult 同层同风格[application/ports/agent_workflow.py L224-238 先例] + **分数域守卫自设加严**）：
  - 字段：`hallucination_score: float`（0.0=无幻觉 1.0=完全幻觉——OD-5 字面语义）/ `context_relevance: float`（[0,1] 证据支撑度——OD-3）/ `confidence_accuracy: float`（[0,1] 校准准确度）/ `overall_score: float`（[0,1] 质量总分——OD-5 反转加权）
  - `__post_init__` 守卫：四字段均须 `isinstance(x, (int, float))` 且 `bool` 拒 + `0.0 <= x <= 1.0`（越界/类型错抛 `ValidationError` EXCEPTION_201——**应用层输入校验**，模板 §异常契约清单钦定映射；context 携 `{字段名: 实际值}`——242 惯例形态）
- [ ] `HallucinationEvaluationSchema`（`src/application/services/evaluation_schemas.py`，pydantic BaseModel——relevance_schemas.py 先例）：`hallucination_score: float`（`ge=0.0, le=1.0`）+ `rationale: str`（`min_length=1, max_length=1000`——判断理由）；**扁平零嵌套**（anthropic tools 通道嵌套 Schema 服务端栈溢出——litellm_llm_client.py L630-637 注记；与既有五 Schema 类对象两两不同——Schema 身份分派前提）
- [ ] `EVALUATION_WEIGHTS` 权重常量（`src/application/ports/agent_evaluation.py`——评估契约单源）：`HALLUCINATION_WEIGHT = 0.4` / `CONTEXT_RELEVANCE_WEIGHT = 0.35` / `CONFIDENCE_ACCURACY_WEIGHT = 0.25`（overall 三维——和为 1.0）/ `ACTUAL_FACTUAL_WEIGHT = 0.5`（actual_quality 均权——OD-4）/ `CONTEXT_CITATION_WEIGHT = 0.4` / `CONTEXT_ARTIFACT_WEIGHT = 0.3` / `CONTEXT_TOOL_TRACE_WEIGHT = 0.3`（证据支撑度三元——和为 1.0）；评估调用常量（`src/application/services/evaluation_harness.py` 模块级——TEMPERATURE_PROFILE 先例形态）：`EVALUATION_TEMPERATURE = 0.1`（verify 档先例）/ `EVALUATION_TIMEOUT_SEC = 8.0`（per-call timeout 先例）
- [ ] **本 Story domain 层数据模型零新增**（EvaluationResult 是应用层 DTO——评估是可观测应用面非领域概念，5-7 DC-2「追踪非领域概念」同款论证；domain 触碰仅 exceptions 注册三件——见异常契约节）

#### 统一端口定义注册与管理 (Port Contract)

- [ ] `AgentEvaluationPort`（`src/application/ports/agent_evaluation.py`，`@runtime_checkable Protocol`——**R2 具体应用端口**：Agent 评估可观测族[5.7-5.9]的应用契约，与 agent_tracing 同层同族；**端口命名甄别**：区别于检索域 `RelevanceEvaluationPort`[domain/ports/relevance_evaluation.py——评估「查询 vs SearchResult 检索质量」]，本端口评估「Agent 回答 vs 证据包输出质量」——两端口语义分立，其 TypedDict `context_relevance` 字段与本 Story EvaluationResult 同名属巧合撞名，契约文档显式登记）：
  - `async def evaluate(self, result: AgentWorkflowResult) -> EvaluationResult`——评估 Agent 工作流输出质量（幻觉检测 LLM 调用 + 证据支撑度 + 置信度校准 + overall 加权）。Args: result 工作流结果（AgentWorkflowResult 五字段——evaluate 只读不改写）。Returns: EvaluationResult 四分数。Raises 契约：`AgentEvaluationError`（450——幻觉检测 LLM 调用失败包装[LLMAPIError/LLMResponseError/TimeoutError/ServiceUnavailableError] / Schema 实例校验失败 / 路由产物匹配失败）；`LLMConfigError`（332）与 `asyncio.CancelledError` **透传不包装**（_structured_call L468-473 同款纪律）；`ValidationError`（201——EvaluationResult 分数域守卫，理论不可达[输入域已约束]防御层）
- [ ] `EvaluationModelResolverPort`（同文件，`@runtime_checkable Protocol`——**R2 具体应用端口**：评估调用模型解析契约；**R3 落点**：UDMR 路由 + cloud_configs 匹配是技术实现面——infrastructure 实现可替换[静态配置解析/多路由源]，支持扩展其他同类技术实现）：
  - `async def resolve_config(self, input_text: str) -> LLMConfig`——解析评估调用的 LLM 配置（UDMR in-band 动态路由：UDMRTask → decide() → selected_model → per-call LLMConfig——区别于 bootstrap 定格的 SSOT 静态接线）。Args: input_text 被评估文本（UDMRTask.input——合规检测与 token 估算输入）。Returns: LLMConfig（cloud 匹配条目或 local 形态）。Raises: `AgentEvaluationError`（450——路由产物匹配失败[配置漂移]；UDMRService 内部异常上抛面由其自身契约决定——decide() 的合规降级是 forced_local 非异常）
- [ ] 组合根注册元数据（Task 0 定义、Task 1 落地）：`agent_evaluation`：v1.0.0 / AgentEvaluationPort / EvaluationHarness（lambda 双 resolve：llm_client + evaluation_model_resolver）/ module=src.application.services.evaluation_harness / SINGLETON / owner=platform / tags=("agent", "evaluation", "observability")；`evaluation_model_resolver`：v1.0.0 / EvaluationModelResolverPort / UdmrEvaluationModelResolver（lambda：resolve("udmr_service") + UDMRConfig.from_env() 原始值）/ module=src.infrastructure.routing.udmr_evaluation_model_resolver / SINGLETON / owner=platform / tags=("agent", "evaluation", "udmr")
- [ ] **既有组件消费方变更（契约变更登记 ×1）**：`RunAgentWorkflowUseCase.__init__` 第六可选依赖 `evaluation_harness: AgentEvaluationPort | None = None`（尾部追加——存量五参调用零破坏）+ execute 末尾评估块（~12 行：None 守卫 + evaluate 调用 + 三键写入 + AgentEvaluationError 降级 catch）——**5-7 资产同步**：test_acceptance_phoenix_tracer.py AC-4.3 构造签名基线更新（五依赖 → 六依赖）
- [ ] 端口契约测试两份（`tests/contracts/test_port_contract_agent_evaluation.py` + `test_port_contract_evaluation_model_resolver.py`，11 维度 + _DummyResolver 各一份——Dummy 分发端口名：前者 llm_client/evaluation_model_resolver、后者 udmr_service）
- [ ] **禁止**在服务文件本地定义 Protocol/Port 抽象（EvaluationResult/双端口定义在端口文件，服务只 import）；**禁止**新建语义重复端口（禁新建 evaluation/harness/quality 同义端口；RelevanceEvaluationPort 检索域既有面不碰；MetricsPort 已有面不碰）

#### 端口契约清单执行约束（强制）
- [ ] 本 Story 端口清单唯一真源 = 本 Task 0 定义（`agent_evaluation` + `evaluation_model_resolver` 两新端口 + 一项既有组件消费方变更：use case 第六依赖——契约变更登记）
- [ ] 禁止新增未登记端口；禁止未同步 registry/resolver/contract test
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> 原则/适用范围/禁止条款同模板基线。**本 Story 新增领域异常 ×1**（evaluation 子域新开）：

- [ ] **归属模块与基类**：新子域 `evaluation`（CODE_RANGES 增 `"evaluation": (450, 459)`——四代开段先例：data_source(410)/debate(420)/tool_version(430)/agent(440)「前段满/语义独立 → 开独立段」，agent 段 440-449 已满[_code_ranges.py L131 注记] + 450-459 全仓未占用[grep 验证]）；基类 **`SystemException`**（评估是系统侧可观测行为——AgentWorkflowError[444] 同族论证「工作流执行属系统侧行为」；评估失败主因[LLM 调用失败]已在 450 包装内携 cause 链，外层语义是「评估管线执行失败」非「外部服务失败」——与 RelevanceEvaluationError[360, ExternalException] 的差异：后者是检索域直调外部评估服务，本 Story 评估是 Agent 可观测族管线[路由+调用+计算+组装]的系统级编排失败面）
- [ ] **唯一编码分配**：`AgentEvaluationError` = EXCEPTION_450；`grep -r "EXCEPTION_450" src/domain/exceptions/` 验证无碰撞
- [ ] **构造器参数设计**：`message/cause/context` 标准三件 + 领域上下文（`agent_id`/`phase="evaluation"`/`reason`——context dict 暴露 `{agent_id, phase, reason}`，对齐 AgentWorkflowError context 三键形态[agent_exceptions.py L243-247]；reason 描述失败环节[llm_call/schema_validation/model_resolution]）
- [ ] **消息安全性**：错误消息面向调用方可理解（不泄露 prompt 全文/endpoint 凭据——LLMAPIError 脱敏先例[endpoint 仅 scheme+hostname]；context 不携带 api_key）
- [ ] **编码注册四件套**：①定义文件 `src/domain/exceptions/evaluation_exceptions.py`（Google 风格全中文 docstring + 模块 `__all__`）；②`_code_ranges.py` CODE_RANGES 增 evaluation 行 + `_CLASS_TO_SUBDOMAIN` 增 `AgentEvaluationError → evaluation` + agent 段注释后追注 451-459 预留说明；③`__init__.py` 导入 + `__all__`；④`EXCEPTION_HTTP_MAP` 显式注册 450→500（exception_handlers.py L140-283——SystemException 族惯例）；文档同步 sisys-uni-exception-design.md §3.3.2 编码分配表 + test_code_ranges.py `allowed_child_parent_subdomains`/`nested_subdomains` 两表按需增行（evaluation→system 嵌套关系）
- [ ] **测试覆盖**：构造/属性/`to_dict()`/HTTP 映射 + 编码唯一性（test_error_code_uniqueness.py 自动反射）+ 子域范围（test_code_ranges.py Rule 1-4）全绿：`poetry run pytest tests/unit/domain/exceptions/ -v` + `poetry run pytest tests/unit/interfaces/api/test_exception_handlers.py -v`
- [ ] **复用清单**：`ValidationError`（201——EvaluationResult 分数域守卫，应用层输入校验）；LLM 族异常透传/包装纪律（330/331→450 包装、332/CancelledError 透传——_structured_call 先例）
- [ ] BDD 验收场景：450 包装路径（AC-1 异常矩阵）+ 降级路径（AC-3.2）纳入验收 Edge Cases

#### API 契约 (API Contract)

- [ ] 本 Story 无 REST API / 无 CLI 命令（评估是嵌入式可观测基础设施——5.7 同款定位）。`docs/api/openapi.yaml` 零改动
- [ ] 环境契约：`.env.example` **零改动**（无新环境变量——评估温度/超时/权重是代码常量[TEMPERATURE_PROFILE 先例]、评估模型经既有 UDMR_* 变量族、无评估开关[范围边界表 YAGNI 裁定]）

#### 六边形架构约束（必须遵守）

> 四层定义/零依赖原则/依赖方向矩阵同模板基线。本 Story 特别注意：

- [ ] `agent_evaluation.py`（双端口 + EvaluationResult + 权重常量）在 application 层——**纯标准库零第三方**（Protocol + dataclass + 常量——agent_tracing.py 同款形态；LLMConfig 从 domain/ports import 合法[application→domain 允许]；AgentWorkflowResult 从同层 ports import）
- [ ] `evaluation_harness.py` / `evaluation_schemas.py` / `evaluation_prompts.py` 在 application 层——pydantic（Schema）合法（A+ 全层基线 {opentelemetry, pydantic, yaml} 内）；`run_agent_workflow.py` 既有 opentelemetry + 新增 AgentEvaluationPort import 合法；**禁止 import infrastructure**
- [ ] `udmr_evaluation_model_resolver.py` 在 infrastructure 层（routing/ 归口——StaticUdmrPolicy 同目录）——实现 application 端口（infrastructure→application 依赖方向合法——六边形依赖方向矩阵 infrastructure 行）；import UDMRService/UDMRTask（domain）+ UDMRConfig（同层 infrastructure/config）+ LLMConfig（domain）合法
- [ ] `evaluation_exceptions.py` 在 domain/exceptions——标准库零外部依赖（体系铁律）；domain 业务域（ports/services/entities/value_objects/events）**零触碰**（AST 验证器断言——本 Story domain 触碰仅 exceptions 注册三件）
- [ ] 接口层零改动（无 CLI/API 面）；组合根是唯一注册与实例化点

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_agent_evaluation.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_agent_evaluation.py`
- [ ] 场景组织：AC 注释横幅分组 + 全场景逐一 `@scenario` 显式绑定（多行字面量路径——R6 形态，禁 `scenarios()` 批量绑定与 then-pass 占位）；场景名 `AC-x.y - 中文描述`（feature 与 .py 逐字一致）；**禁 Background 背景块**（步骤化门控——本 Story 外部服务门控 = 零外部服务[Fake LLM + 零 IO 手写替身 + 真实 UDMR 链本地计算]）；Gherkin Given 钉「评估链已装配（Fake LLM + 真实 UDMR 决策链）」类前置步骤
- [ ] 14 场景规划（终态 = Task 0 编写 13 + Task 6 追加收尾 1；三属性分档表 Task 0.6 定稿落 docstring）：
  - AC-1 ×3（组件级，零服务依赖）：EvaluationResult 构造与分数域校验（含 201 越界参数化）/ 幻觉检测 LLM 结构化调用（prompt 三要素 + config 派生断言 + Schema 实例守卫 + LLM 族异常矩阵）/ 证据支撑度与校准公式计算（四态参数化 + 数值矩阵 + overall 加权）
  - AC-2 ×3（组件级，真实 UDMR 决策链手工装配）：评估模型 cloud 路由与 LLMConfig 匹配 / 云端不可用 local 回退 + 非硬编码双配置判别 / 路由产物匹配失败 450 + RoutingDecided 事件发布
  - AC-3 ×3（链级，Fake LLM 手工装配 + initialize 全局通道）：主链评估执行与 eval.* 三键写根 span / 评估降级不阻断主链（三键缺席 + warning + 十属性不受影响）/ 构造签名扩展与存量回归基线（六依赖 + None 兼容 + 5-7 断言更新——全量回归绿在 Task 6 收尾跑）
  - AC-4 ×2（静态 + 接线）：组合根接线（双端口 resolve 四件 + use case lambda 注入 + 契约 11 维度×2）/ 架构静态扫描（AST 三验证器 + domain 触碰收窄 + 零 env/零事件通道变更）
  - AC-5 ×1（委托集成计时）：评估管线 P95<500ms
  - 收尾 ×1：完成清单逐项确认（src + tests 四目录——5-7 收尾同款）
- [ ] BDD 步骤约束：全部同步 `def` + `_run_async(context["_loop"], ...)`（禁 `@pytest.mark.asyncio`——context 数据丢失）；参数化步骤显式 `parsers.parse`；异常断言三段式（raises 捕获存 `context["caught"]` → then 断言 isinstance + code + context——450/201/透传场景）；**span 断言锚（5-7 SSOT 全文唯一口径）**：**装饰器/@trace 链路 span 只经全局 provider 可观测**——链级场景（AC-3.1/3.2/3.3）统一通道 = 场景级新 `TracerProvider + SimpleSpanProcessor + InMemorySpanExporter` 经 `PhoenixTracer(config=测试配置, tracer_provider=注入).initialize()` → 断言 → **teardown 强制 `reset_for_testing()` 双复位**（变量 + Once 闩锁重建——5-7 R1 实测；凡 initialize 一律双复位义务[复位义务正交条款]）；组件级场景（AC-1/AC-2）零全局触碰（不经装饰器，纯服务调用无 span 依赖）
- [ ] 显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.xdist_group("agent-evaluation-perf")]`（文件名不含服务关键词且零外部服务——无 redis/database marker；组名与集成计时场景逐字同组）+ 延迟 import 纪律（本 Story 新交付模块一律在步骤函数体内 import——模块顶部 import 会使 pytest 收集期整文件 collection error，无法逐 Task 转绿）
- [ ] teardown：span 面零资源（凡 initialize 场景 teardown `reset_for_testing()` 双复位 + exporter 清空——5-7 同款；无 Redis/PG 清理面）；计时场景委托缓存防双跑

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——**红形态钉死[5-7 R3-10 同款]**：13 场景逐一 failed（场景级延迟 import 的 ModuleNotFoundError/断言红）而非 collection error——若模块级评估模块 import 导致 1 个 collection error + 0 tests，则 @scenario 绑定校验全被掩盖，需回查延迟 import 纪律）
- [ ] 规范文档通过人工评审或自动化校验
- [ ] **链路接线断言清单**已定义（Epic 4 回顾行动项 7.1-1）：①`agent_evaluation` + `evaluation_model_resolver` 组合根 register_port 装配验证（resolve 可达 + isinstance + PortSpec + SINGLETON）②use case lambda 第六依赖注入确认（resolve("agent_workflow_use_case") 实例 `_evaluation_harness` 非 None——接线可达性）③主链评估块静态锚（execute 体内 evaluate 调用 + 三常量引用 + is_recording 守卫——AST/inspect 扫描）④eval.* 三键 span 落链验证（链级场景经 initialize 全局通道后 InMemory exporter 能取到三键真值——AC-3.1 场景承载）⑤UDMR in-band 消费链验证（resolver → decide() → RoutingDecided 发布 → LLMConfig 匹配——AC-2 场景承载）

---

### TDD 循环约束（适用于每个 Task）

> 每 Task 依次执行 🔴红→🟢绿→🟡变异→🔄重构；变异实证 = 对新行为契约的断言改坏→红→还原→绿（Epic 4 行动项 7.1-2 强制）。禁止行为四条同模板基线。
>
> **套件型 Task 豁免条款**（Task 4 性能场景 / Task 5 架构验证 / Task 6 收尾场景）：验证型测试层首跑即绿——红由 Task 0 验收红阶段前置承担；断言活性由 🟡 变异实证强制（如：权重常量改错→overall 断言红；三键写入删除→span 断言红；P95 常量突变→阈值断言红；评估块删除→静态锚红）。

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| TDD 单元测试 | AgentEvaluationError | 构造/code 450/context 三键/to_dict/HTTP 映射 500 | `tests/unit/domain/exceptions/test_evaluation_exceptions.py` | Task 1 |
| TDD 单元测试 | EvaluationResult | 构造/四分数域 201 守卫/frozen | `tests/unit/application/test_agent_evaluation_model.py`（端口模型单测——按 tests/unit/application/ 现状落位） | Task 1 |
| TDD 单元测试 | EvaluationHarness | 幻觉检测调用（Fake LLM 分派 + config 派生 + prompt 三要素）/ 启发式四态 / 校准矩阵 / overall 加权 / 异常包装矩阵（450 包装 + 332/Cancelled 透传） | `tests/unit/application/services/test_evaluation_harness.py` | Task 2 |
| TDD 单元测试 | UdmrEvaluationModelResolver | cloud 匹配/local 回退/双配置非硬编码/匹配失败 450/UDMRTask 构造/事件发布（真实 UDMR 链 + 零 IO 替身 + 健康检查替身） | `tests/unit/infrastructure/routing/test_udmr_evaluation_model_resolver.py` | Task 3 |
| TDD 契约测试 | agent_evaluation | 11 维度 + _DummyResolver（分发 llm_client/evaluation_model_resolver） | `tests/contracts/test_port_contract_agent_evaluation.py` | Task 1 |
| TDD 契约测试 | evaluation_model_resolver | 11 维度 + _DummyResolver（分发 udmr_service） | `tests/contracts/test_port_contract_evaluation_model_resolver.py` | Task 1 |
| TDD 单元测试 | 主链接入 | use case 第六依赖/评估块三键写入（initialize 全局通道 + Fake LLM 链）/降级路径/None 默认路径 | `tests/unit/application/use_cases/test_run_agent_workflow.py`（追加——5-3 存量文件） | Task 3 |
| 集成测试 | 全链评估 | 六阶段真实链 + 评估执行 + span 三键真值 + 降级链 + UDMR in-band 全链 + P95 计时委托 | `tests/integration/test_integration_agent_evaluation.py` | Task 4 |
| SDD 架构验证 | 六边形约束 | application 白名单/domain 触碰收窄/组合根外零实例化/主链评估块静态锚/六依赖签名基线 | `tests/unit/architecture/test_arch_evaluation.py` | Task 5 |
| TDD 验收测试 | Gherkin + BDD | 13 场景 Task 0 编写（收尾 Task 6 追加成 14 终态）；各 Task 转绿——AC-1 随 Task 1/2、AC-2 随 Task 3、AC-3 随 Task 3/4、AC-4 随 Task 1/3/5、AC-5 随 Task 4 | `test_acceptance_agent_evaluation.feature/.py` | Task 0-6 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] 整体 ≥80%（P0 阻断）；**应用层 ≥85%**（evaluation_harness/agent_evaluation/主链评估块主战场——epics L1798）；infrastructure ≥75%（udmr_evaluation_model_resolver——epics L1799「集成测试覆盖率≥75%」按仓内门禁体系落为 infrastructure 层 ≥75%[`scripts/check_coverage_gates.py` L69]——5-7 口径映射注记同款）；domain ≥90% 维持（exceptions 新文件全覆盖——业务域零触碰不降不升）；四档与 `scripts/check_coverage_gates.py` 一致
- [ ] 关键分支可执行口径：幻觉检测三分支（正常/Schema 校验失败/LLM 异常包装）+ 降级 catch 分支 + None 跳过分支 + resolver 三分支（cloud/local/匹配失败）各配独立命名测试用例（用例名即分支清单）

#### 代码质量门禁

- [ ] `ruff check src/ tests/` + `mypy src/`（零新第三方依赖——零 stubs 新增需求）+ `pre-commit run` 全过
- [ ] 三条红线自查零输出（`raise ValueError`/手动 `HTTPException`/继承内置 Exception——注意 EvaluationResult 分数域守卫必须 201 非 ValueError、AgentEvaluationError 必须继承 SystemException 体系）+ 零抑制注释（noqa/type: ignore/pylint: disable 全禁——5-7 noqa 清零先例）
- [ ] 提交信息零 AI 署名

#### 测试隔离约束

> 基线同模板。本 Story 特别注意：

- [ ] **OTel 全局状态隔离（AC-3 链级场景 + 主链接入单测）**：凡 `initialize()` 一律「前置 reset 双复位 → act → teardown reset 双复位」（复位义务正交条款——5-7 SSOT）；**已知同进程泄漏源** `tests/unit/infrastructure/monitoring/test_event_monitoring.py::TestInitTracing`（L351-375 init set 全局无 teardown）——凡断言「全局未 set」前提的测试前置双复位；建议本 Story 测试文件采用**文件级 function-scope autouse 双复位 fixture** 兜底（5-7 机制化形态——Task 0 红阶段兼容 ImportError 时零复位零阻断）；**环境前提**：验收/集成进程 env 不带 `PHOENIX_TRACING_ENABLED=true`（场景级 monkeypatch.delenv 钉死）；**严禁跨测试文件共享已 set 的全局 provider**
- [ ] **本 Story 零外部服务依赖**：无 Redis/PG/Phoenix server/LLM API 硬依赖（评估面 Fake LLM + 真实 UDMR 本地计算链[ComplianceGateway 纯正则/StaticUdmrPolicy 纯逻辑] + 零 IO 手写替身自包含——5-3/5-7 先例边界）；验收禁 mock 红线的豁免面 = llm_client（外部 SaaS——5-3 先例）+ 健康检查替身（外部探测面——手写类非 AsyncMock）+ 零 IO 事件/决策日志替身（手写 duck-typing 类——5-4/5-5 先例）
- [ ] **Fake LLM 手工装配边界**（5-3 先例口径 + Schema 前提）：`AsyncMock(spec=LLMClientPort)` + side_effect 按 response_schema 身份分派返回**真实 Schema 实例**；**HallucinationEvaluationSchema 分派分支与既有五 Schema 身份互斥**（Schema 两两不同是分派键前提——新增分支不破坏既有断言锚）；幻觉分派值可注入（场景控制幻觉分——AC-3.1 三键真值断言的数据源）
- [ ] **pytest-xdist 计时组**：`xdist_group("agent-evaluation-perf")` 与既有 12 组互异（全仓 grep 断言——AC-5 验证标准清单）；`_PERF_CACHE` 委托缓存 + benchmark 场景级标记；P95 常量单源（集成定义/验收 import）
- [ ] **评估链状态零残留**：EvaluationHarness 无状态（纯函数式 evaluate——无 eval_history 累积[5.9/5.10 范围]）；场景间零共享（每场景自装配）；UDMR 决策日志替身场景级新建（零跨场景累积）
- [ ] BDD 步骤禁 `@pytest.mark.asyncio`；步骤函数同步 def + `_run_async` 调度；模块级 event_loop fixture（5-7 显式定义形态）
- [ ] **5-3/5-7 存量回归**：use case 构造签名扩展（第六可选依赖 None 默认——存量五参构造零破坏）+ 5-7 AC-4.3 断言基线更新后 5-7 全家（unit×3 + 契约 + integration + acceptance 15 场景）+ 5-3 全家（unit×4 + 契约×3 + integration + acceptance）全量回归绿——回归清单 Task 3 登记

**验证要求：** `pytest tests/` 通过（仓库默认 `-n auto --dist loadgroup`）；连续 5 次无随机失败；`ruff check` + `mypy` 通过；5-3/5-7 全家回归绿；异常体系 CI 测试（test_code_ranges/test_error_code_uniqueness/test_exception_handlers）全绿。

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | EvaluationResult 构造 + 分数域 201 守卫 | Task 1 | EvaluationResult 模型 | test_agent_evaluation_model + 验收 AC-1.1 |
| AC-1 | 幻觉检测 LLM 结构化调用（Schema/prompt/config 派生） | Task 2 | 幻觉检测调用面 | test_evaluation_harness + 验收 AC-1.2 |
| AC-1 | 证据支撑度四态 + 校准公式矩阵 + overall 加权 | Task 2 | 双本地计算 + 加权 | test_evaluation_harness + 验收 AC-1.3 |
| AC-1 | LLM 族异常包装矩阵（450/透传） | Task 2 | 异常包装纪律 | test_evaluation_harness + 验收 AC-1.2 |
| AC-2 | UDMR cloud 路由 + LLMConfig 匹配 | Task 3 | resolver cloud 分支 | test_udmr_evaluation_model_resolver + 验收 AC-2.1 |
| AC-2 | local 回退 + 非硬编码双配置判别 | Task 3 | resolver local 分支 | 同上 + 验收 AC-2.2 |
| AC-2 | 匹配失败 450 + RoutingDecided 事件发布 | Task 3 | resolver 失败分支 + 事件 | 同上 + 验收 AC-2.3 |
| AC-3 | 主链评估执行 + eval.* 三键写根 span（OD-2[5.7] 兑现） | Task 3 | use case 评估块 | test_run_agent_workflow（追加）+ 验收 AC-3.1 |
| AC-3 | 评估降级不阻断主链 | Task 3 | 降级 catch 分支 | 同上 + 验收 AC-3.2 |
| AC-3 | 构造签名扩展 + None 兼容 + 5-7 断言更新 + 存量回归 | Task 3 | 六依赖 + 回归清单 | 同上 + 5-7 验收 AC-4.3 + 验收 AC-3.3 |
| AC-4 | 组合根双注册 + use case lambda 注入 + 契约×2 | Task 1 | 注册 + 契约测试 | 契约×2 + 验收 AC-4.1 |
| AC-4 | 架构静态扫描（白名单/domain 收窄/静态锚） | Task 5 | AST 三验证器 | test_arch_evaluation + 验收 AC-4.2 |
| AC-5 | 评估管线 P95<500ms（委托计时） | Task 4 | 计时委托 helper | 集成 + 验收 AC-5.1 |
| 全 AC | 收尾清单 | Task 6 | 完成清单场景 | 验收收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则**同模板。每 Subtask 组内按领域粒度拆分红绿循环。

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部

- [ ] Subtask 0.1: 定义数据模型规范——EvaluationResult（frozen 四字段 + 201 分数域守卫）+ HallucinationEvaluationSchema（扁平两字段 ge/le）+ EVALUATION_WEIGHTS 七常量 + 评估调用常量（本文件「数据模型」节为唯一真源）
- [ ] Subtask 0.2: 定义端口契约——AgentEvaluationPort（evaluate）+ EvaluationModelResolverPort（resolve_config）+ 组合根注册元数据 ×2 + 契约变更登记 ×1（use case 第六依赖——含 5-7 AC-4.3 断言基线更新）+ 端口命名甄别（vs RelevanceEvaluationPort 检索域）
- [ ] Subtask 0.3: 定义异常契约——evaluation 子域 450-459 新开 + AgentEvaluationError(450, SystemException) 编码注册四件套 + LLM 族透传/包装纪律 + 复用清单（201）
- [ ] Subtask 0.4: 定义 UDMR in-band 消费链规范——UdmrEvaluationModelResolver（UDMRTask → decide() → selected_model 匹配 → per-call LLMConfig；cloud/local/匹配失败三分支）+ 与 SSOT 静态接线的区别锚
- [ ] Subtask 0.5: 定义性能测量口径——Fake LLM 评估管线 P95（warmup 1 + 20 采样 + 常量单源 + 正向锚 + 口径声明）
- [ ] Subtask 0.6: 编写 Gherkin `test_acceptance_agent_evaluation.feature`（13 场景）+ BDD 步骤实现 `.py`（@scenario 全显式绑定 + context dict fixture + 链级 initialize 全局通道 fixture + Fake LLM 手工装配链 fixture[HallucinationEvaluationSchema 分派分支] + UDMR 真实决策链手工装配 fixture + 文件级 autouse 双复位兜底）+ **13 场景三属性分档表**定稿（docstring）
- [ ] Subtask 0.7: 运行验收测试确认失败（🔴 红阶段——红形态钉死：13 场景逐一 failed 非 collection error）+ **deferred-work.md 处置注记**（OD-1[5.7] 触发条件裁定不满足 + OD-2[5.7] eval.* 兑现注记 + R1-DF3 锚位顺延[5.8 消费面走 get_current_span 不触发] + 本 Story OD-3 V1 升级通道登记[LLM-as-a-Judge/embedding 相关性通道]——gap 四要素齐备）+ 本 Story OD-1~OD-5 知悉登记（OD-3/OD-4/OD-5 设计裁定不进台账[非 gap——伪码空白/缺陷的必要裁定]，OD-1/OD-2 命名/依赖裁定不进台账[5-7 OD-3 同款]）
- [ ] Subtask 0.8: 移交留项处置落盘（前置依赖表四项逐一登记处置结果：OD-1[5.7] 裁定不触发 / OD-2[5.7] 本 Story 兑现 / R1-DF3 不触发顺延 / trace_id 防呆复核零风险知悉）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义；验收测试红阶段确认（13 场景逐一 failed）；链路接线断言清单 L1-L5 定义

---

### Task 1: AgentEvaluationError + 评估端口族 + 契约测试 + 组合根注册

**关联 AC:** AC-1（模型面）、AC-4.1

#### TDD 循环 A：AgentEvaluationError（evaluation 子域新开）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_evaluation_exceptions.py`（构造 agent_id/phase/reason context 三键 / code == "EXCEPTION_450" / to_dict 序列化 / message 默认与自定义 / HTTP 映射 500——EXCEPTION_HTTP_MAP 注册断言） |
| 🟢 绿 | 实现 `src/domain/exceptions/evaluation_exceptions.py` + `_code_ranges.py` evaluation 行 + `_CLASS_TO_SUBDOMAIN` + `__init__.py` 导出 + `exception_handlers.py` 450→500 |
| 🟡 变异 | code 改 "EXCEPTION_451"→唯一性测试红（test_error_code_uniqueness 自动反射）；CODE_RANGES evaluation 行删除→test_code_ranges Rule 1 红；还原→绿 |
| 🔄 重构 | Google 风格全中文 docstring（触发场景/Raises 契约）+ sisys-uni-exception-design.md §3.3.2 编码分配表同步 + ruff+mypy |

#### TDD 循环 B：EvaluationResult + 双端口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_agent_evaluation_model.py`（构造四字段 / 越界参数化[-0.01/1.01/2.0]→201 三段式 / bool 类型拒 / frozen 不可变 raises FrozenInstanceError / EVALUATION_WEIGHTS 和为 1.0 元断言×2 + 双端口 REQUIRED_METHODS callable 断言） |
| 🟢 绿 | 实现 `src/application/ports/agent_evaluation.py`（EvaluationResult + AgentEvaluationPort + EvaluationModelResolverPort + 权重常量——纯标准库零第三方）+ `application/ports/__init__.py` 聚合导出 |
| 🟡 变异 | 201 守卫删除→越界用例红；权重 0.4 改 0.5→和为 1.0 断言红；还原→绿 |
| 🔄 重构 | docstring（四分数语义对照表[OD-3/4/5 锚] + 端口命名甄别注记）+ ruff+mypy |

#### TDD 循环 C：契约测试 ×2 + 组合根注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/contracts/test_port_contract_agent_evaluation.py` + `test_port_contract_evaluation_model_resolver.py`（11 维度 + _DummyResolver——agent_evaluation 的 Dummy 分发 llm_client/evaluation_model_resolver[Fake 实例]，resolver 的分发 udmr_service） |
| 🟢 绿 | 组合根 `# === Story 5.8 — Agent 输出质量评估 ===` 区段追加双注册（SINGLETON + owner=platform + tags）+ use case 注册 lambda 更新（resolve_optional("agent_evaluation") 注入第六依赖——Task 3 循环 B 交付评估块后接线完整生效） |
| 🟡 变异 | lambda 漏 llm_client 注入→维度 9b 红；注册名拼写错→维度 1 红；还原→绿 |
| 🔄 重构 | 注册区段设计注释（SINGLETON 依据 + lambda 依赖清单 + 原始值注入纪律）+ ruff+mypy |

- [ ] Subtask 1.1: 🔴 红 — AgentEvaluationError 失败测试
- [ ] Subtask 1.2: 🟢 绿 — evaluation_exceptions + 注册四件套
- [ ] Subtask 1.3: 🟡 变异 — code/子域注册突变实证
- [ ] Subtask 1.4: 🔴 红 — EvaluationResult + 双端口失败测试
- [ ] Subtask 1.5: 🟢 绿 — agent_evaluation.py 端口族实现
- [ ] Subtask 1.6: 🟡 变异 — 201 守卫/权重突变实证
- [ ] Subtask 1.7: 🔴🔴🟢 — 契约测试 ×2 + 组合根双注册 + use case lambda 更新
- [ ] Subtask 1.8: 🔄 重构 — 导出/docstring/编码分配表/门禁

**完成标准/Definition of Done:**
- [ ] 异常/端口/注册三件交付；契约 11 维度 ×2 绿；异常体系 CI 测试全绿；验收 AC-1.1 + AC-4.1 转绿

---

### Task 2: EvaluationHarness 核心——幻觉检测 + 双本地计算 + overall 加权

**关联 AC:** AC-1（全部计算面）

#### TDD 循环 A：Schema + prompt + 幻觉检测调用

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_evaluation_harness.py` 循环 A 用例（Fake LLM AsyncMock spec + HallucinationEvaluationSchema 身份分派 → evaluate 内幻觉检测：structured_generate 调用断言[prompt 含 input_summary/证据摘要/final_answer 三要素 + response_schema is HallucinationEvaluationSchema + config.temperature == 0.1 + config.timeout == 8.0——config 基底来自注入 resolver 替身返回的固定 LLMConfig] / Schema 实例守卫[Fake 返回非 Schema → 450] / LLM 族异常矩阵[LLMAPIError→450 包装 from error + LLMAPIError/LLMResponseError/TimeoutError/ServiceUnavailableError 参数化 + LLMConfigError 透传 + CancelledError 透传]) |
| 🟢 绿 | 实现 `src/application/services/evaluation_schemas.py` + `evaluation_prompts.py`（SYSTEM_PROMPT 评估者角色 + USER_TEMPLATE 三要素占位）+ `evaluation_harness.py`（`_detect_hallucination`：resolver.resolve_config(chain.final_answer) → dataclasses.replace(config, temperature, timeout) → structured_generate → isinstance 守卫 → 异常包装） |
| 🟡 变异 | 温度 0.1 改 0.7→config 断言红；isinstance 守卫删除→非 Schema 用例红；包装改透传→450 断言红；还原→绿 |
| 🔄 重构 | docstring（prompt 三要素对照 + Raises 矩阵）+ ruff+mypy |

#### TDD 循环 B：compute_context_relevance + compute_confidence_accuracy + overall

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 追加循环 B 用例（compute_context_relevance 四态参数化[全空 0.0/仅 citations 0.4/citations+tool_trace 0.7/全满 1.0] / compute_confidence_accuracy 数值矩阵[diff 0→1.0 / diff 0.3→0.7 / diff ≥1.0→0.0] / overall 加权手算对照[给定三输入 → overall == 公式精确值] / actual_quality 口径断言[(1-h)*0.5+cr*0.5]）——构造 TaskEvidencePackage/ChainOfThought 真实 VO 实例（domain VO 真实构造——242 校验通过的真实材料） |
| 🟢 绿 | 实现两计算方法（纯同步——@staticmethod 或实例方法，权重常量引用端口文件单源）+ `_compute_overall` 私有组装 |
| 🟡 变异 | CITATION_WEIGHT 0.4 改 0.5→四态断言红；公式 min 删除→矩阵红；overall 反转 (1-h) 删 h→加权断言红；还原→绿 |
| 🔄 重构 | 公式 docstring（§17.3.8 L1681 钦定注记 + OD-3/4/5 锚）+ ruff+mypy |

#### TDD 循环 C：evaluate 编排

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 追加循环 C 用例（evaluate 端到端：Fake LLM 幻觉分注入 0.2 + 真实 VO 输入 → EvaluationResult 四字段全断言[hallucination == 0.2 / context_relevance == 启发式手算 / confidence_accuracy == 校准手算 / overall == 加权手算] / evaluate 只读不改写断言[输入 result 对象字段不变——frozen 天然，断言 evidence.confidence 原值]） |
| 🟢 绿 | 实现 `evaluate`（幻觉检测 await → 双本地计算 → actual_quality → confidence_accuracy → overall → EvaluationResult 构造） |
| 🟡 变异 | evaluate 字段装配错位[confidence_accuracy 与 context_relevance 互换]→四字段断言红；还原→绿 |
| 🔄 重构 | EvaluationHarness 类 docstring（评估管线五步流程图）+ ruff+mypy |

- [ ] Subtask 2.1: 🔴 红 — Schema/prompt/幻觉检测失败测试
- [ ] Subtask 2.2: 🟢 绿 — 幻觉检测调用面最小实现
- [ ] Subtask 2.3: 🟡 变异 — 温度/守卫/包装突变实证
- [ ] Subtask 2.4: 🔴 红 — 双本地计算 + overall 失败测试
- [ ] Subtask 2.5: 🟢 绿 — 计算方法实现
- [ ] Subtask 2.6: 🟡 变异 — 权重/公式突变实证
- [ ] Subtask 2.7: 🔴 红 — evaluate 编排失败测试
- [ ] Subtask 2.8: 🟢 绿 — evaluate 编排实现
- [ ] Subtask 2.9: 🟡 变异 — 装配错位突变实证
- [ ] Subtask 2.10: 🔄 重构 — docstring/门禁

**完成标准/Definition of Done:**
- [ ] EvaluationHarness 三循环全绿；验收 AC-1.2 + AC-1.3 转绿；应用层覆盖率 ≥85% 达标面

---

### Task 3: UdmrEvaluationModelResolver + 主链接入 + 5-3/5-7 回归

**关联 AC:** AC-2（全部）、AC-3（全部）、AC-4.1（接线面）

#### TDD 循环 A：UdmrEvaluationModelResolver（UDMR in-band 消费链）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/routing/test_udmr_evaluation_model_resolver.py`（真实 UDMR 决策链装配：真实 UDMRService + 真实 StaticUdmrPolicy[测试 cloud_configs 注入] + 真实 ComplianceGatewayImpl + 手写 `_RecordingEventPublisher` + 手写零 IO 决策日志替身 + 手写健康检查替身[True/False 可控]——用例：cloud 路由[健康 True + 单云端 → config.model == cloud.model + endpoint/api_key/timeout 逐字段] / local 回退[健康 False → decide 回退 local → config.model == local_model + from_env 连接字段形态] / 非硬编码双配置[cloud_configs 模型 A → config.model==A；模型 B → ==B] / 匹配失败 450[monkeypatch decide 或构造漂移配置 → AgentEvaluationError + context 含 selected_model] / RoutingDecided 事件发布[替身捕获 isinstance + selected_model 对应] / UDMRTask 构造[input_text 传递断言——经决策日志替身或事件 task_context 捕获]) |
| 🟢 绿 | 实现 `src/infrastructure/routing/udmr_evaluation_model_resolver.py`（构造器注入 udmr_service/cloud_configs/local_model/llm_timeout 原始值——UDMRService 注册先例纪律；resolve_config：UDMRTask 构造 → decide() → route_type 分派[cloud 匹配循环 / local replace(from_env)] → 匹配失败 450） |
| 🟡 变异 | 匹配循环 `==` 改 `!=`→cloud 用例红；local 分支 model 不用 selected_model→local 用例红；匹配失败改静默回退→450 用例红；还原→绿 |
| 🔄 重构 | docstring（in-band vs SSOT 区别锚 + 三分支决策表）+ ruff+mypy |

#### TDD 循环 B：use case 主链评估块

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/application/use_cases/test_run_agent_workflow.py` 追加（**经 initialize 全局通道**——模块级 fixture：reset 双复位 → initialize → teardown 双复位）：注入 Fake evaluation_harness[AsyncMock spec=AgentEvaluationPort + evaluate side_effect 返回固定 EvaluationResult] → execute → agent_execution span 三键断言（值 == Fake 注入的 EvaluationResult 字段——经 get_current_span 面取 exporter）/ 降级路径[Fake evaluate side_effect 抛 AgentEvaluationError → 主链正常返回 + 三键缺席 + MVP 十属性仍在 + caplog warning] / None 默认路径[五参构造 → 行为与 5-7 基线一致 + 三键缺席] |
| 🟢 绿 | `run_agent_workflow.py`：第六可选依赖 + execute 末尾评估块（None 守卫 → try evaluate → is_recording 三键写入 → except AgentEvaluationError → logger.warning 降级）+ **5-7 资产同步**：test_acceptance_phoenix_tracer.py AC-4.3 构造签名基线更新（五依赖 → 六依赖） |
| 🟡 变异 | 三键写入删除→span 断言红；降级 catch 删除→主链断言红[AgentEvaluationError 上抛击穿 execute]；None 守卫删除→五参构造用例红[AttributeError]；还原→绿 |
| 🔄 重构 | 评估块注释（OD-2[5.7] 兑现注记 + 降级哲学锚）+ ruff+mypy |

#### TDD 循环 C：5-3/5-7 存量全家回归

| 阶段 | 动作 |
|------|------|
| 🔴→🟢 | 回归绿清单执行：**5-3 全家**（test_agent_workflow_service 存量 + 契约×3[service/use_case/engine] + test_single_agent_workflow_graph + test_langgraph_engine + 集成 + 验收）+ **5-7 全家**（test_phoenix_config/test_phoenix_tracer/test_tracing_decorator + 契约 + test_arch_phoenix_tracer + 集成八场景 + 验收 15 场景[AC-4.3 基线更新后]）——第六可选依赖 None 默认 + 评估块 None 守卫使存量零破坏预期全绿；**异常项逐一登记**（实施时以实际清单为准甄别修复） |

- [ ] Subtask 3.1: 🔴 红 — resolver 六用例失败测试
- [ ] Subtask 3.2: 🟢 绿 — UdmrEvaluationModelResolver 实现
- [ ] Subtask 3.3: 🟡 变异 — 匹配/回退/失败分支突变实证
- [ ] Subtask 3.4: 🔴 红 — 主链评估块失败测试（三面：注入/降级/None）
- [ ] Subtask 3.5: 🟢 绿 — 第六依赖 + 评估块 + 5-7 断言更新
- [ ] Subtask 3.6: 🟡 变异 — 三键/降级/守卫突变实证
- [ ] Subtask 3.7: 🟢 — 5-3/5-7 存量全家回归绿（清单登记）
- [ ] Subtask 3.8: 🔄 重构 — docstring/门禁

**完成标准/Definition of Done:**
- [ ] resolver + 主链评估块交付；验收 AC-2 ×3 + AC-3 ×3 + AC-4.1 转绿；5-3/5-7 全家零回归；组合根 use case lambda 接线完整生效

---

### Task 4: 集成测试与性能——全链评估 + UDMR in-band 全链 + P95

**关联 AC:** AC-3（集成面）、AC-5（全部）

> 性质说明：本 Task 对 Task 1-3 已交付链编写验证型测试（套件型豁免——红由 Task 0 前置，活性由变异保证）。

- [ ] Subtask 4.1: 编写 `tests/integration/test_integration_agent_evaluation.py`（Fake LLM 手工装配六阶段链 + 真实 EvaluationHarness + 真实 UDMR 决策链[零 IO 替身] + **链级 initialize 全局通道**[场景级 reset 双复位 → initialize → 断言 → teardown 双复位]）：场景① 全链评估（execute → span 三键真值断言[幻觉分 == Fake 注入 + context_relevance == 手算 + confidence_accuracy == 手算] + overall 可派生性断言[三键经 EVALUATION_WEIGHTS 重构 == overall]）② UDMR in-band 全链（resolver 真实链 → 幻觉检测 config.model == 路由产物——经 Fake LLM call_args 捕获 config 断言）③ 降级链（幻觉检测分支抛 LLMAPIError → 主链正常 + 三键缺席 + warning + AgentDecided 照常发布）④ None 路径对比（五参构造 execute → 与 5-7 基线 span 树等价[十属性 + 零 eval.* 键]）⑤ P95<500ms（`_PERF_CACHE` + warmup 1 + 20 采样 + Fake LLM 即时返回 + 正向锚[Fake structured_generate 调用计数 == 21] + `EVALUATION_P95_LIMIT_SECONDS = 0.5` 常量单源 + benchmark 场景级标记）
- [ ] Subtask 4.2: 变异实证——权重常量改错→场景①手算断言红；三键写入删除→场景①红；P95 常量突变（0.5→0.000001）→场景⑤红；匹配循环破坏→场景②红；还原→绿
- [ ] Subtask 4.3: 验收 AC-5.1 场景转绿（委托计时缓存命中验证）+ AC-3/AC-2 集成对应场景转绿

**完成标准/Definition of Done:**
- [ ] 集成五场景全绿；P95 达标（实测 μs~ms 级——500ms 裕量充足）；计时组与既有 12 组不冲突；验收对应场景全绿

---

### Task 5: SDD 架构约束验证测试

**关联 AC:** AC-4.2

> 性质说明：SDD 规范验证测试（验证架构约束是否被遵守），非 TDD 单元测试。

- [ ] Subtask 5.1: 创建 `tests/unit/architecture/test_arch_evaluation.py`——验证器 A：application 触碰文件（agent_evaluation.py/evaluation_harness.py/evaluation_schemas.py/evaluation_prompts.py/run_agent_workflow.py + **ports/__init__.py**[聚合导出也是触碰文件]）第三方 import 白名单（pydantic/opentelemetry 允许——5.7 验证器 A+ 全层基线 {opentelemetry, pydantic, yaml} 内零新增断言——OD-1[5.7] 裁定不触发的实现面证据）；验证器 B：domain 触碰收窄（_STORY58 业务符号[EvaluationHarness/AgentEvaluationPort/EvaluationModelResolverPort/EvaluationResult/HallucinationEvaluationSchema] 在 domain/ports|services|entities|value_objects|events 零命中 + AgentEvaluationError 仅在 domain/exceptions/ 三件内命中）+ 组合根外零实例化（EvaluationHarness(/UdmrEvaluationModelResolver( 构造点仅 composition_root.py + tests/）+ 依赖方向（udmr_evaluation_model_resolver.py import src.application 断言——infrastructure→application 合法面锚定）；验证器 C：主链评估块静态锚（execute 体内 evaluate 调用 + SpanAttributeKeys 三常量引用 + is_recording 守卫在位——AST/inspect 扫描）+ use case 六依赖签名基线（inspect.signature 对照——[agent_repository, agent_profile_use_case, agent_engine, agent_workflow_service, isolation_guard, evaluation_harness] 且第六参数默认 None）+ evaluation_exceptions 标准库零外部依赖断言
- [ ] Subtask 5.2: 变异实证——evaluation_harness.py 注入 fastapi import→验证器 A 红；domain/services 下放置评估符号→验证器 B 红；评估块三常量引用删除→验证器 C 红；还原→绿
- [ ] Subtask 5.3: 验收 AC-4.2 场景转绿

**完成标准/Definition of Done:**
- [ ] 架构验证器三件全绿；违规即红；循环依赖检测沿用 ruff/isort（不引入新工具）

---

### Task 6: 开发结束验收测试

**关联 AC:** 全部

> 性质说明：对 Story 收尾阶段的交付物与完成清单进行最终验收。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 feature 收尾验收场景（完成清单） |
| 🟢 绿 | 编写 BDD 步骤实现（文件存在性检查——src 新建五文件[agent_evaluation.py/evaluation_harness.py/evaluation_schemas.py/evaluation_prompts.py/udmr_evaluation_model_resolver.py] + evaluation_exceptions.py + 修改四文件[run_agent_workflow.py/composition_root.py/_code_ranges.py+__init__.py+exception_handlers.py——异常注册三件] + tests 四目录清单 + 5-7 断言更新文件，missing 断言） |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 6.1: 收尾场景步骤 1 — src 完成清单逐项确认（新建六文件 + 修改四文件 + .env.example 零改动断言 + event_channels.yaml 零改动断言）
- [ ] Subtask 6.2: 收尾场景步骤 2 — tests 四目录完成清单逐项确认（unit 三件[exceptions/model/harness/resolver] + 契约×2 + 集成 + 架构 + acceptance 两件 + 5-7 追加面 + use case 追加面——同一收尾场景内两份清单）
- [ ] Subtask 6.3: 运行全量验收（14 场景终态）+ `pytest tests/` + `ruff check` + `mypy` 收尾校验 + 5-3/5-7 全家回归终验 + 异常体系 CI 终验
- [ ] Subtask 6.4: 文档与台账终态更新——deferred-work.md 留项终态（OD-1[5.7]/OD-2[5.7]/R1-DF3 处置注记落盘确认 + OD-3 V1 通道登记终态）+ architecture.md §14.4 交付注记更新（评估面交付——5.8）+ sisys-core-domain-design.md §17.3.8 实现注记更新（OD-2/OD-3/OD-4/OD-5 裁定映射）+ sisys-uni-exception-design.md §3.3.2 编码分配表（Task 1 已同步——终态确认）+ sprint-status.yaml 状态流转

**完成标准/Definition of Done:**
- [ ] 14 场景全绿；全量回归零 5.8 面新失败；Story 可进入 `review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../docs/architecture/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ 评估即端口（AgentEvaluationPort 应用契约 + EvaluationModelResolverPort 技术实现可替换端口——R1[R2 组合 R3 实现]三层落地）+ 可观测附加面（评估降级哲学——5.7 DC-7 延续）
- **设计约束:** 领域层零依赖（domain 触碰仅 exceptions 注册三件）；`.importlinter` application-no-infrastructure（resolver 在 infrastructure 实现 application 端口——依赖方向矩阵 infrastructure→application 合法）；端口注册 PortSpec + 组合根唯一实例化点；OTel 全局 TracerProvider 单次设置约束（凡 initialize 一律双复位——5-7 SSOT）
- **接口治理:** 统一端口注册/Registry/Resolver/ContractGate、Composition Root 装配、契约优先（11 维度 ×2）、版本化兼容、禁止跨模块直接依赖实现类；端口命名甄别（agent_evaluation vs 检索域 relevance_evaluation——语义分立登记）
- **技术栈:** Python 3.11+ / pydantic ^2.5（Schema——既有依赖）/ litellm ^1.28（LLM 调用——既有依赖）/ opentelemetry ^1.21（span 写入——既有依赖）/**零新运行时依赖**（OD-1[5.7] 裁定不触发的实现面收益）

### 关键架构决策 Key Design Decisions

**DC-1 评估端口族——双端口分立：评估契约（应用）与模型解析（技术）解耦**
- 选定：`AgentEvaluationPort`（evaluate——评估编排契约）+ `EvaluationModelResolverPort`（resolve_config——评估模型解析契约）双端口同文件（application/ports/agent_evaluation.py）；`EvaluationHarness`（application/services——实现 evaluate）+ `UdmrEvaluationModelResolver`（infrastructure/routing——实现 resolve_config）
- 论证：①**R1/R2/R3 规则落地**——LLMClientPort（domain 基础端口 R1）被 EvaluationHarness 组合注入（R2）；UDMR 路由 + cloud_configs 匹配是技术实现面（R3——infrastructure 实现 application 端口，可替换静态配置解析/多路由源——扩展其他同类技术实现）；②若单端口（harness 内嵌 UDMR 消费）则 harness 必须 import infrastructure 配置类型——违反 application-no-infrastructure；③「评估模型获取方式」是独立演化轴（MVP 静态策略路由 → V1 语义路由 → 专用评估模型池）——端口分立使演化不触碰评估编排；④span 写入不走 harness（职责单一——harness 只算值，写入归 use case 调用方——5.7 MVP 十属性块同构先例 + span 存活期约束[execute 返回即 end]）
- 备选：单端口 harness 全包（弃——层违例 + 演化耦合）；harness 注入 AgentTracingPort 自写 span（弃——写入职责分裂双通道[根 span vs 自建 span]且与 5.7 先例不一致；R1-DF3 缝隙也将被触发）

**DC-2 幻觉检测调用面——structured_generate + 自有扁平 Schema（OD-1[5.7] 裁定不触发）**
- 选定：`LLMClientPort.structured_generate(prompt=三要素, response_schema=HallucinationEvaluationSchema, config=路由产物派生)`——扁平 Schema（hallucination_score ge/le + rationale）零嵌套
- 论证：①`phoenix.evals.llm_eval_binary_classifier` 是伪码旧生态 API（5.7 OD-1 同源废弃链）；本 Story 只需「LLM 结构化评分」语义——structured_generate 三策略级联解析 + Schema 域约束完整达成；②零新依赖 = 零架构白名单变更（5.7 验证器 A+ 基线不动——R3-6[5.7] 前瞻的治理点不触发）；③prompt 三要素（input_summary 任务理解 + 证据摘要 + final_answer 被评估回答）——严格幻觉检测需证据参照（伪码 L1651 只给回答是简化——三要素是可辩护增强）；④binary → [0,1] 连续评分宽化（OD-2）：5.9 CUSUM 累积和需要连续量 + span 属性可过滤——信息量优于二值；⑤config 派生纪律照 `_build_call_config`（replace 只覆温度 0.1/超时 8.0——连接字段随路由产物继承，防裸构造丢连接字段）
- 备选：引入 arize-phoenix-client / openinference-semantic-conventions（弃——OD-1[5.7] 触发条件不满足 + 依赖树 OTel 栈升级回归风险）；pydantic 嵌套 Schema（弃——anthropic 通道服务端栈溢出，litellm_llm_client.py L630-637）；generate 纯文本 + 手工 JSON 解析（弃——structured_generate 已内建解析与守卫，重造轮子）

**DC-3 评估模型 UDMR in-band 动态路由——仓内首个 per-call 路由消费方**
- 选定：`UdmrEvaluationModelResolver.resolve_config`：UDMRTask(input=final_answer) → `UDMRService.decide(task)`（复用既有组合根注册实例）→ route_type/selected_model → cloud 匹配（`model == selected_model` 循环——非「第一个 enabled」）/ local（`replace(LLMConfig.from_env(), model=selected_model)`）/ 匹配失败 450（禁静默回退——配置漂移是错误面）
- 论证：①epics L1782 AC 硬约束「评估模型通过 UDMR 动态路由获取（非硬编码）」——现状（Agent A 调研）是 bootstrap 定格 SSOT（build_default_llm_config 取第一个 enabled）**无 per-call 消费模式**——本 Story 新建 in-band 消费链是 AC 唯一满足路径；②复用 `UDMRService.decide()` 而非直调 `UdmrPolicyPort.route()`——decide 含 L1 合规（评估文本过 PIPL 正则——评估 prompt 携带 Agent 输出的合规防线）+ 健康检查回退 + RoutingDecided 事件（评估调用成本经既有 CostMetricsListener 订阅面自然统计——零新增消费基建）+ 决策日志（评估路由可审计）；③「非硬编码」判别性锚定「经 decide() 获取」而非「模型评分动态」（L2 四因子未实现——Epic 11 Story 11.1；MVP 是静态策略路由——Agent A 调研钉死）；④匹配失败抛 450 而非回退第一 enabled——静默错模型比显式失败更危险（评估结果可信性归零）
- 备选：直调 UdmrPolicyPort.route()（弃——绕过合规/健康检查/事件/日志四面，评估调用失去合规防线与成本统计）；harness 内置默认 config + UDMR 可选（弃——非硬编码 AC 失败）；匹配失败回退 build_default_llm_config（弃——静默漂移）

**DC-4 三指标算法——两本地纯计算 + 一 LLM 调用（OD-3/OD-4/OD-5 裁定群）**
- 选定：幻觉检测 = LLM 异步调用；context_relevance = 证据支撑度三元加权（citations 0.4 / artifacts 0.3 / tool_trace 0.3——确定性同步）；confidence_accuracy = §17.3.8 L1681 钦定公式（`1.0 - min(|predicted - actual|, 1.0)`，actual = `(1-h)×0.5 + cr×0.5`）；overall = `(1-h)×0.4 + cr×0.35 + ca×0.25`（反转加权——三键方向归一后 SYS AGENT 五维评分先例形态）
- 论证：①伪码算法空白（context_relevance 无算法体）+ 伪码缺陷（confidence_accuracy 引用未构造的 eval_result——循环依赖 bug）——MVP 必须裁定可实施口径且裁定可辩护可测试；②两本地计算零外部依赖（评估延迟预算 + 确定性测试 + 无网络失败面）；③hallucination_score 字面语义（0=无幻觉）与 overall 反转 (1-h) 显式化——字段名诚实 + 质量分单调正向（5.9 CUSUM 消费方向一致性前提）；④权重常量单源（EVALUATION_WEIGHTS——和为 1.0 元断言防漂移）
- 备选：context_relevance 走 LLM-as-a-Judge（弃——V1 通道：评估延迟翻倍 + 双 LLM 失败面 + RelevanceEvaluationPort 检索域先例语义混淆风险；deferred 登记）；hallucination_score 语义反转为事实性分（弃——字段名与语义相反的误导性更强）；actual 用 overall（弃——循环依赖：overall 含 confidence_accuracy 而 confidence_accuracy 依赖 actual）

**DC-5 主链接入——第六可选依赖 + 可观测附加面降级（5-6 苦役结构性规避）**
- 选定：`RunAgentWorkflowUseCase.__init__` 尾部追加 `evaluation_harness: AgentEvaluationPort | None = None`（存量五参调用零破坏）；execute 末尾评估块（None 守卫 → try evaluate → 三键写入[is_recording 守卫] → except AgentEvaluationError → logger.warning 降级跳过）
- 论证：①可选 None 默认 = 存量构造点零苦役（5-6 十四构造点教训——必选依赖会击穿全部存量构造/测试）；②降级哲学（5.7 DC-7 同款强化）：评估是可观测附加面——评估失败不得阻断工作流主链（LLM 调用失败是评估最高频失败面——主链可用性 > 评估完整性）；③写入位置钉死 execute 体内 return 前（span 在方法返回时 end——end 后 set_attribute no-op；Agent B 调研实证）；④overall 不写 span（5.7 SpanAttributeKeys 契约键表零改动——三键经权重常量可派生 overall，YAGNI + 键表是 5.7 已收敛契约）；⑤**5-7 资产同步义务**：test_acceptance_phoenix_tracer.py AC-4.3 构造签名断言（L1351-1376 inspect.signature 对照五依赖）必须同步更新为六依赖——这是本 Story 唯一的 5-7 资产触碰点（显式登记防遗漏）
- 备选：必选第六依赖（弃——存量苦役）；评估块放 AgentWorkflowService（弃——span 是根 span 上下文[use case 层]，服务层写入拿不到根 span；且服务层职责是六阶段不是评估）；独立 RunEvaluationUseCase 不接主链（弃——epics AC「Given Agent 执行完成」语义绑定工作流 + span 存活期 + 5.9 连续评估数据流依赖主链触发）；评估失败上抛（弃——违反可观测附加面哲学）

**DC-6 评估异常契约——evaluation 子域 450-459 新开 + LLM 族传播纪律照抄**
- 选定：`AgentEvaluationError`（EXCEPTION_450，SystemException——「评估管线执行失败」系统侧语义，AgentWorkflowError[444] 同族论证）；传播纪律照 `_structured_call`：LLMAPIError/LLMResponseError/TimeoutError/ServiceUnavailableError → 450 包装 `from error`；LLMConfigError/CancelledError → 透传
- 论证：①agent 段 440-449 已满（_code_ranges.py L131 注记）——四代开段先例（data_source 410/debate 420/tool_version 430/agent 440）支持 evaluation 独立段 450-459；②SystemException vs ExternalException 抉择：450 的外层语义是「评估管线编排失败」（路由+调用+计算+组装多环节），LLM 外部失败已在内层 cause 链——与 RelevanceEvaluationError（360 ExternalException——检索域直调外部评估服务单环节）语义分立；③异常体系四件套 + test_code_ranges 两表增行 + §3.3.2 文档表——完整 checklist 落地；④降级 catch 面收窄为 `except AgentEvaluationError`（精确捕获——LLMConfigError 透传会击穿主链是**设计意图**[配置错误是开发期错误应显性失败非运行期降级面]）
- 备选：复用 llm 333-339 预留位（弃——评估失败不全是 LLM 失败[Schema 校验/路由匹配失败]）；复用 AgentWorkflowError 444（弃——phase 枚举是六阶段[perceive..package]，"evaluation" 不在其列；444 语义绑定工作流阶段执行）；EvaluationError 命名（弃——agent 前缀对齐 AgentWorkflowError 族命名 + 检索域 RelevanceEvaluationError 消歧）

**DC-7 测试通道与替身——零外部服务自包含 + UDMR 真实链手工装配**
- 选定：评估链测试三件套：①Fake LLM（AsyncMock spec=LLMClientPort + HallucinationEvaluationSchema 身份分派——5-3 先例照抄 + 幻觉分可注入）；②UDMR 真实决策链手工装配（真实 UDMRService/StaticUdmrPolicy/ComplianceGatewayImpl——纯正则纯逻辑零 IO；手写 `_RecordingEventPublisher` + 零 IO 决策日志替身 + 手写健康检查替身[True/False 可控——路由方向控制]）；③span 断言走链级 initialize 全局通道（5-7 SSOT——凡 initialize 一律双复位）
- 论证：①验收「真实服务优先」原则最大化——评估链可测部分（UDMR 决策/合规检查）全真实，仅外部不可达面（LLM SaaS/云端健康探测）用替身；②健康检查替身 True/False 可控 = cloud/local 双路由方向确定性测试（真实 CloudHealthChecker 会真探测云端——测试环境不可控）；③零 IO 替身手写类（非 AsyncMock）——5-4/5-5 手写 duck-typing 先例 + 验收 mock 红线豁免口径（llm_client + 健康检查外部探测 + 零 IO 替身）
- 备选：全 mock 评估链（弃——验收禁 mock 红线）；真实云端健康检查（弃——外部不可达 + 路由方向不可控）；跳过 UDMR 链测试只测 harness（弃——AC-2 路由面无覆盖）

**DC-8 性能口径——Fake LLM 评估管线 P95（网络延迟显式出栈）**
- 选定：P95<500ms 口径 = 评估管线自身开销（幻觉检测调用编排 + 双本地计算 + overall + EvaluationResult 构造），Fake LLM 即时返回；warmup 1 + 20 采样 + exclusive 法 [18] + `_PERF_CACHE` 委托 + `agent-evaluation-perf` 组 + 正向锚（structured_generate 调用计数 == 21）
- 论证：①epics L1794「评估延迟 P95<500ms」对真实 LLM 网络（秒级）不可行——5-7 AC-5「测纯进程内开销」同款口径声明先例（BatchSpanProcessor 异步导出不计入同源逻辑：LLM 网络延迟是外部主导面，预算约束的是管线开销）；②正向锚防静默降级假绿（评估调用真实发生——Fake 计数断言）；③真实 LLM 面不承担 P95 断言（网络主导不可控——验收 LLM 可达场景仅验证端到端真值不计时）
- 备选：真实 LLM 计时（弃——CI 不可行 + flaky）；管线开销 + 固定 sleep 注入（弃——评估无 sleep 需求，注入只会稀释判别力）

**DC-9 生命周期与注册——SINGLETON 双端口 + resolve_optional 接线**
- 选定：agent_evaluation + evaluation_model_resolver 双 SINGLETON（Epic 5 全家政策——agent_tracing/isolation 四注册块/agent_workflow_use_case 连先例）；use case lambda 第六依赖经 `resolve_optional("agent_evaluation")`（可选依赖先例——5.6 audit_service composition_root.py L2903；注册失败降级 None 不阻断 bootstrap——与评估降级哲学同构）
- 论证：①EvaluationHarness 无状态（纯函数式 evaluate——无 eval_history[5.9/5.10 范围]）——SINGLETON 安全；②resolver 持 UDMRService 单例引用 + UDMRConfig 原始值——构造期定格（DC-9[5.7] 设计事实同款：env 后置变更不经 resolve 传导）；③resolve_optional 使评估端口未注册/构造失败时 use case 降级 None（NoOp 评估）——主链永不被评估接线问题阻断
- 备选：SCOPED（弃——无请求级状态）；TRANSIENT（弃——每次 evaluate 新 harness 无意义）；必选 resolve（弃——注册缺失击穿 bootstrap，违背附加面哲学）

**关键决策对照表（选中方案 vs 备选）：**

| 决策点 | 选中 | 备选（弃因） |
|--------|------|-------------|
| 端口族 | 双端口分立（DC-1） | 单端口全包（层违例 + 演化耦合）；harness 自写 span（职责分裂 + R1-DF3 触发） |
| 幻觉检测 | structured_generate + 扁平 Schema（DC-2） | phoenix.evals（OD-1[5.7] 不触发 + 依赖风险）；嵌套 Schema（anthropic 栈溢出） |
| 模型路由 | UDMRService.decide() in-band（DC-3） | 直调 policy.route（绕过合规/事件/日志）；静态默认（AC 失败）；静默回退（漂移掩盖） |
| 三指标算法 | 两本地 + 一 LLM（DC-4） | 全 LLM（延迟/失败面）；actual=overall（循环依赖） |
| 主链接入 | 第六可选依赖 + 降级（DC-5） | 必选依赖（存量苦役）；服务层评估（根 span 不可达）；独立用例（AC 语义/数据流断链） |
| 异常 | evaluation 450 新段 + SystemException（DC-6） | llm 预留位（语义不符）；444 复用（phase 枚举不含 evaluation） |
| 测试替身 | UDMR 真实链 + Fake LLM（DC-7） | 全 mock（红线）；真实健康检查（方向不可控） |
| 性能口径 | 管线开销 P95（DC-8） | 真实 LLM 计时（CI 不可行） |

### 风险登记

| # | 风险 | 处置 |
|---|------|------|
| 1 | UDMRService.decide() 事件副作用量级（评估高频调用 → RoutingDecided 事件 + 决策日志逐次累积——每工作流 run +1 事件/日志；MVP 单 Agent 低频可接受） | 语义正确性论证：评估调用是真实 LLM 调用（成本应统计/路由应审计——CostMetricsListener 既有面覆盖）；量级风险登记：5.9+ 多 Agent 高频场景若事件洪流再评估（批量评估/采样评估策略——deferred 知悉不进台账，触发条件明确[事件量监控告警]） |
| 2 | 评估 LLM 调用叠加主链延迟（+500ms 预算内——但真实 LLM 网络秒级时主链总延迟显著增加） | DC-5 降级哲学覆盖失败面；延迟面：MVP 接受（评估是 FR-EV-02 P0 价值）；V1 若主链延迟敏感可评估异步评估/旁路评估（范围边界表外——V1 按需，deferred-work 不登记[无当前 gap——设计选项记录]） |
| 3 | UDMR 合规检测 forced_local 路由（评估文本命中 PIPL 正则 → 评估模型强制本地——本地小模型幻觉检测质量弱于云端） | DC-3 论证②：合规是防线非缺陷（强制本地是正确行为）；测试预期钉死（AC-2 合规注记——评估文本含敏感词场景路由断言 local）；质量风险知悉：V1 评估模型池分级（deferred 不登记——UDMR 域演化） |
| 4 | 5-7 AC-4.3 构造签名断言遗漏更新（use case 六依赖后 5-7 验收 15 场景红——回归破坏） | Task 3 循环 B 显式登记同步义务 + Task 3 循环 C 全家回归清单含 5-7 验收 15 场景；AST 验证器 C 六依赖基线双锚（更新后断言锁死） |
| 5 | RoutingDecided 事件与评估链的发布依赖（resolver 手工装配测试中 publisher 替身遗漏 → decide() 内部发布抛异常击穿 resolve_config） | AC-2 装配清单钉死四替身（publisher/决策日志/健康检查/合规真实）；UDMRService 构造器依赖注入完整清单对齐组合根 L1627-1647 形态 |
| 6 | hallucination_score 语义误读（后续消费方[5.9/仪表盘]误当「越高越好」与 context_relevance 混用） | OD-5 显式裁定 + EvaluationResult 字段 docstring 语义注记 + overall 反转公式 docstring；5.9 立项时 CUSUM 方向消费以 overall_score 为准（本 Story 故事文件传递锚） |
| 7 | Fake LLM Schema 身份分派与既有五 Schema 冲突（HallucinationEvaluationSchema 意外与既有 Schema 同名/同对象——分派键失效） | Schema 独立新类 + AC-1 验证标准「与既有五 Schema 两两不同 is not 断言」；agent_workflow_schemas.py L9-11 设计决策前提保持 |
| 8 | mypy 对 EvaluationHarness 泛型/协议签名的类型窄化告警（async Protocol 方法返回 dataclass） | 标准形态（Protocol async def + dataclass 返回——relevance_evaluation_service 先例无告警）；实施时 ruff+mypy 门禁即验 |
| 9 | 组合根 lambda 构造期 UDMRConfig.from_env() 的 101 抛（UDMR_* 环境损坏 → resolve("evaluation_model_resolver") 抛 → bootstrap 击穿——与 5-7 R1-13 同构风险） | use case 第六依赖经 resolve_optional（DC-9——fallback 面覆盖 KeyError/RuntimeError/ImportError；ConfigurationError 不在默认 fallback_on[R1-DF3 同源缝隙]）→ **接线形态钉死**：lambda 内 try/except ConfigurationError 降级 None（组合根内联防护——5-7 _wire_agent_tracing 整段 try 同款形态），评估接线配置错误只损失评估面不阻断主链 |

### 项目结构说明 Project Structure

```
src/
├── application/
│   ├── ports/
│   │   ├── agent_evaluation.py             # 新建：AgentEvaluationPort + EvaluationModelResolverPort + EvaluationResult + EVALUATION_WEIGHTS
│   │   └── __init__.py                     # 修改：聚合导出
│   ├── services/
│   │   ├── evaluation_harness.py           # 新建：EvaluationHarness（幻觉检测 + 双本地计算 + overall + evaluate 编排）
│   │   ├── evaluation_schemas.py           # 新建：HallucinationEvaluationSchema（扁平 pydantic）
│   │   ├── evaluation_prompts.py           # 新建：幻觉检测 prompt 模块（SYSTEM_PROMPT + USER_TEMPLATE）
│   │   └── agent_workflow_service.py       # 零改动（六阶段服务不碰——评估块在 use case 层）
│   └── use_cases/
│       └── run_agent_workflow.py           # 修改：第六可选依赖 + execute 末尾评估块（纯附加）
├── domain/
│   └── exceptions/
│       ├── evaluation_exceptions.py        # 新建：AgentEvaluationError（EXCEPTION_450）
│       ├── _code_ranges.py                 # 修改：evaluation 子域 450-459 + _CLASS_TO_SUBDOMAIN
│       └── __init__.py                     # 修改：导出
├── infrastructure/
│   ├── routing/
│   │   └── udmr_evaluation_model_resolver.py  # 新建：UdmrEvaluationModelResolver（EvaluationModelResolverPort 实现）
│   └── ...
└── composition_root.py                     # 修改：# === Story 5.8 === 双注册 + use case lambda 更新

tests/
├── unit/
│   ├── domain/exceptions/
│   │   └── test_evaluation_exceptions.py   # 新建（450 构造/映射/注册）
│   ├── application/
│   │   ├── test_agent_evaluation_model.py  # 新建（EvaluationResult + 端口形态）
│   │   └── services/
│   │       └── test_evaluation_harness.py  # 新建（三循环用例）
│   │   └── use_cases/
│   │       └── test_run_agent_workflow.py  # 追加（评估块三面）
│   ├── infrastructure/routing/
│   │   └── test_udmr_evaluation_model_resolver.py  # 新建（六用例——真实 UDMR 链）
│   └── architecture/
│       └── test_arch_evaluation.py         # 新建（验证器 A/B/C）
├── contracts/
│   ├── test_port_contract_agent_evaluation.py          # 新建（11 维度）
│   └── test_port_contract_evaluation_model_resolver.py # 新建（11 维度）
├── integration/
│   └── test_integration_agent_evaluation.py # 新建（五场景 + 计时委托常量单源）
├── acceptance/
│   ├── test_acceptance_agent_evaluation.feature  # 新建（13+收尾=14 场景）
│   ├── test_acceptance_agent_evaluation.py       # 新建（BDD 步骤）
│   └── test_acceptance_phoenix_tracer.py         # 修改：AC-4.3 构造签名基线更新（5-7 资产同步）

docs/architecture/sisys-uni-exception-design.md   # 修改：§3.3.2 编码分配表（Task 1）
docs/architecture/architecture.md                 # 修改：§14.4 交付注记（Task 6）
docs/architecture/sisys-core-domain-design.md     # 修改：§17.3.8 实现注记（Task 6）
_bmad-output/implementation-artifacts/deferred-work.md  # 修改：处置注记（Task 0/6）
_bmad-output/implementation-artifacts/sprint-status.yaml  # 修改：5-8 状态流转
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 5.7](./5-7-phoenix-evaluation-harness.md)（v2.2.1 done 收敛态——文档审查 5 轮 + 代码审查 5 轮完整教训链）+ [Story 5.3](./5-3-single-agent-workflow.md)（5.8 直接依赖的工作流宿主）

**关键学习/Key Learnings:**
- **构造签名扩展 = 回归面苦役**（5-6 十四构造点；5-7 结构性规避：装饰器纯附加）——本 Story 对策：第六可选依赖 None 默认（存量五参调用零破坏）+ 5-7 AC-4.3 断言基线同步更新（唯一触碰点显式登记——风险表 #4）
- **断言可满足性断层是最大实施陷阱**（5-6 R3-F1 端口 Raises 与实现不满足；5-7 R1-1 span 可观测机制自相矛盾）——本 Story 对策：span 断言锚全文唯一口径（链级 initialize 全局通道——评估块写入经 get_current_span 在根 span 上下文，5-7 SSOT 直接继承）；AC-1 异常矩阵透传/包装分述（332/Cancelled 透传与 450 包装不同断言路径）
- **断言恒真防范**（Epic 4 教训 8/13 恒真断言；5-7 record_exception 删除不红——框架兜底）——本 Story 对策：非硬编码判别用双配置矩阵（config.model 随注入变化——硬编码实现必红）；正向锚（Fake LLM 调用计数 == 采样数）；overall 手算对照（权重改错必红）
- **测试环境前提必须钉死**（5-7 OTel 全局状态 R1 实测 Once 闩锁 + TestInitTracing 泄漏源）——本 Story 继承：凡 initialize 一律双复位 + 前提测试条款 + env 不带 PHOENIX_TRACING_ENABLED=true
- **委托计时模式**（_PERF_CACHE + xdist_group 同组 + 常量单源 + 采样禁双跑 + 复测保护）——本 Story 照抄（AC-5）
- **Fake LLM Schema 身份分派前提**（Schema 两两不同——5-3 设计决策）——本 Story 新增 HallucinationEvaluationSchema 分派分支保持前提
- **组合根 lambda 构造期配置异常击穿 bootstrap**（5-7 R1-13/R2-6 try 罩整段）——本 Story 对策：resolve_optional + lambda 内 ConfigurationError 防护（风险表 #9）
- **OD-n 偏离声明编号 + gap 四要素 + 承接方链接**（5-6/5-7 规范）——本 Story OD-1~OD-5 + 三条 5-7 移交留项处置落盘
- **验收禁 mock 红线豁免口径**（llm_client 外部 SaaS + 零 IO 手写替身——5-3/5-7 先例）——本 Story 豁免面扩展：健康检查替身（外部探测面）
- **mypy 全仓验证盲区**（5-7 v2.2.1 教训：装饰器类跨文件类型影响组件改签名后必须 mypy . 全仓）——本 Story 对策：use case 构造签名扩展后跑全仓 mypy 验证（Task 3 收尾）

**应用到本故事/Applied to This Story:**
- [ ] 第六可选依赖 + 5-7 断言同步更新（Task 3 循环 B）
- [ ] span 断言锚 SSOT 继承（Task 0.4/0.6 + 测试隔离约束节）
- [ ] 双配置矩阵/正向锚/手算对照三判别力设计（AC-1/AC-2/AC-5）
- [ ] OTel 双复位纪律全套继承（测试隔离约束节）
- [ ] 委托计时三件（Task 4 + AC-5）
- [ ] resolve_optional + lambda ConfigurationError 防护（Task 1 循环 C + 风险表 #9）
- [ ] 全仓 mypy 验证（Task 3 收尾）

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
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（L1765-1811） |
| **架构文档** | `docs/architecture/architecture.md`（§14.4/L2626-2643/§17.4/L2944） |
| **核心域设计** | `docs/architecture/sisys-core-domain-design.md`（§17.3.8 L1594-1702） |
| **统一异常设计** | `docs/architecture/sisys-uni-exception-design.md`（§3.3/§3.12） |
| **前一个 Story** | `5-7-phoenix-evaluation-harness.md`（v2.2.1 done——直接依赖）+ `5-3-single-agent-workflow.md`（宿主依赖） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（含范围边界表——与 5.9/5.10/V1/deploy 精确切分）
- [x] 架构约束从 architecture.md/sisys-core-domain-design.md 提取（§17.3.8 评估面 + §14.4 交付注记 + 异常体系 §3.3/§3.12）
- [x] 前一个故事学习经验整合（5-7 教训链 + 三条移交留项处置 + trace_id 防呆复核）
- [x] 五视角并行代码调研（UDMR 路由机制与消费模式 / 5.7 追踪交付物与 span 通道 / 工作流数据模型与 LLM 调用面 / 验收测试模板与 R6 改造形态 / 偏离台账与异常体系组合根惯例——关键事实独立验证：per-call UDMR 消费模式零先例 / agent 段 440-449 全满 / RelevanceEvaluationPort 语义甄别 / 5-7 AC-4.3 构造签名断言绊线 / anthropic 扁平 Schema 约束 / SpanAttributeValue 值域）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（DC-1~DC-9 设计决策 + OD-1~OD-5 偏离声明 + 风险九项）
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/5-8-agent-output-quality-evaluation.md`（本文件）

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/application/ports/agent_evaluation.py` - 评估端口族（AgentEvaluationPort + EvaluationModelResolverPort + EvaluationResult + 权重常量）
- `src/application/services/evaluation_harness.py` - EvaluationHarness（评估编排核心）
- `src/application/services/evaluation_schemas.py` - HallucinationEvaluationSchema
- `src/application/services/evaluation_prompts.py` - 幻觉检测 prompt 模块
- `src/infrastructure/routing/udmr_evaluation_model_resolver.py` - UDMR in-band 模型解析器
- `src/domain/exceptions/evaluation_exceptions.py` - AgentEvaluationError（EXCEPTION_450）
- `tests/unit/domain/exceptions/test_evaluation_exceptions.py` - 异常单测
- `tests/unit/application/test_agent_evaluation_model.py` - 端口模型单测
- `tests/unit/application/services/test_evaluation_harness.py` - Harness 单测（三循环）
- `tests/unit/infrastructure/routing/test_udmr_evaluation_model_resolver.py` - resolver 单测（真实 UDMR 链）
- `tests/contracts/test_port_contract_agent_evaluation.py` - 契约测试
- `tests/contracts/test_port_contract_evaluation_model_resolver.py` - 契约测试
- `tests/integration/test_integration_agent_evaluation.py` - 集成（五场景 + 计时委托）
- `tests/unit/architecture/test_arch_evaluation.py` - AST 架构验证器
- `tests/acceptance/test_acceptance_agent_evaluation.feature` - Gherkin（13+收尾=14 场景）
- `tests/acceptance/test_acceptance_agent_evaluation.py` - BDD 步骤实现

**待修改的文件/To Be Modified (Dev Story 实施):**
- `src/application/use_cases/run_agent_workflow.py` - 第六可选依赖 + execute 评估块（纯附加）
- `src/application/ports/__init__.py` - 聚合导出
- `src/domain/exceptions/_code_ranges.py` - evaluation 子域注册
- `src/domain/exceptions/__init__.py` - 导出
- `src/interfaces/api/exception_handlers.py` - EXCEPTION_HTTP_MAP 450→500
- `src/composition_root.py` - Story 5.8 区段双注册 + use case lambda 更新
- `tests/acceptance/test_acceptance_phoenix_tracer.py` - AC-4.3 构造签名基线更新（5-7 资产同步）
- `tests/unit/application/use_cases/test_run_agent_workflow.py` - 评估块三面追加
- `docs/architecture/sisys-uni-exception-design.md` - §3.3.2 编码分配表
- `docs/architecture/architecture.md` - §14.4 交付注记
- `docs/architecture/sisys-core-domain-design.md` - §17.3.8 实现注记
- `_bmad-output/implementation-artifacts/deferred-work.md` - 三条处置注记 + OD-3 V1 通道登记
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - 状态流转

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 5.8 |
| **Story Key** | 5-8-agent-output-quality-evaluation |
| **File** | `_bmad-output/implementation-artifacts/stories/5-8-agent-output-quality-evaluation.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 5: Agent 协作系统（价值组：单 Agent 战略规划能力——EV 可观测族第二 Story） |
| **优先级** | P0-8（epics 执行序；FR-EV-02 功能 P0——双锚） |
| **覆盖 FR** | FR-EV-02（Agent 输出质量评估——幻觉检测/上下文相关性/置信度校准） |
| **性能锚** | epics L1794（评估延迟 P95<500ms——Fake LLM 管线口径 DC-8） |
| **覆盖率锚** | 应用层 ≥85%（epics L1798）/ infrastructure ≥75%（epics L1799 口径映射）/ domain ≥90% 维持 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | （待审查后填写） | | |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** [待审查时填写]
**审查模式:** [待审查时填写]

#### 需决策 Decision Needed

- 无（待审查后填写）

#### 已修复 Patch

- （待审查后填写）

#### 已推迟 Defer

- （待审查后填写）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施（从 Task 0 开始）
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

### 📋 变更日志 Change Log [dev-story 必填]

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-10-28 | v1.0.0 | 创建故事文件（五视角并行调研：UDMR 路由机制/5.7 追踪交付物/工作流数据模型/验收测试模板/偏离台账与异常体系；9 项关键架构决策 DC-1~DC-9 + 5 项偏离声明 OD-1~OD-5 + 风险九项；双端口分立[DC-1——评估契约与模型解析解耦]；幻觉检测 structured_generate + 扁平 Schema[DC-2——OD-1[5.7] 触发条件裁定不满足，零新依赖]；UDMR in-band 动态路由[DC-3——仓内首个 per-call 路由消费方]；三指标算法裁定[DC-4——OD-3 证据支撑度启发式/OD-4 actual 口径/OD-5 幻觉分字面语义]；第六可选依赖主链接入 + 降级[DC-5——5-6 苦役结构性规避 + 5-7 AC-4.3 断言同步]；evaluation 子域 450-459 新开[DC-6——agent 段满后四代开段先例]；5-7 移交留项三项处置[OD-1 裁定不触发/OD-2 本 Story 兑现/R1-DF3 顺延] + trace_id 防呆复核零风险知悉） |

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-10-28
**最后更新/Last Updated:** 2026-10-28
**更新说明/Description:**
- v1.0.0: 创建故事文件
