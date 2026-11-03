"""战略报告实体（Story 6-5a——Markdown 报告生成的领域交付物）。

报告是 BLM 前两阶段产物的可交付形态：按 plan_id 事后聚合八步思维链归档
（chain 主源）与 latest 快照（辅源），经领域渲染纯函数生成 Markdown 文本，
落 L0 文件 + L2 元数据行（strategic_reports 表）并发布 ReportGenerated 事件。

领域零依赖约束：本模块仅依赖标准库与领域异常体系（import-linter 强制）。
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from src.domain.exceptions import EntityValidationError

__all__ = ["ReportType", "StrategicReport"]


class ReportType(Enum):
    """报告类型枚举。

    Attributes:
        MARKDOWN: Markdown 基础报告（6-5a 交付面）。
        PDF: PDF 报告（6-5b 预留值——本 Story 零产出，仅枚举成员在位）。
    """

    MARKDOWN = "markdown"
    PDF = "pdf"


@dataclass(frozen=True)
class StrategicReport:
    """战略报告实体（报告生成的持久化真相源行——L2 strategic_reports 表实体面）。

    幂等锚 = report_id（非 plan_id）：同 plan_id 重复生成产生新报告（新
    report_id + 新 L2 行——OD-10 裁定；重跑是预期用法不拦截）。

    Attributes:
        report_id: 报告主键（默认 uuid4）。
        plan_id: 规划任务标识（UUID 字符串——与 chain 归档 plan_id 同源）。
        report_type: 报告类型枚举成员（裸 str 拒绝——构造期守卫）。
        file_path: L0 逻辑路径（``reports/{memory_id}.md`` 单源派生——非绝对
            路径：base 物理路径归 infrastructure MemoryConfig，application 层
            不得知悉；memory_id 可经 ``Path(file_path).stem`` 反解——OD-4）。
        section_count: 正文 H3 小节总数（gap 4 + 六子 6 + synthesis 1 = 11；
            目录/附录不计——H3 口径钦定，H2 口径下缺 ≥3 步破坏不变量炸 242）。
        degraded_section_count: 内容缺失类 H3 小节数（缺行计入/降级信封态
            计入/锚叠加不计——R2 口径；恒 ≤ section_count）。
        generation_ms: 生成窗口毫秒（**实际窗口 = 聚合起点→L2 落库前**——
            frozen 实体须先于 save/publish 构造（publish 依赖 report_id），
            物理上不可能含发布段；AC-7 全窗口「→事件发布返回」口径由测试侧
            execute 包裹计时承载——OD-8 联动，CR1-F16 勘误）。
        created_at: 创建时间（UTC）。
    """

    report_id: uuid.UUID = field(default_factory=uuid.uuid4)
    plan_id: str = ""
    report_type: ReportType = ReportType.MARKDOWN
    file_path: str = ""
    section_count: int = 0
    degraded_section_count: int = 0
    generation_ms: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """构造期不变量守卫（违例抛 EntityValidationError 242——fail-loud）。

        Raises:
            EntityValidationError: report_type 非枚举成员（裸 str 拒绝——
                ArchiveType validate 同款形态）/ plan_id 为空（字段表「非空
                UUID 字符串」契约）/ file_path 为空或纯空白 / 三计数负值
                （字段表 ≥0 约束）/ 计数不变量破坏（degraded_section_count
                > section_count）。
        """
        if not isinstance(self.report_type, ReportType):
            raise EntityValidationError(
                message="report_type 必须为 ReportType 枚举成员（裸字符串拒绝）",
                context={"entity": "StrategicReport", "field": "report_type", "value": str(self.report_type)},
            )
        if not self.plan_id.strip():
            raise EntityValidationError(
                message="plan_id 不可为空（与 chain 归档 plan_id 同源的 UUID 字符串）",
                context={"entity": "StrategicReport", "field": "plan_id"},
            )
        if not self.file_path.strip():
            raise EntityValidationError(
                message="file_path 不可为空（L0 逻辑路径单源派生锚）",
                context={"entity": "StrategicReport", "field": "file_path"},
            )
        if self.section_count < 0 or self.degraded_section_count < 0 or self.generation_ms < 0:
            raise EntityValidationError(
                message="计数与耗时字段不可为负值（section_count/degraded_section_count/generation_ms ≥ 0）",
                context={
                    "entity": "StrategicReport",
                    "field": "section_count/degraded_section_count/generation_ms",
                    "section_count": str(self.section_count),
                    "degraded_section_count": str(self.degraded_section_count),
                    "generation_ms": str(self.generation_ms),
                },
            )
        if self.degraded_section_count > self.section_count:
            raise EntityValidationError(
                message="degraded_section_count 不可超过 section_count（内容缺失数恒 ≤ 小节总数）",
                context={
                    "entity": "StrategicReport",
                    "field": "degraded_section_count",
                    "section_count": str(self.section_count),
                    "degraded_section_count": str(self.degraded_section_count),
                },
            )
