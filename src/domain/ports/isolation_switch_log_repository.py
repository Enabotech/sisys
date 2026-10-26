"""隔离切换日志仓储端口模块（Story 5.6 — FR-AC-06 审计留痕面）

R1 领域层基础端口：日志持久化与多维检索是领域基础能力（同层先例
IsolationRepository/AgentRepository）。实现类位于 infrastructure 层
（``PostgreSQLIsolationSwitchLogRepository``——异步 ORM 适配 + 双模式
session，DC-5）。

端口面最小（save/search 两方法——追加型日志只增不改，无 update/delete：
防篡改由 PG RLS deny 策略承载）。

Run with:
    poetry run pytest tests/unit/domain/ports/test_isolation_switch_log_repository_port.py -v
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from src.domain.entities.isolation_switch_log import IsolationSwitchLog
from src.domain.events.enums import IsolationLevel
from src.domain.exceptions import EntityValidationError

__all__ = [
    "IsolationSwitchLogQuery",
    "IsolationSwitchLogRepository",
    "IsolationSwitchLogSearchResult",
]


@dataclass(frozen=True)
class IsolationSwitchLogQuery:
    """隔离切换日志多维检索查询（Query Object——多字段组合+分页命中决策规则）.

    四过滤维度（组合语义 AND）+ 分页。全字段 None/默认 = 全量分页返回
    （合法调用）。

    Attributes:
        agent_id: 按 Agent 精确过滤（审计检索不要求 Agent 现存——无 443 守卫，
            与写入面形成对照）。
        start_time: switch_timestamp 闭区间下界（>=）。
        end_time: switch_timestamp 闭区间上界（<=）。
        level: 隔离等级双向命中（previous_level 或 target_level 任一等于该
            等级即命中——DC-3：「切换涉及该等级即命中」，单侧命中会漏半边
            审计面）。
        offset: 分页偏移（默认 0）。
        limit: 分页上限（默认 50，上限 500——防失控全表拉取）。

    Raises:
        EntityValidationError: offset<0 / limit<=0 / limit>500；agent_id 非 UUID
            实例；level 非 ``IsolationLevel`` 枚举实例（str,Enum 混入语义 hash
            穿透——isinstance 先行双条件，5-4 R3-F01 教训的 Query 侧延伸）；
            start_time/end_time 非 datetime 实例或 naive；start_time > end_time
            （EXCEPTION_242——全部边界拒绝）。
    """

    agent_id: uuid.UUID | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    level: IsolationLevel | None = None
    offset: int = 0
    limit: int = 50

    def __post_init__(self) -> None:
        """查询参数守卫（242——分页边界 + 类型/时区/区间拒绝）。"""
        if self.offset < 0:
            raise EntityValidationError(
                message="offset 不能为负",
                context={"offset": self.offset},
            )
        if self.limit <= 0:
            raise EntityValidationError(
                message="limit 必须为正整数",
                context={"limit": self.limit},
            )
        if self.limit > 500:
            raise EntityValidationError(
                message="limit 不能超过 500（防失控全表拉取）",
                context={"limit": self.limit},
            )
        if self.agent_id is not None and not isinstance(self.agent_id, uuid.UUID):
            raise EntityValidationError(
                message=f"agent_id 必须为 UUID 实例（实际类型 {type(self.agent_id).__name__}）",
                context={"agent_id": str(self.agent_id)},
            )
        if self.level is not None and not isinstance(self.level, IsolationLevel):
            # 双条件 isinstance 先行：裸 str "L4" 经 hash 穿透 ``in`` 判定后
            # 深入 PG 实现以 AttributeError 逃逸异常体系（R1-F5）
            raise EntityValidationError(
                message=f"level 必须为 IsolationLevel 枚举实例（实际类型 {type(self.level).__name__}）",
                context={"level": str(self.level)},
            )
        for field_name in ("start_time", "end_time"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, datetime) or value.tzinfo is None):
                raise EntityValidationError(
                    message=f"{field_name} 必须为带时区的 datetime 实例（naive 时间在跨时区部署下过滤语义歧义）",
                    context={field_name: str(value)},
                )
        if self.start_time is not None and self.end_time is not None and self.start_time > self.end_time:
            raise EntityValidationError(
                message="start_time 不能晚于 end_time（反转时间窗以空结果静默呈现会与「该时段确无切换」不可区分）",
                context={"start_time": str(self.start_time), "end_time": str(self.end_time)},
            )


@dataclass(frozen=True)
class IsolationSwitchLogSearchResult:
    """隔离切换日志检索结果（强类型实体 tuple——audit search 返回 dict 是 1.10
    历史形态，新端口用实体，类型安全，DC-3）.

    Attributes:
        items: 命中日志实体（switch_timestamp 降序——最新在前）。
        total: 独立计数总数（非 items 长度——分页语义）。
        offset: 本次查询偏移（回显）。
        limit: 本次查询上限（回显）。
    """

    items: tuple[IsolationSwitchLog, ...]
    total: int
    offset: int
    limit: int


@runtime_checkable
class IsolationSwitchLogRepository(Protocol):
    """隔离切换日志仓储端口（R1 领域层基础端口——追加写入 + 多维检索）.

    实现契约（DC-5——双模式 session）: 两方法均「请求 ContextVar session 优先
    （HTTP 事务内 add+flush / 同事务查询）+ RuntimeError 时经注入
    ``session_factory`` 走 ``session_context()`` 独立会话 commit（CLI/后台
    路径——CLI isolation-logs 检索可达性前提）」分派。⚠️ 实现方 fallback 分派
    必须直调 ``session_context.get_session()`` 并 catch ``RuntimeError``
    （经 ``PostgreSQLAdapter._session`` property 则 except 永不命中——RuntimeError
    被包成 InvalidStateError ``from None``）。
    """

    async def save(self, log: IsolationSwitchLog) -> None:
        """追加写入一条切换日志（日志只增不改——RLS deny UPDATE/DELETE 保证）.

        Args:
            log: 日志实体（from_event 构造——六字段审计事实）。

        Raises:
            StorageError: PG 连接/写入故障（EXCEPTION_103——实现方须以
                「捕获数据库驱动原生异常 → ``raise StorageError(...) from exc``
                包装链」保证该契约，否则坏连接抛出的驱动原生异常与
                StorageError 无继承关系）。
        """
        ...

    async def search(self, query: IsolationSwitchLogQuery) -> IsolationSwitchLogSearchResult:
        """多维检索切换日志（按 AGENT/时间范围/隔离等级 + 分页 + 排序）.

        检索无 443 守卫（Agent TTL 过期后历史日志仍可查——审计要求）。
        排序固定 switch_timestamp 降序（最新在前）。

        Args:
            query: 检索查询（四维组合 AND + offset/limit 分页）。

        Returns:
            IsolationSwitchLogSearchResult: 强类型结果（items 实体 tuple +
                total 独立计数）。

        Raises:
            StorageError: PG 连接/查询故障（EXCEPTION_103——同 save 包装链）。
        """
        ...
