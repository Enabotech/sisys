"""入侵检测服务单元测试

等保2.0三级入侵防范要求验证:
- AC-4.1: SQL注入检测准确率≥95%
- AC-4.2: XSS攻击检测准确率≥95%
- AC-4.3: 暴力破解检测（频率阈值）
- AC-4.4: 10种攻击类型全覆盖
- AC-4.5: 入侵告警机制生效
- AC-4.6: IP阻断机制就绪

本测试验证 IntrusionDetectionServiceImpl 的等保合规实现

对应 Story: 1-12-equilibrium-level-3-compliance Task 2 Subtask 2.1-2.12
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.domain.events.compliance_events import AttackType, IntrusionSeverity
from src.domain.value_objects.intrusion_detection_result import (
    IntrusionStats,
)
from src.infrastructure.security.intrusion_detection_service_impl import (
    IntrusionDetectionServiceImpl,
)


@pytest.fixture
def intrusion_service() -> IntrusionDetectionServiceImpl:
    """创建入侵检测服务实例（含 mock 依赖）"""
    mock_attack_repo = AsyncMock()
    mock_event_publisher = AsyncMock()
    return IntrusionDetectionServiceImpl(
        attack_repository=mock_attack_repo,
        event_publisher=mock_event_publisher,
    )


class TestSQLInjectionDetection:
    """SQL注入检测验证 (AC-4.1)"""

    async def test_detect_basic_sql_injection(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """检测基本SQL注入攻击"""
        result = await intrusion_service.detect_attack(
            source_ip="192.168.1.100",
            request_data="' OR 1=1 --",
            request_path="/api/v1/users",
        )
        assert result.detected is True
        assert result.attack_type == AttackType.SQL_INJECTION.value
        assert result.severity in [
            IntrusionSeverity.HIGH.value,
            IntrusionSeverity.CRITICAL.value,
        ]

    async def test_detect_union_sql_injection(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """检测UNION SQL注入攻击"""
        result = await intrusion_service.detect_attack(
            source_ip="192.168.1.100",
            request_data="SELECT * FROM users UNION SELECT * FROM passwords",
            request_path="/api/v1/search",
        )
        assert result.detected is True
        assert result.attack_type == AttackType.SQL_INJECTION.value

    async def test_detect_sql_injection_drop_table(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """检测DROP TABLE SQL注入攻击"""
        result = await intrusion_service.detect_attack(
            source_ip="192.168.1.100",
            request_data="'; DROP TABLE users; --",
            request_path="/api/v1/admin",
        )
        assert result.detected is True
        assert result.attack_type == AttackType.SQL_INJECTION.value
        assert result.severity == IntrusionSeverity.CRITICAL.value

    async def test_no_false_positive_normal_query(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """正常查询不应误报为SQL注入"""
        result = await intrusion_service.detect_attack(
            source_ip="192.168.1.100",
            request_data="SELECT product_name FROM products WHERE id = 5",
            request_path="/api/v1/products",
        )
        # 这是合法的业务查询，不应被检测为攻击
        assert result.detected is False or result.attack_type != AttackType.SQL_INJECTION.value


class TestXSSDetection:
    """XSS攻击检测验证 (AC-4.2)"""

    async def test_detect_script_tag_xss(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """检测<script>标签XSS攻击"""
        result = await intrusion_service.detect_attack(
            source_ip="192.168.1.101",
            request_data="<script>alert('XSS')</script>",
            request_path="/api/v1/comments",
        )
        assert result.detected is True
        assert result.attack_type == AttackType.XSS.value

    async def test_detect_onclick_xss(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """检测onclick事件XSS攻击"""
        result = await intrusion_service.detect_attack(
            source_ip="192.168.1.101",
            request_data="<img src=x onerror=alert('XSS')>",
            request_path="/api/v1/upload",
        )
        assert result.detected is True
        assert result.attack_type == AttackType.XSS.value

    async def test_detect_javascript_protocol_xss(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """检测javascript:协议XSS攻击"""
        result = await intrusion_service.detect_attack(
            source_ip="192.168.1.101",
            request_data="javascript:alert(document.cookie)",
            request_path="/api/v1/redirect",
        )
        assert result.detected is True
        assert result.attack_type == AttackType.XSS.value


class TestBruteForceDetection:
    """暴力破解检测验证 (AC-4.3)"""

    async def test_detect_brute_force_from_same_ip(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """检测同一IP的暴力破解尝试"""
        # 模拟同一IP多次快速失败登录
        for i in range(12):
            await intrusion_service.detect_attack(
                source_ip="10.0.0.50",
                request_data="login_failed",
                request_path="/api/v1/auth/login",
            )

        result = await intrusion_service.detect_attack(
            source_ip="10.0.0.50",
            request_data="login_failed",
            request_path="/api/v1/auth/login",
        )
        # 13次失败后应触发暴力破解检测
        assert result.detected is True
        assert result.attack_type == AttackType.BRUTE_FORCE.value
        assert result.severity == IntrusionSeverity.MEDIUM.value


class TestCommandInjectionDetection:
    """命令注入检测验证"""

    async def test_detect_command_injection_pipe(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """检测管道命令注入"""
        result = await intrusion_service.detect_attack(
            source_ip="192.168.1.102",
            request_data="; cat /etc/passwd | grep root",
            request_path="/api/v1/system",
        )
        assert result.detected is True
        assert result.attack_type == AttackType.COMMAND_INJECTION.value

    async def test_detect_command_injection_backticks(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """检测反引号命令注入"""
        result = await intrusion_service.detect_attack(
            source_ip="192.168.1.102",
            request_data="`whoami`",
            request_path="/api/v1/exec",
        )
        assert result.detected is True
        assert result.attack_type == AttackType.COMMAND_INJECTION.value


class TestPathTraversalDetection:
    """路径遍历检测验证"""

    async def test_detect_path_traversal_dotdot(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """检测../路径遍历攻击"""
        result = await intrusion_service.detect_attack(
            source_ip="192.168.1.103",
            request_data="../../../etc/passwd",
            request_path="/api/v1/files",
        )
        assert result.detected is True
        assert result.attack_type == AttackType.PATH_TRAVERSAL.value

    async def test_detect_path_traversal_encoded(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """检测URL编码路径遍历攻击"""
        result = await intrusion_service.detect_attack(
            source_ip="192.168.1.103",
            request_data="..%2F..%2F..%2Fetc%2Fpasswd",
            request_path="/api/v1/files",
        )
        assert result.detected is True
        assert result.attack_type == AttackType.PATH_TRAVERSAL.value


class TestRateLimitViolationDetection:
    """速率限制违规检测验证"""

    async def test_detect_rate_limit_violation(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """检测速率限制违规"""
        # 模拟高频请求
        for i in range(100):
            await intrusion_service.detect_attack(
                source_ip="10.0.0.99",
                request_data=f"request_{i}",
                request_path="/api/v1/data",
            )

        result = await intrusion_service.detect_attack(
            source_ip="10.0.0.99",
            request_data="request_100",
            request_path="/api/v1/data",
        )
        # 100次请求后应触发速率限制违规
        assert result.detected is True
        assert result.attack_type == AttackType.RATE_LIMIT_VIOLATION.value


class TestIntrusionStats:
    """入侵统计数据验证 (AC-4.4)"""

    async def test_get_intrusion_stats_returns_stats(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """获取入侵统计数据应返回正确格式"""
        stats = await intrusion_service.get_intrusion_stats(period_hours=24)
        assert isinstance(stats, IntrusionStats)
        assert stats.total_attacks >= 0
        assert isinstance(stats.attacks_by_type, dict)
        assert isinstance(stats.attacks_by_severity, dict)
        assert isinstance(stats.blocked_ips, list)


class TestIPBlocking:
    """IP阻断机制验证 (AC-4.6)"""

    async def test_block_ip_returns_true(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """封禁IP应返回成功"""
        result = await intrusion_service.block_ip(
            ip_address="192.168.1.200",
            reason="SQL injection attack detected",
            duration_hours=24,
        )
        assert result is True

    async def test_blocked_ip_in_stats(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """已封禁IP应出现在统计数据中"""
        await intrusion_service.block_ip(
            ip_address="10.0.0.50",
            reason="Brute force attack",
            duration_hours=48,
        )
        stats = await intrusion_service.get_intrusion_stats(period_hours=24)
        assert "10.0.0.50" in stats.blocked_ips

    async def test_blocked_ip_detection_action(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """已封禁IP的请求应被阻断"""
        await intrusion_service.block_ip(
            ip_address="192.168.1.200",
            reason="Malicious IP",
            duration_hours=24,
        )
        result = await intrusion_service.detect_attack(
            source_ip="192.168.1.200",
            request_data="normal request",
            request_path="/api/v1/data",
        )
        assert result.detected is True
        assert result.action_taken == "blocked"


class TestDetectionResultStructure:
    """检测结果结构验证"""

    async def test_detection_result_has_required_fields(
        self,
        intrusion_service: IntrusionDetectionServiceImpl,
    ) -> None:
        """检测结果应包含所有必需字段"""
        result = await intrusion_service.detect_attack(
            source_ip="192.168.1.100",
            request_data="' OR 1=1 --",
            request_path="/api/v1/users",
        )
        assert hasattr(result, "detected")
        assert hasattr(result, "attack_type")
        assert hasattr(result, "severity")
        assert hasattr(result, "confidence")
        assert hasattr(result, "description")
        assert hasattr(result, "source_ip")
        assert hasattr(result, "evidence")
        assert hasattr(result, "action_taken")
