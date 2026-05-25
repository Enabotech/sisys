"""等保2.0三级综合合规验证测试

等保2.0三级10个安全层面综合验证:
- SC-1: 身份鉴别验证
- SC-2: 访问控制验证
- SC-3: 安全审计验证
- SC-4: 入侵防范验证
- SC-5: 数据完整性验证
- SC-6: 备份恢复验证
- SC-7: 合规报告生成

本测试验证 EquilibriumComplianceVerifier 的等保综合合规验证

对应 Story: 1-12-equilibrium-level-3-compliance Task 5 Subtask 5.1-5.13
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.security.equilibrium_compliance_verifier import (
    ComplianceReport,
    ComplianceStatus,
    EquilibriumComplianceVerifier,
    SecurityDomainResult,
)


@pytest.fixture
def compliance_verifier() -> EquilibriumComplianceVerifier:
    """创建等保合规验证器实例（含 mock 依赖）"""
    mock_auth_service = AsyncMock()
    mock_permission_service = AsyncMock()
    mock_audit_service = AsyncMock()
    mock_intrusion_service = AsyncMock()
    mock_integrity_service = AsyncMock()
    mock_backup_service = AsyncMock()

    # 配置 mock 返回值
    mock_auth_service._login_attempt_repo = AsyncMock()
    mock_permission_service.check_permission = AsyncMock(return_value=False)
    mock_audit_service.record = AsyncMock(return_value=MagicMock(actor="test", action_type="login"))
    mock_intrusion_service.detect_attack = AsyncMock(
        return_value=MagicMock(detected=False, attack_type="", severity="", action_taken="logged")
    )
    mock_integrity_service.calculate_checksum = AsyncMock(return_value="a" * 64)
    mock_backup_service.create_backup = AsyncMock(
        return_value=MagicMock(success=True, backup_id="test-backup", backup_type="postgresql")
    )

    return EquilibriumComplianceVerifier(
        auth_service=mock_auth_service,
        permission_service=mock_permission_service,
        audit_service=mock_audit_service,
        intrusion_service=mock_intrusion_service,
        integrity_service=mock_integrity_service,
        backup_service=mock_backup_service,
    )


class TestIdentityAuthenticationVerification:
    """身份鉴别验证 (SC-1)"""

    async def test_verify_identity_authentication(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """验证身份鉴别合规"""
        result = await compliance_verifier.verify_identity_authentication()
        assert isinstance(result, SecurityDomainResult)
        assert result.domain == "identity_authentication"
        assert result.status in [ComplianceStatus.COMPLIANT, ComplianceStatus.NON_COMPLIANT]

    async def test_identity_auth_checks_password_policy(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """身份鉴别验证应包含密码策略检查"""
        result = await compliance_verifier.verify_identity_authentication()
        assert "password_policy" in result.checks
        assert "lockout_mechanism" in result.checks
        assert "mfa_support" in result.checks


class TestAccessControlVerification:
    """访问控制验证 (SC-2)"""

    async def test_verify_access_control(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """验证访问控制合规"""
        result = await compliance_verifier.verify_access_control()
        assert isinstance(result, SecurityDomainResult)
        assert result.domain == "access_control"

    async def test_access_control_checks_rbac(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """访问控制验证应包含RBAC检查"""
        result = await compliance_verifier.verify_access_control()
        assert "rbac_enforcement" in result.checks
        assert "privilege_escalation_protection" in result.checks


class TestSecurityAuditVerification:
    """安全审计验证 (SC-3)"""

    async def test_verify_security_audit(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """验证安全审计合规"""
        result = await compliance_verifier.verify_security_audit()
        assert isinstance(result, SecurityDomainResult)
        assert result.domain == "security_audit"

    async def test_audit_checks_event_recording(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """安全审计验证应包含事件记录检查"""
        result = await compliance_verifier.verify_security_audit()
        assert "event_recording" in result.checks
        assert "integrity_verification" in result.checks


class TestIntrusionPreventionVerification:
    """入侵防范验证 (SC-4)"""

    async def test_verify_intrusion_prevention(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """验证入侵防范合规"""
        result = await compliance_verifier.verify_intrusion_prevention()
        assert isinstance(result, SecurityDomainResult)
        assert result.domain == "intrusion_prevention"

    async def test_intrusion_checks_detection_capability(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """入侵防范验证应包含检测能力检查"""
        result = await compliance_verifier.verify_intrusion_prevention()
        assert "attack_detection" in result.checks
        assert "ip_blocking" in result.checks


class TestDataIntegrityVerification:
    """数据完整性验证 (SC-5)"""

    async def test_verify_data_integrity(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """验证数据完整性合规"""
        result = await compliance_verifier.verify_data_integrity()
        assert isinstance(result, SecurityDomainResult)
        assert result.domain == "data_integrity"

    async def test_integrity_checks_checksum(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """数据完整性验证应包含校验和检查"""
        result = await compliance_verifier.verify_data_integrity()
        assert "checksum_algorithm" in result.checks
        assert "tamper_detection" in result.checks


class TestBackupRecoveryVerification:
    """备份恢复验证 (SC-6)"""

    async def test_verify_backup_recovery(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """验证备份恢复合规"""
        result = await compliance_verifier.verify_backup_recovery()
        assert isinstance(result, SecurityDomainResult)
        assert result.domain == "backup_recovery"

    async def test_backup_checks_mechanism(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """备份恢复验证应包含备份机制检查"""
        result = await compliance_verifier.verify_backup_recovery()
        assert "backup_mechanism" in result.checks
        assert "restore_capability" in result.checks


class TestComprehensiveReport:
    """合规报告生成验证 (SC-7)"""

    async def test_generate_compliance_report(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """生成等保合规报告"""
        report = await compliance_verifier.generate_report()
        assert isinstance(report, ComplianceReport)
        assert report.total_domains > 0
        assert isinstance(report.results, list)
        assert len(report.results) == report.total_domains

    async def test_report_contains_all_domains(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """合规报告应包含所有安全层面"""
        report = await compliance_verifier.generate_report()
        domains = [r.domain for r in report.results]
        assert "identity_authentication" in domains
        assert "access_control" in domains
        assert "security_audit" in domains
        assert "intrusion_prevention" in domains
        assert "data_integrity" in domains
        assert "backup_recovery" in domains

    async def test_report_has_compliance_score(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """合规报告应包含合规评分"""
        report = await compliance_verifier.generate_report()
        assert hasattr(report, "compliance_score")
        assert 0.0 <= report.compliance_score <= 1.0

    async def test_report_has_summary(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """合规报告应包含摘要信息"""
        report = await compliance_verifier.generate_report()
        assert hasattr(report, "compliant_count")
        assert hasattr(report, "non_compliant_count")
        assert report.compliant_count + report.non_compliant_count == report.total_domains


class TestSecurityDomainResultStructure:
    """安全层面结果结构验证"""

    async def test_result_has_required_fields(
        self,
        compliance_verifier: EquilibriumComplianceVerifier,
    ) -> None:
        """安全层面结果应包含所有必需字段"""
        result = await compliance_verifier.verify_identity_authentication()
        assert hasattr(result, "domain")
        assert hasattr(result, "status")
        assert hasattr(result, "checks")
        assert hasattr(result, "score")
        assert 0.0 <= result.score <= 1.0
