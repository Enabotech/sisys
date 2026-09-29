# language: zh-CN
功能: Skills 数据采集集成
  作为工具工程师
  我希望 6 个外部数据驱动型 Skills 复用 Story 4.1b 数据采集基础设施
  以便 Agent 调用这些 Skills 时自动从权威数据源获取高质量、可靠、新鲜的信息，
    LLM 基于真实数据生成结构化分析输出，无需用户手工填入数据

  背景:
    假如 数据采集基础设施已初始化
    并且 Redis 缓存服务可用

  # =========================================================================
  # AC-4: 六个外部数据型 Skills 全链路并发采集
  # =========================================================================

  场景: pestel-analysis 六源并发采集全链路
    假如 加载技能 "pestel-analysis" 的 L2 技能元数据
    并且 全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合
    并且 输出元数据含 source 与 freshness 与 confidence

  场景: porters-five-forces 三源并发采集链路
    假如 加载技能 "porters-five-forces" 的 L2 技能元数据
    并且 全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

  场景: appeals-analysis 三源并发采集链路
    假如 加载技能 "appeals-analysis" 的 L2 技能元数据
    并且 全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

  场景: competitor-analysis 四源并发采集链路
    假如 加载技能 "competitor-analysis" 的 L2 技能元数据
    并且 全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

  场景: scenario-planning 三源并发采集链路
    假如 加载技能 "scenario-planning" 的 L2 技能元数据
    并且 全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

  场景: disruptive-innovation 双源交叉验证采集链路
    假如 加载技能 "disruptive-innovation" 的 L2 技能元数据
    并且 全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

  # =========================================================================
  # AC-6: 异常路径与安全失败不变量（Edge Cases）
  # =========================================================================

  场景: 沙箱代码引用白名单外数据源安全失败
    假如 加载技能 "pestel-analysis" 的 L2 技能元数据
    并且 全部声明数据源适配器行为正常
    当 沙箱代码引用白名单外数据源 "uspto"
    那么 抛出 BusinessRuleViolationError
    并且 错误码为 EXCEPTION_207

  场景: 数据源不可用部分失败收敛
    假如 加载技能 "porters-five-forces" 的 L2 技能元数据
    并且 数据源 "eurostat" 配置为不可用，其余声明源行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 可用数据源数据已注入
    并且 已发布 DataSourceFetchFailed 事件

  场景: Key 缺失未注册降级部分失败收敛
    假如 加载技能 "appeals-analysis" 的 L2 技能元数据
    并且 数据源 "tavily" 与 "newsapi" 未注册（模拟 API Key 缺失），其余声明源行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 可用数据源数据已注入
    并且 已发布 DataSourceFetchFailed 事件

  场景: 缓存命中二次执行不重复采集
    假如 加载技能 "scenario-planning" 的 L2 技能元数据
    并且 全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记连续两次经 Engine Execute 阶段处理
    那么 第二次执行外部采集次数不增加
    并且 输出元数据 freshness 评分在 0 到 1 之间

  场景: 纯内部框架 Skill 空白名单安全失败
    假如 加载技能 "business-model-canvas" 的 L2 技能元数据
    当 含数据源标记的沙箱代码经 Engine Execute 阶段处理
    那么 抛出 BusinessRuleViolationError
    并且 错误码为 EXCEPTION_207

  场景: 多源三角化全声明源覆盖
    假如 加载技能 "competitor-analysis" 的 L2 技能元数据
    并且 全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 注入数据源数量大于等于 3
    并且 每个声明数据源恰好采集 1 次
