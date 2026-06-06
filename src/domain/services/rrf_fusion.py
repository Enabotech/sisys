"""领域层 RRF（Reciprocal Rank Fusion）融合算法模块

RRF 出自 Cormack, Clarke, Büttcher 于 SIGIR 2009 发表的论文：
"Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods"
https://doi.org/10.1145/1571941.1572114

论文原文明确写道：
"k = 60 was fixed during a pilot investigation and not altered during subsequent validation"

k=60 是经过大量 TREC 基准和 LETOR 3 数据集验证的鲁棒默认值。
Elasticsearch（rank_constant 社区实践设为 60）、PyTerrier、Pyserini 均推荐 k=60。

设计决策：
- 领域层零外部依赖（仅使用 Python 标准库 collections.defaultdict）
- 函数签名一次到位：fuse(*result_lists, k=60, weights=None) 预留三路扩展
- MVP 阶段对称融合（weights=None），V1 传入 weights 实现加权 RRF
"""

from __future__ import annotations

from src.domain.ports.l3_vector import SearchResult

#: RRF 平滑常数默认值（Cormack et al. SIGIR 2009 经验值）
RRF_K_DEFAULT: int = 60


def fuse(
    *result_lists: list[SearchResult],
    k: int = RRF_K_DEFAULT,
    weights: list[float] | None = None,
) -> list[SearchResult]:
    """RRF 对称/加权融合算法

    对多个检索通道的结果执行 Reciprocal Rank Fusion，
    返回按 RRF 分数降序排列的合并去重列表。

    融合公式：
        RRF_score(d) = Σ w_i / (k + rank_i(d))

    其中 rank_i(d) 从 1 开始计数（论文标准），k 为平滑常数（默认 60）。

    Args:
        *result_lists: 各检索通道的排序结果列表（每个通道内部按相关性降序）
        k: 平滑常数，默认 60（论文经验值，防止 rank 1 绝对主导）
        weights: 各通道权重，默认 None（对称融合，w_i = 1.0）
                 V1（Story 3-4）传入 [w_dense, w_sparse, w_graph] 实现加权 RRF

    Returns:
        按 RRF 分数降序排列的合并去重结果列表

    Raises:
        ValueError: weights 非 None 且长度与 result_lists 不一致时（纯函数参数校验）

    Example:
        MVP（对称融合）:
            >>> fused = fuse(dense_results, sparse_results)

        V1（加权融合）:
            >>> fused = fuse(dense, sparse, graph, weights=[0.4, 0.4, 0.2])

    参考:
        Cormack et al. SIGIR 2009: https://doi.org/10.1145/1571941.1572114
    """
    # 参数校验（纯函数参数契约）
    if k < 0:
        raise ValueError(f"k 必须为非负数，当前值: {k}")
    if not result_lists:
        return []

    # 权重校验
    if weights is not None and len(weights) != len(result_lists):
        raise ValueError(f"weights 长度({len(weights)})与 result_lists 长度({len(result_lists)})不匹配")
    if weights is not None and any(w < 0 for w in weights):
        raise ValueError(f"weights 元素必须为非负数，当前值: {weights}")

    # 单路直通 — 跳过融合（无需计算 RRF）
    if len(result_lists) == 1:
        return list(result_lists[0])

    # 有效权重（对称融合默认 w_i = 1.0）
    effective_weights = weights if weights is not None else [1.0] * len(result_lists)

    # 文档 ID → (累计 RRF 分数, 首次出现的 SearchResult)
    # payload 保留首次出现（跨通道去重时保留最先 encounter 的 payload）
    scores: dict[str | int, tuple[float, SearchResult]] = {}

    for w, results in zip(effective_weights, result_lists):
        for rank, doc in enumerate(results, start=1):  # rank 从 1 开始（论文标准）
            doc_id = doc["id"]
            rrf_score = w / (k + rank)

            if doc_id in scores:
                old_score, old_doc = scores[doc_id]
                # RRF 分数累加，payload 保留首次出现
                scores[doc_id] = (old_score + rrf_score, old_doc)
            else:
                scores[doc_id] = (rrf_score, doc)

    # 按 RRF 分数降序排列，返回标准 SearchResult 格式
    sorted_results = sorted(scores.values(), key=lambda item: item[0], reverse=True)

    return [SearchResult(id=doc["id"], score=score, payload=doc["payload"]) for score, doc in sorted_results]
