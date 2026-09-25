"""基础设施层 Eurostat 数据源适配器（Story 4.1b）

Eurostat SDMX REST API（PoC v1 验证可用，HTTP 200，42KB JSON）：
- 端点：GET {base}/statistics/1.0/data/{dataset}?format=JSON&lang=EN
- 响应：JSON-stat 2.0（value/dimension/updated 字段）

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
from src.infrastructure.config.eurostat import EurostatConfig
from src.infrastructure.external_services.datasources._http_helpers import (
    request_json_with_resilience,
)
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class EurostatAdapter:
    """Eurostat 数据源适配器（SDMX_JSON / JSON-stat 2.0）"""

    def __init__(
        self,
        config: EurostatConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
    ) -> None:
        """初始化适配器（参数语义同 WorldBankAdapter）"""
        self._config = config or EurostatConfig()
        self._client = client or httpx.AsyncClient(base_url=self._config.api_url, timeout=self._config.timeout)
        self._owns_client = client is None
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=1,
            name="data-source-eurostat",
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据"""
        return DataSourceRef(
            name="eurostat",
            url=self._config.api_url,
            ttl_seconds=self._config.ttl_seconds,
            api_type=DataSourceApiType.SDMX_JSON,
        )

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """按数据集代码查询 Eurostat 数据

        Args:
            query: DataSourceQuery（query=数据集代码如 "nama_10_gdp"，
                   parameters 透传为 SDMX 过滤参数如 ("geo", "DE")）

        Returns:
            DataSourceResult（payload 为 JSON-stat 核心字段 JSON 字符串）

        Raises:
            DataSourceResponseError: 响应缺少 value 字段（结构非法）
        """
        params: dict[str, Any] = {"format": "JSON", "lang": "EN"}
        params.update(dict(query.parameters))
        data = await request_json_with_resilience(
            self._client,
            "GET",
            f"/statistics/1.0/data/{query.query}",
            source_name="eurostat",
            circuit_breaker=self._circuit_breaker,
            params=params,
            max_attempts=self._retry_max_attempts,
            min_wait=self._retry_min_wait,
            max_wait=self._retry_max_wait,
        )
        payload_obj = self._extract_payload(data)
        source_ts = self._parse_source_timestamp(data)
        return DataSourceResult(
            source_name="eurostat",
            payload=json.dumps(payload_obj, ensure_ascii=False),
            source_timestamp=source_ts,
            fetched_at=datetime.now(UTC),
            freshness=DataFreshness(source_timestamp=source_ts, ttl_seconds=self._config.ttl_seconds),
            confidence=0.95,  # 欧盟官方统计
        )

    async def health_check(self) -> bool:
        """探活（轻量数据集查询，最小载荷）"""
        try:
            await request_json_with_resilience(
                self._client,
                "GET",
                "/statistics/1.0/data/nama_10_gdp",
                source_name="eurostat",
                circuit_breaker=self._circuit_breaker,
                params={"format": "JSON", "lang": "EN", "time": "2024", "geo": "DE"},
                max_attempts=1,
            )
            return True
        except Exception as e:
            logger.warning("Eurostat 探活失败: %s", type(e).__name__)
            return False

    def _extract_payload(self, data: Any) -> dict[str, Any]:
        """提取 JSON-stat 核心字段（缺 value 抛 DataSourceResponseError）"""
        if not isinstance(data, dict) or "value" not in data:
            raise DataSourceResponseError(
                message="Eurostat 响应缺少 'value' 字段（JSON-stat 结构非法）",
                context={"source_name": "eurostat", "actual_type": type(data).__name__},
            )
        return {
            "value": data["value"],
            "dimension": data.get("dimension", {}),
            "id": data.get("id", []),
            "size": data.get("size", []),
        }

    def _parse_source_timestamp(self, data: dict[str, Any]) -> datetime:
        """解析 JSON-stat updated 字段（ISO 日期），缺失/非法时回退当前时间"""
        raw = data.get("updated")
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw).replace(tzinfo=UTC)
            except ValueError:
                logger.warning("Eurostat updated 字段解析失败: %r（回退当前时间）", raw)
        return datetime.now(UTC)

    async def close(self) -> None:
        """关闭自持的 httpx 客户端（注入客户端由调用方管理）"""
        if self._owns_client:
            await self._client.aclose()


__all__ = ["EurostatAdapter"]
