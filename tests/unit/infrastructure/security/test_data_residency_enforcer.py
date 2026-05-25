"""Tests for DataResidencyEnforcer service implementation.

TDD Red Phase: These tests define expected behavior for data residency enforcement.
"""


class TestDataResidencyEnforcer:
    """Test DataResidencyEnforcer service functionality."""

    def test_enforce_residency_domestic_allowed(self):
        """Test enforcement allows domestic region."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, EnforcementLevel, Region
        from src.infrastructure.security.data_residency_enforcer_impl import DataResidencyEnforcerImpl

        enforcer = DataResidencyEnforcerImpl()
        policy = DataResidencyPolicy(
            name="China Policy",
            allowed_regions=(Region.CHINA_DOMESTIC.value,),
            blocked_regions=(Region.OVERSEAS.value,),
            enforcement_level=EnforcementLevel.STRICT,
        )

        result = enforcer.enforce_residency("sensitive data", Region.CHINA_DOMESTIC.value, policy)
        assert result is True

    def test_enforce_residency_overseas_blocked(self):
        """Test enforcement blocks overseas region when STRICT."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, EnforcementLevel, Region
        from src.infrastructure.security.data_residency_enforcer_impl import DataResidencyEnforcerImpl

        enforcer = DataResidencyEnforcerImpl()
        policy = DataResidencyPolicy(
            name="China Policy",
            allowed_regions=(Region.CHINA_DOMESTIC.value,),
            blocked_regions=(Region.OVERSEAS.value,),
            enforcement_level=EnforcementLevel.STRICT,
        )

        result = enforcer.enforce_residency("sensitive data", Region.OVERSEAS.value, policy)
        assert result is False

    def test_enforce_residency_moderate_allows_with_approval(self):
        """Test MODERATE level allows overseas with proper approval context."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, EnforcementLevel, Region
        from src.infrastructure.security.data_residency_enforcer_impl import DataResidencyEnforcerImpl

        enforcer = DataResidencyEnforcerImpl()
        policy = DataResidencyPolicy(
            name="Moderate Policy",
            allowed_regions=(Region.CHINA_DOMESTIC.value, Region.CHINA_HKMO.value),
            blocked_regions=(Region.OVERSEAS.value,),
            enforcement_level=EnforcementLevel.MODERATE,
        )

        # MODERATE level should allow with approval context
        result = enforcer.enforce_residency("data", Region.CHINA_HKMO.value, policy)
        assert result is True

    def test_check_violation_no_violation(self):
        """Test check_violation returns False when no violation."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, EnforcementLevel, Region
        from src.infrastructure.security.data_residency_enforcer_impl import DataResidencyEnforcerImpl

        enforcer = DataResidencyEnforcerImpl()
        policy = DataResidencyPolicy(
            allowed_regions=(Region.CHINA_DOMESTIC.value,),
            blocked_regions=(Region.OVERSEAS.value,),
            enforcement_level=EnforcementLevel.STRICT,
        )

        has_violation = enforcer.check_violation(
            target_region=Region.CHINA_DOMESTIC.value,
            policy=policy,
        )
        assert has_violation is False

    def test_check_violation_detected(self):
        """Test check_violation returns True when violation detected."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, EnforcementLevel, Region
        from src.infrastructure.security.data_residency_enforcer_impl import DataResidencyEnforcerImpl

        enforcer = DataResidencyEnforcerImpl()
        policy = DataResidencyPolicy(
            allowed_regions=(Region.CHINA_DOMESTIC.value,),
            blocked_regions=(Region.OVERSEAS.value,),
            enforcement_level=EnforcementLevel.STRICT,
        )

        has_violation = enforcer.check_violation(
            target_region=Region.OVERSEAS.value,
            policy=policy,
        )
        assert has_violation is True


class TestDataResidencyEnforcerIntegration:
    """Integration tests for DataResidencyEnforcer with UDMR."""

    def test_strict_policy_forces_local_processing(self):
        """Test STRICT policy forces local processing."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, EnforcementLevel
        from src.infrastructure.security.data_residency_enforcer_impl import DataResidencyEnforcerImpl

        enforcer = DataResidencyEnforcerImpl()
        policy = DataResidencyPolicy(
            name="Strict China Only",
            enforcement_level=EnforcementLevel.STRICT,
        )

        assert policy.requires_local_processing() is True

        # Even if UDMR tries to route overseas, strict policy should block
        result = enforcer.enforce_residency("data", "OVERSEAS", policy)
        assert result is False

    def test_policy_context_for_udmr(self):
        """Test policy context is correctly formatted for UDMR."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, EnforcementLevel

        policy = DataResidencyPolicy(
            name="Test Policy",
            enforcement_level=EnforcementLevel.STRICT,
        )

        ctx = policy.get_policy_context()
        assert "policy_id" in ctx
        assert "local_only" in ctx
        assert ctx["local_only"] is True


class TestDataResidencyEnforcerBranches:
    """DataResidencyEnforcer 未覆盖分支测试"""

    def test_enforce_residency_moderate_unknown_region(self):
        """Test MODERATE level allows unknown region."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, EnforcementLevel, Region
        from src.infrastructure.security.data_residency_enforcer_impl import DataResidencyEnforcerImpl

        enforcer = DataResidencyEnforcerImpl()
        policy = DataResidencyPolicy(
            name="Moderate Policy",
            allowed_regions=(Region.CHINA_DOMESTIC.value,),
            blocked_regions=(Region.OVERSEAS.value,),
            enforcement_level=EnforcementLevel.MODERATE,
        )

        result = enforcer.enforce_residency("data", "UNKNOWN_REGION", policy)
        assert result is True

    def test_enforce_residency_permissive_unknown_region(self):
        """Test PERMISSIVE level allows unknown region."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, EnforcementLevel, Region
        from src.infrastructure.security.data_residency_enforcer_impl import DataResidencyEnforcerImpl

        enforcer = DataResidencyEnforcerImpl()
        policy = DataResidencyPolicy(
            name="Permissive Policy",
            allowed_regions=(Region.CHINA_DOMESTIC.value,),
            blocked_regions=(),
            enforcement_level=EnforcementLevel.PERMISSIVE,
        )

        result = enforcer.enforce_residency("data", "SOME_OTHER_REGION", policy)
        assert result is True

    def test_check_violation_moderate_blocked_region(self):
        """Test MODERATE level blocked region returns True."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, EnforcementLevel, Region
        from src.infrastructure.security.data_residency_enforcer_impl import DataResidencyEnforcerImpl

        enforcer = DataResidencyEnforcerImpl()
        policy = DataResidencyPolicy(
            name="Moderate Policy",
            allowed_regions=(Region.CHINA_DOMESTIC.value,),
            blocked_regions=(Region.OVERSEAS.value,),
            enforcement_level=EnforcementLevel.MODERATE,
        )

        result = enforcer.check_violation(Region.OVERSEAS.value, policy)
        assert result is True

    def test_check_violation_permissive_blocked_region(self):
        """Test PERMISSIVE level blocked region returns True."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, EnforcementLevel, Region
        from src.infrastructure.security.data_residency_enforcer_impl import DataResidencyEnforcerImpl

        enforcer = DataResidencyEnforcerImpl()
        policy = DataResidencyPolicy(
            name="Permissive Policy",
            allowed_regions=(Region.CHINA_DOMESTIC.value,),
            blocked_regions=(Region.OVERSEAS.value,),
            enforcement_level=EnforcementLevel.PERMISSIVE,
        )

        result = enforcer.check_violation(Region.OVERSEAS.value, policy)
        assert result is True

    def test_check_violation_permissive_unknown_region(self):
        """Test PERMISSIVE level unknown region returns False (no violation)."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, EnforcementLevel, Region
        from src.infrastructure.security.data_residency_enforcer_impl import DataResidencyEnforcerImpl

        enforcer = DataResidencyEnforcerImpl()
        policy = DataResidencyPolicy(
            name="Permissive Policy",
            allowed_regions=(Region.CHINA_DOMESTIC.value,),
            blocked_regions=(),
            enforcement_level=EnforcementLevel.PERMISSIVE,
        )

        result = enforcer.check_violation("RANDOM_REGION", policy)
        assert result is False

    def test_enforce_residency_strict_unknown_region(self):
        """Test STRICT level unknown region returns False."""
        from src.domain.entities.data_residency_policy import DataResidencyPolicy, EnforcementLevel, Region
        from src.infrastructure.security.data_residency_enforcer_impl import DataResidencyEnforcerImpl

        enforcer = DataResidencyEnforcerImpl()
        policy = DataResidencyPolicy(
            name="Strict Policy",
            allowed_regions=(Region.CHINA_DOMESTIC.value,),
            blocked_regions=(Region.OVERSEAS.value,),
            enforcement_level=EnforcementLevel.STRICT,
        )

        result = enforcer.enforce_residency("data", "UNKNOWN_REGION", policy)
        assert result is False
