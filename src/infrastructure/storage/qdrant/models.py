"""Qdrant 向量存储层数据模型。

包含 Collection 配置、向量点和稀疏向量定义。
所有模型位于基础设施层，不污染领域层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class CollectionConfig:
    """Qdrant Collection 配置。

    用于创建和管理向量集合，支持 HNSW 索引配置和多租户隔离。

    字段说明:
        name: Collection 名称（应遵循 sisys:{type}:{namespace} 规范）
        vector_size: 向量维度（bge-m3 为 1024）
        distance: 相似度度量方式（Cosine/Euclidean/Dot）
        shard_number: 分片数量
        replication_factor: 复制因子
        on_disk: 是否将向量存储在磁盘
        hnsw_config: HNSW 索引配置
    """

    name: str
    vector_size: int = 1024
    distance: str = "Cosine"
    shard_number: int = 1
    replication_factor: int = 1
    on_disk: bool = False
    hnsw_config: dict = field(
        default_factory=lambda: {
            "m": 16,
            "ef_construct": 128,
            "full_scan_threshold": 10000,
        }
    )


@dataclass
class VectorPoint:
    """向量点数据模型。

    用于存储和检索向量及其关联的 payload 元数据。

    字段说明:
        id: 向量点唯一标识
        vector: 1024 维浮点向量（bge-m3 嵌入）
        payload: 元数据字典，包含 document_id, chunk_id, business_domain, content_hash
        created_at: 创建时间（UTC）
    """

    id: str
    vector: list[float]
    payload: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self):
        """验证向量维度是否正确。"""
        if len(self.vector) != 1024:
            raise ValueError(f"Vector dimension must be 1024, got {len(self.vector)}")


@dataclass
class SparseVector:
    """稀疏向量模型（用于 BM25 检索）。

    字段说明:
        indices: 词项 ID 列表（词项在词汇表中的位置）
        values: 词项权重列表（TF-IDF 值）
    """

    indices: list[int]
    values: list[float]

    def __post_init__(self):
        """验证 indices 和 values 长度是否匹配。"""
        if len(self.indices) != len(self.values):
            raise ValueError(
                f"indices and values must have same length, got {len(self.indices)} indices and {len(self.values)} values"
            )
