"""隔离切换日志实体模块（Story 5.6 — FR-AC-06 审计留痕面）

隔离等级切换的追加型审计事实（append-only log）——FR-AC-06 六要素的领域载体：
AGENT ID（agent_id）、时间戳（switch_timestamp——单钟纪律，取事件切换时刻）、
原隔离等级（previous_level）、目标隔离等级（target_level）、触发原因
（trigger_reason）、审批链（approval_chain——tuple 不可变形态）。

形态决策（DC-1）:
- ``@dataclass(frozen=True)`` 不可变——追加型日志事实（AuditLog 先例；与
  IsolationState 可变聚合对照——日志只增不改，防篡改由实体不变量 + PG RLS
  + CheckConstraint 双层防线承载）
- ``from_event`` 是唯一生产构造通道（``IsolationLevelSwitched`` 事件六字段
  payload = 5-4 钉明的数据源契约，映射零加工——保证日志与事件双投影一致）；
  log_id 自铸 UUID4；approval_chain list→tuple 冻结拷贝
- ``worm_ref`` nullable 预留（OD-1——MinIO WORM 24h 归档管线归 V1 Story 13-4）

Run with:
    poetry run pytest tests/unit/domain/entities/test_isolation_switch_log.py -v
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.domain.events.enums import IsolationLevel
from src.domain.events.isolation_events import IsolationLevelSwitched
from src.domain.exceptions import EntityValidationError


@dataclass(frozen=True)
class IsolationSwitchLog:
    """隔离切换日志实体（frozen——追加型审计事实）.

    六字段与 ``IsolationLevelSwitched`` 事件 payload 一一对应（from_event 零加工
    映射）；``log_id`` 自铸、``worm_ref`` 预留 nullable。

    Attributes:
        log_id: 日志唯一标识（UUID4 自铸——每条日志独立审计事实）。
        agent_id: 目标 Agent 实例标识。
        previous_level: 原隔离等级（切换前）。
        target_level: 目标隔离等级（切换后——等级即协作状态语义，OD-2）。
        trigger_reason: 触发原因（非空文本——MVP 用户显式请求通道）。
        approval_chain: 审批链（tuple[str, ...] 不可变——空 tuple 是用户请求
            通道无审批的真实事实记录，非字段缺失）。
        switch_timestamp: 切换时刻（单钟纪律——取事件 switch_timestamp 而非
            event.timestamp，事件时刻=状态变更时刻）。
        worm_ref: WORM 归档引用（预留 None——OD-1，V1 Story 13-4 归档管线接线）。
    """

    log_id: uuid.UUID
    agent_id: uuid.UUID
    previous_level: IsolationLevel
    target_level: IsolationLevel
    trigger_reason: str
    approval_chain: tuple[str, ...]
    switch_timestamp: datetime
    worm_ref: str | None = None

    @classmethod
    def from_event(cls, event: IsolationLevelSwitched) -> IsolationSwitchLog:
        """从切换事件构造日志实体（事件 payload 单一真源——DC-1）.

        六字段零加工映射；approval_chain 经 ``tuple()`` 冻结拷贝（防御性拷贝
        ——源 list 后续变异不影响实体）；switch_timestamp 取事件的
        ``switch_timestamp`` 字段（单钟纪律）。

        Args:
            event: ``IsolationLevelSwitched`` 领域事件（5-4 交付——六字段
                payload 已覆盖 FR-AC-06 全部要求）。

        Returns:
            IsolationSwitchLog: 新建日志实体（log_id 自铸 UUID4、worm_ref=None）。
        """
        return cls(
            log_id=uuid.uuid4(),
            agent_id=event.agent_id,
            previous_level=event.previous_level,
            target_level=event.target_level,
            trigger_reason=event.trigger_reason,
            approval_chain=tuple(event.approval_chain),
            switch_timestamp=event.switch_timestamp,
        )

    def __post_init__(self) -> None:
        """实体不变量校验（失败抛 ``EntityValidationError`` 242）.

        五场景（context 形态 ``{字段名: 实际值}``——对齐 isolation_state 先例，
        逐字段名稳定可断言）:
        ① agent_id / log_id 非 UUID 实例拒（合法 UUID 字符串同拒——isinstance 判定）；
        ② previous_level / target_level 非 ``IsolationLevel`` 枚举实例拒
          （双条件 isinstance 先行——str,Enum 混入语义下 ``"L4" == L4_HARD``
          为 True 但类型非法，值比对守卫拦不住，5-4 R3-F01 教训）；
        ③ ``previous_level == target_level`` 拒（切换语义不变量——no-op 不得
          产生日志；与 PG CheckConstraint 构成双层防线）；
        ④ trigger_reason 非 str 或空白拒；
        ⑤ approval_chain 非 tuple 拒 + 元素非 str 或空白串拒。

        Raises:
            EntityValidationError: 任一不变量不满足（EXCEPTION_242）。
        """
        if not isinstance(self.agent_id, uuid.UUID):
            raise EntityValidationError(
                message=f"agent_id 必须为 UUID 实例（实际类型 {type(self.agent_id).__name__}）",
                context={"agent_id": str(self.agent_id)},
            )
        if not isinstance(self.log_id, uuid.UUID):
            raise EntityValidationError(
                message=f"log_id 必须为 UUID 实例（实际类型 {type(self.log_id).__name__}）",
                context={"log_id": str(self.log_id)},
            )
        if not isinstance(self.previous_level, IsolationLevel):
            raise EntityValidationError(
                message=(f"previous_level 必须为 IsolationLevel 枚举实例（实际类型 {type(self.previous_level).__name__}）"),
                context={"previous_level": str(self.previous_level)},
            )
        if not isinstance(self.target_level, IsolationLevel):
            raise EntityValidationError(
                message=(f"target_level 必须为 IsolationLevel 枚举实例（实际类型 {type(self.target_level).__name__}）"),
                context={"target_level": str(self.target_level)},
            )
        if self.previous_level == self.target_level:
            raise EntityValidationError(
                message="previous_level 与 target_level 不得相等（no-op 切换不产生日志）",
                context={"previous_level": self.previous_level.value, "target_level": self.target_level.value},
            )
        if not isinstance(self.trigger_reason, str) or not self.trigger_reason.strip():
            raise EntityValidationError(
                message="trigger_reason 不能为空（非空文本——审计留痕必填）",
                context={"trigger_reason": str(self.trigger_reason)},
            )
        if not isinstance(self.approval_chain, tuple):
            raise EntityValidationError(
                message=(f"approval_chain 必须为 tuple 不可变形态（实际类型 {type(self.approval_chain).__name__}）"),
                context={"approval_chain": str(self.approval_chain)},
            )
        for member in self.approval_chain:
            if not isinstance(member, str) or not member.strip():
                raise EntityValidationError(
                    message="approval_chain 元素必须为非空字符串",
                    context={"approval_chain": str(self.approval_chain), "invalid_member": str(member)},
                )

    def to_dict(self) -> dict[str, Any]:
        """全字段可序列化字典（对齐 audit_log.to_dict 序列化惯例）.

        类型转换: UUID→str / Enum→value / datetime→ISO 8601 字符串 /
        tuple→list（JSONB 写入前置形态—— worm_ref None 保持 None）。

        Returns:
            八字段字典（键集与实体字段一一对应）。
        """
        return {
            "log_id": str(self.log_id),
            "agent_id": str(self.agent_id),
            "previous_level": self.previous_level.value,
            "target_level": self.target_level.value,
            "trigger_reason": self.trigger_reason,
            "approval_chain": list(self.approval_chain),
            "switch_timestamp": self.switch_timestamp.isoformat(),
            "worm_ref": self.worm_ref,
        }


__all__ = ["IsolationSwitchLog"]
