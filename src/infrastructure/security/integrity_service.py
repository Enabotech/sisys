"""Integrity Service — Data integrity verification and digital signatures.

Implements data integrity verification for 等保 2.0 Level 3:
- Hash-based integrity verification (SHA-256, SHA-512)
- Digital signature generation and verification
- Integrity check records

等保 2.0 Level 3 要求:
- 数据完整性: Hash校验、数字签名
- 加密覆盖率 100%
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key

from src.infrastructure.security.models import (
    HashAlgorithm,
    IntegrityCheck,
    IntegrityStatus,
)

if TYPE_CHECKING:
    pass


class IntegrityError(Exception):
    """Base exception for integrity errors."""

    pass


class HashMismatchError(IntegrityError):
    """Hash verification failed."""

    pass


class SignatureError(IntegrityError):
    """Digital signature verification failed."""

    pass


class IntegrityVerifier:
    """Data Integrity Verifier using hash algorithms.

    Implements hash-based integrity verification following 等保 2.0 Level 3:
    - SHA-256 (default)
    - SHA-512
    - MD5 (legacy support)
    """

    def __init__(
        self,
        default_algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    ) -> None:
        """Initialize Integrity Verifier.

        Args:
            default_algorithm: Default hash algorithm.
        """
        self._default_algorithm = default_algorithm
        # In-memory store for integrity checks (in production, use PostgreSQL)
        self._integrity_records: dict[UUID, IntegrityCheck] = {}

    def compute_hash(
        self,
        data: str | bytes,
        algorithm: HashAlgorithm | None = None,
    ) -> str:
        """Compute hash of data.

        Args:
            data: Data to hash.
            algorithm: Hash algorithm to use. If None, uses default.

        Returns:
            str: Hex-encoded hash value.
        """
        if algorithm is None:
            algorithm = self._default_algorithm

        if isinstance(data, str):
            data = data.encode("utf-8")

        if algorithm == HashAlgorithm.SHA256:
            return hashlib.sha256(data).hexdigest()
        elif algorithm == HashAlgorithm.SHA512:
            return hashlib.sha512(data).hexdigest()
        elif algorithm == HashAlgorithm.MD5:
            return hashlib.md5(data, usedforsecurity=False).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

    def verify_hash(
        self,
        data: str | bytes,
        expected_hash: str,
        algorithm: HashAlgorithm | None = None,
    ) -> bool:
        """Verify data against expected hash.

        Args:
            data: Data to verify.
            expected_hash: Expected hash value.
            algorithm: Hash algorithm to use. If None, uses default.

        Returns:
            bool: True if hash matches.
        """
        actual_hash = self.compute_hash(data, algorithm)
        return hmac.compare_digest(actual_hash.lower(), expected_hash.lower())

    async def verify_and_record(
        self,
        data_id: UUID,
        data: str | bytes,
        expected_hash: str,
        data_type: str = "",
        source: str = "",
        algorithm: HashAlgorithm | None = None,
    ) -> IntegrityCheck:
        """Verify data integrity and record the check.

        Args:
            data_id: UUID of the data being verified.
            data: Data to verify.
            expected_hash: Expected hash value.
            data_type: Type of data (document, config, etc.).
            source: Storage location.
            algorithm: Hash algorithm to use.

        Returns:
            IntegrityCheck: Record of the verification check.
        """
        algorithm = algorithm or self._default_algorithm
        actual_hash = self.compute_hash(data, algorithm)

        # Verify
        matches = hmac.compare_digest(actual_hash.lower(), expected_hash.lower())

        # Create record
        check = IntegrityCheck(
            id=uuid4(),
            data_type=data_type,
            data_id=data_id,
            hash_value=expected_hash,
            algorithm=algorithm,
            status=IntegrityStatus.VERIFIED if matches else IntegrityStatus.VIOLATED,
            source=source,
        )

        self._integrity_records[check.id] = check

        return check

    async def get_integrity_check(self, check_id: UUID) -> IntegrityCheck | None:
        """Get an integrity check record.

        Args:
            check_id: UUID of the check record.

        Returns:
            IntegrityCheck | None: Check record if found.
        """
        return self._integrity_records.get(check_id)

    async def verify_file(self, file_path: str, expected_hash: str) -> bool:
        """Verify file integrity.

        Args:
            file_path: Path to file.
            expected_hash: Expected hash value.

        Returns:
            bool: True if hash matches.
        """
        # In production, read file and compute hash
        # For now, simulate
        with open(file_path, "rb") as f:
            content = f.read()
        return self.verify_hash(content, expected_hash)


class SignatureService:
    """Digital Signature Service for data authenticity.

    Implements digital signatures following 等保 2.0 Level 3:
    - RSA signatures (RSASSA-PKCS1-v1_5)
    - Signature verification
    - Key management
    """

    def __init__(self) -> None:
        """Initialize Signature Service."""
        # In production, use secure key storage (HSM/KMS)
        self._private_key: rsa.RSAPrivateKey | None = None
        self._public_key: rsa.RSAPublicKey | None = None

    def generate_key_pair(self, key_size: int = 2048) -> tuple[bytes, bytes]:
        """Generate RSA key pair.

        Args:
            key_size: RSA key size in bits (default 2048).

        Returns:
            tuple: (private_key_pem, public_key_pem)
        """
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
        )
        self._private_key = private_key
        self._public_key = private_key.public_key()

        # Serialize keys
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        public_pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return private_pem, public_pem

    def set_key_pair(self, private_key_pem: bytes, public_key_pem: bytes) -> None:
        """Set key pair from PEM-encoded bytes.

        Args:
            private_key_pem: PEM-encoded private key.
            public_key_pem: PEM-encoded public key.
        """
        self._private_key = cast(rsa.RSAPrivateKey, load_pem_private_key(private_key_pem, password=None))
        self._public_key = cast(rsa.RSAPublicKey, load_pem_public_key(public_key_pem))

    def sign(self, data: str | bytes) -> str:
        """Sign data with RSA private key.

        Args:
            data: Data to sign.

        Returns:
            str: Base64-encoded signature.

        Raises:
            SignatureError: If signing fails.
        """
        if self._private_key is None:
            raise SignatureError("Private key not set. Call generate_key_pair or set_key_pair first.")

        if isinstance(data, str):
            data = data.encode("utf-8")

        # Sign using RSASSA-PKCS1-v1_5 with SHA-256
        signature = self._private_key.sign(
            data,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

        # Return as base64
        import base64

        return base64.b64encode(signature).decode("ascii")

    def verify(self, data: str | bytes, signature: str) -> bool:
        """Verify signature with RSA public key.

        Args:
            data: Original data that was signed.
            signature: Base64-encoded signature to verify.

        Returns:
            bool: True if signature is valid.

        Raises:
            SignatureError: If verification fails.
        """
        if self._public_key is None:
            raise SignatureError("Public key not set. Call generate_key_pair or set_key_pair first.")

        if isinstance(data, str):
            data = data.encode("utf-8")

        try:
            import base64

            signature_bytes = base64.b64decode(signature)
            self._public_key.verify(
                signature_bytes,
                data,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False

    def sign_data_with_timestamp(self, data: str | bytes) -> dict[str, Any]:
        """Sign data and include timestamp.

        Args:
            data: Data to sign.

        Returns:
            dict: Contains data, signature, and timestamp.
        """
        import base64
        from datetime import datetime

        if isinstance(data, str):
            data_bytes = data.encode("utf-8")
        else:
            data_bytes = data

        timestamp = datetime.now(UTC).isoformat()
        data_to_sign = f"{base64.b64encode(data_bytes).decode()}.{timestamp}"

        signature = self.sign(data_to_sign)

        return {
            "data": data if isinstance(data, str) else base64.b64encode(data).decode(),
            "timestamp": timestamp,
            "signature": signature,
        }

    def verify_data_with_timestamp(self, signed_data: dict[str, Any]) -> bool:
        """Verify data with timestamp.

        Args:
            signed_data: Dictionary with data, timestamp, and signature.

        Returns:
            bool: True if verification succeeds.
        """
        try:
            import base64

            data = signed_data["data"]
            timestamp = signed_data["timestamp"]
            signature = signed_data["signature"]

            data_to_verify = f"{base64.b64encode(data.encode() if isinstance(data, str) else data).decode()}.{timestamp}"

            return self.verify(data_to_verify, signature)
        except Exception:
            return False


# Global instances
_integrity_verifier: IntegrityVerifier | None = None
_signature_service: SignatureService | None = None


def get_integrity_verifier() -> IntegrityVerifier:
    """Get global Integrity Verifier instance.

    Returns:
        IntegrityVerifier: Global integrity verifier instance.
    """
    global _integrity_verifier
    if _integrity_verifier is None:
        _integrity_verifier = IntegrityVerifier()
    return _integrity_verifier


def get_signature_service() -> SignatureService:
    """Get global Signature Service instance.

    Returns:
        SignatureService: Global signature service instance.
    """
    global _signature_service
    if _signature_service is None:
        _signature_service = SignatureService()
    return _signature_service
