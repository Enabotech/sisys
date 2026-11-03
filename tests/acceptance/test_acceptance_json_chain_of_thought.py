"""Story 6-4 — JSON 思维链输出（BLM 面组装 + EVIDENCE_PACKAGE 归档 + 追溯）验收测试。

模板基准: test_acceptance_postgresql_relational_layer.feature/.py（R6——
中文 Gherkin + AC 横幅分组）；装配形态对齐 6-3 test_acceptance_checkpoint_
snapshot.py（四真实服务 + Fake LLM/Fake Embedding/Sandbox 执行器三替身
豁免——CR1-F5 声明面如实化 + teardown 六步链 + 13 场景全绑定）+ 6-2
test_acceptance_market_insight.py（BLM 全链装配 + Fake LLM 八 Schema 族
分派 + fail_schemas 身份注入）；R6 旧欠账（部分绑定/无 pytestmark/无三件
套）不承袭。

13 场景三属性分档表（Subtask 0.5 钉死——层级/LLM 依赖/服务门控）：

| #   | 场景                     | 层级               | LLM            | 服务门控              |
|-----|--------------------------|--------------------|----------------|-----------------------|
| S1  | 全链 8 条+成功率         | 用例级（全链装配） | Fake           | R+PG+Qdrant+MinIO     |
| S2  | 组装映射判别力           | 用例级             | Fake           | 同上                  |
| S3  | 降级步信封               | 用例级             | Fake Schema 注 | 同上                  |
| S4  | Result 携带+投影真实化   | 用例级（图引擎）   | Fake           | 同上                  |
| S5  | 归档三层落位             | 用例级+真实存储链  | Fake           | 同上                  |
| S6  | 追溯正向+blob 解引用     | 用例级（查询面）   | Fake           | 同上                  |
| S7  | 追溯负向两形态           | 用例级             | 无             | PG                    |
| S8  | 快照/事件契约零回归      | 用例级（读侧）     | Fake           | 同 S1                 |
| S9  | 事件零新增+落行          | 用例级（真实发布） | Fake           | 同 S1                 |
| S10 | to_display 展示形态      | 用例级             | Fake           | 同 S1                 |
| S11 | P95 组装窗口             | 纯函数直调         | 无             | 无独立门控（零 I/O；Background Redis 随组——CR1-F9） |
| S12 | 并发 10 归档             | 服务级（gather）   | 无             | PG+Qdrant+MinIO       |
| S13 | 收尾完成清单             | 静态完成清单       | 无             | 无                    |

门控档位：Redis ping / PG 双预检（event_outbox+strategic_archives 表）/
Qdrant get_collections + strategic_archive collection 确保（1024/COSINE）/
MinIO bucket 存在性 + object-lock 自愈 / 检索 R 档（真实 embedding+Qdrant
双探测 + 租户隔离 collection 建制语料 upsert——3-1a/6-2 先例）；任一不可达
逐场景 pytest.skip 动态跳过（禁 @pytest.mark.skip 写死）。

口径声明（OD-10 性能口径差）：
- S11 组装窗口 P95<50ms = 步骤素材就绪 → ChainOfThought VO 构造完成窗口
  （纯内存组装——OD-2 确定性组装零 LLM 调用使指标物理可达）；归档 I/O
  （L2/L3/L4）与 LLM 延迟显式出栈独立计量（采样直调模块级纯函数
  compose_step_chain——R1-F13 钦定，采样素材型=六子步骤型）。
- S1 成功率口径（OD-5 重读）：正常路径 8 次归档 8 次可查回 + 失败零静默
  （archived 台账可见）——非「失败即中断」字面。

新模块延迟 import 纪律：本 Story 交付的模块（chain_of_thought_archive
端口/服务、get_blm_chain_trace 用例、blm_planning_service 尾参注入、
compose_step_chain 纯函数）一律在步骤/装配函数体内延迟 import——模块顶部
import 会使 pytest 收集期整文件 collection error，无法逐 Task 转绿（Task 0
预期红因 = 运行期 ImportError/AttributeError）。

Run with:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/acceptance/test_acceptance_json_chain_of_thought.py -v

测试隔离:
    - 场景级独立 Redis 客户端 + 同循环关闭（跨循环 "Event loop is closed" 存档教训）
    - Agent 状态键逐 agent_id 精确删除（agent/isolation 双 namespace；禁 flush）
    - 检索 collection 场景级唯一命名 + teardown 精确删除
    - per-step/latest 快照键按 plan_id 天然隔离（TTL 86400 吸收——6-1 先例）
    - 归档三面清理（PG 档案行按 archive_id / Qdrant 点按 payload.archive_id /
      MinIO WORM 对象 bypass_governance）+ outbox 行双通道 DELETE
      （event_id 面 + plan_id 双 JSONB 路径兜底——6-3 teardown 第②步先例）
    - BDD 步骤禁 @pytest.mark.asyncio（context 数据丢失红线），统一 _run_async
    - Fake LLM/Fake Embedding 端口替身是外部 SaaS 豁免面；Sandbox 执行器
      AsyncMock(spec=...) 是 Docker 沙箱外部依赖替身（6-2 集成先例——三替身
      豁免面 CR1-F5 如实登记；存储端口保持真实）
    - xdist_group 复用 6-1 组名 blm-planning-perf（跨 Story 采样场景全局同
      worker 串行——R2-2 修订钦定）
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Generator
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
    pytest.mark.database,
    pytest.mark.redis,
    pytest.mark.qdrant,
    pytest.mark.minio,
    pytest.mark.xdist_group("blm-planning-perf"),
]

#: 8 步 stage 锚执行序期望（独立构造自 or.md 钦定序 + STAGE 前缀拼装公式——
#: 禁经被测服务生成期望）
EXPECTED_STAGE_ORDER: tuple[str, ...] = (
    "performance_gap",
    "market_insight_trend",
    "market_insight_market_customer",
    "market_insight_competition",
    "market_insight_self",
    "market_insight_opportunity",
    "market_insight_opportunity_gap",
    "market_insight_synthesis",
)

#: 每步期望工具轨迹（独立构造自语义配置表白名单首候选 + TOOL_CATALOG
#: name 同值 + slug 零定义回落——R3-F6 实值恒中文显示名；synthesis 无工具
#: 无检索恒空元组——R1-F2 口径）
EXPECTED_TOOL_TRACE: dict[str, tuple[str, ...]] = {
    "performance_gap": ("SWOT-TOWS",),
    "market_insight_trend": ("PESTEL 分析",),
    "market_insight_market_customer": ("$APPEALS",),
    "market_insight_competition": ("波特五力",),
    "market_insight_self": ("价值链分析",),
    "market_insight_opportunity": ("SWOT-TOWS",),
    "market_insight_opportunity_gap": ("GE-麦肯锡矩阵",),
    "market_insight_synthesis": (),
}

#: Fake gap 产物期望值（独立构造——与 Fake LLM 分派值各自字面量，互证非自证）
_EXPECTED_GAP_PAYLOAD: dict[str, Any] = {
    "financial_gap": "财务差距量化：营收达成率 82%，毛利率 -3.2pct",
    "operational_gap": "运营差距分析：交付周期延长与产能利用率不足",
    "root_causes": ["价格竞争侵蚀毛利", "供应链成本上升", "组织响应迟缓"],
    "portfolio_health": "业务组合健康度：核心业务稳健，新兴业务双低",
    "degraded": False,
    "degrade_reason": "",
}

#: Fake synthesis 产物期望值（全成功链路——degraded_inputs 空）
_EXPECTED_SYNTHESIS_PAYLOAD: dict[str, Any] = {
    "conclusions": ["综合结论一：优先补强内部能力", "综合结论二：把握海外机会窗口"],
    "degraded_inputs": [],
}

#: Fake 六子步骤产物期望值（独立构造——summary 前缀与 findings 双公共字段
#: + 各步专属字段，值与 Fake LLM 分派值互证）
_EXPECTED_STEP_PAYLOADS: dict[str, dict[str, Any]] = {
    "market_insight_trend": {
        "summary": "市场洞察产物:trend（结构化要点）",
        "findings": ["发现一：政策与技术双趋势信号明确", "发现二：情景分化风险上升"],
        "pestel_political": "政策维度：补贴退坡与准入收紧",
        "pestel_economic": "经济维度：利率上行压制可选消费",
        "pestel_social": "社会维度：绿色出行消费习惯迁移",
        "pestel_technological": "技术维度：固态电池与智能驾驶演进",
        "pestel_environmental": "环境维度：碳排法规趋严",
        "pestel_legal": "法律维度：数据合规与知识产权要求升级",
        "technology_roadmap": ["短期：平台化架构降本", "中期：固态电池量产", "长期：智驾生态成型"],
        "scenario_plans": ["基准情景：渗透率稳步提升", "乐观情景：政策加码提速", "悲观情景：价格战侵蚀利润"],
    },
    "market_insight_market_customer": {
        "summary": "市场洞察产物:market_customer（结构化要点）",
        "findings": ["发现一：细分需求分化明显", "发现二：补能效率是首要痛点"],
        "customer_segments": ["价格敏感型家庭用户", "科技尝鲜型年轻用户", "运营降本型企业客户"],
        "demand_priority_matrix": ["续航与补能效率（最高优先）", "智能座舱体验（高优先）", "购车总价（中优先）"],
        "value_proposition_map": ["痛点：补能焦虑→收益：超充网络覆盖", "痛点：保值率低→收益：电池质保计划"],
    },
    "market_insight_competition": {
        "summary": "市场洞察产物:competition（结构化要点）",
        "findings": ["发现一：竞争强度处历史高位", "发现二：头部厂商成本优势扩大"],
        "five_forces_supplier_power": "供应商议价能力：中高（电池厂商集中度高）",
        "five_forces_buyer_power": "购买者议价能力：中（选择增多但转换成本存在）",
        "five_forces_new_entrants": "新进入者威胁：高（跨界造车与代工模式降低门槛）",
        "five_forces_substitutes": "替代品威胁：中（公共交通与共享出行部分替代）",
        "five_forces_rivalry": "现有竞争者强度：极高（价格战与渠道战并发）",
        "competitor_radar": ["研发能力：头部厂商 9/10", "成本控制：二线厂商 6/10", "渠道下沉：新势力 5/10"],
        "strategy_recommendations": ["以差异化配置避开正面价格战", "锁定上游电池产能对冲供应风险"],
    },
    "market_insight_self": {
        "summary": "市场洞察产物:self（结构化要点）",
        "findings": ["发现一：三电自研是核心能力", "发现二：渠道与品牌存在短板"],
        "internal_capabilities": ["三电自研平台", "软件 OTA 体系", "海外渠道初步布局"],
        "vrio_assessment": [
            "三电平台：价值+稀有+难模仿+组织适配（核心能力）",
            "软件体系：价值+稀有（潜力能力）",
            "海外渠道：价值+非稀有（待强化）",
        ],
        "resource_constraints": ["研发预算受限", "电池产能依赖外部", "组织数字化人才缺口"],
    },
    "market_insight_opportunity": {
        "summary": "市场洞察产物:opportunity（结构化要点）",
        "findings": ["发现一：海外市场窗口期明确", "发现二：高端智能化溢价空间大"],
        "opportunity_list": ["海外新兴市场渗透", "高端智能化细分", "电池银行服务模式"],
        "priority_ranking": ["海外新兴市场（评分 9）", "高端智能化（评分 8）", "电池银行（评分 6）"],
        "growth_path": ["现产品×新市场：出海优先", "新产品×现市场：高端智能款", "新产品×新市场：能源服务"],
    },
    "market_insight_opportunity_gap": {
        "summary": "市场洞察产物:opportunity_gap（结构化要点）",
        "findings": ["发现一：渠道差距是首要瓶颈", "发现二：品牌溢价能力不足"],
        "gap_quantification": ["海外渠道覆盖差距 40%", "高端品牌溢价能力差距 25%"],
        "capability_match_matrix": ["海外机会×渠道能力：弱匹配", "高端机会×品牌能力：中匹配"],
        "closure_strategies": ["合资并购获取渠道", "联名合作提升品牌溢价"],
    },
}

#: 语义配置期望（独立构造——display_name/role_prefix 字面量，组装公式判别锚；
#: 语义配置是 6-1 既有资产非 6-4 被测面，此处字面量防 import 自证）
_EXPECTED_SEMANTICS: dict[str, tuple[str, str]] = {
    "performance_gap": ("业绩差距分析", "以 CFO 财务差距量化与 COO 运营差距分析的双重视角"),
    "market_insight_trend": ("看趋势", "以 CEO 宏观趋势判断与 CTO 技术趋势分析的双重视角"),
    "market_insight_market_customer": ("看市场与客户", "以 CMO 客户需求洞察与 COO 市场细分分析的双重视角"),
    "market_insight_competition": ("看竞争", "以 CEO 竞争格局判断与 CMO 竞争对手分析的双重视角"),
    "market_insight_self": ("看自己", "以 COO 内部能力评估与 CFO 财务健康度分析的双重视角"),
    "market_insight_opportunity": ("看机会", "以 CEO 机会识别与 CMO 市场机会验证的双重视角"),
    "market_insight_opportunity_gap": ("机会差距分析", "以 CEO 机会差距量化与 CFO 机会价值评估的双重视角"),
}

#: synthesis 语义常量期望（无 StepSemanticConfig——组装服务模块级常量钦定）
_EXPECTED_SYNTHESIS_SEMANTICS: tuple[str, str] = ("市场洞察综合", "CMO")

#: latest 快照 state_data 七键契约（6-2 冻结——零新键回归锚，OD-8）
EXPECTED_SNAPSHOT_SEVEN_KEYS: frozenset[str] = frozenset(
    {
        "plan_id",
        "phase",
        "current_step",
        "completed_steps",
        "total_steps",
        "degraded_steps",
        "timeline",
    }
)

#: AgentDecided 投影五键白名单（DC-11——结构零变化回归锚）
EXPECTED_PROJECTION_KEYS: frozenset[str] = frozenset(
    {"workflow_status", "task_summary", "chain_summary", "evidence_ref", "retry_count"}
)

# 真实检索语料（背景建制——与任务主题相关，保证 dense 命中；沿 6-1/6-2 语料）
_CORPUS_TEXTS: tuple[str, ...] = (
    "新能源汽车行业进入战略分析报告：市场增速放缓但渗透率持续提升",
    "财务业绩差距分析：营收目标达成率与毛利率下滑根因",
    "竞争对手动态：头部厂商价格战与渠道下沉策略",
    "宏观趋势：政策补贴退坡与技术路线演进（固态电池）",
    "内部能力评估：研发投入占比与组织能力短板",
    "市场机会：海外新兴市场增长路径与机会差距量化",
)

# Fake LLM 各步骤产出摘要标记（步骤值可判别）
_FAKE_STEP_SUMMARY_PREFIX = "市场洞察产物"

#: BLM 规划任务文本（全链场景共享——task 截断断言锚）
_BLM_TASK = "制定新能源汽车行业五年战略规划"


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
    """BDD 步骤间共享状态容器（场景级独立客户端 + 同循环 teardown 六步链）。

    teardown 顺序（断言失败也执行——K8 纪律）：① 端口覆写还原；② outbox
    事件行按 event_id + plan_id 双 JSONB 通道精确 DELETE（ArchiveCreated 8
    行/run × 全链场景——R3-F3）；③ Redis 快照/Agent 状态键精确删除；④⑤
    Qdrant 点 / MinIO WORM 对象 / PG 归档行精确清理；⑥ 同循环关闭全部客户端。
    """
    ctx: dict[str, Any] = {
        "_loop": event_loop,
        "_env": acceptance_env_config,
        "_redis_client": None,
        "_restorers": [],
        "_agent_ids": [],
        "_created_collections": [],
        "_outbox_event_ids": [],
        "_outbox_plan_ids": [],
        "_snapshot_session_ids": [],
        "_archive_plan_ids": [],
        "_archive_row_ids": [],
        "_minio_blob_refs": [],
        "_pg_manager": None,
        "_pg_session": None,
        "_pg_session_token": None,
    }
    yield ctx
    _teardown_chain(ctx)


def _run_async(event_loop: asyncio.AbstractEventLoop, awaitable: Awaitable[_T]) -> _T:
    """在模块级共享事件循环上同步调度可等待对象（BDD 步骤禁 @pytest.mark.asyncio）。

    泛型签名保留精确返回类型（裸 Any 会向全部调用点扩散 no-any-return）；
    Awaitable 口径覆盖 session.begin()（AsyncSessionTransaction 实现 __await__
    非 Coroutine 子类——严格 Coroutine 约束会误拒事务开启面）。
    """
    return event_loop.run_until_complete(awaitable)


def _new_plan_id() -> str:
    """新铸 plan_id（场景间互异——资源唯一性隔离行）。"""
    return str(uuid.uuid4())


# ===================================================================
# 共享基建：teardown 六步链（6-3 形态移植 + outbox 双通道 R3-F3）
# ===================================================================


def _teardown_chain(ctx: dict[str, Any]) -> None:
    """teardown 六步链（context fixture yield 后执行——断言失败也运行）。

    各步独立 try/except（前步失败不阻断后步——残局防线，R8-F2）；全部
    _run_async 同循环（跨循环 "Event loop is closed" 存档教训）。
    """
    # ① 端口覆写还原（真实发布链路场景注册的替身）+ PG 会话提交还原
    for restore in ctx["_restorers"]:
        try:
            restore()
        except Exception:
            pass
    _run_async(ctx["_loop"], _finalize_pg_session(ctx))
    # ② outbox 事件行精确 DELETE（event_id 面 + plan_id 双 JSONB 通道兜底）
    try:
        _cleanup_outbox_rows(ctx)
    except Exception:
        pass
    # ③ Redis 键族精确删除（快照会话键 + Agent 状态键）
    _run_async(ctx["_loop"], _cleanup_redis_keys(ctx))
    # ④⑤ Qdrant 点 / MinIO 对象 / PG 归档行精确清理
    _run_async(ctx["_loop"], _cleanup_archive_residues(ctx))
    # ⑥ 检索 collection 精确删除 + 同循环关闭 Redis 客户端
    for name in list(ctx["_created_collections"]):
        try:
            _run_async(ctx["_loop"], _delete_collection(ctx, name))
        except Exception:
            pass
    if ctx["_redis_client"] is not None:
        try:
            _run_async(ctx["_loop"], ctx["_redis_client"].close())
        except Exception:
            pass


async def _finalize_pg_session(ctx: dict[str, Any]) -> None:
    """PG 会话收尾（commit 残留事务 → 还原 ContextVar → 关闭会话）。"""
    session = ctx.get("_pg_session")
    if session is None:
        return
    from src.infrastructure.storage.postgresql.session_context import reset_session

    try:
        await session.commit()
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass
    if ctx.get("_pg_session_token") is not None:
        try:
            reset_session(ctx["_pg_session_token"])
        except Exception:
            pass
    try:
        await session.close()
    except Exception:
        pass


def _commit_pg_session(context: dict[str, Any]) -> None:
    """提交当前 PG 事务（行断言前置——commit 后独立连接可见；session 自动新事务）。"""
    session = context.get("_pg_session")
    if session is not None:
        _run_async(context["_loop"], session.commit())


async def _cleanup_redis_keys(ctx: dict[str, Any]) -> None:
    """Redis 键族精确删除（快照会话键 + Agent 状态双 namespace——禁 flush）。"""
    client = ctx["_redis_client"]
    if client is None:
        return
    keys: list[str] = []
    for session_id in ctx["_snapshot_session_ids"]:
        keys.append(build_key("snapshot", session_id))
    for agent_id in ctx["_agent_ids"]:
        for namespace in ("agent", "isolation"):
            keys.append(build_key(namespace, str(agent_id)))
    for key in keys:
        try:
            await client.delete(key)
        except Exception:
            pass


def _cleanup_outbox_rows(ctx: dict[str, Any]) -> None:
    """outbox 事件行精确 DELETE（event_id 面 + plan_id 双 JSONB 通道兜底——R3-F3）。

    ArchiveCreated 的 plan_id 位于 payload->'payload' 内层（to_dict 信封）；
    payload->'metadata' 通道为 CheckpointReached 专属——双通道 OR 兜底覆盖
    两类事件行（6-3 teardown 第②步先例形态）。
    """
    import sqlalchemy as sa

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

    env = ctx["_env"]

    async def _delete() -> None:
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
            async with engine.begin() as conn:
                if ctx["_outbox_event_ids"]:
                    await conn.execute(
                        sa.text("DELETE FROM event_outbox WHERE event_id = ANY(:ids)"),
                        {"ids": [str(e) for e in ctx["_outbox_event_ids"]]},
                    )
                if ctx["_outbox_plan_ids"]:
                    await conn.execute(
                        sa.text(
                            "DELETE FROM event_outbox WHERE payload->'metadata'->>'plan_id' = ANY(:ids) "
                            "OR payload->'payload'->>'plan_id' = ANY(:ids)"
                        ),
                        {"ids": list(ctx["_outbox_plan_ids"])},
                    )
            await engine.dispose()
        except Exception:
            pass  # 清理尽力而为（PG 不可达时跳过）

    _run_async(ctx["_loop"], _delete())


async def _cleanup_archive_residues(ctx: dict[str, Any]) -> None:
    """归档残留精确清理（Qdrant 点按 payload.archive_id / MinIO 对象 bypass / PG 归档行）。"""
    env = ctx["_env"]
    # 按收集面 plan_id 补集归档行（archive_id/blob_ref 双收集——失败不阻断）
    if ctx["_archive_plan_ids"] and ctx["_pg_manager"] is not None:
        try:
            import sqlalchemy as sa

            engine = ctx["_pg_manager"].get_async_engine()
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        sa.text("SELECT archive_id, blob_ref FROM strategic_archives WHERE plan_id = ANY(:ids)"),
                        {"ids": list(ctx["_archive_plan_ids"])},
                    )
                ).fetchall()
            await engine.dispose()
            for row in rows:
                ctx["_archive_row_ids"].append(str(row[0]))
                if row[1]:
                    ctx["_minio_blob_refs"].append(row[1])
        except Exception:
            pass
    # ④ Qdrant 点按 payload.archive_id filter 精确删除（点 ID 为 MD5 哈希 int）
    if ctx["_archive_row_ids"]:
        try:
            from qdrant_client import AsyncQdrantClient, models

            client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
            try:
                await client.delete(
                    collection_name="strategic_archive",
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="archive_id",
                                    match=models.MatchAny(any=list(ctx["_archive_row_ids"])),
                                )
                            ]
                        )
                    ),
                )
            finally:
                await client.close()
        except Exception:
            pass
    # ⑤ MinIO 对象批量删除（object-lock bucket GOVERNANCE retention——bypass 形态）
    if ctx["_minio_blob_refs"]:
        try:
            from minio import Minio
            from minio.deleteobjects import DeleteObject

            minio_client = Minio(
                endpoint=env.minio.endpoint,
                access_key=env.minio.access_key,
                secret_key=env.minio.secret_key,
                secure=env.minio.secure,
            )
            bucket_name = _resolve_archive_bucket_name(ctx)
            _ = list(
                minio_client.remove_objects(
                    bucket_name,
                    [DeleteObject(blob_ref) for blob_ref in ctx["_minio_blob_refs"]],
                    bypass_governance_mode=True,
                )
            )
        except Exception:
            pass
    # ⑤ PG strategic_archives 行按 archive_id 精确 DELETE
    if ctx["_archive_row_ids"]:
        try:
            import sqlalchemy as sa

            manager = ctx["_pg_manager"]
            if manager is not None:
                engine = manager.get_async_engine()
                async with engine.begin() as conn:
                    await conn.execute(
                        sa.text("DELETE FROM strategic_archives WHERE archive_id = ANY(:ids)"),
                        {"ids": list(ctx["_archive_row_ids"])},
                    )
                await engine.dispose()
        except Exception:
            pass


async def _delete_collection(ctx: dict[str, Any], name: str) -> None:
    """删除场景级检索 collection（租户隔离建制面清理）。"""
    from qdrant_client import AsyncQdrantClient

    from src.infrastructure.config.qdrant import QdrantConfig

    env = ctx["_env"]
    config = QdrantConfig(
        host=env.qdrant.host, port=env.qdrant.port, grpc_port=env.qdrant.grpc_port, api_key=env.qdrant.api_key
    )
    client = AsyncQdrantClient(url=f"http://{config.host}:{config.port}", timeout=10)
    try:
        await client.delete_collection(name)
    finally:
        await client.close()


def _resolve_archive_bucket_name(ctx: dict[str, Any]) -> str:
    """解析 archive-evidence 物理 bucket 名（{prefix}-{type}-{tenant} 复合形态）。"""
    from src.domain.ports.resolver import resolve

    l4 = resolve("l4_object")
    return str(l4._repository._resolve_bucket_name("archive-evidence"))


# ===================================================================
# 共享基建：Fake 工厂（外部依赖替身豁免——Fake LLM / Fake Embedding /
# Sandbox 执行器三替身，CR1-F5 声明面如实化）
# ===================================================================


def _make_fake_llm(
    *,
    fail_call_indices: frozenset[int] = frozenset(),
    fail_schemas: frozenset[type] = frozenset(),
) -> Any:
    """BLM 面 Fake LLM 端口替身（外部 SaaS 豁免面——分派键 = response_schema 身份）。

    6-2 _make_fake_llm 形态移植（:365-506——hold_at_call/delay_sec 场景用参数
    裁剪）：分派键 = GapAnalysisSchema / 六类型化 Schema / InsightSynthesisSchema
    八者 __name__ 字符串身份；6-4 组装零新增 LLM 调用故 Fake 面不扩（OD-2）。
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
        if response_schema in fail_schemas:
            raise __import__("src.domain.exceptions.llm_exceptions", fromlist=["LLMAPIError"]).LLMAPIError(
                f"Fake schema 身份注入失败（{response_schema.__name__} 恒败——首调与重试皆败）"
            )
        if call_index in fail_call_indices:
            raise __import__("src.domain.exceptions.llm_exceptions", fromlist=["LLMAPIError"]).LLMAPIError(
                f"Fake 注入失败（调用序 {call_index}）"
            )

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


def _make_fake_embedding() -> Any:
    """Fake Embedding 工厂（AsyncMock(spec=EmbeddingServicePort)——外部 SaaS 豁免）。

    embedding_service 是 strategic_archive_service 的强制依赖（L3 写入链），
    属外部 SaaS 同类——固定维度向量注入使 L3 写入链可构造（6-3 R2-F2 同款；
    存储端口保持真实）。
    """
    from unittest.mock import AsyncMock

    from src.domain.ports.embedding_service import EmbeddingServicePort

    fake = AsyncMock(spec=EmbeddingServicePort)
    fake.embed_query = AsyncMock(return_value=[0.1] * 1024)
    fake.embed_documents = AsyncMock(return_value=[[0.1] * 1024])
    fake.close = AsyncMock()
    return fake


# ===================================================================
# 共享基建：记录总线 + 真实链装配（6-2 形态移植）
# ===================================================================


class _RecordingEventBus:
    """记录发布事件的发布器（手写 EventPublisher 协议实现——4-6/4-7/5-3/6-2 先例）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


class _CachedEmbedding:
    """embedding 查询/文档向量缓存代理（测试面性能优化——非被测对象，6-2 同款）。"""

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


class _StubIsolationSwitchLogRepository:
    """手写 duck-typing 日志仓储替身（5-3/6-2 验收同款——零 IO 替身，真实链归 5-6）。"""

    def __init__(self) -> None:
        self.saved_logs: list[Any] = []

    async def save(self, log: Any) -> None:
        self.saved_logs.append(log)

    async def search(self, query: Any) -> Any:
        from src.domain.ports.isolation_switch_log_repository import IsolationSwitchLogSearchResult

        return IsolationSwitchLogSearchResult(items=(), total=0, offset=query.offset, limit=query.limit)


def _make_real_guard_chain(ctx: dict[str, Any]) -> Any:
    """真实隔离守卫链（5-3/6-2 验收同款三依赖注入——场景级 Redis 仓储）。"""
    if "isolation_guard_chain" in ctx:
        return ctx["isolation_guard_chain"]["guard"]

    from src.application.services.isolation_guard_service import IsolationGuardService
    from src.application.services.isolation_management_service import IsolationManagementService
    from src.domain.ports.resolver import resolve
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_agent_repository import RedisAgentRepository
    from src.infrastructure.storage.redis.redis_isolation_repository import RedisIsolationRepository

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
    _run_async(ctx["_loop"], redis_client.ping())
    return guard


def _instantiate_real_agent(ctx: dict[str, Any]) -> uuid.UUID:
    """经真实实例化用例构造 CEO Agent（5-3/6-2 同步形态先例）。"""
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
    """手工组装工具注册服务（InMemoryToolRepository + register_all——5-3/6-2 同款）。"""
    from src.application.services.tool_registry_service import ToolRegistryService
    from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository

    registry = ToolRegistryService(InMemoryToolRepository())
    registry.register_all()
    return registry


def _build_tool_execution_service(fake_llm: Any) -> Any:
    """真实工具执行装饰链（Fake LLM 注入——5-3/6-2 集成/验收同款）。

    sandbox 替身纪律：AsyncMock(spec=SandboxExecutor) + execute_code 显式
    return_value 真实 dict 形态（Docker 沙箱外部依赖豁免面——6-2 先例）。
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


def _ensure_qdrant_retrieval(ctx: dict[str, Any]) -> None:
    """检索门控 + 租户隔离 collection 建制语料 upsert（3-1a/6-2 验收先例）。"""
    if "retrieval_collection" in ctx:
        return

    from qdrant_client import AsyncQdrantClient

    from src.infrastructure.config.embedding import EmbeddingConfig
    from src.infrastructure.config.qdrant import QdrantConfig
    from src.infrastructure.external_services.embedding.embedding_api_client import EmbeddingAPIClient

    env = ctx["_env"]
    loop = ctx["_loop"]

    async def _setup() -> tuple[str, Any, AsyncQdrantClient]:
        embedding = _CachedEmbedding(EmbeddingAPIClient(EmbeddingConfig.from_env()))
        qconfig = QdrantConfig(
            host=env.qdrant.host, port=env.qdrant.port, grpc_port=env.qdrant.grpc_port, api_key=env.qdrant.api_key
        )
        client = AsyncQdrantClient(url=f"http://{qconfig.host}:{qconfig.port}", timeout=30)
        await embedding.embed_query("连通性探测")  # embedding 服务不可达即抛
        await client.get_collections()  # Qdrant 不可达即抛

        collection = f"test_chain_{uuid.uuid4().hex[:8]}"
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
    """真实 hybrid 检索服务（场景级实例——dense+sparse 双路，6-2 同款）。"""
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


# ===================================================================
# 共享基建：服务门控探测（6-3 形态移植）
# ===================================================================


def _probe_postgres(context: dict[str, Any]) -> None:
    """PG 双预检（连接 + event_outbox/strategic_archives 表存在——5-4 R1-F07 先例）。"""
    import sqlalchemy as sa

    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

    env = context["_env"]
    manager = PostgreSQLManager(
        PostgreSQLConfig(
            host=env.postgres.host,
            port=env.postgres.port,
            database=env.postgres.database,
            username=env.postgres.username,
            password=env.postgres.password,
        )
    )

    async def _probe() -> None:
        engine = manager.get_async_engine()
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT event_id FROM event_outbox LIMIT 1"))
            await conn.execute(sa.text("SELECT archive_id FROM strategic_archives LIMIT 1"))
        await engine.dispose()

    try:
        _run_async(context["_loop"], _probe())
    except Exception as exc:
        pytest.skip(f"PostgreSQL 不可达或 event_outbox/strategic_archives 表未初始化: {exc}")
    context["_pg_manager"] = manager


def _probe_qdrant(context: dict[str, Any]) -> None:
    """Qdrant 连通性门控 + strategic_archive collection 确保（1024/COSINE——L3 前提）。"""
    from qdrant_client import AsyncQdrantClient, models

    env = context["_env"]

    async def _probe() -> None:
        client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
        try:
            existing = {collection.name for collection in (await client.get_collections()).collections}
            if "strategic_archive" not in existing:
                await client.create_collection(
                    collection_name="strategic_archive",
                    vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
                )
        finally:
            await client.close()

    try:
        _run_async(context["_loop"], _probe())
    except Exception as exc:
        pytest.skip(f"Qdrant 不可用: {exc}")


def _probe_minio(context: dict[str, Any]) -> None:
    """MinIO 连通性门控 + archive-evidence bucket 确保（object-lock 自愈——6-3 先例）。"""
    env = context["_env"]

    def _probe() -> None:
        from minio import Minio
        from minio.deleteobjects import DeleteObject

        from src.domain.ports.resolver import resolve

        client = Minio(
            endpoint=env.minio.endpoint,
            access_key=env.minio.access_key,
            secret_key=env.minio.secret_key,
            secure=env.minio.secure,
        )
        bucket_name = resolve("l4_object")._repository._resolve_bucket_name("archive-evidence")
        if not client.bucket_exists(bucket_name):
            try:
                client.make_bucket(bucket_name, object_lock=True)
            except Exception:
                # 并行重建竞态（BucketAlreadyOwnedByYou）——bucket 在位即可
                if not client.bucket_exists(bucket_name):
                    raise
            return
        try:
            client.get_object_lock_config(bucket_name)
        except Exception:
            # 历史无锁形态 best-effort 自愈（bypass 清版本重建带锁；竞态失败接受现状）
            try:
                versions = [
                    DeleteObject(obj.object_name, version_id=obj.version_id)
                    for obj in client.list_objects(bucket_name, recursive=True, include_version=True)
                ]
                _ = list(client.remove_objects(bucket_name, versions, bypass_governance_mode=True))
                client.remove_bucket(bucket_name)
                client.make_bucket(bucket_name, object_lock=True)
            except Exception:
                pass

    try:
        _run_async(context["_loop"], asyncio.to_thread(_probe))
    except Exception as exc:
        pytest.skip(f"MinIO 不可用: {exc}")


# ===================================================================
# 装配链：BLM 全链（真实检索/快照/工具/guard）+ 归档链（真实 L2/L3/L4 +
# Fake Embedding 豁免）+ 6-4 新交付（延迟 import——Task 0 红因锚）
# ===================================================================


def _dispose_assembly(context: dict[str, Any]) -> None:
    """释放既有装配资源（重复装配前置——Redis 客户端关闭 + PG 会话还原，防泄漏）。"""
    _run_async(context["_loop"], _finalize_pg_session(context))
    if context["_redis_client"] is not None:
        try:
            _run_async(context["_loop"], context["_redis_client"].close())
        except Exception:
            pass
    context["_redis_client"] = None
    context["_pg_session"] = None
    context["_pg_session_token"] = None
    context["_chain_assembled"] = False


def _assemble_json_chain(context: dict[str, Any], *, fail_schemas: frozenset[type] = frozenset()) -> None:
    """装配 BLM 思维链全链（四真实服务 + Fake LLM/Fake Embedding/Sandbox 执行器三替身豁免）。

    装配面（6-2 全链形态 + 6-3 归档形态组合）：
    - 真实：Redis（快照存储）/ PG（archive L2 + outbox，AsyncSession 激活）/
      Qdrant（L3 向量）/ MinIO（L4 WORM）/ 真实 guard 链 + CEO 实例化 + 档案
      加载 + 真实工具链/注册表 + 真实 hybrid 检索（R 门控）
    - Fake（外部 SaaS 豁免）：LLMClientPort（八 Schema 族分派 + fail_schemas
      身份注入）+ EmbeddingServicePort（归档 L3 embedding——固定 1024 维）
    - 6-4 新交付（延迟 import——组装归档服务/追溯用例/BLM 第九依赖尾参注入）
    """
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.application.services.blm_planning_service import BlmPlanningService
    from src.application.services.chain_of_thought_archive_service import ChainOfThoughtArchiveService
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.application.use_cases.agent_profile_loading import AgentProfileLoadResult, LoadAgentProfileUseCase
    from src.application.use_cases.get_blm_chain_trace import GetBlmChainTraceUseCase
    from src.application.use_cases.run_blm_planning import RunBlmPlanningUseCase
    from src.domain.entities.agent import AgentRole
    from src.domain.ports.resolver import get_resolver, resolve
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig
    from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
    from src.infrastructure.storage.postgresql.session_context import set_session
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
    from src.infrastructure.storage.redis.redis_snapshot_store import RedisSnapshotStore

    loop = context["_loop"]
    env = context["_env"]

    # 1) 真实 Redis 客户端 + 快照仓储（场景级独立客户端——跨循环教训）
    redis_client = aioredis.Redis(
        host=env.redis.host,
        port=env.redis.port,
        password=env.redis.password or None,
        decode_responses=True,
    )
    _run_async(loop, redis_client.ping())  # 门控：不可达由 Given 步骤先行 skip
    context["_redis_client"] = redis_client
    redis_adapter = RedisAdapter(redis_client=redis_client)
    snapshot_store = RedisSnapshotStore(adapter=redis_adapter)

    # 2) 真实 guard 链 + CEO 实例化 + 档案加载
    _make_real_guard_chain(context)
    agent_id = _instantiate_real_agent(context)
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
    context["agent_id"] = agent_id
    context["profile_result"] = profile_result

    # 3) Fake LLM（八 Schema 族分派 + 身份失败注入）+ 真实工具链
    fake_llm = _make_fake_llm(fail_schemas=fail_schemas)
    context["fake_llm"] = fake_llm
    tool_execution_service = _build_tool_execution_service(fake_llm)

    # 4) PG 会话激活（SessionContext——归档 L2 仓储前置）
    session = AsyncSession(context["_pg_manager"].get_async_engine())
    _run_async(loop, session.begin())
    context["_pg_session"] = session
    context["_pg_session_token"] = set_session(session)

    # 5) 归档服务（真实 L2/L3/L4 + Fake Embedding 豁免 + L5 可选降级；
    #    publisher 默认 None——真实发布场景 S9 经 resolve 重建注入，R3-F8）
    archive_service = StrategicArchiveService(
        archive_repo=resolve("archive_repository"),
        embedding_service=_make_fake_embedding(),  # 外部 SaaS 豁免（R2-F2）
        vector_storage=resolve("l3_vector"),
        object_storage=resolve("l4_object"),
        graph_storage=None,  # L5 可选降级（Neo4j 非本 Story 断言面）
        event_publisher=None,  # 验收默认无发布——发布场景经真实 publisher 重建
        staleness_service=None,
    )

    # 6) 组装归档服务（6-4 新交付——双注入 R1-F6：归档服务 + L4 解引用通道）
    chain_archive_service = ChainOfThoughtArchiveService(
        archive_service=archive_service,
        object_storage=resolve("l4_object"),
    )
    context["chain_archive_service"] = chain_archive_service

    # 7) BLM 规划服务（九依赖——chain_archive_service 尾参注入为 6-4 挂接位）
    recorder = _RecordingEventBus()
    context["recorder"] = recorder
    service = BlmPlanningService(
        llm_client=fake_llm,
        tool_execution_service=tool_execution_service,
        tool_registry_service=_make_registry(),
        isolation_guard=context["isolation_guard_chain"]["guard"],
        hybrid_search=_make_real_hybrid_search(context),
        search_collection=context["retrieval_collection"],
        event_publisher=recorder,
        snapshot_repository=snapshot_store,
        chain_archive_service=chain_archive_service,
    )
    context["blm_service"] = service

    # 8) 图引擎 + 执行用例 + 追溯用例
    context["engine"] = LangGraphEngine(
        config=LangGraphConfig.from_env(),
        event_publisher=recorder,
        blm_planning_service=service,
    )
    profile_use_case = LoadAgentProfileUseCase(
        profile_loader=resolve("agent_profile_loader"),
        repository=context["isolation_guard_chain"]["agent_repository"],
        skill_selector=resolve("skill_selector"),
        event_publisher=InMemoryEventBus(),
    )
    context["use_case"] = RunBlmPlanningUseCase(
        agent_repository=context["isolation_guard_chain"]["agent_repository"],
        agent_profile_use_case=profile_use_case,
        agent_engine=context["engine"],
        blm_planning_service=service,
        isolation_guard=context["isolation_guard_chain"]["guard"],
        event_publisher=recorder,
    )
    context["trace_use_case"] = GetBlmChainTraceUseCase(chain_archive_service=chain_archive_service)
    context["task"] = _BLM_TASK
    context["_resolver"] = get_resolver()


def _register_flow_cleanup(context: dict[str, Any], plan_id: str) -> None:
    """登记 run 级清理面（快照会话键/归档行/outbox 行——按 plan_id 三通道）。"""
    from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX

    context["_snapshot_session_ids"].append(f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}")
    context["_archive_plan_ids"].append(plan_id)
    context["_outbox_plan_ids"].append(plan_id)
    for step_value in ("trend", "market_customer", "competition", "self", "opportunity", "opportunity_gap"):
        context["_snapshot_session_ids"].append(f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}:{step_value}")


def _run_full_flow(context: dict[str, Any]) -> Any:
    """执行 BLM 前两阶段全流程（显式 plan_id——清理面可登记）。"""
    plan_id = context.get("_plan_id") or _new_plan_id()
    context["_plan_id"] = plan_id
    _register_flow_cleanup(context, plan_id)
    result = _run_async(
        context["_loop"],
        context["use_case"].execute(agent_id=context["agent_id"], task=context["task"], plan_id=plan_id),
    )
    _commit_pg_session(context)  # 归档行/outbox 行提交——独立连接断言可见
    context["result"] = result
    return result


def _chain_records_of(context: dict[str, Any]) -> tuple[Any, ...]:
    """取执行结果 chain_records（Result 携带面——AC-2）。"""
    result = context["result"]
    raw_records = getattr(result, "chain_records", None)
    assert raw_records is not None, "BlmPlanningResult 未携带 chain_records（AC-2 Result 扩展缺失）"
    records: tuple[Any, ...] = tuple(raw_records)
    return records


def _expected_payload_for(stage: str) -> dict[str, Any]:
    """按 stage 型构造期望 payload（独立构造——S2/S5/S6 判别力锚）。"""
    if stage == "performance_gap":
        return dict(_EXPECTED_GAP_PAYLOAD)
    if stage == "market_insight_synthesis":
        return dict(_EXPECTED_SYNTHESIS_PAYLOAD)
    return dict(_EXPECTED_STEP_PAYLOADS[stage])


def _query_archive_rows(context: dict[str, Any], plan_id: str) -> list[Any]:
    """按 plan_id + EVIDENCE_PACKAGE 查询 L2 档案行（独立连接——断言面）。"""
    import sqlalchemy as sa

    async def _query() -> list[Any]:
        engine = context["_pg_manager"].get_async_engine()
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    sa.text(
                        "SELECT archive_id, archive_type, decision_basis, blob_ref FROM strategic_archives "
                        "WHERE plan_id = CAST(:plan_id AS uuid) AND archive_type = 'evidence_package' "
                        "ORDER BY archived_at ASC"
                    ),
                    {"plan_id": plan_id},
                )
                rows: list[Any] = result.fetchall()
                return rows
        finally:
            await engine.dispose()

    return _run_async(context["_loop"], _query())


def _query_outbox_rows(context: dict[str, Any], plan_id: str, event_type: str | None = None) -> list[Any]:
    """按 plan_id 查询 outbox 事件行（payload 双 JSONB 通道兜底——6-2 先例）。"""
    import sqlalchemy as sa

    type_filter = "AND event_type = :etype" if event_type else ""

    async def _query() -> list[Any]:
        engine = context["_pg_manager"].get_async_engine()
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    sa.text(
                        "SELECT event_id, event_type, payload FROM event_outbox "
                        "WHERE (payload->'payload'->>'plan_id' = :plan_id "
                        "OR payload->'metadata'->>'plan_id' = :plan_id) " + type_filter
                    ),
                    {"plan_id": plan_id, "etype": event_type},
                )
                rows: list[Any] = result.fetchall()
                return rows
        finally:
            await engine.dispose()

    return _run_async(context["_loop"], _query())


def _retrieve_blob_json(context: dict[str, Any], blob_ref: str) -> dict[str, Any]:
    """L4 WORM blob 解引用（流式下载累积 + JSON 反序列化——AC-5 通道 R1-F6）。"""
    from src.domain.ports.resolver import resolve

    async def _read() -> dict[str, Any]:
        l4 = resolve("l4_object")
        chunks: list[bytes] = []
        async for chunk in l4.retrieve(bucket_type="archive-evidence", object_key=blob_ref):
            chunks.append(chunk)
        blob_data: dict[str, Any] = json.loads(b"".join(chunks).decode("utf-8"))
        return blob_data

    return _run_async(context["_loop"], _read())


# ===================================================================
# 场景绑定（13 场景全绑定——R6 欠账禁沿用）
# ===================================================================


@scenario("test_acceptance_json_chain_of_thought.feature", "S1 全链执行产出 8 条思维链且全量归档可读回")
def test_s1_full_chain_eight_chains() -> None:
    """AC-1.1 全链 8 条 + 归档成功率（OD-5 口径并入）。"""
    pass


@scenario("test_acceptance_json_chain_of_thought.feature", "S2 组装映射判别力（素材独立构造期望非回声）")
def test_s2_assembly_mapping_discriminating() -> None:
    """AC-1.2 组装映射判别力（期望独立构造——非 Fake 回声）。"""
    pass


@scenario("test_acceptance_json_chain_of_thought.feature", "S3 降级步骤思维链仍产出且信封在位")
def test_s3_degraded_step_envelope() -> None:
    """AC-1.3 降级步思维链（信封形态 + 三处降级承载）。"""
    pass


@scenario("test_acceptance_json_chain_of_thought.feature", "S4 执行结果携带思维链且事件投影真实化")
def test_s4_result_carries_chains_and_projection() -> None:
    """AC-2 Result 携带 + AgentDecided 投影 chain_summary 真实化。"""
    pass


@scenario("test_acceptance_json_chain_of_thought.feature", "S5 思维链归档真实落位 L2 与 L3 与 L4")
def test_s5_archive_three_layer_placement() -> None:
    """AC-3 EVIDENCE_PACKAGE 三层落位（L2 行/L3 点/L4 blob + WORM）。"""
    pass


@scenario("test_acceptance_json_chain_of_thought.feature", "S6 决策追溯查询正向（round-trip 与 blob 深度解引用）")
def test_s6_trace_query_roundtrip() -> None:
    """AC-5 追溯查询正向（round-trip 等值 + include_blob 深度解引用）。"""
    pass


@scenario("test_acceptance_json_chain_of_thought.feature", "S7 追溯查询负向两形态")
def test_s7_trace_query_negative() -> None:
    """AC-5 负向（空清单 + 非 UUID 242——单 Scenario 双段 R2-F9）。"""
    pass


@scenario("test_acceptance_json_chain_of_thought.feature", "S8 快照与事件契约零回归")
def test_s8_snapshot_event_contract_zero_regression() -> None:
    """AC-6 快照七键契约 + BlmStageCompleted + 事件通道零新增。"""
    pass


@scenario("test_acceptance_json_chain_of_thought.feature", "S9 事件零新增且 ArchiveCreated 落行")
def test_s9_event_zero_new_and_archive_created_rows() -> None:
    """AC-6 ArchiveCreated 落行（真实 publisher）+ 事件类型零新增。"""
    pass


@scenario("test_acceptance_json_chain_of_thought.feature", "S10 思维链五段展示形态")
def test_s10_to_display_five_segments() -> None:
    """AC-1.5 to_display 展示形态（五段顺序 + XML 标签闭合对）。"""
    pass


@scenario("test_acceptance_json_chain_of_thought.feature", "S11 组装窗口 P95 小于 50 毫秒")
def test_s11_assembly_window_p95() -> None:
    """AC-7 组装窗口 P95<50ms（纯函数直调——OD-10 口径差声明）。"""
    pass


@scenario("test_acceptance_json_chain_of_thought.feature", "S12 并发写入 10 个思维链")
def test_s12_concurrent_ten_chains() -> None:
    """AC-7 并发 10（gather + session_context 独立 scope——R1-F7）。"""
    pass


@scenario("test_acceptance_json_chain_of_thought.feature", "S13 开发完成清单收尾（src 与四测试目录交付件存在性）")
def test_s13_completion_checklist() -> None:
    """收尾清单（交付件存在性 + 关键符号 + 四守护文件零改动）。"""
    pass


# ===================================================================
# 背景
# ===================================================================


@given("Redis 服务可用")
def redis_service_available(context: dict[str, Any]) -> None:
    """Redis 连通性门控（Background——不可达环境动态 skip）。"""
    import redis.asyncio as aioredis

    env = context["_env"]
    client = aioredis.Redis(
        host=env.redis.host,
        port=env.redis.port,
        password=env.redis.password or None,
        decode_responses=True,
    )
    try:
        _run_async(context["_loop"], client.ping())
    except Exception as exc:
        _run_async(context["_loop"], client.close())
        pytest.skip(f"Redis 不可用: {exc}")
    _run_async(context["_loop"], client.close())


# ===================================================================
# AC-1: BLM 每步五段思维链产出——S1/S2/S3/S10
# ===================================================================


@given("BLM 思维链测试管线已装配（四真实服务与 Fake LLM、Fake Embedding、Sandbox 执行器三替身豁免）")
def json_chain_pipeline_available(context: dict[str, Any]) -> None:
    """四真实服务三探测门控 + 全链装配（PG/Qdrant/MinIO 逐档 skip + 检索 R 门控）。"""
    _probe_postgres(context)
    _probe_qdrant(context)
    _probe_minio(context)
    _assemble_json_chain(context)
    context["_chain_assembled"] = True


@given("以全新 plan_id 启动 BLM 前两阶段全流程")
def fresh_plan_id_prepared(context: dict[str, Any]) -> None:
    """全新 plan_id 就绪（场景间互异——资源唯一性隔离行）。"""
    context["_plan_id"] = _new_plan_id()


@given("Fake LLM 对六子步骤 Schema 子集注入恒定失败")
def fake_llm_schema_subset_failure_injected(context: dict[str, Any]) -> None:
    """六子 Schema 子集恒败注入（R3-F10——限子集防全降级 481 场景不可达）。

    双装配防泄漏：既有默认链先释放资源再以失败注入形态重装。
    """
    from src.application.services.blm_planning_prompts import (
        MARKET_INSIGHT_STEP_SCHEMA,
        MarketInsightStep,
    )

    subset = frozenset(
        {
            MARKET_INSIGHT_STEP_SCHEMA[MarketInsightStep.TREND],
            MARKET_INSIGHT_STEP_SCHEMA[MarketInsightStep.MARKET_CUSTOMER],
        }
    )
    if context.get("_chain_assembled"):
        _dispose_assembly(context)
    _assemble_json_chain(context, fail_schemas=subset)
    context["_chain_assembled"] = True


@when("全流程 8 步执行完成")
def full_flow_eight_steps_executed(context: dict[str, Any]) -> None:
    """全流程执行（经用例层——Result 携带 chain_records 断言面）。"""
    _run_full_flow(context)


@then("图终态 chain_records 恰 8 条")
def final_state_chain_records_exactly_eight(context: dict[str, Any]) -> None:
    """chain_records 恰 8 条（OD-3 每步粒度——图 state 经投影直写回传）。"""
    records = _chain_records_of(context)
    assert len(records) == 8, f"chain_records 实测={len(records)} 条 期望=8（每步一条——OD-3 粒度）"


@then("每条思维链四文本字段非空白且 tools_used 形态合法")
def every_chain_four_text_fields_non_blank(context: dict[str, Any]) -> None:
    """四文本字段非空白 + tools_used 形态合法（R2-F7 口径——空元组合法）。"""
    for record in _chain_records_of(context):
        chain = record.chain
        for field_name in ("input_summary", "reflection", "constraints_check", "final_answer"):
            value = getattr(chain, field_name)
            assert isinstance(value, str) and value.strip(), (
                f"stage={record.stage} 字段 {field_name} 空白（VO 242 校验应已拦截）"
            )
        assert isinstance(chain.tools_used, tuple), f"stage={record.stage} tools_used 非 tuple"
        for item in chain.tools_used:
            assert isinstance(item, str) and item.strip(), f"stage={record.stage} tools_used 元素非法: {item!r}"


@then("stage 锚与 STAGE_VALUE_DOMAIN 八值按执行序一一对应")
def stage_anchors_match_domain_in_order(context: dict[str, Any]) -> None:
    """stage 锚按执行序与八值域一一对应（独立构造期望——非读回自比）。"""
    records = _chain_records_of(context)
    actual_order = tuple(record.stage for record in records)
    assert actual_order == EXPECTED_STAGE_ORDER, f"stage 执行序实测={actual_order} 期望={EXPECTED_STAGE_ORDER}"


@then("档案库按 plan_id 与 EVIDENCE_PACKAGE 过滤恰 8 行（归档成功率 8/8）")
def archive_filtered_exactly_eight_rows(context: dict[str, Any]) -> None:
    """归档成功率 8/8（OD-5 口径——正常路径 N 归档 N 可查回）。"""
    rows = _query_archive_rows(context, context["_plan_id"])
    assert len(rows) == 8, f"EVIDENCE_PACKAGE 档案实测={len(rows)} 行 期望=8（归档成功率）"
    archived_flags = [record.archived for record in _chain_records_of(context)]
    assert all(archived_flags), f"chain_records archived 台账含 False: {archived_flags}"


@then("每条思维链 tools_used 等于独立构造的期望工具轨迹")
def every_chain_tools_used_matches_expected(context: dict[str, Any]) -> None:
    """tools_used 判别力断言（执行轨迹第三位单数 slug 包装——非 Fake 回声）。"""
    for record in _chain_records_of(context):
        expected = EXPECTED_TOOL_TRACE[record.stage]
        assert record.chain.tools_used == expected, (
            f"stage={record.stage} tools_used 实测={record.chain.tools_used} 期望={expected}（独立构造自白名单首候选）"
        )


@then("每条思维链 final_answer 经 JSON 反序列化等于该步结构化产物期望值")
def every_chain_final_answer_matches_expected(context: dict[str, Any]) -> None:
    """final_answer round-trip 判别（json.loads 等值——asdict tuple 已归一 list）。"""
    for record in _chain_records_of(context):
        expected = _expected_payload_for(record.stage)
        actual = json.loads(record.chain.final_answer)
        assert actual == expected, f"stage={record.stage} final_answer round-trip 实测={actual} 期望={expected}"


@then("每条思维链 input_summary 含该步语义配置与证据计数")
def every_chain_input_summary_contains_semantics(context: dict[str, Any]) -> None:
    """input_summary 语义配置 + 任务 + 证据计数（三型分列公式——R1-F3）。"""
    task = context["task"]
    for record in _chain_records_of(context):
        summary_text = record.chain.input_summary
        if record.stage == "market_insight_synthesis":
            display_name, role_prefix = _EXPECTED_SYNTHESIS_SEMANTICS
            assert "综合结论 2 项" in summary_text, f"synthesis 结论计数缺失: {summary_text!r}"
        else:
            display_name, role_prefix = _EXPECTED_SEMANTICS[record.stage]
            import re

            match = re.search(r"检索证据 (\d+) 条", summary_text)
            assert match is not None, f"stage={record.stage} 证据计数段缺失: {summary_text!r}"
            evidence_count = int(match.group(1))
            assert 0 <= evidence_count <= 5, f"stage={record.stage} 证据计数越界: {evidence_count}"
        assert display_name in summary_text, f"stage={record.stage} display_name 缺失: {summary_text!r}"
        assert role_prefix in summary_text, f"stage={record.stage} role_prefix 缺失: {summary_text!r}"
        assert task[:80] in summary_text, f"stage={record.stage} 任务文本缺失: {summary_text!r}"


@then("每条思维链 reflection 与 constraints_check 按冻结公式构造期望值")
def every_chain_reflection_and_constraints_match_formula(context: dict[str, Any]) -> None:
    """reflection/constraints_check 冻结公式判别（值级等值——独立构造期望）。"""
    for record in _chain_records_of(context):
        stage = record.stage
        chain = record.chain
        if stage == "performance_gap":
            expected_reflection = "步骤产出: 财务差距量化：营收达成率 82%，毛利率 -3.2pct；根因 3 项；流程正常"
            expected_constraints = "四字段产物完整性: 通过；证据充分性: 充足；降级标记: False"
        elif stage == "market_insight_synthesis":
            expected_reflection = "综合结论 2 项；降级输入 0 项；流程正常"
            expected_constraints = "结论产出判定: 通过；降级输入: 0 项；降级标记: False"
        else:
            step_value = stage.removeprefix("market_insight_")
            expected_reflection = f"步骤产出: {_FAKE_STEP_SUMMARY_PREFIX}:{step_value}（结构化要点）；要点 2 项；流程正常"
            expected_constraints = "结构化输出值域校验: 通过；证据充分性: 充足；降级标记: False"
        assert chain.reflection == expected_reflection, (
            f"stage={stage} reflection 实测={chain.reflection!r} 期望={expected_reflection!r}"
        )
        assert chain.constraints_check == expected_constraints, (
            f"stage={stage} constraints_check 实测={chain.constraints_check!r} 期望={expected_constraints!r}"
        )


@then("降级步骤思维链仍产出且 final_answer 为降级信封 JSON")
def degraded_step_chain_envelope_json(context: dict[str, Any]) -> None:
    """降级步思维链产出 + 信封形态（R2-F2——产物缺席形态独有）。"""
    records = _chain_records_of(context)
    degraded_stages = {"market_insight_trend", "market_insight_market_customer"}
    for record in records:
        if record.stage not in degraded_stages:
            continue
        envelope = json.loads(record.chain.final_answer)
        assert envelope.get("degraded") is True, f"降级步 {record.stage} 信封 degraded 非 True: {envelope}"
        assert envelope.get("degrade_reason"), f"降级步 {record.stage} degrade_reason 缺失"


@then("降级信封携带 degrade_reason 与降级标注在 constraints_check")
def degraded_envelope_carries_reason_and_marker(context: dict[str, Any]) -> None:
    """降级三处承载之 constraints_check 面（reflection 后缀/decision_basis.degraded 同源）。"""
    for record in _chain_records_of(context):
        if record.stage == "market_insight_trend":
            assert "降级标记: True" in record.chain.constraints_check, (
                f"降级步 constraints_check 缺降级标注: {record.chain.constraints_check!r}"
            )
            assert "降级" in record.chain.reflection, f"降级步 reflection 缺降级后缀: {record.chain.reflection!r}"


@then("每条思维链 to_display 展示五段顺序与三个闭合 XML 标签对与 JSON 尾段")
def every_chain_to_display_five_segments(context: dict[str, Any]) -> None:
    """to_display 展示形态（DC-2 展示用标签——5-3 既有 VO 方法零改动复用）。"""
    records = _chain_records_of(context)
    for record in records:
        display = record.chain.to_display()
        assert display.startswith(f"Input: {record.chain.input_summary}"), f"首段 Input 缺失: {display[:60]!r}"
        for tag in ("Reflection", "Tools_Used", "Constraints_Check"):
            assert f"<{tag}>" in display and f"</{tag}>" in display, f"标签对 {tag} 缺失"
        assert display.endswith(record.chain.final_answer), "JSON 尾段缺失（应以 final_answer 原样结尾）"
    # 空轨迹占位（synthesis 恒空元组——(none) 展示形态）
    synthesis_record = records[-1]
    assert synthesis_record.chain.tools_used == (), "synthesis 步 tools_used 应恒空元组"
    assert "(none)" in synthesis_record.chain.to_display(), "空轨迹 (none) 占位缺失"


# ===================================================================
# AC-2: Result 携带 + 事件投影真实化——S4
# ===================================================================


@then("执行结果 chain_records 恰 8 条且为 tuple 形态")
def result_chain_records_exactly_eight_tuple(context: dict[str, Any]) -> None:
    """Result 携带面（默认尾字段 () 零破坏 + 读侧 tuple 归一 R2-F5）。"""
    records = _chain_records_of(context)
    assert isinstance(records, tuple), f"chain_records 非 tuple 形态: {type(records).__name__}"
    assert len(records) == 8, f"chain_records 实测={len(records)} 期望=8"


@then("AgentDecided 投影 chain_summary 等于末条思维链 final_answer 前 200 字符")
def agent_decided_projection_chain_summary_realized(context: dict[str, Any]) -> None:
    """投影值级断言（非仅类型级——6-3 R1-F6/R8 教训）。"""
    records = _chain_records_of(context)
    last_final_answer = records[-1].chain.final_answer
    agent_decided = [event for event in context["recorder"].published_events if type(event).__name__ == "AgentDecided"]
    assert len(agent_decided) == 1, f"AgentDecided 实测={len(agent_decided)} 次 期望=1"
    payload = agent_decided[0].decision_result
    assert payload["chain_summary"] == last_final_answer[:200], (
        f"chain_summary 实测={payload['chain_summary']!r} 期望=末条 final_answer[:200]"
    )


@then("投影五键白名单结构与纯标量约束维持")
def projection_five_keys_pure_scalars_maintained(context: dict[str, Any]) -> None:
    """五键白名单（DC-11——结构零变化）+ 纯标量（VO 实例禁入 payload）。"""
    agent_decided = [event for event in context["recorder"].published_events if type(event).__name__ == "AgentDecided"]
    payload = agent_decided[0].decision_result
    assert frozenset(payload.keys()) == EXPECTED_PROJECTION_KEYS, f"投影键族漂移: {sorted(payload.keys())}"
    for key, value in payload.items():
        assert isinstance(value, (str, int, float, bool)), f"投影键 {key} 非纯标量: {type(value)}"


# ===================================================================
# AC-3: 归档真实落位——S5
# ===================================================================


@then("L2 PostgreSQL 恰 8 行 EVIDENCE_PACKAGE 档案且 decision_basis 携带 kind 与 stage 语境锚")
def l2_eight_rows_with_kind_stage_anchor(context: dict[str, Any]) -> None:
    """L2 行 + decision_basis 语境锚（kind+stage——R8-F3 同构）。"""
    from src.application.ports.chain_of_thought_archive import CHAIN_ARCHIVE_KIND

    rows = _query_archive_rows(context, context["_plan_id"])
    assert len(rows) == 8, f"L2 EVIDENCE_PACKAGE 实测={len(rows)} 行 期望=8"
    stages_seen = []
    for row in rows:
        decision_basis = row[2]
        assert decision_basis.get("kind") == CHAIN_ARCHIVE_KIND, f"kind 语境锚缺失: {decision_basis.get('kind')!r}"
        stage = decision_basis.get("stage")
        assert stage in EXPECTED_STAGE_ORDER, f"stage 语境锚越域: {stage!r}"
        stages_seen.append(stage)
    assert stages_seen == list(EXPECTED_STAGE_ORDER), f"L2 行 stage 序漂移: {stages_seen}"


@then("L3 Qdrant 点可搜且 payload 的 archive_id 与档案行匹配")
def l3_points_searchable_archive_id_matches(context: dict[str, Any]) -> None:
    """L3 点可搜（filter 面过滤检索——不依赖相似命中）。"""
    rows = _query_archive_rows(context, context["_plan_id"])
    archive_ids = {str(row[0]) for row in rows}

    async def _search() -> set[str]:
        from qdrant_client import AsyncQdrantClient, models

        env = context["_env"]
        client = AsyncQdrantClient(url=f"http://{env.qdrant.host}:{env.qdrant.port}", timeout=10)
        try:
            found: set[str] = set()
            for archive_id in archive_ids:
                result = await client.scroll(
                    collection_name="strategic_archive",
                    scroll_filter=models.Filter(
                        must=[models.FieldCondition(key="archive_id", match=models.MatchValue(value=archive_id))]
                    ),
                    limit=1,
                )
                for point in result[0]:
                    payload = point.payload or {}
                    found.add(str(payload.get("archive_id")))
            return found
        finally:
            await client.close()

    found = _run_async(context["_loop"], _search())
    assert found == archive_ids, f"L3 点覆盖不全: 实测={len(found)} 期望={len(archive_ids)}"


@then("L4 MinIO 对象可取且 blob 解引用 JSON 等于独立构造的期望五字段")
def l4_blob_retrievable_json_matches_expected(context: dict[str, Any]) -> None:
    """L4 blob 深度解引用等值（判别力——非自证）。"""
    from src.application.ports.chain_of_thought_archive import CHAIN_ARCHIVE_KIND

    rows = _query_archive_rows(context, context["_plan_id"])
    stage_by_blob = {}
    for row in rows:
        decision_basis = row[2]
        assert decision_basis.get("kind") == CHAIN_ARCHIVE_KIND
        stage_by_blob[row[3]] = decision_basis["stage"]
    for blob_ref, stage in stage_by_blob.items():
        blob_json = _retrieve_blob_json(context, blob_ref)
        assert blob_json.get("stage") == stage, f"blob stage 锚漂移: {blob_json.get('stage')!r} 期望={stage}"
        chain_dict = blob_json["chain"]
        expected = _expected_payload_for(stage)
        assert json.loads(chain_dict["final_answer"]) == expected, (
            f"stage={stage} blob final_answer 与期望不等值（WORM 真源一致性）"
        )


@then("WORM 保留天数为 2555 天")
def worm_retention_2555_days(context: dict[str, Any]) -> None:
    """WORM retention 验证（6-3 集成① L4 断言先例——get_metadata retention 属性）。"""
    rows = _query_archive_rows(context, context["_plan_id"])
    blob_refs = [row[3] for row in rows if row[3]]
    assert blob_refs, "无 blob_ref（L4 落对象双前提未满足——R1-F16）"

    def _check_retention() -> None:
        from minio import Minio

        from src.domain.ports.resolver import resolve

        env = context["_env"]
        client = Minio(
            endpoint=env.minio.endpoint,
            access_key=env.minio.access_key,
            secret_key=env.minio.secret_key,
            secure=env.minio.secure,
        )
        bucket_name = resolve("l4_object")._repository._resolve_bucket_name("archive-evidence")
        for blob_ref in blob_refs[:2]:  # 抽样两条（WORM retention 是 bucket 级对象锁语义）
            retention = client.get_object_retention(bucket_name, blob_ref)
            assert retention is not None, f"对象 {blob_ref} 无 retention 配置"
            days = (retention.retain_until_date.timestamp() - time.time()) / 86400
            assert 2550 <= days <= 2560, f"对象 {blob_ref} retention 实测={days:.1f} 天 期望≈2555"

    _run_async(context["_loop"], asyncio.to_thread(_check_retention))


# ===================================================================
# AC-5: 决策追溯查询面——S6/S7
# ===================================================================


@then("决策追溯查询查回 8 条且按归档时间升序排列")
def trace_query_returns_eight_sorted(context: dict[str, Any]) -> None:
    """追溯查询（include_blob=True 一次到位——S6 正向主断言）。"""
    view = _run_async(
        context["_loop"],
        context["trace_use_case"].execute(plan_id=context["_plan_id"], include_blob=True),
    )
    context["trace_view"] = view
    assert view.total == 8, f"追溯 total 实测={view.total} 期望=8"
    stages = [record["stage"] for record in view.records]
    assert stages == list(EXPECTED_STAGE_ORDER), f"追溯 stage 升序漂移: {stages}"


@then("每条五字段与组装期期望值等值（独立构造期望）")
def trace_records_five_fields_match_expected(context: dict[str, Any]) -> None:
    """五字段 round-trip 等值（重构 VO 经 242 校验 + tuple 归一 R1-F9）。"""
    view = context["trace_view"]
    for record in view.records:
        stage = record["stage"]
        chain = record["chain"]
        expected_payload = _expected_payload_for(stage)
        assert json.loads(chain.final_answer) == expected_payload, f"stage={stage} 追溯 final_answer 漂移"
        expected_tools = EXPECTED_TOOL_TRACE[stage]
        assert chain.tools_used == expected_tools, (
            f"stage={stage} 追溯 tools_used 实测={chain.tools_used} 期望={expected_tools}（tuple 归一口径）"
        )


@then("include_blob 为真时 blob_content 与独立构造的期望五字段 dict 等值")
def blob_content_matches_expected_five_fields(context: dict[str, Any]) -> None:
    """blob_content 落位断言（R2-F4——值级非交互回声）。"""
    view = context["trace_view"]
    for record in view.records:
        blob_content = record.get("blob_content")
        assert blob_content is not None, f"stage={record['stage']} blob_content 为 None（解引用失败或未填充）"
        chain_dict = blob_content["chain"]
        expected_payload = _expected_payload_for(record["stage"])
        assert json.loads(chain_dict["final_answer"]) == expected_payload, (
            f"stage={record['stage']} blob_content final_answer 与期望不等值"
        )


@given("无档案的合法 plan_id 就绪")
def valid_plan_id_without_archives(context: dict[str, Any]) -> None:
    """合法 UUID 且无归档（空清单语义——查询面幂等读）。"""
    context["_query_plan_id"] = str(uuid.uuid4())


@given("非法 plan_id 形态（非 UUID）")
def invalid_plan_id_form(context: dict[str, Any]) -> None:
    """非 UUID 形态（242 守卫通道——与空清单语义分立 R1-F14）。"""
    context["_query_plan_id"] = "not-a-uuid-form"
    context["_expect_242"] = True


@when("执行决策追溯查询")
def execute_trace_query(context: dict[str, Any]) -> None:
    """执行追溯查询（负向 242 捕获为结果面——Then 分型断言）。"""
    if context.get("_expect_242"):
        from src.domain.exceptions import EntityValidationError

        try:
            _run_async(context["_loop"], context["trace_use_case"].execute(plan_id=context["_query_plan_id"]))
            context["_query_error"] = None
        except EntityValidationError as error:
            context["_query_error"] = error
        return
    view = _run_async(
        context["_loop"],
        context["trace_use_case"].execute(plan_id=context["_query_plan_id"]),
    )
    context["trace_view"] = view


@then("返回空清单且 total 为 0")
def empty_records_total_zero(context: dict[str, Any]) -> None:
    """空清单（查询面空结果不抛异常——与恢复面 480 语义分立）。"""
    view = context["trace_view"]
    assert view.total == 0, f"无档案 plan_id total 实测={view.total} 期望=0"
    assert view.records == [], f"无档案 plan_id records 实测={view.records} 期望=[]"


@then("抛出 EntityValidationError 且异常编码为 EXCEPTION_242")
def raises_entity_validation_242(context: dict[str, Any]) -> None:
    """非 UUID 242（CLI 守卫构造真实异常——6-3 R1-F18 统一形态先例）。"""
    error = context.get("_query_error")
    assert error is not None, "非 UUID plan_id 未抛 EntityValidationError（242 守卫缺失）"
    assert getattr(error, "code", None) == "EXCEPTION_242", f"异常编码实测={getattr(error, 'code', None)!r}"


# ===================================================================
# AC-6: 契约零回归——S8/S9
# ===================================================================


@then("latest 快照 state_data 维持七键契约零新键")
def latest_snapshot_seven_keys_unchanged(context: dict[str, Any]) -> None:
    """快照七键契约（OD-8——chain_records 不进 Redis state_data）。"""
    from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX

    snapshot = _run_async(
        context["_loop"],
        context["blm_service"].snapshot_repository.load(f"{BLM_PLANNING_SESSION_PREFIX}{context['_plan_id']}"),
    )
    assert snapshot is not None, "latest 快照缺失"
    actual_keys = frozenset(snapshot.state_data.keys())
    assert actual_keys == EXPECTED_SNAPSHOT_SEVEN_KEYS, (
        f"快照键族漂移: 新增={sorted(actual_keys - EXPECTED_SNAPSHOT_SEVEN_KEYS)} "
        f"缺失={sorted(EXPECTED_SNAPSHOT_SEVEN_KEYS - actual_keys)}"
    )


@then("BlmStageCompleted 事件恰 8 次发布且 stage 值域合法")
def blm_stage_completed_eight_times_valid_stages(context: dict[str, Any]) -> None:
    """BlmStageCompleted 8 次（每步一事件——6-1 既有契约零改动）。"""
    from src.domain.value_objects.blm_phases import STAGE_VALUE_DOMAIN

    events = [event for event in context["recorder"].published_events if type(event).__name__ == "BlmStageCompleted"]
    assert len(events) == 8, f"BlmStageCompleted 实测={len(events)} 次 期望=8"
    for event in events:
        assert event.stage in STAGE_VALUE_DOMAIN, f"stage 越域: {event.stage!r}"


@then("事件通道配置与路由映射零新增条目")
def event_channel_and_router_zero_new_entries(context: dict[str, Any]) -> None:
    """零新事件守护（event_channels.yaml + ChannelRouter.DEFAULT_MAPPINGS 零 diff）。"""
    yaml_path = REPO_ROOT / "configs" / "event_channels.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")
    for marker in ("ChainOfThought", "chain_of_thought", "BlmChain"):
        assert marker not in yaml_text, f"event_channels.yaml 含思维链事件标记 {marker!r}（零新事件违例）"
    from src.infrastructure.messaging.channel_router import ChannelRouter

    router_source = Path(ChannelRouter.__module__.replace(".", "/") + ".py")
    if not router_source.exists():
        import inspect

        router_source_text = inspect.getsource(ChannelRouter)
    else:
        router_source_text = router_source.read_text(encoding="utf-8")
    for marker in ("ChainOfThought", "BlmChain"):
        assert marker not in router_source_text, f"ChannelRouter 含思维链事件标记 {marker!r}（零新事件违例）"


@given("真实事件发布器与 PG outbox 已装配")
def real_publisher_and_outbox_assembled(context: dict[str, Any]) -> None:
    """真实 publisher 装配（clear_singleton + resolve 覆写——6-3 S9 先例 R3-F8）。

    双落行重建：BLM 服务（BlmStageCompleted/AgentDecided）+ 归档服务内
    ArchiveCreated 均注入真实 publisher。双装配防泄漏：既有默认链先释放
    资源再重装。
    """
    from src.application.services.blm_planning_service import BlmPlanningService
    from src.application.services.chain_of_thought_archive_service import ChainOfThoughtArchiveService
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.domain.ports.resolver import get_resolver, resolve

    if context.get("_chain_assembled"):
        _dispose_assembly(context)
    _assemble_json_chain(context)
    get_resolver().clear_singleton()
    real_publisher = resolve("event_publisher")

    archive_service = StrategicArchiveService(
        archive_repo=resolve("archive_repository"),
        embedding_service=_make_fake_embedding(),
        vector_storage=resolve("l3_vector"),
        object_storage=resolve("l4_object"),
        graph_storage=None,
        event_publisher=real_publisher,
        staleness_service=None,
    )
    chain_archive_service = ChainOfThoughtArchiveService(
        archive_service=archive_service,
        object_storage=resolve("l4_object"),
    )
    context["chain_archive_service"] = chain_archive_service
    context["blm_service"] = BlmPlanningService(
        llm_client=context["fake_llm"],
        tool_execution_service=context["blm_service"].tool_execution_service,
        tool_registry_service=context["blm_service"].tool_registry_service,
        isolation_guard=context["blm_service"].isolation_guard,
        hybrid_search=context["blm_service"].hybrid_search,
        search_collection=context["retrieval_collection"],
        event_publisher=real_publisher,
        snapshot_repository=context["blm_service"].snapshot_repository,
        chain_archive_service=chain_archive_service,
    )
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig

    context["engine"] = LangGraphEngine(
        config=LangGraphConfig.from_env(),
        event_publisher=real_publisher,
        blm_planning_service=context["blm_service"],
    )
    context["use_case"]._agent_engine = context["engine"]
    context["use_case"]._blm_planning_service = context["blm_service"]
    context["use_case"]._event_publisher = real_publisher

    def _restore() -> None:
        get_resolver().clear_singleton()

    context["_restorers"].append(_restore)


@then("outbox 落行 ArchiveCreated 恰 8 行")
def outbox_archive_created_exactly_eight_rows(context: dict[str, Any]) -> None:
    """ArchiveCreated 落行 8 行（归档内事件发布——零新事件复用承载）。"""
    time.sleep(0.2)  # outbox 异步落行窗口
    rows = _query_outbox_rows(context, context["_plan_id"], event_type="ArchiveCreated")
    assert len(rows) == 8, f"outbox ArchiveCreated 实测={len(rows)} 行 期望=8"
    context["_outbox_event_ids"].extend(str(row[0]) for row in rows)


@then("事件类型集合零新增（无思维链专属事件）")
def event_type_set_zero_new(context: dict[str, Any]) -> None:
    """本 run 事件类型集合 ⊆ 既有四类（零新事件判别）。"""
    rows = _query_outbox_rows(context, context["_plan_id"])
    known_types = {"PlanningStarted", "BlmStageCompleted", "AgentDecided", "ArchiveCreated"}
    actual_types = {row[1] for row in rows}
    unexpected = actual_types - known_types
    assert not unexpected, f"零新事件违例: 出现既有白名单外事件类型 {sorted(unexpected)}"
    context["_outbox_event_ids"].extend(str(row[0]) for row in rows)


# ===================================================================
# AC-7: 性能与并发——S11/S12
# ===================================================================


@when("对纯组装函数执行 20 轮以上采样")
def sample_pure_assembly_function(context: dict[str, Any]) -> None:
    """组装窗口采样（OD-10 口径差：素材就绪→VO 构造完成；归档 I/O/LLM 出栈）。

    采样对象=模块级纯函数 compose_step_chain（R1-F13——零 I/O 零 LLM）；
    采样素材型=六子步骤型（Task 5.4 钦定）；task 文本固定。
    """
    from src.application.ports.chain_of_thought_archive import StepChainMaterial
    from src.application.services.chain_of_thought_archive_service import compose_step_chain

    material = StepChainMaterial(
        stage="market_insight_trend",
        display_name="看趋势",
        role_prefix="以 CEO 宏观趋势判断与 CTO 技术趋势分析的双重视角",
        task=_BLM_TASK,
        evidence_count=5,
        tool_slug="PESTEL 分析",
        evidence_refs=("chunk-001", "chunk-002", "chunk-003", "chunk-004", "chunk-005"),
        summary="市场洞察产物:trend（结构化要点）",
        findings_count=2,
        degraded=False,
        degrade_reason="",
        payload=dict(_EXPECTED_STEP_PAYLOADS["market_insight_trend"]),
        structured_ok=True,
    )
    durations: list[float] = []
    for _ in range(25):  # ≥20 轮（7.1 数学口径——ceil(0.95*25)=24）
        started = time.perf_counter()
        compose_step_chain(material)
        durations.append((time.perf_counter() - started) * 1000)
    context["_assembly_durations"] = durations


@then("组装窗口 P95 小于 50 毫秒")
def assembly_window_p95_below_50ms(context: dict[str, Any]) -> None:
    """P95 = sorted(durations)[ceil(0.95*n)-1]（升序排序前提显式——6-1/6-2/6-3 同款）。"""
    import math

    durations = context["_assembly_durations"]
    ordered = sorted(durations)
    p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
    assert p95 < 50.0, f"组装窗口 P95 实测={p95:.3f}ms 期望<50ms（纯内存组装——OD-10 口径）"


@given("10 份独立步骤素材与场景专属 plan_id 就绪")
def ten_materials_and_shared_plan_id_ready(context: dict[str, Any]) -> None:
    """10 素材 + 场景专属 plan_id（R1-F7 消歧——共享单 plan_id，count==10 过滤成立）。"""
    _probe_postgres(context)
    _probe_qdrant(context)
    _probe_minio(context)
    _assemble_json_chain(context)
    context["_chain_assembled"] = True
    context["_plan_id"] = _new_plan_id()
    _register_flow_cleanup(context, context["_plan_id"])


@when("asyncio gather 并发组装归档 10 条思维链")
def gather_ten_concurrent_chains(context: dict[str, Any]) -> None:
    """gather 10（每协程 session_context 独立 scope——R1-F7 gather 共享单
    AsyncSession 并发使用不被 SQLAlchemy 支持）。"""
    from src.application.ports.chain_of_thought_archive import StepChainMaterial
    from src.infrastructure.storage.postgresql.session_context import session_context

    plan_uuid = uuid.UUID(context["_plan_id"])
    materials = []
    for index in range(10):
        materials.append(
            StepChainMaterial(
                stage="market_insight_trend",
                display_name="看趋势",
                role_prefix="以 CEO 宏观趋势判断与 CTO 技术趋势分析的双重视角",
                task=f"{_BLM_TASK}（并发采样 {index}）",
                evidence_count=5,
                tool_slug="PESTEL 分析",
                evidence_refs=(f"chunk-{index}-001",),
                summary=f"市场洞察产物:trend（并发采样 {index}）",
                findings_count=2,
                degraded=False,
                degrade_reason="",
                payload=dict(_EXPECTED_STEP_PAYLOADS["market_insight_trend"]),
                structured_ok=True,
            )
        )

    async def _archive_one(material: Any) -> Any:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(context["_pg_manager"].get_async_engine())
        async with session_context(factory):
            return await context["chain_archive_service"].compose_and_archive_step_chain(
                plan_id=plan_uuid, stage=material.stage, material=material
            )

    async def _gather() -> list[Any]:
        return await asyncio.gather(*(_archive_one(material) for material in materials))

    context["_concurrent_records"] = _run_async(context["_loop"], _gather())


@then("全部归档成功且 archived 为真")
def all_ten_archived_true(context: dict[str, Any]) -> None:
    """gather 全部返回 archived=True（并发无失败）。"""
    records = context["_concurrent_records"]
    assert len(records) == 10, f"并发返回实测={len(records)} 期望=10"
    for record in records:
        assert record is not None, "并发归档返回 None（组装失败降级——正常路径不应出现）"
        assert record.archived, f"stage={record.stage} archived=False（并发归档失败）"


@then("档案库按 plan_id 与 EVIDENCE_PACKAGE 过滤恰 10 行")
def archive_filtered_exactly_ten_rows(context: dict[str, Any]) -> None:
    """count==10（按场景专属 plan_id + archive_type 过滤——R1-F7 口径）。"""
    rows = _query_archive_rows(context, context["_plan_id"])
    assert len(rows) == 10, f"EVIDENCE_PACKAGE 实测={len(rows)} 行 期望=10（并发写入面）"


# ===================================================================
# 收尾：S13 开发完成清单
# ===================================================================


@when("检查 src 与四测试目录交付件")
def check_src_and_test_deliverables(context: dict[str, Any]) -> None:
    """交付件存在性检查（文件级——Then 逐项断言关键符号）。"""
    context["_deliverable_checks"] = True


@then("源码交付件齐全（端口与服务与用例与 CLI 与挂接）")
def src_deliverables_complete(context: dict[str, Any]) -> None:
    """src 完成清单（6-4 新交付五件 + 挂接面关键符号）。"""
    port_file = REPO_ROOT / "src" / "application" / "ports" / "chain_of_thought_archive.py"
    service_file = REPO_ROOT / "src" / "application" / "services" / "chain_of_thought_archive_service.py"
    use_case_file = REPO_ROOT / "src" / "application" / "use_cases" / "get_blm_chain_trace.py"
    assert port_file.exists(), f"端口文件缺失: {port_file}"
    assert service_file.exists(), f"服务文件缺失: {service_file}"
    assert use_case_file.exists(), f"用例文件缺失: {use_case_file}"
    port_text = port_file.read_text(encoding="utf-8")
    port_symbols = (
        "ChainOfThoughtArchiveServicePort",
        "StepChainMaterial",
        "ChainRecord",
        "ChainOfThoughtTraceView",
        "CHAIN_ARCHIVE_KIND",
    )
    for symbol in port_symbols:
        assert symbol in port_text, f"端口文件缺符号 {symbol}"
    service_text = service_file.read_text(encoding="utf-8")
    assert "compose_step_chain" in service_text, "服务文件缺纯函数 compose_step_chain（R1-F13）"
    # 挂接面：BLM 服务尾参 + 投影第七方法 + 图适配器直写行
    blm_path = REPO_ROOT / "src" / "application" / "services" / "blm_planning_service.py"
    blm_text = blm_path.read_text(encoding="utf-8")
    assert "chain_archive_service" in blm_text, "BLM 服务缺尾参注入"
    assert "project_chain_records" in blm_text, "BLM 服务缺投影第七方法"
    graph_path = REPO_ROOT / "src" / "infrastructure" / "agent_orch" / "graphs" / "sp_blm_graph.py"
    graph_text = graph_path.read_text(encoding="utf-8")
    assert "chain_records" in graph_text, "sp_blm_graph 缺 chain_records 直写行"
    cli_text = (REPO_ROOT / "src" / "entrypoints" / "agent_cli.py").read_text(encoding="utf-8")
    assert "chain-query" in cli_text, "CLI 缺 chain-query 子命令"


@then("测试交付件齐全（单测与集成与契约与架构验证与验收）")
def assert_test_deliverables_complete(context: dict[str, Any]) -> None:
    """四测试目录完成清单。"""
    expected_files = (
        REPO_ROOT / "tests" / "unit" / "application" / "test_chain_of_thought_archive_service.py",
        REPO_ROOT / "tests" / "unit" / "application" / "use_cases" / "test_blm_chain_trace_use_case.py",
        REPO_ROOT / "tests" / "unit" / "architecture" / "test_json_chain_of_thought.py",
        REPO_ROOT / "tests" / "integration" / "test_integration_chain_of_thought.py",
        REPO_ROOT / "tests" / "contracts" / "test_port_contract_chain_of_thought.py",
        REPO_ROOT / "tests" / "acceptance" / "test_acceptance_json_chain_of_thought.feature",
        REPO_ROOT / "tests" / "acceptance" / "test_acceptance_json_chain_of_thought.py",
    )
    for path in expected_files:
        assert path.exists(), f"测试交付件缺失: {path}"


@then("四守护文件零改动（事件通道与路由与码段与异常映射）")
def four_guard_files_zero_diff(context: dict[str, Any]) -> None:
    """四守护文件零思维链事件登记/零预留码占用（CR1-F4——原 git diff 断言
    仅在未提交窗口有判别力、提交后恒真失效，转持久缺席断言；@then 绑定串
    与 feature 文本维持锁步不变。token 锚定 6-4 事件名族——不含
    ChainOfThought 大驼峰（既有 445 类是 5-3 合法登记）与裸 chain 子串
    （撞 ToolChainExecuted 既有登记）；485-489 预留码在 6-6 落地时让位更新）。"""
    guard_files = {
        "configs/event_channels.yaml": REPO_ROOT / "configs" / "event_channels.yaml",
        "channel_router.py": REPO_ROOT / "src" / "infrastructure" / "messaging" / "channel_router.py",
        "_code_ranges.py": REPO_ROOT / "src" / "domain" / "exceptions" / "_code_ranges.py",
        "exception_handlers.py": REPO_ROOT / "src" / "interfaces" / "api" / "exception_handlers.py",
    }
    event_tokens = ("chain_of_thought", "ChainArchived", "BlmChain")
    for name, path in guard_files.items():
        content = path.read_text(encoding="utf-8")
        for token in event_tokens:
            assert token not in content, f"{name} 出现思维链事件登记 {token}（零新事件违例）"
        for code in range(485, 490):
            assert f"EXCEPTION_{code}" not in content, (
                f"{name} 出现预留码 EXCEPTION_{code} 占用（零新异常违例——6-6 落地时本断言让位更新）"
            )
