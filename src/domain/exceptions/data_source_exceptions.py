"""领域层数据源异常模块（Story 4.1b — Skills 数据采集基础设施）

data_source 子域（410-419）共 4 个异常：
- EXCEPTION_410 DataSourceError：数据源通用错误基类
- EXCEPTION_411 DataSourceUnavailableError：数据源不可用（5xx/连接失败/熔断断开）
- EXCEPTION_412 DataSourceRateLimitError：数据源限流（429）
- EXCEPTION_413 DataSourceResponseError：响应解析失败（不可重试）

子域范围注册于 _code_ranges.py CODE_RANGES["data_source"] = (410, 419)。
注意：本文件仅定义通用四元组；数据源超时复用 EXCEPTION_302（TimeoutError），
配置缺失复用 EXCEPTION_101（ConfigurationError），白名单违规复用 EXCEPTION_207
（BusinessRuleViolationError）——禁止同义异常重复定义。
"""

from __future__ import annotations

from src.domain.exceptions.external_exceptions import ExternalException


class DataSourceError(ExternalException):
    """数据源通用错误基类（具体异常的兜底父类）

    Attributes:
        code: 错误码 EXCEPTION_410
        message: 默认消息
    """

    code = "EXCEPTION_410"
    message = "Data source error"


class DataSourceUnavailableError(DataSourceError):
    """数据源不可用（5xx/连接失败/熔断断开，重试耗尽后抛出）

    Attributes:
        code: 错误码 EXCEPTION_411
        message: 默认消息
    """

    code = "EXCEPTION_411"
    message = "Data source unavailable"


class DataSourceRateLimitError(DataSourceError):
    """数据源限流（HTTP 429，如 NewsAPI 免费 100 次/天）

    Attributes:
        code: 错误码 EXCEPTION_412
        message: 默认消息
    """

    code = "EXCEPTION_412"
    message = "Data source rate limited"


class DataSourceResponseError(DataSourceError):
    """数据源响应解析失败（非法 JSON/required_fields 缺失/schema 不符，不可重试）

    Attributes:
        code: 错误码 EXCEPTION_413
        message: 默认消息
    """

    code = "EXCEPTION_413"
    message = "Data source response error"


__all__ = [
    "DataSourceError",
    "DataSourceRateLimitError",
    "DataSourceResponseError",
    "DataSourceUnavailableError",
]
