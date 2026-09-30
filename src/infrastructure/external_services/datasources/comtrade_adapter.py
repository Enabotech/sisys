"""基础设施层 UN Comtrade 数据源适配器（Story 4.1f）

UN Comtrade（联合国官方贸易统计，HS 商品级行业量化数据源）：
- 注册语义：无条件注册 + preview 端点免 key 兜底；key 可选增强（有 key 加
  Ocp-Apim-Subscription-Key 头，配额 100 → 500 次/天）
- 管道串解析：`reporter=156|cmd=8703|flow=X|period=2024` → API query params
  （cmd 必填缺失 → ValidationError(201) 输入前置校验；reporter 缺省 156 中国口径）
- 日配额守卫（epics AC-4 承载）：进程内日窗口请求计数（UTC 00:00 重置，
  now_fn 注入）——超限前置抛 412 零请求消耗；守卫模式复用 EPO 周窗口设计
- 端点：GET {base}/public/v1/preview/C/A/HS?reporterCode=...&cmdCode=...
- 响应：{"records": [{cmd_code, trade_value, period}]}

实现 DataSourcePort。容错：tenacity + CircuitBreaker（复用 _http_helpers 集中映射）。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from src.domain.exceptions import DataSourceRateLimitError, DataSourceResponseError, ValidationError
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)
from src.infrastructure.config.comtrade import ComtradeConfig
from src.infrastructure.external_services.datasources._http_helpers import request_json_with_resilience
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

_PREVIEW_ENDPOINT = "/public/v1/preview/C/A/HS"  # typeCode=C/freqCode=A/classificationCode=HS
_DAILY_LIMIT_WITH_KEY = 500  # 官方免费 key 配额（Task 0 定稿）
_DAILY_LIMIT_PREVIEW = 100  # 无 key preview 保守值（Task 0 定稿）
_PARAM_KEY_MAP = {
    "reporter": "reporterCode",
    "cmd": "cmdCode",
    "flow": "flowCode",
    "period": "period",
}
_DEFAULT_REPORTER = "156"  # 中国口径（缺省）


def parse_pipeline_query(raw: str) -> dict[str, str]:
    """解析管道分隔参数串为 Comtrade API query params（输入前置校验）。

    Args:
        raw: 管道串（如 reporter=156|cmd=8703|flow=X|period=2024）

    Returns:
        API 参数字典（reporter 缺省 156 中国口径）

    Raises:
        ValidationError: 串为空或缺少必填的 cmd（HS 商品码）
    """
    if not raw.strip():
        raise ValidationError(
            message="comtrade 检索式为空（期望管道串如 reporter=156|cmd=8703|flow=X|period=2024）",
            context={"source_name": "comtrade", "field": "query", "value": raw[:100]},
        )
    params: dict[str, str] = {}
    for segment in raw.split("|"):
        segment = segment.strip()
        if not segment:
            continue
        if "=" not in segment:
            raise ValidationError(
                message=f"comtrade 管道串段格式非法（期望 key=value）: {segment[:50]}",
                context={"source_name": "comtrade", "field": "query", "value": segment[:50]},
            )
        key, _, value = segment.partition("=")
        if key not in _PARAM_KEY_MAP:
            raise ValidationError(
                message=f"comtrade 管道串含未知参数 {key!r}（合法: reporter/cmd/flow/period）",
                context={"source_name": "comtrade", "field": "query", "value": key},
            )
        params[_PARAM_KEY_MAP[key]] = value
    if "cmdCode" not in params or not params["cmdCode"]:
        raise ValidationError(
            message="comtrade 检索式缺少必填参数 cmd（HS 商品码，如 cmd=8703）",
            context={"source_name": "comtrade", "field": "query", "value": raw[:100]},
        )
    params.setdefault("reporterCode", _DEFAULT_REPORTER)
    return params


class DailyQuotaGuard:
    """Comtrade 日配额守卫（有 key 500 次/天 / 无 key preview 100 次/天）。

    进程内日窗口请求计数（UTC 00:00 重置，now_fn 可注入）；超限前置抛 412
    （零请求消耗）。守卫模式复用 EPO 周窗口设计（Lock 类变量 + 可注入初始计数）。
    """

    _lock: asyncio.Lock = asyncio.Lock()  # 类变量（协程间共享——单例适配器语义）

    def __init__(
        self,
        *,
        api_key_present: bool,
        quota_requests_used: int = 0,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._limit = _DAILY_LIMIT_WITH_KEY if api_key_present else _DAILY_LIMIT_PREVIEW
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._used = quota_requests_used
        self._day = self._now_fn().date()

    @property
    def used_requests(self) -> int:
        """当前日窗口已用请求数。"""
        return self._used

    async def ensure_capacity(self) -> None:
        """前置容量检查——日配额耗尽时抛 412（消息含已用次数与重置时间）。"""
        async with self._lock:
            self._rollover_if_new_day()
            if self._used >= self._limit:
                reset_at = datetime.combine(self._day + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
                raise DataSourceRateLimitError(
                    message=(
                        f"comtrade 日配额已耗尽（已用 {self._used} 次 >= {self._limit} 次/天，"
                        f"重置时间 {reset_at.isoformat()}）——前置拦截，零请求消耗"
                    ),
                    context={"source_name": "comtrade", "used_requests": self._used, "limit": self._limit},
                )

    async def consume(self) -> None:
        """请求计数 +1（成功发起一次上游请求后调用）。"""
        async with self._lock:
            self._rollover_if_new_day()
            self._used += 1

    def _rollover_if_new_day(self) -> None:
        """越过 UTC 00:00 重置窗口（调用方须已持锁）。"""
        current_day = self._now_fn().date()
        if current_day > self._day:
            self._day = current_day
            self._used = 0


class ComtradeAdapter:
    """UN Comtrade 数据源适配器（key 可选 + 管道串解析 + 日配额守卫）"""

    def __init__(
        self,
        config: ComtradeConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
        now_fn: Callable[[], datetime] | None = None,
        quota_requests_used: int = 0,
    ) -> None:
        """构造适配器（key 可选——缺失走 preview 裸模式，构造器不抛）。

        Args:
            config: 配置（可空——缺省类默认值）
            client: 可注入 httpx 客户端（测试 MockTransport）
            circuit_breaker: 可注入熔断器
            retry_max_attempts: 重试次数上限
            retry_min_wait: 重试最小等待秒数（测试注入加速）
            retry_max_wait: 重试最大等待秒数
            now_fn: 时钟注入（日窗口重置测试）
            quota_requests_used: 日配额已用请求初始值（守卫可注入性）
        """
        self._config = config or ComtradeConfig()
        self._client = client or httpx.AsyncClient(base_url=self._config.api_url, timeout=self._config.timeout)
        self._owns_client = client is None
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5, recovery_timeout=30.0, half_open_max_calls=1, name="data-source-comtrade"
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait
        self._quota_guard = DailyQuotaGuard(
            api_key_present=bool(self._config.api_key),
            quota_requests_used=quota_requests_used,
            now_fn=now_fn,
        )

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据（required_fields 属声明面，适配器侧不填——Task 5 定稿）。"""
        return DataSourceRef(
            name="comtrade",
            url=self._config.api_url,
            ttl_seconds=self._config.ttl_seconds,
            api_type=DataSourceApiType.REST_JSON,
        )

    @property
    def quota_used_requests(self) -> int:
        """当前日配额已用请求数（测试/运维观测）。"""
        return self._quota_guard.used_requests

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """执行管道串检索（cmd 必填前置校验 → preview 端点 GET）。

        Args:
            query: 检索请求（管道串如 reporter=156|cmd=8703|flow=X|period=2024）

        Returns:
            DataSourceResult（payload 为 records 列表 JSON 字符串）

        Raises:
            ValidationError: 管道串缺 cmd 或格式非法（输入前置校验，零请求消耗）
            DataSourceRateLimitError: 日配额耗尽前置拦截 / HTTP 429
            DataSourceResponseError: 响应结构异常 / 非法 JSON
            DataSourceUnavailableError: 5xx/连接失败重试耗尽/熔断
            TimeoutError: 请求超时
        """
        params = parse_pipeline_query(query.query)  # 输入前置校验（201——零请求消耗）
        await self._quota_guard.ensure_capacity()  # 配额前置拦截（412——零请求消耗）
        headers: dict[str, str] = {}
        if self._config.api_key:
            headers["Ocp-Apim-Subscription-Key"] = self._config.api_key
        data = await request_json_with_resilience(
            self._client,
            "GET",
            _PREVIEW_ENDPOINT,
            source_name="comtrade",
            circuit_breaker=self._circuit_breaker,
            params=params,
            headers=headers or None,
            max_attempts=self._retry_max_attempts,
            min_wait=self._retry_min_wait,
            max_wait=self._retry_max_wait,
        )
        await self._quota_guard.consume()
        records = self._extract_records(data)
        now = datetime.now(UTC)
        source_ts = self._latest_period(records) or now
        return DataSourceResult(
            source_name="comtrade",
            payload=json.dumps({"records": records}, ensure_ascii=False),
            source_timestamp=source_ts,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=source_ts, ttl_seconds=self._config.ttl_seconds),
            confidence=0.9,  # 联合国官方统计权威数据
        )

    def _extract_records(self, data: Any) -> list[dict[str, Any]]:
        """二段结构校验：响应须为 dict 且含 records 列表。"""
        if not isinstance(data, dict) or "records" not in data:
            raise DataSourceResponseError(
                message="comtrade 响应缺少 'records' 字段",
                context={"source_name": "comtrade", "actual_type": type(data).__name__},
            )
        records = data["records"]
        if not isinstance(records, list):
            raise DataSourceResponseError(
                message="comtrade 响应 'records' 字段非列表",
                context={"source_name": "comtrade", "actual_type": type(records).__name__},
            )
        return records

    @staticmethod
    def _latest_period(records: list[dict[str, Any]]) -> datetime | None:
        """取记录中最晚期间（period 为年或年月形态）。"""
        latest: datetime | None = None
        for item in records:
            raw = str(item.get("period", ""))
            if not raw:
                continue
            try:
                ts = datetime.fromisoformat(f"{raw[:4]}-01-01").replace(tzinfo=UTC)
            except ValueError:
                continue
            if latest is None or ts > latest:
                latest = ts
        return latest

    async def health_check(self) -> bool:
        """探活（最小商品码查询，单次尝试）。"""
        try:
            params = parse_pipeline_query("cmd=8703")
            await self._quota_guard.ensure_capacity()
            await request_json_with_resilience(
                self._client,
                "GET",
                _PREVIEW_ENDPOINT,
                source_name="comtrade",
                circuit_breaker=self._circuit_breaker,
                params=params,
                headers={"Ocp-Apim-Subscription-Key": self._config.api_key} if self._config.api_key else None,
                max_attempts=1,
                min_wait=self._retry_min_wait,
                max_wait=self._retry_max_wait,
            )
            return True
        except Exception as e:  # 探活失败不抛——健康检查语义
            logger.warning("ComtradeAdapter 探活失败: %s", type(e).__name__)
            return False

    async def close(self) -> None:
        """释放自持客户端（注入客户端由调用方管理）。"""
        if self._owns_client:
            await self._client.aclose()


__all__ = ["ComtradeAdapter", "DailyQuotaGuard", "parse_pipeline_query"]
