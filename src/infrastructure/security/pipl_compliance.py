"""PIPL Compliance Service.

Implements Personal Information Protection Law (PIPL) compliance functionality.
Reference: Story 1.11 Data Sovereignty Isolation - AC-5.

Architecture: Infrastructure layer service (hexagonal architecture).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from .models import SensitiveDataType

if TYPE_CHECKING:
    from ..config.sovereignty import DataSovereigntyConfig


class GuardianConsentRequiredError(Exception):
    """Raised when guardian consent is required but not provided."""

    pass


@dataclass
class PIPLAccessRecord:
    """Record of personal information access under PIPL.

    Attributes:
        access_id: Unique access record ID.
        personal_data_id: UUID of personal data accessed.
        purpose: Purpose of data processing.
        legal_basis: Legal basis for processing (consent, contract, legal_obligation, etc.)
        data_subject_consent: Whether data subject provided consent.
        accessor: User/System accessing the data.
        accessed_at: Timestamp of access.
        is_biometric: Whether this involves biometric data.
        is_minor: Whether this involves minor's data.
    """

    access_id: UUID = field(default_factory=uuid4)
    personal_data_id: UUID = field(default_factory=uuid4)
    purpose: str = ""
    legal_basis: str = ""
    data_subject_consent: bool = False
    accessor: str = ""
    accessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_biometric: bool = False
    is_minor: bool = False


@dataclass
class DataSubjectRights:
    """Data subject rights information.

    Attributes:
        data_id: UUID of the data.
        access_right: Whether access right has been exercised.
        deletion_right: Whether deletion right has been exercised.
        correction_right: Whether correction right has been exercised.
        portability_right: Whether data portability right has been exercised.
        last_exercised: Last time any right was exercised.
    """

    data_id: UUID
    access_right: bool = False
    deletion_right: bool = False
    correction_right: bool = False
    portability_right: bool = False
    last_exercised: datetime | None = None


@dataclass
class PIPLComplianceReport:
    """PIPL compliance report.

    Attributes:
        report_id: Unique report ID.
        generated_at: Report generation timestamp.
        total_pipl_processing_records: Total number of PIPL processing records.
        consent_records: Number of consent-based processing records.
        legal_basis_breakdown: Breakdown by legal basis type.
        data_subject_rights_exercised: Count of rights exercises by type.
        biometric_processing_count: Number of biometric processing records.
        minor_data_processing_count: Number of minor data processing records.
    """

    report_id: UUID
    generated_at: datetime
    total_pipl_processing_records: int = 0
    consent_records: int = 0
    legal_basis_breakdown: dict[str, int] = field(default_factory=dict)
    data_subject_rights_exercised: dict[str, int] = field(default_factory=dict)
    biometric_processing_count: int = 0
    minor_data_processing_count: int = 0


class PIPLComplianceService:
    """Service for PIPL (Personal Information Protection Law) compliance.

    Handles:
    - Recording personal information access
    - Verifying legal basis for processing
    - Guardian consent for minor data
    - Data subject rights tracking
    - PIPL compliance reporting
    """

    # Valid legal bases under PIPL
    VALID_LEGAL_BASES = {"consent", "contract", "legal_obligation", "vital_interest", "public_task", "legitimate_interest"}

    def __init__(self, config: DataSovereigntyConfig | None = None) -> None:
        """Initialize service with configuration.

        Args:
            config: Data sovereignty configuration.
        """
        from ..config.sovereignty import get_sovereignty_config

        self._config = config or get_sovereignty_config()
        self._access_records: dict[UUID, PIPLAccessRecord] = {}
        self._data_subject_rights: dict[UUID, DataSubjectRights] = {}

    def record_access(
        self,
        personal_data_id: UUID,
        purpose: str,
        legal_basis: str,
        data_subject_consent: bool,
        accessor: str,
        data_type: SensitiveDataType = SensitiveDataType.PII,
    ) -> PIPLAccessRecord:
        """Record personal information access under PIPL.

        Args:
            personal_data_id: UUID of personal data accessed.
            purpose: Purpose of data processing.
            legal_basis: Legal basis for processing.
            data_subject_consent: Whether consent was provided.
            accessor: User/System accessing the data.
            data_type: Type of sensitive data.

        Returns:
            Created PIPLAccessRecord.

        Raises:
            ValueError: If legal basis is invalid.
        """
        if not self.verify_legal_basis(legal_basis):
            raise ValueError(f"Invalid legal basis: {legal_basis}")

        # Check consent requirement for sensitive data
        if self.check_consent_required(data_type) and not data_subject_consent:
            if legal_basis == "consent":
                raise ValueError("Consent is required for this data type but was not provided")

        record = PIPLAccessRecord(
            personal_data_id=personal_data_id,
            purpose=purpose,
            legal_basis=legal_basis,
            data_subject_consent=data_subject_consent,
            accessor=accessor,
            is_biometric=data_type == SensitiveDataType.BIOMETRIC,
            is_minor=data_type == SensitiveDataType.MINOR,
        )

        self._access_records[record.access_id] = record
        return record

    def record_minor_access(
        self,
        personal_data_id: UUID,
        purpose: str,
        legal_basis: str,
        guardian_consent: bool,
        accessor: str,
        minor_age: int,
    ) -> PIPLAccessRecord:
        """Record minor's personal information access.

        Args:
            personal_data_id: UUID of minor's personal data.
            purpose: Purpose of data processing.
            legal_basis: Legal basis for processing.
            guardian_consent: Whether guardian consent was provided.
            accessor: User/System accessing the data.
            minor_age: Age of the minor.

        Returns:
            Created PIPLAccessRecord.

        Raises:
            GuardianConsentRequiredError: If guardian consent is required but not provided.
        """
        age_threshold = self._config.minor_age_threshold

        if minor_age < age_threshold and not guardian_consent:
            raise GuardianConsentRequiredError(f"Guardian consent required for minors under {age_threshold} years old")

        record = PIPLAccessRecord(
            personal_data_id=personal_data_id,
            purpose=purpose,
            legal_basis=legal_basis,
            data_subject_consent=guardian_consent,  # For minors, guardian consent replaces subject consent
            accessor=accessor,
            is_minor=True,
        )

        self._access_records[record.access_id] = record
        return record

    def check_consent_required(self, data_type: SensitiveDataType) -> bool:
        """Check if consent is required for a data type.

        Args:
            data_type: Sensitive data type.

        Returns:
            True if consent is required.
        """
        if not self._config.pipl_consent_required:
            return False

        # Sensitive types require consent
        sensitive_types = {
            SensitiveDataType.PII,
            SensitiveDataType.BIOMETRIC,
            SensitiveDataType.MINOR,
            SensitiveDataType.HEALTH,
            SensitiveDataType.IDENTITY_DOCUMENT,
        }

        return data_type in sensitive_types

    def verify_legal_basis(self, legal_basis: str) -> bool:
        """Verify if legal basis is valid under PIPL.

        Args:
            legal_basis: Legal basis to verify.

        Returns:
            True if legal basis is valid.
        """
        return legal_basis in self.VALID_LEGAL_BASES

    def check_data_subject_rights(self, data_id: UUID) -> DataSubjectRights:
        """Check data subject rights exercised for a data item.

        Args:
            data_id: UUID of the personal data.

        Returns:
            DataSubjectRights with rights exercise information.
        """
        if data_id not in self._data_subject_rights:
            self._data_subject_rights[data_id] = DataSubjectRights(data_id=data_id)

        return self._data_subject_rights[data_id]

    def exercise_access_right(self, data_id: UUID) -> None:
        """Record exercise of access right.

        Args:
            data_id: UUID of the personal data.
        """
        if data_id not in self._data_subject_rights:
            self._data_subject_rights[data_id] = DataSubjectRights(data_id=data_id)

        rights = self._data_subject_rights[data_id]
        rights.access_right = True
        rights.last_exercised = datetime.now(UTC)

    def exercise_deletion_right(self, data_id: UUID) -> None:
        """Record exercise of deletion right.

        Args:
            data_id: UUID of the personal data.
        """
        if data_id not in self._data_subject_rights:
            self._data_subject_rights[data_id] = DataSubjectRights(data_id=data_id)

        rights = self._data_subject_rights[data_id]
        rights.deletion_right = True
        rights.last_exercised = datetime.now(UTC)

    def exercise_correction_right(self, data_id: UUID) -> None:
        """Record exercise of correction right.

        Args:
            data_id: UUID of the personal data.
        """
        if data_id not in self._data_subject_rights:
            self._data_subject_rights[data_id] = DataSubjectRights(data_id=data_id)

        rights = self._data_subject_rights[data_id]
        rights.correction_right = True
        rights.last_exercised = datetime.now(UTC)

    def generate_report(self) -> PIPLComplianceReport:
        """Generate PIPL compliance report.

        Returns:
            PIPLComplianceReport with compliance statistics.
        """
        report = PIPLComplianceReport(
            report_id=uuid4(),
            generated_at=datetime.now(UTC),
        )

        # Count records
        report.total_pipl_processing_records = len(self._access_records)

        # Breakdown by legal basis
        legal_basis_counts: dict[str, int] = {}
        for record in self._access_records.values():
            legal_basis_counts[record.legal_basis] = legal_basis_counts.get(record.legal_basis, 0) + 1
            if record.legal_basis == "consent":
                report.consent_records += 1
            if record.is_biometric:
                report.biometric_processing_count += 1
            if record.is_minor:
                report.minor_data_processing_count += 1

        report.legal_basis_breakdown = legal_basis_counts

        # Data subject rights exercised
        rights_counts: dict[str, int] = {
            "access": 0,
            "deletion": 0,
            "correction": 0,
            "portability": 0,
        }
        for rights in self._data_subject_rights.values():
            if rights.access_right:
                rights_counts["access"] += 1
            if rights.deletion_right:
                rights_counts["deletion"] += 1
            if rights.correction_right:
                rights_counts["correction"] += 1
            if rights.portability_right:
                rights_counts["portability"] += 1

        report.data_subject_rights_exercised = rights_counts

        return report
