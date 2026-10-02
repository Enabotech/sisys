"""领域层辩论会话仓储端口模块

Story 4.5 — 红蓝辩论机制基础：辩论会话聚合根的仓储抽象。

设计决策：**不继承 L2RdbPort**
原因：本 Story 仅有 InMemory 实现（MVP 无历史辩论查询需求，PG 持久化随
Epic 10 审计需求落地），独立 Protocol 即可覆盖 save / get_by_id 两方法
（4.4 SandboxSessionRepositoryPort 同款先例）；主键虽为 UUID，但无 PG
实现时引入泛型基座无收益（Simplicity First）。

参考：CLAUDE.md §4 端口查询参数决策规则——单字段标识查找用直接参数。

本端口无专属异常（save 前置 validate 抛 EntityValidationError 242 属实体
不变量，不构成仓储层异常契约）。
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from src.domain.entities.debate_session import DebateSession


@runtime_checkable
class DebateSessionRepositoryPort(Protocol):
    """辩论会话仓储端口（领域层，Story 4.5 新增）

    基础操作（按 debate_id UUID 主键索引）：
    - save: 先 validate 再幂等覆盖（无版本冲突检测，V1 CAS 预留）
    - get_by_id: 主键查找，不存在返回 None
    """

    async def save(self, session: DebateSession) -> DebateSession:
        """保存辩论会话（insert or update，幂等覆盖）

        Args:
            session: 辩论会话聚合根实例

        Returns:
            保存后的实体（对齐既有 5 个 InMemory 仓储 save -> Entity 先例）

        Raises:
            EntityValidationError: 实体不变量违反（save 前置 validate）
        """
        ...

    async def get_by_id(self, debate_id: uuid.UUID) -> DebateSession | None:
        """按辩论会话 ID 查询（主键查找）

        Args:
            debate_id: 辩论会话 ID

        Returns:
            DebateSession 实例，不存在则返回 None
        """
        ...


__all__ = ["DebateSessionRepositoryPort"]
