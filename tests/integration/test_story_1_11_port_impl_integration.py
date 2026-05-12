"""Integration tests for Story 1.11 - Data Sovereignty Isolation.

集成测试目的：验证多个组件协同工作，跨层验证 port 接口与 implementation 实现正确对接。
不使用 mock，测试组件间的真实交互。

Run with: pytest tests/integration/test_story_1_11_port_impl_integration.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.domain.entities.cross_border_transfer import (
    CrossBorderTransferRequest,
    LegalBasisType,
    TransferStatus,
)
from src.domain.entities.data_residency_policy import DataResidencyPolicy, EnforcementLevel, Region
from src.domain.entities.external_api_whitelist import ExternalAPIWhitelist, RiskLevel
from src.domain.entities.pipl_compliance_record import (
    ConsentStatus,
    LegalBasis,
    PIPLComplianceRecord,
)
from src.domain.entities.sensitive_data_result import SensitiveDataResult
from src.domain.events.compliance_events import SensitiveType
from src.domain.value_objects.compliance_result import ComplianceResult
from src.domain.value_objects.udmr_task import UDMRTask
from src.infrastructure.security.compliance_gateway_impl import ComplianceGatewayImpl
from src.infrastructure.security.cross_border_transfer_service_impl import (
    CrossBorderTransferServiceImpl,
)
from src.infrastructure.security.data_residency_enforcer_impl import DataResidencyEnforcerImpl
from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl
from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl
from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

# ===================================================================
# AC-1: Sensitive Data Detection - Port + Impl Integration
# ===================================================================


class TestSensitiveDataDetectorIntegration:
    """集成测试：SensitiveDataDetectorPort 接口与 SensitiveDataDetectorImpl 实现协作"""

    def test_detect_pii_id_card_number(self):
        """测试检测身份证号 - 验证 port 接口调用 impl 实现"""
        detector = SensitiveDataDetectorImpl()
        content = "张三的身份证号是110101199001011234"
        result = detector.detect_sensitive_data(content)

        assert isinstance(result, SensitiveDataResult)
        assert SensitiveType.PII in result.sensitive_types
        assert result.confidence > 0.8

    def test_detect_trade_secret_keyword(self):
        """测试检测商业秘密关键词"""
        detector = SensitiveDataDetectorImpl()
        content = "公司核心技术配方保密"
        result = detector.detect_sensitive_data(content)

        assert isinstance(result, SensitiveDataResult)
        assert SensitiveType.TRADE_SECRET in result.sensitive_types

    def test_detect_financial_bank_account(self):
        """测试检测银行账号"""
        detector = SensitiveDataDetectorImpl()
        content = "银行账号6222021234567890123"
        result = detector.detect_sensitive_data(content)

        assert isinstance(result, SensitiveDataResult)
        assert SensitiveType.FINANCIAL in result.sensitive_types

    def test_detect_returns_sensitive_data_result_entity(self):
        """测试检测返回 SensitiveDataResult 实体"""
        detector = SensitiveDataDetectorImpl()
        result = detector.detect_sensitive_data("测试内容")
        assert result.is_high_confidence(threshold=0.5)


# ===================================================================
# AC-2: Data Residency - Port + Impl Integration
# ===================================================================


class TestDataResidencyEnforcerIntegration:
    """集成测试：DataResidencyEnforcerPort 接口与 DataResidencyEnforcerImpl 实现协作"""

    def test_enforce_blocks_overseas_for_strict_policy(self):
        """测试 STRICT 级别阻止海外传输"""
        enforcer = DataResidencyEnforcerImpl()
        policy = DataResidencyPolicy(
            allowed_regions=(Region.CHINA_DOMESTIC,),
            blocked_regions=(Region.OVERSEAS,),
            enforcement_level=EnforcementLevel.STRICT,
        )

        result = enforcer.enforce_residency(
            data="sensitive data",
            target_region=Region.OVERSEAS,
            policy=policy,
        )
        assert result is False

    def test_enforce_allows_domestic_for_strict_policy(self):
        """测试 STRICT 级别允许境内传输"""
        enforcer = DataResidencyEnforcerImpl()
        policy = DataResidencyPolicy(
            allowed_regions=(Region.CHINA_DOMESTIC,),
            blocked_regions=(Region.OVERSEAS,),
            enforcement_level=EnforcementLevel.STRICT,
        )

        result = enforcer.enforce_residency(
            data="domestic data",
            target_region=Region.CHINA_DOMESTIC,
            policy=policy,
        )
        assert result is True

    def test_strict_policy_requires_local_processing(self):
        """测试 STRICT 级别需要本地处理"""
        policy = DataResidencyPolicy(
            allowed_regions=(Region.CHINA_DOMESTIC,),
            blocked_regions=(Region.OVERSEAS,),
            enforcement_level=EnforcementLevel.STRICT,
        )
        assert policy.requires_local_processing() is True

    def test_policy_context_contains_required_fields(self):
        """测试策略上下文包含必需字段"""
        policy = DataResidencyPolicy(
            allowed_regions=(Region.CHINA_DOMESTIC,),
            blocked_regions=(Region.OVERSEAS,),
            enforcement_level=EnforcementLevel.STRICT,
        )
        ctx = policy.get_policy_context()
        assert "policy_id" in ctx
        assert "name" in ctx
        assert "allowed_regions" in ctx


# ===================================================================
# AC-3: Whitelist - Port + Impl Integration
# ===================================================================


class TestWhitelistServiceIntegration:
    """集成测试：WhitelistServicePort 接口与 WhitelistServiceImpl 实现协作"""

    def test_is_allowed_verified_valid_endpoint(self):
        """测试经验证的未过期 API 在白名单中"""
        service = WhitelistServiceImpl()
        entry = ExternalAPIWhitelist(
            endpoint="https://api.domestic.cn",
            is_verified=True,
            risk_level=RiskLevel.LOW,
            valid_until=datetime(2099, 12, 31, tzinfo=UTC),
        )
        service.add_to_whitelist(entry)

        assert service.is_allowed("https://api.domestic.cn") is True

    def test_is_allowed_unverified_endpoint(self):
        """测试未验证的 API 不在白名单"""
        service = WhitelistServiceImpl()
        entry = ExternalAPIWhitelist(
            endpoint="https://api.unverified.cn",
            is_verified=False,
            risk_level=RiskLevel.LOW,
            valid_until=datetime(2099, 12, 31, tzinfo=UTC),
        )
        service.add_to_whitelist(entry)

        assert service.is_allowed("https://api.unverified.cn") is False

    def test_is_valid_returns_false_for_expired(self):
        """测试过期条目返回 False"""
        entry = ExternalAPIWhitelist(
            endpoint="https://api.expired.cn",
            is_verified=True,
            risk_level=RiskLevel.LOW,
            valid_until=datetime(2020, 1, 1, tzinfo=UTC),
        )
        assert entry.is_valid() is False

    def test_high_risk_requires_dpo_approval(self):
        """测试高风险 API 需要 DPO 审批"""
        entry = ExternalAPIWhitelist(
            endpoint="https://api.risky.cn",
            is_verified=True,
            risk_level=RiskLevel.HIGH,
            valid_until=datetime(2099, 12, 31, tzinfo=UTC),
        )
        assert entry.requires_dpo_approval() is True
        assert entry.is_high_risk() is True

    def test_days_until_expiry_calculation(self):
        """测试距过期天数计算"""
        entry = ExternalAPIWhitelist(
            endpoint="https://api.example.com",
            is_verified=True,
            risk_level=RiskLevel.LOW,
            valid_until=datetime.now(UTC) + timedelta(days=10),
        )
        days = entry.days_until_expiry()
        assert days >= 9


# ===================================================================
# AC-4: Cross-Border Transfer - Port + Impl Integration
# ===================================================================


class TestCrossBorderTransferIntegration:
    """集成测试：CrossBorderTransferServicePort 接口与 CrossBorderTransferServiceImpl 实现协作"""

    def test_request_transfer_creates_pending_request(self):
        """测试发起传输请求创建待审批状态"""
        service = CrossBorderTransferServiceImpl()
        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Model Inference",
            requester="user-001",
            legal_basis_type=LegalBasisType.SCC,
        )

        service.request_transfer(request)
        stored = service.get_request(str(request.request_id))

        assert stored is not None
        assert stored.status == TransferStatus.PENDING
        assert stored.is_pending() is True

    def test_approve_changes_status_to_approved(self):
        """测试审批后状态变为 APPROVED"""
        service = CrossBorderTransferServiceImpl()
        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Model Inference",
            requester="user-001",
            legal_basis_type=LegalBasisType.SCC,
        )

        service.request_transfer(request)
        service.approve(str(request.request_id), "admin-001")
        updated = service.get_request(str(request.request_id))

        assert updated.status == TransferStatus.APPROVED
        assert updated.approver == "admin-001"
        assert updated.approval_timestamp is not None

    def test_reject_changes_status_to_rejected(self):
        """测试拒绝后状态变为 REJECTED"""
        service = CrossBorderTransferServiceImpl()
        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Model Inference",
            requester="user-001",
            legal_basis_type=LegalBasisType.SCC,
        )

        service.request_transfer(request)
        service.reject(str(request.request_id), "admin-001")
        updated = service.get_request(str(request.request_id))

        assert updated.status == TransferStatus.REJECTED

    def test_execute_after_approval_changes_status_to_executed(self):
        """测试审批通过后执行状态变为 EXECUTED"""
        service = CrossBorderTransferServiceImpl()
        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Model Inference",
            requester="user-001",
            legal_basis_type=LegalBasisType.SCC,
        )

        service.request_transfer(request)
        service.approve(str(request.request_id), "admin-001")
        service.execute(str(request.request_id))
        updated = service.get_request(str(request.request_id))

        assert updated.status == TransferStatus.EXECUTED

    def test_block_changes_status_to_blocked(self):
        """测试阻止后状态变为 BLOCKED"""
        service = CrossBorderTransferServiceImpl()
        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Model Inference",
            requester="user-001",
            legal_basis_type=LegalBasisType.SCC,
        )

        service.request_transfer(request)
        service.block(str(request.request_id))
        updated = service.get_request(str(request.request_id))

        assert updated.status == TransferStatus.BLOCKED

    def test_list_pending_requests(self):
        """测试列出待审批请求"""
        service = CrossBorderTransferServiceImpl()
        request1 = CrossBorderTransferRequest(
            data_id="data-1",
            destination="US",
            purpose="Inference 1",
            requester="user-001",
            legal_basis_type=LegalBasisType.SCC,
        )
        request2 = CrossBorderTransferRequest(
            data_id="data-2",
            destination="EU",
            purpose="Inference 2",
            requester="user-002",
            legal_basis_type=LegalBasisType.ADEQUACY_ASSESSMENT,
        )

        service.request_transfer(request1)
        service.request_transfer(request2)
        pending = service.list_pending_requests()

        assert len(pending) == 2

    def test_security_assessment_legal_basis_valid(self):
        """测试安全评估法律依据有效"""
        request = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Security Assessment",
            requester="user-001",
            legal_basis_type=LegalBasisType.SECURITY_ASSESSMENT,
        )
        assert request.legal_basis_type in [
            LegalBasisType.SCC,
            LegalBasisType.ADEQUACY_ASSESSMENT,
            LegalBasisType.SECURITY_ASSESSMENT,
        ]


# ===================================================================
# AC-5: PIPL Compliance - Port + Impl Integration
# ===================================================================


class TestPIPLComplianceServiceIntegration:
    """集成测试：PIPLComplianceServicePort 接口与 PIPLComplianceServiceImpl 实现协作"""

    def test_record_access_with_consent(self):
        """测试记录同意的个人信息访问"""
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
        stored = service.get_record("pd-123")

        assert stored is not None
        assert stored.consent_status == ConsentStatus.GIVEN

    def test_validate_legal_basis_with_given_consent(self):
        """测试同意状态下的法律依据验证"""
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

    def test_validate_legal_basis_with_withdrawn_consent(self):
        """测试撤回同意后法律依据无效"""
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

    def test_validate_legal_basis_legal_obligation_always_valid(self):
        """测试法定义务法律依据始终有效"""
        service = PIPLComplianceServiceImpl()
        record = PIPLComplianceRecord(
            personal_data_id="pd-456",
            purpose="Legal Compliance",
            legal_basis=LegalBasis.LEGAL_OBLIGATION.value,
            accessor="system",
            data_subject_id="user-789",
        )

        service.record_access(record)
        result = service.validate_legal_basis("pd-456", LegalBasis.LEGAL_OBLIGATION.value)
        assert result is True

    def test_respond_to_access_request(self):
        """测试响应数据主体访问请求"""
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

        response = service.respond_to_access_request("user-456")
        assert response["status"] == "available"
        assert len(response["records"]) == 1

    def test_respond_to_deletion_request(self):
        """测试响应数据主体删除请求"""
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

        response = service.respond_to_deletion_request("user-456")
        assert response["status"] == "deleted"
        assert service.get_record("pd-123") is None

    def test_validate_minor_consent_with_guardian(self):
        """测试未成年人有监护人同意时有效"""
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
        assert record.validate_minor_consent() is True

    def test_validate_minor_consent_without_guardian(self):
        """测试未成年人无监护人同意时无效"""
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
        assert record.validate_minor_consent() is False


# ===================================================================
# AC-6: Compliance Gateway - All Services Integration
# ===================================================================


class TestComplianceGatewayIntegration:
    """集成测试：ComplianceGateway 协调所有子服务"""

    def test_gateway_check_china_domestic_allows(self):
        """测试中国大陆数据驻留合规检查通过"""
        gateway = ComplianceGatewayImpl()
        task = UDMRTask(
            input="普通文本",
            data_residency="CHINA_DOMESTIC",
            preferred_model="xxx.xxx.xxx",
        )

        import asyncio

        result = asyncio.run(gateway.check(task))

        assert result.allowed is True

    def test_gateway_check_redirects_overseas_model_for_domestic_data(self):
        """测试使用海外模型处理国内数据被重定向到本地处理"""
        gateway = ComplianceGatewayImpl()
        task = UDMRTask(
            input="测试文本",
            data_residency="CHINA_DOMESTIC",
            preferred_model="openai/gpt-4",
        )

        import asyncio

        result = asyncio.run(gateway.check(task))

        assert result.allowed is True
        assert result.forced_local is True
        assert result.violation_type == "data_residency_violation"

    def test_gateway_check_blocks_model_not_in_whitelist(self):
        """测试白名单外模型被阻止"""
        gateway = ComplianceGatewayImpl()
        task = UDMRTask(
            input="测试文本",
            data_residency="CHINA_DOMESTIC",
            preferred_model="unauthorized/model",
            allowed_models=["approved/model-1", "approved/model-2"],
        )

        import asyncio

        result = asyncio.run(gateway.check(task))

        assert result.allowed is False
        assert result.violation_type == "model_not_in_whitelist"

    def test_gateway_with_sensitive_data_detector(self):
        """测试集成敏感数据检测服务"""
        from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl

        detector = SensitiveDataDetectorImpl()
        gateway = ComplianceGatewayImpl(sensitive_data_detector=detector)
        task = UDMRTask(
            input="张三的身份证号110101199001011234",
            data_residency="CHINA_DOMESTIC",
            preferred_model="xxx.xxx.xxx",
        )

        import asyncio

        result = asyncio.run(gateway.check(task))

        assert result.allowed is True
        assert result.forced_local is True

    def test_gateway_with_pipl_service(self):
        """测试集成 PIPL 合规服务"""
        from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl

        pipl_service = PIPLComplianceServiceImpl()
        gateway = ComplianceGatewayImpl(pipl_service=pipl_service)
        # Use text that matches personal data patterns
        task = UDMRTask(
            input="姓名：张三，手机号：13800138000",
            data_residency="CHINA_DOMESTIC",
            preferred_model="xxx.xxx.xxx",
        )

        import asyncio

        result = asyncio.run(gateway.check(task))

        assert result.allowed is True
        assert result.forced_local is True

    def test_gateway_with_cross_border_service(self):
        """测试集成跨境传输服务"""
        from src.infrastructure.security.cross_border_transfer_service_impl import CrossBorderTransferServiceImpl

        cross_border_service = CrossBorderTransferServiceImpl()
        gateway = ComplianceGatewayImpl(cross_border_service=cross_border_service)
        task = UDMRTask(
            input="测试跨境传输",
            data_residency="OVERSEAS",
            preferred_model="xxx.xxx.xxx",
        )

        import asyncio

        result = asyncio.run(gateway.check(task))

        assert result.allowed is True


# ===================================================================
# Architecture: Entity Immutability
# ===================================================================


class TestEntityImmutability:
    """验证领域实体的不可变性"""

    def test_sensitive_data_result_is_frozen(self):
        """测试 SensitiveDataResult 不可修改"""
        result = SensitiveDataResult(
            sensitive_types=(SensitiveType.PII,),
            confidence=0.9,
        )
        with pytest.raises(AttributeError):
            result.confidence = 0.5

    def test_data_residency_policy_is_frozen(self):
        """测试 DataResidencyPolicy 不可修改"""
        policy = DataResidencyPolicy(
            allowed_regions=(Region.CHINA_DOMESTIC,),
            blocked_regions=(Region.OVERSEAS,),
            enforcement_level=EnforcementLevel.STRICT,
        )
        with pytest.raises(AttributeError):
            policy.enforcement_level = EnforcementLevel.RELAXED

    def test_external_api_whitelist_is_frozen(self):
        """测试 ExternalAPIWhitelist 不可修改"""
        entry = ExternalAPIWhitelist(
            endpoint="https://api.example.com",
            is_verified=True,
            risk_level=RiskLevel.LOW,
            valid_until=datetime(2099, 12, 31, tzinfo=UTC),
        )
        with pytest.raises(AttributeError):
            entry.is_verified = False

    def test_pipl_compliance_record_is_frozen(self):
        """测试 PIPLComplianceRecord 不可修改"""
        record = PIPLComplianceRecord(
            personal_data_id="pd-123",
            purpose="Analytics",
            legal_basis=LegalBasis.CONSENT.value,
            consent_status=ConsentStatus.GIVEN,
            accessor="system",
            data_subject_id="user-456",
        )
        with pytest.raises(AttributeError):
            record.consent_status = ConsentStatus.WITHDRAWN


# ===================================================================
# Architecture: ComplianceResult Value Object
# ===================================================================


class TestComplianceResultValueObject:
    """测试 ComplianceResult 值对象"""

    def test_compliance_result_is_frozen(self):
        """测试 ComplianceResult 不可修改"""
        result = ComplianceResult(
            allowed=True,
            reason="Compliant",
        )
        with pytest.raises(AttributeError):
            result.allowed = False

    def test_is_allowed_method(self):
        """测试 is_allowed 方法"""
        result = ComplianceResult(allowed=True)
        assert result.is_allowed() is True

    def test_is_violation_method(self):
        """测试 is_violation 方法"""
        result = ComplianceResult(
            allowed=False,
            violation_type="unauthorized_transfer",
        )
        assert result.is_violation() is True

    def test_get_violation_type_method(self):
        """测试 get_violation_type 方法"""
        result = ComplianceResult(
            allowed=False,
            violation_type="data_residency_violation",
        )
        assert result.get_violation_type() == "data_residency_violation"


# ===================================================================
# Architecture: Task Value Object
# ===================================================================


class TestTaskValueObject:
    """测试 Task 值对象"""

    def test_task_is_frozen(self):
        """测试 Task 不可修改"""
        task = UDMRTask(
            input="test",
            data_residency="CHINA_DOMESTIC",
        )
        with pytest.raises(AttributeError):
            task.data_residency = "OVERSEAS"

    def test_is_china_domestic_method(self):
        """测试 is_china_domestic 方法"""
        task = UDMRTask(data_residency="CHINA_DOMESTIC")
        assert task.is_china_domestic() is True

    def test_requires_local_processing_method(self):
        """测试 requires_local_processing 方法"""
        task = UDMRTask(data_residency="CHINA_DOMESTIC")
        assert task.requires_local_processing() is True

    def test_get_task_context_method(self):
        """测试 get_task_context 方法"""
        task = UDMRTask(
            input="test input",
            data_residency="CHINA_DOMESTIC",
            preferred_model="xxx.xxx.xxx",
        )
        ctx = task.get_task_context()
        assert "task_id" in ctx
        assert "data_residency" in ctx
        assert ctx["data_residency"] == "CHINA_DOMESTIC"
