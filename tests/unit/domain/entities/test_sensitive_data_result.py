"""Tests for SensitiveDataResult domain entity.

TDD Red Phase: These tests define expected behavior before implementation.
"""

from datetime import UTC

import pytest


class TestSensitiveDataResultCreation:
    """Test SensitiveDataResult entity creation."""

    def test_create_with_required_fields(self):
        """Test creating SensitiveDataResult with required fields."""
        from src.domain.entities.sensitive_data_result import SensitiveDataResult
        from src.domain.events.compliance_events import SensitiveType

        result = SensitiveDataResult(
            source_data_hash="abc123",
            sensitive_types=(SensitiveType.PII,),
            confidence=0.95,
        )

        assert result.source_data_hash == "abc123"
        assert result.sensitive_types == (SensitiveType.PII,)
        assert result.confidence == 0.95
        assert result.result_id is not None
        assert result.labels == ()
        assert result.detected_at is not None

    def test_create_with_all_fields(self):
        """Test creating SensitiveDataResult with all fields."""
        import uuid
        from datetime import datetime

        from src.domain.entities.sensitive_data_result import SensitiveDataResult
        from src.domain.events.compliance_events import SensitiveType

        custom_id = uuid.uuid4()
        custom_time = datetime(2026, 1, 1, tzinfo=UTC)

        result = SensitiveDataResult(
            result_id=custom_id,
            source_data_hash="hash456",
            sensitive_types=(SensitiveType.FINANCIAL, SensitiveType.TRADE_SECRET),
            confidence=0.88,
            labels=("urgent", "review"),
            detected_at=custom_time,
        )

        assert result.result_id == custom_id
        assert result.source_data_hash == "hash456"
        assert result.sensitive_types == (SensitiveType.FINANCIAL, SensitiveType.TRADE_SECRET)
        assert result.confidence == 0.88
        assert result.labels == ("urgent", "review")
        assert result.detected_at == custom_time


class TestSensitiveDataResultMethods:
    """Test SensitiveDataResult business methods."""

    def test_is_high_confidence_above_threshold(self):
        """Test is_high_confidence returns True when above threshold."""
        from src.domain.entities.sensitive_data_result import SensitiveDataResult

        result = SensitiveDataResult(confidence=0.9)
        assert result.is_high_confidence() is True

    def test_is_high_confidence_at_threshold(self):
        """Test is_high_confidence returns True when at threshold."""
        from src.domain.entities.sensitive_data_result import SensitiveDataResult

        result = SensitiveDataResult(confidence=0.8)
        assert result.is_high_confidence() is True

    def test_is_high_confidence_below_threshold(self):
        """Test is_high_confidence returns False when below threshold."""
        from src.domain.entities.sensitive_data_result import SensitiveDataResult

        result = SensitiveDataResult(confidence=0.7)
        assert result.is_high_confidence() is False

    def test_is_high_confidence_custom_threshold(self):
        """Test is_high_confidence with custom threshold."""
        from src.domain.entities.sensitive_data_result import SensitiveDataResult

        result = SensitiveDataResult(confidence=0.85)
        assert result.is_high_confidence(threshold=0.9) is False

    def test_has_type_found(self):
        """Test has_type returns True when type exists."""
        from src.domain.entities.sensitive_data_result import SensitiveDataResult
        from src.domain.events.compliance_events import SensitiveType

        result = SensitiveDataResult(sensitive_types=(SensitiveType.PII, SensitiveType.FINANCIAL))
        assert result.has_type(SensitiveType.PII) is True

    def test_has_type_not_found(self):
        """Test has_type returns False when type does not exist."""
        from src.domain.entities.sensitive_data_result import SensitiveDataResult
        from src.domain.events.compliance_events import SensitiveType

        result = SensitiveDataResult(sensitive_types=(SensitiveType.PII,))
        assert result.has_type(SensitiveType.BIOMETRIC) is False

    def test_merge_with(self):
        """Test merging two SensitiveDataResult instances."""
        from src.domain.entities.sensitive_data_result import SensitiveDataResult
        from src.domain.events.compliance_events import SensitiveType

        result1 = SensitiveDataResult(
            source_data_hash="hash1",
            sensitive_types=(SensitiveType.PII,),
            confidence=0.9,
            labels=("urgent",),
        )
        result2 = SensitiveDataResult(
            source_data_hash="hash2",
            sensitive_types=(SensitiveType.FINANCIAL,),
            confidence=0.85,
            labels=("review",),
        )

        merged = result1.merge_with(result2)

        assert merged.source_data_hash == "hash1"
        assert SensitiveType.PII in merged.sensitive_types
        assert SensitiveType.FINANCIAL in merged.sensitive_types
        assert merged.confidence == 0.9
        assert "urgent" in merged.labels
        assert "review" in merged.labels

    def test_merge_with_empty_source_hash(self):
        """Test merge uses other source_data_hash when first is empty."""
        from src.domain.entities.sensitive_data_result import SensitiveDataResult
        from src.domain.events.compliance_events import SensitiveType

        result1 = SensitiveDataResult(
            source_data_hash="",
            sensitive_types=(SensitiveType.PII,),
        )
        result2 = SensitiveDataResult(
            source_data_hash="hash2",
            sensitive_types=(SensitiveType.FINANCIAL,),
        )

        merged = result1.merge_with(result2)
        assert merged.source_data_hash == "hash2"


class TestSensitiveDataResultImmutability:
    """Test that SensitiveDataResult is immutable."""

    def test_is_frozen_dataclass(self):
        """Test SensitiveDataResult is a frozen dataclass."""
        from src.domain.entities.sensitive_data_result import SensitiveDataResult

        result = SensitiveDataResult()
        with pytest.raises(AttributeError):
            result.confidence = 0.5

    def test_result_id_not_modifiable(self):
        """Test result_id cannot be modified after creation."""
        from src.domain.entities.sensitive_data_result import SensitiveDataResult

        result = SensitiveDataResult()
        with pytest.raises(AttributeError):
            result.result_id = None
