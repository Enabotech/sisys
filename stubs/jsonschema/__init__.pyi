"""jsonschema 类型存根（PEP 561）

为 jsonschema ^4.19 提供最小化类型定义，覆盖项目实际使用的 API 表面：
- Story 4.1 验收测试：Draft7Validator.check_schema() 静态方法 + SchemaError
- Story 4.3 端口实现：Draft7Validator 实例化 + iter_errors() / validate() + ValidationError
"""

from typing import Any, Iterable

class Draft7Validator:
    """Draft-07 验证器（项目实际使用的最小化子集）."""

    @staticmethod
    def check_schema(schema: dict[str, Any]) -> None:
        """校验 schema 结构是否符合 Draft-07 meta-schema.

        Raises:
            jsonschema.SchemaError: schema 结构非法时抛出
        """
        ...

    def __init__(self, schema: dict[str, Any]) -> None:
        """初始化 Draft-07 验证器实例（绑定 schema 供后续 validate/iter_errors 使用）"""
        ...

    def iter_errors(self, instance: Any) -> Iterable["ValidationError"]:
        """迭代校验 instance 与 schema 的所有违规（供批量错误反馈，不立即抛错）

        Args:
            instance: 待校验的数据实例

        Returns:
            ValidationError 迭代器(可能为空,空表示通过)
        """
        ...

    def validate(self, instance: Any) -> None:
        """校验 instance 与 schema(首个错误立即抛 ValidationError)

        Args:
            instance: 待校验的数据实例

        Raises:
            ValidationError: 校验失败
        """
        ...

class SchemaError(Exception):
    """Schema 结构错误异常."""

    ...

class ValidationError(Exception):
    """Schema 数据校验错误异常（与 SchemaError 区分）.

    Attributes:
        message: 错误描述
        path: JSON Pointer 形式的路径列表(逐层)
        validator: 触发错误的校验器名称(如 "type", "required")
        instance: 触发错误的实际值
        schema: 触发错误的 schema 子树
    """

    message: str
    path: list[Any]
    absolute_path: list[Any]
    validator: str
    instance: Any
    schema: dict[str, Any]

    ...
