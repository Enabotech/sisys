"""Tests for DataSovereigntyService.

TDD Red phase - tests should fail before implementation.
Reference: Story 1.11 Data Sovereignty Isolation - AC-2.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.infrastructure.security.models import (
    DataResidency,
    SensitiveDataType,
)


class TestDataSovereigntyService:
    """DataSovereigntyService tests for data residency enforcement."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        from src.infrastructure.security.data_sovereignty_service import DataSovereigntyService

        return DataSovereigntyService()

    def test_get_policy_for_pii_data(self, service):
        """Should return China domestic policy for PII data."""
        policy = service.get_policy(SensitiveDataType.PII)

        assert policy is not None
        assert policy.residency_requirement == DataResidency.CHINA_DOMESTIC
        assert policy.cross_border_allowed is False

    def test_get_policy_for_trade_secret(self, service):
        """Should return strict policy for trade secrets."""
        policy = service.get_policy(SensitiveDataType.TRADE_SECRET)

        assert policy is not None
        assert policy.residency_requirement == DataResidency.CHINA_DOMESTIC
        assert policy.cross_border_allowed is False

    def test_get_policy_for_custom_data(self, service):
        """Should return global policy for custom data type."""
        policy = service.get_policy(SensitiveDataType.CUSTOM)

        assert policy is not None
        assert policy.cross_border_allowed is True

    def test_check_storage_allowed_domestic(self, service):
        """Should allow storage in China for PII."""
        result = service.check_storage_allowed(SensitiveDataType.PII, "CN")

        assert result.is_allowed is True
        assert result.violation is None

    def test_check_storage_allowed_foreign_blocked(self, service):
        """Should block storage outside China for PII."""
        result = service.check_storage_allowed(SensitiveDataType.PII, "US")

        assert result.is_allowed is False
        assert result.violation is not None
        assert "境外" in result.violation.reason or "US" in result.violation.reason

    def test_check_storage_allowed_cross_border_allowed(self, service):
        """Should allow foreign storage when cross_border_allowed is True."""
        result = service.check_storage_allowed(SensitiveDataType.CUSTOM, "US")

        assert result.is_allowed is True

    def test_select_storage_layer_domestic(self, service):
        """Should prioritize domestic storage layers."""
        layers = ["CN_REDIS", "CN_POSTGRES", "US_REDIS", "EU_POSTGRES"]

        selected = service.select_storage_layer(SensitiveDataType.PII, layers)

        assert selected in ["CN_REDIS", "CN_POSTGRES"]
        assert selected not in ["US_REDIS", "EU_POSTGRES"]

    def test_select_storage_layer_returns_none_when_blocked(self, service):
        """Should return None when no allowed layer available."""
        layers = ["US_REDIS", "EU_POSTGRES"]

        selected = service.select_storage_layer(SensitiveDataType.PII, layers)

        assert selected is None

    def test_check_cross_border_transfer_blocked(self, service):
        """Should block cross-border transfer for sensitive data without approval."""
        result = service.check_cross_border_transfer(
            data_id=uuid4(), data_type=SensitiveDataType.PII, destination="US", purpose="analysis"
        )

        assert result.is_blocked is True
        assert result.approval_required is True

    def test_check_cross_border_transfer_allowed_for_custom(self, service):
        """Should allow cross-border transfer for custom data type."""
        result = service.check_cross_border_transfer(
            data_id=uuid4(), data_type=SensitiveDataType.CUSTOM, destination="US", purpose="analysis"
        )

        assert result.is_blocked is False
        assert result.approval_required is False
