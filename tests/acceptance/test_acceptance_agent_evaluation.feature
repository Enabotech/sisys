# language: zh-CN
功能: Agent 输出质量评估（Story 5.8——FR-EV-02）

  作为可观测性工程师
  我想要实现 Agent 输出质量评估（EvaluationHarness：幻觉检测 + 上下文相关性 + 置信度校准 + overall 加权）
  以便 Agent 工作流输出质量可量化评估，评估指标写入 span 属性，支持基于评估结果的质量改进与漂移检测

  # =========================================================================
  # AC-1: EvaluationResult 模型与三维指标计算（组件级——零服务依赖）
  # =========================================================================

  场景: AC-1.1 - EvaluationResult 构造与分数域校验
    假如 评估端口模型模块已加载
    当 构造合法 EvaluationResult 实例并执行分数域校验
    那么 四分数字段值与权重常量断言通过
    并且 越界分数构造抛出 ValidationError 201
    并且 frozen 不可变断言通过

  场景: AC-1.2 - 幻觉检测 LLM 结构化调用
    假如 评估链已装配（Fake LLM + resolver 替身）
    当 调用 EvaluationHarness.evaluate 执行评估
    那么 幻觉检测 structured_generate 调用断言通过（prompt 三要素 + Schema 身份 + config 派生）
    并且 幻觉分与 Fake 注入值相等
    并且 Schema 校验失败路径抛出 AgentEvaluationError 450
    并且 LLM 族异常矩阵断言通过（450 包装与 332 透传分述）

  场景: AC-1.3 - 证据支撑度与校准公式计算
    假如 评估链已装配（Fake LLM + resolver 替身）
    当 调用证据支撑度四态参数化计算与校准公式数值矩阵
    那么 上下文相关性四态精确值断言通过（全空 0.0 / 仅引用 0.4 / 引用加轨迹 0.7 / 全满 1.0）
    并且 置信度校准数值矩阵断言通过（偏差 0 得 1.0 / 偏差 0.3 得 0.7 / 偏差不小于 1.0 得 0.0）
    并且 overall 加权手算对照断言通过（同式表达式期望值）

  # =========================================================================
  # AC-2: 评估模型 UDMR in-band 动态路由（组件级——真实 UDMR 决策链手工装配）
  # =========================================================================

  场景: AC-2.1 - 评估模型 cloud 路由与 LLMConfig 匹配
    假如 真实 UDMR 决策链已装配（健康检查替身 True + 单云端配置 + PIPL 服务显式注入）
    当 调用 resolver.resolve_config 解析评估模型配置
    那么 config 匹配云端模型（model 与 endpoint 与 api_key 与 timeout 逐字段相等）
    并且 RoutingDecided 事件经替身捕获发布断言通过
    并且 决策日志持久化断言通过

  场景: AC-2.2 - 云端不可用 local 回退与非硬编码双配置判别
    假如 真实 UDMR 决策链已装配（健康检查替身 False + 云端配置 + 本地模型）
    当 调用 resolver.resolve_config 解析评估模型配置
    那么 local 分支断言通过（config.model 等于 selected_model 等于 local_model）
    并且 双配置矩阵非硬编码判别通过（模型 A 与模型 B 随注入变化）

  场景: AC-2.3 - 路由产物匹配失败 450 与事件发布
    假如 漂移配置双注入构造（policy 云配置模型 B 与 resolver 云配置模型 A）
    当 调用 resolver.resolve_config 解析评估模型配置
    那么 匹配失败抛出 AgentEvaluationError 450（context 含 selected_model 与可用清单）
    并且 RoutingDecided 事件已发布断言通过（selected_model 与配置对应）

  # =========================================================================
  # AC-3: 主链接入——评估执行 + eval.* 三键写根 span + 降级（链级）
  # =========================================================================

  场景: AC-3.1 - 主链评估执行与 eval.* 三键写根 span
    假如 工作流链已装配（Fake LLM 五 Schema 分派 + 评估链注入 + OTel 链级全局通道）
    当 调用 RunAgentWorkflowUseCase.execute 执行六阶段工作流
    那么 agent_execution 根 span 三键真值断言通过（幻觉 0.2 / 相关性 0.0 / 校准 0.55）
    并且 三键经 SpanAttributeKeys 常量写入（键字符串逐字对照）
    并且 工作流返回值与评估块零耦合

  场景: AC-3.2 - 评估降级不阻断主链
    假如 工作流链已装配（Fake LLM 幻觉分支抛 LLMAPIError + 评估链注入 + OTel 链级全局通道）
    当 调用 RunAgentWorkflowUseCase.execute 执行六阶段工作流
    那么 主链正常返回 result（工作流断言全绿）
    并且 span 三键缺席断言通过
    并且 评估降级 warning 日志已记录
    并且 MVP 十属性不受影响

  场景: AC-3.3 - 构造签名扩展与存量回归基线
    假如 use case 模块与 5-7 基线资产已加载
    当 检查构造签名六依赖清单与 None 默认路径
    那么 第六参数 evaluation_harness 默认 None 且签名清单断言通过
    并且 None 默认路径行为与 5-7 基线一致（三键缺席 + 十属性在位）
    并且 5-7 断言更新后基线断言通过（六依赖基线对照）

  # =========================================================================
  # AC-4: 端口接线、架构合规与组合根注册（静态 + 接线）
  # =========================================================================

  场景: AC-4.1 - 组合根双端口接线与 use case 注入
    假如 UDMR 云端环境变量已清理
    当 resolve 双端口与 use case 实例
    那么 agent_evaluation 四件断言通过（可达与 isinstance 与 PortSpec 元数据与 SINGLETON）
    并且 evaluation_model_resolver 四件断言通过
    并且 use case 第六依赖注入可达（_evaluation_harness 非 None 且 isinstance 端口）
    并且 契约测试 11 维度断言基础齐备（REQUIRED_METHODS callable）

  场景: AC-4.2 - 架构静态扫描（白名单/domain 收窄/主链静态锚）
    假如 Story 5.8 交付文件已存在
    当 执行轻量 AST 扫描与符号 grep
    那么 application 触碰文件第三方白名单断言通过（仅 pydantic 与 opentelemetry）
    并且 domain 业务域零触碰断言通过（评估符号仅 exceptions 三件）
    并且 组合根外零实例化断言通过
    并且 主链评估块静态锚断言通过（evaluate 调用 + 三常量引用 + is_recording 守卫）
    并且 .env.example 与 event_channels.yaml 零改动

  # =========================================================================
  # AC-5: 评估延迟 P95<500ms（委托集成计时）
  # =========================================================================

  场景: AC-5.1 - 评估管线 P95 延迟达标
    假如 集成计时委托已缓存采样结果
    当 读取委托缓存的评估管线 P95 值
    那么 P95 小于 0.5 秒（常量单源 EVALUATION_P95_LIMIT_SECONDS）
    并且 正向锚断言通过（structured_generate 调用计数等于采样总数）

  # =========================================================================
  # 收尾: 完成清单逐项确认
  # =========================================================================

  场景: 收尾 - 完成清单逐项确认
    假如 Story 5.8 开发已完成
    当 检查 src 与 tests 完成清单
    那么 src 新建六文件与修改六文件逐项存在
    并且 tests 四目录清单逐项存在
    并且 5-7 断言更新文件两处已更新
    并且 .env.example 与 event_channels.yaml 零改动
