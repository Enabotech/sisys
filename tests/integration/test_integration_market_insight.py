"""Story 6-2 — 市场洞察六子步骤类型化输出集成测试（真实链四场景）。

模式对齐 6-1 test_integration_blm_planning.py（Task 5 验证型豁免声明：本
文件创建时服务已实现——TDD 红绿由 5.5 验证型变异实证替代）：真实 Redis/
真实守卫链/真实 CEO 实例化/真实档案加载/真实工具链/真实检索（门控
_ensure_retrieval 双探测 skip）/真实图引擎 + Fake LLM 唯一豁免（八键族
分派 + fail_schemas schema 身份注入扩展——AC-4 R1 钦定注入键）。

四场景（Subtask 5.1/5.2/5.3/5.4a/5.4b）：
- 场景① 类型化全链：六步 structured_output 领域要素键族逐步断言（期望键族
  独立构造）+ 图身份锚
- 场景② per-step 快照读回 + outbox 负向：真实发布装配（非空锚 ≥9 行前置
  ——R3-3 防空真）→ 6 per-step + latest 逐键 load() 读回、七键契约、
  plan_id 归属锚、版本写读一致（state_version 恒 0——R2 措辞）、零
  CheckpointReached（两级 JSONB 路径 payload->'payload'->>'plan_id'）
- 场景③ 双杀注入采样：相邻两步 Schema 恒败（fail_schemas——schema 身份
  与轮次无关）→ 恰两步降级互不传染、信封完整、per-step 快照含降级标记、
  20 轮采样成功率 100%（信封完整口径）；recorder 总线 + 每轮新铸 plan_id
  （R2 三边界钦定：采样轮快照键 TTL 吸收不逐删）
- 场景④-A 并发正确性：5 不同 plan_id asyncio.gather + 真实 publisher +
  PG outbox per-plan 9 行计数（PlanningStarted×1+BlmStageCompleted×8；
  AgentDecided 无 plan_id 子键天然排除）+ per-step 快照归属锚逐 plan 断言
  ——不断言 P95（并发争用延迟与 AC-5 串行口径不同质——R1-7）
- 场景④-B 性能采样：市场洞察段 P95<25s 独立串行 ≥20 轮（OD-3 Fake LLM
  管线开销口径——真实 LLM 延迟显式出栈归 6.1-DF1；观测点 = timeline 两端
  trend.started_at → synthesis.completed_at；task 文本固定是模块级 embedding
  缓存命中前提——R3 补）

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/integration/test_integration_market_insight.py -v

测试隔离:
    - try/finally 自包含：outbox 按 event_id 精确 DELETE + _dispose_retrieval
    - Agent 状态键 agent/isolation 双 namespace 逐键删除（禁 flush）
    - 断言场景（②④-A）per-step/latest 快照键逐键精确删除；采样轮（③④-B）
      快照键沿 6-1 先例 TTL 86400 吸收（20 轮 × 7 键不逐删——R2 钦定）
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest

from src.infrastructure.storage.redis.key_builder import build_key

# 文件名不含服务关键词，integration conftest 不会自动添加 marker——显式声明；
# xdist_group 复用 6-1 组名 blm-planning-perf（跨 Story 采样场景同 worker 串行）
pytestmark = [
    pytest.mark.integration,
    pytest.mark.redis,
    pytest.mark.xdist_group("blm-planning-perf"),
]

#: 六子步骤执行序期望（独立构造自 or.md——禁经被测服务生成）
EXPECTED_ORDER: tuple[str, ...] = (
    "trend",
    "market_customer",
    "competition",
    "self",
    "opportunity",
    "opportunity_gap",
)

#: 各步 structured_output 期望键族（独立构造自 Task 0.1 冻结表——字面量）
EXPECTED_STRUCTURED_KEYS: dict[str, frozenset[str]] = {
    "trend": frozenset(
        {
            "summary",
            "findings",
            "pestel_political",
            "pestel_economic",
            "pestel_social",
            "pestel_technological",
            "pestel_environmental",
            "pestel_legal",
            "technology_roadmap",
            "scenario_plans",
        }
    ),
    "market_customer": frozenset(
        {"summary", "findings", "customer_segments", "demand_priority_matrix", "value_proposition_map"}
    ),
    "competition": frozenset(
        {
            "summary",
            "findings",
            "five_forces_supplier_power",
            "five_forces_buyer_power",
            "five_forces_new_entrants",
            "five_forces_substitutes",
            "five_forces_rivalry",
            "competitor_radar",
            "strategy_recommendations",
        }
    ),
    "self": frozenset({"summary", "findings", "internal_capabilities", "vrio_assessment", "resource_constraints"}),
    "opportunity": frozenset({"summary", "findings", "opportunity_list", "priority_ranking", "growth_path"}),
    "opportunity_gap": frozenset(
        {"summary", "findings", "gap_quantification", "capability_match_matrix", "closure_strategies"}
    ),
}

#: per-step state_data 七键期望（独立构造——端口文件第三级契约镜像）
EXPECTED_STEP_SNAPSHOT_KEYS: frozenset[str] = frozenset(
    {"step", "plan_id", "summary", "structured_output", "degraded", "degrade_reason", "completed_steps"}
)

#: PESTEL 六维度字段族（场景① 领域要素断言锚——OD-8 工具产物化）
_PESTEL_KEYS: tuple[str, ...] = (
    "pestel_political",
    "pestel_economic",
    "pestel_social",
    "pestel_technological",
    "pestel_environmental",
    "pestel_legal",
)

#: 波特五力五维字段族（场景① 领域要素断言锚——OD-8 工具产物化）
_FIVE_FORCES_KEYS: tuple[str, ...] = (
    "five_forces_supplier_power",
    "five_forces_buyer_power",
    "five_forces_new_entrants",
    "five_forces_substitutes",
    "five_forces_rivalry",
)

# 真实检索语料（背景建制——与任务主题相关，保证 dense 命中；沿 6-1 语料）
_CORPUS_TEXTS: tuple[str, ...] = (
    "新能源汽车行业进入战略分析报告：市场增速放缓但渗透率持续提升",
    "财务业绩差距分析：营收目标达成率与毛利率下滑根因",
    "竞争对手动态：头部厂商价格战与渠道下沉策略",
    "宏观趋势：政策补贴退坡与技术路线演进（固态电池）",
    "内部能力评估：研发投入占比与组织能力短板",
    "市场机会：海外新兴市场增长路径与机会差距量化",
)


class _CachedEmbedding:
    """embedding 查询/文档向量缓存代理（测试面性能优化——非被测对象）。

    探针实证（6-1）：embedding API 往返占采样场景成本 >95%——同文本向量
    经 bge-m3 确定性推理恒同，缓存命中与真实调用等价。模块级缓存跨场景
    复用（进程内有效；跨文件不共享——共享面是外部 embedding 服务）。
    """

    _query_cache: dict[str, Any] = {}
    _documents_cache: dict[tuple[str, ...], Any] = {}

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    async def embed_query(self, text: str) -> Any:
        if text not in self._query_cache:
            self._query_cache[text] = await self._inner.embed_query(text)
        return self._query_cache[text]

    async def embed_documents(self, texts: list[str]) -> Any:
        key = tuple(texts)
        if key not in self._documents_cache:
            self._documents_cache[key] = await self._inner.embed_documents(texts)
        return self._documents_cache[key]

    async def close(self) -> None:
        await self._inner.close()


async def _ensure_retrieval(env: Any) -> dict[str, Any] | None:
    """探测并建制检索语料（不可达返回 None——调用方 skip）。"""
    from qdrant_client import AsyncQdrantClient, models

    from src.infrastructure.config.embedding import EmbeddingConfig
    from src.infrastructure.external_services.embedding.embedding_api_client import EmbeddingAPIClient

    embedding = _CachedEmbedding(EmbeddingAPIClient(EmbeddingConfig.from_env()))
    client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=30)
    try:
        await embedding.embed_query("连通性探测")
        await client.get_collections()
        collection = f"test_market_int_{uuid.uuid4().hex[:8]}"
        await client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
        )
        vectors = await embedding.embed_documents(list(_CORPUS_TEXTS))
        await client.upsert(
            collection_name=collection,
            points=[
                models.PointStruct(id=str(uuid.uuid4()), vector=vec, payload={"text": text})
                for vec, text in zip(vectors, _CORPUS_TEXTS)
            ],
        )
        return {"collection": collection, "embedding": embedding, "client": client}
    except Exception:
        await embedding.close()
        return None


async def _dispose_retrieval(retrieval: dict[str, Any]) -> None:
    """清理检索语料 collection。"""
    try:
        await retrieval["client"].delete_collection(retrieval["collection"])
        await retrieval["client"].close()
    except Exception:
        pass
    try:
        await retrieval["embedding"].close()
    except Exception:
        pass


class _StubIsolationSwitchLogRepository:
    """零 IO 日志仓储替身（5-3 验收同款——真实链归 5-6）。"""

    def __init__(self) -> None:
        self.saved_logs: list[Any] = []

    async def save(self, log: Any) -> None:
        self.saved_logs.append(log)

    async def search(self, query: Any) -> Any:
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogSearchResult

        return IsolationSwitchLogSearchResult(items=(), total=0, offset=query.offset, limit=query.limit)


def _make_fake_llm(
    *,
    fail_call_indices: frozenset[int] = frozenset(),
    fail_schemas: frozenset[type] = frozenset(),
    hold_at_call: int | None = None,
    delay_sec: float = 0.0,
) -> Any:
    """BLM 面 Fake LLM 端口替身（外部 SaaS 豁免面——分派键 = response_schema 身份）。

    分派键 = GapAnalysisSchema / 六类型化 Schema / InsightSynthesisSchema 八者
    身份互斥。注入控制：fail_call_indices（调用序）/ fail_schemas（schema 身份
    恒败——6-2 AC-4 R1 钦定主注入键，首调与重试皆败、与轮次无关）/
    hold_at_call / delay_sec。
    """
    from unittest.mock import AsyncMock

    from src.domain.ports.llm_client import LLMClientPort, LLMResponse

    state: dict[str, Any] = {"count": 0, "calls": [], "hold_event": asyncio.Event()}

    async def _structured_generate(
        prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
    ) -> Any:
        call_index = state["count"]
        state["count"] += 1
        state["calls"].append(
            {
                "prompt": prompt,
                "schema": response_schema,
                "temperature": getattr(config, "temperature", None),
                "timeout": getattr(config, "timeout", None),
                "call_index": call_index,
            }
        )
        if delay_sec:
            await asyncio.sleep(delay_sec)
        if hold_at_call is not None and call_index == hold_at_call:
            await state["hold_event"].wait()
        if response_schema in fail_schemas:
            from src.domain.exceptions.llm_exceptions import LLMAPIError

            raise LLMAPIError(f"Fake schema 身份注入失败（{response_schema.__name__} 恒败）")
        if call_index in fail_call_indices:
            from src.domain.exceptions.llm_exceptions import LLMAPIError

            raise LLMAPIError(f"Fake 注入失败（调用序 {call_index}）")

        from src.application.services.blm_planning_prompts import (
            CompetitionInsightSchema,
            GapAnalysisSchema,
            InsightSynthesisSchema,
            MarketCustomerInsightSchema,
            OpportunityGapInsightSchema,
            OpportunityInsightSchema,
            SelfInsightSchema,
            TrendInsightSchema,
        )

        if response_schema is GapAnalysisSchema:
            return GapAnalysisSchema(
                financial_gap="财务差距量化（集成）",
                operational_gap="运营差距分析（集成）",
                root_causes=["根因一", "根因二"],
                portfolio_health="组合健康度（集成）",
            )
        if response_schema is TrendInsightSchema:
            return TrendInsightSchema(
                summary=f"洞察产物-trend-{call_index}",
                findings=["发现"],
                pestel_political="政策维度：补贴退坡（集成）",
                pestel_economic="经济维度：利率上行（集成）",
                pestel_social="社会维度：绿色出行（集成）",
                pestel_technological="技术维度：固态电池（集成）",
                pestel_environmental="环境维度：碳排法规（集成）",
                pestel_legal="法律维度：数据合规（集成）",
                technology_roadmap=["短期：平台降本", "中期：电池量产", "长期：智驾生态"],
                scenario_plans=["基准情景", "乐观情景", "悲观情景"],
            )
        if response_schema is MarketCustomerInsightSchema:
            return MarketCustomerInsightSchema(
                summary=f"洞察产物-market_customer-{call_index}",
                findings=["发现"],
                customer_segments=["家庭用户", "年轻用户", "企业客户"],
                demand_priority_matrix=["补能效率（最高）", "智能座舱（高）", "总价（中）"],
                value_proposition_map=["补能焦虑→超充网络", "保值率低→电池质保"],
            )
        if response_schema is CompetitionInsightSchema:
            return CompetitionInsightSchema(
                summary=f"洞察产物-competition-{call_index}",
                findings=["发现"],
                five_forces_supplier_power="供应商议价：中高（电池集中度高）",
                five_forces_buyer_power="购买者议价：中",
                five_forces_new_entrants="新进入者威胁：高",
                five_forces_substitutes="替代品威胁：中",
                five_forces_rivalry="现有竞争强度：极高",
                competitor_radar=["研发 9/10", "成本 6/10", "渠道 5/10"],
                strategy_recommendations=["差异化避战", "锁定电池产能"],
            )
        if response_schema is SelfInsightSchema:
            return SelfInsightSchema(
                summary=f"洞察产物-self-{call_index}",
                findings=["发现"],
                internal_capabilities=["三电自研", "OTA 体系", "海外渠道"],
                vrio_assessment=["三电：核心能力", "软件：潜力能力"],
                resource_constraints=["研发预算", "电池产能", "数字化人才"],
            )
        if response_schema is OpportunityInsightSchema:
            return OpportunityInsightSchema(
                summary=f"洞察产物-opportunity-{call_index}",
                findings=["发现"],
                opportunity_list=["海外渗透", "高端智能", "电池银行"],
                priority_ranking=["海外（9）", "高端（8）", "电池银行（6）"],
                growth_path=["出海优先", "高端智能款", "能源服务"],
            )
        if response_schema is OpportunityGapInsightSchema:
            return OpportunityGapInsightSchema(
                summary=f"洞察产物-opportunity_gap-{call_index}",
                findings=["发现"],
                gap_quantification=["渠道覆盖差距 40%", "品牌溢价差距 25%"],
                capability_match_matrix=["海外×渠道：弱匹配", "高端×品牌：中匹配"],
                closure_strategies=["合资并购", "联名合作"],
            )
        if response_schema is InsightSynthesisSchema:
            return InsightSynthesisSchema(conclusions=["综合结论（集成）"])
        raise AssertionError(f"未知 response_schema: {response_schema!r}")

    async def _generate(prompt: str, config: Any = None, system_prompt: str | None = None) -> LLMResponse:
        if delay_sec:
            await asyncio.sleep(delay_sec)
        return LLMResponse(content='{"valid": true}', model="fake-llm")

    async def _close() -> None:
        return None

    fake = AsyncMock(spec=LLMClientPort)
    fake.structured_generate.side_effect = _structured_generate
    fake.generate.side_effect = _generate
    fake.close.side_effect = _close
    fake_probe: Any = fake
    fake_probe._blm_state = state
    return fake


class _RecordingEventBus:
    """记录发布事件的发布器（手写 EventPublisher 协议实现——4-6/4-7 先例）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


async def _assemble_chain(redis_client: Any, env: Any, retrieval: dict[str, Any], **fake_kwargs: Any) -> dict[str, Any]:
    """市场洞察全链手工装配（6-1 _assemble_chain 形态复用 + fail_schemas 透传）。"""
    from src.application.services.blm_planning_service import BlmPlanningService
    from src.application.services.dense_search_service import DenseSemanticSearchService
    from src.application.services.hybrid_search_service import HybridSearchService
    from src.application.services.isolation_guard_service import IsolationGuardService
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.application.services.retry_helpers import RetryPolicy
    from src.application.services.sparse_search_service import Bm25SparseSearchService
    from src.application.services.tool_execution_engine import ToolExecutionEngine
    from src.application.services.tool_execution_service import ToolExecutionService
    from src.application.services.tool_registry_service import ToolRegistryService
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.application.use_cases.agent_profile_loading import LoadAgentProfileUseCase
    from src.application.use_cases.run_blm_planning import RunBlmPlanningUseCase
    from src.domain.entities.agent import AgentRole
    from src.domain.ports.resolver import resolve
    from src.domain.services.rrf_fusion import fuse
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository
    from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository
    from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore

    redis_adapter = RedisAdapter(redis_client=redis_client)
    agent_repository = RedisAgentRepository(adapter=redis_adapter)
    isolation_repository = RedisIsolationRepository(adapter=redis_adapter)
    isolation_service = IsolationManagementService(
        isolation_repository=isolation_repository,
        agent_repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        agent_config_loader=resolve("agent_config_loader"),
        isolation_switch_log_repository=_StubIsolationSwitchLogRepository(),
        audit_service=None,
    )
    guard = IsolationGuardService(
        isolation_management_service=isolation_service,
        agent_repository=agent_repository,
        agent_config_loader=resolve("agent_config_loader"),
    )

    instantiate = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        isolation_service=isolation_service,
    )
    agent_id = (await instantiate.execute(role=AgentRole.CEO)).agent_id

    await resolve("agent_profile_loader").load(role=AgentRole.CEO, agent_id=agent_id)
    await resolve("skill_selector").list_active_skills()

    fake_llm = _make_fake_llm(**fake_kwargs)
    registry = ToolRegistryService(InMemoryToolRepository())
    registry.register_all()
    from unittest.mock import AsyncMock

    from src.domain.ports.sandbox_executor import SandboxExecutor

    sandbox = AsyncMock(spec=SandboxExecutor)
    sandbox.execute_code.return_value = {"status": "ok", "output": '{"valid": true}', "error": None}
    engine = ToolExecutionEngine(
        llm_client=fake_llm,
        sandbox=sandbox,
        retry_policy=RetryPolicy(max_attempts=1, initial_delay_sec=0.01),
    )
    tool_execution_service = ToolExecutionService(registry=registry, engine=engine)

    vector_storage = QdrantVectorStorage(retrieval["client"])
    hybrid = HybridSearchService(
        dense_search=DenseSemanticSearchService(embedding_service=retrieval["embedding"], vector_storage=vector_storage),
        sparse_search=Bm25SparseSearchService(embedding_service=retrieval["embedding"], vector_storage=vector_storage),
        fuse=fuse,
        graph_search=None,
        weights=[1.0, 1.0, 0.5],
    )

    recorder = _RecordingEventBus()
    snapshot_store = RedisSnapshotStore(adapter=redis_adapter)
    service = BlmPlanningService(
        llm_client=fake_llm,
        tool_execution_service=tool_execution_service,
        tool_registry_service=registry,
        isolation_guard=guard,
        hybrid_search=hybrid,
        search_collection=retrieval["collection"],
        event_publisher=recorder,
        snapshot_repository=snapshot_store,
    )
    langgraph_engine = LangGraphEngine(
        config=LangGraphConfig.from_env(), event_publisher=recorder, blm_planning_service=service
    )
    profile_use_case = LoadAgentProfileUseCase(
        profile_loader=resolve("agent_profile_loader"),
        repository=agent_repository,
        skill_selector=resolve("skill_selector"),
        event_publisher=InMemoryEventBus(),
    )
    use_case = RunBlmPlanningUseCase(
        agent_repository=agent_repository,
        agent_profile_use_case=profile_use_case,
        agent_engine=langgraph_engine,
        blm_planning_service=service,
        isolation_guard=guard,
        event_publisher=recorder,
    )
    return {
        "agent_id": agent_id,
        "agent_repository": agent_repository,
        "guard": guard,
        "profile_use_case": profile_use_case,
        "fake_llm": fake_llm,
        "service": service,
        "snapshot_store": snapshot_store,
        "recorder": recorder,
        "use_case": use_case,
        "task": "制定新能源汽车行业五年战略规划",
    }


async def _cleanup_chain(redis_client: Any, chain: dict[str, Any]) -> None:
    """清理 Agent 状态键（agent/isolation 双 namespace 精确删除）。"""
    agent_id = chain["agent_id"]
    for namespace in ("agent", "isolation"):
        await redis_client.delete(build_key(namespace, str(agent_id)))


async def _cleanup_step_snapshots(redis_client: Any, plan_id: str) -> None:
    """断言场景 per-step/latest 快照键逐键精确删除（采样轮 TTL 吸收——R2 钦定）。"""
    from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX

    keys = [f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}"] + [
        f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}:{step}" for step in EXPECTED_ORDER
    ]
    await redis_client.delete(*[build_key("snapshot", k) for k in keys])


async def _pg_probe_or_skip(env: Any) -> Any:
    """PG 双预检（连接 + event_outbox 表存在——5-4 R1-F07 先例；失败 skip）。"""
    import sqlalchemy as sa

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

    manager = PostgreSQLManager(
        PostgreSQLConfig(
            host=env.postgres.host,
            port=env.postgres.port,
            username=env.postgres.username,
            password=env.postgres.password,
            database=env.postgres.database,
        )
    )
    engine = manager.get_async_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT event_id FROM event_outbox LIMIT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL 不可达或 event_outbox 表未初始化: {exc}")
    return manager


async def _query_outbox_by_plan(engine: Any, plan_id: str) -> list[tuple[str, str | None]]:
    """按 plan_id 两级 JSONB 路径查行（R1-3 主键口径——aggregate_id 为 agent_id 不可用）。"""
    import sqlalchemy as sa

    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                sa.text(
                    "SELECT event_type, payload->'payload'->>'stage' AS stage "
                    "FROM event_outbox "
                    "WHERE payload->'payload'->>'plan_id' = :plan_id "
                    "AND created_at >= NOW() - INTERVAL '5 minutes'"
                ),
                {"plan_id": plan_id},
            )
        ).fetchall()
    return [(str(r[0]), r[1]) for r in rows]


async def _count_checkpoint_reached_leaks(engine: Any, plan_id: str) -> int:
    """CheckpointReached 零发布负向守卫（双通道——R1-F2）。

    独立查询（不动 _query_outbox_by_plan 的按 plan_id 语义）：plan_id 通道对
    CheckpointReached 恒 NULL（事件类字段族无 plan_id），第二通道以转义 LIKE
    捕获 phase_identifier="market_insight_*" 误发布形态（BLM 命名空间独占前缀；
    下划线必须转义——未转义 `_` 是单字符通配符，会误命中 Epic 1 既有
    "market-insight" 连字符形态值）。
    """
    import sqlalchemy as sa

    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                sa.text(
                    "SELECT COUNT(*) FROM event_outbox "
                    "WHERE event_type = 'CheckpointReached' "
                    "AND created_at >= NOW() - INTERVAL '5 minutes' "
                    "AND (payload->'payload'->>'plan_id' = :plan_id "
                    "OR payload->'payload'->>'phase_identifier' LIKE 'market\\_insight%')"
                ),
                {"plan_id": plan_id},
            )
        ).fetchall()
    return int(rows[0][0])


async def _delete_outbox_by_plan(engine: Any, plan_id: str) -> None:
    """按 plan_id 精确删除 outbox 行（真实发布场景清理）。"""
    import sqlalchemy as sa

    async with engine.begin() as conn:
        await conn.execute(
            sa.text("DELETE FROM event_outbox WHERE payload->'payload'->>'plan_id' = :plan_id"),
            {"plan_id": plan_id},
        )


async def _rebuild_with_real_publisher(chain: dict[str, Any], retrieval: dict[str, Any]) -> dict[str, Any]:
    """真实 publisher 重建三件（clear_singleton 防跨 loop 死连接——6-1 场景③ 先例）。"""
    from src.application.services.blm_planning_service import BlmPlanningService
    from src.application.use_cases.run_blm_planning import RunBlmPlanningUseCase
    from src.domain.ports.resolver import get_resolver, resolve
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig

    get_resolver().clear_singleton()
    real_publisher = resolve("event_publisher")
    service = BlmPlanningService(
        llm_client=chain["fake_llm"],
        tool_execution_service=chain["service"].tool_execution_service,
        tool_registry_service=chain["service"].tool_registry_service,
        isolation_guard=chain["service"].isolation_guard,
        hybrid_search=chain["service"].hybrid_search,
        search_collection=retrieval["collection"],
        event_publisher=real_publisher,
        snapshot_repository=chain["snapshot_store"],
    )
    engine = LangGraphEngine(config=LangGraphConfig.from_env(), event_publisher=real_publisher, blm_planning_service=service)
    use_case = RunBlmPlanningUseCase(
        agent_repository=chain["agent_repository"],
        agent_profile_use_case=chain["profile_use_case"],
        agent_engine=engine,
        blm_planning_service=service,
        isolation_guard=chain["guard"],
        event_publisher=real_publisher,
    )
    return {"service": service, "use_case": use_case, "agent_id": chain["agent_id"], "task": chain["task"]}


# ===================================================================
# 场景①：类型化全链（六步领域要素键族逐步断言 + 图身份锚）
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_1_typed_full_chain(real_redis: Any) -> None:
    """场景①：真实链完整跑通，六步 structured_output 键族与领域要素逐步断言。"""
    from tests.environments import get_test_env

    retrieval = await _ensure_retrieval(get_test_env())
    if retrieval is None:
        pytest.skip("检索服务（embedding/Qdrant）不可用")
    try:
        chain = await _assemble_chain(real_redis, get_test_env(), retrieval)
        result = await chain["use_case"].execute(agent_id=chain["agent_id"], task=chain["task"])

        # 图身份锚（终态含 BLM 专属键——图零改动回归）
        assert result.plan_id
        assert len(result.insight_steps) == 6, "六子步骤恒满 6"
        by_step = {s.step: s for s in result.insight_steps}
        # 六步键族 + 领域要素逐步断言（期望独立构造——禁经被测服务生成）
        for step_value in EXPECTED_ORDER:
            structured = by_step[step_value].structured_output
            assert structured is not None, f"{step_value} structured_output 未填充"
            assert set(structured) == EXPECTED_STRUCTURED_KEYS[step_value], (
                f"{step_value} 键族不一致: {set(structured) ^ EXPECTED_STRUCTURED_KEYS[step_value]}"
            )
        for key in _PESTEL_KEYS:
            assert by_step["trend"].structured_output[key], f"trend.{key}（PESTEL 要素）为空"
        for key in _FIVE_FORCES_KEYS:
            assert by_step["competition"].structured_output[key], f"competition.{key}（波特五力要素）为空"
        # 信封同源双公共字段
        for step_value in EXPECTED_ORDER:
            step_result = by_step[step_value]
            assert step_result.structured_output["summary"] == step_result.summary
            assert list(step_result.structured_output["findings"]) == list(step_result.findings)
        # gap 四字段传导（阶段 2 首步 prompt 含四标签——AC-7）
        trend_call = next(c for c in chain["fake_llm"]._blm_state["calls"] if c["schema"].__name__ == "TrendInsightSchema")
        for label in ("财务差距=", "运营差距=", "根因=", "组合健康度="):
            assert label in trend_call["prompt"], f"trend prompt 缺 gap 标签「{label}」（AC-7 四字段传导）"
        await _cleanup_chain(real_redis, chain)
        await _cleanup_step_snapshots(real_redis, result.plan_id)
    finally:
        await _dispose_retrieval(retrieval)


# ===================================================================
# 场景②：per-step 快照读回 + outbox 负向（真实发布装配）
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_2_per_step_snapshot_and_outbox_negative(real_redis: Any) -> None:
    """场景②：6 per-step + latest 逐键读回（七键/归属锚/版本写读一致）+ outbox
    非空锚 ≥9 行 + 零 CheckpointReached（两级 JSONB 路径）。"""
    from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX
    from tests.environments import get_test_env

    retrieval = await _ensure_retrieval(get_test_env())
    if retrieval is None:
        pytest.skip("检索服务（embedding/Qdrant）不可用")
    env = get_test_env()
    pg_manager = await _pg_probe_or_skip(env)
    pg_engine = pg_manager.get_async_engine()
    try:
        chain = await _assemble_chain(real_redis, env, retrieval)
        real_chain = await _rebuild_with_real_publisher(chain, retrieval)
        result = await real_chain["use_case"].execute(agent_id=real_chain["agent_id"], task=real_chain["task"])
        plan_id = result.plan_id

        # per-step 快照逐键读回（真实 RedisSnapshotStore.load 链）
        store = chain["snapshot_store"]
        for step_value in EXPECTED_ORDER:
            snapshot = await store.load(f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}:{step_value}")
            assert snapshot is not None, f"per-step 快照缺失: {plan_id}:{step_value}（真实链写入断裂）"
            assert snapshot.stage_id == f"market_insight_{step_value}"
            state = snapshot.state_data
            assert set(state) == EXPECTED_STEP_SNAPSHOT_KEYS, (
                f"{step_value} 七键不一致: {set(state) ^ EXPECTED_STEP_SNAPSHOT_KEYS}"
            )
            assert state["plan_id"] == plan_id, f"{step_value} 归属锚错配: {state['plan_id']}"
            assert state["structured_output"] is not None
            assert state["completed_steps"][-1] == step_value, f"{step_value} completed_steps 末位错配"
            # 版本写读一致（服务构造不传 state_version——实体默认 0，R2 措辞口径）
            assert snapshot.state_version == 0
        latest = await store.load(f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}")
        assert latest is not None, "latest 快照缺失（6-1 行为回归）"
        assert latest.state_data["completed_steps"] == 8, "latest 终态 8 步"

        # outbox：非空锚前置（R3-3）+ 零 CheckpointReached 负向（双通道独立查询——R1-F2）
        rows = await _query_outbox_by_plan(pg_engine, plan_id)
        assert len(rows) >= 9, f"plan {plan_id} outbox 行数 {len(rows)} < 9（真实发布装配断裂——负向断言将空真）"
        checkpoint_leak_count = await _count_checkpoint_reached_leaks(pg_engine, plan_id)
        assert checkpoint_leak_count == 0, f"CheckpointReached 落行 {checkpoint_leak_count}（6.3 语义分立被破坏）"
        stage_completed = [r for r in rows if r[0] == "BlmStageCompleted"]
        assert len(stage_completed) == 8, f"BlmStageCompleted {len(stage_completed)} 行 != 8"

        await _delete_outbox_by_plan(pg_engine, plan_id)
        await pg_engine.dispose()
        await _cleanup_chain(real_redis, chain)
        await _cleanup_step_snapshots(real_redis, plan_id)
    finally:
        await _dispose_retrieval(retrieval)


# ===================================================================
# 场景③：双杀注入降级 + 20 轮采样成功率（recorder 总线——R2 钦定）
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_3_double_kill_sampling(real_redis: Any) -> None:
    """场景③：相邻两步 Schema 恒败 → 恰两步降级互不传染 + 20 轮采样成功率 100%。

    采样轮边界（R2 钦定）：①每轮新铸 plan_id（execute 内 uuid——禁固定复用，
    第 2 轮起触发 482 重跑守卫全轮炸）②recorder 总线口径（真实发布 20×9=180
    行清理成本无谓）③采样轮快照键 TTL 86400 吸收不逐删（20 轮 × 7 键）。
    """
    from src.application.services.blm_planning_prompts import MarketCustomerInsightSchema, TrendInsightSchema
    from tests.environments import get_test_env

    retrieval = await _ensure_retrieval(get_test_env())
    if retrieval is None:
        pytest.skip("检索服务（embedding/Qdrant）不可用")
    env = get_test_env()
    try:
        fail_schemas = frozenset({TrendInsightSchema, MarketCustomerInsightSchema})
        for round_index in range(20):
            chain = await _assemble_chain(real_redis, env, retrieval, fail_schemas=fail_schemas)
            result = await chain["use_case"].execute(agent_id=chain["agent_id"], task=chain["task"])
            assert len(result.insight_steps) == 6, f"第 {round_index} 轮六步恒满 6"
            degraded = sorted(result.degraded_steps)
            assert degraded == ["market_customer", "trend"], (
                f"第 {round_index} 轮双杀应恰两步降级（实测 {degraded}——schema 身份注入与轮次无关，漂移即分派/降级机制异常）"
            )
            by_step = {s.step: s for s in result.insight_steps}
            for step_value in ("competition", "self", "opportunity", "opportunity_gap"):
                assert by_step[step_value].degraded is False, f"第 {round_index} 轮 {step_value} 被传染"
                assert by_step[step_value].structured_output is not None
            # 降级步信封完整（信封完整口径计入成功——AC-4）
            for step_value in ("trend", "market_customer"):
                degraded_step = by_step[step_value]
                envelope_complete = degraded_step.degraded and bool(degraded_step.degrade_reason)
                assert envelope_complete, f"第 {round_index} 轮 {step_value} 降级信封不完整"
                assert degraded_step.structured_output is None
            # 首轮抽验 per-step 快照降级标记（快照面锚——后续轮 TTL 吸收）
            if round_index == 0:
                from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX

                trend_snapshot = await chain["snapshot_store"].load(f"{BLM_PLANNING_SESSION_PREFIX}{result.plan_id}:trend")
                assert trend_snapshot is not None, "降级步 per-step 快照缺失（AC-2）"
                assert trend_snapshot.state_data["degraded"] is True
                assert trend_snapshot.state_data["structured_output"] is None
                assert "structured_output" in trend_snapshot.state_data
            await _cleanup_chain(real_redis, chain)
            # 采样轮快照键不逐删（TTL 86400 吸收——R2 钦定）
        # 成功率语义由轮内逐条断言承载（任一步失败即中止——20 轮 × 每轮全断言
        # ≡ 100% 的逐轮验证，强于尾聚合；原尾聚合 rate 断言数学恒真已删——R1-F3）
    finally:
        await _dispose_retrieval(retrieval)


# ===================================================================
# 场景④-A：并发正确性（5 不同 plan_id——不断言 P95）
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_4a_concurrent_five_plans(real_redis: Any) -> None:
    """场景④-A：5 任务 asyncio.gather 全成功 + per-step 快照/outbox 按 plan 分离。

    per-plan 预期计数钉死 9 行（PlanningStarted×1 + BlmStageCompleted×8；
    AgentDecided 由引擎发布且 payload 无 plan_id 子键、两级路径过滤天然排除）。
    """
    from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX
    from tests.environments import get_test_env

    retrieval = await _ensure_retrieval(get_test_env())
    if retrieval is None:
        pytest.skip("检索服务（embedding/Qdrant）不可用")
    env = get_test_env()
    pg_manager = await _pg_probe_or_skip(env)
    pg_engine = pg_manager.get_async_engine()
    try:
        chain = await _assemble_chain(real_redis, env, retrieval)
        real_chain = await _rebuild_with_real_publisher(chain, retrieval)
        use_case = real_chain["use_case"]

        async def _run_one() -> Any:
            return await use_case.execute(agent_id=real_chain["agent_id"], task=real_chain["task"])

        results = list(await asyncio.gather(*[_run_one() for _ in range(5)]))
        assert len(results) == 5
        plan_ids = tuple(sorted(r.plan_id for r in results))
        assert len(set(plan_ids)) == 5, f"plan_id 去重 {len(set(plan_ids))} != 5（OD-4 不同 plan_id）"

        # per-step 快照归属锚逐 plan 断言（R1-4）
        store = chain["snapshot_store"]
        for plan_id in plan_ids:
            for step_value in EXPECTED_ORDER:
                snapshot = await store.load(f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}:{step_value}")
                assert snapshot is not None, f"plan {plan_id} 步 {step_value} 快照缺失"
                assert snapshot.state_data["plan_id"] == plan_id, (
                    f"plan {plan_id} 步 {step_value} 归属锚错配: {snapshot.state_data['plan_id']}（跨 plan 污染）"
                )
            latest = await store.load(f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}")
            assert latest is not None and latest.state_data["plan_id"] == plan_id

        # outbox 按 plan 逐任务计数（9 行/plan）
        for plan_id in plan_ids:
            rows = await _query_outbox_by_plan(pg_engine, plan_id)
            planning = sum(1 for r in rows if r[0] == "PlanningStarted")
            stage_completed = sum(1 for r in rows if r[0] == "BlmStageCompleted")
            assert planning == 1, f"plan {plan_id} PlanningStarted {planning} != 1"
            assert stage_completed == 8, f"plan {plan_id} BlmStageCompleted {stage_completed} != 8"
            await _delete_outbox_by_plan(pg_engine, plan_id)
        await pg_engine.dispose()
        await _cleanup_chain(real_redis, chain)
        for plan_id in plan_ids:
            await _cleanup_step_snapshots(real_redis, plan_id)
    finally:
        await _dispose_retrieval(retrieval)


# ===================================================================
# 场景④-B：市场洞察段 P95<25s 独立串行采样（≥20 轮）
# ===================================================================


@pytest.mark.asyncio
async def test_scenario_4b_market_insight_p95(real_redis: Any) -> None:
    """场景④-B：市场洞察段 P95<25s（OD-3 Fake LLM 管线开销口径）。

    口径差声明（OD-3/DC-7 先例）：真实 LLM 延迟显式出栈（单次结构化调用
    真实环境 30s+ 量级——归 6.1-DF1 部署验证）；task 文本固定是模块级
    embedding 缓存命中前提（R3 补——每轮换文本则 140 次 embed 全 miss 假红）；
    观测点 = timeline 两端（trend.started_at → synthesis.completed_at，
    裸 step 键口径）；P95 = durations[ceil(0.95*n)-1]（20 轮次大值档）。
    """
    from datetime import datetime

    from tests.environments import get_test_env

    retrieval = await _ensure_retrieval(get_test_env())
    if retrieval is None:
        pytest.skip("检索服务（embedding/Qdrant）不可用")
    env = get_test_env()
    try:
        durations: list[float] = []
        for _ in range(20):
            chain = await _assemble_chain(real_redis, env, retrieval)
            result = await chain["use_case"].execute(agent_id=chain["agent_id"], task=chain["task"])
            # 观测点钦定：timeline 两端（经服务投影读——InsightSynthesis VO 无时间戳）
            timeline = {entry["step"]: entry for entry in chain["service"].project_timeline(result.plan_id)}
            seg_start = datetime.fromisoformat(timeline["trend"]["started_at"])
            seg_end = datetime.fromisoformat(timeline["market_insight_synthesis"]["completed_at"])
            durations.append((seg_end - seg_start).total_seconds())
            await _cleanup_chain(real_redis, chain)
            # 采样轮快照键 TTL 吸收（R2 钦定）
        import math

        durations.sort()
        p95 = durations[math.ceil(len(durations) * 0.95) - 1]
        assert p95 < 25.0, f"市场洞察段 P95={p95:.2f}s >= 25s（OD-3 Fake LLM 管线开销口径）"
    finally:
        await _dispose_retrieval(retrieval)
