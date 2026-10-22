"""应用层 EIP 隔离管理端口模块（Story 5.4 — EIP 弹性隔离协议基础）

EIP 隔离管理的应用层端口（R2 具体应用端口——组合注入 R1 领域层基础端口
IsolationRepository/AgentRepository/EventPublisher + 同层应用端口
AgentConfigLoader 四依赖）。实现类 IsolationManagementService 在
application/services/，经组合根注册为 `isolation_management_service`（SINGLETON）。

设计决策（Story 5.4 DC-4）:
- 单端口三方法（initialize/get/switch）: 三操作同聚合（IsolationState）同关注点
  （EIP 管理），避免三个微用例类蔓延
- 纯策略表（ISOLATION_POLICIES）留 domain value_objects；本端口编排仓储读写
  与事件发布，属应用编排关注点（偏离声明 D-2）

异常契约:
- AgentNotFoundError(443): get/switch 前置 Agent 存在守卫（agent_repository）
- IsolationStateNotInitializedError(447): 隔离状态缺失
- IsolationLevelNotSupportedError(446): 等级非法（实体工厂/switch_to 内聚抛出，
  本层向上透传不重复校验）
- AgentConfigError(440): TTL 越界（仓储防御校验）/ 配置加载失败
- StorageError(103): 存储连接故障（透传）

Run with:
    经组合根 resolve("isolation_management_service") 获取实现
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.entities.isolation_state import IsolationState
from src.domain.events.enums import IsolationLevel
from src.domain.events.isolation_events import IsolationLevelSwitched


@dataclass(frozen=True)
class IsolationSwitchResult:
    """隔离等级切换结果 DTO（多字段组合载体——端口文件内定义先例）

    Attributes:
        switched: 是否发生实际切换（False=同等级 no-op——幂等语义）
        state: 切换后的隔离状态（no-op 时为当前未变更状态）
        event: 发布的切换事件（no-op 时为 None——零事件语义）
    """

    switched: bool
    state: IsolationState
    event: IsolationLevelSwitched | None


@runtime_checkable
class IsolationManagementServicePort(Protocol):
    """EIP 隔离管理端口（应用层，Story 5.4 新增——MVP 唯一触发通道为用户显式请求）"""

    async def initialize_agent_isolation(
        self, agent_id: UUID, default_level: IsolationLevel, ttl_seconds: int
    ) -> IsolationState:
        """初始化 Agent 隔离状态（upsert 语义——重复初始化覆盖回默认等级）

        前置条件（调用方保证）: agent 已持久化——本方法无 443 前置守卫；
        MVP 唯一调用方 InstantiateAgentUseCase 在 save(agent) 之后调用满足前提。
        重复初始化覆盖回默认等级是安全方向设计意图（回最严格等级——
        Story 5.4 DC-3/R1-F33；服务级以同 id 重新 initialize 可自愈 fail-fast 残留态）。

        Args:
            agent_id: 归属 Agent 唯一标识
            default_level: 初始等级（真源 AgentConfig.default_isolation_level）
            ttl_seconds: 状态 TTL 秒（真源 AgentConfig.state_ttl——与 Agent 键同源 DC-9）

        Returns:
            初始化完成的 IsolationState（last_trigger_reason=="initial_default"）

        Raises:
            IsolationLevelNotSupportedError: 非法等级（EXCEPTION_446——实体工厂守卫）
            AgentConfigError: TTL 越界（EXCEPTION_440——仓储防御校验）
            StorageError: 存储故障（EXCEPTION_103）
        """
        ...

    async def get_isolation_state(self, agent_id: UUID) -> IsolationState:
        """查询 Agent 隔离状态（隔离检查入口——5.5 执行前强制检查消费面）

        守卫序: Agent 存在(443) → 隔离状态存在(447)——隔离检查先验 Agent 合法性。

        Args:
            agent_id: 目标 Agent 唯一标识

        Returns:
            完整 IsolationState（三重隔离策略由消费方持 state 联查
            get_isolation_policy(state.current_level) 派生——本返回不含策略）

        Raises:
            AgentNotFoundError: Agent 不存在（EXCEPTION_443）
            IsolationStateNotInitializedError: 隔离状态缺失（EXCEPTION_447）
            StorageError: 存储故障（EXCEPTION_103）
        """
        ...

    async def switch_isolation_level(
        self,
        agent_id: UUID,
        target_level: IsolationLevel,
        trigger_reason: str,
        approval_chain: tuple[str, ...] | list[str] = (),
    ) -> IsolationSwitchResult:
        """切换隔离等级（MVP 唯一触发通道——用户显式请求）

        守卫序: Agent 存在(443) → 隔离状态存在(447) → 等级合法(446，实体内聚)。
        通过后切换等级、刷新 TTL（真源 config.state_ttl——R1-F01）、发布
        IsolationLevelSwitched 事件；同等级为 no-op（零仓储写零事件——幂等）。

        Args:
            agent_id: 目标 Agent 唯一标识
            target_level: 目标等级（IsolationLevel 枚举实例）
            trigger_reason: 切换原因（非空——用户显式请求语义必填）
            approval_chain: 审批链（默认空——MVP 用户直切无审批链，V1 SYS 命令通道扩展）

        Returns:
            IsolationSwitchResult（switched/state/event 三字段）

        Raises:
            AgentNotFoundError: Agent 不存在（EXCEPTION_443）
            IsolationStateNotInitializedError: 隔离状态缺失（EXCEPTION_447）
            IsolationLevelNotSupportedError: 等级非法（EXCEPTION_446——实体 switch_to）
            EntityValidationError: trigger_reason 空/空白（EXCEPTION_242——实体不变量透传）
            AgentConfigError: 配置加载失败/TTL 越界（EXCEPTION_440）
            StorageError: 存储故障（EXCEPTION_103）
        """
        ...


__all__ = ["IsolationManagementServicePort", "IsolationSwitchResult"]
