"""基础设施层 World Bank 数据源适配器（Story 4.1b）

World Bank Open Data API（公开免费，无需 API Key）：
- 端点：GET {base}/country/{country}/indicator/{indicator}?format=json
- 响应：[meta, rows] 列表结构（rows 含 indicator/country/value/date）
- 典型指标：NY.GDP.MKTP.CD（GDP）/ 治理指标（Governance Indicators）

实现 DataSourcePort（R3：基础设施层实现领域端口）。
容错：tenacity 指数退避（仅 5xx/超时/传输错误）+ CircuitBreaker（5 次/30s）。
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from src.domain.exceptions import DataSourceResponseError
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)
from src.infrastructure.config.worldbank import WorldBankConfig
from src.infrastructure.external_services.datasources._http_helpers import (
    request_json_with_resilience,
)
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class WorldBankAdapter:
    """World Bank 数据源适配器（REST_JSON）

    Attributes:
        _config: WorldBankConfig 配置
        _client: httpx 异步客户端（可注入 MockTransport 测试）
        _circuit_breaker: 熔断器（默认 5 次失败断开 30 秒）
    """

    def __init__(
        self,
        config: WorldBankConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
    ) -> None:
        """初始化适配器

        Args:
            config: 数据源配置（默认 WorldBankConfig()）
            client: 可选注入的 httpx 客户端（测试注入 MockTransport）
            circuit_breaker: 可选熔断器（默认 failure_threshold=5 / recovery_timeout=30s）
            retry_max_attempts: 最大重试次数（含首次）
            retry_min_wait: 最小退避秒数
            retry_max_wait: 最大退避秒数
        """
        self._config = config or WorldBankConfig()
        self._client = client or httpx.AsyncClient(base_url=self._config.api_url, timeout=self._config.timeout)
        self._owns_client = client is None
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=1,
            name="data-source-worldbank",
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据"""
        return DataSourceRef(
            name="world-bank",
            url=self._config.api_url,
            ttl_seconds=self._config.ttl_seconds,
            api_type=DataSourceApiType.REST_JSON,
        )

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """按指标查询 World Bank 数据

        Args:
            query: DataSourceQuery（query=指标代码如 "NY.GDP.MKTP.CD"，
                   parameters 可含 ("country", "CN")，默认 WLD 全球）

        Returns:
            DataSourceResult（payload 为 rows JSON 字符串）

        Raises:
            DataSourceResponseError: 响应结构非法（非 [meta, rows] 列表）
            DataSourceUnavailableError/TimeoutError/DataSourceRateLimitError: 见 _http_helpers
        """
        country = dict(query.parameters).get("country", "WLD")
        data = await request_json_with_resilience(
            self._client,
            "GET",
            f"/country/{country}/indicator/{query.query}",
            source_name="world-bank",
            circuit_breaker=self._circuit_breaker,
            params={"format": "json", "per_page": 100},
            max_attempts=self._retry_max_attempts,
            min_wait=self._retry_min_wait,
            max_wait=self._retry_max_wait,
        )
        rows = self._extract_rows(data)
        source_ts = self._parse_source_timestamp(rows)
        return DataSourceResult(
            source_name="world-bank",
            payload=json.dumps(rows, ensure_ascii=False),
            source_timestamp=source_ts,
            fetched_at=datetime.now(UTC),
            freshness=DataFreshness(source_timestamp=source_ts, ttl_seconds=self._config.ttl_seconds),
            confidence=0.95,  # 官方统计数据源（高置信度）
        )

    async def health_check(self) -> bool:
        """探活（轻量指标查询，不消耗配额——World Bank 公开免费）"""
        try:
            await request_json_with_resilience(
                self._client,
                "GET",
                "/country/WLD/indicator/SP.POP.TOTL",
                source_name="world-bank",
                circuit_breaker=self._circuit_breaker,
                params={"format": "json", "per_page": 1},
                max_attempts=1,
            )
            return True
        except Exception as e:
            logger.warning("World Bank 探活失败: %s", type(e).__name__)
            return False

    def _extract_rows(self, data: Any) -> list[dict[str, Any]]:
        """解析 [meta, rows] 结构（非法结构抛 DataSourceResponseError）"""
        if not isinstance(data, list) or len(data) != 2 or not isinstance(data[1], list):
            raise DataSourceResponseError(
                message="World Bank 响应结构非法（期望 [meta, rows] 列表）",
                context={"source_name": "world-bank", "actual_type": type(data).__name__},
            )
        return [row for row in data[1] if isinstance(row, dict) and row.get("value") is not None]

    def _parse_source_timestamp(self, rows: list[dict[str, Any]]) -> datetime:
        """从 rows 最新 date 字段（年份字符串）解析源端时间戳，缺失时回退当前时间"""
        years = [int(r["date"]) for r in rows if str(r.get("date", "")).isdigit()]
        if years:
            return datetime(max(years), 1, 1, tzinfo=UTC)
        return datetime.now(UTC)

    async def close(self) -> None:
        """关闭自持的 httpx 客户端（注入客户端由调用方管理）"""
        if self._owns_client:
            await self._client.aclose()


__all__ = ["WorldBankAdapter"]
