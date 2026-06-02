"""Story 2-2a: 端口契约测试 — 文档解析端口

验证 document_parser 端口注册、版本、接口和实现完整性。
"""

from __future__ import annotations

from src.domain.ports.registry import Lifetime, _global_registry


class TestDocumentParserPortContract:
    """DocumentParserPort 端口契约测试"""

    def test_port_registered_in_registry(self) -> None:
        """验证 document_parser 端口已注册到 PortRegistry"""
        spec = _global_registry.get("document_parser")
        assert spec is not None, "document_parser 端口未注册"

    def test_port_interface_is_document_parser_port(self) -> None:
        """验证端口接口类型为 DocumentParserPort"""
        from src.domain.ports.document_parser import DocumentParserPort

        spec = _global_registry.get("document_parser")
        assert spec is not None
        assert spec.interface is DocumentParserPort

    def test_port_version_is_v1_1(self) -> None:
        """验证端口版本为 v1.1.0（扩展格式解析器注册后升级）"""
        spec = _global_registry.get("document_parser")
        assert spec is not None
        assert spec.version == "v1.1.0"

    def test_port_lifetime_is_scoped(self) -> None:
        """验证端口生命周期为 SCOPED"""
        spec = _global_registry.get("document_parser")
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED

    def test_port_owner_is_epic2(self) -> None:
        """验证端口归属为 epic-2"""
        spec = _global_registry.get("document_parser")
        assert spec is not None
        assert spec.owner == "epic-2"

    def test_port_impl_is_callable(self) -> None:
        """验证 impl 为 lambda 工厂（可调用）"""
        spec = _global_registry.get("document_parser")
        assert spec is not None
        assert callable(spec.impl), "impl 应为 lambda 工厂函数"

    def test_port_interface_has_parse_method(self) -> None:
        """验证端口接口包含 parse 方法签名"""
        from src.domain.ports.document_parser import DocumentParserPort

        required_methods = {"parse"}
        actual_methods = {
            name for name in dir(DocumentParserPort) if not name.startswith("_") and callable(getattr(DocumentParserPort, name))
        }
        assert required_methods.issubset(actual_methods), f"缺少方法: {required_methods - actual_methods}"

    def test_document_parser_port_is_runtime_checkable(self) -> None:
        """验证 DocumentParserPort 是 @runtime_checkable Protocol"""
        from src.domain.ports.document_parser import DocumentParserPort

        assert hasattr(DocumentParserPort, "__protocol_attrs__") or hasattr(DocumentParserPort, "_is_protocol")


class TestExtendedFormatMIMERouting:
    """验证扩展格式 MIME 类型已注册"""

    def test_all_15_mime_types_in_routing_table(self) -> None:
        """验证 CompositeDocumentParser 包含所有 15 种格式 MIME 映射"""
        from unittest.mock import MagicMock

        spec = _global_registry.get("document_parser")
        assert spec is not None
        assert callable(spec.impl)
        parser = spec.impl(MagicMock())
        mime_types = set(parser._parsers.keys())

        expected = {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "text/plain",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
            "text/csv",
            "image/jpeg",
            "image/png",
            "image/gif",
            "text/html",
            "text/markdown",
            "text/rtf",
        }
        missing = expected - mime_types
        assert not missing, f"CompositeDocumentParser 缺少 MIME 路由: {missing}"

    def test_unsupported_mime_returns_failed_not_exception(self) -> None:
        """验证不支持的 MIME 返回 ParsedDocument(parse_status=failed)，不抛异常"""
        from unittest.mock import MagicMock

        spec = _global_registry.get("document_parser")
        assert spec is not None
        assert callable(spec.impl)
        parser = spec.impl(MagicMock())

        result = parser.parse("/dev/null", "application/x-unknown-format")
        from src.domain.value_objects.parsed_document import ParsedDocument

        assert isinstance(result, ParsedDocument)
        assert result.parse_status == "failed"
        assert result.error_message is not None


class TestExistingDocumentPortsStillWork:
    """验证新增 document_parser 端口不影响已有文档端口"""

    def test_document_repository_still_registered(self) -> None:
        spec = _global_registry.get("document_repository")
        assert spec is not None

    def test_document_upload_service_still_registered(self) -> None:
        spec = _global_registry.get("document_upload_service")
        assert spec is not None

    def test_document_storage_still_registered(self) -> None:
        spec = _global_registry.get("document_storage")
        assert spec is not None
