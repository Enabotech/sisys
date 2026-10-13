"""基础设施层巨潮资讯数据源适配器（Story 4.1f Task 10——D-10 范围扩展）

巨潮资讯网（cninfo——证监会指定上市公司法定信息披露网站，免 key 无条件注册）：
- 两段式 POST 表单检索（EPO「先 token 后查询」同款两段范式）：
  ①topSearch 公司匹配（keyword → code/orgId/zwjc，A 股条目优先）→
  ②hisAnnouncement 公告查询（stock=code,orgId；column 沪深判定——code 6 开头 sse 其余 szse）
- query 规范：管道串 `keyword=宁德时代|category=category_ndbg_szsh|seDate=2026-01-01~2026-10-13`
  （keyword 必填缺失→201；category/seDate 可选直通；未知参数→201——comtrade 管道串范式同款）
- 输出：`{"company", "announcements": [{"title", "announcement_time"(ISO UTC), "pdf_url"(绝对)}]}`
  ——announcementTime 毫秒时间戳转换；adjunctUrl 相对路径拼 PDF 静态域绝对 URL（MVP 仅元数据，内容下载拆期归 B2 摄取桥）
- 空结果语义：topSearch 空数组短路（公告段零请求）/ announcements null → 空列表正常返回
  （EDGAR 空结果同语义——Skill §7 数据缺口话术承接）
- UA：浏览器兼容形态常量（cninfo 无官方 UA 格式义务——礼貌性标识，2026-10-13 实测通过）

实现 DataSourcePort。容错：tenacity + CircuitBreaker（复用 _http_helpers 集中映射）。
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from src.domain.exceptions import DataSourceResponseError, ValidationError
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)
from src.infrastructure.config.cninfo import CninfoConfig
from src.infrastructure.external_services.datasources._http_helpers import request_json_with_resilience
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

UA_HEADER = "Mozilla/5.0 (compatible; sisys-tools/1.0; +contact@sisys.local)"  # 浏览器兼容形态（2026-10-13 实测通过）
PDF_BASE_URL = "https://static.cninfo.com.cn"  # 公告 PDF 静态域（adjunctUrl 相对路径的绝对前缀）
_TOPSEARCH_ENDPOINT = "/new/information/topSearch/query"
_ANNOUNCEMENT_ENDPOINT = "/new/hisAnnouncement/query"
_PAGE_SIZE = "30"  # 公告单页条数（MVP 首页——分页能力拆期，口径段声明）
_MAX_COMPANY_CANDIDATES = "10"  # topSearch 候选数上限
_A_SHARE_CATEGORY = "A股"  # topSearch 条目的市场类别字段值（A 股优先匹配依据）
_QUERY_KEY_MAP: dict[str, str] = {"keyword": "keyword", "category": "category", "seDate": "seDate"}
_EPOCH_MS = 1000.0  # 毫秒时间戳 → 秒的换算因子


def _parse_pipeline_query(raw: str) -> dict[str, str]:
    """解析管道分隔参数串为 cninfo 检索参数（输入前置校验）。

    Args:
        raw: 管道串（如 keyword=宁德时代|category=category_ndbg_szsh|seDate=2026-01-01~2026-10-13）

    Returns:
        参数字典（keyword/category/seDate——category 与 seDate 缺省缺位）

    Raises:
        ValidationError: 串为空、缺必填的 keyword、段格式非法或含未知参数
    """
    if not raw.strip():
        raise ValidationError(
            message="cninfo 检索式为空（期望管道串如 keyword=宁德时代|category=category_ndbg_szsh）",
            context={"source_name": "cninfo", "field": "query", "value": raw[:100]},
        )
    params: dict[str, str] = {}
    for segment in raw.split("|"):
        segment = segment.strip()
        if not segment:
            continue
        if "=" not in segment:
            raise ValidationError(
                message=f"cninfo 管道串段格式非法（期望 key=value）: {segment[:50]}",
                context={"source_name": "cninfo", "field": "query", "value": segment[:50]},
            )
        key, _, value = segment.partition("=")
        if key not in _QUERY_KEY_MAP:
            raise ValidationError(
                message=f"cninfo 管道串含未知参数 {key!r}（合法: keyword/category/seDate）",
                context={"source_name": "cninfo", "field": "query", "value": key},
            )
        params[key] = value
    if not params.get("keyword"):
        raise ValidationError(
            message="cninfo 检索式缺少必填参数 keyword（公司名或证券代码，如 keyword=宁德时代）",
            context={"source_name": "cninfo", "field": "query", "value": raw[:100]},
        )
    return params


def _pick_a_share(candidates: list[Any]) -> dict[str, Any] | None:
    """从 topSearch 候选列表选取公司条目（A 股优先，无 A 股回退首条；空列表返回 None）。"""
    if not candidates:
        return None
    for entry in candidates:
        if isinstance(entry, dict) and entry.get("category") == _A_SHARE_CATEGORY:
            return entry
    first = candidates[0]
    if not isinstance(first, dict):
        raise DataSourceResponseError(
            message="cninfo topSearch 候选条目非对象",
            context={"source_name": "cninfo", "actual_type": type(first).__name__},
        )
    return first


class CninfoAdapter:
    """巨潮资讯数据源适配器（免 key + 两段式 POST 表单公告检索）"""

    def __init__(
        self,
        config: CninfoConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 4.0,
    ) -> None:
        """构造适配器。

        Args:
            config: 配置（可空——免 key 源，缺省 from_env 语义的类默认值）
            client: 可注入 httpx 客户端（测试 MockTransport）
            circuit_breaker: 可注入熔断器
            retry_max_attempts: 重试次数上限
            retry_min_wait: 重试最小等待秒数（测试注入加速）
            retry_max_wait: 重试最大等待秒数
        """
        self._config = config or CninfoConfig()
        self._client = client or httpx.AsyncClient(base_url=self._config.api_url, timeout=self._config.timeout)
        self._owns_client = client is None
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5, recovery_timeout=30.0, half_open_max_calls=1, name="data-source-cninfo"
        )
        self._retry_max_attempts = retry_max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait

    def get_metadata(self) -> DataSourceRef:
        """返回数据源引用元数据（required_fields 属声明面，适配器侧不填——Task 5 定稿同款）。"""
        return DataSourceRef(
            name="cninfo",
            url=self._config.api_url,
            ttl_seconds=self._config.ttl_seconds,
            api_type=DataSourceApiType.REST_JSON,
        )

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        """两段式公告检索（管道串解析 → topSearch 公司匹配 → hisAnnouncement 公告查询）。

        Args:
            query: 检索请求（管道串 keyword=公司名[|category=类别码][|seDate=起~止]）

        Returns:
            DataSourceResult（payload 为公告元数据 JSON 字符串）

        Raises:
            ValidationError: 管道串非法（输入前置校验，零请求消耗）
            DataSourceResponseError: 响应结构异常 / 非法 JSON
            DataSourceUnavailableError: 5xx/连接失败重试耗尽/熔断
            DataSourceRateLimitError: HTTP 429
            TimeoutError: 请求超时
        """
        params = _parse_pipeline_query(query.query)
        candidates = await self._fetch_top_search(params["keyword"])
        company = _pick_a_share(candidates)
        now = datetime.now(UTC)
        if company is None:
            # topSearch 空结果短路（公告段零请求）——空集合语义同 EDGAR，Skill §7 数据缺口话术承接
            return self._build_result({"company": "", "announcements": []}, now)
        announcements = await self._fetch_announcements(company, params)
        return self._build_result({"company": str(company.get("zwjc", "")), "announcements": announcements}, now)

    async def _fetch_top_search(self, keyword: str) -> list[Any]:
        """第一段：topSearch 公司匹配（keyword → 候选条目列表）。"""
        data = await self._request(_TOPSEARCH_ENDPOINT, form_data={"keyWord": keyword, "maxNum": _MAX_COMPANY_CANDIDATES})
        if not isinstance(data, list):
            raise DataSourceResponseError(
                message="cninfo topSearch 响应非列表（期望公司候选数组）",
                context={"source_name": "cninfo", "actual_type": type(data).__name__},
            )
        return data

    async def _fetch_announcements(self, company: dict[str, Any], params: dict[str, str]) -> list[dict[str, Any]]:
        """第二段：hisAnnouncement 公告查询（stock=code,orgId；column 沪深判定）。"""
        code = str(company.get("code", ""))
        org_id = str(company.get("orgId", ""))
        form: dict[str, str] = {
            "pageNum": "1",
            "pageSize": _PAGE_SIZE,
            "column": "sse" if code.startswith("6") else "szse",  # 沪深判定：6 开头沪市，其余深市
            "tabName": "fulltext",
            "stock": f"{code},{org_id}",
        }
        if params.get("category"):
            form["category"] = params["category"]
        if params.get("seDate"):
            form["seDate"] = params["seDate"]
        data = await self._request(_ANNOUNCEMENT_ENDPOINT, form_data=form)
        return self._extract_announcements(data)

    @staticmethod
    def _extract_announcements(data: Any) -> list[dict[str, Any]]:
        """公告列表提取（真实端点无结果时 announcements 为 null → 空列表；条目字段转换）。

        - announcementTitle → title（原文）
        - announcementTime（毫秒时间戳）→ announcement_time（ISO UTC）
        - adjunctUrl（相对路径）→ pdf_url（PDF 静态域绝对 URL）
        """
        announcements = data.get("announcements") if isinstance(data, dict) else None
        if announcements is None:
            return []
        if not isinstance(announcements, list):
            raise DataSourceResponseError(
                message="cninfo 公告响应 'announcements' 字段非列表",
                context={"source_name": "cninfo", "actual_type": type(announcements).__name__},
            )
        converted: list[dict[str, Any]] = []
        for entry in announcements:
            if not isinstance(entry, dict):
                raise DataSourceResponseError(
                    message="cninfo 公告条目非对象",
                    context={"source_name": "cninfo", "actual_type": type(entry).__name__},
                )
            converted.append(
                {
                    "title": str(entry.get("announcementTitle", "")),
                    "announcement_time": _epoch_ms_to_iso(entry.get("announcementTime")),
                    "pdf_url": f"{PDF_BASE_URL}/{str(entry.get('adjunctUrl', ''))}",
                }
            )
        return converted

    def _build_result(self, payload_obj: dict[str, Any], fetched_at: datetime) -> DataSourceResult:
        """构造 DataSourceResult（source_timestamp 取最新公告时间，空结果回落 fetched_at）。"""
        latest = max(
            (item["announcement_time"] for item in payload_obj["announcements"]),
            default="",
        )
        timestamp = datetime.fromisoformat(latest) if latest else fetched_at
        return DataSourceResult(
            source_name="cninfo",
            payload=json.dumps(payload_obj, ensure_ascii=False),
            source_timestamp=timestamp,
            fetched_at=fetched_at,
            freshness=DataFreshness(source_timestamp=timestamp, ttl_seconds=self._config.ttl_seconds),
            confidence=0.95,  # 证监会指定法定信息披露平台
        )

    async def _request(self, url: str, *, form_data: dict[str, str], max_attempts: int | None = None) -> Any:
        """经 resilience helper 执行 POST 表单请求（form_data 通道——Q1-F4 既有）。"""
        return await request_json_with_resilience(
            self._client,
            "POST",
            url,
            source_name="cninfo",
            circuit_breaker=self._circuit_breaker,
            form_data=form_data,
            headers={"User-Agent": UA_HEADER},
            max_attempts=max_attempts if max_attempts is not None else self._retry_max_attempts,
            min_wait=self._retry_min_wait,
            max_wait=self._retry_max_wait,
        )

    async def health_check(self) -> bool:
        """探活（topSearch 最小查询，单次尝试——EDGAR R3 同款 max_attempts=1）。"""
        try:
            await self._request(_TOPSEARCH_ENDPOINT, form_data={"keyWord": "probe", "maxNum": "1"}, max_attempts=1)
            return True
        except Exception as e:  # 探活失败不抛——健康检查语义
            logger.warning("CninfoAdapter 探活失败: %s", type(e).__name__)
            return False

    async def close(self) -> None:
        """释放自持客户端（注入客户端由调用方管理）。"""
        if self._owns_client:
            await self._client.aclose()


def _epoch_ms_to_iso(raw_ms: Any) -> str:
    """毫秒时间戳转 ISO UTC 字符串（非法/缺失值返回空串——条目级容错不整体失败）。

    Raises:
        DataSourceResponseError: 值存在但非数值（结构校验——非法形态显式暴露）
    """
    if raw_ms is None:
        return ""
    if isinstance(raw_ms, bool) or not isinstance(raw_ms, (int, float)):
        raise DataSourceResponseError(
            message=f"cninfo 公告时间戳非数值: {type(raw_ms).__name__}",
            context={"source_name": "cninfo", "field": "announcementTime"},
        )
    return datetime.fromtimestamp(raw_ms / _EPOCH_MS, tz=UTC).isoformat()


__all__ = ["CninfoAdapter", "PDF_BASE_URL", "UA_HEADER"]
