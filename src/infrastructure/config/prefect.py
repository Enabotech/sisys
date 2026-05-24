"""基础设施层 Prefect 配置模块

PrefectConfig 使用 frozen dataclass + from_env() 模式管理 Prefect 连接参数

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PrefectConfig:
    """Prefect 连接配置

    通过环境变量注入，支持多环境部署
    模式参考 AutoExecuteConfig（frozen dataclass + from_env()）
    """

    api_url: str = "http://localhost:4200/api"
    work_pool_name: str = "sisys-worker-pool"
    retry_max_attempts: int = 3
    retry_delay_seconds: int = 30
    task_timeout_seconds: int = 300
    flow_timeout_seconds: int = 3600

    @classmethod
    def from_env(cls) -> PrefectConfig:
        """从环境变量创建配置实例

        空字符串环境变量视为未设置，使用默认值

        Returns:
            PrefectConfig 实例
        """

        def _env_int(key: str, default: int) -> int:
            value = os.getenv(key, "")
            return int(value) if value else default

        return cls(
            api_url=os.getenv("PREFECT_API_URL", "http://localhost:4200/api") or "http://localhost:4200/api",
            work_pool_name=os.getenv("PREFECT_WORK_POOL_NAME", "sisys-worker-pool") or "sisys-worker-pool",
            retry_max_attempts=_env_int("PREFECT_RETRY_MAX_ATTEMPTS", 3),
            retry_delay_seconds=_env_int("PREFECT_RETRY_DELAY_SECONDS", 30),
            task_timeout_seconds=_env_int("PREFECT_TASK_TIMEOUT_SECONDS", 300),
            flow_timeout_seconds=_env_int("PREFECT_FLOW_TIMEOUT_SECONDS", 3600),
        )
