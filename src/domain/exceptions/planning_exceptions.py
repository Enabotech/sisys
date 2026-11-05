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
- CheckpointRecoveryError (486)——恢复执行编排强制环节失败（Story 6-6：
  try 面扩包③修正应用/④恢复记录两处 save 的 StorageError 统一包裹——
  fail-loud；485 空洞维持——OD-7 段内空洞永不设码）
- RecoveryModeConflictError (487)——模式强制执法拒绝（Story 6-6：建议
  Replay 而请求 Override → 零副作用拒绝——or.md L622 不变约束承载；
  488/489 继续预留——planning 段残留位）
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import BusinessException

__all__ = [
    "CheckpointCreationError",
    "CheckpointIntegrityError",
    "CheckpointRecoveryError",
    "PlanningExecutionError",
    "PlanningNotFoundError",
    "PlanningStateError",
    "RecoveryModeConflictError",
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


class CheckpointRecoveryError(BusinessException):
    """Checkpoint 恢复执行编排失败（EXCEPTION_486——系统执行语义 500）。

    触发场景（Story 6-6 恢复引擎 execute_recovery 强制环节失败——AC-7
    fail-loud）：③修正应用步 apply_correction 内 save 失败与④恢复记录
    save 失败统一归 486（try 面扩包③④两处 save——不扩包则 StorageError
    103 裸逃逸破坏六码全景；save 无 try 是 6-3 冻结行为面、486 包裹是
    恢复编排层职责）；except 面钦定 StorageError（RedisSnapshotStore.save
    唯一异常出口，包装一切异常）。480/482/484 在 save 之前触发经既有
    触发点透传不并入；⑤发布独立降级面不属 486（发布失败降级 warning
    不回滚恢复记录——恢复记录是审计真相源、事件是通知面）。
    """

    code = "EXCEPTION_486"
    message = "Checkpoint 恢复执行失败"

    def __init__(
        self,
        plan_id: str = "",
        checkpoint_no: str = "",
        reason: str = "",
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """构造 Checkpoint 恢复执行失败异常。

        Args:
            plan_id: 规划任务标识。
            checkpoint_no: 恢复起点检查点编号（如 "CP-3"）。
            reason: 失败环节描述（如 "恢复记录落库失败: Redis 写入超时"）。
            message: 覆写消息（缺省回落类静态文案）。
            cause: 底层异常（可选——StorageError 链透传）。
            context_extra: 附加领域上下文（合并进 context）。
        """
        context: dict[str, str] = {"plan_id": plan_id, "checkpoint_no": checkpoint_no, "reason": reason}
        if context_extra:
            context.update(context_extra)
        # message 组合语义（6-3 R1-F3 组合先例直接继承）：reason 非空且调用方
        # 未覆写 message 时，默认 message 组合根因描述（根因对 CLI/API 操作者可见）
        if message is None and reason:
            message = f"Checkpoint 恢复执行失败: {reason}"
        super().__init__(message=message, cause=cause, context=context)


class RecoveryModeConflictError(BusinessException):
    """恢复模式强制执法冲突（EXCEPTION_487——冲突语义 409）。

    触发场景（Story 6-6 模式执法——or.md L622 不变约束「修改影响≥2 个
    后续 Checkpoint 强制采用 Replay 模式」）：建议 REPLAY（后续 ≥2）而请求
    OVERRIDE → 拒绝执行（零副作用——恢复记录不写、事件不发、修正不应用；
    执法点②.5 前置于③修正应用）；建议 OVERRIDE 而请求 REPLAY → 允许
    （用户可选更强一致性模式——弱替强允方向性执法，OD-6）。
    """

    code = "EXCEPTION_487"
    message = "恢复模式冲突"

    def __init__(
        self,
        recommended_mode: str = "Replay",
        requested_mode: str = "Override",
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """构造恢复模式冲突异常。

        Args:
            recommended_mode: 建议恢复模式（大写展示形态 "Replay"/"Override"——
                与事件枚举值同形，引擎构造时经 to_event_recovery_mode 转换传入）。
            requested_mode: 请求恢复模式（同上大写形态）。
            message: 覆写消息（缺省组合建议/请求双模式）。
            cause: 底层异常（可选）。
            context_extra: 附加领域上下文（合并进 context）。
        """
        context: dict[str, str] = {"recommended_mode": recommended_mode, "requested_mode": requested_mode}
        if context_extra:
            context.update(context_extra)
        # message 组合语义（可理解性裁决面）：默认 message 携带建议模式与请求
        # 模式（操作者免查 context 即可理解冲突两方——OD-6）
        if message is None:
            message = f"恢复模式冲突: 影响≥2 个后续 Checkpoint 强制 Replay（建议={recommended_mode}, 请求={requested_mode}）"
        super().__init__(message=message, cause=cause, context=context)
