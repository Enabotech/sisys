"""Acceptance tests for Story 4.1f - Data Source Expansion.

Real adapter instance acceptance tests using MockTransport injection.
Mock is limited to the HTTP transport layer - the real production
mapping chain (resilience helper, circuit breaker, domain exceptions,
quota guards, token management) is fully exercised.

Covers:
    - AC-1: CJK adaptive params for tavily/newsapi (country/language injection)
    - AC-2: EPO OPS adapter (OAuth2 token flow + weekly quota guard + CQL search)
    - AC-3: SEC EDGAR adapter (official UA + dual-mode dispatch)
    - AC-4: UN Comtrade adapter (optional key + pipeline query + daily quota guard)

Run with: poetry run pytest tests/acceptance/test_acceptance_data_source_expansion.py -v

Prerequisites:
    - No external service required (MockTransport at HTTP transport layer)
    - Real-endpoint integration coverage lives in
      tests/integration/external_services/data_sources/test_new_sources_integration.py
      (EPO key-gated dynamic skip)

Test approach:
    - Scenario-scoped context fixture (dict container) shared across steps
    - BDD steps use event_loop.run_until_complete (no @pytest.mark.asyncio)
    - Fake keys are constant-concatenated (detect-secrets zero false positive)
    - Conditional-registration probe runs in a clean subprocess
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from pytest_bdd import given, parsers, scenario, then, when

from src.domain.exceptions import DataSourceRateLimitError, ValidationError
from src.domain.ports.data_source import DataSourcePort, DataSourceQuery
from src.infrastructure.config.comtrade import ComtradeConfig
from src.infrastructure.config.epo_ops import EpoOpsConfig
from src.infrastructure.config.newsapi import NewsAPIConfig
from src.infrastructure.config.sec_edgar import SecEdgarConfig
from src.infrastructure.config.tavily import TavilyConfig
from src.infrastructure.external_services.datasources.comtrade_adapter import ComtradeAdapter
from src.infrastructure.external_services.datasources.epo_ops_adapter import EpoOpsAdapter
from src.infrastructure.external_services.datasources.newsapi_adapter import NewsAPIAdapter
from src.infrastructure.external_services.datasources.sec_edgar_adapter import SecEdgarAdapter
from src.infrastructure.external_services.datasources.tavily_adapter import TavilyAdapter

# All scenarios join the data-source-cache group: the conditional-registration
# probe (subprocess bootstrap) must run serially with 4.1b probe scenarios on
# the same worker (same rationale as test_acceptance_data_source.py)
pytestmark = pytest.mark.xdist_group("data-source-cache")

# ===================================================================
# Paths & Constants
# ===================================================================

ROOT = Path(__file__).resolve().parents[2]

_TAVILY_BASE_URL = "https://api.tavily.test"
_NEWSAPI_BASE_URL = "https://newsapi.test"
_EPO_API_URL = "https://ops.epo.org"
_EDGAR_EFTS_URL = "https://efts.sec.gov"
_COMTRADE_API_URL = "https://comtradeapi.un.org"

# Fake keys via constant concatenation (detect-secrets KeywordDetector
# intercepts literal assignment forms - same mitigation as Story 4.1b)
_FAKE_TAVILY_KEY_PARTS = ("fake-tavily-", "key-test1234")
_FAKE_NEWSAPI_KEY_PARTS = ("fake-newsapi-", "key-test1234")
_FAKE_EPO_CREDENTIAL_PARTS = ("fake-epo-consumer-", "key-test1234")
_FAKE_COMTRADE_KEY_PARTS = ("fake-comtrade-", "key-test1234")

_EPO_TOKEN_BODY = {"access_token": "fake-epo-token-1", "expires_in": 3600}
_EPO_SEARCH_BODY = {"patents": [{"title": "Battery tech", "applicant": "华为", "filing_date": "2026-01-15"}]}
_EDGAR_FILINGS_BODY = {"filings": [{"company": "Tesla", "cik": "1318605", "form": "10-K", "filed_at": "2026-01-30"}]}
_EDGAR_XBRL_BODY = {"concept": "Revenues", "unit": "USD", "values": [{"end": "2024-12-31", "val": 97690}]}
_COMTRADE_RECORDS_BODY = {"records": [{"cmd_code": "8703", "trade_value": 1234567, "period": "2024"}]}

# Conditional-registration probe: scrub every keyed data-source env var
# (existing keyed sources + 4.1f EPO dual credentials + Comtrade optional key)
_PROBE_SCRUB_KEYS = (
    "TAVILY_API_KEY",
    "NEWSAPI_API_KEY",
    "USPTO_API_KEY",
    "EPO_OPS_CONSUMER_KEY",
    "EPO_OPS_CONSUMER_SECRET",
    "COMTRADE_API_KEY",
)


def _fake_tavily_key() -> str:
    """Concatenated fake Tavily key (detect-secrets safe)."""
    return _FAKE_TAVILY_KEY_PARTS[0] + _FAKE_TAVILY_KEY_PARTS[1]


def _fake_newsapi_key() -> str:
    """Concatenated fake NewsAPI key (detect-secrets safe)."""
    return _FAKE_NEWSAPI_KEY_PARTS[0] + _FAKE_NEWSAPI_KEY_PARTS[1]


def _fake_epo_credential() -> str:
    """Concatenated fake EPO OAuth2 credential (detect-secrets safe)."""
    return _FAKE_EPO_CREDENTIAL_PARTS[0] + _FAKE_EPO_CREDENTIAL_PARTS[1]


def _fake_comtrade_key() -> str:
    """Concatenated fake Comtrade subscription key (detect-secrets safe)."""
    return _FAKE_COMTRADE_KEY_PARTS[0] + _FAKE_COMTRADE_KEY_PARTS[1]


def _capture_client(
    base_url: str,
    respond: Callable[[httpx.Request], httpx.Response],
) -> tuple[httpx.AsyncClient, list[httpx.Request]]:
    """Build an httpx client with a capturing MockTransport.

    Returns the client and the captured-request list (appended per request).
    """
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond(request)

    client = httpx.AsyncClient(base_url=base_url, transport=httpx.MockTransport(handler), timeout=5.0)
    return client, captured


def _epo_respond(
    token_calls: dict[str, int],
    request_count: dict[str, int],
    expire_first: bool,
) -> Callable[[httpx.Request], httpx.Response]:
    """Build the EPO dual-endpoint responder (token endpoint + search endpoint).

    expire_first=True replays the business-401 scenario: the first search
    request returns 401 (expired token), forcing one token refresh + retry.
    """

    def respond(request: httpx.Request) -> httpx.Response:
        if "/auth/accesstoken" in str(request.url):
            token_calls["n"] += 1
            return httpx.Response(200, json={"access_token": f"fake-token-{token_calls['n']}", "expires_in": 3600})
        request_count["n"] += 1
        if expire_first and request_count["n"] == 1:
            return httpx.Response(401, json={"error": "invalid_token"})
        return httpx.Response(200, json=_EPO_SEARCH_BODY)

    return respond


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def ds_context(event_loop: Any) -> dict[str, Any]:
    """Scenario-scoped context container shared across BDD steps.

    Slots: adapter (DataSourcePort), captured (request list), token_calls /
    request_count (endpoint counters), result (DataSourceResult),
    query_error (exception raised during fetch).
    """
    return {
        "_loop": event_loop,
        "adapter": None,
        "captured": [],
        "token_calls": {"n": 0},
        "request_count": {"n": 0},
        "result": None,
        "query_error": None,
    }


def _fetch(ds_context: dict[str, Any], source_name: str, query: str) -> None:
    """Run one fetch on the current adapter; exception goes to query_error."""
    adapter = ds_context["adapter"]
    assert adapter is not None, "adapter must be constructed by a Given step"
    try:
        ds_context["result"] = ds_context["_loop"].run_until_complete(
            adapter.fetch(DataSourceQuery(source_name=source_name, query=query))
        )
    except Exception as exc:  # BDD steps capture all exceptions for Then typing
        ds_context["query_error"] = exc


# ===================================================================
# Background Steps
# ===================================================================


@given("数据源扩展验收环境已初始化")
def data_source_expansion_env_ready(ds_context: dict[str, Any]):
    """Background step: reset scenario state slots."""
    ds_context["adapter"] = None
    ds_context["captured"] = []
    ds_context["token_calls"] = {"n": 0}
    ds_context["request_count"] = {"n": 0}
    ds_context["result"] = None
    ds_context["query_error"] = None


# ===================================================================
# AC-1: CJK Adaptive Params (tavily/newsapi)
# ===================================================================


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "tavily 中文检索自动注入国家参数",
)
def test_tavily_cjk_query_injects_country(ds_context: dict[str, Any]):
    """Test tavily CJK query auto-injects country=china."""
    pass


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "tavily 英文检索请求体零变化",
)
def test_tavily_non_cjk_query_body_unchanged(ds_context: dict[str, Any]):
    """Test tavily non-CJK query keeps the request body unchanged."""
    pass


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "newsapi 中文检索自动注入语言参数",
)
def test_newsapi_cjk_query_injects_language(ds_context: dict[str, Any]):
    """Test newsapi CJK query auto-injects language=zh."""
    pass


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "newsapi 英文检索请求参数零变化",
)
def test_newsapi_non_cjk_query_params_unchanged(ds_context: dict[str, Any]):
    """Test newsapi non-CJK query keeps request params unchanged."""
    pass


@given("tavily 适配器已构造并注入捕获传输层")
def tavily_adapter_with_capture(ds_context: dict[str, Any]):
    """Construct a real TavilyAdapter with a capturing MockTransport."""
    client, captured = _capture_client(
        _TAVILY_BASE_URL,
        lambda request: httpx.Response(200, json={"results": [{"title": "AI 趋势", "url": "https://x.test"}]}),
    )
    ds_context["captured"] = captured
    ds_context["adapter"] = TavilyAdapter(
        config=TavilyConfig(api_key=_fake_tavily_key(), api_url=_TAVILY_BASE_URL, timeout=5.0),
        client=client,
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


@given("newsapi 适配器已构造并注入捕获传输层")
def newsapi_adapter_with_capture(ds_context: dict[str, Any]):
    """Construct a real NewsAPIAdapter with a capturing MockTransport."""
    client, captured = _capture_client(
        _NEWSAPI_BASE_URL,
        lambda request: httpx.Response(200, json={"articles": [{"title": "t", "publishedAt": "2026-01-01"}]}),
    )
    ds_context["captured"] = captured
    ds_context["adapter"] = NewsAPIAdapter(
        config=NewsAPIConfig(api_key=_fake_newsapi_key(), api_url=_NEWSAPI_BASE_URL, timeout=5.0),
        client=client,
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


@when(parsers.parse('以中文关键词 "{keywords}" 执行数据采集'))
@when(parsers.parse('以英文关键词 "{keywords}" 执行数据采集'))
def fetch_with_keywords(ds_context: dict[str, Any], keywords: str):
    """Run one fetch on the current adapter with the given keywords."""
    adapter: DataSourcePort = ds_context["adapter"]
    _fetch(ds_context, adapter.get_metadata().name, keywords)


@then('请求体自动包含国家参数 "china"')
def verify_tavily_country_china(ds_context: dict[str, Any]):
    """Verify the tavily request body carries country=china (official enum)."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    body = json.loads(ds_context["captured"][0].content.decode())
    assert body.get("country") == "china", f"country=china expected, got keys: {sorted(body)}"


@then("请求体与既有形态逐键一致")
def verify_tavily_body_unchanged(ds_context: dict[str, Any]):
    """Verify the non-CJK request body keeps the legacy key set (regression baseline)."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    body = json.loads(ds_context["captured"][0].content.decode())
    assert set(body) == {"api_key", "query", "max_results"}, f"non-CJK body must stay unchanged: {sorted(body)}"


@then("请求体不含国家参数")
def verify_tavily_no_country(ds_context: dict[str, Any]):
    """Verify the non-CJK request body has no country key."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    body = json.loads(ds_context["captured"][0].content.decode())
    assert "country" not in body


@then('请求参数自动包含语言参数 "zh"')
def verify_newsapi_language_zh(ds_context: dict[str, Any]):
    """Verify the newsapi request params carry language=zh (ISO 639-1)."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    params = dict(ds_context["captured"][0].url.params)
    assert params.get("language") == "zh", f"language=zh expected, got params: {sorted(params)}"


@then("请求参数与既有形态逐键一致")
def verify_newsapi_params_unchanged(ds_context: dict[str, Any]):
    """Verify the non-CJK request params keep the legacy key set (regression baseline)."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    params = dict(ds_context["captured"][0].url.params)
    assert set(params) == {"q", "pageSize", "sortBy"}, f"non-CJK params must stay unchanged: {sorted(params)}"


@then("请求参数不含语言参数")
def verify_newsapi_no_language(ds_context: dict[str, Any]):
    """Verify the non-CJK request params have no language key."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    params = dict(ds_context["captured"][0].url.params)
    assert "language" not in params


# ===================================================================
# AC-2: EPO OPS Adapter (OAuth2 token flow + weekly quota guard)
# ===================================================================


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "EPO OAuth2 令牌自动获取并检索专利",
)
def test_epo_token_flow_and_search(ds_context: dict[str, Any]):
    """Test EPO OAuth2 token auto-fetch and CQL search."""
    pass


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "EPO 令牌缓存命中不重复请求",
)
def test_epo_token_cache_hit(ds_context: dict[str, Any]):
    """Test EPO token cache hit avoids duplicate token requests."""
    pass


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "EPO 业务请求 401 令牌失效重取一次",
)
def test_epo_401_refresh_once(ds_context: dict[str, Any]):
    """Test EPO business 401 forces exactly one token refresh + retry."""
    pass


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "EPO 周配额超限前置拦截",
)
def test_epo_weekly_quota_preflight(ds_context: dict[str, Any]):
    """Test EPO weekly quota guard preflight raises 412 with zero requests."""
    pass


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "EPO 凭据缺失时条件注册跳过",
)
def test_epo_conditional_registration_probe(ds_context: dict[str, Any]):
    """Test EPO dual-credential gate skips registration when credentials missing."""
    pass


def _build_epo_adapter(ds_context: dict[str, Any], expire_first: bool, quota_bytes_used: int = 0) -> None:
    """Construct a real EpoOpsAdapter with the EPO dual-endpoint responder."""
    respond = _epo_respond(ds_context["token_calls"], ds_context["request_count"], expire_first)
    client, captured = _capture_client(_EPO_API_URL, respond)
    ds_context["captured"] = captured
    ds_context["adapter"] = EpoOpsAdapter(
        config=EpoOpsConfig(
            consumer_key=_fake_epo_credential(),
            consumer_secret=_fake_epo_credential(),
            api_url=_EPO_API_URL,
            timeout=5.0,
        ),
        quota_bytes_used=quota_bytes_used,
        client=client,
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


@given("EPO OPS 适配器已构造并注入令牌与检索应答传输层")
def epo_adapter_with_token_flow(ds_context: dict[str, Any]):
    """Construct an EpoOpsAdapter with token + search dual-endpoint transport."""
    _build_epo_adapter(ds_context, expire_first=False)


@given("EPO OPS 适配器已构造并注入首令牌过期传输层")
def epo_adapter_with_expired_token(ds_context: dict[str, Any]):
    """Construct an EpoOpsAdapter replaying the business-401 expired-token scenario."""
    _build_epo_adapter(ds_context, expire_first=True)


@given("EPO OPS 适配器已构造并注入已耗尽周配额计数")
def epo_adapter_with_exhausted_quota(ds_context: dict[str, Any]):
    """Construct an EpoOpsAdapter with a pre-exhausted weekly quota counter.

    经 _build_epo_adapter 单一构造路径（captured 真实接线——零请求断言依赖，R1-F3）；
    守卫在 fetch 前置拦截，handler 永不被调用。
    """
    _build_epo_adapter(ds_context, expire_first=False, quota_bytes_used=4 * 1024**3)


@given("子进程环境已清理全部数据源凭据")
def subprocess_env_scrubbed(ds_context: dict[str, Any]):
    """Mark the probe branch: scrub every keyed data-source env var."""
    ds_context["_probe_scrub_keys"] = _PROBE_SCRUB_KEYS


@when(parsers.parse('以 CQL 检索式 "{cql}" 执行数据采集'))
def fetch_epo_with_cql(ds_context: dict[str, Any], cql: str):
    """Run one EPO CQL fetch."""
    _fetch(ds_context, "epo-ops", cql)


@when("连续执行两次 CQL 检索")
def fetch_epo_twice(ds_context: dict[str, Any]):
    """Run two consecutive EPO fetches (second should hit the token cache)."""
    _fetch(ds_context, "epo-ops", 'pa="华为"')
    assert ds_context["query_error"] is None, f"first fetch failed: {ds_context['query_error']}"
    _fetch(ds_context, "epo-ops", 'pa="BYD"')


@when("执行组合根引导并检查端口注册态")
def bootstrap_and_check_registration(ds_context: dict[str, Any]):
    """Run bootstrap in a clean subprocess and assert registration states.

    Half-credential branch (set before the single bootstrap - bootstrap is
    not idempotent): EPO dual gate closed under conjunction semantics
    (consumer key present, secret empty - bool() rejects empty strings);
    EDGAR/Comtrade register unconditionally.
    """

    fake_epo_credential = _fake_epo_credential()
    scrub_lines = "".join(f"os.environ.pop('{key}', None);" for key in ds_context["_probe_scrub_keys"])
    script = (
        "import os; "
        f"{scrub_lines}"
        f"os.environ['EPO_OPS_CONSUMER_KEY'] = '{fake_epo_credential}'; "
        "os.environ['EPO_OPS_CONSUMER_SECRET'] = ''; "
        "from src.composition_root import bootstrap; "
        "from src.domain.ports.registry import _global_registry; "
        "bootstrap(); "
        "assert _global_registry.get('data_source_epo_ops') is None, 'EPO must stay unregistered with half credentials'; "
        "assert _global_registry.get('data_source_sec_edgar') is not None, 'EDGAR must register unconditionally'; "
        "assert _global_registry.get('data_source_comtrade') is not None, 'Comtrade must register unconditionally'; "
        "print('PROBE_OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=ROOT,
    )
    assert result.returncode == 0, f"registration probe failed:\n{result.stdout}\n{result.stderr}"
    ds_context["probe_verified"] = True


@then("OAuth2 令牌经 Basic 凭证自动获取")
def verify_epo_basic_token(ds_context: dict[str, Any]):
    """Verify the token endpoint was called with Basic credentials."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    token_requests = [r for r in ds_context["captured"] if "/auth/accesstoken" in str(r.url)]
    assert token_requests, "token endpoint request expected"
    assert token_requests[0].headers.get("authorization", "").startswith("Basic "), "Basic credentials expected"


@then("业务请求携带 Bearer 令牌")
def verify_epo_bearer(ds_context: dict[str, Any]):
    """Verify the business search request carries the Bearer token."""
    business = [r for r in ds_context["captured"] if "/auth/accesstoken" not in str(r.url)]
    assert business, "business search request expected"
    assert business[-1].headers.get("authorization", "").startswith("Bearer "), "Bearer token expected"


@then("结果结构化为专利列表")
def verify_epo_patents_structured(ds_context: dict[str, Any]):
    """Verify the payload is a structured patents list."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    payload = json.loads(ds_context["result"].payload)
    assert isinstance(payload.get("patents"), list) and payload["patents"], "non-empty patents expected"
    assert {"title", "applicant", "filing_date"} <= set(payload["patents"][0])


@then("令牌端点仅被请求一次")
def verify_epo_token_cached(ds_context: dict[str, Any]):
    """Verify the token endpoint was requested exactly once (cache hit)."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    assert ds_context["token_calls"]["n"] == 1, f"token cache hit expects 1 call, got {ds_context['token_calls']['n']}"


@then("令牌自动刷新一次并重发业务请求")
def verify_epo_refresh_once(ds_context: dict[str, Any]):
    """Verify exactly one token refresh and one business retry (101-typing path)."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    assert ds_context["token_calls"]["n"] == 2, f"one refresh expected (2 total), got {ds_context['token_calls']['n']}"
    assert ds_context["request_count"]["n"] == 2, f"one retry expected (2 total), got {ds_context['request_count']['n']}"


@then("重试后检索成功")
def verify_epo_retry_success(ds_context: dict[str, Any]):
    """Verify the retried fetch returned a result."""
    assert ds_context["result"] is not None, "retry should return a result"


@then("前置拦截抛出限流异常")
def verify_rate_limit_raised(ds_context: dict[str, Any]):
    """Verify the quota guard raised DataSourceRateLimitError."""
    assert isinstance(ds_context["query_error"], DataSourceRateLimitError), (
        f"DataSourceRateLimitError expected, got {type(ds_context['query_error']).__name__}"
    )


@then("限流异常编码为 EXCEPTION_412")
def verify_rate_limit_code(ds_context: dict[str, Any]):
    """Verify the rate-limit error code is EXCEPTION_412."""
    assert ds_context["query_error"].code == "EXCEPTION_412"


@then("上游零请求消耗")
def verify_zero_upstream_requests(ds_context: dict[str, Any]):
    """Verify zero upstream requests (token endpoint included) after guard interception.

    断言基于 captured 请求列表（MockTransport 传输层真接线——R1-F3：此前读未接线的
    计数器导致 4 场景恒真，守卫旁路不会被发现）。
    """
    assert not ds_context["captured"], f"guard interception expects zero requests, captured {len(ds_context['captured'])}"


@then("EPO 端口未注册")
def verify_epo_port_unregistered(ds_context: dict[str, Any]):
    """Verify the EPO port stayed unregistered in the subprocess probe."""
    assert ds_context.get("probe_verified") is True


@then("EDGAR 与 Comtrade 端口无条件注册")
def verify_edgar_comtrade_registered(ds_context: dict[str, Any]):
    """Verify EDGAR/Comtrade ports registered unconditionally in the probe."""
    assert ds_context.get("probe_verified") is True


# ===================================================================
# AC-3: SEC EDGAR Adapter (official UA + dual-mode dispatch)
# ===================================================================


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "EDGAR 免 key 检索返回财报列表",
)
def test_edgar_search_mode_filings(ds_context: dict[str, Any]):
    """Test EDGAR keyless search mode returns a structured filings list."""
    pass


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "EDGAR XBRL 前缀分派返回指标时序",
)
def test_edgar_xbrl_dispatch(ds_context: dict[str, Any]):
    """Test EDGAR xbrl: prefix dispatches to the XBRL data endpoint."""
    pass


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "EDGAR 非法前缀前置校验拒绝",
)
def test_edgar_invalid_prefix_rejected(ds_context: dict[str, Any]):
    """Test EDGAR unknown mode prefix raises ValidationError with zero requests."""
    pass


def _build_edgar_adapter(ds_context: dict[str, Any], body: dict[str, Any]) -> None:
    """Construct a real SecEdgarAdapter with a capturing MockTransport."""
    client, captured = _capture_client(_EDGAR_EFTS_URL, lambda request: httpx.Response(200, json=body))
    ds_context["captured"] = captured
    ds_context["adapter"] = SecEdgarAdapter(
        config=SecEdgarConfig(api_url=_EDGAR_EFTS_URL, timeout=5.0),
        client=client,
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


@given("SEC EDGAR 适配器已构造并注入财报检索应答传输层")
def edgar_adapter_with_filings(ds_context: dict[str, Any]):
    """Construct a SecEdgarAdapter with a search-mode filings responder."""
    _build_edgar_adapter(ds_context, _EDGAR_FILINGS_BODY)


@given("SEC EDGAR 适配器已构造并注入 XBRL 概念应答传输层")
def edgar_adapter_with_xbrl(ds_context: dict[str, Any]):
    """Construct a SecEdgarAdapter with an XBRL companyconcept responder."""
    _build_edgar_adapter(ds_context, _EDGAR_XBRL_BODY)


@given("SEC EDGAR 适配器已构造并注入应答传输层")
def edgar_adapter_generic(ds_context: dict[str, Any]):
    """Construct a SecEdgarAdapter with a default responder (must not be reached)."""
    _build_edgar_adapter(ds_context, _EDGAR_FILINGS_BODY)


@when(parsers.parse('以检索式 "{query}" 执行 EDGAR 数据采集'))
@when(parsers.parse('以 XBRL 检索式 "{query}" 执行 EDGAR 数据采集'))
@when(parsers.parse('以非法前缀检索式 "{query}" 执行 EDGAR 数据采集'))
def fetch_edgar_with_query(ds_context: dict[str, Any], query: str):
    """Run one EDGAR fetch (search default / xbrl prefix / invalid prefix)."""
    _fetch(ds_context, "sec-edgar", query)


@then("全部请求携带规范 UA 头")
def verify_edgar_ua_header(ds_context: dict[str, Any]):
    """Verify every request carries the official UA header (Fair Access duty)."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    ua = ds_context["captured"][0].headers.get("user-agent", "")
    assert "sisys-tools" in ua and "@" in ua, f"official UA (company email) expected, got: {ua!r}"


@then("结果结构化为财报列表")
def verify_edgar_filings_structured(ds_context: dict[str, Any]):
    """Verify the payload is a structured filings list."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    payload = json.loads(ds_context["result"].payload)
    assert isinstance(payload.get("filings"), list) and payload["filings"], "non-empty filings expected"
    assert {"company", "form", "filed_at"} <= set(payload["filings"][0])


@then("请求分派至 XBRL 数据端点")
def verify_edgar_xbrl_dispatch(ds_context: dict[str, Any]):
    """Verify the request dispatched to the data.sec.gov companyconcept endpoint."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    url = str(ds_context["captured"][0].url)
    assert "data.sec.gov" in url and "companyconcept" in url, f"XBRL companyconcept expected, got: {url}"


@then("结果结构化为指标时序")
def verify_edgar_xbrl_structured(ds_context: dict[str, Any]):
    """Verify the XBRL payload is a concept time series."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    payload = json.loads(ds_context["result"].payload)
    assert {"concept", "unit", "values"} <= set(payload)


@then("前置校验抛出参数校验异常")
def verify_validation_error_raised(ds_context: dict[str, Any]):
    """Verify the input precheck raised ValidationError."""
    assert isinstance(ds_context["query_error"], ValidationError), (
        f"ValidationError expected, got {type(ds_context['query_error']).__name__}"
    )


@then("参数校验异常编码为 EXCEPTION_201")
def verify_validation_error_code(ds_context: dict[str, Any]):
    """Verify the validation error code is EXCEPTION_201."""
    assert ds_context["query_error"].code == "EXCEPTION_201"


# ===================================================================
# AC-4: UN Comtrade Adapter (optional key + daily quota guard)
# ===================================================================


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "Comtrade 免 key preview 检索返回贸易记录",
)
def test_comtrade_keyless_preview(ds_context: dict[str, Any]):
    """Test Comtrade keyless preview mode omits the subscription header."""
    pass


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "Comtrade 配置 key 时附加订阅头",
)
def test_comtrade_key_attaches_header(ds_context: dict[str, Any]):
    """Test Comtrade with a key attaches the subscription header."""
    pass


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "Comtrade 管道串缺商品码前置校验拒绝",
)
def test_comtrade_missing_cmd_rejected(ds_context: dict[str, Any]):
    """Test Comtrade pipeline query missing cmd raises ValidationError."""
    pass


@scenario(
    "test_acceptance_data_source_expansion.feature",
    "Comtrade 日配额超限前置拦截",
)
def test_comtrade_daily_quota_preflight(ds_context: dict[str, Any]):
    """Test Comtrade daily quota guard preflight raises 412 with zero requests."""
    pass


def _build_comtrade_adapter(ds_context: dict[str, Any], api_key: str, quota_requests_used: int = 0) -> None:
    """Construct a real ComtradeAdapter with a capturing MockTransport."""
    client, captured = _capture_client(_COMTRADE_API_URL, lambda request: httpx.Response(200, json=_COMTRADE_RECORDS_BODY))
    ds_context["captured"] = captured
    ds_context["adapter"] = ComtradeAdapter(
        config=ComtradeConfig(api_key=api_key, api_url=_COMTRADE_API_URL, timeout=5.0),
        quota_requests_used=quota_requests_used,
        client=client,
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


@given("Comtrade 适配器已构造为无 key 模式并注入贸易记录应答传输层")
def comtrade_adapter_keyless(ds_context: dict[str, Any]):
    """Construct a keyless ComtradeAdapter (empty key - preview bare mode)."""
    _build_comtrade_adapter(ds_context, api_key="")


@given("Comtrade 适配器已构造为有 key 模式并注入贸易记录应答传输层")
def comtrade_adapter_with_key(ds_context: dict[str, Any]):
    """Construct a keyed ComtradeAdapter (subscription header enhancement)."""
    _build_comtrade_adapter(ds_context, api_key=_fake_comtrade_key())


@given("Comtrade 适配器已构造并注入应答传输层")
def comtrade_adapter_generic(ds_context: dict[str, Any]):
    """Construct a default ComtradeAdapter (must not reach upstream)."""
    _build_comtrade_adapter(ds_context, api_key="")


@given("Comtrade 适配器已构造并注入已耗尽日配额计数")
def comtrade_adapter_exhausted_quota(ds_context: dict[str, Any]):
    """Construct a ComtradeAdapter with a pre-exhausted daily quota counter."""
    _build_comtrade_adapter(ds_context, api_key=_fake_comtrade_key(), quota_requests_used=500)


@when(parsers.parse('以管道串 "{query}" 执行 Comtrade 数据采集'))
def fetch_comtrade_with_pipeline(ds_context: dict[str, Any], query: str):
    """Run one Comtrade pipeline-query fetch."""
    _fetch(ds_context, "comtrade", query)


@then("请求不携带订阅头")
def verify_comtrade_no_subscription_header(ds_context: dict[str, Any]):
    """Verify the keyless request omits Ocp-Apim-Subscription-Key."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    header_names = {name.lower() for name in ds_context["captured"][0].headers}
    assert "ocp-apim-subscription-key" not in header_names


@then("结果结构化为贸易记录列表")
def verify_comtrade_records_structured(ds_context: dict[str, Any]):
    """Verify the payload is a structured trade-records list."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    payload = json.loads(ds_context["result"].payload)
    assert isinstance(payload.get("records"), list) and payload["records"], "non-empty records expected"
    assert {"cmd_code", "trade_value", "period"} <= set(payload["records"][0])


@then("请求自动携带订阅密钥头")
def verify_comtrade_subscription_header(ds_context: dict[str, Any]):
    """Verify the keyed request carries Ocp-Apim-Subscription-Key."""
    assert ds_context["query_error"] is None, f"fetch failed: {ds_context['query_error']}"
    header = ds_context["captured"][0].headers.get("ocp-apim-subscription-key")
    assert header == _fake_comtrade_key()
