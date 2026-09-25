"""Story 4.1b — DataSourcePort 端口单元测试

验证 DataSourcePort Protocol 的 runtime_checkable 属性、方法签名契约、
合规实现的 isinstance 通过、不合规实现的拒绝（对齐 test_port_contract_sandbox_executor.py
Protocol 结构子类型模式）。
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from typing import Any

from src.domain.ports.data_source import DataSourcePort, DataSourceQuery
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)


class _CompliantAdapter:
    """合规实现桩（满足 DataSourcePort 全部三方法）。"""

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        now = datetime.now(UTC)
        return DataSourceResult(
            source_name=query.source_name,
            payload="{}",
            source_timestamp=now,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=now, ttl_seconds=86400),
            confidence=1.0,
        )

    def get_metadata(self) -> DataSourceRef:
        return DataSourceRef(name="stub", url="https://stub.local", api_type=DataSourceApiType.REST_JSON)

    async def health_check(self) -> bool:
        return True


class _NonCompliantAdapter:
    """不合规实现桩（缺少 health_check）。"""

    async def fetch(self, query: DataSourceQuery) -> Any: ...

    def get_metadata(self) -> Any: ...


class TestDataSourcePortProtocol:
    def test_is_runtime_checkable(self) -> None:
        assert getattr(DataSourcePort, "_is_runtime_protocol", False) is True

    def test_fetch_is_coroutine(self) -> None:
        assert inspect.iscoroutinefunction(DataSourcePort.fetch)

    def test_health_check_is_coroutine(self) -> None:
        assert inspect.iscoroutinefunction(DataSourcePort.health_check)

    def test_get_metadata_is_sync(self) -> None:
        assert not inspect.iscoroutinefunction(DataSourcePort.get_metadata)

    def test_fetch_signature(self) -> None:
        import typing

        sig = inspect.signature(DataSourcePort.fetch)
        params = list(sig.parameters)
        assert params == ["self", "query"]
        hints = typing.get_type_hints(DataSourcePort.fetch)
        assert hints["query"] is DataSourceQuery
        assert hints["return"] is DataSourceResult

    def test_compliant_impl_passes_isinstance(self) -> None:
        assert isinstance(_CompliantAdapter(), DataSourcePort)

    def test_non_compliant_impl_rejected(self) -> None:
        assert not isinstance(_NonCompliantAdapter(), DataSourcePort)
