"""工作流领域事件单元测试

验证 RAGIndexed 和 ReportGenerated 事件定义、序列化、注册

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid

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
            event.index_name = "changed"  # type: ignore[misc]

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
            event.report_type = "changed"  # type: ignore[misc]

    def test_auto_registered_in_domain_event_registry(self) -> None:
        """ReportGenerated 应自动注册到 DomainEvent._registry"""
        from src.domain.events.base import DomainEvent
        from src.domain.events.workflow_events import ReportGenerated

        assert "ReportGenerated" in DomainEvent._registry
        assert DomainEvent._registry["ReportGenerated"] is ReportGenerated
