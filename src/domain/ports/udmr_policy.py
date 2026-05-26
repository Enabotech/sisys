"""领域层 UDMR 策略端口模块

遵循六边形架构：端口接口定义，仅依赖 Protocol 和 Python 标准库
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from src.domain.value_objects.compliance_result import ComplianceResult
from src.domain.value_objects.udmr_task import UDMRTask


@runtime_checkable
class UdmrPolicyPort(Protocol):
    """UDMR 策略抽象端口（协议接口）.

    MVP 阶段实现静态路由策略（云端优先 + 本地回退）
    """

    async def route(
        self,
        task: UDMRTask,
        compliance_result: ComplianceResult,
    ) -> tuple[
        Literal["local", "cloud"],
        str,
        Literal["timeout", "unavailable", "health_check_failed"] | None,
    ]:
        """执行路由决策

        Args:
            task: UDMR 路由任务
            compliance_result: L1 合规检查结果

        Returns:
            tuple[str, str, str | None]: (route_type, selected_model, fallback_reason)
            - route_type: "local" | "cloud"
            - selected_model: 具体模型名称
            - fallback_reason: "timeout" | "unavailable" | "health_check_failed" | None
        """
