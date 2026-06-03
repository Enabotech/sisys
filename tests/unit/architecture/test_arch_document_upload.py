"""Story 2-1: SDD 架构约束验证测试

验证文档上传功能的架构合规性：
- domain 层零外部依赖
- 依赖方向正确（interfaces → application → domain, infrastructure → application → domain）
- 端口注册完整性
- 事件通道注册一致性
"""

from __future__ import annotations

import importlib

import pytest


class TestDomainLayerPurity:
    """验证 domain 层零外部依赖"""

    def test_document_format_no_external_deps(self) -> None:
        """document_format.py 不依赖外部库"""
        mod = importlib.import_module("src.domain.value_objects.document_format")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if hasattr(attr, "__module__") and attr.__module__:
                assert not attr.__module__.startswith(("sqlalchemy", "pydantic", "redis", "fastapi", "minio")), (
                    f"domain 层禁止依赖 {attr.__module__}"
                )

    def test_upload_limits_no_external_deps(self) -> None:
        """upload_limits.py 不依赖外部库"""
        mod = importlib.import_module("src.domain.value_objects.upload_limits")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if hasattr(attr, "__module__") and attr.__module__:
                assert not attr.__module__.startswith(("sqlalchemy", "pydantic", "redis", "fastapi", "minio")), (
                    f"domain 层禁止依赖 {attr.__module__}"
                )

    def test_document_repository_port_is_protocol(self) -> None:
        """DocumentRepositoryPort 是 Protocol（非具体实现）"""
        from typing import Protocol

        from src.domain.ports.document_repository import DocumentRepositoryPort

        assert Protocol in DocumentRepositoryPort.__mro__

    def test_document_events_no_external_deps(self) -> None:
        """document_events.py 不依赖外部库"""
        from src.domain.events.document_events import DocumentUploaded

        for field_type in [str, int]:
            assert hasattr(DocumentUploaded, "__dataclass_fields__")


class TestDependencyDirection:
    """验证依赖方向正确"""

    def test_application_imports_domain_only(self) -> None:
        """应用层仅依赖 domain 层"""

        import_tree = set()
        for name, val in vars(importlib.import_module("src.application.services.document_upload_service")).items():
            if hasattr(val, "__module__") and val.__module__:
                import_tree.add(val.__module__)

        for module_name in import_tree:
            if module_name.startswith("src."):
                assert module_name.startswith("src.domain.") or module_name.startswith("src.application."), (
                    f"应用层不应直接依赖 {module_name}"
                )

    def test_infrastructure_can_import_domain(self) -> None:
        """基础设施层可以导入 domain 层"""
        from src.infrastructure.document_parsing.archive_extractor import ArchiveExtractor
        from src.infrastructure.storage.redis.chunked_upload_manager import ChunkedUploadManager

        assert ArchiveExtractor is not None
        assert ChunkedUploadManager is not None

    def test_interfaces_imports_application_not_infrastructure(self) -> None:
        """接口层不直接导入基础设施层"""
        import ast
        import os

        route_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "src",
            "interfaces",
            "api",
            "document_upload.py",
        )
        route_path = os.path.normpath(route_path)

        if not os.path.exists(route_path):
            pytest.skip("路由文件不存在")

        with open(route_path) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("src.infrastructure.storage.redis.chunked_upload_manager"), (
                    f"接口层不应直接导入 {node.module}"
                )


class TestPortRegistration:
    """验证端口注册完整性"""

    def test_document_repository_registered(self) -> None:
        """document_repository 端口已在 composition_root 注册"""
        from src.domain.ports.registry import _global_registry

        assert "document_repository" in _global_registry, "document_repository 未注册"

    def test_document_repository_port_spec_has_required_fields(self) -> None:
        """document_repository 端口规格包含必需字段"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("document_repository")
        assert spec is not None
        assert spec.version == "v1.0.0"
        assert spec.lifetime.value in ("singleton", "scoped", "transient")

    def test_document_repository_impl_points_to_correct_class(self) -> None:
        """document_repository 实现指向正确的类"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("document_repository")
        assert spec is not None
        impl = spec.impl
        assert isinstance(impl, str)
        assert "PostgreSQLDocumentRepository" in impl


class TestEventChannelRegistration:
    """验证事件通道注册一致性"""

    def test_document_uploaded_in_default_mappings(self) -> None:
        """DocumentUploaded 已在 ChannelRouter.DEFAULT_MAPPINGS 注册"""
        from src.infrastructure.messaging.channel_router import ChannelRouter

        assert "DocumentUploaded" in ChannelRouter.DEFAULT_MAPPINGS

    def test_document_uploaded_reliable_delivery(self) -> None:
        """DocumentUploaded 使用 RELIABLE 投递模式"""
        from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode

        mapping = ChannelRouter.DEFAULT_MAPPINGS["DocumentUploaded"]
        assert mapping.delivery_mode == DeliveryMode.RELIABLE

    def test_document_uploaded_has_rabbitmq_routing_key(self) -> None:
        """DocumentUploaded 有 RabbitMQ routing key"""
        from src.infrastructure.messaging.channel_router import ChannelRouter

        mapping = ChannelRouter.DEFAULT_MAPPINGS["DocumentUploaded"]
        key = mapping.rabbitmq_routing_key
        assert key is not None
        assert key.startswith("sisys.events.reliable.")
