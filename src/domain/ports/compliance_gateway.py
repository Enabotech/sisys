"""ComplianceGatewayPort — Interface for compliance gateway service.

遵循六边形架构：端口接口定义，仅依赖 ABC 和 Python 标准库。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.value_objects.compliance_result import ComplianceResult
from src.domain.value_objects.task import UDMRTask


class ComplianceGatewayPort(ABC):
    """合规性网关端口（抽象接口）.

    UDMR L1 合规性网关，负责在路由决策前进行合规检查。
    """

    @abstractmethod
    async def check(self, task: UDMRTask) -> ComplianceResult:
        """执行合规性检查。

        Args:
            task: UDMR 路由任务

        Returns:
            ComplianceResult 合规检查结果
        """
        ...
