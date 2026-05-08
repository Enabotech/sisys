"""StorageEnums 枚举测试。

验证 StorageLayer, StorageTier, DataAccessPattern 枚举定义正确。
"""

from __future__ import annotations

from src.domain.ports.storage_enums import DataAccessPattern, StorageLayer, StorageTier


class TestStorageLayer:
    """StorageLayer 枚举测试。"""

    def test_has_all_required_values(self) -> None:
        """StorageLayer 应有所有必需的值。"""
        assert hasattr(StorageLayer, "L0_FILE")
        assert hasattr(StorageLayer, "L1_CACHE")
        assert hasattr(StorageLayer, "L2_SQL")
        assert hasattr(StorageLayer, "L3_VECTOR")
        assert hasattr(StorageLayer, "L4_OBJECT")
        assert hasattr(StorageLayer, "L5_GRAPH")

    def test_values_are_strings(self) -> None:
        """枚举值应为字符串。"""
        assert StorageLayer.L0_FILE.value == "l0_file"
        assert StorageLayer.L1_CACHE.value == "l1_cache"
        assert StorageLayer.L2_SQL.value == "l2_sql"
        assert StorageLayer.L3_VECTOR.value == "l3_vector"
        assert StorageLayer.L4_OBJECT.value == "l4_object"
        assert StorageLayer.L5_GRAPH.value == "l5_graph"


class TestStorageTier:
    """StorageTier 枚举测试。"""

    def test_has_all_required_values(self) -> None:
        """StorageTier 应有所有必需的值。"""
        assert hasattr(StorageTier, "HOT")
        assert hasattr(StorageTier, "WARM")
        assert hasattr(StorageTier, "COLD")
        assert hasattr(StorageTier, "FROZEN")

    def test_values_are_strings(self) -> None:
        """枚举值应为字符串。"""
        assert StorageTier.HOT.value == "hot"
        assert StorageTier.WARM.value == "warm"
        assert StorageTier.COLD.value == "cold"
        assert StorageTier.FROZEN.value == "frozen"


class TestDataAccessPattern:
    """DataAccessPattern 枚举测试。"""

    def test_has_all_required_values(self) -> None:
        """DataAccessPattern 应有所有必需的值。"""
        assert hasattr(DataAccessPattern, "FREQUENT")
        assert hasattr(DataAccessPattern, "OCCASIONAL")
        assert hasattr(DataAccessPattern, "RARE")
        assert hasattr(DataAccessPattern, "ARCHIVED")

    def test_values_are_strings(self) -> None:
        """枚举值应为字符串。"""
        assert DataAccessPattern.FREQUENT.value == "frequent"
        assert DataAccessPattern.OCCASIONAL.value == "occasional"
        assert DataAccessPattern.RARE.value == "rare"
        assert DataAccessPattern.ARCHIVED.value == "archived"
