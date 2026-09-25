"""基础设施层 Tavily 数据源适配器（Story 4.1b）

Tavily Search API（Web 搜索 + 新闻聚合）：
- 端点：POST {base}/search（Key 走请求体 api_key 字段，**URL 零泄露**）
- 响应：{"results": [{title, url, content, score}], "answer": ...}

实现 DataSourcePort。容错：tenacity + CircuitBreaker（5 次/30s 默认档）。
安全：缺 Key 构造时抛 ConfigurationError(EXCEPTION_101)；Key 不出现在 URL/异常消息/日志。
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
from src.infrastructure.config.tavily import TavilyConfig
from src.infrastructure.external_services.datasources._http_helpers import (
    request_json_with_resilience,
)
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class TavilyAdapter:
    """Tavily 数据源适配器（REST_JSON + API Key）"""

    def __init__(
        self,
        config: TavilyConfig,
        *,
        client: httpx.AsyncClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
    ) -> None:
        """初始化适配器

        Args:
            config: TavilyConfig（api_key 必填）
            client: 可选注入的 httpx 客户端（测试注入 MockTransport）
            circuit_breaker: 可选熔断器（默认 5 次/30s）
            retry_max_attempts: 最大重试次数（含首次）
            retry_min_wait: 最小退避秒数
            retry_max_wait: 最大退避秒数

        Raises:
            ConfigurationError: api_key 为空（EXCEPTION_101，消息不含 Key 材料）
        """
        if not config.api_key:
            raise ConfigurationError(
                message="Tavily 数据源缺少 API Key（请配置环境变量 TAVILY_API_KEY）",
                context={"source_name": "tavily", "field": "api_key"},
            )
        self._config = config
        self._client = client or httpx.AsyncClient(base_url=config.api_url, timeout=config.timeout)
        self._owns_client = client is None
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=1,
            name="data-source-tavily",
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据"""
        return DataSourceRef(
            name="tavily",
            url=self._config.api_url,
            ttl_seconds=self._config.ttl_seconds,
            api_type=DataSourceApiType.REST_JSON,
        )

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """按关键词执行 Web 搜索

        Args:
            query: DataSourceQuery（query=搜索关键词，parameters 可含 ("max_results", "5")）

        Returns:
            DataSourceResult（payload 为 results/answer JSON 字符串）

        Raises:
            DataSourceResponseError: 响应缺少 results 字段
        """
        params_dict = dict(query.parameters)
        body: dict[str, Any] = {
            "api_key": self._config.api_key,
            "query": query.query,
            "max_results": int(params_dict.get("max_results", "5")),
        }
        data = await request_json_with_resilience(
            self._client,
            "POST",
            "/search",
            source_name="tavily",
            circuit_breaker=self._circuit_breaker,
            json_body=body,
            max_attempts=self._retry_max_attempts,
            min_wait=self._retry_min_wait,
            max_wait=self._retry_max_wait,
        )
        payload_obj = self._extract_payload(data)
        now = datetime.now(UTC)
        return DataSourceResult(
            source_name="tavily",
            payload=json.dumps(payload_obj, ensure_ascii=False),
            source_timestamp=now,  # 搜索结果实时性：源端时间戳即采集时刻
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=now, ttl_seconds=self._config.ttl_seconds),
            confidence=0.7,  # Web 聚合源（中置信度，需三角化）
        )

    async def health_check(self) -> bool:
        """探活（最小搜索请求）"""
        try:
            await request_json_with_resilience(
                self._client,
                "POST",
                "/search",
                source_name="tavily",
                circuit_breaker=self._circuit_breaker,
                json_body={"api_key": self._config.api_key, "query": "ping", "max_results": 1},
                max_attempts=1,
            )
            return True
        except Exception as e:
            logger.warning("Tavily 探活失败: %s", type(e).__name__)
            return False

    def _extract_payload(self, data: Any) -> dict[str, Any]:
        """提取 results/answer 字段（缺 results 抛 DataSourceResponseError）"""
        if not isinstance(data, dict) or "results" not in data:
            raise DataSourceResponseError(
                message="Tavily 响应缺少 'results' 字段",
                context={"source_name": "tavily", "actual_type": type(data).__name__},
            )
        return {"results": data["results"], "answer": data.get("answer", "")}

    async def close(self) -> None:
        """关闭自持的 httpx 客户端（注入客户端由调用方管理）"""
        if self._owns_client:
            await self._client.aclose()


__all__ = ["TavilyAdapter"]
