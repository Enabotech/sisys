"""文档版本快照应用服务

提供版本快照创建、查询等用例编排。
采用事件驱动方案，不直接注入到上传/解析服务。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from src.domain.services.document_version_diff_service import compute_diff

if TYPE_CHECKING:
    from src.domain.ports.document_repository import DocumentRepositoryPort
    from src.domain.ports.event_publisher import EventPublisher
    from src.domain.value_objects.document_version import DocumentVersionSnapshot


class DocumentVersionService:
    """文档版本快照应用服务

    编排版本快照的创建、查询等操作，依赖注入模式使用 TYPE_CHECKING。
    """

    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        event_publisher: EventPublisher,
    ) -> None:
        """初始化文档版本快照服务

        Args:
            document_repository: 文档仓储端口
            event_publisher: 事件发布器端口
        """
        self._repository = document_repository
        self._publisher = event_publisher

    async def create_snapshot(
        self,
        document_id: UUID,
        tenant_id: str,
        created_by: str,
        change_description: str = "",
    ) -> DocumentVersionSnapshot:
        """创建文档版本快照

        1. 查询文档实体（获取当前版本号）
        2. 获取前一个版本的 metadata（用于 diff 计算）
        3. 调用领域服务 compute_diff() 计算差异摘要
        4. 使用 save_with_version_check() 保存文档（乐观锁验证）
        5. 持久化 DocumentVersionSnapshot
        6. 发布 DocumentVersionSnapshotCreated 事件

        Args:
            document_id: 文档唯一标识符
            tenant_id: 租户标识符
            created_by: 操作者标识
            change_description: 变更描述

        Returns:
            创建成功的版本快照

        Raises:
            DocumentVersionConflictError: 版本冲突时抛出
        """
        # 1. 查询文档实体
        from src.domain.ports.document_repository import DocumentQuery

        query = DocumentQuery(
            document_id=document_id,
            tenant_id=tenant_id,
        )
        document = await self._repository.find(query)
        if document is None:
            from src.domain.exceptions import NotFoundError

            raise NotFoundError(f"Document not found: {document_id}")

        current_version = document.version

        # 2. 获取前一个版本的 metadata
        old_metadata = dict(document.metadata) if document.metadata else {}

        # 3. 计算差异摘要
        is_initial = current_version == 1
        diff = compute_diff(
            old_metadata=old_metadata,
            new_metadata=old_metadata,
            is_initial=is_initial,
        )

        # 4. 使用 save_with_version_check 保存文档（乐观锁验证）
        from datetime import UTC, datetime
        from uuid import uuid4

        document.version = current_version
        await self._repository.save_with_version_check(
            document=document,
            expected_version=current_version,
        )

        # 5. 持久化 DocumentVersionSnapshot
        from src.domain.value_objects.document_version import DocumentVersionSnapshot

        snapshot_id = uuid4()
        snapshot = DocumentVersionSnapshot(
            document_id=document_id,
            version=current_version,
            snapshot_id=snapshot_id,
            created_at=datetime.now(UTC),
            created_by=created_by,
            change_description=change_description,
            diff_summary=diff.diff_summary,
            diff_json={
                "changed_fields": diff.changed_fields,
                "is_initial": diff.is_initial,
            }
            if diff.changed_fields or diff.is_initial
            else None,
        )

        await self._repository.save_version_snapshot(snapshot)

        # 6. 发布 DocumentVersionSnapshotCreated 事件
        from src.domain.events.document_events import DocumentVersionSnapshotCreated

        event = DocumentVersionSnapshotCreated(
            document_id=document_id,
            new_version=current_version,
            snapshot_id=snapshot_id,
            created_by=created_by,
            diff_summary=diff.diff_summary,
            tenant_id=tenant_id,
        )
        await self._publisher.publish(event)

        return snapshot

    async def list_versions(
        self,
        document_id: UUID,
        tenant_id: str,
    ) -> list[DocumentVersionSnapshot]:
        """列出文档版本历史

        Args:
            document_id: 文档唯一标识符
            tenant_id: 租户标识符

        Returns:
            版本快照列表（按版本号降序排列）
        """
        return await self._repository.list_versions(document_id, tenant_id)

    async def get_version(
        self,
        document_id: UUID,
        version: int,
        tenant_id: str,
    ) -> DocumentVersionSnapshot | None:
        """获取指定版本快照

        Args:
            document_id: 文档唯一标识符
            version: 版本号
            tenant_id: 租户标识符

        Returns:
            版本快照或 None
        """
        return await self._repository.get_version(document_id, version, tenant_id)
