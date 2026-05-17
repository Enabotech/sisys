"""ContractGate 和 PortContractTest 单元测试

验证端口兼容性检查和契约测试基类的行为
"""

from __future__ import annotations

import pytest

from src.domain.ports.contract_gate import (
    CompatibilityResult,
    ContractGate,
    PortContractTest,
)
from src.domain.ports.registry import Lifetime, PortSpec


class _MockInterface:
    """用于测试的模拟接口。"""

    def method_a(self, x: int) -> str:
        """方法 A。"""
        return ""

    def method_b(self) -> int:
        """方法 B。"""
        return 0


class _MockInterfaceV2:
    """用于测试的模拟接口 V2（缺少 method_b）。"""

    def method_a(self, x: int) -> str:
        """方法 A。"""
        return ""

    def new_method(self) -> None:
        """新方法。"""
        pass


class _MockInterfaceChangedSig:
    """用于测试的模拟接口（签名变更）。"""

    def method_a(self, x: str, y: int) -> str:
        """方法 A（签名已变更）。"""
        return ""

    def method_b(self) -> int:
        """方法 B。"""
        return 0


class TestContractGateCheckCompatibility:
    """ContractGate.check_compatibility 测试。"""

    @pytest.fixture
    def gate(self) -> ContractGate:
        """创建 ContractGate 实例。"""
        return ContractGate()

    def test_identical_specs_compatible(self, gate: ContractGate) -> None:
        """相同 spec 应返回 is_compatible=True。"""
        old_spec = PortSpec(
            name="test_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockInterface,
            module="test.module",
        )
        new_spec = PortSpec(
            name="test_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockInterface,
            module="test.module",
        )
        result = gate.check_compatibility(old_spec, new_spec)
        assert result.is_compatible
        assert len(result.breaking_changes) == 0
        assert len(result.warnings) == 0

    def test_removed_method_breaking_change(self, gate: ContractGate) -> None:
        """删除方法应为破坏性变更。"""
        old_spec = PortSpec(
            name="test_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockInterface,
            module="test.module",
        )
        new_spec = PortSpec(
            name="test_port",
            version="2.0.0",
            interface=_MockInterfaceV2,
            impl=_MockInterfaceV2,
            module="test.module",
        )
        result = gate.check_compatibility(old_spec, new_spec)
        assert not result.is_compatible
        assert any("Removed method" in change for change in result.breaking_changes)

    def test_changed_signature_breaking_change(self, gate: ContractGate) -> None:
        """签名变更应为破坏性变更。"""
        old_spec = PortSpec(
            name="test_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockInterface,
            module="test.module",
        )
        new_spec = PortSpec(
            name="test_port",
            version="2.0.0",
            interface=_MockInterfaceChangedSig,
            impl=_MockInterfaceChangedSig,
            module="test.module",
        )
        result = gate.check_compatibility(old_spec, new_spec)
        assert not result.is_compatible
        assert any("Changed signature" in change for change in result.breaking_changes)

    def test_lifetime_change_warning_only(self, gate: ContractGate) -> None:
        """生命周期变更应为警告而非破坏性变更。"""
        old_spec = PortSpec(
            name="test_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockInterface,
            module="test.module",
            lifetime=Lifetime.SINGLETON,
        )
        new_spec = PortSpec(
            name="test_port",
            version="1.1.0",
            interface=_MockInterface,
            impl=_MockInterface,
            module="test.module",
            lifetime=Lifetime.SCOPED,
        )
        result = gate.check_compatibility(old_spec, new_spec)
        assert result.is_compatible
        assert len(result.breaking_changes) == 0
        assert any("Lifetime changed" in w for w in result.warnings)

    def test_result_preserves_port_name(self, gate: ContractGate) -> None:
        """结果应保留 port_name。"""
        old_spec = PortSpec(
            name="my_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockInterface,
            module="test.module",
        )
        new_spec = PortSpec(
            name="my_port",
            version="2.0.0",
            interface=_MockInterface,
            impl=_MockInterface,
            module="test.module",
        )
        result = gate.check_compatibility(old_spec, new_spec)
        assert result.port_name == "my_port"

    def test_result_preserves_versions(self, gate: ContractGate) -> None:
        """结果应保留版本信息。"""
        old_spec = PortSpec(
            name="test_port",
            version="1.0.0",
            interface=_MockInterface,
            impl=_MockInterface,
            module="test.module",
        )
        new_spec = PortSpec(
            name="test_port",
            version="2.0.0",
            interface=_MockInterface,
            impl=_MockInterface,
            module="test.module",
        )
        result = gate.check_compatibility(old_spec, new_spec)
        assert result.old_version == "1.0.0"
        assert result.new_version == "2.0.0"


class TestContractGateGetMethods:
    """ContractGate._get_methods 测试。"""

    @pytest.fixture
    def gate(self) -> ContractGate:
        """创建 ContractGate 实例。"""
        return ContractGate()

    def test_excludes_private_methods(self, gate: ContractGate) -> None:
        """应排除以 _ 开头的方法。"""
        methods = gate._get_methods(_MockInterface)
        assert "_private_method" not in methods
        assert "method_a" in methods

    def test_includes_public_methods(self, gate: ContractGate) -> None:
        """应包含公开方法。"""
        methods = gate._get_methods(_MockInterface)
        assert "method_a" in methods
        assert "method_b" in methods

    def test_signature_string_format(self, gate: ContractGate) -> None:
        """方法签名应为字符串格式。"""
        methods = gate._get_methods(_MockInterface)
        assert isinstance(methods["method_a"], str)
        assert "(x: int)" in methods["method_a"] or "x" in methods["method_a"]


class TestCompatibilityResultDataclass:
    """CompatibilityResult 数据类测试。"""

    def test_dataclass_fields(self) -> None:
        """应包含所有必需字段。"""
        result = CompatibilityResult(
            port_name="test_port",
            old_version="1.0.0",
            new_version="2.0.0",
            is_compatible=False,
            breaking_changes=["Removed method: foo"],
            warnings=["Lifetime changed"],
        )
        assert result.port_name == "test_port"
        assert result.old_version == "1.0.0"
        assert result.new_version == "2.0.0"
        assert result.is_compatible is False
        assert result.breaking_changes == ["Removed method: foo"]
        assert result.warnings == ["Lifetime changed"]


class TestPortContractTestBaseClass:
    """PortContractTest 基类测试。"""

    def test_get_port_name_not_implemented(self) -> None:
        """基类 get_port_name 应抛出 NotImplementedError。"""
        with pytest.raises(NotImplementedError):
            PortContractTest.get_port_name()

    def test_get_implementation_not_implemented(self) -> None:
        """基类 get_implementation 应抛出 NotImplementedError。"""
        with pytest.raises(NotImplementedError):
            PortContractTest.get_implementation()

    def test_test_contract_not_implemented(self) -> None:
        """基类 test_contract 应抛出 NotImplementedError。"""
        instance = PortContractTest()
        with pytest.raises(NotImplementedError):
            instance.test_contract()

    def test_verify_implements_interface_success(self) -> None:
        """实现类应通过接口验证。"""
        instance = PortContractTest()

        class _Impl(_MockInterface):
            def method_a(self, x: int) -> str:
                return str(x)

            def method_b(self) -> int:
                return 0

        impl = _Impl()
        instance._verify_implements_interface(impl, _MockInterface)

    def test_verify_implements_interface_failure(self) -> None:
        """非实现类应抛出 AssertionError。"""
        instance = PortContractTest()

        class _OtherClass:
            pass

        other = _OtherClass()
        with pytest.raises(AssertionError, match="does not implement"):
            instance._verify_implements_interface(other, _MockInterface)
