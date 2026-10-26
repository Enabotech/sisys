"""应用层 EIP 隔离管理服务模块（Story 5.4 — EIP 弹性隔离协议基础；
Story 5.6 扩展——audit-first 切换日志写入 + audit 联动）

实现 IsolationManagementServicePort（应用层服务，R2——组合注入四 domain 端口
+ 一个同层应用端口六依赖）:
- isolation_repository（domain 端口——隔离状态持久化）
- agent_repository（domain 端口——443 存在性守卫）
- event_publisher（domain 端口——切换事件发布）
- agent_config_loader（应用端口——switch 重置 TTL 真源 AgentConfig.state_ttl，R1-F01）
- isolation_switch_log_repository（domain 基础端口——切换日志持久化，Story 5.6
  第五依赖必填：审计日志可被静默跳过是合规缺口，弃 None 容忍——5-5 守卫必填
  先例同哲学）
- audit_service（domain 服务端口——统一审计联动，Story 5.6 第六依赖可选：
  联动审计是增值索引非 SSOT，resolve_optional + 失败降级——DC-6）

守卫序契约（DC-5）:
- get/switch: Agent 存在(443) → 隔离状态存在(447) → 等级合法(446 实体内聚)
- 等级合法性校验内聚实体（initialize/switch_to 两入口统一——CLI 只做
  字符串→枚举转换守卫，服务不重复校验向上透传）

no-op 语义（DC-5）: switch_to 返回 False → switched=False + 零仓储写 +
零事件发布 + 零日志写（幂等；「切换」事件语义要求前后等级相异；TTL 不刷新
——查询型重复调用不得无限续期；Story 5.6: no-op 不得产生日志——审计留痕
面与事件语义对齐）。

audit-first 写入链（Story 5.6 DC-2——FR-AC-06 审计留痕面）:
no-op 检查 → 构造事件 → from_event（零加工映射——事件 payload 六字段 SSOT）
→ config load（只读前置——TTL 真源；440 失败路径零日志/零 Redis 写/零事件，
干净拒绝退出误报窗口）→ **日志 save（失败上抛 = 切换被拒——fail-closed：
无审计痕迹的切换不允许发生）** → Redis 状态写 → 事件发布（DC-10 容错）
→ audit 联动（可选 + 降级——DC-6）。
顺序论证（audit-first vs state-first）: state-first 在日志失败时丢审计（合规
红线）；audit-first 的反向窗口（日志写成功 + Redis 写失败 → 未生效切换的日志
记录）登记 5-6 风险 #1——两害相权，审计合规宁可多记不可漏记。

事件发布失败容错（DC-10）: 记日志不回滚——状态已切换是事实、事件是通知；
真实失败面为 PublishResult.is_success == False（DualChannelEventBus 捕获异常
返回失败结果不抛出）与 raise 两分支（InstantiateAgentUseCase 先例同款）。

audit 联动失败降级（DC-6）: try/except logger.warning 不回滚不重试——主日志
SSOT 已在 isolation_switch_log_repository 落盘，audit_log 是联动索引
（PersistentNoteTaker 先例）；AuditServiceImpl 在 CLI 上下文（无请求 session）
会包装 AuditError 上抛，必填+上抛会使 CLI set-isolation 崩溃，降级保主链可用。
"""

from __future__ import annotations

import logging
from uuid import UUID

from src.application.ports.agent_config_loader import AgentConfigLoader
from src.application.ports.isolation_management import (
    IsolationManagementServicePort,
    IsolationSwitchResult,
)
from src.domain.entities.isolation_state import IsolationState
from src.domain.entities.isolation_switch_log import IsolationSwitchLog
from src.domain.events.audit_events import AuditActionType
from src.domain.events.enums import IsolationLevel
from src.domain.events.isolation_events import IsolationLevelSwitched
from src.domain.exceptions import AgentNotFoundError, EntityValidationError, IsolationStateNotInitializedError
from src.domain.ports.agent_repository import AgentRepository
from src.domain.ports.audit_service import AuditServicePort
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.isolation_repository import IsolationRepository
from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogRepository

logger = logging.getLogger(__name__)


class IsolationManagementService(IsolationManagementServicePort):
    """EIP 隔离管理服务（三方法: initialize/get/switch——同聚合同关注点 DC-4）

    Attributes:
        _isolation_repository: 隔离状态仓储端口（组合根 isolation_repository）
        _agent_repository: Agent 仓储端口（组合根 agent_repository——443 守卫）
        _event_publisher: 事件发布端口（组合根 event_publisher）
        _agent_config_loader: 配置加载端口（组合根 agent_config_loader——TTL 真源）
        _isolation_switch_log_repository: 切换日志仓储端口（组合根
            isolation_switch_log_repository——Story 5.6 第五依赖，必填）
        _audit_service: 审计服务端口（组合根 audit_service——Story 5.6 第六
            依赖，可选 None 零联动）
    """

    def __init__(
        self,
        isolation_repository: IsolationRepository,
        agent_repository: AgentRepository,
        event_publisher: EventPublisher,
        agent_config_loader: AgentConfigLoader,
        isolation_switch_log_repository: IsolationSwitchLogRepository,
        audit_service: AuditServicePort | None = None,
    ) -> None:
        """初始化服务（R2 组合六依赖——四 domain 端口 + 同层应用端口 + 可选审计端口）

        Args:
            isolation_repository: 隔离状态仓储端口
            agent_repository: Agent 仓储端口（443 存在性守卫）
            event_publisher: 事件发布端口
            agent_config_loader: 配置加载端口（switch 重置 TTL 真源）
            isolation_switch_log_repository: 切换日志仓储端口（第五依赖必填——
                审计日志可被静默跳过是合规缺口，弃 None 容忍）
            audit_service: 审计服务端口（第六依赖可选——联动审计是增值索引非
                SSOT；None 时零联动，主链不受影响）
        """
        self._isolation_repository = isolation_repository
        self._agent_repository = agent_repository
        self._event_publisher = event_publisher
        self._agent_config_loader = agent_config_loader
        self._isolation_switch_log_repository = isolation_switch_log_repository
        self._audit_service = audit_service

    async def initialize_agent_isolation(
        self, agent_id: UUID, default_level: IsolationLevel, ttl_seconds: int
    ) -> IsolationState:
        """初始化隔离状态（upsert——前置条件: agent 已持久化，无 443 前置守卫）

        Raises:
            IsolationLevelNotSupportedError: 非法等级（EXCEPTION_446——实体工厂守卫透传）
            AgentConfigError: TTL 越界（EXCEPTION_440——仓储防御校验透传）
            StorageError: 存储故障（EXCEPTION_103——透传）
        """
        state = IsolationState.initialize(agent_id, default_level)
        await self._isolation_repository.save(state, ttl=ttl_seconds)
        logger.info(
            "隔离状态初始化: agent_id=%s level=%s ttl=%d",
            agent_id,
            default_level.value,
            ttl_seconds,
        )
        return state

    async def get_isolation_state(self, agent_id: UUID) -> IsolationState:
        """查询隔离状态（隔离检查入口——守卫序 443 → 447）

        Raises:
            AgentNotFoundError: Agent 不存在（EXCEPTION_443）
            IsolationStateNotInitializedError: 隔离状态缺失（EXCEPTION_447）
            StorageError: 存储故障（EXCEPTION_103——透传）
        """
        agent = await self._agent_repository.get_by_id(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id=str(agent_id))
        state = await self._isolation_repository.get_by_agent_id(agent_id)
        if state is None:
            raise IsolationStateNotInitializedError(agent_id=str(agent_id))
        return state

    async def switch_isolation_level(
        self,
        agent_id: UUID,
        target_level: IsolationLevel,
        trigger_reason: str,
        approval_chain: tuple[str, ...] | list[str] = (),
    ) -> IsolationSwitchResult:
        """切换隔离等级（守卫序 443 → 447 → 446 实体内聚 + no-op 零副作用
        + audit-first 日志写入——Story 5.6 DC-2）

        写入链顺序: no-op 检查 → approval_chain 形态校验 → 构造事件 → from_event
        → config load（只读）→ 日志 save（失败上抛 = 切换被拒）→ Redis 状态写
        → 事件发布（容错）→ audit 联动（可选 + 降级）。日志先于状态写
        （fail-closed——无审计痕迹的切换不允许发生）；审计联动失败降级不回滚
        （主日志 SSOT 已落盘）。

        Args:
            approval_chain: 审批链（tuple/list 形态——str 一律拒：str 是
                ``Sequence[str]`` 合法子类型但语义为单审批人字符串，经
                ``list()`` 会爆裂成单字符序列造成审计数据永久损坏，
                5-6 R1-F1 双层防御的服务层入口面）。

        Raises:
            AgentNotFoundError: Agent 不存在（EXCEPTION_443）
            IsolationStateNotInitializedError: 隔离状态缺失（EXCEPTION_447）
            IsolationLevelNotSupportedError: 等级非法（EXCEPTION_446——实体 switch_to）
            EntityValidationError: trigger_reason 空/空白 或 approval_chain 为
                str 形态（EXCEPTION_242——实体不变量透传 + 入口形态守卫）
            AgentConfigError: 配置加载失败/TTL 越界（EXCEPTION_440——零日志零
                Redis 写零事件的干净拒绝）
            StorageError: 存储/日志故障（EXCEPTION_103——日志 save 失败上抛 =
                切换被拒，fail-closed）
        """
        agent = await self._agent_repository.get_by_id(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id=str(agent_id))
        state = await self._isolation_repository.get_by_agent_id(agent_id)
        if state is None:
            raise IsolationStateNotInitializedError(agent_id=str(agent_id))

        previous_level = state.current_level
        switched = state.switch_to(target_level, trigger_reason)
        if not switched:
            # no-op: 零仓储写零事件零日志（幂等——TTL 不刷新，查询型重复调用不得
            # 无限续期；Story 5.6: no-op 不得产生日志——审计留痕面与事件语义对齐）
            logger.info("隔离等级同等级 no-op: agent_id=%s level=%s", agent_id, target_level.value)
            return IsolationSwitchResult(switched=False, state=state, event=None)

        # approval_chain 形态守卫（5-6 R1-F1 服务层入口面——插位与事件构造同位：
        # 守卫序 443→447→no-op 后、状态变异前置校验；str 是 Sequence 合法子类型
        # 但 list("审批人") 会爆裂成单字符序列——审计数据永久损坏防线）
        if isinstance(approval_chain, str):
            raise EntityValidationError(
                message="approval_chain 不能为字符串（单审批人请传单元素序列，字符串会被逐字符爆裂）",
                context={"approval_chain": str(approval_chain)},
            )

        # 事件构造（audit-first 插位上移——Story 5.6: from_event 消费该事件对象；
        # 六字段输入在 no-op 检查后全部就绪，与 Redis save 无依赖）
        event = IsolationLevelSwitched(
            agent_id=agent_id,
            previous_level=previous_level,
            target_level=target_level,
            trigger_reason=state.last_trigger_reason,  # strip 后文本（与持久化态单源——事件/状态双投影一致，R3-F03）
            approval_chain=list(approval_chain),  # kw_only 必填形态（DC-6）+ 显式转发
            switch_timestamp=state.updated_at,  # 单钟纪律: 事件时刻=状态变更时刻（对齐 initialize 单 now 双用叙事）
        )
        # audit-first 日志（Story 5.6 DC-2）: from_event 零加工映射（事件 payload
        # 六字段 SSOT）——先于状态写，日志失败 = 切换被拒（无审计痕迹的切换
        # 不允许发生）
        log = IsolationSwitchLog.from_event(event)

        # TTL 真源（R1-F01）: 复用 443 守卫已取 agent → config.state_ttl
        # （agent_config_loader 同层应用端口注入——零第二真源零额外 Redis 读；
        # 只读前置——440 失败路径零日志/零 Redis 写/零事件，干净拒绝退出误报窗口）
        config = await self._agent_config_loader.load(agent.role)

        await self._isolation_switch_log_repository.save(log)
        await self._isolation_repository.save(state, ttl=config.state_ttl)

        try:
            publish_result = await self._event_publisher.publish(event)
        except Exception:
            # 发布失败记日志不回滚（DC-10——状态已切换是事实、事件是通知；
            # exc_info=True 记录完整异常链，无需绑定异常变量）
            logger.warning("隔离切换事件发布失败（状态已切换）: agent_id=%s", agent_id, exc_info=True)
        else:
            if publish_result is not None and not publish_result.is_success:
                # 真实总线失败面（DualChannelEventBus 捕获异常返回失败结果不抛出）
                logger.warning(
                    "隔离切换事件发布失败结果（状态已切换）: agent_id=%s channels=%s",
                    agent_id,
                    publish_result.results,
                )

        # audit 联动（Story 5.6 DC-6——可选 + 降级）: isolation:switch 动作使隔离
        # 切换进入 1.10 统一审计检索面；失败降级不回滚不重试（主日志 SSOT 已落盘，
        # PersistentNoteTaker 先例）；old/new_value 的 level 用 .value 字符串
        # （JSONB 序列化安全——传枚举对象会触发降级静默丢失）
        if self._audit_service is not None:
            try:
                await self._audit_service.record(
                    actor=f"agent:{agent_id}",
                    action_type=AuditActionType.ISOLATION_SWITCH.value,
                    target_resource=f"agent:{agent_id}",
                    old_value={"level": previous_level.value},
                    new_value={
                        "level": target_level.value,
                        "reason": state.last_trigger_reason,  # strip 后单源（与事件/日志双投影一致——R1-F12 审计对账文本等值）
                        "approval_chain": list(approval_chain),
                    },
                    correlation_id=str(event.event_id),
                )
            except Exception:
                logger.warning("隔离切换联动审计记录失败（主日志已落盘）: agent_id=%s", agent_id, exc_info=True)
        logger.info(
            "隔离等级切换: agent_id=%s %s -> %s（原因: %s）",
            agent_id,
            previous_level.value,
            target_level.value,
            trigger_reason,
        )
        return IsolationSwitchResult(switched=True, state=state, event=event)


__all__ = ["IsolationManagementService"]
