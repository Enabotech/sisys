"""基础设施层数据源适配器共享 HTTP 韧性助手（Story 4.1b）

纯函数助手（非抽象基类，对齐 Story 4.1b 设计决策：禁止预先抽 base.py 继承层级）：
- request_json_with_resilience: httpx + tenacity 指数退避 + CircuitBreaker + 内联异常映射
  （范本：src/infrastructure/external_services/embedding/embedding_api_client.py）

异常映射契约（data_source 子域）：
- httpx.TimeoutException → TimeoutError（EXCEPTION_302，重试耗尽后）
  （注：TimeoutException 是 TransportError 的子类——TimeoutException 分支必须在前，顺序是硬约束）
- httpx.DecodingError → DataSourceResponseError（EXCEPTION_413，响应体解码失败属确定性错误，
  不重试不计熔断——对齐「响应解析类问题不计熔断」契约）
- httpx.InvalidURL → ConfigurationError（EXCEPTION_101，URL 配置错误属确定性错误，不重试不计熔断）
- httpx.UnsupportedProtocol → ConfigurationError（EXCEPTION_101，URL scheme 缺失属确定性配置错误，
  不重试不计熔断——R3-4 K1：原 ⊂ TransportError 被白名单重试且计熔断，已对齐 InvalidURL 口径）
- httpx.RequestError（其余传输类：TransportError 子类/TooManyRedirects 等）→
  DataSourceUnavailableError（EXCEPTION_411，重试耗尽后，计熔断）
- HTTP 5xx → 可重试，耗尽后 DataSourceUnavailableError（EXCEPTION_411）
- HTTP 3xx → DataSourceResponseError（EXCEPTION_413，端点迁移/配置漂移，确定性错误不重试不计熔断）
- HTTP 429 → DataSourceRateLimitError（EXCEPTION_412，不重试）
- HTTP 其他 4xx → DataSourceResponseError（EXCEPTION_413，确定性错误不重试）
- 401/403 → ConfigurationError（EXCEPTION_101，API Key 凭证问题）
- JSON 解析失败 → DataSourceResponseError（EXCEPTION_413，不重试、不计熔断）
- CircuitBreakerOpenError → DataSourceUnavailableError（EXCEPTION_411，快速失败）

熔断器探测槽位语义（R3-P0-1）：全部确定性错误路径（429/401/403/3xx/4xx/
DecodingError/InvalidURL/JSON 解析失败）经 on_ignored() 释放半开探测槽位——
请求已收到确定性结果（服务可连通），不计熔断统计；仅传输类瞬时故障
（超时/连接失败/5xx）经 on_failure() 推进熔断统计。

安全约束：客户端禁止开启 follow_redirects——newsapi/tavily 等 Key 走 header/body，
跨域重定向转发会造成 Key 泄露面（httpx 仅对 Authorization 头做跨域降级保护）。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import quote

import httpx
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.domain.exceptions import (
    ConfigurationError,
    DataSourceRateLimitError,
    DataSourceResponseError,
    DataSourceUnavailableError,
    TimeoutError,
    ValidationError,
)
from src.infrastructure.external_services.embedding.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
)

logger = logging.getLogger(__name__)

# 可恢复的服务端 HTTP 状态码（瞬时故障可自行恢复）
RETRYABLE_STATUS_CODES = frozenset({500, 502, 503, 504})


def quote_path_segment(segment: str) -> str:
    """URL 路径段安全编码（R2-2-B6/H4：LLM 不可信输入注入防护）

    quote(safe="") 编码全部保留字符（含 / ? # 空格），防空格/分隔符注入；
    显式拒绝 ".." 段（quote 对点号零防护——点为 RFC 3986 unreserved）防路径穿越。

    Args:
        segment: 单个路径段（禁止含 /——多段路径由调用方 split 后逐段编码）

    Returns:
        percent-encoded 路径段（合法指标代码如 NY.GDP.MKTP.CD / nama_10_gdp 原样通过）

    Raises:
        DataSourceResponseError: 段含 ".."（EXCEPTION_413，确定性错误）
    """
    if ".." in segment:
        raise DataSourceResponseError(
            message="数据源查询路径段含非法穿越序列（..）",
            context={"segment": segment[:100]},
        )
    return quote(segment, safe="")


def parse_int_param(
    params_dict: dict[str, str],
    key: str,
    default: int,
    *,
    source_name: str,
) -> int:
    """从查询参数字典解析整型参数（R3-2 红线组 G4：内置 ValueError 前置为 ValidationError）

    DataSourceQuery.parameters 类型注解 tuple[tuple[str, str], ...]——"abc"/"10.5"
    是合法 str 输入，裸 int() 会抛内置 ValueError 逃逸领域异常体系（红线破口）。
    参数属调用方输入错误（非响应解析失败），归 ValidationError(201)——语义为
    HTTP 400 且在发起外部请求前抛出（零配额消耗、不重试、不污染熔断）。

    Args:
        params_dict: 查询参数字典（DataSourceQuery.parameters 转换而来）
        key: 参数名（如 "page_size"/"max_results"）
        default: 参数缺失时的回退默认值
        source_name: 数据源名称（异常 context，便于按源定位）

    Returns:
        解析后的整型值（缺失回退 default）

    Raises:
        ValidationError: 参数值非整数（EXCEPTION_201，不消耗外部配额）
    """
    raw = params_dict.get(key, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            message=f"查询参数 {key} 必须为整数，实际 {raw!r}",
            context={"source_name": source_name, "field": key, "value": str(raw)},
            cause=exc,
        ) from exc


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
    # URL scheme 缺失/不支持：确定性配置错误（对齐 InvalidURL 101 口径，R3-4 K1）——
    # UnsupportedProtocol ⊂ TransportError，排除分支必须位于 TransportError 检查之前
    if isinstance(exception, httpx.UnsupportedProtocol):
        return False
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
    form_data: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 4.0,
    pre_request: Callable[[], Awaitable[None]] | None = None,
) -> Any:
    """带韧性（重试 + 熔断）的 JSON HTTP 请求

    Args:
        client: httpx 异步客户端（调用方管理生命周期）
        method: HTTP 方法（GET/POST）
        url: 请求路径或完整 URL（相对路径走 client.base_url）
        source_name: 数据源名称（异常 context，禁止含敏感信息）
        circuit_breaker: 熔断器实例
        params: URL 查询参数（禁止放入 API Key——Key 走 headers/json_body/form_data）
        json_body: POST JSON 请求体（与 form_data 互斥——二者仅传其一；同传时运行时
            防线抛 ValidationError 拦截，第三周期 T1-F8 前为 httpx data 优先静默
            忽略 json_body 的隐蔽故障面）
        form_data: POST form 请求体（application/x-www-form-urlencoded——OAuth2 token
            端点 RFC 7523 形态，assertion 等短时效凭证禁入 URL query 走此通道）
        headers: 请求头（API Key 应走此处，避免 URL 泄露）
        max_attempts: 最大重试次数（含首次，默认 3）
        min_wait: 最小退避秒数
        max_wait: 最大退避秒数
        pre_request: 每次真实 HTTP 尝试前的前置动作（限速等；None 不执行——重试同属真实
            请求，限速语义须覆盖每次 attempt）

    Returns:
        解析后的 JSON（dict 或 list）

    Raises:
        ValidationError: json_body 与 form_data 同传（EXCEPTION_201——调用方参数域
            错误，与 parse_int_param 同族；编程错误在熔断统计前拦截）
        TimeoutError: 请求超时（重试耗尽后，EXCEPTION_302）
        DataSourceUnavailableError: 5xx/连接失败重试耗尽或熔断断开（EXCEPTION_411）
        DataSourceRateLimitError: HTTP 429 限流（EXCEPTION_412，不重试）
        DataSourceResponseError: 4xx/3xx/JSON 或响应体解码失败（EXCEPTION_413，不重试）
        ConfigurationError: 401/403（API Key 凭证问题）或 URL 配置畸形（EXCEPTION_101）
    """
    # 第 0 步：请求体互斥防线（T1-F8——编程错误不消耗熔断统计，先于 before_call）
    if form_data is not None and json_body is not None:
        raise ValidationError(
            message=(
                f"数据源 {source_name!r} 请求参数错误：json_body 与 form_data 互斥（二者仅传其一）——"
                "同传时 httpx data 优先、json_body 会被静默忽略"
            ),
            context={
                "source_name": source_name,
                "json_body_keys": sorted(json_body),
                "form_data_keys": sorted(form_data),
            },
        )

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
                # 每次真实 HTTP 尝试前的挂载点（限速等前置动作——重试同属真实请求，4.1f R2-F2：
                # sec-edgar 滑动窗限速经此下沉，防 tenacity 重试绕过 8 rps 上限）
                if pre_request is not None:
                    await pre_request()
                resp = await client.request(method, url, params=params, json=json_body, data=form_data, headers=headers)
                # 429/4xx 在此显式转换（tenacity 白名单不含 → 不重试）
                if resp.status_code == 429:
                    raise DataSourceRateLimitError(
                        message=f"数据源 {source_name} 触发限流（HTTP 429）",
                        context={"source_name": source_name, "status_code": 429},
                    )
                # Round 2 P1-infra-4: 401/403 是 API Key 凭证问题（ConfigurationError 101），
                # 不归"响应解析失败"413，避免运维误判为响应格式问题。
                # 构造时 ConfigurationError message 不含 Key 实际值，仅含字段名（防泄露）
                if resp.status_code in (401, 403):
                    raise ConfigurationError(
                        message=f"数据源 {source_name} API Key 无效或未授权（HTTP {resp.status_code}）",
                        context={"source_name": source_name, "status_code": resp.status_code},
                    )
                # R2-2-B7/H5: 3xx 是端点迁移/配置漂移（确定性错误），非瞬时服务端故障——
                # 不重试不计熔断；location 仅入 context（经 to_dict 脱敏）禁入 message
                # （message 直发事件通道），截断防签名 URL 长 token 落日志
                if 300 <= resp.status_code < 400:
                    raise DataSourceResponseError(
                        message=f"数据源 {source_name} 返回重定向（HTTP {resp.status_code}），请检查 API 地址配置",
                        context={
                            "source_name": source_name,
                            "status_code": resp.status_code,
                            "location": resp.headers.get("location", "")[:200],
                        },
                    )
                if 400 <= resp.status_code < 500:
                    raise DataSourceResponseError(
                        message=f"数据源 {source_name} 返回客户端错误（HTTP {resp.status_code}）",
                        context={"source_name": source_name, "status_code": resp.status_code},
                    )
                resp.raise_for_status()
                data = resp.json()
    except (DataSourceRateLimitError, ConfigurationError, DataSourceResponseError):
        # 确定性错误路径单点收敛（R3-P0-1）：429/401/403/3xx/4xx 五条状态码路径
        # 在 with attempt 块内已转换的领域异常在此统一释放半开探测槽位——
        # 请求已收到确定性响应（服务可连通），不计熔断统计。
        # 本函数 on_ignored 调用点之一（其余：下方 DecodingError/InvalidURL/ValueError 分支，
        # 每条异常路径恰好调用一次，无双释放）
        circuit_breaker.on_ignored()
        raise
    except httpx.TimeoutException as e:
        # 注意：TimeoutException 是 TransportError 的子类——本分支必须位于
        # RequestError/TransportError 分支之前（顺序是硬约束，302 语义依赖此顺序）
        circuit_breaker.on_failure()
        raise TimeoutError(
            message=f"数据源 {source_name} 请求超时",
            context={"source_name": source_name},
            cause=e,
        ) from e
    except httpx.DecodingError as e:
        # 响应体解码失败（截断 gzip/不支持的 content-encoding）：确定性错误，
        # 不计熔断统计，仅释放探测槽位（R3-P1-6 + R3-P0-1）
        circuit_breaker.on_ignored()
        raise DataSourceResponseError(
            message=f"数据源 {source_name} 响应体解码失败（内容编码异常）",
            context={"source_name": source_name},
            cause=e,
        ) from e
    except httpx.InvalidURL as e:
        # URL 配置畸形（环境变量/配置类）：确定性配置错误，不计熔断统计（R3-P1-6）
        circuit_breaker.on_ignored()
        raise ConfigurationError(
            message=f"数据源 {source_name} API 地址配置非法（URL 格式错误）",
            context={"source_name": source_name},
            cause=e,
        ) from e
    except httpx.UnsupportedProtocol as e:
        # URL 协议缺失（如 base_url 无 http:// scheme）：确定性配置错误（R3-4 K1——
        # 修复前 ⊂ TransportError 被白名单重试 3 次且 on_failure 计熔断，配置漂移
        # 可单独打 open 熔断器；对齐 InvalidURL 101 口径）
        circuit_breaker.on_ignored()
        raise ConfigurationError(
            message=f"数据源 {source_name} API 地址协议非法（缺少 http/https scheme）",
            context={"source_name": source_name},
            cause=e,
        ) from e
    except httpx.RequestError as e:
        # 其余传输类故障（TransportError 子类/TooManyRedirects 等）：瞬时故障，
        # 重试耗尽后计熔断（R3-P1-6：TransportError 放宽为 RequestError，
        # 闭合 DecodingError 等非传输 RequestError 子类的穿透缺口）
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
        # JSON 解析失败：不重试，不记熔断器（对端响应格式问题），仅释放探测槽位
        circuit_breaker.on_ignored()
        raise DataSourceResponseError(
            message=f"数据源 {source_name} 响应 JSON 解析失败",
            context={"source_name": source_name},
            cause=e,
        ) from e

    # 成功 → 通知熔断器
    circuit_breaker.on_success()
    return data


__all__ = [
    "RETRYABLE_STATUS_CODES",
    "is_retryable_http_error",
    "parse_int_param",
    "quote_path_segment",
    "request_json_with_resilience",
]
