"""ComplianceGatewayImpl — Implementation of compliance gateway service.

遵循六边形架构：服务实现，位于基础设施层。

UDMR L1 合规性网关，协调各子服务进行综合合规检查。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from src.domain.ports.compliance_gateway import ComplianceGatewayPort
from src.domain.value_objects.compliance_result import ComplianceResult
from src.domain.value_objects.task import UDMRTask

if TYPE_CHECKING:
    from src.domain.ports.cross_border_transfer_service import CrossBorderTransferServicePort
    from src.domain.ports.data_residency_enforcer import DataResidencyEnforcerPort
    from src.domain.ports.pipl_compliance_service import PIPLComplianceServicePort
    from src.domain.ports.sensitive_data_detector import SensitiveDataDetectorPort
    from src.domain.ports.whitelist_service import WhitelistServicePort


class ComplianceGatewayImpl(ComplianceGatewayPort):
    """UDMR L1 合规性网关实现.

    协调敏感数据检测、数据驻留强制、白名单验证、PIPL合规和跨境传输审批。
    """

    def __init__(
        self,
        sensitive_data_detector: SensitiveDataDetectorPort | None = None,
        data_residency_enforcer: DataResidencyEnforcerPort | None = None,
        whitelist_service: WhitelistServicePort | None = None,
        pipl_service: PIPLComplianceServicePort | None = None,
        cross_border_service: CrossBorderTransferServicePort | None = None,
    ) -> None:
        """初始化合规性网关.

        Args:
            sensitive_data_detector: 敏感数据检测服务
            data_residency_enforcer: 数据驻留强制服务
            whitelist_service: 白名单服务
            pipl_service: PIPL合规服务
            cross_border_service: 跨境传输服务
        """
        self._sensitive_data_detector = sensitive_data_detector
        self._data_residency_enforcer = data_residency_enforcer
        self._whitelist_service = whitelist_service
        self._pipl_service = pipl_service
        self._cross_border_service = cross_border_service

    async def check(self, task: UDMRTask) -> ComplianceResult:
        """执行合规性检查。

        综合检查敏感数据、数据驻留、白名单、PIPL合规和跨境传输。

        Args:
            task: UDMR 路由任务

        Returns:
            ComplianceResult 合规检查结果
        """
        if task.data_residency == "CHINA_DOMESTIC":
            if task.preferred_model and task.allowed_models:
                if task.preferred_model not in task.allowed_models:
                    return ComplianceResult(
                        allowed=False,
                        reason=f"Model {task.preferred_model} not in whitelist",
                        forced_local=True,
                        violation_type="model_not_in_whitelist",
                    )

            if task.preferred_model:
                if self._is_overseas_model(task.preferred_model):
                    return ComplianceResult(
                        allowed=True,
                        reason=f"Model {task.preferred_model} violates data residency requirement, forced local processing",
                        forced_local=True,
                        violation_type="data_residency_violation",
                    )

            if self._sensitive_data_detector:
                from src.domain.entities.sensitive_data_result import SensitiveDataResult

                detection_result = self._sensitive_data_detector.detect_sensitive_data(task.input)
                if isinstance(detection_result, SensitiveDataResult):
                    if len(detection_result.sensitive_types) > 0:
                        if task.data_residency == "CHINA_DOMESTIC":
                            return ComplianceResult(
                                allowed=True,
                                reason="Sensitive data detected, forced local processing",
                                forced_local=True,
                                violation_type=None,
                            )

            if self._pipl_service:
                if self._contains_personal_data(task.input):
                    return ComplianceResult(
                        allowed=True,
                        reason="Personal data detected, requires PIPL compliance",
                        forced_local=True,
                        violation_type=None,
                    )

        if task.data_residency == "OVERSEAS":
            if self._cross_border_service:
                pending = self._cross_border_service.list_pending_requests()
                if pending:
                    return ComplianceResult(
                        allowed=True,
                        reason="Cross-border transfer pending approval",
                        forced_local=False,
                        violation_type=None,
                    )
                return ComplianceResult(
                    allowed=True,
                    reason="Cross-border transfer not required for this request",
                    forced_local=False,
                    violation_type=None,
                )

        if task.preferred_model and task.allowed_models:
            if task.preferred_model not in task.allowed_models:
                return ComplianceResult(
                    allowed=False,
                    reason=f"Model {task.preferred_model} not in whitelist",
                    forced_local=False,
                    violation_type="model_not_in_whitelist",
                )

        return ComplianceResult(
            allowed=True,
            reason="Compliant",
            forced_local=False,
            violation_type=None,
        )

    def _is_overseas_model(self, model: str) -> bool:
        """检查是否为海外模型。

        Args:
            model: 模型标识

        Returns:
            True 如果是海外模型
        """
        overseas_prefixes = (
            "openai/",
            "anthropic/",
            "google/",
            "meta/",
            "amazon/",
            "cohere/",
            "ai21/",
            "mistral/",
        )
        return model.startswith(overseas_prefixes)

    def _contains_personal_data(self, text: str) -> bool:
        """检查文本是否包含个人信息。

        Args:
            text: 待检测文本

        Returns:
            True 如果包含个人信息
        """
        patterns = [
            r"身份证[\s:：]*\d{15}|\d{18}",
            r"手机[号\s:：]*1\d{10}",
            r"姓名[\s:：]*[\u4e00-\u9fa5]{2,4}",
            r"地址[\s:：]*[\u4e00-\u9fa5]+",
            r"邮箱[\s:：]*[\w.-]+@[\w.-]+\.\w+",
        ]

        for pattern in patterns:
            if re.search(pattern, text):
                return True
        return False
