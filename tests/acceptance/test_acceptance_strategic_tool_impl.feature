# language: zh-CN
功能: 战略工具执行实现
  作为工具工程师
  我希望将已注册的 23 种战略工具从"目录条目"转化为"可执行工具"
  以便 Agent 可以按 Think→Code→Execute→Observe→Validate 标准工作流调用工具

  背景:
    假如 战略工具执行服务已初始化（真实 InMemoryToolRepository + ToolRegistryService + ToolExecutionService + SkillLoader）
    并且 已注册 23 种战略工具
    并且 Skill 加载器包含 23 份 SKILL.md + skill_manifest 双向映射

  # ==========================================================================
  # AC-1: Tool 聚合根元数据字段增强 + ToolExecution 6 状态机
  # ==========================================================================
  场景: AC-1a - Tool 实体新增 4 元数据字段（向后兼容 23 个 TOOL_CATALOG）
    当 查询任意已注册工具（例如 PESTEL 分析）
    那么 返回 Tool 实体包含 rule_version 字段
    并且 返回 Tool 实体包含 reliability_score 字段（值 ∈ [0.0, 1.0]）
    并且 返回 Tool 实体包含 execution_count 字段（值 ≥ 0）
    并且 返回 Tool 实体包含 slug 字段（kebab-case 格式）
    并且 23 个 TOOL_CATALOG 实例不破坏现有功能

  场景: AC-1b - 4 字段不变量校验
    当 构造 Tool 实体的 reliability_score 为 1.5
    那么 抛出 EntityValidationError
    并且 错误码为 EXCEPTION_242
    当 构造 Tool 实体的 execution_count 为 -1
    那么 抛出 EntityValidationError
    当 构造 Tool 实体的 slug 为 "Invalid_Slug"
    那么 抛出 EntityValidationError

  场景: AC-1c - ToolExecutionState 6 状态枚举完整
    那么 ToolExecutionState 枚举包含 IDLE/PLANNING/EXECUTING/VALIDATING/COMPLETED/FAILED 共 6 值

  场景: AC-1d - 状态机主链正向迁移（IDLE→COMPLETED）
    当 创建初始 IDLE 状态的 ToolExecution
    并且 依次执行状态迁移 IDLE→PLANNING→EXECUTING→VALIDATING→COMPLETED
    那么 最终 state 为 COMPLETED
    并且 completed_at 不为空
    并且 state_version 单调递增

  场景: AC-1e - 中间态可转 FAILED
    当 创建 PLANNING 状态的 ToolExecution
    并且 执行状态迁移 PLANNING→FAILED
    那么 最终 state 为 FAILED
    并且 completed_at 不为空
    当 创建 EXECUTING 状态的 ToolExecution
    并且 执行状态迁移 EXECUTING→FAILED
    那么 最终 state 为 FAILED

  场景: AC-1f - 非法迁移抛 EntityStateTransitionError（EXCEPTION_243）
    当 创建 COMPLETED 状态的 ToolExecution
    并且 尝试反向迁移 COMPLETED→IDLE
    那么 抛出 EntityStateTransitionError
    并且 错误码为 EXCEPTION_243
    当 尝试跳过中间态 IDLE→EXECUTING
    那么 抛出 EntityStateTransitionError

  # ==========================================================================
  # AC-2: ToolExecutionService 应用层服务
  # ==========================================================================
  场景: AC-2 - ToolExecutionService.execute 委托元数据查询
    当 调用 ToolExecutionService.execute 传入有效 tool_id 和 ToolCall
    那么 委托 ToolRegistryService.get_tool 查询 Tool 元数据
    并且 返回 ToolResult（含 status/output/evidence_package）

  场景: AC-2b - 不存在的 tool_id 抛 ToolNotFoundError
    当 调用 ToolExecutionService.execute 传入不存在的 tool_id
    那么 抛出 ToolNotFoundError
    并且 错误码为 EXCEPTION_380

  # ==========================================================================
  # AC-3: 值对象完整性校验
  # ==========================================================================
  场景: AC-3 - ToolResult.success 状态必填 EvidencePackage
    假如 构造 ToolResult status=success 且 evidence_package=None
    那么 调用 validate_complete 抛出 EvidenceValidationFailedError
    并且 错误码为 EXCEPTION_386

  场景: AC-3b - EvidencePackage 缺 plan 字段抛 EvidenceValidationFailedError
    假如 构造 EvidencePackage plan=""（必填缺失）
    那么 调用 validate_complete 抛出 EvidenceValidationFailedError
    并且 错误码为 EXCEPTION_386
    并且 missing_fields 包含 "plan"

  场景: AC-3c - ToolResultStatus 4 值边界
    那么 ToolResultStatus 枚举包含 success/failed/invalid/insufficient_data 共 4 值

  # ==========================================================================
  # AC-4: ToolExecutionEngine 五阶段工作流（Mock 端口，验证端口映射）
  # ==========================================================================
  场景: AC-4 - 五阶段端口映射（Think/Code/Validate → LLM，Execute/Observe → Sandbox）
    当 引擎执行一次完整五阶段链路（使用 Mock LLMClient + Mock Sandbox）
    那么 Think 阶段调用 LLMClientPort.structured_generate 产出 plan
    并且 Code 阶段调用 LLMClientPort.structured_generate 产出 code
    并且 Execute 阶段调用 SandboxExecutor.execute_code 产出 result
    并且 Observe 阶段调用 SandboxExecutor.execute_code 产出 observation
    并且 Validate 阶段调用 LLMClientPort.structured_generate 产出 validation

  场景: AC-4b - 沙箱 Session 生命周期管理
    当 引擎执行一次完整五阶段链路（使用 Mock LLMClient + Mock Sandbox）
    那么 执行前调用 SandboxExecutor.start_container
    并且 执行后调用 SandboxExecutor.stop_container

  场景: AC-4c - 重试机制（LLMAPIError 触发指数退避）
    当 LLMClientPort 首次调用抛 LLMAPIError 后续成功
    那么 重试后引擎成功完成五阶段

  场景: AC-4d - 重试耗尽抛 ToolExecutionRetryExhaustedError
    当 LLMClientPort 持续抛 LLMAPIError 超过 max_attempts
    那么 抛出 ToolExecutionRetryExhaustedError
    并且 错误码为 EXCEPTION_383

  场景: AC-4e - EvidencePackage 9 字段完整
    当 引擎执行一次完整五阶段链路（使用 Mock LLMClient + Mock Sandbox）
    那么 ToolResult.evidence_package 包含 input_hash/rule_version/plan/code/result/observation/validation/confidence/citations 共 9 字段

  # ==========================================================================
  # AC-5: 端口注册（4 个新端口）
  # ==========================================================================
  场景: AC-5a - 4 个新端口已注册到 composition_root
    那么 tool_execution_repository 端口已注册
    并且 tool_execution_service 端口已注册
    并且 tool_execution_engine 端口已注册
    并且 skill_loader 端口已注册

  场景: AC-5b - 端口元数据完整（7 字段）
    假如 tool_execution_repository 端口已注册
    那么 PortSpec.name == "tool_execution_repository"
    并且 PortSpec.version == "v1.0.0"
    并且 PortSpec.lifetime == SCOPED
    并且 PortSpec.owner == "tool-team"
    并且 PortSpec.tags 包含 ("tool", "execution", "repository")
