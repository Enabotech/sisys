"""外部 SDK 错误到异常的标准化映射.

优先使用类型匹配（isinstance）而非字符串匹配
对于 MinIO S3Error，应使用 error.code 属性直接映射
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable, TypeVar

from src.domain.exceptions import (
    ConflictError,
    InvalidStateError,
    MessageBusError,
    NetworkError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    SystemException,
    ThirdPartyError,
    TimeoutError,
    ValidationError,
)
from src.domain.exceptions.base_exceptions import BaseException

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorMapper:
    """外部错误标准化映射器.

    使用示例：
        try:
            await client.stat(bucket, object_key)
        except S3Error as e:
            raise ErrorMapper.map_s3_error(e.code, e.message) from e
    """

    # MinIO S3Error 映射
    S3_ERROR_MAP: dict[str, type[BaseException]] = {
        "nosuchbucket": NotFoundError,
        "nosuchkey": NotFoundError,
        "nosuchlifecycleconfiguration": NotFoundError,
        "bucketalreadyexists": ConflictError,
        "bucketalreadyownedbyyou": ConflictError,
        "accessdenied": PermissionDeniedError,
        "forbidden": PermissionDeniedError,
        "invalidobjectstate": InvalidStateError,
        "objectlockconfigurationnotfound": InvalidStateError,
        "requesttimeout": TimeoutError,
        "serviceunavailable": ServiceUnavailableError,
        "internalerror": ThirdPartyError,
        "nosuchupload": NotFoundError,
        "nosuchversion": NotFoundError,
        "entitytoolarge": ValidationError,
        "methodnotallowed": ThirdPartyError,
        "slowdown": ServiceUnavailableError,
    }

    # RabbitMQ 错误映射
    RABBITMQ_ERROR_MAP: dict[str, type[BaseException]] = {
        "ConnectionError": NetworkError,
        "ChannelError": MessageBusError,
        "TimeoutError": TimeoutError,
    }

    # Redis 错误映射
    REDIS_ERROR_MAP: dict[str, type[BaseException]] = {
        "ConnectionError": NetworkError,
        "TimeoutError": TimeoutError,
        "ClusterDownError": ServiceUnavailableError,
    }

    @classmethod
    def map_s3_error(cls, code: str, message: str | None = None) -> BaseException:
        """映射 MinIO S3 错误.

        Args:
            code: S3Error.code 属性值（如 "NoSuchBucket"）
            message: 原始错误消息

        Returns:
            对应的异常实例
        """
        exc_class = cls.S3_ERROR_MAP.get(code.lower(), ThirdPartyError)
        if exc_class is ThirdPartyError:
            logger.warning("Unknown S3 error code: %s, defaulting to ThirdPartyError", code)
        return exc_class(message=message or f"S3 error: {code}")

    @classmethod
    def map_rabbitmq_error(cls, error_type: str, message: str | None = None) -> BaseException:
        """映射 RabbitMQ 错误."""
        exc_class = cls.RABBITMQ_ERROR_MAP.get(error_type, MessageBusError)
        return exc_class(message=message or f"RabbitMQ error: {error_type}")

    @classmethod
    def map_redis_error(cls, error_type: str, message: str | None = None) -> BaseException:
        """映射 Redis 错误."""
        exc_class = cls.REDIS_ERROR_MAP.get(error_type, SystemException)
        return exc_class(message=message or f"Redis error: {error_type}")

    @classmethod
    def wrap_external_error(
        cls,
        error: Exception,
        target_exc_class: type[BaseException],
        context: dict | None = None,
    ) -> BaseException:
        """包装外部错误为异常.

        推荐用法：
            try:
                await external_call()
            except SomeError as e:
                raise ErrorMapper.wrap_external_error(
                    e, TargetException, {"operation": "xxx"}
                ) from e
        """
        logger.warning(
            "Wrapping external error: %s -> %s",
            type(error).__name__,
            target_exc_class.__name__,
        )
        return target_exc_class(
            message=str(error),
            cause=error if isinstance(error, BaseException) else None,
            context={**(context or {}), "original_error_type": type(error).__name__},
        )


def with_error_mapping(
    error_map: dict[str, type[BaseException]],
    default_exc: type[BaseException] = ThirdPartyError,
    *,
    exact_match: bool = False,
) -> Callable:
    """装饰器：自动映射外部错误

    注意：这是兜底方案。优先使用 ErrorMapper.map_* 方法直接映射

    Args:
        error_map: 错误码到异常类的映射
        default_exc: 默认异常类
        exact_match: True 时使用精确匹配，False 时使用子串匹配
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_str = str(e)
                for key, exc_class in error_map.items():
                    if exact_match:
                        if key.lower() == error_str.lower():
                            raise exc_class(
                                message=str(e),
                                cause=e if isinstance(e, BaseException) else None,
                                context={"original_error_type": type(e).__name__},
                            ) from e
                    else:
                        if key.lower() in error_str.lower():
                            raise exc_class(
                                message=str(e),
                                cause=e if isinstance(e, BaseException) else None,
                                context={"original_error_type": type(e).__name__},
                            ) from e
                raise default_exc(
                    message=str(e),
                    cause=e if isinstance(e, BaseException) else None,
                    context={"original_error_type": type(e).__name__},
                ) from e

        return wrapper

    return decorator
