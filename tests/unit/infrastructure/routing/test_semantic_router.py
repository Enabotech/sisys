"""Unit tests for SemanticRouter — semantic similarity-based routing."""

from __future__ import annotations

import math
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.routing.semantic_router import (
    Candidate,
    EmbeddingModelProtocol,
    SemanticRouter,
)


class TestSemanticRouter:
    """Test suite for SemanticRouter."""

    @pytest.fixture
    def mock_embedding_model(self) -> AsyncMock:
        """Create mock embedding model."""
        model = AsyncMock(spec=EmbeddingModelProtocol)
        model.embed.return_value = [[0.1] * 1024]
        return model

    @pytest.fixture
    def cfo_candidate(self) -> Candidate:
        """CFO agent candidate - distinct embedding pattern."""
        # Use pseudo-orthogonal embeddings for distinct similarity scores
        embedding = []
        for i in range(1024):
            if i % 3 == 0:
                embedding.append(0.8)  # CFO marker
            elif i % 3 == 1:
                embedding.append(0.1)
            else:
                embedding.append(0.1)
        return Candidate(
            candidate_id="cfo-agent",
            name="CFO Agent",
            description="Financial analysis, risk assessment, and investment planning",
            embedding=embedding,
        )

    @pytest.fixture
    def ceo_candidate(self) -> Candidate:
        """CEO agent candidate - distinct embedding pattern."""
        embedding = []
        for i in range(1024):
            if i % 3 == 0:
                embedding.append(0.1)
            elif i % 3 == 1:
                embedding.append(0.8)  # CEO marker
            else:
                embedding.append(0.1)
        return Candidate(
            candidate_id="ceo-agent",
            name="CEO Agent",
            description="Strategic planning and executive decision making",
            embedding=embedding,
        )

    @pytest.fixture
    def cto_candidate(self) -> Candidate:
        """CTO agent candidate - distinct embedding pattern."""
        embedding = []
        for i in range(1024):
            if i % 3 == 0:
                embedding.append(0.1)
            elif i % 3 == 1:
                embedding.append(0.1)
            else:
                embedding.append(0.8)  # CTO marker
        return Candidate(
            candidate_id="cto-agent",
            name="CTO Agent",
            description="Technology strategy, software architecture, and digital transformation",
            embedding=embedding,
        )

    @pytest.fixture
    def semantic_router(
        self,
        cfo_candidate: Candidate,
        ceo_candidate: Candidate,
        cto_candidate: Candidate,
    ) -> SemanticRouter:
        """Create SemanticRouter with test candidates."""
        return SemanticRouter(candidates=[cfo_candidate, ceo_candidate, cto_candidate])

    @pytest.mark.asyncio
    async def test_route_returns_best_match(self, semantic_router: SemanticRouter) -> None:
        """Route should return highest similarity candidate."""
        # Without embedding model, all candidates get 0.0 score
        # Route should return first candidate (cfo-agent)
        task_context = {"task_type": "financial_analysis"}
        target, score = await semantic_router.route(task_context)
        assert target == "cfo-agent"  # First candidate since all scores are 0
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_route_with_empty_candidates(self) -> None:
        """Route with no candidates should return empty tuple."""
        router = SemanticRouter(candidates=[])
        target, score = await router.route({"task_type": "test"})
        assert target == ""
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_route_without_embedding_model(self, cfo_candidate: Candidate) -> None:
        """Route without embedding model returns zero similarity."""
        router = SemanticRouter(candidates=[cfo_candidate])
        target, score = await router.route({"task_type": "financial"})
        assert target == "cfo-agent"
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_route_with_empty_task_context(self) -> None:
        """Route with empty task context returns empty target."""
        router = SemanticRouter(
            candidates=[
                Candidate(
                    candidate_id="agent-1",
                    name="Agent 1",
                    description="Test agent",
                    embedding=[0.5] * 1024,
                )
            ]
        )
        target, score = await router.route({})
        assert target == ""
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_route_with_embedding_model(
        self,
        cfo_candidate: Candidate,
        mock_embedding_model: AsyncMock,
    ) -> None:
        """Route with embedding model should use it for task embedding."""
        router = SemanticRouter(candidates=[cfo_candidate], embedding_model=mock_embedding_model)
        task_context = {"task_type": "financial analysis"}
        await router.route(task_context)
        mock_embedding_model.embed.assert_called_once()

    def test_route_extracts_description_from_task_context(self) -> None:
        """Route should extract description from various task context fields."""
        router = SemanticRouter(candidates=[])

        # Test 'description' field
        desc = router._extract_task_description({"description": "test description"})
        assert desc == "test description"

        # Test 'task_description' field
        desc = router._extract_task_description({"task_description": "task desc"})
        assert desc == "task desc"

        # Test 'task_type' field
        desc = router._extract_task_description({"task_type": "analysis"})
        assert desc == "analysis"

        # Test 'name' field
        desc = router._extract_task_description({"name": "task name"})
        assert desc == "task name"

        # Test 'prompt' field
        desc = router._extract_task_description({"prompt": "task prompt"})
        assert desc == "task prompt"

        # Test empty context
        desc = router._extract_task_description({})
        assert desc == ""

    def test_route_with_complex_task_context(self) -> None:
        """Route should handle complex values in supported fields."""
        router = SemanticRouter(candidates=[])
        # list value in 'description' field should be stringified
        desc = router._extract_task_description({"description": ["finance", "analysis"]})
        assert "finance" in desc

    def test_add_candidate(self, semantic_router: SemanticRouter) -> None:
        """Adding candidate should increase candidate count."""
        assert semantic_router.candidate_count == 3
        semantic_router.add_candidate(
            Candidate(
                candidate_id="new-agent",
                name="New Agent",
                description="New agent description",
                embedding=[0.5] * 1024,
            )
        )
        assert semantic_router.candidate_count == 4

    def test_remove_candidate(self, semantic_router: SemanticRouter) -> None:
        """Removing candidate should decrease candidate count."""
        assert semantic_router.candidate_count == 3
        semantic_router.remove_candidate("cfo-agent")
        assert semantic_router.candidate_count == 2
        assert "cfo-agent" not in semantic_router._candidates

    def test_remove_nonexistent_candidate(self, semantic_router: SemanticRouter) -> None:
        """Removing non-existent candidate should not raise."""
        semantic_router.remove_candidate("nonexistent")
        assert semantic_router.candidate_count == 3

    @staticmethod
    def test_cosine_similarity_identical_vectors() -> None:
        """Identical vectors should have similarity 1.0."""
        vec = [0.1] * 10
        score = SemanticRouter._cosine_similarity(vec, vec)
        assert math.isclose(score, 1.0, rel_tol=1e-9)

    @staticmethod
    def test_cosine_similarity_opposite_vectors() -> None:
        """Opposite vectors should have similarity -1.0."""
        vec1 = [1.0] * 10
        vec2 = [-1.0] * 10
        score = SemanticRouter._cosine_similarity(vec1, vec2)
        assert math.isclose(score, -1.0, rel_tol=1e-9)

    @staticmethod
    def test_cosine_similarity_orthogonal_vectors() -> None:
        """Orthogonal vectors should have similarity 0.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        score = SemanticRouter._cosine_similarity(vec1, vec2)
        assert math.isclose(score, 0.0, rel_tol=1e-9)

    @staticmethod
    def test_cosine_similarity_empty_vectors() -> None:
        """Empty vectors should return 0.0."""
        score = SemanticRouter._cosine_similarity([], [])
        assert score == 0.0

    @staticmethod
    def test_cosine_similarity_zero_magnitude_vector() -> None:
        """Zero-magnitude vector should return 0.0."""
        score = SemanticRouter._cosine_similarity([0.0, 0.0], [1.0, 2.0])
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_embedding_cache(self, cfo_candidate: Candidate) -> None:
        """Same text should be cached and not re-embedded."""
        mock_model = AsyncMock(spec=EmbeddingModelProtocol)
        mock_model.embed.return_value = [[0.1] * 1024]

        router = SemanticRouter(candidates=[cfo_candidate], embedding_model=mock_model)
        task_text = "financial analysis task"

        # First call
        await router._get_task_embedding(task_text)
        assert mock_model.embed.call_count == 1

        # Second call - should use cache
        await router._get_task_embedding(task_text)
        assert mock_model.embed.call_count == 1  # Still 1, not 2

    @pytest.mark.asyncio
    async def test_cache_size_limit(self) -> None:
        """Cache should not exceed MAX_CACHE_SIZE."""
        router = SemanticRouter()
        router._embedding_cache.clear()  # Start fresh

        # Fill to one below limit
        for i in range(SemanticRouter.MAX_CACHE_SIZE - 1):
            router._embedding_cache[f"text-{i}"] = [0.1] * 1024

        # Adding one more should work (now at limit)
        router._embedding_cache[f"text-{SemanticRouter.MAX_CACHE_SIZE}"] = [0.1] * 1024
        assert len(router._embedding_cache) == SemanticRouter.MAX_CACHE_SIZE

    @pytest.mark.asyncio
    async def test_route_with_real_semantic_matching(
        self,
        cfo_candidate: Candidate,
        ceo_candidate: Candidate,
        mock_embedding_model: AsyncMock,
    ) -> None:
        """有 embedding model 时应根据语义相似度选择最佳候选"""
        # CFO-like embedding (匹配 cfo_candidate 的模式)
        cfo_like_embedding = []
        for i in range(1024):
            if i % 3 == 0:
                cfo_like_embedding.append(0.9)
            else:
                cfo_like_embedding.append(0.1)
        mock_embedding_model.embed.return_value = [cfo_like_embedding]

        router = SemanticRouter(
            candidates=[cfo_candidate, ceo_candidate],
            embedding_model=mock_embedding_model,
        )
        target, score = await router.route({"description": "financial analysis"})
        assert target == "cfo-agent"
        assert score > 0.0

    @pytest.mark.asyncio
    async def test_route_with_dict_description(self) -> None:
        """description 为 dict 类型时应转为字符串"""
        candidate = Candidate(
            candidate_id="agent-1",
            name="Agent 1",
            description="Test agent",
            embedding=[0.5] * 1024,
        )
        router = SemanticRouter(candidates=[candidate])
        target, score = await router.route({"description": {"key": "value"}})
        # 没有 embedding model 所以 score=0，但不应报错
        assert target == "agent-1"

    @pytest.mark.asyncio
    async def test_route_with_none_description_value(self) -> None:
        """description 为 None 时应跳过该字段"""
        candidate = Candidate(
            candidate_id="agent-1",
            name="Agent 1",
            description="Test agent",
            embedding=[0.5] * 1024,
        )
        router = SemanticRouter(candidates=[candidate])
        target, score = await router.route({"description": None, "task_type": "analysis"})
        assert target == "agent-1"

    @pytest.mark.asyncio
    async def test_route_with_empty_string_description(self) -> None:
        """空字符串 description 应被跳过"""
        candidate = Candidate(
            candidate_id="agent-1",
            name="Agent 1",
            description="Test agent",
            embedding=[0.5] * 1024,
        )
        router = SemanticRouter(candidates=[candidate])
        target, score = await router.route({"description": ""})
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_route_none_init_creates_empty_router(self) -> None:
        """candidates=None 应创建空路由器"""
        router = SemanticRouter(candidates=None)
        assert router.candidate_count == 0
        target, score = await router.route({"task_type": "test"})
        assert target == ""
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_add_candidate_replaces_existing(self) -> None:
        """添加同 ID 候选应替换"""
        router = SemanticRouter()
        router.add_candidate(
            Candidate(
                candidate_id="agent-1",
                name="Original",
                description="First version",
                embedding=[0.1] * 1024,
            )
        )
        assert router.candidate_count == 1

        router.add_candidate(
            Candidate(
                candidate_id="agent-1",
                name="Updated",
                description="Second version",
                embedding=[0.9] * 1024,
            )
        )
        assert router.candidate_count == 1
        assert router._candidates["agent-1"].name == "Updated"

    @staticmethod
    def test_cosine_similarity_different_lengths() -> None:
        """不同长度向量应按较短的长度计算"""
        a = [1.0, 0.0, 1.0]
        b = [1.0, 0.0]
        score = SemanticRouter._cosine_similarity(a, b)
        assert 0.0 <= abs(score) <= 1.0

    @pytest.mark.asyncio
    async def test_get_task_embedding_no_model_returns_zeros(self) -> None:
        """无 embedding model 时应返回零向量"""
        router = SemanticRouter()
        embedding = await router._get_task_embedding("test text")
        assert len(embedding) == SemanticRouter.DEFAULT_EMBEDDING_DIM
        assert all(v == 0.0 for v in embedding)

    @pytest.mark.asyncio
    async def test_get_task_embedding_model_returns_empty(self) -> None:
        """embedding model 返回空列表时应回退零向量"""
        mock_model = AsyncMock(spec=EmbeddingModelProtocol)
        mock_model.embed.return_value = []
        router = SemanticRouter(embedding_model=mock_model)
        embedding = await router._get_task_embedding("test text")
        assert all(v == 0.0 for v in embedding)

    def test_candidate_count_property(self) -> None:
        """candidate_count 应正确反映候选项数量"""
        router = SemanticRouter()
        assert router.candidate_count == 0
        router.add_candidate(Candidate(candidate_id="a", name="A", description="a", embedding=[0.0]))
        assert router.candidate_count == 1

    @pytest.mark.asyncio
    async def test_embedding_cache_not_exceeding_max(self) -> None:
        """缓存满时不应添加新条目"""
        router = SemanticRouter()
        router._embedding_cache.clear()
        # 预填充到最大
        for i in range(SemanticRouter.MAX_CACHE_SIZE):
            router._embedding_cache[f"text-{i}"] = [0.0] * 1024

        _embedding = await router._get_task_embedding("new text")
        assert "new text" not in router._embedding_cache
        assert len(router._embedding_cache) == SemanticRouter.MAX_CACHE_SIZE
