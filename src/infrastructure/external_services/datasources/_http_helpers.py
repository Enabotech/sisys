"""基础设施层数据源适配器共享 HTTP 韧性助手（Story 4.1b）

纯函数助手（非抽象基类，对齐 Story 4.1b 设计决策：禁止预先抽 base.py 继承层级）：
- request_json_with_resilience: httpx + tenacity 指数退避 + CircuitBreaker + 内联异常映射
  （范本：src/infrastructure/external_services/embedding/embedding_api_client.py）

异常映射契约（data_source 子域）：
- httpx.TimeoutException → TimeoutError（EXCEPTION_302，重试耗尽后）
- httpx.TransportError → DataSourceUnavailableError（EXCEPTION_411，重试耗尽后）
- HTTP 5xx → 可重试，耗尽后 DataSourceUnavailableError（EXCEPTION_411）
- HTTP 429 → DataSourceRateLimitError（EXCEPTION_412，不重试）
- HTTP 其他 4xx → DataSourceResponseError（EXCEPTION_413，确定性错误不重试）
- JSON 解析失败 → DataSourceResponseError（EXCEPTION_413，不重试、不计熔断）
- CircuitBreakerOpenError → DataSourceUnavailableError（EXCEPTION_411，快速失败）
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.domain.exceptions import (
    DataSourceRateLimitError,
    DataSourceResponseError,
    DataSourceUnavailableError,
    TimeoutError,
)
from src.infrastructure.external_services.embedding.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
)

logger = logging.getLogger(__name__)

# 可恢复的服务端 HTTP 状态码（瞬时故障可自行恢复）
RETRYABLE_STATUS_CODES = frozenset({500, 502, 503, 504})


def is_retryable_http_error(exception: BaseException) -> bool:
    """判断异常是否可重试（白名单模式，对齐 embedding _is_retryable_http_error）

    规则：
    - httpx.TimeoutException → 可重试（网络抖动）
    - httpx.TransportError → 可重试（临时连接故障）
    - HTTPStatusError 且状态码 ∈ RETRYABLE_STATUS_CODES → 可重试
    - 其他（含 429/4xx/解析错误）→ 不可重试（确定性失败，快速抛出）
    """
    if isinstance(exception, httpx.TimeoutException):
        return True
    if isinstance(exception, httpx.TransportError):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRYABLE_STATUS_CODES
    return False


async def request_json_with_resilience(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    source_name: str,
    circuit_breaker: CircuitBreaker,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 4.0,
) -> Any:
    """带韧性（重试 + 熔断）的 JSON HTTP 请求

    Args:
        client: httpx 异步客户端（调用方管理生命周期）
        method: HTTP 方法（GET/POST）
        url: 请求路径或完整 URL（相对路径走 client.base_url）
        source_name: 数据源名称（异常 context，禁止含敏感信息）
        circuit_breaker: 熔断器实例
        params: URL 查询参数（禁止放入 API Key——Key 走 headers/json_body）
        json_body: POST JSON 请求体
        headers: 请求头（API Key 应走此处，避免 URL 泄露）
        max_attempts: 最大重试次数（含首次，默认 3）
        min_wait: 最小退避秒数
        max_wait: 最大退避秒数

    Returns:
        解析后的 JSON（dict 或 list）

    Raises:
        TimeoutError: 请求超时（重试耗尽后，EXCEPTION_302）
        DataSourceUnavailableError: 5xx/连接失败重试耗尽或熔断断开（EXCEPTION_411）
        DataSourceRateLimitError: HTTP 429 限流（EXCEPTION_412，不重试）
        DataSourceResponseError: 4xx 或 JSON 解析失败（EXCEPTION_413，不重试）
    """
    # 第 1 步：熔断器快速失败
    try:
        circuit_breaker.before_call()
    except CircuitBreakerOpenError as e:
        raise DataSourceUnavailableError(
            message=f"数据源 {source_name} 熔断器已断开",
            context={"source_name": source_name},
            cause=e,
        ) from e

    # 第 2 步：指数退避重试（重试层只让原始 httpx 异常传播，耗尽后再映射）
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception(is_retryable_http_error),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                resp = await client.request(method, url, params=params, json=json_body, headers=headers)
                # 429/4xx 在此显式转换（tenacity 白名单不含 → 不重试）
                if resp.status_code == 429:
                    raise DataSourceRateLimitError(
                        message=f"数据源 {source_name} 触发限流（HTTP 429）",
                        context={"source_name": source_name, "status_code": 429},
                    )
                if 400 <= resp.status_code < 500:
                    raise DataSourceResponseError(
                        message=f"数据源 {source_name} 返回客户端错误（HTTP {resp.status_code}）",
                        context={"source_name": source_name, "status_code": resp.status_code},
                    )
                resp.raise_for_status()
                data = resp.json()
    except httpx.TimeoutException as e:
        circuit_breaker.on_failure()
        raise TimeoutError(
            message=f"数据源 {source_name} 请求超时",
            context={"source_name": source_name},
            cause=e,
        ) from e
    except httpx.TransportError as e:
        circuit_breaker.on_failure()
        raise DataSourceUnavailableError(
            message=f"数据源 {source_name} 连接失败（重试耗尽）",
            context={"source_name": source_name},
            cause=e,
        ) from e
    except httpx.HTTPStatusError as e:
        circuit_breaker.on_failure()
        raise DataSourceUnavailableError(
            message=f"数据源 {source_name} 服务端错误（HTTP {e.response.status_code}，重试耗尽）",
            context={"source_name": source_name, "status_code": e.response.status_code},
            cause=e,
        ) from e
    except ValueError as e:
        # JSON 解析失败：不重试，不记熔断器（对端响应格式问题）
        raise DataSourceResponseError(
            message=f"数据源 {source_name} 响应 JSON 解析失败",
            context={"source_name": source_name},
            cause=e,
        ) from e

    # 成功 → 通知熔断器
    circuit_breaker.on_success()
    return data


__all__ = ["RETRYABLE_STATUS_CODES", "is_retryable_http_error", "request_json_with_resilience"]
