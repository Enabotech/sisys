"""基础设施层 USPTO 数据源适配器（Story 4.1b）

USPTO PatentsView API（专利数据库，公开免费）：
- 端点：POST {base}/api/v1/patent/（JSON 查询体）
- 响应：{"patents": [{patent_id, patent_title, patent_date, ...}]}

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
from src.infrastructure.config.uspto import USPTOConfig
from src.infrastructure.external_services.datasources._http_helpers import (
    request_json_with_resilience,
)
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class USPTOAdapter:
    """USPTO 数据源适配器（REST_JSON，专利检索）"""

    def __init__(
        self,
        config: USPTOConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
    ) -> None:
        """初始化适配器（参数语义同 WorldBankAdapter）"""
        self._config = config or USPTOConfig()
        self._client = client or httpx.AsyncClient(base_url=self._config.api_url, timeout=self._config.timeout)
        self._owns_client = client is None
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=1,
            name="data-source-uspto",
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据"""
        return DataSourceRef(
            name="uspto",
            url=self._config.api_url,
            ttl_seconds=self._config.ttl_seconds,
            api_type=DataSourceApiType.REST_JSON,
        )

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """按关键词检索专利

        Args:
            query: DataSourceQuery（query=检索关键词，parameters 可含 ("page_size", "10")）

        Raises:
            DataSourceResponseError: 响应缺少 patents 字段
        """
        params_dict = dict(query.parameters)
        body: dict[str, Any] = {
            "q": {"_text_any": {"patent_title": query.query}},
            "f": ["patent_id", "patent_title", "patent_date", "assignees"],
            "o": {"size": int(params_dict.get("page_size", "10"))},
        }
        data = await request_json_with_resilience(
            self._client,
            "POST",
            "/api/v1/patent/",
            source_name="uspto",
            circuit_breaker=self._circuit_breaker,
            json_body=body,
            max_attempts=self._retry_max_attempts,
            min_wait=self._retry_min_wait,
            max_wait=self._retry_max_wait,
        )
        patents = self._extract_patents(data)
        source_ts = self._parse_source_timestamp(patents)
        return DataSourceResult(
            source_name="uspto",
            payload=json.dumps({"patents": patents}, ensure_ascii=False),
            source_timestamp=source_ts,
            fetched_at=datetime.now(UTC),
            freshness=DataFreshness(source_timestamp=source_ts, ttl_seconds=self._config.ttl_seconds),
            confidence=0.9,  # 官方专利库
        )

    async def health_check(self) -> bool:
        """探活（最小专利查询）"""
        try:
            await request_json_with_resilience(
                self._client,
                "POST",
                "/api/v1/patent/",
                source_name="uspto",
                circuit_breaker=self._circuit_breaker,
                json_body={"q": {"patent_id": "10000001"}, "f": ["patent_id"], "o": {"size": 1}},
                max_attempts=1,
            )
            return True
        except Exception as e:
            logger.warning("USPTO 探活失败: %s", type(e).__name__)
            return False

    def _extract_patents(self, data: Any) -> list[dict[str, Any]]:
        """提取 patents 字段（缺失抛 DataSourceResponseError）"""
        if not isinstance(data, dict) or "patents" not in data:
            raise DataSourceResponseError(
                message="USPTO 响应缺少 'patents' 字段",
                context={"source_name": "uspto", "actual_type": type(data).__name__},
            )
        patents = data["patents"]
        if not isinstance(patents, list):
            raise DataSourceResponseError(
                message="USPTO 响应 'patents' 字段非列表",
                context={"source_name": "uspto", "actual_type": type(patents).__name__},
            )
        return patents

    def _parse_source_timestamp(self, patents: list[dict[str, Any]]) -> datetime:
        """从最新专利 patent_date 解析源端时间戳，缺失回退当前时间"""
        latest: datetime | None = None
        for patent in patents:
            raw = patent.get("patent_date") if isinstance(patent, dict) else None
            if isinstance(raw, str):
                try:
                    ts = datetime.fromisoformat(raw).replace(tzinfo=UTC)
                except ValueError:
                    continue
                if latest is None or ts > latest:
                    latest = ts
        return latest or datetime.now(UTC)

    async def close(self) -> None:
        """关闭自持的 httpx 客户端（注入客户端由调用方管理）"""
        if self._owns_client:
            await self._client.aclose()


__all__ = ["USPTOAdapter"]
