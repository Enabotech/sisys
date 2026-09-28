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

import pytest
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


class TestWithExecutionIdFieldPreservation:
    """with_execution_id 字段保留语义（R3-P1-4 修复）

    修复前手工逐字段重建丢失基类 9 个字段（event_id 重新生成、timestamp 漂移为
    rebind 时刻、correlation_id/causation_id/metadata/version/source/schema_version/
    payload 回落默认值）——追踪链静默断裂。判别锚点：回退为手工重建本组用例必红。
    """

    @staticmethod
    def _make_fetched() -> DataSourceFetched:
        """构造带全量基类字段的源事件（rebind 前快照）"""
        return DataSourceFetched(
            source_name="world-bank",
            query="NY.GDP.MKTP.CD",
            freshness_score=0.9,
            confidence=0.85,
            cache_hit=False,
            latency_ms=42.0,
            correlation_id=uuid.uuid4(),
            causation_id=uuid.uuid4(),
            metadata={"tenant": "t-1"},
            version=7,
            source="resolver",
        )

    def test_base_fields_preserved_after_rebind(self) -> None:
        """rebind 后基类核心标识字段逐一保留（event_id/timestamp/correlation_id/
        causation_id/metadata/version/source/schema_version/payload 九字段相等）"""
        original = self._make_fetched()
        rebound = original.with_execution_id(uuid.uuid4())
        assert rebound.event_id == original.event_id  # 修复前：重新生成
        assert rebound.timestamp == original.timestamp  # 修复前：漂移为 rebind 时刻
        assert rebound.correlation_id == original.correlation_id
        assert rebound.causation_id == original.causation_id
        assert rebound.metadata == original.metadata
        assert rebound.version == original.version
        assert rebound.source == original.source
        assert rebound.schema_version == original.schema_version
        assert rebound.payload == original.payload
        # 业务字段与绑定字段
        assert rebound.execution_id != original.execution_id
        assert rebound.aggregate_id == rebound.execution_id
        assert rebound.source_name == original.source_name
        assert rebound.query == original.query

    def test_to_dict_equivalent_except_execution(self) -> None:
        """rebind 前后 to_dict() 序列化面等价（execution_id/aggregate_id 除外）——
        锁定消费方视角的序列化稳定性"""
        original = self._make_fetched()
        rebound = original.with_execution_id(uuid.uuid4())
        raw_o, raw_r = original.to_dict(), rebound.to_dict()
        payload_o = {k: v for k, v in raw_o["payload"].items() if k != "execution_id"}
        payload_r = {k: v for k, v in raw_r["payload"].items() if k != "execution_id"}
        assert payload_o == payload_r
        assert raw_o["event_id"] == raw_r["event_id"]
        assert raw_o["timestamp"] == raw_r["timestamp"]

    def test_fetch_failed_base_fields_preserved(self) -> None:
        """DataSourceFetchFailed.with_execution_id 同样保留基类字段（同构修复）"""
        original = DataSourceFetchFailed(
            source_name="newsapi",
            query="keyword",
            error_code="EXCEPTION_412",
            error_message="限流",
            correlation_id=uuid.uuid4(),
            metadata={"attempt": 1},
        )
        rebound = original.with_execution_id(uuid.uuid4())
        assert rebound.event_id == original.event_id
        assert rebound.timestamp == original.timestamp
        assert rebound.correlation_id == original.correlation_id
        assert rebound.metadata == original.metadata
        assert rebound.error_code == original.error_code
        assert rebound.error_message == original.error_message


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


class TestEventFieldValidation:
    """事件字段不变量校验（R3-3 H5v2：跨进程序列化 + from_dict 回放重建重触发
    __post_init__——比 VO 更暴露的不可信契约面）"""

    def test_fetched_out_of_range_score_rejected(self) -> None:
        """freshness_score/confidence 越界 → 242（原可静默构造并污染下游聚合看板）"""
        from src.domain.exceptions import EntityValidationError

        with pytest.raises(EntityValidationError, match="freshness_score"):
            DataSourceFetched(source_name="world-bank", freshness_score=9.9)
        with pytest.raises(EntityValidationError, match="confidence"):
            DataSourceFetched(source_name="world-bank", confidence=-3.0)

    def test_fetched_non_numeric_score_rejected(self) -> None:
        """非数值分值（str/None/bool——from_dict 回放畸形消息形态）→ 242（H5v2-①：
        原在数值比较抛内置 TypeError 逃逸领域异常体系）"""

        from src.domain.exceptions import EntityValidationError

        for bad_score in ["0.5", None, True]:
            kwargs: dict[str, Any] = {"source_name": "world-bank", "freshness_score": bad_score}
            with pytest.raises(EntityValidationError, match="必须为数值"):
                DataSourceFetched(**kwargs)

    def test_empty_source_name_rejected(self) -> None:
        """空 source_name → 242（两事件同构）"""
        from src.domain.exceptions import EntityValidationError

        with pytest.raises(EntityValidationError, match="source_name"):
            DataSourceFetched(source_name="  ")
        with pytest.raises(EntityValidationError, match="source_name"):
            DataSourceFetchFailed(source_name="  ", error_code="EXCEPTION_411", error_message="x")

    def test_from_dict_roundtrip_valid_event(self) -> None:
        """合法事件 to_dict → from_dict 回放回归（新校验不破坏回放链路）"""
        event = DataSourceFetched(source_name="imf", query="NGDP_RPCH", freshness_score=0.8, confidence=0.7)
        rebuilt = DataSourceFetched.from_dict(event.to_dict())
        assert isinstance(rebuilt, DataSourceFetched)
        assert rebuilt.source_name == "imf"
