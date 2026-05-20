# language: zh-CN
功能: Story 1.18a - Prefect 工作流引擎集成

  作为系统架构师
  我想要集成 Prefect 3.6+ 作为确定性数据管道引擎
  以便系统支持文档处理工作流的可靠执行与状态追踪

  背景:
    假如 Story 1.1 六边形架构骨架和 Story 1.3 事件总线已实现
    假如 PrefectConfig 已通过环境变量配置
    假如 PrefectEngine 已初始化并注入 EventPublisher

  # =========================================================================
  # AC-1: WorkflowEnginePort 端口定义
  # =========================================================================

  场景: AC-1 - WorkflowEnginePort 满足 Protocol 接口
    假如 WorkflowEnginePort 定义于 src/domain/ports/workflow_engine.py
    那么 WorkflowEnginePort 应该使用 runtime_checkable Protocol
    并且 定义 submit_flow 和 get_flow_status 异步方法
    并且 FlowStatus 枚举包含 PENDING/RUNNING/COMPLETED/FAILED/RETRYING 五个状态

  # =========================================================================
  # AC-2: PrefectEngine 实现
  # =========================================================================

  场景: AC-2 - PrefectEngine 满足 WorkflowEnginePort Protocol
    假如 PrefectEngine 使用 PrefectConfig 实例化
    那么 isinstance(PrefectEngine(...), WorkflowEnginePort) 应该返回 True
    并且 所有 import prefect 仅存在于 infrastructure/workflow/

  # =========================================================================
  # AC-3: DocumentProcessingFlow 执行
  # =========================================================================

  场景: AC-3 - 文档处理工作流结构验证
    假如 DocumentProcessingFlow 已定义
    那么 事件应包含 document_id, parse_result, embedding 字段

  # =========================================================================
  # AC-4: OrchestrationService 路由
  # =========================================================================

  场景: AC-4 - OrchestrationService 路由 data_pipeline 任务
    假如 OrchestrationService 注入了 WorkflowEnginePort
    那么 返回 WorkflowResult 包含 flow_run_id, status, submitted_at

  # =========================================================================
  # AC-5: 新领域事件定义
  # =========================================================================

  场景: AC-5 - RAGIndexed 和 ReportGenerated 事件定义
    假如 RAGIndexed 事件定义于 workflow_events.py
    那么 RAGIndexed 应包含 document_id, index_name, chunk_count 字段
    并且 ReportGenerated 应包含 report_id, report_type, file_path 字段
    并且 两事件应注册到 config/event_channels.yaml 的 RELIABLE 通道

  # =========================================================================
  # AC-6: PrefectConfig 配置
  # =========================================================================

  场景: AC-6 - PrefectConfig 从环境变量加载
    那么 from_env() 应从 PREFECT_API_URL 等环境变量读取配置
    并且 未设置环境变量时应使用合理默认值

  # =========================================================================
  # AC-7: Composition Root 注册
  # =========================================================================

  场景: AC-7 - Composition Root 注册 workflow 端口
    假如 composition_root.py 的 bootstrap() 已执行
    那么 WorkflowEnginePort 应注册为 PrefectEngine 实现
    并且 OrchestrationService 应注册为 SINGLETON
    并且 PrefectConfig 不注册为端口而是在 lambda 工厂中创建
