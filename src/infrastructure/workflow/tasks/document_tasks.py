"""基础设施层文档处理任务模块

定义 parse_document, generate_embedding, index_document Prefect tasks

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from typing import Any

from prefect import task


@task(retries=2)
async def parse_document(document_id: uuid.UUID, file_path: str) -> dict[str, Any]:
    """解析文档任务

    MVP 占位实现，返回 mock 数据。
    真实解析逻辑由 Epic 2/3 故事补充。

    Args:
        document_id: 文档 UUID
        file_path: 文件路径

    Returns:
        ParseResult mock 数据
    """
    return {"status": "parsed", "document_id": str(document_id), "pages": 0}


@task(retries=2)
async def generate_embedding(parse_result: dict[str, Any]) -> list[float]:
    """生成嵌入向量任务

    MVP 占位实现，返回 mock 数据。
    真实嵌入逻辑由 Epic 2/3 故事补充。

    Args:
        parse_result: 解析结果

    Returns:
        Embedding mock 数据
    """
    return []


@task(retries=2)
async def index_document(embedding_result: list[float]) -> dict[str, Any]:
    """索引文档任务

    MVP 占位实现，返回 mock 数据。
    真实索引逻辑由 Epic 2/3 故事补充。

    Args:
        embedding_result: 嵌入结果

    Returns:
        IndexResult mock 数据
    """
    return {"indexed": False, "chunk_count": 0}
