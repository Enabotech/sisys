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
