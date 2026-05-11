"""Tests for SensitiveDataDetector service implementation.

TDD Red Phase: These tests define expected detection behavior.
"""


class TestSensitiveDataDetectorPII:
    """Test PII detection functionality."""

    def test_detect_chinese_id_card(self):
        """Test Chinese ID card number detection."""
        from src.domain.events.compliance_events import SensitiveType
        from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl

        detector = SensitiveDataDetectorImpl()
        content = "张三的身份证号是110101199001011234"
        result = detector.detect_sensitive_data(content)

        assert result is not None
        assert SensitiveType.PII in result.sensitive_types
        assert result.confidence >= 0.8

    def test_detect_phone_number(self):
        """Test Chinese phone number detection."""
        from src.domain.events.compliance_events import SensitiveType
        from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl

        detector = SensitiveDataDetectorImpl()
        content = "联系电话：13800138000"
        result = detector.detect_sensitive_data(content)

        assert result is not None
        assert SensitiveType.PII in result.sensitive_types
        assert result.confidence >= 0.8

    def test_detect_email(self):
        """Test email address detection."""
        from src.domain.events.compliance_events import SensitiveType
        from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl

        detector = SensitiveDataDetectorImpl()
        content = "邮箱是 user@example.com"
        result = detector.detect_sensitive_data(content)

        assert result is not None
        assert SensitiveType.PII in result.sensitive_types

    def test_detect_multiple_pii_types(self):
        """Test detection of multiple PII types in same content."""
        from src.domain.events.compliance_events import SensitiveType
        from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl

        detector = SensitiveDataDetectorImpl()
        content = "姓名张三，身份证110101199001011234，手机13800138000"
        result = detector.detect_sensitive_data(content)

        assert result is not None
        assert len(result.sensitive_types) >= 1
        assert SensitiveType.PII in result.sensitive_types


class TestSensitiveDataDetectorTradeSecret:
    """Test trade secret detection functionality."""

    def test_detect_trade_secret_keyword(self):
        """Test trade secret keyword detection."""
        from src.domain.events.compliance_events import SensitiveType
        from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl

        detector = SensitiveDataDetectorImpl()
        content = "公司核心技术配方是保密的"
        result = detector.detect_sensitive_data(content)

        assert result is not None
        assert SensitiveType.TRADE_SECRET in result.sensitive_types

    def test_detect_customer_list(self):
        """Test customer list as trade secret."""
        from src.domain.events.compliance_events import SensitiveType
        from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl

        detector = SensitiveDataDetectorImpl()
        content = "客户列表属于商业秘密"
        result = detector.detect_sensitive_data(content)

        assert result is not None
        assert SensitiveType.TRADE_SECRET in result.sensitive_types

    def test_detect_strategic_plan(self):
        """Test strategic plan as trade secret."""
        from src.domain.events.compliance_events import SensitiveType
        from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl

        detector = SensitiveDataDetectorImpl()
        content = "公司战略计划是最高机密"
        result = detector.detect_sensitive_data(content)

        assert result is not None
        assert SensitiveType.TRADE_SECRET in result.sensitive_types


class TestSensitiveDataDetectorFinancial:
    """Test financial data detection functionality."""

    def test_detect_bank_account(self):
        """Test bank account number detection."""
        from src.domain.events.compliance_events import SensitiveType
        from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl

        detector = SensitiveDataDetectorImpl()
        content = "银行账号是6222021234567890123"
        result = detector.detect_sensitive_data(content)

        assert result is not None
        assert SensitiveType.FINANCIAL in result.sensitive_types

    def test_detect_credit_card(self):
        """Test credit card number detection."""
        from src.domain.events.compliance_events import SensitiveType
        from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl

        detector = SensitiveDataDetectorImpl()
        content = "信用卡号：4532015112830366"
        result = detector.detect_sensitive_data(content)

        assert result is not None
        assert SensitiveType.FINANCIAL in result.sensitive_types

    def test_detect_no_false_positives_on_normal_text(self):
        """Test no false positives on normal text."""
        from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl

        detector = SensitiveDataDetectorImpl()
        content = "今天天气很好，适合出门散步。明天工作计划已安排妥当。"
        result = detector.detect_sensitive_data(content)

        assert result is not None
        assert len(result.sensitive_types) == 0


class TestSensitiveDataDetectorEdgeCases:
    """Test edge cases."""

    def test_empty_content(self):
        """Test detection on empty content."""
        from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl

        detector = SensitiveDataDetectorImpl()
        result = detector.detect_sensitive_data("")

        assert result is not None
        assert result.sensitive_types == ()

    def test_no_sensitive_data(self):
        """Test detection on content with no sensitive data."""
        from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl

        detector = SensitiveDataDetectorImpl()
        content = "今天天气很好，适合出门散步。"
        result = detector.detect_sensitive_data(content)

        assert result is not None
        assert len(result.sensitive_types) == 0

    def test_source_data_hash_generated(self):
        """Test that source_data_hash is generated."""
        from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl

        detector = SensitiveDataDetectorImpl()
        result = detector.detect_sensitive_data("test content")

        assert result.source_data_hash != ""
        assert len(result.source_data_hash) > 0
