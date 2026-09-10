"""领域层 Schema 验证记录仓储端口模块

定义 SchemaValidationRecordRepositoryPort(继承 L2RdbPort[SchemaValidationRecord]),
提供 Schema 验证历史的持久化与查询能力。

设计依据：Story 4.3 AC-5
- 继承 L2RdbPort[T] 泛型 async CRUD 基座(沿用 ToolChainDag 模式)
- 扩展 list_by_query(query) / count(query) 方法支持多字段过滤
- @runtime_checkable Protocol 允许 isinstance 检查
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.entities.schema_validation_record import (
    SchemaValidationRecord,
    SchemaValidationRecordQuery,
)
from src.domain.ports.l2_rdb import L2RdbPort


@runtime_checkable
class SchemaValidationRecordRepositoryPort(L2RdbPort[SchemaValidationRecord], Protocol):
    """Schema 验证记录仓储端口（领域层）

    继承 L2RdbPort[SchemaValidationRecord] 获得 async CRUD 基座:
    - async def get_by_id(id) -> SchemaValidationRecord | None
    - async def save(entity) -> SchemaValidationRecord
    - async def delete(id) -> None
    - async def list_all() -> list[SchemaValidationRecord]

    领域扩展方法:
    - async def list_by_query(query) -> list[SchemaValidationRecord]
    - async def count(query) -> int
    """

    async def list_by_query(
        self,
        query: SchemaValidationRecordQuery,
    ) -> list[SchemaValidationRecord]:
        """通过 Query Object 多字段过滤查询

        Args:
            query: 查询条件(tenant_id / tool_id / execution_id / validation_phase / is_valid)

        Returns:
            符合条件的记录列表（按 validated_at DESC 排序 + offset/limit 分页）
        """
        ...

    async def count(self, query: SchemaValidationRecordQuery) -> int:
        """统计符合条件的记录数量

        Args:
            query: 查询条件

        Returns:
            记录总数
        """
        ...


__all__ = ["SchemaValidationRecordRepositoryPort"]
