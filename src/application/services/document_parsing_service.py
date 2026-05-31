"""应用层文档解析服务

编排文档解析流程：获取文档 → MinIO 下载 → 临时文件桥接 → 解析 → 状态更新 → 事件发布。
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from dataclasses import replace
from typing import TYPE_CHECKING

from src.domain.entities.document import Document, ParseStatus
from src.domain.events.document_events import DocumentProcessed
from src.domain.ports.document_repository import DocumentQuery

if TYPE_CHECKING:
    from src.application.ports.document_storage_port import DocumentStoragePort
    from src.domain.ports.document_parser import DocumentParserPort
    from src.domain.ports.document_repository import DocumentRepositoryPort
    from src.domain.ports.event_publisher import EventPublisher


class DocumentParsingService:
    """文档解析编排服务

    编排完整的文档解析流程：
    1. 从仓储获取 Document 实体
    2. 从 MinIO 下载文件到临时文件（桥接 AsyncIterator → file_path）
    3. 调用解析器获取 ParsedDocument
    4. 更新 Document 状态和元数据
    5. 发布 DocumentProcessed 事件
    6. 清理临时文件
    """

    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        document_storage: DocumentStoragePort,
        event_publisher: EventPublisher,
        document_parser: DocumentParserPort,
    ) -> None:
        self._repository = document_repository
        self._storage = document_storage
        self._publisher = event_publisher
        self._parser = document_parser

    async def parse_document(self, document_id: uuid.UUID, tenant_id: str) -> Document:
        """解析文档

        Args:
            document_id: 文档 ID
            tenant_id: 租户标识符

        Returns:
            更新后的 Document 实体
        """
        query = DocumentQuery(tenant_id=tenant_id, document_id=document_id)
        document = await self._repository.find(query)

        if document is None:
            return Document(
                document_id=document_id,
                filename="",
                parse_status=ParseStatus.FAILED,
                metadata={"error": "文档不存在"},
            )

        # 检查 storage_object_key
        object_key = document.metadata.get("storage_object_key")
        if not object_key:
            document.parse_status = ParseStatus.FAILED
            document.metadata["parse_error"] = "文档缺少 storage_object_key"
            return document

        # 更新状态为 IN_PROGRESS
        document.parse_status = ParseStatus.IN_PROGRESS
        await self._repository.save(document)

        temp_path = ""
        try:
            # 下载文件到临时文件
            temp_path = await self._download_to_temp("raw-documents", object_key)

            # 解析文档（CPU 密集型，使用线程池避免阻塞事件循环）
            parsed_doc = await asyncio.to_thread(self._parser.parse, temp_path, document.mime_type)

            # 用真实文档 ID 覆盖解析器随机生成的 ID
            parsed_doc = replace(parsed_doc, document_id=str(document.document_id))

            if parsed_doc.parse_status == "failed":
                document.parse_status = ParseStatus.FAILED
                document.metadata["parse_error"] = parsed_doc.error_message or "解析失败"
                await self._repository.save(document)
                return document

            # 更新状态和元数据
            document.parse_status = ParseStatus.COMPLETED
            result_dict = parsed_doc.to_dict()
            document.metadata["parse_result"] = result_dict
            saved_doc = await self._repository.save(document)

            # 发布事件
            event = DocumentProcessed(
                document_id=saved_doc.document_id,
                parse_result=result_dict,
            )
            await self._publisher.publish(event)

            return saved_doc

        except Exception as e:
            document.parse_status = ParseStatus.FAILED
            document.metadata["parse_error"] = str(e)
            await self._repository.save(document)
            return document

        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    async def _download_to_temp(self, bucket_type: str, object_key: str) -> str:
        """从 MinIO 下载文件到临时文件

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键

        Returns:
            临时文件路径
        """
        stream = self._storage.retrieve(bucket_type, object_key)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
        try:
            async for chunk in stream:
                tmp.write(chunk)
            tmp.close()
            return tmp.name
        except Exception:
            tmp.close()
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
            raise
