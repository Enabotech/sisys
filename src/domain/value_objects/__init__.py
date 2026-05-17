"""领域层值对象模块

领域值对象是领域模型中的不可变对象，通过值而非标识来衡量
本模块聚合所有值对象定义，统一对外导出

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from src.domain.value_objects.auto_trigger_context import AutoTriggerContext
from src.domain.value_objects.compliance_result import ComplianceResult
from src.domain.value_objects.token_payload import TokenPayload
from src.domain.value_objects.udmr_task import UDMRTask

__all__ = [
    "AutoTriggerContext",
    "ComplianceResult",
    "UDMRTask",
    "TokenPayload",
]
