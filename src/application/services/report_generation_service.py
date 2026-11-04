"""报告生成服务（Story 6-5a——双源聚合 + 五段编排）。

五段编排（AC-1）：①chain 归档主源聚合（query_chain_trace）→ ②latest 快照
辅源（容错）→ ③领域渲染纯函数 → ④L0 写 + L2 元数据行 → ⑤ReportGenerated
事件发布。

服务无状态约束（AC-7 并发）：SINGLETON 实例并发共享——实现不持每次调用的
可变实例态；附录 B 登记清单是单次调用局部累积（函数内列表随返回丢弃）。

save 与 publish 分属独立会话**无共同事务**（发布失败处置按 AC-5 宽容语义
warning 不回滚——L0/L2 是报告真相源、事件是通知面）。
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from src.application.ports.blm_planning import BLM_PLANNING_SESSION_PREFIX
from src.application.ports.chain_of_thought_archive import (
    SYNTHESIS_DISPLAY_NAME,
    ChainOfThoughtArchiveServicePort,
)
from src.application.ports.report_generation import (
    EXPECTED_REPORT_STAGES,
    REPORT_FILE_MEMORY_TYPE,
    REPORT_TITLE_TEMPLATE,
)
from src.application.services.blm_planning_prompts import (
    MARKET_INSIGHT_STEP_CONFIG,
    PERFORMANCE_GAP_CONFIG,
)
from src.domain.entities.strategic_report import ReportType, StrategicReport
from src.domain.events.workflow_events import ReportGenerated
from src.domain.exceptions import ReportGenerationError, ReportStorageError
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.l0_storage import L0StoragePort
from src.domain.ports.report_repository import ReportRepositoryProtocol
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
from src.domain.services.markdown_report_renderer import render_markdown_report
from src.domain.value_objects.markdown_report import (
    MarkdownReportDocument,
    ReportBlock,
    ReportSection,
)

__all__ = ["ReportGenerationService"]

logger = logging.getLogger(__name__)

#: 降级信封态键集（三态判定②——键集 ⊆ 此二键且非空即为信封）
_ENVELOPE_KEYS: frozenset[str] = frozenset({"degraded", "degrade_reason"})

#: 降级原因固定兜底文案（payload 无 degrade_reason 键时——禁解析 reflection 文本）
_DEGRADE_REASON_FALLBACK: str = "降级（原因未随归档行结构化持久化）"

#: 缺行 callout 固定文案
_MISSING_DATA_TEXT: str = "该步骤归档记录不可用"

#: gap 四小节固定标题（冻结表 1.1~1.4）
_GAP_SUBSECTIONS: tuple[tuple[str, str], ...] = (
    ("1.1 财务差距", "financial_gap"),
    ("1.2 运营差距", "operational_gap"),
    ("1.3 根因分析", "root_causes"),
    ("1.4 业务组合健康度", "portfolio_health"),
)

#: 正文 H3 小节总数（gap 4 + 六子 6 + synthesis 1 = 11——CR1-F7 派生化：
#: 与 EXPECTED_REPORT_STAGES 同源「配置增步自动跟随」原则，禁字面量钉死）
_SECTION_COUNT: int = len(_GAP_SUBSECTIONS) + len(MARKET_INSIGHT_STEP_CONFIG) + 1

#: synthesis 小节编号（第 2 章六子之后——CR1-F7 派生化：六子增步自动跟随防撞号）
_SYNTHESIS_SUBNUMBER: int = len(MARKET_INSIGHT_STEP_CONFIG) + 1

#: PESTEL 表行标签（维度列——description 中文语义源）
_PESTEL_ROWS: tuple[tuple[str, str], ...] = (
    ("政治", "pestel_political"),
    ("经济", "pestel_economic"),
    ("社会", "pestel_social"),
    ("技术", "pestel_technological"),
    ("环境", "pestel_environmental"),
    ("法律", "pestel_legal"),
)

#: 五力表行标签（五力列——description 中文语义源）
_FIVE_FORCES_ROWS: tuple[tuple[str, str], ...] = (
    ("供应商议价能力", "five_forces_supplier_power"),
    ("购买者议价能力", "five_forces_buyer_power"),
    ("新进入者威胁", "five_forces_new_entrants"),
    ("替代品威胁", "five_forces_substitutes"),
    ("现有竞争者强度", "five_forces_rivalry"),
)

#: 加粗行标签组（三组 bullet_list 前置——不开 H4 的承载形态）
_BULLETED_FIELD_GROUPS: dict[str, tuple[tuple[str, str], ...]] = {
    "market_customer": (
        ("客户细分画像", "customer_segments"),
        ("需求优先级矩阵（$APPEALS）", "demand_priority_matrix"),
        ("价值主张地图", "value_proposition_map"),
    ),
    "self": (
        ("内部能力清单", "internal_capabilities"),
        ("核心能力 VRIO 评估", "vrio_assessment"),
        ("资源约束分析", "resource_constraints"),
    ),
    "opportunity": (
        ("机会清单", "opportunity_list"),
        ("机会优先级排序", "priority_ranking"),
        ("增长路径图（安索夫矩阵路径）", "growth_path"),
    ),
    "opportunity_gap": (
        ("机会差距量化报告要点", "gap_quantification"),
        ("能力-机会匹配矩阵", "capability_match_matrix"),
        ("差距弥合策略", "closure_strategies"),
    ),
}

#: 附录 A 时间线表头（五列——summary_excerpt 显式省略）
_TIMELINE_HEADERS: tuple[str, ...] = ("步骤", "开始", "完成", "状态", "降级")

#: 附录 B 表头（三列——类型值域 {[数据缺失],[降级]} 两类全收）
_APPENDIX_B_HEADERS: tuple[str, ...] = ("类型", "步骤", "原因")


class ReportGenerationService:
    """报告生成服务（R2 具体应用端口实现——五依赖组合注入）。"""

    def __init__(
        self,
        *,
        chain_archive_service: ChainOfThoughtArchiveServicePort,
        snapshot_repository: SnapshotRepositoryProtocol,
        l0_storage: L0StoragePort,
        report_repository: ReportRepositoryProtocol,
        event_publisher: EventPublisher,
    ) -> None:
        """初始化报告生成服务（五依赖全 keyword-only 注入）。

        Args:
            chain_archive_service: 思维链归档服务（聚合主源）。
            snapshot_repository: 快照仓储（latest 辅源）。
            l0_storage: L0 文件存储端口（报告文件写）。
            report_repository: 报告仓储（L2 元数据行）。
            event_publisher: 事件发布器（ReportGenerated）。
        """
        self._chain_archive_service = chain_archive_service
        self._snapshot_repository = snapshot_repository
        self._l0_storage = l0_storage
        self._report_repository = report_repository
        self._event_publisher = event_publisher

    async def generate_markdown_report(self, plan_id: uuid.UUID) -> StrategicReport:
        """按 plan_id 生成 Markdown 战略报告（五段编排）。

        Args:
            plan_id: 规划任务标识。

        Returns:
            StrategicReport 实体（generation_ms 为聚合起点→L2 落库前窗口近似；
            完整「聚合→事件发布返回」口径由调用方计时承载——OD-8 注记）。

        Raises:
            ReportGenerationError: 数据源全缺（chain total==0——490）。
            ReportStorageError: L0/L2 持久化失败（二元 layer——491）。
        """
        started = time.perf_counter()
        # ① chain 归档主源聚合（空档案 total==0 → 490——两形态同判）
        trace = await self._chain_archive_service.query_chain_trace(plan_id)
        if trace.total == 0:
            raise ReportGenerationError(plan_id=str(plan_id))
        # ② latest 快照辅源（缺失/TTL 过期/读失败同形态容错——附录 A 省略）
        snapshot = await self._load_snapshot(plan_id)
        # ③ 领域渲染纯函数（聚合 → 文档 VO → Markdown 文本）
        aggregation = aggregate_report_document(str(plan_id), trace.records, snapshot, started)
        markdown_text = render_markdown_report(aggregation.document)
        # ④ L0 写 + L2 元数据行落库（真相源二元——失败 491）
        memory_id = f"{plan_id}_{datetime.now(timezone.utc):%Y%m%d%H%M%S}"
        file_path = f"reports/{memory_id}.md"
        await self._write_l0(memory_id, markdown_text)
        report = StrategicReport(
            plan_id=str(plan_id),
            report_type=ReportType.MARKDOWN,
            file_path=file_path,
            section_count=_SECTION_COUNT,
            degraded_section_count=aggregation.degraded_count,
            generation_ms=int((time.perf_counter() - started) * 1000),
        )
        await self._save_l2(report, aggregation.metadata)
        # ⑤ ReportGenerated 发布（宽容语义——真相源已落盘，事件是通知面）
        await self._publish_event(report)
        return report

    async def _load_snapshot(self, plan_id: uuid.UUID) -> Any:
        """加载 latest 快照（容错——异常与缺失同形态返回 None）。

        Args:
            plan_id: 规划任务标识。

        Returns:
            CheckpointSnapshot 或 None（读失败不阻断报告生成）。
        """
        try:
            return await self._snapshot_repository.load(f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}")
        except Exception as error:  # 快照是辅源：任何读失败降级省略（宽容面注释）
            logger.warning("latest 快照读取失败（附录 A 省略——辅源容错）: plan_id=%s error=%s", plan_id, error)
            return None

    async def _write_l0(self, memory_id: str, content: str) -> None:
        """L0 报告文件写（OSError 与 False 返回双检出口径——491 包装）。

        Args:
            memory_id: 报告文件标识（plan_id_时间戳）。
            content: Markdown 文本。

        Raises:
            ReportStorageError: 写失败（layer="l0"——真实适配器从不返回 False
                只抛 OSError，write() is False 返回值同查端口契约面）。
        """
        try:
            written = await self._l0_storage.write(memory_id, REPORT_FILE_MEMORY_TYPE, content)
        except OSError as error:
            raise ReportStorageError(layer="l0", cause=error) from error
        if written is False:
            raise ReportStorageError(layer="l0")

    async def _save_l2(self, report: StrategicReport, metadata: dict[str, Any]) -> None:
        """L2 元数据行落库（失败 491 包装——layer="l2"）。

        Args:
            report: 报告实体。
            metadata: 扩展元数据（timeline_available/缺失步清单）。

        Raises:
            ReportStorageError: 落库失败（layer="l2"）。
        """
        try:
            await self._report_repository.save(report, metadata=metadata)
        except Exception as error:
            raise ReportStorageError(layer="l2", cause=error) from error

    async def _publish_event(self, report: StrategicReport) -> None:
        """发布 ReportGenerated（宽容语义——双防线失败检出 + warning 不上抛）。

        失败检出双防线（AC-5 强制）：①``is_success`` 判定先判（实现层经
        DualChannelEventBus 委托 RabbitMQEventBus.publish——吞异常只返回失败
        PublishResult，纯 except 恒不触发）+ ②``except`` 兜底；两防线任一命中
        均走 warning（491 上抛回滚不了已落盘 L0/L2，且 CLI exit 1 误导重跑
        叠加多份——OD-6 裁定）。

        Args:
            report: 报告实体（事件三键显式传——事件类三键有缺省空串，漏传
                不炸产空串事件，唯一防线在构造点）。
        """
        event = ReportGenerated(
            report_id=report.report_id,
            report_type=report.report_type.value,
            file_path=report.file_path,
        )
        try:
            result = await self._event_publisher.publish(event)
            if not result.is_success:
                logger.warning(
                    "ReportGenerated 发布降级（报告已落盘不回滚）: report_id=%s event_type=%s error=%s",
                    report.report_id,
                    event.event_type,
                    result.partial_error,
                )
        except Exception as error:  # 宽容语义：发布失败不上抛（双防线第二道）
            logger.warning(
                "ReportGenerated 发布降级（报告已落盘不回滚）: report_id=%s event_type=%s error=%s",
                report.report_id,
                event.event_type,
                error,
            )


class _Aggregation:
    """单次聚合结果（文档 VO + 计数 + 元数据——函数局部累积非实例态）。"""

    __slots__ = ("document", "degraded_count", "metadata")

    def __init__(self, document: MarkdownReportDocument, degraded_count: int, metadata: dict[str, Any]) -> None:
        """初始化聚合结果。

        Args:
            document: 报告文档 VO。
            degraded_count: 内容缺失类 H3 小节数。
            metadata: L2 扩展元数据。
        """
        self.document = document
        self.degraded_count = degraded_count
        self.metadata = metadata


def _classify_payload(record: dict[str, Any] | None) -> tuple[str, dict[str, Any] | None]:
    """三态判定（payload 形态优先于 degraded 锚——AC-4 冻结版）。

    Args:
        record: chain 读侧单条记录（None=归档行缺失）。

    Returns:
        (state, payload) 二元组——state ∈ {"missing", "envelope", "normal"}：
        ①missing：行缺失 / final_answer 解析失败 / 非 dict 形态不可识别；
        ②envelope：键集 ⊆ {degraded, degrade_reason}（降级信封态——gap 型
        恒 asdict 六键不适用②）；
        ③normal：其余（payload 完整，行 degraded 锚叠加判定归调用方）。
    """
    if record is None:
        return "missing", None
    try:
        payload = json.loads(record["chain"].final_answer)
    except (json.JSONDecodeError, TypeError, ValueError):
        return "missing", None
    if not isinstance(payload, dict):
        return "missing", None
    if not payload:
        # 空 dict 归①缺失态（CR1-F14：键集 ⊆ 判定对 {} 恒真——空 payload 无任何
        # 降级信号，语义是内容缺失非降级信封；与 _ENVELOPE_KEYS 注释「且非空」对齐）
        return "missing", None
    if payload.keys() <= _ENVELOPE_KEYS:
        return "envelope", payload
    return "normal", payload


def _resolve_degrade_reason(payload: dict[str, Any] | None) -> str:
    """解析降级原因（次序冻结：payload.degrade_reason → 固定兜底文案）。

    Args:
        payload: 步骤 payload dict（信封态可为 None 键集形态）。

    Returns:
        原因文本（缺席/空值走兜底——禁解析 chain VO reflection 文本）。
    """
    reason = (payload or {}).get("degrade_reason")
    return reason if reason else _DEGRADE_REASON_FALLBACK


def _appendix_a_rows(snapshot: Any) -> list[tuple[str, ...]]:
    """构造附录 A 时间线表数据行（display_name 三源映射 + miss 直显裸值）。

    辅源形态守卫双层闭合（CR2-F10——AC-4「辅源不阻断」信封延伸）：容器级
    （state_data 非 dict / timeline 非 list → 空行 = 附录 A 省略）+ 元素级
    （条目非 dict 跳过其余行照常——Redis 反序列化可返回任意 JSON 类型，
    形态损坏走 AttributeError 逃逸非 DomainError 即违信封）。

    Args:
        snapshot: latest 快照（None 或形态损坏 → 空列表）。

    Returns:
        五列数据行列表（summary_excerpt 显式省略）。
    """
    if snapshot is None:
        return []
    state_data = getattr(snapshot, "state_data", None)
    if not isinstance(state_data, dict):
        return []
    timeline = state_data.get("timeline")
    if not isinstance(timeline, list):
        return []
    rows: list[tuple[str, ...]] = []
    for entry in timeline:
        if not isinstance(entry, dict):
            continue
        rows.append(
            (
                _timeline_step_display(str(entry.get("step", ""))),
                str(entry.get("started_at", "")),
                str(entry.get("completed_at", "")),
                str(entry.get("status", "")),
                "是" if entry.get("degraded") else "否",
            )
        )
    return rows


def _timeline_step_display(step: str) -> str:
    """timeline step 值 → 显示名（三源映射：gap 配置/六子配置/synthesis 常量）。

    Args:
        step: timeline 条目 step 值（三种形态——写侧 record_step 实证值：
            六子裸值 trend 等 / ``performance_gap`` /
            ``market_insight_synthesis``【CR1-F1 勘误：原记裸值 ``synthesis``
            系对端口 docstring 简称的误读，写侧实际记录 stage 全值】）。

    Returns:
        display_name；映射 miss（未知 step 值）直显裸值（防未来配置增步炸渲染）。
    """
    if step == "performance_gap":
        return PERFORMANCE_GAP_CONFIG.display_name
    if step == "market_insight_synthesis":
        return SYNTHESIS_DISPLAY_NAME
    for config_step, config in MARKET_INSIGHT_STEP_CONFIG.items():
        if step == config_step.value:
            return config.display_name
    return step


def _str_items(value: Any) -> tuple[str, ...]:
    """payload 字段值归一为字符串元组（JSON round-trip list → tuple）。

    Args:
        value: 源字段值（list[str] 或其他）。

    Returns:
        字符串元组（非列表形态安全降空——渲染容错）。
    """
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def _str_field(payload: dict[str, Any], key: str) -> str:
    """payload 字符串字段安全取值（非 str 形态降空串——渲染容错）。

    Args:
        payload: 步骤 payload。
        key: 字段键。

    Returns:
        字符串值。
    """
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def aggregate_report_document(
    plan_id: str,
    records: list[dict[str, Any]],
    snapshot: Any,
    started: float,
) -> _Aggregation:
    """双源聚合为文档 VO（冻结章节结构 + 三态判定 + 附录 B 局部累积）。

    公开函数（Story 6-5b 聚合公开化——原 ``_aggregate_document`` 更名，签名/
    行为/返回结构零变）：被 6-5a Markdown 链与 6-5b PDF 链双链消费的同源
    聚合单源（OD-3 同源双渲染）。返回的 ``MarkdownReportDocument`` 是双渲染
    共用的中间文档模型（IR）——名字带 Markdown 前缀但已成 PDF 链同源 IR
    （VO 本体属 6-5a 冻结面不可改名，docstring 消歧——R3B-2）。

    Args:
        plan_id: 规划任务标识。
        records: chain 读侧 records（五键结构）。
        snapshot: latest 快照（可 None）。
        started: 生成起点（perf_counter——元信息表执行耗时行）。

    Returns:
        _Aggregation（文档/计数/L2 元数据）。
    """
    records_by_stage: dict[str, dict[str, Any]] = {str(record["stage"]): record for record in records}
    appendix_b: list[tuple[str, str, str]] = []
    degraded_count = 0
    # 内容缺失类 stage 清单（CR2-F11——与 degraded_section_count 同口径的
    # 三处增量位并行累积，禁从 appendix_b 派生【附录 B 两类全收含锚叠加且
    # 类型列无法区分信封与锚叠加】；missing_stages ⊆ degraded_stages 包含
    # 关系——前者只反映行缺席，本清单另含信封态与解析失败形态）
    degraded_stages: list[str] = []
    sections: list[ReportSection] = []

    # --- 第 1 章：业绩差距分析（gap 四小节；缺行 → 四小节骨架共享步骤锚定）---
    gap_record = records_by_stage.get("performance_gap")
    gap_state, gap_payload = _classify_payload(gap_record)
    gap_display = PERFORMANCE_GAP_CONFIG.display_name
    chapter_one_blocks: list[ReportBlock] = []
    if gap_state == "normal":
        assert gap_payload is not None
        if gap_record is not None and gap_record.get("degraded"):
            chapter_one_blocks.append(
                ReportBlock(kind="callout", text=f"⚠️ [降级] {gap_display}：{_resolve_degrade_reason(gap_payload)}")
            )
            appendix_b.append(("[降级]", gap_display, _resolve_degrade_reason(gap_payload)))
        sections.append(ReportSection(title=f"1 {gap_display}", level=2, blocks=tuple(chapter_one_blocks)))
        for title, field in _GAP_SUBSECTIONS:
            if field == "root_causes":
                sections.append(
                    ReportSection(
                        title=title,
                        level=3,
                        blocks=(ReportBlock(kind="bullet_list", items=_str_items(gap_payload.get("root_causes"))),),
                    )
                )
            else:
                paragraph = ReportBlock(kind="paragraph", text=_str_field(gap_payload, field))
                sections.append(ReportSection(title=title, level=3, blocks=(paragraph,)))
    else:
        reason = _resolve_degrade_reason(gap_payload) if gap_state == "envelope" else _MISSING_DATA_TEXT
        if gap_state == "envelope":
            appendix_b.append(("[降级]", gap_display, reason))
        else:
            appendix_b.append(("[数据缺失]", gap_display, _MISSING_DATA_TEXT))
        sections.append(ReportSection(title=f"1 {gap_display}", level=2))
        for title, _field in _GAP_SUBSECTIONS:
            mark = "[降级]" if gap_state == "envelope" else "[数据缺失]"
            sections.append(
                ReportSection(
                    title=title,
                    level=3,
                    blocks=(ReportBlock(kind="callout", text=f"⚠️ {mark} {gap_display}：{reason}"),),
                )
            )
        degraded_count += len(_GAP_SUBSECTIONS)
        degraded_stages.append("performance_gap")

    # --- 第 2 章：市场洞察（六子 2.1~2.6 + synthesis 2.7）---
    sections.append(ReportSection(title="2 市场洞察", level=2))
    for index, (step_enum, step_config) in enumerate(MARKET_INSIGHT_STEP_CONFIG.items(), start=1):
        stage = f"market_insight_{step_enum.value}"
        display = step_config.display_name
        record = records_by_stage.get(stage)
        state, payload = _classify_payload(record)
        title = f"2.{index} {display}"
        if state != "normal":
            mark = "[降级]" if state == "envelope" else "[数据缺失]"
            reason = _resolve_degrade_reason(payload) if state == "envelope" else _MISSING_DATA_TEXT
            sections.append(
                ReportSection(
                    title=title,
                    level=3,
                    blocks=(ReportBlock(kind="callout", text=f"⚠️ {mark} {display}：{reason}"),),
                )
            )
            appendix_b.append((mark, display, reason))
            degraded_count += 1
            degraded_stages.append(stage)
            continue
        assert payload is not None
        blocks: list[ReportBlock] = []
        if record is not None and record.get("degraded"):
            blocks.append(ReportBlock(kind="callout", text=f"⚠️ [降级] {display}：{_resolve_degrade_reason(payload)}"))
            appendix_b.append(("[降级]", display, _resolve_degrade_reason(payload)))
        blocks.append(ReportBlock(kind="paragraph", text=_str_field(payload, "summary")))
        blocks.append(ReportBlock(kind="bullet_list", items=_str_items(payload.get("findings"))))
        blocks.extend(_step_field_blocks(step_enum.value, payload))
        sections.append(ReportSection(title=title, level=3, blocks=tuple(blocks)))

    # --- 2.7 市场洞察综合（conclusions + degraded_inputs 显式列举；编号派生自六子配置长度）---
    synthesis_record = records_by_stage.get("market_insight_synthesis")
    synthesis_state, synthesis_payload = _classify_payload(synthesis_record)
    synthesis_blocks: list[ReportBlock] = []
    if synthesis_state == "normal":
        assert synthesis_payload is not None
        if synthesis_record is not None and synthesis_record.get("degraded"):
            synthesis_blocks.append(
                ReportBlock(
                    kind="callout", text=f"⚠️ [降级] {SYNTHESIS_DISPLAY_NAME}：{_resolve_degrade_reason(synthesis_payload)}"
                )
            )
            appendix_b.append(("[降级]", SYNTHESIS_DISPLAY_NAME, _resolve_degrade_reason(synthesis_payload)))
        synthesis_blocks.append(ReportBlock(kind="bullet_list", items=_str_items(synthesis_payload.get("conclusions"))))
        for item in _str_items(synthesis_payload.get("degraded_inputs")):
            synthesis_blocks.append(ReportBlock(kind="callout", text=f"⚠️ [降级输入] {item}"))
        sections.append(
            ReportSection(title=f"2.{_SYNTHESIS_SUBNUMBER} {SYNTHESIS_DISPLAY_NAME}", level=3, blocks=tuple(synthesis_blocks))
        )
    else:
        mark = "[降级]" if synthesis_state == "envelope" else "[数据缺失]"
        reason = _resolve_degrade_reason(synthesis_payload) if synthesis_state == "envelope" else _MISSING_DATA_TEXT
        sections.append(
            ReportSection(
                title=f"2.{_SYNTHESIS_SUBNUMBER} {SYNTHESIS_DISPLAY_NAME}",
                level=3,
                blocks=(ReportBlock(kind="callout", text=f"⚠️ {mark} {SYNTHESIS_DISPLAY_NAME}：{reason}"),),
            )
        )
        appendix_b.append((mark, SYNTHESIS_DISPLAY_NAME, reason))
        degraded_count += 1
        degraded_stages.append("market_insight_synthesis")

    # --- 附录 A：执行时间线（latest 快照在位时）---
    timeline_rows = _appendix_a_rows(snapshot)
    if timeline_rows:
        sections.append(
            ReportSection(
                title="附录 A 执行时间线",
                level=2,
                blocks=(ReportBlock(kind="table", headers=_TIMELINE_HEADERS, rows=tuple(timeline_rows)),),
            )
        )

    # --- 附录 B：降级与数据缺失记录（固定章——两类全收，空时表头骨架）---
    sections.append(
        ReportSection(
            title="附录 B 降级与数据缺失记录",
            level=2,
            blocks=(ReportBlock(kind="table", headers=_APPENDIX_B_HEADERS, rows=tuple((t, s, r) for t, s, r in appendix_b)),),
        )
    )

    # --- 封面元信息表（五项素材源：plan_id/生成时间/执行耗时/章节数/降级数）---
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    meta_rows: tuple[tuple[str, str], ...] = (
        ("计划标识", plan_id),
        ("生成时间", datetime.now(timezone.utc).isoformat()),
        ("执行耗时", f"{elapsed_ms} ms"),
        ("正文章节数", str(_SECTION_COUNT)),
        ("降级章节数", str(degraded_count)),
    )
    document = MarkdownReportDocument(
        plan_id=plan_id,
        title=REPORT_TITLE_TEMPLATE,
        meta_rows=meta_rows,
        sections=tuple(sections),
        toc_enabled=True,
    )
    missing_stages = [stage for stage in EXPECTED_REPORT_STAGES if stage not in records_by_stage]
    metadata: dict[str, Any] = {
        "timeline_available": bool(timeline_rows),
        "missing_stages": missing_stages,
        # CR2-F11：内容缺失类 stage 全收（缺行/信封态/解析失败——锚叠加不收，
        # 与 degraded_section_count 同口径；missing_stages ⊆ degraded_stages）
        "degraded_stages": degraded_stages,
    }
    return _Aggregation(document, degraded_count, metadata)


def _step_field_blocks(step_key: str, payload: dict[str, Any]) -> list[ReportBlock]:
    """六子步骤领域要素字段 → 块型序列（要素渲染映射冻结表分派）。

    Args:
        step_key: 步骤键（trend/market_customer/competition/self/opportunity/
            opportunity_gap）。
        payload: 步骤 payload（normal 态）。

    Returns:
        领域字段块列表（summary/findings 公共前缀之外的部分）。
    """
    blocks: list[ReportBlock] = []
    if step_key == "trend":
        pestel_rows = tuple((label, _str_field(payload, key)) for label, key in _PESTEL_ROWS)
        blocks.append(ReportBlock(kind="table", headers=("维度", "评估"), rows=pestel_rows))
        blocks.append(ReportBlock(kind="bullet_list", items=_str_items(payload.get("technology_roadmap"))))
        blocks.append(ReportBlock(kind="bullet_list", items=_str_items(payload.get("scenario_plans"))))
    elif step_key == "competition":
        forces_rows = tuple((label, _str_field(payload, key)) for label, key in _FIVE_FORCES_ROWS)
        blocks.append(ReportBlock(kind="table", headers=("五力", "评估"), rows=forces_rows))
        radar_rows = tuple(
            (f"维度 {index}", str(item)) for index, item in enumerate(_str_items(payload.get("competitor_radar")), start=1)
        )
        blocks.append(ReportBlock(kind="table", headers=("能力维度", "评估要点"), rows=radar_rows))
        blocks.append(ReportBlock(kind="bullet_list", items=_str_items(payload.get("strategy_recommendations"))))
    else:
        for label, key in _BULLETED_FIELD_GROUPS[step_key]:
            blocks.append(ReportBlock(kind="paragraph", text=f"**{label}**"))
            blocks.append(ReportBlock(kind="bullet_list", items=_str_items(payload.get(key))))
    return blocks
