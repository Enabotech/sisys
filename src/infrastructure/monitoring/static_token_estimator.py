"""基础设施层静态 Token 估算器模块

MVP 阶段使用静态估算策略：
- 本地模型：prompt=256, completion=512
- 云端模型：prompt=512, completion=1024

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from src.domain.ports.token_estimator import TokenEstimatorPort


class StaticTokenEstimator(TokenEstimatorPort):
    """静态 Token 估算器

    MVP 阶段使用固定值估算 Token 消耗
    """

    # MVP 估算常量
    LOCAL_PROMPT_TOKENS = 256
    LOCAL_COMPLETION_TOKENS = 512
    CLOUD_PROMPT_TOKENS = 512
    CLOUD_COMPLETION_TOKENS = 1024

    async def estimate(self, route_type: str, model: str) -> tuple[int, int]:
        """估算 Token 消耗

        Args:
            route_type: 路由类型（local/cloud），不区分大小写
            model: 模型标识符（MVP 阶段未使用）

        Returns:
            (prompt_tokens, completion_tokens) 元组

        Raises:
            ValueError: route_type 为 None 或空字符串时
        """
        if not route_type or not route_type.strip():
            raise ValueError("route_type must not be None or empty")
        if route_type.lower() == "local":
            return self.LOCAL_PROMPT_TOKENS, self.LOCAL_COMPLETION_TOKENS
        # 默认使用云端估算（包括未知路由类型）
        return self.CLOUD_PROMPT_TOKENS, self.CLOUD_COMPLETION_TOKENS
