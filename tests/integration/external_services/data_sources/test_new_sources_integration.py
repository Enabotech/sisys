"""Story 4.1f — 三新源真实端点集成测试（EPO OPS / SEC EDGAR / UN Comtrade）

集成纪律（CLAUDE.md/Story 测试隔离约束）：
- SEC EDGAR / UN Comtrade 免 key 无条件真实连通（官方免费通道——预筛实测锚点）
- EPO OPS 依赖 OAuth2 Consumer Key/Secret（外部申请资产）——key 未就绪时
  pytest.skip() 动态跳过留痕（禁止写死 skip），key 到位后人工补跑（Story R7 锚点）
- 自包含：创建 → 执行 → 断言 → 关闭；无全局状态污染
- 不 mock 适配器（验证真实装配路径与真实端点行为）；限速语义由单测覆盖
"""

from __future__ import annotations

import os

import pytest

from src.domain.ports.data_source import DataSourceQuery

pytestmark = [pytest.mark.integration]  # 纯外网 HTTP 零 Redis 依赖（R2 修正误标）


@pytest.fixture
def epo_adapter():
    """EPO 适配器（key 门控 fixture——双凭据缺失时动态 skip 留痕）。"""
    consumer_key = os.getenv("EPO_OPS_CONSUMER_KEY", "")
    consumer_secret = os.getenv("EPO_OPS_CONSUMER_SECRET", "")
    if not consumer_key or not consumer_secret:
        pytest.skip("EPO_OPS_CONSUMER_KEY/SECRET 未配置（developers.epo.org 申请）——key 到位后补跑（Story R7 锚点）")
    from src.infrastructure.config.epo_ops import EpoOpsConfig
    from src.infrastructure.external_services.datasources.epo_ops_adapter import EpoOpsAdapter

    adapter = EpoOpsAdapter(config=EpoOpsConfig.from_env())
    return adapter


class TestSecEdgarRealEndpoint:
    """SEC EDGAR 免 key 真实端点（官方 Fair Access——Tesla CIK 预筛实测锚点）。"""

    @pytest.mark.asyncio
    async def test_search_mode_real_filings(self) -> None:
        """检索模式：q="market share" forms=10-K 真实返回财报列表（含 company/form/filed_at）。"""
        import json

        from src.infrastructure.external_services.datasources.sec_edgar_adapter import SecEdgarAdapter

        adapter = SecEdgarAdapter()
        try:
            result = await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query='"market share" forms=10-K'))
            payload = json.loads(result.payload)
            assert isinstance(payload.get("filings"), list) and payload["filings"], "真实端点应返回非空 filings"
            assert {"company", "form", "filed_at"} <= set(payload["filings"][0])
            assert result.confidence == 0.95
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_xbrl_mode_real_revenue_series(self) -> None:
        """XBRL 模式：xbrl:CIK0001318605:Revenues 返回 Tesla 营收时序（concept/unit/values）。"""
        import json

        from src.infrastructure.external_services.datasources.sec_edgar_adapter import SecEdgarAdapter

        adapter = SecEdgarAdapter()
        try:
            result = await adapter.fetch(DataSourceQuery(source_name="sec-edgar", query="xbrl:CIK0001318605:Revenues"))
            payload = json.loads(result.payload)
            assert payload.get("concept") == "Revenues", "companyconcept 应返回概念名"
            assert isinstance(payload.get("values"), list) and payload["values"], "营收时序应非空"
        finally:
            await adapter.close()


class TestComtradeRealEndpoint:
    """UN Comtrade preview 免 key 真实端点（中国整车出口——预筛实测 195 条锚点）。"""

    @pytest.mark.asyncio
    async def test_preview_real_trade_records(self) -> None:
        """preview 端点：reporter=156|cmd=8703 真实返回中国整车出口贸易记录。"""
        import json

        from src.infrastructure.external_services.datasources.comtrade_adapter import ComtradeAdapter

        adapter = ComtradeAdapter()
        try:
            result = await adapter.fetch(
                DataSourceQuery(source_name="comtrade", query="reporter=156|cmd=8703|flow=X|period=2024")
            )
            payload = json.loads(result.payload)
            assert isinstance(payload.get("records"), list), "preview 端点应返回 records 结构"
            if payload["records"]:  # 实时数据窗口可能为空——非空时校验字段形态
                assert {"cmd_code", "trade_value", "period"} <= set(payload["records"][0])
        finally:
            await adapter.close()


class TestEpoOpsRealEndpoint:
    """EPO OPS 真实端点（key 门控——OAuth2 令牌流 + pa= 中文申请人检索）。"""

    @pytest.mark.asyncio
    async def test_pa_chinese_applicant_real_patents(self, epo_adapter) -> None:
        """CQL 检索：pa="华为" 真实返回专利列表（含 title/applicant/filing_date）。"""
        import json

        try:
            result = await epo_adapter.fetch(DataSourceQuery(source_name="epo-ops", query='pa="华为"'))
            payload = json.loads(result.payload)
            assert isinstance(payload.get("patents"), list) and payload["patents"], "pa= 中文申请人检索应返回非空结果"
            assert {"title", "applicant", "filing_date"} <= set(payload["patents"][0])
        finally:
            # in-test 关闭（对齐同文件 EDGAR/Comtrade 先例——同步 fixture teardown 跨事件循环，
            # 4.1f 代码审查 R1-F9：get_event_loop 在 pytest-asyncio 关闭其 loop 后取到异属 loop）
            await epo_adapter.close()


class TestGooglePatentsRealEndpoint:
    """google-patents BigQuery 真实端点（GCP 双门门控——D-09 服务账号 JWT + 管道串检索）。

    GOOGLE_APPLICATION_CREDENTIALS（服务账号 JSON 路径）与 GOOGLE_PATENTS_PROJECT_ID
    任一缺失即动态 skip——GCP 项目需绑定 Billing（Sandbox 无 API 编程访问——D-09
    预筛勘误留痕）；免费层 1TiB/月查询字节。
    """

    @pytest.mark.asyncio
    async def test_pipeline_query_real_patents(self) -> None:
        """管道串检索：assignee=华为|country=CN 真实返回专利列表（publication_number/assignee/filing_date）。"""
        import json

        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        project_id = os.getenv("GOOGLE_PATENTS_PROJECT_ID", "")
        from pathlib import Path

        if not credentials_path or not Path(credentials_path).is_file() or not project_id:
            pytest.skip(
                "GOOGLE_APPLICATION_CREDENTIALS（凭据文件存在）+ GOOGLE_PATENTS_PROJECT_ID 未齐备"
                "（GCP 项目 + 服务账号——D-09 双门）——凭据到位后补跑（Story R7 锚点）"
            )
        from src.infrastructure.config.google_patents import GooglePatentsConfig
        from src.infrastructure.external_services.datasources.google_patents_adapter import GooglePatentsAdapter

        adapter = GooglePatentsAdapter(config=GooglePatentsConfig.from_env())
        try:
            result = await adapter.fetch(
                DataSourceQuery(source_name="google-patents", query="assignee=华为|country=CN|year=2020-2026")
            )
            payload = json.loads(result.payload)
            assert isinstance(payload.get("patents"), list) and payload["patents"], "assignee 检索应返回非空结果"
            assert {"publication_number", "assignee", "filing_date"} <= set(payload["patents"][0])
            # 计费字节入账锚点（Q2/A-8 观测闭环）：真实端点返回 totalBytesProcessed 时
            # 守卫必须入账 > 0——deprecated 字段若失效此断言即红（与单测 warning 呼应）
            assert adapter.quota_used_bytes > 0, "真实查询后月配额账应为正（totalBytesProcessed 入账）"
        finally:
            await adapter.close()
