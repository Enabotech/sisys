"""领域层工具实体模块

定义工具领域实体，包含唯一标识符、I/O 模式和执行器
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from src.domain.exceptions import EntityValidationError


class ToolStatus(str, Enum):
    """工具生命周期状态枚举"""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    MAINTENANCE = "maintenance"


class ToolCategory(str, Enum):
    """工具分类枚举

    两维度分类体系：
    - 原有分类：按功能类型划分
      （ANALYSIS/GENERATION/VALIDATION/VISUALIZATION/OTHER）
    - 新增战略分类：按业务领域划分
      （ENVIRONMENT_ANALYSIS/COMPETITIVE_ANALYSIS/STRATEGIC_SELECTION/
       BUSINESS_MODEL/EXECUTION_MANAGEMENT）
    两者维度不同，共存不冲突。
    """

    # 原有功能分类
    ANALYSIS = "analysis"
    GENERATION = "generation"
    VALIDATION = "validation"
    VISUALIZATION = "visualization"
    OTHER = "other"
    # 战略工具箱业务领域分类
    ENVIRONMENT_ANALYSIS = "environment_analysis"
    COMPETITIVE_ANALYSIS = "competitive_analysis"
    STRATEGIC_SELECTION = "strategic_selection"
    BUSINESS_MODEL = "business_model"
    EXECUTION_MANAGEMENT = "execution_management"


_NAME_MAX_LENGTH = 200
_DESCRIPTION_MAX_LENGTH = 500
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
_JSON_SCHEMA_KEYWORDS = frozenset(
    {"type", "properties", "$ref", "allOf", "anyOf", "oneOf"},
)


@dataclass
class Tool:
    """工具实体，包含唯一标识符、I/O 模式和执行器

    不变量约束:
    - tool_id 必须为有效 UUID
    - name 非空且长度不超过 200 字符
    - description 长度不超过 500 字符
    - category 必须为 ToolCategory 枚举值
    - status 必须为 ToolStatus 枚举值
    - version 必须符合 SemVer X.Y.Z 格式
    - created_at / updated_at 必须 timezone-aware 且 updated_at &gt;= created_at
    - input_schema / output_schema 必须为 dict（空 dict 合法）；
      非空时需包含 type/properties/$ref/allOf/anyOf/oneOf 至少一个关键词
    """

    tool_id: uuid.UUID
    name: str
    description: str = ""
    category: ToolCategory = ToolCategory.OTHER
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    status: ToolStatus = ToolStatus.ACTIVE
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """构造时强制校验所有不变量

        DDD Aggregate Root 不变量强制原则：实体在构造时即保证不变量满足，
        避免半成品实体存在（Eric Evans《DDD》第 5 章 / Vaughn Vernon《IDDD》）。
        与项目惯例对齐（AuditLog / MemoryMetadata / MemoryChangeHistory）。
        """
        self.validate()

    def validate(self) -> bool:
        """验证不变量约束

        Returns:
            所有不变量满足时返回 True

        Raises:
            EntityValidationError: 任何不变量违反时抛出
        """
        if not isinstance(self.tool_id, uuid.UUID):
            raise EntityValidationError(
                message="tool_id must be a valid UUID",
                context={"entity": "Tool", "field": "tool_id"},
            )
        if not self.name or not self.name.strip():
            raise EntityValidationError(
                message="name must not be empty",
                context={"entity": "Tool", "field": "name"},
            )
        if len(self.name) > _NAME_MAX_LENGTH:
            raise EntityValidationError(
                message=f"name 长度不能超过 {_NAME_MAX_LENGTH} 字符",
                context={"entity": "Tool", "field": "name", "length": len(self.name)},
            )
        if len(self.description) > _DESCRIPTION_MAX_LENGTH:
            raise EntityValidationError(
                message=f"description 长度不能超过 {_DESCRIPTION_MAX_LENGTH} 字符",
                context={
                    "entity": "Tool",
                    "field": "description",
                    "length": len(self.description),
                },
            )
        if not isinstance(self.category, ToolCategory):
            raise EntityValidationError(
                message="category 必须为 ToolCategory 枚举值",
                context={
                    "entity": "Tool",
                    "field": "category",
                    "value": self.category,
                },
            )
        if not isinstance(self.status, ToolStatus):
            raise EntityValidationError(
                message="status 必须为 ToolStatus 枚举值",
                context={
                    "entity": "Tool",
                    "field": "status",
                    "value": self.status,
                },
            )
        if not isinstance(self.version, str) or not _SEMVER_PATTERN.match(self.version):
            raise EntityValidationError(
                message="version 必须符合 SemVer X.Y.Z 格式",
                context={"entity": "Tool", "field": "version", "value": self.version},
            )
        if not isinstance(self.input_schema, dict):
            raise EntityValidationError(
                message="input_schema must be a dict",
                context={"entity": "Tool", "field": "input_schema"},
            )
        if not isinstance(self.output_schema, dict):
            raise EntityValidationError(
                message="output_schema must be a dict",
                context={"entity": "Tool", "field": "output_schema"},
            )
        # 空 schema 视为合法（不强制关键词）；非空 schema 需含 JSON Schema 关键词
        if self.input_schema and not (_JSON_SCHEMA_KEYWORDS & set(self.input_schema.keys())):
            raise EntityValidationError(
                message="input_schema 非空时必须包含 JSON Schema 关键词之一",
                context={
                    "entity": "Tool",
                    "field": "input_schema",
                    "required_keywords": sorted(_JSON_SCHEMA_KEYWORDS),
                    "actual_keys": sorted(self.input_schema.keys()),
                },
            )
        if self.output_schema and not (_JSON_SCHEMA_KEYWORDS & set(self.output_schema.keys())):
            raise EntityValidationError(
                message="output_schema 非空时必须包含 JSON Schema 关键词之一",
                context={
                    "entity": "Tool",
                    "field": "output_schema",
                    "required_keywords": sorted(_JSON_SCHEMA_KEYWORDS),
                    "actual_keys": sorted(self.output_schema.keys()),
                },
            )
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise EntityValidationError(
                message="created_at/updated_at 必须为 timezone-aware",
                context={
                    "entity": "Tool",
                    "created_at_tzinfo": self.created_at.tzinfo,
                    "updated_at_tzinfo": self.updated_at.tzinfo,
                },
            )
        if self.updated_at < self.created_at:
            raise EntityValidationError(
                message="updated_at 不能早于 created_at",
                context={
                    "entity": "Tool",
                    "created_at": self.created_at.isoformat(),
                    "updated_at": self.updated_at.isoformat(),
                },
            )
        return True
