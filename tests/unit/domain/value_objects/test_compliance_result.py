"""Tests for ComplianceResult value object.

TDD Red Phase: These tests define expected behavior before implementation.
"""


class TestComplianceResultCreation:
    """Test ComplianceResult value object creation."""

    def test_create_allowed_result(self):
        """Test creating an allowed compliance result."""
        from src.domain.value_objects.compliance_result import ComplianceResult

        result = ComplianceResult(
            allowed=True,
            reason="All checks passed",
            forced_local=False,
        )

        assert result.allowed is True
        assert result.reason == "All checks passed"
        assert result.forced_local is False
        assert result.violation_type is None

    def test_create_denied_result(self):
        """Test creating a denied compliance result."""
        from src.domain.value_objects.compliance_result import ComplianceResult

        result = ComplianceResult(
            allowed=False,
            reason="Data sovereignty violation",
            forced_local=True,
            violation_type="unauthorized_transfer",
        )

        assert result.allowed is False
        assert result.reason == "Data sovereignty violation"
        assert result.forced_local is True
        assert result.violation_type == "unauthorized_transfer"


class TestComplianceResultMethods:
    """Test ComplianceResult business methods."""

    def test_is_allowed_true(self):
        """Test is_allowed returns True when allowed."""
        from src.domain.value_objects.compliance_result import ComplianceResult

        result = ComplianceResult(allowed=True)
        assert result.is_allowed() is True

    def test_is_allowed_false(self):
        """Test is_allowed returns False when denied."""
        from src.domain.value_objects.compliance_result import ComplianceResult

        result = ComplianceResult(allowed=False)
        assert result.is_allowed() is False

    def test_is_violation_true(self):
        """Test is_violation returns True when violation_type is set."""
        from src.domain.value_objects.compliance_result import ComplianceResult

        result = ComplianceResult(
            allowed=False,
            violation_type="unauthorized_transfer",
        )
        assert result.is_violation() is True

    def test_is_violation_false(self):
        """Test is_violation returns False when violation_type is None."""
        from src.domain.value_objects.compliance_result import ComplianceResult

        result = ComplianceResult(allowed=True)
        assert result.is_violation() is False

    def test_get_violation_type_with_violation(self):
        """Test get_violation_type returns type when violation exists."""
        from src.domain.value_objects.compliance_result import ComplianceResult

        result = ComplianceResult(
            allowed=False,
            violation_type="data_exfiltration",
        )
        assert result.get_violation_type() == "data_exfiltration"

    def test_get_violation_type_without_violation(self):
        """Test get_violation_type returns None when no violation."""
        from src.domain.value_objects.compliance_result import ComplianceResult

        result = ComplianceResult(allowed=True)
        assert result.get_violation_type() is None
