"""文档版本快照端口契约测试

验证 DocumentRepositoryPort 端口契约：
- 端口注册到 _global_registry
- 接口类型正确
- 版本号正确
- 生命周期正确
- 新增方法签名存在
"""

from __future__ import annotations

import dataclasses

import pytest

from src.domain.events.base import DomainEvent
from src.domain.events.document_events import DocumentVersionSnapshotCreated
from src.domain.ports.document_repository import DocumentRepositoryPort
from src.domain.ports.registry import _global_registry


class TestDocumentVersionPortContract:
    """验证文档版本相关端口契约"""

    def test_document_repository_port_registered(self) -> None:
        """document_repository 端口应已注册到 _global_registry"""
        spec = _global_registry.get("document_repository")
        assert spec is not None, "document_repository port should be registered"

    def test_interface_type_is_document_repository_port(self) -> None:
        """端口接口类型应为 DocumentRepositoryPort"""
        spec = _global_registry.get("document_repository")
        assert spec is not None
        assert spec.interface is DocumentRepositoryPort

    def test_version_is_v1_1_0(self) -> None:
        """端口版本应为 v1.1.0"""
        spec = _global_registry.get("document_repository")
        assert spec is not None
        assert spec.version == "v1.1.0"

    def test_lifetime_is_scoped(self) -> None:
        """生命周期应为 SCOPED"""
        spec = _global_registry.get("document_repository")
        assert spec is not None
        assert spec.lifetime.name == "SCOPED"

    def test_save_version_snapshot_method_exists(self) -> None:
        """save_version_snapshot 方法应存在"""
        assert hasattr(DocumentRepositoryPort, "save_version_snapshot")
        method = DocumentRepositoryPort.save_version_snapshot
        assert callable(method)

    def test_list_versions_method_exists(self) -> None:
        """list_versions 方法应存在"""
        assert hasattr(DocumentRepositoryPort, "list_versions")
        method = DocumentRepositoryPort.list_versions
        assert callable(method)

    def test_get_version_method_exists(self) -> None:
        """get_version 方法应存在"""
        assert hasattr(DocumentRepositoryPort, "get_version")
        method = DocumentRepositoryPort.get_version
        assert callable(method)

    def test_save_with_version_check_method_exists(self) -> None:
        """save_with_version_check 方法应存在"""
        assert hasattr(DocumentRepositoryPort, "save_with_version_check")
        method = DocumentRepositoryPort.save_with_version_check
        assert callable(method)


class TestDocumentVersionSnapshotCreatedEventContract:
    """验证 DocumentVersionSnapshotCreated 事件契约"""

    def test_event_registered_in_domain_event_registry(self) -> None:
        """事件应自动注册到 DomainEvent._registry"""
        assert "DocumentVersionSnapshotCreated" in DomainEvent._registry
        assert DomainEvent._registry["DocumentVersionSnapshotCreated"] is DocumentVersionSnapshotCreated

    def test_event_is_frozen_dataclass(self) -> None:
        """事件应为 frozen dataclass"""
        assert dataclasses.is_dataclass(DocumentVersionSnapshotCreated)
        # 行为验证：frozen dataclass 修改字段抛出 FrozenInstanceError
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(DocumentVersionSnapshotCreated(), "new_version", 99)

    def test_event_has_required_fields(self) -> None:
        """事件应包含所有必需字段"""
        import inspect

        sig = inspect.signature(DocumentVersionSnapshotCreated)
        params = sig.parameters
        assert "document_id" in params
        assert "new_version" in params
        assert "snapshot_id" in params
        assert "created_by" in params
        assert "diff_summary" in params
        assert "tenant_id" in params
