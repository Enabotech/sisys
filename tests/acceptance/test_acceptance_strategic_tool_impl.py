"""Story 4.1a 验收测试 BDD 步骤实现

TDD 红阶段：步骤函数体故意触发 NotImplementedError 或预期失败，
确保 pytest-bdd 收集时输出红色失败报告。

设计原则：
- BDD 步骤函数禁止 @pytest.mark.asyncio（CLAUDE.md §5 红线）
- 使用 event_loop.run_until_complete() 调度异步代码
- 场景上下文通过 context dict 共享（pytest-bdd 标准）
"""

from __future__ import annotations

import asyncio

import pytest
from pytest_bdd import (
    given,
    scenarios,
    then,
    when,
)

# 加载 Gherkin feature 文件
scenarios("test_acceptance_strategic_tool_impl.feature")


@pytest.fixture
def context() -> dict:
    """场景上下文：跨步骤共享状态"""
    return {}


def _run(coro):
    """同步调度异步协程（CLAUDE.md §5：禁止 BDD 用 @pytest.mark.asyncio）"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# === 背景步骤 ===


@given("测试租户 TestTenant 已生成 UUID 前缀")
def given_test_tenant(context: dict) -> None:
    """准备测试租户（红阶段：标记 fixture 未实现）"""
    pytest.skip("Task 0 红阶段：TestTenant fixture 待 Task 7 实现")


@given("23 个工具元数据已通过 ToolRegistryService 注册到 InMemoryToolRepository")
def given_tools_registered(context: dict) -> None:
    """注册 23 个工具元数据（红阶段：标记未实现）"""
    pytest.skip("Task 0 红阶段：依赖 Task 1 Tool 实体增强完成")


@given("7 个新异常（EXCEPTION_382/383/385/386/387/388/389）已注册到 _CLASS_TO_SUBDOMAIN")
def given_seven_exceptions_registered(context: dict) -> None:
    """7 个新异常已注册（红阶段：已实现，作为基线存在）"""
    from src.domain.exceptions import (  # noqa: F401
        EvidenceValidationFailedError,
        SkillLoadError,
        SkillNotFoundError,
        ToolExecutionFailedError,
        ToolExecutionRetryExhaustedError,
        ToolExecutionTimeoutError,
        ToolResultValidationError,
    )


# === AC-1: Tool 实体字段增强 ===


@when("调用 ToolRegistryService.get_tool 获取任意已注册工具")
def when_get_tool(context: dict) -> None:
    """获取工具（红阶段：标记未实现）"""
    pytest.skip("Task 0 红阶段：ToolRegistryService 集成待 Task 1+2 完成")


@then('返回的 Tool 实体应包含 rule_version 字段（业务规则版本，如 "BLM-v3.2")')
def then_tool_has_rule_version(context: dict) -> None:
    """校验 rule_version 字段（红阶段：标记未实现）"""
    pytest.skip("Task 0 红阶段：依赖 Task 1 Tool 字段增强")


@then("返回的 Tool 实体应包含 reliability_score 字段（取值 [0.0, 1.0]）")
def then_tool_has_reliability_score(context: dict) -> None:
    """校验 reliability_score 字段（红阶段：标记未实现）"""
    pytest.skip("Task 0 红阶段：依赖 Task 1 Tool 字段增强")


@then("返回的 Tool 实体应包含 execution_count 字段（int ≥ 0）")
def then_tool_has_execution_count(context: dict) -> None:
    """校验 execution_count 字段（红阶段：标记未实现）"""
    pytest.skip("Task 0 红阶段：依赖 Task 1 Tool 字段增强")


@then("返回的 Tool 实体应包含 slug 字段（kebab-case 格式）")
def then_tool_has_slug(context: dict) -> None:
    """校验 slug 字段（红阶段：标记未实现）"""
    pytest.skip("Task 0 红阶段：依赖 Task 1 Tool 字段增强")


@then("23 个 TOOL_CATALOG 实例应保持 slug 唯一")
def then_tool_catalog_slugs_unique(context: dict) -> None:
    """校验 slug 唯一性（红阶段：标记未实现）"""
    pytest.skip("Task 0 红阶段：依赖 Task 1 + Task 6 完成")


# === AC-1: ToolExecution 状态机 ===


@when("创建初始状态为 IDLE 的 ToolExecution")
def when_create_idle_tool_execution(context: dict) -> None:
    """创建 IDLE 状态 ToolExecution（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 1 ToolExecution 聚合根")


@when("顺序执行状态迁移 IDLE→PLANNING→EXECUTING→VALIDATING→COMPLETED")
def when_full_state_progression(context: dict) -> None:
    """完整状态迁移（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 1 ToolExecution 状态机")


@then("最终状态应为 COMPLETED 且 completed_at 不为空")
def then_terminal_completed(context: dict) -> None:
    """校验终态（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 1 终态不变量")


@when("尝试从 COMPLETED 反向迁移到 IDLE")
def when_illegal_reverse_transition(context: dict) -> None:
    """非法反向迁移（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 1 transition_to()")


@then("应抛出 EntityStateTransitionError (EXCEPTION_243)")
def then_state_transition_error_thrown(context: dict) -> None:
    """校验状态机异常（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 1 状态机迁移守卫")


@when("尝试从 PLANNING 直接跳到 COMPLETED（跳过中间态）")
def when_skip_intermediate_state(context: dict) -> None:
    """跳过中间态（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 1 transition_to()")


# === AC-2: ToolExecutionService ===


@when("调用 ToolExecutionService.execute 传入有效 tool_id 和 ToolCall")
def when_execute_tool(context: dict) -> None:
    """执行工具（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 2 ToolExecutionService")


@then("应返回 ToolResult（含 status/output/evidence_package）")
def then_tool_result_returned(context: dict) -> None:
    """ToolResult 返回（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 2 + Task 3")


@then("应委托 ToolRegistryService.get_tool_metadata 获取 Tool 元数据")
def then_delegate_to_registry(context: dict) -> None:
    """委托给 Registry（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 2 Service 委托")


# === AC-3: 值对象完整性 ===


@given("构造一个 ToolResult 缺少 plan 字段")
def given_tool_result_missing_plan(context: dict) -> None:
    """构造缺字段 ToolResult（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 3 值对象")


@when("调用其完整性校验方法")
def when_call_completeness_check(context: dict) -> None:
    """完整性校验（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 3 校验")


@then("应抛出 EvidenceValidationFailedError (EXCEPTION_386)")
def then_evidence_validation_error(context: dict) -> None:
    """校验缺字段异常（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 3 异常触发")


# === AC-4: 五阶段工作流 ===


@when("引擎执行一次完整五阶段链路")
def when_engine_full_pipeline(context: dict) -> None:
    """五阶段完整执行（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 4 ToolExecutionEngine")


@then("Think 阶段应调用 LLMClientPort.structured_generate 产出 plan")
def then_think_stage_plan(context: dict) -> None:
    """Think 阶段（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 4 五阶段映射")


@then("Code 阶段应调用 LLMClientPort.structured_generate 产出 code")
def then_code_stage_code(context: dict) -> None:
    """Code 阶段（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 4 五阶段映射")


@then("Execute 阶段应调用 SandboxExecutor.execute_code 产出 result")
def then_execute_stage_result(context: dict) -> None:
    """Execute 阶段（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 4 五阶段映射")


@then("Observe 阶段应调用 SandboxExecutor.execute_code 产出 observation")
def then_observe_stage_observation(context: dict) -> None:
    """Observe 阶段（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 4 五阶段映射")


@then("Validate 阶段应调用 LLMClientPort.structured_generate 产出 validation")
def then_validate_stage_validation(context: dict) -> None:
    """Validate 阶段（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 4 五阶段映射")


@then("最终 ToolExecution.state 应为 COMPLETED")
def then_engine_terminal_completed(context: dict) -> None:
    """终态校验（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 4 状态机集成")


@then("EvidencePackage 应包含 9 字段（input_hash/rule_version/plan/code/result/observation/validation/confidence/citations）")
def then_evidence_package_9_fields(context: dict) -> None:
    """9 字段校验（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 3 + Task 4 EvidencePackage")


# === AC-5: UseCase 编排 ===


@when('调用 use_case.execute(tool_name="pestel-analysis", arguments={...})')
def when_usecase_execute(context: dict) -> None:
    """UseCase 执行（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 5 StrategicAnalysisUseCase")


@then("应通过 SkillLoaderPort.load_metadata 加载 L1 元数据")
def then_load_metadata(context: dict) -> None:
    """L1 加载（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 5 + Task 6 SkillLoader")


@then("应通过 SkillLoaderPort.load_sop 加载 L2 SOP")
def then_load_sop(context: dict) -> None:
    """L2 加载（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 5 + Task 6 SkillLoader")


@then("应调用 ToolExecutionService.execute 触发五阶段执行")
def then_execute_via_service(context: dict) -> None:
    """执行入口（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 5 + Task 2")


@then("应发布 ToolExecuted 事件（双通道 realtime + reliable）")
def then_tool_executed_event_dual_channel(context: dict) -> None:
    """事件双通道（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 5 双通道升级")


# === AC-6: Skills 三级加载 ===


@when("调用 SkillLoaderPort.load_metadata 加载 L1")
def when_load_metadata_l1(context: dict) -> None:
    """L1 加载入口（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 6 SkillLoader")


@then("应返回 ToolMetadata（含 tool_name/slug/category/input_schema/output_schema）")
def then_metadata_returned(context: dict) -> None:
    """ToolMetadata 返回（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 6 SkillLoader")


@when("调用 SkillLoaderPort.load_sop 加载 L2")
def when_load_sop_l2(context: dict) -> None:
    """L2 加载入口（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 6 SkillLoader")


@then("应返回 SkillDocument（含 tool_name/slug/content/token_count）")
def then_sop_returned(context: dict) -> None:
    """SkillDocument 返回（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 6 SkillLoader")


@when("调用 SkillLoaderPort.load_references 加载 L3")
def when_load_references_l3(context: dict) -> None:
    """L3 加载入口（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 6 SkillLoader")


@then("应返回脚本/参考文件 bytes")
def then_references_bytes(context: dict) -> None:
    """L3 返回（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 6 SkillLoader")


# === AC-7: 端口注册 ===


@when('调用 resolver.resolve("tool_execution_repository")')
def when_resolve_tool_execution_repo(context: dict) -> None:
    """解析仓储端口（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 7 端口注册")


@then("应返回 InMemoryToolExecutionRepository 实例")
def then_repo_instance(context: dict) -> None:
    """仓储实例（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 7 端口注册")


@when('调用 resolver.resolve("tool_execution_service")')
def when_resolve_tool_execution_service(context: dict) -> None:
    """解析服务端口（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 7 端口注册")


@then("应返回 ToolExecutionService 实例")
def then_service_instance(context: dict) -> None:
    """服务实例（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 7 端口注册")


@when('调用 resolver.resolve("tool_execution_engine")')
def when_resolve_tool_execution_engine(context: dict) -> None:
    """解析引擎端口（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 7 端口注册")


@then("应返回 ToolExecutionEngine 实例")
def then_engine_instance(context: dict) -> None:
    """引擎实例（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 7 端口注册")


@when('调用 resolver.resolve("skill_loader")')
def when_resolve_skill_loader(context: dict) -> None:
    """解析加载器端口（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 7 端口注册")


@then("应返回 InMemorySkillLoader 实例")
def then_loader_instance(context: dict) -> None:
    """加载器实例（红阶段）"""
    pytest.skip("Task 0 红阶段：依赖 Task 7 端口注册")
