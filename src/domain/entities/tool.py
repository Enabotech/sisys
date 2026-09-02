"""领域层工具实体模块

定义工具领域实体，包含唯一标识符、I/O 模式和执行器
"""

from __future__ import annotations

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


@dataclass
class Tool:
    """工具实体，包含唯一标识符、I/O 模式和执行器

    不变量约束:
    - tool_id 必须为有效 UUID
    - name 不能为空
    - input_schema 必须为有效 JSON Schema 字典
    - output_schema 必须为有效 JSON Schema 字典
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
        return True
