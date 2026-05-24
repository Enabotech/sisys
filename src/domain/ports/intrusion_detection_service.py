"""领域层入侵检测服务端口模块

定义入侵检测服务的抽象接口，遵循六边形架构端口协议
用于等保2.0三级入侵防范合规

设计原则：
- detect_attack(): 检测攻击类型，返回检测结果
- get_intrusion_stats(): 获取入侵统计数据
- block_ip(): 封禁恶意 IP

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.value_objects.intrusion_detection_result import (
    AttackDetectionResult,
    IntrusionStats,
)


@runtime_checkable
class IntrusionDetectionServicePort(Protocol):
    """入侵检测服务抽象端口

    等保2.0三级入侵防范要求的核心服务端口，负责：
    - 10种攻击类型检测（SQL注入、XSS、暴力破解等）
    - 入侵统计数据汇总
    - IP封禁管理

    实现类必须遵循此接口契约，确保端口的可替换性
    """

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
            request_data: 请求内容（含可能攻击特征）
            request_path: 请求路径（可选）
            user_id: 用户标识（可选）

        Returns:
            AttackDetectionResult 包含检测结果、攻击类型、严重级别等
        """
        ...

    async def get_intrusion_stats(
        self,
        period_hours: int = 24,
    ) -> IntrusionStats:
        """获取入侵检测统计数据

        Args:
            period_hours: 统计周期（小时）

        Returns:
            IntrusionStats 包含攻击总数、按类型/严重级别统计、封禁 IP 列表
        """
        ...

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
        ...
