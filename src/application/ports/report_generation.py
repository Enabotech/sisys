"""报告生成服务端口（Story 6-5a——R2 具体应用端口）。

端口契约（Task 0.3 冻结）：
- **L0 memory_type 命名约定**：``REPORT_FILE_MEMORY_TYPE = "reports"``（单源
  常量——禁两处字面量；L0 路径形态 ``{base}/reports/{memory_id}.md``）。
- **文件命名**：``memory_id = f"{plan_id}_{YYYYMMDDHHMMSS}"``（秒级时间戳——
  同秒重复生成 L0 覆写为一份，幂等锚=report_id 非文件名——OD-10 注记）。
- **file_path 逻辑路径**：``reports/{memory_id}.md`` 单源派生（OD-4——非绝对
  路径；memory_id 可经 ``Path(file_path).stem`` 反解）。
- **双源读径**：主源 ``query_chain_trace(plan_id)``（PG 归档行 7 年——payload
  三态：gap asdict 六键 / 六子 structured_output 原样或降级信封 / synthesis
  asdict 两键）+ 辅源 latest 快照（``blm-planning-{plan_id}`` 键——timeline
  → 附录 A；TTL 86400 过期或缺失 → 容错省略不阻断）。
- **降级判别**（三态判定以 payload 形态为准——AC-4 冻结版）：
  ①payload 解析失败或非 dict → [数据缺失]；②六子 payload 键集 ⊆
  {degraded, degrade_reason}（降级信封态）→ [降级] callout（带
  payload.degrade_reason，缺席固定兜底文案）+ 跳过字段渲染 + 计入
  degraded_section_count；③其余 → 正常渲染 + 行 degraded 锚 True 时叠加
  [降级] callout（不计入——内容完整）。
- **八 stage 期望集派生公式**（缺失判定单源——禁硬编码八清单）::

      expected_stages = ("performance_gap",
                         *(f"market_insight_{step.value}" for step in MARKET_INSIGHT_STEP_CONFIG),
                         "market_insight_synthesis")

  配置增步自动跟随（键序有序且与章节标题 display_name 同源——frozenset 无序
  不适配差集判定与渲染顺序，故取 CONFIG 键序非 STAGE_VALUE_DOMAIN）。
"""

import uuid
from typing import Protocol, runtime_checkable

from src.application.services.blm_planning_prompts import MARKET_INSIGHT_STEP_CONFIG
from src.domain.entities.strategic_report import StrategicReport

__all__ = [
    "REPORT_FILE_MEMORY_TYPE",
    "REPORT_TITLE_TEMPLATE",
    "EXPECTED_REPORT_STAGES",
    "ReportGenerationServicePort",
]

#: L0 报告文件 memory_type（单源常量——禁两处字面量）
REPORT_FILE_MEMORY_TYPE: str = "reports"

#: 报告封面标题模板（H1 冻结源——渲染器入参 title 消费）
REPORT_TITLE_TEMPLATE: str = "战略规划报告（BLM 前两阶段）"

#: 八 stage 期望集（缺失判定单源——派生公式见模块 docstring；配置增步自动跟随）
EXPECTED_REPORT_STAGES: tuple[str, ...] = (
    "performance_gap",
    *(f"market_insight_{step.value}" for step in MARKET_INSIGHT_STEP_CONFIG),
    "market_insight_synthesis",
)


@runtime_checkable
class ReportGenerationServicePort(Protocol):
    """报告生成服务端口（R2 具体应用端口——组合注入 R1 基础端口）。

    五依赖注入面（R2 组合律）：
    - ``chain_archive_service``（应用层 ChainOfThoughtArchiveServicePort——聚合主源）
    - ``snapshot_repository``（R1 SnapshotRepositoryProtocol——latest 快照辅源）
    - ``l0_storage``（R1 L0StoragePort——报告文件写）
    - ``report_repository``（R1 ReportRepositoryProtocol——L2 元数据行）
    - ``event_publisher``（R1 EventPublisher——ReportGenerated 发布）
    """

    async def generate_markdown_report(self, plan_id: uuid.UUID) -> StrategicReport:
        """按 plan_id 生成 Markdown 战略报告（五段编排）。

        Args:
            plan_id: 规划任务标识（UUID——与 chain 归档 plan_id 同源）。

        Returns:
            StrategicReport 实体（report_id/plan_id/report_type="markdown"/
            file_path/section_count/degraded_section_count/generation_ms）。

        Raises:
            ReportGenerationError: 数据源全缺（chain total==0——490）。
            ReportStorageError: 持久化失败（L0/L2 二元 layer——491）。
        """
        ...
