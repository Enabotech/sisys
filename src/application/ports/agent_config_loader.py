"""应用层 Agent 配置加载端口模块（Story 5-1 — CEO Agent 实例化 MVP）

Agent 基础配置加载的应用层端口（R2 具体应用端口）：抽象「按角色加载
配置资产 → 构造领域值对象」能力，YAML 解析等具体技术下沉 infrastructure
（YamlAgentConfigLoader 实现，六边形依赖倒置）。

本端口无专属异常契约——加载失败统一抛 AgentConfigError(EXCEPTION_440，
agent 子域），见 src/domain/exceptions/agent_exceptions.py。

Run with:
    经组合根 resolve("agent_config_loader") 获取实现
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.entities.agent import AgentRole
from src.domain.value_objects.agent_config import AgentConfig


@runtime_checkable
class AgentConfigLoader(Protocol):
    """Agent 基础配置加载器端口（应用层，Story 5-1 新增）

    按 role 加载对应配置资产并构造 AgentConfig 值对象。
    配置资产身份键为 identity.role（配置文件名 {role.value}_agent.yaml）。
    """

    async def load(self, role: AgentRole) -> AgentConfig:
        """加载指定角色的基础配置

        Args:
            role: Agent 角色（当前 MVP 仅 CEO 开放，角色守卫在用例层）

        Returns:
            AgentConfig 领域值对象（已归一化与自校验）

        Raises:
            AgentConfigError: 配置文件缺失 / YAML 解析失败 / 必填字段无效 /
                role 与配置不匹配（EXCEPTION_440）
        """
        ...


__all__ = ["AgentConfigLoader"]
