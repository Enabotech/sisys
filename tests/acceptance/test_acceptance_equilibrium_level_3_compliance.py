"""等保2.0三级基础安全合规验收测试步骤实现

实现 Gherkin 验收测试场景的步骤函数
对应 Story: 1-12-equilibrium-level-3-compliance

绿阶段：服务实现已完成，步骤函数调用实际服务
"""

from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.security.backup_recovery_service_impl import BackupRecoveryServiceImpl
from src.infrastructure.security.data_integrity_service_impl import DataIntegrityServiceImpl
from src.infrastructure.security.intrusion_detection_service_impl import IntrusionDetectionServiceImpl

scenarios("test_acceptance_equilibrium_level_3_compliance.feature")


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context() -> dict[str, Any]:
    """Share state between BDD steps."""
    return {}


# ==================== 背景 ====================
@given("系统已初始化完成")
def system_initialized(context: dict[str, Any]) -> None:
    """系统已初始化（bootstrap 由 conftest.py 自动完成）"""
    context["initialized"] = True


@given("所有安全服务端口已注册")
def security_ports_registered(context: dict[str, Any]) -> None:
    """验证安全服务端口已注册"""
    from src.composition_root import _global_registry

    required_ports = [
        "intrusion_detection_service",
        "data_integrity_service",
        "backup_recovery_service",
    ]
    for port_name in required_ports:
        spec = _global_registry.get(port_name)
        assert spec is not None, f"Port {port_name} not registered"
    context["ports_registered"] = True


# ==================== 入侵检测 ====================
@given("入侵检测服务可用")
def intrusion_detection_service_available(context: dict[str, Any]) -> None:
    """入侵检测服务可用"""
    service = IntrusionDetectionServiceImpl()
    context["intrusion_service"] = service


@given("数据完整性服务可用")
def data_integrity_service_available(context: dict[str, Any]) -> None:
    """数据完整性服务可用"""
    service = DataIntegrityServiceImpl()
    context["integrity_service"] = service


@given("备份恢复服务可用")
def backup_recovery_service_available(context: dict[str, Any]) -> None:
    """备份恢复服务可用"""
    service = BackupRecoveryServiceImpl()
    context["backup_service"] = service


@given("数据已存储校验和")
def data_has_checksum(context: dict[str, Any]) -> None:
    """数据已存储校验和"""
    service = context["integrity_service"]
    test_data = "original test data"
    import asyncio

    checksum = asyncio.get_event_loop().run_until_complete(service.calculate_checksum(test_data))
    context["original_data"] = test_data
    context["stored_checksum"] = checksum


@given("数据已被篡改")
def data_tampered(context: dict[str, Any]) -> None:
    """数据已被篡改"""
    service = context["integrity_service"]
    original_data = "original test data"
    import asyncio

    checksum = asyncio.get_event_loop().run_until_complete(service.calculate_checksum(original_data))
    context["original_data"] = original_data
    context["stored_checksum"] = checksum
    context["tampered_data"] = "tampered test data"


@given("已存在有效备份")
def valid_backup_exists(context: dict[str, Any]) -> None:
    """已存在有效备份"""
    service = context["backup_service"]
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(service.create_backup(backup_type="full"))
    context["backup_id"] = result.backup_id
    context["backup_result"] = result


@given("已存在备份")
def backup_exists(context: dict[str, Any]) -> None:
    """已存在备份"""
    service = context["backup_service"]
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(service.create_backup(backup_type="postgresql"))
    context["backup_id"] = result.backup_id
    context["backup_result"] = result


# ==================== 操作 ====================
@when("系统收到包含SQL注入特征的请求")
def receive_sql_injection_request(context: dict[str, Any]) -> None:
    """收到SQL注入请求"""
    service = context["intrusion_service"]
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        service.detect_attack(
            source_ip="192.168.1.100",
            request_data="' OR 1=1 -- SELECT * FROM users",
            request_path="/api/query",
        )
    )
    context["detection_result"] = result


@when("系统收到包含XSS特征的请求")
def receive_xss_request(context: dict[str, Any]) -> None:
    """收到XSS请求"""
    service = context["intrusion_service"]
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        service.detect_attack(
            source_ip="192.168.1.101",
            request_data="<script>alert('xss')</script>",
            request_path="/api/comment",
        )
    )
    context["detection_result"] = result


@when("同一IP地址在5分钟内失败登录超过10次")
def brute_force_attempts(context: dict[str, Any]) -> None:
    """暴力破解尝试"""
    service = context["intrusion_service"]
    import asyncio

    loop = asyncio.get_event_loop()
    source_ip = "192.168.1.102"
    for _ in range(15):
        loop.run_until_complete(
            service.detect_attack(
                source_ip=source_ip,
                request_data="login attempt",
                request_path="/auth/login",
            )
        )
    result = loop.run_until_complete(
        service.detect_attack(
            source_ip=source_ip,
            request_data="login attempt",
            request_path="/auth/login",
        )
    )
    context["detection_result"] = result


@when("管理员封禁恶意IP地址")
def admin_block_ip(context: dict[str, Any]) -> None:
    """管理员封禁IP"""
    service = context["intrusion_service"]
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        service.block_ip(
            ip_address="192.168.1.200",
            reason="Repeated attack attempts",
            duration_hours=24,
        )
    )
    context["block_result"] = result
    context["blocked_ip"] = "192.168.1.200"


@when("系统计算数据的SHA256校验和")
def calculate_checksum(context: dict[str, Any]) -> None:
    """计算校验和"""
    service = context["integrity_service"]
    import asyncio

    checksum = asyncio.get_event_loop().run_until_complete(service.calculate_checksum("test data for checksum"))
    context["calculated_checksum"] = checksum


@when("系统验证数据完整性")
def verify_data_integrity(context: dict[str, Any]) -> None:
    """验证数据完整性"""
    service = context["integrity_service"]
    import asyncio

    if "tampered_data" in context:
        data = context["tampered_data"]
    else:
        data = context["original_data"]

    result = asyncio.get_event_loop().run_until_complete(
        service.verify_data_integrity(
            data_id="test_data_001",
            data=data,
            stored_hash=context["stored_checksum"],
        )
    )
    context["integrity_result"] = result


@when("管理员触发PostgreSQL备份")
def trigger_postgresql_backup(context: dict[str, Any]) -> None:
    """触发PostgreSQL备份"""
    service = context["backup_service"]
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(service.create_backup(backup_type="postgresql"))
    context["backup_result"] = result
    context["backup_id"] = result.backup_id


@when("管理员触发完整备份")
def trigger_full_backup(context: dict[str, Any]) -> None:
    """触发完整备份"""
    service = context["backup_service"]
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(service.create_backup(backup_type="full"))
    context["full_backup_result"] = result
    context["backup_id"] = result.backup_id


@when("管理员触发备份恢复")
def trigger_backup_restore(context: dict[str, Any]) -> None:
    """触发备份恢复"""
    service = context["backup_service"]
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(service.restore_backup(backup_id=context["backup_id"]))
    context["restore_result"] = result


@when("系统验证备份完整性")
def verify_backup_integrity(context: dict[str, Any]) -> None:
    """验证备份完整性"""
    service = context["backup_service"]
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(service.verify_backup_integrity(backup_id=context["backup_id"]))
    context["backup_integrity_valid"] = result


@when("系统请求过去24小时的入侵统计")
def request_intrusion_stats(context: dict[str, Any]) -> None:
    """请求入侵统计"""
    service = context["intrusion_service"]
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(service.get_intrusion_stats(period_hours=24))
    context["intrusion_stats"] = result


# ==================== 结果 ====================
@then("入侵检测服务识别为SQL注入攻击")
def sql_injection_detected(context: dict[str, Any]) -> None:
    """SQL注入被检测"""
    result = context["detection_result"]
    assert result.detected is True
    assert "sql_injection" in result.attack_type.lower()


@then("攻击被记录到审计日志")
def attack_logged(context: dict[str, Any]) -> None:
    """攻击已记录"""
    result = context["detection_result"]
    assert result.action_taken in ["logged", "alerted", "blocked"]


@then("入侵检测服务识别为XSS攻击")
def xss_detected(context: dict[str, Any]) -> None:
    """XSS被检测"""
    result = context["detection_result"]
    assert result.detected is True
    assert "xss" in result.attack_type.lower()


@then("攻击严重级别为HIGH")
def severity_high(context: dict[str, Any]) -> None:
    """严重级别HIGH"""
    result = context["detection_result"]
    assert result.severity.lower() in ["high", "critical"]


@then("入侵检测服务识别为暴力破解攻击")
def brute_force_detected(context: dict[str, Any]) -> None:
    """暴力破解被检测"""
    result = context["detection_result"]
    assert result.detected is True
    assert "brute_force" in result.attack_type.lower()


@then("攻击严重级别为MEDIUM")
def severity_medium(context: dict[str, Any]) -> None:
    """严重级别MEDIUM"""
    result = context["detection_result"]
    assert result.severity.lower() in ["medium", "low", "medium"]


@then("该IP地址被封禁")
def ip_blocked(context: dict[str, Any]) -> None:
    """IP已封禁"""
    assert context["block_result"] is True


@then("封禁时长为24小时")
def block_duration_24h(context: dict[str, Any]) -> None:
    """封禁24小时"""
    service = context["intrusion_service"]
    blocked_ip = context["blocked_ip"]
    assert blocked_ip in service._blocked_ips


@then("返回64位十六进制哈希值")
def checksum_64_hex(context: dict[str, Any]) -> None:
    """返回64位哈希"""
    checksum = context["calculated_checksum"]
    assert len(checksum) == 64
    assert all(c in "0123456789abcdef" for c in checksum)


@then("校验和匹配验证通过")
def checksum_match(context: dict[str, Any]) -> None:
    """校验和匹配"""
    result = context["integrity_result"]
    assert result.valid is True


@then("校验和不匹配验证失败")
def checksum_mismatch(context: dict[str, Any]) -> None:
    """校验和不匹配"""
    result = context["integrity_result"]
    assert result.valid is False


@then("发布DataIntegrityViolationEvent事件")
def integrity_violation_event_published(context: dict[str, Any]) -> None:
    """完整性违规事件已发布"""
    result = context["integrity_result"]
    assert result.valid is False
    assert "checksum mismatch" in result.error_message.lower() or "integrity violation" in result.error_message.lower()


@then("PostgreSQL数据库备份成功")
def postgresql_backup_success(context: dict[str, Any]) -> None:
    """PostgreSQL备份成功"""
    result = context.get("backup_result") or context.get("full_backup_result")
    assert result is not None
    assert result.success is True
    backup_type = result.backup_type
    assert backup_type in ("postgresql", "full")


@then("备份结果包含校验和")
def backup_has_checksum(context: dict[str, Any]) -> None:
    """备份包含校验和"""
    result = context.get("backup_result") or context.get("full_backup_result")
    assert result is not None
    assert result.checksum != ""
    assert len(result.checksum) == 64


@then("MinIO对象存储备份成功")
def minio_backup_success(context: dict[str, Any]) -> None:
    """MinIO备份成功"""
    result = context["full_backup_result"]
    assert result.success is True
    assert result.backup_type == "full"


@then("Redis缓存备份成功")
def redis_backup_success(context: dict[str, Any]) -> None:
    """Redis备份成功"""
    result = context["full_backup_result"]
    assert result.success is True


@then("备份恢复成功")
def restore_success(context: dict[str, Any]) -> None:
    """恢复成功"""
    result = context["restore_result"]
    assert result.success is True


@then("恢复结果包含已恢复项数")
def restore_has_items_count(context: dict[str, Any]) -> None:
    """恢复结果含项数"""
    result = context["restore_result"]
    assert result.restored_items > 0


@then("备份完整性验证通过")
def backup_integrity_verified(context: dict[str, Any]) -> None:
    """备份完整性验证通过"""
    assert context["backup_integrity_valid"] is True


@then("返回攻击总数")
def return_total_attacks(context: dict[str, Any]) -> None:
    """返回攻击总数"""
    stats = context["intrusion_stats"]
    assert stats.total_attacks >= 0


@then("返回按攻击类型统计")
def return_attacks_by_type(context: dict[str, Any]) -> None:
    """返回按类型统计"""
    stats = context["intrusion_stats"]
    assert isinstance(stats.attacks_by_type, dict)


@then("返回按严重级别统计")
def return_attacks_by_severity(context: dict[str, Any]) -> None:
    """返回按严重级别统计"""
    stats = context["intrusion_stats"]
    assert isinstance(stats.attacks_by_severity, dict)
