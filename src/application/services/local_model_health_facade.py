"""LocalModelHealthFacade — 应用层门面，多模型健康检查统一入口。

根据配置选择具体 Adapter（Ollama/Gemini/vLLM），统一暴露给 UDMRouter。

架构来源: Story 1.17 六边形架构设计澄清（2026-05-07）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.ports.health_check import HealthCheckPort
    from src.infrastructure.config.udmr import UDMRConfig


class LocalModelHealthFacade:
    """应用层门面 — 多模型健康检查统一入口。

    职责：
    - 根据配置选择具体 Adapter（Ollama/Gemini/vLLM）
    - 统一暴露 async check() / close() 接口
    - 隐藏具体实现细节

    设计原则：
    - 应用层编排，不包含业务逻辑
    - 依赖 Domain Port（HealthCheckPort）
    - 工厂模式：根据配置创建对应 Adapter
    """

    def __init__(self, config: UDMRConfig | None = None) -> None:
        """初始化 LocalModelHealthFacade。

        Args:
            config: UDMRConfig 配置，决定使用哪个 Adapter。
                   如果为 None，使用默认 OllamaHealthAdapter。
        """
        self._config = config
        self._adapter: HealthCheckPort | None = None

    def _create_adapter(self) -> HealthCheckPort:
        """根据配置创建对应的健康检查 Adapter。

        Returns:
            HealthCheckPort 实现实例。
        """
        # Import here to avoid circular dependency
        from src.infrastructure.routing.ollama_health_adapter import (
            OllamaHealthAdapter,
        )

        if self._config is not None and self._config.local_model:
            # Future: 可扩展为根据 model type 选择不同 Adapter
            # e.g., if self._config.local_model_type == "gemini": ...
            pass

        # Default: 使用 OllamaHealthAdapter
        return OllamaHealthAdapter()

    @property
    def _health_checker(self) -> HealthCheckPort:
        """惰性加载 Adapter。"""
        if self._adapter is None:
            self._adapter = self._create_adapter()
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
