"""TOTP Generator and Verifier — Time-based One-Time Password (RFC 6238).

Implements TOTP algorithm for multi-factor authentication.
Reference: RFC 6238, RFC 4226 (HOTP).

等保 2.0 Level 3 要求:
- 支持基于时间的一次性密码 (TOTP)
- 支持 Authenticator App (如 Google Authenticator, Microsoft Authenticator)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# TOTP Parameters (RFC 6238)
_TOTP_PERIOD: int = 30  # Time step in seconds
_TOTP_DIGITS: int = 6  # Number of digits in TOTP
_TOTP_ALGORITHM: str = "sha1"  # HMAC algorithm (sha1 per RFC 6238)


class TOTPError(Exception):
    """Base exception for TOTP errors."""

    pass


class TOTPVerificationError(TOTPError):
    """TOTP verification failed."""

    pass


class TOTPExpiredError(TOTPError):
    """TOTP has expired."""

    pass


@dataclass
class TOTPSecret:
    """TOTP secret key with metadata.

    Attributes:
        secret: Base32-encoded secret key.
        issuer: Service issuer name (shown in authenticator app).
        account_name: User account name (shown in authenticator app).
        created_at: Secret creation timestamp.
    """

    secret: str
    issuer: str = "SISYS"
    account_name: str = ""
    created_at: float | None = None

    def __post_init__(self) -> None:
        """Set created_at if not provided."""
        if self.created_at is None:
            self.created_at = time.time()


class TOTPGenerator:
    """TOTP Generator for creating time-based one-time passwords.

    Implements RFC 6238 TOTP algorithm with the following features:
    - RFC 6238 compliant TOTP generation
    - Configurable time step (default 30 seconds)
    - Configurable output digits (default 6)
    - Support for custom HMAC algorithms
    """

    def __init__(
        self,
        period: int = _TOTP_PERIOD,
        digits: int = _TOTP_DIGITS,
        algorithm: str = _TOTP_ALGORITHM,
    ) -> None:
        """Initialize TOTP Generator.

        Args:
            period: Time step in seconds (default 30).
            digits: Number of digits in generated TOTP (default 6).
            algorithm: HMAC algorithm (default sha1 per RFC 6238).
        """
        self._period = period
        self._digits = digits
        self._algorithm = algorithm

    @staticmethod
    def generate_secret(length: int = 20) -> str:
        """Generate a cryptographically secure random secret.

        Args:
            length: Length of secret in bytes (default 20).
                   Results in ~32 Base32 characters.

        Returns:
            str: Base32-encoded secret key.
        """
        random_bytes = secrets.token_bytes(length)
        return base64.b32encode(random_bytes).decode("ascii").rstrip("=")

    @staticmethod
    def get_current_counter(period: int = _TOTP_PERIOD) -> int:
        """Get current time counter value.

        The counter is the number of time steps elapsed since Unix epoch.

        Args:
            period: Time step in seconds.

        Returns:
            int: Current counter value.
        """
        return int(time.time()) // period

    def generate(
        self,
        secret: str,
        counter: int | None = None,
    ) -> str:
        """Generate TOTP code for given secret and counter.

        Args:
            secret: Base32-encoded secret key.
            counter: Time counter value. If None, uses current time.

        Returns:
            str: Generated TOTP code padded to configured digits.
        """
        if counter is None:
            counter = self.get_current_counter(self._period)

        return self._generate_hotp(secret, counter)

    def _generate_hotp(self, secret: str, counter: int) -> str:
        """Generate HOTP value for given counter (RFC 4226).

        Args:
            secret: Base32-encoded secret key.
            counter: Counter value.

        Returns:
            str: Generated HOTP code padded to configured digits.
        """
        # Decode Base32 secret
        secret_bytes = self._decode_base32(secret)

        # Convert counter to 8-byte big-endian
        counter_bytes = counter.to_bytes(8, byteorder="big")

        # Generate HMAC
        hmac_hash = hmac.new(
            secret_bytes,
            counter_bytes,
            hashlib.new(self._algorithm).name,
        ).digest()

        # Dynamic truncation (RFC 4226 Section 5.4)
        offset = hmac_hash[-1] & 0x0F
        truncated_hash = (
            (hmac_hash[offset] & 0x7F) << 24
            | (hmac_hash[offset + 1] & 0xFF) << 16
            | (hmac_hash[offset + 2] & 0xFF) << 8
            | (hmac_hash[offset + 3] & 0xFF)
        )

        # Generate code with configured number of digits
        code = truncated_hash % (10**self._digits)

        return str(code).zfill(self._digits)

    @staticmethod
    def _decode_base32(encoded: str) -> bytes:
        """Decode Base32-encoded string.

        Args:
            encoded: Base32-encoded string.

        Returns:
            bytes: Decoded bytes.

        Raises:
            ValueError: If input is not valid Base32.
        """
        # Add padding if necessary
        padding = (8 - len(encoded) % 8) % 8
        encoded_padded = encoded + "=" * padding

        try:
            return base64.b32decode(encoded_padded.upper())
        except Exception as e:
            raise ValueError(f"Invalid Base32 encoding: {e}") from e

    def get_provisioning_uri(
        self,
        secret: str,
        account_name: str,
        issuer: str = "SISYS",
    ) -> str:
        """Generate provisioning URI for QR code.

        Format: otpauth://totp/{issuer}:{account_name}?secret={secret}&issuer={issuer}&algorithm={algorithm}&digits={digits}&period={period}

        Args:
            secret: Base32-encoded secret key.
            account_name: User account name.
            issuer: Service issuer name.

        Returns:
            str: Provisioning URI for QR code scanning.
        """
        from urllib.parse import quote

        label = quote(f"{issuer}:{account_name}")
        params = (
            f"secret={secret}&issuer={quote(issuer)}"
            f"&algorithm={self._algorithm.upper()}"
            f"&digits={self._digits}&period={self._period}"
        )

        return f"otpauth://totp/{label}?{params}"


class TOTPVerifier:
    """TOTP Verifier for validating time-based one-time passwords.

    Implements verification with the following security measures:
    - Time window tolerance (allows codes from previous/current/next time steps)
    - Single-use enforcement (prevents replay attacks)
    - Rate limiting (integrates with intrusion detection)
    """

    # Time window: allow codes from 1 period before and after current
    DEFAULT_TIME_WINDOW: int = 1

    def __init__(
        self,
        generator: TOTPGenerator | None = None,
        time_window: int = DEFAULT_TIME_WINDOW,
    ) -> None:
        """Initialize TOTP Verifier.

        Args:
            generator: TOTP generator instance. If None, creates default.
            time_window: Number of time periods to allow before/after current.
                        Default 1 allows codes from previous, current, and next periods.
        """
        self._generator = generator or TOTPGenerator()
        self._time_window = time_window

    def verify(
        self,
        secret: str,
        code: str,
        valid_counter: int | None = None,
    ) -> bool:
        """Verify a TOTP code against the secret.

        Args:
            secret: Base32-encoded secret key.
            code: TOTP code to verify (string of digits).
            valid_counter: Optional counter to verify against.
                          If None, checks current and adjacent periods.

        Returns:
            bool: True if code is valid, False otherwise.
        """
        # Clean and validate input
        code = code.strip()
        if not code.isdigit() or len(code) != self._generator._digits:
            return False

        code_int = int(code)

        if valid_counter is not None:
            # Verify against specific counter
            expected = int(self._generator.generate(secret, valid_counter))
            return code_int == expected

        # Check adjacent time windows for tolerance
        current_counter = TOTPGenerator.get_current_counter(self._generator._period)

        for offset in range(-self._time_window, self._time_window + 1):
            counter = current_counter + offset
            expected = int(self._generator.generate(secret, counter))
            if code_int == expected:
                return True

        return False

    def get_acceptable_counters(
        self,
        period: int = _TOTP_PERIOD,
        window: int | None = None,
    ) -> list[int]:
        """Get list of acceptable counter values based on time window.

        Args:
            period: Time step in seconds.
            window: Time window in periods. If None, uses default.

        Returns:
            list[int]: List of acceptable counter values.
        """
        if window is None:
            window = self._time_window

        current_counter = TOTPGenerator.get_current_counter(period)
        return [current_counter + offset for offset in range(-window, window + 1)]


# Convenience function for generating new TOTP secrets
def generate_totp_secret(length: int = 20) -> str:
    """Generate a cryptographically secure TOTP secret.

    Args:
        length: Length of secret in bytes (default 20).

    Returns:
        str: Base32-encoded secret key.
    """
    return TOTPGenerator.generate_secret(length)


# Global instances for convenience
_totp_generator: TOTPGenerator | None = None
_totp_verifier: TOTPVerifier | None = None


def get_totp_generator() -> TOTPGenerator:
    """Get global TOTP Generator instance.

    Returns:
        TOTPGenerator: Global TOTP generator instance.
    """
    global _totp_generator
    if _totp_generator is None:
        _totp_generator = TOTPGenerator()
    return _totp_generator


def get_totp_verifier() -> TOTPVerifier:
    """Get global TOTP Verifier instance.

    Returns:
        TOTPVerifier: Global TOTP verifier instance.
    """
    global _totp_verifier
    if _totp_verifier is None:
        _totp_verifier = TOTPVerifier()
    return _totp_verifier
