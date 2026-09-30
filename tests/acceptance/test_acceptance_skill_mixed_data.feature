# language: zh-CN
功能: 混合数据型 Skills 数据采集与内外数据融合

  作为工具工程师
  我想要 10 个混合数据型 Skills 基于内部数据（Schema 模板采集）与外部行业基准（2 源基线交叉，vrio 4-1f 升级三源）输出分析
  以便 Agent 调用这些 Skills 时生成可执行的结构化分析结果

  背景:
    假如 数据采集基础设施已初始化

  # =========================================================================
  # AC-1/AC-4: 外部基准采集全链路（Happy Path——2 源基线，vrio 三源）
  # =========================================================================

  场景: swot-tows 全链路双源采集与内外数据融合
    假如 加载技能 "swot-tows" 的 L2 技能元数据
    并且 该技能全部声明数据源适配器行为正常
    当 该技能携带内部数据参数执行且全部声明数据源标记经 Engine Execute 阶段处理
    那么 执行结果为成功
    并且 每个声明数据源恰好采集 1 次
    并且 输出元数据含 source 与 freshness 与 confidence

  场景: ansoff-matrix 双源采集链路
    假如 加载技能 "ansoff-matrix" 的 L2 技能元数据
    并且 该技能全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 执行结果为成功
    并且 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

  场景: value-curve-analysis 双源采集链路
    假如 加载技能 "value-curve-analysis" 的 L2 技能元数据
    并且 该技能全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 执行结果为成功
    并且 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

  场景: ge-mckinsey-matrix 双源采集链路
    假如 加载技能 "ge-mckinsey-matrix" 的 L2 技能元数据
    并且 该技能全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 执行结果为成功
    并且 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

  场景: space-matrix 双源采集链路
    假如 加载技能 "space-matrix" 的 L2 技能元数据
    并且 该技能全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 执行结果为成功
    并且 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

  场景: value-chain-analysis 双源采集链路
    假如 加载技能 "value-chain-analysis" 的 L2 技能元数据
    并且 该技能全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 执行结果为成功
    并且 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

  场景: vrio-framework 三源采集链路（专利双库 + 市场）
    假如 加载技能 "vrio-framework" 的 L2 技能元数据
    并且 该技能全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 执行结果为成功
    并且 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

  场景: bsc-scorecard 双源采集链路
    假如 加载技能 "bsc-scorecard" 的 L2 技能元数据
    并且 该技能全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 执行结果为成功
    并且 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

  场景: kpi-tree 双源采集链路
    假如 加载技能 "kpi-tree" 的 L2 技能元数据
    并且 该技能全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 执行结果为成功
    并且 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

  场景: change-management 双源采集链路
    假如 加载技能 "change-management" 的 L2 技能元数据
    并且 该技能全部声明数据源适配器行为正常
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 执行结果为成功
    并且 每个声明数据源恰好采集 1 次
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合

  # =========================================================================
  # AC-6: Edge Cases（策略违规与降级）
  # =========================================================================

  场景: 白名单外数据源标记被拒绝
    假如 加载技能 "swot-tows" 的 L2 技能元数据
    当 代码含白名单外数据源 "ipcc" 标记经 Engine Execute 阶段处理
    那么 抛出 BusinessRuleViolationError
    并且 错误码为 EXCEPTION_207

  场景: 数据源不可用部分失败收敛
    假如 加载技能 "swot-tows" 的 L2 技能元数据
    并且 数据源 "newsapi" 配置为不可用
    当 该技能全部声明数据源标记经 Engine Execute 阶段处理
    那么 执行结果为成功
    并且 已发布 DataSourceFetchFailed 事件
    并且 可用数据源数据已注入

  场景: Key 缺失降级与内部数据继续分析
    假如 加载技能 "kpi-tree" 的 L2 技能元数据
    并且 数据源 "newsapi" 未注册
    当 该技能携带内部数据参数执行且全部声明数据源标记经 Engine Execute 阶段处理
    那么 执行结果为成功
    并且 已发布 DataSourceFetchFailed 事件
    并且 可用数据源数据已注入
    并且 内部数据参数已进入规划提示词

  场景: 缓存命中二次执行不重复采集
    假如 加载技能 "swot-tows" 的 L2 技能元数据
    并且 该技能全部声明数据源适配器行为正常
    当 该技能连续两次执行全部声明数据源标记处理
    那么 第二次执行外部采集次数不增加
    并且 输出元数据 freshness 评分在 0 到 1 之间

  场景: 纯内部框架 Skill 空白名单安全失败
    假如 加载技能 "business-model-canvas" 的 L2 技能元数据
    当 代码含白名单外数据源 "world-bank" 标记经 Engine Execute 阶段处理
    那么 抛出 BusinessRuleViolationError
    并且 错误码为 EXCEPTION_207

  场景: 内外数据融合双通道并存
    假如 加载技能 "swot-tows" 的 L2 技能元数据
    并且 该技能全部声明数据源适配器行为正常
    当 该技能携带内部数据参数执行且全部声明数据源标记经 Engine Execute 阶段处理
    那么 内部数据参数已进入规划提示词
    并且 注入代码前缀含 DATA_SOURCES 字典
    并且 注入 DATA_SOURCES 字典键集合等于声明数据源集合
