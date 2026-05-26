"""领域层合规性网关端口模块

遵循六边形架构：端口接口定义，仅依赖 Protocol 和 Python 标准库
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.value_objects.compliance_result import ComplianceResult
from src.domain.value_objects.udmr_task import UDMRTask


@runtime_checkable
class ComplianceGatewayPort(Protocol):
    """合规性网关端口（协议接口）.

    UDMR L1 合规性网关，负责在路由决策前进行合规检查
    """

    async def check(self, task: UDMRTask) -> ComplianceResult:
        """执行合规性检查

        Args:
            task: UDMR 路由任务

        Returns:
            ComplianceResult 合规检查结果
        """
