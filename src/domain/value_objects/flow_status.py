"""领域层工作流状态值对象模块

FlowStatus 枚举定义工作流执行状态，供 WorkflowEnginePort 和 OrchestrationService 跨层共享

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from enum import Enum


class FlowStatus(str, Enum):
    """工作流执行状态枚举

    业务层状态抽象，不直接映射 Prefect 全部技术状态（9→5 映射由 PrefectEngine 完成）

    映射关系：
    - PENDING: Prefect SCHEDULED/PENDING
    - RUNNING: Prefect RUNNING
    - COMPLETED: Prefect COMPLETED
    - FAILED: Prefect FAILED（重试耗尽）/CANCELLED/CRASHED/CANCELLING/PAUSED
    - RETRYING: Prefect FAILED（重试次数未耗尽）
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
