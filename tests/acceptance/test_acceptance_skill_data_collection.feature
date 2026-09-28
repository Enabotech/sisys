# language: zh-CN
# Story 4.1c — Skills 数据采集集成（6 个外部数据型 Skills，BDD 验收场景）
# 行为验收覆盖：AC-2/AC-4/AC-6 的端到端链路（白名单接线/采集三角化/降级与缓存）；
# AC-1 声明解析与 AC-3 SOP 成熟化由单元测试承载、AC-5 架构约束由架构测试承载（R2-F5 对齐）

功能: Skills 数据采集集成（外部数据型 Skills 完善）
  作为工具工程师
  我希望 6 个外部数据驱动型 Skills（pestel-analysis / porters-five-forces / appeals-analysis /
    competitor-analysis / scenario-planning / disruptive-innovation）复用 Story 4.1b 数据采集基础设施
  以便 Agent 调用这些 Skills 时自动从权威数据源获取高质量、可靠、新鲜的信息，
    LLM 基于真实数据生成结构化分析输出，无需用户手工填入数据

  背景:
    假如 数据采集基础设施已初始化（真实 DataSourceResolverService + 可编程数据源适配器 + 真实缓存 + InMemoryEventBus）

  # ===========================================================================
  # Happy Path：6 个 Skills 全链路采集（AC-4 / AC-6 行为面）
  # ===========================================================================

  场景: 场景 1 - pestel-analysis 六源并发采集全链路（Happy Path）
    假如 加载技能 "pestel-analysis" 的 L2 技能元数据
    并且 全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合
    并且 输出元数据含 source 与 freshness 与 confidence

  场景大纲: 场景 2 - 其余 5 个外部数据型 Skills 采集链路（Happy Path 参数化）
    假如 加载技能 "<slug>" 的 L2 技能元数据
    并且 全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

    例子:
      | slug                  |
      | porters-five-forces   |
      | appeals-analysis      |
      | competitor-analysis   |
      | scenario-planning     |
      | disruptive-innovation |

  # ===========================================================================
  # Edge Cases（AC-6 异常路径与安全失败不变量）
  # ===========================================================================

  场景: 场景 3 - 白名单外数据源抛 BusinessRuleViolationError（Edge）
    假如 加载技能 "pestel-analysis" 的 L2 技能元数据
    并且 全部声明数据源适配器行为正常
    当 沙箱代码引用白名单外数据源 "uspto"
    那么 抛出 BusinessRuleViolationError
    并且 错误码为 EXCEPTION_207

  场景: 场景 4 - 数据源不可用部分失败收敛（Edge）
    假如 加载技能 "porters-five-forces" 的 L2 技能元数据
    并且 数据源 "eurostat" 配置为不可用，其余声明源行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 可用数据源数据已注入
    并且 已发布 DataSourceFetchFailed 事件

  场景: 场景 5 - Key 缺失降级（newsapi/tavily 未注册 → 411 语义部分失败）（Edge）
    假如 加载技能 "appeals-analysis" 的 L2 技能元数据
    并且 数据源 "tavily" 与 "newsapi" 未注册（模拟 API Key 缺失），其余声明源行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 可用数据源数据已注入
    并且 已发布 DataSourceFetchFailed 事件

  场景: 场景 6 - 缓存命中二次执行不重复采集且新鲜度元数据完备（Edge）
    假如 加载技能 "scenario-planning" 的 L2 技能元数据
    并且 全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记连续两次经 Engine Execute 阶段处理
    那么 第二次执行外部采集次数不增加
    并且 输出元数据 freshness 评分在 0 到 1 之间

  场景: 场景 7 - 未成熟化 Skill 空白名单安全失败（Edge）
    假如 加载技能 "swot-tows" 的 L2 技能元数据
    当 含数据源标记的沙箱代码经 Engine Execute 阶段处理
    那么 抛出 BusinessRuleViolationError
    并且 错误码为 EXCEPTION_207

  场景: 场景 8 - 多源三角化断言（≥3 源 Skill 全声明源覆盖）
    假如 加载技能 "competitor-analysis" 的 L2 技能元数据
    并且 全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 注入数据源数量大于等于 3
    并且 每个声明数据源恰好采集 1 次
