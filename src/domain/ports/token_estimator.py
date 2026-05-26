"""领域层 Token 估算端口模块

定义 Token 消耗估算的领域端口，供基础设施层实现
MVP 阶段使用静态估算策略（本地 256+512，云端 512+1024）
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TokenEstimatorPort(Protocol):
    """Token 消耗估算端口

    定义 Token 消耗估算的领域端口，供基础设施层实现
    MVP 阶段使用静态估算策略
    """

    async def estimate(self, route_type: str, model: str) -> tuple[int, int]:
        """估算 Token 消耗

        Args:
            route_type: 路由类型（local/cloud）
            model: 模型标识符

        Returns:
            (prompt_tokens, completion_tokens) 元组
        """
        ...
