"""GraphNode 和 GraphRelationship 单元测试。"""

from __future__ import annotations

import pytest

from src.infrastructure.storage.neo4j.models import GraphNode, GraphRelationship, RelationshipType


class TestGraphNode:
    """GraphNode 测试类。"""

    def test_valid_node_creation(self):
        """测试有效节点创建。"""
        node = GraphNode(
            id="entity-001",
            labels=["sisys:Entity"],
            properties={
                "business_domain": "strategy",
                "entity_type": "Entity",
                "content_hash": "abc123",
            },
        )
        assert node.id == "entity-001"
        assert node.labels == ["sisys:Entity"]
        assert node.properties["business_domain"] == "strategy"
        assert node.properties["entity_type"] == "Entity"
        assert node.properties["content_hash"] == "abc123"
        assert node.created_at is not None

    def test_empty_id_raises_error(self):
        """测试空 id 应抛出 ValueError。"""
        with pytest.raises(ValueError, match="Node id must be a non-empty string"):
            GraphNode(
                id="",
                labels=["sisys:Entity"],
                properties={"business_domain": "test", "entity_type": "Entity", "content_hash": "hash"},
            )

    def test_no_labels_raises_error(self):
        """测试无标签应抛出 ValueError。"""
        with pytest.raises(ValueError, match="Node must have at least one label"):
            GraphNode(
                id="entity-001",
                labels=[],
                properties={"business_domain": "test", "entity_type": "Entity", "content_hash": "hash"},
            )

    def test_missing_required_properties_raises_error(self):
        """测试缺少必需属性应抛出 ValueError。"""
        with pytest.raises(ValueError, match="Node properties must include"):
            GraphNode(
                id="entity-001",
                labels=["sisys:Entity"],
                properties={"business_domain": "test"},
            )

    def test_multiple_labels(self):
        """测试多标签支持。"""
        node = GraphNode(
            id="doc-001",
            labels=["sisys:Document", "sisys:Report"],
            properties={"business_domain": "strategy", "entity_type": "Document", "content_hash": "hash"},
        )
        assert "sisys:Document" in node.labels
        assert "sisys:Report" in node.labels


class TestGraphRelationship:
    """GraphRelationship 测试类。"""

    def test_valid_relationship_creation(self):
        """测试有效关系创建。"""
        rel = GraphRelationship(
            start_node_id="entity-001",
            end_node_id="entity-002",
            relationship_type=RelationshipType.MENTIONS,
            properties={"confidence": 0.95},
        )
        assert rel.start_node_id == "entity-001"
        assert rel.end_node_id == "entity-002"
        assert rel.relationship_type == RelationshipType.MENTIONS
        assert rel.properties["confidence"] == 0.95
        assert rel.created_at is not None

    def test_string_relationship_type(self):
        """测试字符串关系类型。"""
        rel = GraphRelationship(
            start_node_id="entity-001",
            end_node_id="entity-002",
            relationship_type="DEPENDS_ON",
        )
        assert rel.relationship_type == "DEPENDS_ON"

    def test_empty_start_node_id_raises_error(self):
        """测试空起始节点 ID 应抛出 ValueError。"""
        with pytest.raises(ValueError, match="start_node_id must be a non-empty string"):
            GraphRelationship(
                start_node_id="",
                end_node_id="entity-002",
                relationship_type=RelationshipType.MENTIONS,
            )

    def test_empty_end_node_id_raises_error(self):
        """测试空结束节点 ID 应抛出 ValueError。"""
        with pytest.raises(ValueError, match="end_node_id must be a non-empty string"):
            GraphRelationship(
                start_node_id="entity-001",
                end_node_id="",
                relationship_type=RelationshipType.MENTIONS,
            )

    def test_empty_relationship_type_raises_error(self):
        """测试空关系类型应抛出 ValueError。"""
        with pytest.raises(ValueError, match="relationship_type must be specified"):
            GraphRelationship(
                start_node_id="entity-001",
                end_node_id="entity-002",
                relationship_type="",
            )


class TestRelationshipType:
    """RelationshipType 枚举测试。"""

    def test_all_relationship_types_exist(self):
        """测试所有关系类型已定义。"""
        expected_types = {"MENTIONS", "DEPENDS_ON", "RELATES_TO", "PART_OF", "INFLUENCES", "CONTRADICTS"}
        actual_types = {rt.value for rt in RelationshipType}
        assert expected_types == actual_types

    def test_relationship_type_string_value(self):
        """测试关系类型字符串值。"""
        assert RelationshipType.MENTIONS.value == "MENTIONS"
        assert RelationshipType.DEPENDS_ON.value == "DEPENDS_ON"
        assert RelationshipType.CONTRADICTS.value == "CONTRADICTS"
