"""
sisys - Not Found Error.

未找到错误定义。
"""

from src.domain.exceptions.base import DomainError


class NotFoundError(DomainError):
    """
    未找到错误。

    当请求的资源不存在时抛出此异常。
    """

    def __init__(self, entity_type: str, entity_id: str):
        """
        初始化未找到错误。

        Args:
            entity_type: 实体类型
            entity_id: 实体 ID
        """
        message = f"{entity_type} 未找到 (ID: {entity_id})"
        super().__init__(message, code="NOT_FOUND")
        self._entity_type = entity_type
        self._entity_id = entity_id

    @property
    def entity_type(self) -> str:
        """返回实体类型。"""
        return self._entity_type

    @property
    def entity_id(self) -> str:
        """返回实体 ID。"""
        return self._entity_id
