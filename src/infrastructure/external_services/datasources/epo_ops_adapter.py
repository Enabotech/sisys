"""基础设施层 EPO OPS 数据源适配器（Story 4.1f）

EPO Espacenet OPS（Open Patent Services，欧洲专利局官方检索）：
- 端点：POST /3.2/auth/accesstoken（OAuth2 client-credentials，Basic 凭证）+ GET /3.2/rest-services/published-data/search（CQL）
- 认证：令牌进程内缓存（过期提前 60s 刷新）；业务请求 401 → 捕获 101 按 context.status_code
  判别 → 强制刷新重发一次 → 仍失败上抛（禁止裸 client 绕行 helper）
- 配额：4 GB/周（官方 Fair Use）——进程内周窗口字节累计（周一 00:00 GMT 重置，
  now_fn 可注入），超限 fetch 前置抛 412（零请求消耗）；字节口径 = 响应 JSON 序列化字节数
- 响应：{"patents": [{title, applicant, filing_date}]}

实现 DataSourcePort。容错：tenacity + CircuitBreaker（令牌获取与业务请求共用同一熔断器）。
安全：缺凭据构造时抛 ConfigurationError(EXCEPTION_101)；凭据不出现在 URL/异常消息/日志。
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, NoReturn

import httpx

from src.domain.exceptions import (
    ConfigurationError,
    DataSourceRateLimitError,
    DataSourceResponseError,
)
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)
from src.infrastructure.config.epo_ops import EpoOpsConfig
from src.infrastructure.external_services.datasources._http_helpers import request_json_with_resilience
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

# 官方 Reference Guide v1.3.20 + Go/Python 官方生态客户端库同路径（4.1f 代码审查 R2-F1 修正——
# 原契约 /3.2/auth/token 与 R1-F1 检索路径同族契约错误；grant_type 传输形态已 R7 实测锚定：
# 2026-10-14 Key 到位后真实端点实证 query params → 400 / form body → 200，采用 form body）
_TOKEN_ENDPOINT = "/3.2/auth/accesstoken"
# R7 实测锚定（2026-10-14）：biblio 变体——纯 /search 端点仅返回 ops:publication-reference
# 文档引用（无 title/applicant/date），/search/biblio 才返回 exchange-documents/
# bibliographic-data 全量著录项
_SEARCH_ENDPOINT = "/3.2/rest-services/published-data/search/biblio"
_TOKEN_EARLY_REFRESH = timedelta(seconds=60)  # 过期提前 60s 刷新
_WEEKLY_QUOTA_BYTES = 4 * 1024**3  # 官方 Fair Use 免费层：4 GB/周


def _as_list(value: Any) -> list[Any]:
    """JSON 化 XML 单元素折叠归一化（dict|list 两态 → list）。

    EPO Accept: application/json 响应的列表字段在单元素时折叠为 dict
    （R7 实测锚定 2026-10-14）——解析层统一经本 helper 归一化。

    Args:
        value: 待归一化的字段值（dict/list/其他）

    Returns:
        list 形态（None → 空列表；dict → 单元素列表；list 原样）
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


class _EpoTokenManager:
    """EPO OAuth2 令牌管理器（进程内缓存 + 过期提前刷新 + 强制重取）。

    令牌获取走 resilience helper（与业务请求共用 CircuitBreaker——单上游服务语义）。
    """

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        config: EpoOpsConfig,
        circuit_breaker: CircuitBreaker,
        retry_max_attempts: int,
        retry_min_wait: float,
        retry_max_wait: float,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._config = config
        self._circuit_breaker = circuit_breaker
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._token: str | None = None
        self._expires_at: datetime | None = None

    async def get_token(self) -> str:
        """获取有效令牌（缓存命中直接返回；临近过期提前刷新）。"""
        now = self._now_fn()
        if self._token is not None and self._expires_at is not None and now < self._expires_at - _TOKEN_EARLY_REFRESH:
            return self._token
        return await self._fetch_token()

    async def force_refresh(self) -> str:
        """强制刷新令牌（业务请求 401 失效重取路径）。"""
        return await self._fetch_token()

    async def _fetch_token(self) -> str:
        """向令牌端点请求新令牌（Basic 凭证 + grant_type 走 form body，走 resilience helper）。

        grant_type 传输形态（R7 实测锚定 2026-10-14，Key 到位后真实端点实证）：
        query params 形态 → HTTP 400；form body（application/x-www-form-urlencoded）
        形态 → HTTP 200 + access_token——官方契约为 form body。
        """
        basic = base64.b64encode(f"{self._config.consumer_key}:{self._config.consumer_secret}".encode()).decode()
        data = await request_json_with_resilience(
            self._client,
            "POST",
            _TOKEN_ENDPOINT,
            source_name="epo-ops",
            circuit_breaker=self._circuit_breaker,
            form_data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {basic}"},
            max_attempts=self._retry_max_attempts,
            min_wait=self._retry_min_wait,
            max_wait=self._retry_max_wait,
        )
        if not isinstance(data, dict) or "access_token" not in data:
            raise DataSourceResponseError(
                message="EPO OPS 令牌响应缺少 access_token 字段",
                context={"source_name": "epo-ops", "actual_type": type(data).__name__},
            )
        expires_in = data.get("expires_in", 3600)
        if not isinstance(expires_in, (int, float)):
            expires_in = 3600
        self._token = str(data["access_token"])
        self._expires_at = self._now_fn() + timedelta(seconds=float(expires_in))
        return self._token


class _WeeklyQuotaGuard:
    """EPO 周配额守卫（4 GB/周——进程内字节累计，周一 00:00 GMT 重置）。

    前置拦截（ensure_capacity）零请求消耗；响应字节事后累计（consume）。
    Lock 为类变量（SINGLETON 单实例语义下的防御性存在——计数状态为实例级，跨实例并不互斥）。
    临界区纯同步（无 await）——单 loop 下
    acquire 恒走 fast path，锁为临界区未来演化出 await 时的防御性存在；CPython 3.10+
    真实竞争后锁绑定事件循环，跨 loop 复用须 per-loop 分锁（先例 aiodocker_sandbox_adapter）。
    """

    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(
        self,
        *,
        quota_bytes_used: int = 0,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._used = quota_bytes_used
        self._week_start = self._current_week_start(self._now_fn())

    @staticmethod
    def _current_week_start(now: datetime) -> datetime:
        """当前周窗口起点（最近一个周一 00:00 UTC）。"""
        days_since_monday = now.weekday()
        return (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)

    @property
    def used_bytes(self) -> int:
        """当前周窗口已用字节数。"""
        return self._used

    async def ensure_capacity(self) -> None:
        """前置容量检查——累计值达到周配额时抛 412（消息含已用量与重置时间）。"""
        async with self._lock:
            self._rollover_if_new_week()
            if self._used >= _WEEKLY_QUOTA_BYTES:
                reset_at = self._week_start + timedelta(weeks=1)
                raise _rate_limit_error(self._used, reset_at)

    async def consume(self, response_bytes: int) -> None:
        """响应字节计入周配额（响应 JSON 序列化字节数口径）。"""
        async with self._lock:
            self._rollover_if_new_week()
            self._used += response_bytes

    def _rollover_if_new_week(self) -> None:
        """越过周一 00:00 GMT 重置窗口（调用方须已持锁）。"""
        current = self._current_week_start(self._now_fn())
        if current > self._week_start:
            self._week_start = current
            self._used = 0


def _rate_limit_error(used_bytes: int, reset_at: datetime) -> Exception:
    """构造配额超限异常（412——与 HTTP 限流同族语义，零请求消耗）。"""
    return DataSourceRateLimitError(
        message=(
            f"EPO OPS 周配额已耗尽（已用 {used_bytes} 字节 >= {_WEEKLY_QUOTA_BYTES} 字节/4GB，"
            f"重置时间 {reset_at.isoformat()}）——前置拦截，零请求消耗"
        ),
        context={"source_name": "epo-ops", "used_bytes": used_bytes, "reset_at": reset_at.isoformat()},
    )


class EpoOpsAdapter:
    """EPO OPS 数据源适配器（OAuth2 + CQL 检索 + 周配额守卫）"""

    def __init__(
        self,
        config: EpoOpsConfig,
        *,
        client: httpx.AsyncClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
        now_fn: Callable[[], datetime] | None = None,
        quota_bytes_used: int = 0,
    ) -> None:
        """构造适配器（config 必填——空凭据构造期即抛 101，fail-fast）。

        Args:
            config: 配置（含双凭据）
            client: 可注入 httpx 客户端（测试 MockTransport）
            circuit_breaker: 可注入熔断器
            retry_max_attempts: 重试次数上限
            retry_min_wait: 重试最小等待秒数（测试注入加速）
            retry_max_wait: 重试最大等待秒数
            now_fn: 时钟注入（守卫周窗口/令牌过期测试）
            quota_bytes_used: 周配额已用字节初始值（守卫可注入性）

        Raises:
            ConfigurationError: Consumer Key/Secret 缺失时
        """
        if not config.consumer_key or not config.consumer_secret:
            raise ConfigurationError(
                message="EPO OPS 缺少 OAuth2 凭据（请配置环境变量 EPO_OPS_CONSUMER_KEY / EPO_OPS_CONSUMER_SECRET）",
                context={"source_name": "epo-ops", "field": "consumer_key"},
            )
        self._config = config
        self._client = client or httpx.AsyncClient(base_url=config.api_url, timeout=config.timeout)
        self._owns_client = client is None
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5, recovery_timeout=30.0, half_open_max_calls=1, name="data-source-epo-ops"
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait
        self._token_manager = _EpoTokenManager(
            client=self._client,
            config=config,
            circuit_breaker=self._circuit_breaker,
            retry_max_attempts=retry_max_attempts,
            retry_min_wait=retry_min_wait,
            retry_max_wait=retry_max_wait,
            now_fn=now_fn,
        )
        self._quota_guard = _WeeklyQuotaGuard(quota_bytes_used=quota_bytes_used, now_fn=now_fn)

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据（required_fields 属声明面，适配器侧不填——Task 5 定稿）。"""
        return DataSourceRef(
            name="epo-ops",
            url=self._config.api_url,
            ttl_seconds=self._config.ttl_seconds,
            api_type=DataSourceApiType.REST_JSON,
        )

    @property
    def quota_used_bytes(self) -> int:
        """当前周配额已用字节（测试/运维观测）。"""
        return self._quota_guard.used_bytes

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """执行 CQL 检索（query 直通 q 参数——结构化检索语法非自然语言）。

        Args:
            query: 检索请求（query 为 CQL 表达式，如 pa="华为" and ti="battery"）

        Returns:
            DataSourceResult（payload 为 patents 列表 JSON 字符串）

        Raises:
            DataSourceRateLimitError: 周配额耗尽前置拦截 / HTTP 429
            ConfigurationError: 令牌端点或业务请求 401/403（凭证问题）
            DataSourceResponseError: 响应结构异常 / 非法 JSON
            DataSourceUnavailableError: 5xx/连接失败重试耗尽/熔断
            TimeoutError: 请求超时
        """
        await self._quota_guard.ensure_capacity()
        token = await self._token_manager.get_token()
        data = await self._request_search(token, query.query)
        # 字节口径 = 响应 JSON 序列化字节数（helper 只返回解析后 JSON，序列化近似是唯一兼容口径）；
        # consume 先于 extract——结构校验 413 路径字节同样入账（上游 Fair Use 已真实消耗，R1-F12）
        await self._quota_guard.consume(len(json.dumps(data).encode()))
        items = self._extract_patents(data)
        now = datetime.now(UTC)
        source_ts = self._latest_filing_date(items) or now
        return DataSourceResult(
            source_name="epo-ops",
            payload=json.dumps({"patents": items}, ensure_ascii=False),
            source_timestamp=source_ts,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=source_ts, ttl_seconds=self._config.ttl_seconds),
            confidence=0.9,  # 官方专利局权威数据
        )

    async def _request_search(self, token: str, cql: str) -> Any:
        """执行检索请求（401 令牌失效捕获 101 按 status_code 判别重取一次）。"""
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Range": "1-25",  # Range 头分页（首页 25 条——EOPS 官方分页机制）
        }
        try:
            return await request_json_with_resilience(
                self._client,
                "GET",
                _SEARCH_ENDPOINT,
                source_name="epo-ops",
                circuit_breaker=self._circuit_breaker,
                params={"q": cql},
                headers=headers,
                max_attempts=self._retry_max_attempts,
                min_wait=self._retry_min_wait,
                max_wait=self._retry_max_wait,
            )
        except ConfigurationError as exc:
            # 业务请求 401 = 令牌过期（区别于 403 凭证拒绝）——强制刷新重发一次，
            # 仍失败则上抛 101。禁止为看状态码绕开 helper 用裸 client（401 走
            # on_ignored 不污染熔断统计）
            if exc.context.get("status_code") != 401:
                raise
            new_token = await self._token_manager.force_refresh()
            return await request_json_with_resilience(
                self._client,
                "GET",
                _SEARCH_ENDPOINT,
                source_name="epo-ops",
                circuit_breaker=self._circuit_breaker,
                params={"q": cql},
                headers={**headers, "Authorization": f"Bearer {new_token}"},
                max_attempts=self._retry_max_attempts,
                min_wait=self._retry_min_wait,
                max_wait=self._retry_max_wait,
            )

    def _extract_patents(self, data: Any) -> list[dict[str, Any]]:
        """真实响应结构解析（R7 实测锚定 2026-10-14，search/biblio 端点）。

        结构链：ops:world-patent-data → ops:biblio-search → ops:search-result →
        exchange-documents（列表元素为 {exchange-document: {...}} 包装）→
        bibliographic-data（invention-title/parties.applicants/
        application-reference.document-id）。JSON 化 XML 存在单元素 dict 折叠
        （exchange-document/applicant/invention-title 均可能 dict|list 两态）——
        统一经 _as_list 归一化。缺失任一结构层 → 413。

        Args:
            data: 解析后的响应 JSON

        Returns:
            [{"title", "applicant", "filing_date"}]（filing_date 已归一化 ISO 日期）

        Raises:
            DataSourceResponseError: 响应结构缺失真实契约层（EXCEPTION_413）
        """

        def _fail(missing_layer: str, actual: Any) -> NoReturn:
            raise DataSourceResponseError(
                message=f"EPO OPS 响应缺少 '{missing_layer}' 结构层（真实契约锚定）",
                context={"source_name": "epo-ops", "missing_layer": missing_layer, "actual_type": type(actual).__name__},
            )

        if not isinstance(data, dict):
            _fail("ops:world-patent-data", data)
        world = data.get("ops:world-patent-data")
        if not isinstance(world, dict):
            _fail("ops:world-patent-data", data)
        biblio_search = world.get("ops:biblio-search")
        if not isinstance(biblio_search, dict):
            _fail("ops:biblio-search", world)
        search_result = biblio_search.get("ops:search-result")
        if not isinstance(search_result, dict):
            _fail("ops:search-result", biblio_search)
        documents_wrapper = search_result.get("exchange-documents")
        if documents_wrapper is None:
            _fail("exchange-documents", search_result)

        patents: list[dict[str, Any]] = []
        for wrapper in _as_list(documents_wrapper):
            if not isinstance(wrapper, dict):
                continue
            for document in _as_list(wrapper.get("exchange-document", wrapper)):
                if isinstance(document, dict):
                    parsed = self._parse_biblio_document(document)
                    if parsed is not None:
                        patents.append(parsed)
        return patents

    @staticmethod
    def _parse_biblio_document(document: dict[str, Any]) -> dict[str, Any] | None:
        """单条 exchange-document → 三字段契约输出（title/applicant/filing_date）。

        无 bibliographic-data 的文档返回 None（调用方跳过）——静默产出
        {"title": "", "applicant": "", "filing_date": ""} 空记录会掩盖上游
        契约漂移（D2 清偿：跳过优于垃圾行，整层缺失仍由 _fail 报 413）。

        Returns:
            三字段契约字典；文档缺 bibliographic-data 时为 None（跳过）
        """

        def _text(value: Any) -> str:
            """提取 JSON 化 XML 文本（{$: "..."} 或 str；列表取首元素）。"""
            if isinstance(value, dict):
                return str(value.get("$", ""))
            if isinstance(value, list) and value:
                return _text(value[0])
            return value if isinstance(value, str) else ""

        biblio = document.get("bibliographic-data")
        if not isinstance(biblio, dict):
            return None

        # title：invention-title（dict|list 两态）
        title = _text(biblio.get("invention-title"))

        # applicant：parties.applicants.applicant[0].applicant-name.name
        parties = biblio.get("parties")
        applicant = ""
        if isinstance(parties, dict):
            applicants_holder = parties.get("applicants")
            if isinstance(applicants_holder, dict):
                applicants = _as_list(applicants_holder.get("applicant"))
                if applicants and isinstance(applicants[0], dict):
                    name = applicants[0].get("applicant-name")
                    if isinstance(name, dict):
                        applicant = _text(name.get("name"))

        # filing_date：application-reference.document-id 中 @document-id-type=docdb 的 date
        # （YYYYMMDD → ISO YYYY-MM-DD，供 _latest_filing_date 的 fromisoformat 消费）
        filing_date = ""
        app_ref = biblio.get("application-reference")
        if isinstance(app_ref, dict):
            for doc_id in _as_list(app_ref.get("document-id")):
                if isinstance(doc_id, dict) and doc_id.get("@document-id-type") == "docdb":
                    raw = _text(doc_id.get("date"))
                    if len(raw) == 8 and raw.isdigit():
                        filing_date = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
                    break

        return {"title": title, "applicant": applicant, "filing_date": filing_date}

    @staticmethod
    def _latest_filing_date(items: list[dict[str, Any]]) -> datetime | None:
        """取专利列表中最晚申请日（无有效日期返回 None）。"""
        latest: datetime | None = None
        for item in items:
            raw = item.get("filing_date")
            if not isinstance(raw, str) or not raw:
                continue
            try:
                ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            ts = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)
            if latest is None or ts > latest:
                latest = ts
        return latest

    async def health_check(self) -> bool:
        """探活（最小 CQL 查询，单次尝试——响应字节同样入账配额，探活是真实消耗）。"""
        try:
            await self._quota_guard.ensure_capacity()
            token = await self._token_manager.get_token()
            data = await request_json_with_resilience(
                self._client,
                "GET",
                _SEARCH_ENDPOINT,
                source_name="epo-ops",
                circuit_breaker=self._circuit_breaker,
                params={"q": 'ti="probe"'},
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "Range": "1-1"},
                max_attempts=1,
                min_wait=self._retry_min_wait,
                max_wait=self._retry_max_wait,
            )
            await self._quota_guard.consume(len(json.dumps(data).encode()))
            return True
        except Exception as e:  # 探活失败不抛——健康检查语义
            logger.warning("EpoOpsAdapter 探活失败: %s", type(e).__name__)
            return False

    async def close(self) -> None:
        """释放自持客户端（注入客户端由调用方管理）。"""
        if self._owns_client:
            await self._client.aclose()


__all__ = ["EpoOpsAdapter"]
