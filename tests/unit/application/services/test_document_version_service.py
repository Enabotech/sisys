"""文档版本快照应用服务单元测试

测试 DocumentVersionService 的 create_snapshot/list_versions/get_version 方法。
Mock 端口测试各种场景。
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.domain.entities.document import Document
from src.domain.value_objects.document_version import DocumentVersionSnapshot


def _make_service(mock_repo: AsyncMock | None = None, mock_publisher: AsyncMock | None = None):
    """创建带 mock 依赖注入的 DocumentVersionService 实例"""
    from src.application.services.document_version_service import DocumentVersionService

    repo = mock_repo or AsyncMock()
    publisher = mock_publisher or AsyncMock()
    return DocumentVersionService(document_repository=repo, event_publisher=publisher)


def _make_document(version: int = 1, tenant_id: str = "tenant-1") -> Document:
    """创建测试用文档实体"""
    return Document(
        document_id=uuid4(),
        filename="test.pdf",
        version=version,
        tenant_id=tenant_id,
        uploaded_by="user-1",
    )


class TestDocumentVersionServiceCreateSnapshot:
    """测试 create_snapshot 方法"""

    def test_create_snapshot_success(self) -> None:
        """成功创建版本快照"""
        doc = _make_document(version=1)
        repo = AsyncMock()
        repo.find = AsyncMock(return_value=doc)
        repo.save_with_version_check = AsyncMock(return_value=doc)
        repo.save_version_snapshot = AsyncMock(return_value=MagicMock())

        service = _make_service(mock_repo=repo)

        import asyncio

        snapshot = asyncio.run(
            service.create_snapshot(
                document_id=doc.document_id,
                tenant_id=doc.tenant_id,
                created_by="user-1",
                change_description="文档上传",
            )
        )

        assert snapshot.document_id == doc.document_id
        assert snapshot.version == 1
        assert snapshot.created_by == "user-1"
        assert snapshot.change_description == "文档上传"
        repo.find.assert_called_once()
        repo.save_with_version_check.assert_called_once()
        repo.save_version_snapshot.assert_called_once()

    def test_create_snapshot_document_not_found(self) -> None:
        """文档不存在时应抛出 NotFoundError"""
        repo = AsyncMock()
        repo.find = AsyncMock(return_value=None)
        service = _make_service(mock_repo=repo)

        from src.domain.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            import asyncio

            asyncio.run(
                service.create_snapshot(
                    document_id=uuid4(),
                    tenant_id="tenant-1",
                    created_by="user-1",
                )
            )

    def test_create_snapshot_publishes_event(self) -> None:
        """创建快照后应发布事件"""
        doc = _make_document(version=1)
        repo = AsyncMock()
        repo.find = AsyncMock(return_value=doc)
        repo.save_with_version_check = AsyncMock(return_value=doc)
        repo.save_version_snapshot = AsyncMock(return_value=MagicMock())

        publisher = AsyncMock()
        service = _make_service(mock_repo=repo, mock_publisher=publisher)

        import asyncio

        asyncio.run(
            service.create_snapshot(
                document_id=doc.document_id,
                tenant_id=doc.tenant_id,
                created_by="user-1",
            )
        )

        publisher.publish.assert_called_once()
        call_args = publisher.publish.call_args[0][0]
        assert call_args.event_type == "DocumentVersionSnapshotCreated"
        assert call_args.document_id == doc.document_id


class TestDocumentVersionServiceListVersions:
    """测试 list_versions 方法"""

    def test_list_versions_returns_snapshots(self) -> None:
        """列出版本历史应返回快照列表"""
        doc_id = uuid4()
        snapshot = DocumentVersionSnapshot(
            document_id=doc_id,
            version=2,
            snapshot_id=uuid4(),
            created_at=datetime.now(UTC),
            created_by="user-1",
            diff_summary="文档解析完成",
        )

        repo = AsyncMock()
        repo.list_versions = AsyncMock(return_value=[snapshot])
        service = _make_service(mock_repo=repo)

        import asyncio

        result = asyncio.run(service.list_versions(document_id=doc_id, tenant_id="tenant-1"))

        assert len(result) == 1
        assert result[0].version == 2
        assert result[0].diff_summary == "文档解析完成"

    def test_list_versions_empty(self) -> None:
        """空版本历史应返回空列表"""
        repo = AsyncMock()
        repo.list_versions = AsyncMock(return_value=[])
        service = _make_service(mock_repo=repo)

        import asyncio

        result = asyncio.run(service.list_versions(document_id=uuid4(), tenant_id="tenant-1"))

        assert result == []


class TestDocumentVersionServiceGetVersion:
    """测试 get_version 方法"""

    def test_get_version_returns_snapshot(self) -> None:
        """获取指定版本应返回快照"""
        doc_id = uuid4()
        snapshot = DocumentVersionSnapshot(
            document_id=doc_id,
            version=1,
            snapshot_id=uuid4(),
            created_at=datetime.now(UTC),
            created_by="user-1",
        )

        repo = AsyncMock()
        repo.get_version = AsyncMock(return_value=snapshot)
        service = _make_service(mock_repo=repo)

        import asyncio

        result = asyncio.run(service.get_version(document_id=doc_id, version=1, tenant_id="tenant-1"))

        assert result is not None
        assert result.version == 1

    def test_get_version_not_found(self) -> None:
        """不存在的版本应返回 None"""
        repo = AsyncMock()
        repo.get_version = AsyncMock(return_value=None)
        service = _make_service(mock_repo=repo)

        import asyncio

        result = asyncio.run(service.get_version(document_id=uuid4(), version=99, tenant_id="tenant-1"))

        assert result is None
