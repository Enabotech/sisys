"""基础设施层 NewsAPI 数据源适配器（Story 4.1b）

NewsAPI（实时新闻流，替代 Reuters Connect）：
- 端点：GET {base}/v2/everything?q=...（Key 走 X-Api-Key 请求头，**URL 零泄露**）
- 响应：{"status": "ok", "totalResults": N, "articles": [...]}
- 免费档限额：100 次/天 → 熔断差异化配置（2 次失败即断开 600s，配额敏感）

实现 DataSourcePort。
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from src.domain.exceptions import ConfigurationError, DataSourceResponseError
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)
from src.infrastructure.config.newsapi import NewsAPIConfig
from src.infrastructure.external_services.datasources._http_helpers import (
    request_json_with_resilience,
)
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class NewsAPIAdapter:
    """NewsAPI 数据源适配器（REST_JSON + API Key，配额敏感早熔断）"""

    def __init__(
        self,
        config: NewsAPIConfig,
        *,
        client: httpx.AsyncClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
    ) -> None:
        """初始化适配器

        Args:
            config: NewsAPIConfig（api_key 必填）
            client: 可选注入的 httpx 客户端
            circuit_breaker: 可选熔断器（默认 2 次失败断开 600s——免费 100 次/天配额敏感）

        Raises:
            ConfigurationError: api_key 为空（EXCEPTION_101）
        """
        if not config.api_key:
            raise ConfigurationError(
                message="NewsAPI 数据源缺少 API Key（请配置环境变量 NEWSAPI_API_KEY）",
                context={"source_name": "newsapi", "field": "api_key"},
            )
        self._config = config
        self._client = client or httpx.AsyncClient(base_url=config.api_url, timeout=config.timeout)
        self._owns_client = client is None
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=600.0,
            half_open_max_calls=1,
            name="data-source-newsapi",
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据"""
        return DataSourceRef(
            name="newsapi",
            url=self._config.api_url,
            ttl_seconds=self._config.ttl_seconds,
            api_type=DataSourceApiType.REST_JSON,
        )

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """按关键词检索新闻

        Args:
            query: DataSourceQuery（query=关键词，parameters 可含 ("page_size", "10")）

        Raises:
            DataSourceResponseError: 响应缺少 articles 字段
        """
        params_dict = dict(query.parameters)
        data = await request_json_with_resilience(
            self._client,
            "GET",
            "/v2/everything",
            source_name="newsapi",
            circuit_breaker=self._circuit_breaker,
            params={"q": query.query, "pageSize": int(params_dict.get("page_size", "10")), "sortBy": "publishedAt"},
            headers={"X-Api-Key": self._config.api_key},
            max_attempts=self._retry_max_attempts,
            min_wait=self._retry_min_wait,
            max_wait=self._retry_max_wait,
        )
        articles = self._extract_articles(data)
        source_ts = self._parse_source_timestamp(articles)
        return DataSourceResult(
            source_name="newsapi",
            payload=json.dumps({"articles": articles}, ensure_ascii=False),
            source_timestamp=source_ts,
            fetched_at=datetime.now(UTC),
            freshness=DataFreshness(source_timestamp=source_ts, ttl_seconds=self._config.ttl_seconds),
            confidence=0.75,  # 新闻聚合源（中高置信度，需三角化）
        )

    async def health_check(self) -> bool:
        """探活（最小新闻查询，消耗 1 次配额）"""
        try:
            await request_json_with_resilience(
                self._client,
                "GET",
                "/v2/everything",
                source_name="newsapi",
                circuit_breaker=self._circuit_breaker,
                params={"q": "ping", "pageSize": 1},
                headers={"X-Api-Key": self._config.api_key},
                max_attempts=1,
            )
            return True
        except Exception as e:
            logger.warning("NewsAPI 探活失败: %s", type(e).__name__)
            return False

    def _extract_articles(self, data: Any) -> list[dict[str, Any]]:
        """提取 articles 字段（缺失抛 DataSourceResponseError）"""
        if not isinstance(data, dict) or "articles" not in data:
            raise DataSourceResponseError(
                message="NewsAPI 响应缺少 'articles' 字段",
                context={"source_name": "newsapi", "actual_type": type(data).__name__},
            )
        articles = data["articles"]
        if not isinstance(articles, list):
            raise DataSourceResponseError(
                message="NewsAPI 响应 'articles' 字段非列表",
                context={"source_name": "newsapi", "actual_type": type(articles).__name__},
            )
        return articles

    def _parse_source_timestamp(self, articles: list[dict[str, Any]]) -> datetime:
        """从最新文章 publishedAt 解析源端时间戳，缺失回退当前时间"""
        latest: datetime | None = None
        for article in articles:
            raw = article.get("publishedAt") if isinstance(article, dict) else None
            if isinstance(raw, str):
                try:
                    ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if latest is None or ts > latest:
                    latest = ts
        return latest or datetime.now(UTC)

    async def close(self) -> None:
        """关闭自持的 httpx 客户端（注入客户端由调用方管理）"""
        if self._owns_client:
            await self._client.aclose()


__all__ = ["NewsAPIAdapter"]
