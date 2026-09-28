"""Story 4.1b — data_source 子域异常单元测试（EXCEPTION_410-413）

验证 4 个新异常的构造 / code / context / to_dict() 序列化 / cause 链 / HTTP 映射。
完整性 Checklist 伴随验证：子域注册（test_code_ranges.py）+ 编码唯一性
（test_error_code_uniqueness.py）由既有全套测试覆盖。
"""

from __future__ import annotations

from fastapi import status

from src.domain.exceptions import (
    DataSourceError,
    DataSourceRateLimitError,
    DataSourceResponseError,
    DataSourceUnavailableError,
    ExternalException,
)
from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP


class TestDataSourceError:
    """EXCEPTION_410 数据源通用错误基类。"""

    def test_code_and_hierarchy(self) -> None:
        exc = DataSourceError(message="采集失败")
        assert exc.code == "EXCEPTION_410"
        assert isinstance(exc, ExternalException)
        assert exc.message == "采集失败"

    def test_default_message(self) -> None:
        assert DataSourceError().message == "Data source error"

    def test_context_and_to_dict(self) -> None:
        exc = DataSourceError(message="m", context={"source_name": "world-bank", "query": "GDP"})
        d = exc.to_dict()
        assert d["code"] == "EXCEPTION_410"
        assert d["context"]["source_name"] == "world-bank"
        assert d["context"]["query"] == "GDP"

    def test_cause_chain(self) -> None:
        cause = RuntimeError("network down")
        exc = DataSourceError(message="m", cause=cause)
        d = exc.to_dict()
        assert d["cause"]["type"] == "RuntimeError"
        assert "network down" in d["cause"]["message"]


class TestDataSourceUnavailableError:
    """EXCEPTION_411 数据源不可用（5xx/连接失败/熔断断开）。"""

    def test_code(self) -> None:
        exc = DataSourceUnavailableError(message="服务不可用")
        assert exc.code == "EXCEPTION_411"
        assert isinstance(exc, DataSourceError)

    def test_context_fields(self) -> None:
        exc = DataSourceUnavailableError(context={"source_name": "imf", "url": "https://imf.org/api"})
        assert exc.context["source_name"] == "imf"
        assert exc.context["url"] == "https://imf.org/api"


class TestDataSourceRateLimitError:
    """EXCEPTION_412 数据源限流（429）。"""

    def test_code(self) -> None:
        exc = DataSourceRateLimitError(message="限流")
        assert exc.code == "EXCEPTION_412"
        assert isinstance(exc, DataSourceError)

    def test_retry_after_context(self) -> None:
        """412 的 retry_after 经 to_dict 序列化面暴露（code 绑定 + 脱敏管线穿透，
        R3-4 K3：原 dict 直读是构造什么断言什么的零判别往返）"""
        exc = DataSourceRateLimitError(context={"source_name": "newsapi", "retry_after": 3600})
        d = exc.to_dict()
        assert d["code"] == "EXCEPTION_412"
        assert d["context"]["retry_after"] == 3600

    def test_context_url_redacted_through_to_dict(self) -> None:
        """context 含敏感 URL 参数时经 to_dict 脱敏（镜像验收三断言：原串消失 +
        REDACTED 阳性对照 + 非敏感参数保留防过度脱敏）"""
        exc = DataSourceRateLimitError(
            context={"source_name": "newsapi", "url": "https://api.newsapi.org/v2?api_key=secret-123&q=gdp"}
        )
        d = exc.to_dict()
        serialized = str(d)
        assert "secret-123" not in serialized
        assert "***REDACTED***" in serialized
        assert "q=gdp" in serialized


class TestDataSourceResponseError:
    """EXCEPTION_413 响应解析失败（不可重试）。"""

    def test_code(self) -> None:
        exc = DataSourceResponseError(message="解析失败")
        assert exc.code == "EXCEPTION_413"
        assert isinstance(exc, DataSourceError)

    def test_missing_fields_context(self) -> None:
        """413 的 missing_fields 经 to_dict 序列化面暴露（code 绑定 + 管线穿透）"""
        exc = DataSourceResponseError(context={"source_name": "uspto", "missing_fields": ["patent_id"]})
        d = exc.to_dict()
        assert d["code"] == "EXCEPTION_413"
        assert d["context"]["missing_fields"] == ["patent_id"]


class TestDataSourceExceptionHTTPMapping:
    """EXCEPTION_HTTP_MAP 映射断言（502/503/429/502）。"""

    def test_base_maps_502(self) -> None:
        assert EXCEPTION_HTTP_MAP[DataSourceError] == status.HTTP_502_BAD_GATEWAY

    def test_unavailable_maps_503(self) -> None:
        assert EXCEPTION_HTTP_MAP[DataSourceUnavailableError] == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_rate_limit_maps_429(self) -> None:
        assert EXCEPTION_HTTP_MAP[DataSourceRateLimitError] == status.HTTP_429_TOO_MANY_REQUESTS

    def test_response_error_maps_502(self) -> None:
        assert EXCEPTION_HTTP_MAP[DataSourceResponseError] == status.HTTP_502_BAD_GATEWAY
