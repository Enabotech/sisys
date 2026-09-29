# language: zh-CN
功能: Story 4.1e 内部框架 Skills 成熟化验收
  作为工具工程师,
  我希望 7 个纯内部框架 Skills 基于用户输入的内部业务信息输出结构化分析结果,
  以便 Agent 调用这些 Skills 时通过 Schema 模板与框架逻辑引导完成战略分析。

  # ============================================================
  # AC-1 / AC-4: 空声明不变量 + 内部数据主通道行为面（7 Skills 平铺）
  # ============================================================
  场景: value-proposition-canvas 内部数据经主通道驱动五阶段分析
    假如 加载技能 "value-proposition-canvas" 的 L2 技能元数据
    并且 该技能 frontmatter 未声明任何外部数据源
    当 该技能携带内部数据参数执行且分析代码不含数据源标记
    那么 执行结果为成功
    并且 内部数据参数已进入规划提示词
    并且 注入沙箱代码不含 DATA_SOURCES 前言
    并且 输出证据不含外部数据溯源

  场景: business-model-canvas 内部数据经主通道驱动五阶段分析
    假如 加载技能 "business-model-canvas" 的 L2 技能元数据
    并且 该技能 frontmatter 未声明任何外部数据源
    当 该技能携带内部数据参数执行且分析代码不含数据源标记
    那么 执行结果为成功
    并且 内部数据参数已进入规划提示词
    并且 注入沙箱代码不含 DATA_SOURCES 前言
    并且 输出证据不含外部数据溯源

  场景: org-design-framework 内部数据经主通道驱动五阶段分析
    假如 加载技能 "org-design-framework" 的 L2 技能元数据
    并且 该技能 frontmatter 未声明任何外部数据源
    当 该技能携带内部数据参数执行且分析代码不含数据源标记
    那么 执行结果为成功
    并且 内部数据参数已进入规划提示词
    并且 注入沙箱代码不含 DATA_SOURCES 前言
    并且 输出证据不含外部数据溯源

  场景: strategy-map 内部数据经主通道驱动五阶段分析
    假如 加载技能 "strategy-map" 的 L2 技能元数据
    并且 该技能 frontmatter 未声明任何外部数据源
    当 该技能携带内部数据参数执行且分析代码不含数据源标记
    那么 执行结果为成功
    并且 内部数据参数已进入规划提示词
    并且 注入沙箱代码不含 DATA_SOURCES 前言
    并且 输出证据不含外部数据溯源

  场景: dependency-graph 内部数据经主通道驱动五阶段分析
    假如 加载技能 "dependency-graph" 的 L2 技能元数据
    并且 该技能 frontmatter 未声明任何外部数据源
    当 该技能携带内部数据参数执行且分析代码不含数据源标记
    那么 执行结果为成功
    并且 内部数据参数已进入规划提示词
    并且 注入沙箱代码不含 DATA_SOURCES 前言
    并且 输出证据不含外部数据溯源

  场景: raci-matrix 内部数据经主通道驱动五阶段分析
    假如 加载技能 "raci-matrix" 的 L2 技能元数据
    并且 该技能 frontmatter 未声明任何外部数据源
    当 该技能携带内部数据参数执行且分析代码不含数据源标记
    那么 执行结果为成功
    并且 内部数据参数已进入规划提示词
    并且 注入沙箱代码不含 DATA_SOURCES 前言
    并且 输出证据不含外部数据溯源

  场景: gantt-chart 内部数据经主通道驱动五阶段分析
    假如 加载技能 "gantt-chart" 的 L2 技能元数据
    并且 该技能 frontmatter 未声明任何外部数据源
    当 该技能携带内部数据参数执行且分析代码不含数据源标记
    那么 执行结果为成功
    并且 内部数据参数已进入规划提示词
    并且 注入沙箱代码不含 DATA_SOURCES 前言
    并且 输出证据不含外部数据溯源

  # ============================================================
  # AC-6: Edge Cases（空白名单 207 / 内部数据不足引导 / 负向触发跳转 ×2）
  # ============================================================
  场景: 纯内部框架 Skill 空白名单安全失败
    假如 加载技能 "business-model-canvas" 的 L2 技能元数据
    当 代码含白名单外数据源 "world-bank" 标记经 Engine Execute 阶段处理
    那么 抛出 BusinessRuleViolationError
    并且 错误码为 EXCEPTION_207

  场景: 内部数据不足时经模板缺口登记引导补全
    假如 加载技能 "value-proposition-canvas" 的 L2 技能元数据
    当 该技能携带空内部数据参数执行
    那么 执行结果为成功
    并且 规划提示词包含空参数字典
    并且 技能 SOP 含数据缺口登记引导

  场景: dependency-graph 与 gantt-chart 负向触发互相跳转
    假如 加载技能 "dependency-graph" 的 L2 技能元数据
    并且 加载技能 "gantt-chart" 的 L2 技能元数据
    那么 技能 "dependency-graph" 的负向触发章节指向 "gantt-chart"
    并且 技能 "gantt-chart" 的负向触发章节指向 "dependency-graph"

  场景: strategy-map 与 bsc-scorecard 负向触发互相跳转
    假如 加载技能 "strategy-map" 的 L2 技能元数据
    并且 加载技能 "bsc-scorecard" 的 L2 技能元数据
    那么 技能 "strategy-map" 的负向触发章节指向 "bsc-scorecard"
    并且 技能 "bsc-scorecard" 的负向触发章节指向 "strategy-map"
