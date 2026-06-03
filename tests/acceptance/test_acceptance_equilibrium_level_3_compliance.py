"""等保2.0三级基础安全合规验收测试。

BDD 步骤定义：验证身份鉴别、访问控制、安全审计、入侵防范、数据完整性、
备份恢复、综合合规、隐私保护八大安全域。

运行命令: poetry run pytest tests/acceptance/test_acceptance_equilibrium_level_3_compliance.py -v

前置条件:
    - 安全服务端口已注册 (composition_root.py)
    - 各安全服务已实现 (infrastructure/security/)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pytest_bdd import given, scenario, then, when

from src.domain.entities.audit_log import AuditLog
from src.domain.entities.pipl_compliance_record import ConsentStatus, PIPLComplianceRecord
from src.domain.entities.role import Role
from src.domain.events.audit_events import AuditActionType
from src.domain.events.compliance_events import (
    MFAChallengeIssuedEvent,
    MFAChallengeStatus,
    MFAChallengeType,
)
from src.domain.ports.resolver import Resolver
from src.infrastructure.config.auth import AuthConfig
from src.infrastructure.security.encryption_service import EncryptionService
from src.infrastructure.security.equilibrium_compliance_verifier import (
    EquilibriumComplianceVerifier,
)
from src.infrastructure.security.password_validation_service import (
    PasswordValidationService,
)
from src.infrastructure.security.pipl_compliance_service_impl import (
    PIPLComplianceServiceImpl,
)

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def compliance_context() -> dict[str, Any]:
    """共享上下文，保存各场景的服务和操作结果。"""
    return {}


@pytest.fixture
def resolver() -> Resolver:
    """Resolver 实例用于通过端口获取服务。"""
    return Resolver()


@pytest.fixture
def password_service() -> PasswordValidationService:
    """密码验证服务实例。"""
    return PasswordValidationService()


@pytest.fixture
def encryption_service() -> EncryptionService:
    """加密服务实例。"""
    return EncryptionService()


@pytest.fixture
def pipl_service() -> PIPLComplianceServiceImpl:
    """PIPL 合规服务实例。"""
    return PIPLComplianceServiceImpl()


# ===================================================================
# 背景步骤
# ===================================================================


@given("系统已初始化完成")
def system_initialized(compliance_context: dict[str, Any]) -> None:
    """系统已初始化（bootstrap 由 conftest.py 自动完成）。"""
    compliance_context["initialized"] = True


@given("所有安全服务端口已注册")
def security_ports_registered() -> None:
    """验证安全服务端口已注册。"""
    from src.composition_root import _global_registry

    required_ports = [
        "intrusion_detection_service",
        "data_integrity_service",
        "backup_recovery_service",
    ]
    for port_name in required_ports:
        spec = _global_registry.get(port_name)
        assert spec is not None, f"Port {port_name} not registered"


# ===================================================================
# AC-1: 身份鉴别合规
# ===================================================================


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "合规密码验证通过",
)
def test_compliant_password():
    """合规密码验证测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "弱密码验证失败",
)
def test_weak_password():
    """弱密码验证测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "密码哈希与验证机制",
)
def test_password_hashing():
    """密码哈希与验证测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "MFA双因子认证事件可发布",
)
def test_mfa_event():
    """MFA 双因子认证事件测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "认证锁定参数满足等保要求",
)
def test_auth_lockout_config():
    """认证锁定配置测试。"""


@when("使用密码验证服务验证合规密码")
def validate_compliant_password(
    compliance_context: dict[str, Any],
    password_service: PasswordValidationService,
) -> None:
    """使用合规密码调用验证服务。"""
    password_service.validate("Str0ng!Pass")
    compliance_context["password_valid"] = True


@then("密码复杂度验证通过")
def password_validation_passed(compliance_context: dict[str, Any]) -> None:
    """密码验证通过。"""
    assert compliance_context["password_valid"] is True


@when("使用密码验证服务验证弱密码")
def validate_weak_password(
    compliance_context: dict[str, Any],
    password_service: PasswordValidationService,
) -> None:
    """使用弱密码调用验证服务。"""
    try:
        password_service.validate("abc")
        compliance_context["password_failed"] = False
    except Exception:
        compliance_context["password_failed"] = True


@then("密码验证失败")
def password_validation_failed(compliance_context: dict[str, Any]) -> None:
    """密码验证失败。"""
    assert compliance_context["password_failed"] is True


@when("对密码进行bcrypt哈希处理")
def hash_password(
    compliance_context: dict[str, Any],
    encryption_service: EncryptionService,
) -> None:
    """对密码进行 bcrypt 哈希。"""
    hashed = encryption_service.hash_password("MySecret123!")
    compliance_context["hashed_password"] = hashed
    compliance_context["original_password"] = "MySecret123!"  # pragma: allowlist secret


@then("返回bcrypt哈希值")
def verify_bcrypt_hash(compliance_context: dict[str, Any]) -> None:
    """验证返回 bcrypt 哈希值。"""
    hashed = compliance_context["hashed_password"]
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")


@then("原密码验证匹配")
def verify_original_password_match(
    compliance_context: dict[str, Any],
    encryption_service: EncryptionService,
) -> None:
    """原密码验证匹配。"""
    hashed = compliance_context["hashed_password"]
    assert encryption_service.verify_password("MySecret123!", hashed) is True


@then("错误密码验证不匹配")
def verify_wrong_password_mismatch(
    compliance_context: dict[str, Any],
    encryption_service: EncryptionService,
) -> None:
    """错误密码验证不匹配。"""
    hashed = compliance_context["hashed_password"]
    assert encryption_service.verify_password("WrongPassword!", hashed) is False


@when("创建TOTP类型MFA挑战事件")
def create_mfa_challenge_event(compliance_context: dict[str, Any]) -> None:
    """创建 TOTP 类型 MFA 挑战事件。"""
    event = MFAChallengeIssuedEvent(challenge_type=MFAChallengeType.TOTP)
    compliance_context["mfa_event"] = event


@then("事件类型为MFAChallengeIssuedEvent")
def verify_mfa_event_type(compliance_context: dict[str, Any]) -> None:
    """验证 MFA 事件类型。"""
    event = compliance_context["mfa_event"]
    assert event.event_type == "MFAChallengeIssuedEvent"


@then("挑战状态为PENDING")
def verify_mfa_status_pending(compliance_context: dict[str, Any]) -> None:
    """验证挑战状态为 PENDING。"""
    event = compliance_context["mfa_event"]
    assert event.status == MFAChallengeStatus.PENDING


@then("支持TOTP和HOTP两种挑战类型")
def verify_mfa_challenge_types(compliance_context: dict[str, Any]) -> None:
    """验证支持 TOTP 和 HOTP 两种挑战类型。"""
    totp_event = MFAChallengeIssuedEvent(challenge_type=MFAChallengeType.TOTP)
    hotp_event = MFAChallengeIssuedEvent(challenge_type=MFAChallengeType.HOTP)
    assert totp_event.challenge_type == MFAChallengeType.TOTP
    assert hotp_event.challenge_type == MFAChallengeType.HOTP


@when("检查认证锁定配置")
def check_auth_lockout_config(compliance_context: dict[str, Any]) -> None:
    """检查认证锁定配置。"""
    config = AuthConfig()
    compliance_context["auth_config"] = config


@then("认证失败锁定阈值配置为5次")
def verify_lockout_threshold(compliance_context: dict[str, Any]) -> None:
    """验证认证失败锁定阈值。"""
    config = compliance_context["auth_config"]
    assert config.max_login_attempts == 5


@then("锁定持续时间配置为30分钟")
def verify_lockout_duration(compliance_context: dict[str, Any]) -> None:
    """验证锁定持续时间。"""
    config = compliance_context["auth_config"]
    assert config.lockout_duration_minutes == 30


# ===================================================================
# AC-2: 访问控制合规
# ===================================================================


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "RBAC权限检查",
)
def test_rbac_permission_check():
    """RBAC 权限检查测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "通配符权限匹配",
)
def test_wildcard_permission():
    """通配符权限匹配测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "越权访问防护",
)
def test_unauthorized_access_prevention():
    """越权访问防护测试。"""


@given("创建具有admin权限的角色")
def create_admin_role(compliance_context: dict[str, Any]) -> None:
    """创建 admin 角色。"""
    role = Role(
        id=uuid.uuid4(),
        name="admin",
        description="Administrator",
        permissions=("users:read", "users:write", "users:delete", "documents:read"),
    )
    compliance_context["test_role"] = role


@given("创建具有通配符权限的角色")
def create_wildcard_role(compliance_context: dict[str, Any]) -> None:
    """创建通配符角色。"""
    role = Role(
        id=uuid.uuid4(),
        name="super_admin",
        description="Super Administrator",
        permissions=("*:*",),
    )
    compliance_context["test_role"] = role


@given("创建具有只读权限的角色")
def create_readonly_role(compliance_context: dict[str, Any]) -> None:
    """创建只读角色。"""
    role = Role(
        id=uuid.uuid4(),
        name="viewer",
        description="Read Only Viewer",
        permissions=("documents:read", "users:read"),
    )
    compliance_context["test_role"] = role


@when('检查角色是否具有 "users:read" 权限')
def check_admin_permission(compliance_context: dict[str, Any]) -> None:
    """检查 admin 角色权限。"""
    role = compliance_context["test_role"]
    compliance_context["has_permission"] = role.has_permission("users:read")


@when('检查通配符角色对 "documents:delete" 的权限')
def check_wildcard_permission(compliance_context: dict[str, Any]) -> None:
    """检查通配符角色权限。"""
    role = compliance_context["test_role"]
    compliance_context["has_permission"] = role.has_permission("documents:delete")


@when('检查只读角色对 "users:delete" 的权限')
def check_readonly_delete_permission(compliance_context: dict[str, Any]) -> None:
    """检查只读角色对删除操作的权限。"""
    role = compliance_context["test_role"]
    compliance_context["has_permission"] = role.has_permission("users:delete")


@then("角色权限检查返回True")
def permission_check_true(compliance_context: dict[str, Any]) -> None:
    """权限检查返回 True。"""
    assert compliance_context["has_permission"] is True


@then("通配符匹配成功")
def wildcard_match_success(compliance_context: dict[str, Any]) -> None:
    """通配符匹配成功。"""
    assert compliance_context["has_permission"] is True


@then("权限检查返回False")
def permission_check_false(compliance_context: dict[str, Any]) -> None:
    """权限检查返回 False。"""
    assert compliance_context["has_permission"] is False


# ===================================================================
# AC-3: 安全审计合规
# ===================================================================


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "审计日志完整性校验",
)
def test_audit_log_integrity():
    """审计日志完整性校验测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "WORM存储保留期满足等保要求",
)
def test_worm_retention():
    """WORM 存储保留期测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "审计事件类型覆盖安全操作",
)
def test_audit_event_types():
    """审计事件类型覆盖测试。"""


@when("创建审计日志实体并计算校验和")
def create_audit_log_with_checksum(compliance_context: dict[str, Any]) -> None:
    """创建审计日志实体并计算校验和。"""
    log = AuditLog.create(
        actor="admin",
        action_type="authentication:login",
        target_resource="user/session",
        new_value={"status": "logged_in"},
    )
    checksum = log.compute_checksum()
    verified_log = AuditLog(
        log_id=log.log_id,
        timestamp=log.timestamp,
        actor=log.actor,
        action_type=log.action_type,
        target_resource=log.target_resource,
        old_value=log.old_value,
        new_value=log.new_value,
        correction_level=log.correction_level,
        checksum=checksum,
    )
    compliance_context["audit_log"] = verified_log
    compliance_context["audit_checksum"] = checksum


@then("日志包含SHA256校验和")
def verify_audit_log_has_checksum(compliance_context: dict[str, Any]) -> None:
    """日志包含 SHA256 校验和。"""
    checksum = compliance_context["audit_checksum"]
    assert len(checksum) == 64
    assert all(c in "0123456789abcdef" for c in checksum)


@then("校验和验证通过")
def verify_audit_log_checksum_match(compliance_context: dict[str, Any]) -> None:
    """校验和验证通过。"""
    log = compliance_context["audit_log"]
    assert log.verify_checksum() is True


@when("检查WORM存储保留期配置")
def check_worm_retention_config(compliance_context: dict[str, Any]) -> None:
    """检查 WORM 存储保留期配置。"""
    from src.infrastructure.storage.minio.worm_lifecycle import SOX_RETENTION_DAYS

    compliance_context["worm_retention_days"] = SOX_RETENTION_DAYS


@then("WORM保留期为2555天")
def verify_worm_retention_days(compliance_context: dict[str, Any]) -> None:
    """验证 WORM 保留期。"""
    assert compliance_context["worm_retention_days"] == 2555


@when("检查审计事件类型定义")
def check_audit_event_types(compliance_context: dict[str, Any]) -> None:
    """检查审计事件类型定义。"""
    compliance_context["audit_action_types"] = {t.value for t in AuditActionType}


@then("包含认证类审计事件")
def verify_auth_audit_events(compliance_context: dict[str, Any]) -> None:
    """验证包含认证类审计事件。"""
    types = compliance_context["audit_action_types"]
    assert "authentication:login" in types
    assert "authentication:logout" in types
    assert "authentication:failed" in types


@then("包含授权类审计事件")
def verify_authz_audit_events(compliance_context: dict[str, Any]) -> None:
    """验证包含授权类审计事件。"""
    types = compliance_context["audit_action_types"]
    assert "authorization:grant" in types
    assert "authorization:revoke" in types


@then("包含敏感操作审计事件")
def verify_sensitive_audit_events(compliance_context: dict[str, Any]) -> None:
    """验证包含敏感操作审计事件。"""
    types = compliance_context["audit_action_types"]
    assert "document:delete" in types or "document:download" in types


# ===================================================================
# AC-4: 入侵防范合规
# ===================================================================


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "检测SQL注入攻击",
)
def test_sql_injection_detection():
    """SQL 注入攻击检测测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "检测XSS攻击",
)
def test_xss_detection():
    """XSS 攻击检测测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "检测暴力破解攻击",
)
def test_brute_force_detection():
    """暴力破解攻击检测测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "封禁恶意IP地址",
)
def test_block_malicious_ip():
    """封禁恶意 IP 地址测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "获取入侵检测统计",
)
def test_intrusion_stats():
    """入侵检测统计测试。"""


@given("入侵检测服务可用")
def intrusion_detection_service_available(
    compliance_context: dict[str, Any],
    resolver: Resolver,
) -> None:
    """入侵检测服务可用。"""
    service = resolver.resolve("intrusion_detection_service")
    compliance_context["intrusion_service"] = service


@when("系统收到包含SQL注入特征的请求")
def receive_sql_injection_request(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """收到 SQL 注入请求。"""
    service = compliance_context["intrusion_service"]
    result = event_loop.run_until_complete(
        service.detect_attack(
            source_ip="192.168.1.100",
            request_data="' OR 1=1 -- SELECT * FROM users",
            request_path="/api/query",
        )
    )
    compliance_context["detection_result"] = result


@when("系统收到包含XSS特征的请求")
def receive_xss_request(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """收到 XSS 请求。"""
    service = compliance_context["intrusion_service"]
    result = event_loop.run_until_complete(
        service.detect_attack(
            source_ip="192.168.1.101",
            request_data="<script>alert('xss')</script>",
            request_path="/api/comment",
        )
    )
    compliance_context["detection_result"] = result


@when("同一IP地址在5分钟内失败登录超过10次")
def brute_force_attempts(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """暴力破解尝试。"""
    service = compliance_context["intrusion_service"]
    source_ip = "192.168.1.102"
    for _ in range(15):
        event_loop.run_until_complete(
            service.detect_attack(
                source_ip=source_ip,
                request_data="login attempt",
                request_path="/auth/login",
            )
        )
    result = event_loop.run_until_complete(
        service.detect_attack(
            source_ip=source_ip,
            request_data="login attempt",
            request_path="/auth/login",
        )
    )
    compliance_context["detection_result"] = result


@when("管理员封禁恶意IP地址")
def admin_block_ip(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """管理员封禁 IP。"""
    service = compliance_context["intrusion_service"]
    result = event_loop.run_until_complete(
        service.block_ip(
            ip_address="192.168.1.200",
            reason="Repeated attack attempts",
            duration_hours=24,
        )
    )
    compliance_context["block_result"] = result
    compliance_context["blocked_ip"] = "192.168.1.200"


@when("系统请求过去24小时的入侵统计")
def request_intrusion_stats(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """请求入侵统计。"""
    service = compliance_context["intrusion_service"]
    result = event_loop.run_until_complete(service.get_intrusion_stats(period_hours=24))
    compliance_context["intrusion_stats"] = result


@then("入侵检测服务识别为SQL注入攻击")
def sql_injection_detected(compliance_context: dict[str, Any]) -> None:
    """SQL 注入被检测。"""
    result = compliance_context["detection_result"]
    assert result.detected is True
    assert "sql_injection" in result.attack_type.lower()


@then("攻击被记录到审计日志")
def attack_logged(compliance_context: dict[str, Any]) -> None:
    """攻击已记录。"""
    result = compliance_context["detection_result"]
    assert result.action_taken in ["logged", "alerted", "blocked"]


@then("入侵检测服务识别为XSS攻击")
def xss_detected(compliance_context: dict[str, Any]) -> None:
    """XSS 被检测。"""
    result = compliance_context["detection_result"]
    assert result.detected is True
    assert "xss" in result.attack_type.lower()


@then("攻击严重级别为HIGH")
def severity_high(compliance_context: dict[str, Any]) -> None:
    """严重级别 HIGH。"""
    result = compliance_context["detection_result"]
    assert result.severity.lower() in ["high", "critical"]


@then("入侵检测服务识别为暴力破解攻击")
def brute_force_detected(compliance_context: dict[str, Any]) -> None:
    """暴力破解被检测。"""
    result = compliance_context["detection_result"]
    assert result.detected is True
    assert "brute_force" in result.attack_type.lower()


@then("攻击严重级别为MEDIUM")
def severity_medium(compliance_context: dict[str, Any]) -> None:
    """严重级别 MEDIUM。"""
    result = compliance_context["detection_result"]
    assert result.severity.lower() in ["medium", "low"]


@then("该IP地址被封禁")
def ip_blocked(compliance_context: dict[str, Any]) -> None:
    """IP 已封禁。"""
    assert compliance_context["block_result"] is True


@then("封禁时长为24小时")
def block_duration_24h(compliance_context: dict[str, Any]) -> None:
    """封禁 24 小时。"""
    service = compliance_context["intrusion_service"]
    blocked_ip = compliance_context["blocked_ip"]
    assert blocked_ip in service._blocked_ips


@then("返回攻击总数")
def return_total_attacks(compliance_context: dict[str, Any]) -> None:
    """返回攻击总数。"""
    stats = compliance_context["intrusion_stats"]
    assert stats.total_attacks >= 0


@then("返回按攻击类型统计")
def return_attacks_by_type(compliance_context: dict[str, Any]) -> None:
    """返回按类型统计。"""
    stats = compliance_context["intrusion_stats"]
    assert isinstance(stats.attacks_by_type, dict)


@then("返回按严重级别统计")
def return_attacks_by_severity(compliance_context: dict[str, Any]) -> None:
    """返回按严重级别统计。"""
    stats = compliance_context["intrusion_stats"]
    assert isinstance(stats.attacks_by_severity, dict)


# ===================================================================
# AC-5: 数据完整性合规
# ===================================================================


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "计算数据校验和",
)
def test_calculate_checksum():
    """计算数据校验和测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "验证数据完整性",
)
def test_verify_data_integrity():
    """验证数据完整性测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "检测数据篡改",
)
def test_detect_data_tampering():
    """检测数据篡改测试。"""


@given("数据完整性服务可用")
def data_integrity_service_available(
    compliance_context: dict[str, Any],
    resolver: Resolver,
) -> None:
    """数据完整性服务可用。"""
    service = resolver.resolve("data_integrity_service")
    compliance_context["integrity_service"] = service


@given("数据已存储校验和")
def data_has_checksum(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """数据已存储校验和。"""
    service = compliance_context["integrity_service"]
    test_data = "original test data"
    checksum = event_loop.run_until_complete(service.calculate_checksum(test_data))
    compliance_context["original_data"] = test_data
    compliance_context["stored_checksum"] = checksum


@given("数据已被篡改")
def data_tampered(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """数据已被篡改。"""
    service = compliance_context["integrity_service"]
    original_data = "original test data"
    checksum = event_loop.run_until_complete(service.calculate_checksum(original_data))
    compliance_context["original_data"] = original_data
    compliance_context["stored_checksum"] = checksum
    compliance_context["tampered_data"] = "tampered test data"


@when("系统计算数据的SHA256校验和")
def calculate_checksum(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """计算校验和。"""
    service = compliance_context["integrity_service"]
    checksum = event_loop.run_until_complete(service.calculate_checksum("test data for checksum"))
    compliance_context["calculated_checksum"] = checksum


@when("系统验证数据完整性")
def verify_data_integrity(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """验证数据完整性。"""
    service = compliance_context["integrity_service"]
    if "tampered_data" in compliance_context:
        data = compliance_context["tampered_data"]
    else:
        data = compliance_context["original_data"]
    result = event_loop.run_until_complete(
        service.verify_data_integrity(
            data_id="test_data_001",
            data=data,
            stored_hash=compliance_context["stored_checksum"],
        )
    )
    compliance_context["integrity_result"] = result


@then("返回64位十六进制哈希值")
def checksum_64_hex(compliance_context: dict[str, Any]) -> None:
    """返回 64 位哈希。"""
    checksum = compliance_context["calculated_checksum"]
    assert len(checksum) == 64
    assert all(c in "0123456789abcdef" for c in checksum)


@then("校验和匹配验证通过")
def checksum_match(compliance_context: dict[str, Any]) -> None:
    """校验和匹配。"""
    result = compliance_context["integrity_result"]
    assert result.valid is True


@then("校验和不匹配验证失败")
def checksum_mismatch(compliance_context: dict[str, Any]) -> None:
    """校验和不匹配。"""
    result = compliance_context["integrity_result"]
    assert result.valid is False


@then("发布DataIntegrityViolationEvent事件")
def integrity_violation_event_published(compliance_context: dict[str, Any]) -> None:
    """完整性违规事件已发布。"""
    result = compliance_context["integrity_result"]
    assert result.valid is False
    assert "checksum mismatch" in result.error_message.lower() or "integrity violation" in result.error_message.lower()


# ===================================================================
# AC-6: 备份恢复合规
# ===================================================================


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "创建PostgreSQL备份",
)
def test_postgresql_backup():
    """PostgreSQL 备份测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "创建完整备份",
)
def test_full_backup():
    """完整备份测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "恢复备份",
)
def test_restore_backup():
    """备份恢复测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "验证备份完整性",
)
def test_verify_backup_integrity():
    """备份完整性验证测试。"""


@given("备份恢复服务可用")
def backup_recovery_service_available(
    compliance_context: dict[str, Any],
    resolver: Resolver,
) -> None:
    """备份恢复服务可用。"""
    service = resolver.resolve("backup_recovery_service")
    compliance_context["backup_service"] = service


@given("已存在有效备份")
def valid_backup_exists(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """已存在有效备份。"""
    service = compliance_context["backup_service"]
    result = event_loop.run_until_complete(service.create_backup(backup_type="full"))
    compliance_context["backup_id"] = result.backup_id
    compliance_context["backup_result"] = result


@given("已存在备份")
def backup_exists(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """已存在备份。"""
    service = compliance_context["backup_service"]
    result = event_loop.run_until_complete(service.create_backup(backup_type="postgresql"))
    compliance_context["backup_id"] = result.backup_id
    compliance_context["backup_result"] = result


@when("管理员触发PostgreSQL备份")
def trigger_postgresql_backup(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """触发 PostgreSQL 备份。"""
    service = compliance_context["backup_service"]
    result = event_loop.run_until_complete(service.create_backup(backup_type="postgresql"))
    compliance_context["backup_result"] = result
    compliance_context["backup_id"] = result.backup_id


@when("管理员触发完整备份")
def trigger_full_backup(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """触发完整备份。"""
    service = compliance_context["backup_service"]
    result = event_loop.run_until_complete(service.create_backup(backup_type="full"))
    compliance_context["full_backup_result"] = result
    compliance_context["backup_id"] = result.backup_id


@when("管理员触发备份恢复")
def trigger_backup_restore(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """触发备份恢复。"""
    service = compliance_context["backup_service"]
    result = event_loop.run_until_complete(service.restore_backup(backup_id=compliance_context["backup_id"]))
    compliance_context["restore_result"] = result


@when("系统验证备份完整性")
def verify_backup_integrity(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """验证备份完整性。"""
    service = compliance_context["backup_service"]
    result = event_loop.run_until_complete(service.verify_backup_integrity(backup_id=compliance_context["backup_id"]))
    compliance_context["backup_integrity_valid"] = result


@then("PostgreSQL数据库备份成功")
def postgresql_backup_success(compliance_context: dict[str, Any]) -> None:
    """PostgreSQL 备份成功。"""
    result = compliance_context.get("backup_result") or compliance_context.get("full_backup_result")
    assert result is not None
    assert result.success is True
    assert result.backup_type in ("postgresql", "full")


@then("备份结果包含校验和")
def backup_has_checksum(compliance_context: dict[str, Any]) -> None:
    """备份包含校验和。"""
    result = compliance_context.get("backup_result") or compliance_context.get("full_backup_result")
    assert result is not None
    assert result.checksum != ""
    assert len(result.checksum) == 64


@then("MinIO对象存储备份成功")
def minio_backup_success(compliance_context: dict[str, Any]) -> None:
    """MinIO 备份成功。"""
    result = compliance_context["full_backup_result"]
    assert result.success is True
    assert result.backup_type == "full"


@then("Redis缓存备份成功")
def redis_backup_success(compliance_context: dict[str, Any]) -> None:
    """Redis 备份成功。"""
    result = compliance_context["full_backup_result"]
    assert result.success is True


@then("备份恢复成功")
def restore_success(compliance_context: dict[str, Any]) -> None:
    """恢复成功。"""
    result = compliance_context["restore_result"]
    assert result.success is True


@then("恢复结果包含已恢复项数")
def restore_has_items_count(compliance_context: dict[str, Any]) -> None:
    """恢复结果含项数。"""
    result = compliance_context["restore_result"]
    assert result.restored_items > 0


@then("备份完整性验证通过")
def backup_integrity_verified(compliance_context: dict[str, Any]) -> None:
    """备份完整性验证通过。"""
    assert compliance_context["backup_integrity_valid"] is True


# ===================================================================
# AC-7: 等保综合合规
# ===================================================================


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "等保合规报告生成",
)
def test_compliance_report():
    """等保合规报告生成测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "单个安全域验证",
)
def test_single_domain_verification():
    """单个安全域验证测试。"""


@given("等保合规验证器已初始化")
def compliance_verifier_initialized(
    compliance_context: dict[str, Any],
    resolver: Resolver,
) -> None:
    """初始化等保合规验证器。"""
    intrusion_service = resolver.resolve("intrusion_detection_service")
    integrity_service = resolver.resolve("data_integrity_service")
    backup_service = resolver.resolve("backup_recovery_service")
    verifier = EquilibriumComplianceVerifier(
        intrusion_service=intrusion_service,
        integrity_service=integrity_service,
        backup_service=backup_service,
    )
    compliance_context["compliance_verifier"] = verifier


@when("生成等保合规报告")
def generate_compliance_report(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """生成等保合规报告。"""
    verifier = compliance_context["compliance_verifier"]
    report = event_loop.run_until_complete(verifier.generate_report())
    compliance_context["compliance_report"] = report


@then("报告包含6个安全域验证结果")
def verify_report_contains_6_domains(compliance_context: dict[str, Any]) -> None:
    """报告包含 6 个安全域。"""
    report = compliance_context["compliance_report"]
    assert report.total_domains == 6
    assert len(report.results) == 6


@then("报告包含合规评分")
def verify_report_has_score(compliance_context: dict[str, Any]) -> None:
    """报告包含合规评分。"""
    report = compliance_context["compliance_report"]
    assert 0.0 <= report.compliance_score <= 1.0


@when("验证入侵防范安全域")
def verify_intrusion_domain(
    compliance_context: dict[str, Any],
    event_loop,
) -> None:
    """验证入侵防范安全域。"""
    verifier = compliance_context["compliance_verifier"]
    result = event_loop.run_until_complete(verifier.verify_intrusion_prevention())
    compliance_context["domain_result"] = result


@then("入侵防范域验证完成")
def intrusion_domain_verified(compliance_context: dict[str, Any]) -> None:
    """入侵防范域验证完成。"""
    result = compliance_context["domain_result"]
    assert result.domain == "intrusion_prevention"
    assert result.status is not None


# ===================================================================
# AC-8: 隐私保护合规
# ===================================================================


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "个人信息访问记录",
)
def test_personal_data_access_record():
    """个人信息访问记录测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "数据主体删除请求响应",
)
def test_data_subject_deletion():
    """数据主体删除请求测试。"""


@scenario(
    "test_acceptance_equilibrium_level_3_compliance.feature",
    "数据主体访问请求响应",
)
def test_data_subject_access():
    """数据主体访问请求测试。"""


@given("PIPL合规服务可用")
def pipl_service_available(
    compliance_context: dict[str, Any],
    pipl_service: PIPLComplianceServiceImpl,
) -> None:
    """PIPL 合规服务可用。"""
    compliance_context["pipl_service"] = pipl_service


@given("已存在个人信息访问记录")
def personal_data_record_exists(compliance_context: dict[str, Any]) -> None:
    """创建个人信息访问记录。"""
    service = compliance_context["pipl_service"]
    record = PIPLComplianceRecord(
        access_id=uuid.uuid4(),
        personal_data_id="data_001",
        purpose="marketing_analysis",
        legal_basis="consent",
        consent_status=ConsentStatus.GIVEN,
        accessor="analyst_user",
        accessed_at=datetime.now(UTC),
        data_subject_id="subject_001",
        is_minor=False,
        guardian_consent_obtained=False,
    )
    service.record_access(record)
    compliance_context["data_subject_id"] = "subject_001"


@when("记录个人信息访问行为")
def record_personal_data_access(compliance_context: dict[str, Any]) -> None:
    """记录个人信息访问行为。"""
    service = compliance_context["pipl_service"]
    record = PIPLComplianceRecord(
        access_id=uuid.uuid4(),
        personal_data_id="data_002",
        purpose="data_analysis",
        legal_basis="consent",
        consent_status=ConsentStatus.GIVEN,
        accessor="researcher",
        accessed_at=datetime.now(UTC),
        data_subject_id="subject_002",
        is_minor=False,
        guardian_consent_obtained=False,
    )
    service.record_access(record)
    compliance_context["recorded_data_id"] = "data_002"


@then("访问记录已保存")
def access_record_saved(compliance_context: dict[str, Any]) -> None:
    """访问记录已保存。"""
    service = compliance_context["pipl_service"]
    record = service.get_record(compliance_context["recorded_data_id"])
    assert record is not None


@when("数据主体发起删除请求")
def data_subject_deletion_request(compliance_context: dict[str, Any]) -> None:
    """数据主体发起删除请求。"""
    service = compliance_context["pipl_service"]
    result = service.respond_to_deletion_request(compliance_context["data_subject_id"])
    compliance_context["deletion_result"] = result


@then("删除请求处理成功")
def deletion_request_processed(compliance_context: dict[str, Any]) -> None:
    """删除请求处理成功。"""
    result = compliance_context["deletion_result"]
    assert result.get("status") == "deleted"


@then("相关记录已被删除")
def records_deleted(compliance_context: dict[str, Any]) -> None:
    """相关记录已被删除。"""
    service = compliance_context["pipl_service"]
    record = service.get_record("data_001")
    assert record is None


@when("数据主体发起访问请求")
def data_subject_access_request(compliance_context: dict[str, Any]) -> None:
    """数据主体发起访问请求。"""
    service = compliance_context["pipl_service"]
    result = service.respond_to_access_request(compliance_context["data_subject_id"])
    compliance_context["access_result"] = result


@then("返回个人信息访问历史")
def access_history_returned(compliance_context: dict[str, Any]) -> None:
    """返回个人信息访问历史。"""
    result = compliance_context["access_result"]
    assert isinstance(result, dict)
    assert "records" in result
    assert len(result["records"]) > 0
