"""RRF（Reciprocal Rank Fusion）融合算法单元测试

验证 RRF 融合算法的数学正确性：对称两路/加权三路/单路直通/空输入/重复文档ID/自定义k值
参考：Cormack et al., SIGIR 2009: https://doi.org/10.1145/1571941.1572114

领域层零外部依赖测试：仅使用 Python 标准库
"""

from __future__ import annotations

import math
import time

import pytest

from src.domain.exceptions import ValidationError
from src.domain.ports.l3_vector import SearchResult
from src.domain.services.rrf_fusion import RRF_K_DEFAULT, fuse


def _make_result(id: str | int, score: float, title: str = "") -> SearchResult:
    """构造测试用 SearchResult"""
    return SearchResult(id=id, score=score, payload={"title": title})


class TestRrfFusionSymmetricTwoLists:
    """对称两路融合（MVP 默认模式）"""

    def test_symmetric_fusion_two_lists(self) -> None:
        """两路对称融合，验证 rank 从 1 开始、RRF 分数计算正确"""
        dense = [
            _make_result("doc1", 0.95, "doc1"),  # rank1
            _make_result("doc2", 0.85, "doc2"),  # rank2
            _make_result("doc3", 0.75, "doc3"),  # rank3
        ]
        sparse = [
            _make_result("doc2", 10.0, "doc2"),  # rank1（跨通道重复）
            _make_result("doc4", 8.0, "doc4"),  # rank2
            _make_result("doc1", 5.0, "doc1"),  # rank3（跨通道重复）
        ]

        result = fuse(dense, sparse)

        # doc2 出现在两路（rank2 in dense, rank1 in sparse）
        # RRF_score(doc2) = 1/(60+2) + 1/(60+1) = 1/62 + 1/61 ≈ 0.03252
        # doc1 出现在两路（rank1 in dense, rank3 in sparse）
        # RRF_score(doc1) = 1/(60+1) + 1/(60+3) = 1/61 + 1/63 ≈ 0.03227
        # doc4 出现在一路（rank2 in sparse）
        # RRF_score(doc4) = 1/(60+2) = 1/62 ≈ 0.01613
        # doc3 出现在一路（rank3 in dense）
        # RRF_score(doc3) = 1/(60+3) = 1/63 ≈ 0.01587

        assert len(result) == 4  # 去重后 4 个文档
        assert result[0]["id"] == "doc2"  # RRF 分数最高
        assert result[1]["id"] == "doc1"

        # 验证分数降序
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)

        # 验证 doc2 RRF 分数 = 1/62 + 1/61（rank 从 1 开始）
        doc2_score = next(r["score"] for r in result if r["id"] == "doc2")
        assert math.isclose(doc2_score, 1 / 62 + 1 / 61, rel_tol=1e-9)

    def test_rank_starts_at_one(self) -> None:
        """验证 enumerate(results, start=1) — rank 从 1 计数"""
        dense = [
            _make_result("doc1", 0.9),
            _make_result("doc2", 0.8),
        ]
        sparse = [
            _make_result("doc3", 5.0),
        ]

        result = fuse(dense, sparse)

        # doc1: rank1 in dense → 1/(60+1) = 1/61 ≈ 0.016393
        doc1_score = next(r["score"] for r in result if r["id"] == "doc1")
        expected_doc1 = 1 / (RRF_K_DEFAULT + 1)
        assert math.isclose(doc1_score, expected_doc1, rel_tol=1e-9)

        # doc2: rank2 in dense → 1/(60+2) = 1/62 ≈ 0.016129
        doc2_score = next(r["score"] for r in result if r["id"] == "doc2")
        expected_doc2 = 1 / (RRF_K_DEFAULT + 2)
        assert math.isclose(doc2_score, expected_doc2, rel_tol=1e-9)

        # doc3: rank1 in sparse → 1/(60+1) = 1/61 (should match doc1)
        doc3_score = next(r["score"] for r in result if r["id"] == "doc3")
        assert math.isclose(doc3_score, expected_doc1, rel_tol=1e-9)

    def test_duplicate_document_across_lists(self) -> None:
        """同文档跨通道出现时 RRF 分数累加，payload 保留首次出现"""
        dense = [
            _make_result("same_doc", 0.95, "from_dense"),
        ]
        sparse = [
            _make_result("same_doc", 10.0, "from_sparse"),
        ]

        result = fuse(dense, sparse)

        assert len(result) == 1
        assert result[0]["id"] == "same_doc"
        # RRF_score = 1/(60+1) + 1/(60+1) = 2/61 ≈ 0.03279
        expected_score = 2 / (RRF_K_DEFAULT + 1)
        assert math.isclose(result[0]["score"], expected_score, rel_tol=1e-9)
        # payload 保留首次出现（dense 通道的 "from_dense"）
        assert result[0]["payload"]["title"] == "from_dense"

    def test_empty_result_lists(self) -> None:
        """某路空列表 — 另一路正常返回"""
        dense = [
            _make_result("doc1", 0.9),
            _make_result("doc2", 0.8),
        ]
        sparse: list[SearchResult] = []

        result = fuse(dense, sparse)

        assert len(result) == 2
        assert result[0]["id"] == "doc1"

    def test_all_empty_result_lists(self) -> None:
        """全部空列表 — 返回空列表"""
        empty: list[SearchResult] = []
        result = fuse(empty, empty)
        assert result == []

    def test_mixed_partial_empty(self) -> None:
        """某路非空，某路为空"""
        dense: list[SearchResult] = []
        sparse = [_make_result("doc1", 5.0)]

        result = fuse(dense, sparse)

        assert len(result) == 1
        assert result[0]["id"] == "doc1"


class TestRrfFusionWeighted:
    """加权融合（V1 预留接口）"""

    def test_weighted_fusion_three_lists(self) -> None:
        """加权三路融合 weights=[0.4, 0.4, 0.2]"""
        dense = [_make_result("doc1", 0.9)]
        sparse = [_make_result("doc1", 5.0)]
        graph = [_make_result("doc1", 0.5)]

        result = fuse(dense, sparse, graph, weights=[0.4, 0.4, 0.2])

        assert len(result) == 1
        # RRF = 0.4/(60+1) + 0.4/(60+1) + 0.2/(60+1) = 1.0/61
        expected = 1.0 / (RRF_K_DEFAULT + 1)
        assert math.isclose(result[0]["score"], expected, rel_tol=1e-9)

    def test_weighted_fusion_different_weights(self) -> None:
        """不同权重的三路融合"""
        dense = [_make_result("doc_a", 0.9)]
        sparse = [_make_result("doc_b", 5.0)]
        graph = [_make_result("doc_c", 0.5)]

        result = fuse(dense, sparse, graph, weights=[0.5, 0.3, 0.2])

        assert len(result) == 3
        # doc_a: 0.5/(60+1) ≈ 0.008197
        doc_a = next(r for r in result if r["id"] == "doc_a")
        assert math.isclose(doc_a["score"], 0.5 / 61, rel_tol=1e-9)
        # doc_b: 0.3/(60+1) ≈ 0.004918
        doc_b = next(r for r in result if r["id"] == "doc_b")
        assert math.isclose(doc_b["score"], 0.3 / 61, rel_tol=1e-9)

    def test_weights_length_mismatch_raises_validation_error(self) -> None:
        """weights 长度不匹配时抛出 ValidationError"""
        dense = [_make_result("doc1", 0.9)]
        sparse = [_make_result("doc2", 5.0)]

        with pytest.raises(ValidationError, match="weights 长度"):
            fuse(dense, sparse, weights=[0.5])  # 2 路但 weights 只有 1 个

    def test_all_zero_weights(self) -> None:
        """全零权重 — 所有分数为 0"""
        dense = [_make_result("doc1", 0.9)]
        sparse = [_make_result("doc2", 5.0)]

        result = fuse(dense, sparse, weights=[0.0, 0.0])

        # 所有分数应为 0
        assert all(r["score"] == 0.0 for r in result)

    # === 补充三路缺失用例（Story 3-4） ===

    def test_three_way_default_weights(self) -> None:
        """三路默认权重 [1.0, 1.0, 0.5] 融合"""
        dense = [_make_result("doc1", 0.9)]
        sparse = [_make_result("doc2", 5.0)]
        graph = [_make_result("doc3", 0.5)]

        result = fuse(dense, sparse, graph, weights=[1.0, 1.0, 0.5])

        assert len(result) == 3
        # doc1: 1.0/(60+1) ≈ 0.016393
        doc1 = next(r for r in result if r["id"] == "doc1")
        assert math.isclose(doc1["score"], 1.0 / 61, rel_tol=1e-9)
        # doc2: 1.0/(60+1) ≈ 0.016393
        doc2 = next(r for r in result if r["id"] == "doc2")
        assert math.isclose(doc2["score"], 1.0 / 61, rel_tol=1e-9)
        # doc3: 0.5/(60+1) ≈ 0.008197
        doc3 = next(r for r in result if r["id"] == "doc3")
        assert math.isclose(doc3["score"], 0.5 / 61, rel_tol=1e-9)

    def test_three_way_symmetric_no_weights(self) -> None:
        """三路对称无权重融合（weights=None）"""
        dense = [_make_result("doc1", 0.9)]
        sparse = [_make_result("doc2", 5.0)]
        graph = [_make_result("doc3", 0.5)]

        result = fuse(dense, sparse, graph)

        assert len(result) == 3
        # 对称融合：所有权重为 1.0
        for r in result:
            assert math.isclose(r["score"], 1.0 / 61, rel_tol=1e-9), f"doc {r['id']} score={r['score']}"

    def test_three_way_performance(self) -> None:
        """三路各 50 结果的融合延迟 P95 < 50ms"""
        dense = [_make_result(f"d_{i}", 0.9 - i * 0.01) for i in range(50)]
        sparse = [_make_result(f"s_{i}", 5.0 - i * 0.1) for i in range(50)]
        graph = [_make_result(f"g_{i}", 0.5 - i * 0.005) for i in range(50)]

        latencies: list[float] = []
        for _ in range(100):
            start = time.perf_counter()
            fuse(dense, sparse, graph, weights=[1.0, 1.0, 0.5])
            latencies.append((time.perf_counter() - start) * 1000)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        assert p95 < 50, f"三路 RRF 融合延迟 P95={p95:.2f}ms，超过 50ms 门禁"


class TestRrfFusionSingleList:
    """单路直通（跳过融合）"""

    def test_single_list_passthrough(self) -> None:
        """单路直接返回（跳过融合）"""
        dense = [
            _make_result("doc1", 0.95),
            _make_result("doc2", 0.85),
        ]

        result = fuse(dense)

        assert len(result) == 2
        assert result == dense  # 原样返回

    def test_single_list_weights_length_mismatch_raises(self) -> None:
        """单路直通时 weights 长度不匹配应抛 ValidationError（契约校验不因单路绕过）"""
        from src.domain.exceptions import ValidationError

        dense = [_make_result("doc1", 0.95)]
        with pytest.raises(ValidationError):
            fuse(dense, weights=[1.0, 1.0, 0.5])

    def test_single_list_negative_weight_raises(self) -> None:
        """单路直通时负权重应抛 ValidationError"""
        from src.domain.exceptions import ValidationError

        dense = [_make_result("doc1", 0.95)]
        with pytest.raises(ValidationError):
            fuse(dense, weights=[-1.0])

    def test_single_list_valid_weight_passthrough(self) -> None:
        """单路直通时合法权重（长度 1 且非负）正常通过"""
        dense = [_make_result("doc1", 0.95)]
        result = fuse(dense, weights=[1.0])
        assert len(result) == 1

    def test_empty_input_no_lists(self) -> None:
        """无输入 — 返回空列表"""
        result = fuse()
        assert result == []


class TestRrfFusionCustomKValue:
    """自定义 k 值参数"""

    def test_custom_k_2(self) -> None:
        """k=2（更强 top-heavy 偏向，两路融合验证 k 生效）"""
        dense = [
            _make_result("doc1", 0.9),
            _make_result("doc2", 0.8),
        ]
        sparse = [
            _make_result("doc3", 5.0),
        ]

        result = fuse(dense, sparse, k=2)

        # doc1: rank1 in dense → 1/(2+1) = 1/3 ≈ 0.333
        doc1_score = next(r["score"] for r in result if r["id"] == "doc1")
        assert math.isclose(doc1_score, 1 / 3, rel_tol=1e-9)
        # doc2: rank2 in dense → 1/(2+2) = 1/4 = 0.25
        doc2_score = next(r["score"] for r in result if r["id"] == "doc2")
        assert math.isclose(doc2_score, 1 / 4, rel_tol=1e-9)
        # doc3: rank1 in sparse → 1/(2+1) = 1/3 ≈ 0.333
        doc3_score = next(r["score"] for r in result if r["id"] == "doc3")
        assert math.isclose(doc3_score, 1 / 3, rel_tol=1e-9)

    def test_custom_k_10(self) -> None:
        """k=10（两路融合可验证 k 值效果）"""
        result = fuse(
            [_make_result("doc1", 0.9)],
            [_make_result("doc2", 0.8)],
            k=10,
        )

        assert len(result) == 2
        # doc1: 1/(10+1) = 1/11 ≈ 0.0909
        assert math.isclose(result[0]["score"], 1 / 11, rel_tol=1e-9)

    def test_custom_k_100(self) -> None:
        """k=100（大 k 值更平滑，两路各一文档）"""
        result = fuse(
            [_make_result("doc1", 0.9)],
            [_make_result("doc2", 0.8)],
            k=100,
        )

        assert len(result) == 2
        # doc1: 1/(100+1) = 1/101 ≈ 0.00990
        assert math.isclose(result[0]["score"], 1 / 101, rel_tol=1e-9)

    def test_k_zero(self) -> None:
        """k=0 — rank1 得分 = 1（极端情况）"""
        dense = [_make_result("doc1", 0.9)]
        sparse = [_make_result("doc2", 0.8)]

        result = fuse(dense, sparse, k=0)

        # 两路各 1 文档，不同 ID：RRF = 1/(0+1) = 1.0
        assert math.isclose(result[0]["score"], 1.0, rel_tol=1e-9)
        assert math.isclose(result[1]["score"], 1.0, rel_tol=1e-9)

    def test_k_negative_raises_validation_error(self) -> None:
        """k<0 抛出 ValidationError"""
        dense = [_make_result("doc1", 0.9)]
        with pytest.raises(ValidationError, match="k 必须为非负数"):
            fuse(dense, k=-1)

    def test_weights_negative_element_raises_validation_error(self) -> None:
        """weights 含负数时抛出 ValidationError"""
        dense = [_make_result("doc1", 0.9)]
        sparse = [_make_result("doc2", 5.0)]
        with pytest.raises(ValidationError, match="weights 元素必须为非负数"):
            fuse(dense, sparse, weights=[-0.5, 1.0])


class TestRrfFusionIdTypes:
    """不同 ID 类型的支持"""

    def test_str_ids(self) -> None:
        """字符串 ID"""
        results = [
            _make_result("doc-1", 0.9),
            _make_result("doc-2", 0.8),
        ]
        result = fuse(results)
        assert [r["id"] for r in result] == ["doc-1", "doc-2"]

    def test_int_ids(self) -> None:
        """整数 ID（Qdrant ScoredPoint 返回 int）"""
        results = [
            _make_result(1, 0.9),
            _make_result(2, 0.8),
        ]
        result = fuse(results)
        assert [r["id"] for r in result] == [1, 2]

    def test_mixed_str_int_ids(self) -> None:
        """混合 str/int ID"""
        dense = [_make_result("doc-a", 0.9)]
        sparse = [_make_result(42, 5.0)]

        result = fuse(dense, sparse)
        assert len(result) == 2


class TestRrfFusionPerformance:
    """RRF 融合性能验证（P95 < 50ms）"""

    def test_fusion_latency_p95_under_50ms(self) -> None:
        """两路各 ≤50 结果的融合延迟 P95 < 50ms"""
        # 生成 50 个结果（MVP 典型负载）
        dense = [_make_result(f"doc_d_{i}", 0.9 - i * 0.01) for i in range(50)]
        sparse = [_make_result(f"doc_s_{i}", 5.0 - i * 0.1) for i in range(50)]

        latencies: list[float] = []
        for _ in range(100):
            start = time.perf_counter()
            fuse(dense, sparse)
            latencies.append((time.perf_counter() - start) * 1000)  # 转换为 ms

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]

        assert p95 < 50, f"RRF 融合延迟 P95={p95:.2f}ms，超过 50ms 门禁"


class TestRrfFusionDefaultKConstant:
    """默认 k 常量验证"""

    def test_default_k_is_60(self) -> None:
        """默认 k 值为 60（论文经验值）"""
        assert RRF_K_DEFAULT == 60
