"""基础设施层入侵检测服务模块

基于 IntrusionDetectionServicePort 接口实现多类型攻击检测、入侵告警和IP阻断
用于等保2.0三级入侵防范合规

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from src.domain.events.compliance_events import AttackType, IntrusionAction, IntrusionSeverity
from src.domain.ports.intrusion_detection_service import IntrusionDetectionServicePort
from src.domain.value_objects.intrusion_detection_result import (
    AttackDetectionResult,
    IntrusionStats,
)


class IntrusionDetectionServiceImpl(IntrusionDetectionServicePort):
    """入侵检测服务实现，负责攻击检测、告警和IP阻断

    Attributes:
        _attack_repo: 攻击记录仓储（可选）
        _event_publisher: 事件发布器（可选）
        _blocked_ips: 已封禁IP字典 {ip: expiry_time}
        _attack_history: 攻击历史记录
        _request_counts: 请求频率计数器 {ip: [timestamps]}
    """

    # SQL注入正则模式
    _SQL_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"(?i)(\b(union\s+select)\b)", re.IGNORECASE),
        re.compile(r"(?i)(\b(or|and)\s+\d+\s*=\s*\d+)", re.IGNORECASE),
        re.compile(r"(?i)(;\s*(drop|delete|insert|update|alter|create)\s+)", re.IGNORECASE),
        re.compile(r"(?i)(--|\#|/\*)", re.IGNORECASE),
        re.compile(r"(?i)('\s*(or|and)\s+)", re.IGNORECASE),
        re.compile(r"(?i)(\bexec\s*\(|execute\s+)", re.IGNORECASE),
    ]

    # 高危SQL关键词（仅在请求上下文中触发）
    _SQL_HIGH_RISK_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"(?i)(\bdrop\s+table\b)", re.IGNORECASE),
        re.compile(r"(?i)(\btruncate\s+table\b)", re.IGNORECASE),
        re.compile(r"(?i)(\bdelete\s+from\b\s+(?!.*where))", re.IGNORECASE),
    ]

    # XSS正则模式
    _XSS_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"(?i)<\s*script", re.IGNORECASE),
        re.compile(r"(?i)\bon\w+\s*=", re.IGNORECASE),
        re.compile(r"(?i)javascript\s*:", re.IGNORECASE),
        re.compile(r"(?i)<\s*img[^>]+onerror", re.IGNORECASE),
        re.compile(r"(?i)<\s*svg[^>]+onload", re.IGNORECASE),
        re.compile(r"(?i)(alert|confirm|prompt)\s*\(", re.IGNORECASE),
    ]

    # 命令注入正则模式
    _COMMAND_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r";\s*(cat|ls|rm|wget|curl|bash|sh|python|perl|nc)\b", re.IGNORECASE),
        re.compile(r"`[^`]+`", re.IGNORECASE),
        re.compile(r"\$\([^)]+\)", re.IGNORECASE),
        re.compile(r"\|\s*(cat|ls|rm|wget|curl|bash|sh)\b", re.IGNORECASE),
    ]

    # 路径遍历正则模式
    _PATH_TRAVERSAL_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"\.\./", re.IGNORECASE),
        re.compile(r"\.\.\\" "", re.IGNORECASE),
        re.compile(r"%2e%2e%2f", re.IGNORECASE),
        re.compile(r"%2e%2e/", re.IGNORECASE),
        re.compile(r"\.\.%2f", re.IGNORECASE),
        re.compile(r"\.\.%5c", re.IGNORECASE),
    ]

    # 暴力破解阈值
    _BRUTE_FORCE_THRESHOLD = 10
    _BRUTE_FORCE_WINDOW_SECONDS = 300

    # 速率限制阈值
    _RATE_LIMIT_THRESHOLD = 80
    _RATE_LIMIT_WINDOW_SECONDS = 60

    def __init__(
        self,
        attack_repository: Any = None,
        event_publisher: Any = None,
    ) -> None:
        """初始化入侵检测服务.

        Args:
            attack_repository: 攻击记录仓储（可选）
            event_publisher: 事件发布器（可选）
        """
        self._attack_repo = attack_repository
        self._event_publisher = event_publisher
        self._blocked_ips: dict[str, datetime] = {}
        self._attack_history: list[dict[str, Any]] = []
        self._request_counts: dict[str, list[datetime]] = defaultdict(list)

    async def detect_attack(
        self,
        source_ip: str,
        request_data: str,
        request_path: str = "",
        user_id: str = "",
    ) -> AttackDetectionResult:
        """检测请求中的攻击行为

        Args:
            source_ip: 请求来源 IP 地址
            request_data: 请求内容
            request_path: 请求路径
            user_id: 用户标识

        Returns:
            AttackDetectionResult 检测结果
        """
        now = datetime.now(UTC)

        # 检查IP是否已被封禁
        if source_ip in self._blocked_ips:
            expiry = self._blocked_ips[source_ip]
            if now < expiry:
                self._record_attack(source_ip, "blocked_request", IntrusionSeverity.HIGH.value, now)
                return AttackDetectionResult(
                    detected=True,
                    attack_type=AttackType.UNAUTHORIZED_ACCESS.value,
                    severity=IntrusionSeverity.HIGH.value,
                    confidence=1.0,
                    description=f"Blocked IP attempted access: {source_ip}",
                    source_ip=source_ip,
                    evidence=request_data[:500],
                    action_taken=IntrusionAction.BLOCKED.value,
                )
            del self._blocked_ips[source_ip]

        # 记录请求频率
        self._request_counts[source_ip].append(now)
        self._cleanup_old_requests(source_ip, now)

        # 依次检测各类攻击
        result = self._detect_sql_injection(source_ip, request_data, request_path, now)
        if result is not None:
            return result

        result = self._detect_xss(source_ip, request_data, request_path, now)
        if result is not None:
            return result

        result = self._detect_command_injection(source_ip, request_data, request_path, now)
        if result is not None:
            return result

        result = self._detect_path_traversal(source_ip, request_data, request_path, now)
        if result is not None:
            return result

        result = self._detect_brute_force(source_ip, request_path, now)
        if result is not None:
            return result

        result = self._detect_rate_limit(source_ip, now)
        if result is not None:
            return result

        return AttackDetectionResult(
            detected=False,
            source_ip=source_ip,
            evidence=request_data[:500],
        )

    async def get_intrusion_stats(
        self,
        period_hours: int = 24,
    ) -> IntrusionStats:
        """获取入侵检测统计数据

        Args:
            period_hours: 统计周期（小时）

        Returns:
            IntrusionStats 统计结果
        """
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=period_hours)

        recent_attacks = [a for a in self._attack_history if a["timestamp"] >= cutoff]

        attacks_by_type: dict[str, int] = defaultdict(int)
        attacks_by_severity: dict[str, int] = defaultdict(int)
        for attack in recent_attacks:
            attacks_by_type[attack["attack_type"]] += 1
            attacks_by_severity[attack["severity"]] += 1

        active_blocked = [ip for ip, expiry in self._blocked_ips.items() if expiry > now]

        return IntrusionStats(
            total_attacks=len(recent_attacks),
            attacks_by_type=dict(attacks_by_type),
            attacks_by_severity=dict(attacks_by_severity),
            blocked_ips=active_blocked,
        )

    async def block_ip(
        self,
        ip_address: str,
        reason: str = "",
        duration_hours: int = 24,
    ) -> bool:
        """封禁指定 IP 地址

        Args:
            ip_address: 待封禁的 IP 地址
            reason: 封禁原因
            duration_hours: 封禁时长（小时）

        Returns:
            True 表示封禁成功
        """
        expiry = datetime.now(UTC) + timedelta(hours=duration_hours)
        self._blocked_ips[ip_address] = expiry
        self._record_attack(ip_address, "ip_blocked", IntrusionSeverity.HIGH.value, datetime.now(UTC))
        return True

    def _detect_sql_injection(
        self,
        source_ip: str,
        request_data: str,
        request_path: str,
        now: datetime,
    ) -> AttackDetectionResult | None:
        """检测SQL注入攻击"""
        # 先检查高危模式
        for pattern in self._SQL_HIGH_RISK_PATTERNS:
            if pattern.search(request_data):
                self._record_attack(source_ip, AttackType.SQL_INJECTION.value, IntrusionSeverity.CRITICAL.value, now)
                return AttackDetectionResult(
                    detected=True,
                    attack_type=AttackType.SQL_INJECTION.value,
                    severity=IntrusionSeverity.CRITICAL.value,
                    confidence=0.95,
                    description="Critical SQL injection detected (destructive command)",
                    source_ip=source_ip,
                    evidence=request_data[:500],
                    action_taken=IntrusionAction.ALERTED.value,
                )

        # 检查常规SQL注入模式
        match_count = 0
        for pattern in self._SQL_PATTERNS:
            if pattern.search(request_data):
                match_count += 1

        if match_count >= 1:
            severity = IntrusionSeverity.HIGH.value
            confidence = min(0.85 + match_count * 0.05, 0.99)
            self._record_attack(source_ip, AttackType.SQL_INJECTION.value, severity, now)
            return AttackDetectionResult(
                detected=True,
                attack_type=AttackType.SQL_INJECTION.value,
                severity=severity,
                confidence=confidence,
                description=f"SQL injection detected ({match_count} patterns matched)",
                source_ip=source_ip,
                evidence=request_data[:500],
                action_taken=IntrusionAction.ALERTED.value,
            )

        return None

    def _detect_xss(
        self,
        source_ip: str,
        request_data: str,
        request_path: str,
        now: datetime,
    ) -> AttackDetectionResult | None:
        """检测XSS攻击"""
        for pattern in self._XSS_PATTERNS:
            if pattern.search(request_data):
                self._record_attack(source_ip, AttackType.XSS.value, IntrusionSeverity.HIGH.value, now)
                return AttackDetectionResult(
                    detected=True,
                    attack_type=AttackType.XSS.value,
                    severity=IntrusionSeverity.HIGH.value,
                    confidence=0.92,
                    description="XSS attack detected",
                    source_ip=source_ip,
                    evidence=request_data[:500],
                    action_taken=IntrusionAction.ALERTED.value,
                )

        return None

    def _detect_command_injection(
        self,
        source_ip: str,
        request_data: str,
        request_path: str,
        now: datetime,
    ) -> AttackDetectionResult | None:
        """检测命令注入攻击"""
        for pattern in self._COMMAND_PATTERNS:
            if pattern.search(request_data):
                self._record_attack(source_ip, AttackType.COMMAND_INJECTION.value, IntrusionSeverity.CRITICAL.value, now)
                return AttackDetectionResult(
                    detected=True,
                    attack_type=AttackType.COMMAND_INJECTION.value,
                    severity=IntrusionSeverity.CRITICAL.value,
                    confidence=0.90,
                    description="Command injection detected",
                    source_ip=source_ip,
                    evidence=request_data[:500],
                    action_taken=IntrusionAction.BLOCKED.value,
                )

        return None

    def _detect_path_traversal(
        self,
        source_ip: str,
        request_data: str,
        request_path: str,
        now: datetime,
    ) -> AttackDetectionResult | None:
        """检测路径遍历攻击"""
        for pattern in self._PATH_TRAVERSAL_PATTERNS:
            if pattern.search(request_data):
                self._record_attack(source_ip, AttackType.PATH_TRAVERSAL.value, IntrusionSeverity.HIGH.value, now)
                return AttackDetectionResult(
                    detected=True,
                    attack_type=AttackType.PATH_TRAVERSAL.value,
                    severity=IntrusionSeverity.HIGH.value,
                    confidence=0.93,
                    description="Path traversal attack detected",
                    source_ip=source_ip,
                    evidence=request_data[:500],
                    action_taken=IntrusionAction.BLOCKED.value,
                )

        return None

    def _detect_brute_force(
        self,
        source_ip: str,
        request_path: str,
        now: datetime,
    ) -> AttackDetectionResult | None:
        """检测暴力破解攻击"""
        if "/auth/login" not in request_path:
            return None

        timestamps = self._request_counts.get(source_ip, [])
        recent = [t for t in timestamps if (now - t).total_seconds() <= self._BRUTE_FORCE_WINDOW_SECONDS]

        if len(recent) >= self._BRUTE_FORCE_THRESHOLD:
            self._record_attack(source_ip, AttackType.BRUTE_FORCE.value, IntrusionSeverity.MEDIUM.value, now)
            return AttackDetectionResult(
                detected=True,
                attack_type=AttackType.BRUTE_FORCE.value,
                severity=IntrusionSeverity.MEDIUM.value,
                confidence=0.85,
                description=f"Brute force detected: {len(recent)} attempts in 5 minutes",
                source_ip=source_ip,
                evidence=f"{len(recent)} login attempts",
                action_taken=IntrusionAction.ALERTED.value,
            )

        return None

    def _detect_rate_limit(
        self,
        source_ip: str,
        now: datetime,
    ) -> AttackDetectionResult | None:
        """检测速率限制违规"""
        timestamps = self._request_counts.get(source_ip, [])
        recent = [t for t in timestamps if (now - t).total_seconds() <= self._RATE_LIMIT_WINDOW_SECONDS]

        if len(recent) > self._RATE_LIMIT_THRESHOLD:
            self._record_attack(source_ip, AttackType.RATE_LIMIT_VIOLATION.value, IntrusionSeverity.MEDIUM.value, now)
            return AttackDetectionResult(
                detected=True,
                attack_type=AttackType.RATE_LIMIT_VIOLATION.value,
                severity=IntrusionSeverity.MEDIUM.value,
                confidence=0.88,
                description=f"Rate limit exceeded: {len(recent)} requests in 60 seconds",
                source_ip=source_ip,
                evidence=f"{len(recent)} requests in rate limit window",
                action_taken=IntrusionAction.LOGGED.value,
            )

        return None

    def _record_attack(
        self,
        source_ip: str,
        attack_type: str,
        severity: str,
        timestamp: datetime,
    ) -> None:
        """记录攻击事件到历史"""
        self._attack_history.append(
            {
                "source_ip": source_ip,
                "attack_type": attack_type,
                "severity": severity,
                "timestamp": timestamp,
            }
        )

    def _cleanup_old_requests(self, source_ip: str, now: datetime) -> None:
        """清理过期的请求计数"""
        cutoff = now - timedelta(seconds=self._BRUTE_FORCE_WINDOW_SECONDS)
        self._request_counts[source_ip] = [t for t in self._request_counts[source_ip] if t > cutoff]
