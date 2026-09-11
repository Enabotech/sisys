"""基础设施层 PostgreSQL ToolChainDag 仓储

实现 ToolChainRepositoryPort（Story 4.2 AC-3 + 4.3 后续技术债清理）：
- 继承 PostgreSQLAdapter[ToolChainDag, ToolChainModel]
- nodes JSONB ↔ tuple[ToolChainNode, ...] 双向序列化
- _reverse_adj 重建（领域实体 __post_init__ 自动调用）
- 支持 ToolChainDagQuery 多字段过滤
- 乐观锁：description 字段作为版本戳（如需）

设计依据：Story 4.3 后续技术债清理(路径 2: SQLAlchemy ORM 风格)
- 与现有 archive_repository.py 模式一致
- 通过 _to_entity / _to_model 隔离领域层与 ORM 层
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select

from src.domain.entities.tool_chain import (
    FailureStrategy,
    ToolChainDag,
    ToolChainNode,
)
from src.domain.ports.tool_chain_repository import ToolChainDagQuery
from src.infrastructure.storage.postgresql.models.tool_chain import ToolChainModel
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import (
    PostgreSQLAdapter,
)

logger = logging.getLogger(__name__)


class PostgreSQLToolChainRepository(PostgreSQLAdapter[ToolChainDag, ToolChainModel]):
    """工具链 DAG 仓储实现（SQLAlchemy ORM 风格）

    关键设计：
    - nodes JSONB ↔ tuple[ToolChainNode, ...] 双向序列化
    - 失败策略枚举 → 字符串（DB 存储值，值对象降级）
    - 与 InMemoryToolChainRepository 行为等价（list_by_query + count + 时间倒序）
    """

    pk_column: str = "chain_id"

    def __init__(self) -> None:
        super().__init__(ToolChainModel)

    # ------------------------------------------------------------------
    # 实体/模型转换（nodes JSONB ↔ tuple[ToolChainNode, ...]）
    # ------------------------------------------------------------------

    def _to_entity(self, model: ToolChainModel) -> ToolChainDag:
        """将 ORM 模型转换为领域实体

        Args:
            model: SQLAlchemy ToolChainModel 实例

        Returns:
            ToolChainDag 领域实体
        """
        nodes_data: list[dict[str, Any]] = model.nodes or []
        nodes = tuple(self._deserialize_node(n) for n in nodes_data)
        # 失败策略枚举安全重建（DB 存储字符串值）
        try:
            failure_strategy = (
                FailureStrategy(model.failure_strategy) if model.failure_strategy else FailureStrategy.SKIP_DOWNSTREAM
            )
        except ValueError:
            logger.warning(
                "Invalid failure_strategy %r in DB for chain %s, defaulting to SKIP_DOWNSTREAM",
                model.failure_strategy,
                model.chain_id,
            )
            failure_strategy = FailureStrategy.SKIP_DOWNSTREAM
        return ToolChainDag(
            chain_id=model.chain_id,
            tenant_id=model.tenant_id,
            name=model.name,
            description=model.description or "",
            nodes=nodes,
            failure_strategy=failure_strategy,
            max_concurrency=model.max_concurrency,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: ToolChainDag) -> ToolChainModel:
        """将领域实体转换为 ORM 模型

        Args:
            entity: ToolChainDag 领域实体

        Returns:
            SQLAlchemy ToolChainModel 实例
        """
        nodes_data = [self._serialize_node(n) for n in entity.nodes]
        return ToolChainModel(
            chain_id=entity.chain_id,
            tenant_id=entity.tenant_id,
            name=entity.name,
            description=entity.description,
            nodes=nodes_data,
            failure_strategy=entity.failure_strategy.value,
            max_concurrency=entity.max_concurrency,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def _serialize_node(node: ToolChainNode) -> dict[str, Any]:
        """ToolChainNode → dict（JSONB 元素）

        Args:
            node: 不可变 ToolChainNode 实体

        Returns:
            可序列化为 JSONB 的 dict
        """
        return {
            "node_id": node.node_id,
            "tool_slug": node.tool_slug,
            "depends_on": list(node.depends_on),
            "arguments_template": dict(node.arguments_template),
            "failure_strategy": (node.failure_strategy.value if node.failure_strategy else None),
            "skip_on_upstream_failure": node.skip_on_upstream_failure,
        }

    @staticmethod
    def _deserialize_node(data: dict[str, Any]) -> ToolChainNode:
        """dict → ToolChainNode（JSONB 元素反序列化）

        Args:
            data: JSONB dict（来自 PG rows）

        Returns:
            ToolChainNode 不可变实体
        """
        failure_strategy_value = data.get("failure_strategy")
        failure_strategy = FailureStrategy(failure_strategy_value) if failure_strategy_value else None
        return ToolChainNode(
            node_id=data["node_id"],
            tool_slug=data["tool_slug"],
            depends_on=tuple(data.get("depends_on", ())),
            arguments_template=dict(data.get("arguments_template", {})),
            failure_strategy=failure_strategy,
            skip_on_upstream_failure=bool(data.get("skip_on_upstream_failure", True)),
        )

    # ------------------------------------------------------------------
    # ToolChainRepositoryPort 实现
    # ------------------------------------------------------------------

    def _apply_filters(self, stmt: Any, query: ToolChainDagQuery) -> Any:
        """应用 ToolChainDagQuery 过滤条件到 statement

        Args:
            stmt: SQLAlchemy select/count statement
            query: 查询条件

        Returns:
            添加过滤条件后的 statement
        """
        if query.tenant_id is not None:
            stmt = stmt.where(ToolChainModel.tenant_id == query.tenant_id)
        if query.name is not None:
            stmt = stmt.where(ToolChainModel.name == query.name)
        if query.failure_strategy is not None:
            stmt = stmt.where(ToolChainModel.failure_strategy == query.failure_strategy.value)
        # min_nodes / max_nodes：基于 JSONB 数组长度过滤
        if query.min_nodes is not None:
            stmt = stmt.where(func.jsonb_array_length(ToolChainModel.nodes) >= query.min_nodes)
        if query.max_nodes is not None:
            stmt = stmt.where(func.jsonb_array_length(ToolChainModel.nodes) <= query.max_nodes)
        return stmt

    async def list_by_query(self, query: ToolChainDagQuery) -> list[ToolChainDag]:
        """通过 Query Object 查询 ToolChainDag 列表

        Args:
            query: 查询条件

        Returns:
            符合条件的 ToolChainDag 列表（按 updated_at DESC + offset/limit）
        """
        stmt = select(ToolChainModel)
        stmt = self._apply_filters(stmt, query)
        stmt = stmt.order_by(ToolChainModel.updated_at.desc()).offset(query.offset).limit(query.limit)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def count(self, query: ToolChainDagQuery | None = None) -> int:
        """统计符合条件的 ToolChainDag 数量

        Args:
            query: 查询条件（None 时统计全量,兼容父类 PostgreSQLAdapter.count() 无参签名）

        Returns:
            数量
        """
        if query is None:
            query = ToolChainDagQuery()
        stmt = select(func.count()).select_from(ToolChainModel)
        stmt = self._apply_filters(stmt, query)
        result = await self._session.execute(stmt)
        return int(result.scalar() or 0)


__all__ = [
    "PostgreSQLToolChainRepository",
]
