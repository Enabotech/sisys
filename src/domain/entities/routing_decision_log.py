"""领域层路由决策日志实体模块

定义路由决策日志领域实体，用于审计和成本追踪
WORM 存储要求（合规要求保留 7 年）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class RoutingDecisionLog:
    """路由决策日志条目

    存储路由决策细节，用于审计和成本追踪
    WORM 存储要求（合规要求保留 7 年）

    不变量约束:
    - log_id 必须为有效 UUID
    - task_id 不能为空
    - session_id 不能为空
    - route_type 必须为: "hash", "semantic", "mixed", "local", "cloud" 之一
    - route_score 必须在 0.0 至 1.0 范围内

    Attributes:
        log_id: 日志唯一标识符
        task_id: 任务标识符
        session_id: 会话标识符
        route_type: 路由类型
        route_target: 路由目标（智能体/工具/模型名）
        route_score: 路由置信度/评分（0.0-1.0）
        cost_estimate: 预估成本（美元）
        latency_ms: 路由决策延迟（毫秒）
        timestamp: 决策时间戳
        worm_storage_ref: WORM 存储引用（合规）
        selected_model: UDMR 选定模型（本地/云端）
        cost_actual: 实际成本（美元）
        fallback_reason: UDMR 回退原因
    """

    log_id: uuid.UUID
    task_id: str
    session_id: str
    route_type: str  # "hash" | "semantic" | "mixed" | "local" | "cloud"
    route_target: str  # Target Agent or tool ID or model name
    route_score: float  # Routing confidence/score (0.0 to 1.0)
    cost_estimate: float = 0.0  # Estimated cost in USD
    latency_ms: float = 0.0  # Routing decision latency in milliseconds
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    worm_storage_ref: str = ""  # WORM storage reference for compliance
    # UDMR extension fields
    selected_model: str = ""  # Selected model for UDMR (local/cloud)
    cost_actual: float = 0.0  # Actual cost in USD
    fallback_reason: str | None = None  # Fallback reason for UDMR
    # Token consumption fields (Story 1.19)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def validate(self) -> None:
        """验证不变量约束

        Raises:
            ValueError: 任何不变量违反时抛出
        """
        if not isinstance(self.log_id, uuid.UUID):
            raise ValueError("log_id must be a valid UUID")
        if not self.task_id or not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.session_id or not self.session_id.strip():
            raise ValueError("session_id must not be empty")
        if self.route_type not in ("hash", "semantic", "mixed", "local", "cloud"):
            raise ValueError(f"route_type must be one of: hash, semantic, mixed, local, cloud. Got: {self.route_type}")
        if not (0.0 <= self.route_score <= 1.0):
            raise ValueError(f"route_score must be between 0.0 and 1.0. Got: {self.route_score}")
        if self.cost_estimate < 0:
            raise ValueError(f"cost_estimate must be non-negative. Got: {self.cost_estimate}")
        if self.cost_actual < 0:
            raise ValueError(f"cost_actual must be non-negative. Got: {self.cost_actual}")
        if self.latency_ms < 0:
            raise ValueError(f"latency_ms must be non-negative. Got: {self.latency_ms}")
        if self.fallback_reason is not None and self.fallback_reason not in (
            "timeout",
            "unavailable",
            "health_check_failed",
        ):
            raise ValueError(
                f"fallback_reason must be one of: timeout, unavailable, health_check_failed. Got: {self.fallback_reason}"
            )
        # Token fields validation (Story 1.19)
        if self.prompt_tokens < 0:
            raise ValueError(f"prompt_tokens must be non-negative. Got: {self.prompt_tokens}")
        if self.completion_tokens < 0:
            raise ValueError(f"completion_tokens must be non-negative. Got: {self.completion_tokens}")
        if self.total_tokens < 0:
            raise ValueError(f"total_tokens must be non-negative. Got: {self.total_tokens}")
        # 不变量约束：total_tokens 必须等于 prompt + completion（非零时）
        if self.total_tokens > 0 and self.prompt_tokens + self.completion_tokens > 0:
            expected = self.prompt_tokens + self.completion_tokens
            if self.total_tokens != expected:
                raise ValueError(
                    f"total_tokens must equal prompt_tokens + completion_tokens. "
                    f"Got: total={self.total_tokens}, expected={expected}"
                )
