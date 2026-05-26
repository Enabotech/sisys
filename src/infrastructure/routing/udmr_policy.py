"""基础设施层 UDMR 静态路由策略模块

云端优先静态路由策略：合规通过时选择云端，合规不通过或云端不可用时回退本地
"""

from __future__ import annotations

import logging
from typing import Literal

from src.domain.value_objects.compliance_result import ComplianceResult
from src.domain.value_objects.udmr_task import UDMRTask
from src.infrastructure.config.udmr import CloudModelConfig

logger = logging.getLogger(__name__)


class StaticUdmrPolicy:
    """UDMR 静态路由策略（云端优先 + 本地回退）.

    实现领域端口 UdmrPolicyPort 的路由决策逻辑：
    1. L1 合规强制本地（forced_local=True）→ local
    2. local_first=True → local
    3. 云端优先（第一个 enabled 的云端模型）
    4. 云端不可用 → local + fallback_reason="unavailable"
    """

    def __init__(
        self,
        cloud_configs: list[CloudModelConfig],
        local_model: str = "qwen2.5:7b",
        local_first: bool = False,
    ) -> None:
        self._cloud_configs = cloud_configs
        self._local_model = local_model
        self._local_first = local_first

    async def route(
        self,
        task: UDMRTask,
        compliance_result: ComplianceResult,
    ) -> tuple[
        Literal["local", "cloud"],
        str,
        Literal["timeout", "unavailable", "health_check_failed"] | None,
    ]:
        """执行静态路由决策.

        Args:
            task: UDMR 路由任务
            compliance_result: L1 合规检查结果

        Returns:
            (route_type, selected_model, fallback_reason)
        """
        # 1. L1 合规强制本地
        if compliance_result.forced_local:
            logger.debug("L1 compliance forced local routing")
            return "local", self._local_model, None

        # 2. local_first 模式
        if self._local_first:
            logger.debug("local_first mode, routing to local")
            return "local", self._local_model, None

        # 3. 云端优先：选择第一个 enabled 的云端模型
        for cloud in self._cloud_configs:
            if cloud.enabled:
                logger.debug("Cloud-first routing to %s", cloud.model)
                return "cloud", cloud.model, None

        # 4. 云端不可用 → 回退本地
        logger.debug("No enabled cloud models, falling back to local")
        return "local", self._local_model, "unavailable"
