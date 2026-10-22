"""领域层 EIP 隔离状态实体模块（Story 5.4 — EIP 弹性隔离协议基础）

Agent EIP 隔离状态聚合（独立于 Agent 实体的协议状态——Story 5.4 DC-1）:
- 每个 Agent 一条，Redis 键空间 sisys:isolation:{agent_id}（IsolationRepository）
- 有独立生命周期（切换/过期）与独立读写面（隔离检查入口 P95 计时锚），
  与 Agent 实体状态机解耦（5-1「复用不修改」纪律——Agent 实体不加隔离字段）
- 非 frozen dataclass（对齐 Agent 实体可变状态机形态——有切换生命周期）

领域行为内聚（DC-5）: 等级合法性校验统一在本类（initialize/switch_to 两入口），
服务层与 CLI 不重复校验（CLI 只做字符串→枚举转换守卫）。

等级守卫双条件（R3-F01 实测定谳）: str,Enum 混入语义下 hash("L3")==hash(L3_SOFT)，
合法值域裸 str 经 `in frozenset` 判定为 True——单 `not in` 守卫拦不住（会放行
到 242/类型污染）；`not isinstance(level, IsolationLevel) or level not in
MVP_ALLOWED_LEVELS` 双条件中 isinstance 先行是唯一可靠子类型防线
（实测 Python 3.11.15）。switch_to 路径尤其关键: dataclass 属性赋值不触发
__post_init__，裸 str 穿透单守卫后 self.current_level = target_level 即
静默类型污染持久化。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from src.domain.events.enums import IsolationLevel
from src.domain.exceptions import EntityValidationError, IsolationLevelNotSupportedError


def _mvp_allowed_levels() -> frozenset[IsolationLevel]:
    """MVP 允许等级集（方法内延迟 import——打破包初始化环）。

    模块级 import 会构成包互嵌环（实证 value_objects-first 入口: isolation_policy
    部分初始化 → events/__init__ L7 archive_events → entities/__init__ → 本模块
    回头 import 未完成的 isolation_policy → ImportError；entities-first 入口不断环）。
    MVP_ALLOWED_LEVELS 的 SSOT 在 value_objects/isolation_policy.py（策略域归属），
    运行时调用时各包均已完成初始化，sys.modules 命中零开销。
    """
    from src.domain.value_objects.isolation_policy import MVP_ALLOWED_LEVELS

    return MVP_ALLOWED_LEVELS


def _supported_level_values() -> tuple[str, ...]:
    """446 异常 context 的支持等级清单（从 MVP_ALLOWED_LEVELS 真派生）。

    按枚举定义序（L4→L1）过滤迭代——定义序天然稳定（区别于 frozenset 迭代序
    不稳定），与 446 docstring「从 MVP_ALLOWED_LEVELS 派生，勿硬编码」承诺一致；
    V2 开放 L1 时仅改 MVP_ALLOWED_LEVELS 一处即可全链生效。仅在异常 raise 路径
    调用（延迟 import 同 _mvp_allowed_levels——模块级 import 会断包初始化环）。
    """
    mvp = _mvp_allowed_levels()
    return tuple(level.value for level in IsolationLevel if level in mvp)


@dataclass
class IsolationState:
    """Agent EIP 隔离状态聚合（协议状态——独立于 Agent 实体）

    Attributes:
        agent_id: 归属 Agent 唯一标识
        current_level: 当前隔离等级
        initialized_at: 初始化时刻（UTC）
        updated_at: 最近变更时刻（UTC——no-op 不推进）
        last_trigger_reason: 最近触发原因（初始化为 "initial_default"）
    """

    agent_id: uuid.UUID
    current_level: IsolationLevel
    initialized_at: datetime
    updated_at: datetime
    last_trigger_reason: str

    def __post_init__(self) -> None:
        """不变量校验（非配置实体——失败抛 EntityValidationError 242）。

        绕过工厂直构造的防御面（initialize/switch_to 工厂方法另有 446 等级守卫）。

        Raises:
            EntityValidationError: agent_id 非 UUID / current_level 非枚举实例 /
                last_trigger_reason 空（EXCEPTION_242）
        """
        if not isinstance(self.agent_id, uuid.UUID):
            raise EntityValidationError(
                message=f"agent_id 必须为 UUID 实例（实际类型 {type(self.agent_id).__name__}）",
                context={"agent_id": str(self.agent_id)},
            )
        if not isinstance(self.current_level, IsolationLevel):
            raise EntityValidationError(
                message=f"current_level 必须为 IsolationLevel 枚举实例（实际类型 {type(self.current_level).__name__}）",
                context={"current_level": str(self.current_level)},
            )
        if not isinstance(self.last_trigger_reason, str) or not self.last_trigger_reason.strip():
            raise EntityValidationError(
                message="last_trigger_reason 不能为空",
                context={"last_trigger_reason": self.last_trigger_reason},
            )

    @classmethod
    def initialize(cls, agent_id: uuid.UUID, level: IsolationLevel, *, now: datetime | None = None) -> IsolationState:
        """工厂方法: 以默认等级初始化隔离状态

        Args:
            agent_id: 归属 Agent 唯一标识（调用方保证 agent 已持久化——本方法
                无 443 前置守卫，前置条件见 IsolationManagementServicePort docstring）
            level: 初始等级（真源 AgentConfig.default_isolation_level）
            now: 时间注入（默认 datetime.now(UTC)——单 now 双用保证
                initialized_at == updated_at 严格相等）

        Returns:
            初始化完成的 IsolationState（last_trigger_reason=="initial_default"）

        Raises:
            IsolationLevelNotSupportedError: 非法等级值或非枚举实例（EXCEPTION_446
                ——双条件守卫: isinstance 先行拦裸 str hash 混入穿透，再查 MVP 白名单
                拦 L1 融合态）
        """
        if not isinstance(level, IsolationLevel) or level not in _mvp_allowed_levels():
            raise IsolationLevelNotSupportedError(
                level=str(getattr(level, "value", level)),
                supported_levels=_supported_level_values(),
            )
        moment = now or datetime.now(UTC)
        return cls(
            agent_id=agent_id,
            current_level=level,
            initialized_at=moment,
            updated_at=moment,
            last_trigger_reason="initial_default",
        )

    def switch_to(
        self,
        target_level: IsolationLevel,
        trigger_reason: str,
        *,
        now: datetime | None = None,
    ) -> bool:
        """切换隔离等级（领域行为——等级合法性校验内聚本方法）

        Args:
            target_level: 目标等级
            trigger_reason: 切换原因（非空——用户显式请求的语义必填）
            now: 时间注入（默认 datetime.now(UTC)）

        Returns:
            True=已切换（三字段更新）；False=同等级 no-op（零变更——幂等语义，
            「切换」事件语义要求前后等级相异，TTL 不刷新）

        Raises:
            IsolationLevelNotSupportedError: 非法等级（EXCEPTION_446——双条件
                守卫，switch_to 路径是类型污染防线主阵地: dataclass 赋值不触发
                __post_init__，isinstance 先行封死裸 str 穿透）
            EntityValidationError: trigger_reason 空/空白（EXCEPTION_242——
                原因缺失是实体不变量问题，与等级非法 446 语义区分）
        """
        if not isinstance(target_level, IsolationLevel) or target_level not in _mvp_allowed_levels():
            raise IsolationLevelNotSupportedError(
                level=str(getattr(target_level, "value", target_level)),
                supported_levels=_supported_level_values(),
            )
        if not isinstance(trigger_reason, str) or not trigger_reason.strip():
            raise EntityValidationError(
                message="trigger_reason 不能为空（切换必须有原因）",
                context={"trigger_reason": trigger_reason},
            )
        if target_level == self.current_level:
            return False  # no-op: 零变更（不推进 updated_at 不改写原因——幂等）
        self.current_level = target_level
        self.updated_at = now or datetime.now(UTC)
        self.last_trigger_reason = trigger_reason.strip()
        return True


__all__ = ["IsolationState"]
