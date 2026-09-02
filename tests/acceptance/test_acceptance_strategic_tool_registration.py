"""战略工具注册验收测试（BDD 步骤实现）

遵循项目验收测试规范：
- 步骤函数使用 event_loop.run_until_complete() 运行 async 测试
- 不使用 @pytest.mark.asyncio（会导致 context 数据丢失）
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.services.tool_registry_service import ToolRegistryService
from src.domain.entities.tool import ToolCategory
from src.domain.exceptions import EntityValidationError
from src.domain.exceptions.tool_exceptions import ToolNotFoundError
from src.domain.ports.registry import _global_registry
from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

scenarios("test_acceptance_strategic_tool_registration.feature")

# ===================================================================
# 共享上下文
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """BDD 步骤间共享状态"""
    return {}


# ===================================================================
# Helper: 构建真实服务
# ===================================================================


def _build_service() -> dict[str, Any]:
    """构建真实 ToolRegistryService 实例"""
    repo = InMemoryToolRepository()
    service = ToolRegistryService(repository=repo)
    return {"repo": repo, "service": service}


# ===================================================================
# Background
# ===================================================================


@given("工具注册服务已初始化", target_fixture="context")
def given_service_initialized(context: dict[str, Any]) -> dict[str, Any]:
    """工具注册服务已初始化"""
    ctx = _build_service()
    context.update(ctx)
    return context


@given("已注册 23 种战略工具", target_fixture="context")
def given_tools_registered(context: dict[str, Any]) -> dict[str, Any]:
    """注册 23 种战略工具"""
    context["service"].register_all()
    return context


# ===================================================================
# AC-1 步骤：23 种战略工具全部注册
# ===================================================================


@when("执行工具注册引导流程")
def when_register_all(context: dict[str, Any]) -> None:
    """执行工具注册"""
    context["service"].register_all()


@then("23 种战略工具全部注册成功")
def then_all_23_tools_registered(context: dict[str, Any]) -> None:
    """验证 23 种工具全部注册"""
    assert context["service"].tool_count() == 23


@then("每种工具有唯一 tool_id")
def then_all_tools_have_unique_id(context: dict[str, Any]) -> None:
    """验证 tool_id 唯一"""
    tools = context["service"].list_all_tools()
    ids = [t.tool_id for t in tools]
    assert len(ids) == len(set(ids))


@then("每种工具 name 非空且唯一")
def then_all_tools_have_unique_name(context: dict[str, Any]) -> None:
    """验证 name 非空且唯一"""
    tools = context["service"].list_all_tools()
    names = [t.name for t in tools]
    assert all(n for n in names)
    assert len(names) == len(set(names))


@then("每种工具 category 属于 ToolCategory 枚举值")
def then_all_tools_have_valid_category(context: dict[str, Any]) -> None:
    """验证 category 属于 ToolCategory 枚举"""
    tools = context["service"].list_all_tools()
    for tool in tools:
        assert isinstance(tool.category, ToolCategory)


@then("每种工具 input_schema 和 output_schema 为有效 JSON Schema 字典")
def then_all_tools_have_valid_schemas(context: dict[str, Any]) -> None:
    """验证 input_schema/output_schema 有效"""
    tools = context["service"].list_all_tools()
    for tool in tools:
        assert isinstance(tool.input_schema, dict)
        assert isinstance(tool.output_schema, dict)
        assert tool.input_schema
        assert tool.output_schema


@then("所有工具 status 默认为 ACTIVE")
def then_all_tools_status_active(context: dict[str, Any]) -> None:
    """验证 status 默认 ACTIVE"""
    from src.domain.entities.tool import ToolStatus

    tools = context["service"].list_all_tools()
    for tool in tools:
        assert tool.status == ToolStatus.ACTIVE


@then("所有工具 version 默认为 1.0.0")
def then_all_tools_version_default(context: dict[str, Any]) -> None:
    """验证 version 默认 1.0.0"""
    tools = context["service"].list_all_tools()
    for tool in tools:
        assert tool.version == "1.0.0"


# ===================================================================
# AC-2 步骤：按分类查询工具
# ===================================================================


@when("按分类 ENVIRONMENT_ANALYSIS 查询")
def when_query_environment_analysis(context: dict[str, Any]) -> None:
    """按分类查询"""
    context["query_result"] = context["service"].get_tools_by_category(ToolCategory.ENVIRONMENT_ANALYSIS)


@when("按分类 COMPETITIVE_ANALYSIS 查询")
def when_query_competitive_analysis(context: dict[str, Any]) -> None:
    """按分类查询"""
    context["query_result"] = context["service"].get_tools_by_category(ToolCategory.COMPETITIVE_ANALYSIS)


@when("按分类 STRATEGIC_SELECTION 查询")
def when_query_strategic_selection(context: dict[str, Any]) -> None:
    """按分类查询"""
    context["query_result"] = context["service"].get_tools_by_category(ToolCategory.STRATEGIC_SELECTION)


@when("按分类 BUSINESS_MODEL 查询")
def when_query_business_model(context: dict[str, Any]) -> None:
    """按分类查询"""
    context["query_result"] = context["service"].get_tools_by_category(ToolCategory.BUSINESS_MODEL)


@when("按分类 EXECUTION_MANAGEMENT 查询")
def when_query_execution_management(context: dict[str, Any]) -> None:
    """按分类查询"""
    context["query_result"] = context["service"].get_tools_by_category(ToolCategory.EXECUTION_MANAGEMENT)


@then("返回 3 种工具")
def then_returns_3_tools(context: dict[str, Any]) -> None:
    """验证返回 3 种工具"""
    assert len(context["query_result"]) == 3


@then("返回 6 种工具")
def then_returns_6_tools(context: dict[str, Any]) -> None:
    """验证返回 6 种工具"""
    assert len(context["query_result"]) == 6


@then("返回 8 种工具")
def then_returns_8_tools(context: dict[str, Any]) -> None:
    """验证返回 8 种工具"""
    assert len(context["query_result"]) == 8


# ===================================================================
# AC-3 步骤：按 ID/名称查询工具
# ===================================================================


@when("按 tool_id 查询 PESTEL 分析")
def when_query_pestel_by_id(context: dict[str, Any]) -> None:
    """按 tool_id 查询 PESTEL 分析"""
    pestel = context["service"].get_tool(tool_name="PESTEL 分析")
    context["query_result"] = context["service"].get_tool(tool_id=pestel.tool_id)


@when("按 name 查询 波特五力")
def when_query_porters_by_name(context: dict[str, Any]) -> None:
    """按 name 查询波特五力"""
    context["query_result"] = context["service"].get_tool(tool_name="波特五力")


@when("按 tool_id 查询不存在的工具")
def when_query_nonexistent_by_id(context: dict[str, Any]) -> None:
    """按 tool_id 查询不存在的工具"""
    try:
        context["service"].get_tool(tool_id=uuid.uuid4())
        context["query_error"] = None
    except ToolNotFoundError as exc:
        context["query_error"] = exc


@when("按 name 查询不存在的工具")
def when_query_nonexistent_by_name(context: dict[str, Any]) -> None:
    """按 name 查询不存在的工具"""
    try:
        context["service"].get_tool(tool_name="Non-existent Tool")
        context["query_error"] = None
    except ToolNotFoundError as exc:
        context["query_error"] = exc


@then("返回完整工具元数据")
def then_returns_full_metadata(context: dict[str, Any]) -> None:
    """验证返回完整元数据"""
    tool = context["query_result"]
    assert tool.tool_id is not None
    assert tool.name
    assert tool.category
    assert tool.input_schema
    assert tool.output_schema


@then("工具名称为 PESTEL 分析")
def then_tool_name_pestel(context: dict[str, Any]) -> None:
    """验证名称为 PESTEL 分析"""
    assert context["query_result"].name == "PESTEL 分析"


@then("工具分类为 ENVIRONMENT_ANALYSIS")
def then_tool_category_environment(context: dict[str, Any]) -> None:
    """验证分类为 ENVIRONMENT_ANALYSIS"""
    assert context["query_result"].category == ToolCategory.ENVIRONMENT_ANALYSIS


@then("工具名称为 波特五力")
def then_tool_name_porters(context: dict[str, Any]) -> None:
    """验证名称为波特五力"""
    assert context["query_result"].name == "波特五力"


@then("抛出 ToolNotFoundError")
def then_tool_not_found_error(context: dict[str, Any]) -> None:
    """验证抛出 ToolNotFoundError"""
    assert isinstance(context.get("query_error"), ToolNotFoundError)


@when("不传任何参数查询工具")
def when_query_without_params(context: dict[str, Any]) -> None:
    """不传任何参数查询工具（参数验证失败路径）"""
    try:
        context["service"].get_tool()
        context["query_error"] = None
    except EntityValidationError as exc:
        context["query_error"] = exc


@then("抛出 EntityValidationError")
def then_entity_validation_error(context: dict[str, Any]) -> None:
    """验证抛出 EntityValidationError"""
    assert isinstance(context.get("query_error"), EntityValidationError)


@then("错误码为 EXCEPTION_242")
def then_error_code_242(context: dict[str, Any]) -> None:
    """验证错误码为 EXCEPTION_242"""
    err = context.get("query_error")
    assert err is not None
    assert err.code == "EXCEPTION_242"


# ===================================================================
# AC-4 步骤：端口注册与依赖注入
# ===================================================================


@then("tool_repository 端口已注册")
def then_tool_repository_registered() -> None:
    """验证端口已注册"""
    spec = _global_registry.get("tool_repository")
    assert spec is not None


@then("tool_registry_service 端口已注册")
def then_tool_registry_service_registered() -> None:
    """验证端口已注册"""
    spec = _global_registry.get("tool_registry_service")
    assert spec is not None


@then('PortRegistry.get("tool_repository") 返回非空 PortSpec')
def then_tool_repository_port_spec_not_empty() -> None:
    """验证 PortRegistry 返回非空"""
    spec = _global_registry.get("tool_repository")
    assert spec is not None
    assert spec.name == "tool_repository"
    assert spec.version == "v1.0.0"


@then('PortRegistry.get("tool_registry_service") 返回非空 PortSpec')
def then_tool_registry_service_port_spec_not_empty() -> None:
    """验证 PortRegistry 返回非空"""
    spec = _global_registry.get("tool_registry_service")
    assert spec is not None
    assert spec.name == "tool_registry_service"
    assert spec.version == "v1.0.0"
