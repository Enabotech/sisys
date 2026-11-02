"""Story 6-3 — Checkpoint 快照创建集成测试（真实链五场景）。

模式：6-1/6-2 集成同款——真实 Redis（快照+L1 缓存）/真实 PG（archive L2+
outbox）/真实 Qdrant（L3 向量）/真实 MinIO（L4 对象）+ Fake LLM/Fake
Embedding 双豁免（外部 SaaS——压缩摘要 generate 消费点与 embedding 向量，
R2-F2 钦定）；entity_extractor 用真实规则基 RuleBasedExtractor（纯规则）；
strategic_archive_service 手工构造注入 Fake Embedding（组合根 lambda 强制
依赖外部 SaaS embedding——测试面豁免注入，L2/L4 存储保持真实）。

五场景（Task 5 钦定）：
①创建全链（五步真实跑通+四层断言）②事件落行（真实 publisher+outbox 恰
一行+6-2 零发布互证——创建侧 CP-1 值域，R6-6）③公理二负向（242 透传/484
守卫——归档 L4 失败注入按 Task 0.8⑧ 钦定归单测层）④恢复+篡改+修正链
（三点创建/recover/484/482 构造）⑤性能采样（预热+20 轮 build_snapshot→
save 窗口 P95<100ms，OD-6 口径差声明）。

隔离（自创建自清理，禁手动 delete/truncate 共享表）：PG archive 行按
archive_id 精确 DELETE + outbox 按 plan_id 双通道 DELETE；Qdrant 点按
embedding_ref 精确 DELETE（探测面确保 strategic_archive collection 在位）；
MinIO 对象按 blob_ref 批量精确删除（object-lock bucket 上 GOVERNANCE
retention 生效——经 remove_objects(bypass_governance_mode=True) 管理员
凭证删除）；Redis 三键族逐键删除（禁 flush）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_checkpoint.py -v
"""

from __future__ import annotations

import asyncio
import math
import time
import uuid
from typing import TYPE_CHECKING, Any

import pytest
import sqlalchemy as sa

from src.domain.services.persistent_note_taker import PersistentNoteTaker
from tests.environments import get_test_env

if TYPE_CHECKING:
    from src.domain.ports.l3_vector import SearchResult
    from src.domain.services.persistent_note_taker import PersistentNote

pytestmark = [
    pytest.mark.integration,
    pytest.mark.redis,
    pytest.mark.database,
    pytest.mark.qdrant,
    pytest.mark.minio,
    pytest.mark.xdist_group("blm-planning-perf"),
]

#: 完整形态快照 TTL（30 天——R6-20 ttl() 秒口径）
SNAPSHOT_TTL_SECONDS = 2_592_000

#: state_data 13 键（Task 0.2 冻结——期望独立构造）
EXPECTED_STATE_DATA_KEYS = {
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

_CORPUS_TEXTS = [
    "新能源汽车行业战略分析：市场增速放缓但渗透率持续提升，固态电池技术路线演进加速，"
    "头部厂商价格战与渠道下沉竞争加剧，海外新兴市场成为第二增长曲线，研发投入占比与"
    "组织能力短板是内部能力评估的核心约束，政策补贴退坡与准入收紧构成宏观压力。",
    "财务业绩差距分析：营收目标达成率 87% 低于预期，毛利率下滑 2.3 个百分点根因在于"
    "原材料成本上升与产品结构下移，运营差距体现在交付周期拉长与库存周转下降，组合健康度"
    "评估显示现金流承压但资产负债结构稳健，需在下一规划周期修正关键财务参数。",
    "机会差距量化报告：海外新兴市场渗透率仅 12% 对标标杆 35% 存在 23 个百分点差距，"
    "能力-机会匹配矩阵显示渠道能力与本地化合规是两大短板，差距弥合策略分三阶段推进——"
    "先试点再复制后规模化，机会优先级排序前三位为东南亚、中东、拉美市场。",
]

#: Fake LLM 达标压缩产物（压缩比 ≥0.70 且质量分达标——真实质量评估器实测口径）
_FAKE_COMPRESSED_TEXT = (
    "战略语境压缩摘要：市场渗透率提升与技术演进加速并存；财务达成率 87% 与毛利率下滑"
    "需修正；海外市场渗透差距 23 点，三阶段弥合策略以东南亚/中东/拉美为先。"
)


def _make_fake_llm(*, responses: list[str] | None = None) -> Any:
    """Fake LLM（AsyncMock(spec=LLMClientPort)——外部 SaaS 豁免面）。

    Args:
        responses: generate 轮次响应列表（None 恒返回达标产物；低压缩形态注入
            用于终态门禁场景——首轮冗长次轮达标形态 R6-23）。
    """
    from unittest.mock import AsyncMock

    from src.domain.ports.llm_client import LLMClientPort, LLMResponse

    def _response(text: str) -> LLMResponse:
        return LLMResponse(content=text, finish_reason="stop", usage={}, model="fake-llm")

    fake = AsyncMock(spec=LLMClientPort)
    if responses is not None:
        fake.generate = AsyncMock(side_effect=[_response(text) for text in responses])
    else:
        fake.generate = AsyncMock(return_value=_response(_FAKE_COMPRESSED_TEXT))
    fake.close = AsyncMock()
    return fake


def _make_fake_embedding() -> Any:
    """Fake Embedding（AsyncMock(spec=EmbeddingServicePort)——外部 SaaS 豁免，R2-F2）。"""
    from unittest.mock import AsyncMock

    from src.domain.ports.embedding_service import EmbeddingServicePort

    fake = AsyncMock(spec=EmbeddingServicePort)
    fake.embed_query = AsyncMock(return_value=[0.1] * 1024)
    fake.embed_documents = AsyncMock(return_value=[[0.1] * 1024])
    fake.close = AsyncMock()
    return fake


def _make_search_results() -> "list[SearchResult]":
    """构造检索证据族（Task 0 钦定 {"id":…, "payload": {"content": …}} 形态）。"""
    return [
        {"id": f"chk-corpuse-{index}", "score": 0.9, "payload": {"content": text}} for index, text in enumerate(_CORPUS_TEXTS)
    ]


class _KeyRecordingNoteTaker(PersistentNoteTaker):
    """take_notes 记录壳（R1 审查 FR-1——缓存键清理全覆盖形态）。

    每次 take_notes 返回后把 note:{note_id}/compressed:{note_id} 两键登记进
    清理面：note_id 是 PersistentNote 内部 uuid4，门禁/公理二探针等失败路径
    无法从返回值外取——记录壳是覆盖全部调用路径（含失败路径）的唯一形态。
    compressed:{note_id} 由 ContextCompressor 以同 note_id 写入，一并预登记
    （teardown delete 不存在键 no-op，无代价）。
    """

    def __init__(self, *, redis_keys: list[str], **kwargs: Any) -> None:
        """初始化记录壳。

        Args:
            redis_keys: 清理面键列表（_CheckpointChain.redis_keys 引用共享）。
            **kwargs: 透传 PersistentNoteTaker 构造参数。
        """
        super().__init__(**kwargs)
        self._recorded_redis_keys = redis_keys

    async def take_notes(
        self,
        query: str,
        retrieved_docs: list[SearchResult],
        user_id: str,
        session_id: str,
    ) -> PersistentNote:
        """执行持久化笔记并登记缓存键（真实链零拦截——仅追加登记）。"""
        note = await super().take_notes(
            query=query,
            retrieved_docs=retrieved_docs,
            user_id=user_id,
            session_id=session_id,
        )
        self._recorded_redis_keys.append(f"note:{note.note_id}")
        self._recorded_redis_keys.append(f"compressed:{note.note_id}")
        return note


class _CheckpointChain:
    """Checkpoint 创建链装配（四真实服务 + Fake 双豁免 + 清理收集面）。

    Attributes:
        service: CheckpointService（被测编排服务）。
        snapshot_repository: 真实 Redis 快照仓储。
        redis_client: 测试自有 Redis 客户端（键清理）。
        archive_repo: 真实 PG 档案仓储。
        object_storage: 真实 L4 对象存储端口（blob 断言+清理）。
        qdrant_client: 真实 Qdrant 客户端（点断言+清理）。
        pg_manager: PG 管理器（outbox/archive 行清理）。
        blob_refs / archive_ids / redis_keys: 清理收集面。
    """

    def __init__(self, *, llm_responses: list[str] | None = None) -> None:
        """装配全链（redis/PG 探测失败由调用方 pytest.skip 门控）。"""
        import redis.asyncio as aioredis

        from src.application.services.checkpoint_service import CheckpointService
        from src.application.services.strategic_archive_service import StrategicArchiveService
        from src.domain.ports.resolver import resolve
        from src.domain.services.compression_quality_evaluator import CompressionQualityEvaluator
        from src.domain.services.context_compressor import ContextCompressor
        from src.infrastructure.config.postgresql import PostgreSQLConfig
        from src.infrastructure.external_services.entity_extraction.rule_extractor import RuleBasedExtractor
        from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
        from src.infrastructure.storage.redis.redis_adapter import RedisAdapter

        env = get_test_env()
        self.env = env
        self.plan_ids: list[str] = []
        self.blob_refs: list[str] = []
        self.archive_ids: list[str] = []
        self.redis_keys: list[str] = []
        self.session_ids: list[str] = []

        # 真实 Redis（快照 + L1 缓存双职责）
        self.redis_client = aioredis.Redis(
            host=env.redis.host,
            port=env.redis.port,
            password=env.redis.password or None,
            decode_responses=True,
        )
        redis_adapter = RedisAdapter(redis_client=self.redis_client)
        from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore

        self.snapshot_repository = RedisSnapshotStore(adapter=redis_adapter)

        # 领域服务链（真实规则基抽取 + Fake LLM + 真实 L1；note_taker 套记录壳——
        # note:/compressed: 缓存键随 take_notes 全路径登记进清理面，R1 审查 FR-1）
        note_taker = _KeyRecordingNoteTaker(
            redis_keys=self.redis_keys,
            entity_extractor=RuleBasedExtractor(),
            audit_service=None,
            l1_cache=redis_adapter,
        )
        compressor = ContextCompressor(
            llm_client=_make_fake_llm(responses=llm_responses),
            note_taker=note_taker,
            quality_evaluator=CompressionQualityEvaluator(),
            l1_cache=redis_adapter,
        )

        # 归档服务：真实 PG L2 + 真实 Qdrant L3 + 真实 MinIO L4 + Fake Embedding 豁免
        self.pg_manager = PostgreSQLManager(
            PostgreSQLConfig(
                host=env.postgres.host,
                port=env.postgres.port,
                database=env.postgres.database,
                username=env.postgres.username,
                password=env.postgres.password,
            )
        )
        self.archive_repo = resolve("archive_repository")
        self.object_storage = resolve("l4_object")
        self.qdrant_client = resolve("qdrant_client")
        self.archive_service = StrategicArchiveService(
            archive_repo=self.archive_repo,
            embedding_service=_make_fake_embedding(),  # 外部 SaaS 豁免（R2-F2）
            vector_storage=resolve("l3_vector"),
            object_storage=self.object_storage,
            graph_storage=None,  # L5 可选降级（Neo4j 非本 Story 断言面）
            event_publisher=None,  # 集成默认无发布（场景②注入真实 publisher 重建）
            staleness_service=None,
        )

        self.service = CheckpointService(
            note_taker=note_taker,
            compressor=compressor,
            archive_service=self.archive_service,
            snapshot_repository=self.snapshot_repository,
            event_publisher=_NoopPublisher(),
        )
        self._session: Any = None
        self._session_token: Any = None

    async def __aenter__(self) -> "_CheckpointChain":
        """进入链上下文：激活 PG AsyncSession（SessionContext——归档 L2 必需）。"""
        from sqlalchemy.ext.asyncio import AsyncSession

        from src.infrastructure.storage.postgresql.session_context import set_session

        self._session = AsyncSession(self.pg_manager.get_async_engine())
        await self._session.begin()
        self._session_token = set_session(self._session)
        return self

    async def commit(self) -> None:
        """提交当前事务（行断言前置——独立连接可见；session 自动开启新事务）。"""
        if self._session is not None:
            await self._session.commit()

    async def __aexit__(self, *exc_info: Any) -> None:
        """退出链上下文：commit 真实落库 → 还原会话 → 全链清理。"""
        from src.infrastructure.storage.postgresql.session_context import reset_session

        if self._session is not None:
            try:
                await self._session.commit()  # 真实落库（行存在断言+teardown 精确删除语义）
            except Exception:
                await self._session.rollback()
            if self._session_token is not None:
                reset_session(self._session_token)
            await self._session.close()
        await self.cleanup()

    def register_plan(self, plan_id: str, *, session_ids: list[str] | None = None) -> None:
        """登记清理面（plan_id → outbox 行；session_ids → Redis 快照键）。"""
        self.plan_ids.append(plan_id)
        for session_id in session_ids or []:
            self.session_ids.append(session_id)
            self.redis_keys.append(f"sisys:snapshot:{session_id}")

    async def create(self, *, plan_id: str, checkpoint_no: str, stage_id: str = "performance_gap") -> Any:
        """便捷创建（快照键调用前预登记 + note/compressed 键经记录壳登记）。

        预登记时点 = 调用服务**之前**（R1 审查 FR-1：覆盖「save 成功后事件/
        断言失败」中间态——delete 不存在键 no-op，失败路径零代价）。
        """
        from src.application.ports.checkpoint import CHECKPOINT_SESSION_PREFIX

        self.redis_keys.append(f"sisys:snapshot:{CHECKPOINT_SESSION_PREFIX}{plan_id}:{checkpoint_no}")
        self.register_plan(plan_id)
        return await self.service.create_checkpoint(
            plan_id=plan_id,
            checkpoint_no=checkpoint_no,
            stage_id=stage_id,
            query="五年战略规划（集成测试）",
            retrieved_docs=_make_search_results(),
            user_id="integration-executor",
            summary=f"{checkpoint_no} 阶段摘要（集成直供）",
        )

    async def collect_archive_residues(self) -> None:
        """按 plan_id 收集归档残留面（PG 行 + blob_ref + Qdrant 点 ID）。"""
        engine = self.pg_manager.get_async_engine()
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        sa.text("SELECT archive_id, blob_ref, embedding_ref FROM strategic_archives WHERE plan_id = ANY(:ids)"),
                        {"ids": self.plan_ids},
                    )
                ).fetchall()
        finally:
            await engine.dispose()
        for row in rows:
            self.archive_ids.append(str(row[0]))
            if row[1]:
                self.blob_refs.append(row[1])

    async def cleanup(self) -> None:
        """teardown 全链清理（自创建自清理——各步独立 best-effort）。"""
        try:
            await self.collect_archive_residues()
        except Exception:
            pass
        # PG：archive 行按 archive_id + outbox 行按 plan_id 双通道
        try:
            engine = self.pg_manager.get_async_engine()
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
        # MinIO 对象按 blob_ref 删除（GOVERNANCE retention 生效——经 bypass 批量删除；
        # minio-py remove_objects(bypass_governance_mode=True) 管理员凭证可删）
        if self.blob_refs:
            try:
                from minio import Minio
                from minio.deleteobjects import DeleteObject

                env = self.env
                minio_client = Minio(
                    endpoint=env.minio.endpoint,
                    access_key=env.minio.access_key,
                    secret_key=env.minio.secret_key,
                    secure=env.minio.secure,
                )
                bucket_name = self.object_storage._repository._resolve_bucket_name("archive-evidence")
                _ = list(
                    minio_client.remove_objects(
                        bucket_name,
                        [DeleteObject(blob_ref) for blob_ref in self.blob_refs],
                        bypass_governance_mode=True,
                    )
                )
            except Exception:
                pass
        # Qdrant 点按 payload.archive_id 精确删除（filter selector——点 ID 为 MD5 哈希 int）
        if self.archive_ids:
            try:
                from qdrant_client import models

                await self.qdrant_client.delete(
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
        # Redis 三键族逐键删除（快照键 + note/compressed 缓存键经 TTL 自清吸收——快照键显式删）
        for key in self.redis_keys:
            try:
                await self.redis_client.delete(key)
            except Exception:
                pass
        try:
            await self.redis_client.close()
        except Exception:
            pass

    async def query_outbox(self, plan_id: str, *, event_type: str, channel: str = "metadata") -> list[Any]:
        """查询 outbox 行（CheckpointReached 走 metadata 顶层通道——OD-9）。"""
        engine = self.pg_manager.get_async_engine()
        channel_expr = "payload->'metadata'->>'plan_id'" if channel == "metadata" else "payload->'payload'->>'plan_id'"
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        sa.text(
                            f"SELECT event_id, event_type, payload->'payload'->>'phase_identifier' AS phase, "
                            f"payload->'payload'->>'user_feedback_request' AS feedback, "
                            f"payload->'metadata'->>'plan_id' AS meta_plan "
                            f"FROM event_outbox WHERE event_type = :etype AND {channel_expr} = :plan_id "
                            f"AND created_at >= NOW() - INTERVAL '5 minutes'"
                        ),
                        {"etype": event_type, "plan_id": plan_id},
                    )
                ).fetchall()
        finally:
            await engine.dispose()
        return list(rows)

    async def count_recent_events(self, event_type: str) -> int:
        """全通道 5 分钟窗事件计数（event_type 过滤——残局防线查询）。

        R1 审查 FR-5：替代「按刚生成 UUID 过滤」的恒真断言——全通道窗计数
        对 teardown 残留/跨场景污染有真实判别力（6-2 负向查询同构形态）。
        event_type 过滤必留（防本 Story 自身的 ArchiveCreated 行误计入）。
        """
        engine = self.pg_manager.get_async_engine()
        try:
            async with engine.connect() as conn:
                count = (
                    await conn.execute(
                        sa.text(
                            "SELECT COUNT(*) FROM event_outbox "
                            "WHERE event_type = :etype AND created_at >= NOW() - INTERVAL '5 minutes'"
                        ),
                        {"etype": event_type},
                    )
                ).scalar()
        finally:
            await engine.dispose()
        return int(count or 0)


class _NoopPublisher:
    """无发布替身（场景①③④⑤默认——真实发布归场景②专用装配）。

    实现 EventPublisher 协议面（publish 返回成功结果）——集成层禁止 mock
    真实服务，本类是进程内空实现（非 AsyncMock——发布行为在场景②经真实
    publisher 验证）。
    """

    async def publish(self, event: Any) -> Any:
        """发布空实现（返回成功结果面）。"""
        from src.domain.events.publish_result import ChannelResult, PublishResult

        return PublishResult(event_id=str(uuid.uuid4()), results=(ChannelResult("inmemory", True),))


async def _probe_services() -> None:
    """四真实服务双探测（不可达环境 pytest.skip 动态跳过）。"""
    import redis.asyncio as aioredis

    env = get_test_env()
    client = aioredis.Redis(
        host=env.redis.host, port=env.redis.port, password=env.redis.password or None, decode_responses=True
    )
    try:
        await client.ping()
    except Exception as exc:
        pytest.skip(f"Redis 不可用: {exc}")
    finally:
        await client.close()

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
    try:
        engine = manager.get_async_engine()
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT event_id FROM event_outbox LIMIT 1"))
            await conn.execute(sa.text("SELECT archive_id FROM strategic_archives LIMIT 1"))
        await engine.dispose()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 不可达或表未初始化: {exc}")

    try:
        from src.domain.ports.resolver import resolve

        qdrant = resolve("qdrant_client")
        await qdrant.get_collections()
        # strategic_archive collection 确保（L3 upsert 前提——向量维度对齐 Fake Embedding 1024）
        from qdrant_client import models

        existing = {collection.name for collection in (await qdrant.get_collections()).collections}
        if "strategic_archive" not in existing:
            await qdrant.create_collection(
                collection_name="strategic_archive",
                vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
            )

        l4 = resolve("l4_object")
        bucket_name = l4._repository._resolve_bucket_name("archive-evidence")  # 集成面内部锚（bucket 存在性探测）
        from minio import Minio
        from minio.deleteobjects import DeleteObject

        minio_client = Minio(
            endpoint=env.minio.endpoint,
            access_key=env.minio.access_key,
            secret_key=env.minio.secret_key,
            secure=env.minio.secure,
        )
        # object-lock bucket（L4 WORM GOVERNANCE retention 前提——无 object-lock
        # 配置的 bucket 上 set_object_retention 使 archive 阻断）；历史无锁形态
        # best-effort 自愈（竞态失败接受现状——bucket 在位即可）
        if not minio_client.bucket_exists(bucket_name):
            try:
                minio_client.make_bucket(bucket_name, object_lock=True)
            except Exception:
                if not minio_client.bucket_exists(bucket_name):
                    raise
        else:
            try:
                minio_client.get_object_lock_config(bucket_name)
            except Exception:
                try:
                    versions = [
                        DeleteObject(obj.object_name, version_id=obj.version_id)
                        for obj in minio_client.list_objects(bucket_name, recursive=True, include_version=True)
                    ]
                    _ = list(minio_client.remove_objects(bucket_name, versions, bypass_governance_mode=True))
                    minio_client.remove_bucket(bucket_name)
                    minio_client.make_bucket(bucket_name, object_lock=True)
                except Exception:
                    pass
    except Exception as exc:
        pytest.skip(f"Qdrant/MinIO 不可用: {exc}")


async def test_scenario1_full_chain_creation() -> None:
    """场景①：五步全链真实跑通——快照 13 键+TTL+checksum+四层归档+L1 笔记。"""
    await _probe_services()
    async with _CheckpointChain() as chain:
        plan_id = str(uuid.uuid4())
        snapshot = await chain.create(plan_id=plan_id, checkpoint_no="CP-1")

        # 快照读回（Redis 真实键）
        loaded = await chain.snapshot_repository.load(snapshot.session_id)
        assert loaded is not None, "完整形态快照读回为 None"
        assert set(loaded.state_data.keys()) == EXPECTED_STATE_DATA_KEYS
        assert loaded.ttl_seconds == SNAPSHOT_TTL_SECONDS
        ttl = await chain.redis_client.ttl(f"sisys:snapshot:{snapshot.session_id}")
        assert ttl == SNAPSHOT_TTL_SECONDS, f"redis ttl() 实测={ttl}"
        assert loaded.verify_integrity() is True, "round-trip checksum verify 红"
        assert loaded.state_data["created_via"] == "use_case"

        # L1 笔记缓存读回（note:{note_id}——缓存键已经记录壳登记进清理面）
        note_ref = loaded.state_data["persistent_note_ref"]
        raw = await chain.redis_client.get(f"note:{note_ref}")
        assert raw is not None, "L1 笔记缓存键读回为 None（笔记未真实持久化）"

        # PG 归档行（plan_type=SP + checkpoint_no 语境锚）——commit 后独立连接可见
        await chain.commit()
        engine = chain.pg_manager.get_async_engine()
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        sa.text("SELECT plan_type, decision_basis FROM strategic_archives WHERE plan_id = :plan_id"),
                        {"plan_id": plan_id},
                    )
                ).fetchall()
        finally:
            await engine.dispose()
        assert rows, "strategic_archives 归档行缺失"
        assert rows[0][0] == "SP"
        assert rows[0][1].get("checkpoint_no") == "CP-1"  # R8-F3 语境锚

        # Qdrant 点读回（strategic_archive collection——scroll 按 payload.archive_id 匹配；
        # 点 ID 经 MD5 确定性哈希转 int——vector_storage._normalize_point_id 形态）
        await chain.collect_archive_residues()
        assert chain.archive_ids, "归档行缺失（archive_id 收集面空）"
        points, _next = await chain.qdrant_client.scroll(collection_name="strategic_archive", limit=50, with_payload=True)
        point_archives = {str(point.payload.get("archive_id")) for point in points}
        missing = set(chain.archive_ids) - point_archives
        assert not missing, f"Qdrant 点未读回（payload.archive_id 实测={point_archives} 缺 {missing}）"

        # MinIO 对象（blob_ref 解引用含压缩上下文——经 L4 端口）
        assert chain.blob_refs, "L4 blob_ref 缺失（evidence_blob 未入档）"
        blob_bytes = b""
        async for chunk in chain.object_storage.retrieve(bucket_type="archive-evidence", object_key=chain.blob_refs[0]):
            blob_bytes += chunk
        assert loaded.state_data["compressed_context"][:16] in blob_bytes.decode("utf-8")


async def test_scenario2_outbox_checkpoint_reached_row() -> None:
    """场景②：真实 publisher + outbox 落行恰一行 + 6-2 零发布互证（CP-1 值域）。"""
    await _probe_services()
    from src.application.services.checkpoint_service import CheckpointService
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.domain.ports.resolver import get_resolver, resolve

    get_resolver().clear_singleton()  # SINGLETON 跨 loop 防线（6-1 场景③先例）
    real_publisher = resolve("event_publisher")
    async with _CheckpointChain() as chain:
        # 重建服务注入真实 publisher（归档事件与 CheckpointReached 双落行）
        chain.service = CheckpointService(
            note_taker=chain.service._note_taker,
            compressor=chain.service._compressor,
            archive_service=StrategicArchiveService(
                archive_repo=chain.archive_repo,
                embedding_service=_make_fake_embedding(),
                vector_storage=resolve("l3_vector"),
                object_storage=chain.object_storage,
                graph_storage=None,
                event_publisher=real_publisher,
                staleness_service=None,
            ),
            snapshot_repository=chain.snapshot_repository,
            event_publisher=real_publisher,
        )
        plan_id = str(uuid.uuid4())

        # 创建前全通道零行（R1 审查 FR-5：原「按刚生成 UUID 过滤」恒真——改全通道
        # 5 分钟窗计数，对 teardown 残留/跨场景污染有真实判别力；BLM run 正交性
        # 证据由 6-2 既有验收/集成资产承载——OD-13 勘误注记）
        pre_count = await chain.count_recent_events("CheckpointReached")
        assert pre_count == 0, f"创建前 CheckpointReached 全通道计数实测={pre_count} 期望=0（teardown 残局防线）"

        await chain.create(plan_id=plan_id, checkpoint_no="CP-1")
        await chain.commit()  # 归档行 + outbox 行（同事务）提交——独立连接可见
        await asyncio.sleep(0.2)  # outbox 异步落行窗口

        rows = await chain.query_outbox(plan_id, event_type="CheckpointReached")
        assert len(rows) == 1, f"CheckpointReached 落行实测={len(rows)} 期望=1（恰一行）"
        row = rows[0]
        assert row[2] == "performance_gap", f"phase_identifier 实测={row[2]}"
        assert row[3] in (True, "true"), f"user_feedback_request 实测={row[3]}"
        assert row[4] == plan_id, f"metadata.plan_id 实测={row[4]}（顶层通道——OD-9）"

        # ArchiveCreated 事件行（③归档内发布——R2A-8 收集面）
        archive_rows = await chain.query_outbox(plan_id, event_type="ArchiveCreated", channel="payload")
        assert len(archive_rows) >= 1, "ArchiveCreated 事件行缺失（归档发布链）"
    get_resolver().clear_singleton()


async def test_scenario3_axiom_two_and_guards() -> None:
    """场景③：公理二负向——242 透传 + 484 空引用守卫 + 终态门禁 483。

    归档 L4 失败注入归单测层承载（Task 0.8⑧——no-mock 红线互斥裁定，
    6-2 R3-4 同款）；本场景聚焦真实链可构造的负向面。
    """
    from dataclasses import replace as dc_replace

    from src.domain.exceptions import CheckpointCreationError, CheckpointIntegrityError, EntityValidationError

    await _probe_services()
    async with _CheckpointChain() as chain:
        # ① 未持久化笔记压缩 → 既有 EntityValidationError(242) 零回归
        from src.domain.services.persistent_note_taker import PersistentNoteTaker

        note = await chain.service._note_taker.take_notes(
            query="公理二负向",
            retrieved_docs=_make_search_results(),
            user_id="integration-executor",
            session_id="blm-checkpoint-axiom-two-probe",
        )
        unpersisted = dc_replace(note, persisted=False, persisted_at=None) if hasattr(note, "persisted") else note
        with pytest.raises(EntityValidationError):
            await chain.service._compressor.compress(
                retrieved_docs=_make_search_results(), query="q", persistent_note=unpersisted
            )
        assert PersistentNoteTaker.verify_persisted(note) is True

        # ② 空引用构造完整形态快照 → 484（实体守卫）
        from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

        with pytest.raises(CheckpointIntegrityError):
            CheckpointSnapshot(
                session_id="blm-checkpoint-x:CP-1",
                stage_id="performance_gap",
                checkpoint_no="CP-1",
                persistent_note_ref="",
            )

        # ③ 终态门禁：Fake 双响应注入（首轮冗长 ratio<0.70 触发二次、次轮仍冗长——
        #    双指标不足固定形态）→ 483 且零落库
        async with _CheckpointChain(llm_responses=["".join(_CORPUS_TEXTS), "".join(_CORPUS_TEXTS)]) as gate_chain:
            plan_id = str(uuid.uuid4())
            gate_chain.register_plan(plan_id)
            with pytest.raises(CheckpointCreationError) as exc_info:
                await gate_chain.service.create_checkpoint(
                    plan_id=plan_id,
                    checkpoint_no="CP-1",
                    stage_id="performance_gap",
                    query="终态门禁",
                    retrieved_docs=_make_search_results(),
                    user_id="integration-executor",
                    summary="门禁场景",
                )
            assert exc_info.value.code == "EXCEPTION_483"
            loaded = await gate_chain.snapshot_repository.load(f"blm-checkpoint-{plan_id}:CP-1")
            assert loaded is None, "门禁失败仍产出快照（半成品违规）"


async def test_scenario4_recovery_and_tamper() -> None:
    """场景④：三点创建 → recover 视图/篡改 484/修正链 round-trip+版本递增。"""
    from dataclasses import replace as dc_replace

    from src.domain.entities.checkpoint import CorrectionRecord
    from src.domain.exceptions import CheckpointIntegrityError

    await _probe_services()
    async with _CheckpointChain() as chain:
        plan_id = str(uuid.uuid4())
        for checkpoint_no in ("CP-1", "CP-3", "CP-5"):
            await chain.create(plan_id=plan_id, checkpoint_no=checkpoint_no)

        # recover CP-3：后续 [CP-5]、override（1<2）
        view_cp3 = await chain.service.recover_checkpoint(plan_id=plan_id, checkpoint_no="CP-3")
        assert view_cp3.subsequent_checkpoints == ["CP-5"]
        assert view_cp3.recommended_mode == "override"
        # recover CP-1：后续 [CP-3, CP-5]、replay（恰 2 强制）
        view_cp1 = await chain.service.recover_checkpoint(plan_id=plan_id, checkpoint_no="CP-1")
        assert view_cp1.subsequent_checkpoints == ["CP-3", "CP-5"]
        assert view_cp1.recommended_mode == "replay"

        # 篡改快照（读回后篡改 state_data 再存）→ recover 484
        session_id = f"blm-checkpoint-{plan_id}:CP-1"
        loaded = await chain.snapshot_repository.load(session_id)
        assert loaded is not None, f"篡改前置快照读回为 None: {session_id}"
        tampered_state = dict(loaded.state_data)
        tampered_state["summary"] = "被篡改的摘要（场景④注入）"
        await chain.snapshot_repository.save(dc_replace(loaded, state_data=tampered_state))
        with pytest.raises(CheckpointIntegrityError):
            await chain.service.recover_checkpoint(plan_id=plan_id, checkpoint_no="CP-1")

        # 修正链 round-trip（新 plan 隔离——篡改键已污染）
        plan2 = str(uuid.uuid4())
        seeded = await chain.create(plan_id=plan2, checkpoint_no="CP-1")
        corrected = await chain.service.apply_correction(
            session_id=seeded.session_id,
            correction=CorrectionRecord(
                correction_type="key_param", previous_value="87%", new_value="90%", applied_by="integration-executor"
            ),
            expected_state_version=0,
        )
        assert corrected.state_version == 1
        assert len(corrected.state_data["correction_history"]) == 1
        assert corrected.verify_integrity() is True, "修正后 checksum 重算 round-trip 绿"


async def test_scenario5_creation_window_p95() -> None:
    """场景⑤：创建提交窗口 P95<100ms（20 轮独立 plan_id——OD-6 口径）。

    口径差声明：窗口 = build_snapshot 构造起点（含 checksum——R6-5）→
    Redis save 返回；持久化笔记实体抽取与 LLM 压缩延迟显式出栈（Fake LLM
    固定产物，预热轮取得压缩产物——6-1 DC-7/6-2 OD-3 先例）。预热含④步
    save（R8-F5——Redis 连接池已建立，防首轮建连开销抬 P95）。20 轮复用
    预热轮压缩产物（R6-11 血缘豁免——断言面仅验键存在与 TTL）。
    """
    from src.domain.services.context_compressor import CompressedContext

    await _probe_services()
    async with _CheckpointChain() as chain:
        # 预热：单次全链（含④ save——连接池建立）
        warmup = await chain.create(plan_id=str(uuid.uuid4()), checkpoint_no="CP-1")
        state = warmup.state_data
        compressed = CompressedContext(
            context=state["compressed_context"],
            compression_ratio=state["compression_ratio"],
            quality_score=state["quality_score"],
            token_count=state["token_count"],
            persistent_note_ref=state["persistent_note_ref"],
            query="性能采样窗口（固定输入）",
        )

        durations: list[float] = []
        sessions: list[str] = []
        for _round in range(20):
            plan_id = str(uuid.uuid4())  # 20 独立 plan_id（R1-F17——值域 8 上限）
            start = time.monotonic()
            snapshot = chain.service.build_snapshot(
                plan_id=plan_id,
                checkpoint_no="CP-1",
                stage_id="performance_gap",
                compressed=compressed,
                summary="性能采样窗口（固定输入）",
                completed=True,
                created_via="use_case",
            )
            await chain.snapshot_repository.save(snapshot)
            durations.append(time.monotonic() - start)
            sessions.append(snapshot.session_id)
            chain.register_plan(plan_id, session_ids=[snapshot.session_id])  # 采样快照键登记清理面（R1 审查 FR-1）

        # P95 = sorted 升序 [ceil(0.95n)-1]（n=20 取次大值——升序前提显式）
        ordered = sorted(durations)
        p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
        assert p95 < 0.100, f"创建提交窗口 P95 实测={p95 * 1000:.2f}ms ≥ 100ms（OD-6 口径）"

        # 持久化成功率：20/20 可读回 + TTL 断言（R8-F4）
        for session_id in sessions:
            loaded = await chain.snapshot_repository.load(session_id)
            assert loaded is not None, f"采样快照读回为 None: {session_id}"
            ttl = await chain.redis_client.ttl(f"sisys:snapshot:{session_id}")
            assert ttl == SNAPSHOT_TTL_SECONDS
