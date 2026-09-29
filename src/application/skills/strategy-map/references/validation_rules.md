# 战略地图校验规则（确定性规则——分析层评估逻辑）

> 违规经输出 `strategy_visualization` 的附注与主题卡复议清单结构化呈现，
> 不映射为运行时异常 / INSUFFICIENT_DATA——结构性歧义是待澄清假设而非失败。

## 逐条编号规则（规则 1 起序）

- 规则 1 —— 箭头语法校验：causal_relationships 条目必须匹配正则
  `^(financial|customer|internal_process|learning_growth) → (financial|customer|internal_process|learning_growth)：.+`
  （「原因维度 → 结果维度：假设描述」全角冒号形态）——格式违规条目登记
  为待澄清假设，不进入 causal_arrows
- 规则 2 —— 因果链闭合校验：每条箭头首尾维度必须存在非空指标清单
  （断链即孤立节点）；未参与任何箭头的维度标记孤立维度——两者均以
  warning 级列入主题卡复议清单
- 规则 3 —— 标准方向校验（Kaplan-Norton）：因果箭头标准方向自下而上
  learning_growth → internal_process → customer → financial；逆向箭头
  （如 financial → learning_growth）或同层箭头（如 customer → customer）
  标记 warning 级待澄清假设——不硬失败，工作坊复议方向或补正表述
- 规则 4 —— 量化移交（D13 分工闭环）：因果假设的定量验证（目标值/权重/
  达成度计分）移交 bsc-scorecard——本 Skill 输出不含 KPI 量化字段，
  在 causal_arrows 附注中标注「量化验证移交 bsc-scorecard」

## 判定示例

- 合规条目：「learning_growth → internal_process：一线数字化技能提升缩短订单处理周期」
  （标准方向 + 全角冒号 + 传导机制说明）
- warning 条目：「customer → internal_process：客户反馈驱动流程改进」（逆向箭头——
  标记待澄清假设，复议后可保留为反馈回路或改写为标准方向）
- 格式违规条目：「internal_process 改善 customer 满意度」（无箭头语法——
  登记待澄清假设，补写为「internal_process → customer：…」后进入 causal_arrows）
