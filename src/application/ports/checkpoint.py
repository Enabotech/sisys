"""应用层 Checkpoint 编排服务端口模块（Story 6-3/6-6）

Checkpoint 完整形态快照的应用层端口——组合注入五既有依赖（R2：
PersistentNoteTaker/ContextCompressor（domain 服务）+ StrategicArchiveService
（应用层服务）+ SnapshotRepositoryProtocol/EventPublisher（R1 基础端口），
全部既有注册零新基础端口）。

序列化契约区（四级契约同款纪律——6-2/6-6 先例）：

第一级——完整形态快照键族（OD-3 快照双轨制）：
    CHECKPOINT_SESSION_PREFIX（本文件单源常量）→
    session_id = f"{CHECKPOINT_SESSION_PREFIX}{plan_id}:{checkpoint_no}" →
    最终 Redis 键 sisys:snapshot:blm-checkpoint-{plan_id}:{checkpoint_no}
    （RedisSnapshotStore.build_key("snapshot", session_id)——内部冒号原样保留）。
    与 6-2 骨架键族（blm-planning- 前缀双键族，TTL 86400）显式区分；
    读侧判别规则 = 前缀 + state_data 含 checkpoint_no 锚（**适用范围注记**
    （6-6 第四级契约引入后收窄）：该第一级判别语仅在 blm-planning 与
    blm-checkpoint 两族互判时充分；三前缀并存后的权威判别键见第四级）。
    TTL 30 天（2592000 秒——完整形态是审批/恢复面，合规要求；骨架是流程
    状态面维持 86400）。

第二级——state_data 13 键契约（Task 0.2 冻结唯一版本）：
    checkpoint_no / stage_id / stage_number（int 序号——"CP-n" 后缀解析派生，
    R7-1）/ plan_id / completed（bool——CheckpointStatus 映射：True↔COMPLETED/
    False↔IN_PROGRESS）/ summary（调用方直供）/ compressed_context（str——
    压缩产物 context 字段）/ compression_ratio / quality_score / token_count /
    persistent_note_ref / correction_history（list[dict] 恒存在初始 []——
    条目为 CorrectionRecord 五字段 dict 投影，applied_at 取 isoformat() 字符串化，
    R8-F5）/ created_via（值域 "cli"/"use_case" 两值小写枚举——经
    create_checkpoint 入参注入，R6-4）。
    键恒在纪律：correction_history 恒存在（禁「无修正时键缺失」形态——6-6 读侧
    免双兼容）；persistent_note_ref 恒非空（实体构造守卫保证）。

第三级——take_notes session_id 与快照键同源钦定（Task 0.2）：
    create_checkpoint 内部派生 session_id（上述键族形态）作 take_notes 第四参
    ——持久化笔记血缘与快照键一源；归档关联：快照↔归档行经 plan_id 关联查询
    （archive_plan 入参同 plan_id + decision_basis.checkpoint_no 语境锚——
    R3-E/R8-F3，不引入 archive_id 键）。

第四级——恢复记录第三键族（Story 6-6 OD-3，Task 0.1 冻结唯一版本）：
    CHECKPOINT_RECOVERY_SESSION_PREFIX（本文件单源常量）→
    session_id = f"{CHECKPOINT_RECOVERY_SESSION_PREFIX}{plan_id}"（无 :CP-n 段）
    → 最终 Redis 键 sisys:snapshot:blm-checkpoint-recovery-{plan_id}。
    承载形态 = CheckpointSnapshot 通用 KV（checkpoint_no="" **非完整形态**——
    不触发实体构造守卫/persistent_note_ref 强制；checksum 空——非完整性保护
    对象，审计面由 outbox 事件承载），经既有 snapshot_repository.save/load 存取。
    state_data 12 键契约：plan_id / checkpoint_no（恢复起点）/ recovery_mode
    （"replay"/"override" 小写——entities 枚举值形态）/ corrected（bool）/
    correction（五字段投影 dict 或 {}——无修正时空 dict 键恒在）/
    affected_checkpoints（list）/ pending_sync_checkpoints（list——Override
    分支填充，Replay 时空 [] 键恒在）/ invalidated_checkpoints（list——Replay
    分支填充，Override 时空 [] 键恒在）/ confirmed_by（str）/ recovered_at
    （isoformat）/ execution_ms（float）/ created_via（"cli"/"use_case" 两值）。
    TTL 2592000（30 天对齐 checkpoint 键族合规窗）；每 plan 最新一次恢复单键
    覆盖（与 6-2 latest 键同构——历史经事件 outbox 可溯）。
    权威判别键（三前缀并存后）：前缀（blm-planning-/blm-checkpoint-/
    blm-checkpoint-recovery- 三前缀互异）+ 实体面 checkpoint_no==""（Redis 键
    无 :CP-n 段）+ state_data 含 recovery_mode 键（checkpoint 族 13 键无此键
    ——恢复记录 12 键独有；两族 state_data 均含 checkpoint_no 键）。
    sync_status 推导规则（list_checkpoints join 语义）：load 恢复记录（None →
    全量 in_sync——含 load 失败/JSON 损坏同归 None 的退化语义）；对每个存活
    checkpoint_no——在 invalidated_checkpoints → "invalidated"；在
    pending_sync_checkpoints → "pending_sync"；否则 "in_sync"；恢复起点
    checkpoint_no 自身恒 in_sync（新基线）。两条口径注记：① 推导仅基于该 plan
    最新一次恢复记录（单键覆盖后旧标记从显示面消失——读面回退 in_sync，历史
    溯源自 outbox）；② invalidated 点在后续 probe 中仍按键存在性计入后续数
    参与模式判定（MVP 判定不消费 sync 标记——完整协议归 Epic 10）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from src.domain.entities.checkpoint import CorrectionRecord, RecoveryMode
from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.ports.l3_vector import SearchResult
from src.domain.services.context_compressor import CompressedContext

#: 完整形态快照会话前缀（单源常量——OD-3 双轨制，与 blm-planning- 前缀显式区分）
CHECKPOINT_SESSION_PREFIX: str = "blm-checkpoint-"

#: 完整形态快照 TTL（30 天——R8-F4：build_snapshot 显式落值，实体默认 86400 不适用）
CHECKPOINT_TTL_SECONDS: int = 2_592_000

#: checkpoint_no 值域上限（BLM 前两阶段 8 恢复点——后续清单 probe 范围）
CHECKPOINT_NO_MAX: int = 8

#: 恢复记录会话前缀（第三键族单源常量——OD-3：与 blm-checkpoint- 前缀互异判别）
CHECKPOINT_RECOVERY_SESSION_PREFIX: str = "blm-checkpoint-recovery-"


@runtime_checkable
class CheckpointServicePort(Protocol):
    """Checkpoint 编排服务端口（创建五步编排 + 恢复数据面——单端口双方法组）。"""

    async def create_checkpoint(
        self,
        *,
        plan_id: str,
        checkpoint_no: str,
        stage_id: str,
        query: str,
        retrieved_docs: list[SearchResult],
        user_id: str,
        summary: str,
        completed: bool = True,
        created_via: str = "use_case",
    ) -> CheckpointSnapshot:
        """五步编排创建完整形态快照（OD-12 五步序）。

        ①PersistentNoteTaker.take_notes 持久化原始上下文 → ②ContextCompressor
        .compress 压缩（含编排层终态门禁——双指标不足抛 483）→ ③StrategicArchive
        Service 归档（载荷=压缩产物+笔记实体/摘要）→ ④build_snapshot 构造+
        落库（TTL 30 天）→ ⑤发布 CheckpointReached（失败降级不回滚）。

        Args:
            plan_id: 规划任务标识（UUID 字符串——用例层守卫校验）。
            checkpoint_no: 检查点编号（"CP-1".."CP-8"）。
            stage_id: 阶段标识（STAGE_VALUE_DOMAIN 值域）。
            query: 原始查询文本（持久化笔记输入）。
            retrieved_docs: 检索证据族（SearchResult dict 形态——payload.content 键）。
            user_id: 执行用户标识。
            summary: 阶段摘要（调用方直供）。
            completed: 完成状态（默认 True——与 CLI --completed 默认一致，R6-21）。
            created_via: 触发源标识（"cli"/"use_case" 两值小写枚举——默认编程调用；
                CLI 入口显式传 "cli"，R6-4）。

        Returns:
            已落库的完整形态快照实体。

        Raises:
            CheckpointCreationError: 483——五步编排任一强制环节失败（无半成品）。
            EntityValidationError: 242——未持久化笔记压缩等既有守卫透传。
            ArchiveStorageError: 归档强制层失败的底层 cause（包装进 483）。
        """
        ...

    def build_snapshot(
        self,
        *,
        plan_id: str,
        checkpoint_no: str,
        stage_id: str,
        compressed: CompressedContext,
        summary: str,
        completed: bool,
        created_via: str = "use_case",
    ) -> CheckpointSnapshot:
        """④步快照构造逻辑单列（纯构造无副作用——R6-5）。

        13 键组装 + stage_number 派生（"CP-n" 后缀解析，R7-1）+ checksum 显式
        计算（AC-3 初始化链）+ TTL 30 天落值（R8-F4）+ Checkpoint 聚合驱动
        （仅 completed=True 时 complete()——OD-12 附则 a）。create_checkpoint
        第④步内部复用；性能采样（AC-8）直调 build_snapshot → save 两段。

        Args:
            plan_id: 规划任务标识。
            checkpoint_no: 检查点编号。
            stage_id: 阶段标识。
            compressed: 压缩产物（就绪态——双指标已过门禁）。
            summary: 阶段摘要。
            completed: 完成状态。
            created_via: 触发源标识。

        Returns:
            封印 checksum 的完整形态快照（未落库——纯构造）。
        """
        ...

    async def apply_correction(
        self,
        *,
        session_id: str,
        correction: CorrectionRecord,
        expected_state_version: int,
    ) -> CheckpointSnapshot:
        """修正应用（AC-6——乐观锁式不可变更新+同键覆盖）。

        键内存活快照 state_version 与 expected_state_version 比对（不匹配即
        版本倒退/并发过期 → 482 第二触发点，R6-3）；CorrectionRecord 五字段
        dict 投影追加进 correction_history；with_updated_state 不可变更新
        （state_version+1）；checksum 重算替换（AC-3 重算点）；save 覆盖同键
        （单键单版本存活——R3-T2，不建版本键链）。

        Args:
            session_id: 快照会话键（blm-checkpoint-{plan_id}:{checkpoint_no}）。
            correction: 修正记录（既有 CorrectionRecord 五字段）。
            expected_state_version: 调用方持有的基线版本（乐观锁比对）。

        Returns:
            修正后的新版快照（v+1）。

        Raises:
            PlanningNotFoundError: 480——键不存在（含 JSON 损坏同路径统一承载）。
            PlanningStateError: 482——版本倒退/并发过期（第二触发点）。
            CheckpointIntegrityError: 484——修正前置完整性校验失败（R3-1——
                篡改/损坏快照禁止修正，防 checksum 封印洗白）。
        """
        ...

    async def recover_checkpoint(self, *, plan_id: str, checkpoint_no: str) -> "CheckpointRecoveryView":
        """恢复数据面（AC-7——load→verify→反序列化→视图组装；只读不驱动聚合）。

        后续 checkpoint 清单推导（R8-F1）：对值域 {CP-1..CP-8} 中序号大于当前
        checkpoint_no 序号的候选，逐一 load 探测（probe-load），非 None 者按序号
        升序入清单；None 者静默跳过（不存在与 JSON 损坏同路径——仅服务模式判定
        非完整性断言面）。恢复执行引擎（Replay/Override）归 6-6（OD-1）。

        Args:
            plan_id: 规划任务标识。
            checkpoint_no: 恢复起点检查点编号。

        Returns:
            恢复视图 DTO（6-6 消费面契约）。

        Raises:
            PlanningNotFoundError: 480——键不存在（含 JSON 损坏同路径）。
            CheckpointIntegrityError: 484——checksum 校验失败（拒绝恢复）。
        """
        ...

    def recommend_recovery_mode(self, affected_checkpoint_count: int) -> RecoveryMode:
        """恢复模式建议（透传领域纯函数——≥2 REPLAY 强制/<2 OVERRIDE 推荐）。"""
        ...

    async def list_checkpoints(self, *, plan_id: str) -> "list[CheckpointSummaryView]":
        """读面清单（Story 6-6 AC-1——全量 probe + 恢复记录 join sync_status）。

        对值域 {CP-1..CP-8} 全量 probe-load（R8-F1 增量 probe 模式从 CP-1 起
        的全量扩展），非 None 者按序号升序组装 CheckpointSummaryView（8 键）；
        sync_status 经恢复记录 join 推导（无恢复记录/记录损坏同归全量
        in_sync——第四级契约退化语义）。plan_id UUID 守卫归用例层（服务层
        不重复守卫——6-3 先例一致）；空族返回空清单不抛 480（清单是枚举面
        非单点面，与 recover_checkpoint 单点 480 语义分立）。

        Args:
            plan_id: 规划任务标识（UUID 字符串——用例层守卫校验）。

        Returns:
            摘要视图清单（checkpoint_no 升序；空族空清单）。
        """
        ...

    async def execute_recovery(
        self,
        *,
        plan_id: str,
        checkpoint_no: str,
        correction: CorrectionRecord | None = None,
        mode: RecoveryMode | None = None,
        confirmed_by: str = "",
        created_via: str = "use_case",
    ) -> "CheckpointRecoveryOutcome":
        """恢复执行引擎（Story 6-6 AC-3——五步编排）。

        ①入口守卫（_parse_checkpoint_number 三重复用）→ ②恢复数据面
        （recover_checkpoint：load+verify+后续清单+建议模式）→ ②.5 模式裁定
        （mode 显式传入时执行强制语义执法 487——裁定前置于③修正应用，零副作用）
        → ③修正应用（correction 非 None 时经 apply_correction，乐观锁基线取
        自②视图 state_version）→ ④双模式分支落恢复记录（第三键族 12 键，
        Override→后续 pending_sync / Replay→后续 invalidated；486 try 面扩包
        ③④两处 save）→ ⑤发布 CheckpointRecovered（首激活——失败降级 warning
        不回滚恢复记录）。`confirmed` 不入签名：CLI 两态在接口层拦截，无
        confirm 的 dry-run 不进引擎——引擎假设调用方已确认。

        Args:
            plan_id: 规划任务标识（UUID 字符串——用例层守卫校验）。
            checkpoint_no: 恢复起点检查点编号（"CP-1".."CP-8"）。
            correction: 关键参数修正（None=纯恢复场景）。
            mode: 显式恢复模式（None=取②步建议模式；显式传入时强制语义执法——
                建议 REPLAY 而请求 OVERRIDE 抛 487，反向允许）。
            confirmed_by: 审批人标识（审批留痕——与 correction.applied_by 双写
                恢复记录；空串守卫归用例层 242）。
            created_via: 触发源标识（"cli"/"use_case" 两值）。

        Returns:
            恢复执行结果（10 键 Outcome——断言锚单源）。

        Raises:
            EntityValidationError: 242——checkpoint_no 三重守卫或 mode 非 RecoveryMode
                枚举（裸 str 防御守卫——代码审查 R1-F8）。
            PlanningNotFoundError: 480——键不存在（含 JSON 损坏同路径）。
            PlanningStateError: 482——修正乐观锁版本冲突（②视图基线比对）。
            CheckpointIntegrityError: 484——恢复入口 verify 校验失败。
            RecoveryModeConflictError: 487——模式强制执法拒绝（零副作用）。
            CheckpointRecoveryError: 486——编排强制环节失败（③④ save 统一包裹）。
        """
        ...


# -----------------------------------------------------------------------
# 恢复视图 DTO（Task 0 钦定落端口文件——6-6 消费面契约）
# -----------------------------------------------------------------------


@dataclass(frozen=True)
class CheckpointRecoveryView:
    """恢复视图 DTO。

    恢复数据面产物：load→verify→反序列化→组装，供 6-6 审批/恢复执行面消费。
    键契约（Task 0 冻结 7 键 + R3-2 增补 2 键——消费面预演发现的契约缺口：
    6-6 审批「审阅→修正」闭环必须持 expected_state_version 供 apply_correction
    乐观锁，视图不携带将迫使消费方旁路服务直连仓储）：checkpoint_no/stage/
    compressed_context/state_data/correction_history/subsequent_checkpoints/
    recommended_mode + state_version/snapshot_id。

    Attributes:
        checkpoint_no: 恢复起点检查点编号（"CP-n"）。
        stage: 阶段标识（stage_id 值域）。
        compressed_context: 压缩后上下文（恢复载荷核心）。
        state_data: 快照全量状态（13 键）。
        correction_history: 修正历史清单（五字段投影累积）。
        subsequent_checkpoints: 后续仍存活 checkpoint 清单（probe-load 推导升序）。
        recommended_mode: 建议恢复模式（str Enum——"replay"/"override" 可直比）。
        state_version: 快照当前版本（R3-2——6-6 修正面乐观锁基线）。
        snapshot_id: 快照标识字符串（R3-2——与 outbox CheckpointReached.
            checkpoint_id 序列化面同形态，6-6 事件关联比对用）。
    """

    checkpoint_no: str
    stage: str
    compressed_context: str = ""
    state_data: dict[str, Any] = field(default_factory=dict)
    correction_history: list[dict[str, Any]] = field(default_factory=list)
    subsequent_checkpoints: list[str] = field(default_factory=list)
    recommended_mode: RecoveryMode = RecoveryMode.OVERRIDE
    state_version: int = 0
    snapshot_id: str = ""


# -----------------------------------------------------------------------
# 摘要视图 VO（Story 6-6 Task 0 冻结 8 键——AC-1 清单条目契约）
# -----------------------------------------------------------------------


@dataclass(frozen=True)
class CheckpointSummaryView:
    """Checkpoint 摘要视图 VO（清单条目——AC-1 四要素显示的清单承载面）。

    四要素（epics L2319 钦定）：阶段标识（checkpoint_no+stage_id）/ 完成状态
    （completed）/ 关键参数（summary+correction_history 修正历史——后者经详情
    面携带）/ 用户反馈（correction_history 修正响应历史+completed 状态承载；
    user_feedback_request 审批请求标志仅存在于 CheckpointReached 事件 payload
    经 outbox 可溯，不在快照 state_data 13 键内、不进本 VO——8 键契约不含）。

    Attributes:
        checkpoint_no: 检查点编号（"CP-n"）。
        stage_id: 阶段标识（原样直投影——显示语义零值域消费）。
        completed: 完成状态（bool 直投影）。
        summary: 阶段摘要（str 直投影）。
        state_version: 快照当前版本（修正历史轮次锚）。
        created_via: 触发源标识（"cli"/"use_case"）。
        timestamp: 创建时间（isoformat str——实体 datetime 在服务层转换）。
        sync_status: 同步状态（值域 "in_sync"/"pending_sync"/"invalidated"
            三值钦定——经恢复记录 join 推导）。
    """

    checkpoint_no: str
    stage_id: str
    completed: bool = False
    summary: str = ""
    state_version: int = 0
    created_via: str = "use_case"
    timestamp: str = ""
    sync_status: str = "in_sync"


# -----------------------------------------------------------------------
# 恢复执行结果 VO（Story 6-6 Task 0 冻结 10 键——AC-3 断言锚单源）
# -----------------------------------------------------------------------


@dataclass(frozen=True)
class CheckpointRecoveryOutcome:
    """恢复执行结果 VO（引擎⑤步后组装——验收/集成断言锚单源）。

    Attributes:
        checkpoint_no: 恢复起点检查点编号。
        recovery_mode: 实际执行恢复模式（entities 枚举小写——与恢复记录
            state_data 同形态可直比）。
        corrected: 是否应用了修正（correction 非 None 且③步成功）。
        new_state_version: 恢复后快照版本（修正一体=③步 sealed.state_version；
            纯恢复=②视图 state_version）。
        affected_checkpoints: 受影响后续清单（MVP 下与 marked_checkpoints
            恒等——双字段为 V2 部分标记分叉预留）。
        marked_checkpoints: 实际标记清单（Override=pending_sync 清单 /
            Replay=invalidated 清单）。
        execution_ms: 执行窗口毫秒（①~⑤组装点 perf_counter 差——保守方向
            窗口口径，OD-8）。
        next_action_hint: 后续动作指引（Replay 分支=重跑指引——建议以新
            plan_id 经 blm-plan 重跑；Override 分支=一致性风险提示）。
        recovery_record_session_id: 恢复记录会话键（审计回溯锚）。
        recovered_snapshot_id: 恢复后快照标识（⑤步事件 checkpoint_id 的同值
            锚：修正一体=③步 sealed.snapshot_id、纯恢复=②视图.snapshot_id
            ——outbox 值级断言的预期值单源）。
    """

    checkpoint_no: str
    recovery_mode: RecoveryMode
    corrected: bool = False
    new_state_version: int = 0
    affected_checkpoints: list[str] = field(default_factory=list)
    marked_checkpoints: list[str] = field(default_factory=list)
    execution_ms: float = 0.0
    next_action_hint: str = ""
    recovery_record_session_id: str = ""
    recovered_snapshot_id: str = ""
