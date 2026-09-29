# 组织设计框架 Galbraith 五维对齐框架逻辑

> 本 Skill 的分析主轴是 Galbraith Star Model 五维对齐：战略（strategy）提出方向，
> 结构（structure）配置权力，流程（processes）承载信息流，奖励（rewards）牵引行为，
> 人员（people）供给能力——五维相互对齐才构成可落地的组织设计。
> 纯内部框架型：全部判断基于用户输入的组织内部信息，无外部印证。

## 名实注记（org_structure 历史根键）

`org_structure` 为历史根键，扩展后承载 Galbraith Star Model 全五维：structure 维由
本容器三字段（functions / reporting_lines / decentralization_level）承载，
strategy / processes / rewards / people 四维由子容器承载——根键名义上的「组织结构」
不等于实际承载范围（五维全集）。

## 系统化思考步骤（编号步骤序列）

- 步骤 1 —— 锚定战略维（strategy.statements）：逐条确认战略方向陈述完整
  （业务范围 + 竞争优势来源 + 时间里程碑）——后续四维全部以此为对齐基准
- 步骤 2 —— 检验结构维（structure：functions / reporting_lines /
  decentralization_level）：职能清单是否覆盖战略所需关键活动；汇报线是否让
  战略重心有足够决策权；分权程度与战略节奏是否匹配（快节奏市场需要前线分权）
- 步骤 3 —— 检验流程维（processes.core_processes）：核心流程是否贯通战略关键
  活动（集成流）且支撑跨部门协同（管理流）；流程断点即结构失配的信号
- 步骤 4 —— 检验奖励维（rewards.incentive_policies）：激励政策是否牵引与战略
  一致的行为（考核什么就得到什么）；与分权程度联动（分权单元适合利润分享类激励）
- 步骤 5 —— 检验人员维（people.talent_measures）：人才标准与培养举措是否供给
  战略所需能力；与职能清单联动（新职能需要新人才画像）
- 步骤 6 —— 五维对齐计算：逐维读取条目维度对齐度分值，取各维参与条目的最低分
  作为该维对齐分值（维度内短板优先；strategy 维条目分值 = 陈述完备性，
  见 scoring_anchors.md 刻度声明）
- 步骤 7 —— 失配诊断与建议：对最低分维度（或并列多维）生成
  optimization_suggestions（调整该维或联动维的结构性动作），fit_assessment
  呈现五维分值与依据

## 填写指引

- 条目编码：维度对齐度分值（1-5）—— 条目描述（分值 = 首个『 —— 』之前前缀中的
  独立 1-5 整数）；「对齐」指该条目与战略维陈述的支撑程度，非条目自身好坏
  （strategy 维自身例外：其条目分值 = 陈述完备性，见 scoring_anchors.md 刻度声明）
- decentralization_level 为定性描述单值（高度集权/中度分权/高度分权），不打分，
  在步骤 2 中以定性方式参与对齐判断
- 逐条一行：模板采集表格中每条目一行，同字段多行逐条登记
- 填写顺序按步骤 1→5 序（战略先行，四维随后），评分独立于顺序

## 聚合规则

- 各维对齐分值 = 该维全部条目分值的最小值（维度内短板优先）
- fit_assessment 外层键为五维名（structure/strategy/processes/rewards/people），
  值为对齐度分值与依据
- optimization_suggestions 聚焦最低分维度；跨维联动失配（如分权与激励矛盾）
  优先登记
