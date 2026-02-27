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
I want **定义核心领域实体（Document, Agent, Tool, StrategicPlan, Checkpoint）**,
So that **领域逻辑有清晰的模型基础**。

**Acceptance Criteria:**

**Given** 领域实体定义
**When** 创建 `src/domain/models/` 下的实体类
**Then** 包含以下实体：
- `Document`（文档实体，17 种格式支持）
- `Agent`（Agent 实体，7 角色 + SYS+AUD）
- `Tool`（工具实体，23 种战略工具）
- `StrategicPlan`（战略规划实体，SP/BP）
- `Checkpoint`（检查点实体，双模式恢复）
- `StrategicArchive`（战略档案实体，五层存储）
- `RoutingDecisionLog`（路由决策日志）
- `IsolationSwitchLog`（隔离切换日志）

**And** 所有实体通过 mypy 严格类型检查
**And** 实体包含领域事件发布方法

### Story 1.3: 领域服务接口定义

As a **架构师**,
I want **定义领域服务接口（RAGService, ToolService, AgentService, PlanningService）**,
So that **领域层不依赖任何外部技术实现，遵循依赖