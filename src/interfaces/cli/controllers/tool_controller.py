"""tool 命令控制器

命令编排与端口消费（AC-5 表）：
- ``tool_registry_service``（:2598，同步端口——``get_tool(tool_name=slug)``
  slug→``Tool.tool_id`` UUID 解析链——R1-F4，slug 非 UUID 禁套 canonical 守卫）
- ``skill_loader``（:2875，``load_sop`` async——``SkillDocument.frontmatter.
  input_examples`` 运行时数据通路，R1-F3）
- ``tool_execution_service``（:2741，``execute(tool_id, tool_call, context)``）
- ``run_tool_chain_use_case``（:2945，``execute(chain_name, parameters, context)``）
"""

from __future__ import annotations

import asyncio
import json
import uuid as uuid_module
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.application.skills.skill_manifest import get_tool_id
from src.domain.exceptions import ValidationError
from src.domain.exceptions.tool_exceptions import ToolNotFoundError
from src.domain.value_objects.tool_execution import ExecutionContext, ToolCall
from src.interfaces.cli.formatters import get_formatter

PORT_NAME = "tool_registry_service"
PORT_NAME_SCHEMA_LOADER = "skill_loader"
PORT_NAME_EXECUTION = "tool_execution_service"
PORT_NAME_CHAIN = "run_tool_chain_use_case"

# CLI 面固定租户标识（ExecutionContext.tenant_id 必须 UUID 实例——文档化常量）
CLI_DEFAULT_TENANT_UUID = "00000000-0000-0000-0000-000000000101"


def load_input_json(raw: str) -> dict[str, Any]:
    """--input 内联 JSON 装载（dict 形态守卫）。

    Raises:
        ValidationError: EXCEPTION_201——非法 JSON 或非 object 形态
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            message=f"--input 必须为合法 JSON: {exc.msg}",
            context={"input": raw[:100]},
        ) from exc
    if not isinstance(parsed, dict):
        raise ValidationError(
            message="--input 必须为 JSON 对象（参数键值形态）",
            context={"input": raw[:100], "actual_type": type(parsed).__name__},
        )
    return parsed


def load_chain_config(raw: str) -> dict[str, Any]:
    """chain run --config 装载（内联 JSON 或文件路径）。

    Raises:
        ValidationError: EXCEPTION_201——非法 JSON / 非对象 / 文件不可读
    """
    candidate = Path(raw)
    if candidate.is_file():
        try:
            parsed = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(
                message=f"--config 文件非合法 JSON: {candidate}: {exc.msg}",
                context={"config": raw},
            ) from exc
    else:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                message=f"--config 必须为合法 JSON 或存在的文件路径: {exc.msg}",
                context={"config": raw[:100]},
            ) from exc
    if not isinstance(parsed, dict):
        raise ValidationError(
            message="--config 必须为 JSON 对象（参数键值形态）",
            context={"config": raw[:100], "actual_type": type(parsed).__name__},
        )
    return parsed


def _tool_payload(tool: Any) -> dict[str, Any]:
    """Tool 实体转渲染载荷（getattr 宽松取值——属性集由端口契约冻结）。"""
    return {
        "tool_id": str(tool.tool_id),
        "name": tool.name,
        "slug": tool.slug,
        "description": getattr(tool, "description", ""),
        "category": getattr(tool, "category", ""),
        "version": getattr(tool, "version", ""),
        "status": getattr(tool, "status", ""),
    }


def _build_context(session: str, timeout: int) -> ExecutionContext:
    """构造 ExecutionContext（tenant 固定 UUID+session/timeout 透传——AC-3）。"""
    return ExecutionContext(
        tenant_id=uuid_module.UUID(CLI_DEFAULT_TENANT_UUID),
        session_id=session,
        timeout_sec=float(timeout),
    )


def _resolve_tool(slug: str, registry: Any) -> Any:
    """slug→Tool 解析链（skill_manifest.get_tool_id → registry.get_tool(tool_id=)——R1-F4）。

    ``<tool-id>`` 为 TOOLS.md slug（人类/LLM 可读形态非 UUID）——经
    skill_manifest 静态映射解析 tool_id 后查注册表；slug 未登记即拒。
    """
    tool_id = get_tool_id(slug)
    if tool_id is None:
        raise ToolNotFoundError(tool_name=slug)
    return registry.get_tool(tool_id=tool_id)


def run_list(*, category: str, fmt: str, resolve: Callable[[str], Any]) -> int:
    """真实执行工具清单（幂等装载 register_all → --category 客户端域过滤）。"""
    registry = resolve(PORT_NAME)
    registry.register_all()
    tools = registry.list_all_tools()
    if category:
        tools = [tool for tool in tools if str(getattr(tool, "category", "")) == category]
    print(get_formatter(fmt)([_tool_payload(tool) for tool in tools]))
    return 0


def run_schema(slug: str, *, fmt: str, resolve: Callable[[str], Any]) -> int:
    """真实执行工具 schema 查询（幂等装载 + get_tool + load_sop 双端口——input_examples 通路）。"""
    registry = resolve(PORT_NAME)
    registry.register_all()
    tool = _resolve_tool(slug, registry)
    loader = resolve(PORT_NAME_SCHEMA_LOADER)
    document = asyncio.run(loader.load_sop(slug))
    input_examples = getattr(getattr(document, "frontmatter", None), "input_examples", ())
    payload = {
        "slug": getattr(tool, "slug", slug) or slug,
        "name": tool.name,
        "description": getattr(tool, "description", ""),
        "input_schema": getattr(tool, "input_schema", {}),
        "output_schema": getattr(tool, "output_schema", {}),
        "version": getattr(tool, "version", ""),
        "input_examples": list(input_examples),
    }
    print(get_formatter(fmt)(payload))
    return 0


def run_tool(
    slug: str,
    arguments: dict[str, Any],
    *,
    session: str,
    timeout: int,
    fmt: str,
    resolve: Callable[[str], Any],
) -> int:
    """真实执行工具调用（slug→Tool.tool_id→ToolCall 解析链——R1-F4；幂等装载）。"""
    registry = resolve(PORT_NAME)
    registry.register_all()
    tool = _resolve_tool(slug, registry)
    tool_call = ToolCall(tool_id=tool.tool_id, arguments=arguments)
    context = _build_context(session, timeout)
    service = resolve(PORT_NAME_EXECUTION)
    result = asyncio.run(service.execute(tool.tool_id, tool_call, context))
    payload = {
        "tool_id": str(tool.tool_id),
        "slug": slug,
        "status": getattr(result, "status", None),
        "output": getattr(result, "output", None),
        "execution_ms": getattr(result, "execution_ms", None),
    }
    print(get_formatter(fmt)(payload))
    return 0


def run_chain(
    chain_name: str,
    parameters: dict[str, Any],
    *,
    session: str,
    timeout: int,
    fmt: str,
    resolve: Callable[[str], Any],
) -> int:
    """真实执行工具链（run_tool_chain_use_case.execute(chain_name, parameters, context)）。"""
    context = _build_context(session, timeout)
    use_case = resolve(PORT_NAME_CHAIN)
    result = asyncio.run(use_case.execute(chain_name, parameters, context))
    payload = {
        "chain_name": chain_name,
        "status": getattr(result, "status", None),
        "steps_completed": getattr(result, "steps_completed", None),
    }
    print(get_formatter(fmt)(payload))
    return 0
