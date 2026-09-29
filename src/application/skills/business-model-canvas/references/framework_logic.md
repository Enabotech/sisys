# 商业模式画布九块联动框架逻辑

> 本 Skill 的分析主轴是九块联动：客户侧四块（customer_segments /
> channels / customer_relationships / revenue_streams）与供给侧五块
> （value_propositions / key_activities / key_resources / key_partnerships /
> cost_structure）以价值创造-传递-获取链条贯通。纯内部框架型：全部判断
> 基于用户输入的内部业务信息。

## 系统化思考步骤（编号步骤序列）

- 步骤 1 —— 界定客户细分（customer_segments）：逐块锚定目标客群与付费主体
  （分群维度 + 规模量级），客户细分是九块的起点
- 步骤 2 —— 提炼价值主张（value_propositions）：对每个客户细分陈述价值主张
  （痛点回应 + 差异化）；核心匹配检验 value_propositions ↔ customer_segments——
  每条主张必须指向至少一个细分，每个细分至少被一条主张覆盖
- 步骤 3 —— 铺设触达与关系（channels / customer_relationships）：渠道覆盖
  细分触达路径（认知/评估/购买/交付/售后五阶段），关系类型匹配客户行为模式
- 步骤 4 —— 配置供给能力（key_activities / key_resources / key_partnerships）：
  关键业务支撑价值主张兑现（KA→VP），核心资源支撑关键业务（KR→KA），
  重要伙伴补齐自建缺口（外部能力获取）
- 步骤 5 —— 对称双侧核算（revenue_streams / cost_structure）：收入来源与
  各客户细分对应（谁为谁付费）；成本结构与收入结构对称——成本-收入对称检验
  cost_structure ↔ revenue_streams（高价值主张配高成本结构的正当性论证）
- 步骤 6 —— 分块成熟度评估：按 scoring_anchors.md 的 1-5 刻度逐块评定
  成熟度（块的描述完备性 + 论证充分性），聚合为 dimension_scores
- 步骤 7 —— 块间一致性诊断：生成 consistency_analysis——核心匹配缺口
  （无主张覆盖的细分 / 无细分指向的主张）+ 成本-收入失衡（收入依赖单源而
  成本刚性）+ 供给缺口（主张无关键业务支撑）

## 填写指引

- 条目编码：块成熟度分值（1-5）—— 条目描述（分值 = 首个『 —— 』之前前缀中的
  独立 1-5 整数，前缀不得含其它数字）
- 逐条一行：模板采集表格中每条目一行，同块多行逐条登记
- cost_structure 为自由 object：外层键为成本项名，值为成本说明（占比/性质），
  不逐条打分——其成熟度由关键成本项描述完备性整体评定
- 九块填写顺序：步骤 1→5 序（客户细分起步、双侧核算收尾），禁止跳块填写
  （后续块依赖前序块的锚定）

## 聚合规则

- dimension_scores：九块逐块 1-5 分值与依据（cost_structure 整体评定）
- consistency_analysis：核心匹配（value_propositions ↔ customer_segments）
  与成本-收入对称（cost_structure ↔ revenue_streams）双侧对照 + 供给链检验
- 关键连接校验可复用 scripts/validate_canvas.py 的 CRITICAL_LINKS
  （VP↔CS / VP↔CR / KA→VP / KR→KA / CH→CS 五条）
