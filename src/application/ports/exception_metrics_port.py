"""SISYS 应用层异常指标端口模块。

六边形架构：应用层定义端口，基础设施层实现端口。
接口层通过此端口记录异常指标，不能直接导入 infrastructure。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Protocol


class ExceptionMetricsPort(Protocol):
    """异常指标采集端口定义.

    应用层定义此端口，基础设施层实现。
    接口层通过此接口记录异常指标。
    """

    def record_exception(self, exception_type: str, code: str | None = None) -> None:
        """记录异常发生。

        Args:
            exception_type: 异常类型名称（如 "ValidationError"）
            code: 可选的错误码
        """
