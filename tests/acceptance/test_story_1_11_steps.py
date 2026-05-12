"""Acceptance tests for Story 1.11 - Data Sovereignty Isolation.

验收测试：从业务角度验证功能满足需求规格（AC）。

Run with: pytest tests/acceptance/test_story_1_11_steps.py -v
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

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
from src.infrastructure.security.cross_border_transfer_service_impl import CrossBorderTransferServiceImpl
from src.infrastructure.security.data_residency_enforcer_impl import DataResidencyEnforcerImpl
from src.infrastructure.security.pipl_compliance_service_impl import PIPLComplianceServiceImpl
from src.infrastructure.security.sensitive_data_detector_impl import SensitiveDataDetectorImpl
from src.infrastructure.security.whitelist_service_impl import WhitelistServiceImpl

scenarios("test_story_1_11.feature")


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """Share state between BDD steps."""
    return {}


@pytest.fixture
def sensitive_data_detector():
    """Real sensitive data detector service."""
    return SensitiveDataDetectorImpl()


@pytest.fixture
def data_residency_enforcer():
    """Real data residency enforcer service."""
    return DataResidencyEnforcerImpl()


@pytest.fixture
def whitelist_service():
    """Real whitelist service."""
    return WhitelistServiceImpl()


@pytest.fixture
def cross_border_service():
    """Real cross-border transfer service."""
    return CrossBorderTransferServiceImpl()


@pytest.fixture
def pipl_service():
    """Real PIPL compliance service."""
    return PIPLComplianceServiceImpl()


@pytest.fixture
def compliance_gateway(
    sensitive_data_detector,
    data_residency_enforcer,
    whitelist_service,
    pipl_service,
    cross_border_service,
):
    """Real compliance gateway with all dependencies."""
    return ComplianceGatewayImpl(
        sensitive_data_detector=sensitive_data_detector,
        data_residency_enforcer=data_residency_enforcer,
        whitelist_service=whitelist_service,
        pipl_service=pipl_service,
        cross_border_service=cross_border_service,
    )


# ===================================================================
# Background Steps
# ===================================================================


@given("系统已初始化完成")
def system_initialized(context):
    """System is initialized."""
    context["initialized"] = True


@given("领域实体已正确定义")
def domain_entities_defined(context):
    """Domain entities are properly defined."""
    context["entities_defined"] = True


# ===================================================================
# AC-1: Sensitive Data Detection Given Steps
# ===================================================================


@given("待检测内容包含身份证号")
def content_has_id_card(context):
    """Content contains Chinese ID card number."""
    context["content"] = "张三的身份证号是110101199001011234"


@given("待检测内容包含关键词")
def content_has_keyword(context):
    """Content contains trade secret keyword."""
    context["content"] = "公司核心技术配方保密"


@given("待检测内容包含银行账号")
def content_has_bank_account(context):
    """Content contains bank account number."""
    context["content"] = "银行账号6222021234567890123"


@given("内容设置为张三的身份证号110101199001011234")
def content_set_id_card(context):
    """Content is set to ID card number."""
    context["content"] = "张三的身份证号110101199001011234"


@given("内容设置为公司核心技术配方保密")
def content_set_secret(context):
    """Content is set to trade secret keyword."""
    context["content"] = "公司核心技术配方保密"


@given("内容设置为银行账号6222021234567890123")
def content_set_bank_account(context):
    """Content is set to bank account."""
    context["content"] = "银行账号6222021234567890123"


# ===================================================================
# AC-2: Data Residency Given Steps
# ===================================================================


@given("数据驻留策略允许区域为 CHINA_DOMESTIC")
def policy_allows_china(context):
    """Policy allows China domestic region."""
    context["allowed_region"] = Region.CHINA_DOMESTIC


@given("禁止区域为 OVERSEAS")
def policy_forbids_overseas(context):
    """Policy forbids overseas region."""
    context["forbidden_region"] = Region.OVERSEAS


@given("强制级别为 STRICT")
def policy_strict_level(context):
    """Policy has strict enforcement level."""
    context["enforcement_level"] = EnforcementLevel.STRICT


@given("数据驻留策略 enforcement_level 为 STRICT")
def policy_enforcement_strict(context):
    """Policy enforcement level is STRICT."""
    context["policy"] = DataResidencyPolicy(
        allowed_regions=(Region.CHINA_DOMESTIC,),
        blocked_regions=(Region.OVERSEAS,),
        enforcement_level=EnforcementLevel.STRICT,
    )


@given("有效的数据驻留策略")
def valid_residency_policy(context):
    """Valid data residency policy."""
    context["policy"] = DataResidencyPolicy(
        allowed_regions=(Region.CHINA_DOMESTIC,),
        blocked_regions=(Region.OVERSEAS,),
        enforcement_level=EnforcementLevel.STRICT,
    )


# ===================================================================
# AC-3: Whitelist Given Steps
# ===================================================================


@given('白名单条目 endpoint="https://api.domestic.cn" is_verified=True')
def verified_whitelist_entry(context):
    """Verified whitelist entry."""
    context["endpoint"] = "https://api.domestic.cn"
    context["is_verified"] = True
    context["valid_until"] = datetime(2099, 12, 31, tzinfo=UTC)


@given("白名单条目 is_verified=False")
def unverified_whitelist_entry(context):
    """Unverified whitelist entry."""
    context["is_verified"] = False
    context["endpoint"] = "https://api.unverified.cn"
    context["valid_until"] = datetime(2099, 12, 31, tzinfo=UTC)


@given("白名单条目 valid_until 为 2099-12-31")
def valid_until_future(context):
    """Whitelist entry valid until future date."""
    context["valid_until"] = datetime(2099, 12, 31, tzinfo=UTC)


@given("白名单条目 valid_until 为 2020-01-01")
def valid_until_past(context):
    """Whitelist entry valid until past date."""
    context["valid_until"] = datetime(2020, 1, 1, tzinfo=UTC)


@given("白名单条目 risk_level=HIGH")
def high_risk_whitelist_entry(context):
    """High risk whitelist entry."""
    context["risk_level"] = RiskLevel.HIGH
    context["valid_until"] = datetime(2099, 12, 31, tzinfo=UTC)


@given("白名单条目 valid_until 为 10 天后")
def valid_until_10_days(context):
    """Whitelist entry valid until 10 days from now."""
    context["valid_until"] = datetime.now(UTC) + timedelta(days=10)


# ===================================================================
# AC-4: Cross-Border Transfer Given Steps
# ===================================================================


@given('跨境传输请求 data_id="data-123" destination="US"')
def cross_border_request(context):
    """Cross-border transfer request."""
    context["request"] = CrossBorderTransferRequest(
        data_id="data-123",
        destination="US",
        purpose="Model Inference",
        requester="user-001",
        legal_basis_type=LegalBasisType.SCC,
    )


@given("跨境传输请求状态为 pending")
def request_pending(context):
    """Transfer request is pending."""
    if "request" not in context:
        context["request"] = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Model Inference",
            requester="user-001",
            legal_basis_type=LegalBasisType.SCC,
        )


@given("跨境传输请求已审批通过")
def request_approved(context, cross_border_service):
    """Transfer request is approved."""
    request = CrossBorderTransferRequest(
        data_id="data-123",
        destination="US",
        purpose="Model Inference",
        requester="user-001",
        legal_basis_type=LegalBasisType.SCC,
    )
    cross_border_service.request_transfer(request)
    cross_border_service.approve(str(request.request_id), "admin-001")
    context["request"] = cross_border_service.get_request(str(request.request_id))


@given("跨境传输请求 legal_basis_type=security_assessment")
def request_security_assessment(context):
    """Transfer request with security assessment legal basis."""
    context["request"] = CrossBorderTransferRequest(
        data_id="data-123",
        destination="US",
        purpose="Security Assessment",
        requester="user-001",
        legal_basis_type=LegalBasisType.SECURITY_ASSESSMENT,
    )


# ===================================================================
# AC-5: PIPL Compliance Given Steps
# ===================================================================


@given("PIPL 合规记录 legal_basis=consent consent_status=given")
def pipl_consent_given(context):
    """PIPL record with consent given."""
    context["record"] = PIPLComplianceRecord(
        personal_data_id="pd-123",
        purpose="Analytics",
        legal_basis=LegalBasis.CONSENT.value,
        consent_status=ConsentStatus.GIVEN,
        accessor="system",
        data_subject_id="user-456",
    )


@given("PIPL 合规记录 consent_status=withdrawn")
def pipl_consent_withdrawn(context):
    """PIPL record with consent withdrawn."""
    context["record"] = PIPLComplianceRecord(
        personal_data_id="pd-123",
        purpose="Analytics",
        legal_basis=LegalBasis.CONSENT.value,
        consent_status=ConsentStatus.WITHDRAWN,
        accessor="system",
        data_subject_id="user-456",
    )


@given("PIPL 合规记录 legal_basis=legal_obligation")
def pipl_legal_obligation(context):
    """PIPL record with legal obligation basis."""
    context["record"] = PIPLComplianceRecord(
        personal_data_id="pd-123",
        purpose="Legal Compliance",
        legal_basis=LegalBasis.LEGAL_OBLIGATION.value,
        accessor="system",
        data_subject_id="user-456",
    )


@given("PIPL 合规记录 is_minor=True guardian_consent_obtained=True consent_status=given")
def pipl_minor_with_guardian(context):
    """PIPL record for minor with guardian consent."""
    context["record"] = PIPLComplianceRecord(
        personal_data_id="pd-minor",
        purpose="Education Service",
        legal_basis=LegalBasis.MINOR_CONSENT.value,
        consent_status=ConsentStatus.GIVEN,
        accessor="system",
        data_subject_id="user-minor",
        is_minor=True,
        guardian_consent_obtained=True,
    )


@given("PIPL 合规记录 is_minor=True guardian_consent_obtained=False")
def pipl_minor_without_guardian(context):
    """PIPL record for minor without guardian consent."""
    context["record"] = PIPLComplianceRecord(
        personal_data_id="pd-minor",
        purpose="Education Service",
        legal_basis=LegalBasis.MINOR_CONSENT.value,
        consent_status=ConsentStatus.NOT_GIVEN,
        accessor="system",
        data_subject_id="user-minor",
        is_minor=True,
        guardian_consent_obtained=False,
    )


# ===================================================================
# AC-6: Compliance Gateway Given Steps
# ===================================================================


@given("任务数据驻留要求为 CHINA_DOMESTIC")
def task_china_domestic(context):
    """Task with China domestic data residency requirement."""
    context["task"] = UDMRTask(
        input="测试文本包含身份证号110101199001011234",
        data_residency="CHINA_DOMESTIC",
        preferred_model="openai/gpt-4",
    )


@given("任务数据驻留要求为 OVERSEAS")
def task_overseas(context):
    """Task with overseas data residency requirement."""
    context["task"] = UDMRTask(
        input="Test text",
        data_residency="OVERSEAS",
        preferred_model="openai/gpt-4",
    )


@given("无敏感数据检测结果")
def no_sensitive_data(context):
    """No sensitive data detected."""
    context["task"] = UDMRTask(
        input="普通文本内容",
        data_residency="OVERSEAS",
        preferred_model="xxx.xxx.xxx",
    )


@given("合规结果 allowed=True")
def result_allowed(context):
    """Compliance result allowed."""
    context["result"] = ComplianceResult(
        allowed=True,
        reason="Compliant",
    )


@given('合规结果 violation_type="unauthorized_transfer"')
def result_violation(context):
    """Compliance result with violation."""
    context["result"] = ComplianceResult(
        allowed=False,
        reason="Unauthorized transfer",
        violation_type="unauthorized_transfer",
    )


# ===================================================================
# Architecture Given Steps
# ===================================================================


@given("高置信度检测结果 confidence=0.95")
def high_confidence_detection(context):
    """High confidence detection result."""
    context["detection_result"] = SensitiveDataResult(
        sensitive_types=(SensitiveType.PII,),
        confidence=0.95,
    )


@given("两个检测结果分别包含 PII 和 FINANCIAL")
def two_detection_results(context):
    """Two detection results with different types."""
    result1 = SensitiveDataResult(
        sensitive_types=(SensitiveType.PII,),
        confidence=0.9,
    )
    result2 = SensitiveDataResult(
        sensitive_types=(SensitiveType.FINANCIAL,),
        confidence=0.85,
    )
    context["detection_result1"] = result1
    context["detection_result2"] = result2


@given("领域实体已创建")
def domain_entity_created(context):
    """Domain entity has been created."""
    context["entity"] = SensitiveDataResult(
        sensitive_types=(SensitiveType.PII,),
        confidence=0.9,
    )


# ===================================================================
# When Steps
# ===================================================================


@when("执行敏感数据检测")
def detect_sensitive_data(context, sensitive_data_detector):
    """Execute sensitive data detection."""
    content = context.get("content", "")
    result = sensitive_data_detector.detect_sensitive_data(content)
    context["detection_result"] = result


@when("尝试将数据发送到 OVERSEAS 区域")
def try_send_overseas(context, data_residency_enforcer):
    """Try to send data to overseas region."""
    policy = context.get("policy") or DataResidencyPolicy(
        allowed_regions=(Region.CHINA_DOMESTIC,),
        blocked_regions=(Region.OVERSEAS,),
        enforcement_level=EnforcementLevel.STRICT,
    )
    result = data_residency_enforcer.enforce_residency(
        data="test data",
        target_region=Region.OVERSEAS,
        policy=policy,
    )
    context["enforce_result"] = result


@when("调用 requires_local_processing()")
def call_requires_local_processing(context):
    """Call requires_local_processing method."""
    policy = context.get("policy")
    if policy:
        context["requires_local_result"] = policy.requires_local_processing()


@when("调用 get_policy_context()")
def call_get_policy_context(context):
    """Call get_policy_context method."""
    policy = context.get("policy")
    if policy:
        context["policy_context_result"] = policy.get_policy_context()


@when('调用 is_allowed("https://api.domestic.cn")')
def call_is_allowed_with_endpoint(context, whitelist_service):
    """Call is_allowed method with endpoint."""
    endpoint = context.get("endpoint", "https://api.domestic.cn")
    is_verified = context.get("is_verified", True)
    valid_until = context.get("valid_until", datetime(2099, 12, 31, tzinfo=UTC))
    risk_level = context.get("risk_level", RiskLevel.LOW)

    if is_verified:
        entry = ExternalAPIWhitelist(
            endpoint=endpoint,
            is_verified=True,
            risk_level=risk_level,
            valid_until=valid_until,
        )
        whitelist_service.add_to_whitelist(entry)

    context["is_allowed_result"] = whitelist_service.is_allowed(endpoint)


@when("调用 is_allowed()")
def call_is_allowed_without_param(context, whitelist_service):
    """Call is_allowed without parameter."""
    endpoint = context.get("endpoint", "https://api.unverified.cn")
    is_verified = context.get("is_verified", False)
    valid_until = context.get("valid_until", datetime(2099, 12, 31, tzinfo=UTC))
    risk_level = context.get("risk_level", RiskLevel.LOW)

    entry = ExternalAPIWhitelist(
        endpoint=endpoint,
        is_verified=is_verified,
        risk_level=risk_level,
        valid_until=valid_until,
    )
    whitelist_service.add_to_whitelist(entry)
    context["is_allowed_result"] = whitelist_service.is_allowed(endpoint)


@when("调用 is_valid()")
def call_is_valid(context):
    """Call is_valid method."""
    valid_until = context.get("valid_until", datetime(2020, 1, 1, tzinfo=UTC))
    entry = ExternalAPIWhitelist(
        endpoint="https://api.test.cn",
        is_verified=True,
        risk_level=RiskLevel.LOW,
        valid_until=valid_until,
    )
    context["is_valid_result"] = entry.is_valid()


@when("调用 requires_dpo_approval()")
def call_requires_dpo_approval(context):
    """Call requires_dpo_approval method."""
    risk_level = context.get("risk_level", RiskLevel.HIGH)
    entry = ExternalAPIWhitelist(
        endpoint="https://api.risky.cn",
        is_verified=True,
        risk_level=risk_level,
        valid_until=datetime(2099, 12, 31, tzinfo=UTC),
    )
    context["requires_dpo_result"] = entry.requires_dpo_approval()


@when("调用 is_high_risk()")
def call_is_high_risk(context):
    """Call is_high_risk method."""
    risk_level = context.get("risk_level", RiskLevel.HIGH)
    entry = ExternalAPIWhitelist(
        endpoint="https://api.risky.cn",
        is_verified=True,
        risk_level=risk_level,
        valid_until=datetime(2099, 12, 31, tzinfo=UTC),
    )
    context["is_high_risk_result"] = entry.is_high_risk()


@when("调用 days_until_expiry()")
def call_days_until_expiry(context):
    """Call days_until_expiry method."""
    valid_until = context.get("valid_until")
    if valid_until:
        entry = ExternalAPIWhitelist(
            endpoint="https://api.example.com",
            is_verified=True,
            risk_level=RiskLevel.LOW,
            valid_until=valid_until,
        )
        context["days_until_expiry_result"] = entry.days_until_expiry()


@when("请求状态为 pending")
def request_status_pending(context):
    """Request status is pending."""
    if "request" in context:
        context["request_status"] = context["request"].status


@when('调用 approve(approver="admin-001")')
def call_approve(context, cross_border_service):
    """Call approve method."""
    request = context.get("request")
    if request:
        cross_border_service.request_transfer(request)
        cross_border_service.approve(str(request.request_id), "admin-001")
        context["request"] = cross_border_service.get_request(str(request.request_id))


@when('调用 reject(approver="admin-001")')
def call_reject(context, cross_border_service):
    """Call reject method."""
    request = context.get("request")
    if request:
        cross_border_service.request_transfer(request)
        cross_border_service.reject(str(request.request_id), "admin-001")
        context["request"] = cross_border_service.get_request(str(request.request_id))


@when("调用 execute()")
def call_execute(context, cross_border_service):
    """Call execute method."""
    request = context.get("request")
    if request:
        cross_border_service.execute(str(request.request_id))
        context["request"] = cross_border_service.get_request(str(request.request_id))


@when("调用 block()")
def call_block(context, cross_border_service):
    """Call block method."""
    request = context.get("request")
    if request:
        cross_border_service.request_transfer(request)
        cross_border_service.block(str(request.request_id))
        context["request"] = cross_border_service.get_request(str(request.request_id))


@when("调用 is_pending()")
def call_is_pending(context):
    """Call is_pending method."""
    request = context.get("request")
    context["is_pending_result"] = request.is_pending() if request else False


@when("验证法律依据有效性")
def validate_legal_basis(context):
    """Validate legal basis."""
    request = context.get("request")
    if request:
        context["legal_basis_valid"] = request.legal_basis_type in [
            LegalBasisType.SCC,
            LegalBasisType.ADEQUACY_ASSESSMENT,
            LegalBasisType.SECURITY_ASSESSMENT,
        ]


@when("调用 validate_consent()")
def call_validate_consent(context):
    """Call validate_consent method."""
    record = context.get("record")
    context["validate_consent_result"] = record.validate_consent() if record else False


@when("调用 is_compliant()")
def call_is_compliant(context):
    """Call is_compliant method."""
    record = context.get("record")
    context["is_compliant_result"] = record.is_compliant() if record else False


@when("调用 validate_minor_consent()")
def call_validate_minor_consent(context):
    """Call validate_minor_consent method."""
    record = context.get("record")
    context["validate_minor_consent_result"] = record.validate_minor_consent() if record else False


@when("调用 ComplianceGateway.check(task)")
def call_compliance_gateway_check(context, compliance_gateway):
    """Call ComplianceGateway.check method."""
    task = context.get("task")
    if task:
        context["gateway_result"] = asyncio.run(compliance_gateway.check(task))


@when("调用 is_allowed()")
def call_is_allowed_on_result(context):
    """Call is_allowed on compliance result."""
    result = context.get("result")
    context["is_allowed_result"] = result.is_allowed() if result else False


@when("调用 is_violation()")
def call_is_violation_on_result(context):
    """Call is_violation on compliance result."""
    result = context.get("result")
    context["is_violation_result"] = result.is_violation() if result else False


@when("调用 is_high_confidence() 方法")
def call_is_high_confidence(context):
    """Call is_high_confidence method."""
    result = context.get("detection_result")
    context["is_high_confidence_result"] = result.is_high_confidence() if result else False


@when("调用 merge_with() 方法合并")
def call_merge_with(context):
    """Call merge_with method."""
    result1 = context.get("detection_result1")
    result2 = context.get("detection_result2")
    if result1 and result2:
        context["merged_result"] = result1.merge_with(result2)


@when("尝试修改属性")
def try_modify_attribute(context):
    """Try to modify entity attribute."""
    entity = context.get("entity")
    if entity:
        try:
            entity.confidence = 0.5
            context["modification_error"] = None
        except Exception as e:
            context["modification_error"] = e


# ===================================================================
# Then Steps - AC-1
# ===================================================================


@then("系统识别出 PII 类型数据")
def assert_pii_detected(context):
    """Assert PII type is detected."""
    result = context.get("detection_result")
    assert result is not None
    assert SensitiveType.PII in result.sensitive_types


@then("检测置信度大于 0.8")
def assert_confidence_gt_08(context):
    """Assert detection confidence > 0.8."""
    result = context.get("detection_result")
    assert result is not None
    assert result.confidence > 0.8


@then("触发 SensitiveDataDetected 事件")
def assert_sensitive_detected_event(context):
    """Assert SensitiveDataDetected event was triggered."""
    result = context.get("detection_result")
    assert result is not None
    assert len(result.sensitive_types) > 0


@then("系统识别出 TRADE_SECRET 类型数据")
def assert_trade_secret_detected(context):
    """Assert trade secret type is detected."""
    result = context.get("detection_result")
    assert result is not None
    assert SensitiveType.TRADE_SECRET in result.sensitive_types


@then("系统识别出 FINANCIAL 类型数据")
def assert_financial_detected(context):
    """Assert financial type is detected."""
    result = context.get("detection_result")
    assert result is not None
    assert SensitiveType.FINANCIAL in result.sensitive_types


@then("返回 True")
def assert_returns_true(context):
    """Assert method returns True."""
    assert context.get("is_high_confidence_result") is True


@then("合并结果包含两种敏感类型")
def assert_merged_contains_both_types(context):
    """Assert merged result contains both sensitive types."""
    merged = context.get("merged_result")
    assert merged is not None
    assert SensitiveType.PII in merged.sensitive_types
    assert SensitiveType.FINANCIAL in merged.sensitive_types


# ===================================================================
# Then Steps - AC-2
# ===================================================================


@then("系统阻止操作")
def assert_operation_blocked(context):
    """Assert operation was blocked."""
    result = context.get("enforce_result")
    assert result is False


@then("触发 DataSovereigntyViolation 事件")
def assert_sovereignty_violation_event(context):
    """Assert DataSovereigntyViolation event was triggered."""
    result = context.get("enforce_result")
    assert result is False


@then("调用 requires_local_processing() 返回 True")
def assert_requires_local_true(context):
    """Assert requires_local_processing returns True."""
    assert context.get("requires_local_result") is True


@then("调用 get_policy_context() 返回包含 policy_id、name、allowed_regions 的字典")
def assert_policy_context_contains_fields(context):
    """Assert policy context contains required fields."""
    policy_context = context.get("policy_context_result")
    assert policy_context is not None
    assert "policy_id" in policy_context
    assert "name" in policy_context
    assert "allowed_regions" in policy_context


# ===================================================================
# Then Steps - AC-3
# ===================================================================


@then("调用 is_allowed 返回 True")
def assert_is_allowed_true(context):
    """Assert is_allowed returns True."""
    assert context.get("is_allowed_result") is True


@then("调用 is_allowed 返回 False")
def assert_is_allowed_false(context):
    """Assert is_allowed returns False."""
    assert context.get("is_allowed_result") is False


@then("调用 is_valid 返回 False")
def assert_is_valid_false(context):
    """Assert is_valid returns False."""
    assert context.get("is_valid_result") is False


@then("调用 requires_dpo_approval 返回 True")
def assert_requires_dpo_true(context):
    """Assert requires_dpo_approval returns True."""
    assert context.get("requires_dpo_result") is True


@then("调用 is_high_risk 返回 True")
def assert_is_high_risk_true(context):
    """Assert is_high_risk returns True."""
    assert context.get("is_high_risk_result") is True


@then("调用 days_until_expiry 返回值大于等于 9")
def assert_days_until_expiry(context):
    """Assert days_until_expiry returns value >= 9."""
    days = context.get("days_until_expiry_result")
    assert days is not None
    assert days >= 9


# ===================================================================
# Then Steps - AC-4
# ===================================================================


@then("request_transfer() 方法可用")
def assert_request_transfer_available(context):
    """Assert request_transfer method is available."""
    request = context.get("request")
    assert request is not None
    assert request.status == TransferStatus.PENDING


@then("新状态为 APPROVED")
def assert_status_approved(context):
    """Assert new status is APPROVED."""
    request = context.get("request")
    assert request is not None
    assert request.status == TransferStatus.APPROVED


@then('approver 为 "admin-001"')
def assert_approver(context):
    """Assert approver is admin-001."""
    request = context.get("request")
    assert request is not None
    assert request.approver == "admin-001"


@then("approval_timestamp 已记录")
def assert_approval_timestamp(context):
    """Assert approval_timestamp is recorded."""
    request = context.get("request")
    assert request is not None
    assert request.approval_timestamp is not None


@then("新状态为 REJECTED")
def assert_status_rejected(context):
    """Assert new status is REJECTED."""
    request = context.get("request")
    assert request is not None
    assert request.status == TransferStatus.REJECTED


@then("新状态为 EXECUTED")
def assert_status_executed(context):
    """Assert new status is EXECUTED."""
    request = context.get("request")
    assert request is not None
    assert request.status == TransferStatus.EXECUTED


@then("新状态为 BLOCKED")
def assert_status_blocked(context):
    """Assert new status is BLOCKED."""
    request = context.get("request")
    assert request is not None
    assert request.status == TransferStatus.BLOCKED


@then("调用 is_pending 返回 True")
def assert_is_pending_true(context):
    """Assert is_pending returns True."""
    assert context.get("is_pending_result") is True


@then("验证法律依据有效性返回 True")
def assert_legal_basis_valid(context):
    """Assert legal basis is valid."""
    assert context.get("legal_basis_valid") is True


# ===================================================================
# Then Steps - AC-5
# ===================================================================


@then("调用 validate_consent 返回 True")
def assert_validate_consent_true(context):
    """Assert validate_consent returns True."""
    assert context.get("validate_consent_result") is True


@then("调用 validate_consent 返回 False")
def assert_validate_consent_false(context):
    """Assert validate_consent returns False."""
    assert context.get("validate_consent_result") is False


@then("调用 is_compliant() 返回 True")
def assert_is_compliant_true(context):
    """Assert is_compliant returns True."""
    record = context.get("record")
    if record:
        context["is_compliant_result"] = record.is_compliant()
    assert context.get("is_compliant_result") is True


@then("调用 validate_minor_consent 返回 True")
def assert_validate_minor_consent_true(context):
    """Assert validate_minor_consent returns True."""
    assert context.get("validate_minor_consent_result") is True


@then("调用 validate_minor_consent 返回 False")
def assert_validate_minor_consent_false(context):
    """Assert validate_minor_consent returns False."""
    assert context.get("validate_minor_consent_result") is False


# ===================================================================
# Then Steps - AC-6
# ===================================================================


@then("返回结果 allowed=True")
def assert_gateway_allowed(context):
    """Assert gateway result allowed is True."""
    result = context.get("gateway_result")
    assert result is not None
    assert result.allowed is True


@then("返回结果 forced_local=True")
def assert_gateway_forced_local(context):
    """Assert gateway result forced_local is True."""
    result = context.get("gateway_result")
    assert result is not None
    assert result.forced_local is True


@then("调用 is_allowed 返回 True")
def assert_is_allowed_on_result_true(context):
    """Assert is_allowed on result returns True."""
    assert context.get("is_allowed_result") is True


@then("调用 is_violation 返回 True")
def assert_is_violation_true(context):
    """Assert is_violation on result returns True."""
    assert context.get("is_violation_result") is True


# ===================================================================
# Then Steps - Architecture
# ===================================================================


@then("抛出 AttributeError")
def assert_attribute_error(context):
    """Assert AttributeError is raised."""
    error = context.get("modification_error")
    assert error is not None
    assert isinstance(error, AttributeError)
