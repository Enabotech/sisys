"""Story 6-3 — CheckpointService 五步编排单元测试。

TDD 循环 A 载体：五步调用序（note→compress→archive→snapshot→publish，
OD-12）/persistent_note_ref 透传/TTL 30 天/state_data 13 键/事件构造字段/
发布失败不回滚/归档失败 483 包装/压缩终态门禁 fail-loud/build_snapshot
纯构造直测/created_via 透传。Mock 工厂模式（AsyncMock(spec=ProtocolClass)
——单元测试 Mock 端口，真实服务归集成/验收层）。
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.domain.services.context_compressor import CompressedContext

#: 编排层终态门禁阈值（AC-2——与 ContextCompressor 常量同值，测试侧独立字面量）
_GATE_RATIO = 0.70
_GATE_QUALITY = 0.70


def _make_compressed_context(
    *,
    compression_ratio: float = 0.85,
    quality_score: float = 0.82,
    persistent_note_ref: str | None = None,
) -> CompressedContext:
    """压缩产物工厂（全默认 frozen dataclass——双指标自由构造）。"""
    return CompressedContext(
        context="压缩后的战略语境摘要（固定产物）",
        compression_ratio=compression_ratio,
        quality_score=quality_score,
        token_count=320,
        original_token_count=2100,
        persistent_note_ref=persistent_note_ref or str(uuid.uuid4()),
        query="五年战略规划",
        key_entities=[{"name": "新能源", "type": "industry"}],
        rerun_count=0,
    )


def _make_persistent_note() -> Any:
    """持久化笔记工厂（persisted=True 形态——compress 前置校验可通过）。"""
    from datetime import UTC, datetime

    from src.domain.services.persistent_note_taker import PersistentNote

    return PersistentNote(
        query="五年战略规划",
        user_id="unit-executor",
        session_id="blm-checkpoint-plan:CP-1",
        entities=[{"name": "新能源", "type": "industry"}],
        summary={"digest": "战略语境笔记摘要"},
        lineage={"top_k": 3},
        persisted=True,
        persisted_at=datetime.now(UTC),
    )


def _make_service(
    *,
    compressed: CompressedContext | None = None,
    archive_side_effect: Exception | None = None,
    publish_side_effect: Exception | None = None,
    save_side_effect: Exception | None = None,
) -> tuple[Any, dict[str, Any]]:
    """CheckpointService 工厂（五依赖 AsyncMock(spec=)+调用序记录）。

    Returns:
        (被测服务, mock 字典)——调用序记录在 mocks["call_order"] 共享列表。
    """
    from src.application.services.checkpoint_service import CheckpointService
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.domain.events.publish_result import ChannelResult, PublishResult
    from src.domain.ports.event_publisher import EventPublisher
    from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
    from src.domain.services.context_compressor import ContextCompressor
    from src.domain.services.persistent_note_taker import PersistentNoteTaker

    call_order: list[str] = []

    note_taker = AsyncMock(spec=PersistentNoteTaker)

    async def _take_notes(**kwargs: Any) -> Any:
        call_order.append("take_notes")
        return _make_persistent_note()

    note_taker.take_notes = AsyncMock(side_effect=_take_notes)

    compressor = AsyncMock(spec=ContextCompressor)

    async def _compress(**kwargs: Any) -> CompressedContext:
        call_order.append("compress")
        return compressed if compressed is not None else _make_compressed_context()

    compressor.compress = AsyncMock(side_effect=_compress)

    archive_service = AsyncMock(spec=StrategicArchiveService)

    async def _archive_plan(**kwargs: Any) -> None:
        call_order.append("archive_plan")
        if archive_side_effect is not None:
            raise archive_side_effect

    archive_service.archive_plan = AsyncMock(side_effect=_archive_plan)

    snapshot_repository = AsyncMock(spec=SnapshotRepositoryProtocol)

    async def _save(snapshot: Any) -> None:
        call_order.append("save")
        if save_side_effect is not None:
            raise save_side_effect

    snapshot_repository.save = AsyncMock(side_effect=_save)

    publisher = AsyncMock(spec=EventPublisher)

    async def _publish(event: Any) -> PublishResult:
        call_order.append("publish")
        if publish_side_effect is not None:
            raise publish_side_effect
        return PublishResult(event_id=str(uuid.uuid4()), results=(ChannelResult("reliable", True),))

    publisher.publish = AsyncMock(side_effect=_publish)

    service = CheckpointService(
        note_taker=note_taker,
        compressor=compressor,
        archive_service=archive_service,
        snapshot_repository=snapshot_repository,
        event_publisher=publisher,
    )
    mocks = {
        "call_order": call_order,
        "note_taker": note_taker,
        "compressor": compressor,
        "archive_service": archive_service,
        "snapshot_repository": snapshot_repository,
        "publisher": publisher,
    }
    return service, mocks


async def _create(service: Any, **overrides: Any) -> Any:
    """create_checkpoint 直调辅助（默认参——编程调用形态）。"""
    kwargs: dict[str, Any] = {
        "plan_id": str(uuid.uuid4()),
        "checkpoint_no": "CP-1",
        "stage_id": "performance_gap",
        "query": "五年战略规划",
        "retrieved_docs": [{"id": "c-1", "score": 0.9, "payload": {"content": "证据"}}],
        "user_id": "unit-executor",
        "summary": "阶段摘要（直供）",
    }
    kwargs.update(overrides)
    return await service.create_checkpoint(**kwargs)


class TestCreateCheckpointFiveStepOrchestration:
    """五步编排调用序与产物契约（AC-1/AC-4/AC-5）。"""

    async def test_five_step_call_order(self) -> None:
        """调用序钦定：take_notes → compress → archive_plan → save → publish（OD-12）。"""
        service, mocks = _make_service()

        await _create(service)

        assert mocks["call_order"] == ["take_notes", "compress", "archive_plan", "save", "publish"]

    async def test_note_ref_passthrough_from_compressed(self) -> None:
        """persistent_note_ref 从压缩产物透传（系统公理二强制关联血缘）。"""
        note_ref = str(uuid.uuid4())
        service, _ = _make_service(compressed=_make_compressed_context(persistent_note_ref=note_ref))

        snapshot = await _create(service)

        assert snapshot.persistent_note_ref == note_ref
        assert snapshot.state_data["persistent_note_ref"] == note_ref

    async def test_ttl_30_days(self) -> None:
        """快照 TTL=2592000（30 天——R8-F4 build_snapshot 显式落值）。"""
        service, _ = _make_service()

        snapshot = await _create(service)

        assert snapshot.ttl_seconds == 2_592_000

    async def test_state_data_13_key_contract(self) -> None:
        """state_data 13 键契约（Task 0.2 冻结唯一版本）。"""
        service, _ = _make_service()

        snapshot = await _create(service)

        assert set(snapshot.state_data.keys()) == {
            "checkpoint_no",
            "stage_id",
            "stage_number",
            "plan_id",
            "completed",
            "summary",
            "compressed_context",
            "compression_ratio",
            "quality_score",
            "token_count",
            "persistent_note_ref",
            "correction_history",
            "created_via",
        }
        assert snapshot.state_data["checkpoint_no"] == "CP-1"
        assert snapshot.state_data["stage_number"] == 1  # "CP-1" 后缀解析派生（R7-1）
        assert snapshot.state_data["completed"] is True
        assert snapshot.state_data["correction_history"] == []  # 键恒在（6-2 键恒在纪律）
        assert snapshot.state_data["created_via"] == "use_case"  # 默认参（R6-4）

    async def test_session_id_checkpoint_prefix(self) -> None:
        """session_id = blm-checkpoint-{plan_id}:{checkpoint_no}（OD-3 双轨制独立键族）。"""
        plan_id = str(uuid.uuid4())
        service, _ = _make_service()

        snapshot = await _create(service, plan_id=plan_id)

        assert snapshot.session_id == f"blm-checkpoint-{plan_id}:CP-1"

    async def test_snapshot_checksum_sealed(self) -> None:
        """编排④步显式计算写入 checksum（不在构造器自动算——AC-3 初始化链）。"""
        service, _ = _make_service()

        snapshot = await _create(service)

        assert snapshot.checksum
        assert snapshot.verify_integrity() is True

    async def test_checkpoint_reached_event_fields(self) -> None:
        """事件构造字段：checkpoint_id=snapshot_id（UUID 直传同型）/phase_identifier/
        user_feedback_request=True/metadata.plan_id 关联（OD-9）。"""
        from src.domain.events.checkpoint_events import CheckpointReached

        plan_id = str(uuid.uuid4())
        service, mocks = _make_service()

        snapshot = await _create(service, plan_id=plan_id)

        mocks["publisher"].publish.assert_awaited_once()
        event = mocks["publisher"].publish.await_args.args[0]
        assert isinstance(event, CheckpointReached)
        assert event.checkpoint_id == snapshot.snapshot_id  # UUID 同型直传（R6-24）
        assert isinstance(event.checkpoint_id, uuid.UUID)
        assert event.phase_identifier == "performance_gap"
        assert event.user_feedback_request is True
        assert event.metadata.get("plan_id") == plan_id
        assert event.metadata.get("checkpoint_no") == "CP-1"  # R3-3：双关联键（6-6 免 probe 反查）

    async def test_step1_validation_error_passthrough(self) -> None:
        """①步 242 透传（R3-5——take_notes 抛 242 原样透传非 483 包装，同族断言面补齐）。"""
        from src.domain.exceptions import EntityValidationError

        service, mocks = _make_service()

        async def _note_fails(**kwargs: Any) -> Any:
            mocks["call_order"].append("take_notes")
            raise EntityValidationError(message="笔记守卫", context={"step": "take_notes"})

        mocks["note_taker"].take_notes = AsyncMock(side_effect=_note_fails)

        with pytest.raises(EntityValidationError) as exc_info:
            await _create(service)

        assert exc_info.value.code == "EXCEPTION_242"
        assert mocks["call_order"] == ["take_notes"]  # ①即拦截，②③④⑤零触达

    async def test_step3_validation_error_passthrough(self) -> None:
        """③步 242 透传（R3-5——archive_plan 入口守卫（plan_type/validate）242 透传契约的直接承载）。"""
        from src.domain.exceptions import EntityValidationError

        archive_error = EntityValidationError(message="plan_type 守卫", context={"step": "archive"})
        service, mocks = _make_service(archive_side_effect=archive_error)

        with pytest.raises(EntityValidationError) as exc_info:
            await _create(service)

        assert exc_info.value.code == "EXCEPTION_242"
        assert mocks["call_order"] == ["take_notes", "compress", "archive_plan"]  # ③即拦截，④⑤零触达

    async def test_archive_payload_mapping(self) -> None:
        """归档载荷映射（Task 0.8② 冻结）：compressed_context→evidence_blob bytes/
        笔记 entities/summary/lineage→assumptions/checkpoint_no→decision_basis/
        plan_type="SP"（R6-1）。"""
        plan_id = str(uuid.uuid4())
        service, mocks = _make_service()

        await _create(service, plan_id=plan_id)

        mocks["archive_service"].archive_plan.assert_awaited_once()
        kwargs = mocks["archive_service"].archive_plan.await_args.kwargs
        assert str(kwargs["plan_id"]) == plan_id
        assert kwargs["plan_type"] == "SP"
        compressed_context = _make_compressed_context().context
        assert kwargs["evidence_blob"] == compressed_context.encode("utf-8")
        assert kwargs["decision_basis"]["checkpoint_no"] == "CP-1"  # R8-F3 语境锚
        assert "compressed_context" in kwargs["decision_basis"]
        assert kwargs["assumptions"]["entities"]  # 笔记 Top-20 实体入档

    async def test_publish_failure_does_not_rollback_snapshot(self) -> None:
        """发布失败不回滚快照落库（快照是真相源，事件是通知面——降级日志）。"""
        service, mocks = _make_service(publish_side_effect=RuntimeError("bus broken"))

        snapshot = await _create(service)

        assert snapshot is not None  # 不抛——发布失败降级
        mocks["snapshot_repository"].save.assert_awaited_once()  # save 先于 publish 且未被回滚

    async def test_archive_storage_error_wrapped_483_no_snapshot(self) -> None:
        """归档 ArchiveStorageError(284) → 483 包装透传 + save 零调用（无半成品）。"""
        from src.domain.exceptions import ArchiveStorageError, CheckpointCreationError

        service, mocks = _make_service(archive_side_effect=ArchiveStorageError(layer="l4"))

        with pytest.raises(CheckpointCreationError) as exc_info:
            await _create(service)

        assert exc_info.value.code == "EXCEPTION_483"
        assert exc_info.value.cause is not None
        mocks["snapshot_repository"].save.assert_not_awaited()  # 快照零落库
        assert "publish" not in mocks["call_order"]

    async def test_compression_final_gate_ratio_fail_raises_483(self) -> None:
        """压缩终态门禁：二次路径耗尽 compression_ratio<0.70 → 483 + save/archive 零调用（R1-F2 fail-loud）。"""
        from src.domain.exceptions import CheckpointCreationError

        service, mocks = _make_service(
            compressed=_make_compressed_context(
                compression_ratio=0.55, quality_score=0.90, persistent_note_ref=str(uuid.uuid4())
            )
        )

        with pytest.raises(CheckpointCreationError) as exc_info:
            await _create(service)

        assert exc_info.value.code == "EXCEPTION_483"
        assert "compression_ratio" in exc_info.value.context["reason"]
        mocks["archive_service"].archive_plan.assert_not_awaited()
        mocks["snapshot_repository"].save.assert_not_awaited()
        assert mocks["call_order"] == ["take_notes", "compress"]  # 门禁在②后③前拦截

    async def test_compression_final_gate_quality_fail_raises_483(self) -> None:
        """终态门禁质量维度：quality_score<0.70 → 483（evaluator 注入在位——全口径）。"""
        from src.domain.exceptions import CheckpointCreationError

        service, _ = _make_service(
            compressed=_make_compressed_context(
                compression_ratio=0.90, quality_score=0.40, persistent_note_ref=str(uuid.uuid4())
            )
        )

        with pytest.raises(CheckpointCreationError) as exc_info:
            await _create(service)

        assert exc_info.value.code == "EXCEPTION_483"
        assert "quality_score" in exc_info.value.context["reason"]

    async def test_entity_validation_error_passthrough(self) -> None:
        """未持久化笔记压缩 → 既有 EntityValidationError(242) 零回归透传（不包装 483）。"""
        from src.domain.exceptions import EntityValidationError

        service, mocks = _make_service()
        mocks["compressor"].compress = AsyncMock(
            side_effect=EntityValidationError(message="Compression requires persistent note to be persisted first")
        )

        with pytest.raises(EntityValidationError):
            await _create(service)

    async def test_snapshot_save_failure_raises_483(self) -> None:
        """④快照落库失败 → 483（强制环节零吞错）。"""
        from src.domain.exceptions import CheckpointCreationError, StorageError

        service, _ = _make_service(save_side_effect=StorageError("redis down"))

        with pytest.raises(CheckpointCreationError) as exc_info:
            await _create(service)

        assert exc_info.value.code == "EXCEPTION_483"


class TestBuildSnapshotPureConstruction:
    """build_snapshot 纯构造直测（R6-5——④步构造逻辑单列，性能采样直调两段）。"""

    def test_build_snapshot_13_keys_and_checksum(self) -> None:
        """直调断言 13 键+checksum 计算在位+stage_number 派生+TTL 落值。"""

        service, _ = _make_service()
        plan_id = str(uuid.uuid4())
        compressed = _make_compressed_context()

        snapshot = service.build_snapshot(
            plan_id=plan_id,
            checkpoint_no="CP-3",
            stage_id="market_insight_market_customer",
            compressed=compressed,
            summary="构造直测摘要",
            completed=True,
            created_via="cli",
        )

        assert snapshot.session_id == f"blm-checkpoint-{plan_id}:CP-3"
        assert snapshot.state_data["stage_number"] == 3  # "CP-3" 后缀解析（R7-1）
        assert snapshot.state_data["created_via"] == "cli"
        assert snapshot.state_data["completed"] is True
        assert snapshot.ttl_seconds == 2_592_000
        assert snapshot.checksum == snapshot.calculate_checksum()  # checksum 计算含在构造内（R6-5）
        assert snapshot.verify_integrity() is True
        assert set(snapshot.state_data.keys()) == {
            "checkpoint_no",
            "stage_id",
            "stage_number",
            "plan_id",
            "completed",
            "summary",
            "compressed_context",
            "compression_ratio",
            "quality_score",
            "token_count",
            "persistent_note_ref",
            "correction_history",
            "created_via",
        }

    def test_build_snapshot_metadata_five_keys(self) -> None:
        """snapshot_metadata 压缩元数据五键（R2A-10 双位同源）。"""

        service, _ = _make_service()

        snapshot = service.build_snapshot(
            plan_id=str(uuid.uuid4()),
            checkpoint_no="CP-1",
            stage_id="performance_gap",
            compressed=_make_compressed_context(),
            summary="s",
            completed=False,
            created_via="use_case",
        )

        assert set(snapshot.snapshot_metadata.keys()) == {
            "compression_ratio",
            "quality_score",
            "token_count",
            "original_token_count",
            "rerun_count",
        }

    def test_build_snapshot_incompleted_maps_false(self) -> None:
        """completed=False → state_data.completed=False（聚合保持 IN_PROGRESS 不调 complete——死分支防线）。"""

        service, _ = _make_service()

        snapshot = service.build_snapshot(
            plan_id=str(uuid.uuid4()),
            checkpoint_no="CP-1",
            stage_id="performance_gap",
            compressed=_make_compressed_context(),
            summary="s",
            completed=False,
            created_via="use_case",
        )

        assert snapshot.state_data["completed"] is False

    def test_build_snapshot_no_side_effects(self) -> None:
        """纯构造无副作用（save/publish 零调用——性能采样窗口同构的前提）。"""
        service, mocks = _make_service()

        service.build_snapshot(
            plan_id=str(uuid.uuid4()),
            checkpoint_no="CP-1",
            stage_id="performance_gap",
            compressed=_make_compressed_context(),
            summary="s",
            completed=True,
            created_via="use_case",
        )

        assert mocks["call_order"] == []  # 纯构造零端口调用


class TestApplyCorrection:
    """修正应用（AC-6——乐观锁+不可变更新+同键覆盖单版本存活）。"""

    def _make_service_with_store(self) -> tuple[Any, dict[str, Any]]:
        """带内存快照存储的服务工厂（save 覆盖同键、load 读最新——单键单版本）。"""
        service, mocks = _make_service()
        store: dict[str, Any] = {}
        mocks["snapshot_repository"].load = AsyncMock(side_effect=lambda session_id: store.get(session_id))

        async def _save(snapshot: Any) -> None:
            store[snapshot.session_id] = snapshot

        mocks["snapshot_repository"].save = AsyncMock(side_effect=_save)
        mocks["store"] = store
        return service, mocks

    def _seed_snapshot(self, service: Any, mocks: dict[str, Any]) -> Any:
        """种入一份完整形态快照（build_snapshot 构造+v0）。"""
        snapshot = service.build_snapshot(
            plan_id=str(uuid.uuid4()),
            checkpoint_no="CP-1",
            stage_id="performance_gap",
            compressed=_make_compressed_context(),
            summary="阶段摘要",
            completed=True,
            created_via="use_case",
        )
        mocks["store"][snapshot.session_id] = snapshot
        return snapshot

    async def test_correction_appends_history_and_increments_version(self) -> None:
        """修正应用 → state_version+1 + correction_history 追加 + 原字段保留 + 血缘保留。"""
        from datetime import UTC, datetime

        from src.domain.entities.checkpoint import CorrectionRecord

        service, mocks = self._make_service_with_store()
        seeded = self._seed_snapshot(service, mocks)

        corrected = await service.apply_correction(
            session_id=seeded.session_id,
            correction=CorrectionRecord(
                correction_type="key_param",
                previous_value="达成率 87%",
                new_value="达成率 90%",
                applied_by="exec-001",
                applied_at=datetime.now(UTC),
            ),
            expected_state_version=0,  # 首建 v0（R6-2 基线）
        )

        assert seeded.state_version == 0
        assert corrected.state_version == 1  # v0 → v1（修正链 +1）
        history = corrected.state_data["correction_history"]
        assert len(history) == 1
        assert history[0]["correction_type"] == "key_param"
        assert history[0]["applied_by"] == "exec-001"
        assert isinstance(history[0]["applied_at"], str)  # isoformat 字符串化（R8-F5）
        # 原快照字段保留（with_updated_state 合并语义）
        assert corrected.state_data["summary"] == seeded.state_data["summary"]
        assert corrected.state_data["plan_id"] == seeded.state_data["plan_id"]
        # 血缘保留（修正不换笔记）
        assert corrected.state_data["persistent_note_ref"] == seeded.state_data["persistent_note_ref"]

    async def test_correction_recalculates_checksum_roundtrip_green(self) -> None:
        """修正后 checksum 重算替换 → round-trip verify 绿（AC-3 重算点闭环）。"""
        from src.domain.entities.checkpoint import CorrectionRecord

        service, mocks = self._make_service_with_store()
        seeded = self._seed_snapshot(service, mocks)

        corrected = await service.apply_correction(
            session_id=seeded.session_id,
            correction=CorrectionRecord(correction_type="k", previous_value="a", new_value="b", applied_by="e"),
            expected_state_version=0,
        )

        assert corrected.verify_integrity() is True, "修正后 checksum 未重算（verify 恒红——重算点缺失）"

    async def test_correction_overwrites_same_key_single_version_alive(self) -> None:
        """同键覆盖单版本存活（R6-18）：修正 save 后 load 同键——仅存新版本且历史全量。"""
        from src.domain.entities.checkpoint import CorrectionRecord

        service, mocks = self._make_service_with_store()
        seeded = self._seed_snapshot(service, mocks)

        first = await service.apply_correction(
            session_id=seeded.session_id,
            correction=CorrectionRecord(correction_type="c1", previous_value="a", new_value="b", applied_by="e"),
            expected_state_version=0,
        )
        second = await service.apply_correction(
            session_id=seeded.session_id,
            correction=CorrectionRecord(correction_type="c2", previous_value="b", new_value="c", applied_by="e"),
            expected_state_version=first.state_version,
        )
        assert second.state_version == 2

        loaded = await mocks["snapshot_repository"].load(seeded.session_id)
        assert loaded is not None
        assert loaded.state_version == 2  # v0→v1→v2
        assert len(loaded.state_data["correction_history"]) == 2  # 全代际累积（R3-T2 键内承载）
        assert [entry["correction_type"] for entry in loaded.state_data["correction_history"]] == ["c1", "c2"]

    async def test_correction_version_rollback_raises_482_two_step(self) -> None:
        """482 第二触发点（两步构造法 R6-2/R6-3）：先 expected=0 对 v0 通过产 v1，
        再对存活 v1 传 expected=0（低于存活版本）→ 482。"""
        from src.domain.entities.checkpoint import CorrectionRecord
        from src.domain.exceptions import PlanningStateError

        service, mocks = self._make_service_with_store()
        seeded = self._seed_snapshot(service, mocks)

        # 第一步：v0 → v1（匹配通过）
        corrected = await service.apply_correction(
            session_id=seeded.session_id,
            correction=CorrectionRecord(correction_type="c1", previous_value="a", new_value="b", applied_by="e"),
            expected_state_version=0,
        )
        assert corrected.state_version == 1  # 红测断言修正链版本递增值为 0→1 而非 1→2

        # 第二步：对存活 v1 传 expected=0（版本倒退）→ 482
        with pytest.raises(PlanningStateError) as exc_info:
            await service.apply_correction(
                session_id=seeded.session_id,
                correction=CorrectionRecord(correction_type="stale", previous_value="x", new_value="y", applied_by="e"),
                expected_state_version=0,
            )

        assert exc_info.value.code == "EXCEPTION_482"
        assert "version" in exc_info.value.context["transition"]

    async def test_correction_concurrent_stale_raises_482(self) -> None:
        """并发过期（expected 高于存活版本）→ 482（乐观锁双向比较）。"""
        from src.domain.entities.checkpoint import CorrectionRecord
        from src.domain.exceptions import PlanningStateError

        service, mocks = self._make_service_with_store()
        seeded = self._seed_snapshot(service, mocks)

        with pytest.raises(PlanningStateError):
            await service.apply_correction(
                session_id=seeded.session_id,
                correction=CorrectionRecord(correction_type="c", previous_value="a", new_value="b", applied_by="e"),
                expected_state_version=5,  # 高于存活 v0（并发过期）
            )

    async def test_correction_missing_key_raises_480(self) -> None:
        """修正面键不存在 → 480（load None 语义统一承载）。"""
        from src.domain.entities.checkpoint import CorrectionRecord
        from src.domain.exceptions import PlanningNotFoundError

        service, mocks = self._make_service_with_store()

        with pytest.raises(PlanningNotFoundError) as exc_info:
            await service.apply_correction(
                session_id="blm-checkpoint-missing:CP-1",
                correction=CorrectionRecord(correction_type="c", previous_value="a", new_value="b", applied_by="e"),
                expected_state_version=0,
            )

        assert exc_info.value.code == "EXCEPTION_480"
        assert exc_info.value.context["reason"] == "checkpoint_key_not_found"  # R6-22 语境承载


class TestRecoverCheckpoint:
    """恢复数据面（AC-7——load→verify→视图组装+后续清单推导+判定透传）。"""

    def _make_service_with_store(self) -> tuple[Any, dict[str, Any]]:
        """带内存存储的服务工厂（形态同 TestApplyCorrection）。"""
        service, mocks = _make_service()
        store: dict[str, Any] = {}
        mocks["snapshot_repository"].load = AsyncMock(side_effect=lambda session_id: store.get(session_id))

        async def _save(snapshot: Any) -> None:
            store[snapshot.session_id] = snapshot

        mocks["snapshot_repository"].save = AsyncMock(side_effect=_save)
        mocks["store"] = store
        return service, mocks

    def _seed(self, service: Any, mocks: dict[str, Any], plan_id: str, checkpoint_no: str) -> Any:
        """种入指定编号快照（build_snapshot+v0）。"""
        snapshot = service.build_snapshot(
            plan_id=plan_id,
            checkpoint_no=checkpoint_no,
            stage_id=f"stage_{checkpoint_no}",
            compressed=_make_compressed_context(),
            summary=f"{checkpoint_no} 摘要",
            completed=True,
        )
        mocks["store"][snapshot.session_id] = snapshot
        return snapshot

    async def test_recovery_view_key_contract(self) -> None:
        """恢复视图 DTO 7 键契约（Task 0 冻结——6-6 消费面）。"""
        from dataclasses import fields as dc_fields

        from src.application.ports.checkpoint import CheckpointRecoveryView

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        self._seed(service, mocks, plan_id, "CP-1")

        view = await service.recover_checkpoint(plan_id=plan_id, checkpoint_no="CP-1")

        assert isinstance(view, CheckpointRecoveryView)
        assert {field.name for field in dc_fields(view)} == {
            "checkpoint_no",
            "stage",
            "compressed_context",
            "state_data",
            "correction_history",
            "subsequent_checkpoints",
            "recommended_mode",
            "state_version",  # R3-2：6-6 修正面乐观锁基线
            "snapshot_id",  # R3-2：事件关联比对用
        }

    async def test_recovery_subsequent_and_mode_boundary(self) -> None:
        """后续清单 probe-load 推导升序 + 判定边界（1<2 override / 2≥2 replay）。"""
        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        for checkpoint_no in ("CP-1", "CP-3", "CP-5"):
            self._seed(service, mocks, plan_id, checkpoint_no)

        view_cp3 = await service.recover_checkpoint(plan_id=plan_id, checkpoint_no="CP-3")
        assert view_cp3.subsequent_checkpoints == ["CP-5"]  # 升序、CP-2/CP-4 缺失静默跳过
        assert view_cp3.recommended_mode == "override"  # 1 < 2

        view_cp1 = await service.recover_checkpoint(plan_id=plan_id, checkpoint_no="CP-1")
        assert view_cp1.subsequent_checkpoints == ["CP-3", "CP-5"]
        assert view_cp1.recommended_mode == "replay"  # 恰 2 强制（边界）

    async def test_recovery_view_payload(self) -> None:
        """恢复视图载荷（compressed_context/state_data/correction_history/stage）。"""
        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        self._seed(service, mocks, plan_id, "CP-1")

        view = await service.recover_checkpoint(plan_id=plan_id, checkpoint_no="CP-1")

        assert view.stage == "stage_CP-1"
        assert view.compressed_context == _make_compressed_context().context
        assert view.state_data["checkpoint_no"] == "CP-1"
        assert view.correction_history == []

    async def test_recovery_view_version_and_snapshot_id_filled(self) -> None:
        """恢复视图 state_version/snapshot_id 填充值正确（R3-2 值级断言——防「忘填用默认值」零检出）。"""
        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        seeded = self._seed(service, mocks, plan_id, "CP-1")

        # 修正确认一轮使版本递增（v0→v1——验证非默认值的真实透传）
        from src.domain.entities.checkpoint import CorrectionRecord

        updated = await service.apply_correction(
            session_id=seeded.session_id,
            correction=CorrectionRecord(correction_type="c", previous_value="a", new_value="b", applied_by="e"),
            expected_state_version=0,
        )

        view = await service.recover_checkpoint(plan_id=plan_id, checkpoint_no="CP-1")
        assert view.state_version == updated.state_version == 1  # 值级（非默认 0）
        assert view.snapshot_id == str(updated.snapshot_id)  # 与事件 checkpoint_id 序列化面同形态

    async def test_recovery_cp8_upper_boundary_empty_subsequent(self) -> None:
        """CP-8 上界恢复：range(9,9) 空清单 → OVERRIDE（R3-5——上界 probe 路径直接承载）。"""
        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        self._seed(service, mocks, plan_id, "CP-8")

        view = await service.recover_checkpoint(plan_id=plan_id, checkpoint_no="CP-8")

        assert view.subsequent_checkpoints == []  # 上界后无候选
        assert view.recommended_mode == "override"

    async def test_apply_correction_on_tampered_snapshot_raises_484(self) -> None:
        """篡改快照修正 → 484 拒绝且零写回（R3-1——防 checksum 封印洗白）。"""
        from dataclasses import replace as dc_replace

        from src.domain.entities.checkpoint import CorrectionRecord
        from src.domain.exceptions import CheckpointIntegrityError

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        seeded = self._seed(service, mocks, plan_id, "CP-1")

        tampered_state = dict(seeded.state_data)
        tampered_state["compressed_context"] = "被篡改的压缩上下文"
        mocks["store"][seeded.session_id] = dc_replace(seeded, state_data=tampered_state)

        with pytest.raises(CheckpointIntegrityError) as exc_info:
            await service.apply_correction(
                session_id=seeded.session_id,
                correction=CorrectionRecord(correction_type="c", previous_value="a", new_value="b", applied_by="e"),
                expected_state_version=0,
            )

        assert exc_info.value.code == "EXCEPTION_484"
        assert exc_info.value.context["reason"] == "checksum_mismatch_before_correction"
        # 零写回：correction_history 未追加（store 内仍是篡改态单条）
        assert mocks["store"][seeded.session_id].state_data.get("correction_history") == []

    async def test_apply_correction_tampered_note_ref_raises_484(self) -> None:
        """篡改 persistent_note_ref 的修正 → 484（血缘伪造不可经修正面洗白——R3-1）。"""
        from dataclasses import replace as dc_replace

        from src.domain.entities.checkpoint import CorrectionRecord
        from src.domain.exceptions import CheckpointIntegrityError

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        seeded = self._seed(service, mocks, plan_id, "CP-1")

        tampered_state = dict(seeded.state_data)
        tampered_state["persistent_note_ref"] = str(uuid.uuid4())  # 伪造血缘
        mocks["store"][seeded.session_id] = dc_replace(seeded, state_data=tampered_state)

        with pytest.raises(CheckpointIntegrityError):
            await service.apply_correction(
                session_id=seeded.session_id,
                correction=CorrectionRecord(correction_type="c", previous_value="a", new_value="b", applied_by="e"),
                expected_state_version=0,
            )

    async def test_apply_correction_tampered_plus_version_mismatch_prefers_484(self) -> None:
        """篡改+版本不匹配并存 → 484 优先非 482（R3-1——完整性优先于并发语义钉死）。"""
        from dataclasses import replace as dc_replace

        from src.domain.entities.checkpoint import CorrectionRecord
        from src.domain.exceptions import CheckpointIntegrityError

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        seeded = self._seed(service, mocks, plan_id, "CP-1")

        tampered_state = dict(seeded.state_data)
        tampered_state["summary"] = "被篡改的摘要"
        mocks["store"][seeded.session_id] = dc_replace(seeded, state_data=tampered_state)

        with pytest.raises(CheckpointIntegrityError) as exc_info:
            await service.apply_correction(
                session_id=seeded.session_id,
                correction=CorrectionRecord(correction_type="c", previous_value="a", new_value="b", applied_by="e"),
                expected_state_version=99,  # 版本同时不匹配——484 仍优先
            )

        assert exc_info.value.code == "EXCEPTION_484"

    async def test_recovery_missing_key_raises_480(self) -> None:
        """不存在键恢复 → 480（含 JSON 损坏同路径统一承载——Task 0.3 钦定）。"""
        from src.domain.exceptions import PlanningNotFoundError

        service, mocks = self._make_service_with_store()

        with pytest.raises(PlanningNotFoundError) as exc_info:
            await service.recover_checkpoint(plan_id=str(uuid.uuid4()), checkpoint_no="CP-8")

        assert exc_info.value.code == "EXCEPTION_480"
        assert exc_info.value.context["reason"] == "checkpoint_key_not_found"

    async def test_recovery_corrupted_checksum_raises_484(self) -> None:
        """损坏快照（读回后篡改 state_data 再存——checksum 不匹配）→ 484 拒绝恢复。"""
        from dataclasses import replace as dc_replace

        from src.domain.exceptions import CheckpointIntegrityError

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        seeded = self._seed(service, mocks, plan_id, "CP-1")

        tampered_state = dict(seeded.state_data)
        tampered_state["compressed_context"] = "被篡改的压缩上下文"
        mocks["store"][seeded.session_id] = dc_replace(seeded, state_data=tampered_state)

        with pytest.raises(CheckpointIntegrityError) as exc_info:
            await service.recover_checkpoint(plan_id=plan_id, checkpoint_no="CP-1")

        assert exc_info.value.code == "EXCEPTION_484"
        assert exc_info.value.context["reason"] == "checksum_mismatch"

    async def test_recovery_mode_pure_function_passthrough(self) -> None:
        """判定纯函数透传（后续清单计数 → recommend_recovery_mode）。"""
        service, _ = _make_service()

        assert service.recommend_recovery_mode(0).value == "override"
        assert service.recommend_recovery_mode(2).value == "replay"


class TestCheckpointNoGuard:
    """checkpoint_no 三重守卫（R1 审查 FR-2——格式/值域/规范形态）。

    实测背景：守卫缺失时 'garbage' 裸抛 IndexError、'CP-abc' 裸抛 ValueError
    逃逸统一异常体系；'CP-99' 静默通过以 30 天 TTL 落库垃圾数据。守卫承载位
    = 服务层三落位（create 入口 fail-fast / build_snapshot 直调面 / recover 入口）。
    """

    @pytest.mark.parametrize(
        "invalid_no",
        ["garbage", "CP-abc", "cp-1", "CP-", "", "CP-0", "CP-9", "CP-99", "CP-01", "CP-00"],
    )
    async def test_create_invalid_checkpoint_no_raises_242(self, invalid_no: str) -> None:
        """create 入口守卫：畸形/值域外/非规范形态 → 242（fail-loud）。"""
        from src.domain.exceptions import EntityValidationError

        service, mocks = _make_service()
        with pytest.raises(EntityValidationError) as exc_info:
            await service.create_checkpoint(
                plan_id=str(uuid.uuid4()),
                checkpoint_no=invalid_no,
                stage_id="performance_gap",
                query="q",
                retrieved_docs=[],
                user_id="u",
                summary="s",
            )

        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "checkpoint_no"

    async def test_create_guard_fires_before_step_one(self) -> None:
        """守卫先于①（fail-fast）——畸形编号零副作用零调用（LLM/归档不白耗）。"""
        from src.domain.exceptions import EntityValidationError

        service, mocks = _make_service()
        with pytest.raises(EntityValidationError):
            await service.create_checkpoint(
                plan_id=str(uuid.uuid4()),
                checkpoint_no="garbage",
                stage_id="performance_gap",
                query="q",
                retrieved_docs=[],
                user_id="u",
                summary="s",
            )

        assert mocks["call_order"] == []  # 守卫拦截在五步链之前

    @pytest.mark.parametrize("invalid_no", ["garbage", "CP-abc", "CP-0", "CP-9", "CP-01"])
    def test_build_snapshot_invalid_checkpoint_no_raises_242(self, invalid_no: str) -> None:
        """build_snapshot 直调面守卫（AC-8 性能采样路径同受校验）。"""
        from src.domain.exceptions import EntityValidationError

        service, _ = _make_service()
        with pytest.raises(EntityValidationError):
            service.build_snapshot(
                plan_id=str(uuid.uuid4()),
                checkpoint_no=invalid_no,
                stage_id="performance_gap",
                compressed=_make_compressed_context(),
                summary="s",
                completed=True,
            )

    @pytest.mark.parametrize("invalid_no", ["garbage", "CP-abc", "CP-0", "CP-9", "CP-01"])
    async def test_recover_invalid_checkpoint_no_raises_242(self, invalid_no: str) -> None:
        """recover 入口守卫（fail-fast 先于 load——畸形编号零 IO）。"""
        from src.domain.exceptions import EntityValidationError

        service, mocks = _make_service()
        load_calls: list[str] = []
        mocks["snapshot_repository"].load = AsyncMock(side_effect=lambda session_id: load_calls.append(session_id))

        with pytest.raises(EntityValidationError):
            await service.recover_checkpoint(plan_id=str(uuid.uuid4()), checkpoint_no=invalid_no)

        assert load_calls == []  # 守卫拦截在 load 之前

    @pytest.mark.parametrize("valid_no", ["CP-1", "CP-8"])
    def test_valid_checkpoint_numbers_pass(self, valid_no: str) -> None:
        """值域边界合法形态通过（CP-1 下界/CP-8 上界——canonical 形态）。"""
        service, _ = _make_service()
        snapshot = service.build_snapshot(
            plan_id=str(uuid.uuid4()),
            checkpoint_no=valid_no,
            stage_id="performance_gap",
            compressed=_make_compressed_context(),
            summary="s",
            completed=True,
        )
        assert snapshot.checkpoint_no == valid_no


class TestListCheckpoints:
    """读面 list_checkpoints（Story 6-6 AC-1——全量 probe+sync join+8 键 VO）。

    延迟 import 形态：方法/VO 未定义时红 = 运行期 AttributeError/ImportError。
    """

    def _make_service_with_store(self) -> tuple[Any, dict[str, Any]]:
        """带内存存储的服务工厂（形态同 TestRecoverCheckpoint）。"""
        service, mocks = _make_service()
        store: dict[str, Any] = {}
        mocks["snapshot_repository"].load = AsyncMock(side_effect=lambda session_id: store.get(session_id))

        async def _save(snapshot: Any) -> None:
            store[snapshot.session_id] = snapshot

        mocks["snapshot_repository"].save = AsyncMock(side_effect=_save)
        mocks["store"] = store
        return service, mocks

    def _seed(self, service: Any, mocks: dict[str, Any], plan_id: str, checkpoint_no: str) -> Any:
        """种入指定编号快照（build_snapshot+v0——stage 用 performance_gap 值域）。"""
        snapshot = service.build_snapshot(
            plan_id=plan_id,
            checkpoint_no=checkpoint_no,
            stage_id="performance_gap",
            compressed=_make_compressed_context(),
            summary=f"{checkpoint_no} 摘要",
            completed=True,
        )
        mocks["store"][snapshot.session_id] = snapshot
        return snapshot

    def _seed_recovery_record(self, mocks: dict[str, Any], plan_id: str, state_data: dict[str, Any]) -> None:
        """种入恢复记录（第三键族——blm-checkpoint-recovery-{plan}，checkpoint_no 空）。"""
        from datetime import UTC, datetime

        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        record = CheckpointSnapshot(
            session_id=f"blm-checkpoint-recovery-{plan_id}",
            stage_id="recovery_record",
            state_version=0,
            state_data=state_data,
            timestamp=datetime.now(UTC),
            ttl_seconds=2_592_000,
            checkpoint_no="",
        )
        mocks["store"][record.session_id] = record

    async def test_list_probe_full_ascending_with_eight_keys(self) -> None:
        """全量 probe（CP-1 起）+升序+8 键 exact set（R8-F1 增量模式的全量扩展）。"""
        from dataclasses import fields as dc_fields

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        for checkpoint_no in ("CP-5", "CP-1", "CP-3"):  # 乱序种入验证升序输出
            self._seed(service, mocks, plan_id, checkpoint_no)

        summaries = await service.list_checkpoints(plan_id=plan_id)

        assert [s.checkpoint_no for s in summaries] == ["CP-1", "CP-3", "CP-5"]
        for summary in summaries:
            assert {field.name for field in dc_fields(summary)} == {
                "checkpoint_no",
                "stage_id",
                "completed",
                "summary",
                "state_version",
                "created_via",
                "timestamp",
                "sync_status",
            }

    async def test_list_entries_payload_values(self) -> None:
        """条目载荷值（stage/summary/completed/state_version/created_via 直投影）。"""
        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        seeded = self._seed(service, mocks, plan_id, "CP-1")

        summaries = await service.list_checkpoints(plan_id=plan_id)
        entry = summaries[0]

        assert entry.stage_id == "performance_gap"
        assert entry.summary == "CP-1 摘要"
        assert entry.completed is True
        assert entry.state_version == seeded.state_version
        assert entry.created_via == "use_case"

    async def test_list_timestamp_isoformat_string(self) -> None:
        """timestamp 是 isoformat 字符串（实体 datetime→VO str 转换的漂移哨兵——
        返回 datetime 对象即红）。"""
        from datetime import datetime

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        self._seed(service, mocks, plan_id, "CP-1")

        summaries = await service.list_checkpoints(plan_id=plan_id)
        timestamp = summaries[0].timestamp

        assert isinstance(timestamp, str), f"timestamp 实测类型={type(timestamp)} 期望 str（isoformat 转换）"
        assert timestamp  # 非空
        parsed = datetime.fromisoformat(timestamp)  # 可解析（合法 isoformat）
        assert parsed.tzinfo is not None

    async def test_list_no_recovery_record_all_in_sync(self) -> None:
        """无恢复记录→全量 in_sync（键恒在纪律的读侧镜像）。"""
        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        for checkpoint_no in ("CP-1", "CP-3", "CP-5"):
            self._seed(service, mocks, plan_id, checkpoint_no)

        summaries = await service.list_checkpoints(plan_id=plan_id)

        assert [s.sync_status for s in summaries] == ["in_sync", "in_sync", "in_sync"]

    async def test_list_sync_status_override_pending(self) -> None:
        """sync 三态推导矩阵——Override 恢复记录（恢复起点恒 in_sync+后续 pending_sync）。"""
        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        for checkpoint_no in ("CP-1", "CP-3", "CP-5"):
            self._seed(service, mocks, plan_id, checkpoint_no)
        self._seed_recovery_record(
            mocks,
            plan_id,
            {
                "plan_id": plan_id,
                "checkpoint_no": "CP-3",
                "recovery_mode": "override",
                "corrected": False,
                "correction": {},
                "affected_checkpoints": ["CP-5"],
                "pending_sync_checkpoints": ["CP-5"],
                "invalidated_checkpoints": [],
                "confirmed_by": "高管",
                "recovered_at": "2026-11-05T00:00:00+00:00",
                "execution_ms": 1.0,
                "created_via": "use_case",
            },
        )

        summaries = await service.list_checkpoints(plan_id=plan_id)
        by_no = {s.checkpoint_no: s.sync_status for s in summaries}

        assert by_no == {"CP-1": "in_sync", "CP-3": "in_sync", "CP-5": "pending_sync"}, (
            "恢复起点恒 in_sync（新基线）+前序不受影响+后续 pending_sync"
        )

    async def test_list_sync_status_replay_invalidated(self) -> None:
        """sync 三态推导矩阵——Replay 恢复记录（后续 invalidated 全标）。"""
        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        for checkpoint_no in ("CP-1", "CP-3", "CP-5"):
            self._seed(service, mocks, plan_id, checkpoint_no)
        self._seed_recovery_record(
            mocks,
            plan_id,
            {
                "plan_id": plan_id,
                "checkpoint_no": "CP-1",
                "recovery_mode": "replay",
                "corrected": False,
                "correction": {},
                "affected_checkpoints": ["CP-3", "CP-5"],
                "pending_sync_checkpoints": [],
                "invalidated_checkpoints": ["CP-3", "CP-5"],
                "confirmed_by": "高管",
                "recovered_at": "2026-11-05T00:00:00+00:00",
                "execution_ms": 1.0,
                "created_via": "use_case",
            },
        )

        summaries = await service.list_checkpoints(plan_id=plan_id)
        by_no = {s.checkpoint_no: s.sync_status for s in summaries}

        assert by_no == {"CP-1": "in_sync", "CP-3": "invalidated", "CP-5": "invalidated"}

    async def test_list_empty_plan_returns_empty_list(self) -> None:
        """空族返回空清单（枚举面非单点面——不抛 480，AC-1 语义分立）。"""
        from src.domain.exceptions import PlanningNotFoundError

        service, mocks = self._make_service_with_store()

        summaries = await service.list_checkpoints(plan_id=str(uuid.uuid4()))

        assert summaries == []
        # 零抛出显式断言（480 语义分立的运行面证据）
        try:
            await service.list_checkpoints(plan_id=str(uuid.uuid4()))
        except PlanningNotFoundError:
            pytest.fail("list_checkpoints 不得抛 480（清单是枚举面非单点面）")

    async def test_list_probe_calls_covers_full_domain(self) -> None:
        """probe 覆盖全值域 CP-1..CP-8（从 CP-1 起的全量扩展——R8-F1 现状仅探 n+1 起）。"""
        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        load_calls: list[str] = []

        def _record_load(session_id: str) -> None:
            load_calls.append(session_id)

        mocks["snapshot_repository"].load = AsyncMock(side_effect=_record_load)

        await service.list_checkpoints(plan_id=plan_id)

        probed = [call.split(":")[-1] for call in load_calls if "blm-checkpoint-recovery-" not in call]
        assert probed == [f"CP-{number}" for number in range(1, 9)], (
            f"probe 实测={probed} 期望 CP-1..CP-8 全量（含恢复记录键共 9 次 load）"
        )


class TestExecuteRecovery:
    """恢复执行引擎（Story 6-6 AC-3——五步编排/模式裁定 487/双模式分支/12 键/事件）。"""

    def _make_service_with_store(self) -> tuple[Any, dict[str, Any]]:
        """带内存存储+事件捕获的服务工厂（store 承载快照与恢复记录）。"""
        service, mocks = _make_service()
        store: dict[str, Any] = {}
        mocks["snapshot_repository"].load = AsyncMock(side_effect=lambda session_id: store.get(session_id))

        async def _save(snapshot: Any) -> None:
            store[snapshot.session_id] = snapshot

        mocks["snapshot_repository"].save = AsyncMock(side_effect=_save)
        mocks["store"] = store
        published: list[Any] = []
        mocks["published"] = published

        async def _capture_publish(event: Any) -> Any:
            from src.domain.events.publish_result import ChannelResult, PublishResult

            published.append(event)
            mocks["call_order"].append("publish")
            return PublishResult(event_id=str(uuid.uuid4()), results=(ChannelResult("reliable", True),))

        mocks["publisher"].publish = AsyncMock(side_effect=_capture_publish)
        return service, mocks

    def _seed(self, service: Any, mocks: dict[str, Any], plan_id: str, checkpoint_no: str) -> Any:
        """种入指定编号快照（build_snapshot+v0）。"""
        snapshot = service.build_snapshot(
            plan_id=plan_id,
            checkpoint_no=checkpoint_no,
            stage_id="performance_gap",
            compressed=_make_compressed_context(),
            summary=f"{checkpoint_no} 摘要",
            completed=True,
        )
        mocks["store"][snapshot.session_id] = snapshot
        return snapshot

    def _seed_three(self, service: Any, mocks: dict[str, Any], plan_id: str) -> None:
        """三 Checkpoint 前置（CP-1/CP-3/CP-5——Replay 场景≥2 后续）。"""
        for checkpoint_no in ("CP-1", "CP-3", "CP-5"):
            self._seed(service, mocks, plan_id, checkpoint_no)

    async def test_override_execution_record_and_event(self) -> None:
        """Override 执行：恢复记录 12 键+pending_sync 一点+事件 Override/medium。"""
        from src.domain.events.enums import RecoveryMode as EventRecoveryMode

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        self._seed_three(service, mocks, plan_id)

        outcome = await service.execute_recovery(
            plan_id=plan_id,
            checkpoint_no="CP-3",
            confirmed_by="高管-审批人",
        )

        # Outcome 10 键断言
        assert outcome.checkpoint_no == "CP-3"
        assert outcome.recovery_mode == "override"
        assert outcome.corrected is False
        assert outcome.new_state_version == 0
        assert outcome.affected_checkpoints == ["CP-5"]
        assert outcome.marked_checkpoints == ["CP-5"]
        assert outcome.execution_ms > 0.0
        assert outcome.recovery_record_session_id == f"blm-checkpoint-recovery-{plan_id}"
        assert outcome.recovered_snapshot_id  # 非空（②视图 snapshot_id）

        # 恢复记录 12 键 exact set + Override 分支字段
        record = mocks["store"].get(f"blm-checkpoint-recovery-{plan_id}")
        assert record is not None, "恢复记录未落库（第三键族）"
        assert set(record.state_data.keys()) == {
            "plan_id",
            "checkpoint_no",
            "recovery_mode",
            "corrected",
            "correction",
            "affected_checkpoints",
            "pending_sync_checkpoints",
            "invalidated_checkpoints",
            "confirmed_by",
            "recovered_at",
            "execution_ms",
            "created_via",
        }
        state = record.state_data
        assert state["checkpoint_no"] == "CP-3"
        assert state["recovery_mode"] == "override"
        assert state["corrected"] is False
        assert state["correction"] == {}
        assert state["pending_sync_checkpoints"] == ["CP-5"]
        assert state["invalidated_checkpoints"] == []
        assert state["confirmed_by"] == "高管-审批人"  # 审批留痕值级断言
        assert state["created_via"] == "use_case"
        assert state["execution_ms"] > 0.0
        assert record.ttl_seconds == 2_592_000  # 30 天对齐 checkpoint 合规窗
        assert record.checkpoint_no == ""  # 非完整形态（不触发构造守卫）

        # 事件构造字段值级
        assert len(mocks["published"]) == 1
        event = mocks["published"][0]
        assert event.event_type == "CheckpointRecovered"
        assert event.recovery_mode is EventRecoveryMode.OVERRIDE  # events 枚举大写形态
        assert event.recovery_mode.value == "Override"
        assert event.consistency_risk_level == "medium"  # Override+1 后续（同源计算唯一可判别腿）
        assert event.affected_checkpoints == ["CP-5"]
        assert event.modification_content == {}
        assert event.execution_delay_ms > 0.0
        assert event.cost == 0.0
        assert event.metadata["plan_id"] == plan_id  # R3-3 双关联键
        assert event.metadata["checkpoint_no"] == "CP-3"

    async def test_replay_execution_invalidated_and_hint(self) -> None:
        """Replay 执行：invalidated 全标+事件 Replay/low+重跑指引非空。"""
        from src.domain.events.enums import RecoveryMode as EventRecoveryMode

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        self._seed_three(service, mocks, plan_id)

        outcome = await service.execute_recovery(
            plan_id=plan_id,
            checkpoint_no="CP-1",
            confirmed_by="高管-审批人",
        )

        assert outcome.recovery_mode == "replay"
        assert outcome.affected_checkpoints == ["CP-3", "CP-5"]
        assert outcome.marked_checkpoints == ["CP-3", "CP-5"]
        record = mocks["store"][f"blm-checkpoint-recovery-{plan_id}"]
        assert record.state_data["invalidated_checkpoints"] == ["CP-3", "CP-5"]
        assert record.state_data["pending_sync_checkpoints"] == []
        assert outcome.next_action_hint, "重跑指引非空（Replay 分支——建议新 plan_id 经 blm-plan 重跑）"
        assert "blm-plan" in outcome.next_action_hint

        event = mocks["published"][0]
        assert event.recovery_mode is EventRecoveryMode.REPLAY
        assert event.recovery_mode.value == "Replay"
        assert event.consistency_risk_level == "low"  # 恒显式传函数输出（同源）

    async def test_tail_cp8_no_subsequent_low_risk(self) -> None:
        """CP-8 尾点边界：affected 空清单+low 风险+事件正常发布。"""
        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        self._seed(service, mocks, plan_id, "CP-8")

        outcome = await service.execute_recovery(
            plan_id=plan_id,
            checkpoint_no="CP-8",
            confirmed_by="高管",
        )

        assert outcome.recovery_mode == "override"
        assert outcome.affected_checkpoints == []
        event = mocks["published"][0]
        assert event.consistency_risk_level == "low"  # Override 无后续

    async def test_mode_conflict_487_zero_side_effect(self) -> None:
        """模式强制执法：≥2 后续+显式 OVERRIDE → 487 零副作用（save/publish 零调用）。"""
        from src.domain.entities.checkpoint import RecoveryMode
        from src.domain.exceptions import RecoveryModeConflictError

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        self._seed_three(service, mocks, plan_id)
        # 恢复执行前记录 save/publish 基线计数
        save_calls_before = mocks["snapshot_repository"].save.call_count

        with pytest.raises(RecoveryModeConflictError) as exc_info:
            await service.execute_recovery(
                plan_id=plan_id,
                checkpoint_no="CP-1",
                mode=RecoveryMode.OVERRIDE,
                confirmed_by="高管",
            )

        assert exc_info.value.code == "EXCEPTION_487"
        assert "Replay" in exc_info.value.message and "Override" in exc_info.value.message
        # 零副作用断言：恢复记录键不存在+事件零发布+state_version 不变
        assert f"blm-checkpoint-recovery-{plan_id}" not in mocks["store"]
        assert mocks["published"] == []
        assert mocks["snapshot_repository"].save.call_count == save_calls_before

    async def test_mode_conflict_with_correction_apply_zero_call(self) -> None:
        """correction+冲突组合：apply_correction 零调用（裁定②.5 前置的实现漂移哨兵）。"""
        from src.domain.entities.checkpoint import CorrectionRecord, RecoveryMode
        from src.domain.exceptions import RecoveryModeConflictError

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        self._seed_three(service, mocks, plan_id)
        apply_calls: list[dict[str, Any]] = []

        async def _apply(**kwargs: Any) -> Any:
            apply_calls.append(kwargs)
            return self._seed(service, mocks, plan_id, "CP-1")  # 形态无关（不应触达）

        service.apply_correction = AsyncMock(side_effect=_apply)

        with pytest.raises(RecoveryModeConflictError):
            await service.execute_recovery(
                plan_id=plan_id,
                checkpoint_no="CP-1",
                mode=RecoveryMode.OVERRIDE,
                correction=CorrectionRecord(correction_type="L2", previous_value="a", new_value="b", applied_by="u"),
                confirmed_by="高管",
            )

        assert apply_calls == [], "487 须前置于③修正应用（correction+冲突组合零应用）"

    async def test_stronger_mode_allowed(self) -> None:
        """弱替强允：建议 OVERRIDE（1 后续）而显式请求 REPLAY → 允许执行。"""
        from src.domain.entities.checkpoint import RecoveryMode

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        self._seed(service, mocks, plan_id, "CP-1")
        self._seed(service, mocks, plan_id, "CP-3")

        outcome = await service.execute_recovery(
            plan_id=plan_id,
            checkpoint_no="CP-1",
            mode=RecoveryMode.REPLAY,
            confirmed_by="高管",
        )

        assert outcome.recovery_mode == "replay"  # 显式更强模式被采纳
        assert outcome.affected_checkpoints == ["CP-3"]

    async def test_correction_integrated_recovery(self) -> None:
        """修正+恢复一体：③④⑤链式成功+checkpoint_id=③步 sealed.snapshot_id。"""
        from src.domain.entities.checkpoint import CorrectionRecord

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        seeded = self._seed(service, mocks, plan_id, "CP-3")
        self._seed(service, mocks, plan_id, "CP-5")

        outcome = await service.execute_recovery(
            plan_id=plan_id,
            checkpoint_no="CP-3",
            correction=CorrectionRecord(
                correction_type="L2",
                previous_value="旧战略参数",
                new_value="新战略参数",
                applied_by="高管-修正人",
            ),
            confirmed_by="高管-确认人",
        )

        assert outcome.corrected is True
        assert outcome.new_state_version == 1
        assert outcome.recovered_snapshot_id != str(seeded.snapshot_id), (
            "修正一体须取③步 sealed.snapshot_id（with_updated_state 轮换后的新值——②视图值已失效）"
        )
        event = mocks["published"][0]
        assert str(event.checkpoint_id) == outcome.recovered_snapshot_id, (
            "⑤步 checkpoint_id 显式传值断言（修正一体=③步 sealed.snapshot_id）"
        )
        assert set(event.modification_content.keys()) == {
            "correction_type",
            "previous_value",
            "new_value",
            "applied_by",
            "applied_at",
        }
        assert event.modification_content["new_value"] == "新战略参数"
        record = mocks["store"][f"blm-checkpoint-recovery-{plan_id}"]
        assert record.state_data["corrected"] is True
        assert record.state_data["correction"]["correction_type"] == "L2"
        assert record.state_data["correction"]["applied_by"] == "高管-修正人"
        assert record.state_data["confirmed_by"] == "高管-确认人"  # 与 applied_by 双写

    async def test_486_on_correction_save_failure(self) -> None:
        """486 fail-loud：③步 apply_correction save 失败（修正一体场景）→ 486 且事件零发布。"""
        from src.domain.entities.checkpoint import CorrectionRecord
        from src.domain.exceptions import CheckpointRecoveryError, StorageError

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        self._seed(service, mocks, plan_id, "CP-3")
        self._seed(service, mocks, plan_id, "CP-5")

        async def _failing_save(snapshot: Any) -> None:
            raise StorageError("Failed to save snapshot: redis down")

        mocks["snapshot_repository"].save = AsyncMock(side_effect=_failing_save)

        with pytest.raises(CheckpointRecoveryError) as exc_info:
            await service.execute_recovery(
                plan_id=plan_id,
                checkpoint_no="CP-3",
                correction=CorrectionRecord(correction_type="L2", previous_value="a", new_value="b", applied_by="u"),
                confirmed_by="高管",
            )

        assert exc_info.value.code == "EXCEPTION_486"
        assert "redis down" in exc_info.value.message  # reason 组合（根因可见）
        assert mocks["published"] == [], "486 触发时事件零发布"

    async def test_486_on_recovery_record_save_failure(self) -> None:
        """486 fail-loud：④步恢复记录 save 失败（纯恢复场景）→ 486 且事件零发布。"""
        from src.domain.exceptions import CheckpointRecoveryError, StorageError

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        self._seed_three(service, mocks, plan_id)
        save_target = f"blm-checkpoint-recovery-{plan_id}"
        store = mocks["store"]

        async def _failing_save_only_record(snapshot: Any) -> None:
            if snapshot.session_id == save_target:
                raise StorageError("Failed to save snapshot: recovery record write fail")
            store[snapshot.session_id] = snapshot

        mocks["snapshot_repository"].save = AsyncMock(side_effect=_failing_save_only_record)

        with pytest.raises(CheckpointRecoveryError) as exc_info:
            await service.execute_recovery(
                plan_id=plan_id,
                checkpoint_no="CP-3",
                confirmed_by="高管",
            )

        assert exc_info.value.code == "EXCEPTION_486"
        assert mocks["published"] == []

    async def test_publish_failure_degrades_without_rollback(self, caplog: pytest.LogCaptureFixture) -> None:
        """发布降级：⑤步 publish 失败→Outcome 正常返回+恢复记录在+warning 日志（不回滚）。"""
        import logging as std_logging

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        self._seed_three(service, mocks, plan_id)

        async def _failing_publish(event: Any) -> Any:
            raise RuntimeError("rabbitmq unavailable")

        mocks["publisher"].publish = AsyncMock(side_effect=_failing_publish)

        with caplog.at_level(std_logging.WARNING, logger="src.application.services.checkpoint_service"):
            outcome = await service.execute_recovery(
                plan_id=plan_id,
                checkpoint_no="CP-3",
                confirmed_by="高管",
            )

        assert outcome.checkpoint_no == "CP-3"  # Outcome 正常返回
        assert f"blm-checkpoint-recovery-{plan_id}" in mocks["store"], "恢复记录仍落库（审计真相源不回滚）"
        assert "发布降级" in caplog.text, "降级 warning 日志须落（R1-F12 观测锚）"

    async def test_publish_result_failure_degrades_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """发布返回 PublishResult(False) 形态降级（生产真实形态——代码审查 R1-F1）。

        生产 reliable 总线（RabbitMQEventBus）吞一切异常返 PublishResult(False)
        不 raise——except 面对其不可达，发布失败观测经 is_success 返回值检查承载
        （本用例是该检查的红锚：删除 is_success 分支则 warning 断言红）。
        """
        import logging as std_logging

        from src.domain.events.publish_result import ChannelResult, PublishResult

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())
        self._seed_three(service, mocks, plan_id)

        async def _false_result_publish(event: Any) -> PublishResult:
            return PublishResult(
                event_id=str(uuid.uuid4()),
                results=(ChannelResult("reliable", False, "outbox save failed"),),
            )

        mocks["publisher"].publish = AsyncMock(side_effect=_false_result_publish)

        with caplog.at_level(std_logging.WARNING, logger="src.application.services.checkpoint_service"):
            outcome = await service.execute_recovery(
                plan_id=plan_id,
                checkpoint_no="CP-3",
                confirmed_by="高管",
            )

        assert outcome.checkpoint_no == "CP-3"  # Outcome 正常返回（降级不阻断）
        assert f"blm-checkpoint-recovery-{plan_id}" in mocks["store"], "恢复记录仍落库（审计真相源不回滚）"
        assert "发布降级" in caplog.text and "部分通道失败" in caplog.text, (
            "is_success=False 须打 warning（生产观测面——R1-F1 修复锚）"
        )

    async def test_guards_before_engine(self) -> None:
        """入口守卫复用：畸形 checkpoint_no → 242 且 load 零调用（6-3 R1-F2 形态继承）。"""
        from src.domain.exceptions import EntityValidationError

        service, mocks = self._make_service_with_store()
        load_calls: list[str] = []

        def _record_load(session_id: str) -> None:
            load_calls.append(session_id)

        mocks["snapshot_repository"].load = AsyncMock(side_effect=_record_load)

        with pytest.raises(EntityValidationError):
            await service.execute_recovery(plan_id=str(uuid.uuid4()), checkpoint_no="cp3", confirmed_by="x")

        assert load_calls == []

    async def test_execute_recovery_rejects_raw_str_mode(self) -> None:
        """mode 裸 str 防御守卫（代码审查 R1-F8/G1）：非枚举形态 242 且 load 零调用。

        str-Enum 身份比较陷阱：裸 str（含同值 "override"）经②.5 的 is 比较
        恒 False 会绕过 487 执法、④步 .value 抛裸 AttributeError 逃逸异常
        体系——入口守卫 fail-fast（编程面/未来 REST 入口的防御纵深）。
        """
        from src.domain.exceptions import EntityValidationError

        service, mocks = self._make_service_with_store()
        load_calls: list[str] = []

        def _record_load(session_id: str) -> None:
            load_calls.append(session_id)

        mocks["snapshot_repository"].load = AsyncMock(side_effect=_record_load)

        raw_mode: Any = "override"  # 故意裸 str（Any 注解承载非枚举形态——不触 mypy 参数类型红）
        with pytest.raises(EntityValidationError) as exc_info:
            await service.execute_recovery(
                plan_id=str(uuid.uuid4()),
                checkpoint_no="CP-1",
                mode=raw_mode,
                confirmed_by="高管",
            )

        assert exc_info.value.code == "EXCEPTION_242"
        assert load_calls == [], "mode 类型守卫须 fail-fast 先于 load（零 IO）"

    async def test_transparent_errors_not_wrapped(self) -> None:
        """既有触发点透传：480（不存在键）/484（checksum 损坏）不并入 486。"""
        from src.domain.exceptions import PlanningNotFoundError

        service, mocks = self._make_service_with_store()
        plan_id = str(uuid.uuid4())

        with pytest.raises(PlanningNotFoundError):
            await service.execute_recovery(plan_id=plan_id, checkpoint_no="CP-1", confirmed_by="x")
