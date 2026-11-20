"""CLI 共享输入守卫

参数守卫族（先于 bootstrap——输入错误无需初始化端口注册表，agent_cli
先例）：

- Agent 模式预算守卫：``--yes`` 缺 ``--cost-budget`` → ValidationError
  EXCEPTION_201；
- 实体 ID 族 UUID canonical 归一（plan-id 等）：非 UUID →
  EntityValidationError EXCEPTION_242，大写/URN/无连字符等非 canonical
  形态归一 ``str(uuid.UUID(value))`` 后正确命中（6.9-R1-DF1 新面清偿——
  与存量 agent_cli 宽松守卫静默空态对照）；
- agent-id 族 UUID 守卫：非 UUID → ValidationError EXCEPTION_201
  （``_parse_agent_uuid`` agent_cli.py:156-173 先例）。

守卫分工纪律：实体 ID 族走 242、agent-id 族走 201，禁止混用；
``<tool-id>`` 为 slug、``--checkpoint-no`` 为 CP-N 编号，均不入 UUID 守卫族。
"""

from __future__ import annotations

import uuid as uuid_module
from decimal import Decimal

from src.domain.exceptions import EntityValidationError, ValidationError


def require_agent_budget(*, yes: bool, cost_budget: Decimal | None) -> None:
    """Agent 模式预算守卫（``--yes`` 时必须显式提供 ``--cost-budget``——AC-3）。

    Args:
        yes: Agent 模式开关
        cost_budget: 成本预算（Agent 模式必填）

    Raises:
        ValidationError: EXCEPTION_201——``--yes`` 缺 ``--cost-budget``
    """
    if yes and cost_budget is None:
        raise ValidationError(
            message="--yes Agent 模式必须显式提供 --cost-budget",
            context={"yes": yes, "cost_budget": None},
        )


def canonical_uuid(value: str, *, field: str) -> str:
    """实体 ID 族 UUID canonical 归一守卫（plan-id 族——EXCEPTION_242 契约）。

    大写/URN/无连字符等非 canonical 形态经 ``str(uuid.UUID(value))`` 归一
    （归一后正确命中而非静默空态）；非 UUID 形态拒绝。

    Args:
        value: 原始输入串
        field: 参数名字段（异常 context 定位）

    Returns:
        canonical 小写 UUID 字符串

    Raises:
        EntityValidationError: EXCEPTION_242——非 UUID 输入
    """
    try:
        return str(uuid_module.UUID(value.strip()))
    except ValueError:
        raise EntityValidationError(
            message=f"{field} 必须为 UUID 字符串",
            context={"command": "unified_cli", "field": field, field: value},
        ) from None


def parse_agent_uuid(value: str) -> uuid_module.UUID:
    """agent-id 族 UUID 守卫（EXCEPTION_201——agent_cli 先例形态）。

    Args:
        value: 原始输入串（首尾空白剥离）

    Returns:
        uuid.UUID 实例

    Raises:
        ValidationError: EXCEPTION_201——非 UUID 输入
    """
    normalized = value.strip()
    try:
        return uuid_module.UUID(normalized)
    except ValueError:
        raise ValidationError(
            message=f"agent-id 必须为合法 UUID 字符串: {normalized!r}",
            context={"agent_id": normalized},
        ) from None
