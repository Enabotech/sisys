"""应用层 Agent 实例化用例模块（Story 5-1 — CEO Agent 实例化 MVP；Story 5-4 隔离初始化注入）

实现 InstantiateAgentUseCase（应用层用例，R2——MVP 以应用层用例实现实例化
编排，不新建 domain AgentService，偏离声明 D-7）。

编排流程（顺序契约，守卫必须先于加载）：
1. 角色守卫——非 MVP 开放角色抛 AgentRoleNotSupportedError(441)。
   ⚠️ 守卫先于加载是可达性前提：若先加载，execute(CFO) 会先触发
   cfo_agent.yaml 缺失的 AgentConfigError(440)，441 将不可达
   （"cfo" 是合法枚举值，枚举转换拦不住它）
2. 加载配置——AgentConfigLoader 端口（440 传播）
3. 构建实体——复用现有 Agent 实体（构造不修改）；responsibilities/
   domain_knowledge 以 list(...) 显式转换注入（实体字段 list[str]，tuple
   直传将使读写往返类型不对称）；agent.validate() 的 242 透传不包装
4. 持久化——AgentRepository.save(agent, ttl=config.state_ttl) 显式传入
   （VO 是唯一默认值真源）；失败传播且不发布事件（无持久化即无事件——
   Agent 聚合在 Redis、发件箱在 PG 跨存储无 ACID，此序保证无幽灵事件）
5. 隔离初始化（Story 5-4）——IsolationManagementServicePort.initialize_agent_isolation
   （等级=config.default_isolation_level、TTL=config.state_ttl 双消费——实例化即
   L4 硬隔离）；失败向上抛 fail-fast（安全基线优先——静默成功=安全默认破洞；
   残留 agent 键由 TTL 自然回收，DC-3）
6. 发布事件——AgentInstantiated（reliable 审计合规型）；发布失败记日志
   不回滚（对齐 run_tool_chain L180-185 用例先例）；真实失败面为
   PublishResult.is_success == False（raise 路径仅异常基础设施触发）

幂等性：execute 非幂等——每次调用创建新 Agent 与新 Redis 键（AC-1.3
设计行为，靠 TTL 自然回收）。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from src.application.ports.agent_config_loader import AgentConfigLoader
from src.application.ports.isolation_management import IsolationManagementServicePort
from src.domain.entities.agent import Agent, AgentRole
from src.domain.events.agent_events import AgentInstantiated
from src.domain.exceptions import AgentRoleNotSupportedError
from src.domain.ports.agent_repository import AgentRepository
from src.domain.ports.event_publisher import EventPublisher

logger = logging.getLogger(__name__)

# MVP 开放角色常量真源（V1 开放 CFO 时仅改此一处——441 的 context["supported_roles"]
# 从本常量派生，勿硬编码字面量列表）
SUPPORTED_ROLES: frozenset[AgentRole] = frozenset({AgentRole.CEO})


@dataclass(frozen=True)
class AgentInstantiationResult:
    """实例化结果 DTO（应用层，模块内定义——对齐 strategic_analysis.py 先例）

    Attributes:
        agent_id: 新建 Agent 唯一标识
        agent: Agent 聚合根实体引用（role/status/name 等由调用方读取）
    """

    agent_id: uuid.UUID
    agent: Agent


class InstantiateAgentUseCase:
    """Agent 实例化用例

    编排：角色守卫 → 加载配置 → 构建实体 → 持久化 → 隔离初始化 → 发布事件。
    依赖经端口注入（config_loader/repository/event_publisher/isolation_service
    ——R2 同层应用端口组合注入，Story 5-4），不导入 infrastructure 具体实现。

    Attributes:
        _config_loader: Agent 基础配置加载端口
        _repository: Agent 聚合仓储端口
        _event_publisher: 事件发布端口
        _isolation_service: EIP 隔离管理端口（Story 5-4 第四依赖）
    """

    def __init__(
        self,
        config_loader: AgentConfigLoader,
        repository: AgentRepository,
        event_publisher: EventPublisher,
        isolation_service: IsolationManagementServicePort,
    ) -> None:
        """初始化用例

        Args:
            config_loader: 配置加载端口（组合根 agent_config_loader）
            repository: Agent 仓储端口（组合根 agent_repository）
            event_publisher: 事件发布端口（组合根 event_publisher）
            isolation_service: EIP 隔离管理端口（组合根 isolation_management_service
                ——Story 5-4 注入，实例化即默认 L4 硬隔离）
        """
        self._config_loader = config_loader
        self._repository = repository
        self._event_publisher = event_publisher
        self._isolation_service = isolation_service

    async def execute(self, role: AgentRole) -> AgentInstantiationResult:
        """执行 Agent 实例化

        Args:
            role: 请求实例化的 Agent 角色

        Returns:
            AgentInstantiationResult（agent_id + 实体引用）

        Raises:
            AgentRoleNotSupportedError: MVP 未开放角色（EXCEPTION_441，先于加载）
            AgentConfigError: 配置资产无效（EXCEPTION_440，透传加载器）
            EntityValidationError: 实体不变量违反（EXCEPTION_242，透传不包装）
            StorageError: 持久化故障（EXCEPTION_103，透传仓储——不返回假成功）
            IsolationLevelNotSupportedError: 隔离初始化等级非法（EXCEPTION_446，
                透传隔离服务——fail-fast 不发布事件）
        """
        # 1. 角色守卫（先于加载——441 可达性前提，见模块 docstring）
        if role not in SUPPORTED_ROLES:
            raise AgentRoleNotSupportedError(
                role=role.value,
                supported_roles=tuple(sorted(supported.value for supported in SUPPORTED_ROLES)),
            )

        # 2. 加载基础配置（440 传播）
        config = await self._config_loader.load(role)

        # 3. 构建实体（复用现有 Agent 实体；list(...) 显式转换——实体字段 list[str]）
        agent = Agent(
            agent_id=uuid.uuid4(),
            role=config.role,
            name=config.name,
            description=config.description,
            domain_knowledge=list(config.domain_knowledge),
            responsibilities=list(config.responsibilities),
        )
        agent.validate()  # 242 透传不包装（VO 440 已拦截绝大多数非法态）

        # 4. 持久化（ttl 显式自 config.state_ttl；失败传播且零事件——无幽灵事件）
        await self._repository.save(agent, ttl=config.state_ttl)

        # 5. 隔离初始化（Story 5-4：实例化即默认 L4 硬隔离——等级与 TTL 双消费
        # config 真源；失败 fail-fast 向上抛且不发布事件——安全基线优先，DC-3）
        await self._isolation_service.initialize_agent_isolation(
            agent.agent_id, config.default_isolation_level, config.state_ttl
        )

        # 6. 发布事件（失败记日志不回滚——先持久化后发布保证「无持久化即无事件」）
        event = AgentInstantiated(
            agent_id=agent.agent_id,
            role=agent.role.value,
            name=agent.name,
            config_version=config.version,
        )
        try:
            publish_result = await self._event_publisher.publish(event)
            if publish_result is not None and not publish_result.is_success:
                logger.error(
                    "AgentInstantiated 事件发布未成功: agent_id=%s channels=%s",
                    agent.agent_id,
                    publish_result.results,
                )
        except Exception as exc:
            # 事件发布失败不阻塞业务结果（对齐 run_tool_chain 用例先例）
            logger.error("Failed to publish AgentInstantiated event: %s", exc, exc_info=True)

        return AgentInstantiationResult(agent_id=agent.agent_id, agent=agent)


__all__ = ["AgentInstantiationResult", "InstantiateAgentUseCase", "SUPPORTED_ROLES"]
