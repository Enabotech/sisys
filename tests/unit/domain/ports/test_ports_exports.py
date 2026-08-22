"""Domain Ports 导出测试

验证所有新端口都能正确导入
"""

from __future__ import annotations


class TestPortsExport:
    """验证端口导出"""

    def test_l1_cache_port_exported(self) -> None:
        """L1CachePort 应从 ports 模块导出"""
        from src.domain.ports import L1CachePort

        assert L1CachePort is not None

    def test_l3_vector_port_exported(self) -> None:
        """L3VectorPort 应从 ports 模块导出"""
        from src.domain.ports import L3VectorPort

        assert L3VectorPort is not None

    def test_l4_object_port_exported(self) -> None:
        """L4ObjectPort 应从 ports 模块导出"""
        from src.domain.ports import L4ObjectPort

        assert L4ObjectPort is not None

    def test_l5_graph_port_exported(self) -> None:
        """L5GraphPort 应从 ports 模块导出"""
        from src.domain.ports import L5GraphPort

        assert L5GraphPort is not None

    def test_unified_storage_port_exported(self) -> None:
        """UnifiedStoragePort 应从 ports 模块导出"""
        from src.domain.ports import UnifiedStoragePort

        assert UnifiedStoragePort is not None

    def test_storage_layer_exported(self) -> None:
        """StorageLayer 应从 ports 模块导出"""
        from src.domain.ports import StorageLayer

        assert StorageLayer is not None

    def test_storage_tier_exported(self) -> None:
        """StorageTier 应从 ports 模块导出"""
        from src.domain.ports import StorageTier

        assert StorageTier is not None

    def test_data_access_pattern_exported(self) -> None:
        """DataAccessPattern 应从 ports 模块导出"""
        from src.domain.ports import DataAccessPattern

        assert DataAccessPattern is not None

    def test_search_service_port_exported(self) -> None:
        """SearchServicePort 应从 ports 模块导出"""
        from src.domain.ports import SearchServicePort

        assert SearchServicePort is not None

    def test_dense_search_port_exported(self) -> None:
        """DenseSearchPort 应从 ports 模块导出"""
        from src.domain.ports import DenseSearchPort

        assert DenseSearchPort is not None

    def test_sparse_search_port_exported(self) -> None:
        """SparseSearchPort 应从 ports 模块导出"""
        from src.domain.ports import SparseSearchPort

        assert SparseSearchPort is not None

    def test_graph_search_port_exported(self) -> None:
        """GraphSearchPort 应从 ports 模块导出"""
        from src.domain.ports import GraphSearchPort

        assert GraphSearchPort is not None

    def test_hybrid_search_port_exported(self) -> None:
        """HybridSearchPort 应从 ports 模块导出"""
        from src.domain.ports import HybridSearchPort

        assert HybridSearchPort is not None


class TestStorageEnumsValues:
    """验证存储枚举值"""

    def test_storage_layer_has_all_layers(self) -> None:
        """StorageLayer 应包含所有层级"""
        from src.domain.ports import StorageLayer

        assert hasattr(StorageLayer, "L0_FILE")
        assert hasattr(StorageLayer, "L1_CACHE")
        assert hasattr(StorageLayer, "L2_SQL")
        assert hasattr(StorageLayer, "L3_VECTOR")
        assert hasattr(StorageLayer, "L4_OBJECT")
        assert hasattr(StorageLayer, "L5_GRAPH")

    def test_storage_tier_has_all_tiers(self) -> None:
        """StorageTier 应包含所有层级"""
        from src.domain.ports import StorageTier

        assert hasattr(StorageTier, "HOT")
        assert hasattr(StorageTier, "WARM")
        assert hasattr(StorageTier, "COLD")
        assert hasattr(StorageTier, "FROZEN")
