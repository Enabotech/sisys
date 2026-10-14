"""领域层 Agent 基础配置值对象模块（Story 5-1 — CEO Agent 实例化 MVP）

CEO Agent 基础配置的领域值对象：frozen dataclass，零外部依赖
（仅标准库 + AgentRole 枚举——YAML 解析属 infrastructure 职责，
核心域设计 §17.3.6 的 AgentConfig(BaseModel) 层归属偏离见 Story D-2）。

自校验契约：role 合法、必填非空（falsy 判空——空串/空 tuple 均拦截）、
state_ttl 范围 60~2592000（含端点）。校验失败抛 AgentConfigError
（EXCEPTION_440）——「配置资产缺陷」语义与 EntityValidationError(242)
「实体不变量违反」分码监控（VO 内抛子域异常先例：document_metadata.py）。

TTL 契约：state_ttl 默认 86400 是唯一默认值真源——仓储 save(agent, ttl)
签名无默认值，由用例从本值对象显式传入（避免双真源，DC-8）。
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.entities.agent import AgentRole
from src.domain.exceptions import AgentConfigError

# Agent 状态 TTL 闭区间边界（秒）：60 秒 ~ 30 天（范围数字对齐 RedisSnapshotStore.set_ttl，
# 异常类型为 AgentConfigError(440) 而非 ValidationError(201)——仅对齐范围不对齐异常类型，DC-8）
STATE_TTL_MIN_SECONDS = 60
STATE_TTL_MAX_SECONDS = 2592000


@dataclass(frozen=True)
class AgentConfig:
    """Agent 基础配置值对象

    来源：configs/agents/{role}_agent.yaml 经 AgentConfigLoader 端口加载构造
    （YAML 字段映射在 infrastructure 加载器完成，本值对象只承载已归一化的值）。

    Attributes:
        role: Agent 角色（枚举）
        name: 显示名称（如 "CEO Agent"）
        description: 角色描述
        version: 配置资产版本（如 "1.0.0"），写入 AgentInstantiated.config_version
        responsibilities: 职责清单（非空 tuple）
        domain_knowledge: 领域知识清单（非空 tuple）
        preferred_model: 偏好模型名（纯 str 预留，本 Story 不引用 LLMConfig 类型——
            其无该字段；5.3 引擎消费时映射 LLMConfig.model；空串归一化为 None）
        state_ttl: Agent 状态 TTL 秒（闭区间 60~2592000，默认 86400）
        default_isolation_level: 默认 EIP 隔离等级（5.4 消费，本 Story 仅承载）
    """

    role: AgentRole
    name: str
    description: str
    version: str
    responsibilities: tuple[str, ...]
    domain_knowledge: tuple[str, ...]
    preferred_model: str | None
    state_ttl: int = 86400
    default_isolation_level: str = "L4"

    def __post_init__(self) -> None:
        """自校验与归一化（配置资产缺陷语义，抛 AgentConfigError 440）"""
        role = self.role if isinstance(self.role, AgentRole) else None
        if role is None:
            raise AgentConfigError(role=str(self.role), reason="role 必须为 AgentRole 枚举实例")

        def _fail(reason: str) -> None:
            raise AgentConfigError(role=role.value, reason=reason, message=reason)

        # 必填非空：falsy 判空（非 is None）——空白串与空 tuple 均拦截；
        # 空职责/知识清单无下游防线（Agent.validate() 不校验非空），本 VO 是运行时
        # 唯一防线（mypy src 门禁为编译期另一道防线）
        if not self.name or not self.name.strip():
            _fail("name 不能为空")
        if not self.description or not self.description.strip():
            _fail("description 不能为空")
        if not self.version or not self.version.strip():
            _fail("version 不能为空")
        # tuple 类型守卫先于判空：truthy 标量（如 str）越过 falsy 判空后会被用例层
        # list() 逐字符静默展开（静默数据损坏——加载器对同款陷阱显式设防，VO 补齐）
        if not isinstance(self.responsibilities, tuple):
            _fail("responsibilities 必须为 tuple（字符串元组）")
        if not isinstance(self.domain_knowledge, tuple):
            _fail("domain_knowledge 必须为 tuple（字符串元组）")
        if not self.responsibilities:
            _fail("responsibilities 不能为空")
        if not self.domain_knowledge:
            _fail("domain_knowledge 不能为空")

        # state_ttl 类型与闭区间范围（60~2592000，含端点）
        if isinstance(self.state_ttl, bool) or not isinstance(self.state_ttl, int):
            _fail("state_ttl 必须为整数")
        if not STATE_TTL_MIN_SECONDS <= self.state_ttl <= STATE_TTL_MAX_SECONDS:
            _fail(f"state_ttl 必须在 {STATE_TTL_MIN_SECONDS}~{STATE_TTL_MAX_SECONDS} 秒范围内（实际 {self.state_ttl}）")

        # preferred_model 空串归一化为 None（与 YAML null 等价，消费方只见 None | str 两态）
        if self.preferred_model == "":
            object.__setattr__(self, "preferred_model", None)


__all__ = ["AgentConfig", "STATE_TTL_MIN_SECONDS", "STATE_TTL_MAX_SECONDS"]
