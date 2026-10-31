"""基础设施层指标端点配置模块

提供 Prometheus /metrics HTTP 端点配置，支持 K8s 动态扩缩容；
metrics 端口注册工厂（build_metrics_port——组合根装配用，Epic 5 终局审查修复）
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from src.infrastructure.monitoring.metrics_port_impl import MetricsPortImpl


@dataclass
class MetricsConfig:
    """Prometheus /metrics 端点配置

    从环境变量读取，支持启用/禁用、路径配置、认证配置

    Attributes:
        enabled: 是否启用 /metrics 端点（默认 false）
        path: 指标端点路径（默认 "/metrics"）
        auth_enabled: 是否启用 Basic Auth 认证（默认 false）
        port: 指标端点端口（默认 8080，与主应用共用）
    """

    enabled: bool = False
    path: str = "/metrics"
    auth_enabled: bool = False
    port: int = 8080

    @classmethod
    def from_env(cls) -> MetricsConfig:
        """从环境变量创建配置

        Args:
            无（从 os.environ 读取）

        Returns:
            MetricsConfig 实例
        """
        enabled = os.getenv("METRICS_ENABLED", "false").lower() in ("true", "1", "yes")
        path = os.getenv("METRICS_PATH", "/metrics")
        auth_enabled = os.getenv("METRICS_AUTH_ENABLED", "false").lower() in ("true", "1", "yes")

        port_str = os.getenv("METRICS_PORT", "8080")
        try:
            port = int(port_str)
        except (ValueError, TypeError):
            port = 8080

        return cls(
            enabled=enabled,
            path=path,
            auth_enabled=auth_enabled,
            port=port,
        )


_metrics_port_instance: MetricsPortImpl | None = None


def build_metrics_port(resolver: Any) -> MetricsPortImpl:
    """metrics 端口注册工厂（Epic 5 终局审查修复——原组合根字符串 impl 指向不存在的 metrics_adapter 模块）。

    进程级单例复用（R2 修复）：BusinessMetricsCollector 构造器即向 Prometheus
    默认 REGISTRY 注册 sisys_* 指标——二次构造必抛 Duplicated timeseries，而
    resolver 的 SINGLETON 缓存可被测试纪律 clear_singleton() 驱逐（5.x 验收
    场景级重建），驱逐后裸 resolve 重建会在全局 REGISTRY 上必炸。Prometheus
    全局注册表是进程级资源，不应随 resolver 缓存丢弃——本工厂以模块级实例
    缓存对齐两生命周期：clear 后重建返回同一实例，重建幂等。

    激活语义诚实注记（R2②-F2）：本修复恢复的是「订阅注册」（bootstrap 激活环
    resolve cost_metrics_handler 成功 → async register() → RedisEventSubscriber
    纯内存 dict 注册 RoutingDecided，零外部依赖）；「消费循环」全仓零调用点
    （DualChannelEventBus.start / RedisEventBus.start 无人拉起 listen loop），
    on_routing_decided 回调在测试与生产均无触发路径——消费面接线归 Epic 6
    首个事件消费 Story（与 R1-DF2 同锚）。

    历史注记：幽灵 impl 字符串源自 19fbf461（2026-05-12 组合根重构期脚手架），
    d49261b0（2026-10-12 UDMR 审计修复 F2）将 cost_metrics_handler 加入
    handler_names 激活清单后缺陷活化——每次 bootstrap resolve 失败被静默吞为
    warning（1-19 成本追踪「激活」从未生效）。

    本模块归宿注记（用户裁定 2026-10-31：组合根零私有函数纪律——工厂迁至
    infrastructure/config/，组合根仅装配）。

    Args:
        resolver: 端口解析器（resolver._instantiate 以 spec.impl(resolver=self)
            约定调用——零参签名会 TypeError 且被 bootstrap except 吞掉）。

    Returns:
        组合完成的 MetricsPort 进程级单例（15 方法全实现，含
        cost_metrics_handler 消费的 record_token_usage / record_cost）。
    """
    global _metrics_port_instance

    from src.infrastructure.monitoring.aggregator import MetricsAggregator
    from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector
    from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

    if _metrics_port_instance is not None:
        return _metrics_port_instance

    business = BusinessMetricsCollector()
    _metrics_port_instance = MetricsPortImpl(
        aggregator=MetricsAggregator(
            event_metrics_collector=EventMetricsCollector(),
            business_metrics_collector=business,
        ),
        business_metrics=business,
    )
    return _metrics_port_instance
