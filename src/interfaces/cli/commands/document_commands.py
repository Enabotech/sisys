"""document 命令组（upload / parse）

typer 命令定义层（参数解析 → 守卫归一 → CommandContext 组装 → 共享短路
执行器）；编排与端口消费归 ``controllers/document_controller.py``
（commands 只定义参数、controller 只编排——职责分界）。

存量处置（Task 3）：原 version 命令族（argparse 未接线存量，185 行）随本
重写移除——§4.3.1 钦定命令面 defer 7-1-DF5/OD-7 归宿；端口
``document_version_service`` 与事件处理器不动。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer

from src.interfaces.cli import _params
from src.interfaces.cli.controllers.base import CommandContext, ensure_session, execute_command, to_decimal
from src.interfaces.cli.controllers.document_controller import (
    PORT_NAME,
    PORT_NAME_PARSE,
    DocumentUploadCommand,
    normalize_parse_id,
    require_upload_file,
    run_parse,
    run_upload,
)


def build_app(resolve: Callable[[str], Any]) -> typer.Typer:
    """构造 document 命令组（挂载 upload/parse 两命令——12 命令冻结矩阵）。

    Args:
        resolve: 端口解析函数（工厂注入）

    Returns:
        document 模块 typer.Typer 子应用
    """
    document_app = typer.Typer(help="文档管理（upload 上传 / parse 解析）")

    @document_app.command("upload")
    def upload(
        file: Path = typer.Option(..., "--file", help="上传文件路径"),
        business_domain: str = typer.Option("", "--business-domain", help="业务域标注"),
        yes: _params.YesOption = False,
        dry_run: _params.DryRunOption = False,
        mock: _params.MockOption = False,
        fmt: _params.FormatOption = _params.OutputFormat.TABLE,
        session: _params.SessionOption = "",
        cost_budget: _params.CostBudgetOption = None,
    ) -> int:
        """上传文档至文档服务（真实落库并输出 document_id）。"""
        require_upload_file(file)
        command = DocumentUploadCommand(file=file, business_domain=business_domain)
        ctx = CommandContext(
            command="document upload",
            port_name=PORT_NAME,
            parameters=command.to_parameters(),
            fmt=fmt.value,
            dry_run=dry_run,
            mock=mock,
            yes=yes,
            cost_budget=to_decimal(cost_budget),
            session=ensure_session(session),
        )
        return execute_command(
            ctx,
            resolve,
            lambda r: run_upload(file, business_domain=business_domain, fmt=fmt.value, resolve=r),
        )

    @document_app.command("parse")
    def parse(
        document_id: str = typer.Option(..., "--id", help="文档标识（UUID）"),
        yes: _params.YesOption = False,
        dry_run: _params.DryRunOption = False,
        mock: _params.MockOption = False,
        fmt: _params.FormatOption = _params.OutputFormat.TABLE,
        session: _params.SessionOption = "",
        cost_budget: _params.CostBudgetOption = None,
    ) -> int:
        """解析已上传文档（真实解析链）。"""
        normalized_id = normalize_parse_id(document_id)
        ctx = CommandContext(
            command="document parse",
            port_name=PORT_NAME_PARSE,
            parameters={"document_id": normalized_id},
            fmt=fmt.value,
            dry_run=dry_run,
            mock=mock,
            yes=yes,
            cost_budget=to_decimal(cost_budget),
            session=ensure_session(session),
        )
        return execute_command(
            ctx,
            resolve,
            lambda r: run_parse(normalized_id, fmt=fmt.value, resolve=r),
        )

    return document_app
