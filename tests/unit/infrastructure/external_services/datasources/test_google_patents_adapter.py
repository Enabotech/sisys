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
from urllib.parse import parse_qs

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
# 真实 REST 形态 fixture（Q1-F1——对齐 patents-public-data schema 与 TableRow 编码）：
# - assignee 为 REPEATED（ARRAY<STRING>）：v 是 [{"v": 元素}, ...] 列表
# - filing_date 为 INTEGER（YYYYMMDD）：v 是 "20240615" 字符串
# - 第二行含 NULL cell（filing_date 为 null——键存在值 null 形态）
_QUERY_BODY = {
    "jobComplete": True,
    "totalBytesProcessed": "1234567",
    "schema": {"fields": [{"name": "publication_number"}, {"name": "assignee"}, {"name": "filing_date"}]},
    "rows": [
        {
            "f": [
                {"v": "CN-1234567-A"},
                {"v": [{"v": "华为"}, {"v": "华为技术有限公司"}]},
                {"v": "20240615"},
            ]
        },
        {"f": [{"v": "US-2024-0012345-A1"}, {"v": [{"v": "BYD"}]}, {"v": None}]},
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
    circuit_breaker: Any = None,
) -> GooglePatentsAdapter:
    transport = handler or httpx.MockTransport(
        lambda req: httpx.Response(200, json=_TOKEN_BODY if "/token" in str(req.url) else _QUERY_BODY)
    )
    return GooglePatentsAdapter(
        config=config or _make_config(credentials_file),
        client=httpx.AsyncClient(transport=transport, timeout=5.0),
        circuit_breaker=circuit_breaker,
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

    def test_invalid_year_forms_raise_validation_error(self) -> None:
        """year 形态前置校验（Q1-F1——非数字/多段/倒序穿透到服务端 400 前拦截）。"""
        for bad in ("abc", "202", "2020-2026-2030", "2026-2020"):
            with pytest.raises(ValidationError) as exc_info:
                parse_patents_pipeline_query(f"year={bad}")
            assert exc_info.value.code == "EXCEPTION_201"

    def test_single_year_form_accepted(self) -> None:
        assert parse_patents_pipeline_query("year=2024") == {"year": "2024"}

    def test_invalid_country_form_raises_validation_error(self) -> None:
        """country 形态前置校验（小写/三位码静默空结果——GoogleSQL 比较大小写敏感）。"""
        for bad in ("cn", "CHN", "C", "C1"):
            with pytest.raises(ValidationError) as exc_info:
                parse_patents_pipeline_query(f"country={bad}")
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
                # token 体按调用序变化（判别力——过期刷新断言可对值断言而非仅计数）
                return httpx.Response(
                    200, json={"access_token": f"fake-gp-token-{token_calls['n']}", "token_type": "Bearer", "expires_in": 3600}
                )
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
        # 令牌端点参数经 form body 传递（RFC 7523 §2.1——application/x-www-form-urlencoded；
        # assertion 为短时效签名凭证禁入 URL query——代理/访问日志泄露面）
        form = parse_qs(captured[0].content.decode())
        assert form["grant_type"] == ["urn:ietf:params:oauth:grant-type:jwt-bearer"]
        assert form["assertion"][0].startswith("fake-signed-jwt")
        assert not dict(captured[0].url.params), "assertion 凭证不得出现在 URL query"

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
        assert await manager.get_token() == "fake-gp-token-2", "过期应刷新（新令牌值——判别力经值断言）"
        assert token_calls["n"] == 2

    @pytest.mark.asyncio
    async def test_credentials_file_missing_raises_configuration_error(self, tmp_path) -> None:
        from src.infrastructure.external_services.datasources.google_patents_adapter import _GoogleTokenManager

        with pytest.raises(ConfigurationError) as exc_info:
            _GoogleTokenManager(
                credentials_path=str(tmp_path / "nonexistent.json"),
                client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
            )
        assert exc_info.value.code == "EXCEPTION_101"

    @pytest.mark.asyncio
    async def test_malformed_credentials_json_raises_configuration_error(self, tmp_path) -> None:
        """凭据文件非合法 JSON → 101（Q1-F3——JSONDecodeError 禁裸逃逸异常体系）。"""
        from src.infrastructure.external_services.datasources.google_patents_adapter import _GoogleTokenManager

        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(ConfigurationError) as exc_info:
            _GoogleTokenManager(
                credentials_path=str(bad),
                client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
            )
        assert exc_info.value.code == "EXCEPTION_101"

    @pytest.mark.asyncio
    async def test_nondict_credentials_top_level_raises_configuration_error(self, tmp_path) -> None:
        """凭据 JSON 顶层非对象 → 101（Q1-F3——AttributeError 禁裸逃逸）。"""
        from src.infrastructure.external_services.datasources.google_patents_adapter import _GoogleTokenManager

        bad = tmp_path / "list.json"
        bad.write_text('["not", "an", "object"]', encoding="utf-8")
        with pytest.raises(ConfigurationError) as exc_info:
            _GoogleTokenManager(
                credentials_path=str(bad),
                client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
            )
        assert exc_info.value.code == "EXCEPTION_101"

    @pytest.mark.asyncio
    async def test_invalid_private_key_raises_configuration_error(self, credentials_file) -> None:
        """私钥无效（fake PEM 触发 InvalidKeyError）→ 101（Q1-F3——PyJWTError 禁裸逃逸）。

        不 monkeypatch 签名器——让真实 jwt.encode 收 fake 私钥触发异常路径。
        """
        from src.infrastructure.external_services.datasources.google_patents_adapter import _GoogleTokenManager

        manager = _GoogleTokenManager(
            credentials_path=str(credentials_file),
            client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))),
        )
        with pytest.raises(ConfigurationError) as exc_info:
            await manager.get_token()
        assert exc_info.value.code == "EXCEPTION_101"
        assert "BEGIN " + "PRIVATE KEY" not in str(exc_info.value)


class TestMonthlyQuotaGuard:
    @pytest.mark.asyncio
    async def test_preflight_blocks_when_exhausted(self) -> None:
        guard = MonthlyQuotaGuard(quota_bytes_used=1024**4)  # 1 TiB
        with pytest.raises(DataSourceRateLimitError) as exc_info:
            await guard.ensure_capacity()
        assert exc_info.value.code == "EXCEPTION_412"
        assert "1099511627776" in str(exc_info.value), "消息须含配额上限数值"

    @pytest.mark.asyncio
    async def test_monthly_reset_by_now_fn(self) -> None:
        month_a = datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC)
        month_b = datetime(2026, 10, 1, 0, 0, 30, tzinfo=UTC)  # 越过自然月一日 00:00 UTC
        guard = MonthlyQuotaGuard(quota_bytes_used=1024**4, now_fn=lambda: month_a)
        with pytest.raises(DataSourceRateLimitError):
            await guard.ensure_capacity()
        guard._now_fn = lambda: month_b
        await guard.ensure_capacity()  # 月窗口重置不抛
        assert guard.used_bytes == 0, "越过自然月边界后已用字节应归零"

    @pytest.mark.asyncio
    async def test_concurrent_consume_under_lock(self) -> None:
        """并发 consume 行为回归防线（非锁存在性证明——临界区纯同步、单 loop 下天然
        串行，删 Lock 亦绿；对齐 EPO 并发测试 docstring 降格口径）。"""
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
        # REPEATED 列归一：v 列表逐元素解包 join（Q1-F1——禁 dict 字面量污染 payload）
        assert payload["patents"][0]["assignee"] == "华为；华为技术有限公司"
        assert payload["patents"][0]["publication_number"] == "CN-1234567-A"
        # filing_date YYYYMMDD → ISO 归一（与 EPO 契约形态一致）
        assert payload["patents"][0]["filing_date"] == "2024-06-15"
        # NULL cell 归一空串（键存在值 null——dict.get 缺省不生效形态）
        assert payload["patents"][1]["filing_date"] == ""
        assert payload["patents"][1]["assignee"] == "BYD"
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
        await adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=华为|country=CN|year=2020-2026"))

        query_req = [r for r in captured if "/queries" in str(r.url)][0]
        assert query_req.headers.get("authorization") == "Bearer fake-gp-token-1"

        body = json.loads(query_req.content.decode())
        sql = body["query"]
        # SQL 形态锁（schema 事实——Q1-F1 防回归）：
        assert "UNNEST(assignee)" in sql and "LIKE @assignee" in sql, "REPEATED 列须 UNNEST 逐元素匹配"
        assert "ESCAPE" in sql, "LIKE 通配符转义须有 ESCAPE 子句成对"
        assert "DATE(" not in sql, "filing_date 为 INT64——禁 DATE 函数比较（类型不匹配 400）"
        # 列裁剪 + LIMIT + 参数化占位符（防注入）
        assert "publication_number" in sql and "assignee" in sql and "filing_date" in sql
        assert "LIMIT" in sql
        assert body.get("parameterMode") == "NAMED"
        # timeoutMs 从 config.timeout 派生（两层超时约束——httpx 5s → 服务端 3000ms）
        assert body.get("timeoutMs") == 3000
        params = {p["name"]: p["parameterValue"]["value"] for p in body.get("queryParameters", [])}
        # 参数值经 named parameters 传递（非字符串拼接——LIKE 通配符在参数值内，值不进 SQL 文本）
        assert params.get("assignee") == "%华为%"
        # country 参数无 % 通配符（STARTS_WITH 字面前缀语义——带 % 恒空结果）
        assert params.get("country_code") == "CN"
        # year 整数闭区间边界（含首末日——filing_date 为 YYYYMMDD 整数）
        assert params.get("year_start") == "20200101"
        assert params.get("year_end") == "20261231"
        assert "华为" not in sql  # 值不进 SQL 文本

    @pytest.mark.asyncio
    async def test_like_wildcard_in_user_value_is_escaped(self, working_adapter, credentials_file, monkeypatch) -> None:
        """LIKE 通配符转义（Q1-F1——用户值含 %/_ 时禁意外全匹配）。"""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            if "/token" in str(request.url):
                return httpx.Response(200, json=_TOKEN_BODY)
            return httpx.Response(200, json=_QUERY_BODY)

        adapter = _make_adapter(credentials_file, httpx.MockTransport(handler), config=working_adapter._config)
        await adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=%OR_1=1--"))

        query_req = [r for r in captured if "/queries" in str(r.url)][0]
        body = json.loads(query_req.content.decode())
        params = {p["name"]: p["parameterValue"]["value"] for p in body.get("queryParameters", [])}
        # 注入/通配 payload 原样留在参数值内（%/_ 已转义），不进 SQL 文本
        assert params.get("assignee") == "%\\%OR\\_1=1--%"
        assert "1=1" not in body["query"]

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

    @pytest.mark.asyncio
    async def test_health_check_consumes_quota_and_limits_scan(self, working_adapter, credentials_file) -> None:
        """探活扫描字节入账（Q1-F2——R1-F12 对齐）+ LIMIT 1 收窄断言（防 _SQL_ORDER
        改写致 replace 静默失效）。"""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            if "/token" in str(request.url):
                return httpx.Response(200, json=_TOKEN_BODY)
            return httpx.Response(200, json=_QUERY_BODY)

        adapter = _make_adapter(credentials_file, httpx.MockTransport(handler), config=working_adapter._config)
        assert await adapter.health_check() is True
        assert adapter.quota_used_bytes == 1234567, "探活查询的 totalBytesProcessed 应计入月配额"
        probe_req = [r for r in captured if "/queries" in str(r.url)][0]
        body = json.loads(probe_req.content.decode())
        assert "LIMIT 1" in body["query"], "探活查询应收窄到 LIMIT 1"
        assert body.get("maxResults") == 1


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
    async def test_business_401_refreshes_token_once_and_retries(self, signer_patched, credentials_file) -> None:
        """业务 401 判别重取一次（Q1-F6——双计数器钉死路径，删 401 分支必红）。"""
        business_calls = {"n": 0}
        token_calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            if "/token" in str(request.url):
                token_calls["n"] += 1
                return httpx.Response(
                    200, json={"access_token": f"t{token_calls['n']}", "token_type": "Bearer", "expires_in": 3600}
                )
            business_calls["n"] += 1
            if business_calls["n"] == 1:
                return httpx.Response(401, json={"error": "invalid_token"})
            return httpx.Response(200, json=_QUERY_BODY)

        adapter = _make_adapter(credentials_file, httpx.MockTransport(handler))
        result = await adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=华为"))
        assert token_calls["n"] == 2, "业务 401 应强制刷新令牌一次（首取 + 刷新共两次）"
        assert business_calls["n"] == 2, "业务请求应重发一次"
        assert json.loads(result.payload)["patents"], "重试后应返回结果"

    @pytest.mark.asyncio
    async def test_circuit_breaker_early_open(self, signer_patched, credentials_file) -> None:
        """熔断差异化配置（Q1-F6——对齐 EPO 范本）：注入降阈熔断器（threshold=2），
        2 次 fetch 失败即断开，断开期间零 HTTP。

        注：熔断计数按"采集会话"记（每次 fetch 重试耗尽后记 1 次失败——helper 终端
        except 单点 on_failure）；令牌端点与业务请求共用同一熔断器，503-always
        handler 下失败发生在令牌端点，计数不受影响。断言核心 = 断开期间计数器不增。
        """
        from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503, json={})

        adapter = _make_adapter(
            credentials_file,
            httpx.MockTransport(handler),
            circuit_breaker=CircuitBreaker(failure_threshold=2, recovery_timeout=30.0, name="gp-cb-test"),
        )
        for _ in range(2):
            with pytest.raises(DataSourceUnavailableError):
                await adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=华为"))
        calls_before = calls["n"]
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(DataSourceQuery(source_name="google-patents", query="assignee=华为"))
        assert calls["n"] == calls_before, "熔断器断开后应零 HTTP 快速失败"

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
