"""IntrusionDetectionServicePort Protocol 端口契约测试

验证入侵检测服务端口的协议定义和运行时检查行为。
"""

from __future__ import annotations

import inspect

from src.domain.ports.intrusion_detection_service import IntrusionDetectionServicePort


class TestIntrusionDetectionServiceProtocol:
    """Protocol 端口契约测试"""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol 应支持运行时检查"""
        assert hasattr(IntrusionDetectionServicePort, "_is_runtime_protocol")

    def test_protocol_has_detect_attack(self) -> None:
        """协议应定义 detect_attack 方法"""
        assert hasattr(IntrusionDetectionServicePort, "detect_attack")
        sig = inspect.signature(IntrusionDetectionServicePort.detect_attack)
        params = sig.parameters
        assert "source_ip" in params
        assert "request_data" in params
        assert "request_path" in params
        assert "user_id" in params

    def test_protocol_has_get_intrusion_stats(self) -> None:
        """协议应定义 get_intrusion_stats 方法"""
        assert hasattr(IntrusionDetectionServicePort, "get_intrusion_stats")
        sig = inspect.signature(IntrusionDetectionServicePort.get_intrusion_stats)
        assert "period_hours" in sig.parameters

    def test_protocol_has_block_ip(self) -> None:
        """协议应定义 block_ip 方法"""
        assert hasattr(IntrusionDetectionServicePort, "block_ip")
        sig = inspect.signature(IntrusionDetectionServicePort.block_ip)
        assert "ip_address" in sig.parameters
        assert "reason" in sig.parameters
        assert "duration_hours" in sig.parameters

    def test_non_conforming_class_fails_isinstance(self) -> None:
        """不符合协议的类无法通过 isinstance 检查"""

        class NonConforming:
            pass

        assert not isinstance(NonConforming(), IntrusionDetectionServicePort)

    def test_conforming_implementation_passes_isinstance(self) -> None:
        """符合协议的实现应通过 isinstance 检查"""
        from src.infrastructure.security.intrusion_detection_service_impl import (
            IntrusionDetectionServiceImpl,
        )

        impl = IntrusionDetectionServiceImpl.__new__(IntrusionDetectionServiceImpl)
        # 即使未初始化，结构类型也应匹配
        assert isinstance(impl, IntrusionDetectionServicePort)

    def test_detect_attack_return_type_hint(self) -> None:
        """detect_attack 返回类型应为 AttackDetectionResult"""
        sig = inspect.signature(IntrusionDetectionServicePort.detect_attack)
        assert sig.return_annotation is not inspect.Parameter.empty

    def test_get_intrusion_stats_return_type_hint(self) -> None:
        """get_intrusion_stats 返回类型应为 IntrusionStats"""
        sig = inspect.signature(IntrusionDetectionServicePort.get_intrusion_stats)
        assert sig.return_annotation is not inspect.Parameter.empty
