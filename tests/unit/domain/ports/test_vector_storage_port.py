"""VectorStorage Protocol 单元测试。

验证 VectorStorage 和 CollectionManager 接口定义正确。
遵循六边形架构：领域层零依赖，仅使用 Protocol + 标准库。

Reference: Story 1.6 Qdrant Vector Layer
"""

from __future__ import annotations

from src.domain.ports.vector_storage import CollectionManager, VectorStorage


class TestCollectionManagerProtocol:
    """验证 CollectionManager Protocol 接口定义正确。"""

    def test_collection_manager_is_protocol(self) -> None:
        """验证 CollectionManager 是 Protocol。"""
        from typing import Protocol as TypingProtocol

        assert TypingProtocol in CollectionManager.__bases__

    def test_port_has_create_collection_method(self) -> None:
        """验证 create_collection 方法存在。"""
        assert hasattr(CollectionManager, "create_collection")

    def test_port_has_delete_collection_method(self) -> None:
        """验证 delete_collection 方法存在。"""
        assert hasattr(CollectionManager, "delete_collection")

    def test_port_has_collection_exists_method(self) -> None:
        """验证 collection_exists 方法存在。"""
        assert hasattr(CollectionManager, "collection_exists")

    def test_port_has_list_collections_method(self) -> None:
        """验证 list_collections 方法存在。"""
        assert hasattr(CollectionManager, "list_collections")

    def test_create_collection_is_abstractmethod(self) -> None:
        """验证 create_collection 是抽象方法。"""
        method = getattr(CollectionManager, "create_collection")
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_delete_collection_is_abstractmethod(self) -> None:
        """验证 delete_collection 是抽象方法。"""
        method = getattr(CollectionManager, "delete_collection")
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_collection_exists_is_abstractmethod(self) -> None:
        """验证 collection_exists 是抽象方法。"""
        method = getattr(CollectionManager, "collection_exists")
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_list_collections_is_abstractmethod(self) -> None:
        """验证 list_collections 是抽象方法。"""
        method = getattr(CollectionManager, "list_collections")
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_fully_implemented_subclass_can_be_instantiated(self) -> None:
        """验证完全实现抽象方法的子类可以实例化。"""

        class ConcreteCollectionManager(CollectionManager):
            async def create_collection(self, name: str, vector_size: int = 1024, distance: str = "Cosine", **kwargs) -> bool:
                return True

            async def delete_collection(self, name: str) -> bool:
                return True

            async def collection_exists(self, name: str) -> bool:
                return True

            async def list_collections(self) -> list[str]:
                return []

        manager = ConcreteCollectionManager()
        assert manager is not None
        assert hasattr(manager, "create_collection")
        assert hasattr(manager, "delete_collection")
        assert hasattr(manager, "collection_exists")
        assert hasattr(manager, "list_collections")


class TestVectorStorageProtocol:
    """验证 VectorStorage Protocol 接口定义正确。"""

    def test_vector_storage_is_protocol(self) -> None:
        """验证 VectorStorage 是 Protocol。"""
        from typing import Protocol as TypingProtocol

        assert TypingProtocol in VectorStorage.__bases__

    def test_port_has_upsert_points_method(self) -> None:
        """验证 upsert_points 方法存在。"""
        assert hasattr(VectorStorage, "upsert_points")

    def test_port_has_search_method(self) -> None:
        """验证 search 方法存在。"""
        assert hasattr(VectorStorage, "search")

    def test_port_has_search_sparse_method(self) -> None:
        """验证 search_sparse 方法存在。"""
        assert hasattr(VectorStorage, "search_sparse")

    def test_port_has_delete_points_method(self) -> None:
        """验证 delete_points 方法存在。"""
        assert hasattr(VectorStorage, "delete_points")

    def test_port_has_get_point_method(self) -> None:
        """验证 get_point 方法存在。"""
        assert hasattr(VectorStorage, "get_point")

    def test_upsert_points_is_abstractmethod(self) -> None:
        """验证 upsert_points 是抽象方法。"""
        method = getattr(VectorStorage, "upsert_points")
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_search_is_abstractmethod(self) -> None:
        """验证 search 是抽象方法。"""
        method = getattr(VectorStorage, "search")
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_delete_points_is_abstractmethod(self) -> None:
        """验证 delete_points 是抽象方法。"""
        method = getattr(VectorStorage, "delete_points")
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_get_point_is_abstractmethod(self) -> None:
        """验证 get_point 是抽象方法。"""
        method = getattr(VectorStorage, "get_point")
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_search_sparse_is_abstractmethod(self) -> None:
        """验证 search_sparse 是抽象方法。"""
        method = getattr(VectorStorage, "search_sparse")
        assert getattr(method, "__isabstractmethod__", False) is True

    def test_fully_implemented_subclass_can_be_instantiated(self) -> None:
        """验证完全实现抽象方法的子类可以实例化。"""

        class ConcreteVectorStorage(VectorStorage):
            async def upsert_points(self, collection: str, points: list) -> bool:
                return True

            async def search(
                self,
                collection: str,
                query_vector: list[float],
                limit: int = 10,
                filter_payload: dict | None = None,
            ) -> list:
                return []

            async def search_sparse(
                self,
                collection: str,
                sparse_vector,
                limit: int = 10,
                filter_payload: dict | None = None,
            ) -> list:
                return []

            async def delete_points(self, collection: str, point_ids: list[str]) -> bool:
                return True

            async def get_point(self, collection: str, point_id: str) -> dict | None:
                return None

        storage = ConcreteVectorStorage()
        assert storage is not None
        assert hasattr(storage, "upsert_points")
        assert hasattr(storage, "search")
        assert hasattr(storage, "search_sparse")
        assert hasattr(storage, "delete_points")
        assert hasattr(storage, "get_point")
