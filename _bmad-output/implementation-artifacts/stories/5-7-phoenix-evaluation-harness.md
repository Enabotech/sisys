# Story 5.7: Phoenix Evaluation Harness 基础（全链路追踪）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 可观测性工程师,
**I want** 实现 Phoenix Evaluation Harness 全链路追踪基础设施（PhoenixTracer + `@trace` 装饰器自动记录 span）,
**So that** Agent 执行过程自动记录 span，支持全链路追踪和性能分析（FR-EV-01——5.8 评估/5.9 漂移检测的可观测底座）。

### 业务价值

Epic 5「单 Agent 战略规划能力」价值组的可观测性基座 Story：5-3 交付了六阶段执行闭环（感知→规划→执行→验证→反思→证据打包），本 Story 交付**全链路追踪基础设施**——`PhoenixTracer`（project_name="sisys-agent"）+ `@trace` 装饰器（agent_execution 根 span + agent.{phase} 六阶段子 span 树）+ span 属性写入通道（`eval.hallucination_score`/`eval.context_relevance`/`drift.detected` 键常量注册——5.8/5.9 填值）+ `ExecutionContext.trace_id` run 级贯通（5-3 预留位核销）。这是 FR-EV-01 的闭环 Story，也是 sisys-core-domain-design.md §17.3.8（L1594-1702 Agent 评估与可观测性）追踪面的落地：后续 5.8（幻觉检测/上下文相关性/置信度校准写 span 属性）、5.9（CUSUM 漂移写 drift.detected）、5.10（评估历史入 Checkpoint）全部以本 Story 的 span 基础设施为锚点。代码侧已有三处钦定 5.7 接入注释：`agent_workflow_service.py` L29-31/L256（trace_id 空串归 5.7）、`chain_of_thought.py` L4（5.7 消费真源）、`agent_events.py` L44/L75（5.7 消费锚点）。

**范围权威**：epics_v1.0.md L1715-1763（AC + 实现内容 + 测试要求 + 性能锚 L1745-1747）、L465（FR-EV-01 P0）、L1443（依赖 Story 5.3，P0-7）、L685（Epic 5 含 EV-01/02）；sisys-core-domain-design.md §17.3.8（L1594-1702——PhoenixTracer(project_name="sisys-agent")/@trace/start_span("agent_execution")/span 属性 eval.*/drift.detected/§2.5 监控集成表 L1695-1702）、L1118（AgentWorkflow.execute @trace 伪码）；architecture.md §14.4 可观测性设计（L2626-2633）、L2944（Agent 评估：Phoenix/Arize 开源方案）、ADR-012（CUSUM——5.9 范围）；prd.md L1842 附近 EV 系列（FR-EV-01 功能 P0/epics 执行序 P0-7 双锚）；5-3 故事移交注记（trace_id L256/事件锚点/AgentDecided 订阅决定 L595/R1-DF2 锚位顺延 L740）；5-6 故事范围边界表移交（L42「事件订阅消费基建——归 5.7」——**处置见范围边界表与 OD-4**）。

### 范围边界（与后续 Story 的精确切分）

| 能力 | 本 Story（5.7） | 后续 Story |
|------|----------------|-----------|
| PhoenixTracer（project_name="sisys-agent"）+ initialize/shutdown 生命周期 | ✅ infrastructure/monitoring + 单测 | — |
| PhoenixConfig（enabled/endpoint/project_name/sampling——env 驱动） | ✅ infrastructure/config + .env.example | — |
| AgentTracingPort 端口 + SpanHandle 协议 + SpanAttributeKeys 常量注册表 | ✅ application/ports + 契约测试 | — |
| `@trace` 装饰器（agent_execution 根 span + agent.{phase} 子 span，NoOp 零开销降级） | ✅ application/tracing.py | — |
| 工作链接入（UseCase @trace + 六阶段 @trace + span 业务属性写入） | ✅ 纯附加装饰（零构造签名变化） | — |
| `ExecutionContext.trace_id` run 级贯通（span trace_id → 工具执行层） | ✅ 5-3 预留位核销 | — |
| eval.*（hallucination_score/context_relevance/confidence_accuracy）/drift.detected 键常量 + 写入通道 | ✅ 常量注册 + 通道能力验证（OD-2） | 5.8/5.9 生产填值 |
| 性能（span 记录 P95<5ms + 追踪开销<1%） | ✅ 集成委托计时 | — |
| 幻觉检测 llm_eval_binary_classifier / compute_context_relevance / compute_confidence_accuracy / EvaluationHarness.evaluate | ❌ 不做（§17.3.8 评估面——epics 5.8） | 5.8（依赖本 Story span 属性通道） |
| CUSUMDriftDetector / is_drifted / trigger_recalibration | ❌ 不做（ADR-012——epics 5.9） | 5.9 |
| CheckpointWithEvaluation / 评估历史入 Checkpoint | ❌ 不做 | 5.10（依赖 6.3） |
| `eval.*`/`drift.detected` 属性**生产预置与填值** | ❌ 不做（OD-2——值语义归 5.8/5.9；OTel 属性不接受 None 预置，哨兵值有语义歧义风险） | 5.8（eval.*）/5.9（drift.*）经 SpanAttributeKeys 常量填值 |
| arize-phoenix 运行时依赖引入 + `phoenix.otel.register` 集成 | ❌ 不做（OD-1——伪码 API 已废弃 + 重依赖 + OTel 栈升级回归风险） | V1 按需评估（openinference 轻量包） |
| Phoenix server 部署（容器/compose/OTLP 接收端运维） | ❌ 不做（部署面——客户端经 OTLP endpoint 指向即可，测试全用 InMemorySpanExporter 零外联） | deploy/ops 立项（Epic 0 交付系统范畴） |
| eval.* 指标 Prometheus 导出 + Grafana 仪表盘（§2.5 集成表） | ❌ 不做（评估指标有值才可导出——依赖 5.8） | 5.8 起随评估指标扩展 |
| 事件订阅消费基建（EventHandler 形态消费 AgentDecided/AgentInstantiated/AgentProfileLoaded——5-6 L42 移交） | ❌ 不做（OD-4——epics 5.7 范围权威是 @trace 追踪不含 RabbitMQ 消费侧基建；reliable 事件不可经 DualChannelEventBus.subscribe 订阅[5-6 DC-2 论证②]） | 5.11 SAP 协议（P1-11，依赖 1.3 事件总线的首个消费 Story）+ deferred-work 登记 |
| AgentDecided 订阅接线（AutoTriggerHandler 已注册未订阅——5-3 L595 移交决定项） | ❌ 不接线（span 追踪是进程内同步面，不依赖事件订阅；AutoTriggerHandler 接线归其消费语义立项） | 1-14a 触发链扩展/9-x 多 Agent 立项评估 |
| outbox poller 宿主 / 发布失败可观测信号（deferred-work R1-DF2——锚位 5.3→顺延 5.7） | ❌ 不做（Task 0 评估处置：本 Story 交付 span 追踪面不含可靠投递消费基建） | 5.11 消费侧立项时一并定夺（deferred-work 锚位再顺延登记） |
| 工具执行层孙 span（ToolExecuted 事件关联 span） | ❌ 不做（MVP 两级树够用；trace_id 已贯通工具层） | V1 深度追踪按需 |
| LangGraph callback/hook 机制 | ❌ 不做（仓内无此机制；span 在应用层根/子 span 已覆盖引擎调用） | — |

### 偏离声明（Deviation Declarations）

| # | 偏离 | 规划原文 | 偏离理由与归宿 |
|---|------|---------|---------------|
| OD-1 | 不引入 arize-phoenix 运行时依赖；PhoenixTracer 以仓内既有 opentelemetry-api/sdk/exporter-otlp ^1.21.0（pyproject L88-90）实现同构语义——`project_name="sisys-agent"` 经 OTel Resource `service.name` 承载（Phoenix OTLP 接收端按 service.name 归项目），span 经 OTLP exporter 指向 Phoenix server | sisys-core-domain-design.md §17.3.8 L1600-1602（`from phoenix.tracing import trace` + `phoenix.evals.llm_eval_binary_classifier` 伪码） | ①`phoenix.tracing.trace` 是 2023 年代旧 API——Phoenix 官方生态已迁移到 OpenInference/OpenTelemetry（`phoenix.otel.register` 是现入口，trace 装饰器职责归 openinference-instrumentation 家族）；②arize-phoenix 20.26.1（2026-10 最新稳定版）依赖树含 FastAPI server/grpc/openinference 全家且 container extra 钉死 opentelemetry-sdk==1.45.0——强制升级仓内 ^1.21.0 OTel 栈威胁 1.3 事件总线既有 OTEL 集成（otel_config.py，回归面不可控）；③Phoenix 官方客户端模式本就支持「任意 OTLP 导出 + Phoenix server 独立部署」——零运行时新依赖即可达成同等追踪语义（span 创建/属性/导出全由 OTel SDK 承载）；④CLAUDE.md import-untyped 修复成本：arize-phoenix 未确认 py.typed，引入则可能需建 stubs/phoenix/。**触发条件 = 5.8 需要 OpenInference LLM span 语义约定（llm.* 属性族）或 Phoenix evals 内置评估器时**——届时评估引入轻量 openinference-semantic-conventions / arize-phoenix-client；**承接方 = Story 5.8（评估指标 span 化）**；**Task 0.7 随 deferred-work.md 登记**（gap 四要素：描述/触发条件/归宿/承接方链接） |
| OD-2 | `eval.hallucination_score`/`eval.context_relevance`/`drift.detected` 属性**不做生产预置**——本 Story 交付 `SpanAttributeKeys` 常量注册表（键字符串单一真源）+ 属性写入通道（create_span/SpanHandle.set_attribute/get_current_span 三通道），AC-3.2 以「通道能力」口径验证（测试写入 `SpanAttributeKeys.EVAL_HALLUCINATION_SCORE` 键后断言 span 属性含该键） | epics_v1.0.md L1735（「And span 包含 eval.hallucination_score、eval.context_relevance 属性」）+ L1736（「漂移检测完成后 span 设置 drift.detected 属性」） | ①属性值生产点在 5.8（幻觉检测/相关性）与 5.9（漂移检测）——5.7 无值可写；②OTel `set_attribute` 不接受 None 值（合法类型 str/bool/int/float/序列），「预置 None」技术不可行；哨兵值（0.0/-1.0）与真实评估值（0.0 可能是合法幻觉分）语义歧义——预置反而毒化下游过滤；③常量注册表保证 5.8/5.9 引用同一键字符串（防拼写漂移），通道能力测试证明写入→导出→断言全链可用——epics AC 意图（评估指标可挂到 span）完整达成。**归宿 = 5.8 填 eval.*/5.9 填 drift.detected（经 SpanAttributeKeys 常量）**；**Task 0.7 随 deferred-work.md 登记** |
| OD-3 | 测试文件命名从仓内惯例不从 epics 占位名：`tests/unit/infrastructure/monitoring/test_phoenix_tracer.py`（epics 占位 `tests/unit/architecture/test_phoenix_tracer.py`）+ `tests/unit/architecture/test_arch_phoenix_tracer.py`（AST 架构验证器——仓内 per-story 惯例）+ `tests/integration/test_integration_phoenix_tracer.py`（epics 占位 `test_phoenix_tracer_integration.py`） | epics_v1.0.md L1759-1760（测试文件占位名） | 5-6 OD-4 同款注记：epics 占位名是规划文本，仓内惯例（test_arch_* 前缀/unit 按层归目录/test_integration_* 前缀）是活代码事实源；规划占位名与仓内惯例的正常偏差，随本 OD 知悉不进台账 |
| OD-4 | 5-6 范围边界表移交的「事件订阅消费基建（EventHandler 形态）」不入本 Story 范围 | 5-6 故事 L42（「事件订阅消费写日志（EventHandler 形态）｜❌ 不做（DC-2——audit-first 同步写；消费基建归 5.7）」——注：「5.7 Phoenix（事件订阅基建面）」） | epics_v1.0.md L1715-1763 是本 Story 范围权威：PhoenixTracer/@trace/span 追踪，**不含任何事件消费基建**；5-6 移交注记的「消费基建归 5.7」与 epics 范围定义冲突时以 epics 为准（RabbitMQ 消费侧/Outbox 轮询宿主是可靠投递基建，与进程内 span 追踪正交；reliable 事件不能经 DualChannelEventBus.subscribe 订阅——5-6 DC-2 论证②，消费基建须专项立项）；deferred-work R1-DF2 锚位随本裁定**再顺延至 5.11**（P1-11，依赖 1.3 事件总线的首个消费 Story）。**承接方 = Story 5.11（sap-protocol-support）**；**Task 0.7 随 deferred-work.md 登记锚位顺延** |

> 优先级双锚说明（非偏离）：epics L465 将 FR-EV-01 定级 P0（功能等级），epics L1443 执行优先级 P0-7（执行序——依赖 5.3 完成后执行，与 5.4/5.5/5.6 并行序不冲突）。两者不矛盾：功能等级与执行序双锚。

---

## 🔗 前置依赖（全部 ✅ 已完成，无阻塞）

| 依赖 | 组件 | 用途 | 状态 |
|------|------|------|------|
| Story 5.3 | `RunAgentWorkflowUseCase.execute`（application/use_cases/run_agent_workflow.py L86-163——七步编排，**@trace("agent_execution") 根 span 接入位**）+ `AgentWorkflowService` 六阶段方法（application/services/agent_workflow_service.py L103——perceive/plan/execute/verify/reflect/package_evidence，**子 span 接入位**）+ `ExecutionContext.trace_id` 预留位（L254-257 空串 + 注释「run 级 trace_id 归 5.7 追踪接入」）+ `AgentWorkflowResult` 五字段（chain/evidence/workflow_status/retry_count/executed_phases——span 业务属性数据源）+ `ChainOfThought` VO（domain/value_objects/chain_of_thought.py L34——L4 注释「5.7 Phoenix 追踪消费的结构化真源」）+ `executed_phases` 阶段名枚举（钉死 "package" 非 package_evidence——**span 名对齐**） | 追踪接入的全部宿主 | ✅ done |
| OTel 基建（Epic 1 资产） | `opentelemetry-api/sdk/exporter-otlp ^1.21.0`（pyproject.toml L88-90 已装——**零新依赖**）+ `otel_config.py`（infrastructure/monitoring/otel_config.py——init/shutdown/get_tracer_provider/**reset_for_testing L315-339[直接复位 OTel 内部 `trace._TRACER_PROVIDER`——全局 provider 单次设置约束的测试解法先例]**/BatchSpanProcessor/OTLP grpc 4317 + http 4318 双协议生命周期先例）+ `OpenTelemetryTracer.create_span`（event_metrics.py L227-264——contextmanager + `trace.get_tracer` + `start_as_current_span` + `set_attribute` + **未启用 yield None 零开销降级**——PhoenixTracer.create_span 同构模板） | SDK 依赖 + 生命周期/降级两大照抄模板 | ✅ 就绪 |
| 监控域端口先例 | `MetricsPort`（application/ports/metrics_port.py——应用层可观测端口先例）+ `CacheMetricsPort`（runtime_checkable + property 形态）+ 组合根注册样例（cache_metrics L1825-1834 lambda 直 new infrastructure 实现 SINGLETON 先例） | AgentTracingPort 端口形态参照 | ✅ 就绪 |
| 配置先例 | `MetricsConfig`（infrastructure/config/metrics.py L12-55——frozen dataclass + `from_env()` classmethod + bool 解析 `in ("true","1","yes")` 惯例）+ `.env.example` 可观测性区（L224-236——OTEL_* 五变量 + EVENT_BUS_OTEL_TRACE_ENABLED=false + METRICS_* 四变量，PHOENIX_* 变量插入锚点） | PhoenixConfig 照抄模板 | ✅ 就绪 |
| 装饰器埋点先例 | `SemanticCacheMiddleware`（application/services/semantic_cache_middleware.py——构造注入 metrics 端口包装 search_service，组合根 L1839-1853 装配）——**应用层装饰器/包装器埋点范式先例**；@trace 装饰器是其在「方法装饰器」维度的延伸（静态装饰无注入通道 → OTel 全局 API——DC-4） | 装饰器合法性先例 | ✅ 就绪 |
| 测试基建 | `tests/acceptance/conftest.py`（acceptance_env_config L99-106 + 文件名服务 marker 自动挂载 L110-140）+ 模块级 `event_loop` fixture 惯例（≥10 验收文件同款）+ `_run_async` 同循环调度 + 步骤化门控 skip 先例（5-6 最新 R6 形态）+ `tests/integration/conftest.py` xdist_group 计时组惯例 | 验收/集成骨架 | ✅ 就绪 |
| 异常体系 | `ConfigurationError`(101——PhoenixConfig 校验) 全部复用（DC-8——零新异常；追踪运行面降级不上抛） | 配置校验 | ✅ 就绪 |

**移交给本 Story 的留项（必须处置）**：

| # | 留项 | 来源 | 本 Story 处置 |
|---|------|------|--------------|
| 1 | **R1-DF2 事件观测面**（outbox 无 poller 宿主——AgentInstantiated/AgentProfileLoaded reliable 事件 pending 累积 + 发布失败无程序化可观测信号；锚位 5-3→顺延 5.7） | deferred-work.md L169 | **Task 0 评估处置**：本 Story 交付进程内 span 追踪面，不含可靠投递消费基建（poller 宿主）与 CLI 发布失败退码化——锚位随 OD-4 **再顺延至 5.11**（首个事件消费 Story 立项时一并定夺）；Task 0.7 在 deferred-work.md 原条目追加 5.7 注记 |
| 2 | **AgentDecided 无活跃订阅者**（AutoTriggerHandler 端口已注册组合根 L1094 但未进 handler_names 订阅列表 L2800-2809——5-3 L595「5.7 Phoenix 追踪立项时决定是否接线」） | 5-3 移交 | **不接线**（span 追踪是进程内同步面不依赖事件订阅；AutoTriggerHandler 接线归其消费语义立项）；Task 0.7 知悉登记（不进 deferred-work——无 gap，仅决定记录） |
| 3 | **5-6「事件订阅消费基建归 5.7」移交注记** | 5-6 范围边界表 L42 | **OD-4 裁定**：不入 5.7（epics 范围权威）；承接 5.11 + deferred-work 登记 |

---

## 🔗 现有代码继承（必须复用，禁止重复定义）

> ⚠️ **防重复造轮子清单**——以下组件已存在，dev agent 只可「直接复用 / 参考照抄」，禁止新建同义组件。

| 组件 | 文件路径 | 复用方式 |
|------|---------|---------|
| OTel SDK 三件套 | pyproject.toml L88-90（opentelemetry-api/sdk/exporter-otlp ^1.21.0） | **直接复用——零新运行时依赖**（OD-1）；InMemorySpanExporter 在 `opentelemetry.sdk.trace.export`（SDK 自带，测试零新依赖） |
| `init()/shutdown()/reset_for_testing()` 生命周期三件套 | `src/infrastructure/monitoring/otel_config.py` L167/L277/L315-339（含 `trace._TRACER_PROVIDER = None` 内部状态复位——OTel 全局单次设置约束的测试解法） | **参考照抄**——PhoenixTracer.initialize/shutdown/reset_for_testing 同构（⚠️ **不改动 otel_config.py 本体**——event-bus 域资产零侵入；5.7 成为全局 TracerProvider 唯一 setter 的声明见 DC-6） |
| `create_span` contextmanager + None 降级 | `src/infrastructure/monitoring/event_metrics.py` L227-264（`@contextmanager` + `trace.get_tracer(...)` + `start_as_current_span` + `set_attribute` 点分键 + 未启用 `yield None`） | **参考照抄**——PhoenixTracer.create_span 同构骨架（差异：attributes 参数化 + initialize 状态守卫 + handle 返回 OTel Span 原生对象——duck-type SpanHandle 协议零包装层） |
| `MetricsConfig.from_env()` 形态 | `src/infrastructure/config/metrics.py` L12-55（frozen dataclass + from_env + bool 三态解析） | **参考照抄**——PhoenixConfig（enabled/endpoint/project_name/sampling 四字段 + `__post_init__` 101 守卫） |
| `MetricsPort` / `CacheMetricsPort` 端口形态 | `src/application/ports/metrics_port.py` + `cache_metrics_port.py`（runtime_checkable Protocol + 方法 docstring + Raises 契约） | **参考照抄**——AgentTracingPort（SpanHandle 协议方法签名直接对齐 OTel Span 方法名——set_attribute/record_exception/set_status，duck-type 零包装） |
| `SemanticCacheMiddleware` 装饰器/包装埋点范式 | `src/application/services/semantic_cache_middleware.py`（应用层包装器 + 端口注入 + 组合根装配） | **范式参照**——@trace 是其在方法装饰器维度的延伸（DC-4 论证静态装饰走 OTel 全局 API） |
| 端口契约测试 11 维度 + `_DummyResolver` | `tests/contracts/test_port_contract_isolation_switch_log_repository.py`（114 行——PORT_NAME/EXPECTED_TAGS/REQUIRED_METHODS 类常量 + 11 维度 + Dummy 分发） | **参考照抄**——test_port_contract_agent_tracing.py 同款结构 |
| 验收 R6 骨架 | `tests/acceptance/test_acceptance_isolation_switch_log.py`（5-6 最新形态：@scenario 多行字面量显式绑定 + context dict fixture + `_run_async` 同循环 + 步骤化门控 + 收尾清单场景 + 延迟 import + 禁 then-pass） | **参考照抄**——R6 主体基准；PG 模板（test_acceptance_postgresql_relational_layer.feature/.py）取 Gherkin 中文关键字与场景组织形态 |
| 集成委托计时模式 | `tests/integration/test_integration_isolation_switch_log.py`（`_PERF_CACHE` 单槽缓存 helper + `xdist_group` 同 worker 缓存 + 常量单源集成定义/验收 import） | **参考照抄**——`_PERF_CACHE` + xdist_group("phoenix-tracer-perf") + P95 常量单源 |
| AST 架构验证器形态 | `tests/unit/architecture/test_arch_isolation_switch_log.py`（REPO_ROOT + 目标文件常量 + `_scan_file_imports` AST helper + 验证器 A/B/C 参数化） | **参考照抄**——test_arch_phoenix_tracer.py（验证器维度不同：application 层第三方白名单 opentelemetry + 组合根外零实例化 + domain 零侵入） |
| `build_key` 等测试工具 | `src/infrastructure/storage/redis/key_builder.py`（如需） | 本 Story **无 Redis/PG 依赖**（进程内追踪）——预计零使用，列此防误引 |
| Fake LLM 手工装配先例 | 5-3 验收/集成（Fake llm_client 注入手工装配真实服务链——`AsyncMock(spec=LLMClientPort)` + side_effect 按 Schema 身份分派返回真实 Schema 实例） | **参考照抄**——六阶段真实链场景的 LLM 面替身（外部 API 不可验收强依赖——5-3 先例边界） |

**明确不存在、本 Story 需新建**（全仓 grep 验证：`PhoenixTracer|AgentTracingPort|SpanAttributeKeys|agent_tracing|PHOENIX_` 在 `src/` 与 `tests/` **零命中**；`@trace` 装饰器零定义；phoenix/openinference 不在 pyproject——防重复造轮子结论成立）：

1. `PhoenixConfig`（src/infrastructure/config/phoenix.py——frozen dataclass + from_env + 101 守卫）
2. `PhoenixTracer`（src/infrastructure/monitoring/phoenix_tracer.py——AgentTracingPort 实现 + initialize/shutdown/reset_for_testing）
3. `AgentTracingPort` + `SpanHandle` 协议 + `SpanAttributeKeys` 常量注册表（src/application/ports/agent_tracing.py）
4. `@trace` 装饰器（src/application/tracing.py——async 方法装饰器 + OTel 全局 API + NoOp 降级）
5. 工作链接入（修改：run_agent_workflow.py 根 span + 属性写入块；agent_workflow_service.py 六装饰器 + trace_id 填充——**纯附加零构造签名变化**）
6. 组合根 `# === Story 5.7 ===` 区段（agent_tracing 端口注册 + initialize 接线）
7. `.env.example` PHOENIX_* 三变量（可观测性区追加）
8. 测试六件：`tests/unit/infrastructure/monitoring/test_phoenix_tracer.py` / `tests/unit/application/test_tracing_decorator.py`（装饰器单测，含 SpanAttributeKeys 键常量断言）/ `tests/contracts/test_port_contract_agent_tracing.py` / `tests/integration/test_integration_phoenix_tracer.py`（span 树真实链 + P95 + 开销对比）/ `tests/unit/architecture/test_arch_phoenix_tracer.py` / `tests/acceptance/test_acceptance_phoenix_tracer.{feature,py}`

---

## ✅ Acceptance Criteria 验收标准

### AC-1: PhoenixTracer 实例化与配置（project_name 契约）

**Given** PhoenixConfig 环境契约（`PHOENIX_TRACING_ENABLED` 默认 false / `PHOENIX_OTLP_ENDPOINT` 默认 `http://localhost:4317`[未设时 fallback `OTEL_EXPORTER_OTLP_ENDPOINT`] / `PHOENIX_PROJECT_NAME` 默认 `"sisys-agent"`——epics 钦定值 / `PHOENIX_TRACES_SAMPLER_ARG` 默认 1.0）
**When** 构造 `PhoenixTracer(config=PhoenixConfig(project_name="sisys-agent"), tracer_provider=<注入 TracerProvider>)` 并调用 `initialize()`
**Then** Resource 携带 `service.name == "sisys-agent"`（Phoenix OTLP 接收端按 service.name 归项目——OD-1 映射）+ `telemetry.sdk...` 标准 Resource 属性；TracerProvider 配置 `TraceIdRatioBased(sampling_ratio)` + SpanProcessor（生产 BatchSpanProcessor + OTLPSpanExporter；**测试注入 SimpleSpanProcessor + InMemorySpanExporter——同步导出零外联**）；`initialize()` 幂等（二次调用返回 True 零重复装配）且 enabled=false 时**不装配不设全局**（返回 False——NoOp 天然降级）
**And** PhoenixConfig `__post_init__` 101 守卫：enabled 非 bool 拒；project_name 空/空白拒；endpoint 空/非 http(s) 前缀拒；sampling_ratio 非数值或 ∉(0,1] 拒（上下界含 1.0 全采样、不含 0——0 采样等价禁用应走 enabled=false）；`from_env()` 四变量解析（bool 三态 `in ("true","1","yes")` 对齐 MetricsConfig 惯例）；`create_span` 在未 initialize 时 `yield None`（零开销降级——event_metrics L227 同款语义，显式消费方 None 分支契约）

**验证标准/Validation Criteria:**
- [ ] project_name → Resource service.name 断言（注入 provider 后 `resource.attributes["service.name"] == "sisys-agent"`）
- [ ] initialize 幂等（两次调用零重复 processor——provider span_processors 计数断言）+ enabled=false 不装配（全局 provider 保持 None + 返回 False）
- [ ] PhoenixConfig 101 守卫五场景参数化（isinstance→code→context 三段式）
- [ ] from_env 四变量（含 OTEL_EXPORTER_OTLP_ENDPOINT fallback 链 + 默认值矩阵）
- [ ] create_span 未初始化 yield None 降级断言

### AC-2: @trace 装饰器自动 span（agent_execution 根 + 六阶段子树）

**Given** PhoenixTracer 已 initialize（测试注入 SimpleSpanProcessor + InMemorySpanExporter；工作流链 = 5-3 手工装配形态：Fake LLM[AsyncMock spec 端口按 Schema 身份分派] + 真实 AgentWorkflowService/LangGraphEngine/RunAgentWorkflowUseCase）
**When** 调用 `RunAgentWorkflowUseCase.execute(agent_id, task)` 执行六阶段工作流
**Then** **根 span `agent_execution`** 自动创建（@trace("agent_execution")——span 名 epics 钦定）+ **六阶段子 span** `agent.perceive`/`agent.plan`/`agent.execute`/`agent.verify`/`agent.reflect`/`agent.package`（span 名对齐 `executed_phases` 枚举——**末阶段钉死 "package" 非 package_evidence**，5-3 谓词键对照表对齐）依执行序创建；**parent 链**：六子 span 的 parent 均为 agent_execution 根（同进程 async 上下文传播——OTel contextvars 机制）；**重试轮**：verify→reflect→plan 循环再入时 `agent.plan`/`agent.reflect` 多实例合法（span 序列 == executed_phases 序列——一致性断言）
**And** **异常路径**：被装饰方法抛 DomainError（如 444 LLM 失败）时 span 记录 `Status ERROR` + `record_exception`（异常事件），随后**原样上抛**（追踪零吞异常——装饰器不改异常语义，5-3 既有断言零回归）；**未启用降级**：enabled=false（NoOp tracer）时零 span 产生 + 主链行为与 5-3 完全一致（装饰器 overhead 仅一层函数调用）；装饰器 `functools.wraps` 保签名（`__name__`/`__doc__` 保留——mypy ParamSpec 泛型签名不窄化）

**验证标准/Validation Criteria:**
- [ ] InMemory exporter 取 span 列表：根 span 名 == "agent_execution" + 六子 span 名集合断言 + 执行序断言（perceive→plan→execute→verify[→reflect→plan...→]package）
- [ ] parent 链断言（每子 span.parent.span_id == 根 span.span_id；根 parent 为空）
- [ ] 重试轮 span 序列 == executed_phases 终态序列（同源一致）
- [ ] 异常路径：注入 Fake LLM 抛 LLMError → span status ERROR + events 含 exception + `pytest.raises` 原异常透传
- [ ] NoOp 降级：enabled=false 链跑通 + exporter 空 + 主链返回值与无装饰一致
- [ ] functools.wraps 签名保留断言（六阶段方法 __name__ 不变——5-3 存量单测兼容前提）

### AC-3: span 属性契约与 trace_id 贯通

**Given** agent_execution span 存活期（用例 execute 方法体内）
**When** 写入业务属性（经 `SpanAttributeKeys` 常量 + `trace.get_current_span().set_attribute`）
**Then** **MVP 属性集**（值取自 run 链现成数据——不消费事件、不加实体字段）：`agent.id`（str(agent_id)）/ `agent.role`（AgentRole.value）/ `agent.name` / `agent.startup_context_tokens`（AgentProfileLoadResult 现成——agent_events.py L75 锚点兑现）/ `agent.active_skill_count`（同上）/ `workflow.status`（AgentWorkflowResult.workflow_status——"completed"/"failed"）/ `workflow.retry_count` / `workflow.executed_phases`（tuple[str,...] 序列属性）/ `llm.confidence`（verify 产物）/ `evidence.input_hash`（sha256 hex——chain_of_thought.py L4 消费真源兑现）；**eval/drift 通道**（OD-2 口径）：`SpanAttributeKeys.EVAL_HALLUCINATION_SCORE`("eval.hallucination_score") / `EVAL_CONTEXT_RELEVANCE`("eval.context_relevance") / `EVAL_CONFIDENCE_ACCURACY`("eval.confidence_accuracy") / `DRIFT_DETECTED`("drift.detected") 键常量注册 + 写入通道可用（测试写入 → InMemory exporter span.attributes 含该键与值——AC-3.2 场景验证通道能力，生产填值归 5.8/5.9）
**And** **trace_id 贯通**（5-3 预留位核销）：`agent_workflow_service.py` execute 阶段构造 `ExecutionContext` 时 `trace_id = format(get_current_span().get_span_context().trace_id, "032x")`（32 位小写 hex——OTel trace_id 标准形态）——工具执行层（tool_version_service route_key 等）与 span 同 trace；NoOp 时 trace_id 为全零 hex（`000...0`——get_current_span 返回 INVALID_SPAN 的 trace_id==0 格式化形态，与 5-3 空串语义差异登记：非空常量串，零污染版本桶评估归 5.8 立项时复核）——**⚠️ 防呆：全零串仍会散列进同一版本桶（与空串等价语义），5-3 注释「MVP 空串可接受」的口径不变，仅真源从空串变为 span 派生**

**验证标准/Validation Criteria:**
- [ ] 真实链 span.attributes 逐键断言（MVP 十项属性集——值与 AgentWorkflowResult/AgentProfileLoadResult 逐项相等）
- [ ] eval/drift 通道：SpanAttributeKeys 四常量字符串值断言（"eval.hallucination_score" 等逐字）+ 测试写入→span.attributes 断言（键在/值等）
- [ ] trace_id 贯通：根 span trace_id hex == ExecutionContext.trace_id（工具执行链断言点——手工装配链内捕获 ExecutionContext 或经 tool_trace 侧证）
- [ ] NoOp 链 trace_id == 全零 32 位 hex（降级语义钉死）
- [ ] SpanAttributeKeys 常量与 epics L1726-1728 键名逐字一致断言（防拼写漂移的元断言）

### AC-4: 端口接线、架构合规与回归零破坏

**Given** 端口、实现、装饰器、接入全部交付
**When** 验证接线与合规
**Then** 新端口 `agent_tracing`（**SINGLETON——Epic 5 全家政策**[isolation_repository L2874/isolation_management L2887/isolation_guard L2917/isolation_switch_log_repository L2945 五连先例；PhoenixTracer 持 provider 单例语义天然 SINGLETON，无 SCOPED 捕获面]）经组合根 `# === Story 5.7 ===` 区段注册且 resolve 可达（PortSpec：v1.0.0 / `AgentTracingPort` / lambda 注入 `PhoenixConfig.from_env()` / module=src.infrastructure.monitoring.phoenix_tracer / owner=platform / tags=("agent","observability","tracing")）；bootstrap 内**显式调用 initialize 接线**（resolve → isinstance → `initialize()`——enabled=false 时 NoOp 零开销，全局唯一 TracerProvider setter 声明[DC-6]）；`.env.example` 可观测性区追加 PHOENIX_* 三变量
**And** 架构合规：application 层第三方 import 白名单（application/tracing.py + ports/agent_tracing.py + run_agent_workflow.py + agent_workflow_service.py 允许 `opentelemetry`——**禁止 pydantic/fastapi 等非白名单第三方入 application 既有防线不变**）；`agent_tracing.py` 端口文件零第三方依赖（纯 Protocol + 常量——同层 metrics_port 形态）；组合根外零实例化（PhoenixTracer 实例化点仅 composition_root.py + tests/）；**domain 层零侵入**（本 Story domain 零新文件零改动——grep 断言 domain/ 无本 Story 触碰）；**5-3 回归零破坏**：装饰器接入是纯附加（零构造签名变化→**零构造点苦役**——与 5-6 对比的关键简化），5-3 全家存量测试（test_agent_workflow_service 单测/契约×2/集成/验收 + run_agent_workflow 相关）全量回归绿

**验证标准/Validation Criteria:**
- [ ] 组合根注册 + resolve + isinstance + lifetime==SINGLETON 断言（5-6 AC-6.1 同款四件）
- [ ] initialize 接线断言（resolve 后 initialize() 返回 bool + enabled 配置传导——注入测试 env 后全局 tracer provider 可用性）
- [ ] AST 验证器 A：application 新增/触碰文件 import 白名单扫描（opentelemetry 允许；domain 目录零触碰断言）
- [ ] AST 验证器 B：组合根外零实例化（src/ 扫描 PhoenixTracer( 构造点）
- [ ] .env.example 三变量存在性断言（PHOENIX_TRACING_ENABLED/PHOENIX_OTLP_ENDPOINT/PHOENIX_PROJECT_NAME）
- [ ] 5-3 存量全家回归绿清单（unit/contracts×2/integration/acceptance 五文件族逐一列出登记）

### AC-5: 性能（span 记录延迟 P95<5ms + 追踪开销<1%）

**Given** 测试注入 SimpleSpanProcessor + InMemorySpanExporter（同步导出——测量纯进程内开销，生产 BatchSpanProcessor 异步导出不计入且更优）
**When** 测量 span 记录延迟与追踪开销
**Then** **span 记录延迟 P95<5ms**（epics L1746——计时锚 = `create_span` 全周期：进入 contextmanager → set_attribute × 10（MVP 属性集满量）→ 退出 end；warmup 1 + 20 采样 `statistics.quantiles(latencies, n=20)[18] < SPAN_RECORD_P95_LIMIT_SECONDS`——常量 0.005 单源定义于集成模块，验收侧 import）；**追踪开销<1%**（epics L1747——测量口径钉死：同一手工装配六阶段 Fake LLM 链双跑对比，`overhead = (t_traced - t_untraced) / t_untraced < 0.01`——t 为全链 wall time；**t_untraced 锚**：PhoenixTracer 未 initialize（NoOp tracer——装饰器仍在位但 span 空转，测得即「装饰器+NoOp」纯开销；traced 锚：initialize + InMemory processor）
**And** 计时委托集成模块（`_PERF_CACHE` 单槽缓存 + `xdist_group("phoenix-tracer-perf")` 同 worker 串行——5-6 委托模式照抄，与 agent-isolation-perf/agent-triple-isolation-perf/isolation-switch-log-perf 三组名互异；基准场景级 `pytest.mark.benchmark` 标记）；**开销裕量注记**：Fake LLM 链单轮全链 ~百 ms 级（含 6 次 structured 模拟 + 图调度），OTel 进程内 span 开销 ~μs 级/个（12+ span/轮），预期裕量 >100×——若实测不达标，优先排查 BatchSpanProcessor 误入测试链（同步 Simple 应为默认注入）

**验证标准/Validation Criteria:**
- [ ] P95<5ms：常量单源（集成定义/验收 import）+ 委托缓存命中（验收 AC-5.1 不自跑采样）
- [ ] 开销<1%：双跑对比公式断言（同 worker 同链；t_untraced 基准值下限守卫——防链被意外加速导致分母失真，t_untraced ≥ 已知下限常量）
- [ ] benchmark 场景级标记 + xdist_group 同组（四组名互异确认）
- [ ] 采样禁双跑（委托缓存断言——5-6 同款）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] **不新建领域事件、不修改既有事件**——追踪是进程内同步可观测面，不经事件总线；`event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` 零改动。`AgentDecided`/`AgentInstantiated`/`AgentProfileLoaded` 三事件仅作为 span 属性语义参照（startup_context_tokens/active_skill_count 锚点经 run 链 AgentProfileLoadResult 现成兑现——不消费事件本体，OD-4 消费基建归 5.11）。

#### 数据模型 (Data Models)

- [ ] `PhoenixConfig`（`src/infrastructure/config/phoenix.py`，frozen dataclass——MetricsConfig 先例 L12-55）：
  - 字段：`enabled: bool = False`（PHOENIX_TRACING_ENABLED——保守默认对齐 EVENT_BUS_OTEL_TRACE_ENABLED=false 形态）/ `endpoint: str = "http://localhost:4317"`（PHOENIX_OTLP_ENDPOINT——OTLP gRPC 惯例端口；未设时 fallback OTEL_EXPORTER_OTLP_ENDPOINT）/ `project_name: str = "sisys-agent"`（PHOENIX_PROJECT_NAME——epics 钦定）/ `sampling_ratio: float = 1.0`（PHOENIX_TRACES_SAMPLER_ARG——OTEL_TRACES_SAMPLER_ARG 惯例名对齐）
  - `__post_init__` 守卫（抛 `ConfigurationError` 101，context 携带字段名与实际值——{字段名: 值} 形态对齐 242 惯例）：enabled 非 bool 拒（isinstance 先行——bool 子类 int 防呆）；project_name 非 str 或空白拒；endpoint 非 str 或不以 http:///https:// 前缀拒；sampling_ratio 非 int/float（bool 拒）或 ∉ (0, 1.0] 拒
  - `from_env()` classmethod：四变量解析（bool 三态 `in ("true", "1", "yes")`——MetricsConfig 惯例）+ endpoint fallback 链（PHOENIX_OTLP_ENDPOINT > OTEL_EXPORTER_OTLP_ENDPOINT > 默认值）
- [ ] **本 Story domain 层零新数据模型**（span 属性键/句柄契约归应用层端口文件——见下）

#### 统一端口定义注册与管理 (Port Contract)

- [ ] `AgentTracingPort`（`src/application/ports/agent_tracing.py`，`@runtime_checkable Protocol`——**R2 具体应用端口**：追踪是 Agent 评估可观测族[5.7-5.9]的应用契约，同层先例 metrics_port/cache_metrics_port；**不设 domain 端口**——追踪非领域概念，domain 零依赖原则下 domain/ports 只承载业务基础能力）：
  - `def create_span(self, name: str, attributes: dict[str, str | bool | int | float | tuple[str, ...]] | None = None) -> AbstractContextManager[SpanHandle | None]`——span 生命周期上下文（进入开 span + attributes 批量写入；退出 end）。Returns 契约：**已 initialize 时 yield SpanHandle（OTel Span 原生对象 duck-type）；未 initialize 时 yield None**（零开销降级——显式消费方判 None，event_metrics L227 同款语义）。Raises 契约：**零抛出**（追踪失败降级 logger.warning 绝不上抛——DC-7 可观测性附加哲学）
  - `def initialize(self) -> bool`——配置全局 TracerProvider（幂等；enabled=false 返回 False 不装配）。Returns：是否实际启用
  - `def shutdown(self) -> None`——刷盘并释放（BatchSpanProcessor.force_flush + provider shutdown；atexit 注册——otel_config L303 先例）
- [ ] `SpanHandle` 协议（同文件，`@runtime_checkable Protocol`——方法签名**逐名对齐 OTel Span**（duck-type 零包装层，OTel Span 天然满足））：
  - `def set_attribute(self, key: str, value: str | bool | int | float | tuple[str, ...]) -> None`
  - `def record_exception(self, exception: BaseException) -> None`
  - `def set_status(self, status_ok: bool, description: str = "") -> None`（封装 OTel Status/StatusCode.OK/ERROR 两态）
- [ ] `SpanAttributeKeys` 常量注册表（同文件，`class SpanAttributeKeys: str` 常量类——键字符串单一真源，5.8/5.9 引用防拼写漂移）：
  ```
  AGENT_ID="agent.id" / AGENT_NAME="agent.name" / AGENT_ROLE="agent.role"
  AGENT_STARTUP_CONTEXT_TOKENS="agent.startup_context_tokens" / AGENT_ACTIVE_SKILL_COUNT="agent.active_skill_count"
  WORKFLOW_STATUS="workflow.status" / WORKFLOW_RETRY_COUNT="workflow.retry_count" / WORKFLOW_EXECUTED_PHASES="workflow.executed_phases"
  LLM_CONFIDENCE="llm.confidence" / EVIDENCE_INPUT_HASH="evidence.input_hash"
  EVAL_HALLUCINATION_SCORE="eval.hallucination_score" / EVAL_CONTEXT_RELEVANCE="eval.context_relevance" / EVAL_CONFIDENCE_ACCURACY="eval.confidence_accuracy"
  DRIFT_DETECTED="drift.detected"
  ```
  （eval.*/drift.* 四键——epics L1726-1728 键名逐字源；`SpanNames` 常量：`AGENT_EXECUTION="agent_execution"`[epics 钦定] / `PHASE_PREFIX="agent."`——span 名与 executed_phases 枚举一致性由 AC-2 元断言锁定）
- [ ] `@trace` 装饰器（`src/application/tracing.py`——**独立模块非端口文件**：装饰器是静态语法构件非注入契约）：
  - `def trace(span_name: str, attributes: dict[...] | None = None)` 返回 async 方法装饰器：`functools.wraps` + `ParamSpec/TypeVar` 泛型签名保真；wrapper 内 `tracer = opentelemetry.trace.get_tracer("sisys.agent")`（**OTel 全局 API——未 initialize 时返回 proxy→NoOp tracer，span 操作空转零开销**）→ `tracer.start_as_current_span(span_name)` 内 `await func(...)`；异常路径 `span.record_exception(exc)` + `span.set_status(ERROR)` 后 **re-raise 原异常**（零吞异常）
  - 同步函数支持：**不提供**（接入面全 async——YAGNI；docstring 注明）
- [ ] 组合根注册元数据：`agent_tracing`：v1.0.0 / `AgentTracingPort` / `PhoenixTracer`（lambda: `PhoenixTracer(config=PhoenixConfig.from_env())`） / module=src.infrastructure.monitoring.phoenix_tracer / **SINGLETON** / owner=platform / tags=("agent", "observability", "tracing")
- [ ] **既有组件消费方变更（契约变更登记 ×1）**：`RunAgentWorkflowUseCase.execute` 加 `@trace(SpanNames.AGENT_EXECUTION)` + 方法体内属性写入块（~15 行）；`AgentWorkflowService` 六阶段方法各加 `@trace(f"{SpanNames.PHASE_PREFIX}perceive")` 等六行 + execute 阶段 `ExecutionContext.trace_id` 填充一行——**纯附加装饰，零构造签名变化**（与 5-6 五/六依赖扩展对比：本 Story 零构造点回归面——5-6 苦役不复发的前提锚定）
- [ ] 端口契约测试一份（`tests/contracts/test_port_contract_agent_tracing.py`，11 维度 + `_DummyResolver`——PhoenixTracer 构造仅需 config，Dummy 分发 `phoenix_config → None` 或直接 from_env）
- [ ] **禁止**在服务文件本地定义 Protocol/Port 抽象（SpanHandle 定义在端口文件，服务只 import）；**禁止**新建语义重复端口（追踪端口唯一；禁新建 tracer/telemetry/observability 同义端口；MetricsPort 已有面不碰）

#### 端口契约清单执行约束（强制）
- [ ] 本 Story 端口清单唯一真源 = 本 Task 0 定义（`agent_tracing` 一新端口 + 一项既有组件消费方变更：use case/service 装饰器接入——契约变更登记）
- [ ] 禁止新增未登记端口；禁止未同步 registry/resolver/contract test
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> 原则/适用范围/禁止条款同模板基线。**本 Story 零新领域异常（DC-8）**——失败面由既有异常 + 降级哲学覆盖：

- [ ] 复用清单（零新增）：`ConfigurationError`(101——PhoenixConfig `__post_init__` 五场景守卫)；**追踪运行面零抛出**（create_span/装饰器内任何 OTel 异常 catch → logger.warning 降级——可观测性组件故障不得影响主链，5-6 audit 降级 DC-6 同哲学的更强形态：追踪连「拒绝主链」语义都没有，纯旁路）
- [ ] 零新异常论证：配置校验=101 语义精确；span 操作无业务失败面（OTel API 契约不抛业务异常）；无新业务规则失败面。`_code_ranges.py` / `exceptions/__init__.py` / `EXCEPTION_HTTP_MAP` / §3.3.2 文档表**零改动**（异常契约四件套豁免——无新增即无登记）
- [ ] BDD 异常路径：101 配置守卫路径（AC-1.2 参数化）+ 追踪零吞异常路径（AC-2.3 原异常透传）纳入验收 Edge Cases

#### API 契约 (API Contract)

- [ ] 本 Story 无 REST API / 无 CLI 命令（追踪是嵌入式基础设施，无独立交付面）。`docs/api/openapi.yaml` 零改动
- [ ] 环境契约：`.env.example` 可观测性区（L224-236 后）追加三变量 + 注释行（PHOENIX_TRACING_ENABLED=false / PHOENIX_OTLP_ENDPOINT= / PHOENIX_PROJECT_NAME=sisys-agent——sampling 变量随 OTEL_TRACES_SAMPLER_ARG 复用说明，不重复设变量）

#### 六边形架构约束（必须遵守）

> 四层定义/零依赖原则/依赖方向矩阵同模板基线。本 Story 特别注意：

- [ ] `agent_tracing.py`（端口 + SpanHandle + 常量）在 application 层——**纯标准库 + 零第三方**（Protocol 形态同 metrics_port——OTel 类型不出现在端口签名，SpanHandle 方法签名是手写抽象）；
- [ ] `tracing.py`（装饰器）在 application 层——**允许 `opentelemetry` 第三方 import**（`.importlinter` 只限层间方向不限第三方；opentelemetry-api 是横切标准 API 包，与 logging 同级定位——DC-4 论证）；**禁止 import infrastructure**
- [ ] `PhoenixTracer`/`PhoenixConfig` 在 infrastructure 层（monitoring/ + config/ 归口）——实现 application 端口；OTel SDK import（sdk/exporter）仅此层（application 只碰 opentelemetry-api 的全局 tracer/get_current_span 面——API 包与 SDK 包的分界即层分界）
- [ ] 接入面（run_agent_workflow.py/agent_workflow_service.py 已在 application）装饰器 + get_current_span import 合法；**domain 层零触碰**（本 Story 无 domain 改动——AST 验证器断言）
- [ ] 接口层零改动（无 CLI/API 面）

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_phoenix_tracer.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_phoenix_tracer.py`
- [ ] 场景组织：AC 注释横幅分组 + 全场景逐一 `@scenario` 显式绑定（多行字面量路径——R6 形态，禁 `scenarios()` 批量绑定与 then-pass 占位）；场景名 `AC-x.y - 中文描述`（feature 与 .py 逐字一致）；**禁 Background 背景块门控**（步骤化门控——本 Story 外部服务门控 = 零外部服务，仅 Fake LLM 手工装配链自包含；Gherkin Given 钉「Phoenix 追踪已启用（测试内存导出器）」类前置步骤）
- [ ] 15 场景规划（终态 = Task 0 编写 14 + Task 6 追加收尾 1；三属性分档表 Task 0.6 定稿落 docstring）：
  - AC-1 ×3（组件级，零服务依赖）：PhoenixTracer 实例化与 project_name→service.name 映射 / initialize 幂等与 enabled=false 不装配 / PhoenixConfig 101 守卫与 from_env 四变量（参数化）
  - AC-2 ×3（链级，Fake LLM 手工装配）：agent_execution 根 span + 六阶段子 span 树自动创建（parent 链 + 执行序 + 重试轮序列一致性）/ 异常路径 span ERROR + 原异常透传 / NoOp 降级零 span 且主链等价
  - AC-3 ×3（链级 + 组件级）：MVP 十项业务属性真实链逐键断言 / eval-drift 四键常量与写入通道能力（OD-2 口径）/ trace_id 贯通（span hex == ExecutionContext.trace_id + NoOp 全零形态）
  - AC-4 ×3（静态 + 接线）：组合根接线（resolve 四件 + initialize 传导）/ 架构静态扫描（AST 三验证器 + domain 零触碰 + .env.example 三变量）/ 5-3 回归资产在位（五文件族存在 + 装饰器纯附加声明——全量回归绿在 Task 6 收尾跑）
  - AC-5 ×2（委托集成计时）：span 记录 P95<5ms / 追踪开销<1%（双跑对比公式）
  - 收尾 ×1：完成清单逐项确认（src + tests 四目录——5-6 收尾同款）
- [ ] BDD 步骤约束：全部同步 `def` + `_run_async(context["_loop"], ...)`（禁 `@pytest.mark.asyncio`——context 数据丢失）；参数化步骤显式 `parsers.parse`；异常断言三段式（raises 捕获存 `context["caught"]` → then 断言 code + context——101 场景）；**span 断言锚**：场景级独立 TracerProvider + SimpleSpanProcessor + InMemorySpanExporter（**不经全局 set——避免跨场景全局 provider 单次设置冲突[OTel GitHub #8639 教训]；每场景新 provider 实例 + PhoenixTracer(tracer_provider=注入) 构造注入通道**）
- [ ] 显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.xdist_group("phoenix-tracer-perf")]`（文件名不含服务关键词且零外部服务——无 redis/database marker；组名与集成计时场景逐字同组）+ 延迟 import 纪律
- [ ] teardown：span 面零资源（provider.shutdown() + exporter 清空；无 Redis/PG 清理面——本 Story 自包含优势）；计时场景委托缓存防双跑

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——ModuleNotFoundError/断言红为合法红）
- [ ] 规范文档通过人工评审或自动化校验
- [ ] **链路接线断言清单**已定义（Epic 4 回顾行动项 7.1-1）：①`agent_tracing` 组合根 register_port 装配验证（resolve 可达 + isinstance + PortSpec 元数据 + SINGLETON）②initialize 接线确认（bootstrap 显式调用 + enabled 配置传导 + 全局唯一 setter 声明）③装饰器接线静态锚（六阶段方法 + execute 方法装饰器在位——AST/inspect 扫描）④trace_id 贯通锚（execute 阶段 trace_id 派生代码在位——5-3 预留位核销证据）⑤span→exporter 全链（注入 provider 的 InMemory exporter 能取到 agent_execution span——AC-2.1 场景承载）

---

### TDD 循环约束（适用于每个 Task）

> 每 Task 依次执行 🔴红→🟢绿→🟡变异→🔄重构；变异实证 = 对新行为契约的断言改坏→红→还原→绿（Epic 4 行动项 7.1-2 强制）。禁止行为四条同模板基线。
>
> **套件型 Task 豁免条款**（Task 4 性能场景 / Task 5 架构验证 / Task 6 收尾场景）：验证型测试层首跑即绿——红由 Task 0 验收红阶段前置承担；断言活性由 🟡 变异实证强制（如：span 名改错→树断言红；装饰器 re-raise 删除→透传断言红；P95 常量突变→阈值断言红）。

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| TDD 单元测试 | PhoenixConfig | from_env 四变量/101 守卫五场景/endpoint fallback 链 | `tests/unit/infrastructure/config/test_phoenix_config.py`（如 config 测试有目录惯例则归位——实施时按 `tests/unit/infrastructure/config/` 现状落位） | Task 1 |
| TDD 单元测试 | PhoenixTracer | 实例化/Resource service.name/initialize 幂等/enabled=false 不装配/create_span 降级/异常降级（OTel 异常注入→warning 不上抛） | `tests/unit/infrastructure/monitoring/test_phoenix_tracer.py` | Task 1 |
| TDD 单元测试 | @trace 装饰器 | span 自动创建/异常 record+ERROR+re-raise/NoOp 零 span/functools.wraps 签名/attributes 参数化 | `tests/unit/application/test_tracing_decorator.py` | Task 2 |
| TDD 契约测试 | agent_tracing | 11 维度 + _DummyResolver | `tests/contracts/test_port_contract_agent_tracing.py` | Task 1 |
| TDD 单元测试 | 工作链接入 | use case 属性写入块（get_current_span 面——注入 provider 断言属性集）/trace_id 派生/六阶段装饰器在位 inspect 锚 | `tests/unit/application/use_cases/test_run_agent_workflow.py`（追加——5-3 存量文件）+ `test_agent_workflow_service.py`（追加装饰器锚） | Task 3 |
| 集成测试 | 全链 span 树 | 六阶段真实链（Fake LLM 手工装配）span 树/parent 链/重试轮序列/异常路径/NoOp 对比/P95/开销<1% | `tests/integration/test_integration_phoenix_tracer.py` | Task 4 |
| SDD 架构验证 | 六边形约束 | application 第三方白名单/domain 零触碰/组合根外零实例化/装饰器静态锚 | `tests/unit/architecture/test_arch_phoenix_tracer.py` | Task 5 |
| TDD 验收测试 | Gherkin + BDD | 14 场景 Task 0 编写（收尾 Task 6 追加成 15 终态）；各 Task 转绿——AC-1 随 Task 1、AC-2/AC-3 随 Task 2/3/4、AC-4 随 Task 1/3/5、AC-5 随 Task 4 | `test_acceptance_phoenix_tracer.feature/.py` | Task 0-6 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] 整体 ≥80%（P0 阻断）；**应用层 ≥85%**（装饰器/接入/常量主战场——epics L1750）；infrastructure ≥75%（PhoenixTracer/PhoenixConfig）；domain ≥90% 维持（本 Story 零 domain 改动——不降不升）；四档与 `scripts/check_coverage_gates.py` 一致
- [ ] 关键分支可执行口径：装饰器三分支（正常/异常/NoOp）+ create_span 两态（initialized/未初始化）+ 101 守卫五场景各配独立命名测试用例（用例名即分支清单）

#### 代码质量门禁

- [ ] `ruff check src/ tests/` + `mypy src/`（OTel 1.21 自带类型——无 stubs 新增需求[OD-1 附带收益]）+ `pre-commit run` 全过
- [ ] 三条红线自查零输出（`raise ValueError`/手动 `HTTPException`/继承内置 Exception——注意 PhoenixConfig 守卫必须 101 非 ValueError）+ 零抑制注释
- [ ] 提交信息零 AI 署名

#### 测试隔离约束

> 基线同模板。本 Story 特别注意：

- [ ] **OTel 全局状态隔离（本 Story 特有最大坑面）**：OTel 全局 TracerProvider **每进程仅可设置一次**（二次 set 被静默忽略——Arize-ai/phoenix#8639 实证）；测试一律**不经全局 set**——每测试/场景构造独立 `TracerProvider()` + `SimpleSpanProcessor(InMemorySpanExporter())` 经 `PhoenixTracer(tracer_provider=注入)` 构造通道注入；装饰器 span 面测试的例外（装饰器内部走全局 API）：模块级 fixture 一次性 `trace.set_tracer_provider(测试 provider)` + teardown **`reset_for_testing()` 复位**（`trace._TRACER_PROVIDER = None`——otel_config L315-339 先例）；**严禁跨测试文件共享已 set 的全局 provider**（xdist 每 worker 独进程天然隔离，同进程多模块串行靠 reset 复位）
- [ ] **本 Story 零外部服务依赖**：无 Redis/PG/Phoenix server/LLM API 硬依赖（span 面进程内自包含 + Fake LLM 手工装配——5-3 验收先例边界）；验收/集成**禁 OTLP 外联**（生产 OTLPSpanExporter 仅经组合根 lambda 形态断言覆盖——测试全用 InMemorySpanExporter 注入）
- [ ] **pytest-xdist 计时组**：`xdist_group("phoenix-tracer-perf")` 与三组既有 perf 组名互异；`_PERF_CACHE` 委托缓存 + benchmark 场景级标记；P95 双常量单源（集成定义/验收 import）
- [ ] **Fake LLM 手工装配边界**（5-3 先例口径）：`AsyncMock(spec=LLMClientPort)` + side_effect 按 response_schema 身份分派返回**真实 Schema 实例**（端口契约返回实例非 dict）；验收禁 mock 红线的豁免口径 = 外部 LLM API 不可验收强依赖（5-3 验收同款——豁免面仅 llm_client 一项，六阶段服务/图/用例全真实）
- [ ] BDD 步骤禁 `@pytest.mark.asyncio`；步骤函数同步 def + `_run_async` 调度；模块级 event_loop fixture（≥10 验收文件惯例）
- [ ] **5-3 存量回归**：装饰器纯附加改动后 5-3 全家（unit/contracts×2/integration/acceptance 五文件族）全量回归绿——回归清单 Task 3 登记（与 5-6 十四构造点苦役对比：本 Story 零构造点，回归面仅为「行为不变」验证）

**验证要求：** `pytest tests/` 通过（仓库默认 `-n auto --dist loadgroup`）；连续 5 次无随机失败；`ruff check` + `mypy` 通过；5-3 全家回归绿。

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | PhoenixConfig 101 守卫 + from_env | Task 1 | `__post_init__` + from_env | test_phoenix_config + 验收 AC-1.3 |
| AC-1 | PhoenixTracer 实例化 + project_name→service.name | Task 1 | Resource 装配 | test_phoenix_tracer + 验收 AC-1.1 |
| AC-1 | initialize 幂等 + enabled=false 不装配 | Task 1 | initialize 状态机 | test_phoenix_tracer + 验收 AC-1.2 |
| AC-1 | create_span 未初始化 yield None | Task 1 | 降级通道 | test_phoenix_tracer |
| AC-2 | agent_execution 根 span + 六阶段子树 | Task 2/3 | @trace 装饰器 + 接入 | test_tracing_decorator + 集成 + 验收 AC-2.1 |
| AC-2 | 异常路径 ERROR + re-raise | Task 2 | wrapper 异常分支 | test_tracing_decorator + 验收 AC-2.2 |
| AC-2 | NoOp 降级零 span 主链等价 | Task 2/3 | 全局 API NoOp 语义 | 同上 + 验收 AC-2.3 |
| AC-3 | MVP 十项属性真实链写入 | Task 3 | use case 属性写入块 | test_run_agent_workflow（追加）+ 验收 AC-3.1 |
| AC-3 | eval/drift 键常量 + 通道能力 | Task 1/2 | SpanAttributeKeys + create_span | test_tracing_decorator + 验收 AC-3.2 |
| AC-3 | trace_id 贯通（5-3 预留位核销） | Task 3 | execute 阶段派生 | test_agent_workflow_service（追加）+ 验收 AC-3.3 |
| AC-4 | 组合根接线 + initialize 传导 | Task 1 | 注册 + bootstrap 调用 | 契约测试 + 验收 AC-4.1 |
| AC-4 | 架构静态扫描 + domain 零触碰 | Task 5 | 验证器 A/B/C | test_arch_* + 验收 AC-4.2 |
| AC-4 | 5-3 回归零破坏 | Task 3/6 | 纯附加声明 + 全量回归 | 五文件族回归 + 验收 AC-4.3 |
| AC-5 | span 记录 P95<5ms | Task 4 | 委托计时 helper | 集成 + 验收 AC-5.1 |
| AC-5 | 追踪开销<1% | Task 4 | 双跑对比公式 | 集成 + 验收 AC-5.2 |
| 全 AC | 收尾清单 | Task 6 | 完成清单场景 | 验收收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则同模板。每 Subtask 组内按领域粒度拆分红绿循环。

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部

- [ ] Subtask 0.1: 定义数据模型规范——PhoenixConfig（frozen 四字段 + 101 守卫五场景 + from_env fallback 链；本文件「数据模型」节为唯一真源）
- [ ] Subtask 0.2: 定义端口契约——AgentTracingPort 三方法 + SpanHandle 三方法 + SpanAttributeKeys/SpanNames 常量注册表 + 组合根注册元数据 + 装饰器契约（契约变更登记 ×1：use case/service 装饰器接入）
- [ ] Subtask 0.3: 定义异常契约——零新异常复用清单（101 + 追踪运行面零抛降级）+ 零新增论证
- [ ] Subtask 0.4: 定义 OTel 全局状态隔离策略——独立 provider 注入通道 + reset_for_testing 复位纪律（测试隔离约束节 SSOT）
- [ ] Subtask 0.5: 定义性能测量口径——P95 计时锚（create_span 全周期 ×10 属性）+ 开销公式（双跑对比 + t_untraced 基准下限守卫）+ 常量单源
- [ ] Subtask 0.6: 编写 Gherkin `test_acceptance_phoenix_tracer.feature`（14 场景）+ BDD 步骤实现骨架 `.py`（@scenario 全显式绑定 + context dict fixture + 独立 provider 注入 + Fake LLM 手工装配链 fixture）+ **14 场景三属性分档表**定稿（docstring）
- [ ] Subtask 0.7: 运行验收测试确认失败（🔴 红阶段——ModuleNotFoundError/断言红为合法红）+ **deferred-work.md 登记**（OD-1 承接方 5.8 链接 / OD-2 归宿 5.8·5.9 / OD-4 承接方 5.11 + R1-DF2 锚位顺延注记 + AgentDecided 订阅决定知悉——gap 四要素齐备：描述/触发条件/归宿/承接方链接）
- [ ] Subtask 0.8: 移交留项处置落盘（前置依赖表三项逐一登记处置结果）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义；验收测试红阶段确认；链路接线断言清单 L1-L5 定义

---

### Task 1: PhoenixConfig + PhoenixTracer + 端口 + 组合根注册

**关联 AC:** AC-1（全部）、AC-4.1

#### TDD 循环 A：PhoenixConfig

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_phoenix_config.py`（from_env 四变量矩阵 + endpoint fallback 链 + 101 五场景参数化——三段式断言） |
| 🟢 绿 | 实现 `src/infrastructure/config/phoenix.py`（frozen + `__post_init__` + from_env） |
| 🟡 变异 | sampling 上界 1.0 改 2.0→越界用例红；endpoint 前缀守卫删除→非 http 用例红；还原→绿 |
| 🔄 重构 | Google 风格全中文 docstring + ruff+mypy |

#### TDD 循环 B：端口 + PhoenixTracer

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_phoenix_tracer.py`（实例化注入 provider → Resource service.name 断言 / initialize 幂等 processor 计数 / enabled=false 返回 False 全局保持 None / create_span initialized 态 yield handle + attributes 批量写入 / 未初始化 yield None / OTel 异常注入[坏 exporter processor]→warning 零上抛）+ `tests/unit/application/ports/`（如惯例存在）端口形态测试（SpanHandle duck-type OTel Span 实例 isinstance 断言） |
| 🟢 绿 | 实现 `src/application/ports/agent_tracing.py`（Port + SpanHandle + 常量注册表）+ `src/infrastructure/monitoring/phoenix_tracer.py`（initialize/shutdown/reset_for_testing/create_span——otel_config 生命周期 + event_metrics 降级双模板合成） |
| 🟡 变异 | service.name 装配改硬编码错值→Resource 断言红；initialize 幂等守卫删除→二次 processor 翻倍红；create_span 未初始化分支删除→None 断言红；还原→绿 |
| 🔄 重构 | docstring（Raises 零抛契约 + None 降级契约显式）+ `monitoring/__init__.py` 导出 + `application/ports` 导出 |

#### TDD 循环 C：契约测试 + 组合根

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/contracts/test_port_contract_agent_tracing.py`（11 维度 + _DummyResolver） |
| 🟢 绿 | 组合根 `# === Story 5.7 — Phoenix 全链路追踪 ===` 区段追加注册（SINGLETON + owner=platform + tags）+ bootstrap 内 initialize 接线调用（resolve → initialize——enabled=false NoOp 零开销） |
| 🟡 变异 | lambda 漏 config 注入→维度 9b 红；注册名拼写错→维度 1 红；还原→绿 |
| 🔄 重构 | .env.example 三变量追加 + ruff+mypy |

- [ ] Subtask 1.1: 🔴 红 — PhoenixConfig 失败测试
- [ ] Subtask 1.2: 🟢 绿 — PhoenixConfig 实现
- [ ] Subtask 1.3: 🟡 变异 — 守卫突变实证
- [ ] Subtask 1.4: 🔴 红 — 端口 + PhoenixTracer 失败测试
- [ ] Subtask 1.5: 🟢 绿 — 端口 + 实现最小代码
- [ ] Subtask 1.6: 🟡 变异 — 装配/幂等/降级突变实证
- [ ] Subtask 1.7: 🔴🔴🟢 — 契约测试 + 组合根注册 + initialize 接线
- [ ] Subtask 1.8: 🔄 重构 — 导出/docstring/.env.example/门禁

**完成标准/Definition of Done:**
- [ ] 配置/端口/实现/注册四件交付；契约 11 维度绿；验收 AC-1×3 场景转绿

---

### Task 2: @trace 装饰器

**关联 AC:** AC-2（装饰器面）、AC-3.2（通道）

#### TDD 循环 A：装饰器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/test_tracing_decorator.py`（模块级 fixture：set_tracer_provider(测试 provider + Simple + InMemory) + teardown reset_for_testing——**装饰器走全局 API 的唯一测试通道**；用例：装饰 async 函数→span 自动创建名正确/attributes 参数写入/异常→record_exception + status ERROR + re-raise 原异常/NoOp[全局复位后]→零 span 返回值不变/functools.wraps `__name__`/`__doc__` 保留/SpanAttributeKeys 四键常量逐字断言） |
| 🟢 绿 | 实现 `src/application/tracing.py`（trace 装饰器 + get_tracer("sisys.agent") + ParamSpec 泛型 + SpanNames 引用） |
| 🟡 变异 | re-raise 删除→透传断言红；record_exception 删除→异常事件断言红；span_name 未用参数→名断言红；还原→绿 |
| 🔄 重构 | docstring（NoOp 语义 + 仅 async 支持注记）+ ruff+mypy |

- [ ] Subtask 2.1: 🔴 红 — 装饰器失败测试（五面）
- [ ] Subtask 2.2: 🟢 绿 — 装饰器最小实现
- [ ] Subtask 2.3: 🟡 变异 — 异常分支/命名突变实证
- [ ] Subtask 2.4: 🔄 重构 — 泛型签名/docstring/门禁

**完成标准/Definition of Done:**
- [ ] 装饰器五面（正常/属性/异常/NoOp/签名）全绿；SpanAttributeKeys 键常量锁定；验收 AC-3.2 通道场景（组件面）随转绿

---

### Task 3: 工作链接入——根 span + 六阶段子 span + 属性写入 + trace_id 贯通 + 5-3 回归

**关联 AC:** AC-2（链上面）、AC-3.1/3.3、AC-4.3

#### TDD 循环 A：UseCase 根 span + 属性写入块

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/application/use_cases/test_run_agent_workflow.py` 追加：注入 provider 下 execute → agent_execution span 存在 + MVP 十项属性逐键断言（值与返回 Result/装配材料逐项相等——get_current_span 面）；NoOp 下 execute → 返回值与 5-3 既有断言一致（回归锚） |
| 🟢 绿 | `run_agent_workflow.py`：`@trace(SpanNames.AGENT_EXECUTION)` + execute 体内属性写入块（span = get_current_span()；`if span.is_recording():` 守卫逐键 set——NoOp span 空转零开销；数据源：agent 实体[role/name]、profile_result[startup_context_tokens/active_skill_count]、result[status/retry_count/executed_phases/confidence/input_hash]） |
| 🟡 变异 | 属性键改错字→逐键断言红；is_recording 守卫删除→NoOp 面行为断言红（或开销面红）；还原→绿 |
| 🔄 重构 | docstring（属性数据源对照表）+ ruff+mypy |

#### TDD 循环 B：六阶段装饰器 + trace_id 派生

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_agent_workflow_service.py` 追加：六方法装饰器在位 inspect 锚（`__wrapped__` 存在 + span 名常量引用）；execute 阶段 ExecutionContext.trace_id == 当前 span trace_id hex（注入 provider + Fake LLM 链内捕获） |
| 🟢 绿 | `agent_workflow_service.py`：六装饰器行（`@trace(f"{SpanNames.PHASE_PREFIX}perceive")` 等六处——**span 名末段对齐 executed_phases 枚举：package 非 package_evidence**）+ L254-257 trace_id 派生（`format(get_current_span().get_span_context().trace_id, "032x")`——注释更新：5-3 预留位核销） |
| 🟡 变异 | trace_id 派生改回空串→贯通断言红；某阶段装饰器删除→inspect 锚红；还原→绿 |
| 🔄 重构 | 模块头 5.7 注释更新（L29-31 预留注记核销）+ ruff+mypy |

#### TDD 循环 C：5-3 存量全家回归

| 阶段 | 动作 |
|------|------|
| 🔴→🟢 | 5-3 全家回归绿清单执行：`test_agent_workflow_service.py`（存量全量）/ `test_port_contract_agent_workflow_service.py` / `test_port_contract_agent_workflow_use_case.py` / `test_port_contract_agent_engine.py` / `test_single_agent_workflow_graph.py` / `test_langgraph_engine.py`（追加面）/ 集成 + 验收五文件族——装饰器纯附加（零构造签名变化）预期全绿；**异常项逐一登记**（如 Fake LLM prompt 断言受装饰器影响——实施时以实际清单为准甄别修复） |

- [ ] Subtask 3.1: 🔴 红 — use case span/属性失败测试
- [ ] Subtask 3.2: 🟢 绿 — @trace + 属性写入块
- [ ] Subtask 3.3: 🟡 变异 — 属性键/is_recording 突变实证
- [ ] Subtask 3.4: 🔴 红 — 六装饰器锚 + trace_id 失败测试
- [ ] Subtask 3.5: 🟢 绿 — 六装饰器 + trace_id 派生
- [ ] Subtask 3.6: 🟡 变异 — trace_id 空串回退/装饰器删除实证
- [ ] Subtask 3.7: 🟢 — 5-3 存量全家回归绿（清单登记）
- [ ] Subtask 3.8: 🔄 重构 — docstring/预留注记核销/门禁

**完成标准/Definition of Done:**
- [ ] 接入完成（三文件纯附加）；验收 AC-2.1/2.3、AC-3.1/3.3、AC-4.3 转绿；5-3 全家零回归；应用层覆盖率 ≥85%

---

### Task 4: 集成测试与性能——span 树真实链 + P95 + 开销对比

**关联 AC:** AC-2（集成面）、AC-5（全部）

> 性质说明：本 Task 对 Task 1-3 已交付链编写验证型测试（套件型豁免——红由 Task 0 前置，活性由变异保证）。

- [ ] Subtask 4.1: 编写 `tests/integration/test_integration_phoenix_tracer.py`——Fake LLM 手工装配六阶段链（5-3 集成装配形态 + 独立 provider + InMemory exporter）：场景① 成功链 span 树（根 + 六子 + parent 链 + span 序列 == executed_phases）② 重试轮（Fake LLM 首轮 verify 失败 → plan/reflect 再入序列）③ 异常链（LLM 异常 → 根/子 span ERROR + 原异常透传 + AgentDecided 不发布）④ NoOp 对比链（enabled=false 双跑等价）⑤ eval/drift 通道写入实证（四键写入→exporter 断言）⑥ P95<5ms（`_PERF_CACHE` + warmup 1 + 20 采样 + create_span×10 属性全周期 + `SPAN_RECORD_P95_LIMIT_SECONDS=0.005` 常量）⑦ 开销<1%（双跑对比公式 + t_untraced 基准下限守卫常量）⑧ trace_id 贯通（span hex == ExecutionContext.trace_id）
- [ ] Subtask 4.2: 变异实证——span 名常量改错→场景①红；re-raise 删除→场景③红；P95 常量突变（0.005→0.000001）→场景⑥红；还原→绿
- [ ] Subtask 4.3: 验收 AC-5×2 场景转绿（委托计时缓存命中验证）+ AC-2/AC-3 集成对应场景转绿

**完成标准/Definition of Done:**
- [ ] 集成八场景全绿；P95/开销双指标达标；计时组与三既有组不冲突；验收对应场景全绿

---

### Task 5: SDD 架构约束验证测试

**关联 AC:** AC-4.2

> 性质说明：SDD 规范验证测试（验证架构约束是否被遵守），非 TDD 单元测试。

- [ ] Subtask 5.1: 创建 `tests/unit/architecture/test_arch_phoenix_tracer.py`——验证器 A：application 触碰文件（tracing.py/agent_tracing.py/run_agent_workflow.py/agent_workflow_service.py）第三方 import 白名单（允许 opentelemetry；黑名单 pydantic/fastapi/sqlalchemy/redis 等——application 既有防线不变）；验证器 B：domain 零触碰（`src/domain/` 全目录 mtime 无关性不可测——改为 grep 本 Story 新增符号在 domain/ 零命中 + domain 零 import opentelemetry 断言）+ 组合根外零实例化（PhoenixTracer( 构造点仅 composition_root + tests）；验证器 C：装饰器静态锚（六阶段 + execute 方法 `__wrapped__` 在位——inspect 扫描）
- [ ] Subtask 5.2: 变异实证——tracing.py 注入 pydantic import→验证器 A 红；还原→绿
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
| 🟢 绿 | 编写 BDD 步骤实现（文件存在性检查——src 五文件 + tests 四目录清单，missing 断言） |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 6.1: 收尾场景步骤 1 — src 完成清单逐项确认（config/tracer/端口/装饰器/接入三文件/组合根/.env.example）
- [ ] Subtask 6.2: 收尾场景步骤 2 — tests 四目录完成清单逐项确认（同一收尾场景内两份清单）
- [ ] Subtask 6.3: 运行全量验收（15 场景终态）+ `pytest tests/` + `ruff check` + `mypy` 收尾校验 + 5-3 全家回归终验
- [ ] Subtask 6.4: 文档与台账终态更新——deferred-work.md 留项终态（OD-1/OD-2/OD-4 + R1-DF2 顺延注记落盘确认）+ architecture.md §14.4 注记（5.7 交付——OTel 实现口径）+ §13 目录树 monitoring/ 落位注记 + sisys-core-domain-design.md §17.3.8 实现注记（OD-1 映射说明）+ sprint-status.yaml 状态流转

**完成标准/Definition of Done:**
- [ ] 15 场景全绿；全量回归零 5.7 面新失败；Story 可进入 `review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ 横切可观测（OTel 全局 API 装饰器埋点——应用层第三方 API 包依赖先例开创）+ 基础设施配置器（PhoenixTracer 非 HTTP 组件——进程内 SDK 生命周期管理）
- **设计约束:** 领域层零依赖（本 Story domain 零触碰）；`.importlinter` application-no-infrastructure（第三方包不在层间限制内——opentelemetry 合法）；端口注册 PortSpec + 组合根唯一实例化点；OTel 全局 TracerProvider 单次设置约束（#8639——测试隔离策略 SSOT）
- **接口治理:** 统一端口注册/Registry/Resolver/ContractGate、Composition Root 装配、契约优先（11 维度）、版本化兼容、禁止跨模块直接依赖实现类
- **技术栈:** Python 3.11+ / opentelemetry-api+sdk+exporter-otlp ^1.21.0（**既有依赖零新增**——OD-1）/ InMemorySpanExporter（SDK 自带）/ pytest-bdd ^8.0.0

### 关键架构决策 Key Design Decisions

**DC-1 追踪底座——OTel SDK 原生实现，零新运行时依赖（OD-1）**
- 选定：PhoenixTracer 基于仓内既有 opentelemetry ^1.21.0（pyproject L88-90）实现——`project_name` → Resource `service.name`，span 经 OTLP exporter 指向 Phoenix server（独立部署）
- 论证：①`phoenix.tracing.trace` 伪码 API 已废弃（Phoenix 官方迁移到 OpenInference/OTel——`phoenix.otel.register` 为现入口）；②arize-phoenix 20.26.1 依赖树强制 OTel 栈升级（container extra 钉 opentelemetry-sdk==1.45.0 vs 仓内 ^1.21.0）——威胁 1.3 事件总线既有 OTEL 集成，回归面不可控；③OTel SDK 完整覆盖 epics 全部 AC 语义（span 创建/属性/生命周期/导出——@trace 与 span 树是 OTel 原生能力）；④Phoenix server 官方支持任意 OTLP 客户端——「零依赖客户端 + Phoenix server」是同等达成的现代集成形态；⑤连带收益：OTel 自带类型（零 stubs 需求）+ InMemorySpanExporter 测试零外联
- 备选：引入 arize-phoenix 完整包（弃——上述②③）；openinference-semantic-conventions 轻量包（弃——5.7 自定义键足够，LLM span 语义归 5.8 按需评估）

**DC-2 端口形态——AgentTracingPort 应用层契约 + SpanHandle duck-type OTel Span**
- 选定：`AgentTracingPort`（application/ports——R2 具体应用端口，5.7-5.9 评估可观测族的正式契约）三方法（create_span/initialize/shutdown）+ `SpanHandle` 三方法协议（方法名逐字对齐 OTel Span——set_attribute/record_exception/set_status——**零包装层**：PhoenixTracer 直接返回 OTel Span 原生对象，duck-type 天然满足协议）
- 论证：①端口价值 = 5.8 EvaluationHarness/5.9 CUSUM 的注入式消费契约（构造注入而非全局 API——可测性）+ 组合根纪律（注册/契约测试/接线断言）；②SpanHandle 对齐 OTel 方法名使「零包装」可行——包装层（SpanWrapper 类）是纯转发无增益（YAGNI）；③SpanAttributeKeys 常量注册表归端口文件——键字符串是 5.7-5.9 跨 Story 契约（单一真源防拼写漂移，AC-3.2 元断言锁定）
- 备选：不建端口（装饰器+全局 API 全覆盖——弃：5.8/5.9 无注入面且违反项目端口纪律）；domain/ports 放追踪端口（弃：追踪非领域概念，domain 零依赖原则下 domain/ports 只承载业务基础能力——R1/R2 分工）

**DC-3 @trace 装饰器——OTel 全局 API + NoOp 天然降级（application/tracing.py）**
- 选定：装饰器内部 `opentelemetry.trace.get_tracer("sisys.agent")`（全局 API——未 initialize 时 OTel 返回 proxy→NoOp tracer，span 操作空转零开销零异常）；异常路径 record_exception + set_status(ERROR) + **re-raise 原异常**（零吞异常——装饰器不改异常语义）
- 论证：①装饰器在类定义时静态求值——无构造注入通道，全局 API 是 OTel 官方为「库插桩」设计的标准形态（SQLAlchemy/HTTP instrumentation 同款）；②NoOp 降级零配置零分支（OTel API 内建——比 enabled 判断更彻底：proxy tracer 在 provider set 后自动升级为真 tracer）；③应用层依赖 opentelemetry-**api**（纯 API 包与 logging 同级定位）——.importlinter 只限层间方向不限第三方，合法且留下「application 只碰 API 包、SDK 归 infrastructure」的分界纪律（AST 验证器 A 白名单锁定）
- 备选：装饰器经全局 Resolver resolve("agent_tracing")（弃——服务定位器 + 未 bootstrap 时 KeyError 分支复杂于 NoOp；且与端口注入双通道并存造成语义分裂）；装饰器放 infrastructure（弃——被装饰的应用层方法 import infrastructure 违反依赖方向矩阵）

**DC-4 span 拓扑与接入面——两级树 + 纯附加接入（零构造签名回归）**
- 选定：根 span `agent_execution`（@trace 于 RunAgentWorkflowUseCase.execute——epics 钦定名）+ 六子 span `agent.{phase}`（@trace 于 AgentWorkflowService 六方法——span 名对齐 executed_phases 枚举，末段 "package"）；业务属性经用例体内 `get_current_span().set_attribute` 写入（`is_recording()` 守卫——NoOp 空转零开销）；LangGraphEngine/图工厂**零改动**（引擎是传输层，应用层根/子 span 已覆盖）
- 论证：①两级树匹配 epics AC（agent_execution + 阶段可见性）且最小侵入——对 5-3 三文件是**纯附加装饰**（零构造签名变化 → 零构造点苦役——5-6 十四构造点教训结构性规避）；②属性写入放用例体内而非装饰器声明式提取（on_return 钩子）——数据源显式可测（AC-3.1 逐键断言直配），装饰器保持通用性；③工具层孙 span 不做（trace_id 已贯通 ExecutionContext——工具侧可关联即可，深度追踪 V1 按需）
- 备选：LangGraph callback 机制（弃——仓内无此机制，引入是 5-3 交付面重构）；装饰器声明式属性提取（弃——签名耦合 + 泛型窄化）；引擎层 span（弃——双重埋点 + infrastructure 内 OTel SDK 边界模糊化）

**DC-5 OTel 全局状态治理——5.7 是唯一 setter + 测试独立 provider 注入**
- 选定：生产面 PhoenixTracer.initialize() 是全局 `set_tracer_provider` 的**全仓唯一调用点**（otel_config.init 默认关闭且全仓零生产调用——现状全局从未被 set；5.7 bootstrap 显式接线成为首个也是唯一 setter；event-bus 未来启用时改读全局不 set——文档注记）；测试面**默认不经全局**——独立 TracerProvider + SimpleSpanProcessor + InMemorySpanExporter 经 `PhoenixTracer(tracer_provider=注入)` 构造通道；装饰器测试例外（全局 API 通道）：模块级 fixture set 一次 + teardown `reset_for_testing()` 复位（otel_config L315-339 先例——`trace._TRACER_PROVIDER = None` 内部复位）
- 论证：OTel 全局 provider 每进程仅可设置一次（二次 set 被静默忽略——Arize-ai/phoenix#8639 CI 实证）——不治理则测试跨模块污染（A 模块 set 后 B 模块注入失效）+ 生产双 setter 冲突
- 备选：全测试走全局 + reset（弃——并发场景脆弱且注入通道本就存在）

**DC-6 性能测量口径——进程内开销分离 + 双跑对比公式**
- 选定：P95<5ms 锚 = create_span 全周期（进入→10 属性写入→end；Simple+InMemory 同步导出——测纯进程内开销，生产 Batch 异步导出更优）；开销<1% 公式 = `(t_traced - t_untraced) / t_untraced < 0.01`（同一 Fake LLM 手工装配六阶段链双跑；t_untraced = NoOp 态即「装饰器在位 + span 空转」纯开销形态）+ t_untraced 基准下限守卫（防链意外加速致分母失真）
- 论证：epics「追踪开销<1%（对比有无 @trace 的执行时间）」的可操作化——「有无」两态在装饰器常驻代码后语义为「initialize 启停两态」（装饰器不可运行时摘除）；下限守卫防 benchmark 退化
- 备选：NoOp vs 无装饰器三方对比（弃——无装饰器形态仅 dev 分支可达，测它无生产意义）

**DC-7 追踪失败降级哲学——纯旁路零影响主链**
- 选定：create_span/装饰器/属性写入全部 catch OTel 异常 → logger.warning 降级，**绝不上抛绝不改主链行为**（含 initialize 失败——返回 False 降级 NoOp）；与 5-6 audit 联动降级（DC-6）同哲学的更强形态：追踪连「拒绝主链」语义都没有
- 论证：可观测性是附加面——追踪组件故障不应使 Agent 工作流失败（epics 追踪开销<1% 隐含「追踪不得引入故障面」）；主链可用性 > 可观测完整性
- 备选：追踪失败上抛（弃——单点故障放大）；失败静默（弃——warning 日志是运维面最低可见性）

**DC-8 零新领域异常**
- 101（PhoenixConfig 守卫）复用足够；追踪运行面零抛（DC-7）；无新业务规则失败面——异常契约四件套零改动（同 5-6 DC-8 论证形态）

**DC-9 生命周期——SINGLETON（Epic 5 全家政策）**
- agent_tracing SINGLETON（isolation 五连先例 L2874/L2887/L2917/L2945 + agent_workflow L2832；PhoenixTracer 持 provider 单例语义——initialize 幂等 + 全局唯一 setter 与 SINGLETON 生命周期自洽）；lambda 注入 `PhoenixConfig.from_env()`（config 构造轻量无依赖——无需独立端口）

**关键决策对照表（选中方案 vs 备选）：**

| 决策点 | 选中 | 备选（弃因） |
|--------|------|-------------|
| 追踪底座 | OTel SDK 原生（DC-1） | arize-phoenix 包（旧 API 已废弃 + OTel 栈升级回归风险 + 重依赖） |
| 端口 | AgentTracingPort 应用层 + duck-type SpanHandle（DC-2） | 不建端口（5.8/5.9 无注入面）；domain 端口（追踪非领域概念） |
| 装饰器 | OTel 全局 API + NoOp 降级（DC-3） | Resolver 服务定位（语义分裂）；infrastructure 装饰器（违反依赖方向） |
| span 拓扑 | 两级树 + 纯附加接入（DC-4） | LangGraph callback（无机制需重构）；引擎层 span（双重埋点） |
| 全局状态 | 唯一 setter + 测试注入通道（DC-5） | 全局+reset 全测试（并发脆弱） |
| eval 属性 | 常量注册 + 通道验证（OD-2） | 生产预置 None（OTel 不支持）/哨兵值（语义歧义） |

### 风险登记

| # | 风险 | 处置 |
|---|------|------|
| 1 | OTel 全局 provider 单次设置（#8639）——测试跨模块污染/生产双 setter 冲突 | DC-5：唯一 setter 声明 + 测试独立 provider 注入通道 + 装饰器测试 reset_for_testing 复位；AST/契约锁定 initialize 是 set 唯一生产调用点 |
| 2 | asyncio 跨 task 上下文传播失效（子 span parent 链断裂） | OTel contextvars 机制原生支持 asyncio；AC-2.1 parent 链断言钉死（若断——LangGraph ainvoke 内部线程池边界排查，登记实施裁定） |
| 3 | 装饰器破坏 5-3 存量断言（Fake LLM prompt 序列/契约签名） | Task 3 循环 C 全家回归清单；装饰器纯附加 + functools.wraps 签名保真（AC-2 断言）；异常项登记甄别 |
| 4 | 性能基准 flaky（Fake LLM 链耗时波动致开销比失真） | t_untraced 基准下限守卫常量 + 同 worker 双跑 + _PERF_CACHE 委托；预期裕量 >100×（μs 级 span × 12+ vs 百 ms 级链） |
| 5 | BatchSpanProcessor 误入测试链（后台线程异步导出致断言时序 flaky） | 测试统一注入 SimpleSpanProcessor + InMemorySpanExporter（同步导出）；生产 Batch 仅经组合根 lambda 形态断言 |
| 6 | mypy 对装饰器泛型签名窄化告警（ParamSpec 边界） | ParamSpec + TypeVar 标准形态 + 存量 mypy 宽松模式（disallow_untyped_defs=false）；实施时 ruff+mypy 门禁即验 |
| 7 | metrics 端口 impl 指向不存在的 metrics_adapter.py（Agent 调研发现的存量缺口——bootstrap 静默跳过） | **不碰**（1.19 存量缺陷非本 Story 面——5.7 不依赖 MetricsPort）；知悉登记：未来监控域维护 Story 修复（本 Story 不扩大范围） |

### 项目结构说明 Project Structure

```
src/
├── application/
│   ├── ports/
│   │   ├── agent_tracing.py                  # 新建：AgentTracingPort + SpanHandle + SpanAttributeKeys/SpanNames
│   │   └── __init__.py                       # 修改：（如有聚合导出）
│   ├── tracing.py                            # 新建：@trace 装饰器（OTel 全局 API + NoOp 降级）
│   ├── services/
│   │   └── agent_workflow_service.py         # 修改：六阶段 @trace + trace_id 派生（纯附加）
│   └── use_cases/
│       └── run_agent_workflow.py             # 修改：@trace("agent_execution") + 属性写入块（纯附加）
├── infrastructure/
│   ├── config/
│   │   └── phoenix.py                        # 新建：PhoenixConfig（frozen + from_env + 101 守卫）
│   └── monitoring/
│       ├── phoenix_tracer.py                 # 新建：PhoenixTracer（端口实现 + initialize/shutdown/reset）
│       └── __init__.py                       # 修改：导出
└── composition_root.py                       # 修改：# === Story 5.7 === 注册 + initialize 接线

.env.example                                  # 修改：可观测性区 + PHOENIX_* 三变量

tests/
├── unit/
│   ├── application/
│   │   ├── test_tracing_decorator.py         # 新建（装饰器五面 + 键常量）
│   │   ├── services/test_agent_workflow_service.py      # 追加（装饰器锚 + trace_id）
│   │   └── use_cases/test_run_agent_workflow.py         # 追加（根 span + 属性集）
│   ├── infrastructure/
│   │   ├── monitoring/test_phoenix_tracer.py  # 新建（实例化/幂等/降级/异常降级）
│   │   └── config/test_phoenix_config.py      # 新建（from_env/101 守卫）
│   └── architecture/test_arch_phoenix_tracer.py  # 新建（验证器 A/B/C）
├── contracts/
│   └── test_port_contract_agent_tracing.py   # 新建（11 维度）
├── integration/
│   └── test_integration_phoenix_tracer.py    # 新建（八场景 + 计时委托）
└── acceptance/
    ├── test_acceptance_phoenix_tracer.feature  # 新建（14+收尾=15 场景）
    └── test_acceptance_phoenix_tracer.py       # 新建（BDD 步骤）

docs/architecture/architecture.md             # 修改：§14.4 注记 + §13 目录树（Task 6）
docs/architecture/sisys-core-domain-design.md  # 修改：§17.3.8 实现注记（OD-1 映射——Task 6）
_bmad-output/implementation-artifacts/deferred-work.md  # 修改：OD 登记 + R1-DF2 顺延注记（Task 0/6）
_bmad-output/implementation-artifacts/sprint-status.yaml  # 修改：5-7 状态流转
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 5.6](./5-6-isolation-switching-log.md)（v1.4.3 done 收敛态——文档审查 5 轮 + 代码审查 5 轮完整教训链）+ [Story 5.3](./5-3-single-agent-workflow.md)（v1.2.x——5.7 直接依赖）

**关键学习/Key Learnings:**
- **构造签名扩展 = 回归面苦役**（5-6 十四构造点）——本 Story 结构性规避：装饰器纯附加零构造签名变化（DC-4），回归面仅「行为不变」验证
- **断言可满足性断层是最大实施陷阱**（5-6 R3-F1：端口声明 Raises 但照抄模板实现不满足——红错位至 Task 4）——本 Story 对策：端口「零抛出 + None 降级」契约与实现降级路径同 Task 交付（Task 1 循环 B 异常降级用例前置）
- **测试环境前提必须钉死**（5-6 AC-2.3 不设 ContextVar session 前提）——本 Story 对应面：OTel 全局 provider 测试隔离前提（DC-5 + Task 0.4 SSOT）
- **str/枚举混入与形态守卫**（5-6 R3-F1 白名单哲学）——PhoenixConfig 101 守卫 isinstance 先行 + bool 子类防呆
- **委托计时模式**（_PERF_CACHE + xdist_group 同组 + 常量单源集成定义/验收 import + 采样禁双跑）
- **零新 marker/目录/CI 专项**（5-6 v2.1.0 用户裁定）——本 Story 测试全落既有目录；benchmark 既有 marker 场景级使用
- **审计断言三段式 + 计数断言**（isinstance→code→context；恰一次/零次）——101 场景与 span 计数断言沿用
- **OD-n 偏离声明编号 + gap 四要素 + V1 归宿必进 deferred-work**（5-6 v1.0.1 教训——D# 撞名实害）
- **5-3 移交锚核销模式**：预留注释（trace_id/事件锚点/订阅决定）逐一在 Task 0.8 处置登记——「已实现未接线」清单纪律
- **恒真断言防范**（5-6 R2-F2：`!= or ==` 恒真式）——span 断言用精确值/集合断言，禁 `>=0` 形态

**应用到本故事/Applied to This Story:**
- [ ] 装饰器纯附加 + 5-3 全家回归清单（Task 3 循环 C）
- [ ] 端口零抛契约与降级实现同 Task（Task 1 循环 B）
- [ ] OTel 全局状态隔离 SSOT（Task 0.4 + DC-5）
- [ ] 委托计时三件（Task 4 + 验收 AC-5）
- [ ] 零新 marker/目录/CI 专项
- [ ] 101 三段式 + span 计数精确断言 + OD-n 台账（Task 0.7）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (glm-5.3) |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-10-27 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（L1715-1763） |
| **架构文档** | `docs/architecture/architecture.md`（§14.4/L2944/ADR-012） |
| **核心域设计** | `docs/architecture/sisys-core-domain-design.md`（§17.3.8 L1594-1702） |
| **前一个 Story** | `5-6-isolation-switching-log.md`（v1.4.3）+ `5-3-single-agent-workflow.md`（依赖） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（含范围边界表——与 5.8/5.9/5.10/5.11/V1/deploy 精确切分）
- [x] 架构约束从 architecture.md/sisys-core-domain-design.md 提取（§17.3.8 实际位于 core-domain-design——epics 引用「architecture.md §17.3.8」系文档指针偏差，范围权威内容已核）
- [x] 前一个故事学习经验整合（5-6 教训链 + 5-3/5-6 移交留项三项处置）
- [x] 四视角并行代码调研（可观测性基础设施 / Agent 工作流 5.1-5.6 / 端口契约与注册 / 测试模板与基建——关键事实独立验证：OTel 依赖现状/otel_config 生命周期/create_span 降级先例/trace_id 预留位/AgentWorkflowResult 数据源/importlinter 边界/reset_for_testing 复位机制）
- [x] Web 技术调研（arize-phoenix 20.26.1 版本/依赖树/`phoenix.tracing.trace` 旧 API 废弃/`phoenix.otel.register` 现代入口/OTel 全局单次设置约束 #8639——OD-1 事实依据）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（DC-1~DC-9 设计决策 + OD-1~OD-4 偏离声明 + 风险七项）
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/5-7-phoenix-evaluation-harness.md`（本文件）

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/application/ports/agent_tracing.py` - AgentTracingPort + SpanHandle + SpanAttributeKeys/SpanNames
- `src/application/tracing.py` - @trace 装饰器
- `src/infrastructure/config/phoenix.py` - PhoenixConfig
- `src/infrastructure/monitoring/phoenix_tracer.py` - PhoenixTracer
- `tests/unit/infrastructure/config/test_phoenix_config.py` - 配置单测
- `tests/unit/infrastructure/monitoring/test_phoenix_tracer.py` - Tracer 单测
- `tests/unit/application/test_tracing_decorator.py` - 装饰器单测
- `tests/contracts/test_port_contract_agent_tracing.py` - 端口契约（11 维度）
- `tests/integration/test_integration_phoenix_tracer.py` - 集成（八场景+计时）
- `tests/unit/architecture/test_arch_phoenix_tracer.py` - 架构验证器
- `tests/acceptance/test_acceptance_phoenix_tracer.feature` - Gherkin（14+收尾=15 场景）
- `tests/acceptance/test_acceptance_phoenix_tracer.py` - BDD 步骤

**待修改的文件/To Be Modified (Dev Story 实施):**
- `src/application/services/agent_workflow_service.py` - 六装饰器 + trace_id 派生（纯附加）
- `src/application/use_cases/run_agent_workflow.py` - 根 span + 属性写入块（纯附加）
- `src/composition_root.py` - Story 5.7 区段注册 + initialize 接线
- `src/infrastructure/monitoring/__init__.py` - 导出
- `.env.example` - PHOENIX_* 三变量
- `docs/architecture/architecture.md` + `sisys-core-domain-design.md` - 交付注记（Task 6）
- `_bmad-output/implementation-artifacts/deferred-work.md` - OD 登记 + R1-DF2 顺延（Task 0/6）
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - 状态流转
- 追加面：`tests/unit/application/services/test_agent_workflow_service.py` + `tests/unit/application/use_cases/test_run_agent_workflow.py`（5-3 存量文件追加）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 5.7 |
| **Story Key** | 5-7-phoenix-evaluation-harness |
| **File** | `_bmad-output/implementation-artifacts/stories/5-7-phoenix-evaluation-harness.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 5: Agent 协作系统（价值组：单 Agent 战略规划能力——EV 可观测族首 Story） |
| **优先级** | P0-7（epics 执行序；FR-EV-01 功能 P0——双锚） |
| **覆盖 FR** | FR-EV-01（Phoenix Evaluation Harness 全链路追踪——追踪面；评估面归 5.8） |
| **性能锚** | epics L1746-1747（span 记录 P95<5ms / 追踪开销<1%） |
| **覆盖率锚** | 应用层 ≥85%（epics L1750）/ infrastructure ≥75% / domain ≥90% 维持（零触碰） |

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
| — | （待审查周期填写） | — | — |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** （待代码审查周期填写）
**审查模式:** （待定）

#### 需决策 Decision Needed

- [ ] （待填写）

#### 已修复 Patch

- [ ] （待填写）

#### 已推迟 Defer

- [ ] （待填写）

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
| 2026-10-27 | v1.0.0 | 创建故事文件（四视角并行调研：可观测性基础设施/Agent 工作流/端口契约/测试模板 + Web 技术调研；9 项关键架构决策 DC-1~DC-9 + 4 项偏离声明 OD-1~OD-4 + 风险七项；OTel SDK 原生实现零新依赖[OD-1——phoenix.tracing 旧 API 废弃 + OTel 栈升级回归风险]；AgentTracingPort + duck-type SpanHandle[DC-2]；@trace 装饰器 OTel 全局 API + NoOp 降级[DC-3]；两级 span 树纯附加接入零构造点回归[DC-4]；OTel 全局状态唯一 setter + 测试注入通道[DC-5]；eval/drift 常量注册+通道口径[OD-2]；5-6 事件消费基建移交裁定归 5.11[OD-4]；5-3 移交三项处置[trace_id 核销/AgentDecided 不接线/R1-DF2 顺延]） |

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-10-27
**最后更新/Last Updated:** 2026-10-27
**更新说明/Description:**
- v1.0.0: 创建故事文件
