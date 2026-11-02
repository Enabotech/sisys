"""应用层 Checkpoint 编排服务模块（Story 6-3）

五步编排（OD-12 四源合成钦定——architecture §8.2 主链 + §11.2.6 触发链 +
L850 归档位 + L871 发布行）：①PersistentNoteTaker.take_notes 持久化原始
上下文 → ②ContextCompressor.compress 压缩（含编排层终态门禁——R1-F2：
compress 二次路径耗尽静默返回不达标产物，门禁落编排层 fail-loud）→
③StrategicArchiveService 归档（载荷=压缩产物+笔记实体/摘要，L2 强制+L3/L5
可降级+L4 强制）→ ④build_snapshot 构造+落库（TTL 30 天）→ ⑤发布
CheckpointReached（发布点唯一落位——blm_planning 四文件零引用，OD-4；
失败降级不回滚：快照是真相源，事件是通知面）。

发布容错语义分层（R1-12）：③内 ArchiveCreated 发布失败 → ArchiveStorageError
→ 483 全链阻断（Outbox 原子性设计）；⑤CheckpointReached 发布失败 → 降级
日志（与 6-1 快照写容错同语义）——两套容错语义并存，编排不得在③步吞
ArchiveCreated 发布失败。
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import replace
from typing import Any

from src.application.ports.checkpoint import (
    CHECKPOINT_NO_MAX,
    CHECKPOINT_SESSION_PREFIX,
    CHECKPOINT_TTL_SECONDS,
    CheckpointRecoveryView,
)
from src.application.services.strategic_archive_service import StrategicArchiveService
from src.domain.entities.checkpoint import Checkpoint, CheckpointStatus, CorrectionRecord, RecoveryMode
from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.events.checkpoint_events import CheckpointReached
from src.domain.exceptions import (
    ArchiveStorageError,
    CheckpointCreationError,
    CheckpointIntegrityError,
    EntityValidationError,
    PlanningNotFoundError,
    PlanningStateError,
)
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
from src.domain.services.context_compressor import CompressedContext, ContextCompressor
from src.domain.services.persistent_note_taker import PersistentNoteTaker
from src.domain.services.recovery_mode import recommend_recovery_mode

logger = logging.getLogger(__name__)

#: 压缩终态门禁阈值（AC-2——与 ContextCompressor 常量同值；编排层 fail-loud 终局校验）
_COMPRESSION_RATIO_GATE: float = 0.70
_QUALITY_SCORE_GATE: float = 0.70

#: 归档笔记实体入档上限（Top-20——与 PersistentNoteTaker._ENTITY_LIMIT 同源）
_ARCHIVE_ENTITY_LIMIT: int = 20

#: checkpoint_no 规范形态（"CP-n"——R1 审查：全链守卫，拒畸形/值域外/非规范别名形态）
_CHECKPOINT_NO_PATTERN = re.compile(r"CP-(\d+)")


def _parse_checkpoint_number(checkpoint_no: str) -> int:
    """解析并校验 checkpoint_no（格式 + 值域 + 规范形态三重守卫）。

    守卫覆盖（R1 审查 FR-2——实测畸形编号原裸抛 IndexError/ValueError 逃逸
    统一异常体系、值域外编号静默落库 30 天垃圾数据）：
    ① 格式：fullmatch "CP-(\\d+)"（拒 "garbage"/"CP-abc"/"cp-1" 大小写）；
    ② 值域：1 <= n <= CHECKPOINT_NO_MAX（拒 "CP-0"/"CP-9"——BLM 前两阶段
       8 恢复点值域，上界经 CHECKPOINT_NO_MAX 单源派生，扩值域改一处常量）；
    ③ 规范形态：checkpoint_no == f"CP-{n}"（拒 "CP-01"/全角数字别名——
       非 canonical 形态会产生键别名使后续清单 probe 失明）。

    Args:
        checkpoint_no: 检查点编号字符串。

    Returns:
        解析后的序号 int（stage_number/后续清单推导同源）。

    Raises:
        EntityValidationError: 242——格式非法或值域越界（fail-loud，message 含值域声明）。
    """
    matched = _CHECKPOINT_NO_PATTERN.fullmatch(checkpoint_no)
    if matched is None:
        raise EntityValidationError(
            message=f"checkpoint_no 必须为 CP-[1-{CHECKPOINT_NO_MAX}] 形态（实测={checkpoint_no!r}）",
            context={"service": "CheckpointService", "field": "checkpoint_no", "checkpoint_no": checkpoint_no},
        )
    number = int(matched.group(1))
    if not 1 <= number <= CHECKPOINT_NO_MAX or checkpoint_no != f"CP-{number}":
        raise EntityValidationError(
            message=f"checkpoint_no 超出值域 CP-1..CP-{CHECKPOINT_NO_MAX} 或非规范形态（实测={checkpoint_no!r}）",
            context={"service": "CheckpointService", "field": "checkpoint_no", "checkpoint_no": checkpoint_no},
        )
    return number


class CheckpointService:
    """Checkpoint 编排服务（五步创建 + 恢复数据面——实现 CheckpointServicePort）。

    R2 组合注入五既有依赖（全部经组合根 resolve 注入，零新基础端口）：
    persistent_note_taker/context_compressor（domain 服务，首个生产消费方——
    检索-压缩循环激活）/strategic_archive_service（应用层服务，Checkpoint
    归档接线）/snapshot_repository/event_publisher（R1 基础端口）。
    """

    def __init__(
        self,
        *,
        note_taker: PersistentNoteTaker,
        compressor: ContextCompressor,
        archive_service: StrategicArchiveService,
        snapshot_repository: SnapshotRepositoryProtocol,
        event_publisher: EventPublisher,
    ) -> None:
        """初始化 Checkpoint 编排服务。

        Args:
            note_taker: 持久化笔记记录器（domain 服务）。
            compressor: 上下文压缩器（domain 服务——含 verify_persisted 前置校验）。
            archive_service: 战略档案编排服务（L2-L5 归档）。
            snapshot_repository: 快照仓储端口（R1 基础端口）。
            event_publisher: 事件发布端口（R1 基础端口——reliable 单通道）。
        """
        self._note_taker = note_taker
        self._compressor = compressor
        self._archive_service = archive_service
        self._snapshot_repository = snapshot_repository
        self._event_publisher = event_publisher

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
        """五步编排创建完整形态快照（OD-12——压缩先于归档、归档先于落库）。

        步骤序依据：§11.2.6 触发链（take_notes→compress→StrategicArchive 持久化）
        + L850（StrategicArchive=Checkpoint 快照前强制持久化）+ L871（发布末位）。
        任一强制环节失败抛 483 且不产出半成品快照（归档侧残留语义：①②已写的
        L1 笔记缓存/压缩缓存 TTL 自清、③内已写的 L2 行/L3 点为可接受残留）。

        Args:
            plan_id: 规划任务标识（UUID 字符串——用例层守卫校验）。
            checkpoint_no: 检查点编号（"CP-1".."CP-8"）。
            stage_id: 阶段标识（STAGE_VALUE_DOMAIN 值域）。
            query: 原始查询文本。
            retrieved_docs: 检索证据族（SearchResult dict 形态）。
            user_id: 执行用户标识。
            summary: 阶段摘要（调用方直供）。
            completed: 完成状态（默认 True——与 CLI --completed 默认一致）。
            created_via: 触发源标识（"cli"/"use_case"——R6-4）。

        Returns:
            已落库的完整形态快照。

        Raises:
            CheckpointCreationError: 483——强制环节失败（含压缩终态门禁）。
            EntityValidationError: 242——checkpoint_no 格式/值域守卫与未持久化笔记压缩等既有守卫透传。
        """
        # 入口守卫（R1 审查 FR-2：fail-fast 先于①——畸形编号零副作用零白耗，
        # 拒绝形态见 _parse_checkpoint_number 三重校验）
        _parse_checkpoint_number(checkpoint_no)
        session_id = f"{CHECKPOINT_SESSION_PREFIX}{plan_id}:{checkpoint_no}"

        # ① 持久化笔记（系统公理二前置：压缩前必须持久化）
        try:
            note = await self._note_taker.take_notes(
                query=query,
                retrieved_docs=retrieved_docs,
                user_id=user_id,
                session_id=session_id,
            )
        except (EntityValidationError, CheckpointIntegrityError):
            raise
        except Exception as error:
            raise CheckpointCreationError(
                plan_id=plan_id,
                checkpoint_no=checkpoint_no,
                reason=f"持久化笔记失败: {error}",
                cause=error,
            ) from error

        # ② 压缩（ContextCompressor 既有 verify_persisted 前置校验透传 242）
        try:
            compressed = await self._compressor.compress(
                retrieved_docs=retrieved_docs,
                query=query,
                persistent_note=note,
            )
        except EntityValidationError:
            raise  # 未持久化笔记压缩——既有路径零回归（AC-2 VC）
        except Exception as error:
            raise CheckpointCreationError(
                plan_id=plan_id,
                checkpoint_no=checkpoint_no,
                reason=f"上下文压缩失败: {error}",
                cause=error,
            ) from error

        # 编排层终态门禁（R1-F2/OD-7：compress 无最终门禁静默返回不达标产物——
        # 二次路径耗尽仍不达标时 fail-loud，快照零落库）
        if compressed.compression_ratio < _COMPRESSION_RATIO_GATE or compressed.quality_score < _QUALITY_SCORE_GATE:
            raise CheckpointCreationError(
                plan_id=plan_id,
                checkpoint_no=checkpoint_no,
                reason=(
                    f"压缩终态门禁：compression_ratio={compressed.compression_ratio} "
                    f"quality_score={compressed.quality_score}（阈值 0.70/0.70）"
                ),
            )

        # ③ StrategicArchive 归档（L2 强制→L3 降级→L4 强制→L5 降级→引用回写；
        #    归档内 ArchiveCreated 发布失败同抛 ArchiveStorageError——不容错）
        try:
            await self._archive_service.archive_plan(
                plan_id=uuid.UUID(plan_id),
                plan_type="SP",  # R6-1 钦定：Checkpoint 是 SP 编制过程阶段快照
                assumptions={
                    "entities": note.entities[:_ARCHIVE_ENTITY_LIMIT],
                    "summary": note.summary,
                    "lineage": note.lineage,
                },
                decision_basis={
                    "compressed_context": compressed.context,
                    "checkpoint_no": checkpoint_no,  # R8-F3 归档行 checkpoint 语境锚
                    "summary": summary,
                },
                evidence_blob=compressed.context.encode("utf-8"),
            )
        except ArchiveStorageError as error:
            raise CheckpointCreationError(
                plan_id=plan_id,
                checkpoint_no=checkpoint_no,
                reason=f"StrategicArchive 归档失败: {error}",
                cause=error,
            ) from error
        except (EntityValidationError, CheckpointIntegrityError):
            raise  # archive_plan 入口守卫（plan_type/validate）的 242 透传契约——端口 Raises 明列（R1 审查 FR-4）
        except Exception as error:
            # 宽捕兜底对齐 ①②④ 步家族形态（含 uuid.UUID 解析失败等非存储类异常——
            # 裸 ValueError 逃逸统一异常体系的口径收口，R1 审查 FR-4）
            raise CheckpointCreationError(
                plan_id=plan_id,
                checkpoint_no=checkpoint_no,
                reason=f"StrategicArchive 归档失败: {error}",
                cause=error,
            ) from error

        # ④ 快照构造+落库（build_snapshot 复用——13 键+checksum+TTL 30 天）
        snapshot = self.build_snapshot(
            plan_id=plan_id,
            checkpoint_no=checkpoint_no,
            stage_id=stage_id,
            compressed=compressed,
            summary=summary,
            completed=completed,
            created_via=created_via,
        )
        try:
            await self._snapshot_repository.save(snapshot)
        except Exception as error:
            raise CheckpointCreationError(
                plan_id=plan_id,
                checkpoint_no=checkpoint_no,
                reason=f"快照落库失败: {error}",
                cause=error,
            ) from error

        # ⑤ 发布 CheckpointReached（发布点唯一落位——OD-4；失败降级不回滚：
        #    快照是真相源，事件是通知面——与 6-1 快照写容错同语义）
        event = CheckpointReached(
            checkpoint_id=snapshot.snapshot_id,  # UUID 同型直传（R6-24）
            phase_identifier=stage_id,
            user_feedback_request=True,  # 阶段审批请求语义（AC-6 联动）
            metadata={"plan_id": plan_id},  # plan 关联经 metadata 顶层通道（OD-9）
        )
        try:
            await self._event_publisher.publish(event)
        except Exception as error:
            logger.warning(
                "CheckpointReached 发布降级（快照已落库不回滚）: session_id=%s error=%s",
                session_id,
                error,
            )

        logger.info(
            "Checkpoint 创建完成: plan_id=%s checkpoint_no=%s session_id=%s",
            plan_id,
            checkpoint_no,
            session_id,
        )
        return snapshot

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

        Args:
            plan_id: 规划任务标识。
            checkpoint_no: 检查点编号。
            stage_id: 阶段标识。
            compressed: 压缩产物（就绪态）。
            summary: 阶段摘要。
            completed: 完成状态。
            created_via: 触发源标识。

        Returns:
            封印 checksum 的完整形态快照（未落库）。
        """
        session_id = f"{CHECKPOINT_SESSION_PREFIX}{plan_id}:{checkpoint_no}"
        # stage_number 派生（R7-1："CP-n" 后缀解析→int n，不进签名不独立传参；
        # 经 _parse_checkpoint_number 守卫——性能直调路径（AC-8）同受格式/值域/规范三重校验）
        stage_number = _parse_checkpoint_number(checkpoint_no)

        # Checkpoint 聚合驱动点（OD-12 附则 a：④内 checksum 计算前、仅
        # completed=True 时构造聚合并调 complete()——status 映射进 completed 键；
        # completed=False 保持 IN_PROGRESS 不调 complete()（防死分支）；
        # 聚合为④内局部变量，构造后不落库——修正历史唯一存活面是
        # state_data.correction_history 键（R6-8））
        aggregate = Checkpoint(
            checkpoint_id=uuid.uuid4(),
            phase_identifier=stage_id,
            summary=summary,
            status=CheckpointStatus.IN_PROGRESS if not completed else CheckpointStatus.PENDING,
        )
        if completed:
            aggregate.complete()  # 守卫驱动：PENDING → COMPLETED

        state_data: dict[str, Any] = {
            "checkpoint_no": checkpoint_no,
            "stage_id": stage_id,
            "stage_number": stage_number,
            "plan_id": plan_id,
            "completed": completed,
            "summary": summary,
            "compressed_context": compressed.context,
            "compression_ratio": compressed.compression_ratio,
            "quality_score": compressed.quality_score,
            "token_count": compressed.token_count,
            "persistent_note_ref": compressed.persistent_note_ref,
            "correction_history": [],  # 键恒在（初始 []——6-2 键恒在纪律）
            "created_via": created_via,
        }
        snapshot = CheckpointSnapshot(
            session_id=session_id,
            stage_id=stage_id,
            state_version=0,  # 首建 v0（实体默认同构——R6-2；重复创建覆盖重置）
            state_data=state_data,
            ttl_seconds=CHECKPOINT_TTL_SECONDS,  # R8-F4 显式落值（30 天）
            persistent_note_ref=compressed.persistent_note_ref,
            snapshot_metadata={
                # 压缩元数据五键（R2A-10 双位同源——与 state_data 同一 CompressedContext 填充）
                "compression_ratio": compressed.compression_ratio,
                "quality_score": compressed.quality_score,
                "token_count": compressed.token_count,
                "original_token_count": compressed.original_token_count,
                "rerun_count": compressed.rerun_count,
            },
            checkpoint_no=checkpoint_no,
        )
        # checksum 显式计算写入（AC-3 初始化链——编排④步显式计算，构造器不自动算）
        return replace(snapshot, checksum=snapshot.calculate_checksum())

    async def apply_correction(
        self,
        *,
        session_id: str,
        correction: CorrectionRecord,
        expected_state_version: int,
    ) -> CheckpointSnapshot:
        """修正应用（AC-6——乐观锁式不可变更新+同键覆盖单版本存活）。

        Args:
            session_id: 快照会话键。
            correction: 修正记录（既有 CorrectionRecord 五字段）。
            expected_state_version: 调用方基线版本（乐观锁比对）。

        Returns:
            修正后的新版快照（state_version+1）。

        Raises:
            PlanningNotFoundError: 480——键不存在（含 JSON 损坏同路径统一承载）。
            PlanningStateError: 482——版本倒退/并发过期（第二触发点，R6-3）。
        """
        current = await self._load_or_480(session_id)

        # 乐观锁比对（版本倒退/并发过期 → 482 第二触发点——唯一构造通道）
        if current.state_version != expected_state_version:
            raise PlanningStateError(
                plan_id=str(current.state_data.get("plan_id", "")),
                transition=(
                    f"checkpoint_correction_version_conflict: expected={expected_state_version} actual={current.state_version}"
                ),
                message="Checkpoint 修正版本冲突（版本倒退/并发过期——请以最新快照重试）",
            )

        # CorrectionRecord 五字段 dict 投影（R8-F5：applied_at isoformat 字符串化）
        entry: dict[str, Any] = {
            "correction_type": correction.correction_type,
            "previous_value": correction.previous_value,
            "new_value": correction.new_value,
            "applied_by": correction.applied_by,
            "applied_at": correction.applied_at.isoformat(),
        }
        history = [*current.state_data.get("correction_history", []), entry]
        updated = current.with_updated_state({"correction_history": history})

        # checksum 重算替换（AC-3 重算点——载荷已变而 checksum 不重算则恒 verify 红）
        sealed = replace(updated, checksum=updated.calculate_checksum())
        await self._snapshot_repository.save(sealed)  # 单键单版本存活（覆盖同键，R3-T2）
        return sealed

    async def recover_checkpoint(self, *, plan_id: str, checkpoint_no: str) -> CheckpointRecoveryView:
        """恢复数据面（AC-7——load→verify→反序列化→视图组装；只读不驱动聚合）。

        Args:
            plan_id: 规划任务标识。
            checkpoint_no: 恢复起点检查点编号。

        Returns:
            恢复视图 DTO（6-6 消费面契约）。

        Raises:
            PlanningNotFoundError: 480——键不存在（含 JSON 损坏同路径）。
            CheckpointIntegrityError: 484——checksum 校验失败（拒绝恢复）。
            EntityValidationError: 242——checkpoint_no 格式/值域守卫（R1 审查 FR-2）。
        """
        # 入口守卫（fail-fast 先于 load——畸形编号零 IO）
        _parse_checkpoint_number(checkpoint_no)
        session_id = f"{CHECKPOINT_SESSION_PREFIX}{plan_id}:{checkpoint_no}"
        snapshot = await self._load_or_480(session_id)

        # 恢复入口强制先 verify_integrity（校验失败拒绝恢复——AC-3；
        # 实体纯判定不抛，484 抛出点在编排调用方）
        if not snapshot.verify_integrity():
            raise CheckpointIntegrityError(
                session_id=session_id,
                checkpoint_no=checkpoint_no,
                reason="checksum_mismatch",
                message="快照完整性校验失败（checksum 不匹配——疑似篡改或损坏），拒绝恢复",
            )

        # 后续 checkpoint 清单推导（R8-F1：值域 probe-load、非 None 升序入清单、
        # None 静默跳过——清单服务模式判定非完整性断言面；序号经入口守卫解析）
        current_number = _parse_checkpoint_number(checkpoint_no)
        subsequent: list[str] = []
        for candidate_number in range(current_number + 1, CHECKPOINT_NO_MAX + 1):
            candidate_session = f"{CHECKPOINT_SESSION_PREFIX}{plan_id}:CP-{candidate_number}"
            candidate = await self._snapshot_repository.load(candidate_session)
            if candidate is not None:
                subsequent.append(f"CP-{candidate_number}")

        mode = recommend_recovery_mode(len(subsequent))
        return CheckpointRecoveryView(
            checkpoint_no=checkpoint_no,
            stage=snapshot.stage_id,
            compressed_context=str(snapshot.state_data.get("compressed_context", "")),
            state_data=snapshot.state_data,
            correction_history=list(snapshot.state_data.get("correction_history", [])),
            subsequent_checkpoints=subsequent,
            recommended_mode=mode,
        )

    def recommend_recovery_mode(self, affected_checkpoint_count: int) -> RecoveryMode:
        """恢复模式建议（透传领域纯函数——判定逻辑单源在 domain）。

        Args:
            affected_checkpoint_count: 受影响的后续 Checkpoint 数量。

        Returns:
            RecoveryMode 枚举（REPLAY/OVERRIDE）。
        """
        return recommend_recovery_mode(affected_checkpoint_count)

    async def _load_or_480(self, session_id: str) -> CheckpointSnapshot:
        """快照读回或抛 480（键不存在与 JSON 损坏同路径统一承载——R1-D1/R6-22）。

        Args:
            session_id: 快照会话键。

        Returns:
            存活快照实体。

        Raises:
            PlanningNotFoundError: 480——load None（不存在/损坏不可区分）。
        """
        snapshot = await self._snapshot_repository.load(session_id)
        if snapshot is None:
            # R6-22 参数映射钦定：session_id 键填 plan_id 参数位 +
            # context_extra 承载「checkpoint 键不存在」语境
            raise PlanningNotFoundError(
                plan_id=session_id,
                context_extra={"reason": "checkpoint_key_not_found"},
            )
        return snapshot
