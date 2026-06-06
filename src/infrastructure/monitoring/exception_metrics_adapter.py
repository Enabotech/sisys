"""基础设施层异常指标适配器模块

适配 ExceptionMetricsImpl 为 ExceptionMetricsPort，注册于 composition_root。
遵循 R3（基础设施层实现应用层端口），委托给同层 ExceptionMetricsImpl。
"""

from __future__ import annotations

from src.application.ports.exception_metrics_port import ExceptionMetricsPort
from src.infrastructure.logging.exception_metrics_impl import ExceptionMetricsImpl


class ExceptionMetricsAdapter(ExceptionMetricsPort):
    """异常指标适配器，委托给 ExceptionMetricsImpl

    作为 composition_root 中注册的端口实现，将异常指标采集
    委托给同层 ExceptionMetricsImpl（线程安全计数器 + Prometheus 导出）。

    Attributes:
        _impl: 实际的异常指标收集器实例
    """

    def __init__(self) -> None:
        """初始化适配器，创建内部 ExceptionMetricsImpl 实例"""
        self._impl = ExceptionMetricsImpl()

    def record_exception(self, exception_type: str, code: str | None = None) -> None:
        """记录异常发生

        Args:
            exception_type: 异常类型名称
            code: 可选的错误码
        """
        self._impl.record_exception(exception_type, code)
