"""领域层 planning 子域异常（Story 6-1 — BLM 前两阶段流程）

规划子域物理码段 **(480,489)**——八代开段先例链（system 101/business 201/
storage 211/.../agent 440/evaluation 450/sap 460/financial 470 之后的第八段）；
语义继承 BusinessException 基类（planning 段编码）。

开段依据（Subtask 0.2 钦定）：business 物理段 (201,209) 已满、financial
(470,479) 为双重成文预留段（`_code_ranges.py` 段条目注释 +
sisys-uni-exception-design.md §3.3.2 编码表双处成文）不可占用——取空闲段
480 开 planning 子域（全仓 grep EXCEPTION_48 零占用验证）。

异常清单：
- PlanningNotFoundError (480)——plan_id 不存在（状态查询无快照第三态）
- PlanningExecutionError (481)——全流程失败终态（RunBlmPlanningUseCase
  终态组装处：len(degraded_steps) == total_steps 时抛出）
- PlanningStateError (482)——状态机非法推进（已激活：同 plan_id 重跑守卫
  ——R1-5；482 第二触发点=Checkpoint 修正面乐观锁版本倒退——Story 6-3）
- CheckpointCreationError (483)——Checkpoint 五步编排强制环节失败
  （Story 6-3：持久化笔记失败/压缩终态门禁/快照落库失败等——AC-1 负向；
  485 独立码不设——OD-7：compress 二次路径耗尽静默返回，门禁落编排层后
  恰是 483 触发面，独立码语义冗余）
- CheckpointIntegrityError (484)——完整性违约（Story 6-3：完整形态缺失
  persistent_note_ref 构造守卫 + checksum 校验失败/篡改检测——AC-2/AC-3）
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import BusinessException

__all__ = [
    "CheckpointCreationError",
    "CheckpointIntegrityError",
    "PlanningExecutionError",
    "PlanningNotFoundError",
    "PlanningStateError",
]


class PlanningNotFoundError(BusinessException):
    """规划任务不存在（EXCEPTION_480——404 语义）。

    触发场景：GetBlmPlanningStatusUseCase 查询的 plan_id 无快照记录
    （读写时序错位或 plan_id 非法）——状态查询第三态显式失败。
    """

    code = "EXCEPTION_480"
    message = "规划任务不存在"

    def __init__(
        self,
        plan_id: str,
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """构造规划不存在异常。

        Args:
            plan_id: 不存在的规划任务标识。
            message: 覆写消息（缺省回落类静态文案）。
            cause: 底层异常（可选）。
            context_extra: 附加领域上下文（合并进 context）。
        """
        context: dict[str, str] = {"plan_id": plan_id}
        if context_extra:
            context.update(context_extra)
        super().__init__(message=message, cause=cause, context=context)


class PlanningExecutionError(BusinessException):
    """规划执行失败终态（EXCEPTION_481——系统执行语义 500）。

    触发场景：BLM 前两阶段全部 8 步降级（阶段 1 + 六子步骤 + synthesis
    全部 degraded）——RunBlmPlanningUseCase 终态组装处抛出；部分降级
    （如 7/8）不触发本异常（返回成功 DTO + degraded_steps 成文语义）。
    """

    code = "EXCEPTION_481"
    message = "规划执行失败"

    def __init__(
        self,
        agent_id: str = "",
        plan_id: str = "",
        reason: str = "",
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """构造规划执行失败异常。

        Args:
            agent_id: 执行 Agent 标识。
            plan_id: 规划任务标识。
            reason: 失败原因（全降级终态描述）。
            message: 覆写消息（缺省回落类静态文案）。
            cause: 底层异常（可选）。
            context_extra: 附加领域上下文。
        """
        context: dict[str, str] = {"agent_id": agent_id, "plan_id": plan_id, "reason": reason}
        if context_extra:
            context.update(context_extra)
        super().__init__(message=message, cause=cause, context=context)


class PlanningStateError(BusinessException):
    """规划状态机非法推进（EXCEPTION_482）。

    触发场景：①同 plan_id 重跑（R1-5——`BlmPlanningService.run_performance_gap_analysis`
    入口守卫：首次 run 事件已发布/快照已写，重跑将污染 timeline 与降级计数；
    重试语义=新 plan_id）②规划阶段位点非法跃迁（如 market_insight →
    performance_gap 回退——6.3 Checkpoint 恢复面的状态机守卫扩展位）。
    """

    code = "EXCEPTION_482"
    message = "规划状态机非法推进"

    def __init__(
        self,
        plan_id: str = "",
        transition: str = "",
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """构造状态机非法推进异常。

        Args:
            plan_id: 规划任务标识。
            transition: 非法跃迁描述（如 "market_insight→performance_gap"）。
            message: 覆写消息（缺省回落类静态文案）。
            cause: 底层异常（可选）。
            context_extra: 附加领域上下文。
        """
        context: dict[str, str] = {"plan_id": plan_id, "transition": transition}
        if context_extra:
            context.update(context_extra)
        super().__init__(message=message, cause=cause, context=context)


class CheckpointCreationError(BusinessException):
    """Checkpoint 创建编排失败（EXCEPTION_483——系统执行语义 500）。

    触发场景（Story 6-3 五步编排强制环节失败——AC-1 负向）：①持久化笔记
    失败；②压缩终态门禁（compress 二次路径耗尽仍不达标——编排层校验双
    指标 fail-loud，R1-F2/OD-7）；③StrategicArchive 归档 L2/L4 失败及
    归档内 ArchiveCreated 发布失败（ArchiveStorageError 284 包装透传）；
    ④快照落库失败。任一强制环节失败抛出且不产出半成品快照。
    """

    code = "EXCEPTION_483"
    message = "Checkpoint 创建失败"

    def __init__(
        self,
        plan_id: str = "",
        checkpoint_no: str = "",
        reason: str = "",
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """构造 Checkpoint 创建失败异常。

        Args:
            plan_id: 规划任务标识。
            checkpoint_no: 检查点编号（如 "CP-1"）。
            reason: 失败环节描述（如 "压缩终态门禁：双指标不足"）。
            message: 覆写消息（缺省回落类静态文案）。
            cause: 底层异常（可选）。
            context_extra: 附加领域上下文（合并进 context）。
        """
        context: dict[str, str] = {"plan_id": plan_id, "checkpoint_no": checkpoint_no, "reason": reason}
        if context_extra:
            context.update(context_extra)
        # message 组合语义（R1 审查 FR-3——有意变更留痕）：reason 非空且调用方未覆写
        # message 时，默认 message 组合根因描述（CLI/6-6/API 等人机消费面可见——
        # 实测静态文案使 483 的真实根因只存于 context 对操作者不可见）；context
        # 中的结构化 reason 字段保持不变，to_dict 契约零变更
        if message is None and reason:
            message = f"Checkpoint 创建失败: {reason}"
        super().__init__(message=message, cause=cause, context=context)


class CheckpointIntegrityError(BusinessException):
    """Checkpoint 完整性违约（EXCEPTION_484——冲突语义 409）。

    触发场景（Story 6-3）：①完整形态快照构造守卫——checkpoint_no 非空而
    persistent_note_ref 为空（系统公理二：禁止无持久化引用的完整形态快照
    ——AC-2）；②checksum 校验失败/篡改检测（恢复入口强制先
    verify_integrity，校验失败拒绝恢复——AC-3）；③修正入口写前验证
    （R3-1——篡改/损坏快照的修正会把 checksum 重算封印到篡改载荷上使
    本门禁永久失效，写前 verify 拒绝使完整性信封不可经修正面洗白）。
    """

    code = "EXCEPTION_484"
    message = "Checkpoint 完整性违约"

    def __init__(
        self,
        session_id: str = "",
        checkpoint_no: str = "",
        reason: str = "",
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """构造 Checkpoint 完整性违约异常。

        Args:
            session_id: 快照会话键（blm-checkpoint-{plan_id}:{checkpoint_no}）。
            checkpoint_no: 检查点编号（如 "CP-1"）。
            reason: 违约原因（如 "empty_persistent_note_ref"/"checksum_mismatch"）。
            message: 覆写消息（缺省回落类静态文案）。
            cause: 底层异常（可选）。
            context_extra: 附加领域上下文（合并进 context）。
        """
        context: dict[str, str] = {"session_id": session_id, "checkpoint_no": checkpoint_no, "reason": reason}
        if context_extra:
            context.update(context_extra)
        super().__init__(message=message, cause=cause, context=context)
