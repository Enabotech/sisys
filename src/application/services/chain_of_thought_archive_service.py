"""应用层思维链归档服务（Story 6-4 — JSON 思维链输出）

ChainOfThoughtArchiveService——BLM 面思维链「确定性组装 → EVIDENCE_PACKAGE
归档 → 决策追溯查询」编排实现。R2 规则：组合注入 StrategicArchiveService
（3-10 归档编排零改动复用——archive_plan 五步序 L2 强制→L3 降级→L4 WORM
强制→L5 降级→引用回写→ArchiveCreated）+ L4ObjectPort（include_blob 深度
解引用通道——R1-F6 双注入）。

组装公式冻结（Task 0.2 唯一真源——三型分列 R1-F3）：
- input_summary：六子/gap=f"{display_name}｜{role_prefix}｜任务: {task[:80]}｜
  检索证据 {n} 条"；synthesis=f"市场洞察综合｜CMO｜任务: {task[:80]}｜
  综合结论 {n} 项"（SYNTHESIS_* 模块常量——语义配置表无 synthesis 行）。
- reflection：六子=f"步骤产出: {summary[:120]}；要点 {n} 项{降级后缀}"；
  gap 同构换「根因 {n} 项」；synthesis=f"综合结论 {n} 项；降级输入 {n} 项
  {降级后缀}"（降级是决策过程的一部分——降级信息入反思）。
- constraints_check：六子/gap 同构三段（结构化校验段按型替换首段 + 证据
  充分性 n>=3 + 降级标记）；synthesis 无检索面无证据充分性段（结论产出
  判定 + 降级输入计数 + 降级标记）。
- final_answer：json.dumps(payload, ensure_ascii=False)（payload 三态：
  产物原样/降级信封——R2-F2 部分降级产物在位原样）。
- tools_used：(tool_slug,) if tool_slug else ()（单数 slug 包装——R1-F2
  执行轨迹第三返回值，每步至多 1 项）。

降级语义（OD-5——可观测面非流程面）：
- 组装失败 242 → 捕获改写 445（missing_fields——5-3 package_evidence
  :386-393 同款先例）→ warning 日志 → 返回 None（chain 缺席台账）。
- 归档 284（L2/L4 强制环节/发布失败）→ ChainRecord(archived=False) +
  warning 日志 → 返回非 None（台账可见可数）。

Run with（单测）:
    SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit/application/test_chain_of_thought_archive_service.py -v
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from src.application.ports.chain_of_thought_archive import (
    CHAIN_ARCHIVE_KIND,
    ChainOfThoughtArchiveServicePort,
    ChainOfThoughtTraceView,
    ChainRecord,
    StepChainMaterial,
)
from src.application.services.strategic_archive_service import StrategicArchiveService
from src.domain.entities.strategic_archive import ArchiveType
from src.domain.exceptions import (
    ArchiveStorageError,
    ChainOfThoughtValidationError,
    EntityValidationError,
)
from src.domain.ports.archive_repository import ArchiveQuery
from src.domain.ports.l4_object import L4ObjectPort
from src.domain.value_objects.chain_of_thought import ChainOfThought

logger = logging.getLogger(__name__)

#: L4 WORM blob 深度解引用的 bucket 类型（与 strategic_archive_service.L4_BUCKET_TYPE 同源）
_ARCHIVE_EVIDENCE_BUCKET: str = "archive-evidence"

#: 追溯查询显式 limit（R1-F17——ArchiveQuery 默认 20，单 run 8 条满量+余量钦定 50）
_TRACE_QUERY_LIMIT: int = 50

#: archived_at 可空列的排序下界回落（epoch——None 历史脏数据形态排最前）
_EPOCH_FLOOR = datetime(1970, 1, 1, tzinfo=UTC)


def compose_step_chain(material: StepChainMaterial) -> ChainOfThought:
    """纯组装函数（R1-F13——模块级、零 I/O 零 LLM，AC-7 P95 采样对象）。

    三型分列公式（Task 0.2 冻结表——stage 锚判型）：
    - market_insight_synthesis → synthesis 型（模块常量语义/结论计数/无证据段）
    - performance_gap → gap 型（根因计数/四字段完整性段）
    - 其余（market_insight_*）→ 六子型（要点计数/值域校验段）

    Args:
        material: 组装素材（挂接段构造——三型分列字段）。

    Returns:
        ChainOfThought VO（__post_init__ 242 校验——素材缺陷即抛）。

    Raises:
        EntityValidationError: EXCEPTION_242——素材缺陷（tool_slug 纯空白串
            经 VO 元素级守卫拒绝——R2-F3 唯一可达通道；四文本字段恒非空白、
            payload 恒非空由素材源受控保证）。
    """
    task_excerpt = material.task[:80]
    degrade_suffix = f"；降级: {material.degrade_reason}" if material.degraded else "；流程正常"
    if material.stage == "market_insight_synthesis":
        input_summary = (
            f"{material.display_name}｜{material.role_prefix}｜任务: {task_excerpt}｜综合结论 {material.findings_count} 项"
        )
        reflection = f"综合结论 {material.findings_count} 项；降级输入 {material.degraded_inputs_count} 项{degrade_suffix}"
        constraints_check = (
            f"结论产出判定: {'通过' if material.structured_ok else '缺失'}；"
            f"降级输入: {material.degraded_inputs_count} 项；降级标记: {material.degraded}"
        )
    elif material.stage == "performance_gap":
        input_summary = (
            f"{material.display_name}｜{material.role_prefix}｜任务: {task_excerpt}｜检索证据 {material.evidence_count} 条"
        )
        reflection = f"步骤产出: {material.summary[:120]}；根因 {material.findings_count} 项{degrade_suffix}"
        constraints_check = (
            f"四字段产物完整性: {'通过' if material.structured_ok else '缺失'}；"
            f"证据充分性: {'充足' if material.evidence_count >= 3 else '不足'}；降级标记: {material.degraded}"
        )
    else:
        input_summary = (
            f"{material.display_name}｜{material.role_prefix}｜任务: {task_excerpt}｜检索证据 {material.evidence_count} 条"
        )
        reflection = f"步骤产出: {material.summary[:120]}；要点 {material.findings_count} 项{degrade_suffix}"
        constraints_check = (
            f"结构化输出值域校验: {'通过' if material.structured_ok else '缺失'}；"
            f"证据充分性: {'充足' if material.evidence_count >= 3 else '不足'}；降级标记: {material.degraded}"
        )
    tools_used = (material.tool_slug,) if material.tool_slug else ()
    return ChainOfThought(
        input_summary=input_summary,
        reflection=reflection,
        tools_used=tools_used,
        constraints_check=constraints_check,
        final_answer=json.dumps(material.payload, ensure_ascii=False),
    )


class ChainOfThoughtArchiveService(ChainOfThoughtArchiveServicePort):
    """思维链归档服务（组装+归档单步 / 追溯查询——端口两方法实现）。"""

    def __init__(
        self,
        *,
        archive_service: StrategicArchiveService,
        object_storage: L4ObjectPort | None = None,
    ) -> None:
        """初始化思维链归档服务（R1-F6 双注入）。

        Args:
            archive_service: 战略档案编排服务（3-10 归档链零改动复用）。
            object_storage: L4 对象存储端口（include_blob 深度解引用通道；
                None 时 blob 槽位置 None 不抛——R2-F4）。
        """
        self._archive_service = archive_service
        self._object_storage = object_storage

    async def compose_and_archive_step_chain(
        self,
        plan_id: uuid.UUID,
        stage: str,
        material: StepChainMaterial,
    ) -> ChainRecord | None:
        """组装并归档单步思维链（确定性组装 + EVIDENCE_PACKAGE 归档 + 双降级）。

        Args:
            plan_id: 规划任务标识（UUID——归档行 plan_id 锚）。
            stage: 步骤 stage 锚（STAGE_VALUE_DOMAIN 八值之一）。
            material: 组装素材（挂接段构造——三型分列）。

        Returns:
            ChainRecord（archived=True 归档成功 / archived=False 归档失败
            284 降级台账）；None（组装失败 445 降级——chain 缺席）。
        """
        try:
            chain = compose_step_chain(material)
        except EntityValidationError as error:
            # 三层次序②（5-3 :386-393 同款先例）：VO 构造守卫 242 → 改写 445
            # 携 missing_fields；OD-5 降级不阻断——warning 台账 + chain 缺席。
            missing = error.context.get("field")
            validation_error = ChainOfThoughtValidationError(
                agent_id="",
                missing_fields=(missing,) if isinstance(missing, str) else (),
                cause=error,
            )
            logger.warning(
                "思维链组装失败（%s 降级——chain 缺席台账，missing_fields=%s）[stage=%s plan_id=%s]: %s",
                validation_error.code,
                validation_error.context.get("missing_fields"),
                stage,
                plan_id,
                validation_error.message,
            )
            return None

        chain_dict: dict[str, Any] = {
            "input_summary": chain.input_summary,
            "reflection": chain.reflection,
            "tools_used": list(chain.tools_used),
            "constraints_check": chain.constraints_check,
            "final_answer": chain.final_answer,
        }
        decision_basis: dict[str, Any] = {
            "kind": CHAIN_ARCHIVE_KIND,
            "stage": stage,
            "chain": chain_dict,
            "degraded": material.degraded,
        }
        assumptions: dict[str, Any] = {
            "tools_used": list(chain.tools_used),
            "evidence_refs": list(material.evidence_refs),
        }
        evidence_blob = json.dumps({"stage": stage, "chain": chain_dict}, ensure_ascii=False, sort_keys=True).encode("utf-8")
        try:
            archive = await self._archive_service.archive_plan(
                plan_id=plan_id,
                plan_type="SP",
                archive_type=ArchiveType.EVIDENCE_PACKAGE,
                assumptions=assumptions,
                decision_basis=decision_basis,
                evidence_blob=evidence_blob,
            )
        except ArchiveStorageError as error:
            logger.warning(
                "思维链归档失败（284 降级不阻断——台账 archived=False）[stage=%s plan_id=%s]: %s",
                stage,
                plan_id,
                error,
            )
            return ChainRecord(stage=stage, chain=chain, archived=False, archive_id="")
        return ChainRecord(stage=stage, chain=chain, archived=True, archive_id=str(archive.archive_id))

    async def query_chain_trace(
        self,
        plan_id: uuid.UUID,
        include_blob: bool = False,
    ) -> ChainOfThoughtTraceView:
        """决策追溯查询（档案清单 → 视图组装；round-trip 重构 VO + 可选 blob 解引用）。

        Args:
            plan_id: 规划任务标识（UUID）。
            include_blob: 是否深度解引用 L4 WORM blob（默认 False）。

        Returns:
            追溯视图（archived_at 升序——执行序；空档案返回空清单 total=0）。
        """
        archives = await self._archive_service.query_archive(
            ArchiveQuery(plan_id=plan_id, archive_type=ArchiveType.EVIDENCE_PACKAGE, limit=_TRACE_QUERY_LIMIT)
        )
        ordered = sorted(
            (archive for archive in archives if (archive.decision_basis or {}).get("kind") == CHAIN_ARCHIVE_KIND),
            # archived_at 可空列——None 回落 epoch 下界（kind 过滤后行均为归档行，
            # None 仅历史脏数据形态，排序稳定性优先）
            key=lambda archive: archive.archived_at or _EPOCH_FLOOR,
        )
        records: list[dict[str, Any]] = []
        for archive in ordered:
            basis = archive.decision_basis or {}
            chain_dict = basis.get("chain") or {}
            # R1-F9：PG JSONB 读回 tools_used 为 list，VO tuple 类型守卫必拒——
            # 重构前显式 tuple() 归一。
            chain = ChainOfThought(
                input_summary=str(chain_dict.get("input_summary", "")),
                reflection=str(chain_dict.get("reflection", "")),
                tools_used=tuple(chain_dict.get("tools_used") or ()),
                constraints_check=str(chain_dict.get("constraints_check", "")),
                final_answer=str(chain_dict.get("final_answer", "")),
            )
            blob_content = await self._dereference_blob(archive.blob_ref) if include_blob else None
            records.append(
                {
                    "stage": str(basis.get("stage", "")),
                    "chain": chain,
                    "archive_id": str(archive.archive_id),
                    "degraded": bool(basis.get("degraded", False)),
                    "blob_content": blob_content,
                }
            )
        return ChainOfThoughtTraceView(
            plan_id=str(plan_id),
            records=records,
            total=len(records),
            archived_count=sum(1 for record in records if record["archive_id"]),
        )

    async def _dereference_blob(self, blob_ref: str | None) -> dict[str, Any] | None:
        """L4 WORM blob 深度解引用（流式下载累积 + JSON 反序列化——R1-F6 通道）。

        L4ObjectPort.retrieve 是同步 def 返回 AsyncIterator[bytes]（流式防
        OOM）——async for 累积。解引用失败（对象缺失/网络异常）与通道缺席
        （object_storage=None）同形态：warning + 返回 None（查询面幂等读语义
        对齐——不抛异常，R2-F4）。

        Args:
            blob_ref: 对象键（归档行 blob_ref 列；None 无对象）。

        Returns:
            blob JSON dict；无对象/通道缺席/失败时 None。
        """
        if not blob_ref:
            return None
        if self._object_storage is None:
            logger.warning("include_blob=True 但 object_storage 未注入——blob_content 槽位置 None（R2-F4 降级不抛）")
            return None
        try:
            chunks: list[bytes] = []
            async for chunk in self._object_storage.retrieve(bucket_type=_ARCHIVE_EVIDENCE_BUCKET, object_key=blob_ref):
                chunks.append(chunk)
            blob_data: dict[str, Any] = json.loads(b"".join(chunks).decode("utf-8"))
            return blob_data
        except Exception as error:
            logger.warning("blob 解引用失败（blob_content=None）[blob_ref=%s]: %s", blob_ref, error)
            return None


__all__ = ["ChainOfThoughtArchiveService", "compose_step_chain"]
