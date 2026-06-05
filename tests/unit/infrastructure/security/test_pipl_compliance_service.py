"""Tests for PIPLComplianceService service implementation.

TDD Red Phase: These tests define expected PIPL compliance behavior.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.domain.entities.pipl_compliance_record import (
    ConsentStatus,
    LegalBasis,
    PIPLComplianceRecord,
)
from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl


class TestPIPLComplianceServiceRecordAccess:
    """Test record_access functionality."""

    def test_record_access_with_consent(self):
        """Test recording access with valid consent."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            LegalBasis,
            PIPLComplianceRecord,
        )
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()

        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="Analytics",
            legal_basis=LegalBasis.CONSENT.value,
            consent_status=ConsentStatus.GIVEN,
            accessor="system",
            data_subject_id="user-456",
        )

        service.record_access(record)

        # Verify record was stored
        stored = service.get_record("pd-123")
        assert stored is not None
        assert stored.consent_status == ConsentStatus.GIVEN

    def test_record_access_with_legal_obligation(self):
        """Test recording access with legal obligation basis."""
        from src.domain.entities.pipl_compliance_record import (
            LegalBasis,
            PIPLComplianceRecord,
        )
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()

        record = PIPLComplianceRecord(
            personal_data_id="pd-456",
            purpose="Legal Compliance",
            legal_basis=LegalBasis.LEGAL_OBLIGATION.value,
            accessor="system",
            data_subject_id="user-789",
        )

        service.record_access(record)

        # Verify is_compliant returns True for legal obligation
        result = service.validate_legal_basis("pd-456", LegalBasis.LEGAL_OBLIGATION.value)
        assert result is True


class TestPIPLComplianceServiceValidateLegalBasis:
    """Test validate_legal_basis functionality."""

    def test_validate_consent_basis_with_given_consent(self):
        """Test consent basis is valid when consent is given."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            LegalBasis,
            PIPLComplianceRecord,
        )
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()

        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="Analytics",
            legal_basis=LegalBasis.CONSENT.value,
            consent_status=ConsentStatus.GIVEN,
            accessor="system",
            data_subject_id="user-456",
        )

        service.record_access(record)
        result = service.validate_legal_basis("pd-123", LegalBasis.CONSENT.value)
        assert result is True

    def test_validate_consent_basis_with_withdrawn_consent(self):
        """Test consent basis is invalid when consent is withdrawn."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            LegalBasis,
            PIPLComplianceRecord,
        )
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()

        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="Analytics",
            legal_basis=LegalBasis.CONSENT.value,
            consent_status=ConsentStatus.WITHDRAWN,
            accessor="system",
            data_subject_id="user-456",
        )

        service.record_access(record)
        result = service.validate_legal_basis("pd-123", LegalBasis.CONSENT.value)
        assert result is False

    def test_validate_non_consent_basis(self):
        """Test non-consent bases are always valid."""
        from src.domain.entities.pipl_compliance_record import (
            LegalBasis,
            PIPLComplianceRecord,
        )
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()

        bases = [
            LegalBasis.CONTRACT.value,
            LegalBasis.LEGAL_OBLIGATION.value,
            LegalBasis.VITAL_INTEREST.value,
            LegalBasis.PUBLIC_TASK.value,
            LegalBasis.LEGITIMATE_INTEREST.value,
        ]

        for basis in bases:
            record = PIPLComplianceRecord(
                personal_data_id=f"pd-{basis}",
                purpose="Test",
                legal_basis=basis,
                accessor="system",
                data_subject_id="user-123",
            )
            service.record_access(record)
            result = service.validate_legal_basis(f"pd-{basis}", basis)
            assert result is True


class TestPIPLComplianceServiceDataSubjectRights:
    """Test data subject rights functionality."""

    def test_respond_to_access_request(self):
        """Test responding to data subject access request."""
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()
        response = service.respond_to_access_request("user-123")

        assert "status" in response
        assert response["status"] == "available"

    def test_respond_to_correction_request(self):
        """Test responding to data subject correction request."""
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()
        corrections = {"name": "New Name", "email": "new@example.com"}
        response = service.respond_to_correction_request("user-123", corrections)

        assert "status" in response
        assert response["status"] == "processed"

    def test_respond_to_deletion_request(self):
        """Test responding to data subject deletion request."""
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()
        response = service.respond_to_deletion_request("user-123")

        assert "status" in response
        assert response["status"] == "deleted"

    def test_respond_to_portability_request(self):
        """Test responding to data subject portability request."""
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()
        response = service.respond_to_portability_request("user-123")

        assert "status" in response
        assert response["status"] == "available"
        assert "data" in response


class TestPIPLComplianceServiceMinorConsent:
    """Test minor consent functionality."""

    def test_validate_minor_consent_with_guardian_consent(self):
        """Test minor consent is valid with guardian consent."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            LegalBasis,
            PIPLComplianceRecord,
        )
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()

        record = PIPLComplianceRecord(
            personal_data_id="pd-minor",
            purpose="Education Service",
            legal_basis=LegalBasis.MINOR_CONSENT.value,
            consent_status=ConsentStatus.GIVEN,
            accessor="system",
            data_subject_id="user-minor",
            is_minor=True,
            guardian_consent_obtained=True,
        )

        service.record_access(record)

        # Validate the record
        stored = service.get_record("pd-minor")
        assert stored is not None
        assert stored.validate_minor_consent() is True

    def test_validate_minor_consent_without_guardian_consent(self):
        """Test minor consent is invalid without guardian consent."""
        from src.domain.entities.pipl_compliance_record import (
            ConsentStatus,
            LegalBasis,
            PIPLComplianceRecord,
        )
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        service = PIPLComplianceServiceImpl()

        record = PIPLComplianceRecord(
            personal_data_id="pd-minor",
            purpose="Education Service",
            legal_basis=LegalBasis.MINOR_CONSENT.value,
            consent_status=ConsentStatus.NOT_GIVEN,
            accessor="system",
            data_subject_id="user-minor",
            is_minor=True,
            guardian_consent_obtained=False,
        )

        service.record_access(record)

        stored = service.get_record("pd-minor")
        assert stored is not None
        assert stored.validate_minor_consent() is False


class TestPIPLComplianceServiceDataSubjectRightsWithData:
    """数据主体权利响应 — 含实际存储记录"""

    def _make_record(
        self,
        personal_data_id: str = "pd-test",
        data_subject_id: str = "user-ds-001",
        legal_basis: str | None = None,
        consent_status: ConsentStatus | None = None,
        accessed_at: datetime | None = None,
    ) -> PIPLComplianceRecord:
        """构造 PIPLComplianceRecord 辅助函数"""
        from src.domain.entities.pipl_compliance_record import LegalBasis

        return PIPLComplianceRecord(
            personal_data_id=personal_data_id,
            purpose="数据分析",
            legal_basis=legal_basis or LegalBasis.CONSENT.value,
            consent_status=consent_status if consent_status is not None else ConsentStatus.GIVEN,
            accessor="system",
            data_subject_id=data_subject_id,
            accessed_at=accessed_at if accessed_at is not None else datetime.now(tz=timezone.utc),
        )

    def test_access_request_returns_stored_records_with_timestamps(self) -> None:
        """访问请求应返回含 ISO 时间戳的完整记录"""
        service = PIPLComplianceServiceImpl()
        now = datetime.now(tz=timezone.utc)
        service.record_access(self._make_record("pd-a1", "user-ds-001", accessed_at=now))
        service.record_access(self._make_record("pd-a2", "user-ds-001", accessed_at=now))

        response = service.respond_to_access_request("user-ds-001")

        assert response["status"] == "available"
        assert len(response["records"]) == 2
        record_data = response["records"][0]
        assert "personal_data_id" in record_data
        assert "purpose" in record_data
        assert "legal_basis" in record_data
        assert record_data["accessed_at"] == now.isoformat()

    def test_access_request_filters_by_data_subject_id(self) -> None:
        """访问请求应仅返回匹配 data_subject_id 的记录"""
        service = PIPLComplianceServiceImpl()
        service.record_access(self._make_record("pd-b1", "user-ds-001"))
        service.record_access(self._make_record("pd-b2", "user-ds-002"))

        response = service.respond_to_access_request("user-ds-001")

        assert len(response["records"]) == 1
        assert response["records"][0]["personal_data_id"] == "pd-b1"

    def test_access_request_no_matching_records(self) -> None:
        """无匹配记录时应返回空列表"""
        service = PIPLComplianceServiceImpl()

        response = service.respond_to_access_request("unknown-user")

        assert response["status"] == "available"
        assert response["records"] == []

    def test_deletion_request_removes_records(self) -> None:
        """删除请求应实际移除匹配的记录"""
        service = PIPLComplianceServiceImpl()
        service.record_access(self._make_record("pd-d1", "user-ds-del"))
        service.record_access(self._make_record("pd-d2", "user-ds-del"))
        service.record_access(self._make_record("pd-d3", "user-ds-other"))

        response = service.respond_to_deletion_request("user-ds-del")

        assert response["status"] == "deleted"
        assert service.get_record("pd-d1") is None
        assert service.get_record("pd-d2") is None
        # 其他用户记录不受影响
        assert service.get_record("pd-d3") is not None

    def test_portability_request_returns_data_fields(self) -> None:
        """可携带权请求应返回 personal_data_id/purpose/legal_basis"""
        service = PIPLComplianceServiceImpl()
        service.record_access(self._make_record("pd-p1", "user-ds-port"))

        response = service.respond_to_portability_request("user-ds-port")

        assert response["status"] == "available"
        assert len(response["data"]) == 1
        data_item = response["data"][0]
        assert data_item["personal_data_id"] == "pd-p1"
        assert data_item["purpose"] == "数据分析"
        assert data_item["legal_basis"] is not None

    def test_portability_request_no_data(self) -> None:
        """无可携带数据时应返回空列表"""
        service = PIPLComplianceServiceImpl()

        response = service.respond_to_portability_request("no-such-user")

        assert response["data"] == []


class TestPIPLComplianceServiceEdgeCases:
    """PIPL 合规服务边界情况"""

    def test_get_record_not_found(self) -> None:
        """未记录的 ID 应返回 None"""
        service = PIPLComplianceServiceImpl()
        assert service.get_record("nonexistent-id") is None

    def test_validate_legal_basis_unknown_data_id(self) -> None:
        """未知的 data_id 应返回 False"""
        service = PIPLComplianceServiceImpl()
        result = service.validate_legal_basis("unknown-data-id", "consent")
        assert result is False

    def test_record_access_overwrites_existing(self) -> None:
        """相同 personal_data_id 再次记录应覆盖"""
        service = PIPLComplianceServiceImpl()
        record1 = self._make_record("pd-ov", "user-1", consent_status=ConsentStatus.GIVEN)
        record2 = self._make_record("pd-ov", "user-2", consent_status=ConsentStatus.WITHDRAWN)

        service.record_access(record1)
        service.record_access(record2)

        stored = service.get_record("pd-ov")
        assert stored is not None
        assert stored.data_subject_id == "user-2"
        assert stored.consent_status == ConsentStatus.WITHDRAWN

    def _make_record(
        self,
        personal_data_id: str,
        data_subject_id: str,
        consent_status: ConsentStatus = ConsentStatus.GIVEN,
    ) -> PIPLComplianceRecord:
        """构造 PIPLComplianceRecord 辅助函数"""
        return PIPLComplianceRecord(
            personal_data_id=personal_data_id,
            purpose="测试用途",
            legal_basis=LegalBasis.CONSENT.value,
            consent_status=consent_status,
            accessor="system",
            data_subject_id=data_subject_id,
        )
