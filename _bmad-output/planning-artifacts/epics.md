---
stepsCompleted: ['step-01-validate-prerequisites']
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
workflowType: 'epics-and-stories'
project_name: 'sisys'
user_name: 'Agimtech'
date: '2026-02-28'
status: 'in-progress'
currentStep: 'step-01-validate-prerequisites'
---

# sisys - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for sisys, decomposing the requirements from the PRD, UX Design, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

**FR-DM (文档与数据管理 - 15 项):**
- FR-DM-01 (P0): 用户可以上传 17 种格式的文档（pdf/txt/doc/docx/ppt/pptx/xls/xlsx/csv/jpeg/png/gif/markdown/html + zip/tar 压缩包）
- FR-DM-02 (P0): 系统可以解析上传文档并提取文本、表格、图像、公式内容
- FR-DM-03 (P0): 系统可以保留文档版面信息（元素坐标 x, y, width, height），采用 DocLayNet 标准格式
- FR-DM-04 (P0): 系统可以提取表格的行列语义，输出包含表头与列类型的结构化 JSON
- FR-DM-05 (P0): 系统可以对扫描件或图像 PDF 进行 OCR 解析（中/英），提取置信度并标注
- FR-DM-06 (P0): 用户可以创建文档版本快照，系统记录操作者、时间戳与差异摘要
- FR-DM-07 (P0): 系统可以校验入库文档的最小元字段集（creator/created_at/source/license/business_domain）
- FR-DM-08 (P0): 系统可以对文档进行语义分块，基于文档语义边界而非固定字数切片
- FR-DM-09 (P1): 用户可以追溯每个解析后的数据切片至导入批次与原始文件版本
- FR-DM-10 (P1): 系统可以执行环境预检（GPU 驱动/CUDA 版本/内存），仅异常时通知用户
- FR-DM-11 (P1): 用户可以导入季度/年度经营复盘数据，用于计算与规划的偏差
- FR-DM-12 (P1): 系统可以支持合并单元格语义还原与跨页表格识别
- FR-DM-13 (P2): 系统可以识别数学公式并输出 LaTeX 与 MathML 双格式表达
- FR-DM-14 (P2): 系统可以实现图文联合嵌入空间，支持"以图搜文/以文搜图"的跨模态检索
- FR-DM-15 (P2): 系统可以支持音视频转录文本接入

**FR-SR (智能检索与知识发现 - 15 项):**
- FR-SR-01 (P0): 系统可以执行混合检索（Dense bge-m3 + BM25 稀疏检索），双路召回
- FR-SR-02 (P0): 系统可以抽取实体（LLM+ 规则混合策略），输出三元组
- FR-SR-03 (P0): 系统可以管理战略领域词典库，支持热更新与版本管理
- FR-SR-04 (P0): 系统可以融合三路检索结果（Dense + Sparse + Graph/metadata signals），使用 RRF 融合排序
- FR-SR-05 (P0): 系统可以执行分层检索（L1 跨文档摘要→L2 文档摘要→L3 文档切片→L4 实体级片段）
- FR-SR-06 (P0): 系统可以生成契约化结构化摘要（财务/市场/技术视角），输出符合预定义 JSON Schema
- FR-SR-07 (P0): 系统可以评估检索相关性（LLM-as-a-Judge 实时多维评估），相关性<0.6 标注"数据不足"
- FR-SR-08 (P0): 系统可以保留引文"三元组"特征（文档 ID、切片 ID、字符范围），支持 Bounding Box 级溯源
- FR-SR-09 (P1): 系统可以对齐与消歧实体（基于编辑距离 + 语义相似度双路匹配）
- FR-SR-10 (P1): 系统可以根据查询复杂度与意图自动路由至对应检索层级
- FR-SR-11 (P1): 系统可以评估摘要质量（信息熵 + 关键实体覆盖率），评分<0.7 自动触发二次生成
- FR-SR-12 (P1): 系统可以触发自动补救机制（扩展检索范围/调用白名单外部数据源/生成数据缺口报告）
- FR-SR-13 (P1): 系统可以构建知识图谱（实体节点 + 关系边），支持 GraphRAG 增强检索
- FR-SR-14 (P2): 系统可以管理引用数据的时效性，超 12 个月数据自动标记"数据陈旧"并降权
- FR-SR-15 (P2): 系统可以执行实体关联查询、路径查询、社区发现算法（Louvain/Label Propagation）

**FR-ST (战略工具箱 - 11 项):**
- FR-ST-01 (P0): 系统可以注册战略工具（23 种：PESTEL/波特五力/$APPEALS/价值链等）
- FR-ST-02 (P0): 系统可以编排工具链（DAG 有向无环图），按拓扑顺序调度子任务
- FR-ST-03 (P0): 系统可以验证工具输入/输出 Schema（Pydantic V2 契约化）
- FR-ST-04 (P0): 系统可以在 Docker 沙箱中执行工具代码，网络隔离 + 权限最小化
- FR-ST-05 (P0): 系统可以执行红蓝辩论机制基础（单 Agent 多视角，MVP 替代方案）
- FR-ST-06 (P1): 系统可以管理工具版本，支持版本控制、灰度发布与回滚
- FR-ST-07 (P1): 系统可以执行 Validation Feedback 闭环（最大重试 3 次，失败标记不可行）
- FR-ST-08 (P1): 系统可以遵循 MCP 2025 规范与 A2A 协议，通过 MCP Registry 暴露工具能力
- FR-ST-09 (P1): 系统可以支持财务建模与估值基础（DCF/可比公司/先例交易基础）
- FR-ST-10 (P2): 系统可以在 gVisor 沙箱中执行代码，提供用户空间内核隔离
- FR-ST-11 (P2): 系统可以支持压力测试建模（宏观经济变量情景分析）

**FR-AC (Agent 协作 - 16 项):**
- FR-AC-01 (P0): 系统可以实例化 Agent 角色基础（CEO Agent，MVP 单 Agent 方案）
- FR-AC-02 (P0): 系统可以加载 Agent 身份档案（IDENTITY.md/CODE.md/SOUL.md/TOOLS.md/USER.md/MEMORY.md/HEARTBEAT.md）
- FR-AC-03 (P0): 系统可以执行单 Agent 任务（感知→规划→执行→验证→反思→证据打包）
- FR-AC-04 (P0): 系统可以执行弹性视角隔离协议基础（L4 硬隔离默认）
- FR-AC-05 (P0): 系统可以保证 Agent 默认隔离等级为 L4 硬隔离（Prompt/工具/数据三重硬隔离）
- FR-AC-06 (P0): 系统可以记录隔离切换日志（AGENT ID、时间戳、原隔离等级、目标隔离等级、触发原因、审批链）
- FR-AC-07 (P1): 系统可以分解多 Agent 协作任务（SYS Agent 解析目标并分解，各专业 Agent 并行执行）
- FR-AC-08 (P1): 系统可以生成协作依赖图（基于 BLM/BEM 阶段）
- FR-AC-09 (P1): 系统可以动态调整隔离等级（基于任务依赖/关键词频率/SYS Agent 命令）
- FR-AC-10 (P1): 系统可以创建联合分析组，相关 Agent 隔离等级降级至 L2 协作态
- FR-AC-11 (P1): 系统可以通过公共黑板交换中间结论（附带置信度与引用源）
- FR-AC-12 (P1): 系统可以执行 SYS Agent 裁决（最大辩论轮次 3+ 风险等级，上限 7 轮）
- FR-AC-13 (P1): 系统可以生成三套方案（Plan A 保守/Plan B 激进/Plan C AI 融合版）
- FR-AC-14 (P1): 系统可以执行深度思考与多路径推演（并行生成多条思维链）
- FR-AC-15 (P2): 系统可以强制暂停 5 分钟请求用户介入，超时无操作按 SYS Agent 决策执行
- FR-AC-16 (P2): 系统可以支持 Agent 实例池化与动态扩缩容（基于负载自动伸缩）

**FR-SP (战略规划流程 - 12 项):**
- FR-SP-01 (P0): 系统可以执行 BLM 前两阶段流程（业绩差距分析 + 市场洞察，含流程可视化；MVP 阶段 CEO AGENT 替代流程中所有 AGENT 角色）
- FR-SP-02 (P0): 系统可以执行市场洞察六子步骤基础（看趋势/看市场与客户/看竞争/看自己/看机会/机会差距分析）
- FR-SP-03 (P0): 系统可以创建 Checkpoint 快照（阶段标识、完成状态、用户反馈、修正记录）
- FR-SP-04 (P0): 系统可以输出 JSON 思维链（Input→<Reflection>→<Tools_Used>→<Constraints_Check>→JSON）
- FR-SP-05 (P1): 系统可以执行完整 BLM 六阶段流程（业绩差距分析→市场洞察六子步骤→战略意图与目标→创新焦点→业务设计→执行设计；各 AGENT 按标准角色定义各司其职）
- FR-SP-06 (P1): 系统可以执行 Replay 重放模式（修改点后所有状态重新计算，强一致性）
- FR-SP-07 (P1): 系统可以评估修改影响范围（≥2 个后续 Checkpoint 强制 Replay，<2 个推荐 Override）
- FR-SP-08 (P1): 系统可以执行 Override 覆盖模式（仅修改指定状态，需人工确认一致性风险）
- FR-SP-09 (P1): 系统可以执行 Time-travel 两阶段能力（单点恢复/分支对比）
- FR-SP-10 (P1): 系统可以支持红蓝辩论机制完整实现（发散 Temperature=0.8→收敛 Temperature=0.5→裁决 Temperature=0.2）
- FR-SP-11 (P2): 系统可以执行 BEM 六阶段流程（澄清战略方向→导出战略举措→导出衡量指标→确定年度措施→分解目标→导出重点工作计划）
- FR-SP-12 (P2): 系统可以将 SP 输出结构化映射为 BP 输入（战略解码器）

**FR-UI (用户交互与报告 - 13 项):**
- FR-UI-01 (P0): 用户可以通过 CLI 执行命令（文档上传/Agent 调用/规划生成/Checkpoint 恢复）
- FR-UI-02 (P0): 系统可以通过 REST API 提供接口（文档管理/工具调用/Agent 协作/规划生成/系统管理）
- FR-UI-03 (P0): 系统可以通过 API Gateway 统一入口处理所有外部请求（统一认证/限流/路由/安全控制）
- FR-UI-04 (P0): 系统可以生成多格式报告（PDF/Markdown），包含可点击的引文索引
- FR-UI-05 (P0): 用户可以查看 Checkpoint 摘要并修正关键参数后恢复运行
- FR-UI-06 (P0): 系统可以展示溯源树（从结论逐层展开至原始数据）
- FR-UI-07 (P0): 系统可以支持高管简化视图（仪表盘/审批中心/审计摘要）
- FR-UI-08 (P1): 系统可以可视化展示决策过程（关键决策路径和依据）
- FR-UI-09 (P1): 系统可以创建/切换/删除分支，提供分支差异对比视图
- FR-UI-10 (P1): 系统可以展示 Checkpoint 恢复模式选择界面（影响范围、推荐模式、风险提示）
- FR-UI-11 (P1): 系统可以支持无障碍设计（WCAG 2.1 AA，键盘导航，屏幕阅读器兼容）
- FR-UI-12 (P1): 系统可以支持多语言界面（中文/英文切换）
- FR-UI-13 (P2): 系统可以支持决策影响分析（Shapley 贡献值，反事实推理）

**FR-SC (系统管理与合规 - 14 项):**
- FR-SC-01 (P0): 系统可以管理用户认证与 RBAC 权限（用户表/角色表/权限表/关联表）
- FR-SC-02 (P0): 系统可以记录统一审计日志（log_id/timestamp/actor/action_type/target_resource/old_value/new_value）
- FR-SC-03 (P0): 系统可以将审计日志写入不可变存储（WORM 基础，MVP 采用 PostgreSQL 审计表方案）
- FR-SC-04 (P0): 系统可以按时间/角色/任务类型/修正级别多维检索审计日志
- FR-SC-05 (P0): 系统可以执行修正分级判定基础（L0 拼写/格式/L1 参数/权重 自动固化）
- FR-SC-06 (P0): 系统可以自动固化 L0/L1 级修正（生成 Few-Shot 样本→Strat-Bench 测试→版本注册→WORM 存储）
- FR-SC-07 (P0): 系统可以执行数据主权隔离（敏感数据本地优先，外部网络调用需审计与白名单批准）
- FR-SC-08 (P0): 系统可以支持等保 2.0 三级要求（身份鉴别/访问控制/安全审计/入侵防范/数据完整性/备份恢复）
- FR-SC-09 (P1): 系统可以对敏感数据脱敏（个人可识别信息、商业机密）
- FR-SC-10 (P1): 系统可以执行 L2 级修正专家确认（1 人，4 小时 SLA，紧急通道 1 小时）
- FR-SC-11 (P1): 系统可以执行 L3 级修正委员会审批（≥3 人，48 小时 SLA）
- FR-SC-12 (P1): 系统可以支持 SOX 合规（404 条款内部控制评估报告）
- FR-SC-13 (P2): 系统可以支持 ISO 27001 认证（信息安全管理体系）
- FR-SC-14 (P2): 系统可以支持银保监会规范（1104 报表/EAST 报表生成）

**FR-CP (成本与性能优化 - 12 项):**
- FR-CP-01 (P0): 系统可以记录路由决策日志（任务 ID、时间戳、L1 结果、L2 各因子评分、最终评分、选定路由、成本、延迟）
- FR-CP-02 (P0): 系统可以执行语义缓存基础（相似度>0.9 直接返回缓存结果）
- FR-CP-03 (P0): 系统可以提供健康度仪表盘（实时可视化各 Agent 健康度指标）
- FR-CP-04 (P0): 系统可以输出 OpenTelemetry Trace（自适应采样，错误率>1% 时全采样）
- FR-CP-05 (P1): 系统可以执行统一动态模型路由框架（UDMR）三层决策（L1 合规性过滤→L2 任务复杂度评估→L3 路由决策执行）
- FR-CP-06 (P1): 系统可以基于四因子评分路由（语义匹配 35% + 历史成功率 30% + 成本效率 20% + 任务复杂度 15%）
- FR-CP-07 (P1): 系统可以执行三级成本熔断（任务级/会话级/系统级）
- FR-CP-08 (P1): 系统可以预测任务成本（基于历史相似任务），偏差超阈值触发分级预警
- FR-CP-09 (P1): 系统可以管理缓存失效（TTL 24 小时 + 事件驱动失效 + 版本感知失效）
- FR-CP-10 (P1): 系统可以检测性能漂移（CUSUM 算法，滑动窗口 7 天）
- FR-CP-11 (P2): 系统可以执行区块链哈希链（审计日志不可篡改增强）
- FR-CP-12 (P2): 系统可以提供 UEBA 用户行为分析（高级威胁检测）

**FR-SA (战略档案库与长期记忆 - 10 项):**
- FR-SA-01 (P0): 系统可以永久存储历年 SP/BP 的关键假设变量、决策依据、实际执行偏差
- FR-SA-02 (P0): 系统可以管理事实有效期标签（valid_from/valid_until）
- FR-SA-03 (P0): 系统可以执行数据陈旧标记（超 12 个月自动降权）
- FR-SA-04 (P1): 系统可以查询时间轴演进（按时间范围查询历史决策）
- FR-SA-05 (P1): 系统可以执行心跳机制（周期性自动唤醒，检查待办事项、偏差预警、周期性任务）
- FR-SA-06 (P1): 系统可以发布战略偏差预警事件（偏差超阈值 10% 自动触发）
- FR-SA-07 (P1): 系统可以管理分支（主线/分支差异对比、分支合并/放弃）
- FR-SA-08 (P2): 系统可以主动推送知识更新（检测到行业报告/市场数据/政策法规更新时）
- FR-SA-09 (P2): 系统可以支持预测性战略预警（基于市场数据的主动预警，CUSUM 漂移检测）
- FR-SA-10 (P3): 系统可以支持群体智能（多企业匿名数据学习，提升战略建议质量）- V3+ 版本

**FR-AR (架构约束 - 4 项):**
- FR-AR-01 (P0): 系统可以保证领域层不依赖任何外部框架（仅依赖 Python 标准库与领域模型）
- FR-AR-02 (P0): 系统可以发布领域事件至事件总线，支持事件重放与失败重试
- FR-AR-03 (P0): 系统可以执行跨存储事务基础（PostgreSQL 事务，MVP 方案），保证最终一致性
- FR-AR-04 (P0): 系统可以通过仓储模式向领域层提供统一存储接口（领域层不直接依赖具体存储实现）

### Non-Functional Requirements

**NFR-PERF (性能 - 7 项):**
- NFR-PERF-01 (P0): 检索延迟 P95 <800ms（MVP），<500ms（V1），<300ms（V2）
- NFR-PERF-02 (P0): 路由决策延迟 P95 <100ms（MVP），<50ms（V1），<30ms（V2）
- NFR-PERF-03 (P0): 报告生成时间 <30 秒（标准报告），<2 分钟（完整 SP/BP 报告）
- NFR-PERF-04 (P0): 并发 Agent 会话支持 MVP≥10，V1≥50，V2≥200，延迟 P95<2s
- NFR-PERF-05 (P0): Checkpoint 恢复时间 <60 秒（Replay 模式，MVP），<30 秒（Override 模式，V1）
- NFR-PERF-06 (P1): 语义缓存命中率 >40%，Token 消耗降低 40-50%
- NFR-PERF-07 (P1): 图遍历查询延迟 P95 <200ms（简单查询），<800ms（复杂图遍历）

**NFR-SEC (安全性 - 7 项):**
- NFR-SEC-01 (P0): 数据传输加密 TLS 1.3，SSL Labs A+ 评级
- NFR-SEC-02 (P0): 数据存储加密 AES-256，加密审计通过
- NFR-SEC-03 (P0): 渗透测试无高危漏洞，中危漏洞<5 个
- NFR-SEC-04 (P0): 数据泄露事件 0 事件
- NFR-SEC-05 (P0): 提示注入检测准确率≥95%（ShieldCortex），误报率<5%
- NFR-SEC-06 (P0): RBAC 权限测试 100% 通过，越权访问 0 次
- NFR-SEC-07 (P0): 沙箱逃逸测试 0 次逃逸成功

**NFR-COMP (合规性 - 9 项):**
- NFR-COMP-01 (P0): 等保 2.0 三级通过公安部指定测评机构测评，MVP 发布前 1 个月完成，无高风险项
- NFR-COMP-02 (P0): 审计日志保留 PostgreSQL 审计表（MVP），7 年 WORM 存储 + Object Lock（V2）
- NFR-COMP-03 (P0): 数据主权数据境内存储 100%，跨境传输审批率 100%
- NFR-COMP-04 (P0): 隐私保护（PIPL）个人信息脱敏率 100%，删除请求响应<24 小时
- NFR-COMP-05 (P0): 审计日志完整性 100% 完整，日志审计工具验证通过
- NFR-COMP-06 (P1): SOX 404 条款通过第三方审计，内部控制无重大缺陷
- NFR-COMP-07 (P1): ISO 27001 通过认证，ISMS 运行有效
- NFR-COMP-08 (P2): 银保监会规范 1104 报表/EAST 报表生成准确率 100%
- NFR-COMP-09 (P2): 完整审计追踪可视化 7 年 WORM 存储 + 区块链哈希链 + 可视化时间线，审计查询<10 秒

**NFR-REL (可靠性 - 6 项):**
- NFR-REL-01 (P0): 系统可用性 99%（MVP），99.5%（V1），99.9%（V2）
- NFR-REL-02 (P0): 数据备份每日全量 + 实时增量，RPO<1 小时
- NFR-REL-03 (P0): 灾难恢复 RTO<4 小时，异地灾备，季度演练成功率 100%
- NFR-REL-04 (P0): Checkpoint 快照持久化 100% 持久化，故障恢复成功率≥99%
- NFR-REL-05 (P1): 性能漂移检测 CUSUM 算法检测连续性能下降（滑动窗口 7 天），检测准确率≥85%
- NFR-REL-06 (P1): 成本熔断三级熔断触发准确率 100%，成本超支 0 事件

**NFR-SCALE (可扩展性 - 4 项):**
- NFR-SCALE-01 (P1): 用户增长支持支持 10 倍用户增长（100→1000→10000 用户），性能下降<10%
- NFR-SCALE-02 (P1): 数据量支持 TB 级战略档案库，检索延迟 P95<1s
- NFR-SCALE-03 (P1): Agent 动态扩缩容基于负载自动伸缩，响应时间<5 分钟
- NFR-SCALE-04 (P0): 多租户隔离 Schema per Tenant + Row-Level Security，隔离测试 100% 通过

**NFR-INT (集成性 - 5 项):**
- NFR-INT-01 (P0): API 可用性≥99%，OpenAPI 3.1 规范，自动生成文档/SDK/Mock 服务
- NFR-INT-02 (P1): 预置集成适配器≥5 个（ERP/CRM/OA 各至少 1 个）
- NFR-INT-03 (P1): 外部数据源接入≥3 个（工商/税务/专利等）
- NFR-INT-04 (P0): 集成失败率<1%，失败自动重试（最多 3 次），重试成功率≥80%
- NFR-INT-05 (P0): MCP/A2A 协议兼容性向后兼容 1-2 个版本，协议兼容性测试通过

**NFR-ACC (可访问性 - 2 项):**
- NFR-ACC-01 (P1): 无障碍设计 WCAG 2.1 AA 标准，键盘导航 100% 支持，屏幕阅读器兼容
- NFR-ACC-02 (P1): 多语言支持中文/英文界面，翻译准确率≥95%，术语表统一

### Additional Requirements

**架构技术要求（来自 Architecture.md）:**

- **六边形架构**: 领域层零依赖，仅依赖 Python 标准库与领域模型
- **事件驱动架构**: RabbitMQ + Redis 双通道事件总线，支持事件重放
- **五层存储架构**: 
  - L1 高速缓存层（Redis 7.0+）：会话状态、语义缓存
  - L2 关系存储层（PostgreSQL 15+）：用户/RBAC、审计元数据
  - L3 向量存储层（Qdrant 1.7+）：嵌入向量、混合检索 payload
  - L4 对象存储层（MinIO WORM）：原始文档、证据包、审计归档
  - L5 图存储层（Neo4j 5.x）：知识图谱、实体关系
- **双核引擎架构**: Prefect 负责确定性数据流，LangGraph 负责认知推理
- **UDMR 统一动态模型路由**: L1 合规性过滤→L2 任务复杂度评估→L3 路由决策执行
- **EIP 弹性视角隔离协议**: 四级隔离等级（L4 硬隔离/L3 软隔离/L2 协作态/L1 融合态）
- **修正分级判定体系**: 五维特征加权算法（修正类型 30%/置信度变化 25%/影响范围 20%/可逆性 15%/领域关键度 10%）
- **SYS AGENT 裁决机制**: 五维评分（事实准确性 35%/逻辑一致性 25%/风险可控性 20%/资源可行性 15%/战略对齐度 5%）
- **Checkpoint 双模式恢复**: Replay 模式（强一致性）与 Override 模式（需人工确认）

**UX 设计要求（来自 ux-design-specification.md）:**

- **三视图设计**: 高管视图（简化决策）、分析师视图（专业工具）、企业战略与市场人员视图（流程标准化）
- **高保真溯源**: Bounding Box 坐标级跳转，响应时间<300ms，定位准确率≥95%
- **高管仪表盘**: 第一屏只显示 3 个关键指标，红/黄/绿状态指示器
- **情感目标**: 高管掌控感、企业战略人员成就感、专业顾问专业感
- **设计系统**: Ant Design 5.x + CSS-in-JS + Design Tokens
- **白标输出**: 品牌模板系统，支持咨询/投行品牌定制

**部署与运维要求:**

- **部署模式**: 本地部署/私有云/公有云/混合云
- **灾备要求**: RPO<1 小时，RTO<4 小时，季度恢复演练
- **监控要求**: 系统可用性、性能监控、安全监控、成本监控、合规监控

### FR Coverage Map

**FR 与 Epic 映射关系:**

| Epic | 覆盖的 FR | 优先级 |
|------|---------|-------|
| Epic 1: 基础架构与核心能力 | FR-AR-01~04, FR-SC-01~08, FR-DM-01~08 | P0 |
| Epic 2: RAG 检索与高保真溯源 | FR-SR-01~08, FR-DM-03, FR-UI-06 | P0 |
| Epic 3: 单 Agent 执行与 EIP 隔离 | FR-AC-01~06, FR-ST-01~05 | P0 |
| Epic 4: BLM 战略规划流程 | FR-SP-01~04, FR-UI-04~05, FR-SA-01~03 | P0 |
| Epic 5: 用户接口与报告生成 | FR-UI-01~04, FR-UI-07, FR-CP-03~04 | P0 |
| Epic 6: 多 Agent 协作与裁决 | FR-AC-07~14, FR-SP-05~10, FR-ST-06~09 | P1 |
| Epic 7: UDMR 动态路由与成本优化 | FR-CP-05~10, FR-SA-04~07 | P1 |
| Epic 8: 完整合规与审计 | FR-SC-09~14, FR-CP-11~12, NFR-COMP-06~09 | P1/P2 |
| Epic 9: BEM 战略解码 | FR-SP-11~12, FR-ST-10~11, FR-SR-14~15 | P2 |
| Epic 10: 企业级能力与生态集成 | FR-DM-09~15, FR-SR-09~13, FR-UI-08~13, FR-AC-15~16 | P1/P2 |

### Requirements Coverage Summary

**需求覆盖统计:**

| 类别 | P0 (MVP) | P1 (V1) | P2 (V2) | P3 (V3+) | 总计 |
|------|---------|--------|--------|---------|------|
| 功能需求 (FR) | 57 | 46 | 18 | 1 | 122 |
| 非功能需求 (NFR) | 25 | 13 | 2 | - | 40 |
| **总计** | **82** | **59** | **20** | **1** | **162** |

**MVP 范围确认（57 项 FR + 25 项 NFR）:**

核心验证能力：
- ✅ 高保真溯源（30 秒 vs 2 小时）
- ✅ 白标输出（可直接交付）
- ✅ 单 Agent 执行（CEO Agent）
- ✅ BLM 前两阶段
- ✅ 基础合规（等保 2.0/RBAC/审计日志）

---

## Epic List

**基于用户价值流和依赖关系，将 122 项 FR 和 40 项 NFR 分解为以下 10 个 Epic:**

| Epic ID | Epic 名称 | 用户价值 | 包含 FR | 包含 NFR | 优先级 |
|--------|---------|---------|--------|---------|-------|
| **Epic 1** | 基础架构与核心能力 | 奠定六边形架构基础，支持领域层零依赖和事件驱动 | FR-AR-01~04, FR-SC-01~08, FR-DM-01~08 | NFR-SEC-01~07, NFR-COMP-01~05, NFR-SCALE-04 | P0 |
| **Epic 2** | RAG 检索与高保真溯源 | 实现 30 秒溯源至原始文档坐标点，建立用户信任 | FR-SR-01~08, FR-DM-03 | NFR-PERF-01, NFR-PERF-03 | P0 |
| **Epic 3** | 单 Agent 执行与 EIP 隔离 | MVP 单 Agent 方案，支持弹性视角隔离基础 | FR-AC-01~06, FR-ST-01~05 | NFR-SEC-05~07 | P0 |
| **Epic 4** | BLM 战略规划流程 | 执行 BLM 前两阶段（业绩差距 + 市场洞察），支持 Checkpoint 快照 | FR-SP-01~04, FR-SA-01~03 | NFR-REL-01~04 | P0 |
| **Epic 5** | 用户接口与报告生成 | CLI/API 接口、报告生成、高管仪表盘 | FR-UI-01~04, FR-UI-07, FR-CP-03~04 | NFR-INT-01, NFR-INT-04~05 | P0 |
| **Epic 6** | 多 Agent 协作与裁决 | 完整 7 角色 Agent 协作、SYS Agent 裁决、红蓝辩论 | FR-AC-07~14, FR-SP-05~10, FR-ST-06~09 | NFR-PERF-04 | P1 |
| **Epic 7** | UDMR 动态路由与成本优化 | 三层决策路由、语义缓存、成本熔断 | FR-CP-05~10, FR-SA-04~07 | NFR-PERF-02, NFR-PERF-06~07, NFR-REL-05~06 | P1 |
| **Epic 8** | 完整合规与审计 | SOX/ISO27001 合规、7 年 WORM 存储、区块链哈希链 | FR-SC-09~14, FR-CP-11~12 | NFR-COMP-06~09 | P1/P2 |
| **Epic 9** | BEM 战略解码 | SP→BP 映射、BEM 六阶段、压力测试 | FR-SP-11~12, FR-ST-10~11, FR-SR-14~15 | NFR-PERF-07 | P2 |
| **Epic 10** | 企业级能力与生态集成 | 数据治理增强、知识图谱、无障碍设计、多语言 | FR-DM-09~15, FR-SR-09~13, FR-UI-08~13, FR-AC-15~16 | NFR-SCALE-01~03, NFR-INT-02~03, NFR-ACC-01~02 | P1/P2 |

---

## Epic 1: 基础架构与核心能力

**Goal:** 建立六边形架构基础，实现领域层零依赖、事件驱动架构、RBAC 权限管理、基础合规（等保 2.0）和文档管理基础能力，为后续功能提供坚实的技术基础。

**Business Value:** 
- 技术风险控制：六边形架构确保领域逻辑与技术实现隔离，支持长期演进
- 合规准入门槛：等保 2.0 三级是企业市场准入的基本要求
- 数据安全基础：RBAC 权限控制和审计日志确保企业数据安全

**Dependencies:** 无（基础架构 Epic）

**Acceptance Criteria:**
- 领域层零依赖测试通过（仅依赖 Python 标准库）
- 事件发布/重放成功率 100%
- RBAC 权限测试 100% 通过
- 等保 2.0 三级测评无高风险项
- 审计日志完整性 100%

---

### Story 1.1: 六边形架构骨架搭建

As a **系统架构师**,
I want **搭建六边形架构骨架，定义领域层/应用层/基础设施层边界**,
So that **领域逻辑与技术实现隔离，支持长期独立演进**.

**Acceptance Criteria:**

**Given** 项目初始化完成
**When** 架构师创建项目结构
**Then** 领域层不包含任何外部框架依赖（仅 Python 标准库）
**And** 应用层通过接口与领域层交互

**Given** 领域模型定义完成
**When** 基础设施层实现仓储接口
**Then** 领域层不直接依赖具体存储实现
**And** 依赖方向指向领域层（依赖倒置原则）

---

### Story 1.2: 事件驱动总线实现

As a **系统架构师**,
I want **实现 RabbitMQ + Redis 双通道事件总线**,
So that **核心业务逻辑通过领域事件触发，支持事件重放与失败重试**.

**Acceptance Criteria:**

**Given** 事件总线配置完成
**When** 领域服务发布事件
**Then** 事件同时写入 RabbitMQ（持久化）和 Redis（实时通知）
**And** 事件消息包含完整上下文（event_id/timestamp/actor/payload）

**Given** 事件消费者订阅完成
**When** 事件总线发布事件
**Then** 消费者在 100ms 内接收到事件
**And** 事件处理失败时自动重试（最多 3 次）

**Given** 事件溯源启用
**When** 需要重放事件
**Then** 可以从事件存储中按时间顺序重放
**And** 重放成功率≥99%

---

### Story 1.3: RBAC 权限管理实现

As a **系统管理员**,
I want **实现基于 RBAC 的权限管理（用户表/角色表/权限表/关联表）**,
So that **不同角色用户拥有细粒度的数据访问权限**.

**Acceptance Criteria:**

**Given** 用户角色配置完成
**When** 用户登录系统
**Then** 从 JWT 中提取角色和权限范围
**And** 用户只能访问授权范围内的数据

**Given** 权限变更请求
**When** 管理员修改用户权限
**Then** 权限立即生效（通过 Redis 缓存刷新）
**And** 权限变更记录至审计日志

**Given** 越权访问尝试
**When** 用户尝试访问未授权数据
**Then** 系统拒绝访问并记录安全事件
**And** 越权访问次数为 0（验收标准）

---

### Story 1.4: 等保 2.0 三级合规实现

As a **合规官**,
I want **实现等保 2.0 三级要求（身份鉴别/访问控制/安全审计/入侵防范/数据完整性/备份恢复）**,
So that **系统通过公安部指定测评机构测评，无高风险项**.

**Acceptance Criteria:**

**Given** 等保 2.0 配置完成
**When** 测评机构执行测评
**Then** 身份鉴别（双因子认证）通过
**And** 访问控制（细粒度权限）通过
**And** 安全审计（6 个月日志保留）通过
**And** 入侵防范（实时检测告警）通过
**And** 数据完整性（防篡改）通过
**And** 备份恢复（RPO<1 小时，RTO<4 小时）通过

**Given** 高风险项检查
**When** 执行自动扫描
**Then** 高风险项数量为 0
**And** 中危漏洞<5 个

---

### Story 1.5: 统一审计日志实现

As a **审计员**,
I want **实现统一审计日志（log_id/timestamp/actor/action_type/target_resource/old_value/new_value）**,
So that **所有操作可追溯，满足 SOX/ISO27001 合规要求**.

**Acceptance Criteria:**

**Given** 用户执行操作
**When** 操作完成
**Then** 审计日志在 100ms 内写入 PostgreSQL 审计表
**And** 日志包含完整上下文（log_id/timestamp/actor/action_type/target_resource/old_value/new_value）

**Given** 审计查询请求
**When** 审计员按时间/角色/任务类型检索
**Then** 查询结果在 5 秒内返回
**And** 日志完整性 100%（模拟 10000 次操作验证）

**Given** 日志保留策略
**When** MVP 阶段
**Then** 使用 PostgreSQL 审计表存储
**And** 支持后续升级至 7 年 WORM 存储

---

### Story 1.6: 文档上传与解析基础

As a **企业战略人员**,
I want **上传 17 种格式的文档（pdf/txt/doc/docx/ppt/pptx/xls/xlsx/csv/jpeg/png/gif/markdown/html + zip/tar 压缩包）并自动解析**,
So that **系统可以提取文本、表格、图像内容，为 RAG 检索做准备**.

**Acceptance Criteria:**

**Given** 用户选择文档
**When** 用户拖拽上传或通过 CLI 上传
**Then** 系统支持 17 种格式
**And** 解析准确率≥95%

**Given** 文档上传完成
**When** 系统解析文档
**Then** 提取文本、表格、图像、公式内容
**And** 保留文档版面信息（元素坐标 x, y, width, height），采用 DocLayNet 标准格式

**Given** 扫描件或图像 PDF
**When** 系统执行 OCR 解析
**Then** 支持中文/英文识别
**And** 提取置信度并标注（置信度<0.7 标记"需人工复核"）

---

### Story 1.7: 文档版本管理与元数据校验

As a **知识管理员**,
I want **创建文档版本快照并校验元数据**,
So that **文档变更可追溯，入库文档符合最小元字段集要求**.

**Acceptance Criteria:**

**Given** 文档变更发生
**When** 用户创建版本快照
**Then** 系统记录操作者、时间戳与差异摘要
**And** 支持版本对比（并排显示差异）

**Given** 文档入库前
**When** 系统校验元数据
**Then** 验证最小元字段集（creator/created_at/source/license/business_domain）
**And** 缺失字段时拒绝入库并提示用户补充

---

### Story 1.8: 文档语义分块

As a **RAG 工程师**,
I want **基于文档语义边界而非固定字数进行分块**,
So that **检索时可以保留完整语义上下文，提高检索相关性**.

**Acceptance Criteria:**

**Given** 文档解析完成
**When** 系统执行语义分块
**Then** 基于文档结构（章节/段落/表格边界）分块
**And** 每个分块包含完整语义（非截断）

**Given** 分块完成
**When** 生成嵌入向量
**Then** 每个分块生成一个向量
**And** 向量与分块 payload 关联存储至 Qdrant

---

## Epic 2: RAG 检索与高保真溯源

**Goal:** 实现混合检索（Dense + Sparse）、实体抽取、RRF 融合排序、分层检索、契约化摘要、相关性评估和 Bounding Box 级溯源，支持 30 秒内从结论跳转至原始文档坐标点。

**Business Value:**
- 核心差异化：30 秒溯源 vs 人工 1-2 小时，建立用户信任第一步
- 高管决策支持：快速验证数据可靠性，支撑高质量决策
- 企业战略人员效率：当场回应高管质疑，提升专业形象

**Dependencies:** Epic 1（基础架构与核心能力）

**Acceptance Criteria:**
- 检索延迟 P95 <800ms（MVP）
- Bounding Box 定位准确率≥95%
- 溯源响应时间<300ms
- 检索相关性≥0.7（LLM-as-a-Judge 评估）

---

### Story 2.1: 混合检索实现（Dense + Sparse）

As a **搜索工程师**,
I want **执行混合检索（Dense bge-m3 + BM25 稀疏检索），双路召回**,
So that **结合语义匹配和关键词匹配的优势，提高检索召回率**.

**Acceptance Criteria:**

**Given** 用户输入查询
**When** 系统执行 Dense 检索
**Then** 使用 bge-m3 嵌入模型生成查询向量
**And** 从 Qdrant 检索 Top-K 相似分块（K=50）

**Given** 用户输入查询
**When** 系统执行 Sparse 检索
**Then** 使用 BM25 算法检索关键词匹配分块
**And** 从 Elasticsearch 检索 Top-K 分块（K=50）

**Given** 双路检索完成
**When** 合并检索结果
**Then** 使用 RRF（Reciprocal Rank Fusion）融合排序
**And** 分级预算：初检 200ms + 精排 250ms + 融合 50ms（总计 500ms）

---

### Story 2.2: 实体抽取与三元组输出

As a **知识图谱工程师**,
I want **抽取实体（LLM+ 规则混合策略），输出三元组**,
So that **构建领域知识图谱，支持 GraphRAG 增强检索**.

**Acceptance Criteria:**

**Given** 文档分块完成
**When** 系统执行实体抽取
**Then** 使用 LLM+ 规则混合策略识别实体（公司名/产品名/财务指标/时间等）
**And** 输出三元组（头实体，关系，尾实体）

**Given** 实体抽取完成
**When** 存储至 Neo4j
**Then** 创建实体节点和关系边
**And** 支持实体对齐与消歧（基于编辑距离 + 语义相似度双路匹配）

---

### Story 2.3: 战略领域词典库管理

As a **领域专家**,
I want **管理战略领域词典库，支持热更新与版本管理**,
So that **检索时可以使用最新的专业术语，提高检索准确率**.

**Acceptance Criteria:**

**Given** 新术语提交
**When** 领域专家审核通过
**Then** 术语添加至词典库并生成版本号
**And** 词典库热更新（无需重启系统）

**Given** 检索请求
**When** 执行检索
**Then** 使用最新版词典库增强检索
**And** 专业术语匹配权重提升 20%

---

### Story 2.4: 三路检索融合与 RRF 排序

As a **搜索算法工程师**,
I want **融合三路检索结果（Dense + Sparse + Graph/metadata signals），使用 RRF 融合排序**,
So that **综合语义匹配、关键词匹配和图结构的优势，提高检索相关性**.

**Acceptance Criteria:**

**Given** 三路检索完成
**When** 融合检索结果
**Then** 使用 RRF（Reciprocal Rank Fusion）算法：Score = 1/(k + rank)
**And** k 值默认 60（可配置）

**Given** RRF 融合完成
**When** 输出最终排序
**Then** Top-10 分块作为检索结果
**And** 检索延迟 P95 <800ms（MVP）

---

### Story 2.5: 分层检索（L1→L2→L3→L4）

As a **系统架构师**,
I want **执行分层检索（L1 跨文档摘要→L2 文档摘要→L3 文档切片→L4 实体级片段）**,
So that **根据查询复杂度自动选择合适层级，平衡检索速度与精度**.

**Acceptance Criteria:**

**Given** 用户查询输入
**When** 系统评估查询复杂度
**Then** 自动路由至对应检索层级
**And** 简单查询（L1/L2）延迟<300ms，复杂查询（L3/L4）延迟<800ms

**Given** 分层检索执行
**When** L1 跨文档摘要检索
**Then** 返回相关文档列表及其摘要
**And** 支持逐层下钻至文档切片和实体级片段

---

### Story 2.6: 契约化结构化摘要生成

As a **产品经理**,
I want **生成契约化结构化摘要（财务/市场/技术视角），输出符合预定义 JSON Schema**,
So that **高管可以快速理解关键信息，无需阅读完整文档**.

**Acceptance Criteria:**

**Given** 检索结果返回
**When** 生成摘要
**Then** 按照预定义 JSON Schema 输出（财务视角：收入/成本/利润；市场视角：规模/增长/份额；技术视角：趋势/专利/竞争）
**And** 摘要质量评分≥0.7（信息熵 + 关键实体覆盖率）

**Given** 摘要质量评分<0.7
**When** 自动触发二次生成
**Then** 调整参数重新生成摘要
**And** 最多重试 3 次，仍失败则标记"数据不足"

---

### Story 2.7: 检索相关性评估（LLM-as-a-Judge）

As a **质量保障工程师**,
I want **评估检索相关性（LLM-as-a-Judge 实时多维评估）**,
So that **相关性<0.6 时标注"数据不足"，避免误导用户**.

**Acceptance Criteria:**

**Given** 检索结果返回
**When** 执行相关性评估
**Then** 使用 LLM 从多维度评分（语义相关性/实体覆盖率/时效性）
**And** 综合相关性<0.6 时标注"数据不足"

**Given** 相关性评估完成
**When** 记录评估结果
**Then** 存储至审计日志用于回溯分析
**And** 评估准确率≥85%（与人工标注对比）

---

### Story 2.8: Bounding Box 级溯源

As a **企业战略人员**,
I want **从结论跳转至原始文档坐标点（Bounding Box 级溯源）**,
So that **可以在 30 秒内验证数据可靠性，当场回应高管质疑**.

**Acceptance Criteria:**

**Given** 用户点击结论文字
**When** 系统弹出溯源卡片
**Then** 响应时间<300ms
**And** 卡片显示文档名称、页码、置信度（高/中/低）、原文引用

**Given** 用户点击"跳转到原始文档"
**When** 系统打开 PDF 查看器
**Then** 自动定位到第 X 页（<1 秒）
**And** 红色框高亮显示具体段落（Bounding Box 坐标：x, y, width, height）

**Given** 溯源成功
**When** 显示成功反馈
**Then** 对勾动画（200ms）+ Toast 提示"溯源成功"
**And** 定位准确率≥95%（随机抽样 100 次验证）

---

## Epic 3: 单 Agent 执行与 EIP 隔离

（继续按此格式展开所有 Epic 和 Story...）

---

**Note:** 由于文档长度限制，此处仅展示 Epic 1、Epic 2 的完整 Story 分解。后续 Epic 3-10 将按照相同格式继续展开，包含：

- **Epic 3:** 单 Agent 执行与 EIP 隔离（8 个 Story）
- **Epic 4:** BLM 战略规划流程（6 个 Story）
- **Epic 5:** 用户接口与报告生成（7 个 Story）
- **Epic 6:** 多 Agent 协作与裁决（12 个 Story）
- **Epic 7:** UDMR 动态路由与成本优化（8 个 Story）
- **Epic 8:** 完整合规与审计（8 个 Story）
- **Epic 9:** BEM 战略解码（6 个 Story）
- **Epic 10:** 企业级能力与生态集成（12 个 Story）

**总计：** 约 75-85 个 User Story，覆盖 122 项 FR 和 40 项 NFR。

---

## Menu Options

**Confirm the Requirements are complete and correct to [C] continue:**

- **C** - Continue to Step 2: Design Epics
- **Comments/Questions** - I can help clarify or adjust requirements before proceeding
