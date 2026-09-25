"""领域层数据源事件模块（Story 4.1b — Skills 数据采集基础设施）

定义数据采集相关的领域事件：
- DataSourceFetched: 数据采集成功（含新鲜度/置信度/缓存命中/延迟埋点）
- DataSourceFetchFailed: 数据采集失败（含错误码/错误消息）

事件归属：ToolExecution 是执行聚合根（对齐 Story 4.1a ToolExecuted 模式），
aggregate_id = execution_id，aggregate_type = "ToolExecution"。

通道配置（双通道，需同步两处）：
- configs/event_channels.yaml（运行时主配置）
- ChannelRouter.DEFAULT_MAPPINGS（编译时 baseline）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from src.domain.events.base import DomainEvent


@dataclass(frozen=True)
class DataSourceFetched(DomainEvent):
    """数据采集成功事件

    Attributes:
        execution_id: ToolExecution 聚合根主键
        source_name: 数据源名称（如 "world-bank"）
        query: 查询表达式
        freshness_score: 采集时刻新鲜度评分 ∈ [0, 1]
        confidence: 置信度 ∈ [0, 1]
        cache_hit: 是否缓存命中
        latency_ms: 采集延迟（毫秒）
        event_type: 事件类型，固定为 "DataSourceFetched"
    """

    execution_id: uuid.UUID = field(default_factory=uuid.uuid4)
    source_name: str = ""
    query: str = ""
    freshness_score: float = 0.0
    confidence: float = 0.0
    cache_hit: bool = False
    latency_ms: float = 0.0
    event_type: str = field(default="DataSourceFetched", init=False)

    def __post_init__(self) -> None:
        """设置 aggregate_id 和 aggregate_type（对齐 ToolExecuted 模式）"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.execution_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "ToolExecution")


@dataclass(frozen=True)
class DataSourceFetchFailed(DomainEvent):
    """数据采集失败事件

    Attributes:
        execution_id: ToolExecution 聚合根主键
        source_name: 数据源名称
        query: 查询表达式
        error_code: 领域异常编码（如 "EXCEPTION_411"）
        error_message: 错误消息（面向调用方，不泄露堆栈/API Key）
        event_type: 事件类型，固定为 "DataSourceFetchFailed"
    """

    execution_id: uuid.UUID = field(default_factory=uuid.uuid4)
    source_name: str = ""
    query: str = ""
    error_code: str = ""
    error_message: str = ""
    event_type: str = field(default="DataSourceFetchFailed", init=False)

    def __post_init__(self) -> None:
        """设置 aggregate_id 和 aggregate_type（对齐 ToolExecuted 模式）"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.execution_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "ToolExecution")


__all__ = ["DataSourceFetched", "DataSourceFetchFailed"]
