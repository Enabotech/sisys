"""SISYS 基础设施层重试策略模块。

实现完整指数退避策略，配合 jitter 防止惊群效应和最大延迟上限，
用于消息重试调度

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class RetryPolicy:
    """重试策略配置

    指数退避公式: delay = min(base * 2^retry_count * jitter, max)
    jitter 范围: [0.5, 1.5]
    """

    base_delay: float = 1.0
    max_delay: float = 60.0
    max_retries: int = 3

    def get_delay(self, retry_count: int) -> float:
        """计算重试延迟

        Args:
            retry_count: 当前重试次数

        Returns:
            延迟秒数（永远 ≤ max_delay）
        """
        jitter: float = random.uniform(0.5, 1.5)  # nosec B311
        delay = min(self.base_delay * (2**retry_count) * jitter, self.max_delay)
        return float(delay)

    def should_retry(self, retry_count: int, max_retries: int | None = None) -> bool:
        """判断是否应该重试

        Args:
            retry_count: 当前重试次数
            max_retries: 最大重试次数（覆盖默认值）

        Returns:
            True: 可以重试
            False: 达到最大次数，不应重试
        """
        limit = max_retries if max_retries is not None else self.max_retries
        return retry_count < limit
