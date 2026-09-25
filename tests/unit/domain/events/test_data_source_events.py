"""Story 4.1b — 数据源领域事件单元测试

验证 DataSourceFetched / DataSourceFetchFailed 的：
- event_type 注册与多态反序列化（DomainEvent._registry）
- aggregate 归属（ToolExecution，aggregate_id = execution_id）
- to_dict() 序列化（payload 含 source_name/query/freshness 等）
- 双通道配置一致性（configs/event_channels.yaml vs ChannelRouter.DEFAULT_MAPPINGS）
"""

from __future__ import annotations

import uuid
from typing import Any, cast

import yaml

from src.domain.events.base import DomainEvent
from src.domain.events.data_source_events import DataSourceFetched, DataSourceFetchFailed
from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode


class TestDataSourceFetched:
    def test_event_type_and_aggregate(self) -> None:
        eid = uuid.uuid4()
        event = DataSourceFetched(
            execution_id=eid,
            source_name="world-bank",
            query="GDP China",
            freshness_score=0.95,
            confidence=0.9,
            cache_hit=False,
            latency_ms=123.4,
        )
        assert event.event_type == "DataSourceFetched"
        assert event.aggregate_id == eid
        assert event.aggregate_type == "ToolExecution"

    def test_to_dict_payload(self) -> None:
        event = DataSourceFetched(
            execution_id=uuid.uuid4(),
            source_name="eurostat",
            query="unemployment DE",
            freshness_score=0.8,
            confidence=0.7,
            cache_hit=True,
            latency_ms=5.0,
        )
        d = event.to_dict()
        assert d["event_type"] == "DataSourceFetched"
        assert d["payload"]["source_name"] == "eurostat"
        assert d["payload"]["cache_hit"] is True
        assert d["payload"]["latency_ms"] == 5.0

    def test_polymorphic_deserialize(self) -> None:
        event = DataSourceFetched(execution_id=uuid.uuid4(), source_name="imf", query="WEO")
        restored = DomainEvent.from_dict(event.to_dict())
        assert type(restored) is DataSourceFetched
        assert restored.source_name == "imf"


class TestDataSourceFetchFailed:
    def test_event_type_and_aggregate(self) -> None:
        eid = uuid.uuid4()
        event = DataSourceFetchFailed(
            execution_id=eid,
            source_name="newsapi",
            query="tech",
            error_code="EXCEPTION_412",
            error_message="rate limited",
        )
        assert event.event_type == "DataSourceFetchFailed"
        assert event.aggregate_id == eid
        assert event.aggregate_type == "ToolExecution"

    def test_to_dict_payload(self) -> None:
        event = DataSourceFetchFailed(
            execution_id=uuid.uuid4(),
            source_name="imf",
            query="WEO",
            error_code="EXCEPTION_411",
            error_message="unavailable",
        )
        d = event.to_dict()
        assert d["payload"]["error_code"] == "EXCEPTION_411"
        assert d["payload"]["error_message"] == "unavailable"


class TestDualChannelConsistency:
    """双通道配置一致性（yaml 与 DEFAULT_MAPPINGS 两处同步，防 R6 配置漂移）。"""

    def _yaml_channels(self) -> dict[str, Any]:
        with open("configs/event_channels.yaml", encoding="utf-8") as f:
            config: dict[str, Any] = yaml.safe_load(f)
        return cast(dict[str, Any], config["event_channels"])

    def test_fetched_in_both_channels(self) -> None:
        yaml_cfg = self._yaml_channels()["DataSourceFetched"]
        mapping = ChannelRouter.DEFAULT_MAPPINGS["DataSourceFetched"]
        assert yaml_cfg["redis_channel"] == mapping.redis_channel == "sisys:rt:data_source_fetched"
        assert yaml_cfg["rabbitmq_routing_key"] == mapping.rabbitmq_routing_key == "sisys.events.reliable.data_source_fetched"
        assert mapping.delivery_mode is DeliveryMode.RELIABLE

    def test_fetch_failed_in_both_channels(self) -> None:
        yaml_cfg = self._yaml_channels()["DataSourceFetchFailed"]
        mapping = ChannelRouter.DEFAULT_MAPPINGS["DataSourceFetchFailed"]
        assert mapping.rabbitmq_routing_key == "sisys.events.reliable.data_source_fetch_failed"
        assert yaml_cfg["rabbitmq_routing_key"] == mapping.rabbitmq_routing_key
        assert mapping.delivery_mode is DeliveryMode.RELIABLE
