"""DataResidencyEnforcerImpl — Implementation of data residency enforcement service.

遵循六边形架构：服务实现，位于基础设施层。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.domain.entities.data_residency_policy import DataResidencyPolicy
from src.domain.ports.data_residency_enforcer import DataResidencyEnforcerPort

if TYPE_CHECKING:
    pass


class DataResidencyEnforcerImpl(DataResidencyEnforcerPort):
    """数据驻留强制执行服务实现.

    负责检查数据是否在合规的区域处理，触发违规事件。
    """

    def enforce_residency(self, data: Any, target_region: str, policy: DataResidencyPolicy) -> bool:
        """强制数据在指定区域驻留。

        Args:
            data: 待处理数据
            target_region: 目标区域
            policy: 数据驻留策略

        Returns:
            True 如果执行成功（符合策略），False 如果违反策略
        """
        # 检查目标区域是否被阻止
        if policy.is_blocked_region(target_region):
            return False

        # 检查目标区域是否在允许列表中
        if policy.is_allowed_region(target_region):
            return True

        # 非明确允许的区域，根据强制级别判断
        if policy.enforcement_level.value == "strict":
            return False

        return True

    def check_violation(self, target_region: str, policy: DataResidencyPolicy) -> bool:
        """检查是否存在数据驻留违规。

        Args:
            target_region: 目标区域
            policy: 数据驻留策略

        Returns:
            True 如果存在违规
        """
        # STRICT 级别禁止任何非允许区域的处理
        if policy.enforcement_level.value == "strict":
            if not policy.is_allowed_region(target_region):
                return True

        # MODERATE 和 PERMISSIVE 级别只在明确被阻止时违规
        if policy.is_blocked_region(target_region):
            return True

        return False
