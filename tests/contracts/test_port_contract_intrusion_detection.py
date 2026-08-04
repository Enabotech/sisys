"""IntrusionDetectionServicePort 端口契约测试

验证 IntrusionDetectionServicePort Protocol 的结构化子类型合规性。
"""

from __future__ import annotations

import inspect

from src.domain.ports.intrusion_detection_service import IntrusionDetectionServicePort


class TestIntrusionDetectionServiceContract:
    """测试 IntrusionDetectionServicePort 端口契约"""

    def test_protocol_is_runtime_checkable(self) -> None:
        assert hasattr(IntrusionDetectionServicePort, "_is_runtime_protocol")
        assert IntrusionDetectionServicePort._is_runtime_protocol is True  # type: ignore[attr-defined]

    def test_detect_attack_method_exists(self) -> None:
        assert hasattr(IntrusionDetectionServicePort, "detect_attack")
        method = getattr(IntrusionDetectionServicePort, "detect_attack")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_get_intrusion_stats_method_exists(self) -> None:
        assert hasattr(IntrusionDetectionServicePort, "get_intrusion_stats")
        method = getattr(IntrusionDetectionServicePort, "get_intrusion_stats")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_block_ip_method_exists(self) -> None:
        assert hasattr(IntrusionDetectionServicePort, "block_ip")
        method = getattr(IntrusionDetectionServicePort, "block_ip")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_detect_attack_signature(self) -> None:
        method = getattr(IntrusionDetectionServicePort, "detect_attack")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "source_ip" in params
        assert "request_data" in params
        assert "request_path" in params
        assert "user_id" in params

    def test_get_intrusion_stats_default_period(self) -> None:
        method = getattr(IntrusionDetectionServicePort, "get_intrusion_stats")
        sig = inspect.signature(method)
        period_param = sig.parameters["period_hours"]
        assert period_param.default == 24

    def test_block_ip_signature(self) -> None:
        method = getattr(IntrusionDetectionServicePort, "block_ip")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert params == ["self", "ip_address", "reason", "duration_hours"]
        assert sig.return_annotation == "bool"

    def test_compliant_implementation(self) -> None:
        class MockDetector:
            async def detect_attack(self, source_ip: str, request_data: str, request_path: str = "", user_id: str = ""):
                return None

            async def get_intrusion_stats(self, period_hours: int = 24):
                return None

            async def block_ip(self, ip_address: str, reason: str = "", duration_hours: int = 24) -> bool:
                return True

        detector = MockDetector()
        assert isinstance(detector, IntrusionDetectionServicePort)

    def test_noncompliant_implementation_fails(self) -> None:
        class BadDetector:
            pass

        assert not isinstance(BadDetector(), IntrusionDetectionServicePort)


__all__ = ["TestIntrusionDetectionServiceContract"]
