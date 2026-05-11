"""Tests for SensitiveDataDetectorPort interface.

TDD Red Phase: These tests define expected behavior before implementation.
"""


class TestSensitiveDataDetectorPortInterface:
    """Test SensitiveDataDetectorPort interface contract."""

    def test_detect_sensitive_data_returns_result(self):
        """Test detect_sensitive_data method exists and returns SensitiveDataResult."""
        from src.domain.entities.sensitive_data_result import SensitiveDataResult
        from src.domain.events.compliance_events import SensitiveType
        from src.domain.ports.sensitive_data_detector import SensitiveDataDetectorPort

        # Verify the interface has the required method
        assert hasattr(SensitiveDataDetectorPort, "detect_sensitive_data")

        # Create a mock implementation to test the interface contract
        class MockDetector(SensitiveDataDetectorPort):
            def detect_sensitive_data(self, content: str) -> SensitiveDataResult:
                return SensitiveDataResult(
                    source_data_hash="test",
                    sensitive_types=(SensitiveType.PII,),
                    confidence=0.95,
                )

        detector = MockDetector()
        result = detector.detect_sensitive_data("test content with 110101199001011234")

        assert isinstance(result, SensitiveDataResult)
        assert result.confidence == 0.95
        assert SensitiveType.PII in result.sensitive_types

    def test_port_is_abstract(self):
        """Test SensitiveDataDetectorPort is an abstract base class."""
        from abc import ABC

        from src.domain.ports.sensitive_data_detector import SensitiveDataDetectorPort

        assert issubclass(SensitiveDataDetectorPort, ABC)
