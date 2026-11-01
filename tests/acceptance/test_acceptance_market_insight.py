"""Story 6-2 — 市场洞察六子步骤类型化输出与 per-step Checkpoint 快照验收测试。

模板基准: test_acceptance_postgresql_relational_layer.py（R6——多行 @scenario
字面量路径 + 场景绑定与步骤实现交替排列 + AC 横幅分组 + 中文 Gherkin）；
装配形态对齐 6-1 test_acceptance_blm_planning.py（真实服务链 + Fake LLM
唯一豁免替身 + 延迟 import 纪律 + 场景分档表 + teardown 五步链）。

14 场景三属性分档表（Subtask 0.4 钉死——层级/LLM 依赖/服务门控）：

| #  | 场景                 | 层级               | LLM          | 服务门控      |
|----|----------------------|--------------------|--------------|---------------|
| 1  | AC-1.1 类型化全量    | 用例级（全链装配） | Fake         | Redis+检索(R) |
| 2  | AC-1.2 执行序+Schema | 用例级             | Fake         | R             |
| 3  | AC-1.3 综合消费      | 用例级             | Fake 捕获    | R             |
| 4  | AC-2.1 快照全量读回  | 用例级+真实快照链  | Fake         | R             |
| 5  | AC-2.2 latest 零回归 | 用例级（读侧用例） | Fake         | R             |
| 6  | AC-2.3 降级步快照    | 用例级             | Fake 失败注  | R             |
| 7  | AC-3.1 事件零发布    | 用例级（真实发布） | Fake         | R+PG          |
| 8  | AC-4.1 单点降级      | 用例级             | Fake Schema 注 | R           |
| 9  | AC-4.2 双杀互不传染  | 用例级             | Fake Schema 注 | R           |
| 10 | AC-5.1 段延迟单轮    | 用例级（timeline 观测） | Fake     | R             |
| 11 | AC-6.1 并发 5 任务   | 用例级（gather+真实发布） | Fake    | R+PG          |
| 12 | AC-7.1 四字段传导    | 用例级（prompt 断言） | Fake       | R             |
| 13 | AC-7.2 gap 降级标注  | 用例级             | Fake Schema 注 | R           |
| 14 | 收尾完成清单         | 静态完成清单       | 无           | 无            |

检索门控档位（R = embedding+Qdrant 双探测 + 租户隔离 collection 建制语料
upsert，3-1a 验收先例；检索不可达环境逐场景动态 skip；PG = event_outbox
连接+表存在双预检，5-4 R1-F07 先例）。

口径声明：
- AC-5 市场洞察段 P95<25s 的 ≥20 轮采样归集成 5.4b 承载（OD-3 Fake LLM
  管线开销口径——真实 LLM 延迟显式出栈归 6.1-DF1）；验收层单轮窗口断言
  （分化维度表钦定——防全管线 60 次冗余）。
- AC-4 降级注入一律按 response_schema 身份（fail_schemas——schema 恒败，
  首调与重试皆败）；禁用调用序算术注入（重试同占调用序、20 轮采样下序号
  连续累计漂移错位——AC-4 R1 修订钦定）。

新模块延迟 import 纪律：本 Story 交付的模块（六类型化 Schema /
MARKET_INSIGHT_STEP_SCHEMA / InsightStepResult.structured_output 扩展 /
per-step 快照写入）一律在步骤函数体内延迟 import——模块顶部 import 会使
pytest 收集期整文件 collection error，已实现/未实现场景一起炸，无法逐
Task 转绿（Task 0 预期红因 = 运行期 ImportError：既有模块中缺失的类名）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_market_insight.py -v

测试隔离:
    - 场景级独立 Redis 客户端 + 同循环关闭（跨循环 "Event loop is closed" 存档教训）
    - Agent 状态键逐 agent_id 精确删除（agent/isolation 双 namespace；禁 flush）
    - 检索 collection 场景级唯一命名 + teardown 精确删除
    - per-step/latest 快照键按 plan_id 天然隔离（TTL 86400 吸收——6-1 先例）
    - outbox 事件清理走 context teardown（K8 先例——断言失败也执行）
    - BDD 步骤禁 @pytest.mark.asyncio（context 数据丢失红线），统一 _run_async
    - Fake LLM 端口替身是外部 SaaS 豁免面（分派键 = response_schema 身份）
    - xdist_group 复用 6-1 组名 blm-planning-perf（跨 Story 采样场景全局同
      worker 串行——R2-2 修订钦定）
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Coroutine, Generator
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pytest_bdd import given, scenario, then, when

from src.infrastructure.storage.redis.key_builder import build_key

#: _run_async 泛型参数（协程返回类型透传——裸 Any 向调用点扩散 no-any-return）
_T = TypeVar("_T")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# 文件名不含服务关键词，acceptance conftest 不会自动添加 marker——显式声明；
# xdist_group 复用 6-1 组名（性能/采样场景跨 Story 同 worker 串行化）
pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.redis,
    pytest.mark.xdist_group("blm-planning-perf"),
]

#: 六子步骤执行序期望（独立构造自 or.md L385-415 钦定序——禁经被测服务生成）
EXPECTED_INSIGHT_ORDER: tuple[str, ...] = (
    "trend",
    "market_customer",
    "competition",
    "self",
    "opportunity",
    "opportunity_gap",
)

#: 六步类型化 Schema 名期望序（独立构造——「每步调用使用该步专属类型化
#: Schema」断言锚；与 Task 0.1 冻结表同源但独立字面量，非 import 反射自证）
EXPECTED_STEP_SCHEMA_NAMES: dict[str, str] = {
    "trend": "TrendInsightSchema",
    "market_customer": "MarketCustomerInsightSchema",
    "competition": "CompetitionInsightSchema",
    "self": "SelfInsightSchema",
    "opportunity": "OpportunityInsightSchema",
    "opportunity_gap": "OpportunityGapInsightSchema",
}

#: 各步 structured_output 期望键族（独立构造自 Task 0.1 冻结表——逐字字面量，
#: 禁 import Schema 后反射自证恒真；summary/findings 双公共字段同源含入）
_EXPECTED_TREND_KEYS: frozenset[str] = frozenset(
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
)
_EXPECTED_MARKET_CUSTOMER_KEYS: frozenset[str] = frozenset(
    {"summary", "findings", "customer_segments", "demand_priority_matrix", "value_proposition_map"}
)
_EXPECTED_COMPETITION_KEYS: frozenset[str] = frozenset(
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
)
_EXPECTED_SELF_KEYS: frozenset[str] = frozenset(
    {"summary", "findings", "internal_capabilities", "vrio_assessment", "resource_constraints"}
)
_EXPECTED_OPPORTUNITY_KEYS: frozenset[str] = frozenset(
    {"summary", "findings", "opportunity_list", "priority_ranking", "growth_path"}
)
_EXPECTED_OPPORTUNITY_GAP_KEYS: frozenset[str] = frozenset(
    {"summary", "findings", "gap_quantification", "capability_match_matrix", "closure_strategies"}
)

#: 六步期望键族总表（AC-1.1 全量断言锚——期望构造侧唯一事实源）
EXPECTED_STEP_STRUCTURED_KEYS: dict[str, frozenset[str]] = {
    "trend": _EXPECTED_TREND_KEYS,
    "market_customer": _EXPECTED_MARKET_CUSTOMER_KEYS,
    "competition": _EXPECTED_COMPETITION_KEYS,
    "self": _EXPECTED_SELF_KEYS,
    "opportunity": _EXPECTED_OPPORTUNITY_KEYS,
    "opportunity_gap": _EXPECTED_OPPORTUNITY_GAP_KEYS,
}

#: PESTEL 六维度字段族（AC-1.1 看趋势要素断言锚——OD-8 工具产物化）
_PESTEL_KEYS: tuple[str, ...] = (
    "pestel_political",
    "pestel_economic",
    "pestel_social",
    "pestel_technological",
    "pestel_environmental",
    "pestel_legal",
)

#: 波特五力五维字段族（AC-1.1 看竞争要素断言锚——OD-8 工具产物化）
_FIVE_FORCES_KEYS: tuple[str, ...] = (
    "five_forces_supplier_power",
    "five_forces_buyer_power",
    "five_forces_new_entrants",
    "five_forces_substitutes",
    "five_forces_rivalry",
)

#: gap 四字段摘要标签族（AC-7.1 断言锚——Task 2.3 冻结形态：四标签子串恒存，
#: 「财务差距=」子串兼容 6-1 单测 L533 先例）
_GAP_SUMMARY_LABELS: tuple[str, ...] = (
    "财务差距=",
    "运营差距=",
    "根因=",
    "组合健康度=",
)

#: 降级标注前缀字面量（独立构造——DEGRADATION_MARKER_PREFIX 单源在 prompts，
#: 断言侧字面量防 import 自证）
_DEGRADATION_MARKER = "[降级]"

# 真实检索语料（背景建制——与任务主题相关，保证 dense 命中；沿 6-1 语料）
_CORPUS_TEXTS: tuple[str, ...] = (
    "新能源汽车行业进入战略分析报告：市场增速放缓但渗透率持续提升",
    "财务业绩差距分析：营收目标达成率与毛利率下滑根因",
    "竞争对手动态：头部厂商价格战与渠道下沉策略",
    "宏观趋势：政策补贴退坡与技术路线演进（固态电池）",
    "内部能力评估：研发投入占比与组织能力短板",
    "市场机会：海外新兴市场增长路径与机会差距量化",
)

# Fake LLM 各步骤产出摘要标记（步骤值可判别——synthesis 注入断言锚）
_FAKE_STEP_SUMMARY_PREFIX = "市场洞察产物"


class _CachedEmbedding:
    """embedding 查询/文档向量缓存代理（测试面性能优化——非被测对象）。

    背景：embedding API 往返占 BLM 测试时长 >95%（6-1 探针实证 7 次
    embed_query ≈2.8s/轮，而装配/清理 ≈0）——同文本查询向量经 bge-m3
    确定性推理恒同（缓存命中与真实调用等价）。模块级缓存跨场景复用
    （进程内有效；跨文件不共享——共享面是外部 embedding 服务）。
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


# ===================================================================
# 共享基建：三件套（context fixture / 模块级 event_loop / _run_async）
# ===================================================================


@pytest.fixture(scope="module")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """模块级事件循环（BDD 步骤禁 @pytest.mark.asyncio——同循环三件套）。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def context(
    event_loop: asyncio.AbstractEventLoop,
    acceptance_env_config: Any,
) -> Generator[dict[str, Any], None, None]:
    """BDD 步骤间共享状态容器（场景级独立 Redis 客户端 + 同循环 teardown）。

    teardown 顺序：恢复端口覆写 → 删 outbox 事件行（真实发布场景）→ 删检索
    collection → 删 Agent 状态键 → 关闭 Redis 客户端（全部 _run_async 同循环；
    K8 先例——断言失败也执行）。per-step/latest 快照键按 plan_id 天然隔离 +
    TTL 86400 吸收（6-1 先例——不逐键删除）。
    """
    import redis.asyncio as aioredis

    redis_client = aioredis.Redis(
        host=acceptance_env_config.redis.host,
        port=acceptance_env_config.redis.port,
        password=acceptance_env_config.redis.password,
        decode_responses=True,
    )
    ctx: dict[str, Any] = {
        "_tenant": uuid.uuid4(),
        "_loop": event_loop,
        "_env_config": acceptance_env_config,
        "_redis_client": redis_client,
        "_agent_ids": [],
        "_restorers": [],
        "_created_collections": [],
        "_outbox_event_ids": [],
    }
    yield ctx

    # 1) 端口覆写还原（真实发布链路场景注册的替身）
    for restore in ctx["_restorers"]:
        restore()
    # 2) outbox 事件清理（真实发布场景按 event_id 精确删除——K8 teardown 先例）
    if ctx["_outbox_event_ids"]:
        _cleanup_outbox_rows(ctx)
    # 3) 检索 collection 精确删除
    for name in list(ctx["_created_collections"]):
        try:
            _run_async(event_loop, _delete_collection(ctx, name))
        except Exception:
            pass
    # 4) Agent 状态键精确删除（agent/isolation 双 namespace）
    for agent_id in ctx["_agent_ids"]:
        for namespace in ("agent", "isolation"):
            _run_async(event_loop, redis_client.delete(build_key(namespace, str(agent_id))))
    # 5) 同循环关闭客户端
    _run_async(event_loop, redis_client.close())


def _run_async(event_loop: asyncio.AbstractEventLoop, coro: Coroutine[Any, Any, _T]) -> _T:
    """在模块级共享事件循环上同步调度协程（BDD 步骤禁 @pytest.mark.asyncio）。

    泛型签名保留协程精确返回类型（裸 Any 会向全部调用点扩散 no-any-return）。
    """
    return event_loop.run_until_complete(coro)


async def _delete_collection(ctx: dict[str, Any], name: str) -> None:
    from qdrant_client import AsyncQdrantClient

    from src.infrastructure.config.qdrant import QdrantConfig

    env = ctx["_env_config"]
    config = QdrantConfig(
        host=env.qdrant.host, port=env.qdrant.port, grpc_port=env.qdrant.grpc_port, api_key=env.qdrant.api_key
    )
    client = AsyncQdrantClient(url=f"http://{config.host}:{config.port}", timeout=10)
    try:
        await client.delete_collection(name)
    finally:
        await client.close()


def _cleanup_outbox_rows(ctx: dict[str, Any]) -> None:
    """按 event_id 精确删除本场景落库的 outbox 事件行（真实发布场景清理）。"""
    import sqlalchemy as sa

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

    env = ctx["_env_config"]

    async def _delete() -> None:
        manager = PostgreSQLManager(
            PostgreSQLConfig(
                host=env.postgres.host,
                port=env.postgres.port,
                username=env.postgres.username,
                password=env.postgres.password,
                database=env.postgres.database,
            )
        )
        try:
            engine = manager.get_async_engine()
            async with engine.begin() as conn:
                await conn.execute(
                    sa.text("DELETE FROM event_outbox WHERE event_id = ANY(:ids)"),
                    {"ids": [str(e) for e in ctx["_outbox_event_ids"]]},
                )
            await engine.dispose()
        except Exception:
            pass  # 清理尽力而为（PG 不可达时跳过——生产残留归 L170 锚知悉）

    try:
        _run_async(ctx["_loop"], _delete())
    except Exception:
        pass


# ===================================================================
# 共享基建：Fake LLM（八键族 Schema 分派 + schema 身份失败注入 + 配置捕获）
# ===================================================================


def _make_fake_llm(
    *,
    fail_call_indices: frozenset[int] = frozenset(),
    fail_schemas: frozenset[type] = frozenset(),
    hold_at_call: int | None = None,
    delay_sec: float = 0.0,
) -> Any:
    """BLM 面 Fake LLM 端口替身（外部 SaaS 豁免面——分派键 = response_schema 身份）。

    分派键 = GapAnalysisSchema / 六类型化 Schema / InsightSynthesisSchema 八者
    身份互斥（6-2 扩展——AC-4 R1 修订钦定注入键）。注入控制：
    - fail_call_indices: 按调用序（0 基）注入 LLMAPIError（挂起场景兼容保留）
    - fail_schemas: 按 response_schema 身份恒败（首调与重试皆败——schema 注入
      与轮次无关，AC-4 R1 钦定主注入键；禁调用序算术注入防漂移错位）
    - hold_at_call: 指定调用序挂起（await asyncio.Event）
    - delay_sec: 每调用延迟（计时下界注入）

    calls 记录每次 structured_generate 的 prompt/schema/temperature/timeout
    实参（AC-1.2 Schema 分派断言锚 + AC-7 prompt 注入断言锚）。
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
            await state["hold_event"].wait()  # 门控挂起（场景 teardown 前 set 释放）
        if response_schema in fail_schemas:
            raise __import__("src.domain.exceptions.llm_exceptions", fromlist=["LLMAPIError"]).LLMAPIError(
                f"Fake schema 身份注入失败（{response_schema.__name__} 恒败——首调与重试皆败）"
            )
        if call_index in fail_call_indices:
            raise __import__("src.domain.exceptions.llm_exceptions", fromlist=["LLMAPIError"]).LLMAPIError(
                f"Fake 注入失败（调用序 {call_index}）"
            )

        # 六类型化 Schema 分派（返回体字段族与 Task 0.1 冻结表逐字段对齐——
        # 与断言侧期望常量各自独立构造，互证非自证）
        if response_schema.__name__ == "TrendInsightSchema":
            return response_schema(
                summary=f"{_FAKE_STEP_SUMMARY_PREFIX}:trend（结构化要点）",
                findings=["发现一：政策与技术双趋势信号明确", "发现二：情景分化风险上升"],
                pestel_political="政策维度：补贴退坡与准入收紧",
                pestel_economic="经济维度：利率上行压制可选消费",
                pestel_social="社会维度：绿色出行消费习惯迁移",
                pestel_technological="技术维度：固态电池与智能驾驶演进",
                pestel_environmental="环境维度：碳排法规趋严",
                pestel_legal="法律维度：数据合规与知识产权要求升级",
                technology_roadmap=["短期：平台化架构降本", "中期：固态电池量产", "长期：智驾生态成型"],
                scenario_plans=["基准情景：渗透率稳步提升", "乐观情景：政策加码提速", "悲观情景：价格战侵蚀利润"],
            )
        if response_schema.__name__ == "MarketCustomerInsightSchema":
            return response_schema(
                summary=f"{_FAKE_STEP_SUMMARY_PREFIX}:market_customer（结构化要点）",
                findings=["发现一：细分需求分化明显", "发现二：补能效率是首要痛点"],
                customer_segments=["价格敏感型家庭用户", "科技尝鲜型年轻用户", "运营降本型企业客户"],
                demand_priority_matrix=["续航与补能效率（最高优先）", "智能座舱体验（高优先）", "购车总价（中优先）"],
                value_proposition_map=["痛点：补能焦虑→收益：超充网络覆盖", "痛点：保值率低→收益：电池质保计划"],
            )
        if response_schema.__name__ == "CompetitionInsightSchema":
            return response_schema(
                summary=f"{_FAKE_STEP_SUMMARY_PREFIX}:competition（结构化要点）",
                findings=["发现一：竞争强度处历史高位", "发现二：头部厂商成本优势扩大"],
                five_forces_supplier_power="供应商议价能力：中高（电池厂商集中度高）",
                five_forces_buyer_power="购买者议价能力：中（选择增多但转换成本存在）",
                five_forces_new_entrants="新进入者威胁：高（跨界造车与代工模式降低门槛）",
                five_forces_substitutes="替代品威胁：中（公共交通与共享出行部分替代）",
                five_forces_rivalry="现有竞争者强度：极高（价格战与渠道战并发）",
                competitor_radar=["研发能力：头部厂商 9/10", "成本控制：二线厂商 6/10", "渠道下沉：新势力 5/10"],
                strategy_recommendations=["以差异化配置避开正面价格战", "锁定上游电池产能对冲供应风险"],
            )
        if response_schema.__name__ == "SelfInsightSchema":
            return response_schema(
                summary=f"{_FAKE_STEP_SUMMARY_PREFIX}:self（结构化要点）",
                findings=["发现一：三电自研是核心能力", "发现二：渠道与品牌存在短板"],
                internal_capabilities=["三电自研平台", "软件 OTA 体系", "海外渠道初步布局"],
                vrio_assessment=[
                    "三电平台：价值+稀有+难模仿+组织适配（核心能力）",
                    "软件体系：价值+稀有（潜力能力）",
                    "海外渠道：价值+非稀有（待强化）",
                ],
                resource_constraints=["研发预算受限", "电池产能依赖外部", "组织数字化人才缺口"],
            )
        if response_schema.__name__ == "OpportunityInsightSchema":
            return response_schema(
                summary=f"{_FAKE_STEP_SUMMARY_PREFIX}:opportunity（结构化要点）",
                findings=["发现一：海外市场窗口期明确", "发现二：高端智能化溢价空间大"],
                opportunity_list=["海外新兴市场渗透", "高端智能化细分", "电池银行服务模式"],
                priority_ranking=["海外新兴市场（评分 9）", "高端智能化（评分 8）", "电池银行（评分 6）"],
                growth_path=["现产品×新市场：出海优先", "新产品×现市场：高端智能款", "新产品×新市场：能源服务"],
            )
        if response_schema.__name__ == "OpportunityGapInsightSchema":
            return response_schema(
                summary=f"{_FAKE_STEP_SUMMARY_PREFIX}:opportunity_gap（结构化要点）",
                findings=["发现一：渠道差距是首要瓶颈", "发现二：品牌溢价能力不足"],
                gap_quantification=["海外渠道覆盖差距 40%", "高端品牌溢价能力差距 25%"],
                capability_match_matrix=["海外机会×渠道能力：弱匹配", "高端机会×品牌能力：中匹配"],
                closure_strategies=["合资并购获取渠道", "联名合作提升品牌溢价"],
            )
        if response_schema.__name__ == "GapAnalysisSchema":
            return response_schema(
                financial_gap="财务差距量化：营收达成率 82%，毛利率 -3.2pct",
                operational_gap="运营差距分析：交付周期延长与产能利用率不足",
                root_causes=["价格竞争侵蚀毛利", "供应链成本上升", "组织响应迟缓"],
                portfolio_health="业务组合健康度：核心业务稳健，新兴业务双低",
            )
        if response_schema.__name__ == "InsightSynthesisSchema":
            return response_schema(conclusions=["综合结论一：优先补强内部能力", "综合结论二：把握海外机会窗口"])
        raise AssertionError(f"未知 response_schema: {response_schema!r}")

    async def _generate(prompt: str, config: Any = None, system_prompt: str | None = None) -> LLMResponse:
        if delay_sec:
            await asyncio.sleep(delay_sec)
        return LLMResponse(content='{"valid": true, "confidence": 0.9}', model="fake-llm")

    async def _close() -> None:
        return None

    fake = AsyncMock(spec=LLMClientPort)
    fake.structured_generate.side_effect = _structured_generate
    fake.generate.side_effect = _generate
    fake.close.side_effect = _close
    fake_probe: Any = fake  # 测试探针挂载（Any 收窄——动态属性断言锚）
    fake_probe._blm_state = state
    return fake


# ===================================================================
# 共享基建：记录总线 + 真实链装配
# ===================================================================


class _RecordingEventBus:
    """记录发布事件的发布器（手写 EventPublisher 协议实现——4-6/4-7/5-3 先例）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


def _ensure_qdrant_retrieval(ctx: dict[str, Any]) -> None:
    """检索门控 + 租户隔离 collection 建制语料 upsert（3-1a 验收先例）。

    embedding 客户端构造 + Qdrant health 双探测，任一不可达 pytest.skip；
    建制语料 upsert 后返回（collection 名经 ctx["retrieval_collection"] 共享）。
    """
    if "retrieval_collection" in ctx:
        return

    from qdrant_client import AsyncQdrantClient

    from src.infrastructure.config.embedding import EmbeddingConfig
    from src.infrastructure.config.qdrant import QdrantConfig
    from src.infrastructure.external_services.embedding.embedding_api_client import EmbeddingAPIClient

    env = ctx["_env_config"]
    loop = ctx["_loop"]

    async def _setup() -> tuple[str, Any, AsyncQdrantClient]:
        embedding = _CachedEmbedding(EmbeddingAPIClient(EmbeddingConfig.from_env()))
        qconfig = QdrantConfig(
            host=env.qdrant.host, port=env.qdrant.port, grpc_port=env.qdrant.grpc_port, api_key=env.qdrant.api_key
        )
        client = AsyncQdrantClient(url=f"http://{qconfig.host}:{qconfig.port}", timeout=30)
        await embedding.embed_query("连通性探测")  # embedding 服务不可达即抛
        await client.get_collections()  # Qdrant 不可达即抛

        collection = f"test_market_{uuid.uuid4().hex[:8]}"
        from qdrant_client import models

        await client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
        )
        vectors = await embedding.embed_documents(list(_CORPUS_TEXTS))
        points = [
            models.PointStruct(id=str(uuid.uuid4()), vector=vec, payload={"text": text})
            for vec, text in zip(vectors, _CORPUS_TEXTS)
        ]
        await client.upsert(collection_name=collection, points=points)
        return collection, embedding, client

    try:
        collection, embedding, qclient = _run_async(loop, _setup())
    except Exception as exc:  # 探测失败——检索不可达环境动态 skip
        pytest.skip(f"检索服务（embedding/Qdrant）不可用: {exc}")

    ctx["retrieval_collection"] = collection
    ctx["_created_collections"].append(collection)
    ctx["_embedding_client"] = embedding
    ctx["_qdrant_client"] = qclient


def _make_real_hybrid_search(ctx: dict[str, Any]) -> Any:
    """真实 hybrid 检索服务（场景级实例——dense+sparse 双路，graph 路豁免注记）。

    全真实组件手动构造（EmbeddingAPIClient/QdrantVectorStorage/
    DenseSemanticSearchService/Bm25SparseSearchService/HybridSearchService/rrf fuse）；
    graph_search=None（Neo4j 路非本 Story 检索依赖面）。场景级实例避免
    SINGLETON 缓存跨 loop 死连接。
    """
    _ensure_qdrant_retrieval(ctx)

    from src.application.services.dense_search_service import DenseSemanticSearchService
    from src.application.services.hybrid_search_service import HybridSearchService
    from src.application.services.sparse_search_service import Bm25SparseSearchService
    from src.domain.services.rrf_fusion import fuse
    from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage

    vector_storage = QdrantVectorStorage(ctx["_qdrant_client"])
    dense = DenseSemanticSearchService(embedding_service=ctx["_embedding_client"], vector_storage=vector_storage)
    sparse = Bm25SparseSearchService(embedding_service=ctx["_embedding_client"], vector_storage=vector_storage)
    return HybridSearchService(dense_search=dense, sparse_search=sparse, fuse=fuse, graph_search=None, weights=[1.0, 1.0, 0.5])


class _StubIsolationSwitchLogRepository:
    """手写 duck-typing 日志仓储替身（5-3 验收同款——零 IO 替身，真实链归 5-6）。"""

    def __init__(self) -> None:
        self.saved_logs: list[Any] = []

    async def save(self, log: Any) -> None:
        self.saved_logs.append(log)

    async def search(self, query: Any) -> Any:
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogSearchResult

        return IsolationSwitchLogSearchResult(items=(), total=0, offset=query.offset, limit=query.limit)


def _make_real_guard_chain(ctx: dict[str, Any]) -> Any:
    """真实隔离守卫链（5-3 验收同款三依赖注入——场景级 Redis 仓储）。"""
    if "isolation_guard_chain" in ctx:
        return ctx["isolation_guard_chain"]["guard"]

    from src.application.services.isolation_guard_service import IsolationGuardService
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

    loop = ctx["_loop"]
    redis_client = ctx["_redis_client"]
    config_loader = resolve("agent_config_loader")
    agent_repository = RedisAgentRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_repository = RedisIsolationRepository(adapter=RedisAdapter(redis_client=redis_client))
    isolation_service = IsolationManagementService(
        isolation_repository=isolation_repository,
        agent_repository=agent_repository,
        event_publisher=InMemoryEventBus(),
        agent_config_loader=config_loader,
        isolation_switch_log_repository=_StubIsolationSwitchLogRepository(),
        audit_service=None,
    )
    guard = IsolationGuardService(
        isolation_management_service=isolation_service,
        agent_repository=agent_repository,
        agent_config_loader=config_loader,
    )
    ctx["isolation_guard_chain"] = {
        "guard": guard,
        "agent_repository": agent_repository,
        "isolation_service": isolation_service,
    }
    _run_async(loop, redis_client.ping())
    return guard


def _instantiate_real_agent(ctx: dict[str, Any]) -> uuid.UUID:
    """经真实实例化用例构造 CEO Agent（5-3 同步形态先例）。"""
    from src.application.use_cases.agent_instantiation import InstantiateAgentUseCase
    from src.domain.entities.agent import AgentRole
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

    chain = ctx["isolation_guard_chain"]
    use_case = InstantiateAgentUseCase(
        config_loader=resolve("agent_config_loader"),
        repository=chain["agent_repository"],
        event_publisher=InMemoryEventBus(),
        isolation_service=chain["isolation_service"],
    )
    result = _run_async(ctx["_loop"], use_case.execute(role=AgentRole.CEO))
    agent_id: uuid.UUID = result.agent_id
    ctx["_agent_ids"].append(agent_id)
    return agent_id


def _make_registry() -> Any:
    """手工组装工具注册服务（InMemoryToolRepository + register_all——5-3 同款）。"""
    from src.application.services.tool_registry_service import ToolRegistryService
    from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

    registry = ToolRegistryService(InMemoryToolRepository())
    registry.register_all()
    return registry


def _build_tool_execution_service(fake_llm: Any) -> Any:
    """真实工具执行装饰链（Fake LLM 注入——5-3 集成/验收同款）。

    sandbox 替身纪律：AsyncMock(spec=SandboxExecutor) + execute_code 显式
    return_value 真实 dict 形态——裸 AsyncMock 的 return_value 与子属性均
    AsyncMock 化，被测代码同步调用 result.get("output") 时返回协程无人
    await（RuntimeWarning 泄漏）且 str(协程) 垃圾文本混入工具输出注入面。
    """
    from unittest.mock import AsyncMock

    from src.application.services.retry_helpers import RetryPolicy
    from src.application.services.tool_execution_engine import ToolExecutionEngine
    from src.application.services.tool_execution_service import ToolExecutionService
    from src.domain.ports.sandbox_executor import SandboxExecutor

    sandbox = AsyncMock(spec=SandboxExecutor)
    sandbox.execute_code.return_value = {"status": "ok", "output": '{"valid": true}', "error": None}
    engine = ToolExecutionEngine(
        llm_client=fake_llm,
        sandbox=sandbox,
        retry_policy=RetryPolicy(max_attempts=1, initial_delay_sec=0.01),
    )
    return ToolExecutionService(registry=_make_registry(), engine=engine)


def _assemble_market_insight_chain(ctx: dict[str, Any], **fake_kwargs: Any) -> None:
    """市场洞察全链手工装配（6-1 _assemble_blm_chain 形态复用 + Fake LLM 八键族扩展）。

    装配面：真实 guard 链 + 真实 CEO 实例化 + 真实档案加载 + 真实工具链/注册表 +
    真实 hybrid 检索（R 门控）+ 真实快照存储（RedisSnapshotStore）+ Fake LLM
    （fail_schemas 注入扩展）+ BlmPlanningService + LangGraphEngine +
    RunBlmPlanningUseCase + GetBlmPlanningStatusUseCase（读侧 latest 消费）。
    """
    from src.application.services.blm_planning_service import BlmPlanningService
    from src.application.use_cases.agent_profile_loading import AgentProfileLoadResult, LoadAgentProfileUseCase
    from src.application.use_cases.get_blm_planning_status import GetBlmPlanningStatusUseCase
    from src.application.use_cases.run_blm_planning import RunBlmPlanningUseCase
    from src.domain.entities.agent import AgentRole
    from src.domain.ports.resolver import resolve
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore

    loop = ctx["_loop"]

    # 1) 真实 guard 链 + CEO 实例化 + 档案加载
    _make_real_guard_chain(ctx)
    agent_id = _instantiate_real_agent(ctx)
    profile_loader = resolve("agent_profile_loader")
    profile = _run_async(loop, profile_loader.load(role=AgentRole.CEO, agent_id=agent_id))
    skill_selector = resolve("skill_selector")
    tools_l1 = _run_async(loop, skill_selector.list_active_skills())
    profile_result = AgentProfileLoadResult(
        agent_id=agent_id,
        role=AgentRole.CEO,
        profile=profile,
        tools_l1=tools_l1,
        startup_context_tokens=0,
    )
    ctx["agent_id"] = agent_id
    ctx["profile_result"] = profile_result

    # 2) Fake LLM（八键族分派）+ 真实工具链
    fake_llm = _make_fake_llm(**fake_kwargs)
    ctx["fake_llm"] = fake_llm
    tool_execution_service = _build_tool_execution_service(fake_llm)

    # 3) BlmPlanningService（真实检索 + 真实快照存储 + 记录总线）
    hybrid = _make_real_hybrid_search(ctx)
    snapshot_store = RedisSnapshotStore(adapter=RedisAdapter(redis_client=ctx["_redis_client"]))
    recorder = _RecordingEventBus()
    ctx["recorder"] = recorder
    service = BlmPlanningService(
        llm_client=fake_llm,
        tool_execution_service=tool_execution_service,
        tool_registry_service=_make_registry(),
        isolation_guard=ctx["isolation_guard_chain"]["guard"],
        hybrid_search=hybrid,
        search_collection=ctx["retrieval_collection"],
        event_publisher=recorder,
        snapshot_repository=snapshot_store,
    )
    ctx["blm_service"] = service

    # 4) 图引擎 + 用例（执行 + 读侧状态查询）
    ctx["engine"] = LangGraphEngine(
        config=LangGraphConfig.from_env(),
        event_publisher=recorder,
        blm_planning_service=service,
    )
    profile_use_case = LoadAgentProfileUseCase(
        profile_loader=resolve("agent_profile_loader"),
        repository=ctx["isolation_guard_chain"]["agent_repository"],
        skill_selector=resolve("skill_selector"),
        event_publisher=InMemoryEventBus(),
    )
    ctx["use_case"] = RunBlmPlanningUseCase(
        agent_repository=ctx["isolation_guard_chain"]["agent_repository"],
        agent_profile_use_case=profile_use_case,
        agent_engine=ctx["engine"],
        blm_planning_service=service,
        isolation_guard=ctx["isolation_guard_chain"]["guard"],
        event_publisher=recorder,
    )
    ctx["profile_use_case"] = profile_use_case
    ctx["status_use_case"] = GetBlmPlanningStatusUseCase(snapshot_repository=snapshot_store)
    ctx["task"] = "制定新能源汽车行业五年战略规划"


def _run_planning(ctx: dict[str, Any], **execute_kwargs: Any) -> Any:
    """执行 BLM 规划（默认 task 经 ctx 注入；plan_id 缺省新铸）。"""
    kwargs = {"agent_id": ctx["agent_id"], "task": ctx["task"]}
    kwargs.update(execute_kwargs)
    return _run_async(ctx["_loop"], ctx["use_case"].execute(**kwargs))


def _load_step_snapshot(ctx: dict[str, Any], plan_id: str, step_value: str) -> Any:
    """读回 per-step Checkpoint 快照（session_id 后缀 :{step_value}——AC-2 键契约）。"""
    from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX

    session_id = f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}:{step_value}"
    return _run_async(ctx["_loop"], ctx["blm_service"].snapshot_repository.load(session_id))


def _load_latest_snapshot(ctx: dict[str, Any], plan_id: str) -> Any:
    """读回 latest 快照（6-1 既有键——零回归对照面）。"""
    from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX

    return _run_async(ctx["_loop"], ctx["blm_service"].snapshot_repository.load(f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}"))


def _collect_outbox_rows_by_plan(ctx: dict[str, Any], plan_ids: tuple[str, ...]) -> dict[str, list[tuple[str, str | None]]]:
    """按 plan_id 两级 JSONB 路径反查 outbox 行（AC-3/AC-6 主键口径——R1 修订钦定）。

    payload 列存 to_dict() 全量、plan_id 位于 payload 子字典内（两级路径
    payload->'payload'->>'plan_id'——与 6-1 集成先例 payload->'payload'->>'stage'
    同构；禁用 payload->>'aggregate_id'——BlmStageCompleted.aggregate_id 实测
    语义为 agent_id 非 plan_id，共享 CEO agent 时不可分离）。
    """
    import sqlalchemy as sa

    async def _query() -> dict[str, list[tuple[str, str | None]]]:
        engine = ctx["_pg_manager"].get_async_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT payload->'payload'->>'plan_id' AS plan_id, event_type, "
                        "payload->'payload'->>'stage' AS stage, event_id "
                        "FROM event_outbox "
                        "WHERE payload->'payload'->>'plan_id' = ANY(:plan_ids) "
                        "AND created_at >= NOW() - INTERVAL '5 minutes'"
                    ),
                    {"plan_ids": list(plan_ids)},
                )
            ).fetchall()
        await engine.dispose()
        grouped: dict[str, list[tuple[str, str | None]]] = {pid: [] for pid in plan_ids}
        for row in rows:
            pid, event_type, _stage, event_id = str(row[0]), str(row[1]), row[2], str(row[3])
            grouped.setdefault(pid, []).append((event_type, _stage))
            ctx["_outbox_event_ids"].append(event_id)
        return grouped

    return _run_async(ctx["_loop"], _query())


# ===================================================================
# Background Steps
# ===================================================================


@given("Redis 服务可用")
def redis_service_available(context: dict[str, Any]) -> None:
    """验证 Redis 服务可用（场景级客户端 ping——不可达 skip）。"""
    try:
        _run_async(context["_loop"], context["_redis_client"].ping())
    except Exception as exc:
        pytest.skip(f"Redis 不可用: {exc}")


@given("检索服务可用且语料已索引")
def retrieval_service_available(context: dict[str, Any]) -> None:
    """检索门控（embedding+Qdrant 双探测 + 租户隔离 collection 语料 upsert）。"""
    _ensure_qdrant_retrieval(context)


# ===================================================================
# AC-1: 六子步骤类型化结构化输出
# ===================================================================


@scenario(
    "test_acceptance_market_insight.feature",
    "完整流程六子步骤类型化产物全量断言",
)
def test_full_flow_typed_outputs_all_steps() -> None:
    """AC-1.1 完整流程（六步领域要素键族全量 + structured_output 挂载）。"""
    pass


@given("CEO Agent 已实例化且档案已加载")
def ceo_agent_instantiated_and_profile_loaded(context: dict[str, Any]) -> None:
    """真实 CEO Agent 实例化 + 档案加载 + 市场洞察全链装配。"""
    _assemble_market_insight_chain(context)


@when("启动 BLM 规划")
def start_blm_planning(context: dict[str, Any]) -> None:
    """执行 RunBlmPlanningUseCase（全链真实 + Fake LLM 八键族）。"""
    context["result"] = _run_planning(context)


def _structured_output_of(context: dict[str, Any], step_value: str) -> dict[str, Any]:
    """取指定子步骤的 structured_output（前置断言非 None——None 会以 TypeError 掩盖）。"""
    from src.domain.value_objects.blm_phases import InsightStepResult

    by_step = {s.step: s for s in context["result"].insight_steps}
    assert step_value in by_step, f"步骤 {step_value} 不在产物序列（实际 {sorted(by_step)}）"
    step_result: InsightStepResult = by_step[step_value]
    structured = step_result.structured_output
    assert structured is not None, f"步骤 {step_value} structured_output 为 None（未挂载或降级）"
    return structured


@then("看趋势产出 PESTEL 六维度评估与技术演进路线图与情景规划方案集")
def trend_step_typed_outputs(context: dict[str, Any]) -> None:
    """看趋势：PESTEL 六维度评估（OD-8 产物化）+ 技术演进路线图 + 情景规划方案集。"""
    structured = _structured_output_of(context, "trend")
    expected = EXPECTED_STEP_STRUCTURED_KEYS["trend"]
    actual_keys = set(structured)
    assert actual_keys == expected, f"trend 键族不一致: 缺 {expected - actual_keys} / 多 {actual_keys - expected}"
    for key in _PESTEL_KEYS:
        assert structured[key], f"trend.{key}（PESTEL 要素）为空"
    assert structured["technology_roadmap"], "trend.technology_roadmap（技术演进路线图）为空"
    assert structured["scenario_plans"], "trend.scenario_plans（情景规划方案集）为空"


@then("看市场与客户产出客户细分画像与需求优先级矩阵与价值主张地图")
def market_customer_step_typed_outputs(context: dict[str, Any]) -> None:
    """看市场与客户：客户细分画像 + 需求优先级矩阵 + 价值主张地图。"""
    structured = _structured_output_of(context, "market_customer")
    expected = EXPECTED_STEP_STRUCTURED_KEYS["market_customer"]
    assert set(structured) == expected, f"market_customer 键族不一致: {set(structured) ^ expected}"
    assert structured["customer_segments"], "market_customer.customer_segments（客户细分画像）为空"
    assert structured["demand_priority_matrix"], "market_customer.demand_priority_matrix（需求优先级矩阵）为空"
    assert structured["value_proposition_map"], "market_customer.value_proposition_map（价值主张地图）为空"


@then("看竞争产出波特五力五维评估与竞争对手能力雷达图评估与竞争策略建议")
def competition_step_typed_outputs(context: dict[str, Any]) -> None:
    """看竞争：波特五力五维评估（OD-8 产物化）+ 能力雷达图评估 + 竞争策略建议。"""
    structured = _structured_output_of(context, "competition")
    expected = EXPECTED_STEP_STRUCTURED_KEYS["competition"]
    assert set(structured) == expected, f"competition 键族不一致: {set(structured) ^ expected}"
    for key in _FIVE_FORCES_KEYS:
        assert structured[key], f"competition.{key}（波特五力要素）为空"
    assert structured["competitor_radar"], "competition.competitor_radar（能力雷达图评估）为空"
    assert structured["strategy_recommendations"], "competition.strategy_recommendations（竞争策略建议）为空"


@then("看自己产出内部能力清单与核心能力 VRIO 评估与资源约束分析")
def self_step_typed_outputs(context: dict[str, Any]) -> None:
    """看自己：内部能力清单 + 核心能力 VRIO 评估 + 资源约束分析。"""
    structured = _structured_output_of(context, "self")
    expected = EXPECTED_STEP_STRUCTURED_KEYS["self"]
    assert set(structured) == expected, f"self 键族不一致: {set(structured) ^ expected}"
    assert structured["internal_capabilities"], "self.internal_capabilities（内部能力清单）为空"
    assert structured["vrio_assessment"], "self.vrio_assessment（VRIO 评估）为空"
    assert structured["resource_constraints"], "self.resource_constraints（资源约束分析）为空"


@then("看机会产出机会清单与机会优先级排序与增长路径图")
def opportunity_step_typed_outputs(context: dict[str, Any]) -> None:
    """看机会：机会清单 + 机会优先级排序 + 增长路径图。"""
    structured = _structured_output_of(context, "opportunity")
    expected = EXPECTED_STEP_STRUCTURED_KEYS["opportunity"]
    assert set(structured) == expected, f"opportunity 键族不一致: {set(structured) ^ expected}"
    assert structured["opportunity_list"], "opportunity.opportunity_list（机会清单）为空"
    assert structured["priority_ranking"], "opportunity.priority_ranking（机会优先级排序）为空"
    assert structured["growth_path"], "opportunity.growth_path（增长路径图）为空"


@then("机会差距分析产出机会差距量化报告与能力-机会匹配矩阵与差距弥合策略")
def opportunity_gap_step_typed_outputs(context: dict[str, Any]) -> None:
    """机会差距分析：量化报告要点 + 能力-机会匹配矩阵 + 差距弥合策略。"""
    structured = _structured_output_of(context, "opportunity_gap")
    expected = EXPECTED_STEP_STRUCTURED_KEYS["opportunity_gap"]
    assert set(structured) == expected, f"opportunity_gap 键族不一致: {set(structured) ^ expected}"
    assert structured["gap_quantification"], "opportunity_gap.gap_quantification（机会差距量化报告）为空"
    assert structured["capability_match_matrix"], "opportunity_gap.capability_match_matrix（能力-机会匹配矩阵）为空"
    assert structured["closure_strategies"], "opportunity_gap.closure_strategies（差距弥合策略）为空"


@then("类型化产物以 structured_output 挂载于子步骤信封")
def structured_output_mounted_on_envelope(context: dict[str, Any]) -> None:
    """六步 structured_output 全部挂载（信封扩展字段——键值均为 JSON 标量/标量列表）。"""
    for step_result in context["result"].insight_steps:
        structured = getattr(step_result, "structured_output", None)
        assert structured is not None, f"步骤 {step_result.step} structured_output 未挂载"
        for key, value in structured.items():
            assert isinstance(key, str), f"{step_result.step}.{key} 键非 str"
            assert isinstance(value, (str, float, int, bool, list)), f"{step_result.step}.{key} 值非 JSON 标量/标量列表"
            if isinstance(value, list):
                assert all(isinstance(item, str) for item in value), f"{step_result.step}.{key} 列表元素非 str"
        # 公共双字段同源（R3-1：summary/findings 与信封字段同源）
        assert structured["summary"] == step_result.summary, f"{step_result.step} summary 与信封不同源"
        assert list(structured["findings"]) == list(step_result.findings), f"{step_result.step} findings 与信封不同源"


@scenario(
    "test_acceptance_market_insight.feature",
    "六子步骤类型化分派按执行序进行",
)
def test_step_order_and_schema_dispatch() -> None:
    """AC-1.2 执行序双锚 + 每步专属类型化 Schema 分派。"""
    pass


@then("六子步骤顺序与 or.md 钦定顺序一致")
def six_steps_match_ormd_order(context: dict[str, Any]) -> None:
    """锚 1：执行序独立构造自 or.md（不经被测服务生成期望——循环自证红线）。"""
    actual = tuple(step_result.step for step_result in context["result"].insight_steps)
    assert actual == EXPECTED_INSIGHT_ORDER, f"六子步骤顺序错乱: {actual}"


@then("每步调用使用该步专属类型化 Schema")
def each_step_uses_dedicated_schema(context: dict[str, Any]) -> None:
    """锚 2：六步 LLM 调用的 response_schema 按步专属分派（SSOT 映射零硬编码）。"""
    calls = context["fake_llm"]._blm_state["calls"]
    step_calls = [c for c in calls if c["schema"].__name__ in set(EXPECTED_STEP_SCHEMA_NAMES.values())]
    assert len(step_calls) == 6, f"六子步骤 Schema 调用应恰 6 次（实际 {len(step_calls)}——分派失败或重复）"
    for call, step_value in zip(step_calls, EXPECTED_INSIGHT_ORDER):
        expected_schema = EXPECTED_STEP_SCHEMA_NAMES[step_value]
        assert call["schema"].__name__ == expected_schema, (
            f"步骤 {step_value} 应分派 {expected_schema}（实际 {call['schema'].__name__}——硬编码回潮嫌疑）"
        )


@scenario(
    "test_acceptance_market_insight.feature",
    "综合洞察消费六步类型化产物",
)
def test_synthesis_consumes_six_step_outputs() -> None:
    """AC-1.3 综合消费（synthesis prompt 六步摘要逐一注入 + degraded_inputs 空）。"""
    pass


@then("综合提示词包含六子步骤产物摘要")
def synthesis_prompt_contains_six_step_summaries(context: dict[str, Any]) -> None:
    """注入侧锚：synthesis prompt 六步产物摘要逐一可判别（R1-7——summary 步骤值标记）。"""
    calls = context["fake_llm"]._blm_state["calls"]
    synthesis_calls = [c for c in calls if c["schema"].__name__ == "InsightSynthesisSchema"]
    assert synthesis_calls, "无 InsightSynthesisSchema 调用（综合步骤缺失）"
    prompt = synthesis_calls[-1]["prompt"]
    for step_value in EXPECTED_INSIGHT_ORDER:
        assert f"{_FAKE_STEP_SUMMARY_PREFIX}:{step_value}" in prompt, (
            f"synthesis prompt 缺步骤 {step_value} 产物摘要（六步逐一注入——漏传即红）"
        )


@then("正常路径下降级输入清单为空")
def degraded_inputs_empty_on_normal_path(context: dict[str, Any]) -> None:
    """正常路径 synthesis.degraded_inputs 为空元组（零回归——6-1 语义）。"""
    synthesis = context["result"].synthesis
    assert synthesis.degraded_inputs == (), f"正常路径 degraded_inputs 应空（实际 {synthesis.degraded_inputs}）"
    assert synthesis.conclusions, "综合结论非空"


# ===================================================================
# AC-2: 每子步骤触发 Checkpoint 快照骨架
# ===================================================================


@scenario(
    "test_acceptance_market_insight.feature",
    "每子步骤独立 Checkpoint 快照可读回",
)
def test_per_step_snapshots_readable() -> None:
    """AC-2.1 6+1 快照全量读回（per-step 七键契约 + latest 兼容）。"""
    pass


@then("六个子步骤快照与 latest 快照全部独立读回")
def six_step_snapshots_and_latest_readable(context: dict[str, Any]) -> None:
    """6 个 per-step 快照 + 1 个 latest 快照全部可独立读回（AC-2 主断言）。"""
    plan_id = context["result"].plan_id
    for step_value in EXPECTED_INSIGHT_ORDER:
        snapshot = _load_step_snapshot(context, plan_id, step_value)
        assert snapshot is not None, f"per-step 快照缺失: {plan_id}:{step_value}（写入或键形态断裂）"
        assert "step" in snapshot.state_data and "plan_id" in snapshot.state_data, (
            f"{step_value} 快照缺归属双锚（step/plan_id）"
        )
    latest = _load_latest_snapshot(context, plan_id)
    assert latest is not None, f"latest 快照缺失: {plan_id}（6-1 既有行为回归）"


@then("per-step 快照 stage 为该步 stage 值")
def per_step_snapshot_stage_id_correct(context: dict[str, Any]) -> None:
    """stage_id = market_insight_{step}（与 STAGE_VALUE_DOMAIN 同源）。"""
    plan_id = context["result"].plan_id
    for step_value in EXPECTED_INSIGHT_ORDER:
        snapshot = _load_step_snapshot(context, plan_id, step_value)
        assert snapshot is not None, f"{step_value} per-step 快照缺失"
        assert snapshot.stage_id == f"market_insight_{step_value}", (
            f"{step_value} 快照 stage_id={snapshot.stage_id} != market_insight_{step_value}"
        )


@then("per-step 快照携带步骤标识与规划标识与类型化产物")
def per_step_snapshot_carries_seven_keys(context: dict[str, Any]) -> None:
    """state_data 七键契约（step/plan_id/summary/structured_output/degraded/
    degrade_reason/completed_steps——structured_output 键恒在；completed_steps
    含该步且首步即含 performance_gap）。"""
    plan_id = context["result"].plan_id
    for step_value in EXPECTED_INSIGHT_ORDER:
        snapshot = _load_step_snapshot(context, plan_id, step_value)
        assert snapshot is not None
        state = snapshot.state_data
        expected_keys = {
            "step",
            "plan_id",
            "summary",
            "structured_output",
            "degraded",
            "degrade_reason",
            "completed_steps",
        }
        assert set(state) == expected_keys, f"{step_value} state_data 键族不一致: {set(state) ^ expected_keys}"
        assert state["step"] == step_value, f"{step_value} 快照 step 锚错配: {state['step']}"
        assert state["plan_id"] == plan_id, f"{step_value} 快照 plan_id 归属锚错配: {state['plan_id']}"
        assert state["structured_output"] is not None, f"{step_value} 正常步 structured_output 应非 None"
        # completed_steps 为含该步的步骤标识清单（timeline step 口径——R1-6 自然实现
        # [e.step for e in run_state.timeline]，六子步骤为裸 step 值；首步即含 performance_gap）
        assert state["completed_steps"][-1] == step_value, (
            f"{step_value} completed_steps 末位应为该步: {state['completed_steps']}"
        )
        assert "performance_gap" in state["completed_steps"], (
            f"{step_value} completed_steps 应含阶段 1（首步即含 performance_gap）"
        )


@scenario(
    "test_acceptance_market_insight.feature",
    "latest 快照行为与 6-1 一致",
)
def test_latest_snapshot_zero_regression() -> None:
    """AC-2.2 latest 零回归（读侧 GetBlmPlanningStatusUseCase 消费面）。"""
    pass


@when("启动 BLM 规划并查询规划状态")
def start_planning_and_query_status(context: dict[str, Any]) -> None:
    """执行规划 + 读侧状态查询（GetBlmPlanningStatusUseCase——latest 消费面）。"""
    context["result"] = _run_planning(context)
    context["final_status"] = _run_async(
        context["_loop"], context["status_use_case"].execute(plan_id=context["result"].plan_id)
    )


@then("状态查询读回 latest 快照终态")
def status_query_reads_latest_snapshot(context: dict[str, Any]) -> None:
    """读侧用例消费 latest 快照成功（per-step 新增键零污染读径）。"""
    status = context["final_status"]
    assert status is not None, "状态查询返回 None（latest 快照丢失或读径断裂）"
    assert status.completed_steps == 8, f"终态 completed_steps={status.completed_steps} != 8"


@then("状态为 8 步全部完成的终态")
def status_is_final_state(context: dict[str, Any]) -> None:
    """终态四锚：total_steps=8 + progress 100% + timeline 8 条 + 终步标识。"""
    status = context["final_status"]
    assert status.total_steps == 8, f"total_steps={status.total_steps} != 8"
    assert status.progress_percent == 100.0, f"progress_percent={status.progress_percent} != 100.0"
    assert len(status.timeline) == 8, f"timeline {len(status.timeline)} 条 != 8"
    assert status.current_step == "market_insight_synthesis", f"current_step={status.current_step} 非终步"


@scenario(
    "test_acceptance_market_insight.feature",
    "降级步同样触发 per-step 快照",
)
def test_degraded_step_snapshot_triggered() -> None:
    """AC-2.3 降级步快照标记（快照面——与 AC-4.1 流程面区分）。"""
    pass


@given("Fake LLM 对指定子步骤注入失败")
def fake_llm_fails_specified_step(context: dict[str, Any]) -> None:
    """schema 身份注入失败（trend 步——fail_schemas 恒败，首调与重试皆败）。"""
    from src.application.services.blm_planning_prompts import TrendInsightSchema

    _assemble_market_insight_chain(context, fail_schemas=frozenset({TrendInsightSchema}))


def _assemble_with_failure(context: dict[str, Any], *schema_names: str) -> None:
    """按 Schema 名构造失败注入链（fail_schemas=frozenset 身份恒败）。"""
    from src.application.services import blm_planning_prompts as prompts_module

    fail_classes = frozenset(getattr(prompts_module, name) for name in schema_names)
    _assemble_market_insight_chain(context, fail_schemas=fail_classes)


@then("降级步 per-step 快照含降级标记")
def degraded_step_snapshot_has_marker(context: dict[str, Any]) -> None:
    """降级步快照 state_data.degraded=True + degrade_reason 非空。"""
    plan_id = context["result"].plan_id
    snapshot = _load_step_snapshot(context, plan_id, "trend")
    assert snapshot is not None, "降级步 per-step 快照缺失（降级步同样触发——AC-2）"
    assert snapshot.state_data["degraded"] is True, f"trend 快照 degraded={snapshot.state_data['degraded']}"
    assert snapshot.state_data["degrade_reason"], "trend 快照 degrade_reason 为空"


@then("降级步 structured_output 为空")
def degraded_step_structured_output_null(context: dict[str, Any]) -> None:
    """structured_output 键恒存在；LLM 失败降级步值为 None（禁"降级时键缺失"形态——
    None ⟺ LLM 调用/校验失败，工具/检索面降级而 LLM 成功时非 None——R1-F1 收窄口径）。"""
    plan_id = context["result"].plan_id
    snapshot = _load_step_snapshot(context, plan_id, "trend")
    assert snapshot is not None
    assert "structured_output" in snapshot.state_data, "structured_output 键缺失（键恒在契约——6-3 读侧免双兼容）"
    assert snapshot.state_data["structured_output"] is None, "降级步 structured_output 应为 None"
    # 信封面同步：该步 degraded 且 structured_output None（AC-4 语义）
    by_step = {s.step: s for s in context["result"].insight_steps}
    assert by_step["trend"].degraded is True, "trend 信封应降级"
    assert by_step["trend"].structured_output is None, "trend 信封 structured_output 应 None"


# ===================================================================
# AC-3: CheckpointReached 事件语义分立
# ===================================================================


@scenario(
    "test_acceptance_market_insight.feature",
    "CheckpointReached 事件零发布",
)
def test_checkpoint_reached_not_published() -> None:
    """AC-3 负向断言（非空锚前置 ≥9 行 + 零 CheckpointReached + stage 8 值）。"""
    pass


@given("PostgreSQL 事件外发表可用")
def postgres_outbox_available(context: dict[str, Any]) -> None:
    """PG 门控双预检（连接 + event_outbox 表存在——5-4 R1-F07 先例）。"""
    import sqlalchemy as sa

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

    env = context["_env_config"]

    async def _probe() -> Any:
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
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT event_id FROM event_outbox LIMIT 1"))
        await engine.dispose()
        return manager

    try:
        context["_pg_manager"] = _run_async(context["_loop"], _probe())
    except Exception as exc:
        pytest.skip(f"PostgreSQL 不可达或 event_outbox 表未初始化: {exc}")


@when("启动 BLM 规划并经真实发布链路投递")
def planning_with_real_publish_chain(context: dict[str, Any]) -> None:
    """真实 event_publisher 装配执行（SINGLETON 跨 loop 防线——clear_singleton）。"""
    from src.application.services.blm_planning_service import BlmPlanningService
    from src.application.use_cases.run_blm_planning import RunBlmPlanningUseCase
    from src.domain.ports.resolver import get_resolver, resolve
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig

    _assemble_market_insight_chain(context)
    # 覆写：记录总线 → 真实 publisher（clear_singleton 防跨 loop 死连接——5-3 场景⑤先例）
    get_resolver().clear_singleton()
    real_publisher = resolve("event_publisher")
    service = BlmPlanningService(
        llm_client=context["fake_llm"],
        tool_execution_service=context["blm_service"].tool_execution_service,
        tool_registry_service=context["blm_service"].tool_registry_service,
        isolation_guard=context["isolation_guard_chain"]["guard"],
        hybrid_search=context["blm_service"].hybrid_search,
        search_collection=context["retrieval_collection"],
        event_publisher=real_publisher,
        snapshot_repository=context["blm_service"].snapshot_repository,
    )
    engine = LangGraphEngine(
        config=LangGraphConfig.from_env(),
        event_publisher=real_publisher,
        blm_planning_service=service,
    )
    context["use_case"] = RunBlmPlanningUseCase(
        agent_repository=context["isolation_guard_chain"]["agent_repository"],
        agent_profile_use_case=context["profile_use_case"],
        agent_engine=engine,
        blm_planning_service=service,
        isolation_guard=context["isolation_guard_chain"]["guard"],
        event_publisher=real_publisher,
    )
    context["result"] = _run_planning(context)


@then("事件外发表该规划行数不少于 9 行")
def outbox_plan_rows_at_least_nine(context: dict[str, Any]) -> None:
    """非空锚前置（R3-3）：先断言该 plan_id 行数 ≥9（PlanningStarted×1 +
    BlmStageCompleted×8）再负向 CheckpointReached——防 recorder 装配空真。"""
    rows = _collect_outbox_rows_by_plan(context, (context["result"].plan_id,))
    plan_rows = rows[context["result"].plan_id]
    assert len(plan_rows) >= 9, (
        f"plan_id={context['result'].plan_id} outbox 行数 {len(plan_rows)} < 9（真实发布装配断裂——"
        f"负向断言在该形态下空真无鉴别力）"
    )


@then("事件外发表零 CheckpointReached 事件")
def outbox_zero_checkpoint_reached(context: dict[str, Any]) -> None:
    """负向断言：CheckpointReached 零发布（6.3 语义分立——per-step 快照≠事件）。

    双通道过滤（R1-F2）：plan_id 通道对 CheckpointReached 恒 NULL（该事件类
    字段族无 plan_id——单通道时最可能的误发布形态 phase_identifier 绕过过滤
    器恒绿）；第二通道 LIKE 'market\\_insight%' 转义下划线（未转义 `_` 是单
    字符通配符，会误命中 Epic 1 既有 "market-insight" 连字符形态值）捕获
    BLM 命名空间前缀的 phase_identifier 误发布形态。
    """
    import sqlalchemy as sa

    async def _query() -> int:
        engine = context["_pg_manager"].get_async_engine()
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
                    {"plan_id": context["result"].plan_id},
                )
            ).fetchall()
        await engine.dispose()
        return int(rows[0][0])

    count = _run_async(context["_loop"], _query())
    assert count == 0, f"CheckpointReached 落行 {count} != 0（6.3 语义分立被破坏——6-2 零发布钦定）"


@then("阶段完成事件 stage 值域保持 8 值")
def stage_value_domain_remains_eight(context: dict[str, Any]) -> None:
    """BlmStageCompleted stage 8 值全集各恰一次（STAGE_VALUE_DOMAIN 零扩展）。"""
    from src.domain.value_objects.blm_phases import STAGE_VALUE_DOMAIN

    rows = _collect_outbox_rows_by_plan(context, (context["result"].plan_id,))
    stage_rows = [(etype, stage) for etype, stage in rows[context["result"].plan_id] if etype == "BlmStageCompleted"]
    actual_stages = {stage for _, stage in stage_rows}
    assert actual_stages == set(STAGE_VALUE_DOMAIN), f"stage 全集不一致: {actual_stages ^ set(STAGE_VALUE_DOMAIN)}"
    assert len(stage_rows) == 8, f"BlmStageCompleted {len(stage_rows)} 行 != 8"


# ===================================================================
# AC-4: 类型化校验失败降级与成功率
# ===================================================================


@scenario(
    "test_acceptance_market_insight.feature",
    "单点类型化校验失败仅该步降级",
)
def test_single_point_schema_failure_degrades_only_that_step() -> None:
    """AC-4.1 单点注入（schema 身份恒败 → 仅该步降级，其余五步 + synthesis 正常）。"""
    pass


@given("Fake LLM 对指定子步骤 Schema 注入校验失败")
def fake_llm_fails_specified_step_schema(context: dict[str, Any]) -> None:
    """单点 schema 注入（market_customer 步——fail_schemas 恒败）。"""
    from src.application.services.blm_planning_prompts import MarketCustomerInsightSchema

    _assemble_market_insight_chain(context, fail_schemas=frozenset({MarketCustomerInsightSchema}))


@then("流程完成且降级步骤清单恰含该步")
def degraded_steps_exactly_that_step(context: dict[str, Any]) -> None:
    """流程完成 + degraded_steps 恰含 market_customer 单步。"""
    result = context["result"]
    assert len(result.insight_steps) == 6, "流程完成（insight_steps 恒满 6）"
    assert tuple(result.degraded_steps) == ("market_customer",), (
        f"降级清单应恰含 market_customer（实际 {result.degraded_steps}）"
    )
    by_step = {s.step: s for s in result.insight_steps}
    degraded = by_step["market_customer"]
    assert degraded.degraded is True and degraded.degrade_reason, "降级步信封完整（原因非空）"


@then("其余五步与综合步骤类型化产物正常")
def other_five_steps_and_synthesis_normal(context: dict[str, Any]) -> None:
    """互不传染：其余五步 structured_output 正常 + synthesis 结论非空。"""
    by_step = {s.step: s for s in context["result"].insight_steps}
    for step_value in EXPECTED_INSIGHT_ORDER:
        if step_value == "market_customer":
            continue
        structured = getattr(by_step[step_value], "structured_output", None)
        assert structured is not None, f"{step_value} 被传染降级（structured_output=None——互不传染破坏）"
        assert set(structured) == EXPECTED_STEP_STRUCTURED_KEYS[step_value], (
            f"{step_value} 键族在被注入场景漂移: {set(structured) ^ EXPECTED_STEP_STRUCTURED_KEYS[step_value]}"
        )
    assert context["result"].synthesis.conclusions, "synthesis 正常（未被单点注入传染）"


@scenario(
    "test_acceptance_market_insight.feature",
    "相邻两步 Schema 双杀注入互不传染",
)
def test_adjacent_double_schema_failure_isolated() -> None:
    """AC-4.2 双杀注入（相邻两步各自降级互不传染——schema 身份恒败）。"""
    pass


@given("Fake LLM 对相邻两步 Schema 注入校验失败")
def fake_llm_fails_adjacent_step_schemas(context: dict[str, Any]) -> None:
    """双杀注入（trend + market_customer 相邻两步——AC-4 R1 钦定注入键）。"""
    from src.application.services.blm_planning_prompts import MarketCustomerInsightSchema, TrendInsightSchema

    _assemble_market_insight_chain(context, fail_schemas=frozenset({TrendInsightSchema, MarketCustomerInsightSchema}))


@then("恰两步降级且互不传染")
def exactly_two_steps_degraded(context: dict[str, Any]) -> None:
    """恰 trend + market_customer 两步降级，其余四步正常（互不传染锚）。"""
    result = context["result"]
    assert sorted(result.degraded_steps) == ["market_customer", "trend"], (
        f"双杀应恰两步降级（实际 {result.degraded_steps}——传染或漏杀）"
    )
    assert len(result.insight_steps) == 6, "流程完成（恒满 6）"
    by_step = {s.step: s for s in result.insight_steps}
    for step_value in ("competition", "self", "opportunity", "opportunity_gap"):
        assert by_step[step_value].degraded is False, f"{step_value} 被传染降级（双杀应互不传染）"
        assert by_step[step_value].structured_output is not None, f"{step_value} 产物被传染"


@then("降级步信封完整且 structured_output 为空")
def degraded_envelopes_complete_and_output_none(context: dict[str, Any]) -> None:
    """两 LLM 失败降级步完整信封（degraded+原因）+ structured_output=None（schema 注入路径）。"""
    by_step = {s.step: s for s in context["result"].insight_steps}
    for step_value in ("trend", "market_customer"):
        degraded = by_step[step_value]
        assert degraded.degraded is True, f"{step_value} 应降级"
        assert degraded.degrade_reason, f"{step_value} 降级原因非空（信封完整）"
        assert degraded.structured_output is None, (
            f"{step_value} structured_output 应 None（LLM 校验失败注入路径——R1-F1 收窄口径）"
        )


# ===================================================================
# AC-5: 市场洞察段性能 P95 小于 25 秒
# ===================================================================


@scenario(
    "test_acceptance_market_insight.feature",
    "市场洞察段延迟满足 P95 门限",
)
def test_market_insight_segment_latency_under_25s() -> None:
    """AC-5 段延迟（验收层单轮窗口断言——≥20 轮 P95 采样归集成 5.4b）。"""
    pass


@when("执行市场洞察段并按 Fake LLM 管线开销口径计量")
def execute_and_measure_segment(context: dict[str, Any]) -> None:
    """单轮执行 + timeline 两端窗口观测（OD-3 口径——真实 LLM 延迟出栈归 6.1-DF1）。

    观测点钦定（AC-5 R1 修订）：timeline 两端——市场洞察首步（trend）started_at
    → synthesis completed_at（阶段 2 全段；timeline 条目 step 键 = 裸步骤值口径）。"""
    context["result"] = _run_planning(context)
    timeline = {entry["step"]: entry for entry in context["blm_service"].project_timeline(context["result"].plan_id)}
    context["segment_window"] = (
        timeline["trend"]["started_at"],
        timeline["market_insight_synthesis"]["completed_at"],
    )


@then("市场洞察段延迟 P95 小于 25 秒")
def segment_latency_under_25s(context: dict[str, Any]) -> None:
    """单轮窗口差值 <25s（验收层单轮口径；20 轮 P95=次大值档归集成 5.4b 承载）。"""
    from datetime import datetime

    started_raw, completed_raw = context["segment_window"]
    started = datetime.fromisoformat(started_raw)
    completed = datetime.fromisoformat(completed_raw)
    elapsed = (completed - started).total_seconds()
    assert elapsed < 25.0, f"市场洞察段单轮 {elapsed:.2f}s >= 25s（OD-3 Fake LLM 管线开销口径）"


# ===================================================================
# AC-6: 并发执行 5 个市场洞察任务
# ===================================================================


@scenario(
    "test_acceptance_market_insight.feature",
    "并发 5 个规划任务互不串扰",
)
def test_concurrent_five_plans_isolated() -> None:
    """AC-6 并发正确性（5 不同 plan_id gather + per-plan 快照/outbox 分离）。"""
    pass


@given("5 个不同规划任务共享的 CEO Agent 已实例化且档案已加载")
def five_plan_ceo_agents_instantiated(context: dict[str, Any]) -> None:
    """真实发布链装配（并发场景 outbox 断言钦定真实 publisher——R3 补；单 Agent×5
    不同 plan_id 共享——OD-4 钦定，步骤文与实现对齐——R1-F12）。"""
    from src.application.services.blm_planning_service import BlmPlanningService
    from src.application.use_cases.run_blm_planning import RunBlmPlanningUseCase
    from src.domain.ports.resolver import get_resolver, resolve
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig

    _assemble_market_insight_chain(context)
    get_resolver().clear_singleton()
    real_publisher = resolve("event_publisher")
    service = BlmPlanningService(
        llm_client=context["fake_llm"],
        tool_execution_service=context["blm_service"].tool_execution_service,
        tool_registry_service=context["blm_service"].tool_registry_service,
        isolation_guard=context["isolation_guard_chain"]["guard"],
        hybrid_search=context["blm_service"].hybrid_search,
        search_collection=context["retrieval_collection"],
        event_publisher=real_publisher,
        snapshot_repository=context["blm_service"].snapshot_repository,
    )
    engine = LangGraphEngine(
        config=LangGraphConfig.from_env(),
        event_publisher=real_publisher,
        blm_planning_service=service,
    )
    context["use_case"] = RunBlmPlanningUseCase(
        agent_repository=context["isolation_guard_chain"]["agent_repository"],
        agent_profile_use_case=context["profile_use_case"],
        agent_engine=engine,
        blm_planning_service=service,
        isolation_guard=context["isolation_guard_chain"]["guard"],
        event_publisher=real_publisher,
    )


@when("并发启动 5 个 BLM 规划")
def launch_five_plans_concurrently(context: dict[str, Any]) -> None:
    """asyncio.gather 5 次 execute（5 不同 plan_id——OD-4；同 plan_id 竞态归 7-2）。"""
    loop = context["_loop"]
    use_case = context["use_case"]

    async def _run_five() -> list[Any]:
        tasks = [use_case.execute(agent_id=context["agent_id"], task=context["task"]) for _ in range(5)]
        return list(await asyncio.gather(*tasks))

    context["concurrent_results"] = _run_async(loop, _run_five())


@then("5 个任务全部完成")
def all_five_plans_completed(context: dict[str, Any]) -> None:
    """5 任务全部成功 DTO（各自六步产物满 6 + synthesis 非空）。"""
    results = context["concurrent_results"]
    assert len(results) == 5, f"并发任务数 {len(results)} != 5"
    plan_ids = {r.plan_id for r in results}
    assert len(plan_ids) == 5, f"plan_id 去重后 {len(plan_ids)} 个 != 5（OD-4 不同 plan_id 钦定）"
    for result in results:
        assert len(result.insight_steps) == 6, f"plan {result.plan_id} 六步产物不满 6"
        assert result.synthesis.conclusions, f"plan {result.plan_id} synthesis 空"
    context["concurrent_plan_ids"] = tuple(sorted(plan_ids))


@then("各任务 per-step 快照按规划标识可分离")
def per_step_snapshots_separable_by_plan(context: dict[str, Any]) -> None:
    """5×6 per-step 快照独立读回 + state_data.plan_id 归属锚逐任务断言（R1-4）。"""
    for plan_id in context["concurrent_plan_ids"]:
        for step_value in EXPECTED_INSIGHT_ORDER:
            snapshot = _load_step_snapshot(context, plan_id, step_value)
            assert snapshot is not None, f"plan {plan_id} 步 {step_value} per-step 快照缺失"
            assert snapshot.state_data["plan_id"] == plan_id, (
                f"plan {plan_id} 步 {step_value} 快照归属锚错配: {snapshot.state_data['plan_id']}（跨 plan 污染）"
            )


@then("事件外发表行按规划标识逐任务计数正确")
def outbox_rows_counted_by_plan(context: dict[str, Any]) -> None:
    """per-plan 9 行计数（PlanningStarted×1+BlmStageCompleted×8；AgentDecided 无
    plan_id 子键经两级路径天然排除——R3-3 钉死）。"""
    rows = _collect_outbox_rows_by_plan(context, context["concurrent_plan_ids"])
    for plan_id in context["concurrent_plan_ids"]:
        plan_rows = rows.get(plan_id, [])
        planning = sum(1 for etype, _ in plan_rows if etype == "PlanningStarted")
        stage_completed = sum(1 for etype, _ in plan_rows if etype == "BlmStageCompleted")
        assert planning == 1, f"plan {plan_id} PlanningStarted {planning} 行 != 1"
        assert stage_completed == 8, f"plan {plan_id} BlmStageCompleted {stage_completed} 行 != 8"


# ===================================================================
# AC-7: 跨阶段传导与综合消费
# ===================================================================


@scenario(
    "test_acceptance_market_insight.feature",
    "gap 四字段全量传导注入阶段 2",
)
def test_gap_four_fields_full_transmission() -> None:
    """AC-7.1 正常态四字段全量摘要注入阶段 2 首步 prompt。"""
    pass


@then("阶段 2 首步提示词含四字段全量摘要")
def phase2_first_prompt_contains_four_fields(context: dict[str, Any]) -> None:
    """阶段 2 首步（trend）prompt 含四字段标签族全量（AC-7——R2-3 成文裁定）。"""
    calls = context["fake_llm"]._blm_state["calls"]
    trend_calls = [c for c in calls if c["schema"].__name__ == "TrendInsightSchema"]
    assert trend_calls, "无 trend 调用（阶段 2 首步缺失）"
    prompt = trend_calls[0]["prompt"]
    for label in _GAP_SUMMARY_LABELS:
        assert label in prompt, f"trend prompt 缺 gap 摘要标签「{label}」（四字段全量传导——非单字段）"


@scenario(
    "test_acceptance_market_insight.feature",
    "gap 降级标注传导",
)
def test_gap_degradation_marker_transmission() -> None:
    """AC-7.2 gap 降级态 [降级] 标注传导（fail_schemas={GapAnalysisSchema} 独立 run）。"""
    pass


@given("Fake LLM 对业绩差距分析 Schema 注入校验失败")
def fake_llm_fails_gap_analysis_schema(context: dict[str, Any]) -> None:
    """gap 阶段 schema 注入（GapAnalysisSchema 恒败——阶段 1 降级构造）。"""
    from src.application.services.blm_planning_prompts import GapAnalysisSchema

    _assemble_market_insight_chain(context, fail_schemas=frozenset({GapAnalysisSchema}))


@then("阶段 2 首步提示词的 gap 摘要含降级标注")
def phase2_first_prompt_contains_degradation_marker(context: dict[str, Any]) -> None:
    """gap 降级时 trend prompt 摘要带 [降级] 标注（DEGRADATION_MARKER_PREFIX 单源）。"""
    calls = context["fake_llm"]._blm_state["calls"]
    trend_calls = [c for c in calls if c["schema"].__name__ == "TrendInsightSchema"]
    assert trend_calls, "无 trend 调用"
    prompt = trend_calls[0]["prompt"]
    assert _DEGRADATION_MARKER in prompt, "trend prompt 缺 [降级] 标注（gap 降级标注传导断裂）"
    # performance_gap 子串断言已删（正常/降级两路径同命中、无判别力——R1-F13；
    # 判别锚由上行 _DEGRADATION_MARKER 承担，字面在单测层另有钉）


# ===================================================================
# 收尾: 开发完成清单
# ===================================================================


@scenario(
    "test_acceptance_market_insight.feature",
    "开发完成清单收尾",
)
def test_development_completion_checklist() -> None:
    """收尾：src 交付清单 + 四测试目录完成清单逐项确认。"""
    pass


@given("扫描源码交付清单与测试目录")
def scan_delivery_checklist() -> None:
    """静态扫描（零服务依赖——src/交付件与 tests/ 四目录文件存在性）。"""
    pass


@then("市场洞察类型化交付件全部就位")
def src_delivery_files_present() -> None:
    """src 交付清单（本 Story 修改/新增文件全部在位）。"""
    expected = [
        "src/domain/value_objects/blm_phases.py",
        "src/application/ports/blm_planning.py",
        "src/application/services/blm_planning_prompts.py",
        "src/application/services/blm_planning_service.py",
    ]
    missing = [str(p) for p in expected if not (REPO_ROOT / p).is_file()]
    assert not missing, f"src 交付件缺失: {missing}"


@then("四测试目录完成清单全部就位")
def delivery_files_in_four_test_dirs_present() -> None:
    """四测试目录交付清单（unit/integration/acceptance/contracts 全部在位）。"""
    expected = [
        "tests/unit/domain/test_blm_domain_models.py",
        "tests/unit/application/test_market_insight_schemas.py",
        "tests/unit/application/test_blm_planning_service.py",
        "tests/unit/architecture/test_market_insight.py",
        "tests/integration/test_integration_market_insight.py",
        "tests/contracts/test_port_contract_blm_planning.py",
        "tests/contracts/test_event_channel_mapping_blm_planning.py",
        "tests/acceptance/test_acceptance_market_insight.feature",
        "tests/acceptance/test_acceptance_market_insight.py",
    ]
    missing = [str(p) for p in expected if not (REPO_ROOT / p).is_file()]
    assert not missing, f"测试交付件缺失: {missing}"
