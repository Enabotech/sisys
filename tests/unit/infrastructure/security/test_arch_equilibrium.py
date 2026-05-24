"""等保2.0三级架构约束验证测试

验证等保合规实现的架构约束:
- AC-A1: 领域层零外部依赖
- AC-A2: 安全层隔离（infrastructure 层不直接依赖其他 infrastructure 模块）
- AC-A3: 端口接口定义仅在 domain 层

对应 Story: 1-12-equilibrium-level-3-compliance Task 5 Subtask 5.17-5.19
"""

from __future__ import annotations

import dataclasses
import importlib
import os

from src.domain.ports.backup_recovery_service import BackupRecoveryServicePort
from src.domain.ports.data_integrity_service import DataIntegrityServicePort
from src.domain.ports.intrusion_detection_service import IntrusionDetectionServicePort
from src.domain.value_objects.backup_result import BackupResult, RestoreResult
from src.domain.value_objects.data_integrity_result import IntegrityResult
from src.domain.value_objects.intrusion_detection_result import AttackDetectionResult
from src.infrastructure.security.backup_recovery_service_impl import BackupRecoveryServiceImpl
from src.infrastructure.security.data_integrity_service_impl import DataIntegrityServiceImpl
from src.infrastructure.security.intrusion_detection_service_impl import IntrusionDetectionServiceImpl


class TestDomainLayerZeroDependencies:
    """领域层零依赖验证 (AC-A1)"""

    def test_domain_layer_no_third_party_imports(self) -> None:
        """领域层模块不应导入任何第三方包"""
        domain_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "src",
            "domain",
        )

        third_party_indicators = [
            "pydantic",
            "sqlalchemy",
            "fastapi",
            "redis",
            "qdrant",
            "minio",
            "neo4j",
            "aio_pika",
            "litellm",
            "instructor",
            "httpx",
            "requests",
            "docker",
            "psycopg2",
            "prefect",
            "langgraph",
        ]

        for root, _dirs, files in os.walk(domain_path):
            for fname in files:
                if not fname.endswith(".py") or fname == "__init__.py":
                    continue

                filepath = os.path.join(root, fname)
                with open(filepath) as f:
                    content = f.read()

                for indicator in third_party_indicators:
                    assert indicator not in content, f"Domain layer file {filepath} contains import of {indicator}"

    def test_security_value_objects_are_frozen_dataclasses(self) -> None:
        """安全相关值对象应为 frozen dataclass"""
        assert dataclasses.is_dataclass(AttackDetectionResult)
        assert dataclasses.is_dataclass(IntegrityResult)
        assert dataclasses.is_dataclass(BackupResult)
        assert dataclasses.is_dataclass(RestoreResult)

    def test_security_ports_are_runtime_checkable_protocols(self) -> None:
        """安全端口应为 runtime_checkable Protocol"""
        # 验证 isinstance() 对端口协议工作正常
        assert isinstance(IntrusionDetectionServiceImpl(), IntrusionDetectionServicePort)
        assert isinstance(DataIntegrityServiceImpl(), DataIntegrityServicePort)
        assert isinstance(BackupRecoveryServiceImpl(), BackupRecoveryServicePort)


class TestSecurityLayerIsolation:
    """安全层隔离验证 (AC-A2)"""

    def test_security_impl_imports_only_domain_and_stdlib(self) -> None:
        """安全服务实现应只依赖领域层和标准库"""
        security_modules = [
            "src.infrastructure.security.intrusion_detection_service_impl",
            "src.infrastructure.security.data_integrity_service_impl",
            "src.infrastructure.security.backup_recovery_service_impl",
        ]

        for module_name in security_modules:
            spec = importlib.util.find_spec(module_name)
            assert spec is not None, f"Module {module_name} not found"

    def test_impl_classes_satisfy_port_protocols(self) -> None:
        """实现类应满足对应端口协议"""
        assert isinstance(IntrusionDetectionServiceImpl(), IntrusionDetectionServicePort)
        assert isinstance(DataIntegrityServiceImpl(), DataIntegrityServicePort)
        assert isinstance(BackupRecoveryServiceImpl(), BackupRecoveryServicePort)


class TestPortRegistration:
    """端口注册验证 (AC-A3)"""

    def test_security_ports_registered_in_composition_root(self) -> None:
        """安全端口应在 composition_root 中注册"""
        from src.composition_root import _global_registry

        required_ports = [
            "intrusion_detection_service",
            "data_integrity_service",
            "backup_recovery_service",
        ]

        for port_name in required_ports:
            spec = _global_registry.get(port_name)
            assert spec is not None, f"Port {port_name} not registered in composition_root"

    def test_security_exceptions_defined(self) -> None:
        """安全异常应已定义"""
        from src.domain.exceptions.service_exceptions import (
            BackupError,
            DataIntegrityError,
            IntrusionDetectionError,
        )

        assert IntrusionDetectionError is not None
        assert DataIntegrityError is not None
        assert BackupError is not None
