"""应用层 Checkpoint 编排服务端口模块（Story 6-3）

Checkpoint 完整形态快照的应用层端口——组合注入五既有依赖（R2：
PersistentNoteTaker/ContextCompressor（domain 服务）+ StrategicArchiveService
（应用层服务）+ SnapshotRepositoryProtocol/EventPublisher（R1 基础端口），
全部既有注册零新基础端口）。

序列化契约区（三级契约同款纪律——6-2 先例）：

第一级——完整形态快照键族（OD-3 快照双轨制）：
    CHECKPOINT_SESSION_PREFIX（本文件单源常量）→
    session_id = f"{CHECKPOINT_SESSION_PREFIX}{plan_id}:{checkpoint_no}" →
    最终 Redis 键 sisys:snapshot:blm-checkpoint-{plan_id}:{checkpoint_no}
    （RedisSnapshotStore.build_key("snapshot", session_id)——内部冒号原样保留）。
    与 6-2 骨架键族（blm-planning- 前缀双键族，TTL 86400）显式区分；
    读侧判别规则 = 前缀 + state_data 含 checkpoint_no 锚。TTL 30 天
    （2592000 秒——完整形态是审批/恢复面，合规要求；骨架是流程状态面维持 86400）。

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
