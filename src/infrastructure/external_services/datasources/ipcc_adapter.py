"""基础设施层 IPCC 数据源适配器（Story 4.1b）

IPCC 环境数据（CSV 下载）：
- 端点：GET {csv_base_url}/{query}.csv
- 响应：CSV 文本 → 解析为行记录列表（含大文件截断保护 max_rows）

实现 DataSourcePort。容错：tenacity + CircuitBreaker（2 次/120s 立即熔断档——
大文件传输失败代价高，快速断开保护带宽）。
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import UTC, datetime

import httpx

from src.domain.exceptions import DataSourceResponseError
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)
from src.infrastructure.config.ipcc import IPCCConfig
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class IPCCAdapter:
    """IPCC 数据源适配器（CSV_DOWNLOAD）

    CSV 解析不走 _http_helpers 的 JSON 路径（响应为 text/csv），
    但复用相同的 tenacity + 熔断 + 异常映射契约（内联保持一致）。
    """

    def __init__(
        self,
        config: IPCCConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
        max_rows: int = 10000,
    ) -> None:
        """初始化适配器

        Args:
            config: IPCCConfig 配置
            client: 可选注入的 httpx 客户端（测试注入 MockTransport）
            circuit_breaker: 可选熔断器（默认 2 次失败断开 120s）
            max_rows: CSV 行数截断保护上限（默认 10000）
        """
        self._config = config or IPCCConfig()
        self._client = client or httpx.AsyncClient(timeout=self._config.timeout)
        self._owns_client = client is None
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=120.0,
            half_open_max_calls=1,
            name="data-source-ipcc",
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait
        self._max_rows = max_rows

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据"""
        return DataSourceRef(
            name="ipcc",
            url=self._config.csv_base_url,
            ttl_seconds=self._config.ttl_seconds,
            api_type=DataSourceApiType.CSV_DOWNLOAD,
        )

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """下载并解析 CSV 数据集

        Args:
            query: DataSourceQuery（query=数据集相对路径键，如 "ar6-wg1-spm"）

        Raises:
            DataSourceResponseError: CSV 为空/无表头/解析失败（不重试）
            DataSourceUnavailableError/TimeoutError/DataSourceRateLimitError: HTTP 层故障
        """
        text = await self._request_csv(f"{self._config.csv_base_url}/{query.query}.csv")
        rows, truncated = self._parse_csv(text)
        now = datetime.now(UTC)
        return DataSourceResult(
            source_name="ipcc",
            payload=json.dumps({"rows": rows, "truncated": truncated}, ensure_ascii=False),
            source_timestamp=now,  # 静态报告无源端时间戳，按采集时刻计
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=now, ttl_seconds=self._config.ttl_seconds),
            confidence=0.85,  # 权威报告数据
        )

    async def health_check(self) -> bool:
        """探活（HEAD 基础地址）"""
        try:
            resp = await self._client.head(self._config.csv_base_url)
            return resp.status_code < 500
        except Exception as e:
            logger.warning("IPCC 探活失败: %s", type(e).__name__)
            return False

    async def _request_csv(self, url: str) -> str:
        """带韧性（重试 + 熔断）的 CSV 文本请求（异常映射契约与 _http_helpers 一致）"""
        from tenacity import (
            AsyncRetrying,
            before_sleep_log,
            retry_if_exception,
            stop_after_attempt,
            wait_exponential,
        )

        from src.domain.exceptions import (
            DataSourceRateLimitError,
            DataSourceUnavailableError,
            TimeoutError,
        )
        from src.infrastructure.external_services.datasources._http_helpers import (
            is_retryable_http_error,
        )
        from src.infrastructure.external_services.embedding.circuit_breaker import (
            CircuitBreakerOpenError,
        )

        try:
            self._circuit_breaker.before_call()
        except CircuitBreakerOpenError as e:
            raise DataSourceUnavailableError(
                message="数据源 ipcc 熔断器已断开",
                context={"source_name": "ipcc"},
                cause=e,
            ) from e

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._retry_max_attempts),
                wait=wait_exponential(multiplier=1, min=self._retry_min_wait, max=self._retry_max_wait),
                retry=retry_if_exception(is_retryable_http_error),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    # R2-2-B2/G7 流式改造：整段（含字节累计缓冲区）必须位于 with attempt 内
                    # 且每次 attempt 重新初始化——否则 mid-stream 超时重试会跨重试累计字节，
                    # 413 超限误判。status_code 在进入 stream 上下文（headers 到达）后即可用，
                    # 429/4xx 分流契约与 _http_helpers.request_json_with_resilience 对齐：
                    # 429 → DataSourceRateLimitError(412)、其他 4xx → DataSourceResponseError(413)
                    # 不走 resp.raise_for_status → httpx.HTTPStatusError → 411 错误路由
                    chunks: list[bytes] = []
                    total = 0
                    async with self._client.stream("GET", url) as resp:
                        if resp.status_code == 429:
                            raise DataSourceRateLimitError(
                                message="数据源 ipcc 触发限流（HTTP 429）",
                                context={"source_name": "ipcc", "status_code": 429},
                            )
                        if 400 <= resp.status_code < 500:
                            raise DataSourceResponseError(
                                message=f"数据源 ipcc 返回客户端错误（HTTP {resp.status_code}）",
                                context={"source_name": "ipcc", "status_code": resp.status_code},
                            )
                        resp.raise_for_status()
                        # Content-Type 拒绝式校验（非白名单——CSV 端点 Content-Type 实务多样，
                        # 只拒绝明确错误信号）：CDN/反爬/WAF 的 HTML 错误页（HTTP 200）若放行，
                        # csv.DictReader 会静默解析为结构合法的垃圾行数据（数据污染而非报错）
                        content_type = resp.headers.get("content-type", "")
                        if content_type.startswith("text/html"):
                            raise DataSourceResponseError(
                                message="数据源 ipcc 返回 HTML 错误页而非 CSV",
                                context={"source_name": "ipcc", "content_type": content_type, "url_path": resp.url.path},
                            )
                        # 流式累计 + 字节上限（无界读取 OOM 面修复；超限为确定性响应错误
                        # → 413 不重试（白名单外）不计熔断（非 httpx 异常），与 JSON 解析失败先例一致）
                        async for chunk in resp.aiter_bytes(65536):
                            total += len(chunk)
                            if total > self._config.max_bytes:
                                raise DataSourceResponseError(
                                    message=f"数据源 ipcc 响应超过大小上限（{self._config.max_bytes} 字节）",
                                    context={"source_name": "ipcc", "max_bytes": self._config.max_bytes},
                                )
                            chunks.append(chunk)
                    # 流式路径无法访问 resp.text（ResponseNotRead）；解码以 charset 头为准，
                    # 缺省 utf-8（行为收窄：不再走 charset_normalizer 内容探测——
                    # IPCC CSV 实际均为 utf-8/ascii，可接受）
                    text = b"".join(chunks).decode(resp.charset_encoding or "utf-8", errors="replace")
        except httpx.TimeoutException as e:
            self._circuit_breaker.on_failure()
            raise TimeoutError(
                message="数据源 ipcc 请求超时",
                context={"source_name": "ipcc"},
                cause=e,
            ) from e
        except httpx.TransportError as e:
            self._circuit_breaker.on_failure()
            raise DataSourceUnavailableError(
                message="数据源 ipcc 连接失败（重试耗尽）",
                context={"source_name": "ipcc"},
                cause=e,
            ) from e
        except httpx.HTTPStatusError as e:
            self._circuit_breaker.on_failure()
            raise DataSourceUnavailableError(
                message=f"数据源 ipcc 服务端错误（HTTP {e.response.status_code}，重试耗尽）",
                context={"source_name": "ipcc", "status_code": e.response.status_code},
                cause=e,
            ) from e

        self._circuit_breaker.on_success()
        return text

    def _parse_csv(self, text: str) -> tuple[list[dict[str, str]], bool]:
        """解析 CSV 文本为行记录（含截断保护）

        Returns:
            (行记录列表, 是否截断)

        Raises:
            DataSourceResponseError: 空内容/无表头
        """
        if not text or not text.strip():
            raise DataSourceResponseError(
                message="IPCC 响应 CSV 为空",
                context={"source_name": "ipcc"},
            )
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise DataSourceResponseError(
                message="IPCC 响应 CSV 无表头",
                context={"source_name": "ipcc"},
            )
        rows: list[dict[str, str]] = []
        truncated = False
        for row in reader:
            if len(rows) >= self._max_rows:
                truncated = True
                break
            rows.append(dict(row))
        return rows, truncated

    async def close(self) -> None:
        """关闭自持的 httpx 客户端（注入客户端由调用方管理）"""
        if self._owns_client:
            await self._client.aclose()


__all__ = ["IPCCAdapter"]
