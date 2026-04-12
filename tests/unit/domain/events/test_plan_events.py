"""Tests for core domain events."""

import uuid

from src.domain.events.plan_events import (
    AgentDecided,
    CheckpointReached,
    CorrectionApproved,
    DocumentProcessed,
    ToolExecuted,
)


class TestDocumentProcessed:
    """Test DocumentProcessed event."""

    def test_create_event(self):
        """Can create DocumentProcessed event."""
        doc_id = uuid.uuid4()
        event = DocumentProcessed(
            document_id=doc_id,
            parse_result={"pages": 10},
        )
        assert event.event_type == "DocumentProcessed"
        assert event.aggregate_id == doc_id
        assert event.document_id == doc_id

    def test_serialization(self):
        """DocumentProcessed serializes correctly."""
        doc_id = uuid.uuid4()
        event = DocumentProcessed(document_id=doc_id)
        d = event.to_dict()
        assert d["event_type"] == "DocumentProcessed"


class TestToolExecuted:
    """Test ToolExecuted event."""

    def test_create_event(self):
        """Can create ToolExecuted event."""
        tool_id = uuid.uuid4()
        event = ToolExecuted(
            tool_id=tool_id,
            execution_result={"output": "success"},
        )
        assert event.event_type == "ToolExecuted"
        assert event.aggregate_id == tool_id


class TestAgentDecided:
    """Test AgentDecided event."""

    def test_create_event(self):
        """Can create AgentDecided event."""
        agent_id = uuid.uuid4()
        event = AgentDecided(
            agent_id=agent_id,
            decision_result={"choice": "A"},
            confidence=0.85,
        )
        assert event.event_type == "AgentDecided"
        assert event.aggregate_id == agent_id
        assert event.confidence == 0.85


class TestCheckpointReached:
    """Test CheckpointReached event."""

    def test_create_event(self):
        """Can create CheckpointReached event."""
        cp_id = uuid.uuid4()
        event = CheckpointReached(
            checkpoint_id=cp_id,
            phase_identifier="market-insight",
        )
        assert event.event_type == "CheckpointReached"
        assert event.aggregate_id == cp_id
        assert event.phase_identifier == "market-insight"


class TestCorrectionApproved:
    """Test CorrectionApproved event."""

    def test_create_event(self):
        """Can create CorrectionApproved event."""
        corr_id = uuid.uuid4()
        event = CorrectionApproved(
            correction_id=corr_id,
            correction_type="L1",
            previous_value="old",
            new_value="new",
            approval_chain=["expert1"],
        )
        assert event.event_type == "CorrectionApproved"
        assert event.aggregate_id == corr_id
        assert event.correction_type == "L1"
