"""SensitiveDataDetectorPort Protocol Interface Tests.

Protocol 测试核心原则：
- 行为验证（assert_called_...）代替结构检查（hasattr）
- 用 spec 让 mock 遵循协议契约
- 不用强制实现类，只用满足协议的 mock
- 配合静态类型检查（mypy）达到编译期安全
"""

from __future__ import annotations

from unittest.mock import Mock

from src.domain.entities.sensitive_data_result import SensitiveDataResult, SensitiveType
from src.domain.ports.sensitive_data_detector import SensitiveDataDetectorPort


class TestSensitiveDataDetectorMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec constraint.

    Mock(spec=Protocol) 创建成功即证明契约存在，无需 hasattr 检查。
    行为验证通过 assert_called_* 系列方法完成。
    """

    def test_mock_detect_sensitive_data_verified(self):
        """Mock detect_sensitive_data should be verifiable via spec constraint."""
        # spec 创建成功 = 协议契约存在（无需 hasattr 验证）
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
