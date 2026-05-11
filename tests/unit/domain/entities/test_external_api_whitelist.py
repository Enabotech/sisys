"""Tests for ExternalAPIWhitelist domain entity.

TDD Red Phase: These tests define expected behavior before implementation.
"""

from datetime import UTC, timedelta

import pytest


class TestExternalAPIWhitelistCreation:
    """Test ExternalAPIWhitelist entity creation."""

    def test_create_with_required_fields(self):
        """Test creating ExternalAPIWhitelist with required fields."""
        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist

        api = ExternalAPIWhitelist(
            endpoint="https://api.example.com",
            provider="ExampleProvider",
            region="us-east-1",
        )

        assert api.endpoint == "https://api.example.com"
        assert api.provider == "ExampleProvider"
        assert api.region == "us-east-1"
        assert api.api_id is not None
        assert api.is_verified is False
        assert api.risk_level.value == "low"

    def test_create_with_all_fields(self):
        """Test creating ExternalAPIWhitelist with all fields."""
        import uuid
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel

        custom_id = uuid.uuid4()
        now = datetime.now(UTC)
        future = now + timedelta(days=30)

        api = ExternalAPIWhitelist(
            api_id=custom_id,
            endpoint="https://api.secure.com",
            provider="SecureProvider",
            region="eu-west-1",
            is_verified=True,
            risk_level=RiskLevel.HIGH,
            valid_from=now,
            valid_until=future,
        )

        assert api.api_id == custom_id
        assert api.is_verified is True
        assert api.risk_level == RiskLevel.HIGH


class TestExternalAPIWhitelistMethods:
    """Test ExternalAPIWhitelist business methods."""

    def test_is_valid_when_verified_and_not_expired(self):
        """Test is_valid returns True when verified and not expired."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist

        api = ExternalAPIWhitelist(
            is_verified=True,
            valid_from=datetime.now(UTC) - timedelta(days=1),
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )

        assert api.is_valid() is True

    def test_is_valid_returns_false_when_not_verified(self):
        """Test is_valid returns False when not verified."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist

        api = ExternalAPIWhitelist(
            is_verified=False,
            valid_from=datetime.now(UTC) - timedelta(days=1),
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )

        assert api.is_valid() is False

    def test_is_valid_returns_false_when_expired(self):
        """Test is_valid returns False when expired."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist

        api = ExternalAPIWhitelist(
            is_verified=True,
            valid_from=datetime.now(UTC) - timedelta(days=30),
            valid_until=datetime.now(UTC) - timedelta(days=1),
        )

        assert api.is_valid() is False

    def test_is_high_risk_high_level(self):
        """Test is_high_risk returns True for HIGH risk."""
        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel

        api = ExternalAPIWhitelist(risk_level=RiskLevel.HIGH)
        assert api.is_high_risk() is True

    def test_is_high_risk_medium_level(self):
        """Test is_high_risk returns False for MEDIUM risk."""
        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel

        api = ExternalAPIWhitelist(risk_level=RiskLevel.MEDIUM)
        assert api.is_high_risk() is False

    def test_requires_dpo_approval_high_risk(self):
        """Test requires_dpo_approval returns True for high risk."""
        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel

        api = ExternalAPIWhitelist(risk_level=RiskLevel.HIGH)
        assert api.requires_dpo_approval() is True

    def test_is_expired_true(self):
        """Test is_expired returns True when past valid_until."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist

        api = ExternalAPIWhitelist(
            valid_from=datetime.now(UTC) - timedelta(days=30),
            valid_until=datetime.now(UTC) - timedelta(days=1),
        )

        assert api.is_expired() is True

    def test_is_expired_false(self):
        """Test is_expired returns False when before valid_until."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist

        api = ExternalAPIWhitelist(
            valid_from=datetime.now(UTC) - timedelta(days=1),
            valid_until=datetime.now(UTC) + timedelta(days=30),
        )

        assert api.is_expired() is False

    def test_days_until_expiry_positive(self):
        """Test days_until_expiry returns positive number when not expired."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist

        api = ExternalAPIWhitelist(
            valid_until=datetime.now(UTC) + timedelta(days=10),
        )

        assert api.days_until_expiry() >= 9

    def test_days_until_expiry_negative(self):
        """Test days_until_expiry returns negative number when expired."""
        from datetime import datetime

        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist

        api = ExternalAPIWhitelist(
            valid_until=datetime.now(UTC) - timedelta(days=5),
        )

        assert api.days_until_expiry() < 0


class TestExternalAPIWhitelistImmutability:
    """Test that ExternalAPIWhitelist is immutable."""

    def test_is_frozen_dataclass(self):
        """Test ExternalAPIWhitelist is a frozen dataclass."""
        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist

        api = ExternalAPIWhitelist()
        with pytest.raises(AttributeError):
            api.is_verified = True  # type: ignore

    def test_api_id_not_modifiable(self):
        """Test api_id cannot be modified after creation."""
        from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist

        api = ExternalAPIWhitelist()
        with pytest.raises(AttributeError):
            api.api_id = None  # type: ignore
