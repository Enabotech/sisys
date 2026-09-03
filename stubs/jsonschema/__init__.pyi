"""jsonschema 类型存根（PEP 561）

为 jsonschema ^4.19 提供最小化类型定义，覆盖 Story 4.1 验收测试中
Draft7Validator.check_schema() 的使用。

来源:
  - tests/acceptance/test_acceptance_strategic_tool_registration.py
"""

from typing import Any

class Draft7Validator:
    """Draft-07 验证器（最小化子集）."""

    @staticmethod
    def check_schema(schema: dict[str, Any]) -> None:
        """校验 schema 结构是否符合 Draft-07 meta-schema.

        Raises:
            jsonschema.SchemaError: schema 结构非法时抛出
        """
        ...

class SchemaError(Exception):
    """Schema 结构错误异常."""
    ...
