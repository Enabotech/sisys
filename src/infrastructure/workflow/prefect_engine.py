"""基础设施层 Prefect 引擎适配器模块

PrefectEngine 实现 WorkflowEnginePort Protocol，封装 Prefect SDK 调用
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from prefect.client.orchestration import get_client
from prefect.states import StateType

from src.domain.value_objects.flow_status import FlowStatus
from src.infrastructure.config.prefect import PrefectConfig

if TYPE_CHECKING:
    from src.domain.ports.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


class PrefectEngine:
    """WorkflowEnginePort 的 Prefect 实现

    负责工作流生命周期管理（提交、状态查询、事件发布）
    所有 Prefect SDK 导入限定于此模块及子模块

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
        避免直接使用 Flow 对象（仅适用于进程内调用）
        成功后发布 WorkflowSubmitted 事件

        Args:
            flow_name: Deployment 名称，格式为 <FLOW_NAME>/<DEPLOYMENT_NAME>
            parameters: 工作流参数覆盖（未提供时使用 deployment 默认值）

        Returns:
            flow_run_id 字符串

        Raises:
            ValueError: flow_name 为空或格式无效
            RuntimeError: Prefect server 连接或 API 调用失败
        """
        if not flow_name or "/" not in flow_name:
            raise ValueError(f"flow_name 格式无效: '{flow_name}'，期望 '<FLOW_NAME>/<DEPLOYMENT_NAME>'")

        try:
            async with get_client() as client:
                deployment = await client.read_deployment_by_name(flow_name)
                flow_run = await client.create_flow_run_from_deployment(
                    deployment_id=deployment.id,
                    parameters=parameters,
                )
                flow_run_id = str(flow_run.id)
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"提交工作流失败 [{flow_name}]: {e}") from e

        # 事件发布独立于工作流提交，失败不影响返回值
        try:
            await self._publish_workflow_submitted(uuid.UUID(flow_run_id), flow_name, parameters)
        except Exception:
            logger.exception("WorkflowSubmitted 事件发布异常 [flow_run_id=%s]", flow_run_id)

        return flow_run_id

    async def get_flow_status(self, flow_run_id: str) -> FlowStatus:
        """查询工作流状态

        Args:
            flow_run_id: 工作流运行标识符

        Returns:
            FlowStatus 枚举值

        Raises:
            ValueError: flow_run_id 不是有效的 UUID 格式
            RuntimeError: Prefect server 连接或 API 调用失败
        """
        try:
            run_uuid = uuid.UUID(flow_run_id)
        except ValueError:
            raise ValueError(f"flow_run_id 格式无效: '{flow_run_id}'，期望 UUID 格式") from None

        try:
            async with get_client() as client:
                flow_run = await client.read_flow_run(run_uuid)
        except Exception as e:
            raise RuntimeError(f"查询工作流状态失败 [{flow_run_id}]: {e}") from e

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

    async def _publish_workflow_submitted(self, flow_run_id: uuid.UUID, flow_name: str, parameters: dict[str, Any]) -> None:
        """发布 WorkflowSubmitted 领域事件

        Args:
            flow_run_id: 工作流运行标识符
            flow_name: 工作流名称
            parameters: 工作流参数
        """
        from src.domain.events.workflow_events import WorkflowSubmitted

        event = WorkflowSubmitted(
            flow_run_id=flow_run_id,
            flow_name=flow_name,
            parameters=parameters,
        )
        publish_result = await self._event_publisher.publish(event)
        if publish_result is None:
            logger.warning("WorkflowSubmitted 事件发布返回 None [flow_run_id=%s]", flow_run_id)
        elif publish_result.is_full_failure:
            logger.warning(
                "WorkflowSubmitted 事件发布全部失败 [flow_run_id=%s]: %s",
                flow_run_id,
                publish_result,
            )
