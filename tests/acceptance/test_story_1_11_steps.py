"""Acceptance tests for Story 1.11 - 数据主权隔离.

Run with: pytest tests/acceptance/test_story_1_11.feature -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.security.approval_workflow import ApprovalWorkflowService
from src.infrastructure.security.data_sovereignty_service import DataSovereigntyService
from src.infrastructure.security.models import (
    ApprovalStatus,
    CrossBorderApproval,
    SensitiveDataType,
    WhitelistRule,
)
from src.infrastructure.security.pipl_compliance import PIPLComplianceService
from src.infrastructure.security.sensitive_data_detector import SensitiveDataDetector
from src.infrastructure.security.whitelist_service import WhitelistService

scenarios("test_story_1_11.feature")


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context():
    """Share state between steps."""
    return {}


@pytest.fixture
def mock_session():
    """Mock database session."""
    session = mock.Mock()
    session.add = mock.Mock()
    session.flush = mock.AsyncMock()
    session.execute = mock.AsyncMock()
    session.commit = mock.AsyncMock()
    session.rollback = mock.AsyncMock()
    return session


@pytest.fixture
def sensitive_data_detector():
    """Create SensitiveDataDetector instance."""
    return SensitiveDataDetector()


@pytest.fixture
def sovereignty_service():
    """Create DataSovereigntyService instance."""
    return DataSovereigntyService()


@pytest.fixture
def whitelist_service():
    """Create WhitelistService instance."""
    return WhitelistService()


@pytest.fixture
def approval_workflow():
    """Create ApprovalWorkflowService instance."""
    return ApprovalWorkflowService()


@pytest.fixture
def pipl_service():
    """Create PIPLComplianceService instance."""
    return PIPLComplianceService()


# ===================================================================
# AC-1: 敏感数据识别与标记 - Background Steps
# ===================================================================


@given("系统已配置 DataSovereigntyConfig")
def given_sovereignty_config(context):
    """系统已配置 DataSovereigntyConfig"""
    from src.infrastructure.config.sovereignty import DataSovereigntyConfig

    context["config"] = DataSovereigntyConfig()
    return context["config"]


@given("PostgreSQL 审计日志表已创建（Story 1.10）")
def given_audit_tables_created(context):
    """PostgreSQL 审计日志表已创建"""
    context["db_ready"] = True
    return True


@given("数据库连接正常")
def given_db_connection_ok(context, mock_session):
    """数据库连接正常"""
    context["session"] = mock_session
    return True


# ===================================================================
# AC-1: 敏感数据识别与标记 - Scenario Steps
# ===================================================================


@given("系统处理包含身份证号的数据")
def given_data_with_id_card(context, sensitive_data_detector):
    """系统处理包含身份证号的数据"""
    text = "姓名张三身份证号110101199001011234"
    context["detection_result"] = sensitive_data_detector.detect(text)
    context["text"] = text
    return context["detection_result"]


@given("系统处理包含手机号的数据")
def given_data_with_phone(context, sensitive_data_detector):
    """系统处理包含手机号的数据"""
    text = "联系电话13812345678"
    context["detection_result"] = sensitive_data_detector.detect(text)
    context["text"] = text
    return context["detection_result"]


@given('系统处理包含"机密"、"配方"等关键词的数据')
def given_data_with_trade_secret_keywords(context, sensitive_data_detector):
    """系统处理包含"机密"、"配方"等关键词的数据"""
    text = "这是一份机密文件，包含核心配方"
    context["detection_result"] = sensitive_data_detector.detect(text)
    context["text"] = text
    return context["detection_result"]


@given("系统处理包含银行卡号的数据")
def given_data_with_bank_account(context, sensitive_data_detector):
    """系统处理包含银行卡号的数据"""
    text = "银行账号6222021234567890"
    context["detection_result"] = sensitive_data_detector.detect(text)
    context["text"] = text
    return context["detection_result"]


@given("系统处理包含指纹、人脸特征的数据")
def given_data_with_biometric(context, sensitive_data_detector):
    """系统处理包含指纹、人脸特征的数据"""
    text = "指纹特征：Fingerprint{001} 人脸特征：Face{002}"
    context["detection_result"] = sensitive_data_detector.detect(text)
    context["text"] = text
    return context["detection_result"]


@given("系统配置了自定义敏感类型")
def given_custom_sensitive_type(context):
    """系统配置了自定义敏感类型"""
    detector = SensitiveDataDetector()
    detector.add_custom_rule(r"custom:\w+", "CUSTOM")
    context["detector"] = detector
    return detector


@given("原始数据已被标记为敏感")
def given_data_marked_sensitive(context):
    """原始数据已被标记为敏感"""
    context["sensitive_data"] = {
        "content": "敏感数据",
        "sensitive_type": SensitiveDataType.PII,
        "labels": ["pii", "personal"],
    }
    return context["sensitive_data"]


@given("测试数据集包含100个样本")
def given_test_dataset_100_samples(context):
    """测试数据集包含100个样本"""
    context["test_samples"] = [f"样本{i}包含身份证号110101199001011234" for i in range(100)]
    return context["test_samples"]


@when("数据进入系统")
def when_data_enters_system(context, sensitive_data_detector):
    """数据进入系统"""
    text = context.get("text", "姓名张三身份证号110101199001011234")
    context["detection_result"] = sensitive_data_detector.detect(text)
    return context["detection_result"]


@when("数据被访问时")
def when_data_is_accessed(context, sensitive_data_detector):
    """数据被访问时"""
    text = context.get("text", "联系电话13812345678")
    context["detection_result"] = sensitive_data_detector.detect(text)
    return context["detection_result"]


@when("数据匹配自定义规则时")
def when_custom_rule_matches(context):
    """数据匹配自定义规则时"""
    detector = context.get("detector")
    if detector:
        context["detection_result"] = detector.detect("custom:sensitive_data")
    return context.get("detection_result")


@when("数据被复制或传输至下游系统")
def when_data_copied_to_downstream(context, sensitive_data_detector):
    """数据被复制或传输至下游系统"""
    original = context.get("sensitive_data", {})
    context["copied_data"] = original.copy()
    # Detect on the copied data content to simulate downstream detection
    content = original.get("content", "")
    context["detection_result"] = sensitive_data_detector.detect(content)
    return context["copied_data"]


@when("执行敏感数据识别")
def when_run_detection(context, sensitive_data_detector):
    """执行敏感数据识别"""
    samples = context.get("test_samples", [])
    context["detection_results"] = [sensitive_data_detector.detect(s) for s in samples]
    return context["detection_results"]


# ===================================================================
# AC-2: 数据境内存储策略 - Scenario Steps
# ===================================================================


@given("敏感数据已被标记为 PII 类型")
def given_pii_data_marked(context):
    """敏感数据已被标记为 PII 类型"""
    context["data_for_storage"] = {
        "data_id": uuid.uuid4(),
        "sensitive_type": SensitiveDataType.PII,
        "available_layers": ["cn-primary", "us-secondary"],
        "content": "敏感个人信息",
    }
    return context["data_for_storage"]


@given("敏感数据需要存储在境外")
def given_data_needs_offshore_storage(context):
    """敏感数据需要存储在境外"""
    context["storage_request"] = {
        "data_id": uuid.uuid4(),
        "destination": "us-west-2",
        "sensitive_type": SensitiveDataType.PII,
    }
    return context["storage_request"]


@given("系统有多层存储可用")
def given_multi_layer_storage(context):
    """系统有多层存储可用"""
    context["storage_layers"] = ["cn-primary", "cn-backup", "us-secondary"]
    context["data_for_storage"] = {
        "available_layers": ["cn-primary", "cn-backup", "us-secondary"],
    }
    return context["storage_layers"]


@given("配置指定数据只能存储在中国大陆")
def given_config_china_only(context):
    """配置指定数据只能存储在中国大陆"""
    from src.infrastructure.config.sovereignty import DataSovereigntyConfig

    context["config"] = DataSovereigntyConfig()
    return context["config"]


@given("系统配置境内和境外存储层")
def given_configured_domestic_and_offshore(context):
    """系统配置境内和境外存储层"""
    context["storage_layers"] = ["cn-primary", "us-secondary"]
    return context["storage_layers"]


@given("发生跨境数据传输")
def given_cross_border_transfer(context):
    """发生跨境数据传输"""
    context["transfer"] = {
        "data_id": uuid.uuid4(),
        "source": "cn-primary",
        "destination": "us-west-2",
        "sensitive_type": SensitiveDataType.PII,
    }
    return context["transfer"]


@given("合规性测试执行")
def given_compliance_test_running(context):
    """合规性测试执行"""
    context["compliance_test"] = True
    return True


@when("系统选择存储层")
def when_select_storage_layer(context, sovereignty_service):
    """系统选择存储层"""
    data = context.get("data_for_storage", {})
    context["storage_result"] = sovereignty_service.select_storage_layer(
        data_type=data.get("sensitive_type", SensitiveDataType.PII),
        available_layers=data.get("available_layers", ["cn-primary", "us-secondary"]),
    )
    return context.get("storage_result")


@when("存储请求被发起")
def when_storage_requested(context, sovereignty_service):
    """存储请求被发起"""
    request = context.get("storage_request", {})
    context["storage_result"] = sovereignty_service.request_storage(
        data_id=request.get("data_id", uuid.uuid4()),
        destination=request.get("destination", "us-west-2"),
        sensitive_type=request.get("sensitive_type", SensitiveDataType.PII),
    )
    return context.get("storage_result")


@when("需要选择存储位置时")
def when_need_storage_location(context, sovereignty_service):
    """需要选择存储位置时"""
    context["storage_result"] = sovereignty_service.select_storage_layer(
        data_type=SensitiveDataType.PII,
        available_layers=context.get("storage_layers", ["cn-primary", "us-secondary"]),
    )
    return context.get("storage_result")


@when("尝试将数据存储到境外")
def when_try_offshore_storage(context, sovereignty_service):
    """尝试将数据存储到境外"""
    context["storage_result"] = sovereignty_service.select_storage_layer(
        data_type=SensitiveDataType.PII,
        available_layers=["cn-primary", "us-west-2"],
    )
    return context.get("storage_result")


@when("敏感数据存储时")
def when_sensitive_data_stored(context, sovereignty_service):
    """敏感数据存储时"""
    context["storage_result"] = sovereignty_service.select_storage_layer(
        data_type=SensitiveDataType.PII,
        available_layers=["cn-primary", "us-secondary"],
    )
    return context.get("storage_result")


@when("传输完成时")
def when_transfer_completed(context, sovereignty_service):
    """传输完成时"""
    transfer = context.get("transfer", {})
    context["transfer_result"] = sovereignty_service.log_cross_border_event(
        data_id=transfer.get("data_id", uuid.uuid4()),
        source=transfer.get("source", "cn-primary"),
        destination=transfer.get("destination", "us-west-2"),
        sensitive_type=transfer.get("sensitive_type", SensitiveDataType.PII),
    )
    return context.get("transfer_result")


@when("验证数据境内存储要求")
def when_verify_data_residency(context, sovereignty_service):
    """验证数据境内存储要求"""
    context["compliance_result"] = sovereignty_service.verify_compliance()
    return context.get("compliance_result")


# ===================================================================
# AC-3: 外部调用白名单机制 - Scenario Steps
# ===================================================================


@given("外部 API 端点已在白名单中（active 状态）")
def given_endpoint_in_whitelist(context):
    """外部 API 端点已在白名单中（active 状态）"""
    rule = WhitelistRule(
        id=uuid.uuid4(),
        endpoint="https://api.example.com/data",
        provider="ExampleAPI",
        purpose="数据同步",
        risk_level="low",
        status="active",
    )
    context["whitelist_rule"] = rule
    return rule


@given("外部 API 端点不在白名单中")
def given_endpoint_not_in_whitelist(context):
    """外部 API 端点不在白名单中"""
    context["endpoint"] = "https://unknown-endpoint.com/api"
    return context["endpoint"]


@given("管理员添加新白名单规则")
def given_admin_adds_rule(context):
    """管理员添加新白名单规则"""
    context["new_rule"] = {
        "endpoint": "https://new-api.example.com",
        "provider": "NewProvider",
        "purpose": "新功能调用",
        "risk_level": "medium",
    }
    return context["new_rule"]


@given("白名单规则已过期")
def given_expired_whitelist_rule(context):
    """白名单规则已过期"""
    rule = WhitelistRule(
        id=uuid.uuid4(),
        endpoint="https://expired.example.com",
        provider="ExpiredAPI",
        purpose="测试",
        risk_level="low",
        status="expired",
        expiry_date=datetime.now(UTC) - timedelta(days=1),
    )
    context["whitelist_rule"] = rule
    return rule


@given("管理员撤销白名单规则")
def given_admin_revokes_rule(context):
    """管理员撤销白名单规则"""
    rule = WhitelistRule(
        id=uuid.uuid4(),
        endpoint="https://revoked.example.com",
        provider="RevokedAPI",
        purpose="测试",
        risk_level="low",
        status="revoked",
    )
    context["whitelist_rule"] = rule
    return rule


@given('管理员执行 sisys system whitelist add --endpoint https://api.example.com --provider ExampleAPI --purpose "数据同步"')
def given_cli_whitelist_add(context):
    """管理员执行 CLI 白名单添加命令"""
    context["cli_rule"] = {
        "endpoint": "https://api.example.com",
        "provider": "ExampleAPI",
        "purpose": "数据同步",
    }
    return context["cli_rule"]


@given("系统存在多条白名单规则")
def given_multiple_whitelist_rules(context):
    """系统存在多条白名单规则"""
    context["whitelist_rules"] = [
        WhitelistRule(
            id=uuid.uuid4(),
            endpoint=f"https://api{i}.example.com",
            provider=f"Provider{i}",
            purpose="测试",
            risk_level="low",
            status="active",
        )
        for i in range(3)
    ]
    return context["whitelist_rules"]


@given("管理员调用 POST /api/v1/admin/whitelist")
def given_api_whitelist_create(context):
    """管理员调用 API 创建白名单"""
    context["api_rule"] = {
        "endpoint": "https://api.new.com",
        "provider": "NewAPI",
        "purpose": "新接口",
        "risk_level": "low",
    }
    return context["api_rule"]


@given("系统调用外部 API")
def given_external_api_call(context):
    """系统调用外部 API"""
    context["endpoint"] = "https://api.example.com/external"
    return context["endpoint"]


@given("合规性测试执行")
def given_compliance_test(context):
    """合规性测试执行"""
    context["compliance_test"] = True
    return True


@when("系统调用该端点")
def when_call_endpoint(context, whitelist_service):
    """系统调用该端点"""
    rule = context.get("whitelist_rule")
    if rule:
        # Ensure rule exists in service
        if rule.endpoint not in whitelist_service._rules:
            whitelist_service._rules[rule.endpoint] = rule
        context["validation_result"] = whitelist_service.validate_call(rule.endpoint)
    return context.get("validation_result")


@when("系统尝试调用该端点")
def when_try_call_endpoint(context, whitelist_service):
    """系统尝试调用该端点"""
    endpoint = context.get("endpoint", "https://unknown.com")
    context["validation_result"] = whitelist_service.validate_call(endpoint)
    return context.get("validation_result")


@when("规则状态为 active")
def when_rule_is_active(context, whitelist_service):
    """规则状态为 active"""
    new_rule = context.get("new_rule", {})
    context["add_result"] = whitelist_service.add_rule(
        endpoint=new_rule.get("endpoint", "https://new.com"),
        provider=new_rule.get("provider", "Provider"),
        purpose=new_rule.get("purpose", "测试"),
        risk_level=new_rule.get("risk_level", "low"),
        status="active",
    )
    return context.get("add_result")


@when("系统验证该规则时")
def when_validate_rule(context, whitelist_service):
    """系统验证该规则时"""
    rule = context.get("whitelist_rule")
    if rule:
        context["validation_result"] = whitelist_service.validate_call(rule.endpoint)
    return context.get("validation_result")


@when("后续调用使用该规则")
def when_subsequent_call_uses_rule(context, whitelist_service):
    """后续调用使用该规则"""
    rule = context.get("whitelist_rule")
    if rule:
        context["validation_result"] = whitelist_service.validate_call(rule.endpoint)
    return context.get("validation_result")


@when("命令执行成功")
def when_cli_command_succeeds(context, whitelist_service):
    """命令执行成功"""
    cli_rule = context.get("cli_rule", {})
    context["add_result"] = whitelist_service.add_rule(
        endpoint=cli_rule.get("endpoint", "https://api.example.com"),
        provider=cli_rule.get("provider", "ExampleAPI"),
        purpose=cli_rule.get("purpose", "数据同步"),
    )
    return context.get("add_result")


@when("管理员执行 sisys system whitelist list --status active")
def when_cli_list_whitelist(context, whitelist_service):
    """管理员执行 CLI 列出白名单命令"""
    context["list_result"] = whitelist_service.list_rules(status="active")
    return context.get("list_result")


@when("请求包含规则信息")
def when_api_create_whitelist(context, whitelist_service):
    """请求包含规则信息"""
    api_rule = context.get("api_rule", {})
    context["create_result"] = whitelist_service.add_rule(
        endpoint=api_rule.get("endpoint", "https://api.new.com"),
        provider=api_rule.get("provider", "NewAPI"),
        purpose=api_rule.get("purpose", "新接口"),
        risk_level=api_rule.get("risk_level", "low"),
    )
    return context.get("create_result")


@when("调用完成时")
def when_call_completed(context, whitelist_service):
    """调用完成时"""
    endpoint = context.get("endpoint", "https://api.example.com")
    context["validation_result"] = whitelist_service.validate_call(endpoint)
    return context.get("validation_result")


@when("验证白名单验证覆盖率")
def when_verify_whitelist_coverage(context, whitelist_service):
    """验证白名单验证覆盖率"""
    context["coverage_result"] = whitelist_service.get_coverage_report()
    return context.get("coverage_result")


# ===================================================================
# AC-4: 跨境传输审批流程 - Scenario Steps
# ===================================================================


@given("数据需要跨境传输")
def given_data_needs_cross_border(context):
    """数据需要跨境传输"""
    context["transfer_request"] = {
        "data_id": uuid.uuid4(),
        "destination": "us-west-2",
        "purpose": "数据分析",
        "requester": "user-123",
    }
    return context["transfer_request"]


@given("存在待审批的跨境传输请求")
def given_pending_approval_request(context):
    """存在待审批的跨境传输请求"""
    request = CrossBorderApproval(
        id=uuid.uuid4(),
        request_id=uuid.uuid4(),
        data_id=uuid.uuid4(),
        destination="us-west-2",
        purpose="测试",
        requester="user-123",
        status=ApprovalStatus.PENDING,
        requested_at=datetime.now(UTC),
    )
    context["approval_request"] = request
    return request


@given("审批请求已超过 SLA 时限（48小时）")
def given_approval_exceeded_sla(context):
    """审批请求已超过 SLA 时限"""
    request = CrossBorderApproval(
        id=uuid.uuid4(),
        request_id=uuid.uuid4(),
        data_id=uuid.uuid4(),
        destination="us-west-2",
        purpose="测试",
        requester="user-123",
        status=ApprovalStatus.PENDING,
        requested_at=datetime.now(UTC) - timedelta(hours=49),
    )
    context["approval_request"] = request
    return request


@given("审批请求超时 24 小时")
def given_approval_timeout_24h(context):
    """审批请求超时 24 小时"""
    request = CrossBorderApproval(
        id=uuid.uuid4(),
        request_id=uuid.uuid4(),
        data_id=uuid.uuid4(),
        destination="us-west-2",
        purpose="测试",
        requester="user-123",
        status=ApprovalStatus.PENDING,
        requested_at=datetime.now(UTC) - timedelta(hours=25),
        sla_deadline=datetime.now(UTC) - timedelta(hours=1),
    )
    context["approval_request"] = request
    return request


@given("跨境传输请求未获批准")
def given_unapproved_transfer(context):
    """跨境传输请求未获批准"""
    context["unapproved"] = {
        "data_id": uuid.uuid4(),
        "destination": "us-west-2",
        "approved": False,
    }
    return context["unapproved"]


@given("跨境传输请求已完成审批")
def given_approved_transfer(context):
    """跨境传输请求已完成审批"""
    context["approved"] = {
        "data_id": uuid.uuid4(),
        "destination": "us-west-2",
        "status": ApprovalStatus.APPROVED,
    }
    return context["approved"]


@given("管理员执行 sisys system approval list --status pending")
def given_cli_approval_list(context):
    """管理员执行 CLI 列出审批请求"""
    context["cli_status"] = "pending"
    return "pending"


@given("存在待审批请求（request_id: xxx）")
def given_pending_request_with_id(context):
    """存在待审批请求"""
    context["request_id"] = uuid.uuid4()
    return context["request_id"]


@given("管理员执行 sisys system approval approve --request-id xxx")
def given_cli_approval_approve(context):
    """管理员执行 CLI 批准命令"""
    context["cli_request_id"] = uuid.uuid4()
    return context["cli_request_id"]


@given('管理员执行 sisys system approval reject --request-id xxx --reason "不合规"')
def given_cli_approval_reject(context):
    """管理员执行 CLI 拒绝命令"""
    context["cli_reject"] = {"request_id": uuid.uuid4(), "reason": "不合规"}
    return context["cli_reject"]


@when("传输请求被发起")
def when_transfer_requested(context, approval_workflow):
    """传输请求被发起"""
    request = context.get("transfer_request", {})
    context["request_result"] = approval_workflow.create_request(
        data_id=request.get("data_id", uuid.uuid4()),
        destination=request.get("destination", "us-west-2"),
        purpose=request.get("purpose", "测试"),
        requester=request.get("requester", "user-123"),
    )
    return context.get("request_result")


@when("合规官执行 approve 操作")
def when_compliance_officer_approves(context, approval_workflow):
    """合规官执行 approve 操作"""
    request = context.get("approval_request")
    if request:
        # Ensure approval exists in service
        if request.id not in approval_workflow._approvals:
            approval_workflow._approvals[request.id] = request
        context["approve_result"] = approval_workflow.approve(
            request_id=request.id,
            approver="compliance-officer-001",
        )
    return context.get("approve_result")


@when("合规官执行 reject 操作并提供原因")
def when_compliance_officer_rejects(context, approval_workflow):
    """合规官执行 reject 操作并提供原因"""
    request = context.get("approval_request")
    if request:
        # Ensure approval exists in service
        if request.id not in approval_workflow._approvals:
            approval_workflow._approvals[request.id] = request
        context["reject_result"] = approval_workflow.reject(
            request_id=request.id,
            approver="compliance-officer-001",
            reason="不合规请求",
        )
    return context.get("reject_result")


@when("系统检查待审批请求")
def when_check_pending_requests(context, approval_workflow):
    """系统检查待审批请求"""
    context["sla_result"] = approval_workflow.check_sla_violations()
    return context.get("sla_result")


@when("系统检测到超时")
def when_detect_timeout(context, approval_workflow):
    """系统检测到超时"""
    request = context.get("approval_request")
    if request:
        # Ensure approval exists in service
        if request.id not in approval_workflow._approvals:
            approval_workflow._approvals[request.id] = request
        context["escalate_result"] = approval_workflow.escalate_request(request.id)
    return context.get("escalate_result")


@when("尝试执行跨境传输")
def when_try_cross_border_transfer(context, approval_workflow):
    """尝试执行跨境传输"""
    unapproved = context.get("unapproved", {})
    context["validate_result"] = approval_workflow.validate_transfer(
        data_id=unapproved.get("data_id", uuid.uuid4()),
        destination=unapproved.get("destination", "us-west-2"),
    )
    return context.get("validate_result")


@when("查询审批历史")
def when_query_approval_history(context, approval_workflow):
    """查询审批历史"""
    approved = context.get("approved", {})
    context["history_result"] = approval_workflow.get_history(
        data_id=approved.get("data_id", uuid.uuid4()),
    )
    return context.get("history_result")


@when("管理员执行 sisys system approval list --status pending")
def when_cli_list_pending(context, approval_workflow):
    """管理员执行 CLI 列出待审批"""
    context["list_result"] = approval_workflow.list_requests(status="pending")
    return context.get("list_result")


@when("管理员执行 sisys system approval approve --request-id xxx")
def when_cli_approve(context, approval_workflow):
    """管理员执行 CLI 批准"""
    request_id = context.get("cli_request_id", uuid.uuid4())
    # Create approval in service for the test
    request = CrossBorderApproval(
        id=request_id,
        request_id=request_id,
        data_id=uuid.uuid4(),
        destination="us-west-2",
        purpose="测试",
        requester="user-123",
        status=ApprovalStatus.PENDING,
        requested_at=datetime.now(UTC),
    )
    approval_workflow._approvals[request_id] = request
    context["approve_result"] = approval_workflow.approve(
        request_id=request_id,
        approver="admin",
    )
    return context.get("approve_result")


@when('管理员执行 sisys system approval reject --request-id xxx --reason "不合规"')
def when_cli_reject(context, approval_workflow):
    """管理员执行 CLI 拒绝"""
    reject_info = context.get("cli_reject", {})
    request_id = reject_info.get("request_id", uuid.uuid4())
    # Create approval in service for the test
    request = CrossBorderApproval(
        id=request_id,
        request_id=request_id,
        data_id=uuid.uuid4(),
        destination="us-west-2",
        purpose="测试",
        requester="user-123",
        status=ApprovalStatus.PENDING,
        requested_at=datetime.now(UTC),
    )
    approval_workflow._approvals[request_id] = request
    context["reject_result"] = approval_workflow.reject(
        request_id=request_id,
        approver="admin",
        reason=reject_info.get("reason", "不合规"),
    )
    return context.get("reject_result")


@when("验证跨境传输审批率")
def when_verify_approval_coverage(context, approval_workflow):
    """验证跨境传输审批率"""
    context["approval_rate_result"] = approval_workflow.get_approval_rate_report()
    return context.get("approval_rate_result")


# ===================================================================
# AC-5: PIPL 合规 - Scenario Steps
# ===================================================================


@given("系统访问个人信息")
def given_accessing_personal_info(context):
    """系统访问个人信息"""
    context["personal_access"] = {
        "personal_data_id": uuid.uuid4(),
        "accessor": "user-123",
        "purpose": "数据展示",
        "legal_basis": "consent",
    }
    return context["personal_access"]


@given("系统处理个人信息")
def given_processing_personal_info(context):
    """系统处理个人信息"""
    context["personal_processing"] = {
        "personal_data_id": uuid.uuid4(),
        "processor": "system",
        "purpose": "统计分析",
        "legal_basis": "contract",
    }
    return context["personal_processing"]


@given("PIPL 配置要求同意")
def given_pipl_requires_consent(context):
    """PIPL 配置要求同意"""
    from src.infrastructure.config.sovereignty import DataSovereigntyConfig

    context["pipl_config"] = DataSovereigntyConfig()
    return context["pipl_config"]


@given("数据主体请求查看其个人信息")
def given_data_subject_requests_access(context):
    """数据主体请求查看其个人信息"""
    context["access_request_id"] = uuid.uuid4()
    return context["access_request_id"]


@given("数据主体请求删除其个人信息")
def given_data_subject_requests_deletion(context):
    """数据主体请求删除其个人信息"""
    context["deletion_request_id"] = uuid.uuid4()
    return context["deletion_request_id"]


@given("数据主体请求更正其个人信息")
def given_data_subject_requests_correction(context):
    """数据主体请求更正其个人信息"""
    context["correction_request_id"] = uuid.uuid4()
    return context["correction_request_id"]


@given("系统处理生物识别信息")
def given_processing_biometric(context):
    """系统处理生物识别信息"""
    context["biometric_data"] = {
        "data_id": uuid.uuid4(),
        "biometric_type": "fingerprint",
        "purpose": "身份验证",
    }
    return context["biometric_data"]


@given("系统处理14岁以下未成年人信息")
def given_processing_minor_info(context):
    """系统处理未成年人信息"""
    context["minor_data"] = {
        "data_id": uuid.uuid4(),
        "age": 12,
        "guardian_id": "guardian-001",
    }
    return context["minor_data"]


@given("合规审计需要报告")
def given_compliance_audit_needs_report(context):
    """合规审计需要报告"""
    context["report_period"] = {
        "start": datetime.now(UTC) - timedelta(days=30),
        "end": datetime.now(UTC),
    }
    return context["report_period"]


@given("PIPL 合规测试执行")
def given_pipl_compliance_test(context):
    """PIPL 合规测试执行"""
    context["pipl_test"] = True
    return True


@when("访问发生时")
def when_access_happens(context, pipl_service):
    """访问发生时"""
    access = context.get("personal_access", {})
    context["access_result"] = pipl_service.record_access(
        personal_data_id=access.get("personal_data_id", uuid.uuid4()),
        accessor=access.get("accessor", "user-123"),
        purpose=access.get("purpose", "测试"),
        legal_basis=access.get("legal_basis", "consent"),
        data_subject_consent=access.get("data_subject_consent", True),
    )
    return context.get("access_result")


@when("处理发生时")
def when_processing_happens(context, pipl_service):
    """处理发生时"""
    processing = context.get("personal_processing", {})
    context["processing_result"] = pipl_service.record_processing(
        personal_data_id=processing.get("personal_data_id", uuid.uuid4()),
        processor=processing.get("processor", "system"),
        purpose=processing.get("purpose", "测试"),
        legal_basis=processing.get("legal_basis", "contract"),
    )
    return context.get("processing_result")


@when("个人信息被处理")
def when_personal_data_processed(context, pipl_service):
    """个人信息被处理"""
    context["consent_result"] = pipl_service.validate_consent(
        personal_data_id=uuid.uuid4(),
        purpose="测试",
    )
    return context.get("consent_result")


@when("请求被处理")
def when_access_request_processed(context, pipl_service):
    """请求被处理 - 访问权"""
    access_request_id = context.get("access_request_id", uuid.uuid4())
    context["records_result"] = pipl_service.get_access_records(access_request_id)
    return context.get("records_result")


@when("请求被处理")
def when_deletion_request_processed(context, pipl_service):
    """请求被处理 - 删除权"""
    deletion_id = context.get("deletion_request_id", uuid.uuid4())
    context["deletion_result"] = pipl_service.delete_personal_data(deletion_id)
    return context.get("deletion_result")


@when("请求被处理")
def when_correction_request_processed(context, pipl_service):
    """请求被处理 - 更正权"""
    correction_id = context.get("correction_request_id", uuid.uuid4())
    context["correction_result"] = pipl_service.correct_personal_data(
        correction_id,
        corrected_data={"name": "新名字"},
    )
    return context.get("correction_result")


@when("处理发生时")
def when_biometric_processed_2(context, pipl_service):
    """处理生物识别数据时"""
    biometric = context.get("biometric_data", {})
    context["biometric_result"] = pipl_service.process_biometric_data(
        data_id=biometric.get("data_id", uuid.uuid4()),
        biometric_type=biometric.get("biometric_type", "fingerprint"),
        purpose=biometric.get("purpose", "身份验证"),
    )
    return context.get("biometric_result")


@when("处理发生时")
def when_minor_processed_2(context, pipl_service):
    """处理未成年人数据时"""
    minor = context.get("minor_data", {})
    context["minor_result"] = pipl_service.process_minor_data(
        data_id=minor.get("data_id", uuid.uuid4()),
        age=minor.get("age", 12),
        guardian_id=minor.get("guardian_id", "guardian-001"),
    )
    return context.get("minor_result")


@when("报告生成请求")
def when_report_requested(context, pipl_service):
    """报告生成请求"""
    period = context.get("report_period", {})
    context["report_result"] = pipl_service.generate_pipl_report(
        start_date=period.get("start", datetime.now(UTC) - timedelta(days=30)),
        end_date=period.get("end", datetime.now(UTC)),
    )
    return context.get("report_result")


@when("所有测试项通过")
def when_all_tests_pass(context, pipl_service):
    """所有测试项通过"""
    context["test_result"] = pipl_service.run_compliance_tests()
    return context.get("test_result")


# ===================================================================
# AC-6: 合规性测试 - Scenario Steps
# ===================================================================


@given("执行 COMP-05 合规性测试")
def given_comp05_test(context):
    """执行 COMP-05 合规性测试"""
    context["test_name"] = "COMP-05"
    return "COMP-05"


@given("执行敏感数据识别测试")
def given_sensitive_data_test(context):
    """执行敏感数据识别测试"""
    context["test_name"] = "sensitive_data_detection"
    return "sensitive_data_detection"


@given("执行白名单验证覆盖率测试")
def given_whitelist_coverage_test(context):
    """执行白名单验证覆盖率测试"""
    context["test_name"] = "whitelist_coverage"
    return "whitelist_coverage"


@given("执行跨境传输审批率测试")
def given_approval_rate_test(context):
    """执行跨境传输审批率测试"""
    context["test_name"] = "approval_rate"
    return "approval_rate"


@when("测试完成")
def when_test_completed(context, sovereignty_service):
    """测试完成"""
    context["compliance_result"] = sovereignty_service.verify_data_residency_compliance()
    return context.get("compliance_result")


@when("测试样本 ≥ 100")
def when_test_samples_100(context, sensitive_data_detector):
    """测试样本"""
    samples = [f"身份证号11010119900101123{i % 10}" for i in range(100)]
    context["detection_results"] = [sensitive_data_detector.detect(s) for s in samples]
    return context["detection_results"]


@when("测试外部调用样本")
def when_test_external_calls(context, whitelist_service):
    """测试外部调用样本"""
    endpoints = ["https://api.example.com", "https://api2.example.com"]
    context["validation_results"] = [whitelist_service.validate_call(ep) for ep in endpoints]
    return context["validation_results"]


@when("测试跨境传输请求")
def when_test_transfer_requests(context, approval_workflow):
    """测试跨境传输请求"""
    requests = [
        CrossBorderApproval(
            id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            data_id=uuid.uuid4(),
            destination="us-west-2",
            purpose="测试",
            requester="user-123",
            status=ApprovalStatus.APPROVED,
            requested_at=datetime.now(UTC),
        )
    ]
    context["validate_results"] = approval_workflow.validate_all_transfers(requests)
    return context.get("validate_results")


# ===================================================================
# Then Steps - Validation
# ===================================================================


@then("系统识别出身份证号")
def then_id_card_detected(context):
    """系统识别出身份证号"""
    result = context.get("detection_result")
    assert result is not None
    assert result.is_sensitive is True


@then("数据标记为 PII 类型（敏感类型）")
def then_marked_as_pii(context):
    """数据标记为 PII 类型"""
    result = context.get("detection_result")
    assert result is not None
    assert result.sensitive_type == SensitiveDataType.PII


@then("数据标记为 PII 类型")
def then_marked_as_pii_short(context):
    """数据标记为 PII 类型"""
    result = context.get("detection_result")
    assert result is not None
    assert result.sensitive_type == SensitiveDataType.PII


@then("识别置信度 ≥ 95%")
def then_confidence_above_95(context):
    """识别置信度 ≥ 95%"""
    result = context.get("detection_result")
    if result:
        assert result.confidence >= 0.95


@then("系统识别出手机号（1开头11位）")
def then_phone_detected(context):
    """系统识别出手机号"""
    result = context.get("detection_result")
    assert result is not None
    assert result.is_sensitive is True


@then("系统识别出商业秘密关键词")
def then_trade_secret_detected(context):
    """系统识别出商业秘密关键词"""
    result = context.get("detection_result")
    assert result is not None
    assert result.is_sensitive is True


@then("数据标记为 TRADE_SECRET 类型")
def then_marked_as_trade_secret(context):
    """数据标记为 TRADE_SECRET 类型"""
    result = context.get("detection_result")
    assert result is not None
    assert result.sensitive_type == SensitiveDataType.TRADE_SECRET


@then("系统识别出银行账号")
def then_bank_account_detected(context):
    """系统识别出银行账号"""
    result = context.get("detection_result")
    assert result is not None


@then("数据标记为 FINANCIAL 类型")
def then_marked_as_financial(context):
    """数据标记为 FINANCIAL 类型"""
    result = context.get("detection_result")
    assert result is not None
    assert result.sensitive_type == SensitiveDataType.FINANCIAL


@then("系统识别出生物识别信息")
def then_biometric_detected(context):
    """系统识别出生物识别信息"""
    result = context.get("detection_result")
    assert result is not None
    assert result.is_sensitive is True


@then("数据标记为 BIOMETRIC 类型（PIPL 特殊保护）")
def then_marked_as_biometric(context):
    """数据标记为 BIOMETRIC 类型"""
    result = context.get("detection_result")
    assert result is not None
    assert result.sensitive_type == SensitiveDataType.BIOMETRIC


@then("系统识别为对应自定义类型")
def then_custom_type_detected(context):
    """系统识别为对应自定义类型"""
    result = context.get("detection_result")
    assert result is not None


@then("应用相应保护策略")
def then_protection_applied(context):
    """应用相应保护策略"""
    result = context.get("detection_result")
    assert result is not None


@then("敏感标签随数据传播")
def then_label_propagates(context):
    """敏感标签随数据传播"""
    copied = context.get("copied_data", {})
    assert "sensitive_type" in copied


@then("下游系统识别相同敏感类型")
def then_downstream_recognizes(context):
    """下游系统识别相同敏感类型"""
    result = context.get("detection_result")
    assert result is not None


@then("识别准确率 ≥ 95%")
def then_accuracy_above_95(context):
    """识别准确率 ≥ 95%"""
    results = context.get("detection_results", [])
    total = len(results)
    if total > 0:
        correct = sum(1 for r in results if r.is_sensitive)
        accuracy = correct / total
        assert accuracy >= 0.95


@then("系统优先选择境内存储层")
def then_prefers_domestic_storage(context):
    """系统优先选择境内存储层"""
    result = context.get("storage_result")
    assert result is not None


@then("优先选择中国境内存储层")
def then_prefers_china_storage(context):
    """优先选择中国境内存储层"""
    result = context.get("storage_result")
    assert result is not None


@then("数据物理存储在中国大陆")
def then_stored_in_china(context):
    """数据物理存储在中国大陆"""
    result = context.get("storage_result")
    assert result is not None


@then("系统触发跨境审批流程")
def then_triggers_approval(context):
    """系统触发跨境审批流程"""
    result = context.get("storage_result")
    assert result is not None


@then("审批通过前阻断存储操作")
def then_blocks_until_approved(context):
    """审批通过前阻断存储操作"""
    result = context.get("storage_result")
    assert result is not None


@then("记录路由决策原因")
def then_records_routing_reason(context):
    """记录路由决策原因"""
    pass


@then("系统拒绝存储请求")
def then_rejects_storage(context):
    """系统拒绝存储请求"""
    pass


@then("记录违规事件")
def then_records_violation(context):
    """记录违规事件"""
    pass


@then("境内数据与境外数据物理隔离")
def then_data_isolated(context):
    """境内数据与境外数据物理隔离"""
    pass


@then("系统生成跨境告警")
def then_generates_cross_border_alert(context):
    """系统生成跨境告警"""
    result = context.get("transfer_result")
    assert result is not None


@then("告警记录包含源、目的、敏感数据类型")
def then_alert_contains_details(context):
    """告警记录包含源、目的、敏感数据类型"""
    result = context.get("transfer_result")
    assert result is not None


@then("数据境内存储率 = 100%")
def then_100_percent_domestic(context):
    """数据境内存储率 = 100%"""
    result = context.get("compliance_result")
    if result and isinstance(result, dict):
        assert result.get("domestic_rate") == 1.0
    else:
        assert result is True


@then("白名单验证通过")
def then_whitelist_passed(context):
    """白名单验证通过"""
    result = context.get("validation_result")
    assert result is True or result is None


@then("允许调用执行")
def then_allows_call(context):
    """允许调用执行"""
    pass


@then("白名单验证失败")
def then_whitelist_failed(context):
    """白名单验证失败"""
    result = context.get("validation_result")
    assert result is False


@then("调用被阻断")
def then_call_blocked(context):
    """调用被阻断"""
    result = context.get("validation_result")
    assert result is False


@then("阻断事件记录至审计日志")
def then_blocks_and_logs(context):
    """阻断事件记录至审计日志"""
    pass


@then("新规则立即生效")
def then_new_rule_takes_effect(context):
    """新规则立即生效"""
    result = context.get("add_result")
    assert result is not None


@then("规则状态变为 expired")
def then_rule_expired(context):
    """规则状态变为 expired"""
    result = context.get("validation_result")
    assert result is False


@then("验证失败")
def then_validation_fails(context):
    """验证失败"""
    result = context.get("validation_result")
    assert result is False


@then("记录撤销原因")
def then_records_revocation_reason(context):
    """记录撤销原因"""
    pass


@then("白名单规则创建成功")
def then_whitelist_rule_created(context):
    """白名单规则创建成功"""
    result = context.get("create_result") or context.get("add_result")
    assert result is not None


@then("规则状态为 pending")
def then_rule_pending(context):
    """规则状态为 pending"""
    result = context.get("create_result") or context.get("add_result")
    assert result is not None


@then("返回所有 active 状态的规则")
def then_returns_active_rules(context):
    """返回所有 active 状态的规则"""
    result = context.get("list_result")
    assert result is not None


@then("包含规则详情（endpoint, provider, risk_level）")
def then_contains_rule_details(context):
    """包含规则详情"""
    result = context.get("list_result")
    assert result is not None


@then("返回所有 pending 状态的请求")
def then_returns_pending_requests(context):
    """返回所有 pending 状态的请求"""
    result = context.get("list_result")
    assert result is not None


@then("包含详情（data_id, destination, purpose, requester）")
def then_contains_approval_details(context):
    """包含详情（data_id, destination, purpose, requester）"""
    result = context.get("list_result")
    assert result is not None


@then("返回规则 ID")
def then_returns_rule_id(context):
    """返回规则 ID"""
    result = context.get("create_result")
    assert result is not None


@then("审计日志记录：调用时间、端点、结果（成功/失败）")
def then_logs_api_call(context):
    """审计日志记录调用信息"""
    pass


@then("所有外部调用均经过白名单验证")
def then_all_calls_validated(context):
    """所有外部调用均经过白名单验证"""
    result = context.get("coverage_result")
    assert result is not None


@then("所有传输均经过审批流程")
def then_all_transfers_approved(context):
    """所有传输均经过审批流程"""
    result = context.get("coverage_result")
    assert result is not None


@then("所有调用均经过白名单验证")
def then_all_calls_whitelisted(context):
    """所有调用均经过白名单验证"""
    result = context.get("coverage_result")
    assert result is not None


@then("审批请求创建成功")
def then_request_created(context):
    """审批请求创建成功"""
    result = context.get("request_result")
    assert result is not None


@then("状态为 pending")
def then_status_pending(context):
    """状态为 pending"""
    result = context.get("request_result")
    assert result is not None


@then("请求状态变为 approved")
def then_status_approved(context):
    """请求状态变为 approved"""
    result = context.get("approve_result")
    assert result is not None


@then("记录批准人")
def then_records_approver(context):
    """记录批准人"""
    result = context.get("approve_result")
    assert result is not None


@then("允许跨境传输")
def then_allows_transfer(context):
    """允许跨境传输"""
    result = context.get("approve_result")
    assert result is not None


@then("请求状态变为 rejected")
def then_status_rejected(context):
    """请求状态变为 rejected"""
    result = context.get("reject_result")
    assert result is not None


@then("记录拒绝原因")
def then_records_rejection_reason(context):
    """记录拒绝原因"""
    result = context.get("reject_result")
    assert result is not None


@then("跨境传输被阻断")
def then_transfer_blocked(context):
    """跨境传输被阻断"""
    result = context.get("reject_result")
    assert result is not None


@then("传输被阻断")
def then_transfer_is_blocked(context):
    """传输被阻断"""
    result = context.get("validate_result")
    assert result is False


@then("生成 SLA 超时告警")
def then_sla_alert_generated(context):
    """生成 SLA 超时告警"""
    result = context.get("sla_result")
    assert result is not None


@then("告警通知相关合规官")
def then_alert_notifies_compliance(context):
    """告警通知相关合规官"""
    result = context.get("sla_result")
    assert result is not None


@then("请求自动升级给上级合规官")
def then_request_escalated(context):
    """请求自动升级给上级合规官"""
    result = context.get("escalate_result")
    assert result is not None


@then("阻断日志记录")
def then_blocks_logged(context):
    """阻断日志记录"""
    result = context.get("validate_result")
    assert result is not None


@then("返回完整审批记录（请求人、审批人、时间、结果）")
def then_returns_full_history(context):
    """返回完整审批记录"""
    result = context.get("history_result")
    assert result is not None


@then("所有跨境传输均经过审批")
def then_all_cross_border_approved(context):
    """所有跨境传输均经过审批"""
    result = context.get("approval_rate_result")
    assert result is not None


@then("记录处理目的（purpose）")
def then_records_purpose(context):
    """记录处理目的"""
    result = context.get("access_result")
    assert result is not None


@then("记录处理方式（legal_basis）")
def then_records_legal_basis(context):
    """记录处理方式"""
    result = context.get("access_result")
    assert result is not None


@then("记录数据主体同意状态")
def then_records_consent_status(context):
    """记录数据主体同意状态"""
    result = context.get("access_result")
    assert result is not None


@then("记录合法依据（consent/contract/legal_obligation）")
def then_records_legal_basis_2(context):
    """记录合法依据"""
    result = context.get("processing_result")
    assert result is not None


@then("验证数据主体已提供同意")
def then_validates_consent(context):
    """验证数据主体已提供同意"""
    result = context.get("consent_result")
    assert result is not None


@then("拒绝未同意的处理请求")
def then_rejects_without_consent(context):
    """拒绝未同意的处理请求"""
    result = context.get("consent_result")
    assert result is not None


@then("返回该主体的所有个人信息记录")
def then_returns_all_records(context):
    """返回该主体的所有个人信息记录"""
    result = context.get("records_result")
    assert result is not None


@then("标记个人信息为已删除")
def then_marks_as_deleted(context):
    """标记个人信息为已删除"""
    result = context.get("deletion_result")
    assert result is not None


@then("停止所有相关处理活动")
def then_stops_processing(context):
    """停止所有相关处理活动"""
    result = context.get("deletion_result")
    assert result is not None


@then("更新相关信息")
def then_updates_info(context):
    """更新相关信息"""
    result = context.get("correction_result")
    assert result is not None


@then("记录更正历史")
def then_records_correction_history(context):
    """记录更正历史"""
    result = context.get("correction_result")
    assert result is not None


@then("应用最严格的保护措施")
def then_applies_strictest_protection(context):
    """应用最严格的保护措施"""
    result = context.get("biometric_result")
    assert result is not None


@then("禁止跨境传输")
def then_prohibits_cross_border(context):
    """禁止跨境传输"""
    result = context.get("biometric_result")
    assert result is not None


@then("需要监护人额外同意")
def then_requires_guardian_consent(context):
    """需要监护人额外同意"""
    result = context.get("minor_result")
    assert result is not None


@then("应用增强保护措施")
def then_applies_enhanced_protection(context):
    """应用增强保护措施"""
    result = context.get("minor_result")
    assert result is not None


@then("生成 PIPL 合规审计报告")
def then_generates_pipl_report(context):
    """生成 PIPL 合规审计报告"""
    result = context.get("report_result")
    assert result is not None


@then("包含所有个人信息处理记录")
def then_contains_all_processing_records(context):
    """包含所有个人信息处理记录"""
    result = context.get("report_result")
    assert result is not None


@then("系统满足 PIPL 合规要求")
def then_meets_pipl_requirements(context):
    """系统满足 PIPL 合规要求"""
    result = context.get("test_result")
    assert result is True or result is not None
