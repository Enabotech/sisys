"""战略档案端口契约测试

验证 archive_repository / strategic_archive_service 端口的注册、解析和实现。
遵循项目三方法模式: test_port_is_registered + test_implementation_has_required_methods + test_metadata_complete
"""

from __future__ import annotations

import importlib

from src.domain.ports.registry import PortRegistry


def _load_impl_cls(module_path: str, cls_name: str):
    """通过模块路径和类名导入实现类"""
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name, None)


class TestArchiveRepositoryPortContract:
    """archive_repository 端口契约"""

    PORT_NAME = "archive_repository"
    IMPL_CLS_NAME = "PostgreSQLArchiveRepository"
    REQUIRED_METHODS = [
        "get_by_id",
        "save",
        "delete",
        "find",
        "list_by_plan",
        "list_by_archive_type",
        "count",
    ]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"
        from src.domain.ports.archive_repository import ArchiveRepositoryPort

        assert spec.interface is ArchiveRepositoryPort

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


class TestStrategicArchiveServicePortContract:
    """strategic_archive_service 端口契约"""

    PORT_NAME = "strategic_archive_service"
    IMPL_CLS_NAME = "StrategicArchiveService"
    REQUIRED_METHODS = [
        "archive_plan",
        "get_archive",
        "query_archive",
    ]

    def test_port_is_registered(self, registry: PortRegistry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"端口 {self.PORT_NAME} 未注册"
        from src.application.services.strategic_archive_service import StrategicArchiveService

        assert spec.interface is StrategicArchiveService

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
