"""Whitelist Service and Validator.

Implements external API call whitelist validation and management.
Reference: Story 1.11 Data Sovereignty Isolation - AC-3.

Architecture: Infrastructure layer service (hexagonal architecture).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from .models import WhitelistRule, WhitelistStatus

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..config.sovereignty import DataSovereigntyConfig


@dataclass
class ValidationResult:
    """Result of whitelist validation.

    Attributes:
        is_allowed: Whether the endpoint is allowed.
        matched_rule_id: ID of matched rule if applicable.
        reason: Reason for allow/deny.
    """

    is_allowed: bool
    matched_rule_id: UUID | None = None
    reason: str | None = None


class WhitelistValidator:
    """Validator for external API call whitelist.

    Validates whether an external API endpoint is allowed based on
    the whitelist rules configuration.
    """

    def __init__(self, config: DataSovereigntyConfig | None = None) -> None:
        """Initialize validator with configuration.

        Args:
            config: Data sovereignty configuration.
        """
        from ..config.sovereignty import get_sovereignty_config

        self._config = config or get_sovereignty_config()

    def validate(
        self,
        endpoint: str,
        rule: WhitelistRule | None = None,
    ) -> ValidationResult:
        """Validate if an endpoint is allowed.

        Args:
            endpoint: External API endpoint URL.
            rule: Whitelist rule to validate against (if provided).

        Returns:
            ValidationResult with validation results.
        """
        # If no rule provided, endpoint is not in whitelist
        if rule is None:
            return ValidationResult(
                is_allowed=False,
                reason="Endpoint not in whitelist",
            )

        # Check if rule is active (includes status and expiry check)
        if not rule.is_active():
            if rule.status == WhitelistStatus.REVOKED:
                return ValidationResult(
                    is_allowed=False,
                    matched_rule_id=rule.id,
                    reason="Whitelist rule has been revoked",
                )
            elif rule.status == WhitelistStatus.PENDING:
                return ValidationResult(
                    is_allowed=False,
                    matched_rule_id=rule.id,
                    reason="Whitelist rule is pending approval",
                )
            else:
                # Rule is expired (is_active returned False but status is ACTIVE)
                return ValidationResult(
                    is_allowed=False,
                    matched_rule_id=rule.id,
                    reason="Whitelist rule has expired",
                )

        # Check endpoint pattern match
        if not self._matches_pattern(endpoint, rule.endpoint):
            return ValidationResult(
                is_allowed=False,
                matched_rule_id=rule.id,
                reason="Endpoint does not match whitelist pattern",
            )

        return ValidationResult(
            is_allowed=True,
            matched_rule_id=rule.id,
            reason="Endpoint is in whitelist",
        )

    def _matches_pattern(self, endpoint: str, pattern: str) -> bool:
        """Check if endpoint matches the whitelist pattern.

        Supports:
        - Exact match (case-insensitive for URL host and path)
        - Wildcard (*) matching any characters
        - Glob-style patterns (e.g., *.example.com)

        Args:
            endpoint: Endpoint URL to check.
            pattern: Whitelist pattern.

        Returns:
            True if endpoint matches pattern.
        """
        # Normalize URLs for comparison
        endpoint_normalized = self._normalize_url(endpoint)
        pattern_normalized = self._normalize_url(pattern)

        # Direct match (case-insensitive for URLs)
        if endpoint_normalized.lower() == pattern_normalized.lower():
            return True

        # Wildcard pattern matching
        if "*" in pattern_normalized:
            # Convert glob pattern to regex (case-insensitive)
            regex_pattern = self._glob_to_regex(pattern_normalized)
            try:
                return bool(re.match(regex_pattern, endpoint_normalized, re.IGNORECASE))
            except re.error:
                return False

        return False

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison (case-insensitive).

        Args:
            url: URL to normalize.

        Returns:
            Normalized URL string.
        """
        # Remove trailing slash
        url = url.rstrip("/")

        # Remove protocol for comparison (http/https)
        if url.startswith("https://"):
            url = url[8:]
        elif url.startswith("http://"):
            url = url[7:]

        # Remove www prefix
        if url.startswith("www."):
            url = url[4:]

        # Remove port number (e.g., :443, :8080)
        if ":" in url:
            url = url.split(":")[0]

        return url

    def _glob_to_regex(self, pattern: str) -> str:
        """Convert glob-style pattern to regex.

        Args:
            pattern: Glob pattern with * and ? wildcards.

        Returns:
            Regex pattern string.
        """
        # Escape special regex characters except * and ?
        escaped = re.escape(pattern)
        # Convert * to .* for regex (match any characters)
        escaped = escaped.replace(r"\*", ".*")
        # Convert ? to . for regex (match single character)
        escaped = escaped.replace(r"\?", ".")
        return f"^{escaped}$"


class WhitelistService:
    """Service for managing whitelist rules.

    Provides CRUD operations for whitelist rule management.
    """

    def __init__(self, config: DataSovereigntyConfig | None = None) -> None:
        """Initialize service with configuration.

        Args:
            config: Data sovereignty configuration.
        """
        from ..config.sovereignty import get_sovereignty_config

        self._config = config or get_sovereignty_config()
        self._validator = WhitelistValidator(config)
        self._rules: dict[UUID, WhitelistRule] = {}

    @property
    def validator(self) -> WhitelistValidator:
        """Get the whitelist validator.

        Returns:
            WhitelistValidator instance.
        """
        return self._validator

    def add_rule(
        self,
        rule: WhitelistRule | None = None,
        endpoint: str = "",
        provider: str = "",
        purpose: str = "",
        risk_level: str = "medium",
        status: str = "pending",
    ) -> WhitelistRule:
        """Add a new whitelist rule.

        Can be called with a WhitelistRule object or with individual parameters.

        Args:
            rule: Whitelist rule to add.
            endpoint: External API endpoint URL pattern.
            provider: Service provider name.
            purpose: Purpose/description of the external call.
            risk_level: Risk level (low, medium, high, critical).
            status: Initial rule status.

        Returns:
            Added rule.

        Raises:
            ValueError: If max rules limit reached or no rule/parameters provided.
        """
        if rule is None:
            if not endpoint:
                raise ValueError("Either rule or endpoint must be provided")
            from uuid import uuid4

            rule = WhitelistRule(
                id=uuid4(),
                endpoint=endpoint,
                provider=provider,
                purpose=purpose,
                risk_level=risk_level,
                status=WhitelistStatus(status),
            )

        if len(self._rules) >= self._config.whitelist_max_rules:
            raise ValueError(f"Maximum whitelist rules limit ({self._config.whitelist_max_rules}) reached")

        self._rules[rule.id] = rule
        return rule

    def get_rule(self, rule_id: UUID) -> WhitelistRule | None:
        """Get a whitelist rule by ID.

        Args:
            rule_id: Rule ID.

        Returns:
            WhitelistRule if found, None otherwise.
        """
        return self._rules.get(rule_id)

    def revoke_rule(self, rule_id: UUID, reason: str = "") -> bool:
        """Revoke a whitelist rule.

        Args:
            rule_id: Rule ID to revoke.
            reason: Revocation reason.

        Returns:
            True if rule was revoked, False if not found.
        """
        rule = self._rules.get(rule_id)
        if rule is None:
            return False

        rule.status = WhitelistStatus.REVOKED
        return True

    def list_rules(
        self,
        status: WhitelistStatus | str | None = None,
    ) -> list[WhitelistRule]:
        """List whitelist rules with optional status filter.

        Args:
            status: Filter by rule status (WhitelistStatus or string).

        Returns:
            List of matching rules.
        """
        rules = list(self._rules.values())

        if status is not None:
            if isinstance(status, str):
                status = WhitelistStatus(status)
            rules = [r for r in rules if r.status == status]

        return rules

    def validate_endpoint(self, endpoint: str) -> ValidationResult:
        """Validate an endpoint against all active rules.

        Args:
            endpoint: Endpoint URL to validate.

        Returns:
            ValidationResult with validation results.
        """
        active_rules = self.list_rules(status=WhitelistStatus.ACTIVE)

        for rule in active_rules:
            result = self._validator.validate(endpoint, rule)
            if result.is_allowed:
                return result

        return ValidationResult(
            is_allowed=False,
            reason="Endpoint not in whitelist",
        )

    def validate_call(self, endpoint: str) -> bool:
        """Validate an endpoint call (returns bool for convenience).

        Args:
            endpoint: Endpoint URL to validate.

        Returns:
            True if call is allowed, False otherwise.
        """
        result = self.validate_endpoint(endpoint)
        # AC-3: All whitelist validations must be logged for audit
        # TODO(V2): Integrate with AuditService for structured audit logging
        logger.info(
            "Whitelist validation: endpoint=%s, allowed=%s, rule_id=%s, reason=%s",
            endpoint,
            result.is_allowed,
            result.matched_rule_id,
            result.reason,
        )
        return result.is_allowed

    def get_coverage_report(self) -> dict:
        """Get whitelist coverage statistics report.

        Returns:
            Dict with coverage statistics.
        """
        all_rules = list(self._rules.values())
        active_rules = [r for r in all_rules if r.status == WhitelistStatus.ACTIVE]

        return {
            "total_rules": len(all_rules),
            "active_rules": len(active_rules),
            "pending_rules": len([r for r in all_rules if r.status == WhitelistStatus.PENDING]),
            "expired_rules": len([r for r in all_rules if r.status == WhitelistStatus.EXPIRED]),
            "revoked_rules": len([r for r in all_rules if r.status == WhitelistStatus.REVOKED]),
            "coverage_percentage": len(active_rules) / len(all_rules) if all_rules else 1.0,
        }

    def add_rule_by_params(
        self,
        endpoint: str,
        provider: str,
        purpose: str,
        risk_level: str = "medium",
        status: str = "pending",
    ) -> WhitelistRule:
        """Add a new whitelist rule by parameters.

        Convenience method to create and add a rule in one call.

        Args:
            endpoint: External API endpoint URL pattern.
            provider: Service provider name.
            purpose: Purpose/description of the external call.
            risk_level: Risk level (low, medium, high, critical).
            status: Initial rule status.

        Returns:
            Created WhitelistRule.
        """
        from uuid import uuid4

        rule = WhitelistRule(
            id=uuid4(),
            endpoint=endpoint,
            provider=provider,
            purpose=purpose,
            risk_level=risk_level,
            status=WhitelistStatus(status),
        )
        return self.add_rule(rule)
