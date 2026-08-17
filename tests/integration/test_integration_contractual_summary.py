"""Story 3.6 契约化摘要生成集成测试

验证真实 SummaryGenerationService + 真实 LLM 客户端协作。
使用本地 aiohttp HTTP mock 服务器模拟 LLM API（参考 test_integration_llm_client.py），
验证 LitellmLLMClient 与 litellm 的完整 HTTP 交互链路，同时保证测试确定性。

Mock 原因：LLM API 是外部 SaaS 服务，有成本/限流/输出不确定性，
使用本地 HTTP 服务器模拟 API 端点，在保持可重复性的同时验证完整的 HTTP 交互链路。

L3VectorPort 使用 Mock（Qdrant 为重型基础设施依赖），
EmbeddingService 使用 Mock（外部 API）。

覆盖场景：
- 各视角摘要生成集成（financial/market/technical）
- LLM 调用失败异常包装
- 不支持的视角异常
- 跨文档摘要生成集成
- 摘要存储集成
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from aiohttp import web

from src.application.services.summary_generation_service import SummaryGenerationService
from src.domain.ports.embedding_service import EmbeddingServicePort
from src.domain.ports.l3_vector import L3VectorPort, SearchResult
from src.domain.ports.llm_client import LLMConfig
from src.infrastructure.external_services.embedding.circuit_breaker import CircuitBreaker
from src.infrastructure.external_services.llm.litellm_llm_client import LitellmLLMClient

# ===================================================================
# 本地 Mock LLM API HTTP 服务器
# ===================================================================


def _make_openai_response(
    content: str = "Hello, world!",
    finish_reason: str = "stop",
    model: str = "test-model",
) -> dict[str, Any]:
    """构建 OpenAI 兼容的 chat completion 非 streaming 响应"""
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": 1234567890,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
    }


class MockSummaryLLMHandler:
    """模拟 LLM API 的 HTTP 请求处理器（针对摘要生成场景）

    根据请求中的 system_prompt 视角返回对应的结构化 JSON 响应。
    """

    def __init__(self) -> None:
        self._default_response: dict[str, Any] = _make_openai_response()
        self._sequence: list[tuple[int, dict[str, Any] | None, str | None]] | None = None
        self._call_index: int = 0
        self.requests: list[dict[str, Any]] = []

    def set_success_financial(self) -> None:
        """设置服务器返回财务摘要 JSON"""
        content = json.dumps(
            {
                "summary_text": "公司2024年财务表现稳健，全年实现营收120亿元，同比增长15%。",
                "key_points": ["营收120亿元，同比增长15%", "净利润率稳定在20%"],
                "confidence_score": 0.9,
                "revenue_trend": "2024年营收120亿元，同比增长15%",
                "profit_analysis": "净利润率维持在20%左右",
                "risk_factors": ["市场竞争加剧"],
                "market_position": "市场份额35%，行业领先",
            },
            ensure_ascii=False,
        )
        self._default_response = _make_openai_response(content=content)
        self._sequence = None
        self._call_index = 0

    def set_success_market(self) -> None:
        """设置服务器返回市场摘要 JSON"""
        content = json.dumps(
            {
                "summary_text": "2024年企业级AI市场规模达1000亿元，年增长率12%。",
                "key_points": ["市场规模1000亿元", "竞争格局分散"],
                "confidence_score": 0.85,
                "market_size": "2024年市场规模达1000亿元",
                "competitive_landscape": "竞争格局分散，前五名占40%",
                "growth_drivers": ["技术升级", "政策支持"],
                "customer_insights": "客户满意度4.2/5",
            },
            ensure_ascii=False,
        )
        self._default_response = _make_openai_response(content=content)
        self._sequence = None
        self._call_index = 0

    def set_success_technical(self) -> None:
        """设置服务器返回技术摘要 JSON"""
        content = json.dumps(
            {
                "summary_text": "系统采用六边形架构，微服务部署，技术栈为Python/React。",
                "key_points": ["六边形架构", "微服务部署"],
                "confidence_score": 0.88,
                "technology_stack": "Python/React/PostgreSQL/Qdrant",
                "innovation_points": ["多Agent协作", "高保真溯源"],
                "technical_risks": ["数据安全合规"],
                "architecture_overview": "六边形架构，微服务部署",
            },
            ensure_ascii=False,
        )
        self._default_response = _make_openai_response(content=content)
        self._sequence = None
        self._call_index = 0

    def set_http_error(self, status: int = 500, body: str | None = None) -> None:
        """设置服务器返回 HTTP 错误"""
        self._default_response = {}
        self._sequence = [(status, None, body or '{"error": {"message": "server error"}}')]
        self._call_index = 0

    def _get_response(self) -> tuple[int, dict[str, Any] | None, str | None]:
        """获取当前调用的响应配置"""
        if self._sequence is not None:
            idx = min(self._call_index, len(self._sequence) - 1)
            return self._sequence[idx]
        return 200, self._default_response, None

    async def handle(self, request: web.Request) -> web.Response:
        """处理 POST /chat/completions 请求"""
        body = await request.json()
        self.requests.append(body)

        status, resp_body, error_body = self._get_response()
        self._call_index += 1

        if error_body is not None:
            return web.Response(
                status=status,
                body=error_body.encode("utf-8"),
                content_type="application/json",
            )

        return web.json_response(resp_body or {}, status=status)


# ===================================================================
# 辅助工厂函数
# ===================================================================


def _make_embedding_service() -> AsyncMock:
    """创建 Mock EmbeddingServicePort 实例"""
    mock = AsyncMock(spec=EmbeddingServicePort)
    mock.embed_documents.return_value = [[0.1] * 1024]
    mock.dimension = 1024
    return mock


def _make_l3_vector() -> AsyncMock:
    """创建 Mock L3VectorPort 实例"""
    mock = AsyncMock(spec=L3VectorPort)

    async def _upsert_points(collection: str, points: list[dict]) -> bool:
        return True

    async def _collection_exists(collection: str) -> bool:
        return True

    mock.upsert_points.side_effect = _upsert_points
    mock.collection_exists.side_effect = _collection_exists
    return mock


def _make_layered_retrieval() -> AsyncMock:
    """创建 Mock LayeredRetrievalPort 实例"""
    mock = AsyncMock()

    async def _search_top_down(
        query_text: str,
        target_level: str = "L4",
        collection: str = "documents",
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        if target_level in ("L1", "L2"):
            return [
                SearchResult(
                    id=f"summary-{target_level}",
                    score=0.85,
                    payload={
                        "summary_text": "已有摘要文本",
                        "perspective": "financial",
                        "index_level": target_level,
                    },
                )
            ]
        return []

    mock.search_top_down.side_effect = _search_top_down
    return mock


def _make_financial_search_results() -> list[SearchResult]:
    """构造财务场景检索结果"""
    return [
        SearchResult(
            id="doc-1",
            score=0.95,
            payload={
                "content": "公司2024年财报显示全年营收达120亿元，同比增长15%，"
                "净利润率维持在20%左右。核心业务市场份额持续扩大，达到35%。",
                "document_id": "doc-001",
                "index_level": "parent",
            },
        ),
    ]


# ===================================================================
# 全局清理：停止 LiteLLM 日志工作线程
# ===================================================================


@pytest.fixture(autouse=True)
async def _stop_litellm_worker() -> AsyncGenerator[None, None]:
    """每个测试结束后停止 LiteLLM 全局日志工作线程

    LiteLLM 的 LoggingWorker 是模块级单例，在首次调用 acompletion() 时
    创建后台 _worker_loop 协程。若不在测试间清理，该协程会在事件循环关闭后
    被 GC 时触发 RuntimeWarning（详见 test_integration_llm_client.py 注释）。
    """
    yield
    try:
        from litellm.litellm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER

        running = list(GLOBAL_LOGGING_WORKER._running_tasks)
        if running:
            await asyncio.gather(*running, return_exceptions=True)
        queue = getattr(GLOBAL_LOGGING_WORKER, "_queue", None)
        if queue is not None:
            for _ in range(200):
                try:
                    item = queue.get_nowait()
                    try:
                        await asyncio.wait_for(item["coroutine"], timeout=1.0)
                    except Exception:
                        pass
                    finally:
                        queue.task_done()
                except asyncio.QueueEmpty:
                    break
        await GLOBAL_LOGGING_WORKER.stop()
    except Exception:
        pass


# ===================================================================
# 集成测试
# ===================================================================


class TestSummaryGenerationIntegration:
    """契约化摘要生成集成测试"""

    @pytest.fixture
    async def mock_llm_server(
        self,
    ) -> AsyncGenerator[tuple[MockSummaryLLMHandler, int], None]:
        """启动本地 HTTP 服务器模拟 LLM API，返回 (handler, port)"""
        handler = MockSummaryLLMHandler()
        app = web.Application()
        app.router.add_post("/chat/completions", handler.handle)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()

        assert site._server is not None, "TCPSite._server should not be None after start()"
        # aiohttp AbstractServer 类型未声明 sockets 属性（运行时存在），
        # cast 到 Any 获取实际端口号
        port = cast(Any, site._server).sockets[0].getsockname()[1]

        yield handler, port

        await runner.cleanup()

    @pytest.fixture
    def llm_config(self, mock_llm_server: tuple[MockSummaryLLMHandler, int]) -> LLMConfig:
        """LLM 配置，指向本地模拟服务器"""
        _, port = mock_llm_server
        return LLMConfig(
            api_type="openai",
            model="test-model",
            endpoint=f"http://127.0.0.1:{port}",
            api_key="test-key",  # pragma: allowlist secret
            timeout=30.0,
        )

    @pytest.fixture
    async def real_client(self, llm_config: LLMConfig) -> AsyncGenerator[LitellmLLMClient, None]:
        """真实 LLM 客户端（带熔断器和重试配置）"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0, name="test-summary")
        client = LitellmLLMClient(
            config=llm_config,
            circuit_breaker=cb,
            retry_max_attempts=1,
            retry_min_wait=0.1,
            retry_max_wait=0.2,
        )
        yield client
        await client.close()

    @pytest.fixture
    def embedding_service(self) -> AsyncMock:
        """Mock EmbeddingServicePort"""
        return _make_embedding_service()

    @pytest.fixture
    def l3_vector(self) -> AsyncMock:
        """Mock L3VectorPort"""
        return _make_l3_vector()

    @pytest.fixture
    def layered_retrieval(self) -> AsyncMock:
        """Mock LayeredRetrievalPort"""
        return _make_layered_retrieval()

    @pytest.fixture
    def service(
        self,
        real_client: LitellmLLMClient,
        layered_retrieval: AsyncMock,
        embedding_service: AsyncMock,
        l3_vector: AsyncMock,
    ) -> SummaryGenerationService:
        """真实 SummaryGenerationService（注入真实 LLM + Mock 端口）"""
        return SummaryGenerationService(
            llm_client=real_client,
            layered_retrieval=layered_retrieval,
            embedding_service=embedding_service,
            l3_vector=l3_vector,
        )

    # --- AC-4: 各视角摘要生成 ---

    @pytest.mark.asyncio
    async def test_generate_financial_summary(
        self,
        service: SummaryGenerationService,
        mock_llm_server: tuple[MockSummaryLLMHandler, int],
    ) -> None:
        """财务视角摘要生成集成"""
        from src.application.services.summary_schemas import FinancialSummary

        handler, _ = mock_llm_server
        handler.set_success_financial()

        result = await service.generate_summary(
            query_text="分析公司2024年财务表现",
            search_results=_make_financial_search_results(),
            perspective="financial",
        )

        assert isinstance(result, FinancialSummary), f"期望 FinancialSummary，实际 {type(result)}"
        assert result.summary_text, "摘要文本不应为空"
        assert len(result.summary_text) >= 10, "摘要文本长度应 >= 10"
        assert len(result.key_points) >= 1, "关键要点应 >= 1"
        assert 0.0 <= result.confidence_score <= 1.0, "置信度应在 [0, 1] 范围"
        assert result.revenue_trend, "收入趋势不应为空"
        assert result.profit_analysis, "利润分析不应为空"
        assert result.risk_factors, "风险因素不应为空"
        assert result.market_position, "市场地位不应为空"

        # 验证 litellm 实际发送了 HTTP 请求到正确端点
        assert len(handler.requests) == 1
        req_body = handler.requests[0]
        assert req_body["model"] == "test-model"
        assert req_body["messages"][0]["role"] == "system"

    @pytest.mark.asyncio
    async def test_generate_market_summary(
        self,
        service: SummaryGenerationService,
        mock_llm_server: tuple[MockSummaryLLMHandler, int],
    ) -> None:
        """市场视角摘要生成集成"""
        from src.application.services.summary_schemas import MarketSummary

        handler, _ = mock_llm_server
        handler.set_success_market()

        result = await service.generate_summary(
            query_text="分析2024年企业级AI市场趋势",
            search_results=[
                SearchResult(
                    id="doc-2",
                    score=0.92,
                    payload={
                        "content": ("2024年企业级AI市场规模达1000亿元，年增长率12%。竞争格局分散，前五名合计占40%。"),
                        "document_id": "doc-002",
                        "index_level": "parent",
                    },
                ),
            ],
            perspective="market",
        )

        assert isinstance(result, MarketSummary)
        assert result.summary_text
        assert result.market_size
        assert result.competitive_landscape
        assert result.growth_drivers
        assert result.customer_insights

    @pytest.mark.asyncio
    async def test_generate_technical_summary(
        self,
        service: SummaryGenerationService,
        mock_llm_server: tuple[MockSummaryLLMHandler, int],
    ) -> None:
        """技术视角摘要生成集成"""
        from src.application.services.summary_schemas import TechnicalSummary

        handler, _ = mock_llm_server
        handler.set_success_technical()

        result = await service.generate_summary(
            query_text="分析系统技术架构",
            search_results=[
                SearchResult(
                    id="doc-3",
                    score=0.88,
                    payload={
                        "content": "系统采用六边形架构，微服务部署。技术栈为Python/React/PostgreSQL/Qdrant。",
                        "document_id": "doc-003",
                        "index_level": "parent",
                    },
                ),
            ],
            perspective="technical",
        )

        assert isinstance(result, TechnicalSummary)
        assert result.summary_text
        assert result.technology_stack
        assert result.innovation_points
        assert result.technical_risks
        assert result.architecture_overview

    # --- 异常路径 ---

    @pytest.mark.asyncio
    async def test_unsupported_perspective(
        self,
        service: SummaryGenerationService,
    ) -> None:
        """不支持的视角抛出 SummaryPerspectiveNotSupportedError"""
        from src.domain.exceptions import SummaryPerspectiveNotSupportedError

        with pytest.raises(SummaryPerspectiveNotSupportedError) as exc_info:
            await service.generate_summary(
                query_text="测试",
                search_results=[],
                perspective="unsupported_视角",
            )
        assert exc_info.value.code == "EXCEPTION_291"
        assert exc_info.value.context["perspective"] == "unsupported_视角"

    @pytest.mark.asyncio
    async def test_llm_api_error_wraps_to_summary_generation_error(
        self,
        real_client: LitellmLLMClient,
        service: SummaryGenerationService,
        mock_llm_server: tuple[MockSummaryLLMHandler, int],
    ) -> None:
        """LLM API 调用失败包装为 SummaryGenerationError"""
        from src.domain.exceptions import SummaryGenerationError

        handler, _ = mock_llm_server
        handler.set_http_error(500)

        with pytest.raises(SummaryGenerationError) as exc_info:
            await service.generate_summary(
                query_text="测试",
                search_results=[],
                perspective="financial",
            )
        assert exc_info.value.code == "EXCEPTION_290"

    # --- 跨文档摘要生成 ---

    @pytest.mark.asyncio
    async def test_cross_document_summary(
        self,
        service: SummaryGenerationService,
        mock_llm_server: tuple[MockSummaryLLMHandler, int],
        l3_vector: AsyncMock,
    ) -> None:
        """跨文档摘要生成集成"""
        from src.application.services.summary_schemas import FinancialSummary

        handler, _ = mock_llm_server
        handler.set_success_financial()

        result = await service.generate_summary(
            query_text="综合多个文档分析公司财务表现",
            search_results=_make_financial_search_results(),
            perspective="financial",
            cross_document=True,
        )

        assert isinstance(result, FinancialSummary)
        assert result.summary_text

        # 验证存储被调用（跨文档→ cross_document_summaries）
        l3_vector.upsert_points.assert_called_once()
        call_args = l3_vector.upsert_points.call_args[1]
        assert call_args["collection"] == "cross_document_summaries"

    # --- 摘要存储集成 ---

    @pytest.mark.asyncio
    async def test_summary_storage_side_effect(
        self,
        service: SummaryGenerationService,
        mock_llm_server: tuple[MockSummaryLLMHandler, int],
        l3_vector: AsyncMock,
    ) -> None:
        """单文档摘要存储到 document_summaries"""
        handler, _ = mock_llm_server
        handler.set_success_financial()

        result = await service.generate_summary(
            query_text="分析公司财务表现",
            search_results=_make_financial_search_results(),
            perspective="financial",
        )

        assert result is not None

        # 验证 upsert_points 被调用到 document_summaries
        l3_vector.upsert_points.assert_called_once()
        call_args = l3_vector.upsert_points.call_args[1]
        assert call_args["collection"] == "document_summaries"
        points = call_args["points"]
        assert len(points) == 1
        point = points[0]
        assert "summary-doc-001-financial" in point["id"]
        assert point["payload"]["perspective"] == "financial"
        assert point["payload"]["index_level"] == "L2"
