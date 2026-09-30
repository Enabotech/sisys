"""基础设施层 SEC EDGAR 数据源适配器（Story 4.1f）

SEC EDGAR（美国证监会法定披露，免 key 无条件注册）：
- UA 规范：全部请求携带「公司名 邮箱」格式 UA（官方 Fair Access 义务——无 UA 实测 403）
- 限速：滑动窗口 8 req/s（官方 10 留余量）——进程内令牌桶（Lock + 时间窗）
- 双模式（query 前缀分派）：
  - 检索模式（缺省）：检索词（如 `"market share" forms=10-K` 或纯关键词）→
    GET {efts}/LATEST/search-index?q=...&forms=...（Elasticsearch 风格 JSON）
  - XBRL 模式：`xbrl:CIK:概念` 前缀 → data.sec.gov/api/xbrl/companyconcept/...（绝对
    URL 拼接——单 httpx client 双 base，httpx 绝对 URL 忽略 base_url）
  - 非法模式前缀（形如 `xxx:` 但非 xbrl）→ ValidationError(201) 输入前置校验（xbrl-frame: 未实现，同样 201 拦截）
- 响应：检索模式 {"filings": [{company, form, filed_at}]}；XBRL 模式 {concept, unit, values}

实现 DataSourcePort。容错：tenacity + CircuitBreaker（复用 _http_helpers 集中映射）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import deque
from datetime import UTC, datetime
from typing import Any

import httpx

from src.domain.exceptions import DataSourceResponseError, ValidationError
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)
from src.infrastructure.config.sec_edgar import SecEdgarConfig
from src.infrastructure.external_services.datasources._http_helpers import request_json_with_resilience
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

UA_HEADER = "sisys-tools/1.0 (contact@sisys.local)"  # 官方 Fair Access：「公司名 邮箱」格式
_DATA_BASE = "https://data.sec.gov"  # XBRL 数据域（官方固定域名——绝对 URL 拼接）
_SEARCH_ENDPOINT = "/LATEST/search-index"
_RATE_PER_SECOND = 8.0  # 官方 10 req/s 留余量
_RATE_WINDOW = 1.0  # 滑动窗口秒数
_KNOWN_MODE_PREFIXES = ("xbrl",)  # frames 模式（xbrl-frame:）未实现——按非法前缀 201 拦截，Defer 见 Story 4.1f（R1-F2）
_MODE_PREFIX_PATTERN = re.compile(r"^([a-zA-Z][a-zA-Z-]*):")
_FORMS_PATTERN = re.compile(r"\s+forms=(\S+)$")


def _compute_delay(
    timestamps: list[float], now: float, *, rate: float = _RATE_PER_SECOND, window: float = _RATE_WINDOW
) -> float:
    """滑动窗口限速纯函数：窗口已满时返回最老时间戳出窗所需等待秒数，未满返回 0。

    Args:
        timestamps: 窗口内历史请求时刻（monotonic 秒，升序可含同刻）
        now: 当前时刻（monotonic 秒）
        rate: 窗口内允许的最大请求数
        window: 窗口长度秒数
    """
    in_window = [ts for ts in timestamps if now - ts < window]
    if len(in_window) < rate:
        return 0.0
    oldest = min(in_window)
    return max(0.0, window - (now - oldest))


class _SlidingWindowRateLimiter:
    """进程内滑动窗口限速器（8 req/s——Lock 保护 + 时间窗）。"""

    _lock: asyncio.Lock = asyncio.Lock()  # 类变量（协程间共享——单例适配器语义）

    def __init__(self) -> None:
        self._timestamps: deque[float] = deque()

    async def acquire(self) -> None:
        """等待直至窗口容量允许本次请求（记录时刻入窗）。"""
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] >= _RATE_WINDOW:
                    self._timestamps.popleft()
                delay = _compute_delay(list(self._timestamps), now)
                if delay <= 0.0:
                    self._timestamps.append(now)
                    return
            await asyncio.sleep(delay)


class SecEdgarAdapter:
    """SEC EDGAR 数据源适配器（免 key + 强制 UA + 滑动窗口限速 + 双模式检索）"""

    def __init__(
        self,
        config: SecEdgarConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
        rate_limited: bool = True,
    ) -> None:
        """构造适配器。

        Args:
            config: 配置（可空——免 key 源，缺省 from_env 语义的类默认值）
            client: 可注入 httpx 客户端（测试 MockTransport）
            circuit_breaker: 可注入熔断器
            retry_max_attempts: 重试次数上限
            retry_min_wait: 重试最小等待秒数（测试注入加速）
            retry_max_wait: 重试最大等待秒数
            rate_limited: 是否启用进程内限速（测试并发断言场景关闭单次，节流专项测试开启）
        """
        self._config = config or SecEdgarConfig()
        self._client = client or httpx.AsyncClient(base_url=self._config.api_url, timeout=self._config.timeout)
        self._owns_client = client is None
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5, recovery_timeout=30.0, half_open_max_calls=1, name="data-source-sec-edgar"
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait
        self._rate_limiter = _SlidingWindowRateLimiter() if rate_limited else None

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据（required_fields 属声明面，适配器侧不填——Task 5 定稿）。"""
        return DataSourceRef(
            name="sec-edgar",
            url=self._config.api_url,
            ttl_seconds=self._config.ttl_seconds,
            api_type=DataSourceApiType.REST_JSON,
        )

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """双模式检索（query 前缀分派：缺省检索 / xbrl: 结构化 / 非法前缀 201）。

        Args:
            query: 检索请求（检索词或 xbrl:CIK:概念 前缀）

        Returns:
            DataSourceResult（payload 为 filings 列表或 XBRL 概念时序 JSON 字符串）

        Raises:
            ValidationError: 非法模式前缀（输入前置校验，零请求消耗）
            DataSourceResponseError: 响应结构异常 / 非法 JSON
            DataSourceUnavailableError: 5xx/连接失败重试耗尽/熔断
            DataSourceRateLimitError: HTTP 429
            TimeoutError: 请求超时
        """
        if self._rate_limiter is not None:
            await self._rate_limiter.acquire()
        raw = query.query
        prefix_match = _MODE_PREFIX_PATTERN.match(raw)
        if prefix_match and prefix_match.group(1) not in _KNOWN_MODE_PREFIXES:
            raise ValidationError(
                message=(f"sec-edgar 检索式含未注册的模式前缀 {prefix_match.group(1)!r}:（合法前缀 xbrl:，检索模式无需前缀）"),
                context={"source_name": "sec-edgar", "field": "query", "value": raw[:100]},
            )
        if raw.startswith("xbrl:"):
            data, source_ts = await self._fetch_xbrl_companyconcept(raw[len("xbrl:") :])
            payload_obj: dict[str, Any] = data
        else:
            data, source_ts = await self._fetch_search(raw)
            payload_obj = {"filings": data["filings"]}
        now = datetime.now(UTC)
        timestamp = source_ts or now
        return DataSourceResult(
            source_name="sec-edgar",
            payload=json.dumps(payload_obj, ensure_ascii=False),
            source_timestamp=timestamp,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=timestamp, ttl_seconds=self._config.ttl_seconds),
            confidence=0.95,  # 美政府法定披露权威数据
        )

    async def _fetch_search(self, raw_query: str) -> tuple[dict[str, Any], datetime | None]:
        """检索模式（efts search-index；`"关键词" forms=表单` 语法解析为 q/forms 两参数）。"""
        q = raw_query
        forms: str | None = None
        forms_match = _FORMS_PATTERN.search(raw_query)
        if forms_match:
            forms = forms_match.group(1)
            q = raw_query[: forms_match.start()].strip().strip('"')
        params: dict[str, str] = {"q": q}
        if forms:
            params["forms"] = forms
        data = await self._request(_SEARCH_ENDPOINT, params=params)
        filings = self._extract_filings(data)
        return {"filings": filings}, self._latest_filed_at(filings)

    @staticmethod
    def _extract_filings(data: Any) -> list[dict[str, Any]]:
        """财报列表提取（双形态：契约直接形态 / 真实端点 Elasticsearch 形态）。

        - 契约形态（单测/规范）：{"filings": [{company, cik, form, filed_at}]}
        - 真实端点形态（efts Elasticsearch）：{"hits": {"hits": [{"_source": {ciks,
          display_names, form, file_date}}]}} → 转换为 filings 结构（契约三箭头语义）
        """
        if isinstance(data, dict) and "filings" in data:
            filings = data["filings"]
            if not isinstance(filings, list):
                raise DataSourceResponseError(
                    message="SEC EDGAR 响应 'filings' 字段非列表",
                    context={"source_name": "sec-edgar", "actual_type": type(filings).__name__},
                )
            return filings
        hits = data.get("hits") if isinstance(data, dict) else None
        if isinstance(hits, dict) and isinstance(hits.get("hits"), list):
            converted: list[dict[str, Any]] = []
            for hit in hits["hits"]:
                source = hit.get("_source", {}) if isinstance(hit, dict) else {}
                display_names = source.get("display_names") or []
                ciks = source.get("ciks") or []
                converted.append(
                    {
                        "company": display_names[0] if display_names else "",
                        "cik": str(ciks[0]) if ciks else "",
                        "form": source.get("form", ""),
                        "filed_at": source.get("file_date", ""),
                    }
                )
            return converted
        raise DataSourceResponseError(
            message="SEC EDGAR 响应缺少 'filings'/'hits' 字段",
            context={"source_name": "sec-edgar", "actual_type": type(data).__name__},
        )

    async def _fetch_xbrl_companyconcept(self, spec: str) -> tuple[dict[str, Any], datetime | None]:
        """XBRL 模式（xbrl:CIK:概念 → data.sec.gov companyconcept 绝对 URL 单指标时序）。"""
        parts = spec.split(":")
        if len(parts) < 2 or not parts[0] or not parts[1]:
            raise ValidationError(
                message=(f"sec-edgar XBRL 检索式格式非法（期望 xbrl:CIK:概念，如 xbrl:CIK0001318605:Revenues）: {spec[:100]}"),
                context={"source_name": "sec-edgar", "field": "query", "value": spec[:100]},
            )
        cik, concept = parts[0], parts[1]
        taxonomy = parts[2] if len(parts) > 2 else "us-gaap"
        url = f"{_DATA_BASE}/api/xbrl/companyconcept/{cik}/{taxonomy}/{concept}.json"
        data = await self._request(url)
        return self._extract_xbrl(data), None

    @staticmethod
    def _extract_xbrl(data: Any) -> dict[str, Any]:
        """XBRL 概念提取（双形态：契约直接形态 / 真实端点形态）。

        - 契约形态（单测/规范）：{concept, unit, values}
        - 真实端点形态（companyconcept API）：{tag, units: {<单位>: [时序条目]}} →
          转换为契约形态（concept=tag，unit=首个单位键，values=该单位时序数组）
        """
        if isinstance(data, dict) and "concept" in data:
            return data
        if isinstance(data, dict) and "tag" in data and isinstance(data.get("units"), dict) and data["units"]:
            unit, values = next(iter(data["units"].items()))
            if isinstance(values, list):
                return {"concept": str(data["tag"]), "unit": str(unit), "values": values}
        raise DataSourceResponseError(
            message="SEC EDGAR XBRL 响应缺少 'concept'/'tag+units' 字段",
            context={"source_name": "sec-edgar", "actual_type": type(data).__name__},
        )

    async def _request(self, url: str, *, params: dict[str, str] | None = None) -> Any:
        """经 resilience helper 执行请求（绝对 URL 拼接——双 base 单 client）。"""
        return await request_json_with_resilience(
            self._client,
            "GET",
            url,
            source_name="sec-edgar",
            circuit_breaker=self._circuit_breaker,
            params=params,
            headers={"User-Agent": UA_HEADER},
            max_attempts=self._retry_max_attempts,
            min_wait=self._retry_min_wait,
            max_wait=self._retry_max_wait,
        )

    @staticmethod
    def _latest_filed_at(filings: list[dict[str, Any]]) -> datetime | None:
        """取财报列表中最晚申报日（无有效日期返回 None）。"""
        latest: datetime | None = None
        for item in filings:
            raw = item.get("filed_at")
            if not isinstance(raw, str) or not raw:
                continue
            try:
                ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            ts = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)
            if latest is None or ts > latest:
                latest = ts
        return latest

    async def health_check(self) -> bool:
        """探活（最小检索，单次尝试）。"""
        try:
            if self._rate_limiter is not None:
                await self._rate_limiter.acquire()
            await self._request(_SEARCH_ENDPOINT, params={"q": "probe"})
            return True
        except Exception as e:  # 探活失败不抛——健康检查语义
            logger.warning("SecEdgarAdapter 探活失败: %s", type(e).__name__)
            return False

    async def close(self) -> None:
        """释放自持客户端（注入客户端由调用方管理）。"""
        if self._owns_client:
            await self._client.aclose()


__all__ = ["SecEdgarAdapter", "UA_HEADER"]
