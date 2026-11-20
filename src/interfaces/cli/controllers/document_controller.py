"""document 命令控制器

命令对象（DC-4 frozen dataclass）+ 守卫归一 + 真实执行编排 + 静态
``PORT_NAME`` 常量（``--dry-run`` 端口名唯一来源——R1-F5，禁止 resolve）。

消费端口（AC-5 表）：
- ``document_upload_service``（composition_root.py:1189）
- ``document_parsing_service``（:1371）

CLI 无用户上下文的租户取值常量（upload 服务必填 str——API 面经
X-Tenant-ID header 承载的缺口在 CLI 面的等价取值）。
"""

from __future__ import annotations

import asyncio
import mimetypes
import uuid as uuid_module
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.domain.exceptions import NotFoundError
from src.interfaces.cli._guards import canonical_uuid
from src.interfaces.cli.formatters import get_formatter

PORT_NAME = "document_upload_service"
PORT_NAME_PARSE = "document_parsing_service"

CLI_DEFAULT_TENANT_ID = "cli-default"
CLI_DEFAULT_USER = "cli-user"

# 五最小元字段补全常量（DocumentMetadata 必填校验——creator/created_at 由服务
# 自动填充，source/license/business_domain 由 CLI 侧补全）
CLI_DEFAULT_SOURCE = "cli-upload"
CLI_DEFAULT_LICENSE = "internal"
CLI_DEFAULT_BUSINESS_DOMAIN = "general"


@dataclass(frozen=True)
class DocumentUploadCommand:
    """文档上传命令值对象（CLI 参数归一后形态）。

    Args:
        file: 上传文件路径
        business_domain: 业务域标注（空串为未指定）
    """

    file: Path
    business_domain: str = ""

    def to_parameters(self) -> dict[str, Any]:
        """命令对象转 parameters 载荷（mock/dry-run 面渲染形态）。"""
        return {"file": str(self.file), "business_domain": self.business_domain}


def require_upload_file(file: Path) -> None:
    """上传文件存在性守卫（先于短路——坏输入在 mock/dry-run 面同样拒绝）。

    Raises:
        NotFoundError: EXCEPTION_202——文件不存在
    """
    if not file.is_file():
        raise NotFoundError(message=f"上传文件不存在: {file}", context={"file": str(file)})


def normalize_parse_id(document_id: str) -> str:
    """parse 文档标识 canonical 归一（实体 ID 族 242 守卫——R5-3 显式点名）。"""
    return canonical_uuid(document_id, field="document_id")


def run_upload(
    file: Path,
    *,
    business_domain: str = "",
    fmt: str = "table",
    resolve: Callable[[str], Any],
) -> int:
    """真实执行文档上传（守卫 → resolve 服务 → 上传 → 渲染 document_id）。

    Args:
        file: 上传文件路径
        business_domain: 业务域标注
        fmt: 输出格式
        resolve: 端口解析函数

    Returns:
        退出码（0=成功；DomainError 向上传播由入口统一映射）
    """
    require_upload_file(file)
    service = resolve(PORT_NAME)
    stat = file.stat()
    mime_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    document = asyncio.run(
        service.upload(
            filename=file.name,
            mime_type=mime_type,
            file_size_bytes=stat.st_size,
            tenant_id=CLI_DEFAULT_TENANT_ID,
            uploaded_by=CLI_DEFAULT_USER,
            file_path=str(file),
            metadata={
                "business_domain": business_domain or CLI_DEFAULT_BUSINESS_DOMAIN,
                "source": CLI_DEFAULT_SOURCE,
                "license": CLI_DEFAULT_LICENSE,
            },
        )
    )
    print(get_formatter(fmt)({"document_id": str(document.document_id), "filename": file.name}))
    return 0


def run_parse(
    document_id: str,
    *,
    fmt: str = "table",
    resolve: Callable[[str], Any],
) -> int:
    """真实执行文档解析（canonical 守卫 → resolve 服务 → 解析 → 渲染结果）。

    Args:
        document_id: 文档标识原始输入（canonical 归一后转 UUID 实例入服务）
        fmt: 输出格式
        resolve: 端口解析函数

    Returns:
        退出码（0=成功）
    """
    normalized = normalize_parse_id(document_id)
    service = resolve(PORT_NAME_PARSE)
    document = asyncio.run(service.parse_document(uuid_module.UUID(normalized), CLI_DEFAULT_TENANT_ID))
    payload = {
        "document_id": normalized,
        "parse_status": getattr(document, "parse_status", None),
        "page_count": getattr(document, "page_count", None),
    }
    print(get_formatter(fmt)(payload))
    return 0
