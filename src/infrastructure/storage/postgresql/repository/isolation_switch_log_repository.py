"""PostgreSQL 隔离切换日志仓储实现（Story 5.6 — FR-AC-06 审计留痕面）

实现 domain 端口 ``IsolationSwitchLogRepository``（R3 基础设施层实现领域层端口）。

双模式 session（DC-5——照抄 PostgreSQLOutboxRepository 的 Story 4-7 修复形态）:
- 请求路径: ``get_session()`` 命中 ContextVar（HTTP 请求事务内）→ ``add`` + ``flush``
  （不 commit——持久性随外层请求事务）
- fallback 路径: ``get_session()`` 抛 ``RuntimeError``（CLI/后台上下文）→ 经注入
  ``session_factory`` 走 ``session_context()`` 独立会话 commit（CLI isolation-logs
  检索可达性前提——save 与 search 两方法均分派）

⚠️ 防呆: fallback 分派直调 ``session_context.get_session()`` 并 catch
``RuntimeError``（outbox L80 形态）——经 ``PostgreSQLAdapter._session`` property
则会把 RuntimeError 包成 InvalidStateError（``from None``），except 永不命中。

相对 outbox/audit 模板的必做增量——SQLAlchemyError → StorageError 包装链
（save/search 两方法）: 模板均不包装（SQLAlchemy 原生异常透传），本端口契约
声明 ``Raises: StorageError``，坏连接实际抛 ``sqlalchemy.exc.OperationalError``
（与 StorageError 无继承关系）——无包装链则 ``pytest.raises(StorageError)``
断言必红。redis_isolation_repository L94 ``raise StorageError(..., cause=exc)
from exc`` 先例的 PG 版。

Run with:
    poetry run pytest tests/unit/infrastructure/storage/postgresql/\\
        test_isolation_switch_log_repository.py -v
"""

from __future__ import annotations

import logging

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.isolation_switch_log import IsolationSwitchLog
from src.domain.events.enums import IsolationLevel
from src.domain.exceptions import EntityValidationError, StorageError
from src.domain.ports.isolation_switch_log_repository import (
    IsolationSwitchLogQuery,
    IsolationSwitchLogRepository,
    IsolationSwitchLogSearchResult,
)
from src.infrastructure.storage.postgresql.models.isolation_switch_log import (
    IsolationSwitchLogModel,
)
from src.infrastructure.storage.postgresql.session_context import (
    get_session,
    session_context,
)

logger = logging.getLogger(__name__)

__all__ = ["PostgreSQLIsolationSwitchLogRepository"]


class PostgreSQLIsolationSwitchLogRepository(IsolationSwitchLogRepository):
    """隔离切换日志 PG 仓储（双模式 session——请求 ContextVar 优先 + factory fallback）.

    仓储无状态（session 每调用现取），SINGLETON 生命周期无共享态风险
    （DC-11——组合根注册形态）。
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        """构造器.

        Args:
            session_factory: fallback 独立会话工厂（CLI/后台路径——None 时无
                ContextVar session 则 RuntimeError 上抛，配置缺失显式失败）。
        """
        self._session_factory = session_factory

    async def save(self, log: IsolationSwitchLog) -> None:
        """追加写入一条切换日志（请求路径 add+flush / fallback 独立会话 commit）.

        Args:
            log: 日志实体（from_event 构造——六字段审计事实）。

        Raises:
            StorageError: PG 连接/写入故障（SQLAlchemyError 包装链——EXCEPTION_103）。
        """
        model = self._to_model(log)
        try:
            try:
                session = get_session()
            except RuntimeError:
                # 后台/CLI 路径（无请求 session）——经注入工厂走独立 session 写入
                if self._session_factory is None:
                    raise
                await self._save_via_independent_session(model)
                return
            session.add(model)
            await session.flush()
        except (SQLAlchemyError, OSError) as exc:
            # OSError 面: asyncpg connect 阶段的网络故障（ConnectionRefused/
            # Timeout 等）穿透 SQLAlchemy 包装层——实测不包装为 OperationalError
            logger.error("隔离切换日志写入失败: log_id=%s error=%s", log.log_id, exc)
            raise StorageError(f"Failed to save isolation switch log: {exc}", cause=exc) from exc

    async def _save_via_independent_session(self, model: IsolationSwitchLogModel) -> None:
        """fallback 独立会话写入（session_context 编排 commit/rollback/close）."""
        assert self._session_factory is not None  # 调用前已窄化（None 时 save 分支早 return）
        log_id = str(model.log_id)  # session 关闭后 detached——提前捕获
        async with session_context(self._session_factory):
            session = get_session()
            session.add(model)
            await session.flush()
        logger.info("隔离切换日志经独立会话落库（后台路径 fallback）: log_id=%s", log_id)

    async def search(self, query: IsolationSwitchLogQuery) -> IsolationSwitchLogSearchResult:
        """多维检索切换日志（四维 AND 组合 + 分页 + switch_timestamp 降序）.

        Args:
            query: 检索查询（agent_id/时间闭区间/level 双向命中 + offset/limit）。

        Returns:
            强类型结果（items 实体 tuple + total 独立计数——func.count 单查询）。

        Raises:
            StorageError: PG 连接/查询故障（SQLAlchemyError 包装链——EXCEPTION_103）。
        """
        try:
            try:
                session = get_session()
            except RuntimeError:
                # CLI 检索路径（isolation-logs）——search 也必须走 fallback 才可达
                if self._session_factory is None:
                    raise
                assert self._session_factory is not None  # 上一行窄化（None 已 raise）
                async with session_context(self._session_factory):
                    return await self._search_within_context(query)
            return await self._do_search(session, query)
        except (SQLAlchemyError, OSError) as exc:
            # OSError 面: asyncpg connect 阶段网络故障穿透 SQLAlchemy 包装层
            logger.error("隔离切换日志检索失败: error=%s", exc)
            raise StorageError(f"Failed to search isolation switch logs: {exc}", cause=exc) from exc

    async def _search_within_context(self, query: IsolationSwitchLogQuery) -> IsolationSwitchLogSearchResult:
        """fallback 独立会话检索（session_context 作用域内取 session）."""
        session = get_session()
        return await self._do_search(session, query)

    async def _do_search(self, session: AsyncSession, query: IsolationSwitchLogQuery) -> IsolationSwitchLogSearchResult:
        """检索主体（动态条件构建 + count + 分页 + 降序——纯 AND，无 match_any）.

        Args:
            session: 当前可用 AsyncSession（请求路径或 fallback 作用域内）。
            query: 检索查询。

        Returns:
            IsolationSwitchLogSearchResult。
        """
        conditions = []
        if query.agent_id is not None:
            conditions.append(IsolationSwitchLogModel.agent_id == query.agent_id)
        if query.start_time is not None:
            conditions.append(IsolationSwitchLogModel.switch_timestamp >= query.start_time)
        if query.end_time is not None:
            conditions.append(IsolationSwitchLogModel.switch_timestamp <= query.end_time)
        if query.level is not None:
            # level 双向命中（DC-3）: previous 或 target 任一等于该等级——
            # 「切换涉及该等级即命中」，单侧命中漏半边审计面（or_ 两臂皆索引化）
            conditions.append(
                or_(
                    IsolationSwitchLogModel.previous_level == query.level.value,
                    IsolationSwitchLogModel.target_level == query.level.value,
                )
            )

        base = select(IsolationSwitchLogModel)
        count_stmt = select(func.count()).select_from(IsolationSwitchLogModel)
        for condition in conditions:
            base = base.where(condition)
            count_stmt = count_stmt.where(condition)

        total = (await session.execute(count_stmt)).scalar_one()
        # 排序: switch_timestamp 降序 + log_id 次级键——同刻多行（微秒精度可同值）
        # 在 offset 分页下无次级键会跨页重复/丢行（R1-F13 确定性分页）
        items_stmt = (
            base.order_by(IsolationSwitchLogModel.switch_timestamp.desc(), IsolationSwitchLogModel.log_id)
            .offset(query.offset)
            .limit(query.limit)
        )
        models = (await session.execute(items_stmt)).scalars().all()
        return IsolationSwitchLogSearchResult(
            items=tuple(self._to_entity(model) for model in models),
            total=total,
            offset=query.offset,
            limit=query.limit,
        )

    @staticmethod
    def _to_model(log: IsolationSwitchLog) -> IsolationSwitchLogModel:
        """实体 → ORM 模型（枚举取 .value 字符串 / 审批链 tuple→list JSONB 投影）."""
        return IsolationSwitchLogModel(
            log_id=log.log_id,
            agent_id=log.agent_id,
            previous_level=log.previous_level.value,
            target_level=log.target_level.value,
            trigger_reason=log.trigger_reason,
            approval_chain=list(log.approval_chain),
            switch_timestamp=log.switch_timestamp,
            worm_ref=log.worm_ref,
        )

    @staticmethod
    def _to_entity(model: IsolationSwitchLogModel) -> IsolationSwitchLog:
        """ORM 模型 → 实体（等级 value→枚举 / 审批链 list→tuple / **丢弃 created_at**
        ——实体八字段无 created_at，行创建审计列仅 DB 侧，检索投影不传）。

        Raises:
            EntityValidationError: 等级列值不在 ``IsolationLevel`` 枚举域
                （EXCEPTION_242——脏行（直插旁路写入越域值，migration 016 值域
                CHECK 前的存量行）重建枚举的裸 ``ValueError`` 会穿透
                ``(SQLAlchemyError, OSError)`` 包装链违反异常体系契约，且单条
                脏行毒化整页检索——对齐 ``DomainEvent.from_dict`` 畸形 payload
                包装先例，R1-F4）。
        """
        try:
            previous_level = IsolationLevel(model.previous_level)
            target_level = IsolationLevel(model.target_level)
        except ValueError as exc:
            raise EntityValidationError(
                message=(
                    f"日志行等级值越域（previous={model.previous_level!r} target={model.target_level!r}"
                    "——不在 IsolationLevel 枚举域，疑似直插脏行）"
                ),
                context={
                    "log_id": str(model.log_id),
                    "previous_level": str(model.previous_level),
                    "target_level": str(model.target_level),
                },
            ) from exc
        return IsolationSwitchLog(
            log_id=model.log_id,
            agent_id=model.agent_id,
            previous_level=previous_level,
            target_level=target_level,
            trigger_reason=model.trigger_reason,
            approval_chain=tuple(model.approval_chain),
            switch_timestamp=model.switch_timestamp,
            worm_ref=model.worm_ref,
        )
