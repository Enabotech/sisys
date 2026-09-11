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
    """

    pk_column: str = "execution_id"

    def __init__(self) -> None:
        super().__init__(ToolExecutionModel)

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
