"""领域层数据源值对象模块

定义 Skills 数据采集基础设施（Story 4.1b）的不可变值对象：
- DataSourceApiType: 数据源 API 类型枚举（rest_json / sdmx_json / csv_download / crawler）
- DataSourceRef: 数据源引用元数据（name/url/ttl_seconds/required_fields/api_type）
- DataFreshness: 数据新鲜度评分（指数衰减 + TTL stale 判定）
- DataSourceResult: 采集结果（payload + source_timestamp + freshness + confidence）
- DataSourceMeta: 证据包溯源元数据（挂接到 EvidencePackage.data_sources）

约束：
- 领域层零外部依赖（仅 Python 标准库）
- @dataclass(frozen=True) 不可变
- 不变量违反抛 EntityValidationError（EXCEPTION_242），禁止 ValueError
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.domain.exceptions import EntityValidationError

# 数据源名称：kebab-case（对齐 skill slug 规范 _SLUG_PATTERN）
_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# TTL 合法范围（参考 redis_snapshot_store.py 运行时强制校验先例 [60, 2592000]）
_MIN_TTL_SECONDS = 60
_MAX_TTL_SECONDS = 2592000


class DataSourceApiType(str, Enum):
    """数据源 API 类型枚举

    - REST_JSON: REST JSON API（WorldBank/USPTO/NewsAPI/Tavily）
    - SDMX_JSON: SDMX 统计数据交换格式（IMF/Eurostat）
    - CSV_DOWNLOAD: CSV 文件下载（IPCC）
    - CRAWLER: 爬虫插件采集（中国国家统计局，经 CrawlerClientPort）
    """

    REST_JSON = "rest_json"
    SDMX_JSON = "sdmx_json"
    CSV_DOWNLOAD = "csv_download"
    CRAWLER = "crawler"


def _validate_score(value: float, field_name: str, entity: str) -> None:
    """校验评分字段 ∈ [0.0, 1.0]（confidence/freshness_score 共用）。"""
    if not (0.0 <= value <= 1.0):
        raise EntityValidationError(
            message=f"{field_name} 必须 ∈ [0.0, 1.0]，实际 {value}",
            context={"entity": entity, "field": field_name, "value": value, "constraint": "[0.0, 1.0]"},
        )


@dataclass(frozen=True)
class DataSourceRef:
    """数据源引用元数据（ToolMetadata.data_sources 的元素）

    Attributes:
        name: 数据源名称（kebab-case，如 "world-bank"）
        url: 数据源基础 URL（必须 http/https）
        ttl_seconds: 缓存 TTL（秒），∈ [60, 2592000]，默认 86400（1 天）
        required_fields: 响应必需字段（缺失抛 DataSourceResponseError）
        api_type: API 类型（决定适配器解析策略）
    """

    name: str
    url: str
    api_type: DataSourceApiType
    ttl_seconds: int = 86400
    required_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """字段不变量校验（抛 EntityValidationError EXCEPTION_242）"""
        if not self.name or not _NAME_PATTERN.match(self.name):
            raise EntityValidationError(
                message=f"name 必须为非空 kebab-case，实际 {self.name!r}",
                context={"entity": "DataSourceRef", "field": "name", "value": self.name},
            )
        if not self.url.startswith(("http://", "https://")):
            raise EntityValidationError(
                message=f"url 必须为 http(s) URL，实际 {self.url!r}",
                context={"entity": "DataSourceRef", "field": "url", "value": self.url},
            )
        if not (_MIN_TTL_SECONDS <= self.ttl_seconds <= _MAX_TTL_SECONDS):
            raise EntityValidationError(
                message=f"ttl_seconds 必须 ∈ [{_MIN_TTL_SECONDS}, {_MAX_TTL_SECONDS}]，实际 {self.ttl_seconds}",
                context={
                    "entity": "DataSourceRef",
                    "field": "ttl_seconds",
                    "value": self.ttl_seconds,
                    "constraint": f"[{_MIN_TTL_SECONDS}, {_MAX_TTL_SECONDS}]",
                },
            )
        if not isinstance(self.api_type, DataSourceApiType):
            raise EntityValidationError(
                message="api_type 必须为 DataSourceApiType 枚举值",
                context={"entity": "DataSourceRef", "field": "api_type"},
            )


@dataclass(frozen=True)
class DataFreshness:
    """数据新鲜度值对象（指数衰减评分 + TTL stale 判定）

    评分模型：score(at) = 0.5 ** (age / half_life_seconds)（指数衰减，业界惯例：
    Prometheus staleness / CDN stale-while-revalidate）。
    默认半衰期 604800 秒（7 天），适配 World Bank/IMF 年度统计数据场景。

    Attributes:
        source_timestamp: 数据源端数据的原始时间戳
        ttl_seconds: 缓存 TTL（秒），超过则判定 stale
        half_life_seconds: 新鲜度半衰期（秒），默认 604800（7 天）
    """

    source_timestamp: datetime
    ttl_seconds: int
    half_life_seconds: int = 604800

    def __post_init__(self) -> None:
        """字段不变量校验"""
        if self.ttl_seconds <= 0:
            raise EntityValidationError(
                message=f"ttl_seconds 必须 > 0，实际 {self.ttl_seconds}",
                context={"entity": "DataFreshness", "field": "ttl_seconds", "value": self.ttl_seconds},
            )
        if self.half_life_seconds <= 0:
            raise EntityValidationError(
                message=f"half_life_seconds 必须 > 0，实际 {self.half_life_seconds}",
                context={"entity": "DataFreshness", "field": "half_life_seconds", "value": self.half_life_seconds},
            )

    def score(self, at: datetime) -> float:
        """计算 at 时刻的新鲜度评分（指数衰减，∈ [0, 1]）

        Args:
            at: 评估时刻

        Returns:
            新鲜度评分；未来时间戳（age < 0）按满分 1.0 处理（时钟偏移容错）
        """
        age_seconds = max(0.0, (at - self.source_timestamp).total_seconds())
        return math.pow(0.5, age_seconds / self.half_life_seconds)

    def is_stale(self, at: datetime) -> bool:
        """判定 at 时刻数据是否过期（age > ttl_seconds）

        Args:
            at: 评估时刻

        Returns:
            True 表示已过期（应触发重新采集）
        """
        return (at - self.source_timestamp).total_seconds() > self.ttl_seconds


@dataclass(frozen=True)
class DataSourceResult:
    """数据采集结果值对象

    Attributes:
        source_name: 数据源名称（对应 DataSourceRef.name）
        payload: 采集载荷（JSON 字符串，非空）
        source_timestamp: 数据在源端的原始时间戳
        fetched_at: 本次采集完成时间戳
        freshness: 新鲜度评分值对象
        confidence: 置信度 ∈ [0.0, 1.0]
        cache_hit: 是否缓存命中（True 表示未消耗外部配额）
    """

    source_name: str
    payload: str
    source_timestamp: datetime
    fetched_at: datetime
    freshness: DataFreshness
    confidence: float
    cache_hit: bool = False

    def __post_init__(self) -> None:
        """字段不变量校验"""
        if not self.source_name or not self.source_name.strip():
            raise EntityValidationError(
                message="source_name 不能为空",
                context={"entity": "DataSourceResult", "field": "source_name"},
            )
        if not self.payload:
            raise EntityValidationError(
                message="payload 不能为空",
                context={"entity": "DataSourceResult", "field": "payload"},
            )
        _validate_score(self.confidence, "confidence", "DataSourceResult")


@dataclass(frozen=True)
class DataSourceMeta:
    """数据源溯源元数据（挂接 EvidencePackage.data_sources，支撑输出溯源）

    Attributes:
        source_name: 数据源名称
        source_timestamp: 数据在源端的原始时间戳
        freshness_score: 采集时刻的新鲜度评分 ∈ [0.0, 1.0]
        confidence: 置信度 ∈ [0.0, 1.0]
    """

    source_name: str
    source_timestamp: datetime
    freshness_score: float
    confidence: float

    def __post_init__(self) -> None:
        """字段不变量校验"""
        if not self.source_name or not self.source_name.strip():
            raise EntityValidationError(
                message="source_name 不能为空",
                context={"entity": "DataSourceMeta", "field": "source_name"},
            )
        _validate_score(self.freshness_score, "freshness_score", "DataSourceMeta")
        _validate_score(self.confidence, "confidence", "DataSourceMeta")


__all__ = [
    "DataFreshness",
    "DataSourceApiType",
    "DataSourceMeta",
    "DataSourceRef",
    "DataSourceResult",
]
