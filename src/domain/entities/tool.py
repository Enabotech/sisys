"""领域层工具实体模块

定义工具领域实体，包含唯一标识符、I/O 模式和执行器

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class ToolStatus(str, Enum):
    """工具生命周期状态枚举"""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    MAINTENANCE = "maintenance"


class ToolCategory(str, Enum):
    """工具分类枚举"""

    ANALYSIS = "analysis"
    GENERATION = "generation"
    VALIDATION = "validation"
    VISUALIZATION = "visualization"
    OTHER = "other"


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
            ValueError: 任何不变量违反时抛出
        """
        if not isinstance(self.tool_id, uuid.UUID):
            raise ValueError("tool_id must be a valid UUID")
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        if not isinstance(self.input_schema, dict):
            raise ValueError("input_schema must be a dict")
        if not isinstance(self.output_schema, dict):
            raise ValueError("output_schema must be a dict")
        return True
