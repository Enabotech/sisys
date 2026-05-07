"""LocalModelHealth — 向后兼容入口与工厂函数。

提供：
- LocalModelHealth：向后兼容工厂函数
- create_local_model_health_facade：根据 config.model_type 分发到具体工厂

六边形约束遵守：
- 工厂函数在 Infrastructure 层
- 创建 Application 层需要的 LocalModelHealthFacade
- 通过 HealthCheckerFactory 接口创建具体 Adapter
"""

from __future__ import annotations

from src.application.services.local_model_health_facade import (
    LocalModelHealthFacade,
)
from src.infrastructure.config.udmr import UDMRConfig


def create_local_model_health_facade(config: UDMRConfig | None = None) -> LocalModelHealthFacade:
    """工厂函数：创建 LocalModelHealthFacade 实例。

    根据 config.local_model_type 选择对应的 HealthCheckerFactory 实现：
    - "gemini" -> GeminiHealthCheckerFactory (未来)
    - "vllm"   -> VllmHealthCheckerFactory (未来)
    - 默认     -> OllamaHealthCheckerFactory

    Args:
        config: UDMRConfig 配置，用于决定创建哪个 Adapter。

    Returns:
        LocalModelHealthFacade 实例。
    """
    from src.application.services.local_model_health_facade import (
        LocalModelHealthFacade,
    )
    from src.infrastructure.routing.ollama_health import (
        OllamaHealthCheckerFactory,
    )

    model_type = getattr(config, "local_model_type", None) if config else None

    if model_type == "gemini":
        msg = "Gemini health checker not yet implemented"
        raise NotImplementedError(msg)
    elif model_type == "vllm":
        msg = "vLLM health checker not yet implemented"
        raise NotImplementedError(msg)

    # 默认使用 OllamaHealthCheckerFactory
    factory = OllamaHealthCheckerFactory(config=config)
    return LocalModelHealthFacade(factory=factory, config=config)


def LocalModelHealth(  # noqa: N802
    endpoint: str | None = None,
    timeout: float = 5.0,
    config=None,  # UDMRConfig | None
):
    """创建 LocalModelHealthFacade 实例（向后兼容工厂函数）。

    Args:
        endpoint: 自定义 Ollama 健康检查端点（已废弃，仅保持向后兼容）
        timeout: 请求超时时间（秒）（已废弃，仅保持向后兼容）
        config: UDMRConfig 配置（推荐使用，用于多模型支持）

    Returns:
        LocalModelHealthFacade 实例
    """
    # 如果提供了 config，使用工厂创建
    if config is not None:
        return create_local_model_health_facade(config=config)

    # 向后兼容：创建默认 facade
    return create_local_model_health_facade(config=None)


__all__ = ["LocalModelHealth", "create_local_model_health_facade"]
