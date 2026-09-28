"""Story 4.1b — 数据源值对象单元测试

验证 DataSourceRef / DataSourceApiType / DataSourceQuery / DataSourceResult /
DataFreshness / DataSourceMeta 的不变量校验与新鲜度评分语义。

约束：
- 不变量违反抛 EntityValidationError（EXCEPTION_242），禁止 ValueError
- 全部值对象 frozen 不可变（setattr 触发 FrozenInstanceError）
"""

from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.domain.exceptions import EntityValidationError
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceMeta,
    DataSourceRef,
    DataSourceResult,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _make_ref(
    name: str = "world-bank",
    url: str = "https://api.worldbank.org/v2",
    ttl_seconds: int = 86400,
    required_fields: tuple[str, ...] = ("value",),
    api_type: DataSourceApiType = DataSourceApiType.REST_JSON,
) -> DataSourceRef:
    """构造 DataSourceRef（测试工厂，默认全合法）。"""
    return DataSourceRef(
        name=name,
        url=url,
        ttl_seconds=ttl_seconds,
        required_fields=required_fields,
        api_type=api_type,
    )


# ===================================================================
# DataSourceRef 不变量
# ===================================================================


class TestDataSourceRef:
    def test_valid_construction(self) -> None:
        ref = _make_ref()
        assert ref.name == "world-bank"
        assert ref.ttl_seconds == 86400
        assert ref.api_type == DataSourceApiType.REST_JSON

    def test_default_ttl_and_required_fields(self) -> None:
        ref = DataSourceRef(name="imf", url="https://imf.org/api", api_type=DataSourceApiType.SDMX_JSON)
        assert ref.ttl_seconds == 86400
        assert ref.required_fields == ()

    @pytest.mark.parametrize("bad_name", ["", "  ", "World_Bank", "WORLD", "-bad", "bad-"])
    def test_invalid_name_raises(self, bad_name: str) -> None:
        with pytest.raises(EntityValidationError) as exc_info:
            _make_ref(name=bad_name)
        assert exc_info.value.code == "EXCEPTION_242"

    @pytest.mark.parametrize("bad_ttl", [0, 59, -1, 2592001])
    def test_invalid_ttl_raises(self, bad_ttl: int) -> None:
        with pytest.raises(EntityValidationError) as exc_info:
            _make_ref(ttl_seconds=bad_ttl)
        assert exc_info.value.code == "EXCEPTION_242"

    @pytest.mark.parametrize("ttl", [60, 2592000])
    def test_ttl_boundary_accepted(self, ttl: int) -> None:
        assert _make_ref(ttl_seconds=ttl).ttl_seconds == ttl

    @pytest.mark.parametrize("bad_url", ["", "ftp://x.com", "api.worldbank.org", "javascript://x"])
    def test_invalid_url_raises(self, bad_url: str) -> None:
        with pytest.raises(EntityValidationError):
            _make_ref(url=bad_url)

    @pytest.mark.parametrize(
        ("field", "bad_value"),
        [
            ("name", 123),  # name: 123 → 原 re.match 抛原生 TypeError 逃逸
            ("url", 123),  # url: 123 → 原 startswith 抛原生 AttributeError 逃逸
            ("ttl_seconds", "604800"),  # YAML 引号字符串 → 原比较抛原生 TypeError 逃逸
            ("ttl_seconds", None),  # YAML 空值 → 原 int<=None 抛原生 TypeError 逃逸
            ("ttl_seconds", 60.5),  # float 混入
        ],
    )
    def test_scalar_type_confusion_rejected(self, field: str, bad_value: Any) -> None:
        """SKILL.md frontmatter 标量类型混淆在 VO 构造侧拦截（R3-2 G3：YAML
        编排错误原以原生 TypeError/AttributeError 逃逸领域异常体系——红线破口）。

        bad_value 为 Any：本用例的语义就是「故意传错误类型验证 VO 门禁」，
        Any 是对该意图的诚实类型表达（非性能或省事）。
        """
        kwargs: dict[str, Any] = {field: bad_value}
        with pytest.raises(EntityValidationError, match="必须为"):
            DataSourceRef(
                name=kwargs.get("name", "world-bank"),
                url=kwargs.get("url", "https://x.local/api"),
                api_type=DataSourceApiType.REST_JSON,
                ttl_seconds=kwargs.get("ttl_seconds", 86400),
            )

    def test_required_fields_scalar_and_non_str_elements_rejected(self) -> None:
        """required_fields 标量（str 透传 → 子串匹配退化）与非 str 元素（tuple[int,...]）拦截"""
        bad_values: list[Any] = ["indicator", (1, 2)]  # Any 语义同上：故意破坏类型验证门禁
        for bad_value in bad_values:
            with pytest.raises(EntityValidationError, match="tuple"):
                DataSourceRef(
                    name="world-bank",
                    url="https://x.local/api",
                    api_type=DataSourceApiType.REST_JSON,
                    required_fields=bad_value,
                )

    def test_frozen(self) -> None:
        ref = _make_ref()
        with pytest.raises(FrozenInstanceError):
            setattr(ref, "name", "other")


# ===================================================================
# DataSourceApiType 枚举
# ===================================================================


class TestDataSourceApiType:
    def test_four_values(self) -> None:
        assert {m.value for m in DataSourceApiType} == {"rest_json", "sdmx_json", "csv_download", "crawler"}

    def test_str_enum(self) -> None:
        assert DataSourceApiType.REST_JSON == "rest_json"
        assert isinstance(DataSourceApiType.CRAWLER, str)


# ===================================================================
# DataSourceQuery（Query Object）
# ===================================================================


class TestDataSourceQuery:
    def test_valid_construction(self) -> None:
        q = DataSourceQuery(source_name="world-bank", query="GDP China")
        assert q.parameters == ()
        assert q.tenant_id is None

    def test_full_fields(self) -> None:
        tid = uuid.uuid4()
        q = DataSourceQuery(
            source_name="eurostat",
            query="unemployment",
            parameters=(("geo", "DE"), ("year", "2025")),
            tenant_id=tid,
        )
        assert q.parameters == (("geo", "DE"), ("year", "2025"))
        assert q.tenant_id == tid

    def test_empty_source_name_raises(self) -> None:
        with pytest.raises(EntityValidationError):
            DataSourceQuery(source_name="  ", query="GDP")

    def test_empty_query_raises(self) -> None:
        with pytest.raises(EntityValidationError):
            DataSourceQuery(source_name="world-bank", query=" ")

    def test_frozen(self) -> None:
        q = DataSourceQuery(source_name="imf", query="WEO")
        with pytest.raises(FrozenInstanceError):
            setattr(q, "query", "other")


# ===================================================================
# DataFreshness 新鲜度评分
# ===================================================================


class TestDataFreshness:
    def test_score_one_at_source_time(self) -> None:
        ts = _now()
        f = DataFreshness(source_timestamp=ts, ttl_seconds=86400)
        assert f.score(ts) == pytest.approx(1.0)

    def test_score_half_at_half_life(self) -> None:
        ts = _now()
        f = DataFreshness(source_timestamp=ts, ttl_seconds=86400 * 14, half_life_seconds=604800)
        at = ts + timedelta(seconds=604800)
        assert f.score(at) == pytest.approx(0.5, abs=0.01)

    def test_score_monotonic_decreasing(self) -> None:
        ts = _now()
        f = DataFreshness(source_timestamp=ts, ttl_seconds=86400 * 30)
        scores = [f.score(ts + timedelta(days=d)) for d in (0, 1, 7, 14, 30)]
        assert all(a >= b for a, b in zip(scores, scores[1:], strict=False))
        assert all(0.0 <= s <= 1.0 for s in scores)

    def test_is_stale_boundary(self) -> None:
        ts = _now()
        f = DataFreshness(source_timestamp=ts, ttl_seconds=60)
        assert f.is_stale(ts + timedelta(seconds=59)) is False
        assert f.is_stale(ts + timedelta(seconds=61)) is True

    def test_invalid_ttl_raises(self) -> None:
        with pytest.raises(EntityValidationError):
            DataFreshness(source_timestamp=_now(), ttl_seconds=0)

    def test_invalid_half_life_raises(self) -> None:
        with pytest.raises(EntityValidationError):
            DataFreshness(source_timestamp=_now(), ttl_seconds=60, half_life_seconds=0)

    def test_naive_source_timestamp_rejected(self) -> None:
        """naive source_timestamp 构造拒绝（R3-P1-5：tz-awareness 门禁——naive 输入
        在 score()/is_stale() 与 aware 时刻混算抛原生 TypeError，必须构造侧拦截）"""
        with pytest.raises(EntityValidationError, match="tz-aware"):
            DataFreshness(source_timestamp=datetime(2024, 1, 1), ttl_seconds=60)

    def test_naive_at_rejected_by_score_and_is_stale(self) -> None:
        """naive 评估时刻 at 在 score()/is_stale() 入口拒绝（调用侧闭环——
        抛 EntityValidationError 而非原生 TypeError 逃逸领域契约）"""
        f = DataFreshness(source_timestamp=_now(), ttl_seconds=60)
        with pytest.raises(EntityValidationError, match="tz-aware"):
            f.score(datetime(2025, 1, 1))
        with pytest.raises(EntityValidationError, match="tz-aware"):
            f.is_stale(datetime(2025, 1, 1))


# ===================================================================
# DataSourceResult
# ===================================================================


def _make_result(
    payload: str = '{"value": 1.23}',
    confidence: float = 0.9,
) -> DataSourceResult:
    """构造 DataSourceResult（测试工厂，默认全合法）。"""
    ts = _now()
    return DataSourceResult(
        source_name="world-bank",
        payload=payload,
        source_timestamp=ts,
        fetched_at=ts,
        freshness=DataFreshness(source_timestamp=ts, ttl_seconds=86400),
        confidence=confidence,
    )


class TestDataSourceResult:
    def test_valid_construction(self) -> None:
        r = _make_result()
        assert r.cache_hit is False
        assert r.confidence == 0.9

    def test_naive_timestamps_rejected(self) -> None:
        """naive source_timestamp / fetched_at 构造拒绝（R3-P1-5，同 DataFreshness）"""
        aware_ts = _now()
        with pytest.raises(EntityValidationError, match="tz-aware"):
            DataSourceResult(
                source_name="world-bank",
                payload='{"v": 1}',
                source_timestamp=datetime(2024, 1, 1),  # naive
                fetched_at=aware_ts,
                freshness=DataFreshness(source_timestamp=aware_ts, ttl_seconds=60),
                confidence=0.9,
            )
        with pytest.raises(EntityValidationError, match="tz-aware"):
            DataSourceResult(
                source_name="world-bank",
                payload='{"v": 1}',
                source_timestamp=aware_ts,
                fetched_at=datetime(2024, 1, 1),  # naive
                freshness=DataFreshness(source_timestamp=aware_ts, ttl_seconds=60),
                confidence=0.9,
            )

    def test_empty_payload_raises(self) -> None:
        with pytest.raises(EntityValidationError):
            _make_result(payload="")

    @pytest.mark.parametrize("bad_confidence", [-0.1, 1.1])
    def test_confidence_out_of_range_raises(self, bad_confidence: float) -> None:
        with pytest.raises(EntityValidationError):
            _make_result(confidence=bad_confidence)

    @pytest.mark.parametrize("ok_confidence", [0.0, 0.5, 1.0])
    def test_confidence_boundary_accepted(self, ok_confidence: float) -> None:
        assert _make_result(confidence=ok_confidence).confidence == ok_confidence

    def test_frozen(self) -> None:
        r = _make_result()
        with pytest.raises(FrozenInstanceError):
            setattr(r, "payload", "{}")


# ===================================================================
# DataSourceMeta（证据包溯源元数据）
# ===================================================================


def _make_meta(freshness_score: float = 0.5, confidence: float = 0.5, source_name: str = "imf") -> DataSourceMeta:
    """构造 DataSourceMeta（测试工厂，默认全合法）。"""
    return DataSourceMeta(
        source_name=source_name,
        source_timestamp=_now(),
        freshness_score=freshness_score,
        confidence=confidence,
    )


class TestDataSourceMeta:
    def test_valid_construction(self) -> None:
        meta = _make_meta(freshness_score=0.95, confidence=0.8, source_name="eurostat")
        assert meta.source_name == "eurostat"

    @pytest.mark.parametrize("bad", [-0.01, 1.01])
    def test_freshness_score_range(self, bad: float) -> None:
        with pytest.raises(EntityValidationError):
            _make_meta(freshness_score=bad)

    @pytest.mark.parametrize("bad", [-0.01, 1.01])
    def test_confidence_range(self, bad: float) -> None:
        with pytest.raises(EntityValidationError):
            _make_meta(confidence=bad)

    def test_empty_source_name_raises(self) -> None:
        with pytest.raises(EntityValidationError):
            _make_meta(source_name="")
