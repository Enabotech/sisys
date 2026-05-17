"""SISYS 领域层用户仓储端口模块

领域层接口，定义用户数据访问的契约
遵循六边形架构：领域层零依赖，仅使用标准库

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.entities.user import User


@runtime_checkable
class UserRepositoryPort(Protocol):
    """用户仓储端口（领域层定义，仅使用标准库）"""

    async def get_by_username(self, username: str) -> User | None:
        """根据用户名获取用户

        Args:
            username: 用户名

        Returns:
            User 领域实体，或 None（用户不存在）
        """

    async def get_by_id(self, user_id: UUID) -> User | None:
        """根据 ID 获取用户

        Args:
            user_id: 用户 UUID

        Returns:
            User 领域实体，或 None（用户不存在）
        """
