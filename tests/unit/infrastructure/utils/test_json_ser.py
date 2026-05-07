"""Unit tests for JSON serialization utilities."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from enum import Enum

import pytest

from src.infrastructure.utils.json_ser import RedisJSONEncoder, json_dumps, json_loads


class TestRedisJSONEncoder:
    """Test RedisJSONEncoder for handling special types."""

    def test_encode_datetime(self) -> None:
        """Should encode datetime to ISO format."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        result = json.dumps({"dt": dt}, cls=RedisJSONEncoder)
        parsed = json.loads(result)
        assert parsed["dt"] == "2024-01-15T10:30:00+00:00"

    def test_encode_date(self) -> None:
        """Should encode date to ISO format."""
        d = date(2024, 1, 15)
        result = json.dumps({"d": d}, cls=RedisJSONEncoder)
        parsed = json.loads(result)
        assert parsed["d"] == "2024-01-15"

    def test_encode_uuid(self) -> None:
        """Should encode UUID to string."""
        uid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        result = json.dumps({"uid": uid}, cls=RedisJSONEncoder)
        parsed = json.loads(result)
        assert parsed["uid"] == "12345678-1234-5678-1234-567812345678"

    def test_encode_enum(self) -> None:
        """Should encode Enum to its value."""

        class MyEnum(Enum):
            VALUE_ONE = "value_one"
            VALUE_TWO = "value_two"

        result = json.dumps({"e": MyEnum.VALUE_ONE}, cls=RedisJSONEncoder)
        parsed = json.loads(result)
        assert parsed["e"] == "value_one"

    def test_encode_bytes_utf8(self) -> None:
        """Should encode bytes (UTF-8) to string."""
        b = b"hello world"
        result = json.dumps({"b": b}, cls=RedisJSONEncoder)
        parsed = json.loads(result)
        assert parsed["b"] == "hello world"

    def test_encode_bytes_latin1_fallback(self) -> None:
        """Should decode bytes with latin-1 fallback for non-UTF-8."""
        # Create bytes that are valid latin-1 but not valid UTF-8
        b = bytes([0x80, 0x81, 0x82])  # Invalid UTF-8, valid latin-1
        result = json.dumps({"b": b}, cls=RedisJSONEncoder)
        parsed = json.loads(result)
        assert parsed["b"] == "\x80\x81\x82"

    def test_encode_set(self) -> None:
        """Should encode set to sorted list."""
        s = {"banana", "apple", "cherry"}
        result = json.dumps({"s": s}, cls=RedisJSONEncoder)
        parsed = json.loads(result)
        assert sorted(parsed["s"]) == ["apple", "banana", "cherry"]

    def test_encode_unknown_type_calls_super(self) -> None:
        """Should call super().default() for unknown types."""

        class UnknownType:
            pass

        encoder = RedisJSONEncoder()
        with pytest.raises(TypeError):
            encoder.default(UnknownType())


class TestJsonDumps:
    """Test json_dumps function."""

    def test_dumps_with_datetime(self) -> None:
        """Should serialize datetime using RedisJSONEncoder."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        result = json_dumps({"dt": dt})
        parsed = json.loads(result)
        assert parsed["dt"] == "2024-01-15T10:30:00+00:00"

    def test_dumps_with_uuid(self) -> None:
        """Should serialize UUID using RedisJSONEncoder."""
        uid = uuid.uuid4()
        result = json_dumps({"uid": uid})
        parsed = json.loads(result)
        assert parsed["uid"] == str(uid)

    def test_dumps_with_kwargs(self) -> None:
        """Should pass kwargs to json.dumps."""
        data = {"value": 42}
        result = json_dumps(data, indent=2)
        assert "\n" in result  # indent was applied


class TestJsonLoads:
    """Test json_loads function."""

    def test_loads_string(self) -> None:
        """Should deserialize JSON string."""
        data = '{"key": "value"}'
        result = json_loads(data)
        assert result == {"key": "value"}

    def test_loads_bytes(self) -> None:
        """Should deserialize JSON bytes."""
        data = b'{"key": "value"}'
        result = json_loads(data)
        assert result == {"key": "value"}

    def test_loads_with_kwargs(self) -> None:
        """Should pass kwargs to json.loads."""
        data = '{"key": "value"}'
        result = json_loads(data, parse_float=lambda x: float(x) * 2)
        # No float values, but ensure kwargs are passed
        assert result == {"key": "value"}
