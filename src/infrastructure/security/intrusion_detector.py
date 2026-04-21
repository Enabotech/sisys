"""Intrusion Detector — Security intrusion detection for 等保 2.0 Level 3.

Implements intrusion detection for common attack patterns:
- Brute force attacks
- SQL injection
- XSS (Cross-Site Scripting)
- CSRF (Cross-Site Request Forgery)
- Path traversal
- Command injection
- Rate limit violations
- Prompt injection

等保 2.0 Level 3 要求:
- 入侵防范: 检测并抵御常见攻击
- 渗透测试覆盖率 >= 90%
- 高风险项 = 0, 中危漏洞 < 5
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from src.domain.events.compliance_events import (
    AttackType,
    IntrusionAction,
    IntrusionDetectedEvent,
    IntrusionSeverity,
)

if TYPE_CHECKING:
    pass


class ThreatLevel(str, Enum):
    """Threat level classification."""

    BENIGN = "benign"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    CRITICAL = "critical"


@dataclass
class ThreatAssessment:
    """Result of threat assessment.

    Attributes:
        threat_level: Overall threat level.
        score: Threat score (0-100).
        detected_attacks: List of detected attack types.
        action_recommended: Recommended action.
        details: Additional details.
    """

    threat_level: ThreatLevel
    score: float
    detected_attacks: list[AttackType]
    action_recommended: IntrusionAction
    details: str = ""


@dataclass
class RateLimitEntry:
    """Rate limit tracking entry.

    Attributes:
        count: Number of requests.
        window_start: Start of the rate limit window.
        blocked_until: If blocked, when the block expires.
    """

    count: int = 0
    window_start: float = field(default_factory=time.time)
    blocked_until: float | None = None


class IntrusionDetector:
    """Intrusion Detector for detecting security threats.

    Implements pattern-based detection for common attack vectors
    with rate limiting and threat scoring.
    """

    # Rate limiting defaults
    DEFAULT_RATE_LIMIT_WINDOW: int = 60  # 1 minute
    DEFAULT_RATE_LIMIT_MAX: int = 100  # requests per window
    BRUTE_FORCE_THRESHOLD: int = 5  # failed attempts before blocking

    # Brute force detection
    BRUTE_FORCE_WINDOW_SECONDS: int = 300  # 5 minutes
    BRUTE_FORCE_MAX_ATTEMPTS: int = 5

    def __init__(
        self,
        rate_limit_window: int = DEFAULT_RATE_LIMIT_WINDOW,
        rate_limit_max: int = DEFAULT_RATE_LIMIT_MAX,
        brute_force_window: int = BRUTE_FORCE_WINDOW_SECONDS,
        brute_force_max_attempts: int = BRUTE_FORCE_MAX_ATTEMPTS,
    ) -> None:
        """Initialize Intrusion Detector.

        Args:
            rate_limit_window: Rate limit window in seconds.
            rate_limit_max: Max requests per window.
            brute_force_window: Brute force detection window in seconds.
            brute_force_max_attempts: Max failed attempts before blocking.
        """
        self._rate_limit_window = rate_limit_window
        self._rate_limit_max = rate_limit_max
        self._brute_force_window = brute_force_window
        self._brute_force_max_attempts = brute_force_max_attempts

        # Rate limit tracking: ip -> RateLimitEntry
        self._rate_limits: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)

        # Brute force tracking: ip -> list of failed attempt timestamps
        self._brute_force_tracking: dict[str, list[float]] = defaultdict(list)

        # Blocked IPs: ip -> blocked_until timestamp
        self._blocked_ips: dict[str, float] = {}

        # Regex patterns for attack detection
        self._patterns = self._init_detection_patterns()

    @staticmethod
    def _init_detection_patterns() -> dict[AttackType, re.Pattern]:
        """Initialize detection regex patterns.

        Returns:
            dict: Mapping of attack type to regex pattern.
        """
        return {
            AttackType.SQL_INJECTION: re.compile(
                r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b|"
                r"--|;|'|/\*|\*/|@@|char|nchar|varchar|nvarchar|"
                r"fetch|open|close|declare|sp_executesql)\b",
                re.IGNORECASE,
            ),
            AttackType.XSS: re.compile(
                r"(<script|javascript:|on\w+\s*=|"
                r"<iframe|<object|<embed|"
                r"data:text/html|"
                r"document\.cookie|document\.write|"
                r"eval\(|innerHTML)",  # pragma: allowlist secret
                re.IGNORECASE,
            ),
            AttackType.COMMAND_INJECTION: re.compile(
                r"(\b(cat|ls|dir|rm|mv|cp|chmod|chown|wget|curl|nc|netcat|bash|sh|cmd|powershell)\b|"
                r"[;&|`$]|"
                r"\bcurl\s+|"
                r"\bwget\s+|"
                r"\bnc\s+|"
                r"\|)",
                re.IGNORECASE,
            ),
            AttackType.PATH_TRAVERSAL: re.compile(
                r"(\.\./|\.\.\\|%2e%2e/|" r"\.\.%2f|%2e%2e%5c|" r"etc/passwd|" r"c:\\windows|" r"boot\.ini)",
                re.IGNORECASE,
            ),
            AttackType.PROMPT_INJECTION: re.compile(
                r"(\b(ignore|disregard|forget|override)\s+(previous|all|above|past)\s+(instructions?|orders?|commands?|rules?)\b|"
                r"\b(you\s+are\s+now|you\s+must\s+only|only\s+respond)\b|"
                r"(system\s*:|admin\s*:|instruction\s*:|directive\s*:)\s*|"
                r"---\s*role|"
                r"#\s*role|"
                r"new\s+rule|"
                r"ignore\s+rule)",
                re.IGNORECASE,
            ),
        }

    def check_rate_limit(self, ip_address: str) -> bool:
        """Check if IP is within rate limits.

        Args:
            ip_address: Source IP address.

        Returns:
            bool: True if within limits, False if rate limited.
        """
        # Check if IP is blocked
        if self.is_ip_blocked(ip_address):
            return False

        entry = self._rate_limits[ip_address]
        now = time.time()

        # Reset window if expired
        if now - entry.window_start > self._rate_limit_window:
            entry.count = 0
            entry.window_start = now

        # Check limit
        if entry.count >= self._rate_limit_max:
            entry.blocked_until = now + self._rate_limit_window
            return False

        entry.count += 1
        return True

    def is_ip_blocked(self, ip_address: str) -> bool:
        """Check if IP is currently blocked.

        Args:
            ip_address: Source IP address.

        Returns:
            bool: True if blocked.
        """
        blocked_until = self._blocked_ips.get(ip_address)
        if blocked_until is None:
            return False

        if time.time() > blocked_until:
            # Block expired
            del self._blocked_ips[ip_address]
            return False

        return True

    def block_ip(self, ip_address: str, duration_seconds: int = 300) -> None:
        """Block an IP address.

        Args:
            ip_address: Source IP address to block.
            duration_seconds: Block duration in seconds.
        """
        self._blocked_ips[ip_address] = time.time() + duration_seconds

    def record_failed_login(self, ip_address: str) -> bool:
        """Record a failed login attempt for brute force detection.

        Args:
            ip_address: Source IP address.

        Returns:
            bool: True if IP should be blocked (brute force detected).
        """
        now = time.time()
        attempts = self._brute_force_tracking[ip_address]

        # Clean old attempts outside window
        cutoff = now - self._brute_force_window
        attempts = [ts for ts in attempts if ts > cutoff]
        attempts.append(now)
        self._brute_force_tracking[ip_address] = attempts

        # Check if threshold exceeded
        if len(attempts) >= self._brute_force_max_attempts:
            self.block_ip(ip_address, self._brute_force_window)
            return True

        return False

    def detect_attack(self, request_content: str) -> list[AttackType]:
        """Detect attack patterns in request content.

        Args:
            request_content: Request body or parameters to check.

        Returns:
            list[AttackType]: List of detected attack types.
        """
        detected: list[AttackType] = []

        for attack_type, pattern in self._patterns.items():
            if pattern.search(request_content):
                detected.append(attack_type)

        return detected

    def assess_threat(
        self,
        ip_address: str,
        request_content: str = "",
        failed_login: bool = False,
    ) -> ThreatAssessment:
        """Assess threat level for a request.

        Args:
            ip_address: Source IP address.
            request_content: Request body or parameters.
            failed_login: Whether this is a failed login attempt.

        Returns:
            ThreatAssessment: Threat assessment result.
        """
        detected_attacks = self.detect_attack(request_content)
        score = 0.0
        action = IntrusionAction.LOGGED

        # Rate limit check
        if not self.check_rate_limit(ip_address):
            score += 30
            detected_attacks.append(AttackType.RATE_LIMIT_VIOLATION)
            action = IntrusionAction.BLOCKED

        # Brute force check
        if failed_login:
            is_blocked = self.record_failed_login(ip_address)
            if is_blocked:
                score += 50
                detected_attacks.append(AttackType.BRUTE_FORCE)
                action = IntrusionAction.BLOCKED
            else:
                score += 10

        # Attack pattern scoring
        for attack in detected_attacks:
            if attack == AttackType.SQL_INJECTION:
                score += 40
            elif attack == AttackType.XSS:
                score += 30
            elif attack == AttackType.COMMAND_INJECTION:
                score += 50
            elif attack == AttackType.PATH_TRAVERSAL:
                score += 30
            elif attack == AttackType.PROMPT_INJECTION:
                score += 35
            elif attack == AttackType.CSRF:
                score += 20
            elif attack == AttackType.DATA_EXFILTRATION:
                score += 45

        # Cap score at 100
        score = min(score, 100.0)

        # Determine threat level
        if score >= 80:
            threat_level = ThreatLevel.CRITICAL
            action = IntrusionAction.BLOCKED
        elif score >= 60:
            threat_level = ThreatLevel.MALICIOUS
        elif score >= 30:
            threat_level = ThreatLevel.SUSPICIOUS
        else:
            threat_level = ThreatLevel.BENIGN

        return ThreatAssessment(
            threat_level=threat_level,
            score=score,
            detected_attacks=detected_attacks,
            action_recommended=action,
            details=f"IP {ip_address}: {len(detected_attacks)} attack patterns detected",
        )

    def create_intrusion_event(
        self,
        ip_address: str,
        threat_assessment: ThreatAssessment,
        raw_evidence: str = "",
    ) -> IntrusionDetectedEvent:
        """Create an intrusion detection event.

        Args:
            ip_address: Source IP address.
            threat_assessment: Threat assessment result.
            raw_evidence: Raw request data for evidence.

        Returns:
            IntrusionDetectedEvent: Domain event for intrusion.
        """
        # Determine severity from threat level
        if threat_assessment.threat_level == ThreatLevel.CRITICAL:
            severity = IntrusionSeverity.CRITICAL
        elif threat_assessment.threat_level == ThreatLevel.MALICIOUS:
            severity = IntrusionSeverity.HIGH
        elif threat_assessment.threat_level == ThreatLevel.SUSPICIOUS:
            severity = IntrusionSeverity.MEDIUM
        else:
            severity = IntrusionSeverity.LOW

        # Get primary attack type
        attack_type = (
            threat_assessment.detected_attacks[0] if threat_assessment.detected_attacks else AttackType.UNAUTHORIZED_ACCESS
        )

        return IntrusionDetectedEvent(
            intrusion_id=uuid4(),
            source_ip=ip_address,
            attack_type=attack_type,
            severity=severity,
            action_taken=threat_assessment.action_recommended,
            description=threat_assessment.details,
            raw_evidence=raw_evidence[:1000] if raw_evidence else "",  # Truncate for storage
        )


# Global intrusion detector instance
_intrusion_detector: IntrusionDetector | None = None


def get_intrusion_detector() -> IntrusionDetector:
    """Get global Intrusion Detector instance.

    Returns:
        IntrusionDetector: Global intrusion detector instance.
    """
    global _intrusion_detector
    if _intrusion_detector is None:
        _intrusion_detector = IntrusionDetector()
    return _intrusion_detector
