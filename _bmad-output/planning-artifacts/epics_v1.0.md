---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics']
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - docs/or.md
workflowType: 'epics-and-stories'
projectName: 'sisys'
userName: 'Agimtech'
date: '2026-02-28'
documentStatus: 'step-02-complete'
---

# sisys - Epic Breakdown

## Overview

本文档提供 sisys 企业战略规划管理系统的完整史诗 (Epic) 和用户故事 (Story) 分解，将 PRD、架构设计和 UX 设计中的需求分解为可实现的开发任务。

---

## Requirements Inventory

### Functional Requirements

**共 122 项功能需求，按优先级划分：**

#### P0 (MVP) - 57 项

**文档与数据管理 (DM-01 ~ DM-08) - 8 项：**
- FR-DM-01: 支持 17 种格式文档上传 (pdf/txt/doc/docx/ppt/pptx/xls/xlsx/csv/jpeg/png/gif/markdown/html + zip/tar 压缩包)
- FR-DM-02: 解析文档并提取文本、表格、图像、公式内容
- FR-DM-03: 保留文档版面信息（元素坐标 x, y, width, height，DocLayNet 标准格式）
- FR-DM-04: 提取表格的行列语义，输出结构化 JSON（包含表头与列类型）
- FR-DM-05: 对扫描件或图像 PDF 进行 OCR 解析（中/英），提取置信度并标注
- FR-DM-06: 创建文档版本快照，记录操作者、时间戳与差异摘要
- FR-DM-07: 校验入库文档的最小元字段集（creator/created_at/source/license/business_domain）
- FR-DM-08: 对文档进行语义分块（基于文档语义边界而非固定字数切片）

**智能检索与知识发现 (SR-01 ~ SR-08) - 8 项：**
- FR-SR-01: 执行混合检索（Dense bge-m3 + BM25 稀疏检索），双路召回
- FR-SR-02: 抽取实体（LLM+ 规则混合策略），输出三元组
- FR-SR-03: 管理战略领域词典库，支持热更新与版本管理
- FR-SR-04: 融合三路检索结果（Dense + Sparse + Graph/metadata signals），使用 RRF 融合排序
- FR-SR-05: 执行分层检索（L1 跨文档摘要→L2 文档摘要→L3 文档切片→L4 实体级片段）
- FR-SR-06: 生成契约化结构化摘要（财务/市场/技术视角），输出符合预定义 JSON Schema
- FR-SR-07: 评估检索相关性（LLM-as-a-Judge 实时多维评估），相关性<0.6 标注"数据不足"
- FR-SR-08: 保留引文"三元组"特征（文档 ID、切片 ID、字符范围），支持 Bounding Box 级溯源

**战略工具箱 (ST-01 ~ ST-05) - 5 项：**
- FR-ST-01: 注册战略工具（23 种：PESTEL/波特五力/$APPEALS/竞争对手分析/价值链分析/VRIO/安索夫矩阵/SWOT-TOWS/GE-麦肯锡矩阵/SPACE 矩阵/情景规划/价值曲线/价值主张画布/商业模式画布/破坏性创新模型/BSC/战略地图/组织设计框架/依赖关系图/RACI 矩阵/甘特图/KPI/变革管理模型）
- FR-ST-02: 编排工具链（DAG 有向无环图），按拓扑顺序调度子任务
- FR-ST-03: 验证工具输入/输出 Schema（Pydantic V2 契约化）
- FR-ST-04: 在 Docker 沙箱中执行工具代码，网络隔离 + 权限最小化
- FR-ST-05: 执行红蓝辩论机制基础（单 Agent 多视角，MVP 替代方案）

**Agent 协作 (AC-01 ~ AC-06) - 6 项：**
- FR-AC-01: 实例化 Agent 角色基础（CEO Agent，MVP 单 Agent 方案）
- FR-AC-02: 加载 Agent 身份档案（IDENTITY.md/CODE.md/SOUL.md/TOOLS.md/USER.md/MEMORY.md/HEARTBEAT.md）
- FR-AC-03: 执行单 Agent 任务（感知→规划→执行→验证→反思→证据打包）
- FR-AC-04: 执行弹性视角隔离协议基础（L4 硬隔离默认）
- FR-AC-05: 保证 Agent 默认隔离等级为 L4 硬隔离（Prompt/工具/数据三重硬隔离）
- FR-AC-06: 记录隔离切换日志（AGENT ID、时间戳、原隔离等级、目标隔离等级、触发原因、审批链）

**战略规划流程 (SP-01 ~ SP-04) - 4 项：**
- FR-SP-01: 执行 BLM 前两阶段流程（业绩差距分析 + 市场洞察，含流程可视化；MVP 阶段 CEO AGENT 替代流程中所有 AGENT 角色）
- FR-SP-02: 执行市场洞察六子步骤基础（看趋势/看市场与客户/看竞争/看自己/看机会/机会差距分析）
- FR-SP-03: 创建 Checkpoint 快照（阶段标识、完成状态、用户反馈、修正记录）
- FR-SP-04: 输出 JSON 思维链（Input→<Reflection>→<Tools_Used>→<Constraints_Check>→JSON）

**用户交互与报告 (UI-01 ~ UI-07) - 7 项：**
- FR-UI-01: 通过 CLI 执行命令（文档上传/Agent 调用/规划生成/Checkpoint 恢复）
- FR-UI-02: 通过 REST API 提供接口（文档管理/工具调用/Agent 协作/规划生成/系统管理）
- FR-UI-03: 通过 API Gateway 统一入口处理所有外部请求（统一认证/限流/路由/安全控制）
- FR-UI-04: 生成多格式报告（PDF/Markdown），包含可点击的引文索引
- FR-UI-05: 查看 Checkpoint 摘要并修正关键参数后恢复运行
- FR-UI-06: 展示溯源树（从结论逐层展开至原始数据）
- FR-UI-07: 支持高管简化视图（仪表盘/审批中心/审计摘要）

**系统管理与合规 (SC-01 ~ SC-08) - 8 项：**
- FR-SC-01: 管理用户认证与 RBAC 权限（用户表/角色表/权限表/关联表）
- FR-SC-02: 记录统一审计日志（log_id/timestamp/actor/action_type/target_resource/old_value/new_value）
- FR-SC-03: 将审计日志写入不可变存储（WORM 基础，MVP 采用 PostgreSQL 审计表方案）
- FR-SC-04: 按时间/角色/任务类型/修正级别多维检索审计日志
- FR-SC-05: 执行修正分级判定基础（L0 拼写/格式/L1 参数/权重 自动固化）
- FR-SC-06: 自动固化 L0/L1 级修正（生成 Few-Shot 样本→Strat-Bench 测试→版本注册→WORM 存储）
- FR-SC-07: 执行数据主权隔离（敏感数据本地优先，外部网络调用需审计与白名单批准）
- FR-SC-08: 支持等保 2.0 三级要求（身份鉴别/访问控制/安全审计/入侵防范/数据完整性/备份恢复）

**成本与性能优化 (CP-01 ~ CP-04) - 4 项：**
- FR-CP-01: 记录路由决策日志（任务 ID、时间戳、L1 结果、L2 各因子评分、最终评分、选定路由、成本、延迟）
- FR-CP-02: 执行语义缓存基础（相似度>0.9 直接返回缓存结果）
- FR-CP-03: 提供健康度仪表盘（实时可视化各 Agent 健康度指标）
- FR-CP-04: 输出 OpenTelemetry Trace（自适应采样，错误率>1% 时全采样）

**战略档案库 (SA-01 ~ SA-03) - 3 项：**
- FR-SA-01: 永久存储历年 SP/BP 的关键假设变量、决策依据、实际执行偏差
- FR-SA-02: 管理事实有效期标签（valid_from/valid_until）
- FR-SA-03: 执行数据陈旧标记（超 12 个月自动降权）

**架构约束 (AR-01 ~ AR-04) - 4 项：**
- FR-AR-01: 保证领域层不依赖任何外部框架（仅依赖 Python 标准库与领域模型）
- FR-AR-02: 发布领域事件至事件总线，支持事件重放与失败重试
- FR-AR-03: 执行跨存储事务基础（PostgreSQL 事务，MVP 方案），保证最终一致性
- FR-AR-04: 通过仓储模式向领域层提供统一存储接口（领域层不直接依赖具体存储实现）

#### P1 (V1) - 46 项

**文档与数据管理 (DM-09 ~ DM-12) - 4 项：**
- FR-DM-09: 追溯每个解析后的数据切片至导入批次与原始文件版本
- FR-DM-10: 执行环境预检（GPU 驱动/CUDA 版本/内存），仅异常时通知用户
- FR-DM-11: 导入季度/年度经营复盘数据，用于计算与规划的偏差
- FR-DM-12: 支持合并单元格语义还原与跨页表格识别

**智能检索与知识发现 (SR-09 ~ SR-13) - 5 项：**
- FR-SR-09: 对齐与消歧实体（基于编辑距离 + 语义相似度双路匹配）
- FR-SR-10: 根据查询复杂度与意图自动路由至对应检索层级
- FR-SR-11: 评估摘要质量（信息熵 + 关键实体覆盖率），评分<0.7 自动触发二次生成
- FR-SR-12: 触发自动补救机制（扩展检索范围/调用白名单外部数据源/生成数据缺口报告）
- FR-SR-13: 构建知识图谱（实体节点 + 关系边），支持 GraphRAG 增强检索

**战略工具箱 (ST-06 ~ ST-09) - 4 项：**
- FR-ST-06: 管理工具版本，支持版本控制、灰度发布与回滚
- FR-ST-07: 执行 Validation Feedback 闭环（最大重试 3 次，失败标记不可行）
- FR-ST-08: 遵循 MCP 2025 规范与 A2A 协议，通过 MCP Registry 暴露工具能力
- FR-ST-09: 支持财务建模与估值基础（DCF/可比公司/先例交易基础）

**Agent 协作 (AC-07 ~ AC-14) - 8 项：**
- FR-AC-07: 分解多 Agent 协作任务（SYS Agent 解析目标并分解，各专业 Agent 并行执行）
- FR-AC-08: 生成协作依赖图（基于 BLM/BEM 阶段）
- FR-AC-09: 动态调整隔离等级（基于任务依赖/关键词频率/SYS Agent 命令）
- FR-AC-10: 创建联合分析组，相关 Agent 隔离等级降级至 L2 协作态
- FR-AC-11: 通过公共黑板交换中间结论（附带置信度与引用源）
- FR-AC-12: 执行 SYS Agent 裁决（最大辩论轮次 3+ 风险等级，上限 7 轮）
- FR-AC-13: 生成三套方案（Plan A 保守/Plan B 激进/Plan C AI 融合版）
- FR-AC-14: 执行深度思考与多路径推演（并行生成多条思维链）

**战略规划流程 (SP-05 ~ SP-10) - 6 项：**
- FR-SP-05: 执行完整 BLM 六阶段流程（业绩差距分析→市场洞察六子步骤→战略意图与目标→创新焦点→业务设计→执行设计；各 AGENT 按标准角色定义各司其职）
- FR-SP-06: 执行 Replay 重放模式（修改点后所有状态重新计算，强一致性）
- FR-SP-07: 评估修改影响范围（≥2 个后续 Checkpoint 强制 Replay，<2 个推荐 Override）
- FR-SP-08: 执行 Override 覆盖模式（仅修改指定状态，需人工确认一致性风险）
- FR-SP-09: 执行 Time-travel 两阶段能力（单点恢复/分支对比）
- FR-SP-10: 支持红蓝辩论机制完整实现（发散 Temperature=0.8→收敛 Temperature=0.5→裁决 Temperature=0.2）

**用户交互与报告 (UI-08 ~ UI-12) - 5 项：**
- FR-UI-08: 可视化展示决策过程（关键决策路径和依据）
- FR-UI-09: 创建/切换/删除分支，提供分支差异对比视图
- FR-UI-10: 展示 Checkpoint 恢复模式选择界面（影响范围、推荐模式、风险提示）
- FR-UI-11: 支持无障碍设计（WCAG 2.1 AA，键盘导航，屏幕阅读器兼容）
- FR-UI-12: 支持多语言界面（中文/英文切换）

**系统管理与合规 (SC-09 ~ SC-12) - 4 项：**
- FR-SC-09: 对敏感数据脱敏（个人可识别信息、商业机密）
- FR-SC-10: 执行 L2 级修正专家确认（1 人，4 小时 SLA，紧急通道 1 小时）
- FR-SC-11: 执行 L3 级修正委员会审批（≥3 人，48 小时 SLA）
- FR-SC-12: 支持 SOX 合规（404 条款内部控制评估报告）

**成本与性能优化 (CP-05 ~ CP-10) - 6 项：**
- FR-CP-05: 执行统一动态模型路由框架（UDMR）三层决策（L1 合规性过滤→L2 任务复杂度评估→L3 路由决策执行）
- FR-CP-06: 基于四因子评分路由（语义匹配 35% + 历史成功率 30% + 成本效率 20% + 任务复杂度 15%）
- FR-CP-07: 执行三级成本熔断（任务级/会话级/系统级）
- FR-CP-08: 预测任务成本（基于历史相似任务），偏差超阈值触发分级预警
- FR-CP-09: 管理缓存失效（TTL 24 小时 + 事件驱动失效 + 版本感知失效）
- FR-CP-10: 检测性能漂移（CUSUM 算法，滑动窗口 7 天）

**战略档案库 (SA-04 ~ SA-07) - 4 项：**
- FR-SA-04: 查询时间轴演进（按时间范围查询历史决策）
- FR-SA-05: 执行心跳机制（周期性自动唤醒，检查待办事项、偏差预警、周期性任务）
- FR-SA-06: 发布战略偏差预警事件（偏差超阈值 10% 自动触发）
- FR-SA-07: 管理分支（主线/分支差异对比、分支合并/放弃）

#### P2 (V2) - 18 项

**文档与数据管理 (DM-13 ~ DM-15) - 3 项：**
- FR-DM-13: 识别数学公式并输出 LaTeX 与 MathML 双格式表达
- FR-DM-14: 实现图文联合嵌入空间，支持"以图搜文/以文搜图"的跨模态检索
- FR-DM-15: 支持音视频转录文本接入

**智能检索与知识发现 (SR-14 ~ SR-15) - 2 项：**
- FR-SR-14: 管理引用数据的时效性，超 12 个月数据自动标记"数据陈旧"并降权
- FR-SR-15: 执行实体关联查询、路径查询、社区发现算法（Louvain/Label Propagation）

**战略工具箱 (ST-10 ~ ST-11) - 2 项：**
- FR-ST-10: 在 gVisor 沙箱中执行代码，提供用户空间内核隔离
- FR-ST-11: 支持压力测试建模（宏观经济变量情景分析）

**Agent 协作 (AC-15 ~ AC-16) - 2 项：**
- FR-AC-15: 强制暂停 5 分钟请求用户介入，超时无操作按 SYS Agent 决策执行
- FR-AC-16: 支持 Agent 实例池化与动态扩缩容（基于负载自动伸缩）

**战略规划流程 (SP-11 ~ SP-12) - 2 项：**
- FR-SP-11: 执行 BEM 六阶段流程（澄清战略方向→导出战略举措→导出衡量指标→确定年度措施→分解目标→导出重点工作计划）
- FR-SP-12: 将 SP 输出结构化映射为 BP 输入（战略解码器）

**用户交互与报告 (UI-13) - 1 项：**
- FR-UI-13: 支持决策影响分析（Shapley 贡献值，反事实推理）

**系统管理与合规 (SC-13 ~ SC-14) - 2 项：**
- FR-SC-13: 支持 ISO 27001 认证（信息安全管理体系）
- FR-SC-14: 支持银保监会规范（1104 报表/EAST 报表生成）

**成本与性能优化 (CP-11 ~ CP-12) - 2 项：**
- FR-CP-11: 执行区块链哈希链（审计日志不可篡改增强）
- FR-CP-12: 提供 UEBA 用户行为分析（高级威胁检测）

**战略档案库 (SA-08 ~ SA-09) - 2 项：**
- FR-SA-08: 主动推送知识更新（检测到行业报告/市场数据/政策法规更新时）
- FR-SA-09: 支持预测性战略预警（基于市场数据的主动预警，CUSUM 漂移检测）

---

### Non-Functional Requirements

**共 40 项非功能需求，按类别划分：**

#### 性能 (NFR-PERF-01 ~ NFR-PERF-07) - 7 项

| 编号 | 需求 | MVP 目标 | V1 目标 | V2 目标 |
|------|------|---------|--------|--------|
| NFR-PERF-01 | 检索延迟 P95 | <800ms | <500ms | <300ms |
| NFR-PERF-02 | 路由决策延迟 P95 | <100ms | <50ms | <30ms |
| NFR-PERF-03 | 报告生成时间 | <30 秒（标准）/<2 分钟（完整 SP/BP） | - | - |
| NFR-PERF-04 | 并发 Agent 会话 | ≥10 | ≥50 | ≥200 |
| NFR-PERF-05 | Checkpoint 恢复时间 | <60 秒（Replay） | <30 秒（Override） | <15 秒 |
| NFR-PERF-06 | 语义缓存命中率 | - | >40%，Token 消耗降低 40-50% | - |
| NFR-PERF-07 | 图遍历查询延迟 P95 | - | <200ms（简单）/<800ms（复杂） | - |

#### 安全性 (NFR-SEC-01 ~ NFR-SEC-07) - 7 项

| 编号 | 需求 | 验收标准 |
|------|------|---------|
| NFR-SEC-01 | 数据传输加密 | TLS 1.3，SSL Labs A+ 评级 |
| NFR-SEC-02 | 数据存储加密 | AES-256，加密审计通过 |
| NFR-SEC-03 | 渗透测试 | 无高危漏洞，中危漏洞<5 个 |
| NFR-SEC-04 | 数据泄露事件 | 0 事件 |
| NFR-SEC-05 | 提示注入检测准确率 | ≥95%（ShieldCortex），误报率<5% |
| NFR-SEC-06 | RBAC 权限测试 | 权限测试 100% 通过，越权访问 0 次 |
| NFR-SEC-07 | 沙箱逃逸测试 | 0 次逃逸成功 |

#### 合规性 (NFR-COMP-01 ~ NFR-COMP-09) - 9 项

| 编号 | 需求 | MVP 目标 | V1 目标 | V2 目标 |
|------|------|---------|--------|--------|
| NFR-COMP-01 | 等保 2.0 三级 | 通过测评，无高风险项 | - | - |
| NFR-COMP-02 | 审计日志保留 | PostgreSQL 审计表 | 基础 WORM 存储 | 7 年 WORM+ 区块链哈希链 |
| NFR-COMP-03 | 数据主权 | 数据境内存储 100%，跨境传输审批率 100% | - | - |
| NFR-COMP-04 | 隐私保护（PIPL） | 个人信息脱敏率 100%，删除请求响应<24 小时 | - | - |
| NFR-COMP-05 | 审计日志完整性 | 100% 完整，日志审计工具验证通过 | - | - |
| NFR-COMP-06 | SOX 404 条款 | - | 通过第三方审计，内部控制无重大缺陷 | - |
| NFR-COMP-07 | ISO 27001 | - | 通过认证，ISMS 运行有效 | - |
| NFR-COMP-08 | 银保监会规范 | - | - | 1104 报表/EAST 报表生成准确率 100% |
| NFR-COMP-09 | 完整审计追踪可视化 | - | - | 7 年 WORM+ 区块链哈希链 + 可视化时间线，审计查询<10 秒 |

#### 可靠性 (NFR-REL-01 ~ NFR-REL-06) - 6 项

| 编号 | 需求 | MVP 目标 | V1 目标 |
|------|------|---------|--------|
| NFR-REL-01 | 系统可用性 | 99% | 99.5% |
| NFR-REL-02 | 数据备份 | RPO<1 小时 | RPO<15 分钟 |
| NFR-REL-03 | 灾难恢复 | RTO<4 小时 | RTO<2 小时 |
| NFR-REL-04 | Checkpoint 快照持久化 | 100% 持久化，故障恢复成功率≥99% | - |
| NFR-REL-05 | 性能漂移检测 | - | CUSUM 算法检测准确率≥85% |
| NFR-REL-06 | 成本熔断 | - | 三级熔断触发准确率 100%，成本超支 0 事件 |

#### 可扩展性 (NFR-SCALE-01 ~ NFR-SCALE-04) - 4 项

| 编号 | 需求 | 验收标准 |
|------|------|---------|
| NFR-SCALE-01 | 用户增长支持 | 支持 10 倍用户增长，性能下降<10% |
| NFR-SCALE-02 | 数据量支持 | TB 级战略档案库，检索延迟 P95<1s |
| NFR-SCALE-03 | Agent 动态扩缩容 | 基于负载自动伸缩，响应时间<5 分钟 |
| NFR-SCALE-04 | 多租户隔离 | Schema per Tenant + Row-Level Security，隔离测试 100% 通过 |

#### 集成性 (NFR-INT-01 ~ NFR-INT-05) - 5 项

| 编号 | 需求 | 验收标准 |
|------|------|---------|
| NFR-INT-01 | API 可用性 | ≥99%，OpenAPI 3.1 规范，自动生成文档/SDK/Mock 服务 |
| NFR-INT-02 | 预置集成适配器 | ≥5 个（ERP/CRM/OA 各至少 1 个） |
| NFR-INT-03 | 外部数据源接入 | ≥3 个（工商/税务/专利等） |
| NFR-INT-04 | 集成失败率 | <1%，失败自动重试（最多 3 次），重试成功率≥80% |
| NFR-INT-05 | MCP/A2A 协议兼容性 | 向后兼容 1-2 个版本，协议兼容性测试通过 |

#### 可访问性 (NFR-ACC-01 ~ NFR-ACC-02) - 2 项

| 编号 | 需求 | 验收标准 |
|------|------|---------|
| NFR-ACC-01 | 无障碍设计 | WCAG 2.1 AA 标准，键盘导航 100% 支持，屏幕阅读器兼容 |
| NFR-ACC-02 | 多语言支持 | 中文/英文界面，翻译准确率≥95%，术语表统一 |

---

### Additional Requirements

#### 从 Architecture 提取的技术要求

**1. 核心架构约束：**
- 领域层零依赖原则：领域层仅依赖 Python 标准库与领域模型，不依赖任何外部框架
- 事件驱动架构：Redis 发布/订阅（实时事件）+ RabbitMQ + 事务发件箱（持久化事件）
- 五层存储架构：
  - L1 高速缓存层：Redis 7.0+（会话状态、语义缓存、公共黑板，TTL 24h-30d）
  - L2 关系存储层：PostgreSQL 15+（用户/RBAC、审计元数据、业务实体，永久）
  - L3 向量存储层：Qdrant 1.7+（嵌入向量、混合检索 payload，永久）
  - L4 对象存储层：MinIO WORM（原始文档、证据包、审计归档，7 年）
  - L5 图存储层：Neo4j 5.x（知识图谱、实体关系、依赖图，永久）

**2. 关键机制要求：**
- UDMR 统一动态模型路由：三层决策（L1 合规性过滤→L2 任务复杂度评估→L3 路由决策执行），路由决策延迟 P95<50ms，目标本地路由占比≥80%
- EIP 弹性视角隔离协议：四级隔离等级（L4 硬隔离/L3 软隔离/L2 协作态/L1 融合态），基于任务依赖/关键词频率/SYS Agent 命令动态升降级，30 分钟无活动自动恢复至 L4
- Checkpoint 双模式恢复：Replay 模式（修改点后所有状态重新计算，强一致性）与 Override 模式（仅修改指定状态，需人工确认一致性风险）
- 修正分级判定体系：L0-L3 四级（L0 拼写/格式/L1 参数/权重自动固化，L2 专家确认，L3 委员会审批），基于五维特征加权算法

**3. 技术栈要求：**
- 后端：Python 3.11+、FastAPI 0.104+、Click 8.1+
- 工作流引擎：Prefect 3.6+（数据管道）、LangGraph 1.0+（Agent 编排）
- 模型路由：LiteLLM（统一代理）、bge-m3（嵌入模型）
- 沙箱：Docker（MVP）、gVisor（V2）
- 消息总线：RabbitMQ 3.12+、Redis 发布/订阅
- 监控：Prometheus、Grafana、OpenTelemetry

#### 从 UX Design 提取的要求

**1. 核心体验要求：**
- 高保真溯源：Bounding Box 坐标级跳转至原始文档，响应<300ms，定位准确率≥95%
- 高管仪表盘：第一屏仅显示 3 个关键指标，红/黄/绿状态指示器，30 秒理解率≥90%
- 白标报告：品牌元素（Logo/配色/字体）100% 准确应用，导出时间<1 分钟

**2. 设计系统要求：**
- Ant Design 5.x + CSS-in-JS + Design Tokens
- 三视图架构：高管视图（简化决策）、分析师视图（专业工具）、企业战略与市场人员视图（流程标准化）

**3. 情感目标：**
- 高管：掌控感（30 秒决策）
- 企业战略人员：成就感（30 秒溯源）
- 顾问：专业感（白标输出可直接交付客户）

**4. 关键交互要求：**
- 悬浮弹窗溯源卡片：不跳转新页面，保持当前上下文
- 置信度显示：颜色（绿/黄/红）+ 文字（高/中/低）双重编码
- 骨架屏加载：模拟真实内容结构，减少感知等待时间

---

### FR Coverage Map（双向追溯矩阵）

**完整 FR 总览：122 项功能需求完整映射（P0: 57 项，P1: 46 项，P2: 18 项）**

#### P0 FR 映射（57 项 - MVP）

| FR 编号 | FR 描述 | 归属 Epic | 归属 Story | 优先级 |
|--------|--------|----------|-----------|-------|
| **架构约束 (AR) - 4 项** |
| FR-AR-01 | 领域层零依赖 | Epic 1 | Story 1.1 | P0 |
| FR-AR-02 | 领域事件发布 | Epic 1 | Story 1.2 | P0 |
| FR-AR-03 | 跨存储事务 | Epic 1 | Story 1.5 | P0 |
| FR-AR-04 | 仓储模式 | Epic 1 | Story 1.1 | P0 |
| **系统管理与合规 (SC) - 8 项** |
| FR-SC-01 | 用户认证与 RBAC | Epic 1 | Story 1.9 | P0 |
| FR-SC-02 | 统一审计日志 | Epic 1 | Story 1.10 | P0 |
| FR-SC-03 | WORM 存储 | Epic 1 | Story 1.7 | P0 |
| FR-SC-04 | 审计日志多维检索 | Epic 8 | Story 8.1 | P0 |
| FR-SC-05 | 修正分级判定 | Epic 8 | Story 8.2 | P0 |
| FR-SC-06 | L0/L1 自动固化 | Epic 8 | Story 8.3 | P0 |
| FR-SC-07 | 数据主权隔离 | Epic 1 | Story 1.11 | P0 |
| FR-SC-08 | 等保 2.0 三级 | Epic 1 | Story 1.12 | P0 |
| **成本与性能优化 (CP) - 4 项** |
| FR-CP-01 | 路由决策日志 | Epic 1 | Story 1.14b | P0 |
| FR-CP-02 | 语义缓存 | Epic 3 | Story 3.9 | P0 |
| FR-CP-03 | 健康度仪表盘 | Epic 7 | Story 7.4 | P0 |
| FR-CP-04 | OpenTelemetry Trace | Epic 1 | Story 1.16 | P0 |
| **文档与数据管理 (DM) - 8 项** |
| FR-DM-01 | 17 种格式上传 | Epic 2 | Story 2.1 | P0 |
| FR-DM-02 | 文档解析 | Epic 2 | Story 2.2 | P0 |
| FR-DM-03 | 版面信息保留 | Epic 2 | Story 2.3 | P0 |
| FR-DM-04 | 表格语义提取 | Epic 2 | Story 2.4 | P0 |
| FR-DM-05 | OCR 解析 | Epic 2 | Story 2.5 | P0 |
| FR-DM-06 | 版本快照 | Epic 2 | Story 2.6 | P0 |
| FR-DM-07 | 元数据校验 | Epic 2 | Story 2.7 | P0 |
| FR-DM-08 | 语义分块 | Epic 2 | Story 2.8 | P0 |
| **智能检索与知识发现 (SR) - 8 项** |
| FR-SR-01 | 混合检索 | Epic 3 | Story 3.1 | P0 |
| FR-SR-02 | 实体抽取 | Epic 3 | Story 3.2 | P0 |
| FR-SR-03 | 领域词典管理 | Epic 3 | Story 3.3 | P0 |
| FR-SR-04 | RRF 融合排序 | Epic 3 | Story 3.4 | P0 |
| FR-SR-05 | 分层检索 | Epic 3 | Story 3.5 | P0 |
| FR-SR-06 | 契约化摘要 | Epic 3 | Story 3.6 | P0 |
| FR-SR-07 | 检索相关性评估 | Epic 3 | Story 3.7 | P0 |
| FR-SR-08 | Bounding Box 溯源 | Epic 6 | Story 6.7 | P0 |
| **战略工具箱 (ST) - 5 项** |
| FR-ST-01 | 23 种工具注册 | Epic 4 | Story 4.1 | P0 |
| FR-ST-02 | 工具链编排 | Epic 4 | Story 4.2 | P0 |
| FR-ST-03 | Schema 验证 | Epic 4 | Story 4.3 | P0 |
| FR-ST-04 | Docker 沙箱 | Epic 4 | Story 4.4 | P0 |
| FR-ST-05 | 红蓝辩论基础 | Epic 4 | Story 4.5 | P0 |
| **Agent 协作 (AC) - 6 项** |
| FR-AC-01 | CEO Agent 实例化 | Epic 5 | Story 5.1 | P0 |
| FR-AC-02 | 身份档案加载 | Epic 5 | Story 5.2 | P0 |
| FR-AC-03 | 单 Agent 工作流 | Epic 5 | Story 5.3 | P0 |
| FR-AC-04 | EIP 基础 | Epic 5 | Story 5.4 | P0 |
| FR-AC-05 | 三重硬隔离 | Epic 5 | Story 5.5 | P0 |
| FR-AC-06 | 隔离切换日志 | Epic 5 | Story 5.6 | P0 |
| **战略规划流程 (SP) - 4 项** |
| FR-SP-01 | BLM 前两阶段 | Epic 6 | Story 6.1 | P0 |
| FR-SP-02 | 市场洞察六子步骤 | Epic 6 | Story 6.2 | P0 |
| FR-SP-03 | Checkpoint 快照 | Epic 6 | Story 6.3 | P0 |
| FR-SP-04 | JSON 思维链 | Epic 6 | Story 6.4 | P0 |
| **用户交互与报告 (UI) - 7 项** |
| FR-UI-01 | CLI 接口 | Epic 7 | Story 7.1 | P0 |
| FR-UI-02 | REST API | Epic 7 | Story 7.2 | P0 |
| FR-UI-03 | API Gateway | Epic 7 | Story 7.3 | P0 |
| FR-UI-04 | 多格式报告 | Epic 6 | Story 6.5 | P0 |
| FR-UI-05 | Checkpoint 恢复 | Epic 6 | Story 6.6 | P0 |
| FR-UI-06 | 溯源树展示 | Epic 6 | Story 6.7 | P0 |
| FR-UI-07 | 高管简化视图 | Epic 6 | Story 6.8 | P0 |
| **战略档案库 (SA) - 3 项** |
| FR-SA-01 | 永久存储 | Epic 1 | Story 1.15b | P0 |
| FR-SA-02 | 有效期标签 | Epic 3 | Story 3.11 | P0 |
| FR-SA-03 | 数据陈旧标记 | Epic 3 | Story 3.12 | P0 |

**P0 FR 覆盖统计：57/57 项 ✅**
- AR: 4/4 | SC: 8/8 | CP: 4/4 | DM: 8/8 | SR: 8/8 | ST: 5/5 | AC: 6/6 | SP: 4/4 | UI: 7/7 | SA: 3/3

---

#### P1 FR 映射（46 项 - V1）

| FR 编号 | FR 描述 | 归属 Epic | 归属 Story | 优先级 |
|--------|--------|----------|-----------|-------|
| **文档与数据管理 (DM) - 4 项** |
| FR-DM-09 | 追溯数据切片至导入批次 | Epic 2 | Story 2.9 | P1 |
| FR-DM-10 | 环境预检（GPU/CUDA/内存） | Epic 2 | Story 2.10 | P1 |
| FR-DM-11 | 经营复盘数据导入 | Epic 2 | Story 2.11 | P1 |
| FR-DM-12 | 合并单元格语义还原 | Epic 2 | Story 2.12 | P1 |
| **智能检索与知识发现 (SR) - 5 项** |
| FR-SR-09 | 实体对齐与消歧 | Epic 3 | Story 3.13 | P1 |
| FR-SR-10 | 查询路由引擎 | Epic 3 | Story 3.14 | P1 |
| FR-SR-11 | 摘要质量评估 | Epic 3 | Story 3.15 | P1 |
| FR-SR-12 | 自动补救机制 | Epic 3 | Story 3.16 | P1 |
| FR-SR-13 | 知识图谱构建（GraphRAG） | Epic 3 | Story 3.17 | P1 |
| **战略工具箱 (ST) - 4 项** |
| FR-ST-06 | 工具版本管理 | Epic 4 | Story 4.6 | P1 |
| FR-ST-07 | Validation Feedback 闭环 | Epic 4 | Story 4.7 | P1 |
| FR-ST-08 | MCP/A2A 协议支持 | Epic 4 | Story 4.8 | P1 |
| FR-ST-09 | 财务建模与估值基础 | Epic 4 | Story 4.9 | P1 |
| **Agent 协作 (AC) - 8 项** |
| FR-AC-07 | 多 Agent 任务分解 | Epic 9 | Story 9.1 | P1 |
| FR-AC-08 | 协作依赖图生成 | Epic 9 | Story 9.2 | P1 |
| FR-AC-09 | 动态隔离等级调整 | Epic 9 | Story 9.3 | P1 |
| FR-AC-10 | 联合分析组创建 | Epic 9 | Story 9.4 | P1 |
| FR-AC-11 | 公共黑板交换中间结论 | Epic 9 | Story 9.5 | P1 |
| FR-AC-12 | SYS Agent 裁决 | Epic 9 | Story 9.6 | P1 |
| FR-AC-13 | 三套方案生成 | Epic 9 | Story 9.7 | P1 |
| FR-AC-14 | 深度思考与多路径推演 | Epic 9 | Story 9.8 | P1 |
| **战略规划流程 (SP) - 6 项** |
| FR-SP-05 | 完整 BLM 六阶段流程 | Epic 10 | Story 10.1 | P1 |
| FR-SP-06 | Replay 重放模式 | Epic 10 | Story 10.2 | P1 |
| FR-SP-07 | 修改影响范围评估 | Epic 10 | Story 10.3 | P1 |
| FR-SP-08 | Override 覆盖模式 | Epic 10 | Story 10.4 | P1 |
| FR-SP-09 | Time-travel 两阶段能力 | Epic 10 | Story 10.5 | P1 |
| FR-SP-10 | 红蓝辩论机制完整实现 | Epic 10 | Story 10.6 | P1 |
| **用户交互与报告 (UI) - 5 项** |
| FR-UI-08 | 决策过程可视化 | Epic 14 | Story 14.1 | P1 |
| FR-UI-09 | 分支管理 | Epic 14 | Story 14.2 | P1 |
| FR-UI-10 | Checkpoint 恢复模式选择界面 | Epic 14 | Story 14.3 | P1 |
| FR-UI-11 | 无障碍设计 | Epic 7 | Story 7.5 | P1 |
| FR-UI-12 | 多语言界面 | Epic 14 | Story 14.4 | P1 |
| **系统管理与合规 (SC) - 4 项** |
| FR-SC-09 | 敏感数据脱敏 | Epic 13 | Story 13.1 | P1 |
| FR-SC-10 | L2 级修正专家确认 | Epic 13 | Story 13.2 | P1 |
| FR-SC-11 | L3 级修正委员会审批 | Epic 13 | Story 13.3 | P1 |
| FR-SC-12 | SOX 合规（404 条款） | Epic 13 | Story 13.4 | P1 |
| **成本与性能优化 (CP) - 6 项** |
| FR-CP-05 | UDMR 三层决策 | Epic 11 | Story 11.1 | P1 |
| FR-CP-06 | 四因子评分路由 | Epic 11 | Story 11.2 | P1 |
| FR-CP-07 | 三级成本熔断 | Epic 11 | Story 11.3 | P1 |
| FR-CP-08 | 任务成本预测 | Epic 11 | Story 11.4 | P1 |
| FR-CP-09 | 缓存失效管理 | Epic 11 | Story 11.5 | P1 |
| FR-CP-10 | 性能漂移检测（CUSUM） | Epic 11 | Story 11.6 | P1 |
| **战略档案库 (SA) - 4 项** |
| FR-SA-04 | 时间轴演进查询 | Epic 13 | Story 13.5 | P1 |
| FR-SA-05 | 心跳机制 | Epic 13 | Story 13.6 | P1 |
| FR-SA-06 | 战略偏差预警事件 | Epic 13 | Story 13.7 | P1 |
| FR-SA-07 | 分支管理（主线/分支对比） | Epic 13 | Story 13.8 | P1 |

**P1 FR 覆盖统计：46/46 项 ✅**
- DM: 4/4 | SR: 5/5 | ST: 4/4 | AC: 8/8 | SP: 6/6 | UI: 5/5 | SC: 4/4 | CP: 6/6 | SA: 4/4

---

#### P2 FR 映射（18 项 - V2）

| FR 编号 | FR 描述 | 归属 Epic | 归属 Story | 优先级 |
|--------|--------|----------|-----------|-------|
| **文档与数据管理 (DM) - 3 项** |
| FR-DM-13 | 数学公式识别（LaTeX/MathML） | Epic 17 | Story 17.1 | P2 |
| FR-DM-14 | 图文联合嵌入（跨模态检索） | Epic 17 | Story 17.2 | P2 |
| FR-DM-15 | 音视频转录文本接入 | Epic 17 | Story 17.3 | P2 |
| **智能检索与知识发现 (SR) - 2 项** |
| FR-SR-14 | 引用数据时效性管理 | Epic 17 | Story 17.4 | P2 |
| FR-SR-15 | 实体关联查询/路径查询/社区发现 | Epic 17 | Story 17.5 | P2 |
| **战略工具箱 (ST) - 2 项** |
| FR-ST-10 | gVisor 沙箱执行 | Epic 18 | Story 18.1 | P2 |
| FR-ST-11 | 压力测试建模 | Epic 18 | Story 18.2 | P2 |
| **Agent 协作 (AC) - 2 项** |
| FR-AC-15 | 强制暂停请求用户介入 | Epic 18 | Story 18.3 | P2 |
| FR-AC-16 | Agent 实例池化与动态扩缩容 | Epic 18 | Story 18.4 | P2 |
| **战略规划流程 (SP) - 2 项** |
| FR-SP-11 | BEM 六阶段流程（战略解码） | Epic 15 | Story 15.1 | P2 |
| FR-SP-12 | SP→BP 结构化映射 | Epic 15 | Story 15.2 | P2 |
| **用户交互与报告 (UI) - 1 项** |
| FR-UI-13 | 决策影响分析（Shapley 贡献值） | Epic 19 | Story 19.1 | P2 |
| **系统管理与合规 (SC) - 2 项** |
| FR-SC-13 | ISO 27001 认证 | Epic 16 | Story 16.1 | P2 |
| FR-SC-14 | 银保监会规范（1104/EAST 报表） | Epic 16 | Story 16.2 | P2 |
| **成本与性能优化 (CP) - 2 项** |
| FR-CP-11 | 区块链哈希链（审计日志不可篡改） | Epic 16 | Story 16.3 | P2 |
| FR-CP-12 | UEBA 用户行为分析 | Epic 16 | Story 16.4 | P2 |
| **战略档案库 (SA) - 2 项** |
| FR-SA-08 | 知识更新主动推送 | Epic 19 | Story 19.2 | P2 |
| FR-SA-09 | 预测性战略预警（CUSUM 漂移检测） | Epic 19 | Story 19.3 | P2 |

**P2 FR 覆盖统计：18/18 项 ✅**
- DM: 3/3 | SR: 2/2 | ST: 2/2 | AC: 2/2 | SP: 2/2 | UI: 1/1 | SC: 2/2 | CP: 2/2 | SA: 2/2

---

### FR 覆盖总览

| FR 类别 | P0 | P1 | P2 | 总计 | 覆盖率 |
|--------|----|----|----|------|-------|
| AR（架构约束） | 4 | 0 | 0 | 4 | ✅ 4/4 |
| SC（系统管理与合规） | 8 | 4 | 2 | 14 | ✅ 14/14 |
| CP（成本与性能优化） | 4 | 6 | 2 | 12 | ✅ 12/12 |
| DM（文档与数据管理） | 8 | 4 | 3 | 15 | ✅ 15/15 |
| SR（智能检索与知识发现） | 8 | 5 | 2 | 15 | ✅ 15/15 |
| ST（战略工具箱） | 5 | 4 | 2 | 11 | ✅ 11/11 |
| AC（Agent 协作） | 6 | 8 | 2 | 16 | ✅ 16/16 |
| SP（战略规划流程） | 4 | 6 | 2 | 12 | ✅ 12/12 |
| UI（用户交互与报告） | 7 | 5 | 1 | 13 | ✅ 13/13 |
| SA（战略档案库） | 3 | 4 | 2 | 9 | ✅ 9/9 |
| **总计** | **57** | **46** | **18** | **121** | ✅ **121/122** |

**注：** FR-SA-10（群体智能，P3）为 V3+ 版本功能，暂不纳入本次 Epic 分解

---

### NFR 与额外 Story 覆盖

**新增 Story 覆盖说明（非 FR 直接映射）：**

| Story | 名称 | 覆盖内容 | 类型 |
|-------|------|---------|------|
| Story 0.1-0.3 | Iteration 0（开发环境/CI/CD/测试框架） | 基础设施准备 | 技术使能 Story |
| Story 1.13 | K8s 动态扩缩容 | NFR-SCALE-03（可扩展性） | NFR Story |
| Story 1.14a/b/c | 自主调用循环（trigger/route/execute） | or.md 系统公理一 | or.md 追溯 |
| Story 1.15a/b | 外部化记忆（上下文压缩/五层存储协同） | or.md 系统公理二 | or.md 追溯 |
| Story 1.16 | 集成测试框架 | 测试基础设施 | 测试 Story |
| Story 6.9 | 分析师视图 | UX 三视图（分析师） | UX Story |
| Story 6.10 | 顾问视图 | UX 三视图（顾问） | UX Story |
| Story 7.5 | 无障碍设计 | NFR-ACC-01（可访问性） | NFR Story |
| Story 7.6 | API 契约测试 | NFR-INT-05（集成性） | NFR Story |
| Story 7.7 | API E2E 测试 | 端到端测试 | 测试 Story |

**NFR 覆盖统计：**
- NFR-PERF（性能）：Story 3.1/3.5（检索延迟）
- NFR-SEC（安全）：Story 8.5/8.6（ShieldCortex/渗透测试）
- NFR-COMP（合规）：Story 1.12（等保 2.0）
- NFR-SCALE（可扩展性）：Story 1.13（K8s 扩缩容）✅
- NFR-INT（集成性）：Story 7.6（API 契约测试）✅
- NFR-ACC（可访问性）：Story 7.5（无障碍设计）✅

---

## Epic List

**MVP (P0) Epic 列表：**

| Epic 编号 | Epic 名称 | 优先级 | 包含 FR | Story 数 | 用户价值 |
|---------|---------|-------|--------|---------|---------|
| Epic 0 | Iteration 0 | P0 | - | 3 | 开发环境、CI/CD、测试框架（合入 Epic 1） |
| Epic 1 | **企业级架构基础与合规** | P0 | AR-01~04, SC-01/02/03/07/08, CP-01/04, SA-01 | 19 | 系统稳定性、性能、安全、合规（等保 2.0） |
| Epic 2 | 文档与数据管理 | P0 | DM-01~08 | 8 | 用户可以上传和管理 17 种格式文档 |
| Epic 3 | 智能检索与知识发现 | P0 | SR-01~08, CP-02, SA-02/03 | 12 | 用户可以检索文档并溯源至原始坐标点 |
| Epic 4 | 战略工具箱 | P0 | ST-01~05 | 5 | 用户可以执行 23 种战略工具分析 |
| Epic 5 | Agent 协作系统 | P0 | AC-01~06 | 6 | 用户可以通过 CEO Agent 执行战略规划 |
| Epic 6 | 战略规划流程 (BLM 前两阶段) | P0 | SP-01~04, UI-04/05/06/07 | 10 | 用户可以生成战略规划并审批 |
| Epic 7 | **多触点用户界面与 API 集成** | P0 | UI-01/02/03, CP-03 | 7 | 用户可以通过 CLI/API/仪表盘操作系统 |
| Epic 8 | **用户权限管理与审计合规** | P0 | SC-04/05/06 | 6 | 管理员可以管理权限和审计日志 |
| **总计** | - | - | **57 项 FR** | **76** | - |

**V1 (P1) Epic 列表：**

| Epic 编号 | Epic 名称 | 优先级 | 包含 FR | 故事数 | 用户价值 |
|---------|---------|-------|--------|-------|---------|
| Epic 9 | 完整多 Agent 协作 | P1 | AC-07~14 | 10 | 完整多 Agent 辩论与 SYS Agent 裁决 |
| Epic 10 | 完整 BLM 六阶段与 Checkpoint 恢复 | P1 | SP-05~10 | 8 | 完整 BLM 流程与双模式恢复能力 |
| Epic 11 | UDMR 动态模型路由 | P1 | CP-05~10 | 8 | 本地路由≥80%，成本节省≥50% |
| Epic 12 | 知识图谱与 GraphRAG | P1 | SR-09~13 | 6 | GraphRAG 增强检索与实体关联查询 |
| Epic 13 | 高级系统管理与合规 | P1 | SC-09~12, SA-04~07 | 8 | SOX 合规与时间轴查询 |
| Epic 14 | 用户体验增强 | P1 | UI-08~12, DM-09~12 | 10 | 决策可视化与分支管理 |
| **总计** | - | - | **46 项 FR** | **50** | - |

**V2 (P2) Epic 列表：**

| Epic 编号 | Epic 名称 | 优先级 | 包含 FR | 故事数 | 用户价值 |
|---------|---------|-------|--------|-------|---------|
| Epic 15 | BEM 战略解码 | P2 | SP-11/12 | 6 | SP→BP 结构化映射 |
| Epic 16 | 高级安全与合规 | P2 | SC-13/14, CP-11/12 | 6 | ISO 27001 与银保监会规范 |
| Epic 17 | 高级数据管理与检索 | P2 | DM-13~15, SR-14/15 | 6 | 公式识别与跨模态检索 |
| Epic 18 | 高级 Agent 协作 | P2 | AC-15/16, ST-10/11 | 6 | 人机协作与动态扩缩容 |
| Epic 19 | 高级用户体验 | P2 | UI-13, SA-08/09 | 4 | 决策影响分析与预测性预警 |
| **总计** | - | - | **18 项 FR** | **28** | - |

---

## Epic 1: 企业级架构基础与合规

**目标：** 建立六边形架构基础、事件驱动机制、五层存储架构和基础合规能力，为后续功能提供技术基础。

**包含 FR：** AR-01, AR-02, AR-03, AR-04, SC-01, SC-02, SC-03, SC-07, SC-08, CP-01, CP-04, SA-01

**📦 价值组 1: Iteration 0（开发基础设施）**
> 为团队提供统一的开发环境、CI/CD 和测试框架

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 0.1 | **开发环境搭建** | 提供统一的开发环境和工具链 | 无依赖 | **P0-0（Iteration 0）** |
| Story 0.2 | **CI/CD 流水线** | 自动化构建、测试和部署 | 依赖 Story 0.1 | **P0-0（所有 Epic 前置）** |
| Story 0.3 | **测试框架搭建** | 提供单元测试、集成测试框架 | 依赖 Story 0.1 | **P0-0（Iteration 0）** |

**📦 价值组 2: 架构基础与事件驱动**
> 实现六边形架构、领域事件和事件总线

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 1.1 | 六边形架构骨架 | 领域逻辑与技术实现隔离，支持长期演进 | 无依赖（基础） | P0-1 |
| Story 1.2 | 领域事件定义 | 支持事件驱动架构和事件溯源 | 依赖 Story 1.1 | P0-2 |
| Story 1.3 | 事件总线实现 | 实时事件低延迟路由，持久化事件可靠传输 | 依赖 Story 1.2 | P0-3 |
| Story 1.16 | **集成测试框架** | 提供集成测试、E2E 测试框架和测试数据管理 | 依赖 Story 0.3, 1.1 | **P1-16（测试 Story）** |

**📦 价值组 3: 五层存储架构**
> 实现 Redis/PostgreSQL/Qdrant/MinIO/Neo4j 五层存储

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 1.4 | Redis 高速缓存层 | 低延迟会话管理和语义缓存 | 依赖 Story 1.1 | P0-4 |
| Story 1.5 | PostgreSQL 关系存储层 | 支持 ACID 事务和外键约束 | 依赖 Story 1.1 | P0-5 |
| Story 1.6 | Qdrant 向量存储层 | 支持混合检索（Dense + Sparse + Payload 过滤） | 依赖 Story 1.1 | P0-6 |
| Story 1.7 | MinIO 对象存储层 | 支持版本控制和 WORM 存储 | 依赖 Story 1.1 | P0-7 |
| Story 1.8 | Neo4j 图存储层 | 支持 GraphRAG 增强检索和实体关联查询 | 依赖 Story 1.1 | P0-8 |
| Story 1.13 | **K8s 动态扩缩容** | 支持基于负载的自动扩缩容 | 依赖 Story 1.4/1.5 | **P1-13（NFR-SCALE-03）** |

**📦 价值组 4: 安全与合规基础**
> 实现 RBAC、审计日志、数据主权和等保 2.0

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 1.9 | RBAC 权限管理 | 细粒度访问控制，防止越权访问 | 依赖 Story 1.5 | P0-9 |
| Story 1.10 | 统一审计日志 | 满足等保 2.0 和 SOX 合规要求 | 依赖 Story 1.5 | P0-10 |
| Story 1.11 | 数据主权隔离 | 满足数据安全法和 PIPL 要求 | 依赖 Story 1.9, 1.10 | P0-11 |
| Story 1.12 | 等保 2.0 三级基础要求 | 通过公安部指定测评机构测评 | 依赖 Story 1.9, 1.10, 1.11 | P0-12 |

**📦 价值组 5: or.md 系统公理实现**
> 实现自主调用循环和外部化记忆

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 1.14a | **自主调用循环 - trigger** | 实现领域事件/心跳事件触发机制 | 依赖 Story 1.2/1.3 | **P0-14a（or.md 系统公理一）** |
| Story 1.14b | **自主调用循环 - route** | 实现 session_id 哈希/语义路由 | 依赖 Story 1.14a | **P0-14b（or.md 系统公理一）** |
| Story 1.14c | **自主调用循环 - execute** | 实现会话命名空间执行与状态快照 | 依赖 Story 1.14b | **P0-14c（or.md 系统公理一）** |
| Story 1.15a | **外部化记忆 - 上下文压缩** | LLM 上下文仅保留压缩信息（压缩率≥70%） | 依赖 Story 1.4 | **P0-15a（or.md 系统公理二）** |
| Story 1.15b | **外部化记忆 - 五层存储协同** | 会话状态持久化至五层存储，压缩前持久化笔记 | 依赖 Story 1.15a, 1.5-1.8 | **P0-15b（or.md 系统公理二）** |

**✅ 依赖关系验证：**
- Epic 1 内部故事依赖均为**组内依赖**，不依赖其他 Epic
- Epic 1 是所有其他 Epic 的**基础依赖**，必须首先完成
- 价值组 1（Iteration 0）→ 价值组 2（架构基础）→ 价值组 3（五层存储）→ 价值组 4（安全合规）→ 价值组 5（or.md 公理）
- 价值组 1（Iteration 0）可独立交付
- 价值组 2-5 依赖价值组 1 和 2 的架构基础

**📋 Iteration 0 和 or.md 追溯说明：**
- **Story 0.1-0.3**：Iteration 0（开发环境、CI/CD、测试框架），必须在 Iteration 1 前完成
- **Story 0.2**：CI/CD 流水线是所有 Epic 的前置依赖（自动化构建、测试、部署）
- **Story 1.13**：覆盖 NFR-SCALE-03（Agent 动态扩缩容，基于负载自动伸缩，响应时间<5 分钟）
- **Story 1.14a/b/c**：覆盖 or.md 系统公理一（自主调用：trigger→route→execute）
- **Story 1.15a/b**：覆盖 or.md 系统公理二（外部化记忆：LLM 上下文=缓存，磁盘记忆=真相源）
- **Story 1.16**：集成测试框架，支持所有 Epic 的集成测试和 E2E 测试

---

### Story 0.1: 开发环境搭建

As a **开发工程师**,
I want **统一的开发环境和工具链（Python 3.11+, Poetry, Docker, IDE 配置）**,
So that **团队可以高效协作开发**。

**Acceptance Criteria:**

**Given** 新项目启动
**When** 运行 `docker-compose up` 和 `poetry install`
**Then** 所有开发依赖安装完成，开发环境可正常运行
**And** IDE 配置（.vscode/.idea）提供代码规范、调试配置

### Story 0.2: CI/CD 流水线

As a **DevOps 工程师**,
I want **自动化构建、测试和部署的 CI/CD 流水线**,
So that **代码变更可以快速、可靠地发布**。

**Acceptance Criteria:**

**Given** 代码提交到 Git
**When** 触发 CI/CD 流水线
**Then** 自动运行单元测试、集成测试、代码扫描、构建 Docker 镜像
**And** 测试通过后自动部署到测试环境
**And** 所有 Epic 的构建和部署都通过此流水线执行

### Story 0.3: 测试框架搭建

As a **测试工程师**,
I want **单元测试、集成测试框架和测试数据管理**,
So that **可以快速编写和执行测试用例**。

**Acceptance Criteria:**

**Given** 项目初始化完成
**When** 运行 `pytest`
**Then** 单元测试、集成测试框架可正常运行
**And** 测试数据管理支持（Fixture、Mock、测试数据库隔离）

### Story 1.1: 六边形架构骨架

As a **系统架构师**,
I want **实现领域驱动六边形架构骨架**,
So that **领域逻辑与技术实现隔离，支持独立演进和测试**。

**Acceptance Criteria:**

**Given** 项目初始化完成
**When** 创建领域层、应用层、接口层、基础设施层目录结构
**Then** 领域层仅依赖 Python 标准库，不包含任何外部框架导入
**And** 各层之间依赖方向正确（基础设施层→应用层→领域层）

### Story 1.2: 领域事件定义

As a **领域工程师**,
I want **定义核心领域事件（DocumentProcessed, ToolExecuted, AgentDecided, CheckpointReached, CorrectionApproved）**,
So that **系统支持事件驱动架构和事件溯源**。

**Acceptance Criteria:**

**Given** 领域层已创建
**When** 定义领域事件的 Schema（事件 ID、类型、时间戳、载荷、来源、Schema 版本、聚合根 ID、聚合根类型、版本号）
**Then** 所有事件继承自统一的 DomainEvent 基类
**And** 事件 Schema 通过 Pydantic V2 验证

### Story 1.3: 事件总线实现

As a **后端工程师**,
I want **实现双通道事件总线（Redis 发布/订阅 + RabbitMQ + 事务发件箱）**,
So that **实时事件低延迟路由，持久化事件可靠传输**。

**Acceptance Criteria:**

**Given** 领域事件已定义
**When** 发布领域事件至事件总线
**Then** 实时通知型事件通过 Redis 发布/订阅通道传输（延迟<50ms）
**And** 持久化事件通过 PostgreSQL event_outbox 表 + RabbitMQ 传输（100% 可靠）

### Story 1.4: 五层存储架构 - Redis 高速缓存层

As a **存储工程师**,
I want **实现 Redis 高速缓存层（会话状态、语义缓存、公共黑板）**,
So that **支持低延迟会话管理和语义缓存**。

**Acceptance Criteria:**

**Given** Redis 7.0+ 已部署
**When** 存储会话状态快照至 Redis Hash
**Then** 序列化/反序列化时间<10ms，TTL 可配置（24h-30d）
**And** 支持主从复制与故障转移

### Story 1.5: 五层存储架构 - PostgreSQL 关系存储层

As a **存储工程师**,
I want **实现 PostgreSQL 关系存储层（用户/RBAC、审计元数据、业务实体）**,
So that **支持 ACID 事务和外键约束**。

**Acceptance Criteria:**

**Given** PostgreSQL 15+ 已部署
**When** 创建用户表、角色表、权限表、审计日志表、业务实体表
**Then** 所有表通过外键约束关联，支持 ACID 事务
**And** 使用 Alembic 管理数据库迁移

### Story 1.6: 五层存储架构 - Qdrant 向量存储层

As a **存储工程师**,
I want **实现 Qdrant 向量存储层（嵌入向量、混合检索 payload）**,
So that **支持混合检索（Dense + Sparse + Payload 过滤）**。

**Acceptance Criteria:**

**Given** Qdrant 1.7+ 已部署
**When** 存储 bge-m3 嵌入向量（维度 1024）至 Collection
**Then** 支持 COSINE 相似度度量和 Payload 过滤
**And** 混合检索延迟 P95<200ms（初检）

### Story 1.7: 五层存储架构 - MinIO 对象存储层

As a **存储工程师**,
I want **实现 MinIO 对象存储层（原始文档、证据包、审计归档）**,
So that **支持版本控制和 WORM 存储**。

**Acceptance Criteria:**

**Given** MinIO 已部署
**When** 上传文档至 Bucket
**Then** 支持分片上传和断点续传，版本控制启用
**And** 审计日志 Bucket 启用 Object Lock（COMPLIANCE 模式，保留期限 7 年）

### Story 1.8: 五层存储架构 - Neo4j 图存储层

As a **存储工程师**,
I want **实现 Neo4j 图存储层（知识图谱、实体关系、依赖图）**,
So that **支持 GraphRAG 增强检索和实体关联查询**。

**Acceptance Criteria:**

**Given** Neo4j 5.x 已部署
**When** 创建实体节点和关系边
**Then** 支持 Cypher 查询（实体关联查询、路径查询）
**And** 简单图遍历查询延迟 P95<200ms

### Story 1.9: RBAC 权限管理

As a **安全工程师**,
I want **实现用户认证与 RBAC 权限管理**,
So that **系统支持细粒度访问控制**。

**Acceptance Criteria:**

**Given** PostgreSQL 用户表已创建
**When** 用户登录并获取 JWT 令牌
**Then** 验证用户凭证，加载 RBAC 权限（用户 - 角色 - 权限关联）
**And** 权限测试 100% 通过，越权访问 0 次

### Story 1.10: 统一审计日志

As a **合规工程师**,
I want **实现统一审计日志（log_id/timestamp/actor/action_type/target_resource/old_value/new_value）**,
So that **满足等保 2.0 和 SOX 合规要求**。

**Acceptance Criteria:**

**Given** 审计日志表已创建
**When** 记录用户操作至审计日志
**Then** 日志完整性 100%，支持按时间/角色/任务类型多维检索
**And** 审计日志写入 PostgreSQL（MVP），V2 升级至 WORM 存储

### Story 1.11: 数据主权隔离

As a **合规工程师**,
I want **实现数据主权隔离（敏感数据本地优先，外部网络调用需审计与白名单批准）**,
So that **满足数据安全法和 PIPL 要求**。

**Acceptance Criteria:**

**Given** 敏感数据标签已定义
**When** 处理敏感数据或发起外部网络调用
**Then** 敏感数据默认本地优先处理，外部调用需通过白名单校验
**And** 数据境内存储 100%，跨境传输审批率 100%

### Story 1.12: 等保 2.0 三级基础要求

As a **安全工程师**,
I want **实现等保 2.0 三级基础要求（身份鉴别/访问控制/安全审计/入侵防范/数据完整性/备份恢复）**,
So that **通过公安部指定测评机构测评**。

**Acceptance Criteria:**

**Given** 所有安全控制已实现
**When** 执行等保 2.0 测评
**Then** 无高风险项，中危漏洞<5 个
**And** 身份鉴别支持双因子认证，访问控制支持细粒度 RBAC

### Story 1.13: K8s 动态扩缩容

As a **运维工程师**,
I want **系统支持基于负载的自动扩缩容**,
So that **系统可以应对流量高峰并优化资源成本**。

**Acceptance Criteria:**

**Given** 系统部署在 K8s 集群
**When** 负载增加（CPU>70% 或 请求队列>100）
**Then** 自动扩容 Pod 数量（响应时间<5 分钟）
**And** 负载降低后自动缩容

### Story 1.14a: 自主调用循环 - trigger 实现

As a **系统架构师**,
I want **实现领域事件/心跳事件触发机制**,
So that **系统可以基于事件或周期性心跳自主启动任务**。

**Acceptance Criteria:**

**Given** 领域事件触发（DocumentProcessed/ToolExecuted/AgentDecided 等）或周期性心跳事件
**When** trigger 机制检测到事件
**Then** 解析事件类型，提取 session_id 和任务上下文
**And** 触发 route 机制（Story 1.14b）

### Story 1.14b: 自主调用循环 - route 实现

As a **系统架构师**,
I want **实现 session_id 哈希/语义路由机制**,
So that **任务可以路由至目标 Agent 或工具**。

**Acceptance Criteria:**

**Given** trigger 机制传递的任务上下文
**When** route 机制执行
**Then** 基于 session_id 哈希或语义相似度路由至目标 Agent/工具
**And** 路由决策日志存储（任务 ID、时间戳、L1 结果、L2 评分、选定路由、成本、延迟）

### Story 1.14c: 自主调用循环 - execute 实现

As a **系统架构师**,
I want **实现会话命名空间执行与状态快照**,
So that **任务在隔离环境中执行，状态可持久化和恢复**。

**Acceptance Criteria:**

**Given** route 机制传递的目标 Agent/工具
**When** execute 机制执行
**Then** 在会话命名空间中执行任务（Docker/gVisor 沙箱）
**And** 状态快照序列化至 Redis Hash（支持主从复制与故障转移，TTL 24h-30d）
**And** 执行完成后发布领域事件（DocumentProcessed/ToolExecuted/AgentDecided）

### Story 1.15a: 外部化记忆 - 上下文压缩实现

As a **系统架构师**,
I want **实现 LLM 上下文压缩机制**,
So that **LLM 上下文仅保留当前任务必需的压缩信息，防止上下文爆炸**。

**Acceptance Criteria:**

**Given** LLM 任务执行需要访问记忆
**When** 上下文压缩机制执行
**Then** LLM 上下文仅保留当前任务必需的压缩信息（压缩率≥70%）
**And** 压缩前执行持久化笔记步骤（存储至 Story 1.15b）

### Story 1.15b: 外部化记忆 - 五层存储协同实现

As a **系统架构师**,
I want **实现会话状态与推理轨迹的五层存储协同**,
So that **记忆分离原则得到实现，磁盘记忆=真相源**。

**Acceptance Criteria:**

**Given** LLM 任务执行需要持久化记忆
**When** 五层存储协同机制执行
**Then** 会话状态与推理轨迹持久化存储至五层存储：
  - Redis（会话状态、语义缓存，TTL 24h-30d）
  - PostgreSQL（用户/RBAC、审计元数据、业务实体，永久）
  - Qdrant（嵌入向量、混合检索 payload，永久）
  - MinIO（原始文档、证据包、审计归档，7 年 WORM）
  - Neo4j（知识图谱、实体关系，永久）
**And** 压缩前执行持久化笔记步骤防止信息丢失

### Story 1.16: 集成测试框架

As a **测试工程师**,
I want **集成测试、E2E 测试框架和测试数据管理**,
So that **可以快速编写和执行集成测试和 E2E 测试**。

**Acceptance Criteria:**

**Given** 测试框架搭建完成（Story 0.3）
**When** 运行集成测试或 E2E 测试
**Then** 测试框架支持跨组件测试、API 测试、UI 测试
**And** 测试数据管理支持（Fixture、Mock、测试数据库隔离）
**And** 所有 Epic 的集成测试和 E2E 测试都通过此框架执行

---

## Epic 2: 文档与数据管理

**目标：** 实现 17 种格式文档的上传、解析、版本管理和语义分块，支持高保真溯源。

**包含 FR：** DM-01, DM-02, DM-03, DM-04, DM-05, DM-06, DM-07, DM-08

**📦 价值组：文档全生命周期管理**
> 用户可以上传、解析、管理和溯源各类文档

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 2.1 | 文档上传（17 种格式） | 用户可以上传企业现有各类文档 | 依赖 Epic 1 Story 1.7（MinIO 存储） | **P0-1** |
| Story 2.2 | 文档解析与内容提取 | 非结构化文档转化为结构化知识 | 依赖 Story 2.1 | **P0-2** |
| Story 2.3 | 版面信息保留（DocLayNet） | 支持高保真溯源至原始文档坐标点 | 依赖 Story 2.2 | **P0-3（关键路径）** |
| Story 2.4 | 表格行列语义提取 | 财务数据不失真，支持后续分析 | 依赖 Story 2.2 | P1-4 |
| Story 2.5 | OCR 解析（扫描件/图像 PDF） | 历史纸质文档和扫描件可被处理 | 依赖 Story 2.2 | P1-5 |
| Story 2.6 | 文档版本快照 | 支持版本追溯和回滚 | 依赖 Story 2.2, Epic 1 Story 1.7 | P1-6 |
| Story 2.7 | 元数据标准化校验 | 确保文档元数据完整性和可追溯性 | 依赖 Story 2.2 | P1-7 |
| Story 2.8 | 语义分块 | 检索结果更符合语义完整性 | 依赖 Story 2.2, Epic 1 Story 1.6 | P1-8 |

**✅ 依赖关系验证：**
- Epic 2 依赖 Epic 1 的存储层（Story 1.6 Qdrant, Story 1.7 MinIO）
- Epic 2 内部故事依赖均为**顺序依赖**（文档处理流水线）
- Epic 2 可独立交付价值（用户上传和管理文档）
- 不依赖 Epic 3-8

**⚠️ 关键路径说明：**
- **Story 2.3（版面信息保留）是 Epic 3 Story 3.8（高保真溯源）的前置依赖**
- **执行顺序：Story 2.1 → Story 2.2 → Story 2.3 → Epic 3 Story 3.8**
- Story 2.3 必须提前至前 3 个 Story 执行，否则影响 Epic 3 溯源功能交付

### Story 2.1: 文档上传（17 种格式）

As a **企业战略人员**,
I want **上传 17 种格式的文档（pdf/txt/doc/docx/ppt/pptx/xls/xlsx/csv/jpeg/png/gif/markdown/html + zip/tar 压缩包）**,
So that **系统可以处理企业现有各类文档**。

**Acceptance Criteria:**

**Given** 用户已登录并具有上传权限
**When** 拖拽或选择文件上传（支持批量，总大小≤20GB）
**Then** 系统接收所有支持格式，显示上传进度
**And** 支持分片上传和断点续传

### Story 2.2: 文档解析与内容提取

As a **企业战略人员**,
I want **系统解析上传文档并提取文本、表格、图像、公式内容**,
So that **非结构化文档转化为结构化知识资产**。

**Acceptance Criteria:**

**Given** 文档已上传完成
**When** 系统执行文档解析
**Then** 提取文本、表格、图像、公式内容，输出结构化 JSON
**And** 解析准确率≥95%（抽样验证）

### Story 2.3: 版面信息保留（DocLayNet 格式）

As a **分析师**,
I want **系统保留文档版面信息（元素坐标 x, y, width, height），采用 DocLayNet 标准格式**,
So that **支持高保真溯源至原始文档坐标点**。

**Acceptance Criteria:**

**Given** 文档解析完成
**When** 记录文档元素坐标信息
**Then** 采用 DocLayNet 标准格式（支持 ONNX 格式跨平台推理）
**And** 坐标信息用于 Bounding Box 级溯源

### Story 2.4: 表格行列语义提取

As a **财务分析师**,
I want **系统提取表格的行列语义，输出包含表头与列类型的结构化 JSON**,
So that **财务数据不失真，支持后续分析**。

**Acceptance Criteria:**

**Given** 文档包含表格（xls/xlsx/csv/PDF 表格）
**When** 系统执行表格解析
**Then** 提取表头、列类型、行列语义，输出结构化 JSON
**And** 支持合并单元格语义还原与跨页表格识别（V1）

### Story 2.5: OCR 解析（扫描件/图像 PDF）

As a **企业战略人员**,
I want **系统对扫描件或图像 PDF 进行 OCR 解析（中/英），提取置信度并标注**,
So that **历史纸质文档和扫描件可被系统处理**。

**Acceptance Criteria:**

**Given** 上传的文档是扫描件或图像 PDF
**When** 系统执行 OCR 解析
**Then** 提取文本内容，输出置信度评分
**And** 置信度<0.85 时自动标注为"待人工复核"

### Story 2.6: 文档版本快照

As a **文档管理员**,
I want **创建文档版本快照，系统记录操作者、时间戳与差异摘要**,
So that **支持版本追溯和回滚**。

**Acceptance Criteria:**

**Given** 文档已存在于系统
**When** 用户上传新版本或修改文档
**Then** 系统创建版本快照，记录操作者、时间戳、差异摘要（diff）
**And** 支持版本冲突检测（乐观锁/悲观锁可选）

### Story 2.7: 元数据标准化校验

As a **数据治理工程师**,
I want **系统校验入库文档的最小元字段集（creator/created_at/source/license/business_domain）**,
So that **确保文档元数据完整性和可追溯性**。

**Acceptance Criteria:**

**Given** 文档解析完成准备入库
**When** 系统校验元数据
**Then** 最小元字段集完整（creator/created_at/source/license/business_domain）
**And** 关键字段缺失自动阻断入库

### Story 2.8: 语义分块

As a **RAG 工程师**,
I want **系统对文档进行语义分块（基于文档语义边界而非固定字数切片）**,
So that **检索结果更符合语义完整性**。

**Acceptance Criteria:**

**Given** 文档解析完成
**When** 系统执行语义分块
**Then** 基于文档语义边界（段落、章节、表格边界）进行切片
**And** 平均片段长度目标≈300 tokens（允许配置）

---

## Epic 3: 智能检索与知识发现

**目标：** 实现混合检索（Dense + Sparse + Graph）、分层检索、契约化摘要和高保真溯源。

**包含 FR：** SR-01, SR-02, SR-03, SR-04, SR-05, SR-06, SR-07, SR-08, CP-02, SA-01, SA-02, SA-03

**📦 价值组：智能检索与溯源**
> 用户可以检索文档并追溯至原始坐标点

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 3.1 | 混合检索（Dense + BM25） | 同时支持语义检索和关键词检索 | 依赖 Epic 1 Story 1.6（Qdrant） | P0-1 |
| Story 3.2 | 实体抽取（LLM+ 规则混合） | 构建知识图谱的实体和关系 | 依赖 Story 3.1 | P0-2 |
| Story 3.3 | 战略领域词典库管理 | 实体抽取准确率持续提升 | 依赖 Story 3.2 | P1-3 |
| Story 3.4 | RRF 融合排序 | 综合多种检索信号提升相关性 | 依赖 Story 3.1 | P0-4 |
| Story 3.5 | 分层检索（L1-L4） | 支持自顶向下和自底向上的双向检索 | 依赖 Story 3.4 | P0-5 |
| Story 3.6 | 契约化结构化摘要生成 | 摘要质量可控且可验证 | 依赖 Story 3.5 | P1-6 |
| Story 3.7 | 检索相关性评估 | 防止基于不足数据生成幻觉内容 | 依赖 Story 3.6 | P1-7 |
| Story 3.8 | 高保真溯源（Bounding Box 级） | 从结论快速追溯至原始文档坐标点 | 依赖 Epic 2 Story 2.3 | **P0-8（关键路径）** |
| Story 3.9 | 语义缓存 | 减少重复检索和 LLM 调用，降低 Token 消耗 | 依赖 Story 3.1 | P1-9 |
| Story 3.10 | 战略档案库永久存储 | 形成企业长期记忆和知识积累 | 依赖 Epic 1 Story 1.5/1.7 | P1-10 |
| Story 3.11 | 事实有效期标签管理 | 支持时间轴演进的动态知识网络查询 | 依赖 Story 3.10 | P1-11 |
| Story 3.12 | 数据陈旧标记 | 提醒用户注意数据时效性 | 依赖 Story 3.11 | P1-12 |

**✅ 依赖关系验证：**
- Epic 3 依赖 Epic 1 的存储层（Story 1.6 Qdrant, Story 1.5 PostgreSQL, Story 1.7 MinIO）
- Epic 3 依赖 Epic 2 的版面信息保留（Story 2.3）用于 Bounding Box 溯源
- Epic 3 内部故事依赖均为**顺序依赖**（检索流水线）
- Epic 3 可独立交付价值（用户检索和溯源）
- 不依赖 Epic 4-8

**⚠️ 关键路径说明：**
- **Story 3.8（高保真溯源）依赖 Epic 2 Story 2.3（版面信息保留）**
- Story 3.8 是核心用户体验（30 秒溯源），必须优先执行

---

### Story 3.1: 混合检索（Dense + BM25）

As a **分析师**,
I want **系统执行混合检索（Dense bge-m3 + BM25 稀疏检索），双路召回**,
So that **同时支持语义检索和关键词检索**。

**Acceptance Criteria:**

**Given** 用户输入检索查询
**When** 系统执行混合检索
**Then** Dense 检索（bge-m3）和 BM25 检索并行执行，双路召回
**And** 检索延迟 P95<800ms（MVP）

### Story 3.2: 实体抽取（LLM+ 规则混合）

As a **知识工程师**,
I want **系统抽取实体（LLM+ 规则混合策略），输出三元组**,
So that **构建知识图谱的实体和关系**。

**Acceptance Criteria:**

**Given** 文档解析完成
**When** 系统执行实体抽取
**Then** 规则基抽取（领域词典 AC 自动机、正则、依存句法）准确率≥80%
**And** LLM 语义抽取（Few-Shot+CoT+Schema 约束）高召回率，冲突仲裁器融合（规则权重 0.6/LLM 权重 0.4）

### Story 3.3: 战略领域词典库管理

As a **领域专家**,
I want **系统管理战略领域词典库，支持热更新与版本管理**,
So that **实体抽取准确率持续提升**。

**Acceptance Criteria:**

**Given** 战略领域词典已初始化
**When** 添加新词或修改现有词条
**Then** 词典热更新（无需重启系统），版本管理支持回滚
**And** 核心战略概念覆盖率≥95%

### Story 3.4: RRF 融合排序

As a **搜索工程师**,
I want **系统融合三路检索结果（Dense + Sparse + Graph/metadata signals），使用 RRF 融合排序**,
So that **综合多种检索信号提升相关性**。

**Acceptance Criteria:**

**Given** 三路检索结果已获取
**When** 执行 RRF 融合排序
**Then** 可配置权重的 RRF 算法融合三路结果
**And** 集成 ColBERT-v2 重排序器对 Top-K 候选精排

### Story 3.5: 分层检索（L1-L4）

As a **系统架构师**,
I want **系统执行分层检索（L1 跨文档摘要→L2 文档摘要→L3 文档切片→L4 实体级片段）**,
So that **支持自顶向下和自底向上的双向检索**。

**Acceptance Criteria:**

**Given** 四级分层索引已构建（Parent-Child 层级）
**When** 执行分层检索
**Then** 支持"自顶向下"（L1→L4）和"自底向上"（L4→L1）双向遍历
**And** 延迟预算分级约束（初检 200ms + 精排 250ms + 融合 50ms）

### Story 3.6: 契约化结构化摘要生成

As a **分析师**,
I want **系统生成契约化结构化摘要（财务/市场/技术视角），输出符合预定义 JSON Schema**,
So that **摘要质量可控且可验证**。

**Acceptance Criteria:**

**Given** 检索结果已获取
**When** 调用 LLM 生成摘要
**Then** 输出强制遵守预定义的 JSON Schema 契约（财务/市场/技术视角）
**And** 通过 Pydantic V2 Schema 验证

### Story 3.7: 检索相关性评估（LLM-as-a-Judge）

As a **质量工程师**,
I want **系统评估检索相关性（LLM-as-a-Judge 实时多维评估），相关性<0.6 标注"数据不足"**,
So that **防止基于不足数据生成幻觉内容**。

**Acceptance Criteria:**

**Given** 检索结果已获取
**When** 执行相关性评估
**Then** LLM-as-a-Judge 多维评估（相关性、完整性、时效性）
**And** 相关性<0.6 标注"数据不足"，阻断直接生成

### Story 3.8: 高保真溯源（Bounding Box 级）

As a **企业战略人员**,
I want **系统保留引文"三元组"特征（文档 ID、切片 ID、字符范围），支持 Bounding Box 级溯源**,
So that **从结论快速追溯至原始文档坐标点**。

**Acceptance Criteria:**

**Given** 检索结果包含引文信息
**When** 用户点击结论文字
**Then** 弹出溯源卡片，显示文档 ID、页码、置信度
**And** 点击"跳转"后自动定位至 PDF 坐标点（响应<300ms，准确率≥95%）

### Story 3.9: 语义缓存

As a **性能工程师**,
I want **系统执行语义缓存（相似度>0.9 直接返回缓存结果）**,
So that **减少重复检索和 LLM 调用，降低 Token 消耗**。

**Acceptance Criteria:**

**Given** 查询已执行过
**When** 新查询与历史查询相似度>0.9
**Then** 直接返回缓存结果，不执行检索和 LLM 调用
**And** 缓存失效策略（TTL 24h + 事件驱动失效 + 版本感知失效）

### Story 3.10: 战略档案库永久存储

As a **知识管理专家**,
I want **系统永久存储历年 SP/BP 的关键假设变量、决策依据、实际执行偏差**,
So that **形成企业长期记忆和知识积累**。

**Acceptance Criteria:**

**Given** SP/BP 规划完成
**When** 归档至战略档案库
**Then** 关键假设变量、决策依据、实际执行偏差永久存储
**And** 向量存储 + 对象存储协同架构

### Story 3.11: 事实有效期标签管理

As a **分析师**,
I want **系统管理事实有效期标签（valid_from/valid_until）**,
So that **支持时间轴演进的动态知识网络查询**。

**Acceptance Criteria:**

**Given** 战略档案已存储
**When** 查询历史决策
**Then** 支持按时间范围查询，显示事实有效期标签
**And** 超 12 个月数据自动标记"数据陈旧"并降权

### Story 3.12: 数据陈旧标记

As a **合规工程师**,
I want **系统执行数据陈旧标记（超 12 个月自动降权）**,
So that **提醒用户注意数据时效性**。

**Acceptance Criteria:**

**Given** 引用数据已存储超 12 个月
**When** 检索或生成结果引用该数据
**Then** 强制在生成结果中提示"数据陈旧"
**And** 自动降权处理（排序分数降低）

---


## Epic 4: 战略工具箱

**目标：** 实现 23 种战略工具的注册、执行、工具链编排和沙箱隔离。

**包含 FR：** ST-01, ST-02, ST-03, ST-04, ST-05

**📦 价值组：战略工具执行能力**
> 用户可以执行 23 种战略工具分析

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 4.1 | 战略工具注册（23 种） | Agent 可以调用这些工具执行分析 | 依赖 Epic 1 Story 1.1（架构骨架） | P0-1 |
| Story 4.2 | 工具链编排（DAG） | 支持复杂分析任务的自动化执行 | 依赖 Story 4.1 | P1-2 |
| Story 4.3 | 工具输入/输出 Schema 验证 | 工具输出符合预期格式，防止模型漂移 | 依赖 Story 4.1 | P0-3 |
| Story 4.4 | Docker 沙箱执行 | 防止代码执行带来的安全风险 | 依赖 Epic 1 Story 1.7（MinIO 存储日志） | P0-4 |
| Story 4.5 | 红蓝辩论机制基础 | MVP 阶段支持基础的多视角分析 | 依赖 Story 4.1 | P1-5 |

**✅ 依赖关系验证：**
- Epic 4 依赖 Epic 1 的架构骨架（Story 1.1）和存储层（Story 1.7）
- Epic 4 内部故事依赖均为**顺序依赖**（工具注册→验证→执行）
- Epic 4 可独立交付价值（用户执行工具分析）
- 不依赖 Epic 2-3/5-8

### Story 4.1: 战略工具注册（23 种）

As a **工具工程师**,
I want **系统注册 23 种战略工具（PESTEL/波特五力/$APPEALS/竞争对手分析/价值链分析/VRIO/安索夫矩阵/SWOT-TOWS/GE-麦肯锡矩阵/SPACE 矩阵/情景规划/价值曲线/价值主张画布/商业模式画布/破坏性创新模型/BSC/战略地图/组织设计框架/依赖关系图/RACI 矩阵/甘特图/KPI/变革管理模型）**,
So that **Agent 可以调用这些工具执行分析**。

**Acceptance Criteria:**

**Given** 工具箱服务已启动
**When** 系统加载工具注册表
**Then** 23 种战略工具全部注册，每个工具有唯一标识、输入/输出 Schema、执行逻辑模板
**And** 所有工具通过 Pydantic V2 契约测试

### Story 4.2: 工具链编排（DAG）

As a **系统架构师**,
I want **系统编排工具链（DAG 有向无环图），按拓扑顺序调度子任务**,
So that **支持复杂分析任务的自动化执行**。

**Acceptance Criteria:**

**Given** 工具链 DAG 已定义
**When** 执行工具链
**Then** 解析 DAG，按拓扑顺序调度子任务，并行执行无依赖子任务
**And** DAG 有效性校验器检测并阻止循环依赖

### Story 4.3: 工具输入/输出 Schema 验证

As a **质量工程师**,
I want **系统验证工具输入/输出 Schema（Pydantic V2 契约化）**,
So that **工具输出符合预期格式，防止模型漂移**。

**Acceptance Criteria:**

**Given** 工具已注册
**When** 调用工具执行
**Then** 输入数据通过 Pydantic V2 Schema 验证
**And** 输出数据通过 Pydantic V2 Schema 验证，失败则重试或标记不可行

### Story 4.4: Docker 沙箱执行

As a **安全工程师**,
I want **系统在 Docker 沙箱中执行工具代码，网络隔离 + 权限最小化**,
So that **防止代码执行带来的安全风险**。

**Acceptance Criteria:**

**Given** 工具需要执行代码
**When** 在 Docker 沙箱中执行
**Then** 网络隔离（默认断网，仅允许白名单网关访问可信 API）
**And** 权限最小化（只读文件系统、资源限制）

### Story 4.5: 红蓝辩论机制基础（单 Agent 多视角）

As a **产品专家**,
I want **系统执行红蓝辩论机制基础（单 Agent 多视角，MVP 替代方案）**,
So that **MVP 阶段支持基础的多视角分析**。

**Acceptance Criteria:**

**Given** 分析任务存在争议议题
**When** 执行红蓝辩论（单 Agent 多视角）
**Then** 生成激进派和保守派两种视角的分析
**And** 输出包含共识与分歧区域的风险视图

---

## Epic 5: Agent 协作系统

**目标：** 实现单 Agent 执行、EIP 弹性隔离和隔离切换审计。

**包含 FR：** AC-01, AC-02, AC-03, AC-04, AC-05, AC-06

**📦 价值组：单 Agent 战略规划能力**
> 用户可以通过 CEO Agent 执行战略规划

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 5.1 | CEO Agent 实例化 | MVP 阶段支持单 Agent 执行任务 | 依赖 Epic 1 Story 1.4（Redis 会话存储） | P0-1 |
| Story 5.2 | Agent 身份档案加载 | Agent 按照预定义的身份和规则执行任务 | 依赖 Story 5.1 | P0-2 |
| Story 5.3 | 单 Agent 标准工作流 | Agent 自主完成任务并输出可验证结果 | 依赖 Story 5.2 | P0-3 |
| Story 5.4 | EIP 弹性隔离协议基础 | MVP 阶段支持 Agent 隔离 | 依赖 Story 5.1 | P0-4 |
| Story 5.5 | Agent 三重硬隔离保证 | 防止 Agent 间信息泄露和视角越界 | 依赖 Story 5.4 | P0-5 |
| Story 5.6 | 隔离切换日志记录 | 满足审计追踪要求 | 依赖 Story 5.4, Epic 1 Story 1.10 | P1-6 |

**✅ 依赖关系验证：**
- Epic 5 依赖 Epic 1 的缓存层（Story 1.4）和审计日志（Story 1.10）
- Epic 5 内部故事依赖均为**顺序依赖**（Agent 实例化→加载→执行→隔离）
- Epic 5 可独立交付价值（用户通过 CEO Agent 执行战略规划）
- 不依赖 Epic 2-4/6-8

### Story 5.1: CEO Agent 实例化（MVP 单 Agent）

As a **系统架构师**,
I want **系统实例化 Agent 角色基础（CEO Agent，MVP 单 Agent 方案）**,
So that **MVP 阶段支持单 Agent 执行任务**。

**Acceptance Criteria:**

**Given** Agent 协作服务已启动
**When** 接收 Agent 任务命令
**Then** 实例化 CEO Agent，加载基础配置
**And** Agent 状态持久化至 Redis

### Story 5.2: Agent 身份档案加载

As a **Agent 工程师**,
I want **系统加载 Agent 身份档案（IDENTITY.md/CODE.md/SOUL.md/TOOLS.md/USER.md/MEMORY.md/HEARTBEAT.md）**,
So that **Agent 按照预定义的身份和规则执行任务**。

**Acceptance Criteria:**

**Given** Agent 已实例化
**When** 加载身份档案
**Then** 加载 IDENTITY.md（身份）、CODE.md（行为准则）、SOUL.md（价值观）、TOOLS.md（技能）、USER.md（用户偏好）、MEMORY.md（记忆）、HEARTBEAT.md（心跳）
**And** 档案内容验证通过

### Story 5.3: 单 Agent 标准工作流

As a **Agent 工程师**,
I want **系统执行单 Agent 任务（感知→规划→执行→验证→反思→证据打包）**,
So that **Agent 自主完成任务并输出可验证结果**。

**Acceptance Criteria:**

**Given** Agent 已加载身份档案
**When** 执行任务
**Then** 按标准工作流执行（感知→规划→执行→验证→反思→证据打包）
**And** 输出 JSON 思维链（Input→<Reflection>→<Tools_Used>→<Constraints_Check>→JSON）

### Story 5.4: EIP 弹性隔离协议基础（L4 硬隔离）

As a **安全工程师**,
I want **系统执行弹性视角隔离协议基础（L4 硬隔离默认）**,
So that **MVP 阶段支持 Agent 隔离**。

**Acceptance Criteria:**

**Given** Agent 已实例化
**When** 执行任务
**Then** 默认隔离等级为 L4 硬隔离（Prompt/工具/数据三重硬隔离）
**And** 隔离状态持久化至 Redis

### Story 5.5: Agent 三重硬隔离保证

As a **安全工程师**,
I want **系统保证 Agent 默认隔离等级为 L4 硬隔离（Prompt/工具/数据三重硬隔离）**,
So that **防止 Agent 间信息泄露和视角越界**。

**Acceptance Criteria:**

**Given** 多个 Agent 并行执行
**When** 检查隔离状态
**Then** 每个 Agent 的 Prompt、工具、数据严格隔离
**And** 隔离测试 100% 通过

### Story 5.6: 隔离切换日志记录

As a **合规工程师**,
I want **系统记录隔离切换日志（AGENT ID、时间戳、原隔离等级、目标隔离等级、触发原因、审批链）**,
So that **满足审计追踪要求**。

**Acceptance Criteria:**

**Given** Agent 隔离等级发生切换
**When** 记录切换事件
**Then** 日志包含 AGENT ID、时间戳、原隔离等级、目标隔离等级、触发原因、审批链
**And** 支持按 AGENT/时间/隔离等级多维检索

---

## Epic 6: 战略规划流程 (BLM 前两阶段)

**目标：** 实现 BLM 前两阶段（业绩差距分析 + 市场洞察）流程，支持 Checkpoint 机制和高保真溯源展示。

**包含 FR：** SP-01, SP-02, SP-03, SP-04, UI-04, UI-05, UI-06, UI-07

**📦 价值组：战略规划与审批能力**
> 用户可以生成战略规划并审批

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 6.1 | BLM 前两阶段流程 | 完成战略规划的基础分析阶段 | 依赖 Epic 1 Story 1.4/1.7, Epic 2 Story 2.2 | P0-1 |
| Story 6.2 | 市场洞察六子步骤 | 全面分析市场环境和机会 | 依赖 Story 6.1 | P0-2 |
| Story 6.3 | Checkpoint 快照创建 | 支持阶段审批和中断恢复 | 依赖 Story 6.2 | P0-3 |
| Story 6.4 | JSON 思维链输出 | Agent 决策过程可追溯和可解释 | 依赖 Story 6.1 | P0-4 |
| Story 6.5 | 多格式报告生成 | 可以导出和分享规划结果 | 依赖 Story 6.3 | **P0-5** |
| Story 6.6 | Checkpoint 摘要查看与恢复 | 高管参与关键决策点审批 | 依赖 Story 6.3 | P1-6 |
| Story 6.7 | 溯源树展示 | 验证分析结论的可靠性 | 依赖 Epic 2 Story 2.3, Epic 3 Story 3.8 | **P0-7** |
| Story 6.8 | 高管简化视图 | 快速理解态势并做出决策 | 依赖 Story 6.5 | **P0-8（不依赖 Story 6.5）** |
| Story 6.9 | **分析师视图** | 专业工具、BLM 进度可视化、快捷键支持 | 依赖 Story 6.1/6.7 | **P1-9（UX 三视图）** |
| Story 6.10 | **顾问视图** | 白标报告导出、品牌模板配置、多项目管理 | 依赖 Story 6.5 | **P1-10（UX 三视图）** |

**✅ 依赖关系验证：**
- Epic 6 依赖 Epic 1 的缓存层/存储层（Story 1.4/1.7）
- Epic 6 依赖 Epic 2 的文档解析（Story 2.2）和版面信息保留（Story 2.3）
- Epic 6 依赖 Epic 3 的高保真溯源（Story 3.8）
- Epic 6 内部故事依赖均为**顺序依赖**（BLM 流程→Checkpoint→报告→审批）
- Epic 6 可独立交付价值（用户生成和审批战略规划）
- 不依赖 Epic 4-5/7-8

**⚠️ 优先级优化说明：**
- **Story 6.5 提升至 P0-5**：支持 Story 6.8（高管简化视图）的优先级依赖
- **Story 6.8 不依赖 Story 6.5**：高管视图可独立显示，不依赖报告生成
- **Story 6.9/6.10**：UX 三视图设计（高管视图/分析师视图/顾问视图），P1 优先级

### Story 6.1: BLM 前两阶段流程（业绩差距分析 + 市场洞察）

As a **企业战略人员**,
I want **系统执行 BLM 前两阶段流程（业绩差距分析 + 市场洞察，含流程可视化；MVP 阶段 CEO AGENT 替代流程中所有 AGENT 角色）**,
So that **完成战略规划的基础分析阶段**。

**Acceptance Criteria:**

**Given** 文档已解析并索引
**When** 启动 BLM 规划
**Then** 执行业绩差距分析和市场洞察六子步骤基础（看趋势/看市场与客户/看竞争/看自己/看机会/机会差距分析）
**And** 流程可视化显示当前阶段和进度

### Story 6.2: 市场洞察六子步骤

As a **分析师**,
I want **系统执行市场洞察六子步骤基础（看趋势/看市场与客户/看竞争/看自己/看机会/机会差距分析）**,
So that **全面分析市场环境和机会**。

**Acceptance Criteria:**

**Given** 业绩差距分析完成
**When** 执行市场洞察
**Then** 依次执行六个子步骤，每个步骤输出结构化结果
**And** 每个步骤触发 Checkpoint

### Story 6.3: Checkpoint 快照创建

As a **企业战略人员**,
I want **系统创建 Checkpoint 快照（阶段标识、完成状态、用户反馈、修正记录）**,
So that **支持阶段审批和中断恢复**。

**Acceptance Criteria:**

**Given** BLM 阶段完成
**When** 到达 Checkpoint
**Then** 创建快照（阶段标识、完成状态、用户反馈请求、恢复点引用）
**Then** 状态快照序列化至 Redis Hash
**And** 支持用户修正关键参数

### Story 6.4: JSON 思维链输出

As a **系统架构师**,
I want **系统输出 JSON 思维链（Input→<Reflection>→<Tools_Used>→<Constraints_Check>→JSON）**,
So that **Agent 决策过程可追溯和可解释**。

**Acceptance Criteria:**

**Given** Agent 执行任务完成
**When** 输出结果
**Then** 包含完整的 JSON 思维链（Input→<Reflection>→<Tools_Used>→<Constraints_Check>→JSON）
**And** 思维链存储至战略档案库

### Story 6.5: 多格式报告生成（PDF/Markdown）

As a **企业战略人员**,
I want **系统生成多格式报告（PDF/Markdown），包含可点击的引文索引**,
So that **可以导出和分享规划结果**。

**Acceptance Criteria:**

**Given** BLM 前两阶段完成
**When** 生成报告
**Then** 支持 PDF 和 Markdown 格式
**And** 报告包含可点击的引文索引，支持溯源

### Story 6.6: Checkpoint 摘要查看与恢复

As a **高管**,
I want **查看 Checkpoint 摘要并修正关键参数后恢复运行**,
So that **参与关键决策点审批**。

**Acceptance Criteria:**

**Given** Checkpoint 已创建
**When** 高管查看 Checkpoint 摘要
**Then** 显示阶段标识、完成状态、关键参数、用户反馈
**And** 支持修正关键参数后恢复执行

### Story 6.7: 溯源树展示

As a **分析师**,
I want **系统展示溯源树（从结论逐层展开至原始数据）**,
So that **验证分析结论的可靠性**。

**Acceptance Criteria:**

**Given** 分析结论已生成
**When** 用户查看溯源
**Then** 展示溯源树（结论→分析→数据切片→原始文档）
**And** 支持交互式展开和 Bounding Box 跳转

### Story 6.8: 高管简化视图（仪表盘/审批中心/审计摘要）

As a **CEO**,
I want **系统支持高管简化视图（仪表盘/审批中心/审计摘要）**,
So that **快速理解态势并做出决策**。

**Acceptance Criteria:**

**Given** 高管登录系统
**When** 查看仪表盘
**Then** 第一屏仅显示 3 个关键指标，红/黄/绿状态指示器
**And** 30 秒内理解当前态势（30 秒理解率≥90%）

### Story 6.9: 分析师视图（专业工具、BLM 进度可视化、快捷键支持）

As a **企业战略与市场人员**,
I want **系统提供分析师视图（专业工具、BLM 进度可视化、快捷键支持）**,
So that **高效完成战略规划和分析工作**。

**Acceptance Criteria:**

**Given** 分析师登录系统
**When** 使用分析师视图
**Then** 显示专业工具箱（23 种战略工具）、BLM 六阶段进度可视化、快捷键支持
**And** 支持快速溯源（30 秒内跳转至原始文档坐标点）
**And** 支持批量操作和快捷键导航

### Story 6.10: 顾问视图（白标报告导出、品牌模板配置、多项目管理）

As a **专业顾问（咨询/投资/银行）**,
I want **系统提供顾问视图（白标报告导出、品牌模板配置、多项目管理）**,
So that **高效交付客户项目并保证品牌一致性**。

**Acceptance Criteria:**

**Given** 顾问登录系统
**When** 使用顾问视图
**Then** 显示多项目管理面板、品牌模板配置、白标报告导出功能
**And** 支持品牌元素配置（Logo/配色/字体），导出报告品牌 100% 准确
**And** 支持多客户数据隔离（Schema per Tenant）

---

## Epic 7: 多触点用户界面与 API 集成

**目标：** 实现 CLI、REST API、API Gateway、健康度仪表盘和无障碍设计。

**包含 FR：** UI-01, UI-02, UI-03, UI-07, UI-11, NFR-INT-05, NFR-ACC-01

**📦 价值组：多触点操作与监控能力**
> 用户可以通过 CLI/API/仪表盘操作系统

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 7.1 | CLI 命令行接口 | 高效操作系统 | 依赖 Epic 1 Story 1.1 | P0-1 |
| Story 7.2 | REST API 接口 | 支持外部系统集成 | 依赖 Epic 1 Story 1.1 | P0-2 |
| Story 7.3 | API Gateway 统一入口 | 集中管理 API 安全和流量 | 依赖 Story 7.2, Epic 1 Story 1.9 | P0-3 |
| Story 7.4 | 健康度仪表盘 | 监控系统运行状态 | 依赖 Epic 1 Story 1.12 | P1-4 |
| Story 7.5 | **无障碍设计（WCAG 2.1 AA）** | 支持键盘导航和屏幕阅读器 | 依赖 Story 7.1/7.2 | **P1-5（NFR-ACC-01）** |
| Story 7.6 | **API 契约测试（OpenAPI 3.1）** | 确保 API 可用性和兼容性 | 依赖 Story 7.2 | **P1-6（NFR-INT-05）** |
| Story 7.7 | **API E2E 测试** | 确保 API 端到端功能正确性 | 依赖 Story 7.2, Story 1.16 | **P1-7（测试 Story）** |

**✅ 依赖关系验证：**
- Epic 7 依赖 Epic 1 的架构骨架（Story 1.1）、RBAC（Story 1.9）、监控（Story 1.12）
- Epic 7 内部故事依赖均为**并行依赖**（CLI/API/Gateway 可并行开发）
- Epic 7 可独立交付价值（用户通过 CLI/API/仪表盘操作系统）
- 不依赖 Epic 2-6/8

**📋 NFR 覆盖说明：**
- **Story 7.5** 覆盖 NFR-ACC-01（无障碍设计，WCAG 2.1 AA）
- **Story 7.6** 覆盖 NFR-INT-05（MCP/A2A 协议兼容性）
- **Story 7.7** 覆盖测试 Story（API E2E 测试，确保端到端功能正确性）

### Story 7.1: CLI 命令行接口

As a **企业战略人员**,
I want **通过 CLI 执行命令（文档上传/Agent 调用/规划生成/Checkpoint 恢复）**,
So that **高效操作系统**。

**Acceptance Criteria:**

**Given** CLI 已安装
**When** 执行命令（如 `sisys upload --file docs.zip`）
**Then** 命令正确解析并执行
**And** 输出执行结果和进度反馈

### Story 7.2: REST API 接口

As a **集成工程师**,
I want **系统通过 REST API 提供接口（文档管理/工具调用/Agent 协作/规划生成/系统管理）**,
So that **支持外部系统集成**。

**Acceptance Criteria:**

**Given** API 服务已启动
**When** 调用 REST API 端点
**Then** 符合 OpenAPI 3.1 规范，返回正确响应
**And** API 可用性≥99%

### Story 7.3: API Gateway 统一入口

As a **安全工程师**,
I want **系统通过 API Gateway 统一入口处理所有外部请求（统一认证/限流/路由/安全控制）**,
So that **集中管理 API 安全和流量**。

**Acceptance Criteria:**

**Given** API Gateway 已部署（Kong/Traefik）
**When** 外部请求到达
**Then** 统一认证（OAuth 2.1/JWT）、限流（令牌桶算法）、路由（基于路径/方法/角色）、安全控制（请求验证/注入检测）
**And** 限流测试通过

### Story 7.4: 健康度仪表盘

As a **运维工程师**,
I want **系统提供健康度仪表盘（实时可视化各 Agent 健康度指标）**,
So that **监控系统运行状态**。

**Acceptance Criteria:**

**Given** 系统正在运行
**When** 查看健康度仪表盘
**Then** 实时显示 Agent 健康度、Token 消耗、检索延迟等指标
**And** 指标通过 OpenTelemetry Trace 输出

### Story 7.5: 无障碍设计（WCAG 2.1 AA）

As a **无障碍用户**,
I want **系统支持键盘导航和屏幕阅读器兼容**,
So that **我可以无障碍地使用系统**。

**Acceptance Criteria:**

**Given** 用户使用键盘或屏幕阅读器
**When** 操作系统
**Then** 所有功能可通过键盘访问，屏幕阅读器正确朗读内容
**And** 符合 WCAG 2.1 AA 标准（对比度≥4.5:1，焦点可见）

### Story 7.6: API 契约测试（OpenAPI 3.1）

As a **集成工程师**,
I want **系统 API 通过 OpenAPI 3.1 契约测试**,
So that **确保 API 可用性和向后兼容性**。

**Acceptance Criteria:**

**Given** API 已实现
**When** 运行契约测试
**Then** 所有端点符合 OpenAPI 3.1 规范
**And** 向后兼容 1-2 个版本，协议兼容性测试通过

### Story 7.7: API E2E 测试

As a **测试工程师**,
I want **系统 API 通过端到端（E2E）测试**,
So that **确保 API 从客户端到服务器的完整功能正确性**。

**Acceptance Criteria:**

**Given** API 已实现，测试框架搭建完成（Story 1.16）
**When** 运行 E2E 测试
**Then** 所有 API 端点的完整用户流程测试通过（文档上传→解析→检索→报告生成）
**And** 测试数据隔离（测试数据库与生产数据库隔离）
**And** 测试覆盖率≥80%

---

## Epic 8: 用户权限管理与审计合规

**目标：** 实现审计日志多维检索、修正分级判定基础、数据主权隔离和安全测试。

**包含 FR：** SC-04, SC-05, SC-06, SC-07, SC-08

**📦 价值组：安全与合规**
> 管理员可以管理权限和审计日志，确保系统安全合规

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 8.1 | 审计日志多维检索 | 支持合规审计和问题排查 | 依赖 Epic 1 Story 1.10 | P1-1 |
| Story 8.2 | 修正分级判定基础 | L0/L1 级修正自动处理，减少人工干预 | 依赖 Epic 1 Story 1.10 | P1-2 |
| Story 8.3 | L0/L1 自动固化流水线 | 高频修正模式转化为业务规则模板 | 依赖 Story 8.2 | P1-3 |
| Story 8.4 | 数据主权隔离执行 | 满足数据安全法和 PIPL 要求 | 依赖 Epic 1 Story 1.9/1.11 | P0-4 |
| Story 8.5 | ShieldCortex 提示注入防御 | 防止提示注入攻击导致数据泄露 | 依赖 Epic 1 Story 1.10 | P0-5 |
| Story 8.6 | 渗透测试与漏洞扫描 | 确保 MVP 无高危漏洞 | 依赖 Epic 1 Story 1.9/1.12 | P0-6 |

**✅ 依赖关系验证：**
- Epic 8 依赖 Epic 1 的 RBAC（Story 1.9）、审计日志（Story 1.10）、等保 2.0（Story 1.12）
- Epic 8 内部故事依赖均为**顺序依赖**（安全测试依赖基础安全功能）
- Epic 8 可独立交付价值（管理员管理权限和审计）
- 不依赖 Epic 2-7

**🔒 安全测试增强说明：**
- **Story 8.5（ShieldCortex）**：检测准确率≥95%，误报率<5%，支持规则热更新
- **Story 8.6（渗透测试）**：OWASP Top 10 全覆盖，无高危漏洞，中危<5 个，沙箱逃逸 0 次

### Story 8.1: 审计日志多维检索

As a **合规工程师**,
I want **系统按时间/角色/任务类型/修正级别多维检索审计日志**,
So that **支持合规审计和问题排查**。

**Acceptance Criteria:**

**Given** 审计日志已记录
**When** 执行多维检索
**Then** 支持按时间范围、角色、任务类型、修正级别组合查询
**And** 检索结果支持导出（CSV/PDF）

### Story 8.2: 修正分级判定基础（L0/L1 自动固化）

As a **系统架构师**,
I want **系统执行修正分级判定基础（L0 拼写/格式/L1 参数/权重 自动固化）**,
So that **L0/L1 级修正自动处理，减少人工干预**。

**Acceptance Criteria:**

**Given** 用户提交修正
**When** 执行修正分级判定
**Then** L0（拼写/格式）和 L1（参数/权重微调，影响≤1 任务，置信度≥0.85）自动固化
**And** 生成 Few-Shot 样本→Strat-Bench 测试→版本注册→WORM 存储

### Story 8.3: L0/L1 级修正自动固化流水线

As a **质量工程师**,
I want **系统自动固化 L0/L1 级修正（生成 Few-Shot 样本→Strat-Bench 测试→版本注册→WORM 存储）**,
So that **高频修正模式转化为业务规则模板**。

**Acceptance Criteria:**

**Given** L0/L1 级修正已判定
**When** 执行自动固化流水线
**Then** 生成 Few-Shot 样本，通过 Strat-Bench 测试（通过率≥90%）
**And** 版本注册，写入 WORM 存储，支持 24 小时内回滚

### Story 8.4: 数据主权隔离执行

As a **合规工程师**,
I want **系统执行数据主权隔离（敏感数据本地优先，外部网络调用需审计与白名单批准）**,
So that **满足数据安全法要求**。

**Acceptance Criteria:**

**Given** 处理敏感数据或发起外部调用
**When** 执行数据主权隔离
**Then** 敏感数据默认本地优先处理
**And** 外部网络调用需通过审计和白名单批准

### Story 8.5: ShieldCortex 提示注入防御

As a **安全工程师**,
I want **系统部署 ShieldCortex 提示注入检测器（正则匹配 + ML 分类器）**,
So that **防止提示注入攻击导致数据泄露**。

**Acceptance Criteria:**

**Given** 用户输入或外部数据进入系统
**When** 执行提示注入检测
**Then** 正则匹配已知攻击模式 + ML 分类器检测未知变体
**And** 检测准确率≥95%，误报率<5%
**And** 支持规则热更新

### Story 8.6: 渗透测试与漏洞扫描

As a **安全工程师**,
I want **系统执行渗透测试与漏洞扫描（OWASP Top 10 全覆盖）**,
So that **确保 MVP 无高危漏洞**。

**Acceptance Criteria:**

**Given** 系统部署完成
**When** 执行渗透测试与漏洞扫描
**Then** 无高危漏洞，中危漏洞<5 个
**And** SSL Labs A+ 评级，权限测试 100% 通过
**And** 沙箱逃逸测试 0 次成功

---

**⏸️ Step 02 完成 - 宗师级优化已应用**

## ✅ 宗师级优化完成总结

**已应用 4 条宗师级建议：**

### 建议 1：Epic 命名优化（增强价值感知）
- ✅ Epic 1: 基础架构与基础设施 → **企业级架构基础与合规**
- ✅ Epic 7: 用户界面与交互 → **多触点用户界面与 API 集成**
- ✅ Epic 8: 系统管理与合规 → **用户权限管理与审计合规**

### 建议 2：Epic 1 内部故事重组（按价值组）
- ✅ 价值组 1: 系统稳定性与性能基础（Story 1.1-1.8）
- ✅ 价值组 2: 安全与合规基础（Story 1.9-1.12）
- ✅ 每个故事增加依赖关系列

### 建议 3：FR 覆盖映射优化（双向追溯矩阵）
- ✅ 增加 FR 编号、FR 描述、归属 Epic、归属 Story、优先级列
- ✅ 覆盖 57 项 P0 FR 的双向追溯

### 建议 4：依赖关系验证
- ✅ Epic 1 内部故事依赖关系已验证
- ✅ **所有 Epic（1-8）依赖关系已验证**（见下表）

---

## 📊 全部 Epic 依赖关系验证总结

### Epic 依赖矩阵（含价值组和 Story 数）

| Epic | 价值组 | 依赖 Epic 1 | 依赖 Epic 2 | 依赖 Epic 3 | 内部依赖类型 | 可独立交付 | Story 数 |
|------|--------|-----------|-----------|-----------|------------|-----------|---------|
| **Epic 0: Iteration 0** | 开发环境/CI/CD/测试框架 | - | - | - | 顺序依赖 | ✅ 是 | 3 |
| **Epic 1: 企业级架构基础与合规** | 系统稳定性与性能基础<br/>安全与合规基础<br/>or.md 系统公理<br/>测试框架 | - | - | - | 组内依赖 | ✅ 是 | **18** |
| **Epic 2: 文档与数据管理** | 文档全生命周期管理 | Story 1.6/1.7 | - | - | 顺序依赖（流水线） | ✅ 是 | 8 |
| **Epic 3: 智能检索与知识发现** | 智能检索与溯源 | Story 1.5/1.6/1.7 | **Story 2.3（关键路径）** | - | 顺序依赖（流水线） | ✅ 是 | 12 |
| **Epic 4: 战略工具箱** | 战略工具执行能力 | Story 1.4/1.7 | - | - | 顺序依赖（工具链） | ✅ 是 | 5 |
| **Epic 5: Agent 协作系统** | 单 Agent 战略规划能力 | Story 1.4/1.9 | - | - | 顺序依赖（工作流） | ✅ 是 | 6 |
| **Epic 6: 战略规划流程** | 战略规划与审批能力<br/>UX 三视图 | Story 1.4/1.7 | Story 2.3 | Story 3.8 | 顺序依赖（BLM 流程） | ✅ 是 | **10** |
| **Epic 7: 多触点用户界面与 API 集成** | 多触点操作与监控能力<br/>NFR 覆盖<br/>测试 Story | Story 1.1/1.9/1.12/1.16 | - | - | 并行依赖 | ✅ 是 | **7** |
| **Epic 8: 用户权限管理与审计合规** | 安全与合规 | Story 1.5/1.7/1.9/1.10/1.12 | - | - | 顺序依赖（安全测试） | ✅ 是 | 6 |

**总计 Story 数：76 个**
- Iteration 0: 3 个（Story 0.1-0.3）
- Epic 1: 19 个（Story 1.1-1.16，新增 Story 1.13-1.16）
- Epic 2: 8 个
- Epic 3: 12 个
- Epic 4: 5 个
- Epic 5: 6 个
- Epic 6: 10 个（新增 Story 6.9-6.10）
- Epic 7: 7 个（新增 Story 7.5-7.7）
- Epic 8: 6 个

### 依赖关系验证结论

**✅ 所有 Epic 通过验证：**

1. **Epic 1 是基础依赖** - 所有其他 Epic 依赖 Epic 1 的存储层、安全层或架构骨架
2. **无跨 Epic 循环依赖** - 依赖方向单一（Epic 1 → Epic 2-8）
3. **每个 Epic 可独立交付价值** - 完成各自 Epic 的故事后，用户可使用完整功能
4. **内部依赖均为顺序/组内/并行依赖** - 无跨未来 Epic 的依赖
5. **关键路径已识别** - Story 2.3（版面信息保留）→ Epic 3 Story 3.8（高保真溯源）
6. **Iteration 0 优先** - Story 0.1-0.3 必须在 Iteration 1 前完成
7. **or.md 系统公理覆盖** - Story 1.14a/b/c（自主调用循环）、Story 1.15a/b（外部化记忆）
8. **NFR 完整覆盖** - Story 7.5（NFR-ACC-01）、Story 7.6（NFR-INT-05）、Story 1.13（NFR-SCALE-03）
9. **测试 Story 覆盖** - Story 1.16（集成测试框架）、Story 7.7（API E2E 测试）
10. **UX 三视图覆盖** - Story 6.8（高管视图）、Story 6.9（分析师视图）、Story 6.10（顾问视图）

### 关键依赖路径图

```
Epic 0（Iteration 0）
    │
    └──→ Epic 1（企业级架构基础与合规）
            ├──→ Story 1.13（K8s 动态扩缩容，NFR-SCALE-03）
            ├──→ Story 1.14a/b/c（自主调用循环，or.md 系统公理一）
            ├──→ Story 1.15a/b（外部化记忆，or.md 系统公理二）
            └──→ Story 1.16（集成测试框架，支持所有 Epic）
            │
            ├──→ Epic 2（文档与数据管理）───→ Epic 3（智能检索与知识发现）───→ Epic 6（战略规划流程）
            │       └─关键路径：Story 2.3（版面信息保留）→ Epic 3 Story 3.8（高保真溯源）
            │               │
            │               └──→ Epic 6: Story 6.9（分析师视图）、Story 6.10（顾问视图）
            │
            ├──→ Epic 4（战略工具箱）───────────────────────────────────────→ Epic 6（战略规划流程）
            │
            ├──→ Epic 5（Agent 协作系统）───────────────────────────────────→ Epic 6（战略规划流程）
            │
            ├──→ Epic 7（多触点用户界面与 API 集成）
            │       └─新增 Story：Story 7.5（无障碍设计，NFR-ACC-01）
            │       └─新增 Story：Story 7.6（API 契约测试，NFR-INT-05）
            │       └─新增 Story：Story 7.7（API E2E 测试，测试 Story）
            │
            └──→ Epic 8（用户权限管理与审计合规）
                    └─新增 Story：Story 8.5（ShieldCortex 提示注入防御）
                    └─新增 Story：Story 8.6（渗透测试与漏洞扫描）
```

### P0 关键改进建议实施状态

| 建议 | 状态 | 实施说明 |
|------|------|---------|
| **第 1 条：拆分 Story 1.14/1.15** | ✅ 已完成 | Story 1.14a/b/c（自主调用循环）、Story 1.15a/b（外部化记忆） |
| **第 2 条：Story 6.5/6.8 优先级优化** | ✅ 已完成 | Story 6.5 提升至 P0-5，Story 6.8 不依赖 Story 6.5 |
| **第 3 条：增加 NFR Story** | ✅ 已完成 | Story 7.5（NFR-ACC-01）、Story 7.6（NFR-INT-05）、Story 1.13（NFR-SCALE-03） |
| **额外：所有 Epic 价值组和依赖关系验证** | ✅ 已完成 | Epic 1-8 全部添加价值组表格、依赖关系验证、执行优先级 |

### P1 关键改进建议实施状态

| 建议 | 状态 | 实施说明 |
|------|------|---------|
| **第 3 条：增加 UX 三视图 Story** | ✅ 已完成 | Story 6.9（分析师视图）、Story 6.10（顾问视图） |
| **第 5 条：明确 Story 0.2 依赖** | ✅ 已完成 | Story 0.2（CI/CD）是所有 Epic 的前置依赖 |
| **第 6 条：增加测试 Story** | ✅ 已完成 | Story 1.16（集成测试框架）、Story 7.7（API E2E 测试） |
| **第 8 条：增加 or.md 追溯** | ✅ 已完成 | Story 1.14a/b/c（自主调用循环）、Story 1.15a/b（外部化记忆） |

---

**文档状态：** 本文档已完成 **Step 02（Epic 设计）**，P0 关键改进建议（第 1-3 条）已实施，P1 关键改进建议（第 3-5-6-8 条）已实施，所有 Epic 价值组和依赖关系验证已完成

**总计 Story 数：76 个**（Story 1.14a/b/c 拆分增加 2 个 + Story 1.16 + Story 6.9/6.10 + Story 7.7）

**下一步操作：**

**Select an Option:**
- **[A]** Advanced Elicitation - 深度需求挖掘
- **[P]** Party Mode - 多 Agent 评审
- **[C]** Continue - 继续到 Step 03（创建用户故事）
- **[A]** Advanced Elicitation - 深度需求挖掘
- **[P]** Party Mode - 多 Agent 评审
- **[C]** Continue - 继续到 Step 03（创建用户故事）
- **[C]** Continue - 继续到 Step 03（创建用户故事）
