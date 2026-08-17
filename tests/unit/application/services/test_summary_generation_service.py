"""Story 3.6 摘要生成应用服务单元测试

验证 SummaryGenerationService 的多视角生成、LLM 调用、Schema 验证、异常处理。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.summary_generation_service import SummaryGenerationService
from src.application.services.summary_schemas import (
    FinancialSummary,
    MarketSummary,
    TechnicalSummary,
)
from src.domain.exceptions import (
    SummaryGenerationError,
    SummaryPerspectiveNotSupportedError,
)
from src.domain.ports.l3_vector import SearchResult

# ===================================================================
# Mock 工厂函数
# ===================================================================


def _make_llm_client() -> AsyncMock:
    """创建 Mock LLMClientPort 实例"""
    mock = AsyncMock()

    async def _structured_generate(prompt, response_schema, config=None, system_prompt=None):
        """返回模拟的 Schema 实例"""
        instance = MagicMock(spec=response_schema)
        instance.summary_text = "模拟摘要文本，用于测试摘要生成服务的结构化输出能力。"
        instance.key_points = ["要点一", "要点二"]
        instance.confidence_score = 0.85

        if response_schema is FinancialSummary:
            instance.revenue_trend = "收入增长15%"
            instance.profit_analysis = "利润率20%"
            instance.risk_factors = ["市场竞争"]
            instance.market_position = "市场领先者"
        elif response_schema is MarketSummary:
            instance.market_size = "1000亿"
            instance.competitive_landscape = "竞争分散"
            instance.growth_drivers = ["技术升级"]
            instance.customer_insights = "满意度4.2"
        elif response_schema is TechnicalSummary:
            instance.technology_stack = "Python"
            instance.innovation_points = ["多Agent"]
            instance.technical_risks = ["安全风险"]
            instance.architecture_overview = "六边形架构"

        return instance

    mock.structured_generate.side_effect = _structured_generate
    return mock


def _make_layered_retrieval() -> AsyncMock:
    """创建 Mock LayeredRetrievalPort 实例"""
    mock = AsyncMock()

    async def _search_top_down(
        query_text, target_level="L4", collection="documents", limit=10, tenant_id=None, filter_payload=None
    ):
        if target_level in ("L1", "L2"):
            return [
                SearchResult(
                    id="summary-1",
                    score=0.85,
                    payload={
                        "summary_text": "已有摘要",
                        "perspective": "financial",
                        "index_level": target_level,
                    },
                )
            ]
        return []

    mock.search_top_down.side_effect = _search_top_down
    return mock


def _make_embedding_service() -> AsyncMock:
    """创建 Mock EmbeddingServicePort 实例"""
    mock = AsyncMock()
    mock.embed_documents.return_value = [[0.1] * 1024]
    mock.dimension = 1024
    return mock


def _make_l3_vector() -> AsyncMock:
    """创建 Mock L3VectorPort 实例"""
    mock = AsyncMock()

    async def _upsert_points(collection, points):
        return True

    async def _collection_exists(collection):
        return True

    mock.upsert_points.side_effect = _upsert_points
    mock.collection_exists.side_effect = _collection_exists
    return mock


def _make_search_results() -> list[SearchResult]:
    """创建 Mock 检索结果"""
    return [
        SearchResult(
            id="doc-1",
            score=0.95,
            payload={
                "content": "这是文档内容，包含财务数据和分析结果。",
                "document_id": "doc-001",
                "index_level": "parent",
            },
        ),
        SearchResult(
            id="doc-2",
            score=0.85,
            payload={
                "content": "这是另一个文档内容，包含市场分析数据。",
                "document_id": "doc-002",
                "index_level": "parent",
            },
        ),
    ]


@pytest.fixture
def service() -> SummaryGenerationService:
    """创建 SummaryGenerationService 实例"""
    return SummaryGenerationService(
        llm_client=_make_llm_client(),
        layered_retrieval=_make_layered_retrieval(),
        embedding_service=_make_embedding_service(),
        l3_vector=_make_l3_vector(),
    )


# ===================================================================
# 测试类
# ===================================================================


class TestGenerateSummary:
    """generate_summary 核心功能验证"""

    @pytest.mark.asyncio
    async def test_generate_financial_summary(self, service: SummaryGenerationService) -> None:
        """生成 FinancialSummary 成功"""
        result = await service.generate_summary(
            query_text="公司财务分析",
            search_results=_make_search_results(),
            perspective="financial",
        )
        assert result is not None
        assert hasattr(result, "summary_text")
        assert hasattr(result, "revenue_trend")
        assert hasattr(result, "profit_analysis")
        assert hasattr(result, "risk_factors")
        assert hasattr(result, "market_position")

    @pytest.mark.asyncio
    async def test_generate_market_summary(self, service: SummaryGenerationService) -> None:
        """生成 MarketSummary 成功"""
        result = await service.generate_summary(
            query_text="市场分析",
            search_results=_make_search_results(),
            perspective="market",
        )
        assert result is not None
        assert hasattr(result, "market_size")
        assert hasattr(result, "competitive_landscape")
        assert hasattr(result, "growth_drivers")
        assert hasattr(result, "customer_insights")

    @pytest.mark.asyncio
    async def test_generate_technical_summary(self, service: SummaryGenerationService) -> None:
        """生成 TechnicalSummary 成功"""
        result = await service.generate_summary(
            query_text="技术架构分析",
            search_results=_make_search_results(),
            perspective="technical",
        )
        assert result is not None
        assert hasattr(result, "technology_stack")
        assert hasattr(result, "innovation_points")
        assert hasattr(result, "technical_risks")
        assert hasattr(result, "architecture_overview")

    @pytest.mark.asyncio
    async def test_unsupported_perspective_raises_error(self, service: SummaryGenerationService) -> None:
        """不支持的视角抛出 SummaryPerspectiveNotSupportedError"""
        with pytest.raises(SummaryPerspectiveNotSupportedError) as exc_info:
            await service.generate_summary(
                query_text="测试",
                search_results=_make_search_results(),
                perspective="unsupported",
            )
        assert exc_info.value.code == "EXCEPTION_291"
        assert exc_info.value.context["perspective"] == "unsupported"

    @pytest.mark.asyncio
    async def test_llm_api_error_raises_summary_generation_error(self, service: SummaryGenerationService) -> None:
        """LLM API 调用失败抛出 SummaryGenerationError"""
        # 替换 Mock，让 LLM 调用失败
        from src.domain.exceptions.llm_exceptions import LLMAPIError

        mock_llm = _make_llm_client()
        mock_llm.structured_generate.side_effect = LLMAPIError(
            message="LLM API 不可用",
            cause=Exception("API 返回 500"),
        )
        service._llm_client = mock_llm

        with pytest.raises(SummaryGenerationError) as exc_info:
            await service.generate_summary(
                query_text="测试",
                search_results=_make_search_results(),
                perspective="financial",
            )
        assert exc_info.value.code == "EXCEPTION_290"
        assert "financial" in exc_info.value.context.get("perspective", "")

    @pytest.mark.asyncio
    async def test_llm_response_error_raises_summary_generation_error(self, service: SummaryGenerationService) -> None:
        """LLM 响应解析失败抛出 SummaryGenerationError"""
        from src.domain.exceptions.llm_exceptions import LLMResponseError

        mock_llm = _make_llm_client()
        mock_llm.structured_generate.side_effect = LLMResponseError(
            message="响应解析失败，Schema 验证未通过",
            cause=Exception("Invalid response format"),
        )
        service._llm_client = mock_llm

        with pytest.raises(SummaryGenerationError):
            await service.generate_summary(
                query_text="测试",
                search_results=_make_search_results(),
                perspective="financial",
            )

    @pytest.mark.asyncio
    async def test_llm_config_error_passthrough(self, service: SummaryGenerationService) -> None:
        """LLM 配置错误透传不包装"""
        from src.domain.exceptions.llm_exceptions import LLMConfigError

        mock_llm = _make_llm_client()
        mock_llm.structured_generate.side_effect = LLMConfigError(
            message="LLM 配置错误",
            cause=Exception("Missing API key"),
        )
        service._llm_client = mock_llm

        with pytest.raises(LLMConfigError):
            await service.generate_summary(
                query_text="测试",
                search_results=_make_search_results(),
                perspective="financial",
            )

    @pytest.mark.asyncio
    async def test_empty_search_results(self, service: SummaryGenerationService) -> None:
        """空检索结果仍然可以生成摘要（以查询文本为主）"""
        result = await service.generate_summary(
            query_text="测试查询",
            search_results=[],
            perspective="financial",
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_cross_document_summary(self, service: SummaryGenerationService) -> None:
        """跨文档摘要模式生成成功"""
        result = await service.generate_summary(
            query_text="跨文档分析",
            search_results=[],
            perspective="financial",
            cross_document=True,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_llm_called_with_correct_prompt(self, service: SummaryGenerationService) -> None:
        """LLM 被正确调用，包含 System Prompt 和 User Prompt"""
        mock_llm = _make_llm_client()
        service._llm_client = mock_llm

        await service.generate_summary(
            query_text="测试",
            search_results=_make_search_results(),
            perspective="financial",
        )

        mock_llm.structured_generate.assert_called_once()
        call_kwargs = mock_llm.structured_generate.call_args[1]
        assert "prompt" in call_kwargs
        assert "system_prompt" in call_kwargs
        assert "response_schema" in call_kwargs
        # 验证 Schema 正确
        assert call_kwargs["response_schema"] is FinancialSummary

    @pytest.mark.asyncio
    async def test_tenant_id_passed_to_cross_document(self, service: SummaryGenerationService) -> None:
        """跨文档模式时 tenant_id 透传到分层检索"""
        mock_retrieval = _make_layered_retrieval()
        service._layered_retrieval = mock_retrieval

        await service.generate_summary(
            query_text="测试",
            search_results=[],
            perspective="financial",
            tenant_id="tenant-001",
            cross_document=True,
        )

        # 验证 tenant_id 透传到 L2 检索
        mock_retrieval.search_top_down.assert_called_with(
            query_text="测试",
            target_level="L2",
            collection="documents",
            limit=10,
            tenant_id="tenant-001",
            filter_payload=None,
        )


class TestStoreSummary:
    """摘要存储逻辑验证"""

    @pytest.mark.asyncio
    async def test_store_summary_called_for_single_document(self, service: SummaryGenerationService) -> None:
        """单文档模式调用存储逻辑"""
        mock_l3 = _make_l3_vector()
        mock_embedding = _make_embedding_service()
        service._l3_vector = mock_l3
        service._embedding_service = mock_embedding

        await service.generate_summary(
            query_text="测试",
            search_results=_make_search_results(),
            perspective="financial",
        )

        # 验证 upsert_points 被调用
        mock_l3.upsert_points.assert_called_once()
        call_args = mock_l3.upsert_points.call_args[1]
        assert call_args["collection"] == "document_summaries"

    @pytest.mark.asyncio
    async def test_store_summary_called_for_cross_document(self, service: SummaryGenerationService) -> None:
        """跨文档模式调用存储逻辑到 cross_document_summaries"""
        mock_l3 = _make_l3_vector()
        mock_embedding = _make_embedding_service()
        service._l3_vector = mock_l3
        service._embedding_service = mock_embedding

        await service.generate_summary(
            query_text="测试",
            search_results=[],
            perspective="financial",
            cross_document=True,
        )

        # 验证 upsert_points 被调用到 cross_document_summaries
        mock_l3.upsert_points.assert_called_once()
        call_args = mock_l3.upsert_points.call_args[1]
        assert call_args["collection"] == "cross_document_summaries"


class TestConstructor:
    """构造函数注入验证"""

    def test_constructor_injects_llm_client(self) -> None:
        """构造函数注入 LLMClientPort"""
        service = SummaryGenerationService(
            llm_client=_make_llm_client(),
            layered_retrieval=_make_layered_retrieval(),
            embedding_service=_make_embedding_service(),
            l3_vector=_make_l3_vector(),
        )
        assert service._llm_client is not None

    def test_constructor_injects_layered_retrieval(self) -> None:
        """构造函数注入 LayeredRetrievalPort"""
        service = SummaryGenerationService(
            llm_client=_make_llm_client(),
            layered_retrieval=_make_layered_retrieval(),
            embedding_service=_make_embedding_service(),
            l3_vector=_make_l3_vector(),
        )
        assert service._layered_retrieval is not None

    def test_constructor_injects_embedding_service(self) -> None:
        """构造函数注入 EmbeddingServicePort"""
        service = SummaryGenerationService(
            llm_client=_make_llm_client(),
            layered_retrieval=_make_layered_retrieval(),
            embedding_service=_make_embedding_service(),
            l3_vector=_make_l3_vector(),
        )
        assert service._embedding_service is not None

    def test_constructor_injects_l3_vector(self) -> None:
        """构造函数注入 L3VectorPort"""
        service = SummaryGenerationService(
            llm_client=_make_llm_client(),
            layered_retrieval=_make_layered_retrieval(),
            embedding_service=_make_embedding_service(),
            l3_vector=_make_l3_vector(),
        )
        assert service._l3_vector is not None


class TestStalenessPrompt:
    """陈旧提示注入测试（Story 3.12 AC-5）"""

    @pytest.fixture
    def service(self) -> SummaryGenerationService:
        """创建 SummaryGenerationService 实例"""
        return SummaryGenerationService(
            llm_client=_make_llm_client(),
            layered_retrieval=_make_layered_retrieval(),
            embedding_service=_make_embedding_service(),
            l3_vector=_make_l3_vector(),
        )

    def test_stale_result_in_context_prefixed(self, service: SummaryGenerationService) -> None:
        """结果中包含 is_stale=True 时上下文文本附加 [数据陈旧: ...] 前缀"""
        results = [
            SearchResult(
                id="doc-1",
                score=0.8,
                payload={
                    "content": "陈旧文档内容",
                    "document_id": "doc-001",
                    "is_stale": True,
                    "stale_reason": "expired",
                    "stale_since": "2026-08-15T00:00:00+00:00",
                },
            ),
        ]
        context_text = service._build_search_context(results)
        assert "[数据陈旧: 原因=expired, 标记时间=2026-08-15T00:00:00+00:00]" in context_text
        assert "陈旧文档内容" in context_text

    def test_fresh_result_no_prefix(self, service: SummaryGenerationService) -> None:
        """结果中不包含陈旧数据时上下文文本无变化"""
        results = [
            SearchResult(
                id="doc-1",
                score=0.8,
                payload={
                    "content": "新鲜文档内容",
                    "document_id": "doc-001",
                    "is_stale": False,
                },
            ),
        ]
        context_text = service._build_search_context(results)
        assert "[数据陈旧" not in context_text
        assert "新鲜文档内容" in context_text

    def test_no_is_stale_flag_no_prefix(self, service: SummaryGenerationService) -> None:
        """payload 中无 is_stale 标记时（archive_repo 未注入）不提示"""
        results = [
            SearchResult(
                id="doc-1",
                score=0.8,
                payload={
                    "content": "无标记文档内容",
                    "document_id": "doc-001",
                },
            ),
        ]
        context_text = service._build_search_context(results)
        assert "[数据陈旧" not in context_text
        assert "无标记文档内容" in context_text

    @pytest.mark.asyncio
    async def test_fallback_archive_repo_stale(self) -> None:
        """payload 无 is_stale 标记时，通过 archive_repo 兜底判断（注入时）"""
        from datetime import UTC, datetime
        from unittest.mock import AsyncMock

        from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
        from src.domain.ports.archive_repository import ArchiveRepositoryPort

        repo = AsyncMock(spec=ArchiveRepositoryPort)
        from uuid import UUID

        stale_archive = StrategicArchive(
            archive_id=UUID("11111111-1111-1111-1111-111111111111"),
            plan_id=UUID("22222222-2222-2222-2222-222222222222"),
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            valid_until=datetime(2021, 1, 1, tzinfo=UTC),
        )
        repo.find.return_value = [stale_archive]
        svc = SummaryGenerationService(
            llm_client=_make_llm_client(),
            layered_retrieval=_make_layered_retrieval(),
            embedding_service=_make_embedding_service(),
            l3_vector=_make_l3_vector(),
            archive_repo=repo,
        )
        results = [
            SearchResult(
                id="strategic_archive:11111111-1111-1111-1111-111111111111",
                score=0.8,
                payload={
                    "content": "陈旧文档内容",
                    "archive_id": "11111111-1111-1111-1111-111111111111",
                },
            ),
        ]
        # prefetch 是异步方法，需在调用 _build_search_context 前执行
        await svc._prefetch_staleness(results)
        context_text = svc._build_search_context(results)
        assert "[数据陈旧: " in context_text
        assert repo.find.called

    @pytest.mark.asyncio
    async def test_fallback_archive_repo_fresh(self) -> None:
        """payload 无 is_stale 标记，archive_repo 判断为新鲜时不提示"""
        from datetime import UTC, datetime
        from unittest.mock import AsyncMock

        from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
        from src.domain.ports.archive_repository import ArchiveRepositoryPort

        repo = AsyncMock(spec=ArchiveRepositoryPort)
        from uuid import UUID

        fresh_archive = StrategicArchive(
            archive_id=UUID("11111111-1111-1111-1111-111111111111"),
            plan_id=UUID("22222222-2222-2222-2222-222222222222"),
            plan_type="SP",
            archive_type=ArchiveType.ASSUMPTION,
            valid_until=datetime(2099, 1, 1, tzinfo=UTC),
        )
        repo.find.return_value = [fresh_archive]
        svc = SummaryGenerationService(
            llm_client=_make_llm_client(),
            layered_retrieval=_make_layered_retrieval(),
            embedding_service=_make_embedding_service(),
            l3_vector=_make_l3_vector(),
            archive_repo=repo,
        )
        results = [
            SearchResult(
                id="strategic_archive:11111111-1111-1111-1111-111111111111",
                score=0.8,
                payload={
                    "content": "新鲜文档内容",
                    "archive_id": "11111111-1111-1111-1111-111111111111",
                },
            ),
        ]
        await svc._prefetch_staleness(results)
        context_text = svc._build_search_context(results)
        assert "[数据陈旧" not in context_text

    def test_cross_document_stale_prompt(self, service: SummaryGenerationService) -> None:
        """跨文档模式（L1）同样支持陈旧提示"""
        l2_results = [
            SearchResult(
                id="summary-1",
                score=0.85,
                payload={
                    "summary_text": "已有摘要内容",
                    "perspective": "financial",
                    "index_level": "L2",
                    "is_stale": True,
                    "stale_reason": "archived_too_long",
                    "stale_since": "2026-07-01T00:00:00+00:00",
                },
            ),
        ]
        context_text = service._build_cross_document_context(l2_results)
        assert "[数据陈旧: 原因=archived_too_long, 标记时间=2026-07-01T00:00:00+00:00]" in context_text
        assert "已有摘要内容" in context_text

    def test_cross_document_fresh_no_prompt(self, service: SummaryGenerationService) -> None:
        """跨文档模式无陈旧数据时不提示"""
        l2_results = [
            SearchResult(
                id="summary-1",
                score=0.85,
                payload={
                    "summary_text": "已有摘要内容",
                    "perspective": "financial",
                    "index_level": "L2",
                },
            ),
        ]
        context_text = service._build_cross_document_context(l2_results)
        assert "[数据陈旧" not in context_text
        assert "已有摘要内容" in context_text


class TestSummaryPromptStaleness:
    """summary_prompts.py 陈旧处理说明测试"""

    def test_financial_prompt_contains_staleness_note(self) -> None:
        """financial system_prompt 包含陈旧数据处理说明"""
        from src.application.services.summary_prompts import FINANCIAL_SYSTEM_PROMPT

        assert "数据陈旧" in FINANCIAL_SYSTEM_PROMPT
        assert "部分引用数据已陈旧" in FINANCIAL_SYSTEM_PROMPT

    def test_market_prompt_contains_staleness_note(self) -> None:
        """market system_prompt 包含陈旧数据处理说明"""
        from src.application.services.summary_prompts import MARKET_SYSTEM_PROMPT

        assert "部分引用数据已陈旧" in MARKET_SYSTEM_PROMPT

    def test_technical_prompt_contains_staleness_note(self) -> None:
        """technical system_prompt 包含陈旧数据处理说明"""
        from src.application.services.summary_prompts import TECHNICAL_SYSTEM_PROMPT

        assert "部分引用数据已陈旧" in TECHNICAL_SYSTEM_PROMPT
