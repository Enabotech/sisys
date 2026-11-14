"""文档 CLI 命令（Story 7-1 Typer 化——upload / search / version snapshot+list）。

统一入口 ``sisys document`` 命令面（Task 0.1 冻结表）：
    - upload：``document_upload_service.upload``（business_domain 映射 metadata
      dict 键——REST 面同源契约 document_upload.py:193-201）
    - search：``hybrid_search_service.search``（collection/query_text/limit/
      tenant_id 全参直传）
    - version snapshot/list：存量 ``document_version_service`` Typer 化保形
      （第 14 命令注记——错误处理对齐 ``[EXCEPTION_code]`` stderr 定式，OD-10）

分层：interfaces 层禁 import entrypoints/composition_root（OD-16 传导链）——
bootstrap/关池经 dispatch 组装期注入钩子承载；resolve 经 domain 层
``get_resolver``（组合根已装配前提——统一入口组装链保证）。
"""

from __future__ import annotations

import asyncio
import mimetypes
import os
from pathlib import Path
from typing import Any

import typer

from src.domain.exceptions import EntityValidationError
from src.domain.ports.resolver import get_resolver
from src.interfaces.cli.dispatch import CommandSpec, cli_session_scope, invoke_command, run_cleanup_async
from src.interfaces.cli.formatters import DryRunOption, FormatOption, MockOption, OutputFormat, YesOption

app = typer.Typer(help="文档上传 / 混合检索 / 版本管理（upload / search / version）")

version_app = typer.Typer(help="文档版本快照与历史（snapshot / list）")

app.add_typer(version_app, name="version")


def _resolve_tenant_id(tenant_id: str | None, *, command: str = "document") -> str:
    """租户双通道解析（--tenant-id 旗标或 SISYS_TENANT_ID env 回退）。

    Task 0.1 租户参数栏钦定：两者皆缺 242 fail-loud（无 default 兜底——
    静默租户是欺骗性成功）；校验层位=controller 守卫层（守卫先于 bootstrap）。

    Args:
        tenant_id: --tenant-id 原始值（缺省 None 走 env 通道）
        command: 命令名（异常 context 携带）

    Returns:
        租户标识字符串

    Raises:
        EntityValidationError: 242——双通道皆缺
    """
    value = tenant_id or os.environ.get("SISYS_TENANT_ID")
    if not value:
        raise EntityValidationError(
            message="租户标识必填（--tenant-id 或 SISYS_TENANT_ID 环境变量——双通道皆缺）",
            context={"command": command, "field": "tenant_id"},
        )
    return value


def _validate_document_uuid(document_id: str, *, command: str) -> str:
    """document_id 守卫+canonical 归一（agent_cli._validate_plan_uuid 同构语义）。

    Args:
        document_id: --id 原始字符串
        command: 命令名

    Returns:
        canonical 小写 UUID 字符串

    Raises:
        EntityValidationError: 242——非 UUID 形态
    """
    import uuid as uuid_module

    try:
        return str(uuid_module.UUID(document_id))
    except (ValueError, TypeError, AttributeError):
        raise EntityValidationError(
            message="文档 ID 必须为 UUID 字符串",
            context={"command": command, "field": "document_id", "document_id": document_id},
        ) from None


def _guess_mime(path: Path) -> str:
    """按扩展名推断 MIME（缺省 application/octet-stream）。"""
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


# ===================================================================
# upload / search 命令
# ===================================================================


def _upload_controller(
    file_path: str,
    business_domain: str,
    source: str,
    license: str,
    document_type: str,
    tenant_id: str | None,
    uploaded_by: str,
    dry_run: bool = False,
) -> Any:
    """document upload controller（守卫→dry_run 分叉→resolve→异步执行）。

    Args:
        file_path: --file 原始路径（存在性守卫 242）
        business_domain: --business-domain（映射 metadata dict 键——非顶层参数）
        source: --source（metadata 必填键——文档来源）
        license: --license（metadata 必填键——许可级别）
        document_type: --document-type（缺省 other）
        tenant_id: --tenant-id（双通道解析）
        uploaded_by: --uploaded-by（上传者身份）
        dry_run: --dry-run 旗标（client 语义——动作清单零 resolve）

    Returns:
        动作清单（dry_run）或上传 Document result

    Raises:
        EntityValidationError: 242——文件不存在/租户缺失
    """
    path = Path(file_path)
    if not path.is_file():
        raise EntityValidationError(
            message=f"上传文件不存在: {file_path}",
            context={"command": "document upload", "field": "file", "file": file_path},
        )
    tenant = _resolve_tenant_id(tenant_id, command="document upload")
    if dry_run:
        return [f"将上传文件 {path.name}（{path.stat().st_size}B）至租户 {tenant}，业务域 {business_domain}"]
    service = get_resolver().resolve("document_upload_service")

    async def _kernel() -> Any:
        # 请求路径仓储（document_repository）硬要求 session——CLI 会话作用域供给；
        # finally 关池（协程内同 loop——dispatch 钩子注入）
        try:
            return await _kernel_upload(service, path, tenant, uploaded_by, business_domain, source, license, document_type)
        finally:
            await run_cleanup_async()

    return asyncio.run(_kernel())


async def _kernel_upload(
    service: Any, path: Path, tenant: str, uploaded_by: str, business_domain: str, source: str, license: str, document_type: str
) -> Any:
    """upload 异步执行体（会话作用域内——独立函数便于阅读）。"""
    async with cli_session_scope():
        return await service.upload(
            filename=path.name,
            mime_type=_guess_mime(path),
            file_size_bytes=path.stat().st_size,
            tenant_id=tenant,
            uploaded_by=uploaded_by,
            file_path=str(path),
            document_type=document_type,
            metadata={"business_domain": business_domain, "source": source, "license": license},
        )


@app.command("upload")
def document_upload(
    file: str = typer.Option(..., "--file", help="上传文件路径"),
    business_domain: str = typer.Option(..., "--business-domain", help="业务域（metadata 必填键）"),
    source: str = typer.Option(..., "--source", help="文档来源（metadata 必填键）"),
    license: str = typer.Option(..., "--license", help="许可级别（metadata 必填键）"),
    tenant_id: str | None = typer.Option(None, "--tenant-id", help="租户标识（或 SISYS_TENANT_ID 环境变量）"),
    uploaded_by: str = typer.Option(..., "--uploaded-by", help="上传者身份（creator 自动填充源）"),
    document_type: str = typer.Option("other", "--document-type", help="文档类型（缺省 other）"),
    dry_run: DryRunOption = False,
    mock: MockOption = False,
    yes: YesOption = False,
    fmt: FormatOption = OutputFormat.PRETTY,
) -> None:
    """上传文档（落 MinIO 对象存储+PG 元数据——真实服务全链）。"""

    def _view(result: Any) -> dict[str, Any]:
        return {
            "document_id": str(getattr(result, "document_id", "")),
            "filename": str(getattr(result, "filename", "")),
            "tenant_id": tenant_id or os.environ.get("SISYS_TENANT_ID", ""),
            "document_type": document_type,
            "status": "uploaded",
        }

    def _pretty_shell() -> int:
        result = _upload_controller(file, business_domain, source, license, document_type, tenant_id, uploaded_by)
        print("文档上传成功:")
        print(f"  document_id: {getattr(result, 'document_id', '')}")
        print(f"  filename: {getattr(result, 'filename', '')}")
        return 0

    def _echo() -> dict[str, Any]:
        echo: dict[str, Any] = {
            "file": file,
            "file_exists": Path(file).is_file(),
            "business_domain": business_domain,
            "source": source,
            "uploaded_by": uploaded_by,
        }
        if tenant_id is not None:
            echo["tenant_id"] = tenant_id
        return echo

    invoke_command(
        CommandSpec(
            command="sisys document upload",
            controller=lambda dr: _upload_controller(
                file, business_domain, source, license, document_type, tenant_id, uploaded_by, dry_run=dr
            ),
            pretty_shell=_pretty_shell,
            mock_echo=_echo,
            fmt=fmt,
            to_view=_view,
        ),
        dry_run=dry_run,
        mock=mock,
        yes=yes,
    )


def _search_controller(
    query: str,
    collection: str,
    limit: int,
    tenant_id: str | None,
    dry_run: bool = False,
) -> Any:
    """document search controller（守卫→dry_run 分叉→resolve→异步执行）。

    Args:
        query: --query 检索文本（非空守卫）
        collection: --collection（缺省 documents）
        limit: --limit（缺省 10）
        tenant_id: --tenant-id（双通道解析）
        dry_run: --dry-run 旗标（读命令退化态——守卫+动作回显）

    Returns:
        动作清单（dry_run）或 SearchResult 列表

    Raises:
        EntityValidationError: 242——空 query/租户缺失
    """
    if not query.strip():
        raise EntityValidationError(
            message="检索文本不可为空",
            context={"command": "document search", "field": "query", "query": query},
        )
    tenant = _resolve_tenant_id(tenant_id, command="document search")
    if dry_run:
        return [f"将在 collection {collection} 执行混合检索: query={query!r} limit={limit}"]
    service = get_resolver().resolve("hybrid_search_service")

    async def _kernel() -> Any:
        # 异步内核 finally 关池（协程内同 loop——R1-F8 与兄弟命令一致性）
        try:
            return await service.search(collection=collection, query_text=query, limit=limit, tenant_id=tenant)
        finally:
            await run_cleanup_async()

    return asyncio.run(_kernel())


@app.command("search")
def document_search(
    query: str = typer.Option(..., "--query", help="检索文本"),
    tenant_id: str | None = typer.Option(None, "--tenant-id", help="租户标识（或 SISYS_TENANT_ID 环境变量）"),
    collection: str = typer.Option("documents", "--collection", help="检索 Collection 名（缺省 documents）"),
    limit: int = typer.Option(10, "--limit", help="返回结果数上限"),
    dry_run: DryRunOption = False,
    mock: MockOption = False,
    yes: YesOption = False,
    fmt: FormatOption = OutputFormat.PRETTY,
) -> None:
    """混合检索（Dense+Sparse+Graph 三路 RRF 融合）。"""

    def _view(result: Any) -> dict[str, Any]:
        items = result or []
        return {
            "total": len(items),
            "results": [
                {
                    "document_id": str(getattr(item, "document_id", getattr(item, "id", ""))),
                    "score": getattr(item, "score", 0.0),
                    "collection": collection,
                    "snippet": str(getattr(item, "text", getattr(item, "snippet", "")))[:80],
                }
                for item in items
            ],
        }

    def _pretty_shell() -> int:
        items = _search_controller(query, collection, limit, tenant_id)
        if not items:
            print("检索无命中结果")
            return 0
        for item in items:
            print(f"  命中: {getattr(item, 'document_id', getattr(item, 'id', ''))} score={getattr(item, 'score', 0.0)}")
        return 0

    invoke_command(
        CommandSpec(
            command="sisys document search",
            controller=lambda dr: _search_controller(query, collection, limit, tenant_id, dry_run=dr),
            pretty_shell=_pretty_shell,
            mock_echo=lambda: {"query": query, "collection": collection, "limit": limit},
            fmt=fmt,
            to_view=_view,
        ),
        dry_run=dry_run,
        mock=mock,
        yes=yes,
    )


# ===================================================================
# version snapshot / list 命令（存量保形——Typer 化重构）
# ===================================================================


def _snapshot_controller(
    document_id: str,
    tenant_id: str | None,
    user: str,
    description: str,
    dry_run: bool = False,
) -> Any:
    """version snapshot controller（守卫→dry_run 分叉→resolve→异步执行）。

    Args:
        document_id: --id 原始字符串（UUID 守卫+归一）
        tenant_id: --tenant-id（双通道解析）
        user: --user（操作者——缺省 cli）
        description: --description（变更描述）
        dry_run: --dry-run 旗标

    Returns:
        动作清单（dry_run）或快照 result

    Raises:
        EntityValidationError: 242——非法 ID/租户缺失
    """
    import uuid as uuid_module

    canonical = _validate_document_uuid(document_id, command="document version snapshot")
    tenant = _resolve_tenant_id(tenant_id, command="document version snapshot")
    if dry_run:
        return [f"将创建文档 {canonical} 版本快照（租户 {tenant}，操作者 {user}）"]
    service = get_resolver().resolve("document_version_service")

    async def _kernel() -> Any:
        try:
            async with cli_session_scope():
                return await service.create_snapshot(
                    document_id=uuid_module.UUID(canonical),
                    tenant_id=tenant,
                    created_by=user,
                    change_description=description,
                )
        finally:
            await run_cleanup_async()

    return asyncio.run(_kernel())


@version_app.command("snapshot")
def version_snapshot(
    id: str = typer.Option(..., "--id", help="文档唯一标识（UUID）"),
    tenant_id: str | None = typer.Option(None, "--tenant-id", help="租户标识（或 SISYS_TENANT_ID 环境变量）"),
    user: str = typer.Option("cli", "--user", help="操作者标识（缺省 cli）"),
    description: str = typer.Option(
        ..., "--description", help="变更描述（必填——Task 0.1 钦定：空描述快照无审计语义 fail-loud）"
    ),
    dry_run: DryRunOption = False,
    mock: MockOption = False,
    yes: YesOption = False,
    fmt: FormatOption = OutputFormat.PRETTY,
) -> None:
    """创建文档版本快照（记录操作者/时间戳/差异摘要）。"""

    def _view(result: Any) -> dict[str, Any]:
        return {
            "snapshot_id": str(getattr(result, "snapshot_id", "")),
            "document_id": str(getattr(result, "document_id", "")),
            "version": getattr(result, "version", 0),
            "created_by": str(getattr(result, "created_by", "")),
        }

    def _pretty_shell() -> int:
        result = _snapshot_controller(id, tenant_id, user, description)
        print("版本快照创建成功:")
        print(f"  快照 ID: {getattr(result, 'snapshot_id', '')}")
        print(f"  文档 ID: {getattr(result, 'document_id', '')}")
        print(f"  版本号: {getattr(result, 'version', 0)}")
        return 0

    invoke_command(
        CommandSpec(
            command="sisys document version snapshot",
            controller=lambda dr: _snapshot_controller(id, tenant_id, user, description, dry_run=dr),
            pretty_shell=_pretty_shell,
            mock_echo=lambda: {"id": id, "user": user},
            fmt=fmt,
            to_view=_view,
        ),
        dry_run=dry_run,
        mock=mock,
        yes=yes,
    )


def _version_list_controller(document_id: str, tenant_id: str | None, dry_run: bool = False) -> Any:
    """version list controller（守卫→dry_run 分叉→resolve→异步执行）。

    Args:
        document_id: --id 原始字符串（UUID 守卫+归一）
        tenant_id: --tenant-id（双通道解析）
        dry_run: --dry-run 旗标（读命令退化态）

    Returns:
        动作清单（dry_run）或版本历史列表

    Raises:
        EntityValidationError: 242——非法 ID/租户缺失
    """
    import uuid as uuid_module

    canonical = _validate_document_uuid(document_id, command="document version list")
    tenant = _resolve_tenant_id(tenant_id, command="document version list")
    if dry_run:
        return [f"将查询文档 {canonical} 版本历史（租户 {tenant}）"]
    service = get_resolver().resolve("document_version_service")

    async def _kernel() -> Any:
        try:
            async with cli_session_scope():
                return await service.list_versions(document_id=uuid_module.UUID(canonical), tenant_id=tenant)
        finally:
            await run_cleanup_async()

    return asyncio.run(_kernel())


@version_app.command("list")
def version_list(
    id: str = typer.Option(..., "--id", help="文档唯一标识（UUID）"),
    tenant_id: str | None = typer.Option(None, "--tenant-id", help="租户标识（或 SISYS_TENANT_ID 环境变量）"),
    dry_run: DryRunOption = False,
    mock: MockOption = False,
    yes: YesOption = False,
    fmt: FormatOption = OutputFormat.PRETTY,
) -> None:
    """查询文档版本历史。"""

    def _view(result: Any) -> dict[str, Any]:
        items = result or []
        return {
            "document_id": id,
            "versions": [
                {
                    "version": getattr(item, "version", 0),
                    "created_by": str(getattr(item, "created_by", "")),
                    "created_at": str(getattr(item, "created_at", "")),
                    "diff_summary": str(getattr(item, "diff_summary", "")),
                }
                for item in items
            ],
        }

    def _pretty_shell() -> int:
        items = _version_list_controller(id, tenant_id)
        if not items:
            print("该文档暂无版本历史")
            return 0
        print(f"文档 {id} 版本历史:")
        for item in items:
            version = getattr(item, "version", 0)
            created_by = getattr(item, "created_by", "")
            diff = getattr(item, "diff_summary", "")
            print(f"  版本 {version} | {created_by} | {diff}")
        return 0

    invoke_command(
        CommandSpec(
            command="sisys document version list",
            controller=lambda dr: _version_list_controller(id, tenant_id, dry_run=dr),
            pretty_shell=_pretty_shell,
            mock_echo=lambda: {"id": id},
            fmt=fmt,
            to_view=_view,
        ),
        dry_run=dry_run,
        mock=mock,
        yes=yes,
    )
