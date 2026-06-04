"""基础设施层静态 Token 估算器模块

MVP 阶段使用静态估算策略：
- 本地模型：prompt=256, completion=512
- 云端模型：prompt=512, completion=1024

注意：此估算器返回固定值而非实际 LLM API 数据，使用时日志会输出 WARNING
"""

from __future__ import annotations

import logging

from src.domain.exceptions import ValidationError
from src.domain.ports.token_estimator import TokenEstimatorPort

logger = logging.getLogger(__name__)


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
            raise ValidationError(message="route_type must not be None or empty")
        if route_type.lower() == "local":
            prompt, completion = self.LOCAL_PROMPT_TOKENS, self.LOCAL_COMPLETION_TOKENS
        else:
            # 默认使用云端估算（包括未知路由类型）
            prompt, completion = self.CLOUD_PROMPT_TOKENS, self.CLOUD_COMPLETION_TOKENS

        logger.warning(
            "StaticTokenEstimator 返回估算值而非实际 LLM API 数据: route_type=%s, model=%s, prompt=%d, completion=%d",
            route_type,
            model,
            prompt,
            completion,
        )
        return prompt, completion
