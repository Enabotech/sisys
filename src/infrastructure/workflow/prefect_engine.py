"""基础设施层 Prefect 引擎适配器模块

PrefectEngine 实现 WorkflowEnginePort Protocol，封装 Prefect SDK 调用

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from prefect.client.orchestration import get_client
from prefect.states import StateType

from src.domain.value_objects.flow_status import FlowStatus
from src.infrastructure.config.prefect import PrefectConfig

if TYPE_CHECKING:
    from src.domain.ports.event_publisher import EventPublisher


class PrefectEngine:
    """WorkflowEnginePort 的 Prefect 实现

    负责工作流生命周期管理（提交、状态查询、事件发布）。
    所有 Prefect SDK 导入限定于此模块及子模块。

    Args:
        config: Prefect 连接配置
        event_publisher: 事件发布端口（通过构造函数注入）
    """

    def __init__(self, config: PrefectConfig, event_publisher: EventPublisher) -> None:
        self._config = config
        self._event_publisher = event_publisher

    async def submit_flow(self, flow_name: str, parameters: dict[str, Any]) -> str:
        """通过 Deployment 提交工作流执行

        使用 Prefect 推荐的 deployment 模式触发远程工作流，
        避免直接使用 Flow 对象（仅适用于进程内调用）。

        Args:
            flow_name: Deployment 名称，格式为 <FLOW_NAME>/<DEPLOYMENT_NAME>
            parameters: 工作流参数覆盖（未提供时使用 deployment 默认值）

        Returns:
            flow_run_id 字符串
        """
        async with get_client() as client:
            deployment = await client.read_deployment_by_name(flow_name)
            flow_run = await client.create_flow_run_from_deployment(
                deployment_id=deployment.id,
                parameters=parameters,
            )
            return str(flow_run.id)

    async def get_flow_status(self, flow_run_id: str) -> FlowStatus:
        """查询工作流状态

        Args:
            flow_run_id: 工作流运行标识符

        Returns:
            FlowStatus 枚举值
        """
        run_uuid = uuid.UUID(flow_run_id)
        async with get_client() as client:
            flow_run = await client.read_flow_run(run_uuid)

        return self._map_state_type(flow_run.state, flow_run.run_count)

    def _map_state_type(self, state: Any, run_count: int) -> FlowStatus:
        """映射 Prefect StateType 到 FlowStatus

        Args:
            state: Prefect state 对象
            run_count: 已运行次数（用于判定是否重试中）

        Returns:
            FlowStatus 枚举值
        """
        state_type = state.type if state else None

        if state_type == StateType.SCHEDULED or state_type == StateType.PENDING:
            return FlowStatus.PENDING
        if state_type == StateType.RUNNING:
            return FlowStatus.RUNNING
        if state_type == StateType.COMPLETED:
            return FlowStatus.COMPLETED
        if state_type == StateType.FAILED:
            max_retries = self._config.retry_max_attempts
            if run_count < max_retries:
                return FlowStatus.RETRYING
            return FlowStatus.FAILED
        # CANCELLED, CRASHED, CANCELLING, PAUSED → FAILED
        return FlowStatus.FAILED
