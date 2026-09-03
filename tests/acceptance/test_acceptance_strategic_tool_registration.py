"""Story 4.1 战略工具注册 — 验收测试（BDD 步骤实现）

本文件遵循项目验收测试规范（参考 tests/acceptance/test_acceptance_event_bus_implementation.py）：

- 步骤函数使用 @given / @when / @then 装饰器 + context: dict[str, Any] fixture
- 使用真实服务实例：InMemoryToolRepository + ToolRegistryService
- 步骤**严格按 AC 顺序**（故事文件主 AC：AC-1/AC-2/AC-3/AC-4），`# ====` 分隔
- 端口注册元数据查询验证
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.services.tool_registry_service import ToolRegistryService
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.exceptions import EntityValidationError
from src.domain.exceptions.tool_exceptions import ToolAlreadyExistsError, ToolNotFoundError
from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

scenarios("test_acceptance_strategic_tool_registration.feature")


# ===================================================================
# 共享 fixtures
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """BDD 步骤间共享状态容器。"""
    return {}


@pytest.fixture
def tool_repository() -> InMemoryToolRepository:
    """真实 InMemory 工具仓储（自包含生命周期，无外部依赖）。"""
    return InMemoryToolRepository()


@pytest.fixture
def tool_registry(tool_repository: InMemoryToolRepository) -> ToolRegistryService:
    """真实 ToolRegistryService（依赖 InMemoryToolRepository）。"""
    return ToolRegistryService(repository=tool_repository)


# 延迟导入全局注册中心（避免模块级循环依赖）
_global_registry = __import__(
    "src.domain.ports.registry",
    fromlist=["_global_registry"],
)._global_registry


# ===================================================================
# Background steps（每个场景前运行）
# ===================================================================


@given("战略工具注册服务已初始化")
def given_service_initialized(
    context: dict[str, Any],
    tool_repository: InMemoryToolRepository,
    tool_registry: ToolRegistryService,
) -> None:
    """工具注册服务已初始化（InMemoryToolRepository + ToolRegistryService）。

    将服务实例绑定到 context，便于后续 When/Then 步骤共享。
    """
    context["repo"] = tool_repository
    context["service"] = tool_registry


@given("已注册 23 种战略工具")
def given_tools_registered(context: dict[str, Any]) -> None:
    """从 TOOL_CATALOG 加载 23 种战略工具并持久化到 InMemoryToolRepository。"""
    context["service"].register_all()


# ===================================================================
# AC-1: 23 种战略工具全部注册
# =================================================================


@when("执行工具注册引导流程")
def when_register_all(context: dict[str, Any]) -> None:
    """执行工具注册引导流程。"""
    context["service"].register_all()


@then("23 种战略工具全部注册成功")
def then_all_23_tools_registered(context: dict[str, Any]) -> None:
    """验证 23 种工具全部注册。"""
    assert context["service"].tool_count() == 23


@then("每种工具有唯一 tool_id")
def then_all_tools_have_unique_id(context: dict[str, Any]) -> None:
    """验证 tool_id 唯一。"""
    tools = context["service"].list_all_tools()
    ids = [t.tool_id for t in tools]
    assert len(ids) == len(set(ids))


@then("每种工具 name 非空且唯一")
def then_all_tools_have_unique_name(context: dict[str, Any]) -> None:
    """验证 name 非空且唯一。"""
    tools = context["service"].list_all_tools()
    names = [t.name for t in tools]
    assert all(n for n in names)
    assert len(names) == len(set(names))


@then("每种工具 category 属于 ToolCategory 枚举值")
def then_all_tools_have_valid_category(context: dict[str, Any]) -> None:
    """验证 category 属于 ToolCategory 枚举。"""
    tools = context["service"].list_all_tools()
    for tool in tools:
        assert isinstance(tool.category, ToolCategory)


@then("每种工具 input_schema 和 output_schema 为有效 JSON Schema 字典")
def then_all_tools_have_valid_schemas(context: dict[str, Any]) -> None:
    """验证 input_schema/output_schema 有效。"""
    tools = context["service"].list_all_tools()
    for tool in tools:
        assert isinstance(tool.input_schema, dict)
        assert isinstance(tool.output_schema, dict)
        assert tool.input_schema
        assert tool.output_schema


@then("所有工具 status 默认为 ACTIVE")
def then_all_tools_status_active(context: dict[str, Any]) -> None:
    """验证 status 默认 ACTIVE。"""
    tools = context["service"].list_all_tools()
    for tool in tools:
        assert tool.status == ToolStatus.ACTIVE


@then("所有工具 version 默认为 1.0.0")
def then_all_tools_version_default(context: dict[str, Any]) -> None:
    """验证 version 默认 1.0.0。"""
    tools = context["service"].list_all_tools()
    for tool in tools:
        assert tool.version == "1.0.0"


@when("再次执行工具注册引导流程")
def when_register_all_again(context: dict[str, Any]) -> None:
    """二次调用 register_all（验证幂等性，不抛异常）。"""
    context["service"].register_all()


@then("工具总数仍为 23")
def then_tool_count_still_23(context: dict[str, Any]) -> None:
    """验证幂等性：总数仍为 23。"""
    assert context["service"].tool_count() == 23


@when("对所有工具执行 JSON Schema Draft-07 结构校验")
def when_validate_all_schemas_draft7(context: dict[str, Any]) -> None:
    """对 23 种工具的 46 个 schema（input + output）执行 Draft-07 结构校验。"""
    from jsonschema import Draft7Validator

    tools = context["service"].list_all_tools()
    validation_errors: list[tuple[str, str, str]] = []
    for tool in tools:
        try:
            Draft7Validator.check_schema(tool.input_schema)
        except Exception as exc:
            validation_errors.append((tool.name, "input_schema", str(exc)))
        try:
            Draft7Validator.check_schema(tool.output_schema)
        except Exception as exc:
            validation_errors.append((tool.name, "output_schema", str(exc)))
    context["validation_errors"] = validation_errors


@then("所有 23 个工具的 input_schema 校验通过")
def then_all_input_schemas_valid(context: dict[str, Any]) -> None:
    """验证所有 23 种工具的 input_schema 通过 Draft-07 校验。"""
    errors = [e for e in context["validation_errors"] if e[1] == "input_schema"]
    assert errors == [], f"input_schema 校验失败: {errors}"


@then("所有 23 个工具的 output_schema 校验通过")
def then_all_output_schemas_valid(context: dict[str, Any]) -> None:
    """验证所有 23 种工具的 output_schema 通过 Draft-07 校验。"""
    errors = [e for e in context["validation_errors"] if e[1] == "output_schema"]
    assert errors == [], f"output_schema 校验失败: {errors}"


@given("工具仓储为空（独立 AC-1 重复注册场景）")
def given_empty_repository_for_ac1_duplicate(
    context: dict[str, Any],
) -> None:
    """AC-1 重复注册场景：独立空仓储（不使用 Background 预注册的 23 工具）。

    清空 context 重新构建仓储，避免与 Background 预注册的 23 工具冲突。
    """
    repo = InMemoryToolRepository()
    service = ToolRegistryService(repository=repo)
    context.clear()
    context["repo"] = repo
    context["service"] = service


@when('直接通过仓储保存名为 "PESTEL 分析" 的工具')
def when_save_pestel_directly(context: dict[str, Any]) -> None:
    """首次直接保存 PESTEL 分析（绕过 service.register_all 静默吞异常路径）。"""
    tool = _build_tool_for_catalog("PESTEL 分析")
    context["repo"].save(tool)


@when('直接通过仓储保存另一名为 "PESTEL 分析" 的工具')
def when_save_duplicate_pestel(context: dict[str, Any]) -> None:
    """同名不同 ID 触发 ToolAlreadyExistsError。"""
    duplicate = Tool(
        tool_id=uuid.uuid4(),
        name="PESTEL 分析",
        category=ToolCategory.ENVIRONMENT_ANALYSIS,
    )
    context["query_error"] = None
    try:
        context["repo"].save(duplicate)
    except ToolAlreadyExistsError as exc:
        context["query_error"] = exc


@then("抛出 ToolAlreadyExistsError")
def then_tool_already_exists_error(context: dict[str, Any]) -> None:
    """验证抛出 ToolAlreadyExistsError。"""
    assert isinstance(context.get("query_error"), ToolAlreadyExistsError)


@then("错误码为 EXCEPTION_381")
def then_error_code_381(context: dict[str, Any]) -> None:
    """验证错误码为 EXCEPTION_381（ToolAlreadyExistsError）。"""
    err = context.get("query_error")
    assert err is not None
    assert err.code == "EXCEPTION_381"


@when("直接通过仓储保存指定 tool_id 的工具")
def when_save_with_specific_id(context: dict[str, Any]) -> None:
    """首次保存指定 tool_id。"""
    specific_id = uuid.UUID("00000000-0000-0000-0000-000000000099")
    tool = Tool(
        tool_id=specific_id,
        name="测试工具 A",
        category=ToolCategory.ANALYSIS,
    )
    context["_duplicate_id"] = specific_id
    context["repo"].save(tool)


@when("直接通过仓储保存相同 tool_id 的另一工具")
def when_save_with_same_id(context: dict[str, Any]) -> None:
    """同 ID 不同名称触发 ToolAlreadyExistsError。"""
    duplicate = Tool(
        tool_id=context["_duplicate_id"],
        name="另一工具",
        category=ToolCategory.ANALYSIS,
    )
    context["query_error"] = None
    try:
        context["repo"].save(duplicate)
    except ToolAlreadyExistsError as exc:
        context["query_error"] = exc


def _build_tool_for_catalog(name: str) -> Tool:
    """从 TOOL_CATALOG 按 name 查找并复制 Tool 实体。"""
    from src.domain.entities.strategic_tool_catalog import TOOL_CATALOG

    for tool in TOOL_CATALOG:
        if tool.name == name:
            return Tool(
                tool_id=tool.tool_id,
                name=tool.name,
                description=tool.description,
                category=tool.category,
                input_schema=dict(tool.input_schema),
                output_schema=dict(tool.output_schema),
                status=tool.status,
                version=tool.version,
                created_at=tool.created_at,
                updated_at=tool.updated_at,
            )
    raise ValueError(f"Tool {name!r} not found in catalog")


# ===================================================================
# AC-2: 按分类查询工具
# =================================================================


@when("按分类 ENVIRONMENT_ANALYSIS 查询")
def when_query_environment_analysis(context: dict[str, Any]) -> None:
    """按分类查询。"""
    context["query_result"] = context["service"].get_tools_by_category(ToolCategory.ENVIRONMENT_ANALYSIS)


@when("按分类 COMPETITIVE_ANALYSIS 查询")
def when_query_competitive_analysis(context: dict[str, Any]) -> None:
    """按分类查询。"""
    context["query_result"] = context["service"].get_tools_by_category(ToolCategory.COMPETITIVE_ANALYSIS)


@when("按分类 STRATEGIC_SELECTION 查询")
def when_query_strategic_selection(context: dict[str, Any]) -> None:
    """按分类查询。"""
    context["query_result"] = context["service"].get_tools_by_category(ToolCategory.STRATEGIC_SELECTION)


@when("按分类 BUSINESS_MODEL 查询")
def when_query_business_model(context: dict[str, Any]) -> None:
    """按分类查询。"""
    context["query_result"] = context["service"].get_tools_by_category(ToolCategory.BUSINESS_MODEL)


@when("按分类 EXECUTION_MANAGEMENT 查询")
def when_query_execution_management(context: dict[str, Any]) -> None:
    """按分类查询。"""
    context["query_result"] = context["service"].get_tools_by_category(ToolCategory.EXECUTION_MANAGEMENT)


@then("返回 3 种工具")
def then_returns_3_tools(context: dict[str, Any]) -> None:
    """验证返回 3 种工具。"""
    assert len(context["query_result"]) == 3


@then("返回 6 种工具")
def then_returns_6_tools(context: dict[str, Any]) -> None:
    """验证返回 6 种工具。"""
    assert len(context["query_result"]) == 6


@then("返回 8 种工具")
def then_returns_8_tools(context: dict[str, Any]) -> None:
    """验证返回 8 种工具。"""
    assert len(context["query_result"]) == 8


@when("按分类 ANALYSIS 查询")
def when_query_analysis_empty(context: dict[str, Any]) -> None:
    """按功能分类 ANALYSIS 查询（23 种战略工具均不在此分类，应返回空列表）。"""
    context["query_result"] = context["service"].get_tools_by_category(
        ToolCategory.ANALYSIS,
    )


@then("返回空列表")
def then_returns_empty_list_for_analysis(context: dict[str, Any]) -> None:
    """验证按分类查询返回空列表。"""
    assert context["query_result"] == []


# ===================================================================
# AC-3: 按 ID/名称查询工具
# =================================================================


@when("按 tool_id 查询 PESTEL 分析")
def when_query_pestel_by_id(context: dict[str, Any]) -> None:
    """按 tool_id 查询 PESTEL 分析。"""
    pestel = context["service"].get_tool(tool_name="PESTEL 分析")
    context["query_result"] = context["service"].get_tool(tool_id=pestel.tool_id)


@when("按 name 查询 波特五力")
def when_query_porters_by_name(context: dict[str, Any]) -> None:
    """按 name 查询波特五力。"""
    context["query_result"] = context["service"].get_tool(tool_name="波特五力")


@when("按 tool_id 查询不存在的工具")
def when_query_nonexistent_by_id(context: dict[str, Any]) -> None:
    """按 tool_id 查询不存在的工具。"""
    context["query_error"] = None
    try:
        context["service"].get_tool(tool_id=uuid.uuid4())
    except ToolNotFoundError as exc:
        context["query_error"] = exc


@when("按 name 查询不存在的工具")
def when_query_nonexistent_by_name(context: dict[str, Any]) -> None:
    """按 name 查询不存在的工具。"""
    context["query_error"] = None
    try:
        context["service"].get_tool(tool_name="Non-existent Tool")
    except ToolNotFoundError as exc:
        context["query_error"] = exc


@then("返回完整工具元数据")
def then_returns_full_metadata(context: dict[str, Any]) -> None:
    """验证返回完整元数据。"""
    tool = context["query_result"]
    assert tool.tool_id is not None
    assert tool.name
    assert tool.category
    assert tool.input_schema
    assert tool.output_schema


@then("工具名称为 PESTEL 分析")
def then_tool_name_pestel(context: dict[str, Any]) -> None:
    """验证名称为 PESTEL 分析。"""
    assert context["query_result"].name == "PESTEL 分析"


@then("工具分类为 ENVIRONMENT_ANALYSIS")
def then_tool_category_environment(context: dict[str, Any]) -> None:
    """验证分类为 ENVIRONMENT_ANALYSIS。"""
    assert context["query_result"].category == ToolCategory.ENVIRONMENT_ANALYSIS


@then("工具名称为 波特五力")
def then_tool_name_porters(context: dict[str, Any]) -> None:
    """验证名称为 波特五力。"""
    assert context["query_result"].name == "波特五力"


@then("抛出 ToolNotFoundError")
def then_tool_not_found_error(context: dict[str, Any]) -> None:
    """验证抛出 ToolNotFoundError。"""
    assert isinstance(context.get("query_error"), ToolNotFoundError)


@when("不传任何参数查询工具")
def when_query_without_params(context: dict[str, Any]) -> None:
    """不传任何参数查询工具（参数验证失败路径）。"""
    context["query_error"] = None
    try:
        context["service"].get_tool()
    except EntityValidationError as exc:
        context["query_error"] = exc


@then("抛出 EntityValidationError")
def then_entity_validation_error(context: dict[str, Any]) -> None:
    """验证抛出 EntityValidationError。"""
    assert isinstance(context.get("query_error"), EntityValidationError)


@then("错误码为 EXCEPTION_242")
def then_error_code_242(context: dict[str, Any]) -> None:
    """验证错误码为 EXCEPTION_242。"""
    err = context.get("query_error")
    assert err is not None
    assert err.code == "EXCEPTION_242"


# ===================================================================
# AC-4: 端口注册与依赖注入
# =================================================================


@then("tool_repository 端口已注册")
def then_tool_repository_registered() -> None:
    """验证端口已注册。"""
    spec = _global_registry.get("tool_repository")
    assert spec is not None


@then("tool_registry_service 端口已注册")
def then_tool_registry_service_registered() -> None:
    """验证端口已注册。"""
    spec = _global_registry.get("tool_registry_service")
    assert spec is not None


@then('PortRegistry.get("tool_repository") 返回非空 PortSpec')
def then_tool_repository_port_spec_not_empty() -> None:
    """验证 PortRegistry 返回非空。"""
    spec = _global_registry.get("tool_repository")
    assert spec is not None
    assert spec.name == "tool_repository"
    assert spec.version == "v1.0.0"


@then('PortRegistry.get("tool_registry_service") 返回非空 PortSpec')
def then_tool_registry_service_port_spec_not_empty() -> None:
    """验证 PortRegistry 返回非空。"""
    spec = _global_registry.get("tool_registry_service")
    assert spec is not None
    assert spec.name == "tool_registry_service"
    assert spec.version == "v1.0.0"
