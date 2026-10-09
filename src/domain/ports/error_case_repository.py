"""领域层错误案例库仓储端口模块（Story 4.7 AC-5）

定义 ErrorCaseRepositoryPort——错误案例库的持久化端口。

V1 查询语义诚实化：自然键 (tenant_id, tool_id, error_signature) UNIQUE 下
精确匹配至多命中 1 行，即「精确查表」——get_by_natural_key 即全部查询面
（多案例加权检索/向量相似检索登记 deferred-work）。

参数形态（CLAUDE.md §4 端口查询参数决策规则）：
- get_by_natural_key：单字段组合标识查找 → 直接参数
- record_case：命令型 upsert → 实体直接参数
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from src.domain.entities.error_case import ErrorCase

__all__ = ["ErrorCaseRepositoryPort"]


@runtime_checkable
class ErrorCaseRepositoryPort(Protocol):
    """错误案例库仓储端口（自然键精确查询 + 幂等计数回填）"""

    async def get_by_natural_key(
        self,
        tenant_id: uuid.UUID,
        tool_id: uuid.UUID,
        error_signature: str,
    ) -> ErrorCase | None:
        """按自然键精确查询案例.

        Args:
            tenant_id: 租户 ID
            tool_id: 工具 ID
            error_signature: 归一化错误签名（64 hex）

        Returns:
            命中案例；未命中返回 None
        """
        ...

    async def record_case(self, case: ErrorCase) -> ErrorCase:
        """记录案例（自然键 upsert 幂等计数）.

        语义：传入 case 的 recovered_count/infeasible_count 为**本次回填增量**
        （0/1——R3-2 定谳）；已有行按增量累加分类计数并同步递增 occurrence_count
        （守恒不变量），outcome 覆写为最近一次终态；RECOVERED 路径覆写 fix_summary
        （最近一次成功——R8-20），MARKED_INFEASIBLE 路径 fix_summary 不动
        （防不可行写回冲掉修复配方——R1-10）；无既有行时直接建行。

        Args:
            case: 回填形态案例（分类计数为增量、occurrence_count=增量合计）

        Returns:
            回填后的最新案例状态（深拷贝隔离）
        """
        ...
