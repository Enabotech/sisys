"""Integration tests for Data Sovereignty system.

Tests the integration between components:
- SensitiveDataDetector
- DataSovereigntyService
- WhitelistService
- ApprovalWorkflowService

Reference: Story 1.11 Data Sovereignty Isolation.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


class TestDataSovereigntyIntegration:
    """Integration tests for complete data sovereignty flow."""

    @pytest.fixture
    def detector(self):
        """Create sensitive data detector."""
        from src.infrastructure.security.sensitive_data_detector import SensitiveDataDetector

        return SensitiveDataDetector()

    @pytest.fixture
    def sovereignty_service(self):
        """Create data sovereignty service."""
        from src.infrastructure.security.data_sovereignty_service import DataSovereigntyService

        return DataSovereigntyService()

    @pytest.fixture
    def whitelist_service(self):
        """Create whitelist service."""
        from src.infrastructure.security.whitelist_service import WhitelistService

        return WhitelistService()

    @pytest.fixture
    def approval_service(self):
        """Create approval workflow service."""
        from src.infrastructure.security.approval_workflow import ApprovalWorkflowService

        return ApprovalWorkflowService()

    def test_sensitive_data_detection_and_storage_policy(self, detector, sovereignty_service):
        """Test: Detect sensitive data and apply correct storage policy."""
        # Given: Text containing PII
        text = "用户张三，身份证号110101199003074512，电话13812345678"

        # When: Detect sensitive data
        result = detector.detect(text)

        # Then: Data is marked as sensitive with correct type
        assert result.is_sensitive is True
        assert result.sensitive_type.value == "pii"

        # And: Storage policy restricts to domestic
        policy = sovereignty_service.get_policy(result.sensitive_type)
        assert policy.residency_requirement.value == "china_domestic"
        assert policy.cross_border_allowed is False

    def test_pii_storage_allowed_in_china(self, detector, sovereignty_service):
        """Test: PII can be stored in China."""
        # Given: PII data type
        from src.infrastructure.security.models import SensitiveDataType

        # When: Check if storage in China is allowed
        result = sovereignty_service.check_storage_allowed(SensitiveDataType.PII, "CN")

        # Then: Storage is allowed
        assert result.is_allowed is True

    def test_pii_storage_blocked_abroad(self, detector, sovereignty_service):
        """Test: PII storage abroad is blocked."""
        # Given: PII data type
        from src.infrastructure.security.models import SensitiveDataType

        # When: Check if storage in US is allowed
        result = sovereignty_service.check_storage_allowed(SensitiveDataType.PII, "US")

        # Then: Storage is blocked
        assert result.is_allowed is False
        assert result.violation is not None

    def test_trade_secret_detection_and_block(self, detector, sovereignty_service):
        """Test: Trade secrets are detected and stored domestically only."""
        # Given: Text containing trade secret keywords (4+ for >= 0.95 confidence)
        text = "本文件包含核心技术机密、客户名单和商业机密，请勿外传"

        # When: Detect sensitive data
        result = detector.detect(text)

        # Then: Data is marked as trade secret
        assert result.is_sensitive is True
        assert result.sensitive_type.value == "trade_secret"

        # And: Storage policy is strict
        policy = sovereignty_service.get_policy(result.sensitive_type)
        assert policy.cross_border_allowed is False

    def test_whitelist_approved_external_call(self, whitelist_service):
        """Test: External API call is allowed when whitelisted."""
        # Given: A whitelisted endpoint
        from src.infrastructure.security.models import WhitelistRule, WhitelistStatus

        rule = WhitelistRule(
            endpoint="https://api.trusted-partner.com/data",
            provider="TrustedPartner",
            purpose="Data sync",
            status=WhitelistStatus.ACTIVE,
        )
        whitelist_service.add_rule(rule)

        # When: Validate the endpoint
        result = whitelist_service.validate_endpoint("https://api.trusted-partner.com/data")

        # Then: Call is allowed
        assert result.is_allowed is True
        assert result.matched_rule_id == rule.id

    def test_whitelist_blocked_unlisted_call(self, whitelist_service):
        """Test: External API call is blocked when not whitelisted."""
        # Given: No whitelist rules

        # When: Validate an unlisted endpoint
        result = whitelist_service.validate_endpoint("https://api.untrusted.com/data")

        # Then: Call is blocked
        assert result.is_allowed is False

    def test_cross_border_approval_workflow(self, approval_service, sovereignty_service):
        """Test: Cross-border transfer requires approval."""
        # Given: Sensitive data that requires approval for cross-border
        from src.infrastructure.security.models import ApprovalStatus, SensitiveDataType

        data_id = uuid4()

        # When: Check if cross-border transfer is allowed
        check_result = sovereignty_service.check_cross_border_transfer(
            data_id=data_id, data_type=SensitiveDataType.PII, destination="US", purpose="International collaboration"
        )

        # Then: Transfer is blocked and approval is required
        assert check_result.is_blocked is True
        assert check_result.approval_required is True

        # When: Create approval request
        approval = approval_service.create_approval_request(
            data_id=data_id, destination="US", purpose="International collaboration", requester="user123"
        )

        # Then: Approval request is created with pending status
        assert approval.status == ApprovalStatus.PENDING

        # When: Approve the request
        approved = approval_service.approve(approval.id, "compliance_officer")

        # Then: Request is approved
        assert approved.status == ApprovalStatus.APPROVED

    def test_complete_data_sovereignty_flow(self, detector, sovereignty_service, whitelist_service, approval_service):
        """Test: Complete flow from detection to storage decision."""
        # Given: A document with sensitive data
        document_text = "联系人：李四，身份证号110101199501011234，机密研发资料"

        # Step 1: Detect sensitive data
        detection_result = detector.detect(document_text)
        assert detection_result.is_sensitive is True

        # Step 2: Check storage policy
        _policy = sovereignty_service.get_policy(detection_result.sensitive_type)
        assert _policy is not None

        # Step 3: Select appropriate storage layer
        available_layers = ["CN_REDIS_L1", "CN_POSTGRES_L2", "US_REDIS_L3", "EU_POSTGRES_L4"]
        selected_layer = sovereignty_service.select_storage_layer(detection_result.sensitive_type, available_layers)

        # Then: Domestic layer is selected
        assert selected_layer in ["CN_REDIS_L1", "CN_POSTGRES_L2"]
        assert selected_layer is not None

    def test_biometric_data_strict_protection(self, detector, sovereignty_service):
        """Test: Biometric data has strictest protection."""
        # Given: Text containing biometric keywords
        text = "人脸识别特征数据用于身份验证"

        # When: Detect sensitive data
        result = detector.detect(text)

        # Then: Data is marked as biometric
        assert result.is_sensitive is True
        assert result.sensitive_type.value == "biometric"

        # And: Storage policy forbids cross-border
        policy = sovereignty_service.get_policy(result.sensitive_type)
        assert policy.cross_border_allowed is False
        assert policy.residency_requirement.value == "china_domestic"

    def test_whitelist_with_expiry(self, whitelist_service):
        """Test: Whitelist rule expires correctly."""
        from datetime import UTC, datetime, timedelta

        from src.infrastructure.security.models import WhitelistRule, WhitelistStatus

        # Given: An expired whitelist rule
        expired_rule = WhitelistRule(
            endpoint="https://api.old-partner.com/data",
            provider="OldPartner",
            purpose="Legacy sync",
            status=WhitelistStatus.ACTIVE,
            expiry_date=datetime.now(UTC) - timedelta(days=1),
        )
        whitelist_service.add_rule(expired_rule)

        # When: Validate the expired endpoint
        result = whitelist_service.validate_endpoint("https://api.old-partner.com/data")

        # Then: Call is blocked due to expiry
        assert result.is_allowed is False
