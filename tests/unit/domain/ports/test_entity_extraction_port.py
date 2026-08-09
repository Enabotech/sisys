"""领域层实体抽取端口与值对象单元测试

验证 EntityExtractionPort 协议契约和值对象（ExtractedEntity/ExtractedRelation/ExtractionResult）的构造与行为。
遵循六边形架构：领域层零外部依赖，仅使用 Python 标准库。
"""

from __future__ import annotations

from src.domain.ports.entity_extraction import (
    EntityExtractionPort,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)


class TestExtractedEntity:
    """ExtractedEntity 值对象测试"""

    def test_constructor_with_all_fields(self) -> None:
        """验证完整字段构造"""
        entity = ExtractedEntity(
            name="BLM",
            entity_type="CONCEPT",
            confidence=0.95,
            extraction_source="rule",
            metadata={"position": 10, "frequency": 3},
            normalized_name="业务领先模型",
        )
        assert entity.name == "BLM"
        assert entity.entity_type == "CONCEPT"
        assert entity.confidence == 0.95
        assert entity.extraction_source == "rule"
        assert entity.metadata == {"position": 10, "frequency": 3}
        assert entity.normalized_name == "业务领先模型"

    def test_constructor_with_defaults(self) -> None:
        """验证默认值"""
        entity = ExtractedEntity(name="SWOT", entity_type="CONCEPT")
        assert entity.name == "SWOT"
        assert entity.entity_type == "CONCEPT"
        assert entity.confidence == 0.0
        assert entity.extraction_source == ""
        assert entity.metadata == {}
        assert entity.normalized_name == ""

    def test_frozen_dataclass(self) -> None:
        """验证 frozen=True 不可变"""
        entity = ExtractedEntity(name="PESTEL", entity_type="CONCEPT")
        try:
            entity.name = "NEW"  # type: ignore[misc]
            assert False, "应抛出 FrozenInstanceError"
        except Exception:
            pass  # frozen dataclass 抛出异常

    def test_equality(self) -> None:
        """验证相等性比较"""
        e1 = ExtractedEntity(name="BLM", entity_type="CONCEPT")
        e2 = ExtractedEntity(name="BLM", entity_type="CONCEPT")
        assert e1 == e2

    def test_inequality(self) -> None:
        """验证不等性比较"""
        e1 = ExtractedEntity(name="BLM", entity_type="CONCEPT")
        e2 = ExtractedEntity(name="SWOT", entity_type="CONCEPT")
        assert e1 != e2


class TestExtractedRelation:
    """ExtractedRelation 值对象测试"""

    def test_constructor_with_all_fields(self) -> None:
        """验证完整字段构造"""
        relation = ExtractedRelation(
            source="BLM",
            target="战略意图",
            relation_type="PART_OF",
            confidence=0.85,
            extraction_source="llm",
            metadata={"sentence": "BLM 包含战略意图"},
        )
        assert relation.source == "BLM"
        assert relation.target == "战略意图"
        assert relation.relation_type == "PART_OF"
        assert relation.confidence == 0.85
        assert relation.extraction_source == "llm"
        assert relation.metadata == {"sentence": "BLM 包含战略意图"}

    def test_constructor_with_defaults(self) -> None:
        """验证默认值"""
        relation = ExtractedRelation(source="SWOT", target="PESTEL", relation_type="RELATES_TO")
        assert relation.source == "SWOT"
        assert relation.target == "PESTEL"
        assert relation.relation_type == "RELATES_TO"
        assert relation.confidence == 0.0
        assert relation.extraction_source == ""
        assert relation.metadata == {}

    def test_frozen_dataclass(self) -> None:
        """验证 frozen=True 不可变"""
        relation = ExtractedRelation(source="A", target="B", relation_type="DEPENDS_ON")
        try:
            relation.source = "C"  # type: ignore[misc]
            assert False, "应抛出 FrozenInstanceError"
        except Exception:
            pass

    def test_source_is_entity_name_not_extraction_source(self) -> None:
        """验证 source 字段是源实体名称，与 extraction_source 不冲突"""
        relation = ExtractedRelation(
            source="BLM",
            target="战略意图",
            relation_type="PART_OF",
            extraction_source="llm",
        )
        assert relation.source == "BLM"  # 源实体名称
        assert relation.extraction_source == "llm"  # 抽取来源标识


class TestExtractionResult:
    """ExtractionResult 值对象测试"""

    def test_constructor_with_all_fields(self) -> None:
        """验证完整字段构造"""
        entities = (
            ExtractedEntity(name="BLM", entity_type="CONCEPT"),
            ExtractedEntity(name="SWOT", entity_type="CONCEPT"),
        )
        relations = (ExtractedRelation(source="BLM", target="SWOT", relation_type="RELATES_TO"),)
        result = ExtractionResult(
            entities=entities,
            relations=relations,
            extraction_metadata={"strategy": "hybrid", "duration_ms": 150},
        )
        assert len(result.entities) == 2
        assert len(result.relations) == 1
        assert result.extraction_metadata["strategy"] == "hybrid"

    def test_constructor_with_defaults(self) -> None:
        """验证默认值"""
        result = ExtractionResult()
        assert result.entities == ()
        assert result.relations == ()
        assert result.extraction_metadata == {}

    def test_frozen_dataclass(self) -> None:
        """验证 frozen=True 不可变"""
        result = ExtractionResult()
        try:
            result.entities = (ExtractedEntity(name="X", entity_type="CONCEPT"),)  # type: ignore[misc]
            assert False, "应抛出 FrozenInstanceError"
        except Exception:
            pass

    def test_empty_result(self) -> None:
        """验证空结果"""
        result = ExtractionResult()
        assert len(result.entities) == 0
        assert len(result.relations) == 0


class TestEntityExtractionPort:
    """EntityExtractionPort 协议测试"""

    def test_is_protocol(self) -> None:
        """验证 EntityExtractionPort 是 Protocol"""
        # Protocol 是 typing 特殊形式，不能直接 issubclass
        # 通过运行时标记验证是 Protocol
        assert getattr(EntityExtractionPort, "_is_protocol", False)

    def test_is_runtime_checkable(self) -> None:
        """验证 @runtime_checkable 已应用"""
        # runtime_checkable 装饰的 Protocol 会设置 _is_runtime_protocol 标记
        assert getattr(EntityExtractionPort, "_is_runtime_protocol", False)

    def test_extract_entities_signature(self) -> None:
        """验证 extract_entities 方法签名"""
        # 验证方法存在
        assert hasattr(EntityExtractionPort, "extract_entities")

        # 验证方法签名：async def extract_entities(content, domain_context=None)
        import inspect

        sig = inspect.signature(EntityExtractionPort.extract_entities)
        params = list(sig.parameters.keys())
        assert "content" in params
        assert "domain_context" in params

        # content 是 str 类型（from __future__ import annotations 下为字符串 'str'）
        content_param = sig.parameters["content"]
        content_ann = content_param.annotation
        assert content_ann in (str, "str"), f"content 注解应为 str, 实际为 {content_ann}"

        # domain_context 是 Optional[dict] 或 dict | None
        domain_param = sig.parameters["domain_context"]
        ann = domain_param.annotation
        ann_str = str(ann) if not isinstance(ann, str) else ann
        assert "dict" in ann_str

    def test_implementing_class_is_runtime_checkable(self) -> None:
        """验证实现了 EntityExtractionPort 的类可通过 isinstance 检测"""

        class MockExtractor:
            async def extract_entities(self, content: str, domain_context: dict | None = None) -> ExtractionResult:
                return ExtractionResult()

        import inspect

        assert inspect.iscoroutinefunction(MockExtractor().extract_entities)
        assert isinstance(MockExtractor(), EntityExtractionPort)
