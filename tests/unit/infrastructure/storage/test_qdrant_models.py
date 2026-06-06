"""Qdrant 数据模型单元测试

验证 VectorPoint 和 SparseVector 的 __post_init__ 校验逻辑。
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import ValidationError
from src.infrastructure.storage.qdrant.models import (
    CollectionConfig,
    SparseVector,
    VectorPoint,
)


class TestVectorPointValidation:
    """VectorPoint 向量维度校验"""

    def test_valid_vector_point(self) -> None:
        """1024 维向量创建成功"""
        point = VectorPoint(
            id="doc-1",
            vector=[0.1] * 1024,
            payload={"doc_id": "abc"},
        )
        assert point.id == "doc-1"
        assert len(point.vector) == 1024

    def test_invalid_vector_dimension_raises(self) -> None:
        """非 1024 维向量应抛出 ValidationError"""
        with pytest.raises(ValidationError, match="Vector dimension must be 1024"):
            VectorPoint(
                id="doc-1",
                vector=[0.1, 0.2, 0.3],  # 仅 3 维
                payload={},
            )

    def test_invalid_vector_dimension_message_includes_actual(self) -> None:
        """错误消息应包含实际维度数"""
        with pytest.raises(ValidationError, match="got 512"):
            VectorPoint(id="doc-1", vector=[0.0] * 512)


class TestSparseVectorValidation:
    """SparseVector indices/values 长度一致性校验"""

    def test_valid_sparse_vector(self) -> None:
        """indices 和 values 长度一致时创建成功"""
        sv = SparseVector(indices=[1, 2, 3], values=[0.5, 0.3, 0.2])
        assert sv.indices == [1, 2, 3]
        assert sv.values == [0.5, 0.3, 0.2]

    def test_empty_sparse_vector(self) -> None:
        """空 indices 和 values 也应合法"""
        sv = SparseVector(indices=[], values=[])
        assert sv.indices == []
        assert sv.values == []

    def test_mismatched_length_raises(self) -> None:
        """indices 和 values 长度不一致应抛出 ValidationError"""
        with pytest.raises(ValidationError, match="indices and values must have same length"):
            SparseVector(indices=[1, 2, 3], values=[0.5])

    def test_mismatch_message_includes_lengths(self) -> None:
        """错误消息应包含两边的实际长度"""
        with pytest.raises(ValidationError, match="got 3 indices and 1 values"):
            SparseVector(indices=[1, 2, 3], values=[0.5])


class TestCollectionConfigDefaults:
    """CollectionConfig 默认值验证"""

    def test_default_values(self) -> None:
        """默认配置值正确"""
        config = CollectionConfig(name="test-collection")
        assert config.name == "test-collection"
        assert config.vector_size == 1024
        assert config.distance == "Cosine"
        assert config.shard_number == 1
        assert config.replication_factor == 1
        assert config.on_disk is False
        assert config.hnsw_config["m"] == 16
        assert config.hnsw_config["ef_construct"] == 128

    def test_custom_hnsw_config(self) -> None:
        """自定义 HNSW 配置"""
        config = CollectionConfig(
            name="custom",
            hnsw_config={"m": 32, "ef_construct": 256, "full_scan_threshold": 5000},
        )
        assert config.hnsw_config["m"] == 32
        assert config.hnsw_config["ef_construct"] == 256
        assert config.hnsw_config["full_scan_threshold"] == 5000
