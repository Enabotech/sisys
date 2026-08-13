"""应用层缓存指标端口模块

定义缓存指标采集的 Protocol 接口，由基础设施层实现。
SemanticCacheMiddleware 通过此端口注入指标采集，避免直接依赖基础设施层 EventMetricsCollector。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CacheMetricsPort(Protocol):
    """缓存指标采集端口

    应用层协议，用于缓存命中/未命中计数、延迟记录和命中率计算。
    由 EventMetricsCollector 或测试 Mock 实现。
    """

    def record_cache_hit(self) -> None:
        """记录缓存命中"""
        ...

    def record_cache_miss(self) -> None:
        """记录缓存未命中"""
        ...

    @property
    def hit_rate(self) -> float:
        """缓存命中率 (0.0~1.0)

        Returns:
            命中率，当总请求数为 0 时返回 0.0
        """
        ...

    @property
    def cache_hits_total(self) -> int:
        """缓存命中总次数"""
        ...

    @property
    def cache_misses_total(self) -> int:
        """缓存未命中总次数"""
        ...
