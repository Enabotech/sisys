# language: zh-CN
功能: Phoenix Evaluation Harness 全链路追踪（Story 5.7 — FR-EV-01 追踪面）

  作为可观测性工程师
  我想要 PhoenixTracer 与 @trace 装饰器自动记录 span（agent_execution 根 span + agent.{phase} 六阶段子 span 树）
  以便 Agent 执行过程支持全链路追踪与性能分析（5.8 评估 / 5.9 漂移检测的可观测底座）

  范围注记:
  - PhoenixTracer 以仓内 OTel SDK 实现（OD-1——零新运行时依赖，project_name 经 Resource service.name 承载）
  - eval.*/drift.* 属性本 Story 交付键常量与写入通道，生产填值归 5.8/5.9（OD-2）
  - 测试链路统一 InMemorySpanExporter 零外联；外部服务门控 = 零外部服务（Fake LLM 手工装配链自包含）

  # =========================================================================
  # AC-1: PhoenixTracer 实例化与配置（组件级——零服务依赖，注入通道为主）
  # =========================================================================

  场景: AC-1.1 - PhoenixTracer 实例化与 project_name 映射（双路径拆分）
    假如 PhoenixTracer 以注入路径构造（测试 provider 与内存导出器）
    当 执行 initialize 启用追踪
    那么 全局 provider 为注入实例且 create_span 产出真 span 到注入导出器
    假如 双复位全局后以自建路径构造 PhoenixTracer（配置 project_name 为 "sisys-agent"）
    当 执行 initialize 启用追踪
    那么 自建 provider 的 Resource 携带 service.name == "sisys-agent"
    并且 sampler 采样率与配置一致

  场景: AC-1.2 - initialize 幂等与 enabled=false 不装配
    假如 PhoenixTracer 以注入测试 provider 构造且已 initialize
    当 同实例再次调用 initialize
    那么 返回 True 且单次 create_span 后导出器恰收 1 个 span（无重复装配）
    并且 同实例再入不产生告警日志（实例闩静默语义）
    假如 enabled 为 false 的 PhoenixTracer 构造（未注入）
    当 调用 initialize
    那么 返回 False 且全局 provider 保持未装配
    并且 未注入未 initialize 的实例 create_span 降级 yield None

  场景: AC-1.3 - PhoenixConfig 101 守卫五场景与 from_env 四变量
    假如 PhoenixConfig 构造通道已就绪
    当 分别注入五类非法输入构造配置
    那么 每类抛 ConfigurationError 101 且 context 携带字段名与实际值
    当 解析环境四变量（含 OTel 标准端点 fallback 链与空串视为未设）
    那么 四变量与默认值矩阵及覆盖矩阵逐项一致

  # =========================================================================
  # AC-2: @trace 装饰器自动 span（链级——Fake LLM 手工装配，经 initialize 全局通道）
  # =========================================================================

  场景: AC-2.1 - agent_execution 根 span 与六阶段子 span 树自动创建
    假如 Phoenix 追踪已启用（测试内存导出器）
    并且 六阶段工作流链已装配（Fake LLM 首轮验证失败）
    当 执行 run-task 工作流
    那么 根 span 名为 agent_execution
    并且 六阶段子 span 名集合完整（agent.perceive/plan/execute/verify/reflect/package）
    并且 九阶段执行序为 perceive→plan→execute→verify→reflect→plan→execute→verify→package
    并且 每个子 span 的 parent 均为根 span（同 trace 上下文传播）
    并且 span 阶段序列与 executed_phases 终态一致（同源断言）

  场景: AC-2.2 - 异常路径 span ERROR 与 444 包装异常透传
    假如 Phoenix 追踪已启用（测试内存导出器）
    并且 六阶段工作流链已装配（Fake LLM 注入 LLMAPIError）
    当 执行 run-task 工作流
    那么 抛出 AgentWorkflowError 且 code 为 444
    并且 异常所在子 span 状态为 ERROR 且事件含 exception
    并且 根 span 同样标记 ERROR 且零吞异常（原样上抛）

  场景: AC-2.3 - NoOp 降级零 span 且主链行为等价（观察哨形态）
    假如 全局追踪未启用（proxy 态前提断言）且观察哨 provider 经注入通道待命
    并且 六阶段工作流链已装配（Fake LLM 首轮验证失败）
    当 执行 run-task 工作流
    那么 观察哨导出器计数保持为零（无旁路泄漏）
    并且 工作流终态与 5-3 基线一致（executed_phases 九阶段 + retry_count 为 1）
    并且 全局 provider 保持未装配（NoOp 判据是全局 provider 状态）

  # =========================================================================
  # AC-3: span 属性契约与 trace_id 贯通
  # =========================================================================

  场景: AC-3.1 - 根 span MVP 十项业务属性逐键断言
    假如 Phoenix 追踪已启用（测试内存导出器）
    并且 六阶段工作流链已装配（Fake LLM 首轮验证失败）
    当 执行 run-task 工作流
    那么 agent_execution span 十项属性与装配材料及返回结果逐项相等
    并且 active_skill_count 等于 len(tools_l1) 派生口径

  场景: AC-3.2 - eval-drift 四键常量注册与写入通道能力（组件级注入通道）
    假如 PhoenixTracer 以注入测试 provider 与内存导出器构造（未 initialize）
    那么 SpanAttributeKeys 四键常量与规划钦定字符串逐字一致
    并且 epics 三键是常量注册表的子集（子集式元断言）
    当 经 create_span 写入 eval-drift 四键测试值
    那么 导出 span 属性含全部四键且值相等（5.8/5.9 填值通道可用）

  场景: AC-3.3 - trace_id run 级贯通（span hex 等于工具层 ExecutionContext.trace_id）
    假如 Phoenix 追踪已启用（测试内存导出器）
    并且 六阶段工作流链已装配（Fake LLM 规划含工具步）
    当 执行 run-task 工作流并捕获工具层 ExecutionContext
    那么 根 span 的 trace_id hex 与 ExecutionContext.trace_id 一致（32 位小写十六进制）
    当 双复位全局后同链再执行（NoOp 态）
    那么 工具层捕获的 trace_id 为全零 32 位 hex（降级语义钉死）

  # =========================================================================
  # AC-4: 端口接线、架构合规与回归零破坏（静态 + 接线）
  # =========================================================================

  场景: AC-4.1 - 组合根接线与 initialize 传导（含配置错误降级负路径）
    假如 组合根已引导装配
    那么 agent_tracing 端口 resolve 可达且 PortSpec 元数据完整（SINGLETON）
    并且 resolve 实例 isinstance AgentTracingPort 且 resolve 无全局副作用
    当 场景内直构 PhoenixTracer（monkeypatch 环境启用追踪）并 initialize
    那么 initialize 返回 True（lambda 同构语义传导）
    当 直调 _wire_agent_tracing 接线单元且采样配置非法（PHOENIX_TRACES_SAMPLER_ARG 为 0）
    那么 记录 warning 降级跳过且不抛出（DC-7 旁路哲学）

  场景: AC-4.2 - 架构静态扫描（AST 三验证器与 domain 零触碰）
    那么 application 触碰文件第三方 import 白名单合规（允许 opentelemetry）
    并且 domain 目录零本 Story 触碰（零新增符号且零 opentelemetry import）
    并且 PhoenixTracer 实例化点仅组合根与测试（组合根外零实例化）
    并且 .env.example 三变量在位（PHOENIX_TRACING_ENABLED/PHOENIX_OTLP_ENDPOINT/PHOENIX_PROJECT_NAME）

  场景: AC-4.3 - 5-3 存量回归资产在位与装饰器纯附加
    那么 5-3 回归测试资产文件全部在位（unit 三文件族 + 契约三件 + integration + acceptance）
    并且 六阶段方法与 execute 用例构造签名与 5-3 基线一致（纯附加装饰零签名变化）
    并且 六阶段方法与 execute 用例的 __wrapped__ 在位（装饰器静态锚）

  # =========================================================================
  # AC-5: 性能（委托集成计时——span 记录 P95 与追踪开销）
  # =========================================================================

  场景: AC-5.1 - span 记录延迟 P95 小于 5ms
    当 执行 span 记录计时采样（委托集成缓存——禁双跑）
    那么 P95 延迟小于 5ms（create_span 全周期 × 10 属性）

  场景: AC-5.2 - 追踪开销小于 1%（k 轮双跑中位数对比）
    当 执行追踪开销双跑采样（委托集成缓存——fail-once 链 5+5 轮）
    那么 开销比例小于 1%（中位数公式）
    并且 traced 块导出器 span 计数恰为 50（正向锚——防静默降级假绿）

  # =========================================================================
  # 收尾: 交付完成清单（Task 6 追加——15 场景终态）
  # =========================================================================

  场景: 收尾 - 交付完成清单
    那么 src 交付九文件全部在位（配置/Tracer/端口/端口聚合导出/装饰器/接入两文件/组合根/monitoring 导出/env）
    并且 tests 四目录交付文件全部在位（unit 三件 + 契约 + integration + acceptance 两件）
