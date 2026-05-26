"""领域层端口契约门控模块

提供端口兼容性检查与契约测试基础类
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Type

from src.domain.ports.registry import PortSpec

logger = logging.getLogger(__name__)


@dataclass
class CompatibilityResult:
    """端口版本兼容性检查结果

    Attributes:
        port_name: 端口名称
        old_version: 旧版本号
        new_version: 新版本号
        is_compatible: 是否兼容
        breaking_changes: 破坏性变更列表
        warnings: 警告列表
    """

    port_name: str
    old_version: str
    new_version: str
    is_compatible: bool
    breaking_changes: list[str]
    warnings: list[str]


class ContractGate:
    """契约兼容性检查器

    检查端口变更的兼容性，确保升级不会破坏已有功能
    """

    def check_compatibility(
        self,
        old_spec: PortSpec,
        new_spec: PortSpec,
    ) -> CompatibilityResult:
        """检查新旧端口规格的兼容性

        Args:
            old_spec: 旧版本规格
            new_spec: 新版本规格

        Returns:
            包含破坏性变更和警告的兼容性结果
        """
        breaking_changes = []
        warnings = []

        # Check interface changes
        if old_spec.interface is not new_spec.interface:
            old_methods = self._get_methods(old_spec.interface)
            new_methods = self._get_methods(new_spec.interface)

            # Check for removed methods
            for method in old_methods:
                if method not in new_methods:
                    breaking_changes.append(f"Removed method: {method}")

            # Check for changed signatures
            for method in new_methods:
                if method in old_methods:
                    old_sig = old_methods[method]
                    new_sig = new_methods[method]
                    if old_sig != new_sig:
                        breaking_changes.append(f"Changed signature: {method} ({old_sig} -> {new_sig})")

        # Check lifecycle changes
        if old_spec.lifetime != new_spec.lifetime:
            warnings.append(f"Lifetime changed: {old_spec.lifetime.value} -> {new_spec.lifetime.value}")

        return CompatibilityResult(
            port_name=old_spec.name,
            old_version=old_spec.version,
            new_version=new_spec.version,
            is_compatible=len(breaking_changes) == 0,
            breaking_changes=breaking_changes,
            warnings=warnings,
        )

    def _get_methods(self, interface: Type) -> dict[str, str]:
        """获取接口的所有方法及其签名"""
        methods = {}
        for name in dir(interface):
            if name.startswith("_"):
                continue
            obj = getattr(interface, name)
            if callable(obj) or isinstance(obj, property):
                try:
                    sig = inspect.signature(obj)
                    methods[name] = str(sig)
                except (ValueError, TypeError):
                    pass
        return methods


class PortContractTest:
    """端口契约测试基类

    所有端口实现须继承此类并实现契约测试
    """

    @classmethod
    def get_port_name(cls) -> str:
        """返回待测试的端口名称"""
        raise NotImplementedError

    @classmethod
    def get_implementation(cls) -> Any:
        """返回待测试的实现实例"""
        raise NotImplementedError

    def run_contract_tests(self) -> None:
        """运行所有契约测试

        由 CI 调用以验证实现匹配契约
        """
        port_name = self.get_port_name()
        impl = self.get_implementation()

        logger.info("Running contract tests for: %s", port_name)

        # Verify implementation exists in registry
        from src.domain.ports.registry import _global_registry

        spec = _global_registry.get(port_name)
        if spec is None:
            raise RuntimeError(f"Port not registered: {port_name}")

        # Verify implementation matches interface
        self._verify_implements_interface(impl, spec.interface)

        # Run concrete contract tests
        self.test_contract()

    def _verify_implements_interface(
        self,
        impl: Any,
        interface: Type,
    ) -> None:
        """验证实现类确实实现了接口"""
        if not isinstance(impl, interface) and not issubclass(type(impl), interface):
            raise AssertionError(f"Implementation {type(impl)} does not implement {interface}")

    def test_contract(self) -> None:
        """在子类中实现具体契约测试"""
        raise NotImplementedError
