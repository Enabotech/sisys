"""Story 6-6 — Checkpoint 恢复链集成测试（真实服务四场景）。

装配形态对齐 6-3 集成基座（_CheckpointChain 自包含装配类——四真实服务+
Fake LLM/Fake Embedding 双豁免+预登记+定向 DELETE 清理）；恢复链差异面：
event_publisher 用真实 publisher（resolve("event_publisher")——
CheckpointRecovered outbox 落行是场景①②③断言面）+ 恢复记录第三键族预登记
（blm-checkpoint-recovery-{plan_id}——R1-F1 键清理面纪律）。

四场景（Task 5.2~5.5）：
① 恢复执行全链（3 点创建→CP-3 Override→恢复记录 12 键+TTL 30 天双验+
   pending_sync 一点+CheckpointRecovered outbox 恰一行 checkpoint_id+
   metadata.plan_id 双通道值级——预期值单源 Outcome.recovered_snapshot_id）；
② Replay 分支+修正一体（≥2 后续+correction→invalidated 全标+事件 Replay+
   checkpoint_id=③步 sealed.snapshot_id 断言+correction 投影落
   modification_content+修正链版本递增读回）；
③ 并发 5 路（5 独立 plan gather——创建+恢复均入 gather，每任务自建
   AsyncSession+set_session（PEP 567 task 级 context 拷贝不外泄，深层
   get_session() 调用期解析自动命中本任务会话——共享装配链会话形态下并发写
   必触发 SQLAlchemy 并发会话防呆）；各恢复记录/事件行独立值级断言）；
④ 恢复窗口与成功率（采样矩阵：Override×5 建议模式单点+Replay×5 显式
   --mode replay 单点（OD-6 弱替强允消费面）——逐次窗口 <15s+10 次恢复
   全读回；窗口载体=Outcome.execution_ms）+ 变异验证型×2（期望键族删键/
   event_type 改名——断言判别力实证）。

清理纪律（键计数净增 0）：恢复记录键族预登记（调用前）；outbox 行按
plan_id 双通道定向 DELETE（含创建侧 CheckpointReached+归档侧 ArchiveCreated+
恢复侧 CheckpointRecovered 三类）；Redis 逐键删除；服务不可达 pytest.skip()。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_checkpoint_recovery.py -v
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
import sqlalchemy as sa

from src.domain.ports.l3_vector import SearchResult
from src.infrastructure.storage.redis.key_builder import build_key
from tests.environments import get_test_env

pytestmark = [
    pytest.mark.integration,
    pytest.mark.database,
    pytest.mark.redis,
    pytest.mark.qdrant,
    pytest.mark.minio,
    pytest.mark.xdist_group("blm-planning-perf"),
]

#: 恢复记录 12 键契约（Task 0.1 冻结——期望值独立构造）
EXPECTED_RECOVERY_RECORD_KEYS: frozenset[str] = frozenset(
    {
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
)

#: 恢复记录 TTL（30 天——对齐 checkpoint 键族合规窗）
RECOVERY_RECORD_TTL_SECONDS: int = 2_592_000

#: 恢复执行窗口门禁（秒——逐次断言蕴含 P95 双门禁，OD-8）
RECOVERY_WINDOW_LIMIT_SECONDS: float = 15.0

#: 并发路数（AC-5——5 独立 plan）
CONCURRENT_PLANS: int = 5

_CORPUS_TEXTS: tuple[str, ...] = (
    "新能源汽车行业战略分析：市场增速放缓但渗透率持续提升，固态电池技术路线演进加速，"
    "头部厂商价格战与渠道下沉竞争加剧，海外新兴市场成为第二增长曲线，研发投入占比与"
    "组织能力短板是内部能力评估的核心约束，政策补贴退坡与准入收紧构成宏观压力。",
    "财务业绩差距分析：营收目标达成率 87% 低于预期，毛利率下滑 2.3 个百分点根因在于"
    "原材料成本上升与产品结构下移，运营差距体现在交付周期拉长与库存周转下降，组合健康度"
    "评估显示现金流承压但资产负债结构稳健，需在下一规划周期修正关键财务参数。",
    "机会差距量化报告：海外新兴市场渗透率仅 12% 对标标杆 35% 存在 23 个百分点差距，"
    "能力-机会匹配矩阵显示渠道能力与本地化合规是两大短板，差距弥合策略三阶段推进——"
    "先试点再复制后规模化，机会优先级排序前三位为东南亚、中东、拉美市场。",
)

_FAKE_COMPRESSED_TEXT = (
    "战略语境压缩摘要：市场渗透率提升与技术演进加速并存；财务达成率 87% 与毛利率下滑"
    "需修正；海外市场渗透差距 23 点，三阶段弥合策略以东南亚/中东/拉美为先。"
)


def _make_search_results() -> list[SearchResult]:
    """构造最小检索证据族（payload.content 键——6-3 集成同款）。"""
    return [
        {"id": f"itg-corpuse-{index}", "score": 0.9, "payload": {"content": text}} for index, text in enumerate(_CORPUS_TEXTS)
    ]


def _make_fake_llm() -> Any:
    """Fake LLM 工厂（外部 SaaS 豁免——固定达标压缩产物）。"""
    from unittest.mock import AsyncMock

    from src.domain.ports.llm_client import LLMClientPort, LLMResponse

    fake = AsyncMock(spec=LLMClientPort)
    fake.generate = AsyncMock(
        return_value=LLMResponse(content=_FAKE_COMPRESSED_TEXT, finish_reason="stop", usage={}, model="fake-llm")
    )
    fake.close = AsyncMock()
    return fake


def _make_fake_embedding() -> Any:
    """Fake Embedding 工厂（外部 SaaS 豁免——固定 1024 维向量）。"""
    from unittest.mock import AsyncMock

    from src.domain.ports.embedding_service import EmbeddingServicePort

    fake = AsyncMock(spec=EmbeddingServicePort)
    fake.embed_query = AsyncMock(return_value=[0.1] * 1024)
    fake.embed_documents = AsyncMock(return_value=[[0.1] * 1024])
    fake.close = AsyncMock()
    return fake


async def _probe_services() -> None:
    """四真实服务探测（不可达环境 pytest.skip 动态跳过）。"""
    env = get_test_env()
    try:
        import redis.asyncio as aioredis

        client = aioredis.Redis(
            host=env.redis.host,
            port=env.redis.port,
            password=env.redis.password or None,
            decode_responses=True,
        )
        await client.ping()
        await client.close()
    except Exception as exc:
        pytest.skip(f"Redis 不可用: {exc}")
    try:
        from src.infrastructure.config.postgresql import PostgreSQLConfig
        from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

        manager = PostgreSQLManager(
            PostgreSQLConfig(
                host=env.postgres.host,
                port=env.postgres.port,
                database=env.postgres.database,
                username=env.postgres.username,
                password=env.postgres.password,
            )
        )
        engine = manager.get_async_engine()
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT event_id FROM event_outbox LIMIT 1"))
            await conn.execute(sa.text("SELECT archive_id FROM strategic_archives LIMIT 1"))
        await engine.dispose()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 不可达: {exc}")
    try:
        from qdrant_client import AsyncQdrantClient

        qdrant_client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
        await qdrant_client.get_collections()
        await qdrant_client.close()
    except Exception as exc:
        pytest.skip(f"Qdrant 不可用: {exc}")
    try:
        from minio import Minio

        minio_client = Minio(
            endpoint=env.minio.endpoint,
            access_key=env.minio.access_key,
            secret_key=env.minio.secret_key,
            secure=env.minio.secure,
        )
        if not minio_client.bucket_exists("sisys-test-archive-evidence-mvp-tenant"):
            # bucket 名经组合根锚解析——此处仅健康探测（存在性任一形态即可）
            buckets = {bucket.name for bucket in minio_client.list_buckets()}
            assert buckets, "MinIO 无可访问 bucket"
    except Exception as exc:
        pytest.skip(f"MinIO 不可用: {exc}")


class _RecoveryChain:
    """恢复链装配（6-3 _CheckpointChain 基座扩展——真实 publisher+恢复记录键族预登记）。"""

    def __init__(self) -> None:
        """装配全链（探测失败由 _probe_services 先行 skip 门控）。"""
        import redis.asyncio as aioredis

        from src.application.services.checkpoint_service import CheckpointService
        from src.application.services.strategic_archive_service import StrategicArchiveService
        from src.domain.ports.resolver import get_resolver, resolve
        from src.domain.services.compression_quality_evaluator import CompressionQualityEvaluator
        from src.domain.services.context_compressor import ContextCompressor
        from src.domain.services.persistent_note_taker import PersistentNoteTaker
        from src.infrastructure.config.postgresql import PostgreSQLConfig
        from src.infrastructure.external_services.entity_extraction.rule_extractor import RuleBasedExtractor
        from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
        from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
        from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore

        env = get_test_env()
        self.env = env
        self.plan_ids: list[str] = []
        self.blob_refs: list[str] = []
        self.archive_ids: list[str] = []
        self.redis_keys: list[str] = []

        self.redis_client = aioredis.Redis(
            host=env.redis.host,
            port=env.redis.port,
            password=env.redis.password or None,
            decode_responses=True,
        )
        redis_adapter = RedisAdapter(redis_client=self.redis_client)
        self.snapshot_repository = RedisSnapshotStore(adapter=redis_adapter)

        outer = self

        class _KeyRecordingNoteTaker(PersistentNoteTaker):
            """take_notes 记录壳（note:/compressed: 键全路径登记——6-3 同款）。"""

            async def take_notes(self, query: str, retrieved_docs: list[Any], user_id: str, session_id: str) -> Any:
                note = await super().take_notes(
                    query=query, retrieved_docs=retrieved_docs, user_id=user_id, session_id=session_id
                )
                outer.redis_keys.append(f"note:{note.note_id}")
                outer.redis_keys.append(f"compressed:{note.note_id}")
                return note

        note_taker = _KeyRecordingNoteTaker(
            entity_extractor=RuleBasedExtractor(),
            audit_service=None,
            l1_cache=redis_adapter,
        )
        compressor = ContextCompressor(
            llm_client=_make_fake_llm(),
            note_taker=note_taker,
            quality_evaluator=CompressionQualityEvaluator(),
            l1_cache=redis_adapter,
        )

        self.pg_manager = PostgreSQLManager(
            PostgreSQLConfig(
                host=env.postgres.host,
                port=env.postgres.port,
                database=env.postgres.database,
                username=env.postgres.username,
                password=env.postgres.password,
            )
        )
        archive_service = StrategicArchiveService(
            archive_repo=resolve("archive_repository"),
            embedding_service=_make_fake_embedding(),  # 外部 SaaS 豁免
            vector_storage=resolve("l3_vector"),
            object_storage=resolve("l4_object"),
            graph_storage=None,
            event_publisher=None,
            staleness_service=None,
        )
        # 恢复链差异面：真实 publisher（CheckpointRecovered outbox 落行断言面）——
        # clear 后 resolve 重建绑本链 loop（6-3 集成②先例同款）
        get_resolver().clear_singleton()
        real_publisher = resolve("event_publisher")
        self.service = CheckpointService(
            note_taker=note_taker,
            compressor=compressor,
            archive_service=archive_service,
            snapshot_repository=self.snapshot_repository,
            event_publisher=real_publisher,
        )
        self._session: Any = None
        self._session_token: Any = None

    async def __aenter__(self) -> "_RecoveryChain":
        """进入链上下文：激活 PG AsyncSession（归档 L2+outbox 落行前置）。"""
        from sqlalchemy.ext.asyncio import AsyncSession

        from src.infrastructure.storage.postgresql.session_context import set_session

        self._session = AsyncSession(self.pg_manager.get_async_engine())
        await self._session.begin()
        self._session_token = set_session(self._session)
        return self

    async def commit(self) -> None:
        """提交当前事务（行断言前置——独立连接可见）。"""
        if self._session is not None:
            await self._session.commit()

    async def __aexit__(self, *exc_info: Any) -> None:
        """退出链上下文：commit → 还原会话 → 全链清理（键计数净增 0）。"""
        from src.domain.ports.resolver import get_resolver
        from src.infrastructure.storage.postgresql.session_context import reset_session

        if self._session is not None:
            try:
                await self._session.commit()
            except Exception:
                await self._session.rollback()
            if self._session_token is not None:
                reset_session(self._session_token)
            await self._session.close()
        get_resolver().clear_singleton()
        await self.cleanup()

    def register_plan(self, plan_id: str) -> None:
        """登记 plan 清理面（outbox 行双通道 DELETE 锚）。"""
        if plan_id not in self.plan_ids:
            self.plan_ids.append(plan_id)

    def register_sessions(self, *session_ids: str) -> None:
        """登记 Redis 快照/恢复记录键（预登记——调用服务之前，6-3 R1-F1 纪律）。

        键构造经 build_key 单源（代码审查 R1-F16——此前硬编码 sisys:snapshot:
        前缀与验收侧双源，键构造规则变更时清理面会静默失配）。
        """
        for session_id in session_ids:
            self.redis_keys.append(build_key("snapshot", session_id))

    def snapshot_session(self, plan_id: str, checkpoint_no: str) -> str:
        """快照会话键登记+返回（期望形态独立构造）。"""
        session_id = f"blm-checkpoint-{plan_id}:{checkpoint_no}"
        self.register_sessions(session_id)
        self.register_plan(plan_id)
        return session_id

    def recovery_session(self, plan_id: str) -> str:
        """恢复记录会话键登记+返回（第三键族——调用前预登记）。"""
        session_id = f"blm-checkpoint-recovery-{plan_id}"
        self.register_sessions(session_id)
        self.register_plan(plan_id)
        return session_id

    async def create(self, *, plan_id: str, checkpoint_no: str) -> Any:
        """便捷创建（键预登记——6-3 集成同款）。"""
        self.snapshot_session(plan_id, checkpoint_no)
        return await self.service.create_checkpoint(
            plan_id=plan_id,
            checkpoint_no=checkpoint_no,
            stage_id="performance_gap",
            query="五年战略规划（恢复链集成）",
            retrieved_docs=_make_search_results(),
            user_id="integration-executor",
            summary=f"{checkpoint_no} 阶段摘要（恢复链集成直供）",
        )

    async def execute_recovery(self, **kwargs: Any) -> Any:
        """便捷恢复执行（恢复记录键预登记）。"""
        self.recovery_session(kwargs["plan_id"])
        return await self.service.execute_recovery(**kwargs)

    async def query_outbox_recovered(self, plan_id: str) -> list[dict[str, Any]]:
        """查询 CheckpointRecovered 落行（checkpoint_id 新键路径+metadata 通道）。"""
        engine = self.pg_manager.get_async_engine()
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        sa.text(
                            "SELECT event_id, event_type, "
                            "payload->'payload'->>'checkpoint_id' AS checkpoint_id, "
                            "payload->'payload'->>'recovery_mode' AS recovery_mode, "
                            "payload->'metadata'->>'plan_id' AS meta_plan "
                            "FROM event_outbox "
                            "WHERE event_type = 'CheckpointRecovered' "
                            "AND created_at >= NOW() - INTERVAL '5 minutes' "
                            "AND payload->'metadata'->>'plan_id' = :plan_id"
                        ),
                        {"plan_id": plan_id},
                    )
                ).fetchall()
        finally:
            await engine.dispose()
        return [
            {
                "event_id": str(row[0]),
                "event_type": row[1],
                "checkpoint_id": row[2],
                "recovery_mode": row[3],
                "meta_plan": row[4],
            }
            for row in rows
        ]

    async def load_recovery_record(self, plan_id: str) -> Any:
        """恢复记录读回（第三键族同形态承载——经 snapshot_repository）。"""
        return await self.snapshot_repository.load(f"blm-checkpoint-recovery-{plan_id}")

    async def cleanup(self) -> None:
        """teardown 全链清理（归档行+outbox 行+MinIO+Qdrant+Redis 逐键）。"""
        engine = self.pg_manager.get_async_engine()
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        sa.text("SELECT archive_id, blob_ref FROM strategic_archives WHERE plan_id = ANY(:ids)"),
                        {"ids": self.plan_ids},
                    )
                ).fetchall()
            for row in rows:
                self.archive_ids.append(str(row[0]))
                if row[1]:
                    self.blob_refs.append(row[1])
        except Exception:
            pass
        try:
            async with engine.begin() as conn:
                if self.archive_ids:
                    await conn.execute(
                        sa.text("DELETE FROM strategic_archives WHERE archive_id = ANY(:ids)"),
                        {"ids": self.archive_ids},
                    )
                if self.plan_ids:
                    await conn.execute(
                        sa.text(
                            "DELETE FROM event_outbox WHERE payload->'metadata'->>'plan_id' = ANY(:ids) "
                            "OR payload->'payload'->>'plan_id' = ANY(:ids)"
                        ),
                        {"ids": self.plan_ids},
                    )
            await engine.dispose()
        except Exception:
            pass
        if self.blob_refs:
            try:
                from minio import Minio
                from minio.deleteobjects import DeleteObject

                from src.domain.ports.resolver import get_resolver, resolve

                get_resolver().clear_singleton()
                env = self.env
                minio_client = Minio(
                    endpoint=env.minio.endpoint,
                    access_key=env.minio.access_key,
                    secret_key=env.minio.secret_key,
                    secure=env.minio.secure,
                )
                bucket_name = resolve("l4_object")._repository._resolve_bucket_name("archive-evidence")
                _ = list(
                    minio_client.remove_objects(
                        bucket_name,
                        [DeleteObject(blob_ref) for blob_ref in self.blob_refs],
                        bypass_governance_mode=True,
                    )
                )
            except Exception:
                pass
        if self.archive_ids:
            try:
                from qdrant_client import models

                from src.domain.ports.resolver import get_resolver, resolve

                get_resolver().clear_singleton()
                await resolve("qdrant_client").delete(
                    collection_name="strategic_archive",
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="archive_id",
                                    match=models.MatchAny(any=list(self.archive_ids)),
                                )
                            ]
                        )
                    ),
                )
            except Exception:
                pass
        for key in self.redis_keys:
            try:
                await self.redis_client.delete(key)
            except Exception:
                pass
        try:
            await self.redis_client.close()
        except Exception:
            pass


async def test_scenario1_override_full_chain() -> None:
    """场景①：Override 全链（3 点→CP-3 恢复→12 键+TTL+pending_sync+outbox 双通道值级）。"""
    await _probe_services()
    async with _RecoveryChain() as chain:
        plan_id = str(uuid.uuid4())
        for checkpoint_no in ("CP-1", "CP-3", "CP-5"):
            await chain.create(plan_id=plan_id, checkpoint_no=checkpoint_no)

        outcome = await chain.execute_recovery(
            plan_id=plan_id,
            checkpoint_no="CP-3",
            confirmed_by="集成-审批人",
        )
        await chain.commit()
        await asyncio.sleep(0.2)  # outbox 异步落行窗口

        # Outcome 断言锚
        assert outcome.recovery_mode.value == "override"
        assert outcome.affected_checkpoints == ["CP-5"]
        assert outcome.recovered_snapshot_id, "断言预期值单源非空"

        # 恢复记录 12 键+TTL 双验
        record = await chain.load_recovery_record(plan_id)
        assert record is not None, "恢复记录读回 None"
        assert frozenset(record.state_data.keys()) == EXPECTED_RECOVERY_RECORD_KEYS, (
            f"12 键实测={sorted(record.state_data.keys())}"
        )
        assert record.state_data["pending_sync_checkpoints"] == ["CP-5"]
        assert record.state_data["confirmed_by"] == "集成-审批人"
        assert record.ttl_seconds == RECOVERY_RECORD_TTL_SECONDS
        # Redis 实测 TTL 区间断言（代码审查 R1-F3：精确等值在 save→ttl 间累计
        # 耗时 ≥1s 时返回 2591999 假红——容差下界覆盖 commit+sleep+断言链窗口）
        redis_ttl = await chain.redis_client.ttl(build_key("snapshot", f"blm-checkpoint-recovery-{plan_id}"))
        assert RECOVERY_RECORD_TTL_SECONDS - 5 <= redis_ttl <= RECOVERY_RECORD_TTL_SECONDS, (
            f"redis ttl 实测={redis_ttl} 期望区间 [{RECOVERY_RECORD_TTL_SECONDS - 5}, {RECOVERY_RECORD_TTL_SECONDS}]"
        )

        # outbox 恰一行（checkpoint_id+metadata.plan_id 双通道值级）
        rows = await chain.query_outbox_recovered(plan_id)
        assert len(rows) == 1, f"CheckpointRecovered 落行实测={len(rows)} 期望=1"
        row = rows[0]
        assert row["checkpoint_id"] == outcome.recovered_snapshot_id, (
            f"checkpoint_id 通道实测={row['checkpoint_id']!r} 期望=Outcome.recovered_snapshot_id（单源锚）"
        )
        assert row["meta_plan"] == plan_id
        assert row["recovery_mode"] == "Override"


async def test_scenario2_replay_with_correction() -> None:
    """场景②：Replay+修正一体（invalidated 全标+checkpoint_id=sealed 断言+版本递增）。"""
    from src.domain.entities.checkpoint import CorrectionRecord

    await _probe_services()
    async with _RecoveryChain() as chain:
        plan_id = str(uuid.uuid4())
        for checkpoint_no in ("CP-1", "CP-3", "CP-5"):
            await chain.create(plan_id=plan_id, checkpoint_no=checkpoint_no)

        outcome = await chain.execute_recovery(
            plan_id=plan_id,
            checkpoint_no="CP-1",
            correction=CorrectionRecord(
                correction_type="L2",
                previous_value="旧战略参数",
                new_value="新战略参数",
                applied_by="集成-修正人",
            ),
            confirmed_by="集成-确认人",
        )
        await chain.commit()
        await asyncio.sleep(0.2)

        assert outcome.recovery_mode.value == "replay"
        assert outcome.corrected is True
        assert outcome.new_state_version == 1
        record = await chain.load_recovery_record(plan_id)
        assert record is not None
        assert record.state_data["invalidated_checkpoints"] == ["CP-3", "CP-5"]
        assert record.state_data["correction"]["new_value"] == "新战略参数"

        # 修正链版本递增读回（修正后快照 v1+verify 绿）
        sealed = await chain.snapshot_repository.load(f"blm-checkpoint-{plan_id}:CP-1")
        assert sealed is not None and sealed.state_version == 1
        assert sealed.verify_integrity(), "修正后快照 verify 红（完整性闭环断裂）"

        rows = await chain.query_outbox_recovered(plan_id)
        assert len(rows) == 1
        assert rows[0]["recovery_mode"] == "Replay"
        assert rows[0]["checkpoint_id"] == outcome.recovered_snapshot_id, (
            "checkpoint_id=③步 sealed.snapshot_id（with_updated_state 轮换后新值）"
        )
        assert outcome.recovered_snapshot_id == str(sealed.snapshot_id), "修正一体值源钦定对账"


async def test_scenario3_five_way_concurrent() -> None:
    """场景③：并发 5 路（gather 每任务会话隔离——互不干扰+恢复记录独立值级）。"""
    await _probe_services()
    async with _RecoveryChain() as chain:
        plan_ids = [str(uuid.uuid4()) for _ in range(CONCURRENT_PLANS)]
        for plan_id in plan_ids:
            chain.snapshot_session(plan_id, "CP-1")
            chain.recovery_session(plan_id)

        async def _one_plan(plan_id: str) -> Any:
            from sqlalchemy.ext.asyncio import AsyncSession

            from src.infrastructure.storage.postgresql.session_context import reset_session, set_session

            session = AsyncSession(chain.pg_manager.get_async_engine())
            try:
                await session.begin()
                token = set_session(session)
                try:
                    await chain.service.create_checkpoint(
                        plan_id=plan_id,
                        checkpoint_no="CP-1",
                        stage_id="performance_gap",
                        query="五年战略规划（并发审批）",
                        retrieved_docs=_make_search_results(),
                        user_id="integration-executor",
                        summary="CP-1 阶段摘要（并发集成直供）",
                    )
                    return await chain.service.execute_recovery(
                        plan_id=plan_id,
                        checkpoint_no="CP-1",
                        confirmed_by=f"并发-{plan_id[:8]}",
                    )
                finally:
                    reset_session(token)
            except Exception:
                await session.rollback()
                raise
            finally:
                try:
                    await session.commit()
                except Exception:
                    pass
                await session.close()

        outcomes = await asyncio.gather(*[_one_plan(plan_id) for plan_id in plan_ids])
        await asyncio.sleep(0.2)

        assert len(outcomes) == CONCURRENT_PLANS
        for plan_id, outcome in zip(plan_ids, outcomes, strict=True):
            assert outcome is not None
            record = await chain.load_recovery_record(plan_id)
            assert record is not None, f"plan={plan_id} 恢复记录读回 None"
            assert record.state_data["plan_id"] == plan_id, "并发无交叉污染值级断言"
            assert record.state_data["confirmed_by"] == f"并发-{plan_id[:8]}"

        # outbox 按 plan 分组各恰一行
        engine = chain.pg_manager.get_async_engine()
        try:
            async with engine.connect() as conn:
                grouped = (
                    await conn.execute(
                        sa.text(
                            "SELECT payload->'metadata'->>'plan_id' AS plan_id, COUNT(*) "
                            "FROM event_outbox "
                            "WHERE event_type = 'CheckpointRecovered' "
                            "AND created_at >= NOW() - INTERVAL '5 minutes' "
                            "AND payload->'metadata'->>'plan_id' = ANY(:ids) "
                            "GROUP BY payload->'metadata'->>'plan_id'"
                        ),
                        {"ids": plan_ids},
                    )
                ).fetchall()
        finally:
            await engine.dispose()
        assert dict((str(row[0]), int(row[1])) for row in grouped) == {plan_id: 1 for plan_id in plan_ids}, (
            "outbox 分组各恰一行断言"
        )


async def test_scenario4_window_and_success_rate() -> None:
    """场景④：恢复窗口与成功率（Override×5+Replay×5 逐次窗口+10 次全读回）。"""
    from src.domain.entities.checkpoint import RecoveryMode

    await _probe_services()
    async with _RecoveryChain() as chain:
        sample_plan_ids = [str(uuid.uuid4()) for _ in range(10)]
        for plan_id in sample_plan_ids:
            chain.snapshot_session(plan_id, "CP-1")
            chain.recovery_session(plan_id)
        for plan_id in sample_plan_ids:
            await chain.create(plan_id=plan_id, checkpoint_no="CP-1")
        await chain.commit()

        outcomes = []
        for index, plan_id in enumerate(sample_plan_ids):
            explicit_mode = RecoveryMode.REPLAY if index >= 5 else None
            outcome = await chain.execute_recovery(
                plan_id=plan_id,
                checkpoint_no="CP-1",
                mode=explicit_mode,
                confirmed_by=f"采样-{index}",
            )
            outcomes.append(outcome)
        await chain.commit()

        for plan_id, outcome in zip(sample_plan_ids, outcomes, strict=True):
            assert outcome.execution_ms < RECOVERY_WINDOW_LIMIT_SECONDS * 1000.0, (
                f"plan={plan_id} 窗口实测={outcome.execution_ms}ms（纯数据面毫秒量级——漂移即红）"
            )
            record = await chain.load_recovery_record(plan_id)
            assert record is not None, f"plan={plan_id} 恢复记录读回 None（成功率 100% 口径）"
        modes = [outcome.recovery_mode.value for outcome in outcomes]
        assert modes.count("override") == 5 and modes.count("replay") == 5, f"双模式采样实测={modes}"


async def test_scenario5_recovery_record_corrupted_json_degrades() -> None:
    """场景⑤：恢复记录损坏 JSON 退化语义（代码审查 R1-F4——单测 mock 层不可达的全链实证）。

    RedisSnapshotStore.load 对 latest 字段 JSON 解析异常吞错返 None，list_checkpoints
    join 面退化为全量 in_sync——端口第四级契约退化语义的真实 Redis 全链承载
    （hset 覆写保持 hash 类型，精确命中 json_loads 解析失败分支——S13 篡改手法；
    判别锚 = pending_sync→in_sync 转变：正常态 CP-3 显示 pending_sync，损坏后
    退化 in_sync——「读到了损坏并退化」与「从未有标记」可区分）。
    """
    await _probe_services()
    async with _RecoveryChain() as chain:
        plan_id = str(uuid.uuid4())
        chain.snapshot_session(plan_id, "CP-1")
        chain.snapshot_session(plan_id, "CP-3")
        chain.recovery_session(plan_id)
        await chain.create(plan_id=plan_id, checkpoint_no="CP-1")
        await chain.create(plan_id=plan_id, checkpoint_no="CP-3")
        await chain.execute_recovery(plan_id=plan_id, checkpoint_no="CP-1", confirmed_by="集成-损坏验证")
        await chain.commit()

        # 正常路径对照锚：Override 后续 CP-3 一点 pending_sync + 起点 in_sync
        summaries = await chain.service.list_checkpoints(plan_id=plan_id)
        assert [s.checkpoint_no for s in summaries] == ["CP-1", "CP-3"]
        assert [s.sync_status for s in summaries] == ["in_sync", "pending_sync"], (
            f"正常态 sync 实测={[s.sync_status for s in summaries]}（判别前提）"
        )

        # 覆写恢复记录 latest 字段为损坏 JSON → load 吞错返 None → 全量 in_sync 退化
        await chain.redis_client.hset(build_key("snapshot", f"blm-checkpoint-recovery-{plan_id}"), "latest", "损坏非JSON{")
        summaries_degraded = await chain.service.list_checkpoints(plan_id=plan_id)
        assert [s.checkpoint_no for s in summaries_degraded] == ["CP-1", "CP-3"], "快照键未损坏——条目仍在"
        assert [s.sync_status for s in summaries_degraded] == ["in_sync", "in_sync"], (
            "恢复记录损坏 JSON → 退化全量 in_sync（不抛异常——第四级契约退化语义全链实证）"
        )


async def test_mutation_verification_key_contract() -> None:
    """变异验证型①：期望键族删键 → 断言红实证（6-3 Task 5 验证型变异先例）。"""
    await _probe_services()
    async with _RecoveryChain() as chain:
        plan_id = str(uuid.uuid4())
        await chain.create(plan_id=plan_id, checkpoint_no="CP-1")
        await chain.execute_recovery(plan_id=plan_id, checkpoint_no="CP-1", confirmed_by="变异验证")
        await chain.commit()

        record = await chain.load_recovery_record(plan_id)
        assert record is not None
        mutated_keys = EXPECTED_RECOVERY_RECORD_KEYS - {"invalidated_checkpoints"}  # 删期望键
        assert not frozenset(record.state_data.keys()) == mutated_keys, (
            "验证型变异失效：删键后的期望集仍与实测相等（断言无判别力）"
        )
        # 还原语义：完整期望集恰相等（对照锚）
        assert frozenset(record.state_data.keys()) == EXPECTED_RECOVERY_RECORD_KEYS


async def test_mutation_verification_event_type() -> None:
    """变异验证型②：event_type 改名查询 → 零行实证（查询通道判别力）。"""
    await _probe_services()
    async with _RecoveryChain() as chain:
        plan_id = str(uuid.uuid4())
        await chain.create(plan_id=plan_id, checkpoint_no="CP-1")
        await chain.execute_recovery(plan_id=plan_id, checkpoint_no="CP-1", confirmed_by="变异验证")
        await chain.commit()
        await asyncio.sleep(0.2)

        rows = await chain.query_outbox_recovered(plan_id)
        assert len(rows) == 1, "正确通道恰一行（前提锚）"

        engine = chain.pg_manager.get_async_engine()
        try:
            async with engine.connect() as conn:
                wrong = (
                    await conn.execute(
                        sa.text(
                            "SELECT COUNT(*) FROM event_outbox "
                            "WHERE event_type = 'CheckpointRecoveredTypo' "
                            "AND payload->'metadata'->>'plan_id' = :plan_id "
                            "AND created_at >= NOW() - INTERVAL '5 minutes'"
                        ),
                        {"plan_id": plan_id},
                    )
                ).scalar()
        finally:
            await engine.dispose()
        assert int(wrong or 0) == 0, "改名 event_type 查询须零行（通道判别力实证）"
