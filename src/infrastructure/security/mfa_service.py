"""MFA Service — Multi-Factor Authentication Service.

Implements multi-factor authentication for 等保 2.0 Level 3 compliance.
Supports TOTP (Time-based One-Time Password) via Authenticator Apps.

Features:
- MFA challenge issuance and verification
- TOTP secret generation and provisioning URI creation
- Integration with AuthService for authentication flow
- Audit logging for security compliance
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.domain.events.compliance_events import (
    MFAChallengeIssuedEvent,
)
from src.domain.events.compliance_events import (
    MFAChallengeStatus as EventMFAChallengeStatus,
)
from src.domain.events.compliance_events import (
    MFAChallengeType as EventMFAChallengeType,
)
from src.infrastructure.security.models import (
    MFAChallenge,
    MFAChallengeStatus,
    MFAChallengeType,
)
from src.infrastructure.security.totp_generator import (
    TOTPGenerator,
    TOTPVerifier,
    get_totp_generator,
    get_totp_verifier,
)

if TYPE_CHECKING:
    pass


class MFAError(Exception):
    """Base exception for MFA errors."""

    pass


class MFAChallengeExpiredError(MFAError):
    """MFA challenge has expired."""

    pass


class MFAInvalidCodeError(MFAError):
    """MFA verification code is invalid."""

    pass


class MFAMaxAttemptsReachedError(MFAError):
    """Maximum MFA verification attempts reached."""

    pass


class MFANotEnabledError(MFAError):
    """MFA is not enabled for the user."""

    pass


@dataclass
class MFASetupResult:
    """Result of MFA setup operation.

    Attributes:
        success: Whether setup was successful.
        secret: TOTP secret (only returned once, must be stored securely).
        provisioning_uri: URI for QR code generation.
        challenge_id: ID of the created MFA challenge.
    """

    success: bool
    secret: str = ""
    provisioning_uri: str = ""
    challenge_id: UUID | None = None


@dataclass
class MFAVerifyResult:
    """Result of MFA verification.

    Attributes:
        success: Whether verification was successful.
        challenge_id: ID of the verified challenge.
        verified_at: Timestamp of verification.
    """

    success: bool
    challenge_id: UUID | None = None
    verified_at: datetime | None = None


class MFAService:
    """MFA Service for multi-factor authentication.

    Implements TOTP-based MFA following 等保 2.0 Level 3 requirements:
    - 双因子认证 (Two-factor authentication)
    - TOTP support (RFC 6238)
    - Maximum 3 verification attempts per challenge
    - Challenge expiration (5 minutes)
    """

    # Challenge settings
    CHALLENGE_TTL_MINUTES: int = 5
    MAX_VERIFICATION_ATTEMPTS: int = 3

    def __init__(
        self,
        totp_generator: TOTPGenerator | None = None,
        totp_verifier: TOTPVerifier | None = None,
    ) -> None:
        """Initialize MFA Service.

        Args:
            totp_generator: TOTP generator instance.
            totp_verifier: TOTP verifier instance.
        """
        self._totp_generator = totp_generator or get_totp_generator()
        self._totp_verifier = totp_verifier or get_totp_verifier()
        # In-memory store for MFA challenges (in production, use Redis/DB)
        self._challenges: dict[UUID, MFAChallenge] = {}
        # In-memory store for user MFA secrets (in production, use encrypted DB field)
        self._user_secrets: dict[UUID, str] = {}

    def setup_mfa(self, user_id: UUID, username: str = "") -> MFASetupResult:
        """Setup MFA for a user.

        Generates a new TOTP secret and creates a provisioning URI
        for QR code scanning.

        Args:
            user_id: UUID of the user setting up MFA.
            username: Username for display in authenticator app.

        Returns:
            MFASetupResult: Setup result with secret and provisioning URI.
        """
        # Generate new TOTP secret
        secret = self._totp_generator.generate_secret()

        # Store secret securely (in production, encrypt before storing)
        self._user_secrets[user_id] = secret

        # Create provisioning URI
        provisioning_uri = self._totp_generator.get_provisioning_uri(
            secret=secret,
            account_name=username or str(user_id),
            issuer="SISYS",
        )

        # Create MFA challenge
        challenge_id = uuid4()
        expires_at = datetime.now(UTC) + timedelta(minutes=self.CHALLENGE_TTL_MINUTES)

        challenge = MFAChallenge(
            id=challenge_id,
            user_id=user_id,
            challenge_type=MFAChallengeType.TOTP,
            secret=secret,
            max_attempts=self.MAX_VERIFICATION_ATTEMPTS,
            expires_at=expires_at,
            status=MFAChallengeStatus.PENDING,
        )

        self._challenges[challenge_id] = challenge

        return MFASetupResult(
            success=True,
            secret=secret,
            provisioning_uri=provisioning_uri,
            challenge_id=challenge_id,
        )

    def verify_mfa_setup(self, user_id: UUID, code: str) -> bool:
        """Verify MFA setup by checking if the code is valid.

        Args:
            user_id: UUID of the user.
            code: TOTP code from authenticator app.

        Returns:
            bool: True if setup is verified successfully.
        """
        secret = self._user_secrets.get(user_id)
        if not secret:
            raise MFANotEnabledError("MFA not enabled for user")

        return self._totp_verifier.verify(secret, code)

    def create_challenge(
        self,
        user_id: UUID,
        ip_address: str = "",
        user_agent: str = "",
    ) -> MFAChallengeIssuedEvent:
        """Create a new MFA challenge for verification.

        Args:
            user_id: UUID of the user.
            ip_address: IP address of the request.
            user_agent: User agent string.

        Returns:
            MFAChallengeIssuedEvent: Domain event for the challenge.

        Raises:
            MFANotEnabledError: If MFA is not enabled for the user.
        """
        if user_id not in self._user_secrets:
            raise MFANotEnabledError("MFA not enabled for user")

        secret = self._user_secrets[user_id]
        challenge_id = uuid4()
        expires_at = datetime.now(UTC) + timedelta(minutes=self.CHALLENGE_TTL_MINUTES)

        challenge = MFAChallenge(
            id=challenge_id,
            user_id=user_id,
            challenge_type=MFAChallengeType.TOTP,
            secret=secret,
            max_attempts=self.MAX_VERIFICATION_ATTEMPTS,
            expires_at=expires_at,
            status=MFAChallengeStatus.PENDING,
        )

        self._challenges[challenge_id] = challenge

        return MFAChallengeIssuedEvent(
            challenge_id=challenge_id,
            user_id=user_id,
            challenge_type=EventMFAChallengeType.TOTP,
            status=EventMFAChallengeStatus.PENDING,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def verify_challenge(
        self,
        challenge_id: UUID,
        code: str,
    ) -> MFAVerifyResult:
        """Verify an MFA challenge with the provided code.

        Args:
            challenge_id: UUID of the challenge to verify.
            code: TOTP code from authenticator app.

        Returns:
            MFAVerifyResult: Verification result.

        Raises:
            MFAChallengeExpiredError: If challenge has expired.
            MFAInvalidCodeError: If code is invalid.
            MFAMaxAttemptsReachedError: If max attempts reached.
        """
        challenge = self._challenges.get(challenge_id)
        if not challenge:
            raise MFAInvalidCodeError("Invalid challenge ID")

        # Check expiration
        if challenge.is_expired():
            challenge.mark_expired()
            raise MFAChallengeExpiredError("MFA challenge has expired")

        # Check max attempts
        if challenge.is_max_attempts_reached():
            challenge.mark_failed()
            raise MFAMaxAttemptsReachedError("Maximum verification attempts reached")

        # Increment attempts
        challenge.increment_attempts()

        # Verify code
        if not self._totp_verifier.verify(challenge.secret, code):
            # Check if max attempts reached after this failure
            if challenge.is_max_attempts_reached():
                challenge.mark_failed()
            raise MFAInvalidCodeError("Invalid MFA verification code")

        # Mark as verified
        challenge.mark_verified()

        return MFAVerifyResult(
            success=True,
            challenge_id=challenge_id,
            verified_at=datetime.now(UTC),
        )

    def get_mfa_status(self, user_id: UUID) -> bool:
        """Check if MFA is enabled for a user.

        Args:
            user_id: UUID of the user.

        Returns:
            bool: True if MFA is enabled.
        """
        return user_id in self._user_secrets

    def disable_mfa(self, user_id: UUID) -> None:
        """Disable MFA for a user.

        Args:
            user_id: UUID of the user.
        """
        if user_id in self._user_secrets:
            del self._user_secrets[user_id]

    def get_challenge(self, challenge_id: UUID) -> MFAChallenge | None:
        """Get an MFA challenge by ID.

        Args:
            challenge_id: UUID of the challenge.

        Returns:
            MFAChallenge | None: Challenge if found.
        """
        return self._challenges.get(challenge_id)


# Global MFA service instance
_mfa_service: MFAService | None = None


def get_mfa_service() -> MFAService:
    """Get global MFA Service instance.

    Returns:
        MFAService: Global MFA service instance.
    """
    global _mfa_service
    if _mfa_service is None:
        _mfa_service = MFAService()
    return _mfa_service
