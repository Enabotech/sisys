"""基础设施层 IMF 数据源适配器（Story 4.1b）

IMF DataMapper API（World Economic Outlook 指标）：
- 端点：GET {base}/{indicator}/{country}
- 响应：{"values": {indicator: {country: {year: value}}}}

实现 DataSourcePort。容错：tenacity + CircuitBreaker（5 次/30s 默认档）。
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
from src.infrastructure.config.imf import IMFConfig
from src.infrastructure.external_services.datasources._http_helpers import (
    request_json_with_resilience,
)
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class IMFAdapter:
    """IMF 数据源适配器（SDMX_JSON / DataMapper API）"""

    def __init__(
        self,
        config: IMFConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
    ) -> None:
        """初始化适配器（参数语义同 WorldBankAdapter）"""
        self._config = config or IMFConfig()
        self._client = client or httpx.AsyncClient(base_url=self._config.api_url, timeout=self._config.timeout)
        self._owns_client = client is None
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=1,
            name="data-source-imf",
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据"""
        return DataSourceRef(
            name="imf",
            url=self._config.api_url,
            ttl_seconds=self._config.ttl_seconds,
            api_type=DataSourceApiType.SDMX_JSON,
        )

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """按指标查询 IMF WEO 数据

        Args:
            query: DataSourceQuery（query=指标代码如 "NGDP_RPCH"，
                   parameters 可含 ("country", "CN")，默认全球聚合视图）

        Returns:
            DataSourceResult（payload 为 values 结构 JSON 字符串）

        Raises:
            DataSourceResponseError: 响应缺少 values 字段
        """
        country = dict(query.parameters).get("country", "")
        path = f"/{query.query}/{country}" if country else f"/{query.query}"
        data = await request_json_with_resilience(
            self._client,
            "GET",
            path,
            source_name="imf",
            circuit_breaker=self._circuit_breaker,
            max_attempts=self._retry_max_attempts,
            min_wait=self._retry_min_wait,
            max_wait=self._retry_max_wait,
        )
        values = self._extract_values(data)
        source_ts = self._parse_source_timestamp(values)
        return DataSourceResult(
            source_name="imf",
            payload=json.dumps({"values": values}, ensure_ascii=False),
            source_timestamp=source_ts,
            fetched_at=datetime.now(UTC),
            freshness=DataFreshness(source_timestamp=source_ts, ttl_seconds=self._config.ttl_seconds),
            confidence=0.95,  # IMF 官方统计
        )

    async def health_check(self) -> bool:
        """探活（指标列表轻量端点）"""
        try:
            await request_json_with_resilience(
                self._client,
                "GET",
                "/indicators",
                source_name="imf",
                circuit_breaker=self._circuit_breaker,
                max_attempts=1,
            )
            return True
        except Exception as e:
            logger.warning("IMF 探活失败: %s", type(e).__name__)
            return False

    def _extract_values(self, data: Any) -> dict[str, Any]:
        """提取 values 字段（缺失抛 DataSourceResponseError）"""
        if not isinstance(data, dict) or "values" not in data:
            raise DataSourceResponseError(
                message="IMF 响应缺少 'values' 字段",
                context={"source_name": "imf", "actual_type": type(data).__name__},
            )
        values = data["values"]
        if not isinstance(values, dict):
            raise DataSourceResponseError(
                message="IMF 响应 'values' 字段非 dict",
                context={"source_name": "imf", "actual_type": type(values).__name__},
            )
        return values

    def _parse_source_timestamp(self, values: dict[str, Any]) -> datetime:
        """从 values 嵌套结构中提取最新年份作为源端时间戳，缺失回退当前时间"""
        latest_year = 0
        for indicator_data in values.values():
            if not isinstance(indicator_data, dict):
                continue
            for country_data in indicator_data.values():
                if not isinstance(country_data, dict):
                    continue
                for year_str in country_data:
                    if str(year_str).isdigit():
                        latest_year = max(latest_year, int(year_str))
        if latest_year > 0:
            return datetime(latest_year, 1, 1, tzinfo=UTC)
        return datetime.now(UTC)

    async def close(self) -> None:
        """关闭自持的 httpx 客户端（注入客户端由调用方管理）"""
        if self._owns_client:
            await self._client.aclose()


__all__ = ["IMFAdapter"]
