"""基础设施层 google-patents 数据源适配器（Story 4.1f Task 9 / D-09）

Google Patents Public Datasets——BigQuery `patents-public-data.patents.publications`
（IFI CLAIMS 维护，全球书目含 CN 99.96%）：

- 技术路线：**BigQuery REST 直连**（jobs.query + OAuth2 服务账号 JWT）而非
  google-cloud-bigquery SDK——pyjwt 经 redis 5.x 硬依赖链已在锁定依赖树（显式声明
  pyproject 见审查留项 Q1 台账），零新第三方依赖；完整复用
  `_http_helpers.request_json_with_resilience`
  （熔断/重试/异常映射全链——本 Story 硬约束天然满足）
- 认证：服务账号 JSON → RS256 JWT（scope=bigquery.readonly）→ OAuth2 token 端点
  （jwt-bearer grant）→ access_token 进程内缓存（过期提前 60s 刷新）；业务请求
  401 → 捕获 101 按 context.status_code 判别重取一次（对齐 EPO 模式）
- 配额：1 TiB/月（BigQuery 按 totalBytesProcessed 精确计费口径）——月窗口字节
  累计守卫（自然月一日 00:00 UTC 重置，now_fn 可注入），超限前置抛 412 零请求
  消耗；SQL 列裁剪（仅三列）+ 强制 LIMIT 控制扫描成本；探活扫描字节同样入账
- 检索式：管道串 `assignee=华为|cpc=Y02E|country=CN|year=2020-2026|keyword=battery`
  （至少一项条件——空条件 201 防全表扫描；year/country 形态前置校验 201；
  参数化查询 named parameters 防注入）
- schema 事实对齐（patents-public-data.patents.publications 真实类型）：
  assignee 为 REPEATED（ARRAY<STRING>）须 UNNEST 匹配、filing_date 为 INTEGER
  （YYYYMMDD）整数区间比较、publication_number 前缀即国家码（STARTS_WITH 字面
  前缀语义）

实现 DataSourcePort。容错：tenacity + CircuitBreaker（复用 _http_helpers 集中映射）。
安全：服务账号私钥不落 repr/日志/异常消息。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import jwt

from src.domain.exceptions import (
    ConfigurationError,
    DataSourceRateLimitError,
    DataSourceResponseError,
    ValidationError,
)
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)
from src.infrastructure.config.google_patents import GooglePatentsConfig
from src.infrastructure.external_services.datasources._http_helpers import request_json_with_resilience
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

_DATASET = "patents-public-data.patents.publications"
_TOKEN_SCOPE = "https://www.googleapis.com/auth/bigquery.readonly"
_TOKEN_EARLY_REFRESH = timedelta(seconds=60)  # 过期提前 60s 刷新（对齐 EPO）
_MONTHLY_QUOTA_BYTES = 1024**4  # 1 TiB/月（BigQuery 免费层——扫描字节口径）
_QUERY_LIMIT = 25  # 强制 LIMIT（对齐 EPO Range 首页 25 条）
_KNOWN_PIPELINE_KEYS = ("assignee", "cpc", "country", "year", "keyword")

# SQL 固定模板（字面量常量——值全部经 named parameters 传递，见 _build_sql）
_SQL_SELECT = "SELECT publication_number, assignee, filing_date FROM `patents-public-data.patents.publications`"
_SQL_ORDER = "ORDER BY filing_date DESC LIMIT 25"

# LIKE 谓词模板（REPEATED 列经 UNNEST 逐元素匹配——assignee 为 ARRAY<STRING>，标量
# LIKE 无函数签名必 400）。raw string：SQL 文本中 ESCAPE '\\' 两反斜杠字符经 BigQuery
# 词法解析为单反斜杠转义符，与 _escape_like 值侧转义（%/_/反斜杠）严格配对——
# 三通道（assignee/cpc/keyword）值转义与 ESCAPE 子句必须成对出现，禁止半套
_ASSIGNEE_PREDICATE = r"EXISTS(SELECT 1 FROM UNNEST(assignee) AS a WHERE a LIKE @assignee ESCAPE '\\')"
_CPC_PREDICATE = r"EXISTS(SELECT 1 FROM UNNEST(cpc) AS c WHERE c.code LIKE @cpc ESCAPE '\\')"
_KEYWORD_PREDICATE = r"EXISTS(SELECT 1 FROM UNNEST(abstract_localized) AS a WHERE a.text LIKE @keyword ESCAPE '\\')"

# 服务端 timeoutMs 相对 httpx client 超时的提前量（毫秒）——两层超时约束：httpx
# 先超时会触发 tenacity 对非幂等 jobs.query 的重试（每次重试各提交新 job 各自计费
# 扫描字节），故 timeoutMs 必须恒小于 client timeout（派生关系，禁独立配置）
_QUERY_TIMEOUT_HEADROOM_MS = 2000

_COUNTRY_PATTERN = re.compile(r"[A-Z]{2}")


def _escape_like(value: str) -> str:
    """转义 LIKE 通配符（反斜杠/%/_）——与谓词模板 ESCAPE '\\\\' 成对的值侧半边。

    用户值含 %/_ 时若不转义会意外全匹配（assignee=% 即匹配一切）；转义后经
    ESCAPE 子句还原为字面字符语义。
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _sign_jwt_rs256(header: dict[str, str], claims: dict[str, Any], private_key_pem: str) -> str:
    """RS256 签名 JWT（服务账号私钥——测试经 monkeypatch 替换，fake 私钥无法真签）。"""
    return jwt.encode(claims, private_key_pem, algorithm="RS256", headers=header)


def parse_patents_pipeline_query(raw: str) -> dict[str, str]:
    """解析专利检索管道串（输入前置校验——201 族）。

    Args:
        raw: 管道串（如 assignee=华为|cpc=Y02E|country=CN|year=2020-2026|keyword=battery）

    Returns:
        条件字典（仅含出现的键）

    Raises:
        ValidationError: 串为空（防全表扫描）、含未知参数键、year/country 形态非法
    """
    if not raw.strip():
        raise ValidationError(
            message=(
                "google-patents 检索式为空——至少一项条件（assignee/cpc/country/year/keyword）"
                "防止 BigQuery 全表扫描（按扫描字节计费）"
            ),
            context={"source_name": "google-patents", "field": "query", "value": ""},
        )
    parsed: dict[str, str] = {}
    for segment in raw.split("|"):
        segment = segment.strip()
        if not segment:
            continue
        if "=" not in segment:
            raise ValidationError(
                message=f"google-patents 管道串段格式非法（期望 key=value）: {segment[:50]}",
                context={"source_name": "google-patents", "field": "query", "value": segment[:50]},
            )
        key, _, value = segment.partition("=")
        if key not in _KNOWN_PIPELINE_KEYS:
            raise ValidationError(
                message=f"google-patents 管道串含未知参数 {key!r}（合法: {'/'.join(_KNOWN_PIPELINE_KEYS)}）",
                context={"source_name": "google-patents", "field": "query", "value": key},
            )
        parsed[key] = value
    _validate_conditions(parsed)
    if not parsed:
        raise ValidationError(
            message="google-patents 检索式无有效条件（防全表扫描）",
            context={"source_name": "google-patents", "field": "query", "value": raw[:100]},
        )
    return parsed


def _validate_conditions(parsed: dict[str, str]) -> None:
    """结构化条件的形态校验（201 前置——零请求消耗，先于令牌获取）。

    - year：YYYY 或 YYYY-YYYY（恰好 1-2 段、每段 4 位数字、起止有序）
    - country：两位大写字母国家码（GoogleSQL 字符串比较大小写敏感——小写/三位码
      静默空结果，前置拦截）
    """
    if "year" in parsed:
        parts = parsed["year"].split("-")
        if not 1 <= len(parts) <= 2 or not all(p.isdigit() and len(p) == 4 for p in parts):
            raise ValidationError(
                message=f"google-patents year 形态非法（期望 YYYY 或 YYYY-YYYY）: {parsed['year'][:20]}",
                context={"source_name": "google-patents", "field": "year", "value": parsed["year"][:20]},
            )
        if len(parts) == 2 and parts[0] > parts[1]:
            raise ValidationError(
                message=f"google-patents year 起止倒序（start <= end）: {parsed['year'][:20]}",
                context={"source_name": "google-patents", "field": "year", "value": parsed["year"][:20]},
            )
    if "country" in parsed and not _COUNTRY_PATTERN.fullmatch(parsed["country"]):
        raise ValidationError(
            message=f"google-patents country 形态非法（期望两位大写字母国家码如 CN/US）: {parsed['country'][:10]}",
            context={"source_name": "google-patents", "field": "country", "value": parsed["country"][:10]},
        )


class _GoogleTokenManager:
    """GCP 服务账号令牌管理器（RS256 JWT → OAuth2 token，进程内缓存）。

    令牌获取走 resilience helper（与业务请求共用 CircuitBreaker——单上游语义）。
    """

    def __init__(
        self,
        *,
        credentials_path: str,
        client: httpx.AsyncClient,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        if not credentials_path or not Path(credentials_path).is_file():
            raise ConfigurationError(
                message=(
                    f"google-patents 服务账号凭据文件不存在或未配置: {credentials_path!r}（GOOGLE_APPLICATION_CREDENTIALS）"
                ),
                context={"source_name": "google-patents", "field": "credentials_path"},
            )
        try:
            sa = json.loads(Path(credentials_path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # OSError=文件不可读；ValueError 覆盖 JSONDecodeError（非法 JSON）与
            # UnicodeDecodeError（非 UTF-8 编码）——凭据域故障统一映射 101（异常体系
            # 契约：库异常禁裸逃逸）；message 不回显文件内容（仅文件名）
            raise ConfigurationError(
                message=f"google-patents 服务账号凭据文件不可读或非合法 JSON: {Path(credentials_path).name}",
                context={"source_name": "google-patents", "field": "credentials_file"},
            ) from exc
        if not isinstance(sa, dict):
            raise ConfigurationError(
                message="google-patents 服务账号凭据 JSON 顶层须为对象（service account 形态）",
                context={"source_name": "google-patents", "field": "credentials_json"},
            )
        self._client_email = sa.get("client_email", "")
        self._private_key = sa.get("private_key", "")
        self._token_uri = sa.get("token_uri", "https://oauth2.googleapis.com/token")
        if not self._client_email or not self._private_key:
            raise ConfigurationError(
                message="google-patents 服务账号 JSON 缺少 client_email/private_key 字段",
                context={"source_name": "google-patents", "field": "credentials_json"},
            )
        self._client = client
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5, recovery_timeout=30.0, half_open_max_calls=1, name="data-source-google-patents"
        )
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
        """构造服务账号 JWT 并向 token 端点换取 access_token。"""
        now = self._now_fn()
        header = {"alg": "RS256", "typ": "JWT"}
        claims = {
            "iss": self._client_email,
            "scope": _TOKEN_SCOPE,
            "aud": self._token_uri,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=3600)).timestamp()),
        }
        try:
            assertion = _sign_jwt_rs256(header, claims, self._private_key)
        except jwt.PyJWTError as exc:
            # 私钥无效/已轮换（InvalidKeyError 等）——请求发出前的凭据域故障映射 101
            raise ConfigurationError(
                message="google-patents 服务账号私钥无效或已轮换（RS256 签名失败）",
                context={"source_name": "google-patents", "field": "private_key"},
            ) from exc
        data = await request_json_with_resilience(
            self._client,
            "POST",
            self._token_uri,
            source_name="google-patents",
            circuit_breaker=self._circuit_breaker,
            # RFC 7523 §2.1：grant_type/assertion 以 application/x-www-form-urlencoded
            # 置于请求体（assertion 为短时效签名凭证——禁入 URL query，代理/访问日志
            # 泄露面；helper form_data 通道承载）
            form_data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
            max_attempts=self._retry_max_attempts,
            min_wait=self._retry_min_wait,
            max_wait=self._retry_max_wait,
        )
        if not isinstance(data, dict) or "access_token" not in data:
            raise DataSourceResponseError(
                message="google-patents 令牌响应缺少 access_token 字段",
                context={"source_name": "google-patents", "actual_type": type(data).__name__},
            )
        expires_in = data.get("expires_in", 3600)
        if not isinstance(expires_in, (int, float)):
            expires_in = 3600
        self._token = str(data["access_token"])
        # 过期时刻用请求后时钟（对齐 EPO——重试退避期间令牌实际有效期不被高估）
        self._expires_at = self._now_fn() + timedelta(seconds=float(expires_in))
        return self._token


class MonthlyQuotaGuard:
    """google-patents 月配额守卫（1 TiB/月——BigQuery 扫描字节口径）。

    totalBytesProcessed 响应精确值事后累计（consume）+ 前置容量检查
    （ensure_capacity）零请求消耗；自然月一日 00:00 UTC 重置（now_fn 可注入）。
    守卫模式复用 EPO 周窗口设计（月窗口变体）。
    """

    _lock: asyncio.Lock = asyncio.Lock()  # 类变量（协程间共享——单例适配器语义）

    def __init__(
        self,
        *,
        quota_bytes_used: int = 0,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._used = quota_bytes_used
        self._month_start = self._current_month_start(self._now_fn())

    @staticmethod
    def _current_month_start(now: datetime) -> datetime:
        """当前自然月起点（当月一日 00:00 UTC）。"""
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    @property
    def used_bytes(self) -> int:
        """当前月窗口已用扫描字节数。"""
        return self._used

    async def ensure_capacity(self) -> None:
        """前置容量检查——累计值达到月配额时抛 412（消息含已用量与重置时间）。"""
        async with self._lock:
            self._rollover_if_new_month()
            if self._used >= _MONTHLY_QUOTA_BYTES:
                year, month = self._month_start.year, self._month_start.month
                next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
                reset_at = datetime(next_year, next_month, 1, tzinfo=UTC)
                raise DataSourceRateLimitError(
                    message=(
                        f"google-patents 月配额已耗尽（已用 {self._used} 字节 >= {_MONTHLY_QUOTA_BYTES} 字节/1TiB，"
                        f"重置时间 {reset_at.isoformat()}）——前置拦截，零请求消耗"
                    ),
                    context={"source_name": "google-patents", "used_bytes": self._used, "reset_at": reset_at.isoformat()},
                )

    async def consume(self, response_bytes: int) -> None:
        """查询扫描字节计入月配额（totalBytesProcessed 精确值）。"""
        async with self._lock:
            self._rollover_if_new_month()
            self._used += response_bytes

    def _rollover_if_new_month(self) -> None:
        """越过自然月一日 00:00 UTC 重置窗口（调用方须已持锁）。"""
        current = self._current_month_start(self._now_fn())
        if current > self._month_start:
            self._month_start = current
            self._used = 0


class GooglePatentsAdapter:
    """google-patents 数据源适配器（BigQuery REST 直连 + 服务账号令牌流 + 月配额守卫）"""

    def __init__(
        self,
        config: GooglePatentsConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
        now_fn: Callable[[], datetime] | None = None,
        quota_bytes_used: int = 0,
    ) -> None:
        """构造适配器（双门缺失构造期抛 101——fail-fast，D-09）。

        Args:
            config: 配置（含凭据路径与项目 ID 双门）
            client: 可注入 httpx 客户端（测试 MockTransport——无 base_url，绝对 URL 直连）
            circuit_breaker: 可注入熔断器
            retry_max_attempts: 重试次数上限
            retry_min_wait: 重试最小等待秒数（测试注入加速）
            retry_max_wait: 重试最大等待秒数
            now_fn: 时钟注入（守卫月窗口/令牌过期测试）
            quota_bytes_used: 月配额已用字节初始值（守卫可注入性）

        Raises:
            ConfigurationError: 双门任一缺失（config 不可为 None——BigQuery 无免凭据形态）
        """
        if config is None:
            raise ConfigurationError(
                message="google-patents 缺少配置（config 必填——GCP 服务账号凭据与项目 ID 双门）",
                context={"source_name": "google-patents", "field": "config"},
            )
        self._config = config
        self._client = client or httpx.AsyncClient(timeout=config.timeout)
        self._owns_client = client is None
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5, recovery_timeout=30.0, half_open_max_calls=1, name="data-source-google-patents"
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait
        self._token_manager = _GoogleTokenManager(
            credentials_path=config.credentials_path,
            client=self._client,
            circuit_breaker=self._circuit_breaker,
            retry_max_attempts=retry_max_attempts,
            retry_min_wait=retry_min_wait,
            retry_max_wait=retry_max_wait,
            now_fn=now_fn,
        )
        self._quota_guard = MonthlyQuotaGuard(quota_bytes_used=quota_bytes_used, now_fn=now_fn)
        self._query_url = f"{config.api_url.rstrip('/')}/bigquery/v2/projects/{config.project_id}/queries"

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据（required_fields 属声明面，适配器侧不填——4-1f 定稿）。"""
        return DataSourceRef(
            name="google-patents",
            url=self._config.api_url,
            ttl_seconds=self._config.ttl_seconds,
            api_type=DataSourceApiType.REST_JSON,
        )

    @property
    def quota_used_bytes(self) -> int:
        """当前月配额已用扫描字节（测试/运维观测）。"""
        return self._quota_guard.used_bytes

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """执行专利管道串检索（参数化 SQL + jobs.query REST）。

        Args:
            query: 检索请求（管道串如 assignee=华为|cpc=Y02E|country=CN）

        Returns:
            DataSourceResult（payload 为 patents 列表 JSON 字符串——
            publication_number/assignee/filing_date 三字段）

        Raises:
            ValidationError: 管道串空/未知参数（输入前置校验，零请求消耗）
            DataSourceRateLimitError: 月配额耗尽前置拦截 / HTTP 429
            ConfigurationError: 令牌端点或业务请求 401/403（凭证问题）
            DataSourceResponseError: 响应结构异常 / jobComplete=false
            DataSourceUnavailableError: 5xx/连接失败重试耗尽/熔断
            TimeoutError: 请求超时
        """
        conditions = parse_patents_pipeline_query(query.query)  # 201 前置校验
        await self._quota_guard.ensure_capacity()  # 412 前置拦截
        token = await self._token_manager.get_token()
        sql, query_params = self._build_sql(conditions)
        data = await self._request_query(token, self._build_query_body(sql, query_params, max_results=_QUERY_LIMIT))
        await self._quota_guard.consume(self._extract_bytes_processed(data))
        patents = self._extract_patents(data)
        now = datetime.now(UTC)
        source_ts = self._latest_filing_date(patents) or now
        return DataSourceResult(
            source_name="google-patents",
            payload=json.dumps({"patents": patents}, ensure_ascii=False),
            source_timestamp=source_ts,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=source_ts, ttl_seconds=self._config.ttl_seconds),
            confidence=0.9,  # Google/IFI CLAIMS 公共数据集（CN 完整性 SSRN caveat——口径段标注）
        )

    @staticmethod
    def _build_sql(conditions: dict[str, str]) -> tuple[str, list[dict[str, Any]]]:
        """构造参数化 SQL（列裁剪三列 + named parameters 防注入 + 强制 LIMIT）。

        成本控制（BigQuery 按扫描字节计费）：SELECT 仅三列（不 SELECT *，输出字段名
        与 required_fields 声明面契约一致——UNNEST 仅用于 WHERE 谓词，不改 SELECT
        输出）；WHERE 至少一项条件由管道串前置校验保证；LIMIT 强制 25。

        schema 事实（Q1-F1 修复）：
        - assignee 为 REPEATED（ARRAY<STRING>）——EXISTS+UNNEST 逐元素 LIKE
          （对齐 cpc/keyword 既有形态），标量 LIKE 无函数签名必 400
        - filing_date 为 INTEGER（YYYYMMDD）——整数闭区间边界（Python 侧算好传入，
          含首末日），DATE() 函数比较类型不匹配必 400
        - country 经 STARTS_WITH(publication_number, @country_code) 字面前缀匹配
          （publication_number 形如 "CN-1234567-A"，前两位即国家码）——参数值不带
          LIKE 通配符 %（STARTS_WITH 无通配符语义，带 % 恒空结果）
        """
        where_parts: list[str] = []
        params: list[dict[str, Any]] = []

        def add_param(name: str, value: str, template: str) -> None:
            where_parts.append(template)
            params.append({"name": name, "parameterType": {"type": "STRING"}, "parameterValue": {"value": value}})

        if "assignee" in conditions:
            add_param("assignee", f"%{_escape_like(conditions['assignee'])}%", _ASSIGNEE_PREDICATE)
        if "cpc" in conditions:
            add_param("cpc", f"%{_escape_like(conditions['cpc'])}%", _CPC_PREDICATE)
        if "country" in conditions:
            add_param("country_code", conditions["country"], "STARTS_WITH(publication_number, @country_code)")
        if "year" in conditions:
            # year=2020-2026 形态已在 parse 层校验（4 位数字/1-2 段/起止有序）
            parts = conditions["year"].split("-")
            start_year = int(parts[0])
            end_year = int(parts[1]) if len(parts) > 1 else start_year
            # filing_date 为 INTEGER（YYYYMMDD）——Python 侧算整数闭区间边界（含首末日）
            where_parts.append("filing_date BETWEEN @year_start AND @year_end")
            params.append(
                {
                    "name": "year_start",
                    "parameterType": {"type": "INT64"},
                    "parameterValue": {"value": str(start_year * 10000 + 101)},
                }
            )
            params.append(
                {
                    "name": "year_end",
                    "parameterType": {"type": "INT64"},
                    "parameterValue": {"value": str(end_year * 10000 + 1231)},
                }
            )
        if "keyword" in conditions:
            add_param("keyword", f"%{_escape_like(conditions['keyword'])}%", _KEYWORD_PREDICATE)

        # SQL 模板为字面量常量（SELECT/ORDER 固定片段）+ WHERE 模板部件 join——
        # 值一律走 named parameters（不进 SQL 文本）；常量拼接形态（bandit B608 对
        # f-string SQL 启发式会误报参数化模板——常量拼接消除静态分析歧义）
        sql = _SQL_SELECT + " WHERE " + " AND ".join(where_parts) + " " + _SQL_ORDER
        return sql, params

    def _build_query_body(self, sql: str, query_params: list[dict[str, Any]], *, max_results: int) -> dict[str, Any]:
        """构造 jobs.query 请求体（fetch 与探活共用）。

        两层超时约束（Q1-F5）：服务端 timeoutMs 从 config.timeout 派生（减去固定
        提前量）——恒小于 httpx client 超时，保证服务端先截断（jobComplete=false
        → 413 如实上报），杜绝 httpx 先超时触发 tenacity 对非幂等 jobs.query 的
        重试（每次重试各提交新 job 各自计费扫描字节）。
        """
        timeout_ms = max(1000, int(self._config.timeout * 1000) - _QUERY_TIMEOUT_HEADROOM_MS)
        return {
            "query": sql,
            "useLegacySql": False,
            "parameterMode": "NAMED",
            "queryParameters": query_params,
            "maxResults": max_results,
            "timeoutMs": timeout_ms,
        }

    async def _request_query(self, token: str, body: dict[str, Any]) -> Any:
        """执行 jobs.query REST（401 判别重取一次——对齐 EPO 模式）。"""
        try:
            return await request_json_with_resilience(
                self._client,
                "POST",
                self._query_url,
                source_name="google-patents",
                circuit_breaker=self._circuit_breaker,
                json_body=body,
                headers={"Authorization": f"Bearer {token}"},
                max_attempts=self._retry_max_attempts,
                min_wait=self._retry_min_wait,
                max_wait=self._retry_max_wait,
            )
        except ConfigurationError as exc:
            # 业务请求 401 = 令牌过期——强制刷新重发一次（401 走 on_ignored 不污染熔断）
            if exc.context.get("status_code") != 401:
                raise
            new_token = await self._token_manager.force_refresh()
            return await request_json_with_resilience(
                self._client,
                "POST",
                self._query_url,
                source_name="google-patents",
                circuit_breaker=self._circuit_breaker,
                json_body=body,
                headers={"Authorization": f"Bearer {new_token}"},
                max_attempts=self._retry_max_attempts,
                min_wait=self._retry_min_wait,
                max_wait=self._retry_max_wait,
            )

    @staticmethod
    def _extract_bytes_processed(data: Any) -> int:
        """提取 totalBytesProcessed（字符串数字形态——缺省 0 容错）。"""
        if not isinstance(data, dict):
            return 0
        raw = data.get("totalBytesProcessed", "0")
        try:
            return int(raw)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _extract_patents(data: Any) -> list[dict[str, Any]]:
        """rows（f.v 形态）→ patents 结构化（schema.fields 名映射）。

        结构校验：jobComplete 必须 true；rows 缺失视为空结果（0 行合法）。
        """
        if not isinstance(data, dict):
            raise DataSourceResponseError(
                message="google-patents 响应非对象形态",
                context={"source_name": "google-patents", "actual_type": type(data).__name__},
            )
        if data.get("jobComplete") is not True:
            raise DataSourceResponseError(
                message=(
                    "google-patents 查询在 timeoutMs 服务端窗口内未完成（jobComplete != true）——"
                    "建议缩小检索条件（追加 year/assignee 等过滤修剪扫描量）；"
                    "jobs.getQueryResults 轮询支持见 Story Defer 登记（Q1 台账）"
                ),
                context={"source_name": "google-patents", "field": "jobComplete"},
            )
        schema_fields = data.get("schema", {}).get("fields") if isinstance(data.get("schema"), dict) else None
        if not isinstance(schema_fields, list) or not all(isinstance(f, dict) for f in schema_fields):
            raise DataSourceResponseError(
                message="google-patents 响应 schema.fields 缺失或形态异常",
                context={"source_name": "google-patents", "field": "schema.fields"},
            )
        names = [f.get("name", "") for f in schema_fields]
        if not names:
            raise DataSourceResponseError(
                message="google-patents 响应缺少 schema.fields 字段名",
                context={"source_name": "google-patents"},
            )
        patents: list[dict[str, Any]] = []
        for row in data.get("rows", []) or []:
            if not isinstance(row, dict):
                raise DataSourceResponseError(
                    message="google-patents 响应 rows 元素非对象形态",
                    context={"source_name": "google-patents", "field": "rows"},
                )
            values = row.get("f", [])
            item: dict[str, Any] = {}
            for name, cell in zip(names, values, strict=False):
                if not isinstance(cell, dict):
                    raise DataSourceResponseError(
                        message=f"google-patents 响应 rows.f 单元格非对象形态（字段 {name}）",
                        context={"source_name": "google-patents", "field": name},
                    )
                item[name] = GooglePatentsAdapter._normalize_cell_value(name, cell.get("v"))
            patents.append(item)
        return patents

    @staticmethod
    def _normalize_cell_value(name: str, v: Any) -> Any:
        """cell 值归一（真实 REST 形态 → 声明面契约形态）。

        BigQuery REST v2 TableRow 编码（Q1-F1 对齐）：
        - REPEATED 列（assignee 为 ARRAY<STRING>）：v 是 [{"v": 元素}, ...] 列表——
          逐元素解包 join 为分号分隔字符串（声明面 assignee 为字符串形态）
        - filing_date（INTEGER YYYYMMDD）：8 位纯数字归一 ISO（与 EPO 契约形态一致）
        - NULL cell（v 为 None——键存在值 null，dict.get 缺省不生效）：归一空串
        """
        if isinstance(v, list):
            parts = [str(el.get("v", "")) if isinstance(el, dict) else str(el) for el in v]
            return "；".join(parts)
        if name == "filing_date" and isinstance(v, str) and len(v) == 8 and v.isdigit():
            return f"{v[:4]}-{v[4:6]}-{v[6:]}"
        return "" if v is None else v

    @staticmethod
    def _latest_filing_date(patents: list[dict[str, Any]]) -> datetime | None:
        """取专利列表中最晚申请日（无有效日期返回 None）。"""
        latest: datetime | None = None
        for item in patents:
            raw = str(item.get("filing_date", ""))
            if not raw:
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
        """探活（最小条件查询，单次尝试——LIMIT 1 控制扫描成本）。

        探活查询是真实计费消耗（BigQuery 按 totalBytesProcessed 计）——扫描字节
        同样计入月配额守卫（对齐 EPO 探活入账语义，R1-F12/Q1-F2：防配额旁路）。
        """
        try:
            await self._quota_guard.ensure_capacity()
            token = await self._token_manager.get_token()
            sql, params = self._build_sql({"assignee": "probe-health-check-zz"})
            data = await request_json_with_resilience(
                self._client,
                "POST",
                self._query_url,
                source_name="google-patents",
                circuit_breaker=self._circuit_breaker,
                json_body=self._build_query_body(sql.replace(f"LIMIT {_QUERY_LIMIT}", "LIMIT 1"), params, max_results=1),
                headers={"Authorization": f"Bearer {token}"},
                max_attempts=1,
                min_wait=self._retry_min_wait,
                max_wait=self._retry_max_wait,
            )
            await self._quota_guard.consume(self._extract_bytes_processed(data))
            return True
        except Exception as e:  # 探活失败不抛——健康检查语义
            logger.warning("GooglePatentsAdapter 探活失败: %s", type(e).__name__)
            return False

    async def close(self) -> None:
        """释放自持客户端（注入客户端由调用方管理）。"""
        if self._owns_client:
            await self._client.aclose()
