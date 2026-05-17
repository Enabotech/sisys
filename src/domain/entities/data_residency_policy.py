"""领域层数据驻留策略实体模块

定义数据驻留策略领域实体，遵循六边形架构：领域层零依赖

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class Region(str, Enum):
    """Data residency regions."""

    CHINA_DOMESTIC = "CHINA_DOMESTIC"
    CHINA_HKMO = "CHINA_HKMO"
    OVERSEAS = "OVERSEAS"


class EnforcementLevel(str, Enum):
    """Data residency enforcement levels."""

    STRICT = "strict"
    MODERATE = "moderate"
    PERMISSIVE = "permissive"


@dataclass(frozen=True)
class DataResidencyPolicy:
    """数据驻留策略领域实体（不可变）.

    Attributes:
        policy_id: 唯一标识符
        name: 策略名称
        allowed_regions: 允许的数据驻留区域列表
        blocked_regions: 禁止的数据驻留区域列表
        enforcement_level: 强制级别
    """

    policy_id: UUID = field(default_factory=uuid4)
    name: str = ""
    allowed_regions: tuple[str, ...] = field(default_factory=lambda: (Region.CHINA_DOMESTIC.value,))
    blocked_regions: tuple[str, ...] = field(default_factory=lambda: (Region.OVERSEAS.value,))
    enforcement_level: EnforcementLevel = EnforcementLevel.STRICT

    def is_allowed_region(self, region: str) -> bool:
        """检查指定区域是否在允许列表中

        Args:
            region: 区域代码

        Returns:
            True 如果区域在允许列表中
        """
        return region in self.allowed_regions

    def is_blocked_region(self, region: str) -> bool:
        """检查指定区域是否在禁止列表中

        Args:
            region: 区域代码

        Returns:
            True 如果区域在禁止列表中
        """
        return region in self.blocked_regions

    def requires_local_processing(self) -> bool:
        """检查是否强制本地处理

        Returns:
            True 如果 enforcement_level 为 STRICT
        """
        return self.enforcement_level == EnforcementLevel.STRICT

    def get_policy_context(self) -> dict[str, Any]:
        """获取策略上下文，用于 UDMR 路由决策

        Returns:
            dict 包含策略上下文信息
        """
        return {
            "policy_id": str(self.policy_id),
            "name": self.name,
            "allowed_regions": list(self.allowed_regions),
            "blocked_regions": list(self.blocked_regions),
            "enforcement_level": self.enforcement_level.value,
            "local_only": self.requires_local_processing(),
        }
