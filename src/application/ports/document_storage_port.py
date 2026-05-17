"""应用层文档存储端口模块

继承 L4ObjectPort，添加文档业务语义

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.ports.l4_object import L4ObjectPort


@runtime_checkable
class DocumentStoragePort(L4ObjectPort, Protocol):
    """文档存储端口 — 继承L4ObjectPort，添加文档业务语义

    继承所有L4ObjectPort方法，额外提供：
    - 自动路径生成（documents/{user_id}/{type}/YYYY-MM）
    - 文档元数据管理
    - 用户文档列表
    """

    async def store_document(
        self,
        user_id: str,
        doc_type: str,
        file_path: str,
        metadata: dict | None = None,
    ) -> str:
        """存储文档（自动生成对象路径）

        Args:
            user_id: 用户 ID
            doc_type: 文档类型
            file_path: 本地文件路径
            metadata: 可选元数据

        Returns:
            文档对象路径作为 ID
        """

    async def list_user_documents(
        self,
        user_id: str,
        doc_type: str | None = None,
    ) -> list[dict]:
        """列出用户文档

        Args:
            user_id: 用户 ID
            doc_type: 可选文档类型过滤

        Returns:
            文档元数据列表
        """

    async def get_document_metadata(
        self,
        user_id: str,
        document_id: str,
    ) -> dict | None:
        """获取文档元数据

        Args:
            user_id: 用户 ID
            document_id: 文档 ID（对象路径）

        Returns:
            文档元数据，不存在返回 None
        """
