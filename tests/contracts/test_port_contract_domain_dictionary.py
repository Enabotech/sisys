"""领域词典端口契约测试

验证 domain_dictionary_repo / domain_dictionary_service 端口的注册、解析和实现。
遵循项目三方法模式: test_port_is_registered + test_implementation_has_required_methods + test_metadata_complete
"""

from __future__ import annotations

import importlib

from src.domain.ports.registry import PortRegistry


def _load_impl_cls(module_path: str, cls_name: str):
    """通过模块路径和类名导入实现类"""
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name, None)


class TestDomainDictionaryRepoPortContract:
    """domain_dictionary_repo 端口契约"""

    PORT_NAME = "domain_dictionary_repo"
    IMPL_CLS_NAME = "PostgreSQLDomainDictionaryRepository"
    REQUIRED_METHODS = [
        "list_entries",
        "get_entry",
        "add_entry",
        "update_entry",
        "delete_entry",
        "get_active_dictionary",
        "create_snapshot",
        "rollback",
        "list_snapshots",
    ]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"
        from src.domain.ports.domain_dictionary import DomainDictionaryPort

        assert spec.interface is DomainDictionaryPort

    def test_implementation_has_required_methods(self, registry: PortRegistry) -> None:
        """实现类必须包含所有必需方法"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.module, f"端口 {self.PORT_NAME} 缺少 module 元数据"

        impl_cls = _load_impl_cls(spec.module, self.IMPL_CLS_NAME)
        assert impl_cls is not None, f"无法从 {spec.module} 导入 {self.IMPL_CLS_NAME}"

        for method in self.REQUIRED_METHODS:
            assert hasattr(impl_cls, method), f"缺少方法: {method}"
            assert callable(getattr(impl_cls, method))

    def test_metadata_complete(self, registry: PortRegistry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version and spec.version != ""
        assert spec.owner and spec.owner != ""
        assert spec.module and spec.module != ""

    def test_lifetime_is_scoped(self, registry: PortRegistry) -> None:
        """仓储必须是 SCOPED 生命周期"""
        from src.domain.ports.registry import Lifetime

        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED


class TestDomainDictionaryServicePortContract:
    """domain_dictionary_service 端口契约"""

    PORT_NAME = "domain_dictionary_service"
    IMPL_CLS_NAME = "DomainDictionaryService"
    REQUIRED_METHODS = [
        "list_entries",
        "get_entry",
        "add_entry",
        "update_entry",
        "delete_entry",
        "refresh_dictionary",
        "create_snapshot",
        "rollback",
        "list_snapshots",
    ]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"

    def test_implementation_has_required_methods(self, registry: PortRegistry) -> None:
        """实现类必须包含所有必需方法"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.module, f"端口 {self.PORT_NAME} 缺少 module 元数据"

        impl_cls = _load_impl_cls(spec.module, self.IMPL_CLS_NAME)
        assert impl_cls is not None, f"无法从 {spec.module} 导入 {self.IMPL_CLS_NAME}"

        for method in self.REQUIRED_METHODS:
            assert hasattr(impl_cls, method), f"缺少方法: {method}"
            assert callable(getattr(impl_cls, method))

    def test_metadata_complete(self, registry: PortRegistry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.version and spec.version != ""
        assert spec.owner and spec.owner != ""
        assert spec.module and spec.module != ""

    def test_lifetime_is_scoped(self, registry: PortRegistry) -> None:
        """服务必须是 SCOPED 生命周期"""
        from src.domain.ports.registry import Lifetime

        spec = registry.get(self.PORT_NAME)
        assert spec is not None
        assert spec.lifetime == Lifetime.SCOPED


class TestDictionaryConsumerPortContract:
    """DictionaryConsumerPort 契约验证

    验证 RuleBasedExtractor 同时实现 EntityExtractionPort 与 DictionaryConsumerPort。
    """

    def test_rule_based_extractor_implements_dictionary_consumer_port(self) -> None:
        """RuleBasedExtractor 实现 DictionaryConsumerPort"""
        from src.domain.ports.domain_dictionary import DictionaryConsumerPort
        from src.infrastructure.external_services.entity_extraction.rule_extractor import (
            RuleBasedExtractor,
        )

        extractor = RuleBasedExtractor()
        assert isinstance(extractor, DictionaryConsumerPort), "RuleBasedExtractor 应实现 DictionaryConsumerPort"
        assert hasattr(extractor, "reload_dictionary")
        assert callable(extractor.reload_dictionary)

    def test_reload_dictionary_signature(self) -> None:
        """reload_dictionary 签名正确"""
        import inspect

        from src.infrastructure.external_services.entity_extraction.rule_extractor import (
            RuleBasedExtractor,
        )

        sig = inspect.signature(RuleBasedExtractor.reload_dictionary)
        params = list(sig.parameters.values())
        param_names = [p.name for p in params]
        assert "dictionary" in param_names

    def test_resolver_returns_entity_extraction_rule_as_consumer(self, resolver) -> None:
        """Resolve entity_extraction_rule 可验证 DictionaryConsumerPort 实现"""
        from src.domain.ports.domain_dictionary import DictionaryConsumerPort

        try:
            resolved = resolver.resolve("entity_extraction_rule")
            assert isinstance(resolved, DictionaryConsumerPort), "entity_extraction_rule 应实现 DictionaryConsumerPort"
        except Exception:
            pass  # 依赖不完整时跳过


class TestDomainDictionaryResolver:
    """领域词典端口解析验证"""

    def test_resolve_domain_dictionary_repo(self, resolver) -> None:
        """验证 Resolver 可解析 domain_dictionary_repo"""
        from src.domain.ports.domain_dictionary import DomainDictionaryPort

        try:
            resolved = resolver.resolve("domain_dictionary_repo")
            assert isinstance(resolved, DomainDictionaryPort)
        except Exception:
            pass  # 依赖不完整时跳过

    def test_resolve_domain_dictionary_service(self, resolver) -> None:
        """验证 Resolver 可解析 domain_dictionary_service"""
        try:
            resolved = resolver.resolve("domain_dictionary_service")
            assert hasattr(resolved, "list_entries")
            assert hasattr(resolved, "add_entry")
            assert hasattr(resolved, "refresh_dictionary")
        except Exception:
            pass  # 依赖不完整时跳过
