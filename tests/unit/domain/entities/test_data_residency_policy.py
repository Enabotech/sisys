"""Tests for DataResidencyPolicy domain entity.

TDD Red Phase: These tests define expected behavior before implementation.
"""

import pytest


class TestDataResidencyPolicyCreation:
    """Test DataResidencyPolicy entity creation."""

    def test_create_with_required_fields(self):
        """Test creating DataResidencyPolicy with required fields."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy

        policy = DataResidencyPolicy(name="China Domestic Policy")

        assert policy.name == "China Domestic Policy"
        assert policy.policy_id is not None
        assert policy.allowed_regions == ("CHINA_DOMESTIC",)
        assert policy.blocked_regions == ("OVERSEAS",)

    def test_create_with_custom_regions(self):
        """Test creating DataResidencyPolicy with custom regions."""
        from src.domain.entities.data_residency_policy import (
            DataResidencyPolicy,
            EnforcementLevel,
            Region,
        )

        policy = DataResidencyPolicy(
            name="Multi Region Policy",
            allowed_regions=(Region.CHINA_DOMESTIC.value, Region.CHINA_HKMO.value),
            blocked_regions=(Region.OVERSEAS.value,),
            enforcement_level=EnforcementLevel.MODERATE,
        )

        assert policy.allowed_regions == ("CHINA_DOMESTIC", "CHINA_HKMO")
        assert policy.blocked_regions == ("OVERSEAS",)
        assert policy.enforcement_level == EnforcementLevel.MODERATE


class TestDataResidencyPolicyMethods:
    """Test DataResidencyPolicy business methods."""

    def test_is_allowed_region_true(self):
        """Test is_allowed_region returns True for allowed region."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, Region

        policy = DataResidencyPolicy(allowed_regions=(Region.CHINA_DOMESTIC.value, Region.CHINA_HKMO.value))

        assert policy.is_allowed_region("CHINA_DOMESTIC") is True
        assert policy.is_allowed_region("CHINA_HKMO") is True

    def test_is_allowed_region_false(self):
        """Test is_allowed_region returns False for non-allowed region."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, Region

        policy = DataResidencyPolicy(allowed_regions=(Region.CHINA_DOMESTIC.value,))

        assert policy.is_allowed_region("OVERSEAS") is False

    def test_is_blocked_region_true(self):
        """Test is_blocked_region returns True for blocked region."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, Region

        policy = DataResidencyPolicy(blocked_regions=(Region.OVERSEAS.value,))

        assert policy.is_blocked_region("OVERSEAS") is True

    def test_is_blocked_region_false(self):
        """Test is_blocked_region returns False for non-blocked region."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, Region

        policy = DataResidencyPolicy(blocked_regions=(Region.OVERSEAS.value,))

        assert policy.is_blocked_region("CHINA_DOMESTIC") is False

    def test_requires_local_processing_strict(self):
        """Test requires_local_processing returns True for STRICT level."""
        from src.domain.entities.data_residency_policy import (
            DataResidencyPolicy,
            EnforcementLevel,
        )

        policy = DataResidencyPolicy(enforcement_level=EnforcementLevel.STRICT)
        assert policy.requires_local_processing() is True

    def test_requires_local_processing_moderate(self):
        """Test requires_local_processing returns False for MODERATE level."""
        from src.domain.entities.data_residency_policy import (
            DataResidencyPolicy,
            EnforcementLevel,
        )

        policy = DataResidencyPolicy(enforcement_level=EnforcementLevel.MODERATE)
        assert policy.requires_local_processing() is False

    def test_get_policy_context(self):
        """Test get_policy_context returns correct dict."""
        from src.domain.entities.data_residency_policy import (
            DataResidencyPolicy,
            EnforcementLevel,
        )

        policy = DataResidencyPolicy(
            name="Test Policy",
            allowed_regions=("CHINA_DOMESTIC",),
            blocked_regions=("OVERSEAS",),
            enforcement_level=EnforcementLevel.STRICT,
        )

        ctx = policy.get_policy_context()
        assert ctx["name"] == "Test Policy"
        assert ctx["allowed_regions"] == ["CHINA_DOMESTIC"]
        assert ctx["blocked_regions"] == ["OVERSEAS"]
        assert ctx["enforcement_level"] == "strict"
        assert ctx["local_only"] is True


class TestDataResidencyPolicyImmutability:
    """Test that DataResidencyPolicy is immutable."""

    def test_is_frozen_dataclass(self):
        """Test DataResidencyPolicy is a frozen dataclass."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy

        policy = DataResidencyPolicy()
        with pytest.raises(AttributeError):
            policy.enforcement_level = None  # type: ignore

    def test_policy_id_not_modifiable(self):
        """Test policy_id cannot be modified after creation."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy

        policy = DataResidencyPolicy()
        with pytest.raises(AttributeError):
            policy.policy_id = None  # type: ignore
