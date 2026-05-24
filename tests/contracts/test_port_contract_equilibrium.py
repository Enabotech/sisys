"""等保2.0三级安全端口契约测试

验证等保2.0三级安全服务端口在全局注册中心正确注册，
实现类拥有所有必需方法，元数据完整

覆盖端口:
- IntrusionDetectionServicePort
- DataIntegrityServicePort
- BackupRecoveryServicePort
- StorageEncryptionServicePort
- APISecurityServicePort
- ContainerSecurityServicePort

对应 Story: 1-12-equilibrium-level-3-compliance Task 0
"""

from __future__ import annotations

from src.domain.ports.api_security_service import APISecurityServicePort
from src.domain.ports.backup_recovery_service import BackupRecoveryServicePort
from src.domain.ports.container_security_service import ContainerSecurityServicePort
from src.domain.ports.data_integrity_service import DataIntegrityServicePort
from src.domain.ports.intrusion_detection_service import IntrusionDetectionServicePort
from src.domain.ports.storage_encryption_service import StorageEncryptionServicePort


def _get_impl(spec, port_name):
    """获取端口实现实例或 None（无法解析时）"""
    impl_cls = spec.impl if isinstance(spec.impl, type) else None
    if impl_cls is None:
        try:
            from src.domain.ports.resolver import Resolver

            return Resolver().resolve(port_name)
        except (RuntimeError, ImportError, KeyError):
            return None
    return impl_cls


class TestIntrusionDetectionServicePort:
    """入侵检测服务端口契约测试"""

    PORT_NAME = "intrusion_detection_service"
    INTERFACE = IntrusionDetectionServicePort
    REQUIRED_METHODS = ["detect_attack", "get_intrusion_stats", "block_ip"]

    def test_port_is_registered(self, registry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """实现类必须拥有所有协议方法"""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec.version is not None and spec.version != "", f"{spec.name} version is empty"
        assert spec.owner is not None and spec.owner != "", f"{spec.name} owner is empty"
        assert spec.module is not None and spec.module != "", f"{spec.name} module is empty"


class TestDataIntegrityServicePort:
    """数据完整性服务端口契约测试"""

    PORT_NAME = "data_integrity_service"
    INTERFACE = DataIntegrityServicePort
    REQUIRED_METHODS = ["calculate_checksum", "verify_checksum", "verify_data_integrity"]

    def test_port_is_registered(self, registry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """实现类必须拥有所有协议方法"""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec.version is not None and spec.version != "", f"{spec.name} version is empty"
        assert spec.owner is not None and spec.owner != "", f"{spec.name} owner is empty"
        assert spec.module is not None and spec.module != "", f"{spec.name} module is empty"


class TestBackupRecoveryServicePort:
    """备份恢复服务端口契约测试"""

    PORT_NAME = "backup_recovery_service"
    INTERFACE = BackupRecoveryServicePort
    REQUIRED_METHODS = [
        "create_backup",
        "restore_backup",
        "verify_backup_integrity",
        "get_backup_status",
    ]

    def test_port_is_registered(self, registry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """实现类必须拥有所有协议方法"""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec.version is not None and spec.version != "", f"{spec.name} version is empty"
        assert spec.owner is not None and spec.owner != "", f"{spec.name} owner is empty"
        assert spec.module is not None and spec.module != "", f"{spec.name} module is empty"


class TestStorageEncryptionServicePort:
    """存储加密服务端口契约测试"""

    PORT_NAME = "storage_encryption_service"
    INTERFACE = StorageEncryptionServicePort
    REQUIRED_METHODS = ["encrypt_field", "decrypt_field", "rotate_key", "verify_encryption"]

    def test_port_is_registered(self, registry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """实现类必须拥有所有协议方法"""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec.version is not None and spec.version != "", f"{spec.name} version is empty"
        assert spec.owner is not None and spec.owner != "", f"{spec.name} owner is empty"
        assert spec.module is not None and spec.module != "", f"{spec.name} module is empty"


class TestAPISecurityServicePort:
    """API 安全服务端口契约测试"""

    PORT_NAME = "api_security_service"
    INTERFACE = APISecurityServicePort
    REQUIRED_METHODS = [
        "check_rate_limit",
        "validate_api_auth",
        "detect_injection_attack",
        "add_security_headers",
    ]

    def test_port_is_registered(self, registry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """实现类必须拥有所有协议方法"""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec.version is not None and spec.version != "", f"{spec.name} version is empty"
        assert spec.owner is not None and spec.owner != "", f"{spec.name} owner is empty"
        assert spec.module is not None and spec.module != "", f"{spec.name} module is empty"


class TestContainerSecurityServicePort:
    """容器安全服务端口契约测试"""

    PORT_NAME = "container_security_service"
    INTERFACE = ContainerSecurityServicePort
    REQUIRED_METHODS = [
        "verify_sandbox_isolation",
        "check_container_limits",
        "detect_escape_attempts",
        "validate_container_network_isolation",
    ]

    def test_port_is_registered(self, registry) -> None:
        """端口必须在全局注册中心注册"""
        spec = registry.get(self.PORT_NAME)
        assert spec is not None, f"Port {self.PORT_NAME} not registered"
        assert spec.interface is self.INTERFACE

    def test_implementation_has_required_methods(self, registry) -> None:
        """实现类必须拥有所有协议方法"""
        spec = registry.get(self.PORT_NAME)
        impl = _get_impl(spec, self.PORT_NAME)
        if impl is None:
            return
        for method in self.REQUIRED_METHODS:
            assert hasattr(impl, method), f"Implementation missing method: {method}"
            assert callable(getattr(impl, method)), f"{method} is not callable"

    def test_metadata_complete(self, registry) -> None:
        """端口元数据必须完整"""
        spec = registry.get(self.PORT_NAME)
        assert spec.version is not None and spec.version != "", f"{spec.name} version is empty"
        assert spec.owner is not None and spec.owner != "", f"{spec.name} owner is empty"
        assert spec.module is not None and spec.module != "", f"{spec.name} module is empty"
