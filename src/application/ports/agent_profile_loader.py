"""应用层档案加载端口（Story 5-2 — Agent 身份档案加载）

AgentProfileLoader——R2 应用层具体应用端口：按角色寻址档案目录
configs/agents/profiles/{role.value}/ 读取六份固定名 .md 静态资产，
组装 AgentProfile 领域值对象（组合消费 R1 基础端口资产目录语义）。

端口契约：
- 失败统一 AgentProfileError(EXCEPTION_442)：目录缺失/文件缺失/不可读
  （OSError 家族）/编码非法（非 UTF-8）/内容空白/超大小上限（64KB 字节）
- agent_id 透传进 VO（档案归属锚点），role 决定寻址子目录
- 实现见 src/infrastructure/agent_orch/markdown_agent_profile_loader.py
  （Markdown 文件读取与校验严格限定基础设施层）
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from src.domain.entities.agent import AgentRole
from src.domain.value_objects.agent_profile import AgentProfile


@runtime_checkable
class AgentProfileLoader(Protocol):
    """Agent 身份档案加载端口（六档案 .md 静态资产 → AgentProfile VO）。

    实现约束（MarkdownAgentProfileLoader 先例）：
    - 构造注入 profile_root（默认仓库根四级上溯锚定，测试传 tmp_path 覆盖）
    - 文件读取 asyncio.to_thread + 显式 encoding="utf-8"（裸 read_text 依赖
      locale，「非 UTF-8 → 442」契约会环境漂移）
    - 判空主检在实现内（context.profile_path 携带文件名——DC-5 观测锚点）
    """

    async def load(self, role: AgentRole, agent_id: uuid.UUID) -> AgentProfile:
        """加载指定角色的六档案并组装 AgentProfile。

        Args:
            role: Agent 角色（决定寻址目录 profiles/{role.value}/）
            agent_id: 档案归属的 Agent 实例标识（透传进 VO 锚点）

        Returns:
            AgentProfile: 六档案值对象

        Raises:
            AgentProfileError: EXCEPTION_442——目录缺失/文件缺失/不可读/
                编码非法/内容空白/超大小上限
        """
        ...
