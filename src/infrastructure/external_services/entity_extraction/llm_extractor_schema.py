"""LLM 实体抽取 Schema 模块

定义 LLM 实体抽取的 Pydantic Schema，用于 LLMClientPort.structured_generate() 的 response_schema。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedEntitySchema(BaseModel):
    """单个实体 Schema"""

    name: str = Field(description="实体名称")
    entity_type: str = Field(description="实体类型: PERSON/ORG/LOC/PRODUCT/CONCEPT/DATE/AMOUNT/PERCENT")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度 0.0-1.0")
    normalized_name: str = Field(default="", description="归一化后的实体名称（可选）")


class ExtractedRelationSchema(BaseModel):
    """单个关系 Schema"""

    source: str = Field(description="源实体名称")
    target: str = Field(description="目标实体名称")
    relation_type: str = Field(description="关系类型: MENTIONS/DEPENDS_ON/RELATES_TO/PART_OF/INFLUENCES/CONTRADICTS")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度 0.0-1.0")


class EntityExtractionSchema(BaseModel):
    """实体抽取结果 Schema"""

    entities: list[ExtractedEntitySchema] = Field(description="抽取的实体列表")
    relations: list[ExtractedRelationSchema] = Field(description="抽取的关系列表")
