"""溯源树聚合查询服务（Story 6-7——四段编排）

四段编排（TraceabilityTreePort 实现——纯读侧聚合，零事件发布/零状态变更）：
    ① 收集段：query_archive(ArchiveQuery(plan_id, EVIDENCE_PACKAGE, limit=1000))
       → kind 过滤（CHAIN_ARCHIVE_KIND 常量消费——6-5b 收集段同款）
    ② 判 run 段：stage 分组 last-write-wins（并列以 archive_id 决胜全序——DR1-11；
       None 行回落 epoch 永不获胜——6-4 _EPOCH_FLOOR 同款）+ 结论层 synthesis 提取
    ③ 切片段（depth>=3）：l3_vector.get_point 逐 chunk 解析（point_missing 降级）
    ④ 文档段（depth=4）：document_repository.find 去重缓存（每 document_id 恰一次
       ——AC-1）+ chunks page 匹配（6-5b :360-371 同款复刻）+ 跳转载荷组装

链路蓝本：6-5b 引文三段链（query_archive → get_point → find 同端口同顺序）；
降级哲学树形版——树整体不因单点依赖失效失败（节点 status 承载），顶层
query_archive 异常空树降级（build_degraded=True 与真空树分立——读模型诚实性）。

性能窗口注记（OD-7）：串行循环（6-5b 引文链同款先例）——~40 点查×毫秒级 + M 次
find ≈100-200ms 余量成立；触发器注记：P95 逼近 300ms 门禁或 evidence_refs 契约
上限放开时改 asyncio.gather（并发需注意 AsyncSession 不共享——6-6 R1 教训）。
get_point 不做跨 stage 调用级去重：树语义节点每路径独立，与 find 去重分立是
刻意取舍（DR1-23）。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from src.application.ports.chain_of_thought_archive import CHAIN_ARCHIVE_KIND
from src.application.ports.traceability_tree import (
    ChunkNode,
    ConclusionNode,
    DocumentNode,
    StageNode,
    TraceabilityTree,
)
from src.application.services.agent_workflow_context import MVP_TENANT_ID
from src.application.services.blm_planning_prompts import MARKET_INSIGHT_STEP_CONFIG, PERFORMANCE_GAP_CONFIG
from src.application.services.strategic_archive_service import StrategicArchiveService
from src.domain.entities.strategic_archive import ArchiveType
from src.domain.ports.archive_repository import ArchiveQuery
from src.domain.ports.document_repository import DocumentQuery, DocumentRepositoryPort
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.value_objects.blm_phases import MarketInsightStep

logger = logging.getLogger(__name__)

_EPOCH_FLOOR = datetime(1970, 1, 1, tzinfo=UTC)
_EXCERPT_MAX_CHARS = 300
_REFLECTION_EXCERPT_CHARS = 200
_TREE_QUERY_LIMIT = 1000
_TREE_TITLE = "BLM 战略规划溯源"
_SYNTHESIS_STAGE = "market_insight_synthesis"
_RAW_DOCUMENTS_BUCKET = "raw-documents"

# 流程规范序（DR3-1）：performance_gap 在前 + 六子按 MARKET_INSIGHT_STEP_CONFIG
# 枚举序（与 display_name 三源同族常量——零新常量；服务必须重排禁透传遍历序）
_STAGE_CANONICAL_ORDER: tuple[str, ...] = ("performance_gap",) + tuple(
    f"market_insight_{step.value}" for step in MarketInsightStep
)


def _display_name_of(stage: str) -> str:
    """display_name 三源拼装（无单一映射表——DR1-22）.

    performance_gap 独立常量 PERFORMANCE_GAP_CONFIG；六子按 MARKET_INSIGHT_STEP_CONFIG
    dict 枚举键匹配；synthesis 归结论层不在本函数值域（调用前已过滤）。
    """
    if stage == "performance_gap":
        return str(PERFORMANCE_GAP_CONFIG.display_name)
    step_key = stage.removeprefix("market_insight_")
    for step, config in MARKET_INSIGHT_STEP_CONFIG.items():
        if step.value == step_key:
            return str(config.display_name)
    return stage


def _as_dict(value: Any) -> dict[str, Any]:
    """JSONB 外部可写面守卫：非 dict 脏形态（如 JSON array）降空 dict.

    assumptions/decision_basis 是 PG JSONB 列（外部可写面——6-5b metadata 守卫同意识）：
    truthy 非 dict 经 `or {}` 形态不降级而直接 AttributeError 逃逸，违反端口
    「本方法不抛业务异常」——六处消费位统一经本守卫（kind 不可读的行按非思维链
    候选排除出 total，assumptions 不可读按零证据降级——DR1-12/DR3-4 语义自洽）。
    """
    return value if isinstance(value, dict) else {}


def _parse_final_answer(raw: Any) -> dict[str, Any] | None:
    """chain.final_answer JSON 解析（非 JSON/非 dict 返 None——降级分支统一入口）."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _synthesis_summary(synthesis_row: Any) -> str:
    """结论层 summary：conclusions 联展（"\\n".join 保序——DR3-8；非 list/空/解析失败降空串）."""
    if synthesis_row is None:
        return ""
    chain = _as_dict(synthesis_row.decision_basis).get("chain")
    if not isinstance(chain, dict):
        return ""
    payload = _parse_final_answer(chain.get("final_answer"))
    if payload is None:
        return ""
    conclusions = payload.get("conclusions")
    if isinstance(conclusions, list) and conclusions:
        return "\n".join(str(item) for item in conclusions)
    return ""


def _match_page(chunks_meta: Any, chunk_id: str) -> int | None:
    """metadata["chunks"] 按 chunk_id 匹配 page_start（6-5b :360-371 同款复刻）.

    脏形态守卫降 None（本 Story VO 契约 int|None——非 6-5b CitationEntry 的 0 值
    语义，防复刻漂移）；匹配到但页码非正整数同样降 None；不在列表降 None。
    """
    if not isinstance(chunks_meta, list):
        return None
    for chunk_meta in chunks_meta:
        if not isinstance(chunk_meta, dict):
            continue
        if str(chunk_meta.get("chunk_id", "")) == str(chunk_id):
            raw_page = chunk_meta.get("page_start")
            if isinstance(raw_page, int) and not isinstance(raw_page, bool) and raw_page > 0:
                return raw_page
            return None
    return None


class TraceabilityTreeService:
    """溯源树聚合查询服务（四段编排——TraceabilityTreePort 实现 v1.0.0）.

    构造注入三既有依赖（R2 应用端口组合注入基础端口——StrategicArchiveService
    是具体应用类注入：仓内无同名 Port，组合根 interface 面即具体类——6-5b
    pdf_report_generation_service 先例）+ search_collection/tenant_id 构造参数
    （组合根 env 传导单源——BLM_SEARCH_COLLECTION，6-1 :1592 先例；单租户口径
    MVP_TENANT_ID，6-5b 构造注入先例）。
    """

    def __init__(
        self,
        *,
        strategic_archive_service: StrategicArchiveService,
        l3_vector: L3VectorPort,
        document_repository: DocumentRepositoryPort,
        search_collection: str = "documents",
        tenant_id: str = str(MVP_TENANT_ID),
    ) -> None:
        """初始化四段编排依赖.

        Args:
            strategic_archive_service: 归档查询服务（query_archive 只读消费——DR1-8）.
            l3_vector: 向量存储端口（get_point 点查）.
            document_repository: 文档仓储端口（find + DocumentQuery）.
            search_collection: Qdrant collection 名（组合根 env 传导单源）.
            tenant_id: 租户 ID（单租户口径默认值）.
        """
        self._strategic_archive_service = strategic_archive_service
        self._l3_vector = l3_vector
        self._document_repository = document_repository
        self._search_collection = search_collection
        self._tenant_id = tenant_id

    async def build_trace_tree(self, *, plan_id: str, depth: int = 4) -> TraceabilityTree:
        """按 plan_id 构建四层溯源树（depth 懒加载——本方法不抛业务异常）.

        Raises:
            无——空计划幂等读返回空树；依赖失效走节点 status 降级；顶层
            query_archive 异常空树降级（build_degraded=True）。畸形输入与
            depth 越域守卫归用例层（服务层不重复守卫——6-6 先例一致）。
            哨兵复用注记：直调服务传非 UUID 时 uuid.UUID 的 ValueError 落入
            顶层容错 → build_degraded=True 空树（守卫归用例层，正常路径不可达）。
        """
        # ① 收集段：query_archive + kind 过滤（顶层容错——空树与真空树分立）
        try:
            archives = await self._strategic_archive_service.query_archive(
                ArchiveQuery(
                    plan_id=uuid.UUID(plan_id),
                    archive_type=ArchiveType.EVIDENCE_PACKAGE,
                    limit=_TREE_QUERY_LIMIT,
                )
            )
        except Exception as error:
            logger.warning("溯源树归档查询失败（空树降级）: plan_id=%s error=%s", plan_id, error)
            return self._empty_tree(plan_id, build_degraded=True)
        chain_rows = [row for row in archives if _as_dict(row.decision_basis).get("kind") == CHAIN_ARCHIVE_KIND]
        total_archives = len(chain_rows)

        # ② 判 run 段：stage 分组 last-write-wins（并列 archive_id 决胜——DR1-11）
        groups: dict[str, Any] = {}
        for row in chain_rows:
            stage = str(_as_dict(row.decision_basis).get("stage") or "")
            row_key = (row.archived_at or _EPOCH_FLOOR, row.archive_id)
            if stage not in groups:
                groups[stage] = row
                continue
            incumbent = groups[stage]
            incumbent_key = (incumbent.archived_at or _EPOCH_FLOOR, incumbent.archive_id)
            if row_key > incumbent_key:
                groups[stage] = row
        # 分析层 = 七值域交分组键（脏 stage 行读侧过滤不抛——DR3-4；流程规范序 DR3-1）
        analysis_stages = [stage for stage in _STAGE_CANONICAL_ORDER if stage in groups]
        synthesis_row = groups.get(_SYNTHESIS_STAGE)
        adopted_archives = len(analysis_stages) + (1 if synthesis_row is not None else 0)

        # ③/④ 切片段与文档段（depth 分层懒加载）
        document_cache: dict[str, Any] = {}
        stage_nodes: list[StageNode] = []
        for stage in analysis_stages:
            adopted_row = groups[stage]
            chunk_children: tuple[ChunkNode, ...] = ()
            if depth >= 3:
                chunk_children = await self._resolve_chunks(adopted_row, depth, document_cache)
            stage_nodes.append(self._build_stage_node(adopted_row, chunk_children))

        degraded_stages = self._rollup_degraded_stages(stage_nodes)
        root = ConclusionNode(
            plan_id=plan_id,
            title=_TREE_TITLE,
            summary=_synthesis_summary(synthesis_row),
            stage_count=len(analysis_stages),
            children=tuple(stage_nodes) if depth >= 2 else (),
        )
        return TraceabilityTree(
            plan_id=plan_id,
            root=root,
            adopted_archives=adopted_archives,
            total_archives=total_archives,
            degraded_stages=degraded_stages,
            build_degraded=False,
            generated_at=datetime.now(UTC).isoformat(),
        )

    async def _resolve_chunks(self, adopted_row: Any, depth: int, document_cache: dict[str, Any]) -> tuple[ChunkNode, ...]:
        """③ 切片段：逐 chunk get_point 解析（point_missing 降级两分支——None/异常）."""
        refs = _as_dict(adopted_row.assumptions).get("evidence_refs")
        if not isinstance(refs, (list, tuple)):
            refs = []
        chunk_nodes: list[ChunkNode] = []
        for chunk_id in refs:
            chunk_id_str = str(chunk_id)
            try:
                point = await self._l3_vector.get_point(self._search_collection, chunk_id_str)
            except Exception as error:
                logger.warning("溯源树切片解析失败（point_missing 降级）: chunk_id=%s error=%s", chunk_id_str, error)
                point = None
            if point is None:
                chunk_nodes.append(
                    ChunkNode(
                        chunk_id=chunk_id_str,
                        content_excerpt="",
                        page_start=None,
                        page_end=None,
                        status="point_missing",
                    )
                )
                continue
            payload = point.get("payload") if isinstance(point, dict) else None
            if not isinstance(payload, dict):
                payload = {}
            content = str(payload.get("content") or "")
            chunk_nodes.append(
                ChunkNode(
                    chunk_id=chunk_id_str,
                    content_excerpt=content[:_EXCERPT_MAX_CHARS],
                    page_start=_positive_int(payload.get("page_start")),
                    page_end=_positive_int(payload.get("page_end")),
                    status="resolved",
                    children=await self._resolve_document(payload, chunk_id_str, depth, document_cache),
                )
            )
        return tuple(chunk_nodes)

    async def _resolve_document(
        self, payload: dict[str, Any], chunk_id: str, depth: int, document_cache: dict[str, Any]
    ) -> tuple[DocumentNode, ...]:
        """④ 文档段：find 去重缓存（每 document_id 恰一次）+ page 匹配 + 跳转载荷组装.

        口径注记：payload 缺 document_id（脏点）时不产 DocumentNode（chunk 保持
        resolved、无文档子节点——「无引用」与 document_missing 分立，production
        点恒带 document_id）；version 脏值（非正整数）降 1 与 document_missing
        占位 0 是两态口径（缺失=0/脏=1——status 已区分两态，VO int 类型必须满足）。
        """
        if depth < 4:
            return ()
        document_id_raw = payload.get("document_id")
        if not document_id_raw:
            return ()
        document_id = str(document_id_raw)
        if document_id not in document_cache:
            try:
                document_cache[document_id] = await self._document_repository.find(
                    DocumentQuery(tenant_id=self._tenant_id, document_id=uuid.UUID(document_id))
                )
            except Exception as error:
                logger.warning("溯源树文档解析失败（document_missing 降级）: document_id=%s error=%s", document_id, error)
                document_cache[document_id] = None
        document = document_cache[document_id]
        if document is None:
            return (
                DocumentNode(
                    document_id=document_id,
                    filename="",
                    version=0,
                    page=None,
                    object_key=None,
                    bucket=_RAW_DOCUMENTS_BUCKET,
                    bbox=None,
                    status="document_missing",
                ),
            )
        metadata = getattr(document, "metadata", None)
        metadata = metadata if isinstance(metadata, dict) else {}
        page = _match_page(metadata.get("chunks"), chunk_id)
        object_key_raw = metadata.get("storage_object_key")
        object_key = str(object_key_raw) if object_key_raw else None
        bbox_raw = payload.get("bbox")
        return (
            DocumentNode(
                document_id=document_id,
                filename=str(getattr(document, "filename", "") or ""),
                version=_positive_int(getattr(document, "version", 1)) or 1,
                page=page,
                object_key=object_key,
                bucket=_RAW_DOCUMENTS_BUCKET,
                bbox=bbox_raw if isinstance(bbox_raw, dict) else None,
                status="resolved",
                jump_ready=bool(object_key) and page is not None,
            ),
        )

    def _build_stage_node(self, adopted_row: Any, chunk_children: tuple[ChunkNode, ...]) -> StageNode:
        """②分析层节点构造（三元组承载 + 三键数据源链——DR1-14）."""
        decision_basis = _as_dict(adopted_row.decision_basis)
        chain = decision_basis.get("chain")
        chain = chain if isinstance(chain, dict) else {}
        stage = str(decision_basis.get("stage") or "")
        payload = _parse_final_answer(chain.get("final_answer"))
        # summary 三型分支：六子取 payload.summary（空串视为无效回退 input_summary——空串无信息量）/
        # gap 无 summary 降 chain.input_summary / 解析失败同降
        payload_summary = payload.get("summary") if payload is not None else None
        summary = (
            str(payload_summary)
            if isinstance(payload_summary, str) and payload_summary
            else str(chain.get("input_summary") or "")
        )
        # degrade_reason 取 payload 键缺省空串（与 degraded 布尔独立取值——DR1-14）
        degrade_reason_raw = payload.get("degrade_reason") if payload is not None else None
        degrade_reason = degrade_reason_raw if isinstance(degrade_reason_raw, str) else ""
        tools_raw = chain.get("tools_used")
        tools_used = tuple(str(item) for item in tools_raw) if isinstance(tools_raw, (list, tuple)) else ()
        reflection_raw = chain.get("reflection")
        reflection_excerpt = reflection_raw[:_REFLECTION_EXCERPT_CHARS] if isinstance(reflection_raw, str) else ""
        refs = _as_dict(adopted_row.assumptions).get("evidence_refs")
        evidence_count = len(refs) if isinstance(refs, (list, tuple)) else 0
        return StageNode(
            stage=stage,
            display_name=_display_name_of(stage),
            summary=summary,
            degraded=decision_basis.get("degraded") is True,
            degrade_reason=degrade_reason,
            tools_used=tools_used,
            reflection_excerpt=reflection_excerpt,
            evidence_count=evidence_count,
            children=chunk_children,
        )

    @staticmethod
    def _rollup_degraded_stages(stage_nodes: list[StageNode]) -> tuple[str, ...]:
        """⑤degraded_stages 上卷：含 ≥1 非 resolved 后代节点的采纳 stage 值元组（升序去重）."""
        degraded: set[str] = set()
        for stage_node in stage_nodes:
            for chunk_node in stage_node.children:
                statuses = [chunk_node.status, *(doc.status for doc in chunk_node.children)]
                if any(status != "resolved" for status in statuses):
                    degraded.add(stage_node.stage)
        return tuple(sorted(degraded))

    @staticmethod
    def _empty_tree(plan_id: str, *, build_degraded: bool) -> TraceabilityTree:
        """顶层降级空树构造（build_degraded=True 分立哨兵；真空树走正常构造路径全零自然态）."""
        root = ConclusionNode(plan_id=plan_id, title=_TREE_TITLE, summary="", stage_count=0, children=())
        return TraceabilityTree(
            plan_id=plan_id,
            root=root,
            adopted_archives=0,
            total_archives=0,
            degraded_stages=(),
            build_degraded=build_degraded,
            generated_at=datetime.now(UTC).isoformat(),
        )


def _positive_int(raw: Any) -> int | None:
    """正整数守卫（bool 排除——6-5b 脏形态守卫同族）."""
    if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
        return raw
    return None
