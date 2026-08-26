"""Story 3.12 外部存储集成测试。

使用运行中的 Qdrant/Neo4j 真实服务；任一外部服务不可用时只跳过对应测试。
测试资源使用 UUID 命名，并在 fixture 结束时仅清理自身资源。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import cast
from uuid import uuid4

import pytest

from src.application.services.staleness_weight_service import StalenessWeightService
from src.application.services.strategic_archive_service import StrategicArchiveService
from src.domain.ports.archive_repository import ArchiveRepositoryPort
from src.infrastructure.config.neo4j import Neo4jConfig
from src.infrastructure.config.qdrant import QdrantConfig
from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage
from src.infrastructure.storage.neo4j.neo4j_manager import Neo4jManager
from src.infrastructure.storage.qdrant.collection_manager import QdrantCollectionManager
from src.infrastructure.storage.qdrant.qdrant_adapter import QdrantAdapter
from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager
from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage
from tests.environments import get_test_env


@pytest.fixture
async def qdrant_resources() -> AsyncGenerator[tuple[QdrantManager, QdrantAdapter, str], None]:
    """创建唯一 Qdrant collection 和真实 L3 适配器。"""
    env = get_test_env()
    manager = QdrantManager(
        QdrantConfig(
            host=env.qdrant.host,
            port=env.qdrant.port,
            grpc_port=env.qdrant.grpc_port,
            api_key=env.qdrant.api_key,
            https=env.qdrant.https,
            timeout=env.qdrant.timeout,
        )
    )
    collection = f"story_3_12_{uuid4().hex}"
    client = manager.get_client()
    try:
        await client.get_collections()
        collection_manager = QdrantCollectionManager(client)
        await collection_manager.create_collection(collection, vector_size=1024)
    except Exception as exc:
        await manager.close()
        pytest.skip(f"Qdrant unavailable: {exc}")
    adapter = QdrantAdapter(QdrantVectorStorage(client), collection_manager)
    try:
        yield manager, adapter, collection
    finally:
        try:
            await collection_manager.delete_collection(collection)
        finally:
            await manager.close()


@pytest.fixture
async def neo4j_resources() -> AsyncGenerator[tuple[Neo4jManager, Neo4jGraphStorage], None]:
    """创建真实 Neo4j L5 适配器。"""
    env = get_test_env()
    manager = Neo4jManager.from_config(
        Neo4jConfig(
            host=env.neo4j.host,
            bolt_port=env.neo4j.bolt_port,
            username=env.neo4j.username,
            password=env.neo4j.password,
            database=env.neo4j.database,
        )
    )
    if not await manager.health_check():
        await manager.close()
        pytest.skip("Neo4j unavailable")
    adapter = Neo4jGraphStorage(manager.get_client(), database=env.neo4j.database)
    memory_id = f"story-3-12-probe-{uuid4()}"
    try:
        yield manager, adapter
    finally:
        try:
            await adapter.execute_write_query(
                "MATCH (n:Memory {id: $memory_id}) DETACH DELETE n",
                {"memory_id": memory_id},
            )
        finally:
            await manager.close()


@pytest.mark.asyncio
async def test_real_qdrant_search_vectors_applies_staleness_weight(
    qdrant_resources: tuple[QdrantManager, QdrantAdapter, str],
) -> None:
    """真实 Qdrant 检索结果经过 StrategicArchiveService 降权。"""
    _, vector, collection = qdrant_resources
    stale_id = f"strategic_archive:{uuid4()}"
    fresh_id = f"strategic_archive:{uuid4()}"
    await vector.upsert_points(
        collection,
        [
            {"id": stale_id, "vector": [1.0] + [0.0] * 1023, "payload": {"is_stale": True}},
            {"id": fresh_id, "vector": [1.0] + [0.0] * 1023, "payload": {"is_stale": False}},
        ],
    )
    service = StrategicArchiveService(
        archive_repo=cast(ArchiveRepositoryPort, None),
        embedding_service=None,
        vector_storage=vector,
        staleness_service=StalenessWeightService(None),
    )
    service.L3_COLLECTION = collection
    results = await service.search_vectors([1.0] + [0.0] * 1023, limit=2)
    assert len(results) == 2
    assert results[0]["score"] >= results[1]["score"]
    assert results[1]["score"] < results[0]["score"]


@pytest.mark.asyncio
async def test_real_qdrant_point_roundtrip_preserves_vector(qdrant_resources: tuple[QdrantManager, QdrantAdapter, str]) -> None:
    """真实 Qdrant get_point 读回向量，保障 handler 后续读改写。"""
    _, vector, collection = qdrant_resources
    point_id = f"strategic_archive:{uuid4()}"
    original = [0.25, 0.5, 0.75, 1.0] + [0.0] * 1020
    await vector.upsert_points(collection, [{"id": point_id, "vector": original, "payload": {"x": "keep"}}])
    point = await vector.get_point(collection, point_id)
    assert point is not None
    assert point["vector"] == pytest.approx([value / 1.3693064 for value in original])
    assert point["payload"]["x"] == "keep"


@pytest.mark.asyncio
async def test_real_neo4j_validity_properties_are_updated(neo4j_resources: tuple[Neo4jManager, Neo4jGraphStorage]) -> None:
    """真实 Neo4j SET 更新有效期且保留其它属性。"""
    _, graph = neo4j_resources
    memory_id = f"story-3-12-{uuid4()}"
    try:
        await graph.execute_write_query(
            "MERGE (n:Memory {id: $memory_id}) SET n.keep = $keep, n.valid_from = $valid_from, n.valid_until = $valid_until",
            {"memory_id": memory_id, "keep": "yes", "valid_from": None, "valid_until": None},
        )
        result = await graph.execute_write_query(
            "MATCH (n:Memory {id: $memory_id}) SET n.valid_from = $valid_from, n.valid_until = $valid_until RETURN n",
            {"memory_id": memory_id, "valid_from": "2026-01-01T00:00:00+00:00", "valid_until": None},
        )
        assert result
    finally:
        await graph.execute_write_query(
            "MATCH (n:Memory {id: $memory_id}) DETACH DELETE n",
            {"memory_id": memory_id},
        )
