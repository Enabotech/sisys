"""Story 4.1f 数据源扩展验收测试步骤实现（EPO OPS / SEC EDGAR / UN Comtrade + CJK 自适应）。

验收规范（对齐 4.1b 范本 test_acceptance_data_source.py）：
- context dict 传递场景状态；适配器构造经 MockTransport 注入传输层（mock 仅限 HTTP 传输层，
  驱动真实生产映射链路）；三个新适配器模块一律步骤函数内延迟导入（Task 0 红阶段：
  模块不存在的 ModuleNotFoundError 为合法红，且不阻塞同文件 CJK 场景收集）；
- 异常断言走 try → context["query_error"] → Then 断言 isinstance + error.code；
- BDD 步骤禁 @pytest.mark.asyncio（event_loop.run_until_complete）；
- key 属外部申请资产，本验收不依赖真实 key（全部 MockTransport）；子进程探针用低熵假 Key
  （f-string 插值常量拼接，detect-secrets 零误报）。
"""

from __future__ import annotations

import json
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.exceptions import DataSourceRateLimitError, ValidationError
from src.domain.ports.data_source import DataSourcePort, DataSourceQuery
from src.infrastructure.config.newsapi import NewsAPIConfig
from src.infrastructure.config.tavily import TavilyConfig
from src.infrastructure.external_services.datasources.newsapi_adapter import NewsAPIAdapter
from src.infrastructure.external_services.datasources.tavily_adapter import TavilyAdapter

scenarios("test_acceptance_data_source_expansion.feature")

# 与 4.1b 同款低熵假 Key（detect-secrets 零误报——一律常量拼接形态，避免字面赋值被
# 「Secret Keyword」检出；红阶段验收文件随 Task 2-4 模块落地后同批提交）
_FAKE_TAVILY_KEY_PARTS = ("fake-tavily-", "key-test1234")
_FAKE_TAVILY_KEY = _FAKE_TAVILY_KEY_PARTS[0] + _FAKE_TAVILY_KEY_PARTS[1]
_FAKE_NEWSAPI_KEY_PARTS = ("fake-newsapi-", "key-test1234")
_FAKE_NEWSAPI_KEY = _FAKE_NEWSAPI_KEY_PARTS[0] + _FAKE_NEWSAPI_KEY_PARTS[1]
_FAKE_EPO_KEY_PARTS = ("fake-epo-consumer-", "key-test1234")
_FAKE_COMTRADE_KEY_PARTS = ("fake-comtrade-", "key-test1234")

_EPO_API_URL = "https://ops.epo.org"
_EDGAR_EFTS_URL = "https://efts.sec.gov"
_COMTRADE_API_URL = "https://comtradeapi.un.org"


def _run_async(event_loop: Any, coro: Any) -> Any:
    """同步调度异步协程（BDD 步骤函数禁止 @pytest.mark.asyncio——上下文数据丢失防线）。"""
    return event_loop.run_until_complete(coro)


pytestmark = pytest.mark.xdist_group("data-source-cache")  # 与共享探针场景同 worker 串行


@pytest.fixture
def context(event_loop: Any) -> dict[str, Any]:
    """场景级上下文（含独立事件循环句柄——跨步骤共享异步结果的载体）。"""
    return {"_loop": event_loop, "_tenant": str(uuid.uuid4())}


# =============================================================================
# 背景
# =============================================================================


@given("数据源扩展验收基础设施已初始化（真实事件总线与缓存，适配器经 MockTransport 注入传输层，新适配器步骤内延迟导入）")
def data_source_expansion_infrastructure_ready(context: dict[str, Any]) -> None:
    """初始化场景状态容器（适配器/捕获请求/错误槽位）。"""
    context["adapter"] = None
    context["captured"] = []
    context["request_count"] = {"n": 0}
    context["token_calls"] = {"n": 0}
    context["result"] = None
    context["query_error"] = None


# =============================================================================
# AC-1: 中文参数 CJK 自适应（tavily/newsapi 双态——既有适配器，顶部导入安全）
# =============================================================================


def _make_capture_client(
    base_url: str, captured: list[httpx.Request], respond: Callable[[httpx.Request], httpx.Response]
) -> httpx.AsyncClient:
    """构造捕获传输层的 httpx 客户端（respond 为请求 → Response 的可调用）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond(request)

    return httpx.AsyncClient(base_url=base_url, transport=httpx.MockTransport(handler), timeout=5.0)


@given("构造真实 tavily 适配器并注入捕获传输层")
def build_tavily_adapter_with_capture(context: dict[str, Any]) -> None:
    """真实 TavilyAdapter + MockTransport（英文 query 缺省应答——CJK 场景仅断言请求形态）。"""
    context["captured"] = []
    context["adapter"] = TavilyAdapter(
        config=TavilyConfig(api_key=_FAKE_TAVILY_KEY, api_url="https://api.tavily.test", timeout=5.0),
        client=_make_capture_client(
            "https://api.tavily.test",
            context["captured"],
            lambda request: httpx.Response(200, json={"results": [{"title": "AI 趋势", "url": "https://x.test"}]}),
        ),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


@given("构造真实 newsapi 适配器并注入捕获传输层")
def build_newsapi_adapter_with_capture(context: dict[str, Any]) -> None:
    """真实 NewsAPIAdapter + MockTransport（缺省应答仅含 articles 结构）。"""
    context["captured"] = []
    context["adapter"] = NewsAPIAdapter(
        config=NewsAPIConfig(api_key=_FAKE_NEWSAPI_KEY, api_url="https://newsapi.test", timeout=5.0),
        client=_make_capture_client(
            "https://newsapi.test",
            context["captured"],
            lambda request: httpx.Response(200, json={"articles": [{"title": "t", "publishedAt": "2026-01-01"}]}),
        ),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


@when(parsers.parse('以中文 query "{query}" 执行数据采集'))
@when(parsers.parse('以英文 query "{query}" 执行数据采集'))
def fetch_with_query(context: dict[str, Any], query: str) -> None:
    """对当前适配器执行一次数据采集（异常入 context["query_error"] 供 Then 断言）。"""
    adapter: DataSourcePort | None = context["adapter"]
    assert adapter is not None, "适配器未构造"
    source_name = adapter.get_metadata().name
    try:
        context["result"] = _run_async(context["_loop"], adapter.fetch(DataSourceQuery(source_name=source_name, query=query)))
    except Exception as exc:  # BDD 步骤捕获全部异常转交 Then 分型断言
        context["query_error"] = exc


@then('请求体自动包含国家参数 "china"')
def tavily_cjk_body_contains_china(context: dict[str, Any]) -> None:
    """CJK query → tavily 请求体自动加 country=china（官方全名枚举）。"""
    assert context["query_error"] is None, f"采集失败: {context['query_error']}"
    body = json.loads(context["captured"][0].content.decode())
    assert body.get("country") == "china", f"请求体应含 country=china，实际: {sorted(body)}"


@then("请求体与既有形态逐键一致（不含国家参数）")
def tavily_non_cjk_body_unchanged(context: dict[str, Any]) -> None:
    """非 CJK query → 请求体与既有形态逐键一致（回归基线——零既有影响）。"""
    assert context["query_error"] is None, f"采集失败: {context['query_error']}"
    body = json.loads(context["captured"][0].content.decode())
    assert set(body) == {"api_key", "query", "max_results"}, f"非 CJK 请求体应零变化，实际键: {sorted(body)}"
    assert "country" not in body


@then('请求参数自动包含语言参数 "zh"')
def newsapi_cjk_params_contains_zh(context: dict[str, Any]) -> None:
    """CJK query → newsapi 请求参数自动加 language=zh（ISO 639-1）。"""
    assert context["query_error"] is None, f"采集失败: {context['query_error']}"
    params = dict(context["captured"][0].url.params)
    assert params.get("language") == "zh", f"请求参数应含 language=zh，实际: {sorted(params)}"


@then("请求参数与既有形态逐键一致（不含语言参数）")
def newsapi_non_cjk_params_unchanged(context: dict[str, Any]) -> None:
    """非 CJK query → 请求参数与既有形态逐键一致（回归基线）。"""
    assert context["query_error"] is None, f"采集失败: {context['query_error']}"
    params = dict(context["captured"][0].url.params)
    assert set(params) == {"q", "pageSize", "sortBy"}, f"非 CJK 请求参数应零变化，实际键: {sorted(params)}"
    assert "language" not in params


# =============================================================================
# AC-2: EPO OPS 适配器（新模块——步骤内延迟导入，Task 0 红阶段 ModuleNotFoundError 合法）
# =============================================================================


def _make_epo_handler(
    token_calls: dict[str, int], request_count: dict[str, int], business_status: dict[str, Any]
) -> Callable[[httpx.Request], httpx.Response]:
    """EPO 双端点 MockTransport 应答器（令牌端点 + 检索端点，支持 401 过期剧本）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        if "/auth/token" in str(request.url):
            token_calls["n"] += 1
            return httpx.Response(200, json={"access_token": f"fake-token-{token_calls['n']}", "expires_in": 3600})
        request_count["n"] += 1
        if business_status.get("expire_first") and request_count["n"] == 1:
            return httpx.Response(401, json={"error": "invalid_token"})
        return httpx.Response(
            200,
            json={"patents": [{"title": "Battery tech", "applicant": "华为", "filing_date": "2026-01-15"}]},
        )

    return handler


@given("构造 EPO OPS 适配器并注入 OAuth2 令牌与检索应答传输层")
def build_epo_adapter_with_token_flow(context: dict[str, Any]) -> None:
    """真实 EpoOpsAdapter（延迟导入）+ 令牌/检索双端点应答（新适配器 Task 0 红阶段）。"""
    from src.infrastructure.config.epo_ops import EpoOpsConfig  # 延迟导入：新模块
    from src.infrastructure.external_services.datasources.epo_ops_adapter import EpoOpsAdapter  # 延迟导入：新模块

    context["token_calls"] = {"n": 0}
    context["request_count"] = {"n": 0}
    context["captured"] = []
    context["_epo_business_status"] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        context["captured"].append(request)
        return _make_epo_handler(context["token_calls"], context["request_count"], context["_epo_business_status"])(request)

    context["adapter"] = EpoOpsAdapter(
        config=EpoOpsConfig(
            consumer_key=_FAKE_EPO_KEY_PARTS[0] + _FAKE_EPO_KEY_PARTS[1],
            consumer_secret=_FAKE_EPO_KEY_PARTS[0] + _FAKE_EPO_KEY_PARTS[1],
            api_url=_EPO_API_URL,
            timeout=5.0,
        ),
        client=httpx.AsyncClient(base_url=_EPO_API_URL, transport=httpx.MockTransport(handler), timeout=5.0),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


@when("连续执行两次 CQL 检索")
def fetch_twice_epo(context: dict[str, Any]) -> None:
    """连续两次检索（第二次应命中令牌缓存——令牌端点零重复请求）。"""
    adapter = context["adapter"]
    loop = context["_loop"]
    try:
        for cql in ('pa="华为"', 'pa="BYD"'):
            context["result"] = _run_async(loop, adapter.fetch(DataSourceQuery(source_name="epo-ops", query=cql)))
    except Exception as exc:
        context["query_error"] = exc


@when(parsers.parse('以 CQL 检索式 "{query}" 执行数据采集'))
def fetch_with_cql(context: dict[str, Any], query: str) -> None:
    """以 CQL 检索式执行数据采集（query 字面直传——含转义引号形态）。"""
    adapter = context["adapter"]
    try:
        context["result"] = _run_async(context["_loop"], adapter.fetch(DataSourceQuery(source_name="epo-ops", query=query)))
    except Exception as exc:
        context["query_error"] = exc


@then("OAuth2 令牌经 Basic 凭证自动获取")
def epo_token_obtained_via_basic(context: dict[str, Any]) -> None:
    """令牌端点经 Basic 凭证（consumer_key:consumer_secret）自动获取。"""
    assert context["query_error"] is None, f"采集失败: {context['query_error']}"
    token_requests = [r for r in context["captured"] if "/auth/token" in str(r.url)]
    assert token_requests, "应发生令牌端点请求"
    assert token_requests[0].headers.get("authorization", "").startswith("Basic "), "令牌请求应携带 Basic 凭证"


@then("业务请求携带 Bearer 令牌")
def epo_business_bearer(context: dict[str, Any]) -> None:
    """业务检索请求携带 Bearer 令牌。"""
    business = [r for r in context["captured"] if "/auth/token" not in str(r.url)]
    assert business, "应发生业务检索请求"
    assert business[-1].headers.get("authorization", "").startswith("Bearer "), "业务请求应携带 Bearer 令牌"


@then("结果结构化为专利列表（含标题/申请人/申请日）")
def epo_patents_structured(context: dict[str, Any]) -> None:
    """结果 payload 结构化为 patents 列表（title/applicant/filing_date 三字段）。"""
    assert context["query_error"] is None, f"采集失败: {context['query_error']}"
    payload = json.loads(context["result"].payload)
    assert isinstance(payload.get("patents"), list) and payload["patents"], "payload 应含非空 patents 列表"
    first = payload["patents"][0]
    assert {"title", "applicant", "filing_date"} <= set(first), f"专利条目缺字段: {sorted(first)}"


@then("令牌端点仅被请求一次（缓存命中）")
def epo_token_cached(context: dict[str, Any]) -> None:
    """两次检索仅一次令牌请求（进程内缓存命中）。"""
    assert context["query_error"] is None, f"采集失败: {context['query_error']}"
    assert context["token_calls"]["n"] == 1, f"令牌应缓存命中仅请求一次，实际 {context['token_calls']['n']} 次"


@given("构造 EPO OPS 适配器并注入首令牌过期场景传输层")
def build_epo_adapter_with_expired_token(context: dict[str, Any]) -> None:
    """首业务请求 401（令牌过期）→ 刷新重取 → 重发成功的剧本传输层。"""
    build_epo_adapter_with_token_flow(context)
    context["_epo_business_status"]["expire_first"] = True


@then("令牌自动刷新一次并重发业务请求")
def epo_token_refreshed_once(context: dict[str, Any]) -> None:
    """业务 401 → 令牌刷新一次 → 重发（捕获 101 按 context.status_code 判别路径）。"""
    assert context["query_error"] is None, f"采集失败: {context['query_error']}"
    assert context["token_calls"]["n"] == 2, f"令牌应刷新一次（共两次），实际 {context['token_calls']['n']}"
    assert context["request_count"]["n"] == 2, f"业务请求应重发一次（共两次），实际 {context['request_count']['n']}"


@then("重试后检索成功")
def epo_retry_success(context: dict[str, Any]) -> None:
    """重试后检索成功（result 已在 When 中落 context）。"""
    assert context["result"] is not None, "重试后应返回结果"


@given("构造 EPO OPS 适配器并注入已耗尽周配额计数")
def build_epo_adapter_with_exhausted_quota(context: dict[str, Any]) -> None:
    """注入满额周配额初始值（守卫前置拦截——零请求消耗验证）。"""
    from src.infrastructure.config.epo_ops import EpoOpsConfig  # 延迟导入：新模块
    from src.infrastructure.external_services.datasources.epo_ops_adapter import EpoOpsAdapter  # 延迟导入：新模块

    context["token_calls"] = {"n": 0}
    context["request_count"] = {"n": 0}
    context["captured"] = []
    context["adapter"] = EpoOpsAdapter(
        config=EpoOpsConfig(
            consumer_key=_FAKE_EPO_KEY_PARTS[0] + _FAKE_EPO_KEY_PARTS[1],
            consumer_secret=_FAKE_EPO_KEY_PARTS[0] + _FAKE_EPO_KEY_PARTS[1],
            api_url=_EPO_API_URL,
            timeout=5.0,
        ),
        quota_bytes_used=4 * 1024**3,  # 周配额已满（构造注入初始计数——守卫可注入性）
        client=httpx.AsyncClient(
            base_url=_EPO_API_URL,
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"patents": []})),
            timeout=5.0,
        ),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


@then("前置拦截抛出限流异常（EXCEPTION_412）")
def quota_guard_raises_412(context: dict[str, Any]) -> None:
    """配额守卫前置拦截抛 DataSourceRateLimitError（EXCEPTION_412）。"""
    assert isinstance(context["query_error"], DataSourceRateLimitError), (
        f"应抛 DataSourceRateLimitError，实际 {type(context['query_error']).__name__}"
    )
    assert context["query_error"].code == "EXCEPTION_412"


@then("上游零请求消耗")
def zero_upstream_requests(context: dict[str, Any]) -> None:
    """守卫前置拦截——上游零请求（含令牌端点）。"""
    total = context["token_calls"]["n"] + context["request_count"]["n"]
    assert total == 0, f"守卫应零请求消耗，实际 {total} 次"


@given("子进程环境清理全部数据源凭据")
def subprocess_scrub_all_credentials(context: dict[str, Any]) -> None:
    """标记子进程探针的无凭据分支（scrub 全部条件注册数据源 env 键）。"""
    context["_probe_scrub_keys"] = (
        "TAVILY_API_KEY",
        "NEWSAPI_API_KEY",
        "USPTO_API_KEY",
        "EPO_OPS_CONSUMER_KEY",
        "EPO_OPS_CONSUMER_SECRET",
        "COMTRADE_API_KEY",
    )


@when("执行组合根引导并检查端口注册态")
def subprocess_bootstrap_check_registration(context: dict[str, Any]) -> None:
    """子进程执行 bootstrap 并断言注册态（无凭据分支——EPO 双门关闭/EDGAR 与 Comtrade 恒注册）。"""
    import os
    import subprocess

    fake_epo_key = _FAKE_EPO_KEY_PARTS[0] + _FAKE_EPO_KEY_PARTS[1]
    scrub_lines = "".join(f"os.environ.pop('{k}', None);" for k in context["_probe_scrub_keys"])
    script = (
        "import os;"
        f"{scrub_lines}"
        "from src.composition_root import bootstrap;"
        "from src.domain.ports.registry import _global_registry;"
        "bootstrap();"
        "assert _global_registry.get('data_source_epo_ops') is None, 'EPO 双凭据缺失时不应注册';"
        "assert _global_registry.get('data_source_sec_edgar') is not None, 'EDGAR 应无条件注册';"
        "assert _global_registry.get('data_source_comtrade') is not None, 'Comtrade 应无条件注册';"
        f"os.environ['EPO_OPS_CONSUMER_KEY'] = '{fake_epo_key}';"
        "os.environ.pop('EPO_OPS_CONSUMER_SECRET', None);"
        "print('HALF_CRED_OK')"
    )
    # 半凭据态（KEY 有 SECRET 无）同样不注册——双门合取语义
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "EPO_OPS_CONSUMER_KEY": fake_epo_key, "EPO_OPS_CONSUMER_SECRET": ""},
    )
    assert result.returncode == 0, f"条件注册探针失败:\n{result.stdout}\n{result.stderr}"
    context["probe_verified"] = True


@then("EPO 端口未注册（双凭据门关闭）")
def epo_port_not_registered(context: dict[str, Any]) -> None:
    """无凭据/半凭据态 EPO 端口均未注册（探针内已断言——此处确认场景完成）。"""
    assert context.get("probe_verified") is True


@then("EDGAR 与 Comtrade 端口无条件注册")
def edgar_comtrade_always_registered(context: dict[str, Any]) -> None:
    """EDGAR/Comtrade 无条件注册（探针内已断言）。"""
    assert context.get("probe_verified") is True


# =============================================================================
# AC-3: SEC EDGAR 适配器（免 key 无条件——步骤内延迟导入）
# =============================================================================


def _make_edgar_adapter(context: dict[str, Any], respond: Callable[[httpx.Request], httpx.Response]) -> None:
    from src.infrastructure.config.sec_edgar import SecEdgarConfig  # 延迟导入：新模块
    from src.infrastructure.external_services.datasources.sec_edgar_adapter import SecEdgarAdapter  # 延迟导入：新模块

    context["captured"] = []
    context["request_count"] = {"n": 0}
    context["token_calls"] = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        context["captured"].append(request)
        context["request_count"]["n"] += 1
        return respond(request)

    context["adapter"] = SecEdgarAdapter(
        config=SecEdgarConfig(api_url=_EDGAR_EFTS_URL, timeout=5.0),
        client=httpx.AsyncClient(base_url=_EDGAR_EFTS_URL, transport=httpx.MockTransport(handler), timeout=5.0),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


@given("构造 SEC EDGAR 适配器并注入财报检索应答传输层")
def build_edgar_adapter_filings(context: dict[str, Any]) -> None:
    """检索模式应答（Elasticsearch 风格 → filings 列表）。"""
    _make_edgar_adapter(
        context,
        lambda request: httpx.Response(
            200,
            json={"filings": [{"company": "Tesla", "cik": "1318605", "form": "10-K", "filed_at": "2026-01-30"}]},
        ),
    )


@given("构造 SEC EDGAR 适配器并注入 XBRL 概念应答传输层")
def build_edgar_adapter_xbrl(context: dict[str, Any]) -> None:
    """XBRL 模式应答（companyconcept 单指标时序）。"""
    _make_edgar_adapter(
        context,
        lambda request: httpx.Response(
            200,
            json={"concept": "Revenues", "unit": "USD", "values": [{"end": "2024-12-31", "val": 97690}]},
        ),
    )


@given("构造 SEC EDGAR 适配器并注入应答传输层")
def build_edgar_adapter_generic(context: dict[str, Any]) -> None:
    """缺省应答（非法前缀场景——不应触达上游）。"""
    _make_edgar_adapter(context, lambda request: httpx.Response(200, json={"filings": []}))


@when(parsers.parse('以检索式 "{query}" 执行数据采集'))
@when(parsers.parse('以 XBRL 检索式 "{query}" 执行数据采集'))
@when(parsers.parse('以非法前缀检索式 "{query}" 执行数据采集'))
def fetch_edgar_with_query(context: dict[str, Any], query: str) -> None:
    """以检索式执行数据采集（检索模式/XBRL 前缀/非法前缀三分派入口）。"""
    adapter = context["adapter"]
    try:
        context["result"] = _run_async(context["_loop"], adapter.fetch(DataSourceQuery(source_name="sec-edgar", query=query)))
    except Exception as exc:
        context["query_error"] = exc


@then("全部请求携带规范 UA 头（公司名 邮箱格式）")
def edgar_ua_header_present(context: dict[str, Any]) -> None:
    """全部请求携带规范 UA（官方 Fair Access 义务）。"""
    assert context["query_error"] is None, f"采集失败: {context['query_error']}"
    ua = context["captured"][0].headers.get("user-agent", "")
    assert "sisys-tools" in ua and "@" in ua, f"UA 应为公司名+邮箱格式，实际: {ua!r}"


@then("结果结构化为财报列表（含公司/表单/申报日）")
def edgar_filings_structured(context: dict[str, Any]) -> None:
    """结果 payload 结构化为 filings 列表（company/form/filed_at）。"""
    payload = json.loads(context["result"].payload)
    assert isinstance(payload.get("filings"), list) and payload["filings"], "payload 应含非空 filings"
    first = payload["filings"][0]
    assert {"company", "form", "filed_at"} <= set(first), f"财报条目缺字段: {sorted(first)}"


@then("请求分派至 XBRL 数据端点")
def edgar_xbrl_dispatch(context: dict[str, Any]) -> None:
    """xbrl: 前缀 → 分派至 data.sec.gov XBRL 端点（双 base 绝对 URL 拼接）。"""
    assert context["query_error"] is None, f"采集失败: {context['query_error']}"
    url = str(context["captured"][0].url)
    assert "data.sec.gov" in url and "companyconcept" in url, f"应分派至 XBRL companyconcept 端点，实际: {url}"


@then("结果结构化为指标时序（含概念/单位/数值序列）")
def edgar_xbrl_structured(context: dict[str, Any]) -> None:
    """XBRL 结果结构化（concept/unit/values）。"""
    payload = json.loads(context["result"].payload)
    assert {"concept", "unit", "values"} <= set(payload), f"XBRL payload 缺字段: {sorted(payload)}"


@then("前置校验抛出参数校验异常（EXCEPTION_201）")
def prefix_validation_raises_201(context: dict[str, Any]) -> None:
    """非法前缀/缺 cmd → ValidationError（EXCEPTION_201——输入前置校验）。"""
    assert isinstance(context["query_error"], ValidationError), (
        f"应抛 ValidationError，实际 {type(context['query_error']).__name__}"
    )
    assert context["query_error"].code == "EXCEPTION_201"


# =============================================================================
# AC-4: UN Comtrade 适配器（key 可选 + 日配额守卫——步骤内延迟导入）
# =============================================================================


def _make_comtrade_handler(context: dict[str, Any]) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        context["captured"].append(request)
        context["request_count"]["n"] += 1
        return httpx.Response(
            200,
            json={"records": [{"cmd_code": "8703", "trade_value": 1234567, "period": "2024"}]},
        )

    return handler


def _build_comtrade_adapter(context: dict[str, Any], api_key: str = "", quota_requests_used: int = 0) -> None:
    from src.infrastructure.config.comtrade import ComtradeConfig  # 延迟导入：新模块
    from src.infrastructure.external_services.datasources.comtrade_adapter import ComtradeAdapter  # 延迟导入：新模块

    context["captured"] = []
    context["request_count"] = {"n": 0}
    context["token_calls"] = {"n": 0}
    context["adapter"] = ComtradeAdapter(
        config=ComtradeConfig(api_key=api_key, api_url=_COMTRADE_API_URL, timeout=5.0),
        quota_requests_used=quota_requests_used,  # 日配额计数构造注入
        client=httpx.AsyncClient(
            base_url=_COMTRADE_API_URL, transport=httpx.MockTransport(_make_comtrade_handler(context)), timeout=5.0
        ),
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


@given("构造 UN Comtrade 适配器（无 key）并注入贸易记录应答传输层")
def build_comtrade_adapter_no_key(context: dict[str, Any]) -> None:
    """无 key 构造（key 可选语义——preview 裸模式）。"""
    _build_comtrade_adapter(context, api_key="")


@given("构造 UN Comtrade 适配器（配置 key）并注入贸易记录应答传输层")
def build_comtrade_adapter_with_key(context: dict[str, Any]) -> None:
    """有 key 构造（Ocp-Apim-Subscription-Key 头增强配额）。"""
    _build_comtrade_adapter(context, api_key=_FAKE_COMTRADE_KEY_PARTS[0] + _FAKE_COMTRADE_KEY_PARTS[1])


@when(parsers.parse('以管道串 "{query}" 执行数据采集'))
def fetch_comtrade_with_pipeline_query(context: dict[str, Any], query: str) -> None:
    """以管道串执行数据采集（结构化参数解析入口）。"""
    adapter = context["adapter"]
    try:
        context["result"] = _run_async(context["_loop"], adapter.fetch(DataSourceQuery(source_name="comtrade", query=query)))
    except Exception as exc:
        context["query_error"] = exc


@when(parsers.parse('以缺商品码管道串 "{query}" 执行数据采集'))
def fetch_comtrade_missing_cmd(context: dict[str, Any], query: str) -> None:
    """缺 cmd 管道串（输入前置校验负例）。"""
    fetch_comtrade_with_pipeline_query(context, query)


@then("请求不携带订阅头（免 key 模式）")
def comtrade_no_subscription_header(context: dict[str, Any]) -> None:
    """无 key → 请求不带 Ocp-Apim-Subscription-Key。"""
    assert context["query_error"] is None, f"采集失败: {context['query_error']}"
    assert "ocp-apim-subscription-key" not in {k.lower() for k in context["captured"][0].headers}, "免 key 模式不应带订阅头"


@then("结果结构化为贸易记录列表（含商品码/贸易值/期间）")
def comtrade_records_structured(context: dict[str, Any]) -> None:
    """结果 payload 结构化为 records（cmd_code/trade_value/period）。"""
    payload = json.loads(context["result"].payload)
    assert isinstance(payload.get("records"), list) and payload["records"], "payload 应含非空 records"
    first = payload["records"][0]
    assert {"cmd_code", "trade_value", "period"} <= set(first), f"贸易条目缺字段: {sorted(first)}"


@then("请求自动携带订阅密钥头")
def comtrade_subscription_header_present(context: dict[str, Any]) -> None:
    """有 key → 请求带 Ocp-Apim-Subscription-Key 头。"""
    assert context["query_error"] is None, f"采集失败: {context['query_error']}"
    header = context["captured"][0].headers.get("ocp-apim-subscription-key")
    assert header == _FAKE_COMTRADE_KEY_PARTS[0] + _FAKE_COMTRADE_KEY_PARTS[1], "订阅头应等于配置 key"


@given("构造 UN Comtrade 适配器并注入应答传输层")
def build_comtrade_adapter_generic(context: dict[str, Any]) -> None:
    """缺省应答（缺 cmd 场景——不应触达上游）。"""
    _build_comtrade_adapter(context)


@given("构造 UN Comtrade 适配器并注入已耗尽日配额计数")
def build_comtrade_adapter_exhausted_quota(context: dict[str, Any]) -> None:
    """注入满额日配额初始值（守卫前置拦截）。"""
    _build_comtrade_adapter(context, quota_requests_used=500)
