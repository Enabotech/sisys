"""SensitiveDataDetectorPort Protocol Interface Tests."""

from __future__ import annotations

from unittest.mock import Mock

from src.domain.entities.sensitive_data_result import SensitiveDataResult, SensitiveType
from src.domain.ports.sensitive_data_detector import SensitiveDataDetectorPort


class TestSensitiveDataDetectorSignature:
    """Structural signature tests — verify Protocol contract."""

    def test_detect_sensitive_data_method_exists(self) -> None:
        """detect_sensitive_data method should exist."""
        assert hasattr(SensitiveDataDetectorPort, "detect_sensitive_data")


class TestSensitiveDataDetectorMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec constraint."""

    def test_mock_detect_sensitive_data_verified(self):
        """Mock detect_sensitive_data should be verifiable."""
        mock = Mock(spec=SensitiveDataDetectorPort)
        mock.detect_sensitive_data.return_value = SensitiveDataResult(
            source_data_hash="test",
            sensitive_types=(SensitiveType.PII,),
            confidence=0.95,
        )

        result = mock.detect_sensitive_data("test content with 110101199001011234")

        assert isinstance(result, SensitiveDataResult)
        assert result.confidence == 0.95
        assert SensitiveType.PII in result.sensitive_types
        mock.detect_sensitive_data.assert_called_once()

    def test_mock_detect_financial_data(self):
        """Mock detect_sensitive_data for financial data."""
        mock = Mock(spec=SensitiveDataDetectorPort)
        mock.detect_sensitive_data.return_value = SensitiveDataResult(
            source_data_hash="test",
            sensitive_types=(SensitiveType.FINANCIAL,),
            confidence=0.90,
        )

        result = mock.detect_sensitive_data("银行账号6222021234567890123")

        assert SensitiveType.FINANCIAL in result.sensitive_types
        mock.detect_sensitive_data.assert_called_once()

    def test_mock_detect_trade_secret(self):
        """Mock detect_sensitive_data for trade secrets."""
        mock = Mock(spec=SensitiveDataDetectorPort)
        mock.detect_sensitive_data.return_value = SensitiveDataResult(
            source_data_hash="test",
            sensitive_types=(SensitiveType.TRADE_SECRET,),
            confidence=0.85,
        )

        result = mock.detect_sensitive_data("公司核心技术配方保密")

        assert SensitiveType.TRADE_SECRET in result.sensitive_types
        mock.detect_sensitive_data.assert_called_once()
