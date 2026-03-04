"""
sisys - Domain Exceptions Base.

领域异常基类。
"""


class DomainError(Exception):
    """领域错误基类。"""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self._message = message
        self._code = code or self.__class__.__name__.upper()

    @property
    def message(self) -> str:
        return self._message

    @property
    def code(self) -> str:
        return self._code


class DomainValidationError(DomainError):
    """领域验证错误。"""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message, code="VALIDATION_ERROR")
        self._field = field

    @property
    def field(self) -> str | None:
        return self._field


# 导入 ValidationError 作为别名（兼容旧代码）
ValidationError = DomainValidationError
