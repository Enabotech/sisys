"""补充测试：提升 SemanticRouter 覆盖率至 85%+

覆盖未测试的路径：
- __init__() 带 cache_ttl_seconds 参数
- _get_task_embedding() 当 embedding model 返回空列表
- _get_task_embedding() 当缓存已满（达到 MAX_CACHE_SIZE）
- _extract_task_description() 处理 dict 类型值
- _extract_task_description() 处理 falsy 值（None、空字符串、0、False）
- route() 实际正相似度分数（> 0）
- add_candidate() 替换现有 candidate
- _cosine_similarity() 两个向量均为零向量
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.infrastructure.routing.semantic_router import (
    Candidate,
    EmbeddingModelProtocol,
    SemanticRouter,
)


class TestSemanticRouterInit:
    """测试 SemanticRouter 初始化"""

    def test_init_with_cache_ttl_seconds(self) -> None:
        """初始化时应正确存储 cache_ttl_seconds 参数"""
        router = SemanticRouter(cache_ttl_seconds=3600)
        assert router._cache_ttl == 3600

    def test_init_with_embedding_model(self) -> None:
        """初始化时应正确存储 embedding_model"""
        mock_model = AsyncMock(spec=EmbeddingModelProtocol)
        router = SemanticRouter(embedding_model=mock_model)
        assert router._embedding_model is mock_model

    def test_init_with_none_candidates(self) -> None:
        """初始化时 candidates 为 None 应创建空字典"""
        router = SemanticRouter(candidates=None)
        assert router._candidates == {}
        assert router.candidate_count == 0


class TestSemanticRouterGetTaskEmbedding:
    """测试 _get_task_embedding 方法"""

    @pytest.mark.asyncio
    async def test_get_task_embedding_returns_zeros_when_no_model(self) -> None:
        """无 embedding model 时应返回零向量"""
        router = SemanticRouter()
        embedding = await router._get_task_embedding("test text")
        assert embedding == [0.0] * SemanticRouter.DEFAULT_EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_get_task_embedding_when_model_returns_empty_list(self) -> None:
        """embedding model 返回空列表时应返回零向量"""
        mock_model = AsyncMock(spec=EmbeddingModelProtocol)
        mock_model.embed.return_value = []  # 返回空列表
        router = SemanticRouter(embedding_model=mock_model)

        embedding = await router._get_task_embedding("test text")
        assert embedding == [0.0] * SemanticRouter.DEFAULT_EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_get_task_embedding_cache_not_updated_when_full(self) -> None:
        """缓存已满时不应添加新条目"""
        router = SemanticRouter()
        router._embedding_cache.clear()

        # 填满缓存到 MAX_CACHE_SIZE
        for i in range(SemanticRouter.MAX_CACHE_SIZE):
            router._embedding_cache[f"text-{i}"] = [0.1] * 1024

        # 验证缓存已满
        assert len(router._embedding_cache) == SemanticRouter.MAX_CACHE_SIZE

        # 尝试获取新文本的 embedding
        embedding = await router._get_task_embedding("new-text-not-in-cache")

        # 新文本不应被缓存
        assert "new-text-not-in-cache" not in router._embedding_cache
        assert len(router._embedding_cache) == SemanticRouter.MAX_CACHE_SIZE
        # 仍应返回 embedding（零向量）
        assert embedding == [0.0] * SemanticRouter.DEFAULT_EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_get_task_embedding_with_valid_embedding_model(self) -> None:
        """有 embedding model 时应调用并返回结果"""
        mock_model = AsyncMock(spec=EmbeddingModelProtocol)
        expected_embedding = [0.5] * 1024
        mock_model.embed.return_value = [expected_embedding]
        router = SemanticRouter(embedding_model=mock_model)

        embedding = await router._get_task_embedding("test text")

        mock_model.embed.assert_called_once_with(["test text"])
        assert embedding == expected_embedding


class TestSemanticRouterExtractTaskDescription:
    """测试 _extract_task_description 方法"""

    def test_extract_description_with_dict_value(self) -> None:
        """dict 类型值应被转换为字符串"""
        router = SemanticRouter()
        desc = router._extract_task_description({"description": {"key": "value", "nested": {"inner": 123}}})
        assert "key" in desc
        assert "value" in desc

    def test_extract_description_with_none_value(self) -> None:
        """None 值应被跳过（falsy）"""
        router = SemanticRouter()
        desc = router._extract_task_description({"description": None, "task_type": "backup"})
        assert desc == "backup"

    def test_extract_description_with_empty_string(self) -> None:
        """空字符串应被跳过（falsy）"""
        router = SemanticRouter()
        desc = router._extract_task_description({"description": "", "name": "test task"})
        assert desc == "test task"

    def test_extract_description_with_zero_value(self) -> None:
        """数字 0 应被跳过（falsy）"""
        router = SemanticRouter()
        desc = router._extract_task_description({"task_type": 0, "prompt": "actual prompt"})
        assert desc == "actual prompt"

    def test_extract_description_with_false_value(self) -> None:
        """False 布尔值应被跳过（falsy）"""
        router = SemanticRouter()
        desc = router._extract_task_description({"name": False, "prompt": "real prompt"})
        assert desc == "real prompt"

    def test_extract_description_priority_order(self) -> None:
        """应按优先级顺序提取：description > task_description > task_type > name > prompt"""
        router = SemanticRouter()

        # description 优先于 task_description
        desc = router._extract_task_description(
            {
                "description": "first",
                "task_description": "second",
                "task_type": "third",
            }
        )
        assert desc == "first"

        # task_description 优先于 task_type
        desc = router._extract_task_description(
            {
                "task_description": "second",
                "task_type": "third",
                "name": "fourth",
            }
        )
        assert desc == "second"

        # task_type 优先于 name
        desc = router._extract_task_description(
            {
                "task_type": "third",
                "name": "fourth",
                "prompt": "fifth",
            }
        )
        assert desc == "third"

        # name 优先于 prompt
        desc = router._extract_task_description(
            {
                "name": "fourth",
                "prompt": "fifth",
            }
        )
        assert desc == "fourth"

        # 最后是 prompt
        desc = router._extract_task_description({"prompt": "fifth"})
        assert desc == "fifth"

    def test_extract_description_with_integer_value(self) -> None:
        """非字符串、非 list/dict 的值应被跳过"""
        router = SemanticRouter()
        desc = router._extract_task_description({"description": 123})
        # 123 是 truthy 但不是 str/list/dict，应返回空字符串
        assert desc == ""


class TestSemanticRouterRoute:
    """测试 route 方法"""

    @pytest.fixture
    def candidate_with_embedding(self) -> Candidate:
        """创建带有非零 embedding 的 candidate"""
        return Candidate(
            candidate_id="test-agent",
            name="Test Agent",
            description="Test description",
            embedding=[1.0] * 1024,  # 非零 embedding
        )

    @pytest.mark.asyncio
    async def test_route_with_positive_similarity_score(self) -> None:
        """当 embedding 匹配时应返回正相似度分数"""
        # 创建 mock embedding model 返回与 candidate 相同的 embedding
        mock_model = AsyncMock(spec=EmbeddingModelProtocol)
        matching_embedding = [1.0] * 1024
        mock_model.embed.return_value = [matching_embedding]

        candidate = Candidate(
            candidate_id="match-agent",
            name="Match Agent",
            description="Matching description",
            embedding=matching_embedding,
        )

        router = SemanticRouter(candidates=[candidate], embedding_model=mock_model)
        target, score = await router.route({"description": "test"})

        assert target == "match-agent"
        assert score == 1.0  # 完全相同的向量，cosine similarity = 1.0

    @pytest.mark.asyncio
    async def test_route_returns_best_match_not_first(self) -> None:
        """应返回最佳匹配而非第一个 candidate"""
        mock_model = AsyncMock(spec=EmbeddingModelProtocol)
        # Task embedding 与 candidate2 更相似
        task_embedding = [0.1] * 512 + [0.9] * 512
        mock_model.embed.return_value = [task_embedding]

        candidate1 = Candidate(
            candidate_id="agent-1",
            name="Agent 1",
            description="First agent",
            embedding=[0.9] * 512 + [0.1] * 512,  # 与 task 不太相似
        )
        candidate2 = Candidate(
            candidate_id="agent-2",
            name="Agent 2",
            description="Second agent",
            embedding=[0.1] * 512 + [0.9] * 512,  # 与 task 更相似
        )

        router = SemanticRouter(candidates=[candidate1, candidate2], embedding_model=mock_model)
        target, score = await router.route({"description": "test"})

        assert target == "agent-2"
        assert score > 0.9  # 高相似度

    @pytest.mark.asyncio
    async def test_route_with_negative_similarity(self) -> None:
        """应正确处理负相似度分数（不更新 best_score，因为 score > best_score 不成立）"""
        mock_model = AsyncMock(spec=EmbeddingModelProtocol)
        # Task embedding 与 candidate 方向相反
        task_embedding = [-1.0] * 1024
        mock_model.embed.return_value = [task_embedding]

        candidate = Candidate(
            candidate_id="opposite-agent",
            name="Opposite Agent",
            description="Opposite direction",
            embedding=[1.0] * 1024,
        )

        router = SemanticRouter(candidates=[candidate], embedding_model=mock_model)
        target, score = await router.route({"description": "test"})

        # 负相似度不满足 score > best_score（best_score 初始为 0）
        # 因此应返回第一个 candidate，分数为 0.0
        assert target == "opposite-agent"
        assert score == 0.0


class TestSemanticRouterAddCandidate:
    """测试 add_candidate 方法"""

    def test_add_candidate_replaces_existing(self) -> None:
        """添加相同 ID 的 candidate 应替换现有的"""
        original = Candidate(
            candidate_id="agent-1",
            name="Original Agent",
            description="Original description",
            embedding=[0.1] * 1024,
        )
        router = SemanticRouter(candidates=[original])

        assert router.candidate_count == 1
        assert router._candidates["agent-1"].name == "Original Agent"

        # 添加相同 ID 的新 candidate
        replacement = Candidate(
            candidate_id="agent-1",
            name="Replacement Agent",
            description="Replacement description",
            embedding=[0.9] * 1024,
        )
        router.add_candidate(replacement)

        assert router.candidate_count == 1  # 数量不变
        assert router._candidates["agent-1"].name == "Replacement Agent"
        assert router._candidates["agent-1"].description == "Replacement description"


class TestSemanticRouterCosineSimilarity:
    """测试 _cosine_similarity 静态方法"""

    @staticmethod
    def test_cosine_similarity_both_zero_vectors() -> None:
        """两个零向量应返回 0.0"""
        vec1 = [0.0] * 10
        vec2 = [0.0] * 10
        score = SemanticRouter._cosine_similarity(vec1, vec2)
        assert score == 0.0

    @staticmethod
    def test_cosine_similarity_second_vector_zero() -> None:
        """第二个向量为零向量时应返回 0.0"""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [0.0, 0.0, 0.0]
        score = SemanticRouter._cosine_similarity(vec1, vec2)
        assert score == 0.0

    @staticmethod
    def test_cosine_similarity_different_lengths() -> None:
        """不同长度的向量应正常计算（zip 会截断到较短长度）"""
        vec1 = [1.0, 0.0]
        vec2 = [1.0, 0.0, 1.0]  # 多一个元素
        # zip 后只比较前两个元素，应为 1.0
        score = SemanticRouter._cosine_similarity(vec1, vec2)
        assert score == 1.0

    @staticmethod
    def test_cosine_similarity_fractional_values() -> None:
        """应正确计算分数值向量的相似度"""
        import math

        vec1 = [0.5, 0.5, 0.5]
        vec2 = [0.5, 0.5, 0.5]
        score = SemanticRouter._cosine_similarity(vec1, vec2)
        assert math.isclose(score, 1.0, rel_tol=1e-9)


class TestSemanticRouterCandidateCount:
    """测试 candidate_count 属性"""

    def test_candidate_count_after_multiple_operations(self) -> None:
        """多次添加和删除后应正确计数"""
        router = SemanticRouter()
        assert router.candidate_count == 0

        # 添加多个
        for i in range(5):
            router.add_candidate(
                Candidate(
                    candidate_id=f"agent-{i}",
                    name=f"Agent {i}",
                    description=f"Description {i}",
                    embedding=[0.1] * 1024,
                )
            )
        assert router.candidate_count == 5

        # 删除部分
        router.remove_candidate("agent-1")
        router.remove_candidate("agent-3")
        assert router.candidate_count == 3

        # 添加已存在的（替换）
        router.add_candidate(
            Candidate(
                candidate_id="agent-0",
                name="Replaced Agent 0",
                description="New description",
                embedding=[0.2] * 1024,
            )
        )
        assert router.candidate_count == 3  # 数量不变

        # 删除不存在的
        router.remove_candidate("nonexistent")
        assert router.candidate_count == 3
