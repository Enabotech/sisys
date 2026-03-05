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

    def __init__(self, entity_type: str | None = None, entity_id: str | None = None, message: str | None = None):
        """
        初始化未找到错误。

        Args:
            entity_type: 实体类型（可选）
            entity_id: 实体 ID（可选）
            message: 自定义消息（可选），如果提供则使用自定义消息

        Example:
            # 方式 1：使用 entity_type 和 entity_id
            raise NotFoundError(entity_type="PlanRepository", entity_id="123")
            # 消息："PlanRepository 未找到 (ID: 123)"

            # 方式 2：使用自定义消息
            raise NotFoundError(message="PlanRepository with id 123 not found")
            # 消息："PlanRepository with id 123 not found"
        """
        if message is not None:
            # 使用自定义消息
            super().__init__(message, code="NOT_FOUND")
            self._entity_type = entity_type or "Unknown"
            self._entity_id = entity_id or "Unknown"
        elif entity_type is not None and entity_id is not None:
            # 使用默认消息格式
            message = f"{entity_type} 未找到 (ID: {entity_id})"
            super().__init__(message, code="NOT_FOUND")
            self._entity_type = entity_type
            self._entity_id = entity_id
        else:
            # 都没有提供，使用默认消息
            message = "Resource not found"
            super().__init__(message, code="NOT_FOUND")
            self._entity_type = "Unknown"
            self._entity_id = "Unknown"

    @property
    def entity_type(self) -> str:
        """返回实体类型。"""
        return self._entity_type

    @property
    def entity_id(self) -> str:
        """返回实体 ID。"""
        return self._entity_id
