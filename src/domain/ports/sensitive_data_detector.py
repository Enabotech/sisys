"""领域层敏感数据检测端口模块

定义敏感数据检测服务的端口接口，遵循六边形架构：仅依赖 Protocol 和 Python 标准库

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.entities.sensitive_data_result import SensitiveDataResult


@runtime_checkable
class SensitiveDataDetectorPort(Protocol):
    """敏感数据检测服务端口（协议接口）."""

    def detect_sensitive_data(self, content: str) -> SensitiveDataResult:
        """检测敏感数据

        Args:
            content: 待检测内容

        Returns:
            SensitiveDataResult 包含检测结果
        """
