---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics']
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - _bmad-output/planning-artifacts/mvp-implementation-plan.md
workflowType: 'epics-and-stories'
projectName: 'sisys'
userName: 'Agimtech'
date: '2026-02-26'
documentStatus: 'epics-approved'
---

# sisys - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for **sisys** (企业战略规划管理系统), decomposing the requirements from the PRD, UX Design, Architecture requirements, and MVP Implementation Plan into implementable stories.

---

## Requirements Inventory

### Functional Requirements

**总计 122 项功能需求（P0: 87 项，P1: 17 项，P2: 18 项）**

#### 1. 文档与数据管理（DM - 15 项）

**P0（MVP 必需 - 10 项）：**
- **DM-01 (P0):** 用户可以上传 17 种格式的文档（pdf/txt/doc/docx/ppt/pptx/xls/xlsx/csv/jpeg/png/gif/markdown/html + zip/tar 压缩包）
- **DM-02 (P0):** 系统可以解析上传文档并提取文本、表格、图像、公式内容
- **DM-03 (P0):** 系统可以保留文档版面信息（元素坐标 x, y, width, height），采用 DocLayNet 标准格式
- **DM-04 (P0):** 系统可以提取表格的行列语义，输出包含表头与列类型的结构化 JSON
- **DM-05 (P0):** 系统可以对扫描件或图像 PDF 进行 OCR 解析（中/英），提取置信度并标注
- **DM-06 (P0):** 用户可以创建文档版本快照，系统记录操作者、时间戳与差异摘要
- **DM-07 (P0):** 系统可以校验入库文档的最小元字段集（creator/created_at/source/license/business_domain）
- **DM-08 (P0):** 用户可以追溯每个解析后的数据切片至导入批次与原始文件版本
- **DM-09 (P0):** 系统可以对文档进行语义分块，基于文档语义边界而非固定字数切片
- **DM-10 (P0):** 系统可以执行环境预检（GPU 驱动/CUDA 版本/内存），仅异常时通知用户

**P1（V1 增加 - 3 项）：**
- **DM-11 (P1):** 系统可以识别数学公式并输出 LaTeX 与 MathML 双格式表达
- **DM-12 (P1):** 系统可以实现图文联合嵌入空间，支持"以图搜文/以文搜图"的跨模态检索
- **DM-13 (P1):** 用户可以导入季度/年度经营复盘数据，用于计算与规划的偏差

**P2（V2 增加 - 2 项）：**
- **DM-14 (P2):** 系统可以支持音视频转录文本接入
- **DM-15 (P2):** 系统可以支持合并单元格语义还原与跨页表格识别

#### 2. 智能检索与知识发现（SR - 15 项）

**P0（MVP 必需 - 13 项）：**
- **SR-01 (P0):** 系统可以执行混合检索（Dense bge-m3 + BM25 稀疏检索），双路召回
- **SR-02 (P0):** 系统可以抽取实体（LLM+ 规则混合策略），输出三元组
- **SR-03 (P0):** 系统可以管理战略领域词典库，支持热更新与版本管理
- **SR-04 (P0):** 系统可以对齐与消歧实体（基于编辑距离 + 语义相似度双路匹配）
- **SR-05 (P0):** 系统可以融合三路检索结果（Dense + Sparse + Graph/metadata signals），使用 RRF 融合排序
- **SR-06 (P0):** 系统可以执行分层检索（L1 跨文档摘要→L2 文档摘要→L3 文档切片→L4 实体级片段）
- **SR-07 (P0):** 系统可以根据查询复杂度与意图自动路由至对应检索层级
- **SR-08 (P0):** 系统可以生成契约化结构化摘要（财务/市场/技术视角），输出符合预定义 JSON Schema
- **SR-09 (P0):** 系统可以评估摘要质量（信息熵 + 关键实体覆盖率），评分<0.7 自动触发二次生成
- **SR-10 (P0):** 系统可以评估检索相关性（LLM-as-a-Judge 实时多维评估），相关性<0.6 标注"数据不足"
- **SR-11 (P0):** 系统可以触发自动补救机制（扩展检索范围/调用白名单外部数据源/生成数据缺口报告）
- **SR-12 (P0):** 系统可以保留引文"三元组"特征（文档 ID、切片 ID、字符范围），支持 Bounding Box 级溯源
- **SR-13 (P0):** 系统可以管理引用数据的时效性，超 12 个月数据自动标记"数据陈旧"并降权

**P2（V2 增加 - 2 项）：**
- **SR-14 (P2):** 系统可以构建知识图谱（实体节点 + 关系边），支持 GraphRAG 增强检索
- **SR-15 (P2):** 系统可以执行实体关联查询、路径查询、社区发现算法（Louvain/Label Propagation）

#### 3. 战略工具箱（ST - 11 项）

**P0（MVP 必需 - 7 项）：**
- **ST-01 (P0):** 系统可以注册战略工具（23 种：PESTEL/波特五力/$APPEALS/竞争对手分析/价值链分析/VRIO/安索夫矩阵/SWOT-TOWS/GE-麦肯锡矩阵/SPACE 矩阵/情景规划/价值曲线分析/价值主张画布/商业模式画布/破坏性创新模型/BSC/战略地图/组织设计框架/依赖关系图/RACI 矩阵/甘特图/KPI/变革管理模型）
- **ST-02 (P0):** 系统可以管理工具版本，支持版本控制、灰度发布与回滚
- **ST-03 (P0):** 系统可以编排工具链（DAG 有向无环图），按拓扑顺序调度子任务
- **ST-04 (P0):** 系统可以验证工具输入/输出 Schema（Pydantic V2 契约化）
- **ST-05 (P0):** 系统可以在 Docker 沙箱中执行工具代码，网络隔离 + 权限最小化
- **ST-06 (P0):** 系统可以执行 Validation Feedback 闭环（最大重试 3 次，失败标记不可行）
- **ST-07 (P0):** 系统可以遵循 MCP 2025 规范与 A2A 协议，通过 MCP Registry 暴露工具能力

**P1（V1 增加 - 2 项）：**
- **ST-08 (P1):** 系统可以在 gVisor 沙箱中执行代码，提供用户空间内核隔离
- **ST-09 (P1):** 系统可以执行红蓝辩论机制（激进派 vs 保守派，最多 7 轮，三阶段）

**P2（V2 增加 - 2 项）：**
- **ST-10 (P2):** 系统可以支持压力测试建模（宏观经济变量情景分析）
- **ST-11 (P2):** 系统可以支持财务建模与估值（DCF/可比公司/先例交易）

#### 4. Agent 协作（AC - 16 项）

**P0（MVP 必需 - 14 项）：**
- **AC-01 (P0):** 系统可以实例化 Agent 角色（7 种核心：CEO/COO/CMO/CTO/CFO/CHO/AUD + SYS Agent）
- **AC-02 (P0):** 系统可以加载 Agent 身份档案（IDENTITY.md/CODE.md/SOUL.md/TOOLS.md/USER.md/MEMORY.md/HEARTBEAT.md）
- **AC-03 (P0):** 系统可以执行单 Agent 任务（感知→规划→执行→验证→反思→证据打包）
- **AC-04 (P0):** 系统可以分解多 Agent 协作任务（SYS Agent 解析目标并分解，各专业 Agent 并行执行）
- **AC-05 (P0):** 系统可以生成协作依赖图（基于 BLM/BEM 阶段）
- **AC-06 (P0):** 系统可以执行弹性视角隔离协议（L4 硬隔离/L3 软隔离/L2 协作态/L1 融合态）
- **AC-07 (P0):** 系统可以动态调整隔离等级（基于任务依赖/关键词频率/SYS Agent 命令）
- **AC-08 (P0):** 系统可以创建联合分析组，相关 Agent 隔离等级降级至 L2 协作态
- **AC-09 (P0):** 系统可以通过公共黑板交换中间结论（附带置信度与引用源）
- **AC-10 (P0):** 系统可以执行 SYS Agent 裁决（最大辩论轮次 3+ 风险等级，上限 7 轮）
- **AC-11 (P0):** 系统可以生成三套方案（Plan A 保守/Plan B 激进/Plan C AI 融合版）
- **AC-12 (P0):** 系统可以强制暂停 5 分钟请求用户介入，超时无操作按 SYS Agent 决策执行
- **AC-13 (P0):** 系统可以保证 Agent 默认隔离等级为 L4 硬隔离（Prompt/工具/数据三重硬隔离）
- **AC-14 (P0):** 系统可以记录隔离切换日志（AGENT ID、时间戳、原隔离等级、目标隔离等级、触发原因、审批链）

**P2（V2 增加 - 2 项）：**
- **AC-15 (P2):** 系统可以执行深度思考与多路径推演（并行生成多条思维链）
- **AC-16 (P2):** 系统可以支持 Agent 实例池化与动态扩缩容（基于负载自动伸缩）

#### 5. 战略规划流程（SP - 12 项）

**P0（MVP 必需 - 7 项）：**
- **SP-01 (P0):** 系统可以执行 BLM 六阶段流程（业绩差距分析→市场洞察六子步骤→战略意图与目标→创新焦点→业务设计→执行设计）
- **SP-02 (P0):** 系统可以执行业绩差距分析（CFO Agent 主导财务差距量化，COO Agent 主导运营差距分析）
- **SP-03 (P0):** 系统可以执行市场洞察六子步骤（看趋势/看市场与客户/看竞争/看自己/看机会/机会差距分析）
- **SP-04 (P0):** 系统可以创建 Checkpoint 快照（阶段标识、完成状态、用户反馈、修正记录）
- **SP-05 (P0):** 系统可以执行 Replay 重放模式（修改点后所有状态重新计算，强一致性）
- **SP-06 (P0):** 系统可以评估修改影响范围（≥2 个后续 Checkpoint 强制 Replay，<2 个推荐 Override）
- **SP-07 (P0):** 系统可以输出 JSON 思维链（Input→<Reflection>→<Tools_Used>→<Constraints_Check>→JSON）

**P1（V1 增加 - 4 项）：**
- **SP-08 (P1):** 系统可以执行 Override 覆盖模式（仅修改指定状态，需人工确认一致性风险）
- **SP-09 (P1):** 系统可以执行 Time-travel 两阶段能力（单点恢复/分支对比）
- **SP-10 (P1):** 系统可以执行 BEM 六阶段流程（澄清战略方向→导出战略举措→导出衡量指标→确定年度措施→分解目标→导出重点工作计划）
- **SP-11 (P1):** 系统可以将 SP 输出结构化映射为 BP 输入（战略解码器）

**P2（V2 增加 - 1 项）：**
- **SP-12 (P2):** 系统可以支持红蓝辩论机制完整实现（发散 Temperature=0.8→收敛 Temperature=0.5→裁决 Temperature=0.2）

#### 6. 用户交互与报告（UI - 13 项）

**P0（MVP 必需 - 7 项）：**
- **UI-01 (P0):** 用户可以通过 CLI 执行命令（文档上传/Agent 调用/规划生成/Checkpoint 恢复）
- **UI-02 (P0):** 系统可以通过 REST API 提供接口（文档管理/工具调用/Agent 协作/规划生成/系统管理）
- **UI-03 (P0):** 系统可以通过 API Gateway 统一入口处理所有外部请求（统一认证/限流/路由/安全控制）
- **UI-04 (P0):** 系统可以生成多格式报告（PDF/Markdown），包含可点击的引文索引
- **UI-05 (P0):** 用户可以查看 Checkpoint 摘要并修正关键参数后恢复运行
- **UI-06 (P0):** 系统可以可视化展示决策过程（关键决策路径和依据）
- **UI-07 (P0):** 系统可以展示溯源树（从结论逐层展开至原始数据）

**P1（V1 增加 - 4 项）：**
- **UI-08 (P1):** 系统可以创建/切换/删除分支，提供分支差异对比视图
- **UI-09 (P1):** 系统可以展示 Checkpoint 恢复模式选择界面（影响范围、推荐模式、风险提示）
- **UI-10 (P1):** 系统可以支持无障碍设计（WCAG 2.1 AA，键盘导航，屏幕阅读器兼容）
- **UI-11 (P1):** 系统可以支持多语言界面（中文/英文切换）

**P2（V2 增加 - 2 项）：**
- **UI-12 (P2):** 系统可以支持高管简化视图（仪表盘/审批中心/审计摘要）
- **UI-13 (P2):** 系统可以支持决策影响分析（Shapley 贡献值，反事实推理）

#### 7. 系统管理与合规（SC - 14 项）

**P0（MVP 必需 - 9 项）：**
- **SC-01 (P0):** 系统可以管理用户认证与 RBAC 权限（用户表/角色表/权限表/关联表）
- **SC-02 (P0):** 系统可以记录统一审计日志（log_id/timestamp/actor/action_type/target_resource/old_value/new_value）
- **SC-03 (P0):** 系统可以将审计日志写入不可变存储（WORM），保留期限 7 年
- **SC-04 (P0):** 系统可以按时间/角色/任务类型/修正级别多维检索审计日志
- **SC-05 (P0):** 系统可以执行修正分级判定（L0 拼写/格式/L1 参数/权重/L2 约束/L3 假设/逻辑/战略）
- **SC-06 (P0):** 系统可以自动固化 L0/L1 级修正（生成 Few-Shot 样本→Strat-Bench 测试→版本注册→WORM 存储）
- **SC-07 (P0):** 系统可以执行数据主权隔离（敏感数据本地优先，外部网络调用需审计与白名单批准）
- **SC-08 (P0):** 系统可以对敏感数据脱敏（个人可识别信息、商业机密）
- **SC-09 (P0):** 系统可以支持等保 2.0 三级要求（身份鉴别/访问控制/安全审计/入侵防范/数据完整性/备份恢复）

**P1（V1 增加 - 2 项）：**
- **SC-10 (P1):** 系统可以执行 L2 级修正专家确认（1 人，4 小时 SLA，紧急通道 1 小时）
- **SC-11 (P1):** 系统可以执行 L3 级修正委员会审批（≥3 人，48 小时 SLA）

**P2（V2 增加 - 3 项）：**
- **SC-12 (P2):** 系统可以支持 SOX 合规（404 条款内部控制评估报告）
- **SC-13 (P2):** 系统可以支持 ISO 27001 认证（信息安全管理体系）
- **SC-14 (P2):** 系统可以支持银保监会规范（1104 报表/EAST 报表生成）

#### 8. 成本与性能优化（CP - 12 项）

**P0（MVP 必需 - 10 项）：**
- **CP-01 (P0):** 系统可以执行统一动态模型路由框架（UDMR）三层决策（L1 合规性过滤→L2 任务复杂度评估→L3 路由决策执行）
- **CP-02 (P0):** 系统可以基于四因子评分路由（语义匹配 35% + 历史成功率 30% + 成本效率 20% + 任务复杂度 15%）
- **CP-03 (P0):** 系统可以记录路由决策日志（任务 ID、时间戳、L1 结果、L2 各因子评分、最终评分、选定路由、成本、延迟）
- **CP-04 (P0):** 系统可以执行三级成本熔断（任务级/会话级/系统级）
- **CP-05 (P0):** 系统可以预测任务成本（基于历史相似任务），偏差超阈值触发分级预警
- **CP-06 (P0):** 系统可以执行语义缓存（相似度>0.9 直接返回缓存结果）
- **CP-07 (P0):** 系统可以管理缓存失效（TTL 24 小时 + 事件驱动失效 + 版本感知失效）
- **CP-08 (P0):** 系统可以检测性能漂移（CUSUM 算法，滑动窗口 7 天）
- **CP-09 (P0):** 系统可以提供健康度仪表盘（实时可视化各 Agent 健康度指标）
- **CP-10 (P0):** 系统可以输出 OpenTelemetry Trace（自适应采样，错误率>1% 时全采样）

**P2（V2 增加 - 2 项）：**
- **CP-11 (P2):** 系统可以执行区块链哈希链（审计日志不可篡改增强）
- **CP-12 (P2):** 系统可以提供 UEBA 用户行为分析（高级威胁检测）

#### 9. 战略档案库与长期记忆（SA - 10 项）

**P0（MVP 必需 - 6 项）：**
- **SA-01 (P0):** 系统可以永久存储历年 SP/BP 的关键假设变量、决策依据、实际执行偏差
- **SA-02 (P0):** 系统可以管理事实有效期标签（valid_from/valid_until）
- **SA-03 (P0):** 系统可以查询时间轴演进（按时间范围查询历史决策）
- **SA-04 (P0):** 系统可以执行数据陈旧标记（超 12 个月自动降权）
- **SA-05 (P0):** 系统可以执行心跳机制（周期性自动唤醒，检查待办事项、偏差预警、周期性任务）
- **SA-06 (P0):** 系统可以发布战略偏差预警事件（偏差超阈值 10% 自动触发）

**P1（V1 增加 - 2 项）：**
- **SA-07 (P1):** 系统可以管理分支（主线/分支差异对比、分支合并/放弃）
- **SA-08 (P1):** 系统可以主动推送知识更新（检测到行业报告/市场数据/政策法规更新时）

**P2（V2 增加 - 2 项）：**
- **SA-09 (P2):** 系统可以支持群体智能（多企业匿名数据学习，提升战略建议质量）
- **SA-10 (P2):** 系统可以支持预测性战略预警（基于市场数据的主动预警）

#### 10. 架构约束（AR - 4 项）

**P0（MVP 必需 - 4 项）：**
- **AR-01 (P0):** 系统可以保证领域层不依赖任何外部框架（仅依赖 Python 标准库与领域模型）
- **AR-02 (P0):** 系统可以发布领域事件至事件总线，支持事件重放与失败重试
- **AR-03 (P0):** 系统可以执行跨存储事务（Saga 模式/事件溯源），保证最终一致性
- **AR-04 (P0):** 系统可以通过仓储模式向领域层提供统一存储接口（领域层不直接依赖具体存储实现）

---

### Non-Functional Requirements

**总计 39 项非功能需求（P0: 29 项，P1: 9 项，P2: 1 项）**

#### 性能（Performance - 7 项）

- **NFR-PERF-01 (P0):** 检索延迟 P95 <500ms（分级预算：初检 200ms + 精排 250ms + 融合 50ms）
- **NFR-PERF-02 (P0):** 路由决策延迟 P95 <50ms（UDMR 三层决策）
- **NFR-PERF-03 (P0):** 报告生成时间 <30 秒（标准报告），<2 分钟（完整 SP/BP 报告）
- **NFR-PERF-04 (P0):** 并发 Agent 会话支持 MVP≥10，V1≥50，V2≥200，延迟 P95<2s
- **NFR-PERF-05 (P0):** Checkpoint 恢复时间 <60 秒（Replay 模式），<30 秒（Override 模式）
- **NFR-PERF-06 (P0):** 语义缓存命中率 >40%，Token 消耗降低 40-50%
- **NFR-PERF-07 (P0):** 图遍历查询延迟 P95 <200ms（简单查询），<800ms（复杂图遍历）

#### 安全性（Security - 7 项）

- **NFR-SEC-01 (P0):** 数据传输加密 TLS 1.3，SSL Labs A+ 评级
- **NFR-SEC-02 (P0):** 数据存储加密 AES-256，加密审计通过
- **NFR-SEC-03 (P0):** 渗透测试无高危漏洞，中危漏洞<5 个
- **NFR-SEC-04 (P0):** 数据泄露事件 0 事件
- **NFR-SEC-05 (P0):** 提示注入检测准确率 ≥95%（ShieldCortex），误报率<5%
- **NFR-SEC-06 (P0):** RBAC 权限测试 100% 通过，越权访问 0 次
- **NFR-SEC-07 (P0):** 沙箱逃逸测试 0 次逃逸成功

#### 合规性（Compliance - 8 项）

- **NFR-COMP-01 (P0):** 等保 2.0 三级通过公安部指定测评机构测评，MVP 发布前 1 个月完成，无高风险项
- **NFR-COMP-02 (P0):** 审计日志保留 7 年 WORM 存储，不可篡改，Object Lock COMPLIANCE 模式
- **NFR-COMP-03 (P0):** 数据主权数据境内存储 100%，跨境传输审批率 100%
- **NFR-COMP-04 (P0):** 隐私保护（PIPL）个人信息脱敏率 100%，删除请求响应<24 小时
- **NFR-COMP-05 (P0):** 审计日志完整性 100%，日志审计工具验证通过
- **NFR-COMP-06 (P1):** SOX 404 条款（V1）通过第三方审计，内部控制无重大缺陷
- **NFR-COMP-07 (P1):** ISO 27001（V1）通过认证，ISMS 运行有效
- **NFR-COMP-08 (P2):** 银保监会规范（V2）1104 报表/EAST 报表生成准确率 100%

#### 可靠性（Reliability - 6 项）

- **NFR-REL-01 (P0):** 系统可用性 99.9%（年停机时间<8.76 小时）
- **NFR-REL-02 (P0):** 数据备份每日全量 + 实时增量，RPO<1 小时
- **NFR-REL-03 (P0):** 灾难恢复 RTO<4 小时，异地灾备，季度演练成功率 100%
- **NFR-REL-04 (P0):** Checkpoint 快照持久化 100% 持久化，故障恢复成功率≥99%
- **NFR-REL-05 (P0):** 性能漂移检测 CUSUM 算法检测连续性能下降（滑动窗口 7 天），检测准确率≥85%
- **NFR-REL-06 (P0):** 成本熔断三级熔断触发准确率 100%，成本超支 0 事件

#### 可扩展性（Scalability - 4 项）

- **NFR-SCALE-01 (P1):** 用户增长支持 10 倍用户增长（100→1000→10000 用户），性能下降<10%
- **NFR-SCALE-02 (P1):** 数据量支持 TB 级战略档案库，检索延迟 P95<1s
- **NFR-SCALE-03 (P1):** Agent 动态扩缩容基于负载自动伸缩，响应时间<5 分钟
- **NFR-SCALE-04 (P0):** 多租户隔离 Schema per Tenant + Row-Level Security，隔离测试 100% 通过

#### 集成性（Integration - 5 项）

- **NFR-INT-01 (P0):** API 可用性 ≥99%，OpenAPI 3.1 规范，自动生成文档/SDK/Mock 服务
- **NFR-INT-02 (P1):** 预置集成适配器 ≥5 个（ERP/CRM/OA 各至少 1 个）
- **NFR-INT-03 (P1):** 外部数据源接入 ≥3 个（工商/税务/专利等）
- **NFR-INT-04 (P0):** 集成失败率 <1%，失败自动重试（最多 3 次），重试成功率≥80%
- **NFR-INT-05 (P0):** MCP/A2A 协议兼容性向后兼容 1-2 个版本，协议兼容性测试通过

#### 可访问性（Accessibility - 2 项）

- **NFR-ACC-01 (P1):** 无障碍设计 WCAG 2.1 AA 标准，键盘导航 100% 支持，屏幕阅读器兼容
- **NFR-ACC-02 (P1):** 多语言支持中文/英文界面，翻译准确率≥95%，术语表统一

---

### Additional Requirements

#### 来自 Architecture.md 的附加技术要求

**Starter Template（绿色田野模板）：**
- 采用领域驱动六边形架构（DDD Hexagonal Architecture）
- 双核引擎架构：Prefect（确定性数据管道）+ LangGraph（认知推理）
- 五层存储架构：Redis（L1 缓存）、PostgreSQL（L2 关系）、Qdrant（L3 向量）、MinIO（L4 对象）、Neo4j（L5 图）
- 双通道事件总线：Redis 发布/订阅（实时）+ RabbitMQ（持久化）

**基础设施和部署要求：**
- Docker Compose 开发环境（PostgreSQL/Redis/RabbitMQ/Qdrant/Neo4j/MinIO）
- Kubernetes 生产部署（MVP 阶段可使用 Docker Swarm）
- Prometheus + Grafana 监控栈
- ELK 日志系统

**集成要求：**
- MCP 2025 协议 + A2A 协议支持
- REST API（OpenAPI 3.1 规范）
- CLI 接口（click 框架）
- OAuth 2.1 + JWT 认证

**监控和日志要求：**
- OpenTelemetry Trace（自适应采样）
- CUSUM 性能漂移检测（滑动窗口 7 天）
- 三级成本熔断（任务级/会话级/系统级）
- 健康度仪表盘（实时可视化各 Agent 健康度）

#### 来自 UX Design Specification 的附加 UX 要求

**核心定义性体验：**
- 高保真溯源（Bounding Box 坐标级跳转，响应<300ms，定位准确率≥95%）
- 高管仪表盘（30 秒理解率≥90%，第一屏只显示 3 个关键指标）
- 财务量化可视化（NPV/IRR/敏感性分析龙卷风图）

**设计系统：**
- Ant Design 5.x + CSS-in-JS + Design Tokens
- 品牌模板系统（支持白标输出）
- 三视图设计（高管视图/分析师视图/企业战略与市场人员视图）

**关键 UX 模式：**
- 悬浮弹窗溯源卡片（不跳转新页面，保持上下文）
- 红/黄/绿状态指示器（高管仪表盘）
- 多 Agent 时间线可视化
- BLM 六阶段进度条

#### 来自 MVP Implementation Plan 的实施约束

**MVP 范围（12 周/8 周）：**
- 单 Agent 执行（CEO Agent）
- 基础 RAG 检索（Dense+Sparse 混合检索）
- BLM 部分阶段（业绩差距分析→市场洞察）
- Checkpoint 机制（Replay 模式）
- 基础审计日志（PostgreSQL 存储）
- 文档上传解析（17 种格式）
- 基础多租户（Basic tier，Row-Level 隔离）
- 白标输出基础（3 种预设主题）

**技术指标（P0 级）：**
- 检索延迟 P95: <800ms
- 系统可用性：99%
- 修正分级准确率：≥80%
- 审计追踪完整性：100%
- 合规检查通过率：100%

**团队组成（AI 原生开发模式）：**
- 1 人 + 4~8 个 Qwen Code Agent 并行
- 领域层 Agent（1-2 个）
- 基础设施层 Agent（1-2 个）
- 测试 Agent（1-2 个）
- 文档 Agent（1 个）
- 审查 Agent（1 个）

---

### FR Coverage Map

**功能需求与 or.md 溯源对照：**

| 能力领域 | FR 数量 | or.md 章节 | 覆盖率 |
|---------|--------|-----------|-------|
| 文档与数据管理（DM） | 15 | 二.1-二.2 | 100% |
| 智能检索与知识发现（SR） | 15 | 二.3-二.7 | 100% |
| 战略工具箱（ST） | 11 | 三.1-三.10 | 100% |
| Agent 协作（AC） | 16 | 四.1-四.15 | 100% |
| 战略规划流程（SP） | 12 | 五.1-五.10 | 100% |
| 用户交互与报告（UI） | 13 | 六.1-六.14 | 100% |
| 系统管理与合规（SC） | 14 | 七.1-七.6 | 100% |
| 成本与性能优化（CP） | 12 | 二.12-二.13 | 100% |
| 战略档案库与长期记忆（SA） | 10 | 二.8, 四.10-四.14 | 100% |
| 架构约束（AR） | 4 | 八.1-八.8 | 100% |
| **总计** | **122** | - | **100%** |

---

## Epic List

**设计原则：**
1. **用户价值优先** - 每个 Epic 让用户完成有意义的事情
2. **增量交付** - 每个 Epic 独立交付价值，不依赖未来 Epic
3. **逻辑流程** - 从用户视角的自然进展
4. **FR 完整覆盖** - 所有 122 项 FR 映射到具体 Epic

---

### Epic 1: 基础设施与项目骨架

**用户价值：** 开发团队拥有可运行的 DDD 六边形架构骨架，支持后续所有功能开发

**用户成果：**
- 开发人员可以运行 `make setup` 创建项目骨架
- 领域层定义完整实体和服务接口（零外部依赖）
- 五层存储基础设施可运行（Redis/PostgreSQL/Qdrant/MinIO/Neo4j）
- Docker 开发环境一键启动

**FRs covered:** AR-01, AR-02, AR-03, AR-04, DM-10

**实施周期：** 第 1-2 周

---

### Epic 2: 文档管理与数据处理

**用户价值：** 用户可以上传 17 种格式文档，系统自动解析并保留版面信息，为战略分析提供数据基础

**用户成果：**
- 用户可以拖拽上传 17 种格式文档（PDF/Word/Excel/PPT/图像等）
- 系统自动解析文档，提取文本、表格、图像、公式
- 保留文档版面信息（DocLayNet 标准坐标）
- 支持文档版本管理和溯源

**FRs covered:** DM-01, DM-02, DM-03, DM-04, DM-05, DM-06, DM-07, DM-08, DM-09

**实施周期：** 第 2-4 周

---

### Epic 3: 智能 RAG 检索系统

**用户价值：** 用户可以执行混合检索，获得相关性排序的结果，支持 Bounding Box 级溯源至原始文档坐标点

**用户成果：**
- 系统执行 Dense+Sparse 双路召回检索
- 实体抽取和对齐，构建战略领域知识
- 分层检索（L1 跨文档摘要→L2 文档摘要→L3 文档切片→L4 实体级片段）
- Bounding Box 级溯源（响应<300ms，准确率≥95%）
- 检索相关性<0.6 自动标注"数据不足"并触发补救

**FRs covered:** SR-01, SR-02, SR-03, SR-04, SR-05, SR-06, SR-07, SR-08, SR-09, SR-10, SR-11, SR-12, SR-13

**实施周期：** 第 3-5 周

---

### Epic 4: 战略工具箱与沙箱执行

**用户价值：** 用户可以使用 13 种战略工具进行分析，工具在 Docker 沙箱中安全执行

**用户成果：**
- 系统注册 23 种战略工具（PESTEL/波特五力/SWOT-TOWS/GE 矩阵等）
- 工具版本管理（版本控制、灰度发布、回滚）
- 工具链编排（DAG 有向无环图，拓扑排序）
- Docker 沙箱执行（网络隔离、权限最小化）
- Validation Feedback 闭环（最大重试 3 次）

**FRs covered:** ST-01, ST-02, ST-03, ST-04, ST-05, ST-06, ST-07

**实施周期：** 第 4-6 周

---

### Epic 5: Agent 协作基础（单 Agent）

**用户价值：** 用户可以让 CEO Agent 独立执行战略规划任务，系统保证 Agent 隔离和安全

**用户成果：**
- 系统实例化 7 种 Agent 角色（CEO/COO/CMO/CTO/CFO/CHO/AUD）+ SYS Agent
- 加载 Agent 身份档案（IDENTITY.md/CODE.md/SOUL.md 等）
- 单 Agent 任务执行（感知→规划→执行→验证→反思→证据打包）
- Agent 默认 L4 硬隔离（Prompt/工具/数据三重隔离）
- 隔离切换日志记录

**FRs covered:** AC-01, AC-02, AC-03, AC-04, AC-05, AC-13, AC-14

**实施周期：** 第 5-7 周

---

### Epic 6: BLM 战略规划流程

**用户价值：** 用户可以执行完整的 BLM 业绩差距分析和市场洞察流程，系统自动创建 Checkpoint 支持恢复

**用户成果：**
- 执行 BLM 六阶段流程（业绩差距分析→市场洞察六子步骤）
- 业绩差距分析（CFO Agent 主导财务差距，COO Agent 主导运营差距）
- 市场洞察六子步骤（看趋势/看市场/看竞争/看自己/看机会/机会差距）
- Checkpoint 快照（阶段标识、完成状态、用户反馈）
- Replay 重放模式（修改点后重新计算，强一致性）
- 影响范围评估（≥2 个后续 Checkpoint 强制 Replay）

**FRs covered:** SP-01, SP-02, SP-03, SP-04, SP-05, SP-06, SP-07

**实施周期：** 第 6-8 周

---

### Epic 7: 用户接口（CLI + REST API）

**用户价值：** 用户可以通过 CLI 和 REST API 与系统交互，上传文档、调用 Agent、生成报告、恢复 Checkpoint

**用户成果：**
- CLI 命令（文档上传/Agent 调用/规划生成/Checkpoint 恢复）
- REST API 接口（文档管理/工具调用/Agent 协作/规划生成/系统管理）
- API Gateway 统一入口（认证/限流/路由/安全控制）
- 多格式报告生成（PDF/Markdown，含可点击引文索引）
- Checkpoint 摘要查看和参数修正
- 决策过程可视化和溯源树展示

**FRs covered:** UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07

**实施周期：** 第 5-7 周

---

### Epic 8: 系统管理与合规基础

**用户价值：** 管理员可以管理用户权限，系统记录完整审计日志满足等保 2.0 三级要求

**用户成果：**
- 用户认证与 RBAC 权限管理（用户表/角色表/权限表）
- 统一审计日志（log_id/timestamp/actor/action_type/target_resource/old_value/new_value）
- 审计日志 WORM 存储（7 年不可篡改）
- 多维审计日志检索（时间/角色/任务类型/修正级别）
- 修正分级判定（L0 拼写/格式→L3 假设/逻辑/战略）
- L0/L1 级修正自动固化（Few-Shot→Strat-Bench→WORM）
- 数据主权隔离（敏感数据本地优先）
- 敏感数据脱敏（PII/商业秘密）
- 等保 2.0 三级要求（身份鉴别/访问控制/安全审计/入侵防范/数据完整性/备份恢复）

**FRs covered:** SC-01, SC-02, SC-03, SC-04, SC-05, SC-06, SC-07, SC-08, SC-09

**实施周期：** 第 4-8 周

---

### Epic 9: 成本优化与性能监控

**用户价值：** 系统自动优化模型路由成本（本地占比≥80%），监控性能漂移和成本熔断

**用户成果：**
- UDMR 三层决策（L1 合规性过滤→L2 任务复杂度评估→L3 路由决策执行）
- 四因子评分路由（语义匹配 35% + 历史成功率 30% + 成本效率 20% + 任务复杂度 15%）
- 路由决策日志（任务 ID、时间戳、L1/L2 结果、最终评分、选定路由、成本、延迟）
- 三级成本熔断（任务级/会话级/系统级）
- 任务成本预测和偏差预警
- 语义缓存（相似度>0.9 命中，TTL 24 小时）
- 缓存失效管理（TTL + 事件驱动 + 版本感知）
- 性能漂移检测（CUSUM 算法，滑动窗口 7 天）
- 健康度仪表盘（实时可视化各 Agent 健康度）
- OpenTelemetry Trace 输出（自适应采样）

**FRs covered:** CP-01, CP-02, CP-03, CP-04, CP-05, CP-06, CP-07, CP-08, CP-09, CP-10

**实施周期：** 第 5-8 周

---

### Epic 10: 战略档案库与长期记忆

**用户价值：** 系统永久存储历年 SP/BP 的关键假设、决策依据、执行偏差，支持时间轴查询和偏差预警

**用户成果：**
- 永久存储历年 SP/BP 关键假设变量、决策依据、实际执行偏差
- 事实有效期标签管理（valid_from/valid_until）
- 时间轴演进查询（按时间范围查询历史决策）
- 数据陈旧标记（超 12 个月自动降权）
- 心跳机制（周期性自动唤醒，检查待办事项、偏差预警）
- 战略偏差预警事件（偏差超阈值 10% 自动触发）

**FRs covered:** SA-01, SA-02, SA-03, SA-04, SA-05, SA-06

**实施周期：** 第 6-8 周

---

### FR 覆盖总览

| Epic | FR 数量 | FR 列表 |
|------|--------|--------|
| Epic 1 | 5 | AR-01~AR-04, DM-10 |
| Epic 2 | 9 | DM-01~DM-09 |
| Epic 3 | 13 | SR-01~SR-13 |
| Epic 4 | 7 | ST-01~ST-07 |
| Epic 5 | 7 | AC-01~AC-05, AC-13~AC-14 |
| Epic 6 | 7 | SP-01~SP-07 |
| Epic 7 | 7 | UI-01~UI-07 |
| Epic 8 | 9 | SC-01~SC-09 |
| Epic 9 | 10 | CP-01~CP-10 |
| Epic 10 | 6 | SA-01~SA-06 |
| **总计** | **87** | **100% P0 FR 覆盖** |

---

### NFR 映射

| Epic | NFR 覆盖 |
|------|---------|
| Epic 1 | NFR-SCALE-04 |
| Epic 2 | NFR-PERF-03, NFR-SEC-02 |
| Epic 3 | NFR-PERF-01, NFR-PERF-07 |
| Epic 4 | NFR-SEC-07, NFR-INT-05 |
| Epic 5 | NFR-PERF-04, NFR-SEC-05 |
| Epic 6 | NFR-PERF-05, NFR-REL-04 |
| Epic 7 | NFR-INT-01, NFR-INT-04 |
| Epic 8 | NFR-COMP-01~COMP-05, NFR-SEC-01~SEC-06 |
| Epic 9 | NFR-PERF-02, NFR-PERF-06, NFR-REL-05~REL-06 |
| Epic 10 | NFR-REL-02~REL-03 |

---

## Epic 1: 基础设施与项目骨架

**目标：** 完成项目初始化、领域驱动六边形架构骨架、五层存储基础设置、Docker 开发环境，为后续功能开发提供技术基础。

**架构约束：**
- 领域层零依赖（仅 Python 标准库 + 领域模型）
- 六边形架构（Domain/Infrastructure/Interfaces 分层）
- 事件驱动架构（RabbitMQ + Redis 双通道）

**Starter Template：**
- DDD 六边形架构模板
- Prefect + LangGraph 双引擎集成
- OpenTelemetry 监控集成

### Story 1.1: 项目目录结构创建

As a **后端开发工程师**,
I want **创建标准的项目目录结构**,
So that **团队可以遵循统一的代码组织规范，支持六边形架构和五层存储**。

**Acceptance Criteria:**

**Given** 项目启动
**When** 运行 `make setup` 命令
**Then** 创建以下目录结构：

```
sisys/
├── src/                                                   # 源代码目录
│   ├── domain/                                            # 领域层（零外部依赖）
│   │   ├── models/       # 领域实体
│   │   ├── services/     # 领域服务接口
│   │   ├── events/       # 领域事件
│   │   ├── repositories/ # 仓储接口
│   │   └── exceptions/   # 领域异常
│   ├── application/                                       # 应用层（用例编排）
│   │   ├── services/     # 应用服务
│   │   ├── use_cases/    # 用例定义
│   │   ├── commands/     # 命令定义
│   │   ├── queries/      # 查询定义
│   │   ├── handlers/     # 处理器
│   │   └── dtos/         # 数据传输对象
│   ├── infrastructure/                                    # 基础设施层
│   │   ├── workflow/              # Prefect 工作流引擎
│   │   ├── agent_orchestration/   # LangGraph Agent 编排
│   │   ├── messaging/             # 消息总线（RabbitMQ/Redis）
│   │   ├── persistence/           # 持久化实现（五层存储）
│   │   ├── external_services/     # 外部服务适配器
│   │   ├── security/              # 安全（认证/加密/审计）
│   │   └── monitoring/            # 监控（性能/CUSUM）
│   ├── interfaces/                                      # 接口层
│   │   ├── cli/          # CLI 接口（click）
│   │   ├── api/          # REST API（FastAPI）
│   │   ├── event_driven/ # 事件驱动接口
│   │   └── adapters/     # 适配器
│   └── shared/                                          # 共享组件
│       ├── containers.py # 依赖注入容器
│       ├── config.py     # 共享配置
│       └── utils.py      # 工具函数
├── tests/                                                 # 测试目录
│   ├── unit/              # 单元测试
│   ├── integration/       # 集成测试
│   ├── e2e/               # 端到端测试
│   ├── fixtures/          # 测试固件
│   └── conftest.py        # pytest 配置
├── configs/                                               # 配置文件
│   ├── development.py     # 开发环境
│   ├── production.py      # 生产环境
│   └── testing.py         # 测试环境
├── scripts/                                               # 脚本目录
│   ├── setup_environment.py
│   ├── database/
│   └── deployment/
├── docker/                                                # Docker 配置
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.prod.yml
├── .github/workflows/                                     # GitHub Actions
│   ├── ci.yml
│   └── cd.yml
├── requirements/                                          # 依赖管理
│   ├── requirements.txt
│   ├── dev.txt
│   └── prod.txt
├── docs/                                                  # 文档目录
│   ├── architecture/
│   ├── api/
│   └── developer/
├── pyproject.toml                                         # Python 项目配置
├── .env.example                                           # 环境变量示例
├── .pre-commit-config.yaml                                # Pre-commit 配置
└── README.md                                              # 项目说明
```

**And** 目录结构通过 mypy 类型检查
**And** 包含 README.md 说明文档
**And** 包含 .gitignore 文件
**And** 包含 pyproject.toml 项目配置

### Story 1.2: 领域实体定义

As a **领域工程师**,
I want **定义核心领域实体**,
So that **领域逻辑有清晰的模型基础**。

**Acceptance Criteria:**

**Given** 领域实体定义任务
**When** 创建 `src/domain/models/` 下的实体类
**Then** 包含以下实体：

**核心业务实体（6 个）：**
- `Document`（文档实体，17 种格式支持，属性：id, title, format, version, embedding_ref, blob_ref）
- `Agent`（Agent 实体，7 角色 + SYS+AUD，属性：id, role, identity, tools, state_snapshot, isolation_level）
- `Tool`（工具实体，23 种战略工具，属性：id, name, version, input_schema, output_schema, reliability_score）
- `StrategicPlan`（SP 实体，BLM 六阶段，属性：id, plan_type, blm_stage, checkpoints, evidence_package）
- `BusinessPlan`（BP 实体，BEM 六阶段，属性：id, sp_ref, bem_stage, checkpoints, evidence_package）
- `Checkpoint`（检查点实体，双模式恢复，属性：id, stage_id, state_snapshot, recovery_mode, branch_id）

**审计日志实体（3 个）：**
- `StrategicArchive`（战略档案实体，五层存储，属性：id, metadata, embedding, blob_ref, graph_ref）
- `RoutingDecisionLog`（路由决策日志，UDMR 审计，属性：id, task_id, l1_result, l2_scores, l3_decision, worm_ref）
- `IsolationSwitchLog`（隔离切换日志，EIP 审计，属性：id, agent_id, from_level, to_level, trigger, worm_ref）

**值对象（4 个）：**
- `Embedding`（嵌入向量值对象）
- `Citation`（引用索引值对象，支持 Bounding Box 溯源）
- `Confidence`（置信度值对象）
- `Cost`（成本值对象）

**And** 所有实体通过 mypy 严格类型检查
**And** 所有实体遵循领域层零外部依赖原则（仅使用 Python 标准库）
**And** 每个实体包含领域事件发布方法
**And** 实体文件位于 `src/domain/models/` 目录下

---

### Story 1.3: 领域服务接口定义

As a **架构师**,
I want **定义领域服务接口**,
So that **领域层不依赖任何外部技术实现，遵循依赖倒置原则**。

**Acceptance Criteria:**

**Given** 领域服务接口定义任务
**When** 创建 `src/domain/services/` 下的接口
**Then** 包含以下服务接口（10 个）：

**核心业务服务（7 个）：**
- `DocumentService`（文档处理服务接口，方法：parse/extract/validate）
- `RAGService`（RAG 检索服务接口，Dense+Sparse+Graph 混合检索）
- `ToolService`（工具箱服务接口，MCP/A2A 协议支持）
- `AgentService`（Agent 协作服务接口，EIP 执行）
- `PlanningService`（规划服务接口，BLM/BEM 状态机）
- `EvaluationService`（评估服务接口，五维评估）
- `VisualizationService`（可视化服务接口，决策过程/溯源树展示）

**架构增强服务（3 个）：**
- `RoutingService`（UDMR 路由服务接口，三层决策）
- `IsolationService`（EIP 隔离服务接口，四级隔离等级）
- `CheckpointService`（Checkpoint 服务接口，双模式恢复）

**And** 所有接口仅依赖 Python 标准库
**And** 接口定义清晰的输入/输出契约（使用 Pydantic V2）
**And** 每个接口包含完整的 docstring 文档
**And** 接口文件位于 `src/domain/services/` 目录下

---

### Story 1.4: 仓储接口定义

As a **架构师**,
I want **定义仓储接口**,
So that **领域层通过统一接口访问存储，不依赖具体存储实现**。

**Acceptance Criteria:**

**Given** 仓储接口定义任务
**When** 创建 `src/domain/repositories/` 下的接口
**Then** 包含以下仓储接口（9 个）：

**核心业务仓储（7 个）：**
- `DocumentRepository`（文档仓储接口，CRUD + 版本管理）
- `AgentRepository`（Agent 仓储接口，CRUD + 状态查询）
- `ToolRepository`（工具仓储接口，CRUD + 版本控制）
- `PlanRepository`（规划仓储接口，CRUD + BLM/BEM 阶段查询）
- `CheckpointRepository`（Checkpoint 仓储接口，CRUD + 恢复模式）
- `ArchiveRepository`（战略档案仓储接口，CRUD + 时间轴查询）
- `BusinessPlanRepository`（BP 仓储接口，CRUD + SP 关联查询）

**审计日志仓储（2 个）：**
- `RoutingLogRepository`（路由日志仓储接口，CRUD + UDMR 审计查询）
- `IsolationLogRepository`（隔离日志仓储接口，CRUD + EIP 审计查询）

**And** 所有接口仅依赖 Python 标准库
**And** 接口定义 CRUD 基本操作和领域特定查询
**And** 接口使用泛型支持类型安全
**And** 接口文件位于 `src/domain/repositories/` 目录下

---

### Story 1.5: 领域事件定义

As a **领域工程师**,
I want **定义领域事件**,
So that **核心业务逻辑通过事件触发，支持事件溯源和审计**。

**Acceptance Criteria:**

**Given** 领域事件定义任务
**When** 创建 `src/domain/events/` 下的事件类
**Then** 包含以下领域事件（8 个）：

**核心业务事件（6 个）：**
- `DocumentProcessed`（文档处理完成事件，payload: document_id, format, status）
- `ToolExecuted`（工具执行完成事件，payload: tool_id, result, execution_time）
- `AgentDecided`（Agent 决策完成事件，payload: agent_id, decision, confidence）
- `CheckpointReached`（检查点到达事件，payload: stage_id, state_snapshot, user_feedback）
- `CorrectionClassified`（修正分级判定事件，payload: correction_id, level, score）
- `ArbitrationCompleted`（裁决完成事件，payload: arbitration_id, decision, confidence）

**架构增强事件（2 个）：**
- `RoutingDecided`（路由决策事件，payload: task_id, l3_decision, cost, latency）
- `IsolationLevelSwitched`（隔离等级切换事件，payload: agent_id, from_level, to_level, trigger）

**And** 所有事件继承自 `DomainEvent` 基类
**And** 事件包含标准字段（event_id, timestamp, aggregate_id, aggregate_type, payload, metadata）
**And** 事件文件位于 `src/domain/events/` 目录下

---

### Story 1.6: 领域异常定义

As a **领域工程师**,
I want **定义领域异常**,
So that **领域错误有清晰的分类和处理机制**。

**Acceptance Criteria:**

**Given** 领域异常定义任务
**When** 创建 `src/domain/exceptions/` 下的异常类
**Then** 包含以下领域异常：

**基础异常：**
- `DomainException`（基础领域异常，所有领域异常的基类）
- `EntityNotFoundException`（实体未找到异常）
- `InvalidEntityStateException`（实体状态无效异常）
- `BusinessRuleViolationException`（业务规则违反异常）

**特定异常：**
- `DocumentParseException`（文档解析异常）
- `RAGRetrievalException`（RAG 检索异常）
- `AgentExecutionException`（Agent 执行异常）
- `CheckpointRecoveryException`（Checkpoint 恢复异常）
- `RoutingDecisionException`（路由决策异常）
- `IsolationViolationException`（隔离违规异常）

**And** 所有异常继承自 `DomainException` 基类
**And** 异常包含清晰的错误消息和错误代码
**And** 异常文件位于 `src/domain/exceptions/` 目录下

---

### Story 1.7: Docker 开发环境配置

As a **开发工程师**,
I want **配置 Docker 开发环境**,
So that **团队可以一键启动五层存储基础设施进行开发**。

**Acceptance Criteria:**

**Given** Docker 开发环境配置任务
**When** 运行 `make docker-up` 命令
**Then** 启动以下容器：
- PostgreSQL 15+（关系存储层，端口 5432）
- Redis 7.0+（高速缓存层，端口 6379）
- Qdrant 1.7+（向量存储层，端口 6333）
- MinIO（对象存储层，端口 9000/9001）
- Neo4j 5.x（图存储层，端口 7687/7474）
- RabbitMQ 3.12+（消息总线，端口 5672/15672）

**And** 所有容器健康检查通过
**And** 可以通过 `docker-compose.dev.yml` 管理环境
**And** 包含数据卷持久化配置
**And** 包含 `.env` 环境变量配置示例

---

### Story 1.8: 五层存储基础设施集成

As a **基础设施工程师**,
I want **实现五层存储的仓储**,
So that **领域层可以通过仓储接口访问具体存储实现**。

**Acceptance Criteria:**

**Given** 五层存储基础设施集成任务
**When** 创建 `src/infrastructure/persistence/` 下的仓储实现
**Then** 实现以下仓储：

**PostgreSQL 仓储实现（L2）：**
- `PostgreSQLDocumentRepository`（文档仓储实现）
- `PostgreSQLAgentRepository`（Agent 仓储实现）
- `PostgreSQLToolRepository`（工具仓储实现）
- `PostgreSQLPlanRepository`（规划仓储实现）
- `PostgreSQLCheckpointRepository`（Checkpoint 仓储实现）
- `PostgreSQLRoutingLogRepository`（路由日志仓储实现）
- `PostgreSQLIsolationLogRepository`（隔离日志仓储实现）

**Redis 缓存实现（L1）：**
- `RedisCheckpointRepository`（Checkpoint 缓存实现，TTL 24h-30d）
- `RedisSemanticCache`（语义缓存实现，相似度>0.9 命中）

**Qdrant 向量存储实现（L3）：**
- `QdrantArchiveRepository`（战略档案向量存储实现）
- `QdrantEmbeddingManager`（嵌入向量管理器）

**MinIO 对象存储实现（L4）：**
- `MinIOStorageAdapter`（对象存储适配器，WORM 7 年）
- `MinIODocumentBlobStore`（文档 Blob 存储）

**Neo4j 图存储实现（L5）：**
- `Neo4jGraphRepository`（知识图谱仓储实现）
- `Neo4jEntityExtractor`（实体抽取器）

**And** 所有实现遵循领域层定义的接口
**And** 存储依赖链为单向（Cache→Relational→Vector→Object→Graph）
**And** 缓存更新通过事件总线异步执行
**And** 包含 Alembic 数据库迁移脚本

---

## Epic 2: 文档管理与数据处理

**目标：** 实现 17 种格式文档的上传、解析、版面保留、表格提取、OCR 解析、版本管理功能，为战略分析提供数据基础。

**架构约束：**
- 文档解析采用 DocLayNet 标准格式
- 表格提取输出结构化 JSON（包含表头与列类型）
- OCR 支持中文/英文，输出置信度标注
- 文档版本快照记录操作者、时间戳、差异摘要

**MVP 阶段存储策略：**
- MVP 阶段：审计日志使用 PostgreSQL 存储（L2 关系存储层）
- V1 升级：迁移至 MinIO WORM 存储（L4 对象存储层，7 年不可篡改）
- 原始文档：MVP 阶段即使用 MinIO 存储（L4 对象存储层）

### Story 2.1: 文档上传功能

As a **企业战略分析师**,
I want **上传 17 种格式的文档**,
So that **系统可以解析并构建战略分析数据基础**。

**Acceptance Criteria:**

**Given** 用户需要上传文档
**When** 通过 CLI 执行 `sisys upload --file docs.zip` 或通过 API POST /documents
**Then** 系统支持以下格式：
- 文档格式：PDF, TXT, DOC, DOCX, PPT, PPTX, HTML, Markdown
- 表格格式：XLS, XLSX, CSV
- 图像格式：JPEG, PNG, GIF
- 压缩包格式：ZIP, TAR（自动解压）

**And** 上传后返回文档 ID 和基本信息
**And** 压缩包自动解压并分别处理每个文件
**And** 上传失败时返回清晰的错误消息（格式不支持/文件损坏/超大文件）

**业务规则：**
- 单文件大小限制：≤100MB
- 压缩包大小限制：≤500MB
- 批量上传数量限制：≤50 个文件/次

**性能要求：**
- 上传响应时间：P95<500ms
- 并发上传支持：≥10 个文件/秒
- 解压速度：≥50MB/s

---

### Story 2.2: 文档解析功能

As a **文档处理工程师**,
I want **解析上传的文档并提取内容**,
So that **提取文本、表格、图像、公式用于后续分析**。

**Acceptance Criteria:**

**Given** 文档上传成功
**When** 触发文档处理流程
**Then** 系统提取以下内容：
- 文本内容（保留段落结构）
- 表格内容（行列数据）
- 图像（提取并存储）
- 公式（识别并输出 LaTeX/MathML）

**And** 解析结果存储至 PostgreSQL（元数据）和 MinIO（原始内容）
**And** 发布 `DocumentProcessed` 领域事件至 RabbitMQ 事件总线
**And** 解析状态可查询（pending/processing/completed/failed）

**业务规则：**
- PDF 解析保留页面顺序
- PPT 提取每页演讲者备注
- Excel 提取所有工作表
- 解析超时：单文档≤5 分钟

**质量要求：**
- 解析准确率：≥95%
- 文本提取完整率：≥98%
- 表格提取完整率：≥95%

---

### Story 2.3: 版面保留功能

As a **数据分析师**,
I want **保留文档版面信息**,
So that **支持高保真溯源至原始文档坐标点**。

**Acceptance Criteria:**

**Given** 文档解析完成
**When** 存储版面信息
**Then** 采用 DocLayNet 标准格式存储：
```json
{
  "page": 1,
  "bbox": {"x": 100, "y": 200, "width": 300, "height": 50},
  "label": "text|table|image|formula",
  "content_id": "uuid"
}
```

**And** 每个内容块包含坐标信息（x, y, width, height）
**And** 支持按页面查询版面信息
**And** 溯源时可根据坐标高亮显示

**性能要求：**
- 版面信息存储延迟：P95<100ms
- 坐标查询响应时间：P95<50ms

**质量要求：**
- 坐标准确率：≥95%
- 版面元素识别完整率：≥98%

---

### Story 2.4: 表格语义提取功能

As a **战略分析师**,
I want **提取表格的行列语义**,
So that **表格数据可以结构化分析**。

**Acceptance Criteria:**

**Given** 文档包含表格
**When** 执行表格提取
**Then** 输出结构化 JSON：
```json
{
  "table_id": "uuid",
  "headers": ["指标", "2023 年", "2024 年", "增长率"],
  "column_types": ["string", "number", "number", "percentage"],
  "rows": [
    {"指标": "营收", "2023 年": 1000000, "2024 年": 1200000, "增长率": 0.20}
  ],
  "source": {"document_id": "uuid", "page": 5, "bbox": {...}}
}
```

**And** 自动识别表头行
**And** 自动推断列类型（string/number/date/percentage）
**And** 合并单元格语义还原
**And** 跨页表格识别并合并

**准确率要求：**
- 表头识别准确率：≥95%
- 列类型推断准确率：≥90%
- 数据提取完整率：≥98%

---

### Story 2.5: OCR 解析功能

As a **文档管理员**,
I want **对扫描件和图像进行 OCR 解析**,
So that **扫描文档内容可以被检索和分析**。

**Acceptance Criteria:**

**Given** 上传文档为扫描件或图像
**When** 触发 OCR 处理
**Then** 系统支持：
- 中文 OCR（简体/繁体）
- 英文 OCR
- 混合语言识别

**And** 输出置信度标注（每行/每字）：
```json
{
  "text": "识别的文本",
  "confidence": 0.95,
  "bbox": {"x": 100, "y": 200, "width": 300, "height": 50}
}
```

**And** 置信度<0.7 的文字标注"低置信度"供人工复核
**And** OCR 结果与原始图像关联存储

**性能要求：**
- 单页 OCR 处理时间：≤5 秒
- 中文识别准确率：≥90%
- 英文识别准确率：≥95%

---

### Story 2.6: 文档版本管理功能

As a **战略经理**,
I want **创建文档版本快照**,
So that **可以追溯文档变更历史和差异**。

**Acceptance Criteria:**

**Given** 文档已存在
**When** 用户上传新版本或修改文档
**Then** 系统创建版本快照：
- 版本号：v1, v2, v3...（自动递增）
- 操作者：用户 ID
- 时间戳：精确到秒
- 差异摘要：新增/修改/删除的内容块数量

**And** 版本历史可查询和对比
**And** 支持回滚到任意历史版本
**And** 版本冲突检测（同时编辑时）

**业务规则：**
- 版本保留策略：最近 10 个版本永久保留，其余 30 天后合并
- 差异计算：基于文本块和版面块的 diff
- 冲突解决：后提交者收到冲突提示，需手动合并

**性能要求：**
- 版本对比响应时间：P95<200ms
- 版本回滚时间：P95<500ms

---

### Story 2.7: 文档元数据校验功能

As a **系统管理员**,
I want **校验入库文档的元数据**,
So that **确保文档数据质量和可追溯性**。

**Acceptance Criteria:**

**Given** 文档解析完成准备入库
**When** 执行元数据校验
**Then** 校验以下最小元字段集：
- `creator`：创建者（用户 ID 或系统）
- `created_at`：创建时间戳
- `source`：来源（上传/导入/外部数据源）
- `license`：许可类型（内部/保密/公开）
- `business_domain`：业务领域（战略/市场/财务/技术）

**And** 元数据缺失时拒绝入库并返回错误
**And** 元数据校验日志记录
**And** 支持元数据批量修正

**数据质量要求：**
- 元数据完整率：100%
- 校验失败率：<1%
- 校验延迟：P95<50ms

---

### Story 2.8: 文档溯源功能

As a **战略分析师**,
I want **追溯数据切片至导入批次和原始文件版本**,
So that **可以快速验证数据来源和可靠性**。

**Acceptance Criteria:**

**Given** 用户需要验证数据来源
**When** 点击溯源查询
**Then** 系统展示完整溯源链：
```
数据切片 → 文档版本 (v3) → 导入批次 (2026-02-27 10:30) → 原始文件 (market_report.pdf)
```

**And** 支持逐层展开溯源树
**And** 点击原始文件可跳转至版面坐标点
**And** 显示文档解析置信度

**性能要求：**
- 溯源查询响应时间：P95<200ms
- 溯源树展开延迟：P95<100ms

---

### Story 2.9: 文档语义分块功能

As a **RAG 工程师**,
I want **对文档进行语义分块**,
So that **检索时可以基于语义边界而非固定字数切片**。

**Acceptance Criteria:**

**Given** 文档解析完成
**When** 执行语义分块
**Then** 基于文档语义边界分块：
- 章节边界（标题/子标题）
- 段落边界
- 表格/图像边界
- 平均块大小：≈300 tokens

**And** 每个块包含语义摘要（用于检索优化）
**And** 块间重叠：50 tokens（避免边界信息丢失）
**And** 分块结果存储至 Qdrant（向量）和 PostgreSQL（元数据）

**质量要求：**
- 分块合理性评分：≥8/10（人工评审）
- 章节边界识别准确率：≥95%
- 分块处理速度：≥100 页/分钟

**存储说明：**
- Qdrant：存储文本块嵌入向量（L3 向量存储层）
- PostgreSQL：存储文本块元数据和原文（L2 关系存储层）

---

## Epic 2 Stories 完成清单

| Story | 标题 | 覆盖 FR | 状态 |
|-------|------|--------|------|
| 2.1 | 文档上传功能 | DM-01 | ✅ 完成（已补充性能要求） |
| 2.2 | 文档解析功能 | DM-02 | ✅ 完成（已补充准确率 + 事件通道） |
| 2.3 | 版面保留功能 | DM-03 | ✅ 完成（已补充坐标准确率） |
| 2.4 | 表格语义提取功能 | DM-04 | ✅ 完成 |
| 2.5 | OCR 解析功能 | DM-05 | ✅ 完成 |
| 2.6 | 文档版本管理功能 | DM-06 | ✅ 完成（已补充性能要求） |
| 2.7 | 文档元数据校验功能 | DM-07 | ✅ 完成 |
| 2.8 | 文档溯源功能 | DM-08 | ✅ 完成 |
| 2.9 | 文档语义分块功能 | DM-09 | ✅ 完成（已补充存储说明） |

---

### 审核修复清单

| 编号 | 修复项 | 修复状态 |
|------|--------|---------|
| **INC-01** | Story 2.2 补充解析准确率≥95% | ✅ 已修复 |
| **INC-02** | Story 2.3 补充坐标准确率≥95% | ✅ 已修复 |
| **INC-03** | Story 2.1/2.2/2.6 补充性能要求 | ✅ 已修复 |
| **INC-04** | Story 2.2 补充事件通道（RabbitMQ） | ✅ 已修复 |
| **INC-05** | Story 2.9 明确 Qdrant 用途 | ✅ 已修复 |
| **INC-06** | MVP 阶段 WORM 存储策略 | ✅ 已修复（Epic 2 开头补充） |

**修复后一致性评级：A (优秀)**

---

**Epic 2 完成！继续创建 Epic 3...**

---

## Epic 3: 智能 RAG 检索系统

**目标：** 实现 Dense+Sparse 混合检索、实体抽取、RRF 融合排序、高保真溯源功能，支持 Bounding Box 级溯源至原始文档坐标点。

**架构约束：**
- 混合检索：Dense (bge-m3) + Sparse (BM25) 双路召回
- 融合排序：RRF (Reciprocal Rank Fusion) + ColBERT 重排序
- 实体抽取：LLM+ 规则混合策略
- 溯源：Bounding Box 级坐标跳转

**MVP 阶段范围：**
- MVP：Dense+Sparse 双路召回，RRF 融合
- V1 升级：增加 Graph 检索，三路融合
- V1 升级：ColBERT 重排序

### Story 3.1: 混合检索功能

As a **战略分析师**,
I want **执行 Dense+Sparse 混合检索**,
So that **获得高相关性的检索结果**。

**Acceptance Criteria:**

**Given** 用户输入检索查询
**When** 执行混合检索
**Then** 系统执行双路召回：
- Dense 检索：使用 bge-m3 嵌入模型进行语义检索
- Sparse 检索：使用 BM25 进行关键词检索

**And** 使用 RRF 融合排序双路结果
**And** 返回 Top-K 最相关结果（K 可配置，默认 20）
**And** 检索结果包含相关性评分
**And** 语义缓存：相似度>0.9 直接返回缓存结果（Redis，TTL 24 小时）

**性能要求：**
- 检索延迟 P95：<800ms（MVP 目标）
- 检索召回率：≥80%
- 相关性评分：≥0.7（LLM-as-a-Judge 评估）
- 语义缓存命中率：>40%

**质量要求：**
- Dense 检索准确率：≥85%
- Sparse 检索召回率：≥90%
- RRF 融合效果：NDCG@10 ≥0.75

**业务规则：**
- 查询长度限制：<100 字符
- 并发查询支持：≥50QPS
- 缓存相似度阈值：>0.9（可配置）

---

### Story 3.2: 实体抽取功能

As a **知识工程师**,
I want **抽取文档中的实体**,
So that **构建战略领域知识图谱**。

**Acceptance Criteria:**

**Given** 文档解析完成
**When** 执行实体抽取
**Then** 系统使用 LLM+ 规则混合策略抽取实体：
- LLM 抽取：识别战略领域实体（公司/人物/指标/时间）
- 规则抽取：基于词典和正则表达式识别实体

**And** 输出实体三元组（头实体，关系，尾实体）
**And** 实体关联至原始文档切片（文档 ID+ 坐标）

**质量要求：**
- 实体抽取综合准确率：≥85%
- LLM 抽取召回率：≥90%
- 规则抽取准确率：≥80%
- 实体关联完整率：≥95%

**业务规则：**
- 实体类型：公司/人物/指标/时间/地点/产品
- 关系类型：投资/竞争/合作/供应/销售
- 低置信度实体标注"待审核"

---

### Story 3.3: 战略领域词典管理功能

As a **领域专家**,
I want **管理战略领域词典库**,
So that **提升实体抽取和检索的领域准确性**。

**Acceptance Criteria:**

**Given** 需要更新领域词典
**When** 添加/修改/删除词典条目
**Then** 系统支持以下词典类型：
- 公司名录（上市公司/独角兽/行业龙头）
- 人物名录（企业家/高管/行业专家）
- 指标术语（财务指标/市场指标/运营指标）
- 行业术语（战略/市场/技术/财务）

**And** 词典支持热更新（无需重启系统）
**And** 词典版本管理（版本号/更新时间/操作者）
**And** 词典覆盖范围统计

**质量要求：**
- 词典覆盖率：≥95%（战略领域）
- 词典更新延迟：<1 秒（热更新）
- 词典冲突检测率：100%

**业务规则：**
- 词典冲突解决：权威数据源优先，时间戳次之
- 词典版本保留：最近 10 个版本永久保留
- 词典生效范围：全局生效，支持租户级覆盖

---

### Story 3.4: 实体对齐与消歧功能

As a **数据工程师**,
I want **对齐与消歧实体**,
So that **避免同一实体在不同文档中的重复**。

**Acceptance Criteria:**

**Given** 实体抽取完成
**When** 执行实体对齐
**Then** 系统使用双路匹配策略：
- 编辑距离：识别拼写变体（如"腾讯"vs"腾讯公司"）
- 语义相似度：识别语义相同实体（如"阿里"vs"阿里巴巴"）

**And** 输出实体对齐结果（主实体 ID，变体实体列表）
**And** 低置信度对齐标注"待人工审核"

**质量要求：**
- 实体对齐准确率：≥90%
- 消歧准确率：≥85%
- 人工审核率：<10%

**业务规则：**
- 编辑距离阈值：≤2 视为相似
- 语义相似度阈值：≥0.85 视为相同
- 冲突时使用权威数据源（如工商注册名）

---

### Story 3.5: 三路检索融合排序功能

As a **搜索工程师**,
I want **融合三路检索结果**,
So that **获得最优的检索相关性**。

**Acceptance Criteria:**

**Given** Dense/Sparse/Graph 检索完成
**When** 执行结果融合
**Then** 系统使用 RRF (Reciprocal Rank Fusion) 融合排序：
- RRF 公式：score = Σ 1/(k + rank_i)，k=60（可配置）
- 支持三路检索结果加权融合

**And** 可选 ColBERT 重排序（V1 功能）
**And** 输出最终排序结果

**性能要求：**
- RRF 融合延迟：P95<50ms
- ColBERT 重排序延迟：P95<200ms（V1）

**质量要求：**
- RRF 融合效果：NDCG@10 ≥0.75
- 重排序提升：NDCG@10 提升≥10%

**MVP 阶段说明：**
- MVP：Dense+Sparse 双路 RRF 融合
- V1：增加 Graph 检索，三路 RRF 融合
- V1：增加 ColBERT 重排序

**业务规则：**
- RRF 的 k 值默认 60，可配置范围 10-100
- 三路权重：Dense 40% + Sparse 40% + Graph 20%（V1）

---

### Story 3.6: 分层检索功能

As a **高级分析师**,
I want **执行分层检索**,
So that **根据查询复杂度自动选择检索粒度**。

**Acceptance Criteria:**

**Given** 用户输入检索查询
**When** 执行分层检索
**Then** 系统根据查询复杂度自动路由至对应层级：
- L1 跨文档摘要：简单查询，返回跨文档摘要
- L2 文档摘要：中等查询，返回文档级摘要
- L3 文档切片：复杂查询，返回文档切片
- L4 实体级片段：精确查询，返回实体级片段

**And** 查询路由准确率≥85%
**And** 支持手动指定检索层级

**性能要求：**
- L1 检索延迟：P95<200ms
- L2 检索延迟：P95<400ms
- L3 检索延迟：P95<600ms
- L4 检索延迟：P95<800ms

**业务规则：**
- 查询复杂度判定：长度>50 字符或包含≥3 个实体为复杂查询
- 简单查询路由至 L1，中等查询路由至 L2，复杂查询路由至 L3/L4
- 支持手动指定检索层级，手动指定优先级高于自动路由

---

### Story 3.7: 检索相关性评估与补救功能

As a **质量工程师**,
I want **评估检索相关性并触发补救**,
So that **确保检索结果质量**。

**Acceptance Criteria:**

**Given** 检索完成
**When** 评估检索相关性
**Then** 系统使用 LLM-as-a-Judge 多维评估：
- 相关性评分：0-1 分，≥0.7 为合格
- 信息完整性：是否覆盖查询关键信息
- 时效性评分：是否优先返回最新数据

**And** 相关性<0.6 标注"数据不足"
**And** 触发自动补救机制：
  - 扩展检索范围（增加 K 值）
  - 调用白名单外部数据源
  - 生成数据缺口报告

**质量要求：**
- 相关性评估准确率：≥85%
- 补救成功率：≥70%
- 数据缺口报告完整率：≥90%

**性能要求：**
- 相关性评估延迟：P95<100ms
- 补救机制触发延迟：P95<50ms

---

### Story 3.8: 高保真溯源功能

As a **战略分析师**,
I want **溯源至原始文档坐标点**,
So that **快速验证数据来源和可靠性**。

**Acceptance Criteria:**

**Given** 用户点击检索结果中的结论
**When** 执行溯源查询
**Then** 系统展示完整溯源链：
```
结论 → 文档切片 → 文档版本 (v3) → 原始文件 (market_report.pdf) → 坐标点 (page:5, bbox:{x,y,w,h})
```

**And** 支持 Bounding Box 级跳转（点击跳转至 PDF 坐标点）
**And** 显示溯源置信度（高/中/低）
**And** 支持溯源树展开（逐层展开至原始数据）

**性能要求：**
- 溯源查询响应时间：P95<200ms
- 溯源树展开延迟：P95<100ms
- PDF 坐标跳转延迟：P95<500ms

**质量要求：**
- Bounding Box 级准确率：≥95%
- 溯源置信度准确率：≥90%
- 用户满意度：≥9/10

**业务规则：**
- 溯源树最大深度：≤10 层，超过时截断并提示
- 置信度显示：高（≥0.9）、中（0.7-0.9）、低（<0.7）

---

### Story 3.9: 引用数据时效性管理功能

As a **数据管理员**,
I want **管理引用数据的时效性**,
So that **优先使用最新数据进行决策**。

**Acceptance Criteria:**

**Given** 检索结果包含引用数据
**When** 评估数据时效性
**Then** 系统自动检查数据年龄：
- 数据年龄 >12 个月：标记"数据陈旧"并降权
- 数据年龄 6-12 个月：标记"注意时效性"
- 数据年龄 <6 个月：标记"最新数据"

**And** 检索排序考虑时效性因子
**And** 支持按时间范围过滤检索结果

**业务规则：**
- 数据年龄计算：当前日期 - 数据发布日期
- 陈旧数据降权因子：0.5（可配置）
- 时效性权重：10%（可配置）

**性能要求：**
- 时效性检查延迟：P95<50ms

**质量要求：**
- 时效性标记准确率：≥95%
- 陈旧数据识别召回率：≥90%

---

## Epic 3 Stories 完成清单

| Story | 标题 | 覆盖 FR | 状态 |
|-------|------|--------|------|
| 3.1 | 混合检索功能 | SR-01 | ✅ 完成（已补充语义缓存 + 业务规则） |
| 3.2 | 实体抽取功能 | SR-02 | ✅ 完成 |
| 3.3 | 战略领域词典管理功能 | SR-03 | ✅ 完成（已补充业务规则） |
| 3.4 | 实体对齐与消歧功能 | SR-04 | ✅ 完成 |
| 3.5 | 三路检索融合排序功能 | SR-05 | ✅ 完成（已补充业务规则） |
| 3.6 | 分层检索功能 | SR-06, SR-07 | ✅ 完成（已补充业务规则） |
| 3.7 | 检索相关性评估与补救功能 | SR-10, SR-11 | ✅ 完成（已补充性能要求） |
| 3.8 | 高保真溯源功能 | SR-12 | ✅ 完成（已补充业务规则） |
| 3.9 | 引用数据时效性管理功能 | SR-13 | ✅ 完成（已补充性能 + 质量要求） |

**注：** SR-08（摘要生成）和 SR-09（摘要质量评估）将在 Epic 6 战略规划流程中实现

---

### 审核修复清单

| 编号 | 修复项 | 修复状态 |
|------|--------|---------|
| **INC-01** | Story 3.1 补充语义缓存说明 | ✅ 已修复 |
| **INC-02** | Story 3.9 补充性能要求 | ✅ 已修复 |
| **INC-03** | Story 3.9 补充质量要求 | ✅ 已修复 |
| **INC-04** | Story 3.1/3.3/3.5/3.6 补充业务规则 | ✅ 已修复 |
| **INC-05** | Story 3.7 补充评估延迟性能要求 | ✅ 已修复 |
| **SUG-01** | Story 3.3 补充词典冲突解决策略 | ✅ 已修复 |
| **SUG-02** | Story 3.6 补充查询复杂度判定标准 | ✅ 已修复 |
| **SUG-03** | Story 3.8 补充溯源树最大深度限制 | ✅ 已修复 |

**修复后一致性评级：A+ (优秀)**

---

**Epic 3 完成！请审核以下内容：**

### 审核清单

1. **FR 覆盖完整性**
   - [ ] SR-01 ~ SR-13 覆盖（除 SR-08/SR-09 外）
   - [ ] 每个 Story 对应明确的 FR

2. **Story 质量**
   - [ ] 每个 Story 有清晰的用户价值（So that）
   - [ ] Acceptance Criteria 使用 Given/When/Then 格式
   - [ ] 包含性能要求和质量要求

3. **架构一致性**
   - [ ] 符合 architecture.md 混合检索设计
   - [ ] Dense(bge-m3)+Sparse(BM25) 双路召回
   - [ ] RRF 融合排序

4. **MVP 范围**
   - [ ] MVP 阶段范围明确
   - [ ] V1 升级路径清晰

---

**请确认 Epic 3 Stories 是否完整正确，或需要调整哪些内容？**