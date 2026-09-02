"""验收测试步骤实现：战略工具注册

使用 pytest-bdd 框架，中文 Gherkin 关键词。
遵循项目验收测试模式：context dict + event_loop.run_until_complete()。
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.services.tool_registry_service import ToolRegistryService
from src.domain.entities.tool import ToolCategory
from src.domain.exceptions.tool_exceptions import ToolNotFoundError
from src.domain.ports.registry import _global_registry
from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

# 绑定所有场景
scenarios("test_acceptance_strategic_tool_registration.feature")


@pytest.fixture
def context() -> dict[str, Any]:
    """测试上下文 dict，在 Given/When/Then 之间传递状态。"""
    return {}


# === Given steps ===


@given("系统已启动，工具注册服务已初始化")
def given_service_initialized(context: dict[str, Any]) -> None:
    """初始化工具注册服务。"""
    repo = InMemoryToolRepository()
    service = ToolRegistryService(repository=repo)
    context["repo"] = repo
    context["service"] = service


@given("23 种战略工具已注册")
def given_tools_registered(context: dict[str, Any]) -> None:
    """注册 23 种战略工具。"""
    repo = InMemoryToolRepository()
    service = ToolRegistryService(repository=repo)
    service.register_all()
    context["repo"] = repo
    context["service"] = service


@given("应用启动时执行 composition_root.bootstrap()")
def given_bootstrap_executed() -> None:
    """验证 bootstrap 已执行（由 conftest.py 自动调用）。"""
    # bootstrap 由 conftest.py session fixture 自动调用
    pass


# === When steps ===


@when("执行工具注册引导流程")
def when_register_all(context: dict[str, Any]) -> None:
    """执行工具注册。"""
    service: ToolRegistryService = context["service"]
    service.register_all()


@when("按分类 ENVIRONMENT_ANALYSIS 查询")
def when_query_environment_analysis(context: dict[str, Any]) -> None:
    """按分类查询。"""
    service: ToolRegistryService = context["service"]
    context["query_result"] = service.get_tools_by_category(ToolCategory.ENVIRONMENT_ANALYSIS)


@when("按分类 COMPETITIVE_ANALYSIS 查询")
def when_query_competitive_analysis(context: dict[str, Any]) -> None:
    """按分类查询。"""
    service: ToolRegistryService = context["service"]
    context["query_result"] = service.get_tools_by_category(ToolCategory.COMPETITIVE_ANALYSIS)


@when("按分类 STRATEGIC_SELECTION 查询")
def when_query_strategic_selection(context: dict[str, Any]) -> None:
    """按分类查询。"""
    service: ToolRegistryService = context["service"]
    context["query_result"] = service.get_tools_by_category(ToolCategory.STRATEGIC_SELECTION)


@when("按分类 BUSINESS_MODEL 查询")
def when_query_business_model(context: dict[str, Any]) -> None:
    """按分类查询。"""
    service: ToolRegistryService = context["service"]
    context["query_result"] = service.get_tools_by_category(ToolCategory.BUSINESS_MODEL)


@when("按分类 EXECUTION_MANAGEMENT 查询")
def when_query_execution_management(context: dict[str, Any]) -> None:
    """按分类查询。"""
    service: ToolRegistryService = context["service"]
    context["query_result"] = service.get_tools_by_category(ToolCategory.EXECUTION_MANAGEMENT)


@when("按 tool_id 查询 PESTEL 分析")
def when_query_pestel_by_id(context: dict[str, Any]) -> None:
    """按 tool_id 查询 PESTEL 分析。"""
    service: ToolRegistryService = context["service"]
    pestel = service.get_tool(tool_name="PESTEL 分析")
    context["query_result"] = service.get_tool(tool_id=pestel.tool_id)


@when("按 name 查询 波特五力")
def when_query_porters_by_name(context: dict[str, Any]) -> None:
    """按 name 查询波特五力。"""
    service: ToolRegistryService = context["service"]
    context["query_result"] = service.get_tool(tool_name="波特五力")


@when("按 tool_id 查询不存在的工具")
def when_query_nonexistent_by_id(context: dict[str, Any]) -> None:
    """按 tool_id 查询不存在的工具。"""
    service: ToolRegistryService = context["service"]
    try:
        service.get_tool(tool_id=uuid.uuid4())
        context["query_error"] = None
    except ToolNotFoundError as exc:
        context["query_error"] = exc


@when("按 name 查询不存在的工具")
def when_query_nonexistent_by_name(context: dict[str, Any]) -> None:
    """按 name 查询不存在的工具。"""
    service: ToolRegistryService = context["service"]
    try:
        service.get_tool(tool_name="Non-existent Tool")
        context["query_error"] = None
    except ToolNotFoundError as exc:
        context["query_error"] = exc


# === Then steps ===


@then("23 种战略工具全部注册成功")
def then_all_23_tools_registered(context: dict[str, Any]) -> None:
    """验证 23 种工具全部注册。"""
    service: ToolRegistryService = context["service"]
    assert service.tool_count() == 23


@then("每种工具有唯一 tool_id")
def then_all_tools_have_unique_id(context: dict[str, Any]) -> None:
    """验证每种工具有唯一 tool_id。"""
    service: ToolRegistryService = context["service"]
    tools = service.list_all_tools()
    ids = [t.tool_id for t in tools]
    assert len(ids) == len(set(ids))


@then("每种工具 name 非空且唯一")
def then_all_tools_have_unique_name(context: dict[str, Any]) -> None:
    """验证每种工具 name 非空且唯一。"""
    service: ToolRegistryService = context["service"]
    tools = service.list_all_tools()
    names = [t.name for t in tools]
    assert all(n for n in names), "所有工具名称不能为空"
    assert len(names) == len(set(names))


@then("每种工具 category 属于 ToolCategory 枚举值")
def then_all_tools_have_valid_category(context: dict[str, Any]) -> None:
    """验证每种工具 category 属于 ToolCategory 枚举。"""
    service: ToolRegistryService = context["service"]
    tools = service.list_all_tools()
    for tool in tools:
        assert isinstance(tool.category, ToolCategory)


@then("每种工具 input_schema 和 output_schema 为有效 JSON Schema 字典")
def then_all_tools_have_valid_schemas(context: dict[str, Any]) -> None:
    """验证每种工具 input_schema/output_schema 为有效 JSON Schema 字典。"""
    service: ToolRegistryService = context["service"]
    tools = service.list_all_tools()
    for tool in tools:
        assert isinstance(tool.input_schema, dict)
        assert isinstance(tool.output_schema, dict)
        assert tool.input_schema, f"Tool '{tool.name}' has empty input_schema"
        assert tool.output_schema, f"Tool '{tool.name}' has empty output_schema"


@then("所有工具 status 默认为 ACTIVE")
def then_all_tools_status_active(context: dict[str, Any]) -> None:
    """验证所有工具 status 默认为 ACTIVE。"""
    from src.domain.entities.tool import ToolStatus

    service: ToolRegistryService = context["service"]
    tools = service.list_all_tools()
    for tool in tools:
        assert tool.status == ToolStatus.ACTIVE


@then("所有工具 version 默认为 1.0.0")
def then_all_tools_version_default(context: dict[str, Any]) -> None:
    """验证所有工具 version 默认为 1.0.0。"""
    service: ToolRegistryService = context["service"]
    tools = service.list_all_tools()
    for tool in tools:
        assert tool.version == "1.0.0"


@then("返回 3 种工具")
def then_returns_3_tools(context: dict[str, Any]) -> None:
    """验证返回 3 种工具。"""
    result = context["query_result"]
    assert len(result) == 3


@then("返回 6 种工具")
def then_returns_6_tools(context: dict[str, Any]) -> None:
    """验证返回 6 种工具。"""
    result = context["query_result"]
    assert len(result) == 6


@then("返回 8 种工具")
def then_returns_8_tools(context: dict[str, Any]) -> None:
    """验证返回 8 种工具。"""
    result = context["query_result"]
    assert len(result) == 8


@then("返回完整工具元数据")
def then_returns_full_metadata(context: dict[str, Any]) -> None:
    """验证返回完整工具元数据。"""
    tool = context["query_result"]
    assert tool.tool_id is not None
    assert tool.name
    assert tool.category
    assert tool.input_schema
    assert tool.output_schema


@then("工具名称为 PESTEL 分析")
def then_tool_name_pestel(context: dict[str, Any]) -> None:
    """验证工具名称为 PESTEL 分析。"""
    tool = context["query_result"]
    assert tool.name == "PESTEL 分析"


@then("工具分类为 ENVIRONMENT_ANALYSIS")
def then_tool_category_environment(context: dict[str, Any]) -> None:
    """验证工具分类为 ENVIRONMENT_ANALYSIS。"""
    tool = context["query_result"]
    assert tool.category == ToolCategory.ENVIRONMENT_ANALYSIS


@then("工具名称为 波特五力")
def then_tool_name_porters(context: dict[str, Any]) -> None:
    """验证工具名称为波特五力。"""
    tool = context["query_result"]
    assert tool.name == "波特五力"


@then("抛出 ToolNotFoundError")
def then_tool_not_found_error(context: dict[str, Any]) -> None:
    """验证抛出 ToolNotFoundError。"""
    error = context.get("query_error")
    assert isinstance(error, ToolNotFoundError)


@then("tool_repository 端口已注册")
def then_tool_repository_registered() -> None:
    """验证 tool_repository 端口已注册。"""
    spec = _global_registry.get("tool_repository")
    assert spec is not None


@then("tool_registry_service 端口已注册")
def then_tool_registry_service_registered() -> None:
    """验证 tool_registry_service 端口已注册。"""
    spec = _global_registry.get("tool_registry_service")
    assert spec is not None


@then('PortRegistry.get("tool_repository") 返回非空 PortSpec')
def then_tool_repository_port_spec_not_empty() -> None:
    """验证 PortRegistry.get("tool_repository") 返回非空。"""
    spec = _global_registry.get("tool_repository")
    assert spec is not None
    assert spec.name == "tool_repository"
    assert spec.version == "v1.0.0"


@then('PortRegistry.get("tool_registry_service") 返回非空 PortSpec')
def then_tool_registry_service_port_spec_not_empty() -> None:
    """验证 PortRegistry.get("tool_registry_service") 返回非空。"""
    spec = _global_registry.get("tool_registry_service")
    assert spec is not None
    assert spec.name == "tool_registry_service"
    assert spec.version == "v1.0.0"
