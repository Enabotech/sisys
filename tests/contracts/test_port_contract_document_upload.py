"""Story 2-1: 端口契约测试 — 文档上传相关端口

验证端口注册、版本、兼容性和接口实现。
"""

from __future__ import annotations


class TestDocumentRepositoryPortContract:
    """DocumentRepositoryPort 端口契约测试"""

    def test_port_registered_in_registry(self) -> None:
        """验证 document_repository 端口已注册到 PortRegistry"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("document_repository")
        assert spec is not None, "document_repository 端口未注册"

    def test_port_interface_is_document_repository_port(self) -> None:
        """验证端口接口类型为 DocumentRepositoryPort"""
        from src.domain.ports.document_repository import DocumentRepositoryPort
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("document_repository")
        assert spec is not None
        assert spec.interface is DocumentRepositoryPort

    def test_port_version_is_v1(self) -> None:
        """验证端口版本为 v1.0.0"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("document_repository")
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_port_lifetime_is_scoped(self) -> None:
        """验证端口生命周期为 SCOPED"""
        from src.domain.ports.registry import Lifetime, _global_registry

        spec = _global_registry.get("document_repository")
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_port_impl_is_valid_module_path(self) -> None:
        """验证 impl 字符串（延迟加载）拼写正确"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("document_repository")
        assert spec is not None
        if isinstance(spec.impl, str):
            module_path, _, class_name = spec.impl.rpartition(".")
            assert module_path, f"impl 路径无效: {spec.impl}"
            assert class_name, f"impl 类名无效: {spec.impl}"

    def test_document_repository_port_is_runtime_checkable(self) -> None:
        """验证 DocumentRepositoryPort 是 @runtime_checkable Protocol"""
        from src.domain.ports.document_repository import DocumentRepositoryPort

        assert hasattr(DocumentRepositoryPort, "__protocol_attrs__") or hasattr(DocumentRepositoryPort, "_is_protocol")

    def test_port_interface_has_required_methods(self) -> None:
        """验证端口接口包含必需的方法签名"""
        from src.domain.ports.document_repository import DocumentRepositoryPort

        required_methods = {"save", "find", "list"}
        actual_methods = {
            name
            for name in dir(DocumentRepositoryPort)
            if not name.startswith("_") and callable(getattr(DocumentRepositoryPort, name))
        }
        assert required_methods.issubset(actual_methods), f"缺少方法: {required_methods - actual_methods}"


class TestDocumentUploadedEventContract:
    """DocumentUploaded 事件契约测试"""

    def test_event_registered_in_domain_event_registry(self) -> None:
        """验证 DocumentUploaded 事件已注册到 DomainEvent._registry"""
        from src.domain.events.base import DomainEvent

        assert "DocumentUploaded" in DomainEvent._registry, "DocumentUploaded 事件未自动注册"

    def test_event_channel_configured_in_default_mappings(self) -> None:
        """验证 DocumentUploaded 事件通道已配置在 DEFAULT_MAPPINGS"""
        from src.infrastructure.messaging.channel_router import ChannelRouter

        mappings = ChannelRouter.DEFAULT_MAPPINGS
        assert "DocumentUploaded" in mappings, "DocumentUploaded 未配置在 DEFAULT_MAPPINGS"

    def test_event_channel_is_reliable(self) -> None:
        """验证 DocumentUploaded 事件通道为 RELIABLE 模式"""
        from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode

        mapping = ChannelRouter.DEFAULT_MAPPINGS.get("DocumentUploaded")
        assert mapping is not None
        assert mapping.delivery_mode == DeliveryMode.RELIABLE

    def test_event_channel_has_rabbitmq_routing_key(self) -> None:
        """验证 DocumentUploaded 事件配置了 RabbitMQ routing key"""
        from src.infrastructure.messaging.channel_router import ChannelRouter

        mapping = ChannelRouter.DEFAULT_MAPPINGS.get("DocumentUploaded")
        assert mapping is not None
        assert mapping.rabbitmq_routing_key is not None
        assert "document_uploaded" in mapping.rabbitmq_routing_key


class TestExistingPortsStillWork:
    """验证新增端口不影响已有端口"""

    def test_document_storage_port_still_registered(self) -> None:
        """验证 document_storage 端口仍然正常"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("document_storage")
        assert spec is not None

    def test_event_publisher_port_still_registered(self) -> None:
        """验证 event_publisher 端口仍然正常"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("event_publisher")
        assert spec is not None

    def test_redis_adapter_port_still_registered(self) -> None:
        """验证 redis_adapter 端口仍然正常"""
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get("redis_adapter")
        assert spec is not None
