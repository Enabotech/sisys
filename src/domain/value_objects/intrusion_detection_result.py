"""领域层入侵检测结果值对象

定义入侵检测服务返回的结果类型，用于等保2.0三级入侵防范
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AttackDetectionResult:
    """攻击检测结果

    Attributes:
        detected: 是否检测到攻击
        attack_type: 攻击类型（AttackType 枚举值）
        severity: 严重级别（IntrusionSeverity 枚举值）
        confidence: 检测置信度（0.0-1.0）
        description: 描述信息
        source_ip: 攻击来源 IP
        evidence: 原始证据数据
        action_taken: 响应动作（IntrusionAction 枚举值）
    """

    detected: bool = False
    attack_type: str = ""
    severity: str = "low"
    confidence: float = 0.0
    description: str = ""
    source_ip: str = ""
    evidence: str = ""
    action_taken: str = "logged"


@dataclass(frozen=True)
class IntrusionStats:
    """入侵检测统计数据

    Attributes:
        total_attacks: 攻击总数
        attacks_by_type: 按攻击类型统计
        attacks_by_severity: 按严重级别统计
        blocked_ips: 已封禁 IP 列表
    """

    total_attacks: int = 0
    attacks_by_type: dict[str, int] = field(default_factory=dict)
    attacks_by_severity: dict[str, int] = field(default_factory=dict)
    blocked_ips: list[str] = field(default_factory=list)
