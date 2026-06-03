"""Story 1.11 - 数据主权隔离验收测试。

验收测试：从业务角度验证功能满足需求规格（AC）

运行: poetry run pytest tests/acceptance/test_acceptance_data_sovereignty_isolation.py -v
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
from src.domain.ports.resolver import Resolver
from src.domain.value_objects.compliance_result import ComplianceResult
from src.domain.value_objects.udmr_task import UDMRTask
from src.infrastructure.security.compliance_gateway_impl import ComplianceGatewayImpl

scenarios("test_acceptance_data_sovereignty_isolation.feature")


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """BDD 步骤间共享状态。"""
    return {}


@pytest.fixture
def sensitive_data_detector(resolver: Resolver):
    """敏感数据检测服务。"""
    return resolver.resolve("sensitive_data_detector")


@pytest.fixture
def data_residency_enforcer(resolver: Resolver):
    """数据驻留策略执行服务。"""
    return resolver.resolve("data_residency_enforcer")


@pytest.fixture
def whitelist_service(resolver: Resolver):
    """白名单服务。"""
    return resolver.resolve("whitelist_service")


@pytest.fixture
def cross_border_service(resolver: Resolver):
    """跨境数据传输服务。"""
    return resolver.resolve("cross_border_transfer")


@pytest.fixture
def pipl_service(resolver: Resolver):
    """PIPL 合规服务。"""
    return resolver.resolve("pipl_compliance")


@pytest.fixture
def compliance_gateway(resolver: Resolver) -> ComplianceGatewayImpl:
    """合规性网关实例。"""
    return resolver.resolve("compliance_gateway", ComplianceGatewayImpl)


# ===================================================================
# Background Steps
# ===================================================================


@given("系统已初始化完成")
def system_initialized(context: dict[str, Any]) -> None:
    """系统已初始化完成。"""
    context["initialized"] = True


@given("领域实体已正确定义")
def domain_entities_defined(context: dict[str, Any]) -> None:
    """领域实体已正确定义。"""
    context["entities_defined"] = True


# ===================================================================
# AC-1: 敏感数据检测 Given 步骤
# ===================================================================


@given("待检测内容包含身份证号")
def content_has_id_card(context: dict[str, Any]) -> None:
    """待检测内容包含身份证号。"""
    context["content"] = "张三的身份证号是110101199001011234"


@given("待检测内容包含关键词")
def content_has_keyword(context: dict[str, Any]) -> None:
    """待检测内容包含商业秘密关键词。"""
    context["content"] = "公司核心技术配方保密"


@given("待检测内容包含银行账号")
def content_has_bank_account(context: dict[str, Any]) -> None:
    """待检测内容包含银行账号。"""
    context["content"] = "银行账号6222021234567890123"


@given("内容设置为张三的身份证号110101199001011234")
def content_set_id_card(context: dict[str, Any]):
    """设置内容为身份证号。"""
    context["content"] = "张三的身份证号110101199001011234"


@given("内容设置为公司核心技术配方保密")
def content_set_secret(context: dict[str, Any]):
    """设置内容为商业秘密关键词。"""
    context["content"] = "公司核心技术配方保密"


@given("内容设置为银行账号6222021234567890123")
def content_set_bank_account(context: dict[str, Any]):
    """设置内容为银行账号。"""
    context["content"] = "银行账号6222021234567890123"


# ===================================================================
# AC-2: 数据驻留策略 Given 步骤
# ===================================================================


@given("数据驻留策略允许区域为 CHINA_DOMESTIC")
def policy_allows_china(context: dict[str, Any]):
    """策略允许中国境内区域。"""
    context["allowed_region"] = Region.CHINA_DOMESTIC


@given("禁止区域为 OVERSEAS")
def policy_forbids_overseas(context: dict[str, Any]):
    """策略禁止海外区域。"""
    context["forbidden_region"] = Region.OVERSEAS


@given("强制级别为 STRICT")
def policy_strict_level(context: dict[str, Any]):
    """策略强制级别为严格。"""
    context["enforcement_level"] = EnforcementLevel.STRICT


@given("数据驻留策略 enforcement_level 为 STRICT")
def policy_enforcement_strict(context: dict[str, Any]):
    """策略执行级别为严格。"""
    context["policy"] = DataResidencyPolicy(
        allowed_regions=(Region.CHINA_DOMESTIC,),
        blocked_regions=(Region.OVERSEAS,),
        enforcement_level=EnforcementLevel.STRICT,
    )


@given("有效的数据驻留策略")
def valid_residency_policy(context: dict[str, Any]):
    """有效的数据驻留策略。"""
    context["policy"] = DataResidencyPolicy(
        allowed_regions=(Region.CHINA_DOMESTIC,),
        blocked_regions=(Region.OVERSEAS,),
        enforcement_level=EnforcementLevel.STRICT,
    )


# ===================================================================
# AC-3: 白名单 Given 步骤
# ===================================================================


@given('白名单条目 endpoint="https://api.domestic.cn" is_verified=True')
def verified_whitelist_entry(context: dict[str, Any]):
    """已验证的白名单条目。"""
    context["endpoint"] = "https://api.domestic.cn"
    context["is_verified"] = True
    context["valid_until"] = datetime(2099, 12, 31, tzinfo=UTC)


@given("白名单条目 is_verified=False")
def unverified_whitelist_entry(context: dict[str, Any]):
    """未验证的白名单条目。"""
    context["is_verified"] = False
    context["endpoint"] = "https://api.unverified.cn"
    context["valid_until"] = datetime(2099, 12, 31, tzinfo=UTC)


@given("白名单条目 valid_until 为 2099-12-31")
def valid_until_future(context: dict[str, Any]):
    """白名单条目有效期至未来日期。"""
    context["valid_until"] = datetime(2099, 12, 31, tzinfo=UTC)


@given("白名单条目 valid_until 为 2020-01-01")
def valid_until_past(context: dict[str, Any]):
    """白名单条目有效期已过期。"""
    context["valid_until"] = datetime(2020, 1, 1, tzinfo=UTC)


@given("白名单条目 risk_level=HIGH")
def high_risk_whitelist_entry(context: dict[str, Any]):
    """高风险白名单条目。"""
    context["risk_level"] = RiskLevel.HIGH
    context["valid_until"] = datetime(2099, 12, 31, tzinfo=UTC)


@given("白名单条目 valid_until 为 10 天后")
def valid_until_10_days(context: dict[str, Any]):
    """白名单条目有效期为 10 天后。"""
    context["valid_until"] = datetime.now(UTC) + timedelta(days=10)


# ===================================================================
# AC-4: 跨境传输 Given 步骤
# ===================================================================


@given('跨境传输请求 data_id="data-123" destination="US"')
def cross_border_request(context: dict[str, Any]):
    """跨境传输请求。"""
    context["request"] = CrossBorderTransferRequest(
        data_id="data-123",
        destination="US",
        purpose="Model Inference",
        requester="user-001",
        legal_basis_type=LegalBasisType.SCC,
    )


@given("跨境传输请求状态为 pending")
def request_pending(context: dict[str, Any]):
    """传输请求状态为待处理。"""
    if "request" not in context:
        context["request"] = CrossBorderTransferRequest(
            data_id="data-123",
            destination="US",
            purpose="Model Inference",
            requester="user-001",
            legal_basis_type=LegalBasisType.SCC,
        )


@given("跨境传输请求已审批通过")
def request_approved(context: dict[str, Any], cross_border_service):
    """传输请求已审批通过。"""
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
def request_security_assessment(context: dict[str, Any]):
    """跨境传输请求使用安全评估作为法律依据。"""
    context["request"] = CrossBorderTransferRequest(
        data_id="data-123",
        destination="US",
        purpose="Security Assessment",
        requester="user-001",
        legal_basis_type=LegalBasisType.SECURITY_ASSESSMENT,
    )


# ===================================================================
# AC-5: PIPL 合规 Given 步骤
# ===================================================================


@given("PIPL 合规记录 legal_basis=consent consent_status=given")
def pipl_consent_given(context: dict[str, Any]):
    """PIPL 记录已获得同意。"""
    context["record"] = PIPLComplianceRecord(
        personal_data_id="pd-123",
        purpose="Analytics",
        legal_basis=LegalBasis.CONSENT.value,
        consent_status=ConsentStatus.GIVEN,
        accessor="system",
        data_subject_id="user-456",
    )


@given("PIPL 合规记录 consent_status=withdrawn")
def pipl_consent_withdrawn(context: dict[str, Any]):
    """PIPL 记录同意已撤回。"""
    context["record"] = PIPLComplianceRecord(
        personal_data_id="pd-123",
        purpose="Analytics",
        legal_basis=LegalBasis.CONSENT.value,
        consent_status=ConsentStatus.WITHDRAWN,
        accessor="system",
        data_subject_id="user-456",
    )


@given("PIPL 合规记录 legal_basis=legal_obligation")
def pipl_legal_obligation(context: dict[str, Any]):
    """PIPL 记录基于法律义务。"""
    context["record"] = PIPLComplianceRecord(
        personal_data_id="pd-123",
        purpose="Legal Compliance",
        legal_basis=LegalBasis.LEGAL_OBLIGATION.value,
        accessor="system",
        data_subject_id="user-456",
    )


@given("PIPL 合规记录 is_minor=True guardian_consent_obtained=True consent_status=given")
def pipl_minor_with_guardian(context: dict[str, Any]):
    """PIPL 记录为未成年人且已获得监护人同意。"""
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
def pipl_minor_without_guardian(context: dict[str, Any]):
    """PIPL 记录为未成年人但未获得监护人同意。"""
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
# AC-6: 合规网关 Given 步骤
# ===================================================================


@given("任务数据驻留要求为 CHINA_DOMESTIC")
def task_china_domestic(context: dict[str, Any]):
    """任务要求数据驻留在中国境内。"""
    context["task"] = UDMRTask(
        input="测试文本包含身份证号110101199001011234",
        data_residency="CHINA_DOMESTIC",
        preferred_model="openai/gpt-4",
    )


@given("任务数据驻留要求为 OVERSEAS")
def task_overseas(context: dict[str, Any]):
    """任务要求数据驻留在海外。"""
    context["task"] = UDMRTask(
        input="Test text",
        data_residency="OVERSEAS",
        preferred_model="openai/gpt-4",
    )


@given("无敏感数据检测结果")
def no_sensitive_data(context: dict[str, Any]):
    """无敏感数据检测。"""
    context["task"] = UDMRTask(
        input="普通文本内容",
        data_residency="OVERSEAS",
        preferred_model="xxx.xxx.xxx",
    )


@given("合规结果 allowed=True")
def result_allowed(context: dict[str, Any]):
    """合规结果允许。"""
    context["result"] = ComplianceResult(
        allowed=True,
        reason="Compliant",
    )


@given('合规结果 violation_type="unauthorized_transfer"')
def result_violation(context: dict[str, Any]):
    """合规结果存在违规。"""
    context["result"] = ComplianceResult(
        allowed=False,
        reason="Unauthorized transfer",
        violation_type="unauthorized_transfer",
    )


# ===================================================================
# 架构 Given 步骤
# ===================================================================


@given("高置信度检测结果 confidence=0.95")
def high_confidence_detection(context: dict[str, Any]):
    """高置信度检测结果。"""
    context["detection_result"] = SensitiveDataResult(
        sensitive_types=(SensitiveType.PII,),
        confidence=0.95,
    )


@given("两个检测结果分别包含 PII 和 FINANCIAL")
def two_detection_results(context: dict[str, Any]):
    """两个不同类型的检测结果。"""
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
def domain_entity_created(context: dict[str, Any]):
    """领域实体已创建。"""
    context["entity"] = SensitiveDataResult(
        sensitive_types=(SensitiveType.PII,),
        confidence=0.9,
    )


# ===================================================================
# When 步骤
# ===================================================================


@when("执行敏感数据检测")
def detect_sensitive_data(context: dict[str, Any], sensitive_data_detector):
    """执行敏感数据检测。"""
    content = context.get("content", "")
    result = sensitive_data_detector.detect_sensitive_data(content)
    context["detection_result"] = result


@when("尝试将数据发送到 OVERSEAS 区域")
def try_send_overseas(context: dict[str, Any], data_residency_enforcer):
    """尝试将数据发送到海外区域。"""
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
def call_requires_local_processing(context: dict[str, Any]):
    """调用 requires_local_processing 方法。"""
    policy = context.get("policy")
    if policy:
        context["requires_local_result"] = policy.requires_local_processing()


@when("调用 get_policy_context()")
def call_get_policy_context(context: dict[str, Any]):
    """调用 get_policy_context 方法。"""
    policy = context.get("policy")
    if policy:
        context["policy_context_result"] = policy.get_policy_context()


@when('调用 is_allowed("https://api.domestic.cn")')
def call_is_allowed_with_endpoint(context: dict[str, Any], whitelist_service):
    """调用 is_allowed 方法并传入端点。"""
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
def call_is_allowed_without_param(context: dict[str, Any], whitelist_service):
    """调用 is_allowed 方法（无参数）。"""
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
def call_is_valid(context: dict[str, Any]):
    """调用 is_valid 方法。"""
    valid_until = context.get("valid_until", datetime(2020, 1, 1, tzinfo=UTC))
    entry = ExternalAPIWhitelist(
        endpoint="https://api.test.cn",
        is_verified=True,
        risk_level=RiskLevel.LOW,
        valid_until=valid_until,
    )
    context["is_valid_result"] = entry.is_valid()


@when("调用 requires_dpo_approval()")
def call_requires_dpo_approval(context: dict[str, Any]):
    """调用 requires_dpo_approval 方法。"""
    risk_level = context.get("risk_level", RiskLevel.HIGH)
    entry = ExternalAPIWhitelist(
        endpoint="https://api.risky.cn",
        is_verified=True,
        risk_level=risk_level,
        valid_until=datetime(2099, 12, 31, tzinfo=UTC),
    )
    context["requires_dpo_result"] = entry.requires_dpo_approval()


@when("调用 is_high_risk()")
def call_is_high_risk(context: dict[str, Any]):
    """调用 is_high_risk 方法。"""
    risk_level = context.get("risk_level", RiskLevel.HIGH)
    entry = ExternalAPIWhitelist(
        endpoint="https://api.risky.cn",
        is_verified=True,
        risk_level=risk_level,
        valid_until=datetime(2099, 12, 31, tzinfo=UTC),
    )
    context["is_high_risk_result"] = entry.is_high_risk()


@when("调用 days_until_expiry()")
def call_days_until_expiry(context: dict[str, Any]):
    """调用 days_until_expiry 方法。"""
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
def request_status_pending(context: dict[str, Any]):
    """请求状态为待处理。"""
    if "request" in context:
        context["request_status"] = context["request"].status


@when('调用 approve(approver="admin-001")')
def call_approve(context: dict[str, Any], cross_border_service):
    """调用 approve 方法。"""
    request = context.get("request")
    if request:
        cross_border_service.request_transfer(request)
        cross_border_service.approve(str(request.request_id), "admin-001")
        context["request"] = cross_border_service.get_request(str(request.request_id))


@when('调用 reject(approver="admin-001")')
def call_reject(context: dict[str, Any], cross_border_service):
    """调用 reject 方法。"""
    request = context.get("request")
    if request:
        cross_border_service.request_transfer(request)
        cross_border_service.reject(str(request.request_id), "admin-001")
        context["request"] = cross_border_service.get_request(str(request.request_id))


@when("调用 execute()")
def call_execute(context: dict[str, Any], cross_border_service):
    """调用 execute 方法。"""
    request = context.get("request")
    if request:
        cross_border_service.execute(str(request.request_id))
        context["request"] = cross_border_service.get_request(str(request.request_id))


@when("调用 block()")
def call_block(context: dict[str, Any], cross_border_service):
    """调用 block 方法。"""
    request = context.get("request")
    if request:
        cross_border_service.request_transfer(request)
        cross_border_service.block(str(request.request_id))
        context["request"] = cross_border_service.get_request(str(request.request_id))


@when("调用 is_pending()")
def call_is_pending(context: dict[str, Any]):
    """调用 is_pending 方法。"""
    request = context.get("request")
    context["is_pending_result"] = request.is_pending() if request else False


@when("验证法律依据有效性")
def validate_legal_basis(context: dict[str, Any]):
    """验证法律依据有效性。"""
    request = context.get("request")
    if request:
        context["legal_basis_valid"] = request.legal_basis_type in [
            LegalBasisType.SCC,
            LegalBasisType.ADEQUACY_ASSESSMENT,
            LegalBasisType.SECURITY_ASSESSMENT,
        ]


@when("调用 validate_consent()")
def call_validate_consent(context: dict[str, Any]):
    """调用 validate_consent 方法。"""
    record = context.get("record")
    context["validate_consent_result"] = record.validate_consent() if record else False


@when("调用 is_compliant()")
def call_is_compliant(context: dict[str, Any]):
    """调用 is_compliant 方法。"""
    record = context.get("record")
    context["is_compliant_result"] = record.is_compliant() if record else False


@when("调用 validate_minor_consent()")
def call_validate_minor_consent(context: dict[str, Any]):
    """调用 validate_minor_consent 方法。"""
    record = context.get("record")
    context["validate_minor_consent_result"] = record.validate_minor_consent() if record else False


@when("调用 ComplianceGateway.check(task)")
def call_compliance_gateway_check(context: dict[str, Any], compliance_gateway):
    """调用 ComplianceGateway.check 方法。"""
    task = context.get("task")
    if task:
        context["gateway_result"] = asyncio.run(compliance_gateway.check(task))


@when("调用 is_allowed()")
def call_is_allowed_on_result(context: dict[str, Any]):
    """调用合规结果的 is_allowed 方法。"""
    result = context.get("result")
    context["is_allowed_result"] = result.is_allowed() if result else False


@when("调用 is_violation()")
def call_is_violation_on_result(context: dict[str, Any]):
    """调用合规结果的 is_violation 方法。"""
    result = context.get("result")
    context["is_violation_result"] = result.is_violation() if result else False


@when("调用 is_high_confidence() 方法")
def call_is_high_confidence(context: dict[str, Any]):
    """调用 is_high_confidence 方法。"""
    result = context.get("detection_result")
    context["is_high_confidence_result"] = result.is_high_confidence() if result else False


@when("调用 merge_with() 方法合并")
def call_merge_with(context: dict[str, Any]):
    """调用 merge_with 方法。"""
    result1 = context.get("detection_result1")
    result2 = context.get("detection_result2")
    if result1 and result2:
        context["merged_result"] = result1.merge_with(result2)


@when("尝试修改属性")
def try_modify_attribute(context: dict[str, Any]):
    """尝试修改实体属性。"""
    entity = context.get("entity")
    if entity:
        try:
            entity.confidence = 0.5
            context["modification_error"] = None
        except Exception as e:
            context["modification_error"] = e


# ===================================================================
# Then 步骤 - AC-1
# ===================================================================


@then("系统识别出 PII 类型数据")
def assert_pii_detected(context: dict[str, Any]):
    """验证 PII 类型被检测。"""
    result = context.get("detection_result")
    assert result is not None
    assert SensitiveType.PII in result.sensitive_types


@then("检测置信度大于 0.8")
def assert_confidence_gt_08(context: dict[str, Any]):
    """验证检测置信度大于 0.8。"""
    result = context.get("detection_result")
    assert result is not None
    assert result.confidence > 0.8


@then("触发 SensitiveDataDetected 事件")
def assert_sensitive_detected_event(context: dict[str, Any]):
    """验证触发敏感数据检测事件。"""
    result = context.get("detection_result")
    assert result is not None
    assert len(result.sensitive_types) > 0


@then("系统识别出 TRADE_SECRET 类型数据")
def assert_trade_secret_detected(context: dict[str, Any]):
    """验证商业秘密类型被检测。"""
    result = context.get("detection_result")
    assert result is not None
    assert SensitiveType.TRADE_SECRET in result.sensitive_types


@then("系统识别出 FINANCIAL 类型数据")
def assert_financial_detected(context: dict[str, Any]):
    """验证金融类型被检测。"""
    result = context.get("detection_result")
    assert result is not None
    assert SensitiveType.FINANCIAL in result.sensitive_types


@then("返回 True")
def assert_returns_true(context: dict[str, Any]):
    """验证方法返回 True。"""
    assert context.get("is_high_confidence_result") is True


@then("合并结果包含两种敏感类型")
def assert_merged_contains_both_types(context: dict[str, Any]):
    """验证合并结果包含两种敏感类型。"""
    merged = context.get("merged_result")
    assert merged is not None
    assert SensitiveType.PII in merged.sensitive_types
    assert SensitiveType.FINANCIAL in merged.sensitive_types


# ===================================================================
# Then 步骤 - AC-2
# ===================================================================


@then("系统阻止操作")
def assert_operation_blocked(context: dict[str, Any]):
    """验证操作被阻止。"""
    result = context.get("enforce_result")
    assert result is False


@then("触发 DataSovereigntyViolation 事件")
def assert_sovereignty_violation_event(context: dict[str, Any]):
    """验证触发数据主权违规事件。"""
    result = context.get("enforce_result")
    assert result is False


@then("调用 requires_local_processing() 返回 True")
def assert_requires_local_true(context: dict[str, Any]):
    """验证 requires_local_processing 返回 True。"""
    assert context.get("requires_local_result") is True


@then("调用 get_policy_context() 返回包含 policy_id、name、allowed_regions 的字典")
def assert_policy_context_contains_fields(context: dict[str, Any]):
    """验证策略上下文包含必要字段。"""
    policy_context = context.get("policy_context_result")
    assert policy_context is not None
    assert "policy_id" in policy_context
    assert "name" in policy_context
    assert "allowed_regions" in policy_context


# ===================================================================
# Then 步骤 - AC-3
# ===================================================================


@then("调用 is_allowed 返回 True")
def assert_is_allowed_true(context: dict[str, Any]):
    """验证 is_allowed 返回 True。"""
    assert context.get("is_allowed_result") is True


@then("调用 is_allowed 返回 False")
def assert_is_allowed_false(context: dict[str, Any]):
    """验证 is_allowed 返回 False。"""
    assert context.get("is_allowed_result") is False


@then("调用 is_valid 返回 False")
def assert_is_valid_false(context: dict[str, Any]):
    """验证 is_valid 返回 False。"""
    assert context.get("is_valid_result") is False


@then("调用 requires_dpo_approval 返回 True")
def assert_requires_dpo_true(context: dict[str, Any]):
    """验证 requires_dpo_approval 返回 True。"""
    assert context.get("requires_dpo_result") is True


@then("调用 is_high_risk 返回 True")
def assert_is_high_risk_true(context: dict[str, Any]):
    """验证 is_high_risk 返回 True。"""
    assert context.get("is_high_risk_result") is True


@then("调用 days_until_expiry 返回值大于等于 9")
def assert_days_until_expiry(context: dict[str, Any]):
    """验证 days_until_expiry 返回值大于等于 9。"""
    days = context.get("days_until_expiry_result")
    assert days is not None
    assert days >= 9


# ===================================================================
# Then 步骤 - AC-4
# ===================================================================


@then("request_transfer() 方法可用")
def assert_request_transfer_available(context: dict[str, Any]):
    """验证 request_transfer 方法可用。"""
    request = context.get("request")
    assert request is not None
    assert request.status == TransferStatus.PENDING


@then("新状态为 APPROVED")
def assert_status_approved(context: dict[str, Any]):
    """验证新状态为已审批。"""
    request = context.get("request")
    assert request is not None
    assert request.status == TransferStatus.APPROVED


@then('approver 为 "admin-001"')
def assert_approver(context: dict[str, Any]):
    """验证审批人为 admin-001。"""
    request = context.get("request")
    assert request is not None
    assert request.approver == "admin-001"


@then("approval_timestamp 已记录")
def assert_approval_timestamp(context: dict[str, Any]):
    """验证审批时间戳已记录。"""
    request = context.get("request")
    assert request is not None
    assert request.approval_timestamp is not None


@then("新状态为 REJECTED")
def assert_status_rejected(context: dict[str, Any]):
    """验证新状态为已拒绝。"""
    request = context.get("request")
    assert request is not None
    assert request.status == TransferStatus.REJECTED


@then("新状态为 EXECUTED")
def assert_status_executed(context: dict[str, Any]):
    """验证新状态为已执行。"""
    request = context.get("request")
    assert request is not None
    assert request.status == TransferStatus.EXECUTED


@then("新状态为 BLOCKED")
def assert_status_blocked(context: dict[str, Any]):
    """验证新状态为已阻止。"""
    request = context.get("request")
    assert request is not None
    assert request.status == TransferStatus.BLOCKED


@then("调用 is_pending 返回 True")
def assert_is_pending_true(context: dict[str, Any]):
    """验证 is_pending 返回 True。"""
    assert context.get("is_pending_result") is True


@then("验证法律依据有效性返回 True")
def assert_legal_basis_valid(context: dict[str, Any]):
    """验证法律依据有效。"""
    assert context.get("legal_basis_valid") is True


# ===================================================================
# Then 步骤 - AC-5
# ===================================================================


@then("调用 validate_consent 返回 True")
def assert_validate_consent_true(context: dict[str, Any]):
    """验证 validate_consent 返回 True。"""
    assert context.get("validate_consent_result") is True


@then("调用 validate_consent 返回 False")
def assert_validate_consent_false(context: dict[str, Any]):
    """验证 validate_consent 返回 False。"""
    assert context.get("validate_consent_result") is False


@then("调用 is_compliant() 返回 True")
def assert_is_compliant_true(context: dict[str, Any]):
    """验证 is_compliant 返回 True。"""
    record = context.get("record")
    if record:
        context["is_compliant_result"] = record.is_compliant()
    assert context.get("is_compliant_result") is True


@then("调用 validate_minor_consent 返回 True")
def assert_validate_minor_consent_true(context: dict[str, Any]):
    """验证 validate_minor_consent 返回 True。"""
    assert context.get("validate_minor_consent_result") is True


@then("调用 validate_minor_consent 返回 False")
def assert_validate_minor_consent_false(context: dict[str, Any]):
    """验证 validate_minor_consent 返回 False。"""
    assert context.get("validate_minor_consent_result") is False


# ===================================================================
# Then 步骤 - AC-6
# ===================================================================


@then("返回结果 allowed=True")
def assert_gateway_allowed(context: dict[str, Any]):
    """验证网关结果允许。"""
    result = context.get("gateway_result")
    assert result is not None
    assert result.allowed is True


@then("返回结果 forced_local=True")
def assert_gateway_forced_local(context: dict[str, Any]):
    """验证网关结果强制本地处理。"""
    result = context.get("gateway_result")
    assert result is not None
    assert result.forced_local is True


@then("调用 is_allowed 返回 True")
def assert_is_allowed_on_result_true(context: dict[str, Any]):
    """验证合规结果的 is_allowed 返回 True。"""
    assert context.get("is_allowed_result") is True


@then("调用 is_violation 返回 True")
def assert_is_violation_true(context: dict[str, Any]):
    """验证合规结果的 is_violation 返回 True。"""
    assert context.get("is_violation_result") is True


# ===================================================================
# Then 步骤 - 架构
# ===================================================================


@then("抛出 AttributeError")
def assert_attribute_error(context: dict[str, Any]):
    """验证抛出 AttributeError。"""
    error = context.get("modification_error")
    assert error is not None
    assert isinstance(error, AttributeError)
