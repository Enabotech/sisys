"""MetricsPort — 应用层端口定义。

六边形架构：应用层定义端口，基础设施层实现端口。
接口层通过此端口获取指标，不能直接导入 infrastructure。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class MetricsPort(ABC):
    """Metrics 采集端口定义。

    应用层定义此端口，基础设施层实现。
    接口层通过此接口获取 Prometheus 指标。
    """

    @abstractmethod
    def collect(self) -> bytes:
        """收集所有指标。

        Returns:
            Prometheus 文本格式的指标字节串
        """
        ...

    @abstractmethod
    def collect_as_dict(self) -> dict[str, float | int]:
        """收集所有指标并返回字典格式。

        Returns:
            指标名称到指标值的字典
        """
        ...

    @abstractmethod
    def record_sessions(self, n: int) -> None:
        """记录活跃 Agent 会话数。

        Args:
            n: 当前活跃会话数
        """
        ...

    @abstractmethod
    def record_queue_length(self, n: int) -> None:
        """记录任务队列长度。

        Args:
            n: 任务队列长度
        """
        ...

    @abstractmethod
    def record_cache_hit(self) -> None:
        """记录缓存命中"""
        ...

    @abstractmethod
    def record_cache_miss(self) -> None:
        """记录缓存未命中"""
        ...

    @abstractmethod
    def record_event_processed(self) -> None:
        """记录一个事件已处理"""
        ...

    @abstractmethod
    def update_processing_rate(self) -> None:
        """更新事件处理速率"""
        ...

    @abstractmethod
    def get_hit_rate(self) -> float:
        """获取当前缓存命中率。

        Returns:
            命中率（0.0-1.0）
        """
        ...

    @abstractmethod
    def get_sessions(self) -> int:
        """获取当前活跃会话数"""
        ...

    @abstractmethod
    def get_queue_length(self) -> int:
        """获取当前任务队列长度"""
        ...

    @abstractmethod
    def get_processing_rate(self) -> float:
        """获取当前事件处理速率"""
        ...
