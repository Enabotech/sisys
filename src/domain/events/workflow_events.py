"""领域层工作流事件模块

定义 RAGIndexed、ReportGenerated 和 WorkflowSubmitted 领域事件

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

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

    flow_run_id: uuid.UUID = field(default_factory=uuid.uuid4)
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

    document_id: uuid.UUID = field(default_factory=uuid.uuid4)
    index_name: str = ""
    chunk_count: int = 0
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

    report_id: uuid.UUID = field(default_factory=uuid.uuid4)
    report_type: str = ""
    file_path: str = ""
    event_type: str = field(default="ReportGenerated", init=False)

    def __post_init__(self) -> None:
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.report_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Report")
