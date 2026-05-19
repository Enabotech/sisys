"""Saga 场景 S01-S03 集成测试

验证 AC-8: Saga 场景落地
对应 Task 9 的 TDD 测试
"""

from __future__ import annotations

from unittest import mock
from uuid import uuid4

import pytest

from src.domain.ports.saga import SagaStep
from src.infrastructure.saga.saga_orchestrator import SagaOrchestrator
from src.infrastructure.saga.saga_status import SagaStatus


class TestDocumentProcessingSaga:
    """S01: 文档处理 Saga — 正向流程和补偿"""

    @pytest.mark.asyncio
    async def test_s01_forward_execution(self) -> None:
        """S01 文档处理 Saga 应完整执行 4 个步骤"""
        steps = []
        for name in ["upload_document", "save_metadata", "generate_embedding", "extract_entities"]:
            step = mock.AsyncMock(spec=SagaStep)
            step.name = name
            step.execute.return_value = {"status": "completed", "step": name}
            step.compensate.return_value = None
            steps.append(step)

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="DocumentProcessing",
            steps=steps,  # type: ignore[arg-type]
        )

        result = await orchestrator.execute()

        assert result.status == SagaStatus.COMPLETED
        for step in steps:
            step.execute.assert_awaited_once()
            step.compensate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_s01_compensation_on_embedding_failure(self) -> None:
        """S01 generate_embedding 失败时补偿前两步"""
        upload_step = mock.AsyncMock(spec=SagaStep)
        upload_step.name = "upload_document"
        upload_step.execute.return_value = {"url": "s3://doc/1"}
        upload_step.compensate.return_value = None

        metadata_step = mock.AsyncMock(spec=SagaStep)
        metadata_step.name = "save_metadata"
        metadata_step.execute.return_value = {"id": "meta-1"}
        metadata_step.compensate.return_value = None

        embedding_step = mock.AsyncMock(spec=SagaStep)
        embedding_step.name = "generate_embedding"
        embedding_step.execute.side_effect = RuntimeError("Qdrant unavailable")
        embedding_step.compensate.return_value = None

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="DocumentProcessing",
            steps=[upload_step, metadata_step, embedding_step],  # type: ignore[arg-type]
        )

        result = await orchestrator.execute()

        assert result.status == SagaStatus.COMPENSATED
        upload_step.compensate.assert_awaited_once()
        metadata_step.compensate.assert_awaited_once()
        embedding_step.compensate.assert_not_awaited()


class TestMemoryManagementSaga:
    """S02: 记忆管理 Saga"""

    @pytest.mark.asyncio
    async def test_s02_forward_execution(self) -> None:
        """S02 记忆管理 Saga 应完整执行"""
        steps = []
        for name in ["validate_input", "compress_memory", "update_index"]:
            step = mock.AsyncMock(spec=SagaStep)
            step.name = name
            step.execute.return_value = {"status": "completed"}
            step.compensate.return_value = None
            steps.append(step)

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="MemoryManagement",
            steps=steps,  # type: ignore[arg-type]
        )

        result = await orchestrator.execute()

        assert result.status == SagaStatus.COMPLETED


class TestCrossStorageSyncSaga:
    """S03: 跨存储同步 Saga"""

    @pytest.mark.asyncio
    async def test_s03_sync_with_compensation(self) -> None:
        """S03 跨存储同步失败时应补偿已完成的存储操作"""
        pg_step = mock.AsyncMock(spec=SagaStep)
        pg_step.name = "sync_to_postgresql"
        pg_step.execute.return_value = {"rows": 1}
        pg_step.compensate.return_value = None

        neo4j_step = mock.AsyncMock(spec=SagaStep)
        neo4j_step.name = "sync_to_neo4j"
        neo4j_step.execute.side_effect = RuntimeError("Neo4j connection lost")
        neo4j_step.compensate.return_value = None

        orchestrator = SagaOrchestrator(
            saga_id=uuid4(),
            saga_type="CrossStorageSync",
            steps=[pg_step, neo4j_step],  # type: ignore[arg-type]
        )

        result = await orchestrator.execute()

        assert result.status == SagaStatus.COMPENSATED
        pg_step.compensate.assert_awaited_once()
        neo4j_step.compensate.assert_not_awaited()
        assert len(result.errors) == 1
        assert result.errors[0]["step"] == "sync_to_neo4j"
