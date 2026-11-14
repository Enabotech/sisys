"""战略归档 CLI 命令（Story 7-1——archive query，CQRS 读模型面）。

消费端口：``strategic_archive_service.query_archive(ArchiveQuery)``（组合根
:2399，SCOPED）——ArchiveQuery 为 Query Object 值对象（domain/ports/
archive_repository.py 定义：plan_id/archive_type/start_date/end_date/
validity_status/offset/limit 等）。

6.4-DF2 核销承载：无 session 上下文的 CLI 归档消费（fallback 独立会话
路径）+ 组合根 session_factory 接线守卫——集成测试
test_integration_cli_unified_entry.py 承载。
"""

from __future__ import annotations

import uuid as uuid_module
from typing import Any

import typer

from src.domain.exceptions import EntityValidationError
from src.domain.ports.resolver import get_resolver
from src.interfaces.cli.commands.document_commands import _resolve_tenant_id
from src.interfaces.cli.dispatch import CommandSpec, invoke_command, run_cleanup_async
from src.interfaces.cli.formatters import DryRunOption, FormatOption, MockOption, OutputFormat, YesOption, enum_value

app = typer.Typer(help="战略归档查询（query）")


def _query_controller(
    plan_id: str | None,
    archive_type: str | None,
    limit: int,
    offset: int,
    tenant_id: str | None,
    dry_run: bool = False,
) -> Any:
    """archive query controller（守卫→dry_run 分叉→resolve→异步执行）。

    Args:
        plan_id: --plan-id（可选——UUID 守卫+归一；缺省全量查询）
        archive_type: --archive-type（可选过滤）
        limit: --limit（缺省 20——ArchiveQuery 契约）
        offset: --offset（分页偏移）
        tenant_id: --tenant-id（双通道解析——租户消费型命令 fail-loud）
        dry_run: --dry-run 旗标（读命令退化态）

    Returns:
        动作清单（dry_run）或 StrategicArchive 列表

    Raises:
        EntityValidationError: 242——非法 plan_id/租户缺失
    """
    canonical_plan = None
    if plan_id is not None:
        try:
            canonical_plan = str(uuid_module.UUID(plan_id))
        except (ValueError, TypeError, AttributeError):
            raise EntityValidationError(
                message="plan_id 必须为 UUID 字符串",
                context={"command": "archive query", "field": "plan_id", "plan_id": plan_id},
            ) from None
    # 租户身份 fail-loud 通道（ArchiveQuery 无 tenant 字段——查询按 plan_id
    # 锚定租户隔离；--tenant-id 为操作者身份声明守卫——Task 0.1 租户消费型钦定）
    _resolve_tenant_id(tenant_id, command="archive query")
    if dry_run:
        return [f"将查询战略归档（plan_id={canonical_plan} archive_type={archive_type} limit={limit}）"]
    import asyncio

    from src.domain.ports.archive_repository import ArchiveQuery

    query_kwargs: dict[str, Any] = {"limit": limit, "offset": offset}
    if canonical_plan is not None:
        query_kwargs["plan_id"] = uuid_module.UUID(canonical_plan)
    if archive_type is not None:
        query_kwargs["archive_type"] = archive_type
    service = get_resolver().resolve("strategic_archive_service")

    async def _kernel() -> Any:
        # 异步内核 finally 关池（协程内同 loop——R1-F8 与兄弟命令一致性）
        try:
            return await service.query_archive(ArchiveQuery(**query_kwargs))
        finally:
            await run_cleanup_async()

    return asyncio.run(_kernel())


@app.command("query")
def archive_query(
    plan_id: str | None = typer.Option(None, "--plan-id", help="规划任务标识（UUID——可选过滤）"),
    archive_type: str | None = typer.Option(None, "--archive-type", help="归档类型过滤"),
    limit: int = typer.Option(20, "--limit", help="返回数上限（1-1000）"),
    offset: int = typer.Option(0, "--offset", help="分页偏移"),
    tenant_id: str | None = typer.Option(None, "--tenant-id", help="租户标识（或 SISYS_TENANT_ID 环境变量）"),
    dry_run: DryRunOption = False,
    mock: MockOption = False,
    yes: YesOption = False,
    fmt: FormatOption = OutputFormat.PRETTY,
) -> None:
    """查询战略归档（CQRS 读模型——无会话上下文 CLI 消费形态）。"""

    def _view(result: Any) -> dict[str, Any]:
        items = result or []
        return {
            "total": len(items),
            "archives": [
                {
                    "archive_id": str(getattr(item, "archive_id", "")),
                    "plan_id": str(getattr(item, "plan_id", "")),
                    "archive_type": enum_value(getattr(item, "archive_type", "")),
                    "created_at": str(getattr(item, "created_at", "")),
                }
                for item in items
            ],
        }

    def _pretty_shell() -> int:
        items = _query_controller(plan_id, archive_type, limit, offset, tenant_id)
        if not items:
            print("无归档记录（空结果）")
            return 0
        print(f"归档清单（{len(items)} 条）:")
        for item in items:
            archive_id = getattr(item, "archive_id", "")
            item_type = enum_value(getattr(item, "archive_type", ""))
            created = getattr(item, "created_at", "")
            print(f"  {archive_id} | {item_type} | {created}")
        return 0

    invoke_command(
        CommandSpec(
            command="sisys archive query",
            controller=lambda dr: _query_controller(plan_id, archive_type, limit, offset, tenant_id, dry_run=dr),
            pretty_shell=_pretty_shell,
            mock_echo=lambda: {"plan_id": plan_id, "archive_type": archive_type, "limit": limit},
            fmt=fmt,
            to_view=_view,
        ),
        dry_run=dry_run,
        mock=mock,
        yes=yes,
    )
