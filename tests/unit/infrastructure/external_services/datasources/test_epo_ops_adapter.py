"""Story 4.1f — EPO OPS 适配器单元测试

验证 EPO Espacenet OPS 数据源适配器（OAuth2 + CQL 检索 + 周配额守卫）：
- 令牌管理三分支：首次获取（Basic 凭证）/ 缓存命中不重复请求 / 业务 401 失效重取一次
- 令牌端点失败映射：401/403 → 101 / 网络耗尽 → 411（走 resilience helper）
- 周配额守卫：累计超 4GB 前置抛 412（零请求消耗）/ 周窗口重置（now_fn 注入）/ 并发安全
- 适配器主体：CQL 直通 + Bearer + Accept/Range 头 / 结构校验缺 patents → 413 /
  失败矩阵（201/302/411/412/413/熔断）/ 凭据缺失构造 → 101 / repr 脱敏

测试模式：httpx.MockTransport 注入（零外网）。
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from src.domain.exceptions import (
    ConfigurationError,
    DataSourceRateLimitError,
    DataSourceResponseError,
    DataSourceUnavailableError,
    TimeoutError,
)
from src.domain.ports.data_source import DataSourcePort, DataSourceQuery
from src.infrastructure.config.epo_ops import EpoOpsConfig
from src.infrastructure.external_services.datasources.epo_ops_adapter import (
    EpoOpsAdapter,
    _EpoTokenManager,
    _WeeklyQuotaGuard,
)

_API_URL = "https://ops.epo.org"
_FAKE_KEY_PARTS = ("fake-epo-consumer-", "key-test1234")
_FAKE_SECRET_PARTS = ("fake-epo-secret-", "test4567")

_TOKEN_BODY = {"access_token": "fake-epo-token-1", "expires_in": 3600}
_SEARCH_BODY = {"patents": [{"title": "Battery tech", "applicant": "华为", "filing_date": "2026-01-15"}]}


def _fake_credentials() -> tuple[str, str]:
    return _FAKE_KEY_PARTS[0] + _FAKE_KEY_PARTS[1], _FAKE_SECRET_PARTS[0] + _FAKE_SECRET_PARTS[1]


def _make_config() -> EpoOpsConfig:
    key, secret = _fake_credentials()
    return EpoOpsConfig(consumer_key=key, consumer_secret=secret, api_url=_API_URL, timeout=5.0)


def _make_adapter(
    handler: httpx.MockTransport | None = None,
    *,
    config: EpoOpsConfig | None = None,
    quota_bytes_used: int = 0,
    now_fn: Any = None,
    circuit_breaker: Any = None,
) -> EpoOpsAdapter:
    transport = handler or httpx.MockTransport(
        lambda req: httpx.Response(200, json=_TOKEN_BODY if "/auth/accesstoken" in str(req.url) else _SEARCH_BODY)
    )
    return EpoOpsAdapter(
        config=config or _make_config(),
        client=httpx.AsyncClient(base_url=_API_URL, transport=transport, timeout=5.0),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
        quota_bytes_used=quota_bytes_used,
        now_fn=now_fn,
        circuit_breaker=circuit_breaker,
    )


class TestEpoOpsConfig:
    def test_from_env_reads_five_variables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        key, secret = _fake_credentials()
        monkeypatch.setenv("EPO_OPS_CONSUMER_KEY", key)
        monkeypatch.setenv("EPO_OPS_CONSUMER_SECRET", secret)
        monkeypatch.setenv("EPO_OPS_API_URL", "https://ops.example.org")
        monkeypatch.setenv("EPO_OPS_TIMEOUT", "12.5")
        monkeypatch.setenv("EPO_OPS_TTL_SECONDS", "3600")
        config = EpoOpsConfig.from_env()
        assert config.consumer_key == key
        assert config.consumer_secret == secret
        assert config.api_url == "https://ops.example.org"
        assert config.timeout == 12.5
        assert config.ttl_seconds == 3600

    def test_from_env_invalid_timeout_raises_configuration_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EPO_OPS_TIMEOUT", "abc")
        with pytest.raises(ConfigurationError) as exc_info:
            EpoOpsConfig.from_env()
        assert exc_info.value.code == "EXCEPTION_101"

    def test_config_repr_masks_credentials(self) -> None:
        config = _make_config()
        key, secret = _fake_credentials()
        assert key not in repr(config) and key not in str(config)
        assert secret not in repr(config) and secret not in str(config)


class TestEpoTokenManager:
    @staticmethod
    def _make_manager(handler: httpx.MockTransport) -> tuple[_EpoTokenManager, dict[str, int]]:
        client = httpx.AsyncClient(base_url=_API_URL, transport=handler, timeout=5.0)
        from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

        manager = _EpoTokenManager(
            client=client,
            config=_make_config(),
            circuit_breaker=CircuitBreaker(name="data-source-epo-ops-test"),
            retry_max_attempts=3,
            retry_min_wait=0.01,
            retry_max_wait=0.02,
        )
        return manager, {}

    @pytest.mark.asyncio
    async def test_first_fetch_uses_basic_credentials(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=_TOKEN_BODY)

        manager, _ = self._make_manager(httpx.MockTransport(handler))
        token = await manager.get_token()
        assert token == "fake-epo-token-1"
        assert "/3.2/auth/accesstoken" in str(captured[0].url), (
            "令牌端点路径契约锁（官方 Reference Guide v1.3.20——R2-F1，防 /3.2/auth/token 旧路径回归）"
        )
        assert captured[0].headers.get("authorization", "").startswith("Basic "), "令牌请求应携带 Basic 凭证"
        assert "grant_type=client_credentials" in str(captured[0].url)

    @pytest.mark.asyncio
    async def test_cache_hit_does_not_refetch(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json=_TOKEN_BODY)

        manager, _ = self._make_manager(httpx.MockTransport(handler))
        assert await manager.get_token() == "fake-epo-token-1"
        assert await manager.get_token() == "fake-epo-token-1"
        assert calls["n"] == 1, "缓存命中不应重复请求令牌端点"

    @pytest.mark.asyncio
    async def test_expired_token_refreshes_early(self) -> None:
        now = datetime(2026, 9, 30, 0, 0, 0, tzinfo=UTC)
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json={"access_token": f"t{calls['n']}", "expires_in": 60})

        from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

        client = httpx.AsyncClient(base_url=_API_URL, transport=httpx.MockTransport(handler), timeout=5.0)
        manager = _EpoTokenManager(
            client=client,
            config=_make_config(),
            circuit_breaker=CircuitBreaker(name="test"),
            retry_max_attempts=3,
            retry_min_wait=0.01,
            retry_max_wait=0.02,
            now_fn=lambda: now,
        )
        assert await manager.get_token() == "t1"
        now2 = now + timedelta(seconds=61)  # 越过过期提前刷新阈值（提前 60s）
        manager._now_fn = lambda: now2
        assert await manager.get_token() == "t2", "过期前 60s 阈值到达应自动刷新"

    @pytest.mark.asyncio
    async def test_token_endpoint_401_raises_configuration_error(self) -> None:
        manager, _ = self._make_manager(httpx.MockTransport(lambda req: httpx.Response(401, json={"error": "bad"})))
        with pytest.raises(ConfigurationError) as exc_info:
            await manager.get_token()
        assert exc_info.value.code == "EXCEPTION_101"

    @pytest.mark.asyncio
    async def test_token_endpoint_network_exhausted_raises_unavailable(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503)

        manager, _ = self._make_manager(httpx.MockTransport(handler))
        with pytest.raises(DataSourceUnavailableError):
            await manager.get_token()
        assert calls["n"] == 3, "重试耗尽应为 3 次（retry_max_attempts 语义）"


class TestWeeklyQuotaGuard:
    @pytest.mark.asyncio
    async def test_guard_preflight_blocks_when_exhausted(self) -> None:
        guard = _WeeklyQuotaGuard(quota_bytes_used=4 * 1024**3)
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            await guard.ensure_capacity()
        assert exc_info.value.code == "EXCEPTION_412"
        assert "4294967296" in str(exc_info.value) or "已用" in str(exc_info.value), "消息应含已用量"

    @pytest.mark.asyncio
    async def test_guard_weekly_reset_by_now_fn(self) -> None:
        week1 = datetime(2026, 9, 28, 12, 0, 0, tzinfo=UTC)  # 周一
        week2 = datetime(2026, 10, 5, 12, 0, 0, tzinfo=UTC)  # 下周一（越过重置点）
        guard = _WeeklyQuotaGuard(quota_bytes_used=4 * 1024**3, now_fn=lambda: week1)
        with pytest.raises(DataSourceRateLimitError):
            await guard.ensure_capacity()
        guard._now_fn = lambda: week2
        await guard.ensure_capacity()  # 周窗口越过周一 00:00 GMT 应重置（不抛）

    @pytest.mark.asyncio
    async def test_guard_concurrent_consume_under_lock(self) -> None:
        """并发计数精确性的行为回归防线（非锁存在性证明——当前临界区无 await、
        单 loop 下天然串行；未来临界区演化出 await 引入竞争丢失更新时本测试变红）。"""
        guard = _WeeklyQuotaGuard()

        async def consume_once() -> None:
            await guard.consume(100)

        await asyncio.gather(*(consume_once() for _ in range(50)))
        assert guard.used_bytes == 50 * 100, "并发累计应精确（Lock 保护）"


class TestEpoOpsAdapterSuccess:
    @pytest.mark.asyncio
    async def test_fetch_success_with_cql_bearer_accept_range(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json=_TOKEN_BODY if "/auth/accesstoken" in str(request.url) else _SEARCH_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler))
        result = await adapter.fetch(DataSourceQuery(source_name="epo-ops", query='pa="华为" and ti="battery"'))
        search = [r for r in captured if "/auth/accesstoken" not in str(r.url)][0]
        assert "rest-services/published-data/search" in str(search.url), (
            "检索路径须含 rest-services 前缀（官方 Reference Guide v1.3.20——R1-F1 路径契约锁）"
        )
        assert search.headers.get("authorization") == "Bearer fake-epo-token-1"
        assert search.headers.get("accept") == "application/json"
        assert search.headers.get("range") == "1-25", "应携带 Range 分页头（首页 25 条）"
        assert 'pa="华为"' in str(search.url.params.get("q", "")), "CQL 表达式应直通 q 参数（解码形态）"
        payload = json.loads(result.payload)
        assert payload["patents"][0]["applicant"] == "华为"
        assert result.confidence == 0.9
        await adapter.close()

    @pytest.mark.asyncio
    async def test_business_401_refreshes_token_once_and_retries(self) -> None:
        business_calls = {"n": 0}
        token_calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            if "/auth/accesstoken" in str(request.url):
                token_calls["n"] += 1
                return httpx.Response(200, json={"access_token": f"t{token_calls['n']}", "expires_in": 3600})
            business_calls["n"] += 1
            if business_calls["n"] == 1:
                return httpx.Response(401, json={"error": "invalid_token"})
            return httpx.Response(200, json=_SEARCH_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler))
        result = await adapter.fetch(DataSourceQuery(source_name="epo-ops", query='pa="BYD"'))
        assert token_calls["n"] == 2, "业务 401 应强制刷新令牌一次（共两次令牌请求）"
        assert business_calls["n"] == 2, "业务请求应重发一次"
        assert json.loads(result.payload)["patents"], "重试后应返回结果"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_quota_exhausted_preflight_zero_requests(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json=_SEARCH_BODY)

        adapter = _make_adapter(httpx.MockTransport(handler), quota_bytes_used=4 * 1024**3)
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="epo-ops", query='pa="华为"'))
        assert exc_info.value.code == "EXCEPTION_412"
        assert calls["n"] == 0, "守卫前置拦截——含令牌端点在内零请求消耗"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_response_bytes_counted_into_quota(self) -> None:
        adapter = _make_adapter()
        await adapter.fetch(DataSourceQuery(source_name="epo-ops", query='pa="华为"'))
        assert adapter.quota_used_bytes == len(json.dumps(_SEARCH_BODY).encode()), "响应 JSON 序列化字节应计入周配额"
        await adapter.close()

    def test_get_metadata_aligns_ssot_prefix(self) -> None:
        ref = _make_adapter().get_metadata()
        assert ref.name == "epo-ops"
        assert ref.url == _API_URL
        assert ref.api_type.value == "rest_json"
        assert ref.ttl_seconds == 604800
        assert ref.required_fields == (), "适配器侧不填声明性字段（Task 5 定稿——frontmatter↔SSOT 承载）"

    @pytest.mark.asyncio
    async def test_implements_port(self) -> None:
        assert isinstance(_make_adapter(), DataSourcePort)

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        adapter = _make_adapter()
        assert await adapter.health_check() is True
        # 探活响应字节同样入账周配额（探活是真实消耗——R1-F12，防配额旁路）
        assert adapter._quota_guard.used_bytes > 0, "探活成功后配额计数应大于 0"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_circuit_breaker_early_open(self) -> None:
        """熔断差异化配置：注入降阈熔断器（threshold=2），2 次 fetch 失败即断开，断开期间零 HTTP。

        注：熔断计数按"采集会话"记（每次 fetch 重试耗尽后记 1 次失败——helper 终端
        except 单点 on_failure）；令牌端点与业务请求共用同一熔断器，503-always handler
        下失败发生在令牌端点，计数不受影响。断言核心 = 断开期间计数器不增（快速失败）。
        """
        from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503, json={})

        adapter = _make_adapter(
            httpx.MockTransport(handler),
            circuit_breaker=CircuitBreaker(failure_threshold=2, recovery_timeout=30.0, name="epo-ops-cb-test"),
        )
        for _ in range(2):
            with pytest.raises(DataSourceUnavailableError):
                await adapter.fetch(DataSourceQuery(source_name="epo-ops", query='ti="battery"'))
        calls_before = calls["n"]
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="epo-ops", query='ti="battery"'))
        assert calls["n"] == calls_before, "熔断器断开后应零 HTTP 快速失败"
        await adapter.close()


class TestEpoOpsAdapterFailures:
    def test_missing_credentials_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError) as exc_info:
            EpoOpsAdapter(config=EpoOpsConfig(consumer_key="", consumer_secret=""))
        assert exc_info.value.code == "EXCEPTION_101"

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(429, json={"message": "limited"})))
        with pytest.raises(DataSourceRateLimitError):
            await adapter.fetch(DataSourceQuery(source_name="epo-ops", query='pa="x"'))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_5xx_retry_exhausted_raises_unavailable(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503)

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="epo-ops", query='pa="x"'))
        assert calls["n"] == 3
        await adapter.close()

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout", request=request)

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(TimeoutError):
            await adapter.fetch(DataSourceQuery(source_name="epo-ops", query='pa="x"'))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_invalid_json_raises_response_error_no_retry(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return (
                httpx.Response(200, content=b"### not json")
                if "/auth/accesstoken" not in str(request.url)
                else httpx.Response(200, json=_TOKEN_BODY)
            )

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(DataSourceResponseError):
            await adapter.fetch(DataSourceQuery(source_name="epo-ops", query='pa="x"'))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_missing_patents_field_raises_response_error(self) -> None:
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json={"unexpected": 1})))
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="epo-ops", query='pa="x"'))
        assert exc_info.value.code == "EXCEPTION_413"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_error_response_zero_credentials_leak(self) -> None:
        """错误响应零凭据泄漏（R2 修正：pytest.raises 结构——except 空洞形态下行为漂移会静默通过）。"""
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(500)))
        with pytest.raises(DataSourceUnavailableError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="epo-ops", query="x"))
        key, secret = _fake_credentials()
        assert key not in json.dumps(exc_info.value.to_dict()) and key not in str(exc_info.value)
        assert secret not in str(exc_info.value)
        await adapter.close()
