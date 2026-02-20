企业战略规划管理智库系统需求特性列表

一、架构哲学与核心原则
    1. 采用领域驱动设计（DDD）与六边形架构为核心架构哲学
        [1]. 领域层（Domain）：封装企业战略规划核心领域逻辑，包括文档、AGENT、工具、战略规划、业务计划等领域实体，领域服务不依赖任何外部技术实现，仅依赖领域模型与领域规则
        [2]. 应用层（Application）：定义用例服务（Use Cases），编排领域对象完成具体业务目标，包括文档处理用例、战略分析用例、AGENT 协作用例、规划生成用例，应用层协调领域层与基础设施层交互
        [3]. 接口层（Interfaces）：实现输入适配器（CLI、API、事件监听）与输出适配器（数据库、消息队列、外部服务），隔离外部系统与领域层，支持技术栈独立演进
        [4]. 基础设施层（Infrastructure）：实现领域层定义的仓储接口与领域服务接口，包括持久化存储（Redis/PostgreSQL/Qdrant/MinIO/Neo4j）、消息总线（RabbitMQ）、外部服务适配器（LLM API、嵌入模型）
    2. 支持事件驱动架构（Event-Driven Architecture）作为系统核心流转机制
        [1]. 领域事件（Domain Events）：定义核心业务事件包括文档处理完成事件、工具执行完成事件、AGENT 决策完成事件、检查点到达事件、修正审批事件，事件携带完整业务上下文
        [2]. 事件总线（Event Bus）：基于发布/订阅模式实现领域事件的路由与分发，支持事件持久化、事件回溯、事件重放，事件格式标准化（事件 ID、类型、时间戳、载荷、来源、Schema 版本）
        [3]. 事件溯源（Event Sourcing）：关键业务实体状态变更通过领域事件序列记录，支持状态重建、审计追踪、时间旅行调试，事件存储至不可变日志（WORM 存储）
    3. 支持两个核心抽象作为系统设计与实现基础
        [1]. 系统公理一 - 自主调用：系统基于 trigger(事件)→route(路由)→execute(执行) 的自主调用循环构建，其中 trigger 由领域事件或周期性心跳事件触发，route 基于 session_id 哈希或语义路由至目标 AGENT 或工具，execute 在会话命名空间中执行并支持状态持久化与中断恢复，状态快照序列化至高速缓存存储（支持主从复制与故障转移，TTL 可配置 24 小时至 30 天）
        [2]. 系统公理二 - 外部化记忆：系统遵循 LLM 上下文=缓存、磁盘记忆=真相源的记忆分离原则，会话状态与推理轨迹持久化存储至战略档案库（采用分层存储架构：高速缓存层处理会话状态与语义缓存、关系存储层处理用户权限与审计元数据、向量存储层处理嵌入向量与相似度检索、对象存储层处理原始文档与版本快照、图存储层处理知识图谱与实体关系），LLM 上下文仅保留当前任务必需的压缩信息，防止上下文爆炸；支持检索 - 压缩循环机制，压缩前必须执行持久化笔记步骤防止信息丢失
    4. 支持混合部署策略（本地 80%+ 云端 20%），常规检索/摘要/数值计算本地执行（Ollama+bge-m3+Python 沙箱），复杂战略分析/多 Agent 辩论/深度推理云端执行（Claude-4.5/GPT-4-Turbo），路由决策基于合规性优先（敏感数据强制本地）+ 任务类型 + 历史成功率（50%）+ 成本预测（30%）+ 数据驻留要求（20%）

二、领域建模：基于 or.md 功能需求抽象为核心领域实体、领域服务与领域事件
    1. 核心领域实体（Domain Entities）
        [1]. 文档实体（Document）：支持 17 种格式（pdf/txt/doc/docx/ppt/pptx/xls/xlsx/csv/jpeg/png/gif/markdown/html 及 zip/tar 压缩包）的元数据、版本历史、解析结果、嵌入向量引用、血缘追踪，支持音视频转录文本接入；支持文档上传、更新、删除、版本快照、分类管理领域操作；不变约束包括最小元字段集校验（creator/created_at/source/license/business_domain）、版本冲突检测与解决策略（乐观锁/悲观锁可选）
        [2]. AGENT 实体（Agent）：支持 7 类核心角色（CEO/CFO/COO/CMO/CHO/CTO/AUD）的身份档案、权责边界、领域知识、技能列表、验证器、演进日志；支持动态角色配置（核心角色必须遵守、扩展角色可协商按需加载）、实例池化、动态扩缩容领域操作；不变约束包括视角隔离（Prompt/工具/数据三重硬隔离）、会话状态持久化
        [3]. 工具实体（Tool）：支持 17 种战略工具（PESTEL/波特五力/$APPEALS/竞争对手分析/价值链分析/安索夫矩阵/SWOT-TOWS/GE-麦肯锡矩阵/SPACE 矩阵/情景规划/价值主张画布/商业模式画布/破坏性创新模型/BSC/战略地图/KPI/变革管理模型）的唯一标识、输入/输出 Schema、执行逻辑模板、领域事实库、验证器、演进日志；支持工具注册、版本控制、灰度发布、回滚领域操作；不变约束包括契约化输出（Pydantic V2 Schema）、沙箱执行隔离
        [4]. 战略规划实体（StrategicPlan）：支持五年滚动战略规划（SP）的 BLM 六阶段模型（业绩差距分析、市场洞察六子步骤、战略意图与目标、创新焦点、业务设计、执行设计）；支持 Checkpoint 机制、用户反馈修正、证据包打包领域操作；不变约束包括 BLM 模型流程不变性、结构化差异校验（Strat-Bench 通过率≥90%）
        [5]. 业务计划实体（BusinessPlan）：支持年度业务计划（BP）的 BEM 六阶段模型（澄清战略方向与运营定义、导出中长期关键战略举措、导出战略衡量指标、确定年度业务关键措施并导出具体目标、分解关键措施和目标、导出重点工作计划）；支持从 SP 到 BP 的结构化映射转换（战略解码器）；不变约束包括 BEM 模型流程不变性、SP 输出到 BP 输入的 Schema 强制映射
        [6]. 检查点实体（Checkpoint）：支持 SP/BP 各阶段的 Checkpoint 快照，包括阶段标识、完成状态、用户反馈、修正记录、恢复点引用；支持 Checkpoint 创建、恢复、修改中间状态变量、继续执行领域操作；不变约束包括状态快照序列化至 Redis、支持 Time-travel 能力
        [7]. 战略档案实体（StrategicArchive）：支持时序战略档案库的永久存储，包括历年 SP/BP 的关键假设变量、决策依据、实际执行偏差、证据包；支持事实有效期标签管理（valid_from/valid_until）、数据陈旧标记（超 12 个月自动降权）、时间轴演进查询领域操作；不变约束包括向量存储 + 对象存储协同架构、不可变存储引用
    2. 领域服务接口（Domain Services）
        [1]. 文档处理服务（DocumentService）：定义文档解析、嵌入生成、索引构建、版本管理、血缘追踪的领域接口；基础设施层实现包括 Unstructured.io 适配器、bge-m3 嵌入生成器、Qdrant 向量索引、MinIO 版本存储
        [2]. RAG 检索服务（RAGService）：定义混合检索（Dense+Sparse+Graph）、分层检索（L1-L4）、查询路由、相关性评估的领域接口；基础设施层实现包括 Qdrant 混合检索、Neo4j 图遍历、RRF 融合排序算法、ColBERT-v2 重排序器
        [3]. 工具箱服务（ToolService）：定义工具注册、工具调用、工具链编排、契约测试的领域接口；基础设施层实现包括 MCP Registry、Docker 沙箱执行器、Pydantic V2 验证器、工具可靠性评分计算
        [4]. AGENT 协作服务（AgentService）：定义 AGENT 实例化、任务分解、协作编排、视角隔离的领域接口；基础设施层实现包括 LangGraph 状态图、Redis 公共黑板、SYS AGENT 裁决状态机、辩论质量评估器
        [5]. 规划生成服务（PlanningService）：定义 BLM/BEM 流程编排、Checkpoint 管理、用户反馈处理、证据包生成的领域接口；基础设施层实现包括 BLM 状态机、BEM 状态机、PostgreSQL Checkpoint 存储、证据包打包器
        [6]. 评估服务（EvaluationService）：定义摘要质量评估（信息熵 + 关键实体覆盖率，评分<0.7 二次生成）、检索相关性评估（动态阈值判定，<0.6 标注数据不足）、决策质量评估（贝叶斯网络置信度）、一致性检验（五维一致性）的领域接口；基础设施层实现包括信息熵计算、LLM-as-a-Judge、规则引擎一致性校验、沙箱数值重计算
        [7]. 可视化服务（VisualizationService）：定义决策过程可视化、溯源树展示、健康度仪表盘、影响模拟器领域的接口；基础设施层实现包括 D3.js 渲染器、溯源数据聚合器、指标计算引擎
    3. 领域事件定义（Domain Events）
        [1]. 文档处理完成事件（DocumentProcessed）：携带文档 ID、解析结果摘要、嵌入向量引用、血缘信息；触发下游实体抽取、图谱构建、索引更新
        [2]. 工具执行完成事件（ToolExecuted）：携带工具 ID、执行结果、成本审计信息、证据包引用；触发下游 AGENT 决策、成本聚合、技能演进
        [3]. AGENT 决策完成事件（AgentDecided）：携带 AGENT ID、决策结果、置信度评分、引用源列表；触发下游 SYS AGENT 仲裁、公共黑板更新、审计日志记录
        [4]. 检查点到达事件（CheckpointReached）：携带阶段标识、阶段性结果、用户反馈请求、恢复点引用；触发用户交互、反馈收集、状态持久化
        [5]. 修正审批事件（CorrectionApproved）：携带修正类型（enum[参数/权重/约束/假设]）、修正前后值、审批链、影响范围；触发自动固化流水线、版本注册、演进日志记录
        [6]. 战略偏差预警事件（StrategicDeviationWarning）：携带偏差类型、偏差等级（轻微/中等/严重）、实际值、规划值、阈值（默认 10%）；触发相关 AGENT 响应、偏差分析报告生成
        [7]. 心跳唤醒事件（HeartbeatTriggered）：携带心跳 ID、唤醒原因、待办事项列表、成本预算；触发周期性任务检查、偏差预警检查、成本预算校验（失败 3 次指数退避重试，连续失败触发告警）

三、应用层：用例服务编排领域对象完成具体业务目标
    1. 文档处理用例（DocumentProcessingUseCase）
        [1]. 支持批量文档上传与解析：接收文档上传命令，调用文档处理服务解析 17 种格式，动态批次管理（基于总大小 20GB），流式处理防止内存溢出，分片上传与断点续传，生成嵌入向量，构建索引，发布文档处理完成事件
        [2]. 支持文档版本管理：接收文档更新命令，创建版本快照（对象存储版本控制），记录差异摘要（diff），更新血缘追踪，发布文档版本创建事件
        [3]. 支持文档检索与溯源：接收文档查询命令，调用 RAG 检索服务返回文档列表，支持高保真视觉级溯源（Bounding Box）跳转至原始文档坐标点
    2. 战略分析用例（StrategicAnalysisUseCase）
        [1]. 支持单工具分析：接收工具调用命令，实例化工具实体，执行 Think→Code→Execute→Observe→Validate 原子循环，发布工具执行完成事件
        [2]. 支持工具链编排：接收工具链调用命令，解析工具链 DAG，按拓扑顺序调度子任务，并行执行无依赖子任务，聚合最终结果
        [3]. 支持红蓝辩论机制：接收争议议题，实例化激进派与保守派子智能体，执行结构化辩论（最多 7 轮，三阶段：发散 Temperature=0.8→收敛 Temperature=0.5→裁决 Temperature=0.2），输出共识与分歧区域风险全景视图
    3. AGENT 协作用例（AgentCollaborationUseCase）
        [1]. 支持单 AGENT 任务执行：接收 AGENT 任务命令，实例化 AGENT 实体，加载身份档案（IDENTITY.md/CODE.md/SOUL.md/TOOLS.md/USER.md/MEMORY.md/HEARTBEAT.md）与工具集，执行标准工作流（感知→规划→执行→验证→反思→证据打包）
        [2]. 支持多 AGENT 协作：接收多 AGENT 协作命令，SYS AGENT 解析目标并分解任务，各专业 AGENT 并行执行子任务，调度器协调资源与依赖，自动生成协作依赖图（基于 BLM/BEM 阶段）
        [3]. 支持 AGENT 仲裁与决策：接收仲裁请求，SYS AGENT 执行裁决状态机（最大辩论轮次 3+ 风险等级，上限 7 轮），未达成一致时生成三套方案（Plan A 保守/Plan B 激进/Plan C AI 融合版），强制暂停 5 分钟请求用户介入，超时无操作按编排器决策执行
    4. 规划生成用例（PlanningGenerationUseCase）
        [1]. 支持 SP 规划生成：接收 SP 规划命令，执行 BLM 六阶段状态机（业绩差距分析→市场洞察六子步骤→战略意图与目标→创新焦点→业务设计→执行设计），各阶段触发 Checkpoint 机制，输出 JSON 思维链（Input→<Reflection>→<Tools_Used>→<Constraints_Check>→JSON）
        [2]. 支持 BP 规划生成：接收 BP 规划命令，执行战略解码器将 SP 输出映射为 BP 输入，执行 BEM 六阶段状态机，各阶段触发 Checkpoint 机制，输出 JSON 思维链
        [3]. 支持 Checkpoint 交互：接收 Checkpoint 恢复命令，加载检查点实体，支持用户修正关键参数，从修改点继续执行（Time-travel 能力）
    5. 系统操作用例（SystemOperationsUseCase）
        [1]. 支持用户认证与权限管理：接收登录命令，验证用户凭证，加载 RBAC 权限，生成 JWT 令牌，记录审计日志
        [2]. 支持成本熔断与监控：接收成本监控事件，聚合任务级/会话级/系统级成本，触发三级熔断机制（任务级：单次 5K/50K tokens；会话级：日配额 100 万 tokens；系统级：连续 3 次失败或成本超预算 200%）
        [3]. 支持性能漂移检测：接收性能指标事件，执行 CUSUM 算法检测连续性能下降（滑动窗口 7 天），触发根因分析与告警

四、接口层：输入适配器与输出适配器隔离外部系统与领域层
    1. 输入适配器（Inbound Adapters）
        [1]. CLI 适配器：支持命令行接口（click 框架），解析文档上传、AGENT 调用、规划生成、系统查询命令，转换为应用层命令对象
        [2]. REST API 适配器：支持 FastAPI 框架，实现 OpenAPI 3.1 规范，提供文档管理、工具调用、AGENT 协作、规划生成、系统管理 REST 接口，API Gateway 统一入口（统一认证 OAuth 2.1/JWT、限流令牌桶算法、路由基于路径/方法/角色、安全控制请求验证/注入检测）
        [3]. 事件监听适配器：支持 RabbitMQ 事件消费者，监听领域事件（文档处理完成、工具执行完成、AGENT 决策完成），触发下游应用层用例
        [4]. 无障碍设计适配器：遵循 WCAG 2.1 AA 标准，支持键盘导航、屏幕阅读器兼容、色盲友好配色
        [5]. 多语言界面适配器：支持中文与英文界面切换，术语表统一翻译
    2. 输出适配器（Outbound Adapters）
        [1]. 数据库适配器：实现领域层定义的仓储接口，包括 PostgreSQL 文档仓储、Qdrant 向量仓储、Neo4j 图谱仓储、Redis 会话仓储、MinIO 对象仓储
        [2]. 外部服务适配器：支持 LLM API 调用（LiteLLM 统一代理，动态模型路由：简单任务 Ollama 本地/复杂任务 Claude/GPT-4 云端）、嵌入模型调用（bge-m3/Ollama）、OCR 服务调用（中/英 OCR，置信度<0.85 标注待复核）、代码沙箱执行（Docker 网络隔离 + 权限最小化）
        [3]. 消息总线适配器：支持 RabbitMQ 事件发布，包括事件序列化、路由键绑定、死信队列处理、事件持久化

五、基础设施层：实现领域层定义的仓储接口与领域服务接口
    1. 高速缓存存储实现（Redis 7.0+）
        [1]. 支持会话状态快照存储：StateSnapshot 序列化至 Redis Hash，TTL 24 小时，支持主从复制与故障转移
        [2]. 支持语义缓存：查询嵌入（bge-m3）存储至 Redis Vector，相似度>0.9 直接命中，缓存失效策略（TTL 24 小时 + 事件驱动失效 + 版本感知失效），目标降低 Token 消耗 40-50%
        [3]. 支持发布/订阅事件总线：领域事件发布至 Redis Pub/Sub 通道，事件消费者订阅对应通道，支持事件重试与死信处理
        [4]. 支持多版本并发控制（MVCC）：公共黑板状态版本存储至 Redis Sorted Set，支持时间旅行查询与版本回滚
    2. 关系存储实现（PostgreSQL 15+）
        [1]. 支持用户认证与 RBAC 权限：用户表、角色表、权限表、用户 - 角色关联表、角色 - 权限关联表，支持 OAuth 2.1/JWT 集成
        [2]. 支持审计日志元数据：审计日志表（log_id/timestamp/actor/action_type/target_resource/old_value/new_value/confidence_delta/impact_scope/approval_chain/worm_storage_ref），与 MinIO WORM Bucket 引用关联
        [3]. 支持业务元数据：文档元数据表、工具注册表、AGENT 状态表、Checkpoint 表、战略规划表、业务计划表
        [4]. 支持事务性操作与外键约束：ACID 事务保证、外键约束、唯一约束、检查约束，支持 Alembic 迁移管理
    3. 向量存储实现（Qdrant 1.7+）
        [1]. 支持嵌入向量存储：Collection 命名规范（documents/embeddings/strategic_archive），向量维度 1024（bge-m3），COSINE 相似度度量
        [2]. 支持混合检索：Dense 检索（bge-m3）+ Payload 过滤（业务域/时间范围/文档类型）+ BM25 稀疏检索，双路召回基座，支持 RRF 融合排序与 ColBERT-v2 重排序（延迟预算 P95<200ms，分级精排 Top-100→Top-20）
        [3]. 支持时间旅行查询：向量点版本管理，支持按版本号或时间戳查询历史状态
        [4]. 支持 Collection 多租户隔离：按业务域或项目分离 Collection，支持 Collection 级别访问控制
    4. 对象存储实现（MinIO 最新）
        [1]. 支持原始文档 BLOB 存储：Bucket 命名规范（documents/audit-logs/versions/backups），支持 S3 兼容协议
        [2]. 支持版本快照与断点续传：MinIO 版本控制启用，分片上传（基于总大小 20GB 动态批次），断点续传记录上传 ID 与分片 ETag
        [3]. 支持不可变存储（WORM）模式：审计日志 Bucket 启用 Object Lock（COMPLIANCE 模式），保留期限 7 年（SOX 合规要求），支持归档至冷存储与以审计友好格式（CSV/PDF）导出
        [4]. 支持对象生命周期管理：自动过期策略（临时文件 30 天）、自动分层（热数据→温数据→冷数据）
    5. 图存储实现（Neo4j 5.x）
        [1]. 支持知识图谱存储：实体节点（Entity）包括类型、名称、属性，关系边（Relationship）包括类型、方向、权重；采用 LLM+ 规则混合实体抽取（规则基准确率≥80%，LLM 语义高召回率，冲突仲裁器权重规则 0.6/LLM0.4）
        [2]. 支持 Parent-Child 层级索引：L1 跨文档摘要→L2 文档摘要→L3 文档切片→L4 实体级片段，支持自顶向下与自底向上双向遍历（图数据库层级关系或关系数据库 parent-join 实现）
        [3]. 支持实体对齐与消歧：基于编辑距离 + 语义相似度（bge-m3）双路匹配，阈值≥0.85 判定为同一实体，支持同义词归并（如"华为"/"Huawei"统一为"华为"）
        [4]. 支持图遍历查询：Cypher 查询模板包括实体关联查询、路径查询、社区发现算法（Louvain/Label Propagation），实现 GraphRAG 增强检索

六、领域事件驱动流转：核心业务场景的事件流转设计
    1. 文档处理事件流转
        [1]. 文档上传完成 → 发布 DocumentUploaded 事件 → 触发文档解析用例 → 发布 DocumentParsed 事件 → 触发嵌入生成用例 → 发布 EmbeddingGenerated 事件 → 触发索引构建用例 → 发布 DocumentIndexed 事件 → 触发实体抽取用例 → 发布 EntitiesExtracted 事件 → 触发图谱构建用例 → 发布 DocumentProcessed 事件
    2. 战略分析事件流转
        [1]. 分析任务创建 → 发布 TaskCreated 事件 → 触发工具选择用例 → 发布 ToolSelected 事件 → 触发工具执行用例 → 发布 ToolExecuted 事件 → 触发结果验证用例 → 发布 ResultValidated 事件 → 触发证据打包用例 → 发布 AnalysisCompleted 事件
    3. AGENT 协作事件流转
        [1]. AGENT 任务分配 → 发布 AgentTaskAssigned 事件 → 触发 AGENT 实例化用例 → 发布 AgentInitialized 事件 → 触发 AGENT 执行用例 → 发布 AgentDecided 事件 → 触发 SYS AGENT 仲裁用例 → 发布 ArbitrationCompleted 事件 → 触发公共黑板更新用例 → 发布 BlackboardUpdated 事件
    4. 规划生成事件流转
        [1]. SP/BP 规划启动 → 发布 PlanningStarted 事件 → 触发 BLM/BEM 状态机用例 → 各阶段完成发布 StageCompleted 事件 → 触发 Checkpoint 创建用例 → 发布 CheckpointReached 事件 → 触发用户反馈用例 → 发布 FeedbackReceived 事件 → 触发 Checkpoint 恢复用例 → 发布 PlanningResumed 事件 → 规划完成发布 PlanningCompleted 事件
    5. 修正审批事件流转
        [1]. 用户修正提交 → 发布 CorrectionSubmitted 事件 → 触发修正分级判定用例 → 发布 CorrectionClassified 事件（L0/L1/L2/L3） → L0/L1 触发自动固化用例 → 发布 CorrectionSolidified 事件；L2 触发专家确认用例（1 人，4 小时 SLA，紧急通道 1 小时） → 发布 CorrectionConfirmed 事件；L3 触发委员会审批用例（≥3 人，48 小时 SLA） → 发布 CorrectionApproved 事件 → 触发版本注册用例 → 发布 VersionRegistered 事件 → 触发演进日志记录用例 → 发布 EvolutionLogged 事件

七、统一标准文档（全系统通用）
    1. 统一修正分级标准文档
        [1]. 定义全系统通用的四级修正分级体系（L0/L1/L2/L3），适用于数据处理、工具箱、AGENT、战略规划所有模块
        [2]. 明确各级修正的触发条件、审批流程、SLA 时限、回滚机制
        [3]. 修正分级判定器判定准确率目标≥85%，判定证据写入统一审计日志
    2. 统一审计日志 Schema（EvolutionLog 扩展）
        [1]. 定义统一审计日志字段：log_id（UUID）、timestamp（ISO 8601）、actor（角色/用户 ID）、action_type（enum）、target_resource（资源 ID）、old_value（JSON）、new_value（JSON）、confidence_delta（float）、impact_scope（int）、approval_chain（array）、worm_storage_ref（URI，指向不可变存储对象）
        [2]. 审计日志保留期限 7 年（SOX 合规要求），支持归档至冷存储与以审计友好格式（CSV/PDF）导出
        [3]. 支持按时间/角色/任务类型/修正级别多维检索与聚合分析
    3. 统一指标计算手册（Metric Handbook）
        [1]. 定义检索指标计算口径：precision@k=检索相关文档数/k，recall@k=检索相关文档数/总相关文档数，MRR=1/首个相关文档排名，NDCG@k=归一化折损累计增益
        [2]. 定义生成质量指标计算口径：Faithfulness=生成内容可溯源比例/总陈述数，Answer_Relevance=相关回答数/总回答数，Hallucination_Rate=不可溯源陈述数/总陈述数
        [3]. 定义性能指标计算口径：检索延迟 P95=95% 检索请求延迟上限（ms），生成延迟 P95=95% 生成请求延迟上限（ms），Token_Throughput=总 tokens/总时长（tokens/s）
        [4]. 定义业务指标计算口径：决策采纳率=被采纳决策数/总决策数，规划完成率=已完成规划项/总规划项，NPS=推荐者数 - 贬损者数，用户修正率=用户修正次数/总生成次数
        [5]. 指标计算逻辑版本化管理，变更需通过变更控制委员会审批

八、架构约束与品质要求
    1. 领域层独立性约束
        [1]. 领域层不得依赖任何外部框架（如 LangGraph、Prefect、FastAPI），仅依赖 Python 标准库与领域模型
        [2]. 领域层定义的仓储接口与领域服务接口，基础设施层必须通过依赖注入（Dependency Injection）实现
        [3]. 领域实体与领域服务的单元测试不得访问数据库、消息队列、外部 API，仅通过 Mock 测试
    2. 事件驱动一致性约束
        [1]. 所有领域事件必须发布至事件总线，不得直接调用下游服务
        [2]. 领域事件处理必须幂等，支持事件重放与失败重试
        [3]. 事件 Schema 必须版本化管理，支持向后兼容 1-2 个版本
    3. 分层存储一致性约束
        [1]. 各存储层通过仓储模式向领域层提供统一接口，领域层不直接依赖具体存储实现
        [2]. 跨存储层事务通过 Saga 模式或事件溯源保证最终一致性
        [3]. 数据契约（Data Contract）定义包括文档/片段/摘要/向量/图谱 Schema，集成 CI 契约测试
    4. 安全与合规约束
        [1]. 敏感数据（个人可识别信息、商业机密）存储前必须脱敏或加密（加密-at-rest）
        [2]. 审计日志必须写入不可变存储（WORM），保留期限 7 年，支持 SOX/ISO27001 审计导出
        [3]. 提示注入检测（ShieldCortex）必须无侵入拦截所有外部输入（正则匹配已知攻击模式+ML 分类器检测未知变体），准确率目标≥95%
        [4]. 零信任纵深防御体系：第一层隔离（Prompt/工具/数据三重硬隔离）、第二层执行（Docker 沙箱）、第三层检测（视角越界/幻觉累积/提示注入）、第四层审计（WORM 存储）、第五层熔断（辩论过热/成本熔断），各层联动
    5. 性能与成本约束
        [1]. 检索延迟 P95<200ms，生成延迟 P95<5000ms，语义缓存命中率>40%，目标降低 Token 消耗 40-50%
        [2]. 三级成本熔断机制（任务级/会话级/系统级）必须启用，熔断阈值基于历史消耗动态调整，支持预算周期（日/周/月）配置
        [3]. 动态模型路由必须启用，简单任务本地执行（Ollama），复杂任务云端执行（Claude/GPT-4），基于语义匹配（60%）+ 历史成功率（40%）计算路由策略，目标降低成本 30-60%
        [4]. 数据质量基准（DQI = 0.4*完整性 + 0.3*唯一性 + 0.3*时效性），入库触发 CI/CD 质量门禁，当 DQI < 0.6 时自动阻断自动化流程，进入人工审核队列