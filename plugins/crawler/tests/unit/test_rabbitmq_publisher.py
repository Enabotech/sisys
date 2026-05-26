"""RabbitMQ 发布器单元测试

验证 RabbitMQPublisher 的消息构造

"""

from __future__ import annotations

from plugins.crawler.messaging.rabbitmq_publisher import RabbitMQPublisher


class TestRabbitMQPublisher:
    """RabbitMQPublisher 测试"""

    def test_build_message_contains_required_fields(self) -> None:
        """_build_message 应包含所有必需字段"""
        publisher = RabbitMQPublisher()
        message = publisher._build_message("CrawlCompleted", {"task_id": "t1"})

        assert message["event_type"] == "CrawlCompleted"
        assert message["event_id"]
        assert message["timestamp"]
        assert message["source"] == "crawler-service"
        assert message["schema_version"] == "1.0.0"
        assert message["aggregate_type"] == "CrawlTask"
        assert message["payload"]["task_id"] == "t1"

    def test_build_message_event_id_is_uuid(self) -> None:
        """event_id 应为 UUID 格式"""
        publisher = RabbitMQPublisher()
        message = publisher._build_message("CrawlCompleted", {})

        assert len(message["event_id"]) == 36
        assert "-" in message["event_id"]

    def test_build_message_timestamp_is_iso_format(self) -> None:
        """timestamp 应为 ISO 8601 格式"""
        publisher = RabbitMQPublisher()
        message = publisher._build_message("CrawlCompleted", {})

        assert "T" in message["timestamp"]
        assert message["timestamp"].endswith("Z") or "+" in message["timestamp"]

    def test_build_message_payload_preserved(self) -> None:
        """payload 字段应完整保留"""
        publisher = RabbitMQPublisher()
        payload = {"key1": "value1", "key2": 123}
        message = publisher._build_message("TestEvent", payload)

        assert message["payload"] == payload
