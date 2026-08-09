"""领域层实体抽取端口与值对象模块

定义 EntityExtractionPort 协议契约及其值对象（ExtractedEntity/ExtractedRelation/ExtractionResult）。
遵循六边形架构：领域层零外部依赖，仅使用 Python 标准库。

设计约束：
- EntityExtractionPort 是 typing.Protocol，使用 @runtime_checkable
- ExtractedEntity/ExtractedRelation/ExtractionResult 是 frozen dataclass
- 所有字段通过构造器传入，不可变设计
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ExtractedEntity:
    """抽取的实体值对象

    Attributes:
        name: 实体名称
        entity_type: 实体类型（PERSON/ORG/LOC/PRODUCT/CONCEPT/DATE/AMOUNT/PERCENT）
        confidence: 置信度 [0.0, 1.0]
        extraction_source: 来源（"rule" / "llm" / "hybrid"）
        metadata: 额外元数据（位置、频率等）
        normalized_name: 归一化名称（可选）
    """

    name: str = ""
    entity_type: str = ""
    confidence: float = 0.0
    extraction_source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    normalized_name: str = ""


@dataclass(frozen=True)
class ExtractedRelation:
    """抽取的关系值对象

    Attributes:
        source: 源实体名称（与 target 配对使用）
        target: 目标实体名称
        relation_type: 关系类型（MENTIONS/DEPENDS_ON/RELATES_TO/PART_OF/INFLUENCES/CONTRADICTS）
        confidence: 置信度 [0.0, 1.0]
        extraction_source: 来源标识（"rule"/"llm"/"hybrid"），与 source 字段语义不同
        metadata: 额外元数据
    """

    source: str = ""
    target: str = ""
    relation_type: str = ""
    confidence: float = 0.0
    extraction_source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractionResult:
    """实体抽取结果值对象

    Attributes:
        entities: 抽取的实体列表
        relations: 抽取的关系列表
        extraction_metadata: 抽取元数据（耗时、策略、token 消耗等）
    """

    entities: tuple[ExtractedEntity, ...] = field(default_factory=tuple)
    relations: tuple[ExtractedRelation, ...] = field(default_factory=tuple)
    extraction_metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class EntityArbitratorPort(Protocol):
    """实体抽取冲突仲裁端口协议

    定义规则基 + LLM 双路抽取结果的融合仲裁接口。
    领域层定义仲裁契约，基础设施层提供具体实现。

    设计约束：
    - 应用层编排服务通过本端口依赖仲裁能力，不直接依赖基础设施实现
    - 实现类负责实体合并、置信度加权平均、关系去重等融合逻辑
    """

    def arbitrate(
        self,
        rule_result: ExtractionResult,
        llm_result: ExtractionResult,
    ) -> ExtractionResult:
        """执行冲突仲裁

        Args:
            rule_result: 规则基抽取结果
            llm_result: LLM 语义抽取结果

        Returns:
            融合后的 ExtractionResult
        """
        ...


@runtime_checkable
class EntityExtractionPort(Protocol):
    """实体抽取端口协议

    定义统一的实体抽取接口，支持规则基和 LLM 语义两种抽取策略。
    所有实现类必须提供 extract_entities 方法。
    """

    async def extract_entities(
        self,
        content: str,
        domain_context: dict | None = None,
    ) -> ExtractionResult:
        """执行实体抽取

        Args:
            content: 待抽取的文本内容
            domain_context: 领域上下文（可选，包含领域词典、领域类型等）

        Returns:
            ExtractionResult 包含抽取的实体和关系列表

        Raises:
            EntityExtractionError: 抽取过程中发生不可恢复的错误
        """
        ...


__all__ = [
    "EntityExtractionPort",
    "EntityArbitratorPort",
    "ExtractedEntity",
    "ExtractedRelation",
    "ExtractionResult",
]
