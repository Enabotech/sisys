"""LocalModelHealthFacade — 应用层入口，多模型健康检查统一入口。

通过注入的 HealthCheckerFactory 创建具体 Adapter（Ollama/Gemini/vLLM），统一暴露给 UDMRouter。

架构来源: Story 1.17 六边形架构设计澄清（2026-05-07）

六边形约束遵守：
- 本类是应用层服务
- 依赖 Domain 层接口（HealthCheckerFactory, HealthCheckPort）
- 工厂由外部注入，不在内部创建 Infrastructure 具体类
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.ports.health_check import HealthCheckPort
    from src.domain.ports.health_check_factory import HealthCheckerFactory
    from src.infrastructure.config.udmr import UDMRConfig


class LocalModelHealthFacade:
    """应用层入口 — 多模型健康检查统一入口。

    职责：
    - 根据注入的 HealthCheckerFactory 创建具体 Adapter（Ollama/Gemini/vLLM）
    - 统一暴露 async check() / close() 接口
    - 隐藏具体 Adapter 创建细节

    设计原则：
    - 应用层编排，不包含业务逻辑
    - 依赖 Domain Port（HealthCheckPort, HealthCheckerFactory）
    - 工厂由外部注入（六边形正确姿势）
    """

    def __init__(
        self,
        factory: HealthCheckerFactory,
        config: UDMRConfig | None = None,
    ) -> None:
        """初始化 LocalModelHealthFacade。

        Args:
            factory: HealthCheckerFactory 实例，用于创建具体 Adapter。
            config: UDMRConfig 配置（可选，用于日志/追踪）。
        """
        self._factory = factory
        self._config = config
        self._adapter: HealthCheckPort | None = None

    @property
    def _health_checker(self) -> HealthCheckPort:
        """惰性加载 Adapter。"""
        if self._adapter is None:
            self._adapter = self._factory.create()
        return self._adapter

    async def check(self) -> bool:
        """执行健康检查。

        Returns:
            True 如果服务健康，False 否则。
        """
        return await self._health_checker.check()

    async def close(self) -> None:
        """关闭健康检查连接，释放资源。"""
        if self._adapter is not None:
            await self._adapter.close()
            self._adapter = None
