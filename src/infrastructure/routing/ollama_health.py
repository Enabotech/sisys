"""OllamaHealth — Ollama 健康检查适配器与工厂。

本模块包含：
- OllamaHealthAdapter：HealthCheckPort 实现
- OllamaHealthCheckerFactory：创建 OllamaHealthAdapter 的工厂

六边形约束遵守：
- 工厂接口在 Domain 层（HealthCheckerFactory）
- 工厂实现和产品实现同在 Infrastructure 层
"""

from __future__ import annotations

import httpx

from src.domain.ports.health_check import HealthCheckPort
from src.domain.ports.health_check_factory import HealthCheckerFactory

DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434/api/health"


class OllamaHealthAdapter(HealthCheckPort):
    """Ollama 模型健康检查适配器。

    实现 HealthCheckPort 接口，使用 httpx.AsyncClient 检查 Ollama 服务可用性。
    """

    def __init__(
        self,
        endpoint: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        """初始化 Ollama 健康检查适配器。

        Args:
            endpoint: 自定义 Ollama 健康检查端点。默认为 localhost:11434.
            timeout: 请求超时时间（秒）。
        """
        self._endpoint = endpoint or DEFAULT_OLLAMA_ENDPOINT
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def check(self) -> bool:
        """检查 Ollama 服务是否可用。

        Returns:
            True 如果服务健康，False 否则。
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await self._client.get(self._endpoint)
            return response.status_code == 200
        except (httpx.RequestError, httpx.TimeoutException):
            return False

    async def close(self) -> None:
        """关闭健康检查连接，释放资源。"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class OllamaHealthCheckerFactory(HealthCheckerFactory):
    """Ollama 模型健康检查专用工厂。

    仅负责创建 OllamaHealthAdapter，不涉及其他模型类型。
    """

    def __init__(self, config=None) -> None:
        """初始化工厂。

        Args:
            config: UDMRConfig 配置，用于提取 endpoint。
        """
        self._config = config

    def create(self) -> HealthCheckPort:
        """创建 OllamaHealthAdapter 实例。

        Returns:
            OllamaHealthAdapter 实例。
        """
        endpoint = None
        if self._config and self._config.local_model:
            endpoint = self._config.local_model

        return OllamaHealthAdapter(endpoint=endpoint)


__all__ = [
    "OllamaHealthAdapter",
    "OllamaHealthCheckerFactory",
    "DEFAULT_OLLAMA_ENDPOINT",
]
