"""Tests for PostgreSQLDocumentRepository — 版本快照操作

Mock 测试 save_version_snapshot / list_versions / get_version / save_with_version_check。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.domain.entities.document import Document
from src.domain.exceptions import DocumentVersionConflictError, NotFoundError
from src.domain.value_objects.document_version import DocumentVersionSnapshot
from src.infrastructure.storage.postgresql.repository.document_repository import (
    PostgreSQLDocumentRepository,
)
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


def run_async(coro):
    """同步运行 async 协程"""
    return asyncio.run(coro)


class MockResult:
    """Mock SQLAlchemy execute result."""

    def __init__(self, scalar_one_or_none=None, scalars_all=None, scalar_one=None):
        self._scalar_one_or_none = scalar_one_or_none
        self._scalars_all = scalars_all
        self._scalar_one = scalar_one

    def scalar_one_or_none(self):
        return self._scalar_one_or_none

    def scalars(self):
        return MockScalars(self._scalars_all or [])

    def scalar_one(self):
        return self._scalar_one


class MockScalars:
    """Mock scalars result."""

    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


def _make_snapshot(version: int = 1) -> DocumentVersionSnapshot:
    """创建测试用版本快照值对象"""
    return DocumentVersionSnapshot(
        document_id=uuid4(),
        version=version,
        snapshot_id=uuid4(),
        created_at=datetime.now(UTC),
        created_by="test_user",
        change_description="test",
        diff_summary="initial version" if version == 1 else "content changed",
        diff_json={"changed_fields": [], "is_initial": version == 1},
    )


def _make_doc(version: int = 1) -> Document:
    """创建测试用文档实体"""
    return Document(
        document_id=uuid4(),
        filename="test.pdf",
        version=version,
        tenant_id="tenant-1",
        uploaded_by="user-1",
    )


class TestSaveVersionSnapshot:
    """验证 save_version_snapshot 方法"""

    @pytest.fixture
    def mock_session(self):
        mock = AsyncMock()
        mock.add = MagicMock()
        mock.flush = AsyncMock()
        return mock

    @pytest.fixture
    def repo(self, mock_session):
        token = set_session(mock_session)
        repo = PostgreSQLDocumentRepository()
        yield repo
        reset_session(token)

    def test_save_version_snapshot_success(self, repo, mock_session) -> None:
        """成功保存版本快照"""
        snapshot = _make_snapshot(version=1)
        mock_session.flush = AsyncMock()
        result = run_async(repo.save_version_snapshot(snapshot))

        assert result.document_id == snapshot.document_id
        assert result.version == snapshot.version
        assert result.diff_summary == snapshot.diff_summary
        mock_session.add.assert_called_once()

    def test_save_version_snapshot_returns_input(self, repo, mock_session) -> None:
        """返回输入值对象（非重新读取）"""
        snapshot = _make_snapshot(version=1)
        mock_session.flush = AsyncMock()
        result = run_async(repo.save_version_snapshot(snapshot))
        assert result is snapshot


class TestListVersions:
    """验证 list_versions 方法"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session):
        token = set_session(mock_session)
        repo = PostgreSQLDocumentRepository()
        yield repo
        reset_session(token)

    def test_list_versions_returns_snapshots(self, repo, mock_session) -> None:
        """列出版本历史"""
        # 构造 mock 模型
        from src.infrastructure.storage.postgresql.models.document_version import (
            DocumentVersionSnapshotModel,
        )

        doc_id = uuid4()
        model = DocumentVersionSnapshotModel(
            document_id=doc_id,
            version=2,
            snapshot_id=uuid4(),
            created_by="user",
            change_description="更新",
            diff_summary="content changed",
        )

        # 第一次查询：验证文档存在
        doc_model_mock = MagicMock()
        doc_model_mock.id = doc_id
        doc_model_mock.tenant_id = "tenant-1"

        mock_session.execute = AsyncMock(
            side_effect=[
                MockResult(scalar_one_or_none=doc_model_mock),  # 文档存在验证
                MockResult(scalars_all=[model]),  # 版本列表查询
            ]
        )

        result = run_async(repo.list_versions(doc_id, "tenant-1"))
        assert len(result) == 1
        assert result[0].version == 2

    def test_list_versions_empty_for_unknown_tenant(self, repo, mock_session) -> None:
        """未知租户返回空列表"""
        mock_session.execute = AsyncMock(return_value=MockResult(scalar_one_or_none=None))

        result = run_async(repo.list_versions(uuid4(), "unknown-tenant"))
        assert result == []


class TestGetVersion:
    """验证 get_version 方法"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session):
        token = set_session(mock_session)
        repo = PostgreSQLDocumentRepository()
        yield repo
        reset_session(token)

    def test_get_version_returns_snapshot(self, repo, mock_session) -> None:
        """获取指定版本"""
        from src.infrastructure.storage.postgresql.models.document_version import (
            DocumentVersionSnapshotModel,
        )

        doc_id = uuid4()
        model = DocumentVersionSnapshotModel(
            document_id=doc_id,
            version=1,
            snapshot_id=uuid4(),
            created_by="user",
        )

        doc_model_mock = MagicMock()
        doc_model_mock.id = doc_id
        doc_model_mock.tenant_id = "tenant-1"

        mock_session.execute = AsyncMock(
            side_effect=[
                MockResult(scalar_one_or_none=doc_model_mock),  # 文档存在验证
                MockResult(scalar_one_or_none=model),  # 版本查询
            ]
        )

        result = run_async(repo.get_version(doc_id, 1, "tenant-1"))
        assert result is not None
        assert result.version == 1

    def test_get_version_not_found(self, repo, mock_session) -> None:
        """不存在的版本返回 None"""
        doc_id = uuid4()
        doc_model_mock = MagicMock()
        doc_model_mock.id = doc_id
        doc_model_mock.tenant_id = "tenant-1"

        mock_session.execute = AsyncMock(
            side_effect=[
                MockResult(scalar_one_or_none=doc_model_mock),  # 文档存在
                MockResult(scalar_one_or_none=None),  # 版本不存在
            ]
        )

        result = run_async(repo.get_version(doc_id, 99, "tenant-1"))
        assert result is None

    def test_get_version_tenant_mismatch(self, repo, mock_session) -> None:
        """租户不匹配返回 None"""
        mock_session.execute = AsyncMock(return_value=MockResult(scalar_one_or_none=None))

        result = run_async(repo.get_version(uuid4(), 1, "wrong-tenant"))
        assert result is None


class TestSaveWithVersionCheck:
    """验证 save_with_version_check 方法"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session):
        token = set_session(mock_session)
        repo = PostgreSQLDocumentRepository()
        yield repo
        reset_session(token)

    def test_save_with_version_check_success(self, repo, mock_session) -> None:
        """版本匹配时成功保存"""
        from sqlalchemy.engine import CursorResult

        doc = _make_doc(version=2)
        doc.document_id = uuid4()

        # 模拟原子 UPDATE 成功（rowcount=1）
        cursor_mock = MagicMock(spec=CursorResult)
        cursor_mock.rowcount = 1
        mock_session.execute = AsyncMock(return_value=cursor_mock)

        # 模拟 reload 查询
        from src.infrastructure.storage.postgresql.models.document import DocumentModel

        reload_model = DocumentModel(
            id=doc.document_id,
            tenant_id="tenant-1",
            filename="test.pdf",
            version=2,
        )
        # 第二次 execute 调用返回 reload 结果
        mock_session.execute.side_effect = [
            cursor_mock,  # UPDATE 结果
            MockResult(scalar_one=reload_model),  # reload 结果
        ]

        result = run_async(repo.save_with_version_check(doc, expected_version=1))
        assert result is not None
        assert result.version == 2

    def test_save_with_version_check_conflict(self, repo, mock_session) -> None:
        """版本不匹配时抛出 DocumentVersionConflictError"""
        from sqlalchemy.engine import CursorResult

        doc = _make_doc(version=2)
        doc.document_id = uuid4()

        # 模拟原子 UPDATE 失败（rowcount=0）
        cursor_mock = MagicMock(spec=CursorResult)
        cursor_mock.rowcount = 0
        mock_session.execute = AsyncMock(return_value=cursor_mock)

        # 检查文档存在（版本冲突场景）
        from src.infrastructure.storage.postgresql.models.document import DocumentModel

        existing_model = DocumentModel(
            id=doc.document_id,
            tenant_id="tenant-1",
            filename="test.pdf",
            version=3,  # 实际版本为 3，与 expected_version=1 不匹配
        )
        mock_session.execute.side_effect = [
            cursor_mock,  # UPDATE 失败
            MockResult(scalar_one_or_none=existing_model),  # 检查文档存在
        ]

        with pytest.raises(DocumentVersionConflictError) as exc_info:
            run_async(repo.save_with_version_check(doc, expected_version=1))

        assert exc_info.value.expected_version == 1
        assert exc_info.value.actual_version == 3

    def test_save_with_version_check_document_not_found(self, repo, mock_session) -> None:
        """文档不存在时抛出 NotFoundError"""
        from sqlalchemy.engine import CursorResult

        doc = _make_doc(version=2)
        doc.document_id = uuid4()

        # 模拟原子 UPDATE 失败（rowcount=0）
        cursor_mock = MagicMock(spec=CursorResult)
        cursor_mock.rowcount = 0
        mock_session.execute = AsyncMock(return_value=cursor_mock)

        # 检查文档存在（文档不存在）
        mock_session.execute.side_effect = [
            cursor_mock,  # UPDATE 失败
            MockResult(scalar_one_or_none=None),  # 文档不存在
        ]

        with pytest.raises(NotFoundError):
            run_async(repo.save_with_version_check(doc, expected_version=1))
