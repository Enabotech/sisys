# 战略地图四层因果假设框架逻辑

> 本 Skill 的分析主轴是「BSC 四维度自下而上的定性因果传导」：learning_growth
> （学习与成长）→ internal_process（内部流程）→ customer（客户）→ financial
> （财务）。纯内部框架型：因果假设基于管理层的战略判断，无外部印证。

## 系统化思考步骤（编号步骤序列）

- 步骤 1 —— 四维度指标梳理：从 bsc_indicators 的四个维度清单
  （learning_growth / internal_process / customer / financial）逐条确认指标
  陈述完整（指标名 + 现状量级，如「营业收入 = 4.2 亿元，年增 12%」）——
  指标是因果链的节点素材
- 步骤 2 —— 因果假设表述：对每对候选维度按因果箭头语法「原因维度 → 结果维度：
  假设描述」表述（causal_relationships 条目）——假设描述须说明传导机制
  （为什么前者能改善后者），不止于相关关系
- 步骤 3 —— 因果链闭合检查：验证每条箭头首尾维度均有指标支撑（断链即孤立
  节点）；识别未参与任何箭头的维度（孤立维度）与多入度汇聚点——完整性问题
  以 warning 级呈现，不否定输入
- 步骤 4 —— 战略主题卡设计：将闭合的因果链归纳为 2-4 张主题卡（theme_cards
  ——主题名 / 涉及维度 / 假设链），每张卡是一条「自下而上」的完整传导故事线

## 与 bsc-scorecard 互查映射（两 Skill 互相负向跳转，键名与语义分工不同）

两个工具同源于 BSC 四维度框架，**输入键与输出语义非对称**：

| strategy-map（定性因果链） | bsc-scorecard（定量计分卡） | 映射说明 |
| --- | --- | --- |
| input 键 `bsc_indicators`（四维度指标 + causal_relationships 因果假设） | input 键 `strategic_objectives`（四维度战略目标，无因果假设字段） | 键名分工：strategy-map 锚 bsc_indicators，bsc-scorecard 锚 strategic_objectives——两 Skill 互查时先核对键名，禁止混用 |
| 输出 `strategy_visualization`（nodes / causal_arrows / theme_cards——定性因果链图） | 输出 `bsc_metrics`（kpi_indicators / target_values / weights——定量 KPI 计分卡） | 输出语义：因果链可视化 vs KPI 目标值与权重 |
| 因果假设仅定性表述（假设描述文本） | 因果链经权重与目标值量化（达成度可计分） | strategy-map 的箭头假设是 bsc-scorecard 权重分配的依据来源 |

> 传递规则：定性因果链先行、量化验证移交 bsc-scorecard——先用 strategy-map
> 对齐传导逻辑（为什么），再用 bsc-scorecard 定目标值与权重（多少）；两 Skill
> 同用时因果假设矛盾以 strategy-map 侧复议为准，量化口径以 bsc-scorecard 侧为准。

## 填写指引

- 四维度清单条目编码：指标陈述（指标名与现状量级，如「订单处理周期 = 5.2 天」）
- causal_relationships 条目编码：因果箭头语法「原因维度 → 结果维度：假设描述」
  （全角冒号；标准方向自下而上 learning_growth → internal_process →
  customer → financial——Kaplan-Norton）
- 逐条一行：模板采集表格中每条指标/因果假设一行，同字段多行逐条登记
- 逆向或同层箭头（如 customer → internal_process）允许登记但会标记 warning
  级待澄清假设——工作坊复议方向或补正表述，不硬失败
