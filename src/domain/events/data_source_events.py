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
from dataclasses import dataclass, field, replace

from src.domain.events.base import DomainEvent
from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.data_source import validate_score


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
        """设置 aggregate_id/aggregate_type + 字段不变量校验

        校验（R3-3 H5v2）：事件跨进程序列化（Redis pub/sub + RabbitMQ）且
        from_dict 回放重建会重触发本方法——比 VO 更暴露的不可信契约面，
        越界分值/非数值将污染下游聚合看板。
        """
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.execution_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "ToolExecution")
        if not self.source_name or not self.source_name.strip():
            raise EntityValidationError(
                message="source_name 不能为空",
                context={"entity": "DataSourceFetched", "field": "source_name"},
            )
        validate_score(self.freshness_score, "freshness_score", "DataSourceFetched")
        validate_score(self.confidence, "confidence", "DataSourceFetched")

    def with_execution_id(self, execution_id: uuid.UUID) -> "DataSourceFetched":
        """绑定 execution_id（返回新实例，保留 frozen immutability 语义）。

        数据源采集时 execution_id 可能尚未生成（ad-hoc 调用场景），
        由 service 层在发布前调用本方法显式绑定到当前 execution_id，
        避免 Resolver 内部使用 object.__setattr__ 绕过 frozen。

        使用 dataclasses.replace（R3-P1-4 修复）：基类全部字段（event_id/
        timestamp/correlation_id/causation_id/metadata/version/source/
        schema_version/payload）原样保留——手工逐字段重建会令其回落默认值，
        追踪链静默断裂（event_id 重新生成、timestamp 漂移为 rebind 时刻）；
        event_type 为 init=False 字段不参与 replace（走类默认值，安全）。

        Returns:
            新的 DataSourceFetched 实例，execution_id/aggregate_id 已绑定，
            其余字段与原实例逐字段相等
        """
        return replace(self, execution_id=execution_id, aggregate_id=execution_id)


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
        """设置 aggregate_id/aggregate_type + source_name 非空校验（R3-3 H5v2）"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.execution_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "ToolExecution")
        if not self.source_name or not self.source_name.strip():
            raise EntityValidationError(
                message="source_name 不能为空",
                context={"entity": "DataSourceFetchFailed", "field": "source_name"},
            )

    def with_execution_id(self, execution_id: uuid.UUID) -> "DataSourceFetchFailed":
        """绑定 execution_id（返回新实例，保留 frozen immutability 语义）。

        详见 DataSourceFetched.with_execution_id 文档（dataclasses.replace
        保留基类全部字段，R3-P1-4 修复）。
        """
        return replace(self, execution_id=execution_id, aggregate_id=execution_id)


__all__ = ["DataSourceFetched", "DataSourceFetchFailed"]
