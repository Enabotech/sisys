"""UserRepositoryPort 单元测试。

验证 UserRepositoryPort 接口定义正确。
遵循六边形架构：领域层零依赖，仅使用 ABC + 标准库。

Reference: Story 1.9 RBAC Permission Management
"""

from __future__ import annotations

from abc import ABC
from uuid import UUID

from src.domain.ports.user_repository import UserRepositoryPort


class TestUserRepositoryPortInterface:
    """验证 UserRepositoryPort 接口定义正确。"""

    def test_user_repository_port_is_abc(self) -> None:
        """验证 UserRepositoryPort 是 ABC。"""
        assert issubclass(UserRepositoryPort, ABC)

    def test_port_has_get_by_username_method(self) -> None:
        """验证 get_by_username 方法存在。"""
        assert hasattr(UserRepositoryPort, "get_by_username")

    def test_port_has_get_by_id_method(self) -> None:
        """验证 get_by_id 方法存在。"""
        assert hasattr(UserRepositoryPort, "get_by_id")

    def test_get_by_username_is_abstract(self) -> None:
        """验证 get_by_username 是抽象方法。"""
        method = getattr(UserRepositoryPort, "get_by_username")
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_get_by_id_is_abstract(self) -> None:
        """验证 get_by_id 是抽象方法。"""
        method = getattr(UserRepositoryPort, "get_by_id")
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_fully_implemented_subclass_can_be_instantiated(self) -> None:
        """验证完全实现抽象方法的子类可以实例化。"""
        from src.domain.entities.user import User

        class ConcreteUserRepository(UserRepositoryPort):
            async def get_by_username(self, username: str) -> User | None:
                return None

            async def get_by_id(self, user_id: UUID) -> User | None:
                return None

        repo = ConcreteUserRepository()
        assert repo is not None
        assert isinstance(repo, UserRepositoryPort)
