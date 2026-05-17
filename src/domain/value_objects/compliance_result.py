"""领域层合规检查结果值对象模块

封装合规检查的结果，作为不可变值对象在领域层传递
遵循六边形架构：值对象，仅包含业务逻辑，无外部依赖

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComplianceResult:
    """合规检查结果值对象（不可变）.

    Attributes:
        allowed: 是否允许操作
        reason: 原因描述
        forced_local: 是否强制本地处理
        violation_type: 违规类型（如果有）
    """

    allowed: bool = True
    reason: str = ""
    forced_local: bool = False
    violation_type: str | None = None

    def is_allowed(self) -> bool:
        """检查操作是否被允许

        Returns:
            True 如果 allowed 为 True
        """
        return self.allowed

    def is_violation(self) -> bool:
        """检查是否存在违规

        Returns:
            True 如果 violation_type 不为 None
        """
        return self.violation_type is not None

    def get_violation_type(self) -> str | None:
        """获取违规类型

        Returns:
            violation_type 值或 None
        """
        return self.violation_type
