# language: zh-CN
# 验收测试 — Story 4.1a: 战略工具实现
# 对应 AC-1 ~ AC-7 业务价值验收
# TDD 阶段：红阶段 — 步骤定义尚未实现，pytest-bdd 收集时必须全部失败

@acceptance
功能: 战略工具从目录条目升级为可执行工具

  背景:
    Given 测试租户 TestTenant 已生成 UUID 前缀
    And 23 个工具元数据已通过 ToolRegistryService 注册到 InMemoryToolRepository
    And 7 个新异常（EXCEPTION_382/383/385/386/387/388/389）已注册到 _CLASS_TO_SUBDOMAIN

  @AC-1
  场景: Tool 实体新增 4 个元数据字段（rule_version/reliability_score/execution_count/slug）
    When 调用 ToolRegistryService.get_tool 获取任意已注册工具
    Then 返回的 Tool 实体应包含 rule_version 字段（业务规则版本，如 "BLM-v3.2"）
    And 返回的 Tool 实体应包含 reliability_score 字段（取值 [0.0, 1.0]）
    And 返回的 Tool 实体应包含 execution_count 字段（int ≥ 0）
    And 返回的 Tool 实体应包含 slug 字段（kebab-case 格式）
    And 23 个 TOOL_CATALOG 实例应保持 slug 唯一

  @AC-1
  场景: ToolExecution 聚合根 6 状态机正确迁移
    When 创建初始状态为 IDLE 的 ToolExecution
    And 顺序执行状态迁移 IDLE→PLANNING→EXECUTING→VALIDATING→COMPLETED
    Then 最终状态应为 COMPLETED 且 completed_at 不为空
    When 尝试从 COMPLETED 反向迁移到 IDLE
    Then 应抛出 EntityStateTransitionError (EXCEPTION_243)
    When 尝试从 PLANNING 直接跳到 COMPLETED（跳过中间态）
    Then 应抛出 EntityStateTransitionError (EXCEPTION_243)

  @AC-2
  场景: ToolExecutionService.execute 编排完整执行链路
    When 调用 ToolExecutionService.execute 传入有效 tool_id 和 ToolCall
    Then 应返回 ToolResult（含 status/output/evidence_package）
    And 应委托 ToolRegistryService.get_tool_metadata 获取 Tool 元数据

  @AC-3
  场景: ToolResult 完整性校验（缺字段抛 EvidenceValidationFailedError）
    Given 构造一个 ToolResult 缺少 plan 字段
    When 调用其完整性校验方法
    Then 应抛出 EvidenceValidationFailedError (EXCEPTION_386)

  @AC-4
  场景: ToolExecutionEngine 五阶段工作流（Think→Code→Execute→Observe→Validate）
    When 引擎执行一次完整五阶段链路
    Then Think 阶段应调用 LLMClientPort.structured_generate 产出 plan
    And Code 阶段应调用 LLMClientPort.structured_generate 产出 code
    And Execute 阶段应调用 SandboxExecutor.execute_code 产出 result
    And Observe 阶段应调用 SandboxExecutor.execute_code 产出 observation
    And Validate 阶段应调用 LLMClientPort.structured_generate 产出 validation
    And 最终 ToolExecution.state 应为 COMPLETED
    And EvidencePackage 应包含 9 字段（input_hash/rule_version/plan/code/result/observation/validation/confidence/citations）

  @AC-5
  场景: StrategicAnalysisUseCase 编排 tool_name→Skill→Execute→Event
    When 调用 use_case.execute(tool_name="pestel-analysis", arguments={...})
    Then 应通过 SkillLoaderPort.load_metadata 加载 L1 元数据
    And 应通过 SkillLoaderPort.load_sop 加载 L2 SOP
    And 应调用 ToolExecutionService.execute 触发五阶段执行
    And 应发布 ToolExecuted 事件（双通道 realtime + reliable）

  @AC-6
  场景: Skills 三级渐进式加载（TOOLS.md / SKILL.md ×23 / scripts+references）
    When 调用 SkillLoaderPort.load_metadata 加载 L1
    Then 应返回 ToolMetadata（含 tool_name/slug/category/input_schema/output_schema）
    When 调用 SkillLoaderPort.load_sop 加载 L2
    Then 应返回 SkillDocument（含 tool_name/slug/content/token_count）
    When 调用 SkillLoaderPort.load_references 加载 L3
    Then 应返回脚本/参考文件 bytes

  @AC-7
  场景: 4 个新端口在 composition_root 注册完整
    When 调用 resolver.resolve("tool_execution_repository")
    Then 应返回 InMemoryToolExecutionRepository 实例
    When 调用 resolver.resolve("tool_execution_service")
    Then 应返回 ToolExecutionService 实例
    When 调用 resolver.resolve("tool_execution_engine")
    Then 应返回 ToolExecutionEngine 实例
    When 调用 resolver.resolve("skill_loader")
    Then 应返回 InMemorySkillLoader 实例
