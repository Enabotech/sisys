"""BM25Builder 单元测试"""

from __future__ import annotations

import pytest

from src.domain.exceptions import ValidationError
from src.infrastructure.storage.qdrant.bm25_builder import BM25Builder
from src.infrastructure.storage.qdrant.models import SparseVector


class TestBM25Builder:
    """BM25Builder 测试类"""

    def test_build_sparse_vector_basic(self):
        """测试基本稀疏向量构建"""
        builder = BM25Builder()
        result = builder.build_sparse_vector("hello world test")

        assert isinstance(result, SparseVector)
        assert len(result.indices) > 0
        assert len(result.values) > 0
        assert len(result.indices) == len(result.values)

    def test_build_sparse_vector_empty(self):
        """测试空文本返回空稀疏向量"""
        builder = BM25Builder()
        result = builder.build_sparse_vector("")

        assert isinstance(result, SparseVector)
        assert result.indices == []
        assert result.values == []

    def test_build_sparse_vector_whitespace(self):
        """测试空白字符返回空稀疏向量"""
        builder = BM25Builder()
        result = builder.build_sparse_vector("   ")

        assert isinstance(result, SparseVector)
        assert result.indices == []
        assert result.values == []

    def test_build_sparse_vector_stopwords(self):
        """测试停用词过滤"""
        builder = BM25Builder()
        result = builder.build_sparse_vector("the a an is")

        assert isinstance(result, SparseVector)
        assert result.indices == []
        assert result.values == []

    def test_build_sparse_vector_single_word(self):
        """测试单个词构建稀疏向量"""
        builder = BM25Builder()
        result = builder.build_sparse_vector("python")

        assert isinstance(result, SparseVector)
        assert len(result.indices) == 1
        assert len(result.values) == 1
        assert result.values[0] > 0

    def test_build_sparse_vector_duplicates(self):
        """测试重复词计算词频"""
        builder = BM25Builder()
        result = builder.build_sparse_vector("python python python")

        assert isinstance(result, SparseVector)
        assert len(result.indices) == 1
        assert result.values[0] > 0

    def test_build_sparse_vector_special_chars(self):
        """测试特殊字符处理"""
        builder = BM25Builder()
        result = builder.build_sparse_vector("hello, world! test?")

        assert isinstance(result, SparseVector)
        assert len(result.indices) > 0
        assert all(v > 0 for v in result.values)

    def test_tokenization(self):
        """测试分词逻辑"""
        builder = BM25Builder()
        tokens = builder._tokenize("Hello, World! Python is great.")

        assert "hello" in tokens
        assert "world" in tokens
        assert "python" in tokens
        assert "great" in tokens
        assert "is" not in tokens  # 停用词

    def test_sparse_vector_validation(self):
        """测试 SparseVector 模型验证"""
        with pytest.raises(ValidationError, match="must have same length"):
            SparseVector(indices=[1, 2], values=[0.5])
