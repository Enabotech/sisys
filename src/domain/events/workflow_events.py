"""领域层工作流事件模块

定义 RAGIndexed、ReportGenerated 和 WorkflowSubmitted 领域事件
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from src.domain.events.base import DomainEvent


@dataclass(frozen=True)
class WorkflowSubmitted(DomainEvent):
    """工作流提交事件

    PrefectEngine 成功提交工作流后触发，与 LangGraphEngine 的 AgentDecided 形成对称模式
    """

    # kw_only 必填（2-6 系技术债清偿 A2：原 default_factory=uuid4 默认从未被使用
    # 且掩盖调用方遗漏——生产构造点全显式传参已实证，必填化后漏传立即 TypeError）
    flow_run_id: uuid.UUID = field(kw_only=True)
    flow_name: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    event_type: str = field(default="WorkflowSubmitted", init=False)

    def __post_init__(self) -> None:
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.flow_run_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Workflow")


@dataclass(frozen=True)
class RAGIndexed(DomainEvent):
    """RAG 索引完成事件

    文档解析和嵌入完成后触发，由 Epic 2/3 故事实现生产者
    """

    document_id: uuid.UUID = field(kw_only=True)  # kw_only 必填（A2 清偿，同 flow_run_id）
    index_name: str = ""
    chunk_count: int = 0
    tenant_id: str = ""
    event_type: str = field(default="RAGIndexed", init=False)

    def __post_init__(self) -> None:
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.document_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "RAGIndex")


@dataclass(frozen=True)
class ReportGenerated(DomainEvent):
    """报告生成完成事件

    报告生成完成后触发，由 Epic 6 故事实现生产者
    """

    report_id: uuid.UUID = field(kw_only=True)  # kw_only 必填（A2 清偿，同 flow_run_id）
    report_type: str = ""
    file_path: str = ""
    event_type: str = field(default="ReportGenerated", init=False)

    def __post_init__(self) -> None:
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.report_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Report")
