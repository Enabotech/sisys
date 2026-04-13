"""CacheEntry serialization tests."""

from __future__ import annotations

from datetime import UTC, datetime

from src.infrastructure.entities.cache_entry import CacheEntry


class TestCacheEntry:
    """CacheEntry 序列化/反序列化测试。"""

    def test_default_values(self) -> None:
        """CacheEntry 应有合理的默认值。"""
        entry = CacheEntry(
            cache_key="test-key",
            query_embedding=[0.1, 0.2, 0.3],
            result={"data": "value"},
        )
        assert entry.cache_key == "test-key"
        assert entry.query_embedding == [0.1, 0.2, 0.3]
        assert entry.result == {"data": "value"}
        assert entry.similarity_threshold == 0.9
        assert entry.ttl == 86400
        assert isinstance(entry.created_at, datetime)

    def test_to_dict_serialization(self) -> None:
        """to_dict 应正确序列化为字典。"""
        entry = CacheEntry(
            cache_key="test-key",
            query_embedding=[0.1, 0.2],
            result={"hit": True},
            similarity_threshold=0.95,
            ttl=3600,
        )
        result = entry.to_dict()
        assert result["cache_key"] == "test-key"
        assert result["query_embedding"] == [0.1, 0.2]
        assert result["result"] == {"hit": True}
        assert result["similarity_threshold"] == 0.95
        assert result["ttl"] == 3600
        assert isinstance(result["created_at"], str)

    def test_from_dict_deserialization(self) -> None:
        """from_dict 应正确从字典反序列化。"""
        data = {
            "cache_key": "test-key",
            "query_embedding": [0.1, 0.2, 0.3],
            "result": {"hit": True},
            "similarity_threshold": 0.85,
            "created_at": "2024-01-01T00:00:00+00:00",
            "ttl": 7200,
        }
        entry = CacheEntry.from_dict(data)
        assert entry.cache_key == "test-key"
        assert entry.query_embedding == [0.1, 0.2, 0.3]
        assert entry.result == {"hit": True}
        assert entry.similarity_threshold == 0.85
        assert entry.ttl == 7200

    def test_roundtrip(self) -> None:
        """to_dict -> from_dict 应保持数据不变。"""
        original = CacheEntry(
            cache_key="test-key",
            query_embedding=[0.1, 0.2, 0.3],
            result={"nested": {"key": "value"}},
            similarity_threshold=0.8,
            ttl=1800,
        )
        restored = CacheEntry.from_dict(original.to_dict())
        assert restored.cache_key == original.cache_key
        assert restored.query_embedding == original.query_embedding
        assert restored.result == original.result
        assert restored.similarity_threshold == original.similarity_threshold
        assert restored.ttl == original.ttl

    def test_from_dict_with_defaults(self) -> None:
        """from_dict 应使用默认值处理缺失字段。"""
        data = {
            "cache_key": "test-key",
            "query_embedding": [0.1],
            "result": {},
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        entry = CacheEntry.from_dict(data)
        assert entry.similarity_threshold == 0.9
        assert entry.ttl == 86400

    def test_from_dict_with_datetime_object(self) -> None:
        """from_dict 应接受 datetime 对象。"""
        now = datetime.now(UTC)
        data = {
            "cache_key": "test-key",
            "query_embedding": [0.1],
            "result": {},
            "created_at": now,
        }
        entry = CacheEntry.from_dict(data)
        assert entry.created_at == now
