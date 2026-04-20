"""Tests for WhitelistValidator.

TDD Red phase - tests should fail before implementation.
Reference: Story 1.11 Data Sovereignty Isolation - AC-3.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.infrastructure.security.models import WhitelistRule, WhitelistStatus


class TestWhitelistValidator:
    """WhitelistValidator tests for external call whitelist validation."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        from src.infrastructure.security.whitelist_service import WhitelistValidator

        return WhitelistValidator()

    @pytest.fixture
    def active_rule(self):
        """Create active whitelist rule."""
        return WhitelistRule(
            id=uuid4(),
            endpoint="https://api.example.com/data",
            provider="ExampleAPI",
            purpose="Data sync",
            status=WhitelistStatus.ACTIVE,
            approved_by="admin",
            expiry_date=datetime.now(UTC) + timedelta(days=30),
        )

    @pytest.fixture
    def expired_rule(self):
        """Create expired whitelist rule."""
        return WhitelistRule(
            id=uuid4(),
            endpoint="https://old-api.example.com/data",
            provider="OldAPI",
            purpose="Legacy sync",
            status=WhitelistStatus.ACTIVE,
            approved_by="admin",
            expiry_date=datetime.now(UTC) - timedelta(days=1),
        )

    @pytest.fixture
    def revoked_rule(self):
        """Create revoked whitelist rule."""
        return WhitelistRule(
            id=uuid4(),
            endpoint="https://revoked-api.example.com/data",
            provider="RevokedAPI",
            purpose="Revoked sync",
            status=WhitelistStatus.REVOKED,
            approved_by="admin",
        )

    def test_validate_allowed_endpoint(self, validator, active_rule):
        """Should allow call when endpoint matches active rule."""
        result = validator.validate("https://api.example.com/data", active_rule)

        assert result.is_allowed is True
        assert result.matched_rule_id == active_rule.id

    def test_validate_expired_rule(self, validator, expired_rule):
        """Should reject call when rule has expired."""
        result = validator.validate("https://old-api.example.com/data", expired_rule)

        assert result.is_allowed is False
        assert "expired" in result.reason.lower()

    def test_validate_revoked_rule(self, validator, revoked_rule):
        """Should reject call when rule has been revoked."""
        result = validator.validate("https://revoked-api.example.com/data", revoked_rule)

        assert result.is_allowed is False
        assert "revoked" in result.reason.lower()

    def test_validate_no_rule(self, validator):
        """Should reject when no matching rule found."""
        result = validator.validate("https://unknown-api.example.com/data")

        assert result.is_allowed is False
        assert "not in whitelist" in result.reason.lower()

    def test_validate_partial_match(self, validator, active_rule):
        """Should reject when endpoint only partially matches."""
        result = validator.validate("https://api.example.com/other", active_rule)

        # Partial path should not match
        assert result.is_allowed is False

    def test_validate_wildcard_pattern(self, validator):
        """Should support wildcard pattern matching."""
        rule = WhitelistRule(
            id=uuid4(),
            endpoint="https://*.example.com/*",
            provider="ExampleWildcard",
            purpose="Wildcard test",
            status=WhitelistStatus.ACTIVE,
        )

        result = validator.validate("https://api.example.com/data", rule)

        assert result.is_allowed is True

    def test_validate_case_insensitive(self, validator, active_rule):
        """URLs should be case insensitive per RFC 3986."""
        result = validator.validate("https://API.EXAMPLE.COM/DATA", active_rule)

        # URLs are case-insensitive for host and path
        assert result.is_allowed is True
