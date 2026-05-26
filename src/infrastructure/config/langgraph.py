"""基础设施层 LangGraph 配置模块

LangGraphConfig 使用 frozen dataclass + from_env() 模式管理 LangGraph 连接参数
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LangGraphConfig:
    """LangGraph 连接配置

    通过环境变量注入，支持多环境部署
    模式参考 PrefectConfig（frozen dataclass + from_env()）
    """

    api_url: str = "http://localhost:8000"
    checkpoint_table: str = "langgraph_checkpoints"
    retry_max_attempts: int = 3
    retry_delay_seconds: int = 30
    task_timeout_seconds: int = 300
    graph_timeout_seconds: int = 1800

    @classmethod
    def from_env(cls) -> LangGraphConfig:
        """从环境变量创建配置实例

        空字符串环境变量视为未设置，使用默认值

        Returns:
            LangGraphConfig 实例
        """

        def _env_int(key: str, default: int) -> int:
            value = os.getenv(key, "")
            if not value:
                return default
            try:
                return int(value)
            except ValueError:
                raise ValueError(f"环境变量 {key} 的值 '{value}' 不是有效整数，期望数字") from None

        return cls(
            api_url=os.getenv("LANGGRAPH_API_URL", "http://localhost:8000") or "http://localhost:8000",
            checkpoint_table=os.getenv("LANGGRAPH_CHECKPOINT_TABLE", "langgraph_checkpoints") or "langgraph_checkpoints",
            retry_max_attempts=_env_int("LANGGRAPH_RETRY_MAX_ATTEMPTS", 3),
            retry_delay_seconds=_env_int("LANGGRAPH_RETRY_DELAY_SECONDS", 30),
            task_timeout_seconds=_env_int("LANGGRAPH_TASK_TIMEOUT_SECONDS", 300),
            graph_timeout_seconds=_env_int("LANGGRAPH_GRAPH_TIMEOUT_SECONDS", 1800),
        )
