"""基础设施层 PostgreSQL ToolExecution 仓储(SQLAlchemy ORM 风格)

实现 ToolExecutionRepositoryPort(Story 4.1a + 4.3 后续技术债清理)：
- 继承 PostgreSQLAdapter[ToolExecution, ToolExecutionModel]
- 状态机 + 乐观锁 CAS（save_with_state_version）
- 证据包字段 input_hash / rule_version / confidence（L2_rdb 结构化）
- L4 MinIO 引用 evidence_storage_key（保留字段，本期不写 L4）
- 通过 _to_entity / _to_model 隔离领域层与 ORM 层

设计依据：Story 4.3 后续技术债清理(路径 2: SQLAlchemy ORM 风格)
- 与 archive_repository.py / document_repository.py 模式一致
- 通过 ContextVar 获取 AsyncSession（非构造器注入）
- 与原 asyncpg 直连实现 PostgreSQLToolExecutionRepository(pool=...) 行为等价

迁移路径：保留 AsyncpgPostgreSQLToolExecutionRepository 作为向后兼容实现，
新代码统一使用本 SQLAlchemy ORM 实现。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select

from src.domain.entities.tool_execution import ToolExecution, ToolExecutionState
from src.domain.exceptions.business_exceptions import EntityStateTransitionError
from src.domain.ports.tool_execution_repository import ToolExecutionQuery
from src.infrastructure.storage.postgresql.models.tool_execution import (
    ToolExecutionModel,
)
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import (
    PostgreSQLAdapter,
)

logger = logging.getLogger(__name__)


class PostgreSQLToolExecutionRepository(PostgreSQLAdapter[ToolExecution, ToolExecutionModel]):
    """ToolExecution 仓储(SQLAlchemy ORM 风格)

    关键设计:
    - ContextVar session 自动注入(由 composition_root 配置 session_context)
    - 乐观锁 CAS：save_with_state_version 用 atomic UPDATE 实现 state_version+1
    - ToolExecutionState 枚举 ↔ 字符串值(防 DB 漂移)
    - save 的后台路径 fallback（技术债清偿 A 类——outbox 同构）：无请求
      session 时经注入 session_factory 独立会话写入——`_persist_execution`
      失败态持久化在后台/CLI 路径不再 RuntimeError 丢失（HTTP 失败路径主事务
      回滚连带的「形态②」见 deferred-work 策略注记）
    """

    pk_column: str = "execution_id"

    def __init__(self, session_factory: Any | None = None) -> None:
        """初始化仓储.

        Args:
            session_factory: 独立会话工厂（后台路径 fallback 用——组合根注入
                async_sessionmaker；None 保持既有 RuntimeError 显式失败语义）
        """
        super().__init__(ToolExecutionModel)
        self._session_factory = session_factory

    async def save(self, entity: ToolExecution) -> ToolExecution:
        """保存实体（请求 session 优先；无请求 session 时 fallback 独立写入）.

        Raises:
            RuntimeError: 无请求 session 且未注入 session_factory（无 fallback
                能力——与 outbox 仓储同款显式失败而非静默丢失）
        """
        from src.infrastructure.storage.postgresql.session_context import get_session

        try:
            get_session()
        except RuntimeError:
            # 后台/CLI 路径（无请求 session）——仅捕获此形态，其他 RuntimeError
            # （连接池等）按原语义传播
            if self._session_factory is None:
                raise
            return await self._save_via_independent_session(entity)
        return await super().save(entity)

    async def _save_via_independent_session(self, entity: ToolExecution) -> ToolExecution:
        """经 session_context 独立会话写入（outbox fallback 先例同款）."""
        from typing import cast

        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from src.infrastructure.storage.postgresql.session_context import session_context

        factory = cast("async_sessionmaker[AsyncSession]", self._session_factory)
        async with session_context(factory):
            # session_context 内已 set——基类 save 经 get_session 取到独立会话
            saved = await PostgreSQLAdapter.save(self, entity)
        logger.info(
            "ToolExecution 经独立会话落库（后台路径 fallback）: execution_id=%s",
            entity.execution_id,
        )
        return saved

    # ------------------------------------------------------------------
    # 实体/模型转换
    # ------------------------------------------------------------------

    def _to_entity(self, model: ToolExecutionModel) -> ToolExecution:
        """将 ORM 模型转换为领域实体

        Args:
            model: SQLAlchemy ToolExecutionModel 实例

        Returns:
            ToolExecution 领域实体
        """
        try:
            state = ToolExecutionState(model.state)
        except ValueError:
            logger.warning(
                "Invalid state %r in DB for execution %s, defaulting to IDLE",
                model.state,
                model.execution_id,
            )
            state = ToolExecutionState.IDLE
        return ToolExecution(
            execution_id=model.execution_id,
            tenant_id=model.tenant_id,
            tool_id=model.tool_id,
            tool_version=model.tool_version,
            state=state,
            started_at=model.started_at,
            completed_at=model.completed_at,
            retry_count=model.retry_count,
            failure_reason=model.failure_reason,
            state_version=model.state_version,
        )

    def _to_model(self, entity: ToolExecution) -> ToolExecutionModel:
        """将领域实体转换为 ORM 模型

        Args:
            entity: ToolExecution 领域实体

        Returns:
            SQLAlchemy ToolExecutionModel 实例
        """
        return ToolExecutionModel(
            execution_id=entity.execution_id,
            tenant_id=entity.tenant_id,
            tool_id=entity.tool_id,
            tool_version=entity.tool_version,
            state=entity.state.value,
            started_at=entity.started_at,
            completed_at=entity.completed_at,
            retry_count=entity.retry_count,
            failure_reason=entity.failure_reason,
            state_version=entity.state_version,
        )

    # ------------------------------------------------------------------
    # ToolExecutionRepositoryPort 实现
    # ------------------------------------------------------------------

    def _apply_filters(self, stmt: Any, query: ToolExecutionQuery) -> Any:
        """应用 ToolExecutionQuery 过滤条件到 statement

        Args:
            stmt: SQLAlchemy select/count statement
            query: 查询条件

        Returns:
            添加过滤条件后的 statement
        """
        if query.tenant_id is not None:
            stmt = stmt.where(ToolExecutionModel.tenant_id == query.tenant_id)
        if query.tool_id is not None:
            stmt = stmt.where(ToolExecutionModel.tool_id == query.tool_id)
        if query.state is not None:
            stmt = stmt.where(ToolExecutionModel.state == query.state.value)
        if query.started_after is not None:
            stmt = stmt.where(ToolExecutionModel.started_at >= query.started_after)
        if query.started_before is not None:
            stmt = stmt.where(ToolExecutionModel.started_at <= query.started_before)
        return stmt

    async def list_by_query(self, query: ToolExecutionQuery) -> list[ToolExecution]:
        """通过 Query Object 查询列表

        Args:
            query: 查询条件

        Returns:
            符合条件的列表（按 started_at DESC + offset/limit）
        """
        stmt = select(ToolExecutionModel)
        stmt = self._apply_filters(stmt, query)
        stmt = stmt.order_by(ToolExecutionModel.started_at.desc()).offset(query.offset).limit(query.limit)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def count(self, query: ToolExecutionQuery | None = None) -> int:
        """统计符合条件数量

        Args:
            query: 查询条件(None 时统计全量,兼容父类 PostgreSQLAdapter.count() 无参签名)

        Returns:
            数量
        """
        if query is None:
            query = ToolExecutionQuery()
        stmt = select(func.count()).select_from(ToolExecutionModel)
        stmt = self._apply_filters(stmt, query)
        result = await self._session.execute(stmt)
        return int(result.scalar() or 0)

    async def save_with_state_version(
        self,
        execution: ToolExecution,
        expected_state_version: int,
    ) -> ToolExecution:
        """乐观锁 CAS 保存（原子 state_version 自增）

        与原 asyncpg 实现行为等价：
        1. SELECT 当前 state_version
        2. 不存在 → EntityStateTransitionError("execution not found")
        3. 版本不匹配 → EntityStateTransitionError("Optimistic lock conflict")
        4. UPDATE state_version = state_version + 1 WHERE state_version = expected

        Args:
            execution: 待保存实体
            expected_state_version: 调用方读到的 state_version(用于乐观锁)

        Returns:
            保存后的实体(state_version 自增 1)

        Raises:
            EntityStateTransitionError: 执行不存在或版本冲突
        """
        # 先查询当前 state_version(同事务内)
        current = await self.get_by_id(execution.execution_id)
        if current is None:
            raise EntityStateTransitionError(
                entity_type="ToolExecution",
                entity_id=str(execution.execution_id),
                from_status="UNKNOWN",
                to_status=execution.state.name,
                message="execution not found in repository",
            )
        if current.state_version != expected_state_version:
            raise EntityStateTransitionError(
                entity_type="ToolExecution",
                entity_id=str(execution.execution_id),
                from_status="UNKNOWN",
                to_status=execution.state.name,
                message=(
                    f"Optimistic lock conflict: expected state_version={expected_state_version}, actual={current.state_version}"
                ),
            )

        # 直接 UPDATE 单条(state_version 自增 1)
        from sqlalchemy import update

        new_version = expected_state_version + 1
        stmt = (
            update(ToolExecutionModel)
            .where(
                ToolExecutionModel.execution_id == execution.execution_id,
                ToolExecutionModel.state_version == expected_state_version,
            )
            .values(
                state=execution.state.value,
                completed_at=execution.completed_at,
                retry_count=execution.retry_count,
                failure_reason=execution.failure_reason,
                state_version=new_version,
                updated_at=func.now(),
            )
        )
        result = await self._session.execute(stmt)
        rowcount = getattr(result, "rowcount", None) or 0
        if rowcount != 1:  # pragma: no cover
            # 极端并发场景:UPDATE 命中 0 行(状态已被其他事务修改)
            raise EntityStateTransitionError(
                entity_type="ToolExecution",
                entity_id=str(execution.execution_id),
                from_status="UNKNOWN",
                to_status=execution.state.name,
                message="Optimistic lock conflict: state_version changed concurrently",
            )
        await self._session.flush()
        # 标记内存中实体的 state_version 已更新
        execution.state_version = new_version
        return execution


__all__ = [
    "PostgreSQLToolExecutionRepository",
]
