"""HealthCheckPort — 健康检查抽象端口。

用于检查外部服务（Ollama、Redis 等）的可用性。
所有健康检查实现必须实现此端口。

设计原则：
- 纯异步接口：async def check() 和 async def close()
- 领域层零外部依赖（仅用 abc + typing）
- ABC 父类选择（名义子类型，非结构子类型）
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class HealthCheckPort(ABC):
    """健康检查抽象端口。

    用于检查外部服务（Ollama、Redis 等）的可用性。
    所有健康检查实现必须实现此端口。
    """

    @abstractmethod
    async def check(self) -> bool:
        """检查服务是否可用。

        Returns:
            True 如果服务健康，False 否则。
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭健康检查连接，释放资源。"""
        pass
