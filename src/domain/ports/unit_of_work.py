"""领域层工作单元模块

用于统一事务边界，保证业务操作与 Outbox 写入原子性
仅定义抽象接口，无外部依赖

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

if TYPE_CHECKING:
    from types import TracebackType


@runtime_checkable
class UnitOfWork(Protocol):
    """抽象工作单元接口

    定义事务边界：begin(), commit(), rollback(), close()
    支持异步上下文管理器协议

    Attributes:
        session: 当前事务的 session 对象
    """

    @property
    def session(self) -> object:
        """获取当前事务的 session

        EventHandler 使用此属性提取 session 传入各 Repository
        """
        ...

    async def begin(self) -> None:
        """开始事务"""
        ...

    async def commit(self) -> None:
        """提交事务"""
        ...

    async def rollback(self) -> None:
        """回滚事务"""
        ...

    async def begin_nested(self) -> None:
        """创建 savepoint（嵌套事务）"""
        ...

    async def __aenter__(self) -> Self:
        """异步上下文管理器入口"""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """异步上下文管理器出口

        规则：
        - 异常：rollback
        - 正常：仅在未手动 commit/rollback 时才 commit
        - 不负责 close session（由 SessionMiddleware 负责）
        - 返回 False：不吞没异常
        """
        ...


@runtime_checkable
class UnitOfWorkFactory(Protocol):
    """UnitOfWork 工厂 Protocol

    用于 DI 容器注册。EventHandler 通过 resolve("uow_factory") 获取工厂，
    然后调用 factory() 创建新的 UnitOfWork 实例

    设计原因（D2 决策）：
    - PortSpec.interface 类型为 Type，Callable[[], UnitOfWork] 不合法
    - 须定义专门的 Protocol 满足 PortSpec 类型约束
    - 工厂每次调用返回新实例（TRANSIENT 生命周期）
    """

    def __call__(self) -> UnitOfWork:
        """创建新的 UnitOfWork 实例

        返回：
            新的 UnitOfWork 实例
        """
        ...
