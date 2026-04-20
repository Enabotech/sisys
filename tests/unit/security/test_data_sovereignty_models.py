"""Tests for Data Sovereignty Models.

TDD Red phase - tests should fail before implementation.
Reference: Story 1.11 Data Sovereignty Isolation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.infrastructure.security.models import (
    ApprovalStatus,
    CrossBorderApproval,
    DataResidency,
    DataSovereigntyPolicy,
    SensitiveDataType,
    SensitiveLabel,
    WhitelistRule,
    WhitelistStatus,
)


class TestSensitiveDataType:
    """SensitiveDataType enum tests."""

    def test_pii_type_exists(self):
        """Should have PII type."""
        assert SensitiveDataType.PII.value == "pii"

    def test_trade_secret_type_exists(self):
        """Should have trade secret type."""
        assert SensitiveDataType.TRADE_SECRET.value == "trade_secret"

    def test_financial_type_exists(self):
        """Should have financial type."""
        assert SensitiveDataType.FINANCIAL.value == "financial"

    def test_biometric_type_exists(self):
        """Should have biometric type for PIPL sensitive data."""
        assert SensitiveDataType.BIOMETRIC.value == "biometric"

    def test_minor_type_exists(self):
        """Should have minor type for PIPL enhanced protection."""
        assert SensitiveDataType.MINOR.value == "minor"

    def test_health_type_exists(self):
        """Should have health type."""
        assert SensitiveDataType.HEALTH.value == "health"

    def test_identity_document_type_exists(self):
        """Should have identity document type."""
        assert SensitiveDataType.IDENTITY_DOCUMENT.value == "identity_document"

    def test_custom_type_exists(self):
        """Should have custom type for user-defined sensitive types."""
        assert SensitiveDataType.CUSTOM.value == "custom"

    def test_all_types_are_string_enum(self):
        """All types should be valid string enum values."""
        for dtype in SensitiveDataType:
            assert isinstance(dtype.value, str)
            assert len(dtype.value) > 0


class TestDataResidency:
    """DataResidency enum tests."""

    def test_china_domestic_exists(self):
        """Should have China domestic residency type."""
        assert DataResidency.CHINA_DOMESTIC.value == "china_domestic"

    def test_china_border_exists(self):
        """Should have China border residency (HK/MO/TW)."""
        assert DataResidency.CHINA_BORDER.value == "china_border"

    def test_global_exists(self):
        """Should have global residency type."""
        assert DataResidency.GLOBAL.value == "global"


class TestWhitelistStatus:
    """WhitelistStatus enum tests."""

    def test_active_status_exists(self):
        """Should have active status."""
        assert WhitelistStatus.ACTIVE.value == "active"

    def test_pending_status_exists(self):
        """Should have pending status."""
        assert WhitelistStatus.PENDING.value == "pending"

    def test_revoked_status_exists(self):
        """Should have revoked status."""
        assert WhitelistStatus.REVOKED.value == "revoked"

    def test_expired_status_exists(self):
        """Should have expired status."""
        assert WhitelistStatus.EXPIRED.value == "expired"


class TestApprovalStatus:
    """ApprovalStatus enum tests."""

    def test_pending_status_exists(self):
        """Should have pending status."""
        assert ApprovalStatus.PENDING.value == "pending"

    def test_approved_status_exists(self):
        """Should have approved status."""
        assert ApprovalStatus.APPROVED.value == "approved"

    def test_rejected_status_exists(self):
        """Should have rejected status."""
        assert ApprovalStatus.REJECTED.value == "rejected"

    def test_expired_status_exists(self):
        """Should have expired status."""
        assert ApprovalStatus.EXPIRED.value == "expired"

    def test_cancelled_status_exists(self):
        """Should have cancelled status."""
        assert ApprovalStatus.CANCELLED.value == "cancelled"


class TestSensitiveLabel:
    """SensitiveLabel dataclass tests."""

    def test_sensitive_label_creation(self):
        """Should create sensitive label with default values."""
        data_id = uuid4()
        label = SensitiveLabel(data_id=data_id)

        assert label.data_id == data_id
        assert label.sensitive_type == SensitiveDataType.PII
        assert label.confidence == 1.0
        assert label.labels == []
        assert label.detection_method == "regex"

    def test_sensitive_label_with_custom_values(self):
        """Should create sensitive label with custom values."""
        data_id = uuid4()
        label = SensitiveLabel(
            data_id=data_id,
            sensitive_type=SensitiveDataType.TRADE_SECRET,
            confidence=0.95,
            labels=["confidential", "internal"],
            detection_method="keyword",
        )

        assert label.data_id == data_id
        assert label.sensitive_type == SensitiveDataType.TRADE_SECRET
        assert label.confidence == 0.95
        assert "confidential" in label.labels
        assert label.detection_method == "keyword"

    def test_sensitive_label_detected_at_auto_set(self):
        """Should auto-set detected_at timestamp."""
        before = datetime.now(UTC)
        label = SensitiveLabel()
        after = datetime.now(UTC)

        assert before <= label.detected_at <= after


class TestDataSovereigntyPolicy:
    """DataSovereigntyPolicy dataclass tests."""

    def test_policy_creation_defaults(self):
        """Should create policy with default values."""
        policy = DataSovereigntyPolicy()

        assert policy.data_type == SensitiveDataType.PII
        assert policy.residency_requirement == DataResidency.CHINA_DOMESTIC
        assert policy.cross_border_allowed is False
        assert "CN" in policy.storage_allowed

    def test_policy_allows_storage_domestic(self):
        """Should allow storage in China."""
        policy = DataSovereigntyPolicy(
            residency_requirement=DataResidency.CHINA_DOMESTIC,
            storage_allowed=["CN"],
            cross_border_allowed=False,
        )

        assert policy.allows_storage("CN") is True
        assert policy.allows_storage("US") is False

    def test_policy_allows_storage_when_cross_border_allowed(self):
        """Should allow storage in any region when cross_border_allowed is True."""
        policy = DataSovereigntyPolicy(
            residency_requirement=DataResidency.GLOBAL,
            storage_allowed=["CN", "US", "EU"],
            cross_border_allowed=True,
        )

        assert policy.allows_storage("CN") is True
        assert policy.allows_storage("US") is True
        assert policy.allows_storage("JP") is True

    def test_policy_storage_allowed_list(self):
        """Should respect storage_allowed list."""
        policy = DataSovereigntyPolicy(
            storage_allowed=["CN", "HK"],
            cross_border_allowed=False,
        )

        assert policy.allows_storage("CN") is True
        assert policy.allows_storage("HK") is True
        assert policy.allows_storage("US") is False


class TestWhitelistRule:
    """WhitelistRule dataclass tests."""

    def test_whitelist_rule_creation(self):
        """Should create whitelist rule with default values."""
        rule = WhitelistRule(
            endpoint="https://api.example.com",
            provider="ExampleAPI",
            purpose="Data sync",
        )

        assert rule.endpoint == "https://api.example.com"
        assert rule.provider == "ExampleAPI"
        assert rule.status == WhitelistStatus.ACTIVE
        assert rule.risk_level == "medium"

    def test_whitelist_rule_is_active_true(self):
        """Should be active when status is active and not expired."""
        rule = WhitelistRule(
            endpoint="https://api.example.com",
            status=WhitelistStatus.ACTIVE,
            expiry_date=datetime.now(UTC) + timedelta(days=30),
        )

        assert rule.is_active() is True

    def test_whitelist_rule_is_active_false_revoked(self):
        """Should not be active when status is revoked."""
        rule = WhitelistRule(
            endpoint="https://api.example.com",
            status=WhitelistStatus.REVOKED,
        )

        assert rule.is_active() is False

    def test_whitelist_rule_is_active_false_expired(self):
        """Should not be active when expiry_date has passed."""
        rule = WhitelistRule(
            endpoint="https://api.example.com",
            status=WhitelistStatus.ACTIVE,
            expiry_date=datetime.now(UTC) - timedelta(days=1),
        )

        assert rule.is_active() is False

    def test_whitelist_rule_is_active_true_no_expiry(self):
        """Should be active when no expiry date set."""
        rule = WhitelistRule(
            endpoint="https://api.example.com",
            status=WhitelistStatus.ACTIVE,
            expiry_date=None,
        )

        assert rule.is_active() is True

    def test_whitelist_rule_default_approved_by_empty(self):
        """Should have empty approved_by by default."""
        rule = WhitelistRule(endpoint="https://api.example.com")

        assert rule.approved_by == ""


class TestCrossBorderApproval:
    """CrossBorderApproval dataclass tests."""

    def test_approval_creation_defaults(self):
        """Should create approval with default values."""
        approval = CrossBorderApproval(
            data_id=uuid4(),
            destination="US",
            purpose="International collaboration",
            requester="user123",
        )

        assert approval.status == ApprovalStatus.PENDING
        assert approval.destination == "US"
        assert approval.requester == "user123"
        assert approval.approver == ""

    def test_approval_approve(self):
        """Should approve and set approver and timestamp."""
        approval = CrossBorderApproval(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user123",
        )

        approval.approve("compliance_officer")

        assert approval.status == ApprovalStatus.APPROVED
        assert approval.approver == "compliance_officer"
        assert approval.approved_at is not None

    def test_approval_reject(self):
        """Should reject and set approver, reason, and timestamp."""
        approval = CrossBorderApproval(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user123",
        )

        approval.reject("compliance_officer", "Policy violation")

        assert approval.status == ApprovalStatus.REJECTED
        assert approval.approver == "compliance_officer"
        assert approval.rejection_reason == "Policy violation"
        assert approval.approved_at is not None

    def test_approval_is_sla_expired_false(self):
        """Should not be expired when within SLA."""
        approval = CrossBorderApproval(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user123",
            sla_deadline=datetime.now(UTC) + timedelta(hours=24),
        )

        assert approval.is_sla_expired() is False

    def test_approval_is_sla_expired_true(self):
        """Should be expired when SLA deadline passed."""
        approval = CrossBorderApproval(
            data_id=uuid4(),
            destination="US",
            purpose="Test",
            requester="user123",
            sla_deadline=datetime.now(UTC) - timedelta(hours=1),
        )

        assert approval.is_sla_expired() is True
