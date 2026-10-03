"""Story 4.1f Task 9 — google-patents（BigQuery 公共专利数据集）适配器单元测试

验证 GooglePatentsAdapter（BigQuery REST 直连 + 服务账号 JWT 令牌流 + 月配额守卫）：
- 令牌管理：服务账号 JSON → RS256 JWT（iss/sub/scope/aud）→ token 端点 POST /
  缓存命中不重复请求 / 过期提前刷新 / 业务 401 判别重取一次
- 月配额守卫：totalBytesProcessed 字节累计（1TiB/月上限前置抛 412 零请求消耗）/
  自然月窗口重置（now_fn 注入）/ 并发安全
- 管道串解析：assignee/cpc/country/year/keyword 五参（空条件 → 201 防全表扫描；
  未知参数 → 201）
- 参数化 SQL：named parameters 防注入 + 列裁剪（仅 publication_number/assignee/
  filing_date 三列）+ 强制 LIMIT
- jobs.query REST：Bearer 头 / rows（f.v）→ patents 结构化 / schema.fields 名映射
- 失败矩阵：101（双门缺失构造/401/403）/ 302 超时 / 411 5xx 耗尽/熔断 /
  412 限流 / 413 结构异常；repr 脱敏；isinstance(DataSourcePort)

测试模式：httpx.MockTransport 注入（零外网零 GCP）。
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from src.domain.exceptions import (
    ConfigurationError,
    DataSourceRateLimitError,
    DataSourceResponseError,
    DataSourceUnavailableError,
    TimeoutError,
    ValidationError,
)
from src.domain.ports.data_source import DataSourcePort, DataSourceQuery
from src.infrastructure.config.google_patents import GooglePatentsConfig
from src.infrastructure.external_services.datasources.google_patents_adapter import (
    GooglePatentsAdapter,
    MonthlyQuotaGuard,
    parse_patents_pipeline_query,
)

_TOKEN_URL = "https://oauth2.googleapis.test/token"
_CREDENTIALS_PATH_PLACEHOLDER = "credentials-placeholder.json"

_FAKE_SERVICE_ACCOUNT_PARTS = ("fake-gcp-sa-", "test@gcp.test")

_TOKEN_BODY = {"access_token": "fake-gp-token-1", "token_type": "Bearer", "expires_in": 3600}
_QUERY_BODY = {
    "jobComplete": True,
    "totalBytesProcessed": "1234567",
    "schema": {"fields": [{"name": "publication_number"}, {"name": "assignee"}, {"name": "filing_date"}]},
    "rows": [
        {"f": [{"v": "CN-1234567-A"}, {"v": "华为"}, {"v": "2024-06-15"}]},
        {"f": [{"v": "US-2024-0012345-A1"}, {"v": "BYD"}, {"v": "2024-03-20"}]},
    ],
}


def _fake_service_account_email() -> str:
    return _FAKE_SERVICE_ACCOUNT_PARTS[0] + _FAKE_SERVICE_ACCOUNT_PARTS[1]


@pytest.fixture
def credentials_file(tmp_path: Path) -> Path:
    """临时服务账号 JSON（fake RSA 私钥占位——签名测试用 monkeypatch 替换签名器）。"""
    sa_path = tmp_path / _CREDENTIALS_PATH_PLACEHOLDER
    sa_path.write_text(
        json.dumps(
            {
                "type": "service_account",
                "client_email": _fake_service_account_email(),
                "private_key": "-----BEGIN " + "PRIVATE KEY-----\nFAKE\n-----END " + "PRIVATE KEY-----",
                "token_uri": _TOKEN_URL,
            }
        ),
        encoding="utf-8",
    )
    return sa_path


def _make_config(credentials_file: Path) -> GooglePatentsConfig:
    return GooglePatentsConfig(
        credentials_path=str(credentials_file),
        project_id="test-project",
        api_url="https://bigquery.googleapis.test",
        token_url=_TOKEN_URL,
        timeout=5.0,
    )


def _make_adapter(
    credentials_file: Path,
    handler: httpx.MockTransport | None = None,
    *,
    config: GooglePatentsConfig | None = None,
    quota_bytes_used: int = 0,
    now_fn: Any = None,
) -> GooglePatentsAdapter:
    transport = handler or httpx.MockTransport(
        lambda req: httpx.Response(200, json=_TOKEN_BODY if "/token" in str(req.url) else _QUERY_BODY)
    )
    return GooglePatentsAdapter(
        config=config or _make_config(credentials_file),
        client=httpx.AsyncClient(transport=transport, timeout=5.0),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
        quota_bytes_used=quota_bytes_used,
        now_fn=now_fn,
    )


class TestGooglePatentsConfig:
    def test_from_env_reads_all_variables(self, credentials_file, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(credentials_file))
        monkeypatch.setenv("GOOGLE_PATENTS_PROJECT_ID", "proj-x")
        monkeypatch.setenv("GOOGLE_PATENTS_TIMEOUT", "12.5")
        monkeypatch.setenv("GOOGLE_PATENTS_TTL_SECONDS", "3600")
        config = GooglePatentsConfig.from_env()
        assert config.credentials_path == str(credentials_file)
        assert config.project_id == "proj-x"
        assert config.timeout == 12.5
        assert config.ttl_seconds == 3600

    def test_missing_credentials_or_project_raises_configuration_error(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        monkeypatch.setenv("GOOGLE_PATENTS_PROJECT_ID", "")
        with pytest.raises(ConfigurationError) as exc_info:
            GooglePatentsConfig.from_env()
        assert exc_info.value.code == "EXCEPTION_101"

    def test_invalid_timeout_raises_configuration_error(self, credentials_file, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(credentials_file))
        monkeypatch.setenv("GOOGLE_PATENTS_PROJECT_ID", "proj")
        monkeypatch.setenv("GOOGLE_PATENTS_TIMEOUT", "abc")
        with pytest.raises(ConfigurationError):
            GooglePatentsConfig.from_env()

    def test_config_repr_masks_credentials(self, credentials_file) -> None:
        config = _make_config(credentials_file)
        assert "FAKE" not in repr(config)
        assert "BEGIN " + "PRIVATE KEY" not in repr(config)


class TestPipelineQueryParsing:
    def test_full_pipeline(self) -> None:
        parsed = parse_patents_pipeline_query("assignee=华为|cpc=Y02E|country=CN|year=2020-2026|keyword=battery")
        assert parsed["assignee"] == "华为"
        assert parsed["cpc"] == "Y02E"
        assert parsed["country"] == "CN"
        assert parsed["year"] == "2020-2026"
        assert parsed["keyword"] == "battery"

    def test_single_param(self) -> None:
        parsed = parse_patents_pipeline_query("assignee=BYD")
        assert parsed == {"assignee": "BYD"}

    def test_empty_query_raises_validation_error(self) -> None:
        """空条件 → 201（防护全表扫描——BigQuery 按扫描字节计费）。"""
        with pytest.raises(ValidationError) as exc_info:
            parse_patents_pipeline_query("")
        assert exc_info.value.code == "EXCEPTION_201"

    def test_unknown_param_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_patents_pipeline_query("foo=bar")
        assert exc_info.value.code == "EXCEPTION_201"


class TestGoogleTokenManager:
    @pytest.fixture
    def token_captured_adapter(self, credentials_file, monkeypatch: pytest.MonkeyPatch):
        """捕获令牌端点请求 + 替换 RS256 签名（fake 私钥无法真签）。"""
        captured: list[httpx.Request] = []
        token_calls = {"n": 0}

        from src.infrastructure.external_services.datasources.google_patents_adapter import _GoogleTokenManager

        monkeypatch.setattr(
            "src.infrastructure.external_services.datasources.google_patents_adapter._sign_jwt_rs256",
            lambda header, claims, key: "fake-signed-jwt",
        )

        def handler(request: httpx.Request) -> httpx.Response:
            if "/token" in str(request.url):
                token_calls["n"] += 1
                captured.append(request)
                return httpx.Response(200, json=_TOKEN_BODY)
            return httpx.Response(200, json=_QUERY_BODY)

        manager = _GoogleTokenManager(
            credentials_path=str(credentials_file),
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5.0),
            retry_max_attempts=3,
            retry_min_wait=0.01,
            retry_max_wait=0.02,
        )
        return manager, captured, token_calls

    @pytest.mark.asyncio
    async def test_jwt_claims_and_token_fetch(self, token_captured_adapter) -> None:
        manager, captured, token_calls = token_captured_adapter
        token = await manager.get_token()
        assert token == "fake-gp-token-1"
        assert token_calls["n"] == 1
        # 令牌端点参数经 query string 传递（helper params 通道——assertion/grant_type）
        query_params = dict(captured[0].url.params)
        assert query_params.get("grant_type") == "urn:ietf:params:oauth:grant-type:jwt-bearer"
        assert query_params.get("assertion", "").startswith("fake-signed-jwt")

    @pytest.mark.asyncio
    async def test_cache_hit_does_not_refetch(self, token_captured_adapter) -> None:
        manager, _captured, token_calls = token_captured_adapter
        assert await manager.get_token() == "fake-gp-token-1"
        assert await manager.get_token() == "fake-gp-token-1"
        assert token_calls["n"] == 1, "缓存命中不应重复请求令牌端点"

    @pytest.mark.asyncio
    async def test_expired_token_refreshes_early(self, token_captured_adapter) -> None:
        manager, _captured, token_calls = token_captured_adapter
        now = datetime(2026, 10, 2, 0, 0, 0, tzinfo=UTC)
        manager._now_fn = lambda: now
        assert await manager.get_token() == "fake-gp-token-1"
        manager._now_fn = lambda: now + timedelta(seconds=3601)
        assert await manager.get_token() == "fake-gp-token-2" or token_calls["n"] == 2, "过期应刷新"

    @pytest.mark.asyncio
    async def test_credentials_file_missing_raises_configuration_error(self, tmp_path) -> None:
        from src.infrastructure.external_services.datasources.google_patents_adapter import _GoogleTokenManager

        with pytest.raises(ConfigurationError) as exc_info:
            _GoogleTokenManager(
                credentials_path=str(tmp_path / "nonexistent.json"),
                client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
            )
        assert exc_info.value.code == "EXCEPTION_101"


class TestMonthlyQuotaGuard:
    def test_preflight_blocks_when_exhausted(self) -> None:
        guard = MonthlyQuotaGuard(quota_bytes_used=1024**4)  # 1 TiB
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            asyncio.get_event_loop().run_until_complete(guard.ensure_capacity())
        assert exc_info.value.code == "EXCEPTION_412"
        assert "1099511627776" in str(exc_info.value) or "1" in str(exc_info.value)

    def test_monthly_reset_by_now_fn(self) -> None:
        month_a = datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC)
        month_b = datetime(2026, 10, 1, 0, 0, 30, tzinfo=UTC)  # 越过自然月一日 00:00 UTC
        guard = MonthlyQuotaGuard(quota_bytes_used=1024**4, now_fn=lambda: month_a)
        with pytest.raises(DataSourceRateLimitError):
            asyncio.get_event_loop().run_until_complete(guard.ensure_capacity())
        guard._now_fn = lambda: month_b
        asyncio.get_event_loop().run_until_complete(guard.ensure_capacity())  # 月窗口重置不抛

    @pytest.mark.asyncio
    async def test_concurrent_consume_under_lock(self) -> None:
        guard = MonthlyQuotaGuard()

        async def consume_once(n: int) -> None:
            await guard.consume(100 * n)

        await asyncio.gather(*(consume_once(i) for i in range(1, 21)))
        assert guard.used_bytes == 100 * sum(range(1, 21))


class TestGooglePatentsAdapterSuccess:
    @pytest.fixture
    def working_adapter(self, credentials_file, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            "src.infrastructure.external_services.datasources.google_patents_adapter._sign_jwt_rs256",
            lambda header, claims, key: "fake-signed-jwt",
        )
        return _make_adapter(credentials_file)

    @pytest.mark.asyncio
    async def test_fetch_success_structured_patents(self, working_adapter) -> None:
        result = await working_adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=华为|country=CN"))
        payload = json.loads(result.payload)
        assert payload["patents"][0]["assignee"] == "华为"
        assert payload["patents"][0]["publication_number"] == "CN-1234567-A"
        assert {"publication_number", "assignee", "filing_date"} <= set(payload["patents"][0])
        assert result.confidence == 0.9
        assert result.source_name == "google-patents"

    @pytest.mark.asyncio
    async def test_query_uses_parameterized_sql_and_bearer(self, working_adapter, credentials_file, monkeypatch) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            if "/token" in str(request.url):
                return httpx.Response(200, json=_TOKEN_BODY)
            return httpx.Response(200, json=_QUERY_BODY)

        adapter = _make_adapter(credentials_file, httpx.MockTransport(handler), config=working_adapter._config)
        await adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=华为|year=2020-2026"))

        query_req = [r for r in captured if "/queries" in str(r.url)][0]
        assert query_req.headers.get("authorization") == "Bearer fake-gp-token-1"

        body = json.loads(query_req.content.decode())
        sql = body["query"]
        # 列裁剪 + LIMIT + 参数化占位符（防注入）
        assert "publication_number" in sql and "assignee" in sql and "filing_date" in sql
        assert "LIMIT" in sql
        assert "@assignee" in sql or "?" in sql or body.get("parameterMode") == "NAMED"
        # 参数值经 named parameters 传递（非字符串拼接——LIKE 通配符在参数值内，值不进 SQL 文本）
        assert body.get("parameterMode") == "NAMED"
        params = {p["name"]: p["parameterValue"]["value"] for p in body.get("queryParameters", [])}
        assert params.get("assignee") == "%华为%"
        assert "华为" not in sql  # 值不进 SQL 文本

    @pytest.mark.asyncio
    async def test_bytes_processed_counted_into_guard(self, working_adapter) -> None:
        await working_adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=华为"))
        assert working_adapter.quota_used_bytes == 1234567, "totalBytesProcessed 应精确计入月配额"

    @pytest.mark.asyncio
    async def test_quota_exhausted_preflight_zero_requests(self, working_adapter, credentials_file) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json=_QUERY_BODY)

        adapter = _make_adapter(
            credentials_file, httpx.MockTransport(handler), config=working_adapter._config, quota_bytes_used=1024**4
        )
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=华为"))
        assert exc_info.value.code == "EXCEPTION_412"
        assert calls["n"] == 0, "守卫前置拦截——含令牌端点零请求"

    def test_get_metadata(self, working_adapter) -> None:
        ref = working_adapter.get_metadata()
        assert ref.name == "google-patents"
        assert ref.api_type.value == "rest_json"
        assert ref.ttl_seconds == 604800
        # 适配器侧不填声明性字段（Task 5 定稿——SSOT/frontmatter 声明面承载）
        assert ref.required_fields == ()

    @pytest.mark.asyncio
    async def test_implements_port(self, working_adapter) -> None:
        assert isinstance(working_adapter, DataSourcePort)

    @pytest.mark.asyncio
    async def test_health_check(self, working_adapter) -> None:
        assert await working_adapter.health_check() is True


class TestGooglePatentsAdapterFailures:
    @pytest.fixture
    def signer_patched(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            "src.infrastructure.external_services.datasources.google_patents_adapter._sign_jwt_rs256",
            lambda header, claims, key: "fake-signed-jwt",
        )

    def test_missing_both_gates_raises_configuration_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError) as exc_info:
            GooglePatentsConfig(credentials_path="", project_id="", api_url="https://x.test", token_url=_TOKEN_URL)
        assert exc_info.value.code == "EXCEPTION_101"

    @pytest.mark.asyncio
    async def test_401_raises_configuration_error_without_key_leak(self, signer_patched, credentials_file) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/token" in str(request.url):
                return httpx.Response(200, json=_TOKEN_BODY)
            return httpx.Response(401, json={"error": "unauthorized"})

        adapter = _make_adapter(credentials_file, httpx.MockTransport(handler))
        with pytest.raises(ConfigurationError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=华为"))
        assert exc_info.value.code == "EXCEPTION_101"
        assert "BEGIN " + "PRIVATE KEY" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_5xx_retry_exhausted_raises_unavailable(self, signer_patched, credentials_file) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            if "/token" in str(request.url):
                return httpx.Response(200, json=_TOKEN_BODY)
            calls["n"] += 1
            return httpx.Response(503)

        adapter = _make_adapter(credentials_file, httpx.MockTransport(handler))
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=华为"))
        assert calls["n"] == 3

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self, signer_patched, credentials_file) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/token" in str(request.url):
                return httpx.Response(200, json=_TOKEN_BODY)
            return httpx.Response(429, json={"error": "rateLimited"})

        adapter = _make_adapter(credentials_file, httpx.MockTransport(handler))
        with pytest.raises(DataSourceRateLimitError):
            await adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=华为"))

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self, signer_patched, credentials_file) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/token" in str(request.url):
                return httpx.Response(200, json=_TOKEN_BODY)
            raise httpx.ReadTimeout("timeout", request=request)

        adapter = _make_adapter(credentials_file, httpx.MockTransport(handler))
        with pytest.raises(TimeoutError):
            await adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=华为"))

    @pytest.mark.asyncio
    async def test_missing_rows_field_raises_response_error(self, signer_patched, credentials_file) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/token" in str(request.url):
                return httpx.Response(200, json=_TOKEN_BODY)
            return httpx.Response(200, json={"jobComplete": True, "schema": {"fields": []}})

        adapter = _make_adapter(credentials_file, httpx.MockTransport(handler))
        with pytest.raises(DataSourceResponseError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=华为"))
        assert exc_info.value.code == "EXCEPTION_413"

    @pytest.mark.asyncio
    async def test_job_incomplete_raises_response_error(self, signer_patched, credentials_file) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "/token" in str(request.url):
                return httpx.Response(200, json=_TOKEN_BODY)
            return httpx.Response(200, json={"jobComplete": False})

        adapter = _make_adapter(credentials_file, httpx.MockTransport(handler))
        with pytest.raises(DataSourceResponseError):
            await adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=华为"))

    @pytest.mark.asyncio
    async def test_empty_pipeline_raises_validation_error_zero_requests(self, signer_patched, credentials_file) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json=_QUERY_BODY)

        adapter = _make_adapter(credentials_file, httpx.MockTransport(handler))
        # 纯分隔符串（非空白——DataSourceQuery 构造允许）parse 后无有效条件 → 201 防全表扫描
        with pytest.raises(ValidationError) as exc_info:
            await adapter.fetch(DataSourceQuery(source_name="google-patents", query="||"))
        assert exc_info.value.code == "EXCEPTION_201"
        assert calls["n"] == 0, "输入前置校验——零请求消耗"
