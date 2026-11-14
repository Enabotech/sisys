"""工具 CLI 命令（Story 7-1——tool list / tool run）。

消费端口（Task 0.1 冻结表——能力级对账定谳）：
    - list → ``tool_execution_service.list_tools_metadata(ToolListQuery)``
      （**同步方法**——tool_version_service 无列工具能力[全方法按单 tool_id
      收窄]，DC-4 对账定谳）；tenant_id 可选 UUID（缺省全租户视图）
    - run → ``tool_execution_service.execute(tool_id, ToolCall, ExecutionContext)``
      （5-3 激活链在位端口——不经休眠的 StrategicAnalysisUseCase）

分层：interfaces 层禁 import entrypoints/composition_root（OD-16）——
bootstrap/关池经 dispatch 注入钩子；resolve 经 domain 层 get_resolver。
"""

from __future__ import annotations

import asyncio
import json
import uuid as uuid_module
from typing import Any

import typer

from src.domain.exceptions import EntityValidationError
from src.domain.ports.resolver import get_resolver
from src.domain.value_objects.tool_execution import ExecutionContext, ToolCall
from src.interfaces.cli.commands.document_commands import _resolve_tenant_id
from src.interfaces.cli.dispatch import CommandSpec, invoke_command, run_cleanup_async
from src.interfaces.cli.formatters import DryRunOption, FormatOption, MockOption, OutputFormat, YesOption, enum_value

app = typer.Typer(help="工具元数据查询与执行（list / run）")


def _validate_uuid(value: str, *, field: str) -> uuid_module.UUID:
    """UUID 守卫转换（ToolListQuery/ExecutionContext 契约——UUID 类型前置）。

    Args:
        value: 原始字符串
        field: 字段名（异常 context 携带）

    Returns:
        uuid.UUID 实例

    Raises:
        EntityValidationError: 242——非 UUID 形态
    """
    try:
        return uuid_module.UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise EntityValidationError(
            message=f"{field} 必须为合法 UUID 字符串: {value!r}",
            context={"command": "tool", "field": field, field: value},
        ) from None


def _parse_input_json(input_json: str) -> dict[str, Any]:
    """--input JSON 串解析守卫（ToolCall.arguments dict 契约）。

    Args:
        input_json: --input 原始字符串

    Returns:
        参数 dict

    Raises:
        EntityValidationError: 242——非 JSON/非 dict 形态
    """
    try:
        parsed = json.loads(input_json)
    except json.JSONDecodeError:
        raise EntityValidationError(
            message="--input 必须为合法 JSON 字符串",
            context={"command": "tool run", "field": "input", "input": input_json},
        ) from None
    if not isinstance(parsed, dict):
        raise EntityValidationError(
            message="--input 必须为 JSON 对象（键值对形态——ToolCall.arguments 契约）",
            context={"command": "tool run", "field": "input", "input": input_json},
        )
    return parsed


# ===================================================================
# tool list 命令
# ===================================================================


def _list_controller(
    tenant_id: str | None,
    category: str | None,
    status: str | None,
    offset: int,
    limit: int,
    dry_run: bool = False,
) -> Any:
    """tool list controller（守卫→dry_run 分叉→resolve→同步执行）。

    Args:
        tenant_id: --tenant-id（可选——UUID 转换过滤；缺省全租户视图）
        category: --category 分类过滤
        status: --status 状态过滤
        offset: --offset 分页偏移
        limit: --limit 分页大小
        dry_run: --dry-run 旗标（读命令退化态）

    Returns:
        动作清单（dry_run）或 Tool 实体列表

    Raises:
        EntityValidationError: 242——非法租户 UUID
    """
    tenant_uuid = _validate_uuid(tenant_id, field="tenant_id") if tenant_id else None
    if dry_run:
        # 可选参数缺席渲染「（全部）」而非 None 字样（R2-β 观感修复）
        category_text = category if category else "（全部）"
        tenant_text = str(tenant_uuid) if tenant_uuid else "（全部租户）"
        return [f"将查询工具元数据清单（category={category_text} tenant={tenant_text} offset={offset} limit={limit}）"]
    from src.application.ports.tool_execution_service import ToolListQuery

    service = get_resolver().resolve("tool_execution_service")
    return service.list_tools_metadata(
        ToolListQuery(tenant_id=tenant_uuid, category=category, status=status, offset=offset, limit=limit)
    )


@app.command("list")
def tool_list(
    tenant_id: str | None = typer.Option(None, "--tenant-id", help="租户标识过滤（可选——缺省全租户视图）"),
    category: str | None = typer.Option(None, "--category", help="按分类过滤"),
    status: str | None = typer.Option(None, "--status", help="按状态过滤"),
    offset: int = typer.Option(0, "--offset", help="分页偏移"),
    limit: int = typer.Option(100, "--limit", help="分页大小"),
    dry_run: DryRunOption = False,
    mock: MockOption = False,
    yes: YesOption = False,
    fmt: FormatOption = OutputFormat.PRETTY,
) -> None:
    """查询工具元数据清单（同步端口——Query Object 模式）。"""

    def _view(result: Any) -> dict[str, Any]:
        items = result or []
        return {
            "total": len(items),
            "tools": [
                {
                    "tool_id": str(getattr(item, "tool_id", getattr(item, "id", ""))),
                    "name": str(getattr(item, "name", "")),
                    "category": enum_value(getattr(item, "category", "")),
                    "status": enum_value(getattr(item, "status", "")),
                }
                for item in items
            ],
        }

    def _pretty_shell() -> int:
        items = _list_controller(tenant_id, category, status, offset, limit)
        if not items:
            print("无工具元数据（空清单）")
            return 0
        print(f"工具清单（{len(items)} 项）:")
        for item in items:
            item_category = enum_value(getattr(item, "category", ""))
            item_status = enum_value(getattr(item, "status", ""))
            print(f"  {getattr(item, 'name', '')} [{item_category}] {item_status}")
        return 0

    invoke_command(
        CommandSpec(
            command="sisys tool list",
            controller=lambda dr: _list_controller(tenant_id, category, status, offset, limit, dry_run=dr),
            pretty_shell=_pretty_shell,
            mock_echo=lambda: {"category": category, "limit": limit},
            fmt=fmt,
            to_view=_view,
        ),
        dry_run=dry_run,
        mock=mock,
        yes=yes,
    )


# ===================================================================
# tool run 命令
# ===================================================================


def _run_controller(tool_id: str, input_json: str, tenant_id: str | None, dry_run: bool = False) -> Any:
    """tool run controller（守卫→dry_run 分叉→resolve→异步执行）。

    Args:
        tool_id: --tool-id（UUID 守卫）
        input_json: --input JSON 串（dict 解析守卫）
        tenant_id: --tenant-id（可选——双通道解析后 UUID 转换；ExecutionContext
            契约 UUID 硬校验。R1-F12：旗标缺省经 SISYS_TENANT_ID env 回退，
            双缺 242 fail-loud——Task 0.1 租户参数栏钦定）
        dry_run: --dry-run 旗标（动作清单：工具名+入参回显+Schema 摘要——Task 3.7 钦定）

    Returns:
        动作清单（dry_run）或 ToolResult

    Raises:
        EntityValidationError: 242——tool_id/input/tenant_id 守卫失败
    """
    tool_uuid = _validate_uuid(tool_id, field="tool_id")
    arguments = _parse_input_json(input_json)
    tenant_uuid = _validate_uuid(_resolve_tenant_id(tenant_id, command="tool run"), field="tenant_id")
    if dry_run:
        schema_keys = "、".join(arguments.keys()) if arguments else "（无参数）"
        return [f"将执行工具 {tool_uuid}（租户 {tenant_uuid}——入参键: {schema_keys}——参数 JSON 经 input_schema 校验后执行）"]
    service = get_resolver().resolve("tool_execution_service")
    tool_call = ToolCall(tool_id=tool_uuid, arguments=arguments, tenant_id=tenant_uuid)
    context = ExecutionContext(tenant_id=tenant_uuid)

    async def _kernel() -> Any:
        # 异步内核 finally 关池（协程内同 loop——R1-F8 与兄弟命令一致性）
        try:
            return await service.execute(tool_uuid, tool_call, context)
        finally:
            await run_cleanup_async()

    return asyncio.run(_kernel())


@app.command("run")
def tool_run(
    tool_id: str = typer.Option(..., "--tool-id", help="工具唯一标识（UUID）"),
    input: str = typer.Option(..., "--input", help="调用参数（JSON 对象——符合工具 input_schema）"),
    tenant_id: str | None = typer.Option(
        None, "--tenant-id", help="租户标识（UUID——ExecutionContext 契约；缺省 SISYS_TENANT_ID env 回退，双缺 fail-loud）"
    ),
    dry_run: DryRunOption = False,
    mock: MockOption = False,
    yes: YesOption = False,
    fmt: FormatOption = OutputFormat.PRETTY,
) -> None:
    """执行工具（沙箱执行链 VFD>Sandbox>Validator>Engine——5-3 激活链）。"""

    def _view(result: Any) -> dict[str, Any]:
        return {
            "tool_id": tool_id,
            "status": enum_value(getattr(result, "status", "")),
            "output": getattr(result, "output", None),
        }

    def _pretty_shell() -> int:
        result = _run_controller(tool_id, input, tenant_id)
        print("工具执行完成:")
        print(f"  状态: {enum_value(getattr(result, 'status', ''))}")
        print(f"  输出: {getattr(result, 'output', '')}")
        return 0

    invoke_command(
        CommandSpec(
            command="sisys tool run",
            controller=lambda dr: _run_controller(tool_id, input, tenant_id, dry_run=dr),
            pretty_shell=_pretty_shell,
            mock_echo=lambda: {
                "tool_id": tool_id,
                "input": input,
                "tenant_id": _resolve_tenant_id(tenant_id, command="tool run"),
            },
            fmt=fmt,
            to_view=_view,
        ),
        dry_run=dry_run,
        mock=mock,
        yes=yes,
    )
