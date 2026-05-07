"""OllamaHealthAdapter — Ollama 健康检查适配器。

实现 HealthCheckPort 接口，使用 httpx.AsyncClient 替代同步 requests.Session。

设计原则：
- 纯异步接口：async def check() 和 async def close()
- httpx.AsyncClient 用于非阻塞 HTTP 请求
- 领域层零外部依赖（端口在 domain，适配器在 infrastructure）
"""

from __future__ import annotations

import httpx

from src.domain.ports.health_check import HealthCheckPort

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


__all__ = ["OllamaHealthAdapter", "DEFAULT_OLLAMA_ENDPOINT"]
