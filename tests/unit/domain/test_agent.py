"""Tests for Agent domain entity."""

import uuid

import pytest

from src.domain.entities.agent import Agent, AgentRole, AgentStatus


def _make_agent(**kwargs) -> Agent:
    """Factory helper for Agent."""
    defaults: dict = {
        "agent_id": uuid.uuid4(),
        "role": AgentRole.CEO,
        "name": "Test CEO",
    }
    defaults.update(kwargs)
    return Agent(**defaults)


class TestAgentCreation:
    """Test Agent entity creation."""

    def test_create_minimal_agent(self):
        """Can create an agent with minimal arguments."""
        agent = _make_agent()
        assert agent.agent_id is not None
        assert agent.role == AgentRole.CEO
        assert agent.name == "Test CEO"
        assert agent.status == AgentStatus.IDLE

    def test_agent_has_empty_knowledge_by_default(self):
        """Agent starts with empty domain knowledge."""
        agent = _make_agent()
        assert agent.domain_knowledge == []


class TestAgentValidation:
    """Test Agent invariant validation."""

    def test_valid_agent_passes(self):
        """Correctly constructed agent passes validation."""
        agent = _make_agent()
        assert agent.validate() is True

    def test_invalid_id_fails(self):
        """Agent with non-UUID id fails validation."""
        agent = _make_agent()
        agent.agent_id = "not-a-uuid"  # type: ignore
        with pytest.raises(ValueError, match="agent_id must be a valid UUID"):
            agent.validate()

    def test_empty_name_fails(self):
        """Agent with empty name fails validation."""
        agent = _make_agent(name="")
        with pytest.raises(ValueError, match="name must not be empty"):
            agent.validate()

    def test_invalid_role_fails(self):
        """Agent with non-AgentRole role fails validation."""
        agent = _make_agent()
        agent.role = "invalid_role"  # type: ignore
        with pytest.raises(ValueError, match="role must be a valid AgentRole"):
            agent.validate()
