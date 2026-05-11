"""DataResidencyEnforcerPort — Interface for data residency enforcement service.

遵循六边形架构：端口接口定义，仅依赖 ABC 和 Python 标准库。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.domain.entities.data_residency_policy import DataResidencyPolicy


class DataResidencyEnforcerPort(ABC):
    """数据驻留强制执行服务端口（抽象接口）."""

    @abstractmethod
    def enforce_residency(self, data: Any, target_region: str, policy: DataResidencyPolicy) -> bool:
        """强制数据在指定区域驻留。

        Args:
            data: 待处理数据
            target_region: 目标区域
            policy: 数据驻留策略

        Returns:
            True 如果执行成功（符合策略）
        """
        ...

    @abstractmethod
    def check_violation(self, target_region: str, policy: DataResidencyPolicy) -> bool:
        """检查是否存在数据驻留违规。

        Args:
            target_region: 目标区域
            policy: 数据驻留策略

        Returns:
            True 如果存在违规
        """
        ...
