"""领域层 Token 消耗值对象模块

定义 Token 消耗值对象，用于记录单次 LLM 调用的 Token 消耗量
不变量：total_tokens == prompt_tokens + completion_tokens

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenConsumption:
    """Token 消耗值对象

    记录单次 LLM 调用的 Token 消耗量，自动计算 total_tokens

    不变量约束:
    - prompt_tokens >= 0
    - completion_tokens >= 0
    - total_tokens == prompt_tokens + completion_tokens

    Attributes:
        prompt_tokens: 输入 Token 数量
        completion_tokens: 输出 Token 数量
        total_tokens: 总 Token 数量（自动计算）
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int = 0

    def __post_init__(self) -> None:
        """验证不变量约束并自动计算 total_tokens."""
        if self.prompt_tokens < 0:
            raise ValueError(f"prompt_tokens must be non-negative. Got: {self.prompt_tokens}")
        if self.completion_tokens < 0:
            raise ValueError(f"completion_tokens must be non-negative. Got: {self.completion_tokens}")
        computed = self.prompt_tokens + self.completion_tokens
        object.__setattr__(self, "total_tokens", computed)
