"""工作流领域事件单元测试

验证 RAGIndexed 和 ReportGenerated 事件定义、序列化、注册

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest

from src.domain.events.base import DomainEvent


class TestRAGIndexedEvent:
    """RAGIndexed 事件测试"""

    def test_event_type_is_rag_indexed(self) -> None:
        """event_type 应为 RAGIndexed"""
        from src.domain.events.workflow_events import RAGIndexed

        event = RAGIndexed()
        assert event.event_type == "RAGIndexed"

    def test_has_required_fields(self) -> None:
        """应包含 document_id, index_name, chunk_count 字段"""
        from src.domain.events.workflow_events import RAGIndexed

        document_id = uuid.uuid4()
        event = RAGIndexed(
            document_id=document_id,
            index_name="test-index",
            chunk_count=42,
        )

        assert event.document_id == document_id
        assert event.index_name == "test-index"
        assert event.chunk_count == 42

    def test_is_domain_event_subclass(self) -> None:
        """RAGIndexed 应为 DomainEvent 子类"""
        from src.domain.events.workflow_events import RAGIndexed

        assert issubclass(RAGIndexed, DomainEvent)

    def test_is_frozen(self) -> None:
        """事件应为不可变"""
        from src.domain.events.workflow_events import RAGIndexed

        event = RAGIndexed()
        with pytest.raises(AttributeError):
            cast(Any, event).index_name = "changed"

    def test_auto_registered_in_domain_event_registry(self) -> None:
        """RAGIndexed 应自动注册到 DomainEvent._registry"""
        from src.domain.events.base import DomainEvent
        from src.domain.events.workflow_events import RAGIndexed

        assert "RAGIndexed" in DomainEvent._registry
        assert DomainEvent._registry["RAGIndexed"] is RAGIndexed


class TestReportGeneratedEvent:
    """ReportGenerated 事件测试"""

    def test_event_type_is_report_generated(self) -> None:
        """event_type 应为 ReportGenerated"""
        from src.domain.events.workflow_events import ReportGenerated

        event = ReportGenerated()
        assert event.event_type == "ReportGenerated"

    def test_has_required_fields(self) -> None:
        """应包含 report_id, report_type, file_path 字段"""
        from src.domain.events.workflow_events import ReportGenerated

        report_id = uuid.uuid4()
        event = ReportGenerated(
            report_id=report_id,
            report_type="compliance",
            file_path="/reports/test.pdf",
        )

        assert event.report_id == report_id
        assert event.report_type == "compliance"
        assert event.file_path == "/reports/test.pdf"

    def test_is_domain_event_subclass(self) -> None:
        """ReportGenerated 应为 DomainEvent 子类"""
        from src.domain.events.workflow_events import ReportGenerated

        assert issubclass(ReportGenerated, DomainEvent)

    def test_is_frozen(self) -> None:
        """事件应为不可变"""
        from src.domain.events.workflow_events import ReportGenerated

        event = ReportGenerated()
        with pytest.raises(AttributeError):
            cast(Any, event).report_type = "changed"

    def test_auto_registered_in_domain_event_registry(self) -> None:
        """ReportGenerated 应自动注册到 DomainEvent._registry"""
        from src.domain.events.base import DomainEvent
        from src.domain.events.workflow_events import ReportGenerated

        assert "ReportGenerated" in DomainEvent._registry
        assert DomainEvent._registry["ReportGenerated"] is ReportGenerated


class TestWorkflowSubmittedEvent:
    """WorkflowSubmitted 事件测试"""

    def test_event_type_is_workflow_submitted(self) -> None:
        """event_type 应为 WorkflowSubmitted"""
        from src.domain.events.workflow_events import WorkflowSubmitted

        event = WorkflowSubmitted()
        assert event.event_type == "WorkflowSubmitted"

    def test_has_required_fields(self) -> None:
        """应包含 flow_run_id, flow_name, parameters 字段"""
        from src.domain.events.workflow_events import WorkflowSubmitted

        flow_run_id = uuid.uuid4()
        event = WorkflowSubmitted(
            flow_run_id=flow_run_id,
            flow_name="DocumentProcessing/deploy-v1",
            parameters={"doc_id": "abc123"},
        )

        assert event.flow_run_id == flow_run_id
        assert event.flow_name == "DocumentProcessing/deploy-v1"
        assert event.parameters == {"doc_id": "abc123"}

    def test_aggregate_type_is_workflow(self) -> None:
        """aggregate_type 应为 Workflow"""
        from src.domain.events.workflow_events import WorkflowSubmitted

        event = WorkflowSubmitted()
        assert event.aggregate_type == "Workflow"

    def test_aggregate_id_defaults_to_flow_run_id(self) -> None:
        """aggregate_id 应默认为 flow_run_id"""
        from src.domain.events.workflow_events import WorkflowSubmitted

        flow_run_id = uuid.uuid4()
        event = WorkflowSubmitted(flow_run_id=flow_run_id)
        assert event.aggregate_id == flow_run_id

    def test_is_domain_event_subclass(self) -> None:
        """WorkflowSubmitted 应为 DomainEvent 子类"""
        from src.domain.events.workflow_events import WorkflowSubmitted

        assert issubclass(WorkflowSubmitted, DomainEvent)

    def test_is_frozen(self) -> None:
        """事件应为不可变"""
        from src.domain.events.workflow_events import WorkflowSubmitted

        event = WorkflowSubmitted()
        with pytest.raises(AttributeError):
            cast(Any, event).flow_name = "changed"

    def test_auto_registered_in_domain_event_registry(self) -> None:
        """WorkflowSubmitted 应自动注册到 DomainEvent._registry"""
        from src.domain.events.base import DomainEvent
        from src.domain.events.workflow_events import WorkflowSubmitted

        assert "WorkflowSubmitted" in DomainEvent._registry
        assert DomainEvent._registry["WorkflowSubmitted"] is WorkflowSubmitted
