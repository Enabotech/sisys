"""HealthCheckerFactory — Domain 层工厂接口。

定义创建 HealthCheckPort 的工厂接口。
Application 层通过此接口创建健康检查 Adapter，不直接引用 Infrastructure 层具体类。

六边形约束：
- Domain 层定义接口（零外部依赖）
- Infrastructure 层实现接口
- Application 层只依赖 Domain 接口
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.ports.health_check import HealthCheckPort


class HealthCheckerFactory(ABC):
    """HealthCheckPort 创建工厂接口。

    Application 层通过此接口获取 HealthCheckPort 实例，
    具体实现由 Infrastructure 层提供。
    """

    @abstractmethod
    def create(self) -> HealthCheckPort:
        """创建 HealthCheckPort 实例。

        Returns:
            HealthCheckPort 实现实例。
        """
        pass
