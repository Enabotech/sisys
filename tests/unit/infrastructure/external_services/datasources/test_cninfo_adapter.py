"""Story 4.1f Task 10 — cninfo 巨潮资讯适配器单元测试（D-10 范围扩展）

验证 cninfo 数据源适配器（免 key A 组无条件注册 + 两段式 POST 表单公告检索）：
- 管道串解析：keyword 必填（缺失/未知参数/段格式非法/空串 → 201 输入前置校验——comtrade 范式）
- 两段式：topSearch 公司匹配（form: keyWord/maxNum + UA 头）→ hisAnnouncement 公告查询
  （form: stock=code,orgId + column 沪深判定——code 6 开头 sse 其余 szse；A 股优先匹配）
- 结构化：announcementTime 毫秒时间戳 → ISO UTC；adjunctUrl 相对路径 → 绝对 PDF URL
- 空结果语义：topSearch 空数组短路（第二段零请求）/ announcements null → 空列表正常返回
  （EDGAR 空结果同语义——SOP §7 数据缺口话术承接）
- 失败矩阵：401/403→101、429→412、5xx→411、超时→302、非 JSON→413、结构异常→413、熔断
- config：from_env 数值非法 → 101；get_metadata 对齐 SSOT 四值

测试模式：httpx.MockTransport 注入（零外网）。fixture 对齐 2026-10-13 真实端点实测形态
（topSearch「宁德时代」→ GD165627；年报 totalAnnouncement=16）。
"""

from __future__ import annotations

from datetime import UTC, datetime
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
from src.infrastructure.config.cninfo import CninfoConfig
from src.infrastructure.external_services.datasources.cninfo_adapter import (
    PDF_BASE_URL,
    UA_HEADER,
    CninfoAdapter,
    _parse_pipeline_query,
)
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

_CNINFO_URL = "https://www.cninfo.com.cn"

# —— 真实端点形态 fixture（2026-10-13 实测：topSearch 返回 A 股在前 + 港股次之）——
_TOPSEARCH_BODY = [
    {"code": "300750", "orgId": "GD165627", "zwjc": "宁德时代", "category": "A股", "type": "shj"},
    {"code": "03750", "orgId": "GD165627", "zwjc": "宁德时代", "category": "港股", "type": "hke"},
]
_TOPSEARCH_BODY_HK_FIRST = list(reversed(_TOPSEARCH_BODY))
_TOPSEARCH_SZ_BODY = [{"code": "600519", "orgId": "GD165627", "zwjc": "贵州茅台", "category": "A股", "type": "shj"}]
_ANN_2025 = {
    "announcementTitle": "2025年年度报告",
    "adjunctUrl": "finalpage/2026-03-10/1225002214.PDF",
    "announcementTime": 1773072000000,
}
_ANN_2024 = {
    "announcementTitle": "2024年年度报告",
    "adjunctUrl": "finalpage/2025-03-10/1200000111.PDF",
    "announcementTime": 1741536000000,
}
_ANNOUNCEMENTS_BODY = {"totalAnnouncement": 16, "announcements": [_ANN_2025, _ANN_2024]}
# 真实端点无结果形态（2026-10-13 实测：announcements 为 null）
_ANNOUNCEMENTS_NULL_BODY = {"totalAnnouncement": 0, "announcements": None, "hasMore": False}


def _make_config() -> CninfoConfig:
    return CninfoConfig(api_url=_CNINFO_URL, timeout=5.0)


def _make_adapter(
    handler: httpx.MockTransport | None = None,
    *,
    circuit_breaker: CircuitBreaker | None = None,
) -> CninfoAdapter:
    """适配器工厂（MockTransport 注入 + 测试加速退避——EDGAR/comtrade 同款范式）。

    缺省 handler 为两段式成功路径（topSearch 宁德时代 → 年报公告）——fetch 行为测试的基线。
    """
    transport = handler or _two_stage_handler([])
    return CninfoAdapter(
        config=_make_config(),
        client=httpx.AsyncClient(base_url=_CNINFO_URL, transport=transport, timeout=5.0),
        circuit_breaker=circuit_breaker,
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )


def _two_stage_handler(
    captured: list[httpx.Request],
    *,
    top_body: object = _TOPSEARCH_BODY,
    ann_body: object = _ANNOUNCEMENTS_BODY,
) -> httpx.MockTransport:
    """两段式 handler：topSearch → hisAnnouncement（按路径分派，未匹配路径 404）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path == "/new/information/topSearch/query":
            return httpx.Response(200, json=top_body)
        if request.url.path == "/new/hisAnnouncement/query":
            return httpx.Response(200, json=ann_body)
        return httpx.Response(404, json={"error": "unexpected path"})

    return httpx.MockTransport(handler)


def _query(raw: str) -> DataSourceQuery:
    return DataSourceQuery(source_name="cninfo", query=raw)


class TestParsePipelineQuery:
    def test_full_three_params(self) -> None:
        """完整三参：keyword/category/seDate 全解析（category/seDate 可选直通）。"""
        params = _parse_pipeline_query("keyword=宁德时代|category=category_ndbg_szsh|seDate=2026-01-01~2026-10-13")
        assert params["keyword"] == "宁德时代"
        assert params["category"] == "category_ndbg_szsh"
        assert params["seDate"] == "2026-01-01~2026-10-13"

    def test_keyword_only(self) -> None:
        """仅必填 keyword（category/seDate 缺省缺位）。"""
        params = _parse_pipeline_query("keyword=贵州茅台")
        assert params["keyword"] == "贵州茅台"
        assert "category" not in params
        assert "seDate" not in params

    def test_empty_string_rejected(self) -> None:
        """空串 → 201。"""
        with pytest.raises(ValidationError, match="cninfo"):
            _parse_pipeline_query("   ")

    def test_missing_keyword_rejected(self) -> None:
        """缺 keyword → 201（消息指引合法参数）。"""
        with pytest.raises(ValidationError, match="keyword"):
            _parse_pipeline_query("category=category_ndbg_szsh")

    def test_unknown_param_rejected(self) -> None:
        """未知参数 → 201。"""
        with pytest.raises(ValidationError, match="未知参数"):
            _parse_pipeline_query("keyword=宁德时代|foo=bar")

    def test_segment_without_equals_rejected(self) -> None:
        """无 = 的段 → 201。"""
        with pytest.raises(ValidationError, match="格式非法"):
            _parse_pipeline_query("keyword=宁德时代|裸段")


class TestFetchTwoStageRequests:
    @pytest.mark.asyncio
    async def test_two_stage_request_shapes(self) -> None:
        """两段式请求形态：topSearch form(keyWord) → hisAnnouncement form(stock/column/tabName/category)。"""
        captured: list[httpx.Request] = []
        adapter = _make_adapter(_two_stage_handler(captured))
        result = await adapter.fetch(_query("keyword=宁德时代|category=category_ndbg_szsh"))
        assert len(captured) == 2

        top_form = parse_qs(captured[0].content.decode("utf-8"))
        assert captured[0].url.path == "/new/information/topSearch/query"
        assert top_form["keyWord"] == ["宁德时代"]

        ann_form = parse_qs(captured[1].content.decode("utf-8"))
        assert captured[1].url.path == "/new/hisAnnouncement/query"
        assert ann_form["stock"] == ["300750,GD165627"]  # A 股匹配（code,orgId）
        assert ann_form["column"] == ["szse"]  # code 3 开头 → 深市
        assert ann_form["tabName"] == ["fulltext"]
        assert ann_form["category"] == ["category_ndbg_szsh"]
        assert result.source_name == "cninfo"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_all_requests_carry_ua(self) -> None:
        """全部请求携带浏览器兼容 UA 常量（cninfo 无官方 UA 义务——礼貌性标识，2026-10-13 实测通过形态）。"""
        captured: list[httpx.Request] = []
        adapter = _make_adapter(_two_stage_handler(captured))
        await adapter.fetch(_query("keyword=宁德时代"))
        assert len(captured) == 2
        for request in captured:
            assert request.headers.get("user-agent") == UA_HEADER
        await adapter.close()

    @pytest.mark.asyncio
    async def test_a_share_preferred_over_hk(self) -> None:
        """A 股优先：港股条目排前时仍匹配 A 股（column 语义按 A 股 code 判定）。"""
        captured: list[httpx.Request] = []
        adapter = _make_adapter(_two_stage_handler(captured, top_body=_TOPSEARCH_BODY_HK_FIRST))
        await adapter.fetch(_query("keyword=宁德时代"))
        ann_form = parse_qs(captured[1].content.decode("utf-8"))
        assert ann_form["stock"] == ["300750,GD165627"]
        await adapter.close()

    @pytest.mark.asyncio
    async def test_shanghai_column_for_6_prefix(self) -> None:
        """沪市判定：code 6 开头 → column=sse（600519 茅台）。"""
        captured: list[httpx.Request] = []
        adapter = _make_adapter(_two_stage_handler(captured, top_body=_TOPSEARCH_SZ_BODY))
        await adapter.fetch(_query("keyword=贵州茅台"))
        ann_form = parse_qs(captured[1].content.decode("utf-8"))
        assert ann_form["stock"] == ["600519,GD165627"]
        assert ann_form["column"] == ["sse"]
        await adapter.close()

    @pytest.mark.asyncio
    async def test_sedate_passthrough(self) -> None:
        """seDate 日期范围直通（波浪号形态——真实端点格式）。"""
        captured: list[httpx.Request] = []
        adapter = _make_adapter(_two_stage_handler(captured))
        await adapter.fetch(_query("keyword=宁德时代|seDate=2026-01-01~2026-10-13"))
        ann_form = parse_qs(captured[1].content.decode("utf-8"))
        assert ann_form["seDate"] == ["2026-01-01~2026-10-13"]
        await adapter.close()


class TestFetchOutputStructure:
    @pytest.mark.asyncio
    async def test_structured_announcements_payload(self) -> None:
        """结构化输出：title 原文 / 毫秒时间戳→ISO UTC / 相对路径→绝对 PDF URL + 公司简称。"""
        import json

        adapter = _make_adapter()
        result = await adapter.fetch(_query("keyword=宁德时代"))
        payload = json.loads(result.payload)
        assert payload["company"] == "宁德时代"
        announcements = payload["announcements"]
        assert announcements[0]["title"] == "2025年年度报告"
        # 1773072000000ms = 北京时间 2026-03-10 00:00（端点为北京时间戳）= UTC 2026-03-09T16:00
        assert announcements[0]["announcement_time"] == "2026-03-09T16:00:00+00:00"
        assert announcements[0]["pdf_url"] == f"{PDF_BASE_URL}/finalpage/2026-03-10/1225002214.PDF"
        assert announcements[1]["title"] == "2024年年度报告"
        assert len(announcements) == 2
        await adapter.close()

    @pytest.mark.asyncio
    async def test_source_timestamp_is_latest_announcement(self) -> None:
        """source_timestamp 取最新公告时间（北京时间戳换算 UTC：2026-03-09T16:00）+ freshness TTL 对齐 config。"""
        adapter = _make_adapter()
        result = await adapter.fetch(_query("keyword=宁德时代"))
        assert result.source_timestamp == datetime(2026, 3, 9, 16, 0, tzinfo=UTC)
        assert result.freshness.ttl_seconds == adapter.get_metadata().ttl_seconds
        await adapter.close()

    @pytest.mark.asyncio
    async def test_confidence_official_disclosure(self) -> None:
        """confidence 0.95（证监会指定法定信息披露平台）。"""
        adapter = _make_adapter()
        result = await adapter.fetch(_query("keyword=宁德时代"))
        assert result.confidence == 0.95
        await adapter.close()


class TestFetchEmptyResults:
    @pytest.mark.asyncio
    async def test_topsearch_empty_short_circuits(self) -> None:
        """topSearch 空结果短路：返回空 announcements 且第二段零请求（capture 长度 == 1）。"""
        captured: list[httpx.Request] = []
        adapter = _make_adapter(_two_stage_handler(captured, top_body=[]))
        import json

        result = await adapter.fetch(_query("keyword=不存在的公司xyz"))
        assert len(captured) == 1  # 仅 topSearch，公告查询未发
        payload = json.loads(result.payload)
        assert payload["announcements"] == []
        await adapter.close()

    @pytest.mark.asyncio
    async def test_announcements_null_treated_as_empty(self) -> None:
        """真实端点无结果形态 announcements=null → 空列表正常返回（非 413）。"""
        captured: list[httpx.Request] = []
        adapter = _make_adapter(_two_stage_handler(captured, ann_body=_ANNOUNCEMENTS_NULL_BODY))
        import json

        result = await adapter.fetch(_query("keyword=宁德时代|seDate=1999-01-01~1999-01-02"))
        payload = json.loads(result.payload)
        assert payload["announcements"] == []
        assert result.source_timestamp is not None  # 空结果仍有 fetched_at 语义的时间基
        await adapter.close()


class TestFailureMatrix:
    @pytest.mark.asyncio
    async def test_http_401_maps_to_configuration_error(self) -> None:
        """HTTP 401 → ConfigurationError(101)（helper 集中映射）。"""
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(401, json={"error": "denied"})))
        with pytest.raises(ConfigurationError):
            await adapter.fetch(_query("keyword=宁德时代"))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_http_429_maps_to_rate_limit(self) -> None:
        """HTTP 429 → DataSourceRateLimitError(412)。"""
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(429, json={"error": "slow down"})))
        with pytest.raises(DataSourceRateLimitError):
            await adapter.fetch(_query("keyword=宁德时代"))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_http_500_maps_to_unavailable(self) -> None:
        """HTTP 5xx（重试耗尽）→ DataSourceUnavailableError(411)。"""
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(500, json={"error": "boom"})))
        with pytest.raises(DataSourceUnavailableError):
            await adapter.fetch(_query("keyword=宁德时代"))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_timeout_maps_to_timeout_error(self) -> None:
        """传输超时 → TimeoutError(302)。"""
        from httpx import ReadTimeout

        def handler(request: httpx.Request) -> httpx.Response:
            raise ReadTimeout("upstream timeout")

        adapter = _make_adapter(httpx.MockTransport(handler))
        with pytest.raises(TimeoutError):
            await adapter.fetch(_query("keyword=宁德时代"))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_non_json_body_maps_to_response_error(self) -> None:
        """非 JSON 响应体 → DataSourceResponseError(413)。"""
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, text="<html>challenge</html>")))
        with pytest.raises(DataSourceResponseError):
            await adapter.fetch(_query("keyword=宁德时代"))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_topsearch_non_list_rejected(self) -> None:
        """topSearch 响应非列表 → 413（结构校验）。"""
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(200, json={"unexpected": True})))
        with pytest.raises(DataSourceResponseError, match="topSearch"):
            await adapter.fetch(_query("keyword=宁德时代"))
        await adapter.close()

    @pytest.mark.asyncio
    async def test_announcements_non_list_rejected(self) -> None:
        """公告查询响应 announcements 非列表非 null → 413（结构校验——两段式 handler 仅公告段坏形态）。"""
        captured: list[httpx.Request] = []
        adapter = _make_adapter(_two_stage_handler(captured, ann_body={"announcements": "bad"}))
        with pytest.raises(DataSourceResponseError, match="announcements"):
            await adapter.fetch(_query("keyword=宁德时代"))
        assert len(captured) == 2  # 两段均已发出，坏形态在第二段响应侧暴露
        await adapter.close()

    @pytest.mark.asyncio
    async def test_invalid_query_rejected_before_any_request(self) -> None:
        """非法管道串 → 201 零请求消耗（输入前置校验语义——comtrade 同款）。"""
        adapter = _make_adapter()
        with pytest.raises(ValidationError):
            await adapter.fetch(_query("category=category_ndbg_szsh"))  # 缺 keyword
        await adapter.close()

    @pytest.mark.asyncio
    async def test_circuit_breaker_early_open(self) -> None:
        """熔断早期开启：threshold=2 注入后第三次 fetch 零 HTTP 快速失败（newsapi 范本——按 fetch 会话计数）。"""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(500, json={"error": "boom"})

        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=30.0, half_open_max_calls=1, name="test-cninfo")
        adapter = _make_adapter(httpx.MockTransport(handler), circuit_breaker=breaker)
        for _ in range(2):
            with pytest.raises(DataSourceUnavailableError):
                await adapter.fetch(_query("keyword=宁德时代"))
        calls_before = calls["n"]
        with pytest.raises(DataSourceUnavailableError):  # 熔断开启后的快速失败（零 HTTP 调用）
            await adapter.fetch(_query("keyword=宁德时代"))
        assert calls["n"] == calls_before
        assert breaker.state.value == "open"
        await adapter.close()


class TestMetadataAndConfig:
    def test_get_metadata_aligns_ssot(self) -> None:
        """get_metadata 对齐 SSOT 四值（required_fields 属声明面不在适配器侧断言——Task 5 定稿同款）。"""
        adapter = _make_adapter()
        meta = adapter.get_metadata()
        assert meta.name == "cninfo"
        assert meta.url == _CNINFO_URL
        assert meta.ttl_seconds == 604800
        assert meta.api_type.value == "rest_json"

    def test_adapter_implements_data_source_port(self) -> None:
        """适配器实现 DataSourcePort 协议。"""
        adapter = _make_adapter()
        assert isinstance(adapter, DataSourcePort)

    def test_from_env_invalid_timeout_rejected(self) -> None:
        """CNINFO_TIMEOUT 非数值 → ConfigurationError(101)（禁止 ValueError 透传）。"""
        import os

        old = os.environ.get("CNINFO_TIMEOUT")
        os.environ["CNINFO_TIMEOUT"] = "not-a-number"
        try:
            with pytest.raises(ConfigurationError, match="CNINFO_TIMEOUT"):
                CninfoConfig.from_env()
        finally:
            if old is None:
                os.environ.pop("CNINFO_TIMEOUT", None)
            else:
                os.environ["CNINFO_TIMEOUT"] = old

    def test_from_env_invalid_ttl_rejected(self) -> None:
        """CNINFO_TTL_SECONDS 非整数 → ConfigurationError(101)。"""
        import os

        old = os.environ.get("CNINFO_TTL_SECONDS")
        os.environ["CNINFO_TTL_SECONDS"] = "3.5"
        try:
            with pytest.raises(ConfigurationError, match="CNINFO_TTL_SECONDS"):
                CninfoConfig.from_env()
        finally:
            if old is None:
                os.environ.pop("CNINFO_TTL_SECONDS", None)
            else:
                os.environ["CNINFO_TTL_SECONDS"] = old

    def test_from_env_non_positive_rejected(self) -> None:
        """timeout/ttl 非正数 → ConfigurationError(101)。"""
        import os

        old = os.environ.get("CNINFO_TIMEOUT")
        os.environ["CNINFO_TIMEOUT"] = "0"
        try:
            with pytest.raises(ConfigurationError):
                CninfoConfig.from_env()
        finally:
            if old is None:
                os.environ.pop("CNINFO_TIMEOUT", None)
            else:
                os.environ["CNINFO_TIMEOUT"] = old

    @pytest.mark.asyncio
    async def test_health_check_probes_topsearch(self) -> None:
        """探活走 topSearch 最小查询（单次尝试——EDGAR R3 同款 max_attempts=1）。"""
        captured: list[httpx.Request] = []
        adapter = _make_adapter(_two_stage_handler(captured))
        assert await adapter.health_check() is True
        assert len(captured) == 1
        assert captured[0].url.path == "/new/information/topSearch/query"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_health_check_failure_returns_false(self) -> None:
        """探活失败返回 False（不抛——健康检查语义）。"""
        adapter = _make_adapter(httpx.MockTransport(lambda req: httpx.Response(500, json={"error": "boom"})))
        assert await adapter.health_check() is False
        await adapter.close()
