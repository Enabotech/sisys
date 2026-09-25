"""领域层数据源端口模块（Story 4.1b — Skills 数据采集基础设施）

R1 领域层统一抽象：DataSourcePort 定义单一外部数据源的获取契约，
8 个基础设施适配器（WorldBank/IMF/Eurostat/USPTO/IPCC/NewsAPI/Tavily/ChinaNBS）
均实现本端口，在 composition_root 统一注册（data_source_<name>）。

约束：
- 领域层零外部依赖（仅 Python 标准库）
- DataSourceQuery 为 DDD Query Object（多字段组合查询，CLAUDE.md §4 端口查询参数决策规则）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.data_source import DataSourceRef, DataSourceResult


@dataclass(frozen=True)
class DataSourceQuery:
    """数据源查询值对象（DDD Query Object 模式：多字段组合查询）

    Attributes:
        source_name: 目标数据源名称（对应 DataSourceRef.name）
        query: 查询表达式（如指标名/关键词，非空）
        parameters: 附加查询参数（如 (("geo", "DE"), ("year", "2025"))）
        tenant_id: 多租户隔离标识（缓存键前缀）
    """

    source_name: str
    query: str
    parameters: tuple[tuple[str, str], ...] = ()
    tenant_id: uuid.UUID | str | None = None

    def __post_init__(self) -> None:
        """字段不变量校验（抛 EntityValidationError EXCEPTION_242）"""
        if not self.source_name or not self.source_name.strip():
            raise EntityValidationError(
                message="source_name 不能为空",
                context={"entity": "DataSourceQuery", "field": "source_name"},
            )
        if not self.query or not self.query.strip():
            raise EntityValidationError(
                message="query 不能为空",
                context={"entity": "DataSourceQuery", "field": "query"},
            )


@runtime_checkable
class DataSourcePort(Protocol):
    """数据源端口——单一外部数据源的获取契约（R1 领域层统一抽象）

    实现约束：
    - fetch 失败抛 data_source 子域异常（410-413）或复用异常（302/101），
      重试语义由适配器内 tenacity 白名单收敛（仅 5xx/超时/传输错误可重试）
    - 实现必须为无状态或可重入（SINGLETON 生命周期注册）
    """

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """按查询获取数据

        Args:
            query: 数据源查询值对象

        Returns:
            DataSourceResult 采集结果（含 freshness/confidence 元数据）

        Raises:
            DataSourceUnavailableError: 数据源 5xx/连接失败（重试耗尽后）
            DataSourceRateLimitError: 数据源 429 限流
            DataSourceResponseError: 响应解析失败（不可重试）
            TimeoutError: 请求超时（EXCEPTION_302）
        """
        ...

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据（name/url/ttl_seconds/required_fields/api_type）"""
        ...

    async def health_check(self) -> bool:
        """探活（轻量端点或最近一次成功状态缓存），不消耗配额或最小消耗"""
        ...


__all__ = ["DataSourcePort", "DataSourceQuery"]
